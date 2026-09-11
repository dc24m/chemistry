"""Versioned, data-linked figure documents. No Qt or renderer dependencies."""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

VERSION = 1
FIGURE_FORMAT = 'spectraplot.figure'
PRESET_FORMAT = 'spectraplot.preset'
MODES = {'pl', 'absorbance', 'xrd', 'iv', 'ta'}
PATH_KEYS = {'path', 'neg_path', 'pos_path', 'uvvis_path'}


def json_value(value):
    """Convert numpy scalars/arrays explicitly, rejecting opaque runtime objects."""
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    if hasattr(value, 'tolist'):
        return json_value(value.tolist())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Cannot save a non-finite numeric value.')
        return value
    raise ValueError(f'Cannot save {type(value).__name__}.')


def atomic_json(path, value):
    path = Path(path)
    payload = json.dumps(json_value(value), ensure_ascii=False, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp',
                                         delete=False) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle, parse_constant=lambda v: (_ for _ in ()).throw(
                ValueError(f'Invalid number: {v}')))
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ValueError('This is not a valid SpectraPlot JSON file.') from exc


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def map_paths(value, mapper):
    """Map only declared source fields, never arbitrary text resembling a path."""
    if isinstance(value, list):
        return [map_paths(v, mapper) for v in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in PATH_KEYS and isinstance(item, str) and item:
            result[key] = mapper(item)
        elif key == 'xrd_refs' and isinstance(item, list):
            result[key] = [mapper(p) for p in item]
        else:
            result[key] = map_paths(item, mapper)
    return result


def source_paths(snapshot):
    paths = []
    def collect(path):
        if path not in paths:
            paths.append(path)
        return path
    map_paths(snapshot, collect)
    return paths


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _dict(value, name):
    _require(isinstance(value, dict), f'{name} must be an object.')


def validate_snapshot(snap):
    _dict(snap, 'Figure settings')
    for key, maximum in (('n_panels', 5), ('n_iv', 10)):
        v = snap.get(key, 1)
        _require(type(v) is int and 1 <= v <= maximum, f'Invalid {key}.')
    for key in ('style', 'axis', 'titles', 'ta_fits', 'control_values'):
        _dict(snap.get(key, {}), key)
    for key, maximum in (('panels', 5), ('iv', 10), ('ta', 5)):
        rows = snap.get(key, [])
        _require(isinstance(rows, list) and len(rows) <= maximum, f'Invalid {key}.')
        for row in rows:
            _dict(row, key + ' entry')
            if key == 'panels':
                traces = row.get('traces', [])
                _require(isinstance(traces, list), 'Traces must be a list.')
                for trace in traces:
                    _dict(trace, 'Trace')
                    _require(isinstance(trace.get('path'), str), 'Trace path must be text.')
            if key == 'ta' and row.get('dataset') is not None:
                _dict(row['dataset'], 'TA dataset')
    refs = snap.get('xrd_refs', [])
    _require(isinstance(refs, list) and all(isinstance(p, str) for p in refs),
             'Reference paths must be a list of strings.')
    def check_paths(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in PATH_KEYS:
                    _require(isinstance(child, str), f'{key} must be text.')
                check_paths(child)
        elif isinstance(value, list):
            for child in value:
                check_paths(child)
    check_paths(snap)
    json_value(snap)


def validate_document(doc):
    _dict(doc, 'Document')
    _require(doc.get('format') == FIGURE_FORMAT, 'This is not a figure document.')
    _require(type(doc.get('version')) is int and doc['version'] == VERSION,
             'Unsupported figure version. Open it with a compatible SpectraPlot version.')
    _require(isinstance(doc.get('name'), str) and bool(doc['name'].strip()), 'Missing figure name.')
    _require(doc.get('mode') in MODES, 'Unknown plot mode.')
    validate_snapshot(doc.get('snapshot'))
    _dict(doc.get('editor', {}), 'Editor state')
    sources = doc.get('sources')
    _require(isinstance(sources, list), 'Missing source manifest.')
    originals = set()
    for src in sources:
        _dict(src, 'Source')
        for key in ('original', 'absolute'):
            _require(isinstance(src.get(key), str) and bool(src[key]), f'Missing source {key}.')
        _require(src.get('relative') is None or isinstance(src['relative'], str), 'Invalid relative path.')
        _require(src.get('fingerprint') is None or isinstance(src['fingerprint'], str), 'Invalid fingerprint.')
        _require(src['original'] not in originals, 'Duplicate source record.')
        originals.add(src['original'])
    _require(set(source_paths(doc['snapshot'])) == originals, 'Source manifest does not match figure files.')
    json_value(doc)


def save_figure(path, name, mode, snapshot, editor, previous_sources=None):
    snapshot = deepcopy(snapshot)
    for fit in snapshot.get('ta_fits', {}).values():
        # The renderer needs lifetimes and fitted spectra, not measured/residual maps.
        for key in ('data', 'fit', 'residual'):
            fit.pop(key, None)
    sources = []
    previous = {s['absolute']: s for s in (previous_sources or [])}
    for original in source_paths(snapshot):
        absolute = os.path.abspath(original)
        try:
            relative = os.path.relpath(absolute, Path(path).resolve().parent)
        except ValueError:  # Different Windows drives.
            relative = None
        old = previous.get(absolute, {})
        sources.append({'original': original, 'absolute': absolute, 'relative': relative,
                        'fingerprint': fingerprint(absolute) if os.path.isfile(absolute)
                        else old.get('fingerprint')})
    doc = json_value({'format': FIGURE_FORMAT, 'version': VERSION, 'name': name,
                      'mode': mode, 'snapshot': snapshot, 'editor': editor, 'sources': sources})
    validate_document(doc)
    atomic_json(path, doc)
    return doc


def load_figure(path):
    doc = read_json(path)
    validate_document(doc)
    mapping, issues = {}, []
    for src in doc['sources']:
        relative = src.get('relative')
        nearby = os.path.abspath(os.path.join(Path(path).resolve().parent, relative)) if relative else None
        resolved = nearby if nearby and os.path.isfile(nearby) else src['absolute']
        mapping[src['original']] = resolved
        status = None
        if not os.path.isfile(resolved):
            status = 'missing'
        elif src.get('fingerprint') and fingerprint(resolved) != src['fingerprint']:
            status = 'changed'
        if status:
            issues.append({'path': resolved, 'status': status, 'original': src['original']})
    doc['snapshot'] = map_paths(doc['snapshot'], lambda p: mapping[p])
    # Keep manifest aligned with resolved paths for subsequent Save/Save As.
    for src in doc['sources']:
        src['original'] = src['absolute'] = mapping[src['original']]
    if issues:
        doc['snapshot']['ta_fits'] = {}
    return doc, issues


def validate_preset(preset):
    _dict(preset, 'Preset')
    _require(preset.get('format') == PRESET_FORMAT and preset.get('version') == VERSION,
             'Unsupported preset format or version.')
    _require(isinstance(preset.get('name'), str) and bool(preset['name'].strip()), 'Name this preset.')
    _dict(preset.get('settings'), 'Preset settings')
    validate_snapshot(preset['settings'])
    _require(not source_paths(preset['settings']), 'Presets cannot contain source files.')
    json_value(preset)
