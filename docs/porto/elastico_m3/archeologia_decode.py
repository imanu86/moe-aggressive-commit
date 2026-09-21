"""Archeologia del decode: da un log di llama-server, con quale modello/slot girava e a che ritmo generava.

  python archeologia_decode.py <log> [<log> ...]

Per ogni log: modello, slot della cache esperti, MTP, colpi, e le generazioni da almeno 100 token raggruppate per
profondita' del contesto (token del prompt al momento della generazione): mediana e massimo dei t/s.
"""
import re
import statistics
import sys
from pathlib import Path

ansi = re.compile(r"\x1b\[[0-9;]*m")
SECCHI = [(0, 16000), (16000, 48000), (48000, 80000), (80000, 112000), (112000, 10**9)]


def analizza(path: Path) -> None:
    modello = slots = None
    spec = "?"
    prompt_di = {}
    gen = []  # (contesto, token, tps)
    colpi = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for riga in f:
            riga = ansi.sub("", riga)
            if modello is None and "general.name" in riga:
                modello = riga.split("=", 1)[-1].strip()
            if "llama_model_loader: loaded meta data" in riga or "print_info: file size" in riga:
                pass
            m = re.search(r"MoE expert cache enabled: (\d+) layers x (\d+) slots", riga)
            if m:
                slots = m.group(2) + " fissi"
            m = re.search(r"moe-elastic: enabled min=(\d+) max=(\d+)", riga)
            if m:
                slots = "elastico"
            if "print_info: file size" in riga:
                modello = (modello or "") + " | " + riga.split("=", 1)[-1].strip()
            m = re.search(r"task (\d+) \| new prompt.*task\.n_tokens = (\d+)", riga)
            if m:
                prompt_di[m.group(1)] = int(m.group(2))
            m = re.search(r"task (\d+) \|\s+eval time =\s+([\d.]+) ms /\s+(\d+) tokens.*?([\d.]+) tokens per second", riga)
            if m and "prompt eval" not in riga:
                gen.append((prompt_di.get(m.group(1), -1), int(m.group(3)), float(m.group(4))))
            m = re.search(r"colpi ([\d.]+)%", riga)
            if m:
                colpi.append(float(m.group(1)))
            if "draft" in riga and "acceptance" in riga:
                spec = "MTP/bozza attiva"
    lunghe = [g for g in gen if g[1] >= 100]
    print(f"\n=== {path.name}")
    print(f"    modello: {modello} | slot: {slots} | speculazione: {spec} | colpi (mediana dei rapporti): "
          f"{statistics.median(colpi):.1f}%" if colpi else f"    modello: {modello} | slot: {slots} | speculazione: {spec}")
    print(f"    generazioni: {len(gen)}, di cui da almeno 100 token: {len(lunghe)}")
    for lo, hi in SECCHI:
        s = [g[2] for g in lunghe if lo <= g[0] < hi]
        if s:
            print(f"      contesto {lo//1000:>3}-{'oltre' if hi > 10**8 else str(hi//1000)+'k':<6} n={len(s):3d}  mediana {statistics.median(s):5.2f}  "
                  f"p90 {sorted(s)[int(0.9*(len(s)-1))]:5.2f}  max {max(s):5.2f} t/s")


for nome in sys.argv[1:]:
    analizza(Path(nome))
