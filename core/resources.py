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


def app_dir() -> str:
    """Return the writable application directory (next to the exe when frozen, project root in dev).
    Use this for user-facing data like deck_cache that should be portable alongside the app."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
