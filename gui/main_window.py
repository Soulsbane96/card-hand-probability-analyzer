from __future__ import annotations

import sys
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.filters import FilterSpec
from gui.themes import THEMES
from gui.settings import load_theme, save_theme
from gui.workers import AnalysisWorker
from gui.filter_widgets import FilterBuilderWidget
from gui.deck_widgets import DeckConfigWidget
from gui.options import OptionsWidget
from gui.results import ResultsPanel


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Card Combination Analyzer")
        self.setMinimumSize(1100, 600)
        self._worker: Optional[AnalysisWorker] = None
        self._build_ui()
        self._build_menu_bar()

    def _build_menu_bar(self) -> None:
        theme_menu = self.menuBar().addMenu("Theme")
        group = QActionGroup(self)
        self._theme_actions: Dict[str, QAction] = {}

        for key in THEMES:
            label = key.replace("_", " ").title()
            action = QAction(label, self, checkable=True)
            action.triggered.connect(lambda _, k=key: self._set_theme(k))
            group.addAction(action)
            theme_menu.addAction(action)
            self._theme_actions[key] = action

        self._sync_theme_check()

    def _sync_theme_check(self) -> None:
        current = load_theme()
        for key, action in self._theme_actions.items():
            action.setChecked(key == current)

    def _set_theme(self, name: str) -> None:
        save_theme(name)
        QApplication.instance().setStyleSheet(THEMES[name])
        self._sync_theme_check()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

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
        self._run_btn.setProperty("prominent", True)
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

        splitter.setCollapsible(1, True)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([10000, 0])
        self._splitter = splitter

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

    def _on_finished(self, stats: dict, filter_spec: Optional[FilterSpec]) -> None:
        self._progress_bar.setVisible(False)
        self._progress_label.setText("")
        self._run_btn.setEnabled(True)

        warnings = stats.get("warnings", [])
        if warnings:
            QMessageBox.warning(self, "Filter Warnings", "\n".join(warnings))

        self._results.populate(stats, filter_spec)
        self._results.setCurrentIndex(0)
        if self._splitter.sizes()[1] == 0:
            w = self._splitter.width()
            self._splitter.setSizes([int(w * 0.4), int(w * 0.6)])

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
    app.setStyleSheet(THEMES[load_theme()])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
