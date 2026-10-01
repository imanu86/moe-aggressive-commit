"""Ricalcola i riepiloghi dalle corse complete conservate qui (solo libreria standard)."""
from datetime import datetime
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent
REQUEST = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read .*?, (\d+) generated in (\d+) ms .*?drafts accepted (\d+) of (\d+)")
STAGE = re.compile(r"stage 0: (\d+) windows; per window: wait for the GPU ([\d.]+) ms, pool \+ plan ([\d.]+) ms, host staging ([\d.]+) ms, commit ([\d.]+) ms")
summary = {}
for name in ("A1_sota", "B_v3", "A2_sota", "C2_sota_fissa5000", "D_v3_fissa5000"):
    folder = ROOT / name
    if not (folder / "results.jsonl").exists():
        continue
    result = json.loads((folder / "esito.json").read_text(encoding="utf-8"))
    if result["status"] != "completed":
        continue
    rows = [json.loads(line) for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [row for row in rows if not row["riscaldamento"]]
    log = (folder / "strata.log").read_text(encoding="utf-8", errors="replace")
    calls = [list(map(int, match)) for match in REQUEST.findall(log) if int(match[3]) > 100]
    assert len(rows) == len(calls) == 2
    passes = sum(gen - accepted for _, _, _, gen, _, accepted, _ in calls)
    verified_rows = sum(gen - accepted + offered for _, _, _, gen, _, accepted, offered in calls)
    decode_ms = sum(call[4] for call in calls)
    stages = STAGE.findall(log)
    cpu = [json.loads(line) for line in (folder / "cpu.jsonl").read_text(encoding="utf-8").splitlines()][1:]
    other = lambda sample: sum(v for k, v in sample["proc"].items() if k.lower() not in ("strata.exe", "llama-server.exe", "system idle process"))
    cpu_summary = {"valid_cpu_samples": len(cpu), "other_cpu_mean_cores": statistics.mean(map(other, cpu)),
                   "other_cpu_max_cores": max(map(other, cpu)), "ram_min_gb": min(s["ram_disp_gb"] for s in cpu)}
    intervals = []
    for row in rows:
        motor = row["motore"]
        start = motor["time"] + motor["prompt_ms"] / 1000
        intervals.append((start, start + motor["decode_ms"] / 1000))
    date = datetime.fromtimestamp(rows[0]["motore"]["time"]).date()
    decode_samples = [s for s in cpu if any(start <= datetime.fromisoformat(f"{date}T{s['t']}").timestamp() <= end
                                          for start, end in intervals)]
    cpu_summary.update(decode_samples=len(decode_samples),
                       decode_other_cpu_mean_cores=statistics.mean(map(other, decode_samples)) if decode_samples else None)
    (folder / "cpu_riassunto.json").write_text(json.dumps(cpu_summary, indent=2), encoding="utf-8")
    metrics_path = folder / "metrics_initial.json"
    if not metrics_path.exists():
        metrics_path = folder / "metrics_avvio.json"
    engine = json.loads(metrics_path.read_text(encoding="utf-8"))["engine"]
    summary[name] = {"decode_tps": result["summary"]["decode_aggregato_tps"],
                     "prefill_cold_tps": rows[0]["prefill_tps_motore"], "ttft_cold_s": rows[0]["ttft_s"],
                     "ms_per_verified_row": decode_ms / verified_rows,
                     "ms_per_window": decode_ms / passes, "tokens_per_window": 2048 / passes,
                     "rows_per_window": verified_rows / passes,
                     "initial_cache": {k: engine.get(k) for k in ("expert_slots", "expert_cache_mib", "vram_free_mib")},
                     "stage_last_cumulative": dict(zip(("windows", "gpu_ms", "pool_plan_ms", "staging_ms", "commit_ms"), map(float, stages[-1]))),
                     "cpu": cpu_summary,
                     "output_sha256": [row["impronta_sha256"] for row in rows]}
if "C2_sota_fissa5000" in summary and "D_v3_fissa5000" in summary:
    base, candidate = summary["C2_sota_fissa5000"], summary["D_v3_fissa5000"]
    summary["fixed_comparison"] = {
        "same_cache_slots": base["initial_cache"]["expert_slots"] == candidate["initial_cache"]["expert_slots"],
        "same_generated_output": base["output_sha256"] == candidate["output_sha256"],
        "decode_gain_pct": (candidate["decode_tps"] / base["decode_tps"] - 1) * 100,
        "verified_row_cost_change_pct": (candidate["ms_per_verified_row"] / base["ms_per_verified_row"] - 1) * 100}
(ROOT / "confronto.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
