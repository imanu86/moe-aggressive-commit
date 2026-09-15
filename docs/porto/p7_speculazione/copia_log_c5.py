"""P7, cella 5 - copia in `log/` gli artefatti puliti delle corse.

Come `copia_log_c4.py`, ma per le corse `P7-cella5`: riepilogo (testo e json) e
le sole righe del log del server che riguardano l'ibrido CPU/GPU, la
speculazione e i guasti CUDA. Il log intero pesa decine di MB e non serve; le
righe copiate sono gia' ripulite dalla chiave API dal banco.

Copia anche i due log di avvio FALLITO di T1 e T1C, che non producono una
cartella di corsa: sono la prova del difetto 1 (`__trap()` nel pianificatore) e
vanno conservati come qualunque altro output.
"""
import re
import shutil
from pathlib import Path

RUNS = Path(r"D:\ds4_work\banco_p0_run")
SRVLOG = Path(r"C:\Users\imanu\Documents\Codex\2026-09-09"
              r"\c-users-imanu-source-repos-moe\work\qwen38_server_logs_sperimentali")
LOG = Path(__file__).resolve().parent / "log"
INTERESSE = re.compile(r"moe cpu|CONTAMINAT|ramo CPU|idoneo al ramo|llama_decode: failed|"
                       r"CUDA error|in function|draft acceptance|common_specu: statistics|"
                       r"graph splits")


def righe_utili(testo):
    return [r for r in testo.splitlines() if INTERESSE.search(r)]


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    for c in sorted(p for p in RUNS.iterdir() if p.is_dir() and "P7-cella5" in p.name):
        tag = c.name.split("_P7-cella5_")[-1]
        for nome, dest in (("riepilogo.txt", "c5_%s_riepilogo.txt" % tag),
                           ("riepilogo.json", "c5_%s_riepilogo.json" % tag)):
            f = c / nome
            if f.exists():
                shutil.copyfile(f, LOG / dest)
        srv = c / "log" / "server.log"
        if srv.exists():
            righe = righe_utili(srv.read_text(encoding="utf-8", errors="replace"))
            (LOG / ("c5_%s_moecpu.txt" % tag)).write_text("\n".join(righe) + "\n",
                                                          encoding="utf-8", newline="\n")
        print("copiato", tag)

    # Gli avvii falliti: nessuna cartella di corsa, solo il log del server.
    for pattern, dest in (("p0_p7c5_t1_mtp1_*_2026091*.log", "c5_t1_avvio_fallito_trap.txt"),
                          ("p0_p7c5_t1c_*_2026091*.log",     "c5_t1c_lancio_bloccante_trap.txt")):
        trovati = sorted(SRVLOG.glob(pattern))
        if not trovati:
            continue
        pezzi = []
        for f in trovati:
            pezzi.append("=== %s ===" % f.name)
            pezzi.extend(righe_utili(f.read_text(encoding="utf-8", errors="replace")))
        (LOG / dest).write_text("\n".join(pezzi) + "\n", encoding="utf-8", newline="\n")
        print("copiato", dest)


if __name__ == "__main__":
    main()
