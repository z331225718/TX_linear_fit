# -*- coding: utf-8 -*-
"""Relative level mismatch metrics, including the IEEE 802.3bs definition."""
from __future__ import annotations

import numpy as np


def calc_rlm(normalized_constellation):
    slice_p = 2.0 / 3.0
    slice_z = 0.0
    slice_n = -slice_p

    x = np.asarray(normalized_constellation, dtype=np.float64)

    def _mean_or_nan(v):
        # MATLAB mean([]) = NaN (and warns); silence the numpy warning here
        if v.size == 0:
            return float('nan')
        return float(np.mean(v))

    V3 = _mean_or_nan(x[x > slice_p])
    V2 = x[x > slice_z]
    V2 = _mean_or_nan(V2[V2 < slice_p])
    V1 = x[x < slice_z]
    V1 = _mean_or_nan(V1[V1 > slice_n])
    V0 = _mean_or_nan(x[x < slice_n])

    # MATLAB min/max ignore NaN by default (R2018b+); numpy propagates.
    def _mmin(vals):
        vals = np.asarray(vals, dtype=np.float64)
        if np.isnan(vals).all():
            return np.nan
        return np.nanmin(vals)

    RLMbj = 3.0 * _mmin([V3 - V2, V2 - V1, V1 - V0]) / (V3 - V0)
    swingScale = (V3 - V0) / (V2 - V1)

    # IEEE 802.3bs spec page 335
    Vmid = (V0 + V3) / 2.0
    ES1 = (V1 - Vmid) / (V0 - Vmid)
    ES2 = (V2 - Vmid) / (V3 - Vmid)
    RLMbs = _mmin([3.0 * ES1, 3.0 * ES2, 2.0 - 3.0 * ES1, 2.0 - 3.0 * ES2])

    # MATLAB calcRLM returns exactly these fields (Vmid/ES1/ES2 internal)
    return {'V3': V3, 'V2': V2, 'V1': V1, 'V0': V0,
            'RLMbj': RLMbj, 'swingScale': swingScale, 'RLMbs': RLMbs}
