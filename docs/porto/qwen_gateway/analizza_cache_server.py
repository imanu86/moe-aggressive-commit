"""Quanta cache del prompt riusa davvero un client? Legge i log di llama-server (-lv 4).

Per ogni richiesta ricava: token del prompt, token ripresi dalla cache, token davvero rifatti, se il
server ha dovuto ripartire da un checkpoint o da zero («forcing full prompt re-processing») e a che
profondita' il prompt nuovo si e' staccato da quello in cache («against N»).

Uso: python analizza_cache_server.py <log> [<log> ...]
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

NUOVO = re.compile(r"task (-?\d+) \| new prompt, .*task\.n_tokens = (\d+)")
CACHE = re.compile(r"task (-?\d+) \| cached n_tokens = (\d+)")
CONTRO = re.compile(r"task (-?\d+) \| checking checkpoint with \[(\d+), (\d+)\] against (\d+)")
ZERO = re.compile(r"task (-?\d+) \| forcing full prompt re-processing")
RIPRESO = re.compile(r"task (-?\d+) \| restored context checkpoint .*pos_max = (\d+)")
TEMPO = re.compile(r"task (-?\d+) \|\s+prompt eval time =\s+([\d.]+) ms /\s+(\d+) tokens")


def analizza(percorso: Path) -> list[dict]:
    rich: dict[str, dict] = {}
    ordine: list[str] = []
    for riga in percorso.open(encoding="utf-8", errors="replace"):
        if (m := NUOVO.search(riga)):
            rich[m.group(1)] = {"task": m.group(1), "prompt": int(m.group(2)), "cache": 0, "da_zero": False,
                                "checkpoint": None, "stacco": None, "rifatti": None, "ms": None}
            ordine.append(m.group(1))
        elif (m := CACHE.search(riga)) and m.group(1) in rich:
            if "visto" not in rich[m.group(1)]:  # vale la PRIMA: le successive sono solo l'avanzamento del prefill
                rich[m.group(1)]["cache"], rich[m.group(1)]["visto"] = int(m.group(2)), True
        elif (m := CONTRO.search(riga)) and m.group(1) in rich:
            rich[m.group(1)]["stacco"] = int(m.group(4))
        elif (m := ZERO.search(riga)) and m.group(1) in rich:
            rich[m.group(1)]["da_zero"] = True
        elif (m := RIPRESO.search(riga)) and m.group(1) in rich:
            rich[m.group(1)]["checkpoint"] = int(m.group(2))
        elif (m := TEMPO.search(riga)) and m.group(1) in rich:
            rich[m.group(1)]["ms"], rich[m.group(1)]["rifatti"] = float(m.group(2)), int(m.group(3))
    return [rich[t] for t in ordine]


def main() -> int:
    for nome in sys.argv[1:]:
        r = [x for x in analizza(Path(nome)) if x["rifatti"] is not None]
        if not r:
            print(f"{Path(nome).name}: nessuna richiesta completa")
            continue
        grandi = [x for x in r if x["prompt"] >= 8000]
        tot_prompt, tot_rifatti = sum(x["prompt"] for x in r), sum(x["rifatti"] for x in r)
        print(f"\n== {Path(nome).name}")
        print(f"richieste {len(r)} | prompt medio {tot_prompt // len(r)} token | riuso della cache {1 - tot_rifatti / tot_prompt:.1%} "
              f"| tempo di prefill totale {sum(x['ms'] for x in r) / 1e3:.0f} s")
        if grandi:
            freddi = [x for x in grandi if x["cache"] == 0]
            da_zero = [x for x in grandi if x["da_zero"]]
            da_ck = [x for x in grandi if x["checkpoint"] is not None and not x["da_zero"]]
            print(f"prompt >= 8k: {len(grandi)} | partiti senza cache: {len(freddi)} (di cui costretti da zero per prefisso "
                  f"cambiato: {len(da_zero)}) | ripresi da un checkpoint: {len(da_ck)}")
            costosi = sorted((x for x in grandi if x["rifatti"] >= 4000), key=lambda x: -x["rifatti"])[:8]
            for x in costosi:
                motivo = ("prefisso cambiato al token %d, nessun checkpoint prima" % x["stacco"] if x["da_zero"] and x["stacco"] is not None
                          else "ripreso dal checkpoint a %d (stacco a %s)" % (x["checkpoint"], x["stacco"]) if x["checkpoint"] is not None
                          else "cache vuota o altra conversazione" if x["cache"] == 0 else "coda nuova")
                print(f"   prompt {x['prompt']:>7} | in cache {x['cache']:>7} | rifatti {x['rifatti']:>7} in {x['ms'] / 1e3:6.1f} s | {motivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
