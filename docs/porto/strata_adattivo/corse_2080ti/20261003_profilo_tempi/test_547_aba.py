"""Isolated operational A/B/A for PR #547 at a fresh 250k input, with first-logit parity."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
DAILY = Path(r"D:\ds4_work\strata\Strata")
SOURCE = DAILY / "build-0138-daily" / "source"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(DAILY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, r"C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75")
import psutil
import validate_model as V
from serve.server import StrataEngine

CFG = json.loads((DAILY / "strata-2080ti-sota.json").read_text(encoding="utf-8-sig"))
FIXTURE = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261003_allineamento038_grid_rimossa\250000-fresh.ids.json")
ids = json.loads(FIXTURE.read_text(encoding="utf-8"))
assert len(ids) == 250000
BASE_EXE = Path(CFG["exe"])
CANDIDATE_EXE = HERE / "build-547" / "strata.exe"
assert CANDIDATE_EXE.is_file()
OUT = HERE / "aba-547"
OUT.mkdir(exist_ok=False)
env = {k: v for k, v in os.environ.items() if not k.startswith("STRATA_")}
env.update(CFG.get("env", {}))
env.update(STRATA_PREFILL_TIMING="1", STRATA_DECODE_TIMING="1", STRATA_SPLIT_TIMING="1")
env["PATH"] = os.pathsep.join(CFG.get("lib_dirs", []) + [env.get("PATH", "")])
plan = {
    "status": "running",
    "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "hardware": "modified 22 GB RTX 2080 Ti; Ryzen 7 5800X",
    "protocol": "Daily 0.1.38 A1 / #547 candidate / Daily A2; fresh 250k input each arm",
    "artificial_pressure": False,
    "input_fixture": str(FIXTURE),
    "input_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
    "base_sha256": hashlib.sha256(BASE_EXE.read_bytes()).hexdigest(),
    "candidate_sha256": hashlib.sha256(CANDIDATE_EXE.read_bytes()).hexdigest(),
    "args": CFG["args"],
    "arms": [],
}
(OUT / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
telemetry_stop = threading.Event()
phase = "startup"

def watch():
    with (OUT / "resources.jsonl").open("w", encoding="utf-8") as f:
        while not telemetry_stop.is_set():
            row = {
                "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "phase": phase,
                "ram_available_gib": round(psutil.virtual_memory().available / 2**30, 2),
                "cpu_percent": psutil.cpu_percent(None),
            }
            try:
                row["gpu"] = subprocess.check_output([
                    "nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu,clocks.sm,power.draw",
                    "--format=csv,noheader,nounits",
                ], text=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW).strip()
            except Exception as exc:
                row["gpu_error"] = repr(exc)
            f.write(json.dumps(row) + "\n")
            f.flush()
            telemetry_stop.wait(10)

watcher = threading.Thread(target=watch, daemon=True)
watcher.start()
try:
    for label, exe in [("A1", BASE_EXE), ("B", CANDIDATE_EXE), ("A2", BASE_EXE)]:
        if any(p.info["name"] and p.info["name"].lower() == "strata.exe"
               for p in psutil.process_iter(["name"])):
            raise RuntimeError("A Strata engine is already active")
        if psutil.virtual_memory().available < 8 * 2**30:
            raise RuntimeError("Available RAM fell below the 8 GiB safety margin")
        phase = label
        folder = OUT / label
        folder.mkdir()
        logits = folder / "first.f32"
        args = list(CFG["args"]) + ["--dump-logits", str(logits)]
        log = folder / "engine.log"
        engine = StrataEngine(str(exe), args, cwd=CFG["cwd"], log=str(log), env=env)
        item = {
            "label": label,
            "exe": str(exe),
            "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            "startup_info": engine.info,
            "fresh_input_tokens": len(ids),
            "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        plan["arms"].append(item)
        (OUT / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print("ABA_START", label, engine.info, flush=True)
        try:
            t0 = time.perf_counter()
            generated = [t for t in engine.generate(ids, 1, {"temperature": 0}, threading.Event()) if t is not None]
            item.update(engine.last)
            item["wall_s"] = time.perf_counter() - t0
            item["output_ids"] = generated
            item["logits_sha256"] = hashlib.sha256(logits.read_bytes()).hexdigest()
            item["logits_bytes"] = logits.stat().st_size
            item["engine_log"] = str(log)
            item["exit"] = "completed"
        except BaseException as exc:
            item["exit"] = "failed"
            item["error"] = repr(exc)
            raise
        finally:
            engine.close()
            item["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (OUT / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print("ABA_DONE", label, item.get("prompt_ms"), item.get("logits_sha256"), flush=True)
    plan["output_ids_identical"] = plan["arms"][0]["output_ids"] == plan["arms"][1]["output_ids"] == plan["arms"][2]["output_ids"]
    plan["logits_bitwise_identical"] = (
        plan["arms"][0]["logits_sha256"] == plan["arms"][1]["logits_sha256"] == plan["arms"][2]["logits_sha256"]
        and plan["arms"][0]["logits_bytes"] == plan["arms"][1]["logits_bytes"] == plan["arms"][2]["logits_bytes"]
    )
    plan["reference_spread_pct"] = (
        abs(plan["arms"][0]["prompt_ms"] - plan["arms"][2]["prompt_ms"])
        / ((plan["arms"][0]["prompt_ms"] + plan["arms"][2]["prompt_ms"]) / 2) * 100
    )
    plan["status"] = "completed"
except BaseException as exc:
    plan["status"] = "failed"
    plan["error"] = repr(exc)
    raise
finally:
    phase = "cleanup"
    telemetry_stop.set()
    watcher.join(timeout=12)
    plan["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print("ABA_STATUS", plan["status"], flush=True)

