"""Track REAP-ds4 — bootstrap CI per la replica pubblica (task #16).

Legge results_raw.csv (config: full, reap_k50, rand50_s0/s1/s2; chunk dom_chunk0..9)
prodotto da run_eval.sh sul corpus surrogato, e calcola per reap_k50 e rand (per seed
+ media cross-seed) il rapporto di ppl appaiato per-chunk vs full, con bootstrap CI95
(percentile, B=10000, seed fisso) sul geomean — stesso metodo di paper_ci.py /
reap_eval_summary_v2.py, per confronto diretto col ramo BonusX.

Verdetto replica: reap_k50 e' "lossless" se il CI95 del geomean-ratio ATTRAVERSA 1.0
(come su BonusX: reap/dom 1.010x CI [0.996,1.025]).

Uso: python scripts/reap_public_replica_ci.py --raw PATH/results_raw.csv [--out PATH]
"""
import argparse
import json
import math
import os
import random
import re

ROW = re.compile(
    r"^(?P<cfg>[\w]+),(?P<chunk>[\w]+),rc=(?P<rc>\d+),tokens=(?P<tokens>\d+) "
    r"scored=(?P<scored>\d+) nll=(?P<nll>[\d.]+) avg_nll=(?P<avg>[\d.]+) ppl=(?P<ppl>[\d.]+)")
B = 10000
SEED = 12345


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def boot_ci(paired, b=B, seed=SEED):
    rng = random.Random(seed)
    n = len(paired)
    stats = sorted(geomean([paired[rng.randrange(n)] for _ in range(n)]) for _ in range(b))
    return stats[int(0.025 * b)], stats[int(0.975 * b)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = {}
    for line in open(a.raw):
        m = ROW.match(line.strip())
        if not m:
            continue
        d = m.groupdict()
        assert d["rc"] == "0", f"run fallita: {line}"
        rows[(d["cfg"], d["chunk"])] = {
            "scored": int(d["scored"]), "nll": float(d["nll"]),
            "avg_nll": float(d["avg"]), "ppl": float(d["ppl"])}

    cfgs = sorted({c for c, _ in rows})
    chunks = sorted({k for _, k in rows if k.startswith("dom")})
    res = {"_meta": {"raw": a.raw.replace("\\", "/"), "bootstrap": B, "seed": SEED,
                     "n_chunks": len(chunks),
                     "bonusx_reference": "reap/dom 1.010x CI[0.996,1.025] LOSSLESS; "
                                         "rand/dom 1.388x (runs/reap/2026-07-05_eval_biasmask_v2)"},
           "aggregate_ppl": {}, "paired_vs_full": {}, "random_multiseed": {},
           "verdicts": []}

    def agg(cfg):
        if not all((cfg, k) in rows for k in chunks):
            return None
        tn = sum(rows[(cfg, k)]["nll"] for k in chunks)
        ts = sum(rows[(cfg, k)]["scored"] for k in chunks)
        return round(math.exp(tn / ts), 4)

    for c in cfgs:
        v = agg(c)
        if v is not None:
            res["aggregate_ppl"][c] = v

    for c in cfgs:
        if c == "full" or not all((c, k) in rows and ("full", k) in rows for k in chunks):
            continue
        paired = [math.exp(rows[(c, k)]["avg_nll"] - rows[("full", k)]["avg_nll"])
                  for k in chunks]
        gm = geomean(paired)
        lo, hi = boot_ci(paired)
        res["paired_vs_full"][c] = {
            "per_chunk_ppl_ratio": [round(x, 4) for x in paired],
            "geomean": round(gm, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "crosses_1.0": bool(lo <= 1.0 <= hi),
            "ppl_ratio_aggregate": (round(res["aggregate_ppl"][c] / res["aggregate_ppl"]["full"], 4)
                                    if "full" in res["aggregate_ppl"] else None)}

    seeds = {c: res["paired_vs_full"][c]["geomean"]
             for c in cfgs if c.startswith("rand50_s") and c in res["paired_vs_full"]}
    if seeds:
        vals = list(seeds.values())
        res["random_multiseed"] = {"per_seed": seeds,
                                   "mean": round(sum(vals) / len(vals), 4),
                                   "min": round(min(vals), 4), "max": round(max(vals), 4)}

    rk = res["paired_vs_full"].get("reap_k50")
    if rk:
        loss = rk["crosses_1.0"]
        res["verdicts"].append(
            f"reap_k50 dom geomean {rk['geomean']}x CI95 {rk['ci95']} -> "
            f"{'LOSSLESS (CI crosses 1.0, replica del BonusX)' if loss else 'NON-lossless (CI sopra 1.0)'}")
    rnd = res.get("random_multiseed", {}).get("mean")
    if rk and rnd is not None:
        ok = rnd > rk["geomean"]
        res["verdicts"].append(
            f"random dom mean {rnd}x (min {res['random_multiseed']['min']}) "
            f"{'>' if ok else '<='} reap {rk['geomean']}x -> "
            f"{'PASS selezione-conta (replica del BonusX)' if ok else 'FAIL'}")

    out = a.out or os.path.join(os.path.dirname(a.raw), "replica_ci.json")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in
                      ("aggregate_ppl", "paired_vs_full", "random_multiseed", "verdicts")},
                     indent=1))
    print("scritto", out)


if __name__ == "__main__":
    main()
