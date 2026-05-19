from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Filter token widget  (one AND-condition row)
# ---------------------------------------------------------------------------

_TOKEN_TYPES: List[tuple] = [
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
        """Page 1: straight — attribute + wrap checkbox + optional wrap-count limit."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 0, 0)
        self._straight_attr = self._attr_combo()
        self._straight_wrap = QCheckBox("Wrap-around")
        self._straight_wrap.stateChanged.connect(self.changed)
        self._straight_wrap.stateChanged.connect(self._on_straight_wrap_changed)

        self._straight_limit_label = QLabel("max wrap:")
        self._straight_limit_label.setEnabled(False)
        self._straight_wrap_count = QSpinBox()
        self._straight_wrap_count.setRange(0, 20)
        self._straight_wrap_count.setValue(0)
        self._straight_wrap_count.setSpecialValueText("∞")   # ∞ for 0
        self._straight_wrap_count.setEnabled(False)
        self._straight_wrap_count.setToolTip(
            "Maximum cards from the END of the sequence that may cross the wrap boundary.\n"
            "∞ (0) = full circular wrap (e.g. both A,2,3,4,5 and Q,K,A,2,3 are valid)\n"
            "1 = only one high-end card wraps (e.g. A,2,3,4,5 valid; Q,K,A,2,3 excluded)"
        )
        self._straight_wrap_count.valueChanged.connect(self.changed)

        h.addWidget(QLabel("attribute:"))
        h.addWidget(self._straight_attr)
        h.addWidget(self._straight_wrap)
        h.addWidget(self._straight_limit_label)
        h.addWidget(self._straight_wrap_count)
        h.addStretch()
        return w

    def _on_straight_wrap_changed(self, state: int) -> None:
        enabled = bool(state)
        self._straight_limit_label.setEnabled(enabled)
        self._straight_wrap_count.setEnabled(enabled)

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

        self._not_check = QCheckBox("NOT")
        self._not_check.setToolTip("Negate this condition (exclude hands that match it)")
        self._not_check.stateChanged.connect(self.changed)
        outer.addWidget(self._not_check)

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

        token = ""
        if kind == "all":
            a = _attr(self._simple_attr)
            token = f"all:{a}" if a else ""

        elif kind == "unique":
            a = _attr(self._simple_attr)
            token = f"unique:{a}" if a else ""

        elif kind == "straight":
            a = _attr(self._straight_attr)
            if not a:
                token = ""
            elif not self._straight_wrap.isChecked():
                token = f"straight:{a}"
            else:
                n = self._straight_wrap_count.value()
                token = f"straight:{a}:wrap={n}" if n > 0 else f"straight:{a}:wrap"

        elif kind == "pattern":
            a   = _attr(self._pattern_attr)
            pat = self._pattern_edit.text().strip()
            token = f"pattern:{a}={pat}" if a and pat else ""

        elif kind == "nof":
            a  = _attr(self._nof_attr)
            op = self._nof_op.currentText()
            n  = self._nof_count.value()
            token = f"nof:{a}{op}{n}" if a else ""

        elif kind == "count":
            a   = _attr(self._count_attr)
            val = self._count_value.currentText()
            if a and val and val != "(load deck first)":
                op = self._count_op.currentText()
                n  = self._count_spin_w.value()
                token = f"{a}:{val}{op}{n}"

        if token and self._not_check.isChecked():
            token = f"not:{token}"
        return token


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
