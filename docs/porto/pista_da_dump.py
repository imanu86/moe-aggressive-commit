"""
Costruisce una pista ORACOLO1 da un dump di route, con il passo giusto.

SOSTITUISCE `oracolo_pista.py` per i dump MULTI-TOKEN (prefill). Quello legge
`ffn_moe_topk` con `reshape(-1, 6)`, ma il tensore e' una VISTA dei primi 6
elementi di ogni riga di `ffn_moe_argsort`, che ne ha 256: `ggml_nbytes` di una
vista misura l'ESTENSIONE, non il contenuto. Su un dump da 64 token legge 2.689
righe invece di 64, e le altre 2.625 sono coda di argsort spacciata per route.
I suoi cancelli non se ne accorgono, perche' l'argsort di 256 elementi e' una
permutazione: sei valori consecutivi sono sempre distinti e sempre in [0,255].
Qui il cancello e' che la riga INTERA sia una permutazione di 0..255.
(Sui dump di decode, un token per chiamata, non c'e' passo e la lettura ingenua
era corretta: le piste dell'8 agosto stanno in piedi.)

L'ALLINEAMENTO, che e' la cosa delicata. La pista viene consumata una riga per
PASSO DI DECODE (`llama-context` chiama `oracolo_avanza` una volta per passo).
Con un prompt di P token, il passo di decode i elabora la posizione P+i. Quindi
la riga 0 della pista dev'essere la posizione P del dump, non la 0.

  uso: pista_da_dump.py <cartella_dump> <uscita.bin> <P> [n_token] [n_id]

Il numero P lo stampa il passo 1 della catena (`prompt_tokens`). Se l'allinea-
mento fosse sbagliato di uno, l'oracolo predirebbe il token accanto e i colpi
resterebbero quelli della LRU: il tasso di colpi E' il cancello dell'offset.
"""

import sys, os, re, struct
import numpy as np

if len(sys.argv) < 4:
    print('uso: pista_da_dump.py <cartella_dump> <uscita.bin> <P> [n_token] [n_id]')
    sys.exit(2)

SRC, DST, P = sys.argv[1], sys.argv[2], int(sys.argv[3])
N_TOK_MAX = int(sys.argv[4]) if len(sys.argv) > 4 else 0
N_ID      = int(sys.argv[5]) if len(sys.argv) > 5 else 6
N_EXP     = 256


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
        return (a.reshape(-1, N_ID), None) if a.size % N_ID == 0 else (None, None)
    ne0, ne1, byte = forma
    if ne0 != N_ID:
        return None, None
    if ne1 == 1 or byte == ne0 * ne1 * 4:
        return a[:ne0 * ne1].reshape(ne1, ne0), None
    resto = byte - ne0 * 4
    if resto % ((ne1 - 1) * 4):
        return None, None
    passo = resto // ((ne1 - 1) * 4)
    piena = a[:(ne1 - 1) * passo].reshape(ne1 - 1, passo)
    out = np.empty((ne1, N_ID), dtype=np.int32)
    out[:ne1 - 1] = piena[:, :N_ID]
    out[ne1 - 1] = a[(ne1 - 1) * passo:(ne1 - 1) * passo + N_ID]
    return out, (piena[0] if passo == N_EXP else None)


FORME = carica_indice(SRC)
rx = re.compile(r'^ffn_moe_topk-(\d+)\.(\d+)\.bin$')
per_strato = {}
for nome in os.listdir(SRC):
    m = rx.match(nome)
    if m:
        per_strato.setdefault(int(m.group(1)), []).append((int(m.group(2)), os.path.join(SRC, nome)))
if not per_strato:
    print('nessun ffn_moe_topk-*.bin in %s' % SRC)
    sys.exit(1)

strati, tracce, campione = sorted(per_strato), {}, None
for L in strati:
    pezzi = []
    for _, path in sorted(per_strato[L]):
        v, riga = leggi(path, FORME.get(os.path.basename(path)))
        if v is None:
            print('  !! %s: passo non deducibile' % path); sys.exit(1)
        if campione is None and riga is not None:
            campione = riga
        pezzi.append(v)
    tracce[L] = np.concatenate(pezzi, axis=0)

n_pos = min(t.shape[0] for t in tracce.values())
n_strato = strati[-1] + 1
print('strati %d (0..%d) | posizioni nel dump %d | prompt P=%d' % (len(strati), strati[-1], n_pos, P))

if campione is not None and not np.array_equal(np.sort(campione), np.arange(N_EXP)):
    print('*** la riga intera NON e\' una permutazione di 0..255: il passo e\' sbagliato, non scrivo')
    sys.exit(1)
print('  la riga intera e\' una permutazione di 0..255   OK')

if P >= n_pos:
    print('*** P=%d ma il dump ha solo %d posizioni' % (P, n_pos)); sys.exit(1)
n_tok = n_pos - P
if N_TOK_MAX and n_tok > N_TOK_MAX:
    n_tok = N_TOK_MAX
print('  righe di pista: %d  (posizioni %d..%d del dump)' % (n_tok, P, P + n_tok - 1))

out = np.full((n_tok, n_strato, N_ID), -1, dtype=np.int32)
for L in strati:
    out[:, L, :] = tracce[L][P:P + n_tok, :]

if not ((out >= 0) & (out < N_EXP)).all():
    print('*** id fuori range, non scrivo'); sys.exit(1)
if np.array_equal(out[0], out[min(50, n_tok - 1)]):
    print('*** la pista non varia nel tempo, non scrivo'); sys.exit(1)

with open(DST, 'wb') as f:
    f.write(b'ORACOLO1')
    f.write(struct.pack('<iii', n_tok, n_strato, N_ID))
    out.tofile(f)
print('scritto %s (%.2f MiB)' % (DST, os.path.getsize(DST) / (1024 ** 2)))
print('  braccio: LLAMA_CACHE_ORACOLO=%s con LLAMA_CACHE_ESPERTI_W>0, spec OFF,' % DST)
print('  e il braccio TRONCATO a %d token o il tetto e\' falsato.' % n_tok)
print('  IL CANCELLO DELL\'ALLINEAMENTO SONO I COLPI: se restano ~53%% come la LRU,')
print('  l\'offset e\' sbagliato e il numero si butta.')
