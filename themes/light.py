from __future__ import annotations

THEME_NAME = "light"

PALETTE: dict[str, str] = {
    # ── Backgrounds ──────────────────────────────────────────────────────────
    "window_bg":              "#ECEFF1",  # Main app window / dialog background
    "panel_bg":               "#FFFFFF",  # Cards, group boxes, tab content area
    "input_bg":               "#FFFFFF",  # Text fields, spinboxes, dropdowns
    "input_bg_readonly":      "#F5F5F5",  # Read-only or disabled text fields
    "clause_container_bg":    "#FFFFFF",  # Scroll area inside the filter builder
    "alt_row_bg":             "#F5F7F8",  # Every other row in tables
    "plaintext_bg":           "#FAFAFA",  # QPlainTextEdit background
    "checkbox_bg":            "#FAFAFA",  # Area behind a checkbox label

    # ── Text ─────────────────────────────────────────────────────────────────
    "text":                   "#212121",  # Primary body text
    "text_muted":             "#546E7A",  # Subdued text (read-only fields, inactive tabs)
    "text_hint":              "#78909C",  # Tiny hint labels below inputs
    "text_header":            "#37474F",  # Table column header text

    # ── Accent — primary interactive blue ────────────────────────────────────
    "accent":                 "#1976D2",  # Button fill, checked indicator fill
    "accent_hover":           "#1E88E5",  # Button hover state
    "accent_pressed":         "#1565C0",  # Button pressed / prominent button base color
    "accent_dark":            "#0D47A1",  # Prominent button deepest press state
    "accent_focus":           "#1976D2",  # Focus rings on inputs, group-box title, selected-tab text
    "accent_faint":           "#E3F2FD",  # Very light tint for selections and hover fills

    # ── Borders ──────────────────────────────────────────────────────────────
    "border":                 "#CFD8DC",  # Default widget / panel border
    "border_muted":           "#B0BEC5",  # Softer inner borders and splitter handles

    # ── Checkbox / radio indicators ──────────────────────────────────────────
    "indicator_border":       "#B0BEC5",  # Border ring around the indicator box or circle
    "indicator_bg":           "#FFFFFF",  # Unchecked checkbox indicator fill
    "radio_indicator_bg":     "#FFFFFF",  # Unchecked radio button indicator fill

    # ── Secondary button (outlined style) ────────────────────────────────────
    "secondary_text":         "#1565C0",
    "secondary_bg":           "#E3F2FD",
    "secondary_border":       "#90CAF9",
    "secondary_hover_bg":     "#BBDEFB",
    "secondary_hover_border": "#42A5F5",
    "secondary_pressed_bg":   "#90CAF9",

    # ── Danger button ────────────────────────────────────────────────────────
    "danger_text":            "#C62828",
    "danger_border":          "#FFCDD2",
    "danger_hover_bg":        "#FFEBEE",
    "danger_hover_border":    "#EF9A9A",
    "danger_pressed_bg":      "#FFCDD2",

    # ── Disabled state ───────────────────────────────────────────────────────
    "disabled_bg":            "#B0BEC5",  # Disabled button fill
    "disabled_text":          "#FFFFFF",  # Disabled button label color

    # ── Selection (lists, tables, dropdowns) ─────────────────────────────────
    "selection_bg":           "#E3F2FD",  # Selected item / cell background
    "selection_text":         "#1565C0",  # Selected item / cell text

    # ── Tabs ─────────────────────────────────────────────────────────────────
    "tab_inactive_bg":        "#ECEFF1",
    "tab_inactive_text":      "#546E7A",
    "tab_selected_bg":        "#FFFFFF",
    "tab_selected_text":      "#1565C0",
    "tab_hover_bg":           "#E3F2FD",
    "tab_hover_text":         "#1976D2",

    # ── Scrollbars ───────────────────────────────────────────────────────────
    "scrollbar_track":        "#F5F5F5",  # Scrollbar track / trough color
    "scrollbar_handle":       "#90A4AE",  # Draggable thumb
    "scrollbar_hover":        "#607D8B",  # Thumb on hover

    # ── Table ────────────────────────────────────────────────────────────────
    "table_bg":               "#FFFFFF",
    "table_gridline":         "#ECEFF1",
    "header_bg":              "#ECEFF1",
    "header_hover_bg":        "#E3F2FD",

    # ── Status bar ───────────────────────────────────────────────────────────
    "statusbar_bg":           "#1565C0",
    "statusbar_text":         "#FFFFFF",

    # ── Progress bar ─────────────────────────────────────────────────────────
    "progress_track":         "#E3F2FD",
    "progress_fill":          "#42A5F5",

    # ── Menu bar ─────────────────────────────────────────────────────────────
    "menubar_bg":             "#ECEFF1",
    "menubar_text":           "#212121",
    "menubar_border":         "transparent",  # Bottom border (transparent = no visible line)
    "menubar_selected_bg":    "#E3F2FD",
    "menubar_selected_text":  "#1565C0",

    # ── Dropdown menus ───────────────────────────────────────────────────────
    "menu_bg":                "#FFFFFF",
    "menu_text":              "#212121",
    "menu_border":            "#CFD8DC",
    "menu_selected_bg":       "#E3F2FD",
    "menu_selected_text":     "#1565C0",

    # ── Highlight (matched-card cell tint in the results table) ──────────────
    "highlight":              "#1565C0",
}
