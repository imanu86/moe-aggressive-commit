#!/usr/bin/env python3
"""Verdetto appaiato ON vs OFF da due log ds4-eval (--plain).

Estrae la tabella risultati per-domanda, appaia per NOME del test (non per indice),
calcola concordanze/discordanze e il test esatto di McNemar (binomiale two-sided
sulle coppie discordanti). Output: tabella + verdetto.

Uso: python paired_verdict.py eval_off2.log eval_on.log
"""
import re
import sys
from math import comb

ROW = re.compile(r"^\s+\d+\s+(PASSED|FAILED)\s+.*?\s(\S+)\s*$")


def load(path):
    out = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.replace("\x00", "").rstrip("\r\n")
        m = ROW.match(line)
        if m:
            out[m.group(2)] = m.group(1) == "PASSED"
    return out


def mcnemar_exact(b, c):
    """p two-sided del binomiale(b; b+c, 0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    off_path, on_path = sys.argv[1], sys.argv[2]
    off, on = load(off_path), load(on_path)
    common = sorted(set(off) & set(on))
    if len(common) != len(off) or len(common) != len(on):
        print(f"ATTENZIONE: set non identici (off={len(off)} on={len(on)} comuni={len(common)})")
    both_p = sum(1 for k in common if off[k] and on[k])
    both_f = sum(1 for k in common if not off[k] and not on[k])
    on_only = sum(1 for k in common if on[k] and not off[k])
    off_only = sum(1 for k in common if off[k] and not on[k])
    p = mcnemar_exact(on_only, off_only)

    print(f"domande appaiate: {len(common)}")
    print(f"OFF: {sum(off[k] for k in common)}/{len(common)}  ON: {sum(on[k] for k in common)}/{len(common)}")
    print(f"concordanti: entrambi-pass={both_p} entrambi-fail={both_f}")
    print(f"discordanti: solo-ON={on_only} solo-OFF={off_only}")
    print(f"McNemar esatto (two-sided): p = {p:.4f}")
    print("dettaglio discordanti:")
    for k in common:
        if off[k] != on[k]:
            print(f"  {'ON+' if on[k] else 'OFF+'} {k}")
    verdict = "EQUIVALENZA NON RIFIUTATA" if p > 0.05 else "DIFFERENZA SIGNIFICATIVA"
    direction = "" if on_only == off_only else (" (direzione: ON meglio)" if on_only > off_only else " (direzione: OFF meglio)")
    print(f"VERDETTO: {verdict}{direction}")


if __name__ == "__main__":
    main()
