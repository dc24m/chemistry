#!/usr/bin/env python3
"""
ta_batch.py — batch analysis of a folder of transient-absorption .dat files.

Point it at the folder holding the collaborator's TA files and it walks the
tree, matches each map to its UV-vis spectrum, and writes plots and CSVs for
every sample into a TA_Analysis/ subfolder:

    python ta_batch.py "D:/Downloads/NY_collab/NY_collab"
    python ta_batch.py <folder> --no-fit
    python ta_batch.py <folder> --bootstrap 100

The maths comes from ta_data, the same module SPECTRAplot's Transient
Absorption mode uses, so the batch numbers and the on-screen figures cannot
drift apart. numpy + matplotlib only, matching the app's dependencies.

Use the GUI when you want to tune a figure; use this when you want every file
processed the same way without clicking through them.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import traceback

import numpy as np

import matplotlib
matplotlib.use('Agg')          # never needs a display
import matplotlib.pyplot as plt

import ta_data


OUTPUT_DIRNAME = 'TA_Analysis'
DPI = 300

# Probe window: outside it the detector records noise rather than signal, and
# including it wrecks both the colour scale and the global fit. See ta_data.
PROBE_WINDOW_NM = (400.0, 530.0)

EARLY_TIME_RANGE_PS = (-5.0, 50.0)
FULL_TIME_RANGE_PS = (-5.0, 7000.0)


# ── Discovery ─────────────────────────────────────────────────────────────────

def find_ta_files(root: str) -> list:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        if OUTPUT_DIRNAME in dirpath.split(os.sep):
            continue
        dirnames[:] = [d for d in dirnames if d != OUTPUT_DIRNAME]
        for name in filenames:
            if name.lower().endswith('.dat'):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def find_uvvis_files(root: str) -> list:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        if OUTPUT_DIRNAME in dirpath.split(os.sep):
            continue
        dirnames[:] = [d for d in dirnames if d != OUTPUT_DIRNAME]
        for name in filenames:
            if name.lower().endswith('.csv'):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def _squash(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def match_uvvis(info: dict, candidates: list):
    """Pair a TA map with its steady-state spectrum by n-value and morphology.

    Scored rather than matched by pattern because the UV-vis names use words
    ("spincoat") where the TA names use codes ("S"), and a bare "S" is far too
    common a substring to match on.
    """
    if not candidates or not info.get('n_label') or not info.get('morphology_code'):
        return None

    n_token = _squash(info['n_label'])
    best, best_score = None, 0
    for path in candidates:
        name = _squash(os.path.basename(path))
        score = 5 if n_token in name else 0
        if info['morphology_code'] == 'ES':
            if 'electrospun' in name:
                score += 5
            if f'{n_token}es' in name:
                score += 4
            if 'spincoat' in name:
                score -= 10
        else:
            if 'spincoat' in name or 'spincoated' in name:
                score += 6
            if 'electrospun' in name:
                score -= 10
        if score > best_score:
            best, best_score = path, score
    return best if best_score >= 6 else None


def load_uvvis(path: str):
    """Two-column wavelength/absorbance reader, tolerant of header lines."""
    xs, ys = [], []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                parts = [p for p in re.split(r'[,;\t\s]+', line.strip()) if p]
                if len(parts) < 2:
                    continue
                try:
                    x, y = float(parts[0]), float(parts[1])
                except ValueError:
                    continue
                if np.isfinite(x) and np.isfinite(y):
                    xs.append(x)
                    ys.append(y)
    except Exception:
        return None, None
    if len(xs) < 2:
        return None, None
    order = np.argsort(xs)
    return np.asarray(xs)[order], np.asarray(ys)[order]


# ── Plot helpers ──────────────────────────────────────────────────────────────

def save(fig, base: str):
    fig.savefig(base + '.png', dpi=DPI, bbox_inches='tight')
    fig.savefig(base + '.pdf', bbox_inches='tight')
    plt.close(fig)


def _symlog_ticks(ax, linthresh, t_min, t_max):
    ticks = ta_data.symlog_ticks(linthresh, t_min, t_max)
    if ticks:
        ax.set_xticks(ticks)


def probe_mask(wavelength):
    lo, hi = PROBE_WINDOW_NM
    mask = (wavelength >= lo) & (wavelength <= hi)
    return mask if mask.sum() >= 2 else np.ones(wavelength.shape, dtype=bool)


def plot_heatmap(m, base: str, title: str, time_range, symlog: bool):
    keep = probe_mask(m.wavelength_nm)
    tmask = (m.time_ps >= time_range[0]) & (m.time_ps <= time_range[1])
    if tmask.sum() < 2 or keep.sum() < 2:
        return
    z = m.delta_a_mod[np.ix_(keep, tmask)]
    finite = np.abs(z[np.isfinite(z)])
    limit = float(np.percentile(finite, 98)) if finite.size else 1.0
    if not np.isfinite(limit) or limit <= 0:
        limit = 1.0

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    mesh = ax.pcolormesh(m.time_ps[tmask], m.wavelength_nm[keep], z,
                         shading='auto', cmap='Spectral',
                         vmin=-limit, vmax=limit)
    fig.colorbar(mesh, ax=ax, label=r'$\Delta A$ (mOD)')
    if symlog:
        ax.set_xscale('symlog', linthresh=5.0)
        _symlog_ticks(ax, 5.0, m.time_ps[tmask].min(), m.time_ps[tmask].max())
    ax.set_xlabel('Pump-probe delay (ps)')
    ax.set_ylabel('Wavelength (nm)')
    ax.set_title(title)
    save(fig, base)


def plot_slices(m, base: str, title: str, uvvis):
    keep = probe_mask(m.wavelength_nm)
    windows = ta_data.DEFAULT_TIME_WINDOWS_PS
    colors = plt.cm.viridis(np.linspace(0.0, 0.9, len(windows)))

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for color, (t0, t1, label) in zip(colors, windows):
        x, y = ta_data.spectrum_at(m, t0, t1)
        ax.plot(x[keep], y[keep], color=color, label=label)
    ax.axhline(0.0, linewidth=0.8, color='black')
    ax.set_xlabel('Wavelength (nm)')
    ax.set_ylabel(r'$\Delta A$ (mOD)')
    ax.set_title(title)

    handles, labels = ax.get_legend_handles_labels()
    if uvvis is not None and uvvis[0] is not None:
        twin = ax.twinx()
        uv_x, uv_y = uvvis
        window = (uv_x >= PROBE_WINDOW_NM[0] - 20) & (uv_x <= PROBE_WINDOW_NM[1] + 30)
        twin.plot(uv_x[window], uv_y[window], color='black', linewidth=1.2)
        twin.set_ylabel('Absorbance (OD)')
        proxy, = ax.plot([], [], color='black', linewidth=1.2)
        handles.append(proxy)
        labels.append('UV-vis')

    ax.legend(handles, labels, frameon=False, fontsize=8, ncol=2)
    save(fig, base)


def plot_kinetics(m, base: str, title: str, normalized: bool, fit=None):
    norm = ta_data.NORM_WINDOW_PS if normalized else None
    t_high, y_high = ta_data.kinetic_trace(m, *ta_data.HIGH_BAND_NM, norm_window=norm)
    t_low, y_low = ta_data.kinetic_trace(m, *ta_data.LOW_BAND_NM, norm_window=norm)

    fig, ax = plt.subplots(figsize=(6.3, 4.0))
    ax.plot(t_high, y_high, label='High-bandgap phase '
            f'({ta_data.HIGH_BAND_NM[0]:g}-{ta_data.HIGH_BAND_NM[1]:g} nm)')
    ax.plot(t_low, y_low, label='Low-bandgap phase '
            f'({ta_data.LOW_BAND_NM[0]:g}-{ta_data.LOW_BAND_NM[1]:g} nm)')

    if fit and fit.get('success'):
        t_fit = np.asarray(fit['time_ps'], dtype=float)
        basis = ta_data.kinetic_basis(t_fit, fit['tau_rise_ps'],
                                      fit['tau_transfer_ps'], fit['tau_long_ps'])
        for band in (ta_data.HIGH_BAND_NM, ta_data.LOW_BAND_NM):
            t_all, y_all = ta_data.kinetic_trace(m, *band, norm_window=norm)
            y = np.interp(t_fit, t_all, y_all)
            good = np.isfinite(y)
            if good.sum() < 3:
                continue
            amps, *_ = np.linalg.lstsq(basis[good], y[good], rcond=None)
            ax.plot(t_fit, basis @ amps, 'k--', linewidth=1.1)
        ax.text(0.98, 0.97,
                (f"$\\tau_1$ = {fit['tau_rise_ps']:.3g} ps\n"
                 f"$\\tau_2$ = {fit['tau_transfer_ps']:.3g} ps\n"
                 f"$\\tau_3$ = {fit['tau_long_ps']:.3g} ps"),
                transform=ax.transAxes, ha='right', va='top', fontsize=9)

    ax.set_xscale('symlog', linthresh=5.0)
    _symlog_ticks(ax, 5.0, *FULL_TIME_RANGE_PS)
    ax.set_xlim(*FULL_TIME_RANGE_PS)
    ax.set_xlabel('Pump-probe delay (ps)')
    ax.set_ylabel(r'$\Delta A$ (normalized)' if normalized else r'$\Delta A$ (mOD)')
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    save(fig, base)


def plot_fit_maps(fit: dict, out_dir: str, title: str):
    t = np.asarray(fit['time_ps'], dtype=float)
    w = np.asarray(fit['wavelength_nm'], dtype=float)
    for name, z in (('global_fit_data', fit['data']),
                    ('global_fit_model', fit['fit']),
                    ('global_fit_residual', fit['residual'])):
        z = np.asarray(z, dtype=float)
        finite = np.abs(z[np.isfinite(z)])
        limit = float(np.percentile(finite, 98)) if finite.size else 1.0
        if not np.isfinite(limit) or limit <= 0:
            limit = 1.0
        fig, ax = plt.subplots(figsize=(7.0, 4.2))
        mesh = ax.pcolormesh(t, w, z, shading='auto', cmap='Spectral',
                             vmin=-limit, vmax=limit)
        fig.colorbar(mesh, ax=ax, label=r'$\Delta A$ (mOD)')
        ax.set_xscale('log')
        ax.set_xlabel('Pump-probe delay (ps)')
        ax.set_ylabel('Wavelength (nm)')
        ax.set_title(f"{title} - {name.replace('_', ' ')}")
        save(fig, os.path.join(out_dir, name))

    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.plot(w, np.asarray(fit['sas_transfer']), label='Transfer / cooling')
    ax.plot(w, np.asarray(fit['sas_long']), label='Long-lived')
    ax.axhline(0.0, linewidth=0.8, color='black')
    ax.set_xlabel('Wavelength (nm)')
    ax.set_ylabel('Fitted amplitude (mOD)')
    ax.set_title(f'{title} - global-fit amplitudes')
    ax.legend(frameon=False)
    save(fig, os.path.join(out_dir, 'global_fit_SAS'))


# ── Exports ───────────────────────────────────────────────────────────────────

def write_csv(path: str, header: list, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def export_matrix(m, path: str):
    header = ['wavelength_nm'] + [f'{t:g}' for t in m.time_ps]
    rows = ([f'{w:g}'] + [f'{v:.6g}' for v in row]
            for w, row in zip(m.wavelength_nm, m.delta_a_mod))
    write_csv(path, header, rows)


def export_slices(m, path: str):
    columns = [m.wavelength_nm]
    header = ['wavelength_nm']
    for t0, t1, label in ta_data.DEFAULT_TIME_WINDOWS_PS:
        _w, y = ta_data.spectrum_at(m, t0, t1)
        columns.append(y)
        header.append('deltaA_' + label.replace(' ', '_').replace('-', 'minus'))
    write_csv(path, header, zip(*[[f'{v:.6g}' for v in col] for col in columns]))


def export_kinetics(m, path: str):
    t, high = ta_data.kinetic_trace(m, *ta_data.HIGH_BAND_NM)
    _t, low = ta_data.kinetic_trace(m, *ta_data.LOW_BAND_NM)
    high_norm = ta_data.normalize_late(t, high)
    low_norm = ta_data.normalize_late(t, low)
    write_csv(
        path,
        ['time_ps', 'high_bandgap_mOD', 'low_bandgap_mOD',
         'high_bandgap_normalized', 'low_bandgap_normalized'],
        ([f'{a:g}'] + [f'{v:.6g}' for v in (b, c, d, e)]
         for a, b, c, d, e in zip(t, high, low, high_norm, low_norm)),
    )


def fit_summary(fit: dict) -> dict:
    """The scalar part of a fit result — the arrays go to CSV, not JSON."""
    skip = {'time_ps', 'wavelength_nm', 'data', 'fit', 'residual',
            'sas_transfer', 'sas_long'}
    return {k: v for k, v in fit.items() if k not in skip}


# ── Per-sample driver ─────────────────────────────────────────────────────────

def analyze(dat_path: str, output_root: str, uvvis_candidates: list,
            do_fit: bool, bootstrap: int) -> dict:
    m = ta_data.parse_ta_map(dat_path)
    if m is None:
        raise ValueError('could not be read as a TA map')

    info = ta_data.parse_ta_filename(dat_path)
    label = info['label'] or os.path.splitext(os.path.basename(dat_path))[0]
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', label).strip('_') or 'sample'
    out_dir = os.path.join(output_root, safe)
    os.makedirs(out_dir, exist_ok=True)

    uvvis_path = match_uvvis(info, uvvis_candidates)
    uvvis = load_uvvis(uvvis_path) if uvvis_path else None

    metadata = dict(info)
    metadata.update({
        'source_dat': dat_path,
        'matched_uvvis': uvvis_path,
        'n_wavelengths': int(m.wavelength_nm.size),
        'n_delays': int(m.time_ps.size),
        'wavelength_min_nm': float(m.wavelength_nm.min()),
        'wavelength_max_nm': float(m.wavelength_nm.max()),
        'time_min_ps': float(m.time_ps.min()),
        'time_max_ps': float(m.time_ps.max()),
        'probe_window_nm': list(PROBE_WINDOW_NM),
    })
    with open(os.path.join(out_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    export_matrix(m, os.path.join(out_dir, 'TA_matrix_mOD.csv'))
    export_slices(m, os.path.join(out_dir, 'TA_spectral_slices.csv'))
    export_kinetics(m, os.path.join(out_dir, 'TA_kinetics.csv'))

    plot_heatmap(m, os.path.join(out_dir, 'TA_heatmap_early'),
                 f'{label} - early time', EARLY_TIME_RANGE_PS, symlog=False)
    plot_heatmap(m, os.path.join(out_dir, 'TA_heatmap_full'),
                 f'{label} - full time', FULL_TIME_RANGE_PS, symlog=True)
    plot_slices(m, os.path.join(out_dir, 'TA_spectral_slices'), label, uvvis)
    plot_kinetics(m, os.path.join(out_dir, 'TA_kinetics_raw'), label,
                  normalized=False)

    summary = {'sample': label, 'source': dat_path, 'output': out_dir,
               'uvvis': uvvis_path or ''}

    fit = None
    if do_fit:
        fit = ta_data.fit_global_map(m, w_range=PROBE_WINDOW_NM)
        if fit.get('success'):
            if bootstrap:
                trace_fit = ta_data.fit_kinetic_traces(m, fit_tau_long=False)
                fit.update(ta_data.bootstrap_lifetimes(
                    m, trace_fit, n_boot=bootstrap))
            plot_fit_maps(fit, out_dir, label)
            write_csv(
                os.path.join(out_dir, 'global_fit_SAS.csv'),
                ['wavelength_nm', 'sas_transfer', 'sas_long'],
                ([f'{w:g}', f'{a:.6g}', f'{b:.6g}'] for w, a, b in
                 zip(fit['wavelength_nm'], fit['sas_transfer'], fit['sas_long'])),
            )
            summary.update({
                'tau_rise_ps': f"{fit['tau_rise_ps']:.4g}",
                'tau_transfer_ps': f"{fit['tau_transfer_ps']:.4g}",
                'tau_long_ps': f"{fit['tau_long_ps']:.4g}",
                'rms_residual_mOD': f"{fit['rms_residual_mod']:.4g}",
                'at_bound': ';'.join(fit.get('at_bound') or []),
            })
        with open(os.path.join(out_dir, 'fit_summary.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(fit_summary(fit), f, indent=2)

    plot_kinetics(m, os.path.join(out_dir, 'TA_kinetics_normalized'), label,
                  normalized=True, fit=fit)

    return summary


def run(root: str, do_fit: bool = True, bootstrap: int = 0) -> list:
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root):
        raise NotADirectoryError(root)

    ta_files = find_ta_files(root)
    if not ta_files:
        raise FileNotFoundError(f'No .dat files were found under {root}')
    uvvis_candidates = find_uvvis_files(root)

    output_root = os.path.join(root, OUTPUT_DIRNAME)
    os.makedirs(output_root, exist_ok=True)

    print('=' * 72)
    print('SPECTRAplot TA batch analysis')
    print('=' * 72)
    print(f'Root:       {root}')
    print(f'TA files:   {len(ta_files)}')
    print(f'UV-vis CSV: {len(uvvis_candidates)}')
    print(f'Output:     {output_root}')
    print(f'Global fit: {"on" if do_fit else "off"}')
    if bootstrap:
        print(f'Bootstrap:  {bootstrap}')
    print('=' * 72)

    results, errors = [], []
    for i, dat_path in enumerate(ta_files, start=1):
        print(f'[{i}/{len(ta_files)}] {os.path.basename(dat_path)}')
        try:
            summary = analyze(dat_path, output_root, uvvis_candidates,
                              do_fit, bootstrap)
            results.append(summary)
            if 'tau_transfer_ps' in summary:
                note = (f"  tau_1 = {summary['tau_rise_ps']} ps, "
                        f"tau_2 = {summary['tau_transfer_ps']} ps, "
                        f"tau_3 = {summary['tau_long_ps']} ps")
                if summary.get('at_bound'):
                    note += f"   [at bound: {summary['at_bound']}]"
                print(note)
            print(f"  -> {summary['output']}")
        except Exception as exc:
            print(f'  ERROR: {exc}')
            errors.append({'file': dat_path, 'error': str(exc),
                           'traceback': traceback.format_exc()})

    if results:
        keys = sorted({k for r in results for k in r})
        write_csv(os.path.join(output_root, 'TA_batch_summary.csv'), keys,
                  ([r.get(k, '') for k in keys] for r in results))

    with open(os.path.join(output_root, 'TA_batch_log.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'root': root, 'results': results, 'errors': errors},
                  f, indent=2)

    print('=' * 72)
    print(f'Finished: {len(results)} succeeded, {len(errors)} failed.')
    print(f'Results in: {output_root}')
    print('=' * 72)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Batch-analyze a folder of transient-absorption .dat files.')
    parser.add_argument('folder', help='Folder containing the TA .dat files.')
    parser.add_argument('--no-fit', action='store_true',
                        help='Skip the global kinetic fit; export and plot only.')
    parser.add_argument('--bootstrap', type=int, default=0, metavar='N',
                        help='Residual-bootstrap iterations for lifetime error '
                             'bars (default: 0, off).')
    args = parser.parse_args()

    try:
        run(args.folder, do_fit=not args.no_fit,
            bootstrap=max(0, args.bootstrap))
        return 0
    except Exception as exc:
        print(f'\nError: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
