# SPECTRAplot — Classic Scientific Desktop UI Redesign

**Date:** 2026-06-13
**Status:** Approved (design)
**Scope:** PyQt6 UI architecture, layout, theming, docking, and visual hierarchy only. **No changes to scientific calculations or features.**

## Goal

Rework the SPECTRAplot PyQt6 interface to resemble modern scientific desktop
software (OriginPro, GraphPad Prism, ImageJ, MATLAB): a `QMainWindow` chrome
stack (menu bar + compact toolbar + native status bar), flat dense gray chrome,
real dockable panels, professional typography, and responsive splitter/dock
layout. Use native Qt widgets only — no web paradigms (no soft shadows, no
rounded "cards", no SaaS softness).

## Decisions (locked)

1. **Aesthetic:** Full classic scientific-software look. Overrides the existing
   `DESIGN.md` "Monochrome Instrument / no-toolbar" doctrine. `DESIGN.md` will be
   updated to reflect the new direction.
2. **Docking:** Hybrid. Core controls + style controls become `QDockWidget`s;
   two additive reflection-only docks (Layers, Log) are added.
3. **Theme:** Light by default, dark toggle retained (moved to View menu +
   toolbar).
4. **Code structure:** Light split — extract the stylesheet/theme into
   `spectra_theme.py`; keep the rest in `spectra_app.py`.

## Current architecture (baseline)

- `TopHeader` (fixed 78px): logo + "SPECTRAplot" wordmark + `ModeTabBar`
  (PL/Absorbance/XRD/IV) + large PLOT button + Dark toggle.
- Horizontal `QSplitter`: `ControlPanel` (fixed 368px `QScrollArea` sidebar;
  groups Plot, Data, IV Curve Data, Axes, PL Options, XRD Options) │ right pane.
- Right pane: vertical `QSplitter` [matplotlib canvas card │ bottom "dock card"
  holding 4 groups: Ticks, Numbers, Legend, Plot Box] + custom `BottomStatusBar`.
- `build_style(accent, dark)` generates all QSS; uses soft shadows (`add_shadow`)
  and rounded `canvasCard` / `dockCard` elevation.
- Scientific core (untouched): `do_plot`, `_style_ax`, IV/XRD/PL logic,
  `FigureEditor` (draggable text/legend), undo stack, `PlotCanvas` toolbar,
  figure-size math.

## Target architecture

### 1. Window shell & chrome

Replace the tall custom `TopHeader` with a true `QMainWindow` chrome stack:

- **Menu bar:** `File` (Open…, Save PNG/SVG/PDF, Exit) · `Edit` (Undo) · `View`
  (toggle each dock, Reset layout, Dark mode) · `Plot` (Plot, Fit, Reset zoom,
  Grid) · `Help` (About).
- **Compact `QToolBar`** (~32px single row): `Plot` (primary/accent action),
  `Save`, separator, mode selector (segmented buttons reusing `ModeTabBar`
  styling), separator, `Fit`, `Zoom +/−`, `Grid` toggle, `Snap` toggle. A slim
  "SPECTRAplot" wordmark sits at the toolbar's left edge.
- **Native `QStatusBar`** replaces custom `BottomStatusBar`: coord readout (mono
  font), a Ready/● indicator widget, transient messages.

**Visual language:** flat, dense, neutral gray chrome. Remove soft shadows and
rounded card elevation (`add_shadow`, `canvasCard`/`dockCard` shadows). Borders +
tonal grays provide separation.

### 2. Docking architecture (hybrid)

- **Left dock — "Build / Parameters":** existing `ControlPanel`, restyled
  denser. Floatable, closable.
- **Bottom dock — "Plot Style":** the existing 4 groups (Ticks/Numbers/Legend/
  Box) as a real `QDockWidget`, replacing the splitter dock card.
- **Right dock — "Layers" (Trace Manager) [additive]:** `QTableWidget`/list
  mirroring already-loaded traces (name, color swatch, visibility). Double-click
  opens the existing `TraceEditDialog`. Pure reflection of existing data — no new
  scientific behavior.
- **Bottom dock tab — "Log" [additive]:** read-only message console echoing
  plot/load/error events already produced by the app.
- **Central widget:** matplotlib canvas + its existing toolbar.
- `View` menu toggles each dock. `QMainWindow.saveState()`/`restoreState()` via
  `QSettings` persists layout across sessions; "Reset layout" restores defaults.

### 3. Density, typography, spacing

- Global font 12 → 11–12px; `QGroupBox` top padding 34 → ~22px; layout spacing
  6 → 4–5px; button min-height 30 → 26px.
- Keep IBM Plex Sans / Segoe UI Variable for UI; **IBM Plex Mono for all measured
  values** (coords, ticks) — preserved.
- Group-box titles styled as compact tracked section headers (MATLAB property-
  panel feel).

### 4. Responsiveness & scaling

- `QSplitter` stretch factors + dock min/max widths so the canvas always wins
  space; left dock width range ~320–400px instead of hard-fixed 368.
- High-DPI: ensure `devicePixelRatio` flows to the matplotlib figure. **Figure
  size math is not modified** — only surrounding layout.

### 5. Theme

- Light default, dark toggle (in View menu + toolbar). Refine both palettes
  toward neutral OriginPro/MATLAB grays. Plot canvas stays white for publication
  output.

### 6. Code structure (light split)

- New `spectra_theme.py`: `build_style`, palettes, `MODES`, `MODE_BY_KEY`,
  `darken`, `add_shadow` (kept for compatibility even if unused). Re-exported from
  `spectra_app` (`from spectra_theme import *`) so `spectra_app.build_style` and
  `spectra_app.MODES` continue to resolve.

## Test impact

Preserve all **scientific-behavior** tests unchanged:
`test_do_plot_applies_separate_panel_x_limits`,
`test_style_ax_applies_tick_label_padding`,
`test_canvas_size_update_skips_unchanged_dimensions`,
`test_iv_curve_mode_has_dedicated_dataset_ui`,
`test_iv_dataset_widget_uses_named_colored_single_sweep_slots`,
`test_figure_size_changes_are_applied_from_toolbar_update`,
`test_trace_color_fallbacks_are_black`,
`test_unused_pandas_dependency_is_not_loaded_at_startup`,
`test_missing_dependency_error_mentions_requirements_file`,
`test_plotting_shows_wait_cursor_and_flushes_ui_events`.

Update these **UI-structure** assertions to match the redesign (intent
preserved, target retargeted):

- `test_plot_canvas_uses_soft_canvas_card` → assert flat canvas frame (no shadow).
- `test_main_window_attaches_bottom_dock_groups` → assert the Plot Style
  `QDockWidget` receives the four style groups.
- `test_selected_tabs_use_full_accent_fill` → assert accent fill on the toolbar
  mode buttons / `QTabBar` selection.
- `test_inner_tab_panes_do_not_add_extra_framing_lines` and `build_style`
  source-greps in the UI-layout test → read `build_style` from `spectra_theme`.

## Out of scope

- Any change to plotting math, data parsing, IV/XRD/PL computations, export
  pipeline, or figure-size calculations.
- New analytical features. The Layers and Log docks only reflect existing state.
- Full modularization of `spectra_app.py` beyond the theme extraction.
