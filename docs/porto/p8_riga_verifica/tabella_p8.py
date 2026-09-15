"""P8 - la tabella delle celle: una riga per corsa, tutte le grandezze della cella.

Legge le corse `*_P8_*` del banco, le scompone con `analizza_p8.py` (stesso modello
di costo: `ciclo = T1 + R + H`), confronta le impronte con il riferimento R1 e
stampa la tabella in markdown.

  python tabella_p8.py [--t1-ms 37.9056] [--md-out tabella.md]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
RUNS = Path(r"D:\ds4_work\banco_p0_run")

# etichetta del preset -> (ordine, nome corto, leve accese)
ORDINE = {
    "p8_r0_spento_binari_nudi":      (0, "R0 · MTP spento", "— (binari nudi)"),
    "p8_r1_mtp1_binari_nudi":        (1, "R1 · MTP bozza 1", "— (binari nudi)"),
    "p8_controllo_leve_tutte_spente": (2, "controllo", "nessuna (binario patchato)"),
    "p8_leva_a_split_inputs":        (3, "A", "A"),
    "p8_leva_ab_bias_residente":     (4, "A+B", "A+B"),
    "p8_leva_abc_getrows_stretto":   (5, "A+B+C", "A+B+C"),
    "p8_leva_abcd1_una_trasposta":   (6, "A+B+C+D1", "A+B+C+D1"),
    "p8_leve_bc_senza_a":            (7, "B+C (senza A)", "B+C"),
    "p8_consigliata_default_della_patch": (8, "consigliata", "default della patch: B+C"),
    "p8_bozza2_tutte_le_leve":       (9, "bozza 2 · A+B+C+D1", "A+B+C+D1, bozza 2"),
}


def corse():
    out = {}
    for c in sorted(p for p in RUNS.iterdir() if p.is_dir() and "_P8_" in p.name):
        et, _, rep = c.name.split("_P8_", 1)[1].rpartition("_r")
        if et in ORDINE:
            out[et + "#r" + rep] = c     # ogni replica e' una riga a se'
    return out


def analizza(cartella, t1, riferimento):
    cmd = [sys.executable, str(QUI / "analizza_p8.py"), "--corsa", str(cartella)]
    if t1 is not None:
        cmd += ["--t1-ms", "%.4f" % t1]
    if riferimento is not None:
        cmd += ["--riferimento", str(riferimento)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:])
    return json.loads(p.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t1-ms", type=float, default=None,
                    help="se assente, si prende dalla corsa R0")
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    trovate = corse()
    t1 = args.t1_ms
    r0 = next((v for k, v in trovate.items() if k.startswith("p8_r0_spento_binari_nudi")), None)
    if t1 is None and r0 is not None:
        t1 = analizza(r0, None, None)["aggregato_131k"]["ms_per_token"]
    rif = next((v for k, v in trovate.items() if k.startswith("p8_r1_mtp1_binari_nudi")), None)

    righe = []
    for et, c in sorted(trovate.items(), key=lambda kv: (ORDINE[kv[0].split("#r")[0]][0], kv[0])):
        base_et = et.split("#r")[0]
        d = analizza(c, t1, rif if base_et != "p8_r1_mtp1_binari_nudi" else None)
        a = d["aggregato_131k"]
        imp = d.get("impronte")
        righe.append({
            "etichetta": et, "corsa": c.name,
            "nome": ORDINE[base_et][1] + (" r" + et.split("#r")[1] if et.split("#r")[1] != "1" else ""),
            "leve": ORDINE[base_et][2],
            "ms_per_token": a["ms_per_token"], "tps": a["tps"],
            "ciclo_ms": a.get("ciclo_ms"), "H_ms": a.get("H_ms"), "R_ms": a.get("R_ms"),
            "token_per_ciclo": a.get("token_per_ciclo"), "verifiche": a.get("verifiche"),
            "splits_bs3": (d["lanci_di_grafo"].get("bs3") or {}).get("splits"),
            "lanci_cuda_bs3": (d["lanci_di_grafo"].get("bs3") or {}).get("lanci_cuda"),
            "splits_bs1": (d["lanci_di_grafo"].get("bs3") or {}).get("splits_bs1"),
            "impronte_uguali": None if imp is None else imp["n_uguali"],
            "impronte_diverse": None if imp is None else imp["n_diverse"],
            "lossless": None if imp is None else imp["lossless"],
            "ram_min_gb": d["carico"]["ram_disponibile_min_gb"],
            "vram_libera_min_mib": d["carico"]["vram_libera_min_mib"],
            "nan": d["occorrenze_nan_nel_log"], "riserve_fallite": d["riserve_di_grafo_fallite"],
            "per_caso": [{k: c2.get(k) for k in
                          ("etichetta", "ms_per_token", "tps", "ciclo_ms", "H_ms", "R_ms",
                           "token_per_ciclo", "acc_per_pos_cumulativa", "impronta")}
                         for c2 in d["per_caso"]],
        })

    base = next((r for r in righe if r["etichetta"].startswith("p8_r1_mtp1_binari_nudi")), None)
    r1_R = base["R_ms"] if base else None

    col = ("| cella | leve | R (ms) | ΔR vs R1 | ms/token | t/s | ciclo (ms) | H (ms) | tok/ciclo "
           "| split bs=3 → lanci CUDA | impronte = R1 | RAM min (GB) | VRAM libera min (MiB) | NaN |")
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:--:|---:|---:|---:|"
    md = [col, sep]
    for r in righe:
        dR = "—" if (r1_R is None or r["R_ms"] is None or r["etichetta"].startswith("p8_r1_mtp1_binari_nudi")) \
            else "%+.3f" % (r["R_ms"] - r1_R)
        imp = "—" if r["lossless"] is None else ("**sì** (%d/%d)" % (r["impronte_uguali"],
                                                                     r["impronte_uguali"] + r["impronte_diverse"])
                                                 if r["lossless"] else
                                                 "**NO** (%d diverse)" % r["impronte_diverse"])
        md.append("| %s | %s | %s | %s | %.3f | %.3f | %s | %s | %s | %s | %s | %.2f | %s | %d |" % (
            r["nome"], r["leve"],
            "—" if r["R_ms"] is None else "%.3f" % r["R_ms"], dR,
            r["ms_per_token"], r["tps"],
            "—" if r["ciclo_ms"] is None else "%.3f" % r["ciclo_ms"],
            "—" if r["H_ms"] is None else "%.3f" % r["H_ms"],
            "—" if r["token_per_ciclo"] is None else "%.3f" % r["token_per_ciclo"],
            "%s → %s lanci" % (r["splits_bs3"], r["lanci_cuda_bs3"]), imp,
            r["ram_min_gb"], r["vram_libera_min_mib"], r["nan"]))
    testo = "\n".join(md)
    print(testo)
    print()
    for r in righe:
        print("%-22s %s" % (r["nome"], r["corsa"]))
    if args.md_out:
        Path(args.md_out).write_text(testo + "\n", encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(righe, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
