# -*- coding: utf-8 -*-
"""Parsers for supported oscilloscope text exports.

lab_txt: lines before "Data, " are headers; every following line is
         "time,voltage" (EOF or '-1' terminator line ends data).  Times are
         shifted so the first sample is 0.
lab_csv: same header rule; every following line is voltage only
         (time_vec stays empty -> the caller skips resampling).
"""
from __future__ import annotations

import numpy as np


def _read_rows(handle):
    """Yield parsed rows (list of floats) after the exact 'Data, ' header
    line, mirroring the MATLAB fgetl/str2num loop incl. skipping empty lines
    and the bare '-1' terminator; malformed rows are dropped."""
    found = False
    for raw in handle:
        line = raw.rstrip('\r\n')
        if found:
            if line == '-1':
                continue            # terminator line: skipped, loop continues
            if not line:
                continue            # empty line skipped
            try:
                yield [float(part) for part in line.split(',')]
            except ValueError:
                continue            # unparseable row: skipped like str2num []
        if line == 'Data, ':
            found = True


def process_lab_txt(filename):
    """Returns dict(time_vec, data_vec). time_vec shifted to start at 0."""
    time_vec = []
    data_vec = []
    with open(filename, 'r', newline='') as f:
        for row in _read_rows(f):
            if len(row) >= 2:
                time_vec.append(row[0])
                data_vec.append(row[1])
    time_vec = np.asarray(time_vec, dtype=np.float64)
    data_vec = np.asarray(data_vec, dtype=np.float64)
    if time_vec.size:
        time_vec = time_vec - time_vec[0]
    return {'time_vec': time_vec, 'data_vec': data_vec}


def process_lab_csv(filename):
    """Returns dict(time_vec=[], data_vec)."""
    data_vec = []
    with open(filename, 'r', newline='') as f:
        for row in _read_rows(f):
            if len(row) >= 1:
                data_vec.append(row[0])
    return {'time_vec': np.array([], dtype=np.float64),
            'data_vec': np.asarray(data_vec, dtype=np.float64)}


def process_input(filetype, filename):
    """Mirrors the intent-fixed MATLAB dispatch in lab_tx_linear_fit_f."""
    if filetype == 'lab_txt':
        return process_lab_txt(filename)
    if filetype == 'lab_csv':
        return process_lab_csv(filename)
    raise ValueError('Unknown filetype: %s' % filetype)
