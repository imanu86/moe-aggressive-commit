"""
K PER STRATO = QUANTI MANCANO IN QUELLO STRATO.

La regola (utente): nessuna copia a domanda, mai. O l'esperto e' arrivato in
tempo e lo calcola la GPU dalla VRAM, o non c'e' e lo calcola la CPU dalla RAM,
in sovrapposizione. Zero trasferimenti esposti.

`kern_partiziona` ordina GIA' per residenza e manda alla CPU i non residenti per
primi. L'unica cosa che rompe la regola e' che il taglio e' FISSO a 2, mentre i
mancanti sono ~4 per strato: gli altri due restano sulla GPU e fanno scattare la
copia proibita.

Un taglio variabile per TOKEN cambierebbe le forme dei tensori e romperebbe i
CUDA graph. Un taglio variabile per STRATO no: ogni strato costruisce le sue
viste alla costruzione del grafo, e restano fisse.

Questo script misura, dalla traccia, quanti esperti mancano in CIASCUNO strato
sotto la politica di residenza, e quindi che K servirebbe li'. Il vincolo e' che
la somma del lavoro CPU stia nella finestra di sovrapposizione:

    finestra = 45 ms   (attenzione + join, la CPU e' ferma)
    costo    = 0,242 ms per esperto su CPU
    quindi la CPU regge ~186 esperti per token
"""

import sys, struct
from collections import OrderedDict, Counter
import numpy as np

PISTA = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\pista2.bin'
SLOT  = int(sys.argv[2]) if len(sys.argv) > 2 else 320
CPU_MS = 0.242
FINESTRA_MS = 45.0

with open(PISTA, 'rb') as f:
    assert f.read(8) == b'ORACOLO1'
    n_token, n_strato, n_id = struct.unpack('<iii', f.read(12))
    dati = np.fromfile(f, dtype=np.int32).reshape(n_token, n_strato, n_id)

# sequenza (token, strato, esperto)
eventi = []
for t in range(n_token):
    for L in range(n_strato):
        if dati[t, L, 0] < 0:
            continue
        for e in dati[t, L]:
            if e >= 0:
                eventi.append((t, L, int(e)))

strati_vivi = sorted({L for _, L, _ in eventi})
print('pista: %d token, %d domande, %d strati con router' % (n_token, len(eventi), len(strati_vivi)))

# --- LRU a SLOT, contando i buchi PER STRATO ---------------------------------
cache = OrderedDict()
buchi_strato = Counter()
dom_strato   = Counter()
for (t, L, e) in eventi:
    k = (L, e)
    dom_strato[L] += 1
    if k in cache:
        cache.move_to_end(k)
    else:
        buchi_strato[L] += 1
        if len(cache) >= SLOT:
            cache.popitem(last=False)
        cache[k] = True

tot_dom = sum(dom_strato.values())
tot_buchi = sum(buchi_strato.values())
print('LRU a %d slot: colpi %.1f%%, buchi %d (%.1f per token)' %
      (SLOT, 100.0*(1 - tot_buchi/tot_dom), tot_buchi, tot_buchi/n_token))

print('\n=== BUCHI PER STRATO (media per token, su 6 esperti) ===')
righe = []
for L in strati_vivi:
    b = buchi_strato[L] / n_token
    righe.append((L, b))
for L, b in righe:
    barra = '#' * int(round(b * 8))
    print('  strato %2d   %.2f mancanti  %s' % (L, b, barra))

med = np.mean([b for _, b in righe])
print('\nmedia %.2f mancanti per strato   (deviazione %.2f, min %.2f, max %.2f)'
      % (med, np.std([b for _, b in righe]), min(b for _, b in righe), max(b for _, b in righe)))

# --- il K per strato che ne discende, col vincolo della finestra CPU ----------
print('\n=== K PER STRATO PROPOSTO, e il conto della finestra CPU ===')
cap_cpu = FINESTRA_MS / CPU_MS
print('la CPU regge %.0f esperti per token nella finestra da %.0f ms' % (cap_cpu, FINESTRA_MS))

for tetto in (3, 4, 5):
    k = [(L, min(int(np.ceil(b)), tetto)) for L, b in righe]
    somma = sum(v for _, v in k)
    ms = somma * CPU_MS
    resta = sum(max(0.0, b - v) for (L, b), (_, v) in zip(righe, k))
    print('  tetto K=%d  ->  somma K = %3d esperti/token = %5.1f ms di CPU  (%s la finestra)   '
          'restano %.1f copie proibite/token'
          % (tetto, somma, ms, 'DENTRO' if ms <= FINESTRA_MS else 'FUORI', resta))

print('\n=== e se K fosse UNIFORME (com e oggi) ===')
for kf in (2, 3, 4):
    somma = kf * len(strati_vivi)
    ms = somma * CPU_MS
    resta = sum(max(0.0, b - kf) for _, b in righe)
    print('  K=%d ovunque  ->  %3d esperti/token = %5.1f ms  (%s)   restano %.1f copie proibite/token'
          % (kf, somma, ms, 'DENTRO' if ms <= FINESTRA_MS else 'FUORI', resta))
