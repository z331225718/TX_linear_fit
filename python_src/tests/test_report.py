"""Small contract tests for the HTML report semantics."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import report


def _fake_prt(dfe_taps=0, has_time_axis=False):
    fit = {
        'alignment_shift': 0, 'vf': 1.0, 'pmax': 0.9,
        'pulsePeakRatio': 1.0, 'eRms': 0.01, 'eRmsRatio': 0.02,
        'SNDR': 30.0, 'SNR_ISI': 20.0,
        'firNum': np.array([0.1, 1.0]),
        'firNumNorm': np.array([0.1, 1.0]),
        'firNumDFE': np.array([0.1, 1.0]),
        'firNumDFENorm': np.array([0.1, 1.0]),
        'DFEtapWeight': np.array([0.01]),
    }
    sndr = {
        'ffe': {
            'rlm_results': {'RLMbj': 0.99, 'RLMbs': 0.98},
            're_interleaved_signal': np.ones(32),
        },
        'ffe_and_dfe': {
            'rlm_results': {'RLMbj': 0.995, 'RLMbs': 0.99},
        },
    }
    meta = {'has_time_axis': has_time_axis,
            'osr_source': 'auto' if has_time_axis else 'manual'}
    if has_time_axis:
        meta.update({'native_samples_per_ui': 15.9,
                     'effective_samples_per_ui': 15.8,
                     'missing_sample_fraction': 0.0125})
    return SimpleNamespace(
        fit_results=fit, sndr_const=sndr,
        tf_calc={'nyquist_loss': -2.0, 'bw_3dB': 40e9},
        symbol_rate_input=32e9, osr_input=16,
        fit_spec={'t_dfe_taps': dfe_taps}, analysis_meta=meta,
        stream_input_interp=np.ones(64),
    )


def _cfg(profile='neutral', filename='input.csv', dfe_taps=0):
    return {
        'profile': profile, 'filename': filename, 'modulation': 'PAM4',
        'prbs_pattern': 'PRBS13', 'pattern_length': 8191,
        'pre_cursor_fit': 2, 'total_cursor_fit': 8,
        'pre_cursor_ffe': 2, 'total_cursor_ffe': 4,
        'dfe_tap_num': dfe_taps,
    }


def _render(tmp_path, prt, cfg, **kwargs):
    path = tmp_path / 'report.html'
    report.write_html_report(
        prt, (0.1, 0.2, 0.3, 0.0, 1.0),
        (0.2, 0.3, 0.4, 0.0, 1.1), cfg,
        out=str(path), plots_dir=str(tmp_path / 'no-plots'),
        central_eye_widths=(0.25, 0.5), **kwargs)
    return path.read_text(encoding='utf-8')


def test_neutral_profile_is_measurement_derived(tmp_path):
    text = _render(tmp_path, _fake_prt(), _cfg())
    assert 'measurement-derived transfer function' in text
    assert 'OIF' not in text
    assert 'protocol' not in text.lower()


def test_profile_label_and_osr_metadata(tmp_path):
    text = _render(tmp_path, _fake_prt(has_time_axis=True), _cfg('ieee8023'))
    assert 'IEEE 802.3' in text
    assert 'Analysis OSR' in text
    assert 'auto' in text
    assert '15.9000' in text
    assert '15.8000' in text
    assert '1.25%' in text

    oif_text = _render(tmp_path, _fake_prt(), _cfg('oif'))
    assert 'OIF profile' in oif_text
    assert 'no compliance limit' in oif_text


def test_missing_time_axis_is_explicit_n_a(tmp_path):
    text = _render(tmp_path, _fake_prt(), _cfg())
    assert text.count('n/a') >= 3
    assert 'Native/effective sampling values are n/a' in text


def test_user_labels_and_dfe_visibility(tmp_path):
    text = _render(tmp_path, _fake_prt(), _cfg())
    assert 'RLM (Min Adjacent Spacing)' in text
    assert 'RLM (IEEE 802.3bs)' in text
    assert 'ideal equally spaced PAM4 levels' in text
    assert 'limit must match the named definition' in text
    assert 'SNDR (FFE)' not in text
    assert 'SNDR (FFE + DFE)' not in text
    assert 'SNDRold' not in text
    assert 'DFE' not in text

    dfe_text = _render(tmp_path, _fake_prt(1), _cfg(dfe_taps=1))
    assert 'FFE + DFE' in dfe_text
    assert 'DFEtapWeight' in dfe_text


def test_precomputed_widths_skip_report_recalculation(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('report recalculated a service-provided eye width')

    monkeypatch.setattr(report, 'calc_central_eye_width', fail)
    text = _render(tmp_path, _fake_prt(), _cfg())
    assert '0.250000' in text
    assert '0.500000' in text

    metrics = SimpleNamespace(
        eye_uneq=SimpleNamespace(central_width_ui=0.125),
        eye_eq=SimpleNamespace(central_width_ui=0.625),
    )
    path = tmp_path / 'metrics.html'
    report.write_html_report(
        _fake_prt(), (0.1, 0.2, 0.3, 0.0, 1.0),
        (0.2, 0.3, 0.4, 0.0, 1.1), _cfg(),
        out=str(path), plots_dir=str(tmp_path / 'no-plots'), metrics=metrics)
    metrics_text = path.read_text(encoding='utf-8')
    assert '0.125000' in metrics_text
    assert '0.625000' in metrics_text


def test_legacy_call_still_accepts_fallback_width_calculation(tmp_path, monkeypatch):
    calls = []

    def fake_calc(*args, **kwargs):
        calls.append((args, kwargs))
        return {'width_ui': 0.375}

    monkeypatch.setattr(report, 'calc_central_eye_width', fake_calc)
    path = tmp_path / 'legacy.html'
    report.write_html_report(
        _fake_prt(), (0.1, 0.2, 0.3, 0.0, 1.0),
        (0.2, 0.3, 0.4, 0.0, 1.1), _cfg(),
        out=str(path), plots_dir=str(tmp_path / 'no-plots'))
    assert len(calls) == 2
    assert '0.375000' in path.read_text(encoding='utf-8')


def test_dynamic_text_is_escaped(tmp_path):
    text = _render(
        tmp_path, _fake_prt(),
        _cfg(filename='input"><script>alert(1)-end.csv'),
        title='<unsafe title>',
    )
    assert '<unsafe title>' not in text
    assert '&lt;unsafe title&gt;' in text
    assert '<script>alert(1)</script>' not in text
    assert '&lt;script&gt;alert(1)-end.csv' in text
