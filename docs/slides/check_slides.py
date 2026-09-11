# -*- coding: utf-8 -*-
"""Self-check for the built slide deck: structure, tokens, content sanity."""
from __future__ import annotations

import html.parser
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DECK = os.path.join(HERE, 'tx_linear_fit_training.html')
VOID = {'meta', 'br', 'img', 'hr', 'input', 'link', 'source'}


class Checker(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append('extra close: ' + tag)
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append('unclosed: ' + self.stack.pop())
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append('stray close: ' + tag)


def main() -> int:
    if not os.path.exists(DECK):
        print('missing deck: ' + DECK)
        return 1
    src = open(DECK, encoding='utf-8').read()
    failures = []

    slides = src.count('class="slide"')
    print('file size      : ' + str(len(src) // 1024) + ' KB')
    print('slides         : ' + str(slides))
    print('embedded images: ' + str(src.count('data:image')))
    print('section labels : ' + str(src.count('data-sec=')))

    if os.environ.get('SLIDE_OUTLINE') == '1':
        blocks = re.split(r'(?=<section class="slide")', src)
        n = 0
        for b in blocks:
            if 'class="slide"' not in b:
                continue
            n += 1
            m = re.search(r'<h[12][^>]*>(.*?)</h[12]>', b, re.S)
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else '(divider)'
            sec = re.search(r'data-sec="([^"]*)"', b)
            print(str(n).rjust(2) + ' | ' + (sec.group(1) if sec else '').ljust(12) +
                  ' | ' + title[:56])
        print('')

    leftovers = re.findall(r'[{][{][A-Z_]+[}][}]', src)
    if leftovers:
        failures.append('unresolved tokens: ' + ', '.join(sorted(set(leftovers))))
    if slides < 40:
        failures.append('expected >= 40 slides, found ' + str(slides))
    if src.count('data:image') < 8:
        failures.append('expected >= 8 embedded images')

    checker = Checker()
    checker.feed(src)
    if checker.errors:
        failures.append('html errors: ' + '; '.join(checker.errors[:6]))
    if checker.stack:
        failures.append('unclosed at EOF: ' + ', '.join(checker.stack[:6]))

    required = [
        'P̂ = Y·Xᵀ·(X·Xᵀ)⁻¹', 'SNR_ISI', 'ES1', 'RLM', 'known deviation',
        'Python', 'Data, ', 'SNR_ISI[dB]', 'freqz', 'colon',
    ]
    missing = [r for r in required if r not in src]
    if missing:
        failures.append('missing content markers: ' + ', '.join(missing))

    script = re.search(r'<script>(.*?)</script>', src, re.S)
    if script:
        open(os.path.join(HERE, '_nav_check.js'), 'w', encoding='utf-8').write(script.group(1))
        print('nav script     : ' + str(len(script.group(1))) + ' chars -> _nav_check.js')
    else:
        failures.append('no nav script found')

    if failures:
        print('')
        for f in failures:
            print('FAIL: ' + f)
        return 1
    print('')
    print('CHECK OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
