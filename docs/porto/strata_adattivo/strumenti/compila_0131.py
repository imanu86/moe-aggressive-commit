"""Build isolata della 0.1.31 con dipendenze locali e controlli numerici sm75."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(r"D:\ds4_work\strata\Strata")
CUDA = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6")
VC = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC")
CMAKE = Path(r"C:\Users\imanu\AppData\Local\Programs\Python\Python312\Scripts\cmake.exe")
NINJA = CMAKE.with_name("ninja.exe")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    out = a.out.resolve(strict=True)
    source = out / "source"
    build = out / "build"
    assert json.loads((out / "porting.json").read_text(encoding="utf-8"))["status"] == "completed"
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    import psutil
    if any((p.info["name"] or "").lower() in ("strata.exe", "llama-server.exe")
           for p in psutil.process_iter(["name"])):
        raise RuntimeError("Motore attivo: attendere prima della compilazione")
    env = dict(os.environ)
    if "STRATA_API_KEY" in env:
        raise RuntimeError("Escludere STRATA_API_KEY dal processo di laboratorio")
    temp = out / "tmp"
    temp.mkdir(exist_ok=True)
    env.update(TEMP=str(temp), TMP=str(temp), PYTHONUTF8="1")
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            env[key] = value
    env["PATH"] = str(CUDA / "bin") + os.pathsep + env.get("Path", env.get("PATH", ""))
    result_path = out / "build-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {"steps": []}
    def run(name, args):
        print(name, flush=True)
        begin = time.monotonic()
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(list(map(str, args)), cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
        result["steps"].append({"name": name, "exit": p.returncode, "seconds": round(time.monotonic() - begin, 2)})
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if p.returncode:
            print((out / (name + ".log")).read_text(encoding="utf-8", errors="replace")[-18000:], flush=True)
            raise RuntimeError(f"{name}: exit {p.returncode}")
    run("configure", [CMAKE, "-S", source, "-B", build, "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_MAKE_PROGRAM=" + str(NINJA),
        "-DCMAKE_CUDA_COMPILER=" + str(CUDA / "bin/nvcc.exe"), "-DCMAKE_CUDA_ARCHITECTURES=75;86",
        "-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared",
        "-DSTRATA_ENABLE_CUDA=ON", "-DSTRATA_ENABLE_HIP=OFF", "-DSTRATA_BUILD_TESTS=OFF",
        "-DSTRATA_PARITY_PROMPT_ATTN=ON", "-DSTRATA_NATIVE_EXPERTS=ON",
        "-DSTRATA_GGML_DIR=" + str(BASE / "third_party/llama.cpp"),
        "-DFETCHCONTENT_FULLY_DISCONNECTED=ON", "-DPython3_EXECUTABLE=" + sys.executable])
    run("compile", [CMAKE, "--build", build, "--parallel", "2", "--target", "strata",
        "iq_multi_parity", "mmvq_multi_parity", "gr_parity", "qsa_prompt_attn_parity", "native_expert_bench"])
    for name, args in [("iq_multi_parity", []), ("mmvq_multi_parity", []), ("gr_parity", ["--selftest"]),
                       ("qsa_prompt_attn_parity", ["32768", "128", "1"])]:
        run("check-" + name, [build / (name + ".exe"), *args])
        print((out / ("check-" + name + ".log")).read_text(encoding="utf-8", errors="replace")[-2000:], flush=True)
    result["exe_sha256"] = hashlib.sha256((build / "strata.exe").read_bytes()).hexdigest()
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("BUILD_AND_PARITY_OK", build, flush=True)


if __name__ == "__main__":
    main()
