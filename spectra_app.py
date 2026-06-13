#!/usr/bin/env python3
"""
SpectraPlot — Chemistry Spectrometry Plotting Tool
PL · Absorbance · XRD
"""

import sys
import os
import re

try:
    import numpy as np

    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    from matplotlib.figure import Figure
    from matplotlib.colors import to_rgb, to_hex
    from matplotlib.ticker import ScalarFormatter, FuncFormatter

    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QAbstractSpinBox, QCheckBox, QLineEdit, QFileDialog, QScrollArea,
        QGroupBox, QColorDialog, QMessageBox, QListWidget, QListWidgetItem,
        QAbstractItemView, QSplitter, QTabWidget, QGridLayout,
        QSizePolicy, QDialog, QDialogButtonBox, QFormLayout,
        QButtonGroup, QSplashScreen, QProgressBar, QGraphicsDropShadowEffect,
        QToolButton, QFrame, QSlider,
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QSize
    from PyQt6.QtGui import (QFont, QColor, QCursor, QPixmap, QFontDatabase,
                              QUndoStack, QUndoCommand, QKeySequence, QShortcut)
except ModuleNotFoundError as exc:
    missing = exc.name or 'a required package'
    raise SystemExit(
        f"SPECTRAplot could not start because '{missing}' is not installed for:\n"
        f"  {sys.executable}\n\n"
        "Install the app dependencies with:\n"
        "  python -m pip install -r requirements_spectra.txt"
    ) from exc

matplotlib.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'Liberation Sans'],
    'axes.unicode_minus': False,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'savefig.facecolor': 'white',
})


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
_APP_DARK = False   # global dark-mode state toggled by the header button


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


# ── Utilities ─────────────────────────────────────────────────────────────────

# Line-style options shared by the trace editor and the plotting code.
LINESTYLE_LABELS = ['solid', 'dashed', 'dotted', 'dash-dot']
LINESTYLE_MAP = {'solid': '-', 'dashed': '--', 'dotted': ':', 'dash-dot': '-.'}
IV_SET_COLORS = [
    '#0072B2', '#D55E00', '#009E73', '#CC79A7', '#56B4E9',
    '#E69F00', '#332288', '#88CCEE', '#117733', '#882255',
]
_FILE_CACHE = {}


def clear_file_cache():
    _FILE_CACHE.clear()


def _load_cached(kind: str, path: str, parser):
    try:
        stat = os.stat(path)
    except OSError:
        return None, None

    cache_key = (kind, os.path.abspath(path))
    signature = (stat.st_mtime_ns, stat.st_size)
    cached = _FILE_CACHE.get(cache_key)
    if cached and cached[0] == signature:
        return cached[1]

    result = parser(path)
    _FILE_CACHE[cache_key] = (signature, result)
    return result


def clean_label(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = name.replace('_', ' ')
    name = re.sub(r'([A-Za-z])(\d)', r'\1 \2', name)
    return name


def make_trace(path: str) -> dict:
    """Build a per-trace customization record from a file path."""
    return {
        'path': path,
        'display_name': clean_label(os.path.basename(path)),
        'color': '#000000',       # MATLAB-black default
        'use_auto_gradient_color': True,
        'visible': True,
        'linewidth': None,        # None = inherit global line width
        'linestyle': 'solid',
    }


def load_file(path: str):
    """
    Robustly load a 2-column spectroscopy file.
    Handles any number of header rows, any delimiter, and European decimals.
    Returns (x, y) arrays or (None, None) on failure.
    """
    return _load_cached('spectra', path, _parse_spectra_file)


def _parse_spectra_file(path: str):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            xs, ys = [], []
            for line in f:
                line = line.strip()
                if not line or line[0] in '#%!':
                    continue
                if ';' in line or '\t' in line:
                    parts = re.split(r'[;\t]+', line)
                    parts = [p.strip() for p in parts if p.strip()]
                    fix = lambda s: s.replace(',', '.')
                else:
                    parts = re.split(r'[,\s]+', line)
                    parts = [p for p in parts if p]
                    fix = lambda s: s
                if len(parts) < 2:
                    continue
                try:
                    x = float(fix(parts[0]))
                    y = float(fix(parts[1]))
                except ValueError:
                    continue
                if np.isfinite(x) and np.isfinite(y):
                    xs.append(x)
                    ys.append(y)
    except Exception:
        return None, None

    return (np.array(xs), np.array(ys)) if len(xs) >= 2 else (None, None)


def sort_iv_files_by_under_value(files: list[str]) -> list[str]:
    """Sort IV filenames by the number after 'under', descending.

    Files without an under### token are placed last.
    """
    def key(path: str):
        name = os.path.basename(path)
        match = re.search(r'under(\d+)', name, flags=re.IGNORECASE)
        if not match:
            return (1, 0, name.lower())
        return (0, -int(match.group(1)), name.lower())

    return sorted(files, key=key)


def load_iv_csv(path: str):
    """Load Keithley IV CSV data: column 3 = voltage, column 4 = current in A."""
    return _load_cached('iv', path, _parse_iv_csv)


def _parse_iv_csv(path: str):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            voltages, currents = [], []
            for line in f:
                line = line.strip()
                if not line or line[0] in '#%!':
                    continue
                if any(ch in line for ch in ',;\t'):
                    parts = re.split(r'[,;\t]+', line)
                else:
                    parts = re.split(r'\s+', line)
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) < 4:
                    continue
                try:
                    voltage = float(parts[2])
                    current = float(parts[3])
                except ValueError:
                    continue
                if np.isfinite(voltage) and np.isfinite(current):
                    voltages.append(voltage)
                    currents.append(current)
    except Exception:
        return None, None

    if not voltages:
        return None, None
    return np.array(voltages), np.array(currents)


def choose_iv_current_unit(max_abs_current: float) -> tuple[float, str]:
    if not np.isfinite(max_abs_current) or max_abs_current == 0:
        return 1.0, 'A'
    if max_abs_current < 1e-9:
        return 1e12, 'pA'
    if max_abs_current < 1e-6:
        return 1e9, 'nA'
    if max_abs_current < 1e-3:
        return 1e6, 'µA'
    if max_abs_current < 1:
        return 1e3, 'mA'
    return 1.0, 'A'


def clean_iv_label(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace('_', ' ')


def validate_iv_sets(iv_sets: list[dict]) -> str | None:
    if not iv_sets:
        return 'Add at least one IV data set before plotting.'
    for idx, data_set in enumerate(iv_sets, start=1):
        neg_paths, pos_paths = _iv_sweep_paths(data_set)
        if len(neg_paths) != 1 or len(pos_paths) != 1:
            return f'Set {idx} requires both IV scan groups (-20 to 0 V and 0 to 20 V).'
    return None


def _iv_sweep_paths(data_set: dict) -> tuple[list[str], list[str]]:
    def paths(single_key: str, legacy_key: str) -> list[str]:
        single = str(data_set.get(single_key, '') or '').strip()
        if single:
            return [single]
        return [
            str(path).strip()
            for path in data_set.get(legacy_key, [])
            if str(path).strip()
        ]

    return paths('neg_path', 'neg_paths'), paths('pos_path', 'pos_paths')


def make_gradient(c1_hex: str, c2_hex: str, n: int) -> list:
    if n <= 0:
        return []
    try:
        c1 = np.array(to_rgb(c1_hex))
        c2 = np.array(to_rgb(c2_hex))
    except Exception:
        c1 = np.array([0.2, 0.2, 0.2])
        c2 = np.array([0.7, 0.7, 0.7])
    if n == 1:
        return [tuple(c1)]
    return [tuple(c1 + t * (c2 - c1)) for t in np.linspace(0, 1, n)]


def two_theta_to_d(two_theta_deg, lam=1.5406, n=1):
    theta_rad = np.deg2rad(np.asarray(two_theta_deg, dtype=float) / 2.0)
    with np.errstate(divide='ignore', invalid='ignore'):
        d = np.where(np.sin(theta_rad) > 1e-9,
                     n * lam / (2.0 * np.sin(theta_rad)), np.nan)
    return d


# ── Spin boxes without arrows and without wheel-scroll ───────────────────────

class FlatSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class FlatDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class NoScrollComboBox(QComboBox):
    """ComboBox that ignores wheel events so scrolling doesn't change the value."""
    def wheelEvent(self, event):
        event.ignore()


# ── Color picker button ───────────────────────────────────────────────────────

class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, hex_color='#EC5381', parent=None):
        super().__init__(parent)
        self.setObjectName('colorpick')
        self._hex = hex_color
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self):
        try:
            r, g, b = [int(v * 255) for v in to_rgb(self._hex)]
        except Exception:
            r, g, b = 180, 180, 180
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        txt = '#fff' if luma < 140 else '#222'
        self.setStyleSheet(
            f'QPushButton#colorpick {{ background:{self._hex}; color:{txt}; '
            f'border:1px solid rgba(0,0,0,0.18); border-radius:7px; '
            f'min-height:32px; font-size:12px; font-weight:700; }}'
        )
        self.setText(self._hex.upper())

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._hex), self, 'Pick color')
        if c.isValid():
            self._hex = c.name()
            self._refresh()
            self.color_changed.emit(self._hex)

    def hex(self) -> str:
        return self._hex

    def set_hex(self, h: str):
        self._hex = h
        self._refresh()


# ── Mode tab bar ───────────────────────────────────────────────────────────────

class ModeTabBar(QWidget):
    mode_changed = pyqtSignal(str)

    # Hard per-tab minimum widths so long labels never clip, regardless of font.
    _MIN_W = {'pl': 230, 'absorbance': 170, 'xrd': 130, 'iv': 140}

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons = {}
        for m in MODES:
            b = QPushButton(m['label'])
            b.setObjectName('headerTab')
            b.setCheckable(True)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            # Use the larger of the spec floor and the measured text width so the
            # label is guaranteed room with padding to spare.
            floor = self._MIN_W.get(m['key'], 130)
            measured = b.fontMetrics().horizontalAdvance(m['label']) + 52
            b.setMinimumWidth(max(floor, measured))
            b.setMinimumHeight(48)
            add_shadow(b, blur=14, y=3, alpha=18)
            b.clicked.connect(lambda _, k=m['key']: self._select(k))
            self._group.addButton(b)
            self.buttons[m['key']] = b
            row.addWidget(b)
        self.buttons[MODES[0]['key']].setChecked(True)
        self._current = MODES[0]['key']

    def _select(self, key: str):
        self._current = key
        self.mode_changed.emit(key)

    def current(self) -> str:
        return self._current


# ── Top header bar ────────────────────────────────────────────────────────────

class TopHeader(QWidget):
    mode_changed = pyqtSignal(str)
    theme_toggled = pyqtSignal(bool)
    plot_requested = pyqtSignal()

    # Fallback font stack if Montserrat is unavailable
    _TITLE_FF = "'Montserrat','Segoe UI Variable','Segoe UI','Inter',sans-serif"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('topHeader')
        self.setFixedHeight(78)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(0)

        # ── Logo image (assets/logo.png, optional)
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'assets', 'logo.png')
        if os.path.isfile(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setObjectName('logoImg')
            pix = QPixmap(logo_path)
            logo_lbl.setPixmap(pix.scaled(48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            logo_lbl.setFixedSize(48, 48)
            lay.addWidget(logo_lbl)
            lay.addSpacing(12)

        # ── Brand block: SPECTRA + plot title over subtitle
        brand = QWidget()
        brand.setObjectName('brandBlock')
        bcol = QVBoxLayout(brand)
        bcol.setContentsMargins(0, 0, 0, 0)
        bcol.setSpacing(0)

        self._title_lbl = QLabel()
        self._title_lbl.setObjectName('appTitle')
        self._title_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._set_title_colors('#171717', '#5F5F5F')
        subtitle = QLabel('by arnold wijoyo')
        subtitle.setObjectName('brandSub')

        bcol.addStretch()
        bcol.addWidget(self._title_lbl)
        bcol.addWidget(subtitle)
        bcol.addStretch()
        lay.addWidget(brand)
        lay.addSpacing(36)

        self.mode_tabs = ModeTabBar()
        self.mode_tabs.mode_changed.connect(self.mode_changed)
        lay.addWidget(self.mode_tabs)

        lay.addStretch()

        self.btn_plot = QPushButton('PLOT')
        self.btn_plot.setObjectName('headerPlotBtn')
        self.btn_plot.setFixedHeight(40)
        self.btn_plot.setMinimumWidth(110)
        self.btn_plot.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_plot.clicked.connect(self.plot_requested)
        add_shadow(self.btn_plot, blur=16, y=3, alpha=30)
        lay.addWidget(self.btn_plot)
        lay.addSpacing(12)

        self.btn_theme = QPushButton('Dark')
        self.btn_theme.setObjectName('themeToggle')
        self.btn_theme.setCheckable(True)
        self.btn_theme.setFixedSize(64, 32)
        self.btn_theme.toggled.connect(self.theme_toggled)
        lay.addWidget(self.btn_theme)

    def _set_title_colors(self, ink: str, muted: str):
        ff = self._TITLE_FF
        self._title_lbl.setText(
            f'<span style="font-family:{ff};font-size:28px;font-weight:800;'
            f'letter-spacing:-0.5px;color:{ink};">SPECTRA</span>'
            f'<span style="font-family:{ff};font-size:28px;font-weight:300;'
            f'color:{muted};">plot</span>'
        )

    def apply_theme(self, dark: bool):
        self._set_title_colors('#D4D4D4' if dark else '#171717',
                               '#6A6A6A' if dark else '#5F5F5F')


# ── Trace edit dialog ─────────────────────────────────────────────────────────

class TraceEditDialog(QDialog):
    """Edit one trace: display name, color, gradient opt-out, visibility,
    line-width override and line style."""

    def __init__(self, trace: dict, parent=None):
        super().__init__(parent)
        self.trace = trace
        self.setWindowTitle('Edit Trace')
        self.setMinimumWidth(340)

        form = QFormLayout(self)
        form.setSpacing(10)

        self.edit_name = QLineEdit(trace.get('display_name', ''))
        form.addRow('Trace name', self.edit_name)

        # Read-only original filename so the source is visible behind a rename.
        path = trace.get('path', '')
        lbl_file = QLabel(os.path.basename(path) or '—')
        lbl_file.setObjectName('hint')
        lbl_file.setWordWrap(True)
        lbl_file.setToolTip(path)
        lbl_file.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow('File', lbl_file)

        self.color = ColorButton(trace.get('color', '#000000'))
        form.addRow('Color', self.color)

        self.chk_gradient = QCheckBox('Use gradient color')
        self.chk_gradient.setChecked(bool(trace.get('use_auto_gradient_color', True)))
        # Picking a custom color opts this trace out of the panel gradient so the
        # chosen color actually renders even when gradient mode is on.
        self.color.color_changed.connect(lambda _: self.chk_gradient.setChecked(False))
        form.addRow('', self.chk_gradient)

        self.chk_visible = QCheckBox('Visible')
        self.chk_visible.setChecked(bool(trace.get('visible', True)))
        form.addRow('', self.chk_visible)

        self.chk_lw = QCheckBox('Override line width')
        self.spin_lw = FlatDoubleSpinBox()
        self.spin_lw.setRange(0.2, 10.0)
        self.spin_lw.setSingleStep(0.5)
        self.spin_lw.setDecimals(1)
        lw = trace.get('linewidth')
        self.chk_lw.setChecked(lw is not None)
        self.spin_lw.setValue(float(lw) if lw is not None else 2.0)
        self.spin_lw.setEnabled(lw is not None)
        self.chk_lw.toggled.connect(self.spin_lw.setEnabled)
        lw_row = QHBoxLayout()
        lw_row.addWidget(self.chk_lw)
        lw_row.addWidget(self.spin_lw)
        lw_w = QWidget(); lw_w.setLayout(lw_row)
        form.addRow('Line width', lw_w)

        self.combo_ls = QComboBox()
        self.combo_ls.addItems(LINESTYLE_LABELS)
        ls = trace.get('linestyle', 'solid')
        if ls in LINESTYLE_LABELS:
            self.combo_ls.setCurrentText(ls)
        form.addRow('Line style', self.combo_ls)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def apply(self):
        name = self.edit_name.text().strip()
        if name:
            self.trace['display_name'] = name
        self.trace['color'] = self.color.hex()
        self.trace['use_auto_gradient_color'] = self.chk_gradient.isChecked()
        self.trace['visible'] = self.chk_visible.isChecked()
        self.trace['linewidth'] = self.spin_lw.value() if self.chk_lw.isChecked() else None
        self.trace['linestyle'] = self.combo_ls.currentText()


# ── Per-row trace widget (name label + eye toggle) ───────────────────────────

class _TraceRow(QWidget):
    """Label + eye button for one trace entry in the file list."""

    def __init__(self, trace: dict, on_change=None, parent=None):
        super().__init__(parent)
        self._trace = trace
        self._on_change = on_change

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 2, 0)
        lay.setSpacing(4)

        self.lbl = QLabel()
        self.lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.btn = QToolButton()
        self.btn.setFixedSize(26, 22)
        self.btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn.clicked.connect(self._toggle)

        lay.addWidget(self.lbl, 1)
        lay.addWidget(self.btn)
        self._refresh()

    def _toggle(self):
        self._trace['visible'] = not self._trace.get('visible', True)
        self._refresh()
        if self._on_change is not None:
            self._on_change()

    def _refresh(self):
        visible = self._trace.get('visible', True)
        self.lbl.setText(self._trace['display_name'])
        self.lbl.setStyleSheet('' if visible else 'color: #A8A8A8;')
        ink = '#444444' if visible else '#C0C0C0'
        self.btn.setStyleSheet(
            f'QToolButton {{ border: none; background: transparent; font-size: 14px; '
            f'color: {ink}; padding: 0px; }}'
            f'QToolButton:hover {{ background: rgba(0,0,0,0.08); border-radius: 3px; }}'
        )
        self.btn.setText('👁')


# ── Per-panel file widget ─────────────────────────────────────────────────────

class PanelFileWidget(QWidget):
    # Emitted whenever a trace's data affecting the figure changes (visibility,
    # color, name, gradient, add/remove) so the app can live-refresh the plot.
    changed = pyqtSignal()

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.traces: list[dict] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.lst = QListWidget()
        self.lst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lst.setMinimumHeight(75)
        self.lst.setMaximumHeight(220)
        self.lst.itemDoubleClicked.connect(self._edit_double)
        lay.addWidget(self.lst)

        br = QHBoxLayout()
        br.setSpacing(6)
        self.btn_add = QPushButton('+ Add Files')
        self.btn_add.setObjectName('secondary')
        self.btn_rem = QPushButton('Remove')
        self.btn_rem.setObjectName('danger')
        self.btn_add.clicked.connect(self._add)
        self.btn_rem.clicked.connect(self._remove)
        br.addWidget(self.btn_add, 2)
        br.addWidget(self.btn_rem, 1)
        lay.addLayout(br)

        self.btn_edit = QPushButton('Edit Trace…')
        self.btn_edit.setObjectName('secondary')
        self.btn_edit.clicked.connect(self._edit_selected)
        lay.addWidget(self.btn_edit)

        # Gradient toggle — when off, each trace uses its own assigned color
        self.chk_gradient = QCheckBox('Use gradient colors')
        self.chk_gradient.setChecked(True)
        self.chk_gradient.toggled.connect(self._toggle_gradient)
        self.chk_gradient.toggled.connect(self.changed)
        lay.addWidget(self.chk_gradient)

        self._grad_rows: list[QWidget] = []
        for attr, label_text, default in (
            ('c_top', 'Top color', '#000000'),
            ('c_bot', 'Bottom color', '#000000'),
        ):
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setFixedWidth(78)
            lbl.setObjectName('fieldlbl')
            btn = ColorButton(default)
            btn.color_changed.connect(lambda _: self.changed.emit())
            row.addWidget(lbl)
            row.addWidget(btn)
            setattr(self, attr, btn)
            rw = QWidget()
            rw.setLayout(row)
            self._grad_rows.append(rw)
            lay.addWidget(rw)

    def _toggle_gradient(self, on: bool):
        # Hide the top/bottom gradient pickers when gradient mode is off.
        for rw in self._grad_rows:
            rw.setVisible(on)

    def _refresh_item(self, row: int):
        widget = self.lst.itemWidget(self.lst.item(row))
        if isinstance(widget, _TraceRow):
            widget._refresh()

    def _add(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, f'Select files for Panel {self.index + 1}',
            '', 'Spectroscopy files (*.csv *.tsv *.xy);;All files (*.*)'
        )
        existing = {t['path'] for t in self.traces}
        added = False
        for p in paths:
            if p not in existing:
                tr = make_trace(p)
                self.traces.append(tr)
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 30))
                self.lst.addItem(item)
                self.lst.setItemWidget(item, _TraceRow(tr, self.changed.emit))
                existing.add(p)
                added = True
        if added:
            self.changed.emit()

    def _remove(self):
        rows = sorted(
            [self.lst.row(i) for i in self.lst.selectedItems()], reverse=True
        )
        for r in rows:
            self.lst.takeItem(r)
            self.traces.pop(r)
        if rows:
            self.changed.emit()

    def _edit_double(self, item):
        self._edit_trace(self.lst.row(item))

    def _edit_selected(self):
        items = self.lst.selectedItems()
        if not items:
            QMessageBox.information(self, 'Edit Trace',
                                    'Select a trace in the list first.')
            return
        self._edit_trace(self.lst.row(items[0]))

    def _edit_trace(self, row: int):
        if row < 0 or row >= len(self.traces):
            return
        dlg = TraceEditDialog(self.traces[row], self)
        if dlg.exec():
            dlg.apply()
            self._refresh_item(row)
            self.changed.emit()

    def file_entries(self) -> list:
        # Return copies so plotting never mutates the live trace records.
        return [dict(t) for t in self.traces]

    def gradient(self) -> tuple:
        return self.c_top.hex(), self.c_bot.hex()

    def use_gradient(self) -> bool:
        return self.chk_gradient.isChecked()


# ── Helpers ───────────────────────────────────────────────────────────────────

class IVDataSetWidget(QWidget):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.neg_path = ''
        self.pos_path = ''

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(10)

        meta = QGroupBox('Set identity')
        meta_lay = QFormLayout(meta)
        meta_lay.setContentsMargins(8, 14, 8, 8)
        meta_lay.setVerticalSpacing(8)
        self.edit_name = QLineEdit(f'Set {index + 1}')
        self.edit_name.setPlaceholderText(f'Set {index + 1}')
        self.color = ColorButton(IV_SET_COLORS[index % len(IV_SET_COLORS)])
        meta_lay.addRow('Name', self.edit_name)
        meta_lay.addRow('Color', self.color)
        lay.addWidget(meta)

        hint = QLabel('Required: one CSV for each sweep direction.')
        hint.setObjectName('hint')
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.neg_label, neg_row = self._sweep_row(
            '-20 to 0 V sweep',
            lambda: self._pick_sweep('neg'),
            lambda: self._clear_sweep('neg'),
        )
        self.pos_label, pos_row = self._sweep_row(
            '0 to 20 V sweep',
            lambda: self._pick_sweep('pos'),
            lambda: self._clear_sweep('pos'),
        )
        lay.addLayout(neg_row)
        lay.addLayout(pos_row)
        lay.addStretch(1)
        self._refresh_sweep_labels()

    def _sweep_row(self, title: str, browse_handler, clear_handler):
        row = QVBoxLayout()
        row.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName('fieldlbl')
        path_label = QLabel('No CSV selected')
        path_label.setObjectName('hint')
        path_label.setMinimumWidth(120)
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        btn_browse = QPushButton('Browse')
        btn_browse.setObjectName('secondary')
        btn_clear = QPushButton('X')
        btn_clear.setObjectName('danger')
        btn_clear.setFixedWidth(34)
        btn_browse.clicked.connect(browse_handler)
        btn_clear.clicked.connect(clear_handler)

        file_row = QHBoxLayout()
        file_row.setSpacing(6)
        file_row.addWidget(title_label)
        file_row.addWidget(path_label, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addStretch(1)
        action_row.addWidget(btn_browse)
        action_row.addWidget(btn_clear)

        row.addLayout(file_row)
        row.addLayout(action_row)
        return path_label, row

    def _refresh_sweep_labels(self):
        self.neg_label.setText(os.path.basename(self.neg_path) if self.neg_path else 'No CSV selected')
        self.pos_label.setText(os.path.basename(self.pos_path) if self.pos_path else 'No CSV selected')

    def _pick_sweep(self, sweep: str):
        label = '-20 to 0 V sweep' if sweep == 'neg' else '0 to 20 V sweep'
        path, _ = QFileDialog.getOpenFileName(
            self,
            f'{self.display_name()}: select {label} CSV',
            '',
            'Keithley CSV files (*.csv);;All files (*.*)',
        )
        if not path:
            return
        if sweep == 'neg':
            self.neg_path = path
        else:
            self.pos_path = path
        self._refresh_sweep_labels()

    def _clear_sweep(self, sweep: str):
        if sweep == 'neg':
            self.neg_path = ''
        else:
            self.pos_path = ''
        self._refresh_sweep_labels()

    def display_name(self) -> str:
        return self.edit_name.text().strip() or f'Set {self.index + 1}'

    def settings(self) -> dict:
        return {
            'name': self.display_name(),
            'color': self.color.hex(),
            'neg_path': self.neg_path,
            'pos_path': self.pos_path,
        }


def _labeled(label_text: str, widget: QWidget, lw: int = 74) -> QHBoxLayout:
    r = QHBoxLayout()
    r.setSpacing(8)
    lbl = QLabel(label_text)
    lbl.setFixedWidth(lw)
    lbl.setObjectName('fieldlbl')
    r.addWidget(lbl)
    r.addWidget(widget)
    return r


def _sep() -> QLabel:
    sep = QLabel()
    sep.setFixedHeight(1)
    sep.setStyleSheet('background: #E2E8F0; margin: 4px 0;')
    return sep


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


# ── Control panel ─────────────────────────────────────────────────────────────

class ControlPanel(QScrollArea):
    plot_requested = pyqtSignal()
    live_update_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('sidebar')
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedWidth(368)

        root = QWidget()
        root.setObjectName('sidebar')
        root.setMinimumWidth(0)
        root.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setWidget(root)

        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 12)
        lay.setSpacing(6)

        self._current_mode = MODES[0]['key']

        # ── Plot panels
        self.g_plot = QGroupBox('Plot')
        gl = QVBoxLayout(self.g_plot)
        gl.setSpacing(9)
        self.spin_panels = FlatSpinBox()
        self.spin_panels.setRange(1, 5)
        self.spin_panels.setValue(1)
        self.spin_panels.valueChanged.connect(self._on_panels_change)
        gl.addLayout(_labeled('Panels', self.spin_panels))

        self.spin_gap = FlatDoubleSpinBox()
        self.spin_gap.setRange(0.0, 1.0)
        self.spin_gap.setSingleStep(0.05)
        self.spin_gap.setDecimals(2)
        self.spin_gap.setValue(0.30)
        gl.addLayout(_labeled('Panel gap', self.spin_gap))
        lay.addWidget(self.g_plot)

        # ── Data tabs
        self.g_data = QGroupBox('Data')
        dgl = QVBoxLayout(self.g_data)
        dgl.setContentsMargins(8, 16, 8, 8)
        dgl.setSpacing(6)
        hint = QLabel('Add .csv / .tsv / .xy files per panel.')
        hint.setObjectName('hint')
        hint.setWordWrap(True)
        dgl.addWidget(hint)
        self.panel_tabs = QTabWidget()
        self.panel_widgets: list[PanelFileWidget] = []
        for i in range(5):
            pw = PanelFileWidget(i)
            pw.changed.connect(self.live_update_requested)
            self.panel_widgets.append(pw)
            self.panel_tabs.addTab(pw, f'P{i+1}')
            if i > 0:
                self.panel_tabs.setTabVisible(i, False)
        dgl.addWidget(self.panel_tabs)
        lay.addWidget(self.g_data)

        self.g_iv = QGroupBox('IV Curve Data')
        iv_lay = QVBoxLayout(self.g_iv)
        iv_lay.setContentsMargins(4, 14, 4, 8)
        iv_lay.setSpacing(8)
        self.spin_iv_sets = FlatSpinBox()
        self.spin_iv_sets.setRange(1, 10)
        self.spin_iv_sets.setValue(3)
        self.spin_iv_sets.valueChanged.connect(self._on_iv_sets_change)
        iv_lay.addLayout(_labeled('Data sets', self.spin_iv_sets))
        iv_hint = QLabel('Each set needs both -20 to 0 V and 0 to 20 V Keithley CSV scans.')
        iv_hint.setObjectName('hint')
        iv_hint.setWordWrap(True)
        iv_lay.addWidget(iv_hint)
        self.iv_tabs = QTabWidget()
        self.iv_widgets: list[IVDataSetWidget] = []
        for i in range(10):
            widget = IVDataSetWidget(i)
            self.iv_widgets.append(widget)
            self.iv_tabs.addTab(widget, f'Set {i + 1}')
            if i >= 3:
                self.iv_tabs.setTabVisible(i, False)
        iv_lay.addWidget(self.iv_tabs)
        self.g_iv.setVisible(False)
        lay.addWidget(self.g_iv)

        # ── Axes
        self.g_axes = QGroupBox('Axes')
        agl = QVBoxLayout(self.g_axes)
        agl.setSpacing(9)

        xrow = QHBoxLayout(); xrow.setSpacing(5)
        xl = QLabel('X range'); xl.setFixedWidth(52); xl.setObjectName('fieldlbl')
        self.spin_xmin = FlatDoubleSpinBox()
        self.spin_xmax = FlatDoubleSpinBox()
        for s in (self.spin_xmin, self.spin_xmax):
            s.setRange(-9999, 99999); s.setDecimals(1)
            s.setMinimumWidth(56)
            s.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spin_xmin.setValue(400); self.spin_xmax.setValue(800)
        dash = QLabel('–'); dash.setStyleSheet('color:#8a93a0;')
        dash.setFixedWidth(12); dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        xrow.addWidget(xl); xrow.addWidget(self.spin_xmin, 1)
        xrow.addWidget(dash); xrow.addWidget(self.spin_xmax, 1)
        agl.addLayout(xrow)

        self.chk_auto_x = QCheckBox('Auto X (fit to data)')
        self.chk_auto_x.setChecked(True)
        agl.addWidget(self.chk_auto_x)

        # Per-panel X limits — off by default keeps the global behavior above.
        self.chk_separate_x = QCheckBox('Use separate X limits per panel')
        self.chk_separate_x.setChecked(False)
        self.chk_separate_x.toggled.connect(self._toggle_separate_x)
        agl.addWidget(self.chk_separate_x)

        self._panel_x = [{'auto': False, 'min': 400.0, 'max': 800.0} for _ in range(5)]
        self._xpanel_idx = 0
        self.combo_xpanel = QComboBox()
        self.combo_xpanel.addItems([f'P{i+1}' for i in range(5)])
        self.combo_xpanel.currentIndexChanged.connect(self._on_xpanel_change)
        agl.addLayout(_labeled('Edit panel', self.combo_xpanel))
        self.chk_pauto_x = QCheckBox('Auto X (this panel)')
        self.chk_pauto_x.toggled.connect(self._toggle_panel_xlim)
        agl.addWidget(self.chk_pauto_x)
        pxrow = QHBoxLayout(); pxrow.setSpacing(5)
        pxl = QLabel('X range'); pxl.setFixedWidth(52); pxl.setObjectName('fieldlbl')
        self.spin_pxmin = FlatDoubleSpinBox()
        self.spin_pxmax = FlatDoubleSpinBox()
        for s in (self.spin_pxmin, self.spin_pxmax):
            s.setRange(-9999, 99999); s.setDecimals(1)
            s.setMinimumWidth(56)
            s.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spin_pxmin.setValue(400); self.spin_pxmax.setValue(800)
        pdash = QLabel('–'); pdash.setStyleSheet('color:#8a93a0;')
        pdash.setFixedWidth(12); pdash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pxrow.addWidget(pxl); pxrow.addWidget(self.spin_pxmin, 1)
        pxrow.addWidget(pdash); pxrow.addWidget(self.spin_pxmax, 1)
        agl.addLayout(pxrow)
        # The per-panel editor widgets are disabled until "separate" is enabled.
        self._sepx_widgets = [self.combo_xpanel, self.chk_pauto_x,
                              self.spin_pxmin, self.spin_pxmax]
        self._toggle_separate_x(False)

        agl.addWidget(_sep())

        yrow = QHBoxLayout(); yrow.setSpacing(5)
        yl = QLabel('Y range'); yl.setFixedWidth(52); yl.setObjectName('fieldlbl')
        self.spin_ymin = FlatDoubleSpinBox()
        self.spin_ymax = FlatDoubleSpinBox()
        for s in (self.spin_ymin, self.spin_ymax):
            s.setRange(-9999999, 9999999); s.setDecimals(2)
            s.setMinimumWidth(56)
            s.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spin_ymin.setValue(0); self.spin_ymax.setValue(1)
        dash2 = QLabel('–'); dash2.setStyleSheet('color:#8a93a0;')
        dash2.setFixedWidth(12); dash2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        yrow.addWidget(yl); yrow.addWidget(self.spin_ymin, 1)
        yrow.addWidget(dash2); yrow.addWidget(self.spin_ymax, 1)
        agl.addLayout(yrow)

        self.chk_auto_y = QCheckBox('Auto Y (fit to data)')
        self.chk_auto_y.setChecked(True)
        agl.addWidget(self.chk_auto_y)
        agl.addWidget(_sep())

        self.chk_share_y = QCheckBox('Share Y limits across panels')
        self.chk_share_y.setChecked(True)
        agl.addWidget(self.chk_share_y)
        lay.addWidget(self.g_axes)

        self.chk_auto_x.stateChanged.connect(self._toggle_xlim)
        self.chk_auto_y.stateChanged.connect(self._toggle_ylim)

        # ── Labels
        g4 = QGroupBox('Labels')
        lgl = QVBoxLayout(g4)
        lgl.setSpacing(7)
        self.chk_main_title = QCheckBox('Main title')
        self.edit_main_title = QLineEdit()
        self.edit_main_title.setPlaceholderText('Enter main title…')
        self.chk_subtitle = QCheckBox('Subtitle')
        self.edit_subtitle = QLineEdit()
        self.edit_subtitle.setPlaceholderText('Enter subtitle…')
        self.chk_panel_titles = QCheckBox('Panel titles')
        self.chk_panel_titles.setChecked(True)
        self.edit_panel_titles = QLineEdit()
        self.edit_panel_titles.setPlaceholderText('A, B, C … (comma-separated)')
        for w in (self.chk_main_title, self.edit_main_title,
                  self.chk_subtitle, self.edit_subtitle,
                  self.chk_panel_titles, self.edit_panel_titles):
            lgl.addWidget(w)
        tip = QLabel('Tip: double-click any text in the figure to edit it; '
                     'drag titles, labels & legend to reposition.')
        tip.setObjectName('hint')
        tip.setWordWrap(True)
        lgl.addWidget(tip)
        lay.addWidget(g4)

        # ── Style
        g5 = QGroupBox('Style')
        sgl = QVBoxLayout(g5)
        sgl.setSpacing(9)

        self.spin_lw = FlatDoubleSpinBox()
        self.spin_lw.setRange(0.5, 6.0); self.spin_lw.setSingleStep(0.5); self.spin_lw.setValue(2.0)
        sgl.addLayout(_labeled('Line width', self.spin_lw))

        self.spin_fs = FlatSpinBox()
        self.spin_fs.setRange(6, 28); self.spin_fs.setValue(16)
        sgl.addLayout(_labeled('Font size', self.spin_fs))

        sgl.addWidget(_sep())

        fw_row = QHBoxLayout(); fw_row.setSpacing(5)
        fw_lbl = QLabel('Size (px)'); fw_lbl.setFixedWidth(52); fw_lbl.setObjectName('fieldlbl')
        self.spin_fw = FlatSpinBox()
        self.spin_fh = FlatSpinBox()
        for s in (self.spin_fw, self.spin_fh):
            s.setRange(100, 3000); s.setSingleStep(50); s.setMaximumWidth(78)
        self.spin_fw.setValue(800); self.spin_fh.setValue(500)
        fw_x = QLabel('×'); fw_x.setStyleSheet('color:#8a93a0;')
        fw_row.addWidget(fw_lbl)
        fw_row.addWidget(self.spin_fw)
        fw_row.addWidget(fw_x)
        fw_row.addWidget(self.spin_fh)
        sgl.addLayout(fw_row)
        fw_note = QLabel('Width × Height — fixed canvas size & export size')
        fw_note.setObjectName('hint')
        fw_note.setWordWrap(True)
        sgl.addWidget(fw_note)
        lay.addWidget(g5)

        # ── Graph Appearance (figure font family)
        g_app = QGroupBox('Graph Appearance')
        appl = QVBoxLayout(g_app)
        appl.setSpacing(4)
        self.combo_font = NoScrollComboBox()
        self.combo_font.addItems([
            'Arial', 'Helvetica', 'Times New Roman',
            'DejaVu Sans', 'DejaVu Serif', 'Liberation Sans',
        ])
        self.combo_font.setCurrentText('Arial')
        appl.addLayout(_labeled('Figure font', self.combo_font))
        fnote = QLabel('Applied to axes, ticks, titles, legend & export.')
        fnote.setObjectName('hint')
        fnote.setWordWrap(True)
        appl.addWidget(fnote)
        lay.addWidget(g_app)

        # ════════════════════════════════════════════════════════════════════
        # The four groups below live in the bottom dock (built by MainWindow via
        # take_dock_groups()), NOT in this sidebar layout. They remain attributes
        # of ControlPanel so settings() stays the single source of truth.
        # ════════════════════════════════════════════════════════════════════

        # ── Ticks (MATLAB-style boxed axes by default)
        g_tick = QGroupBox('Ticks')
        tgl = QVBoxLayout(g_tick)
        tgl.setSpacing(4)
        tgl.setContentsMargins(8, 6, 8, 6)
        self.combo_tick_dir = QComboBox()
        self.combo_tick_dir.addItems(['in', 'out', 'inout'])
        self.combo_tick_dir.setCurrentText('in')
        tgl.addLayout(_labeled('Direction', self.combo_tick_dir))
        self.chk_xticks = QCheckBox('Show X ticks'); self.chk_xticks.setChecked(True)
        self.chk_yticks = QCheckBox('Show Y ticks'); self.chk_yticks.setChecked(True)
        self.chk_top_ticks = QCheckBox('Show top ticks'); self.chk_top_ticks.setChecked(True)
        self.chk_right_ticks = QCheckBox('Show right ticks'); self.chk_right_ticks.setChecked(True)
        self.chk_minor_ticks = QCheckBox('Minor ticks'); self.chk_minor_ticks.setChecked(False)
        for c in (self.chk_xticks, self.chk_yticks, self.chk_top_ticks,
                  self.chk_right_ticks, self.chk_minor_ticks):
            tgl.addWidget(c)
        self.spin_tick_len = FlatDoubleSpinBox()
        self.spin_tick_len.setRange(0.0, 20.0); self.spin_tick_len.setSingleStep(0.5)
        self.spin_tick_len.setDecimals(1); self.spin_tick_len.setValue(4.0)
        tgl.addLayout(_labeled('Tick length', self.spin_tick_len))
        self.spin_tick_w = FlatDoubleSpinBox()
        self.spin_tick_w.setRange(0.1, 6.0); self.spin_tick_w.setSingleStep(0.1)
        self.spin_tick_w.setDecimals(1); self.spin_tick_w.setValue(0.8)
        tgl.addLayout(_labeled('Tick width', self.spin_tick_w))
        tgl.addStretch(1)

        # ── Number format (axis notation)
        g_num = QGroupBox('Axis Numbers')
        ngl = QVBoxLayout(g_num)
        ngl.setSpacing(4)
        ngl.setContentsMargins(8, 6, 8, 6)
        self.combo_ynot = QComboBox()
        self.combo_ynot.addItems(['Normal', 'Scientific notation', 'Engineering/K'])
        self.combo_ynot.currentTextChanged.connect(self._toggle_sci)
        ngl.addLayout(_labeled('Format', self.combo_ynot, 70))
        self.chk_force_sci = QCheckBox('Force scientific Y exponent')
        self.chk_force_sci.setEnabled(False)
        self.chk_force_sci.toggled.connect(self._toggle_sci)
        ngl.addWidget(self.chk_force_sci)
        self.spin_sci_exp = FlatSpinBox()
        self.spin_sci_exp.setRange(-12, 12); self.spin_sci_exp.setValue(3)
        self.spin_sci_exp.setEnabled(False)
        ngl.addLayout(_labeled('Exponent', self.spin_sci_exp, 70))
        # slider + spinbox: distance from axis numbers to box outline
        self.slider_numpad = QSlider(Qt.Orientation.Horizontal)
        self.slider_numpad.setRange(0, 30)
        self.slider_numpad.setValue(6)
        self.spin_numpad = FlatSpinBox()
        self.spin_numpad.setRange(0, 30)
        self.spin_numpad.setValue(6)
        self.spin_numpad.setFixedWidth(44)
        self.slider_numpad.valueChanged.connect(self.spin_numpad.setValue)
        self.spin_numpad.valueChanged.connect(self.slider_numpad.setValue)
        self.slider_numpad.valueChanged.connect(lambda _: self.plot_requested.emit())
        _dist_row = QHBoxLayout()
        _dist_row.setSpacing(6)
        _lbl_dist = QLabel('Distance')
        _lbl_dist.setFixedWidth(70)
        _lbl_dist.setObjectName('fieldlbl')
        _dist_row.addWidget(_lbl_dist)
        _dist_row.addWidget(self.slider_numpad, 1)
        _dist_row.addWidget(self.spin_numpad)
        ngl.addLayout(_dist_row)
        ngl.addStretch(1)

        # ── Legend (full customization; transparent background by default)
        g_legend = QGroupBox('Legend')
        lgll = QFormLayout(g_legend)
        lgll.setVerticalSpacing(4)
        lgll.setContentsMargins(8, 6, 8, 6)
        lgll.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.chk_legend = QCheckBox('Show legend')
        self.chk_legend.setChecked(True)
        lgll.addRow(self.chk_legend)
        # PL only: order legend entries from highest peak (top) to lowest (bottom),
        # independent of plot/gradient order. When off, legend follows add order.
        self.chk_legend_peak_order = QCheckBox('Order legend by peak (high→low)')
        self.chk_legend_peak_order.setChecked(True)
        self.chk_legend_peak_order.toggled.connect(self.live_update_requested)
        lgll.addRow(self.chk_legend_peak_order)
        self.combo_legend_loc = QComboBox()
        self.combo_legend_loc.addItems([
            'best', 'upper right', 'upper left',
            'lower right', 'lower left', 'center right', 'center left',
        ])
        lgll.addRow('Position', self.combo_legend_loc)
        lgll.addRow(_sep())
        self.chk_legend_transp_bg = QCheckBox('Transparent BG')
        self.chk_legend_transp_bg.setChecked(True)
        self.chk_legend_transp_bg.toggled.connect(self._toggle_legend)
        lgll.addRow(self.chk_legend_transp_bg)
        self.color_legend_bg = ColorButton('#FFFFFF')
        self.spin_legend_alpha = FlatDoubleSpinBox()
        self.spin_legend_alpha.setRange(0.0, 1.0); self.spin_legend_alpha.setSingleStep(0.05)
        self.spin_legend_alpha.setDecimals(2); self.spin_legend_alpha.setValue(0.0)
        self.spin_legend_alpha.setFixedWidth(56)
        _bg_row = QHBoxLayout(); _bg_row.setSpacing(4)
        _bg_row.addWidget(self.color_legend_bg); _bg_row.addWidget(self.spin_legend_alpha)
        _bg_w = QWidget(); _bg_w.setLayout(_bg_row)
        lgll.addRow('BG / α', _bg_w)
        lgll.addRow(_sep())
        self.chk_legend_transp_edge = QCheckBox('Transparent edge')
        self.chk_legend_transp_edge.setChecked(False)
        self.chk_legend_transp_edge.toggled.connect(self._toggle_legend)
        lgll.addRow(self.chk_legend_transp_edge)
        self.color_legend_edge = ColorButton('#000000')
        self.spin_legend_edge_w = FlatDoubleSpinBox()
        self.spin_legend_edge_w.setRange(0.0, 6.0); self.spin_legend_edge_w.setSingleStep(0.1)
        self.spin_legend_edge_w.setDecimals(1); self.spin_legend_edge_w.setValue(0.8)
        self.spin_legend_edge_w.setFixedWidth(56)
        _edge_row = QHBoxLayout(); _edge_row.setSpacing(4)
        _edge_row.addWidget(self.color_legend_edge); _edge_row.addWidget(self.spin_legend_edge_w)
        _edge_w = QWidget(); _edge_w.setLayout(_edge_row)
        lgll.addRow('Edge / w', _edge_w)
        self.spin_legend_fs = FlatDoubleSpinBox()
        self.spin_legend_fs.setRange(4.0, 40.0); self.spin_legend_fs.setSingleStep(1.0)
        self.spin_legend_fs.setDecimals(1); self.spin_legend_fs.setValue(16.0)
        lgll.addRow('Font size', self.spin_legend_fs)

        # ── Plot Box (axis box, tick-label padding, manual geometry, snap)
        g_box = QGroupBox('Plot Box')
        bgl = QFormLayout(g_box)
        bgl.setVerticalSpacing(4)
        bgl.setContentsMargins(8, 6, 8, 6)
        bgl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.spin_box_lw = FlatDoubleSpinBox()
        self.spin_box_lw.setRange(0.2, 6.0); self.spin_box_lw.setSingleStep(0.1)
        self.spin_box_lw.setDecimals(1); self.spin_box_lw.setValue(1.0)
        self.color_box = ColorButton('#000000')
        _box_row = QHBoxLayout(); _box_row.setSpacing(4)
        _box_row.addWidget(self.color_box); _box_row.addWidget(self.spin_box_lw)
        _box_w = QWidget(); _box_w.setLayout(_box_row)
        bgl.addRow('Color / lw', _box_w)
        bgl.addRow(_sep())
        self.chk_manual_box = QCheckBox('Manual layout')
        self.chk_manual_box.setChecked(False)
        self.chk_manual_box.toggled.connect(self._toggle_manual_box)
        bgl.addRow(self.chk_manual_box)
        self._manual_rows: list = []
        for attr, label_text, default in (
            ('spin_pa_w', 'Width', 0.84),
            ('spin_pa_h', 'Height', 0.78),
            ('spin_pa_left', 'Left', 0.10),
            ('spin_pa_bottom', 'Bottom', 0.12),
            ('spin_panel_gap', 'Gap', 0.04),
        ):
            sp = FlatDoubleSpinBox()
            sp.setRange(0.0, 1.0); sp.setSingleStep(0.01); sp.setDecimals(3)
            sp.setValue(default); sp.setEnabled(False)
            setattr(self, attr, sp)
            self._manual_rows.append((sp, label_text))
            bgl.addRow(label_text, sp)
        bgl.addRow(_sep())
        self.chk_snap = QCheckBox('Snap to grid')
        self.chk_snap.setChecked(False)
        bgl.addRow(self.chk_snap)
        self.spin_snap_step = FlatDoubleSpinBox()
        self.spin_snap_step.setRange(0.001, 0.5); self.spin_snap_step.setSingleStep(0.005)
        self.spin_snap_step.setDecimals(3); self.spin_snap_step.setValue(0.01)
        bgl.addRow('Step', self.spin_snap_step)

        # Dock groups handed to MainWindow; NOT added to the sidebar layout here.
        self.dock_groups = [g_tick, g_num, g_legend, g_box]
        self._toggle_legend()

        # ── PL options
        self.g_pl = QGroupBox('PL Options')
        plgl = QVBoxLayout(self.g_pl)
        plgl.setSpacing(9)
        self.chk_pl_baseline = QCheckBox('Baseline subtract')
        self.chk_pl_baseline.setChecked(True)
        pl_note = QLabel('Matches the original PL MATLAB workflow: y = y - y(1).')
        pl_note.setObjectName('hint')
        pl_note.setWordWrap(True)
        plgl.addWidget(self.chk_pl_baseline)
        plgl.addWidget(pl_note)
        lay.addWidget(self.g_pl)

        # ── XRD options
        self.g_xrd = QGroupBox('XRD Options')
        xgl = QVBoxLayout(self.g_xrd)
        xgl.setSpacing(9)
        self.chk_d = QCheckBox('Convert 2θ → d-spacing (Å)')
        xgl.addWidget(self.chk_d)
        self.spin_lam = FlatDoubleSpinBox()
        self.spin_lam.setRange(0.5, 3.0); self.spin_lam.setDecimals(4)
        self.spin_lam.setValue(1.5406); self.spin_lam.setSingleStep(0.001)
        xgl.addLayout(_labeled('λ (Å)', self.spin_lam))
        self.spin_ref_step = FlatDoubleSpinBox()
        self.spin_ref_step.setRange(0, 1000); self.spin_ref_step.setValue(1.0)
        xgl.addLayout(_labeled('Ref offset', self.spin_ref_step))
        self.spin_exp_step = FlatDoubleSpinBox()
        self.spin_exp_step.setRange(0, 1000); self.spin_exp_step.setValue(1.0)
        xgl.addLayout(_labeled('Exp offset', self.spin_exp_step))

        xgl.addWidget(_sep())
        self.chk_xrd_margin_labels = QCheckBox('Right margin trace labels')
        self.chk_xrd_margin_labels.setChecked(False)
        xgl.addWidget(self.chk_xrd_margin_labels)
        self.spin_xrd_label_gap = FlatDoubleSpinBox()
        self.spin_xrd_label_gap.setRange(0.0, 1000.0); self.spin_xrd_label_gap.setDecimals(2)
        self.spin_xrd_label_gap.setSingleStep(0.05); self.spin_xrd_label_gap.setValue(0.25)
        xgl.addLayout(_labeled('Label gap', self.spin_xrd_label_gap))

        xgl.addWidget(_sep())
        ref_lbl = QLabel('Reference traces (black, all panels):')
        ref_lbl.setObjectName('fieldlbl')
        xgl.addWidget(ref_lbl)
        self.xrd_ref_list = QListWidget()
        self.xrd_ref_list.setMaximumHeight(90)
        self.xrd_ref_paths: list[str] = []
        xgl.addWidget(self.xrd_ref_list)
        xrd_br = QHBoxLayout(); xrd_br.setSpacing(6)
        self.btn_ref_add = QPushButton('+ Add Refs')
        self.btn_ref_add.setObjectName('secondary')
        self.btn_ref_rem = QPushButton('Remove')
        self.btn_ref_rem.setObjectName('danger')
        self.btn_ref_add.clicked.connect(self._xrd_add_refs)
        self.btn_ref_rem.clicked.connect(self._xrd_rem_refs)
        xrd_br.addWidget(self.btn_ref_add, 2); xrd_br.addWidget(self.btn_ref_rem, 1)
        xgl.addLayout(xrd_br)
        self.g_xrd.setVisible(False)
        lay.addWidget(self.g_xrd)

        # ── Export
        g6 = QGroupBox('Export')
        egl = QVBoxLayout(g6)
        egl.setSpacing(9)
        self.spin_dpi = FlatSpinBox()
        self.spin_dpi.setRange(72, 600); self.spin_dpi.setSingleStep(50); self.spin_dpi.setValue(300)
        egl.addLayout(_labeled('DPI', self.spin_dpi))
        fmt_row = QHBoxLayout(); fmt_row.setSpacing(6)
        for fmt in ('PNG', 'PDF', 'SVG'):
            b = QPushButton(fmt); b.setObjectName('secondary')
            b.clicked.connect(lambda checked, f=fmt.lower(): self._save(f))
            fmt_row.addWidget(b)
        egl.addLayout(fmt_row)
        lay.addWidget(g6)

        # ── Plot button
        self.btn_plot = QPushButton('PLOT')
        self.btn_plot.setObjectName('plotBtn')
        self.btn_plot.setFixedHeight(48)
        self.btn_plot.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_plot.clicked.connect(self.plot_requested)
        lay.addWidget(self.btn_plot)
        lay.addStretch()

        self._canvas = None
        self._apply_accent(MODES[0]['accent'])

    # ── Accent ───────────────────────────────────────────────────────────────────

    def _apply_accent(self, accent: str):
        self.btn_plot.setStyleSheet(
            f'QPushButton#plotBtn{{'
            f'background:#FFFFFF;color:{accent};font-size:12px;'
            f'font-weight:700;border-radius:8px;min-height:44px;'
            f'border:2px solid {accent};letter-spacing:3px;}}'
            f'QPushButton#plotBtn:hover{{'
            f'background:{accent};color:#FFFFFF;}}'
            f'QPushButton#plotBtn:pressed{{'
            f'background:{accent};color:#FFFFFF;}}'
        )

    # ── Slots ──────────────────────────────────────────────────────────────────

    def set_mode(self, key: str):
        self._current_mode = key
        is_iv = key == 'iv'
        self.g_plot.setVisible(not is_iv)
        self.g_data.setVisible(not is_iv)
        self.g_axes.setVisible(not is_iv)
        self.g_iv.setVisible(is_iv)
        self.g_pl.setVisible(key == 'pl')
        self.g_xrd.setVisible(key == 'xrd')
        self._apply_accent(MODE_BY_KEY[key]['accent'])

    def current_mode(self) -> str:
        return self._current_mode

    def _on_panels_change(self, n: int):
        for i in range(5):
            self.panel_tabs.setTabVisible(i, i < n)

    def _on_iv_sets_change(self, n: int):
        for i in range(10):
            self.iv_tabs.setTabVisible(i, i < n)

    def _toggle_xlim(self):
        enabled = not self.chk_auto_x.isChecked() and not self.chk_separate_x.isChecked()
        self.spin_xmin.setEnabled(enabled)
        self.spin_xmax.setEnabled(enabled)

    def _toggle_ylim(self):
        auto = self.chk_auto_y.isChecked()
        self.spin_ymin.setEnabled(not auto)
        self.spin_ymax.setEnabled(not auto)

    def _toggle_sci(self, *_):
        sci = self.combo_ynot.currentText().startswith('Scientific')
        self.chk_force_sci.setEnabled(sci)
        self.spin_sci_exp.setEnabled(sci and self.chk_force_sci.isChecked())

    def _toggle_manual_box(self, on: bool):
        for sp, _row in self._manual_rows:
            sp.setEnabled(on)

    def _toggle_separate_x(self, on: bool):
        for w in self._sepx_widgets:
            w.setEnabled(on)
        self.chk_auto_x.setEnabled(not on)
        self._toggle_xlim()
        if on:
            self._load_xpanel(self._xpanel_idx)
            self._toggle_panel_xlim()

    def _flush_xpanel(self):
        """Save the per-panel X editor widgets into the current panel's record."""
        self._panel_x[self._xpanel_idx] = {
            'auto': self.chk_pauto_x.isChecked(),
            'min': self.spin_pxmin.value(),
            'max': self.spin_pxmax.value(),
        }

    def _load_xpanel(self, idx: int):
        d = self._panel_x[idx]
        self.chk_pauto_x.setChecked(d['auto'])
        self.spin_pxmin.setValue(d['min'])
        self.spin_pxmax.setValue(d['max'])

    def _on_xpanel_change(self, new_idx: int):
        if new_idx == self._xpanel_idx:
            return
        self._flush_xpanel()
        self._xpanel_idx = new_idx
        self._load_xpanel(new_idx)
        self._toggle_panel_xlim()

    def _toggle_panel_xlim(self, *_):
        # Honor the per-panel Auto-X within the per-panel editor.
        if not self.chk_separate_x.isChecked():
            return
        auto = self.chk_pauto_x.isChecked()
        self.spin_pxmin.setEnabled(not auto)
        self.spin_pxmax.setEnabled(not auto)

    def _toggle_legend(self, *_):
        # Transparent toggles disable their corresponding color/value inputs.
        transp_bg = self.chk_legend_transp_bg.isChecked()
        self.color_legend_bg.setEnabled(not transp_bg)
        self.spin_legend_alpha.setEnabled(not transp_bg)
        transp_edge = self.chk_legend_transp_edge.isChecked()
        self.color_legend_edge.setEnabled(not transp_edge)
        self.spin_legend_edge_w.setEnabled(not transp_edge)

    def take_dock_groups(self) -> list:
        """Hand the four bottom-dock QGroupBoxes to MainWindow (which reparents
        them into the dock). Safe to call once after construction."""
        return self.dock_groups

    def _xrd_add_refs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, 'Select reference XRD files', '',
            'Spectroscopy files (*.csv *.tsv *.xy);;All files (*.*)'
        )
        for p in paths:
            if p not in self.xrd_ref_paths:
                self.xrd_ref_paths.append(p)
                self.xrd_ref_list.addItem(clean_label(os.path.basename(p)))

    def _xrd_rem_refs(self):
        rows = sorted(
            [self.xrd_ref_list.row(i) for i in self.xrd_ref_list.selectedItems()],
            reverse=True
        )
        for r in rows:
            self.xrd_ref_list.takeItem(r)
            self.xrd_ref_paths.pop(r)

    def _save(self, fmt: str):
        if self._canvas is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f'Save as {fmt.upper()}', '',
            f'{fmt.upper()} files (*.{fmt});;All files (*.*)'
        )
        if path:
            try:
                self._canvas.save(path, fmt, self.spin_dpi.value(),
                                  self.spin_fw.value() / 100, self.spin_fh.value() / 100)
            except Exception as e:
                QMessageBox.critical(self, 'Save Error', str(e))

    # ── Settings export ────────────────────────────────────────────────────────

    def settings(self) -> dict:
        n = self.spin_panels.value()
        panel_data = [
            {'traces': self.panel_widgets[i].file_entries(),
             'gradient': self.panel_widgets[i].gradient(),
             'use_gradient': self.panel_widgets[i].use_gradient()}
            for i in range(n)
        ]
        iv_sets = [
            self.iv_widgets[i].settings()
            for i in range(self.spin_iv_sets.value())
        ]
        raw = self.edit_panel_titles.text()
        panel_titles = [t.strip() for t in raw.split(',') if t.strip()]
        while len(panel_titles) < 5:
            panel_titles.append(chr(ord('A') + len(panel_titles)))

        # Snapshot the live per-panel X editor before reading the records.
        self._flush_xpanel()
        panel_x_limits = [
            {'auto_x': d['auto'], 'x_min': d['min'], 'x_max': d['max']}
            for d in self._panel_x
        ]

        return {
            'plot_type': self.current_mode(),
            'n_panels': n,
            'panel_data': panel_data,
            'iv_sets': iv_sets,
            'auto_x': self.chk_auto_x.isChecked(),
            'x_min': self.spin_xmin.value(),
            'x_max': self.spin_xmax.value(),
            'separate_x_limits': self.chk_separate_x.isChecked(),
            'panel_x_limits': panel_x_limits,
            'auto_y': self.chk_auto_y.isChecked(),
            'y_min': self.spin_ymin.value(),
            'y_max': self.spin_ymax.value(),
            'share_y': self.chk_share_y.isChecked(),
            'show_main_title': self.chk_main_title.isChecked(),
            'main_title': self.edit_main_title.text().strip(),
            'show_subtitle': self.chk_subtitle.isChecked(),
            'subtitle': self.edit_subtitle.text().strip(),
            'show_panel_titles': self.chk_panel_titles.isChecked(),
            'panel_titles': panel_titles,
            'linewidth': self.spin_lw.value(),
            'fontsize': self.spin_fs.value(),
            'fig_width': self.spin_fw.value(),
            'fig_height': self.spin_fh.value(),
            'show_legend': self.chk_legend.isChecked(),
            'legend_loc': self.combo_legend_loc.currentText(),
            'legend_transparent_bg': self.chk_legend_transp_bg.isChecked(),
            'legend_bg_color': self.color_legend_bg.hex(),
            'legend_bg_alpha': self.spin_legend_alpha.value(),
            'legend_transparent_edge': self.chk_legend_transp_edge.isChecked(),
            'legend_edge_color': self.color_legend_edge.hex(),
            'legend_edge_width': self.spin_legend_edge_w.value(),
            'legend_fontsize': self.spin_legend_fs.value(),
            'legend_peak_order': self.chk_legend_peak_order.isChecked(),
            'pl_baseline_correct': self.chk_pl_baseline.isChecked(),
            'xrd_d_spacing': self.chk_d.isChecked(),
            'xrd_lambda': self.spin_lam.value(),
            'xrd_ref_step': self.spin_ref_step.value(),
            'xrd_exp_step': self.spin_exp_step.value(),
            'xrd_margin_labels': self.chk_xrd_margin_labels.isChecked(),
            'xrd_margin_label_gap': self.spin_xrd_label_gap.value(),
            'xrd_ref_paths': list(self.xrd_ref_paths),
            # Graph appearance — font
            'font_family': self.combo_font.currentText(),
            # Ticks
            'tick_dir': self.combo_tick_dir.currentText(),
            'show_xticks': self.chk_xticks.isChecked(),
            'show_yticks': self.chk_yticks.isChecked(),
            'show_top_ticks': self.chk_top_ticks.isChecked(),
            'show_right_ticks': self.chk_right_ticks.isChecked(),
            'tick_length': self.spin_tick_len.value(),
            'tick_width': self.spin_tick_w.value(),
            'minor_ticks': self.chk_minor_ticks.isChecked(),
            'x_tick_pad': self.spin_numpad.value(),
            'y_tick_pad': self.spin_numpad.value(),
            # Number format
            'y_notation': self.combo_ynot.currentText(),
            'force_sci': self.chk_force_sci.isChecked(),
            'sci_exp': self.spin_sci_exp.value(),
            # Plot box
            'box_linewidth': self.spin_box_lw.value(),
            'box_color': self.color_box.hex(),
            'manual_layout': self.chk_manual_box.isChecked(),
            'pa_width': self.spin_pa_w.value(),
            'pa_height': self.spin_pa_h.value(),
            'pa_left': self.spin_pa_left.value(),
            'pa_bottom': self.spin_pa_bottom.value(),
            'panel_gap': self.spin_panel_gap.value(),
            'panel_wspace': self.spin_gap.value(),
            # Snap-to-grid (consumed by the figure editor)
            'snap_enabled': self.chk_snap.isChecked(),
            'snap_step': self.spin_snap_step.value(),
        }


# ── Interactive editing dialogs ────────────────────────────────────────────────

class TextEditDialog(QDialog):
    """Edit a matplotlib Text artist: content, size, color, weight."""

    def __init__(self, artist, parent=None):
        super().__init__(parent)
        self.artist = artist
        self.setWindowTitle('Edit text')
        self.setMinimumWidth(320)

        form = QFormLayout(self)
        form.setSpacing(10)

        self.edit = QLineEdit(artist.get_text())
        form.addRow('Text', self.edit)

        self.size = FlatDoubleSpinBox()
        self.size.setRange(4, 60); self.size.setDecimals(1)
        self.size.setValue(float(artist.get_fontsize()))
        form.addRow('Font size', self.size)

        self.color = ColorButton(to_hex(artist.get_color()))
        form.addRow('Color', self.color)

        self.bold = QCheckBox('Bold')
        self.bold.setChecked(str(artist.get_fontweight()) in ('bold', '700', 'heavy', 'semibold'))
        self.italic = QCheckBox('Italic')
        self.italic.setChecked(artist.get_style() == 'italic')
        wr = QHBoxLayout(); wr.addWidget(self.bold); wr.addWidget(self.italic)
        wrw = QWidget(); wrw.setLayout(wr)
        form.addRow('Style', wrw)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def apply(self):
        self.artist.set_text(self.edit.text())
        self.artist.set_fontsize(self.size.value())
        self.artist.set_color(self.color.hex())
        self.artist.set_fontweight('bold' if self.bold.isChecked() else 'normal')
        self.artist.set_style('italic' if self.italic.isChecked() else 'normal')


class LegendEditDialog(QDialog):
    """Edit a matplotlib Legend frame: edge color, edge width, fill alpha, font."""

    def __init__(self, legend, parent=None):
        super().__init__(parent)
        self.legend = legend
        frame = legend.get_frame()
        self.setWindowTitle('Edit legend')
        self.setMinimumWidth(320)

        form = QFormLayout(self)
        form.setSpacing(10)

        self.edge = ColorButton(to_hex(frame.get_edgecolor()))
        form.addRow('Edge color', self.edge)

        edge_rgba = frame.get_edgecolor()
        edge_alpha = edge_rgba[3] if hasattr(edge_rgba, '__len__') and len(edge_rgba) >= 4 else 1.0
        self.edge_transparent = QCheckBox('Transparent edge')
        self.edge_transparent.setChecked(edge_alpha <= 0.01 or frame.get_linewidth() <= 0)
        form.addRow('', self.edge_transparent)

        self.width = FlatDoubleSpinBox()
        self.width.setRange(0.0, 6.0); self.width.setSingleStep(0.1); self.width.setDecimals(1)
        self.width.setValue(float(frame.get_linewidth()))
        form.addRow('Edge width', self.width)

        self.face = ColorButton(to_hex(frame.get_facecolor()))
        form.addRow('Fill color', self.face)

        face_rgba = frame.get_facecolor()
        face_alpha = face_rgba[3] if hasattr(face_rgba, '__len__') and len(face_rgba) >= 4 else 1.0
        self.fill_transparent = QCheckBox('Transparent fill')
        self.fill_transparent.setChecked(face_alpha <= 0.01 or frame.get_alpha() == 0)
        form.addRow('', self.fill_transparent)

        self.alpha = FlatDoubleSpinBox()
        self.alpha.setRange(0.0, 1.0); self.alpha.setSingleStep(0.05); self.alpha.setDecimals(2)
        a = frame.get_alpha()
        self.alpha.setValue(1.0 if a is None else float(a))
        form.addRow('Fill opacity', self.alpha)

        self.fs = FlatDoubleSpinBox()
        self.fs.setRange(4, 40); self.fs.setDecimals(1)
        texts = legend.get_texts()
        self.fs.setValue(float(texts[0].get_fontsize()) if texts else 10.0)
        form.addRow('Font size', self.fs)

        self.frame_on = QCheckBox('Show frame')
        self.frame_on.setChecked(frame.get_visible())
        form.addRow('', self.frame_on)

        self.edge_transparent.toggled.connect(self._toggle_transparent_inputs)
        self.fill_transparent.toggled.connect(self._toggle_transparent_inputs)
        self._toggle_transparent_inputs()

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _toggle_transparent_inputs(self):
        self.edge.setEnabled(not self.edge_transparent.isChecked())
        self.width.setEnabled(not self.edge_transparent.isChecked())
        self.face.setEnabled(not self.fill_transparent.isChecked())
        self.alpha.setEnabled(not self.fill_transparent.isChecked())

    def apply(self):
        frame = self.legend.get_frame()
        if self.edge_transparent.isChecked():
            frame.set_edgecolor('none')
            frame.set_linewidth(0)
        else:
            frame.set_edgecolor(self.edge.hex())
            frame.set_linewidth(self.width.value())
        if self.fill_transparent.isChecked():
            frame.set_facecolor('none')
            frame.set_alpha(0)
        else:
            frame.set_facecolor(self.face.hex())
            frame.set_alpha(self.alpha.value())
        frame.set_visible(self.frame_on.isChecked())
        for t in self.legend.get_texts():
            t.set_fontsize(self.fs.value())


# ── Interactive figure editor ──────────────────────────────────────────────────

class _MoveCommand(QUndoCommand):
    """Undo/redo a single text-artist drag in the figure editor."""

    def __init__(self, artist, before_pos, after_pos, canvas):
        super().__init__('Move')
        self._artist = artist
        self._before = before_pos
        self._after = after_pos
        self._canvas = canvas

    def undo(self):
        self._artist.set_position(self._before)
        self._canvas.draw_idle()

    def redo(self):
        self._artist.set_position(self._after)
        self._canvas.draw_idle()


class FigureEditor:
    """
    Adds direct manipulation to a matplotlib canvas:
      • drag any title / axis label / subtitle to reposition it
      • drag the legend to reposition it
      • double-click a text to edit content, size, color, weight
      • double-click the legend to edit its frame (edge color/width, fill, font)
    """

    def __init__(self, canvas_widget):
        self.cw = canvas_widget
        self.canvas = canvas_widget.canvas
        self._texts = []
        self._legends = []
        self._drag = None      # (artist, press_disp_xy, artist_disp0, start_pos)
        self.snap_enabled = False
        self.snap_step = 0.01  # grid step in figure-relative (0–1) coordinates
        self.undo_stack = QUndoStack()
        self.canvas.mpl_connect('button_press_event', self._on_press)
        self.canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.canvas.mpl_connect('button_release_event', self._on_release)

    def set_snap(self, enabled: bool, step: float):
        self.snap_enabled = bool(enabled)
        if step and step > 0:
            self.snap_step = float(step)

    # collect after every (re)plot
    def refresh(self):
        fig = self.cw.fig
        texts = []
        sup = getattr(fig, '_suptitle', None)
        if sup is not None and sup.get_text():
            texts.append(sup)
        for t in fig.texts:
            if t.get_text():
                texts.append(t)
        for ax in fig.axes:
            if ax.get_title():
                texts.append(ax.title)
            if ax.get_xlabel():
                texts.append(ax.xaxis.label)
            if ax.get_ylabel():
                texts.append(ax.yaxis.label)
        self._texts = texts

        self._legends = [ax.get_legend() for ax in fig.axes if ax.get_legend() is not None]
        for leg in self._legends:
            try:
                leg.set_draggable(True, use_blit=False)
            except Exception:
                pass

    # ── hit testing ──────────────────────────────────────────────────────────
    def _text_at(self, event):
        # iterate in reverse so topmost wins
        for t in reversed(self._texts):
            try:
                hit, _ = t.contains(event)
            except Exception:
                hit = False
            if hit:
                return t
        return None

    def _legend_at(self, event):
        for leg in self._legends:
            try:
                bbox = leg.get_window_extent()
            except Exception:
                continue
            if bbox.contains(event.x, event.y):
                return leg
        return None

    # ── events ──────────────────────────────────────────────────────────────
    def _on_press(self, event):
        if event.x is None or event.y is None:
            return
        if event.dblclick:
            t = self._text_at(event)
            if t is not None:
                self._edit_text(t)
                return
            leg = self._legend_at(event)
            if leg is not None:
                self._edit_legend(leg)
            return
        if event.button != 1:
            return
        # start dragging a text (legends drag themselves via mpl)
        t = self._text_at(event)
        if t is not None and self._legend_at(event) is None:
            x0, y0 = t.get_transform().transform(t.get_position())
            start_pos = tuple(t.get_position())
            self._drag = (t, (event.x, event.y), (x0, y0), start_pos)

    def _on_motion(self, event):
        if self._drag is not None:
            t, (px, py), (x0, y0), _start = self._drag
            if event.x is None:
                return
            newdisp = (x0 + (event.x - px), y0 + (event.y - py))
            # Snap the target to a grid in figure-relative coordinates.
            if self.snap_enabled and self.snap_step > 0:
                fig = self.cw.fig
                fx, fy = fig.transFigure.inverted().transform(newdisp)
                step = self.snap_step
                fx = round(fx / step) * step
                fy = round(fy / step) * step
                newdisp = fig.transFigure.transform((fx, fy))
            newpos = t.get_transform().inverted().transform(newdisp)
            t.set_position(tuple(newpos))
            self.canvas.draw_idle()
            return
        # NOTE: legends drag via matplotlib's own handler (set_draggable), which
        # we can't easily intercept for snapping; custom text snaps as above.
        # hover cursor feedback
        if event.x is None:
            return
        over = (self._text_at(event) is not None) or (self._legend_at(event) is not None)
        self.canvas.setCursor(
            QCursor(Qt.CursorShape.OpenHandCursor if over else Qt.CursorShape.ArrowCursor))

    def _on_release(self, event):
        if self._drag is not None:
            t, start_pos = self._drag[0], self._drag[3]
            end_pos = tuple(t.get_position())
            if end_pos != start_pos:
                self.undo_stack.push(_MoveCommand(t, start_pos, end_pos, self.canvas))
        self._drag = None

    # ── editors ────────────────────────────────────────────────────────────
    def _edit_text(self, t):
        dlg = TextEditDialog(t, self.cw)
        if dlg.exec():
            dlg.apply()
            self.canvas.draw_idle()

    def _edit_legend(self, leg):
        dlg = LegendEditDialog(leg, self.cw)
        if dlg.exec():
            dlg.apply()
            self.canvas.draw_idle()


# ── Plot canvas ───────────────────────────────────────────────────────────────

class PlotCanvas(QWidget):
    size_update_requested = pyqtSignal()
    DISPLAY_DPI = 100  # on-screen pixels per inch of figure

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('canvasArea')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 8)
        lay.setSpacing(0)

        self.card = QWidget()
        self.card.setObjectName('canvasCard')
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        add_shadow(self.card, blur=32, y=10, alpha=28)
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(10, 10, 10, 10)
        card_lay.setSpacing(10)

        self.fig = Figure(facecolor='white', dpi=self.DISPLAY_DPI)
        self.canvas = FigureCanvasQTAgg(self.fig)
        # fixed size — the figure must NOT track the window size
        self.canvas.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.toolbar = NavigationToolbar2QT(self.canvas, self.card)
        self.toolbar.setObjectName('figToolbar')

        # Custom toolbar buttons — separator then Fit / Auto Scale / Grid / Save
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setFixedWidth(1)
        sep.setStyleSheet('background: #B8C5D3;')
        self.toolbar.addWidget(sep)

        self.btn_fit = QToolButton()
        self.btn_fit.setText('Fit')
        self.btn_fit.setToolTip('Reset view to plotted data')
        self.btn_autoscale = QToolButton()
        self.btn_autoscale.setText('Auto Scale')
        self.btn_autoscale.setToolTip('Fit all axes to data')
        self.btn_grid = QToolButton()
        self.btn_grid.setText('Grid')
        self.btn_grid.setToolTip('Toggle grid on all axes')
        self.btn_grid.setCheckable(True)
        self.btn_update_size = QToolButton()
        self.btn_update_size.setText('Update')
        self.btn_update_size.setToolTip('Apply pending figure size')
        self.btn_save_fig = QToolButton()
        self.btn_save_fig.setText('Save')
        self.btn_save_fig.setToolTip('Save figure')
        for _b in (self.btn_fit, self.btn_autoscale, self.btn_grid,
                   self.btn_update_size, self.btn_save_fig):
            _b.setObjectName('figToolbarBtn')
            self.toolbar.addWidget(_b)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        sep2.setFixedWidth(1)
        sep2.setStyleSheet('background: #B8C5D3;')
        self.toolbar.addWidget(sep2)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText('−')
        self.btn_zoom_out.setToolTip('Zoom out')
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText('+')
        self.btn_zoom_in.setToolTip('Zoom in')
        for _b in (self.btn_zoom_out, self.btn_zoom_in):
            _b.setObjectName('figToolbarBtn')
            self.toolbar.addWidget(_b)

        self.btn_fit.clicked.connect(self._toolbar_fit)
        self.btn_autoscale.clicked.connect(self._toolbar_fit)
        self.btn_grid.toggled.connect(self._toolbar_grid)
        self.btn_update_size.clicked.connect(lambda _checked=False: self.size_update_requested.emit())
        self.btn_save_fig.clicked.connect(self.toolbar.save_figure)
        self.btn_zoom_out.clicked.connect(lambda: self._zoom_by(1 / 1.25))
        self.btn_zoom_in.clicked.connect(lambda: self._zoom_by(1.25))

        # scroll-to-zoom on the matplotlib canvas widget
        self.canvas.wheelEvent = self._wheel_zoom

        card_lay.addWidget(self.toolbar)

        # scroll area keeps the figure centered on the gray backdrop and lets
        # large figures scroll instead of being squeezed
        self.scroll = QScrollArea()
        self.scroll.setObjectName('canvasScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        holder = QWidget()
        holder.setObjectName('canvasHolder')
        hv = QVBoxLayout(holder)
        hv.setContentsMargins(20, 20, 20, 20)
        hv.addStretch()
        hrow = QHBoxLayout()
        hrow.addStretch()
        hrow.addWidget(self.canvas)
        hrow.addStretch()
        hv.addLayout(hrow)
        hv.addStretch()
        self.scroll.setWidget(holder)
        card_lay.addWidget(self.scroll)
        lay.addWidget(self.card)

        self.set_fig_size(8.0, 5.0)

    def _toolbar_fit(self):
        for ax in self.fig.axes:
            ax.autoscale()
            ax.relim()
            ax.autoscale_view()
        self.canvas.draw_idle()

    def _toolbar_grid(self, checked: bool):
        for ax in self.fig.axes:
            ax.grid(checked, linestyle='--', linewidth=0.5, alpha=0.5, color='#94A3B8')
        self.canvas.draw_idle()

    def _zoom_by(self, factor: float, cx: float = None, cy: float = None):
        for ax in self.fig.axes:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            xc = cx if cx is not None else (xlim[0] + xlim[1]) / 2
            yc = cy if cy is not None else (ylim[0] + ylim[1]) / 2
            xw = (xlim[1] - xlim[0]) / factor / 2
            yw = (ylim[1] - ylim[0]) / factor / 2
            ax.set_xlim(xc - xw, xc + xw)
            ax.set_ylim(yc - yw, yc + yw)
        self.canvas.draw_idle()

    def _wheel_zoom(self, event):
        delta = event.angleDelta().y()
        if delta == 0 or not self.fig.axes:
            event.ignore()
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        # map cursor to data coordinates on the first axes
        ax = self.fig.axes[0]
        try:
            pos = event.position()
            x_disp = pos.x()
            y_disp = self.canvas.height() - pos.y()
            pt = ax.transData.inverted().transform([x_disp, y_disp])
            cx, cy = float(pt[0]), float(pt[1])
            xl, xr = ax.get_xlim()
            yb, yt = ax.get_ylim()
            if not (xl <= cx <= xr and yb <= cy <= yt):
                cx, cy = None, None
        except Exception:
            cx, cy = None, None
        self._zoom_by(factor, cx, cy)
        event.accept()

    def set_fig_size(self, w_in: float, h_in: float):
        """Lock both the matplotlib figure and the on-screen widget to a fixed size."""
        width_px = int(round(w_in * self.DISPLAY_DPI))
        height_px = int(round(h_in * self.DISPLAY_DPI))
        requested_px = (width_px, height_px)
        if requested_px == self.applied_size_pixels():
            self.mark_size_pending(False)
            return

        # Qt's resizeEvent recalculates figure size as:
        #   w_inches = (logical_px * devicePixelRatio) / figure.dpi
        # On Retina/HiDPI screens devicePixelRatio > 1, so we must scale the
        # DPI by the same factor to keep w_inches = w_in after the event fires.
        dpr = self.canvas.devicePixelRatioF() or 1.0
        self.fig.set_dpi(self.DISPLAY_DPI * dpr)
        self.fig.set_size_inches(w_in, h_in)
        self.canvas.setFixedSize(width_px, height_px)
        self._applied_size_px = requested_px
        self.mark_size_pending(False)

    def applied_size_pixels(self) -> tuple[int, int]:
        return getattr(self, '_applied_size_px', (self.canvas.width(), self.canvas.height()))

    def mark_size_pending(self, pending: bool):
        self.btn_update_size.setEnabled(pending)
        self.btn_update_size.setText('Update *' if pending else 'Update')

    def get_figure(self) -> Figure:
        return self.fig

    def save(self, path: str, fmt: str, dpi: int, width_in: float, height_in: float):
        orig = self.fig.get_size_inches()
        self.fig.set_size_inches(width_in, height_in)
        self.fig.savefig(path, format=fmt, dpi=dpi,
                         bbox_inches='tight', facecolor='white')
        self.fig.set_size_inches(*orig)


# ── Plotting helpers ──────────────────────────────────────────────────────────

class _FixedExpFormatter(ScalarFormatter):
    """ScalarFormatter that forces a fixed power-of-ten on the offset, so the
    Y axis always scales by 10**exp (MATLAB-style ×10^n labels)."""

    def __init__(self, exp: int, **kwargs):
        super().__init__(**kwargs)
        self._fixed_exp = exp

    def _set_order_of_magnitude(self):
        self.orderOfMagnitude = self._fixed_exp


def _apply_font(s: dict):
    """Set the active matplotlib font family (affects axes, ticks, titles,
    legend and exported figures). Falls back to Arial if unavailable."""
    fam = s.get('font_family', 'Arial') or 'Arial'
    try:
        matplotlib.rcParams['font.family'] = [fam, 'Arial', 'DejaVu Sans']
    except Exception:
        matplotlib.rcParams['font.family'] = 'Arial'


def _apply_y_notation(ax, s: dict):
    """Apply the chosen Y-axis number format. Off (Normal) by default."""
    mode = s.get('y_notation', 'Normal')
    if mode.startswith('Scientific'):
        if s.get('force_sci'):
            fmt = _FixedExpFormatter(int(s.get('sci_exp', 3)), useMathText=True)
        else:
            fmt = ScalarFormatter(useMathText=True)
        fmt.set_scientific(True)
        fmt.set_powerlimits((-3, 3))
        ax.yaxis.set_major_formatter(fmt)
        # Keep the exponent label the same size as the axis numbers.
        ax.yaxis.get_offset_text().set_fontsize(s.get('fontsize', 12))
    elif mode.startswith('Engineering'):
        def _k_fmt(val, _pos):
            if abs(val) >= 1000:
                return f'{val / 1000:g}K'
            return f'{val:g}'
        ax.yaxis.set_major_formatter(FuncFormatter(_k_fmt))
    # Normal → leave matplotlib's default formatter untouched.


def _style_ax(ax, is_left: bool, xlabel: str, ylabel: str, s: dict):
    fontsize = s['fontsize']
    box_lw = s.get('box_linewidth', 1.0)
    box_color = s.get('box_color', '#000000')
    for sp in ax.spines.values():
        sp.set_linewidth(box_lw)
        sp.set_color(box_color)

    tick_dir = s.get('tick_dir', 'in')
    length = s.get('tick_length', 4.0)
    width = s.get('tick_width', 0.8)
    show_x = s.get('show_xticks', True)
    show_y = s.get('show_yticks', True)
    show_top = s.get('show_top_ticks', True)
    show_right = s.get('show_right_ticks', True)
    x_tick_pad = s.get('x_tick_pad', 6)
    y_tick_pad = s.get('y_tick_pad', 6)

    ax.set_facecolor('white')

    # Only the left-most panel carries Y tick labels (shared-Y look preserved).
    ax.tick_params(axis='x', which='major', direction=tick_dir,
                   length=length, width=width, labelsize=fontsize, colors='black',
                   bottom=show_x, top=show_top,
                   labelbottom=show_x, labeltop=False, pad=x_tick_pad)
    ax.tick_params(axis='y', which='major', direction=tick_dir,
                   length=length, width=width, labelsize=fontsize, colors='black',
                   left=show_y, right=show_right,
                   labelleft=(show_y and is_left), labelright=False, pad=y_tick_pad)

    # The ×10^n exponent (offset text) doesn't inherit labelsize — match it
    # to the axis-number font so scientific notation stays visually consistent.
    ax.xaxis.get_offset_text().set_fontsize(fontsize)
    ax.yaxis.get_offset_text().set_fontsize(fontsize)

    if s.get('minor_ticks', False):
        ax.minorticks_on()
        ax.tick_params(axis='x', which='minor', direction=tick_dir,
                       length=length * 0.55, width=width * 0.8, colors='black',
                       bottom=show_x, top=show_top)
        ax.tick_params(axis='y', which='minor', direction=tick_dir,
                       length=length * 0.55, width=width * 0.8, colors='black',
                       left=show_y, right=show_right)
    else:
        ax.minorticks_off()

    ax.set_xlabel(xlabel, fontsize=fontsize, color='black', labelpad=7)
    if is_left:
        ax.set_ylabel(ylabel, fontsize=fontsize, color='black', labelpad=7)
    else:
        ax.set_ylabel('')


def _add_legend(ax, handles: list, labels: list, s: dict):
    if not s['show_legend'] or not handles:
        return
    fs = s.get('legend_fontsize', max(6, s['fontsize'] - 1))
    leg = ax.legend(handles, labels, loc=s['legend_loc'],
                    fontsize=fs, fancybox=False, labelspacing=0.25)
    frame = leg.get_frame()
    # Background — transparent by default.
    if s.get('legend_transparent_bg', True):
        frame.set_facecolor('none')
        frame.set_alpha(0)
    else:
        frame.set_facecolor(s.get('legend_bg_color', '#FFFFFF'))
        frame.set_alpha(s.get('legend_bg_alpha', 1.0))
    # Edge.
    if s.get('legend_transparent_edge', False):
        frame.set_edgecolor('none')
        frame.set_linewidth(0)
    else:
        frame.set_edgecolor(s.get('legend_edge_color', '#000000'))
        frame.set_linewidth(s.get('legend_edge_width', 0.8))
    # MATLAB-black legend text.
    for t in leg.get_texts():
        t.set_color('#000000')
        t.set_fontsize(fs)


def _panel_title(ax, idx: int, s: dict):
    if s['show_panel_titles'] and idx < len(s['panel_titles']):
        ax.set_title(s['panel_titles'][idx],
                     fontsize=s['fontsize'], fontweight='bold', color='black', pad=6)


def _load_traces(panel: dict) -> tuple[list, int]:
    """Load visible traces for a panel. Returns (list of (x, y, trace), failed)."""
    result, failed = [], 0
    for tr in panel['traces']:
        if not tr.get('visible', True):
            continue
        x, y = load_file(tr['path'])
        if x is not None:
            result.append((x, y, tr))
        else:
            failed += 1
    return result, failed


def _trace_visual(tr: dict, grad_colors, k: int, use_gradient: bool,
                  default_lw: float):
    """Resolve (color, linewidth, linestyle) for a trace. Edited colors override
    the gradient unless the trace opts into the gradient and gradient mode is on."""
    if use_gradient and tr.get('use_auto_gradient_color', True) and grad_colors:
        color = grad_colors[k]
    else:
        color = tr.get('color', '#000000')
    lw = tr.get('linewidth')
    lw = float(lw) if lw is not None else default_lw
    ls = LINESTYLE_MAP.get(tr.get('linestyle', 'solid'), '-')
    return color, lw, ls


# ── Per-type plot functions ───────────────────────────────────────────────────

def _pl_trace_y(y, baseline_correct: bool):
    """Apply the PL baseline correction used by the original MATLAB scripts."""
    if baseline_correct and len(y):
        return y - y[0]
    return y


def _right_edge_y(line, x_probe: float):
    x = np.asarray(line.get_xdata(), dtype=float)
    y = np.asarray(line.get_ydata(), dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if not np.any(mask):
        return np.nan
    x, y = x[mask], y[mask]
    order = np.argsort(x)
    x, y = x[order], y[order]
    try:
        return float(np.interp(x_probe, x, y))
    except Exception:
        return float(y[-1]) if len(y) else np.nan


def _spaced_label_positions(items: list, min_gap: float) -> list:
    ordered = sorted(items, key=lambda item: item[3])
    spaced = []
    last_y = None
    for line, label, color, y in ordered:
        if not np.isfinite(y):
            continue
        if last_y is not None and y - last_y < min_gap:
            y = last_y + min_gap
        spaced.append((line, label, color, y))
        last_y = y
    return spaced


def _add_xrd_margin_labels(fig: Figure, ax, min_gap: float = 0.25):
    lines = [ln for ln in ax.lines if not str(ln.get_label()).startswith('_')]
    if not lines:
        return
    x_probe = ax.get_xlim()[1]
    items = []
    for line in lines:
        label = line.get_label()
        if not label:
            continue
        color = to_hex(line.get_color())
        items.append((line, label, color, _right_edge_y(line, x_probe)))
    if not items:
        return

    pos = ax.get_position()
    y0, y1 = ax.get_ylim()
    yrange = y1 - y0
    if yrange == 0:
        return
    x_fig = min(pos.x1 + 0.012, 0.985)
    for _line, label, color, y in _spaced_label_positions(items, min_gap):
        y_fig = pos.y0 + ((y - y0) / yrange) * pos.height
        text = fig.text(
            x_fig, y_fig, label,
            ha='left', va='center',
            fontsize=ax.xaxis.label.get_fontsize(),
            color=color,
            clip_on=False,
        )
        text.set_gid('xrd_margin_label')


def _plot_pl(axes: list, s: dict) -> int:
    total_failed = 0
    baseline_correct = s.get('pl_baseline_correct', True)
    for i, ax in enumerate(axes):
        panel = s['panel_data'][i]
        traces, failed = _load_traces(panel)
        total_failed += failed
        corrected = []
        for add_idx, (x, y, tr) in enumerate(traces):
            yc = _pl_trace_y(y, baseline_correct)
            corrected.append((x, yc, float(np.max(yc)), tr, add_idx))
        # Plot order stays highest-peak-first so the gradient + z-order are unchanged.
        corrected.sort(key=lambda t: t[2], reverse=True)

        use_grad = panel.get('use_gradient', True)
        colors = make_gradient(*panel['gradient'], len(corrected)) if use_grad else None
        entries = []  # (peak, add_idx, handle, label) for legend ordering
        for k, (x, y, peak, tr, add_idx) in enumerate(corrected):
            color, lw, lstyle = _trace_visual(tr, colors, k, use_grad, s['linewidth'])
            ln, = ax.plot(x, y, linewidth=lw, color=color, linestyle=lstyle)
            entries.append((peak, add_idx, ln, tr['display_name']))

        # Legend order is independent of plot order: by peak (high→low) or add order.
        if s.get('legend_peak_order', True):
            legend_order = sorted(entries, key=lambda e: e[0], reverse=True)
        else:
            legend_order = sorted(entries, key=lambda e: e[1])
        hs = [e[2] for e in legend_order]
        ls = [e[3] for e in legend_order]

        ylabel = 'Baseline-corrected PL' if baseline_correct else 'PL intensity'
        _style_ax(ax, i == 0, 'Wavelength λ (nm)', ylabel, s)
        _add_legend(ax, hs, ls, s)
        _panel_title(ax, i, s)
    return total_failed


def _plot_absorbance(axes: list, s: dict) -> int:
    ylabel = 'Absorbance (a.u.)'
    total_failed = 0
    for i, ax in enumerate(axes):
        panel = s['panel_data'][i]
        traces, failed = _load_traces(panel)
        total_failed += failed
        with_pk = [(x, y, float(np.max(y)) if len(y) else 0.0, tr)
                   for x, y, tr in traces]
        with_pk.sort(key=lambda t: t[2], reverse=True)

        use_grad = panel.get('use_gradient', True)
        colors = make_gradient(*panel['gradient'], len(with_pk)) if use_grad else None
        hs, ls = [], []
        for k, (x, y, _, tr) in enumerate(with_pk):
            color, lw, lstyle = _trace_visual(tr, colors, k, use_grad, s['linewidth'])
            ln, = ax.plot(x, y, linewidth=lw, color=color, linestyle=lstyle)
            hs.append(ln); ls.append(tr['display_name'])

        _style_ax(ax, i == 0, 'Wavelength λ (nm)', ylabel, s)
        _add_legend(ax, hs, ls, s)
        _panel_title(ax, i, s)
    return total_failed


def _plot_xrd(axes: list, s: dict) -> int:
    use_d = s['xrd_d_spacing']
    lam = s['xrd_lambda']
    total_failed = 0

    def maybe_convert(x, y):
        if not use_d:
            return x, y
        d = two_theta_to_d(x, lam)
        mask = np.isfinite(d)
        d, y = d[mask], y[mask]
        order = np.argsort(d)
        return d[order], y[order]

    ref_traces = []
    for path in s['xrd_ref_paths']:
        x, y = load_file(path)
        if x is not None:
            x, y = maybe_convert(x, y)
            ref_traces.append((x, y, clean_label(os.path.basename(path))))
        else:
            total_failed += 1

    for i, ax in enumerate(axes):
        panel = s['panel_data'][i]
        raw, failed = _load_traces(panel)
        total_failed += failed
        exp_traces = []
        for x, y, tr in raw:
            x2, y2 = maybe_convert(x, y)
            exp_traces.append((x2, y2, tr))

        n_ref, n_exp = len(ref_traces), len(exp_traces)
        n_total = n_ref + n_exp
        offsets = [0.0] * n_total
        for k in range(1, n_total):
            step = s['xrd_ref_step'] if k < n_ref else s['xrd_exp_step']
            offsets[k] = offsets[k - 1] + step

        use_grad = panel.get('use_gradient', True)
        exp_colors = make_gradient(*panel['gradient'], n_exp) if use_grad else None
        hs, ls = [], []
        for k, (x, y, lbl) in enumerate(ref_traces):
            ln, = ax.plot(
                x, y + offsets[k],
                linewidth=s['linewidth'],
                color='black',
                label=lbl,
            )
            hs.append(ln); ls.append(lbl)
        for k, (x, y, tr) in enumerate(exp_traces):
            color, lw, lstyle = _trace_visual(tr, exp_colors, k, use_grad, s['linewidth'])
            ln, = ax.plot(x, y + offsets[n_ref + k], linewidth=lw,
                          color=color, linestyle=lstyle, label=tr['display_name'])
            hs.append(ln); ls.append(tr['display_name'])

        xlabel = 'd-spacing (Å)' if use_d else '2θ (°)'
        _style_ax(ax, i == 0, xlabel, 'Intensity', s)
        _add_legend(ax, hs, ls, s)
        _panel_title(ax, i, s)
        if use_d:
            ax.invert_xaxis()
    return total_failed


# ── Main plot dispatcher ──────────────────────────────────────────────────────

def _axis_limits_with_padding(values) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return -1.0, 1.0
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    pad = 0.05 * (hi - lo)
    if pad == 0:
        pad = 1.0
    return lo - pad, hi + pad


def _load_iv_entries(iv_sets: list[dict]):
    entries = []
    failed = 0
    for set_idx, data_set in enumerate(iv_sets, start=1):
        neg_paths, pos_paths = _iv_sweep_paths(data_set)
        name = str(data_set.get('name') or '').strip() or f'Set {set_idx}'
        color = str(data_set.get('color') or '').strip() or IV_SET_COLORS[(set_idx - 1) % len(IV_SET_COLORS)]
        sweeps = []
        for path in (neg_paths[0], pos_paths[0]):
            voltage, current = load_iv_csv(path)
            if voltage is None:
                failed += 1
                continue
            sweeps.append((voltage, current))
        if sweeps:
            entries.append({'name': name, 'color': color, 'sweeps': sweeps})
    return entries, failed


def _plot_iv(fig: Figure, s: dict) -> int:
    problem = validate_iv_sets(s.get('iv_sets', []))
    if problem:
        raise ValueError(problem)

    entries, failed = _load_iv_entries(s.get('iv_sets', []))
    if not entries:
        raise ValueError('No valid IV data could be loaded from the selected CSV files.')

    all_voltage = np.concatenate([voltage for entry in entries for voltage, _current in entry['sweeps']])
    all_current = np.concatenate([current for entry in entries for _voltage, current in entry['sweeps']])
    scale, unit = choose_iv_current_unit(float(np.max(np.abs(all_current))))

    ax = fig.subplots(1, 1)
    handles, labels = [], []
    for entry in entries:
        legend_line = None
        for voltage, current in entry['sweeps']:
            line, = ax.plot(
                voltage,
                current * scale,
                color=entry['color'],
                linestyle='-',
                marker='None',
                linewidth=s.get('linewidth', 2.0),
            )
            if legend_line is None:
                legend_line = line
        if legend_line is not None:
            handles.append(legend_line)
            labels.append(entry['name'])

    _style_ax(ax, True, 'Voltage (V)', f'Current ({unit})', s)
    _add_legend(ax, handles, labels, s)
    ax.set_xlim(*_axis_limits_with_padding(all_voltage))
    ax.set_ylim(*_axis_limits_with_padding(all_current * scale))
    try:
        fig.tight_layout(pad=1.5)
    except Exception:
        pass
    return failed


def do_plot(fig: Figure, s: dict) -> str:
    fig.clear()
    fig.set_facecolor('white')

    _apply_font(s)

    pt = s['plot_type']
    if pt == 'iv':
        failed = _plot_iv(fig, s)
        fig.canvas.draw_idle()
        msg = 'Done — IV curve.'
        if failed:
            msg += f'  ({failed} file(s) failed to load — check format)'
        return msg

    n = s['n_panels']
    axes = fig.subplots(1, n, sharey=False)
    if n == 1:
        axes = [axes]

    if pt == 'pl':
        failed = _plot_pl(axes, s)
    elif pt == 'absorbance':
        failed = _plot_absorbance(axes, s)
    else:
        failed = _plot_xrd(axes, s)

    has_title = s['show_main_title'] and s['main_title']
    has_sub = s['show_subtitle'] and s['subtitle']
    xrd_margin_labels = pt == 'xrd' and s.get('xrd_margin_labels', False)
    right_rect = 0.86 if xrd_margin_labels else 1.0
    top_rect = 0.93
    if has_title or has_sub:
        top_rect = 0.86
        if has_title:
            fig.suptitle(s['main_title'], fontsize=s['fontsize'] + 2,
                         fontweight='bold', color='black', y=0.98)
        if has_sub:
            ysub = 0.945 if has_title else 0.975
            fig.text(0.5, ysub, s['subtitle'], fontsize=s['fontsize'],
                     color='#555', ha='center', va='top')

    if s.get('manual_layout', False):
        # MATLAB-style explicit axes geometry in figure-fraction coordinates,
        # bypassing tight_layout so the plot box obeys the Plot Box controls.
        left = s.get('pa_left', 0.10)
        bottom = s.get('pa_bottom', 0.12)
        total_w = s.get('pa_width', 0.84)
        if xrd_margin_labels:
            total_w = min(total_w, max(0.02, right_rect - left))
        total_h = s.get('pa_height', 0.78)
        gap = s.get('panel_gap', 0.04)
        pw = max(0.02, (total_w - (n - 1) * gap) / n)
        for j, ax in enumerate(axes):
            ax.set_position([left + j * (pw + gap), bottom, pw, total_h])
    else:
        try:
            fig.tight_layout(pad=1.5, rect=[0, 0, right_rect, top_rect])
        except Exception:
            pass
        if n > 1:
            try:
                fig.subplots_adjust(wspace=s.get('panel_wspace', 0.30))
            except Exception:
                pass

    reverse_x = s['plot_type'] == 'xrd' and s['xrd_d_spacing']
    if s.get('separate_x_limits', False):
        panel_limits = s.get('panel_x_limits', [])
        for idx, ax in enumerate(axes):
            limit_cfg = panel_limits[idx] if idx < len(panel_limits) else {}
            if not limit_cfg.get('auto_x', False):
                xmin = limit_cfg.get('x_min', s['x_min'])
                xmax = limit_cfg.get('x_max', s['x_max'])
                if reverse_x:
                    ax.set_xlim(xmax, xmin)
                else:
                    ax.set_xlim(xmin, xmax)
    elif not s['auto_x']:
        for ax in axes:
            if reverse_x:
                ax.set_xlim(s['x_max'], s['x_min'])
            else:
                ax.set_xlim(s['x_min'], s['x_max'])

    if not s['auto_y']:
        for ax in axes:
            ax.set_ylim(s['y_min'], s['y_max'])
    elif s['share_y'] and n > 1:
        lo = min(ax.get_ylim()[0] for ax in axes)
        hi = max(ax.get_ylim()[1] for ax in axes)
        if np.isfinite(lo) and np.isfinite(hi):
            for ax in axes:
                ax.set_ylim(lo, hi)

    # Y-axis number format — applied after limits so a forced exponent sticks.
    for ax in axes:
        _apply_y_notation(ax, s)

    if xrd_margin_labels:
        _add_xrd_margin_labels(
            fig,
            axes[-1],
            min_gap=s.get('xrd_margin_label_gap', 0.25),
        )

    fig.canvas.draw_idle()

    msg = f'Done — {n} panel(s), {pt.upper()}.'
    if failed:
        msg += f'  ({failed} file(s) failed to load — check format)'
    return msg


# ── Main window ───────────────────────────────────────────────────────────────

def create_loading_screen() -> QSplashScreen:
    pixmap = QPixmap(440, 240)
    pixmap.fill(QColor('#FFFFFF'))

    splash = QSplashScreen(pixmap)
    splash.setObjectName('loadingScreen')
    splash.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    splash.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    layout = QVBoxLayout(splash)
    layout.setContentsMargins(34, 30, 34, 28)
    layout.setSpacing(10)

    title = QLabel('SPECTRAplot')
    title.setObjectName('loadingTitle')
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)

    subtitle = QLabel('PL  ·  ABSORBANCE  ·  XRD  ·  IV')
    subtitle.setObjectName('loadingSubtitle')
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

    status = QLabel('Preparing plotting workspace...')
    status.setObjectName('loadingStatus')
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)

    progress = QProgressBar()
    progress.setObjectName('loadingProgress')
    progress.setRange(0, 0)
    progress.setTextVisible(False)

    layout.addStretch(1)
    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addSpacing(18)
    layout.addWidget(progress)
    layout.addWidget(status)
    layout.addStretch(1)

    return splash


class BottomStatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('bottomStatusBar')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(26)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 12, 0)
        lay.setSpacing(5)

        self._dot = QLabel('●')
        self._dot.setObjectName('readyDot')
        self._state = QLabel('Ready')
        self._state.setObjectName('stateLabel')
        self._msg = QLabel()
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._coord = QLabel()
        self._coord.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._coord.setObjectName('coordLabel')
        self._coord.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        lay.addWidget(self._dot)
        lay.addWidget(self._state)
        lay.addSpacing(6)
        lay.addWidget(self._msg)
        lay.addWidget(self._coord)

    def show_message(self, msg: str):
        self._msg.setText(msg)

    def update_coords(self, text: str):
        self._coord.setText(text)

    def clear_coords(self):
        self._coord.clear()

    def set_ready(self, ok: bool):
        color = '#22C55E' if ok else '#EF4444'
        self._dot.setStyleSheet(f'QLabel {{ color: {color}; font-size: 11px; font-weight: 700; }}')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SPECTRAplot')
        self.resize(1300, 820)
        self.setMinimumSize(920, 580)

        self._current_mode = MODES[0]['key']

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self.controls = ControlPanel()
        self.canvas = PlotCanvas()
        self.controls._canvas = self.canvas
        self.editor = FigureEditor(self.canvas)

        # ── Dock card (bottom control strip) ─────────────────────────────
        dock = QWidget()
        dock.setObjectName('dock')
        dock_lay = QVBoxLayout(dock)
        dock_lay.setContentsMargins(14, 6, 14, 10)
        dock_lay.setSpacing(0)

        dock_card = QWidget()
        dock_card.setObjectName('dockCard')
        dock_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        add_shadow(dock_card, blur=28, y=8, alpha=28)
        dock_card_lay = QHBoxLayout(dock_card)
        dock_card_lay.setContentsMargins(12, 10, 12, 10)
        dock_card_lay.setSpacing(12)
        for group in self.controls.take_dock_groups():
            # Expanding lets Qt stretch all groups to the same height — no more
            # janky height mismatch between Ticks / Numbers / Legend / Plot Box.
            group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            dock_card_lay.addWidget(group)

        dock_scroll = QScrollArea()
        dock_scroll.setWidget(dock_card)
        dock_scroll.setWidgetResizable(True)
        dock_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        dock_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        dock_scroll.setFrameShape(QFrame.Shape.NoFrame)
        dock_scroll.setObjectName('dockScroll')
        dock_lay.addWidget(dock_scroll)

        # ── Right pane: canvas + resizable dock via vertical splitter ─────
        self.right_pane = QWidget()
        self.right_pane.setObjectName('rightPane')
        right_lay = QVBoxLayout(self.right_pane)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.setObjectName('vSplitter')
        self.v_splitter.setHandleWidth(5)
        self.v_splitter.addWidget(self.canvas)
        self.v_splitter.addWidget(dock)
        self.v_splitter.setStretchFactor(0, 1)
        self.v_splitter.setStretchFactor(1, 0)
        # dock starts at ~220px; canvas takes the rest
        self.v_splitter.setSizes([560, 220])

        self.statusbar = BottomStatusBar()
        right_lay.addWidget(self.v_splitter, 1)
        right_lay.addWidget(self.statusbar)

        splitter.addWidget(self.controls)
        splitter.addWidget(self.right_pane)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Root: header bar on top, sidebar+canvas splitter below
        root = QWidget()
        root.setObjectName('appRoot')
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        self.header = TopHeader()
        vlay.addWidget(self.header)
        vlay.addWidget(splitter)
        self.setCentralWidget(root)

        undo_sc = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_sc.activated.connect(self.editor.undo_stack.undo)

        self._has_plotted = False
        self.controls.plot_requested.connect(self._do_plot)
        self.controls.live_update_requested.connect(self._auto_replot)
        self.header.plot_requested.connect(self._do_plot)
        self.header.mode_changed.connect(self._on_mode_change)
        self.header.theme_toggled.connect(self._on_theme_toggle)
        self.controls.spin_fw.valueChanged.connect(self._mark_canvas_size_pending)
        self.controls.spin_fh.valueChanged.connect(self._mark_canvas_size_pending)
        self.canvas.size_update_requested.connect(self._update_canvas_size)
        self.controls.chk_snap.toggled.connect(self._update_snap)
        self.controls.spin_snap_step.valueChanged.connect(self._update_snap)
        self.canvas.canvas.mpl_connect('motion_notify_event', self._on_coord_motion)

        self.statusbar.show_message('Ready — add files to a panel and click Plot.')
        self._apply_accent(MODES[0]['accent'])

    def _apply_accent(self, accent: str):
        QApplication.instance().setStyleSheet(build_style(accent, _APP_DARK))

    def _on_mode_change(self, key: str):
        self._current_mode = key
        self._apply_accent(MODE_BY_KEY[key]['accent'])
        self.controls.set_mode(key)

    def _on_theme_toggle(self, dark: bool):
        global _APP_DARK
        _APP_DARK = dark
        self.header.btn_theme.setText('Light' if dark else 'Dark')
        self.header.apply_theme(dark)
        accent = MODE_BY_KEY[self._current_mode]['accent']
        QApplication.instance().setStyleSheet(build_style(accent, dark))

    def _on_coord_motion(self, event):
        if event.inaxes is None:
            self.statusbar.clear_coords()
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            self.statusbar.clear_coords()
            return
        mode = self._current_mode
        if mode == 'pl':
            y_str = f'{y:.3g}' if abs(y) >= 1000 or (abs(y) < 0.01 and y != 0) else f'{y:.2f}'
            text = f'Wavelength: {x:.2f} nm   PL: {y_str}'
        elif mode == 'absorbance':
            text = f'Wavelength: {x:.2f} nm   Abs: {y:.4f}'
        elif mode == 'xrd':
            if self.controls.chk_d.isChecked():
                text = f'd-spacing: {x:.3f} Å   Intensity: {y:.0f}'
            else:
                text = f'2θ: {x:.2f}°   Intensity: {y:.0f}'
        elif mode == 'iv':
            text = f'Voltage: {x:.3g} V   Current: {y:.4g}'
        else:
            text = f'x: {x:.3f}   y: {y:.4g}'
        self.statusbar.update_coords(text)

    def _mark_canvas_size_pending(self, *_):
        requested = (self.controls.spin_fw.value(), self.controls.spin_fh.value())
        self.canvas.mark_size_pending(requested != self.canvas.applied_size_pixels())

    def _update_canvas_size(self):
        self.canvas.set_fig_size(
            self.controls.spin_fw.value() / 100, self.controls.spin_fh.value() / 100)
        self.canvas.canvas.draw_idle()
        self.statusbar.show_message(
            f'Figure size updated to {self.controls.spin_fw.value()} x {self.controls.spin_fh.value()} px.'
        )

    def _update_snap(self, *_):
        self.editor.set_snap(
            self.controls.chk_snap.isChecked(),
            self.controls.spin_snap_step.value())

    def _auto_replot(self):
        """Live-refresh the figure after a trace/legend change — but only once a
        plot already exists, and without popping the 'No Data' / error dialogs."""
        if self._has_plotted:
            self._do_plot(silent=True)

    def _do_plot(self, silent: bool = False):
        s = self.controls.settings()
        if s['plot_type'] == 'iv':
            problem = validate_iv_sets(s.get('iv_sets', []))
            if problem:
                if not silent:
                    QMessageBox.information(self, 'Missing IV Data', problem)
                return
        else:
            has_data = any(len(p['traces']) > 0 for p in s['panel_data'])
            has_xrd_refs = s['plot_type'] == 'xrd' and len(s['xrd_ref_paths']) > 0
            if not has_data and not has_xrd_refs:
                if not silent:
                    QMessageBox.information(
                        self, 'No Data',
                        'Add at least one file to a panel, then click Plot.'
                    )
                return
        self.statusbar.show_message('Plotting…')
        self.canvas.set_fig_size(s['fig_width'] / 100, s['fig_height'] / 100)
        self.editor.set_snap(s['snap_enabled'], s['snap_step'])
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()
        try:
            msg = do_plot(self.canvas.get_figure(), s)
            self.editor.refresh()
            self._has_plotted = True
            self.statusbar.show_message(msg + '   ·   Double-click figure text to edit · drag to reposition.')
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, 'Plot Error', str(e))
            self.statusbar.show_message(f'Error: {e}')
        finally:
            QApplication.restoreOverrideCursor()


# ── Entry point ───────────────────────────────────────────────────────────────

def _load_bundled_fonts():
    """Load Montserrat (and any other bundled fonts) from assets/ if present."""
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
    for fname in ('Montserrat-ExtraBold.ttf', 'Montserrat-Light.ttf',
                  'Montserrat-Bold.ttf', 'Montserrat-Regular.ttf'):
        path = os.path.join(assets, fname)
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)


def main():
    if sys.platform == 'darwin':
        os.environ.setdefault('QT_MAC_WANTS_LAYER', '1')
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    _load_bundled_fonts()
    app.setStyleSheet(build_style(MODES[0]['accent']))
    app.setFont(QFont('Segoe UI', 9))
    splash = create_loading_screen()
    splash.show()
    app.processEvents()
    win = MainWindow()
    win.show()
    splash.finish(win)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
