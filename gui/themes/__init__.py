from __future__ import annotations
import importlib.util
import os
import sys

from gui.themes._paths import CHECK_PATH, RADIO_DOT_PATH
from gui.themes._builder import build_stylesheet

HIGHLIGHT_COLORS: dict[str, str] = {}
THEMES: dict[str, str] = {}

# Fallback palettes used when the external themes/ folder is missing entirely.
_FALLBACK_PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "window_bg": "#ECEFF1", "panel_bg": "#FFFFFF", "input_bg": "#FFFFFF",
        "input_bg_readonly": "#F5F5F5", "clause_container_bg": "#FFFFFF",
        "alt_row_bg": "#F5F7F8", "plaintext_bg": "#FAFAFA", "checkbox_bg": "#FAFAFA",
        "text": "#212121", "text_muted": "#546E7A", "text_hint": "#78909C",
        "text_header": "#37474F", "accent": "#1976D2", "accent_hover": "#1E88E5",
        "accent_pressed": "#1565C0", "accent_dark": "#0D47A1", "accent_focus": "#1976D2",
        "accent_faint": "#E3F2FD", "border": "#CFD8DC", "border_muted": "#B0BEC5",
        "indicator_border": "#B0BEC5", "indicator_bg": "#FFFFFF", "radio_indicator_bg": "#FFFFFF",
        "secondary_text": "#1565C0", "secondary_bg": "#E3F2FD", "secondary_border": "#90CAF9",
        "secondary_hover_bg": "#BBDEFB", "secondary_hover_border": "#42A5F5",
        "secondary_pressed_bg": "#90CAF9", "danger_text": "#C62828",
        "danger_border": "#FFCDD2", "danger_hover_bg": "#FFEBEE",
        "danger_hover_border": "#EF9A9A", "danger_pressed_bg": "#FFCDD2",
        "disabled_bg": "#B0BEC5", "disabled_text": "#FFFFFF",
        "selection_bg": "#E3F2FD", "selection_text": "#1565C0",
        "tab_inactive_bg": "#ECEFF1", "tab_inactive_text": "#546E7A",
        "tab_selected_bg": "#FFFFFF", "tab_selected_text": "#1565C0",
        "tab_hover_bg": "#E3F2FD", "tab_hover_text": "#1976D2",
        "scrollbar_track": "#F5F5F5", "scrollbar_handle": "#90A4AE", "scrollbar_hover": "#607D8B",
        "table_bg": "#FFFFFF", "table_gridline": "#ECEFF1",
        "header_bg": "#ECEFF1", "header_hover_bg": "#E3F2FD",
        "statusbar_bg": "#1565C0", "statusbar_text": "#FFFFFF",
        "progress_track": "#E3F2FD", "progress_fill": "#42A5F5",
        "menubar_bg": "#ECEFF1", "menubar_text": "#212121", "menubar_border": "transparent",
        "menubar_selected_bg": "#E3F2FD", "menubar_selected_text": "#1565C0",
        "menu_bg": "#FFFFFF", "menu_text": "#212121", "menu_border": "#CFD8DC",
        "menu_selected_bg": "#E3F2FD", "menu_selected_text": "#1565C0",
        "highlight": "#1565C0",
    },
    "dark": {
        "window_bg": "#1E1E2E", "panel_bg": "#2A2A3C", "input_bg": "#313244",
        "input_bg_readonly": "#262630", "clause_container_bg": "#1E1E2E",
        "alt_row_bg": "#262630", "plaintext_bg": "#262630", "checkbox_bg": "transparent",
        "text": "#CDD6F4", "text_muted": "#7F849C", "text_hint": "#7F849C",
        "text_header": "#BAC2DE", "accent": "#1976D2", "accent_hover": "#2196F3",
        "accent_pressed": "#1565C0", "accent_dark": "#0D47A1", "accent_focus": "#89B4FA",
        "accent_faint": "#1A3460", "border": "#45475A", "border_muted": "#45475A",
        "indicator_border": "#B0BEC5", "indicator_bg": "#CDD6F4", "radio_indicator_bg": "#FFFFFF",
        "secondary_text": "#89B4FA", "secondary_bg": "#1A2845", "secondary_border": "#2A4A7A",
        "secondary_hover_bg": "#1E3252", "secondary_hover_border": "#89B4FA",
        "secondary_pressed_bg": "#243C65", "danger_text": "#F38BA8",
        "danger_border": "#584244", "danger_hover_bg": "#3D2B2E",
        "danger_hover_border": "#F38BA8", "danger_pressed_bg": "#4D3033",
        "disabled_bg": "#45475A", "disabled_text": "#7F849C",
        "selection_bg": "#1A3460", "selection_text": "#89B4FA",
        "tab_inactive_bg": "#1E1E2E", "tab_inactive_text": "#7F849C",
        "tab_selected_bg": "#2A2A3C", "tab_selected_text": "#89B4FA",
        "tab_hover_bg": "#252538", "tab_hover_text": "#CDD6F4",
        "scrollbar_track": "#1E1E2E", "scrollbar_handle": "#585B70", "scrollbar_hover": "#7F849C",
        "table_bg": "#2A2A3C", "table_gridline": "#313244",
        "header_bg": "#313244", "header_hover_bg": "#1A3460",
        "statusbar_bg": "#11111B", "statusbar_text": "#CDD6F4",
        "progress_track": "#313244", "progress_fill": "#89B4FA",
        "menubar_bg": "#181825", "menubar_text": "#CDD6F4", "menubar_border": "#45475A",
        "menubar_selected_bg": "#313244", "menubar_selected_text": "#89B4FA",
        "menu_bg": "#2A2A3C", "menu_text": "#CDD6F4", "menu_border": "#45475A",
        "menu_selected_bg": "#1A3460", "menu_selected_text": "#89B4FA",
        "highlight": "#1565C0",
    },
    "Forest": {
        "window_bg": "#1E2E1E", "panel_bg": "#2A3C2A", "input_bg": "#313244",
        "input_bg_readonly": "#263026", "clause_container_bg": "#1E2E1E",
        "alt_row_bg": "#263026", "plaintext_bg": "#263026", "checkbox_bg": "transparent",
        "text": "#CDF4CD", "text_muted": "#7F9C7F", "text_hint": "#7F9C7F",
        "text_header": "#BADEC6", "accent": "#2A7A2A", "accent_hover": "#30AC30",
        "accent_pressed": "#0E8D0E", "accent_dark": "#0DA121", "accent_focus": "#89FA89",
        "accent_faint": "#1A601A", "border": "#45475A", "border_muted": "#45475A",
        "indicator_border": "#B0BEC5", "indicator_bg": "#CDF4CD", "radio_indicator_bg": "#FFFFFF",
        "secondary_text": "#89FA89", "secondary_bg": "#1A451A", "secondary_border": "#2A7A2A",
        "secondary_hover_bg": "#24521E", "secondary_hover_border": "#89FA89",
        "secondary_pressed_bg": "#24652D", "danger_text": "#FF5353",
        "danger_border": "#584244", "danger_hover_bg": "#3D2B2E",
        "danger_hover_border": "#FF5353", "danger_pressed_bg": "#4D3033",
        "disabled_bg": "#45475A", "disabled_text": "#7F9C7F",
        "selection_bg": "#1A601A", "selection_text": "#89FA89",
        "tab_inactive_bg": "#1E2E1E", "tab_inactive_text": "#7F9C7F",
        "tab_selected_bg": "#2A3C2A", "tab_selected_text": "#89FA89",
        "tab_hover_bg": "#252538", "tab_hover_text": "#CDF4CD",
        "scrollbar_track": "#1E2E1E", "scrollbar_handle": "#585B70", "scrollbar_hover": "#7F9C7F",
        "table_bg": "#2A3C2A", "table_gridline": "#313244",
        "header_bg": "#313244", "header_hover_bg": "#1A601A",
        "statusbar_bg": "#313244", "statusbar_text": "#CDF4CD",
        "progress_track": "#313244", "progress_fill": "#89FA89",
        "menubar_bg": "#181825", "menubar_text": "#CDF4CD", "menubar_border": "#45475A",
        "menubar_selected_bg": "#313244", "menubar_selected_text": "#89FA89",
        "menu_bg": "#2A3C2A", "menu_text": "#CDF4CD", "menu_border": "#45475A",
        "menu_selected_bg": "#1A601A", "menu_selected_text": "#89FA89",
        "highlight": "#15C01D",
    },
}


def _register(name: str, palette: dict[str, str]) -> None:
    THEMES[name] = build_stylesheet(palette, CHECK_PATH, RADIO_DOT_PATH)
    HIGHLIGHT_COLORS[name] = palette["highlight"]


def _find_themes_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "themes")
    # Development: project root is two levels above gui/themes/
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "themes")


def _load_from_dir(themes_dir: str) -> None:
    for fname in sorted(os.listdir(themes_dir)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        path = os.path.join(themes_dir, fname)
        mod_name = fname[:-3]
        try:
            spec = importlib.util.spec_from_file_location(f"ext_theme.{mod_name}", path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if hasattr(mod, "PALETTE"):
                name = getattr(mod, "THEME_NAME", mod_name)
                _register(name, mod.PALETTE)
        except Exception:
            pass


themes_dir = _find_themes_dir()
if os.path.isdir(themes_dir):
    _load_from_dir(themes_dir)
else:
    for _name, _palette in _FALLBACK_PALETTES.items():
        _register(_name, _palette)
