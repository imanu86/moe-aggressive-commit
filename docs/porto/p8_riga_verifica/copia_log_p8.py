"""P8 - copia in `log/` gli artefatti puliti delle corse P8.

Stesso schema di `copia_log_c6.py` di P7: riepilogo (testo e json), la traccia del
carico e le SOLE righe del log del server che servono a questa cella — lanci di
grafo (`graph splits`), riuso dei grafi, statistiche della speculazione, riserve
fallite e guasti CUDA/NaN. Le righe sono gia' ripulite dalla chiave API dal banco.
"""
import re
import shutil
from pathlib import Path

RUNS = Path(r"D:\ds4_work\banco_p0_run")
LOG = Path(__file__).resolve().parent / "log"
INTERESSE = re.compile(
    r"graph splits|graph nodes|graphs reused|common_specu: statistics|draft acceptance|"
    r"acc per pos|compute buffer size|failed to allocate graph|increasing split inputs|"
    r"increasing graph inputs|CUDA error|llama_decode: failed|nan|NaN|"
    r"demand workspace|print_timing: id .* eval time|reserve took")


def righe_utili(testo):
    return [r for r in testo.splitlines() if INTERESSE.search(r)]


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in sorted(p for p in RUNS.iterdir() if p.is_dir() and "_P8_" in p.name):
        tag = c.name.split("_P8_", 1)[-1]
        for nome, dest in (("riepilogo.txt", "p8_%s_riepilogo.txt" % tag),
                           ("riepilogo.json", "p8_%s_riepilogo.json" % tag),
                           ("results.jsonl", "p8_%s_results.jsonl" % tag)):
            f = c / nome
            if f.exists():
                shutil.copyfile(f, LOG / dest)
        srv = c / "log" / "server.log"
        if srv.exists():
            righe = righe_utili(srv.read_text(encoding="utf-8", errors="replace"))
            (LOG / ("p8_%s_server_estratto.txt" % tag)).write_text(
                "\n".join(righe) + "\n", encoding="utf-8", newline="\n")
        carico = c / "carico.jsonl"
        if carico.exists():
            shutil.copyfile(carico, LOG / ("p8_%s_carico.jsonl" % tag))
        print("copiato", tag)
        n += 1
    print("corse copiate: %d" % n)


if __name__ == "__main__":
    main()
