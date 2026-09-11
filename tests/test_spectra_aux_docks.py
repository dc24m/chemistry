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


class WorkspaceDockTest(unittest.TestCase):
    def test_single_workspace_dock_replaces_auxiliary_panes(self):
        qapp()
        win = spectra_app.MainWindow()
        names = {d.objectName() for d in win.findChildren(QDockWidget)}
        self.assertEqual(names, {"dock_build"})

    def test_status_messages_use_the_native_status_bar(self):
        qapp()
        win = spectra_app.MainWindow()
        win._status_message("Hello log")
        self.assertEqual(win.statusBar().currentMessage(), "Hello log")

    def test_window_does_not_expose_layers_panel_api(self):
        qapp()
        win = spectra_app.MainWindow()
        self.assertFalse(hasattr(win, "layers_dock"))
        self.assertFalse(hasattr(spectra_app, "LayersPanel"))


if __name__ == "__main__":
    unittest.main()
