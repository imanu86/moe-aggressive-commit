"""P9 - scompone una cattura nsys del decode in categorie, per FORWARD.

Il confine fra un forward e il successivo si trova da un kernel PERIODICO (di default
`moe_grouped_plan_decode`, uno per strato MoE): i suoi tempi di partenza si raggruppano
per distanza, ogni gruppo e' un forward. La finestra di analisi va dal primo evento del
forward 2 al primo evento dell'ultimo forward completo, cosi' contiene un numero INTERO
di periodi: la parete per forward e' (t1-t0)/n e le somme dei kernel sono confrontabili.

I nomi demangled portano il parametro di template `GGML_TYPE_*`: e' cosi' che si separa
il matvec degli ESPERTI (iq2_s / iq3_s / iq4_nl) da quello DENSO (q6_k / q8_0).

Uso:
    python analizza_nsys_p9.py cattura.sqlite --md-out log/x.md --json-out log/x.json
"""
import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

TIPI_ESPERTI = ("IQ2_S", "IQ3_S", "IQ4_NL", "IQ2_XXS", "IQ3_XXS")
TIPI_DENSI = ("Q6_K", "Q8_0", "Q4_K", "Q5_K", "Q4_0", "Q2_K")


# numeri di `enum ggml_type` che compaiono nel nome demangled come `(ggml_type)N`
NUMERI_GGML = {0: "F32", 1: "F16", 8: "Q8_0", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K",
               20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 30: "BF16"}


def tipo_ggml(demangled):
    d = demangled or ""
    m = re.search(r"GGML_TYPE_([A-Z0-9_]+)", d)
    if m:
        return m.group(1)
    m = re.search(r"\(ggml_type\)(\d+)", d)
    if m:
        return NUMERI_GGML.get(int(m.group(1)), "tipo%s" % m.group(1))
    m = re.match(r"void mul_mat_vec_f<(__nv_bfloat16|float|half|__half)", d)
    if m:
        return {"__nv_bfloat16": "BF16", "float": "F32", "half": "F16", "__half": "F16"}[m.group(1)]
    m = re.match(r"void mul_mat_f<(__nv_bfloat16|float|half|__half)", d)
    if m:
        return {"__nv_bfloat16": "BF16", "float": "F32", "half": "F16", "__half": "F16"}[m.group(1)]
    return None


def categoria(short, demangled):
    t = tipo_ggml(demangled)
    s = short or ""
    if "mul_mat_vec_q" in s or "mul_mat_vec_q" in (demangled or ""):
        if t in TIPI_ESPERTI:
            return "1. matvec ESPERTI (mmvq %s)" % (t.lower() if t else "?")
        return "2. matvec DENSI quantizzati (mmvq %s)" % (t.lower() if t else "?")
    if "quantize_q8_1" in s:
        return "3. quantizzazione dell'attivazione (quantize_q8_1)"
    if "mul_mat_f" in s:
        return "4b. punteggio QSA sui blocchi (mul_mat_f f32)"
    if "mul_mat_vec_f" in s or "mul_mat" in s:
        return "4. matvec DENSI in virgola mobile (router f32, inject, ssm, indicizzatore bf16)"
    if "gather_decode" in s:
        return "5. trasporto esperti dal PCIe (moe_grouped_gather_decode)"
    if "plan_decode" in s or "topk_moe" in s or "weighted_reduction" in s:
        return "6. instradamento MoE (plan, top-k, riduzione)"
    if "get_rows" in s:
        return "7. indicizzatore QSA: gather delle celle (k_get_rows)"
    if "RadixSort" in s or "Histogram" in s or "argsort" in s or "Onesweep" in s or "sort" in s.lower():
        return "8. indicizzatore QSA: ordinamento (radix sort)"
    if "flash_attn" in s or "fattn" in s:
        return "9. attenzione (flash_attn)"
    if "gated_delta_net" in s or "ssm" in s:
        return "10. GDN / SSM"
    if "rms_norm" in s or "l2_norm" in s or "norm" in s:
        return "11. norme"
    if any(k in s for k in ("bin_bcast", "scale_f32", "unary", "concat", "cpy", "rope",
                            "add", "mul_f32", "silu", "sigmoid", "set_rows", "dup")):
        return "12. elementari (add/mul/scale/unary/rope/copie)"
    return "13. altro"


def unione(intervalli):
    """Somma della lunghezza dell'unione di intervalli (GPU occupata)."""
    if not intervalli:
        return 0
    intervalli.sort()
    tot = 0
    a, b = intervalli[0]
    for x, y in intervalli[1:]:
        if x > b:
            tot += b - a
            a, b = x, y
        else:
            b = max(b, y)
    tot += b - a
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sqlite")
    ap.add_argument("--marcatore", default="plan_decode",
                    help="sottostringa del kernel periodico che segna i forward")
    ap.add_argument("--per-forward", type=int, default=48,
                    help="quante volte il marcatore compare in un forward")
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    c = sqlite3.connect(args.sqlite)
    ker = list(c.execute(
        "select k.start, k.end, sd.value, ss.value, k.gridX, k.gridY, k.gridZ, k.blockX, k.blockY "
        "from CUPTI_ACTIVITY_KIND_KERNEL k "
        "join StringIds sd on sd.id = k.demangledName "
        "join StringIds ss on ss.id = k.shortName order by k.start"))
    if not ker:
        raise SystemExit("nessun kernel nella cattura: la finestra e' caduta fuori dal decode")
    try:
        mem = list(c.execute(
            "select start, end, bytes, copyKind from CUPTI_ACTIVITY_KIND_MEMCPY order by start"))
    except sqlite3.OperationalError:
        mem = []

    # ------------------------------------------------ confini dei forward
    marc = [k[0] for k in ker if args.marcatore in (k[3] or "") or args.marcatore in (k[2] or "")]
    if len(marc) < 2 * args.per_forward:
        raise SystemExit("marcatore '%s' trovato %d volte: troppo poche" % (args.marcatore, len(marc)))
    # Il marcatore compare esattamente `per_forward` volte per forward e sempre nello
    # stesso ordine, quindi marc[i] e marc[i+per_forward] sono LO STESSO punto di due
    # forward consecutivi: l'intervallo fra loro e' un periodo intero qualunque sia la
    # fase. Non serve raggruppare per distanza (fragile: i buchi dentro un forward
    # possono essere piu' grandi di quelli fra forward).
    pf = args.per_forward
    if len(marc) < 3 * pf:
        raise SystemExit("solo %d marcatori: meno di tre forward nella finestra" % len(marc))
    n_fw = (len(marc) - 2 * pf) // pf
    if n_fw < 1:
        raise SystemExit("meno di un forward intero nella finestra")
    t0 = marc[pf]                       # si scarta il primo forward (bordo)
    t1 = marc[pf + n_fw * pf]
    periodi = [(marc[k + pf] - marc[k]) / 1e6 for k in range(pf, pf + n_fw * pf, pf)]
    taglie = [round(min(periodi), 3), round(max(periodi), 3)]
    parete_ms = (t1 - t0) / 1e6 / n_fw

    dentro = [k for k in ker if t0 <= k[0] < t1]
    memd = [m for m in mem if t0 <= m[0] < t1]

    # ------------------------------------------------ per kernel e per categoria
    per_k = defaultdict(lambda: {"n": 0, "ns": 0, "grid": 0, "blocco": None, "tipo": None})
    per_c = defaultdict(lambda: {"n": 0, "ns": 0})
    for st, en, dem, sh, gx, gy, gz, bx, by in dentro:
        nome = sh or dem
        t = tipo_ggml(dem)
        chiave = nome if not t else "%s<%s>" % (nome, t.lower())
        d = per_k[chiave]
        d["n"] += 1
        d["ns"] += en - st
        d["grid"] += (gx or 1) * (gy or 1) * (gz or 1)
        d["blocco"] = "%dx%d" % (bx or 0, by or 0)
        d["tipo"] = t
        cat = categoria(sh, dem)
        per_c[cat]["n"] += 1
        per_c[cat]["ns"] += en - st

    # ------------------------------------------------ controllo di integrita'
    # La geometria del modello fissa quante volte certi kernel devono comparire in un
    # forward: 48 strati MoE, 36 strati GDN, 12 strati di attenzione piena. Se nella
    # finestra non escono ESATTAMENTE quei numeri, il profilatore ha perso eventi e la
    # cattura non si puo' usare.
    ATTESI = {"moe_grouped_plan_decode": 48, "topk_moe_cuda": 48,
              "moe_weighted_reduction_f32": 48, "gated_delta_net_cuda": 36,
              "ssm_conv_f32": 36, "flash_attn_ext_f16": 12}
    conta = defaultdict(int)
    for st, en, dem, sh, gx, gy, gz, bx, by in dentro:
        conta[sh] += 1
    coerenza = {}
    valida = True
    for nome, atteso in ATTESI.items():
        visto = conta.get(nome, 0) / n_fw
        ok = abs(visto - atteso) < 0.02
        valida = valida and ok
        coerenza[nome] = {"atteso_per_forward": atteso, "visto_per_forward": round(visto, 3), "ok": ok}

    occupata_ms = unione([(k[0], k[1]) for k in dentro]) / 1e6 / n_fw
    somma_ms = sum(v["ns"] for v in per_k.values()) / 1e6 / n_fw
    inattiva_ms = parete_ms - occupata_ms

    h2d = [m for m in memd if m[3] == 1]
    d2h = [m for m in memd if m[3] == 2]
    ist = defaultdict(int)
    for m in h2d:
        ist[m[2]] += 1

    out = {
        "file": args.sqlite,
        "n_forward_completi_nella_finestra": n_fw,
        "periodo_min_max_ms": taglie,
        "integrita": {"valida": valida, "conteggi": coerenza},
        "finestra_ms": round((t1 - t0) / 1e6, 3),
        "per_forward_ms": {
            "parete": round(parete_ms, 3),
            "gpu_occupata_unione_kernel": round(occupata_ms, 3),
            "gpu_inattiva": round(inattiva_ms, 3),
            "somma_durate_kernel": round(somma_ms, 3),
            "sovrapposizione_fra_kernel": round(somma_ms - occupata_ms, 3),
        },
        "copie": {
            "h2d_n_per_forward": round(len(h2d) / n_fw, 2),
            "h2d_mib_per_forward": round(sum(m[2] for m in h2d) / n_fw / (1 << 20), 3),
            "h2d_ms_per_forward": round(sum(m[1] - m[0] for m in h2d) / 1e6 / n_fw, 3),
            "d2h_n_per_forward": round(len(d2h) / n_fw, 2),
            "d2h_mib_per_forward": round(sum(m[2] for m in d2h) / n_fw / (1 << 20), 4),
            "d2h_ms_per_forward": round(sum(m[1] - m[0] for m in d2h) / 1e6 / n_fw, 3),
            "istogramma_h2d_byte": {str(k): round(v / n_fw, 2)
                                    for k, v in sorted(ist.items(), key=lambda x: -x[0])[:12]},
        },
        "categorie": [
            {"categoria": k, "ms_per_forward": round(v["ns"] / 1e6 / n_fw, 3),
             "lanci_per_forward": round(v["n"] / n_fw, 1),
             "quota_pct": round(100.0 * v["ns"] / 1e6 / n_fw / parete_ms, 2)}
            for k, v in sorted(per_c.items(), key=lambda x: -x[1]["ns"])],
        "kernel": [
            {"kernel": k, "ms_per_forward": round(v["ns"] / 1e6 / n_fw, 3),
             "lanci_per_forward": round(v["n"] / n_fw, 1),
             "us_per_lancio": round(v["ns"] / 1e3 / max(v["n"], 1), 2),
             "blocchi_medi_per_lancio": round(v["grid"] / max(v["n"], 1), 1),
             "filo_blocco": v["blocco"]}
            for k, v in sorted(per_k.items(), key=lambda x: -x[1]["ns"])],
    }

    righe = []
    righe.append("# Cattura %s" % Path(args.sqlite).name)
    righe.append("")
    righe.append("Controllo di integrita': **%s**. Conteggi per forward attesi dalla geometria "
                 "(48 strati MoE, 36 GDN, 12 attenzione) contro visti: %s" % (
                     "PASSATO" if valida else "FALLITO — il profilatore ha perso eventi",
                     ", ".join("%s %s/%s" % (k, v["visto_per_forward"], v["atteso_per_forward"])
                               for k, v in coerenza.items())))
    righe.append("")
    righe.append("%d forward interi nella finestra (%s ms). Per forward: parete **%.3f ms**, "
                 "GPU occupata %.3f, inattiva %.3f, somma delle durate %.3f "
                 "(sovrapposizione fra kernel %.3f)." % (
                     n_fw, out["finestra_ms"], parete_ms, occupata_ms, inattiva_ms, somma_ms,
                     somma_ms - occupata_ms))
    righe.append("")
    righe.append("| categoria | ms/forward | quota | lanci/forward |")
    righe.append("|---|---:|---:|---:|")
    for r in out["categorie"]:
        righe.append("| %s | %.3f | %.1f%% | %.1f |" % (
            r["categoria"], r["ms_per_forward"], r["quota_pct"], r["lanci_per_forward"]))
    righe.append("| **GPU inattiva** | %.3f | %.1f%% | — |" % (
        inattiva_ms, 100.0 * inattiva_ms / parete_ms))
    righe.append("| **copie H2D (%.1f copie, %.2f MiB)** | %.3f | %.1f%% | — |" % (
        out["copie"]["h2d_n_per_forward"], out["copie"]["h2d_mib_per_forward"],
        out["copie"]["h2d_ms_per_forward"],
        100.0 * out["copie"]["h2d_ms_per_forward"] / parete_ms))
    righe.append("")
    righe.append("| kernel | ms/forward | lanci | us/lancio | blocchi/lancio | filo/blocco |")
    righe.append("|---|---:|---:|---:|---:|---|")
    for r in out["kernel"]:
        righe.append("| `%s` | %.3f | %.1f | %.2f | %.1f | %s |" % (
            r["kernel"], r["ms_per_forward"], r["lanci_per_forward"], r["us_per_lancio"],
            r["blocchi_medi_per_lancio"], r["filo_blocco"]))
    testo = "\n".join(righe) + "\n"

    if args.md_out:
        Path(args.md_out).write_text(testo, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(testo)


if __name__ == "__main__":
    main()
