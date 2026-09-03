# -*- coding: utf-8 -*-
"""Port of matlab_src/fit_pulse_response_f.m

Key MATLAB semantics preserved:
  * reshape unfolds are COLUMN-major (order='F');
  * P = Y*X'*inv(X*X') evaluated in that exact order;
  * eRms is overwritten inside the single-iteration zz loop (FitResults.eRms
    is therefore the *sampled+windowed* value, while SNDRold/SNDR use the
    earlier windowed value);
  * above = p > pmax/1.01; ind = FIRST true (p max element);
  * freqz on pSampled with MATLAB's default 512-point grid;
  * P3 zero masks use MATLAB 1-based ranges (empty ranges are no-ops);
  * inner Nyquist loss: pSampled(index-2:index+4) - out-of-range -> -99.
"""
from __future__ import annotations

import numpy as np

from matlab_compat import rms, filter_fir, freqz, matlab_round


def _log10db(x):
    return 20.0 * np.log10(x)


def fit_pulse_response(data, decisions, fit_spec):
    decisions = np.asarray(decisions, dtype=np.float64)   # circshift(decisions,0)
    UISAMPLES = int(fit_spec['osr_input'])
    numSymbols = int(fit_spec['num_symbols'])
    DATARATE = fit_spec['symbol_rate_input']
    T_DP = int(fit_spec['t_dp'])
    T_NP = int(fit_spec['t_np'])
    T_DW = int(fit_spec['t_dw'])
    T_NW = int(fit_spec['t_nw'])
    T_DFE_TAPS = int(fit_spec['t_dfe_taps'])

    # Bulid UI folded data matrix (column-major!)
    data = np.asarray(data, dtype=np.float64)
    Y = data[:UISAMPLES * numSymbols].reshape(UISAMPLES, numSymbols, order='F')

    # Bulid symbol matrix
    xr = np.concatenate([decisions[T_DP:], decisions[:T_DP]])   # 1-based T_DP
    X = np.zeros((T_NP + 1, len(xr)))
    for i in range(1, T_NP + 1):
        X[i - 1, :] = np.roll(xr, i - 1)
    X[T_NP, :] = 1.0

    # calculate linear fit pulse response matrix
    P = (Y @ X.T) @ np.linalg.inv(X @ X.T)
    E = P @ X - Y
    e = E.reshape(-1, order='F')
    L = P @ X
    l = L.reshape(-1, order='F')

    # Extract P1 vector and unfold pulse response fit
    P1 = P[:, :T_NP]
    p = P1.reshape(-1, order='F')

    # driver figures of merit
    vf = p.sum() / UISAMPLES
    pmax = p.max()
    pulsePeakRatio = pmax / vf
    n_e = len(e)
    lo = int(np.floor(0.1 * n_e))
    hi = int(np.floor(0.9 * n_e))
    eRms = rms(e[lo - 1:hi])                       # e(lo:hi) 1-based inclusive
    eRmsRatio = eRms / vf
    SNDRold = _log10db(rms(data) / eRms)
    SNDR = _log10db(pmax / eRms)

    # create sampled pulse response
    above = p > (pmax / 1.01)
    ind = int(np.argmax(above))                    # first true (1-based tx)
    tx = ind + 1
    initialSample = int(((tx) % UISAMPLES)) + 1    # rem(tx,UISAMPLES)+1
    pSampled = p[initialSample - 1::UISAMPLES]
    if len(pSampled) != T_NP:
        raise ValueError('internal: pSampled length != T_NP')

    # single-iteration loop (zz = initialSample only)
    e_sampled = e[initialSample - 1::UISAMPLES]
    lo2 = int(np.floor(0.1 * len(e_sampled)))
    hi2 = int(np.floor(0.9 * len(e_sampled)))
    eRms = rms(e_sampled[lo2 - 1:hi2])
    SNDRold_peak = _log10db(rms(data[initialSample - 1::UISAMPLES]) / eRms)

    # SNR_ISI
    NB = 10
    pmaxSampled = pSampled.max()
    pmaxSampledIndex = int(np.argmax(pSampled)) + 1   # 1-based
    if pmaxSampledIndex + NB + 1 <= len(pSampled):
        snrIsiCursors = pSampled[pmaxSampledIndex + NB:]   # (p+NB+1):end 1-based
        rssNonPrimary = np.sqrt(np.sum(snrIsiCursors ** 2))
        SNR_ISI = _log10db(pmaxSampled / rssNonPrimary)
    else:
        print('Warning extracted pulse not long enough to calculate SNR ISI')
        SNR_ISI = float('nan')

    # build P3 matrix
    P3 = np.zeros((T_NP, T_NW))
    for i in range(1, T_NW + 1):
        P3[:, i - 1] = np.roll(pSampled, i - 1 - T_DW)   # circshift(pSampled, i-1-T_DW)
        a1 = T_NW + i - T_DW                             # 1-based start of mask 1
        if a1 < 1:
            raise ValueError('P3 mask index < 1 (MATLAB would error too)')
        if a1 <= T_NP:
            P3[a1 - 1:, i - 1] = 0.0
        b1 = i - T_DW - 1                                # 1-based end of mask 2
        if b1 >= 1:
            P3[:min(b1, T_NP), i - 1] = 0.0

    # create xp impulse vector
    xp = np.zeros(T_NP)
    xp[T_DP] = 1.0                                       # xp(T_DP+1)=1

    w = (np.linalg.inv(P3.T @ P3) @ P3.T) @ xp           # inv(P3.'P3)*P3.'*xp
    firNum = w.copy()
    firNumNorm = firNum / w.sum()

    # FFE assuming DFE
    xp = np.zeros(T_NP)
    xp[T_DP] = 1.0
    DFEtapWeight = np.zeros(T_DFE_TAPS)
    for zz in range(1, T_DFE_TAPS + 1):
        v = pSampled[pmaxSampledIndex - 1 + zz] / pSampled[pmaxSampledIndex - 1]
        xp[T_DP + zz] = v                                # xp(T_DP+1+zz)
        DFEtapWeight[zz - 1] = xp[T_DP + zz]
    w = (np.linalg.inv(P3.T @ P3) @ P3.T) @ xp
    firNumDFE = w.copy()
    firNumDFENorm = firNumDFE / np.abs(w).sum()

    # timebases
    dt_tb = 1.0 / (UISAMPLES * DATARATE)
    timebase = np.arange(len(p)) * dt_tb
    timebaseSampled = timebase[initialSample - 1::UISAMPLES][:len(pSampled)]

    # Nyquist loss
    h, _ = freqz(pSampled)
    nyquist_loss = _log10db(np.abs(h[0]) / np.abs(h[-1]))

    idx = int(np.argmax(pSampled)) + 1                   # 1-based
    if idx - 3 >= 0 and idx + 4 <= len(pSampled):
        pSampledInner = pSampled[idx - 3:idx + 4]        # (index-2:index+4)
        h, _ = freqz(pSampledInner)
        nyquist_loss_inner = _log10db(np.abs(h[0]) / np.abs(h[-1]))
    else:
        print("Warning, insufficient FIR taps for inner Nyquist loss calculation")
        nyquist_loss_inner = -99.0

    return {
        'firNum': firNum,
        'firNumNorm': firNumNorm,
        'firNumDFE': firNumDFE,
        'firNumDFENorm': firNumDFENorm,
        'DFEtapWeight': DFEtapWeight,
        'vf': vf,
        'pmax': pmax,
        'pulsePeakRatio': pulsePeakRatio,
        'eRms': eRms,
        'eRmsRatio': eRmsRatio,
        'SNDRold': SNDRold,
        'SNDR': SNDR,
        'SNDRold_peak': SNDRold_peak,
        'SNR_ISI': SNR_ISI,
        'e': e,
        'l': l,
        'p': p,
        'w': w,
        'P3': P3,
        'pSampled': pSampled,
        'xp': xp,
        'nyquist_loss': nyquist_loss,
        'nyquist_loss_inner': nyquist_loss_inner,
        'timebase': timebase - timebaseSampled[0],
        'timebaseSampled': timebaseSampled - timebaseSampled[0],
    }
