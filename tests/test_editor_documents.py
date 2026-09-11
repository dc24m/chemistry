import json
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from matplotlib.figure import Figure
from PyQt6.QtWidgets import QApplication

import spectra_app

FigureCanvasQTAgg = spectra_app.FigureCanvasQTAgg


_APP = None


def qapp():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    return _APP


def make_editor():
    qapp()
    fig = Figure(figsize=(6, 4))
    canvas = FigureCanvasQTAgg(fig)
    host = SimpleNamespace(fig=fig, canvas=canvas)
    return fig, spectra_app.FigureEditor(host)


def build_legend_figure(fig, order=("red", "blue"), fontsize=10):
    fig.clear()
    ax = fig.subplots()
    sources = {
        "red": ("trace", "uid-red"),
        "blue": ("trace", "uid-blue"),
    }
    colors = {"red": "#cc0000", "blue": "#0044cc"}
    handles = []
    for name in order:
        line, = ax.plot([0, 1], [0, 1], color=colors[name], label=name.title())
        line._spectra_src = sources[name]
        handles.append(line)
    legend = ax.legend(handles=handles, labels=[name.title() for name in order],
                       loc="upper right", fontsize=fontsize, frameon=True)
    legend._spectra_sources = [sources[name] for name in order]
    ax.set_xlabel("Wavelength", fontsize=fontsize)
    annotation = ax.text(0.98, 0.97, "fit result", transform=ax.transAxes,
                         ha="right", va="top", fontsize=fontsize)
    return ax, legend, annotation


class FigureEditorDocumentTest(unittest.TestCase):
    def test_state_round_trip_restores_text_annotation_and_selected_legend_edits(self):
        fig, editor = make_editor()
        ax, legend, annotation = build_legend_figure(fig)
        editor.refresh()

        xlabel = ax.xaxis.label
        xlabel.set_text("Photon energy")
        xlabel.set_position((0.37, -0.18))
        xlabel.set_fontsize(17)
        xlabel.set_color("#123456")
        xlabel.set_fontweight("bold")
        xlabel.set_style("italic")
        annotation.set_text("custom fit")
        annotation.set_position((0.72, 0.81))

        legend.set_loc((0.22, 0.31))
        frame = legend.get_frame()
        frame.set_visible(True)
        frame.set_facecolor("#f0e0d0")
        frame.set_edgecolor("#102030")
        frame.set_linewidth(2.5)
        frame.set_alpha(0.65)
        red_text = legend.get_texts()[0]
        red_text.set_text("Edited red")
        red_text.set_fontsize(16)
        red_text.set_color("#654321")
        red_text.set_fontweight("bold")
        red_text.set_style("italic")

        state = editor.capture_state()
        json.dumps(state)

        restored_fig, restored = make_editor()
        changed = []
        restored.changed_callback = lambda: changed.append("changed")
        restored.restore_state(state)
        self.assertEqual(changed, [])

        new_ax, new_legend, new_annotation = build_legend_figure(
            restored_fig, order=("blue", "red"), fontsize=12)
        restored.refresh()
        self.assertEqual(changed, [])

        self.assertEqual(new_ax.get_xlabel(), "Photon energy")
        self.assertEqual(tuple(new_ax.xaxis.label.get_position()), (0.37, -0.18))
        self.assertEqual(new_ax.xaxis.label.get_fontsize(), 17)
        self.assertEqual(new_ax.xaxis.label.get_color(), "#123456")
        self.assertEqual(new_ax.xaxis.label.get_fontweight(), "bold")
        self.assertEqual(new_ax.xaxis.label.get_style(), "italic")
        self.assertEqual(new_annotation.get_text(), "custom fit")
        self.assertEqual(tuple(new_annotation.get_position()), (0.72, 0.81))

        self.assertEqual(tuple(new_legend._loc), (0.22, 0.31))
        new_frame = new_legend.get_frame()
        self.assertTrue(new_frame.get_visible())
        self.assertEqual(new_frame.get_linewidth(), 2.5)
        self.assertEqual(new_frame.get_alpha(), 0.65)
        by_source = dict(zip(new_legend._spectra_sources, new_legend.get_texts()))
        edited = by_source[("trace", "uid-red")]
        untouched = by_source[("trace", "uid-blue")]
        self.assertEqual(edited.get_text(), "Edited red")
        self.assertEqual(edited.get_fontsize(), 16)
        self.assertEqual(edited.get_color(), "#654321")
        self.assertEqual(edited.get_fontweight(), "bold")
        self.assertEqual(edited.get_style(), "italic")
        self.assertEqual(untouched.get_text(), "Blue")
        self.assertEqual(untouched.get_fontsize(), 12)

        build_legend_figure(restored_fig, order=("red", "blue"), fontsize=14)
        restored.refresh()
        rebuilt_legend = restored_fig.axes[0].get_legend()
        rebuilt_by_source = dict(zip(
            rebuilt_legend._spectra_sources, rebuilt_legend.get_texts()))
        self.assertEqual(rebuilt_by_source[("trace", "uid-red")].get_text(), "Edited red")
        self.assertEqual(rebuilt_by_source[("trace", "uid-blue")].get_fontsize(), 14)

    def test_xrd_margin_label_edit_follows_trace_uid_after_source_reordering(self):
        fig, editor = make_editor()

        def build(order):
            fig.clear()
            ax = fig.subplots()
            for name in order:
                uid = f"uid-{name}"
                line, = ax.plot([5, 20], [1, 2], label=name.title())
                line._spectra_src = ("trace", uid)
                text = fig.text(0.9, 0.4 if name == "red" else 0.6, name.title())
                text.set_gid("xrd_margin_label")
            return ax

        build(("red", "blue"))
        editor.refresh()
        red = next(text for text in fig.texts if text.get_text() == "Red")
        red.set_text("Primary phase")
        red.set_position((0.82, 0.73))
        red.set_fontsize(15)
        state = editor.capture_state()

        build(("blue", "red"))
        editor.restore_state(state)
        editor.refresh()
        labels = {text.get_text(): text for text in fig.texts}
        self.assertIn("Primary phase", labels)
        self.assertEqual(tuple(labels["Primary phase"].get_position()), (0.82, 0.73))
        self.assertEqual(labels["Primary phase"].get_fontsize(), 15)
        self.assertEqual(labels["Blue"].get_text(), "Blue")

    def test_committed_drag_undo_redo_and_legend_drag_notify_changes(self):
        fig, editor = make_editor()
        ax, legend, _annotation = build_legend_figure(fig)
        editor.refresh()
        changed = []
        editor.changed_callback = lambda: changed.append(editor.capture_state())

        label = ax.xaxis.label
        start = tuple(label.get_position())
        end = (0.25, -0.12)
        label.set_position(end)
        editor._selected = [label]
        editor._drag = {"items": [(label, (0.0, 0.0), start)]}
        editor._press = {"artist": label, "shift": False, "ctrl": False,
                         "was": True, "moved": True}
        editor._on_release(SimpleNamespace())
        self.assertEqual(len(changed), 1)

        editor.undo_stack.undo()
        self.assertEqual(tuple(label.get_position()), start)
        self.assertEqual(len(changed), 2)
        editor.undo_stack.redo()
        self.assertEqual(tuple(label.get_position()), end)
        self.assertEqual(len(changed), 3)

        editor._legend_press = {"legend": legend, "loc": legend._loc}
        legend.set_loc((0.1, 0.2))
        editor._on_legend_release(SimpleNamespace())
        self.assertEqual(len(changed), 4)
        self.assertEqual(editor.capture_state()["legends"]["legend:0"]["loc"],
                         [0.1, 0.2])


if __name__ == "__main__":
    unittest.main()
