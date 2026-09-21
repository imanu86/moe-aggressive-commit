"""Avvia un llama-server ISOLATO per le prove del gateway (127.0.0.1:8113, chiave temporanea).

Stessa configurazione del banco follow-up (`docs/porto/banco_followup/banco_followup.py`): braccio
`m1` = runtime elastico adattivo, `x4` = binari p11 a 40 slot. Non tocca la produzione (porta 8100).
"""
from __future__ import annotations
import contextlib
import importlib.util
import json
import os
import secrets
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

_BANCO = Path(__file__).resolve().parents[1] / "banco_followup" / "banco_followup.py"
_spec = importlib.util.spec_from_file_location("banco_followup", _BANCO)
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

HOST, PORT = B.HOST, B.PORT


@contextlib.contextmanager
def server(braccio: str, run: Path, log, leve: dict | None = None, slot: str | None = None):
    """Context manager: yield (base_url, chiave). Chiude con CTRL_BREAK, poi terminate se serve.

    `leve` = variabili d'ambiente in piu' (vincono sul braccio), `slot` = numero di slot al posto di quello del braccio.
    """
    config_path, runtime, extra_env, slots = B.BRACCI[braccio]
    slots = slot or slots
    for name in ("logs", "slots", "ffcache", "tmp", "cuda-cache"):
        (run / name).mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.settimeout(1)
        assert s.connect_ex((HOST, PORT)) != 0, f"porta {PORT} occupata"
    vivi = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"],
                          capture_output=True, text=True).stdout
    assert "llama-server.exe" not in vivi, "c'e' gia' un llama-server vivo"

    config = json.loads(config_path.read_text(encoding="utf-8"))
    runtime = runtime or Path(config["binari"]) / config["server_exe"]
    slots = slots or str(config["slot_esperti"])
    key = secrets.token_urlsafe(32)
    keyfile = run / "api-key.txt"
    keyfile.write_text(key + "\n", encoding="ascii")
    repl = {**config["percorsi"], "SLOTDIR": str(run / "slots"), "LOGFILE": str(run / "logs" / "server.log"),
            "HOST": HOST, "PORT": str(PORT), "CONTEXT": str(config["contesto"]), "SLOTS": slots,
            "APIKEY": str(keyfile)}
    argv = [str(runtime)]
    for v in config["args"]:
        if v == "--api-key":
            argv.append("--api-key-file")
        elif v.startswith("{") and v.endswith("}"):
            argv.append(repl[v[1:-1]])
        else:
            argv.append(v)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("GGML_", "LLAMA_", "QWEN"))}
    env.update(config["env"])
    if extra_env == "ELASTIC":
        env.update(B.ELASTIC_ENV)
    env.update(leve or {})
    env.update({"TEMP": str(run / "tmp"), "TMP": str(run / "tmp"), "CUDA_CACHE_PATH": str(run / "cuda-cache")})

    with (run / "logs" / "server.stdout.txt").open("w") as out, (run / "logs" / "server.stderr.txt").open("w") as err:
        proc = subprocess.Popen(argv, cwd=run / "ffcache", env=env, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=err, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    t0 = time.perf_counter()
    try:
        health = urllib.request.Request(f"http://{HOST}:{PORT}/health", headers={"Authorization": "Bearer " + key})
        while True:
            assert proc.poll() is None, f"server uscito in caricamento: {proc.returncode}"
            assert time.perf_counter() - t0 < 1800, "health timeout"
            try:
                with urllib.request.urlopen(health, timeout=3) as r:
                    if json.loads(r.read()).get("status") == "ok":
                        break
            except Exception:
                time.sleep(1)
        log(f"server {braccio} pronto in {time.perf_counter() - t0:.1f} s | VRAM {B.smi()}")
        yield f"http://{HOST}:{PORT}", key
    finally:
        chiusura = "gia' uscito"
        if proc.poll() is None:
            try:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.wait(timeout=90)
                chiusura = f"CTRL_BREAK, uscita {proc.returncode}"
            except Exception as exc:
                proc.terminate()
                proc.wait(timeout=30)
                chiusura = f"ANOMALIA: terminate ({type(exc).__name__})"
        keyfile.unlink(missing_ok=True)
        time.sleep(5)
        log(f"chiusura: {chiusura} | VRAM dopo {B.smi()}")
