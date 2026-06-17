# -*- mode: python ; coding: utf-8 -*-
import os, sys
from PyInstaller.utils.hooks import collect_data_files

# ── data files ───────────────────────────────────────────────────────────────
datas = [
    ('qt.conf', '.'),          # tells Qt where Data/Plugins live so it skips CFBundleCopyBundleURL (macOS 26 PAC crash fix)
    ('assets/logo.png', 'assets'),
    ('assets/loading.png', 'assets'),
    *([('GoogleSans-VariableFont_GRAD,opsz,wght.ttf', '.')] if os.path.isfile('GoogleSans-VariableFont_GRAD,opsz,wght.ttf') else []),
    *([('GoogleSans-Italic-VariableFont_GRAD,opsz,wght.ttf', '.')] if os.path.isfile('GoogleSans-Italic-VariableFont_GRAD,opsz,wght.ttf') else []),
    *collect_data_files('matplotlib'),   # mpl-data: fonts, matplotlibrc, etc.
]

# ── only the hidden imports that PyInstaller genuinely misses ────────────────
hiddenimports = [
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_agg',
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
        # never used
        'tkinter', '_tkinter',
        'IPython', 'jupyter', 'notebook',
        'scipy', 'pandas',
        # test/dev modules
        'matplotlib.tests', 'matplotlib.testing',
        'numpy.testing', 'numpy.tests', 'numpy.f2py',
        # unused Qt modules (big savings)
        'PyQt6.QtNetwork', 'PyQt6.QtBluetooth', 'PyQt6.QtNfc',
        'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender', 'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic', 'PyQt6.Qt3DAnimation', 'PyQt6.Qt3DExtras',
        'PyQt6.QtCharts', 'PyQt6.QtDataVisualization',
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtLocation', 'PyQt6.QtPositioning',
        'PyQt6.QtQuick', 'PyQt6.QtQuickWidgets', 'PyQt6.QtQuickControls2',
        'PyQt6.QtSensors', 'PyQt6.QtSql', 'PyQt6.QtTest',
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineQuick',
        'PyQt6.QtWebSockets', 'PyQt6.QtXml',
        # NOTE: QtDBus must NOT be excluded — QtGui links against it on macOS
        'PyQt6.QtDesigner', 'PyQt6.QtHelp',
        'PyQt6.QtRemoteObjects', 'PyQt6.QtSerialPort', 'PyQt6.QtStateMachine',
    ],
    noarchive=False,
    optimize=1,
)

# ── strip unused Qt binaries that slipped through ────────────────────────────
_qt_drop = {
    'qtwebengine', 'qtnetwork', 'qt3d', 'qtcharts', 'qtdatavisualization',
    'qtmultimedia', 'qtlocation', 'qtpositioning', 'qtquick', 'qtsensors',
    'qtsql', 'qttest', 'qtwebsockets', 'qtxml', 'qtdesigner',
    'qthelp', 'qtbluetooth', 'qtnfc', 'qtremoteobjects', 'qtserialport',
    'qtstatemachine', 'permissionplugin',
}
a.binaries = [b for b in a.binaries
              if not any(k in b[0].lower() for k in _qt_drop)]

pyz = PYZ(a.pure)

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
    upx_exclude=[],
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

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SPECTRAplot.app',
        icon=_icon,
        bundle_identifier='com.spectraplot.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'NSPrincipalClass': 'NSApplication',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'SPECTRAplot',
        },
    )
