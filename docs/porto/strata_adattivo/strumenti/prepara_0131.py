"""Porta le patch ancora necessarie su sorgenti esportati 0.1.31, senza checkout Git."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
import sys
import tarfile

BASE = Path(r"D:\ds4_work\strata\Strata")
UPSTREAM = "9259cad4cfa3543cd3b8decab5962672b968c649"
COMMITS = ["39621d5", "43579bb", "b8a51db", "50a37fa", "16755a6", "b9f5b9e", "66b80a2", "8966caf", "20273f4"]


def resolve_known(ref, name, text, incoming):
    """Risoluzioni revisionate degli incastri con 0.1.31; blocchi diversi restano da esaminare."""
    pattern = re.compile(r"^<<<<<<< 0\.1\.31\+ported\n(.*?)^\|\|\|\|\|\|\| " + ref +
                         r"\^\n(.*?)^=======\n(.*?)^>>>>>>> " + ref + r"\n", re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        return None
    ours, _, theirs = matches[0].groups()
    if ref == "43579bb" and name == "src/prefill/prefill.cpp":
        if "chunk_len(c0)" not in theirs or "core::progress_at" not in ours: return None
        replacement = theirs + next(line for line in ours.splitlines(True) if "core::progress_at" in line)
    elif ref == "b8a51db" and name == "src/program/generate.cpp":
        if "init_prompt_paths()" not in ours or "sp_chunk_max" not in theirs: return None
        replacement = ours
        text = text.replace("        auto init_prompt_paths = [&]() -> int {",
            "        const int64_t sp_chunk_max = (o.elastic && xcache.elastic() && o.prefill_auto && borrow != nullptr) ? 8192 : 0;\n"
            "        auto init_prompt_paths = [&]() -> int {")
        text = text.replace("main_cs, err, borrow, borrow_bytes))",
                            "main_cs, err, borrow, borrow_bytes, sp_chunk_max))")
    elif ref == "b9f5b9e" and name == "CMakeLists.txt":
        if "native_expert_parity_q5_1_min" not in ours or "add_executable(native_expert_bench" not in theirs: return None
        replacement = ours + theirs
    elif ref == "66b80a2" and name == "src/kernels/native_expert_bench.cpp":
        return incoming.replace("native_expert_set_multi(m)", "iq_set_old_kernels(m == 0)")
    elif ref == "20273f4" and name == "src/core/verify.cpp":
        if "window_logprobs" not in ours or "g_commit_async" not in theirs: return None
        replacement = ours + theirs
    elif ref == "20273f4" and name == "src/program/generate.cpp":
        if "bool multi_gpu" not in ours or "Verifier::set_commit_async" not in theirs: return None
        replacement = ours + next(line for line in theirs.splitlines(True) if "Verifier::set_commit_async" in line)
    else:
        return None
    return pattern.sub(lambda _: replacement, text, count=1)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = out / "source"
    if not (out / "upstream.json").exists():
        if source.exists():
            raise RuntimeError("Sorgenti gia' presenti senza provenienza: non sovrascritti")
        archive = subprocess.run(["git", "-C", str(BASE), "archive", UPSTREAM], capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(source, filter="data")
        (out / "upstream.json").write_text(json.dumps({"upstream_sha": UPSTREAM, "source": str(source)}, indent=2),
                                           encoding="utf-8")
    metadata = json.loads((out / "upstream.json").read_text(encoding="utf-8"))
    assert metadata["upstream_sha"] == UPSTREAM
    git = ["git", "-C", str(BASE)]
    def read(ref):
        result = subprocess.run(git + ["show", ref], capture_output=True)
        if result.returncode:
            revision, name = ref.split(":", 1)
            listing = subprocess.run(git + ["ls-tree", revision, "--", name], capture_output=True, check=True)
            if not listing.stdout:
                return b""
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout.replace(b"\r\n", b"\n")
    path = out / "porting.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"upstream": UPSTREAM, "steps": []}
    if state.get("status") == "completed":
        for name, digest in state["source_sha256"].items():
            if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError("File portato modificato dopo la preparazione: " + name)
        print("PORT_ALREADY_COMPLETED", flush=True)
        return
    def save():
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if state["steps"] and state["steps"][-1]["status"] == "conflicts":
        step = state["steps"][-1]
        for name in step["conflicts"]:
            contents = (source / name).read_text(encoding="utf-8")
            if re.search(r"^(?:<<<<<<< |\|\|\|\|\|\|\| |=======\s*$|>>>>>>> )", contents, re.MULTILINE):
                raise RuntimeError("Risolvere prima i conflitti di " + name)
        step["status"] = "resolved"
        save()
    done = {step["commit"] for step in state["steps"]}
    for ref in COMMITS:
        sha = subprocess.run(git + ["rev-parse", ref], capture_output=True, check=True).stdout.decode().strip()
        if sha in done:
            continue
        names = subprocess.run(git + ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                               capture_output=True, check=True).stdout.decode().splitlines()
        stage = out / "porting" / ref
        step = {"commit": sha, "status": "applied", "files": names, "conflicts": []}
        for name in names:
            destination = (source / name).resolve()
            assert destination.is_relative_to(source.resolve())
            old = read(sha + "^:" + name)
            incoming = read(sha + ":" + name)
            current = destination.read_bytes().replace(b"\r\n", b"\n") if destination.exists() else b""
            files = []
            for label, contents in (("current", current), ("base", old), ("incoming", incoming)):
                snapshot = stage / label / name
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                snapshot.write_bytes(contents)
                files.append(snapshot)
            if current == old:
                merged = incoming
                conflicts = 0
            elif current == incoming:
                merged = current
                conflicts = 0
            else:
                result = subprocess.run(["git", "merge-file", "-p", "--diff3", "-L", "0.1.31+ported",
                                         "-L", ref + "^", "-L", ref, *map(str, files)], capture_output=True)
                if result.returncode < 0 or result.returncode > 127:
                    raise RuntimeError("merge-file failed: " + result.stderr.decode(errors="replace"))
                merged = result.stdout
                conflicts = result.returncode
            if conflicts:
                resolved = resolve_known(ref, name, merged.decode("utf-8"), incoming.decode("utf-8"))
                if resolved is not None:
                    merged = resolved.encode("utf-8")
                    conflicts = 0
                    step.setdefault("reviewed_resolutions", []).append(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name == "CMakeLists.txt":
                merged = merged.removeprefix(b"\xef\xbb\xbf")
            destination.write_bytes(merged)
            print("PORT", ref, name, "conflicts", conflicts, flush=True)
            if conflicts:
                step["conflicts"].append(name)
                step["status"] = "conflicts"
        state["steps"].append(step)
        save()
        if step["conflicts"]:
            print("STOP_FOR_RESOLUTION", json.dumps(step), flush=True)
            return
    hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
              for name in sorted({name for step in state["steps"] for name in step["files"]})}
    state.update(status="completed", source_sha256=hashes)
    save()
    print("PORT_COMPLETED", len(state["steps"]), "commits", flush=True)


if __name__ == "__main__":
    main()
