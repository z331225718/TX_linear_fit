# -*- coding: utf-8 -*-
"""Port of matlab_src/pulse_response_tool_c.m (numeric methods only;
plot_* methods land in S5).

Semantics preserved:
  * config_input_stream_f: trim at first |x|>0.1*max, spline interpolation on
    the (identical) raw grid, polarity flip;
  * config_decision_stream_f: pattern regen + gray-off remap, tile/repeat to
    cover the stream, xcorr sync (pad-to-N convention), polarity flip,
    slice levels;
  * apply_linear_fit_pulse_f: fit then alignment search over shift_vec;
  * constellation helper: per-phase slicing, lfilter, slice decisions, DFE
    subtraction, per-phase SNDR, best-phase bookkeeping, column-major
    re-interleave;
  * calc_tf: trapezoid ideal pulse (linear interp + extrap), notch-smoothing
    of ideal FFT with NaN outside the clipped band.
"""
from __future__ import annotations

import numpy as np

from pattern import gen_data_pattern
from matlab_compat import (xcorr, rms, filter_fir, interp1_linear,
                           interp1_spline, colon)
from fit_pulse_response import fit_pulse_response
from calc_rlm import calc_rlm


class PulseResponseTool:
    def __init__(self, osr, symbol_rate):
        self.osr_input = osr
        self.symbol_rate_input = symbol_rate
        self.stream_input = None
        self.stream_input_interp = None
        self.stream_decision = None
        self.stream_decision_interp = None
        self.stream_decision_upsampled = None
        self.modulation = None
        self.prbs_pattern = None
        self.slice_levels = None
        self.slice_target = None
        self.fit_spec = None
        self.fit_results = None
        self.sndr_const = None
        self.tf_calc = None

    # ------------------------------------------------------------- input
    def config_input_stream_f(self, input_data, sample_start_index=1,
                              sample_stop_index=None, polarity=1):
        stop = len(input_data) if sample_stop_index is None else int(sample_stop_index)
        sig = np.asarray(input_data, dtype=np.float64)[
            int(sample_start_index) - 1:stop]
        stream_input = sig.ravel()

        # Trim long delay: first index with |x| > 0.1*max
        thr = 0.1 * np.max(np.abs(stream_input))
        idx_trim = int(np.argmax(np.abs(stream_input) > thr)) + 1   # 1-based
        start1 = idx_trim - self.osr_input
        if start1 >= 1:
            stream_input = stream_input[start1 - 1:]
        else:
            stream_input = stream_input[idx_trim - 1:]
        self.stream_input = stream_input.ravel()

        uiSample = self.osr_input
        samplePeriod = 1.0 / (self.symbol_rate_input * uiSample)
        rawSamplePeriod = 1.0 / (self.symbol_rate_input * self.osr_input)
        n = len(self.stream_input)
        timeBaseUntrim = colon(0.0, samplePeriod, (n - 1) * rawSamplePeriod)
        rawTimeBase = colon(0.0, rawSamplePeriod, (n - 1) * rawSamplePeriod)
        rawSinkData = polarity * self.stream_input
        self.stream_input_interp = interp1_spline(rawTimeBase, rawSinkData,
                                                  timeBaseUntrim).ravel()
        return self

    # ----------------------------------------------------------- decisions
    def config_decision_stream_f(self, modulation, prbs_pattern,
                                 pattern_length, gray_coding):
        self.modulation = modulation
        self.prbs_pattern = prbs_pattern
        prbs_length = int(''.join(ch for ch in str(prbs_pattern)
                                  if ch.isdigit()) or 0)   # unused downstream
        pattern_length = int(pattern_length)
        _, ddata, txdata = gen_data_pattern(prbs_pattern, modulation, 'fixed',
                                            pattern_length, 0, 0)

        # gray coding off: remap from ddata (binary order levels)
        if gray_coding == 'off' and modulation != 'NRZ':
            pam_mapping = []
            for ii in range(len(txdata)):
                pair = ddata[2 * ii:2 * ii + 2]
                if (pair == [0, 0]).all():
                    pam_mapping.append(0)
                elif (pair == [0, 1]).all():
                    pam_mapping.append(1)
                elif (pair == [1, 0]).all():
                    pam_mapping.append(2)
                else:
                    pam_mapping.append(3)
            pam_data = (np.array(pam_mapping, dtype=np.float64) * 2 - 3) / 3
            txdata = pam_data

        self.stream_decision = np.asarray(txdata, dtype=np.float64).ravel()
        repeat_pattern = int(np.ceil(len(self.stream_input) /
                                     (self.osr_input *
                                      max(len(self.stream_decision), 1))))
        self.stream_decision = np.tile(self.stream_decision, repeat_pattern)

        # upsample: repmat(osr,1) then column-major flatten == repeat each
        decisions_up = np.repeat(self.stream_decision, self.osr_input)

        d, lags = xcorr(decisions_up, self.stream_input_interp)
        midx = int(np.argmax(np.abs(d)))
        if d[midx] < 0:
            self.stream_input_interp = -1.0 * self.stream_input_interp
            self.stream_input = -1.0 * self.stream_input
        decisions_up_sync = np.roll(decisions_up, -lags[midx])

        decisions = decisions_up_sync[::self.osr_input]
        numSymbolsSink = int(np.floor(len(self.stream_input_interp) /
                                      self.osr_input))
        self.stream_decision_interp = decisions[:numSymbolsSink].ravel()
        self.stream_decision_upsampled = decisions_up_sync

        if modulation in ('NRZ', 'nrz', 'Nrz'):
            self.slice_levels = np.array([2, 0, -2], dtype=np.float64)
            self.slice_target = 1.0
        else:
            self.slice_levels = np.array([2.0 / 3, 0, -2.0 / 3], dtype=np.float64)
            self.slice_target = 1.0 / 3.0
        return self

    def config_linear_fit_pulse_f(self, pre_cursor_fit, pre_cursor_ffe,
                                  total_cursor_fit, total_cursor_ffe,
                                  dfe_tap_num=0, num_symbols=None):
        if num_symbols is None:
            num_symbols = len(self.stream_decision_interp)
        self.fit_spec = {
            't_dp': int(pre_cursor_fit), 't_dw': int(pre_cursor_ffe),
            't_np': int(total_cursor_fit), 't_nw': int(total_cursor_ffe),
            't_dfe_taps': int(dfe_tap_num), 'num_symbols': int(num_symbols),
        }
        return self

    # --------------------------------------------------------------- fit
    def apply_linear_fit_pulse_f(self, shift_vec=(-2, -1, 1, 2)):
        self.fit_spec['osr_input'] = self.osr_input
        self.fit_spec['symbol_rate_input'] = self.symbol_rate_input

        proper_alignment_found = 0
        self.fit_results = fit_pulse_response(
            self.stream_input_interp, self.stream_decision_interp, self.fit_spec)
        I = int(np.argmax(self.fit_results['firNum'])) + 1   # 1-based
        if I != (self.fit_spec['t_dw'] + 1):
            for zz in shift_vec:
                self.fit_results = fit_pulse_response(
                    self.stream_input_interp,
                    np.roll(self.stream_decision_interp, int(zz)),
                    self.fit_spec)
                I = int(np.argmax(self.fit_results['firNum'])) + 1
                if I == (self.fit_spec['t_dw'] + 1):
                    proper_alignment_found = 1
                    self.fit_results['alignment_shift'] = int(zz)
                    break
        else:
            proper_alignment_found = 1
            self.fit_results['alignment_shift'] = 0
        if proper_alignment_found == 0:
            raise RuntimeError(
                'Alignment error: Unable to find proper alignment for pulse fit')
        return self

    # ------------------------------------------------------------- sndr
    def calc_constellation_sndr_f(self):
        self.sndr_const = {
            'ffe': self._constellation_sndr_helper_f('off'),
            'ffe_and_dfe': self._constellation_sndr_helper_f('calc'),
        }
        return self

    def _constellation_sndr_helper_f(self, dfe_status, dfe_external=None):
        if dfe_status == 'calc':
            dfe_tap_weights = np.asarray(self.fit_results['DFEtapWeight'],
                                         dtype=np.float64).ravel()
            dfe_en = 1
        elif dfe_status == 'off':
            dfe_tap_weights = np.array([0.0])
            dfe_en = 0
        elif dfe_status == 'fixed':
            dfe_tap_weights = np.asarray(dfe_external, dtype=np.float64).ravel()
            dfe_en = 1
        else:
            raise ValueError(dfe_status)

        uiSample = self.osr_input
        const_sndr = 0.0
        sndr = np.zeros(uiSample)
        fs = self.fit_results
        max_phase_len = 0
        arrays = []
        for zz in range(1, uiSample + 1):
            vertical = self.stream_input_interp[zz - 1::uiSample]
            max_phase_len = max(max_phase_len, len(vertical))
            if dfe_en == 0:
                filterConstellation = filter_fir(fs['firNum'], vertical)
                filterConstellationUnity = filter_fir(fs['firNumNorm'], vertical)
            else:
                filterConstellation = filter_fir(fs['firNumDFE'], vertical)
                filterConstellationUnity = filter_fir(fs['firNumDFENorm'], vertical)
            filterConstellation = filterConstellation - filterConstellation.mean()
            arrays.append(filterConstellationUnity.copy())

            slice_p = 2.0 * self.slice_target
            slice_z = 0.0
            slice_n = -2.0 * self.slice_target
            decision_p = filterConstellation > slice_p
            decision_z = filterConstellation > slice_z
            decision_n = filterConstellation > slice_n
            # NOTE: numpy bool '+' is OR; MATLAB logical '+' promotes to
            # double counting (1+1=2). Cast explicitly.
            decisions = (2.0 * self.slice_target) * (
                decision_p.astype(np.float64) + decision_z.astype(np.float64)
                + decision_n.astype(np.float64) - 1.5)

            lengthFir = len(fs['firNum'])
            dfe_vec = np.zeros(len(decisions))
            for dfe_loop, wt in enumerate(dfe_tap_weights, start=1):
                delayed = np.roll(decisions, dfe_loop)
                dfe_vec = dfe_vec + delayed * wt
            filterConstellation = filterConstellation - dfe_vec

            lengthConst = len(filterConstellation)
            lengthDec = len(decisions)
            if lengthConst == lengthDec:
                sndr[zz - 1] = 20.0 * np.log10(
                    rms(decisions[lengthFir - 1:]) /
                    rms(filterConstellation[lengthFir - 1:] -
                        decisions[lengthFir - 1:]))
            else:
                sndr[zz - 1] = 20.0 * np.log10(
                    rms(decisions[lengthFir - 1:]) /
                    rms(filterConstellation[
                            lengthFir - 1:
                            lengthConst - (lengthConst - lengthDec)] -
                        decisions[lengthFir - 1:]))

            if sndr[zz - 1] > const_sndr:
                const_sndr = sndr[zz - 1]
                goodConstellationUnity = filterConstellationUnity.copy()
                goodConstellation = filterConstellation.copy()
                goodUnequalized = vertical
                winning_fir = fs['firNum']
                bestphase = int(np.argmax(sndr[:zz])) + 1

        # re-interleave: MATLAB reInterleavedSignal((zz-1)*cols+kk)=FCArray(zz,kk)
        # i.e. ROW-major flatten of the (max_rows x uiSample) matrix
        R = max_phase_len
        mat = np.zeros((R, uiSample))
        for zz in range(1, uiSample + 1):
            col = arrays[zz - 1]
            mat[:len(col), zz - 1] = col
        re_interleaved = mat.ravel(order='C')

        RLMResults = calc_rlm(goodConstellation)
        return {
            'raw_sndr_results': sndr,
            'sndr': const_sndr,
            'rlm_results': RLMResults,
            'constellation_eq': goodConstellationUnity,
            'constellation_uneq': goodUnequalized,
            're_interleaved_signal': re_interleaved,
        }

    # ---------------------------------------------------------------- tf
    def calc_tf_from_linear_fit_data_f(self, rise_fall_time=1e-15):
        UISAMPLES = self.osr_input
        p = self.fit_results['p']
        DATARATE = self.symbol_rate_input

        ideal_pulse = np.concatenate(
            [np.ones(UISAMPLES) * np.max(np.abs(p)),
             np.zeros(len(p) - UISAMPLES)])

        time_vec_ref = np.arange(len(p)) * (1.0 / DATARATE / UISAMPLES)
        ideal_pulse_time = np.array(
            [0.0, rise_fall_time, 1.0 / DATARATE - rise_fall_time,
             1.0 / DATARATE, time_vec_ref[-1]])
        ideal_pulse_raw = np.array(
            [0.0, np.max(np.abs(p)), np.max(np.abs(p)), 0.0, 0.0])
        ideal_pulse = interp1_linear(ideal_pulse_time, ideal_pulse_raw,
                                     time_vec_ref)

        tf = np.abs(np.fft.fft(p)) / np.abs(np.fft.fft(ideal_pulse))
        tf = tf / tf[0]
        freq = np.arange(1, len(p) + 1) / len(p) * UISAMPLES * DATARATE

        # patch notches in fft of ideal pulse
        fft_pulse = np.abs(np.fft.fft(ideal_pulse))
        keep = fft_pulse > 1e-6
        fft_pulse_clip = fft_pulse[keep]
        fft_pulse_clip_freq = freq[keep]
        fft_pulse_smooth = interp1_linear(fft_pulse_clip_freq, fft_pulse_clip,
                                          freq)
        tf = np.abs(np.fft.fft(p)) / fft_pulse_smooth
        tf = tf / tf[0]

        nyquist_loss = 20.0 * np.log10(
            float(np.interp(self.symbol_rate_input / 2.0, freq, tf)))

        idx_3dB = np.flatnonzero(20.0 * np.log10(tf) < -3.0) + 1  # 1-based (find)
        if idx_3dB.size:
            idx_3dB = idx_3dB[:1]                      # find(...,1,'first')
        if idx_3dB.size:
            i = int(idx_3dB[0])                            # already 1-based
            if i > 1:
                db = 20.0 * np.log10(tf)
                # MATLAB: interp1(20log10(tf(idx-1:idx)), freq(idx-1:idx),
                #                 20log10(tf(1))-3)
                bw_3dB = float(interp1_linear(
                    db[i - 2:i], freq[i - 2:i],
                    20.0 * np.log10(tf[0]) - 3.0))
            else:
                bw_3dB = float(freq[i - 1])
        else:
            bw_3dB = np.array([])

        self.tf_calc = {
            'tf': tf, 'freq': freq, 'nyquist_loss': nyquist_loss,
            'idx_3dB': idx_3dB, 'bw_3dB': bw_3dB,
        }
        return self
