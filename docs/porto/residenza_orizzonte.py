"""
VERIFICA DELLA CURVA DI BELADY A ORIZZONTE LIMITATO -- e la domanda che decide.

Codex (cantiere orizzonte, 8/8) riporta sulla stessa pista, 320 slot:

    k=0  39,7%   k=1  50,5%   k=2  54,6%   k=4  59,5%   k=8  62,0%   k=inf 62,1%

con tre cancelli: k=0 == LRU, monotona, k=inf == Belady. Non ha potuto usare il
nostro interprete (sandbox) e ha scritto un'implementazione propria. Qui la
rifaccio con il nostro simulatore, che e' quello che ha prodotto i riferimenti.

MA il punto vero non e' "quanti TOKEN" di orizzonte: e' quante DOMANDE sono
visibili al momento dello sfratto. Al livello L conosciamo le route calcolate
FINO a L, non quelle di L+1..42. Un token intero e' ~258 domande, cioe' 43
strati di futuro che NON abbiamo. Un blocco speculativo di P posizioni ci da'
soltanto le altre posizioni ALLO STESSO STRATO: 6*(P-1) domande.

Quindi misuro la curva in DOMANDE, non in token, e in piu' simulo l'ordine
layer-major che il blocco impone davvero -- con la sua LRU di controllo, perche'
cambiare l'ordine cambia il tasso di colpi da solo.
"""

import sys, struct
from collections import OrderedDict
import numpy as np

PISTA = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\pista2.bin'
SLOT  = int(sys.argv[2]) if len(sys.argv) > 2 else 320
INF   = 1 << 62

with open(PISTA, 'rb') as f:
    assert f.read(8) == b'ORACOLO1'
    n_token, n_strato, n_id = struct.unpack('<iii', f.read(12))
    dati = np.fromfile(f, dtype=np.int32).reshape(n_token, n_strato, n_id)

print('pista: %d token x %d strati x %d id' % (n_token, n_strato, n_id))

# per token: lista di (strato, chiave), saltando gli strati non instradati
per_tok = []
for t in range(n_token):
    v = []
    for L in range(n_strato):
        riga = dati[t, L]
        if riga[0] < 0:
            continue
        for e in riga:
            if e >= 0:
                v.append((L, (L << 16) | int(e)))
    per_tok.append(v)

seq_token_major = [k for v in per_tok for (_, k) in v]
lay_token_major = [L for v in per_tok for (L, _) in v]
print('domande totali: %d   (%.1f per token)'
      % (len(seq_token_major), len(seq_token_major) / n_token))


def blocco_layer_major(P):
    """L'ordine che il blocco speculativo impone DAVVERO: le P posizioni
    attraversano ogni strato INSIEME. Restituisce (sequenza, strato, gruppo)
    dove `gruppo` identifica il layer-group -- l'unico futuro visibile."""
    seq, lay, grp = [], [], []
    g = 0
    for base in range(0, n_token, P):
        pos = per_tok[base:base + P]
        for L in range(n_strato):
            fetta = [(l, k) for v in pos for (l, k) in v if l == L]
            if not fetta:
                continue
            for (l, k) in fetta:
                seq.append(k); lay.append(l); grp.append(g)
            g += 1
    return seq, lay, grp


def prossimo_uso(seq):
    """futuro[i] = prossimo indice della STESSA chiave dopo i, o INF."""
    fut = [0] * len(seq)
    visto = {}
    for i in range(len(seq) - 1, -1, -1):
        fut[i] = visto.get(seq[i], INF)
        visto[seq[i]] = i
    return fut


def simula_lru(seq, slot):
    cache, colpi = OrderedDict(), 0
    for k in seq:
        if k in cache:
            cache.move_to_end(k); colpi += 1
        else:
            if len(cache) >= slot:
                cache.popitem(last=False)
            cache[k] = True
    return colpi / len(seq)


def simula_orizzonte(seq, slot, limite):
    """Belady a orizzonte limitato.

        fra gli slot il cui prossimo uso e' VISIBILE, sfratta quello piu' lontano;
        se qualche slot non ha uso visibile, sfratta il meno recente FRA QUELLI.

    `limite(i)` restituisce l'indice oltre il quale il futuro non e' visibile.
    limite = i     -> niente visibile -> deve coincidere con LRU
    limite = INF   -> tutto visibile  -> deve coincidere con Belady
    """
    fut = prossimo_uso(seq)
    chiave = np.full(slot, -1, dtype=np.int64)   # chiave nello slot
    nxt    = np.full(slot,  0, dtype=np.int64)   # suo prossimo uso
    ultimo = np.full(slot, -1, dtype=np.int64)   # sua ultima domanda (recency)
    dove   = {}
    libero, colpi = 0, 0

    for i, k in enumerate(seq):
        s = dove.get(k, -1)
        if s >= 0:
            colpi += 1
        elif libero < slot:
            s = libero; libero += 1
        else:
            lim = limite(i)
            visibile = nxt <= lim
            if visibile.all():
                s = int(np.argmax(nxt))               # il piu' lontano
            else:
                cieco = np.where(~visibile)[0]
                s = int(cieco[np.argmin(ultimo[cieco])])   # LRU fra i ciechi
            dove.pop(int(chiave[s]), None)
        chiave[s] = k; dove[k] = s
        nxt[s] = fut[i]; ultimo[s] = i
    return colpi / len(seq)


D = len(seq_token_major) / n_token     # domande per token

print('\n=== CANCELLI (ordine token-major, %d slot) ===' % SLOT)
lru = simula_lru(seq_token_major, SLOT)
bel = simula_orizzonte(seq_token_major, SLOT, lambda i: INF)
zer = simula_orizzonte(seq_token_major, SLOT, lambda i: i)
print('  LRU                       %5.1f%%' % (100 * lru))
print('  orizzonte 0 (deve == LRU) %5.1f%%   %s'
      % (100 * zer, 'OK' if abs(zer - lru) < 1e-9 else '<<< CANCELLO FALLITO'))
print('  BELADY (orizzonte inf)    %5.1f%%' % (100 * bel))

print('\n=== LA CURVA IN TOKEN (il conto di Codex) ===')
prec = None
for k in (0, 1, 2, 4, 8, 16):
    h = simula_orizzonte(seq_token_major, SLOT, lambda i, k=k: i + int(k * D))
    seg = '' if prec is None or h >= prec - 1e-12 else '   <<< NON MONOTONA'
    print('  k = %2d token (%6d domande)   %5.1f%%   (+%4.1f su LRU)%s'
          % (k, int(k * D), 100 * h, 100 * (h - lru), seg))
    prec = h

print('\n=== LA CURVA IN DOMANDE -- quella che decide la portabilita\' ===')
print('    (allo strato L conosciamo le route fino a L: 6 domande per posizione)')
for H in (0, 6, 12, 24, 48, 129, 258, 516, 1032):
    h = simula_orizzonte(seq_token_major, SLOT, lambda i, H=H: i + H)
    print('  %5d domande avanti (%4.1f strati)   %5.1f%%   (+%4.1f su LRU)'
          % (H, H / 6.0, 100 * h, 100 * (h - lru)))

print('\n=== E ORA L\'ORDINE VERO DEL BLOCCO (layer-major, P posizioni) ===')
print('    il controllo LRU e\' rifatto sullo STESSO ordine: cambiare l\'ordine')
print('    sposta i colpi da solo, e va tolto prima di attribuire alla politica')
for P in (2, 4):
    seq, lay, grp = blocco_layer_major(P)
    grp = np.array(grp)
    # fine del layer-group corrente: l'ultimo indice con lo stesso gruppo
    fine = np.zeros(len(seq), dtype=np.int64)
    ultimo_di = {}
    for i, g in enumerate(grp):
        ultimo_di[g] = i
    for i, g in enumerate(grp):
        fine[i] = ultimo_di[g]
    l2 = simula_lru(seq, SLOT)
    imp = simula_orizzonte(seq, SLOT, lambda i: int(fine[i]))
    tetto = simula_orizzonte(seq, SLOT, lambda i: INF)
    print('  P=%d  LRU %.1f%%   |  orizzonte = FINE DEL LAYER-GROUP: %.1f%%  (+%.1f)'
          '   |  Belady su stesso ordine %.1f%%'
          % (P, 100 * l2, 100 * imp, 100 * (imp - l2), 100 * tetto))
