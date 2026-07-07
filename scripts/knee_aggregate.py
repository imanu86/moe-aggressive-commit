"""Aggrega il sweep del ginocchio: grada L0-L3 (functional_grade), calcola aderenza
(selezioni ⊆ keep = mask attiva, auto-gate anti-inerte), rep-rate, t/s, hit.
Costruisce la tabella K -> livello funzionale.

Uso: python knee_aggregate.py <out_dir> <masks_dir>
  out_dir: gen_<tag>.log, route_<tag>.csv, summary.txt
  masks_dir: *.runtime.txt (righe "<layer> <expert>" = potato)
tag: full | reapK<K> | randK<K>
"""
import csv
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functional_grade import grade_frontpage  # noqa: E402

N_EXPERT = 256
OUT = sys.argv[1]
MASKS = sys.argv[2]


def keep_from_mask(mask_path):
    """keep[layer] = set esperti NON potati."""
    pruned = {}
    with open(mask_path) as f:
        for line in f:
            p = line.split()
            if len(p) == 2:
                l, e = int(p[0]), int(p[1])
                pruned.setdefault(l, set()).add(e)
    return {l: set(range(N_EXPERT)) - pr for l, pr in pruned.items()}


def aderenza(route_csv, keep):
    """frazione di selezioni che CADONO nei potati (violazioni). 0 = mask perfetta."""
    if not os.path.exists(route_csv):
        return None
    viol = tot = 0
    with open(route_csv) as f:
        rd = csv.reader(f)
        next(rd, None)
        for r in rd:
            if len(r) < 9:
                continue
            try:
                layer, n = int(r[1]), int(r[2])
            except ValueError:
                continue
            if layer not in keep:
                continue
            for s in range(min(n, 6)):
                try:
                    e = int(r[3 + s])
                except ValueError:
                    continue
                if e < 0:
                    continue
                tot += 1
                if e not in keep[layer]:
                    viol += 1
    return viol / tot if tot else None


def rep_rate(text):
    w = re.findall(r"\S+", text)
    g = [tuple(w[i:i + 4]) for i in range(len(w) - 3)]
    return 1 - len(set(g)) / len(g) if g else 0.0


def tag_to_KA(tag):
    m = re.match(r"(reap|rand)K(\d+)", tag)
    if m:
        return int(m.group(2)), ("reap" if m.group(1) == "reap" else "random")
    return (256, "full") if tag == "full" else (None, tag)


def mask_for_tag(tag):
    K, arm = tag_to_KA(tag)
    if arm == "reap":
        return f"{MASKS}/reap_keepK_{K}.runtime.txt"
    if arm == "random":
        return f"{MASKS}/random_keepK_{K}_seed0.runtime.txt"
    return None


rows = []
for gp in sorted(glob.glob(f"{OUT}/gen_*.log")):
    tag = re.match(r"gen_(.+)\.log", os.path.basename(gp)).group(1)
    K, arm = tag_to_KA(tag)
    txt = open(gp, encoding="utf-8", errors="ignore").read()
    lvl, det = grade_frontpage(txt)
    ts = re.findall(r"generation: *([0-9.]+) t/s", txt)
    hit = re.findall(r"hit_rate=([0-9.]+)", txt)
    mp = mask_for_tag(tag)
    ad = aderenza(f"{OUT}/route_{tag}.csv", keep_from_mask(mp)) if mp and os.path.exists(mp) else None
    rows.append(dict(tag=tag, K=K, arm=arm, level=lvl, ts=float(ts[-1]) if ts else None,
                     hit=float(hit[-1]) if hit else None, rep=rep_rate(txt), ader=ad,
                     jserr=det.get("js_errors"), btn=det.get("button_wired"),
                     form=det.get("form_wired"), gate="OK" if (ad is None or ad < 0.01) else f"INERTE({ad:.2f})"))

order = {"full": 0, "reap": 1, "random": 2}
rows.sort(key=lambda r: (order.get(r["arm"], 9), -(r["K"] or 0)))
print(f"{'tag':10} {'K':>3} {'arm':7} {'L':>2} {'t/s':>6} {'hit':>5} {'rep':>5} "
      f"{'aderenza':>9} {'JSerr':>5} {'btn':>4} {'form':>5} gate")
for r in rows:
    ts_s = f"{r['ts']:.1f}" if r["ts"] else "NA"
    hit_s = f"{r['hit']:.3f}" if r["hit"] else "NA"
    ad_s = f"{r['ader']:.3f}" if r["ader"] is not None else "NA"
    print(f"{r['tag']:10} {str(r['K']):>3} {r['arm']:7} L{r['level']:<1} "
          f"{ts_s:>6} {hit_s:>5} {r['rep']:.2f}  {ad_s:>8} "
          f"{str(r['jserr']):>5} {str(r['btn']):>4} {str(r['form']):>5} {r['gate']}")

reap = sorted([r for r in rows if r["arm"] == "reap"], key=lambda r: r["K"])
knee = None
for i, r in enumerate(reap):
    if r["level"] >= 2 and (i == 0 or reap[i - 1]["level"] < 2):
        pass
# ginocchio = K piu' basso che tiene L>=2 (feature presenti); sotto = rottura
holding = [r["K"] for r in reap if r["level"] >= 2]
knee = min(holding) if holding else None
print(f"\nGINOCCHIO (K piu' basso con L>=2, feature ancora presenti): {'keep-'+str(knee) if knee else 'nessuno tiene'}")
print("Sotto il ginocchio il bottone/JS si rompe (L1) o la pagina non si apre (L0).")
