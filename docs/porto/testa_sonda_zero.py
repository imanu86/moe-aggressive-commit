"""
CANTIERE TESTA — passo 1: la sonda a costo zero.

Domanda: da h_42(t) si predice il token t+1 meglio del BIGRAMMA?
Se si', la raccolta grande e' giustificata. Se no, lo sappiamo prima di
spendere ore di macchina.

Architettura del piano (senza stato, per costruzione):
    h_42(t) --[W]--> h_finale(t+1) --[output_norm, lm_head CONGELATE]--> logits

Qui la [W] e' una RIDGE in forma duale: con n=1.677 campioni e 4096 dimensioni
il sistema e' sotto-determinato, quindi si risolve nello spazio dei campioni
(n x n) invece che in quello delle feature (4096 x 4096). Nessun addestramento
iterativo, nessun iperparametro se non lambda.

DISCIPLINA:
  - split TEMPORALE (primi 80% addestra, ultimi 20% valuta): mai casuale, il
    testo e' una sequenza;
  - baseline BIGRAMMA stimata SOLO sulla parte di addestramento;
  - baseline MODA (il token piu' frequente) come pavimento.
"""

import os, sys
import numpy as np

sys.path.insert(0, r'D:\llama-dspark\gguf-py')
import gguf

MODELLO = r'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
COPPIE = {
    'codice': r'D:\ds4_work\dump\coppie_h42.npz',
    'prosa':  r'D:\ds4_work\dump_prosa\coppie_h42.npz',
}
LAMBDA = [1e2, 1e3, 1e4, 1e5]


def carica_testa(path):
    """output_norm + output (lm_head) dequantizzati dal GGUF."""
    r = gguf.GGUFReader(path, 'r')
    trovati = {}
    for t in r.tensors:
        if t.name in ('output.weight', 'output_norm.weight', 'token_embd.weight'):
            trovati[t.name] = t
    print('  tensori testa trovati:', sorted(trovati.keys()))
    out = {}
    for nome, t in trovati.items():
        a = np.array(t.data)
        if t.tensor_type != gguf.GGMLQuantizationType.F32:
            a = gguf.quants.dequantize(t.data, t.tensor_type)
        out[nome] = a.astype(np.float32).reshape(tuple(int(x) for x in reversed(t.shape)))
        print('    %-22s %-8s -> %s' % (nome, t.tensor_type.name, out[nome].shape))
    return out


def rms_norm(x, w, eps=1e-6):
    return (x / np.sqrt((x * x).mean(-1, keepdims=True) + eps)) * w


print('CANTIERE TESTA — sonda a costo zero\n')
print('Dequantizzo la testa del modello (congelata):')
T = carica_testa(MODELLO)
W_out = T.get('output.weight')
if W_out is None:
    W_out = T['token_embd.weight']          # tied embeddings
    print('  (output.weight assente -> uso token_embd.weight, pesi legati)')
g_norm = T['output_norm.weight'].reshape(-1)
print()

def valuta(X, y, orizzonte, dominio):
    """orizzonte=1: il token che il modello STESSO produce da questo stato
       (serve come verifica di pipeline, deve uscire quasi perfetto).
       orizzonte=2: il token DOPO — e' quello che una testa speculativa
       aggiunge davvero, ed e' l'unica cifra che conta."""
    if orizzonte > 1:
        X = X[:-(orizzonte - 1)]
        y = y[(orizzonte - 1):]
    n = len(X)
    ntr = int(n * 0.8)
    Xtr, ytr, Xte, yte = X[:ntr], y[:ntr], X[ntr:], y[ntr:]

    # --- pavimenti ---
    moda = np.bincount(ytr).argmax()
    p_moda = float((yte == moda).mean())
    big = {}
    for a, b in zip(ytr[:-1], ytr[1:]):
        big.setdefault(int(a), {}).setdefault(int(b), 0)
        big[int(a)][int(b)] += 1
    bigmap = {a: max(v, key=v.get) for a, v in big.items()}
    prev_te = np.concatenate([[ytr[-1]], yte[:-1]])
    p_big = float(np.mean([bigmap.get(int(a), moda) == b for a, b in zip(prev_te, yte)]))

    # --- ridge duale: h(t) -> stato finale di t+1, poi testa congelata ---
    # bersaglio: l'embedding del token vero (spazio in cui vive la lm_head)
    Y = W_out[y]                                   # [n, 4096]
    Ytr = Y[:ntr]
    K = Xtr @ Xtr.T
    Kte = Xte @ Xtr.T
    migliore = None
    for lam in LAMBDA:
        A = np.linalg.solve(K + lam * np.eye(ntr, dtype=np.float32), Ytr)
        P = Kte @ A                                # [nte, 4096] stato predetto
        P = rms_norm(P, g_norm)
        logit = P @ W_out.T
        top1 = logit.argmax(1)
        acc = float((top1 == yte).mean())
        if migliore is None or acc > migliore[1]:
            migliore = (lam, acc)
    lam, p_sonda = migliore

    etichetta = 't+1 (verifica pipeline)' if orizzonte == 1 else 't+2  <<< LA CIFRA CHE CONTA'
    print('  %-24s n=%d (tr %d / te %d) | moda %.3f | BIGRAMMA %.3f | sonda %.3f (lam %.0e)  %s'
          % (etichetta, n, ntr, n - ntr, p_moda, p_big, p_sonda, lam,
             'BATTE' if p_sonda > p_big else 'NON batte'))
    return p_sonda, p_big


for dominio, path in COPPIE.items():
    if not os.path.exists(path):
        print('%s: coppie assenti' % dominio); continue
    d = np.load(path)
    X0, y0 = d['X'].astype(np.float32), d['y']
    print('%s  (id distinti %d)' % (dominio.upper(), len(np.unique(y0))))
    valuta(X0, y0, 1, dominio)
    valuta(X0, y0, 2, dominio)
    print()
