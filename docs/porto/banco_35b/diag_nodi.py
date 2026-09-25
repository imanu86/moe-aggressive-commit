"""Conta nodi e partizioni del grafo del decode (25/9): contare, non cronometrare.

Avvia llama-server con GGML_SCHED_DEBUG=2 e -lv 5 su una porta locale senza chiave, manda UNA richiesta da
pochi token, chiude il server, e dall'ultimo grafo stampato (quello del decode a un token) conta:
partizioni (## SPLIT, ognuna un passaggio di consegne fra backend) e nodi, con istogramma per operazione.
Uso: python diag_nodi.py --exe ...\\llama-server.exe --model ...gguf --etichetta nome [--env K=V ...] [-- args extra]
"""
import argparse
import collections
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--exe", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--etichetta", required=True)
ap.add_argument("--porta", type=int, default=8114)
ap.add_argument("--env", action="append", default=[])
ap.add_argument("extra", nargs=argparse.REMAINDER)
a = ap.parse_args()

out = Path(r"D:\ds4_work\banco_35b_run\diag") / a.etichetta
out.mkdir(parents=True, exist_ok=True)
log = out / "server.log"
env = dict(os.environ, GGML_SCHED_DEBUG="2")
for kv in a.env:
    k, v = kv.split("=", 1)
    env[k] = v
extra = [x for x in a.extra if x != "--"]
cmd = [a.exe, "-m", a.model, "--host", "127.0.0.1", "--port", str(a.porta), "-np", "1", "--jinja",
       "--reasoning", "off", "-lv", "5", "--log-file", str(log)] + extra
with (out / "stderr.txt").open("w", encoding="utf-8", errors="replace") as err:
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err, env=env, stdin=subprocess.DEVNULL)
    try:
        for _ in range(600):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{a.porta}/health", timeout=3) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass
            if p.poll() is not None:
                raise SystemExit("server uscito durante il caricamento, vedi " + str(out / "stderr.txt"))
            time.sleep(1)
        body = json.dumps({"messages": [{"role": "user", "content": "Scrivi un oggetto JSON con i campi nome e eta."}],
                           "max_tokens": 6, "temperature": 0, "stream": False}).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{a.porta}/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            risposta = json.loads(r.read().decode("utf-8"))
    finally:
        p.terminate()
        try:
            p.wait(timeout=30)
        except Exception:
            p.kill()

testo = ""
for f in (log, out / "stderr.txt"):
    if f.exists():
        testo += f.read_text(encoding="utf-8", errors="replace") + "\n"
righe = testo.splitlines()
inizi = [i for i, r in enumerate(righe) if "## SPLIT #0:" in r]
if not inizi:
    raise SystemExit("nessuna riga '## SPLIT' nel log: SCHED_DEBUG o verbosita' non arrivati")
grafo = righe[inizi[-1]:]
fine = next((i for i, r in enumerate(grafo[1:], 1) if "## SPLIT #0:" in r), len(grafo))
grafo = grafo[:fine]
split = [r for r in grafo if "## SPLIT #" in r]
nodi = [r for r in grafo if re.search(r"node #\s*\d+", r)]
ops = collections.Counter()
for r in nodi:
    m = re.search(r"node #\s*\d+\s*\(\s*([A-Z0-9_]+)\s*\)", r)
    ops[m.group(1) if m else "?"] += 1
backend = collections.Counter(re.search(r"## SPLIT #\d+: (\S+)", r).group(1) for r in split)
ris = {"etichetta": a.etichetta, "partizioni": len(split), "per_backend": dict(backend), "nodi": len(nodi),
       "ops": dict(ops.most_common()), "tempi_server": risposta.get("timings")}
(out / "conteggio.json").write_text(json.dumps(ris, indent=1), encoding="utf-8")
print(json.dumps({k: ris[k] for k in ("etichetta", "partizioni", "per_backend", "nodi")}))
print("ops piu' frequenti:", ", ".join(f"{k} {v}" for k, v in ops.most_common(14)))
