"""Compare two forced runs (det_force.sh): windows, rows/window histogram, accepted drafts, drafter disagreement.

    python det_force_compare.py DET-a DET-b
"""
import collections, json, re, sys
from pathlib import Path

K = Path(__file__).resolve().parents[1] / '20261004_routed_keep'


def load(name):
    d = K / name
    w = collections.defaultdict(list)   # request -> [(pos, T, acc, rows)]
    tr = d / 'force_trace.txt'
    if tr.exists():
        for line in tr.read_text().splitlines():
            f = line.split()
            if f and f[0] == 'W':
                w[int(f[1])].append((int(f[2]), int(f[3]), int(f[4]), tuple(int(x) for x in f[5:])))
    log = (d / 'engine.log').read_text(errors='replace')
    work = [l for l in log.splitlines() if l.startswith('strata work:')]
    res = json.loads((d / 'result.json').read_text()) if (d / 'result.json').exists() else {}
    return w, work, res


def main():
    a, b = sys.argv[1], sys.argv[2]
    wa, worka, ra = load(a)
    wb, workb, rb = load(b)
    for x, y in zip(worka, workb):
        print('A', x)
        print('B', y)
        print('   same work line:', re.sub(r'target picks replaced.*', '', x) == re.sub(r'target picks replaced.*', '', y))
    for qa, qb in zip(ra.get('requests', []), rb.get('requests', [])):
        print(qa['case'], 'tokens identical:', qa['generated_ids'] == qb['generated_ids'],
              'tps %.1f / %.1f' % (qa['decode_tps'] or 0, qb['decode_tps'] or 0))
    for r in sorted(set(wa) | set(wb)):
        A, B = wa.get(r, []), wb.get(r, [])
        same = 0
        while same < min(len(A), len(B)) and A[same] == B[same]:
            same += 1
        ha = collections.Counter(t for _, t, _, _ in A)
        hb = collections.Counter(t for _, t, _, _ in B)
        # the drafter: windows that start at the same position (same forced history) - their draft rows compared
        sa = {p: rows for p, _, _, rows in A}
        cmp_n = diff_n = win_n = win_diff = 0
        for p, _, _, rows in B:
            if p in sa:
                ra_, rb_ = sa[p], rows
                m = min(len(ra_), len(rb_)) - 1
                if m <= 0:
                    continue
                win_n += 1
                d = sum(1 for i in range(1, m + 1) if ra_[i] != rb_[i])
                cmp_n += m
                diff_n += d
                win_diff += 1 if (d or len(ra_) != len(rb_)) else 0
        print(f'request {r}: windows {len(A)} / {len(B)}, identical for the first {same}; '
              f'rows hist A {dict(sorted(ha.items()))} B {dict(sorted(hb.items()))}; '
              f'accepted {sum(x[2] for x in A)} / {sum(x[2] for x in B)}')
        print(f'   drafter: {win_n} windows start at the same position; {win_diff} differ in draft tokens or rows; '
              f'{diff_n} of {cmp_n} draft tokens differ ({100.0 * diff_n / max(1, cmp_n):.2f}%)')


main()
