"""Continuation decode profile for the two fixed tasks not completed by the preserved first run.

Dry-run is the default. Task 1's output and failed prompt-count gate remain in
profile-output and are not repeated. Structured-output preprocessing matches the
server's prepare_format() injection exactly. This is not an A/B comparison or a
broad quality claim. Prompt code is never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / ".codex_runs" / "20261004_decode_real"
FIXTURES = LAB / "fixtures"
DAILY = Path(r"D:\ds4_work\strata\Strata")
SOURCE = DAILY / "build-0138-daily" / "source"
SERVER = SOURCE / "serve" / "server.py"
FRONTEND = SOURCE / "serve" / "frontend.py"
TOKENIZER_IMPL = SOURCE / "tools" / "strata_tokenizer.py"
UPSTREAM_BENCH = DAILY / "bench" / "results" / "2026-09-30-community-rtx-5090" / "benchmark.py"
STRUCTURED_HELPER = SOURCE / "serve" / "structured.py"
CONFIG = DAILY / "strata-2080ti-sota.json"
EXE = DAILY / "build-0138-daily" / "strata.exe"
PYTHON = DAILY / ".venv" / "Scripts" / "python.exe"
PORT = 18132
DEADLINE_S = 480
WORK_S = 390
CLEANUP_S = 90
STARTUP_CAP_S = 360
TASK_FILES = ("code-trace-9k.json", "archive-reading-20k.json")
EXPECTED_EXE = "a17d0dd5362bc35420ca9ef3d1a8cf8c014dafbb3aea189c6c664fe7930e8674"
EXPECTED = {
    "reasoning-recurrence-4k": {"sequence": [68, 41, 43, 88, 61, 63, 108, 81], "sum": 553, "last": 81},
    "pure-code-trace-9k": {"hits": 2, "misses": 12,
                            "evicted": ["B", "C", "A", "D", "B", "E", "A", "C", "D"],
                            "final_lru_to_mru": ["B", "F", "E"]},
}
DECODE_RE = re.compile(
    r"strata decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window = "
    r"verify ([\d.]+) \(GPU-reach wait ([\d.]+) \+ per-layer host ([\d.]+) \[plan ([\d.]+) actq ([\d.]+) "
    r"jobs ([\d.]+) CPU ([\d.]+)\] \+ stage ([\d.]+)\) \+ commit/emit ([\d.]+) \+ draft ([\d.]+); "
    r"per layer-window: CPU experts ([\d.]+) \(([\d.]+) entries\), VRAM hits ([\d.]+), PCIe ([\d.]+)"
)
SPLIT_RE = re.compile(
    r"strata serve: stage (\d+): (\d+) windows; per window: wait for the GPU ([\d.]+) ms, "
    r"pool \+ plan ([\d.]+) ms, host staging ([\d.]+) ms, commit ([\d.]+) ms"
)
PROMPT_RE = re.compile(
    r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms "
    r"\(([\d.]+) tok/s\), (\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\), "
    r"drafts accepted (\d+) of (\d+), (\d+) checkpoints"
)
SUFFIX_RE = re.compile(r"strata serve: suffix drafts: (\d+) windows, (\d+) of (\d+) drafts accepted")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_fixture_files() -> list[dict]:
    rows = []
    for name in TASK_FILES:
        path = FIXTURES / name
        row = json.loads(path.read_text(encoding="utf-8"))
        require(isinstance(row.get("prompt"), str) and row["prompt"], f"Bad fixture prompt: {name}")
        require(row.get("reasoning_effort") == "high" and row.get("temperature") == 0,
                f"Fixture sampling changed: {name}")
        rows.append({**row, "fixture_path": path, "fixture_sha256": sha256(path)})
    require([r["id"] for r in rows] == ["pure-code-trace-9k", "migration-closeout-reading-20k"],
            "Remaining fixture order/identity changed")
    require([r["actual_prompt_tokens"] for r in rows] == [9216, 20480],
            "Frozen remaining fixture targets changed")
    require(rows[0].get("oracle") == EXPECTED[rows[0]["id"]], "Code-trace oracle changed")
    require("def access(keys, capacity=3):" in rows[0]["prompt"] and "access(['A', 'B', 'C', 'A', 'D', 'B', 'E', 'A', 'C', 'D', 'E', 'B', 'F', 'E'], capacity=3)" in rows[0]["prompt"],
            "Expected fixed LRU trace missing from code fixture")
    require(rows[1].get("manual_evidence", {}).get("route") == "Cedar-2", "Manual evidence changed")
    return rows


def tokenizer_and_template(config: dict):
    sys.path[:0] = [str(SOURCE), str(SOURCE / "tools")]
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate, openai_to_messages
    from serve.structured import prepare_format

    tokenizer_dir = Path(config["tokenizer"])
    vocab = json.loads((tokenizer_dir / "vocab.json").read_text(encoding="utf-8"))
    tokens = [None] * len(vocab)
    for token, idx in vocab.items():
        tokens[idx] = token
    tokenizer = Tokenizer(tokens, (tokenizer_dir / "merges.txt").read_text(encoding="utf-8").splitlines(),
                          json.loads((tokenizer_dir / "token_type.json").read_text(encoding="utf-8")))
    template = ChatTemplate(tokenizer_dir / "chat_template.jinja")
    return tokenizer, template, openai_to_messages, prepare_format


def request_body(task: dict) -> dict:
    body = {"model": "strata", "messages": [{"role": "user", "content": task["prompt"]}],
            "temperature": 0, "reasoning_effort": "high", "max_tokens": task["max_tokens"],
            "stream": True, "stream_options": {"include_usage": True}}
    if task.get("response_format"):
        body["response_format"] = task["response_format"]
    return body


def count_request(task: dict, tokenizer, template, openai_to_messages, prepare_format) -> int:
    body = request_body(task)
    messages, tools, kwargs = openai_to_messages(body)
    messages, _validator = prepare_format(body.get("response_format"), messages)
    return len(tokenizer.encode(template.render(messages, tools, **kwargs), parse_special=True))


def exact_source_paths(config: dict) -> list[Path]:
    tokenizer_dir = Path(config["tokenizer"])
    profile = Path(config["args"][config["args"].index("--expert-profile") + 1])
    return [EXE, CONFIG, profile, SERVER, FRONTEND, TOKENIZER_IMPL, UPSTREAM_BENCH, STRUCTURED_HELPER,
            tokenizer_dir / "chat_template.jinja", tokenizer_dir / "vocab.json",
            tokenizer_dir / "merges.txt", tokenizer_dir / "token_type.json"]


def make_plan(tasks: list[dict], config: dict, hashes: dict, deadline: int) -> dict:
    return {
        "purpose": "One-process Daily-default decode profile continuation over tasks 2 and 3",
        "status": "planned", "scope": "task 1 raw output and failed prompt-count gate preserved in prior output and not repeated; tasks 2-3 only; no A/B or general quality claim",
        "protocol": "Upstream fresh-prompt serial benchmark pattern: exact ChatTemplate token counts after openai_to_messages and structured.prepare_format injection, local loopback API, temp=0, fixed complete prompts, usage/TTFT plus native logs.",
        "executable": str(EXE), "executable_sha256": hashes["exe"], "expected_executable_sha256": EXPECTED_EXE,
        "daily_config": str(CONFIG), "daily_config_sha256": hashes["config"],
        "config_clone": "created only inside output directory; clone changes only engine log path and adds DECODE_TIMING/SPLIT_TIMING=1; CLI binds 127.0.0.1:18132",
        "profile": config["args"][config["args"].index("--expert-profile") + 1],
        "profile_sha256": hashes["profile"], "helpers_sha256": hashes["helpers"],
        "fixture_hashes": {t["id"]: t["fixture_sha256"] for t in tasks},
        "sampling": {"reasoning_effort": "high (mapped by this server's frontend to template effort xhigh)",
                     "temperature": 0, "thinking": True, "repeats": 1, "arms": ["profile"]},
        "fixed_tasks": [{"id": t["id"], "kind": t["kind"], "target_prompt_tokens": t["target_prompt_tokens"],
                         "fixture_declared_prompt_tokens": t["actual_prompt_tokens"],
                         "actual_prompt_tokens": t["effective_prompt_tokens"], "max_tokens": t["max_tokens"],
                         "response_format": t.get("response_format"), "fixture_sha256": t["fixture_sha256"],
                         "oracle": t.get("oracle"), "manual_evidence": t.get("manual_evidence")}
                        for t in tasks],
        "expected_runtime_policy": {"context": 262144, "kv": "int8", "kv_resident": 32768,
                                    "expert_cache": "auto from Daily config", "elastic": True,
                                    "cli_spec": 4, "actual_spec_and_mtp_policy": "record actual /v1/status; do not infer T as draft count",
                                    "qsa_prefill_multi": "Daily config value", "trace_dump_verify_profile": "absent",
                                    "only_added_engine_env": ["STRATA_DECODE_TIMING=1", "STRATA_SPLIT_TIMING=1"]},
        "timing_capture": {"native_per_request": ["prompt_ms", "decode_ms", "drafts accepted/offered total", "decode timing summary", "GPU stage profile", "suffix draft line", "expert-cache hits/lookups"],
                            "split_stage_lines": "cumulative per-window averages; preserve snapshots and compute any per-task delta as (avg_after*windows_after - avg_before*windows_before)/(window_delta), never subtract averages directly",
                            "draft_semantics": "native accepted/offered include MTP+suffix; subtract suffix accepted/offered only when the matching suffix line exists; label the remainder MTP-only",
                            "residual": "record decode_ms minus reported verify+commit+draft bucket totals as unbucketed residual; do not attribute it to apply-pending/adapt/elastic without separate counters"},
        "oracle_policy": {"reasoning_and_code_trace": "parse JSON and compare exact expected fields; code in prompt is fixed input and model output is never executed",
                          "archive_reading": "preserve complete answer for manual review; no automated content PASS"},
        "server": {"source": str(SERVER), "source_sha256": hashes["server"],
                   "frontend": str(FRONTEND), "frontend_sha256": hashes["frontend"],
                   "structured_output_helper": str(STRUCTURED_HELPER),
                   "structured_output_helper_sha256": hashes["structured"],
                   "upstream_benchmark_reference": str(UPSTREAM_BENCH), "upstream_benchmark_sha256": hashes["bench"]},
        "bounds": {"hard_deadline_seconds": deadline, "work_seconds": WORK_S,
                   "cleanup_reserve_seconds": CLEANUP_S, "startup_cap_seconds": STARTUP_CAP_S,
                   "cleanup_scope": "only own server/engine PIDs with captured creation times"},
        "no_reused_history": True, "no_artificial_load": True, "no_model_generated_code_execution": True,
    }


def parse_native(lines: list[str]) -> dict:
    raw = [line.rstrip("\r\n") for line in lines if line.strip()]
    decode_matches = [DECODE_RE.search(line) for line in raw if DECODE_RE.search(line)]
    prompt_matches = [PROMPT_RE.search(line) for line in raw if PROMPT_RE.search(line)]
    suffix_matches = [SUFFIX_RE.search(line) for line in raw if SUFFIX_RE.search(line)]
    decode = decode_matches[0] if len(decode_matches) == 1 else None
    prompt = prompt_matches[0] if len(prompt_matches) == 1 else None
    suffix = suffix_matches[0] if len(suffix_matches) == 1 else None
    split = []
    for line in raw:
        m = SPLIT_RE.search(line)
        if m:
            split.append({"stage": int(m.group(1)), "cumulative_windows": int(m.group(2)),
                          "avg_wait_gpu_ms_cumulative": float(m.group(3)),
                          "avg_pool_plan_ms_cumulative": float(m.group(4)),
                          "avg_host_stage_ms_cumulative": float(m.group(5)),
                          "avg_commit_ms_cumulative": float(m.group(6)), "raw": line})
    decode_values = None
    if decode:
        names = ("windows", "avg_T_including_base_token", "tokens_per_window", "avg_window_ms", "verify_ms_window",
                 "gpu_reach_wait_ms_window", "per_layer_host_ms_window", "plan_ms_window", "actq_ms_window",
                 "jobs_ms_window", "cpu_ms_window", "stage_ms_window", "commit_emit_ms_window", "draft_ms_window",
                 "cpu_experts_per_layer_window", "entries_per_layer_window", "vram_hits_per_layer_window", "pcie_per_layer_window")
        values = decode.groups()
        decode_values = {name: int(value) if name == "windows" else float(value) for name, value in zip(names, values)}
        covered = decode_values["windows"] * (decode_values["verify_ms_window"] + decode_values["commit_emit_ms_window"] + decode_values["draft_ms_window"])
        decode_values["unbucketed_residual_ms_estimate"] = None  # joined with request-level decode_ms below
        decode_values["reported_buckets_ms_estimate"] = covered
    prompt_values = None
    if prompt:
        prompt_values = {"prompt_tokens": int(prompt.group(1)), "reused_tokens": int(prompt.group(2)),
                         "read_tokens": int(prompt.group(3)), "prompt_ms": float(prompt.group(4)),
                         "prompt_tok_s": float(prompt.group(5)), "generated_tokens": int(prompt.group(6)),
                         "decode_ms": float(prompt.group(7)), "decode_tok_s": float(prompt.group(8)),
                         "drafts_accepted_total_mtp_plus_suffix": int(prompt.group(9)),
                         "drafts_offered_total_mtp_plus_suffix": int(prompt.group(10)),
                         "checkpoints": int(prompt.group(11))}
        if decode_values:
            prompt_values["decode_timing_unbucketed_residual_ms_estimate"] = (
                prompt_values["decode_ms"] - decode_values["reported_buckets_ms_estimate"])
            decode_values["unbucketed_residual_ms_estimate"] = prompt_values["decode_timing_unbucketed_residual_ms_estimate"]
    suffix_values = ({"found": True, "windows": int(suffix.group(1)), "drafts_accepted_suffix": int(suffix.group(2)),
                      "drafts_offered_suffix": int(suffix.group(3))} if suffix else
                     {"found": False, "windows": None, "drafts_accepted_suffix": None,
                      "drafts_offered_suffix": None, "interpretation": "unknown until complete stderr summary is observed"})
    if prompt_values and suffix:
        prompt_values["drafts_accepted_mtp_only"] = prompt_values["drafts_accepted_total_mtp_plus_suffix"] - suffix_values["drafts_accepted_suffix"]
        prompt_values["drafts_offered_mtp_only"] = prompt_values["drafts_offered_total_mtp_plus_suffix"] - suffix_values["drafts_offered_suffix"]
    gpu_stages = [line for line in raw if line.startswith("strata decode GPU stages (ms/window):")]
    return {"raw_lines": raw, "prompt_summary": prompt_values, "decode_timing": decode_values,
            "suffix_drafts": suffix_values, "gpu_stage_profile_raw": gpu_stages,
            "split_stage_cumulative_snapshots": split,
            "decode_timing_found": decode_values is not None, "decode_timing_count": len(decode_matches),
            "prompt_summary_found": prompt_values is not None, "prompt_summary_count": len(prompt_matches),
            "suffix_summary_count": len(suffix_matches)}


def wait_native_log(path: Path, start_offset: int, timeout: float = 5.0) -> bytes:
    deadline = time.monotonic() + timeout
    previous_size = -1; stable = 0
    latest = b""
    while time.monotonic() < deadline:
        if path.exists():
            latest = path.read_bytes()[start_offset:]
            parsed = parse_native(latest.decode("utf-8", errors="replace").splitlines())
            size = len(latest)
            if size == previous_size:
                stable += 1
            else:
                stable = 0
            previous_size = size
            if parsed["prompt_summary_found"] and parsed["decode_timing_found"] and stable >= 2:
                return latest
        time.sleep(0.25)
    return latest


def stage_delta(before: dict[int, dict], after: list[dict]) -> list[dict]:
    result = []
    for cur in after:
        prev = before.get(cur["stage"])
        if not prev:
            continue
        dw = cur["cumulative_windows"] - prev["cumulative_windows"]
        item = {"stage": cur["stage"], "window_delta": dw,
                "basis": "weighted cumulative-average difference; approximate because printed averages are rounded"}
        for field, output in (("avg_wait_gpu_ms_cumulative", "wait_gpu_ms_per_window"),
                              ("avg_pool_plan_ms_cumulative", "pool_plan_ms_per_window"),
                              ("avg_host_stage_ms_cumulative", "host_stage_ms_per_window"),
                              ("avg_commit_ms_cumulative", "commit_ms_per_window")):
            item[output] = ((cur[field] * cur["cumulative_windows"] - prev[field] * prev["cumulative_windows"]) / dw
                            if dw > 0 else None)
        result.append(item)
    return result


def get_json(url: str, timeout: float = 8) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, value: dict, timeout: float = 15) -> dict:
    body = json.dumps(value).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_tree(server_pid: int, owned: dict[int, float]) -> None:
    try:
        parent = __import__("psutil").Process(server_pid)
        for child in parent.children(recursive=True):
            try:
                owned[child.pid] = child.create_time()
            except __import__("psutil").Error:
                pass
    except __import__("psutil").Error:
        pass


def record_owned(server_pid: int, owned: dict[int, float], path: Path, phase: str) -> None:
    collect_tree(server_pid, owned)
    psutil = __import__("psutil")
    rows = []
    for pid, born in sorted(owned.items()):
        try:
            p = psutil.Process(pid)
            if abs(p.create_time() - born) >= 0.02:
                continue
            with p.oneshot():
                rows.append({"pid": pid, "create_time": born, "name": p.name(), "status": p.status(),
                             "cpu_times": tuple(p.cpu_times()), "memory_info_rss": p.memory_info().rss,
                             "cmdline": p.cmdline()})
        except psutil.Error:
            continue
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = []
    existing.append({"timestamp_utc": datetime.now(timezone.utc).isoformat(), "phase": phase,
                     "processes": rows})
    atomic_json(path, existing)


def owned_process_exists(pid: int, created: float) -> bool:
    psutil = __import__("psutil")
    try:
        p = psutil.Process(pid)
        return abs(p.create_time() - created) < 0.02 and p.is_running()
    except psutil.Error:
        return False


def stop_owned(proc: subprocess.Popen, server_birth: float, owned: dict[int, float], base_url: str,
               graceful_unload: bool, deadline: float) -> list[dict]:
    psutil = __import__("psutil")
    actions = []
    collect_tree(proc.pid, owned)
    if graceful_unload and proc.poll() is None:
        try:
            timeout = max(1.0, min(12.0, deadline - time.monotonic() - 70.0))
            result = post_json(base_url + "/v1/unload", {}, timeout=timeout)
            actions.append({"action": "api_unload", "result": result})
        except Exception as exc:
            actions.append({"action": "api_unload", "error": repr(exc)})
    # Give the server's StrataEngine.close() the cleanup reserve; retain PID plus creation time before fallback.
    if graceful_unload:
        until = min(deadline - 15.0, time.monotonic() + 55.0)
        while time.monotonic() < until and proc.poll() is None:
            collect_tree(proc.pid, owned)
            live_children = [pid for pid, born in owned.items()
                             if pid != proc.pid and owned_process_exists(pid, born)]
            if not live_children:
                break
            time.sleep(0.5)
    # Every fallback signal is scoped to this invocation's process tree and verified creation time.
    for pid, born in list(owned.items()):
        if pid == proc.pid:
            continue
        if owned_process_exists(pid, born):
            try:
                p = psutil.Process(pid)
                p.terminate()
                actions.append({"action": "terminate_owned_child", "pid": pid, "create_time": born})
            except psutil.Error:
                pass
    child_wait_deadline = min(deadline - 5.0, time.monotonic() + 8.0)
    for pid, born in list(owned.items()):
        if pid == proc.pid:
            continue
        if owned_process_exists(pid, born):
            try:
                p = psutil.Process(pid)
                remaining = child_wait_deadline - time.monotonic()
                if remaining > 0:
                    p.wait(timeout=remaining)
                else:
                    raise psutil.TimeoutExpired(0, pid)
            except psutil.TimeoutExpired:
                try:
                    if owned_process_exists(pid, born):
                        psutil.Process(pid).kill()
                        actions.append({"action": "kill_owned_child", "pid": pid, "create_time": born})
                except psutil.Error:
                    pass
            except psutil.Error:
                pass
    if proc.poll() is None and owned_process_exists(proc.pid, server_birth):
        proc.terminate()
        try:
            proc.wait(timeout=max(1, min(8, deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            if owned_process_exists(proc.pid, server_birth):
                proc.kill()
                actions.append({"action": "kill_owned_server", "pid": proc.pid, "create_time": server_birth})
    return actions


def stream_request(body: dict, url: str) -> dict:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    started = time.monotonic(); first_text = None; chunks = []; contents = []; thoughts = []; finish = None
    with urllib.request.urlopen(request, timeout=600) as response:
        for line in response:
            if not line.startswith(b"data: "):
                continue
            data = line[6:].strip()
            if data == b"[DONE]":
                break
            chunk = json.loads(data)
            chunks.append(chunk)
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            for choice in chunk.get("choices", []):
                delta = choice.get("delta") or {}
                content = delta.get("content") or ""
                thought = delta.get("reasoning_content") or delta.get("reasoning") or ""
                if content or thought:
                    if first_text is None:
                        first_text = time.monotonic() - started
                    contents.append(content); thoughts.append(thought)
                finish = choice.get("finish_reason") or finish
    return {"chunks": chunks, "content": "".join(contents), "reasoning": "".join(thoughts),
            "finish_reason": finish, "usage": locals().get("usage", {}),
            "client_ttft_seconds": first_text, "client_wall_seconds": time.monotonic() - started,
            "request_sha256": hashlib.sha256(payload).hexdigest()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--exe", type=Path, default=EXE)
    ap.add_argument("--expected-exe-sha256", default=EXPECTED_EXE)
    ap.add_argument("--out", type=Path, default=LAB / "profile-output-v2")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--deadline-seconds", type=int, default=DEADLINE_S)
    ap.add_argument("--run", action="store_true", help="start the isolated local server; default is CPU-only planning")
    args = ap.parse_args()
    args.config = args.config.resolve(); args.exe = args.exe.resolve(); args.out = args.out.resolve()
    require(args.deadline_seconds == DEADLINE_S, "This continuation has a fixed 480-second hard cap")
    require(args.port == PORT, "This profile is pinned to loopback port 18132")
    require(args.config == CONFIG.resolve() and args.exe == EXE.resolve(), "Only the reviewed Daily config/binary is supported")
    require(not args.out.exists(), "Refusing to overwrite an existing output directory")
    cfg_bytes = CONFIG.read_bytes(); config = json.loads(cfg_bytes.decode("utf-8-sig"))
    tasks = load_fixture_files()
    tokenizer, template, openai_to_messages, prepare_format = tokenizer_and_template(config)
    for task in tasks:
        task["effective_prompt_tokens"] = count_request(task, tokenizer, template, openai_to_messages, prepare_format)
    require(sha256(EXE).casefold() == args.expected_exe_sha256.casefold(), "Daily executable SHA-256 mismatch")
    require(sha256(EXE).casefold() == EXPECTED_EXE, "Harness pinned executable SHA-256 mismatch")
    require(PORT >= 1024 and len(tasks) == 2, "Invalid continuation profile bounds")
    env_cfg = dict(config.get("env", {}))
    forbidden_daily_env = ("TRACE", "VERIFY_PROFILE", "DUMP_FIRST_LOGITS", "IQ_MT_MIN",
                           "STRATA_DECODE_TIMING", "STRATA_SPLIT_TIMING")
    require(not any(any(flag in key.upper() for flag in forbidden_daily_env) for key in env_cfg),
            "Daily config contains disallowed trace/verify-profile flags")
    hashes = {"exe": sha256(EXE), "config": hashlib.sha256(cfg_bytes).hexdigest(),
              "profile": sha256(Path(config["args"][config["args"].index("--expert-profile") + 1])),
              "helpers": {str(p): sha256(p) for p in (FRONTEND, TOKENIZER_IMPL, UPSTREAM_BENCH, STRUCTURED_HELPER)},
              "server": sha256(SERVER), "frontend": sha256(FRONTEND), "structured": sha256(STRUCTURED_HELPER),
              "bench": sha256(UPSTREAM_BENCH)}
    helper_paths = (SERVER, FRONTEND, TOKENIZER_IMPL, UPSTREAM_BENCH, STRUCTURED_HELPER,
                    Path(config["tokenizer"]) / "chat_template.jinja", Path(config["tokenizer"]) / "vocab.json",
                    Path(config["tokenizer"]) / "merges.txt", Path(config["tokenizer"]) / "token_type.json")
    hashes["all_helpers"] = {str(p): sha256(p) for p in helper_paths}
    plan = make_plan(tasks, config, hashes, args.deadline_seconds)
    plan["harness_sha256"] = sha256(Path(__file__))
    expected_plan_hash = json.loads((LAB / "profile-plan-v2.json").read_text(encoding="utf-8"))["harness_sha256"]
    require(plan["harness_sha256"] == expected_plan_hash, "Harness SHA differs from reviewed plan")
    if not args.run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    import psutil
    require(psutil.virtual_memory().available >= 16 * 2**30, "Available RAM below 16 GiB")
    forbidden = {"strata.exe", "strata-session-qsa.exe", "strata-exact-small.exe", "llama-server.exe"}
    active = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info.get("name") or "").casefold()
            if name in forbidden or name.startswith("strata"):
                active.append({"pid": p.info["pid"], "name": name})
        except psutil.Error:
            pass
    require(not active, f"Another engine is active: {active!r}")
    with socket.socket() as s:
        s.bind(("127.0.0.1", PORT))

    args.out.mkdir(parents=True, exist_ok=False)
    clone = json.loads(cfg_bytes.decode("utf-8-sig"))
    clone["env"] = dict(clone.get("env", {}))
    clone["env"].update(STRATA_DECODE_TIMING="1", STRATA_SPLIT_TIMING="1")
    clone["log"] = str(args.out / "native.log")
    clone["port"] = PORT
    run_config = args.out / "run_config.json"
    atomic_json(run_config, clone)
    verify_clone = json.loads(run_config.read_text(encoding="utf-8"))
    require(verify_clone["args"] == config["args"] and verify_clone["lib_dirs"] == config["lib_dirs"] and
            verify_clone["tokenizer"] == config["tokenizer"] and
            verify_clone.get("env", {}) == {**config.get("env", {}),
                                            "STRATA_DECODE_TIMING": "1", "STRATA_SPLIT_TIMING": "1"} and
            all(verify_clone.get(k) == v for k, v in config.items() if k not in ("env", "log", "port")),
            "Run config clone changed fields outside env/log/port")
    plan.update(status="running", run_config=str(run_config), run_config_sha256=sha256(run_config),
                run_config_changes={"log": "output/native.log", "port": PORT,
                                    "added_env": {"STRATA_DECODE_TIMING": "1", "STRATA_SPLIT_TIMING": "1"}})
    atomic_json(args.out / "plan.json", plan)
    state = {"status": "starting", "plan_sha256": sha256(args.out / "plan.json"), "tasks": [],
             "scope": "continuation over tasks 2 and 3 only; previous task 1 output and failed gate preserved; no A/B or general quality claim"}
    atomic_json(args.out / "results.json", state)
    server_log = (args.out / "server.log").open("wb")
    clean_env = {k: v for k, v in os.environ.items() if not k.upper().startswith("STRATA_")}
    clean_env["PYTHONPATH"] = os.pathsep.join([str(SOURCE), str(SOURCE / "tools")] +
                                                 ([clean_env["PYTHONPATH"]] if clean_env.get("PYTHONPATH") else []))
    clean_env["PATH"] = os.pathsep.join(list(config.get("lib_dirs", [])) + [clean_env.get("PATH", "")])
    cmd = [str(PYTHON), "-m", "serve.server", "--engine", "strata", "--config", str(run_config),
           "--host", "127.0.0.1", "--port", str(PORT)]
    si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    server = subprocess.Popen(cmd, cwd=str(DAILY), env=clean_env, stdin=subprocess.DEVNULL,
                              stdout=server_log, stderr=subprocess.STDOUT, startupinfo=si,
                              creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
    server_birth = psutil.Process(server.pid).create_time()
    owned = {server.pid: server_birth}
    start = time.monotonic(); work_deadline = start + WORK_S; hard_deadline = start + DEADLINE_S
    cancel = threading.Event(); deadline_timer = threading.Timer(WORK_S, cancel.set)
    deadline_timer.daemon = True; deadline_timer.start()
    base_url = f"http://127.0.0.1:{PORT}"
    split_previous: dict[int, dict] = {}
    error = None
    try:
        state["status"] = "starting"; atomic_json(args.out / "results.json", state)
        process_log = args.out / "process-tree.json"
        next_process_record = 0.0
        while True:
            require(not cancel.is_set() and time.monotonic() < work_deadline, "Work deadline reached during startup")
            if server.poll() is not None:
                tail = (args.out / "server.log").read_text(encoding="utf-8", errors="replace")[-3000:]
                raise RuntimeError(f"Local server exited during startup ({server.returncode}): {tail}")
            try:
                health = get_json(base_url + "/health", timeout=3)
                if health.get("status") == "ok" and health.get("loaded"):
                    status = get_json(base_url + "/v1/status", timeout=5)
                    break
            except Exception:
                pass
            elapsed = time.monotonic() - start
            if elapsed >= next_process_record:
                record_owned(server.pid, owned, process_log, "startup")
                next_process_record = elapsed + 5.0
            if elapsed > STARTUP_CAP_S:
                raise RuntimeError(f"Startup exceeded {STARTUP_CAP_S}s cap")
            if int(elapsed) % 20 == 0:
                print("STARTUP_WAIT_S", int(elapsed), flush=True)
            time.sleep(1)
        require(sha256(EXE) == hashes["exe"] and hashlib.sha256(CONFIG.read_bytes()).hexdigest() == hashes["config"],
                "Daily executable/config changed during startup")
        state.update(status="running", startup_seconds=time.monotonic() - start, health=health,
                     initial_status=status, runtime_policy={"actual": status,
                         "spec_note": "T includes the base token; actual MTP max=4 means up to 3 drafts."})
        atomic_json(args.out / "results.json", state)
        print("READY", json.dumps({"startup_s": state["startup_seconds"], "status": status}, ensure_ascii=False), flush=True)

        for index, task in enumerate(tasks):
            require(not cancel.is_set() and time.monotonic() < work_deadline, "Work deadline reached before task")
            require({str(p): sha256(p) for p in helper_paths} == hashes["all_helpers"] and
                    sha256(EXE) == hashes["exe"] and sha256(CONFIG) == hashes["config"] and
                    sha256(Path(config["args"][config["args"].index("--expert-profile") + 1])) == hashes["profile"],
                    "Pinned executable/config/profile/server/helper changed before request")
            native_path = args.out / "native.log"
            start_offset = native_path.stat().st_size if native_path.exists() else 0
            task_row = {"index": index, "id": task["id"], "kind": task["kind"],
                        "prompt_tokens_expected": task["effective_prompt_tokens"],
                        "fixture_sha256": task["fixture_sha256"], "status": "running"}
            atomic_json(args.out / f"request-{index + 1}.json", request_body(task))
            print("TASK_START", task["id"], "PROMPT", task["effective_prompt_tokens"], flush=True)
            result_queue: queue.Queue = queue.Queue(maxsize=1)
            worker_error = []
            def capture():
                try:
                    result_queue.put(stream_request(request_body(task), base_url + "/v1/chat/completions"))
                except BaseException as exc:
                    worker_error.append(exc)
                    try: result_queue.put(None, timeout=1)
                    except queue.Full: pass
            worker = threading.Thread(target=capture, daemon=True)
            worker.start()
            streamed = None
            while streamed is None:
                if cancel.is_set() or time.monotonic() >= work_deadline:
                    raise RuntimeError("Work deadline reached during task request")
                if server.poll() is not None:
                    raise RuntimeError(f"Local server exited during task {task['id']}")
                elapsed = time.monotonic() - start
                if elapsed >= next_process_record:
                    record_owned(server.pid, owned, process_log, f"request-{index + 1}")
                    next_process_record = elapsed + 5.0
                try:
                    streamed = result_queue.get(timeout=1)
                except queue.Empty:
                    continue
                if streamed is None:
                    raise RuntimeError(f"HTTP request failed for {task['id']}: {worker_error!r}")
            native_bytes = wait_native_log(native_path, start_offset)
            native_lines = native_bytes.decode("utf-8", errors="replace").splitlines()
            private_dir = args.out / "outputs-private"; private_dir.mkdir(exist_ok=True)
            private_output_path = private_dir / f"task-{index + 1}.json"
            atomic_json(private_output_path, {"id": task["id"], "final": streamed["content"],
                        "reasoning": streamed["reasoning"], "chunks": streamed["chunks"],
                        "native_log_excerpt": native_lines, "capture_stage": "raw persisted before analysis gates"})
            native = parse_native(native_lines)
            metrics = get_json(base_url + "/metrics", timeout=10)
            atomic_json(private_output_path, {"id": task["id"], "final": streamed["content"],
                        "reasoning": streamed["reasoning"], "chunks": streamed["chunks"],
                        "native_log_excerpt": native_lines, "metrics_snapshot": metrics,
                        "capture_stage": "raw request and metrics persisted before analysis gates"})
            metric_request = (metrics.get("requests") or [{}])[0]
            prompt_summary = native["prompt_summary"]
            require(prompt_summary is not None, f"Native prompt summary missing for {task['id']}")
            require(native["prompt_summary_count"] == 1, f"Expected exactly one native prompt summary for {task['id']}")
            require(native["decode_timing_found"], f"Native decode timing summary missing for {task['id']}")
            require(native["decode_timing_count"] == 1, f"Expected exactly one native decode timing summary for {task['id']}")
            require(metrics.get("requests_kept") == index + 1,
                    f"Expected one-to-one server request history through task {task['id']}: {metrics.get('requests_kept')}")
            require(prompt_summary["prompt_tokens"] == prompt_summary["reused_tokens"] + prompt_summary["read_tokens"],
                    f"Native prompt token accounting mismatch for {task['id']}")
            require(prompt_summary["prompt_tokens"] == task["effective_prompt_tokens"],
                    f"Native prompt token count differs from server preprocessing for {task['id']}")
            usage = streamed["usage"]
            require(usage.get("prompt_tokens") == prompt_summary["prompt_tokens"],
                    f"API/native prompt token mismatch for {task['id']}: {usage.get('prompt_tokens')} vs {prompt_summary['prompt_tokens']}")
            require(usage.get("completion_tokens") == prompt_summary["generated_tokens"],
                    f"API/native generated token mismatch for {task['id']}: {usage.get('completion_tokens')} vs {prompt_summary['generated_tokens']}")
            require(metric_request.get("prompt_total") == prompt_summary["prompt_tokens"] and
                    metric_request.get("prompt_tokens") == prompt_summary["prompt_tokens"],
                    f"/metrics/native prompt mismatch for {task['id']}")
            require(metric_request.get("engine_generated") == prompt_summary["generated_tokens"] and
                    metric_request.get("output_tokens") == usage.get("completion_tokens"),
                    f"/metrics/native/API generation mismatch for {task['id']}")
            for key in ("prompt_ms", "decode_ms"):
                metric_time = metric_request.get(key)
                native_time = prompt_summary.get(key)
                require(isinstance(metric_time, (int, float)) and isinstance(native_time, (int, float)) and
                        abs(metric_time - native_time) <= 1.0,
                        f"/metrics/native {key} mismatch >1 ms for {task['id']}: {metric_time} vs {native_time}")
            for metric_key, native_key in (("drafts_accepted", "drafts_accepted_total_mtp_plus_suffix"),
                                           ("drafts_offered", "drafts_offered_total_mtp_plus_suffix")):
                require(metric_request.get(metric_key) == prompt_summary[native_key],
                        f"/metrics/native {metric_key} mismatch for {task['id']}")
            require(metric_request.get("finish") == streamed["finish_reason"] and
                    streamed["finish_reason"] in ("stop", "length"),
                    f"HTTP stream and newest /metrics finish disagree for {task['id']}")
            final = streamed["content"].strip()
            oracle_pass = None; oracle_error = None; parsed = None
            if task["id"] in EXPECTED:
                try:
                    parsed = json.loads(final)
                    require(parsed == EXPECTED[task["id"]], f"Exact oracle mismatch for {task['id']}: {parsed!r}")
                    oracle_pass = True
                except Exception as exc:
                    oracle_pass = False; oracle_error = repr(exc)
            else:
                task_row["manual_review_fields"] = task["manual_evidence"]
            require(streamed["finish_reason"] not in (None, "error"), f"No proper finish reason for {task['id']}")
            timing = prompt_summary
            split_before = {row["stage"]: row for row in split_previous.values()}
            split_after = {row["stage"]: row for row in native["split_stage_cumulative_snapshots"]}
            weighted_delta = stage_delta(split_before, native["split_stage_cumulative_snapshots"])
            split_previous = split_after
            task_row.update({"status": "completed", "max_tokens": task["max_tokens"],
                             "reasoning_effort": "high", "temperature": 0, "finish_reason": streamed["finish_reason"],
                             "client_ttft_seconds": streamed["client_ttft_seconds"],
                             "client_wall_seconds": streamed["client_wall_seconds"],
                             "usage": streamed["usage"], "request_sha256": streamed["request_sha256"],
                             "answer_characters": len(final), "reasoning_characters": len(streamed["reasoning"]),
                             "answer_sha256": hashlib.sha256(final.encode("utf-8")).hexdigest(),
                             "reasoning_sha256": hashlib.sha256(streamed["reasoning"].encode("utf-8")).hexdigest(),
                             "oracle_json_pass": oracle_pass, "oracle_error": oracle_error,
                             "parsed_answer": parsed, "native": native, "http_metrics_request": metric_request,
                             "stage_weighted_deltas_approx": weighted_delta,
                             "native_log_start_offset": start_offset, "native_log_end_offset": start_offset + len(native_bytes),
                             "private_output_file": f"outputs-private/task-{index + 1}.json"})
            state["tasks"].append(task_row); atomic_json(args.out / "results.json", state)
            print("TASK_DONE", task["id"], "PROMPT_MS", timing.get("prompt_ms"), "DECODE_MS", timing.get("decode_ms"),
                  "DRAFTS", timing.get("drafts_accepted_total_mtp_plus_suffix"), "/",
                  timing.get("drafts_offered_total_mtp_plus_suffix"), "FINISH", streamed["finish_reason"],
                  "ORACLE", oracle_pass if oracle_pass is not None else "manual", flush=True)

        require(len(state["tasks"]) == 2, "Profile ended without both remaining tasks")
        require(sha256(EXE) == hashes["exe"] and sha256(CONFIG) == hashes["config"] and
                sha256(Path(config["args"][config["args"].index("--expert-profile") + 1])) == hashes["profile"],
                "Daily executable/config/profile changed during profile")
        require({str(p): sha256(p) for p in helper_paths} == hashes["all_helpers"], "Server/helper source changed during profile")
        require({t["id"]: sha256(t["fixture_path"]) for t in tasks} ==
                {t["id"]: t["fixture_sha256"] for t in tasks}, "A frozen task fixture changed during profile")
        require(sha256(run_config) == plan["run_config_sha256"], "Run config clone changed during profile")
        state.update(status="completed", elapsed_seconds=time.monotonic() - start,
                     oracle_summary={t["id"]: next(x["oracle_json_pass"] for x in state["tasks"] if x["id"] == t["id"])
                                     for t in tasks if t["id"] in EXPECTED},
                     manual_review_task="migration-closeout-reading-20k",
                     timing_note="DECODE_TIMING is per request. SPLIT_TIMING rows are cumulative rounded averages; weighted deltas use window-count deltas. Native draft totals include MTP+suffix; MTP-only is computed after subtracting suffix. Residual stays unassigned.")
        atomic_json(args.out / "results.json", state)
        plan.update(status="completed", elapsed_seconds=state["elapsed_seconds"])
        atomic_json(args.out / "plan.json", plan)
        print("PROFILE_COMPLETE", "ELAPSED_S", round(state["elapsed_seconds"], 1),
              "ORACLES", json.dumps(state["oracle_summary"], sort_keys=True), flush=True)
    except BaseException as exc:
        error = repr(exc)
        state.update(status="failed", error=error, elapsed_seconds=time.monotonic() - start)
        atomic_json(args.out / "results.json", state)
        plan.update(status="failed", error=error, elapsed_seconds=state["elapsed_seconds"])
        atomic_json(args.out / "plan.json", plan)
        raise
    finally:
        cancel.set(); deadline_timer.cancel()
        record_owned(server.pid, owned, args.out / "process-tree.json", "cleanup-before")
        cleanup_actions = stop_owned(server, server_birth, owned, base_url,
                                     graceful_unload=server.poll() is None,
                                     deadline=hard_deadline)
        server_log.close()
        state["cleanup_actions"] = cleanup_actions
        state["server_returncode"] = server.poll()
        state["owned_processes_remaining"] = [pid for pid, born in owned.items() if owned_process_exists(pid, born)]
        state["cleanup_completed_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_json(args.out / "results.json", state)
        require(not state["owned_processes_remaining"], "Owned server/engine process remains after cleanup")
        require(time.monotonic() <= hard_deadline, "600-second hard cap exceeded during cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
