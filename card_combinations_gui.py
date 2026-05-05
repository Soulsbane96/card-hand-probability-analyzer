"""
card_combinations_gui.py
========================
PyQt6 GUI front-end for card_combinations.py.

Run:
    python card_combinations_gui.py

Requires:
    pip install PyQt6
"""

from __future__ import annotations

import itertools
import math
import sys
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import card_combinations as cc


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
# Background worker
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
                combos, attr_names, hand_size = cc.load_combinations_csv(p["load_path"])
                self.progress.emit(
                    f"  {len(combos):,} combinations | hand size {hand_size} | "
                    f"attributes: {', '.join(attr_names)}"
                )
            else:
                if source == "csv":
                    self.progress.emit(f"Loading deck from {p['deck_path']!r} …")
                    deck, columns = cc.load_deck_from_csv(p["deck_path"], p["deck_size"])
                    self.progress.emit(
                        f"  {len(deck)} cards | attributes: {', '.join(columns)}"
                    )
                else:
                    deck, columns = cc.build_standard_deck(p["deck_size"])
                    self.progress.emit("Using built-in 52-card deck.")

                attr_names = [c.lower() for c in columns]
                hand_size  = p["hand_size"]

                total_c = math.comb(len(deck), hand_size)
                self.progress.emit(
                    f"Generating C({len(deck)}, {hand_size}) = {total_c:,} combinations …"
                )
                combos = list(itertools.combinations(deck, hand_size))

                if p.get("save_path"):
                    cc.save_combinations_csv(p["save_path"], combos, attr_names)
                    self.progress.emit(f"Saved combinations → {p['save_path']!r}")

            filter_str  = p.get("filter_str", "").strip()
            filter_spec = cc.parse_filter(filter_str)
            if filter_spec:
                filter_spec.validate_attrs(attr_names)

            self.progress.emit("Computing statistics …")
            warnings = cc.check_filter_warnings(filter_spec, hand_size) if filter_spec else []
            stats    = cc.compute_stats(combos, filter_spec, attr_names, hand_size)

            stats["warnings"]  = warnings
            stats["attr_names"] = attr_names
            stats["hand_size"] = hand_size
            stats["label_col"] = p.get("label_col")
            stats["verbose"]   = p.get("verbose", False)

            self.finished.emit(stats, filter_spec)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Filter token widget  (one AND-condition row)
# ---------------------------------------------------------------------------

_TOKEN_TYPES: List[Tuple[str, str]] = [
    ("All Same",     "all"),
    ("All Different","unique"),
    ("Straight",     "straight"),
    ("Pattern",      "pattern"),
    ("N-of-a-Kind",  "nof"),
    ("Value Count",  "count"),
]

# Map kind → stack page index
_KIND_PAGE = {
    "all": 0, "unique": 0,
    "straight": 1,
    "pattern": 2,
    "nof": 3,
    "count": 4,
}


class FilterTokenWidget(QWidget):
    changed          = pyqtSignal()
    remove_requested = pyqtSignal(object)   # emits self

    def __init__(
        self,
        attr_names:  List[str]             = (),
        attr_values: Dict[str, List[str]]  = (),
        parent:      Optional[QWidget]     = None,
    ):
        super().__init__(parent)
        self.attr_names  = list(attr_names)
        self.attr_values = dict(attr_values)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------

    def _attr_combo(self) -> QComboBox:
        cb = QComboBox()
        if self.attr_names:
            cb.addItems(self.attr_names)
        else:
            cb.addItem("(load deck first)")
        cb.currentIndexChanged.connect(self.changed)
        return cb

    def _op_combo(self) -> QComboBox:
        cb = QComboBox()
        cb.addItems(["=", ">=", "<="])
        cb.currentIndexChanged.connect(self.changed)
        return cb

    def _count_spin(self) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(1, 99)
        sp.setValue(1)
        sp.valueChanged.connect(self.changed)
        return sp

    # ------------------------------------------------------------------
    # Stack pages
    # ------------------------------------------------------------------

    def _make_simple_page(self) -> QWidget:
        """Page 0: all / unique — attribute selector only."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 0, 0)
        self._simple_attr = self._attr_combo()
        h.addWidget(QLabel("attribute:"))
        h.addWidget(self._simple_attr)
        h.addStretch()
        return w

    def _make_straight_page(self) -> QWidget:
        """Page 1: straight — attribute + wrap checkbox."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 0, 0)
        self._straight_attr = self._attr_combo()
        self._straight_wrap = QCheckBox("Wrap-around")
        self._straight_wrap.stateChanged.connect(self.changed)
        h.addWidget(QLabel("attribute:"))
        h.addWidget(self._straight_attr)
        h.addWidget(self._straight_wrap)
        h.addStretch()
        return w

    def _make_pattern_page(self) -> QWidget:
        """Page 2: pattern — attribute + free-form pattern string."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 0, 0)
        v.setSpacing(2)

        row = QHBoxLayout()
        self._pattern_attr = self._attr_combo()
        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText("e.g. 3+2  or  2+2+1")
        self._pattern_edit.setMaximumWidth(120)
        self._pattern_edit.textChanged.connect(self.changed)
        row.addWidget(QLabel("attribute:"))
        row.addWidget(self._pattern_attr)
        row.addWidget(QLabel("pattern:"))
        row.addWidget(self._pattern_edit)
        row.addStretch()
        v.addLayout(row)

        hint = QLabel("Numbers must sum to hand size (e.g. 3+2 for a 5-card hand)")
        hint.setStyleSheet("color: gray; font-size: 10px;")
        v.addWidget(hint)
        return w

    def _make_nof_page(self) -> QWidget:
        """Page 3: nof — attribute + operator + count."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 0, 0)
        self._nof_attr  = self._attr_combo()
        self._nof_op    = self._op_combo()
        self._nof_count = self._count_spin()
        h.addWidget(QLabel("attribute:"))
        h.addWidget(self._nof_attr)
        h.addWidget(QLabel("one value appears"))
        h.addWidget(self._nof_op)
        h.addWidget(self._nof_count)
        h.addWidget(QLabel("times"))
        h.addStretch()
        return w

    def _make_count_page(self) -> QWidget:
        """Page 4: count — attribute + specific value + operator + count."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 0, 0)
        self._count_attr  = self._attr_combo()
        self._count_value = QComboBox()
        if not self.attr_names:
            self._count_value.addItem("(load deck first)")
        self._count_value.currentIndexChanged.connect(self.changed)
        self._count_op   = self._op_combo()
        self._count_spin_w = self._count_spin()

        h.addWidget(QLabel("attribute:"))
        h.addWidget(self._count_attr)
        h.addWidget(QLabel("value:"))
        h.addWidget(self._count_value)
        h.addWidget(QLabel("count"))
        h.addWidget(self._count_op)
        h.addWidget(self._count_spin_w)
        h.addStretch()

        self._count_attr.currentIndexChanged.connect(self._refresh_value_combo)
        return w

    # ------------------------------------------------------------------
    # Build full widget
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(4)

        self._type_combo = QComboBox()
        self._type_combo.setMinimumWidth(120)
        for label, kind in _TOKEN_TYPES:
            self._type_combo.addItem(label, kind)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        outer.addWidget(self._type_combo)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._make_simple_page())    # 0
        self._stack.addWidget(self._make_straight_page())  # 1
        self._stack.addWidget(self._make_pattern_page())   # 2
        self._stack.addWidget(self._make_nof_page())       # 3
        self._stack.addWidget(self._make_count_page())     # 4
        outer.addWidget(self._stack, 1)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove this condition")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        outer.addWidget(remove_btn)

        self._on_type_changed(0)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_type_changed(self, idx: int) -> None:
        kind = _TOKEN_TYPES[idx][1]
        self._stack.setCurrentIndex(_KIND_PAGE.get(kind, 0))
        self.changed.emit()

    def _refresh_value_combo(self) -> None:
        attr   = self._count_attr.currentText()
        values = self.attr_values.get(attr, [])
        self._count_value.blockSignals(True)
        self._count_value.clear()
        if values:
            self._count_value.addItems(values)
        else:
            self._count_value.addItem("(load deck first)")
        self._count_value.blockSignals(False)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_attrs(
        self,
        attr_names:  List[str],
        attr_values: Dict[str, List[str]],
    ) -> None:
        self.attr_names  = attr_names
        self.attr_values = attr_values
        for combo in (
            self._simple_attr,
            self._straight_attr,
            self._pattern_attr,
            self._nof_attr,
            self._count_attr,
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(attr_names)
            combo.blockSignals(False)
        self._refresh_value_combo()
        self.changed.emit()

    def to_token_str(self) -> str:
        """Return the DSL token string for this condition, or '' if incomplete."""
        idx  = self._type_combo.currentIndex()
        kind = _TOKEN_TYPES[idx][1]

        def _attr(combo: QComboBox) -> str:
            t = combo.currentText()
            return "" if t in ("", "(load deck first)") else t

        if kind == "all":
            a = _attr(self._simple_attr)
            return f"all:{a}" if a else ""

        if kind == "unique":
            a = _attr(self._simple_attr)
            return f"unique:{a}" if a else ""

        if kind == "straight":
            a    = _attr(self._straight_attr)
            wrap = ":wrap" if self._straight_wrap.isChecked() else ""
            return f"straight:{a}{wrap}" if a else ""

        if kind == "pattern":
            a   = _attr(self._pattern_attr)
            pat = self._pattern_edit.text().strip()
            return f"pattern:{a}={pat}" if a and pat else ""

        if kind == "nof":
            a  = _attr(self._nof_attr)
            op = self._nof_op.currentText()
            n  = self._nof_count.value()
            return f"nof:{a}{op}{n}" if a else ""

        if kind == "count":
            a   = _attr(self._count_attr)
            val = self._count_value.currentText()
            if not a or not val or val == "(load deck first)":
                return ""
            op = self._count_op.currentText()
            n  = self._count_spin_w.value()
            return f"{a}:{val}{op}{n}"

        return ""


# ---------------------------------------------------------------------------
# Filter clause widget  (one OR-group of AND-tokens)
# ---------------------------------------------------------------------------

class FilterClauseWidget(QGroupBox):
    changed          = pyqtSignal()
    remove_requested = pyqtSignal(object)   # emits self

    def __init__(
        self,
        clause_num:  int,
        attr_names:  List[str]            = (),
        attr_values: Dict[str, List[str]] = (),
        parent:      Optional[QWidget]    = None,
    ):
        super().__init__(f"Clause {clause_num}  (OR)", parent)
        self.attr_names  = list(attr_names)
        self.attr_values = dict(attr_values)
        self._tokens: List[FilterTokenWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self._outer = QVBoxLayout(self)
        self._outer.setSpacing(4)

        # Header: remove button
        hdr = QHBoxLayout()
        hdr.addStretch()
        remove_btn = QPushButton("✕ Remove Clause")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        hdr.addWidget(remove_btn)
        self._outer.addLayout(hdr)

        # Token rows
        self._token_layout = QVBoxLayout()
        self._token_layout.setSpacing(2)
        self._outer.addLayout(self._token_layout)

        # Add condition button
        add_btn = QPushButton("+ Add Condition (AND)")
        add_btn.clicked.connect(self._add_token)
        self._outer.addWidget(add_btn)

        self._add_token()   # start with one token

    def _add_token(self) -> None:
        token = FilterTokenWidget(self.attr_names, self.attr_values, self)
        token.changed.connect(self.changed)
        token.remove_requested.connect(self._remove_token)
        self._tokens.append(token)
        self._token_layout.addWidget(token)
        self.changed.emit()

    def _remove_token(self, token: FilterTokenWidget) -> None:
        if len(self._tokens) <= 1:
            return
        self._tokens.remove(token)
        self._token_layout.removeWidget(token)
        token.deleteLater()
        self.changed.emit()

    def update_attrs(
        self,
        attr_names:  List[str],
        attr_values: Dict[str, List[str]],
    ) -> None:
        self.attr_names  = attr_names
        self.attr_values = attr_values
        for token in self._tokens:
            token.update_attrs(attr_names, attr_values)

    def to_clause_str(self) -> str:
        parts = [t.to_token_str() for t in self._tokens]
        return ",".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Filter builder widget  (manages OR-clauses + generated string display)
# ---------------------------------------------------------------------------

class FilterBuilderWidget(QWidget):
    filter_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._clauses:    List[FilterClauseWidget] = []
        self._attr_names: List[str]                = []
        self._attr_values: Dict[str, List[str]]    = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Scrollable clause area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(160)

        self._clause_container = QWidget()
        self._clause_layout    = QVBoxLayout(self._clause_container)
        self._clause_layout.setSpacing(8)
        self._clause_layout.addStretch()
        scroll.setWidget(self._clause_container)
        layout.addWidget(scroll)

        add_btn = QPushButton("+ Add Clause (OR)")
        add_btn.clicked.connect(self._add_clause)
        layout.addWidget(add_btn)

        # Generated filter string (read-only reference)
        row = QHBoxLayout()
        row.addWidget(QLabel("Filter string:"))
        self._filter_display = QLineEdit()
        self._filter_display.setReadOnly(True)
        self._filter_display.setPlaceholderText("(add conditions above to build a filter)")
        self._filter_display.setFont(QFont("Courier New", 9))
        row.addWidget(self._filter_display, 1)
        layout.addLayout(row)

    def _add_clause(self) -> None:
        num    = len(self._clauses) + 1
        clause = FilterClauseWidget(num, self._attr_names, self._attr_values, self)
        clause.changed.connect(self._refresh)
        clause.remove_requested.connect(self._remove_clause)
        self._clauses.append(clause)
        # Insert before the trailing stretch
        self._clause_layout.insertWidget(self._clause_layout.count() - 1, clause)
        self._refresh()

    def _remove_clause(self, clause: FilterClauseWidget) -> None:
        self._clauses.remove(clause)
        self._clause_layout.removeWidget(clause)
        clause.deleteLater()
        self._renumber()
        self._refresh()

    def _renumber(self) -> None:
        for i, clause in enumerate(self._clauses):
            clause.setTitle(f"Clause {i + 1}  (OR)")

    def _refresh(self) -> None:
        parts      = [c.to_clause_str() for c in self._clauses]
        filter_str = ";".join(p for p in parts if p)
        self._filter_display.setText(filter_str)
        self.filter_changed.emit(filter_str)

    # Public API

    def update_attrs(
        self,
        attr_names:  List[str],
        attr_values: Dict[str, List[str]],
    ) -> None:
        self._attr_names  = attr_names
        self._attr_values = attr_values
        for clause in self._clauses:
            clause.update_attrs(attr_names, attr_values)

    def get_filter_str(self) -> str:
        return self._filter_display.text()

    def clear_clauses(self) -> None:
        for clause in list(self._clauses):
            self._clause_layout.removeWidget(clause)
            clause.deleteLater()
        self._clauses.clear()
        self._filter_display.clear()


# ---------------------------------------------------------------------------
# Deck preview window
# ---------------------------------------------------------------------------

class DeckPreviewWindow(QWidget):
    """Stand-alone window: sortable table of cards with per-column filters."""

    def __init__(
        self,
        rows:       List[Dict[str, str]],
        attr_names: List[str],
        title:      str                = "Deck Preview",
        parent:     Optional[QWidget] = None,
    ):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(title)
        self.setMinimumSize(660, 500)
        self._rows       = rows
        self._attr_names = attr_names
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Per-column filter inputs
        filter_box = QGroupBox("Column Filters")
        filter_row = QHBoxLayout(filter_box)
        self._filter_edits: Dict[str, QLineEdit] = {}
        for attr in self._attr_names:
            col_wrap = QVBoxLayout()
            col_wrap.setSpacing(2)
            col_wrap.addWidget(QLabel(attr.capitalize() + ":"))
            le = QLineEdit()
            le.setPlaceholderText("filter…")
            le.setClearButtonEnabled(True)
            le.textChanged.connect(self._apply_filters)
            self._filter_edits[attr] = le
            col_wrap.addWidget(le)
            filter_row.addLayout(col_wrap)
        layout.addWidget(filter_box)

        self._count_label = QLabel()
        layout.addWidget(self._count_label)

        # Card table
        self._table = QTableWidget(0, len(self._attr_names))
        self._table.setHorizontalHeaderLabels(
            [a.capitalize() for a in self._attr_names]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        self._fill_table()

    def _fill_table(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, attr in enumerate(self._attr_names):
                item = QTableWidgetItem(row.get(attr, ""))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(r, c, item)
        self._table.setSortingEnabled(True)
        self._count_label.setText(f"{len(self._rows):,} cards")

    def _apply_filters(self) -> None:
        active = {
            attr: le.text().strip().lower()
            for attr, le in self._filter_edits.items()
            if le.text().strip()
        }
        visible = 0
        for r in range(self._table.rowCount()):
            show = True
            for attr, ftext in active.items():
                col  = self._attr_names.index(attr)
                item = self._table.item(r, col)
                if item is None or ftext not in item.text().lower():
                    show = False
                    break
            self._table.setRowHidden(r, not show)
            if show:
                visible += 1
        total = self._table.rowCount()
        if visible == total:
            self._count_label.setText(f"{total:,} cards")
        else:
            self._count_label.setText(f"{visible:,} of {total:,} cards shown")


# ---------------------------------------------------------------------------
# Deck configuration widget
# ---------------------------------------------------------------------------

class DeckConfigWidget(QGroupBox):
    deck_loaded    = pyqtSignal(list, dict)   # attr_names, {attr: [values]}
    status_message = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Deck Configuration", parent)
        self._loaded_rows:       List[Dict[str, str]] = []
        self._loaded_attr_names: List[str]            = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Source radio buttons
        self._btn_group = QButtonGroup(self)
        self._radio_std    = QRadioButton("Standard 52-card deck")
        self._radio_csv    = QRadioButton("Custom CSV deck")
        self._radio_combos = QRadioButton("Load saved combinations CSV")
        self._radio_std.setChecked(True)
        for i, r in enumerate([self._radio_std, self._radio_csv, self._radio_combos]):
            self._btn_group.addButton(r, i)
            layout.addWidget(r)
        self._btn_group.idClicked.connect(self._on_source_changed)

        # File picker
        file_row = QHBoxLayout()
        self._file_label = QLabel("File:")
        self._file_edit  = QLineEdit()
        self._file_edit.setPlaceholderText("Select a CSV file…")
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self._file_label)
        file_row.addWidget(self._file_edit, 1)
        file_row.addWidget(self._browse_btn)
        layout.addLayout(file_row)

        # Sizes
        sizes_row = QHBoxLayout()
        sizes_row.addWidget(QLabel("Hand size:"))
        self._hand_spin = QSpinBox()
        self._hand_spin.setRange(1, 20)
        self._hand_spin.setValue(5)
        sizes_row.addWidget(self._hand_spin)
        sizes_row.addSpacing(20)
        sizes_row.addWidget(QLabel("Deck size (0 = full deck):"))
        self._deck_spin = QSpinBox()
        self._deck_spin.setRange(0, 9999)
        self._deck_spin.setValue(0)
        sizes_row.addWidget(self._deck_spin)
        sizes_row.addStretch()
        layout.addLayout(sizes_row)

        # Deck action buttons
        btn_row = QHBoxLayout()
        self._load_btn = QPushButton("Load Deck")
        self._load_btn.setToolTip("Load the deck's attributes into the Filter Builder and Output Options")
        self._load_btn.clicked.connect(self._load_deck)
        self._preview_btn = QPushButton("Preview Deck…")
        self._preview_btn.setToolTip("Open a sortable, filterable table of the loaded cards")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._open_preview)
        btn_row.addWidget(self._load_btn)
        btn_row.addWidget(self._preview_btn)
        layout.addLayout(btn_row)

        self._on_source_changed(0)

    def _on_source_changed(self, btn_id: int) -> None:
        is_file   = btn_id in (1, 2)
        is_combos = btn_id == 2
        for w in (self._file_label, self._file_edit, self._browse_btn):
            w.setEnabled(is_file)
        self._hand_spin.setEnabled(not is_combos)
        self._deck_spin.setEnabled(not is_combos)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            self._file_edit.setText(path)

    def _load_deck(self) -> None:
        source    = self._source()
        deck_size = self._deck_spin.value() or None

        try:
            if source == "standard":
                deck, columns = cc.build_standard_deck(deck_size)
                attr_names    = [c.lower() for c in columns]
                attr_values   = self._values_from_deck(deck, attr_names)
                self._loaded_rows       = [card.attributes for card in deck]
                self._loaded_attr_names = attr_names
                self.status_message.emit(
                    f"Standard deck: {len(deck)} cards | Attributes: {', '.join(attr_names)}"
                )
                self.deck_loaded.emit(attr_names, attr_values)

            elif source == "csv":
                path = self._file_edit.text().strip()
                if not path:
                    QMessageBox.warning(self, "No File", "Please select a CSV deck file first.")
                    return
                deck, columns = cc.load_deck_from_csv(path, deck_size)
                attr_names    = [c.lower() for c in columns]
                attr_values   = self._values_from_deck(deck, attr_names)
                self._loaded_rows       = [card.attributes for card in deck]
                self._loaded_attr_names = attr_names
                self.status_message.emit(
                    f"Loaded {len(deck)} cards | Attributes: {', '.join(attr_names)}"
                )
                self.deck_loaded.emit(attr_names, attr_values)

            else:  # load_combos
                path = self._file_edit.text().strip()
                if not path:
                    QMessageBox.warning(self, "No File", "Please select a combinations CSV file first.")
                    return
                combos, attr_names, hand_size = cc.load_combinations_csv(path)
                attr_values  = self._values_from_combos(combos, attr_names)
                seen: set    = set()
                unique_cards = []
                for combo in combos:
                    for card in combo:
                        if card not in seen:
                            unique_cards.append(card)
                            seen.add(card)
                self._loaded_rows       = [card.attributes for card in unique_cards]
                self._loaded_attr_names = attr_names
                self.status_message.emit(
                    f"Loaded {len(combos):,} combinations | hand size {hand_size} | "
                    f"attributes: {', '.join(attr_names)}"
                )
                self.deck_loaded.emit(attr_names, attr_values)

            self._preview_btn.setEnabled(True)

        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Deck", str(exc))

    def _open_preview(self) -> None:
        n     = len(self._loaded_rows)
        title = (
            f"Deck Preview — {n:,} card{'s' if n != 1 else ''} | "
            f"attributes: {', '.join(self._loaded_attr_names)}"
        )
        win = DeckPreviewWindow(
            self._loaded_rows, self._loaded_attr_names, title,
            parent=self.window(),
        )
        win.show()
        win.raise_()

    @staticmethod
    def _values_from_deck(
        deck:       List[cc.Card],
        attr_names: List[str],
    ) -> Dict[str, List[str]]:
        result = {}
        for attr in attr_names:
            order = cc.get_sequence_order(attr)
            if order:
                result[attr] = list(order)
            else:
                seen:     List[str] = []
                seen_set: set       = set()
                for card in deck:
                    v = card.attr(attr)
                    if v not in seen_set:
                        seen.append(v)
                        seen_set.add(v)
                result[attr] = seen
        return result

    @staticmethod
    def _values_from_combos(
        combos:     List[Tuple[cc.Card, ...]],
        attr_names: List[str],
    ) -> Dict[str, List[str]]:
        result = {}
        for attr in attr_names:
            seen:     List[str] = []
            seen_set: set       = set()
            for hand in combos:
                for card in hand:
                    v = card.attr(attr)
                    if v not in seen_set:
                        seen.append(v)
                        seen_set.add(v)
            result[attr] = seen
        return result

    def _source(self) -> str:
        if self._radio_std.isChecked():
            return "standard"
        if self._radio_csv.isChecked():
            return "csv"
        return "load_combos"

    def get_params(self) -> dict:
        source = self._source()
        return {
            "source":    source,
            "deck_path": self._file_edit.text().strip() if source == "csv" else None,
            "load_path": self._file_edit.text().strip() if source == "load_combos" else None,
            "hand_size": self._hand_spin.value(),
            "deck_size": self._deck_spin.value() or None,
        }


# ---------------------------------------------------------------------------
# Output options widget
# ---------------------------------------------------------------------------

class OptionsWidget(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Output Options", parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._verbose_check = QCheckBox("Show matching hands in the Matching Hands tab")
        layout.addWidget(self._verbose_check)

        # Save combos row
        save_row = QHBoxLayout()
        self._save_check = QCheckBox("Save combinations to:")
        self._save_edit  = QLineEdit()
        self._save_edit.setEnabled(False)
        self._save_btn   = QPushButton("Browse…")
        self._save_btn.setEnabled(False)
        self._save_check.stateChanged.connect(self._toggle_save)
        self._save_btn.clicked.connect(self._browse_save)
        save_row.addWidget(self._save_check)
        save_row.addWidget(self._save_edit, 1)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        # Label column
        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Card label column:"))
        self._label_combo = QComboBox()
        self._label_combo.addItem("— default —")
        label_row.addWidget(self._label_combo)
        label_row.addStretch()
        layout.addLayout(label_row)

    def _toggle_save(self, state: int) -> None:
        enabled = bool(state)
        self._save_edit.setEnabled(enabled)
        self._save_btn.setEnabled(enabled)

    def _browse_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Combinations CSV", "", "CSV Files (*.csv)"
        )
        if path:
            self._save_edit.setText(path)

    def update_attrs(self, attr_names: List[str], _attr_values: dict) -> None:
        self._label_combo.blockSignals(True)
        self._label_combo.clear()
        self._label_combo.addItem("— default —")
        self._label_combo.addItems(attr_names)
        self._label_combo.blockSignals(False)

    def get_params(self) -> dict:
        label = self._label_combo.currentText()
        return {
            "verbose":   self._verbose_check.isChecked(),
            "save_path": self._save_edit.text().strip() if self._save_check.isChecked() else None,
            "label_col": None if label == "— default —" else label,
        }


# ---------------------------------------------------------------------------
# Results panel  (tabbed: Statistics / Attribute Frequency / Matching Hands)
# ---------------------------------------------------------------------------

_HIGHLIGHT_COLOR = QColor(173, 216, 230)   # light blue for filter rows


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

    # ------------------------------------------------------------------
    # Population methods
    # ------------------------------------------------------------------

    def populate(self, stats: dict, filter_spec: Optional[cc.FilterSpec]) -> None:
        self._populate_stats(stats, filter_spec)
        self._populate_freq(stats)
        self._populate_hands(stats)

    def _populate_stats(
        self,
        stats:       dict,
        filter_spec: Optional[cc.FilterSpec],
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
                    item.setBackground(QBrush(_HIGHLIGHT_COLOR))
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


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Card Combination Analyzer")
        self.setMinimumSize(950, 720)
        self._worker: Optional[AnalysisWorker] = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ---- Config panel (top half) ----
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setSpacing(8)

        self._deck_config = DeckConfigWidget()
        self._deck_config.deck_loaded.connect(self._on_deck_loaded)
        self._deck_config.status_message.connect(self.statusBar().showMessage)
        config_layout.addWidget(self._deck_config)

        filter_group = QGroupBox("Filter Builder")
        fg_layout    = QVBoxLayout(filter_group)
        fg_layout.setContentsMargins(6, 6, 6, 6)
        self._filter_builder = FilterBuilderWidget()
        fg_layout.addWidget(self._filter_builder)
        config_layout.addWidget(filter_group)

        self._options = OptionsWidget()
        config_layout.addWidget(self._options)

        # Run row
        run_row = QHBoxLayout()
        self._run_btn   = QPushButton("Run Analysis")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run_analysis)
        self._progress_bar   = QProgressBar()
        self._progress_bar.setRange(0, 0)          # indeterminate spinner
        self._progress_bar.setVisible(False)
        self._progress_label = QLabel("")
        run_row.addWidget(self._run_btn)
        run_row.addWidget(self._progress_bar, 1)
        run_row.addWidget(self._progress_label)
        config_layout.addLayout(run_row)

        splitter.addWidget(config_widget)

        # ---- Results panel (bottom half) ----
        self._results = ResultsPanel()
        splitter.addWidget(self._results)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)
        self.statusBar().showMessage("Ready  —  load a deck to begin.")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_deck_loaded(
        self,
        attr_names:  List[str],
        attr_values: Dict[str, List[str]],
    ) -> None:
        self._filter_builder.update_attrs(attr_names, attr_values)
        self._options.update_attrs(attr_names, attr_values)

    def _run_analysis(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        deck_params    = self._deck_config.get_params()
        options_params = self._options.get_params()
        filter_str     = self._filter_builder.get_filter_str()

        # Validate file paths before kicking off worker
        if deck_params["source"] == "csv" and not deck_params["deck_path"]:
            QMessageBox.warning(self, "No Deck File", "Please select a CSV deck file.")
            return
        if deck_params["source"] == "load_combos" and not deck_params["load_path"]:
            QMessageBox.warning(self, "No Combos File", "Please select a combinations CSV file.")
            return

        params = {**deck_params, **options_params, "filter_str": filter_str}

        self._run_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_label.setText("Starting …")

        self._worker = AnalysisWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str) -> None:
        self._progress_label.setText(msg)
        self.statusBar().showMessage(msg)

    def _on_finished(self, stats: dict, filter_spec: Optional[cc.FilterSpec]) -> None:
        self._progress_bar.setVisible(False)
        self._progress_label.setText("")
        self._run_btn.setEnabled(True)

        warnings = stats.get("warnings", [])
        if warnings:
            QMessageBox.warning(self, "Filter Warnings", "\n".join(warnings))

        self._results.populate(stats, filter_spec)
        self._results.setCurrentIndex(0)

        total    = stats["total_combinations"]
        filtered = stats["filtered_count"]
        if filter_spec:
            pct = f"{100 * filtered / total:.4f}%" if total else "0.0000%"
            self.statusBar().showMessage(
                f"Done  —  {filtered:,} matching hands / {total:,} total ({pct})"
            )
        else:
            self.statusBar().showMessage(f"Done  —  {total:,} total combinations")

    def _on_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._progress_label.setText("")
        self._run_btn.setEnabled(True)
        QMessageBox.critical(self, "Analysis Error", msg)
        self.statusBar().showMessage("Error — see dialog for details.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
