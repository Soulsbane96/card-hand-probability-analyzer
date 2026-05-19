from __future__ import annotations

from typing import Dict, List

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


# ---------------------------------------------------------------------------
# Output options widget
# ---------------------------------------------------------------------------

class OptionsWidget(QGroupBox):
    def __init__(self, parent=None):
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
