"""Prima prova di Strata sulla RTX 2080 Ti (build-sm75, opzione sperimentale), 30/9/2026.

Stessa configurazione del confronto equo (strata-iq3_xxs-r1032.json, riserva 1393 come negli A/B rapidi del 29/9), solo
l'eseguibile cambia; profilo `rapido`; CPU di tutti i processi campionata ogni 10 s (daily_rapido.campiona).
Uso:  python prova_sm75.py [--elastic]
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

C.BASE["exe"] = r"D:\ds4_work\strata\Strata\build-sm75\strata.exe"
elastica = "--elastic" in sys.argv
nome = "sm75_elastica" if elastica else "sm75_fissa"
F.OUT.mkdir(parents=True, exist_ok=True)
stop = threading.Event()
th = threading.Thread(target=campiona, args=(stop, F.OUT / f"cpu_{nome}.jsonl"), daemon=True)
th.start()
try:
    F.corsa(nome, F.args_con(sostituisci={"--vram-reserve-mib": "1393"}) + (["--elastic"] if elastica else []), "rapido")
finally:
    stop.set()
print("FINE", time.strftime("%H:%M:%S"), flush=True)
