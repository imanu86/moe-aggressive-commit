"""Confronta i corpi delle richieste salvati dal gateway (dump_haiku) e dice DOVE il prompt cambia.

Per ogni coppia di richieste consecutive della stessa sessione guarda, nell'ordine in cui finiscono nel
prompt (system, tools, messaggi), il primo elemento che differisce e ne mostra un ritaglio. Non stampa
mai i corpi interi. Uso: python confronta_corpi.py <cartella_dump>
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def pezzi(j: dict) -> list[tuple[str, str]]:
    out = []
    sistema = j.get("system")
    if isinstance(sistema, str):
        out.append(("system", sistema))
    else:
        for i, b in enumerate(sistema or []):
            out.append((f"system[{i}]", b.get("text", "")))
    for i, t in enumerate(j.get("tools") or []):
        out.append((f"tool[{i}] {t.get('name')}", json.dumps({k: v for k, v in t.items() if k != "cache_control"}, sort_keys=True, ensure_ascii=False)))
    for i, m in enumerate(j.get("messages") or []):
        c = m.get("content")
        if isinstance(c, str):
            out.append((f"msg[{i}] {m.get('role')}", c))
        else:
            for k, b in enumerate(c or []):
                b = {x: y for x, y in b.items() if x != "cache_control"}
                testo = b.get("text") if b.get("type") == "text" else json.dumps(b, sort_keys=True, ensure_ascii=False)
                out.append((f"msg[{i}] {m.get('role')} blocco[{k}] {b.get('type')}", testo or ""))
    return out


def main() -> int:
    cartella = Path(sys.argv[1])
    file = sorted(cartella.glob("*.json"))
    corpi = [(f.name, json.loads(f.read_text(encoding="utf-8"))) for f in file]
    for (na, a), (nb, b) in zip(corpi, corpi[1:]):
        pa, pb = pezzi(a), pezzi(b)
        car = 0
        print(f"\n== {na} ({len(pa)} pezzi, {sum(len(t) for _, t in pa)} caratteri)  ->  {nb} ({len(pb)} pezzi)")
        for i, ((ea, ta), (eb, tb)) in enumerate(zip(pa, pb)):
            if ea == eb and ta == tb:
                car += len(ta)
                continue
            k = next((x for x, (u, v) in enumerate(zip(ta, tb)) if u != v), min(len(ta), len(tb)))
            print(f"   primo stacco al pezzo {i}: «{ea}» contro «{eb}» | caratteri identici prima: {car + k} "
                  f"(~{(car + k) // 4} token a 4 caratteri/token)")
            print(f"     prima : …{ta[max(0, k - 80):k + 160]!r}")
            print(f"     dopo  : …{tb[max(0, k - 80):k + 160]!r}")
            break
        else:
            print(f"   prefisso identico: la seconda richiesta aggiunge {len(pb) - len(pa)} pezzi in coda")
    return 0


if __name__ == "__main__":
    sys.exit(main())
