"""Measure actual 0.1.38 Daily phase timings at 131k and 250k fresh input."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import threading
import time

DAILY = Path(r"D:\ds4_work\strata\Strata")
EVIDENCE = Path(__file__).resolve().parent
SOURCE = DAILY / "build-0138-daily" / "source"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(DAILY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, r"C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75")
import validate_model as V
from serve.server import StrataEngine

CFG = json.loads((DAILY / "strata-2080ti-sota.json").read_text(encoding="utf-8-sig"))
FIXTURE = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261003_allineamento038_grid_rimossa")
EXE = Path(CFG["exe"])
env = {k: v for k, v in os.environ.items() if not k.startswith("STRATA_")}
env.update(CFG.get("env", {}))
env.update(STRATA_PREFILL_TIMING="1", STRATA_DECODE_TIMING="1", STRATA_SPLIT_TIMING="1")
env["PATH"] = os.pathsep.join(CFG.get("lib_dirs", []) + [env.get("PATH", "")])
result = {
    "status": "running",
    "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "hardware": "modified 22 GB RTX 2080 Ti; Ryzen 7 5800X",
    "binary": str(EXE),
    "binary_sha256": hashlib.sha256(EXE.read_bytes()).hexdigest(),
    "config_sha256": hashlib.sha256((DAILY / "strata-2080ti-sota.json").read_bytes()).hexdigest(),
    "args": CFG["args"],
    "purpose": "profile existing phase timers; fresh input; no synthetic load",
    "requests": [],
}
(EVIDENCE / "plan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

for depth, fixture in [(131072, "131072-fresh.ids.json"), (250000, "250000-fresh.ids.json")]:
    ids = json.loads((FIXTURE / fixture).read_text(encoding="utf-8"))
    assert len(ids) == depth, (depth, len(ids))
    log = EVIDENCE / f"{depth}.engine.log"
    engine = StrataEngine(str(EXE), list(CFG["args"]), cwd=CFG["cwd"], log=str(log), env=env)
    row = {"depth_tokens": depth, "input_fixture": str(FIXTURE / fixture), "startup_info": engine.info}
    result["requests"].append(row)
    try:
        t0 = time.perf_counter()
        generated = [t for t in engine.generate(ids, 32, {"temperature": 0}, threading.Event()) if t is not None]
        row.update(engine.last)
        row["client_wall_s"] = time.perf_counter() - t0
        row["output_ids"] = generated
        row["exit"] = "completed"
    except BaseException as exc:
        row["exit"] = "failed"
        row["error"] = repr(exc)
        raise
    finally:
        engine.close()
        row["engine_log"] = str(log)
        (EVIDENCE / "plan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("PROFILE_REQUEST_DONE", depth, row.get("prompt_ms"), row.get("decode_ms"), flush=True)

result["status"] = "completed"
result["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
(EVIDENCE / "plan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("PROFILE_COMPLETE", EVIDENCE, flush=True)
