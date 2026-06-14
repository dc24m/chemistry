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
    def test_log_dock_exists_without_unfinished_layers_pane(self):
        qapp()
        win = spectra_app.MainWindow()
        names = {d.objectName() for d in win.findChildren(QDockWidget)}
        self.assertIn("dock_log", names)
        self.assertNotIn("dock_layers", names)

    def test_log_appends_status_messages(self):
        qapp()
        win = spectra_app.MainWindow()
        win._status_message("Hello log")
        self.assertIn("Hello log", win.log_dock.text())

    def test_window_does_not_expose_layers_panel_api(self):
        qapp()
        win = spectra_app.MainWindow()
        self.assertFalse(hasattr(win, "layers_dock"))
        self.assertFalse(hasattr(spectra_app, "LayersPanel"))


if __name__ == "__main__":
    unittest.main()
