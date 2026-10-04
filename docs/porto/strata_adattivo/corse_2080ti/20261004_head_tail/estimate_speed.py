"""Rough decode estimate for head/tail configurations (arm B, not a measurement).

CPU expert work is memory bound, so it is counted in full-expert units:
  baseline  miss = 1, hit = 0
  head/tail hit  = trig * (1 - H/640)            head on GPU, tail on CPU when triggered
            miss = H/640 + trig * (1 - H/640)     CPU computes head, tail only when triggered
Residency: static per-layer top-N by calibration frequency (the other two texts),
N0 = 5080 slots / 48 layers for full experts, N = N0 * 640 / H for heads.
Window time T = G + C, with G (GPU part) and C (CPU experts) taken from the
Oct 4 closed-cache logs; C scales with the CPU work ratio r. GPU work for more,
smaller heads, tail-call overhead and synchronisation are NOT modelled.
"""
import collections, json, struct, sys
from pathlib import Path

import numpy as np

FF, TOPK = 640, 10
LAYERS = (0, 1, 35, 36)
TEXTS = ('code', 'explain', 'reason')
N0 = 5080 / 48
# (G = window minus CPU experts, C = CPU experts) in ms per decode window, Oct 4 full-model logs
WINDOWS = {'code-2470': (41.6, 69.0), 'ledger-1680': (40.7, 75.4), 'explain-85': (34.9, 41.2)}
FIELDS = np.dtype([('serial', '<u8'), ('pos', '<i8'), ('layer', '<i4'), ('expert', '<i4'),
                   ('tier', '<i4'), ('gu', '<i4'), ('down', '<i4'), ('cold', '<i4'), ('weight', '<f4'),
                   ('rest', f'V{84524 - 44}')])
assert FIELDS.itemsize == 84524


def load(lab, text):
    parts = []
    for p in sorted((lab / text / 'chunks').glob('chunk-*.snr')):
        n = (p.stat().st_size - 40) // FIELDS.itemsize
        a = np.memmap(p, mode='r', dtype=FIELDS, offset=40, shape=(n,))
        parts.append({k: np.array(a[k]) for k in ('pos', 'layer', 'expert', 'tier', 'weight')})
    return {k: np.concatenate([q[k] for q in parts]) for k in parts[0]}


def rank_of(d, sel):
    pos, w = d['pos'][sel], d['weight'][sel]
    order = np.lexsort((-w, pos))
    rank = np.empty(len(sel), np.int64)
    rank[order] = np.tile(np.arange(TOPK), len(sel) // TOPK)
    return rank


def main(lab, configs):
    lab = Path(lab)
    data = {t: load(lab, t) for t in TEXTS}
    out = []
    for head, trigger in configs:
        units_base = units_new = 0.0
        hits_b = hits_n = calls = 0
        for held in TEXTS:
            d = data[held]
            for layer in LAYERS:
                cnt = collections.Counter()
                for t in TEXTS:
                    if t != held:
                        cnt.update(data[t]['expert'][data[t]['layer'] == layer].tolist())
                ranked = [e for e, _ in cnt.most_common()]
                res0 = set(ranked[:int(N0)])
                res1 = set(ranked[:min(512, int(N0 * FF / head))])
                sel = np.nonzero(d['layer'] == layer)[0]
                ex, w = d['expert'][sel], d['weight'][sel]
                rank = rank_of(d, sel)
                trig = (rank < int(trigger[5:])) if trigger.startswith('rank<') else \
                       (w >= float(trigger[3:])) if trigger.startswith('w>=') else np.zeros(len(sel), bool)
                hb = np.array([e in res0 for e in ex])
                hn = np.array([e in res1 for e in ex])
                tail = 1 - head / FF
                units_base += float((~hb).sum())
                units_new += float((hn * trig * tail).sum() + (~hn * (head / FF + trig * tail)).sum())
                hits_b += int(hb.sum()); hits_n += int(hn.sum()); calls += len(sel)
        r = units_new / units_base
        est = {k: (g + c) / (g + c * r) - 1 for k, (g, c) in WINDOWS.items()}
        out.append({'head': head, 'trigger': trigger, 'hit_base': hits_b / calls, 'hit_new': hits_n / calls,
                    'cpu_work_ratio': r, 'decode_gain_estimate': est})
        print(f"H={head} {trigger:9} hit {hits_b/calls:.2f}->{hits_n/calls:.2f}  CPU x{r:.2f}  "
              + '  '.join(f'{k} {100*v:+.0f}%' for k, v in est.items()))
    return out


if __name__ == '__main__':
    lab = sys.argv[1]
    configs = [(int(h), t) for h, t in (c.split(':') for c in sys.argv[2:])]
    res = main(lab, configs)
    print(json.dumps(res, indent=1))
