# LA MASCHERA RENDE CONVENIENTE IL PARALLELISMO?
#
# LA DOMANDA, e da dove nasce
# ---------------------------
# Cinque leve di parallelismo speculativo sono state falsificate sul 3060
# (speculazione a batch 8, drafter CPU, lane G132, DSpark, Jacobi), tutte per
# la stessa ragione: il batch ammortizza i byte solo in parte, perche' token
# diversi si instradano su esperti diversi.
#
#     1 token     258 esperti distinti   =  1,70 GiB
#     8 token   1.244        distinti    =  8,20 GiB   ->  4,8x i byte per 8x i token
#
# Il pareggio di Jacobi (8,6 token accettati per passo) e' fuori portata proprio
# per questo. MA il problema non e' l'autoregressione: e' la DISPERSIONE del
# routing dentro la finestra.
#
# E la cosa che comprime la dispersione e' la maschera a dominio -- la tesi del
# reap-loop dal 10 luglio, mai provata su llama.cpp:
#
#     "il collo non e' il costo del singolo trasporto ma il VOLUME del working
#      set che il routing libero su 256 esperti genera; le maschere a dominio lo
#      comprimono alla radice"
#
# Se con un pool ristretto otto token pescano 600 esperti invece di 1.244, il
# pareggio di Jacobi si dimezza e l'aritmetica cambia segno. La maschera non
# compete col parallelismo: lo ABILITA.
#
# COME SI MISURA, senza GPU e senza toccare il motore
# ---------------------------------------------------
# Abbiamo la traccia vera: gli stati nascosti (ffn_norm-L) e le route scelte
# (ffn_moe_topk-L) di 1.678 token su 43 strati, piu' i pesi del gate dal GGUF.
# Quindi si puo' RICALCOLARE il routing sotto maschera invece di indovinarlo:
#
#   1. logit = W_gate[L] . h[L] + bias      (riproduce il routing vero)
#   2. si azzerano a -inf gli esperti FUORI dalla maschera
#   3. top-6 fra i sopravvissuti            (quello che farebbe il router mascherato)
#   4. si conta quanti esperti DISTINTI tocca una finestra di N token
#
# La maschera si costruisce per MASSA, come il gate del reap-loop: si somma il
# peso di gating di ciascun esperto sull'intera traccia e si tengono i primi K
# per strato.
#
# UN CANCELLO DI ONESTA', PRIMA DI LEGGERE I NUMERI
# --------------------------------------------------
# Questa misura riguarda SOLO l'economia dei byte. La maschera e' SELEZIONE, non
# residenza: cambia l'uscita, e il registro documenta che una maschera con
# dominio sbagliato COLLASSA (I1, radice del collasso wide). Quindi un risultato
# positivo qui dice "il parallelismo diventerebbe conveniente", non "si puo'
# fare senza costi": la qualita' e' una domanda separata, e la risposta del
# registro e' che serve una maschera COSTRUITA DAL PROMPT, non precotta.
#
# Si stampa anche il metro di controllo: la stessa pipeline SENZA maschera deve
# riprodurre la curva gia' misurata (258 / 1.244 / 1.993 ...). Se non la
# riproduce, e' rotta la pipeline, non la tesi.
import sys, os
import numpy as np
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
from gguf import GGUFReader

D   = r'D:\ds4_work\dump'
MOD = r'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
K_TOPK = 6
MIB    = 6.75

# ------------------------------------------------------------------ lettura
idx = {}
for l in open(os.path.join(D, 'INDICE.tsv')):
    p = l.rstrip('\n').split('\t')
    if p[0] == 'file':
        continue
    idx.setdefault(p[1], []).append((int(p[2]), p[0], p[3], [int(x) for x in p[4:8]]))

def leggi(nome):
    # piu' chiamate per tensore: vanno concatenate NELL'ORDINE, la sequenza
    # temporale e' tutto. E ffn_moe_topk e' una VISTA con stride (le prime 6
    # righe di un argsort su 256): letta come contigua da' spazzatura plausibile.
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

r = GGUFReader(MOD)
gate, bias = {}, {}
for t in r.tensors:
    if '.ffn_gate_inp.weight' in t.name:
        gate[int(t.name.split('.')[1])] = np.array(t.data, np.float32).reshape(256, 4096)
    if '.ffn_exp_probs_b.bias' in t.name or '.exp_probs_b.bias' in t.name:
        bias[int(t.name.split('.')[1])] = np.array(t.data, np.float32).ravel()

NL = 43
H = {L: leggi(f'ffn_norm-{L}')     for L in range(NL) if f'ffn_norm-{L}' in idx}
V = {L: leggi(f'ffn_moe_topk-{L}') for L in range(NL) if f'ffn_moe_topk-{L}' in idx}
T = min(min(v.shape[0] for v in V.values()), min(h.shape[0] for h in H.values()))
strati = sorted(set(H) & set(V) & set(gate))
print(f'traccia {T} token x {len(strati)} strati con stato+route+gate')

# ------------------------------------------- la massa, per costruire la maschera
# massa = somma dei pesi di gating sull'intera traccia. E' il criterio del gate
# del reap-loop: freq x peso, non la sola frequenza.
massa = {}
for L in strati:
    s = H[L][:T] @ gate[L].T + bias.get(L, 0.0)
    e = np.exp(s - s.max(axis=1, keepdims=True))
    p = e / e.sum(axis=1, keepdims=True)
    massa[L] = p.sum(axis=0)          # [256]

def route_sotto_maschera(K):
    """Ricalcola il top-6 di ogni token restringendo il pool ai primi K per massa.
       K = 256 significa nessuna maschera, e deve riprodurre la route vera."""
    R = {}
    for L in strati:
        tenuti = np.argpartition(-massa[L], K-1)[:K] if K < 256 else np.arange(256)
        s = H[L][:T] @ gate[L].T + bias.get(L, 0.0)
        if K < 256:
            fuori = np.ones(256, bool); fuori[tenuti] = False
            s[:, fuori] = -np.inf
        R[L] = np.argpartition(-s, K_TOPK, axis=1)[:, :K_TOPK]
    return R

def distinti_per_finestra(R, finestre):
    out = {}
    for W in finestre:
        d = []
        for t0 in range(0, T - W, max(W, 1)):
            s = set()
            for L in strati:
                s |= set((L << 16) | int(e) for e in R[L][t0:t0+W].ravel())
            d.append(len(s))
        out[W] = float(np.mean(d))
    return out

FIN = [1, 2, 4, 8, 16, 32, 64]

# --- metro: la route VERA, letta dalla traccia (non ricalcolata) -------------
vera = {L: V[L][:T] for L in strati}
d_vera = distinti_per_finestra(vera, FIN)
print()
print('  METRO -- route vera dalla traccia (deve dare 258 / 1.244 / 1.993 ...)')
print('   ' + '  '.join(f'W{w}={d_vera[w]:.0f}' for w in FIN))

# --- controllo: la pipeline ricalcolata senza maschera deve coincidere -------
d_ric = distinti_per_finestra(route_sotto_maschera(256), FIN)
acc = np.mean([len(set(route_sotto_maschera(256)[L][t]) & set(vera[L][t]))/K_TOPK
               for L in strati[:5] for t in range(0, T, 97)])
print(f'  CONTROLLO -- ricalcolata senza maschera, accordo col vero {acc*100:.1f}%')
print('   ' + '  '.join(f'W{w}={d_ric[w]:.0f}' for w in FIN))

# --- la domanda: quanto si appiattisce la curva sotto maschera ---------------
print()
print(f"{'pool':>6} {'GiB pool':>9}  " + '  '.join(f'{("W"+str(w)):>7}' for w in FIN))
for K in (256, 128, 64, 32, 16):
    R = route_sotto_maschera(K)
    d = distinti_per_finestra(R, FIN)
    gib_pool = K * len(strati) * MIB / 1024
    print(f'{K:6d} {gib_pool:8.2f}  ' + '  '.join(f'{d[w]:7.0f}' for w in FIN))

# --- e cosa vuol dire per il pareggio di Jacobi ------------------------------
# pareggio = (byte del passo / banda) x (t/s del metro)
BANDA, METRO = 24.35, 8.0
print()
print('  PAREGGIO DI JACOBI -- token da accettare per passo, per pareggiare 8 t/s')
print(f"{'pool':>6}  " + '  '.join(f'{("W"+str(w)):>7}' for w in FIN if w >= 8))
for K in (256, 128, 64, 32, 16):
    d = distinti_per_finestra(route_sotto_maschera(K), FIN)
    riga = []
    for w in FIN:
        if w < 8: continue
        gib = d[w] * MIB / 1024
        riga.append(f'{gib/BANDA*METRO:7.1f}')
    print(f'{K:6d}  ' + '  '.join(riga))
print()
print('  Il tetto FISICO e\' W (non si accetta piu\' della finestra), e il tetto')
print('  MISURATO dal simulatore della chat parallela e\' 1,43-1,60.')
