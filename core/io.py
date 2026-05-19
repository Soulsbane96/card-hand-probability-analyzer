from __future__ import annotations

import csv
from typing import List, Tuple

from core.cards import Card, register_sequence_order


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
