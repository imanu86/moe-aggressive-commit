"""Tiene acceso un llama-server ISOLATO per la rotta locale del gateway e lo annuncia in locale.json.

  python servizio_locale.py --run [--braccio x4] [--instrada tutti|subagent]

Finche' gira, `%USERPROFILE%\\.claude\\qwen-gateway\\locale.json` dice al gateway dove mandare Haiku.
Si ferma creando il file `ferma_locale` nella stessa cartella (o se il server muore); all'uscita
toglie locale.json, e il gateway torna da solo al vero Haiku. Da lanciare staccato dalla shell di Claude.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rotta_locale  # noqa: E402
import server_locale  # noqa: E402

OUT = Path(r"D:\ds4_work\qwen_gateway_run")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--braccio", default="x4", choices=sorted(server_locale.B.BRACCI))
    ap.add_argument("--instrada", default="tutti", choices=("tutti", "subagent"))
    args = ap.parse_args()
    if not args.run:
        print(__doc__)
        return 0
    run = OUT / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_servizio_" + args.braccio)
    run.mkdir(parents=True)
    flog = (run / "runner.log").open("w", encoding="utf-8")

    def log(msg: str) -> None:
        flog.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        flog.flush()

    cartella = rotta_locale.LOCALE.parent
    ferma = cartella / "ferma_locale"
    ferma.unlink(missing_ok=True)
    try:
        (run / "STATO.txt").write_text("avvio del server\n", encoding="utf-8")
        with server_locale.server(args.braccio, run, log) as (base, chiave):
            rotta_locale.LOCALE.write_text(json.dumps({"base": base, "chiave": chiave, "instrada": args.instrada}), encoding="utf-8")
            (run / "STATO.txt").write_text("PRONTO\n", encoding="utf-8")
            log(f"rotta locale annunciata: {base} instrada={args.instrada}")
            import socket
            persi = 0
            while not ferma.exists() and persi < 3:
                time.sleep(2)
                with socket.socket() as s:
                    s.settimeout(1)
                    persi = persi + 1 if s.connect_ex((server_locale.HOST, server_locale.PORT)) else 0
            log("richiesta di fermata" if ferma.exists() else "il server non risponde piu'")
    except BaseException as exc:
        log(f"ERRORE {type(exc).__name__}: {exc}")
        return 1
    finally:
        rotta_locale.LOCALE.unlink(missing_ok=True)
        ferma.unlink(missing_ok=True)
        (run / "STATO.txt").write_text("FINE\n", encoding="utf-8")
        flog.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
