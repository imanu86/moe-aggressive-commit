"""Build the draft-vocabulary corpus from LOCAL text only (no downloads).

Writes, under the work folder:
  corpus/it_train.txt      Italian prose (docs of moe-aggressive-commit, cgc-infra, cgc-ia-pipeline, MultiPhoneControls, cgc-cockpit)
  corpus/en_prose.txt      English prose (Strata docs, plus English docs of moe-aggressive-commit)
  corpus/code.txt          C++/CUDA/Python sources of the Strata repo (+ a few own scripts)
  corpus/json.txt          tracked JSON (pretty and minified renditions)
  heldout/it_ood.txt       Italian held-out, other domain (oktocgc-guide course texts, bonusx-kb lessons) - NEVER in the corpus
  heldout/it_ind.txt       Italian held-out, same repos as the corpus, files held out by hash - NEVER in the corpus
  corpus/manifest.tsv      every file used: part, source, path, bytes used
  corpus/composition.json  bytes per part / source

Fenced code blocks are removed from prose; secret-looking files are skipped (name or body); the folder of the three
answers measured in the report (docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep) is excluded everywhere.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import langid  # noqa: E402

REPOS = Path(r"C:\Users\imanu\source\repos")
WORK = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
HEXLINE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
LONGBLOB = re.compile(r"\S{80,}")
EXCLUDE_PATH = ("20261004_routed_keep", "node_modules", "third_party", "__MACOSX", ".codex_runs", "/answer", "engine.log")
PER_FILE_CAP = 150_000


def tracked(repo: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def read(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


def clean_prose(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = FENCE.sub("", text)
    keep = []
    for line in text.split("\n"):
        if HEXLINE.search(line) or LONGBLOB.search(line):
            continue
        keep.append(line.rstrip())
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()
    return out[:PER_FILE_CAP]


def h(rel: str) -> int:
    return int(hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8], 16)


def shingles(text: str, n: int = 8) -> set[int]:
    w = re.findall(r"\w+", text.lower())
    return {hash(tuple(w[i:i + n])) for i in range(0, max(0, len(w) - n + 1))}


def main() -> int:
    (WORK / "corpus").mkdir(exist_ok=True)
    (WORK / "heldout").mkdir(exist_ok=True)
    manifest: list[tuple] = []
    skipped_secret: list[str] = []
    seen_hash: set[str] = set()

    def ok_path(rel: str) -> bool:
        return not any(x in rel for x in EXCLUDE_PATH)

    # ---------------------------------------------------------------- Italian: train / held-out
    # (source label, repo, path prefixes (None = all), byte cap for the source)
    it_sources = [
        ("moe-aggressive-commit", REPOS / "moe-aggressive-commit", None, 4_000_000),
        ("cgc-infra", REPOS / "cgc-infra", None, 3_500_000),
        ("MultiPhoneControls", REPOS / "MultiPhoneControls", ("docs/", "TabletRemote/", "tools/"), 2_000_000),
        ("cgc-cockpit", REPOS / "cgc-cockpit", ("docs/", "experiments/"), 700_000),
        ("cgc-ia-pipeline", REPOS / "cgc-ia-pipeline", None, 600_000),
    ]
    it_train: list[tuple[str, str, str]] = []   # (source, rel, text)
    it_ind: list[tuple[str, str, str]] = []
    for label, repo, prefixes, cap in it_sources:
        files = []
        for rel in tracked(repo):
            if not rel.lower().endswith((".md", ".txt")) or not ok_path(rel):
                continue
            if prefixes and not rel.startswith(prefixes):
                continue
            files.append(rel)
        files.sort(key=h)               # a stable pseudo-random order, so the cap samples across the repo
        used = 0
        for rel in files:
            raw = read(repo / rel)
            if raw is None:
                continue
            if langid.looks_secret(rel, raw):
                skipped_secret.append(f"{label}/{rel}")
                continue
            if langid.classify(raw) != "it":
                continue
            digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
            if digest in seen_hash:
                continue
            seen_hash.add(digest)
            text = clean_prose(raw)
            if len(text) < 600:
                continue
            if h("heldout/" + rel) % 100 < 12:       # ~12% of the files never enter the corpus
                it_ind.append((label, rel, text))
                continue
            if used + len(text) > cap:
                continue
            used += len(text)
            it_train.append((label, rel, text))

    # held-out out-of-domain: other repos, never used for the corpus
    it_ood: list[tuple[str, str, str]] = []
    for label, repo, prefixes in (("oktocgc-guide", REPOS / "oktocgc-guide", ("sources/", "docs/")),
                                  ("bonusx-kb", REPOS / "bonusx-kb", ("lessons/", "prompts/", "corpus/"))):
        for rel in tracked(repo):
            if not rel.lower().endswith((".md", ".txt")) or not rel.startswith(prefixes) or not ok_path(rel):
                continue
            raw = read(repo / rel)
            if raw is None or langid.looks_secret(rel, raw) or langid.classify(raw) != "it":
                continue
            digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
            if digest in seen_hash:
                continue
            seen_hash.add(digest)
            text = clean_prose(raw)
            if len(text) >= 600:
                it_ood.append((label, rel, text))
    extra = Path(r"D:\ds4_work\testa\B_prosa_it.txt")
    if extra.exists():
        t = read(extra)
        if t:
            it_ood.append(("ds4_work/testa", "B_prosa_it.txt", clean_prose(t)))

    # leak guard: drop held-out files that share >30% of their 8-word shingles with the corpus
    train_sh: set[int] = set()
    for _, _, t in it_train:
        train_sh |= shingles(t)

    def guard(items):
        keep, dropped = [], []
        for lab, rel, t in items:
            sh = shingles(t)
            frac = len(sh & train_sh) / len(sh) if sh else 0.0
            (dropped if frac > 0.30 else keep).append((lab, rel, t, frac))
        return [(a, b, c) for a, b, c, _ in keep], [(a, b, round(f, 2)) for a, b, _, f in dropped]

    it_ind, drop_ind = guard(it_ind)
    it_ood, drop_ood = guard(it_ood)

    # ---------------------------------------------------------------- English prose
    en: list[tuple[str, str, str]] = []
    strata = REPOS / "Strata-2080Ti"
    for rel in tracked(strata):
        if rel.lower().endswith(".md") and ok_path(rel):
            raw = read(strata / rel)
            if raw and not langid.looks_secret(rel, raw) and langid.classify(raw) == "en":
                t = clean_prose(raw)
                if len(t) >= 400:
                    en.append(("Strata-2080Ti", rel, t))
    moe = REPOS / "moe-aggressive-commit"
    used = 0
    for rel in sorted((r for r in tracked(moe) if r.lower().endswith((".md", ".txt")) and ok_path(r)), key=h):
        raw = read(moe / rel)
        if raw and not langid.looks_secret(rel, raw) and langid.classify(raw) == "en":
            t = clean_prose(raw)
            if len(t) >= 400 and used + len(t) <= 500_000:
                used += len(t)
                en.append(("moe-aggressive-commit", rel, t))

    # ---------------------------------------------------------------- code
    code: list[tuple[str, str, str]] = []
    exts = (".cpp", ".hpp", ".cu", ".cuh", ".h", ".py", ".cc")
    used = 0
    for rel in sorted((r for r in tracked(strata) if r.lower().endswith(exts) and ok_path(r)), key=h):
        raw = read(strata / rel)
        if raw is None or langid.looks_secret(rel, raw):
            continue
        raw = raw.replace("\r\n", "\n")[:100_000]
        if used + len(raw) > 2_500_000:
            continue
        used += len(raw)
        code.append(("Strata-2080Ti", rel, raw))
    used = 0
    for rel in sorted((r for r in tracked(moe) if r.lower().endswith((".py", ".ps1", ".sh")) and ok_path(r)), key=h):
        raw = read(moe / rel)
        if raw is None or langid.looks_secret(rel, raw):
            continue
        raw = raw.replace("\r\n", "\n")[:60_000]
        if used + len(raw) > 500_000:
            continue
        used += len(raw)
        code.append(("moe-aggressive-commit", rel, raw))

    # JSON: tracked small files, each pretty-printed and minified (the answers meter "},{\"" style compact JSON)
    js: list[tuple[str, str, str]] = []
    used = 0
    for label, repo in (("Strata-2080Ti", strata), ("moe-aggressive-commit", moe), ("cgc-infra", REPOS / "cgc-infra")):
        for rel in sorted((r for r in tracked(repo) if r.lower().endswith(".json") and ok_path(r)), key=h):
            if rel.endswith(("package-lock.json",)) or "symbols" in rel or "mcp.config" in rel:
                continue
            raw = read(repo / rel)
            if raw is None or len(raw) > 200_000 or langid.looks_secret(rel, raw):
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            mini = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            both = pretty + "\n" + mini
            if used + len(both) > 800_000:
                continue
            used += len(both)
            js.append((label, rel, both))

    # ---------------------------------------------------------------- hold ~12% of en / code / json files out
    def split(items, tag):
        keep, held = [], []
        for src, rel, t in items:
            (held if h(tag + "/" + rel) % 100 < 12 else keep).append((src, rel, t))
        return keep, held

    en, en_ind = split(en, "heldout-en")
    code, code_ind = split(code, "heldout-code")
    js, js_ind = split(js, "heldout-json")

    # ---------------------------------------------------------------- write
    def write(name: str, items, outdir="corpus"):
        path = WORK / outdir / name
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for _, _, t in items:
                f.write(t.rstrip() + "\n\n")
        return path

    parts = {
        "it_train": ("corpus", it_train), "en_prose": ("corpus", en), "code": ("corpus", code), "json": ("corpus", js),
        "it_ood": ("heldout", it_ood), "it_ind": ("heldout", it_ind),
        "en_ind": ("heldout", en_ind), "code_ind": ("heldout", code_ind), "json_ind": ("heldout", js_ind),
    }
    comp: dict = {}
    with (WORK / "corpus" / "manifest.tsv").open("w", encoding="utf-8") as mf:
        mf.write("part\tsource\tpath\tchars\n")
        for name, (outdir, items) in parts.items():
            write(f"{name}.txt", items, outdir)
            by_src: dict = defaultdict(lambda: [0, 0])
            for src, rel, t in items:
                mf.write(f"{name}\t{src}\t{rel}\t{len(t)}\n")
                by_src[src][0] += 1
                by_src[src][1] += len(t.encode("utf-8"))
            comp[name] = {"files": len(items), "bytes": (WORK / outdir / f"{name}.txt").stat().st_size,
                          "by_source": {k: {"files": v[0], "bytes": v[1]} for k, v in by_src.items()}}
    # per-file view of the Italian corpus (source, path, text) for the document-frequency analysis
    with (WORK / "scratch" / "it_train_files.jsonl").open("w", encoding="utf-8") as jf:
        for src, rel, t in it_train:
            jf.write(json.dumps({"source": src, "path": rel, "text": t}, ensure_ascii=False) + "\n")
    comp["skipped_secret_looking"] = skipped_secret
    comp["heldout_dropped_for_overlap"] = {"it_ind": drop_ind, "it_ood": drop_ood}
    (WORK / "corpus" / "composition.json").write_text(json.dumps(comp, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, v in comp.items():
        if isinstance(v, dict) and "bytes" in v:
            print(f"{name}: {v['files']} files, {v['bytes']:,} bytes  {dict((k, x['bytes']) for k, x in v['by_source'].items())}")
    print("skipped as secret-looking:", len(skipped_secret))
    print("held-out dropped for overlap:", comp["heldout_dropped_for_overlap"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
