# -*- mode: python ; coding: utf-8 -*-
#
# SPECTRAplot PyInstaller spec
#
# Build (macOS):   pyinstaller SPECTRAplot.spec
# Build (Windows): pyinstaller SPECTRAplot.spec   (run this on a Windows machine)
#
# Output lands in dist/
#   macOS  → dist/SPECTRAplot.app
#   Windows → dist/SPECTRAplot/SPECTRAplot.exe

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── data files to bundle ─────────────────────────────────────────────────────
datas = [
    # logo  (src, dest-folder-inside-bundle)
    ('assets/logo.png',                                            'assets'),

    # Google Sans fonts (project root → bundle root so resource_path(fname) works)
    ('GoogleSans-VariableFont_GRAD,opsz,wght.ttf',                '.'),
    ('GoogleSans-Italic-VariableFont_GRAD,opsz,wght.ttf',         '.'),

    # matplotlib needs its own data (mpl-data: fonts, matplotlibrc, etc.)
    *collect_data_files('matplotlib'),

    # numpy data files
    *collect_data_files('numpy'),
]

# ── hidden imports matplotlib/PyQt6 need ────────────────────────────────────
hiddenimports = [
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_agg',
    *collect_submodules('matplotlib'),
    *collect_submodules('numpy'),
    'PyQt6.QtPrintSupport',
]

# ── analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    ['spectra_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',   # not used, saves ~10 MB
        'IPython', 'jupyter',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

import sys, os
_icon = ('assets/icon.icns' if sys.platform == 'darwin'
         else 'assets/icon.ico' if os.path.isfile('assets/icon.ico')
         else None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SPECTRAplot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SPECTRAplot',
)

# ── macOS: wrap into a .app bundle ───────────────────────────────────────────
import sys
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SPECTRAplot.app',
        icon='assets/icon.icns',
        bundle_identifier='com.spectraplot.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'NSPrincipalClass': 'NSApplication',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'SPECTRAplot',
        },
    )
