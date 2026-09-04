# -*- coding: utf-8 -*-
"""Plot layer for TX linear-fit analysis.

Mirrors the results/*.png outputs of lab_tx_linear_fit_f with the same
content, titles, legends and metric texts; matplotlib style is intentionally
simple (the acceptance criterion is numeric/data parity, not pixel parity).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:  # Keep legacy module attributes while avoiding any metric recomputation.
    from .eye_info import calc_central_eye_width, calc_eye_info  # noqa: F401
except ImportError:  # pragma: no cover - direct script-style import
    _MODULE_DIR = str(Path(__file__).resolve().parent)
    if _MODULE_DIR not in sys.path:
        sys.path.insert(0, _MODULE_DIR)
    try:
        from .eye_info import calc_central_eye_width, calc_eye_info  # noqa: F401
    except ImportError:
        from eye_info import calc_central_eye_width, calc_eye_info  # noqa: F401

from eye_persistence import eye_persistence, histogram_centers


def _setup_ax(ax, xlog=False):
    ax.grid(True, which='major')
    if xlog:
        ax.set_xscale('log')
    ax.tick_params(labelsize=9)


def plot_linear_fit_error(prt, outdir='results'):
    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax)
    time = (np.arange(1, len(prt.stream_input_interp) + 1) /
            (prt.osr_input * prt.symbol_rate_input))
    l = prt.fit_results['l']
    e = prt.fit_results['e']
    ax.plot(time[:len(l)], l, lw=0.5, label='Linear fit')
    ax.plot(time, prt.stream_input_interp, lw=0.5, color='k', label='Data')
    ax.plot(time[:len(e)], e, color='g', lw=0.5, label='Error')
    ax.legend()
    ax.set_title('Linear Fit Pulse Error')
    ax.set_xlim(min(time[:len(l)]), max(time[:len(l)]))
    ax.set_xlabel('Time(s)')
    ax.set_ylabel('Voltage (V)')
    fig.savefig(os.path.join(outdir, 'linear_fit_error.png'), dpi=150)
    plt.close(fig)


def plot_constellation_hist(prt, ylim=(-0.7, 0.7), ytick=None, outdir='results'):
    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax)
    o = prt.osr_input
    const_uneq = prt.sndr_const['ffe']['constellation_uneq'][o:-o]
    const_eq = prt.sndr_const['ffe']['constellation_eq'][o:-o]
    bw = 0.01
    lo = min(const_uneq.min(), const_eq.min())
    hi = max(const_uneq.max(), const_eq.max())
    bins = np.arange(np.floor(lo / bw) * bw, hi + bw, bw)
    ax.hist(const_uneq, bins=bins, orientation='horizontal',
            edgecolor='none', label='Unequalized')
    ax.hist(const_eq, bins=bins, orientation='horizontal', edgecolor='none',
            alpha=0.5, color='red', label='Equalized (FFE)')
    ax.legend()
    ax.set_ylim(ylim)
    ax.set_title('Constellation Histogram')
    ax.set_ylabel('Voltage (V)')
    ax.set_xlabel('Number of Occurances')
    fig.savefig(os.path.join(outdir, 'constellation_hist.png'), dpi=150)
    plt.close(fig)


def _center_eye_columns(N, C, hvec):
    """Cyclically shift C columns so the eye-opening center lands at x=0.

    The eye sampling instant is where transitions are rare: in the middle
    voltage band (the 0-level eye for PAM4 / crossing point for NRZ) the raw
    histogram count N dips to a minimum, because no waveform passes through
    mid-levels at the sampling point.  We locate that minimum in *N* (C is
    normalized/quantized and loses the contrast) and roll it to the middle
    of the plot, making centering independent of the absolute eye_delay
    value and of the waveform.
    """
    ncols = C.shape[1]
    if ncols < 3:
        return C
    hvec = np.asarray(hvec, dtype=np.float64)
    hmid = 0.5 * (hvec[0] + hvec[-1])
    hspan = hvec[-1] - hvec[0]
    band = np.abs(hvec - hmid) < 0.08 * hspan
    prof = np.asarray(N, dtype=np.float64)[band].sum(axis=0)
    if prof.size == 0 or prof.max() <= 0:
        return C
    # 5-column moving average to suppress single-column noise
    k = min(5, ncols)
    sm = np.convolve(prof, np.ones(k) / k, mode='same')
    center_col = int(np.argmin(sm))
    mid = ncols // 2
    shift = mid - center_col
    if shift == 0:
        return C
    return np.roll(C, shift, axis=1)


def _metric_value(metrics, name, index=None, default=np.nan):
    """Read a precomputed metric from a service object, mapping, or tuple."""
    if metrics is None:
        return default
    if hasattr(metrics, name):
        return getattr(metrics, name)
    if isinstance(metrics, dict) and name in metrics:
        return metrics[name]
    if index is not None:
        try:
            return metrics[index]
        except (IndexError, KeyError, TypeError):
            pass
    return default


def _central_width(central_metrics, eye_metrics, symbol_rate):
    width_ui = _metric_value(central_metrics, 'central_width_ui', default=None)
    if width_ui is None:
        width_ui = _metric_value(central_metrics, 'width_ui', default=None)
    if width_ui is None:
        width_ui = _metric_value(eye_metrics, 'central_width_ui', default=None)
    if width_ui is None:
        try:
            width_ui = float(central_metrics)
        except (TypeError, ValueError):
            width_ui = np.nan
    width_ui = float(width_ui)
    width_ps = _metric_value(central_metrics, 'central_width_ps', default=None)
    if width_ps is None:
        width_ps = _metric_value(central_metrics, 'width_ps', default=None)
    if width_ps is None:
        width_ps = width_ui / symbol_rate * 1e12
    return width_ui, float(width_ps)


def plot_eye_diagram(data_vec, title, prt=None, ylim=None, ytick=None,
                     outdir='results', *, eye_metrics=None,
                     central_metrics=None):
    """Persistence eye + metric text (content of plot_eye_diagram).

    ylim defaults to the full hvec amplitude range so that all PAM4 eyes
    (levels -1..+1 V) are visible; pass an explicit ylim to clip.
    """
    skip_ui = 100
    eye_delay_ui = 49   # MATLAB default (samples); eye is re-centered below
    eye_num_ui = 2
    uiSample = prt.osr_input
    samplePeriod = 1.0 / (prt.symbol_rate_input * uiSample)
    Tbaud = 2.0 * uiSample * samplePeriod

    hvec, N, C = eye_persistence(data_vec, skip_ui, eye_delay_ui,
                                 eye_num_ui * uiSample,
                                 prt.symbol_rate_input / eye_num_ui,
                                 Tbaud, 1.0)
    C = _center_eye_columns(N, C, hvec)

    if eye_metrics is None:
        raise ValueError('plot_eye_diagram requires precomputed eye_metrics')
    eye_x_opening = float(_metric_value(
        eye_metrics, 'eye_x_opening', index=0))
    min_eye_y_opening = float(_metric_value(
        eye_metrics, 'min_eye_y_opening', index=1))
    max_eye_y_opening = float(_metric_value(
        eye_metrics, 'max_eye_y_opening', index=2))
    eye_y_opening_ratio = float(_metric_value(
        eye_metrics, 'eye_y_opening_ratio', index=4))
    central_width_ui, central_width_ps = _central_width(
        central_metrics, eye_metrics, prt.symbol_rate_input)

    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    # color map approximating MATLAB image() colormap usage
    ncols = C.shape[1]
    x = Tbaud * (-0.5 + np.arange(ncols) / (ncols - 1))
    extent = (x[0], x[-1], hvec[0], hvec[-1])
    vmax = C.max() if C.max() > 0 else 1
    im = ax.imshow(np.flipud(C).astype(float), aspect='auto',
                   extent=extent, cmap='turbo', vmin=0, vmax=vmax)
    ax.grid(True, which='major')
    ax.set_title(title)
    ax.set_xlim(ax.get_xlim())
    if ylim is None:
        ax.set_ylim(hvec[0], hvec[-1])
    else:
        ax.set_ylim(ylim)
    ax.set_ylabel('Voltage(V)')
    ax.set_xlabel('Time(s)')
    fig.subplots_adjust(bottom=0.28)
    width_text = ('n/a' if not np.isfinite(central_width_ui) else
                  f'{central_width_ui:.3f} UI ({central_width_ps:.2f} ps)')
    if 'Unequalized' in title:
        rlm_text = 'RLM: n/a before FFE'
    else:
        rlm = prt.sndr_const['ffe']['rlm_results']
        rlm_text = (f'RLM (Min Adjacent Spacing): {rlm["RLMbj"]:.4f}    '
                    f'RLM (IEEE 802.3bs): {rlm["RLMbs"]:.4f}')
    info = (
        f'Central 99% eye width: {width_text}    '
        f'Strict zero-crossing width: {eye_x_opening:.3f} UI\n'
        f'Min Y opening: {min_eye_y_opening:.3f} Vpp    '
        f'Max amplitude: {max_eye_y_opening:.3f} Vpp    '
        f'Strict Y ratio: {eye_y_opening_ratio:.3f}\n{rlm_text}')
    fig.text(0.125, 0.025, info, fontsize=10, color='#111827',
             linespacing=1.5, verticalalignment='bottom',
             bbox={'boxstyle': 'round,pad=0.45', 'facecolor': '#f8fafc',
                   'edgecolor': '#475569', 'linewidth': 0.9})
    fname = ('eye_Unequalized.png' if 'Unequalized' in title
             else 'eye_Equalized.png')
    fig.savefig(os.path.join(outdir, fname), dpi=150)
    plt.close(fig)


def plot_ffe_coeff(prt, xlim=(-4, 16), outdir='results'):
    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax)
    ffe_array = prt.fit_results['firNumNorm']
    main_loc = int(np.argmax(ffe_array)) + 1
    pre_vec = ffe_array[:main_loc - 1]
    main_vec = ffe_array[main_loc - 1]
    post_vec = ffe_array[main_loc:]
    x = np.arange(-len(pre_vec), len(post_vec) + 1)
    ax.bar(x, ffe_array, color='blue', label='FFE Taps')
    if prt.fit_spec['t_dfe_taps'] != 0:
        ax.bar(x, prt.fit_results['firNumDFENorm'], color='red', alpha=0.6,
               label='FFE + {:d}-tap DFE'.format(prt.fit_spec['t_dfe_taps']))
    ax.legend()
    ax.set_xlim(xlim)
    ax.set_xticks(np.arange(-len(pre_vec), len(post_vec) + 1, 1))
    ax.set_title('Normalized FFE Taps [Pre:{},Post:{}]'.format(
        len(pre_vec), len(post_vec)))
    ax.set_xlabel('Tap location')
    ax.set_ylabel('Normalized Tap Weight')
    fig.savefig(os.path.join(outdir, 'ffe_coeff.png'), dpi=150)
    plt.close(fig)


def plot_ffe_resp(prt, outdir='results'):
    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax)
    freq_n = 10_000
    freq = np.arange(1, freq_n + 1) / freq_n * prt.symbol_rate_input / 2
    k = np.arange(len(prt.fit_results['firNumNorm']))
    # MATLAB: [1xN] * [NxF]; resp(f) = sum_t firNumNorm[t]*exp(-j2pi f t/sr)
    fir_resp = (np.exp(-1j * 2 * np.pi * np.outer(freq, k) /
                       prt.symbol_rate_input) @ prt.fit_results['firNumNorm'])
    boost = 20 * np.log10(abs(fir_resp[-1] / fir_resp[0]))
    ax.plot(freq / 1e9, 20 * np.log10(abs(fir_resp)), lw=3, color='blue',
            label='FFE TF [No DFE] Nyquist:{:.3g}dB'.format(boost))
    if prt.fit_spec['t_dfe_taps'] != 0:
        k = np.arange(len(prt.fit_results['firNumDFENorm']))
        fir_resp = (np.exp(-1j * 2 * np.pi * np.outer(freq, k) /
                           prt.symbol_rate_input) @
                    prt.fit_results['firNumDFENorm'])
        boost = 20 * np.log10(abs(fir_resp[-1] / fir_resp[0]))
        ax.plot(freq / 1e9, 20 * np.log10(abs(fir_resp)), lw=3, color='red',
                label='FFE TF [{:d}-tap DFE] Nyquist:{:.3g}dB'.format(
                    prt.fit_spec['t_dfe_taps'], boost))
    ax.legend()
    ax.set_xlim(0, prt.symbol_rate_input / 1e9 / 2)
    ax.set_title('FFE Transfer Function')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Transfer Function (dB)')
    fig.savefig(os.path.join(outdir, 'ffe_resp.png'), dpi=150)
    plt.close(fig)


def plot_tf(prt, xlim=(1e8, 400e9), outdir='results'):
    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax, xlog=True)
    ax.plot(prt.tf_calc['freq'], 20 * np.log10(np.abs(prt.tf_calc['tf'])),
            lw=3, label='Transfer Function')
    ax.set_xlim(xlim)
    ax.set_title('3dB Freq:{:.4g}GHz'.format(
        float(np.asarray(prt.tf_calc['bw_3dB']).ravel()[0]) / 1e9
        if np.asarray(prt.tf_calc['bw_3dB']).size else float('nan')))
    ax.set_xlabel('Frequency(Hz)')
    ax.set_ylabel('Transfer Function (dB)')
    fig.savefig(os.path.join(outdir, 'tf.png'), dpi=150)
    plt.close(fig)


def plot_linear_fit_pulse(prt, xlim=None, outdir='results'):
    os.makedirs(outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax)
    fr = prt.fit_results
    main_loc = int(np.argmax(fr['p'])) + 1
    main_time_val = fr['timebase'][main_loc - 1] * prt.symbol_rate_input
    pulse_time_ui = fr['timebase'] * prt.symbol_rate_input - main_time_val
    sampled_time_ui = (
        fr['timebaseSampled'] * prt.symbol_rate_input - main_time_val)
    ax.plot(pulse_time_ui, fr['p'], lw=2, label='Pulse response')
    ax.plot(sampled_time_ui, fr['pSampled'], 'o', lw=2,
            label='UI samples')
    if xlim is None:
        left = min(float(np.nanmin(pulse_time_ui)),
                   float(np.nanmin(sampled_time_ui)))
        right = max(float(np.nanmax(pulse_time_ui)),
                    float(np.nanmax(sampled_time_ui)))
        pad = max(0.5, 0.02 * (right - left))
        ax.set_xlim(left - pad, right + pad)
    else:
        ax.set_xlim(xlim)
    txts = [
        'Linear-fit pulse peak (pmax): {:.2f} V'.format(fr['pmax']),
        'Steady-state voltage (vf): {:.2f} V'.format(fr['vf']),
        'Peak / steady-state: {:.2f}'.format(fr['pulsePeakRatio']),
        'Fit SNDR: {:.1f} dB'.format(fr['SNDR']),
        'Derived TF @ Nyquist: {:.1f} dB'.format(
            prt.tf_calc['nyquist_loss']),
        'RLM (Min Adjacent Spacing): {:.4f}'.format(
            prt.sndr_const['ffe']['rlm_results']['RLMbj']),
        'RLM (IEEE 802.3bs): {:.4f}'.format(
            prt.sndr_const['ffe']['rlm_results']['RLMbs']),
    ]
    ax.text(
        0.40, 0.94, '\n'.join(txts), transform=ax.transAxes,
        fontsize=9, fontweight='bold', va='top', linespacing=1.45,
        bbox={'facecolor': 'white', 'edgecolor': '#64748b',
              'alpha': 0.82, 'boxstyle': 'round,pad=0.45'},
    )
    ax.set_title('Extracted Pulse Response')
    ax.set_xlabel('Time (UI)')
    ax.set_ylabel('Voltage (V)')
    fig.savefig(os.path.join(outdir, 'linear_fit_pulse.png'), dpi=150)
    plt.close(fig)


def plot_aggregate(input_files_vec, num_of_row, num_of_col, output_path):
    from PIL import Image
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    imgs = [Image.open(f) for f in input_files_vec]
    w, h = imgs[0].size
    widths = [im.width for im in imgs]
    heights = [im.height for im in imgs]
    cell_w = max(widths)
    cell_h = max(heights)
    canvas = Image.new('RGB',
                       (cell_w * num_of_col, cell_h * num_of_row),
                       (255, 255, 255))
    for i, im in enumerate(imgs):
        r, c = divmod(i, num_of_col)
        canvas.paste(im, (c * cell_w, r * cell_h))
    canvas.save(output_path)
