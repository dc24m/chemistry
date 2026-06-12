import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "spectra_app.py"


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

    def test_iv_curve_mode_has_dedicated_dataset_ui(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("'label': 'IV curve'", source)
        self.assertIn("class IVDataSetWidget", source)
        self.assertIn("self.spin_iv_sets", source)
        self.assertIn("'iv_sets'", source)
        self.assertIn("self.g_iv.setVisible(is_iv)", source)
        self.assertIn("validate_iv_sets", source)


if __name__ == "__main__":
    unittest.main()
