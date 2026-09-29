"""Riassume gli eventi della cache elastica M2 dal log del daily di laboratorio."""
import json
import re
import sys

slots, eventi, ssd = [], {}, None
azzerate = 0
for riga in open(sys.argv[1], encoding="utf-8", errors="replace"):
    m = re.search(r'moe-elastic-json (\{.*\})', riga)
    if m:
        try:
            ev = json.loads(m.group(1))
        except Exception:
            continue
        nome = ev.get("event")
        eventi[nome] = eventi.get(nome, 0) + 1
        if nome == "sample":
            slots.append(ev.get("slots", 0))
        if nome == "resize" and ev.get("slots") == 0 and ev.get("old_slots", 0) > 0:
            azzerate += 1
    m = re.search(r'RAM_STORE \{.*?"SSDreads":(\d+),"SSDbytes":(\d+)', riga)
    if m:
        ssd = (int(m.group(1)), int(m.group(2)))
n = len(slots)
zero = sum(1 for s in slots if s == 0)
print("campioni: %d; a 0 slot: %d (%.0f%%); slot medi %.1f, max %d" % (n, zero, 100.0 * zero / n, sum(slots) / n, max(slots)))
print("cache svuotata a 0 (resize da >0 a 0): %d volte" % azzerate)
print("eventi:", ", ".join("%s=%d" % kv for kv in sorted(eventi.items(), key=lambda x: -x[1])))
if ssd:
    print("letture SSD del deposito RAM: %d, %.0f MB" % (ssd[0], ssd[1] / 2**20))
