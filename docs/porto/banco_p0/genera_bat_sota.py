"""Genera sul Desktop un .bat che avvia il server Qwen nella configurazione SOTA (preset X4 di P11).
Uso: python genera_bat_sota.py [preset.json] [nome_bat]
"""
import json
import re
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
preset = QUI / (sys.argv[1] if len(sys.argv) > 1 else "preset_X4_p11.json")
nome = sys.argv[2] if len(sys.argv) > 2 else "qwen_sota_16-09.bat"
out = Path(r"C:\Users\imanu\Desktop") / nome
bat_prod = Path(r"C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat")

p = json.loads(preset.read_text(encoding="utf-8"))
key = re.search(r'set "API_KEY=([^"]*)"', bat_prod.read_text(encoding="utf-8", errors="replace")).group(1)
per = p["percorsi"]
logdir = per["LOGDIR"]
sost = {
    "{MODEL}": per["MODEL"], "{MMPROJ}": per["MMPROJ"], "{DRAFT}": per["DRAFT"],
    "{FFMPEGDIR}": per["FFMPEGDIR"], "{SLOTDIR}": per["SLOTDIR"],
    "{LOGFILE}": logdir + "\\sota_" + p["id"] + "_%STAMP%.log",
    "{CONTEXT}": str(p["contesto"]), "{SLOTS}": str(p["slot_esperti"]),
    "{HOST}": "%HOST%", "{PORT}": "%PORT%", "{APIKEY}": "%API_KEY%",
}
args = []
for a in p["args"]:
    v = a
    for k, s in sost.items():
        v = v.replace(k, s)
    if (" " in v or "\\" in v) and not v.startswith("%"):
        v = '"' + v + '"'
    args.append(v)

L = [
    "@echo off",
    "REM Qwen3.8-Flash-Next - configurazione SOTA misurata il 15/9 (preset %s di P11):" % p["id"],
    "REM prefill 397 t/s e decode 27,2 t/s a 131k. Binari P11 (snapshot P0 + patch P8/P10/P11).",
    "REM Generato il 16/9 da docs/porto/banco_p0/genera_bat_sota.py. Niente pause: una finestra ferma = un secondo server.",
    "setlocal",
    'set "HOST=0.0.0.0"',
    'set "PORT=8100"',
    'set "API_KEY=%s"' % key,
    'for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "D=%%c%%b%%a"',
    'for /f "tokens=1-2 delims=:." %%a in ("%time%") do set "T=%%a%%b"',
    'set "STAMP=%D%_%T: =0%"',
    "",
    "REM ---- guardia istanza unica: se la porta e gia in ascolto NON avvio un secondo server",
    'netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul',
    "if not errorlevel 1 (",
    "  echo ERRORE: la porta %PORT% e gia in ascolto. Chiudi il server esistente e rilancia.",
    "  timeout /t 20",
    "  exit /b 1",
    ")",
    "",
    "REM ---- manopole (tutte dal preset %s)" % p["id"],
]
for k, v in p["env"].items():
    L.append('set "%s=%s"' % (k, v))
L += [
    "",
    'if not exist "%s" mkdir "%s"' % (logdir, logdir),
    'if not exist "%s" mkdir "%s"' % (per["SLOTDIR"], per["SLOTDIR"]),
    'if not exist "%s" mkdir "%s"' % (p["working_dir"], p["working_dir"]),
    'cd /d "%s"' % p["working_dir"],
    "echo Avvio Qwen SOTA %s su %%HOST%%:%%PORT%%  (log: %s\\sota_%s_%%STAMP%%.log)" % (p["id"], logdir, p["id"]),
    '"%s\\%s" ^' % (p["binari"], p["server_exe"]),
]
for i, a in enumerate(args):
    L.append("  " + a + (" ^" if i < len(args) - 1 else ""))
L += [
    "if errorlevel 1 (",
    "  echo Il server e uscito con errore %errorlevel%. Vedi il log.",
    "  timeout /t 60",
    ")",
    "endlocal",
]
out.write_text("\r\n".join(L) + "\r\n", encoding="cp1252")
print("scritto", out, "righe", len(L))
