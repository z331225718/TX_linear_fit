"""Regression tests for MATLAB-indexing and degenerate-input guards."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest


PYTHON_SRC = Path(__file__).resolve().parents[1]
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

import eye_persistence as eye_persistence_module
import pulse_response_tool as pulse_response_tool_module
from eye_info import calc_eye_info
from fit_pulse_response import fit_pulse_response
from pulse_response_tool import PulseResponseTool


def _eye_input():
    return np.arange(30, dtype=np.float64)


def test_calc_eye_info_settle_uses_matlab_inclusive_start():
    # MATLAB x1(settle_ui*OSR:end) is 1-based and inclusive.  For settle=1
    # and OSR=2, the first two-UI row therefore starts at x1[1] and is
    # [2, 3, 4, 5], not [3, 4, 5, 6].
    metrics = calc_eye_info(_eye_input(), 2, 1.0, 1, csv_output_dir=None)
    np.testing.assert_array_equal(metrics[5][0], [2.0, 3.0, 4.0, 5.0])


def test_eye_persistence_settle_uses_matlab_inclusive_start():
    # Use OSR=320 so the first persistence phase contains the first sample
    # directly (OSRup=1), making the one-sample indexing difference observable.
    data = np.ones(960, dtype=np.float64)
    data[0] = 99.0  # excluded by either valid settle interpretation
    data[319] = 0.75  # MATLAB's first retained sample for settle=1, OSR=320
    data[320] = -0.75  # first retained sample with the old Python slice

    original_histogram = eye_persistence_module.histogram_centers
    seen = []

    def capture_first_sample(values, centers):
        values = np.asarray(values, dtype=np.float64)
        seen.append(values.copy())
        return original_histogram(values, centers)

    with patch.object(eye_persistence_module, 'histogram_centers',
                      side_effect=capture_first_sample):
        eye_persistence_module.eye_persistence(
            data, settle_ui=1, delay=0, OSR=320, data_rate=1.0, Tsym=1.0)

    assert seen
    assert seen[0][0] == pytest.approx(0.75)


def test_calc_eye_info_csv_output_dir_controls_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    calc_eye_info(_eye_input(), 2, 1.0, 1, csv_output_dir=None)
    assert not (tmp_path / 'txcross.csv').exists()
    assert not (tmp_path / 'txhist.csv').exists()

    output_dir = tmp_path / 'nested' / 'eye-csv'
    calc_eye_info(_eye_input(), 2, 1.0, 1, csv_output_dir=output_dir)
    assert output_dir.is_dir()
    assert (output_dir / 'txcross.csv').is_file()
    assert (output_dir / 'txhist.csv').is_file()

    # The default remains '.', preserving direct-call behavior.
    calc_eye_info(_eye_input(), 2, 1.0, 1)
    assert (tmp_path / 'txcross.csv').is_file()
    assert (tmp_path / 'txhist.csv').is_file()


def _fit_spec(num_symbols):
    return {
        'osr_input': 2,
        'num_symbols': num_symbols,
        'symbol_rate_input': 1.0,
        't_dp': 0,
        't_np': 1,
        't_dw': 0,
        't_nw': 1,
        't_dfe_taps': 0,
    }


def test_fit_pulse_response_rejects_short_full_residual_window():
    with pytest.raises(ValueError, match='full residual.*too short'):
        fit_pulse_response(
            np.arange(8, dtype=np.float64),
            np.array([1.0, -1.0, 1.0, -1.0]),
            _fit_spec(num_symbols=4),
        )


def test_fit_pulse_response_rejects_short_sampled_residual_window():
    with pytest.raises(ValueError, match='sampled residual.*too short'):
        fit_pulse_response(
            np.arange(10, dtype=np.float64),
            np.array([1.0, -1.0, 1.0, -1.0, 1.0]),
            _fit_spec(num_symbols=5),
        )


def test_constellation_without_positive_phase_raises_runtime_error():
    tool = PulseResponseTool(osr=1, symbol_rate=1.0)
    tool.stream_input_interp = np.array([1.0, -1.0, 1.0, -1.0])
    tool.slice_target = 1.0
    tool.fit_results = {
        'firNum': np.array([1.0]),
        'firNumNorm': np.array([1.0]),
        'firNumDFE': np.array([1.0]),
        'firNumDFENorm': np.array([1.0]),
        'DFEtapWeight': np.array([], dtype=np.float64),
    }

    # Force each phase's SNDR to 0 dB, so the MATLAB-compatible `> 0`
    # selection never initializes goodConstellation.
    with patch.object(pulse_response_tool_module, 'rms', return_value=1.0):
        with pytest.raises(RuntimeError, match='No valid constellation phase'):
            tool._constellation_sndr_helper_f('off')
