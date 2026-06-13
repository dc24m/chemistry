"""
spectra_theme.py — Palette, stylesheet, and shadow helpers for SpectraPlot.

Extracted from spectra_app.py so the theme layer can evolve independently of
the application logic.  spectra_app re-exports every name defined here so
all existing call-sites continue to resolve without modification.
"""

import sys

from matplotlib.colors import to_rgb, to_hex
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


# ── Color helper ────────────────────────────────────────────────────────────────

def darken(hex_color: str, factor: float = 0.45) -> str:
    """Blend a hex color toward black by `factor` (0 = unchanged, 1 = black).
    Used to derive a contrast-safe (WCAG AA) variant of the light mode accents
    for small title text on white, while the bright accent stays for fills."""
    try:
        r, g, b = to_rgb(hex_color)
    except Exception:
        return hex_color
    f = max(0.0, min(1.0, factor))
    r, g, b = (1 - f) * r, (1 - f) * g, (1 - f) * b
    return to_hex((r, g, b))


# ── Plot modes ──────────────────────────────────────────────────────────────────
# Each mode carries a signature trace accent for plot defaults. The application
# chrome stays monochrome so data color does not compete with the interface.
MODES = [
    {'key': 'pl',         'label': 'Photoluminescence', 'accent': '#F472B6'},
    {'key': 'absorbance', 'label': 'Absorbance',        'accent': '#38BDF8'},
    {'key': 'xrd',        'label': 'XRD',               'accent': '#A78BFA'},
    {'key': 'iv',         'label': 'IV curve',          'accent': '#FBBF24'},
]
for _m in MODES:
    _m['title'] = darken(_m['accent'], 0.45)
MODE_BY_KEY = {m['key']: m for m in MODES}


# ── Stylesheet ────────────────────────────────────────────────────────────────
def build_style(_accent: str, dark: bool = False) -> str:
    if dark:
        BG       = '#1E1E1E'
        SURF     = '#252526'
        SURF2    = '#2D2D2D'
        INK      = '#D4D4D4'
        MUTED    = '#9D9D9D'
        PRIMARY  = '#CCCCCC'
        BORDER   = '#3E3E42'
        HOVER    = '#2A2D2E'
        DISABLED = '#6A6A6A'
        TBAR_BG  = '#303030'
        TBAR_BTN = '#3A3A3A'
        TBAR_BRD = '#505050'
    else:
        BG       = '#FFFFFF'
        SURF     = '#F7F7F7'
        SURF2    = '#EDEDED'
        INK      = '#171717'
        MUTED    = '#5F5F5F'
        PRIMARY  = '#2F2F2F'
        BORDER   = '#DADADA'
        HOVER    = '#E8E8E8'
        DISABLED = '#A8A8A8'
        TBAR_BG  = '#2A2A2A'
        TBAR_BTN = '#3C3C3C'
        TBAR_BRD = '#4A4A4A'
    ACCENT  = _accent     # per-mode signature color for checked/active states
    return f"""
/* ── Global reset ───────────────────────────────────────────────────────── */
* {{
    font-family: 'Segoe UI Variable', 'Segoe UI', 'IBM Plex Sans', 'Inter', system-ui, sans-serif;
    font-size: 12px;
    color: {INK};
}}

/* ── Window & root ──────────────────────────────────────────────────────── */
QMainWindow {{ background: {BG}; }}
#appFrame, #appRoot {{ background: {BG}; }}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
#sidebar {{ background: {SURF}; border-right: 1px solid {BORDER}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea > QWidget {{ background: transparent; }}

/* ── Group boxes ────────────────────────────────────────────────────────── */
QGroupBox {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 0px;
    padding: 34px 12px 12px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    top: 10px;
    left: 12px;
    padding: 0px;
    background: transparent;
    color: {INK};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton {{
    background: {SURF2};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
    letter-spacing: 0.1px;
}}
QPushButton:hover {{
    background: {HOVER};
    border-color: {PRIMARY};
    color: {INK};
}}
QPushButton:pressed {{ background: {BORDER}; border-color: {PRIMARY}; }}
QPushButton:disabled {{
    background: {SURF};
    color: {DISABLED};
    border-color: {SURF2};
}}

QPushButton#secondary {{
    background: {BG};
    color: {MUTED};
    border: 1px solid {BORDER};
    font-size: 12px;
    font-weight: 500;
    min-height: 28px;
}}
QPushButton#secondary:hover {{
    background: {SURF};
    border-color: {PRIMARY};
    color: {INK};
}}

QPushButton#danger {{
    background: #FEF2F2;
    color: #B91C1C;
    border: 1px solid #FECACA;
    font-size: 12px;
    font-weight: 500;
    min-height: 28px;
    padding: 3px 10px;
}}
QPushButton#danger:hover {{
    background: #FEE2E2;
    border-color: #F87171;
    color: #991B1B;
}}

QPushButton#colorpick {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    min-height: 32px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}

/* ── Top header ─────────────────────────────────────────────────────────── */
#topHeader {{
    background: {BG};
    border-bottom: 1px solid {BORDER};
    min-height: 78px;
    max-height: 78px;
}}
#appRoot {{ background: {BG}; }}
QLabel#appTitle {{ color: {INK}; padding: 0 2px; }}
QLabel#brandSub {{ color: {MUTED}; font-size: 13px; font-weight: 500; padding: 0 3px; }}

/* ── Loading screen ─────────────────────────────────────────────────────── */
#loadingScreen {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
#loadingTitle {{ color: {INK}; font-size: 26px; font-weight: 800; }}
#loadingSubtitle {{
    color: {MUTED};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.8px;
}}
#loadingStatus {{ color: {INK}; font-size: 13px; font-weight: 500; }}
#loadingProgress {{
    min-height: 6px; max-height: 6px;
    border: none; border-radius: 3px;
    background: {SURF2};
}}
#loadingProgress::chunk {{ border-radius: 3px; background: {ACCENT}; }}

/* ── Mode tabs ──────────────────────────────────────────────────────────── */
QPushButton#headerTab {{
    background: {BG};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    padding: 0px 18px;
    min-height: 46px;
    letter-spacing: 0.1px;
}}
QPushButton#headerTab:hover {{
    color: {INK};
    background: {SURF};
    border-color: #BDBDBD;
}}
QPushButton#headerTab:checked {{
    color: #171717;
    background: {ACCENT};
    border: 1px solid {ACCENT};
    font-weight: 700;
}}

/* ── Form inputs ────────────────────────────────────────────────────────── */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    color: {INK};
    min-height: 30px;
    selection-background-color: {PRIMARY};
    selection-color: #FFFFFF;
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border: 2px solid {ACCENT};
    background: {BG};
    color: {INK};
}}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {{
    background: {SURF2};
    color: {DISABLED};
    border-color: {SURF2};
}}
QCheckBox:disabled {{ color: {DISABLED}; }}
QCheckBox::indicator:disabled {{ background: {SURF2}; border-color: {SURF2}; }}
QLabel:disabled {{ color: {DISABLED}; }}
QComboBox::drop-down {{ width: 18px; border: none; }}
QComboBox QAbstractItemView {{
    background: {BG};
    border: 1px solid {BORDER};
    color: {INK};
    selection-background-color: {SURF};
    selection-color: {PRIMARY};
    outline: none;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 12px; border: none; background: {SURF};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {SURF2};
}}
QLineEdit::placeholder {{ color: {DISABLED}; }}

/* ── File list ──────────────────────────────────────────────────────────── */
QListWidget {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG};
    font-size: 13px;
    color: {INK};
    outline: none;
    padding: 3px;
}}
QListWidget::item {{ padding: 5px 9px; border-radius: 5px; }}
QListWidget::item:selected {{
    background: {SURF};
    color: {INK};
    border: 1px solid {ACCENT};
    padding: 4px 8px;
}}
QListWidget::item:hover {{ background: {SURF}; color: {INK}; }}

/* ── Checkboxes ─────────────────────────────────────────────────────────── */
QCheckBox {{ font-size: 12px; color: {MUTED}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid #BDBDBD;
    border-radius: 4px;
    background: {BG};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}

/* ── Inner data tabs ────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: {BG};
    border-radius: 0;
}}
QTabBar::tab {{
    background: {SURF};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 600;
    color: {MUTED};
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    letter-spacing: 0.2px;
}}
QTabBar::tab:selected {{
    background: {ACCENT};
    color: #171717;
    border-color: {ACCENT};
}}

/* ── Canvas area ────────────────────────────────────────────────────────── */
#rightPane, #canvasArea, #canvasScroll, #canvasHolder {{ background: {'#1E1E1E' if dark else '#EBEBEB'}; }}
#canvasCard {{
    background: {'#2A2A2A' if dark else '#D8D8D8'};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

/* ── Bottom control dock ────────────────────────────────────────────────── */
#dock {{ background: {BG}; }}
#dockCard {{
    background: {SURF};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#dockTitle {{
    color: {PRIMARY};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.8px;
    padding: 2px 2px 4px 2px;
}}

/* ── Figure toolbar ─────────────────────────────────────────────────────── */
#figToolbar {{
    background: {TBAR_BG};
    border: 1px solid #1A1A1A;
    border-radius: 10px;
    padding: 5px 7px;
    spacing: 3px;
}}
#figToolbar QToolButton, QToolButton#figToolbarBtn {{
    background: {TBAR_BTN};
    border: 1px solid {TBAR_BRD};
    border-radius: 6px;
    min-width: 32px;
    min-height: 28px;
    padding: 2px 7px;
    margin: 1px;
    color: #E8E8E8;
    font-size: 12px;
    font-weight: 500;
}}
#figToolbar QToolButton:hover, QToolButton#figToolbarBtn:hover {{
    background: #505050;
    border-color: #666666;
    color: #FFFFFF;
}}
#figToolbar QToolButton:pressed, QToolButton#figToolbarBtn:pressed {{
    background: #242424;
    border-color: #333333;
}}
#figToolbar QToolButton:checked, QToolButton#figToolbarBtn:checked {{
    background: #F0F0F0;
    border-color: #D0D0D0;
    color: #1A1A1A;
}}
#figToolbar QToolButton:disabled, QToolButton#figToolbarBtn:disabled {{
    background: #303030;
    color: #606060;
    border-color: #383838;
}}
#figToolbar QLabel {{ color: #CCCCCC; font-size: 12px; }}
#figToolbar QLabel#muted {{ color: #888888; }}

/* ── Header Plot button (prominent, accent-filled) ──────────────────────── */
QPushButton#headerPlotBtn {{
    background: {ACCENT};
    color: #171717;
    border: 1px solid {ACCENT};
    border-radius: 10px;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 3px;
    padding: 0px 22px;
}}
QPushButton#headerPlotBtn:hover {{
    background: {darken(ACCENT, 0.12)};
    border-color: {darken(ACCENT, 0.12)};
    color: #FFFFFF;
}}
QPushButton#headerPlotBtn:pressed {{
    background: {darken(ACCENT, 0.25)};
    border-color: {darken(ACCENT, 0.25)};
    color: #FFFFFF;
}}

/* ── Theme toggle button ────────────────────────────────────────────────── */
QPushButton#themeToggle {{
    background: {SURF2};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    min-width: 64px;
    max-width: 64px;
    min-height: 32px;
    max-height: 32px;
    padding: 0px;
}}
QPushButton#themeToggle:hover {{
    background: {HOVER};
    border-color: {PRIMARY};
    color: {INK};
}}
QPushButton#themeToggle:checked {{
    background: {ACCENT};
    color: #FFFFFF;
    border-color: {ACCENT};
}}

/* ── Bottom status bar ──────────────────────────────────────────────────── */
#bottomStatusBar {{
    background: {SURF};
    border-top: 1px solid {BORDER};
    min-height: 26px;
}}
#readyDot {{ color: #22C55E; font-size: 11px; font-weight: 700; }}
#stateLabel {{ font-weight: 600; color: {INK}; font-size: 12px; }}
#coordLabel {{
    font-size: 11px;
    color: {MUTED};
    font-family: 'Cascadia Mono', 'Consolas', 'IBM Plex Mono', 'Fira Code', 'Courier New', monospace;
}}

/* ── Splitter ───────────────────────────────────────────────────────────── */
QSplitter::handle:horizontal {{ background: {BORDER}; width: 1px; }}
QSplitter::handle:vertical {{
    background: {BORDER};
    height: 4px;
    margin: 0 4px;
}}
QSplitter::handle:vertical:hover {{ background: #AFAFAF; }}

/* ── Dialogs ────────────────────────────────────────────────────────────── */
QDialog {{ background: {BG}; }}
QDialog QLabel {{ color: {INK}; }}
QFormLayout QLabel {{ color: {MUTED}; font-size: 13px; }}

/* ── Label variants ─────────────────────────────────────────────────────── */
QLabel#muted {{ font-size: 11px; color: #7A7A7A; letter-spacing: 0.5px; }}
QLabel#hint {{ font-size: 12px; color: {MUTED}; font-style: italic; }}
QLabel#fieldlbl {{ font-size: 13px; color: {MUTED}; font-weight: 600; letter-spacing: 0.2px; }}

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {SURF};
    width: 6px;
    border-radius: 3px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: #BDBDBD;
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    background: {SURF};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: #BDBDBD;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{ background: {MUTED}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

/* ── Message boxes ──────────────────────────────────────────────────────── */
QMessageBox {{ background: {BG}; }}
QMessageBox QLabel {{ color: {INK}; }}
QPushButton#qt_msgbox_buttonbox {{ background: {BG}; }}
"""


# ── Shadow helper ─────────────────────────────────────────────────────────────
def add_shadow(widget, blur: int = 24, y: int = 6, alpha: int = 35):
    """Apply a soft drop shadow for Soft-UI depth. A widget can hold only one
    QGraphicsEffect, so never stack — the last call wins.
    Skipped on macOS: QGraphicsDropShadowEffect corrupts the compositing layer there."""
    if sys.platform == 'darwin':
        return
    sh = QGraphicsDropShadowEffect(widget)
    sh.setBlurRadius(blur)
    sh.setOffset(0, y)
    sh.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(sh)
