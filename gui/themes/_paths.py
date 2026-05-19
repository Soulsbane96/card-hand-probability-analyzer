from __future__ import annotations
import os

_THEMES_DIR = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR    = os.path.dirname(_THEMES_DIR)

CHECK_PATH     = os.path.join(_GUI_DIR, "check.svg").replace("\\", "/")
RADIO_DOT_PATH = os.path.join(_GUI_DIR, "radio_dot.svg").replace("\\", "/")
