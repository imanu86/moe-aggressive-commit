"""Installa l'avvio automatico del gateway e i due bat di servizio sul Desktop.

  - collegamento «Gateway Qwen per Claude.lnk» nella cartella Esecuzione automatica dell'utente:
    all'accesso a Windows parte `pythonw guardiano.py` (nessuna finestra), che avvia e sorveglia il gateway;
  - Desktop\\«Claude - avvia gateway Qwen.bat»: accende guardiano + gateway e attiva il passaggio;
  - Desktop\\«Claude - TORNA DIRETTO (senza gateway).bat»: toglie le chiavi e il segno `voluto`.
Per disinstallare: cancellare il collegamento ed eseguire il bat «TORNA DIRETTO».
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
PY = Path(sys.executable).with_name("python.exe")
PYW = Path(sys.executable).with_name("pythonw.exe")
DESKTOP = Path(os.environ["USERPROFILE"]) / "Desktop"
AVVIO = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
LNK = AVVIO / "Gateway Qwen per Claude.lnk"

BAT = {
    "Claude - avvia gateway Qwen.bat": [
        "@echo off",
        "REM Accende il guardiano (che avvia e sorveglia il gateway su 127.0.0.1:8787) e attiva il passaggio",
        "REM di Claude Code dal gateway. Col server Qwen acceso le chat su Haiku vanno a Qwen; spento, tutto ad Anthropic.",
        f'start "" "{PYW}" "{QUI}\\guardiano.py"',
        "timeout /t 4 >nul",
        f'"{PY}" "{QUI}\\imposta_proxy.py" --attiva',
        f'"{PY}" "{QUI}\\imposta_proxy.py" --stato',
        "timeout /t 12",
    ],
    "Claude - TORNA DIRETTO (senza gateway).bat": [
        "@echo off",
        "REM Toglie HTTPS_PROXY / NODE_EXTRA_CA_CERTS / NO_PROXY da %USERPROFILE%\\.claude\\settings.json e il segno",
        "REM `voluto`: Claude Code torna DIRETTO ad Anthropic e il guardiano non riaccende il passaggio.",
        f'"{PY}" "{QUI}\\imposta_proxy.py" --disattiva',
        f'"{PY}" "{QUI}\\imposta_proxy.py" --stato',
        "timeout /t 20",
    ],
}


def main() -> int:
    assert PYW.exists(), f"manca {PYW}"
    for nome, righe in BAT.items():
        (DESKTOP / nome).write_bytes(("\r\n".join(righe) + "\r\n").encode("ascii"))
        print("scritto:", DESKTOP / nome)
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{LNK}'); $s.TargetPath = '{PYW}'; "
          f"$s.Arguments = '\"{QUI}\\guardiano.py\"'; $s.WorkingDirectory = '{QUI}'; "
          "$s.Description = 'Guardiano del gateway locale di Claude Code (Qwen al posto di Haiku)'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    print("collegamento di avvio automatico:", LNK, "->", LNK.exists())
    return 0


if __name__ == "__main__":
    sys.exit(main())
