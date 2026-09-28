"""Build a overlay del runtime M2g (M2 + cancello RAM della crescita corretto), 28 settembre 2026.

Il difetto (docs/porto/strata_prova/RISULTATI_28_SETTEMBRE.md): con la RAM sotto pressione la cache elastica di M2 va a
0 slot al primo prefill e non ricresce piu', perche' llama_moe_ram_growth_gate nega ogni crescita sotto 2 GiB di RAM
disponibile (e finche' non si resta 15 s sopra 2,5 GiB) anche quando la crescita non alloca RAM (pending_ram_bytes 0).
M2g applica il cancello solo quando la crescita alloca RAM (nuovi trasporti RAM), e ricalcola pending_ram_bytes anche nel
resize. Nient'altro cambia.

Ricompila SOLO src/llama-moecache.cpp coi flag originali di compile_commands.json del build O2 di Codex e ricollega
llama.dll con l'oggetto llama-context.cpp di M2 (D:\\ds4_work\\elastico_m2\\build, in sola lettura) e gli altri oggetti O2,
tutti verificati con SHA prima e dopo. ggml-cuda.dll e il resto del runtime sono copiati byte per byte da runtime-m2
(= bin_elastico_m2 della produzione, che non viene toccata). Il laboratorio sta fuori da git.
Stesso schema di elastico_m3/build_m3_overlay.py.
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

HERE = Path(__file__).resolve().parent
lab = Path(r"D:\ds4_work\elastico_m2g")
old = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920")
m2 = Path(r"D:\ds4_work\elastico_m2")
build, runtime, evidence, originali = lab / "build", lab / "runtime-m2g", lab / "evidence", lab / "originali"
cache_src = lab / "source-overlay" / "src" / "llama-moecache.cpp"
cache_orig = old / "source" / "src" / "llama-moecache.cpp"
ctx_obj_m2 = m2 / "build" / "llama-context.cpp.obj"
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

# la base dell'overlay deve essere il llama-moecache.cpp di O2 con cui e' stato collegato M2
assert sha(originali / "llama-moecache.cpp") == sha(cache_orig)
assert sha(m2 / "runtime-m2" / "llama.dll") == sha(Path(r"D:\ds4_work\bin_elastico_m2\llama.dll")), "runtime-m2 != produzione"

entries = json.loads((old / "build" / "compile_commands.json").read_text())
cmd = next(i["command"] for i in entries if i["file"].replace("\\", "/").endswith("src/llama-moecache.cpp"))
cache_obj = build / "llama-moecache.cpp.obj"
cmd, n1 = re.subn(r"/Fo\S+", lambda _: "/Fo" + str(cache_obj).replace("\\", "/"), cmd)
cmd, n2 = re.subn(r"/Fd\S+", lambda _: "/Fd" + str(build / "compile-llama.pdb").replace("\\", "/"), cmd)
assert n1 == n2 == 1 and cmd.endswith(str(cache_orig))
cache_cmd = cmd[:-len(str(cache_orig))] + str(cache_src)

# --- ricetta di link di llama.dll da build.ninja: il nostro llama-moecache, il llama-context di M2 --------
ninja = (old / "build" / "build.ninja").read_text().splitlines()
i = next(k for k, line in enumerate(ninja) if line.startswith("build bin\\llama.dll "))
names = ninja[i].split(": CXX_SHARED_LIBRARY_LINKER__llama_Release ", 1)[1].split(" | ")[0].split()
assert names and all(n.endswith(".obj") for n in names)
sostituti = {"llama-moecache.cpp.obj": cache_obj, "llama-context.cpp.obj": ctx_obj_m2}
objects = [next((mio for fine, mio in sostituti.items() if n.endswith(fine)), None) or old / "build" / n for n in names]
assert all(objects.count(mio) == 1 for mio in sostituti.values())
libs_line = next(line for line in ninja[i + 1:i + 16] if line.startswith("  LINK_LIBRARIES = "))
libs = []
for token in shlex.split(libs_line.split(" = ", 1)[1], posix=False):
    token = token.strip('"')
    libs.append(old / "build" / token if ("\\" in token and ":" not in token) else token)
inputs = [p for p in objects if p != cache_obj] + [p for p in libs if isinstance(p, Path)]
assert all(p.is_file() for p in inputs), [str(p) for p in inputs if not p.is_file()]
input_hashes = {str(p): sha(p) for p in inputs}

# --- runtime di partenza: M2, copiato byte per byte ------------------------------------------------------
for item in (m2 / "runtime-m2").iterdir():
    if item.suffix.lower() in (".dll", ".exe"):
        shutil.copy2(item, runtime / item.name)

# --- ambiente MSVC ---------------------------------------------------------------------------------------
env_script = build / "import-env.cmd"
env_script.write_text('@echo off\ncall "' + VCVARS + '" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding="ascii")
result = subprocess.run(["cmd.exe", "/d", "/c", str(env_script)], capture_output=True, text=True, check=True, creationflags=NOWIN)
env = dict(os.environ)
for line in result.stdout.splitlines():
    key, sep, value = line.partition("=")
    if sep and key:
        env[key] = value
env["TEMP"] = env["TMP"] = str(build)
linker = Path(cache_cmd.split()[0]).with_name("link.exe")
rsp = build / "llama.rsp"
rsp.write_text("\n".join('"' + str(p) + '"' for p in [*objects, *libs]), encoding="utf-8")
link_llama = [str(linker), "/nologo", "@" + str(rsp), "/out:" + str(runtime / "llama.dll"),
              "/implib:" + str(build / "llama.lib"), "/pdb:" + str(build / "llama.pdb"),
              "/dll", "/version:0.3", "/machine:x64", "/INCREMENTAL:NO", "/MANIFEST:EMBED"]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log = evidence / f"build-m2g-{stamp}.log"
with log.open("w", encoding="utf-8") as output:
    for titolo, comando in (("cl llama-moecache.cpp", cache_cmd), ("link llama.dll", link_llama)):
        output.write(f"\n===== {titolo} =====\n{comando}\n")
        output.flush()
        t0 = datetime.now()
        subprocess.run(comando, cwd=build, env=env, stdout=output, stderr=subprocess.STDOUT, check=True, creationflags=NOWIN)
        output.write(f"----- ok in {(datetime.now() - t0).total_seconds():.1f} s\n")
        output.flush()

assert all(sha(Path(p)) == h for p, h in input_hashes.items()), "un ingresso e' cambiato durante la build"
unchanged = {}
for item in (m2 / "runtime-m2").iterdir():
    if item.suffix.lower() in (".dll", ".exe") and item.name != "llama.dll":
        assert sha(item) == sha(runtime / item.name)
        unchanged[item.name] = sha(item)

patch = "".join(difflib.unified_diff(originali.joinpath("llama-moecache.cpp").read_text(encoding="utf-8").splitlines(keepends=True),
                                     cache_src.read_text(encoding="utf-8").splitlines(keepends=True),
                                     fromfile="a/src/llama-moecache.cpp", tofile="b/src/llama-moecache.cpp"))
for dove in (evidence / "m2g-cancello-ram.patch", HERE / "m2g-cancello-ram.patch"):
    dove.write_text(patch, encoding="utf-8")

manifest = {"built_utc": datetime.now(timezone.utc).isoformat(), "log": str(log),
            "sources": {str(cache_src): sha(cache_src)}, "compile_commands": {"llama-moecache.cpp": cache_cmd},
            "link_commands": {"llama.dll": link_llama}, "reused_input_sha256": input_hashes,
            "unchanged_runtime_sha256": unchanged, "m2_sha256": {"llama.dll": sha(m2 / "runtime-m2" / "llama.dll")},
            "m2g_sha256": {"llama.dll": sha(runtime / "llama.dll")},
            "note": "Oggetti O2 e llama-context.cpp.obj di M2 riusati in sola lettura; ggml-cuda.dll e' quella di M2."}
(evidence / "m2g-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"runtime": str(runtime), "log": str(log), "riusati": len(inputs), "m2g_sha256": manifest["m2g_sha256"]}))
