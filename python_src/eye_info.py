# -*- coding: utf-8 -*-
"""Eye-crossing, histogram, and eye-opening metrics.

By default the compatibility txcross.csv / txhist.csv side effects are
written to the current directory.  ``csv_output_dir=None`` disables those
side effects, while a path directs both files to that directory.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from matlab_compat import matlab_round, matlab_floor


def calc_central_eye_width(x1, OSR, settle_ui=100, central_fraction=0.99):
    """Measure central-eye width from linearly interpolated zero crossings.

    The reported opening is one UI minus the central ``central_fraction``
    span of folded crossing phases.  With the default 0.99, the outer 0.5%
    of crossings on each side are excluded so rare events do not collapse a
    visually open measured eye.
    """
    osr = int(OSR)
    if osr < 2 or float(OSR) != osr:
        raise ValueError('OSR must be an integer >= 2')
    fraction = float(central_fraction)
    if not 0.0 < fraction <= 1.0:
        raise ValueError('central_fraction must be in (0, 1]')

    data = np.asarray(x1, dtype=np.float64).ravel()
    start = max(int(settle_ui * osr) - 1, 0)  # MATLAB 1-based start
    data = data[start:]
    if data.size < 2:
        return {'width_ui': float('nan'), 'central_fraction': fraction,
                'crossing_count': 0}

    left = data[:-1]
    right = data[1:]
    crossing = (np.isfinite(left) & np.isfinite(right) &
                (np.signbit(left) != np.signbit(right)) &
                (left != right))
    indices = np.flatnonzero(crossing)
    if indices.size < 2:
        return {'width_ui': float('nan'), 'central_fraction': fraction,
                'crossing_count': int(indices.size)}

    phase = (indices - left[indices] /
             (right[indices] - left[indices])) % osr
    mean_vector = np.mean(np.exp(2j * np.pi * phase / osr))
    center = (np.angle(mean_vector) % (2 * np.pi)) * osr / (2 * np.pi)
    deviation = (phase - center + osr / 2) % osr - osr / 2
    tail = (1.0 - fraction) / 2.0
    lower, upper = np.quantile(deviation, [tail, 1.0 - tail])
    width_ui = float(np.clip(1.0 - (upper - lower) / osr, 0.0, 1.0))
    return {'width_ui': width_ui, 'central_fraction': fraction,
            'crossing_count': int(indices.size)}


def calc_eye_info(x1, OSR, Tbaud, settle_ui, figname=None, fignum=None,
                  Config=None, csv_output_dir='.'):
    max_len = int(5e4)
    x1 = np.asarray(x1, dtype=np.float64)[:min(max_len, len(x1))]

    eyediag_size = 2
    # MATLAB's x1(settle_ui*OSR:end) starts at a 1-based, inclusive index.
    x = x1[int(settle_ui * OSR) - 1:]

    L = len(x)
    num_ui = int(np.floor(L / OSR)) - 5
    if num_ui < 1:
        raise ValueError('Error :No data to analyze in eye-diagram after '
                         'clipping! Review clipping settings or run-length '
                         'of data!')

    txeye = np.zeros((num_ui, eyediag_size * OSR))
    for k in range(1, num_ui + 1):
        s0 = int(matlab_round(k * OSR)) - 1
        s1 = int(matlab_round((k + eyediag_size) * OSR - 1))   # exclusive end
        txeye[k - 1, :] = x[s0:s1]

    # zero crossings per column
    txcross = np.diff(np.sign(txeye), axis=1)
    num_eye_wraps = txcross.shape[0]
    num_eye_pts_per_wrap = txcross.shape[1]

    txhist = np.abs(txcross / 2.0).sum(axis=0)   # sum over rows (k)

    if csv_output_dir is not None:
        output_dir = Path(csv_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        np.savetxt(output_dir / 'txcross.csv', txcross, fmt='%.17g',
                   delimiter=',')
        np.savetxt(output_dir / 'txhist.csv', txhist.reshape(1, -1),
                   fmt='%.17g', delimiter=',')

    # longest consecutive zero run of txhist
    found_zero = 0
    count_zero = 0
    index_zero_start = 0
    index_zero_end = 0
    count_zero_max = 0
    t2 = 0
    t1 = 0
    for i in range(1, num_eye_pts_per_wrap + 1):
        if txhist[i - 1] == 0:
            if found_zero == 0:
                index_zero_start = i
            found_zero = 1
            count_zero = count_zero + 1
        else:
            if found_zero == 1:
                index_zero_end = i
            found_zero = 0
            if count_zero > count_zero_max:
                count_zero_max = count_zero
                t2 = index_zero_end
                t1 = index_zero_start
            count_zero = 0
    if t1 == 0 and t2 == 0:
        t1 = int(np.floor(num_eye_pts_per_wrap / 2))
        t2 = int(np.floor(num_eye_pts_per_wrap / 2)) + 1
    eye_x_opening = eyediag_size * (t2 - t1) / num_eye_pts_per_wrap

    eye_mid_index = int(np.floor((t2 + t1) / 2))
    col = txeye[:, eye_mid_index - 1]
    min_eye_y_opening = 2.0 * np.min(np.abs(col))
    max_eye_y_opening = 2.0 * np.max(np.abs(col))
    eye_y_opening_ratio = max_eye_y_opening / min_eye_y_opening

    if eye_mid_index > num_eye_pts_per_wrap / 2:
        eyediag_offset = int(np.floor(eye_mid_index - num_eye_pts_per_wrap / 2))
    else:
        eyediag_offset = int(np.floor(num_eye_pts_per_wrap + eye_mid_index
                                      - num_eye_pts_per_wrap / 2))

    cdr_eye = np.zeros((num_ui, eyediag_size * OSR))
    for k in range(1, num_ui + 1):
        s0 = k * OSR + eyediag_offset - 1
        s1 = (k + eyediag_size) * OSR + eyediag_offset - 1   # exclusive
        cdr_eye[k - 1, :] = x[s0:s1]

    return (eye_x_opening, min_eye_y_opening, max_eye_y_opening,
            eye_mid_index, eye_y_opening_ratio, txeye, txcross, txhist,
            cdr_eye)
