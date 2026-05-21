from __future__ import annotations

import sys
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QFont, QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from version import __version__
from core.filters import FilterSpec
from core.resources import resource_path
from core.updater import check_for_update
from gui.themes import THEMES
from gui.update_dialog import UpdateDialog
from gui.settings import load_theme, save_theme
from gui.workers import AnalysisWorker
from gui.filter_widgets import FilterBuilderWidget
from gui.deck_widgets import DeckConfigWidget
from gui.options import OptionsWidget
from gui.results import ResultsPanel


# ---------------------------------------------------------------------------
# Background update checker
# ---------------------------------------------------------------------------

class _UpdateCheckThread(QThread):
    update_found = pyqtSignal(str, str)  # new_version, download_url

    def run(self) -> None:
        try:
            has_update, new_version, url = check_for_update(__version__)
            if has_update and url:
                self.update_found.emit(new_version, url)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Hand Probability Analyzer v{__version__}")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setMinimumSize(1100, 600)
        self._worker: Optional[AnalysisWorker] = None
        self._update_thread: Optional[_UpdateCheckThread] = None
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
        self._results.refresh_highlight_colors()
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

        # Log console — collapsed by default, expands to show all progress messages
        self._log_toggle = QPushButton("▶ Log")
        self._log_toggle.setCheckable(True)
        self._log_toggle.setFlat(True)
        self._log_toggle.setFixedHeight(20)
        self._log_toggle.toggled.connect(self._on_log_toggle)

        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFont(QFont("Courier New", 8))
        self._log_text.setMaximumBlockCount(500)
        self._log_text.setFixedHeight(120)
        self._log_text.setVisible(False)
        self._log_msg_count = 0

        config_layout.addWidget(self._log_toggle)
        config_layout.addWidget(self._log_text)

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
        self._log_text.clear()
        self._log_msg_count = 0
        self._log_toggle.setText("▶ Log")

        self._worker = AnalysisWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str) -> None:
        self._progress_label.setText(msg)
        self.statusBar().showMessage(msg)
        self._log_text.appendPlainText(msg)
        self._log_msg_count += 1
        if not self._log_toggle.isChecked():
            self._log_toggle.setText(f"▶ Log ({self._log_msg_count})")

    def _on_finished(self, stats: dict, filter_spec: Optional[FilterSpec]) -> None:
        self._progress_bar.setVisible(False)
        self._progress_label.setText("")
        self._run_btn.setEnabled(True)

        warnings = stats.get("warnings", [])
        if warnings:
            QMessageBox.warning(self, "Filter Warnings", "\n".join(warnings))

        # Build a map of original filter-row labels → user-supplied clause names.
        clause_names = self._filter_builder.get_clause_names()
        if any(clause_names) and filter_spec:
            name_iter       = iter(clause_names)
            filter_row_names: dict = {}
            for label, _, is_filter in stats.get("agg_checks", []):
                if is_filter:
                    custom = next(name_iter, "")
                    if custom:
                        filter_row_names[label] = custom
            if filter_row_names:
                stats["filter_row_names"] = filter_row_names

        self._results.populate(stats, filter_spec)
        self._results.setCurrentIndex(0)
        if self._splitter.sizes()[1] == 0:
            w = self._splitter.width()
            self._splitter.setSizes([int(w * 0.4), int(w * 0.6)])

        total    = stats["total_combinations"]
        filtered = stats["filtered_count"]
        if filter_spec:
            pct = f"{100 * filtered / total:.4f}%" if total else "0.0000%"
            summary = f"Done — {filtered:,} matching / {total:,} total ({pct})"
            self.statusBar().showMessage(
                f"Done  —  {filtered:,} matching hands / {total:,} total ({pct})"
            )
        else:
            summary = f"Done — {total:,} total combinations"
            self.statusBar().showMessage(f"Done  —  {total:,} total combinations")
        self._log_text.appendPlainText(summary)

    def _on_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._progress_label.setText("")
        self._run_btn.setEnabled(True)
        self._log_text.appendPlainText(f"Error: {msg}")
        QMessageBox.critical(self, "Analysis Error", msg)
        self.statusBar().showMessage("Error — see dialog for details.")

    def _on_log_toggle(self, checked: bool) -> None:
        self._log_text.setVisible(checked)
        if checked:
            self._log_toggle.setText("▼ Log")
            self._log_text.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self._log_toggle.setText(f"▶ Log ({self._log_msg_count})")

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if getattr(sys, "frozen", False):
            QTimer.singleShot(1500, self._start_update_check)

    def _start_update_check(self) -> None:
        self._update_thread = _UpdateCheckThread()
        self._update_thread.update_found.connect(self._on_update_found)
        self._update_thread.start()

    def _on_update_found(self, new_version: str, url: str) -> None:
        dlg = UpdateDialog(new_version, url, self)
        dlg.exec()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Required on Windows so the taskbar groups under this app, not a generic Python process.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"Soulsbane96.HandProbabilityAnalyzer.{__version__}"
        )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(THEMES[load_theme()])
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
