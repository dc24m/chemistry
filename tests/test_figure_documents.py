import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


class DocumentStorageTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('spectra_documents'),
                             'Versioned figure storage must exist')
        import spectra_documents
        self.store = spectra_documents
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'data.csv'
        self.source.write_text('400,1\n500,2\n', encoding='utf-8')

    def snapshot(self):
        return {'n_panels': 1, 'n_iv': 1,
                'panels': [{'traces': [{'path': str(self.source), 'uid': 'a',
                                        'label': 'Sample', 'visible': True}]}],
                'iv': [], 'ta': [], 'xrd_refs': [], 'style': {'fig_width': 800},
                'axis': {}, 'titles': {}, 'ta_fits': {}}

    def save(self, snap=None):
        path = self.root / 'figure.spectra.json'
        self.store.save_figure(path, 'Sample figure', 'pl', snap or self.snapshot(),
                               {'texts': {}})
        return path

    def test_roundtrip_and_relative_source_resolution(self):
        path = self.save()
        raw = json.loads(path.read_text())
        self.assertEqual(raw['version'], 1)
        self.assertEqual(raw['sources'][0]['relative'], 'data.csv')
        doc, issues = self.store.load_figure(path)
        self.assertEqual(doc['name'], 'Sample figure')
        self.assertEqual(doc['snapshot']['panels'][0]['traces'][0]['path'], str(self.source))
        self.assertEqual(issues, [])

    def test_moving_folder_prefers_relative_file(self):
        path = self.save()
        moved = self.root / 'moved'
        moved.mkdir()
        (moved / self.source.name).write_bytes(self.source.read_bytes())
        new_path = moved / path.name
        new_path.write_bytes(path.read_bytes())
        doc, issues = self.store.load_figure(new_path)
        self.assertEqual(doc['snapshot']['panels'][0]['traces'][0]['path'], str(moved / 'data.csv'))
        self.assertEqual(issues, [])

    def test_changed_and_missing_sources_preserve_assignments(self):
        path = self.save()
        self.source.write_text('400,999\n')
        doc, issues = self.store.load_figure(path)
        self.assertEqual(issues[0]['status'], 'changed')
        self.source.unlink()
        doc, issues = self.store.load_figure(path)
        self.assertEqual(issues[0]['status'], 'missing')
        self.assertEqual(doc['snapshot']['panels'][0]['traces'][0]['uid'], 'a')

    def test_numpy_fit_serialization_excludes_raw_measurements(self):
        snap = self.snapshot()
        snap['ta_fits'] = {'x': {'success': True, 'data': np.ones((2, 3)),
                                'sas_long': np.array([1., 2.]), 'cost': np.float64(2)}}
        path = self.save(snap)
        fit = json.loads(path.read_text())['snapshot']['ta_fits']['x']
        self.assertNotIn('data', fit)
        self.assertEqual(fit['sas_long'], [1., 2.])
        self.assertIn('data', snap['ta_fits']['x'])

    def test_atomic_failure_keeps_previous_document(self):
        path = self.save()
        before = path.read_bytes()
        with patch('spectra_documents.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.save()
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_versions_and_nested_shapes_rejected(self):
        path = self.save()
        original = json.loads(path.read_text())
        for modify in (lambda d: d.update(version=99),
                       lambda d: d['snapshot'].update(n_panels=99),
                       lambda d: d['snapshot'].update(panels='bad'),
                       lambda d: d['snapshot']['panels'][0].update(traces=['bad'])):
            value = copy.deepcopy(original)
            modify(value)
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                self.store.load_figure(path)


if __name__ == '__main__':
    unittest.main()
