"""P11 - cancello di qualita': conta gli aghi ritrovati in una corsa del profilo aghi_131k.

Regola: la stringa attesa deve comparire nella RISPOSTA FINALE (content), non solo nel
ragionamento; si riporta comunque anche il caso "solo nel ragionamento", che non conta
come superato ma spiega un eventuale troncamento.

Uso:  python aghi_p11.py <cartella_corsa>
"""
import json
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "banco_p0" / "fixtures"


def main():
    d = Path(sys.argv[1])
    man = json.loads((FIX / "fixtures_manifest.json").read_text(encoding="utf-8"))
    atteso = {c["id"]: c.get("atteso") for c in man["casi"]}
    ris = [json.loads(r) for r in (d / "results.jsonl").read_text(encoding="utf-8").splitlines() if r.strip()]
    ok = tot = 0
    for r in ris:
        if r.get("riscaldamento"):
            continue
        cid = r["caso"]
        a = atteso.get(cid)
        if not a:
            continue
        base = r["etichetta"].replace("@", "_")
        content = (d / "output" / (base + ".content.txt")).read_text(encoding="utf-8")
        reason = (d / "output" / (base + ".reasoning.txt")).read_text(encoding="utf-8")
        if a["tipo"] == "contiene":
            termini = [a["valore"]]
        else:
            termini = a["termini"]
        in_finale = all(t in content for t in termini)
        in_ragion = all(t in (content + reason) for t in termini)
        tot += 1
        ok += 1 if in_finale else 0
        print("%-10s atteso %-45s finale=%-5s (anche_nel_ragionamento=%-5s) pred=%-5s fine=%-8s "
              "content_car=%d" % (cid, "|".join(termini), in_finale, in_ragion,
                                  r.get("predicted_n"), r.get("motivo_fine"),
                                  r.get("content_caratteri")))
    print("RISULTATO: %d/%d nella risposta finale" % (ok, tot))


if __name__ == "__main__":
    main()
