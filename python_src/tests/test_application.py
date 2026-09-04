# -*- coding: utf-8 -*-
"""Small service-contract tests using a deterministic fake engine."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import application  # noqa: E402


class FakePulseResponseTool:
    def __init__(self, osr, symbol_rate):
        self.osr_input = osr
        self.symbol_rate_input = symbol_rate
        self.fit_spec = {}
        self.analysis_meta = {}

    def config_input_stream_f(self, data):
        self.stream_input_interp = np.asarray(data, dtype=float)

    def config_decision_stream_f(self, **_kwargs):
        self.stream_decision_interp = np.ones(len(self.stream_input_interp) // self.osr_input)

    def config_linear_fit_pulse_f(self, **kwargs):
        self.fit_spec = {"t_dfe_taps": kwargs["dfe_tap_num"]}

    def apply_linear_fit_pulse_f(self, _shift_vec):
        self.fit_results = {
            "alignment_shift": 0,
            "firNum": np.array([1.0]),
            "firNumNorm": np.array([1.0]),
            "vf": 1.0,
            "pmax": 1.0,
            "pulsePeakRatio": 1.0,
            "eRms": 0.0,
            "eRmsRatio": 0.0,
            "SNDR": 40.0,
            "SNR_ISI": np.nan,
        }

    def calc_constellation_sndr_f(self):
        signal = np.asarray(self.stream_input_interp, dtype=float)
        stage = {
            "sndr": 20.0,
            "rlm_results": {"RLMbj": 1.0, "RLMbs": 1.0},
            "re_interleaved_signal": signal,
        }
        self.sndr_const = {"ffe": stage, "ffe_and_dfe": stage}

    def calc_tf_from_linear_fit_data_f(self):
        self.tf_calc = {
            "tf": np.array([1.0]),
            "freq": np.array([0.0]),
            "nyquist_loss": 0.0,
            "bw_3dB": 1.0,
        }


def _fake_eye_info(data, *_args, **kwargs):
    assert kwargs["csv_output_dir"] is None
    raw = np.asarray(data, dtype=float)
    return (0.5, 0.25, 1.0, 2, 4.0,
            raw.reshape(1, -1), np.ones((1, 3)), np.ones(3), raw.reshape(1, -1))


class ApplicationServiceTest(unittest.TestCase):
    def config(self):
        return application.AnalysisConfig(
            filetype="lab_csv",
            filename="fake.csv",
            osr=4,
            symbol_rate=32e9,
            modulation="NRZ",
            prbs_pattern="PRBS7",
            pattern_length=127,
            pre_cursor_ffe=1,
            total_cursor_ffe=2,
        )

    def test_legacy_mapping_adds_neutral_profile(self):
        values = self.config().to_mapping()
        values.pop("profile")
        config = application.AnalysisConfig.from_mapping(values)
        self.assertEqual(config.profile, "neutral")

    def test_fit_window_must_cover_ffe_taps(self):
        values = self.config().to_mapping()
        values["total_cursor_fit"] = 8
        values["total_cursor_ffe"] = 18
        with self.assertRaisesRegex(ValueError, "necessarily singular"):
            application.validate_fit_config(values)

    def test_analyze_has_no_cwd_side_effect_and_render_isolated(self):
        lab_data = {"data_vec": np.arange(32, dtype=float) + 1.0,
                    "time_vec": np.array([])}
        with tempfile.TemporaryDirectory() as cwd, \
                tempfile.TemporaryDirectory() as a, \
                tempfile.TemporaryDirectory() as b:
            before = Path.cwd()
            os.chdir(cwd)
            try:
                with patch.object(application, "process_input", return_value=lab_data), \
                        patch.object(application, "PulseResponseTool", FakePulseResponseTool), \
                        patch.object(application, "calc_eye_info", side_effect=_fake_eye_info), \
                        patch.object(application, "calc_central_eye_width",
                                     return_value={"width_ui": 0.75, "crossing_count": 4}):
                    result = application.analyze(self.config())
                    self.assertFalse((Path(cwd) / "txcross.csv").exists())
                    self.assertFalse((Path(cwd) / "txhist.csv").exists())
                    first = application.render_artifacts(
                        result, a, report=False, render_plots=False)
                    second = application.render_artifacts(
                        result, b, report=False, render_plots=False)
                    self.assertNotEqual(first.output_dir, second.output_dir)
                    self.assertTrue(first.txcross_csv.exists())
                    self.assertTrue(second.txhist_csv.exists())
                    self.assertFalse((Path(cwd) / "txcross.csv").exists())
            finally:
                os.chdir(before)


if __name__ == "__main__":
    unittest.main()
