"""Esegue eval_gold.jsonl contro un ds4-server (OpenAI-compatible) e grada per categoria.
Coding=unit_test (esegue completion+test), Math=exact_match_number, Knowledge=mcq_letter.
Gestisce i modelli reasoning: strippa <think> e nudge finale. Uso: python run_eval_ds4.py [N_per_cat] [api_url]
Output: /workspace/eval_results.json + summary a stdout + marker /workspace/EVAL_DONE."""
import json, urllib.request, time, re, sys, subprocess
from collections import defaultdict

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
API = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/v1/chat/completions"
EVAL = sys.argv[3] if len(sys.argv) > 3 else "/workspace/eval_gold.jsonl"
CAPS = {"CODING": 1400, "REASONING-MATH": 1800, "KNOWLEDGE": 1100}

def ask(prompt, mx):
    data = json.dumps({"model": "ds4", "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0, "max_tokens": mx}).encode()
    r = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time(); d = json.load(urllib.request.urlopen(r, timeout=900)); dt = time.time() - t0
    return d["choices"][0]["message"]["content"], d["usage"]["completion_tokens"], dt, d["usage"].get("prompt_tokens", 0)

def strip_think(t):
    if "</think>" in t: return t.split("</think>")[-1]
    if "<|end_thinking|>" in t: return t.split("<|end_thinking|>")[-1]
    return t

def g_math(ans, gold):
    a = strip_think(ans)
    m = re.search(r'answer is[^0-9\-]*(-?\d[\d,]*\.?\d*)', a, re.I)
    nums = [m.group(1)] if m else re.findall(r'-?\d[\d,]*\.?\d*', a)
    if not nums: return False
    try: return abs(float(nums[-1].replace(',', '')) - float(str(gold).replace(',', ''))) < 1e-6
    except: return False

def g_mcq(ans, gold):
    a = strip_think(ans)
    m = re.search(r'answer is[^A-D]*([A-D])', a, re.I) or re.search(r'\b([A-D])\b(?!.*\b[A-D]\b)', a)
    letters = re.findall(r'\b([A-D])\b', a)
    pick = (m.group(1) if m else (letters[-1] if letters else None))
    return pick is not None and pick.upper() == str(gold).upper()

def g_code(ans, meta):
    a = strip_think(ans)
    m = re.search(r'```(?:python)?\s*(.*?)```', a, re.S)
    code = m.group(1) if m else a
    prog = code + "\n" + meta.get("test", "") + f"\ncheck({meta.get('entry_point','')})\n"
    try:
        r = subprocess.run([sys.executable, "-c", prog], capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False

rows = [json.loads(l) for l in open(EVAL, encoding='utf-8') if l.strip()]
by = defaultdict(list)
for r in rows: by[r["category"]].append(r)
results = []
for cat, items in by.items():
    for r in items[:N]:
        p = r["prompt"]
        if cat == "REASONING-MATH": p += "\n\nReason briefly, then end with exactly: 'The answer is <number>'."
        if cat == "KNOWLEDGE": p += "\n\nEnd with exactly: 'The answer is <letter>'."
        try:
            out, ct, dt, pt = ask(p, CAPS[cat])
        except Exception as e:
            out, ct, dt, pt = "[ERR " + str(e)[:80] + "]", 0, 0, 0
        ok = g_math(out, r["gold"]) if cat == "REASONING-MATH" else g_mcq(out, r["gold"]) if cat == "KNOWLEDGE" else g_code(out, r["meta"])
        truncated = ct >= CAPS[cat] - 2 and "</think>" not in out
        results.append({"id": r["id"], "cat": cat, "ok": bool(ok), "ct": ct, "dt": round(dt, 1),
                        "tps": round(ct/dt, 2) if dt else 0, "trunc": truncated, "out_tail": strip_think(out)[-200:]})
        print(f"{'OK ' if ok else 'XX '} {cat[:4]} {r['id'][:30]:30} {ct:>4}tok {dt:>4.0f}s {(ct/dt if dt else 0):>4.1f}t/s {'TRUNC' if truncated else ''}", flush=True)
json.dump(results, open("/workspace/eval_results.json", "w"), indent=1)
agg = defaultdict(lambda: [0, 0]); trunc = 0
for r in results:
    agg[r["cat"]][0] += int(r["ok"]); agg[r["cat"]][1] += 1; trunc += int(r["trunc"])
print("=== SUMMARY (ds4 IQ2_XXS 2-bit) ===")
for cat, (c, n) in agg.items(): print(f"  {cat}: {c}/{n} = {100*c/n:.0f}%")
tps = [r["tps"] for r in results if r["tps"]]
print(f"  avg t/s: {sum(tps)/len(tps):.2f}" if tps else "  n/a", f"| truncated(think-cutoff): {trunc}")
open("/workspace/EVAL_DONE", "w").close()
