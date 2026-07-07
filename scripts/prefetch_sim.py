"""Part C-T2 (SPEX): recall != velocita'. Il dense-oracle predice il routing a valle
(L3->L4 recall@23=0.73), ma un segnale accurato NON e' automaticamente velocita'. Qui
SIMULO una cache LRU di esperti e misuro se il prefetch LAYER-AHEAD alza l'HIT-RATE
(= meno stall SSD = piu' veloce) vs n-gram-prefetch vs nessun-prefetch.

Il trappolone: prefetchare esperti predetti EVICTA altri; e 1 layer di anticipo potrebbe non
bastare a nascondere il fetch (percio' provo lead d=1,2,3, dove il recall CALA).

Input: hidden.bin (0007) + routing.csv (0006). Uso: python prefetch_sim.py hidden.bin routing.csv
"""
import csv
import struct
import sys
from collections import OrderedDict, defaultdict

import numpy as np

N_EMBD_DEF = 4096
N_EXPERT = 256
HID = sys.argv[1] if len(sys.argv) > 1 else "hidden.bin"
ROUT = sys.argv[2] if len(sys.argv) > 2 else "routing.csv"
PREFETCH_P = 23   # quanti esperti prefetchare per layer (budget prefetch)


def load_hidden(path):
    out = {}
    blob = open(path, "rb").read()
    assert blob[:4] == b"DSH1"
    _, n_layer, n_embd = struct.unpack_from("<III", blob, 4)
    row = 8 + n_embd * 2
    for off in range(16, len(blob) - row + 1, row):
        pos, layer = struct.unpack_from("<II", blob, off)
        out[(pos, layer)] = np.frombuffer(blob, np.float16, n_embd, off + 8).astype(np.float32)
    return out, n_embd


def load_routing(path):
    out = {}
    with open(path) as f:
        rd = csv.reader(f); next(rd, None)
        for r in rd:
            if len(r) < 9:
                continue
            try:
                pos, layer, n = int(r[0]), int(r[1]), int(r[2])
            except ValueError:
                continue
            out[(pos, layer)] = [int(r[3 + s]) for s in range(min(n, 6)) if int(r[3 + s]) >= 0]
    return out


def ridge_probe(Xtr, Ytr, Xte, n_pca=48, alpha=10.0):
    mu = Xtr.mean(0)
    U, S, Vt = np.linalg.svd(Xtr - mu, full_matrices=False)
    V = Vt[:n_pca].T
    Ztr, Zte = (Xtr - mu) @ V, (Xte - mu) @ V
    W = np.linalg.solve(Ztr.T @ Ztr + alpha * np.eye(Ztr.shape[1]), Ztr.T @ Ytr)
    return Zte @ W


def main():
    hid, n_embd = load_hidden(HID)
    rout = load_routing(ROUT)
    poss = sorted({p for (p, l) in rout})
    moe = sorted({l for (p, l) in rout})
    split = int(len(poss) * 0.7)
    tr, te = poss[:split], poss[split:]
    print(f"token {len(poss)} (train {len(tr)} test {len(te)}) | layer MoE {min(moe)}..{max(moe)}")

    # predizioni prefetch layer-ahead: per lead d e per src-layer, probe hidden(src)->exp(src+d)
    pred = {1: {}, 2: {}, 3: {}}   # pred[d][(pos,tgt)] = set(top-P esperti predetti)
    recall = {1: [], 2: [], 3: []}
    for d in (1, 2, 3):
        for src in moe:
            tgt = src + d
            if tgt not in moe:
                continue
            def build(ps):
                X, Y, T = [], [], []
                for p in ps:
                    if (p, src) in hid and (p, tgt) in rout:
                        X.append(hid[(p, src)])
                        ind = np.zeros(N_EXPERT, np.float32)
                        for e in rout[(p, tgt)]:
                            ind[e] = 1.0
                        Y.append(ind); T.append((p, rout[(p, tgt)]))
                return np.array(X), np.array(Y), T
            Xtr, Ytr, _ = build(tr)
            Xte, _, Tte = build(te)
            if len(Xtr) < 30 or len(Xte) < 5:
                continue
            sc = ridge_probe(Xtr, Ytr, Xte)
            for i, (p, true) in enumerate(Tte):
                topP = set(np.argsort(sc[i])[-PREFETCH_P:])
                pred[d][(p, tgt)] = topP
                if true:
                    recall[d].append(len(topP & set(true)) / len(true))
    for d in (1, 2, 3):
        r = np.mean(recall[d]) if recall[d] else 0
        print(f"  recall@{PREFETCH_P} lead d={d}: {r:.3f}  (lead-time = {d} layer di compute)")

    # ---- simulazione cache LRU sui token di TEST ----
    def simulate(cache_size, strategy, d=1):
        cache = OrderedDict()   # (layer,expert) -> None, ordine = recency
        hits = miss = 0

        def touch(key):
            cache[key] = None; cache.move_to_end(key)
            while len(cache) > cache_size:
                cache.popitem(last=False)
        for p in te:
            for M in moe:
                if strategy == "ahead":
                    tgt = M + d
                    for e in pred[d].get((p, tgt), ()):    # prefetch predetti per M+d
                        touch((tgt, e))
                elif strategy == "ngram":
                    prev = [q for q in te if q < p]
                    if prev and (prev[-1], M) in rout:
                        for e in rout[(prev[-1], M)]:       # prefetch = routing token precedente
                            touch((M, e))
                for e in rout.get((p, M), ()):              # processa layer M
                    if (M, e) in cache:
                        hits += 1; cache.move_to_end((M, e))
                    else:
                        miss += 1; touch((M, e))
        return hits / (hits + miss) if (hits + miss) else 0

    print(f"\nHIT-RATE cache (test), prefetch budget P={PREFETCH_P}:")
    print(f"{'cache':>6} {'no-prefetch':>12} {'ngram':>8} {'ahead d=1':>10} {'ahead d=2':>10} {'ahead d=3':>10}")
    for cs in (120, 200, 400, 800):
        base = simulate(cs, "none")
        ng = simulate(cs, "ngram")
        a1 = simulate(cs, "ahead", 1)
        a2 = simulate(cs, "ahead", 2)
        a3 = simulate(cs, "ahead", 3)
        print(f"{cs:>6} {base:>12.3f} {ng:>8.3f} {a1:>10.3f} {a2:>10.3f} {a3:>10.3f}")
    print("\nVERDETTO: il prefetch aiuta la VELOCITA' solo se ahead > no-prefetch E > ngram."
          "\nSe recall alto ma hit-rate non sale => recall != velocita' (evict/cache-pressure).")


if __name__ == "__main__":
    main()
