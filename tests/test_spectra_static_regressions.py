import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "spectra_app.py"
REQUIREMENTS = ROOT / "requirements_spectra.txt"


def _module():
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def _function_source(name: str) -> str:
    tree = _module()
    text = SOURCE.read_text(encoding="utf-8")
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    raise AssertionError(f"Function {name!r} not found")


class SpectraStaticRegressionTest(unittest.TestCase):
    def test_do_plot_applies_separate_panel_x_limits(self):
        source = _function_source("do_plot")

        self.assertIn("separate_x_limits", source)
        self.assertIn("panel_x_limits", source)
        self.assertIn("limit_cfg", source)
        self.assertIn("auto_x", source)

    def test_style_ax_applies_tick_label_padding(self):
        source = _function_source("_style_ax")

        self.assertIn("x_tick_pad", source)
        self.assertIn("y_tick_pad", source)
        self.assertIn("pad=", source)

    def test_plot_canvas_uses_soft_canvas_card(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("setObjectName('canvasCard')", source)
        self.assertIn("add_shadow(self.card", source)

    def test_main_window_attaches_bottom_dock_groups(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("take_dock_groups()", source)
        self.assertIn("setObjectName('dockCard')", source)

    def test_trace_color_fallbacks_are_black(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("trace.get('color', '#333333')", source)
        self.assertIn("trace.get('color', '#000000')", source)
        self.assertNotIn("tr.get('color', '#333333')", source)
        self.assertIn("tr.get('color', '#000000')", source)

    def test_unused_pandas_dependency_is_not_loaded_at_startup(self):
        source = SOURCE.read_text(encoding="utf-8")
        requirements = REQUIREMENTS.read_text(encoding="utf-8")

        self.assertNotIn("import pandas", source)
        self.assertNotIn("pandas", requirements.lower())

    def test_missing_dependency_error_mentions_requirements_file(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("except ModuleNotFoundError as exc:", source)
        self.assertIn("requirements_spectra.txt", source)
        self.assertIn("sys.executable", source)

    def test_plotting_shows_wait_cursor_and_flushes_ui_events(self):
        source = SOURCE.read_text(encoding="utf-8")
        method = source.split("    def _do_plot(self, silent: bool = False):", 1)[1].split("\n\n# ── Entry point", 1)[0]

        self.assertIn("QApplication.setOverrideCursor", method)
        self.assertIn("QApplication.restoreOverrideCursor", method)
        self.assertIn("QApplication.processEvents", method)
        self.assertIn("finally:", method)

    def test_canvas_size_update_skips_unchanged_dimensions(self):
        source = SOURCE.read_text(encoding="utf-8")
        method = source.split("    def set_fig_size(self, w_in: float, h_in: float):", 1)[1].split(
            "    def applied_size_pixels", 1
        )[0]

        self.assertIn("if requested_px == self.applied_size_pixels():", method)
        self.assertIn("return", method)

    def test_iv_curve_mode_has_dedicated_dataset_ui(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("'label': 'IV curve'", source)
        self.assertIn("class IVDataSetWidget", source)
        self.assertIn("self.spin_iv_sets", source)
        self.assertIn("'iv_sets'", source)
        self.assertIn("self.g_iv.setVisible(is_iv)", source)
        self.assertIn("validate_iv_sets", source)

    def test_iv_dataset_widget_uses_named_colored_single_sweep_slots(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("self.edit_name", source)
        self.assertIn("self.color = ColorButton", source)
        self.assertIn("'neg_path'", source)
        self.assertIn("'pos_path'", source)
        self.assertIn("_clear_sweep", source)

    def test_figure_size_changes_are_applied_from_toolbar_update(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("self.btn_update_size", source)
        self.assertIn("self.btn_update_size.setText('Update')", source)
        self.assertNotIn("self.controls.spin_fw.valueChanged.connect(self._update_canvas_size)", source)
        self.assertNotIn("self.controls.spin_fh.valueChanged.connect(self._update_canvas_size)", source)

    def test_selected_tabs_use_full_accent_fill(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("QPushButton#headerTab:checked", source)
        self.assertIn("QTabBar::tab:selected", source)
        header_block = source.split("QPushButton#headerTab:checked {{", 1)[1].split("}}", 1)[0]
        tab_block = source.split("QTabBar::tab:selected {{", 1)[1].split("}}", 1)[0]
        self.assertIn("background: {ACCENT};", header_block)
        self.assertIn("background: {ACCENT};", tab_block)
        self.assertNotIn("border: 2px solid {ACCENT};", header_block)
        self.assertNotIn("border-top: 2px solid {ACCENT};", tab_block)


if __name__ == "__main__":
    unittest.main()
