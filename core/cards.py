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


# ---------------------------------------------------------------------------
# Attribute value registry
# ---------------------------------------------------------------------------
# Maps each attribute name to all distinct values observed in the deck.
# Populated at deck-load time alongside _SEQUENCE_ORDER.

_ATTR_VALUES: Dict[str, List[str]] = {}

def register_attr_values(attr: str, values: List[str]) -> None:
    _ATTR_VALUES[attr.lower()] = list(values)

def get_attr_values(attr: str) -> Optional[List[str]]:
    return _ATTR_VALUES.get(attr.lower())

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
    def __init__(
        self,
        attributes: Dict[str, str],
        alternatives: Optional[Tuple[Dict[str, str], ...]] = None,
    ):
        self._attrs: Dict[str, str] = {
            k.lower().strip(): v.strip() for k, v in attributes.items()
        }
        # None = regular card; non-empty tuple = flexible card with concrete alternatives.
        # alternatives is NOT included in __hash__/__eq__ — identity is the base attributes only.
        self.alternatives = alternatives

    @property
    def is_flexible(self) -> bool:
        return self.alternatives is not None

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
    register_attr_values("rank", list(_RANKS))
    register_attr_values("suit", list(_SUITS))
    register_attr_values("color", ["Black", "Red"])
    return (deck[:size] if size else deck), ["rank", "suit", "color"]


def load_deck_from_csv(path: str, size: Optional[int] = None) -> Tuple[List[Card], List[str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV {path!r} has no header row.")
        raw_columns = [c.strip() for c in reader.fieldnames]
        # Detect optional alternatives column (case-insensitive).
        alt_col = next((c for c in raw_columns if c.lower().strip() == "alternatives"), None)
        columns = [c for c in raw_columns if c.lower().strip() != "alternatives"]
        rows: List[Tuple[Dict[str, str], str]] = []
        for row in reader:
            alt_str = (row.get(alt_col) or "").strip() if alt_col else ""
            attrs = {k: v for k, v in row.items() if k.lower().strip() != "alternatives"}
            rows.append((attrs, alt_str))
    if not rows:
        raise ValueError(f"CSV {path!r} has no data rows.")
    rows = rows[:size] if size else rows

    # Phase 1: build base cards without alternatives so the registries can be populated.
    base_cards = [Card(attrs) for attrs, _ in rows]

    # Walk every non-alternatives column and record first-seen value order.
    # This preserves the CSV row order as the "natural" sequence for straight detection,
    # and populates the attr-values registry used by wildcard expansion.
    for col in columns:
        key = col.lower()
        seen: List[str] = []
        seen_set: set = set()
        for card in base_cards:
            v = card.attr(key)
            if v not in seen_set:
                seen.append(v)
                seen_set.add(v)
        register_sequence_order(key, seen)
        register_attr_values(key, seen)

    # Phase 2: rebuild any cards that have an alternatives string, now that the
    # full base_cards list is available for deck-relative resolution.
    deck: List[Card] = []
    for (attrs, alt_str), base_card in zip(rows, base_cards):
        if alt_str:
            alts = _parse_alternatives(alt_str, base_cards, base_card)
            deck.append(Card(base_card.attributes, alternatives=alts))
        else:
            deck.append(base_card)
    return deck, columns


def _parse_alternatives(
    alt_str: str,
    deck_cards: List[Card],
    self_card: Card,
) -> Tuple[Dict[str, str], ...]:
    """Resolve an alternatives string into a tuple of concrete attribute dicts.

    Three supported formats (may be mixed via pipe):
      *                            — any other card in the deck
      rank:*,suit:Spades           — any deck card matching fixed attrs (attr:* = wildcard)
      rank:7,suit:Spades|rank:2,suit:Hearts  — explicit pipe-separated groups

    The alternatives are always resolved against actual deck cards so every
    resulting dict is a complete, valid attribute set.
    """
    alt_str = alt_str.strip()

    if alt_str == "*":
        result = tuple(c.attributes for c in deck_cards if c is not self_card)
        if not result:
            raise ValueError("Wildcard '*' matched no other cards in the deck.")
        return result

    # Parse pipe-separated criteria groups.
    criteria_groups: List[Dict[str, str]] = []
    for segment in alt_str.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        criteria: Dict[str, str] = {}
        for pair in segment.split(","):
            pair = pair.strip()
            if ":" not in pair:
                raise ValueError(
                    f"Invalid alternatives entry {pair!r}: expected 'attr:value' or 'attr:*'."
                )
            attr, val = pair.split(":", 1)
            criteria[attr.strip().lower()] = val.strip()
        criteria_groups.append(criteria)

    if not criteria_groups:
        raise ValueError(f"Empty alternatives value: {alt_str!r}")

    # Validate attribute names.
    valid_attrs = {a for card in deck_cards for a in card.attribute_names}
    for criteria in criteria_groups:
        for attr in criteria:
            if attr not in valid_attrs:
                raise ValueError(
                    f"Unknown attribute {attr!r} in alternatives. "
                    f"Available: {', '.join(sorted(valid_attrs))}"
                )

    # Collect matching deck cards for each criteria group.
    # attr:* means "any value" for that attribute (the constraint is skipped).
    seen_keys: set = set()
    result: List[Dict[str, str]] = []
    for criteria in criteria_groups:
        for card in deck_cards:
            if card is self_card:
                continue
            if all(card.attr(a) == v for a, v in criteria.items() if v != "*"):
                key = tuple(sorted(card.attributes.items()))
                if key not in seen_keys:
                    seen_keys.add(key)
                    result.append(card.attributes)

    if not result:
        raise ValueError(
            f"No deck cards matched any alternative in {alt_str!r}. "
            "Check attribute names and values."
        )
    return tuple(result)
