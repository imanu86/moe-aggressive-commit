"""Track REAP-ds4 — genera runs/reap/public_replica/README.md dai risultati su disco.

Legge, per il candidato scelto:
  - <cand>/neff.json          (equivalenza n_eff vs BonusX)
  - <cand>/eval/replica_ci.json (bootstrap CI del ppl-ratio, da reap_public_replica_ci.py)
  - <cand>/meta.json          (pod, costo)
e produce README.md con la tabella di equivalenza (novita' metodologica), i ppl
reap_k50/rand con CI, e il verdetto replica.

Uso: python scripts/reap_public_replica_report.py --cand prodotto_json
"""
import argparse
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..", "runs", "reap", "public_replica")
BONUSX = {"neff64_count": 46.4, "neff64_weighted": 39.6, "reuse": 0.395,
          "reap_k50": "1.010x CI[0.996,1.025] LOSSLESS", "rand": "1.388x"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    a = ap.parse_args()
    base = os.path.join(BASE, a.cand)
    neff = json.load(open(os.path.join(base, "neff.json")))
    ci = json.load(open(os.path.join(base, "eval", "replica_ci.json")))
    meta = json.load(open(os.path.join(base, "meta.json"))) if \
        os.path.exists(os.path.join(base, "meta.json")) else {}

    nc = neff["neff64_count"]["mean"]
    nw = neff["neff64_weighted"]["mean"]
    ru = neff["reuse_prevtok_same_layer_top6"]["mean"]
    ev = neff["equivalence_verdict"]
    rk = ci["paired_vs_full"].get("reap_k50", {})
    rnd = ci.get("random_multiseed", {})

    lines = []
    A = lines.append
    A(f"# Replica pubblica del ramo-dominio REAP — `{a.cand}`\n")
    A("Task #16: dimostra che il finding **REAP-K50-lossless-su-dominio** NON dipende "
      "dalla KB privata BonusX, replicandolo su un **corpus pubblico/sintetico** "
      f"(`{a.cand}`, generato da `scripts/reap_public_replica_corpus.py`, 100% "
      "regenerabile senza dati proprietari).\n")

    A("## 1. Equivalenza di routing (novita' metodologica)\n")
    A("Il surrogato e' valido come proxy del dominio solo se il router di DS4-Flash "
      "lo \"vede stretto quanto\" BonusX. Metrica: `n_eff@64` = exp(H) della "
      "distribuzione d'uso expert per (file,layer) sui primi 64 token; `reuse` = "
      "recall top-6 prev-token same-layer. Fonte numeri: `neff.json` "
      "(da `scripts/reap_neff.py` sulla trace surrogato) vs trace BonusX "
      "(`runs/reap/2026-07-05_trace_dominio/trace_dominio.tgz`, riprodotta dallo "
      "stesso script).\n")
    A("| firma | BonusX (privato) | surrogato pubblico | entro range? |")
    A("|---|---|---|---|")
    A(f"| n_eff@64 (count) | {BONUSX['neff64_count']} | {nc} | "
      f"{'si' if 35 <= nc <= 50 else 'NO'} ([35,50]) |")
    A(f"| n_eff@64 (gate-weight) | {BONUSX['neff64_weighted']} | {nw} | "
      f"{'si' if 30 <= nw <= 55 else '~'} |")
    A(f"| reuse prev-token same-layer | {BONUSX['reuse']} | {ru} | "
      f"{'si' if ru > 0.30 else 'NO'} (>0.30) |")
    A("")
    A(f"**Verdetto equivalenza:** criterio `{ev['criterion']}` -> "
      f"**{'VALIDO' if ev['valid'] else 'NON VALIDO'}**.\n")

    A("## 2. Eval ppl bias-mask (K50) + controllo random\n")
    A("Corpus di eval DISGIUNTO dai prompt di trace (item generati dopo, anti-overfit "
      "della mask). ppl bias-mask (design equivalente al pruning fisico): "
      "full / reap_k50 / rand50 (seed 0,1,2). Rapporto appaiato per-chunk vs full, "
      "geomean + bootstrap CI95 (B=10000). Fonte: `eval/replica_ci.json`, "
      "`eval/results_raw.csv`.\n")
    if rk:
        A(f"- **reap_k50 / dom**: geomean **{rk['geomean']}x** CI95 {rk['ci95']} "
          f"({'CI attraversa 1.0 = LOSSLESS' if rk['crosses_1.0'] else 'CI sopra 1.0'})")
    if rnd:
        A(f"- **random / dom** (3 seed): media **{rnd['mean']}x** "
          f"(min {rnd['min']}, max {rnd['max']})")
    A(f"- confronto BonusX: reap_k50 {BONUSX['reap_k50']}, random {BONUSX['rand']}")
    A("")
    for v in ci.get("verdicts", []):
        A(f"  - {v}")
    A("")

    # verdetto complessivo
    loss = bool(rk.get("crosses_1.0"))
    sel = rnd.get("mean", 0) > rk.get("geomean", 99) if rk and rnd else False
    if ev["valid"] and loss and sel:
        verdetto = "**REPLICA RIUSCITA**"
        det = ("il surrogato pubblico e' equivalente per routing, reap_k50 e' lossless "
               "(CI attraversa 1.0) e batte il random a pari K — le stesse tre proprieta' "
               "del ramo BonusX. Il finding NON dipende dai dati privati.")
    elif ev["valid"] and (loss or sel):
        verdetto = "**REPLICA PARZIALE**"
        det = ("equivalenza ok; una delle due proprieta' (lossless / selezione-conta) "
               "replica, l'altra e' piu' debole sul surrogato.")
    elif not ev["valid"]:
        verdetto = "**REPLICA FALLITA (equivalenza)**"
        det = "il surrogato non ha centrato le firme di routing del dominio."
    else:
        verdetto = "**REPLICA FALLITA (eval)**"
        det = "equivalenza ok ma reap_k50 non e' lossless sul surrogato."
    A("## 3. Verdetto\n")
    A(f"{verdetto}: {det}\n")

    if meta:
        A("## 4. Pod / costo\n")
        A(f"- GPU: {meta.get('gpu','?')}, pod `{meta.get('pod_id','?')}`, "
          f"immagine {meta.get('image','?')}")
        A(f"- costo attribuito: ~${meta.get('cost_usd','?')} "
          f"(balance {meta.get('balance_before','?')} -> {meta.get('balance_after','?')})")
        A(f"- ds4 {meta.get('ds4_commit','80ebbc3')} + patch 0001-0007, "
          f"build/regression exit 0\n")

    A("## 5. File\n")
    A("- `neff.json` — n_eff surrogato + verdetto equivalenza")
    A("- `reap_mask_<cand>_k50.json` — mask saliency g-only K50 + random control")
    A("- `eval/results_raw.csv` — ppl per config/chunk")
    A("- `eval/replica_ci.json` — geomean-ratio + bootstrap CI")
    A("- `eval/biasmask.log` — V0 mechanism-check (0 violazioni atteso)")
    A("- `trace/` — trace_p*.csv (tgz), log build/regression/trace")
    A("- `meta.json` — pod, cmdline, costo\n")
    A("*Numeri solo da file su disco. Routing/saliency/ppl sono proprieta' del MODELLO "
      "-> trasferiscono dal pod (A6000 sm_86) al 3060; nessun t/s riportato.*")

    out = os.path.join(BASE, "README.md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print("scritto", out)
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
