import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from matplotlib.figure import Figure
from PyQt6.QtWidgets import QApplication

import spectra_app


_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    return _APP


def base_settings(**overrides):
    settings = {
        "plot_type": "pl",
        "n_panels": 2,
        "panel_data": [
            {"traces": [], "gradient": ("#000000", "#000000"), "use_gradient": True},
            {"traces": [], "gradient": ("#000000", "#000000"), "use_gradient": True},
        ],
        "auto_x": False,
        "x_min": 1.0,
        "x_max": 2.0,
        "separate_x_limits": False,
        "panel_x_limits": [
            {"auto_x": False, "x_min": 10.0, "x_max": 20.0},
            {"auto_x": False, "x_min": 30.0, "x_max": 40.0},
        ],
        "auto_y": True,
        "y_min": 0.0,
        "y_max": 1.0,
        "separate_y_limits": False,
        "panel_y_limits": [
            {"auto_y": False, "y_min": -1.0, "y_max": 5.0},
            {"auto_y": False, "y_min": 100.0, "y_max": 200.0},
        ],
        "share_y": False,
        "show_main_title": False,
        "main_title": "",
        "show_subtitle": False,
        "subtitle": "",
        "show_panel_titles": False,
        "panel_titles": ["A", "B"],
        "linewidth": 1.5,
        "fontsize": 12,
        "show_legend": False,
        "legend_loc": "upper right",
        "xrd_d_spacing": False,
        "xrd_lambda": 1.5406,
        "xrd_ref_step": 1.0,
        "xrd_exp_step": 1.0,
        "xrd_ref_paths": [],
        "xrd_margin_labels": False,
        "xrd_margin_label_gap": 0.25,
        "pl_baseline_correct": True,
        "font_family": "DejaVu Sans",
        "font_custom": "",
        "tick_dir": "in",
        "show_xticks": True,
        "show_yticks": True,
        "show_top_ticks": True,
        "show_right_ticks": True,
        "tick_length": 4.0,
        "tick_width": 0.8,
        "minor_ticks": False,
        "x_tick_pad": 6,
        "y_tick_pad": 6,
        "y_notation": "Normal",
        "force_sci": False,
        "sci_exp": 3,
        "box_linewidth": 1.0,
        "box_color": "#000000",
        "manual_layout": False,
    }
    settings.update(overrides)
    return settings


class SpectraPlottingBehaviorTest(unittest.TestCase):
    def test_global_x_limits_apply_when_separate_limits_are_off(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(x_min=5.0, x_max=15.0))

        self.assertEqual([ax.get_xlim() for ax in fig.axes], [(5.0, 15.0), (5.0, 15.0)])

    def test_per_panel_x_limits_apply_independently(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(separate_x_limits=True))

        self.assertEqual([ax.get_xlim() for ax in fig.axes], [(10.0, 20.0), (30.0, 40.0)])

    def test_xrd_d_spacing_reverses_per_panel_x_limits(self):
        fig = Figure()

        spectra_app.do_plot(
            fig,
            base_settings(plot_type="xrd", xrd_d_spacing=True, separate_x_limits=True),
        )

        self.assertEqual([ax.get_xlim() for ax in fig.axes], [(20.0, 10.0), (40.0, 30.0)])

    def test_tick_label_padding_is_applied(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(x_tick_pad=17, y_tick_pad=19))

        self.assertEqual(fig.axes[0].xaxis.majorTicks[0].get_pad(), 17)
        self.assertEqual(fig.axes[0].yaxis.majorTicks[0].get_pad(), 19)

    def test_trace_visual_defaults_to_black_without_gradient(self):
        color, _linewidth, _linestyle = spectra_app._trace_visual(
            {"linestyle": "solid"}, None, 0, False, 1.5
        )

        self.assertEqual(color, "#000000")

    def test_pl_baseline_correction_subtracts_first_point_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl_trace.csv"
            path.write_text("400,4\n450,7\n500,5\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                n_panels=1,
                panel_data=[{
                    "traces": [{
                        "path": str(path),
                        "display_name": "PL trace",
                        "color": "#000000",
                        "visible": True,
                        "use_auto_gradient_color": False,
                    }],
                    "gradient": ("#000000", "#000000"),
                    "use_gradient": False,
                }],
                pl_baseline_correct=True,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(), [0.0, 3.0, 1.0])

    def test_pl_baseline_correction_subtracts_lowest_point_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl_trace.csv"
            path.write_text("400,5\n450,7\n500,4\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                n_panels=1,
                panel_data=[{
                    "traces": [{
                        "path": str(path),
                        "display_name": "PL trace",
                        "color": "#000000",
                        "visible": True,
                        "use_auto_gradient_color": False,
                    }],
                    "gradient": ("#000000", "#000000"),
                    "use_gradient": False,
                }],
                pl_baseline_correct=True,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(), [1.0, 3.0, 0.0])

    def test_pl_baseline_correction_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl_trace.csv"
            path.write_text("400,5\n450,7\n500,4\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                n_panels=1,
                panel_data=[{
                    "traces": [{
                        "path": str(path),
                        "display_name": "PL trace",
                        "color": "#000000",
                        "visible": True,
                        "use_auto_gradient_color": False,
                    }],
                    "gradient": ("#000000", "#000000"),
                    "use_gradient": False,
                }],
                pl_baseline_correct=False,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(), [5.0, 7.0, 4.0])

    # ── Per-panel Y limits ───────────────────────────────────────────────────

    def _pl_panels(self, path, n=2):
        panel = {
            "traces": [{
                "path": str(path),
                "display_name": "trace",
                "color": "#000000",
                "visible": True,
                "use_auto_gradient_color": False,
            }],
            "gradient": ("#000000", "#000000"),
            "use_gradient": False,
        }
        return [dict(panel) for _ in range(n)]

    def test_panel_y_window_is_none_for_both_auto_y_paths(self):
        self.assertIsNone(spectra_app.panel_y_window(
            base_settings(auto_y=True), 0))
        self.assertIsNone(spectra_app.panel_y_window(
            base_settings(
                separate_y_limits=True,
                panel_y_limits=[{"auto_y": True, "y_min": 1.0, "y_max": 2.0}]),
            0))

    def test_panel_y_window_reports_configured_range_per_panel(self):
        s = base_settings(separate_y_limits=True)
        self.assertEqual(spectra_app.panel_y_window(s, 0), (-1.0, 5.0))
        self.assertEqual(spectra_app.panel_y_window(s, 1), (100.0, 200.0))
        self.assertEqual(
            spectra_app.panel_y_window(base_settings(auto_y=False), 0), (0.0, 1.0))

    def test_per_panel_y_limits_apply_independently(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(separate_y_limits=True))

        self.assertEqual([ax.get_ylim() for ax in fig.axes],
                         [(-1.0, 5.0), (100.0, 200.0)])

    def test_a_panel_marked_auto_keeps_its_own_fit_while_its_neighbour_is_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl.csv"
            path.write_text("400,0\n500,4\n600,2\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                panel_data=self._pl_panels(path),
                pl_baseline_correct=False,
                separate_y_limits=True,
                panel_y_limits=[
                    {"auto_y": False, "y_min": -10.0, "y_max": 10.0},
                    {"auto_y": True, "y_min": 0.0, "y_max": 1.0},
                ],
            ))

            pinned, auto = (ax.get_ylim() for ax in fig.axes)
            self.assertEqual(pinned, (-10.0, 10.0))
            self.assertNotEqual(auto, (-10.0, 10.0))
            # Auto-fitted around the 0–4 data rather than the pinned range.
            self.assertLess(auto[0], 1.0)
            self.assertLess(auto[1], 6.0)

    def test_global_y_limits_still_apply_to_every_panel(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(
            auto_y=False, y_min=2.0, y_max=8.0))

        self.assertEqual([ax.get_ylim() for ax in fig.axes], [(2.0, 8.0), (2.0, 8.0)])

    def test_share_y_still_unifies_auto_fitted_panels(self):
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "small.csv"
            big = Path(tmp) / "big.csv"
            small.write_text("400,0\n500,1\n", encoding="utf-8")
            big.write_text("400,0\n500,50\n", encoding="utf-8")
            fig = Figure()

            panels = self._pl_panels(small)
            panels[1] = dict(panels[1])
            panels[1]["traces"] = [dict(panels[1]["traces"][0], path=str(big))]
            spectra_app.do_plot(fig, base_settings(
                panel_data=panels, share_y=True, auto_y=True))

            a, b = (ax.get_ylim() for ax in fig.axes)
            self.assertEqual(a, b)

    def test_share_y_is_skipped_once_a_panel_pins_its_own_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl.csv"
            path.write_text("400,0\n500,4\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                panel_data=self._pl_panels(path),
                share_y=True,
                separate_y_limits=True,
                panel_y_limits=[
                    {"auto_y": False, "y_min": -10.0, "y_max": 10.0},
                    {"auto_y": True, "y_min": 0.0, "y_max": 1.0},
                ],
            ))

            pinned, auto = (ax.get_ylim() for ax in fig.axes)
            self.assertEqual(pinned, (-10.0, 10.0))
            self.assertNotEqual(auto, pinned)

    # ── Panel orientation ────────────────────────────────────────────────────

    def test_panel_rects_splits_a_box_left_to_right_by_default(self):
        rects = spectra_app.panel_rects((0.1, 0.2, 0.8, 0.6), 2, 0.1, vertical=False)

        self.assertEqual(rects, [(0.1, 0.2, 0.35000000000000003, 0.6),
                                 (0.55, 0.2, 0.35000000000000003, 0.6)])

    def test_panel_rects_stacks_panel_zero_on_top_when_vertical(self):
        rects = spectra_app.panel_rects((0.1, 0.2, 0.8, 0.6), 3, 0.06, vertical=True)

        # Same column, equal heights, panel 0 highest, gaps in between.
        self.assertEqual([r[0] for r in rects], [0.1, 0.1, 0.1])
        self.assertEqual([r[2] for r in rects], [0.8, 0.8, 0.8])
        heights = [r[3] for r in rects]
        self.assertTrue(all(abs(h - heights[0]) < 1e-12 for h in heights))
        tops = [r[1] for r in rects]
        self.assertTrue(tops[0] > tops[1] > tops[2])
        self.assertAlmostEqual(tops[2], 0.2)
        self.assertAlmostEqual(tops[0] + heights[0], 0.8)
        self.assertAlmostEqual(tops[1] + heights[1] + 0.06, tops[0])

    def test_panel_rects_gives_a_single_panel_the_whole_box(self):
        box = (0.1, 0.2, 0.8, 0.6)
        self.assertEqual(spectra_app.panel_rects(box, 1, 0.05, vertical=True), [box])
        self.assertEqual(spectra_app.panel_rects(box, 1, 0.05, vertical=False), [box])

    def test_panels_stay_side_by_side_when_no_orientation_is_set(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings())

        a, b = (ax.get_position() for ax in fig.axes)
        self.assertAlmostEqual(a.y0, b.y0)
        self.assertLess(a.x0, b.x0)

    def test_vertical_orientation_stacks_panels_with_panel_zero_on_top(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(panel_orientation="vertical"))

        a, b = (ax.get_position() for ax in fig.axes)
        self.assertAlmostEqual(a.x0, b.x0)
        self.assertAlmostEqual(a.width, b.width)
        self.assertGreater(a.y0, b.y0)

    def test_vertical_orientation_labels_x_on_the_bottom_panel_only(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(panel_orientation="vertical"))

        top, bottom = fig.axes
        self.assertEqual(top.get_xlabel(), "")
        self.assertEqual(bottom.get_xlabel(), "Wavelength λ (nm)")
        self.assertTrue(all(not t.get_visible() for t in top.get_xticklabels()))
        self.assertTrue(any(t.get_visible() for t in bottom.get_xticklabels()))

    def test_vertical_orientation_labels_y_on_every_panel(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(panel_orientation="vertical"))

        for ax in fig.axes:
            self.assertEqual(ax.get_ylabel(), "Baseline-corrected PL")
            self.assertTrue(any(t.get_visible() for t in ax.get_yticklabels()))

    def test_horizontal_orientation_keeps_x_on_all_and_y_on_the_left(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings())

        left, right = fig.axes
        self.assertEqual(left.get_xlabel(), "Wavelength λ (nm)")
        self.assertEqual(right.get_xlabel(), "Wavelength λ (nm)")
        self.assertEqual(left.get_ylabel(), "Baseline-corrected PL")
        self.assertEqual(right.get_ylabel(), "")

    def test_vertical_orientation_keeps_x_labels_when_panels_have_own_limits(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(
            panel_orientation="vertical", separate_x_limits=True))

        for ax in fig.axes:
            self.assertEqual(ax.get_xlabel(), "Wavelength λ (nm)")
            self.assertTrue(any(t.get_visible() for t in ax.get_xticklabels()))

    def test_manual_layout_stacks_panels_inside_the_plot_box(self):
        fig = Figure()

        spectra_app.do_plot(fig, base_settings(
            panel_orientation="vertical", manual_layout=True,
            pa_left=0.1, pa_bottom=0.2, pa_width=0.8, pa_height=0.6,
            panel_gap=0.04,
        ))

        top, bottom = (ax.get_position() for ax in fig.axes)
        self.assertAlmostEqual(top.x0, 0.1)
        self.assertAlmostEqual(top.width, 0.8)
        self.assertAlmostEqual(bottom.y0, 0.2)
        self.assertAlmostEqual(top.y1, 0.8)
        self.assertAlmostEqual(bottom.y1 + 0.04, top.y0)

    def test_iv_keeps_its_axis_labels_regardless_of_orientation(self):
        with tempfile.TemporaryDirectory() as tmp:
            neg = Path(tmp) / "device_under25.csv"
            pos = Path(tmp) / "device_under5.csv"
            neg.write_text("0,0,-20,1e-6\n0,0,0,3e-6\n", encoding="utf-8")
            pos.write_text("0,0,0,4e-6\n0,0,20,6e-6\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="iv", n_panels=3, panel_orientation="vertical",
                iv_sets=[{
                    "name": "Device A",
                    "color": "#0072B2",
                    "neg_path": str(neg),
                    "pos_path": str(pos),
                }],
            ))

            ax = fig.axes[0]
            self.assertEqual(ax.get_xlabel(), "Voltage (V)")
            self.assertEqual(ax.get_ylabel(), "Current (µA)")

    # ── Window-relative normalization ────────────────────────────────────────

    def _one_panel(self, path):
        return [{
            "traces": [{
                "path": str(path),
                "display_name": "trace",
                "color": "#000000",
                "visible": True,
                "use_auto_gradient_color": False,
            }],
            "gradient": ("#000000", "#000000"),
            "use_gradient": False,
        }]

    def test_panel_x_window_is_none_for_both_auto_x_paths(self):
        self.assertIsNone(spectra_app.panel_x_window(
            base_settings(auto_x=True), 0))
        self.assertIsNone(spectra_app.panel_x_window(
            base_settings(
                separate_x_limits=True,
                panel_x_limits=[{"auto_x": True, "x_min": 1.0, "x_max": 2.0}]),
            0))

    def test_panel_x_window_reports_configured_range_per_panel(self):
        s = base_settings(separate_x_limits=True)
        self.assertEqual(spectra_app.panel_x_window(s, 0), (10.0, 20.0))
        self.assertEqual(spectra_app.panel_x_window(s, 1), (30.0, 40.0))
        self.assertEqual(spectra_app.panel_x_window(base_settings(), 0), (1.0, 2.0))

    def test_absorbance_normalize_scales_to_the_peak_inside_the_x_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "abs.csv"
            # 900 nm carries a noise spike well outside the plotted window.
            path.write_text("400,1\n500,2\n600,1\n900,50\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="absorbance", n_panels=1,
                panel_data=self._one_panel(path),
                auto_x=False, x_min=400.0, x_max=600.0,
                abs_normalize=True,
            ))

            y = fig.axes[0].lines[0].get_ydata().tolist()
            self.assertEqual(y, [0.5, 1.0, 0.5, 25.0])
            self.assertEqual(fig.axes[0].get_ylabel(), "Normalized absorbance (a.u.)")

    def test_absorbance_normalize_off_leaves_data_and_label_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "abs.csv"
            path.write_text("400,1\n500,2\n600,1\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="absorbance", n_panels=1,
                panel_data=self._one_panel(path),
                auto_x=False, x_min=400.0, x_max=600.0,
                abs_normalize=False,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(), [1.0, 2.0, 1.0])
            self.assertEqual(fig.axes[0].get_ylabel(), "Absorbance (a.u.)")

    def test_absorbance_normalize_uses_each_panels_own_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "abs.csv"
            path.write_text("10,1\n20,4\n30,2\n40,8\n", encoding="utf-8")
            fig = Figure()

            panel = self._one_panel(path)
            spectra_app.do_plot(fig, base_settings(
                plot_type="absorbance", n_panels=2,
                panel_data=panel + [dict(panel[0])],
                separate_x_limits=True,
                abs_normalize=True,
            ))

            # Panel 1 sees 10–20 (max 4), panel 2 sees 30–40 (max 8).
            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(),
                             [0.25, 1.0, 0.5, 2.0])
            self.assertEqual(fig.axes[1].lines[0].get_ydata().tolist(),
                             [0.125, 0.5, 0.25, 1.0])

    def test_absorbance_normalize_falls_back_to_full_range_for_an_empty_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "abs.csv"
            path.write_text("400,1\n500,2\n600,1\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="absorbance", n_panels=1,
                panel_data=self._one_panel(path),
                auto_x=False, x_min=1000.0, x_max=1200.0,
                abs_normalize=True,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(), [0.5, 1.0, 0.5])

    def test_pl_normalize_scales_to_the_peak_inside_the_x_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl.csv"
            path.write_text("400,0\n500,4\n600,2\n900,40\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                n_panels=1, panel_data=self._one_panel(path),
                auto_x=False, x_min=400.0, x_max=600.0,
                pl_baseline_correct=False, pl_normalize=True,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(),
                             [0.0, 1.0, 0.5, 10.0])

    def test_pl_normalize_under_auto_x_still_uses_the_whole_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pl.csv"
            path.write_text("400,0\n500,4\n600,2\n900,40\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                n_panels=1, panel_data=self._one_panel(path),
                auto_x=True,
                pl_baseline_correct=False, pl_normalize=True,
            ))

            self.assertEqual(fig.axes[0].lines[0].get_ydata().tolist(),
                             [0.0, 0.1, 0.05, 1.0])

    def test_xrd_margin_labels_match_rightmost_trace_names_and_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            red_path = Path(tmp) / "red.xy"
            blue_path = Path(tmp) / "blue.xy"
            red_path.write_text("5 1\n10 2\n20 3\n", encoding="utf-8")
            blue_path.write_text("5 2\n10 3\n20 4\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="xrd",
                n_panels=1,
                panel_data=[{
                    "traces": [
                        {
                            "path": str(red_path),
                            "display_name": "Red phase",
                            "color": "#FF0000",
                            "visible": True,
                            "use_auto_gradient_color": False,
                        },
                        {
                            "path": str(blue_path),
                            "display_name": "Blue phase",
                            "color": "#0000FF",
                            "visible": True,
                            "use_auto_gradient_color": False,
                        },
                    ],
                    "gradient": ("#000000", "#000000"),
                    "use_gradient": False,
                }],
                xrd_margin_labels=True,
                show_legend=False,
            ))

            labels = {
                text.get_text(): text
                for text in fig.texts
                if text.get_gid() == "xrd_margin_label"
            }
            self.assertEqual(set(labels), {"Red phase", "Blue phase"})
            self.assertEqual(labels["Red phase"].get_color().lower(), "#ff0000")
            self.assertEqual(labels["Blue phase"].get_color().lower(), "#0000ff")
            self.assertLess(fig.axes[0].get_position().x1, 0.96)

    def test_iv_files_sort_by_under_value_descending_with_missing_last(self):
        files = [
            "sample_under5.csv",
            "sample.csv",
            "sample_under25.csv",
            "sample_under12.csv",
        ]

        self.assertEqual(
            spectra_app.sort_iv_files_by_under_value(files),
            ["sample_under25.csv", "sample_under12.csv", "sample_under5.csv", "sample.csv"],
        )

    def test_iv_current_unit_selection_thresholds(self):
        cases = [
            (0.0, (1.0, "A")),
            (5e-12, (1e12, "pA")),
            (5e-9, (1e9, "nA")),
            (5e-6, (1e6, "µA")),
            (5e-3, (1e3, "mA")),
            (5.0, (1.0, "A")),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(spectra_app.choose_iv_current_unit(value), expected)

    def test_iv_loader_reads_voltage_and_current_from_columns_three_and_four(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keithley.csv"
            path.write_text(
                "a,b,voltage,current\n"
                "0,0,-20,1e-9\n"
                "0,0,NaN,2e-9\n"
                "0,0,-10,Inf\n"
                "0,0,0,3e-9\n",
                encoding="utf-8",
            )

            voltage, current = spectra_app.load_iv_csv(str(path))

            self.assertEqual(voltage.tolist(), [-20.0, 0.0])
            self.assertEqual(current.tolist(), [1e-9, 3e-9])

    def test_load_file_reuses_cached_data_when_file_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            path.write_text("400,1\n500,2\n", encoding="utf-8")
            spectra_app.clear_file_cache()

            with patch("builtins.open", wraps=open) as mocked_open:
                first_x, first_y = spectra_app.load_file(str(path))
                second_x, second_y = spectra_app.load_file(str(path))

            self.assertEqual(mocked_open.call_count, 1)
            self.assertEqual(first_x.tolist(), second_x.tolist())
            self.assertEqual(first_y.tolist(), second_y.tolist())

    def test_load_file_cache_invalidates_when_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            path.write_text("400,1\n500,2\n", encoding="utf-8")
            spectra_app.clear_file_cache()

            first_x, first_y = spectra_app.load_file(str(path))
            path.write_text("400,5\n500,7\n600,9\n", encoding="utf-8")
            os.utime(path, None)
            second_x, second_y = spectra_app.load_file(str(path))

            self.assertEqual(first_x.tolist(), [400.0, 500.0])
            self.assertEqual(first_y.tolist(), [1.0, 2.0])
            self.assertEqual(second_x.tolist(), [400.0, 500.0, 600.0])
            self.assertEqual(second_y.tolist(), [5.0, 7.0, 9.0])

    def test_iv_plot_renders_set_colored_sweeps_one_legend_entry_and_padded_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            neg = Path(tmp) / "device_under25.csv"
            pos = Path(tmp) / "device_under5.csv"
            neg.write_text("0,0,-20,1e-6\n0,0,-10,2e-6\n0,0,0,3e-6\n", encoding="utf-8")
            pos.write_text("0,0,0,4e-6\n0,0,10,5e-6\n0,0,20,6e-6\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="iv",
                n_panels=1,
                iv_sets=[{
                    "name": "Device A",
                    "color": "#0072B2",
                    "neg_path": str(neg),
                    "pos_path": str(pos),
                }],
                linewidth=2.0,
                fontsize=12,
                show_legend=True,
                legend_loc="best",
            ))

            ax = fig.axes[0]
            self.assertEqual(len(ax.lines), 2)
            self.assertTrue(all(line.get_color() == "#0072B2" for line in ax.lines))
            self.assertTrue(all(line.get_linestyle() == "-" for line in ax.lines))
            self.assertTrue(all(line.get_marker() in ("None", "none", "") for line in ax.lines))
            self.assertEqual(ax.get_xlabel(), "Voltage (V)")
            self.assertEqual(ax.get_ylabel(), "Current (µA)")
            self.assertEqual(
                [text.get_text() for text in ax.get_legend().get_texts()],
                ["Device A"],
            )
            self.assertEqual(ax.get_xlim(), (-22.0, 22.0))
            self.assertEqual(ax.get_ylim(), (0.75, 6.25))

    def test_iv_plot_accepts_legacy_path_groups_with_set_name_and_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            neg = Path(tmp) / "legacy_under20.csv"
            pos = Path(tmp) / "legacy_under0.csv"
            neg.write_text("0,0,-20,1e-6\n0,0,0,2e-6\n", encoding="utf-8")
            pos.write_text("0,0,0,3e-6\n0,0,20,4e-6\n", encoding="utf-8")
            fig = Figure()

            spectra_app.do_plot(fig, base_settings(
                plot_type="iv",
                n_panels=1,
                iv_sets=[{
                    "name": "Legacy Set",
                    "color": "#D55E00",
                    "neg_paths": [str(neg)],
                    "pos_paths": [str(pos)],
                }],
                show_legend=True,
                legend_loc="best",
            ))

            ax = fig.axes[0]
            self.assertEqual(len(ax.lines), 2)
            self.assertTrue(all(line.get_color() == "#D55E00" for line in ax.lines))
            self.assertEqual(
                [text.get_text() for text in ax.get_legend().get_texts()],
                ["Legacy Set"],
            )

    def test_iv_plot_rejects_missing_scan_groups(self):
        fig = Figure()

        with self.assertRaisesRegex(ValueError, "Set 1 requires both IV scan groups"):
            spectra_app.do_plot(fig, base_settings(
                plot_type="iv",
                n_panels=1,
                iv_sets=[{"name": "Device A", "neg_path": "neg.csv", "pos_path": ""}],
            ))

    def test_iv_dataset_widget_settings_include_name_color_and_single_sweep_paths(self):
        qapp()
        widget = spectra_app.IVDataSetWidget(0)
        widget.edit_name.setText("Device A")
        widget.color.set_hex("#009E73")
        widget.neg_path = r"C:\data\neg.csv"
        widget.pos_path = r"C:\data\pos.csv"
        widget._refresh_sweep_labels()

        self.assertEqual(widget.settings(), {
            "name": "Device A",
            "color": "#009E73",
            "neg_path": r"C:\data\neg.csv",
            "pos_path": r"C:\data\pos.csv",
        })

    def test_iv_dataset_widget_clear_sweep_removes_path_from_settings(self):
        qapp()
        widget = spectra_app.IVDataSetWidget(1)
        widget.neg_path = r"C:\data\neg.csv"
        widget.pos_path = r"C:\data\pos.csv"
        widget._clear_sweep("neg")

        settings = widget.settings()
        self.assertEqual(settings["neg_path"], "")
        self.assertEqual(settings["pos_path"], r"C:\data\pos.csv")


def write_ta_dat(path):
    """A small TA map in the collaborator's on-disk format."""
    import numpy as np

    # Enough delays inside the 0.6-6500 ps fit window for fit_global_map to run.
    time = np.concatenate([np.linspace(-10.0, 0.0, 3),
                           np.geomspace(0.2, 6000.0, 25)])
    wave = np.linspace(400.0, 540.0, 15)
    basis = spectra_app.ta_data.kinetic_basis(time, 0.4, 80.0, 3500.0)
    z = (basis @ np.vstack([np.ones(wave.size) * 5.0,
                            -np.ones(wave.size) * 3.0])).T
    with open(path, "w", encoding="utf-8") as f:
        f.write("XAxisTitle Wavelength (nm)\n")
        f.write("YAxisTitle Delay (ps)\n")
        f.write("0.0 " + " ".join("%.6E" % w for w in wave) + "\n")
        for j, t in enumerate(time):
            f.write("%.6E " % t + " ".join("%.6E" % v for v in z[:, j]) + "\n")
    return path


def ta_settings(tmpdir, **overrides):
    dat = write_ta_dat(os.path.join(tmpdir, "sample.dat"))
    settings = base_settings(
        plot_type="ta",
        n_panels=1,
        panel_data=[{"traces": [], "gradient": ("#000000", "#000000"),
                     "use_gradient": True}],
        panel_x_limits=[{"auto_x": True, "x_min": 0.0, "x_max": 1.0}],
        auto_x=True,
        panel_titles=["A"],
        ta_datasets=[{"uid": "u1", "path": dat, "display_name": "S n4",
                      "color": "#000000", "uvvis_path": ""}],
        ta_plot_kind="map",
        ta_trim=False,
        ta_trim_range=(400.0, 530.0),
        ta_cmap="Spectral",
        ta_time_scale="Symlog",
        ta_linthresh=5.0,
        ta_color_pct=98.0,
        ta_colorbar=False,
        ta_windows=list(spectra_app.ta_data.DEFAULT_TIME_WINDOWS_PS),
        ta_zero_line=True,
        ta_uvvis_overlay=True,
        ta_uvvis_auto=True,
        ta_high_band=(420.0, 450.0),
        ta_low_band=(520.0, 530.0),
        ta_high_label="High-bandgap phase",
        ta_low_label="MAPbBr3",
        ta_normalize=False,
        ta_norm_window=(900.0, 1100.0),
        ta_fit_overlay=False,
        ta_fit_annotate=False,
        ta_fits={},
        show_legend=True,
    )
    settings.update(overrides)
    return settings


class TAPlottingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_map_uses_delay_and_wavelength_axes(self):
        fig = Figure()
        message = spectra_app.do_plot(fig, ta_settings(self.tmp.name))

        ax = fig.axes[0]
        self.assertEqual(ax.get_xlabel(), "Pump-probe delay (ps)")
        self.assertIn("Wavelength", ax.get_ylabel())
        self.assertEqual(ax.get_xscale(), "symlog")
        self.assertIn("TA", message)

    def test_map_colorbar_adds_a_second_axes_only_when_enabled(self):
        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_colorbar=False))
        self.assertEqual(len(fig.axes), 1)

        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_colorbar=True))
        self.assertEqual(len(fig.axes), 2)

    def test_slices_draw_one_line_per_delay_window(self):
        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_plot_kind="slices"))

        ax = fig.axes[0]
        self.assertIn("Wavelength", ax.get_xlabel())
        # One line per window, plus the zero line.
        windows = len(spectra_app.ta_data.DEFAULT_TIME_WINDOWS_PS)
        self.assertEqual(len(ax.lines), windows + 1)

    def test_slices_uvvis_overlay_creates_a_twin_axis(self):
        uv = os.path.join(self.tmp.name, "uvvis.csv")
        with open(uv, "w", encoding="utf-8") as f:
            f.write("nm, A\n")
            for w in range(400, 541, 10):
                f.write(f"{w}.0, 0.5\n")

        settings = ta_settings(self.tmp.name, ta_plot_kind="slices")
        settings["ta_datasets"][0]["uvvis_path"] = uv
        fig = Figure()
        spectra_app.do_plot(fig, settings)

        self.assertEqual(len(fig.axes), 2)
        self.assertEqual(fig.axes[1].get_ylabel(), "Absorbance (OD)")

    def test_slices_skip_the_twin_axis_when_overlay_is_off(self):
        uv = os.path.join(self.tmp.name, "uvvis.csv")
        with open(uv, "w", encoding="utf-8") as f:
            f.write("nm, A\n400.0, 0.5\n500.0, 0.4\n")

        settings = ta_settings(self.tmp.name, ta_plot_kind="slices",
                               ta_uvvis_overlay=False)
        settings["ta_datasets"][0]["uvvis_path"] = uv
        fig = Figure()
        spectra_app.do_plot(fig, settings)

        self.assertEqual(len(fig.axes), 1)

    def test_kinetics_plots_both_bands_against_delay(self):
        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_plot_kind="kinetics"))

        ax = fig.axes[0]
        self.assertEqual(ax.get_xlabel(), "Pump-probe delay (ps)")
        self.assertEqual(ax.get_xscale(), "symlog")
        self.assertEqual(len(ax.lines), 2)

    def test_kinetics_label_reflects_normalization(self):
        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_plot_kind="kinetics",
                                             ta_normalize=True))
        self.assertIn("normalized", fig.axes[0].get_ylabel())

        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_plot_kind="kinetics",
                                             ta_normalize=False))
        self.assertIn("mOD", fig.axes[0].get_ylabel())

    def test_sas_without_a_fit_says_so_instead_of_drawing_nothing(self):
        fig = Figure()
        spectra_app.do_plot(fig, ta_settings(self.tmp.name, ta_plot_kind="sas"))

        texts = [t.get_text() for t in fig.axes[0].texts]
        self.assertIn("Run the global fit first", texts)

    def test_sas_draws_both_components_once_fitted(self):
        settings = ta_settings(self.tmp.name, ta_plot_kind="sas")
        m = spectra_app.load_ta_map(settings["ta_datasets"][0]["path"])
        settings["ta_fits"] = {"u1": spectra_app.ta_data.fit_global_map(m)}

        fig = Figure()
        spectra_app.do_plot(fig, settings)

        # Two species-associated spectra plus the zero line.
        self.assertEqual(len(fig.axes[0].lines), 3)

    def test_unreadable_dat_counts_as_failed_instead_of_raising(self):
        bad = os.path.join(self.tmp.name, "bad.dat")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("not a TA file\n")

        settings = ta_settings(self.tmp.name)
        settings["ta_datasets"][0]["path"] = bad
        fig = Figure()
        message = spectra_app.do_plot(fig, settings)

        self.assertIn("failed to load", message)

    def test_empty_panel_still_gets_styled_axes(self):
        settings = ta_settings(self.tmp.name, ta_datasets=[None])
        fig = Figure()
        spectra_app.do_plot(fig, settings)

        self.assertEqual(fig.axes[0].get_xlabel(), "Pump-probe delay (ps)")

    def test_trim_drops_channels_outside_the_probe_window(self):
        wide = ta_settings(self.tmp.name, ta_plot_kind="slices", ta_trim=False)
        narrow = ta_settings(self.tmp.name, ta_plot_kind="slices", ta_trim=True,
                             ta_trim_range=(420.0, 500.0))

        fig = Figure()
        spectra_app.do_plot(fig, wide)
        wide_points = len(fig.axes[0].lines[0].get_xdata())

        fig = Figure()
        spectra_app.do_plot(fig, narrow)
        narrow_points = len(fig.axes[0].lines[0].get_xdata())

        self.assertLess(narrow_points, wide_points)

    def test_ta_dataset_widget_reports_none_until_a_file_is_loaded(self):
        qapp()
        widget = spectra_app.TADataSetWidget(0)
        self.assertIsNone(widget.settings())

        widget.dataset = spectra_app.make_ta_dataset(
            write_ta_dat(os.path.join(self.tmp.name, "widget.dat")))
        widget.edit_name.setText("ES n1.5")
        self.assertEqual(widget.settings()["display_name"], "ES n1.5")

    def test_ta_dataset_widget_state_round_trips(self):
        qapp()
        widget = spectra_app.TADataSetWidget(0)
        widget.dataset = spectra_app.make_ta_dataset(
            write_ta_dat(os.path.join(self.tmp.name, "rt.dat")))
        widget.edit_name.setText("Sample A")
        state = widget.get_state()

        other = spectra_app.TADataSetWidget(0)
        other.set_state(state)
        self.assertEqual(other.settings()["path"], widget.settings()["path"])
        self.assertEqual(other.display_name(), "Sample A")


if __name__ == "__main__":
    unittest.main()
