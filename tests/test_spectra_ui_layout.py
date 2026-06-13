import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import spectra_app


_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    _APP.setStyleSheet(spectra_app.build_style(spectra_app.MODES[0]["accent"]))
    return _APP


class SpectraUILayoutTest(unittest.TestCase):
    def test_control_panel_is_wide_enough_for_dense_iv_controls(self):
        qapp()
        panel = spectra_app.ControlPanel()
        panel.set_mode("iv")
        panel.show()
        QApplication.processEvents()

        self.assertGreaterEqual(panel.width(), 360)

    def test_inner_tab_panes_do_not_add_extra_framing_lines(self):
        style = spectra_app.build_style(spectra_app.MODES[0]["accent"])
        pane_block = style.split("QTabWidget::pane {", 1)[1].split("}", 1)[0]

        self.assertIn("border: none;", pane_block)

    def test_sidebar_content_does_not_overflow_viewport_in_pl_mode(self):
        qapp()
        panel = spectra_app.ControlPanel()
        panel.set_mode("pl")
        panel.show()
        QApplication.processEvents()

        self.assertLessEqual(panel.widget().width(), panel.viewport().width())


if __name__ == "__main__":
    unittest.main()
