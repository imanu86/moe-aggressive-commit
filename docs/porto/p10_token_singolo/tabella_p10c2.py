"""P10 cella 2 - tabella di confronto fra due corse del banco P0 (V1 contro V2).

Legge le cartelle di corsa e produce: ms/token e t/s per caso e aggregati, impronte
(e se coincidono), RAM/VRAM minime, prefill.

Uso:
    python tabella_p10c2.py --a <cartella V1> --b <cartella V2> --md-out ... --json-out ...
"""
import argparse
import json
from pathlib import Path


def leggi(cartella):
    c = Path(cartella)
    ries = json.loads((c / "riepilogo.json").read_text(encoding="utf-8"))
    res = [json.loads(l) for l in (c / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    carico = [json.loads(l) for l in (c / "carico.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ram = [x["ram_disponibile_gb"] for x in carico if x.get("ram_disponibile_gb") is not None]
    vram = [x["vram_totale_mib"] - x["vram_usata_mib"] for x in carico
            if x.get("vram_usata_mib") is not None and x.get("vram_totale_mib") is not None]
    return {
        "cartella": c.name,
        "preset": ries.get("preset"),
        "aggregato_tps": ries["insieme_libero"]["tps_insieme"],
        "aggregato_token": ries["insieme_libero"]["token_accettati"],
        "aggregato_s": ries["insieme_libero"]["tempo_generazione_s"],
        "aggregato_ms_token": 1000.0 * ries["insieme_libero"]["tempo_generazione_s"]
                              / ries["insieme_libero"]["token_accettati"],
        "impronte": ries["impronte"],
        "guasto": ries.get("guasto"),
        "casi": {r["etichetta"]: {
            "ms_token": r["timings_server"]["predicted_per_token_ms"],
            "tps": r["timings_server"]["predicted_per_second"],
            "prompt_n": r.get("prompt_n"),
            "prompt_tps": r.get("prompt_tps_server"),
            "impronta": r["impronta_testo_sha256"][:16],
        } for r in res},
        "ram_disponibile_gb_min": min(ram) if ram else None,
        "vram_libera_mib_min": min(vram) if vram else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="cartella della corsa di riferimento (V1)")
    ap.add_argument("--b", required=True, help="cartella della corsa candidata (V2)")
    ap.add_argument("--nome-a", default="V1")
    ap.add_argument("--nome-b", default="V2")
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    A, B = leggi(args.a), leggi(args.b)
    na, nb = args.nome_a, args.nome_b
    casi = [k for k in A["casi"] if not k.startswith("riscaldamento")]
    uguali = sum(1 for k, v in A["impronte"].items() if B["impronte"].get(k) == v)

    out = {na: A, nb: B,
           "impronte_identiche": "%d/%d" % (uguali, len(A["impronte"])),
           "delta_ms_token_aggregato": B["aggregato_ms_token"] - A["aggregato_ms_token"],
           "delta_tps_aggregato": B["aggregato_tps"] - A["aggregato_tps"]}

    r = []
    r.append("| caso | %s ms/tok | %s t/s | %s ms/tok | %s t/s | delta ms | delta t/s | delta %% |" % (na, na, nb, nb))
    r.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for k in casi:
        a, b = A["casi"][k], B["casi"][k]
        r.append("| %s | %.3f | %.3f | %.3f | %.3f | **%+.3f** | %+.3f | %+.2f%% |" % (
            k, a["ms_token"], a["tps"], b["ms_token"], b["tps"],
            b["ms_token"] - a["ms_token"], b["tps"] - a["tps"],
            100.0 * (b["tps"] - a["tps"]) / a["tps"]))
    r.append("| **aggregato (%d tok)** | **%.3f** | **%.3f** | **%.3f** | **%.3f** | **%+.3f** | **%+.3f** | **%+.2f%%** |" % (
        A["aggregato_token"], A["aggregato_ms_token"], A["aggregato_tps"],
        B["aggregato_ms_token"], B["aggregato_tps"],
        B["aggregato_ms_token"] - A["aggregato_ms_token"],
        B["aggregato_tps"] - A["aggregato_tps"],
        100.0 * (B["aggregato_tps"] - A["aggregato_tps"]) / A["aggregato_tps"]))
    r.append("")
    r.append("| caso | impronta %s | impronta %s | identica |" % (na, nb))
    r.append("|---|---|---|:--:|")
    for k, v in A["impronte"].items():
        r.append("| %s | `%s` | `%s` | %s |" % (k, v, B["impronte"].get(k, "-"),
                                                "si" if B["impronte"].get(k) == v else "**NO**"))
    r.append("")
    r.append("| | %s | %s |" % (na, nb))
    r.append("|---|---:|---:|")
    for k in casi:
        r.append("| prefill %s (t/s) | %.2f | %.2f |" % (k, A["casi"][k]["prompt_tps"], B["casi"][k]["prompt_tps"]))
    r.append("| VRAM libera minima (MiB) | %.0f | %.0f |" % (A["vram_libera_mib_min"], B["vram_libera_mib_min"]))
    r.append("| RAM disponibile minima (GB) | %.2f | %.2f |" % (A["ram_disponibile_gb_min"], B["ram_disponibile_gb_min"]))
    r.append("| guasto | %s | %s |" % (A["guasto"], B["guasto"]))
    testo = "\n".join(r) + "\n"

    if args.md_out:
        Path(args.md_out).write_text(testo, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(testo)
    print("impronte identiche: %s" % out["impronte_identiche"])


if __name__ == "__main__":
    main()
