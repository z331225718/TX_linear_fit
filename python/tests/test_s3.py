# -*- coding: utf-8 -*-
"""S3 unit tests: pattern.py and process_input.py (self-consistency +
documented MATLAB semantics; golden comparison comes later)."""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
from pattern import func_prbs, gen_data_pattern
from process_input import process_lab_txt, process_lab_csv

ROOT = os.path.dirname(os.path.dirname(_HERE))      # repo root
FAIL = []

def check(name, cond, extra=''):
    if not cond:
        FAIL.append(name)
        print('FAIL', name, extra)
    else:
        print('ok  ', name, extra)

# ---- func_prbs ----
s7 = [1, 0, 0, 0, 0, 0, 1]
seq = func_prbs(s7, [7, 6], 200)
check('prbs7 len == lim+1 == 127', len(seq) == 127, f'len={len(seq)}')
check('prbs7 first element is seed LSB (c(1,7))', seq[0] == 1)
seq2 = func_prbs(s7, [7, 6], 300)
check('func_prbs always returns full PRBS7 cycle for big requests',
      len(seq2) == 127 and np.array_equal(seq, seq2))
s13 = [1] + [0] * 11 + [1]
seq13 = func_prbs(s13, [13, 12, 2, 1], 20000)
check('prbs13 len == 8191', len(seq13) == 8191, f'len={len(seq13)}')
check('prbs13 binary', set(np.unique(seq13)) <= {0, 1})
# polynomial consistency: PRBS13 = x^13+x^12+x^2+x+1 is a valid LFSR,
# verify the output-state recurrence on a few consecutive states by
# re-simulating the register from the printed c rows is overkill here;
# structural checks only (golden will validate exact bits).

# ---- gen_data_pattern ----
od, dd, tx = gen_data_pattern('PRBS13', 'PAM4', 'fixed', 8191, 0, 0)
check('PAM4 PRBS13 tx len 8191', len(tx) == 8191)
check('PAM4 PRBS13 dd len 16382', len(dd) == 16382)
check('PAM4 PRBS13 od == dd (exact fit)', np.array_equal(od, dd))
lu = np.unique(np.round(tx, 12))
check('PAM4 levels {-1,-1/3,1/3,1}',
      len(lu) == 4 and np.allclose(lu, [-1.0, -1 / 3, 1 / 3, 1.0], atol=1e-12),
      str(lu))
ok_map = all(
    ((dd[2 * i] == 1 and dd[2 * i + 1] == 0 and tx[i] == 1.0) or
     (dd[2 * i] == 1 and dd[2 * i + 1] == 1 and abs(tx[i] - 1 / 3) < 1e-12) or
     (dd[2 * i] == 0 and dd[2 * i + 1] == 1 and abs(tx[i] + 1 / 3) < 1e-12) or
     (dd[2 * i] == 0 and dd[2 * i + 1] == 0 and tx[i] == -1.0))
    for i in range(64))
check('PAM4 gray mapping consistent', ok_map)

od7, dd7, tx7 = gen_data_pattern('PRBS7', 'PAM4', 'fixed', 127, 0, 0)
check('PAM4 PRBS7 tx len 127', len(tx7) == 127)
check('PAM4 PRBS7 dd len 254', len(dd7) == 254)
od_n, dd_n, tx_n = gen_data_pattern('PRBS7', 'NRZ', 'fixed', 127, 0, 0)
check('NRZ PRBS7 tx len 127, bipolar', len(tx_n) == 127
      and set(np.unique(tx_n)) == {-1.0, 1.0})
check('NRZ tx == 2*(bits-0.5)', np.array_equal(tx_n, 2 * (dd_n[:127] - 0.5)))

od15, dd15, tx15 = gen_data_pattern('PRBS15', 'PAM4', 'fixed', 32767, 0, 0)
check('PAM4 PRBS15 tx len 32767', len(tx15) == 32767)
check('PAM4 PRBS15 dd len 65534', len(dd15) == 65534)

od31, dd31, tx31 = gen_data_pattern('PRBS31', 'NRZ', 'fixed', 1500, 0, 0)
check('NRZ PRBS31 tx len 1500 (truncated)', len(tx31) == 1500)
check('NRZ PRBS31 dd len 1500', len(dd31) == 1500)
# data length = 1502 (lim = num_smpls+1 = 1501 -> seq len 1502); MATLAB
# origin_ddata = [zeros(1,-2) data] = data -> length 1502
check('NRZ PRBS31 od len 1502 (zeros(1,-2) is empty)', len(od31) == 1502)

# ---- process_input ----
data_dir = os.path.join(ROOT, 'data')
p1 = os.path.join(data_dir, 'tx_pam4_prbs13_lab.txt')
res = process_lab_txt(p1)
check('lab_txt: 524224 samples', len(res['data_vec']) == 524224)
check('lab_txt: time starts 0', res['time_vec'][0] == 0.0)
dt = np.diff(res['time_vec'])
check('lab_txt: uniform dt = 1/(32e9*32)',
      np.allclose(dt, 1 / (32e9 * 32), rtol=1e-12, atol=1e-20),
      f'first dt={dt[0]:.6e}')
check('lab_txt: finite values', np.isfinite(res['data_vec']).all())
check('lab_txt: amplitude in range', np.abs(res['data_vec']).max() < 2.0)

p2 = os.path.join(data_dir, 'tx_small_lab.csv')
res2 = process_lab_csv(p2)
check('lab_csv: 8128 samples', len(res2['data_vec']) == 8128)
check('lab_csv: time_vec empty', res2['time_vec'].size == 0)

print()
print('FAILURES:', FAIL if FAIL else 'none')
sys.exit(1 if FAIL else 0)
