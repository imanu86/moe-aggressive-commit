"""SPEX D2 — fit del predittore hidden sul modello di deployment (DS4-Flash 2-bit).

Dati: runs/spex/2026-07-05_trace_pod/  (trace raccolte su pod, patch 0006+0007)
  routing/*.csv  : pos,layer,n,e0..e5,w0..w5   (router reale, gate-weights)
  dsh/*.dsh      : DSH1 header(magic,ver,n_layer,n_embd) + record(pos u32, layer u32, fp16[n_embd])
                   l'hidden e' l'INPUT ESATTO del router di (pos, layer) [ffn_norm].

Predittori fittati (probe lineare ridge per-LAYER, multi-label 256 expert):
  next-layer : h(pos, L)  ->  experts(pos, L+1)     [prefetch intra-token]
  next-token : h(pos, L)  ->  experts(pos+1, L)     [prefetch inter-token]
Baselines sugli stessi TEST pair: prev-token same-layer (identita') e window-8 top-K.

Split PER-DOCUMENTO (prompt) 60/20/20 (train/calib/test) con seed fisso, pool cross-set
per il train, metriche riportate PER SET (generale_ita / coding_en / dominio_kb) sul test.
Metrica: recall@{6,12,32} sul top-6 reale. Output: runs/spex/fit_results.json + stampa.

Uso:  python scripts/spex_fit_predictor.py [--data DIR] [--ridge 10.0] [--smoke]
      --smoke: solo parsing/shape check sui file disponibili, niente fit completo.
"""
import argparse
import csv
import glob
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, 'runs', 'spex', '2026-07-05_trace_pod')
SEED = 42


def read_dsh(path):
    """Ritorna (n_layer, n_embd, dict[(pos,layer)] = np.float16[n_embd])."""
    out = {}
    with open(path, 'rb') as f:
        head = f.read(16)
        if len(head) < 16 or head[:4] != b'DSH1':
            raise ValueError(f'{path}: header non DSH1')
        _, n_layer, n_embd = struct.unpack('<III', head[4:16])
        rec = 8 + 2 * n_embd
        while True:
            b = f.read(rec)
            if len(b) < rec:
                break
            pos, layer = struct.unpack('<II', b[:8])
            out[(pos, layer)] = np.frombuffer(b[8:], dtype=np.float16)
    return n_layer, n_embd, out


def read_routing(path):
    """dict[(pos,layer)] = [e0..e5]"""
    out = {}
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        for r in csv.DictReader(f):
            out[(int(r['pos']), int(r['layer']))] = [int(r[f'e{i}']) for i in range(6)]
    return out


def doc_name(p):
    return re.sub(r'^(routing_|hidden_)|\.(csv|dsh)$', '', os.path.basename(p))


def set_of(doc):
    for s in ('generale_ita', 'coding_en', 'dominio_kb'):
        if doc.startswith(s):
            return s
    return 'altro'


def recall(pred_ids, true6):
    t = set(true6)
    return len(t & set(pred_ids)) / len(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=DATA)
    ap.add_argument('--ridge', type=float, default=10.0)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--export-spex', default=None, help='scrive i pesi del probe next-layer in un .spex')
    ap.add_argument('--export-only', action='store_true', help='esporta e salta la PASS 2 di eval')
    a = ap.parse_args()

    dsh_files = sorted(glob.glob(os.path.join(a.data, 'dsh', '*.dsh')))
    route_files = {doc_name(p): p for p in glob.glob(os.path.join(a.data, 'routing', '*.csv'))}
    docs = []   # (doc, set, routing dict, dsh path)
    for dp in dsh_files:
        d = doc_name(dp)
        rp = route_files.get(d)
        if not rp:
            # match tollerante: routing file che contiene il nome
            cand = [p for n, p in route_files.items() if d in n or n in d]
            rp = cand[0] if cand else None
        if not rp:
            print(f'SKIP {d}: routing csv non trovato'); continue
        docs.append((d, set_of(d), rp, dp))
    print(f'documenti appaiati: {len(docs)} (dsh {len(dsh_files)}, routing {len(route_files)})')
    if not docs:
        sys.exit('nessun documento')

    if a.smoke:
        d, s, rp, dp = docs[0]
        nl, ne, H = read_dsh(dp)
        R = read_routing(rp)
        common = set(H) & set(R)
        print(f'SMOKE {d}: n_layer={nl} n_embd={ne} hidden={len(H)} routing={len(R)} comuni={len(common)}')
        k = sorted(common)[0]
        print(f'  esempio {k}: h[:4]={H[k][:4]} experts={R[k]}')
        return

    # split per-documento, stratificato per set
    rng = np.random.RandomState(SEED)
    by_set = defaultdict(list)
    for d in docs:
        by_set[d[1]].append(d)
    train, test = [], []
    for s, ds in by_set.items():
        idx = rng.permutation(len(ds))
        n_tr = max(1, int(0.7 * len(ds)))   # 70/30 (calib fusa nel train per ora; STS dopo)
        train += [ds[i] for i in idx[:n_tr]]
        test += [ds[i] for i in idx[n_tr:]]
    print(f'train docs={len(train)} test docs={len(test)}')

    # ── PASS 1: accumula gram per-layer sul TRAIN (due target)
    first = read_dsh(train[0][3]); NL, NE = first[0], first[1]
    E = 256
    XtX = np.zeros((NL, NE, NE), dtype=np.float64)  # attenzione RAM: 40*4096^2*8 = 5.4GB → fp32
    XtX = np.zeros((NL, NE, NE), dtype=np.float32)
    XtY = {'nl': np.zeros((NL, NE, E), dtype=np.float32),
           'nt': np.zeros((NL, NE, E), dtype=np.float32)}
    n_tr_pairs = Counter()
    for d, s, rp, dp in train:
        _, _, H = read_dsh(dp)
        R = read_routing(rp)
        byl = defaultdict(list)                      # layer -> [(pos, h), ...]
        for (pos, l), h in H.items():
            byl[l].append((pos, h))
        for l, rows in byl.items():
            rows.sort()
            X = np.stack([h for _, h in rows]).astype(np.float32)      # (n, NE)
            XtX[l] += X.T @ X
            for tag, keyf in (('nl', lambda p: (p, l + 1)), ('nt', lambda p: (p + 1, l))):
                mask, Y = [], []
                for i, (pos, _) in enumerate(rows):
                    tgt = R.get(keyf(pos))
                    if tgt:
                        y = np.zeros(E, dtype=np.float32); y[tgt] = 1.0
                        mask.append(i); Y.append(y)
                if mask:
                    Xm = X[mask]
                    XtY[tag][l] += Xm.T @ np.stack(Y)
                    n_tr_pairs[tag] += len(mask)
        print(f'  train {d}: ok ({len(H)} record)')
    print(f'pairs train: {dict(n_tr_pairs)}')

    # ── risolvi ridge per layer
    W = {}
    for tag in ('nl', 'nt'):
        W[tag] = np.zeros((NL, NE, E), dtype=np.float32)
        for l in range(NL):
            A = XtX[l] + a.ridge * np.eye(NE, dtype=np.float32)
            try:
                W[tag][l] = np.linalg.solve(A, XtY[tag][l])
            except np.linalg.LinAlgError:
                W[tag][l] = np.linalg.lstsq(A, XtY[tag][l], rcond=None)[0]
        print(f'probe {tag}: risolto ({NL} layer)')

    # ── EXPORT .spex (formato per il loader C del motore ds4)
    #   Header 32B: magic 'SPX1' | version u32=1 | predictor u32=2(hidden-next-layer)
    #               n_layer u32 | n_embd u32 | n_expert u32 | ridge_f32 | reserved u32
    #   Per SOURCE layer l in [0..NL-1]: W_nl[l] fp16[n_embd*n_expert] (row-major, x @ W = score[E]).
    #   score(experts di L+1) = h(pos, L) @ W[L].  L'ultimo layer ha W nullo (nessun L+1).
    if a.export_spex:
        with open(a.export_spex, 'wb') as f:
            f.write(b'SPX1')
            f.write(struct.pack('<IIIIIfI', 1, 2, NL, NE, E, float(a.ridge), 0))
            for l in range(NL):
                f.write(W['nl'][l].astype(np.float16).tobytes())   # (NE, E) row-major
        sz = os.path.getsize(a.export_spex)
        print(f'.spex esportato: {a.export_spex} ({sz/1e6:.1f} MB, {NL} layer x {NE}x{E} fp16)')
        # scrittore di riferimento python (per validare il loader C): salva anche npz
        np.savez_compressed(a.export_spex + '.npz', W_nl=W['nl'].astype(np.float16),
                            n_layer=NL, n_embd=NE, n_expert=E)
        if a.export_only:
            print('export-only: salto la PASS 2 di eval'); return

    # ── PASS 2: eval sul TEST, per set, con baseline temporali sugli STESSI pair
    res = defaultdict(lambda: defaultdict(list))
    for d, s, rp, dp in test:
        _, _, H = read_dsh(dp)
        R = read_routing(rp)
        hist = defaultdict(list)   # layer -> lista experts per window baseline (ordine pos)
        poss = sorted({p for p, _ in R})
        for pos in poss:
            for l in range(NL):
                if (pos, l) not in R:
                    continue
                true6 = R[(pos, l)]
                # baseline window-8 top-K (predice (pos,l) dai 8 pos precedenti)
                hh = Counter()
                for q in range(pos - 8, pos):
                    if (q, l) in R:
                        hh.update(R[(q, l)])
                if hh:
                    rk = [k for k, _ in sorted(hh.items(), key=lambda kv: (-kv[1], kv[0]))]
                    for K in (6, 12, 32):
                        res[s][f'win8@{K}'].append(recall(rk[:K], true6))
                if (pos - 1, l) in R:
                    res[s]['prevtok@6'].append(recall(R[(pos - 1, l)], true6))
                # probe next-layer: usa h(pos, l-1) per predire (pos, l)
                hprev = H.get((pos, l - 1))
                if hprev is not None:
                    sc = hprev.astype(np.float32) @ W['nl'][l - 1]
                    top = np.argsort(-sc)
                    for K in (6, 12, 32):
                        res[s][f'hidden_nextlayer@{K}'].append(recall(top[:K], true6))
                # probe next-token: usa h(pos-1, l) per predire (pos, l)
                hpt = H.get((pos - 1, l))
                if hpt is not None:
                    sc = hpt.astype(np.float32) @ W['nt'][l]
                    top = np.argsort(-sc)
                    for K in (6, 12, 32):
                        res[s][f'hidden_nexttok@{K}'].append(recall(top[:K], true6))

    out = {'seed': SEED, 'ridge': a.ridge, 'train_docs': [d[0] for d in train],
           'test_docs': [d[0] for d in test], 'n_train_pairs': dict(n_tr_pairs), 'results': {}}
    print('\n================ RISULTATI (test, per set) ================')
    for s in sorted(res):
        out['results'][s] = {}
        print(f'-- {s}')
        for m in sorted(res[s]):
            v = float(np.mean(res[s][m])); n = len(res[s][m])
            out['results'][s][m] = {'mean': v, 'n': n}
            print(f'   {m:22s} {v:.4f}  (n={n})')
    rp = os.path.join(REPO, 'runs', 'spex', 'fit_results.json')
    json.dump(out, open(rp, 'w'), indent=1)
    print(f'\nsalvato: {rp}')


if __name__ == '__main__':
    main()
