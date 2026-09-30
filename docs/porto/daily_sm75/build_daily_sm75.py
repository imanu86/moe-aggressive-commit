"""Ricompila il daily (runtime elastico M2) per la RTX 2080 Ti (sm_75), 30/9/2026.

Produzione = oggetti del build O2 di Codex + overlay M2 (ggml-cuda.cu, moe-ram-store.cuh, llama-context.cpp), tutto
compilato solo per sm_86. Qui: copia del sorgente base di Codex (in sola lettura), i 3 file M2 sopra, stesse opzioni
CMake del build O2 (lette dal suo CMakeCache.txt) con CMAKE_CUDA_ARCHITECTURES=75, build completa di llama-server.
Niente di esistente viene toccato: bin_elastico_m2, il bat del daily, l'albero di Codex e D:\\ds4_work\\elastico_m2.
Uscita: D:\\ds4_work\\daily_sm75\\runtime (stessi nomi di file della produzione).

Uso:  python build_daily_sm75.py
"""
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

CODEX = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920")
OVL = Path(r"D:\ds4_work\elastico_m2\source-overlay")
PROD = Path(r"D:\ds4_work\bin_elastico_m2")
LAB = Path(r"D:\ds4_work\daily_sm75")
M2 = ["ggml/src/ggml-cuda/ggml-cuda.cu", "ggml/src/ggml-cuda/moe-ram-store.cuh", "src/llama-context.cpp"]
S = Path(r"D:\ds4_work\strata\Strata\.venv\Scripts")   # cmake e ninja gia' usati per Strata
VCVARS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
ARCH = sys.argv[1] if len(sys.argv) > 1 else "75"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    src, build, runtime = LAB / "source", LAB / "build", LAB / "runtime"
    LAB.mkdir(parents=True, exist_ok=True)
    # esclusioni per percorso intero: con il solo nome, /XD models toglieva anche tools/mtmd/models (sorgente).
    # robocopy e' incrementale; i file M2 vengono rimessi subito dopo.
    base = CODEX / "source"
    r = subprocess.run(["robocopy", str(base), str(src), "/E", "/XD", str(base / ".git"), str(base / "build"),
                        str(base / "models"), "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True, text=True)
    assert r.returncode < 8, r.stdout + r.stderr
    for rel in M2:
        a, b = OVL / rel, src / rel
        assert sha(a) != sha(CODEX / "source" / rel), "overlay uguale alla base: " + rel
        shutil.copy2(a, b)
        assert sha(a) == sha(b)
    # opzioni del build O2 (solo quelle scelte, non le interne), architettura sostituita
    righe = (CODEX / "build" / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    init = []
    for r in righe:
        m = re.match(r"^((?:GGML|LLAMA)_[A-Z0-9_]+|BUILD_SHARED_LIBS|CMAKE_BUILD_TYPE|CMAKE_CUDA_COMPILER)"
                     r":(BOOL|STRING|FILEPATH|PATH|UNINITIALIZED)=(.*)$", r)
        if m:
            k, t, v = m.groups()
            t = "STRING" if t == "UNINITIALIZED" else t
            init.append('set(%s "%s" CACHE %s "")' % (k, v.replace("\\", "/"), t))
    init.append('set(CMAKE_CUDA_ARCHITECTURES "%s" CACHE STRING "")' % ARCH)
    (LAB / "init.cmake").write_text("\n".join(init) + "\n", encoding="utf-8")
    bat = LAB / "build.bat"
    bat.write_text("\r\n".join([
        "@echo off",
        'call "%s" >nul' % VCVARS,
        '"%s\\cmake.exe" -G Ninja "-DCMAKE_MAKE_PROGRAM=%s\\ninja.exe" -S "%s" -B "%s" -C "%s" || exit /b 1'
        % (S, S, src, build, LAB / "init.cmake"),
        '"%s\\cmake.exe" --build "%s" --target llama-server -j 8 || exit /b 1' % (S, build),
    ]) + "\r\n", encoding="ascii")
    r = subprocess.run(["cmd", "/c", str(bat)], stdout=open(LAB / "build.log", "w", encoding="utf-8"),
                       stderr=subprocess.STDOUT)
    if r.returncode != 0:
        print("BUILD FALLITA, vedi", LAB / "build.log")
        return 1
    runtime.mkdir(exist_ok=True)
    mancanti = []
    for f in PROD.iterdir():
        if f.suffix.lower() in (".exe", ".dll"):
            nuovo = build / "bin" / f.name
            if nuovo.exists():
                shutil.copy2(nuovo, runtime / f.name)
            else:
                mancanti.append(f.name)
    print("runtime:", runtime, "- file della produzione non prodotti dalla build:", mancanti or "nessuno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
