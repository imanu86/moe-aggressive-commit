"""
VERSO IL 90% DI COLPI: quanto e' CONCENTRATO l'uso degli esperti?

Belady a 320 slot da' 62,1% ed e' un MURO: nessuna politica lo batte. Per il 90%
con la sola capienza servirebbero ~2.500 slot = 17 GiB, che su una 12 GB non ci
sono. Quindi la strada non e' una cache piu' grande: e' un working set piu'
piccolo.

Questo script misura, dalla traccia vera, tre cose che decidono se e' possibile:

  1. CONCENTRAZIONE: quale frazione delle domande e' coperta dai K esperti piu'
     usati di ciascuno strato. Se i primi 64 su 256 coprono il 90%, allora
     potare (REAP) o pinnare quel nucleo porta il tasso di colpi dove vogliamo
     senza aggiungere un byte di VRAM.

  2. IL NUCLEO PINNATO: cosa succede se si tengono FISSI i K piu' frequenti per
     strato e si lascia il resto all'orologio sui rimanenti slot. E' la politica
     ibrida che la concentrazione, se c'e', rende ovvia.

  3. LA TAGLIA DELL'ESPERTO: a IQ1 un esperto costa meta', quindi gli stessi
     MiB diventano il doppio degli slot. Sulla curva di Belady quel raddoppio
     vale +12 punti circa. Qui si stampa la curva per leggerla.
"""

import sys, struct
from collections import Counter, OrderedDict
import numpy as np

PISTA = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\pista2.bin'
SLOT  = int(sys.argv[2]) if len(sys.argv) > 2 else 320

with open(PISTA, 'rb') as f:
    assert f.read(8) == b'ORACOLO1'
    n_token, n_strato, n_id = struct.unpack('<iii', f.read(12))
    dati = np.fromfile(f, dtype=np.int32).reshape(n_token, n_strato, n_id)

sequenze = []
for t in range(n_token):
    ch = []
    for L in range(n_strato):
        if dati[t, L, 0] < 0:
            continue
        for e in dati[t, L]:
            if e >= 0:
                ch.append((L, int(e)))
    sequenze.append(ch)
piatta = [k for s in sequenze for k in s]
print('pista: %d token, %d domande, %.1f per token' % (n_token, len(piatta), len(piatta)/n_token))

# --- 1. CONCENTRAZIONE per strato --------------------------------------------
per_strato = {}
for (L, e) in piatta:
    per_strato.setdefault(L, Counter())[e] += 1

print('\n=== CONCENTRAZIONE: copertura dei K esperti piu usati DI CIASCUNO STRATO ===')
print('   (se pochi coprono molto, potare o pinnare quel nucleo vale piu di qualunque politica)')
for K in (8, 16, 32, 64, 96, 128, 192):
    coperte = 0
    totali  = 0
    slot_richiesti = 0
    for L, cnt in per_strato.items():
        tot = sum(cnt.values())
        top = sum(v for _, v in cnt.most_common(K))
        coperte += top; totali += tot
        slot_richiesti += min(K, len(cnt))
    print('  top %3d per strato  ->  copre %5.1f%% delle domande   (%d slot = %.0f MiB)'
          % (K, 100.0*coperte/totali, slot_richiesti, slot_richiesti*6.75))

print('\n=== quanti esperti DISTINTI vengono mai toccati, per strato ===')
distinti = [len(c) for c in per_strato.values()]
print('  media %.1f su 256 disponibili   (min %d, max %d)' %
      (np.mean(distinti), min(distinti), max(distinti)))

# --- 2. NUCLEO PINNATO + orologio sul resto ----------------------------------
def simula_belady(seq, slot):
    import heapq
    prossimo = {}; futuro = [0]*len(seq)
    for i in range(len(seq)-1, -1, -1):
        futuro[i] = prossimo.get(seq[i], len(seq)+1); prossimo[seq[i]] = i
    dentro = set(); colpi = 0; mucchio = []
    for i, k in enumerate(seq):
        if k in dentro: colpi += 1
        else:
            if len(dentro) >= slot:
                while mucchio:
                    _, kk = heapq.heappop(mucchio)
                    if kk in dentro: dentro.discard(kk); break
            dentro.add(k)
        heapq.heappush(mucchio, (-futuro[i], k))
    return colpi/len(seq)

def simula_pin_piu_lru(seq, slot, per_strato, k_pin):
    """I k_pin piu' frequenti di ogni strato restano SEMPRE dentro; il resto
    degli slot lavora a LRU sulle chiavi non pinnate."""
    pin = set()
    for L, cnt in per_strato.items():
        for e, _ in cnt.most_common(k_pin):
            pin.add((L, e))
    liberi = slot - len(pin)
    if liberi < 0:
        return None, len(pin)
    cache = OrderedDict(); colpi = 0
    for k in seq:
        if k in pin:
            colpi += 1; continue
        if k in cache:
            cache.move_to_end(k); colpi += 1
        else:
            if len(cache) >= liberi and liberi > 0:
                cache.popitem(last=False)
            if liberi > 0:
                cache[k] = True
    return colpi/len(seq), len(pin)

print('\n=== NUCLEO PINNATO + LRU sul resto, a %d slot ===' % SLOT)
for k_pin in (0, 2, 4, 6, 8, 12):
    r = simula_pin_piu_lru(piatta, SLOT, per_strato, k_pin)
    if r[0] is None:
        print('  pin %2d per strato  ->  %d slot pinnati: NON CI STANNO in %d' % (k_pin, r[1], SLOT))
    else:
        print('  pin %2d per strato  ->  %5.1f%%   (%d pinnati, %d a LRU)'
              % (k_pin, 100.0*r[0], r[1], SLOT-r[1]))

# --- 3. la curva di Belady, per leggere cosa vale raddoppiare gli slot --------
print('\n=== BELADY: il muro, a varie capienze ===')
print('   (a IQ1 un esperto costa meta: gli stessi MiB danno il doppio degli slot)')
for s in (320, 480, 640, 960, 1280, 1920, 2560):
    print('  %5d slot   Q2_K %6.0f MiB   IQ1 %6.0f MiB   ->  %5.1f%%'
          % (s, s*6.75, s*3.4, 100.0*simula_belady(piatta, s)))
