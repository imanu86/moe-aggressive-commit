"""Verdict of a hot_ab.py run (7/10), rules declared before reading the levers' results:
- outlier: a measured request more than 8% below the median of its case (L01/L02) over the whole run is a disturbance
  (desktop on the 3060, disk scans) and its pair is dropped - EXCEPT when the slow request is the B arm of a lever
  whose B falls in two or more pairs (then the lever itself breaks, and it is kept);
- position effect: the second request of a pair gains ~2% whatever the arm, so the lever's effect is
  (mean gain of the A-then-B pairs + mean gain of the B-then-A pairs) / 2, per case;
- pass: both cases > +1% and no kept pair below -5%.

    python verdetto_hot.py DET-hot-1 [--follow]      (--follow: print each lever as soon as its 12 requests are in)
"""
import json, statistics, sys, time
from pathlib import Path

K = Path(__file__).resolve().parent.parent / '20261004_routed_keep'


def load(name):
    p = K / name / 'hot_ab.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def verdict(rows, lever):
    meas = [r for r in rows if not r['warm'] and r['tps']]
    med = {c: statistics.median([r['tps'] for r in meas if r['case'] == c]) for c in ('L01', 'L02')}
    mine = [r for r in meas if r['lever'] == lever]
    pairs = {}
    for r in mine:
        pairs.setdefault((r['round'], r['case']), {})[r['arm']] = r['tps']
    slow_b = sum(1 for (rd, c), v in pairs.items() if 'B' in v and v['B'] < 0.92 * med[c])
    out, notes = {}, []
    for c in ('L01', 'L02'):
        ab, ba = [], []
        for (rd, cc), v in sorted(pairs.items()):
            if cc != c or 'A' not in v or 'B' not in v:
                continue
            g = 100 * (v['B'] / v['A'] - 1)
            if v['A'] < 0.92 * med[c] or (v['B'] < 0.92 * med[c] and slow_b < 2):
                notes.append(f'r{rd} {c} scartata (disturbo: A {v["A"]:.1f} B {v["B"]:.1f})')
                continue
            (ab if rd % 2 == 0 else ba).append(g)
        if ab and ba:
            out[c] = (sum(ab) / len(ab) + sum(ba) / len(ba)) / 2, ab, ba
        else:
            out[c] = (None, ab, ba)
    worst = min([g for c in out for g in out[c][1] + out[c][2]] or [0])
    ok = all(out[c][0] is not None and out[c][0] > 1 for c in out) and worst > -5
    s = f'{lever:18s} '
    for c in ('L01', 'L02'):
        e, ab, ba = out[c]
        s += f'{c} {"n/d" if e is None else "%+.1f%%" % e} (AB {["%+.1f" % x for x in ab]} BA {["%+.1f" % x for x in ba]})  '
    s += '-> ' + ('PASSA' if ok else 'crollo della leva' if worst <= -5 else 'nel rumore / no')
    return s + ('' if not notes else '  [' + '; '.join(notes) + ']')


def main():
    name = sys.argv[1]
    follow = '--follow' in sys.argv
    done = set()
    while True:
        rows = load(name)
        levers = list(dict.fromkeys(r['lever'] for r in rows))
        for lv in levers:
            n = sum(1 for r in rows if r['lever'] == lv and not r['warm'])
            if lv not in done and (n >= 12 or not follow):
                print(verdict(rows, lv), flush=True)
                done.add(lv)
        if not follow:
            break
        if (K / name / 'hot_ab.jsonl').exists() and not Path(r'D:\ds4_work\strata\lab_locks\bench.lock').exists():
            break
        time.sleep(20)


if __name__ == '__main__':
    main()
