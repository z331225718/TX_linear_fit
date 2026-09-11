# -*- coding: utf-8 -*-
"""Check that every slide's content fits the 16:9 box (no footer overlap).

The deck measures itself at load time (see the autoscale() function in the
built HTML) and records data-content-px / data-scale on each <section>.
This script reads that measurement out of a headless-rendered DOM dump.

Usage:
  # 1. render the deck and dump its DOM (Edge or Chrome)
  & 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' --headless=new ^
      --disable-gpu --virtual-time-budget=4000 --dump-dom ^
      'file:///C:/Users/z3312/code/TX_linear_fit/docs/slides/tx_linear_fit_training.html' ^
      > docs/slides/_dump.html
  # 2. report
  python docs/slides/measure_slides.py

A scale of 1.000 means the slide fits; anything below 1.000 means the content
was auto-shrunk to avoid overlapping the footer, and should be trimmed.
"""
from __future__ import annotations

import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, '_dump.html')
AVAIL = 720 - 38 - 78 - 24          # stage height - paddings - footer reserve


def main() -> int:
    if not os.path.exists(DUMP):
        print('missing DOM dump: ' + DUMP)
        print('render it first (see the header of this script)')
        return 2
    src = open(DUMP, encoding='utf-8').read()

    rows = []
    for m in re.finditer(r'<section class="slide"(.*?)>', src, re.S):
        px = re.search(r'data-content-px="(\d+)"', m.group(1))
        sc = re.search(r'data-scale="([0-9.]+)"', m.group(1))
        if not px:
            continue
        tail = src[m.end():m.end() + 1200]
        t = re.search(r'<h[12][^>]*>(.*?)</h[12]>', tail, re.S)
        title = re.sub(r'<[^>]+>', '', t.group(1)).strip() if t else '(divider)'
        ovf = re.search(r'data-ovf-x="(\d+)"', m.group(1))
        rows.append((len(rows) + 1, int(px.group(1)),
                     float(sc.group(1)) if sc else 1.0, title,
                     int(ovf.group(1)) if ovf else 0))

    over = [r for r in rows if r[2] < 0.999]
    wide = [r for r in rows if r[4] > 2]
    print('available content height: ' + str(AVAIL) + ' px')
    print('measured content slides : ' + str(len(rows)))
    print('slides needing height shrink : ' + str(len(over)))
    print('slides with horizontal overflow: ' + str(len(wide)))
    print('')
    for n, px, sc, title, ovf in sorted(rows, key=lambda r: r[2])[:12]:
        flag = '  <== TRIM' if sc < 0.999 else ''
        print(('%.3f' % sc) + '  ' + str(px).rjust(4) + ' px  #' + str(n).rjust(2) +
              '  ' + title[:44] + flag)
    if wide:
        print('')
        print('horizontal overflow (px beyond content box):')
        for n, px, sc, title, ovf in sorted(wide, key=lambda r: -r[4])[:12]:
            print('  +' + str(ovf).rjust(3) + ' px  #' + str(n).rjust(2) + '  ' + title[:48])
    return 0 if not over and not wide else 1


if __name__ == '__main__':
    sys.exit(main())
