from __future__ import annotations

import csv
import sqlite3
from typing import Callable, List, Optional, Tuple

from core.cards import Card, register_sequence_order
from core.filters import FilterSpec


# ---------------------------------------------------------------------------
# Combinations CSV  —  save / load
# ---------------------------------------------------------------------------
# Generating all C(52, 5) = 2,598,960 hands takes a few seconds; this pair
# of functions lets callers persist that work to disk and reload it later so
# the expensive itertools.combinations() step can be skipped on re-runs.
#
# File format:
#   Headers  →  card1_rank, card1_suit, card1_color, card2_rank, …
#               (one column per (card_position × attribute) combination)
#   Each row →  one complete hand, all card attributes flattened in order
#
# On load, sequence orders are re-inferred from value appearance order so
# the straight filter works exactly as it would after a fresh deck load.
#
# _combo_col_headers()         — pure helper that generates the header list
# save_combinations_csv()      — writes the flat CSV described above
# load_combinations_csv()      — reads it back, returning (combos, attr_names, hand_size)

def _combo_col_headers(attr_names: List[str], hand_size: int) -> List[str]:
    return [f"card{i+1}_{a}" for i in range(hand_size) for a in attr_names]


def save_combinations_csv(
    path: str,
    combinations: List[Tuple[Card, ...]],
    attr_names: List[str],
) -> None:
    if not combinations:
        print("  (no combinations to save)")
        return
    hand_size = len(combinations[0])
    headers = _combo_col_headers(attr_names, hand_size)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for hand in combinations:
            writer.writerow([card.attr(a) for card in hand for a in attr_names])
    print(f"  Saved {len(combinations):,} combinations  →  {path!r}")


def load_combinations_csv(path: str) -> Tuple[List[Tuple[Card, ...]], List[str], int]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Combinations CSV {path!r} has no header row.")
        headers = [h.strip() for h in reader.fieldnames]
        # Infer attribute names from columns prefixed with "card1_".
        # If none exist the file was not produced by save_combinations_csv().
        card1_attrs = [h[len("card1_"):] for h in headers if h.lower().startswith("card1_")]
        if not card1_attrs:
            raise ValueError(
                "Cannot parse combinations CSV — expected columns like 'card1_rank', 'card1_suit' …"
            )
        attr_names = card1_attrs
        # Determine hand size by counting how many columns share the first attribute name
        # (one per card position, e.g. card1_rank, card2_rank, card3_rank … = hand_size 3).
        hand_size  = sum(1 for h in headers if h.lower().endswith(f"_{attr_names[0].lower()}"))
        combinations: List[Tuple[Card, ...]] = []
        for row in reader:
            hand = tuple(
                Card({a: row[f"card{i+1}_{a}"] for a in attr_names})
                for i in range(hand_size)
            )
            combinations.append(hand)

    # Re-infer sequence order from value appearance across all loaded hands
    # so straight detection works identically to a freshly built deck.
    for attr in attr_names:
        seen: List[str] = []
        seen_set: set = set()
        for hand in combinations:
            for card in hand:
                v = card.attr(attr)
                if v not in seen_set:
                    seen.append(v)
                    seen_set.add(v)
        register_sequence_order(attr, seen)

    return combinations, attr_names, hand_size


def stream_combinations_csv_to_db(
    csv_path: str,
    conn: sqlite3.Connection,
    filter_spec: Optional[FilterSpec],
    attr_names: List[str],
    hand_size: int,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[int, int]:
    """
    Read csv_path row-by-row, apply filter_spec, write matching hands to DB in
    batches. Returns (total_count, filtered_count). Never holds more than one
    batch in RAM.
    """
    from core.db import insert_filtered_hands_batch, INSERT_BATCH_SIZE

    total_count    = 0
    filtered_count = 0
    batch: List[Tuple[Card, ...]] = []

    # Re-infer sequence order from the first pass values seen
    seq_seen: dict = {a: {"seen": [], "seen_set": set()} for a in attr_names}

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Combinations CSV {csv_path!r} has no header row.")
        headers   = [h.strip() for h in reader.fieldnames]
        card1_attrs = [h[len("card1_"):] for h in headers if h.lower().startswith("card1_")]
        if not card1_attrs:
            raise ValueError(
                "Cannot parse combinations CSV — expected columns like 'card1_rank', 'card1_suit' …"
            )
        file_attrs = card1_attrs
        file_hand_size = sum(1 for h in headers if h.lower().endswith(f"_{file_attrs[0].lower()}"))

        for row in reader:
            hand = tuple(
                Card({a: row[f"card{i+1}_{a}"] for a in file_attrs})
                for i in range(file_hand_size)
            )
            total_count += 1

            # Track sequence order from values seen
            for a in file_attrs:
                sd = seq_seen[a] if a in seq_seen else None
                if sd is not None:
                    for card in hand:
                        v = card.attr(a)
                        if v not in sd["seen_set"]:
                            sd["seen"].append(v)
                            sd["seen_set"].add(v)

            if filter_spec is None or filter_spec.matches(hand):
                filtered_count += 1
                batch.append(hand)
                if len(batch) >= INSERT_BATCH_SIZE:
                    insert_filtered_hands_batch(conn, batch, attr_names)
                    batch.clear()
                    if progress_cb:
                        progress_cb(f"  Streamed {filtered_count:,} matching rows …")

    if batch:
        insert_filtered_hands_batch(conn, batch, attr_names)

    # Register sequence orders so straight detection works identically
    for a in file_attrs:
        if a in seq_seen:
            register_sequence_order(a, seq_seen[a]["seen"])

    return total_count, filtered_count
