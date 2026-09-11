"""Small persistent preset library for editable SpectraPlot sessions."""

from copy import deepcopy
from pathlib import Path

from spectra_documents import PRESET_FORMAT, VERSION, atomic_json, read_json, validate_preset


ANALYSIS_KEYS = {
    'pl_baseline_correct', 'pl_normalize', 'abs_normalize',
    'xrd_d_spacing', 'xrd_lambda', 'xrd_ref_step', 'xrd_exp_step',
    'xrd_margin_labels', 'xrd_margin_label_gap', 'xrd_normalize',
    'xrd_divisor', 'xrd_log_exp', 'smooth_enabled', 'smooth_amount',
    'ta_plot_kind', 'ta_trim', 'ta_time_scale', 'ta_linthresh',
    'ta_color_pct', 'ta_colorbar', 'ta_zero_line', 'ta_uvvis_overlay',
    'ta_uvvis_auto', 'ta_uvvis_min', 'ta_uvvis_max', 'ta_high_label',
    'ta_low_label', 'ta_normalize', 'ta_tau_long', 'ta_fit_tau_long',
    'ta_fit_overlay', 'ta_fit_annotate',
}


def preset_from_snapshot(name, snapshot):
    settings = deepcopy(snapshot)
    for panel in settings.get('panels', []):
        panel.pop('traces', None)
    for row in settings.get('iv', []):
        for key in ('neg_path', 'pos_path'):
            row.pop(key, None)
    for row in settings.get('ta', []):
        row.pop('dataset', None)
    settings['xrd_refs'] = []
    settings.pop('ta_fits', None)
    settings.pop('control_values', None)
    style = settings.setdefault('style', {})
    for key in ANALYSIS_KEYS:
        style.pop(key, None)
    preset = {'format': PRESET_FORMAT, 'version': VERSION,
              'name': name.strip(), 'settings': settings}
    validate_preset(preset)
    return preset


class PresetLibrary:
    def __init__(self, storage_dir):
        self.path = Path(storage_dir) / 'presets.json'

    def items(self):
        if not self.path.exists():
            return []
        value = read_json(self.path)
        return value if isinstance(value, list) else []

    def save(self, preset):
        validate_preset(preset)
        items = [item for item in self.items() if item.get('name') != preset['name']]
        items.append(preset)
        atomic_json(self.path, items)

    def import_file(self, path):
        value = read_json(path)
        if value.get('format') == PRESET_FORMAT:
            validate_preset(value)
            return value
        snapshot = {
            'n_panels': 1, 'n_iv': 1, 'panels': [], 'iv': [], 'ta': [],
            'xrd_refs': [], 'axis': {}, 'titles': {}, 'ta_fits': {},
            'style': {k: v for k, v in value.items() if k not in ANALYSIS_KEYS},
        }
        return preset_from_snapshot(Path(path).stem, snapshot)
