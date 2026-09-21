"""Build a overlay del runtime M2 (ripristino delle pagine prima del prefill), 21 settembre 2026.

Ricompila SOLO due oggetti coi flag originali di compile_commands.json del build O2 di Codex:
  - ggml/src/ggml-cuda/ggml-cuda.cu   (include moe-demand.cuh -> moe-ram-store.cuh) -> ggml-cuda.dll
  - src/llama-context.cpp             (overlay M1 + canary che ripristina)           -> llama.dll
e ricollega le due DLL dagli altri oggetti/librerie O2, letti in SOLA LETTURA e verificati con SHA
prima e dopo. Tutti gli output restano in questa cartella; il resto del runtime e' copiato da runtime-m1.
Stesso schema di qwen_ram_mtp_20260920/build_context_overlay.py.
"""
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

lab = Path(__file__).resolve().parent
old = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920")
m1 = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_mtp_20260920")
build, runtime, evidence, originali = lab / "build", lab / "runtime-m2", lab / "evidence", lab / "originali"
overlay = lab / "source-overlay"
cuda_src = overlay / "ggml" / "src" / "ggml-cuda" / "ggml-cuda.cu"
ctx_src = overlay / "src" / "llama-context.cpp"
cuda_orig = old / "source" / "ggml" / "src" / "ggml-cuda" / "ggml-cuda.cu"
ctx_orig = old / "source" / "src" / "llama-context.cpp"
VCVARS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
NOWIN = subprocess.CREATE_NO_WINDOW


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


vivi = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"], capture_output=True, text=True).stdout
if "llama-server.exe" in vivi:
    sys.exit("ERRORE: c'e' un llama-server vivo: non compilo sopra un'inferenza.")
for folder in (build, runtime, evidence):
    folder.mkdir(exist_ok=True)

entries = json.loads((old / "build" / "compile_commands.json").read_text())


def entry(suffix: str) -> str:
    return next(i["command"] for i in entries if i["file"].replace("\\", "/").endswith(suffix))


# --- llama-context.cpp (cl) ---------------------------------------------------------------------
ctx_obj = build / "llama-context.cpp.obj"
ctx_cmd = entry("src/llama-context.cpp")
ctx_cmd, n1 = re.subn(r"/Fo\S+", lambda _: "/Fo" + str(ctx_obj).replace("\\", "/"), ctx_cmd)
ctx_cmd, n2 = re.subn(r"/Fd\S+", lambda _: "/Fd" + str(build / "compile-llama.pdb").replace("\\", "/"), ctx_cmd)
assert n1 == n2 == 1 and ctx_cmd.endswith(str(ctx_orig))
ctx_cmd = ctx_cmd[:-len(str(ctx_orig))] + str(ctx_src)

# --- ggml-cuda.cu (nvcc) ------------------------------------------------------------------------
cuda_obj = build / "ggml-cuda.cu.obj"
cuda_cmd = entry("ggml-cuda/ggml-cuda.cu")
inc_orig = "-I" + str(old / "source" / "ggml" / "src" / "ggml-cuda") + "\\.."
assert cuda_cmd.count(inc_orig) == 1, "include di ggml/src non trovata nel comando nvcc"
# l'overlay davanti: ogni «ggml-cuda/...» si risolve nella copia M2, il resto di ggml/src nell'originale
cuda_cmd = cuda_cmd.replace(inc_orig, "-I" + str(overlay / "ggml" / "src") + " " + inc_orig)
cuda_cmd, n3 = re.subn(r" -o \S+", lambda _: " -o " + str(cuda_obj), cuda_cmd)
cuda_cmd, n4 = re.subn(r"-Xcompiler=-Fd\S+", lambda _: "-Xcompiler=-Fd" + str(build) + "\\,-FS", cuda_cmd)
assert n3 == n4 == 1 and cuda_cmd.count(str(cuda_orig)) == 1
cuda_cmd = cuda_cmd.replace(str(cuda_orig), str(cuda_src))

# --- ricette di link da build.ninja ---------------------------------------------------------------
ninja = (old / "build" / "build.ninja").read_text().splitlines()


def ricetta(prefisso: str, regola: str, mio: Path, nome_obj: str):
    i = next(k for k, line in enumerate(ninja) if line.startswith(prefisso))
    names = ninja[i].split(": " + regola + " ", 1)[1].split(" | ")[0].split()
    assert names and all(n.endswith(".obj") for n in names)
    objects = [mio if n.endswith(nome_obj) else old / "build" / n for n in names]
    assert objects.count(mio) == 1
    libs_line = next(line for line in ninja[i + 1:i + 16] if line.startswith("  LINK_LIBRARIES = "))
    libs = []
    for token in shlex.split(libs_line.split(" = ", 1)[1], posix=False):
        token = token.strip('"')
        libs.append(old / "build" / token if ("\\" in token and ":" not in token) else token)
    return objects, libs


cuda_objects, cuda_libs = ricetta("build bin\\ggml-cuda.dll ", "CUDA_SHARED_LIBRARY_LINKER__ggml-cuda_Release", cuda_obj, "ggml-cuda.cu.obj")
ctx_objects, ctx_libs = ricetta("build bin\\llama.dll ", "CXX_SHARED_LIBRARY_LINKER__llama_Release", ctx_obj, "llama-context.cpp.obj")
inputs = [p for p in cuda_objects + ctx_objects if p not in (cuda_obj, ctx_obj)] + \
         [p for p in cuda_libs + ctx_libs if isinstance(p, Path)]
assert all(p.is_file() for p in inputs), [str(p) for p in inputs if not p.is_file()]
input_hashes = {str(p): sha(p) for p in inputs}

# --- runtime di partenza: M1 (= O2 + llama.dll di M1), copiato byte per byte ----------------------
for item in (m1 / "runtime-m1").iterdir():
    if item.suffix.lower() in (".dll", ".exe"):
        shutil.copy2(item, runtime / item.name)

# --- ambiente MSVC -------------------------------------------------------------------------------
env_script = build / "import-env.cmd"
env_script.write_text('@echo off\ncall "' + VCVARS + '" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding="ascii")
result = subprocess.run(["cmd.exe", "/d", "/c", str(env_script)], capture_output=True, text=True, check=True, creationflags=NOWIN)
env = dict(os.environ)
for line in result.stdout.splitlines():
    key, sep, value = line.partition("=")
    if sep and key:
        env[key] = value
env["TEMP"] = env["TMP"] = str(build)
linker = Path(ctx_cmd.split()[0]).with_name("link.exe")


def link_command(nome: str, objects, libs, versione: str, extra=()):
    rsp = build / (nome + ".rsp")
    rsp.write_text("\n".join('"' + str(p) + '"' for p in [*objects, *libs]), encoding="utf-8")
    return [str(linker), "/nologo", "@" + str(rsp), "/out:" + str(runtime / (nome + ".dll")),
            "/implib:" + str(build / (nome + ".lib")), "/pdb:" + str(build / (nome + ".pdb")),
            "/dll", "/version:" + versione, "/machine:x64", "/INCREMENTAL:NO", "/MANIFEST:EMBED", *extra]


link_cuda = link_command("ggml-cuda", cuda_objects, cuda_libs, "0.22",
                         ['-LIBPATH:C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/lib/x64'])
link_llama = link_command("llama", ctx_objects, ctx_libs, "0.3")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log = evidence / f"build-m2-{stamp}.log"
with log.open("w", encoding="utf-8") as output:
    for titolo, comando in (("cl llama-context.cpp", ctx_cmd), ("nvcc ggml-cuda.cu", cuda_cmd),
                            ("link ggml-cuda.dll", link_cuda), ("link llama.dll", link_llama)):
        output.write(f"\n===== {titolo} =====\n{comando}\n")
        output.flush()
        t0 = datetime.now()
        subprocess.run(comando, cwd=build, env=env, stdout=output, stderr=subprocess.STDOUT, check=True, creationflags=NOWIN)
        output.write(f"----- ok in {(datetime.now() - t0).total_seconds():.1f} s\n")
        output.flush()

assert all(sha(Path(p)) == h for p, h in input_hashes.items()), "un ingresso O2 e' cambiato durante la build"
unchanged = {}
for item in (m1 / "runtime-m1").iterdir():
    if item.suffix.lower() in (".dll", ".exe") and item.name not in ("llama.dll", "ggml-cuda.dll"):
        assert sha(item) == sha(runtime / item.name)
        unchanged[item.name] = sha(item)

patch = ""
for a, b, nome in ((originali / "moe-ram-store.cuh", overlay / "ggml/src/ggml-cuda/moe-ram-store.cuh", "ggml/src/ggml-cuda/moe-ram-store.cuh"),
                   (originali / "ggml-cuda.cu", cuda_src, "ggml/src/ggml-cuda/ggml-cuda.cu"),
                   (originali / "llama-context.m1.cpp", ctx_src, "src/llama-context.cpp")):
    patch += "".join(difflib.unified_diff(a.read_text(encoding="utf-8").splitlines(keepends=True),
                                          b.read_text(encoding="utf-8").splitlines(keepends=True),
                                          fromfile="a/" + nome, tofile="b/" + nome))
(evidence / "m2-restore-before-prefill.patch").write_text(patch, encoding="utf-8")

# l'overlay di ggml-cuda deve differire dall'originale SOLO nei due file toccati
diversi = sorted(str(p.relative_to(overlay / "ggml/src/ggml-cuda")) for p in (overlay / "ggml/src/ggml-cuda").rglob("*")
                 if p.is_file() and sha(p) != sha(old / "source/ggml/src/ggml-cuda" / p.relative_to(overlay / "ggml/src/ggml-cuda")))
assert diversi == ["ggml-cuda.cu", "moe-ram-store.cuh"], diversi

manifest = {"built_utc": datetime.now(timezone.utc).isoformat(), "log": str(log),
            "sources": {str(p): sha(p) for p in (overlay / "ggml/src/ggml-cuda/moe-ram-store.cuh", cuda_src, ctx_src)},
            "compile_commands": {"llama-context.cpp": ctx_cmd, "ggml-cuda.cu": cuda_cmd},
            "link_commands": {"ggml-cuda.dll": link_cuda, "llama.dll": link_llama},
            "reused_input_sha256": input_hashes, "unchanged_runtime_sha256": unchanged,
            "overlay_files_differing_from_O2": diversi,
            "m1_sha256": {n: sha(m1 / "runtime-m1" / n) for n in ("llama.dll", "ggml-cuda.dll")},
            "m2_sha256": {n: sha(runtime / n) for n in ("llama.dll", "ggml-cuda.dll")},
            "note": "Oggetti e librerie O2 riusati in sola lettura, SHA verificato dopo la build."}
(evidence / "m2-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"runtime": str(runtime), "log": str(log), "riusati": len(inputs), "m2_sha256": manifest["m2_sha256"]}))
