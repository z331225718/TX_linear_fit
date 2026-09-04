# -*- coding: utf-8 -*-
"""Shared application service for TX linear-fit analysis.

The service deliberately keeps the numerical engine private.  ``analyze``
only parses input and computes metrics; file-producing work belongs to
``render_artifacts``.  This makes the same analysis usable by the CLI and the
desktop front end without changing the established numerical path.
"""
from __future__ import annotations

import inspect
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import numpy as np

try:  # Support both ``python_src.application`` and script-style imports.
    from .eye_info import calc_central_eye_width, calc_eye_info
    from .matlab_compat import colon, interp1_linear
    from .process_input import process_input
    from .pulse_response_tool import PulseResponseTool
except ImportError:  # pragma: no cover - exercised by direct CLI execution
    # The legacy modules use absolute sibling imports.  Add their directory
    # only for package-style imports so those modules remain unchanged.
    _MODULE_DIR = str(Path(__file__).resolve().parent)
    if _MODULE_DIR not in sys.path:
        sys.path.insert(0, _MODULE_DIR)
    try:
        from .eye_info import calc_central_eye_width, calc_eye_info
        from .matlab_compat import colon, interp1_linear
        from .process_input import process_input
        from .pulse_response_tool import PulseResponseTool
    except ImportError:
        # Direct execution puts python_src on sys.path already.
        from eye_info import calc_central_eye_width, calc_eye_info
        from matlab_compat import colon, interp1_linear
        from process_input import process_input
        from pulse_response_tool import PulseResponseTool


_PROFILES = ("neutral", "ieee8023", "oif")
_DEFAULT_SHIFT_VEC = (-2, -1, 1, 2)


def _shift_tuple(value: Any) -> tuple[int, ...]:
    if isinstance(value, str):
        value = value.split(",")
    return tuple(int(item) for item in value)


@dataclass(frozen=True)
class AnalysisConfig:
    """Numerical inputs for one analysis run.

    Output paths, browser preferences, and terminal/UI options are purposely
    not part of this dataclass.  ``profile`` is currently a report label only.
    """

    filetype: str
    filename: str
    symbol_rate: float
    modulation: str
    prbs_pattern: str
    pattern_length: int
    pre_cursor_ffe: int
    total_cursor_ffe: int
    osr: int | None = None
    repeat_pattern_num: int = 1
    gray_coding: str = "on"
    pre_cursor_fit: int = 2
    total_cursor_fit: int = 8
    dfe_tap_num: int = 1
    shift_vec: tuple[int, ...] = _DEFAULT_SHIFT_VEC
    profile: str = "neutral"

    def __post_init__(self) -> None:
        object.__setattr__(self, "shift_vec", _shift_tuple(self.shift_vec))
        if self.profile not in _PROFILES:
            raise ValueError(
                "profile must be one of: " + ", ".join(_PROFILES)
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | "AnalysisConfig") -> "AnalysisConfig":
        """Build a config from the legacy dict accepted by the old CLI."""
        if isinstance(values, cls):
            return values
        values = dict(values)
        return cls(
            filetype=values["filetype"],
            filename=str(values["filename"]),
            symbol_rate=float(values["symbol_rate"]),
            modulation=values["modulation"],
            prbs_pattern=values["prbs_pattern"],
            pattern_length=int(values["pattern_length"]),
            pre_cursor_ffe=int(values["pre_cursor_ffe"]),
            total_cursor_ffe=int(values["total_cursor_ffe"]),
            osr=None if values.get("osr") is None else int(values["osr"]),
            repeat_pattern_num=int(values.get("repeat_pattern_num", 1)),
            gray_coding=values.get("gray_coding", "on"),
            pre_cursor_fit=int(values.get("pre_cursor_fit", 2)),
            total_cursor_fit=int(values.get("total_cursor_fit", 8)),
            dfe_tap_num=int(values.get("dfe_tap_num", 1)),
            shift_vec=_shift_tuple(values.get("shift_vec", _DEFAULT_SHIFT_VEC)),
            profile=values.get("profile", "neutral"),
        )

    def to_mapping(self) -> dict[str, Any]:
        values = asdict(self)
        values["shift_vec"] = tuple(self.shift_vec)
        return values


@dataclass(frozen=True)
class EyeMetrics:
    """Stable scalar eye metrics with tuple compatibility for legacy callers."""

    eye_x_opening: float
    min_eye_y_opening: float
    max_eye_y_opening: float
    eye_mid_index: int
    eye_y_opening_ratio: float
    central_width_ui: float
    central_width_ps: float
    crossing_count: int
    _raw: tuple[Any, ...] = field(default_factory=tuple, repr=False, compare=False)

    @classmethod
    def from_result(
        cls,
        raw: tuple[Any, ...] | list[Any],
        central: Mapping[str, Any],
        symbol_rate: float,
    ) -> "EyeMetrics":
        values = tuple(raw)
        width_ui = float(central.get("width_ui", float("nan")))
        return cls(
            eye_x_opening=float(values[0]),
            min_eye_y_opening=float(values[1]),
            max_eye_y_opening=float(values[2]),
            eye_mid_index=int(values[3]),
            eye_y_opening_ratio=float(values[4]),
            central_width_ui=width_ui,
            central_width_ps=width_ui / float(symbol_rate) * 1e12,
            crossing_count=int(central.get("crossing_count", 0)),
            _raw=values,
        )

    @property
    def x_opening(self) -> float:
        return self.eye_x_opening

    @property
    def min_y(self) -> float:
        return self.min_eye_y_opening

    @property
    def max_y(self) -> float:
        return self.max_eye_y_opening

    @property
    def ratio(self) -> float:
        return self.eye_y_opening_ratio

    @property
    def width_ui(self) -> float:
        return self.central_width_ui

    @property
    def central_width(self) -> float:
        """Short alias accepted by report/GUI adapters."""
        return self.central_width_ui

    @property
    def width_ps(self) -> float:
        return self.central_width_ps

    @property
    def txcross(self) -> np.ndarray | None:
        return self._raw[6] if len(self._raw) > 6 else None

    @property
    def txhist(self) -> np.ndarray | None:
        return self._raw[7] if len(self._raw) > 7 else None

    def as_tuple(self) -> tuple[Any, ...]:
        return self._raw or (
            self.eye_x_opening,
            self.min_eye_y_opening,
            self.max_eye_y_opening,
            self.eye_mid_index,
            self.eye_y_opening_ratio,
        )

    def __getitem__(self, index: int | slice) -> Any:
        return self.as_tuple()[index]

    def __iter__(self):
        return iter(self.as_tuple())

    def __len__(self) -> int:
        return len(self.as_tuple())

    def to_mapping(self) -> dict[str, Any]:
        return {
            "eye_x_opening": self.eye_x_opening,
            "min_eye_y_opening": self.min_eye_y_opening,
            "max_eye_y_opening": self.max_eye_y_opening,
            "eye_mid_index": self.eye_mid_index,
            "eye_y_opening_ratio": self.eye_y_opening_ratio,
            "central_width_ui": self.central_width_ui,
            "central_width_ps": self.central_width_ps,
            "crossing_count": self.crossing_count,
        }


@dataclass(frozen=True)
class AnalysisMetrics:
    """A stable, renderer/frontend-facing snapshot of one engine run."""

    osr: int
    symbol_rate: float
    analysis_meta: Mapping[str, Any]
    fit_results: Mapping[str, Any]
    sndr_const: Mapping[str, Any]
    tf_calc: Mapping[str, Any]
    eye_uneq: EyeMetrics
    eye_eq: EyeMetrics

    @property
    def fit(self) -> Mapping[str, Any]:
        return self.fit_results

    @property
    def sndr(self) -> Mapping[str, Any]:
        return self.sndr_const

    @property
    def tf(self) -> Mapping[str, Any]:
        return self.tf_calc

    @property
    def eye_unequalized(self) -> EyeMetrics:
        return self.eye_uneq

    @property
    def eye_equalized(self) -> EyeMetrics:
        return self.eye_eq

    @property
    def eye_metrics(self) -> Mapping[str, EyeMetrics]:
        return {"uneq": self.eye_uneq, "eq": self.eye_eq}

    @property
    def central_eye_widths(self) -> Mapping[str, EyeMetrics]:
        return self.eye_metrics


@dataclass(frozen=True)
class AnalysisResult:
    """Analysis output consumed by CLI/GUI; the numerical engine is private."""

    config: AnalysisConfig
    metrics: AnalysisMetrics
    _engine: Any = field(repr=False, compare=False)

    @property
    def osr(self) -> int:
        return self.metrics.osr

    @property
    def symbol_rate(self) -> float:
        return self.metrics.symbol_rate

    @property
    def analysis_meta(self) -> Mapping[str, Any]:
        return self.metrics.analysis_meta

    @property
    def osr_info(self) -> Mapping[str, Any]:
        return self.metrics.analysis_meta

    @property
    def fit_results(self) -> Mapping[str, Any]:
        return self.metrics.fit_results

    @property
    def sndr_const(self) -> Mapping[str, Any]:
        return self.metrics.sndr_const

    @property
    def tf_calc(self) -> Mapping[str, Any]:
        return self.metrics.tf_calc

    @property
    def eye_uneq(self) -> EyeMetrics:
        return self.metrics.eye_uneq

    @property
    def eye_eq(self) -> EyeMetrics:
        return self.metrics.eye_eq

    @property
    def eye_metrics(self) -> Mapping[str, EyeMetrics]:
        return self.metrics.eye_metrics

    @property
    def central_eye_widths(self) -> Mapping[str, EyeMetrics]:
        return self.metrics.central_eye_widths


@dataclass(frozen=True)
class ArtifactPaths:
    """Paths produced by ``render_artifacts`` for one explicit output dir."""

    output_dir: Path
    results_dir: Path
    txcross_csv: Path
    txhist_csv: Path
    images: Mapping[str, Path]
    report: Path | None = None

    @property
    def txcross(self) -> Path:
        return self.txcross_csv

    @property
    def txhist(self) -> Path:
        return self.txhist_csv

    @property
    def report_path(self) -> Path | None:
        """Alias used by the GUI adapter and older callers."""
        return self.report

    @property
    def plots(self) -> Mapping[str, Path]:
        return self.images


def resolve_osr(
    time_vec: Any,
    data_size: int,
    symbol_rate: float,
    requested_osr: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """Resolve analysis OSR and return it with time-axis diagnostics."""
    if not np.isfinite(symbol_rate) or symbol_rate <= 0:
        raise ValueError("symbol_rate must be a positive finite baud rate")

    t = np.asarray(time_vec, dtype=np.float64).ravel()
    meta: dict[str, Any] = {"osr_source": "manual", "has_time_axis": bool(t.size)}
    if t.size:
        if t.size != int(data_size):
            raise ValueError("time and voltage vectors must have the same length")
        if t.size < 2 or not np.isfinite(t).all():
            raise ValueError("time axis must contain at least two finite values")
        dt = np.diff(t)
        if not np.all(dt > 0):
            raise ValueError("time axis must be strictly increasing")

        nominal_dt = float(np.median(dt))
        native_sps = 1.0 / (symbol_rate * nominal_dt)
        effective_sps = (t.size - 1) / ((t[-1] - t[0]) * symbol_rate)
        interval_steps = np.maximum(1, np.rint(dt / nominal_dt).astype(int))
        nominal_intervals = int(interval_steps.sum())
        gap_fraction = (
            (nominal_intervals - len(dt)) / nominal_intervals
            if nominal_intervals
            else 0.0
        )
        meta.update(
            {
                "sample_interval_s": nominal_dt,
                "native_samples_per_ui": float(native_sps),
                "effective_samples_per_ui": float(effective_sps),
                "missing_sample_fraction": float(max(0.0, gap_fraction)),
            }
        )

    if requested_osr is not None:
        value = float(requested_osr)
        if not np.isfinite(value) or not value.is_integer() or value < 2:
            raise ValueError("osr must be an integer >= 2")
        return int(value), meta

    if not t.size:
        raise ValueError("osr is required for voltage-only input (no time axis)")

    native_osr = int(np.floor(meta["native_samples_per_ui"] + 0.5))
    effective_osr = int(np.floor(meta["effective_samples_per_ui"] + 0.5))
    relative_error = abs(meta["native_samples_per_ui"] - native_osr) / meta[
        "native_samples_per_ui"
    ]
    if native_osr < 2:
        raise ValueError(
            "time axis provides fewer than 2 samples/UI; specify "
            "--osr only if intentional resampling is acceptable"
        )
    if native_osr != effective_osr or relative_error > 0.10:
        raise ValueError(
            "unable to infer one reliable integer osr from the time axis "
            f'(nominal={meta["native_samples_per_ui"]:.3f}, '
            f'effective={meta["effective_samples_per_ui"]:.3f}); specify --osr'
        )
    meta["osr_source"] = "auto"
    return native_osr, meta


def validate_fit_config(cfg: Mapping[str, Any] | AnalysisConfig) -> None:
    values = cfg.to_mapping() if isinstance(cfg, AnalysisConfig) else cfg
    pre_fit = int(values["pre_cursor_fit"])
    total_fit = int(values["total_cursor_fit"])
    pre_ffe = int(values["pre_cursor_ffe"])
    total_ffe = int(values["total_cursor_ffe"])
    dfe_taps = int(values["dfe_tap_num"])
    if pre_fit < 0 or total_fit <= 0 or pre_fit + dfe_taps >= total_fit:
        raise ValueError(
            "require 0 <= pre_cursor_fit and "
            "pre_cursor_fit + dfe_tap_num < total_cursor_fit"
        )
    if pre_ffe < 0 or total_ffe <= pre_ffe:
        raise ValueError("require 0 <= pre_cursor_ffe < total_cursor_ffe")
    if total_fit < total_ffe:
        raise ValueError(
            "require total_cursor_fit >= total_cursor_ffe; otherwise the "
            "FFE normal-equation matrix is necessarily singular"
        )
    if dfe_taps < 0:
        raise ValueError("dfe_tap_num must be >= 0")


def _snapshot(value: Any) -> Any:
    """Copy engine values so metrics remain a stable post-analysis snapshot."""
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, dict):
        return {key: _snapshot(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_snapshot(item) for item in value)
    return value


def _eye_metrics(data: np.ndarray, prt: PulseResponseTool) -> EyeMetrics:
    sample_period = 1.0 / (prt.symbol_rate_input * prt.osr_input)
    tbaud = 2.0 * prt.osr_input * sample_period
    raw = calc_eye_info(
        data,
        prt.osr_input,
        tbaud,
        100,
        None,
        None,
        None,
        csv_output_dir=None,
    )
    central = calc_central_eye_width(data, prt.osr_input, settle_ui=100)
    return EyeMetrics.from_result(raw, central, prt.symbol_rate_input)


def analyze(config: AnalysisConfig | Mapping[str, Any]) -> AnalysisResult:
    """Run the numerical analysis without creating files or changing CWD."""
    cfg = AnalysisConfig.from_mapping(config)
    validate_fit_config(cfg)

    lab_data = process_input(cfg.filetype, cfg.filename)
    data_vec = np.asarray(lab_data["data_vec"], dtype=np.float64)
    time_vec_raw = np.asarray(lab_data["time_vec"], dtype=np.float64).ravel()
    if data_vec.size == 0:
        raise ValueError("input contains no readable voltage samples")
    osr, analysis_meta = resolve_osr(
        time_vec_raw, data_vec.size, cfg.symbol_rate, cfg.osr
    )

    if time_vec_raw.size == 0:
        data_vec_interp = np.tile(data_vec, cfg.repeat_pattern_num)
    else:
        time_vec = time_vec_raw - time_vec_raw[0]
        time_vec_interp = colon(
            0.0, 1.0 / cfg.symbol_rate / osr, time_vec[-1]
        )
        data_vec_interp = interp1_linear(
            time_vec, -1.0 * data_vec, time_vec_interp
        )
        data_vec_interp = np.tile(data_vec_interp, cfg.repeat_pattern_num)

    prt = PulseResponseTool(osr, cfg.symbol_rate)
    prt.analysis_meta = analysis_meta
    prt.config_input_stream_f(data_vec_interp)
    prt.config_decision_stream_f(
        modulation=cfg.modulation,
        prbs_pattern=cfg.prbs_pattern,
        pattern_length=cfg.pattern_length,
        gray_coding=cfg.gray_coding,
    )
    prt.config_linear_fit_pulse_f(
        pre_cursor_fit=cfg.pre_cursor_fit,
        pre_cursor_ffe=cfg.pre_cursor_ffe,
        total_cursor_fit=cfg.total_cursor_fit,
        total_cursor_ffe=cfg.total_cursor_ffe,
        dfe_tap_num=cfg.dfe_tap_num,
    )
    prt.apply_linear_fit_pulse_f(cfg.shift_vec)
    prt.calc_constellation_sndr_f()
    prt.calc_tf_from_linear_fit_data_f()

    eye_uneq = _eye_metrics(prt.stream_input_interp, prt)
    eye_eq = _eye_metrics(prt.sndr_const["ffe"]["re_interleaved_signal"], prt)
    metrics = AnalysisMetrics(
        osr=osr,
        symbol_rate=float(cfg.symbol_rate),
        analysis_meta=_snapshot(analysis_meta),
        fit_results=_snapshot(prt.fit_results),
        sndr_const=_snapshot(prt.sndr_const),
        tf_calc=_snapshot(prt.tf_calc),
        eye_uneq=eye_uneq,
        eye_eq=eye_eq,
    )
    result = AnalysisResult(config=cfg, metrics=metrics, _engine=prt)
    # Compatibility plotting helpers can recover the precomputed metrics.
    prt._analysis_result = result
    return result


def _write_eye_csv(result: AnalysisResult, output_dir: Path) -> tuple[Path, Path]:
    """Persist the equalized eye's legacy CSV payload without recalculation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = result.metrics.eye_eq.as_tuple()
    txcross = np.asarray(raw[6])
    txhist = np.asarray(raw[7])
    txcross_path = output_dir / "txcross.csv"
    txhist_path = output_dir / "txhist.csv"
    np.savetxt(txcross_path, txcross, fmt="%.17g", delimiter=",")
    np.savetxt(txhist_path, txhist.reshape(1, -1), fmt="%.17g", delimiter=",")
    return txcross_path, txhist_path


def _write_report(result: AnalysisResult, path: Path, plots_dir: Path) -> Path:
    from report import write_html_report

    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "out": str(path),
        "plots_dir": str(plots_dir),
    }
    # The report remains usable with both the legacy and metrics-aware API.
    params = inspect.signature(write_html_report).parameters
    if "metrics" in params:
        kwargs["metrics"] = result.metrics
    elif "analysis_metrics" in params:
        kwargs["analysis_metrics"] = result.metrics
    if "central_eye_widths" in params:
        kwargs["central_eye_widths"] = (result.eye_uneq, result.eye_eq)
    if "central_eye_uneq" in params:
        kwargs["central_eye_uneq"] = result.eye_uneq
    if "central_eye_eq" in params:
        kwargs["central_eye_eq"] = result.eye_eq
    if "analysis_result" in params:
        kwargs["analysis_result"] = result

    write_html_report(
        result._engine,
        result.eye_uneq,
        result.eye_eq,
        result.config.to_mapping(),
        **kwargs,
    )
    return path


def _render_artifacts(
    result: AnalysisResult,
    output_dir: str | os.PathLike[str],
    *,
    report: bool = True,
    render_plots: bool = True,
) -> ArtifactPaths:
    if not isinstance(result, AnalysisResult):
        raise TypeError("result must be an AnalysisResult")
    root = Path(output_dir).expanduser().resolve()
    plots_dir = root / "results"
    root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    txcross_path, txhist_path = _write_eye_csv(result, root)
    image_paths: dict[str, Path] = {
        "linear_fit_error": plots_dir / "linear_fit_error.png",
        "constellation_hist": plots_dir / "constellation_hist.png",
        "eye_uneq": plots_dir / "eye_Unequalized.png",
        "eye_eq": plots_dir / "eye_Equalized.png",
        "ffe_coeff": plots_dir / "ffe_coeff.png",
        "ffe_resp": plots_dir / "ffe_resp.png",
        "tf": plots_dir / "tf.png",
        "linear_fit_pulse": plots_dir / "linear_fit_pulse.png",
        "summary": plots_dir / "tx_summary.png",
    }

    if render_plots:
        try:
            from .plots import (
                plot_aggregate,
                plot_constellation_hist,
                plot_eye_diagram,
                plot_ffe_coeff,
                plot_ffe_resp,
                plot_linear_fit_error,
                plot_linear_fit_pulse,
                plot_tf,
            )
        except ImportError:  # pragma: no cover - direct script-style import
            from plots import (
                plot_aggregate,
                plot_constellation_hist,
                plot_eye_diagram,
                plot_ffe_coeff,
                plot_ffe_resp,
                plot_linear_fit_error,
                plot_linear_fit_pulse,
                plot_tf,
            )
        engine = result._engine
        out = str(plots_dir)
        plot_linear_fit_error(engine, outdir=out)
        plot_constellation_hist(engine, outdir=out)
        plot_eye_diagram(
            engine.stream_input_interp,
            "Unequalized Eye Diagram",
            engine,
            outdir=out,
            eye_metrics=result.eye_uneq,
            central_metrics=result.eye_uneq,
        )
        plot_eye_diagram(
            engine.sndr_const["ffe"]["re_interleaved_signal"],
            "Equalized Eye Diagram",
            engine,
            outdir=out,
            eye_metrics=result.eye_eq,
            central_metrics=result.eye_eq,
        )
        plot_ffe_coeff(engine, outdir=out)
        plot_ffe_resp(engine, outdir=out)
        plot_tf(engine, outdir=out)
        plot_linear_fit_pulse(engine, outdir=out)
        plot_aggregate(
            [str(image_paths[name]) for name in image_paths if name != "summary"],
            2,
            4,
            str(image_paths["summary"]),
        )

    report_path = None
    if report:
        report_path = _write_report(result, root / "tx_linear_fit_report.html", plots_dir)
    return ArtifactPaths(
        output_dir=root,
        results_dir=plots_dir,
        txcross_csv=txcross_path,
        txhist_csv=txhist_path,
        images=image_paths,
        report=report_path,
    )


def render_artifacts(
    result: AnalysisResult,
    output_dir: str | os.PathLike[str],
    *,
    report: bool = True,
    render_plots: bool = True,
) -> ArtifactPaths:
    """Write requested PNG/CSV/HTML artifacts into ``output_dir`` only."""
    return _render_artifacts(
        result, output_dir, report=report, render_plots=render_plots)
