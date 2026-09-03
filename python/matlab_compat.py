# -*- coding: utf-8 -*-
"""MATLAB numeric-semantics helpers used by the port.

Kept deliberately small and deterministic.  Where MATLAB's exact internal
algorithm is not documented (xcorr FFT vs direct, freqz grid), the canonical
definition is used and flagged for golden verification.
"""
from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import correlate as _scipy_correlate


def matlab_round(x):
    """MATLAB round: halves away from zero (numpy default rounds to even)."""
    x = np.asarray(x, dtype=np.float64)
    return np.copysign(np.floor(np.abs(x) + 0.5), x)


def matlab_floor(x):
    return np.floor(np.asarray(x, dtype=np.float64))


def colon(start, step, stop):
    """MATLAB start:step:stop.

    MATLAB generates v(i) = start + i*step as direct float multiplications
    and keeps elements while v(i) <= stop; the element COUNT therefore is
    max{k : fl(k*step) <= stop} + 1 (verified against golden: with
    step = fl((1/32e9)/32) = 9.7656250000000006e-13 and stop = fl(524223*step)
    this yields 524224 elements, while floor(stop/step)+1 gives 524223)."""
    start = float(start); step = float(step); stop = float(stop)
    if step == 0:
        return np.array([start])
    if (step > 0 and stop < start) or (step < 0 and stop > start):
        return np.array([])
    k = int(np.floor((stop - start) / step))
    best = k
    # fl(k*step) evaluation is authoritative; probe a few surrounding k
    for kk in (k - 2, k - 1, k, k + 1, k + 2, k + 3):
        if (start + kk * step) <= stop:
            best = max(best, kk)
    return start + np.arange(best + 1) * step


def rms(x):
    x = np.asarray(x, dtype=np.float64)
    return np.sqrt(np.mean(x * x))


def filter_fir(b, x):
    """MATLAB filter(b,1,x): FIR with zero initial conditions, output length
    == len(x).  Summation order differs from MATLAB's transposed direct form
    II but agrees to ~1e-16."""
    b = np.asarray(b, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64).ravel()
    return np.convolve(b, x, mode='full')[:len(x)]


def xcorr(a, b):
    """MATLAB xcorr(a,b) with default scaling 'none' and default maxlag.

    Convention (MATLAB doc): lag range -(N-1)..(N-1) where N = max(lengths);
    the shorter vector is zero-padded.  Returns (d, lags); d has 2N-1
    entries, d[m+N-1] = sum_n a[n+m] * conj(b[n]) with a zero-padded.
    Implemented via scipy.signal.correlate (FFT for large inputs)."""
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    n = max(len(a), len(b))
    full = _scipy_correlate(a, b, mode='full')   # lags -(Lb-1)..(La-1)
    d = np.zeros(2 * n - 1)
    lag_min = max(-(n - 1), -(len(b) - 1))
    lag_max = min(n - 1, len(a) - 1)
    if lag_min <= lag_max:
        j0 = lag_min + (len(b) - 1)      # index into 'full'
        j1 = lag_max + (len(b) - 1)
        i0 = lag_min + (n - 1)           # index into padded output
        i1 = lag_max + (n - 1)
        d[i0:i1 + 1] = full[j0:j1 + 1]
    return d, np.arange(-(n - 1), n)


def interp1_linear(x, y, xq):
    """MATLAB interp1(...,'linear') without 'extrap': NaN outside the range
    of x (unlike np.interp which clamps).  Also handles decreasing x grids
    the same way recent MATLAB does (empirically verified on the 3dB point:
    x = 20log10(tf) descending at idx-1:idx)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    scalar = np.isscalar(xq) or np.ndim(xq) == 0
    xq = np.atleast_1d(np.asarray(xq, dtype=np.float64))
    if x[0] > x[-1]:
        x = x[::-1]
        y = y[::-1]
    out = np.interp(xq, x, y)
    out[(xq < x[0]) | (xq > x[-1])] = np.nan
    return float(out[0]) if scalar else out


def interp1_spline(x, y, xq):
    """MATLAB interp1(...,'spline') = not-a-knot cubic spline (scipy default
    bc_type='not-a-knot').  NaN outside range."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xq = np.asarray(xq, dtype=np.float64)
    cs = CubicSpline(x, y)
    out = cs(xq)
    if len(xq):
        out[(xq < x[0]) | (xq > x[-1])] = np.nan
    return out


def freqz(b, n=512):
    """MATLAB freqz(b,1) default: 512 points, w = (0:n-1)*pi/n (π excluded
    from the grid).  Returns (h, w).  Flagged for golden verification."""
    b = np.asarray(b, dtype=np.float64).ravel()
    w = np.arange(n) * np.pi / n
    # H(w) = sum_m b[m] exp(-j w m)
    k = np.arange(len(b))
    H = np.exp(-1j * np.outer(w, k)) @ b
    return H, w
