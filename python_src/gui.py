# -*- coding: utf-8 -*-
"""TX linear-fit desktop workbench.

The GUI is intentionally a thin adapter around :mod:`application`: all
numeric work happens in the service layer and the Tk event loop only handles
form state, progress messages, and presentation of the stable result API.
"""
from __future__ import annotations

import dataclasses
import inspect
import math
import os
import queue
import re
import sys
import traceback
import webbrowser
from concurrent.futures import Future, ThreadPoolExecutor
from collections.abc import Mapping
from numbers import Number
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:  # Package import, for example ``import python_src.gui``.
    from .application import AnalysisConfig, analyze, render_artifacts
    _APPLICATION_IMPORT_ERROR: Exception | None = None
except ImportError:
    try:  # Direct launch: ``python python_src/gui.py``.
        from application import AnalysisConfig, analyze, render_artifacts
        _APPLICATION_IMPORT_ERROR = None
    except ImportError as exc:  # Keep pure validation helpers importable in isolation.
        AnalysisConfig = None  # type: ignore[assignment,misc]
        analyze = None  # type: ignore[assignment]
        render_artifacts = None  # type: ignore[assignment]
        _APPLICATION_IMPORT_ERROR = exc


FILE_TYPES = ("lab_txt", "lab_csv")
MODULATIONS = ("NRZ", "PAM4")
PRBS_PATTERNS = ("PRBS7", "PRBS13", "PRBS15", "PRBS31")
# PRBS31 stays available in the CLI, where callers can choose a bounded
# sequence length.  Expanding its full period is not suitable for the GUI.
GUI_PRBS_PATTERNS = ("PRBS7", "PRBS13", "PRBS15")
PRBS_PATTERN_LENGTHS = {
    "PRBS7": (1 << 7) - 1,
    "PRBS13": (1 << 13) - 1,
    "PRBS15": (1 << 15) - 1,
    "PRBS31": (1 << 31) - 1,
}
PROFILE_OPTIONS = (
    ("Neutral", "neutral"),
    ("IEEE 802.3", "ieee8023"),
    ("OIF CEI", "oif"),
)
PROFILE_DISPLAY_TO_VALUE = dict(PROFILE_OPTIONS)
PROFILE_VALUES = {value for _, value in PROFILE_OPTIONS}
DEFAULT_PRE_CURSOR_FIT = 4
DEFAULT_TOTAL_CURSOR_FIT = 32
DEFAULT_PRE_CURSOR_FFE = 4
DEFAULT_TOTAL_CURSOR_FFE = 18

_RATE_RE = re.compile(
    r"^\s*([+]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|[+]?\.\d+(?:[eE][+-]?\d+)?)"
    r"\s*([kKmMgGtT]?)(?:[bB][dD]|[bB][pP][sS]|[hH][zZ])?\s*$"
)
_RATE_MULTIPLIERS = {"": 1.0, "k": 1e3, "m": 1e6, "g": 1e9, "t": 1e12}


def parse_symbol_rate(value: Any) -> float:
    """Parse a baud rate, accepting plain numbers and friendly ``GBd`` text."""
    text = str(value).strip()
    match = _RATE_RE.fullmatch(text)
    if not match:
        raise ValueError("symbol rate 请输入数字，例如 53.125 GBd 或 53.125e9")
    number = float(match.group(1))
    rate = number * _RATE_MULTIPLIERS[match.group(2).lower()]
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("symbol rate 必须是正的有限数值")
    return rate


def _integer(value: Any, label: str, minimum: int) -> int:
    text = str(value).strip()
    try:
        number = int(text, 10)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 必须是整数") from exc
    if number < minimum:
        raise ValueError(f"{label} 必须 >= {minimum}")
    return number


def infer_filetype(filename: Any) -> str:
    """Infer the legacy parser mode from a waveform filename."""
    suffix = Path(str(filename).strip()).suffix.lower()
    if suffix == ".txt":
        return "lab_txt"
    if suffix == ".csv":
        return "lab_csv"
    raise ValueError("输入文件必须是 .txt 或 .csv")


def prbs_pattern_length(prbs_pattern: Any) -> int:
    """Return one complete sequence length for a supported PRBS pattern."""
    pattern = str(prbs_pattern).strip().upper()
    try:
        return PRBS_PATTERN_LENGTHS[pattern]
    except KeyError as exc:
        raise ValueError("PRBS 请选择 PRBS7、PRBS13、PRBS15 或 PRBS31") from exc


def resolve_osr(mode: Any, value: Any) -> int | None:
    """Return a manual OSR or ``None`` for automatic inference."""
    selected = str(mode).strip().lower()
    if selected in {"auto", "automatic", "自动"}:
        return None
    if selected not in {"manual", "手动"}:
        raise ValueError("OSR 模式必须是自动或手动")
    return _integer(value, "OSR", 2)


def profile_value(value: Any) -> str:
    """Map a display label to its protocol-neutral report semantic value."""
    text = str(value).strip()
    if text in PROFILE_DISPLAY_TO_VALUE:
        return PROFILE_DISPLAY_TO_VALUE[text]
    if text in PROFILE_VALUES:
        return text
    raise ValueError("profile 请选择 Neutral、IEEE 802.3 或 OIF CEI")


def _value(values: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in values:
            return values[name]
    return default


def validate_form_values(values: Mapping[str, Any], *, check_paths: bool = True) -> dict[str, Any]:
    """Validate and normalize form values without creating a Tk root.

    ``check_paths=False`` is useful for unit tests and for callers that have
    already validated filesystem state.  The returned dictionary contains the
    canonical names consumed by :func:`build_analysis_config`.
    """
    input_text = str(_value(values, "input_file", "filename", "input_path")).strip()
    output_text = str(_value(values, "output_dir", "output_path")).strip()
    if not input_text:
        raise ValueError("请选择输入文件")
    if not output_text:
        raise ValueError("请选择输出目录")

    input_path = Path(input_text).expanduser()
    output_path = Path(output_text).expanduser()
    if check_paths and not input_path.is_file():
        raise ValueError(f"输入文件不存在：{input_path}")
    if check_paths and output_path.exists() and not output_path.is_dir():
        raise ValueError(f"输出路径不是目录：{output_path}")

    filetype = str(_value(values, "filetype", "file_type", default="")).strip()
    if not filetype:
        filetype = infer_filetype(input_path)
    if filetype not in FILE_TYPES:
        raise ValueError("file type 请选择 lab_txt 或 lab_csv")

    modulation = str(_value(values, "modulation", default="PAM4")).strip().upper()
    if modulation not in MODULATIONS:
        raise ValueError("modulation 请选择 NRZ 或 PAM4")
    prbs_pattern = str(_value(values, "prbs_pattern", "prbs", default="PRBS13")).strip().upper()
    if prbs_pattern not in PRBS_PATTERNS:
        raise ValueError("PRBS 请选择 PRBS7、PRBS13、PRBS15 或 PRBS31")

    pattern_length_value = _value(values, "pattern_length", default="")
    pattern_length = (
        prbs_pattern_length(prbs_pattern)
        if str(pattern_length_value).strip() == ""
        else _integer(pattern_length_value, "pattern length", 1)
    )
    repeat_pattern_num = _integer(
        _value(values, "repeat_pattern_num", "repeat", default=1), "repeat", 1
    )
    symbol_rate = parse_symbol_rate(
        _value(values, "symbol_rate", "symbol_rate_baud", default="53.125 GBd")
    )
    osr = resolve_osr(
        _value(values, "osr_mode", default="auto"),
        _value(values, "osr", "manual_osr", default="16"),
    )
    if filetype == "lab_csv" and osr is None:
        raise ValueError("lab_csv 只有电压数据，必须手动指定 OSR")

    pre_cursor_fit = _integer(
        _value(values, "pre_cursor_fit", default=DEFAULT_PRE_CURSOR_FIT),
        "pulse fit 前游标", 0
    )
    total_cursor_fit = _integer(
        _value(values, "total_cursor_fit", default=DEFAULT_TOTAL_CURSOR_FIT),
        "pulse fit 总游标", 1
    )
    pre_cursor_ffe = _integer(
        _value(values, "pre_cursor_ffe", "ffe_pre", default=DEFAULT_PRE_CURSOR_FFE),
        "FFE 前游标", 0
    )
    total_cursor_ffe = _integer(
        _value(values, "total_cursor_ffe", "ffe_total", default=DEFAULT_TOTAL_CURSOR_FFE),
        "FFE 总 tap", 1
    )
    dfe_tap_num = _integer(
        _value(values, "dfe_tap_num", "dfe_taps", default=1), "DFE tap", 0
    )
    if pre_cursor_fit + dfe_tap_num >= total_cursor_fit:
        raise ValueError("pulse fit 需要满足：前游标 + DFE tap < 总游标")
    if pre_cursor_ffe >= total_cursor_ffe:
        raise ValueError("FFE 需要满足：前游标 < 总 tap")
    if total_cursor_fit < total_cursor_ffe:
        raise ValueError(
            "Pulse fit 总游标必须 >= FFE 总 tap；否则 FFE 拟合矩阵必然奇异"
        )

    return {
        "input_file": str(input_path),
        "output_dir": str(output_path),
        "filetype": filetype,
        "symbol_rate": symbol_rate,
        "modulation": modulation,
        "prbs_pattern": prbs_pattern,
        "pattern_length": pattern_length,
        "repeat_pattern_num": repeat_pattern_num,
        "osr": osr,
        "osr_mode": "manual" if osr is not None else "auto",
        "pre_cursor_fit": pre_cursor_fit,
        "total_cursor_fit": total_cursor_fit,
        "pre_cursor_ffe": pre_cursor_ffe,
        "total_cursor_ffe": total_cursor_ffe,
        "dfe_tap_num": dfe_tap_num,
        "profile": profile_value(_value(values, "profile", default="neutral")),
    }


_CONFIG_ALIASES = {
    "filetype": ("filetype", "file_type"),
    "filename": ("filename", "input_file", "input_path"),
    "symbol_rate": ("symbol_rate", "symbol_rate_baud"),
    "pattern_length": ("pattern_length",),
    "repeat_pattern_num": ("repeat_pattern_num", "repeat"),
    "prbs_pattern": ("prbs_pattern", "prbs"),
    "pre_cursor_fit": ("pre_cursor_fit", "pulse_fit_pre"),
    "total_cursor_fit": ("total_cursor_fit", "pulse_fit_total"),
    "pre_cursor_ffe": ("pre_cursor_ffe", "ffe_pre", "pre_ffe_taps"),
    "total_cursor_ffe": ("total_cursor_ffe", "ffe_total", "total_ffe_taps"),
    "dfe_tap_num": ("dfe_tap_num", "dfe_taps"),
    "profile": ("profile", "protocol_profile"),
}


def _config_field_names(config_cls: Any) -> set[str] | None:
    try:
        return {field.name for field in dataclasses.fields(config_cls)}
    except (TypeError, AttributeError):
        pass
    annotations = getattr(config_cls, "__annotations__", None)
    if annotations:
        return set(annotations)
    try:
        return {
            name
            for name, parameter in inspect.signature(config_cls).parameters.items()
            if name != "self" and parameter.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
    except (TypeError, ValueError):
        return None


def build_analysis_config(
    values: Mapping[str, Any], config_cls: Any | None = None
) -> Any:
    """Map normalized form values to the current application config contract."""
    config_cls = config_cls or AnalysisConfig
    if config_cls is None:
        detail = f": {_APPLICATION_IMPORT_ERROR}" if _APPLICATION_IMPORT_ERROR else ""
        raise RuntimeError(f"无法导入 application service{detail}")
    normalized = validate_form_values(values, check_paths=False)
    canonical = {
        "filetype": normalized["filetype"],
        "filename": normalized["input_file"],
        "symbol_rate": normalized["symbol_rate"],
        "modulation": normalized["modulation"],
        "prbs_pattern": normalized["prbs_pattern"],
        "pattern_length": normalized["pattern_length"],
        "repeat_pattern_num": normalized["repeat_pattern_num"],
        "osr": normalized["osr"],
        "gray_coding": "on",
        "pre_cursor_fit": normalized["pre_cursor_fit"],
        "total_cursor_fit": normalized["total_cursor_fit"],
        "pre_cursor_ffe": normalized["pre_cursor_ffe"],
        "total_cursor_ffe": normalized["total_cursor_ffe"],
        "dfe_tap_num": normalized["dfe_tap_num"],
        "shift_vec": (-2, -1, 1, 2),
        "profile": normalized["profile"],
    }
    fields = _config_field_names(config_cls)
    if fields is None:
        # A **kwargs-compatible fake service or future config can use the
        # canonical names without coupling this adapter to its implementation.
        return config_cls(**canonical)

    kwargs: dict[str, Any] = {}
    for canonical_name, item in canonical.items():
        for candidate in _CONFIG_ALIASES.get(canonical_name, (canonical_name,)):
            if candidate in fields:
                kwargs[candidate] = item
                break
    return config_cls(**kwargs)


def derive_run_state(running: bool) -> dict[str, Any]:
    """Pure UI state used by the Tk adapter and headless tests."""
    active = bool(running)
    return {
        "running": active,
        "start_enabled": not active,
        "controls_enabled": not active,
        "progress_active": active,
        "close_action": "wait" if active else "close",
    }


def can_start(running: bool) -> bool:
    return not bool(running)


def _format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isnan(number):
            return "NaN"
        if math.isinf(number):
            return "+Inf" if number > 0 else "-Inf"
        if number == 0:
            return "0"
        if abs(number) >= 1000 or abs(number) < 0.001:
            return f"{number:.5g}"
        return f"{number:.6g}"
    return str(value)


_METRIC_LABELS = {
    "sndr": "SNDR · Fit",
    "sndr_ffe": "SNDR · FFE",
    "sndr_ffe_and_dfe": "SNDR · FFE + DFE",
    "snr_isi": "SNR · ISI",
    "rlmbj": "RLM · 最小相邻间距",
    "rlmbs": "RLM · IEEE 802.3bs",
    "rlmbj_ffe": "RLM · 最小相邻间距 · FFE",
    "rlmbs_ffe": "RLM · IEEE 802.3bs · FFE",
    "rlmbj_dfe": "RLM · 最小相邻间距 · FFE + DFE",
    "rlmbs_dfe": "RLM · IEEE 802.3bs · FFE + DFE",
    "nyquist_loss": "TF @ Nyquist",
    "bw_3db": "带宽 · 3 dB",
    "eye_width_ui": "眼宽 · UI",
    "eye_width_ps": "眼宽 · ps",
}


def _metric_label(key: Any) -> str:
    text = str(key)
    normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return _METRIC_LABELS.get(normalized, text.replace("_", " "))


def result_metric_items(result: Any) -> list[tuple[str, str]]:
    """Read only stable scalar fields from ``AnalysisResult.metrics``.

    Older service revisions expose a flat mapping here; the current service
    exposes ``AnalysisMetrics`` with named fit/SNDR/TF/eye snapshots.  Both
    shapes are stable service data and neither requires touching the engine.
    """
    metrics = getattr(result, "metrics", None)
    items: list[tuple[str, str]] = []

    def add_mapping(mapping: Any, prefix: str = "") -> None:
        if not isinstance(mapping, Mapping):
            return
        for key, value in mapping.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if normalized in {"sndr_ffe", "sndr_ffe_and_dfe"}:
                continue
            if isinstance(value, Mapping):
                add_mapping(value, f"{prefix}{key} · ")
            elif isinstance(value, (str, bytes, Number)) or value is None:
                label = f"{prefix}{_metric_label(key)}" if prefix else _metric_label(key)
                items.append((label, _format_metric(value)))

    if isinstance(metrics, Mapping):
        add_mapping(metrics)
        return items
    if metrics is None:
        return items

    add_mapping(getattr(metrics, "fit_results", None))
    add_mapping(getattr(metrics, "tf_calc", None))
    sndr = getattr(metrics, "sndr_const", None)
    config = getattr(result, "config", None)
    if isinstance(config, Mapping):
        dfe_tap_num = config.get("dfe_tap_num")
    else:
        dfe_tap_num = getattr(config, "dfe_tap_num", None)
    show_dfe = dfe_tap_num is None or int(dfe_tap_num) > 0
    branches = [("ffe", "FFE")]
    if show_dfe:
        branches.append(("ffe_and_dfe", "FFE + DFE"))
    for branch_name, branch_label in branches:
        branch = sndr.get(branch_name) if isinstance(sndr, Mapping) else None
        if not isinstance(branch, Mapping):
            continue
        rlm = branch.get("rlm_results")
        if isinstance(rlm, Mapping):
            rlm_labels = {
                "RLMbj": "RLM · 最小相邻间距",
                "RLMbs": "RLM · IEEE 802.3bs",
            }
            for key, metric_label in rlm_labels.items():
                if key in rlm:
                    items.append((f"{metric_label} · {branch_label}", _format_metric(rlm[key])))

    for name, label in (("eye_uneq", "眼宽 · 未均衡"), ("eye_eq", "眼宽 · FFE")):
        eye = getattr(metrics, name, None)
        if eye is not None:
            for field_name, suffix in (("central_width_ui", "UI"), ("central_width_ps", "ps")):
                value = getattr(eye, field_name, None)
                if value is not None:
                    items.append((f"{label} ({suffix})", _format_metric(value)))
    return items


def result_osr_items(result: Any) -> list[tuple[str, str]]:
    """Read the stable OSR fields exposed by ``AnalysisResult``."""
    items: list[tuple[str, str]] = []
    osr = getattr(result, "osr", None)
    if osr is None:
        osr = getattr(result, "osr_value", None)
    if osr is not None:
        items.append(("分析 OSR", _format_metric(osr)))

    info = getattr(result, "osr_info", None)
    if info is None:
        info = getattr(result, "osr_meta", None)
    if info is None:
        info = getattr(result, "analysis_meta", None)
    if isinstance(info, Mapping):
        labels = {
            "osr_source": "OSR 来源",
            "native_samples_per_ui": "Native samples/UI",
            "effective_samples_per_ui": "Effective samples/UI",
            "missing_sample_fraction": "缺失样本比例",
            "sample_interval_s": "采样间隔 (s)",
        }
        for key, label in labels.items():
            if key in info:
                value = info[key]
                if key == "missing_sample_fraction":
                    try:
                        value = f"{float(value):.2%}"
                    except (TypeError, ValueError):
                        value = _format_metric(value)
                else:
                    value = _format_metric(value)
                items.append((label, value))
    return items


class _AutoScrollbar(ttk.Scrollbar):
    """Hide a grid-managed scrollbar while its full range is visible."""

    def set(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(first, last)


class AnalysisGui(tk.Tk):
    """Single-window Tk front end for the shared analysis service."""

    BG = "#edf0ee"
    SURFACE = "#ffffff"
    RAIL = "#f6f8f7"
    PANEL = SURFACE
    PANEL_ALT = "#f1f4f2"
    BORDER = "#d3dbd6"
    BORDER_STRONG = "#b7c3bd"
    TEXT = "#1b2520"
    MUTED = "#66736c"
    ACCENT = "#0b7a63"
    ACCENT_DARK = "#075f4d"
    ACCENT_SOFT = "#e4f1ec"
    OK = "#21834e"
    WARN = "#a96b16"
    ERROR = "#b53c3c"

    def __init__(self, service: Any | None = None) -> None:
        super().__init__()
        if service is None:
            if AnalysisConfig is None or analyze is None or render_artifacts is None:
                detail = f": {_APPLICATION_IMPORT_ERROR}" if _APPLICATION_IMPORT_ERROR else ""
                raise RuntimeError(f"无法导入 application service{detail}")
            service = _ServiceAdapter(analyze, render_artifacts)
        self._service = service
        self._events: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tx-linear-fit")
        self._future: Future[Any] | None = None
        self._running = False
        self._poll_id: str | None = None
        self._run_widgets: list[tk.Widget] = []
        self._report_path: Path | None = None
        self._closed = False

        self._configure_window()
        self._create_variables()
        self._build_layout()
        self._update_osr_state()
        self._set_running(False)
        self._poll_id = self.after(100, self._poll_events)

    def _configure_window(self) -> None:
        self.title("TX Linear Fit · 工程分析工作台")
        self.geometry("1220x800")
        self.minsize(1040, 700)
        self.configure(background=self.BG)
        if os.name == "nt":
            try:
                scaling = float(self.tk.call("tk", "scaling"))
                if scaling < 1.1:
                    self.tk.call("tk", "scaling", 1.25)
            except (tk.TclError, ValueError):
                pass
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self._font_body = ("Segoe UI Variable Text", 9)
        self._font_body_bold = ("Segoe UI Variable Text", 9, "bold")
        self._font_title = ("Segoe UI Variable Display", 18, "bold")
        self._font_section = ("Segoe UI Variable Text", 10, "bold")
        self._font_metric = ("Segoe UI Variable Display", 17, "bold")
        self._font_mono = ("Cascadia Mono", 9)

        style.configure("App.TFrame", background=self.BG)
        style.configure("Header.TFrame", background=self.SURFACE)
        style.configure("Rail.TFrame", background=self.RAIL)
        style.configure("Surface.TFrame", background=self.SURFACE)
        style.configure("Panel.TFrame", background=self.SURFACE)
        style.configure("TLabel", background=self.SURFACE, foreground=self.TEXT,
                        font=self._font_body)
        style.configure("Rail.TLabel", background=self.RAIL, foreground=self.TEXT,
                        font=self._font_body)
        style.configure("Muted.TLabel", background=self.RAIL, foreground=self.MUTED,
                        font=self._font_body)
        style.configure("SurfaceMuted.TLabel", background=self.SURFACE, foreground=self.MUTED,
                        font=self._font_body)
        style.configure("Title.TLabel", background=self.SURFACE, foreground=self.TEXT,
                        font=self._font_title)
        style.configure("Subtitle.TLabel", background=self.SURFACE, foreground=self.MUTED,
                        font=self._font_body)
        style.configure("SectionTitle.TLabel", background=self.RAIL, foreground=self.TEXT,
                        font=self._font_section)
        style.configure("WorkspaceTitle.TLabel", background=self.SURFACE, foreground=self.TEXT,
                        font=self._font_section)
        style.configure("Metric.TLabel", background=self.SURFACE, foreground=self.ACCENT,
                        font=self._font_metric)
        style.configure("Source.TLabel", background=self.ACCENT_SOFT, foreground=self.ACCENT_DARK,
                        font=self._font_body_bold, padding=(8, 4))
        style.configure("TSeparator", background=self.BORDER)

        field_options = {
            "fieldbackground": self.SURFACE,
            "foreground": self.TEXT,
            "insertcolor": self.ACCENT,
            "bordercolor": self.BORDER_STRONG,
            "lightcolor": self.BORDER_STRONG,
            "darkcolor": self.BORDER_STRONG,
            "padding": (7, 5),
            "font": self._font_body,
        }
        style.configure("TEntry", **field_options)
        style.configure("TCombobox", **field_options, background=self.SURFACE,
                        arrowcolor=self.MUTED)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.SURFACE), ("disabled", self.PANEL_ALT)],
            foreground=[("readonly", self.TEXT), ("disabled", self.MUTED)],
            bordercolor=[("focus", self.ACCENT)],
        )
        style.configure("TSpinbox", **field_options, background=self.SURFACE,
                        arrowcolor=self.MUTED, arrowsize=12)
        style.map("TEntry", bordercolor=[("focus", self.ACCENT)])
        style.map("TSpinbox", bordercolor=[("focus", self.ACCENT)],
                  fieldbackground=[("disabled", self.PANEL_ALT)])

        style.configure("TButton", background=self.SURFACE, foreground=self.TEXT,
                        bordercolor=self.BORDER_STRONG, lightcolor=self.BORDER_STRONG,
                        darkcolor=self.BORDER_STRONG, font=self._font_body_bold,
                        padding=(11, 6))
        style.map(
            "TButton",
            background=[("active", self.PANEL_ALT), ("pressed", self.BORDER),
                        ("disabled", self.PANEL_ALT)],
            foreground=[("disabled", "#9aa39e")],
            bordercolor=[("focus", self.ACCENT)],
        )
        style.configure("Accent.TButton", background=self.ACCENT, foreground="#ffffff",
                        bordercolor=self.ACCENT, lightcolor=self.ACCENT,
                        darkcolor=self.ACCENT_DARK, font=("Segoe UI Variable Text", 10, "bold"),
                        padding=(14, 9))
        style.map(
            "Accent.TButton",
            background=[("active", self.ACCENT_DARK), ("pressed", "#054b3d"),
                        ("disabled", "#9eb9af")],
            foreground=[("disabled", "#eef4f1")],
        )
        style.configure("Rail.TCheckbutton", background=self.RAIL, foreground=self.TEXT,
                        font=self._font_body)
        style.map("Rail.TCheckbutton", background=[("active", self.RAIL)],
                  foreground=[("disabled", "#9aa39e")])
        style.layout(
            "Segment.TRadiobutton",
            [("Radiobutton.border", {"sticky": "nswe", "children": [
                ("Radiobutton.padding", {"sticky": "nswe", "children": [
                    ("Radiobutton.label", {"sticky": "nswe"})
                ]})
            ]})],
        )
        style.configure("Segment.TRadiobutton", background=self.SURFACE, foreground=self.MUTED,
                        bordercolor=self.BORDER_STRONG, lightcolor=self.BORDER_STRONG,
                        darkcolor=self.BORDER_STRONG, font=self._font_body_bold,
                        padding=(14, 7), anchor="center")
        style.map(
            "Segment.TRadiobutton",
            background=[("selected", self.ACCENT_SOFT), ("active", self.PANEL_ALT),
                        ("disabled", self.PANEL_ALT)],
            foreground=[("selected", self.ACCENT_DARK), ("disabled", "#9aa39e")],
            bordercolor=[("selected", self.ACCENT), ("focus", self.ACCENT)],
        )
        style.configure("Treeview", background=self.SURFACE, fieldbackground=self.SURFACE,
                        foreground=self.TEXT, rowheight=29, borderwidth=0,
                        relief="flat", font=self._font_body)
        style.configure("Treeview.Heading", background=self.PANEL_ALT, foreground=self.MUTED,
                        bordercolor=self.BORDER, relief="flat", font=self._font_body_bold,
                        padding=(8, 6))
        style.map("Treeview", background=[("selected", self.ACCENT_SOFT)],
                  foreground=[("selected", self.ACCENT_DARK)])
        style.configure("Horizontal.TProgressbar", troughcolor=self.ACCENT_SOFT,
                        background=self.ACCENT, borderwidth=0, lightcolor=self.ACCENT,
                        darkcolor=self.ACCENT)
        style.layout(
            "Clean.Vertical.TScrollbar",
            [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
            ]})],
        )
        style.configure("Clean.Vertical.TScrollbar", troughcolor=self.PANEL_ALT,
                        background=self.BORDER_STRONG, borderwidth=0, gripcount=0,
                        width=9)
        style.map("Clean.Vertical.TScrollbar",
                  background=[("active", self.MUTED), ("pressed", self.ACCENT)])

    def _create_variables(self) -> None:
        default_output = Path.cwd() / "outputs" / "gui_run"
        self.input_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value=str(default_output))
        self._filetype = "lab_txt"
        self.symbol_rate_var = tk.StringVar(value="53.125 GBd")
        self.modulation_var = tk.StringVar(value="PAM4")
        self.prbs_var = tk.StringVar(value="PRBS13")
        self.osr_mode_var = tk.StringVar(value="auto")
        self.osr_var = tk.StringVar(value="16")
        self.pre_fit_var = tk.StringVar(value=str(DEFAULT_PRE_CURSOR_FIT))
        self.total_fit_var = tk.StringVar(value=str(DEFAULT_TOTAL_CURSOR_FIT))
        self.pre_ffe_var = tk.StringVar(value=str(DEFAULT_PRE_CURSOR_FFE))
        self.total_ffe_var = tk.StringVar(value=str(DEFAULT_TOTAL_CURSOR_FFE))
        self.dfe_var = tk.StringVar(value="1")
        self.auto_open_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪")
        self.status_detail_var = tk.StringVar(value="请选择输入文件并确认分析参数")
        self.osr_hint_var = tk.StringVar(value="自动模式：从输入文件时间轴推断整数 OSR")
        self.result_osr_var = tk.StringVar(value="OSR  —")
        self.result_source_var = tk.StringVar(value="等待分析")
        self.report_var = tk.StringVar(value="尚未生成报告")

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(24, 14, 24, 13))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)
        mark = tk.Frame(header, width=4, height=42, background=self.ACCENT)
        mark.grid(row=0, column=0, sticky="nsw", padx=(0, 13))
        mark.grid_propagate(False)
        brand = ttk.Frame(header, style="Header.TFrame")
        brand.grid(row=0, column=1, sticky="w")
        ttk.Label(brand, text="TX LINEAR FIT", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(brand, text="Pulse response · Linear fit · Eye analysis",
                  style="Subtitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        status = ttk.Frame(header, style="Header.TFrame")
        status.grid(row=0, column=2, sticky="e")
        status.columnconfigure(0, minsize=250)
        status.rowconfigure(2, minsize=6)
        status_head = ttk.Frame(status, style="Header.TFrame")
        status_head.grid(row=0, column=0, sticky="e")
        self._status_dot = tk.Label(status_head, text="●", bg=self.SURFACE, fg=self.MUTED,
                                    font=("Segoe UI", 9))
        self._status_dot.grid(row=0, column=0, padx=(0, 8))
        self._status_label = tk.Label(status_head, textvariable=self.status_var, bg=self.SURFACE,
                                      fg=self.TEXT, font=self._font_section)
        self._status_label.grid(row=0, column=1, sticky="e")
        tk.Label(status, textvariable=self.status_detail_var, bg=self.SURFACE, fg=self.MUTED,
                 font=self._font_body).grid(row=1, column=0, sticky="e", pady=(2, 0))
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=250,
                                        style="Horizontal.TProgressbar")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(5, 0))

        ttk.Separator(self, orient="horizontal").grid(row=1, column=0, sticky="ew")

        main = ttk.Frame(self, style="App.TFrame")
        main.grid(row=2, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0, minsize=420)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style="Rail.TFrame", padding=(22, 18, 14, 16))
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="分析设置", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 13)
        )
        form_canvas = tk.Canvas(left, background=self.RAIL, highlightthickness=0,
                                borderwidth=0)
        form_canvas.grid(row=1, column=0, sticky="nsew")
        form_scroll = ttk.Scrollbar(left, orient="vertical", command=form_canvas.yview,
                                    style="Clean.Vertical.TScrollbar")
        form_scroll.grid(row=1, column=1, sticky="ns", padx=(8, 0))
        form_canvas.configure(yscrollcommand=form_scroll.set)
        form = ttk.Frame(form_canvas, style="Rail.TFrame")
        form_window = form_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _event: form_canvas.configure(
            scrollregion=form_canvas.bbox("all")
        ))
        form_canvas.bind("<Configure>", lambda event: form_canvas.itemconfigure(
            form_window, width=event.width
        ))
        form_canvas.bind("<Enter>", lambda _event: form_canvas.bind_all(
            "<MouseWheel>", lambda event: form_canvas.yview_scroll(-int(event.delta / 120), "units")
        ))
        form_canvas.bind("<Leave>", lambda _event: form_canvas.unbind_all("<MouseWheel>"))
        self._form_canvas = form_canvas
        self._build_paths(form)
        self._build_signal(form)
        self._build_osr(form)
        self._build_fit(form)
        self._build_actions(left)

        ttk.Separator(main, orient="vertical").grid(row=0, column=1, sticky="ns")

        right = ttk.Frame(main, style="Surface.TFrame", padding=(24, 19, 24, 17))
        right.grid(row=0, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self._build_summary(right)
        self._build_log(right)
        self._build_report(right)

    def _section(self, parent: ttk.Frame, title: str, row: int) -> ttk.Frame:
        shell = ttk.Frame(parent, style="Rail.TFrame")
        shell.grid(row=row, column=0, sticky="ew", padx=(0, 4), pady=(0, 14))
        shell.columnconfigure(0, weight=1)
        ttk.Label(shell, text=title, style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7)
        )
        ttk.Separator(shell, orient="horizontal").grid(row=1, column=0, sticky="ew",
                                                        pady=(0, 8))
        section = ttk.Frame(shell, style="Rail.TFrame")
        section.grid(row=2, column=0, sticky="ew")
        section.columnconfigure(1, weight=1)
        return section

    def _label(self, parent: ttk.Widget, text: str, row: int, column: int = 0) -> None:
        ttk.Label(parent, text=text, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w", padx=(0, 9), pady=2
        )

    def _entry_row(
        self,
        parent: ttk.Widget,
        row: int,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        button = ttk.Button(parent, text="选择", width=6, command=command)
        button.grid(row=row, column=2, sticky="e", padx=(7, 0), pady=2)
        self._run_widgets.extend((entry, button))

    def _build_paths(self, parent: ttk.Frame) -> None:
        section = self._section(parent, "数据源", 0)
        self._label(section, "输入文件", 0)
        self._entry_row(section, 0, self.input_var, self._choose_input)
        self._label(section, "输出目录", 1)
        self._entry_row(section, 1, self.output_var, self._choose_output)

    def _build_signal(self, parent: ttk.Frame) -> None:
        section = self._section(parent, "信号定义", 1)
        section.columnconfigure(0, weight=1)
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text="符号速率 (GBd / baud)", style="Muted.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(2, 3)
        )
        rate = ttk.Entry(section, textvariable=self.symbol_rate_var, width=17)
        rate.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(section, text="调制格式", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=(2, 3)
        )
        ttk.Label(section, text="码型", style="Muted.TLabel").grid(
            row=2, column=1, sticky="w", padx=(6, 0), pady=(2, 3)
        )
        modulation = ttk.Combobox(section, textvariable=self.modulation_var,
                                  values=MODULATIONS, state="readonly", width=14)
        modulation.grid(row=3, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        self._run_widgets.extend((rate, modulation))
        prbs = ttk.Combobox(section, textvariable=self.prbs_var, values=GUI_PRBS_PATTERNS,
                            state="readonly", width=14)
        prbs.grid(row=3, column=1, sticky="ew", padx=(6, 0), pady=(0, 6))
        self._run_widgets.append(prbs)

    def _build_osr(self, parent: ttk.Frame) -> None:
        section = self._section(parent, "采样设置", 2)
        self._label(section, "模式", 0)
        radios = ttk.Frame(section, style="Rail.TFrame")
        radios.grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        radios.columnconfigure((0, 1), weight=1)
        auto = ttk.Radiobutton(radios, text="自动", value="auto", variable=self.osr_mode_var,
                               command=self._update_osr_state, style="Segment.TRadiobutton")
        auto.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        manual = ttk.Radiobutton(radios, text="手动", value="manual", variable=self.osr_mode_var,
                                  command=self._update_osr_state, style="Segment.TRadiobutton")
        manual.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self._run_widgets.extend((auto, manual))
        self._label(section, "手动 OSR", 1)
        self.osr_entry = ttk.Spinbox(section, textvariable=self.osr_var, from_=2, to=4096,
                                     width=15, state="disabled")
        self.osr_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self._run_widgets.append(self.osr_entry)
        ttk.Label(section, textvariable=self.osr_hint_var, style="Muted.TLabel",
                  wraplength=330).grid(row=2, column=1, columnspan=2, sticky="w", pady=(2, 0))

    def _build_fit(self, parent: ttk.Frame) -> None:
        section = self._section(parent, "拟合与均衡", 3)
        section.columnconfigure(0, weight=1)
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text="Pulse fit 前游标", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(2, 3)
        )
        ttk.Label(section, text="Pulse fit 总游标", style="Muted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(6, 0), pady=(2, 3)
        )
        pre_fit = ttk.Spinbox(section, textvariable=self.pre_fit_var, from_=0, to=100, width=10)
        pre_fit.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        total_fit = ttk.Spinbox(section, textvariable=self.total_fit_var, from_=1, to=200, width=10)
        total_fit.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(0, 6))
        self._run_widgets.extend((pre_fit, total_fit))
        ttk.Label(section, text="FFE 前游标", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=(2, 3)
        )
        ttk.Label(section, text="FFE 总 tap", style="Muted.TLabel").grid(
            row=2, column=1, sticky="w", padx=(6, 0), pady=(2, 3)
        )
        pre_ffe = ttk.Spinbox(section, textvariable=self.pre_ffe_var, from_=0, to=100, width=10)
        pre_ffe.grid(row=3, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        total_ffe = ttk.Spinbox(section, textvariable=self.total_ffe_var, from_=1, to=200, width=10)
        total_ffe.grid(row=3, column=1, sticky="ew", padx=(6, 0), pady=(0, 6))
        self._run_widgets.extend((pre_ffe, total_ffe))
        ttk.Label(section, text="DFE tap", style="Muted.TLabel").grid(
            row=4, column=0, sticky="w", padx=(0, 6), pady=(2, 3)
        )
        ttk.Label(section, text="默认 FFE：18 taps", style="Muted.TLabel").grid(
            row=4, column=1, sticky="w", padx=(6, 0), pady=(2, 3)
        )
        dfe = ttk.Spinbox(section, textvariable=self.dfe_var, from_=0, to=100, width=10)
        dfe.grid(row=5, column=0, sticky="ew", padx=(0, 6))
        self._run_widgets.append(dfe)

    def _build_actions(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent, style="Rail.TFrame")
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Separator(actions, orient="horizontal").grid(row=0, column=0, sticky="ew",
                                                          pady=(0, 12))
        self.run_button = ttk.Button(actions, text="开始分析", style="Accent.TButton",
                                     command=self._start_analysis)
        self.run_button.grid(row=1, column=0, sticky="ew", pady=(0, 9))
        self._run_widgets.append(self.run_button)
        auto_open = ttk.Checkbutton(actions, text="完成后自动打开 HTML 报告",
                                    variable=self.auto_open_var, style="Rail.TCheckbutton")
        auto_open.grid(row=2, column=0, sticky="w")
        self._run_widgets.append(auto_open)

    def _build_summary(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Surface.TFrame")
        section.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        section.columnconfigure(0, weight=1)
        head = ttk.Frame(section, style="Surface.TFrame")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="结果摘要", style="WorkspaceTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(head, textvariable=self.result_osr_var, style="Metric.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(head, textvariable=self.result_source_var, style="Source.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e"
        )
        ttk.Separator(section, orient="horizontal").grid(row=1, column=0, sticky="ew",
                                                          pady=(0, 10))
        tree_frame = ttk.Frame(section, style="Surface.TFrame")
        tree_frame.grid(row=2, column=0, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        self.kpi_tree = ttk.Treeview(tree_frame, columns=("metric", "value"), show="headings",
                                     height=8, selectmode="none")
        self.kpi_tree.heading("metric", text="指标")
        self.kpi_tree.heading("value", text="结果")
        self.kpi_tree.column("metric", width=340, minwidth=260, anchor="w", stretch=True)
        self.kpi_tree.column("value", width=180, anchor="e", stretch=False)
        self.kpi_tree.grid(row=0, column=0, sticky="ew")
        scrollbar = _AutoScrollbar(tree_frame, orient="vertical", command=self.kpi_tree.yview,
                                   style="Clean.Vertical.TScrollbar")
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(5, 0))
        self.kpi_tree.configure(yscrollcommand=scrollbar.set)
        self.kpi_tree.tag_configure("even", background=self.SURFACE, foreground=self.TEXT)
        self.kpi_tree.tag_configure("odd", background=self.PANEL_ALT, foreground=self.TEXT)
        self._empty_result = ttk.Label(tree_frame, text="尚无分析结果",
                                       style="SurfaceMuted.TLabel")
        self._empty_result.place(relx=0.5, rely=0.58, anchor="center")

    def _build_log(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Surface.TFrame")
        section.grid(row=1, column=0, sticky="nsew", pady=(0, 16))
        section.columnconfigure(0, weight=1)
        section.rowconfigure(2, weight=1)
        ttk.Label(section, text="运行日志", style="WorkspaceTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Separator(section, orient="horizontal").grid(row=1, column=0, sticky="ew",
                                                          pady=(0, 10))
        log_frame = ttk.Frame(section, style="Surface.TFrame")
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, wrap="word", state="disabled",
                                background="#f4f6f5", foreground="#2f3a35",
                                insertbackground=self.ACCENT, relief="flat", borderwidth=0,
                                highlightthickness=1, highlightbackground=self.BORDER,
                                highlightcolor=self.ACCENT, padx=11, pady=9,
                                spacing1=1, spacing3=2, font=self._font_mono)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = _AutoScrollbar(log_frame, orient="vertical", command=self.log_text.yview,
                                    style="Clean.Vertical.TScrollbar")
        log_scroll.grid(row=0, column=1, sticky="ns", padx=(5, 0))
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def _build_report(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Surface.TFrame")
        section.grid(row=2, column=0, sticky="ew")
        section.columnconfigure(1, weight=1)
        ttk.Separator(section, orient="horizontal").grid(row=0, column=0, columnspan=3,
                                                          sticky="ew", pady=(0, 12))
        ttk.Label(section, text="HTML 报告", style="SurfaceMuted.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 10)
        )
        report_entry = ttk.Entry(section, textvariable=self.report_var, state="readonly")
        report_entry.grid(row=1, column=1, sticky="ew")
        self.open_button = ttk.Button(section, text="打开报告", command=self._open_report,
                                      state="disabled", width=10)
        self.open_button.grid(row=1, column=2, sticky="e", padx=(8, 0))

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="选择输入波形文件",
            filetypes=(("Lab text", "*.txt"), ("Lab CSV", "*.csv"), ("All files", "*.*")),
        )
        if path:
            try:
                filetype = infer_filetype(path)
            except ValueError as exc:
                messagebox.showerror("不支持的输入文件", str(exc), parent=self)
                return
            self.input_var.set(path)
            self._filetype = filetype
            self._update_osr_state()

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="选择报告输出目录", mustexist=False)
        if path:
            self.output_var.set(path)

    def _update_osr_state(self) -> None:
        manual = self.osr_mode_var.get() == "manual"
        self.osr_entry.configure(state="normal" if manual and not self._running else "disabled")
        try:
            filetype = infer_filetype(self.input_var.get())
        except ValueError:
            filetype = self._filetype
        if filetype == "lab_csv" and not manual:
            self.osr_hint_var.set("lab_csv 不含时间轴，请切换为手动并指定 OSR")
        elif manual:
            self.osr_hint_var.set("手动模式：使用指定的 samples/UI，不推断时间轴")
        else:
            self.osr_hint_var.set("自动模式：从输入文件时间轴推断整数 OSR")

    def _collect_form_values(self) -> dict[str, Any]:
        input_file = self.input_var.get()
        filetype = infer_filetype(input_file) if input_file.strip() else self._filetype
        return {
            "input_file": input_file,
            "output_dir": self.output_var.get(),
            "filetype": filetype,
            "symbol_rate": self.symbol_rate_var.get(),
            "modulation": self.modulation_var.get(),
            "prbs_pattern": self.prbs_var.get(),
            "pattern_length": prbs_pattern_length(self.prbs_var.get()),
            "repeat_pattern_num": 1,
            "osr_mode": self.osr_mode_var.get(),
            "osr": self.osr_var.get(),
            "pre_cursor_fit": self.pre_fit_var.get(),
            "total_cursor_fit": self.total_fit_var.get(),
            "pre_cursor_ffe": self.pre_ffe_var.get(),
            "total_cursor_ffe": self.total_ffe_var.get(),
            "dfe_tap_num": self.dfe_var.get(),
            "profile": "neutral",
        }

    def _start_analysis(self) -> None:
        if not can_start(self._running):
            return
        try:
            values = validate_form_values(self._collect_form_values())
            output_dir = Path(values["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            config = build_analysis_config(values)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            self._set_status("配置有误", "请修正参数后重试", self.ERROR)
            self._append_log(f"[错误] {exc}")
            messagebox.showerror("无法开始分析", str(exc), parent=self)
            return

        self._clear_results()
        self._append_log(f"输入：{values['input_file']}")
        self._append_log(f"输出：{output_dir}")
        self._append_log(
            f"配置：{values['modulation']} / {values['prbs_pattern']} / "
            f"{values['symbol_rate']:.6g} baud / "
            f"OSR={'auto' if values['osr'] is None else values['osr']}"
        )
        self._set_running(True)
        self._set_status("分析中", "数值计算与报告生成可能需要一些时间", self.ACCENT)
        self._events.put(("phase", "开始数值分析…"))
        self._future = self._executor.submit(self._worker, config, output_dir)
        self._future.add_done_callback(self._future_done)

    def _worker(self, config: Any, output_dir: Path) -> tuple[Any, Any]:
        """The worker deliberately delegates only to the two service calls."""
        result = self._service.analyze(config)
        artifacts = self._service.render_artifacts(result, output_dir)
        return result, artifacts

    def _future_done(self, future: Future[Any]) -> None:
        try:
            result, artifacts = future.result()
        except Exception as exc:  # Keep traceback off the Tk thread, but log it there.
            self._events.put(("error", exc, traceback.format_exc()))
        else:
            self._events.put(("done", result, artifacts))

    def _poll_events(self) -> None:
        if self._closed:
            return
        try:
            while True:
                event = self._events.get_nowait()
                kind = event[0]
                if kind == "phase":
                    self._append_log(f"[进行中] {event[1]}")
                elif kind == "done":
                    self._set_running(False)
                    self._present_result(event[1], event[2])
                elif kind == "error":
                    self._set_running(False)
                    self._set_status("分析失败", "请查看日志并检查输入与参数", self.ERROR)
                    self._append_log(f"[错误] {event[1]}")
                    self._append_log(event[2])
                    messagebox.showerror("分析失败", str(event[1]), parent=self)
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll_events)

    def _set_running(self, running: bool) -> None:
        self._running = bool(running)
        state = derive_run_state(self._running)
        for widget in self._run_widgets:
            try:
                if state["controls_enabled"]:
                    widget.state(["!disabled"])
                else:
                    widget.state(["disabled"])
            except (AttributeError, tk.TclError):
                try:
                    widget.configure(state="normal" if state["controls_enabled"] else "disabled")
                except tk.TclError:
                    pass
        self._update_osr_state()
        if self._running:
            self.progress.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()
        self.run_button.configure(text="正在分析..." if self._running else "开始分析")

    def _clear_results(self) -> None:
        for item in self.kpi_tree.get_children(""):
            self.kpi_tree.delete(item)
        self._empty_result.place(relx=0.5, rely=0.58, anchor="center")
        self.result_osr_var.set("OSR  —")
        self.result_source_var.set("计算中")
        self.report_var.set("尚未生成报告")
        self.open_button.configure(state="disabled")
        self._report_path = None

    def _present_result(self, result: Any, artifacts: Any) -> None:
        metric_items = result_metric_items(result)
        osr_items = result_osr_items(result)
        self._empty_result.place_forget()
        for label, value in osr_items:
            if label == "分析 OSR":
                self.result_osr_var.set(f"OSR  {value}")
            elif label == "OSR 来源":
                self.result_source_var.set(value)
        for label, value in osr_items:
            if label != "分析 OSR":
                metric_items.insert(0, (label, value))
        if not metric_items:
            metric_items.append(("指标", "service 未返回可显示的标量指标"))
        for index, (label, value) in enumerate(metric_items):
            self.kpi_tree.insert(
                "", "end", values=(label, value), tags=("even" if index % 2 == 0 else "odd",)
            )

        report = getattr(artifacts, "report_path", None)
        if report is None:
            report = getattr(artifacts, "report", None)
        output_dir = getattr(artifacts, "output_dir", None)
        if report:
            self._report_path = Path(report).expanduser().resolve()
            self.report_var.set(str(self._report_path))
            self.open_button.configure(state="normal")
            self._append_log(f"报告：{self._report_path}")
        if output_dir:
            self._append_log(f"产物目录：{Path(output_dir).expanduser()}")
        self._set_status("分析完成", "结果与 HTML 报告已就绪", self.OK)
        if self.auto_open_var.get() and self._report_path:
            self._open_report(silent=True)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", str(text).rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, status: str, detail: str, color: str | None = None) -> None:
        self.status_var.set(status)
        self.status_detail_var.set(detail)
        if color:
            self._status_dot.configure(fg=color)
            self._status_label.configure(fg=color if color != self.ACCENT else self.TEXT)

    def _open_report(self, *, silent: bool = False) -> None:
        path = self._report_path
        if path is None or not path.exists():
            message = "当前没有可打开的报告"
            self._append_log(f"[提示] {message}")
            if not silent:
                messagebox.showinfo("报告", message, parent=self)
            return
        try:
            accepted = webbrowser.open_new_tab(path.as_uri())
        except Exception as exc:
            accepted = False
            self._append_log(f"[错误] 打开报告失败：{exc}")
        if not accepted and not silent:
            messagebox.showwarning("报告", "默认浏览器未接受报告地址", parent=self)

    def _on_close(self) -> None:
        if self._running:
            messagebox.showinfo(
                "分析仍在运行",
                "分析任务正在运行。为避免产生不完整结果，请等待任务完成后再关闭窗口。",
                parent=self,
            )
            return
        self._closed = True
        if self._poll_id:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        self._executor.shutdown(wait=True)
        self.destroy()


class _ServiceAdapter:
    def __init__(self, analyze_fn: Callable[..., Any], render_fn: Callable[..., Any]) -> None:
        self.analyze = analyze_fn
        self.render_artifacts = render_fn


def main() -> None:
    """Launch the desktop workbench with ``python python_src/gui.py``."""
    try:
        app = AnalysisGui()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    app.mainloop()


if __name__ == "__main__":
    main()
