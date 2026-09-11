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
    def test_workspace_dock_is_wide_enough_for_dense_iv_controls(self):
        qapp()
        win = spectra_app.MainWindow()
        win.controls.set_mode("iv")
        win.show()
        QApplication.processEvents()

        self.assertGreaterEqual(win.dock_build.width(), 320)

    def test_inner_tab_panes_do_not_add_extra_framing_lines(self):
        style = spectra_app.build_style(spectra_app.MODES[0]["accent"])
        pane_block = style.split("QTabWidget::pane {", 1)[1].split("}", 1)[0]

        self.assertIn("border: none;", pane_block)

    def test_sidebar_pages_do_not_overflow_their_scroll_viewports(self):
        qapp()
        panel = spectra_app.ControlPanel()
        panel.set_mode("pl")
        panel.show()
        QApplication.processEvents()

        for index, (name, page) in enumerate(panel.workspace_pages.items()):
            panel.workspace_tabs.setCurrentIndex(index)
            QApplication.processEvents()
            viewport = panel.workspace_scrolls[name].viewport()
            self.assertLessEqual(page.width(), viewport.width())

    def test_figure_tabs_use_centered_light_selected_state(self):
        style = spectra_app.build_style(spectra_app.MODES[0]["accent"])

        tab_block = style.split("QPushButton#figureTab {", 1)[1].split("}", 1)[0]
        selected_block = style.split("QPushButton#figureTab:checked {", 1)[1].split("}", 1)[0]

        self.assertIn("text-align: center;", tab_block)
        self.assertIn("background: #E8E8E8;", selected_block)
        self.assertIn("color: #202020;", selected_block)
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


class PlotCanvasDpiChangeTest(unittest.TestCase):
    def test_figure_inches_survive_monitor_dpi_change_while_zoomed(self):
        qapp()
        canvas = spectra_app.PlotCanvas()
        canvas.show()
        canvas.set_fig_size(8.0, 5.0)
        canvas.set_view_scale(1.25)

        # Moving the window from a 100% monitor to a 175% one makes Matplotlib
        # rewrite fig.dpi from its construction-time value and re-derive the
        # inch size from the pixel size (the mixed-DPI desktop bug).
        for ratio in (1.75, 1.0):
            canvas.canvas.devicePixelRatioF = lambda r=ratio: r
            canvas.canvas._update_pixel_ratio()
            w, h = canvas.fig.get_size_inches()
            self.assertAlmostEqual(w, 8.0, places=6)
            self.assertAlmostEqual(h, 5.0, places=6)
            self.assertAlmostEqual(
                canvas.fig.get_dpi(), canvas.DISPLAY_DPI * 1.25 * ratio, places=6
            )
