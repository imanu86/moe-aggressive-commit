"""Candidata PR315 sopra la SOTA PR270; nessuna scrittura nel clone operativo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from compila_pr270 import ROOT, BASE, BUILD, CUDA, VC, BIN

FILES = ["include/strata/kernels/fused_gr.hpp", "src/core/verify.cpp", "src/kernels/cuda/fused_gr.cu"]


def integrate_gr(original, incoming):
    """Sostituisce HC opt-in #186 con #315 e conserva il tile per scheda della #258."""
    start = original.index("template <int TILEV>\n__global__ void __launch_bounds__(THREADS) gr_down_multi_kernel")
    end = original.index("constexpr int UPM_COLS", start)
    kernel = original[start:end]
    start = incoming.index("#if defined(__HIPCC__)\nconstexpr int TILE")
    end = incoming.index("constexpr int UPM_COLS", start)
    source = incoming[:start] + "// v1/v2 conservano il tile Turing della patch #258.\n" + kernel + incoming[end:]
    helper = '''int down_tile() {
#if defined(__HIPCC__)
    return 1280;
#else
    int dev = 0, major = 0, minor = 0;
    cudaGetDevice(&dev);
    cudaDeviceGetAttribute(&major, cudaDevAttrComputeCapabilityMajor, dev);
    cudaDeviceGetAttribute(&minor, cudaDevAttrComputeCapabilityMinor, dev);
    return major * 10 + minor == 75 ? 1280 : 2560;
#endif
}

'''
    source = source.replace("int down_chunk(bool v3) {", helper + "int down_chunk(bool v3) {\n    const int tv = down_tile();", 1)
    source = source.replace("kFusedGrMaxT * TILE * sizeof(float)", "kFusedGrMaxT * tv * sizeof(float)", 1)
    old = "        cudaFuncSetAttribute(gr_down_multi_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize, want);"
    new = '''        if (tv == 1280) cudaFuncSetAttribute(gr_down_multi_kernel<1280>, cudaFuncAttributeMaxDynamicSharedMemorySize, want);
        else cudaFuncSetAttribute(gr_down_multi_kernel<2560>, cudaFuncAttributeMaxDynamicSharedMemorySize, want);'''
    assert source.count(old) == 1
    source = source.replace(old, new)
    source = source.replace("(TILE * sizeof(float))", "(tv * sizeof(float))", 1)
    source = source.replace("    const size_t per_tok = (v3 ? (size_t) 2 * H_TILE : (size_t) TILE) * sizeof(float);",
                            "    const int tv = down_tile();\n    const size_t per_tok = (v3 ? (size_t) 2 * H_TILE : (size_t) tv) * sizeof(float);", 1)
    old = "        else gr_down_multi_kernel<<<DOWN_BLOCKS + 1, THREADS, (size_t) ct * per_tok, st>>>(c);"
    new = '''        else if (tv == 1280) gr_down_multi_kernel<1280><<<DOWN_BLOCKS + 1, THREADS, (size_t) ct * per_tok, st>>>(c);
        else gr_down_multi_kernel<2560><<<DOWN_BLOCKS + 1, THREADS, (size_t) ct * per_tok, st>>>(c);'''
    assert source.count(old) == 1
    source = source.replace(old, new)
    assert "STRATA_GR_V3" not in source
    return source


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prepare", "build"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bench", action="store_true", help="Dopo la parita', misura v1/v2/v3 del solo HC")
    a = ap.parse_args()
    out = a.out.resolve()
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    import psutil
    if any((p.info["name"] or "").lower() in ("strata.exe", "llama-server.exe")
           for p in psutil.process_iter(["name"])):
        raise RuntimeError("Motore gia' attivo; non viene fermato")
    env = dict(os.environ)
    if "STRATA_API_KEY" in env:
        raise RuntimeError("Escludere STRATA_API_KEY dal processo di laboratorio")
    for key in ("STRATA_GR_V3", "STRATA_HC_V2"):
        env.pop(key, None)
    git = ["git", "-c", "safe.directory=" + BASE.as_posix(), "-C", str(BASE)]
    def read(ref):
        return subprocess.run(git + ["show", ref], capture_output=True, check=True, env=env).stdout
    if a.mode == "prepare":
        out.mkdir(parents=True, exist_ok=False)
        patch = subprocess.run(git + ["format-patch", "-1", "--stdout", "pr-315"],
                               capture_output=True, check=True, env=env).stdout
        (out / "upstream315.patch").write_bytes(patch)
        conflicts = []
        for path in FILES:
            target = out / "source" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            current = out / "original" / path
            parent = out / "parent" / path
            incoming = out / "incoming" / path
            for dest, contents in [(current, (BASE / path).read_bytes()),
                                   (parent, read("pr-315^:" + path)), (incoming, read("pr-315:" + path))]:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(contents.replace(b"\r\n", b"\n"))
            merged = subprocess.run(["git", "merge-file", "-p", str(current), str(parent), str(incoming)],
                                    capture_output=True, env=env)
            if path == FILES[2] and merged.returncode:
                target.write_text(integrate_gr(current.read_text(), incoming.read_text()), encoding="utf-8")
                print("INTEGRATION: #315 replaces optional #186, keeps #258 per-card tile", flush=True)
                continue
            target.write_bytes(merged.stdout)
            print("MERGE", path, merged.returncode, flush=True)
            if merged.returncode:
                conflicts.append(path)
        if conflicts:
            raise RuntimeError("Conflitti da risolvere nelle copie: " + str(conflicts))
        print("SOURCE_READY", out, flush=True)
        return
    sources = out / "source"
    for path in FILES:
        if b"<<<<<<<" in (sources / path).read_bytes():
            raise RuntimeError("Conflitti ancora presenti in " + path)
    temp = out / "tmp"
    temp.mkdir(exist_ok=True)
    env.update(TEMP=str(temp), TMP=str(temp))
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            k, v = line.split("=", 1)
            env[k] = v
    env["PATH"] = str(CUDA / "bin") + os.pathsep + env.get("Path", env.get("PATH", ""))
    sota = BASE / "build-0130-pr270"
    if hashlib.sha256((sota / "strata.exe").read_bytes()).hexdigest() != "713922610f2820b0e726adc371eb774a7d5502a548d08b59d244afbb38e898ed":
        raise RuntimeError("La SOTA PR270 e' cambiata: rivalutare il confronto")
    evidence = {"pr": 315, "sota": str(sota), "steps": [],
                "integration": "PR315 replaces optional PR186 HC path; PR258 per-card tile and PR270 retained",
                "base_commit": subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True,
                                              env=env, check=True).stdout.decode().strip(),
                "source_sha256": {
        path: hashlib.sha256((sources / path).read_bytes()).hexdigest() for path in FILES}}
    evidence["upstream_commit"] = subprocess.run(git + ["rev-parse", "pr-315"],
        capture_output=True, env=env, check=True).stdout.decode().strip()
    def run(name, args):
        print(name, flush=True)
        begin = time.monotonic()
        with (out / (name + ".log")).open("w", encoding="utf-8") as f:
            p = subprocess.run([str(x) for x in args], cwd=out, env=env, stdout=f, stderr=subprocess.STDOUT)
        evidence["steps"].append({"name": name, "exit": p.returncode,
                                  "seconds": round(time.monotonic() - begin, 2)})
        (out / "build-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        if p.returncode:
            print((out / (name + ".log")).read_text(encoding="utf-8", errors="replace"), flush=True)
            raise RuntimeError(f"{name}: exit {p.returncode}")
    gr = out / "fused_gr.cu.obj"
    verify = out / "verify.cpp.obj"
    run("nvcc-pr315", [CUDA / "bin/nvcc.exe", "-forward-unknown-to-host-compiler",
        "-D_WINDOWS", "-Xcompiler=/EHsc", "-Xcompiler=/O2,/Ob2", "-DNDEBUG", "-std=c++20",
        "--generate-code=arch=compute_75,code=[compute_75,sm_75]",
        "--generate-code=arch=compute_86,code=[compute_86,sm_86]", "-Xcompiler=/MD,/W4",
        "-I" + str(sources / "include"), "-I" + str(BASE / "include"),
        "-c", sources / FILES[2], "-o", gr])
    run("cl-verify-pr315", [BIN / "cl.exe", "/nologo", "/std:c++20", "/EHsc", "/O2", "/Ob2", "/MD",
        "/utf-8", "/DNDEBUG", "/DSTRATA_NATIVE_EXPERTS=1", "/c", "/I" + str(sources / "include"),
        "/I" + str(BASE / "include"), "/I" + str(BASE / "third_party/llama.cpp/ggml/include"),
        "/I" + str(CUDA / "include"), sources / FILES[1], "/Fo:" + str(verify)])
    ninja = (BUILD / "build.ninja").read_text()
    def archive(name, replacements):
        line = next(x for x in ninja.splitlines() if x.startswith("build " + name + ":"))
        members = line.split("Release ", 1)[1].split(" ||", 1)[0].split()
        paths = [replacements.get(x, BUILD / x) for x in members]
        assert all(p.is_file() for p in paths)
        assert all(k in members for k in replacements)
        rsp = out / (name + ".rsp")
        rsp.write_text('/nologo\n/out:"' + str(out / name) + '"\n' +
                       "\n".join('"' + str(p) + '"' for p in paths), encoding="utf-8")
        run("archive-" + name, [BIN / "lib.exe", "@" + str(rsp)])
    archive("strata_kernels.lib", {r"CMakeFiles\strata_kernels.dir\src\kernels\cuda\fused_gr.cu.obj": gr,
        r"CMakeFiles\strata_kernels.dir\src\kernels\cuda\qsa_prompt_attn.cu.obj": sota / "qsa_prompt_attn.cu.obj"})
    archive("strata_engine.lib", {r"CMakeFiles\strata_engine.dir\src\core\verify.cpp.obj": verify})
    libs = [out / "strata_engine.lib", BUILD / "strata_prefill.lib", BUILD / "strata_spec.lib", out / "strata_kernels.lib"]
    libs += [BUILD / x for x in ["strata_core.lib", "strata_kernels_cpu.lib", "ggml/src/ggml-cpu.lib",
                               "strata_mmq.lib", "ggml/src/ggml-base.lib"]]
    libs += [CUDA / "lib/x64" / (x + ".lib") for x in ["cudart", "cuda", "cublas", "cublasLt", "cudadevrt"]]
    libs += [x + ".lib" for x in ["kernel32", "user32", "gdi32", "winspool", "shell32", "ole32", "oleaut32", "uuid", "comdlg32", "advapi32"]]
    run("link-strata-pr315", [BIN / "link.exe", "/nologo", "/machine:x64", "/INCREMENTAL:NO",
        "/subsystem:console", "/DEBUG", "/OPT:REF", "/OPT:ICF", "/MANIFEST:EMBED",
        "/out:" + str(out / "strata.exe"), "/pdb:" + str(out / "strata.pdb"),
        BUILD / "CMakeFiles/strata.dir/src/program/generate.cpp.obj", *libs])
    # Il controllo upstream verifica v1/v2/v3, 1..8 token, con e senza scrittura pendente.
    parity = out / "hc_check.cpp"
    parity.write_text('#include "strata/kernels/fused_gr.hpp"\n#include <cstdio>\n'
                      'int main(){strata::kernels::fused_gr_check(); int v=strata::kernels::fused_gr_variant();'
                      'std::printf("HC_VARIANT=%d\\n",v); return v>=2?0:1;}\n', encoding="utf-8")
    run("compile-hc-check", [BIN / "cl.exe", "/nologo", "/std:c++20", "/EHsc", "/O2", "/MD",
        "/I" + str(sources / "include"), parity, "/Fo:" + str(out / "hc_check.obj"),
        "/Fe:" + str(out / "hc_check.exe"), "/link", out / "strata_kernels.lib",
        BUILD / "strata_core.lib", CUDA / "lib/x64/cudart.lib", CUDA / "lib/x64/cudadevrt.lib"])
    run("hc-check", [out / "hc_check.exe"])
    print((out / "hc-check.log").read_text(), flush=True)
    if a.bench:
        run("compile-hc-bench", [BIN / "cl.exe", "/nologo", "/std:c++20", "/EHsc", "/O2", "/MD",
            "/I" + str(sources / "include"), "/I" + str(CUDA / "include"),
            Path(__file__).with_name("bench_hc315.cpp"), "/Fo:" + str(out / "bench_hc.obj"),
            "/Fe:" + str(out / "bench_hc.exe"), "/link", out / "strata_kernels.lib",
            BUILD / "strata_core.lib", CUDA / "lib/x64/cudart.lib", CUDA / "lib/x64/cudadevrt.lib"])
        for value in ("0", "2", "3"):
            env["STRATA_HC_V2"] = value
            run("bench-hc-v" + value, [out / "bench_hc.exe"])
            print((out / ("bench-hc-v" + value + ".log")).read_text(), flush=True)
        env.pop("STRATA_HC_V2", None)
    evidence["exe_sha256"] = hashlib.sha256((out / "strata.exe").read_bytes()).hexdigest()
    (out / "build-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("BUILD_AND_HC_CHECK_OK", out, flush=True)


if __name__ == "__main__":
    main()
