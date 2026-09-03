# -*- coding: utf-8 -*-
"""Python entry mirroring matlab_src/lab_tx_linear_fit_f.m (numeric part;
plotting is added in S5).

Usage example:
  python run_tx_linear_fit.py --filetype lab_txt --filename ../data/tx_pam4_prbs13_lab.txt \
      --symbol_rate 32e9 --modulation PAM4 --prbs_pattern PRBS13 --pattern_length 8191 \
      --osr 32 --pre_cursor_fit 2 --total_cursor_fit 8 --pre_cursor_ffe 2 --total_cursor_ffe 4 \
      --gray_coding on

Prints the key metrics; writes txcross.csv / txhist.csv (eye-info side
effects, same as MATLAB) into the CWD.
"""
from __future__ import annotations

import argparse
import os

import numpy as np

from process_input import process_input
from matlab_compat import colon, interp1_linear
from pulse_response_tool import PulseResponseTool
from eye_info import calc_eye_info


def make_plots(prt):
    from plots import (plot_linear_fit_error, plot_constellation_hist,
                       plot_eye_diagram, plot_ffe_coeff, plot_ffe_resp,
                       plot_tf, plot_linear_fit_pulse, plot_aggregate)
    plot_linear_fit_error(prt)
    plot_constellation_hist(prt)
    plot_eye_diagram(prt.stream_input_interp, 'Unequalized Eye Diagram', prt)
    plot_eye_diagram(prt.sndr_const['ffe']['re_interleaved_signal'],
                     'Equalized Eye Diagram', prt)
    plot_ffe_coeff(prt)
    plot_ffe_resp(prt)
    plot_tf(prt)
    plot_linear_fit_pulse(prt)
    input_files_vec = [
        'results/linear_fit_error.png', 'results/constellation_hist.png',
        'results/eye_Unequalized.png', 'results/eye_Equalized.png',
        'results/ffe_coeff.png', 'results/ffe_resp.png', 'results/tf.png',
        'results/linear_fit_pulse.png']
    plot_aggregate(input_files_vec, 2, 4, 'results/tx_summary.png')


def run_tx_linear_fit(cfg, plots=False):
    os.makedirs('results', exist_ok=True)

    lab_data = process_input(cfg['filetype'], cfg['filename'])
    data_vec = np.asarray(lab_data['data_vec'], dtype=np.float64)

    if lab_data['time_vec'].size == 0:
        data_vec_interp = data_vec
        data_vec_interp = np.tile(data_vec_interp, cfg['repeat_pattern_num'])
    else:
        time_vec = lab_data['time_vec'] - lab_data['time_vec'][0]
        time_vec_interp = colon(0.0, 1.0 / cfg['symbol_rate'] / cfg['osr'],
                                time_vec[-1])
        data_vec_interp = interp1_linear(time_vec, -1.0 * data_vec,
                                         time_vec_interp)
        data_vec_interp = np.tile(data_vec_interp, cfg['repeat_pattern_num'])

    prt = PulseResponseTool(cfg['osr'], cfg['symbol_rate'])
    prt.config_input_stream_f(data_vec_interp)
    prt.config_decision_stream_f(
        modulation=cfg['modulation'], prbs_pattern=cfg['prbs_pattern'],
        pattern_length=cfg['pattern_length'], gray_coding=cfg['gray_coding'])
    prt.config_linear_fit_pulse_f(
        pre_cursor_fit=cfg['pre_cursor_fit'],
        pre_cursor_ffe=cfg['pre_cursor_ffe'],
        total_cursor_fit=cfg['total_cursor_fit'],
        total_cursor_ffe=cfg['total_cursor_ffe'],
        dfe_tap_num=cfg['dfe_tap_num'])
    prt.apply_linear_fit_pulse_f(cfg['shift_vec'])
    prt.calc_constellation_sndr_f()
    prt.calc_tf_from_linear_fit_data_f()

    # eye-info calls mirroring plot_eye_diagram (incl. csv side effects)
    samplePeriod = 1.0 / (prt.symbol_rate_input * prt.osr_input)
    Tbaud = 2.0 * prt.osr_input * samplePeriod
    eye_uneq = calc_eye_info(prt.stream_input_interp, prt.osr_input, Tbaud,
                             100, None, None, None)
    eye_eq = calc_eye_info(prt.sndr_const['ffe']['re_interleaved_signal'],
                           prt.osr_input, Tbaud, 100, None, None, None)
    if plots:
        make_plots(prt)
    return prt, eye_uneq, eye_eq


def print_summary(prt, eye_uneq, eye_eq):
    fr = prt.fit_results
    print('====== TX linear fit summary (Python port) ======')
    print('alignment_shift      :', fr['alignment_shift'])
    print('firNum               :', np.array2string(fr['firNum'], precision=9))
    print('firNumNorm           :', np.array2string(fr['firNumNorm'], precision=9))
    print('firNumDFE            :', np.array2string(fr['firNumDFE'], precision=9))
    print('firNumDFENorm        :', np.array2string(fr['firNumDFENorm'], precision=9))
    print('DFEtapWeight         :', np.array2string(fr['DFEtapWeight'], precision=9))
    print('vf                   :', fr['vf'])
    print('pmax                 :', fr['pmax'])
    print('pulsePeakRatio       :', fr['pulsePeakRatio'])
    print('eRms                 :', fr['eRms'])
    print('eRmsRatio            :', fr['eRmsRatio'])
    print('SNDRold              :', fr['SNDRold'])
    print('SNDR                 :', fr['SNDR'])
    print('SNDRold_peak         :', fr['SNDRold_peak'])
    print('SNR_ISI              :', fr['SNR_ISI'])
    print('nyquist_loss         :', fr['nyquist_loss'])
    print('nyquist_loss_inner   :', fr['nyquist_loss_inner'])
    print('SNDR ffe             :', prt.sndr_const['ffe']['sndr'])
    print('SNDR ffe_and_dfe     :', prt.sndr_const['ffe_and_dfe']['sndr'])
    print('RLMbj / RLMbs (ffe)  :',
          prt.sndr_const['ffe']['rlm_results']['RLMbj'],
          prt.sndr_const['ffe']['rlm_results']['RLMbs'])
    print('RLMbj / RLMbs (dfe)  :',
          prt.sndr_const['ffe_and_dfe']['rlm_results']['RLMbj'],
          prt.sndr_const['ffe_and_dfe']['rlm_results']['RLMbs'])
    print('tf nyquist_loss      :', prt.tf_calc['nyquist_loss'])
    print('tf bw_3dB            :', prt.tf_calc['bw_3dB'])
    print('eye uneq x/min/max/ratio:',
          (eye_uneq[0], eye_uneq[1], eye_uneq[2], eye_uneq[4]))
    print('eye eq   x/min/max/ratio:',
          (eye_eq[0], eye_eq[1], eye_eq[2], eye_eq[4]))


def main():
    ap = argparse.ArgumentParser(description='TX linear fit (MATLAB port)')
    ap.add_argument('--filetype', default='lab_txt')
    ap.add_argument('--filename', required=True)
    ap.add_argument('--osr', type=float, default=128)
    ap.add_argument('--symbol_rate', type=float, required=True)
    ap.add_argument('--modulation', required=True)
    ap.add_argument('--prbs_pattern', required=True)
    ap.add_argument('--pattern_length', type=int, required=True)
    ap.add_argument('--repeat_pattern_num', type=int, default=1)
    ap.add_argument('--gray_coding', default='on')
    ap.add_argument('--pre_cursor_fit', type=int, default=2)
    ap.add_argument('--total_cursor_fit', type=int, default=8)
    ap.add_argument('--pre_cursor_ffe', type=int, default=2)
    ap.add_argument('--total_cursor_ffe', type=int, default=4)
    ap.add_argument('--dfe_tap_num', type=int, default=1)
    ap.add_argument('--shift_vec', default='-2,-1,1,2')
    ap.add_argument('--plots', type=int, default=1, help='render results/*.png')
    args = ap.parse_args()

    cfg = {
        'filetype': args.filetype, 'filename': args.filename,
        'osr': int(args.osr), 'symbol_rate': float(args.symbol_rate),
        'modulation': args.modulation, 'prbs_pattern': args.prbs_pattern,
        'pattern_length': int(args.pattern_length),
        'repeat_pattern_num': int(args.repeat_pattern_num),
        'gray_coding': args.gray_coding,
        'pre_cursor_fit': int(args.pre_cursor_fit),
        'total_cursor_fit': int(args.total_cursor_fit),
        'pre_cursor_ffe': int(args.pre_cursor_ffe),
        'total_cursor_ffe': int(args.total_cursor_ffe),
        'dfe_tap_num': int(args.dfe_tap_num),
        'shift_vec': tuple(int(x) for x in args.shift_vec.split(',')),
    }
    prt, e1, e2 = run_tx_linear_fit(cfg, plots=bool(args.plots))
    print_summary(prt, e1, e2)


if __name__ == '__main__':
    main()
