"""Guardiano del gateway: lo tiene acceso e, se non ci riesce, riporta Claude Code al collegamento diretto.

Parte all'accesso a Windows (collegamento nella cartella Esecuzione automatica, con pythonw: nessuna finestra).
Ogni 5 secondi:
  - se il gateway non ascolta su 127.0.0.1:8787 lo avvia;
  - se ascolta e l'utente lo vuole (segno `voluto`, lasciato da `imposta_proxy.py --attiva`), mette le chiavi
    in settings.json;
  - se dopo due giri non ascolta ancora, TOGLIE le chiavi: Claude Code torna diretto ad Anthropic e funziona
    come prima. Le rimette da solo quando il gateway e' di nuovo su.
Un solo guardiano alla volta (il lucchetto e' la porta 8786). Registro: log_gateway\\guardiano.log.
"""
from __future__ import annotations
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import imposta_proxy as P  # noqa: E402

REGISTRO = Path(r"D:\ds4_work\qwen_gateway_run\log_gateway\guardiano.log")
PYTHONW = Path(sys.executable).with_name("pythonw.exe")


def log(msg: str) -> None:
    try:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        with REGISTRO.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def main() -> int:
    lucchetto = socket.socket()
    try:
        lucchetto.bind(("127.0.0.1", 8786))
        lucchetto.listen(1)
    except OSError:
        return 0  # un altro guardiano e' gia' al lavoro
    log("guardiano avviato")
    figlio, giu = None, 0
    while True:
        try:
            if P.gateway_vivo():
                if giu:
                    log("gateway di nuovo in ascolto")
                giu = 0
                if P.VOLUTO.exists() and P.imposta(True):
                    log("chiavi messe in settings.json: Claude Code passa dal gateway")
            else:
                giu += 1
                if figlio is None or figlio.poll() is not None:
                    exe = PYTHONW if PYTHONW.exists() else Path(sys.executable)
                    figlio = subprocess.Popen([str(exe), str(QUI / "gateway.py"), "--porta", str(P.PORTA)], cwd=str(QUI),
                                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    log(f"gateway avviato (PID {figlio.pid})")
                if giu >= 2 and P.imposta(False):
                    log("il gateway non risponde: chiavi TOLTE, Claude Code torna diretto")
        except Exception as exc:  # il guardiano non deve morire mai
            log(f"errore: {type(exc).__name__}: {exc}")
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
