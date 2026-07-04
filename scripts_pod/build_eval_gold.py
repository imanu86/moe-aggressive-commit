#!/usr/bin/env python
"""
build_eval_gold.py — Assemble a SERIOUS eval-gold set from open-source HF datasets.

Emits D:\\models\\eval\\eval_gold.jsonl with one JSON object per line:
  { id, category, prompt, gold, eval_method, meta }

Categories / sources:
  CODING          openai/openai_humaneval           (40)  eval_method=unit_test
  CODING          google-research-datasets/mbpp     (20)  eval_method=unit_test
  REASONING-MATH  openai/gsm8k  (config 'main')      (40)  eval_method=exact_match_number
  KNOWLEDGE       cais/mmlu  (hard subsets)          (40)  eval_method=mcq_letter
  KNOWLEDGE       idavidrein/gpqa (optional)         (10)  eval_method=mcq_letter

~150 items total. Prompts are cleaned & self-contained; gold extracted correctly.
"""
import json
import os
import re
import sys

from datasets import load_dataset

OUT_DIR = r"D:\models\eval"
OUT_PATH = os.path.join(OUT_DIR, "eval_gold.jsonl")

LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"]


def clean(s):
    if s is None:
        return ""
    return str(s).strip()


# ---------------------------------------------------------------------------
# CODING: HumanEval
# ---------------------------------------------------------------------------
def build_humaneval(n=40):
    print(f"[humaneval] loading openai/openai_humaneval ...", flush=True)
    ds = load_dataset("openai/openai_humaneval", split="test")
    items = []
    for i, ex in enumerate(ds):
        if len(items) >= n:
            break
        task_id = ex["task_id"]                 # e.g. "HumanEval/0"
        prompt_code = ex["prompt"]              # function signature + docstring
        canonical = ex["canonical_solution"]   # body completing the function
        test = ex["test"]                       # def check(candidate): ...
        entry_point = ex["entry_point"]

        prompt = (
            "Complete the following Python function. Return only the full "
            "function implementation.\n\n" + prompt_code
        )
        # gold = full reference program (signature + docstring + canonical body)
        gold = prompt_code + canonical
        items.append({
            "id": f"humaneval::{task_id}",
            "category": "CODING",
            "prompt": prompt,
            "gold": gold,
            "eval_method": "unit_test",
            "meta": {
                "source": "openai/openai_humaneval",
                "entry_point": entry_point,
                "test": test,
                "canonical_solution": canonical,
            },
        })
    print(f"[humaneval] collected {len(items)}", flush=True)
    return items


# ---------------------------------------------------------------------------
# CODING: MBPP
# ---------------------------------------------------------------------------
def build_mbpp(n=20):
    print(f"[mbpp] loading google-research-datasets/mbpp ...", flush=True)
    # 'full' config; use the test split for held-out-ish problems
    try:
        ds = load_dataset("google-research-datasets/mbpp", "full", split="test")
    except Exception as e:
        print(f"[mbpp] full/test failed ({e}); trying default test split", flush=True)
        ds = load_dataset("google-research-datasets/mbpp", split="test")
    items = []
    for ex in ds:
        if len(items) >= n:
            break
        text = clean(ex["text"])            # NL problem description
        code = clean(ex["code"])            # reference solution
        test_list = list(ex["test_list"])   # assert statements
        test_setup = clean(ex.get("test_setup_code", ""))
        tid = ex["task_id"]

        asserts = "\n".join(test_list)
        prompt = (
            f"{text}\n\n"
            "Write a Python solution. Your code must satisfy the following tests:\n"
            f"{asserts}"
        )
        items.append({
            "id": f"mbpp::{tid}",
            "category": "CODING",
            "prompt": prompt,
            "gold": code,
            "eval_method": "unit_test",
            "meta": {
                "source": "google-research-datasets/mbpp",
                "test_list": test_list,
                "test_setup_code": test_setup,
            },
        })
    print(f"[mbpp] collected {len(items)}", flush=True)
    return items


# ---------------------------------------------------------------------------
# REASONING-MATH: GSM8K
# ---------------------------------------------------------------------------
def extract_gsm8k_answer(answer_field):
    # The final numeric answer follows '####'
    m = re.search(r"####\s*(.+)", answer_field)
    if not m:
        return None
    raw = m.group(1).strip()
    # strip commas, currency, trailing punctuation
    num = raw.replace(",", "").replace("$", "").strip()
    num = num.rstrip(".")
    return num


def build_gsm8k(n=40):
    print(f"[gsm8k] loading openai/gsm8k (main) ...", flush=True)
    ds = load_dataset("openai/gsm8k", "main", split="test")
    items = []
    for i, ex in enumerate(ds):
        if len(items) >= n:
            break
        question = clean(ex["question"])
        gold = extract_gsm8k_answer(ex["answer"])
        if gold is None:
            continue
        prompt = (
            question
            + "\n\nSolve the problem. Give your final numeric answer on the last "
            "line in the form '#### <number>'."
        )
        items.append({
            "id": f"gsm8k::test::{i}",
            "category": "REASONING-MATH",
            "prompt": prompt,
            "gold": gold,
            "eval_method": "exact_match_number",
            "meta": {
                "source": "openai/gsm8k",
                "full_solution": clean(ex["answer"]),
            },
        })
    print(f"[gsm8k] collected {len(items)}", flush=True)
    return items


# ---------------------------------------------------------------------------
# KNOWLEDGE: MMLU (hard subsets)
# ---------------------------------------------------------------------------
MMLU_HARD = [
    "college_mathematics",
    "professional_law",
    "college_physics",
    "formal_logic",
]


def build_mmlu(n=40):
    per = max(1, n // len(MMLU_HARD))
    items = []
    for subj in MMLU_HARD:
        print(f"[mmlu] loading cais/mmlu {subj} ...", flush=True)
        ds = load_dataset("cais/mmlu", subj, split="test")
        got = 0
        for i, ex in enumerate(ds):
            if got >= per or len(items) >= n:
                break
            question = clean(ex["question"])
            choices = ex["choices"]
            answer_idx = ex["answer"]           # int 0..3
            gold_letter = LETTERS[answer_idx]
            opts = "\n".join(
                f"{LETTERS[j]}. {clean(c)}" for j, c in enumerate(choices)
            )
            prompt = (
                f"Answer the following multiple-choice question. Respond with only "
                f"the letter of the correct option.\n\n"
                f"{question}\n\n{opts}"
            )
            items.append({
                "id": f"mmlu::{subj}::{i}",
                "category": "KNOWLEDGE",
                "prompt": prompt,
                "gold": gold_letter,
                "eval_method": "mcq_letter",
                "meta": {
                    "source": "cais/mmlu",
                    "subject": subj,
                    "choices": list(choices),
                    "answer_index": int(answer_idx),
                },
            })
            got += 1
        print(f"[mmlu] {subj}: {got}", flush=True)
    print(f"[mmlu] collected {len(items)}", flush=True)
    return items[:n]


# ---------------------------------------------------------------------------
# KNOWLEDGE: GPQA (optional, gated — may fail)
# ---------------------------------------------------------------------------
def build_gpqa(n=10):
    import random
    print(f"[gpqa] trying idavidrein/gpqa (gpqa_main) ...", flush=True)
    try:
        ds = load_dataset("idavidrein/gpqa", "gpqa_main", split="train")
    except Exception as e:
        print(f"[gpqa] SKIP (not accessible): {e}", flush=True)
        return []
    items = []
    rng = random.Random(1234)
    for i, ex in enumerate(ds):
        if len(items) >= n:
            break
        question = clean(ex["Question"])
        correct = clean(ex["Correct Answer"])
        incorrect = [
            clean(ex["Incorrect Answer 1"]),
            clean(ex["Incorrect Answer 2"]),
            clean(ex["Incorrect Answer 3"]),
        ]
        options = incorrect + [correct]
        rng.shuffle(options)
        gold_idx = options.index(correct)
        gold_letter = LETTERS[gold_idx]
        opts = "\n".join(f"{LETTERS[j]}. {o}" for j, o in enumerate(options))
        prompt = (
            "Answer the following graduate-level multiple-choice question. "
            "Respond with only the letter of the correct option.\n\n"
            f"{question}\n\n{opts}"
        )
        items.append({
            "id": f"gpqa::main::{i}",
            "category": "KNOWLEDGE",
            "prompt": prompt,
            "gold": gold_letter,
            "eval_method": "mcq_letter",
            "meta": {
                "source": "idavidrein/gpqa",
                "options": options,
                "correct_answer": correct,
            },
        })
    print(f"[gpqa] collected {len(items)}", flush=True)
    return items


def truncate(s, n=220):
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + " ..."


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_items = []
    all_items += build_humaneval(40)
    all_items += build_mbpp(20)
    all_items += build_gsm8k(40)
    all_items += build_mmlu(40)
    all_items += build_gpqa(10)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for it in all_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    # counts per category
    counts = {}
    for it in all_items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1

    print("\n" + "=" * 60)
    print(f"WROTE {len(all_items)} items -> {OUT_PATH}")
    print("COUNTS PER CATEGORY:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    # 2 examples per category
    print("\nEXAMPLES (2 per category):")
    seen = {}
    for it in all_items:
        c = it["category"]
        if seen.get(c, 0) >= 2:
            continue
        seen[c] = seen.get(c, 0) + 1
        print("-" * 60)
        print(f"[{c}] id={it['id']} eval_method={it['eval_method']}")
        print(f"  PROMPT: {truncate(it['prompt'])}")
        print(f"  GOLD:   {truncate(str(it['gold']))}")

    # machine-readable summary line for the harness to parse
    print("\nSUMMARY_JSON=" + json.dumps({
        "path": OUT_PATH,
        "total": len(all_items),
        "counts_per_category": counts,
    }))


if __name__ == "__main__":
    main()
