"""Banco del decode: quanti token al secondo genera il server a tre profondita' di contesto.

  python banco_decode.py --produzione              misura il server gia' acceso sulla 8100 (chiave letta dal
                                                   lanciatore sul Desktop, mai stampata)
  python banco_decode.py --run --braccio x4        avvia un server isolato (127.0.0.1:8113) e lo misura

Per ogni profondita' (~1k, ~50k, ~100k token) manda in chat lo stesso documento troncato a N token e fa generare
512 token, greedy. I prompt crescono sullo stesso prefisso, quindi il prefill si riusa da una profondita' alla
successiva. Legge `timings` dalla risposta: decode t/s (predicted_per_second) e prefill. Da lanciare staccato.
"""
from __future__ import annotations
import argparse
import gzip
import json
import struct
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rotta_locale  # noqa: E402
import server_locale  # noqa: E402

OUT = Path(r"D:\ds4_work\qwen_gateway_run")
PROFONDITA = [1000, 50000, 100000]
GENERA = 512


def misura(base: str, chiave: str, log, esiti: list) -> None:
    def post(percorso: str, corpo: dict, timeout: float = 3600) -> dict:
        req = urllib.request.Request(base + percorso, data=json.dumps(corpo).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + chiave})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    packed = gzip.decompress(server_locale.B.IDS.read_bytes())
    ids = list(struct.unpack("<" + "i" * (len(packed) // 4), packed))
    for n in PROFONDITA:
        testo = post("/detokenize", {"tokens": ids[:n]})["content"]
        messaggi = [{"role": "user", "content": "Leggi il documento e poi descrivine in dettaglio la struttura, in italiano, "
                                                  "con un elenco lungo e ragionato.\n<documento>\n" + testo}]
        t0 = time.perf_counter()
        r = post("/v1/chat/completions", {"messages": messaggi, "max_tokens": GENERA, "temperature": 0.0, "seed": 1234,
                                          "stream": False, "cache_prompt": True})
        tm = r.get("timings", {})
        riga = {"profondita": n, "prompt_valutati": tm.get("prompt_n"), "in_cache": tm.get("cache_n"),
                "prefill_tps": round(tm.get("prompt_per_second", 0), 1), "generati": tm.get("predicted_n"),
                "decode_tps": round(tm.get("predicted_per_second", 0), 2), "muro_s": round(time.perf_counter() - t0, 1)}
        esiti.append(riga)
        log(json.dumps(riga))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--produzione", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--braccio", default="x4", choices=sorted(server_locale.B.BRACCI))
    args = ap.parse_args()
    if not (args.produzione or args.run):
        print(__doc__)
        return 0
    etichetta = "produzione" if args.produzione else args.braccio
    run = OUT / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_decode_" + etichetta)
    run.mkdir(parents=True)
    flog = (run / "runner.log").open("w", encoding="utf-8")

    def log(msg: str) -> None:
        flog.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        flog.flush()

    esiti: list = []
    errore = None
    try:
        (run / "STATO.txt").write_text("in corso\n", encoding="utf-8")
        if args.produzione:
            chiave = rotta_locale._chiave_produzione()
            assert chiave, "chiave di produzione non trovata nei lanciatori"
            misura(rotta_locale.PRODUZIONE, chiave, log, esiti)
        else:
            with server_locale.server(args.braccio, run, log) as (base, chiave):
                misura(base, chiave, log, esiti)
    except BaseException as exc:
        errore = f"{type(exc).__name__}: {exc}"
        log("ERRORE " + errore)
    finally:
        (run / "esiti.json").write_text(json.dumps({"braccio": etichetta, "esiti": esiti, "errore": errore}, indent=1), encoding="utf-8")
        (run / "STATO.txt").write_text(("FINE errore: " + errore) if errore else "FINE ok\n", encoding="utf-8")
        flog.close()
    return 1 if errore else 0


if __name__ == "__main__":
    sys.exit(main())
