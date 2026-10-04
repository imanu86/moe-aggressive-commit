"""Worst case over held-out texts and layers for each (order, head, trigger)."""
import collections, json, sys

MEAN_MAX, P99_MAX = 0.03, 0.10


def main(path):
    r = json.load(open(path))['results']
    agg = collections.defaultdict(list)
    for x in r:
        agg[(x['order'], x['head'], x['trigger'])].append(x)
    rows = []
    for (o, h, t), xs in agg.items():
        worst_mean = max(x['mean'] for x in xs)
        worst_p99 = max(x['p99'] for x in xs)
        deep = max(x['p99'] for x in xs if x['layer'] >= 35)
        frac = sum(x['tail_calls_computed'] for x in xs) / len(xs)
        rows.append((o, h, t, frac, worst_mean, worst_p99, deep,
                     worst_mean <= MEAN_MAX and worst_p99 <= P99_MAX))
    rows.sort(key=lambda z: (z[0], z[1], z[3]))
    print(f"{'order':8} {'head':>4} {'trigger':9} {'tail%':>6} {'worstMean':>9} {'worstP99':>8} {'deepP99':>8} pass")
    for o, h, t, f, m, p, d, ok in rows:
        print(f"{o:8} {h:4d} {t:9} {100*f:6.1f} {100*m:8.2f}% {100*p:7.2f}% {100*d:7.2f}% {'PASS' if ok else ''}")


if __name__ == '__main__':
    main(sys.argv[1])
