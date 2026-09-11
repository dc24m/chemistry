import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QMessageBox
import spectra_app as app

_APP = QApplication.instance() or QApplication([])


class SessionWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {'SPECTRAPLOT_DATA_DIR': self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.win = app.MainWindow()
        self.addCleanup(self.win.deleteLater)
        self.assertTrue(hasattr(self.win, 'save_figure_document'), 'Editable figure saving is required')

    def trace(self):
        source = Path(self.tmp.name) / 'sample.csv'
        source.write_text('400,1\n500,2\n600,1\n')
        return {'path': str(source), 'uid': 'sample', 'label': 'Sample', 'color': '#336699',
                'visible': True, 'linewidth': 2., 'linestyle': 'solid'}

    def test_document_restores_controls_and_opens_new_tab(self):
        w = self.win
        w.controls.panel_widgets[0].set_state({'traces': [self.trace()]})
        w.controls.spin_fw.setValue(950)
        w.controls.spin_pa_left.setValue(.17)
        w.controls.spin_ta_high_lo.setValue(415)
        w.controls.spin_dpi.setValue(300)
        w._do_plot(silent=True)
        path = str(Path(self.tmp.name) / 'saved.spectra.json')
        self.assertTrue(w.save_figure_document(path))
        w.controls.spin_fw.setValue(600)
        self.assertTrue(w.open_figure_document(path))
        self.assertEqual(len(w._figure_states), 2)
        self.assertEqual(w.controls.spin_fw.value(), 950)
        self.assertAlmostEqual(w.controls.spin_pa_left.value(), .17)
        self.assertEqual(w.controls.spin_ta_high_lo.value(), 415)
        self.assertEqual(w.controls.spin_dpi.value(), 300)
        self.assertFalse(w._figure_states[1].dirty)

    def test_xrd_margin_label_edit_renames_trace_and_reference(self):
        w = self.win
        ref = Path(self.tmp.name) / 'ref.xy'
        ref.write_text('5 1\n10 2\n20 3\n')
        w.header.mode_tabs.buttons['xrd'].click()
        w.controls.panel_widgets[0].set_state({'traces': [self.trace()]})
        w.controls.xrd_ref_paths.append(str(ref))
        for lst, default in ((w.controls.xrd_ref_colors, '#000000'), (w.controls.xrd_ref_labels, 'Ref'),
                             (w.controls.xrd_ref_widths, None), (w.controls.xrd_ref_styles, 'solid'),
                             (w.controls.xrd_ref_scales, 1.0), (w.controls.xrd_ref_offsets, 0.0)):
            lst.append(default)
        w.controls.chk_xrd_margin_labels.setChecked(True)
        w._do_plot(silent=True)

        labels = {t.get_text(): t for t in w.canvas.fig.texts if t.get_gid() == 'xrd_margin_label'}
        self.assertEqual(set(labels), {'Sample', 'Ref'})
        for old, new in (('Sample', 'Perovskite'), ('Ref', 'PbI2 reference')):
            labels[old].set_text(new)
            w.editor._sync_text_to_controls(labels[old])

        self.assertEqual(w.controls.panel_widgets[0].traces[0]['display_name'], 'Perovskite')
        self.assertEqual(w.controls.xrd_ref_labels, ['PbI2 reference'])
        self.assertEqual(w.controls.xrd_ref_list.item(0).text(), 'PbI2 reference')

        w._do_plot(silent=True)
        replotted = {t.get_text() for t in w.canvas.fig.texts if t.get_gid() == 'xrd_margin_label'}
        self.assertEqual(replotted, {'Perovskite', 'PbI2 reference'})

    def test_preset_keeps_hidden_data_and_excludes_analysis(self):
        w = self.win
        w.controls.spin_panels.setValue(2)
        w.controls.panel_widgets[1].set_state({'traces': [self.trace()]})
        w.controls.chk_pl_normalize.setChecked(True)
        custom = w.capture_preset('My layout')
        self.assertNotIn('pl_normalize', custom['settings']['style'])
        self.assertNotIn('traces', custom['settings']['panels'][1])
        w.apply_preset(w.starter_presets()[0])
        self.assertEqual(w.controls.spin_panels.value(), 1)
        self.assertEqual(w.controls.panel_widgets[1].traces[0]['uid'], 'sample')
        self.assertTrue(w.controls.chk_pl_normalize.isChecked())
        w.apply_preset(custom)
        self.assertEqual(w.controls.spin_panels.value(), 2)
        self.assertEqual(w.controls.panel_widgets[1].traces[0]['uid'], 'sample')

    def test_invalid_document_leaves_workspace_untouched(self):
        w = self.win
        path = str(Path(self.tmp.name) / 'bad.spectra.json')
        Path(path).write_text('{"format":"spectraplot.figure","version":99}')
        before = copy.deepcopy(w.controls.capture_data())
        with patch.object(QMessageBox, 'warning'):
            self.assertFalse(w.open_figure_document(path))
        self.assertEqual(len(w._figure_states), 1)
        self.assertEqual(w.controls.capture_data(), before)

    def test_dirty_close_cancel_preserves_tab(self):
        w = self.win
        w._on_add_figure()
        w.controls.spin_fw.setValue(950)
        with patch.object(QMessageBox, 'warning', return_value=QMessageBox.StandardButton.Cancel):
            w._close_figure(1)
        self.assertEqual(len(w._figure_states), 2)

    def test_library_persists_and_imports_legacy(self):
        w = self.win
        item = w.capture_preset('Reusable')
        w.preset_library.save(item)
        from spectra_session import PresetLibrary
        fresh = PresetLibrary(w.storage_dir)
        self.assertEqual(fresh.items()[0]['name'], 'Reusable')
        legacy = Path(self.tmp.name) / 'legacy.json'
        legacy.write_text(json.dumps({'fig_width': 900, 'pl_normalize': True}))
        converted = fresh.import_file(legacy)
        self.assertEqual(converted['settings']['style']['fig_width'], 900)
        self.assertNotIn('pl_normalize', converted['settings']['style'])


if __name__ == '__main__':
    unittest.main()
