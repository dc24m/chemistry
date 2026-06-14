import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QStatusBar
import spectra_app

_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    _APP.setStyleSheet(spectra_app.build_style(spectra_app.MODES[0]["accent"]))
    return _APP


class WindowChromeTest(unittest.TestCase):
    def test_window_has_native_menu_header_statusbar(self):
        qapp()
        win = spectra_app.MainWindow()
        win.show()
        QApplication.processEvents()
        menu_titles = [a.text().replace("&", "") for a in win.menuBar().actions()]
        for expected in ("File", "Edit", "View", "Plot", "Help"):
            self.assertIn(expected, menu_titles)
        self.assertIsInstance(win.header, spectra_app.TopHeader)
        self.assertTrue(win.header.isVisible())
        for key in ("pl", "absorbance", "xrd", "iv"):
            self.assertIn(key, win.header.mode_tabs.buttons)
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
        self.assertEqual(win.header.mode_tabs.current(), "xrd")
        self.assertTrue(win.header.mode_tabs.buttons["xrd"].isChecked())

    def test_header_tabs_switch_control_panel_mode(self):
        qapp()
        win = spectra_app.MainWindow()
        win.header.mode_tabs.buttons["absorbance"].click()
        self.assertEqual(win.controls.current_mode(), "absorbance")
        self.assertTrue(win.mode_actions["absorbance"].isChecked())

    def test_core_panels_are_dock_widgets(self):
        from PyQt6.QtWidgets import QDockWidget
        qapp()
        win = spectra_app.MainWindow()
        names = {d.objectName() for d in win.findChildren(QDockWidget)}
        self.assertIn("dock_build", names)
        self.assertIn("dock_style", names)
        self.assertIn("dock_log", names)
        self.assertNotIn("dock_layers", names)
        self.assertIs(win.canvas.parent(), win.canvas_stack)
        self.assertIs(win.canvas_stack.parent(), win.app_root)
        self.assertIsNotNone(win._default_state)

    def test_plot_style_dock_launches_wide_enough_for_controls(self):
        qapp()
        win = spectra_app.MainWindow()
        win.show()
        QApplication.processEvents()
        QApplication.processEvents()

        self.assertGreaterEqual(win.dock_style.width(), 360)

    def test_view_menu_lists_dock_toggles(self):
        qapp()
        win = spectra_app.MainWindow()
        view_actions = [a.text() for a in win.m_view.actions()]
        joined = " ".join(view_actions)
        self.assertIn("Build", joined)
        self.assertIn("Plot Style", joined)
        self.assertIn("Log", joined)
        self.assertNotIn("Layers", joined)


if __name__ == "__main__":
    unittest.main()
