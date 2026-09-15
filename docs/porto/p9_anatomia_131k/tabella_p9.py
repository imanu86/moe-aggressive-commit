"""P9 - unisce la scomposizione nsys (misura) al pavimento di byte (modello) e produce
la tabella B: byte per token, tempo minimo alla banda misurata, tempo misurato, efficienza.

Le categorie nsys vengono dal file prodotto da `analizza_nsys_p9.py`; i byte vengono
dall'intestazione del GGUF (`composizione_gguf_p9.py`) e dalla geometria della QSA.
Ogni numero della colonna "byte" e' un MODELLO dichiarato, non una misura: le regole
sono nell'esito, §B.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
VRAM = 340.3e9      # B/s misurati
PCIE = 26.3e9       # B/s misurati
ATTN = {3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47}


def byte_modello(comp, n_kv, top_k, esperti_mancanti, ratio=4, n_idx_h=4, idx_dim=128):
    T = comp["tensori"]
    q = defaultdict(int)          # byte dei pesi, per "corsia"
    esp_per_strato = defaultdict(int)
    for t in T:
        m = re.match(r"blk\.(\d+)\.(.*)", t["nome"])
        if not m:
            if t["nome"].startswith(("token_embd", "per_layer_token_embd")):
                continue          # letti per riga
            q["denso_" + ("quant" if t["tipo"] not in ("f32", "bf16", "f16") else "float")] += t["byte"]
            continue
        blk, corto = int(m.group(1)), m.group(2)
        if "_exps" in corto:
            esp_per_strato[blk] += t["byte"] // 512
            continue
        if corto.startswith(("ple_", "per_layer")):
            continue
        q["denso_" + ("quant" if t["tipo"] not in ("f32", "bf16", "f16") else "float")] += t["byte"]

    esperti_tot = sum(v * 10 for v in esp_per_strato.values())
    esperti_pcie = sum(v * esperti_mancanti for v in esp_per_strato.values())
    n_blocks = n_kv // ratio
    return {
        # mmvq legge dalla cache TUTTI e 10 gli esperti instradati: i mancanti ci sono
        # appena stati copiati dentro, quindi il traffico VRAM non si riduce coi colpi.
        "esperti_vram": esperti_tot,
        "esperti_pcie": esperti_pcie,
        "denso_quant": q["denso_quant"],
        "denso_float": q["denso_float"],
        "qsa_pool": n_blocks * idx_dim * 4 * 12,
        # gather delle celle: K+V q8_0 (2 teste x 256) + chiave dell'indicizzatore (128)
        "gather_kv": top_k * (2 * 512 * 17 // 16) * 2 * 12 + top_k * 136 * 12,
        "bias_h2d": n_kv * 4,
    }


MAPPA = [
    # (etichetta, prefissi delle categorie nsys, chiave dei byte, banda)
    ("esperti: matvec dalla cache in VRAM (iq2_s/iq3_s/iq4_nl)", ["1."], "esperti_vram", VRAM),
    ("esperti: trasporto dal PCIe (gather)", ["5."], "esperti_pcie", PCIE),
    ("densi quantizzati: matvec q6_k/q8_0 (+quantize_q8_1)", ["2.", "3."], "denso_quant", VRAM),
    ("densi in virgola mobile: router f32, inject, ssm, indicizzatore bf16", ["4."], "denso_float", VRAM),
    ("punteggio QSA sui blocchi (legge la cache dei blocchi)", ["4b"], "qsa_pool", VRAM),
    ("indicizzatore/KV: gather delle celle (host mappato)", ["7."], "gather_kv", PCIE),
    ("instradamento MoE (plan, top-k, riduzione)", ["6."], None, None),
    ("indicizzatore: ordinamento", ["8."], None, None),
    ("attenzione (flash_attn)", ["9."], None, None),
    ("GDN / SSM", ["10."], None, None),
    ("norme", ["11."], None, None),
    ("elementari (add/mul/scale/unary/rope/copie)", ["12."], None, None),
    ("altro", ["13."], None, None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nsys-json", required=True)
    ap.add_argument("--composizione", default=str(HERE / "log" / "p9_composizione.json"))
    ap.add_argument("--n-kv", type=int, default=131248)
    ap.add_argument("--top-k", type=int, default=2048)
    ap.add_argument("--esperti-mancanti", type=float, default=1.86,
                    help="ricavato INVERTENDO il tempo del gather alla banda misurata (26,3 GB/s)")
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    ns = json.loads(Path(args.nsys_json).read_text(encoding="utf-8"))
    comp = json.loads(Path(args.composizione).read_text(encoding="utf-8"))
    by = byte_modello(comp, args.n_kv, args.top_k, args.esperti_mancanti)

    misurato = {r["categoria"]: r for r in ns["categorie"]}
    parete = ns["per_forward_ms"]["parete"]

    righe = []
    usate = set()
    for etichetta, prefissi, chiave, banda in MAPPA:
        ms = 0.0
        lanci = 0.0
        for k, r in misurato.items():
            if any(k.startswith(p) for p in prefissi):
                ms += r["ms_per_forward"]
                lanci += r["lanci_per_forward"]
                usate.add(k)
        if ms == 0 and chiave is None:
            continue
        b = by.get(chiave) if chiave else None
        pav = (b / banda * 1e3) if b else None
        righe.append({"categoria": etichetta, "ms": round(ms, 3), "lanci": round(lanci, 1),
                      "mib": round(b / (1 << 20), 1) if b else None,
                      "banda_gbs": round(banda / 1e9, 1) if banda else None,
                      "pavimento_ms": round(pav, 3) if pav else None,
                      "efficienza_pct": round(100 * pav / ms, 1) if (pav and ms) else None,
                      "spreco_ms": round(ms - pav, 3) if pav else None,
                      "banda_effettiva_gbs": round(b / (ms / 1e3) / 1e9, 1) if (b and ms) else None})
    rimaste = [k for k in misurato if k not in usate]

    h2d = ns["copie"]
    righe.append({"categoria": "copie H2D esplicite (bias QSA e piccole)", "ms": h2d["h2d_ms_per_forward"],
                  "lanci": h2d["h2d_n_per_forward"], "mib": h2d["h2d_mib_per_forward"],
                  "banda_gbs": 26.3,
                  "pavimento_ms": round(h2d["h2d_mib_per_forward"] * (1 << 20) / PCIE * 1e3, 3),
                  "efficienza_pct": None, "spreco_ms": None,
                  "banda_effettiva_gbs": round(h2d["h2d_mib_per_forward"] * (1 << 20) /
                                               max(h2d["h2d_ms_per_forward"], 1e-9) * 1e3 / 1e9, 1)})

    somma_ms = sum(r["ms"] for r in righe)
    somma_pav = sum(r["pavimento_ms"] or 0 for r in righe)

    out = {"nsys": args.nsys_json, "parete_per_forward_ms": parete,
           "gpu_inattiva_ms": ns["per_forward_ms"]["gpu_inattiva"],
           "gpu_occupata_ms": ns["per_forward_ms"]["gpu_occupata_unione_kernel"],
           "somma_durate_kernel_ms": ns["per_forward_ms"]["somma_durate_kernel"],
           "byte_modello_mib": {k: round(v / (1 << 20), 2) for k, v in by.items()},
           "righe": righe, "categorie_non_mappate": rimaste,
           "somma_categorie_ms": round(somma_ms, 3), "somma_pavimenti_ms": round(somma_pav, 3)}

    r = []
    r.append("| categoria | misurato ms | lanci | MiB/token | banda usata GB/s | pavimento ms | efficienza | spreco ms |")
    r.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for x in righe:
        r.append("| %s | %.3f | %.1f | %s | %s | %s | %s | %s |" % (
            x["categoria"], x["ms"], x["lanci"],
            "%.1f" % x["mib"] if x["mib"] else "—",
            "%.1f" % x["banda_effettiva_gbs"] if x["banda_effettiva_gbs"] else "—",
            "%.3f" % x["pavimento_ms"] if x["pavimento_ms"] else "—",
            "%.0f%%" % x["efficienza_pct"] if x["efficienza_pct"] else "—",
            "%.3f" % x["spreco_ms"] if x["spreco_ms"] else "—"))
    r.append("| **somma delle durate** | **%.3f** | | | | **%.3f** | | |" % (somma_ms, somma_pav))
    r.append("| *GPU inattiva* | %.3f | | | | | | |" % ns["per_forward_ms"]["gpu_inattiva"])
    r.append("| *sovrapposizione fra kernel (da sottrarre)* | −%.3f | | | | | | |" %
             ns["per_forward_ms"]["sovrapposizione_fra_kernel"])
    r.append("| **parete per token** | **%.3f** | | | | | | |" % parete)
    testo = "\n".join(r) + "\n"
    if args.md_out:
        Path(args.md_out).write_text(testo, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(testo)
    if rimaste:
        print("categorie nsys non mappate:", rimaste)
    print("byte del modello (MiB/token):", out["byte_modello_mib"])


if __name__ == "__main__":
    main()
