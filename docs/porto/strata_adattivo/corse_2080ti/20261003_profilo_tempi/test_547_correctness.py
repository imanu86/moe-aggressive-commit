"""Compare 32 greedy output IDs for baseline and #547 at 131k fresh input."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
DAILY = Path(r"D:\ds4_work\strata\Strata")
SOURCE = DAILY / "build-0138-daily" / "source"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(DAILY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, r"C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75")
from serve.server import StrataEngine

CFG = json.loads((DAILY / "strata-2080ti-sota.json").read_text(encoding="utf-8-sig"))
FIXTURE = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261003_allineamento038_grid_rimossa\131072-fresh.ids.json")
ids = json.loads(FIXTURE.read_text(encoding="utf-8"))
assert len(ids) == 131072
EXES = [
    ("A", Path(CFG["exe"])),
    ("B", HERE / "build-547" / "strata.exe"),
]
OUT = HERE / "correctness-547"
OUT.mkdir(exist_ok=False)
env = {k: v for k, v in os.environ.items() if not k.startswith("STRATA_")}
env.update(CFG.get("env", {}))
env["PATH"] = os.pathsep.join(CFG.get("lib_dirs", []) + [env.get("PATH", "")])
report = {
    "status": "running",
    "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "protocol": "fresh 131072 input; daily config; 32 greedy output tokens; baseline vs PR547 candidate",
    "binary_sha256": {name: hashlib.sha256(exe.read_bytes()).hexdigest() for name, exe in EXES},
    "input_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
    "arms": [],
}
(OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
try:
    for label, exe in EXES:
        folder = OUT / label
        folder.mkdir()
        log = folder / "engine.log"
        engine = StrataEngine(str(exe), list(CFG["args"]), cwd=CFG["cwd"], log=str(log), env=env)
        row = {"label": label, "startup_info": engine.info, "input_tokens": len(ids)}
        report["arms"].append(row)
        print("START", label, engine.info, flush=True)
        try:
            t0 = time.perf_counter()
            row["output_ids"] = [
                token for token in engine.generate(ids, 32, {"temperature": 0}, threading.Event())
                if token is not None
            ]
            row.update(engine.last)
            row["elapsed_s"] = time.perf_counter() - t0
            row["engine_log"] = str(log)
            row["finish"] = engine.last.get("finish")
            row["status"] = "completed"
        finally:
            engine.close()
        (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("DONE", label, row.get("prompt_ms"), len(row.get("output_ids", [])), flush=True)
    report["output_ids_identical"] = report["arms"][0]["output_ids"] == report["arms"][1]["output_ids"]
    report["status"] = "completed"
except BaseException as exc:
    report["status"] = "failed"
    report["error"] = repr(exc)
    raise
finally:
    report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("STATUS", report["status"], "IDS_IDENTICAL", report.get("output_ids_identical"), flush=True)

