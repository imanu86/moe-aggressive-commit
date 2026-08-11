"""
QUANTI ESPERTI DISTINTI CHIAMA DAVVERO UNA SESSIONE?

Domanda dell'utente, 11/8: «quanti esperti chiamiamo nel prompt neuraforge
durante tutta la corsa fino a 8k».

Non e' la domanda dei COLPI. I colpi dicono quante volte la cache aveva gia'
quello che serviva; questo dice di quanti esperti DIVERSI ha bisogno una
generazione intera. Sono due numeri diversi e il secondo non l'abbiamo mai
misurato: nel codice non esiste nessun contatore di distinti.

INGRESSO: la cartella di dump di common/debug.cpp, cioe' i file
    ffn_moe_topk-<strato>.<chiamata>.bin
prodotti con LLAMA_DEBUG_DUMP=<cartella> e LLAMA_DEBUG_FILTER=ffn_moe_topk.

## IL PASSO. Leggere questi file come un array [n_token, 6] E' SBAGLIATO.

`ffn_moe_topk` non e' un tensore suo: e' una VISTA dei primi 6 elementi di
ogni riga di `ffn_moe_argsort`, che ha 256 colonne. `ggml_nbytes` di una vista
misura l'ESTENSIONE, non il contenuto, quindi il file contiene anche il resto
della permutazione:

    byte = 6*4 + (n_token - 1) * 256*4          # 64.536 per 64 token

Con `reshape(-1, 6)` si leggono 2.689 righe invece di 64, e le 2.625 in piu'
sono coda di argsort spacciata per route. I cancelli ovvi non se ne accorgono:
l'argsort di 256 elementi e' una permutazione, quindi sei valori consecutivi
sono SEMPRE distinti e SEMPRE in [0,255]. Il cancello che se ne accorge e'
l'unico vero: ogni riga intera dev'essere una permutazione di 0..255.

(Sui dump di DECODE, un token per chiamata, non c'e' passo da saltare e la
lettura ingenua e' corretta: le piste ORACOLO1 dell'8 agosto stanno in piedi.)

## COME SI LEGGE IL RISULTATO

L'esperto e' identificato dalla COPPIA (strato, indice): lo stesso indice su
due strati e' due tensori e due residenze diverse. Il totale possibile e'
n_strati_con_router x 256.
"""

import sys, os, re
import numpy as np

if len(sys.argv) < 2:
    print('uso: conta_esperti.py <cartella_dump> [n_id] [n_esperti]')
    sys.exit(2)

SRC   = sys.argv[1]
N_ID  = int(sys.argv[2]) if len(sys.argv) > 2 else 6      # n_expert_used
N_EXP = int(sys.argv[3]) if len(sys.argv) > 3 else 256    # n_expert
MIB   = 6.75          # un esperto di uno strato, IQ2_XXS, gate+up+down


# L'INDICE dice forma e byte di ogni file, e serve: il passo NON e' lo stesso
# ovunque. Nei primi strati (instradamento per hash) `ffn_moe_topk` e' un
# tensore vero e contiguo; dove c'e' il router e' una vista di argsort col
# passo di 256. Deducendolo dal solo file si sbaglia in un verso o nell'altro.
def carica_indice(src):
    idx = os.path.join(src, 'INDICE.tsv')
    forme = {}
    if not os.path.exists(idx):
        return forme
    with open(idx, 'r', encoding='utf-8', errors='replace') as f:
        intest = f.readline().rstrip('\n').split('\t')
        col = {n: i for i, n in enumerate(intest)}
        for riga in f:
            c = riga.rstrip('\n').split('\t')
            if len(c) < len(intest):
                continue
            forme[c[col['file']]] = (int(c[col['ne0']]), int(c[col['ne1']]), int(c[col['byte']]))
    return forme


def leggi(path, forma):
    """Estrae [n_token, N_ID]. Restituisce anche la prima riga INTERA del
    genitore quando c'e' un passo, per il cancello della permutazione."""
    a = np.fromfile(path, dtype=np.int32)
    if forma is None:                        # nessun indice: due sole ipotesi
        if a.size % N_ID == 0 and a.size // N_ID <= 1:
            return a.reshape(-1, N_ID), None
        ne0, ne1 = N_ID, None
        resto = a.size - N_ID
        if resto % N_EXP:
            return None, None
        ne1 = resto // N_EXP + 1
        byte = a.size * 4
    else:
        ne0, ne1, byte = forma
        if ne0 != N_ID:
            return None, None
    if ne1 == 1:
        return a[:N_ID].reshape(1, N_ID), None
    if byte == ne0 * ne1 * 4:                # contiguo: nessun passo
        return a[:ne0 * ne1].reshape(ne1, ne0), None
    resto = byte - ne0 * 4
    if resto % ((ne1 - 1) * 4):
        return None, None
    passo = resto // ((ne1 - 1) * 4)         # int32 per riga del genitore
    piena = a[:(ne1 - 1) * passo].reshape(ne1 - 1, passo)
    ids = np.empty((ne1, N_ID), dtype=np.int32)
    ids[:ne1 - 1] = piena[:, :N_ID]
    ids[ne1 - 1] = a[(ne1 - 1) * passo:(ne1 - 1) * passo + N_ID]
    return ids, (piena[0] if passo == N_EXP else None)


FORME = carica_indice(SRC)
rx = re.compile(r'^ffn_moe_topk-(\d+)\.(\d+)\.bin$')
per_strato = {}
for nome in os.listdir(SRC):
    m = rx.match(nome)
    if m:
        per_strato.setdefault(int(m.group(1)), []).append((int(m.group(2)), os.path.join(SRC, nome)))

if not per_strato:
    print('nessun file ffn_moe_topk-*.bin in %s' % SRC)
    sys.exit(1)

strati = sorted(per_strato)
tracce, campione = {}, None
for L in strati:
    pezzi = []
    for _, path in sorted(per_strato[L]):
        ids, riga_piena = leggi(path, FORME.get(os.path.basename(path)))
        if ids is None:
            print('  !! %s: %d int32, forma %s: il passo non torna'
                  % (path, os.path.getsize(path) // 4, FORME.get(os.path.basename(path))))
            sys.exit(1)
        if campione is None and riga_piena is not None:
            campione = riga_piena
        pezzi.append(ids)
    tracce[L] = np.concatenate(pezzi, axis=0)

lung = {L: t.shape[0] for L, t in tracce.items()}
n_tok = min(lung.values())
print('strati con router : %d  (indici %d..%d)' % (len(strati), strati[0], strati[-1]))
print('posizioni         : %d%s' % (n_tok, '' if len(set(lung.values())) == 1
                                    else '  (troncate al minimo; max %d)' % max(lung.values())))

# --- CANCELLI, prima di contare -------------------------------------------
tutti = np.concatenate([tracce[L][:n_tok] for L in strati], axis=0)
riga  = tracce[strati[len(strati) // 2]][:n_tok]
cancelli = [
    ('id nel range [0,255]',        bool(((tutti >= 0) & (tutti < N_EXP)).all())),
    ('sei id distinti per riga',    bool(all(len(set(r.tolist())) == N_ID for r in riga[:200]))),
    ('la traccia VARIA nel tempo',  bool(not np.array_equal(riga[0], riga[min(100, n_tok - 1)]))),
]
if campione is not None:
    # IL CANCELLO CHE CONTA: se il passo fosse sbagliato, questa non sarebbe
    # una permutazione completa di 0..255
    cancelli.append(('la riga intera e\' una permutazione di 0..%d' % (N_EXP - 1),
                     bool(np.array_equal(np.sort(campione), np.arange(N_EXP)))))
else:
    cancelli.append(('passo verificabile (serve >1 token per chiamata)', None))

for nome, ok in cancelli:
    print('  %-46s %s' % (nome, 'n/d' if ok is None else ('OK' if ok else '*** FALLITO ***')))
if any(ok is False for _, ok in cancelli):
    print('\nESITO: la traccia non e\' quello che credo, non conto')
    sys.exit(1)

# --- il conteggio ---------------------------------------------------------
possibili = len(strati) * N_EXP
domande   = n_tok * len(strati) * N_ID
visti     = {L: np.unique(tracce[L][:n_tok]) for L in strati}
distinti  = sum(len(v) for v in visti.values())
p = lambda n: format(int(n), ',d').replace(',', '.')

print()
print('=' * 70)
print('  ESPERTI DISTINTI CHIAMATI : %s  su %s possibili  =  %.1f%%'
      % (p(distinti), p(possibili), 100.0 * distinti / possibili))
print('  se fossero tutti residenti: %s MiB' % p(distinti * MIB))
print('  domande totali            : %s' % p(domande))
print('=' * 70)

n_per_strato = np.array([len(visti[L]) for L in strati])
print()
print('  per strato, quanti dei %d vengono chiamati:' % N_EXP)
print('     min %d | mediana %d | media %.1f | max %d'
      % (n_per_strato.min(), int(np.median(n_per_strato)), n_per_strato.mean(), n_per_strato.max()))
print('     strati che ne chiamano piu\' di meta\' (>%d): %d su %d'
      % (N_EXP // 2, int((n_per_strato > N_EXP // 2).sum()), len(strati)))
print('     i cinque piu\' larghi : %s' % ', '.join(
    'L%d=%d' % (strati[i], n_per_strato[i]) for i in np.argsort(-n_per_strato)[:5]))
print('     i cinque piu\' stretti: %s' % ', '.join(
    'L%d=%d' % (strati[i], n_per_strato[i]) for i in np.argsort(n_per_strato)[:5]))

# --- LA CURVA DI COPERTURA: il numero che decide il keep-level -------------
freq = np.concatenate([np.bincount(tracce[L][:n_tok].ravel(), minlength=N_EXP) for L in strati])
cum  = np.cumsum(np.sort(freq)[::-1])
print()
print('  === COPERTURA: quanti esperti coprono il X%% delle domande ===')
for q in (0.50, 0.70, 0.80, 0.90, 0.95, 0.99, 1.00):
    k = int(np.searchsorted(cum, q * domande) + 1)
    print('     %3d%% <- i %6s piu\' chiamati   (%s MiB)' % (q * 100, p(k), p(k * MIB)))
print('     riferimenti: 339 slot = 2.288 MiB | 448 = 3.024 | 512 = 3.456')

# --- e la coda: quanto pesa cio' che si chiama una volta sola --------------
usati = freq[freq > 0]
print()
print('  la coda: %s esperti chiamati UNA volta sola (%.1f%% dei distinti, %.3f%% delle domande)'
      % (p((usati == 1).sum()), 100.0 * (usati == 1).sum() / distinti,
         100.0 * (usati == 1).sum() / domande))
print('  il piu\' chiamato: %s volte (%.2f%% delle domande da solo)'
      % (p(usati.max()), 100.0 * usati.max() / domande))
