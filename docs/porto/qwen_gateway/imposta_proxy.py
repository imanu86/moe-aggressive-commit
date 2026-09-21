"""Accende o spegne il passaggio di Claude Code dal gateway locale.

  python imposta_proxy.py --attiva      l'utente VUOLE il gateway: mette le tre chiavi nell'env e lascia il segno
                                        `voluto`, cosi' il guardiano lo tiene acceso e lo riaccende dopo un guasto
  python imposta_proxy.py --disattiva   l'utente NON lo vuole piu': toglie le chiavi e il segno (il guardiano non
                                        le rimette); Claude Code torna diretto ad Anthropic
  python imposta_proxy.py --stato       dice come sta

Tocca solo HTTPS_PROXY, NODE_EXTRA_CA_CERTS e NO_PROXY di %USERPROFILE%\\.claude\\settings.json; la prima volta
che scrive salva una copia `settings.json.prima_del_gateway_<data>`. L'app desktop applica la modifica a caldo.
"""
from __future__ import annotations
import json
import os
import shutil
import socket
import sys
from datetime import datetime
from pathlib import Path

SETTINGS = Path(os.environ["USERPROFILE"]) / ".claude" / "settings.json"
CARTELLA = Path(os.environ["USERPROFILE"]) / ".claude" / "qwen-gateway"
CA = CARTELLA / "ca.pem"
VOLUTO = CARTELLA / "voluto"
PORTA = 8787
CHIAVI = {"HTTPS_PROXY": f"http://127.0.0.1:{PORTA}", "NODE_EXTRA_CA_CERTS": str(CA), "NO_PROXY": "localhost,127.0.0.1"}


def gateway_vivo() -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORTA)) == 0


def attivo() -> bool:
    try:
        env = json.loads(SETTINGS.read_text(encoding="utf-8")).get("env", {})
    except (OSError, ValueError):
        return False
    return all(env.get(k) == v for k, v in CHIAVI.items() if k != "NO_PROXY")


def imposta(acceso: bool) -> bool:
    """Scrive o toglie le tre chiavi. Ritorna True se ha cambiato qualcosa. Non tocca il segno `voluto`."""
    dati = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    env = dati.get("env", {})
    nuovo = {**env, **CHIAVI} if acceso else {k: v for k, v in env.items() if k not in CHIAVI}
    if nuovo == env:
        return False
    if SETTINGS.exists() and not list(SETTINGS.parent.glob("settings.json.prima_del_gateway_*")):
        shutil.copy2(SETTINGS, SETTINGS.with_name(f"settings.json.prima_del_gateway_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))
    if nuovo:
        dati["env"] = nuovo
    else:
        dati.pop("env", None)
    provvisorio = SETTINGS.with_name("settings.json.tmp_gateway")
    provvisorio.write_text(json.dumps(dati, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(provvisorio, SETTINGS)  # scrittura atomica: l'app rilegge il file a caldo
    return True


def main() -> int:
    azione = sys.argv[1] if len(sys.argv) > 1 else "--stato"
    if azione == "--stato":
        print("passaggio dal gateway:", "ATTIVO" if attivo() else "spento", "| voluto dall'utente:", "si" if VOLUTO.exists() else "no",
              "| gateway in ascolto:", "si" if gateway_vivo() else "NO")
        return 0
    if azione == "--attiva":
        if not CA.exists():
            sys.exit(f"manca {CA}: esegui prima genera_ca.py")
        VOLUTO.write_text("1", encoding="ascii")
        if not gateway_vivo():
            print("segno lasciato; il gateway ora non ascolta: le chiavi le mettera' il guardiano appena il gateway e' su")
            return 0
        imposta(True)
        print("fatto: passaggio dal gateway ATTIVO")
    elif azione == "--disattiva":
        VOLUTO.unlink(missing_ok=True)
        imposta(False)
        print("fatto: Claude Code torna DIRETTO ad Anthropic (il guardiano non lo riaccendera')")
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
