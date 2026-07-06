"""Scoring field-accuracy dei draft Segnali vs gold (regole di eval_extract.py):
categorici (technique/variance/validity) = exact match; numerici (cap_eur/rollover_x/
cashback_pct/stake_min_eur) = tolleranza 0.01, null==null match, null vs valore = errore.
Metrica ledger: overall_excl_validity (6 campi). JSON estratto con la stessa regex.

Uso: python score_segnali.py <dir_con_gen_*.log> [config...]  (default: full k50 k91 2step)
"""
import json
import re
import sys
from collections import defaultdict

NUM_FIELDS = ["cap_eur", "rollover_x", "cashback_pct", "stake_min_eur"]
CAT_FIELDS = ["technique", "variance", "validity"]
GOLD = json.load(open(__file__.replace("score_segnali.py", "gold.json"), encoding="utf-8"))


def clean_text(path):
    raw = open(path, "rb").read().decode("utf-8", "replace").replace("\r", "\n")
    t = "\n".join(l for l in raw.split("\n")
                  if not (l.startswith("ds4:") or "prefill layer" in l or l.startswith("=== ")))
    return re.sub(r"ds4: REAP mask [^\n]*", "", t)


def parse_json(text):
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def num_eq(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return False


def main():
    d = sys.argv[1]
    configs = sys.argv[2:] or ["full", "k50", "k91", "2step"]
    print(f"{'config':8} {'parse':>6} {'overall_excl_val':>17} {'technique':>10} "
          f"{'variance':>9} {'numerici':>9}")
    results = {}
    for cfg in configs:
        per_field = defaultdict(lambda: [0, 0])
        parsed = 0
        n = 0
        for name, gold in GOLD.items():
            base = name.replace(".txt", "")
            try:
                text = clean_text(f"{d}/gen_{cfg}_{base}.log")
            except FileNotFoundError:
                continue
            n += 1
            pred = parse_json(text)
            if pred is None:
                for f in CAT_FIELDS + NUM_FIELDS:
                    per_field[f][1] += 1
                continue
            parsed += 1
            for f in CAT_FIELDS:
                per_field[f][1] += 1
                per_field[f][0] += int(str(pred.get(f)) == str(gold.get(f)))
            for f in NUM_FIELDS:
                per_field[f][1] += 1
                per_field[f][0] += int(num_eq(pred.get(f), gold.get(f)))
        if n == 0:
            print(f"{cfg:8} (nessun file)")
            continue
        excl = [f for f in CAT_FIELDS + NUM_FIELDS if f != "validity"]
        ov = sum(per_field[f][0] for f in excl) / max(sum(per_field[f][1] for f in excl), 1)
        tech = per_field["technique"]
        var = per_field["variance"]
        nums = [per_field[f] for f in NUM_FIELDS]
        num_acc = sum(x[0] for x in nums) / max(sum(x[1] for x in nums), 1)
        results[cfg] = {"n": n, "parsed": parsed, "overall_excl_validity": round(ov, 3),
                        "technique": round(tech[0] / max(tech[1], 1), 3),
                        "variance": round(var[0] / max(var[1], 1), 3),
                        "numerici": round(num_acc, 3)}
        print(f"{cfg:8} {parsed:>3}/{n:<3} {ov:>17.3f} "
              f"{tech[0]/max(tech[1],1):>10.3f} {var[0]/max(var[1],1):>9.3f} {num_acc:>9.3f}")
    json.dump(results, open(f"{d}/scores.json", "w"), indent=1)
    print(f"\nscores.json scritto in {d}")


if __name__ == "__main__":
    main()
