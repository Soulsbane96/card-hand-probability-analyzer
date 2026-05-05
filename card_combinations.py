"""
card_combinations.py
====================
Generate all C(deck_size, X) combinations of cards from a deck,
then report aggregate statistics and filtered results.

DECK SOURCES
  • Built-in standard 52-card deck  (default, no --deck flag)
  • CSV file   --deck my_deck.csv   (any columns, any attribute names)
  • Pre-saved combinations CSV  --load-combos hands5.csv  (skip recalculation)

CSV DECK FORMAT
  Each row is one card; column headers become attribute names.

      Rank,Suit,Color,Value
      2,Clubs,Black,2
      Ace,Spades,Black,14

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FILTER DSL   --filter / -f
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRUCTURE
  • Tokens within a clause are comma-separated and ALL must match (AND).
  • Clauses are semicolon-separated; ANY clause matching = hand matches (OR).

TOKEN REFERENCE
  all:<attr>
      Every card shares the same value for <attr>.
      e.g.  all:suit  →  flush

  unique:<attr>
      Every card has a different value for <attr>.
      e.g.  unique:rank  →  all ranks distinct

  straight:<attr>
  straight:<attr>:nowrap   (default — no wrap-around)
      The hand's values form a run of consecutive steps in the deck's
      natural order (CSV row order / built-in rank order).
      All values must be distinct.
      e.g.  straight:rank           →  3 4 5 6 7 (any suits)
            straight:rank,all:suit  →  straight flush

  straight:<attr>:wrap
      Consecutive on a circular ring — the sequence may cross the
      end-of-order boundary (e.g. A-2-3-4-5, Q-K-A-2-3 …).

  pattern:<attr>=n1+n2+…
      The sorted frequency counts of <attr> values match exactly.
      e.g.  pattern:rank=3+2   →  full house
            pattern:rank=4+1   →  four of a kind
            pattern:rank=2+2+1 →  two pair

  nof:<attr>=<n>     some value of <attr> appears exactly <n> times
  nof:<attr>>=<n>    some value of <attr> appears at least <n> times
  nof:<attr><=<n>    some value of <attr> appears at most  <n> times

  <attr>:<value>=<count>   exactly  <count> cards have attr == value
  <attr>:<value>>=<count>  at least <count> cards have attr == value
  <attr>:<value><=<count>  at most  <count> cards have attr == value

EXAMPLES
  -f "all:suit"                         # Flush
  -f "straight:rank"                    # Straight (no wrap)
  -f "straight:rank,all:suit"           # Straight flush
  -f "pattern:rank=3+2"                 # Full house
  -f "pattern:rank=4+1"                 # Four of a kind
  -f "pattern:rank=2+2+1"              # Two pair
  -f "pattern:rank=3+2;pattern:rank=4+1"  # Full house OR four of a kind
  -f "rank:5=2,suit:Hearts=3"           # Exactly 2 Fives AND 3 Hearts
  -f "straight:rank:wrap"               # Wrap-around straight

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAVING & LOADING COMBINATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Generate once and save to disk
  python card_combinations.py -n 5 --save-combos hands5.csv

  # Later: load and apply any filter instantly
  python card_combinations.py --load-combos hands5.csv -f "straight:rank,all:suit"
"""

from __future__ import annotations

# Standard library imports.
# - argparse: CLI argument parsing
# - csv: reading/writing deck and combination CSV files
# - itertools: combinations() used for efficient hand generation
# - math: math.comb() for computing C(n, k) totals without enumerating
# - Counter: frequency counting for pattern/nof filter token matching
# - Typing helpers: used throughout for annotation clarity
import argparse
import csv
import itertools
import math
from collections import Counter
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Sequence registry
# ---------------------------------------------------------------------------
# Maps a card attribute name (e.g. "rank", "suit") to a list of its values
# in their canonical order.  This order is used by the `straight` filter
# token to decide whether a hand's values form a consecutive run.
#
# The registry is populated at deck-load time:
#   - build_standard_deck()      hard-codes rank and suit orders
#   - load_deck_from_csv()       infers order from CSV row appearance
#   - load_combinations_csv()    infers order by scanning all loaded hands
#
# Supporting functions:
#   register_sequence_order  — write an entry into the registry
#   get_sequence_order       — read an entry (returns None if unregistered)
#   _is_consecutive          — test whether a list of integer indices forms
#                              a run, with optional wrap-around support

_SEQUENCE_ORDER: Dict[str, List[str]] = {}

def register_sequence_order(attr: str, ordered_values: List[str]) -> None:
    _SEQUENCE_ORDER[attr.lower()] = ordered_values

def get_sequence_order(attr: str) -> Optional[List[str]]:
    return _SEQUENCE_ORDER.get(attr.lower())

def _is_consecutive(indices: List[int], wrap: bool, total: int) -> bool:
    s = sorted(indices)
    n = len(s)
    if n < 2:
        return True
    # Non-wrap: every adjacent pair in sorted order must differ by exactly 1.
    if not wrap:
        return all(s[i+1] - s[i] == 1 for i in range(n - 1))
    # Wrap: treat the order as a circular ring of `total` positions.
    # Build the n gaps between consecutive sorted indices plus the one
    # gap that wraps from the last back to the first.  A valid circular
    # straight has exactly one gap that is not 1 (the "break" in the ring),
    # and that break must account for all the remaining positions
    # (i.e. total - (n-1) unit steps).
    cyclic_gaps = [s[i+1] - s[i] for i in range(n - 1)] + [total - s[-1] + s[0]]
    big = [g for g in cyclic_gaps if g != 1]
    return len(big) == 1 and big[0] == total - (n - 1)


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------
# Represents a single card as a flat dict of attribute → value strings.
# Attribute names are normalised to lower-case on construction so callers
# can use any casing.
#
# Key design points for maintainers:
#   - attr()            raises ValueError for unknown names, making filter
#                       errors explicit rather than silently returning None.
#   - label()           produces a human-readable string; falls back to
#                       "key=value  key=value …" for non-standard decks.
#   - __hash__/__eq__   are defined so Card instances can be stored in sets
#                       and used as dict keys (needed by combination dedup).

class Card:
    def __init__(self, attributes: Dict[str, str]):
        self._attrs: Dict[str, str] = {
            k.lower().strip(): v.strip() for k, v in attributes.items()
        }

    def attr(self, name: str) -> str:
        key = name.lower().strip()
        if key not in self._attrs:
            available = ", ".join(sorted(self._attrs.keys()))
            raise ValueError(f"Unknown card attribute {name!r}. Available: {available}")
        return self._attrs[key]

    @property
    def attributes(self) -> Dict[str, str]:
        return dict(self._attrs)

    @property
    def attribute_names(self) -> List[str]:
        return list(self._attrs.keys())

    def label(self, col: Optional[str] = None) -> str:
        if col:
            return self.attr(col)
        if "rank" in self._attrs and "suit" in self._attrs:
            return f"{self._attrs['rank']} of {self._attrs['suit']}"
        return "  ".join(f"{k}={v}" for k, v in self._attrs.items())

    def __str__(self)  -> str: return self.label()
    def __repr__(self) -> str: return f"Card({self._attrs!r})"
    def __hash__(self) -> int: return hash(tuple(sorted(self._attrs.items())))
    def __eq__(self, other) -> bool:
        return isinstance(other, Card) and self._attrs == other._attrs


# ---------------------------------------------------------------------------
# Deck sources
# ---------------------------------------------------------------------------
# Two ways to obtain a deck at runtime:
#
#   build_standard_deck()    — hard-codes the 52-card deck and registers the
#                              canonical rank / suit orders for straight detection.
#   load_deck_from_csv()     — reads any CSV where each row is one card and
#                              column headers become attribute names.  Sequence
#                              order is inferred from the CSV row order, so the
#                              first appearance of each value becomes position 0.
#
# Both functions accept an optional `size` argument to truncate the deck.
# Both return (deck: List[Card], columns: List[str]) so callers always know
# which attribute names are available.

_SUITS  = ("Clubs", "Diamonds", "Hearts", "Spades")
_RANKS  = ("2","3","4","5","6","7","8","9","10","Jack","Queen","King","Ace")
_COLORS = {"Clubs":"Black","Spades":"Black","Hearts":"Red","Diamonds":"Red"}


def build_standard_deck(size: Optional[int] = None) -> Tuple[List[Card], List[str]]:
    deck = [
        Card({"rank": rank, "suit": suit, "color": _COLORS[suit]})
        for suit in _SUITS for rank in _RANKS
    ]
    register_sequence_order("rank", list(_RANKS))
    register_sequence_order("suit", list(_SUITS))
    return (deck[:size] if size else deck), ["rank", "suit", "color"]


def load_deck_from_csv(path: str, size: Optional[int] = None) -> Tuple[List[Card], List[str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV {path!r} has no header row.")
        columns = [c.strip() for c in reader.fieldnames]
        deck = [Card(dict(row)) for row in reader]
    if not deck:
        raise ValueError(f"CSV {path!r} has no data rows.")
    deck = deck[:size] if size else deck
    # Walk every column and record the first-seen order of each value.
    # This preserves the CSV row order as the "natural" sequence, which
    # the straight filter relies on for gap calculations.
    for col in columns:
        key = col.lower()
        seen: List[str] = []
        seen_set: set = set()
        for card in deck:
            v = card.attr(key)
            if v not in seen_set:
                seen.append(v)
                seen_set.add(v)
        register_sequence_order(key, seen)
    return deck, columns


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


# ---------------------------------------------------------------------------
# Filter DSL
# ---------------------------------------------------------------------------
# Parses and evaluates the --filter string into a three-level hierarchy:
#
#   FilterSpec      — top level; one or more clauses joined by ";" (OR logic).
#                     A hand matches the spec if ANY clause matches it.
#
#   FilterClause    — one semicolon-delimited segment; contains one or more
#                     tokens joined by "," (AND logic).  A hand matches the
#                     clause only if ALL tokens match.
#
#   FilterToken     — a single predicate string such as "all:suit" or
#                     "pattern:rank=3+2".  Parsing happens in __init__ via
#                     _parse(); evaluation against a hand is in matches().
#
# To add a new token type:
#   1. Add a branch in FilterToken._parse() that sets self.kind and any
#      needed fields (self.attr, self.count, etc.).
#   2. Add a matching branch in FilterToken.matches().
#   3. Add a branch in FilterToken.describe() for the report label.
#   4. Update referenced_attrs() if the new type uses an attribute name.
#
# parse_filter()   is the public entry point; returns None for empty input.

class FilterToken:
    def __init__(self, token: str):
        self.raw = token.strip()
        self._parse()

    def _parse(self):
        tok = self.raw
        lo  = tok.lower()

        # "all:<attr>"  — every card in the hand shares the same value (e.g. flush)
        if lo.startswith("all:"):
            self.kind = "all";  self.attr = tok[4:].strip();  return

        # "unique:<attr>"  — every card has a different value for this attribute
        if lo.startswith("unique:"):
            self.kind = "unique";  self.attr = tok[7:].strip();  return

        # "straight:<attr>" or "straight:<attr>:wrap"
        # Values must form a consecutive run in the registered sequence order.
        # Defaults to no-wrap; pass ":wrap" for circular (Ace-low) straights.
        if lo.startswith("straight:"):
            rest  = tok[9:].split(":")
            self.kind = "straight"
            self.attr = rest[0].strip()
            flag = rest[1].lower() if len(rest) > 1 else "nowrap"
            self.wrap = True if flag == "wrap" else False
            return

        # "pattern:<attr>=n1+n2+…"
        # The sorted frequency counts of attr values must match exactly.
        # e.g. pattern:rank=3+2  →  full house (stored as (3,2) after sorting)
        if lo.startswith("pattern:"):
            rest = tok[8:]
            attr, pat = rest.split("=", 1)
            self.kind    = "pattern"
            self.attr    = attr.strip()
            self.pattern = tuple(sorted([int(x) for x in pat.strip().split("+")], reverse=True))
            return

        # "nof:<attr><op><n>"  — some value of attr appears op n times
        # op may be >=, <=, or =  (tried in that order to avoid mis-splitting ">=")
        if lo.startswith("nof:"):
            rest = tok[4:]
            for op in (">=", "<=", "="):
                if op in rest:
                    attr, n = rest.split(op, 1)
                    self.kind = "nof";  self.attr = attr.strip()
                    self.op = op;  self.count = int(n.strip())
                    return
            raise ValueError(f"'nof:' token missing operator in {tok!r}")

        # "<attr>:<value><op><count>"  — count cards where attr == value
        # Tries >=, <=, = in that order to avoid splitting ">" from ">="
        for op in (">=", "<=", "="):
            if op in tok:
                left, right = tok.split(op, 1)
                if ":" not in left:
                    raise ValueError(f"Cannot parse filter token {tok!r}: missing ':' before operator.")
                attr, value = left.split(":", 1)
                self.kind = "count";  self.attr = attr.strip()
                self.value = value.strip();  self.op = op;  self.count = int(right.strip())
                return

        raise ValueError(
            f"Cannot parse filter token {tok!r}.\n"
            "Valid forms: all:<attr>  unique:<attr>  straight:<attr>[:wrap|:nowrap]\n"
            "  pattern:<attr>=n+n  nof:<attr><op><n>  <attr>:<value><op><count>"
        )

    def matches(self, hand: Tuple[Card, ...]) -> bool:
        # All cards share the same value for this attribute (e.g. flush = all same suit)
        if self.kind == "all":
            return len({c.attr(self.attr) for c in hand}) == 1

        # Every card has a distinct value for this attribute
        if self.kind == "unique":
            return len({c.attr(self.attr) for c in hand}) == len(hand)

        # Cards form a consecutive run in the registered sequence order.
        # Requires all values to be distinct first to avoid duplicates
        # confusing the index lookup.
        if self.kind == "straight":
            vals = [c.attr(self.attr) for c in hand]
            if len(set(vals)) != len(vals):
                return False
            order = get_sequence_order(self.attr)
            if order is None:
                return False
            idx_map = {v: i for i, v in enumerate(order)}
            if any(v not in idx_map for v in vals):
                return False
            return _is_consecutive([idx_map[v] for v in vals], self.wrap, len(order))

        # Frequency pattern: sorted counts of attr values must match self.pattern exactly
        # e.g. pattern (3,2) matches a hand where one value appears 3× and another 2×
        if self.kind == "pattern":
            freq = tuple(sorted(Counter(c.attr(self.attr) for c in hand).values(), reverse=True))
            return freq == self.pattern

        # N-of-a-kind: at least one value of attr satisfies the count condition
        if self.kind == "nof":
            counts = Counter(c.attr(self.attr) for c in hand).values()
            if self.op == "=":  return any(v == self.count for v in counts)
            if self.op == ">=": return any(v >= self.count for v in counts)
            if self.op == "<=": return any(v <= self.count for v in counts)

        # Exact value count: count cards where attr == self.value and compare to self.count
        if self.kind == "count":
            actual = sum(1 for c in hand if c.attr(self.attr) == self.value)
            if self.op == "=":  return actual == self.count
            if self.op == ">=": return actual >= self.count
            if self.op == "<=": return actual <= self.count

        return False

    def describe(self) -> str:
        if self.kind == "all":     return f"all same {self.attr}"
        if self.kind == "unique":  return f"all distinct {self.attr}"
        if self.kind == "straight":
            return f"straight {self.attr} ({'wrap' if self.wrap else 'no wrap'})"
        if self.kind == "pattern":
            return f"{self.attr} pattern {'+'.join(str(x) for x in self.pattern)}"
        if self.kind == "nof":
            op_word = {"=": "exactly", ">=": "at least", "<=": "at most"}[self.op]
            return f"some {self.attr} appears {op_word} {self.count}×"
        op_word = {"=": "exactly", ">=": "at least", "<=": "at most"}[self.op]
        return f"{op_word} {self.count} card(s) with {self.attr}={self.value!r}"

    def referenced_attrs(self) -> List[str]:
        return [self.attr.lower()]


class FilterClause:
    """AND-group of FilterToken predicates, comma-separated within one semicolon segment.
    A hand matches this clause only when every token in self.tokens returns True."""

    def __init__(self, clause_str: str):
        self.raw    = clause_str.strip()
        self.tokens = [FilterToken(t) for t in clause_str.split(",") if t.strip()]

    def matches(self, hand: Tuple[Card, ...]) -> bool:
        return all(t.matches(hand) for t in self.tokens)

    def describe(self) -> str:
        return "  AND  ".join(t.describe() for t in self.tokens)

    def referenced_attrs(self) -> List[str]:
        return [a for t in self.tokens for a in t.referenced_attrs()]


class FilterSpec:
    """Top-level filter parsed from the --filter string.
    Clauses are split on ";" and OR-ed together: a hand matches if ANY single clause matches."""

    def __init__(self, filter_str: str):
        self.raw     = filter_str.strip()
        self.clauses = [FilterClause(c) for c in filter_str.split(";") if c.strip()]

    def matches(self, hand: Tuple[Card, ...]) -> bool:
        return any(c.matches(hand) for c in self.clauses)

    def describe(self) -> str:
        if len(self.clauses) == 1:
            return self.clauses[0].describe()
        return "  OR  ".join(f"({c.describe()})" for c in self.clauses)

    def validate_attrs(self, attr_names: List[str]) -> None:
        # Called before the main scan so attribute typos surface immediately
        # rather than silently matching zero hands.
        for clause in self.clauses:
            for attr in clause.referenced_attrs():
                if attr not in attr_names:
                    raise ValueError(
                        f"Filter attribute {attr!r} not found. Available: {', '.join(attr_names)}"
                    )


def parse_filter(filter_str: str) -> Optional[FilterSpec]:
    return FilterSpec(filter_str) if filter_str.strip() else None


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
    filter_spec: Optional["FilterSpec"] = None,
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point: parse args → load deck or combinations → apply filter → print report."""
    parser = argparse.ArgumentParser(
        description="Analyse all X-card combinations from a deck.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = parser.add_mutually_exclusive_group()
    src.add_argument("--deck", "-D", type=str, default=None, metavar="CSV_FILE",
        help="CSV deck file (one row per card, headers = attributes). "
             "Omit for the built-in 52-card deck.")
    src.add_argument("--load-combos", type=str, default=None, metavar="CSV_FILE",
        help="Load a previously saved combinations CSV to skip recalculation.")

    parser.add_argument("--hand-size", "-n", type=int, default=5,
        help="Cards per combination (default: 5). Ignored with --load-combos.")
    parser.add_argument("--deck-size", "-d", type=int, default=None,
        help="Use only the first N cards of the deck.")
    parser.add_argument("--save-combos", type=str, default=None, metavar="CSV_FILE",
        help="Save all generated combinations to this CSV file for later reuse.")
    parser.add_argument("--filter", "-f", type=str, default="",
        metavar="FILTER_STRING",
        help=(
            "Filter string. Comma = AND within a clause, semicolon = OR between clauses.\n"
            "Tokens: all:<a>  unique:<a>  straight:<a>[:wrap]  pattern:<a>=n+n\n"
            "        nof:<a><op><n>  <a>:<v><op><count>   (op: =  >=  <=)"
        ),
    )
    parser.add_argument("--label-col", type=str, default=None, metavar="COLUMN",
        help="Column to use as card label in verbose output.")
    parser.add_argument("--list-attrs", action="store_true",
        help="Print attribute names and unique values, then exit.")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Print every matching hand (can be very large!).")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load / generate combinations
    # ------------------------------------------------------------------
    if args.load_combos:
        print(f"\nLoading combinations from  {args.load_combos!r} …")
        try:
            combos, attr_names, hand_size = load_combinations_csv(args.load_combos)
        except FileNotFoundError:
            parser.error(f"File not found: {args.load_combos!r}")
        except Exception as exc:
            parser.error(str(exc))
        columns    = attr_names
        print(f"  {len(combos):,} combinations loaded  |  "
              f"Hand size: {hand_size}  |  Attributes: {', '.join(attr_names)}")

    else:
        if args.deck:
            print(f"\nLoading deck from  {args.deck!r} …")
            try:
                deck, columns = load_deck_from_csv(args.deck, args.deck_size)
            except FileNotFoundError:
                parser.error(f"File not found: {args.deck!r}")
            except Exception as exc:
                parser.error(str(exc))
            print(f"  {len(deck)} cards loaded  |  Attributes: {', '.join(columns)}")
        else:
            deck, columns = build_standard_deck(args.deck_size)
            print(f"\nUsing built-in 52-card deck"
                  f"{f' (first {args.deck_size})' if args.deck_size else ''}.")

        attr_names = [c.lower() for c in columns]
        hand_size  = args.hand_size

        if args.list_attrs:
            print("\nCard attributes in this deck:")
            for col in columns:
                key   = col.lower()
                order = get_sequence_order(key)
                vals  = order if order else sorted({c.attr(key) for c in deck})
                print(f"  {col:24}  ({len(vals):>3} unique):  {', '.join(vals)}")
            return

        if hand_size > len(deck):
            parser.error(f"Hand size {hand_size} exceeds deck size {len(deck)}.")

        total_count = math.comb(len(deck), hand_size)
        print(f"\nGenerating C({len(deck)}, {hand_size}) = {total_count:,} combinations …")
        combos = list(itertools.combinations(deck, hand_size))

        if args.save_combos:
            save_combinations_csv(args.save_combos, combos, attr_names)

    # ------------------------------------------------------------------
    # Parse & validate filter
    # ------------------------------------------------------------------
    filter_spec = parse_filter(args.filter)
    if filter_spec:
        try:
            filter_spec.validate_attrs(attr_names)
        except ValueError as exc:
            parser.error(str(exc))

    # ------------------------------------------------------------------
    # Analyse & report
    # ------------------------------------------------------------------
    warnings = check_filter_warnings(filter_spec, hand_size) if filter_spec else []
    stats = compute_stats(combos, filter_spec, attr_names, hand_size)
    print_report(stats, filter_spec, hand_size, attr_names, args.label_col, args.verbose, warnings)


if __name__ == "__main__":
    main()