"""Isola il kernel vettoriale del fork 2080ti riusando gli oggetti della base 0.1.31."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from compila_0131 import BASE, CUDA, VC

FORK = "ea158a93ed30340092f1bf4a13522231062453f5"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    root = a.base.resolve(strict=True)
    build = root / "build"
    source = root / "source"
    out = a.out.resolve()
    out.mkdir(exist_ok=False, parents=True)
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    import psutil
    if any((p.info["name"] or "").lower() in ("strata.exe", "llama-server.exe")
           for p in psutil.process_iter(["name"])):
        raise RuntimeError("Motore attivo: nessuna compilazione durante le corse")
    env = dict(os.environ)
    if "STRATA_API_KEY" in env: raise RuntimeError("Escludere STRATA_API_KEY")
    temp = out / "tmp"
    temp.mkdir()
    env.update(TEMP=str(temp), TMP=str(temp))
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            k, v = line.split("=", 1); env[k] = v
    env["PATH"] = str(CUDA / "bin") + os.pathsep + env.get("Path", env.get("PATH", ""))
    binary = VC / "Tools/MSVC/14.44.35207/bin/Hostx64/x64"
    evidence = {"fork_commit": FORK, "base": str(root), "steps": [], "source_sha256": {}}
    def run(name, args):
        print(name, flush=True)
        begin = time.monotonic()
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(list(map(str, args)), cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
        evidence["steps"].append({"name": name, "exit": p.returncode, "seconds": round(time.monotonic()-begin, 2)})
        (out / "build-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        if p.returncode:
            print((out / (name + ".log")).read_text(encoding="utf-8", errors="replace")[-12000:], flush=True)
            raise RuntimeError(f"{name}: exit {p.returncode}")
    def git_show(ref):
        return subprocess.run(["git", "-C", str(BASE), "show", ref], capture_output=True, check=True).stdout.replace(b"\r\n", b"\n")
    relative = "src/kernels/cuda/dequant_bf16.cu"
    if git_show(FORK + "^:" + relative) != (source / relative).read_bytes().replace(b"\r\n", b"\n"):
        raise RuntimeError("La base dequant differisce dal parent del fork")
    cu = out / "dequant_bf16.cu"
    cu.write_bytes(git_show(FORK + ":" + relative))
    header = out / "include/strata/core/tc_sm75.hpp"
    header.parent.mkdir(parents=True)
    header.write_bytes(git_show(FORK + ":include/strata/core/tc_sm75.hpp"))
    for p in [cu, header]: evidence["source_sha256"][str(p.relative_to(out))] = hashlib.sha256(p.read_bytes()).hexdigest()
    obj = out / "dequant_bf16.cu.obj"
    run("nvcc-vector", [CUDA / "bin/nvcc.exe", "-forward-unknown-to-host-compiler", "-D_WINDOWS",
        "-Xcompiler=/EHsc", "-Xcompiler=/O2,/Ob2", "-DNDEBUG", "-std=c++20",
        "--generate-code=arch=compute_75,code=[compute_75,sm_75]",
        "--generate-code=arch=compute_86,code=[compute_86,sm_86]", "-Xcompiler=/MD,/W4",
        "-I" + str(out / "include"), "-I" + str(source / "include"),
        "-I" + str(source / "third_party/ggml"), "-c", cu, "-o", obj])
    line = next(x for x in (build / "build.ninja").read_text(encoding="utf-8").splitlines()
                if x.startswith("build strata_kernels.lib:"))
    members = line.split("Release ", 1)[1].split(" ||", 1)[0].split()
    paths = [obj if x.endswith("dequant_bf16.cu.obj") else build / x for x in members]
    assert sum(p == obj for p in paths) == 1 and all(p.is_file() for p in paths)
    rsp = out / "kernels.rsp"
    rsp.write_text('/nologo\n/out:"' + str(out / "strata_kernels.lib") + '"\n' +
                   "\n".join('"' + str(p) + '"' for p in paths), encoding="utf-8")
    run("archive-vector", [binary / "lib.exe", "@" + str(rsp)])
    libs = [build / x for x in ["strata_engine.lib", "strata_prefill.lib", "strata_spec.lib"]]
    libs += [out / "strata_kernels.lib"]
    libs += [build / x for x in ["strata_core.lib", "strata_kernels_cpu.lib", "ggml/src/ggml-cpu.lib",
                               "strata_mmq.lib", "ggml/src/ggml-base.lib"]]
    libs += [CUDA / "lib/x64" / (x + ".lib") for x in ["cudart", "cuda", "cublas", "cublasLt", "cudadevrt"]]
    libs += [x + ".lib" for x in ["kernel32", "user32", "gdi32", "winspool", "shell32", "ole32",
                                 "oleaut32", "uuid", "comdlg32", "advapi32"]]
    run("link-vector", [binary / "link.exe", "/nologo", "/machine:x64", "/INCREMENTAL:NO",
        "/subsystem:console", "/DEBUG", "/OPT:REF", "/OPT:ICF", "/MANIFEST:EMBED",
        "/out:" + str(out / "strata.exe"), "/pdb:" + str(out / "strata.pdb"),
        build / "CMakeFiles/strata.dir/src/program/generate.cpp.obj", *libs])
    for label, library in [("baseline", build / "strata_kernels.lib"), ("vector", out / "strata_kernels.lib")]:
        exe = out / ("parity-" + label + ".exe")
        run("compile-parity-" + label, [binary / "cl.exe", "/nologo", "/std:c++20", "/EHsc", "/O2", "/MD",
            "/I" + str(source / "include"), "/I" + str(CUDA / "include"),
            Path(__file__).with_name("parita_dequant_vec.cpp"), "/Fe:" + str(exe),
            "/Fo:" + str(out / ("parity-" + label + ".obj")), "/link", library, build / "strata_core.lib",
            CUDA / "lib/x64/cudart.lib", CUDA / "lib/x64/cublas.lib", CUDA / "lib/x64/cudadevrt.lib"])
        run("parity-" + label, [exe, *[Path(r"C:\Users\imanu\Downloads") /
            f"Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-0000{i}-of-00002.gguf" for i in [1, 2]]])
    baseline = (out / "parity-baseline.log").read_bytes()
    vector = (out / "parity-vector.log").read_bytes()
    if baseline != vector: raise RuntimeError("Parita' fra binari fallita: controllare digest e righe")
    evidence.update(bitwise_cross_binary=True, exe_sha256=hashlib.sha256((out / "strata.exe").read_bytes()).hexdigest())
    (out / "build-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(vector.decode(errors="replace"), flush=True)
    print("VECTOR_BUILD_AND_PARITY_OK", out, flush=True)


if __name__ == "__main__": main()
