from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import struct
from collections import Counter
from typing import Callable, Dict, List, Optional, Tuple

from core.cards import Card


INSERT_BATCH_SIZE = 10_000
PAGE_CACHE_SIZE   = 500
MAX_SEARCHABLE    = 2_000_000
TIER1_SIZE_LIMIT  = 750_000_000

# Per-connection metadata cache: keyed by id(conn).
# Stores is_blob, and for BLOB connections: deck, bpc, fmt, hand_size.
# Cleared in open_results_db to prevent stale hits if an address is reused.
_conn_meta_cache: Dict[int, dict] = {}


def open_results_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _conn_meta_cache.pop(id(conn), None)
    return conn


def _get_conn_meta(conn: sqlite3.Connection) -> dict:
    k = id(conn)
    if k not in _conn_meta_cache:
        fmt_row = conn.execute(
            "SELECT value FROM metadata WHERE key='hand_format'"
        ).fetchone()
        is_blob = fmt_row is not None and fmt_row[0] == "blob"
        if is_blob:
            meta      = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
            deck      = [Card(d) for d in json.loads(meta["deck_json"])]
            bpc       = int(meta.get("bytes_per_card", "1"))
            hand_size = int(meta["hand_size"])
            fmt       = f"{hand_size}B" if bpc == 1 else f"{hand_size}H"
            _conn_meta_cache[k] = {
                "is_blob": True, "deck": deck, "bpc": bpc,
                "fmt": fmt, "hand_size": hand_size,
            }
        else:
            hs_row    = conn.execute(
                "SELECT value FROM metadata WHERE key='hand_size'"
            ).fetchone()
            hand_size = int(hs_row[0]) if hs_row else 0
            _conn_meta_cache[k] = {"is_blob": False, "hand_size": hand_size}
    return _conn_meta_cache[k]


def init_results_db(
    conn: sqlite3.Connection,
    attr_names: List[str],
    hand_size: int,
    deck_hash: str,
    filter_str: str,
    deck: Optional[List[Card]] = None,
) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS filtered_hands (
            hand_id   INTEGER PRIMARY KEY,
            hand_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agg_counts (
            label     TEXT PRIMARY KEY,
            count     INTEGER NOT NULL,
            is_filter INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attr_freq (
            attr  TEXT NOT NULL,
            value TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (attr, value)
        );
    """)
    meta_rows = [
        ("attr_names", json.dumps(attr_names)),
        ("hand_size",  str(hand_size)),
        ("deck_hash",  deck_hash),
        ("filter_str", filter_str),
    ]
    if deck is not None:
        bpc = 1 if len(deck) <= 256 else 2
        meta_rows += [
            ("hand_format",    "blob"),
            ("bytes_per_card", str(bpc)),
            ("deck_json",      json.dumps([c.attributes for c in deck])),
        ]
    conn.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", meta_rows)
    conn.commit()


def insert_filtered_hands_batch(
    conn: sqlite3.Connection,
    hands: List[Tuple[Card, ...]],
    attr_names: List[str],
    deck_to_idx: Optional[Dict[Card, int]] = None,
) -> None:
    if not hands:
        return
    if deck_to_idx is not None:
        # BLOB mode (tier-1): encode each hand as packed card indices
        meta      = _get_conn_meta(conn)
        bpc       = meta.get("bpc", 1)
        hand_size = len(hands[0])
        fmt       = f"{hand_size}B" if bpc == 1 else f"{hand_size}H"
        rows = [
            (struct.pack(fmt, *(deck_to_idx[c] for c in hand)),)
            for hand in hands
        ]
    else:
        # JSON mode (tier-2, unchanged)
        rows = [
            (json.dumps([{a: card.attr(a) for a in attr_names} for card in hand]),)
            for hand in hands
        ]
    conn.executemany("INSERT INTO filtered_hands (hand_json) VALUES (?)", rows)
    conn.commit()


def write_stats(
    conn: sqlite3.Connection,
    agg_checks,
    agg_counts: Dict[str, int],
    attr_freq,
    total: int,
    filtered_count: int,
) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO agg_counts (label, count, is_filter) VALUES (?, ?, ?)",
        [
            (label, agg_counts.get(label, 0), 1 if is_filter else 0)
            for label, _, is_filter in agg_checks
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO attr_freq (attr, value, count) VALUES (?, ?, ?)",
        [
            (attr, value, count)
            for attr, freq in attr_freq.items()
            for value, count in freq.items()
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("total_count",    str(total)),
            ("filtered_count", str(filtered_count)),
        ],
    )
    conn.commit()


def query_hand_page(
    conn: sqlite3.Connection,
    offset: int,
    limit: int,
    attr_names: List[str],
) -> List[Tuple[Card, ...]]:
    rows = conn.execute(
        "SELECT hand_json FROM filtered_hands ORDER BY hand_id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    if not rows:
        return []
    meta = _get_conn_meta(conn)
    if meta["is_blob"]:
        deck, fmt = meta["deck"], meta["fmt"]
        return [tuple(deck[i] for i in struct.unpack(fmt, row[0])) for row in rows]
    result = []
    for (hand_json,) in rows:
        hand = tuple(Card(d) for d in json.loads(hand_json))
        result.append(hand)
    return result


def count_filtered_hands(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM filtered_hands").fetchone()
    return row[0] if row else 0


def read_stats(conn: sqlite3.Connection) -> dict:
    meta = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
    attr_names     = json.loads(meta.get("attr_names", "[]"))
    total          = int(meta.get("total_count",    0))
    filtered_count = int(meta.get("filtered_count", 0))

    agg_rows   = conn.execute(
        "SELECT label, count, is_filter FROM agg_counts ORDER BY rowid"
    ).fetchall()
    agg_counts = {label: count for label, count, _ in agg_rows}
    agg_checks = [
        (label, None, bool(is_filter)) for label, _, is_filter in agg_rows
    ]

    freq_rows  = conn.execute("SELECT attr, value, count FROM attr_freq").fetchall()
    attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    for attr, value, count in freq_rows:
        if attr in attr_freq:
            attr_freq[attr][value] = count

    return {
        "total_combinations": total,
        "filtered_count":     filtered_count,
        "agg_checks":         agg_checks,
        "agg_counts":         agg_counts,
        "attr_freq":          attr_freq,
        "filtered_hands":     [],
    }


def export_csv_from_db(
    conn: sqlite3.Connection,
    csv_path: str,
    attr_names: List[str],
) -> None:
    meta      = _get_conn_meta(conn)
    blob_mode = meta["is_blob"]
    hand_size = meta["hand_size"]

    if blob_mode:
        deck = meta["deck"]
        fmt  = meta["fmt"]
        if hand_size == 0:
            print("  (no combinations to export)")
            return
    else:
        first = conn.execute(
            "SELECT hand_json FROM filtered_hands LIMIT 1"
        ).fetchone()
        if not first:
            print("  (no combinations to export)")
            return
        if hand_size == 0:
            hand_size = len(json.loads(first[0]))

    headers = [f"card{i+1}_{a}" for i in range(hand_size) for a in attr_names]
    total   = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        offset = 0
        while True:
            rows = conn.execute(
                "SELECT hand_json FROM filtered_hands ORDER BY hand_id LIMIT ? OFFSET ?",
                (INSERT_BATCH_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            for (hand_data,) in rows:
                if blob_mode:
                    cards = [deck[i] for i in struct.unpack(fmt, hand_data)]
                    writer.writerow([c.attr(a) for c in cards for a in attr_names])
                else:
                    cards_data = json.loads(hand_data)
                    writer.writerow([d[a] for d in cards_data for a in attr_names])
                total += 1
            offset += INSERT_BATCH_SIZE
    print(f"  Exported {total:,} combinations  ->  {csv_path!r}")


def stream_db_to_db(
    src_conn: sqlite3.Connection,
    dst_conn: sqlite3.Connection,
    filter_spec,
    attr_names: List[str],
    agg_checks: List[Tuple],
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[int, int]:
    """Scan tier-1 (BLOB) through filter_spec and write matching hands to tier-2 (JSON).

    Also accumulates agg_counts and attr_freq, then calls write_stats on dst_conn.
    Returns (total_count, filtered_count).
    """
    src_meta  = _get_conn_meta(src_conn)
    deck      = src_meta["deck"]
    fmt       = src_meta["fmt"]

    merged_counts: Dict[str, int]        = {label: 0 for label, _, _ in agg_checks}
    merged_attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    batch: List[Tuple[Card, ...]]        = []
    total    = 0
    filtered = 0
    offset   = 0

    while True:
        rows = src_conn.execute(
            "SELECT hand_json FROM filtered_hands ORDER BY hand_id LIMIT ? OFFSET ?",
            (INSERT_BATCH_SIZE, offset),
        ).fetchall()
        if not rows:
            break
        for (blob,) in rows:
            hand = tuple(deck[i] for i in struct.unpack(fmt, blob))
            total += 1
            for label, fn, _ in agg_checks:
                if fn and fn(hand):
                    merged_counts[label] += 1
            if filter_spec is None or filter_spec.matches(hand):
                filtered += 1
                for card in hand:
                    for attr in attr_names:
                        merged_attr_freq[attr][card.attr(attr)] += 1
                batch.append(hand)
                if len(batch) >= INSERT_BATCH_SIZE:
                    insert_filtered_hands_batch(dst_conn, batch, attr_names)
                    batch.clear()
        offset += INSERT_BATCH_SIZE
        if progress_cb and total % 1_000_000 == 0:
            progress_cb(
                f"  Re-filtering … {total:,} scanned, {filtered:,} matched"
            )

    if batch:
        insert_filtered_hands_batch(dst_conn, batch, attr_names)

    write_stats(dst_conn, agg_checks, merged_counts, merged_attr_freq, total, filtered)
    return total, filtered


def get_deck_hash(deck: List[Card], deck_source: str) -> str:
    if deck_source == "standard":
        return "standard"
    content = "|".join(
        ":".join(f"{k}={card.attr(k)}" for k in sorted(card._attrs.keys()))
        for card in deck
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def find_cache_db(
    cache_dir: str,
    deck_hash: str,
    hand_size: int,
    filter_str: str,
) -> Optional[str]:
    if not os.path.isdir(cache_dir):
        return None
    filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:8]
    db_path     = os.path.join(cache_dir, f"{deck_hash}_h{hand_size}_{filter_hash}.db")
    if not os.path.isfile(db_path):
        return None
    try:
        c   = sqlite3.connect(db_path)
        row = c.execute(
            "SELECT value FROM metadata WHERE key = 'total_count'"
        ).fetchone()
        c.close()
        if row and int(row[0]) > 0:
            return db_path
    except Exception:
        pass
    return None


def make_cache_db_path(
    cache_dir: str,
    deck_hash: str,
    hand_size: int,
    filter_str: str,
) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:8]
    return os.path.join(cache_dir, f"{deck_hash}_h{hand_size}_{filter_hash}.db")


def find_tier1_db(
    cache_dir: str,
    deck_hash: str,
    hand_size: int,
) -> Optional[str]:
    if not os.path.isdir(cache_dir):
        return None
    db_path = os.path.join(cache_dir, f"{deck_hash}_h{hand_size}_all.db")
    if not os.path.isfile(db_path):
        return None
    try:
        c   = sqlite3.connect(db_path)
        row = c.execute(
            "SELECT value FROM metadata WHERE key = 'total_count'"
        ).fetchone()
        c.close()
        if row and int(row[0]) > 0:
            return db_path
    except Exception:
        pass
    return None


def make_tier1_db_path(
    cache_dir: str,
    deck_hash: str,
    hand_size: int,
) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{deck_hash}_h{hand_size}_all.db")
