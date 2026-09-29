"""Costo per passata di verifica di Strata dai suoi log, 29/9/2026.

Il testo generato cambia con la residenza degli esperti (GPU e CPU arrotondano diversamente), quindi i t/s grezzi
mescolano il costo della passata con l'accettazione della bozza. Qui si separano: per ogni richiesta con piu' di 100
token generati, passate = generati - bozze accettate, righe = passate + bozze offerte (ogni passata verifica la riga
vera piu' le bozze), ms per passata, ms per riga, token per passata.

Uso:  python costo_passata.py etichetta=percorso.log [etichetta=percorso.log ...]
"""
import re
import sys

RIGA = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read .*?, (\d+) generated in (\d+) ms .*?"
                  r"drafts accepted (\d+) of (\d+)")


def main():
    print("%-12s %4s %7s %9s %8s %10s %8s %6s" % ("cache", "caso", "prompt", "tok/pass", "ms/pass", "righe/pass",
                                                  "ms/riga", "t/s"))
    for arg in sys.argv[1:]:
        nome, percorso = arg.split("=", 1)
        n = 0
        tot_ms = tot_rows = tot_pass = tot_gen = 0
        for riga in open(percorso, encoding="utf-8", errors="replace"):
            m = RIGA.search(riga)
            if not m:
                continue
            prompt, _, _, gen, ms, acc, off = (int(x) for x in m.groups())
            if gen <= 100:
                continue
            n += 1
            passate = gen - acc
            righe = passate + off
            tot_ms += ms; tot_rows += righe; tot_pass += passate; tot_gen += gen
            print("%-12s %4d %7d %9.2f %8.1f %10.2f %8.1f %6.1f" % (nome, n, prompt, gen / passate, ms / passate,
                                                                   righe / passate, ms / righe, gen / (ms / 1000)))
        if n:
            print("%-12s  TOT %7s %9.2f %8.1f %10.2f %8.1f %6.1f" % (nome, "", tot_gen / tot_pass, tot_ms / tot_pass,
                                                                    tot_rows / tot_pass, tot_ms / tot_rows,
                                                                    tot_gen / (tot_ms / 1000)))


if __name__ == "__main__":
    main()
