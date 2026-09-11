"""
spectra_theme.py — Palette, stylesheet, and shadow helpers for SpectraPlot.

Extracted from spectra_app.py so the theme layer can evolve independently of
the application logic.  spectra_app re-exports every name defined here so
all existing call-sites continue to resolve without modification.
"""

import re
from functools import lru_cache

from matplotlib.colors import to_rgb, to_hex


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
UI_BOOST = 1.0

# Flat px added to every QSS font-size (before UI_SCALE), so text reads larger
# without enlarging layout dimensions. Raise/lower to taste.
UI_FONT_BOOST = 0


def init_ui_scale(app, base=(2560, 1440)) -> float:
    """Qt scales logical pixels for the display DPI; screen dimensions are irrelevant."""
    global UI_SCALE
    UI_SCALE = 1.0
    return UI_SCALE


# ── UI font ───────────────────────────────────────────────────────────────────
# The application font stack. set_ui_font() prepends a freshly loaded family
# so build_style() and chrome text pick it up.
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
    return round(px * UI_SCALE)


# ── Plot modes ──────────────────────────────────────────────────────────────────
# Each mode carries a signature trace accent for plot defaults. The application
# chrome stays monochrome so data color does not compete with the interface.
MODES = [
    {'key': 'pl',         'label': 'Photoluminescence', 'accent': '#F472B6'},
    {'key': 'absorbance', 'label': 'Absorbance',        'accent': '#38BDF8'},
    {'key': 'xrd',        'label': 'XRD',               'accent': '#A78BFA'},
    {'key': 'iv',         'label': 'IV curve',          'accent': '#FBBF24'},
    {'key': 'ta',         'label': 'Transient Abs.',    'accent': '#34D399'},
]
for _m in MODES:
    _m['title'] = darken(_m['accent'], 0.45)
MODE_BY_KEY = {m['key']: m for m in MODES}


# ── Stylesheet ────────────────────────────────────────────────────────────────
@lru_cache(maxsize=32)
def build_style(accent: str, dark: bool = False, scale: float = 1.0) -> str:
    """Restrained chrome with logical-pixel dimensions and explicit focus states.
    The mode accent appears only where it states something: the active mode
    button, a checked checkbox, and the selected list row."""
    if dark:
        BG, SURF, SURF2 = '#202020', '#272727', '#303030'
        INK, MUTED, BORDER, HOVER = '#EEEEEE', '#B8B8B8', '#4D4D4D', '#3B3B3B'
        PRIMARY, ON_PRIMARY, FOCUS = '#DCDCDC', '#202020', '#93B9E3'
        DISABLED = '#909090'
    else:
        BG, SURF, SURF2 = '#FFFFFF', '#F5F5F5', '#EEEEEE'
        INK, MUTED, BORDER, HOVER = '#202020', '#606060', '#CDCDCD', '#E8E8E8'
        PRIMARY, ON_PRIMARY, FOCUS = '#333333', '#FFFFFF', '#376C9E'
        DISABLED = '#777777'
    ACCENT = accent
    ACCENT_TEXT = accent if dark else darken(accent, 0.45)
    _r, _g, _b = (round(c * 255) for c in to_rgb(accent))
    ACCENT_FILL = f'rgba({_r},{_g},{_b},{0.18 if dark else 0.12})'
    qss = f"""
QWidget {{ color: {INK}; font-family: {UI_FONT_FAMILY}; font-size: 13px; }}
QMainWindow, QDialog, #appRoot {{ background: {BG}; }}
#sidebar, #workspacePage {{ background: {SURF}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#hint, QLabel#muted, QLabel#fieldlbl {{ color: {MUTED}; font-size: 12px; }}
QLabel#appTitle {{ font-size: 16px; font-weight: 600; }}
#topHeader {{ background: {SURF}; border-bottom: 1px solid {BORDER}; }}
QGroupBox {{ border: none; margin-top: 20px; padding: 8px 0px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; color: {INK}; }}
QGroupBox#workspaceSection {{ border: none; border-bottom: 1px solid {BORDER}; margin: 0px; padding: 0px 0px 8px 0px; }}
QToolButton#sectionToggle {{ text-align: left; background: transparent; border: none; padding: 5px 2px; font-weight: 600; min-height: 24px; }}
QToolButton#sectionToggle:checked {{ background: transparent; }}
QToolButton#sectionToggle:hover {{ background: {HOVER}; }}
QToolButton#sectionToggle:focus {{ border: 1px solid {FOCUS}; }}
QPushButton, QToolButton {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 3px; padding: 4px 9px; min-height: 22px; }}
QPushButton:hover, QToolButton:hover {{ background: {HOVER}; border-color: {MUTED}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {SURF2}; }}
QPushButton:checked, QToolButton:checked {{ background: {HOVER}; border-color: {MUTED}; }}
QPushButton:focus, QToolButton:focus, QCheckBox:focus {{ border: 1px solid {FOCUS}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {DISABLED}; background: {SURF}; border-color: {BORDER}; }}
QPushButton#headerPlotBtn {{ background: {PRIMARY}; color: {ON_PRIMARY}; border-color: {PRIMARY}; font-weight: 600; padding: 4px 18px; }}
QPushButton#headerPlotBtn:hover {{ background: {MUTED}; }}
QPushButton#headerPlotBtn:focus {{ border: 2px solid {FOCUS}; }}
QPushButton#danger {{ color: {INK}; }}
QPushButton#themeToggle {{ min-width: 38px; }}
QPushButton#headerTab {{ background: transparent; color: {MUTED}; border: 1px solid transparent; padding: 4px 12px; }}
QPushButton#headerTab:hover {{ background: {HOVER}; color: {INK}; }}
QPushButton#headerTab:checked {{ background: {ACCENT_FILL}; border-color: {ACCENT}; color: {ACCENT_TEXT}; font-weight: 600; }}
QPushButton#headerTab:focus {{ border-color: {FOCUS}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {BG}; color: {INK}; border: 1px solid {BORDER}; border-radius: 3px; padding: 4px 6px; min-height: 22px; selection-background-color: {PRIMARY}; selection-color: {ON_PRIMARY}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {FOCUS}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ background: {SURF2}; color: {DISABLED}; }}
QLineEdit {{ placeholder-text-color: {MUTED}; }}
QComboBox {{ padding-right: 20px; }}
QComboBox::drop-down {{ width: 18px; border: none; }}
QComboBox QAbstractItemView {{ background: {BG}; color: {INK}; selection-background-color: {HOVER}; selection-color: {INK}; }}
QCheckBox {{ spacing: 6px; min-height: 24px; background: transparent; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {MUTED}; border-radius: 3px; background: {BG}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox::indicator:disabled {{ background: {SURF2}; border-color: {BORDER}; }}
QListWidget, QPlainTextEdit {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 3px; alternate-background-color: {SURF}; }}
QListWidget::item {{ padding: 5px 4px; }}
QListWidget::item:selected {{ background: {HOVER}; color: {INK}; border: 1px solid {ACCENT}; }}
QListWidget::item:hover {{ background: {SURF2}; }}
QListWidget:focus {{ border-color: {FOCUS}; }}
QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 7px 10px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ background: {BG}; color: {INK}; border-bottom-color: {PRIMARY}; }}
QTabBar::tab:hover {{ background: {HOVER}; color: {INK}; }}
QTabBar::tab:focus {{ border-bottom-color: {FOCUS}; }}
#workspaceTabs > QTabBar::tab {{ min-width: 64px; font-weight: 600; padding: 8px 10px; }}
#figureTabBar {{ background: {SURF}; border-bottom: 1px solid {BORDER}; }}
QPushButton#figureTab {{ background: transparent; border: none; border-radius: 0px; text-align: center; min-height: 22px; padding: 3px 10px; }}
QPushButton#figureTab:checked {{ background: {HOVER}; color: {INK}; }}
QPushButton#figureTabClose {{ border: none; background: transparent; min-height: 18px; padding: 0px; }}
QPushButton#figureTabAdd {{ background: transparent; border: none; padding: 0px 6px; }}
#canvasArea, #canvasCard, #canvasScroll, #canvasHolder {{ background: {SURF2}; border: none; border-radius: 0px; }}
#figToolbar {{ background: {SURF}; border: none; border-bottom: 1px solid {BORDER}; padding: 2px; spacing: 1px; }}
#figToolbar QToolButton, QToolButton#figToolbarBtn {{ background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 2px 5px; min-height: 22px; min-width: 20px; }}
#figToolbar QToolButton:hover, QToolButton#figToolbarBtn:hover {{ background: {HOVER}; border-color: {BORDER}; }}
#figToolbar QToolButton:checked, QToolButton#figToolbarBtn:checked {{ background: {HOVER}; border-color: {MUTED}; }}
#figToolbar QToolButton:focus, QToolButton#figToolbarBtn:focus {{ border-color: {FOCUS}; }}
#figToolbar QLabel {{ color: {MUTED}; font-size: 12px; }}
QMenuBar, QMenu {{ background: {SURF}; color: {INK}; }}
QMenuBar::item {{ padding: 4px 8px; background: transparent; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {HOVER}; }}
QMenu {{ border: 1px solid {BORDER}; }}
QMenu::item {{ padding: 5px 24px; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QToolBar {{ background: {SURF}; border: none; }}
QDockWidget {{ background: {SURF}; border: none; font-weight: 600; }}
QDockWidget::title {{ background: {SURF}; padding: 6px 10px; border-bottom: 2px solid {ACCENT}; }}
QMainWindow::separator {{ background: {BORDER}; width: 4px; height: 4px; }}
QMainWindow::separator:hover {{ background: {MUTED}; }}
QStatusBar, #bottomStatusBar {{ background: {SURF}; border-top: 1px solid {BORDER}; min-height: 24px; }}
QStatusBar::item {{ border: none; }}
#readyDot {{ color: {MUTED}; }}
#coordLabel, #stateLabel {{ font-size: 12px; color: {MUTED}; }}
QToolTip {{ background: {BG}; color: {INK}; border: 1px solid {BORDER}; padding: 5px; }}
"""
    if scale != 1.0:
        qss = re.sub(r'(\d+(?:\.\d+)?)px',
                     lambda m: f'{round(float(m.group(1)) * scale, 2)}px', qss)
    return qss


def add_shadow(widget, blur: int = 0, y: int = 0, alpha: int = 0):
    """Compatibility hook: native workspace surfaces use borders, without shadows."""
    widget.setGraphicsEffect(None)
