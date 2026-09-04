# -*- coding: utf-8 -*-
"""Generate a self-contained HTML report for a linear-fit run.

The report deliberately keeps protocol language opt-in.  ``profile`` is a
labeling choice, not a compliance checker: this module never invents limits
or pass/fail criteria for a protocol.
"""
from __future__ import annotations

import base64
import html
import os
from collections.abc import Mapping
from datetime import datetime

import numpy as np

try:  # Package-style service imports and direct CLI imports are both valid.
    from .eye_info import calc_central_eye_width
except ImportError:  # pragma: no cover - direct ``python report.py`` path
    from eye_info import calc_central_eye_width


_PROFILE_INFO = {
    'neutral': {
        'label': 'Neutral',
        'tf_heading': 'Measurement-derived Transfer Function',
        'loss_label': 'TF magnitude @ Nyquist (measurement-derived)',
        'description': (
            'measurement-derived transfer function; no compliance limit or '
            'pass/fail criterion is applied.'),
    },
    'ieee8023': {
        'label': 'IEEE 802.3',
        'tf_heading': 'Transfer Function (IEEE 802.3 profile)',
        'loss_label': 'TF magnitude @ Nyquist (IEEE 802.3 profile)',
        'description': (
            'IEEE 802.3 profile label only; no compliance limit or pass/fail '
            'criterion is applied.'),
    },
    'oif': {
        'label': 'OIF',
        'tf_heading': 'Transfer Function (OIF profile)',
        'loss_label': 'TF magnitude @ Nyquist (OIF profile)',
        'description': (
            'OIF profile label only; no compliance limit or pass/fail '
            'criterion is applied.'),
    },
}


def _get(obj, key, default=None):
    """Read a field from a mapping or a dataclass-like object."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _h(value):
    """Escape a value before placing it in HTML text or an attribute."""
    return html.escape(str(value), quote=True)


def _text(value, default='?'):
    if value is None or value == '':
        value = default
    return _h(value)


def _cfg_text(cfg, key, default='?'):
    return _text(_get(cfg, key, default), default)


def _num(x, fmt='.4f'):
    try:
        value = float(x)
    except (TypeError, ValueError):
        return 'n/a'
    if not np.isfinite(value):
        return 'n/a'
    return format(value, fmt)


def _scaled_num(x, scale=1.0, fmt='.4f'):
    try:
        return _num(float(x) * scale, fmt)
    except (TypeError, ValueError):
        return 'n/a'


def _vec(x):
    try:
        a = np.atleast_1d(np.asarray(x, dtype=np.float64))
    except (TypeError, ValueError):
        return 'n/a'
    values = []
    for value in a:
        try:
            values.append('n/a' if not np.isfinite(value) else f'{value:.6g}')
        except TypeError:
            values.append('n/a')
    return '[' + ', '.join(values) + ']'


def _b64(path):
    with open(path, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')


def _img(path, caption):
    """Inline an image, without exposing the source path in the report."""
    if path and os.path.isfile(path):
        label = _h(caption)
        return (
            f'<figure class="img-card"><img src="{_b64(path)}" '
            f'alt="{label}"><figcaption>{label}</figcaption></figure>')
    return ''


def _profile(cfg):
    value = _get(cfg, 'profile', 'neutral')
    key = str(value).strip().lower() if value is not None else 'neutral'
    return key if key in _PROFILE_INFO else 'neutral'


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() not in ('', '0', 'false', 'off', 'no')
    return bool(value)


def _dfe_enabled(prt, cfg):
    spec = getattr(prt, 'fit_spec', {}) or {}
    value = _get(spec, 't_dfe_taps', None)
    if value is None:
        value = _get(cfg, 'dfe_tap_num', 0)
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return _as_bool(value)


def _eye_value(eye, index):
    try:
        return eye[index]
    except (IndexError, KeyError, TypeError):
        return None


def _width_ui(value):
    """Extract a precomputed central-eye width from common result shapes."""
    if value is None:
        return None
    if isinstance(value, Mapping) or hasattr(value, '__dict__'):
        width = _get(value, 'width_ui', None)
        if width is None:
            width = _get(value, 'central_width_ui', None)
        if width is None:
            width = _get(value, 'central_eye_width_99pct', None)
        value = width
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _precomputed_pair(widths):
    """Return (unequalized, equalized) widths from a mapping or pair."""
    if widths is None:
        return None, None
    if isinstance(widths, Mapping) or hasattr(widths, '__dict__'):
        uneq = None
        equalized = None
        for key in ('uneq', 'unequalized', 'eye_uneq', 'eye_unequalized',
                    'central_uneq', 'central_eye_uneq', 'central_eye_width_uneq'):
            candidate = _get(widths, key, None)
            if candidate is not None:
                uneq = _width_ui(candidate)
                break
        for key in ('eq', 'equalized', 'eye_eq', 'eye_equalized',
                    'central_eq', 'central_eye_eq', 'central_eye_width_eq'):
            candidate = _get(widths, key, None)
            if candidate is not None:
                equalized = _width_ui(candidate)
                break
        return uneq, equalized
    try:
        if len(widths) >= 2:
            return _width_ui(widths[0]), _width_ui(widths[1])
    except (TypeError, IndexError):
        pass
    return None, None


def _central_widths(prt, osr, central_eye_widths=None,
                    central_eye_uneq=None, central_eye_eq=None,
                    metrics=None):
    """Use service-computed widths; calculate only for the legacy API.

    The optional values may be scalar widths or ``{'width_ui': ...}`` result
    mappings.  A service may pass either a pair/mapping in
    ``central_eye_widths`` or the two explicit keyword arguments.
    """
    if central_eye_widths is None and metrics is not None:
        central_eye_widths = {
            'uneq': _get(_get(metrics, 'eye_uneq', None),
                         'central_width_ui', None),
            'eq': _get(_get(metrics, 'eye_eq', None),
                       'central_width_ui', None),
        }
    if central_eye_widths is None:
        central_eye_widths = getattr(prt, 'central_eye_widths', None)
    if central_eye_widths is None:
        # ``application.analyze`` attaches its immutable metrics snapshot to
        # the engine for compatibility callers.  Reuse those widths rather
        # than running the crossing analysis a second time.
        result = getattr(prt, '_analysis_result', None)
        metrics = getattr(result, 'metrics', None)
        if metrics is not None:
            central_eye_widths = {
                'uneq': _get(_get(metrics, 'eye_uneq', None),
                             'central_width_ui', None),
                'eq': _get(_get(metrics, 'eye_eq', None),
                           'central_width_ui', None),
            }
    uneq, equalized = _precomputed_pair(central_eye_widths)
    if central_eye_uneq is not None:
        uneq = _width_ui(central_eye_uneq)
    if central_eye_eq is not None:
        equalized = _width_ui(central_eye_eq)

    # Compatibility for callers that still provide only (prt, eye_uneq,
    # eye_eq, cfg).  The service path supplies both values above and does not
    # repeat the eye crossing analysis here.
    if uneq is None:
        uneq = _width_ui(calc_central_eye_width(
            prt.stream_input_interp, osr, settle_ui=100))
    if equalized is None:
        equalized = _width_ui(calc_central_eye_width(
            prt.sndr_const['ffe']['re_interleaved_signal'], osr,
            settle_ui=100))
    return uneq, equalized


def _analysis_osr(prt, cfg, metrics=None):
    meta = getattr(prt, 'analysis_meta', {}) or {}
    if not meta and metrics is not None:
        meta = _get(metrics, 'analysis_meta', {}) or {}
    has_time_axis = _as_bool(_get(meta, 'has_time_axis', False))
    analysis_osr = _get(meta, 'analysis_osr', None)
    if analysis_osr is None:
        analysis_osr = _get(meta, 'osr', None)
    if analysis_osr is None:
        analysis_osr = getattr(prt, 'osr_input', _get(cfg, 'osr', None))
    source = str(_get(meta, 'osr_source', 'manual')).strip().lower()
    if source not in ('auto', 'manual'):
        source = 'manual'
    native = _get(meta, 'native_samples_per_ui', None) if has_time_axis else None
    effective = (_get(meta, 'effective_samples_per_ui', None)
                 if has_time_axis else None)
    missing = (_get(meta, 'missing_sample_fraction', None)
               if has_time_axis else None)
    return {
        'analysis_osr': _num(analysis_osr, '.0f'),
        'source': source,
        'native': _num(native, '.4f'),
        'effective': _num(effective, '.4f'),
        'missing': _num(missing, '.2%'),
        'has_time_axis': has_time_axis,
    }


def _rlm_value(sndr, stage, key):
    result = _get(_get(sndr, stage, {}), 'rlm_results', {}) or {}
    return _num(_get(result, key, None), '.10f')


def write_html_report(prt, eye_uneq, eye_eq, cfg,
                      out='tx_linear_fit_report.html', plots_dir='results',
                      title=None, central_eye_widths=None,
                      central_eye_uneq=None, central_eye_eq=None,
                      metrics=None, analysis_metrics=None):
    """Generate a self-contained HTML report and return ``out``.

    ``metrics`` or ``central_eye_widths`` (or the two explicit width
    arguments) is the preferred service-facing input.  The fallback
    calculation keeps the historical four-argument call working for scripts
    outside the service.
    """
    cfg = cfg or {}
    if metrics is None:
        metrics = analysis_metrics
    fr = getattr(prt, 'fit_results', {}) or {}
    sndr = getattr(prt, 'sndr_const', {}) or {}
    tf = getattr(prt, 'tf_calc', {}) or {}
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    report_title = 'TX Linear Fit Report' if title is None else title

    sr = getattr(prt, 'symbol_rate_input', None)
    if sr is None:
        sr = _get(cfg, 'symbol_rate', None)
    nq_ghz = _scaled_num(sr, 0.5 / 1e9, '.2f')
    osr_info = _analysis_osr(prt, cfg, metrics=metrics)
    profile_key = _profile(cfg)
    profile = _PROFILE_INFO[profile_key]
    dfe_enabled = _dfe_enabled(prt, cfg)

    central_uneq_ui, central_eq_ui = _central_widths(
        prt, getattr(prt, 'osr_input', _get(cfg, 'osr', None)),
        central_eye_widths=central_eye_widths,
        central_eye_uneq=central_eye_uneq,
        central_eye_eq=central_eye_eq,
        metrics=metrics)
    try:
        ps_per_ui = 1e12 / float(sr)
    except (TypeError, ValueError, ZeroDivisionError):
        ps_per_ui = None
    central_uneq_ps = (_scaled_num(central_uneq_ui, ps_per_ui, '.2f')
                       if ps_per_ui is not None else 'n/a')
    central_eq_ps = (_scaled_num(central_eq_ui, ps_per_ui, '.2f')
                     if ps_per_ui is not None else 'n/a')

    # ---- Embedded images ------------------------------------------
    image_specs = (
        ('linear_fit_error', 'linear_fit_error.png', 'Fit residual'),
        ('constellation_hist', 'constellation_hist.png', 'Constellation histogram'),
        ('eye_uneq', 'eye_Unequalized.png', 'Unequalized eye diagram'),
        ('eye_eq', 'eye_Equalized.png', 'Equalized eye diagram'),
        ('ffe_coeff', 'ffe_coeff.png', 'FFE coefficients'),
        ('ffe_resp', 'ffe_resp.png', 'FFE response'),
        ('tf', 'tf.png', 'Transfer function'),
        ('pulse', 'linear_fit_pulse.png', 'Linear-fit pulse'),
        ('summary', 'tx_summary.png', 'Run summary'),
    )
    img_blocks = {
        key: _img(os.path.join(plots_dir, filename), caption)
        for key, filename, caption in image_specs
    }

    # ---- Small render helpers -------------------------------------
    def table(rows, headers=('Metric', 'Value')):
        head = ''.join(f'<th scope="col">{_h(value)}</th>' for value in headers)
        body = ''.join(
            f'<tr><td class="label-col">{_h(label)}</td>'
            f'<td class="val-col">{_h(value)}</td></tr>'
            for label, value in rows)
        return (
            '<div class="table-scroll"><table><thead><tr>' + head +
            '</tr></thead><tbody>' + body + '</tbody></table></div>')

    fit_rows = [
        ('alignment_shift', _num(_get(fr, 'alignment_shift', None), '.0f')),
        ('vf', _num(_get(fr, 'vf', None), '.10f')),
        ('pmax', _num(_get(fr, 'pmax', None), '.10f')),
        ('pulsePeakRatio', _num(_get(fr, 'pulsePeakRatio', None), '.10f')),
        ('eRms', _num(_get(fr, 'eRms', None), '.6e')),
        ('eRmsRatio', _num(_get(fr, 'eRmsRatio', None), '.6e')),
        ('SNDR', _num(_get(fr, 'SNDR', None), '.6f')),
        ('SNR_ISI', _num(_get(fr, 'SNR_ISI', None), '.6f')),
    ]
    taps_rows = [
        ('firNum', _vec(_get(fr, 'firNum', None))),
        ('firNumNorm', _vec(_get(fr, 'firNumNorm', None))),
    ]
    if dfe_enabled:
        taps_rows.extend([
            ('firNumDFE', _vec(_get(fr, 'firNumDFE', None))),
            ('firNumDFENorm', _vec(_get(fr, 'firNumDFENorm', None))),
            ('DFEtapWeight', _vec(_get(fr, 'DFEtapWeight', None))),
        ])

    rlm_headers = ['Metric', 'FFE']
    rlm_rows = [
        ('RLM (Min Adjacent Spacing)', _rlm_value(sndr, 'ffe', 'RLMbj')),
        ('RLM (IEEE 802.3bs)', _rlm_value(sndr, 'ffe', 'RLMbs')),
    ]
    if dfe_enabled:
        rlm_headers.append('FFE + DFE')
        rlm_rows = [
            (label, ffe, dfe)
            for (label, ffe), dfe in zip(
                rlm_rows,
                (_rlm_value(sndr, 'ffe_and_dfe', 'RLMbj'),
                 _rlm_value(sndr, 'ffe_and_dfe', 'RLMbs')))
        ]
    rlm_head = ''.join(f'<th scope="col">{_h(value)}</th>'
                       for value in rlm_headers)
    rlm_body = ''.join(
        '<tr>' + ''.join(
            f'<td class="{"label-col" if index == 0 else "val-col"}">'
            f'{_h(value)}</td>' for index, value in enumerate(row)) + '</tr>'
        for row in rlm_rows)
    rlm_table = (
        '<div class="table-scroll"><table><thead><tr>' + rlm_head +
        '</tr></thead><tbody>' + rlm_body + '</tbody></table></div>')

    eye_rows = [
        ('central_eye_width_99pct (UI)', _num(central_uneq_ui, '.6f'),
         _num(central_eq_ui, '.6f')),
        ('central_eye_width_99pct (ps)', central_uneq_ps, central_eq_ps),
        ('strict_eye_x_opening (UI)',
         _num(_eye_value(eye_uneq, 0), '.6f'),
         _num(_eye_value(eye_eq, 0), '.6f')),
        ('min_eye_y_opening (Vpp)',
         _num(_eye_value(eye_uneq, 1), '.6f'),
         _num(_eye_value(eye_eq, 1), '.6f')),
        ('max_eye_y_opening (Vpp)',
         _num(_eye_value(eye_uneq, 2), '.6f'),
         _num(_eye_value(eye_eq, 2), '.6f')),
        ('eye_y_opening_ratio',
         _num(_eye_value(eye_uneq, 4), '.4f'),
         _num(_eye_value(eye_eq, 4), '.4f')),
    ]
    eye_head = '<th scope="col">Metric</th><th scope="col">Unequalized</th>' \
        '<th scope="col">Equalized</th>'
    eye_body = ''.join(
        f'<tr><td class="label-col">{_h(label)}</td>'
        f'<td class="val-col">{_h(uneq)}</td>'
        f'<td class="val-col">{_h(equalized)}</td></tr>'
        for label, uneq, equalized in eye_rows)
    eye_table = (
        '<div class="table-scroll"><table><thead><tr>' + eye_head +
        '</tr></thead><tbody>' + eye_body + '</tbody></table></div>')

    osr_cells = [
        ('Analysis OSR', osr_info['analysis_osr']),
        ('Source', osr_info['source']),
        ('Native samples/UI', osr_info['native']),
        ('Effective samples/UI', osr_info['effective']),
        ('Missing fraction', osr_info['missing']),
    ]
    osr_html = ''.join(
        f'<div class="osr-item"><div class="metric-label">{_h(label)}</div>'
        f'<div class="metric-value">{_h(value)}</div></div>'
        for label, value in osr_cells)
    axis_note = (
        'Native/effective sampling values are n/a because no time axis was '
        'provided.' if not osr_info['has_time_axis'] else
        'Native and effective samples/UI are derived from the supplied time axis.')

    kpi = [
        ('SNDR (Fit)', _num(_get(fr, 'SNDR', None), '.2f'), 'dB'),
        ('RLM (Min Adjacent Spacing)',
         _rlm_value(sndr, 'ffe', 'RLMbj'), 'normalized'),
        (profile['loss_label'], _num(_get(tf, 'nyquist_loss', None), '.2f'),
         f'dB @ {nq_ghz} GHz'),
        ('BW 3dB', _scaled_num(_get(tf, 'bw_3dB', None), 1e-9, '.2f'), 'GHz'),
        ('Central Eye Width (equalized)', _num(central_eq_ui, '.3f'),
         f'UI / {central_eq_ps} ps · central 99%'),
        ('RLM (IEEE 802.3bs)',
         _rlm_value(sndr, 'ffe', 'RLMbs'), 'normalized'),
    ]
    kpi_html = ''.join(
        f'<div class="kpi"><div class="label">{_h(label)}</div>'
        f'<div class="value">{_h(value)}</div><div class="unit">{_h(unit)}</div></div>'
        for label, value, unit in kpi)

    dfe_meta = (
        f' · DFE={_cfg_text(cfg, "dfe_tap_num")} tap(s)'
        if dfe_enabled else '')
    fit_heading = 'FFE / DFE Taps' if dfe_enabled else 'FFE Taps'
    profile_note = _h(profile['description'])
    report_title_html = _h(report_title)
    source_name = _cfg_text(cfg, 'filename', '?')
    try:
        filename = os.path.basename(os.path.normpath(str(_get(cfg, 'filename', ''))))
    except (TypeError, ValueError):
        filename = '?'
    filename = _text(filename, '?')
    symbol_rate = _scaled_num(sr, 1e-9, '.4f')
    metadata_line = (
        f'Generated {now} · {_cfg_text(cfg, "modulation")} '
        f'{_cfg_text(cfg, "prbs_pattern")} / {_cfg_text(cfg, "pattern_length")} UI · '
        f'analysis OSR {osr_info["analysis_osr"]} ({osr_info["source"]}) · '
        f'{_h(symbol_rate)} GBd · file: {filename}')
    if source_name == '?':
        metadata_line = metadata_line.replace(' · file: ?', '')

    html_report = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{report_title_html}</title>
<style>
:root {{
  --bg:#101311; --surface:#1b201d; --surface-raised:#252c28;
  --text:#f3f1e9; --muted:#abb5ae; --accent:#59d2c3;
  --warm:#efb85f; --border:#424d47; --mono:"SFMono-Regular",Consolas,
    "Liberation Mono",Menlo,monospace;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
html {{ scroll-behavior:smooth; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,
  BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; font-size:15px;
  line-height:1.6; }}
a {{ color:var(--accent); }}
.container {{ width:min(1120px,100%); margin:0 auto; padding:0 24px 48px; }}
nav {{ position:sticky; top:0; z-index:10; display:flex; flex-wrap:wrap;
  gap:8px 20px; padding:12px 24px; background:rgba(16,19,17,.97);
  border-bottom:1px solid var(--border); }}
nav a {{ color:var(--muted); font:12px var(--mono); text-decoration:none; }}
nav a:hover, nav a:focus {{ color:var(--accent); }}
.report-header {{ padding:42px 0 28px; border-bottom:1px solid var(--border); }}
.eyebrow {{ color:var(--accent); font:12px var(--mono); letter-spacing:1.5px;
  text-transform:uppercase; }}
h1 {{ margin-top:8px; color:var(--text); font-size:36px;
  line-height:1.15; font-weight:700; overflow-wrap:anywhere; }}
.meta {{ margin-top:12px; color:var(--muted); font:12px/1.7 var(--mono);
  overflow-wrap:anywhere; }}
.profile-note {{ display:inline-block; margin-top:14px; padding:6px 10px;
  border-left:3px solid var(--warm); color:var(--text); font-size:13px; }}
section {{ margin-top:34px; }}
section h2 {{ padding-bottom:10px; border-bottom:1px solid var(--border);
  color:var(--text); font-size:22px; line-height:1.25; }}
section h2 .num {{ margin-right:10px; color:var(--accent); font:14px var(--mono); }}
.card {{ margin-top:14px; padding:18px; background:var(--surface);
  border:1px solid var(--border); border-radius:4px; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:10px; margin-top:14px; }}
.kpi {{ min-width:0; padding:16px 14px; background:var(--surface);
  border:1px solid var(--border); border-top:3px solid var(--accent); }}
.kpi .label {{ min-height:2.8em; color:var(--muted); font:11px/1.4 var(--mono);
  overflow-wrap:anywhere; }}
.kpi .value {{ margin:9px 0 4px; color:var(--text); font:700 25px var(--mono);
  overflow-wrap:anywhere; }}
.kpi .unit {{ color:var(--muted); font-size:12px; overflow-wrap:anywhere; }}
.osr-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px; }}
.osr-item {{ min-width:0; padding:12px 0; border-right:1px solid var(--border); }}
.osr-item:last-child {{ border-right:0; }}
.metric-label {{ color:var(--muted); font:11px/1.4 var(--mono); }}
.metric-value {{ margin-top:6px; color:var(--text); font:700 19px var(--mono);
  overflow-wrap:anywhere; }}
.note {{ margin-top:12px; color:var(--muted); font-size:13px; }}
h3 {{ margin:22px 0 10px; color:var(--text); font-size:16px; }}
.table-scroll {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
table {{ width:100%; min-width:440px; border-collapse:collapse; }}
th {{ padding:10px 12px; background:var(--surface-raised); color:var(--text);
  text-align:left; font-size:12px; white-space:nowrap; }}
td {{ padding:9px 12px; border-top:1px solid var(--border); color:var(--text);
  font:12px/1.45 var(--mono); white-space:nowrap; }}
tr:hover td {{ background:var(--surface-raised); }}
.label-col {{ color:var(--muted); }}
.val-col {{ color:var(--text); }}
.technical {{ margin-top:12px; color:var(--muted); font-size:12px; }}
.technical summary {{ cursor:pointer; color:var(--accent); }}
.technical p {{ margin-top:8px; }}
code {{ color:var(--warm); font-family:var(--mono); }}
.callout {{ margin-top:14px; padding:12px 15px; border-left:3px solid var(--warm);
  background:var(--surface); color:var(--muted); font-size:13px; }}
.img-card {{ margin-top:14px; padding:14px; background:var(--surface);
  border:1px solid var(--border); text-align:center; }}
.img-card img {{ display:block; width:auto; max-width:100%; height:auto; margin:0 auto; }}
.img-card figcaption {{ margin-top:8px; color:var(--muted); font:11px var(--mono); }}
footer {{ margin-top:46px; padding-top:16px; border-top:1px solid var(--border);
  color:var(--muted); text-align:center; font:11px var(--mono); }}
@media (max-width:640px) {{
  .container {{ padding:0 14px 34px; }}
  nav {{ padding:10px 14px; gap:6px 14px; }}
  .report-header {{ padding-top:30px; }}
  h1 {{ font-size:28px; }}
  .card {{ padding:12px; }}
  .osr-item {{ border-right:0; border-bottom:1px solid var(--border); }}
  .osr-item:last-child {{ border-bottom:0; }}
  .kpi .value {{ font-size:21px; }}
}}
</style></head><body>
<nav aria-label="Report sections">
  <a href="#kpi">KPI</a><a href="#osr">Sampling</a><a href="#fit">Fit</a>
  <a href="#rlm">RLM</a><a href="#tf">Transfer function</a>
  <a href="#eye">Eye</a><a href="#gallery">Gallery</a>
</nav>
<main class="container">
<header class="report-header">
  <div class="eyebrow">TX LINEAR FIT REPORT</div>
  <h1>{report_title_html}</h1>
  <p class="meta">{metadata_line}</p>
  <p class="meta">Pulse fit: pre={_cfg_text(cfg, 'pre_cursor_fit')} /
  total={_cfg_text(cfg, 'total_cursor_fit')} UI · FFE: pre=
  {_cfg_text(cfg, 'pre_cursor_ffe')} / total={_cfg_text(cfg, 'total_cursor_ffe')} taps
  {dfe_meta}</p>
  <p class="profile-note"><strong>{_h(profile["label"])} profile:</strong>
  {profile_note}</p>
</header>

<section id="kpi">
  <h2><span class="num">01</span>Key Metrics</h2>
  <div class="kpi-grid">{kpi_html}</div>
</section>

<section id="osr">
  <h2><span class="num">02</span>Analysis Sampling</h2>
  <div class="card"><div class="osr-grid">{osr_html}</div>
  <p class="note">{_h(axis_note)}</p></div>
</section>

<section id="fit">
  <h2><span class="num">03</span>Pulse Response Fit</h2>
  <div class="card">{table(fit_rows)}</div>
  <h3>{_h(fit_heading)}</h3>
  <div class="card">{table(taps_rows)}</div>
  {img_blocks['linear_fit_error']}
  {img_blocks['pulse']}
</section>

<section id="rlm">
  <h2><span class="num">04</span>Constellation RLM</h2>
  <div class="card">{rlm_table}
  <details class="technical"><summary>Technical metric definitions</summary>
  <p><strong>Min Adjacent Spacing</strong> is
  3 &times; min(V<sub>3</sub>-V<sub>2</sub>, V<sub>2</sub>-V<sub>1</sub>,
  V<sub>1</sub>-V<sub>0</sub>) / (V<sub>3</sub>-V<sub>0</sub>).</p>
  <p><strong>IEEE 802.3bs</strong> normalizes the two inner levels around
  (V<sub>0</sub>+V<sub>3</sub>)/2 and applies the IEEE R<sub>LM</sub> equation.
  Both metrics equal 1 for ideal equally spaced PAM4 levels. Any acceptance
  limit must match the named definition.</p>
  </details></div>
  {img_blocks['constellation_hist']}
  {img_blocks['ffe_coeff']}
  {img_blocks['ffe_resp']}
</section>

<section id="tf">
  <h2><span class="num">05</span>{_h(profile['tf_heading'])}</h2>
  <div class="card">{table([
    (profile['loss_label'], f'{_num(_get(tf, "nyquist_loss", None), ".4f")} dB @ {nq_ghz} GHz'),
    ('BW 3dB', f'{_scaled_num(_get(tf, "bw_3dB", None), 1e-9, ".4f")} GHz'),
  ])}</div>
  <div class="callout">{profile_note}</div>
  {img_blocks['tf']}
</section>

<section id="eye">
  <h2><span class="num">06</span>Eye Diagram</h2>
  <div class="card">{eye_table}</div>
  <div class="callout"><strong>Eye width definition:</strong> the primary
  value uses the interpolated zero-crossing phase central 99% interval;
  Strict zero-crossing width is retained as a compatibility diagnostic.</div>
  {img_blocks['eye_uneq']}
  {img_blocks['eye_eq']}
</section>

<section id="gallery">
  <h2><span class="num">07</span>Summary</h2>
  {img_blocks['summary']}
</section>

<footer>TX_linear_fit · python_src · {now}</footer>
</main></body></html>'''

    with open(out, 'w', encoding='utf-8') as f:
        f.write(html_report)
    return out


if __name__ == '__main__':
    print('report.py: use write_html_report(prt, eye_uneq, eye_eq, cfg, ...)')
