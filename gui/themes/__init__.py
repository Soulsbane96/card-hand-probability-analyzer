from __future__ import annotations
import os
import importlib

from gui.themes._paths import CHECK_PATH, RADIO_DOT_PATH
from gui.themes._builder import build_stylesheet
from gui.themes.light import PALETTE as _LIGHT_PALETTE, THEME_NAME as _LIGHT_NAME
from gui.themes.dark import PALETTE as _DARK_PALETTE, THEME_NAME as _DARK_NAME

HIGHLIGHT_COLORS: dict[str, str] = {}
THEMES: dict[str, str] = {}


def _register(name: str, palette: dict[str, str]) -> None:
    THEMES[name] = build_stylesheet(palette, CHECK_PATH, RADIO_DOT_PATH)
    HIGHLIGHT_COLORS[name] = palette["highlight"]


_register(_LIGHT_NAME, _LIGHT_PALETTE)
_register(_DARK_NAME, _DARK_PALETTE)

_BUILTIN_MODULES = {"light", "dark"}
_HERE = os.path.dirname(__file__)

for _fname in sorted(os.listdir(_HERE)):
    if _fname.startswith("_") or not _fname.endswith(".py"):
        continue
    _mod_name = _fname[:-3]
    if _mod_name in _BUILTIN_MODULES:
        continue
    try:
        _mod = importlib.import_module(f"gui.themes.{_mod_name}")
        if hasattr(_mod, "PALETTE"):
            _name = getattr(_mod, "THEME_NAME", _mod_name)
            _register(_name, _mod.PALETTE)
    except Exception:
        pass
