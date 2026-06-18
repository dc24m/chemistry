#!/usr/bin/env python3
"""
SpectraPlot — Chemistry Spectrometry Plotting Tool
PL · Absorbance · XRD
"""

import sys
import os
import re
import json
import time
import uuid
from dataclasses import dataclass


def resource_path(*parts) -> str:
    """Return absolute path to a bundled resource (works frozen via PyInstaller or from source)."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)

try:
    import numpy as np

    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    from matplotlib.figure import Figure
    from matplotlib.colors import to_rgb, to_hex
    from matplotlib.ticker import ScalarFormatter, FuncFormatter
    from matplotlib.patches import Rectangle

    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QAbstractSpinBox, QCheckBox, QLineEdit, QFileDialog, QScrollArea,
        QGroupBox, QColorDialog, QMessageBox, QListWidget, QListWidgetItem,
        QAbstractItemView, QTabWidget,
        QSizePolicy, QDialog, QDialogButtonBox, QFormLayout,
        QButtonGroup, QSplashScreen, QProgressBar,
        QToolButton, QFrame, QSlider, QToolBar,
        QDockWidget, QPlainTextEdit, QStackedWidget,
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QEvent
    from PyQt6.QtGui import (QFont, QColor, QCursor, QPixmap, QFontDatabase,
                              QUndoStack, QUndoCommand, QKeySequence,
                              QAction, QActionGroup)
except ModuleNotFoundError as exc:
    missing = exc.name or 'a required package'
    raise SystemExit(
        f"SPECTRAplot could not start because '{missing}' is not installed for:\n"
        f"  {sys.executable}\n\n"
        "Install the app dependencies with:\n"
        "  python -m pip install -r requirements_spectra.txt"
    ) from exc

import spectra_theme
from spectra_theme import (
    MODES, MODE_BY_KEY, darken, add_shadow, build_style, s, vs, init_ui_scale,
    set_ui_font,
)

matplotlib.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'Liberation Sans'],
    'axes.unicode_minus': False,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'savefig.facecolor': 'white',
    'mathtext.fontset': 'dejavusans',
})


_APP_DARK = False   # global dark-mode state toggled by the header button



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
        'uid': uuid.uuid4().hex,   # stable id so canvas edits map back to this record
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


class NoScrollSlider(QSlider):
    """Slider that ignores wheel events — must be clicked/dragged to change."""
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
            f'border:1px solid rgba(0,0,0,0.18); border-radius:6px; '
            f'min-height:{s(26)}px; max-height:{s(26)}px; padding:{s(3)}px {s(8)}px; '
            f'font-size:{s(12)}px; font-weight:700; }}'
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

@dataclass
class FigureState:
    canvas: object
    editor: object
    mode:   str
    label:  str
    # Snapshot of the control panel's data inputs (traces, IV sweeps, XRD refs)
    # for this figure, so switching tabs restores what was loaded. None = empty.
    data:   dict = None


class FigureTabBar(QWidget):
    figure_selected      = pyqtSignal(int)
    figure_close_requested = pyqtSignal(int)
    figure_add_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('figureTabBar')
        self.setFixedHeight(s(36))
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(s(8), s(4), s(8), s(4))
        self._layout.setSpacing(s(4))
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._slots: list[tuple[QPushButton, QPushButton]] = []  # (tab_btn, close_btn)

        self._add_btn = QPushButton('+')
        self._add_btn.setObjectName('figureAddBtn')
        self._add_btn.setFixedHeight(s(26))
        self._add_btn.setFixedWidth(s(32))
        self._add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._add_btn.clicked.connect(self.figure_add_requested)
        self._layout.addWidget(self._add_btn)
        self._layout.addStretch()

    def add_figure(self, label: str):
        idx = len(self._slots)
        slot = QWidget()
        slot_lay = QHBoxLayout(slot)
        slot_lay.setContentsMargins(0, 0, 0, 0)
        slot_lay.setSpacing(s(2))

        tab_btn = QPushButton(label)
        tab_btn.setObjectName('figureTab')
        tab_btn.setCheckable(True)
        tab_btn.setFixedHeight(s(26))
        tab_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        tab_btn.clicked.connect(lambda _, i=idx: self.figure_selected.emit(i))
        self._group.addButton(tab_btn)

        close_btn = QPushButton('×')
        close_btn.setObjectName('figureTabClose')
        close_btn.setFixedHeight(s(20))
        close_btn.setFixedWidth(s(18))
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(lambda _, i=idx: self.figure_close_requested.emit(i))
        close_btn.setVisible(False)  # hidden until >1 tab

        slot_lay.addWidget(tab_btn)
        slot_lay.addWidget(close_btn)
        self._slots.append((tab_btn, close_btn))

        # Insert before the "+" button (which is at position 0)
        self._layout.insertWidget(idx, slot)
        self._update_close_visibility()

    def remove_figure(self, idx: int):
        if idx >= len(self._slots):
            return
        tab_btn, _ = self._slots[idx]
        self._group.removeButton(tab_btn)
        slot_widget = self._layout.itemAt(idx).widget()
        self._layout.removeWidget(slot_widget)
        slot_widget.deleteLater()
        self._slots.pop(idx)
        # Re-wire click signals for shifted indices
        for i, (btn, cbtn) in enumerate(self._slots):
            try:
                btn.clicked.disconnect()
            except RuntimeError:
                pass
            try:
                cbtn.clicked.disconnect()
            except RuntimeError:
                pass
            btn.clicked.connect(lambda _, n=i: self.figure_selected.emit(n))
            cbtn.clicked.connect(lambda _, n=i: self.figure_close_requested.emit(n))
        self._update_close_visibility()

    def set_active(self, idx: int):
        if 0 <= idx < len(self._slots):
            self._slots[idx][0].setChecked(True)

    def _update_close_visibility(self):
        show = len(self._slots) > 1
        for _, close_btn in self._slots:
            close_btn.setVisible(show)


class ModeTabBar(QWidget):
    mode_changed = pyqtSignal(str)

    # Hard per-tab minimum widths so long labels never clip, regardless of font.
    _MIN_W = {'pl': 190, 'absorbance': 142, 'xrd': 78, 'iv': 96}

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(s(6))
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
            floor = s(self._MIN_W.get(m['key'], 130))
            measured = b.fontMetrics().horizontalAdvance(m['label']) + s(34)
            b.setMinimumWidth(max(floor, measured))
            b.setMinimumHeight(s(34))
            b.clicked.connect(lambda _, k=m['key']: self._select(k))
            self._group.addButton(b)
            self.buttons[m['key']] = b
            row.addWidget(b)
        self.buttons[MODES[0]['key']].setChecked(True)
        self._current = MODES[0]['key']

    def _select(self, key: str):
        if key in self.buttons:
            self.buttons[key].setChecked(True)
        self._current = key
        self.mode_changed.emit(key)

    def set_current(self, key: str):
        if key not in self.buttons:
            return
        self._current = key
        self.buttons[key].setChecked(True)

    def current(self) -> str:
        return self._current


# ── Top header bar ────────────────────────────────────────────────────────────

class TopHeader(QWidget):
    mode_changed = pyqtSignal(str)
    theme_toggled = pyqtSignal(bool)
    plot_requested = pyqtSignal()

    # Fallback font stack if Montserrat is unavailable
    _TITLE_FF = "'Segoe UI Variable','Segoe UI','IBM Plex Sans','Inter',sans-serif"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('topHeader')
        self.setFixedHeight(s(80))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(s(14), 0, s(14), 0)
        lay.setSpacing(0)

        # ── Logo image (assets/logo.png, optional)
        logo_path = resource_path('assets', 'logo.png')
        if os.path.isfile(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setObjectName('logoImg')
            # Render at the screen's native pixel density so it stays crisp on Retina.
            scr = QApplication.primaryScreen()
            dpr = scr.devicePixelRatio() if scr else 1.0
            pix = QPixmap(logo_path).scaled(
                int(s(48) * dpr), int(s(48) * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            pix.setDevicePixelRatio(dpr)
            logo_lbl.setPixmap(pix)
            logo_lbl.setFixedSize(s(48), s(48))
            lay.addWidget(logo_lbl)
            lay.addSpacing(s(11))

        # ── Brand block: SPECTRA + plot title over subtitle
        brand = QWidget()
        brand.setObjectName('brandBlock')
        bcol = QVBoxLayout(brand)
        bcol.setContentsMargins(0, 0, 0, 0)
        bcol.setSpacing(0)

        self._title_lbl = QLabel()
        self._title_lbl.setObjectName('appTitle')
        self._title_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._title_lbl.setContentsMargins(0, 0, 0, 0)
        self._set_title_colors('#171717', '#5F5F5F')
        subtitle = QLabel('by Arnold Wijoyo')
        subtitle.setObjectName('brandSub')
        # Pull the byline up tight under the title.
        subtitle.setContentsMargins(0, s(-4), 0, 0)

        bcol.addStretch()
        bcol.addWidget(self._title_lbl)
        bcol.addWidget(subtitle)
        bcol.addStretch()
        lay.addWidget(brand)
        lay.addSpacing(s(22))

        self.mode_tabs = ModeTabBar()
        self.mode_tabs.mode_changed.connect(self.mode_changed)
        lay.addWidget(self.mode_tabs)

        lay.addStretch()

        self.btn_plot = QPushButton('PLOT')
        self.btn_plot.setObjectName('headerPlotBtn')
        self.btn_plot.setFixedHeight(s(42))
        self.btn_plot.setMinimumWidth(s(96))
        self.btn_plot.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_plot.clicked.connect(self.plot_requested)
        lay.addWidget(self.btn_plot)
        lay.addSpacing(s(8))

        self.btn_theme = QPushButton('Dark')
        self.btn_theme.setObjectName('themeToggle')
        self.btn_theme.setCheckable(True)
        self.btn_theme.setFixedSize(s(62), s(36))
        self.btn_theme.toggled.connect(self.theme_toggled)
        lay.addWidget(self.btn_theme)

    def _set_title_colors(self, ink: str, muted: str):
        ff = spectra_theme.UI_FONT_FAMILY
        self._title_lbl.setText(
            f'<span style="font-family:{ff};font-size:{s(30)}px;font-weight:800;'
            f'letter-spacing:0;color:{ink};">SPECTRA</span>'
            f'<span style="font-family:{ff};font-size:{s(30)}px;font-weight:300;'
            f'color:{muted};">plot</span>'
        )

    def apply_theme(self, dark: bool):
        self._set_title_colors('#D4D4D4' if dark else '#171717',
                               '#6A6A6A' if dark else '#5F5F5F')
        self.btn_theme.setText('Light' if dark else 'Dark')


# ── Trace edit dialog ─────────────────────────────────────────────────────────

class TraceEditDialog(QDialog):
    """Edit one trace: display name, color, gradient opt-out, visibility,
    line-width override and line style."""

    def __init__(self, trace: dict, parent=None):
        super().__init__(parent)
        self.trace = trace
        self.setWindowTitle('Edit Trace')
        self.setMinimumWidth(s(340))

        form = QFormLayout(self)
        form.setSpacing(s(10))

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


class ReferenceEditDialog(QDialog):
    """Edit one XRD reference: label, color, line-width override, line style.
    Reads/writes the ControlPanel parallel lists at index `idx`, so the list box
    and the figure-pane double-click share exactly the same editor."""

    def __init__(self, idx: int, parent=None, controls=None):
        super().__init__(parent)
        self.idx = idx
        self.controls = controls
        self.setWindowTitle('Edit Reference')
        self.setMinimumWidth(s(340))

        form = QFormLayout(self)
        form.setSpacing(s(10))

        cur_label = controls.xrd_ref_labels[idx] if idx < len(controls.xrd_ref_labels) else ''
        cur_color = controls.xrd_ref_colors[idx] if idx < len(controls.xrd_ref_colors) else '#000000'
        cur_w = controls.xrd_ref_widths[idx] if idx < len(controls.xrd_ref_widths) else None
        cur_ls = controls.xrd_ref_styles[idx] if idx < len(controls.xrd_ref_styles) else 'solid'

        self.edit_name = QLineEdit(cur_label)
        form.addRow('Label', self.edit_name)

        path = controls.xrd_ref_paths[idx] if idx < len(controls.xrd_ref_paths) else ''
        lbl_file = QLabel(os.path.basename(path) or '—')
        lbl_file.setObjectName('hint')
        lbl_file.setWordWrap(True)
        lbl_file.setToolTip(path)
        form.addRow('File', lbl_file)

        self.color = ColorButton(cur_color)
        form.addRow('Color', self.color)

        self.chk_lw = QCheckBox('Override line width')
        self.spin_lw = FlatDoubleSpinBox()
        self.spin_lw.setRange(0.2, 10.0); self.spin_lw.setSingleStep(0.5); self.spin_lw.setDecimals(1)
        self.chk_lw.setChecked(cur_w is not None)
        self.spin_lw.setValue(float(cur_w) if cur_w is not None else 2.0)
        self.spin_lw.setEnabled(cur_w is not None)
        self.chk_lw.toggled.connect(self.spin_lw.setEnabled)
        lw_row = QHBoxLayout(); lw_row.addWidget(self.chk_lw); lw_row.addWidget(self.spin_lw)
        lw_w = QWidget(); lw_w.setLayout(lw_row)
        form.addRow('Line width', lw_w)

        self.combo_ls = QComboBox()
        self.combo_ls.addItems(LINESTYLE_LABELS)
        if cur_ls in LINESTYLE_LABELS:
            self.combo_ls.setCurrentText(cur_ls)
        form.addRow('Line style', self.combo_ls)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def apply(self):
        c = self.controls
        i = self.idx
        name = self.edit_name.text().strip()
        if i < len(c.xrd_ref_labels) and name:
            c.xrd_ref_labels[i] = name
        if i < len(c.xrd_ref_colors):
            c.xrd_ref_colors[i] = self.color.hex()
        if i < len(c.xrd_ref_widths):
            c.xrd_ref_widths[i] = self.spin_lw.value() if self.chk_lw.isChecked() else None
        if i < len(c.xrd_ref_styles):
            c.xrd_ref_styles[i] = self.combo_ls.currentText()


# ── Per-row trace widget (name label + eye toggle) ───────────────────────────

class _TraceRow(QWidget):
    """Label + eye button for one trace entry in the file list."""

    def __init__(self, trace: dict, on_change=None, parent=None):
        super().__init__(parent)
        self._trace = trace
        self._on_change = on_change

        lay = QHBoxLayout(self)
        lay.setContentsMargins(s(6), 0, s(2), 0)
        lay.setSpacing(s(4))

        self.lbl = QLabel()
        self.lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.btn = QToolButton()
        self.btn.setFixedSize(s(26), s(22))
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
            f'QToolButton {{ border: none; background: transparent; font-size: {s(14)}px; '
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
        lay.setContentsMargins(s(10), s(10), s(10), s(10))
        lay.setSpacing(s(8))

        self.lst = QListWidget()
        self.lst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lst.setMinimumHeight(s(75))
        self.lst.setMaximumHeight(s(220))
        self.lst.itemDoubleClicked.connect(self._edit_double)
        lay.addWidget(self.lst)

        br = QHBoxLayout()
        br.setSpacing(s(6))
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
            row.setSpacing(s(8))
            lbl = QLabel(label_text)
            lbl.setFixedWidth(s(96))
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

    def clear(self):
        """Drop every trace from this panel. Used to give a freshly added
        figure an empty data box (does not emit `changed`)."""
        self.lst.clear()
        self.traces.clear()

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

    def get_state(self) -> dict:
        """Snapshot this panel for per-figure persistence. Trace dicts are kept
        by reference (each belongs to one figure) so in-place edits survive."""
        return {
            'traces': list(self.traces),
            'gradient': (self.c_top.hex(), self.c_bot.hex()),
            'use_gradient': self.chk_gradient.isChecked(),
        }

    def set_state(self, st: dict):
        """Repopulate this panel from a get_state() snapshot, without emitting
        `changed` (the caller triggers a single refresh)."""
        self.clear()
        g = st.get('gradient', ('#000000', '#000000'))
        self.c_top.set_hex(g[0])
        self.c_bot.set_hex(g[1])
        self.chk_gradient.blockSignals(True)
        self.chk_gradient.setChecked(st.get('use_gradient', True))
        self.chk_gradient.blockSignals(False)
        self._toggle_gradient(self.chk_gradient.isChecked())
        for tr in st.get('traces', []):
            self.traces.append(tr)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 30))
            self.lst.addItem(item)
            self.lst.setItemWidget(item, _TraceRow(tr, self.changed.emit))


# ── Helpers ───────────────────────────────────────────────────────────────────

class IVDataSetWidget(QWidget):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.neg_path = ''
        self.pos_path = ''

        lay = QVBoxLayout(self)
        lay.setContentsMargins(s(4), s(8), s(4), s(8))
        lay.setSpacing(s(10))

        meta = QGroupBox('Set identity')
        meta_lay = QFormLayout(meta)
        meta_lay.setContentsMargins(s(8), s(14), s(8), s(8))
        meta_lay.setVerticalSpacing(s(8))
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
        row.setSpacing(s(6))
        title_label = QLabel(title)
        title_label.setObjectName('fieldlbl')
        path_label = QLabel('No CSV selected')
        path_label.setObjectName('hint')
        path_label.setMinimumWidth(s(120))
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        btn_browse = QPushButton('Browse')
        btn_browse.setObjectName('secondary')
        btn_clear = QPushButton('X')
        btn_clear.setObjectName('danger')
        btn_clear.setFixedWidth(s(34))
        btn_browse.clicked.connect(browse_handler)
        btn_clear.clicked.connect(clear_handler)

        file_row = QHBoxLayout()
        file_row.setSpacing(s(6))
        file_row.addWidget(title_label)
        file_row.addWidget(path_label, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(s(6))
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

    def clear(self):
        """Forget both sweep CSVs so a freshly added figure starts empty."""
        self.neg_path = ''
        self.pos_path = ''
        self._refresh_sweep_labels()

    def get_state(self) -> dict:
        return {'name': self.edit_name.text(), 'color': self.color.hex(),
                'neg_path': self.neg_path, 'pos_path': self.pos_path}

    def set_state(self, st: dict):
        self.edit_name.blockSignals(True)
        self.edit_name.setText(st.get('name', ''))
        self.edit_name.blockSignals(False)
        self.color.set_hex(st.get('color', self.color.hex()))
        self.neg_path = st.get('neg_path', '')
        self.pos_path = st.get('pos_path', '')
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


def _labeled(label_text: str, widget: QWidget, lw: int = 90) -> QHBoxLayout:
    r = QHBoxLayout()
    r.setSpacing(s(8))
    lbl = QLabel(label_text)
    lbl.setFixedWidth(s(lw))
    lbl.setObjectName('fieldlbl')
    r.addWidget(lbl)
    r.addWidget(widget)
    return r


def _sep() -> QLabel:
    sep = QLabel()
    sep.setFixedHeight(s(1))
    sep.setStyleSheet(f'background: #E2E8F0; margin: {s(4)}px 0;')
    return sep


# ── Control panel ─────────────────────────────────────────────────────────────

class ControlPanel(QScrollArea):
    plot_requested = pyqtSignal()
    live_update_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('sidebar')
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedWidth(s(368))

        root = QWidget()
        root.setObjectName('sidebar')
        root.setMinimumWidth(0)
        root.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setWidget(root)

        lay = QVBoxLayout(root)
        lay.setContentsMargins(s(8), vs(8), s(8), vs(12))
        lay.setSpacing(vs(6))

        self._current_mode = MODES[0]['key']

        # ── Plot panels
        self.g_plot = QGroupBox('Plot')
        gl = QVBoxLayout(self.g_plot)
        gl.setSpacing(vs(9))
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
        dgl.setContentsMargins(s(8), vs(16), s(8), vs(8))
        dgl.setSpacing(vs(6))
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
        iv_lay.setContentsMargins(s(4), vs(14), s(4), vs(8))
        iv_lay.setSpacing(vs(8))
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
        agl.setSpacing(vs(9))

        xrow = QHBoxLayout(); xrow.setSpacing(s(5))
        xl = QLabel('X range'); xl.setFixedWidth(s(66)); xl.setObjectName('fieldlbl')
        self.spin_xmin = FlatDoubleSpinBox()
        self.spin_xmax = FlatDoubleSpinBox()
        for sb in (self.spin_xmin, self.spin_xmax):
            sb.setRange(-9999, 99999); sb.setDecimals(1)
            sb.setMinimumWidth(s(56))
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spin_xmin.setValue(400); self.spin_xmax.setValue(800)
        dash = QLabel('–'); dash.setStyleSheet('color:#8a93a0;')
        dash.setFixedWidth(s(12)); dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        pxrow = QHBoxLayout(); pxrow.setSpacing(s(5))
        pxl = QLabel('X range'); pxl.setFixedWidth(s(66)); pxl.setObjectName('fieldlbl')
        self.spin_pxmin = FlatDoubleSpinBox()
        self.spin_pxmax = FlatDoubleSpinBox()
        for sb in (self.spin_pxmin, self.spin_pxmax):
            sb.setRange(-9999, 99999); sb.setDecimals(1)
            sb.setMinimumWidth(s(56))
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spin_pxmin.setValue(400); self.spin_pxmax.setValue(800)
        pdash = QLabel('–'); pdash.setStyleSheet('color:#8a93a0;')
        pdash.setFixedWidth(s(12)); pdash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pxrow.addWidget(pxl); pxrow.addWidget(self.spin_pxmin, 1)
        pxrow.addWidget(pdash); pxrow.addWidget(self.spin_pxmax, 1)
        agl.addLayout(pxrow)
        # The per-panel editor widgets are disabled until "separate" is enabled.
        self._sepx_widgets = [self.combo_xpanel, self.chk_pauto_x,
                              self.spin_pxmin, self.spin_pxmax]
        self._toggle_separate_x(False)

        agl.addWidget(_sep())

        yrow = QHBoxLayout(); yrow.setSpacing(s(5))
        yl = QLabel('Y range'); yl.setFixedWidth(s(66)); yl.setObjectName('fieldlbl')
        self.spin_ymin = FlatDoubleSpinBox()
        self.spin_ymax = FlatDoubleSpinBox()
        for sb in (self.spin_ymin, self.spin_ymax):
            sb.setRange(-9999999, 9999999); sb.setDecimals(2)
            sb.setMinimumWidth(s(56))
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.spin_ymin.setValue(0); self.spin_ymax.setValue(1)
        dash2 = QLabel('–'); dash2.setStyleSheet('color:#8a93a0;')
        dash2.setFixedWidth(s(12)); dash2.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        lgl.setSpacing(vs(7))
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
        sgl.setSpacing(vs(9))

        self.spin_lw = FlatDoubleSpinBox()
        self.spin_lw.setRange(0.5, 6.0); self.spin_lw.setSingleStep(0.5); self.spin_lw.setValue(1.5)
        sgl.addLayout(_labeled('Line width', self.spin_lw))

        self.spin_fs = FlatSpinBox()
        self.spin_fs.setRange(6, 28); self.spin_fs.setValue(16)
        sgl.addLayout(_labeled('Font size', self.spin_fs))

        sgl.addWidget(_sep())

        fw_row = QHBoxLayout(); fw_row.setSpacing(s(5))
        fw_lbl = QLabel('Size (px)'); fw_lbl.setFixedWidth(s(66)); fw_lbl.setObjectName('fieldlbl')
        self.spin_fw = FlatSpinBox()
        self.spin_fh = FlatSpinBox()
        for sb in (self.spin_fw, self.spin_fh):
            sb.setRange(100, 3000); sb.setSingleStep(50); sb.setMaximumWidth(s(78))
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
        appl.setSpacing(vs(4))
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
        tgl.setSpacing(vs(4))
        tgl.setContentsMargins(s(8), vs(6), s(8), vs(6))
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
        self.spin_tick_w.setDecimals(1); self.spin_tick_w.setValue(2.0)
        tgl.addLayout(_labeled('Tick width', self.spin_tick_w))
        tgl.addStretch(1)

        # ── Number format (axis notation)
        g_num = QGroupBox('Axis Numbers')
        ngl = QVBoxLayout(g_num)
        ngl.setSpacing(vs(4))
        ngl.setContentsMargins(s(8), vs(6), s(8), vs(6))
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
        self.slider_numpad = NoScrollSlider(Qt.Orientation.Horizontal)
        self.slider_numpad.setRange(0, 30)
        self.slider_numpad.setValue(10)
        self.spin_numpad = FlatSpinBox()
        self.spin_numpad.setRange(0, 30)
        self.spin_numpad.setValue(10)
        self.spin_numpad.setFixedWidth(s(44))
        self.slider_numpad.valueChanged.connect(self.spin_numpad.setValue)
        self.spin_numpad.valueChanged.connect(self.slider_numpad.setValue)
        self.slider_numpad.valueChanged.connect(lambda _: self.plot_requested.emit())
        _dist_row = QHBoxLayout()
        _dist_row.setSpacing(s(6))
        _lbl_dist = QLabel('Distance')
        _lbl_dist.setFixedWidth(s(70))
        _lbl_dist.setObjectName('fieldlbl')
        _dist_row.addWidget(_lbl_dist)
        _dist_row.addWidget(self.slider_numpad, 1)
        _dist_row.addWidget(self.spin_numpad)
        ngl.addLayout(_dist_row)
        ngl.addStretch(1)

        # ── Legend (full customization; transparent background by default)
        g_legend = QGroupBox('Legend')
        lgll = QFormLayout(g_legend)
        lgll.setVerticalSpacing(vs(4))
        lgll.setContentsMargins(s(8), vs(6), s(8), vs(6))
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
        self.spin_legend_alpha.setFixedWidth(s(56))
        _bg_row = QHBoxLayout(); _bg_row.setSpacing(s(4))
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
        self.spin_legend_edge_w.setFixedWidth(s(56))
        _edge_row = QHBoxLayout(); _edge_row.setSpacing(s(4))
        _edge_row.addWidget(self.color_legend_edge); _edge_row.addWidget(self.spin_legend_edge_w)
        _edge_w = QWidget(); _edge_w.setLayout(_edge_row)
        lgll.addRow('Edge / w', _edge_w)
        self.spin_legend_fs = FlatDoubleSpinBox()
        self.spin_legend_fs.setRange(4.0, 40.0); self.spin_legend_fs.setSingleStep(1.0)
        self.spin_legend_fs.setDecimals(1); self.spin_legend_fs.setValue(16.0)
        lgll.addRow('Font size', self.spin_legend_fs)
        self.spin_legend_spacing = FlatDoubleSpinBox()
        self.spin_legend_spacing.setRange(0.0, 3.0); self.spin_legend_spacing.setSingleStep(0.05)
        self.spin_legend_spacing.setDecimals(2); self.spin_legend_spacing.setValue(0.25)
        lgll.addRow('Entry spacing', self.spin_legend_spacing)
        self.chk_legend_2col = QCheckBox('2 columns')
        lgll.addRow(self.chk_legend_2col)
        self.combo_legend_align = NoScrollComboBox()
        self.combo_legend_align.addItems(['left', 'center', 'right'])
        lgll.addRow('Label align', self.combo_legend_align)
        self.chk_legend_markerfirst = QCheckBox('Markers on left')
        self.chk_legend_markerfirst.setChecked(True)
        lgll.addRow(self.chk_legend_markerfirst)

        # ── Plot Box (axis box, tick-label padding, manual geometry, snap)
        g_box = QGroupBox('Plot Box')
        bgl = QFormLayout(g_box)
        bgl.setVerticalSpacing(vs(4))
        bgl.setContentsMargins(s(8), vs(6), s(8), vs(6))
        bgl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.spin_box_lw = FlatDoubleSpinBox()
        self.spin_box_lw.setRange(0.2, 6.0); self.spin_box_lw.setSingleStep(0.1)
        self.spin_box_lw.setDecimals(1); self.spin_box_lw.setValue(2.0)
        self.color_box = ColorButton('#000000')
        _box_row = QHBoxLayout(); _box_row.setSpacing(s(4))
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
        plgl.setSpacing(vs(9))
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
        xgl.setSpacing(vs(9))
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
        ref_lbl = QLabel('Reference traces:')
        ref_lbl.setObjectName('fieldlbl')
        xgl.addWidget(ref_lbl)
        self.xrd_ref_list = QListWidget()
        self.xrd_ref_list.setMaximumHeight(s(90))
        self.xrd_ref_paths: list[str] = []
        self.xrd_ref_colors: list[str] = []   # per-reference colour (double-click to change)
        self.xrd_ref_labels: list[str] = []   # per-reference legend label
        self.xrd_ref_widths: list = []        # per-reference line width override (None = global)
        self.xrd_ref_styles: list[str] = []   # per-reference line style
        self.xrd_ref_list.itemDoubleClicked.connect(
            lambda item: self.edit_reference(self.xrd_ref_list.row(item)))
        xgl.addWidget(self.xrd_ref_list)
        xrd_br = QHBoxLayout(); xrd_br.setSpacing(s(6))
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
        egl.setSpacing(vs(9))
        self.spin_dpi = FlatSpinBox()
        self.spin_dpi.setRange(72, 600); self.spin_dpi.setSingleStep(50); self.spin_dpi.setValue(300)
        egl.addLayout(_labeled('DPI', self.spin_dpi))
        fmt_row = QHBoxLayout(); fmt_row.setSpacing(s(6))
        for fmt in ('PNG', 'PDF', 'SVG'):
            b = QPushButton(fmt); b.setObjectName('secondary')
            b.clicked.connect(lambda checked, f=fmt.lower(): self._save(f))
            fmt_row.addWidget(b)
        egl.addLayout(fmt_row)
        lay.addWidget(g6)

        lay.addStretch()

        self._canvas = None
        self.before_save = None   # MainWindow sets this to clear canvas selection pre-export

        # Pressing Enter/Return in any spin box, line edit or combo pushes an
        # immediate replot, so parameter tweaks apply without clicking Plot.
        for w in (self.findChildren(QAbstractSpinBox)
                  + self.findChildren(QLineEdit)
                  + self.findChildren(QComboBox)):
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            if isinstance(obj, QAbstractSpinBox):
                obj.interpretText()   # commit typed text to value() before plotting
            self.plot_requested.emit()
            return False
        return super().eventFilter(obj, event)

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
                self.xrd_ref_colors.append('#000000')
                self.xrd_ref_labels.append(clean_label(os.path.basename(p)))
                self.xrd_ref_widths.append(None)
                self.xrd_ref_styles.append('solid')
                self.xrd_ref_list.addItem(clean_label(os.path.basename(p)))

    def _xrd_rem_refs(self):
        rows = sorted(
            [self.xrd_ref_list.row(i) for i in self.xrd_ref_list.selectedItems()],
            reverse=True
        )
        for r in rows:
            self.xrd_ref_list.takeItem(r)
            self.xrd_ref_paths.pop(r)
            for lst in (self.xrd_ref_colors, self.xrd_ref_labels,
                        self.xrd_ref_widths, self.xrd_ref_styles):
                if r < len(lst):
                    lst.pop(r)

    def edit_reference(self, idx: int):
        """Open the shared edit box for reference at `idx` (list or canvas)."""
        if idx < 0 or idx >= len(self.xrd_ref_paths):
            return
        dlg = ReferenceEditDialog(idx, self, self)
        if dlg.exec():
            dlg.apply()
            self.refresh_xrd_ref_list()
            self.plot_requested.emit()

    # ── canvas-edit write-backs (used by FigureEditor) ──────────────────────────
    def find_trace_by_uid(self, uid: str):
        for pw in self.panel_widgets:
            for tr in pw.traces:
                if tr.get('uid') == uid:
                    return tr
        return None
    def set_trace_color_by_uid(self, uid: str, hexcol: str) -> bool:
        """Recolour the trace with this uid (double-click on the plot)."""
        for pw in self.panel_widgets:
            for tr in pw.traces:
                if tr.get('uid') == uid:
                    tr['color'] = hexcol
                    tr['use_auto_gradient_color'] = False
                    return True
        return False

    def set_trace_label_by_uid(self, uid: str, label: str) -> bool:
        for pw in self.panel_widgets:
            for tr in pw.traces:
                if tr.get('uid') == uid:
                    tr['display_name'] = label
                    return True
        return False

    def refresh_xrd_ref_list(self):
        self.xrd_ref_list.clear()
        for lbl in self.xrd_ref_labels:
            self.xrd_ref_list.addItem(lbl)

    def _save(self, fmt: str):
        if self._canvas is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f'Save as {fmt.upper()}', '',
            f'{fmt.upper()} files (*.{fmt});;All files (*.*)'
        )
        if path:
            if self.before_save:
                self.before_save()   # strip on-canvas selection highlight before export
            try:
                self._canvas.save(path, fmt, self.spin_dpi.value(),
                                  self.spin_fw.value() / 100, self.spin_fh.value() / 100)
            except Exception as e:
                QMessageBox.critical(self, 'Save Error', str(e))

    def reset_data(self):
        """Clear every loaded data source (traces, IV sweeps, XRD references)
        so a freshly added figure starts with an empty data box. Style settings
        are intentionally left untouched."""
        for pw in self.panel_widgets:
            pw.clear()
        for iv in self.iv_widgets:
            iv.clear()
        self.xrd_ref_paths.clear()
        self.xrd_ref_colors.clear()
        self.xrd_ref_labels.clear()
        self.xrd_ref_widths.clear()
        self.xrd_ref_styles.clear()
        self.xrd_ref_list.clear()

    def capture_data(self) -> dict:
        """Snapshot a figure's full state — data AND style — so reselecting its
        tab restores everything. Style reuses the preset machinery; axes and
        labels (not part of presets) are captured here too."""
        self._flush_xpanel()
        return {
            # ── Data ──
            'n_panels': self.spin_panels.value(),
            'panels': [pw.get_state() for pw in self.panel_widgets],
            'n_iv': self.spin_iv_sets.value(),
            'iv': [iv.get_state() for iv in self.iv_widgets],
            'xrd_refs': list(self.xrd_ref_paths),
            'xrd_ref_colors': list(self.xrd_ref_colors),
            'xrd_ref_labels': list(self.xrd_ref_labels),
            'xrd_ref_widths': list(self.xrd_ref_widths),
            'xrd_ref_styles': list(self.xrd_ref_styles),
            # ── Style (Plot Style dock + graph appearance) ──
            'style': self._style_preset(),
            # ── Axes (Build panel) ──
            'axis': {
                'auto_x': self.chk_auto_x.isChecked(),
                'x_min': self.spin_xmin.value(),
                'x_max': self.spin_xmax.value(),
                'separate_x': self.chk_separate_x.isChecked(),
                'panel_x': [dict(d) for d in self._panel_x],
                'xpanel_idx': self._xpanel_idx,
                'auto_y': self.chk_auto_y.isChecked(),
                'y_min': self.spin_ymin.value(),
                'y_max': self.spin_ymax.value(),
                'share_y': self.chk_share_y.isChecked(),
                'panel_gap': self.spin_gap.value(),
            },
            # ── Labels (Build panel) ──
            'titles': {
                'show_main': self.chk_main_title.isChecked(),
                'main': self.edit_main_title.text(),
                'show_sub': self.chk_subtitle.isChecked(),
                'sub': self.edit_subtitle.text(),
                'show_panel': self.chk_panel_titles.isChecked(),
                'panel': self.edit_panel_titles.text(),
            },
        }

    def restore_data(self, snap: dict):
        """Reload a figure's full state from a capture_data() snapshot. A falsy
        snapshot (e.g. a brand-new figure) resets to an empty data box while
        leaving style at its defaults."""
        if not snap:
            self.reset_data()
            return

        def _val(w, v):
            w.blockSignals(True); w.setValue(v); w.blockSignals(False)

        def _chk(w, v):
            w.blockSignals(True); w.setChecked(bool(v)); w.blockSignals(False)

        def _txt(w, v):
            w.blockSignals(True); w.setText(v); w.blockSignals(False)

        # ── Data ──
        _val(self.spin_panels, snap.get('n_panels', 1))
        self._on_panels_change(self.spin_panels.value())
        for pw, st in zip(self.panel_widgets, snap.get('panels', [])):
            pw.set_state(st)
        _val(self.spin_iv_sets, snap.get('n_iv', self.spin_iv_sets.value()))
        self._on_iv_sets_change(self.spin_iv_sets.value())
        for iv, st in zip(self.iv_widgets, snap.get('iv', [])):
            iv.set_state(st)
        self.xrd_ref_paths = list(snap.get('xrd_refs', []))
        self.xrd_ref_colors = list(snap.get('xrd_ref_colors', []))
        self.xrd_ref_labels = list(snap.get('xrd_ref_labels', []))
        self.xrd_ref_widths = list(snap.get('xrd_ref_widths', []))
        self.xrd_ref_styles = list(snap.get('xrd_ref_styles', []))
        # Backfill parallel lists for older snapshots / mismatched lengths.
        while len(self.xrd_ref_colors) < len(self.xrd_ref_paths):
            self.xrd_ref_colors.append('#000000')
        while len(self.xrd_ref_labels) < len(self.xrd_ref_paths):
            self.xrd_ref_labels.append(
                clean_label(os.path.basename(self.xrd_ref_paths[len(self.xrd_ref_labels)])))
        while len(self.xrd_ref_widths) < len(self.xrd_ref_paths):
            self.xrd_ref_widths.append(None)
        while len(self.xrd_ref_styles) < len(self.xrd_ref_paths):
            self.xrd_ref_styles.append('solid')
        self.refresh_xrd_ref_list()

        # ── Style ──
        self._apply_style_preset(snap.get('style', {}))

        # ── Axes ──
        a = snap.get('axis', {})
        _chk(self.chk_auto_x, a.get('auto_x', True))
        _val(self.spin_xmin, a.get('x_min', 400.0))
        _val(self.spin_xmax, a.get('x_max', 800.0))
        _chk(self.chk_separate_x, a.get('separate_x', False))
        self._panel_x = [dict(d) for d in a.get('panel_x', self._panel_x)]
        self._xpanel_idx = a.get('xpanel_idx', 0)
        self.combo_xpanel.blockSignals(True)
        self.combo_xpanel.setCurrentIndex(self._xpanel_idx)
        self.combo_xpanel.blockSignals(False)
        _chk(self.chk_auto_y, a.get('auto_y', True))
        _val(self.spin_ymin, a.get('y_min', 0.0))
        _val(self.spin_ymax, a.get('y_max', 1.0))
        _chk(self.chk_share_y, a.get('share_y', True))
        _val(self.spin_gap, a.get('panel_gap', 0.30))

        # ── Labels ──
        t = snap.get('titles', {})
        _chk(self.chk_main_title, t.get('show_main', False))
        _txt(self.edit_main_title, t.get('main', ''))
        _chk(self.chk_subtitle, t.get('show_sub', False))
        _txt(self.edit_subtitle, t.get('sub', ''))
        _chk(self.chk_panel_titles, t.get('show_panel', True))
        _txt(self.edit_panel_titles, t.get('panel', ''))

        # Refresh enable/visibility states that the blocked setters skipped.
        self._toggle_separate_x(self.chk_separate_x.isChecked())
        self._toggle_xlim()
        self._toggle_ylim()
        self._toggle_sci()
        self._toggle_manual_box(self.chk_manual_box.isChecked())
        self._toggle_legend()
        if not self.chk_separate_x.isChecked():
            self._load_xpanel(self._xpanel_idx)

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
            'legend_labelspacing': self.spin_legend_spacing.value(),
            'legend_2col': self.chk_legend_2col.isChecked(),
            'legend_alignment': self.combo_legend_align.currentText(),
            'legend_markerfirst': self.chk_legend_markerfirst.isChecked(),
            'legend_peak_order': self.chk_legend_peak_order.isChecked(),
            'pl_baseline_correct': self.chk_pl_baseline.isChecked(),
            'xrd_d_spacing': self.chk_d.isChecked(),
            'xrd_lambda': self.spin_lam.value(),
            'xrd_ref_step': self.spin_ref_step.value(),
            'xrd_exp_step': self.spin_exp_step.value(),
            'xrd_margin_labels': self.chk_xrd_margin_labels.isChecked(),
            'xrd_margin_label_gap': self.spin_xrd_label_gap.value(),
            'xrd_ref_paths': list(self.xrd_ref_paths),
            'xrd_ref_colors': list(self.xrd_ref_colors),
            'xrd_ref_labels': list(self.xrd_ref_labels),
            'xrd_ref_widths': list(self.xrd_ref_widths),
            'xrd_ref_styles': list(self.xrd_ref_styles),
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


    # Keys from settings() that represent pure style (safe to save/restore as presets)
    _PRESET_KEYS = {
        'linewidth', 'fontsize', 'font_family', 'fig_width', 'fig_height',
        'tick_dir', 'show_xticks', 'show_yticks', 'show_top_ticks', 'show_right_ticks',
        'minor_ticks', 'tick_length', 'tick_width', 'x_tick_pad', 'y_tick_pad',
        'y_notation', 'force_sci', 'sci_exp',
        'show_legend', 'legend_loc', 'legend_transparent_bg', 'legend_bg_color',
        'legend_bg_alpha', 'legend_transparent_edge', 'legend_edge_color',
        'legend_edge_width', 'legend_fontsize', 'legend_peak_order',
        'legend_alignment', 'legend_markerfirst', 'legend_labelspacing', 'legend_2col',
        'box_linewidth', 'box_color', 'manual_layout',
        'pa_width', 'pa_height', 'pa_left', 'pa_bottom', 'panel_gap',
        'snap_enabled', 'snap_step',
        'pl_baseline_correct',
        'xrd_d_spacing', 'xrd_lambda', 'xrd_ref_step', 'xrd_exp_step',
        'xrd_margin_labels', 'xrd_margin_label_gap',
    }

    def _style_preset(self) -> dict:
        return {k: v for k, v in self.settings().items() if k in self._PRESET_KEYS}

    def _apply_style_preset(self, p: dict):
        def _set(widget, val):
            widget.blockSignals(True)
            widget.setValue(val)
            widget.blockSignals(False)
        if 'linewidth'              in p: _set(self.spin_lw, p['linewidth'])
        if 'fontsize'               in p: _set(self.spin_fs, p['fontsize'])
        if 'fig_width'              in p: _set(self.spin_fw, p['fig_width'])
        if 'fig_height'             in p: _set(self.spin_fh, p['fig_height'])
        if 'tick_length'            in p: _set(self.spin_tick_len, p['tick_length'])
        if 'tick_width'             in p: _set(self.spin_tick_w, p['tick_width'])
        if 'x_tick_pad'             in p:
            _set(self.spin_numpad, p['x_tick_pad'])
            _set(self.slider_numpad, p['x_tick_pad'])
        if 'box_linewidth'          in p: _set(self.spin_box_lw, p['box_linewidth'])
        if 'legend_bg_alpha'        in p: _set(self.spin_legend_alpha, p['legend_bg_alpha'])
        if 'legend_edge_width'      in p: _set(self.spin_legend_edge_w, p['legend_edge_width'])
        if 'legend_fontsize'        in p: _set(self.spin_legend_fs, p['legend_fontsize'])
        if 'legend_labelspacing'    in p: _set(self.spin_legend_spacing, p['legend_labelspacing'])
        if 'pa_width'               in p: _set(self.spin_pa_w, p['pa_width'])
        if 'pa_height'              in p: _set(self.spin_pa_h, p['pa_height'])
        if 'pa_left'                in p: _set(self.spin_pa_left, p['pa_left'])
        if 'pa_bottom'              in p: _set(self.spin_pa_bottom, p['pa_bottom'])
        if 'panel_gap'              in p: _set(self.spin_panel_gap, p['panel_gap'])
        if 'snap_step'              in p: _set(self.spin_snap_step, p['snap_step'])
        if 'xrd_lambda'             in p: _set(self.spin_lam, p['xrd_lambda'])
        if 'xrd_ref_step'           in p: _set(self.spin_ref_step, p['xrd_ref_step'])
        if 'xrd_exp_step'           in p: _set(self.spin_exp_step, p['xrd_exp_step'])
        if 'xrd_margin_label_gap'   in p: _set(self.spin_xrd_label_gap, p['xrd_margin_label_gap'])
        if 'sci_exp'                in p: _set(self.spin_sci_exp, p['sci_exp'])
        # Checkboxes
        for attr, key in [
            (self.chk_xticks,              'show_xticks'),
            (self.chk_yticks,              'show_yticks'),
            (self.chk_top_ticks,           'show_top_ticks'),
            (self.chk_right_ticks,         'show_right_ticks'),
            (self.chk_minor_ticks,         'minor_ticks'),
            (self.chk_legend,              'show_legend'),
            (self.chk_legend_transp_bg,    'legend_transparent_bg'),
            (self.chk_legend_transp_edge,  'legend_transparent_edge'),
            (self.chk_legend_peak_order,   'legend_peak_order'),
            (self.chk_legend_2col,         'legend_2col'),
            (self.chk_legend_markerfirst,  'legend_markerfirst'),
            (self.chk_manual_box,          'manual_layout'),
            (self.chk_snap,                'snap_enabled'),
            (self.chk_pl_baseline,         'pl_baseline_correct'),
            (self.chk_d,                   'xrd_d_spacing'),
            (self.chk_xrd_margin_labels,   'xrd_margin_labels'),
            (self.chk_force_sci,           'force_sci'),
        ]:
            if key in p:
                attr.blockSignals(True)
                attr.setChecked(p[key])
                attr.blockSignals(False)
        # Combos
        if 'tick_dir'      in p: self.combo_tick_dir.setCurrentText(p['tick_dir'])
        if 'y_notation'    in p: self.combo_ynot.setCurrentText(p['y_notation'])
        if 'legend_loc'    in p: self.combo_legend_loc.setCurrentText(p['legend_loc'])
        if 'legend_alignment' in p: self.combo_legend_align.setCurrentText(p['legend_alignment'])
        if 'font_family'   in p: self.combo_font.setCurrentText(p['font_family'])
        # Color buttons
        if 'box_color'         in p: self.color_box.set_hex(p['box_color'])
        if 'legend_bg_color'   in p: self.color_legend_bg.set_hex(p['legend_bg_color'])
        if 'legend_edge_color' in p: self.color_legend_edge.set_hex(p['legend_edge_color'])

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Preset', '', 'JSON Preset (*.json)')
        if not path:
            return
        if not path.endswith('.json'):
            path += '.json'
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._style_preset(), f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, 'Save Failed', str(e))

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load Preset', '', 'JSON Preset (*.json)')
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            self._apply_style_preset(data)
        except Exception as e:
            QMessageBox.warning(self, 'Load Failed', str(e))


# ── Interactive editing dialogs ────────────────────────────────────────────────

class TextEditDialog(QDialog):
    """Edit a matplotlib Text artist: content, size, color, weight."""

    def __init__(self, artist, parent=None):
        super().__init__(parent)
        self.artist = artist
        self.setWindowTitle('Edit text')
        self.setMinimumWidth(s(320))

        form = QFormLayout(self)
        form.setSpacing(s(10))

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
    """Edit a matplotlib Legend: per-entry label text, alignment, marker side,
    plus frame edge color/width, fill alpha and font."""

    def __init__(self, legend, parent=None, controls=None):
        super().__init__(parent)
        self.legend = legend
        self.controls = controls
        self.needs_replot = False
        frame = legend.get_frame()
        self.setWindowTitle('Edit legend')
        self.setMinimumWidth(s(320))

        form = QFormLayout(self)
        form.setSpacing(s(10))

        # ── Per-entry label text ───────────────────────────────────────────────
        self._sources = list(getattr(legend, '_spectra_sources', None) or [])
        self.label_edits = []
        for i, txt in enumerate(legend.get_texts()):
            le = QLineEdit(txt.get_text())
            self.label_edits.append(le)
            form.addRow(f'Label {i + 1}', le)
        if self.label_edits:
            form.addRow(_sep())

        # ── Layout: alignment + marker side ────────────────────────────────────
        self.align = NoScrollComboBox()
        self.align.addItems(['left', 'center', 'right'])
        if controls is not None:
            self.align.setCurrentText(controls.combo_legend_align.currentText())
        form.addRow('Label align', self.align)

        self.markerfirst = QCheckBox('Markers on left')
        self.markerfirst.setChecked(
            controls.chk_legend_markerfirst.isChecked() if controls is not None else True)
        form.addRow('', self.markerfirst)
        form.addRow(_sep())

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

        # Per-entry label text: apply in place and write back to the data sources.
        for i, le in enumerate(self.label_edits):
            new = le.text()
            if i < len(self.legend.get_texts()):
                self.legend.get_texts()[i].set_text(new)
            if self.controls is not None and i < len(self._sources):
                kind, key = self._sources[i]
                if kind == 'trace':
                    self.controls.set_trace_label_by_uid(key, new)
                elif kind == 'xrdref' and 0 <= key < len(self.controls.xrd_ref_labels):
                    self.controls.xrd_ref_labels[key] = new
        if self.controls is not None:
            self.controls.refresh_xrd_ref_list()

        # Alignment + marker side live on the control panel; changing them needs a
        # rebuild (matplotlib can't flip markerfirst on an existing legend).
        if self.controls is not None:
            new_align = self.align.currentText()
            new_mf = self.markerfirst.isChecked()
            if (new_align != self.controls.combo_legend_align.currentText()
                    or new_mf != self.controls.chk_legend_markerfirst.isChecked()):
                self.needs_replot = True
            self.controls.combo_legend_align.setCurrentText(new_align)
            self.controls.chk_legend_markerfirst.setChecked(new_mf)
        if self.label_edits:
            self.needs_replot = True   # ensure renamed labels survive future replots


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

    _SEL_BBOX = dict(boxstyle='round,pad=0.25', facecolor='none',
                     edgecolor='#1E88E5', linewidth=1.3)

    def __init__(self, canvas_widget):
        self.cw = canvas_widget
        self.canvas = canvas_widget.canvas
        self._texts = []                 # editable Text artists (current plot)
        self._role_by_artist = {}        # id(artist) -> stable role str or None
        self._legends = []
        self._selected = []              # multi-selection of Text artists
        self._drag = None                # dict while dragging
        self._press = None               # dict between press and release
        self._box_selected = False       # plot-box resize mode
        self._box_artists = []           # overlay outline + handle patches
        self._box_drag = None            # dict while resizing the plot box
        self.snap_enabled = False
        self.snap_step = 0.01            # grid step in figure-relative coords
        self.overrides = {}              # role -> {text,fontsize,color,bold,italic,pos}
        self.controls = None             # ControlPanel, set by MainWindow
        self.request_replot = None       # callable, set by MainWindow
        self.undo_stack = QUndoStack()
        self.canvas.mpl_connect('button_press_event', self._on_press)
        self.canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.canvas.mpl_connect('button_release_event', self._on_release)

    def set_snap(self, enabled: bool, step: float):
        self.snap_enabled = bool(enabled)
        if step and step > 0:
            self.snap_step = float(step)

    @staticmethod
    def _mods():
        m = QApplication.keyboardModifiers()
        shift = bool(m & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(m & (Qt.KeyboardModifier.ControlModifier
                         | Qt.KeyboardModifier.MetaModifier))
        return shift, ctrl

    # collect after every (re)plot, then re-apply persisted manual edits
    def refresh(self):
        fig = self.cw.fig
        texts, roles = [], {}

        def add(artist, role):
            texts.append(artist)
            roles[id(artist)] = role

        sup = getattr(fig, '_suptitle', None)
        if sup is not None and sup.get_text():
            add(sup, 'suptitle')
        sub_assigned = False
        for t in fig.texts:
            if not t.get_text():
                continue
            if t.get_gid() == 'xrd_margin_label':
                add(t, None)            # auto-generated; draggable but not persisted
            elif not sub_assigned:
                add(t, 'subtitle'); sub_assigned = True
            else:
                add(t, None)
        for pidx, ax in enumerate(fig.axes):
            if ax.get_title():
                add(ax.title, f'title:{pidx}')
            if ax.get_xlabel():
                add(ax.xaxis.label, f'xlabel:{pidx}')
            if ax.get_ylabel():
                add(ax.yaxis.label, f'ylabel:{pidx}')
        self._texts = texts
        self._role_by_artist = roles
        self._selected = []             # artists were recreated; drop stale selection
        self._box_artists = []          # overlay was wiped by fig.clear()
        self._box_selected = False
        self._box_drag = None

        self._legends = [ax.get_legend() for ax in fig.axes if ax.get_legend() is not None]
        for leg in self._legends:
            try:
                leg.set_draggable(True, use_blit=False)
            except Exception:
                pass

        self._apply_overrides()

    def _apply_overrides(self):
        """Re-apply manual figure edits after a rebuild so they survive replots."""
        for artist in self._texts:
            role = self._role_by_artist.get(id(artist))
            ov = self.overrides.get(role) if role else None
            if not ov:
                continue
            try:
                if 'text' in ov:     artist.set_text(ov['text'])
                if 'fontsize' in ov: artist.set_fontsize(ov['fontsize'])
                if 'color' in ov:    artist.set_color(ov['color'])
                if 'bold' in ov:     artist.set_fontweight('bold' if ov['bold'] else 'normal')
                if 'italic' in ov:   artist.set_style('italic' if ov['italic'] else 'normal')
                if 'pos' in ov:      artist.set_position(tuple(ov['pos']))
            except Exception:
                pass
        self.canvas.draw_idle()

    # ── hit testing ──────────────────────────────────────────────────────────
    def _text_at(self, event):
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

    def _line_at(self, event):
        for ax in self.cw.fig.axes:
            for ln in reversed(ax.lines):
                if getattr(ln, '_spectra_src', None) is None:
                    continue
                try:
                    hit, _ = ln.contains(event)
                except Exception:
                    hit = False
                if hit:
                    return ln
        return None

    # ── selection ──────────────────────────────────────────────────────────
    def _highlight(self, a, on: bool):
        try:
            a.set_bbox(dict(self._SEL_BBOX) if on else None)
        except Exception:
            pass

    def _set_selection(self, artists):
        for a in self._selected:
            self._highlight(a, False)
        self._selected = []
        for a in artists:
            self._selected.append(a)
            self._highlight(a, True)
        self.canvas.draw_idle()

    def _add_to_selection(self, a):
        if a not in self._selected:
            self._selected.append(a)
            self._highlight(a, True)
            self.canvas.draw_idle()

    def _remove_from_selection(self, a):
        if a in self._selected:
            self._selected.remove(a)
            self._highlight(a, False)
            self.canvas.draw_idle()

    def clear_selection(self):
        if self._selected:
            self._set_selection([])
        if self._box_artists:
            self._clear_box_handles()

    # ── plot-box resize ──────────────────────────────────────────────────────
    def _union_axes_rect(self):
        axes = self.cw.fig.axes
        if not axes:
            return (0.10, 0.12, 0.84, 0.78)
        x0 = min(ax.get_position().x0 for ax in axes)
        y0 = min(ax.get_position().y0 for ax in axes)
        x1 = max(ax.get_position().x1 for ax in axes)
        y1 = max(ax.get_position().y1 for ax in axes)
        return (x0, y0, x1 - x0, y1 - y0)

    @staticmethod
    def _handle_centers(rect):
        l, b, w, h = rect
        return {
            'sw': (l, b),         'se': (l + w, b),
            'nw': (l, b + h),     'ne': (l + w, b + h),
            's':  (l + w / 2, b), 'n':  (l + w / 2, b + h),
            'w':  (l, b + h / 2), 'e':  (l + w, b + h / 2),
        }

    def _current_box_rect(self):
        if self._box_drag and 'rect' in self._box_drag:
            return self._box_drag['rect']
        return self._union_axes_rect()

    def _show_box_handles(self, rect=None):
        self._clear_box_handles()
        fig = self.cw.fig
        if rect is None:
            rect = self._union_axes_rect()
        l, b, w, h = rect
        outline = Rectangle((l, b), w, h, transform=fig.transFigure, fill=False,
                            edgecolor='#1E88E5', linewidth=1.2, linestyle='--', zorder=1000)
        outline.set_gid('_resize_overlay')
        fig.add_artist(outline)
        self._box_artists = [outline]
        size = 0.013
        for _name, (fx, fy) in self._handle_centers(rect).items():
            hb = Rectangle((fx - size / 2, fy - size / 2), size, size,
                           transform=fig.transFigure, facecolor='white',
                           edgecolor='#1E88E5', linewidth=1.2, zorder=1001)
            hb.set_gid('_resize_overlay')
            fig.add_artist(hb)
            self._box_artists.append(hb)
        self._box_selected = True
        self.canvas.draw_idle()

    def _clear_box_handles(self):
        for a in self._box_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._box_artists = []
        self._box_selected = False

    def _handle_at(self, event):
        if not self._box_selected:
            return None
        trans = self.cw.fig.transFigure
        R = 8
        for name, (fx, fy) in self._handle_centers(self._current_box_rect()).items():
            cx, cy = trans.transform((fx, fy))
            if abs(event.x - cx) <= R and abs(event.y - cy) <= R:
                return name
        return None

    def _begin_box_drag(self, event, handle):
        self._box_drag = {'handle': handle, 'press': (event.x, event.y),
                          'rect0': self._union_axes_rect()}

    def _apply_box_rect(self, rect):
        fig = self.cw.fig
        axes = list(fig.axes)
        n = len(axes) or 1
        gap = self.controls.spin_panel_gap.value() if self.controls else 0.04
        l, b, w, h = rect
        pw = max(0.02, (w - (n - 1) * gap) / n)
        for j, ax in enumerate(axes):
            ax.set_position([l + j * (pw + gap), b, pw, h])

    def _update_box_drag(self, event):
        fig = self.cw.fig
        d = self._box_drag
        l, b, w, h = d['rect0']
        inv = fig.transFigure.inverted()
        x0f, y0f = inv.transform(d['press'])
        xf, yf = inv.transform((event.x, event.y))
        dxf, dyf = xf - x0f, yf - y0f
        hd = d['handle']
        nl, nb, nw, nh = l, b, w, h
        if 'w' in hd:
            nl, nw = l + dxf, w - dxf
        elif 'e' in hd:
            nw = w + dxf
        if 's' in hd:
            nb, nh = b + dyf, h - dyf
        elif 'n' in hd:
            nh = h + dyf
        if self.snap_enabled and self.snap_step > 0:
            st = self.snap_step
            nl = round(nl / st) * st; nb = round(nb / st) * st
            nw = round(nw / st) * st; nh = round(nh / st) * st
        nw = max(0.04, nw); nh = max(0.04, nh)
        nl = min(max(0.0, nl), 0.96); nb = min(max(0.0, nb), 0.96)
        if nl + nw > 1.0:
            nw = 1.0 - nl
        if nb + nh > 1.0:
            nh = 1.0 - nb
        rect = (nl, nb, nw, nh)
        self._box_drag['rect'] = rect
        self._apply_box_rect(rect)
        self._show_box_handles(rect)

    def _finish_box_drag(self):
        d = self._box_drag
        rect = d.get('rect', d['rect0'])
        self._box_drag = None
        if self.controls is not None:
            c = self.controls
            for wdg, val in ((c.spin_pa_left, rect[0]), (c.spin_pa_bottom, rect[1]),
                             (c.spin_pa_w, rect[2]), (c.spin_pa_h, rect[3])):
                wdg.blockSignals(True); wdg.setValue(val); wdg.blockSignals(False)
            if not c.chk_manual_box.isChecked():
                c.chk_manual_box.setChecked(True)   # makes the geometry stick on replot
        if self.request_replot:
            self.request_replot()

    # ── events ──────────────────────────────────────────────────────────────
    def _on_press(self, event):
        if event.x is None or event.y is None:
            return
        if event.dblclick:
            t = self._text_at(event)
            if t is not None:
                self._edit_text(t); return
            leg = self._legend_at(event)
            if leg is not None:
                self._edit_legend(leg); return
            ln = self._line_at(event)
            if ln is not None:
                self._edit_line(ln); return
            return
        if event.button != 1:
            return
        shift, ctrl = self._mods()
        # plot-box resize handle takes priority once the box is selected
        if self._box_selected:
            hd = self._handle_at(event)
            if hd is not None:
                self._begin_box_drag(event, hd)
                self._press = None
                return
        t = self._text_at(event)
        if t is not None and self._legend_at(event) is None:
            self._clear_box_handles()
            was = t in self._selected
            if shift or ctrl:
                if not was:
                    self._add_to_selection(t)   # ensure it joins the group drag
            else:
                if not was:
                    self._set_selection([t])
            self._press = {'artist': t, 'shift': shift, 'ctrl': ctrl,
                           'was': was, 'moved': False}
            self._begin_drag(event)
            return
        if self._legend_at(event) is not None:
            self._press = None
            return
        # click inside the plot area → select the plot box (show resize handles)
        if getattr(event, 'inaxes', None) is not None:
            self.clear_selection()
            self._show_box_handles()
            self._press = None
            return
        # empty space → clear text selection and the box overlay
        if not (shift or ctrl):
            self.clear_selection()
        self._clear_box_handles()
        self.canvas.draw_idle()
        self._press = None

    def _begin_drag(self, event):
        items = []
        for a in self._selected:
            x0, y0 = a.get_transform().transform(a.get_position())
            items.append((a, (x0, y0), tuple(a.get_position())))
        self._drag = {'press': (event.x, event.y), 'items': items}

    _HANDLE_CURSOR = {
        'nw': Qt.CursorShape.SizeFDiagCursor, 'se': Qt.CursorShape.SizeFDiagCursor,
        'ne': Qt.CursorShape.SizeBDiagCursor, 'sw': Qt.CursorShape.SizeBDiagCursor,
        'n': Qt.CursorShape.SizeVerCursor, 's': Qt.CursorShape.SizeVerCursor,
        'e': Qt.CursorShape.SizeHorCursor, 'w': Qt.CursorShape.SizeHorCursor,
    }

    def _on_motion(self, event):
        if self._box_drag is not None and event.x is not None:
            self._update_box_drag(event)
            return
        if self._drag is not None and event.x is not None:
            if self._press is not None:
                self._press['moved'] = True
            shift, _ = self._mods()
            dx = event.x - self._drag['press'][0]
            dy = event.y - self._drag['press'][1]
            if shift:                       # constrain to a straight line
                if abs(dx) >= abs(dy):
                    dy = 0
                else:
                    dx = 0
            for a, (x0, y0), _start in self._drag['items']:
                newdisp = (x0 + dx, y0 + dy)
                if self.snap_enabled and self.snap_step > 0:
                    fig = self.cw.fig
                    fx, fy = fig.transFigure.inverted().transform(newdisp)
                    step = self.snap_step
                    fx = round(fx / step) * step
                    fy = round(fy / step) * step
                    newdisp = fig.transFigure.transform((fx, fy))
                newpos = a.get_transform().inverted().transform(newdisp)
                a.set_position(tuple(newpos))
            self.canvas.draw_idle()
            return
        if event.x is None:
            return
        if self._box_selected:
            hd = self._handle_at(event)
            if hd is not None:
                self.canvas.setCursor(QCursor(self._HANDLE_CURSOR[hd]))
                return
        over = (self._text_at(event) is not None
                or self._legend_at(event) is not None
                or self._line_at(event) is not None)
        self.canvas.setCursor(
            QCursor(Qt.CursorShape.OpenHandCursor if over else Qt.CursorShape.ArrowCursor))

    def _on_release(self, event):
        if self._box_drag is not None:
            self._finish_box_drag()
            self._press = None
            return
        moved = bool(self._press and self._press.get('moved'))
        if self._drag is not None and moved:
            self.undo_stack.beginMacro('Move')
            for a, _disp0, start in self._drag['items']:
                end = tuple(a.get_position())
                if end != start:
                    self.undo_stack.push(_MoveCommand(a, start, end, self.canvas))
                role = self._role_by_artist.get(id(a))
                if role:
                    self.overrides.setdefault(role, {})['pos'] = tuple(a.get_position())
            self.undo_stack.endMacro()
        elif self._press is not None and not moved:
            t = self._press['artist']
            if self._press['shift'] or self._press['ctrl']:
                if self._press['was']:
                    self._remove_from_selection(t)   # toggle off on plain click
            else:
                self._set_selection([t])
        self._drag = None
        self._press = None

    # ── editors ────────────────────────────────────────────────────────────
    def _edit_text(self, t):
        dlg = TextEditDialog(t, self.cw)
        if dlg.exec():
            dlg.apply()
            self._capture_text_override(t)
            self._sync_text_to_controls(t)
            self.canvas.draw_idle()

    def _capture_text_override(self, t):
        role = self._role_by_artist.get(id(t))
        if not role:
            return
        ov = self.overrides.setdefault(role, {})
        ov['text'] = t.get_text()
        ov['fontsize'] = float(t.get_fontsize())
        ov['color'] = to_hex(t.get_color())
        ov['bold'] = str(t.get_fontweight()) in ('bold', '700', 'heavy', 'semibold')
        ov['italic'] = t.get_style() == 'italic'

    def _sync_text_to_controls(self, t):
        """Mirror edited title/subtitle text back into the left-panel fields."""
        role = self._role_by_artist.get(id(t))
        if not role or self.controls is None:
            return
        target = None
        if role == 'suptitle':
            target = self.controls.edit_main_title
        elif role == 'subtitle':
            target = self.controls.edit_subtitle
        if target is not None:
            target.blockSignals(True)
            target.setText(t.get_text())
            target.blockSignals(False)

    def _edit_line(self, ln):
        """Double-click a plotted line → full edit box (shared with the list boxes)."""
        src = getattr(ln, '_spectra_src', None)
        if src is None or self.controls is None:
            return
        kind, key = src
        if kind == 'xrdref':
            self.controls.edit_reference(key)   # opens ReferenceEditDialog and replots
            return
        if kind == 'trace':
            tr = self.controls.find_trace_by_uid(key)
            if tr is None:
                return
            dlg = TraceEditDialog(tr, self.cw)
            if dlg.exec():
                dlg.apply()
                if self.request_replot:
                    self.request_replot()

    def _edit_legend(self, leg):
        dlg = LegendEditDialog(leg, self.cw, controls=self.controls)
        if dlg.exec():
            dlg.apply()
            self.canvas.draw_idle()
            if dlg.needs_replot and self.request_replot:
                self.request_replot()


# ── Plot canvas ───────────────────────────────────────────────────────────────

class PlotCanvas(QWidget):
    size_update_requested = pyqtSignal()
    DISPLAY_DPI = 100  # on-screen pixels per inch of figure

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('canvasArea')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(s(14), vs(14), s(14), vs(8))
        lay.setSpacing(0)

        self.card = QWidget()
        self.card.setObjectName('canvasCard')
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        add_shadow(self.card, blur=32, y=10, alpha=28)
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(s(10), vs(10), s(10), vs(10))
        card_lay.setSpacing(vs(10))

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
        sep.setFixedWidth(s(1))
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
        sep2.setFixedWidth(s(1))
        sep2.setStyleSheet('background: #B8C5D3;')
        self.toolbar.addWidget(sep2)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText('−')
        self.btn_zoom_out.setToolTip('Zoom out (visual only — does not change data or export)')
        self.btn_zoom_reset = QToolButton()
        self.btn_zoom_reset.setText('100%')
        self.btn_zoom_reset.setToolTip('Reset zoom to 100%')
        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText('+')
        self.btn_zoom_in.setToolTip('Zoom in (visual only — does not change data or export)')
        for _b in (self.btn_zoom_out, self.btn_zoom_reset, self.btn_zoom_in):
            _b.setObjectName('figToolbarBtn')
            self.toolbar.addWidget(_b)

        self.btn_fit.clicked.connect(self._toolbar_fit)
        self.btn_autoscale.clicked.connect(self._toolbar_fit)
        self.btn_grid.toggled.connect(self._toolbar_grid)
        self.btn_update_size.clicked.connect(lambda _checked=False: self.size_update_requested.emit())
        self.btn_save_fig.clicked.connect(self.toolbar.save_figure)
        self._view_scale = 1.0
        self.btn_zoom_out.clicked.connect(lambda: self.set_view_scale(self._view_scale / 1.25))
        self.btn_zoom_in.clicked.connect(lambda: self.set_view_scale(self._view_scale * 1.25))
        self.btn_zoom_reset.clicked.connect(lambda: self.set_view_scale(1.0))

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
        hv.setContentsMargins(s(20), s(20), s(20), s(20))
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

    def set_fig_size(self, w_in: float, h_in: float):
        """Set the figure's true (export) size in inches, then lay it out on
        screen at the current view scale."""
        self._fig_w_in = w_in
        self._fig_h_in = h_in
        self.fig.set_size_inches(w_in, h_in)
        self._apply_display_size()
        # Logical (unscaled) pixels track the requested figure size for the
        # pending-size ("Update") bookkeeping; the view scale never affects it.
        self._applied_size_px = (int(round(w_in * self.DISPLAY_DPI)),
                                 int(round(h_in * self.DISPLAY_DPI)))
        self.mark_size_pending(False)

    def set_view_scale(self, z: float):
        """Visually scale the WHOLE figure on screen (zoom for viewing only).
        Does not change data limits, figure inches, or exported output."""
        self._view_scale = max(0.2, min(3.0, round(z, 3)))
        self._apply_display_size()
        self.btn_zoom_reset.setText(f'{int(round(self._view_scale * 100))}%')

    def _apply_display_size(self):
        """Resize the on-screen canvas to figure_inches × DISPLAY_DPI × view_scale.
        figure.set_size_inches stays at the true size so export is unaffected.
        DPI is scaled by view_scale × devicePixelRatio so Qt's resizeEvent
        (w_in = logical_px·dpr / dpi) keeps the inch size stable."""
        w_in = getattr(self, '_fig_w_in', 8.0)
        h_in = getattr(self, '_fig_h_in', 5.0)
        z = getattr(self, '_view_scale', 1.0)
        dpr = self.canvas.devicePixelRatioF() or 1.0
        self.fig.set_dpi(self.DISPLAY_DPI * z * dpr)
        self.canvas.setFixedSize(int(round(w_in * self.DISPLAY_DPI * z)),
                                 int(round(h_in * self.DISPLAY_DPI * z)))
        self.canvas.draw_idle()

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
    # Render mathtext (sub/superscripts via $..$) in the same figure font, upright,
    # instead of matplotlib's default math font — so subscripts match the rest.
    try:
        matplotlib.rcParams['mathtext.default'] = 'regular'
        matplotlib.rcParams['mathtext.fontset'] = 'custom'
        matplotlib.rcParams['mathtext.rm'] = fam
        matplotlib.rcParams['mathtext.it'] = f'{fam}:italic'
        matplotlib.rcParams['mathtext.bf'] = f'{fam}:bold'
    except Exception:
        pass


_MATH_RUN = re.compile(r'(?:[_^]\{[^}]*\})+')


def _mathify(text: str) -> str:
    """Render TeX sub/superscripts (_{...} / ^{...}) by wrapping ONLY those tokens
    in $...$ — the surrounding text keeps its real font and spacing (the H$_2$O idiom)."""
    if not text:
        return text
    stripped = text.strip()
    if stripped.startswith('$') and stripped.endswith('$') and stripped.count('$') == 2:
        return text
    if '_{' not in text and '^{' not in text:
        return text
    return _MATH_RUN.sub(lambda m: f'${m.group(0)}$', text)


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

    ax.set_xlabel(_mathify(xlabel), fontsize=fontsize, color='black', labelpad=7)
    if is_left:
        ax.set_ylabel(_mathify(ylabel), fontsize=fontsize, color='black', labelpad=7)
    else:
        ax.set_ylabel('')


def _add_legend(ax, handles: list, labels: list, s: dict, sources=None):
    if not s['show_legend'] or not handles:
        return
    fs = s.get('legend_fontsize', max(6, s['fontsize'] - 1))
    _ls = s.get('legend_labelspacing', 0.25)
    labelspacing = _ls * (10.0 / max(fs, 6.0))  # normalise to 10pt so gap stays constant as font scales
    ncols = 2 if s.get('legend_2col', False) else 1
    markerfirst = s.get('legend_markerfirst', True)   # False = flip markers to the right
    alignment = s.get('legend_alignment', 'left')
    labels = [_mathify(l) for l in labels]
    leg = ax.legend(handles, labels, loc=s['legend_loc'],
                    fontsize=fs, fancybox=False, labelspacing=labelspacing,
                    ncols=ncols, markerfirst=markerfirst, alignment=alignment)
    # Remember what each entry maps back to, so the legend editor can rename them.
    leg._spectra_sources = list(sources) if sources else None
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
        ax.set_title(_mathify(s['panel_titles'][idx]),
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
        return y - np.min(y)
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
        entries = []  # (peak, add_idx, handle, label, src) for legend ordering
        for k, (x, y, peak, tr, add_idx) in enumerate(corrected):
            color, lw, lstyle = _trace_visual(tr, colors, k, use_grad, s['linewidth'])
            ln, = ax.plot(x, y, linewidth=lw, color=color, linestyle=lstyle)
            ln._spectra_src = ('trace', tr.get('uid'))
            entries.append((peak, add_idx, ln, tr['display_name'], ('trace', tr.get('uid'))))

        # Legend order is independent of plot order: by peak (high→low) or add order.
        if s.get('legend_peak_order', True):
            legend_order = sorted(entries, key=lambda e: e[0], reverse=True)
        else:
            legend_order = sorted(entries, key=lambda e: e[1])
        hs = [e[2] for e in legend_order]
        ls = [e[3] for e in legend_order]
        srcs = [e[4] for e in legend_order]

        ylabel = 'Baseline-corrected PL' if baseline_correct else 'PL intensity'
        _style_ax(ax, i == 0, 'Wavelength λ (nm)', ylabel, s)
        _add_legend(ax, hs, ls, s, srcs)
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
        hs, ls, srcs = [], [], []
        for k, (x, y, _, tr) in enumerate(with_pk):
            color, lw, lstyle = _trace_visual(tr, colors, k, use_grad, s['linewidth'])
            ln, = ax.plot(x, y, linewidth=lw, color=color, linestyle=lstyle)
            ln._spectra_src = ('trace', tr.get('uid'))
            hs.append(ln); ls.append(tr['display_name']); srcs.append(('trace', tr.get('uid')))

        _style_ax(ax, i == 0, 'Wavelength λ (nm)', ylabel, s)
        _add_legend(ax, hs, ls, s, srcs)
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

    ref_colors = s.get('xrd_ref_colors', [])
    ref_labels = s.get('xrd_ref_labels', [])
    ref_widths = s.get('xrd_ref_widths', [])
    ref_styles = s.get('xrd_ref_styles', [])
    ref_traces = []
    for idx, path in enumerate(s['xrd_ref_paths']):
        x, y = load_file(path)
        if x is not None:
            x, y = maybe_convert(x, y)
            lbl = ref_labels[idx] if idx < len(ref_labels) else clean_label(os.path.basename(path))
            col = ref_colors[idx] if idx < len(ref_colors) else '#000000'
            rw = ref_widths[idx] if idx < len(ref_widths) else None
            rw = float(rw) if rw is not None else s['linewidth']
            rls = LINESTYLE_MAP.get(ref_styles[idx] if idx < len(ref_styles) else 'solid', '-')
            ref_traces.append((x, y, lbl, col, idx, rw, rls))
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
        hs, ls, srcs = [], [], []
        for k, (x, y, lbl, col, ridx, rw, rls) in enumerate(ref_traces):
            ln, = ax.plot(
                x, y + offsets[k],
                linewidth=rw,
                linestyle=rls,
                color=col,
                label=lbl,
            )
            ln._spectra_src = ('xrdref', ridx)
            hs.append(ln); ls.append(lbl); srcs.append(('xrdref', ridx))
        for k, (x, y, tr) in enumerate(exp_traces):
            color, lw, lstyle = _trace_visual(tr, exp_colors, k, use_grad, s['linewidth'])
            ln, = ax.plot(x, y + offsets[n_ref + k], linewidth=lw,
                          color=color, linestyle=lstyle, label=tr['display_name'])
            ln._spectra_src = ('trace', tr.get('uid'))
            hs.append(ln); ls.append(tr['display_name']); srcs.append(('trace', tr.get('uid')))

        xlabel = 'd-spacing (Å)' if use_d else '2θ (°)'
        _style_ax(ax, i == 0, xlabel, 'Intensity', s)
        _add_legend(ax, hs, ls, s, srcs)
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
            fig.suptitle(_mathify(s['main_title']), fontsize=s['fontsize'] + 2,
                         fontweight='bold', color='black', y=0.98)
        if has_sub:
            ysub = 0.945 if has_title else 0.975
            fig.text(0.5, ysub, _mathify(s['subtitle']), fontsize=s['fontsize'],
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
    pixmap = QPixmap(s(760), s(740))
    pixmap.fill(QColor('#FFFFFF'))

    splash = QSplashScreen(pixmap)
    splash.setObjectName('loadingScreen')
    splash.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    splash.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    layout = QVBoxLayout(splash)
    layout.setContentsMargins(s(40), s(30), s(40), s(28))
    layout.setSpacing(s(10))

    # ── Hero image (assets/loading.png, optional)
    img_path = resource_path('assets', 'loading.png')
    if os.path.isfile(img_path):
        img_lbl = QLabel()
        img_lbl.setObjectName('loadingImage')
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Render at the screen's native pixel density so it stays crisp on Retina
        scr = QApplication.primaryScreen()
        dpr = scr.devicePixelRatio() if scr else 1.0
        target_w = s(680)
        pix = QPixmap(img_path).scaledToWidth(
            int(target_w * dpr), Qt.TransformationMode.SmoothTransformation)
        pix.setDevicePixelRatio(dpr)
        img_lbl.setPixmap(pix)
        layout.addWidget(img_lbl)

    # SPECTRA (extrabold) + plot (light), big, in Montserrat
    ff = spectra_theme.UI_FONT_FAMILY
    title = QLabel()
    title.setObjectName('loadingTitle')
    title.setTextFormat(Qt.TextFormat.RichText)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setText(
        f'<span style="font-family:{ff};font-size:{s(56)}px;font-weight:800;'
        f'color:#171717;">SPECTRA</span>'
        f'<span style="font-family:{ff};font-size:{s(56)}px;font-weight:300;'
        f'color:#5F5F5F;">plot</span>'
    )

    subtitle = QLabel('PL  ·  ABSORBANCE  ·  XRD  ·  IV')
    subtitle.setObjectName('loadingSubtitle')
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

    status = QLabel('preparing plotting workspace...')
    status.setObjectName('loadingStatus')
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # cycle through a few (lowercase) loading quips while the splash is up
    _quips = [
        'calibrating the diffractometer...',
        "summoning bragg's law...",
        'aligning the x-rays (do not look directly)...',
        'fitting gaussians nobody asked for...',
        'bribing matplotlib to cooperate...',
        # material science
        'annealing your grain boundaries...',
        'indexing miller planes...',
        'quenching the melt a little too fast...',
        'measuring band gaps you cannot afford...',
        'doping the lattice (academically)...',
        'blaming everything on surface defects...',
        'pretending the peak shift is not thermal expansion...',
        'chasing a phase that is only metastable...',
        # semiconductor
        'passivating dangling bonds, mostly...',
        'recombining carriers nonradiatively...',
        'spin-coating until the substrate gives up...',
        'tunneling through a barrier we promised was thick...',
        'counting traps in the band gap...',
        'blaming the mobility on the substrate...',
        # polymer
        'untangling polymer chains...',
        'glass transition pending, please wait...',
        'measuring a polydispersity we will not report...',
        'degrading under uv, as designed...',
        # dark humour
        'absorbing more radiation than the sample...',
        'voiding the warranty on your instruments...',
        'normalizing data until it agrees with the hypothesis...',
        'this run will outlive your funding...',
        'crystallizing slower than your phd...',
    ]
    import random as _random
    _random.shuffle(_quips)
    _quips.insert(0, 'preparing plotting workspace...')   # always start here
    _qi = {'i': 0}

    def _next_quip():
        _qi['i'] = (_qi['i'] + 1) % len(_quips)
        status.setText(_quips[_qi['i']])

    _quip_timer = QTimer(splash)
    _quip_timer.timeout.connect(_next_quip)
    _quip_timer.start(1700)
    splash._quip_timer = _quip_timer   # keep a reference so it isn't GC'd

    progress = QProgressBar()
    progress.setObjectName('loadingProgress')
    progress.setRange(0, 0)
    progress.setTextVisible(False)

    byline = QLabel()
    byline.setObjectName('loadingBy')
    byline.setTextFormat(Qt.TextFormat.RichText)
    byline.setAlignment(Qt.AlignmentFlag.AlignCenter)
    byline.setText(
        f'<span style="font-family:{ff};font-size:{s(14)}px;font-weight:500;'
        f'color:#8A8A8A;">by Arnold Wijoyo</span>'
    )

    layout.addStretch(1)
    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addSpacing(18)
    layout.addWidget(progress)
    layout.addWidget(status)
    layout.addStretch(1)
    layout.addWidget(byline)

    return splash


class LogPanel(QWidget):
    """Append-only message console echoing status-bar messages."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(s(4), s(4), s(4), s(4))
        lay.setSpacing(0)
        self.view = QPlainTextEdit()
        self.view.setObjectName("logView")
        self.view.setReadOnly(True)
        lay.addWidget(self.view)

    def append(self, msg: str):
        self.view.appendPlainText(msg)

    def text(self) -> str:
        return self.view.toPlainText()



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SPECTRAplot')
        self.resize(s(1520), s(900))
        self.setMinimumSize(s(1100), s(640))

        self._current_mode = MODES[0]['key']

        self.controls = ControlPanel()
        # Strip the on-canvas selection highlight before any export.
        self.controls.before_save = lambda: self.editor.clear_selection()
        self._figure_states: list[FigureState] = []
        self._active_fig_idx: int = 0
        self.figure_tab_bar = FigureTabBar()
        self.canvas_stack = QStackedWidget()
        self._build_chrome()

        self.app_root = QWidget()
        self.app_root.setObjectName('appRoot')
        root_lay = QVBoxLayout(self.app_root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        self.header = TopHeader()
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header.mode_changed.connect(self._on_mode_change)
        self.header.theme_toggled.connect(self._on_theme_toggle)
        self.header.plot_requested.connect(self._do_plot)
        # The header spans the full window width above the docks (a top toolbar
        # sits above the left/right dock areas while keeping the menu bar).
        self.header_bar = QToolBar('Header', self)
        self.header_bar.setObjectName('headerBar')
        self.header_bar.setMovable(False)
        self.header_bar.setFloatable(False)
        self.header_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.header_bar.setStyleSheet(
            'QToolBar#headerBar { border: none; padding: 0px; margin: 0px; spacing: 0px; }')
        self.header_bar.addWidget(self.header)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.header_bar)

        root_lay.addWidget(self.figure_tab_bar)
        root_lay.addWidget(self.canvas_stack, 1)
        self.setCentralWidget(self.app_root)

        # Create the first figure state (canvas + editor) and activate it
        self._switch_figure(self._add_figure_state(mode=MODES[0]['key']))

        # ── Left dock: Build / Parameters (the ControlPanel) ────────────────
        self.dock_build = QDockWidget("Build", self)
        self.dock_build.setObjectName("dock_build")
        self.dock_build.setWidget(self.controls)
        self.dock_build.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_build)

        # ── Plot Style dock: left area, next to Build (stacked vertically) ─────
        style_host = QWidget()
        style_host.setObjectName("plotStyleHost")
        style_lay = QVBoxLayout(style_host)
        style_lay.setContentsMargins(s(8), s(8), s(8), s(8))
        style_lay.setSpacing(s(8))

        # ── Preset buttons at the top of the style dock ──────────────────────
        preset_row = QWidget()
        preset_lay = QHBoxLayout(preset_row)
        preset_lay.setContentsMargins(0, 0, 0, 0)
        preset_lay.setSpacing(s(6))
        btn_save_preset = QPushButton('Save Preset')
        btn_save_preset.setObjectName('presetBtn')
        btn_load_preset = QPushButton('Load Preset')
        btn_load_preset.setObjectName('presetBtn')
        btn_save_preset.clicked.connect(self.controls.save_preset)
        btn_load_preset.clicked.connect(self.controls.load_preset)
        preset_lay.addWidget(btn_save_preset)
        preset_lay.addWidget(btn_load_preset)
        style_lay.addWidget(preset_row)

        for group in self.controls.take_dock_groups():
            group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            style_lay.addWidget(group)
        style_lay.addStretch()
        style_scroll = QScrollArea()
        style_scroll.setObjectName("plotStyleScroll")
        style_scroll.setWidget(style_host)
        style_scroll.setWidgetResizable(True)
        style_scroll.setFrameShape(QFrame.Shape.NoFrame)
        style_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.dock_style = QDockWidget("Plot Style", self)
        self.dock_style.setObjectName("dock_style")
        self.dock_style.setWidget(style_scroll)
        self.dock_style.setMinimumWidth(s(360))
        self.dock_style.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_style)

        # (Log panel removed — status messages still go to the status bar.)
        self.log_dock = None

        # Left dock owns left corners; right dock owns right corners (full height)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)

        # View-menu dock toggles (inserted before the Dark Mode action)
        self.m_view.insertAction(self.act_dark, self.dock_build.toggleViewAction())
        self.m_view.insertAction(self.act_dark, self.dock_style.toggleViewAction())
        self.m_view.insertSeparator(self.act_dark)

        self._default_state = self.saveState()
        QTimer.singleShot(0, self._apply_dock_sizes)

        self._has_plotted = False
        self._suppress_replot = False
        self._plot_called_for_test = False
        self.controls.plot_requested.connect(self._do_plot)
        self.controls.live_update_requested.connect(self._auto_replot)
        self.controls.spin_fw.valueChanged.connect(self._mark_canvas_size_pending)
        self.controls.spin_fh.valueChanged.connect(self._mark_canvas_size_pending)
        self.controls.chk_snap.toggled.connect(self._update_snap)
        self.controls.spin_snap_step.valueChanged.connect(self._update_snap)

        # Figure tab bar signals
        self.figure_tab_bar.figure_selected.connect(self._switch_figure)
        self.figure_tab_bar.figure_add_requested.connect(self._on_add_figure)
        self.figure_tab_bar.figure_close_requested.connect(self._close_figure)

        self._status_message('Ready — add files to a panel and click Plot.')
        self._apply_accent(MODES[0]['accent'])

    # ── Figure state properties ───────────────────────────────────────────────

    @property
    def canvas(self) -> 'PlotCanvas':
        return self._figure_states[self._active_fig_idx].canvas

    @property
    def editor(self) -> 'FigureEditor':
        return self._figure_states[self._active_fig_idx].editor

    # ── Figure management ─────────────────────────────────────────────────────

    def _add_figure_state(self, mode: str = 'pl') -> int:
        c = PlotCanvas()
        e = FigureEditor(c)
        e.controls = self.controls
        e.request_replot = lambda: self._auto_replot()
        n = len(self._figure_states) + 1
        state = FigureState(canvas=c, editor=e, mode=mode, label=f'Fig {n}')
        self._figure_states.append(state)
        self.canvas_stack.addWidget(c)
        self.figure_tab_bar.add_figure(state.label)
        c.size_update_requested.connect(self._update_canvas_size)
        c.canvas.mpl_connect('motion_notify_event', self._on_coord_motion)
        return len(self._figure_states) - 1

    def _switch_figure(self, idx: int):
        if idx < 0 or idx >= len(self._figure_states):
            return
        # Save the outgoing figure's data before swapping the shared data box.
        if 0 <= self._active_fig_idx < len(self._figure_states):
            self._figure_states[self._active_fig_idx].data = self.controls.capture_data()
        self._active_fig_idx = idx
        state = self._figure_states[idx]
        self.canvas_stack.setCurrentIndex(idx)
        self.figure_tab_bar.set_active(idx)
        self.controls._canvas = state.canvas
        self._on_mode_change(state.mode)
        # Restore this figure's data. The canvas already holds its last render,
        # so suppress live-replots while the data box is repopulated.
        self._suppress_replot = True
        try:
            self.controls.restore_data(state.data)
        finally:
            self._suppress_replot = False

    def _on_add_figure(self):
        # A new figure carries no data; _switch_figure restores its empty state
        # while preserving the previous figure's traces.
        idx = self._add_figure_state(mode=self._current_mode)
        self._switch_figure(idx)

    def _close_figure(self, idx: int):
        if len(self._figure_states) <= 1:
            return
        state = self._figure_states.pop(idx)
        self.canvas_stack.removeWidget(state.canvas)
        state.canvas.deleteLater()
        self.figure_tab_bar.remove_figure(idx)
        # The closed figure's data is discarded with it — mark "no active figure"
        # so the upcoming switch doesn't capture it back into a surviving tab.
        self._active_fig_idx = -1
        self._switch_figure(min(idx, len(self._figure_states) - 1))

    def _apply_dock_sizes(self):
        self.resizeDocks([self.dock_build], [s(260)], Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_style], [s(360)], Qt.Orientation.Horizontal)

    def _build_chrome(self):
        self.act_plot = QAction("Plot", self)
        self.act_plot.setShortcut("Ctrl+Return")
        self.act_plot.triggered.connect(self._do_plot)

        self.act_save = QAction("Save Figure…", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(lambda: self.controls._save("png"))

        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(lambda: self.editor.undo_stack.undo())

        self.act_fit = QAction("Fit to Data", self)
        self.act_fit.triggered.connect(lambda: self.canvas._toolbar_fit())
        self.act_grid = QAction("Grid", self)
        self.act_grid.setCheckable(True)
        self.act_grid.toggled.connect(lambda checked: self.canvas._toolbar_grid(checked))
        self.act_zoom_in = QAction("Zoom In", self)
        self.act_zoom_in.triggered.connect(lambda: self.canvas.set_view_scale(self.canvas._view_scale * 1.25))
        self.act_zoom_out = QAction("Zoom Out", self)
        self.act_zoom_out.triggered.connect(lambda: self.canvas.set_view_scale(self.canvas._view_scale / 1.25))

        self.act_dark = QAction("Dark Mode", self)
        self.act_dark.setCheckable(True)
        self.act_dark.toggled.connect(self._on_theme_toggle)

        self.act_quit = QAction("Exit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)

        self.act_about = QAction("About SPECTRAplot", self)
        self.act_about.triggered.connect(self._show_about)

        self.act_reset_layout = QAction("Reset Layout", self)
        self.act_reset_layout.triggered.connect(self._reset_layout)

        self.mode_actions = {}
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        for m in MODES:
            a = QAction(m["label"], self)
            a.setCheckable(True)
            a.setObjectName(f"modeAction_{m['key']}")
            a.triggered.connect(lambda _checked, k=m["key"]: self._on_mode_change(k))
            self._mode_group.addAction(a)
            self.mode_actions[m["key"]] = a
        self.mode_actions[MODES[0]["key"]].setChecked(True)

        mb = self.menuBar()
        m_file = mb.addMenu("&File")
        m_file.addAction(self.act_save)
        m_file.addSeparator()
        m_file.addAction(self.act_quit)
        m_edit = mb.addMenu("&Edit")
        m_edit.addAction(self.act_undo)
        self.m_view = mb.addMenu("&View")
        self.m_view.addAction(self.act_dark)
        self.m_view.addAction(self.act_reset_layout)
        self.m_view.addSeparator()
        m_plot = mb.addMenu("&Plot")
        m_plot.addAction(self.act_plot)
        m_plot.addSeparator()
        m_plot.addAction(self.act_fit)
        m_plot.addAction(self.act_grid)
        m_plot.addAction(self.act_zoom_in)
        m_plot.addAction(self.act_zoom_out)
        m_plot.addSeparator()
        for a in self.mode_actions.values():
            m_plot.addAction(a)
        m_help = mb.addMenu("&Help")
        m_help.addAction(self.act_about)

        sb = self.statusBar()
        self._sb_ready = QLabel("● Ready")
        self._sb_ready.setObjectName("readyDot")
        self._sb_coord = QLabel("")
        self._sb_coord.setObjectName("coordLabel")
        sb.addPermanentWidget(self._sb_ready)
        sb.addPermanentWidget(self._sb_coord)

    def _show_about(self):
        QMessageBox.about(self, "SPECTRAplot",
                          "SPECTRAplot — spectrometry visualization\nby arnold wijoyo")

    def _reset_layout(self):
        if getattr(self, "_default_state", None) is not None:
            self.restoreState(self._default_state)

    def _status_message(self, msg: str):
        self.statusBar().showMessage(msg)
        if getattr(self, "log_dock", None) is not None:
            self.log_dock.append(msg)

    def _status_ready(self, ok: bool):
        self._sb_ready.setText("● Ready" if ok else "● Busy")

    def _apply_accent(self, accent: str):
        QApplication.instance().setStyleSheet(build_style(accent, _APP_DARK, spectra_theme.UI_SCALE))
        if getattr(self, "header", None) is not None:
            self.header.apply_theme(_APP_DARK)

    def _on_mode_change(self, key: str):
        self._current_mode = key
        if self._figure_states:
            self._figure_states[self._active_fig_idx].mode = key
        if getattr(self, "header", None) is not None:
            self.header.mode_tabs.set_current(key)
        action = self.mode_actions.get(key)
        if action is not None and not action.isChecked():
            action.setChecked(True)
        self._apply_accent(MODE_BY_KEY[key]['accent'])
        self.controls.set_mode(key)

    def _on_theme_toggle(self, dark: bool):
        global _APP_DARK
        _APP_DARK = dark
        if self.act_dark.isChecked() != dark:
            self.act_dark.blockSignals(True)
            self.act_dark.setChecked(dark)
            self.act_dark.blockSignals(False)
        if getattr(self, "header", None) is not None:
            if self.header.btn_theme.isChecked() != dark:
                self.header.btn_theme.blockSignals(True)
                self.header.btn_theme.setChecked(dark)
                self.header.btn_theme.blockSignals(False)
            self.header.apply_theme(dark)
        accent = MODE_BY_KEY[self._current_mode]['accent']
        QApplication.instance().setStyleSheet(build_style(accent, dark, spectra_theme.UI_SCALE))

    def _on_coord_motion(self, event):
        if event.inaxes is None:
            self._sb_coord.clear()
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            self._sb_coord.clear()
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
        self._sb_coord.setText(text)

    def _mark_canvas_size_pending(self, *_):
        requested = (self.controls.spin_fw.value(), self.controls.spin_fh.value())
        self.canvas.mark_size_pending(requested != self.canvas.applied_size_pixels())

    def _update_canvas_size(self):
        self.canvas.set_fig_size(
            self.controls.spin_fw.value() / 100, self.controls.spin_fh.value() / 100)
        self.canvas.canvas.draw_idle()
        self._status_message(
            f'Figure size updated to {self.controls.spin_fw.value()} x {self.controls.spin_fh.value()} px.'
        )

    def _update_snap(self, *_):
        self.editor.set_snap(
            self.controls.chk_snap.isChecked(),
            self.controls.spin_snap_step.value())

    def _auto_replot(self):
        """Live-refresh the figure after a trace/legend change — but only once a
        plot already exists, and without popping the 'No Data' / error dialogs."""
        if self._suppress_replot:
            return
        if self._has_plotted:
            self._do_plot(silent=True)

    def _do_plot(self, silent: bool = False):
        self._plot_called_for_test = True
        self._status_ready(False)
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
        self._status_message('Plotting…')
        self.canvas.set_fig_size(s['fig_width'] / 100, s['fig_height'] / 100)
        self.editor.set_snap(s['snap_enabled'], s['snap_step'])
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()
        try:
            msg = do_plot(self.canvas.get_figure(), s)
            self.editor.refresh()
            self._has_plotted = True
            self._status_message(msg + '   ·   Double-click figure text to edit · drag to reposition.')
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, 'Plot Error', str(e))
            self._status_message(f'Error: {e}')
        finally:
            QApplication.restoreOverrideCursor()
            self._status_ready(True)


# ── Entry point ───────────────────────────────────────────────────────────────

def _load_bundled_fonts() -> str:
    """Load the bundled Montserrat variable font and return its family name, or
    '' if unavailable. The file is renamed to the unique family 'Montserrat App'
    so Qt always uses our copy instead of (or colliding with) a system install.
    The single variable file supplies every weight (Light 300 … ExtraBold 800)."""
    path = resource_path('assets', 'Montserrat-App.ttf')
    if os.path.isfile(path):
        fid = QFontDatabase.addApplicationFont(path)
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            return fams[0]
    return ''


def _load_ui_font() -> str:
    """Register the bundled Google Sans font (project root) and return its
    family name, or '' if unavailable."""
    family = ''
    for fname in ('GoogleSans-VariableFont_GRAD,opsz,wght.ttf',
                  'GoogleSans-Italic-VariableFont_GRAD,opsz,wght.ttf'):
        path = resource_path(fname)
        if os.path.isfile(path):
            fid = QFontDatabase.addApplicationFont(path)
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams and not family:
                family = fams[0]
    return family


def main():
    if sys.platform == 'darwin':
        os.environ.setdefault('QT_MAC_WANTS_LAYER', '1')
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    init_ui_scale(app)
    mont_font = _load_bundled_fonts()
    ui_font = _load_ui_font()
    chosen_font = mont_font or ui_font   # Montserrat is the primary UI font
    if chosen_font:
        set_ui_font(chosen_font)
    app.setStyleSheet(build_style(MODES[0]['accent'], False, spectra_theme.UI_SCALE))
    app.setFont(QFont(chosen_font or 'Segoe UI', s(9)))
    splash = create_loading_screen()
    splash.show()
    app.processEvents()
    _t0 = time.monotonic()
    win = MainWindow()
    # Keep the loading screen up for a fixed 10 s total (minus build time)
    _elapsed_ms = int((time.monotonic() - _t0) * 1000)
    _remaining = max(0, 10000 - _elapsed_ms)

    def _reveal():
        if hasattr(splash, '_quip_timer'):
            splash._quip_timer.stop()
        win.showMaximized()
        splash.finish(win)

    QTimer.singleShot(_remaining, _reveal)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
