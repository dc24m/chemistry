#!/usr/bin/env python3
"""
ta_data.py — transient-absorption (TA) data core for SPECTRAplot.

A TA measurement is a 2-D map ΔA(λ, t): one axis is the probe wavelength, the
other the pump–probe delay. That does not fit the 1-D trace model the rest of
the app uses, so parsing, slicing and kinetic fitting live here.

numpy only — no Qt, no matplotlib, no scipy, no pandas. SPECTRAplot.spec
excludes scipy and pandas from the frozen build, so the global fit is done with
a hand-rolled simplex minimiser over a variable-projection cost (see
fit_global_map). Keeping this module Qt-free also makes it directly testable and
lets ta_batch.py share the exact maths the GUI uses.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import numpy as np


# ── Defaults taken from the collaborator's notebook ──────────────────────────

# Delay windows averaged into each spectral slice. The label is the nominal
# delay; the window is what actually gets averaged (averaging a few points
# instead of picking one cuts noise appreciably).
DEFAULT_TIME_WINDOWS_PS = [
    (-30.0, -5.0, '-10 ps'),
    (0.0, 2.0, '1 ps'),
    (9.0, 11.0, '10 ps'),
    (95.0, 105.0, '100 ps'),
    (990.0, 1010.0, '1000 ps'),
]

# Probe bands the manuscript tracks: the higher-bandgap quasi-2D phase and the
# lower-bandgap bulk MAPbBr3 phase.
HIGH_BAND_NM = (420.0, 450.0)
LOW_BAND_NM = (520.0, 530.0)

# Kinetic traces are normalised to their mean over this late-time window so the
# two bands can be compared on one axis.
NORM_WINDOW_PS = (900.0, 1100.0)

# Delay range used for the global fit. Starting at 0.6 ps skips the pump–probe
# overlap artefact, which the two-exponential model does not describe.
FIT_TIME_RANGE_PS = (0.6, 6500.0)

# The notebook fixes the long lifetime rather than fitting it; that choice is
# explicit here instead of buried in the model function.
DEFAULT_TAU_LONG_PS = 3500.0

TAU_RISE_GUESS_PS = 0.28
TAU_TRANSFER_GUESS_PS = 45.0
TAU_LONG_GUESS_PS = 2300.0

# Physically sensible limits, same as the notebook's least_squares bounds.
# They matter: without an upper limit on tau_transfer the two-component basis is
# degenerate — as tau_transfer grows, f_transfer collapses to a plain rising
# step that, paired with f_long, can absorb almost any decay. Three of the four
# 100-power samples run away to tau_transfer > 2000 ps unbounded.
TAU_RISE_BOUNDS_PS = (0.01, 10.0)
TAU_TRANSFER_BOUNDS_PS = (1.0, 1000.0)
TAU_LONG_BOUNDS_PS = (100.0, 100000.0)


@dataclass
class TAMap:
    """One TA experiment. Both axes are sorted ascending."""
    time_ps: np.ndarray          # (n_t,) pump–probe delay
    wavelength_nm: np.ndarray    # (n_w,) probe wavelength
    delta_a_mod: np.ndarray      # (n_w, n_t) ΔA in mOD

    @property
    def shape(self) -> tuple:
        return self.delta_a_mod.shape


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_ta_map(path: str):
    """
    Load a TA .dat file.

    Layout (two text header lines, then one numeric block):

        XAxisTitle Wavelength (nm)
        YAxisTitle Delay (ps)
        0.0      380.0   381.0   ...   550.0
        -10.0     ΔA      ΔA     ...    ΔA
        ...

    The first numeric row holds the probe wavelengths (its leading cell is a
    placeholder), the first numeric column the delays, the interior ΔA in mOD.

    Returns a TAMap, or None on any failure — matching the contract of
    _parse_spectra_file in spectra_app.py so this plugs into the same cache.
    """
    try:
        rows = []
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                if i < 2:          # instrument header
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    rows.append([float(p) for p in parts])
                except ValueError:
                    continue       # stray text row — skip rather than fail
    except Exception:
        return None

    if len(rows) < 3:
        return None

    header = rows[0]
    n_w = len(header) - 1
    if n_w < 2:
        return None

    wavelength = np.asarray(header[1:], dtype=float)

    times, matrix = [], []
    for row in rows[1:]:
        if len(row) < n_w + 1:
            continue               # truncated line
        times.append(row[0])
        matrix.append(row[1:n_w + 1])

    if len(times) < 2:
        return None

    time_ps = np.asarray(times, dtype=float)
    # Source is delay × wavelength; the rest of the app wants wavelength × delay.
    delta_a = np.asarray(matrix, dtype=float).T

    # Drop axis entries that are not finite, then sort both axes so slicing and
    # pcolormesh can assume monotonic axes.
    ok_t = np.isfinite(time_ps)
    ok_w = np.isfinite(wavelength)
    if ok_t.sum() < 2 or ok_w.sum() < 2:
        return None
    time_ps = time_ps[ok_t]
    wavelength = wavelength[ok_w]
    delta_a = delta_a[np.ix_(ok_w, ok_t)]

    w_order = np.argsort(wavelength)
    t_order = np.argsort(time_ps)
    return TAMap(
        time_ps=time_ps[t_order],
        wavelength_nm=wavelength[w_order],
        delta_a_mod=delta_a[np.ix_(w_order, t_order)],
    )


_RE_N = re.compile(r'^n(\d+(?:p\d+)?)$', re.I)
_RE_PWR = re.compile(r'^pwr(\d+(?:\.\d+)?)$', re.I)
_RE_EX = re.compile(r'^ex(\d+(?:\.\d+)?)$', re.I)
_RE_FREQ = re.compile(r'^(\d+(?:\.\d+)?)khz$', re.I)
_RE_ACQ = re.compile(r'^(\d+)acq$', re.I)
_RE_LP = re.compile(r'^(\d+(?:\.\d+)?)lp$', re.I)
_RE_DATE = re.compile(r'^(\d{8})$')


def parse_ta_filename(name: str) -> dict:
    """
    Pull the measurement metadata out of the collaborator's filename, e.g.

        20260824_n1p5_ES_Ex370_380LP_5kHz_300acq_MA_pwr100.0_CH.dat

    Token-by-token rather than one strict regex, so a file that only matches
    some of the convention still yields a useful label instead of nothing.
    """
    stem = os.path.splitext(os.path.basename(name))[0]
    info = {
        'stem': stem,
        'date': None,
        'n_label': None,
        'n_value': None,
        'morphology_code': None,
        'morphology': None,
        'excitation_nm': None,
        'longpass_nm': None,
        'rep_rate_khz': None,
        'acquisitions': None,
        'magic_angle': False,
        'chirp_corrected': False,
        'power': None,
    }

    for token in stem.split('_'):
        tok = token.strip()
        if not tok:
            continue
        upper = tok.upper()

        if upper == 'ES':
            info['morphology_code'] = 'ES'
            info['morphology'] = 'Electrospun'
            continue
        if upper == 'S':
            info['morphology_code'] = 'S'
            info['morphology'] = 'Spin-coat'
            continue
        if upper == 'MA':
            info['magic_angle'] = True
            continue
        if upper == 'CH':
            info['chirp_corrected'] = True
            continue

        m = _RE_DATE.match(tok)
        if m:
            info['date'] = m.group(1)
            continue
        m = _RE_N.match(tok)
        if m:
            info['n_label'] = tok
            try:
                info['n_value'] = float(m.group(1).replace('p', '.'))
            except ValueError:
                pass
            continue
        m = _RE_PWR.match(tok)
        if m:
            info['power'] = float(m.group(1))
            continue
        m = _RE_EX.match(tok)
        if m:
            info['excitation_nm'] = float(m.group(1))
            continue
        m = _RE_LP.match(tok)
        if m:
            info['longpass_nm'] = float(m.group(1))
            continue
        m = _RE_FREQ.match(tok)
        if m:
            info['rep_rate_khz'] = float(m.group(1))
            continue
        m = _RE_ACQ.match(tok)
        if m:
            info['acquisitions'] = int(m.group(1))
            continue

    info['label'] = _short_label(info)
    return info


def _short_label(info: dict) -> str:
    parts = []
    if info.get('morphology_code'):
        parts.append(info['morphology_code'])
    if info.get('n_value') is not None:
        parts.append(f"n{info['n_value']:g}")
    elif info.get('n_label'):
        parts.append(info['n_label'])
    if info.get('power') is not None:
        parts.append(f"pwr{info['power']:g}")
    return ' '.join(parts) if parts else info.get('stem', '')


# ── Slicing ───────────────────────────────────────────────────────────────────

def _window_mean(values: np.ndarray, axis_values: np.ndarray,
                 lo: float, hi: float, axis: int):
    """Mean of `values` over the axis entries inside [lo, hi].

    When the window contains no sample point the nearest single entry is used
    instead — a requested delay that falls between measured points should still
    give a curve rather than an empty plot.
    """
    lo, hi = sorted((float(lo), float(hi)))
    mask = (axis_values >= lo) & (axis_values <= hi)
    if not np.any(mask):
        idx = int(np.argmin(np.abs(axis_values - 0.5 * (lo + hi))))
        return np.take(values, idx, axis=axis).astype(float)
    with np.errstate(invalid='ignore'):
        return np.nanmean(np.compress(mask, values, axis=axis), axis=axis)


def spectrum_at(m: TAMap, t0: float, t1: float):
    """ΔA(λ) averaged over the delay window [t0, t1]. Returns (λ, ΔA)."""
    y = _window_mean(m.delta_a_mod, m.time_ps, t0, t1, axis=1)
    return m.wavelength_nm.copy(), np.asarray(y, dtype=float)


def kinetic_trace(m: TAMap, w0: float, w1: float, norm_window=None):
    """
    ΔA(t) averaged over the probe band [w0, w1]. Returns (t, ΔA).

    With `norm_window` given, the trace is divided by its own mean over that
    delay window, which is how the notebook puts the high- and low-bandgap
    traces on a common scale.
    """
    y = np.asarray(_window_mean(m.delta_a_mod, m.wavelength_nm, w0, w1, axis=0),
                   dtype=float)
    t = m.time_ps.copy()
    if norm_window is not None:
        y = normalize_late(t, y, norm_window)
    return t, y


def normalize_late(t: np.ndarray, y: np.ndarray, window=NORM_WINDOW_PS):
    """Divide a trace by its mean over `window`. Left unchanged if that mean is
    unusable, so a bad window degrades the plot rather than blowing it up."""
    lo, hi = sorted((float(window[0]), float(window[1])))
    mask = (t > lo) & (t < hi) & np.isfinite(y)
    if np.any(mask):
        ref = float(np.nanmean(y[mask]))
        if np.isfinite(ref) and abs(ref) > 1e-15:
            return y / ref
    return np.asarray(y, dtype=float).copy()


def dA_to_dT_over_T(delta_a_mod):
    """Convert ΔA in mOD to ΔT/T, as the notebook does."""
    return 10.0 ** (-np.asarray(delta_a_mod, dtype=float) * 1e-3) - 1.0


# ── Kinetic model ─────────────────────────────────────────────────────────────

def kinetic_basis(t, tau_rise: float, tau_transfer: float, tau_long: float):
    """
    The two shared temporal components of the global model, as an (n_t, 2)
    design matrix:

        f_transfer = exp(-t/tau_transfer) - exp(-t/tau_rise)
        f_long     = exp(-t/tau_long)

    f_transfer rises with tau_rise (carrier cooling) and decays with
    tau_transfer (funnelling to the low-bandgap phase); f_long is the
    nanosecond recombination. Both are zero before time zero.
    """
    t = np.asarray(t, dtype=float)
    tp = np.maximum(t, 0.0)
    f_transfer = np.exp(-tp / tau_transfer) - np.exp(-tp / tau_rise)
    f_long = np.exp(-tp / tau_long)
    neg = t < 0
    f_transfer[neg] = 0.0
    f_long[neg] = 0.0
    return np.column_stack([f_transfer, f_long])


def symlog_ticks(linthresh: float, t_min: float, t_max: float) -> list:
    """Decade tick positions for a symlog delay axis, plus zero.

    Matplotlib's default symlog locator also places ticks *inside* the linear
    threshold, which crowds -10^0, 0 and 10^0 into a few pixels on a TA delay
    axis and makes the labels unreadable. Starting at the first decade at or
    above linthresh avoids that. Returns [] when the range is unusable, so
    callers can just leave the default locator alone.
    """
    if not all(np.isfinite([linthresh, t_min, t_max])) or linthresh <= 0:
        return []
    first = 10.0 ** int(np.ceil(np.log10(linthresh)))
    ticks = [0.0]
    value = first
    while value <= t_max:
        ticks.append(value)
        value *= 10.0
    value = -first
    while value >= t_min:
        ticks.append(value)
        value *= 10.0
    return sorted(ticks) if len(ticks) > 1 else []


def nelder_mead(fun, x0, step: float = 0.2, tol: float = 1e-10,
                max_iter: int = 4000):
    """
    Downhill-simplex minimiser (Nelder–Mead), numpy only.

    Used instead of scipy.optimize.least_squares because the app ships without
    scipy. With only 2–3 free parameters (and the amplitudes projected out
    analytically) a derivative-free simplex is both adequate and robust.
    Returns (best_x, best_value).
    """
    x0 = np.asarray(x0, dtype=float)
    n = x0.size

    simplex = [x0.copy()]
    for i in range(n):
        p = x0.copy()
        p[i] += step if p[i] == 0.0 else step * abs(p[i])
        simplex.append(p)
    simplex = np.asarray(simplex, dtype=float)
    values = np.array([fun(p) for p in simplex], dtype=float)

    for _ in range(int(max_iter)):
        order = np.argsort(values)
        simplex, values = simplex[order], values[order]
        if abs(values[-1] - values[0]) <= tol * (abs(values[0]) + tol):
            break

        centroid = simplex[:-1].mean(axis=0)
        worst = simplex[-1]

        reflected = centroid + (centroid - worst)
        f_ref = fun(reflected)
        if f_ref < values[0]:
            expanded = centroid + 2.0 * (centroid - worst)
            f_exp = fun(expanded)
            simplex[-1], values[-1] = ((expanded, f_exp) if f_exp < f_ref
                                       else (reflected, f_ref))
        elif f_ref < values[-2]:
            simplex[-1], values[-1] = reflected, f_ref
        else:
            contracted = centroid + 0.5 * (worst - centroid)
            f_con = fun(contracted)
            if f_con < values[-1]:
                simplex[-1], values[-1] = contracted, f_con
            else:
                simplex[1:] = simplex[0] + 0.5 * (simplex[1:] - simplex[0])
                values[1:] = [fun(p) for p in simplex[1:]]

    order = np.argsort(values)
    return simplex[order][0], float(values[order][0])


def _log_bounds(fit_tau_long: bool):
    """Parameter box, in the log space the simplex actually searches."""
    bounds = [TAU_RISE_BOUNDS_PS, TAU_TRANSFER_BOUNDS_PS]
    if fit_tau_long:
        bounds.append(TAU_LONG_BOUNDS_PS)
    arr = np.log(np.asarray(bounds, dtype=float))
    return arr[:, 0], arr[:, 1]


def _varpro_cost(log_taus, t, targets, tau_long_fixed):
    """
    Sum of squared residuals after projecting out the linear amplitudes.

    `targets` is (n_t, n_series). For any candidate lifetime set the optimal
    amplitudes are the linear least-squares solution, so only the lifetimes
    stay non-linear — that is what makes a 2–3 parameter simplex enough.
    Lifetimes are searched as logs so they stay positive.

    Nelder–Mead has no notion of bounds, so out-of-box points are evaluated at
    the clipped lifetimes and scaled up by how far outside they sat. That keeps
    the cost finite (an inf would stall the simplex) while pushing it back in.
    """
    log_taus = np.asarray(log_taus, dtype=float)
    if not np.all(np.isfinite(log_taus)):
        return np.inf
    lo, hi = _log_bounds(tau_long_fixed is None)
    clipped = np.clip(log_taus, lo, hi)
    penalty = float(np.sum((log_taus - clipped) ** 2))

    taus = np.exp(clipped)
    if not np.all(np.isfinite(taus)):
        return np.inf
    if tau_long_fixed is None:
        tau_rise, tau_transfer, tau_long = taus
    else:
        tau_rise, tau_transfer = taus
        tau_long = tau_long_fixed

    basis = kinetic_basis(t, tau_rise, tau_transfer, tau_long)
    if not np.all(np.isfinite(basis)):
        return np.inf
    try:
        amps, *_ = np.linalg.lstsq(basis, targets, rcond=None)
    except np.linalg.LinAlgError:
        return np.inf
    cost = float(np.sum((targets - basis @ amps) ** 2))
    return cost * (1.0 + 1e3 * penalty)


def _solve(t, targets, tau_long_fixed, starts):
    """Run the simplex from several seeds and keep the best minimum.

    The cost surface has local minima — a single start can settle on a
    too-fast transfer time — so the seeds are spread around the notebook's
    initial guesses.
    """
    best_x, best_cost = None, np.inf
    for seed in starts:
        seed = np.asarray(seed, dtype=float)
        if tau_long_fixed is None and seed.size == 2:
            continue
        if tau_long_fixed is not None and seed.size == 3:
            seed = seed[:2]
        try:
            x, cost = nelder_mead(
                lambda p: _varpro_cost(p, t, targets, tau_long_fixed),
                np.log(seed),
            )
        except Exception:
            continue
        if np.isfinite(cost) and cost < best_cost:
            best_x, best_cost = x, cost
    return best_x, best_cost


def _seeds(fit_tau_long: bool):
    base = [
        (TAU_RISE_GUESS_PS, TAU_TRANSFER_GUESS_PS),
        (0.4, 80.0),
        (0.15, 20.0),
        (1.0, 150.0),
    ]
    if not fit_tau_long:
        return base
    return [(r, tr, tl) for r, tr in base for tl in (TAU_LONG_GUESS_PS, 3500.0)]


def _bound_flags(tau_rise, tau_transfer, tau_long, fit_tau_long, rtol=0.02):
    """Names of lifetimes that came to rest on a bound.

    A pinned lifetime means the data did not choose it — the optimiser was
    stopped by the box. That matters here: the two-component basis becomes
    nearly degenerate when tau_transfer grows (f_transfer flattens into a slow
    decay that f_long can mimic), and on this dataset the degenerate minimum
    sits within about 1% of the physical one. Callers surface this rather than
    quoting a lifetime the data does not actually support.
    """
    checks = [('tau_rise', tau_rise, TAU_RISE_BOUNDS_PS),
              ('tau_transfer', tau_transfer, TAU_TRANSFER_BOUNDS_PS)]
    if fit_tau_long:
        checks.append(('tau_long', tau_long, TAU_LONG_BOUNDS_PS))
    hit = []
    for name, value, (lo, hi) in checks:
        if value <= lo * (1.0 + rtol) or value >= hi * (1.0 - rtol):
            hit.append(name)
    return hit


def _bound_warning(hit):
    if not hit:
        return None
    return ('Fit stopped at a bound for: ' + ', '.join(hit) +
            '. The lifetimes are not constrained by this data — try a wider '
            'fit window, or treat the result as unreliable.')


def fit_global_map(m: TAMap,
                   t_range=FIT_TIME_RANGE_PS,
                   w_range=None,
                   tau_long: float = DEFAULT_TAU_LONG_PS,
                   fit_tau_long: bool = False) -> dict:
    """
    Global fit of the whole TA map: two shared temporal components with
    wavelength-dependent amplitudes, solved by variable projection.

    The notebook's own version hard-codes exp(-t/3500) inside the model while
    still passing tau_long as a fit parameter, so tau_long could not actually
    change its fit. Here the choice is explicit: tau_long is held at
    `tau_long` unless `fit_tau_long` is set.

    `w_range` restricts the fit to the usable probe window. Passing it matters:
    detector channels outside the probe range carry noise of the same order as
    the signal, and including them can pull the fit into the degenerate
    long-tau_transfer minimum.

    Returns a dict with the lifetimes, the two species-associated spectra
    (amplitude vs wavelength), the modelled map, its residual and RMS.
    `success` is False with an `error` message when the fit cannot be run.
    """
    lo, hi = sorted((float(t_range[0]), float(t_range[1])))
    tmask = (m.time_ps >= lo) & (m.time_ps <= hi)
    t = m.time_ps[tmask]
    z = m.delta_a_mod[:, tmask].astype(float)

    # Only wavelengths that are finite everywhere in the window take part, so
    # lstsq solves one clean system for all of them at once.
    wmask = np.all(np.isfinite(z), axis=1) & np.isfinite(m.wavelength_nm)
    if w_range is not None:
        w_lo, w_hi = sorted((float(w_range[0]), float(w_range[1])))
        in_window = (m.wavelength_nm >= w_lo) & (m.wavelength_nm <= w_hi)
        if in_window.sum() >= 3:
            wmask = wmask & in_window
    wave = m.wavelength_nm[wmask]
    z = z[wmask, :]

    if t.size < 10 or wave.size < 3:
        return {'success': False,
                'error': 'Not enough finite data in the fit window.'}

    targets = z.T                                   # (n_t, n_w)
    tau_long_fixed = None if fit_tau_long else float(tau_long)
    best_x, best_cost = _solve(t, targets, tau_long_fixed,
                               _seeds(fit_tau_long))
    if best_x is None:
        return {'success': False, 'error': 'Global fit did not converge.'}

    taus = np.exp(best_x)
    if fit_tau_long:
        tau_rise, tau_transfer, tau_long_out = (float(v) for v in taus)
    else:
        tau_rise, tau_transfer = (float(v) for v in taus)
        tau_long_out = float(tau_long)

    basis = kinetic_basis(t, tau_rise, tau_transfer, tau_long_out)
    amps, *_ = np.linalg.lstsq(basis, targets, rcond=None)   # (2, n_w)
    model = (basis @ amps).T                                  # (n_w, n_t)
    residual = z - model
    hit = _bound_flags(tau_rise, tau_transfer, tau_long_out, fit_tau_long)

    return {
        'success': True,
        'tau_rise_ps': tau_rise,
        'tau_transfer_ps': tau_transfer,
        'tau_long_ps': tau_long_out,
        'tau_long_fixed': not fit_tau_long,
        'at_bound': hit,
        'warning': _bound_warning(hit),
        'time_ps': t,
        'wavelength_nm': wave,
        'data': z,
        'fit': model,
        'residual': residual,
        'sas_transfer': amps[0, :],
        'sas_long': amps[1, :],
        'cost': best_cost,
        'rms_residual_mod': float(np.sqrt(np.mean(residual ** 2))),
    }


def fit_kinetic_traces(m: TAMap,
                       bands=(HIGH_BAND_NM, LOW_BAND_NM),
                       t_range=FIT_TIME_RANGE_PS,
                       norm_window=NORM_WINDOW_PS,
                       tau_long: float = DEFAULT_TAU_LONG_PS,
                       fit_tau_long: bool = True) -> dict:
    """
    Same model fitted to just the band-averaged traces (high- and low-bandgap),
    with one amplitude pair per band.

    Cheaper and easier to plot against, but based on two traces rather than the
    whole map — treat fit_global_map as the primary result and this as a
    cross-check.
    """
    lo, hi = sorted((float(t_range[0]), float(t_range[1])))
    tmask = (m.time_ps >= lo) & (m.time_ps <= hi)
    t = m.time_ps[tmask]

    traces = []
    for w0, w1 in bands:
        _, y = kinetic_trace(m, w0, w1, norm_window=norm_window)
        traces.append(y[tmask])

    targets = np.column_stack(traces)
    finite = np.all(np.isfinite(targets), axis=1)
    t, targets = t[finite], targets[finite]

    if t.size < 10:
        return {'success': False,
                'error': 'Not enough finite data in the fit window.'}

    tau_long_fixed = None if fit_tau_long else float(tau_long)
    best_x, best_cost = _solve(t, targets, tau_long_fixed,
                               _seeds(fit_tau_long))
    if best_x is None:
        return {'success': False, 'error': 'Trace fit did not converge.'}

    taus = np.exp(best_x)
    if fit_tau_long:
        tau_rise, tau_transfer, tau_long_out = (float(v) for v in taus)
    else:
        tau_rise, tau_transfer = (float(v) for v in taus)
        tau_long_out = float(tau_long)

    basis = kinetic_basis(t, tau_rise, tau_transfer, tau_long_out)
    amps, *_ = np.linalg.lstsq(basis, targets, rcond=None)
    model = basis @ amps
    hit = _bound_flags(tau_rise, tau_transfer, tau_long_out, fit_tau_long)

    return {
        'success': True,
        'tau_rise_ps': tau_rise,
        'tau_transfer_ps': tau_transfer,
        'tau_long_ps': tau_long_out,
        'tau_long_fixed': not fit_tau_long,
        'at_bound': hit,
        'warning': _bound_warning(hit),
        'time_ps': t,
        'data': targets,
        'fit': model,
        'amplitudes': amps,
        'cost': best_cost,
        'rms_residual_mod': float(np.sqrt(np.mean((targets - model) ** 2))),
    }


def bootstrap_lifetimes(m: TAMap, fit: dict, n_boot: int = 0,
                        seed: int = 12345, **fit_kwargs) -> dict:
    """
    Residual bootstrap for error bars on the trace-fit lifetimes.

    Resamples the fit residuals, adds them back to the model, and refits.
    Off by default (n_boot = 0) because each iteration is a full refit.
    """
    if not fit.get('success') or not n_boot or n_boot < 2:
        return {}

    rng = np.random.default_rng(seed)
    t = np.asarray(fit['time_ps'], dtype=float)
    data = np.asarray(fit['data'], dtype=float)
    model = np.asarray(fit['fit'], dtype=float)
    residual = (data - model).ravel()

    tau_long_fixed = None if not fit.get('tau_long_fixed') else fit['tau_long_ps']
    starts = _seeds(tau_long_fixed is None)

    rows = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(residual, size=residual.size, replace=True)
        target = model + sampled.reshape(model.shape)
        best_x, _cost = _solve(t, target, tau_long_fixed, starts)
        if best_x is None:
            continue
        taus = np.exp(best_x)
        if tau_long_fixed is None:
            rows.append(taus)
        else:
            rows.append(np.append(taus, tau_long_fixed))

    if not rows:
        return {}

    arr = np.asarray(rows, dtype=float)
    return {
        'bootstrap_n': int(arr.shape[0]),
        'tau_rise_sd_ps': float(np.std(arr[:, 0], ddof=1)) if arr.shape[0] > 1 else 0.0,
        'tau_transfer_sd_ps': float(np.std(arr[:, 1], ddof=1)) if arr.shape[0] > 1 else 0.0,
        'tau_long_sd_ps': float(np.std(arr[:, 2], ddof=1)) if arr.shape[0] > 1 else 0.0,
    }
