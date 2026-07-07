"""SPEX dense-front-end routing oracle — primo segnale.

Idea (SPEX-main): i layer densi 0-2 del DeepSeek-V4-Flash girano per primi, sono
sempre residenti, costano poco. Usare le loro hidden per PREDIRE quali esperti
instraderanno i layer MoE (3-42) → prefetch anticipato → nasconde latenza SSD.
Predittore su feature/hidden-state, NON sui logprob del router (che erano morti).

Input:
  hidden.bin  = patch 0007: righe [pos:u32][layer:u32][n_embd=4096 x f16]
  routing.csv = patch 0006: pos,layer,n,e0..e5,w0..w5 (solo layer MoE 3-42)

Predittore: ridge multi-output su hidden(layer SORGENTE) -> indicatore-expert(layer
TARGET); PCA per non overfittare (4096 feat, ~poche centinaia di token). top-k ->
recall@k dei 6 realmente instradati. Baseline: n-gram (routing del token precedente)
+ chance (k/256). Train/test split temporale (primi 70% train, ultimi 30% test) per
non barare col futuro.

Uso: python dense_oracle.py hidden.bin routing.csv
"""
import csv
import struct
import sys
from collections import defaultdict

import numpy as np

N_EMBD = 4096
N_EXPERT = 256
HID = sys.argv[1] if len(sys.argv) > 1 else "hidden.bin"
ROUT = sys.argv[2] if len(sys.argv) > 2 else "routing.csv"


def load_hidden(path):
    """{(pos,layer): np.float32[n_embd]}. File = 16B header DSH1 + record da
    [pos:u32][layer:u32][hidden:f16 x n_embd]."""
    out = {}
    with open(path, "rb") as f:
        blob = f.read()
    assert blob[:4] == b"DSH1", f"magic inatteso: {blob[:4]!r}"
    version, n_layer, n_embd = struct.unpack_from("<III", blob, 4)
    row = 8 + n_embd * 2
    start = 16
    for off in range(start, len(blob) - row + 1, row):
        pos, layer = struct.unpack_from("<II", blob, off)
        h = np.frombuffer(blob, dtype=np.float16, count=n_embd,
                          offset=off + 8).astype(np.float32)
        out[(pos, layer)] = h
    return out


def load_routing(path):
    """{(pos,layer): set(experts)}"""
    out = {}
    with open(path) as f:
        rd = csv.reader(f)
        next(rd, None)
        for r in rd:
            if len(r) < 9:
                continue
            try:
                pos, layer, n = int(r[0]), int(r[1]), int(r[2])
                out[(pos, layer)] = set(int(r[3 + s]) for s in range(min(n, 6))
                                        if int(r[3 + s]) >= 0)
            except ValueError:
                continue
    return out


def recall_at_k(pred_scores, true_sets, k):
    """media su token di |topk(pred) ∩ true| / |true|"""
    vals = []
    for sc, true in zip(pred_scores, true_sets):
        if not true:
            continue
        topk = set(np.argsort(sc)[-k:])
        vals.append(len(topk & true) / len(true))
    return float(np.mean(vals)) if vals else 0.0


def ridge_probe(Xtr, Ytr, Xte, n_pca=48, alpha=10.0):
    """PCA -> ridge multi-output; ritorna scores[te, 256]."""
    mu = Xtr.mean(0)
    Xtr0, Xte0 = Xtr - mu, Xte - mu
    # PCA via SVD sul train
    U, S, Vt = np.linalg.svd(Xtr0, full_matrices=False)
    V = Vt[:n_pca].T
    Ztr, Zte = Xtr0 @ V, Xte0 @ V
    # ridge: W = (Z'Z + aI)^-1 Z'Y
    A = Ztr.T @ Ztr + alpha * np.eye(Ztr.shape[1])
    W = np.linalg.solve(A, Ztr.T @ Ytr)
    return Zte @ W


def main():
    hid = load_hidden(HID)
    rout = load_routing(ROUT)
    poss = sorted({p for (p, l) in rout})
    moe_layers = sorted({l for (p, l) in rout})
    hid_layers = sorted({l for (p, l) in hid})
    # sorgente = primo layer che ha hidden CON overlap sulle posizioni di routing (decode).
    # I densi 0-2 sono dumpati solo in prefill (no routing lì) -> il primo utile e' L3, il
    # cui router-input = uscita del front-end denso + attention di L3 = "front-end effettivo".
    dec_pos = set(poss)
    src_dense = min((l for l in hid_layers if len({p for (p, ll) in hid if ll == l} & dec_pos) >= 30),
                    default=min(moe_layers))
    print(f"token decode: {len(poss)} | layer MoE: {min(moe_layers)}..{max(moe_layers)} "
          f"| hidden righe: {len(hid)} | layer in hidden: {min(hid_layers)}..{max(hid_layers)}")
    print(f"layer sorgente (primo con hidden in decode): L{src_dense}")
    split = int(len(poss) * 0.7)
    tr_pos, te_pos = poss[:split], poss[split:]

    print(f"\n{'src->tgt':10} {'recall@6':>9} {'recall@12':>10} {'recall@23':>10} "
          f"{'ngram@23':>9} {'chance@23':>9}")
    results = {}
    for tgt in [m for m in (4, 5, 6, 8, 12, 22, 32, 42) if m in moe_layers and m > src_dense]:
        # dataset: hidden(src_dense) del token t -> experts(tgt) del token t
        def build(pos_list):
            X, Y, T = [], [], []
            for p in pos_list:
                if (p, src_dense) in hid and (p, tgt) in rout:
                    X.append(hid[(p, src_dense)])
                    ind = np.zeros(N_EXPERT, np.float32)
                    for e in rout[(p, tgt)]:
                        ind[e] = 1.0
                    Y.append(ind)
                    T.append(rout[(p, tgt)])
            return np.array(X), np.array(Y), T
        Xtr, Ytr, _ = build(tr_pos)
        Xte, Yte, Tte = build(te_pos)
        if len(Xtr) < 30 or len(Xte) < 10:
            print(f"L{src_dense}->L{tgt:<6} (dati insuff: tr={len(Xtr)} te={len(Xte)})")
            continue
        sc = ridge_probe(Xtr, Ytr, Xte)
        r6, r12, r23 = (recall_at_k(sc, Tte, k) for k in (6, 12, 23))
        # baseline n-gram: routing del token PRECEDENTE allo stesso layer tgt
        ng_scores = []
        for i, p in enumerate([q for q in te_pos if (q, tgt) in rout]):
            prev = [q for q in poss if q < p and (q, tgt) in rout]
            s = np.zeros(N_EXPERT)
            if prev:
                for e in rout[(prev[-1], tgt)]:
                    s[e] = 1.0
            ng_scores.append(s)
        ng23 = recall_at_k(ng_scores, Tte, 23)
        chance = 23 / N_EXPERT
        results[tgt] = dict(r6=r6, r12=r12, r23=r23, ng23=ng23)
        print(f"L{src_dense}->L{tgt:<6} {r6:>9.3f} {r12:>10.3f} {r23:>10.3f} "
              f"{ng23:>9.3f} {chance:>9.3f}")

    # controllo: adiacente (src = tgt-1 hidden) come upper-bound del segnale
    print("\n[adiacente src=tgt-1, upper-bound del segnale hidden]")
    for tgt in [m for m in (4, 10, 42) if m in moe_layers and (m - 1) in {l for _, l in hid}]:
        src = tgt - 1
        def build2(pos_list):
            X, T = [], []
            for p in pos_list:
                if (p, src) in hid and (p, tgt) in rout:
                    X.append(hid[(p, src)]); T.append(rout[(p, tgt)])
            return np.array(X), T
        Xtr, _ = build2(tr_pos); Ytr = np.array([[1.0 if e in rout[(p, tgt)] else 0.0
                                                  for e in range(N_EXPERT)]
                                                 for p in tr_pos if (p, src) in hid and (p, tgt) in rout])
        Xte, Tte = build2(te_pos)
        if len(Xtr) < 30 or len(Xte) < 10:
            continue
        sc = ridge_probe(Xtr, Ytr, Xte)
        print(f"L{src}->L{tgt:<6} recall@23={recall_at_k(sc, Tte, 23):.3f}")

    print("\nVERDETTO: dense-oracle utile se recall@23 (L2->L3..) >> chance 0.09 e >= n-gram.")


if __name__ == "__main__":
    main()
