"""Self-contained regression tests for patterns, input parsing, and OSR."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


PYTHON_SRC = Path(__file__).resolve().parents[1]
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from application import resolve_osr
from eye_info import calc_central_eye_width
from pattern import func_prbs, gen_data_pattern
from process_input import process_lab_csv, process_lab_txt


def test_prbs_cycles_have_expected_lengths_and_binary_values():
    seq7 = func_prbs([1, 0, 0, 0, 0, 0, 1], [7, 6], 300)
    assert len(seq7) == 127
    assert seq7[0] == 1
    assert set(np.unique(seq7)) <= {0, 1}

    seq13 = func_prbs([1] + [0] * 11 + [1], [13, 12, 2, 1], 20_000)
    assert len(seq13) == 8191
    assert set(np.unique(seq13)) <= {0, 1}


def test_pam4_gray_mapping_and_nrz_levels():
    origin, bits, pam4 = gen_data_pattern("PRBS13", "PAM4", "fixed", 8191, 0, 0)
    assert len(pam4) == 8191
    assert len(bits) == 16_382
    np.testing.assert_array_equal(origin, bits)
    np.testing.assert_allclose(
        np.unique(np.round(pam4, 12)), [-1.0, -1 / 3, 1 / 3, 1.0], atol=1e-12
    )

    for index in range(64):
        pair = tuple(bits[2 * index:2 * index + 2])
        expected = {(1, 0): 1.0, (1, 1): 1 / 3, (0, 1): -1 / 3, (0, 0): -1.0}
        assert pam4[index] == pytest.approx(expected[pair])

    _, nrz_bits, nrz = gen_data_pattern("PRBS7", "NRZ", "fixed", 127, 0, 0)
    assert set(np.unique(nrz)) == {-1.0, 1.0}
    np.testing.assert_array_equal(nrz, 2 * (nrz_bits[:127] - 0.5))


def test_prbs31_supports_a_bounded_analysis_sequence():
    origin, bits, nrz = gen_data_pattern("PRBS31", "NRZ", "fixed", 1500, 0, 0)
    assert len(nrz) == 1500
    assert len(bits) == 1500
    assert len(origin) == 1502


def test_scope_text_and_voltage_only_input_parsers(tmp_path):
    timed = tmp_path / "timed.txt"
    timed.write_text(
        "Scope export\nData, \n1.0e-12,0.25\n1.5e-12,-0.50\n2.0e-12,0.75\n",
        encoding="utf-8",
    )
    parsed_timed = process_lab_txt(timed)
    np.testing.assert_allclose(parsed_timed["time_vec"], [0.0, 0.5e-12, 1.0e-12])
    np.testing.assert_allclose(parsed_timed["data_vec"], [0.25, -0.50, 0.75])

    voltage_only = tmp_path / "voltage.csv"
    voltage_only.write_text("Scope export\nData, \n0.25\n-0.50\n0.75\n", encoding="utf-8")
    parsed_voltage = process_lab_csv(voltage_only)
    assert parsed_voltage["time_vec"].size == 0
    np.testing.assert_allclose(parsed_voltage["data_vec"], [0.25, -0.50, 0.75])


def test_osr_auto_inference_handles_regular_and_gapped_time_axes():
    symbol_rate = 53.125e9
    regular = np.arange(100) / (symbol_rate * 5)
    osr, metadata = resolve_osr(regular, len(regular), symbol_rate)
    assert osr == 5
    assert metadata["osr_source"] == "auto"

    sample_indices = np.delete(np.arange(100), [10, 20, 21, 70])
    gapped = sample_indices / (symbol_rate * 12)
    osr, metadata = resolve_osr(gapped, len(gapped), symbol_rate)
    assert osr == 12
    assert metadata["missing_sample_fraction"] > 0


def test_osr_manual_override_and_fail_closed_inputs():
    symbol_rate = 53.125e9
    timed = np.arange(100) / (symbol_rate * 5)
    osr, metadata = resolve_osr(timed, len(timed), symbol_rate, 16)
    assert osr == 16
    assert metadata["osr_source"] == "manual"

    with pytest.raises(ValueError, match="voltage-only"):
        resolve_osr(np.array([]), 100, symbol_rate)

    steps = np.array([1, 1, 1, 1, 1, 1, 3, 3, 3, 3])
    ambiguous = np.r_[0, np.cumsum(steps)] / (symbol_rate * 12)
    with pytest.raises(ValueError, match="unable to infer"):
        resolve_osr(ambiguous, len(ambiguous), symbol_rate)


def test_central_eye_width_uses_interpolated_crossing_phases():
    osr = 20
    samples = np.arange(4000)
    waveform = np.r_[
        np.sin(np.pi * (samples - 0.25) / osr),
        np.sin(np.pi * (samples - 4.25) / osr),
    ]
    width = calc_central_eye_width(waveform, osr, settle_ui=0, central_fraction=0.99)
    assert width["width_ui"] == pytest.approx(0.8, abs=1e-9)

    no_crossing = calc_central_eye_width(
        np.ones(100), osr, settle_ui=0, central_fraction=0.99
    )
    assert np.isnan(no_crossing["width_ui"])
