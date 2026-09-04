# -*- coding: utf-8 -*-
"""PRBS generation and NRZ/PAM4 symbol mapping.

Compatibility semantics:
  * func_prbs: lim = min(2^n-2, num_smpls+1), hard cap 2^23; rows
    c(k+1,:) = s after each shift; output is column n of c (i.e. the
    rightmost register bit over time).  The caller does
    data = [func_prbs(...) 0]; data = data(1:end-1);  ->  data == seq.
  * PAM4 level mapping (Gray order): 10 -> +1, 11 -> +1/3, 01 -> -1/3,
    00 -> -1 ; NRZ: 2*(bit-0.5).
"""
from __future__ import annotations

import numpy as np


def func_prbs(s, t, num_smpls):
    """Port of func_prbs.m.

    s        : initial register state (list/array of 0/1, len n)
    t        : polynomial tap positions (1-based, e.g. [7 6])
    num_smpls: requested number of samples
    returns  : row array of length lim+1 (lim = min(2^n-2, num_smpls+1),
               capped at 2^23)
    """
    n = len(s)
    lim = min(2 ** n - 2, num_smpls + 1)
    if lim > 2 ** 23:
        lim = 2 ** 23

    c = np.zeros((lim + 1, n), dtype=np.int64)
    s_arr = np.array(s, dtype=np.int64)
    c[0, :] = s_arr
    m = len(t)
    b = np.zeros(max(m - 1, 1), dtype=np.int64)
    for k in range(1, lim + 1):           # MATLAB k = 1..lim
        s_old = s_arr.copy()
        b[0] = s_old[t[0] - 1] ^ s_old[t[1] - 1]
        if m > 2:
            for i in range(1, m - 1):     # MATLAB i = 1..m-2 -> b(i+1)
                b[i] = s_old[t[i + 1] - 1] ^ b[i - 1]
        s_arr[1:] = s_old[:-1]            # s(n+1-j) = s(n-j) for j=1..n-1
        s_arr[0] = b[m - 2]               # s(1) = b(m-1)
        c[k, :] = s_arr
    return c[:, n - 1]                    # seq = c(:,n)'


def gen_data_pattern(data_pattern, signal_type, seed_type, num_symbols,
                     fec_ena, fec_mode):
    """Port of func_gen_data_pattern.m (fec_ena can be 0/1; fec only used
    in branches that no-op when fec_ena==0). Returns (origin_ddata, ddata,
    txdata) as numpy arrays."""
    if signal_type == 'PAM4':
        num_bits = 2 * num_symbols
    else:
        num_bits = num_symbols

    if data_pattern == 'Clock':
        count = np.arange(1, num_bits + 1)
        data = np.mod(count, 2)
    elif data_pattern == 'Half-Clock':
        count = np.arange(1, num_bits + 1)
        data = np.floor(np.mod(count, 4) / 2)
    elif data_pattern in ('PRBS7', 'PRBS9', 'PRBS11', 'PRBS13', 'PRBS15',
                          'PRBS23', 'PRBS31'):
        seeds = {
            'PRBS7':  [1, 0, 0, 0, 0, 0, 1],
            'PRBS9':  [1, 0, 0, 0, 0, 0, 0, 0, 1],
            'PRBS11': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            'PRBS13': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            'PRBS15': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            'PRBS23': [1] + [0] * 21 + [1],
            'PRBS31': [1] + [0] * 29 + [1],
        }
        polys = {
            'PRBS7':  [7, 6],
            'PRBS9':  [9, 5],
            'PRBS11': [11, 9],
            'PRBS13': [13, 12, 2, 1],
            'PRBS15': [15, 14],
            'PRBS23': [23, 18],
            'PRBS31': [31, 28],
        }
        seed = seeds[data_pattern]
        poly = polys[data_pattern]
        # MATLAB: data = [func_prbs(...) 0]; data = data(1:end-1); -> data == seq
        data = func_prbs(seed, poly, num_bits)
        data = data.astype(np.int64)
        if seed_type == 'random':
            raise NotImplementedError(
                "seed_type='random' needs the MATLAB rand draw; use 'fixed' "
                "(tool flow passes 'fixed')")
    elif data_pattern == 'Random':
        raise NotImplementedError(
            "data_pattern='Random' uses MATLAB rand; not needed in tool flow")
    else:
        raise ValueError('Invalid data pattern: %s' % data_pattern)

    # ---- repeat the data to achieve num_bits ----
    data_out = data.copy()
    nrep = int(np.floor(num_bits / len(data))) - 1
    for _ in range(nrep):
        data_out = np.concatenate([data_out, data])

    # ---- FEC block padding (fec_ena == 0 -> none) ----
    if fec_ena == 1:
        if fec_mode in ('KR4', 'KP4'):
            additional = int(np.mod(len(data_out), 5140))
            extra_repeats = int(np.ceil(additional / len(data)))
            for _ in range(extra_repeats):
                data_out = np.concatenate([data_out, data])
    data = data_out

    # ---- origin_ddata: [zeros(1, num_bits-len(data)) data] ----
    # MATLAB zeros(1,negative) is empty -> guard with max(...,0)
    origin_ddata = np.concatenate(
        [np.zeros(max(num_bits - len(data), 0), dtype=np.int64), data])

    # ---- FEC encode (fec_ena == 0 -> pass through) ----
    if fec_ena == 1:
        raise NotImplementedError('FEC encode not ported (flow uses fec_ena=0)')
    encoded_data = data

    # ---- level mapping ----
    if signal_type == 'PAM4':
        tdata = np.zeros(int(np.round(len(encoded_data) / 2)))
        for i in range(0, len(encoded_data) - 1, 2):
            pair = encoded_data[i:i + 2]
            if (pair == [1, 0]).all():
                tdata[i // 2] = 1.0
            elif (pair == [1, 1]).all():
                tdata[i // 2] = 1.0 / 3.0
            elif (pair == [0, 1]).all():
                tdata[i // 2] = -1.0 / 3.0
            else:
                tdata[i // 2] = -1.0
    elif signal_type == 'NRZ':
        tdata = 2.0 * (encoded_data - 0.5)
    else:
        raise ValueError('Invalid signal type: %s' % signal_type)

    # ---- txdata: repeat pattern to num_symbols ----
    if num_symbols <= len(tdata):
        txdata = tdata[:num_symbols]
    else:
        txdata = tdata.copy()
        nrep = int(np.floor(num_symbols / len(tdata))) - 1
        for _ in range(nrep):
            txdata = np.concatenate([txdata, tdata])
        if num_symbols > len(txdata):
            txdata = np.concatenate(
                [txdata, tdata[:(num_symbols - len(txdata))]])

    # ---- ddata ----
    if num_bits <= len(data):
        ddata = encoded_data[:num_bits]
    else:
        ddata = data.copy()
        nrep = int(np.floor(num_bits / len(data))) - 1
        for _ in range(nrep):
            ddata = np.concatenate([ddata, encoded_data])
        if num_bits > len(encoded_data):
            ddata = np.concatenate(
                [ddata, encoded_data[:(num_bits - len(data))]])

    return origin_ddata, ddata, txdata
