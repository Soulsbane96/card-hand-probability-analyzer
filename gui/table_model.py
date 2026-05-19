from __future__ import annotations

from typing import Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QTableWidgetItem, QWidget


# Shared highlight colour for filter-matching rows in both the stats table
# and the all-combinations virtual view.
_HIGHLIGHT_COLOR = QColor(230, 130, 0)


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
    """Return a frozenset of indices into combinations that appear in filtered_hands.

    Uses object identity (id()) because compute_stats() stores the same tuple
    references — no copies are made.
    """
    # relies on compute_stats() (core/analysis.py) preserving tuple object identity
    id_to_idx = {id(h): i for i, h in enumerate(combinations)}
    return frozenset(
        id_to_idx[id(h)] for h in filtered_hands if id(h) in id_to_idx
    )


# ---------------------------------------------------------------------------
# Virtual table model for the all-combinations view
# ---------------------------------------------------------------------------

class CombinationsTableModel(QAbstractTableModel):
    """Virtual table model for all combinations.  Only visible rows are ever
    touched by Qt, so memory and paint cost are independent of dataset size."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._combinations: List[Tuple] = []
        self._display_indices: List[int] = []
        self._matched_indices: frozenset = frozenset()
        self._hand_size: int = 0
        self._label_col: Optional[str] = None
        self._sort_col: int = -1
        self._sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
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

        if role == Qt.ItemDataRole.DisplayRole:
            return self._combinations[orig_idx][col].label(self._label_col)

        if role == Qt.ItemDataRole.BackgroundRole:
            if orig_idx in self._matched_indices:
                return QBrush(_HIGHLIGHT_COLOR)
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
    ) -> None:
        self.beginResetModel()
        self._combinations = combinations
        self._matched_indices = matched_indices
        self._hand_size = hand_size
        self._label_col = label_col
        self._display_indices = list(range(len(combinations)))
        self._sort_col = -1
        self._sort_order = Qt.SortOrder.AscendingOrder
        self.endResetModel()

    def apply_results(self, new_indices: List[int]) -> None:
        self.beginResetModel()
        self._display_indices = new_indices
        self.endResetModel()
