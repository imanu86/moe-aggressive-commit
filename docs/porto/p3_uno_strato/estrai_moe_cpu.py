#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 - estrae dal log del server le righe del ramo CPU e ne fa un riassunto.

    python estrai_moe_cpu.py <log_del_server> [--copia <destinazione>]

Nessuna API key compare mai nel log del server (il banco non la passa sulla riga
di comando del log), ma la copia viene comunque filtrata per prudenza.
"""
import argparse
import re
import sys

CHIAVI = ("moe cpu:", "moe cpu [", "moe cache:", "esecutore CPU degli esperti",
          "moe-cache:", "CONTAMINATO")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--copia")
    a = ap.parse_args()

    righe = []
    with open(a.log, encoding="utf-8", errors="replace") as f:
        for r in f:
            if any(k in r for k in CHIAVI):
                righe.append(r.rstrip("\n"))

    # redazione di prudenza: qualunque cosa somigli a una chiave lunga
    red = [re.sub(r"(api[-_ ]?key\S*[=: ]+)\S+", r"\1<REDATTA>", r, flags=re.I) for r in righe]

    for r in red:
        print(r)

    if a.copia:
        with open(a.copia, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(red) + "\n")
        print("\n[scritte %d righe in %s]" % (len(red), a.copia), file=sys.stderr)

    # riassunto delle ultime righe di contatori
    ultima = [r for r in red if "moe cpu: strato" in r]
    if ultima:
        print("\n--- ultima riga di contatori ---")
        print(ultima[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
