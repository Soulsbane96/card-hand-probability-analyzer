from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.filters import FilterSpec
from gui.table_model import (
    NumericItem,
    CombinationsTableModel,
    _build_matched_set,
    _highlight_color,
)
from gui.workers import SearchSortWorker


# ---------------------------------------------------------------------------
# All Combinations viewer  (virtual model/view for large datasets)
# ---------------------------------------------------------------------------

class AllCombinationsWidget(QWidget):
    """Tab widget that shows all combinations with search, sort, and filter-match
    highlighting.  Uses CombinationsTableModel (virtual) so row count has no
    impact on memory or initial paint time."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[SearchSortWorker] = None
        self._pending_search: str = ""
        self._pending_show_matches: bool = False
        self._build_ui()

    def _build_ui(self) -> None:
        self._model = CombinationsTableModel(self)

        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setSortingEnabled(False)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._view.setAlternatingRowColors(False)
        self._view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search…")
        self._search_edit.setMaximumWidth(280)
        self._search_edit.textChanged.connect(self._on_search_changed)

        self._matches_only_check = QCheckBox("Show only matches")
        self._matches_only_check.stateChanged.connect(self._on_matches_only_changed)

        self._count_label = QLabel("No combinations loaded.")

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_fired)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search_edit)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._matches_only_check)
        toolbar.addStretch()
        toolbar.addWidget(self._count_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(toolbar)
        layout.addWidget(self._view)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(
        self,
        combinations: List[Tuple],
        matched_indices: frozenset,
        hand_size: int,
        label_col: Optional[str],
    ) -> None:
        self._abort_worker()
        self._model.update_data(combinations, matched_indices, hand_size, label_col)
        self._search_edit.blockSignals(True)
        self._search_edit.clear()
        self._search_edit.blockSignals(False)
        self._matches_only_check.blockSignals(True)
        self._matches_only_check.setChecked(False)
        self._matches_only_check.setEnabled(bool(matched_indices))
        self._matches_only_check.blockSignals(False)
        self._pending_search = ""
        self._pending_show_matches = False
        self._trigger_search_sort("", False, -1, Qt.SortOrder.AscendingOrder)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self._pending_search = text
        self._debounce_timer.start(300)

    def _on_matches_only_changed(self, state: int) -> None:
        self._pending_show_matches = bool(state)
        self._debounce_timer.stop()
        self._fire_search()

    def _on_debounce_fired(self) -> None:
        self._fire_search()

    def _on_header_clicked(self, logical_index: int) -> None:
        if self._model._sort_col == logical_index:
            order = (
                Qt.SortOrder.DescendingOrder
                if self._model._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = Qt.SortOrder.AscendingOrder
        self._model._sort_col   = logical_index
        self._model._sort_order = order
        self._view.horizontalHeader().setSortIndicator(logical_index, order)
        self._view.horizontalHeader().setSortIndicatorShown(True)
        self._debounce_timer.stop()
        self._trigger_search_sort(
            self._pending_search,
            self._pending_show_matches,
            logical_index,
            order,
        )

    def _on_worker_finished(self, indices: list) -> None:
        self._model.apply_results(indices)
        self._update_count_label()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fire_search(self) -> None:
        self._trigger_search_sort(
            self._pending_search,
            self._pending_show_matches,
            self._model._sort_col,
            self._model._sort_order,
        )

    def _trigger_search_sort(
        self,
        search_text: str,
        show_only_matches: bool,
        sort_col: int,
        sort_order: Qt.SortOrder,
    ) -> None:
        self._abort_worker()
        if not self._model._combinations:
            return
        self._worker = SearchSortWorker(
            self._model._combinations,
            self._model._matched_indices,
            search_text,
            show_only_matches,
            sort_col,
            sort_order,
            self._model._hand_size,
            self._model._label_col,
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _abort_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait()
        self._worker = None

    def _update_count_label(self) -> None:
        showing = len(self._model._display_indices)
        total   = len(self._model._combinations)
        self._count_label.setText(f"Showing {showing:,} of {total:,} combinations")


# ---------------------------------------------------------------------------
# Results panel  (tabbed: Statistics / Attribute Frequency / Matching Hands /
#                          All Combinations)
# ---------------------------------------------------------------------------

class ResultsPanel(QTabWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_tabs()

    def _build_tabs(self) -> None:
        # ---- Statistics ----
        self._stats_table = QTableWidget(0, 3)
        self._stats_table.setHorizontalHeaderLabels(["Label", "Count", "%"])
        self._stats_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._stats_table.setSortingEnabled(True)
        self._stats_table.setAlternatingRowColors(True)
        self.addTab(self._stats_table, "Statistics")

        # ---- Attribute Frequency ----
        self._freq_table = QTableWidget(0, 3)
        self._freq_table.setHorizontalHeaderLabels(["Attribute", "Value", "Count"])
        self._freq_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._freq_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._freq_table.setSortingEnabled(True)
        self._freq_table.setAlternatingRowColors(True)
        self.addTab(self._freq_table, "Attribute Frequency")

        # ---- Matching Hands ----
        self._hands_text = QPlainTextEdit()
        self._hands_text.setReadOnly(True)
        self._hands_text.setFont(QFont("Courier New", 9))
        self._hands_text.setPlaceholderText(
            "Enable 'Show matching hands' in Output Options and run the analysis."
        )
        self.addTab(self._hands_text, "Matching Hands")

        # ---- All Combinations ----
        self._all_combos_widget = AllCombinationsWidget()
        self.addTab(self._all_combos_widget, "All Combinations")

    # ------------------------------------------------------------------
    # Population methods
    # ------------------------------------------------------------------

    def populate(self, stats: dict, filter_spec: Optional[FilterSpec]) -> None:
        self._populate_stats(stats, filter_spec)
        self._populate_freq(stats)
        self._populate_hands(stats)
        self._populate_all_combos(stats, filter_spec)

    def _populate_stats(
        self,
        stats:       dict,
        filter_spec: Optional[FilterSpec],
    ) -> None:
        agg_checks = stats["agg_checks"]
        agg_counts = stats["agg_counts"]
        total      = stats["total_combinations"]

        self._stats_table.setSortingEnabled(False)
        self._stats_table.setRowCount(len(agg_checks))

        for row, (label, _, is_filter) in enumerate(agg_checks):
            count = agg_counts[label]
            pct   = count / total if total else 0.0
            pct_s = f"{100 * pct:.4f}%"

            display_label = ("▶  " if is_filter else "    ") + label
            label_item    = QTableWidgetItem(display_label)
            count_item    = NumericItem(count, f"{count:,}")
            pct_item      = NumericItem(pct,   pct_s)

            for col, item in enumerate([label_item, count_item, pct_item]):
                if is_filter:
                    item.setBackground(QBrush(_highlight_color()))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter
                    | (Qt.AlignmentFlag.AlignLeft if col == 0 else Qt.AlignmentFlag.AlignRight)
                )
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._stats_table.setItem(row, col, item)

        self._stats_table.setSortingEnabled(True)

        # Show summary in the tab label
        filtered = stats["filtered_count"]
        if filter_spec:
            pct_s = f"{100 * filtered / total:.4f}%" if total else "0.0000%"
            self.setTabText(0, f"Statistics  ({filtered:,} / {total:,} = {pct_s})")
        else:
            self.setTabText(0, f"Statistics  ({total:,} total)")

    def _populate_freq(self, stats: dict) -> None:
        attr_freq  = stats["attr_freq"]
        attr_names = stats["attr_names"]

        rows_data = []
        for attr in attr_names:
            freq = attr_freq.get(attr, {})
            for value, count in sorted(freq.items(), key=lambda x: (-x[1], x[0])):
                rows_data.append((attr, value, count))

        self._freq_table.setSortingEnabled(False)
        self._freq_table.setRowCount(len(rows_data))
        for row, (attr, value, count) in enumerate(rows_data):
            self._freq_table.setItem(row, 0, QTableWidgetItem(attr))
            self._freq_table.setItem(row, 1, QTableWidgetItem(value))
            count_item = NumericItem(count, f"{count:,}")
            count_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._freq_table.setItem(row, 2, count_item)
        self._freq_table.setSortingEnabled(True)

    def _populate_hands(self, stats: dict) -> None:
        filtered_hands = stats.get("filtered_hands", [])
        label_col      = stats.get("label_col")
        verbose        = stats.get("verbose", False)

        if not verbose:
            self._hands_text.setPlainText(
                "Enable 'Show matching hands (verbose)' in Output Options and run again."
            )
            return

        MAX_DISPLAY = 1000
        total       = len(filtered_hands)
        lines       = []

        for i, hand in enumerate(filtered_hands[:MAX_DISPLAY], 1):
            hand_str = "  |  ".join(c.label(label_col) for c in hand)
            lines.append(f"{i:>6}.  {hand_str}")

        if total > MAX_DISPLAY:
            lines.append(
                f"\n… showing first {MAX_DISPLAY:,} of {total:,} matching hands."
            )
        elif total == 0:
            lines.append("No hands match the current filter.")

        self._hands_text.setPlainText("\n".join(lines))

    def _populate_all_combos(
        self,
        stats: dict,
        filter_spec: Optional[FilterSpec],
    ) -> None:
        combinations   = stats.get("combinations", [])
        filtered_hands = stats.get("filtered_hands", [])
        hand_size      = stats.get("hand_size", 0)
        label_col      = stats.get("label_col")

        if filter_spec is None:
            matched_indices: frozenset = frozenset()
        else:
            matched_indices = _build_matched_set(combinations, filtered_hands)

        self._all_combos_widget.populate(combinations, matched_indices, hand_size, label_col)
