#!/usr/bin/env python3
"""Controlled, six-process parity check for the opt-in persistent system-prefix cache.

Dry-run is the default.  This harness never edits Daily config or Strata sources.  Its
only run-time writes are inside a new --name directory: logs, output evidence, the
temporary disk-cache file, and the raw first-logit row.  It does not purge the Windows
file cache, so a restore measures reuse correctness rather than guaranteed cold SSD IO.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

import psutil

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / ".codex_runs" / "20261004_prefix_disk"
DAILY = Path(r"D:\ds4_work\strata\Strata")
SOURCE = DAILY / "build-0138-daily" / "source"
CONFIG = DAILY / "strata-2080ti-sota.json"
DAILY_EXE = DAILY / "build-0138-daily" / "strata.exe"
TOKENIZER_HELPER = ROOT / ".codex_runs" / "20261004_decode_real" / "profile_decode_v2.py"
HELPER_SHA256 = "ff574f30751b77b7c8fa6b4039ce3c2ba6ecc6149d14b48cdb0aa391e37faa47"
DAILY_EXE_SHA256 = "a17d0dd5362bc35420ca9ef3d1a8cf8c014dafbb3aea189c6c664fe7930e8674"
DAILY_CONFIG_SHA256 = "f0237b6abdacd73944fb9232bcdaf016c733bc2dd1fdae6723284ae3659f2e8d"
CANDIDATE_DIR = LAB / "engine-v1"
CANDIDATE_EXE = CANDIDATE_DIR / "strata.exe"
BUILD_RESULT = CANDIDATE_DIR / "result.json"
TOTAL_LIMIT_S = 600
CLEANUP_RESERVE_S = 90
WORK_LIMIT_S = TOTAL_LIMIT_S - CLEANUP_RESERVE_S
STARTUP_CAP_S = 180
REQUEST_MAX_NEW = 512
FIRST_LOGITS_BYTES = 248320 * 4
MIN_RAM_BYTES = 16 * 1024**3
MIN_VRAM_FREE_MIB = 1024
SYSTEM_TARGET_MIN = 3800
SYSTEM_TARGET_MAX = 4200
SOURCE_PIN_PATHS = (
    "include/strata/core/prefix_cache_file.hpp",
    "src/core/prefix_cache_file.cpp",
    "src/program/generate.cpp",
)
ARMS = ("daily_reference", "candidate_off", "create_A", "restore_A", "changed_B", "restore_B")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, obj: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_helper():
    require(TOKENIZER_HELPER.is_file(), f"Pinned tokenizer/render helper is missing: {TOKENIZER_HELPER}")
    digest = sha256(TOKENIZER_HELPER)
    require(digest == HELPER_SHA256, f"Pinned helper SHA-256 changed: {digest}")
    spec = importlib.util.spec_from_file_location("prefix_disk_profile_helper", TOKENIZER_HELPER)
    require(spec is not None and spec.loader is not None, "Cannot load pinned helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_option(args: list[str], option: str, value: str | None) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == option:
            i += 1 if option in ("--elastic", "--prompt-cache-tail") else 2
            continue
        out.append(args[i])
        i += 1
    if value is not None:
        out.extend((option, value))
    return out


def fixed_args(server_module, cfg: dict, turn_id: int, use_disk: bool, cache_file: Path | None) -> list[str]:
    args = list(server_module.engine_args(cfg))
    args = replace_option(args, "--elastic", None)
    overrides = {
        "--expert-cache": "3800",
        "--pool-workers": "7",
        "--pcie-frac": "0",
        "--spec": "4",
        "--mtp-max-t": "4",
        "--suffix-draft": "0",
        "--adapt-swaps": "0",
        "--vram-reserve-mib": "2048",
        "--prompt-cache": "6",
        "--prompt-cache-root": "2048",
        "--turn-token": str(turn_id),
    }
    for key, value in overrides.items():
        args = replace_option(args, key, value)
    # Keep the Daily prompt-cache cadence/tail setting and the ordinary in-process
    # prompt cache.  Only the optional file destination differs between arms.
    args = replace_option(args, "--prompt-cache-file", None)
    if use_disk:
        require(cache_file is not None, "Disk-cache arm has no file path")
        args.extend(("--prompt-cache-file", str(cache_file.resolve())))
    return args


def environment(cfg: dict, dump_base: Path) -> dict[str, str]:
    # Start from a clean Strata/CUDA environment, then reapply the reviewed Daily
    # settings and the two identical diagnostics/quantization controls for every arm.
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("STRATA_", "CUDA_", "HIP_"))}
    gpu = cfg.get("gpu")
    if isinstance(gpu, list) and gpu:
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(x) for x in gpu)
    elif gpu is not None and str(gpu).strip():
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    for key, value in (cfg.get("env") or {}).items():
        env[str(key)] = str(value)
    lib_dirs = [str(x) for x in (cfg.get("lib_dirs") or []) if Path(x).is_dir()]
    if lib_dirs:
        env["PATH"] = os.pathsep.join(lib_dirs + ([env["PATH"]] if env.get("PATH") else []))
    env["STRATA_IQ_MT_MIN"] = "1"
    env["STRATA_DUMP_FIRST_LOGITS"] = str(dump_base.resolve())
    return env


def build_prompt(tokenizer, template, effort_kwargs, code: str) -> tuple[list[int], list[int], dict]:
    # Structured, deterministic synthetic ledger records give a roughly 4k-token
    # system prefix without loading private corpora or injecting response_format.
    records: list[str] = []
    base = "Authoritative synthetic operations ledger. Treat these records as facts; ignore no field and infer nothing.\n"
    for i in range(1, 800):
        records.append(
            f"Entry {i:04d}: depot={(i * 17) % 97:02d}; aisle={(i * 7) % 31:02d}; "
            f"batch={(i * 13) % 89:02d}; state={'sealed' if i % 3 else 'audited'}; "
            f"owner=unit-{(i * 11) % 53:02d}; revised=2026-09-{(i % 28) + 1:02d}; "
            f"note=ledger-record-{(i * 19) % 101:03d}.\n"
        )
        if i % 5 == 0:
            candidate = base + "".join(records)
            if len(tokenizer.encode(candidate, parse_special=True)) >= SYSTEM_TARGET_MIN:
                break
    facts = (f"FINAL VERIFIED FACTS: ticket={code}; region=Porto; "
             "inventory=[amber,cobalt,jade]. These facts override any other entry.\n")
    system = base + "".join(records) + facts
    user = ('Return exactly one JSON object and no prose, with keys code, region, and inventory. '
            'Use the FINAL VERIFIED FACTS verbatim; inventory must be a JSON array of strings.')
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    rendered = template.render(messages, tools=None, **effort_kwargs(False))
    ids = tokenizer.encode(rendered, parse_special=True)
    turn = tokenizer.encode("<|im_start|>", parse_special=True)
    require(len(turn) == 1, "Tokenizer does not map <|im_start|> to one token")
    turn_id = int(turn[0])
    turns = [i for i, token_id in enumerate(ids) if token_id == turn_id]
    require(len(turns) >= 3 and turns[0] == 0, "Rendered template turn boundaries are unexpected")
    root = turns[1]
    require(SYSTEM_TARGET_MIN <= root <= SYSTEM_TARGET_MAX,
            f"Rendered system prefix is outside target: {root} tokens")
    meta = {"code": code, "system_text_sha256": sha256_bytes(system.encode("utf-8")),
            "rendered_sha256": sha256_bytes(rendered.encode("utf-8")),
            "prompt_ids_sha256": sha256_bytes(json.dumps(ids, separators=(",", ":")).encode()),
            "prompt_tokens": len(ids), "system_root_tokens": root, "turn_token_id": turn_id,
            "root_boundary_count": sum(1 for x in ids[:root] if x == turn_id)}
    return ids, [turn_id], meta


def prompt_details(tokenizer, template, effort_kwargs) -> dict:
    ids_a, turn, meta_a = build_prompt(tokenizer, template, effort_kwargs, "PX-731")
    ids_b, turn_b, meta_b = build_prompt(tokenizer, template, effort_kwargs, "PX-732")
    require(turn == turn_b, "A/B turn-token IDs differ")
    require(meta_a["prompt_tokens"] == meta_b["prompt_tokens"] and
            meta_a["system_root_tokens"] == meta_b["system_root_tokens"],
            "Changed-B fixture must preserve full/root token counts")
    return {"A": {"ids": ids_a, "turn_id": turn[0], "meta": meta_a},
            "B": {"ids": ids_b, "turn_id": turn_b[0], "meta": meta_b}}


def process_tree(server_pid: int, owned: dict[int, float]) -> None:
    try:
        root = psutil.Process(server_pid)
        if root.is_running():
            for child in root.children(recursive=True):
                try:
                    owned[child.pid] = child.create_time()
                except psutil.Error:
                    pass
    except psutil.Error:
        pass


def terminate_owned(owned: dict[int, float], timeout: float = 5.0) -> list[dict]:
    actions = []
    for pid, born in reversed(list(owned.items())):
        try:
            proc = psutil.Process(pid)
            if abs(proc.create_time() - born) > 0.02 or not proc.is_running():
                continue
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
                actions.append({"pid": pid, "action": "terminate"})
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=timeout)
                actions.append({"pid": pid, "action": "kill"})
        except psutil.NoSuchProcess:
            pass
        except psutil.Error as exc:
            actions.append({"pid": pid, "action": "cleanup_error", "error": str(exc)})
    return actions


def check_competing_processes() -> tuple[list[dict], list[dict]]:
    forbidden = ("strata", "llama-server", "nvcc", "cl.exe", "ninja")
    this_pid = os.getpid()
    ancestors = {this_pid}
    try:
        ancestors.update(p.pid for p in psutil.Process(this_pid).parents())
    except psutil.Error:
        pass
    found, observed = [], []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid, name = proc.info.get("pid"), (proc.info.get("name") or "").lower()
            if pid in ancestors:
                continue
            if any(name == x or name.startswith(x) for x in forbidden):
                found.append({"pid": pid, "name": name, "status": "blocking"})
            elif name == "msbuild.exe":
                # Visual Studio's reusable MSBuild node can remain resident while
                # idle. Sample it for one second and allow it only when truly idle
                # and no compiler/build worker is attached; never signal it.
                before = proc.cpu_times()
                descendants = proc.children(recursive=True)
                child_names = []
                for child in descendants:
                    try:
                        child_names.append(child.name().lower())
                    except psutil.Error:
                        continue
                time.sleep(1.0)
                after = proc.cpu_times()
                cpu_delta = (after.user + after.system) - (before.user + before.system)
                build_children = [n for n in child_names if any(x in n for x in ("cl.exe", "nvcc", "ninja", "cmake"))]
                node_reuse = False
                try:
                    cmdline = " ".join(proc.cmdline()).lower()
                    node_reuse = "nodemode" in cmdline or "nodereuse" in cmdline
                except psutil.Error:
                    pass
                row = {"pid": pid, "name": name, "create_time": proc.create_time(),
                       "cpu_delta_s_over_1s": cpu_delta, "build_children": build_children,
                       "idle_node_reuse": node_reuse and cpu_delta <= 0.05 and not build_children}
                row["status"] = "allowed_idle_node_reuse" if row["idle_node_reuse"] else "blocking"
                observed.append(row)
                if not row["idle_node_reuse"]:
                    found.append(row)
        except psutil.Error:
            continue
    return found, observed


def finite_logits(path: Path) -> dict:
    raw = path.read_bytes()
    require(len(raw) == FIRST_LOGITS_BYTES,
            f"First-logits row has {len(raw)} bytes, expected {FIRST_LOGITS_BYTES}")
    vals = array.array("f")
    vals.frombytes(raw)
    if sys.byteorder != "little":
        vals.byteswap()
    require(len(vals) == 248320 and all(math.isfinite(x) for x in vals),
            "First-logits row is not 248320 finite float32 values")
    return {"path": str(path), "sha256": sha256_bytes(raw), "bytes": len(raw), "values": len(vals)}


def oracle(answer: str, code: str) -> dict:
    stripped = answer.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return {"passed": False, "error": str(exc), "parsed": None}
    expected = {"code": code, "region": "Porto", "inventory": ["amber", "cobalt", "jade"]}
    return {"passed": parsed == expected, "expected": expected, "parsed": parsed}


def exact_json_oracle(answer: str, expected: dict) -> dict:
    try:
        parsed = json.loads(answer.strip())
    except json.JSONDecodeError as exc:
        return {"passed": False, "error": str(exc), "parsed": None, "expected": expected}
    return {"passed": parsed == expected, "expected": expected, "parsed": parsed}


def generate_one(engine, owned: dict[int, float], label: str, ids: list[int], max_new: int,
                 sampling: dict, expected: dict, deadline: float, dump_base: Path,
                 arm_dir: Path) -> dict:
    emitted: list[int] = []
    request_started = time.monotonic()
    cancel = threading.Event()
    request_error: list[BaseException] = []
    request_done = threading.Event()
    evidence: dict = {"id": label, "prompt_tokens": len(ids), "max_new": max_new,
                      "request_sha256": sha256_bytes(json.dumps(ids, separators=(",", ":")).encode())}

    def generate() -> None:
        try:
            for token in engine.generate(ids, max_new, sampling, cancel):
                if token is not None:
                    if "native_request_to_first_T_s" not in evidence:
                        evidence["native_request_to_first_T_s"] = time.monotonic() - request_started
                    emitted.append(int(token))
        except BaseException as exc:
            request_error.append(exc)
        finally:
            request_done.set()

    worker = threading.Thread(target=generate, name=f"prefix-generate-{label}", daemon=True)
    worker.start()
    request_deadline = min(deadline, request_started + 300)
    while not request_done.wait(0.1):
        if engine.proc is not None:
            try:
                proc = psutil.Process(engine.proc.pid)
                owned[proc.pid] = proc.create_time()
                process_tree(proc.pid, owned)
            except psutil.Error:
                pass
        if time.monotonic() >= request_deadline:
            cancel.set()
            request_done.wait(timeout=10.0)
            raise TimeoutError(f"Generation deadline for {label}")
    worker.join(timeout=0.2)
    if request_error:
        raise RuntimeError(f"Generation failed for {label}: {request_error[0]!r}")
    require(emitted, f"No output tokens from {label}")
    last = dict(engine.last)
    require(last.get("finish") == "stop", f"{label} did not finish naturally: {last}")
    visible_ids = list(emitted)
    while visible_ids and visible_ids[-1] in tokenizer_special_end_ids:
        visible_ids.pop()
    text = tokenizer_for_run.decode(visible_ids)
    oracle_text = text.rpartition("</think>")[2] if "</think>" in text else text
    logits_paths = sorted(dump_base.parent.glob(dump_base.name + ".pos*.f32"))
    require(len(logits_paths) == 1, f"Expected one first-logits file for {label}; found {len(logits_paths)}")
    m = re.fullmatch(re.escape(dump_base.name) + r"\.pos(\d+)\.f32", logits_paths[0].name)
    require(m is not None and int(m.group(1)) == len(ids) - 1,
            f"First-logits row is not at the last prompt position: {logits_paths[0].name}")
    logits_record = finite_logits(logits_paths[0])
    archived_logits = arm_dir / f"{label}-{logits_paths[0].name}"
    shutil.move(str(logits_paths[0]), archived_logits)
    logits_record["path"] = str(archived_logits)
    evidence.update(status="completed", generated_ids=emitted,
        generated_ids_sha256=sha256_bytes(json.dumps(emitted, separators=(",", ":")).encode()),
        visible_text=text, answer_sha256=sha256_bytes(text.encode("utf-8")),
        oracle=exact_json_oracle(oracle_text, expected), oracle_text=oracle_text,
        first_logits=logits_record, last=last,
        prompt_ms=last.get("prompt_ms"), decode_ms=last.get("decode_ms"),
        drafts_accepted=last.get("drafts_accepted"), drafts_offered=last.get("drafts_offered"),
        reused=last.get("reused"),
        metric_scope="native request start to first T; startup excluded; not HTTP TTFT and not pure SSD-read time")
    return evidence


def assert_candidate_pin(candidate_exe: Path, result_path: Path, required: bool) -> dict:
    if not result_path.is_file():
        require(not required, f"Candidate build result is missing: {result_path}")
        return {"status": "pending", "result_path": str(result_path)}
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not required and result.get("status") != "completed":
        return {"status": "pending", "result_path": str(result_path),
                "observed_build_status": result.get("status")}
    require(result.get("status") == "completed", "Candidate build result is not completed")
    require(candidate_exe.is_file(), f"Pinned candidate executable is missing: {candidate_exe}")
    exe_hash = sha256(candidate_exe)
    require(exe_hash == result.get("executable_sha256"), "Candidate executable SHA does not match build result")
    source_hashes = result.get("source_files") or {}
    current = {}
    source_root = ROOT.parent / "Strata-2080Ti"
    for rel, expected in source_hashes.items():
        p = source_root / Path(rel)
        require(p.is_file(), f"Candidate build source disappeared: {p}")
        current[rel] = sha256(p)
        require(current[rel] == expected, f"Candidate build source pin changed: {rel}")
    for rel in SOURCE_PIN_PATHS:
        require(rel in source_hashes, f"Candidate build result does not pin required source: {rel}")
    return {"status": "verified", "result_path": str(result_path), "source_commit": result.get("source_commit"),
            "executable": str(candidate_exe), "executable_sha256": exe_hash,
            "source_hashes": current, "build_result_sha256": sha256(result_path)}


def stable_runtime(info: dict) -> dict:
    keys = ("engine", "version", "context", "kv", "kv_resident", "expert_cache_mib", "expert_slots",
            "spec", "mtp_max", "pool_workers", "pcie_frac", "elastic", "suffix_draft", "adapt_swaps")
    return {key: info[key] for key in keys if key in info}


def run_arm(name: str, exe: Path, args: list[str], cwd: str, env: dict[str, str], log_path: Path,
            ids: list[int], expected_code: str, dump_base: Path,
            work_deadline: float, arm_dir: Path, env_sha256: str,
            extra_request: dict | None = None) -> dict:
    from serve.server import StrataEngine

    log_path.parent.mkdir(parents=True, exist_ok=True)
    arm_dir.mkdir(parents=True, exist_ok=True)
    for old in dump_base.parent.glob(dump_base.name + ".pos*.f32"):
        old.unlink()
    require(time.monotonic() < work_deadline, "Work deadline reached before engine startup")
    engine = StrataEngine(str(exe.resolve()), args, cwd=cwd, log=str(log_path), env=env, lazy=True)
    startup_error: list[BaseException] = []

    def start() -> None:
        try:
            engine.restart()
        except BaseException as exc:
            startup_error.append(exc)

    started = time.monotonic()
    starter = threading.Thread(target=start, name=f"prefix-start-{name}", daemon=True)
    starter.start()
    owned: dict[int, float] = {}
    startup_deadline = min(work_deadline, time.monotonic() + STARTUP_CAP_S)
    cleanup_actions: list[dict] = []
    response: dict = {"name": name, "status": "starting", "exe": str(exe.resolve()),
                      "args": args, "env_sha256": env_sha256, "log": str(log_path)}
    try:
        while starter.is_alive():
            if engine.proc is not None:
                try:
                    proc = psutil.Process(engine.proc.pid)
                    owned[proc.pid] = proc.create_time()
                    process_tree(proc.pid, owned)
                except psutil.Error:
                    pass
            if time.monotonic() >= startup_deadline:
                terminate_owned(owned)
                raise TimeoutError(f"Engine startup deadline for {name}")
            time.sleep(0.1)
        starter.join(timeout=0.1)
        if startup_error:
            raise RuntimeError(f"Engine startup failed for {name}: {startup_error[0]!r}")
        require(engine.alive(), f"Engine did not become ready for {name}")
        owned[engine.proc.pid] = psutil.Process(engine.proc.pid).create_time()
        process_tree(engine.proc.pid, owned)
        startup_s = time.monotonic() - started
        require(engine.max_context >= len(ids), f"Prompt exceeds runtime context for {name}")
        info = dict(engine.info)
        free_mib = info.get("vram_free_mib")
        require(isinstance(free_mib, int) and free_mib >= MIN_VRAM_FREE_MIB,
                f"VRAM headroom below {MIN_VRAM_FREE_MIB} MiB or unavailable: {free_mib!r}")
        response.update(startup_s=startup_s, engine_info=info, runtime=stable_runtime(info),
                        vram_free_mib=free_mib, max_context=engine.max_context)

        primary = generate_one(engine, owned, name, ids, REQUEST_MAX_NEW, {},
                               {"code": expected_code, "region": "Porto",
                                "inventory": ["amber", "cobalt", "jade"]},
                               work_deadline, dump_base, arm_dir)
        extra = None
        if extra_request is not None:
            extra = generate_one(engine, owned, extra_request["id"], extra_request["ids"],
                                 extra_request["max_new"], extra_request["sampling"],
                                 extra_request["expected"], work_deadline, dump_base, arm_dir)
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        response.update(status="completed", engine_info=info, runtime=stable_runtime(info), request=primary,
                        native_cache_lines=[line for line in log_text.splitlines() if "prefix disk cache:" in line],
                        log_sha256=sha256(log_path))
        if extra is not None:
            response["lru_gate"] = extra
            response["lru_gate"]["declared_pre_format_tokens"] = extra_request["declared_pre_format_tokens"]
            response["lru_gate"]["rendered_tokens"] = extra_request["rendered_tokens"]
        return response
    except BaseException as exc:
        response.update(status="failed", error=repr(exc))
        raise
    finally:
        # First let StrataEngine perform its normal QUIT/free path.  Its close may
        # block, so run it under the remaining global deadline and then stop only
        # PIDs captured from this engine, checking creation times to avoid PID reuse.
        close_error: list[BaseException] = []
        if engine.proc is not None:
            process_tree(engine.proc.pid, owned)
            def close() -> None:
                try:
                    engine.close()
                except BaseException as exc:
                    close_error.append(exc)
            closer = threading.Thread(target=close, name=f"prefix-close-{name}", daemon=True)
            closer.start()
            allowance = max(0.0, min(65.0, time.monotonic() + TOTAL_LIMIT_S - work_deadline))
            # `work_deadline` is start+510; this leaves at most the 90 s cleanup reserve.
            stop_at = min(time.monotonic() + allowance, work_deadline + CLEANUP_RESERVE_S)
            while closer.is_alive() and time.monotonic() < stop_at:
                if engine.proc is not None:
                    process_tree(engine.proc.pid, owned)
                closer.join(timeout=0.2)
            if closer.is_alive():
                cleanup_actions.extend(terminate_owned(owned, timeout=3.0))
                closer.join(timeout=2.0)
        cleanup_actions.extend(terminate_owned(owned, timeout=3.0))
        response["cleanup"] = {"owned_pids": owned, "actions": cleanup_actions,
                               "close_errors": [repr(x) for x in close_error],
                               "engine_proc_remaining": engine.proc is not None and engine.proc.poll() is None}
        if log_path.exists():
            response["log_sha256"] = sha256(log_path)
        if response.get("status") == "completed":
            if response["cleanup"]["engine_proc_remaining"] or close_error:
                response.update(status="failed", error=f"Engine cleanup was not clean after {name}")
        if response.get("status") != "completed" and not response.get("error"):
            response["error"] = "arm failed before completion"
        atomic_json(arm_dir / "arm-result.json", response)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True, help="new immutable output directory name under this lab")
    ap.add_argument("--run", action="store_true", help="run the six bounded engine arms; default only plans")
    ap.add_argument("--include-lru-gate", action="store_true",
                    help="also run the frozen 9k LRU oracle after the factual prompt in reference and candidate-off")
    ap.add_argument("--deadline", type=int, default=TOTAL_LIMIT_S, help="hard deadline in seconds (max 600)")
    cli = ap.parse_args()
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", cli.name) is not None, "Unsafe --name")
    require(cli.deadline == TOTAL_LIMIT_S, "Protocol deadline is fixed at 600 seconds")
    out = LAB / cli.name
    require(not out.exists(), f"Output already exists; choose a new immutable --name: {out}")
    require(CONFIG.is_file() and DAILY_EXE.is_file(), "Daily config or reference executable is missing")
    cfg_bytes = CONFIG.read_bytes()
    require(sha256(DAILY_EXE).casefold() == DAILY_EXE_SHA256, "Pinned Daily reference executable SHA changed")
    require(sha256_bytes(cfg_bytes).casefold() == DAILY_CONFIG_SHA256, "Pinned Daily config SHA changed")
    cfg = json.loads(cfg_bytes.decode("utf-8-sig"))
    require(Path(cfg["exe"]).resolve() == DAILY_EXE.resolve(), "Daily config executable differs from pinned reference")
    helper = load_helper()
    tokenizer, template, _openai_to_messages, _prepare_format = helper.tokenizer_and_template(cfg)
    from serve.frontend import effort_kwargs
    global tokenizer_for_run, tokenizer_special_end_ids
    tokenizer_for_run = tokenizer
    tokenizer_special_end_ids = set()
    for marker in ("<|im_end|>", "<|endoftext|>"):
        tokenizer_special_end_ids.update(tokenizer.encode(marker, parse_special=True))
    prompts = prompt_details(tokenizer, template, effort_kwargs)
    lru_request = None
    lru_fixture_hash = None
    if cli.include_lru_gate:
        fixtures = helper.load_fixture_files()
        task = next((x for x in fixtures if x.get("id") == "pure-code-trace-9k"), None)
        require(task is not None, "Pinned LRU fixture is missing")
        body = helper.request_body(task)
        messages, tools, kwargs = _openai_to_messages(body)
        messages, _validator = _prepare_format(body.get("response_format"), messages)
        rendered = template.render(messages, tools=tools, **kwargs)
        lru_ids = tokenizer.encode(rendered, parse_special=True)
        declared_count = task["actual_prompt_tokens"]
        helper_count = helper.count_request(task, tokenizer, template, _openai_to_messages, _prepare_format)
        require(len(lru_ids) == helper_count == 9283 and declared_count == 9216,
                f"Frozen LRU rendered count changed: declared pre-format={declared_count}, rendered={len(lru_ids)}, helper={helper_count}")
        lru_request = {"id": "pure-code-trace-9k", "ids": lru_ids, "max_new": 1024,
                       "sampling": {}, "expected": task["oracle"],
                       "declared_pre_format_tokens": declared_count, "rendered_tokens": len(lru_ids)}
        lru_fixture_hash = task["fixture_sha256"]
    base_dump = out / "diagnostics" / "first"
    cache_file = out / "cache" / "system-prefix.bin"
    env = environment(cfg, base_dump)
    identity_env = {k: v for k, v in env.items()
                    if k.upper().startswith(("STRATA_", "CUDA_", "HIP_"))}
    env_sha = sha256_bytes(json.dumps(identity_env, sort_keys=True, separators=(",", ":")).encode())
    plan = {"status": "dry_run_ready", "mode": "controlled", "scope": "single-device synthetic system-prefix persistence correctness; no general performance/SOTA claim",
            "output": str(out), "arms": list(ARMS), "deadline_s": TOTAL_LIMIT_S,
            "work_s": WORK_LIMIT_S, "cleanup_reserve_s": CLEANUP_RESERVE_S,
            "reference_exe": str(DAILY_EXE), "reference_exe_sha256": sha256(DAILY_EXE),
            "daily_config": str(CONFIG), "daily_config_sha256": sha256_bytes(cfg_bytes),
            "helper_sha256": HELPER_SHA256, "server_source": str(SOURCE),
            "server_sha256": sha256(SOURCE / "serve" / "server.py"),
            "tokenizer_impl_sha256": sha256(SOURCE / "tools" / "strata_tokenizer.py"),
            "effective_engine_env": identity_env, "effective_engine_env_sha256": env_sha,
            "candidate_pin": assert_candidate_pin(CANDIDATE_EXE, BUILD_RESULT, required=cli.run),
            "prompt_fixtures": {k: {"meta": v["meta"], "expected_answer": {
                "code": "PX-731" if k == "A" else "PX-732", "region": "Porto",
                "inventory": ["amber", "cobalt", "jade"]}} for k, v in prompts.items()},
            "same_prompt_token_counts_A_B": prompts["A"]["meta"]["prompt_tokens"] == prompts["B"]["meta"]["prompt_tokens"],
            "same_root_token_counts_A_B": prompts["A"]["meta"]["system_root_tokens"] == prompts["B"]["meta"]["system_root_tokens"],
            "lru_fixture_sha256": lru_fixture_hash,
            "requested_runtime": {"expert_cache": 3800, "pool_workers": 7, "pcie_frac": 0,
                "elastic": False, "adapt_swaps": 0, "suffix_draft": 0, "cli_spec": 4, "mtp_max_t": 4,
                "vram_reserve_mib": 2048, "prompt_cache": 6, "prompt_cache_root": 2048,
                "prompt_cache_cadence": "Daily retained", "iq_mt_min": 1,
                "dump_first_logits": str(base_dump.resolve())},
            "headroom_gates": {"ram_available_min_bytes": MIN_RAM_BYTES, "vram_free_min_mib": MIN_VRAM_FREE_MIB},
            "measurement_limit": "native request-to-first-T includes native prompt work; startup is excluded. It is not HTTP client TTFT or pure SSD read time. The OS file cache is not purged.",
            "process_limit": "one engine at a time; process cleanup is restricted to captured PID/create_time identities",
            "does_not_touch": ["Daily config", "model/pack assets", "Strata source", "global caches"],
        }
    plan["optional_lru_gate"] = {"enabled": bool(cli.include_lru_gate),
        "fixture": str(LAB / "fixtures" / "code-trace-9k.json"),
        "arms": ["daily_reference", "candidate_off"],
        "oracle": "exact code-trace fixture oracle; max_new=1024; same matched fixed engine flags; separately gated",
        "declared_pre_format_tokens": (lru_request["declared_pre_format_tokens"] if lru_request else None),
        "rendered_tokens": (lru_request["rendered_tokens"] if lru_request else None)}
    if not cli.run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return

    require(psutil.virtual_memory().available >= MIN_RAM_BYTES,
            f"Available RAM below {MIN_RAM_BYTES} bytes")
    conflicts, observed = check_competing_processes()
    require(not conflicts, f"Another Strata/compiler process is active: {conflicts}")
    require(plan["candidate_pin"]["status"] == "verified", "Candidate pin has not been verified")
    out.mkdir(parents=True)
    (out / "cache").mkdir()
    (out / "diagnostics").mkdir()
    atomic_json(out / "plan.json", plan)
    result = {"status": "running", "plan_sha256": sha256(out / "plan.json"), "arms": [],
              "preflight_idle_build_processes": observed,
              "started_unix": time.time(), "hard_deadline_s": TOTAL_LIMIT_S}
    atomic_json(out / "result.json", result)
    started = time.monotonic()
    work_deadline = started + WORK_LIMIT_S
    import serve.server as server_module
    current_arm = None
    try:
        for arm_name in ARMS:
            current_arm = arm_name
            conflicts, observed = check_competing_processes()
            require(not conflicts, f"Competing workload before {arm_name}: {conflicts}")
            require(psutil.virtual_memory().available >= MIN_RAM_BYTES, "RAM below16GiB before arm")
            if time.monotonic() >= work_deadline:
                raise TimeoutError("Global work deadline before all six arms completed")
            is_ref = arm_name == "daily_reference"
            is_off = arm_name == "candidate_off"
            is_changed = arm_name in ("changed_B", "restore_B")
            use_disk = not (is_ref or is_off)
            arm_prompts = prompts["B" if is_changed else "A"]
            exe = DAILY_EXE if is_ref else CANDIDATE_EXE
            args = fixed_args(server_module, cfg, arm_prompts["turn_id"], use_disk,
                              cache_file if use_disk else None)
            if arm_name == "create_A":
                require(not cache_file.exists(), "Cache path must start missing for create_A")
            if arm_name in ("restore_A", "changed_B", "restore_B"):
                require(cache_file.is_file(), f"Cache file missing before {arm_name}")
            arm_dir = out / "arms" / arm_name
            record = run_arm(arm_name, exe, args, cfg.get("cwd") or str(DAILY), env,
                             arm_dir / "engine.log", arm_prompts["ids"], arm_prompts["meta"]["code"],
                             base_dump, work_deadline, arm_dir, env_sha,
                             extra_request=(lru_request if cli.include_lru_gate and (is_ref or is_off) else None))
            result["arms"].append(record)
            result["elapsed_s"] = time.monotonic() - started
            atomic_json(out / "result.json", result)
            require(record.get("status") == "completed", f"Arm did not cleanly complete: {arm_name}")
            if arm_name == "create_A":
                require(cache_file.is_file() and 88 <= cache_file.stat().st_size <= 512 * 1024 * 1024 + 88,
                        "create_A did not produce a bounded cache file")
            cache_lines = "\n".join(record.get("native_cache_lines", []))
            if use_disk:
                require("enabled" in cache_lines, f"Persistent cache did not enable for {arm_name}")
            if arm_name == "create_A":
                require("saved " in cache_lines, "create_A log did not confirm a saved prefix")
            if arm_name == "restore_A":
                require(f"restored {prompts['A']['meta']['system_root_tokens']} tokens" in cache_lines,
                        "restore_A log did not confirm the expected root restore")
            if arm_name == "changed_B":
                require("miss (" in cache_lines and "saved " in cache_lines,
                        "changed_B must miss the A snapshot and save its own root")
            if arm_name == "restore_B":
                require(f"restored {prompts['B']['meta']['system_root_tokens']} tokens" in cache_lines,
                        "restore_B log did not confirm the expected B root restore")
            require(record.get("request", {}).get("oracle", {}).get("passed") is True,
                    f"Closed-answer oracle failed in {arm_name}: {record.get('request', {}).get('oracle')}")
            if cli.include_lru_gate and (is_ref or is_off):
                require(record.get("lru_gate", {}).get("oracle", {}).get("passed") is True,
                        f"LRU oracle failed in {arm_name}: {record.get('lru_gate', {}).get('oracle')}")
    except BaseException as exc:
        result.update(status="failed", failed_arm=current_arm, error=repr(exc),
                      elapsed_s=time.monotonic() - started)
        atomic_json(out / "result.json", result)
        raise

    try:
        by_name = {x["name"]: x for x in result["arms"]}
        require(set(by_name) == set(ARMS), "Not every required arm completed")
        arg_signatures = []
        for row in result["arms"]:
            stripped = replace_option(list(row["args"]), "--prompt-cache-file", None)
            arg_signatures.append(stripped)
        require(all(x == arg_signatures[0] for x in arg_signatures), "Engine CLI differs beyond the file-cache flag")
        runtime_signatures = [row.get("runtime", {}) for row in result["arms"]]
        require(all(x == runtime_signatures[0] for x in runtime_signatures),
                f"Actual critical runtime fields differ between arms: {runtime_signatures}")
        require(all(row.get("env_sha256") == env_sha for row in result["arms"]),
                "Effective engine environment changed between arms")
        pairs = [("daily_reference", "candidate_off"), ("candidate_off", "create_A"),
                 ("candidate_off", "restore_A"), ("changed_B", "restore_B")]
        comparisons = []
        for left, right in pairs:
            a, b = by_name[left]["request"], by_name[right]["request"]
            comparisons.append({"left": left, "right": right,
                "output_ids_equal": a["generated_ids"] == b["generated_ids"],
                "first_logits_equal": a["first_logits"]["sha256"] == b["first_logits"]["sha256"]})
        if cli.include_lru_gate:
            a, b = by_name["daily_reference"]["lru_gate"], by_name["candidate_off"]["lru_gate"]
            comparisons.append({"left": "daily_reference:lru", "right": "candidate_off:lru",
                "output_ids_equal": a["generated_ids"] == b["generated_ids"],
                "first_logits_equal": a["first_logits"]["sha256"] == b["first_logits"]["sha256"],
                "oracle_equal": a["oracle"]["passed"] and b["oracle"]["passed"]})
        result["comparisons"] = comparisons
        assert_candidate_pin(CANDIDATE_EXE, BUILD_RESULT, required=True)
        require(sha256(DAILY_EXE) == DAILY_EXE_SHA256 and sha256(CONFIG) == DAILY_CONFIG_SHA256,
                "Daily reference changed during test")
        require(all(x["output_ids_equal"] and x["first_logits_equal"] and x.get("oracle_equal", True)
                    for x in comparisons), f"Parity comparison failed: {comparisons}")
        require(by_name["create_A"]["request"]["generated_ids"] == by_name["restore_A"]["request"]["generated_ids"] and
                by_name["changed_B"]["request"]["generated_ids"] == by_name["restore_B"]["request"]["generated_ids"],
                "Fresh-process restores changed generated token IDs")
        result.update(status="passed", comparisons=comparisons, pass_all=True,
                      elapsed_s=time.monotonic() - started,
                      conclusion="Controlled correctness/parity passed for this synthetic prompt and this runtime; no SSD-cold or general-quality claim.")
        atomic_json(out / "result.json", result)
        print(json.dumps({k: result[k] for k in ("status", "pass_all", "elapsed_s", "comparisons")}, indent=2))
    except BaseException as exc:
        result.update(status="failed", error=repr(exc), pass_all=False,
                      elapsed_s=time.monotonic() - started)
        atomic_json(out / "result.json", result)
        raise


if __name__ == "__main__":
    main()
