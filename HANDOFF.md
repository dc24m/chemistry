# SPECTRAplot experimental handoff

Updated: 2026-09-10

## Where to work

- Worktree: `C:\Users\arnold\Desktop\portfolio\.worktrees\spectraplot-experimental`
- Branch: `experimental/spectraplot-workspace`
- Base commit: `2c016e8`
- The work is intentionally uncommitted. Do not reset or overwrite the dirty tree.

## What is implemented

- Consolidated the old multi-dock controls into one resizable `Workspace` dock.
- Added `Data`, `Layout`, and `Style` task tabs with collapsible sections.
- Replaced the wide mode-button row with a compact mode selector.
- Simplified the application chrome and theme while preserving the monochrome instrument design.
- Added versioned editable figure documents with:
  - atomic JSON writes;
  - relative and absolute source paths;
  - SHA-256 source fingerprints;
  - changed/missing source reporting;
  - NumPy-safe serialization;
  - validation before workspace mutation.
- Added document Save/Open actions and header buttons.
- Editable documents restore controls, data sources, figure-editor text/legend overrides, and open in a new figure tab.
- Added dirty-state tracking and Save/Discard/Cancel protection when closing a figure tab.
- Added a persistent preset library plus legacy preset import.
- Presets preserve hidden measurement data and analysis choices; they apply layout/style only.
- Figure-editor overrides now survive replots and source reordering using stable source identities.
- Figure-editor drag, undo, redo, and legend movement mark the document dirty.
- Forced Matplotlib QtAgg to use PyQt6 to prevent mixed PySide6/PyQt6 widgets during tests.
- Restored the no-op guard when figure pixel dimensions are unchanged.

## Files added

- `spectra_documents.py` — document validation, serialization, source manifests, atomic I/O.
- `spectra_session.py` — preset filtering, persistence, and legacy import.
- `spectra_workspace.py` — task-tab and collapsible-section layout helpers.
- `tests/test_editor_documents.py`
- `tests/test_figure_documents.py`
- `tests/test_session_workflow.py`
- `tests/test_spectra_workspace.py`

## Files materially changed

- `spectra_app.py`
- `spectra_theme.py`
- Existing chrome/layout/static tests were updated because the old multi-dock and mode-button expectations directly contradicted the new single-workspace design.

## Verification completed

Run from the worktree root:

```powershell
python -m pytest -q --tb=short
```

Latest result:

```text
151 passed, 14 subtests passed in 177.35s (0:02:57)
```

Also completed successfully:

```powershell
python -m py_compile spectra_app.py spectra_theme.py spectra_documents.py spectra_session.py spectra_workspace.py
git diff --check
```

An offscreen QA capture was generated at:

`C:\Users\arnold\AppData\Local\Temp\spectraplot-experimental-qa.png`

The captured window was 1280x820 with a 320px workspace dock.

## Current Git state

Expected modified files:

- `spectra_app.py`
- `spectra_theme.py`
- `tests/test_spectra_aux_docks.py`
- `tests/test_spectra_static_regressions.py`
- `tests/test_spectra_ui_layout.py`
- `tests/test_spectra_window_chrome.py`

Expected untracked implementation/test files are listed above. `workspace-before-qa.png` is also untracked and predates this wrap-up; inspect it before deciding whether to keep or remove it.

## First steps for the next agent

1. Read this file, then run `git status --short --branch`.
2. Run the full pytest command above before editing.
3. Launch the app interactively and manually exercise Save/Open, preset save/apply, dirty-close prompts, and changed/missing source warnings.
4. Inspect `C:\Users\arnold\AppData\Local\Temp\spectraplot-experimental-qa.png` and compare it with `workspace-before-qa.png` if useful.
5. If manual QA is clean, update `SPECTRAplot.spec` only if PyInstaller does not discover the three new imported modules automatically.
6. Do not add abstractions or dependencies unless a failing acceptance check requires them.

## Known follow-up risk

- The automated workflow is covered, but the Presets header button currently saves a named preset; there is no full preset-management dialog. The programmatic `preset_library`, `capture_preset`, `apply_preset`, and `starter_presets` paths exist and are tested. Add UI only if explicitly required.
- Full tests take about three minutes because many tests construct real offscreen Qt/Matplotlib windows.
- Qt prints a local PySide6 font-directory warning on this machine even though the application and canvas are pinned to PyQt6; it did not cause test failures.

## Addendum — 2026-09-10, later session

- Fixed: figure geometry corrupted after a window move between mixed-DPI monitors while zoomed (`PlotCanvas._restore_figure_geometry`, `spectra_app.py`).
- Dark theme is now the launch default (`_APP_DARK = True`).
- Mode selector is a button row again (`ModeTabBar.buttons`), active one tinted with the mode accent. Accents also fill checked checkboxes, outline the selected list row, and rule the Workspace dock title. `DESIGN.md`/`README.md` updated to say so.
- Checkboxes have a visible outline and a filled checked state; expanded section headers no longer sit on the hover fill.
- `Files_traces`: bare `&` in section titles was a button mnemonic; escaped in `collapse_section`.
- Section titles are sentence case (`XRD options`, `Plot box`, …).
- XRD references have per-reference **Intensity ×** and **Offset +** (Edit reference dialog), applied before stacking, saved in figure documents; old documents backfill to 1.0 / 0.0.
- Suite: 156 passed. `workspace-before-qa.png` removed.
