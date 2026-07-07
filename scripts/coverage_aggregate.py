"""Aggrega la coverage-sweep: per (task, COV%) -> K-auto scelto + livello L0-L3 + t/s.
Risponde: una copertura FISSA riproduce i ginocchi task-dipendenti? qual e' la copertura
UNIVERSALE (COV% minimo che da' L3 su tutti i task)?

Uso: python coverage_aggregate.py <base_dir>
  base_dir contiene cov_<task>/out/ con deliverable_<COV>.html, summary.txt, p2_<COV>.diag
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functional_grade import grade_frontpage, grade_python, grade_json  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "."
COVS = [80, 85, 90, 95]
TASKS = ["json", "python", "frontpage"]

PY_TESTS = [
    (([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]),
    (([[1, 4], [4, 5]],), [[1, 5]]),
    (([],), []),
    (([[1, 4], [0, 4]],), [[0, 4]]),
    (([[1, 4], [2, 3]],), [[1, 4]]),
]
JSON_KEYS = ["name", "age", "email", "city"]
JSON_EXP = {"name": "Maria Rossi", "age": 34, "email": "maria.rossi@example.com", "city": "Milan"}


def grade(task, txt):
    if task == "python":
        return grade_python(txt, unit_tests=PY_TESTS, func_name="merge_intervals")
    if task == "json":
        return grade_json(txt, required_keys=JSON_KEYS, expected=JSON_EXP)
    return grade_frontpage(txt)


def kauto(summary, cov):
    # riga "coverage 90% ...: K-auto medio 49.0/layer ..."
    for line in summary.splitlines():
        m = re.search(rf"coverage {cov}%.*K-auto medio ([0-9.]+)", line)
        if m:
            return float(m.group(1))
    return None


results = {}
for task in TASKS:
    d = f"{BASE}/cov_{task}/out"
    if not os.path.isdir(d):
        continue
    summ = open(f"{d}/summary.txt", encoding="utf-8", errors="ignore").read() if os.path.exists(f"{d}/summary.txt") else ""
    for cov in COVS:
        dp = f"{d}/deliverable_{cov}.html"
        if not os.path.exists(dp):
            continue
        txt = open(dp, encoding="utf-8", errors="ignore").read()
        lvl, _ = grade(task, txt)
        diag = f"{d}/p2_{cov}.diag"
        ts = None
        if os.path.exists(diag):
            m = re.findall(r"generation: *([0-9.]+) t/s", open(diag, errors="ignore").read())
            ts = float(m[-1]) if m else None
        results[(task, cov)] = (kauto(summ, cov), lvl, ts)

print(f"{'task':10} {'COV%':>5} {'K-auto':>7} {'livello':>7} {'t/s':>6}")
for task in TASKS:
    for cov in COVS:
        if (task, cov) in results:
            k, lvl, ts = results[(task, cov)]
            print(f"{task:10} {cov:>5} {(f'{k:.1f}' if k else 'NA'):>7} {'L'+str(lvl):>7} "
                  f"{(f'{ts:.1f}' if ts else 'NA'):>6}")

# copertura universale = COV minimo con L3 su tutti i task presenti
present_tasks = sorted({t for (t, c) in results})
print("\n=== copertura UNIVERSALE (COV minimo con L3 su tutti) ===")
for cov in COVS:
    lvls = {t: results[(t, cov)][1] for t in present_tasks if (t, cov) in results}
    allL3 = lvls and all(v >= 3 for v in lvls.values())
    allL2 = lvls and all(v >= 2 for v in lvls.values())
    tag = "TUTTI L3" if allL3 else ("tutti >=L2" if allL2 else "no")
    print(f"  COV {cov}%: {lvls} -> {tag}")
