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


# --- LE CANDIDATE IMPLEMENTABILI ------------------------------------------
# Belady dice quanto c'e' da prendere (+24 punti); queste dicono quanto se ne
# prende SENZA conoscere il futuro. Il fatto che conta, misurato sulla stessa
# traccia: di 258 coppie usate a un token, il 36,4% torna al token dopo. Una
# buona politica deve indovinare QUELLE.
#
#   lfu        pura frequenza: butta la meno chiamata di sempre
#   massa      quello che il nostro codice chiama massa: +1 a ogni domanda e
#              dimezzamento quando la scansione di sfratto la incontra
#              (cache-esperti.cu:1719 e :2400). E' frequenza con oblio.
#   slru       due segmenti: chi entra sta in "provvisorio", chi viene
#              riusato promuove in "protetto". Si sfratta dal provvisorio.
#              E' la difesa classica contro l'accesso ciclico.
#   riuso      tieni solo chi e' stato riusato almeno una volta da quando e'
#              entrato; a parita', LRU
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
    elif politica in ('lfu', 'massa'):
        import collections, heapq as hq
        res, freq, mucchio = {}, collections.defaultdict(int), []
        for i in range(N):
            g = int(G[i])
            freq[g] += 1
            if g in res:
                colpi += 1
            else:
                if len(res) >= K:
                    while True:
                        f, cand = hq.heappop(mucchio)
                        if cand in res and f == freq[cand]:
                            # l'oblio della `massa`: la scansione che incontra
                            # una candidata le dimezza il conto
                            if politica == 'massa':
                                freq[cand] >>= 1
                            del res[cand]
                            break
                res[g] = 1
            hq.heappush(mucchio, (freq[g], g))
    elif politica in ('slru', 'riuso'):
        import collections
        prov = collections.OrderedDict()   # provvisorio: entrato, mai riusato
        prot = collections.OrderedDict()   # protetto: riusato almeno una volta
        quota = K // 2 if politica == 'slru' else K   # slru: meta' protetta
        for i in range(N):
            g = int(G[i])
            if g in prot:
                colpi += 1; prot.move_to_end(g)
            elif g in prov:
                colpi += 1
                del prov[g]; prot[g] = 1
                while len(prot) > quota:                # il protetto trabocca
                    k, _ = prot.popitem(last=False)     # nel provvisorio
                    prov[k] = 1
            else:
                if len(prov) + len(prot) >= K:
                    if prov:
                        prov.popitem(last=False)
                    else:
                        prot.popitem(last=False)
                prov[g] = 1
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


POLITICHE = ['lru', 'lfu', 'massa', 'slru', 'riuso', 'consumato', 'belady']
print()
print('  ' + 'capienza'.ljust(10) + ''.join(p.upper().rjust(11) for p in POLITICHE))
righe = {}
for K in CAPIENZE:
    r = {p: simula(K, p) for p in POLITICHE}
    righe[K] = r
    print('  %-10d' % K + ''.join(('%.1f%%' % r[p]).rjust(11) for p in POLITICHE))
print()
print('  BELADY e\' il tetto assoluto: nessuna politica puo\' superarlo a quella')
print('  capienza. Le altre sono TUTTE implementabili senza conoscere il futuro.')
print()
print('  quanto del margine di Belady prende ciascuna (a %d slot):' % CAPIENZE[0])
r0 = righe[CAPIENZE[0]]
sp = r0['belady'] - r0['lru']
for p in POLITICHE:
    if p in ('lru', 'belady'):
        continue
    print('     %-10s %+6.1f punti sulla LRU   =  %5.1f%% del margine'
          % (p, r0[p] - r0['lru'], 100.0 * (r0[p] - r0['lru']) / sp if sp else 0.0))
print()
print('  NB: `massa` e\' quello che il nostro codice implementa gia\'')
print('  (cache-esperti.cu:1719 e :2400), ed e\' spento di difetto.')
