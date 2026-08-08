"""
LA TESI DELL'UTENTE, misurata sulla pista vera invece che discussa.

Tre affermazioni, tre cancelli:

  1. "il 30% minimo e' identico a ogni token"
     -> esiste un NUCLEO CALDO che quasi tutti i token toccano?
        (diverso dalla sovrapposizione a coppie: quella e' 39,7% ma potrebbe
        essere fatta ogni volta da esperti diversi)

  2. "con 380 slot dovremmo avere margine quasi per due token consecutivi"
     -> quanto vale l'unione di due token consecutivi?

  3. "anche mettendo esperti a caso faremmo meglio di ora"
     -> sfratto CASUALE contro l'orologio di produzione

E la politica che ne segue, che e' l'architettura proposta:
     PIN dei piu' caldi + resto a rotazione. Quanti pinnare, e quanto rende?
"""

import sys, struct, random
import numpy as np
from collections import OrderedDict, Counter

PISTA = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\pista2.bin'
random.seed(12345)

with open(PISTA, 'rb') as f:
    assert f.read(8) == b'ORACOLO1'
    n_token, n_strato, n_id = struct.unpack('<iii', f.read(12))
    dati = np.fromfile(f, dtype=np.int32).reshape(n_token, n_strato, n_id)

per_tok = []
for t in range(n_token):
    v = []
    for L in range(n_strato):
        r = dati[t, L]
        if r[0] < 0:
            continue
        for e in r:
            if e >= 0:
                v.append((L << 16) | int(e))
    per_tok.append(v)

seq = [k for v in per_tok for k in v]
N = len(seq)
print('pista: %d token, %d domande (%.1f per token)' % (n_token, N, N / n_token))

# ---------------------------------------------------------------- 1. IL NUCLEO
freq = Counter(seq)
distinti = len(freq)
print('\n=== 1. IL NUCLEO CALDO ===')
print('esperti distinti toccati in tutta la pista: %d su %d possibili (%.1f%%)'
      % (distinti, n_strato * 256, 100.0 * distinti / (n_strato * 256)))

# in quanti token compare ciascuno
presenza = Counter()
for v in per_tok:
    for k in set(v):
        presenza[k] += 1

print('\nesperti presenti in almeno X%% dei token:')
for soglia in (0.99, 0.95, 0.90, 0.75, 0.50, 0.25, 0.10):
    n = sum(1 for k, c in presenza.items() if c >= soglia * n_token)
    # quanta parte della DOMANDA totale coprirebbero
    cop = sum(freq[k] for k, c in presenza.items() if c >= soglia * n_token)
    print('   >= %3.0f%% dei token: %5d esperti (%6.1f MiB)  coprono il %4.1f%% delle domande'
          % (100 * soglia, n, n * 6.75, 100.0 * cop / N))

print('\nil TOP-N per frequenza, e quanta domanda copre:')
top = [k for k, _ in freq.most_common()]
cum = 0
for n in (64, 128, 192, 256, 320, 380, 448, 512, 640):
    cop = sum(freq[k] for k in top[:n])
    print('   top %4d (%6.1f MiB)  copre il %4.1f%% delle domande' % (n, n * 6.75, 100.0 * cop / N))

# ------------------------------------------------------- 2. UNIONE DI DUE TOKEN
print('\n=== 2. QUANTO VALE L\'UNIONE DI TOKEN CONSECUTIVI ===')
for w in (1, 2, 3, 4):
    u = [len(set().union(*[set(per_tok[t - j]) for j in range(w)])) for t in range(w, n_token)]
    print('   unione di %d token: media %5.1f esperti (%6.1f MiB) -- con 380 slot: %s'
          % (w, np.mean(u), np.mean(u) * 6.75,
             'CI STA' if np.mean(u) <= 380 else 'NON ci sta (%.0f slot)' % np.mean(u)))

# ------------------------------------------------------------- 3. LE POLITICHE
def orologio(seq, slot, pin=frozenset()):
    """second-chance, quello che gira in produzione. Gli slot PIN sono fissi."""
    fissi = {}
    for i, k in enumerate(list(pin)[:slot]):
        fissi[k] = i
    n_pin = len(fissi)
    liberi = slot - n_pin
    slots = [None] * liberi
    dove = {}
    usato = [0] * liberi
    mano = 0
    colpi = 0
    for k in seq:
        if k in fissi:
            colpi += 1
            continue
        if liberi == 0:
            continue
        s = dove.get(k, -1)
        if s >= 0 and slots[s] == k:
            usato[s] = 1; colpi += 1; continue
        for _ in range(2 * liberi):
            if slots[mano] is None or usato[mano] == 0:
                break
            usato[mano] = 0
            mano = (mano + 1) % liberi
        v = slots[mano]
        if v is not None:
            dove.pop(v, None)
        slots[mano] = k; dove[k] = mano; usato[mano] = 1
        mano = (mano + 1) % liberi
    return colpi / len(seq)

def casuale(seq, slot):
    """sfratto CASUALE: il controllo che l'utente chiede."""
    dentro = set()
    lista = []
    colpi = 0
    for k in seq:
        if k in dentro:
            colpi += 1
            continue
        if len(lista) >= slot:
            j = random.randrange(len(lista))
            dentro.discard(lista[j])
            lista[j] = k
        else:
            lista.append(k)
        dentro.add(k)
    return colpi / len(seq)

def lru(seq, slot, pin=frozenset()):
    fissi = set(list(pin)[:slot])
    liberi = slot - len(fissi)
    c = OrderedDict(); colpi = 0
    for k in seq:
        if k in fissi:
            colpi += 1; continue
        if liberi <= 0:
            continue
        if k in c:
            c.move_to_end(k); colpi += 1
        else:
            if len(c) >= liberi:
                c.popitem(last=False)
            c[k] = True
    return colpi / len(seq)

print('\n=== 3. LE POLITICHE, senza pin ===')
for s in (320, 380, 448, 512):
    print('   %4d slot   orologio %5.1f%%   CASUALE %5.1f%%   LRU %5.1f%%'
          % (s, 100 * orologio(seq, s), 100 * casuale(seq, s), 100 * lru(seq, s)))

print('\n=== 4. PIN DEI CALDI + RESTO A ROTAZIONE (l\'architettura proposta) ===')
for s in (320, 380, 448, 512):
    riga = '   %4d slot: ' % s
    for p in (0, 64, 128, 192, 256):
        if p >= s:
            continue
        h = lru(seq, s, frozenset(top[:p]))
        riga += ' pin%3d=%5.1f%%' % (p, 100 * h)
    print(riga)

print('\nLETTURA: se il pin non batte la rotazione pura, il nucleo caldo non esiste')
print('come massa fissa e la capienza va spesa tutta in buffer.')
