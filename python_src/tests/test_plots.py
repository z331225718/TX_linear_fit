"""Focused rendering regressions for plots changed by the desktop workflow."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np


PYTHON_SRC = Path(__file__).resolve().parents[1]
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

import plots  # noqa: E402


def test_pulse_plot_covers_the_configured_cursor_window(tmp_path, monkeypatch):
    samples_per_ui = 10
    timebase = np.arange(32 * samples_per_ui, dtype=float) / samples_per_ui
    pulse = np.exp(-0.5 * ((timebase - 4.0) / 0.45) ** 2)
    sampled_timebase = np.arange(32, dtype=float)
    sampled_pulse = np.exp(-0.5 * ((sampled_timebase - 4.0) / 0.45) ** 2)
    prt = SimpleNamespace(
        symbol_rate_input=1.0,
        fit_results={
            "timebase": timebase,
            "p": pulse,
            "timebaseSampled": sampled_timebase,
            "pSampled": sampled_pulse,
            "pmax": 1.0,
            "vf": 1.0,
            "pulsePeakRatio": 1.0,
            "SNDR": 30.0,
        },
        tf_calc={"nyquist_loss": -8.0},
        sndr_const={
            "ffe": {"rlm_results": {"RLMbj": 0.977846, "RLMbs": 0.955692}}
        },
    )

    original_close = plots.plt.close
    monkeypatch.setattr(plots.plt, "close", lambda _figure: None)
    try:
        plots.plot_linear_fit_pulse(prt, outdir=tmp_path)
        figure = plots.plt.gcf()
        left, right = figure.axes[0].get_xlim()
        annotation = "\n".join(text.get_text() for text in figure.axes[0].texts)
        assert left < -4.0
        assert right > 27.0
        assert "0.9778" in annotation
        assert "0.977846" not in annotation
        assert (tmp_path / "linear_fit_pulse.png").is_file()
    finally:
        original_close(plots.plt.gcf())
