#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic synthetic scope waveform generator (lab_txt / lab_csv formats)
consumed identically by MATLAB golden and the Python port.

Scope txt format (as parsed by process_input_f):
  arbitrary header lines, then exact line "Data, " then "time,voltage" rows
  until EOF ('-1' terminator line is skipped by the parser).

The waveform carries a PAM4 (or NRZ) PRBS pattern with light ISI and
deterministic noise so the TX linear-fit tool has something to fit.
LFSR here is an INDEPENDENT implementation; the tool re-syncs via xcorr,
so any cyclic phase of the same PRBS family works.
"""
from __future__ import annotations
import argparse
import os
import numpy as np

# ---------------------------------------------------------------- LFSR
def lfsr_bits(seed_int: int, taps: list[int], nbits: int, count: int) -> np.ndarray:
    """Classic Fibonacci LFSR; output bit = current LSB before shift.
    Deterministic. Any maximal-sequence phase is fine."""
    mask = (1 << nbits) - 1
    sr = seed_int & mask
    out = np.empty(count, dtype=np.int64)
    for i in range(count):
        fb = 0
        for t in taps:
            fb ^= (sr >> (t - 1)) & 1
        out[i] = sr & 1
        sr = ((sr << 1) | fb) & mask
    return out

PRBS_PARAMS = {
    # name: (seed_int, taps, nbits) -- standard polynomials
    'PRBS7':  (0b1000001, [7, 6], 7),        # x^7+x^6+1
    'PRBS13': (0b1000000000001, [13, 12, 2, 1], 13),  # x^13+x^12+x^2+x+1
    'PRBS15': (0b100000000000001, [15, 14], 15),
    'PRBS31': (0b1 << 30 | 1, [31, 28], 31),
}

def pam4_levels(bits: np.ndarray) -> np.ndarray:
    """Map bit pairs to PAM4 levels exactly as func_gen_data_pattern.m:
       10 -> +1, 11 -> +1/3, 01 -> -1/3, 00 -> -1  (Gray order)"""
    n = len(bits) // 2
    b = bits[:2 * n].reshape(n, 2)
    lv = np.empty(n)
    lv[(b[:, 0] == 1) & (b[:, 1] == 0)] = 1.0
    lv[(b[:, 0] == 1) & (b[:, 1] == 1)] = 1.0 / 3.0
    lv[(b[:, 0] == 0) & (b[:, 1] == 1)] = -1.0 / 3.0
    lv[(b[:, 0] == 0) & (b[:, 1] == 0)] = -1.0
    return lv

def nrz_levels(bits: np.ndarray) -> np.ndarray:
    return 2.0 * (bits - 0.5)

def build_waveform(symbol_rate: float, osr: int, prbs: str, modulation: str,
                   pattern_length: int, repeats: int, isi: np.ndarray,
                   noise_std: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Returns (time, voltage) sample vectors on the osr grid."""
    nbits = pattern_length if modulation == 'NRZ' else 2 * pattern_length
    seed_int, taps, nb = PRBS_PARAMS[prbs]
    bits = lfsr_bits(seed_int, taps, nb, nbits * max(repeats, 1))
    sym = pam4_levels(bits) if modulation == 'PAM4' else nrz_levels(bits)
    if repeats > 1:
        if len(sym) < pattern_length * repeats:
            sweep = np.tile(sym, repeats + 1)[:pattern_length * repeats]
        else:
            sweep = sym
    else:
        sweep = sym
    x = np.repeat(sweep, osr)
    if len(isi):
        hlen = max(ui for ui, _ in isi) * osr + 1
        h = np.zeros(hlen)
        for ui, amp in isi:
            h[ui * osr] = amp
        x = np.convolve(x, h, mode='full')[:len(x)]
    rng = np.random.default_rng(seed)
    x = x + rng.normal(0.0, noise_std, len(x))
    dt = 1.0 / (symbol_rate * osr)
    t = np.arange(len(x)) * dt
    return t, x

HEADER = "Keysight Technologies, DSOV084A Oscilloscope" + chr(10) + "Time,Amplitude" + chr(10)

def write_lab_txt(path: str, t: np.ndarray, v: np.ndarray) -> None:
    with open(path, 'w', newline='') as f:
        f.write(HEADER)
        f.write("Data, " + chr(10))
        for tt, vv in zip(t, v):
            f.write(f"{tt:.17g},{vv:.17g}" + chr(10))
        f.write("-1" + chr(10))

def write_lab_csv(path: str, v: np.ndarray) -> None:
    with open(path, 'w', newline='') as f:
        f.write(HEADER)
        f.write("Data, " + chr(10))
        for vv in v:
            f.write(f"{vv:.17g}" + chr(10))
        f.write("-1" + chr(10))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default=os.path.join(os.path.dirname(__file__), '..', 'data'))
    args = ap.parse_args()
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    # UI-aligned post-cursor taps: (ui_offset, amplitude)
    ISI = [(0, 1.0), (1, 0.18), (2, -0.09), (4, 0.04)]

    # Config A (golden default): PAM4 PRBS13, osr=32, 32 GBd, 2 repeats
    t, v = build_waveform(32e9, 32, 'PRBS13', 'PAM4', 8191, 2, ISI, 0.008, seed=20240517)
    p = os.path.join(outdir, 'tx_pam4_prbs13_lab.txt')
    write_lab_txt(p, t, v)
    print(f"{p}: {len(v)} samples, {len(v)/32/8191:.3f} pattern repeats")

    # Config B: NRZ PRBS7, osr=128, 53.125 GBd, 4 repeats
    t, v = build_waveform(53.125e9, 128, 'PRBS7', 'NRZ', 127, 4, ISI, 0.005, seed=7)
    p = os.path.join(outdir, 'tx_nrz_prbs7_lab.txt')
    write_lab_txt(p, t, v)
    print(f"{p}: {len(v)} samples")

    # small csv (voltage only) for parser checks
    t, v = build_waveform(32e9, 32, 'PRBS7', 'PAM4', 127, 2, ISI, 0.008, seed=3)
    p = os.path.join(outdir, 'tx_small_lab.csv')
    write_lab_csv(p, v)
    print(f"{p}: {len(v)} samples (csv, no time)")

if __name__ == '__main__':
    main()
