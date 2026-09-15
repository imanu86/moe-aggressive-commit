"""P11 - estrae da una corsa del banco le grandezze della cella.

prefill t/s INTEGRALE = prompt_n / prompt_ms, cioe' tutto il prompt, non il picco
dei primi blocchi. VRAM/RAM minime dalla sonda, limitate alla finestra della
richiesta di prefill. Workspace CUDA dal log del server.

Uso:  python tabella_p11.py <cartella_corsa> [<cartella_corsa> ...]
"""
import json
import re
import sys
from pathlib import Path


def leggi_corsa(d):
    d = Path(d)
    ris = [json.loads(r) for r in (d / "results.jsonl").read_text(encoding="utf-8").splitlines() if r.strip()]
    utili = [r for r in ris if not r.get("riscaldamento")]

    carico = []
    p = d / "carico.jsonl"
    if p.exists():
        for riga in p.read_text(encoding="utf-8").splitlines():
            if riga.strip():
                try:
                    carico.append(json.loads(riga))
                except Exception:
                    pass

    def finestra(etichetta):
        return [c for c in carico if c.get("etichetta") == etichetta]

    def finestra_prefill(r):
        """Solo i campioni dentro il prefill: dall'inizio della richiesta al primo delta.
        Dopo il primo token la cache degli esperti torna sul device e la VRAM libera
        crolla: quel minimo e' del decode, non del prefill, e va tenuto separato."""
        from datetime import datetime as _dt
        try:
            t0 = _dt.fromisoformat(r["inizio_iso"]).timestamp()
        except Exception:
            return []
        t1 = t0 + (r.get("ttft_primo_delta_s") or 0)
        return [c for c in finestra(r["etichetta"]) if t0 <= c.get("t", 0) <= t1]

    ws_max = None
    log = d / "log" / "server.log"
    if log.exists():
        val = [float(m) for m in re.findall(
            r"CUDA0 compute buffer size\s*=\s*([0-9.]+) MiB",
            log.read_text(encoding="utf-8", errors="replace"))]
        ws_max = max(val) if val else None

    righe = []
    for r in utili:
        c = finestra(r["etichetta"])
        cp = finestra_prefill(r) or c

        def libera(campioni):
            return [x["vram_totale_mib"] - x["vram_usata_mib"] for x in campioni
                    if x.get("vram_totale_mib") and x.get("vram_usata_mib") is not None]
        vram_lib = libera(cp)
        vram_lib_tutta = libera(c)
        ram = [x["ram_disponibile_gb"] for x in c if x.get("ram_disponibile_gb") is not None]
        pn, pms = r.get("prompt_n") or 0, r.get("prompt_ms") or 0
        righe.append({
            "caso": r["etichetta"],
            "prompt_n": pn, "cache_n": r.get("cache_n"),
            "prefill_tps": round(pn / (pms / 1000.0), 3) if pms else None,
            "prefill_s": round(pms / 1000.0, 2),
            "predicted_n": r.get("predicted_n"),
            "decode_tps": r.get("gen_tps_server"),
            "wall_s": r.get("wall_http_s"),
            "vram_libera_min_mib": round(min(vram_lib), 1) if vram_lib else None,
            "vram_libera_min_mib_tutta_la_richiesta": round(min(vram_lib_tutta), 1) if vram_lib_tutta else None,
            "campioni_prefill": len(cp),
            "ram_libera_min_gb": round(min(ram), 2) if ram else None,
            "campioni": len(c),
            "impronta": r["impronta_testo_sha256"][:12],
            "fine": r.get("motivo_fine"),
        })
    return {"corsa": d.name, "workspace_cuda_max_mib": ws_max, "casi": righe}


def main():
    for d in sys.argv[1:]:
        r = leggi_corsa(d)
        print("== %s   workspace CUDA max %s MiB" % (r["corsa"], r["workspace_cuda_max_mib"]))
        for c in r["casi"]:
            print("   %-16s prompt_n %-7s cache_n %-6s prefill %8s t/s (%7ss)  pred %-5s dec %-8s "
                  "VRAM min pref %-8s (richiesta %-8s) RAM min %-6s sha %s  %s" % (
                      c["caso"], c["prompt_n"], c["cache_n"], c["prefill_tps"], c["prefill_s"],
                      c["predicted_n"],
                      round(c["decode_tps"], 3) if c["decode_tps"] else None,
                      c["vram_libera_min_mib"], c["vram_libera_min_mib_tutta_la_richiesta"],
                      c["ram_libera_min_gb"], c["impronta"], c["fine"]))


if __name__ == "__main__":
    main()
