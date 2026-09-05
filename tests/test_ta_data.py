import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ta_data


REAL_FILENAMES = [
    "20260824_n1p5_ES_Ex370_380LP_5kHz_300acq_MA_pwr100.0_CH.dat",
    "20260824_n1p5_ES_Ex370_380LP_5kHz_300acq_MA_pwr25.0_CH.dat",
    "20260824_n1p5_ES_Ex370_380LP_5kHz_300acq_MA_pwr50.0_CH.dat",
    "20260824_n1p5_S_Ex370_380LP_5kHz_300acq_MA_pwr100.0_CH.dat",
    "20260824_n1p5_S_Ex370_380LP_5kHz_300acq_MA_pwr25.0_CH.dat",
    "20260824_n1p5_S_Ex370_380LP_5kHz_300acq_MA_pwr50.0_CH.dat",
    "20260824_n4_ES_Ex370_380LP_5kHz_300acq_MA_pwr100.0_CH.dat",
    "20260824_n4_S_Ex370_380LP_5kHz_300acq_MA_pwr100.0_CH.dat",
]


def write_dat(path, time_ps, wavelength_nm, matrix_w_by_t):
    """Write a .dat in the collaborator's exact layout: two text header lines,
    a wavelength row with a leading placeholder, then one row per delay."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write('XAxisTitle Wavelength (nm)\n')
        f.write('YAxisTitle Delay (ps)\n')
        f.write('   0.0   ' + '   '.join('%.6E' % w for w in wavelength_nm) + '\n')
        for j, t in enumerate(time_ps):
            row = matrix_w_by_t[:, j]
            f.write('   %.6E   ' % t + '   '.join('%.6E' % v for v in row) + '\n')


class TAParsingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'sample.dat')
        self.time = np.array([-10.0, 0.0, 1.0, 10.0, 100.0])
        self.wave = np.array([400.0, 410.0, 420.0, 430.0])
        # Distinct value per cell so an orientation error is visible.
        self.matrix = np.arange(self.wave.size * self.time.size, dtype=float)
        self.matrix = self.matrix.reshape(self.wave.size, self.time.size)
        write_dat(self.path, self.time, self.wave, self.matrix)

    def test_round_trips_axes_and_orientation(self):
        m = ta_data.parse_ta_map(self.path)
        self.assertIsNotNone(m)
        np.testing.assert_allclose(m.time_ps, self.time)
        np.testing.assert_allclose(m.wavelength_nm, self.wave)
        self.assertEqual(m.delta_a_mod.shape, (self.wave.size, self.time.size))
        np.testing.assert_allclose(m.delta_a_mod, self.matrix)

    def test_sorts_unsorted_axes(self):
        path = os.path.join(self.tmp.name, 'unsorted.dat')
        write_dat(path, self.time[::-1], self.wave[::-1], self.matrix[::-1, ::-1])
        m = ta_data.parse_ta_map(path)
        np.testing.assert_allclose(m.time_ps, self.time)
        np.testing.assert_allclose(m.wavelength_nm, self.wave)
        np.testing.assert_allclose(m.delta_a_mod, self.matrix)

    def test_skips_trailing_text_row(self):
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write('end of file marker here\n')
        m = ta_data.parse_ta_map(self.path)
        self.assertEqual(m.delta_a_mod.shape, (self.wave.size, self.time.size))

    def test_returns_none_for_junk(self):
        path = os.path.join(self.tmp.name, 'junk.dat')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('not\na\nta file at all\n')
        self.assertIsNone(ta_data.parse_ta_map(path))

    def test_returns_none_for_missing_file(self):
        self.assertIsNone(ta_data.parse_ta_map(os.path.join(self.tmp.name, 'nope.dat')))


class FilenameTests(unittest.TestCase):
    def test_parses_every_real_filename(self):
        for name in REAL_FILENAMES:
            with self.subTest(name=name):
                info = ta_data.parse_ta_filename(name)
                self.assertEqual(info['date'], '20260824')
                self.assertEqual(info['excitation_nm'], 370.0)
                self.assertEqual(info['longpass_nm'], 380.0)
                self.assertEqual(info['rep_rate_khz'], 5.0)
                self.assertEqual(info['acquisitions'], 300)
                self.assertTrue(info['magic_angle'])
                self.assertTrue(info['chirp_corrected'])
                self.assertIn(info['morphology_code'], ('ES', 'S'))
                self.assertIn(info['n_value'], (1.5, 4.0))

    def test_label_and_morphology(self):
        es = ta_data.parse_ta_filename(REAL_FILENAMES[0])
        self.assertEqual(es['morphology'], 'Electrospun')
        self.assertEqual(es['label'], 'ES n1.5 pwr100')

        sc = ta_data.parse_ta_filename(REAL_FILENAMES[7])
        self.assertEqual(sc['morphology'], 'Spin-coat')
        self.assertEqual(sc['label'], 'S n4 pwr100')

    def test_unrecognised_name_falls_back_to_stem(self):
        info = ta_data.parse_ta_filename('some random measurement.dat')
        self.assertEqual(info['label'], 'some random measurement')
        self.assertIsNone(info['n_value'])


class SlicingTests(unittest.TestCase):
    def setUp(self):
        self.time = np.array([-10.0, 0.0, 1.0, 10.0, 100.0])
        self.wave = np.array([400.0, 410.0, 420.0, 430.0])
        self.matrix = np.arange(20, dtype=float).reshape(4, 5)
        self.m = ta_data.TAMap(self.time, self.wave, self.matrix)

    def test_spectrum_at_averages_the_window(self):
        w, y = ta_data.spectrum_at(self.m, 0.0, 1.0)
        np.testing.assert_allclose(w, self.wave)
        np.testing.assert_allclose(y, self.matrix[:, 1:3].mean(axis=1))

    def test_spectrum_at_falls_back_to_nearest_delay(self):
        # No sample point inside 60-80 ps; nearest to the centre (70) is 100 ps.
        _w, y = ta_data.spectrum_at(self.m, 60.0, 80.0)
        np.testing.assert_allclose(y, self.matrix[:, 4])

    def test_kinetic_trace_averages_the_band(self):
        t, y = ta_data.kinetic_trace(self.m, 400.0, 410.0)
        np.testing.assert_allclose(t, self.time)
        np.testing.assert_allclose(y, self.matrix[0:2, :].mean(axis=0))

    def test_kinetic_trace_falls_back_to_nearest_wavelength(self):
        _t, y = ta_data.kinetic_trace(self.m, 402.0, 404.0)
        np.testing.assert_allclose(y, self.matrix[0, :])

    def test_normalize_late_divides_by_window_mean(self):
        t = np.array([0.0, 950.0, 1050.0, 5000.0])
        y = np.array([10.0, 2.0, 4.0, 1.0])
        np.testing.assert_allclose(
            ta_data.normalize_late(t, y, (900.0, 1100.0)), y / 3.0)

    def test_normalize_late_leaves_trace_alone_when_window_is_empty(self):
        t = np.array([0.0, 1.0, 2.0])
        y = np.array([5.0, 6.0, 7.0])
        np.testing.assert_allclose(ta_data.normalize_late(t, y, (900.0, 1100.0)), y)

    def test_da_to_dt_over_t(self):
        np.testing.assert_allclose(ta_data.dA_to_dT_over_T(0.0), 0.0)
        # Positive delta-A means less transmission, so delta-T/T must be negative.
        self.assertLess(ta_data.dA_to_dT_over_T(10.0), 0.0)


class KineticModelTests(unittest.TestCase):
    def test_basis_is_zero_before_time_zero(self):
        t = np.array([-5.0, -1.0, 0.0, 1.0, 10.0])
        basis = ta_data.kinetic_basis(t, 0.4, 80.0, 3500.0)
        self.assertEqual(basis.shape, (5, 2))
        np.testing.assert_allclose(basis[:2, :], 0.0)
        self.assertTrue(np.all(basis[3:, 1] > 0))

    def test_nelder_mead_finds_a_known_minimum(self):
        best, value = ta_data.nelder_mead(
            lambda p: float((p[0] - 3.0) ** 2 + (p[1] + 1.5) ** 2), [0.0, 0.0])
        np.testing.assert_allclose(best, [3.0, -1.5], atol=1e-4)
        self.assertLess(value, 1e-8)


def synthetic_map(tau_rise=0.4, tau_transfer=80.0, tau_long=3500.0,
                  noise=0.0, seed=0):
    """A TA map built from the model itself, so a fit has a known right answer."""
    time = np.concatenate([
        np.linspace(-5.0, 0.0, 6),
        np.geomspace(0.1, 6500.0, 120),
    ])
    wave = np.linspace(400.0, 550.0, 40)
    basis = ta_data.kinetic_basis(time, tau_rise, tau_transfer, tau_long)
    # Two distinct, wavelength-dependent amplitude profiles.
    a_transfer = np.exp(-((wave - 425.0) / 18.0) ** 2) * 30.0
    a_long = -np.exp(-((wave - 525.0) / 12.0) ** 2) * 20.0
    z = (basis @ np.vstack([a_transfer, a_long])).T
    if noise:
        z = z + np.random.default_rng(seed).normal(0.0, noise, size=z.shape)
    return ta_data.TAMap(time, wave, z)


class GlobalFitTests(unittest.TestCase):
    def test_recovers_known_lifetimes_from_a_clean_map(self):
        fit = ta_data.fit_global_map(synthetic_map(), tau_long=3500.0)
        self.assertTrue(fit['success'], fit.get('error'))
        self.assertAlmostEqual(fit['tau_rise_ps'], 0.4, delta=0.02)
        self.assertAlmostEqual(fit['tau_transfer_ps'], 80.0, delta=2.0)
        self.assertEqual(fit['at_bound'], [])
        self.assertIsNone(fit['warning'])
        self.assertLess(fit['rms_residual_mod'], 1e-6)

    def test_recovers_lifetimes_with_noise(self):
        fit = ta_data.fit_global_map(synthetic_map(noise=0.2), tau_long=3500.0)
        self.assertTrue(fit['success'])
        self.assertAlmostEqual(fit['tau_rise_ps'], 0.4, delta=0.06)
        self.assertAlmostEqual(fit['tau_transfer_ps'], 80.0, delta=8.0)

    def test_shapes_and_sas_line_up(self):
        fit = ta_data.fit_global_map(synthetic_map())
        n_w = fit['wavelength_nm'].size
        n_t = fit['time_ps'].size
        self.assertEqual(fit['data'].shape, (n_w, n_t))
        self.assertEqual(fit['fit'].shape, (n_w, n_t))
        self.assertEqual(fit['residual'].shape, (n_w, n_t))
        self.assertEqual(fit['sas_transfer'].shape, (n_w,))
        self.assertEqual(fit['sas_long'].shape, (n_w,))
        # The transfer component peaks near 425 nm, the long-lived one near 525.
        self.assertAlmostEqual(
            fit['wavelength_nm'][np.argmax(fit['sas_transfer'])], 425.0, delta=8.0)
        self.assertAlmostEqual(
            fit['wavelength_nm'][np.argmin(fit['sas_long'])], 525.0, delta=8.0)

    def test_can_fit_tau_long_when_asked(self):
        fit = ta_data.fit_global_map(synthetic_map(tau_long=2000.0), fit_tau_long=True)
        self.assertTrue(fit['success'])
        self.assertFalse(fit['tau_long_fixed'])
        self.assertAlmostEqual(fit['tau_long_ps'], 2000.0, delta=200.0)

    def test_reports_bound_hits_instead_of_quoting_a_pinned_lifetime(self):
        # True transfer time of 3000 ps sits above the 1000 ps cap, so the fit
        # can only stop at the bound - and must say so rather than quote 1000 ps
        # as if the data had chosen it.
        m = synthetic_map(tau_rise=0.4, tau_transfer=3000.0, tau_long=200.0)
        fit = ta_data.fit_global_map(m, tau_long=200.0)
        self.assertTrue(fit['success'])
        self.assertEqual(fit['at_bound'], ['tau_transfer'])
        self.assertIn('bound', fit['warning'])

    def test_refuses_a_window_with_too_little_data(self):
        fit = ta_data.fit_global_map(synthetic_map(), t_range=(1000.0, 1001.0))
        self.assertFalse(fit['success'])
        self.assertIn('Not enough', fit['error'])


class TraceFitTests(unittest.TestCase):
    def test_recovers_lifetimes_from_band_traces(self):
        fit = ta_data.fit_kinetic_traces(
            synthetic_map(), bands=((415.0, 435.0), (515.0, 535.0)),
            fit_tau_long=False)
        self.assertTrue(fit['success'], fit.get('error'))
        self.assertAlmostEqual(fit['tau_rise_ps'], 0.4, delta=0.05)
        self.assertAlmostEqual(fit['tau_transfer_ps'], 80.0, delta=5.0)
        self.assertEqual(fit['data'].shape, fit['fit'].shape)
        self.assertEqual(fit['data'].shape[1], 2)

    def test_bootstrap_is_off_by_default(self):
        m = synthetic_map()
        fit = ta_data.fit_kinetic_traces(m, fit_tau_long=False)
        self.assertEqual(ta_data.bootstrap_lifetimes(m, fit), {})

    def test_bootstrap_reports_spread(self):
        m = synthetic_map(noise=0.2)
        fit = ta_data.fit_kinetic_traces(
            m, bands=((415.0, 435.0), (515.0, 535.0)), fit_tau_long=False)
        out = ta_data.bootstrap_lifetimes(m, fit, n_boot=4)
        self.assertEqual(out['bootstrap_n'], 4)
        self.assertGreaterEqual(out['tau_transfer_sd_ps'], 0.0)


if __name__ == '__main__':
    unittest.main()
