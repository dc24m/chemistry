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

    def test_figure_tabs_use_centered_light_selected_state(self):
        style = spectra_app.build_style(spectra_app.MODES[0]["accent"])

        tab_block = style.split("QPushButton#figureTab {", 1)[1].split("}", 1)[0]
        selected_block = style.split("QPushButton#figureTab:checked {", 1)[1].split("}", 1)[0]

        self.assertIn("text-align: center;", tab_block)
        self.assertIn("background: #E8E8E8;", selected_block)
        self.assertIn("color: #171717;", selected_block)
        self.assertNotIn("background: {PRIMARY};", selected_block)

    def test_color_picker_buttons_match_compact_input_height(self):
        qapp()
        button = spectra_app.ColorButton("#000000")
        button_style = button.styleSheet()

        self.assertIn("min-height:26px", button_style)
        self.assertIn("max-height:26px", button_style)
        self.assertIn("border-radius:6px", button_style)
        self.assertNotIn("min-height:32px", button_style)


if __name__ == "__main__":
    unittest.main()
