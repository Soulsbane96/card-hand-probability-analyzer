from __future__ import annotations

import itertools
from collections import Counter
from typing import Iterator, List, Optional, Tuple

from core.cards import Card, get_sequence_order, _is_consecutive


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

        # "not:<token>"  — negate whatever token follows
        self.negated = False
        if lo.startswith("not:"):
            self.negated = True
            tok = tok[4:].strip()
            lo  = tok.lower()

        # "all:<attr>"  — every card in the hand shares the same value (e.g. flush)
        if lo.startswith("all:"):
            self.kind = "all";  self.attr = tok[4:].strip();  return

        # "unique:<attr>"  — every card has a different value for this attribute
        if lo.startswith("unique:"):
            self.kind = "unique";  self.attr = tok[7:].strip();  return

        # "straight:<attr>" or "straight:<attr>:wrap" or "straight:<attr>:wrap=N"
        # Values must form a consecutive run in the registered sequence order.
        # Defaults to no-wrap; ":wrap" allows full circular straights; ":wrap=N"
        # additionally caps how many cards from the END of the sequence may cross
        # the wrap boundary (e.g. wrap=1 allows A,2,3,4,5 but not Q,K,A,2,3).
        if lo.startswith("straight:"):
            rest      = tok[9:].split(":")
            self.kind = "straight"
            self.attr = rest[0].strip()
            self.wrap = False
            self.wrap_count: Optional[int] = None
            if len(rest) > 1:
                flag = rest[1].strip().lower()
                if flag.startswith("wrap"):
                    self.wrap = True
                    suffix = flag[4:]   # "" or "=N"
                    if suffix.startswith("="):
                        n = int(suffix[1:])
                        self.wrap_count = n if n > 0 else None
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
            "Valid forms: all:<attr>  unique:<attr>  straight:<attr>[:wrap|:wrap=N|:nowrap]\n"
            "  pattern:<attr>=n+n  nof:<attr><op><n>  <attr>:<value><op><count>"
        )

    def matches(self, hand: Tuple[Card, ...]) -> bool:
        result = self._eval(hand)
        return (not result) if self.negated else result

    def _eval(self, hand: Tuple[Card, ...]) -> bool:
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
            return _is_consecutive([idx_map[v] for v in vals], self.wrap, len(order), self.wrap_count)

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
        prefix = "NOT " if self.negated else ""
        if self.kind == "all":     return f"{prefix}all same {self.attr}"
        if self.kind == "unique":  return f"{prefix}all distinct {self.attr}"
        if self.kind == "straight":
            if not self.wrap:
                wrap_desc = "no wrap"
            elif self.wrap_count is not None:
                wrap_desc = f"wrap ≤{self.wrap_count}"
            else:
                wrap_desc = "wrap"
            return f"{prefix}straight {self.attr} ({wrap_desc})"
        if self.kind == "pattern":
            return f"{prefix}{self.attr} pattern {'+'.join(str(x) for x in self.pattern)}"
        if self.kind == "nof":
            op_word = {"=": "exactly", ">=": "at least", "<=": "at most"}[self.op]
            return f"{prefix}some {self.attr} appears {op_word} {self.count}×"
        op_word = {"=": "exactly", ">=": "at least", "<=": "at most"}[self.op]
        return f"{prefix}{op_word} {self.count} card(s) with {self.attr}={self.value!r}"

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

    def _matches_wildcards_any(self, hand: Tuple[Card, ...]) -> bool:
        """Wildcard mode 'any': hand matches if ANY single consistent substitution
        satisfies every token in this clause simultaneously."""
        for concrete in _expand_wildcards(hand):
            if all(t.matches(concrete) for t in self.tokens):
                return True
        return False

    def _matches_wildcards_optimal(self, hand: Tuple[Card, ...]) -> bool:
        """Wildcard mode 'optimal': wildcards are evaluated with split semantics.

        Positive tokens (negated=False): satisfied if there EXISTS a substitution
        where the token is True.  Negative tokens (negated=True): satisfied only
        if EVERY substitution that passes all positive tokens also keeps the base
        condition False.

        This prevents a wildcard from "dodging" a negated condition by being
        played sub-optimally.  For example, a Joker that can complete a straight
        flush will NOT sneak into the "flush but not straight" bucket just because
        it could also be played as a non-completing card.
        """
        positive = [t for t in self.tokens if not t.negated]
        negative = [t for t in self.tokens if t.negated]

        # Collect every concrete substitution that satisfies all positive conditions.
        valid_subs = [
            concrete
            for concrete in _expand_wildcards(hand)
            if all(t.matches(concrete) for t in positive)
        ]

        if not valid_subs:
            return False

        # Every positive-satisfying substitution must also pass all negative tokens.
        return all(
            all(t.matches(concrete) for t in negative)
            for concrete in valid_subs
        )

    def describe(self) -> str:
        return "  AND  ".join(t.describe() for t in self.tokens)

    def referenced_attrs(self) -> List[str]:
        return [a for t in self.tokens for a in t.referenced_attrs()]


class FilterSpec:
    """Top-level filter parsed from the --filter string.
    Clauses are split on ";" and OR-ed together: a hand matches if ANY single clause matches.

    wildcard_mode controls how flexible cards (wildcards) are evaluated:
      "any"     — hand matches if any single consistent substitution satisfies the full clause.
      "optimal" — positive tokens use EXISTS semantics; negative tokens use FORALL over the
                  positive-satisfying substitutions (wildcards play their best possible hand).
    """

    def __init__(self, filter_str: str, wildcard_mode: str = "any"):
        self.raw           = filter_str.strip()
        self.wildcard_mode = wildcard_mode
        self.clauses       = [FilterClause(c) for c in filter_str.split(";") if c.strip()]

    def matches(self, hand: Tuple[Card, ...]) -> bool:
        if not any(c.is_flexible for c in hand):
            return any(c.matches(hand) for c in self.clauses)
        if self.wildcard_mode == "optimal":
            return any(c._matches_wildcards_optimal(hand) for c in self.clauses)
        return any(c._matches_wildcards_any(hand) for c in self.clauses)

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


def parse_filter(filter_str: str, wildcard_mode: str = "any") -> Optional[FilterSpec]:
    return FilterSpec(filter_str, wildcard_mode=wildcard_mode) if filter_str.strip() else None


# ---------------------------------------------------------------------------
# Wildcard expansion
# ---------------------------------------------------------------------------

def _expand_wildcards(hand: Tuple[Card, ...]) -> Iterator[Tuple[Card, ...]]:
    """Yield all concrete hands produced by substituting each flexible card.

    Each flexible card's pre-resolved alternatives list is used directly, so
    no deck context is needed here.  If a flexible card has no alternatives
    (shouldn't happen after validation, but guards against empty lists),
    the hand is silently dropped.
    """
    wild_indices = [i for i, c in enumerate(hand) if c.is_flexible]
    if not wild_indices:
        yield hand
        return

    alt_lists = [
        [Card(attrs) for attrs in hand[i].alternatives]  # type: ignore[arg-type]
        for i in wild_indices
    ]
    if any(not lst for lst in alt_lists):
        return  # no valid substitutions — hand produces no concrete hands

    for combo in itertools.product(*alt_lists):
        concrete: List[Card] = list(hand)
        for idx, alt in zip(wild_indices, combo):
            concrete[idx] = alt
        yield tuple(concrete)
