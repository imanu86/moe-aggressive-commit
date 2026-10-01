"""Ricompila tre oggetti HC/GDN e ricollega in laboratorio; base immutata."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from compila_0131 import BASE, CUDA, VC, NINJA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    base = a.base.resolve(strict=True)
    out = a.out.resolve(strict=True)
    source, build = out / "source", base / "build"
    assert json.loads((out / "porting.json").read_text(encoding="utf-8"))["status"] == "completed"
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    import psutil
    if any((p.info["name"] or "").lower() in ("strata.exe", "llama-server.exe") for p in psutil.process_iter(["name"])):
        raise RuntimeError("Motore attivo: compilazione rinviata")
    env = dict(os.environ)
    if "STRATA_API_KEY" in env: raise RuntimeError("Escludere STRATA_API_KEY")
    tmp = out / "tmp"; tmp.mkdir(exist_ok=True)
    env.update(TEMP=str(tmp), TMP=str(tmp))
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            k, v = line.split("=", 1); env[k] = v
    env["PATH"] = str(CUDA / "bin") + os.pathsep + env.get("Path", env.get("PATH", ""))
    binary = VC / "Tools/MSVC/14.44.35207/bin/Hostx64/x64"
    result = {"base": str(base), "scope": "HC/GDN FP16, draft BF16, scalar dequant", "steps": []}
    def run(name, args, shell=False):
        print(name, flush=True)
        start = time.monotonic()
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(args if shell else list(map(str, args)), shell=shell, cwd=out, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
        result["steps"].append({"name": name, "exit": p.returncode, "seconds": round(time.monotonic()-start, 2)})
        (out / "build-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if p.returncode:
            print((out / (name + ".log")).read_text(encoding="utf-8", errors="replace")[-12000:], flush=True)
            raise RuntimeError(f"{name}: exit {p.returncode}")
    targets = [r"CMakeFiles\strata_prefill.dir\src\prefill\kernels.cu.obj",
               r"CMakeFiles\strata_prefill.dir\src\prefill\prefill.cpp.obj",
               r"CMakeFiles\strata.dir\src\program\generate.cpp.obj"]
    replacements = {}
    for target in targets:
        command = subprocess.run([str(NINJA), "-C", str(build), "-t", "commands", target],
                                 capture_output=True, check=True).stdout.decode("utf-8").splitlines()[-1]
        if " -c " not in command or target not in command: raise RuntimeError("Regola compilazione inattesa")
        command = command.replace(str(base / "source"), str(source)).replace((base / "source").as_posix(), source.as_posix())
        destination = out / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        replacements[target] = destination
        # Every relative output, including dependency files and PDBs, lands under cwd=out.
        run("compile-" + Path(target.replace("\\", "/")).name, command, shell=True)
    ninja = (build / "build.ninja").read_text(encoding="utf-8")
    line = next(x for x in ninja.splitlines() if x.startswith("build strata_prefill.lib:"))
    objects = line.split("Release ", 1)[1].split(" ||", 1)[0].split()
    paths = [replacements.get(x, build / x) for x in objects]
    assert all(x.is_file() for x in paths)
    rsp = out / "prefill.rsp"
    rsp.write_text('/nologo\n/out:"' + str(out / "strata_prefill.lib") + '"\n' +
                   "\n".join('"' + str(p) + '"' for p in paths), encoding="utf-8")
    run("archive-hc", [binary / "lib.exe", "@" + str(rsp)])
    libs = [build / "strata_engine.lib", out / "strata_prefill.lib", build / "strata_spec.lib"]
    libs += [build / x for x in ["strata_kernels.lib", "strata_core.lib", "strata_kernels_cpu.lib",
                               "ggml/src/ggml-cpu.lib", "strata_mmq.lib", "ggml/src/ggml-base.lib"]]
    libs += [CUDA / "lib/x64" / (x + ".lib") for x in ["cudart", "cuda", "cublas", "cublasLt", "cudadevrt"]]
    libs += [x + ".lib" for x in ["kernel32", "user32", "gdi32", "winspool", "shell32", "ole32", "oleaut32",
                                 "uuid", "comdlg32", "advapi32"]]
    run("link-hc", [binary / "link.exe", "/nologo", "/machine:x64", "/INCREMENTAL:NO", "/subsystem:console",
        "/DEBUG", "/OPT:REF", "/OPT:ICF", "/MANIFEST:EMBED", "/out:" + str(out / "strata.exe"),
        "/pdb:" + str(out / "strata.pdb"), replacements[targets[-1]], *libs])
    run("compile-parity-hc", [binary / "cl.exe", "/nologo", "/std:c++20", "/EHsc", "/O2", "/MD",
        "/I" + str(source / "include"), "/I" + str(CUDA / "include"),
        Path(__file__).with_name("parita_hc_fp16.cpp"), "/Fe:" + str(out / "parity-hc.exe"),
        "/Fo:" + str(out / "parity-hc.obj"), "/link", *libs])
    run("parity-hc", [out / "parity-hc.exe"])
    print((out / "parity-hc.log").read_text(encoding="utf-8", errors="replace"), flush=True)
    result["exe_sha256"] = hashlib.sha256((out / "strata.exe").read_bytes()).hexdigest()
    result["source_sha256"] = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [source / "src/prefill/prefill.cpp", source / "src/prefill/kernels.cu", source / "src/program/generate.cpp",
                  source / "include/strata/prefill/kernels.hpp", source / "include/strata/core/tc_sm75.hpp"]}
    (out / "build-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("HC_BUILD_OK", out, flush=True)


if __name__ == "__main__": main()
