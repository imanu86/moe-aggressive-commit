"""P7, cella 6 - copia in `log/` gli artefatti puliti delle corse U3/U4/U6 (e le loro
varianti contatori U3C/U4C/U6C). Stesso schema di copia_log_c5.py: riepilogo (testo e
json) e le sole righe del log del server che riguardano l'ibrido CPU/GPU, la
speculazione e i guasti CUDA. Le righe copiate sono gia' ripulite dalla chiave API dal
banco.
"""
import re
import shutil
from pathlib import Path

RUNS = Path(r"D:\ds4_work\banco_p0_run")
LOG = Path(__file__).resolve().parent / "log"
INTERESSE = re.compile(r"moe cpu|CONTAMINAT|ramo CPU|idoneo al ramo|llama_decode: failed|"
                       r"CUDA error|in function|draft acceptance|common_specu: statistics|"
                       r"graph splits")


def righe_utili(testo):
    return [r for r in testo.splitlines() if INTERESSE.search(r)]


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    for c in sorted(p for p in RUNS.iterdir() if p.is_dir() and "P7-cella6" in p.name):
        tag = c.name.split("_P7-cella6_")[-1]
        for nome, dest in (("riepilogo.txt", "c6_%s_riepilogo.txt" % tag),
                           ("riepilogo.json", "c6_%s_riepilogo.json" % tag)):
            f = c / nome
            if f.exists():
                shutil.copyfile(f, LOG / dest)
        srv = c / "log" / "server.log"
        if srv.exists():
            righe = righe_utili(srv.read_text(encoding="utf-8", errors="replace"))
            (LOG / ("c6_%s_moecpu.txt" % tag)).write_text("\n".join(righe) + "\n",
                                                          encoding="utf-8", newline="\n")
        carico = c / "carico.jsonl"
        if carico.exists():
            shutil.copyfile(carico, LOG / ("c6_%s_carico.jsonl" % tag))
        print("copiato", tag)


if __name__ == "__main__":
    main()
