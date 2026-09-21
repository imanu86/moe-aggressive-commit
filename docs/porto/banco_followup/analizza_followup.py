"""Legge una corsa di banco_followup.py e stampa la matrice profondita' x taglia.

Uso: python analizza_followup.py D:\\ds4_work\\banco_followup_run\\<corsa> [--md]

Tempo di prefill = `timings.prompt_ms` del server; i token sono quelli davvero
valutati (`prompt_n`: il follow-up piu' il template e i pochi token rifatti dopo
il rollback al checkpoint). Per ogni passo riporta anche le riserve dell'area di
lavoro («demand workspace tokens=… kv=…») cadute nella finestra della richiesta:
le marche del log del server sono relative al suo avvio, `orologio.json` le
aggancia all'orologio del runner.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

RISERVA = re.compile(r"^(\d+(?:\.\d+)+) \w +sched_reserve\w*: demand workspace tokens=(\d+) kv=(\d+)")


def secondi(marca: str) -> float:
    p = [int(x) for x in marca.split(".")]
    us, ms, s = p[-1], p[-2], p[-3]
    m = p[-4] if len(p) >= 4 else 0
    h = p[-5] if len(p) >= 5 else 0
    return h * 3600 + m * 60 + s + ms / 1e3 + us / 1e6


def main() -> int:
    run = Path(sys.argv[1])
    md = "--md" in sys.argv
    passi = [json.loads(l) for l in (run / "passi.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    t_avvio = json.loads((run / "orologio.json").read_text(encoding="utf-8"))["t_avvio_server_qpc"]
    riserve = []
    for line in (run / "logs" / "server.stderr.txt").open(encoding="utf-8", errors="replace"):
        m = RISERVA.match(line)
        if m and int(m.group(2)) > 8:  # le riserve da 3-6 token sono il decode
            riserve.append((t_avvio + secondi(m.group(1)), int(m.group(2)), int(m.group(3))))

    righe = []
    for p in passi:
        tm = p["timings"]
        dentro = [f"{tok}@{kv // 1024}k" for t, tok, kv in riserve if p["t0_qpc"] - 0.3 <= t <= p["t1_qpc"]]
        s = tm["prompt_ms"] / 1e3
        righe.append({**p, "prompt_n": tm["prompt_n"], "prefill_s": s, "tps": tm["prompt_n"] / s,
                      "decode_tps": tm.get("predicted_per_second", 0.0), "riserve": " ".join(dentro) or "-"})

    testa = ["passo", "liv", "tipo", "contesto", "chiesti", "valutati", "prefill s", "muro s", "t/s", "riserve ubatch@kv"]
    if md:
        print("| " + " | ".join(testa) + " |")
        print("|" + "---|" * len(testa))
    else:
        print("  ".join(testa))
    for r in righe:
        campi = [str(r["passo"]), str(r["livello"]),
                 ("riemp." if r["tipo"] == "riempimento" else "cella") + ("*" if r.get("ripetuta") else ""),
                 str(r["contesto_prima"]), str(r["token_chiesti"]), str(r["prompt_n"]), f"{r['prefill_s']:.2f}",
                 f"{r['muro_s']:.2f}", f"{r['tps']:.0f}", r["riserve"]]
        print(("| " + " | ".join(campi) + " |") if md else "  ".join(campi))

    celle = [r for r in righe if r["tipo"] == "cella"]
    taglie = sorted({r["token"] for r in celle})
    livelli = sorted({r["livello"] for r in celle})
    for titolo, valore, fmt in (
            ("PREFILL (s) per follow-up — righe: contesto a inizio livello; colonne: token del follow-up",
             lambda v: sum(c["prefill_s"] for c in v) / len(v), "{:>9.2f}"),
            ("T/S APPARENTI (token valutati / tempo di prefill)",
             lambda v: sum(c["prompt_n"] for c in v) / sum(c["prefill_s"] for c in v), "{:>9.0f}")):
        print()
        print(titolo)
        riga = f"{'contesto':>9}" + "".join(f"{t:>9}" for t in taglie)
        if md:
            print("| contesto | " + " | ".join(str(t) for t in taglie) + " |")
            print("|" + "---|" * (len(taglie) + 1))
        else:
            print(riga)
        for lv in livelli:
            del_livello = [c for c in celle if c["livello"] == lv]
            inizio = min(c["contesto_prima"] for c in del_livello)
            valori = []
            for t in taglie:
                v = [c for c in del_livello if c["token"] == t]
                valori.append(fmt.format(valore(v)).strip() if v else "-")
            if md:
                print(f"| {inizio} | " + " | ".join(valori) + " |")
            else:
                print(f"{inizio:>9}" + "".join(f"{x:>9}" for x in valori))

    rip = []
    for lv in livelli:
        for t in (256, 1024):
            v = [c["prefill_s"] for c in celle if c["livello"] == lv and c["token"] == t]
            if len(v) == 2:
                rip.append(abs(v[0] - v[1]) / (sum(v) / 2))
    if rip:
        print()
        print(f"Rumore sulle celle ripetute (|a-b|/media): mediano {sorted(rip)[len(rip) // 2]:.1%}, massimo {max(rip):.1%}")
    dec = [r["decode_tps"] for r in righe if r["decode_tps"]]
    if dec:
        print(f"Decode sugli 8 token fra un prefill e l'altro: da {dec[0]:.1f} t/s a {dec[-1]:.1f} t/s (indicativo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
