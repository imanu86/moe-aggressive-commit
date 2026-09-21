"""Banco del decode: quanti token al secondo genera il server a tre profondita' di contesto.

  python banco_decode.py --produzione              misura il server gia' acceso sulla 8100 (chiave letta dal
                                                   lanciatore sul Desktop, mai stampata)
  python banco_decode.py --run --braccio x4        avvia un server isolato (127.0.0.1:8113) e lo misura
  ... --env NOME=VALORE (ripetibile) --slot 64     leve del braccio B: env in piu' e numero di slot
  ... --profondita 100000 --genera 2048 --flusso   una sola profondita', generazione lunga, tempi per finestra

Per ogni profondita' (~1k, ~50k, ~100k token) manda in chat lo stesso documento troncato a N token e fa generare
512 token, greedy. I prompt crescono sullo stesso prefisso, quindi il prefill si riusa da una profondita' alla
successiva. Legge `timings` dalla risposta: decode t/s (predicted_per_second) e prefill. Con --flusso la risposta
arriva in streaming e si misura anche il ritmo per finestre di 128 pezzi (la cache esperti si scalda: l'inizio
e' piu' lento del regime). Da lanciare staccato.
"""
from __future__ import annotations
import argparse
import gzip
import json
import struct
import subprocess
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
FINESTRA = 128


def misura(base: str, chiave: str, log, esiti: list, profondita: list, genera: int, flusso: bool) -> None:
    intestazioni = {"Content-Type": "application/json", "Authorization": "Bearer " + chiave}

    def post(percorso: str, corpo: dict, timeout: float = 3600) -> dict:
        req = urllib.request.Request(base + percorso, data=json.dumps(corpo).encode("utf-8"), method="POST", headers=intestazioni)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def post_flusso(percorso: str, corpo: dict, timeout: float = 3600) -> tuple[dict, list]:
        req = urllib.request.Request(base + percorso, data=json.dumps(corpo).encode("utf-8"), method="POST", headers=intestazioni)
        arrivi, ultimo = [], {}
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for riga in r:
                riga = riga.strip()
                if not riga.startswith(b"data: ") or riga == b"data: [DONE]":
                    continue
                pezzo = json.loads(riga[6:])
                delta = (pezzo.get("choices") or [{}])[0].get("delta", {})
                if delta.get("content") or delta.get("reasoning_content"):
                    arrivi.append(time.perf_counter())
                if "timings" in pezzo:
                    ultimo = pezzo
        return ultimo, arrivi

    packed = gzip.decompress(server_locale.B.IDS.read_bytes())
    ids = list(struct.unpack("<" + "i" * (len(packed) // 4), packed))
    for n in profondita:
        testo = post("/detokenize", {"tokens": ids[:n]})["content"]
        messaggi = [{"role": "user", "content": "Leggi il documento e poi descrivine in dettaglio la struttura, in italiano, "
                                                  "con un elenco lungo e ragionato.\n<documento>\n" + testo}]
        corpo = {"messages": messaggi, "max_tokens": genera, "temperature": 0.0, "seed": 1234,
                 "stream": flusso, "cache_prompt": True}
        t0 = time.perf_counter()
        arrivi: list = []
        if flusso:
            corpo["timings_per_token"] = True
            r, arrivi = post_flusso("/v1/chat/completions", corpo)
        else:
            r = post("/v1/chat/completions", corpo)
        tm = r.get("timings", {})
        riga = {"profondita": n, "prompt_valutati": tm.get("prompt_n"), "in_cache": tm.get("cache_n"),
                "prefill_tps": round(tm.get("prompt_per_second", 0), 1), "generati": tm.get("predicted_n"),
                "decode_tps": round(tm.get("predicted_per_second", 0), 2), "muro_s": round(time.perf_counter() - t0, 1)}
        if len(arrivi) > FINESTRA:
            riga["pezzi"] = len(arrivi)
            riga["tps_per_finestra"] = [round(FINESTRA / (arrivi[k + FINESTRA] - arrivi[k]), 2)
                                        for k in range(0, len(arrivi) - FINESTRA, FINESTRA)]
        esiti.append(riga)
        log(json.dumps(riga))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--produzione", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--braccio", default="x4", choices=sorted(server_locale.B.BRACCI))
    ap.add_argument("--env", action="append", default=[], metavar="NOME=VALORE", help="env in piu' per il server (ripetibile)")
    ap.add_argument("--slot", default=None, help="numero di slot al posto di quello del braccio")
    ap.add_argument("--profondita", default=None, help="profondita' separate da virgola (predefinito 1000,50000,100000)")
    ap.add_argument("--genera", type=int, default=GENERA)
    ap.add_argument("--flusso", action="store_true", help="streaming: misura anche il ritmo per finestre di 128 pezzi")
    ap.add_argument("--carico-cpu", type=int, default=0, metavar="N",
                    help="N processi che tengono occupata la CPU durante la misura (uso reale: agente e programmi aperti)")
    ap.add_argument("--etichetta", default="")
    args = ap.parse_args()
    if not (args.produzione or args.run):
        print(__doc__)
        return 0
    leve = dict(v.split("=", 1) for v in args.env)
    profondita = [int(x) for x in args.profondita.split(",")] if args.profondita else PROFONDITA
    etichetta = ("produzione" if args.produzione else args.braccio) + ("_" + args.etichetta if args.etichetta else "")
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
        log(f"leve {leve} slot {args.slot} profondita {profondita} genera {args.genera} flusso {args.flusso}")
        if args.produzione:
            chiave = rotta_locale._chiave_produzione()
            assert chiave, "chiave di produzione non trovata nei lanciatori"
            misura(rotta_locale.PRODUZIONE, chiave, log, esiti, profondita, args.genera, args.flusso)
        else:
            with server_locale.server(args.braccio, run, log, leve, args.slot) as (base, chiave):
                # il carico parte a server pronto: il caricamento del modello non fa parte della misura
                carico = [subprocess.Popen([sys.executable, "-c", "while True: pass"], creationflags=subprocess.CREATE_NO_WINDOW)
                          for _ in range(args.carico_cpu)]
                try:
                    if carico:
                        log(f"carico CPU: {len(carico)} processi occupati")
                    misura(base, chiave, log, esiti, profondita, args.genera, args.flusso)
                finally:
                    for p in carico:
                        p.kill()
    except BaseException as exc:
        errore = f"{type(exc).__name__}: {exc}"
        log("ERRORE " + errore)
    finally:
        (run / "esiti.json").write_text(json.dumps({"braccio": etichetta, "leve": leve, "slot": args.slot, "genera": args.genera,
                                                    "esiti": esiti, "errore": errore}, indent=1), encoding="utf-8")
        (run / "STATO.txt").write_text(("FINE errore: " + errore) if errore else "FINE ok\n", encoding="utf-8")
        flog.close()
    return 1 if errore else 0


if __name__ == "__main__":
    sys.exit(main())
