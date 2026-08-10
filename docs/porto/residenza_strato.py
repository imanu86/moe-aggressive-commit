"""
LA DISTANZA CICLICA DALLO STRATO: quanto vale come politica di sfratto.

Un esperto (L, e) viene chiesto SOLTANTO allo strato L, e gli strati si
attraversano in ordine ciclico 0..42 a ogni token. Quindi quando si sfratta allo
strato S, per ogni residente dello strato M la distanza dal prossimo uso
POSSIBILE e' esatta, non stimata:

    distanza = (M - S + n_strati) % n_strati        0 = strato appena superato

La vittima giusta e' quella con la distanza PIU' GRANDE: uno dello strato appena
passato non puo' servire per altri 42 strati, uno dello strato S+1 serve subito.

Le politiche basate sul passato (recency, frequenza) approssimano il futuro con
cio' che e' gia' successo. Qui il futuro ha una STRUTTURA NOTA e si puo' usare
direttamente. La domanda che questo script risponde: quanta parte del margine di
Belady cattura, senza sapere nulla del contenuto.
"""

import sys, struct, heapq
from collections import OrderedDict
import numpy as np

PISTA = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\pista2.bin'

with open(PISTA, 'rb') as f:
    assert f.read(8) == b'ORACOLO1'
    n_token, n_strato, n_id = struct.unpack('<iii', f.read(12))
    dati = np.fromfile(f, dtype=np.int32).reshape(n_token, n_strato, n_id)

seq, lay = [], []
for t in range(n_token):
    for L in range(n_strato):
        r = dati[t, L]
        if r[0] < 0:
            continue
        for e in r:
            if e >= 0:
                seq.append((L << 16) | int(e))
                lay.append(L)
N = len(seq)

# quanti strati sono davvero instradati: il ciclo vero, non n_strato
strati_veri = sorted(set(lay))
CICLO = max(strati_veri) + 1


def lru(seq, slot):
    c, colpi = OrderedDict(), 0
    for k in seq:
        if k in c:
            c.move_to_end(k); colpi += 1
        else:
            if len(c) >= slot:
                c.popitem(last=False)
            c[k] = True
    return colpi / N


def per_strato(seq, lay, slot, ciclo):
    """Vittima con la distanza ciclica MAGGIORE; spareggio sulla meno recente."""
    dentro = {}          # chiave -> (strato, epoca)
    colpi = 0
    epoca = 0
    for i, k in enumerate(seq):
        S = lay[i]
        epoca += 1
        if k in dentro:
            dentro[k] = (dentro[k][0], epoca)
            colpi += 1
            continue
        if len(dentro) >= slot:
            peggio, pd, pe = None, -1, None
            for kk, (M, e) in dentro.items():
                dist = (M - S + ciclo) % ciclo
                if dist > pd or (dist == pd and e < pe):
                    pd, pe, peggio = dist, e, kk
            del dentro[peggio]
        dentro[k] = (S, epoca)
    return colpi / N


def belady(seq, slot):
    pross, fut = {}, [0] * N
    for i in range(N - 1, -1, -1):
        fut[i] = pross.get(seq[i], N + 1)
        pross[seq[i]] = i
    dentro, colpi, mucchio = set(), 0, []
    for i, k in enumerate(seq):
        if k in dentro:
            colpi += 1
        else:
            if len(dentro) >= slot:
                while mucchio:
                    _, kk = heapq.heappop(mucchio)
                    if kk in dentro:
                        dentro.discard(kk); break
            dentro.add(k)
        heapq.heappush(mucchio, (-fut[i], k))
    return colpi / N


print('pista: %d domande, %d token, ciclo di %d strati instradati' % (N, n_token, CICLO))
print()
print('%6s  %8s  %8s  %8s   %s' % ('slot', 'LRU', 'STRATO', 'BELADY', 'margine catturato'))
for s in (448, 640, 900):
    l = lru(seq, s)
    st = per_strato(seq, lay, s, CICLO)
    b = belady(seq, s)
    quota = 100.0 * (st - l) / (b - l) if b > l else 0.0
    print('%6d  %7.1f%%  %7.1f%%  %7.1f%%   %+5.1f punti su LRU, %.0f%% del margine'
          % (s, 100 * l, 100 * st, 100 * b, 100 * (st - l), quota))

print()
print('LETTURA: se STRATO cattura una fetta grossa del margine fra LRU e Belady,')
print('la struttura ciclica vale piu' + "'" + ' di qualunque euristica sul passato --')
print('e costa zero, perche' + "'" + ' lo strato e' + "'" + ' gia' + "'" + ' dentro la chiave.')
