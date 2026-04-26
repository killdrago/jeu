"""
Feuilles de style Qt centralisées — thème terminal sombre.
"""

# Couleurs globales
C_BG         = "#0a0a0a"
C_BG2        = "#0f0f0f"
C_BG3        = "#1a1a1a"
C_GREEN      = "#00ff41"
C_GREEN_DIM  = "#00aa2a"
C_BLUE       = "#00b4ff"
C_YELLOW     = "#ffcc00"
C_RED        = "#ff4444"
C_ORANGE     = "#ff8800"
C_GRAY       = "#444444"
C_GRAY2      = "#2a2a2a"
C_WHITE      = "#e0ffe0"
C_PURPLE     = "#cc88ff"

FONT_MONO    = "Consolas, 'Courier New', monospace"


MAIN_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_GREEN};
    font-family: {FONT_MONO};
    font-size: 13px;
}}

QSplitter::handle {{
    background: {C_GRAY};
    width: 2px;
    height: 2px;
}}

QScrollBar:vertical {{
    background: {C_BG2};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C_GREEN_DIM};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {C_BG2};
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {C_GREEN_DIM};
    border-radius: 4px;
}}

QToolTip {{
    background: {C_BG3};
    color: {C_GREEN};
    border: 1px solid {C_GREEN_DIM};
    padding: 4px;
    font-family: {FONT_MONO};
}}

QMenuBar {{
    background: {C_BG2};
    color: {C_GREEN};
    border-bottom: 1px solid {C_GRAY};
}}
QMenuBar::item:selected {{
    background: {C_GRAY2};
}}
QMenu {{
    background: {C_BG2};
    color: {C_GREEN};
    border: 1px solid {C_GRAY};
}}
QMenu::item:selected {{
    background: {C_GRAY2};
}}
"""

BUTTON_STYLE = f"""
QPushButton {{
    background: {C_BG3};
    color: {C_GREEN};
    border: 1px solid {C_GREEN_DIM};
    border-radius: 3px;
    padding: 5px 12px;
    font-family: {FONT_MONO};
    font-size: 12px;
}}
QPushButton:hover {{
    background: {C_GRAY2};
    border-color: {C_GREEN};
}}
QPushButton:pressed {{
    background: {C_GREEN_DIM};
    color: {C_BG};
}}
QPushButton:disabled {{
    color: {C_GRAY};
    border-color: {C_GRAY};
}}
"""

BUTTON_PRIMARY = f"""
QPushButton {{
    background: {C_GREEN_DIM};
    color: {C_BG};
    border: 1px solid {C_GREEN};
    border-radius: 3px;
    padding: 6px 16px;
    font-family: {FONT_MONO};
    font-size: 12px;
    font-weight: bold;
}}
QPushButton:hover {{
    background: {C_GREEN};
}}
QPushButton:pressed {{
    background: #008020;
}}
QPushButton:disabled {{
    background: {C_GRAY2};
    color: {C_GRAY};
    border-color: {C_GRAY};
}}
"""

BUTTON_DANGER = f"""
QPushButton {{
    background: #3a0000;
    color: {C_RED};
    border: 1px solid {C_RED};
    border-radius: 3px;
    padding: 6px 16px;
    font-family: {FONT_MONO};
    font-size: 12px;
    font-weight: bold;
}}
QPushButton:hover {{
    background: #550000;
}}
QPushButton:pressed {{
    background: #220000;
}}
"""

BUTTON_WARN = f"""
QPushButton {{
    background: #2a2000;
    color: {C_YELLOW};
    border: 1px solid {C_YELLOW};
    border-radius: 3px;
    padding: 6px 16px;
    font-family: {FONT_MONO};
    font-size: 12px;
    font-weight: bold;
}}
QPushButton:hover {{
    background: #3a2a00;
}}
"""

INPUT_STYLE = f"""
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {C_BG2};
    color: {C_WHITE};
    border: 1px solid {C_GRAY};
    border-radius: 3px;
    padding: 4px 8px;
    font-family: {FONT_MONO};
    font-size: 13px;
    selection-background-color: {C_GREEN_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {C_GREEN_DIM};
}}
"""

LABEL_STYLE = f"""
QLabel {{
    color: {C_GREEN};
    font-family: {FONT_MONO};
}}
"""

TAB_STYLE = f"""
QTabWidget::pane {{
    border: 1px solid {C_GRAY};
    background: {C_BG};
}}
QTabBar::tab {{
    background: {C_BG2};
    color: {C_GRAY};
    border: 1px solid {C_GRAY};
    padding: 5px 15px;
    font-family: {FONT_MONO};
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background: {C_BG3};
    color: {C_GREEN};
    border-bottom: 2px solid {C_GREEN};
}}
QTabBar::tab:hover {{
    color: {C_WHITE};
}}
"""

COMBO_STYLE = f"""
QComboBox {{
    background: {C_BG2};
    color: {C_GREEN};
    border: 1px solid {C_GRAY};
    border-radius: 3px;
    padding: 4px 8px;
    font-family: {FONT_MONO};
    font-size: 12px;
}}
QComboBox:hover {{
    border-color: {C_GREEN_DIM};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {C_BG2};
    color: {C_GREEN};
    selection-background-color: {C_GRAY2};
    border: 1px solid {C_GRAY};
}}
"""

STATUS_BAR_STYLE = f"""
QStatusBar {{
    background: {C_BG2};
    color: {C_GREEN_DIM};
    border-top: 1px solid {C_GRAY};
    font-family: {FONT_MONO};
    font-size: 11px;
}}
"""

HEADER_STYLE = f"""
QLabel {{
    color: {C_GREEN};
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 2px;
    padding: 4px;
    background: {C_BG2};
    border-bottom: 1px solid {C_GREEN_DIM};
}}
"""
