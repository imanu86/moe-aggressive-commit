"""Ricompila solo PR270 e riusa gli oggetti della build 0130, senza modificarla."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(r"D:\ds4_work\strata\Strata")
BUILD = BASE / "build-0130"
OUT = ROOT / ".codex_runs/strata_pr270_20261001"
CUDA = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6")
VC = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC")
BIN = VC / "Tools/MSVC/14.44.35207/bin/Hostx64/x64"


def main():
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    import psutil
    if any((p.info["name"] or "").lower() in ("strata.exe", "llama-server.exe")
           for p in psutil.process_iter(["name"])):
        raise RuntimeError("Motore gia' attivo: compilazione e parita' devono avvenire fuori dalle corse")
    OUT.mkdir(parents=True, exist_ok=True)
    temp = OUT / "tmp"
    temp.mkdir(exist_ok=True)
    env = dict(os.environ)
    if "STRATA_API_KEY" in env:
        raise RuntimeError("Escludere STRATA_API_KEY dal processo di laboratorio")
    env.update(TEMP=str(temp), TMP=str(temp))
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env)
    if init.returncode:
        raise RuntimeError(f"vcvars64: exit {init.returncode}: {init.stderr}")
    for line in init.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            k, v = line.split("=", 1)
            env[k] = v
    env["PATH"] = str(CUDA / "bin") + os.pathsep + env.get("Path", env.get("PATH", ""))
    evidence = {"base": str(BUILD), "pr": 270, "steps": []}
    for label, ref in [("base_commit", "HEAD"), ("upstream_commit", "pr-270")]:
        evidence[label] = subprocess.run(
            ["git", "-c", "safe.directory=" + BASE.as_posix(), "-C", str(BASE), "rev-parse", ref],
            capture_output=True, check=True, env=env).stdout.decode().strip()
    evidence["base_exe_sha256"] = hashlib.sha256((BUILD / "strata.exe").read_bytes()).hexdigest()

    def run(name, args):
        print(name, flush=True)
        begin = time.monotonic()
        with (OUT / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run([str(x) for x in args], cwd=OUT, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
        evidence["steps"].append({"name": name, "exit": p.returncode,
                                  "seconds": round(time.monotonic() - begin, 2)})
        (OUT / "build-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        if p.returncode:
            print((OUT / (name + ".log")).read_text(encoding="utf-8", errors="replace"), flush=True)
            raise RuntimeError(f"{name}: exit {p.returncode}")

    pr = subprocess.run(["git", "-c", "safe.directory=" + BASE.as_posix(), "-C", str(BASE),
                         "show", "pr-270:src/kernels/cuda/qsa_prompt_attn.cu"],
                        capture_output=True, check=True, env=env).stdout
    parent = subprocess.run(["git", "-c", "safe.directory=" + BASE.as_posix(), "-C", str(BASE),
                             "show", "pr-270^:src/kernels/cuda/qsa_prompt_attn.cu"],
                            capture_output=True, check=True, env=env).stdout
    normalize = lambda b: b.replace(b"\r\n", b"\n")
    if normalize(parent) != normalize((BASE / "src/kernels/cuda/qsa_prompt_attn.cu").read_bytes()):
        raise RuntimeError("Il kernel base differisce dal parent di PR270: rivalutare l'integrazione")
    source = OUT / "qsa_prompt_attn.cu"
    source.write_bytes(pr)
    evidence["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    obj = OUT / "qsa_prompt_attn.cu.obj"
    run("nvcc-pr270", [CUDA / "bin/nvcc.exe", "-forward-unknown-to-host-compiler",
        "-D_WINDOWS", "-Xcompiler=/EHsc", "-Xcompiler=/O2,/Ob2", "-DNDEBUG", "-std=c++20",
        "--generate-code=arch=compute_75,code=[compute_75,sm_75]",
        "--generate-code=arch=compute_86,code=[compute_86,sm_86]",
        "-Xcompiler=/MD,/W4", "-I" + str(BASE / "third_party/ggml"),
        "-I" + str(BASE / "include"), "-c", source, "-o", obj])
    ninja = (BUILD / "build.ninja").read_text()
    line = next(x for x in ninja.splitlines() if x.startswith("build strata_kernels.lib:"))
    members = line.split("Release ", 1)[1].split(" ||", 1)[0].split()
    paths = [obj if x.endswith("qsa_prompt_attn.cu.obj") else BUILD / x for x in members]
    assert sum(p == obj for p in paths) == 1
    assert all(p.is_file() for p in paths)
    rsp = OUT / "kernels.rsp"
    rsp.write_text('/nologo\n/out:"' + str(OUT / "strata_kernels.lib") + '"\n' +
                   "\n".join('"' + str(p) + '"' for p in paths), encoding="utf-8")
    run("archive-pr270", [BIN / "lib.exe", "@" + str(rsp)])
    libs = [BUILD / x for x in ["strata_engine.lib", "strata_prefill.lib", "strata_spec.lib"]]
    libs += [OUT / "strata_kernels.lib"]
    libs += [BUILD / x for x in ["strata_core.lib", "strata_kernels_cpu.lib",
                               "ggml/src/ggml-cpu.lib", "strata_mmq.lib", "ggml/src/ggml-base.lib"]]
    libs += [CUDA / "lib/x64" / (x + ".lib") for x in ["cudart", "cuda", "cublas", "cublasLt", "cudadevrt"]]
    libs += [x + ".lib" for x in ["kernel32", "user32", "gdi32", "winspool", "shell32",
                                  "ole32", "oleaut32", "uuid", "comdlg32", "advapi32"]]
    run("link-strata-pr270", [BIN / "link.exe", "/nologo", "/machine:x64", "/INCREMENTAL:NO",
        "/subsystem:console", "/DEBUG", "/OPT:REF", "/OPT:ICF", "/MANIFEST:EMBED",
        "/out:" + str(OUT / "strata.exe"), "/pdb:" + str(OUT / "strata.pdb"),
        BUILD / "CMakeFiles/strata.dir/src/program/generate.cpp.obj", *libs])
    run("compile-parity", [BIN / "cl.exe", "/nologo", "/std:c++20", "/EHsc", "/O2", "/MD",
        "/I" + str(BASE / "include"), "/I" + str(CUDA / "include"),
        BASE / "src/kernels/qsa_prompt_attn_parity.cpp", "/Fe:" + str(OUT / "qsa_prompt_attn_parity.exe"),
        "/Fo:" + str(OUT / "parity.obj"), "/link", OUT / "strata_kernels.lib",
        BUILD / "strata_core.lib", CUDA / "lib/x64/cudart.lib", CUDA / "lib/x64/cublas.lib",
        CUDA / "lib/x64/cudadevrt.lib"])
    for ctx, queries in [(32768, 128), (32768, 2048)]:
        run(f"parity-{ctx}-{queries}", [OUT / "qsa_prompt_attn_parity.exe", str(ctx), str(queries), "1"])
        print((OUT / f"parity-{ctx}-{queries}.log").read_text(), flush=True)
    evidence["exe_sha256"] = hashlib.sha256((OUT / "strata.exe").read_bytes()).hexdigest()
    (OUT / "build-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("BUILD_AND_PARITY_OK", OUT, flush=True)


if __name__ == "__main__":
    main()
