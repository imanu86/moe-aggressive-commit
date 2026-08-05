# QUANTO E' PREVEDIBILE LA ROUTE DELLO STRATO L+1 DALLO STATO DI L
#
# previsione = top6( W_gate[L+1] . h[L] )      <- lo stato che HAI GIA'
# verita'    = ffn_moe_topk-(L+1)              <- quello che sceglie davvero
#
# La metrica che conta non e' la precisione ma il RECALL: quanti dei sei veri
# sono nella lista prevista. Indovinare uno gia' residente non vale niente, ma
# quella parte si misura solo con una cache vera -- qui si misura il tetto.
#
# METRO DI CONTROLLO: la stessa previsione fatta con lo stato GIUSTO h[L+1]
# deve dare ~100%. Se non lo da', e' rotta la pipeline offline, non la tesi.
import sys, numpy as np, os
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
from gguf import GGUFReader

D = r'D:\ds4_work\dump'
idx = {}
for l in open(os.path.join(D,'INDICE.tsv'))  :
    p = l.rstrip('\n').split('\t')
    if p[0]=='file': continue
    idx[p[1]] = (p[0], p[3], [int(x) for x in p[4:8]])

r = GGUFReader(r'C:\ds4-models\DS4-0731-IQ2XXS.gguf')
gate, bias = {}, {}
for t in r.tensors:
    if '.ffn_gate_inp.weight' in t.name:
        L = int(t.name.split('.')[1]); gate[L] = np.array(t.data, dtype=np.float32)
    if '.exp_probs_b.bias' in t.name:
        L = int(t.name.split('.')[1]); bias[L] = np.array(t.data, dtype=np.float32).ravel()

def leggi(nome):
    # ATTENZIONE AL PASSO: ffn_moe_topk e' una VISTA delle prime 6 righe di un
    # argsort su 256, quindi il file e' 59416 byte per 354 numeri utili -- le
    # righe stanno a 1024 byte l'una dall'altra. Leggerlo come contiguo da
    # spazzatura plausibile, che e' il modo peggiore di sbagliare.
    f, tipo, ne = idx[nome]
    dt = np.float32 if tipo=='f32' else np.int32
    d = np.fromfile(os.path.join(D,f), dtype=dt)
    ne0, ne1 = ne[0], ne[1]
    if d.size == ne0*ne1:
        return d.reshape(ne1, ne0)
    passo = (d.size - ne0) // (ne1 - 1)      # elementi fra una riga e l'altra
    out = np.empty((ne1, ne0), dtype=dt)
    for t in range(ne1):
        out[t] = d[t*passo : t*passo + ne0]
    return out

NHASH = 3       # i primi 3 strati instradano per hash dell'id del token
K = 6
righe = []
for L in range(NHASH, 42):
    if f'ffn_norm-{L}' not in idx or f'ffn_moe_topk-{L+1}' not in idx: continue
    h    = leggi(f'ffn_norm-{L}')            # [T, 4096]
    hnext= leggi(f'ffn_norm-{L+1}')
    vero = leggi(f'ffn_moe_topk-{L+1}')      # [T, 6]
    W = gate[L+1].reshape(256, 4096) if gate[L+1].size == 256*4096 else gate[L+1]
    b = bias.get(L+1, np.zeros(256, np.float32))

    def top(x):
        s = x @ W.T + b
        return np.argpartition(-s, K, axis=1)[:, :K]

    pred  = top(h)        # con lo stato di PRIMA  -> la tesi
    ctrl  = top(hnext)    # con lo stato GIUSTO    -> il metro della pipeline

    def recall(p):
        return np.mean([len(set(p[t]) & set(vero[t]))/K for t in range(vero.shape[0])])
    righe.append((L, recall(pred), recall(ctrl)))

print(f"{'strato':>6} {'recall da h[L]':>15} {'metro da h[L+1]':>16}")
for L, rp, rc in righe:
    print(f'{L:6d} {rp*100:14.1f}% {rc*100:15.1f}%')
import statistics as st
print()
print(f'  MEDIA  recall previsione {st.mean(x[1] for x in righe)*100:.1f}%   metro {st.mean(x[2] for x in righe)*100:.1f}%')
print(f'  primi 10 strati {st.mean(x[1] for x in righe[:10])*100:.1f}%   ultimi 10 {st.mean(x[1] for x in righe[-10:])*100:.1f}%')
print(f'  casuale (6 su 256) = {6/256*100:.1f}%')

# ------------------------------------------------------------------------
# LA DOMANDA CHE DECIDE: il 71% e' sui facili o sui difficili?
#
# Per una cache indovinare un esperto GIA' RESIDENTE non vale niente. L'unica
# metrica utile e' il recall sui NUOVI -- quelli che non compaiono nella
# finestra recente, che il registro chiama "sorpresa" e su cui la recency e'
# cieca per costruzione.
W = 16      # finestra di recency, la stessa del registro (hit 0,97 dentro fase)
tot_n = tot_p = tot_r = 0
per_strato = []
for L in range(NHASH, 42):
    if f'ffn_norm-{L}' not in idx or f'ffn_moe_topk-{L+1}' not in idx: continue
    h    = leggi(f'ffn_norm-{L}')
    vero = leggi(f'ffn_moe_topk-{L+1}')
    Wg = gate[L+1].reshape(256, 4096) if gate[L+1].size == 256*4096 else gate[L+1]
    b  = bias.get(L+1, np.zeros(256, np.float32))
    s  = h @ Wg.T + b
    pred = np.argpartition(-s, K, axis=1)[:, :K]
    nuovi = prev = colti = coltirec = 0
    for t in range(W, vero.shape[0]):
        recenti = set(vero[max(0,t-W):t].ravel().tolist())
        for e in vero[t]:
            if e in recenti:
                prev += 1
                if e in pred[t]: coltirec += 1
            else:
                nuovi += 1
                if e in pred[t]: colti += 1
    if nuovi:
        per_strato.append((L, colti/nuovi, coltirec/max(prev,1), nuovi, prev))
        tot_n += nuovi; tot_p += colti; tot_r += prev
print()
print('  --- recall separato: NUOVI (la sorpresa) contro GIA VISTI negli ultimi 16 token ---')
import statistics as st
rn = st.mean(x[1] for x in per_strato); rp = st.mean(x[2] for x in per_strato)
print(f'  recall sui NUOVI      {rn*100:5.1f}%     ({tot_n} casi, {tot_n/(tot_n+tot_r)*100:.1f}% della domanda)')
print(f'  recall sui GIA VISTI  {rp*100:5.1f}%     ({tot_r} casi)')
print()
print(f'  quota di domanda che la sola RECENCY copre: {tot_r/(tot_n+tot_r)*100:.1f}%')
print(f'  quota che resta scoperta dalla recency:     {tot_n/(tot_n+tot_r)*100:.1f}%')
print(f'  ... di cui il predittore ne prende          {rn*100:.1f}%')
print(f'  => copertura combinata recency+predittore:  {(tot_r + tot_n*rn)/(tot_n+tot_r)*100:.1f}%')
