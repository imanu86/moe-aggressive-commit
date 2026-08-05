# SI PUO' PREVEDERE LA ROUTE DEL TOKEN t+1 DALLO STATO FINALE DI t?
#
# E' la domanda che decide se vale la pena addestrare una testa di route sulla
# testa MTP (o sul drafter). Se si', l'anticipo passa da 3 ms (un solo strato,
# col predittore gratuito che gia' abbiamo) a UN TOKEN INTERO, 125 ms -- e i
# 23,6 ms di copie esposte vanno verso zero.
#
# IL METODO: la testa piu' debole che esista
# ------------------------------------------
# Una regressione ridge da h_finale(t) [4096] ai punteggi dei 256 esperti dello
# strato L per il token t+1. Nessuna nonlinearita', nessun addestramento vero.
# E' un LIMITE INFERIORE: se una retta prende qualcosa, una testa addestrata su
# milioni di token prendera' di piu'. Se una retta non prende niente,
# l'informazione probabilmente non c'e' e nessuna architettura la crea.
#
# L'ONESTA' STA NELLA DIVISIONE
# -----------------------------
# 4096 dimensioni e ~1.100 campioni di addestramento: il sistema e'
# sottodeterminato e una ridge puo' memorizzare il rumore. Quindi si addestra
# sul PRIMO 70% della corsa e si misura sull'ULTIMO 30%, che sono token che il
# modello non ha mai visto. Il numero che conta e' quello di prova; quello di
# addestramento serve solo a vedere quanto ha memorizzato.
#
# I DUE METRI DI CONFRONTO
#   caso                      6/256 = 2,3%
#   recency a distanza 1      le route del token PRECEDENTE, senza imparare niente
import sys, os
import numpy as np

D = r'D:\ds4_work\dump'
K = 6

idx = {}
for l in open(os.path.join(D, 'INDICE.tsv')):
    p = l.rstrip('\n').split('\t')
    if p[0] == 'file':
        continue
    idx.setdefault(p[1], []).append((int(p[2]), p[0], p[3], [int(x) for x in p[4:8]]))

def leggi(nome):
    pezzi = []
    for _, f, tipo, ne in sorted(idx[nome]):
        dt = np.float32 if tipo == 'f32' else np.int32
        d = np.fromfile(os.path.join(D, f), dtype=dt)
        ne0, ne1 = ne[0], ne[1]
        if d.size == ne0 * ne1:
            pezzi.append(d.reshape(ne1, ne0))
        else:
            passo = (d.size - ne0) // (ne1 - 1)
            pezzi.append(np.stack([d[t*passo:t*passo+ne0] for t in range(ne1)]))
    return np.concatenate(pezzi, axis=0)

NL = 43
V = {L: leggi(f'ffn_moe_topk-{L}') for L in range(NL) if f'ffn_moe_topk-{L}' in idx}
# lo stato finale del token: l'ultimo ffn_norm disponibile
Lfin = max(L for L in range(NL) if f'ffn_norm-{L}' in idx)
H = leggi(f'ffn_norm-{Lfin}')
T = min(min(v.shape[0] for v in V.values()), H.shape[0])
print(f'traccia {T} token, stato finale da ffn_norm-{Lfin} ({H.shape[1]} dimensioni)')

# X[t] = stato di t, Y[t] = route di t+1
X = H[:T-1].astype(np.float32)
X = np.hstack([X, np.ones((X.shape[0], 1), np.float32)])     # bias
ntr = int(0.70 * X.shape[0])
Xtr, Xte = X[:ntr], X[ntr:]
print(f'addestramento {Xtr.shape[0]} token, prova {Xte.shape[0]} (gli ULTIMI, mai visti)')

# la matrice normale si calcola UNA volta: e' la stessa per tutti i 43 strati
lam = 1e3
A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1], dtype=np.float32)
Ainv = np.linalg.inv(A)

r_tr, r_te, r_rec = [], [], []
for L in range(NL):
    if L not in V:
        continue
    Y = np.zeros((T-1, 256), np.float32)
    for t in range(T-1):
        Y[t, V[L][t+1]] = 1.0                      # le route di t+1
    Wm = Ainv @ (Xtr.T @ Y[:ntr])

    for nome, Xs, Ys, acc in (('tr', Xtr, Y[:ntr], r_tr), ('te', Xte, Y[ntr:], r_te)):
        S = Xs @ Wm
        P = np.argpartition(-S, K, axis=1)[:, :K]
        veri = [np.nonzero(Ys[t])[0] for t in range(Ys.shape[0])]
        acc.append(np.mean([len(set(P[t]) & set(veri[t])) / K for t in range(len(veri))]))

    # metro senza imparare niente: le route del token PRECEDENTE
    rec = []
    for t in range(ntr, T-1):
        rec.append(len(set(V[L][t].tolist()) & set(V[L][t+1].tolist())) / K)
    r_rec.append(np.mean(rec))

import statistics as st
print()
print(f'  {"":22s} {"recall":>8}')
print(f'  {"caso (6 su 256)":22s} {6/256*100:7.1f}%')
print(f'  {"recency: route di t":22s} {st.mean(r_rec)*100:7.1f}%   <- senza imparare niente')
print(f'  {"sonda lineare, TRAIN":22s} {st.mean(r_tr)*100:7.1f}%   (quanto ha memorizzato)')
print(f'  {"sonda lineare, TEST":22s} {st.mean(r_te)*100:7.1f}%   <- IL NUMERO CHE CONTA')
print()
print('  per profondita (test):')
n = len(r_te)
for nome, a, b in (('primi 10', 0, 10), ('centrali', 10, n-10), ('ultimi 10', n-10, n)):
    print(f'    {nome:10s} sonda {st.mean(r_te[a:b])*100:5.1f}%   recency {st.mean(r_rec[a:b])*100:5.1f}%')
