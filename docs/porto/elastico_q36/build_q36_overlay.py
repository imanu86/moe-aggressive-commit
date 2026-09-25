"""Build a overlay del runtime elastico per Qwen3.6-35B-A3B (arch qwen35moe), 25 settembre 2026.

Ricompila SOLO src/llama-context.cpp (overlay M2 + quattro ritocchi Q36) coi flag originali di
compile_commands.json del build O2 di Codex e ricollega llama.dll dagli altri oggetti/librerie O2,
letti in SOLA LETTURA e verificati con SHA prima e dopo. Tutto il resto del runtime (ggml-cuda.dll
di M2 compresa) e' copiato byte per byte da runtime-m2. Stesso schema di elastico_m3/build_m3_overlay.py.

I quattro ritocchi (vedi evidence/q36-qwen35moe.patch):
  1. costruttore: niente llama_moe_cache_init per il contesto MTP di qwen35moe (col DEMAND acceso la
     seconda init lanciava "one inference context per process");
  2. costruttore: area di lavoro dinamica ammessa anche per LLM_ARCH_QWEN35MOE;
  3. sched_reserve_impl: limit_reserve_kv sulla sola cache d'attenzione della memoria ibrida normale;
  4. decode: `used` letto da llama_memory_hybrid; la cache idx_ solo per qwen4exp.
Il laboratorio sta fuori da git: D:\\ds4_work\\elastico_q36.
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

lab = Path(r"D:\ds4_work\elastico_q36")
old = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920")
m2 = Path(r"D:\ds4_work\elastico_m2")
build, runtime, evidence, originali = lab / "build", lab / "runtime-q36", lab / "evidence", lab / "originali"
ctx_src = lab / "source-overlay" / "src" / "llama-context.cpp"
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

# la base dell'overlay deve essere quella dichiarata: il llama-context.cpp di M2 (produzione)
assert sha(originali / "llama-context.m2.cpp") == sha(m2 / "source-overlay" / "src" / "llama-context.cpp")
assert sorted(p.name for p in ctx_src.parent.iterdir()) == ["llama-context.cpp"]

entries = json.loads((old / "build" / "compile_commands.json").read_text())
ctx_obj = build / "llama-context.cpp.obj"
cmd = next(i["command"] for i in entries if i["file"].replace("\\", "/").endswith("src/llama-context.cpp"))
cmd, n1 = re.subn(r"/Fo\S+", lambda _: "/Fo" + str(ctx_obj).replace("\\", "/"), cmd)
cmd, n2 = re.subn(r"/Fd\S+", lambda _: "/Fd" + str(build / "compile-llama.pdb").replace("\\", "/"), cmd)
assert n1 == n2 == 1 and cmd.endswith(str(ctx_orig))
ctx_cmd = cmd[:-len(str(ctx_orig))] + str(ctx_src)

# --- ricetta di link di llama.dll da build.ninja ---------------------------------------------------
ninja = (old / "build" / "build.ninja").read_text().splitlines()
i = next(k for k, line in enumerate(ninja) if line.startswith("build bin\\llama.dll "))
names = ninja[i].split(": CXX_SHARED_LIBRARY_LINKER__llama_Release ", 1)[1].split(" | ")[0].split()
assert names and all(n.endswith(".obj") for n in names)
objects = [ctx_obj if n.endswith("llama-context.cpp.obj") else old / "build" / n for n in names]
assert objects.count(ctx_obj) == 1
libs_line = next(line for line in ninja[i + 1:i + 16] if line.startswith("  LINK_LIBRARIES = "))
libs = []
for token in libs_line.split(" = ", 1)[1].split():
    token = token.strip('"')
    libs.append(old / "build" / token if ("\\" in token and ":" not in token) else token)
inputs = [p for p in objects if p != ctx_obj] + [p for p in libs if isinstance(p, Path)]
assert all(p.is_file() for p in inputs), [str(p) for p in inputs if not p.is_file()]
input_hashes = {str(p): sha(p) for p in inputs}

# --- runtime di partenza: M2, copiato byte per byte --------------------------------------------------
for item in (m2 / "runtime-m2").iterdir():
    if item.suffix.lower() in (".dll", ".exe"):
        shutil.copy2(item, runtime / item.name)

# --- ambiente MSVC ---------------------------------------------------------------------------------
env_script = build / "import-env.cmd"
env_script.write_text('@echo off\ncall "' + VCVARS + '" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding="ascii")
result = subprocess.run(["cmd.exe", "/d", "/c", str(env_script)], capture_output=True, text=True, check=True, creationflags=NOWIN)
env = dict(os.environ)
for line in result.stdout.splitlines():
    key, sep, value = line.partition("=")
    if sep and key:
        env[key] = value
env["TEMP"] = env["TMP"] = str(build)
compiler = Path(ctx_cmd.split()[0])
linker = compiler.with_name("link.exe")

rsp = build / "llama.rsp"
rsp.write_text("\n".join('"' + str(p) + '"' for p in [*objects, *libs]), encoding="utf-8")
link_llama = [str(linker), "/nologo", "@" + str(rsp), "/out:" + str(runtime / "llama.dll"),
              "/implib:" + str(build / "llama.lib"), "/pdb:" + str(build / "llama.pdb"),
              "/dll", "/version:0.3", "/machine:x64", "/INCREMENTAL:NO", "/MANIFEST:EMBED"]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log = evidence / f"build-q36-{stamp}.log"
with log.open("w", encoding="utf-8") as output:
    for titolo, comando in (("cl llama-context.cpp", ctx_cmd), ("link llama.dll", link_llama)):
        output.write(f"\n===== {titolo} =====\n{comando}\n")
        output.flush()
        t0 = datetime.now()
        subprocess.run(comando, cwd=build, env=env, stdout=output, stderr=subprocess.STDOUT, check=True, creationflags=NOWIN)
        output.write(f"----- ok in {(datetime.now() - t0).total_seconds():.1f} s\n")
        output.flush()

assert all(sha(Path(p)) == h for p, h in input_hashes.items()), "un ingresso O2 e' cambiato durante la build"
unchanged = {}
for item in (m2 / "runtime-m2").iterdir():
    if item.suffix.lower() in (".dll", ".exe") and item.name != "llama.dll":
        assert sha(item) == sha(runtime / item.name)
        unchanged[item.name] = sha(item)

prima = (originali / "llama-context.m2.cpp").read_text(encoding="utf-8").splitlines(keepends=True)
dopo = ctx_src.read_text(encoding="utf-8").splitlines(keepends=True)
patch = "".join(difflib.unified_diff(prima, dopo, fromfile="a/src/llama-context.cpp", tofile="b/src/llama-context.cpp"))
(evidence / "q36-qwen35moe.patch").write_text(patch, encoding="utf-8")

manifest = {"built_utc": datetime.now(timezone.utc).isoformat(), "log": str(log),
            "sources": {str(ctx_src): sha(ctx_src)},
            "compile_commands": {"llama-context.cpp": ctx_cmd},
            "link_commands": {"llama.dll": link_llama},
            "reused_input_sha256": input_hashes, "unchanged_runtime_sha256": unchanged,
            "m2_sha256": {"llama.dll": sha(m2 / "runtime-m2" / "llama.dll")},
            "q36_sha256": {"llama.dll": sha(runtime / "llama.dll")},
            "note": "Oggetti e librerie O2 riusati in sola lettura, SHA verificato dopo la build; ggml-cuda.dll e' quella di M2."}
(evidence / "q36-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"runtime": str(runtime), "log": str(log), "riusati": len(inputs), "q36_sha256": manifest["q36_sha256"]}))
