from __future__ import annotations
import os
import sys


def resource_path(relative_path: str) -> str:
    """Return absolute path to a bundled resource, works for dev and PyInstaller --onefile."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
