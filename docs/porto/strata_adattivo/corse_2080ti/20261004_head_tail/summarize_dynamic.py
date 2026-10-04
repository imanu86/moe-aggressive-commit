"""Worst case over texts and layers, plus a rough decode estimate (CPU experts only)."""
import collections, json, sys

MEAN_MAX, P99_MAX = 0.03, 0.10
# (G, C) ms per decode window from the Oct 4 full-model logs: C = CPU experts
WINDOWS = {'code-2470': (41.6, 69.0), 'explain-85': (34.9, 41.2)}


def main(path):
    d = json.load(open(path))
    agg = collections.defaultdict(list)
    for x in d['results']:
        agg[(x['score'], x['keep'], x['full_top'])].append(x)
    print(f"{'score':7} {'keep':>4} {'full':>4} {'worstMean':>9} {'worstP99':>8} {'bytesT':>6} {'bytesO':>6} "
          f"{'gainT code/explain':>19} pass")
    for (s, k, r), xs in sorted(agg.items()):
        m, p = max(x['mean'] for x in xs), max(x['p99'] for x in xs)
        bt = sum(x['bytes_transposed_down'] for x in xs) / len(xs)
        bo = sum(x['bytes_original_down'] for x in xs) / len(xs)
        gains = [(g + c) / (g + c * bt) - 1 for g, c in WINDOWS.values()]
        ok = m <= MEAN_MAX and p <= P99_MAX
        print(f"{s:7} {k:4.1f} {r:4d} {100*m:8.2f}% {100*p:7.2f}% {bt:6.2f} {bo:6.2f} "
              f"{100*gains[0]:+8.0f}% {100*gains[1]:+7.0f}%  {'PASS' if ok else ''}")
    print('checks', {k: round(v['h_py_vs_replay_p50'], 4) for k, v in d['checks'].items()})
    print('bytes', d['bytes'])


if __name__ == '__main__':
    main(sys.argv[1])
