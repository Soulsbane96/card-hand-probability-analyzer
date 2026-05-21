from __future__ import annotations

THEME_NAME = "magma"

PALETTE: dict[str, str] = {
    # ── Backgrounds ──────────────────────────────────────────────────────────
    "window_bg":              "#1D0101",  # Main app window / dialog background
    "panel_bg":               "#200707",  # Cards, group boxes, tab content area
    "input_bg":               "#3F1B1B",  # Text fields, spinboxes, dropdowns
    "input_bg_readonly":      "#3D1E1E",  # Read-only or disabled text fields
    "clause_container_bg":    "#270B0B",  # Scroll area inside the filter builder
    "alt_row_bg":             "#1F0E0E",  # Every other row in tables
    "plaintext_bg":           "#302626",  # QPlainTextEdit background
    "checkbox_bg":            "transparent",  # Area behind a checkbox label

    # ── Text ─────────────────────────────────────────────────────────────────
    "text":                   "#F4CDCD",  # Primary body text
    "text_muted":             "#9C7F7F",  # Subdued text (read-only fields, inactive tabs)
    "text_hint":              "#9C7F7F",  # Tiny hint labels below inputs
    "text_header":            "#DEBABA",  # Table column header text

    # ── Accent — primary interactive red ────────────────────────────────────
    "accent":                 "#9B1919",  # Button fill, checked indicator fill
    "accent_hover":           "#E91717",  # Button hover state
    "accent_pressed":         "#C01515",  # Button pressed / prominent button base color
    "accent_dark":            "#880B0B",  # Prominent button deepest press state
    "accent_focus":           "#F74E4E",  # Focus rings on inputs, group-box title, selected-tab text
    "accent_faint":           "#501414",  # Tint fill for selections and hover backgrounds

    # ── Borders ──────────────────────────────────────────────────────────────
    "border":                 "#5A4545",  # Default widget / panel border
    "border_muted":           "#5A4545",  # Softer inner borders and splitter handles

    # ── Checkbox / radio indicators ──────────────────────────────────────────
    "indicator_border":       "#C5B0B0",  # Border ring around the indicator box or circle
    "indicator_bg":           "#F4CDCD",  # Unchecked checkbox indicator fill
    "radio_indicator_bg":     "#FFFFFF",  # Unchecked radio button indicator fill

    # ── Secondary button (outlined style) ────────────────────────────────────
    "secondary_text":         "#FA8989",
    "secondary_bg":           "#451A1A",
    "secondary_border":       "#7A2A2A",
    "secondary_hover_bg":     "#521E1E",
    "secondary_hover_border": "#FA8989",
    "secondary_pressed_bg":   "#652424",

    # ── Danger button ────────────────────────────────────────────────────────
    "danger_text":            "#FFA600",
    "danger_border":          "#C07000",
    "danger_hover_bg":        "#75450A",
    "danger_hover_border":    "#FFA600",
    "danger_pressed_bg":      "#7C6108",

    # ── Disabled state ───────────────────────────────────────────────────────
    "disabled_bg":            "#5F3131",  # Disabled button fill
    "disabled_text":          "#A16363",  # Disabled button label color

    # ── Selection (lists, tables, dropdowns) ─────────────────────────────────
    "selection_bg":           "#601A1A",  # Selected item / cell background
    "selection_text":         "#FA8989",  # Selected item / cell text

    # ── Tabs ─────────────────────────────────────────────────────────────────
    "tab_inactive_bg":        "#361717",
    "tab_inactive_text":      "#AC6666",
    "tab_selected_bg":        "#691717",
    "tab_selected_text":      "#E4C0C0",
    "tab_hover_bg":           "#472424",
    "tab_hover_text":         "#F7D8D8",

    # ── Scrollbars ───────────────────────────────────────────────────────────
    "scrollbar_track":        "#251515",  # Scrollbar track / trough color
    "scrollbar_handle":       "#532C2C",  # Draggable thumb
    "scrollbar_hover":        "#8F4343",  # Thumb on hover

    # ── Table ────────────────────────────────────────────────────────────────
    "table_bg":               "#471B1B",
    "table_gridline":         "#4E1212",
    "header_bg":              "#700505",
    "header_hover_bg":        "#690707",

    # ── Status bar ───────────────────────────────────────────────────────────
    "statusbar_bg":           "#1B1111",
    "statusbar_text":         "#F4CDCD",

    # ── Progress bar ─────────────────────────────────────────────────────────
    "progress_track":         "#443131",
    "progress_fill":          "#FA8989",

    # ── Menu bar ─────────────────────────────────────────────────────────────
    "menubar_bg":             "#251818",
    "menubar_text":           "#F4CDCD",
    "menubar_border":         "#5A4545",  # Bottom border line
    "menubar_selected_bg":    "#443131",
    "menubar_selected_text":  "#FA8989",

    # ── Dropdown menus ───────────────────────────────────────────────────────
    "menu_bg":                "#3C2A2A",
    "menu_text":              "#F4CDCD",
    "menu_border":            "#5A4545",
    "menu_selected_bg":       "#601A1A",
    "menu_selected_text":     "#FA8989",

    # ── Highlight (matched-card cell tint in the results table) ──────────────
    "highlight":              "#C01515",
}
