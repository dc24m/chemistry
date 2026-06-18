"""
spectra_theme.py — Palette, stylesheet, and shadow helpers for SpectraPlot.

Extracted from spectra_app.py so the theme layer can evolve independently of
the application logic.  spectra_app re-exports every name defined here so
all existing call-sites continue to resolve without modification.
"""

import re
import sys
from functools import lru_cache

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


# ── UI scaling ──────────────────────────────────────────────────────────────────
# Every chrome dimension in the app was tuned on a 1440p (2560×1440) display.
# init_ui_scale() derives one global factor from the actual screen so the
# interface keeps the same screen proportion it had on the design target, and
# s() / build_style(scale=) apply it to Python dimensions and the QSS.
UI_SCALE = 1.0  # set at startup by init_ui_scale()

# Extra zoom applied on top of the auto-detected screen proportion. Bump this
# to make the whole interface larger/smaller without touching anything else.
UI_BOOST = 1.25

# Flat px added to every QSS font-size (before UI_SCALE), so text reads larger
# without enlarging layout dimensions. Raise/lower to taste.
UI_FONT_BOOST = 2


def init_ui_scale(app, base=(2560, 1440)) -> float:
    """Derive a global UI scale from the primary screen vs the 1440p design
    target, so chrome keeps the same screen proportion it had on 1440p, then
    apply UI_BOOST as an overall zoom."""
    global UI_SCALE
    try:
        geo = app.primaryScreen().geometry()
        proportion = min(geo.width() / base[0], geo.height() / base[1])
        UI_SCALE = max(0.75, min(2.5, proportion * UI_BOOST))
    except Exception:
        UI_SCALE = UI_BOOST
    return UI_SCALE


# ── UI font ───────────────────────────────────────────────────────────────────
# The application font stack. set_ui_font() prepends a freshly loaded family
# (e.g. bundled Google Sans) so build_style() and chrome text pick it up.
_FONT_FALLBACK = ("'Segoe UI Variable', 'Segoe UI', 'IBM Plex Sans', 'Inter', "
                  "system-ui, sans-serif")
UI_FONT_FAMILY = _FONT_FALLBACK


def set_ui_font(family: str):
    """Make `family` the primary UI font, keeping the existing stack as fallback.
    Call before the first build_style() so the stylesheet cache picks it up."""
    global UI_FONT_FAMILY
    if family:
        UI_FONT_FAMILY = f"'{family}', {_FONT_FALLBACK}"


def s(px):
    """Scale a 1440p-tuned pixel length by the active UI scale."""
    return round(px * UI_SCALE)


def vs(px):
    """Vertical spacing — s() with an extra 1.25× vertical boost."""
    return round(px * UI_SCALE * 1.25)


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
@lru_cache(maxsize=32)
def build_style(_accent: str, dark: bool = False, scale: float = 1.0) -> str:
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
    ACCENT  = _accent     # per-mode signature color for plotted data defaults
    try:
        _ar, _ag, _ab = to_rgb(ACCENT)
        _alum = 0.2126 * _ar + 0.7152 * _ag + 0.0722 * _ab
        ON_ACCENT = '#111111' if _alum > 0.35 else '#FFFFFF'
    except Exception:
        ON_ACCENT = '#111111'
    # Contrast-safe accent for text on white (or on dark bg in dark mode)
    ACCENT_TEXT = ACCENT if dark else darken(ACCENT, 0.52)
    ON_PRIMARY = '#171717' if dark else '#FFFFFF'
    try:
        _fr, _fg, _fb = [round(c * 255) for c in to_rgb(ACCENT)]
        ACCENT_FILL = f'rgba({_fr},{_fg},{_fb},0.12)'  # faint accent for tab hover
    except Exception:
        ACCENT_FILL = SURF
    FONT = UI_FONT_FAMILY
    qss = f"""
/* ── Global reset ───────────────────────────────────────────────────────── */
* {{
    font-family: {FONT};
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
    padding: 28px 10px 13px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    top: 8px;
    left: 12px;
    padding: 0px;
    background: transparent;
    color: {ACCENT};
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.3px;
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton {{
    background: {SURF2};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 500;
    min-height: 33px;
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
    border-radius: 6px;
    min-height: 26px;
    max-height: 26px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.1px;
}}

/* ── Top header ─────────────────────────────────────────────────────────── */
#topHeader {{
    background: {BG};
    border-bottom: 1px solid {BORDER};
    min-height: 62px;
    max-height: 62px;
}}
#appRoot {{ background: {BG}; }}
QLabel#appTitle {{ color: {INK}; padding: 0 2px; }}
QLabel#brandSub {{ color: {MUTED}; font-size: 12px; font-weight: 400; padding: 0 3px; }}

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
    border-radius: 7px;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 12px;
    min-height: 43px;
    letter-spacing: 0px;
}}
QPushButton#headerTab:hover {{
    color: {INK};
    background: {ACCENT_FILL};
    border-color: {ACCENT};
}}
QPushButton#headerTab:checked {{
    color: #ffffff;
    background: {ACCENT};
    border: 1px solid {ACCENT};
    font-weight: 700;
}}

/* ── Form inputs ────────────────────────────────────────────────────────── */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    color: {INK};
    min-height: 26px;
    selection-background-color: {PRIMARY};
    selection-color: #FFFFFF;
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border: 1px solid {PRIMARY};
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
    selection-color: {ACCENT};
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
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
    color: {MUTED};
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    letter-spacing: 0.2px;
}}
QTabBar::tab:selected {{
    background: {PRIMARY};
    color: {ON_PRIMARY};
    border-color: {PRIMARY};
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
    color: {ACCENT_TEXT};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.8px;
    padding: 3px 2px 5px 2px;
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
    color: {ON_ACCENT};
    border: 1px solid {ACCENT};
    border-radius: 7px;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.4px;
    padding: 0px 16px;
}}
QPushButton#headerPlotBtn:hover {{
    background: {darken(ACCENT, 0.14)};
    border-color: {darken(ACCENT, 0.14)};
    color: {ON_ACCENT};
}}
QPushButton#headerPlotBtn:pressed {{
    background: {darken(ACCENT, 0.28)};
    border-color: {darken(ACCENT, 0.28)};
    color: {ON_ACCENT};
}}

/* ── Theme toggle button ────────────────────────────────────────────────── */
QPushButton#themeToggle {{
    background: {SURF2};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-radius: 7px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    min-width: 58px;
    max-width: 58px;
    min-height: 30px;
    max-height: 30px;
    padding: 0px;
}}
QPushButton#themeToggle:hover {{
    background: {HOVER};
    border-color: {PRIMARY};
    color: {INK};
}}
QPushButton#themeToggle:checked {{
    background: {PRIMARY};
    color: {ON_PRIMARY};
    border-color: {PRIMARY};
}}
QPushButton#settingsBtn {{
    background: {SURF2};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-radius: 7px;
    font-size: 15px;
    padding: 0px;
}}
QPushButton#settingsBtn:hover {{
    background: {HOVER};
    border-color: {PRIMARY};
    color: {INK};
}}
QPushButton#settingsBtn:checked {{
    background: {HOVER};
    border-color: {PRIMARY};
    color: {INK};
}}
QLabel#settingsTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {INK};
}}
QFrame#settingsSep {{
    color: {BORDER};
    background: {BORDER};
    max-height: 1px;
}}
QLabel#settingsHint {{
    font-size: 11px;
    color: {MUTED};
}}
QLabel#scaleLbl {{
    font-size: 13px;
    font-weight: 600;
    color: {PRIMARY};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {SURF2};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {PRIMARY};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: {PRIMARY};
    border-radius: 8px;
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
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
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
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

/* ── Dock widget titles ─────────────────────────────────────────────────── */
QDockWidget::title {{
    background: {SURF};
    border-bottom: 2px solid {ACCENT};
    padding: 7px 10px;
    font-size: 12px;
    font-weight: 600;
    color: {INK};
}}

/* ── Log panel ──────────────────────────────────────────────────────────── */
#logPanel {{ background: {BG}; }}
QPlainTextEdit#logView {{
    background: {BG};
    color: {INK};
    border: none;
    font-family: 'Cascadia Mono', 'Consolas', 'IBM Plex Mono', 'Fira Code', monospace;
    font-size: 11px;
}}

/* ── Message boxes ──────────────────────────────────────────────────────── */
QMessageBox {{ background: {BG}; }}
QMessageBox QLabel {{ color: {INK}; }}
QPushButton#qt_msgbox_buttonbox {{ background: {BG}; }}

/* ── Preset buttons ─────────────────────────────────────────────────────── */
QPushButton#presetBtn {{
    background: {SURF};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    min-height: 26px;
}}
QPushButton#presetBtn:hover {{
    background: {HOVER};
    border-color: {INK};
}}
QPushButton#presetBtn:pressed {{
    background: {SURF};
    color: {MUTED};
}}

/* ── Figure tab bar ─────────────────────────────────────────────────────── */
#figureTabBar {{
    background: {SURF2};
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
}}
QPushButton#figureTab {{
    background: transparent;
    color: {MUTED};
    border: 1px solid transparent;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 20px;
    min-height: 26px;
    min-width: 72px;
    text-align: center;
}}
QPushButton#figureTab:checked {{
    background: {HOVER};
    color: {INK};
    border-color: {BORDER};
}}
QPushButton#figureTab:hover:!checked {{
    color: {INK};
    border-color: {BORDER};
    background: {HOVER};
}}
QPushButton#figureTabClose {{
    background: transparent;
    color: {MUTED};
    border: none;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 4px;
    max-width: 16px;
    min-width: 16px;
}}
QPushButton#figureTabClose:hover {{
    background: {HOVER};
    color: {INK};
}}
QPushButton#figureAddBtn {{
    background: transparent;
    color: {MUTED};
    border: 1px dashed {BORDER};
    border-radius: 5px;
    font-size: 14px;
    font-weight: 400;
    padding: 1px 10px;
    min-height: 24px;
}}
QPushButton#figureAddBtn:hover {{
    color: {INK};
    border-color: {INK};
    border-style: solid;
}}
"""
    # Bump every font-size by a flat amount (layout dimensions untouched) so UI
    # text reads a little larger without changing the overall UI scale.
    if UI_FONT_BOOST:
        qss = re.sub(
            r'(font-size:\s*)(\d+(?:\.\d+)?)px',
            lambda m: f'{m.group(1)}{round(float(m.group(2)) + UI_FONT_BOOST, 2)}px',
            qss)
    if scale != 1.0:
        qss = re.sub(r'(\d+(?:\.\d+)?)px',
                     lambda m: f'{round(float(m.group(1)) * scale, 2)}px', qss)
    return qss


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
