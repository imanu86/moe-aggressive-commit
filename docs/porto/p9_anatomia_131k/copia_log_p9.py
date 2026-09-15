"""P9 - copia in `log/` gli artefatti della corsa profilata, ripuliti.

Non copia i `.nsys-rep` ne' gli `.sqlite` (45 MB l'uno): restano in
`D:\\ds4_work\\banco_p0_run\\...\\nsys\\`. Copia i log di testo, il riepilogo, i
risultati e le righe utili del log del server, e ricontrolla che la chiave API non
compaia in nessuno dei file prodotti.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "log"
BANCO = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0")
sys.path.insert(0, str(BANCO))
import banco_p0 as B  # noqa: E402

RIGHE_UTILI = re.compile(
    r"graph splits|sched_reserve|print_timing|prompt processing|"
    r"n_ctx|moe cache|slot release|slot launch|NaN|nan|error|failed|warmup", re.I)


def main():
    corsa = Path(sys.argv[1] if len(sys.argv) > 1 else
                 r"D:\ds4_work\banco_p0_run\20260915_145054_P9_p9_anatomia_131k")
    LOG.mkdir(parents=True, exist_ok=True)
    chiave = B.chiave_api()

    for nome, dest in [("riepilogo.json", "p9_riepilogo.json"),
                       ("results.jsonl", "p9_results.jsonl"),
                       ("log/client.log", "p9_client.log"),
                       ("carico.jsonl", "p9_carico.jsonl")]:
        src = corsa / nome
        if src.exists():
            testo = src.read_text(encoding="utf-8", errors="replace").replace(chiave, "<REDATTA>")
            (LOG / dest).write_text(testo, encoding="utf-8")
            print("copiato", dest, "(%d byte)" % len(testo))

    # righe utili del log del server
    srv = corsa / "log" / "server.log"
    if srv.exists():
        righe = []
        for r in srv.read_text(encoding="utf-8", errors="replace").replace("\r", "\n").splitlines():
            if RIGHE_UTILI.search(r):
                righe.append(r.replace(chiave, "<REDATTA>"))
        (LOG / "p9_server_estratto.txt").write_text("\n".join(righe) + "\n", encoding="utf-8")
        print("estratte %d righe del log del server" % len(righe))

    # la riga di comando, gia' redatta dal lanciatore
    a = corsa / "log" / "args.redacted.txt"
    if a.exists():
        shutil.copy(a, LOG / "p9_args.redacted.txt")

    # controllo finale: la chiave non deve comparire da nessuna parte in log/
    sporchi = [p.name for p in LOG.glob("*")
               if p.is_file() and chiave in p.read_text(encoding="utf-8", errors="replace")]
    print("file che contengono ancora la chiave:", sporchi or "nessuno")
    return 1 if sporchi else 0


if __name__ == "__main__":
    sys.exit(main())
