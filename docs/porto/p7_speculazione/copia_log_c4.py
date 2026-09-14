"""P7, cella 4 — copia in `log/` gli artefatti puliti delle corse.

Per ogni corsa `P7-cella4` porta via il riepilogo (testo e json) e le righe del
log del server che riguardano l'ibrido CPU/GPU: il log intero pesa decine di MB
e non serve. Le righe copiate sono gia' ripulite dalla chiave API dal banco.
"""
import json
import re
import shutil
from pathlib import Path

RUNS = Path(r"D:\ds4_work\banco_p0_run")
LOG = Path(__file__).resolve().parent / "log"
INTERESSE = re.compile(r"moe cpu|CONTAMINAT|ramo CPU|idoneo al ramo|llama_decode: failed|"
                       r"spec\s+process|graph splits|n_gen =")


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    for c in sorted(p for p in RUNS.iterdir() if p.is_dir() and "P7-cella4" in p.name):
        tag = c.name.split("_P7-cella4_")[-1]
        for nome, dest in (("riepilogo.txt", "c4_%s_riepilogo.txt" % tag),
                           ("riepilogo.json", "c4_%s_riepilogo.json" % tag)):
            f = c / nome
            if f.exists():
                shutil.copyfile(f, LOG / dest)
        srv = c / "log" / "server.log"
        if srv.exists():
            righe = []
            for r in srv.read_text(encoding="utf-8", errors="replace").splitlines():
                if INTERESSE.search(r):
                    righe.append(r)
            (LOG / ("c4_%s_moecpu.txt" % tag)).write_text("\n".join(righe) + "\n",
                                                          encoding="utf-8", newline="\n")
        print("copiato", tag)


if __name__ == "__main__":
    main()
