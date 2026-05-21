from __future__ import annotations

import itertools
import os
import sqlite3
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple

from core.cards import Card, _SEQUENCE_ORDER
from core.filters import FilterSpec


PARALLEL_THRESHOLD = 500_000
FILTERED_HANDS_LIMIT = 1_000_000


def _filter_db_chunk_to_db(args: tuple) -> tuple:
    """
    Worker: read a hand_id range from a tier-1 BLOB DB in pages, apply the filter,
    and write matching hands as JSON to a per-worker temp SQLite DB.
    No hand data crosses IPC — only lightweight stats are returned.

    When skip_auto_agg=True, only filter-clause checks are evaluated per row;
    the caller fills in auto-row counts from the tier-1's stored agg_counts.

    Returns (agg_counts, attr_freq, filtered_count, total).
    """
    (db_path, hand_id_min, hand_id_max, attr_names, filter_str,
     hand_size, deck_attrs, sequence_orders, temp_db_path, skip_auto_agg) = args

    import json as _json
    import sqlite3 as _sqlite3
    import struct
    from collections import Counter
    from core.cards import Card, register_sequence_order
    from core.filters import parse_filter
    from core.analysis import build_aggregate_checks

    for attr, vals in sequence_orders.items():
        register_sequence_order(attr, vals)

    deck = [Card(d) for d in deck_attrs]
    bpc  = 1 if len(deck) <= 256 else 2
    fmt  = f"{hand_size}B" if bpc == 1 else f"{hand_size}H"

    filter_spec = parse_filter(filter_str) if filter_str else None
    all_checks  = build_aggregate_checks(attr_names, hand_size, deck, filter_spec)

    # When tier-1 already has auto-row counts, only evaluate the filter-clause
    # checks per row (typically 1-5 checks vs. 20-50 auto checks).
    active_checks = (
        [(l, fn, is_f) for l, fn, is_f in all_checks if is_f]
        if skip_auto_agg else all_checks
    )

    agg_counts: Dict[str, int]    = {label: 0 for label, _, _ in all_checks}
    attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    filtered_count = 0
    total          = 0

    src_conn = _sqlite3.connect(db_path)
    src_conn.execute("PRAGMA journal_mode=WAL")
    src_conn.execute("PRAGMA query_only=ON")
    src_conn.execute("PRAGMA cache_size=-32768")

    dst_conn = _sqlite3.connect(temp_db_path)
    dst_conn.execute("PRAGMA journal_mode=OFF")
    dst_conn.execute("PRAGMA synchronous=OFF")
    dst_conn.execute("PRAGMA cache_size=-32768")
    dst_conn.execute("CREATE TABLE filtered_hands (hand_json TEXT NOT NULL)")

    PAGE  = 50_000
    BATCH = 10_000
    batch: List[Tuple] = []

    try:
        lo = hand_id_min
        while lo <= hand_id_max:
            hi = min(lo + PAGE - 1, hand_id_max)
            rows = src_conn.execute(
                "SELECT hand_json FROM filtered_hands"
                " WHERE hand_id >= ? AND hand_id <= ?",
                (lo, hi),
            ).fetchall()
            for (blob,) in rows:
                hand = tuple(deck[i] for i in struct.unpack(fmt, blob))
                total += 1
                for label, fn, _ in active_checks:
                    if fn and fn(hand):
                        agg_counts[label] += 1
                if filter_spec is None or filter_spec.matches(hand):
                    filtered_count += 1
                    for card in hand:
                        for attr in attr_names:
                            attr_freq[attr][card.attr(attr)] += 1
                    batch.append((
                        _json.dumps([{a: card.attr(a) for a in attr_names} for card in hand]),
                    ))
                    if len(batch) >= BATCH:
                        dst_conn.executemany(
                            "INSERT INTO filtered_hands VALUES (?)", batch
                        )
                        dst_conn.commit()
                        batch.clear()
            lo = hi + 1
    finally:
        src_conn.close()

    if batch:
        dst_conn.executemany("INSERT INTO filtered_hands VALUES (?)", batch)
        dst_conn.commit()
    dst_conn.close()

    return agg_counts, attr_freq, filtered_count, total


def parallel_stream_db_to_db(
    src_path: str,
    dst_conn: sqlite3.Connection,
    filter_spec,
    filter_str: str,
    attr_names: List[str],
    agg_checks: List[Tuple],
    deck: List[Card],
    hand_size: int,
    progress_cb: Optional[Callable[[str], None]] = None,
    abort_flag: Optional[Callable[[], bool]] = None,
) -> Tuple[int, int]:
    """
    Parallel re-filter of a tier-1 BLOB DB.  Each worker writes its matching
    hands to a local temp SQLite DB; only lightweight stats cross IPC.
    Temp DBs are merged into dst_conn via ATTACH (pure SQLite C layer, no Python
    deserialization of hand data).

    Auto-row agg_counts (All same rank, Straight, Has N-of-a-kind, etc.) are read
    directly from the tier-1 DB — they were computed during the initial build and
    don't change across re-filters.  Workers only evaluate the new filter-clause
    checks per row, which is typically 1-5 checks instead of 20-50.

    Returns (total_count, filtered_count).
    """
    from core.db import write_stats

    probe = sqlite3.connect(src_path)
    probe.execute("PRAGMA journal_mode=WAL")
    row = probe.execute(
        "SELECT MIN(hand_id), MAX(hand_id) FROM filtered_hands"
    ).fetchone()

    # Read stored auto-row agg_counts from tier-1 so workers can skip that work.
    tier1_auto_counts: Dict[str, int] = {}
    try:
        rows = probe.execute(
            "SELECT label, count FROM agg_counts WHERE is_filter = 0"
        ).fetchall()
        tier1_auto_counts = {label: count for label, count in rows}
    except Exception:
        pass
    probe.close()

    if row is None or row[0] is None:
        write_stats(dst_conn, agg_checks,
                    {label: 0 for label, _, _ in agg_checks},
                    {a: Counter() for a in attr_names}, 0, 0)
        return 0, 0

    skip_auto_agg   = bool(tier1_auto_counts)
    id_min, id_max  = row
    total_rows      = id_max - id_min + 1
    n_workers       = min(os.cpu_count() or 2, total_rows)
    # Use more chunks than workers so progress fires frequently (~every few seconds).
    n_chunks        = max(n_workers, min(n_workers * 8, 128))
    chunk_size      = max(1, (total_rows + n_chunks - 1) // n_chunks)
    deck_attrs      = [c.attributes for c in deck]
    sequence_orders = dict(_SEQUENCE_ORDER)

    db_dir  = os.path.dirname(os.path.abspath(src_path))
    db_stem = os.path.splitext(os.path.basename(src_path))[0]

    args_list:  List[Tuple] = []
    temp_paths: List[str]   = []
    lo = id_min
    for i in range(n_chunks):
        hi = lo + chunk_size - 1 if i < n_chunks - 1 else id_max
        if lo > id_max:
            break
        tmp = os.path.join(db_dir, f"{db_stem}_filt_part_{i}.tmp")
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        temp_paths.append(tmp)
        args_list.append((
            src_path, lo, min(hi, id_max),
            attr_names, filter_str, hand_size,
            deck_attrs, sequence_orders, tmp, skip_auto_agg,
        ))
        lo = hi + 1

    merged_counts: Dict[str, int]        = {label: 0 for label, _, _ in agg_checks}
    merged_attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    total = filtered_count = completed   = 0

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(_filter_db_chunk_to_db, a) for a in args_list]
        try:
            for future in as_completed(futures):
                if abort_flag and abort_flag():
                    for f in futures:
                        f.cancel()
                    break
                agg_c, attr_f, fc, tc = future.result()
                for label in merged_counts:
                    merged_counts[label] += agg_c.get(label, 0)
                for attr in attr_names:
                    merged_attr_freq[attr].update(attr_f.get(attr, {}))
                total          += tc
                filtered_count += fc
                completed      += 1
                if progress_cb:
                    progress_cb(
                        f"  Re-filtering … chunk {completed}/{len(args_list)} done,"
                        f" {filtered_count:,} matched so far"
                    )
        except Exception:
            for f in futures:
                f.cancel()
            raise

    # Fill auto-row counts from tier-1 (skips re-computing per-row work done at build time).
    if skip_auto_agg:
        for label, _, is_f in agg_checks:
            if not is_f and label in tier1_auto_counts:
                merged_counts[label] = tier1_auto_counts[label]

    # Merge per-worker temp DBs into dst_conn via ATTACH (no Python deserialization).
    if progress_cb:
        progress_cb("  Merging worker results …")
    for tmp_path in temp_paths:
        if not os.path.isfile(tmp_path):
            continue
        try:
            safe = tmp_path.replace("'", "''")
            dst_conn.execute(f"ATTACH DATABASE '{safe}' AS _fpart")
            dst_conn.execute(
                "INSERT INTO filtered_hands (hand_json) "
                "SELECT hand_json FROM _fpart.filtered_hands"
            )
            dst_conn.commit()
            dst_conn.execute("DETACH DATABASE _fpart")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    write_stats(dst_conn, agg_checks, merged_counts, merged_attr_freq,
                total, filtered_count)
    return total, filtered_count


def _analyze_chunk(args: tuple) -> tuple:
    """
    Worker function: evaluate all combinations where deck[i] is the first card,
    for each i in first_indices.

    Returns (agg_counts, attr_freq, filtered_hands, filtered_count, total).
    filtered_hands is capped at max_hands to bound per-worker memory; attr_freq
    and the true filtered_count are always fully accurate.
    """
    deck, hand_size, first_indices, attr_names, filter_str, max_hands, sequence_orders = args

    from collections import Counter
    from core.cards import register_sequence_order
    from core.filters import parse_filter
    from core.analysis import build_aggregate_checks

    for attr, ordered_values in sequence_orders.items():
        register_sequence_order(attr, ordered_values)

    filter_spec = parse_filter(filter_str) if filter_str else None
    agg_checks = build_aggregate_checks(attr_names, hand_size, deck, filter_spec)
    agg_counts: Dict[str, int] = {label: 0 for label, _, _ in agg_checks}
    attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    filtered_hands: List[Tuple] = []
    filtered_count = 0
    total = 0

    for i in first_indices:
        first = deck[i]
        for rest in itertools.combinations(deck[i + 1:], hand_size - 1):
            hand = (first,) + rest
            total += 1
            if filter_spec is None or filter_spec.matches(hand):
                filtered_count += 1
                for card in hand:
                    for attr in attr_names:
                        attr_freq[attr][card.attr(attr)] += 1
                if max_hands == 0 or filtered_count <= max_hands:
                    filtered_hands.append(hand)
            for label, fn, _ in agg_checks:
                if fn(hand):
                    agg_counts[label] += 1

    return agg_counts, attr_freq, filtered_hands, filtered_count, total


def _analyze_chunk_to_db(args: tuple) -> tuple:
    """
    Worker for tier-1 build: generates combinations for first_indices, writes
    all hands directly to a per-worker temp SQLite DB in batches, and returns
    only lightweight stats.  No hand data is transferred over IPC, so RAM usage
    per worker is bounded by the batch size rather than the full chunk.
    Returns (agg_counts, attr_freq, filtered_count, total).
    """
    (deck_attrs, hand_size, first_indices, attr_names, filter_str,
     sequence_orders, temp_db_path, bpc) = args

    import sqlite3 as _sqlite3
    import struct
    import itertools
    from collections import Counter
    from core.cards import Card, register_sequence_order
    from core.filters import parse_filter
    from core.analysis import build_aggregate_checks

    for attr, vals in sequence_orders.items():
        register_sequence_order(attr, vals)

    deck = [Card(d) for d in deck_attrs]
    deck_to_idx = {c: i for i, c in enumerate(deck)}
    fmt = f"{hand_size}B" if bpc == 1 else f"{hand_size}H"

    filter_spec = parse_filter(filter_str) if filter_str else None
    agg_checks = build_aggregate_checks(attr_names, hand_size, deck, filter_spec)
    agg_counts: Dict[str, int] = {label: 0 for label, _, _ in agg_checks}
    attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    filtered_count = 0
    total = 0

    conn = _sqlite3.connect(temp_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("CREATE TABLE filtered_hands (hand_json BLOB NOT NULL)")

    batch: List[Tuple] = []

    for i in first_indices:
        first = deck[i]
        for rest in itertools.combinations(deck[i + 1:], hand_size - 1):
            hand = (first,) + rest
            total += 1
            for label, fn, _ in agg_checks:
                if fn(hand):
                    agg_counts[label] += 1
            if filter_spec is None or filter_spec.matches(hand):
                filtered_count += 1
                for card in hand:
                    for attr in attr_names:
                        attr_freq[attr][card.attr(attr)] += 1
                batch.append((struct.pack(fmt, *(deck_to_idx[c] for c in hand)),))
                if len(batch) >= 50_000:
                    conn.executemany("INSERT INTO filtered_hands VALUES (?)", batch)
                    conn.commit()
                    batch.clear()

    if batch:
        conn.executemany("INSERT INTO filtered_hands VALUES (?)", batch)
        conn.commit()
    conn.close()

    return agg_counts, attr_freq, filtered_count, total


def parallel_compute_stats(
    deck: List[Card],
    hand_size: int,
    attr_names: List[str],
    filter_str: str,
    filter_spec: Optional[FilterSpec],
    progress_cb: Optional[Callable[[str], None]] = None,
    abort_flag: Optional[Callable[[], bool]] = None,
    db_conn: Optional[sqlite3.Connection] = None,
    no_cap: bool = False,
    tier1_deck: Optional[List[Card]] = None,
) -> dict:
    """
    Distribute combination analysis across CPU cores.
    Returns a dict with the same keys as compute_stats(), so all downstream
    GUI and CLI code works without changes.

    Combinations are never fully materialized — each worker generates only its
    share of starting positions, capping peak RAM to O(chunk) instead of O(total).
    filtered_hands is capped at FILTERED_HANDS_LIMIT to prevent OOM on
    unfiltered large-hand analyses.
    """
    from core.analysis import build_aggregate_checks

    n_deck = len(deck)
    max_first = n_deck - hand_size + 1
    n_workers = min(os.cpu_count() or 2, max_first)
    max_hands_per_worker = 0 if no_cap else max(1, FILTERED_HANDS_LIMIT // n_workers)
    sequence_orders = dict(_SEQUENCE_ORDER)

    # Interleave deck indices across workers so load is balanced:
    # early indices (more combos) are spread evenly among all workers.
    worker_indices: List[List[int]] = [[] for _ in range(n_workers)]
    for j in range(max_first):
        worker_indices[j % n_workers].append(j)

    agg_checks = build_aggregate_checks(attr_names, hand_size, deck, filter_spec)
    merged_counts: Dict[str, int] = {label: 0 for label, _, _ in agg_checks}
    merged_attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    true_filtered_count = 0
    total = 0
    completed = 0

    if no_cap and db_conn is not None:
        # Tier-1 build path: workers write directly to per-worker temp SQLite DBs
        # to avoid accumulating hundreds of millions of hands in RAM before IPC
        # transfer.  Only lightweight stats (agg_counts, attr_freq) cross IPC.
        bpc = 1 if len(deck) <= 256 else 2
        deck_attrs = [c.attributes for c in deck]
        db_file = db_conn.execute("PRAGMA database_list").fetchone()
        main_db_path = db_file[2] if db_file else ""
        active_indices = [idxs for idxs in worker_indices if idxs]
        temp_paths = [f"{main_db_path}_part_{i}.tmp" for i in range(len(active_indices))]

        # Remove any stale temp files from a previously aborted build
        for p in temp_paths:
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        args_list = [
            (deck_attrs, hand_size, idxs, attr_names, filter_str,
             sequence_orders, tmp_path, bpc)
            for idxs, tmp_path in zip(active_indices, temp_paths)
        ]

        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = [executor.submit(_analyze_chunk_to_db, a) for a in args_list]
            try:
                for future in as_completed(futures):
                    if abort_flag and abort_flag():
                        for f in futures:
                            f.cancel()
                        break
                    agg_counts, attr_freq, filtered_count, chunk_total = future.result()
                    for label in merged_counts:
                        merged_counts[label] += agg_counts.get(label, 0)
                    for attr in attr_names:
                        merged_attr_freq[attr].update(attr_freq.get(attr, {}))
                    true_filtered_count += filtered_count
                    total += chunk_total
                    completed += 1
                    if progress_cb:
                        progress_cb(f"  Core {completed} of {len(args_list)} done …")
            except Exception:
                for f in futures:
                    f.cancel()
                raise

        # Merge per-worker temp DBs into the main tier-1 DB via ATTACH so the
        # copy stays in the SQLite C layer rather than deserializing rows in Python.
        if progress_cb:
            progress_cb("  Merging worker databases into tier-1 …")
        for i, tmp_path in enumerate(temp_paths):
            if not os.path.isfile(tmp_path):
                continue
            try:
                safe = tmp_path.replace("'", "''")
                db_conn.execute(f"ATTACH DATABASE '{safe}' AS _t1part")
                db_conn.execute(
                    "INSERT INTO filtered_hands (hand_json) "
                    "SELECT hand_json FROM _t1part.filtered_hands"
                )
                db_conn.commit()
                db_conn.execute("DETACH DATABASE _t1part")
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            if progress_cb:
                progress_cb(f"  Merged part {i + 1} of {len(temp_paths)} …")

        from core.db import write_stats
        write_stats(db_conn, agg_checks, merged_counts, merged_attr_freq,
                    total, true_filtered_count)
        return {
            "total_combinations": total,
            "filtered_count":     true_filtered_count,
            "agg_checks":         agg_checks,
            "agg_counts":         merged_counts,
            "attr_freq":          merged_attr_freq,
            "filtered_hands":     [],
        }

    # Standard (non-tier-1) path: original implementation
    args_list = [
        (deck, hand_size, idxs, attr_names, filter_str, max_hands_per_worker, sequence_orders)
        for idxs in worker_indices
        if idxs
    ]

    merged_filtered: List[Tuple] = []
    deck_to_idx = {c: i for i, c in enumerate(tier1_deck)} if tier1_deck else None

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(_analyze_chunk, args) for args in args_list]
        future_iter = as_completed(futures)
        try:
            for future in future_iter:
                if abort_flag and abort_flag():
                    for f in futures:
                        f.cancel()
                    break
                agg_counts, attr_freq, filtered_hands, filtered_count, chunk_total = future.result()
                for label in merged_counts:
                    merged_counts[label] += agg_counts.get(label, 0)
                for attr in attr_names:
                    merged_attr_freq[attr].update(attr_freq.get(attr, {}))
                if db_conn is not None:
                    from core.db import insert_filtered_hands_batch
                    insert_filtered_hands_batch(
                        db_conn, filtered_hands, attr_names, deck_to_idx=deck_to_idx
                    )
                else:
                    merged_filtered.extend(filtered_hands)
                true_filtered_count += filtered_count
                total += chunk_total
                completed += 1
                if progress_cb:
                    progress_cb(f"  Core {completed} of {len(args_list)} done …")
        except Exception:
            for f in futures:
                f.cancel()
            raise

    if db_conn is not None:
        from core.db import write_stats
        write_stats(db_conn, agg_checks, merged_counts, merged_attr_freq, total, true_filtered_count)

    return {
        "total_combinations": total,
        "filtered_count":     true_filtered_count,
        "agg_checks":         agg_checks,
        "agg_counts":         merged_counts,
        "attr_freq":          merged_attr_freq,
        "filtered_hands":     [] if db_conn is not None else merged_filtered,
    }
