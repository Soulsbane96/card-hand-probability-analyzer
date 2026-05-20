from __future__ import annotations

THEME_NAME = "dark"

PALETTE: dict[str, str] = {
    # ── Backgrounds ──────────────────────────────────────────────────────────
    "window_bg":              "#1E1E2E",  # Main app window / dialog background
    "panel_bg":               "#2A2A3C",  # Cards, group boxes, tab content area
    "input_bg":               "#313244",  # Text fields, spinboxes, dropdowns
    "input_bg_readonly":      "#262630",  # Read-only or disabled text fields
    "clause_container_bg":    "#1E1E2E",  # Scroll area inside the filter builder
    "alt_row_bg":             "#262630",  # Every other row in tables
    "plaintext_bg":           "#262630",  # QPlainTextEdit background
    "checkbox_bg":            "transparent",  # Area behind a checkbox label

    # ── Text ─────────────────────────────────────────────────────────────────
    "text":                   "#CDD6F4",  # Primary body text
    "text_muted":             "#7F849C",  # Subdued text (read-only fields, inactive tabs)
    "text_hint":              "#7F849C",  # Tiny hint labels below inputs
    "text_header":            "#BAC2DE",  # Table column header text

    # ── Accent — primary interactive blue ────────────────────────────────────
    "accent":                 "#1976D2",  # Button fill, checked indicator fill
    "accent_hover":           "#2196F3",  # Button hover state
    "accent_pressed":         "#1565C0",  # Button pressed / prominent button base color
    "accent_dark":            "#0D47A1",  # Prominent button deepest press state
    "accent_focus":           "#89B4FA",  # Focus rings on inputs, group-box title, selected-tab text
    "accent_faint":           "#1A3460",  # Tint fill for selections and hover backgrounds

    # ── Borders ──────────────────────────────────────────────────────────────
    "border":                 "#45475A",  # Default widget / panel border
    "border_muted":           "#45475A",  # Softer inner borders and splitter handles

    # ── Checkbox / radio indicators ──────────────────────────────────────────
    "indicator_border":       "#B0BEC5",  # Border ring around the indicator box or circle
    "indicator_bg":           "#CDD6F4",  # Unchecked checkbox indicator fill
    "radio_indicator_bg":     "#FFFFFF",  # Unchecked radio button indicator fill

    # ── Secondary button (outlined style) ────────────────────────────────────
    "secondary_text":         "#89B4FA",
    "secondary_bg":           "#1A2845",
    "secondary_border":       "#2A4A7A",
    "secondary_hover_bg":     "#1E3252",
    "secondary_hover_border": "#89B4FA",
    "secondary_pressed_bg":   "#243C65",

    # ── Danger button ────────────────────────────────────────────────────────
    "danger_text":            "#F38BA8",
    "danger_border":          "#584244",
    "danger_hover_bg":        "#3D2B2E",
    "danger_hover_border":    "#F38BA8",
    "danger_pressed_bg":      "#4D3033",

    # ── Disabled state ───────────────────────────────────────────────────────
    "disabled_bg":            "#45475A",  # Disabled button fill
    "disabled_text":          "#7F849C",  # Disabled button label color

    # ── Selection (lists, tables, dropdowns) ─────────────────────────────────
    "selection_bg":           "#1A3460",  # Selected item / cell background
    "selection_text":         "#89B4FA",  # Selected item / cell text

    # ── Tabs ─────────────────────────────────────────────────────────────────
    "tab_inactive_bg":        "#1E1E2E",
    "tab_inactive_text":      "#7F849C",
    "tab_selected_bg":        "#2A2A3C",
    "tab_selected_text":      "#89B4FA",
    "tab_hover_bg":           "#252538",
    "tab_hover_text":         "#CDD6F4",

    # ── Scrollbars ───────────────────────────────────────────────────────────
    "scrollbar_track":        "#1E1E2E",  # Scrollbar track / trough color
    "scrollbar_handle":       "#585B70",  # Draggable thumb
    "scrollbar_hover":        "#7F849C",  # Thumb on hover

    # ── Table ────────────────────────────────────────────────────────────────
    "table_bg":               "#2A2A3C",
    "table_gridline":         "#313244",
    "header_bg":              "#313244",
    "header_hover_bg":        "#1A3460",

    # ── Status bar ───────────────────────────────────────────────────────────
    "statusbar_bg":           "#11111B",
    "statusbar_text":         "#CDD6F4",

    # ── Progress bar ─────────────────────────────────────────────────────────
    "progress_track":         "#313244",
    "progress_fill":          "#89B4FA",

    # ── Menu bar ─────────────────────────────────────────────────────────────
    "menubar_bg":             "#181825",
    "menubar_text":           "#CDD6F4",
    "menubar_border":         "#45475A",  # Bottom border line
    "menubar_selected_bg":    "#313244",
    "menubar_selected_text":  "#89B4FA",

    # ── Dropdown menus ───────────────────────────────────────────────────────
    "menu_bg":                "#2A2A3C",
    "menu_text":              "#CDD6F4",
    "menu_border":            "#45475A",
    "menu_selected_bg":       "#1A3460",
    "menu_selected_text":     "#89B4FA",

    # ── Highlight (matched-card cell tint in the results table) ──────────────
    "highlight":              "#1565C0",
}
