"""Build isolated #547 candidate and its targeted CUDA regression binaries."""
from pathlib import Path
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source-547"
BUILD = HERE / "build-547"
VC = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC")
CM = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake")
CUDA = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6")
GGML = Path(r"D:\ds4_work\strata\Strata\third_party\llama.cpp")
PYTHON = Path(sys.executable)

env = dict(os.environ)
env.pop("STRATA_API_KEY", None)
p = subprocess.run(
    f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
    capture_output=True, text=True, encoding="cp1252", errors="replace",
    env=env, creationflags=subprocess.CREATE_NO_WINDOW,
)
if p.returncode:
    raise RuntimeError(p.stdout + p.stderr)
for line in p.stdout.splitlines():
    if "=" in line and not line.startswith("="):
        k, v = line.split("=", 1)
        env[k] = v
env.pop("STRATA_API_KEY", None)
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PATH"] = str(CUDA / "bin") + os.pathsep + env.get("PATH", "")

def run(command, name, timeout=3600):
    log = HERE / f"{name}.log"
    print("START", name, flush=True)
    with log.open("w", encoding="utf-8") as f:
        q = subprocess.run([str(x) for x in command], cwd=HERE, env=env, stdout=f,
                           stderr=subprocess.STDOUT, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    if q.returncode:
        print(log.read_text(encoding="utf-8", errors="replace")[-10000:])
        raise RuntimeError(f"{name} failed: {q.returncode}")
    print("DONE", name, "log", log, flush=True)

run([
    CM / "CMake/bin/cmake.exe", "-S", SOURCE, "-B", BUILD, "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_MAKE_PROGRAM={CM / 'Ninja/ninja.exe'}",
    f"-DCMAKE_CUDA_COMPILER={CUDA / 'bin/nvcc.exe'}", "-DCMAKE_CUDA_ARCHITECTURES=75",
    "-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc", "-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared",
    "-DSTRATA_ENABLE_CUDA=ON", "-DSTRATA_ENABLE_HIP=OFF", "-DSTRATA_BUILD_TESTS=ON",
    "-DSTRATA_PARITY_PROMPT_ATTN=ON", "-DSTRATA_NATIVE_EXPERTS=ON",
    f"-DSTRATA_GGML_DIR={GGML}", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
    f"-DPython3_EXECUTABLE={PYTHON}",
], "configure_547")
targets = [
    "strata", "expert_cache_elastic_test", "expert_cache_per_layer_test",
    "expert_profile_save_test", "qsa_topk_active_parity", "gr_parity", "gdn_parity",
    "pool_quant_parity",
]
run([CM / "CMake/bin/cmake.exe", "--build", BUILD, "--parallel", "2", "--target", *targets],
    "build_547")
run([CM / "CMake/bin/ctest.exe", "--test-dir", BUILD, "--output-on-failure", "-R",
     "^(qsa_topk_active_parity|gr_parity|gdn_parity|expert_cache_elastic_test|expert_cache_per_layer_test|expert_profile_save_test)$"],
    "ctest_547")
run([BUILD / "pool_quant_parity.exe",
     r"C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"],
    "pool_quant_547")
metadata = {
    "candidate_exe": str(BUILD / "strata.exe"),
    "candidate_binary_sha256": __import__("hashlib").sha256((BUILD / "strata.exe").read_bytes()).hexdigest(),
    "source_manifest_sha256": __import__("hashlib").sha256((SOURCE / "source-manifest.json").read_bytes()).hexdigest()
        if (SOURCE / "source-manifest.json").is_file() else None,
    "build": "CUDA SM75, Release, targeted regression suite passed",
}
(HERE / "build-547.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(json.dumps(metadata, indent=2), flush=True)

