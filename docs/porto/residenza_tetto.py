"""
IL 33,7% E' IL PATTERN O E' LA NOSTRA POLITICA?

Con 320 slot e 258 esperti per token abbiamo il 124% del fabbisogno di UN token.
Se molti esperti si riusassero fra token consecutivi, una politica migliore
dovrebbe tenerne dentro molti di piu' del 33,7% che misuriamo con l'orologio.

Questo script risponde OFFLINE, sulla pista gia' registrata, confrontando:

  ORACOLO (Belady)  sfratta quello il cui prossimo uso e' PIU' LONTANO.
                    E' il massimo teorico: nessuna politica online puo' batterlo.
  LRU               sfratta il meno recentemente usato.
  ORLOGIO           second-chance, cioe' quello che gira in produzione.
  FIFO              per avere un pavimento.

Se Belady da' ~70% e noi 33,7%, meta' del guadagno e' sul tavolo e la politica
va cambiata. Se Belady da' ~40%, il pattern e' diffuso e nessuna politica salva:
allora la strada e' un'altra (mandare i buchi alla CPU, che costa 0,242 ms e
zero PCIe, invece di inseguire la residenza).

Stampa anche la SOVRAPPOSIZIONE fra token consecutivi, che e' la quantita' che
l'utente ha chiamato "molti si riusano": e' il tetto naturale di qualunque
politica che guardi solo indietro.
"""

import sys, struct
from collections import OrderedDict
import numpy as np

PISTA = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\pista2.bin'
SLOT  = int(sys.argv[2]) if len(sys.argv) > 2 else 320

with open(PISTA, 'rb') as f:
    magia = f.read(8)
    assert magia == b'ORACOLO1', 'pista non valida: %r' % magia
    n_token, n_strato, n_id = struct.unpack('<iii', f.read(12))
    dati = np.fromfile(f, dtype=np.int32)

dati = dati.reshape(n_token, n_strato, n_id)
print('pista: %d token x %d strati x %d id  (%s)' % (n_token, n_strato, n_id, PISTA))

# --- la sequenza di domande: una chiave (strato, esperto) per uso -------------
# gli strati senza pianificazione hanno -1 nella prima posizione
sequenze = []          # per token: lista di chiavi
for t in range(n_token):
    chiavi = []
    for L in range(n_strato):
        riga = dati[t, L]
        if riga[0] < 0:
            continue
        for e in riga:
            if e >= 0:
                chiavi.append((L << 16) | int(e))
    sequenze.append(chiavi)

per_token = [len(s) for s in sequenze]
print('chiavi per token: media %.1f  (min %d, max %d)' %
      (np.mean(per_token), min(per_token), max(per_token)))

# --- quanto si riusa fra token CONSECUTIVI -----------------------------------
sovr = []
for t in range(1, n_token):
    a, b = set(sequenze[t-1]), set(sequenze[t])
    if b:
        sovr.append(len(a & b) / len(b))
print('sovrapposizione fra token consecutivi: %.1f%%   <- il tetto di chi guarda solo indietro'
      % (100.0 * np.mean(sovr)))

# quanto si riusa dentro una FINESTRA di N token (il tetto di una cache da N token)
for finestra in (2, 4, 8, 16):
    q = []
    for t in range(finestra, n_token):
        prec = set()
        for k in range(1, finestra + 1):
            prec |= set(sequenze[t-k])
        b = set(sequenze[t])
        if b:
            q.append(len(prec & b) / len(b))
    print('   dentro %2d token precedenti: %.1f%%' % (finestra, 100.0 * np.mean(q)))

# --- le politiche -------------------------------------------------------------
piatta = [k for s in sequenze for k in s]
N = len(piatta)
print('\ndomande totali: %d' % N)

def simula_lru(seq, slot):
    cache = OrderedDict()
    colpi = 0
    for k in seq:
        if k in cache:
            cache.move_to_end(k); colpi += 1
        else:
            if len(cache) >= slot:
                cache.popitem(last=False)
            cache[k] = True
    return colpi / len(seq)

def simula_fifo(seq, slot):
    from collections import deque
    dentro, coda = set(), deque()
    colpi = 0
    for k in seq:
        if k in dentro:
            colpi += 1
        else:
            if len(coda) >= slot:
                dentro.discard(coda.popleft())
            coda.append(k); dentro.add(k)
    return colpi / len(seq)

def simula_orologio(seq, slot):
    """second-chance: quello che gira in produzione."""
    slots = [None] * slot
    dove  = {}
    usato = [0] * slot
    mano  = 0
    colpi = 0
    for k in seq:
        s = dove.get(k, -1)
        if s >= 0 and slots[s] == k:
            usato[s] = 1; colpi += 1
            continue
        # cammina la lancetta cercando usato==0
        for _ in range(2 * slot):
            if slots[mano] is None or usato[mano] == 0:
                break
            usato[mano] = 0
            mano = (mano + 1) % slot
        v = slots[mano]
        if v is not None:
            dove.pop(v, None)
        slots[mano] = k; dove[k] = mano; usato[mano] = 1
        mano = (mano + 1) % slot
    return colpi / len(seq)

def simula_belady(seq, slot):
    """OTTIMO: sfratta quello il cui prossimo uso e' piu' lontano."""
    prossimo = {}
    futuro = [0] * len(seq)
    for i in range(len(seq) - 1, -1, -1):
        futuro[i] = prossimo.get(seq[i], len(seq) + 1)
        prossimo[seq[i]] = i
    dentro = set()
    colpi = 0
    import heapq
    mucchio = []           # (-prossimo_uso, chiave)
    for i, k in enumerate(seq):
        if k in dentro:
            colpi += 1
        else:
            if len(dentro) >= slot:
                while mucchio:
                    negp, kk = heapq.heappop(mucchio)
                    if kk in dentro:
                        dentro.discard(kk); break
            dentro.add(k)
        heapq.heappush(mucchio, (-futuro[i], k))
    return colpi / len(seq)

print('\n=== TASSO DI COLPI CON %d SLOT ===' % SLOT)
for nome, fn in (('FIFO', simula_fifo), ('OROLOGIO (produzione)', simula_orologio),
                 ('LRU', simula_lru), ('BELADY (ottimo)', simula_belady)):
    print('  %-24s %5.1f%%' % (nome, 100.0 * fn(piatta, SLOT)))

print('\n=== E SE AVESSIMO PIU' + "'" + ' SLOT (con Belady) ===')
for s in (320, 480, 640, 960, 1280):
    print('  %5d slot (%5.0f MiB)   %5.1f%%' % (s, s * 6.75, 100.0 * simula_belady(piatta, s)))

print('\nLETTURA: se BELADY e OROLOGIO sono vicini, il pattern e diffuso e nessuna')
print('politica salva -- la strada e mandare i buchi alla CPU (0,242 ms, zero PCIe).')
print('Se BELADY e molto sopra, meta del guadagno e sul tavolo ed e una questione')
print('di politica, non di capienza.')
