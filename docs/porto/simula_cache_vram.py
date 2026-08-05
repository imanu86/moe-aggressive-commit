# SIMULAZIONE DELLA CACHE ESPERTI IN VRAM, sulla traccia vera
#
# LA DOMANDA
# ----------
# Prima di scrivere la cache per-esperto in C serve sapere tre cose:
#   1. quanti slot servono perche' la sola LRU regga
#   2. quanto aggiunge il prefetch predittivo (gate dello strato dopo)
#   3. QUANTI BYTE costa il prefetch -- perche' con precisione 25% si rischia
#      di chiedere al PCIe piu' banda di quanta ne abbia, e allora il conto
#      torna a zero
#
# La (3) e' quella che puo' uccidere il progetto, ed e' il motivo di questo file.
#
# COSA SIMULA
# -----------
# Cache di N slot su coppie (strato, esperto), politica LRU, sulla traccia
# reale di 1714 token x 43 strati. Tre politiche:
#   A  LRU pura, a domanda           <- il metro
#   B  LRU + prefetch a finestra W   <- la tesi
#   C  oracolo (Belady approssimato) <- il tetto, per sapere quanto si lascia
#
# IL PREFETCH
# -----------
# Allo strato L del token t si prevede il routing di L+1..L+W applicando
# W_gate[L+k] allo stato nascosto h[L], e si portano in cache i predetti che
# non ci sono. Il margine e' k*3 ms contro gli 0,56 ms di una copia da 6,75 MiB
# su PCIe 3.0 x16: c'e' tempo, il problema e' la BANDA AGGREGATA.
import sys, os, glob, re
import numpy as np
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
from gguf import GGUFReader

D = r'D:\ds4_work\dump'
MIB = 6.75           # byte per esperto (gate+up+down IQ2_XXS/Q2_K)
K = 6

# ---------------------------------------------------------------- lettura
idx = {}
for l in open(os.path.join(D, 'INDICE.tsv')):
    p = l.rstrip('\n').split('\t')
    if p[0] == 'file':
        continue
    idx.setdefault(p[1], []).append((int(p[2]), p[0], p[3], [int(x) for x in p[4:8]]))

def leggi(nome):
    # PIU' CHIAMATE PER TENSORE: con ub 256 e 1714 token il grafo gira 7 volte,
    # e ogni giro scrive il suo file. Vanno concatenati NELL'ORDINE, altrimenti
    # la sequenza temporale -- che e' tutto, in una simulazione di cache -- e'
    # mescolata.
    pezzi = []
    for _, f, tipo, ne in sorted(idx[nome]):
        dt = np.float32 if tipo == 'f32' else np.int32
        d = np.fromfile(os.path.join(D, f), dtype=dt)
        ne0, ne1 = ne[0], ne[1]
        if d.size == ne0 * ne1:
            pezzi.append(d.reshape(ne1, ne0))
        else:
            # vista con stride: ffn_moe_topk sono le prime 6 righe di un
            # argsort su 256, le righe distano 1024 byte
            passo = (d.size - ne0) // (ne1 - 1)
            pezzi.append(np.stack([d[t*passo:t*passo+ne0] for t in range(ne1)]))
    return np.concatenate(pezzi, axis=0)

r = GGUFReader(r'C:\ds4-models\DS4-0731-IQ2XXS.gguf')
gate, bias = {}, {}
for t in r.tensors:
    if '.ffn_gate_inp.weight' in t.name:
        gate[int(t.name.split('.')[1])] = np.array(t.data, np.float32).reshape(256, 4096)
    if '.exp_probs_b.bias' in t.name:
        bias[int(t.name.split('.')[1])] = np.array(t.data, np.float32).ravel()

NL = 43
H = {L: leggi(f'ffn_norm-{L}')      for L in range(NL) if f'ffn_norm-{L}' in idx}
V = {L: leggi(f'ffn_moe_topk-{L}')  for L in range(NL) if f'ffn_moe_topk-{L}' in idx}
T = min(v.shape[0] for v in V.values())
print(f'traccia: {T} token x {len(V)} strati = {T*len(V)*K:,} richieste di esperto')

# --------------------------------------------------------- le previsioni
# precalcolate una volta: per ogni (sorgente L, bersaglio L+k) la lista dei 6
def previsioni(W):
    P = {}
    for L in H:
        for k in range(1, W+1):
            Tg = L + k
            if Tg not in V or Tg not in gate:
                continue
            s = H[L] @ gate[Tg].T + bias.get(Tg, 0.0)
            P[(L, Tg)] = np.argpartition(-s, K, axis=1)[:, :K]
    return P

# ------------------------------------------------------------ simulatore
def simula(slot, W=0, P=None):
    """LRU su (strato,esperto). Ritorna (hit%, miss a domanda, esperti prefetchati)."""
    from collections import OrderedDict
    cache = OrderedDict()
    miss = dom = pref_fatti = 0
    for t in range(T):
        for L in range(NL):
            if L not in V:
                continue
            # 1. il prefetch per gli strati a venire, dallo stato di QUESTO strato
            if W and L in H:
                for k in range(1, W+1):
                    key = (L, L+k)
                    if key not in P:
                        continue
                    for e in P[key][t]:
                        c = (L+k, int(e))
                        if c not in cache:
                            cache[c] = True
                            pref_fatti += 1
                            if len(cache) > slot:
                                cache.popitem(last=False)
                        else:
                            cache.move_to_end(c)
            # 2. la domanda vera
            for e in V[L][t]:
                c = (L, int(e))
                dom += 1
                if c in cache:
                    cache.move_to_end(c)
                else:
                    miss += 1
                    cache[c] = True
                    if len(cache) > slot:
                        cache.popitem(last=False)
    return (dom-miss)/dom*100, miss, pref_fatti

print()
print(f"{'slot':>6} {'GiB':>6} {'LRU pura':>10} {'+prefetch W=4':>15} {'byte prefetch/token':>21} {'banda a 8 t/s':>15}")
P4 = previsioni(4)
for slot in (128, 256, 400, 600, 900, 1400):
    hA, mA, _   = simula(slot)
    hB, mB, pf  = simula(slot, 4, P4)
    gib = slot * MIB / 1024
    byte_tok = pf * MIB / T                      # MiB prefetchati per token
    banda = byte_tok * 8 / 1024                  # GiB/s a 8 token/s
    print(f'{slot:6d} {gib:6.2f} {hA:9.1f}% {hB:14.1f}% {byte_tok:18.0f} MiB {banda:12.1f} GiB/s')

# ------------------------------------------------------------------------
# LA FINESTRA E' L'UNICA MANOPOLA: piu' e' profonda, piu' indovina e piu'
# spreca. E il conto della banda va fatto anche per la LRU pura, dove i miss
# a domanda vanno copiati comunque -- e' quello il vero pavimento.
print()
print(f"{'slot':>6} {'W':>3} {'hit':>7} {'copie/token':>12} {'banda a 8 t/s':>15}  PCIe 3.0 x16 = ~12 GiB/s")
for slot in (400, 900, 1400, 2400):
    for W in (0, 1, 2, 4):
        P = previsioni(W) if W else None
        h, m, pf = simula(slot, W, P)
        copie = (m + pf) / T                       # miss a domanda + prefetch
        banda = copie * MIB * 8 / 1024
        segno = 'OK ' if banda <= 12 else 'NO '
        print(f'{slot:6d} {W:3d} {h:6.1f}% {copie:11.0f} {banda:12.1f} GiB/s  {segno}')

# ------------------------------------------------------------------------
# CORREZIONE 5/8 sera: il PCIe di questa macchina e' 4.0 x16, non 3.0.
# Verificato con nvidia-smi: pcie.link.gen.max=4, width=16 (il gen.current=1 e'
# solo il risparmio a riposo). Sono ~25 GiB/s pratici invece di ~12.
#
# E si aggiunge la colonna che conta davvero. La banda totale dice se il bus
# regge; i MILLISECONDI ESPOSTI dicono quanto si aspetta -- perche' il prefetch
# viaggia in parallelo al calcolo, ma un miss a domanda no: quello ferma tutto.
BUS = 25.0     # GiB/s pratici, PCIe 4.0 x16
print()
print(f"{'slot':>6} {'GiB':>6} {'W':>3} {'hit':>7} {'miss/tok':>9} {'ms ESPOSTI':>11} {'banda':>10} {'verdetto':>9}")
for slot in (350, 400, 600, 900, 1400, 2400):
    for W in (0, 1, 2, 4):
        P = previsioni(W) if W else None
        h, m, pf = simula(slot, W, P)
        miss_tok = m / T
        esposti  = miss_tok * MIB / 1024 / BUS * 1000        # ms/token bloccanti
        banda    = (m + pf) / T * MIB * 8 / 1024             # GiB/s a 8 t/s
        ok = 'OK' if banda <= BUS else 'satura'
        print(f'{slot:6d} {slot*MIB/1024:6.2f} {W:3d} {h:6.1f}% {miss_tok:8.0f} {esposti:10.1f} {banda:9.1f} {ok:>9}')
print()
print(f'  metro: oggi il token costa 128 ms con gli esperti calcolati su CPU.')
print(f'  di quei 128, ~65 sono calcolo CPU che sparirebbe portandoli in VRAM.')

# ------------------------------------------------------------------------
# RIDURRE IL COSTO DEL PREDITTORE. Il calcolo e' l'1,4% e non e' il problema:
# il problema e' la BANDA sprecata, perche' si prefetchano 6 esperti per
# previsione per averne ~4 giusti. Ma le previsioni in cima alla classifica
# valgono molto piu' di quelle in fondo -- quindi si taglia la coda.
def simula_topn(slot, W, N):
    from collections import OrderedDict
    P = {}
    for L in H:
        for k in range(1, W+1):
            Tg = L + k
            if Tg in V and Tg in gate:
                s = H[L] @ gate[Tg].T + bias.get(Tg, 0.0)
                ordine = np.argsort(-s, axis=1)[:, :N]      # ORDINATI, non solo i primi N a caso
                P[(L, Tg)] = ordine
    cache = OrderedDict(); miss = dom = pf = 0
    for t in range(T):
        for L in range(NL):
            if L not in V: continue
            if W and L in H:
                for k in range(1, W+1):
                    key = (L, L+k)
                    if key not in P: continue
                    for e in P[key][t]:
                        c = (L+k, int(e))
                        if c not in cache:
                            cache[c] = True; pf += 1
                            if len(cache) > slot: cache.popitem(last=False)
                        else: cache.move_to_end(c)
            for e in V[L][t]:
                c = (L, int(e)); dom += 1
                if c in cache: cache.move_to_end(c)
                else:
                    miss += 1; cache[c] = True
                    if len(cache) > slot: cache.popitem(last=False)
    return (dom-miss)/dom*100, miss/T, (miss+pf)/T

BUS = 24.35   # misurato, non di targa
print()
print(f"{'slot':>5} {'W':>2} {'topN':>5} {'hit':>7} {'miss/tok':>9} {'ms esposti':>11} {'banda':>10} {'% del bus':>10}")
for slot in (350, 600):
    for W in (1, 2, 3):
        for N in (2, 3, 4, 6):
            h, m, tot = simula_topn(slot, W, N)
            esp = m * MIB / 1024 / BUS * 1000
            bw  = tot * MIB * 8 / 1024
            print(f'{slot:5d} {W:2d} {N:5d} {h:6.1f}% {m:8.0f} {esp:10.1f} {bw:9.1f} {bw/BUS*100:9.0f}%')
