"""Survey candidate local text files: language, size, secret screen. Writes scratch/survey.tsv."""
from __future__ import annotations

import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langid  # noqa: E402

REPOS = Path(r"C:\Users\imanu\source\repos")
WORK = Path(__file__).resolve().parent.parent

# (label, repo dir, glob suffixes) - tracked files only, so untracked run outputs and junk stay out
SOURCES = [
    ("moe-aggressive-commit", REPOS / "moe-aggressive-commit"),
    ("cgc-infra", REPOS / "cgc-infra"),
    ("cgc-ia-pipeline", REPOS / "cgc-ia-pipeline"),
    ("Strata-2080Ti", REPOS / "Strata-2080Ti"),
    ("oktocgc-guide", REPOS / "oktocgc-guide"),
    ("oktocgc-website", REPOS / "oktocgc-website"),
    ("MultiPhoneControls", REPOS / "MultiPhoneControls"),
    ("bonusx-kb", REPOS / "bonusx-kb"),
    ("cgc-cockpit", REPOS / "cgc-cockpit"),
    ("scope", REPOS / "scope"),
    ("reap-loop", REPOS / "reap-loop"),
]


def tracked(repo: Path) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    except Exception:
        return []
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def main() -> int:
    rows = []
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for label, repo in SOURCES:
        if not repo.exists():
            continue
        for rel in tracked(repo):
            if not rel.lower().endswith((".md", ".txt")):
                continue
            p = repo / rel
            try:
                data = p.read_bytes()
                text = data.decode("utf-8")
            except Exception:
                continue
            if "node_modules" in rel or "/third_party/" in rel or "__MACOSX" in rel:
                continue
            kind = langid.classify(text)
            sec = langid.looks_secret(rel, text)
            rows.append((label, rel, len(data), kind, sec))
            top = rel.split("/")[0] if "/" in rel else "."
            a = agg[(label, top)][kind]
            a[0] += 1
            a[1] += len(data)
    out = WORK / "scratch" / "survey.tsv"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    for (label, top), kinds in sorted(agg.items()):
        s = " ".join(f"{k}:{v[0]}f/{v[1]//1024}K" for k, v in sorted(kinds.items()))
        print(f"{label}/{top}: {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
