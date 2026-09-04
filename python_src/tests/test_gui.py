# -*- coding: utf-8 -*-
"""Headless tests for the Tk adapter's pure mapping and state helpers."""
from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gui  # noqa: E402


class FakeConfig:
    filetype: str
    filename: str
    symbol_rate: float
    modulation: str
    prbs_pattern: str
    pattern_length: int
    repeat_pattern_num: int
    osr: int | None
    gray_coding: str
    pre_cursor_fit: int
    total_cursor_fit: int
    pre_cursor_ffe: int
    total_cursor_ffe: int
    dfe_tap_num: int
    shift_vec: tuple[int, ...]
    profile: str

    def __init__(self, **kwargs):
        self.values = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeService:
    def __init__(self):
        self.calls = []

    def analyze(self, config):
        self.calls.append(("analyze", config))
        return SimpleNamespace(metrics={"sndr_ffe": 18.5}, osr=16, osr_info={})

    def render_artifacts(self, result, output_dir):
        artifact = SimpleNamespace(report_path=Path(output_dir) / "report.html", output_dir=output_dir)
        self.calls.append(("render_artifacts", result, output_dir, artifact))
        return artifact


def form_values(**overrides):
    values = {
        "input_file": "waveform.txt",
        "output_dir": "results",
        "filetype": "lab_txt",
        "symbol_rate": "32 GBd",
        "modulation": "PAM4",
        "prbs_pattern": "PRBS13",
        "pattern_length": "8191",
        "repeat_pattern_num": "1",
        "osr_mode": "auto",
        "osr": "16",
        "pre_cursor_fit": "4",
        "total_cursor_fit": "32",
        "pre_cursor_ffe": "4",
        "total_cursor_ffe": "18",
        "dfe_tap_num": "1",
        "profile": "neutral",
    }
    values.update(overrides)
    return values


class GuiHelpersTest(unittest.TestCase):
    def test_gui_supports_package_import(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import python_src.gui as gui; "
                    "assert gui.AnalysisConfig is not None; "
                    "assert gui._APPLICATION_IMPORT_ERROR is None"
                ),
            ],
            cwd=HERE.parent.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_symbol_rate_and_osr(self):
        self.assertEqual(gui.parse_symbol_rate("32 GBd"), 32e9)
        self.assertEqual(gui.parse_symbol_rate("53.125e9"), 53.125e9)
        self.assertIsNone(gui.resolve_osr("auto", "not-used"))
        self.assertEqual(gui.resolve_osr("manual", "12"), 12)

    def test_gui_infers_parser_and_prbs_sequence_length(self):
        self.assertEqual(gui.infer_filetype("capture.TXT"), "lab_txt")
        self.assertEqual(gui.infer_filetype("capture.csv"), "lab_csv")
        self.assertEqual(gui.prbs_pattern_length("PRBS7"), 127)
        self.assertEqual(gui.prbs_pattern_length("prbs13"), 8191)

        values = form_values(prbs_pattern="PRBS15")
        values.pop("filetype")
        values.pop("pattern_length")
        values.pop("repeat_pattern_num")
        values.pop("symbol_rate")
        normalized = gui.validate_form_values(values, check_paths=False)
        self.assertEqual(normalized["filetype"], "lab_txt")
        self.assertEqual(normalized["pattern_length"], 32767)
        self.assertEqual(normalized["repeat_pattern_num"], 1)
        self.assertEqual(normalized["symbol_rate"], 53.125e9)

    def test_parameter_mapping_and_profile(self):
        normalized = gui.validate_form_values(form_values(), check_paths=False)
        config = gui.build_analysis_config(normalized, FakeConfig)
        self.assertEqual(config.filename, "waveform.txt")
        self.assertEqual(config.symbol_rate, 32e9)
        self.assertIsNone(config.osr)
        self.assertEqual(config.pre_cursor_fit, 4)
        self.assertEqual(config.total_cursor_fit, 32)
        self.assertEqual(config.total_cursor_ffe, 18)
        self.assertEqual(config.profile, "neutral")
        self.assertEqual(config.shift_vec, (-2, -1, 1, 2))

        manual = gui.validate_form_values(
            form_values(filetype="lab_csv", osr_mode="manual", osr="8", profile="oif"),
            check_paths=False,
        )
        manual_config = gui.build_analysis_config(manual, FakeConfig)
        self.assertEqual(manual["osr"], 8)
        self.assertEqual(manual_config.profile, "oif")

    def test_validation_rejects_inconsistent_taps(self):
        with self.assertRaisesRegex(ValueError, "前游标"):
            gui.validate_form_values(
                form_values(pre_cursor_fit="7", total_cursor_fit="8", dfe_tap_num="1"),
                check_paths=False,
            )
        with self.assertRaisesRegex(ValueError, "必须手动"):
            gui.validate_form_values(
                form_values(filetype="lab_csv", osr_mode="auto"), check_paths=False
            )
        with self.assertRaisesRegex(ValueError, "总游标必须 >= FFE 总 tap"):
            gui.validate_form_values(
                form_values(total_cursor_fit="8", total_cursor_ffe="18"),
                check_paths=False,
            )

    def test_path_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.txt"
            source.write_text("0, 1\n", encoding="utf-8")
            values = form_values(input_file=str(source), output_dir=str(Path(temp) / "out"))
            normalized = gui.validate_form_values(values)
            self.assertEqual(normalized["input_file"], str(source))
            with self.assertRaisesRegex(ValueError, "不存在"):
                gui.validate_form_values(form_values(input_file=str(source) + ".missing"))

    def test_fake_service_worker_and_run_state(self):
        service = FakeService()
        adapter = gui.AnalysisGui.__new__(gui.AnalysisGui)
        adapter._service = service
        config = gui.build_analysis_config(gui.validate_form_values(form_values(), check_paths=False), FakeConfig)
        result, artifacts = adapter._worker(config, Path("results"))
        self.assertEqual(len(service.calls), 2)
        self.assertIs(config, service.calls[0][1])
        self.assertIs(result, service.calls[1][1])
        self.assertIs(artifacts, service.calls[1][3])
        self.assertFalse(gui.derive_run_state(False)["progress_active"])
        self.assertFalse(gui.derive_run_state(True)["start_enabled"])
        self.assertEqual(gui.derive_run_state(True)["close_action"], "wait")
        self.assertTrue(gui.can_start(False))
        self.assertFalse(gui.can_start(True))

    def test_rlm_labels_explain_the_two_definitions(self):
        result = SimpleNamespace(
            config=SimpleNamespace(dfe_tap_num=1),
            metrics=SimpleNamespace(
                fit_results={},
                tf_calc={},
                sndr_const={
                    "ffe": {
                        "sndr": 19.0,
                        "rlm_results": {"RLMbj": 0.91, "RLMbs": 0.88},
                    },
                    "ffe_and_dfe": {
                        "sndr": 20.0,
                        "rlm_results": {"RLMbj": 0.92, "RLMbs": 0.89},
                    },
                },
                eye_uneq=None,
                eye_eq=None,
            )
        )
        labels = [label for label, _ in gui.result_metric_items(result)]
        self.assertIn("RLM · 最小相邻间距 · FFE", labels)
        self.assertIn("RLM · IEEE 802.3bs · FFE", labels)
        self.assertIn("RLM · IEEE 802.3bs · FFE + DFE", labels)

        result.config = SimpleNamespace(dfe_tap_num=0)
        labels = [label for label, _ in gui.result_metric_items(result)]
        self.assertNotIn("RLM · IEEE 802.3bs · FFE + DFE", labels)


if __name__ == "__main__":
    unittest.main()
