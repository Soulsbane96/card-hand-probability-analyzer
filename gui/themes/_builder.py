from __future__ import annotations
from string import Template

_QSS = Template("""
QMainWindow, QDialog {
    background-color: $window_bg;
}
QWidget {
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 9pt;
    color: $text;
    background-color: $window_bg;
}

QGroupBox {
    background-color: $panel_bg;
    border: 1px solid $border;
    border-radius: 6px;
    padding-top: 24px;
    margin-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    padding: 4px 8px;
    color: $accent_focus;
    font-weight: bold;
}

QSplitter::handle:vertical   { height: 2px; background-color: $border_muted; }
QSplitter::handle:horizontal { width:  2px; background-color: $border_muted; }

QPushButton {
    background-color: $accent;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 5px 14px;
    font-weight: 600;
    min-height: 26px;
}
QPushButton:hover    { background-color: $accent_hover; }
QPushButton:pressed  { background-color: $accent_pressed; }
QPushButton:disabled { background-color: $disabled_bg; color: $disabled_text; }

QPushButton[danger="true"] {
    background-color: transparent;
    color: $danger_text;
    border: 1px solid $danger_border;
    border-radius: 4px;
    padding: 3px 10px;
    font-weight: 600;
    min-height: 22px;
}
QPushButton[danger="true"]:hover   { background-color: $danger_hover_bg; border-color: $danger_hover_border; }
QPushButton[danger="true"]:pressed { background-color: $danger_pressed_bg; }

QPushButton[secondary="true"] {
    background-color: $secondary_bg;
    color: $secondary_text;
    border: 1px solid $secondary_border;
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 600;
    min-height: 24px;
}
QPushButton[secondary="true"]:hover   { background-color: $secondary_hover_bg; border-color: $secondary_hover_border; }
QPushButton[secondary="true"]:pressed { background-color: $secondary_pressed_bg; }

QLineEdit {
    border: 1px solid $border_muted;
    border-radius: 4px;
    padding: 4px 8px;
    background-color: $input_bg;
    color: $text;
    selection-background-color: $accent;
    selection-color: #FFFFFF;
    min-height: 22px;
}
QLineEdit:focus { border: 2px solid $accent_focus; }
QLineEdit[readOnly="true"] {
    background-color: $input_bg_readonly;
    color: $text_muted;
    border-style: dashed;
}

QSpinBox {
    border: 1px solid $border_muted;
    border-radius: 4px;
    padding: 3px 4px;
    background-color: $input_bg;
    color: $text;
    min-height: 22px;
}
QSpinBox:focus { border: 2px solid $accent_focus; }
QSpinBox::up-button, QSpinBox::down-button { border: none; background: transparent; width: 14px; }

QComboBox {
    border: 1px solid $border_muted;
    border-radius: 4px;
    padding: 3px 6px;
    background-color: $input_bg;
    color: $text;
    min-height: 22px;
}
QComboBox:focus { border: 2px solid $accent_focus; }
QComboBox::drop-down { border: none; padding-right: 4px; }
QComboBox QAbstractItemView {
    border: 1px solid $border_muted;
    background-color: $input_bg;
    color: $text;
    selection-background-color: $selection_bg;
    selection-color: $selection_text;
    outline: none;
}

QCheckBox {
    spacing: 6px;
    background-color: $checkbox_bg;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid $indicator_border;
    border-radius: 3px;
    background-color: $indicator_bg;
}
QCheckBox::indicator:checked {
    background-color: $accent;
    border-color: $accent;
    image: url($check_path);
}
QCheckBox::indicator:hover {
    border-color: $accent;
}

QRadioButton { spacing: 6px; color: $text; background-color: transparent; }
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid $indicator_border;
    border-radius: 7px;
    background-color: $radio_indicator_bg;
}
QRadioButton::indicator:checked {
    background-color: $accent;
    border-color: $accent;
    image: url($radio_dot_path);
}
QRadioButton::indicator:hover {
    border-color: $accent;
}

QTabWidget::pane {
    border: 1px solid $border;
    background-color: $panel_bg;
    border-radius: 0 4px 4px 4px;
    top: -1px;
}
QTabBar::tab {
    background-color: $tab_inactive_bg;
    color: $tab_inactive_text;
    padding: 6px 14px;
    border: 1px solid $border;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
    min-width: 80px;
}
QTabBar::tab:selected        { background-color: $tab_selected_bg; color: $tab_selected_text; font-weight: 600; }
QTabBar::tab:hover:!selected { background-color: $tab_hover_bg; color: $tab_hover_text; }

QScrollArea { border: none; background-color: transparent; }
QWidget#clauseContainer { background-color: $clause_container_bg; }
QScrollBar:horizontal {
    height: 8px; background-color: $scrollbar_track; margin: 0; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: $scrollbar_handle; border-radius: 4px; min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background-color: $scrollbar_hover; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; height: 0; }
QScrollBar:vertical {
    width: 8px; background-color: $scrollbar_track; margin: 0; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: $scrollbar_handle; border-radius: 4px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background-color: $scrollbar_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { width: 0; height: 0; }

QTableWidget, QTableView {
    gridline-color: $table_gridline;
    border: 1px solid $border;
    border-radius: 4px;
    selection-background-color: $selection_bg;
    selection-color: $selection_text;
    alternate-background-color: $alt_row_bg;
    background-color: $table_bg;
    color: $text;
}
QHeaderView::section {
    background-color: $header_bg;
    color: $text_header;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 1px solid $border_muted;
    font-weight: 600;
}
QHeaderView::section:hover { background-color: $header_hover_bg; }

QStatusBar {
    background-color: $statusbar_bg;
    color: $statusbar_text;
    font-size: 9pt;
    padding: 2px 6px;
    min-height: 22px;
}

QProgressBar {
    border: none;
    border-radius: 2px;
    background-color: $progress_track;
    text-align: center;
    max-height: 6px;
}
QProgressBar::chunk { background-color: $progress_fill; border-radius: 2px; }

QPlainTextEdit {
    background-color: $plaintext_bg;
    color: $text;
    border: 1px solid $border;
    border-radius: 4px;
}

QLabel#hintLabel {
    color: $text_hint;
    font-size: 8pt;
}

QPushButton[prominent="true"] {
    background-color: $accent_pressed;
    font-size: 10pt;
    letter-spacing: 0.5px;
    border-radius: 4px;
}
QPushButton[prominent="true"]:hover   { background-color: $accent; }
QPushButton[prominent="true"]:pressed { background-color: $accent_dark; }

QMenuBar {
    background-color: $menubar_bg;
    color: $menubar_text;
    border-bottom: 1px solid $menubar_border;
}
QMenuBar::item:selected { background-color: $menubar_selected_bg; color: $menubar_selected_text; }
QMenu {
    background-color: $menu_bg;
    color: $menu_text;
    border: 1px solid $menu_border;
}
QMenu::item:selected { background-color: $menu_selected_bg; color: $menu_selected_text; }
QMenu::indicator { width: 16px; height: 16px; }
""")


def build_stylesheet(palette: dict[str, str], check_path: str, radio_dot_path: str) -> str:
    return _QSS.substitute(**palette, check_path=check_path, radio_dot_path=radio_dot_path)
