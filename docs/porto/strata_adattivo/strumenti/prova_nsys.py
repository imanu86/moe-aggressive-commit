"""Profilo Nsight Systems di Strata a meta' decodifica, 30/9/2026.

Stessa configurazione della prova C (build-0129, --elastic, riserva di avvio 1393). Il server parte sotto nsys (che
segue anche strata.exe, figlio del server Python) con --cuda-graph-trace=node, cosi' si vedono i kernel dentro il grafo
della finestra di verifica; la cattura parte dopo --ritardo secondi e dura --durata, mentre gira il profilo `rapido`.
Poi `nsys stats` riassume i kernel per tempo GPU totale.
Uso:  python prova_nsys.py [--ritardo 120] [--durata 15]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_prova")
import curva_strata as C  # noqa: E402
import f0_profilo as F  # noqa: E402

NSYS = r"C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe"
OUT = Path(r"D:\ds4_work\strata\nsys")


def opz(nome, predefinito):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else predefinito


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ritardo, durata = opz("--ritardo", "120"), opz("--durata", "15")
    C.BASE["exe"] = r"D:\ds4_work\strata\Strata\build-0129\strata.exe"
    args = F.args_con(sostituisci={"--vram-reserve-mib": "1393"}) + ["--elastic"]
    cfg = dict(C.BASE, args=args, log=str(OUT / "strata_nsys.log"))
    cfg_path = C.S / "f0_nsys.json"
    cfg_path.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    C.ferma()
    time.sleep(5)
    rep = OUT / "strata_2080ti"
    srv = subprocess.Popen([NSYS, "profile", "--trace=cuda", "--cuda-graph-trace=node", "--sample=none",
                            "--cpuctxsw=none", "--delay", ritardo, "--duration", durata, "--force-overwrite", "true",
                            "-o", str(rep), str(C.PY), str(C.S / "serve" / "server.py"), "--engine", "strata",
                            "--config", str(cfg_path), "--port", str(C.PORTA)], cwd=str(C.S),
                           stdout=open(OUT / "server_nsys.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    t0 = time.time()
    if not C.pronto():
        print("server non pronto", flush=True)
    else:
        print("server pronto dopo %.0f s dal lancio; cattura da %s s per %s s" % (time.time() - t0, ritardo, durata),
              flush=True)
        b = subprocess.run([str(C.PY), str(F.HERE / "banco_strata.py"), "--profilo", "rapido", "--url",
                            f"http://127.0.0.1:{C.PORTA}", "--etichetta", "nsys"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        for l in b.stdout.splitlines():
            if "@corto" in l:
                print(l, flush=True)
    C.ferma()
    try:
        srv.wait(timeout=300)   # nsys scrive il rapporto dopo che i processi sono usciti
    except subprocess.TimeoutExpired:
        print("nsys non ha finito in 300 s", flush=True)
    r = subprocess.run([NSYS, "stats", "--report", "cuda_gpu_kern_sum", "--format", "csv", "--force-export", "true",
                        "-o", str(OUT / "kernel"), str(rep) + ".nsys-rep"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout[-3000:], r.stderr[-2000:], flush=True)
    print("FINE", time.strftime("%H:%M:%S"), flush=True)


if __name__ == "__main__":
    main()
