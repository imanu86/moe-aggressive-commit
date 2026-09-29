"""F0 del fork adattivo (29/9/2026): il profilo degli esperti costruito dal NOSTRO lavoro contro quello originale.

1. addestra: Strata con `--dump-routing`, i prompt del profilo `addestra` di banco_strata.py (S01-S10, L05-L08 corti,
   mai usati nella misura); 2. `tools/make_profile.py --no-base` sulla traccia; 3. A = profilo originale, B = il nostro,
   A2 = di nuovo l'originale in coda (deriva della macchina), tutti col profilo `f0` del banco. Stessa riserva per tutti
   (1.393 MiB, chiesta dal motore la mattina del 29/9). Riusa avvio/arresto di curva_strata.py.

Uso:  python f0_profilo.py [fase ...]     fasi: addestra profilo A B A2 (senza argomenti: tutte)
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import curva_strata as C  # noqa: E402  (ferma, pronto, vram_mib, PY, S, PORTA)

OUT = Path(r"D:\ds4_work\strata\f0")
TRACCIA = OUT / "routing_addestra.bin"
PROFILO = OUT / "profilo_nostro.bin"
RISERVA = "1393"


def args_con(extra_via=(), sostituisci=None):
    base, a, i = C.BASE["args"], [], 0
    sostituisci = sostituisci or {}
    while i < len(base):
        if base[i] in extra_via or base[i] in sostituisci:
            if base[i] in sostituisci:
                a += [base[i], sostituisci[base[i]]]
            i += 2
            continue
        a.append(base[i])
        i += 1
    return a


def corsa(nome, args, profilo_banco):
    C.ferma()
    time.sleep(5)
    cfg = dict(C.BASE, args=args, log=str(OUT / f"strata_{nome}.log"))
    cfg_path = C.S / f"f0_{nome}.json"
    cfg_path.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    v0 = C.vram_mib()
    print(f"[{time.strftime('%H:%M:%S')}] {nome}: VRAM altri programmi {v0} MiB", flush=True)
    srv = subprocess.Popen([str(C.PY), str(C.S / "serve" / "server.py"), "--engine", "strata", "--config", str(cfg_path),
                            "--port", str(C.PORTA)], cwd=str(C.S),
                           stdout=open(OUT / f"server_{nome}.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    if not C.pronto():
        print(f"  {nome}: server non pronto", flush=True)
    else:
        for l in Path(cfg["log"]).read_text(encoding="utf-8", errors="replace").splitlines():
            if "expert cache" in l and "slots" in l or "VRAM free with everything" in l:
                print("  " + l.strip(), flush=True)
        b = subprocess.run([str(C.PY), str(HERE / "banco_strata.py"), "--profilo", profilo_banco, "--url",
                            f"http://127.0.0.1:{C.PORTA}", "--etichetta", f"f0_{nome}",
                            "--nota", f"F0 {nome}, VRAM altri {v0} MiB"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        for l in b.stdout.splitlines():
            if "@ctx" in l or "@corto" in l:
                print(l, flush=True)
    C.ferma()
    srv.wait(timeout=60)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fasi = sys.argv[1:] or ["addestra", "profilo", "A", "B", "A2"]
    riserva = {"--vram-reserve-mib": RISERVA}
    for fase in fasi:
        if fase == "addestra":
            corsa("addestra", args_con(sostituisci=riserva) + ["--dump-routing", str(TRACCIA)], "addestra")
            print(f"  traccia: {TRACCIA.stat().st_size / 2**20:.1f} MiB", flush=True)
        elif fase == "profilo":
            r = subprocess.run([str(C.PY), str(C.S / "tools" / "make_profile.py"), str(TRACCIA), "--no-base",
                                "--out", str(PROFILO)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(r.stdout.strip()[-800:], r.stderr.strip()[-400:], flush=True)
        elif fase in ("A", "A2"):
            corsa(fase, args_con(sostituisci=riserva), "f0")
        elif fase == "B":
            corsa("B", args_con(sostituisci=dict(riserva, **{"--expert-profile": str(PROFILO)})), "f0")
    print("FINE", flush=True)


if __name__ == "__main__":
    main()
