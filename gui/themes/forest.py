from __future__ import annotations

THEME_NAME = "Forest"

PALETTE: dict[str, str] = {
    # ── Backgrounds ──────────────────────────────────────────────────────────
    "window_bg":              "#1E2E1E",  # Main app window / dialog background
    "panel_bg":               "#2A3C2A",  # Cards, group boxes, tab content area
    "input_bg":               "#313244",  # Text fields, spinboxes, dropdowns
    "input_bg_readonly":      "#263026",  # Read-only or disabled text fields
    "clause_container_bg":    "#1E2E1E",  # Scroll area inside the filter builder
    "alt_row_bg":             "#263026",  # Every other row in tables
    "plaintext_bg":           "#263026",  # QPlainTextEdit background
    "checkbox_bg":            "transparent",  # Area behind a checkbox label

    # ── Text ─────────────────────────────────────────────────────────────────
    "text":                   "#CDF4CD",  # Primary body text
    "text_muted":             "#7F9C7F",  # Subdued text (read-only fields, inactive tabs)
    "text_hint":              "#7F9C7F",  # Tiny hint labels below inputs
    "text_header":            "#BADEC6",  # Table column header text

    # ── Accent — primary interactive green ────────────────────────────────────
    "accent":                 "#2A7A2A",  # Button fill, checked indicator fill
    "accent_hover":           "#30AC30",  # Button hover state
    "accent_pressed":         "#0E8D0E",  # Button pressed / prominent button base color
    "accent_dark":            "#0DA121",  # Prominent button deepest press state
    "accent_focus":           "#89FA89",  # Focus rings on inputs, group-box title, selected-tab text
    "accent_faint":           "#1A601A",  # Tint fill for selections and hover backgrounds

    # ── Borders ──────────────────────────────────────────────────────────────
    "border":                 "#45475A",  # Default widget / panel border
    "border_muted":           "#45475A",  # Softer inner borders and splitter handles

    # ── Checkbox / radio indicators ──────────────────────────────────────────
    "indicator_border":       "#B0BEC5",  # Border ring around the indicator box or circle
    "indicator_bg":           "#CDF4CD",  # Unchecked checkbox indicator fill
    "radio_indicator_bg":     "#FFFFFF",  # Unchecked radio button indicator fill

    # ── Secondary button (outlined style) ────────────────────────────────────
    "secondary_text":         "#89FA89",
    "secondary_bg":           "#1A451A",
    "secondary_border":       "#2A7A2A",
    "secondary_hover_bg":     "#24521E",
    "secondary_hover_border": "#89FA89",
    "secondary_pressed_bg":   "#24652D",

    # ── Danger button ────────────────────────────────────────────────────────
    "danger_text":            "#FF5353",
    "danger_border":          "#584244",
    "danger_hover_bg":        "#3D2B2E",
    "danger_hover_border":    "#FF5353",
    "danger_pressed_bg":      "#4D3033",

    # ── Disabled state ───────────────────────────────────────────────────────
    "disabled_bg":            "#45475A",  # Disabled button fill
    "disabled_text":          "#7F9C7F",  # Disabled button label color

    # ── Selection (lists, tables, dropdowns) ─────────────────────────────────
    "selection_bg":           "#1A601A",  # Selected item / cell background
    "selection_text":         "#89FA89",  # Selected item / cell text

    # ── Tabs ─────────────────────────────────────────────────────────────────
    "tab_inactive_bg":        "#1E2E1E",
    "tab_inactive_text":      "#7F9C7F",
    "tab_selected_bg":        "#2A3C2A",
    "tab_selected_text":      "#89FA89",
    "tab_hover_bg":           "#252538",
    "tab_hover_text":         "#CDF4CD",

    # ── Scrollbars ───────────────────────────────────────────────────────────
    "scrollbar_track":        "#1E2E1E",  # Scrollbar track / trough color
    "scrollbar_handle":       "#585B70",  # Draggable thumb
    "scrollbar_hover":        "#7F9C7F",  # Thumb on hover

    # ── Table ────────────────────────────────────────────────────────────────
    "table_bg":               "#2A3C2A",
    "table_gridline":         "#313244",
    "header_bg":              "#313244",
    "header_hover_bg":        "#1A601A",

    # ── Status bar ───────────────────────────────────────────────────────────
    "statusbar_bg":           "#313244",
    "statusbar_text":         "#CDF4CD",

    # ── Progress bar ─────────────────────────────────────────────────────────
    "progress_track":         "#313244",
    "progress_fill":          "#89FA89",

    # ── Menu bar ─────────────────────────────────────────────────────────────
    "menubar_bg":             "#181825",
    "menubar_text":           "#CDF4CD",
    "menubar_border":         "#45475A",  # Bottom border line
    "menubar_selected_bg":    "#313244",
    "menubar_selected_text":  "#89FA89",

    # ── Dropdown menus ───────────────────────────────────────────────────────
    "menu_bg":                "#2A3C2A",
    "menu_text":              "#CDF4CD",
    "menu_border":            "#45475A",
    "menu_selected_bg":       "#1A601A",
    "menu_selected_text":     "#89FA89",

    # ── Highlight (matched-card cell tint in the results table) ──────────────
    "highlight":              "#15C01D",
}
