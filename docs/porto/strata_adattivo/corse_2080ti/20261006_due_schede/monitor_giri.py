"""One status line per change for the long A/B arms: decode t/s L01/L02, ms/window and a text check.

Text check: words, distinct/total words and the longest run of one repeated character. "We!!!!!..." is one
word (distinct ratio 1.00) and still broken: the run length catches it. ROTTO when words < 100, ratio < 0.35
or run >= 20.
Usage: python monitor_giri.py ARM [ARM ...]   (exits when the last arm has result.json)
"""
import re, sys, time
from pathlib import Path

K = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep')


def text_check(p):
    try:
        t = p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    w = t.split()
    ratio = len(set(w)) / max(len(w), 1)
    run = max((len(m.group(0)) for m in re.finditer(r'(.)\1*', t)), default=0)
    bad = len(w) < 100 or ratio < 0.35 or run >= 20
    return f'{len(w)}p q{ratio:.2f}' + (' ROTTO' if bad else '')


def arm_line(n):
    d = K / n
    log = d / 'engine.log'
    if not log.exists():
        return ''
    s = log.read_text(encoding='utf-8', errors='replace')
    tps = re.findall(r'generated in \d+ ms \(([0-9.]+) tok/s\)', s)
    msw = re.findall(r'decode timing: \d+ windows.*?([0-9.]+) ms/window', s)
    fail = re.search(r'too little|do not fit|stopped unexpectedly', s)
    if not tps and not fail:
        return ''
    parts = [n, '/'.join(tps)]
    if msw:
        parts.append('(' + '/'.join(f'{float(x):.0f}' for x in msw) + ' ms/fin)')
    for c in ('L01', 'L02'):
        q = text_check(d / f'{c}.txt')
        if q:
            parts.append(f'{c} {q}')
    if fail:
        parts.append('ERRORE ' + fail.group(0))
    return ' '.join(parts)


if __name__ == '__main__':
    arms = sys.argv[1:]
    seen = None
    while True:
        out = ' | '.join(x for x in (arm_line(n) for n in arms) if x)
        if out and out != seen:
            print(time.strftime('%H:%M'), out, flush=True)
            seen = out
        if (K / arms[-1] / 'result.json').exists():
            break
        time.sleep(60)
