from __future__ import annotations
import os
import sys
import tempfile

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core.updater import apply_update, download_update


class _DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url: str, dest: str) -> None:
        super().__init__()
        self._url  = url
        self._dest = dest

    def run(self) -> None:
        try:
            download_update(self._url, self._dest, self.progress.emit)
            self.finished.emit(self._dest)
        except Exception as exc:
            self.error.emit(str(exc))


class UpdateDialog(QDialog):
    def __init__(self, new_version: str, download_url: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setFixedWidth(420)
        self._url  = download_url
        self._dest = os.path.join(tempfile.gettempdir(), "CardHandAnalyzer_new.exe")

        layout = QVBoxLayout(self)

        self._label = QLabel(
            f"<b>Version {new_version} is available.</b><br>"
            "Would you like to download and install it now?"
        )
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        buttons = QDialogButtonBox()
        self._update_btn = QPushButton("Update Now")
        self._later_btn  = QPushButton("Later")
        buttons.addButton(self._update_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self._later_btn,  QDialogButtonBox.ButtonRole.RejectRole)
        self._update_btn.clicked.connect(self._start_download)
        self._later_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _start_download(self) -> None:
        self._update_btn.setEnabled(False)
        self._later_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._label.setText("Downloading update…")

        self._thread = _DownloadThread(self._url, self._dest)
        self._thread.progress.connect(self._progress.setValue)
        self._thread.finished.connect(self._on_downloaded)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_downloaded(self, path: str) -> None:
        self._label.setText("Restarting…")
        apply_update(sys.executable, path)

    def _on_error(self, msg: str) -> None:
        self._label.setText(f"Download failed: {msg}")
        self._update_btn.setEnabled(True)
        self._later_btn.setEnabled(True)
        self._progress.setVisible(False)
