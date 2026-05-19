from __future__ import annotations

from PyQt6.QtCore import QSettings

_ORG = "CardHandAnalyzer"
_APP = "CardHandAnalyzer"


def load_theme() -> str:
    return QSettings(_ORG, _APP).value("theme", "light")


def save_theme(name: str) -> None:
    QSettings(_ORG, _APP).setValue("theme", name)
