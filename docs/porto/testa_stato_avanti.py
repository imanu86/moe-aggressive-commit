# LA TESTA PREDICE LO STATO, NON IL TOKEN — quanto è prevedibile h(t+1) da h(t)?
#
# IL DISEGNO (fissato dopo la notte del 7/8)
# ------------------------------------------
# Un drafter deve proporre il token DOPO quello appena campionato, cioè t+2
# rispetto all'ultimo stato disponibile h(t): il token t+1 lo produce il
# bersaglio stesso nel forward di t (misurato: la sonda diretta a t+1 fa 70,3%
# in prosa e 99,8% in codice PROPRIO perché ricalcola quel forward).
#
# La testa stile EAGLE non impara il token: impara lo STATO.
#
#     h(t)  --adapter-->  h^(t+1)  --lm_head CONGELATA-->  logits del token t+2
#
# Due ragioni per cui è meglio che predire il token direttamente:
#   1. il bersaglio è denso (4096 float) invece che categorico su 129k: molto
#      più segnale per campione, e i nostri campioni sono poche migliaia;
#   2. la lm_head esiste già ed è residente in VRAM (output.weight, Q8_0,
#      536,6 MiB): la testa aggiunge solo l'adapter (~34 MiB) e NON tocca
#      nessun esperto — né i 74 GiB mappati né i 380 slot di cache.
#
# COSA MISURA QUESTO SCRIPT, e con quale cancello
# -----------------------------------------------
#   A. la predicibilità dello stato: coseno fra h^(t+1) e h(t+1) su token mai
#      visti, contro il metro "copia h(t)" (che è gratis e non impara niente);
#   B. la composizione: il token t+2 letto da h^(t+1) attraverso il decodificatore
#      appreso, contro lo stesso decodificatore su h(t+1) VERO. Il rapporto fra
#      i due dice quanta accuratezza si perde nel predire lo stato — che è
#      l'unica parte che la testa deve imparare.
#   C. il confronto con la sonda diretta h(t) -> token t+2 (53,6% prosa,
#      99,2% codice): se la via a due stadi non batte quella diretta, il
#      disegno a stato non serve e si torna alla testa categorica.
#
# LIMITE DICHIARATO: la traccia ha ffn_norm-42 (ingresso dell'ULTIMA FFN), non
# lo stato finale post-norm. Il decodificatore appreso qui fa quindi le veci di
# [FFN-42 + norm + lm_head]. Per la testa vera serve un dump di `result_norm`:
# è ~15 minuti di macchina, ed è l'unica dipendenza dalla macchina di tutto il
# cantiere. I numeri di qui sono una STIMA, non il p1.
import os, re, sys
import numpy as np

def carica(dom):
    if dom == 'codice':
        D, LOG = r'D:\ds4_work\dump_codice2', r'D:\ds4_work\llama_run\testa_ridump_log.txt'
    else:
        D, LOG = r'D:\ds4_work\dump_prosa', r'D:\ds4_work\llama_run\evalcb_prosa_log.txt'
    ids, on = [], False
    for l in open(LOG, encoding='utf-8', errors='replace'):
        if 'number of input tokens' in l:
            on = True; continue
        if on:
            m = re.match(r'^[\d\.]+ I\s+(\d+)\s*$', l)
            if m: ids.append(int(m.group(1)))
            elif ids: break
    idx = {}
    for l in open(os.path.join(D, 'INDICE.tsv')):
        p = l.rstrip('\n').split('\t')
        if p[0] == 'file': continue
        idx.setdefault(p[1], []).append((int(p[2]), p[0], p[3], [int(x) for x in p[4:8]]))
    def leggi(nome):
        pezzi = []
        for _, f, tipo, ne in sorted(idx[nome]):
            dt = np.float32 if tipo == 'f32' else np.int32
            d = np.fromfile(os.path.join(D, f), dtype=dt)
            ne0, ne1 = ne[0], ne[1]
            if d.size == ne0*ne1:
                pezzi.append(d.reshape(ne1, ne0))
            else:
                passo = (d.size - ne0)//(ne1 - 1)
                pezzi.append(np.stack([d[t*passo:t*passo+ne0] for t in range(ne1)]))
        return np.concatenate(pezzi, axis=0)
    L = max(int(m.group(1)) for k in idx for m in [re.match(r'^ffn_norm-(\d+)$', k)] if m)
    H = leggi(f'ffn_norm-{L}').astype(np.float32)
    T = min(H.shape[0], len(ids))
    if len(ids) != H.shape[0]:
        sys.exit(f'CANCELLO: id {len(ids)} != traccia {H.shape[0]} in {dom}')
    return H[:T], np.array(ids[:T], np.int64)

def ridge(X, Y, lam):
    A = X.T @ X + lam*np.eye(X.shape[1], dtype=np.float32)
    return np.linalg.inv(A) @ (X.T @ Y)

def cos(A, B):
    a = A/np.maximum(np.linalg.norm(A, axis=1, keepdims=True), 1e-9)
    b = B/np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-9)
    return float(np.mean(np.sum(a*b, axis=1)))

for dom in ('prosa', 'codice'):
    H, ids = carica(dom)
    T = H.shape[0]
    print(f'=== {dom}: {T} token, stato {H.shape[1]}-dim ===')

    # --- A. predire lo STATO un passo avanti: h(t) -> h(t+1)
    X = np.hstack([H[:T-2], np.ones((T-2,1), np.float32)])
    Y = H[1:T-1]
    ntr = int(0.70*X.shape[0])
    W = ridge(X[:ntr], Y[:ntr], 1e3)
    Hp = X[ntr:] @ W                      # h^(t+1) su token mai visti
    print(f'  A. stato: coseno h^(t+1) vs h(t+1)  {cos(Hp, Y[ntr:]):.3f}'
          f'   |  metro "copia h(t)": {cos(X[ntr:, :-1], Y[ntr:]):.3f}')

    # --- B. decodificatore appreso (fa le veci di FFN-42+norm+lm_head):
    #        h(s) -> token(s+1), addestrato sullo stesso 70% iniziale
    y2 = ids[2:T]                          # token t+2
    classi = np.unique(ids); pos = {c:i for i,c in enumerate(classi)}
    Yd = np.zeros((T-2, len(classi)), np.float32)
    Yd[np.arange(T-2), [pos[v] for v in y2]] = 1.0
    Xd = np.hstack([H[1:T-1], np.ones((T-2,1), np.float32)])   # h(t+1) -> token t+2
    Wd = ridge(Xd[:ntr], Yd[:ntr], 1e3)

    def acc(Xs, ys):
        return float(np.mean(classi[np.argmax(Xs @ Wd, 1)] == ys))
    tetto  = acc(Xd[ntr:], y2[ntr:])                                   # con lo stato VERO
    catena = acc(np.hstack([Hp, np.ones((Hp.shape[0],1), np.float32)]), y2[ntr:])  # con h^

    # --- C. la via diretta, per confronto: h(t) -> token t+2
    Wdir = ridge(X[:ntr], Yd[:ntr], 1e3)
    diretta = float(np.mean(classi[np.argmax(X[ntr:] @ Wdir, 1)] == y2[ntr:]))

    print(f'  B. token t+2 dallo stato VERO h(t+1)      {tetto*100:5.1f}%   <- il tetto del disegno')
    print(f'     token t+2 dallo stato PREDETTO h^(t+1)  {catena*100:5.1f}%   ({catena/tetto*100:.0f}% del tetto)')
    print(f'  C. via diretta h(t) -> token t+2          {diretta*100:5.1f}%   <- da battere')
    print(f'     VERDETTO: la via a stato {"BATTE" if catena > diretta else "NON batte"} la diretta'
          f' ({catena*100:.1f} contro {diretta*100:.1f})')
    print()
