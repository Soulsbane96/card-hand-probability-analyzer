from __future__ import annotations
import os

_CHECK_PATH     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check.svg').replace('\\', '/')
_RADIO_DOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'radio_dot.svg').replace('\\', '/')

HIGHLIGHT_COLORS: dict[str, str] = {
    "light": "#1565C0",
    "dark":  "#1565C0",
}

LIGHT_STYLE = """
QMainWindow, QDialog {
    background-color: #ECEFF1;
}
QWidget {
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 9pt;
    color: #212121;
}

QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #CFD8DC;
    border-radius: 6px;
    padding-top: 24px;
    margin-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    padding: 4px 8px;
    color: #1565C0;
    font-weight: bold;
}

QSplitter::handle:vertical   { height: 2px; background-color: #B0BEC5; }
QSplitter::handle:horizontal { width:  2px; background-color: #B0BEC5; }

QPushButton {
    background-color: #1976D2;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 5px 14px;
    font-weight: 600;
    min-height: 26px;
}
QPushButton:hover    { background-color: #1E88E5; }
QPushButton:pressed  { background-color: #1565C0; }
QPushButton:disabled { background-color: #B0BEC5; color: #FFFFFF; }

QPushButton[danger="true"] {
    background-color: transparent;
    color: #C62828;
    border: 1px solid #FFCDD2;
    border-radius: 4px;
    padding: 3px 10px;
    font-weight: 600;
    min-height: 22px;
}
QPushButton[danger="true"]:hover   { background-color: #FFEBEE; border-color: #EF9A9A; }
QPushButton[danger="true"]:pressed { background-color: #FFCDD2; }

QPushButton[secondary="true"] {
    background-color: #E3F2FD;
    color: #1565C0;
    border: 1px solid #90CAF9;
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 600;
    min-height: 24px;
}
QPushButton[secondary="true"]:hover   { background-color: #BBDEFB; border-color: #42A5F5; }
QPushButton[secondary="true"]:pressed { background-color: #90CAF9; }

QLineEdit {
    border: 1px solid #B0BEC5;
    border-radius: 4px;
    padding: 4px 8px;
    background-color: #FFFFFF;
    selection-background-color: #1976D2;
    selection-color: #FFFFFF;
    min-height: 22px;
}
QLineEdit:focus { border: 2px solid #1976D2; }
QLineEdit[readOnly="true"] {
    background-color: #F5F5F5;
    color: #546E7A;
    border-style: dashed;
}

QSpinBox {
    border: 1px solid #B0BEC5;
    border-radius: 4px;
    padding: 3px 4px;
    background-color: #FFFFFF;
    min-height: 22px;
}
QSpinBox:focus { border: 2px solid #1976D2; }
QSpinBox::up-button, QSpinBox::down-button { border: none; background: transparent; width: 14px; }

QComboBox {
    border: 1px solid #B0BEC5;
    border-radius: 4px;
    padding: 3px 6px;
    background-color: #FFFFFF;
    min-height: 22px;
}
QComboBox:focus { border: 2px solid #1976D2; }
QComboBox::drop-down { border: none; padding-right: 4px; }
QComboBox QAbstractItemView {
    border: 1px solid #B0BEC5;
    background-color: #FFFFFF;
    selection-background-color: #E3F2FD;
    selection-color: #1565C0;
    outline: none;
}

QCheckBox { 
    spacing: 6px; 
    background-color: #FAFAFA;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #B0BEC5;
    border-radius: 3px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #1976D2;
    border-color: #1976D2;
    image: url(__CHECK_PATH__);
}
QCheckBox::indicator:hover {
    border-color: #1976D2;
}
QRadioButton { spacing: 6px; background-color: transparent; }
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #B0BEC5;
    border-radius: 7px;
    background-color: #FFFFFF;
}
QRadioButton::indicator:checked {
    background-color: #1976D2;
    border-color: #1976D2;
    image: url(__RADIO_DOT_PATH__);
}
QRadioButton::indicator:hover {
    border-color: #1976D2;
}

QTabWidget::pane {
    border: 1px solid #CFD8DC;
    background-color: #FFFFFF;
    border-radius: 0 4px 4px 4px;
    top: -1px;
}
QTabBar::tab {
    background-color: #ECEFF1;
    color: #546E7A;
    padding: 6px 14px;
    border: 1px solid #CFD8DC;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
    min-width: 80px;
}
QTabBar::tab:selected        { background-color: #FFFFFF; color: #1565C0; font-weight: 600; }
QTabBar::tab:hover:!selected { background-color: #E3F2FD; color: #1976D2; }

QScrollArea { border: none; background-color: transparent; }
QWidget#clauseContainer { background-color: #FFFFFF; }
QScrollBar:horizontal {
    height: 8px; background-color: #F5F5F5; margin: 0; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #90A4AE; border-radius: 4px; min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background-color: #607D8B; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; height: 0; }
QScrollBar:vertical {
    width: 8px; background-color: #F5F5F5; margin: 0; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #90A4AE; border-radius: 4px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background-color: #607D8B; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { width: 0; height: 0; }

QTableWidget, QTableView {
    gridline-color: #ECEFF1;
    border: 1px solid #CFD8DC;
    border-radius: 4px;
    selection-background-color: #E3F2FD;
    selection-color: #1565C0;
    alternate-background-color: #F5F7F8;
    background-color: #FFFFFF;
}
QHeaderView::section {
    background-color: #ECEFF1;
    color: #37474F;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #CFD8DC;
    border-bottom: 1px solid #B0BEC5;
    font-weight: 600;
}
QHeaderView::section:hover { background-color: #E3F2FD; }

QStatusBar {
    background-color: #1565C0;
    color: #FFFFFF;
    font-size: 9pt;
    padding: 2px 6px;
    min-height: 22px;
}

QProgressBar {
    border: none;
    border-radius: 2px;
    background-color: #E3F2FD;
    text-align: center;
    max-height: 6px;
}
QProgressBar::chunk { background-color: #42A5F5; border-radius: 2px; }

QPlainTextEdit {
    background-color: #FAFAFA;
    border: 1px solid #CFD8DC;
    border-radius: 4px;
}

QLabel#hintLabel {
    color: #78909C;
    font-size: 8pt;
}

QPushButton[prominent="true"] {
    background-color: #1565C0;
    font-size: 10pt;
    letter-spacing: 0.5px;
    border-radius: 4px;
}
QPushButton[prominent="true"]:hover   { background-color: #1976D2; }
QPushButton[prominent="true"]:pressed { background-color: #0D47A1; }

QMenuBar {
    background-color: #ECEFF1;
    color: #212121;
}
QMenuBar::item:selected { background-color: #E3F2FD; color: #1565C0; }
QMenu {
    background-color: #FFFFFF;
    color: #212121;
    border: 1px solid #CFD8DC;
}
QMenu::item:selected { background-color: #E3F2FD; color: #1565C0; }
QMenu::indicator { width: 16px; height: 16px; }
"""

DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #1E1E2E;
}
QWidget {
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 9pt;
    color: #CDD6F4;
    background-color: #1E1E2E;
}

QGroupBox {
    background-color: #2A2A3C;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding-top: 24px;
    margin-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    padding: 4px 8px;
    color: #89B4FA;
    font-weight: bold;
}

QSplitter::handle:vertical   { height: 2px; background-color: #45475A; }
QSplitter::handle:horizontal { width:  2px; background-color: #45475A; }

QPushButton {
    background-color: #1976D2;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 5px 14px;
    font-weight: 600;
    min-height: 26px;
}
QPushButton:hover    { background-color: #2196F3; }
QPushButton:pressed  { background-color: #1565C0; }
QPushButton:disabled { background-color: #45475A; color: #7F849C; }

QPushButton[danger="true"] {
    background-color: transparent;
    color: #F38BA8;
    border: 1px solid #584244;
    border-radius: 4px;
    padding: 3px 10px;
    font-weight: 600;
    min-height: 22px;
}
QPushButton[danger="true"]:hover   { background-color: #3D2B2E; border-color: #F38BA8; }
QPushButton[danger="true"]:pressed { background-color: #4D3033; }

QPushButton[secondary="true"] {
    background-color: #1A2845;
    color: #89B4FA;
    border: 1px solid #2A4A7A;
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 600;
    min-height: 24px;
}
QPushButton[secondary="true"]:hover   { background-color: #1E3252; border-color: #89B4FA; }
QPushButton[secondary="true"]:pressed { background-color: #243C65; }

QLineEdit {
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 4px 8px;
    background-color: #313244;
    color: #CDD6F4;
    selection-background-color: #1976D2;
    selection-color: #FFFFFF;
    min-height: 22px;
}
QLineEdit:focus { border: 2px solid #89B4FA; }
QLineEdit[readOnly="true"] {
    background-color: #262630;
    color: #7F849C;
    border-style: dashed;
}

QSpinBox {
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 3px 4px;
    background-color: #313244;
    color: #CDD6F4;
    min-height: 22px;
}
QSpinBox:focus { border: 2px solid #89B4FA; }
QSpinBox::up-button, QSpinBox::down-button { border: none; background: transparent; width: 14px; }

QComboBox {
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 3px 6px;
    background-color: #313244;
    color: #CDD6F4;
    min-height: 22px;
}
QComboBox:focus { border: 2px solid #89B4FA; }
QComboBox::drop-down { border: none; padding-right: 4px; }
QComboBox QAbstractItemView {
    border: 1px solid #45475A;
    background-color: #313244;
    color: #CDD6F4;
    selection-background-color: #1A3460;
    selection-color: #89B4FA;
    outline: none;
}

QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #B0BEC5;
    border-radius: 3px;
    background-color: #CDD6F4;
}
QCheckBox::indicator:checked {
    background-color: #1976D2;
    border-color: #1976D2;
    image: url(__CHECK_PATH__);
}
QCheckBox::indicator:hover {
    border-color: #1976D2;
}
QRadioButton { spacing: 6px; color: #CDD6F4; background-color: transparent; }
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #B0BEC5;
    border-radius: 7px;
    background-color: #FFFFFF;
}
QRadioButton::indicator:checked {
    background-color: #1976D2;
    border-color: #1976D2;
    image: url(__RADIO_DOT_PATH__);
}
QRadioButton::indicator:hover {
    border-color: #1976D2;
}

QTabWidget::pane {
    border: 1px solid #45475A;
    background-color: #2A2A3C;
    border-radius: 0 4px 4px 4px;
    top: -1px;
}
QTabBar::tab {
    background-color: #1E1E2E;
    color: #7F849C;
    padding: 6px 14px;
    border: 1px solid #45475A;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
    min-width: 80px;
}
QTabBar::tab:selected        { background-color: #2A2A3C; color: #89B4FA; font-weight: 600; }
QTabBar::tab:hover:!selected { background-color: #252538; color: #CDD6F4; }

QScrollArea { border: none; background-color: transparent; }
QWidget#clauseContainer { background-color: #1E1E2E; }
QScrollBar:horizontal {
    height: 8px; background-color: #1E1E2E; margin: 0; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #585B70; border-radius: 4px; min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background-color: #7F849C; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; height: 0; }
QScrollBar:vertical {
    width: 8px; background-color: #1E1E2E; margin: 0; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #585B70; border-radius: 4px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background-color: #7F849C; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { width: 0; height: 0; }

QTableWidget, QTableView {
    gridline-color: #313244;
    border: 1px solid #45475A;
    border-radius: 4px;
    selection-background-color: #1A3460;
    selection-color: #89B4FA;
    alternate-background-color: #262630;
    background-color: #2A2A3C;
    color: #CDD6F4;
}
QHeaderView::section {
    background-color: #313244;
    color: #BAC2DE;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #45475A;
    border-bottom: 1px solid #585B70;
    font-weight: 600;
}
QHeaderView::section:hover { background-color: #1A3460; }

QStatusBar {
    background-color: #11111B;
    color: #CDD6F4;
    font-size: 9pt;
    padding: 2px 6px;
    min-height: 22px;
}

QProgressBar {
    border: none;
    border-radius: 2px;
    background-color: #313244;
    text-align: center;
    max-height: 6px;
}
QProgressBar::chunk { background-color: #89B4FA; border-radius: 2px; }

QPlainTextEdit {
    background-color: #262630;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
}

QLabel#hintLabel {
    color: #7F849C;
    font-size: 8pt;
}

QPushButton[prominent="true"] {
    background-color: #1565C0;
    font-size: 10pt;
    letter-spacing: 0.5px;
    border-radius: 4px;
}
QPushButton[prominent="true"]:hover   { background-color: #1976D2; }
QPushButton[prominent="true"]:pressed { background-color: #0D47A1; }

QMenuBar {
    background-color: #181825;
    color: #CDD6F4;
    border-bottom: 1px solid #45475A;
}
QMenuBar::item:selected { background-color: #313244; color: #89B4FA; }
QMenu {
    background-color: #2A2A3C;
    color: #CDD6F4;
    border: 1px solid #45475A;
}
QMenu::item:selected { background-color: #1A3460; color: #89B4FA; }
QMenu::indicator { width: 16px; height: 16px; }
"""

LIGHT_STYLE = LIGHT_STYLE.replace('__CHECK_PATH__', _CHECK_PATH).replace('__RADIO_DOT_PATH__', _RADIO_DOT_PATH)
DARK_STYLE  = DARK_STYLE.replace('__CHECK_PATH__', _CHECK_PATH).replace('__RADIO_DOT_PATH__', _RADIO_DOT_PATH)

THEMES: dict[str, str] = {
    "light": LIGHT_STYLE,
    "dark":  DARK_STYLE,
}
