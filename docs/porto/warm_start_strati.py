# QUANTO E' BUONA LA PARTENZA A CALDO DEL TOKEN PRECEDENTE?
#
# LA DOMANDA, e a cosa serve
# --------------------------
# L'idea dell'utente: due worker che si rimandano la palla FRA STRATI, cioe'
# Jacobi applicato agli strati invece che ai token -- si ipotizza l'ingresso di
# tutti e 43 gli strati, li si calcola TUTTI INSIEME (dati gli ingressi
# ipotizzati sono indipendenti), e si itera fino a convergenza.
#
# E' l'unica leva che attacca la catena di 43 passi in se', e ha una proprieta'
# che sulla nostra macchina vale doppio: trasforma un problema a batch 1 in uno
# a batch 43, che e' esattamente cio' che vuole una GPU usata al 6%.
#
# Il conto (pavimento ~5 ms + calcolo ~2,6 + trasporto 39 per iterazione) mette
# il PAREGGIO A ~2,3 ITERAZIONI. Jacobi propaga uno strato di informazione
# esatta per iterazione su 43 strati, quindi k=2-3 e' fuori portata A FREDDO.
# L'unica cosa che abbassa k e' partire da un'ipotesi gia' buona, e l'ipotesi
# gratis e' LO STATO DEL TOKEN PRECEDENTE.
#
# COSA SI PUO' MISURARE OFFLINE, E COSA NO
# -----------------------------------------
# NON si puo' misurare k: servirebbe far girare gli strati, e la traccia ha solo
# il cammino percorso. Si puo' misurare la QUALITA' DELLA PARTENZA, che e' il
# fattore che decide k, e in una forma che parla la nostra lingua: gli ESPERTI.
#
#   1. similitudine coseno fra h_L(t) e h_L(t+1), strato per strato
#   2. quanti dei 6 esperti veri di t+1 si azzeccano instradando lo stato
#      VECCHIO h_L(t) attraverso il gate di L -- cioe' quanto della route e'
#      gia' giusta all'iterazione ZERO
#   3. il totale sui 43 strati: quanti dei 258 esperti/token sarebbero gia'
#      corretti a costo nullo
#
# IL PROFILO IN PROFONDITA' E' LA COSA CHE DECIDE: se la partenza a caldo e'
# buona negli strati bassi e cattiva negli alti, e' buona dove serve meno,
# perche' l'errore si propaga in avanti e si accumula.
#
# CANCELLO DI CONTROLLO: instradare lo stato GIUSTO h_L(t) e confrontarlo con la
# route vera di t deve dare ~100%. Se non lo da', e' rotta la pipeline.
import sys, os
import numpy as np
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
from gguf import GGUFReader

D   = r'D:\ds4_work\dump'
MOD = r'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
K_TOPK = 6

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
print(f'traccia {T} token x {len(strati)} strati')
print()

def route(L, X):
    s = X @ gate[L].T + bias.get(L, 0.0)
    return np.argpartition(-s, K_TOPK, axis=1)[:, :K_TOPK]

cos_L, caldo_L, ctrl_L = {}, {}, {}
for L in strati:
    h  = H[L][:T].astype(np.float32)
    n  = np.linalg.norm(h, axis=1, keepdims=True)
    hn = h / np.maximum(n, 1e-9)
    cos_L[L] = float(np.mean(np.sum(hn[:-1] * hn[1:], axis=1)))

    vero = V[L][:T]
    # partenza a CALDO: lo stato VECCHIO instradato, contro la route VERA di t+1
    r_caldo = route(L, h[:-1])
    caldo_L[L] = float(np.mean([len(set(r_caldo[i]) & set(vero[i+1])) for i in range(T-1)])) / K_TOPK
    # CONTROLLO: lo stato GIUSTO instradato, contro la route vera di t
    r_ctrl = route(L, h[::37])
    ctrl_L[L] = float(np.mean([len(set(r_ctrl[j]) & set(vero[j*37])) for j in range(len(r_ctrl))])) / K_TOPK

print(f'  CONTROLLO -- stato giusto instradato contro la route vera: '
      f'{np.mean(list(ctrl_L.values()))*100:.1f}% (deve essere ~100)')
print()
print(f'{"gruppo di strati":>18} {"cos(h_t, h_t+1)":>16} {"route gia giusta":>17}')
gruppi = [('bassi  0-10', [L for L in strati if L <= 10]),
          ('medi  11-21', [L for L in strati if 11 <= L <= 21]),
          ('alti  22-32', [L for L in strati if 22 <= L <= 32]),
          ('ultimi 33-42',[L for L in strati if L >= 33])]
for nome, G in gruppi:
    if not G: continue
    print(f'{nome:>18} {np.mean([cos_L[L] for L in G]):16.3f} '
          f'{np.mean([caldo_L[L] for L in G])*100:16.1f}%')
tot = np.mean(list(caldo_L.values()))
print(f'{"TUTTI":>18} {np.mean(list(cos_L.values())):16.3f} {tot*100:16.1f}%')
print()
print(f'  Sui 258 esperti/token, la partenza a caldo ne azzecca {tot*258:.0f} '
      f'e ne sbaglia {258-tot*258:.0f}.')
print()
print('  LETTURA: il numero che conta e la route GIA GIUSTA all iterazione zero.')
print('  Alto e stabile in profondita -> la partenza a caldo e vicina, k puo scendere.')
print('  Basso o in calo verso gli strati alti -> l errore entra dove si accumula,')
print('  e nessuna iterazione economica lo recupera: il pareggio a 2,3 resta fuori.')
