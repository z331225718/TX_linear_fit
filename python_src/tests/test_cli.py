"""CLI adapter tests that keep browser and service behavior at the boundary."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


PYTHON_SRC = Path(__file__).resolve().parents[1]
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

import run_tx_linear_fit as cli


def _args(output_dir: Path, *extra: str) -> list[str]:
    return [
        "--filename", "input.txt",
        "--symbol_rate", "32e9",
        "--modulation", "PAM4",
        "--prbs_pattern", "PRBS13",
        "--pattern_length", "8191",
        "--pre_cursor_ffe", "4",
        "--total_cursor_ffe", "18",
        "--output-dir", str(output_dir),
        *extra,
    ]


def _patch_run(monkeypatch, tmp_path: Path):
    result = object()
    calls = []

    def fake_render(value, output_dir, *, report, render_plots):
        calls.append((value, Path(output_dir), report, render_plots))
        path = Path(output_dir).resolve() / "tx_linear_fit_report.html"
        return SimpleNamespace(report=path if report else None)

    browser = Mock(return_value=True)
    monkeypatch.setattr(cli, "analyze", Mock(return_value=result))
    monkeypatch.setattr(cli, "print_summary", Mock())
    monkeypatch.setattr(cli, "render_artifacts", fake_render)
    monkeypatch.setattr(cli.webbrowser, "open_new_tab", browser)
    return result, calls, browser


def test_default_generates_and_opens_report(monkeypatch, tmp_path):
    result, calls, browser = _patch_run(monkeypatch, tmp_path)
    cli.main(_args(tmp_path))
    assert calls == [(result, tmp_path, True, True)]
    browser.assert_called_once_with(
        (tmp_path / "tx_linear_fit_report.html").resolve().as_uri())


def test_no_open_keeps_report_without_browser(monkeypatch, tmp_path):
    result, calls, browser = _patch_run(monkeypatch, tmp_path)
    cli.main(_args(tmp_path, "--no-open"))
    assert calls == [(result, tmp_path, True, True)]
    browser.assert_not_called()


def test_no_report_and_no_plots_reach_renderer(monkeypatch, tmp_path):
    result, calls, browser = _patch_run(monkeypatch, tmp_path)
    cli.main(_args(tmp_path, "--no-report", "--plots", "0"))
    assert calls == [(result, tmp_path, False, False)]
    browser.assert_not_called()
