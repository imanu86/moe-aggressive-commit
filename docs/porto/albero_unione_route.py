# QUANTO PICCOLA PUO' DIVENTARE L'UNIONE DELLE ROUTE DI K RAMI?
#
# LA DOMANDA, e da dove nasce
# ---------------------------
# Tutta l'aritmetica che ha chiuso Jacobi -- e il pricing di oggi -- poggia sulla
# curva del working set misurata su TOKEN CONSECUTIVI: 258 esperti distinti per
# 1 token, 447 per 2, 1.244 per 8, 4.680 estrapolati per 92.
#
# Ma i rami di un albero di speculazione NON sono token consecutivi. Stanno
# tutti nella STESSA posizione, dopo lo STESSO prefisso, e differiscono solo per
# quale token si prova a mettere. L'intuizione dell'utente: se i loro stati
# nascosti sono quasi uguali, le route sono quasi uguali, l'unione non esplode,
# e il pareggio di Jacobi e' stato calcolato con il numero sbagliato.
#
# COME SI RISPONDE SENZA MACCHINA E SENZA CODICE NEL RUNTIME
# -----------------------------------------------------------
# Non possiamo simulare i rami veri: per sapere le route del ramo "ti" servirebbe
# lo stato nascosto di quel ramo, che richiede un passaggio in avanti. La traccia
# ha solo il cammino percorso.
#
# Ma possiamo calcolare il CASO MIGLIORE ASSOLUTO, che e' un limite superiore al
# beneficio e quindi decide da solo se la porta e' chiusa:
#
#   per ogni ancora t, invece dei K token CONSECUTIVI prendiamo i K stati
#   nascosti PIU' VICINI a quello di t in tutta la traccia, strato per strato,
#   e contiamo l'unione delle loro route.
#
# Nessun insieme di K rami puo' fare meglio: sono gli stati piu' simili che
# esistono nei dati, scelti col senno di poi e in modo diverso per ogni strato
# (un vantaggio che nessun albero reale ha). Se nemmeno cosi' l'unione si
# comprime, allora non si comprime per nessun albero, e il verdetto su Jacobi
# regge con il numero giusto invece che con un'estrapolazione.
#
# IL CANCELLO DI CONTROLLO
# ------------------------
# Il braccio CONSECUTIVI deve riprodurre la curva gia' misurata (258/447/1.244).
# Se non la riproduce, e' rotta la pipeline, non la tesi.
#
# UN VINCOLO STRUTTURALE DA VERIFICARE, che gioca CONTRO l'intuizione
# -------------------------------------------------------------------
# DSV4 instrada i primi strati per HASH DELL'ID DEL TOKEN (ffn_gate_tid2eid,
# hash_layer_count=3): li' due token candidati diversi vanno su esperti
# scorrelati PER COSTRUZIONE, e la condivisione e' quella del caso. Lo script
# stampa quali strati hanno davvero un gate imparato.
import sys, os
import numpy as np
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
from gguf import GGUFReader

D   = r'D:\ds4_work\dump'
MOD = r'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
K_TOPK  = 6
MIB     = 6.75
BANDA   = 24.35     # GiB/s, PCIe 4.0 x16 misurata
HIT     = 0.44      # tasso di colpi della cache a 380 slot
PAVIMENTO = 52.7    # ms per PASSAGGIO (lanci, confini, attenzione, densi)
CALCOLO   = 16.3    # ms di calcolo esperti su GPU a batch 1
METRO_MS  = 108.0   # ms/token del nostro migliore (9,26 t/s)
ANCORE  = 200       # ancore campionate (basta per una media)

# ------------------------------------------------------------------ lettura
idx = {}
for l in open(os.path.join(D, 'INDICE.tsv')):
    p = l.rstrip('\n').split('\t')
    if p[0] == 'file':
        continue
    idx.setdefault(p[1], []).append((int(p[2]), p[0], p[3], [int(x) for x in p[4:8]]))

def leggi(nome):
    # piu' chiamate per tensore: vanno concatenate NELL'ORDINE. E ffn_moe_topk e'
    # una VISTA con stride (le prime 6 righe di un argsort su 256): letta come
    # contigua da' spazzatura plausibile.
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
gate = {}
for t in r.tensors:
    if '.ffn_gate_inp.weight' in t.name:
        gate[int(t.name.split('.')[1])] = np.array(t.data, np.float32).reshape(256, 4096)

NL = 43
H = {L: leggi(f'ffn_norm-{L}')     for L in range(NL) if f'ffn_norm-{L}' in idx}
V = {L: leggi(f'ffn_moe_topk-{L}') for L in range(NL) if f'ffn_moe_topk-{L}' in idx}
T = min(min(v.shape[0] for v in V.values()), min(h.shape[0] for h in H.values()))
strati = sorted(set(H) & set(V) & set(gate))
senza_gate = sorted(set(H) & set(V) - set(gate))

print(f'traccia {T} token x {len(strati)} strati con stato+route+gate')
print(f'strati SENZA gate imparato (instradati per hash dell id token): {senza_gate}')
print(f'  -> su quegli strati due candidati diversi sono scorrelati PER COSTRUZIONE')
print()

# stati normalizzati: la route e' argmax(W.h), invariante alla scala di h,
# quindi la vicinanza che conta e' quella angolare
Hn = {}
for L in strati:
    h = H[L][:T].astype(np.float32)
    n = np.linalg.norm(h, axis=1, keepdims=True)
    Hn[L] = h / np.maximum(n, 1e-9)

VER = {L: V[L][:T] for L in strati}

rng = np.random.default_rng(0)
ancore = rng.choice(np.arange(0, T - 32), size=min(ANCORE, T - 32), replace=False)

def unione_consecutivi(K):
    """I K token CONSECUTIVI a partire dall'ancora: riproduce la curva nota."""
    tot = []
    for t0 in ancore:
        s = set()
        for L in strati:
            for e in VER[L][t0:t0+K].ravel():
                s.add((L << 16) | int(e))
        tot.append(len(s))
    return float(np.mean(tot))

def unione_vicini(K):
    """I K stati PIU' VICINI all'ancora, scelti indipendentemente per ogni
       strato: il caso migliore assoluto, irraggiungibile da un albero vero."""
    tot = []
    vicini = {}
    for L in strati:
        sim = Hn[L][ancore] @ Hn[L].T                    # [ancore, T]
        vicini[L] = np.argpartition(-sim, K, axis=1)[:, :K]
    for i in range(len(ancore)):
        s = set()
        for L in strati:
            for t in vicini[L][i]:
                for e in VER[L][t]:
                    s.add((L << 16) | int(e))
        tot.append(len(s))
    return float(np.mean(tot))

def unione_vicini_coerenti(K):
    """I K stati piu' vicini scelti UNA VOLTA su uno strato centrale e poi
       applicati a TUTTI gli strati. A differenza di unione_vicini questo e' un
       raggruppamento REALIZZABILE: sono K posizioni vere, non una scelta
       diversa per ogni strato. E' il caso migliore ONESTO."""
    Lrif = strati[len(strati)//2]
    sim  = Hn[Lrif][ancore] @ Hn[Lrif].T
    vic  = np.argpartition(-sim, K, axis=1)[:, :K]
    tot = []
    for i in range(len(ancore)):
        s = set()
        for L in strati:
            for t in vic[i]:
                for e in VER[L][t]:
                    s.add((L << 16) | int(e))
        tot.append(len(s))
    return float(np.mean(tot))

def riga(K, u, etichetta):
    nonres  = u * (1 - HIT)
    trasp   = nonres * MIB / 1024 / BANDA * 1000
    passo   = PAVIMENTO + CALCOLO + trasp
    pareggio = passo / METRO_MS
    print(f'{etichetta:>14} {K:4d} {u:8.0f} {u/(K*258)*100:6.0f}% {trasp:8.1f} {passo:9.1f} '
          f'{pareggio:9.2f} {min(K, 99):8d}  {"SI" if pareggio <= K else "no":>3}')

print(f'{"gruppo":>14} {"K":>4} {"unione":>8} {"vs K x258":>7} {"trasp ms":>8} '
      f'{"passo ms":>9} {"pareggio":>9} {"max fis.":>8}  {"?":>3}')
for K in (1, 2, 4, 8, 10, 16):
    riga(K, unione_consecutivi(K), 'CONSECUTIVI')
    if K > 1:
        riga(K, unione_vicini_coerenti(K), 'VICINI COER.')
        riga(K, unione_vicini(K), 'PIU VICINI')
print()
print('  CONSECUTIVI e il controllo: deve dare 258 / 447 / 751 / 1.244 (curva 5/8).')
print('  PIU VICINI e il limite superiore del beneficio: nessun albero fa meglio.')
print('  "pareggio" = token da accettare per passo per pareggiare 108 ms/token;')
print('  "max fis." = il massimo accettabile (la profondita dell albero).')
print('  Se pareggio > max fisico, la porta e chiusa PER COSTRUZIONE.')
