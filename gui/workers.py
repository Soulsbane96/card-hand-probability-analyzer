from __future__ import annotations

import itertools
import math
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget

from core import (
    load_combinations_csv,
    load_deck_from_csv,
    build_standard_deck,
    save_combinations_csv,
    parse_filter,
    check_filter_warnings,
    compute_stats,
)


# ---------------------------------------------------------------------------
# Background worker — full analysis pipeline
# ---------------------------------------------------------------------------

class AnalysisWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict, object)   # stats dict, FilterSpec | None
    error    = pyqtSignal(str)

    def __init__(self, params: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.params = params

    def run(self) -> None:
        try:
            p      = self.params
            source = p["source"]

            if source == "load_combos":
                self.progress.emit(f"Loading combinations from {p['load_path']!r} …")
                combos, attr_names, hand_size = load_combinations_csv(p["load_path"])
                self.progress.emit(
                    f"  {len(combos):,} combinations | hand size {hand_size} | "
                    f"attributes: {', '.join(attr_names)}"
                )
            else:
                if source == "csv":
                    self.progress.emit(f"Loading deck from {p['deck_path']!r} …")
                    deck, columns = load_deck_from_csv(p["deck_path"], p["deck_size"])
                    self.progress.emit(
                        f"  {len(deck)} cards | attributes: {', '.join(columns)}"
                    )
                else:
                    deck, columns = build_standard_deck(p["deck_size"])
                    self.progress.emit("Using built-in 52-card deck.")

                attr_names = [c.lower() for c in columns]
                hand_size  = p["hand_size"]

                total_c = math.comb(len(deck), hand_size)
                self.progress.emit(
                    f"Generating C({len(deck)}, {hand_size}) = {total_c:,} combinations …"
                )
                combos = list(itertools.combinations(deck, hand_size))

                if p.get("save_path"):
                    save_combinations_csv(p["save_path"], combos, attr_names)
                    self.progress.emit(f"Saved combinations → {p['save_path']!r}")

            filter_str  = p.get("filter_str", "").strip()
            filter_spec = parse_filter(filter_str)
            if filter_spec:
                filter_spec.validate_attrs(attr_names)

            self.progress.emit("Computing statistics …")
            warnings = check_filter_warnings(filter_spec, hand_size) if filter_spec else []
            stats    = compute_stats(combos, filter_spec, attr_names, hand_size)

            stats["combinations"] = combos
            stats["warnings"]  = warnings
            stats["attr_names"] = attr_names
            stats["hand_size"] = hand_size
            stats["label_col"] = p.get("label_col")
            stats["verbose"]   = p.get("verbose", False)

            self.finished.emit(stats, filter_spec)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Background worker — search and sort for the combinations table
# ---------------------------------------------------------------------------

class SearchSortWorker(QThread):
    """Off-thread search and sort so the UI never freezes on large datasets."""

    finished = pyqtSignal(list)
    aborted  = pyqtSignal()

    def __init__(
        self,
        combinations: List[Tuple],
        matched_indices: frozenset,
        search_text: str,
        show_only_matches: bool,
        sort_col: int,
        sort_order: Qt.SortOrder,
        hand_size: int,
        label_col: Optional[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._combinations     = combinations
        self._matched_indices  = matched_indices
        self._search_text      = search_text.lower()
        self._show_only        = show_only_matches
        self._sort_col         = sort_col
        self._sort_order       = sort_order
        self._hand_size        = hand_size
        self._label_col        = label_col
        self._abort            = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        combos = self._combinations
        lc     = self._label_col

        # Build candidate pool
        if self._show_only:
            candidates = sorted(self._matched_indices)
        else:
            candidates = list(range(len(combos)))

        # Text filter
        text = self._search_text
        if text:
            filtered: List[int] = []
            for i, idx in enumerate(candidates):
                if self._abort:
                    self.aborted.emit()
                    return
                if any(text in card.label(lc).lower() for card in combos[idx]):
                    filtered.append(idx)
                if i % 50_000 == 0 and self._abort:
                    self.aborted.emit()
                    return
            candidates = filtered

        # Sort
        if self._sort_col >= 0 and not self._abort:
            col     = self._sort_col
            reverse = self._sort_order == Qt.SortOrder.DescendingOrder
            candidates.sort(
                key=lambda i: combos[i][col].label(lc).lower(),
                reverse=reverse,
            )

        if self._abort:
            self.aborted.emit()
            return

        self.finished.emit(candidates)
