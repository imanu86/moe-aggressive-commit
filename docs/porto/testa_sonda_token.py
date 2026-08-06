# SI PUO' PREVEDERE IL TOKEN t+1 DALLO STATO FINALE DI t? (pavimento, stile testa_route.py)
#
# LA DOMANDA
# ----------
# La sonda di route (testa_route.py) ha dato 59,4% sul TEST: lo stato finale di
# t porta informazione sulla ROUTE di t+1. Qui la stessa domanda sul TOKEN:
# una regressione ridge da ffn_norm-42(t) [4096] al token id di t+1.
# E' la testa piu' debole che esista: se prende qualcosa, una testa vera
# (nonlineare, milioni di token) prendera' di piu'. E' un PAVIMENTO.
#
# COSA QUESTO NUMERO NON E' (onesta' prima di tutto)
# --------------------------------------------------
# NON e' il p1 della metrica (TESTA_METRICA.md). Tre ottimismi dichiarati:
#   1. MONDO CHIUSO: classifica solo fra i token PRESENTI nel testo (~centinaia),
#      non sui ~129k del vocabolario. Ottimista.
#   2. TEACHER FORCING: gli stati vengono dal flusso greedy vero, niente
#      accumulo d'errore. (Per p1 a catena profondita' 1 e' pero' realistico:
#      la proposta parte sempre da uno stato verificato.)
#   3. POCHI CAMPIONI: ~1.400 di addestramento su 4096 dimensioni; il gap
#      train/test dice quanto e' memorizzazione.
# E un pessimismo: ffn_norm-42 e' la norm PRE-FFN dell'ultimo strato — manca
# l'ultimo pezzo di calcolo (FFN-42 + norm finale) che il modello vero avrebbe.
#
# I METRI DI CONFRONTO (senza stati, solo statistica di superficie)
#   caso            1/C
#   moda            il token piu' frequente del train
#   ripetizione     y(t+1) == y(t)
#   bigram          successore piu' frequente di y(t) nel train  <- il metro VERO:
#                   se la sonda non lo batte, gli stati non aggiungono niente
#
# ALLINEAMENTO (la parte che ha gia' bruciato mezza giornata altrove)
# -------------------------------------------------------------------
# Gli id NON si ricostruiscono tokenizzando il testo salvato: i .txt su disco
# non sono byte-identici all'input (whitespace; misurato: prosa 2.155 contro
# 1.996, codice 1.890 contro 1.678). Gli id si leggono dal LOG di
# llama-eval-callback, che li stampa uno per riga dopo "number of input
# tokens = N": sono la verita' per costruzione, stessa run che scrisse i dump.
# CANCELLO: len(ids) == T della traccia, o si ferma tutto.
import os, re, sys
import numpy as np

# default: prosa; per il codice: testa_sonda_token.py codice
if len(sys.argv) > 1 and sys.argv[1] == 'codice':
    D   = r'D:\ds4_work\dump_codice2'
    LOG = r'D:\ds4_work\llama_run\testa_ridump_log.txt'
    DOMINIO = 'codice'
else:
    D   = r'D:\ds4_work\dump_prosa'
    LOG = r'D:\ds4_work\llama_run\evalcb_prosa_log.txt'
    DOMINIO = 'prosa'

# ---- id dal log dell'eval-callback (ground truth) ----
ids, on = [], False
for l in open(LOG, encoding='utf-8', errors='replace'):
    if 'number of input tokens' in l:
        on = True
        continue
    if on:
        m = re.match(r'^[\d\.]+ I\s+(\d+)\s*$', l)
        if m:
            ids.append(int(m.group(1)))
        elif ids:
            break
ids = np.array(ids, dtype=np.int64)

# ---- traccia: loader della ricetta (identico a testa_route.py) ----
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

# nel dump prosa esistono anche i duplicati "ffn_norm-N (reshaped)": solo i nomi esatti
Lfin = max(int(m.group(1)) for k in idx for m in [re.match(r'^ffn_norm-(\d+)$', k)] if m)
H = leggi(f'ffn_norm-{Lfin}')
T = H.shape[0]
print(f'traccia {T} token ({DOMINIO}), stato da ffn_norm-{Lfin} ({H.shape[1]} dim); id dal log: {len(ids)}')
if len(ids) != T:
    sys.exit(f'CANCELLO FALLITO: id {len(ids)} != traccia {T} — allineamento non garantito, stop.')

# X[t] = stato di t; y[t] = token di t+1
X = H[:T-1].astype(np.float32)
X = np.hstack([X, np.ones((X.shape[0], 1), np.float32)])
y = ids[1:T]
x_tok = ids[:T-1]                       # il token corrente (per bigram/ripetizione)

classi = np.unique(np.concatenate([y, x_tok]))
C = len(classi)
pos = {c: i for i, c in enumerate(classi)}
Y = np.zeros((T-1, C), np.float32)
Y[np.arange(T-1), [pos[v] for v in y]] = 1.0

ntr = int(0.70 * X.shape[0])
Xtr, Xte, Ytr = X[:ntr], X[ntr:], Y[:ntr]
ytr, yte      = y[:ntr], y[ntr:]
xtr, xte      = x_tok[:ntr], x_tok[ntr:]
print(f'addestramento {ntr} token, prova {len(yte)} (gli ULTIMI, mai visti); {C} classi (mondo chiuso)')

lam = 1e3
A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1], dtype=np.float32)
W = np.linalg.inv(A) @ (Xtr.T @ Ytr)

def topk_acc(Xs, ys, k):
    S = Xs @ W
    if k == 1:
        P = classi[np.argmax(S, axis=1)]
        return float(np.mean(P == ys))
    P = classi[np.argpartition(-S, k, axis=1)[:, :k]]
    return float(np.mean([ys[i] in P[i] for i in range(len(ys))]))

# metri di superficie (stimati sul train, misurati sul test)
moda = np.bincount([pos[v] for v in ytr]).argmax()
acc_moda = float(np.mean(yte == classi[moda]))
acc_rip  = float(np.mean(yte == xte))
succ = {}
for a, b in zip(xtr, ytr):
    succ.setdefault(a, {})
    succ[a][b] = succ[a].get(b, 0) + 1
big = {a: max(d, key=d.get) for a, d in succ.items()}
acc_big = float(np.mean([big.get(xte[i], classi[moda]) == yte[i] for i in range(len(yte))]))

print()
print(f'  {"caso (1/C)":24s} {1/C*100:6.1f}%')
print(f'  {"moda del train":24s} {acc_moda*100:6.1f}%')
print(f'  {"ripetizione y==x":24s} {acc_rip*100:6.1f}%')
print(f'  {"bigram del train":24s} {acc_big*100:6.1f}%   <- il metro da battere')
print(f'  {"sonda top-1 TRAIN":24s} {topk_acc(Xtr, ytr, 1)*100:6.1f}%   (quanto ha memorizzato)')
print(f'  {"sonda top-1 TEST":24s} {topk_acc(Xte, yte, 1)*100:6.1f}%   <- IL NUMERO CHE CONTA')
print(f'  {"sonda top-3 TEST":24s} {topk_acc(Xte, yte, 3)*100:6.1f}%')
print(f'  {"sonda top-10 TEST":24s} {topk_acc(Xte, yte, 10)*100:6.1f}%')
print()
print('  LETTURA: pavimento in mondo chiuso, NON p1. Sonda >> bigram = gli stati')
print('  portano il token dopo, e una testa vera parte da qui in su. Il top-10 dice')
print('  il margine: dove arriva una testa che riordina bene i candidati.')
