#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4, seconda cella - riassume le corse della cella di estensione.

Legge le cartelle di corsa di `D:\\ds4_work\\banco_p0_run` che appartengono alla
fase `P4-estensione`, ne ricava ms/token e t/s e confronta le impronte con la
corsa presa come riferimento.

    python tabella_celle.py [--root D:\\ds4_work\\banco_p0_run] [--rif <corsa>]

Il ms/token si ricava da `tutti_i_casi_misurati` (tempo di generazione diviso
token accettati): e' la stessa definizione usata da P4-costo, cosi' le due
tabelle si confrontano senza tradurre niente. Il t/s dell'insieme libero e'
invece `insieme_libero.tps_insieme`, la metrica primaria del decode.
"""
import argparse
import json
from pathlib import Path


def leggi(cartella):
    f = cartella / "riepilogo.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    tutti = d.get("tutti_i_casi_misurati") or {}
    libero = d.get("insieme_libero") or {}
    tok = tutti.get("token_accettati") or 0
    sec = tutti.get("tempo_generazione_s") or 0.0
    return {
        "corsa": d.get("corsa"),
        "preset": d.get("preset"),
        "etichetta": d.get("etichetta"),
        "profilo": d.get("profilo"),
        "token": tok,
        "ms_token": (1000.0 * sec / tok) if tok else float("nan"),
        "tps_tutti": tutti.get("tps_insieme"),
        "tps_libero": libero.get("tps_insieme"),
        "n_liberi": libero.get("n_casi"),
        "impronte": d.get("impronte") or {},
        "guasto": d.get("guasto"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"D:\ds4_work\banco_p0_run")
    ap.add_argument("--rif", default=None, help="corsa di riferimento per le impronte e i delta")
    a = ap.parse_args()

    root = Path(a.root)
    corse = []
    for c in sorted(root.iterdir()):
        if not c.is_dir() or "P4-estensione" not in c.name:
            continue
        r = leggi(c)
        if r:
            corse.append(r)

    rif = None
    if a.rif:
        rif = next((r for r in corse if a.rif in r["corsa"]), None)
    if rif is None:
        rif = next((r for r in corse if r["preset"] == "E0_p4" and r["profilo"] == "fumo"), None)

    print("%-8s %-56s %-12s %6s %10s %9s %9s" %
          ("preset", "corsa", "profilo", "token", "ms/token", "delta", "t/s lib"))
    for r in corse:
        delta = (r["ms_token"] - rif["ms_token"]) if (rif and r["profilo"] == rif["profilo"]) else float("nan")
        print("%-8s %-56s %-12s %6d %10.3f %9s %9s" %
              (r["preset"], r["corsa"], r["profilo"], r["token"], r["ms_token"],
               ("%+.3f" % delta) if delta == delta else "-",
               ("%.4f" % r["tps_libero"]) if r["tps_libero"] else "-"))

    if rif:
        print("\nriferimento delle impronte: %s (%s)" % (rif["preset"], rif["corsa"]))
        for r in corse:
            diverse = [k for k, v in r["impronte"].items()
                       if k in rif["impronte"] and rif["impronte"][k] != v]
            mancanti = [k for k in r["impronte"] if k not in rif["impronte"]]
            stato = "nessuna" if not diverse else ("%d: %s" % (len(diverse), ",".join(sorted(diverse))))
            if mancanti:
                stato += " (+%d non nel riferimento)" % len(mancanti)
            print("  %-8s %-56s impronte diverse: %s" % (r["preset"], r["corsa"], stato))

    guasti = [r for r in corse if r["guasto"]]
    if guasti:
        print("\nCORSE CON GUASTO:")
        for r in guasti:
            print("  %s: %s" % (r["corsa"], r["guasto"]))
    else:
        print("\nnessuna corsa con guasto")


if __name__ == "__main__":
    main()
