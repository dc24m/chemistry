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
