# -*- coding: utf-8 -*-
"""Plot layer for the Python port (S5).

Mirrors the results/*.png outputs of lab_tx_linear_fit_f with the same
content, titles, legends and metric texts; matplotlib style is intentionally
simple (the acceptance criterion is numeric/data parity, not pixel parity).
"""
from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from eye_info import calc_eye_info
from eye_persistence import eye_persistence, histogram_centers


def _setup_ax(ax, xlog=False):
    ax.grid(True, which='major')
    if xlog:
        ax.set_xscale('log')
    ax.tick_params(labelsize=9)


def plot_linear_fit_error(prt, outdir='results'):
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
            alpha=0.5, color='red',
            label='Equalized - SNDR:{:.2f}'.format(
                prt.sndr_const['ffe']['sndr']))
    ax.legend()
    ax.set_ylim(ylim)
    ax.set_title('Constellation Histogram')
    ax.set_ylabel('Voltage (V)')
    ax.set_xlabel('Number of Occurances')
    fig.savefig(os.path.join(outdir, 'constellation_hist.png'), dpi=150)
    plt.close(fig)


def plot_eye_diagram(data_vec, title, prt=None, ylim=(-0.7, 0.7), ytick=None,
                     outdir='results'):
    """Persistence eye + metric text (content of plot_eye_diagram)."""
    skip_ui = 100
    eye_delay_ui = 49
    eye_num_ui = 2
    uiSample = prt.osr_input
    samplePeriod = 1.0 / (prt.symbol_rate_input * uiSample)
    Tbaud = 2.0 * uiSample * samplePeriod

    hvec, N, C = eye_persistence(data_vec, skip_ui, eye_delay_ui,
                                 eye_num_ui * uiSample,
                                 prt.symbol_rate_input / eye_num_ui,
                                 Tbaud, 1.0)

    metrics = calc_eye_info(data_vec, uiSample, Tbaud, skip_ui, None, None, None)
    eye_x_opening, min_eye_y_opening, max_eye_y_opening, eye_mid_index,         eye_y_opening_ratio = metrics[:5]

    fig, ax = plt.subplots(figsize=(8, 6))
    # color map approximating MATLAB image() colormap usage
    ncols = C.shape[1]
    x = Tbaud * (-0.5 + np.arange(ncols) / (ncols - 1))
    extent = (x[0], x[-1], hvec[0], hvec[-1])
    vmax = C.max() if C.max() > 0 else 1
    im = ax.imshow(np.flipud(C).astype(float), aspect='auto',
                   extent=extent, cmap='turbo', vmin=0, vmax=vmax)
    ax.set_ylim(hvec[0], hvec[-1])
    ax.invert_yaxis() if False else None
    ax.grid(True, which='major')
    ax.set_title(title)
    ax.set_xlim(ax.get_xlim())
    ax.set_ylim(ylim)
    ax.set_ylabel('Voltage(V)')
    ax.set_xlabel('Time(s)')
    xlimit = ax.get_xlim()
    ax.text(xlimit[0] + xlimit[1] / 20, -0.5,
            'Min X-Eye Opening(pp)={:.3f}UI           Min Y-Eye Opening(pp)={:.3f}Vpp'
            .format(eye_x_opening, min_eye_y_opening), fontsize=9)
    ax.text(xlimit[0] + xlimit[1] / 20, -0.6,
            'Max Amplitude(pp)={:.3f}VPP          Max-Amp/Eye-Opening Ratio={:.3f}'
            .format(max_eye_y_opening, eye_y_opening_ratio), fontsize=9)
    fname = ('eye_Unequalized.png' if 'Unequalized' in title
             else 'eye_Equalized.png')
    fig.savefig(os.path.join(outdir, fname), dpi=150)
    plt.close(fig)


def plot_ffe_coeff(prt, xlim=(-4, 16), outdir='results'):
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


def plot_linear_fit_pulse(prt, xlim=(-10, 20), outdir='results'):
    fig, ax = plt.subplots(figsize=(8, 6))
    _setup_ax(ax)
    fr = prt.fit_results
    main_loc = int(np.argmax(fr['p'])) + 1
    main_time_val = fr['timebase'][main_loc - 1] * prt.symbol_rate_input
    ax.plot(fr['timebase'] * prt.symbol_rate_input - main_time_val, fr['p'],
            lw=2, label='Transfer Function')
    ax.plot(fr['timebaseSampled'] * prt.symbol_rate_input - main_time_val,
            fr['pSampled'], 'o', lw=2, label='Transfer Function')
    ax.set_xlim(xlim)
    ylimit = ax.get_ylim()
    txts = [
        'Linear fit pulse peak (p_{{max}}):{:.2f}'.format(fr['pmax']),
        'Steady-state voltage(v_f):{:.2f}'.format(fr['vf']),
        'p_{{max}}/v_f:{:.2f}'.format(fr['pulsePeakRatio']),
        'SNDR [pmax/e_{{rms}}:{:.1f} dB'.format(fr['SNDR']),
        'SNDR [data_{{rms}}/e_{{rms}}:{:.1f} dB'.format(fr['SNDRold']),
        'SNDR_{{peak}}  [data_{{rms}}/e_{{rms}}]:{:.1f} dB'.format(
            fr['SNDRold_peak']),
        'Nyquist Loss:{:.1f} dB'.format(fr['nyquist_loss']),
        'RLMbj:{}'.format(prt.sndr_const['ffe']['rlm_results']['RLMbj']),
        'RLMbs:{}'.format(prt.sndr_const['ffe']['rlm_results']['RLMbs']),
    ]
    for i, s in enumerate(txts):
        ax.text(2, ylimit[1] * (0.9 - 0.1 * i), s, fontsize=9,
                fontweight='bold')
    ax.set_title('Extracted Pulse Response')
    ax.set_xlabel('Time(UI)')
    ax.set_ylabel('Voltage (V)')
    fig.savefig(os.path.join(outdir, 'linear_fit_pulse.png'), dpi=150)
    plt.close(fig)


def plot_aggregate(input_files_vec, num_of_row, num_of_col, output_path):
    from PIL import Image
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
