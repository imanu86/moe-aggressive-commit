"""Uso reale: per ogni generazione, quanti resize a meta' decode e quanta parte dell'eval time in pausa."""
import json
import re
import sys

ansi = re.compile(r"\x1b\[[0-9;]*m")


def t_us(s):
    m, s2, ms, us = s.split(".")
    return ((int(m) * 60 + int(s2)) * 1000 + int(ms)) * 1000 + int(us)


ev, gen = [], []
with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
    for riga in f:
        riga = ansi.sub("", riga.rstrip("\n"))
        ts = riga[:13].strip()
        if not re.match(r"^\d+\.\d\d\.\d{3}\.\d{3}$", ts):
            continue
        i = riga.find("moe-elastic-json ")
        if i >= 0:
            try:
                e = json.loads(riga[i + 17:])
                e["_us"] = t_us(ts)
                ev.append(e)
            except Exception:
                pass
        elif " eval time =" in riga and "prompt eval" not in riga:
            m = re.search(r"eval time =\s+([\d.]+) ms /\s+(\d+) tokens", riga)
            gen.append((t_us(ts), float(m.group(1)), int(m.group(2))))

resize = [e for e in ev if e["event"] == "resize"]
prima = [e for e in ev if e["event"] == "before_resize"]
pronto = [e for e in ev if e["event"] == "workspace_ready"]
tot_eval = tot_pausa = 0.0
tot_meta = 0
for t_fine, eval_ms, ntok in gen:
    t_ini = t_fine - int(eval_ms * 1000)
    dentro = [r for r in resize if t_ini <= r["_us"] <= t_fine]
    meta = [r for r in dentro if r["reason"] == "budget" and r["old_slots"] > 30]
    pausa = 0.0
    for b in prima:
        if t_ini <= b["_us"] <= t_fine:
            dopo = [p for p in pronto if p["_us"] >= b["_us"]]
            if dopo:
                pausa += (dopo[0]["_us"] - b["_us"]) / 1000
    taglie = [r["slots"] for r in dentro]
    print(f'{ntok:5d} tok  {ntok/(eval_ms/1000):5.2f} t/s  eval {eval_ms/1000:7.1f} s | resize {len(dentro):3d} (a meta\' decode {len(meta):3d}) | '
          f'pause {pausa/1000:6.1f} s = {100*pausa/eval_ms:5.1f}% | un resize ogni {eval_ms/1000/max(1,len(meta)):5.1f} s | taglie {min(taglie) if taglie else "-"}..{max(taglie) if taglie else "-"}')
    tot_eval += eval_ms
    tot_pausa += pausa
    tot_meta += len(meta)
print(f'\nTOTALE: eval {tot_eval/1000:.0f} s, pause misurate {tot_pausa/1000:.1f} s = {100*tot_pausa/tot_eval:.1f}%, resize a meta\' decode {tot_meta}')
passi = [abs(r["slots"] - r["old_slots"]) for r in resize if r["reason"] == "budget" and r["old_slots"] > 30]
from collections import Counter
print("ampiezza dei resize a meta' decode (slot -> quanti):", dict(sorted(Counter(passi).items())))
