from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QTableWidgetItem, QWidget

from gui.settings import load_theme
from gui.themes import HIGHLIGHT_COLORS


def _highlight_color() -> QColor:
    return QColor(HIGHLIGHT_COLORS[load_theme()])


# ---------------------------------------------------------------------------
# Numeric-sortable table item
# ---------------------------------------------------------------------------

class NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by a numeric value instead of display text."""

    def __init__(self, value: float, display: str):
        super().__init__(display)
        self._value = value

    def __lt__(self, other: "NumericItem") -> bool:
        if isinstance(other, NumericItem):
            return self._value < other._value
        return super().__lt__(other)


# ---------------------------------------------------------------------------
# Helper: map filtered hands back to indices in the full combinations list
# ---------------------------------------------------------------------------

def _build_matched_set(
    combinations: List[Tuple],
    filtered_hands: List[Tuple],
) -> frozenset:
    """Return a frozenset of indices into combinations that appear in filtered_hands."""
    id_to_idx = {id(h): i for i, h in enumerate(combinations)}
    return frozenset(
        id_to_idx[id(h)] for h in filtered_hands if id(h) in id_to_idx
    )


# ---------------------------------------------------------------------------
# Virtual table model for the all-combinations view
# ---------------------------------------------------------------------------

class CombinationsTableModel(QAbstractTableModel):
    """Virtual table model for all combinations.

    Supports two modes:
    - List mode  (db_conn is None): _combinations holds all Card tuples in RAM.
    - DB mode    (db_conn is set):  rows are fetched from SQLite in pages.
    """

    _PAGE_SIZE = 500

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._combinations: List[Tuple]  = []
        self._display_indices: List[int] = []
        self._matched_indices: frozenset = frozenset()
        self._hand_size: int             = 0
        self._label_col: Optional[str]   = None
        self._sort_col: int              = -1
        self._sort_order: Qt.SortOrder   = Qt.SortOrder.AscendingOrder

        # DB mode state
        self._db_conn: Optional[sqlite3.Connection] = None
        self._db_attr_names: List[str]              = []
        self._db_row_count: int                     = 0
        # page cache: maps page_start_row -> List[Tuple[Card,...]]
        self._page_cache: Dict[int, List[Tuple]]    = {}

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self._db_conn is not None:
            return len(self._display_indices)
        return len(self._display_indices)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._hand_size

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row >= len(self._display_indices) or col >= self._hand_size:
            return None

        orig_idx = self._display_indices[row]

        if self._db_conn is not None:
            if role == Qt.ItemDataRole.DisplayRole:
                card = self._get_db_card(orig_idx, col)
                return card.label(self._label_col) if card else None
            if role == Qt.ItemDataRole.BackgroundRole:
                return None   # no per-row highlighting in DB mode
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None

        # List mode
        if role == Qt.ItemDataRole.DisplayRole:
            return self._combinations[orig_idx][col].label(self._label_col)
        if role == Qt.ItemDataRole.BackgroundRole:
            if orig_idx in self._matched_indices:
                return QBrush(_highlight_color())
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return f"Card {section + 1}"
        return str(section + 1)

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------

    def update_data(
        self,
        combinations: List[Tuple],
        matched_indices: frozenset,
        hand_size: int,
        label_col: Optional[str],
        db_conn: Optional[sqlite3.Connection] = None,
        db_attr_names: Optional[List[str]] = None,
    ) -> None:
        self.beginResetModel()
        self._db_conn        = db_conn
        self._db_attr_names  = db_attr_names or []
        self._page_cache     = {}

        if db_conn is not None:
            from core.db import count_filtered_hands
            self._db_row_count    = count_filtered_hands(db_conn)
            self._combinations    = []
            self._matched_indices = frozenset()
            self._display_indices = list(range(self._db_row_count))
        else:
            self._combinations    = combinations
            self._matched_indices = matched_indices
            self._display_indices = list(range(len(combinations)))
            self._db_row_count    = 0

        self._hand_size  = hand_size
        self._label_col  = label_col
        self._sort_col   = -1
        self._sort_order = Qt.SortOrder.AscendingOrder
        self.endResetModel()

    def apply_results(self, new_indices: List[int]) -> None:
        self.beginResetModel()
        self._display_indices = new_indices
        self._page_cache      = {}   # invalidate page cache on new sort/filter
        self.endResetModel()

    # ------------------------------------------------------------------
    # DB page-fetch helper
    # ------------------------------------------------------------------

    def _get_db_card(self, row_idx: int, col: int):
        """Return Card at (row_idx, col) from DB, fetching a page if needed."""
        page_start = (row_idx // self._PAGE_SIZE) * self._PAGE_SIZE
        if page_start not in self._page_cache:
            self._load_db_page(page_start)
        page = self._page_cache.get(page_start)
        if page is None:
            return None
        local = row_idx - page_start
        if local >= len(page):
            return None
        hand = page[local]
        if col >= len(hand):
            return None
        return hand[col]

    def _load_db_page(self, page_start: int) -> None:
        from core.db import query_hand_page
        hands = query_hand_page(
            self._db_conn, page_start, self._PAGE_SIZE, self._db_attr_names
        )
        self._page_cache[page_start] = hands
        # Keep cache bounded to ~20 pages
        if len(self._page_cache) > 20:
            oldest = next(iter(self._page_cache))
            del self._page_cache[oldest]
