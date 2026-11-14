"""Quota del peso del router sugli esperti fuori dalle schede, con i pesi veri di --dump-routing.
(a) residenza fissa: i primi N del profilo; (b) cache adattiva simulata: per strato tanti posti quanti residenti ha quello strato
nel profilo, si parte dal profilo e un esperto scelto entra al posto del meno usato di recente (LRU)."""
import struct, sys
from collections import OrderedDict
import numpy as np

prof = open(r'D:\ds4_work\strata\Strata\data\expert-profile.bin', 'rb').read()
ver, nl, ne, slots, n = struct.unpack_from('<5I', prof, 4)
order = [struct.unpack_from('<HH', prof, 24 + 4 * i) for i in range(n)]
b = open(sys.argv[1], 'rb').read(); off = 0; recs = []
while off + 8 <= len(b):
    l, k = struct.unpack_from('<ii', b, off); off += 8
    ids = struct.unpack_from('<%di' % k, b, off); off += 4 * k
    w = struct.unpack_from('<%df' % k, b, off); off += 4 * k
    recs.append((l, ids, w))
W = np.array([r[2] for r in recs]); K = W.shape[1]
print(f'{len(recs)} righe token-strato, k={K}, token ~{len(recs) // nl}; pesi: somma per riga media {W.sum(1).mean():.3f}, '
      f'peso medio per posizione ' + ' '.join(f'{x:.3f}' for x in np.sort(W, 1)[:, ::-1].mean(0)))
for N in (13323, 17491, 19565, 22000):
    res = set(order[:N])
    fuori = np.array([[(l, e) not in res for e in ids] for l, ids, _ in recs])
    mfix = (W * fuori).sum() / W.sum()
    cap = [0] * nl
    for l, e in order[:N]: cap[l] += 1
    cache = [OrderedDict() for _ in range(nl)]
    for l, e in reversed(order[:N]): cache[l][e] = True
    miss_w = 0.0; miss_n = 0; riga_fuori = 0
    for l, ids, w in recs:
        c = cache[l]; any_miss = False
        for e, x in zip(ids, w):
            if e in c: c.move_to_end(e)
            else:
                miss_w += x; miss_n += 1; any_miss = True
                if cap[l] > 0:
                    if len(c) >= cap[l]: c.popitem(last=False)
                    c[e] = True
        riga_fuori += any_miss
    print(f'  {N} sulle schede ({100 * N / nl / ne:.0f}%): fissa: peso fuori {100 * mfix:.2f}%, scelte fuori {100 * fuori.mean():.2f}% | '
          f'adattiva (LRU): peso fuori {100 * miss_w / W.sum():.2f}%, scelte fuori {100 * miss_n / W.size:.2f}%, '
          f'righe con almeno una fuori {100 * riga_fuori / len(recs):.1f}%')
