"""Una prova sul checkpoint da 205k: forward a 1 riga contro forward a 2 (o 3) righe.

Uso: python prova_verifica.py --tag T01 [--profile] [--width 2] [--tokens 64] [--env CHIAVE=VALORE ...]
"""
import argparse, json, os, pathlib, statistics, subprocess, time

S = pathlib.Path(__file__).resolve().parent
W = pathlib.Path(r"C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work")
BIN = W / "qwen38_clean" / "build" / "bin"
BASIS = W / "qwen38_incremental" / "paired" / "bm_mtp_full512_524capacity205k"
NSYS = r"C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe"

ap = argparse.ArgumentParser()
ap.add_argument("--tag", required=True)
ap.add_argument("--profile", action="store_true")
ap.add_argument("--width", type=int, choices=(2, 3), default=2)
ap.add_argument("--tokens", type=int, default=64)
ap.add_argument("--warm", type=int, default=16)
ap.add_argument("--exe", default=str(S / "paired_probe_prof.exe"))
ap.add_argument("--env", action="append", default=[])
ap.add_argument("--rollback", action="store_true", help="contesto con n_rs_seq=1 come nel ciclo MTP vero")
ap.add_argument("--set-arg", action="append", default=[], help="FLAG=VALORE sostituisce il valore di un flag del comando")
ap.add_argument("--mtp", action="store_true", help="ciclo MTP completo (bozza + verifica a 2 + rollback) sulla fase speculative")
args = ap.parse_args()

busy = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                       "@(Get-Process -Name llama-server,paired_probe,paired_probe_prof,incremental_probe,route_capture -ErrorAction SilentlyContinue).Count"],
                      capture_output=True, text=True).stdout.strip()
if busy != "0":
    raise SystemExit("processo di inferenza gia' attivo")

run = S / "prove" / args.tag
run.mkdir(parents=True, exist_ok=False)
prior = json.loads((BASIS / "manifest.json").read_text())
config = {k: prior["config"][k] for k in ("state", "depth", "inputs", "expected")}
if args.tokens % args.width:
    raise SystemExit("tokens deve essere multiplo di width")
config.update({"directory": str(run), "warm": args.warm, "tokens": args.tokens, "batch": args.width,
               "capture": False, "save_logits": False, "phases": ["sequential", "batch"]})
if args.rollback:
    config["rollback_depth"] = args.width - 1
if args.mtp:
    if args.width != 2:
        raise SystemExit("--mtp richiede --width 2")
    config.update({"mtp_model": r"D:\models\qwen38flashnext\MTP\mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf",
                   "rollback_depth": 1, "phases": ["speculative"]})
(run / "config.json").write_text(json.dumps(config))

env = {k: v for k, v in os.environ.items() if not k.startswith(("QWEN", "LLAMA_MOE_", "GGML_CUDA_MOE_", "GGML_CUDA_SCALAR"))}
env.update({k: v for k, v in prior["environment"].items() if k not in ("QWEN_PAIR_CONFIG", "QWEN4EXP_POOL_DEBUG")})
env["QWEN_PAIR_CONFIG"] = str(run / "config.json")
env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")
if args.profile:
    env["QWEN_PAIR_PROFILE"] = "1"
for kv in args.env:
    k, v = kv.split("=", 1)
    if v == "":
        env.pop(k, None)
    else:
        env[k] = v

command = list(prior["command"])
command[0] = args.exe
for fv in args.set_arg:
    flag, value = fv.split("=", 1)
    i = command.index(flag)
    command[i + 1] = value
launch = command
if args.profile:
    launch = [NSYS, "profile", "--session-new=qwen38_" + args.tag, "--trace=cuda,nvtx", "--cuda-graph-trace=node",
              "--capture-range=cudaProfilerApi", "--capture-range-end=stop", "--sample=none", "--cpuctxsw=none",
              "--export=sqlite", "--output=" + str(run / "verifica"), *command]
record = {"tag": args.tag, "launch": launch, "env_diff": {k: env.get(k) for k in sorted(set(prior["environment"]) | {kv.split("=", 1)[0] for kv in args.env})},
          "started": time.time()}
(run / "manifest.json").write_text(json.dumps(record, indent=1))
t0 = time.time()
with (run / "stdout.log").open("w") as out, (run / "stderr.log").open("w") as err:
    code = subprocess.run(launch, env=env, stdout=out, stderr=err, timeout=1800).returncode
res_path = run / "result.json"
summary = {"tag": args.tag, "exit": code, "wall_s": round(time.time() - t0, 1)}
if res_path.exists():
    r = json.loads(res_path.read_text())
    for ph in r.get("phases", []):
        ms = ph.get("decode_ms", [])[4:]
        if ms:
            summary[f"{ph['name']}_b{ph['batch']}_med_ms"] = round(statistics.median(ms), 2)
            summary[f"{ph['name']}_b{ph['batch']}_p90_ms"] = round(sorted(ms)[int(len(ms) * 0.9)], 2)
        summary[f"{ph['name']}_mismatch"] = len(ph.get("mismatches", []))
        if ph["name"] == "speculative" and ph.get("wall_ms"):
            summary["mtp_tps"] = round(len(ph.get("generated", [])) / ph["wall_ms"] * 1000, 2)
            summary["mtp_accettate"] = f"{ph.get('accepted_drafts')}/{ph.get('drafted_tokens')}"
            cyc = ph.get("cycles", [])
            if cyc:
                summary["bozza_med_ms"] = round(statistics.median(c["draft_ms"] for c in cyc), 2)
                summary["verifica_med_ms"] = round(statistics.median(c["target_ms"] for c in cyc), 2)
    b1 = summary.get("sequential_b1_med_ms")
    bw = summary.get(f"batch_b{args.width}_med_ms")
    if b1 and bw:
        summary["riga_in_piu_ms"] = round((bw - b1) / (args.width - 1), 2)
(run / "summary.json").write_text(json.dumps(summary, indent=1))
with (S / "prove" / "registro.jsonl").open("a") as f:
    f.write(json.dumps({**summary, "env": args.env, "profile": args.profile}) + "\n")
print(json.dumps(summary))
