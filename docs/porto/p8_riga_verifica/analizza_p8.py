"""P8 - scompone una corsa del banco a 131k nei termini della riga di verifica.

Il modello di costo e' quello di P7 (`P7_RIGA_DI_VERIFICA_14_SETTEMBRE.md` §3.0):

    ciclo = T1 + R + H

dove `ciclo` e' il tempo fra due verifiche consecutive, `T1` e' il costo di un forward
a UNA riga (si legge dalla corsa con MTP spento, stessa profondita'), `H` e' il passo
della testa MTP, e `R` e' quello che costa la riga in piu' della verifica.

Tutto viene da numeri gia' scritti, nessuno e' dedotto in silenzio:

  results.jsonl      predicted_n, predicted_ms  -> ms per token accettato e t/s
  log/server.log     riga `spec common_specu: statistics ... #calls(b,g,a) = ...,
                     dur(b,g,a) = b, g, a ms`  -> numero di verifiche e tempo della
                     testa, CUMULATIVI: si prendono le DIFFERENZE fra richieste
  log/server.log     `graph splits = N (with bs=3), M (with bs=1)` -> lanci di grafo
  log/server.log     `graphs reused` per richiesta
  carico.jsonl       RAM disponibile minima e VRAM libera minima

Uso:
  python analizza_p8.py --corsa <cartella> [--t1-ms <ms/token a una riga>]
                        [--riferimento <cartella R1>] [--json-out f.json]
"""
import argparse
import json
import re
from pathlib import Path

RE_SPEC = re.compile(
    r"#calls\(b,g,a\)\s*=\s*(\d+)\s+(\d+)\s+(\d+).*?"
    r"#gen tokens\s*=\s*(\d+),\s*#acc tokens\s*=\s*(\d+).*?"
    r"#acc rate/pos\s*=\s*\(([^)]*)\).*?"
    r"dur\(b,g,a\)\s*=\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)\s*ms")
RE_SPLITS = re.compile(r"graph splits = (\d+) \(with bs=(\d+)\), (\d+) \(with bs=1\)")
RE_SPLITS1 = re.compile(r"graph splits = (\d+)\s*$")
RE_NODES   = re.compile(r"graph nodes\s+= (\d+) \(with bs=(\d+)\), (\d+) \(with bs=1\)")
RE_NODES1  = re.compile(r"graph nodes\s+= (\d+)\s*$")
RE_REUSED = re.compile(r"graphs reused\s*=\s*(\d+)")


def leggi_results(c):
    righe = []
    f = c / "results.jsonl"
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                righe.append(json.loads(l))
    return righe


def leggi_log(c):
    f = c / "log" / "server.log"
    if not f.exists():
        return {}
    testo = f.read_text(encoding="utf-8", errors="replace")
    spec = []
    for m in RE_SPEC.finditer(testo):
        spec.append({
            "calls_b": int(m.group(1)), "calls_g": int(m.group(2)), "calls_a": int(m.group(3)),
            "gen_tokens": int(m.group(4)), "acc_tokens": int(m.group(5)),
            "acc_per_pos": [float(x) for x in m.group(6).split(",") if x.strip()],
            "dur_b_ms": float(m.group(7)), "dur_g_ms": float(m.group(8)),
            "dur_a_ms": float(m.group(9)),
        })
    # Ogni riserva stampa due righe consecutive: `graph nodes = ...` e `graph splits = ...`.
    # Quando i due conteggi coincidono llama.cpp stampa la forma corta `graph splits = N`
    # SENZA il `(with bs=...)`, ed e' proprio il caso che interessa (la leva A porta 4 e 2 a
    # 2 e 2). Per questo lo split si legge appaiandolo alla riga `graph nodes` che lo precede,
    # non da solo: cosi' le due forme si contano allo stesso modo.
    splits = {}
    bs_corrente = None
    for riga in testo.splitlines():
        mn = RE_NODES.search(riga)
        if mn:
            bs_corrente = mn.group(2)
            continue
        mn1 = RE_NODES1.search(riga)
        if mn1:
            bs_corrente = "1"
            continue
        ms = RE_SPLITS.search(riga)
        if ms and bs_corrente is not None:
            chiave = "bs%s" % bs_corrente
            v = splits.setdefault(chiave, {"splits": 0, "splits_bs1": 0, "riserve": 0,
                                           "lanci_cuda": 0})
            v["splits"], v["splits_bs1"] = int(ms.group(1)), int(ms.group(3))
            v["lanci_cuda"] = int(ms.group(1)) - 1     # uno degli split non e' CUDA
            v["riserve"] += 1
            bs_corrente = None
            continue
        ms1 = RE_SPLITS1.search(riga)
        if ms1 and bs_corrente is not None:
            chiave = "bs%s" % bs_corrente
            v = splits.setdefault(chiave, {"splits": 0, "splits_bs1": 0, "riserve": 0,
                                           "lanci_cuda": 0})
            v["splits"] = v["splits_bs1"] = int(ms1.group(1))
            v["lanci_cuda"] = int(ms1.group(1)) - 1
            v["riserve"] += 1
            bs_corrente = None
    reused = [int(m.group(1)) for m in RE_REUSED.finditer(testo)]
    return {"spec_cumulativi": spec, "graph_splits": splits, "graphs_reused_per_richiesta": reused,
            "nan_nel_log": testo.lower().count("nan"),
            "riserve_fallite": testo.count("failed to allocate graph")}


def delta_spec(spec):
    """I contatori del server sono cumulativi: le differenze consecutive sono le richieste."""
    out = []
    prec = {"calls_a": 0, "dur_g_ms": 0.0, "gen_tokens": 0, "acc_tokens": 0}
    for s in spec:
        d_calls = s["calls_a"] - prec["calls_a"]
        d_dur_g = s["dur_g_ms"] - prec["dur_g_ms"]
        d_gen = s["gen_tokens"] - prec["gen_tokens"]
        d_acc = s["acc_tokens"] - prec["acc_tokens"]
        out.append({
            "verifiche": d_calls,
            "testa_ms_totali": round(d_dur_g, 3),
            "H_ms_per_verifica": round(d_dur_g / d_calls, 4) if d_calls else None,
            "bozza_generati": d_gen, "bozza_accettati": d_acc,
            "accettazione": round(d_acc / d_gen, 4) if d_gen else None,
            "acc_per_pos_cumulativa": s["acc_per_pos"],
        })
        prec = s
    return out


def picchi(c):
    f = c / "carico.jsonl"
    if not f.exists():
        return {}
    ram_disp, vram_usata, vram_tot, gpu = [], [], [], []
    for l in f.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if d.get("ram_disponibile_gb") is not None:
            ram_disp.append(d["ram_disponibile_gb"])
        if d.get("vram_usata_mib") is not None:
            vram_usata.append(d["vram_usata_mib"])
        if d.get("vram_totale_mib"):
            vram_tot.append(d["vram_totale_mib"])
        if d.get("gpu_util_pct") is not None:
            gpu.append(d["gpu_util_pct"])
    tot = max(vram_tot) if vram_tot else None
    return {
        "ram_disponibile_min_gb": min(ram_disp) if ram_disp else None,
        "vram_usata_max_mib": max(vram_usata) if vram_usata else None,
        "vram_totale_mib": tot,
        "vram_libera_min_mib": round(tot - max(vram_usata), 1) if (tot and vram_usata) else None,
        "gpu_util_medio_pct": round(sum(gpu) / len(gpu), 1) if gpu else None,
        "campioni": len(vram_usata),
        "corsa_valida_ram": (min(ram_disp) >= 4.0) if ram_disp else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corsa", required=True)
    ap.add_argument("--t1-ms", type=float, default=None,
                    help="ms per token del forward a UNA riga (dalla corsa con MTP spento)")
    ap.add_argument("--riferimento", default=None, help="cartella della corsa R1, per le impronte")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    c = Path(args.corsa)
    righe = leggi_results(c)
    log = leggi_log(c)
    spec_d = delta_spec(log.get("spec_cumulativi", []))

    # le richieste misurate sono quelle non di riscaldamento; le righe `spec` del log sono
    # una per richiesta CHE HA SPECULATO (i riscaldamenti compresi), in ordine.
    misurate = [r for r in righe if not r.get("riscaldamento") and r.get("valido")]
    per_caso = []
    # allineamento: le ultime len(misurate) righe spec corrispondono alle richieste misurate
    coda = spec_d[-len(misurate):] if len(spec_d) >= len(misurate) else [None] * len(misurate)
    for r, s in zip(misurate, coda):
        n = r.get("predicted_n") or 0
        ms = r.get("predicted_ms") or 0.0
        v = {
            "etichetta": r["etichetta"], "contesto": r.get("contesto"),
            "predicted_n": n, "predicted_ms": round(ms, 2),
            "ms_per_token": round(ms / n, 4) if n else None,
            "tps": round(n / (ms / 1000.0), 4) if ms else None,
            "prompt_n": r.get("prompt_n"), "cache_n": r.get("cache_n"),
            "prompt_ms": r.get("prompt_ms"),
            "draft_n": r.get("draft_n"), "draft_n_accepted": r.get("draft_n_accepted"),
            "motivo_fine": r.get("motivo_fine"),
            "impronta": r.get("impronta_testo_sha256"),
        }
        if s and s["verifiche"]:
            v["verifiche"] = s["verifiche"]
            v["H_ms"] = s["H_ms_per_verifica"]
            v["ciclo_ms"] = round(ms / s["verifiche"], 4)
            v["token_per_ciclo"] = round(n / s["verifiche"], 4)
            v["accettazione"] = s["accettazione"]
            v["acc_per_pos_cumulativa"] = s["acc_per_pos_cumulativa"]
            if args.t1_ms is not None:
                v["R_ms"] = round(v["ciclo_ms"] - args.t1_ms - (v["H_ms"] or 0.0), 4)
        per_caso.append(v)

    tot_n = sum((r.get("predicted_n") or 0) for r in misurate)
    tot_ms = sum((r.get("predicted_ms") or 0.0) for r in misurate)
    tot_ver = sum(v.get("verifiche") or 0 for v in per_caso)
    tot_H = sum((v.get("H_ms") or 0.0) * (v.get("verifiche") or 0) for v in per_caso)
    agg = {
        "n_casi": len(misurate), "token": tot_n,
        "tempo_generazione_s": round(tot_ms / 1000.0, 3),
        "ms_per_token": round(tot_ms / tot_n, 4) if tot_n else None,
        "tps": round(tot_n / (tot_ms / 1000.0), 4) if tot_ms else None,
        "verifiche": tot_ver or None,
        "ciclo_ms": round(tot_ms / tot_ver, 4) if tot_ver else None,
        "token_per_ciclo": round(tot_n / tot_ver, 4) if tot_ver else None,
        "H_ms": round(tot_H / tot_ver, 4) if tot_ver else None,
    }
    if args.t1_ms is not None and tot_ver:
        agg["T1_ms_usato"] = args.t1_ms
        agg["R_ms"] = round(agg["ciclo_ms"] - args.t1_ms - agg["H_ms"], 4)

    ris = {
        "corsa": c.name, "cartella": str(c),
        "aggregato_131k": agg,
        "per_caso": per_caso,
        "lanci_di_grafo": log.get("graph_splits"),
        "graphs_reused_per_richiesta": log.get("graphs_reused_per_richiesta"),
        "riserve_di_grafo_fallite": log.get("riserve_fallite"),
        "occorrenze_nan_nel_log": log.get("nan_nel_log"),
        "carico": picchi(c),
    }

    if args.riferimento:
        rif = {r["etichetta"]: r["impronta_testo_sha256"]
               for r in leggi_results(Path(args.riferimento))}
        uguali, diverse, assenti = [], [], []
        for r in righe:
            e = r["etichetta"]
            if e not in rif:
                assenti.append(e)
            elif rif[e] == r["impronta_testo_sha256"]:
                uguali.append(e)
            else:
                diverse.append(e)
        ris["impronte"] = {
            "riferimento": Path(args.riferimento).name,
            "n_uguali": len(uguali), "n_diverse": len(diverse),
            "uguali": uguali, "diverse": diverse, "non_confrontabili": assenti,
            "lossless": len(diverse) == 0 and len(uguali) > 0,
        }

    print(json.dumps(ris, indent=1, ensure_ascii=False))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(ris, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
