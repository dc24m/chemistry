# SPECTRAplot Desktop UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the SPECTRAplot PyQt6 UI to resemble classic scientific desktop software (OriginPro/Prism/ImageJ/MATLAB) — `QMainWindow` menu bar + compact toolbar + native status bar, flat dense gray chrome, real dockable panels, denser typography — without touching any scientific calculation or feature.

**Architecture:** Extract the stylesheet into `spectra_theme.py` (re-exported from `spectra_app`). Replace the custom `TopHeader`/`BottomStatusBar` with native `QMainWindow` chrome (menuBar, QToolBar, QStatusBar). Convert the `ControlPanel` and the four "Plot Style" groups into `QDockWidget`s, and add two additive reflection-only docks (Layers, Log). Flatten the visual language (remove shadows/cards) and tighten density in `build_style`. Persist dock layout via `QSettings`.

**Tech Stack:** Python 3, PyQt6, matplotlib (QtAgg backend), pytest/unittest with `QT_QPA_PLATFORM=offscreen`.

---

## File Structure

- **Create** `spectra_theme.py` — `MODES`, `MODE_BY_KEY`, `darken`, `to_rgb`/`to_hex` re-use, `add_shadow`, `build_style`. Single responsibility: palette + QSS generation.
- **Modify** `spectra_app.py` — import theme via `from spectra_theme import *`; remove the moved definitions; rebuild `MainWindow` chrome; convert panels to docks; flatten `PlotCanvas` card; replace status bar.
- **Modify** `tests/test_spectra_ui_layout.py` — point `build_style` source-greps at `spectra_theme`; add dock/menu/toolbar structural assertions.
- **Modify** `tests/test_spectra_static_regressions.py` — retarget the four UI-structure assertions; leave scientific-behavior assertions untouched.
- **Modify** `DESIGN.md` — update doctrine to the classic-desktop direction.

> **Conventions for every task:** run tests headless with `QT_QPA_PLATFORM=offscreen`. On Windows PowerShell use `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest ...`. The existing suite is the safety net — Task 8 runs all of it. Commit after each task.

---

## Task 1: Extract theme module (`spectra_theme.py`)

Moves palette + stylesheet out of `spectra_app.py`. Must keep `spectra_app.build_style`, `spectra_app.MODES`, `spectra_app.MODE_BY_KEY`, `spectra_app.darken`, `spectra_app.add_shadow` resolvable (the tests use `spectra_app.build_style` and `spectra_app.MODES`).

**Files:**
- Create: `spectra_theme.py`
- Modify: `spectra_app.py` (top imports ~7-52; remove `MODES`/`darken` block ~55-112 of `build_style`; remove `add_shadow` ~1359)
- Test: `tests/test_spectra_theme_module.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spectra_theme_module.py
import unittest


class ThemeModuleTest(unittest.TestCase):
    def test_theme_module_owns_build_style_and_modes(self):
        import spectra_theme
        self.assertTrue(hasattr(spectra_theme, "build_style"))
        self.assertTrue(hasattr(spectra_theme, "MODES"))
        self.assertEqual(spectra_theme.MODES[0]["key"], "pl")

    def test_spectra_app_reexports_theme_symbols(self):
        import spectra_app
        import spectra_theme
        # Same object, re-exported — not a divergent copy.
        self.assertIs(spectra_app.build_style, spectra_theme.build_style)
        self.assertIs(spectra_app.MODES, spectra_theme.MODES)

    def test_build_style_accepts_accent_and_dark_flag(self):
        import spectra_theme
        light = spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        dark = spectra_theme.build_style(spectra_theme.MODES[0]["accent"], dark=True)
        self.assertIn("QMainWindow", light)
        self.assertNotEqual(light, dark)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_theme_module.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spectra_theme'`.

- [ ] **Step 3: Create `spectra_theme.py`**

Move these from `spectra_app.py` verbatim into a new `spectra_theme.py`, with the imports they need:

```python
# spectra_theme.py
"""SPECTRAplot theme: mode palette, color helpers, and QSS generation.

Imported wholesale by spectra_app (`from spectra_theme import *`) so
spectra_app.build_style / spectra_app.MODES continue to resolve.
"""
from matplotlib.colors import to_rgb, to_hex
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


def darken(hex_color: str, factor: float = 0.45) -> str:
    """Blend a hue toward black. Used to derive a readable title tone
    for small title text on white, while the bright accent stays for fills."""
    try:
        r, g, b = to_rgb(hex_color)
    except Exception:
        return hex_color
    f = max(0.0, min(1.0, factor))
    r, g, b = (1 - f) * r, (1 - f) * g, (1 - f) * b
    return to_hex((r, g, b))


MODES = [
    {'key': 'pl',         'label': 'Photoluminescence', 'accent': '#F472B6'},
    {'key': 'absorbance', 'label': 'Absorbance',        'accent': '#38BDF8'},
    {'key': 'xrd',        'label': 'XRD',               'accent': '#A78BFA'},
    {'key': 'iv',         'label': 'IV curve',          'accent': '#FBBF24'},
]
for _m in MODES:
    _m['title'] = darken(_m['accent'], 0.45)
MODE_BY_KEY = {m['key']: m for m in MODES}


def add_shadow(widget, blur: int = 24, y: int = 6, alpha: int = 35):
    """Kept for backward compatibility. The redesign is flat, so callers
    generally no longer use this — but it remains importable."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, y)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return eff


def build_style(_accent: str, dark: bool = False) -> str:
    # <<< MOVE the full current body of build_style here unchanged for now.
    # Density/flatten edits happen in Task 6. Keep it identical in this task
    # so the only change is *location*, making the diff reviewable. >>>
    ...
```

Copy the **entire existing `build_style` body** (currently `spectra_app.py:86`-end of the returned f-string) into this function unchanged. Do not edit the QSS content in this task.

- [ ] **Step 4: Wire `spectra_app.py` to the theme module**

In `spectra_app.py`, immediately after the `try/except` import block (after line ~52), add:

```python
from spectra_theme import (
    MODES, MODE_BY_KEY, darken, add_shadow, build_style,
)
```

Then delete the now-duplicated definitions from `spectra_app.py`: the `darken` helper (~55-67), the `MODES`/`MODE_BY_KEY` block (~70-81), the entire `build_style` function (~85 to the end of its return string), and the `add_shadow` function (~1359). Keep `_APP_DARK = False` in `spectra_app.py` (it is app state, not theme).

- [ ] **Step 5: Run the theme test + import smoke**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_theme_module.py -v`
Expected: PASS (3 tests).
Run: `python -c "import spectra_app; print(spectra_app.build_style(spectra_app.MODES[0]['accent'])[:20])"`
Expected: prints the start of the QSS, no ImportError.

- [ ] **Step 6: Update the UI-layout test's source target**

`tests/test_spectra_ui_layout.py` greps the live string from `build_style(...)` (runtime call), so `test_inner_tab_panes_do_not_add_extra_framing_lines` keeps working unchanged — it already calls `spectra_app.build_style`. No change needed here yet; confirm by running it:

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_ui_layout.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add spectra_theme.py spectra_app.py tests/test_spectra_theme_module.py
git commit -m "refactor: extract stylesheet/palette into spectra_theme module"
```

---

## Task 2: Native window chrome — menu bar, toolbar, status bar

Replace `TopHeader` (mode tabs + PLOT + Dark) and `BottomStatusBar` with native `QMainWindow` chrome. The custom classes stay defined for now (removed only if unused after wiring); the goal of this task is the new chrome existing and driving the same signals.

**Files:**
- Modify: `spectra_app.py` top imports (~21-33); `MainWindow.__init__` (~3260-3361); `_on_theme_toggle` (~3371); `_on_coord_motion` (~3379)
- Test: `tests/test_spectra_window_chrome.py`

- [ ] **Step 1: Add the required Qt imports**

In the `QtWidgets` import tuple add `QToolBar`, `QStatusBar`, `QDockWidget`, `QTableWidget`, `QTableWidgetItem`, `QHeaderView`, `QPlainTextEdit`. In the `QtCore` import add `QSettings`, `QByteArray`. In the `QtGui` import add `QAction`, `QActionGroup`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_spectra_window_chrome.py
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QStatusBar, QToolBar
import spectra_app

_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    _APP.setStyleSheet(spectra_app.build_style(spectra_app.MODES[0]["accent"]))
    return _APP


class WindowChromeTest(unittest.TestCase):
    def test_window_has_native_menu_toolbar_statusbar(self):
        qapp()
        win = spectra_app.MainWindow()
        # Menu bar with the expected top-level menus
        titles = [m.title().replace("&", "") for m in win.menuBar().findChildren(type(win.menuBar().addMenu("x")))]
        # Simpler: check action texts on the menubar
        menu_titles = [a.text().replace("&", "") for a in win.menuBar().actions()]
        for expected in ("File", "Edit", "View", "Plot", "Help"):
            self.assertIn(expected, menu_titles)
        self.assertIsInstance(win.findChild(QToolBar), QToolBar)
        self.assertIsInstance(win.statusBar(), QStatusBar)

    def test_toolbar_plot_action_triggers_plot(self):
        qapp()
        win = spectra_app.MainWindow()
        fired = []
        win.controls.plot_requested.connect(lambda: fired.append(True))
        win.act_plot.trigger()
        self.assertTrue(fired or win._plot_called_for_test)

    def test_mode_actions_switch_control_panel_mode(self):
        qapp()
        win = spectra_app.MainWindow()
        win.mode_actions["xrd"].trigger()
        self.assertEqual(win.controls.current_mode(), "xrd")


if __name__ == "__main__":
    unittest.main()
```

> Note: the first test's `findChildren` line is awkward; replace with the menu_titles check only. Keep the menu_titles assertion as the real check.

- [ ] **Step 3: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_window_chrome.py -v`
Expected: FAIL — `win.act_plot` / `win.mode_actions` do not exist; no menu bar populated.

- [ ] **Step 4: Build the chrome in `MainWindow.__init__`**

Add a helper `_build_chrome()` called early in `__init__` (after `self.controls`/`self.canvas` exist). Insert this method on `MainWindow`:

```python
def _build_chrome(self):
    # ── Actions (shared by menu + toolbar) ──────────────────────────────
    self.act_plot = QAction("Plot", self)
    self.act_plot.setShortcut("Ctrl+Return")
    self.act_plot.triggered.connect(self._do_plot)

    self.act_save = QAction("Save Figure…", self)
    self.act_save.setShortcut(QKeySequence.StandardKey.Save)
    self.act_save.triggered.connect(lambda: self.controls._save("png"))

    self.act_undo = QAction("Undo", self)
    self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
    self.act_undo.triggered.connect(self.editor.undo_stack.undo)

    self.act_fit = QAction("Fit to Data", self)
    self.act_fit.triggered.connect(self.canvas._toolbar_fit)
    self.act_grid = QAction("Grid", self); self.act_grid.setCheckable(True)
    self.act_grid.toggled.connect(self.canvas._toolbar_grid)
    self.act_zoom_in = QAction("Zoom In", self)
    self.act_zoom_in.triggered.connect(lambda: self.canvas._zoom_by(1.25))
    self.act_zoom_out = QAction("Zoom Out", self)
    self.act_zoom_out.triggered.connect(lambda: self.canvas._zoom_by(1 / 1.25))

    self.act_dark = QAction("Dark Mode", self); self.act_dark.setCheckable(True)
    self.act_dark.toggled.connect(self._on_theme_toggle)

    self.act_quit = QAction("Exit", self)
    self.act_quit.setShortcut("Ctrl+Q")
    self.act_quit.triggered.connect(self.close)

    self.act_about = QAction("About SPECTRAplot", self)
    self.act_about.triggered.connect(self._show_about)

    self.act_reset_layout = QAction("Reset Layout", self)
    self.act_reset_layout.triggered.connect(self._reset_layout)

    # Mode actions (exclusive) — replaces the header ModeTabBar
    self.mode_actions = {}
    self._mode_group = QActionGroup(self)
    self._mode_group.setExclusive(True)
    for m in MODES:
        a = QAction(m["label"], self); a.setCheckable(True)
        a.setObjectName(f"modeAction_{m['key']}")
        a.triggered.connect(lambda _checked, k=m["key"]: self._on_mode_change(k))
        self._mode_group.addAction(a)
        self.mode_actions[m["key"]] = a
    self.mode_actions[MODES[0]["key"]].setChecked(True)

    # ── Menu bar ────────────────────────────────────────────────────────
    mb = self.menuBar()
    m_file = mb.addMenu("&File")
    m_file.addAction(self.act_save)
    m_file.addSeparator(); m_file.addAction(self.act_quit)
    m_edit = mb.addMenu("&Edit"); m_edit.addAction(self.act_undo)
    self.m_view = mb.addMenu("&View")   # dock toggles appended in Task 3/4
    self.m_view.addAction(self.act_dark)
    self.m_view.addAction(self.act_reset_layout)
    self.m_view.addSeparator()
    m_plot = mb.addMenu("&Plot")
    m_plot.addAction(self.act_plot); m_plot.addSeparator()
    m_plot.addAction(self.act_fit); m_plot.addAction(self.act_grid)
    m_plot.addAction(self.act_zoom_in); m_plot.addAction(self.act_zoom_out)
    m_plot.addSeparator()
    for a in self.mode_actions.values():
        m_plot.addAction(a)
    m_help = mb.addMenu("&Help"); m_help.addAction(self.act_about)

    # ── Toolbar ─────────────────────────────────────────────────────────
    tb = QToolBar("Main", self)
    tb.setObjectName("mainToolbar")
    tb.setMovable(False)
    tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    wm = QLabel("SPECTRAplot")
    wm.setObjectName("toolbarWordmark")
    tb.addWidget(wm)
    tb.addSeparator()
    tb.addAction(self.act_plot)
    tb.addAction(self.act_save)
    tb.addSeparator()
    for a in self.mode_actions.values():
        tb.addAction(a)
    tb.addSeparator()
    tb.addAction(self.act_fit)
    tb.addAction(self.act_zoom_out); tb.addAction(self.act_zoom_in)
    tb.addAction(self.act_grid)
    self.addToolBar(tb)
    self.toolbar = tb

    # ── Status bar ──────────────────────────────────────────────────────
    sb = self.statusBar()
    self._sb_ready = QLabel("● Ready")
    self._sb_ready.setObjectName("readyDot")
    self._sb_coord = QLabel("")
    self._sb_coord.setObjectName("coordLabel")
    sb.addPermanentWidget(self._sb_coord)
    sb.insertWidget(0, self._sb_ready)
```

Add the small support methods used above:

```python
def _show_about(self):
    QMessageBox.about(self, "SPECTRAplot",
                      "SPECTRAplot — spectrometry visualization\nby arnold wijoyo")

def _reset_layout(self):
    if getattr(self, "_default_state", None) is not None:
        self.restoreState(self._default_state)

# status-bar shims so existing call sites keep working
def _status_message(self, msg: str):
    self.statusBar().showMessage(msg)

def _status_ready(self, ok: bool):
    self._sb_ready.setText("● Ready" if ok else "● Busy")
```

- [ ] **Step 5: Replace `TopHeader`/`BottomStatusBar` usage in `__init__`**

In `MainWindow.__init__`: delete the `self.header = TopHeader()` block and its `vlay.addWidget(self.header)`. Delete `self.statusbar = BottomStatusBar()` and its `right_lay.addWidget(self.statusbar)`. Call `self._build_chrome()` after `self.editor = FigureEditor(self.canvas)`. Rewire the former header connections:
- Replace `self.header.plot_requested.connect(self._do_plot)` — now handled by `act_plot`.
- Replace `self.header.mode_changed.connect(self._on_mode_change)` — now via `mode_actions`.
- Replace `self.header.theme_toggled.connect(self._on_theme_toggle)` — now via `act_dark`.
- Update `self.statusbar.show_message(...)` → `self._status_message(...)`.
- In `_on_coord_motion`, replace `self.statusbar.update_coords(text)`/`clear_coords()` with `self._sb_coord.setText(text)` / `self._sb_coord.clear()`.
- In `_on_theme_toggle`, remove `self.header.btn_theme.setText(...)` and `self.header.apply_theme(dark)` lines (keep the global `_APP_DARK` + `setStyleSheet`). Set `self.act_dark.setChecked(dark)` defensively (it is the source, so guard against recursion is unnecessary since toggled only fires on change).

Add `self._plot_called_for_test = False` in `__init__` and set it `True` at the top of `_do_plot` (lets the chrome test assert the action path without a full plot).

- [ ] **Step 6: Run test to verify it passes**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_window_chrome.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add spectra_app.py tests/test_spectra_window_chrome.py
git commit -m "feat: native QMainWindow menu bar, toolbar, and status bar"
```

---

## Task 3: Convert ControlPanel and Plot Style into QDockWidgets

Replace the horizontal/vertical `QSplitter` arrangement with real docks. The canvas becomes the central widget.

**Files:**
- Modify: `spectra_app.py` `MainWindow.__init__` (the splitter/dock/right_pane block ~3269-3342)
- Test: extend `tests/test_spectra_window_chrome.py`

- [ ] **Step 1: Write the failing test (append to chrome test file)**

```python
    def test_core_panels_are_dock_widgets(self):
        from PyQt6.QtWidgets import QDockWidget
        qapp()
        win = spectra_app.MainWindow()
        names = {d.objectName() for d in win.findChildren(QDockWidget)}
        self.assertIn("dock_build", names)
        self.assertIn("dock_style", names)
        # Canvas is the central widget, not inside a splitter pane
        self.assertIs(win.centralWidget(), win.canvas)

    def test_view_menu_lists_dock_toggles(self):
        qapp()
        win = spectra_app.MainWindow()
        view_actions = [a.text() for a in win.m_view.actions()]
        joined = " ".join(view_actions)
        self.assertIn("Build", joined)
        self.assertIn("Plot Style", joined)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_window_chrome.py -k dock -v`
Expected: FAIL — no `QDockWidget`s; central widget is the splitter root.

- [ ] **Step 3: Replace the splitter layout with docks**

In `MainWindow.__init__`, delete the `splitter`, `dock`/`dock_card`/`dock_scroll`, `right_pane`, and `v_splitter` construction (~3269-3342) and the `root`/`vlay`/`setCentralWidget(root)` block. Replace with:

```python
    # Central widget: the plot canvas
    self.setCentralWidget(self.canvas)

    # ── Left dock: Build / Parameters (the ControlPanel) ────────────────
    self.dock_build = QDockWidget("Build", self)
    self.dock_build.setObjectName("dock_build")
    self.dock_build.setWidget(self.controls)
    self.dock_build.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
    self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_build)

    # ── Bottom dock: Plot Style (the four style groups) ─────────────────
    style_host = QWidget()
    style_host.setObjectName("plotStyleHost")
    style_lay = QHBoxLayout(style_host)
    style_lay.setContentsMargins(8, 6, 8, 8)
    style_lay.setSpacing(10)
    for group in self.controls.take_dock_groups():
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        style_lay.addWidget(group)
    style_lay.addStretch()
    style_scroll = QScrollArea()
    style_scroll.setObjectName("plotStyleScroll")
    style_scroll.setWidget(style_host)
    style_scroll.setWidgetResizable(True)
    style_scroll.setFrameShape(QFrame.Shape.NoFrame)
    style_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    self.dock_style = QDockWidget("Plot Style", self)
    self.dock_style.setObjectName("dock_style")
    self.dock_style.setWidget(style_scroll)
    self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_style)

    # View-menu toggles (insert before the Dark Mode action block)
    self.m_view.insertAction(self.act_dark, self.dock_build.toggleViewAction())
    self.m_view.insertAction(self.act_dark, self.dock_style.toggleViewAction())
    self.m_view.insertSeparator(self.act_dark)

    self.resizeDocks([self.dock_build], [360], Qt.Orientation.Horizontal)
```

The `ControlPanel` still has `setFixedWidth(368)` in its own `__init__`; relax that in Task 5 so dock resizing works. For now `resizeDocks` is harmless.

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_window_chrome.py -v`
Expected: PASS (all chrome + dock tests).

- [ ] **Step 5: Commit**

```bash
git add spectra_app.py tests/test_spectra_window_chrome.py
git commit -m "feat: ControlPanel and Plot Style become dockable QDockWidgets"
```

---

## Task 4: Additive docks — Layers (Trace Manager) and Log

Two new docks that **reflect existing state only**. Layers lists traces from the current settings; Log echoes status messages. No scientific behavior changes.

**Files:**
- Create: nothing (classes added inline in `spectra_app.py`)
- Modify: `spectra_app.py` (add `LayersDock`, `LogDock` classes near `BottomStatusBar`; wire in `MainWindow`)
- Test: `tests/test_spectra_aux_docks.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spectra_aux_docks.py
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDockWidget
import spectra_app

_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    _APP.setStyleSheet(spectra_app.build_style(spectra_app.MODES[0]["accent"]))
    return _APP


class AuxDockTest(unittest.TestCase):
    def test_layers_and_log_docks_exist(self):
        qapp()
        win = spectra_app.MainWindow()
        names = {d.objectName() for d in win.findChildren(QDockWidget)}
        self.assertIn("dock_layers", names)
        self.assertIn("dock_log", names)

    def test_log_appends_status_messages(self):
        qapp()
        win = spectra_app.MainWindow()
        win._status_message("Hello log")
        self.assertIn("Hello log", win.log_dock.text())

    def test_layers_reflects_trace_rows_without_plotting(self):
        qapp()
        win = spectra_app.MainWindow()
        rows = [
            {"label": "Sample A", "color": "#F472B6", "visible": True},
            {"label": "Sample B", "color": "#38BDF8", "visible": False},
        ]
        win.layers_dock.set_rows(rows)
        self.assertEqual(win.layers_dock.row_count(), 2)
        self.assertEqual(win.layers_dock.label_at(0), "Sample A")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_aux_docks.py -v`
Expected: FAIL — `dock_layers`/`dock_log`/`layers_dock`/`log_dock` undefined.

- [ ] **Step 3: Add the two widgets (near `BottomStatusBar`, ~3216)**

```python
class LayersPanel(QWidget):
    """Read-only reflection of the traces in the current plot settings.
    Double-click a row to open the existing TraceEditDialog on that trace."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("layersPanel")
        self._rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("layersTable")
        self.table.setHorizontalHeaderLabels(["", "Trace", "Vis"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.table)
        empty = QLabel("No traces yet — add data and Plot.")
        empty.setObjectName("hint")
        lay.addWidget(empty)
        self._empty = empty

    def set_rows(self, rows: list):
        self._rows = list(rows)
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            swatch = QTableWidgetItem("")
            swatch.setBackground(QColor(r.get("color", "#000000")))
            self.table.setItem(i, 0, swatch)
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("label", f"Trace {i+1}"))))
            self.table.setItem(i, 2, QTableWidgetItem("●" if r.get("visible", True) else "○"))
        self._empty.setVisible(len(self._rows) == 0)

    def row_count(self) -> int:
        return self.table.rowCount()

    def label_at(self, i: int) -> str:
        item = self.table.item(i, 1)
        return item.text() if item else ""


class LogPanel(QWidget):
    """Append-only message console echoing status-bar messages."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(0)
        self.view = QPlainTextEdit()
        self.view.setObjectName("logView")
        self.view.setReadOnly(True)
        lay.addWidget(self.view)

    def append(self, msg: str):
        self.view.appendPlainText(msg)

    def text(self) -> str:
        return self.view.toPlainText()
```

- [ ] **Step 4: Wire the docks in `MainWindow.__init__`** (after `dock_style` is added)

```python
    self.layers_dock = LayersPanel()
    self.dock_layers = QDockWidget("Layers", self)
    self.dock_layers.setObjectName("dock_layers")
    self.dock_layers.setWidget(self.layers_dock)
    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_layers)

    self.log_dock = LogPanel()
    self.dock_log = QDockWidget("Log", self)
    self.dock_log.setObjectName("dock_log")
    self.dock_log.setWidget(self.log_dock)
    self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_log)
    self.tabifyDockWidget(self.dock_style, self.dock_log)
    self.dock_style.raise_()

    self.m_view.insertAction(self.act_dark, self.dock_layers.toggleViewAction())
    self.m_view.insertAction(self.act_dark, self.dock_log.toggleViewAction())
```

Update `_status_message` to also echo to the log:

```python
def _status_message(self, msg: str):
    self.statusBar().showMessage(msg)
    self.log_dock.append(msg)
```

In `_do_plot`, after a successful plot, refresh Layers from the trace settings the app already builds. Locate where `_do_plot` assembles settings (it calls `self.controls.settings()`); add — guarded, reflection-only:

```python
    try:
        cfg = self.controls.settings()
        rows = []
        for panel in cfg.get("panels", []):
            for tr in panel.get("traces", panel.get("files", [])):
                rows.append({
                    "label": tr.get("label", tr.get("name", "")),
                    "color": tr.get("color", "#000000"),
                    "visible": tr.get("visible", True),
                })
        self.layers_dock.set_rows(rows)
    except Exception:
        pass  # Layers is a reflection; never let it break plotting.
```

> Adjust the `cfg`/panel key names to match what `ControlPanel.settings()` actually returns (inspect it — see `settings()` at ~2028). The shape above is the contract; map real keys to `label`/`color`/`visible`. The `except` guard guarantees plotting is unaffected.

- [ ] **Step 5: Run test to verify it passes**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_aux_docks.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add spectra_app.py tests/test_spectra_aux_docks.py
git commit -m "feat: add reflection-only Layers and Log docks"
```

---

## Task 5: Density, typography, and dock sizing in build_style + ControlPanel

Tighten spacing/typography and relax the fixed sidebar width so docks resize naturally. All edits are in `spectra_theme.build_style` (QSS) and `ControlPanel`/`PlotCanvas` sizing.

**Files:**
- Modify: `spectra_theme.py` `build_style` (global font, QGroupBox padding, QPushButton min-height; add `QToolBar`, `QDockWidget`, `QMenuBar`, `QStatusBar`, `QTableWidget`, `QPlainTextEdit` rules)
- Modify: `spectra_app.py` `ControlPanel.__init__` (`setFixedWidth(368)` → min/max range)
- Test: `tests/test_spectra_ui_layout.py` (update width assertion); `tests/test_spectra_theme_chrome_style.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spectra_theme_chrome_style.py
import unittest
import spectra_theme


class ChromeStyleTest(unittest.TestCase):
    def test_style_covers_native_chrome_widgets(self):
        css = spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        for sel in ("QToolBar", "QMenuBar", "QStatusBar",
                    "QDockWidget", "QDockWidget::title", "QTableWidget"):
            self.assertIn(sel, css)

    def test_density_is_compact(self):
        css = spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        # Buttons tightened from 30px to <=26px min-height
        self.assertIn("min-height: 26px;", css)

    def test_toolbar_mode_action_uses_accent_when_checked(self):
        css = spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        block = css.split("QToolButton:checked {", 1)[1].split("}", 1)[0]
        self.assertIn(spectra_theme.MODES[0]["accent"], block)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_theme_chrome_style.py -v`
Expected: FAIL — chrome selectors and `min-height: 26px;` absent; no `QToolButton:checked` block.

- [ ] **Step 3: Edit `build_style` for density**

In `spectra_theme.build_style`:
- Change `QPushButton { ... min-height: 30px; ... }` → `min-height: 26px;` and `padding: 5px 14px;` → `padding: 4px 12px;`.
- Change `QGroupBox { ... padding: 34px 12px 12px 12px; }` → `padding: 22px 10px 10px 10px;` and `QGroupBox::title { top: 10px; ... }` → `top: 6px;`.

- [ ] **Step 4: Append chrome rules to the QSS** (inside the returned f-string, before the closing `"""`)

```python
/* ── Native chrome ──────────────────────────────────────────────────── */
QMenuBar {{ background: {SURF}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {HOVER}; }}
QMenu {{ background: {BG}; border: 1px solid {BORDER}; }}
QMenu::item {{ padding: 5px 22px; }}
QMenu::item:selected {{ background: {HOVER}; }}

QToolBar#mainToolbar {{
    background: {SURF}; border-bottom: 1px solid {BORDER};
    spacing: 4px; padding: 3px 6px;
}}
QToolBar::separator {{ background: {BORDER}; width: 1px; margin: 4px 6px; }}
QLabel#toolbarWordmark {{ font-weight: 800; letter-spacing: -0.3px; padding: 0 8px 0 2px; }}
QToolButton {{
    background: transparent; border: 1px solid transparent;
    border-radius: 5px; padding: 4px 10px; min-height: 22px;
}}
QToolButton:hover {{ background: {HOVER}; border-color: {BORDER}; }}
QToolButton:checked {{ background: {ACCENT}; color: #FFFFFF; border-color: {ACCENT}; }}

QStatusBar {{ background: {SURF}; border-top: 1px solid {BORDER}; }}
QStatusBar QLabel#coordLabel {{ font-family: 'IBM Plex Mono','Fira Code',monospace; color: {MUTED}; }}
QStatusBar::item {{ border: none; }}

QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{
    background: {SURF2}; padding: 4px 8px; border-bottom: 1px solid {BORDER};
    font-weight: 700; font-size: 11px; letter-spacing: 0.4px;
}}

QTableWidget#layersTable {{ background: {BG}; gridline-color: {BORDER}; border: none; }}
QHeaderView::section {{
    background: {SURF}; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 3px 6px; font-weight: 700;
}}
QPlainTextEdit#logView {{
    background: {BG}; border: none; color: {MUTED};
    font-family: 'IBM Plex Mono','Fira Code',monospace; font-size: 11px;
}}
```

- [ ] **Step 5: Relax the ControlPanel fixed width**

In `spectra_app.py` `ControlPanel.__init__`, replace `self.setFixedWidth(368)` with:

```python
        self.setMinimumWidth(320)
        self.setMaximumWidth(460)
```

Update `tests/test_spectra_ui_layout.py::test_control_panel_is_wide_enough_for_dense_iv_controls` to assert `>= 320` (was 360), since the lower bound changed:

```python
        self.assertGreaterEqual(panel.width(), 320)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_theme_chrome_style.py tests/test_spectra_ui_layout.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add spectra_theme.py spectra_app.py tests/test_spectra_theme_chrome_style.py tests/test_spectra_ui_layout.py
git commit -m "feat: compact density + native-chrome styling; resizable left dock"
```

---

## Task 6: Flatten visual language (remove shadow/card elevation)

Remove SaaS-style shadows and rounded cards from the canvas; rely on borders + tonal grays.

**Files:**
- Modify: `spectra_app.py` `PlotCanvas.__init__` (~2441-2447, 2536) — drop `add_shadow`, flatten `canvasCard`
- Modify: `spectra_theme.py` `build_style` — `#canvasCard` rule to flat border
- Modify: `tests/test_spectra_static_regressions.py::test_plot_canvas_uses_soft_canvas_card`

- [ ] **Step 1: Update the regression test to expect a flat canvas**

Replace `test_plot_canvas_uses_soft_canvas_card` in `tests/test_spectra_static_regressions.py` with:

```python
    def test_plot_canvas_is_flat_without_drop_shadow(self):
        source = SOURCE.read_text(encoding="utf-8")
        # The canvas frame is flat: no drop-shadow on the canvas card.
        self.assertNotIn("add_shadow(self.card", source)
        self.assertIn("setObjectName('canvasFrame')", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_static_regressions.py::SpectraStaticRegressionTest::test_plot_canvas_is_flat_without_drop_shadow -v`
Expected: FAIL — `add_shadow(self.card` still present; no `canvasFrame`.

- [ ] **Step 3: Flatten `PlotCanvas`**

In `spectra_app.py` `PlotCanvas.__init__`:
- Rename `self.card.setObjectName('canvasCard')` → `self.card.setObjectName('canvasFrame')`.
- Delete the line `add_shadow(self.card, blur=32, y=10, alpha=28)`.
- Reduce the outer margins for density: `lay.setContentsMargins(14, 14, 14, 8)` → `lay.setContentsMargins(0, 0, 0, 0)` and `card_lay.setContentsMargins(10, 10, 10, 10)` → `card_lay.setContentsMargins(6, 6, 6, 6)`.

- [ ] **Step 4: Update the QSS for the flat frame**

In `spectra_theme.build_style`, find the `#canvasCard` rule and rename/flatten it:

```python
#canvasFrame {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 0px;
}}
```

(If no `#canvasCard` rule exists, add the above near the canvas rules.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_static_regressions.py -k canvas -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add spectra_app.py spectra_theme.py tests/test_spectra_static_regressions.py
git commit -m "feat: flatten canvas chrome — remove drop shadow and rounded card"
```

---

## Task 7: Layout persistence + retarget remaining UI-structure tests

Persist dock geometry/state across sessions and fix the last two source-grep regression tests that referenced removed chrome.

**Files:**
- Modify: `spectra_app.py` `MainWindow` (`__init__` end, add `closeEvent`, capture `_default_state`)
- Modify: `tests/test_spectra_static_regressions.py` (`test_main_window_attaches_bottom_dock_groups`, `test_selected_tabs_use_full_accent_fill`)
- Test: `tests/test_spectra_window_chrome.py` (persistence round-trip)

- [ ] **Step 1: Write the failing persistence test (append to chrome test file)**

```python
    def test_layout_state_round_trips(self):
        qapp()
        win = spectra_app.MainWindow()
        win._default_state = win.saveState()
        win.dock_layers.setFloating(True)
        win.restoreState(win._default_state)
        self.assertFalse(win.dock_layers.isFloating())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_window_chrome.py -k round_trips -v`
Expected: FAIL — `_default_state` not set in `__init__`.

- [ ] **Step 3: Add persistence to `MainWindow`**

At the end of `__init__` (after all docks added):

```python
    self._settings = QSettings("SPECTRAplot", "SPECTRAplot")
    self._default_state = self.saveState()
    self._default_geometry = self.saveGeometry()
    geo = self._settings.value("geometry")
    st = self._settings.value("winstate")
    if isinstance(geo, QByteArray):
        self.restoreGeometry(geo)
    if isinstance(st, QByteArray):
        self.restoreState(st)
```

Add the method:

```python
def closeEvent(self, event):
    self._settings.setValue("geometry", self.saveGeometry())
    self._settings.setValue("winstate", self.saveState())
    super().closeEvent(event)
```

- [ ] **Step 4: Retarget the two remaining UI-structure regression tests**

In `tests/test_spectra_static_regressions.py`:

Replace `test_main_window_attaches_bottom_dock_groups` with:

```python
    def test_main_window_hosts_plot_style_dock(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("take_dock_groups()", source)
        self.assertIn('setObjectName("dock_style")', source)
```

Replace `test_selected_tabs_use_full_accent_fill` with (accent now lives on toolbar mode buttons + tab selection):

```python
    def test_selected_controls_use_full_accent_fill(self):
        import spectra_theme
        css = spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        tb_block = css.split("QToolButton:checked {", 1)[1].split("}", 1)[0]
        tab_block = css.split("QTabBar::tab:selected {", 1)[1].split("}", 1)[0]
        self.assertIn(spectra_theme.MODES[0]["accent"], tb_block)
        self.assertIn("background:", tab_block)
```

> The original `test_selected_tabs_use_full_accent_fill` used `{ACCENT}`/`{{`-escaped greps against the raw f-string source. Since `build_style` moved to `spectra_theme.py`, assert against the **rendered** CSS instead (more robust). Keep `QTabBar::tab:selected` accent fill present in the QSS; if it isn't, add `QTabBar::tab:selected {{ background: {ACCENT}; color: #FFFFFF; }}`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_spectra_window_chrome.py tests/test_spectra_static_regressions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add spectra_app.py tests/test_spectra_static_regressions.py tests/test_spectra_window_chrome.py
git commit -m "feat: persist dock layout via QSettings; retarget UI-structure tests"
```

---

## Task 8: Full-suite verification + manual smoke + docs

Confirm no scientific-behavior regressions, smoke-launch the app, and update `DESIGN.md`.

**Files:**
- Modify: `DESIGN.md`
- Remove (if now unused): `TopHeader`, `BottomStatusBar`, `ModeTabBar` classes in `spectra_app.py`

- [ ] **Step 1: Run the entire test suite**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/ -v`
Expected: ALL PASS. The scientific-behavior tests in `test_spectra_static_regressions.py`
(`do_plot` limits, `_style_ax` padding, canvas-size skip, IV dataset UI, trace-color
fallbacks, pandas-not-imported, missing-dep message, wait-cursor, figure-size-from-toolbar)
must pass **unchanged**. Also run `tests/test_spectra_plotting_behavior.py` and
`tests/test_loading_screen.py`.

- [ ] **Step 2: Remove dead chrome classes**

Search for remaining references: `grep -n "TopHeader\|BottomStatusBar\|ModeTabBar" spectra_app.py`. If the only matches are the class definitions themselves (no instantiation), delete the `TopHeader`, `BottomStatusBar`, and `ModeTabBar` class bodies. If `ModeTabBar` is still referenced, leave it. Re-run the suite after deletion.

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/ -q`
Expected: ALL PASS.

- [ ] **Step 3: Manual smoke launch**

Run: `python spectra_app.py`
Verify by observation: menu bar (File/Edit/View/Plot/Help) present; toolbar with Plot + mode buttons + Fit/Zoom/Grid; left "Build" dock, bottom "Plot Style"/"Log" tabs, right "Layers" dock; docks float/redock when dragged; View menu toggles each; Dark Mode toggles theme; clicking a mode button reskins accent; adding files + Plot renders and the Layers dock fills. Close and reopen — layout is restored.

> If launching headless/CI, skip Step 3 and note it was skipped.

- [ ] **Step 4: Update `DESIGN.md`**

Replace the "Monochrome Instrument / no-toolbar" doctrine intro and the Do/Don't items that forbid toolbars with the classic-desktop direction: native `QMainWindow` chrome (menu bar, compact toolbar, status bar), dockable panels, flat gray chrome (no shadows/cards), compact density, IBM Plex Mono for measured values retained, accent reserved for active/checked controls + trace identity. Keep the palette/typography tables. Update the seed comment at the top.

- [ ] **Step 5: Commit**

```bash
git add spectra_app.py DESIGN.md
git commit -m "chore: remove dead chrome classes; update DESIGN.md for desktop redesign"
```

---

## Self-Review Notes

- **Spec coverage:** Window shell (Task 2), hybrid docking incl. Layers+Log (Tasks 3-4), density/typography (Task 5), responsiveness/dock sizing (Tasks 3,5), theme light-default + dark toggle (Task 2 wiring + existing palettes), light split (Task 1), flatten (Task 6), persistence (Task 7), test impact handled across Tasks 1,5,6,7, DESIGN.md (Task 8). All spec sections map to tasks.
- **Scientific tests preserved:** explicitly verified in Task 8 Step 1; only the four named UI-structure assertions are retargeted (Tasks 6,7) plus the theme-location greps (Tasks 1,5).
- **Type/name consistency:** `dock_build`, `dock_style`, `dock_layers`, `dock_log` object names; `LayersPanel.set_rows/row_count/label_at`; `LogPanel.append/text`; `MainWindow.act_plot`, `mode_actions`, `_status_message`, `_status_ready`, `_default_state`, `_reset_layout`, `_show_about` — used consistently across tasks.
- **Known follow-up flagged for the implementer:** in Task 4 Step 4, the exact key names from `ControlPanel.settings()` must be confirmed against `spectra_app.py:2028` and mapped to `label`/`color`/`visible`; the `try/except` guard keeps plotting safe regardless.
