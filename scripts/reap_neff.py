"""Track REAP-ds4 — firme di routing (n_eff@64 + reuse) da una dir di trace CSV.

Metrica di EQUIVALENZA per la replica pubblica (task #16). Calcola, per un set di
trace_p*.csv (formato pos,layer,n,e0..e5,w0..w5 della patch 0006):

  n_eff@64  = exp(H) della distribuzione d'uso degli expert per (file, layer) sui
              PRIMI 64 token di decode del file. Due varianti:
                - count   : H sui conteggi di selezione
                - weighted: H sui gate-weight sommati (equivalente informativo alla
                            massa di routing)
              n_eff = numero EFFICACE di expert distinti = quanto "stretto" e' il
              routing (256 = uso uniforme; piccolo = concentrato).
  reuse     = recall top-6 prev-token same-layer = |E(pos)&E(pos-1)| / |E(pos)|,
              mediato su tutti i (file, layer, pos>0).

Riferimento BonusX (riprodotto da runs/reap/2026-07-05_trace_dominio/trace_dominio.tgz):
  n_eff@64 count ~46.4, weighted ~39.6, reuse ~0.395. Un surrogato pubblico e'
  "visto stretto quanto" se n_eff@64 ~ 35-50 e reuse > 0.30.

Uso:
  python scripts/reap_neff.py --tracedir DIR [--out neff.json] [--label nome]
  python scripts/reap_neff.py --tgz PATH.tgz [...]   # estrae e analizza un tgz
"""
import argparse
import csv
import glob
import json
import math
import os
import statistics as st
import tarfile
import tempfile
from collections import Counter, defaultdict

WINDOW = 64
N_SEL = 6


def _entropy_neff(counter):
    tot = sum(counter.values())
    if tot <= 0:
        return None
    h = -sum((v / tot) * math.log(v / tot) for v in counter.values() if v > 0)
    return math.exp(h)


def analyze_dir(tracedir):
    files = [f for f in sorted(glob.glob(os.path.join(tracedir, "trace_p*.csv")))
             if "repeat" not in os.path.basename(f)]
    if not files:
        # accetta anche nomi trace_*.csv generici
        files = [f for f in sorted(glob.glob(os.path.join(tracedir, "trace_*.csv")))
                 if "repeat" not in os.path.basename(f)]
    if not files:
        raise SystemExit(f"nessuna trace_*.csv in {tracedir}")

    neff_count, neff_weight, reuse = [], [], []
    per_file = {}
    for path in files:
        rows = []
        with open(path) as fh:
            rd = csv.DictReader(fh)
            if "w0" not in rd.fieldnames:
                raise SystemExit(f"{path}: trace senza colonne pesi (w0..w5)")
            for r in rd:
                pos, layer, n = int(r["pos"]), int(r["layer"]), int(r["n"])
                es = [(int(r[f"e{i}"]), float(r[f"w{i}"])) for i in range(n)]
                rows.append((pos, layer, [(e, w) for e, w in es if e >= 0]))
        allpos = sorted({p for p, _, _ in rows})
        win = set(allpos[:WINDOW])
        cnt = defaultdict(Counter)
        wsum = defaultdict(Counter)
        layer_pos = defaultdict(dict)   # layer -> pos -> set(experts)
        for pos, layer, es in rows:
            layer_pos[layer][pos] = {e for e, _ in es}
            if pos in win:
                for e, w in es:
                    cnt[layer][e] += 1
                    wsum[layer][e] += w
        fc, fw = [], []
        for layer in cnt:
            nc = _entropy_neff(cnt[layer])
            nw = _entropy_neff(wsum[layer])
            if nc:
                neff_count.append(nc)
                fc.append(nc)
            if nw:
                neff_weight.append(nw)
                fw.append(nw)
        fr = []
        for layer, posmap in layer_pos.items():
            ps = sorted(posmap)
            for i in range(1, len(ps)):
                a, b = posmap[ps[i]], posmap[ps[i - 1]]
                if a:
                    v = len(a & b) / len(a)
                    reuse.append(v)
                    fr.append(v)
        per_file[os.path.basename(path)] = {
            "n_pos": len(allpos),
            "neff64_count_mean": round(st.mean(fc), 3) if fc else None,
            "neff64_weighted_mean": round(st.mean(fw), 3) if fw else None,
            "reuse_prevtok_mean": round(st.mean(fr), 4) if fr else None,
        }

    def summ(xs):
        return None if not xs else {
            "mean": round(st.mean(xs), 3), "median": round(st.median(xs), 3),
            "min": round(min(xs), 3), "max": round(max(xs), 3), "n": len(xs)}

    return {
        "tracedir": tracedir.replace("\\", "/"),
        "n_files": len(files), "window_tokens": WINDOW,
        "neff64_count": summ(neff_count),
        "neff64_weighted": summ(neff_weight),
        "reuse_prevtok_same_layer_top6": summ(reuse),
        "per_file": per_file,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracedir")
    ap.add_argument("--tgz", help="tgz contenente le trace_*.csv (le estrae in tmp)")
    ap.add_argument("--out")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()

    if a.tgz:
        tmp = tempfile.mkdtemp(prefix="neff_")
        with tarfile.open(a.tgz) as tf:
            try:
                tf.extractall(tmp, filter="data")
            except TypeError:      # Python < 3.12 senza filtro
                tf.extractall(tmp)
        # cerca la sotto-dir con le trace
        tracedir = tmp
        for root, _d, fs in os.walk(tmp):
            if any(f.startswith("trace_") and f.endswith(".csv") for f in fs):
                tracedir = root
                break
    else:
        tracedir = a.tracedir
    if not tracedir:
        raise SystemExit("serve --tracedir o --tgz")

    res = analyze_dir(tracedir)
    if a.label:
        res["label"] = a.label
    bonusx = {"neff64_count": 46.4, "neff64_weighted": 39.6, "reuse": 0.395}
    res["bonusx_reference"] = bonusx
    nc = res["neff64_count"]["mean"] if res["neff64_count"] else None
    nw = res["neff64_weighted"]["mean"] if res["neff64_weighted"] else None
    ru = (res["reuse_prevtok_same_layer_top6"]["mean"]
          if res["reuse_prevtok_same_layer_top6"] else None)
    valid = (nc is not None and 35 <= nc <= 50 and ru is not None and ru > 0.30)
    res["equivalence_verdict"] = {
        "criterion": "n_eff64_count in [35,50] AND reuse > 0.30",
        "neff64_count": nc, "neff64_weighted": nw, "reuse": ru,
        "valid": bool(valid)}

    out = a.out
    if out:
        json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in
                      ("label", "n_files", "neff64_count", "neff64_weighted",
                       "reuse_prevtok_same_layer_top6", "bonusx_reference",
                       "equivalence_verdict") if k in res}, indent=1))
    if out:
        print("scritto", out)


if __name__ == "__main__":
    main()
