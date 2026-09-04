# -*- coding: utf-8 -*-
"""Eye-diagram persistence matrix calculation.

Uses chunked linear interpolation and per-phase histogram accumulation.
Plotting is handled by :mod:`plots`.
"""
from __future__ import annotations

import numpy as np

from matlab_compat import matlab_round, colon


def eye_persistence(data, settle_ui, delay, OSR, data_rate, Tsym,
                    saturation=1.0):
    # MATLAB's data(settle_ui*OSR:end) uses a 1-based inclusive start.
    data4eye = np.asarray(data, dtype=np.float64)[int(settle_ui * OSR) - 1:]
    max_x4 = np.ceil(60.0 * data4eye.max()) / 60.0
    min_x4 = np.floor(60.0 * data4eye.min()) / 60.0
    hvec = colon(min_x4, 0.001, max_x4)
    LEN = len(data4eye)

    delsamples = int(delay)
    if delsamples > 0:
        data4eye = np.roll(data4eye, delsamples)

    OSRup = 1.0 / matlab_round(320.0 / OSR)
    OSRact = OSR / OSRup
    npieces = int(np.ceil(LEN / (32 * 10000 * (10 * OSRup))))
    Nsize = int(np.floor(LEN / npieces))
    Nsize = int(OSRact * np.floor(Nsize / OSRact))       # float floor -> int

    nphases = int(round(OSR / OSRup))
    N = np.zeros((len(hvec), nphases))

    for i in range(1, npieces + 1):
        seg = data4eye[(i - 1) * Nsize:(i - 1) * Nsize + Nsize]
        xi = np.arange(1, Nsize + 1, dtype=np.float64)
        xq = np.arange(1.0, Nsize + 1e-9, OSRup)         # [1:OSRup:Nsize]
        d3 = np.interp(xq, xi, seg)
        for k in range(1, nphases + 1):
            col = d3[k - 1::nphases]
            N[:, k - 1] += histogram_centers(col, hvec)

    cmax = N.max()
    C = 0 + np.ceil(N / cmax * saturation * 256.0) if cmax > 0 else np.zeros_like(N)
    return hvec, N, C


def histogram_centers(x, centers):
    """MATLAB hist(x, centers): bins centered at 'centers' (uniform step d);
    edges are midpoints; values outside the outer edges fall in the first /
    last bin (clamped counting)."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) == 0:
        return np.zeros(len(centers))
    d = centers[1] - centers[0]
    n = len(centers)
    idx = np.floor((x - centers[0]) / d + 0.5).astype(np.int64)
    idx = np.clip(idx, 0, n - 1)
    out = np.zeros(n)
    np.add.at(out, idx, 1.0)
    return out
