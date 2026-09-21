"""Accende o spegne il passaggio di Claude Code dal gateway locale.

  python imposta_proxy.py --attiva      aggiunge HTTPS_PROXY, NODE_EXTRA_CA_CERTS, NO_PROXY all'env
  python imposta_proxy.py --disattiva   le toglie (= Claude Code torna diretto ad Anthropic)
  python imposta_proxy.py --stato       dice come sta

Tocca solo quelle tre chiavi di %USERPROFILE%\\.claude\\settings.json; prima di scrivere salva una copia
`settings.json.prima_del_gateway_<data>`. Vale per le sessioni aperte DOPO la modifica.
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
CA = Path(os.environ["USERPROFILE"]) / ".claude" / "qwen-gateway" / "ca.pem"
PORTA = 8787
CHIAVI = {"HTTPS_PROXY": f"http://127.0.0.1:{PORTA}", "NODE_EXTRA_CA_CERTS": str(CA), "NO_PROXY": "localhost,127.0.0.1"}


def gateway_vivo() -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORTA)) == 0


def main() -> int:
    azione = sys.argv[1] if len(sys.argv) > 1 else "--stato"
    dati = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    env = dati.get("env", {})
    attivo = all(env.get(k) == v for k, v in CHIAVI.items() if k != "NO_PROXY")
    if azione == "--stato":
        print("passaggio dal gateway:", "ATTIVO" if attivo else "spento", "| gateway in ascolto:", "si" if gateway_vivo() else "NO")
        return 0
    if azione == "--attiva":
        if not CA.exists():
            sys.exit(f"manca {CA}: esegui prima genera_ca.py")
        if not gateway_vivo():
            sys.exit(f"il gateway non ascolta su 127.0.0.1:{PORTA}: avvialo prima, altrimenti Claude Code non si collega")
        nuovo = {**env, **CHIAVI}
    elif azione == "--disattiva":
        nuovo = {k: v for k, v in env.items() if k not in CHIAVI}
    else:
        sys.exit(__doc__)
    if nuovo == env:
        print("niente da cambiare")
        return 0
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_name(f"settings.json.prima_del_gateway_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))
    if nuovo:
        dati["env"] = nuovo
    else:
        dati.pop("env", None)
    SETTINGS.write_text(json.dumps(dati, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("fatto:", "passaggio dal gateway ATTIVO" if azione == "--attiva" else "Claude Code torna DIRETTO ad Anthropic",
          "- vale per le sessioni aperte da adesso")
    return 0


if __name__ == "__main__":
    sys.exit(main())
