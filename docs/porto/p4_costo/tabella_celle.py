#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4 - tabella delle celle: ms per token del server, delta su C0, impronte.

Il tempo per token e' `predicted_ms / predicted_n` aggregato somma/somma sui
casi misurati (esclusi i due riscaldamenti), come prescrive il protocollo. Il
banco e' deterministico in greedy: l'impronta del testo e' l'oracolo.

    python tabella_celle.py [--run D:\\ds4_work\\banco_p0_run]
"""
import argparse
import json
from pathlib import Path

RIF_CELLA = "C0"


def leggi(cartella):
    ris = []
    for riga in (Path(cartella) / "results.jsonl").read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if riga:
            ris.append(json.loads(riga))
    utili = [r for r in ris if not r.get("riscaldamento") and r.get("valido", True)]
    tok = sum((r["predicted_n"] or 0) for r in utili)
    ms = sum((r["predicted_ms"] or 0) for r in utili)
    return {
        "cartella": Path(cartella).name,
        "token": tok,
        "ms": ms,
        "ms_per_token": ms / tok if tok else None,
        "tps": 1000.0 * tok / ms if ms else None,
        "impronte": {r["etichetta"]: (r.get("impronta_testo_sha256") or "")[:16] for r in ris},
        "per_caso": {r["etichetta"]: (r["predicted_ms"] / r["predicted_n"])
                     for r in utili if r.get("predicted_n")},
    }


def cella_di(nome):
    # 20260914_105030_P4_p4_c0_spento_r1 -> C0
    parte = nome.split("_P4_p4_")
    if len(parte) != 2:
        return None
    return parte[1].split("_")[0].upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=r"D:\ds4_work\banco_p0_run")
    a = ap.parse_args()

    corse = {}
    for d in sorted(Path(a.run).glob("*_P4_p4_*")):
        if not (d / "results.jsonl").exists():
            continue
        c = cella_di(d.name)
        if not c:
            continue
        corse.setdefault(c, []).append(leggi(d))

    rif = None
    if RIF_CELLA in corse:
        rif = sum(x["ms_per_token"] for x in corse[RIF_CELLA]) / len(corse[RIF_CELLA])

    ordine = sorted(corse, key=lambda c: (len(c), c))
    print("%-5s %-42s %7s %10s %9s %9s  %s" %
          ("cella", "corsa", "token", "ms/token", "delta C0", "t/s", "impronte L01/S01"))
    for c in ordine:
        for x in corse[c]:
            d = "" if rif is None else "%+9.3f" % (x["ms_per_token"] - rif)
            imp = "%s %s" % (x["impronte"].get("L01@corto", "-"),
                             x["impronte"].get("S01@corto", "-"))
            print("%-5s %-42s %7d %10.3f %9s %9.3f  %s" %
                  (c, x["cartella"], x["token"], x["ms_per_token"], d, x["tps"], imp))
    if rif is not None:
        print("\nriferimento C0 = %.3f ms/token" % rif)
    # impronte: elenco di quelle diverse dal riferimento C0
    if RIF_CELLA in corse:
        base = corse[RIF_CELLA][0]["impronte"]
        print("\nimpronte diverse da C0:")
        for c in ordine:
            for x in corse[c]:
                div = [k for k, v in x["impronte"].items() if base.get(k) and v != base[k]]
                print("  %-5s %-42s %s" % (c, x["cartella"], ", ".join(div) if div else "nessuna"))


if __name__ == "__main__":
    main()
