import os
from pathlib import Path
import tempfile
import unittest
import unittest.mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np

import spectra_app as app
import spectra_documents as store


def write_csv(path, xs, ys):
    path.write_text(''.join(f'{x},{y}\n' for x, y in zip(xs, ys)), encoding='utf-8')
    return str(path)


class TraceMathTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.x = np.array([1.0, 2.0, 3.0, 4.0])
        self.y = np.array([2.0, 4.0, 6.0, 8.0])

    def test_number_operations(self):
        expected = {'+': [3, 5, 7, 9], '-': [1, 3, 5, 7], '*': [2, 4, 6, 8], '/': [2, 4, 6, 8]}
        for op, want in expected.items():
            got = app.apply_trace_math(self.x, self.y, {'op': op, 'value': 1.0})
            np.testing.assert_allclose(got, want)

    def test_trace_operations_on_same_grid(self):
        b = write_csv(self.root / 'b.csv', self.x, [1, 2, 3, 4])
        expected = {'+': [3, 6, 9, 12], '-': [1, 2, 3, 4], '*': [2, 8, 18, 32], '/': [2, 2, 2, 2]}
        for op, want in expected.items():
            got = app.apply_trace_math(self.x, self.y, {'op': op, 'operand_path': b})
            np.testing.assert_allclose(got, want)

    def test_mismatched_grid_interpolates_and_does_not_extrapolate(self):
        # Unsorted on purpose: b covers x 1.5..3.5 with y == 10 * x.
        b = write_csv(self.root / 'b.csv', [3.5, 1.5, 2.5], [35, 15, 25])
        got = app.apply_trace_math(self.x, self.y, {'op': '-', 'operand_path': b})
        self.assertTrue(np.isnan(got[0]))
        self.assertTrue(np.isnan(got[3]))
        np.testing.assert_allclose(got[1:3], [4 - 20, 6 - 30])

    def test_divide_by_zero_leaves_a_gap(self):
        b = write_csv(self.root / 'b.csv', self.x, [1, 0, 2, 4])
        got = app.apply_trace_math(self.x, self.y, {'op': '/', 'operand_path': b})
        self.assertTrue(np.isnan(got[1]))
        np.testing.assert_allclose(got[[0, 2, 3]], [2, 3, 2])

    def test_unreadable_operand_counts_as_failed(self):
        a = write_csv(self.root / 'a.csv', self.x, self.y)
        tr = app.make_trace(a)
        tr['math'] = {'op': '+', 'operand_path': str(self.root / 'missing.csv')}
        traces, failed = app._load_traces({'traces': [tr]})
        self.assertEqual((traces, failed), ([], 1))

    def test_gaps_do_not_blank_baseline_or_peak(self):
        y = np.array([np.nan, 3.0, 5.0, np.nan])
        np.testing.assert_allclose(app._pl_trace_y(y, True)[1:3], [0, 2])
        self.assertEqual(app._trace_peak(y), 5.0)
        self.assertEqual(app._trace_peak(np.array([np.nan, np.nan])), 0.0)

    def test_source_label(self):
        tr = {'path': 'dir/a.csv', 'math': {'op': '*', 'value': 2.0}}
        self.assertEqual(app.trace_math_source(tr), 'a.csv × 2')
        tr['math'] = {'op': '-', 'operand_path': 'dir/b.csv'}
        self.assertEqual(app.trace_math_source(tr), 'a.csv − b.csv')
        self.assertEqual(app.trace_math_source({'path': 'dir/a.csv'}), 'a.csv')

    def test_math_survives_figure_save_and_reopen(self):
        a = write_csv(self.root / 'a.csv', self.x, self.y)
        b = write_csv(self.root / 'b.csv', self.x, self.y)
        math = {'op': '-', 'operand_path': b}
        snap = {'n_panels': 1, 'n_iv': 1,
                'panels': [{'traces': [{'path': a, 'uid': 'r', 'visible': True, 'math': math}]}],
                'iv': [], 'ta': [], 'xrd_refs': [], 'style': {}, 'axis': {}, 'titles': {},
                'ta_fits': {}}
        path = self.root / 'fig.spectra.json'
        store.save_figure(path, 'Fig', 'pl', snap, {'texts': {}})
        doc, _ = store.load_figure(path)
        self.assertEqual({s['original'] for s in doc['sources']}, {a, b})
        trace = doc['snapshot']['panels'][0]['traces'][0]
        self.assertEqual(trace['math']['op'], '-')
        self.assertTrue(os.path.samefile(trace['math']['operand_path'], b))


class TraceMathDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = app.QApplication.instance() or app.QApplication([])

    def traces(self):
        return [app.make_trace('d/a.csv'), app.make_trace('d/b.csv')]

    def test_number_result(self):
        traces = self.traces()
        dlg = app.TraceMathDialog(traces, 1)
        dlg.combo_op.setCurrentIndex(dlg.combo_op.findData('*'))
        dlg.spin_value.setValue(2.5)
        tr = dlg.result_trace()
        self.assertEqual(tr['path'], 'd/b.csv')
        self.assertEqual(tr['math'], {'op': '*', 'value': 2.5})
        self.assertEqual(tr['display_name'], f"{traces[1]['display_name']} × 2.5")
        self.assertNotEqual(tr['uid'], traces[1]['uid'])
        self.assertNotIn('math', traces[1])

    def test_trace_result(self):
        dlg = app.TraceMathDialog(self.traces(), 0)
        dlg.combo_op.setCurrentIndex(dlg.combo_op.findData('-'))
        dlg.combo_b.setCurrentIndex(2)
        self.assertFalse(dlg.spin_value.isEnabled())
        self.assertEqual(dlg.result_trace()['math'], {'op': '-', 'operand_path': 'd/b.csv'})

    def test_typed_name_is_kept(self):
        dlg = app.TraceMathDialog(self.traces(), 0)
        dlg.edit_name.setText('Background removed')
        dlg.edit_name.textEdited.emit('Background removed')
        dlg.spin_value.setValue(3)
        self.assertEqual(dlg.result_trace()['display_name'], 'Background removed')

    def test_divide_by_constant_zero_is_blocked(self):
        dlg = app.TraceMathDialog(self.traces(), 0)
        ok = dlg.buttons.button(app.QDialogButtonBox.StandardButton.Ok)
        dlg.combo_op.setCurrentIndex(dlg.combo_op.findData('/'))
        dlg.spin_value.setValue(0)
        self.assertFalse(ok.isEnabled())
        dlg.spin_value.setValue(2)
        self.assertTrue(ok.isEnabled())

    def test_panel_adds_result_and_source_file_can_be_readded(self):
        panel = app.PanelFileWidget(0)
        result = app.make_trace('d/a.csv')
        result['math'] = {'op': '+', 'value': 1.0}
        panel.add_math_trace(result)
        self.assertEqual(panel.lst.count(), 1)
        self.assertEqual(panel.lst.currentRow(), 0)
        with unittest.mock.patch.object(app.QFileDialog, 'getOpenFileNames',
                                        return_value=(['d/a.csv'], '')):
            panel._add()
        self.assertEqual(len(panel.traces), 2)


class ExportTargetTest(unittest.TestCase):
    def test_typed_extension_wins(self):
        self.assertEqual(app.resolve_export_target('fig.PDF', 'PNG files (*.png)'), ('fig.PDF', 'pdf'))

    def test_filter_supplies_missing_extension(self):
        self.assertEqual(app.resolve_export_target('fig', 'PDF files (*.pdf)'), ('fig.pdf', 'pdf'))
        self.assertEqual(app.resolve_export_target('fig.v2', 'SVG files (*.svg)'), ('fig.v2.svg', 'svg'))

    def test_save_dialog_offers_all_formats_and_writes_pdf(self):
        qapp = app.QApplication.instance() or app.QApplication([])
        self.assertIsNotNone(qapp)
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'fig')
            panel = app.ControlPanel()
            panel._canvas = app.PlotCanvas()
            with unittest.mock.patch.object(app.QFileDialog, 'getSaveFileName',
                                            return_value=(target, 'PDF files (*.pdf)')) as dlg:
                panel._save()
            filters = dlg.call_args[0][3]
            for name in ('PNG', 'PDF', 'SVG'):
                self.assertIn(f'{name} files', filters)
            self.assertTrue(Path(target + '.pdf').read_bytes().startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
