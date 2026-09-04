# -*- coding: utf-8 -*-
"""Command-line adapter for the shared TX linear-fit application service."""
from __future__ import annotations

import argparse
import os
import shutil
import webbrowser
from pathlib import Path
from typing import Any, Mapping

import numpy as np

try:  # Support direct execution and ``python_src`` package imports.
    from .application import (
        AnalysisConfig,
        AnalysisResult,
        analyze,
        render_artifacts,
        resolve_osr,
        validate_fit_config,
    )
except ImportError:  # pragma: no cover - direct ``python python_src/...`` path
    from application import (
        AnalysisConfig,
        AnalysisResult,
        analyze,
        render_artifacts,
        resolve_osr,
        validate_fit_config,
    )


def make_plots(
    prt: Any,
    eye_uneq: Any = None,
    eye_eq: Any = None,
    outdir: str | os.PathLike[str] = "results",
) -> None:
    """Compatibility plotting helper using metrics computed by ``analyze``."""
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

    result = getattr(prt, "_analysis_result", None)
    if result is not None:
        if eye_uneq is None:
            eye_uneq = result.eye_uneq
        if eye_eq is None:
            eye_eq = result.eye_eq
        central_uneq = result.eye_uneq
        central_eq = result.eye_eq
    else:
        central_uneq = eye_uneq
        central_eq = eye_eq
    if eye_uneq is None or eye_eq is None:
        raise ValueError("make_plots requires precomputed eye metrics")

    out = str(outdir)
    Path(out).mkdir(parents=True, exist_ok=True)
    plot_linear_fit_error(prt, outdir=out)
    plot_constellation_hist(prt, outdir=out)
    plot_eye_diagram(
        prt.stream_input_interp,
        "Unequalized Eye Diagram",
        prt,
        outdir=out,
        eye_metrics=eye_uneq,
        central_metrics=central_uneq,
    )
    plot_eye_diagram(
        prt.sndr_const["ffe"]["re_interleaved_signal"],
        "Equalized Eye Diagram",
        prt,
        outdir=out,
        eye_metrics=eye_eq,
        central_metrics=central_eq,
    )
    plot_ffe_coeff(prt, outdir=out)
    plot_ffe_resp(prt, outdir=out)
    plot_tf(prt, outdir=out)
    plot_linear_fit_pulse(prt, outdir=out)
    plot_aggregate(
        [
            os.path.join(out, "linear_fit_error.png"),
            os.path.join(out, "constellation_hist.png"),
            os.path.join(out, "eye_Unequalized.png"),
            os.path.join(out, "eye_Equalized.png"),
            os.path.join(out, "ffe_coeff.png"),
            os.path.join(out, "ffe_resp.png"),
            os.path.join(out, "tf.png"),
            os.path.join(out, "linear_fit_pulse.png"),
        ],
        2,
        4,
        os.path.join(out, "tx_summary.png"),
    )


def run_tx_linear_fit(
    cfg: AnalysisConfig | Mapping[str, Any], plots: bool = False
) -> tuple[Any, Any, Any]:
    """Legacy tuple-returning adapter retained for verification scripts."""
    result = analyze(cfg)
    if plots:
        # The old helper rendered into CWD/results; preserve that opt-in only.
        render_artifacts(result, Path.cwd(), report=False, render_plots=True)
    return result._engine, result.eye_uneq.as_tuple(), result.eye_eq.as_tuple()


def _print_result_summary(result: AnalysisResult) -> None:
    metrics = result.metrics
    fr = metrics.fit_results
    sndr = metrics.sndr_const
    tf = metrics.tf_calc
    print("====== TX linear fit summary ======")
    meta = metrics.analysis_meta
    print("osr                   :", metrics.osr,
          "(" + meta.get("osr_source", "manual") + ")")
    if meta.get("has_time_axis"):
        print(
            "input samples/UI      : nominal={:.4f}, effective={:.4f}, gaps={:.2%}".format(
                meta["native_samples_per_ui"],
                meta["effective_samples_per_ui"],
                meta["missing_sample_fraction"],
            )
        )
    print("alignment_shift      :", fr["alignment_shift"])
    print("firNum               :", np.array2string(fr["firNum"], precision=9))
    print("firNumNorm           :", np.array2string(fr["firNumNorm"], precision=9))
    if result._engine.fit_spec["t_dfe_taps"]:
        print("firNumDFE            :", np.array2string(fr["firNumDFE"], precision=9))
        print("firNumDFENorm        :", np.array2string(fr["firNumDFENorm"], precision=9))
        print("DFEtapWeight         :", np.array2string(fr["DFEtapWeight"], precision=9))
    print("vf                   :", fr["vf"])
    print("pmax                 :", fr["pmax"])
    print("pulsePeakRatio       :", fr["pulsePeakRatio"])
    print("eRms                 :", fr["eRms"])
    print("eRmsRatio            :", fr["eRmsRatio"])
    print("SNDR                 :", fr["SNDR"])
    print("SNR_ISI              :", fr["SNR_ISI"])
    print("SNDR ffe             :", sndr["ffe"]["sndr"])
    if result._engine.fit_spec["t_dfe_taps"]:
        print("SNDR ffe_and_dfe     :", sndr["ffe_and_dfe"]["sndr"])
    print(
        "RLM min-adj / 802.3bs (ffe):",
        sndr["ffe"]["rlm_results"]["RLMbj"],
        sndr["ffe"]["rlm_results"]["RLMbs"],
    )
    if result._engine.fit_spec["t_dfe_taps"]:
        print(
            "RLM min-adj / 802.3bs (dfe):",
            sndr["ffe_and_dfe"]["rlm_results"]["RLMbj"],
            sndr["ffe_and_dfe"]["rlm_results"]["RLMbs"],
        )
    print("tf nyquist_loss      :", tf["nyquist_loss"])
    print("tf bw_3dB             :", tf["bw_3dB"])
    print(
        "eye uneq central99 UI/ps:",
        metrics.eye_uneq.central_width_ui,
        metrics.eye_uneq.central_width_ps,
    )
    print(
        "eye eq   central99 UI/ps:",
        metrics.eye_eq.central_width_ui,
        metrics.eye_eq.central_width_ps,
    )
    print(
        "eye uneq strict x/min/max/ratio:",
        (metrics.eye_uneq[0], metrics.eye_uneq[1], metrics.eye_uneq[2], metrics.eye_uneq[4]),
    )
    print(
        "eye eq   strict x/min/max/ratio:",
        (metrics.eye_eq[0], metrics.eye_eq[1], metrics.eye_eq[2], metrics.eye_eq[4]),
    )


def print_summary(
    result_or_prt: AnalysisResult | Any,
    eye_uneq: Any = None,
    eye_eq: Any = None,
) -> None:
    """Print a result summary, retaining the old ``(prt, eye, eye)`` call."""
    if isinstance(result_or_prt, AnalysisResult):
        _print_result_summary(result_or_prt)
        return

    # Legacy callers may still pass the engine and tuple metrics directly.
    prt = result_or_prt
    print("====== TX linear fit summary ======")
    meta = getattr(prt, "analysis_meta", {})
    print("osr                   :", prt.osr_input,
          "(" + meta.get("osr_source", "manual") + ")")
    if meta.get("has_time_axis"):
        print(
            "input samples/UI      : nominal={:.4f}, effective={:.4f}, gaps={:.2%}".format(
                meta["native_samples_per_ui"],
                meta["effective_samples_per_ui"],
                meta["missing_sample_fraction"],
            )
        )
    fr = prt.fit_results
    print("alignment_shift      :", fr["alignment_shift"])
    print("firNum               :", np.array2string(fr["firNum"], precision=9))
    print("firNumNorm           :", np.array2string(fr["firNumNorm"], precision=9))
    if prt.fit_spec["t_dfe_taps"]:
        print("firNumDFE            :", np.array2string(fr["firNumDFE"], precision=9))
        print("firNumDFENorm        :", np.array2string(fr["firNumDFENorm"], precision=9))
        print("DFEtapWeight         :", np.array2string(fr["DFEtapWeight"], precision=9))
    for key in ("vf", "pmax", "pulsePeakRatio", "eRms", "eRmsRatio", "SNDR", "SNR_ISI"):
        print(f"{key:<21}:", fr[key])
    print("SNDR ffe             :", prt.sndr_const["ffe"]["sndr"])
    if prt.fit_spec["t_dfe_taps"]:
        print("SNDR ffe_and_dfe     :", prt.sndr_const["ffe_and_dfe"]["sndr"])
    print(
        "RLM min-adj / 802.3bs (ffe):",
        prt.sndr_const["ffe"]["rlm_results"]["RLMbj"],
        prt.sndr_const["ffe"]["rlm_results"]["RLMbs"],
    )
    if prt.fit_spec["t_dfe_taps"]:
        print(
            "RLM min-adj / 802.3bs (dfe):",
            prt.sndr_const["ffe_and_dfe"]["rlm_results"]["RLMbj"],
            prt.sndr_const["ffe_and_dfe"]["rlm_results"]["RLMbs"],
        )
    print("tf nyquist_loss      :", prt.tf_calc["nyquist_loss"])
    print("tf bw_3dB             :", prt.tf_calc["bw_3dB"])
    for label, eye in (("uneq", eye_uneq), ("eq", eye_eq)):
        if eye is not None:
            strict = (eye[0], eye[1], eye[2], eye[4])
            print(f"eye {label} strict x/min/max/ratio:", strict)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="TX waveform linear-fit analysis")
    ap.add_argument("--filetype", choices=("lab_txt", "lab_csv"),
                    default="lab_txt",
                    help="lab_txt: time,voltage; lab_csv: voltage only")
    ap.add_argument("--filename", required=True)
    ap.add_argument("--osr", type=int, default=None,
                    help="analysis samples/UI; auto from a valid time axis, "
                         "required for voltage-only input")
    ap.add_argument("--symbol_rate", type=float, required=True,
                    help="symbol rate in baud (not PAM4 bit rate)")
    ap.add_argument("--modulation", required=True)
    ap.add_argument("--prbs_pattern", required=True)
    ap.add_argument("--pattern_length", type=int, required=True)
    ap.add_argument("--repeat_pattern_num", type=int, default=1)
    ap.add_argument("--gray_coding", default="on")
    ap.add_argument("--pre_cursor_fit", type=int, default=2)
    ap.add_argument("--total_cursor_fit", type=int, default=8)
    ap.add_argument("--pre_cursor_ffe", type=int, required=True,
                    help="number of precursor FFE taps")
    ap.add_argument("--total_cursor_ffe", type=int, required=True,
                    help="total number of FFE taps")
    ap.add_argument("--dfe_tap_num", type=int, default=1)
    ap.add_argument("--shift_vec", default="-2,-1,1,2")
    ap.add_argument("--profile", choices=("neutral", "ieee8023", "oif"),
                    default="neutral", help="report label; does not add limits")
    ap.add_argument("--output-dir", default=".",
                    help="directory for this run's CSV, PNG, and HTML artifacts")
    ap.add_argument("--plots", type=int, default=1, help="render results/*.png")
    ap.add_argument("--report", default=None,
                    help="HTML report name/path (default: output-dir/tx_linear_fit_report.html)")
    ap.add_argument("--no-report", action="store_true",
                    help="disable default HTML report generation")
    ap.add_argument("--no-open", action="store_true",
                    help="generate the HTML report without opening a browser")
    return ap


def main(argv: list[str] | None = None) -> None:
    ap = _build_parser()
    args = ap.parse_args(argv)
    try:
        config = AnalysisConfig(
            filetype=args.filetype,
            filename=args.filename,
            osr=args.osr,
            symbol_rate=float(args.symbol_rate),
            modulation=args.modulation,
            prbs_pattern=args.prbs_pattern,
            pattern_length=int(args.pattern_length),
            repeat_pattern_num=int(args.repeat_pattern_num),
            gray_coding=args.gray_coding,
            pre_cursor_fit=int(args.pre_cursor_fit),
            total_cursor_fit=int(args.total_cursor_fit),
            pre_cursor_ffe=int(args.pre_cursor_ffe),
            total_cursor_ffe=int(args.total_cursor_ffe),
            dfe_tap_num=int(args.dfe_tap_num),
            shift_vec=args.shift_vec,
            profile=args.profile,
        )
        result = analyze(config)
    except (ValueError, RuntimeError) as exc:
        ap.error(str(exc))

    print_summary(result)
    artifacts = render_artifacts(
        result,
        args.output_dir,
        report=not args.no_report,
        render_plots=bool(args.plots),
    )

    report_path = artifacts.report
    if report_path is not None and args.report:
        target = Path(args.report).expanduser()
        if not target.is_absolute():
            # ``--report`` was historically relative to CWD; only the
            # implicit default is redirected under ``--output-dir``.
            target = Path.cwd() / target
        target = target.resolve()
        if target != report_path:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_path, target)
        report_path = target

    if report_path is not None:
        print(f"HTML report: {report_path}")
        if not args.no_open:
            try:
                if webbrowser.open_new_tab(report_path.as_uri()):
                    print("Opened report in the default browser")
                else:
                    print("Warning: the default browser did not accept the report URL")
            except Exception as exc:
                print(f"Warning: unable to open the HTML report: {exc}")


if __name__ == "__main__":
    main()
