"""Prova di Strata sulla RTX 2080 Ti, 30/9/2026.

Stessa configurazione del confronto equo (strata-iq3_xxs-r1032.json) salvo eseguibile, riserva ed elastica; profilo
`rapido`; CPU di tutti i processi campionata ogni 10 s (daily_rapido.campiona).
Uso:  python prova_sm75.py [--exe PERCORSO] [--riserva MIB] [--elastic] [--nome NOME]
      (predefiniti: build-sm75 della 0.1.21, riserva 1393, cache fissa, nome sm75_fissa / sm75_elastica)
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_prova")
sys.path.insert(0, str(Path(__file__).parent))
import curva_strata as C  # noqa: E402
import f0_profilo as F  # noqa: E402
from daily_rapido import campiona  # noqa: E402


def opz(nome, predefinito):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else predefinito


import os  # noqa: E402

# 30/9: --env K=V (anche piu' volte) passa variabili al motore, es. STRATA_SPLIT_TIMING=1
for i, a in enumerate(sys.argv):
    if a == "--env":
        k, v = sys.argv[i + 1].split("=", 1)
        os.environ[k] = v
C.BASE["exe"] = opz("--exe", r"D:\ds4_work\strata\Strata\build-sm75\strata.exe")
riserva = opz("--riserva", "1393")
elastica = "--elastic" in sys.argv
nome = opz("--nome", "sm75_elastica" if elastica else "sm75_fissa")
F.OUT.mkdir(parents=True, exist_ok=True)
stop = threading.Event()
th = threading.Thread(target=campiona, args=(stop, F.OUT / f"cpu_{nome}.jsonl"), daemon=True)
th.start()
try:
    print("exe", C.BASE["exe"], "riserva", riserva, "elastica", elastica, flush=True)
    # 30/9: --arg K=V sostituisce (o aggiunge) un argomento del motore, es. --arg --spec-min-p=0.3
    sost = {"--vram-reserve-mib": riserva}
    extra = []
    for i, a in enumerate(sys.argv):
        if a == "--arg":
            k, v = sys.argv[i + 1].split("=", 1)
            if k in C.BASE["args"]:
                sost[k] = v
            else:
                extra += [k, v]
    print("sostituiti", sost, "aggiunti", extra, flush=True)
    F.corsa(nome, F.args_con(sostituisci=sost) + extra + (["--elastic"] if elastica else []), "rapido")
finally:
    stop.set()
print("FINE", time.strftime("%H:%M:%S"), flush=True)
