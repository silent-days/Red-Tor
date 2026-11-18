"""Red Tor - Privacy Dashboard theme (Tor-onion red + clean white).

Inspired by the Tor onion: warm white surfaces, deep slate text, and a
signature red brand accent (#E01414) used for the logo, active sidebar
items, primary CTAs, and light console and chart surfaces
that contrast against the light theme. App name: Red Tor.
"""
from PyQt5.QtGui import QColor, QPalette, QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication

# ---- Tor onion red palette ----
NIGHT        = "#F5F5F7"   # main background (very light gray)
NIGHT_2      = "#FFFFFF"   # panels / cards (pure white)
NIGHT_3      = "#EFEFF2"   # raised surfaces / groups
ICE          = "#E4E4E8"   # borders / input backgrounds
ICE_LIGHT    = "#D8D8DD"
FROST        = "#111111"   # primary text (near-black)
FROST_DIM    = "#6B6B73"   # muted text
GLACIER      = "#A0A0A8"   # disabled / hint

# Signature Tor onion red (the only brand accent)
VIOLET       = "#E01414"   # primary brand (Tor onion red)
VIOLET_DARK  = "#B71010"
VIOLET_LIGHT = "#F24848"

# Secondary accents (used sparingly)
TEAL         = "#E01414"   # alias - red is the only accent
TEAL_DARK    = "#B71010"
GREEN_OK     = "#22A045"   # success (status cards, terminal [+])
RED_OFF      = "#E01414"   # = brand red
RED_HARD     = "#B71010"
AMBER        = "#E89A0C"   # warning (terminal [!])
BLUE_INFO    = "#2563EB"

# Convenience aliases (kept for compat with old code that imported CREAM etc.)
CREAM        = NIGHT
CREAM_LIGHT  = NIGHT_2
CREAM_DARK   = NIGHT_3
TAN          = ICE
TAN_DARK     = ICE_LIGHT
DARK_TEXT    = FROST
MUTED        = FROST_DIM
PURPLE       = VIOLET
PURPLE_DARK  = VIOLET_DARK
PURPLE_LIGHT = VIOLET_LIGHT
PURPLE_PALE  = "#FDE7E7"   # very light red tint for cards / hovers


# Classic UI font: bundled Inter (clean modern sans, the z.ai-style look)
# with graceful fallbacks for systems where the bundle is absent.
FONT_STACK = ["Inter", "Segoe UI", "Noto Sans", "DejaVu Sans", "sans-serif"]

MONO_STACK = ["DejaVu Sans Mono", "Liberation Mono", "monospace"]


def register_bundled_fonts():
    """Load the bundled Inter TTFs from assets/fonts (idempotent)."""
    import os
    import glob
    fonts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets", "fonts")
    fonts_dir = os.path.normpath(fonts_dir)
    if os.path.isdir(fonts_dir):
        for path in sorted(glob.glob(os.path.join(fonts_dir, "*.ttf"))):
            QFontDatabase.addApplicationFont(path)


def app_font() -> QFont:
    """The classic app-wide font with the full fallback chain."""
    font = QFont()
    if hasattr(font, "setFamilies"):        # Qt >= 5.13
        font.setFamilies(FONT_STACK)
    else:
        font.setFamily(FONT_STACK[0])
    font.setPointSize(10)
    return font


def apply_classic_theme(app: QApplication):
    """Apply the Tor-onion red + white theme."""
    register_bundled_fonts()
    app.setFont(app_font())
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(NIGHT))
    pal.setColor(QPalette.WindowText,      QColor(FROST))
    pal.setColor(QPalette.Base,            QColor(NIGHT_2))
    pal.setColor(QPalette.AlternateBase,   QColor(NIGHT_3))
    pal.setColor(QPalette.Text,            QColor(FROST))
    pal.setColor(QPalette.Button,          QColor(NIGHT_2))
    pal.setColor(QPalette.ButtonText,      QColor(FROST))
    pal.setColor(QPalette.Highlight,       QColor(PURPLE_PALE))
    pal.setColor(QPalette.HighlightedText, QColor(FROST))
    pal.setColor(QPalette.ToolTipBase,     QColor(NIGHT_2))
    pal.setColor(QPalette.ToolTipText,     QColor(FROST))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor(GLACIER))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(GLACIER))
    app.setPalette(pal)
    app.setStyleSheet(_STYLESHEET)


_STYLESHEET = f"""
QMainWindow, QWidget {{ background-color: {NIGHT}; color: {FROST}; }}

QMenuBar {{
    background-color: {NIGHT_2};
    color: {FROST};
    border-bottom: 1px solid {ICE_LIGHT};
    padding: 4px;
    font-weight: 500;
    font-size: 10pt;
}}
QMenuBar::item {{ padding: 6px 14px; background: transparent; border-radius: 3px; color: {FROST}; }}
QMenuBar::item:selected {{ background: {PURPLE_PALE}; color: {VIOLET_DARK}; }}

QMenu {{
    background-color: {NIGHT_2};
    border: 1px solid {ICE_LIGHT};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 16px; border-radius: 4px; color: {FROST}; }}
QMenu::item:selected {{ background: {PURPLE_PALE}; color: {VIOLET_DARK}; }}
QMenu::separator {{ height: 1px; background: {ICE}; margin: 4px 8px; }}

QTabWidget::pane {{
    border: none;
    background: {NIGHT};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {FROST_DIM};
    padding: 10px 22px;
    border: none;
    border-bottom: 3px solid transparent;
    margin-right: 1px;
    font-weight: 500;
    font-size: 10pt;
}}
QTabBar::tab:selected {{
    background: transparent;
    color: {VIOLET_DARK};
    border-bottom: 3px solid {VIOLET};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {FROST};
    border-bottom: 3px solid {ICE_LIGHT};
}}

QPushButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {NIGHT_2}, stop:1 {NIGHT_3});
    color: {FROST};
    border: 1px solid {ICE_LIGHT};
    border-bottom: 2px solid {ICE_LIGHT};
    padding: 8px 16px;
    border-radius: 6px;
    min-height: 22px;
    font-weight: 500;
    font-size: 10pt;
}}
QPushButton:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {NIGHT_2}, stop:0.7 {PURPLE_PALE});
    border-color: {VIOLET_LIGHT};
    border-bottom-color: {VIOLET_LIGHT};
    color: {VIOLET_DARK};
}}
QPushButton:pressed {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {NIGHT_3}, stop:1 {NIGHT_2});
    border-bottom-width: 0px;
    padding-top: 9px;
    color: {FROST};
    border-color: {VIOLET};
}}
QPushButton:default {{ border: 1px solid {VIOLET}; color: {FROST}; }}
QPushButton:checked {{ background-color: {PURPLE_PALE}; color: {FROST}; border-color: {VIOLET}; }}
QPushButton:disabled {{ color: {GLACIER}; background: {NIGHT_3}; border-color: {ICE}; }}

/* Primary CTA button (objectName == "primaryBtn"): raised red pill with a
   glowing bottom edge; pressed sinks it into the surface. */
QPushButton#primaryBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {VIOLET_LIGHT}, stop:1 {VIOLET});
    color: #FFFFFF;
    border: 1px solid {VIOLET_DARK};
    border-bottom: 3px solid {VIOLET_DARK};
    padding: 10px 22px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 11pt;
}}
QPushButton#primaryBtn:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {VIOLET}, stop:1 {VIOLET_LIGHT});
    border-bottom-color: {RED_HARD};
}}
QPushButton#primaryBtn:pressed {{
    background-color: {VIOLET_DARK};
    border-bottom-width: 1px;
    padding-top: 12px;
    color: #FFFFFF;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {NIGHT_2};
    border: 1px solid {ICE_LIGHT};
    padding: 6px 10px;
    border-radius: 6px;
    color: {FROST};
    selection-background-color: {PURPLE_PALE};
    selection-color: {FROST};
    font-size: 10pt;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {VIOLET};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {NIGHT_2};
    border: 1px solid {ICE_LIGHT};
    selection-background-color: {PURPLE_PALE};
    selection-color: {FROST};
    color: {FROST};
}}

QGroupBox {{
    border: 1px solid {ICE_LIGHT};
    border-radius: 10px;
    margin-top: 12px;
    padding: 14px 10px 10px 10px;
    background-color: {NIGHT_2};
    font-weight: 600;
    color: {FROST};
    font-size: 10pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 8px;
    background: {NIGHT};
    color: {VIOLET_DARK};
}}

QProgressBar {{
    border: 1px solid {ICE_LIGHT};
    border-radius: 6px;
    background: {NIGHT_3};
    text-align: center;
    height: 18px;
    color: {FROST};
    font-weight: 600;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 {VIOLET_LIGHT}, stop:1 {VIOLET});
    border-radius: 1px;
}}

QTableWidget {{
    background-color: {NIGHT_2};
    alternate-background-color: {NIGHT_3};
    gridline-color: {ICE};
    selection-background-color: {PURPLE_PALE};
    selection-color: {FROST};
    border: 1px solid {ICE_LIGHT};
    border-radius: 6px;
    color: {FROST};
}}
QTableWidget::item {{ padding: 5px 8px; }}
QHeaderView::section {{
    background-color: {NIGHT_3};
    color: {VIOLET_DARK};
    padding: 8px 6px;
    border: none;
    border-right: 1px solid {ICE};
    font-weight: 600;
    font-size: 10pt;
}}

QScrollBar:vertical {{
    background: {NIGHT_3};
    width: 14px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {ICE_LIGHT};
    border-radius: 6px;
    min-height: 28px;
    margin: 1px;
}}
QScrollBar::handle:vertical:hover {{ background: {VIOLET_LIGHT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: {NIGHT_3};
    height: 14px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {ICE_LIGHT};
    border-radius: 6px;
    min-width: 28px;
    margin: 1px;
}}
QScrollBar::handle:horizontal:hover {{ background: {VIOLET_LIGHT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ background: none; width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QStatusBar {{
    background-color: {NIGHT_3};
    color: {FROST_DIM};
    border-top: 1px solid {ICE_LIGHT};
    padding: 3px 10px;
    font-weight: 500;
    font-size: 9pt;
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {FROST_DIM}; }}

QLabel {{ color: {FROST}; }}
QCheckBox {{ color: {FROST}; spacing: 6px; font-size: 10pt; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {ICE_LIGHT};
    background: {NIGHT_2};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background: {VIOLET};
    border-color: {VIOLET_DARK};
}}

QFrame[frameShape="6"] {{ color: {ICE_LIGHT}; }}

QToolTip {{
    background-color: {NIGHT_2};
    color: {VIOLET_DARK};
    border: 1px solid {ICE_LIGHT};
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 9pt;
}}

QSplitter::handle {{ background: {ICE}; }}
QSplitter::handle:hover {{ background: {VIOLET_LIGHT}; }}

QDialog {{ background-color: {NIGHT}; }}

/* Sidebar nav item (objectName == "navBtn") */
QPushButton#navBtn {{
    text-align: left;
    background: transparent;
    border: none;
    color: {FROST};
    padding: 10px 14px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 10pt;
}}
QPushButton#navBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {NIGHT_3}, stop:1 {NIGHT_2});
    color: {FROST};
    padding-left: 18px;
}}
QPushButton#navBtn:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {PURPLE_PALE}, stop:1 {NIGHT_2});
    color: {FROST};
    border-left: 3px solid {VIOLET};
    padding-left: 16px;
    font-weight: 600;
}}

/* Card style (objectName == "card"): raised white panel over the app bg. */
QFrame#card {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 {NIGHT_2}, stop:1 {NIGHT_3});
    border: 1px solid {ICE_LIGHT};
    border-radius: 12px;
}}
"""
