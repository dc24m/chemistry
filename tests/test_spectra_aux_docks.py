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
