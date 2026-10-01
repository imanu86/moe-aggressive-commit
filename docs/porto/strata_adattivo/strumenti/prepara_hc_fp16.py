"""Porta separatamente HC/GDN FP16 sm75 e correzioni del budget sul laboratorio 0.1.31."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from prepara_0131 import BASE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    base = a.base.resolve(strict=True)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    shutil.copytree(base / "source", source)
    refs = ["56495c3", "500d12e", "b4f8a44", "bdea4cb"]
    selected = {
        "56495c3": ["include/strata/core/tc_sm75.hpp", "include/strata/prefill/kernels.hpp",
                    "src/prefill/kernels.cu", "src/prefill/prefill.cpp"],
        "500d12e": ["src/prefill/prefill.cpp"],
        "b4f8a44": ["include/strata/core/tc_sm75.hpp", "src/prefill/prefill.cpp"],
        "bdea4cb": ["src/program/generate.cpp"],
    }
    def read(ref, name):
        result = subprocess.run(["git", "-C", str(BASE), "show", ref + ":" + name], capture_output=True)
        if result.returncode:
            tree = subprocess.run(["git", "-C", str(BASE), "ls-tree", ref, "--", name], capture_output=True, check=True)
            if tree.stdout: raise RuntimeError(result.stderr.decode(errors="replace"))
            return b""
        return result.stdout.replace(b"\r\n", b"\n")
    steps = []
    for ref in refs:
        sha = subprocess.run(["git", "-C", str(BASE), "rev-parse", ref], capture_output=True, check=True).stdout.decode().strip()
        for name in selected[ref]:
            dst = source / name
            old, incoming = read(ref + "^", name), read(ref, name)
            current = dst.read_bytes().replace(b"\r\n", b"\n") if dst.exists() else b""
            snapshots = []
            for label, content in [("current", current), ("base", old), ("incoming", incoming)]:
                path = out / "porting" / ref / label / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content); snapshots.append(path)
            if current == old:
                merged, status = incoming, 0
            else:
                p = subprocess.run(["git", "merge-file", "-p", "--diff3", *map(str, snapshots)], capture_output=True)
                merged, status = p.stdout, p.returncode
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(merged)
            print(ref, name, "conflicts", status, flush=True)
            steps.append({"commit": sha, "file": name, "merge_exit": status})
            (out / "porting.json").write_text(json.dumps({"steps": steps}, indent=2), encoding="utf-8")
            if status: raise RuntimeError("Conflitto: " + name)
    generate = source / "src/program/generate.cpp"
    text = generate.read_text(encoding="utf-8")
    if '#include "strata/core/tc_sm75.hpp"' not in text:
        text = '#include "strata/core/tc_sm75.hpp"\n' + text
    # This isolated variant has only the three HC buffers; it does not allocate the fork's proposed PLE mirror.
    text = text.replace("g.n_embd * g.n_embd * 2;", "0;")
    generate.write_text(text, encoding="utf-8")
    (out / "porting.json").write_text(json.dumps({"status": "completed", "steps": steps,
        "base": str(base), "scope": "HC/GDN FP16; draft BF16; accurate buffer budget; no vector dequant"}, indent=2), encoding="utf-8")
    print("HC_PORTED", out, flush=True)


if __name__ == "__main__": main()
