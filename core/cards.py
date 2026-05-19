from __future__ import annotations

import csv
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

def _is_consecutive(
    indices: List[int],
    wrap: bool,
    total: int,
    wrap_count: Optional[int] = None,
) -> bool:
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
    if len(big) != 1 or big[0] != total - (n - 1):
        return False
    # wrap_count limits how many cards from the END of the sequence may cross
    # the wrap boundary into the beginning.  The "high group" is the run of
    # cards that sit after the big gap in the sorted index list; a limit of 1
    # allows only one high-end card to wrap (e.g. Ace-low A,2,3,4,5 is valid
    # but Q,K,A,2,3 is not).
    if wrap_count is not None:
        big_gap_pos    = cyclic_gaps.index(big[0])
        high_group_size = n - 1 - big_gap_pos
        if high_group_size > wrap_count:
            return False
    return True


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
