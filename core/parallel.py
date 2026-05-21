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
                if filtered_count <= max_hands:
                    filtered_hands.append(hand)
            for label, fn, _ in agg_checks:
                if fn(hand):
                    agg_counts[label] += 1

    return agg_counts, attr_freq, filtered_hands, filtered_count, total


def parallel_compute_stats(
    deck: List[Card],
    hand_size: int,
    attr_names: List[str],
    filter_str: str,
    filter_spec: Optional[FilterSpec],
    progress_cb: Optional[Callable[[str], None]] = None,
    abort_flag: Optional[Callable[[], bool]] = None,
    db_conn: Optional[sqlite3.Connection] = None,
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
    max_hands_per_worker = max(1, FILTERED_HANDS_LIMIT // n_workers)
    sequence_orders = dict(_SEQUENCE_ORDER)

    # Interleave deck indices across workers so load is balanced:
    # early indices (more combos) are spread evenly among all workers.
    worker_indices: List[List[int]] = [[] for _ in range(n_workers)]
    for j in range(max_first):
        worker_indices[j % n_workers].append(j)

    args_list = [
        (deck, hand_size, idxs, attr_names, filter_str, max_hands_per_worker, sequence_orders)
        for idxs in worker_indices
        if idxs
    ]

    agg_checks = build_aggregate_checks(attr_names, hand_size, deck, filter_spec)
    merged_counts: Dict[str, int] = {label: 0 for label, _, _ in agg_checks}
    merged_attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    merged_filtered: List[Tuple] = []
    true_filtered_count = 0
    total = 0
    completed = 0

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(_analyze_chunk, args) for args in args_list]
        try:
            for future in as_completed(futures):
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
                    insert_filtered_hands_batch(db_conn, filtered_hands, attr_names)
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
