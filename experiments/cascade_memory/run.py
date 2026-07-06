"""Run an arm over a synthetic dataset and log a per-item JSONL.

Usage:
  python run.py --dataset runs/smoke.jsonl --arm B0_no_memory --base-url mock:oracle_decay
  python run.py --dataset data/synth_full.jsonl --arm B1_always_rag \
      --base-url http://localhost:8080/v1 --model qwen2.5-7b-instruct

Step 1 arms: B0_no_memory, B1_always_rag (or 'all'). NO cascade here.
"""
from __future__ import annotations
import os
import re
import sys
import json
import argparse
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import arms as arms_mod
import confidence as conf_mod
from scorer import score_item
from logger import RunLogger
from retrieval_adapter import backend_name

_FMT_RE = {
    "code": re.compile(r"[A-Za-z]{2}-\d{4}"),
    "number": re.compile(r"\b\d{3,}\b"),
}


def _git_commit(repo_dir):
    try:
        return subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def load_dataset(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def run_arm(arm, items, base_url, model, k, limit):
    runner = arms_mod.ARMS[arm]
    manifest = {
        "dataset_n": len(items),
        "base_url": base_url,
        "model": model,
        "sensor_primary": config.SENSOR_PRIMARY,
        "cost_weights": config.COST_WEIGHTS,
        "retriever_backend": backend_name(),
        "gen_defaults": config.GEN_DEFAULTS,
        "git_commit": _git_commit(os.path.dirname(os.path.abspath(__file__))),
        "k_retrieval": k,
    }
    logger = RunLogger(config.RUNS_DIR, arm, manifest)
    n_correct = n_abst = n_plant = n_ctl = 0
    tot_tokens = 0
    use = items[:limit] if limit else items
    for it in use:
        has_plant = it.get("has_plant", True)
        kwargs = {"k": k} if arm == "B1_always_rag" else {}
        out = runner(it, base_url, model, **kwargs)
        res = out["result"]
        sc = score_item(res.text, it["answer"])
        fmt_re = _FMT_RE.get(it.get("answer_type", "code"))
        cf = conf_mod.score(res, expected_format_re=fmt_re)
        logger.log_item(
            item_id=it["item_id"], arm=out["arm"], seed=it["seed"],
            distance=it["distance"], difficulty=it["difficulty"], category=it["category"],
            cost=out["cost"], confidence=cf["primary"], sensor_used=cf["used"],
            correct=sc["correct"], abstained=sc["abstained"],
            pred=res.text, gold=it["answer"], question=it["question"],
            n_distractors=it.get("n_distractors"),
            extra={"has_plant": it.get("has_plant", True),
                   "answer_type": it.get("answer_type"),
                   "conf_signals": cf["signals"],
                   "backend": res.backend, **out.get("meta", {})},
        )
        tot_tokens += out["cost"].total_tokens
        if has_plant:
            n_plant += 1
            n_correct += sc["correct"]
            n_abst += sc["abstained"]
        else:
            n_ctl += 1
    logger.close()
    N = logger.n
    acc = n_correct / n_plant if n_plant else float("nan")
    abst = n_abst / n_plant if n_plant else float("nan")
    print(f"[{arm}] N={N} (plant={n_plant}, ctl={n_ctl})  acc={acc:.3f} (correct/N_plant)  "
          f"abst={abst:.3f}  mean_tokens={tot_tokens/N:.1f}  -> {logger.path}")
    return logger.path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--arm", default="all", help="B0_no_memory | B1_always_rag | all")
    ap.add_argument("--base-url", default=config.BASE_URL)
    ap.add_argument("--model", default=config.MODEL)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    items = load_dataset(a.dataset)
    arm_list = list(arms_mod.ARMS) if a.arm == "all" else [a.arm]
    for arm in arm_list:
        run_arm(arm, items, a.base_url, a.model, a.k, a.limit)


if __name__ == "__main__":
    main()
