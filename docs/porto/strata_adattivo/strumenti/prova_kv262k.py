"""Prova KV 262k con fixture 131k e carico reale; tutti gli output nel checkout.

Non aggiunge stress artificiali e termina solo i processi avviati da questa corsa.
Usa il runtime Python integrato con le dipendenze del clone, senza scrivere nel clone.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request

CLONE = Path(r"D:\ds4_work\strata\Strata")
sys.path.insert(0, str(CLONE / ".venv/Lib/site-packages"))
import psutil

HERE = Path(__file__).resolve().parent
AREA = HERE.parent
REPO = AREA.parents[2]
PORT = 18120


def monitor(stop, path):
    known = {}
    with path.open("w", encoding="utf-8") as f:
        while not stop.is_set():
            record = {"t": time.strftime("%H:%M:%S"), "proc": {},
                      "ram_disp_gb": round(psutil.virtual_memory().available / 2**30, 2)}
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    old = known.get(p.pid)
                    if old is None:
                        p.cpu_percent(None)
                        known[p.pid] = p
                        continue
                    value = old.cpu_percent(None) / 100
                    if value >= 0.05:
                        name = p.info["name"] or str(p.pid)
                        record["proc"][name] = round(record["proc"].get(name, 0) + value, 2)
                except (psutil.Error, OSError):
                    pass
            f.write(json.dumps(record) + "\n")
            f.flush()
            stop.wait(10)


def get_json(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=5) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nome", default="kv262k_prompt131k")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--exe", type=Path, help="Eseguibile candidato; altrimenti build-0130")
    ap.add_argument("--server-source", type=Path, help="Sorgenti server della versione candidata; altrimenti clone operativo")
    ap.add_argument("--needle-lengths", help="Dopo il banco: controllo retrieval upstream, ad esempio 32k,250k")
    ap.add_argument("--retrieval-250k", action="store_true", help="Dopo il banco: prompt con almeno 250000 token reali e ago al 50%")
    ap.add_argument("--solo-retrieval-250k", action="store_true", help="Solo riempimento/retrieval 250k, senza ripetere il banco 131k")
    ap.add_argument("--durata-max-s", type=int, default=3600, help="Limite totale della corsa, incluso avvio; termina i soli processi propri")
    ap.add_argument("--logits-first", action="store_true", help="Diagnostica opt-in del primo token di ogni richiesta, se compilata")
    ap.add_argument("--gather-modo", choices=["uno", "batch"], help="A/B PR439 nello stesso binario; cache operativa preservata")
    ap.add_argument("--solo-avvio", action="store_true", help="Verifica avvio e capacita' senza inviare prompt")
    ap.add_argument("--cache-fissa", type=int, help="Solo laboratorio: budget slot richiesto, senza elasticita'; il pack puo' aumentare gli slot effettivi")
    a = ap.parse_args()
    if a.durata_max_s <= 0 or (a.solo_avvio and a.solo_retrieval_250k):
        ap.error("Durata positiva e modalita' solo-avvio/solo-retrieval distinte")
    deadline = time.monotonic() + a.durata_max_s
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("Limite totale della corsa raggiunto")
        return seconds
    active = [p.info["name"] for p in psutil.process_iter(["name"])
              if (p.info["name"] or "").lower() in ("strata.exe", "llama-server.exe")]
    if active:
        raise RuntimeError(f"Motore gia' attivo: {active}; nessun processo viene fermato")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", PORT))
    out = (a.out or REPO / ".codex_runs" / (time.strftime("%Y%m%d_%H%M%S_") + a.nome)).resolve()
    out.mkdir(parents=True, exist_ok=False)
    cfg = json.loads((AREA / "lanciatori/strata-2080ti-256k.json").read_text(encoding="utf-8-sig"))
    if a.exe:
        candidate = a.exe.resolve(strict=True)
        cfg["exe"] = str(candidate)
    cfg.update(cwd=str(out), log=str(out / "strata.log"), port=PORT, host="127.0.0.1")
    cfg["env"] = dict(cfg.get("env", {}), STRATA_WATCHDOG_S="240", STRATA_SPLIT_TIMING="1")
    if a.logits_first:
        cfg["env"]["STRATA_DUMP_FIRST_LOGITS"] = str(out / "first-logits")
    if a.gather_modo == "uno":
        cfg["env"]["STRATA_PREFILL_GATHER_ONE"] = "1"
    elif a.gather_modo == "batch":
        cfg["env"].pop("STRATA_PREFILL_GATHER_ONE", None)
    if a.cache_fissa is not None:
        if a.cache_fissa <= 0:
            raise ValueError("La cache fissa deve avere un numero positivo di slot")
        cfg["args"] = [arg for arg in cfg["args"] if arg != "--elastic"]
        index = cfg["args"].index("--expert-cache")
        cfg["args"][index + 1] = str(a.cache_fissa)
    cfg_path = out / "config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    env = dict(os.environ)
    # Il chiamante esclude STRATA_API_KEY senza leggerla prima di avviare questo processo.
    if "STRATA_API_KEY" in env:
        raise RuntimeError("Escludere STRATA_API_KEY dall'ambiente del solo processo di laboratorio")
    if a.gather_modo is not None:
        # La PR controlla la presenza, anche un valore "0" disattiva il batch.
        env.pop("STRATA_PREFILL_GATHER_ONE", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    server_wrapper = out / "server_bootstrap.py"
    bench_wrapper = out / "bench_bootstrap.py"
    bootstrap = ("import sys, runpy\n"
                 f"sys.path.insert(0, {str(CLONE / '.venv/Lib/site-packages')!r})\n")
    server_source = (a.server_source or CLONE).resolve(strict=True)
    server_path = (server_source / "serve/server.py").resolve(strict=True)
    server_wrapper.write_text(bootstrap + f"runpy.run_path({str(server_path)!r}, run_name='__main__')\n",
                              encoding="utf-8")
    bench_path = AREA.parent / "strata_prova/banco_strata.py"
    bench_wrapper.write_text(bootstrap + f"sys.path.insert(0, {str(bench_path.parent)!r})\n"
                             f"runpy.run_path({str(bench_path)!r}, run_name='__main__')\n", encoding="utf-8")
    stop = threading.Event()
    sampler = threading.Thread(target=monitor, args=(stop, out / "cpu.jsonl"), daemon=True)
    server = None
    bench = None
    result = {"name": a.nome, "kv_capacity": 262144,
              "prompt_profile": None if a.solo_avvio or a.solo_retrieval_250k else "lungo_131k", "out": str(out),
              "duration_limit_s": a.durata_max_s,
              "exe": cfg["exe"],
              "exe_sha256": hashlib.sha256(Path(cfg["exe"]).read_bytes()).hexdigest(),
              "server_source": str(server_source),
              "server_sha256": hashlib.sha256(server_path.read_bytes()).hexdigest(),
              "requested_fixed_cache_slots": a.cache_fissa,
              "gather_mode": a.gather_modo,
              "artificial_load": False, "status": "starting"}
    print("OUTPUT", out, flush=True)
    sampler.start()
    try:
        with (out / "server.log").open("w", encoding="utf-8") as server_log:
            server = subprocess.Popen([sys.executable, "-B", "-u", str(server_wrapper), "--engine", "strata",
                                       "--config", str(cfg_path), "--host", "127.0.0.1", "--port", str(PORT)],
                                      cwd=out, env=env, stdout=server_log, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            (out / "server.pid").write_text(str(server.pid), encoding="ascii")
            started = time.monotonic()
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"Server terminato durante l'avvio: {server.returncode}; vedere server.log")
                try:
                    health = get_json("/health")
                    if health.get("status") == "ok":
                        break
                except (OSError, ValueError):
                    pass
                if time.monotonic() - started > 600:
                    raise TimeoutError("Server non pronto entro 600 s")
                remaining()
                time.sleep(3)
            if health.get("max_context") != 262144:
                raise RuntimeError(f"Capacita' runtime inattesa: {health.get('max_context')}")
            result.update(status="ready", startup_s=round(time.monotonic() - started, 2), health=health)
            (out / "health.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
            print("READY", health["max_context"], "token; avvio", result["startup_s"], "s", flush=True)
            initial_metrics = get_json("/metrics")
            (out / "metrics_initial.json").write_text(json.dumps(initial_metrics, indent=2), encoding="utf-8")
            engine = initial_metrics["engine"]
            result["initial_cache"] = {key: engine.get(key) for key in
                                       ("expert_slots", "expert_cache_mib", "vram_free_mib")}
            print("CACHE", json.dumps(result["initial_cache"]), flush=True)
            if a.cache_fissa is not None and engine.get("vram_free_mib", 0) < 1000:
                raise RuntimeError("Cache fissa senza margine VRAM di almeno 1000 MiB; nessun prompt inviato")
            if a.solo_avvio:
                result.update(status="completed", test_type="startup_only")
                return
            if a.solo_retrieval_250k:
                with (out / "retrieval-250k.log").open("w", encoding="utf-8") as log:
                    bench = subprocess.Popen([sys.executable, "-B", "-u", str(HERE / "retrieval_250k.py"),
                        "--source", str(server_source), "--tokenizer", cfg["tokenizer"],
                        "--url", f"http://127.0.0.1:{PORT}", "--out", str(out / "retrieval-250k")],
                        cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    code = bench.wait(timeout=remaining())
                result["retrieval_250k"] = json.loads((out / "retrieval-250k/result.json").read_text(encoding="utf-8"))
                print((out / "retrieval-250k.log").read_text(encoding="utf-8"), flush=True)
                if code:
                    raise RuntimeError("Controllo 250k fallito; vedere retrieval-250k/result.json")
                result.update(status="completed", test_type="retrieval_250k_only")
                return
            with (out / "banco.log").open("w", encoding="utf-8") as bench_log:
                bench = subprocess.Popen([sys.executable, "-B", "-u", str(bench_wrapper), "--profilo", "lungo_131k",
                                          "--url", f"http://127.0.0.1:{PORT}", "--etichetta", a.nome,
                                          "--out", str(out / "banco"), "--nota", "KV 262144; prompt 131k; carico reale"],
                                         cwd=out, env=env, stdout=bench_log, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                if bench.wait(timeout=remaining()) != 0:
                    raise RuntimeError("Banco fallito; vedere banco.log")
            runs = list((out / "banco").glob("*/results.jsonl"))
            if len(runs) != 1:
                raise RuntimeError("Risultati mancanti o ambigui")
            rows = [json.loads(line) for line in runs[0].read_text(encoding="utf-8").splitlines()]
            useful = [row for row in rows if not row.get("riscaldamento")]
            if len(useful) != 2 or any(row["fine"] != "length" or row["motore"]["output_tokens"] != 1024
                                       for row in useful):
                raise RuntimeError("Le due richieste non hanno completato il budget di 1024 token")
            summary = json.loads((runs[0].parent / "riassunto.json").read_text(encoding="utf-8"))
            result.update(status="completed", summary=summary)
            print(json.dumps(summary, indent=2), flush=True)
            if a.needle_lengths:
                needle_tool = (server_source / "tools/needle_bench.py").resolve(strict=True)
                with (out / "needles.log").open("w", encoding="utf-8") as log:
                    bench = subprocess.Popen([sys.executable, "-B", "-u", str(needle_tool),
                        "--url", f"http://127.0.0.1:{PORT}", "--lengths", a.needle_lengths,
                        "--depths", "10,50,90", "--out", str(out / "needles.json")],
                        cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    code = bench.wait(timeout=remaining())
                result["needles"] = json.loads((out / "needles.json").read_text(encoding="utf-8"))
                print((out / "needles.log").read_text(encoding="utf-8"), flush=True)
                if code:
                    raise RuntimeError("Retrieval needle fallito; vedere needles.json")
            if a.retrieval_250k:
                with (out / "retrieval-250k.log").open("w", encoding="utf-8") as log:
                    bench = subprocess.Popen([sys.executable, "-B", "-u", str(HERE / "retrieval_250k.py"),
                        "--source", str(server_source), "--tokenizer", cfg["tokenizer"],
                        "--url", f"http://127.0.0.1:{PORT}", "--out", str(out / "retrieval-250k")],
                        cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    code = bench.wait(timeout=remaining())
                result["retrieval_250k"] = json.loads((out / "retrieval-250k/result.json").read_text(encoding="utf-8"))
                print((out / "retrieval-250k.log").read_text(encoding="utf-8"), flush=True)
                if code:
                    raise RuntimeError("Controllo 250k fallito; vedere retrieval-250k/result.json")
    except Exception as exc:
        result.update(status="failed", error=str(exc))
        raise
    finally:
        if bench is not None and bench.poll() is None:
            bench.terminate()
            try:
                bench.wait(timeout=10)
            except subprocess.TimeoutExpired:
                bench.kill()
        if server is not None and server.poll() is None:
            try:
                children = psutil.Process(server.pid).children(recursive=True)
            except psutil.Error:
                children = []
            for child in reversed(children):
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
            _, alive = psutil.wait_procs(children, timeout=5)
            for child in alive:
                try:
                    child.kill()
                except psutil.Error:
                    pass
        stop.set()
        sampler.join(timeout=3)
        (out / "esito.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("ESITO", result["status"], flush=True)


if __name__ == "__main__":
    main()
