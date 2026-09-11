# -*- coding: utf-8 -*-
"""Build the self-contained training slide deck.

Concatenates the HTML fragments in docs/slides/src (sorted by name) and
replaces IMG tokens with base64 data URIs taken from python_src/results.

Usage:  python docs/slides/build_slides.py
Output: docs/slides/tx_linear_fit_training.html
"""
from __future__ import annotations

import base64
import io
import os
import re
import sys

try:
    from PIL import Image
except ImportError:
    Image = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(HERE, 'src')
RESULTS = os.path.join(ROOT, 'python_src', 'results')
OUT = os.path.join(HERE, 'tx_linear_fit_training.html')

# token -> (file, max width, force jpeg)
IMAGES = {
    'IMG_PULSE': ('linear_fit_pulse.png', 1000, False),
    'IMG_ERR': ('linear_fit_error.png', 1000, False),
    'IMG_CONST': ('constellation_hist.png', 1000, False),
    'IMG_EYE_EQ': ('eye_Equalized.png', 1000, True),
    'IMG_EYE_UNEQ': ('eye_Unequalized.png', 1000, True),
    'IMG_FFE_COEFF': ('ffe_coeff.png', 1000, False),
    'IMG_FFE_RESP': ('ffe_resp.png', 1000, False),
    'IMG_TF': ('tf.png', 1000, False),
    'IMG_SUMMARY': ('tx_summary.png', 1200, True),
}


def data_uri(path: str, max_width: int, force_jpeg: bool) -> str:
    raw = open(path, 'rb').read()
    if Image is None:
        mime = 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
        return 'data:' + mime + ';base64,' + base64.b64encode(raw).decode('ascii')

    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.width > max_width:
        h = int(round(im.height * max_width / im.width))
        im = im.resize((max_width, h), Image.LANCZOS)

    use_jpeg = force_jpeg or len(raw) > 240000
    if use_jpeg:
        buf = io.BytesIO()
        im.convert('RGB').save(buf, format='JPEG', quality=84, optimize=True)
        mime = 'image/jpeg'
        payload = buf.getvalue()
    else:
        buf = io.BytesIO()
        im.convert('RGBA').save(buf, format='PNG', optimize=True)
        payload = buf.getvalue()
        mime = 'image/png'
        if len(payload) >= len(raw):
            # re-encode is not a win for line art: keep the original bytes
            payload = raw
            mime = 'image/png'
    print('  ' + os.path.basename(path) + ': ' + str(len(raw) // 1024) + 'KB -> ' +
          str(len(payload) // 1024) + 'KB (' + mime + ')')
    return 'data:' + mime + ';base64,' + base64.b64encode(payload).decode('ascii')


def renumber(html: str) -> str:
    """Rewrite every slide's page number from its document order, so that
    adding/removing a slide never leaves stale numbers behind."""
    counter = [0]

    def sub(_match):
        counter[0] += 1
        return '<div class="num">' + str(counter[0]) + '</div>'

    html = re.sub(r'<div class="num">[0-9]+</div>', sub, html)
    print('renumbered slides: ' + str(counter[0]))
    return html


def main() -> int:
    parts = sorted(f for f in os.listdir(SRC) if f.lower().endswith('.html'))
    if not parts:
        print('no fragments in ' + SRC)
        return 1
    html = ''
    for name in parts:
        with open(os.path.join(SRC, name), 'r', encoding='utf-8') as fh:
            html += fh.read()
    print('fragments: ' + str(len(parts)) + ' -> ' + str(len(html)) + ' chars')

    print('embedding images:')
    for token, (fname, width, jpeg) in IMAGES.items():
        path = os.path.join(RESULTS, fname)
        placeholder = '{{' + token + '}}'
        if not os.path.exists(path):
            if placeholder in html:
                print('  MISSING ' + fname + ' (token kept as-is)')
            continue
        if placeholder not in html:
            continue
        html = html.replace(placeholder, data_uri(path, width, jpeg))

    html = renumber(html)

    leftovers = sorted(set(re.findall(r'\{\{[A-Z_]+\}\}', html)))
    if leftovers:
        print('UNRESOLVED TOKENS: ' + ', '.join(leftovers))
        return 2

    slide_count = html.count('class="slide"')
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print('slides: ' + str(slide_count))
    print('written: ' + OUT + ' (' + str(os.path.getsize(OUT) // 1024) + ' KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
