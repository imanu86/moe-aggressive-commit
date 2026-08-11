"""
ORCHESTRARE LA RESIDENZA SUI PROSSIMI W TOKEN (idea dell'utente, 11/8).

«il draft ci puo' dare fino a cinque token, non ci serve verificarli tutti;
potremmo verificarne due come ora, ma anticipare un'orchestrazione per MASSA
sui prossimi 5 token»

E' un uso diverso della stessa informazione. Oggi la testa Markov di DSpark ha
`block_size=5` e ne consumiamo due per la verifica; gli altri tre si buttano.
Qui si usano per decidere CHI STA IN VRAM.

## Perche' e' diverso da tutto quello che e' caduto oggi

Il prefetch con pianificazione ESATTA ha dato zero (5,97 t/s contro 5,89 del
cieco): ma quello decideva, strato per strato, COSA PORTARE, e il macchinario
ritrasportava ogni esperto due volte e univa subito. Questo decide, una volta
ogni W token, CHI TENERE -- e' una politica di residenza, non un prefetch.

E le euristiche di sfratto senza futuro hanno dato tutte peggio della LRU. Il
futuro qui c'e': lo produce la bozza.

## Il modello

Ogni W token si rifa' l'insieme residente: i migliori K per MASSA (peso x
frequenza) sulla finestra dei prossimi W token. Fra un rifacimento e l'altro la
cache serve a domanda; i mancanti entrano sfrattando col criterio di riserva.

Si misura:
  colpi           quanto si guadagna
  installazioni   quanto costa: ogni installazione e' 6,75 MiB sul bus, e il
                  bus va a 24 GiB/s ma lavora al 22% ([[trasporto-chiuso-tre-angoli]])
  distinti nella finestra    se superano K, l'orizzonte e' troppo lungo per la
                  capienza e la politica si sabota da sola

CONFRONTI, sulla stessa traccia: LRU 40,3% a 339 slot, Belady 63,4%.
E il regime vero misurato in produzione: 53-56% di colpi.

  uso: simula_anticipo.py <cartella_dump> [K] [W ...]
"""

import sys, os, re
import numpy as np

if len(sys.argv) < 2:
    print('uso: simula_anticipo.py <cartella_dump> [K] [W ...]')
    sys.exit(2)
SRC = sys.argv[1]
K   = int(sys.argv[2]) if len(sys.argv) > 2 else 339
FIN = [int(x) for x in sys.argv[3:]] or [1, 2, 3, 5, 8, 16]
N_ID, N_EXP, MIB = 6, 256, 6.75


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
                ne0, ne1, ne2 = int(c[col['ne0']]), int(c[col['ne1']]), int(c[col['ne2']])
                if ne0 == 1 and ne1 == N_ID:
                    ne0, ne1 = ne1, ne2
                forme[c[col['file']]] = (ne0, ne1, int(c[col['byte']]))
    return forme


def leggi(path, forma, dtype):
    a = np.fromfile(path, dtype=dtype)
    if forma is None:
        return a.reshape(-1, N_ID)
    ne0, ne1, byte = forma
    if ne1 == 1 or byte == ne0 * ne1 * 4:
        return a[:ne0 * ne1].reshape(ne1, ne0)
    passo = (byte - ne0 * 4) // ((ne1 - 1) * 4)
    piena = a[:(ne1 - 1) * passo].reshape(ne1 - 1, passo)
    out = np.empty((ne1, N_ID), dtype=dtype)
    out[:ne1 - 1] = piena[:, :N_ID]
    out[ne1 - 1] = a[(ne1 - 1) * passo:(ne1 - 1) * passo + N_ID]
    return out


def raccogli(prefisso, dtype):
    rx = re.compile(r'^' + prefisso + r'-(\d+)\.(\d+)\.bin$')
    per = {}
    for nome in os.listdir(SRC):
        m = rx.match(nome)
        if m:
            per.setdefault(int(m.group(1)), []).append((int(m.group(2)), os.path.join(SRC, nome)))
    if not per:
        return None, None
    st = sorted(per)
    return st, {L: np.concatenate([leggi(p, FORME.get(os.path.basename(p)), dtype)
                                   for _, p in sorted(per[L])], axis=0) for L in st}


FORME = carica_indice(SRC)
strati, topk = raccogli('ffn_moe_topk', np.int32)
if strati is None:
    print('nessun ffn_moe_topk-*.bin in %s' % SRC); sys.exit(1)
pesi = None
for nome in ('ffn_moe_weights_norm', 'ffn_moe_weights_scaled', 'ffn_moe_weights'):
    _, tw = raccogli(nome, np.float32)
    if tw is not None:
        pesi = tw; break

n_tok = min(t.shape[0] for t in topk.values())
n_str = len(strati)
E = np.stack([topk[L][:n_tok] for L in strati], axis=1)              # [t, L, k]
G = (np.arange(n_str)[None, :, None] * N_EXP + E).reshape(n_tok, -1) # [t, 258]
if pesi is not None:
    W = np.stack([pesi[L][:n_tok] for L in strati], axis=1)
    P = (W / W.sum(axis=2, keepdims=True)).reshape(n_tok, -1)
else:
    P = np.ones_like(G, dtype=np.float32)
DOM = G.shape[1]
p = lambda n: format(int(n), ',d').replace(',', '.')
print('%s: %s token x %d strati, %d domande/token, K = %s slot'
      % (os.path.basename(SRC), p(n_tok), n_str, DOM, p(K)))
print()
print('    W   distinti     colpi   installazioni   MiB/token   (K=%s)' % p(K))
print('        in finestra           per token')

N_COPPIE = n_str * N_EXP
for Wf in FIN:
    residenti = set()
    colpi = dom = inst = 0
    dist_tot = n_fin = 0
    for t in range(n_tok):
        if t % Wf == 0:
            # RIFACIMENTO: i migliori K per massa sui prossimi W token
            a, b = t, min(t + Wf, n_tok)
            g, w = G[a:b].ravel(), P[a:b].ravel()
            acc = np.bincount(g, weights=w, minlength=N_COPPIE)
            vivi = int((acc > 0).sum())
            dist_tot += vivi; n_fin += 1
            tenuti = np.flatnonzero(acc) if vivi <= K else np.argpartition(-acc, K)[:K]
            nuovo = set(tenuti.tolist())
            inst += len(nuovo - residenti)       # cio' che va portato davvero
            residenti = nuovo
        for g in G[t]:
            dom += 1
            if int(g) in residenti:
                colpi += 1
            else:
                # a domanda: entra comunque, sfrattando (la cache non resta a
                # guardare). Il costo lo conto come installazione.
                inst += 1
                if len(residenti) >= K:
                    residenti.pop()
                residenti.add(int(g))
    print('  %3d   %8s   %6.1f%%   %11.1f   %9.1f'
          % (Wf, p(dist_tot / max(1, n_fin)), 100.0 * colpi / dom,
             inst / n_tok, inst / n_tok * MIB))

print()
print('  confronti sulla STESSA traccia: LRU %.1f%%, Belady %.1f%% (simula_sfratto.py)'
      % (40.3, 63.4))
print('  e in produzione la cache misura 53-56%% di colpi.')
print()
print('  COME SI LEGGE. Se i distinti nella finestra superano K, la politica si')
print('  sabota: promette residenza a piu' + "'" + ' esperti di quanti ne tenga. E le')
print('  installazioni sono il prezzo: a 6,75 MiB l\'una su un bus da 24 GiB/s che')
print('  oggi lavora al 22%, 100 installazioni/token sono 675 MiB = 27 ms di bus.')
