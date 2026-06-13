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
        menu_titles = [a.text().replace("&", "") for a in win.menuBar().actions()]
        for expected in ("File", "Edit", "View", "Plot", "Help"):
            self.assertIn(expected, menu_titles)
        self.assertIsInstance(win.findChild(QToolBar), QToolBar)
        self.assertIsInstance(win.statusBar(), QStatusBar)

    def test_toolbar_plot_action_triggers_plot(self):
        qapp()
        win = spectra_app.MainWindow()
        from unittest.mock import patch
        with patch("spectra_app.QMessageBox.information"), patch("spectra_app.QMessageBox.critical"):
            win.act_plot.trigger()
        self.assertTrue(win._plot_called_for_test)

    def test_mode_actions_switch_control_panel_mode(self):
        qapp()
        win = spectra_app.MainWindow()
        win.mode_actions["xrd"].trigger()
        self.assertEqual(win.controls.current_mode(), "xrd")


if __name__ == "__main__":
    unittest.main()
