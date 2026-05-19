from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import (
    Card,
    get_sequence_order,
    build_standard_deck,
    load_deck_from_csv,
    load_combinations_csv,
)


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
                deck, columns = build_standard_deck(deck_size)
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
                deck, columns = load_deck_from_csv(path, deck_size)
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
                combos, attr_names, hand_size = load_combinations_csv(path)
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
        deck:       List[Card],
        attr_names: List[str],
    ) -> Dict[str, List[str]]:
        result = {}
        for attr in attr_names:
            order = get_sequence_order(attr)
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
        combos:     List[Tuple[Card, ...]],
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
