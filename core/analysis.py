from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

from core.cards import Card, get_sequence_order, _is_consecutive
from core.filters import FilterSpec


# ---------------------------------------------------------------------------
# Aggregate checks — only generate meaningful ones for each attribute
# ---------------------------------------------------------------------------
# build_aggregate_checks() produces the full list of (label, fn, is_filter_row)
# triples that drive the statistics table in the report.
#
# _unique_values_in_deck() is a helper used internally to decide which checks
# are worth including — it counts how many distinct values an attribute has
# across all combinations so that trivially-forced or impossible checks are
# suppressed (see the docstring on build_aggregate_checks for the full rules).

def _unique_values_in_deck(attr: str, combinations: List[Tuple[Card, ...]]) -> int:
    """Count how many distinct values appear for this attr across all hands."""
    seen: set = set()
    for hand in combinations:
        for card in hand:
            seen.add(card.attr(attr))
    return len(seen)


def build_aggregate_checks(
    attr_names: List[str],
    hand_size: int,
    combinations: List[Tuple[Card, ...]],
    filter_spec: Optional[FilterSpec] = None,
) -> List[Tuple[str, any, bool]]:
    """
    Build aggregate checks as (label, fn, is_filter_row) triples.

    FILTER ROWS  (is_filter_row=True)
      One row per filter clause, always at the top of the table, marked with ▶.
      The row counts how many hands (out of ALL hands) match that clause — so
      you can see "full house = 3,744 / 2,598,960 = 0.14%" regardless of what
      else is in the filter.

    AUTO ROWS  (is_filter_row=False)
      Only generated when they are genuinely informative:
      - "All same <attr>"     — always (flush / matching-value check)
      - "All distinct <attr>" — only when n_unique >= hand_size
      - "Straight <attr>"     — only when n_unique > hand_size (otherwise every
                                all-distinct hand is trivially a straight)
      - "Has N-of-a-kind"     — only for meaningful N:
                                  * N <= n_unique  (can't have 4-of-a-kind with 3 values)
                                  * not pigeonhole-forced  (skip when hand_size forces it)
      - Named patterns        — only for attributes where n_unique >= hand_size,
                                meaning there are enough distinct values for the
                                pattern to be non-trivial. This prevents "Full house
                                suit" or "Full house color" for low-cardinality attrs.
      - Pair-attribute checks — always
    """
    checks: List[Tuple[str, any, bool]] = []
    seen_labels: set = set()

    # Dedup helper — silently ignores duplicate labels so filter rows and
    # auto-rows never produce the same entry twice in the output table.
    def add(label: str, fn, is_filter: bool = False) -> None:
        if label not in seen_labels:
            checks.append((label, fn, is_filter))
            seen_labels.add(label)

    # ------------------------------------------------------------------
    # 1. One row per filter clause (marked as filter rows)
    # Each clause gets its own ▶-marked row at the top of the table so the
    # operator can immediately see the count for their exact filter condition.
    # The count is still measured against ALL hands, not just the filtered set.
    # ------------------------------------------------------------------
    if filter_spec:
        for clause in filter_spec.clauses:
            label = clause.describe()
            fn    = clause.matches
            add(label, fn, is_filter=True)

    # ------------------------------------------------------------------
    # 2. Auto-generated rows per attribute
    # For each attribute, generate only the checks that can produce a
    # non-trivial (non-zero, non-100%) result given the deck's cardinality.
    # ------------------------------------------------------------------
    for attr in attr_names:
        a        = attr
        n_unique = _unique_values_in_deck(attr, combinations)
        order    = get_sequence_order(a)
        ord_size = len(order) if order else n_unique

        # All same (e.g. flush) — always meaningful; will be 0 only for
        # attributes with more unique values than hand_size.
        add(f"All same {attr}",
            lambda h, a=a: len({c.attr(a) for c in h}) == 1)

        # All distinct — only when enough unique values exist to fill a hand
        if n_unique >= hand_size:
            add(f"All distinct {attr}",
                lambda h, a=a: len({c.attr(a) for c in h}) == len(h))

        # Straight — only when there's room beyond hand_size for a run to be selective.
        # If n_unique == hand_size then every all-distinct hand is trivially a straight,
        # making it an uninformative duplicate of "All distinct".
        if order and n_unique > hand_size:
            add(f"Straight {attr} (no wrap)",
                lambda h, a=a, order=order, sz=ord_size: (
                    len({c.attr(a) for c in h}) == len(h) and
                    _is_consecutive(
                        [{v: i for i, v in enumerate(order)}.get(c.attr(a), -999) for c in h],
                        wrap=False, total=sz,
                    )
                ))
            add(f"Straight {attr} (wrap-around)",
                lambda h, a=a, order=order, sz=ord_size: (
                    len({c.attr(a) for c in h}) == len(h) and
                    _is_consecutive(
                        [{v: i for i, v in enumerate(order)}.get(c.attr(a), -999) for c in h],
                        wrap=True, total=sz,
                    )
                ))

        # N-of-a-kind — skip when trivially forced by pigeonhole or impossible.
        # pigeonhole_forced: if hand_size > n_unique * (n-1), every hand must
        # contain at least one value ≥ n times (by pigeonhole principle).
        for n in range(2, hand_size + 1):
            pigeonhole_forced = hand_size > n_unique * (n - 1)
            if n <= n_unique and not pigeonhole_forced:
                add(f"Has {n}-of-a-kind {attr}",
                    lambda h, a=a, n=n: any(
                        v >= n for v in Counter(c.attr(a) for c in h).values()
                    ))

        # Named patterns — only for attributes with enough unique values.
        # Low-cardinality attributes (suit=4 unique values, color=2) would produce
        # misleading pattern rows like "Full house suit" — excluded here.
        if n_unique >= hand_size:
            for pattern, name in [
                ((3, 2),       f"Full house {attr} (3+2)"),
                ((4, 1),       f"Four-of-a-kind {attr} (4+1)"),
                ((2, 2, 1),    f"Two pair {attr} (2+2+1)"),
                ((3, 1, 1),    f"Three-of-a-kind {attr} (3+1+1)"),
                ((2, 1, 1),    f"One pair {attr} (2+1+1)"),
                ((2, 1),       f"One pair {attr} (2+1)"),
                ((3, 1),       f"Three-of-a-kind {attr} (3+1)"),
            ]:
                # Only add patterns whose card counts sum to the actual hand size
                if sum(pattern) == hand_size:
                    _p = pattern
                    add(name,
                        lambda h, a=a, p=_p: tuple(sorted(
                            Counter(c.attr(a) for c in h).values(), reverse=True
                        )) == p)

    # ------------------------------------------------------------------
    # 3. All-same for every pair of attributes
    # Checks whether all cards share the same value on both attributes
    # simultaneously (e.g. same rank AND same suit = all identical cards).
    # ------------------------------------------------------------------
    for i, a1 in enumerate(attr_names):
        for a2 in attr_names[i + 1:]:
            _a1, _a2 = a1, a2
            add(f"All same {a1} & {a2}",
                lambda h, a1=_a1, a2=_a2: len({(c.attr(a1), c.attr(a2)) for c in h}) == 1)

    return checks


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
# check_filter_warnings()  — pre-flight validation that catches filter clauses
#                            guaranteed to match zero hands (e.g. pattern sum ≠
#                            hand_size), emitting ⚠ warnings before the scan.
#
# compute_stats()          — single pass over all combinations that:
#                              1. Applies filter_spec to collect matching hands.
#                              2. Runs every aggregate check against ALL hands
#                                 (so percentages are always "% of total").
#                              3. Tallies per-attribute value frequencies across
#                                 the filtered (or all) hands for the frequency table.
#                            Returns a plain dict so print_report() can consume
#                            it without re-running any calculations.

def check_filter_warnings(filter_spec: FilterSpec, hand_size: int) -> List[str]:
    """Return warnings for filter clauses that can never match."""
    warnings = []
    for clause in filter_spec.clauses:
        for tok in clause.tokens:
            if tok.kind == "pattern":
                required = sum(tok.pattern)
                if required != hand_size:
                    warnings.append(
                        f"  ⚠  '{tok.describe()}' needs {required} cards "
                        f"but hand size is {hand_size} — this clause will never match."
                    )
            if tok.kind == "count" and tok.op == "=" and tok.count > hand_size:
                warnings.append(
                    f"  ⚠  '{tok.describe()}' needs {tok.count} cards "
                    f"but hand size is {hand_size} — this clause will never match."
                )
    return warnings


def compute_stats(
    combinations: List[Tuple[Card, ...]],
    filter_spec: Optional[FilterSpec],
    attr_names: List[str],
    hand_size: int,
) -> dict:
    total    = len(combinations)
    # Collect hands that satisfy the filter, or all hands if no filter is active.
    filtered = (
        [h for h in combinations if filter_spec.matches(h)]
        if filter_spec else list(combinations)
    )

    # Build the aggregate check list (suppresses trivial/impossible checks).
    agg_checks = build_aggregate_checks(attr_names, hand_size, combinations, filter_spec)

    # All aggregate counts run against ALL combinations so % are always "% of total".
    # Iterating once and dispatching to each check fn is O(n_combinations * n_checks).
    agg_counts = {label: 0 for label, _, _ in agg_checks}
    for hand in combinations:
        for label, fn, _ in agg_checks:
            if fn(hand):
                agg_counts[label] += 1

    # Per-attribute value frequencies measured across only the filtered hands.
    # Used in the "Attribute Frequency" table to show which values are most common
    # in the result set (e.g. which suits appear most in a flush filter).
    attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    for hand in filtered:
        for card in hand:
            for attr in attr_names:
                attr_freq[attr][card.attr(attr)] += 1

    return {
        "total_combinations": total,
        "filtered_count":     len(filtered),
        "agg_checks":         agg_checks,
        "agg_counts":         agg_counts,
        "attr_freq":          attr_freq,
        "filtered_hands":     filtered,
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
# _pct()         — formats a fraction as a percentage string to 4 decimal places.
#                  Returns "0.0000%" when whole == 0 to avoid ZeroDivisionError.
#
# print_report() — renders the full analysis to stdout in three blocks:
#                    1. Header with total combination count and active filter.
#                    2. Aggregate Statistics table — one row per check, with ▶
#                       markers on filter rows and a visual separator between
#                       filter rows and auto-generated rows.
#                    3. Attribute Frequency table — value counts across the
#                       filtered (or all) hands, sorted by descending frequency.
#                    4. Verbose hand listing (only when --verbose is set).

def _pct(part: int, whole: int) -> str:
    """Return part/whole as a percentage string with 4 decimal places; safe when whole is 0."""
    if whole == 0: return "0.0000%"
    return f"{100 * part / whole:.4f}%"


def print_report(
    stats: dict,
    filter_spec: Optional[FilterSpec],
    hand_size: int,
    attr_names: List[str],
    label_col: Optional[str],
    verbose: bool,
    warnings: Optional[List[str]] = None,
) -> None:
    total      = stats["total_combinations"]
    filtered   = stats["filtered_count"]
    agg_counts = stats["agg_counts"]
    W    = 80
    sep  = "=" * W
    sep2 = "-" * W

    print(sep)
    print(f"  CARD COMBINATION ANALYSIS  —  Hand size: {hand_size}")
    print(sep)
    print(f"\n  Total combinations (C(deck, {hand_size}))  :  {total:,}")

    if filter_spec:
        print(f"\n  Active filter  :  {filter_spec.describe()}")
        print(f"  Matching hands :  {filtered:,}  ({_pct(filtered, total)} of total)")

    if warnings:
        print()
        for w in warnings:
            print(w)

    print(f"\n  Aggregate Statistics  (% of all {total:,} hands)")
    print(sep2)

    printed_divider = False
    for label, _, is_filter_row in stats["agg_checks"]:
        # Print a visual separator between filter rows and auto rows
        if not is_filter_row and not printed_divider:
            if filter_spec:
                print(f"  {'':—<{W-4}}")
            printed_divider = True
        cnt    = agg_counts[label]
        marker = "▶ " if is_filter_row else "  "
        print(f"{marker}{label:<58}  {cnt:>8,}   {_pct(cnt, total):>10}")

    scope = "matching hands" if filter_spec else "all hands"
    print(f"\n  Attribute Frequency  (cards across {scope})")
    print(sep2)
    for attr in attr_names:
        freq = stats["attr_freq"][attr]
        if not freq:
            continue
        print(f"  By {attr}:")
        for value, cnt in sorted(freq.items(), key=lambda x: (-x[1], x[0])):
            print(f"    {value:<26}  {cnt:>8,}")

    if verbose:
        print(f"\n{'Matching Hands':^{W}}")
        print(sep2)
        for i, hand in enumerate(stats["filtered_hands"], 1):
            hand_str = "  |  ".join(c.label(label_col) for c in hand)
            print(f"  {i:>6}.  {hand_str}")

    print(sep)
