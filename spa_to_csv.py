#!/usr/bin/env python3
"""
spa_to_csv.py — convert Thermo Scientific OMNIC .spa (FTIR) files to two-column CSV.

Each .spa file is a binary blob holding one spectrum: a wavenumber range, a point
count, and the intensities (float32). This reads that block and writes
`wavenumber,intensity` rows (descending wavenumber, the OMNIC convention) — a format
that loads straight into SPECTRAplot.

Usage:
    python spa_to_csv.py sample.spa                 # -> sample.csv (next to input)
    python spa_to_csv.py a.spa b.spa c.spa          # convert several files
    python spa_to_csv.py path/to/folder             # every .spa under the folder
    python spa_to_csv.py folder --outdir converted  # write all CSVs into ./converted
    python spa_to_csv.py sample.spa --header         # add a "Wavenumber,Intensity" row

The binary offsets used here are the well-established OMNIC layout; this script was
verified byte-for-byte against pricebenjamin/SPA-file-reader's sample .spa/.csv pairs.
"""

import argparse
import os
import sys

import numpy as np


def read_spa(path: str):
    """Read one OMNIC .spa file.

    Returns (wavenumbers, intensities, title) where wavenumbers runs from the
    high wavenumber to the low one (OMNIC's native order) and both arrays are
    float64 of equal length.

    The layout of a .spa file varies between OMNIC versions and spectrum types
    (raw scan, subtraction result, …), so fixed byte offsets are unreliable.
    Instead we walk the block directory that starts at offset 304 (0x130): a run
    of 16-byte entries, each `key` (uint8) + `position` (uint32 @ +2) +
    `size` (uint32 @ +6), terminated by key 0 or 1. Key 2 is the header block
    (holds nx / first-x / last-x); key 3 is the float32 intensity block.
    """
    with open(path, 'rb') as f:
        raw = f.read()

    # Optional spectrum title: a null-terminated string near the top of the header.
    title = raw[30:30 + 255].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()

    nx = firstx = lastx = None
    data_pos = data_size = None
    pos = 304
    while pos + 16 <= len(raw):
        key = raw[pos]
        if key in (0, 1):            # end of directory
            break
        if key == 2 and nx is None:  # header block: nx, first-x, last-x
            hp = int(np.frombuffer(raw, np.uint32, 1, pos + 2)[0])
            if hp + 24 <= len(raw):
                nx = int(np.frombuffer(raw, np.uint32, 1, hp + 4)[0])
                firstx = float(np.frombuffer(raw, np.float32, 1, hp + 16)[0])
                lastx = float(np.frombuffer(raw, np.float32, 1, hp + 20)[0])
        elif key == 3 and data_pos is None:  # intensity data block (first one)
            data_pos = int(np.frombuffer(raw, np.uint32, 1, pos + 2)[0])
            data_size = int(np.frombuffer(raw, np.uint32, 1, pos + 6)[0])
        pos += 16

    if data_pos is None or not data_size:
        raise ValueError(f'{path}: no spectrum data block (key 3) found — not a valid .spa?')
    if data_pos + data_size > len(raw):
        raise ValueError(f'{path}: data block runs past end of file — file may be truncated.')

    n = data_size // 4
    intensities = np.frombuffer(raw, np.float32, n, data_pos).astype(float)

    # Build the wavenumber axis from the header endpoints. Fall back to a plain
    # index if the header block was missing or its length disagrees with the data.
    if firstx is None or lastx is None:
        wavenumbers = np.arange(n, dtype=float)
    else:
        wavenumbers = np.linspace(firstx, lastx, n if nx != n else nx)
    return wavenumbers, intensities, title


def write_csv(wavenumbers, intensities, out_path: str, header: bool = False):
    """Write a two-column CSV. %.7g preserves full float32 precision compactly."""
    with open(out_path, 'w', encoding='utf-8') as f:
        if header:
            f.write('Wavenumber,Intensity\n')
        for x, y in zip(wavenumbers, intensities):
            f.write(f'{x:.7g},{y:.7g}\n')


def find_spa_files(paths) -> list:
    """Expand the given paths into a flat list of .spa files (folders searched
    recursively, case-insensitively)."""
    found = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for name in files:
                    if name.lower().endswith('.spa'):
                        found.append(os.path.join(root, name))
        elif os.path.isfile(p):
            found.append(p)
        else:
            print(f'  ! not found: {p}', file=sys.stderr)
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='Convert Thermo OMNIC .spa (FTIR) files to two-column CSV.')
    ap.add_argument('inputs', nargs='+', help='.spa file(s) and/or folder(s) to convert')
    ap.add_argument('--outdir', help='write all CSVs into this folder '
                                     '(default: next to each input file)')
    ap.add_argument('--header', action='store_true',
                    help='include a "Wavenumber,Intensity" header row')
    args = ap.parse_args(argv)

    spa_files = find_spa_files(args.inputs)
    if not spa_files:
        print('No .spa files found.', file=sys.stderr)
        return 1

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)

    ok = 0
    for src in spa_files:
        try:
            wn, y, title = read_spa(src)
        except Exception as e:
            print(f'  ✗ {src}: {e}', file=sys.stderr)
            continue
        base = os.path.splitext(os.path.basename(src))[0] + '.csv'
        dst = os.path.join(args.outdir, base) if args.outdir else \
            os.path.splitext(src)[0] + '.csv'
        write_csv(wn, y, dst, header=args.header)
        print(f'  ✓ {src} -> {dst}  ({len(wn)} pts, {wn[0]:.1f}–{wn[-1]:.1f} cm⁻¹)')
        ok += 1

    print(f'Done: {ok}/{len(spa_files)} file(s) converted.')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
