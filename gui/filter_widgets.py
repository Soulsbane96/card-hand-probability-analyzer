from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import pyqtSignal, Qt
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
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


_TOKEN_TYPES: List[tuple] = [
    ("All Same",     "all"),
    ("All Different","unique"),
    ("Straight",     "straight"),
    ("Pattern",      "pattern"),
    ("N-of-a-Kind",  "nof"),
    ("Value Count",  "count"),
]

# Map kind → stack page index (0 = no extra params needed)
_KIND_PAGE = {
    "all": 0, "unique": 0,
    "straight": 1,
    "pattern": 2,
    "nof": 3,
    "count": 4,
}


# ---------------------------------------------------------------------------
# Filter token widget  (one AND-condition)
# Row 1: NOT | type | attr | ✕
# Row 2: type-specific extra controls (hidden for all/unique)
# ---------------------------------------------------------------------------

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
    # Small widget helpers
    # ------------------------------------------------------------------

    def _op_combo(self) -> QComboBox:
        cb = QComboBox()
        cb.addItems(["=", ">=", "<="])
        cb.setFixedWidth(52)
        cb.currentIndexChanged.connect(self.changed)
        return cb

    def _count_spin(self) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(1, 99)
        sp.setValue(1)
        sp.setFixedWidth(52)
        sp.valueChanged.connect(self.changed)
        return sp

    # ------------------------------------------------------------------
    # Stack pages — extra params only, attr is in row 1
    # ------------------------------------------------------------------

    def _make_straight_page(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._straight_wrap = QCheckBox("Wrap")
        self._straight_wrap.stateChanged.connect(self.changed)
        self._straight_wrap.stateChanged.connect(self._on_straight_wrap_changed)

        self._straight_limit_label = QLabel("limit:")
        self._straight_limit_label.setEnabled(False)
        self._straight_wrap_count = QSpinBox()
        self._straight_wrap_count.setRange(0, 20)
        self._straight_wrap_count.setValue(0)
        self._straight_wrap_count.setSpecialValueText("∞")
        self._straight_wrap_count.setFixedWidth(52)
        self._straight_wrap_count.setEnabled(False)
        self._straight_wrap_count.setToolTip(
            "Maximum cards from the END of the sequence that may cross the wrap boundary.\n"
            "∞ (0) = full circular wrap (e.g. both A,2,3,4,5 and Q,K,A,2,3 are valid)\n"
            "1 = only one high-end card wraps (e.g. A,2,3,4,5 valid; Q,K,A,2,3 excluded)"
        )
        self._straight_wrap_count.valueChanged.connect(self.changed)

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
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._pattern_edit = QLineEdit()
        self._pattern_edit.setPlaceholderText("e.g. 3+2")
        self._pattern_edit.setMaximumWidth(90)
        self._pattern_edit.textChanged.connect(self.changed)
        row.addWidget(QLabel("pat:"))
        row.addWidget(self._pattern_edit)
        row.addStretch()
        v.addLayout(row)

        hint = QLabel("Numbers must sum to hand size")
        hint.setObjectName("hintLabel")
        v.addWidget(hint)
        return w

    def _make_nof_page(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._nof_op    = self._op_combo()
        self._nof_count = self._count_spin()
        h.addWidget(QLabel("has"))
        h.addWidget(self._nof_op)
        h.addWidget(self._nof_count)
        h.addWidget(QLabel("same"))
        h.addStretch()
        return w

    def _make_count_page(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._count_value = QComboBox()
        if not self.attr_names:
            self._count_value.addItem("(load deck first)")
        self._count_value.currentIndexChanged.connect(self.changed)
        self._count_op     = self._op_combo()
        self._count_spin_w = self._count_spin()

        h.addWidget(self._count_value)
        h.addWidget(self._count_op)
        h.addWidget(self._count_spin_w)
        h.addStretch()
        return w

    # ------------------------------------------------------------------
    # Build full widget
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 1, 0, 1)
        outer.setSpacing(2)

        # Build stack pages first so _count_value exists before _attr_select signals fire
        self._stack = QStackedWidget()
        self._stack.addWidget(QWidget())                   # 0: all/unique — no extras
        self._stack.addWidget(self._make_straight_page())  # 1
        self._stack.addWidget(self._make_pattern_page())   # 2
        self._stack.addWidget(self._make_nof_page())       # 3
        self._stack.addWidget(self._make_count_page())     # 4

        # Row 1: NOT | type | attr | ✕
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self._not_check = QCheckBox("NOT")
        self._not_check.setToolTip("Negate this condition (exclude hands that match it)")
        self._not_check.stateChanged.connect(self.changed)
        top_row.addWidget(self._not_check)

        self._type_combo = QComboBox()
        for label, kind in _TOKEN_TYPES:
            self._type_combo.addItem(label, kind)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        top_row.addWidget(self._type_combo)

        self._attr_select = QComboBox()
        if self.attr_names:
            self._attr_select.addItems(self.attr_names)
        else:
            self._attr_select.addItem("(load deck first)")
        self._attr_select.currentIndexChanged.connect(self.changed)
        self._attr_select.currentIndexChanged.connect(self._refresh_value_combo)
        top_row.addWidget(self._attr_select)
        top_row.addStretch(1)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove this condition")
        remove_btn.setProperty("danger", True)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        top_row.addWidget(remove_btn)
        outer.addLayout(top_row)

        # Row 2: extra parameters (hidden for all/unique)
        outer.addWidget(self._stack)

        self._on_type_changed(0)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_type_changed(self, idx: int) -> None:
        kind = _TOKEN_TYPES[idx][1]
        page = _KIND_PAGE.get(kind, 0)
        self._stack.setCurrentIndex(page)
        self._stack.setVisible(page != 0)
        self.changed.emit()

    def _refresh_value_combo(self) -> None:
        attr   = self._attr_select.currentText()
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
        self._attr_select.blockSignals(True)
        self._attr_select.clear()
        self._attr_select.addItems(attr_names)
        self._attr_select.blockSignals(False)
        self._refresh_value_combo()
        self.changed.emit()

    def to_token_str(self) -> str:
        """Return the DSL token string for this condition, or '' if incomplete."""
        idx  = self._type_combo.currentIndex()
        kind = _TOKEN_TYPES[idx][1]

        t = self._attr_select.currentText()
        a = "" if t in ("", "(load deck first)") else t

        token = ""
        if kind == "all":
            token = f"all:{a}" if a else ""

        elif kind == "unique":
            token = f"unique:{a}" if a else ""

        elif kind == "straight":
            if not a:
                token = ""
            elif not self._straight_wrap.isChecked():
                token = f"straight:{a}"
            else:
                n = self._straight_wrap_count.value()
                token = f"straight:{a}:wrap={n}" if n > 0 else f"straight:{a}:wrap"

        elif kind == "pattern":
            pat = self._pattern_edit.text().strip()
            token = f"pattern:{a}={pat}" if a and pat else ""

        elif kind == "nof":
            op = self._nof_op.currentText()
            n  = self._nof_count.value()
            token = f"nof:{a}{op}{n}" if a else ""

        elif kind == "count":
            val = self._count_value.currentText()
            if a and val and val != "(load deck first)":
                op = self._count_op.currentText()
                n  = self._count_spin_w.value()
                token = f"{a}:{val}{op}{n}"

        if token and self._not_check.isChecked():
            token = f"not:{token}"
        return token


# ---------------------------------------------------------------------------
# Filter clause widget  (one OR-group) — compact card, fixed width
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
        super().__init__(f"OR Clause {clause_num}", parent)
        self.attr_names  = list(attr_names)
        self.attr_values = dict(attr_values)
        self._tokens: List[FilterTokenWidget] = []
        self.setFixedWidth(360)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self._build_ui()

    def _build_ui(self) -> None:
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(6, 4, 6, 6)
        self._outer.setSpacing(4)

        # Header: remove button right-aligned
        hdr = QHBoxLayout()
        hdr.addStretch()
        remove_btn = QPushButton("Remove")
        remove_btn.setProperty("danger", True)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        hdr.addWidget(remove_btn)
        self._outer.addLayout(hdr)

        # Token rows
        self._token_layout = QVBoxLayout()
        self._token_layout.setSpacing(4)
        self._outer.addLayout(self._token_layout)

        # Add condition button
        add_btn = QPushButton("+ AND Condition")
        add_btn.setProperty("secondary", True)
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
# Filter builder widget — horizontal scrolling card row
# ---------------------------------------------------------------------------

class FilterBuilderWidget(QWidget):
    filter_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._clauses:     List[FilterClauseWidget] = []
        self._attr_names:  List[str]                = []
        self._attr_values: Dict[str, List[str]]     = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        # Horizontally scrollable clause card row
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(220)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._clause_container = QWidget()
        self._clause_container.setObjectName("clauseContainer")
        self._clause_layout    = QHBoxLayout(self._clause_container)
        self._clause_layout.setSpacing(8)
        self._clause_layout.setContentsMargins(4, 4, 4, 4)
        self._clause_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._clause_layout.addStretch()
        scroll.setWidget(self._clause_container)
        layout.addWidget(scroll)

        add_btn = QPushButton("+ Add OR Clause")
        add_btn.clicked.connect(self._add_clause)
        layout.addWidget(add_btn)

        # Generated filter string (read-only reference)
        row = QHBoxLayout()
        row.addWidget(QLabel("Filter:"))
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
            clause.setTitle(f"OR Clause {i + 1}")

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
