"""P10 cella 2 - porta in `log/` gli artefatti delle corse, ripuliti dalla chiave API.

Non copia i `.nsys-rep` ne' i `.sqlite` (decine di MB): restano nella cartella della
corsa, indicata nell'esito.
"""
import json
import re
import shutil
import sys
from pathlib import Path

DEST = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\p10_token_singolo\log")
BAT = Path(r"C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat")

CORSE = [
    # (prefisso nel nome del file di destinazione, cartella della corsa)
    ("prima_V1", r"D:\ds4_work\banco_p0_run\20260915_160208_P10_p10_c2_prima_v1"),
    ("V2",       r"D:\ds4_work\banco_p0_run\20260915_162514_P10_p10_c2_v2_buchi_mtp_spento_r1"),
    ("V2r2",     r"D:\ds4_work\banco_p0_run\20260915_165455_P10_p10_c2_v2_buchi_mtp_spento_r2"),
    ("dopo_V2",  r"D:\ds4_work\banco_p0_run\20260915_163619_P10_p10_c2_dopo_v2"),
]

INTERESSANTI = ("split", "graph", "reused", "bias", "moe-cache", "sched_reserve",
                "print_timing", "n_ctx", "slot release")


def chiave():
    m = re.search(r'set "API_KEY=([^"]*)"', BAT.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def pulisci(testo, k):
    return testo.replace(k, "<REDATTA>") if k else testo


def main():
    k = chiave()
    DEST.mkdir(parents=True, exist_ok=True)
    for pref, cartella in CORSE:
        c = Path(cartella)
        if not c.exists():
            print("assente:", c)
            continue
        for nome, dst in (("riepilogo.json", "%s_riepilogo.json" % pref),
                          ("results.jsonl", "%s_results.jsonl" % pref),
                          ("log/client.log", "%s_client.log" % pref),
                          ("log/args.redacted.txt", "%s_args.redacted.txt" % pref),
                          ("log/env_sovrascritte.json", "%s_env_sovrascritte.json" % pref),
                          ("chiusura.json", "%s_chiusura.json" % pref),
                          ("riepilogo.txt", "%s_riepilogo.txt" % pref)):
            src = c / nome
            if not src.exists():
                continue
            if src.suffix in (".json", ".jsonl", ".log", ".txt"):
                (DEST / dst).write_text(pulisci(src.read_text(encoding="utf-8", errors="replace"), k),
                                        encoding="utf-8")
            else:
                shutil.copy2(src, DEST / dst)
            print("  ", dst)
        # estratto del log del server: solo le righe che dicono qualcosa su grafo e split
        for cand in ("log/server.log",):
            src = c / cand
            if not src.exists():
                continue
            righe = []
            for i, riga in enumerate(src.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if any(t in riga for t in INTERESSANTI):
                    righe.append("%d:%s" % (i, pulisci(riga, k)))
            (DEST / ("%s_server_estratto.txt" % pref)).write_text("\n".join(righe) + "\n", encoding="utf-8")
            print("   %s_server_estratto.txt (%d righe)" % (pref, len(righe)))
        # carico: minimi di RAM e VRAM
        car = c / "carico.jsonl"
        if car.exists():
            dati = [json.loads(x) for x in car.read_text(encoding="utf-8").splitlines() if x.strip()]
            ram = [d["ram_disponibile_gb"] for d in dati if d.get("ram_disponibile_gb") is not None]
            vram = [d["vram_totale_mib"] - d["vram_usata_mib"] for d in dati
                    if d.get("vram_usata_mib") is not None]
            (DEST / ("%s_carico_minimi.json" % pref)).write_text(json.dumps({
                "campioni": len(dati),
                "ram_disponibile_gb_min": min(ram) if ram else None,
                "vram_libera_mib_min": min(vram) if vram else None,
            }, indent=1), encoding="utf-8")
            print("   %s_carico_minimi.json" % pref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
