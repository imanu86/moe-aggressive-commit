"""
QUANTO VALE LO SFRATTO, sulla traccia vera. Nessuna GPU.

Domanda dell'utente (11/8): con un numero di slot limitato ci sono esperti usati
in questo strato e non nel prossimo che siamo costretti a tenere -- e il
prefetch, per fare posto, e' costretto a buttare roba ancora viva.

LA PRECISAZIONE CHE CAMBIA IL CONTO: due strati non condividono MAI un
residente. L'unita' e' la coppia (strato, esperto); lo strato 20 esperto 7 e lo
strato 21 esperto 7 sono due blocchi da 6,75 MiB in due slot diversi. Quindi
ogni esperto e' MORTO nell'istante in cui il suo strato finisce, e non servira'
piu' fino a quando il token successivo arrivera' allo stesso strato: 43 strati
dopo. E' il candidato allo sfratto perfetto -- e la LRU lo tiene, perche' e'
"usato di recente". E' il caso patologico da manuale.

Quattro politiche sulla stessa traccia, stessa capienza:

  LRU        quella di oggi
  CONSUMATO  butta per prima una coppia gia' usata IN QUESTO TOKEN (il suo
             strato e' passato): sappiamo con CERTEZZA che non serve piu' per
             ~43 strati. Pari merito -> LRU. E' implementabile senza oracolo:
             basta il numero di strato corrente.
  BELADY     l'ottimo: butta quella il cui prossimo uso e' piu' lontano.
             Nessuna politica puo' fare meglio a parita' di capienza. E' il
             TETTO, non una proposta.
  IDEALE     capienza infinita, per vedere quanto della miss e' obbligatoria
             (prima volta che si vede una coppia).

  uso: simula_sfratto.py <cartella_dump> [K ...]
"""

import sys, os, re
import numpy as np
import heapq

if len(sys.argv) < 2:
    print('uso: simula_sfratto.py <cartella_dump> [K ...]')
    sys.exit(2)
SRC = sys.argv[1]
CAPIENZE = [int(x) for x in sys.argv[2:]] or [339, 448, 512]
N_ID, N_EXP = 6, 256


def carica_indice(src):
    idx, forme = os.path.join(src, 'INDICE.tsv'), {}
    if not os.path.exists(idx):
        return forme
    with open(idx, 'r', encoding='utf-8', errors='replace') as f:
        intest = f.readline().rstrip('\n').split('\t')
        col = {n: i for i, n in enumerate(intest)}
        for riga in f:
            c = riga.rstrip('\n').split('\t')
            if len(c) >= len(intest):
                forme[c[col['file']]] = (int(c[col['ne0']]), int(c[col['ne1']]), int(c[col['byte']]))
    return forme


def leggi(path, forma):
    a = np.fromfile(path, dtype=np.int32)
    if forma is None:
        return a.reshape(-1, N_ID)
    ne0, ne1, byte = forma
    if ne1 == 1 or byte == ne0 * ne1 * 4:
        return a[:ne0 * ne1].reshape(ne1, ne0)
    passo = (byte - ne0 * 4) // ((ne1 - 1) * 4)
    piena = a[:(ne1 - 1) * passo].reshape(ne1 - 1, passo)
    out = np.empty((ne1, N_ID), dtype=np.int32)
    out[:ne1 - 1] = piena[:, :N_ID]
    out[ne1 - 1] = a[(ne1 - 1) * passo:(ne1 - 1) * passo + N_ID]
    return out


FORME = carica_indice(SRC)
rx = re.compile(r'^ffn_moe_topk-(\d+)\.(\d+)\.bin$')
per_strato = {}
for nome in os.listdir(SRC):
    m = rx.match(nome)
    if m:
        per_strato.setdefault(int(m.group(1)), []).append((int(m.group(2)), os.path.join(SRC, nome)))
strati = sorted(per_strato)
tracce = {L: np.concatenate([leggi(p, FORME.get(os.path.basename(p)))
                             for _, p in sorted(per_strato[L])], axis=0) for L in strati}
n_tok = min(t.shape[0] for t in tracce.values())
n_str = len(strati)

# la sequenza di accessi, in ORDINE DI ESECUZIONE: token, poi strato, poi i sei
E = np.stack([tracce[L][:n_tok] for L in strati], axis=1)          # [t, L, k]
G = (np.arange(n_str)[None, :, None] * N_EXP + E).reshape(-1)      # coppia globale
STR = np.tile(np.repeat(np.arange(n_str), N_ID), n_tok)            # strato di ogni accesso
N = G.size
print('%s: %d token x %d strati x %d id = %s accessi, %s coppie distinte'
      % (os.path.basename(SRC), n_tok, n_str, N_ID,
         format(N, ',d').replace(',', '.'),
         format(len(np.unique(G)), ',d').replace(',', '.')))

# prossimo uso di ogni accesso (per Belady), calcolato all'indietro
prossimo = np.full(N, N, dtype=np.int64)
ultimo = {}
for i in range(N - 1, -1, -1):
    g = int(G[i])
    if g in ultimo:
        prossimo[i] = ultimo[g]
    ultimo[g] = i
obbligatorie = int((np.array([prossimo[i] for i in range(N)]) >= 0).sum() and
                   len(np.unique(G)))
print('  miss obbligatorie (prima volta che si vede una coppia): %s = %.1f%%'
      % (format(obbligatorie, ',d').replace(',', '.'), 100.0 * obbligatorie / N))


def simula(K, politica):
    dove = {}                      # coppia -> nulla, sta solo per appartenenza
    colpi = 0
    if politica == 'lru':
        import collections
        res = collections.OrderedDict()
        for i in range(N):
            g = int(G[i])
            if g in res:
                colpi += 1; res.move_to_end(g)
            else:
                if len(res) >= K: res.popitem(last=False)
                res[g] = 1
    elif politica == 'consumato':
        import collections
        res = collections.OrderedDict()   # ordine LRU
        strato_di = {}                    # coppia -> strato (fisso)
        tok_di = {}                       # coppia -> ultimo token che l'ha usata
        for i in range(N):
            g, L = int(G[i]), int(STR[i]); t = i // (n_str * N_ID)
            if g in res:
                colpi += 1; res.move_to_end(g); tok_di[g] = t
            else:
                if len(res) >= K:
                    # prima vittima: una coppia gia' consumata IN QUESTO TOKEN
                    vittima = None
                    for cand in res:                      # dal meno recente
                        if tok_di.get(cand, -1) == t and strato_di[cand] < L:
                            vittima = cand; break
                    if vittima is None:
                        vittima = next(iter(res))         # ripiego: LRU
                    del res[vittima]
                res[g] = 1; strato_di[g] = L; tok_di[g] = t
    elif politica == 'belady':
        res = set(); mucchio = []          # (-prossimo_uso, coppia)
        vivo = {}
        for i in range(N):
            g = int(G[i])
            if g in res:
                colpi += 1
            else:
                if len(res) >= K:
                    while True:
                        neg, cand = heapq.heappop(mucchio)
                        if cand in res and vivo.get(cand) == -neg:
                            res.discard(cand); vivo.pop(cand, None); break
                res.add(g)
            vivo[g] = int(prossimo[i])
            heapq.heappush(mucchio, (-int(prossimo[i]), g))
    return 100.0 * colpi / N


print()
print('  capienza     LRU     CONSUMATO     BELADY (tetto)')
for K in CAPIENZE:
    l = simula(K, 'lru')
    c = simula(K, 'consumato')
    b = simula(K, 'belady')
    print('  %5d %8.1f%% %10.1f%% %12.1f%%      (%+.1f e %+.1f punti sulla LRU)'
          % (K, l, c, b, c - l, b - l))
print()
print('  BELADY e\' il tetto assoluto: nessuna politica di sfratto puo\' superarlo')
print('  a quella capienza. Se CONSUMATO ci arriva vicino, e\' implementabile')
print('  SENZA oracolo -- basta il numero di strato corrente.')
