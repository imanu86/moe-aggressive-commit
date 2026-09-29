"""Quali fork di Niko1221/Strata hanno commit propri (29/9/2026). Solo letture via `gh api`.

Per ogni fork elencato in D:\\ds4_work\\strata\\fork_elenco.tsv (full_name, branch, pushed_at, stelle) chiede il confronto
upstream main...owner:branch; tiene quelli con ahead_by > 0 e ne stampa i messaggi dei commit e i file toccati.
"""
import json
import subprocess
import sys
from pathlib import Path

ELENCO = Path(r"D:\ds4_work\strata\fork_elenco.tsv")
OUT = Path(r"D:\ds4_work\strata\fork_avanti.json")


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def main():
    avanti = []
    righe = [l.split("\t") for l in ELENCO.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    for i, (nome, branch, pushed, stelle) in enumerate(righe, 1):
        owner = nome.split("/")[0]
        c = gh(f"repos/Niko1221/Strata/compare/main...{owner}:{branch}")
        if not c:
            print(f"[{i}/{len(righe)}] {nome}: confronto non riuscito", file=sys.stderr)
            continue
        if c.get("ahead_by", 0) > 0:
            commit = [x["commit"]["message"].splitlines()[0][:120] for x in c.get("commits", [])]
            file_ = sorted({f["filename"] for f in c.get("files", [])})
            avanti.append({"fork": nome, "branch": branch, "pushed_at": pushed, "stelle": int(stelle),
                           "ahead_by": c["ahead_by"], "behind_by": c.get("behind_by"), "commit": commit,
                           "file": file_[:40], "n_file": len(file_)})
            print(f"[{i}/{len(righe)}] {nome}: +{c['ahead_by']} -{c.get('behind_by')}  {commit[:3]}", flush=True)
    OUT.write_text(json.dumps(avanti, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"fork con commit propri: {len(avanti)} su {len(righe)}")


if __name__ == "__main__":
    main()
