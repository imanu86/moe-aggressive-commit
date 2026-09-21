"""Build a overlay del runtime M3 (politica elastica con banda morta), 21 settembre 2026.

Ricompila SOLO due oggetti di llama.dll coi flag originali di compile_commands.json del build O2 di Codex:
  - src/llama-moecache.cpp   (politica M3; include il nuovo llama-moecache-policy-m3.h)
  - src/llama-context.cpp    (overlay M2 + agganci M3 al cambio d'area di lavoro)
e ricollega llama.dll dagli altri oggetti/librerie O2, letti in SOLA LETTURA e verificati con SHA prima e
dopo. Tutto il resto del runtime (ggml-cuda.dll di M2 compresa) e' copiato byte per byte da runtime-m2.
Prima della build compila ed esegue il test autonomo della politica: se non passa, non si collega niente.
Stesso schema di elastico_m1_canary/m2/build_m2_overlay.py. Il laboratorio sta fuori da git.
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

lab = Path(r"D:\ds4_work\elastico_m3")
old = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920")
m2 = Path(r"D:\ds4_work\elastico_m2")
build, runtime, evidence, originali = lab / "build", lab / "runtime-m3", lab / "evidence", lab / "originali"
overlay = lab / "source-overlay" / "src"
ctx_src, cache_src, policy_src = overlay / "llama-context.cpp", overlay / "llama-moecache.cpp", overlay / "llama-moecache-policy-m3.h"
ctx_orig = old / "source" / "src" / "llama-context.cpp"
cache_orig = old / "source" / "src" / "llama-moecache.cpp"
test_src = lab / "tests" / "policy_m3_test.cpp"
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

# le basi dell'overlay devono essere quelle dichiarate: M2 per il contesto, O2 di Codex per la cache
assert sha(originali / "llama-context.m2.cpp") == sha(m2 / "source-overlay" / "src" / "llama-context.cpp")
assert sha(originali / "llama-moecache.cpp") == sha(cache_orig)
assert sorted(p.name for p in overlay.iterdir()) == ["llama-context.cpp", "llama-moecache-policy-m3.h", "llama-moecache.cpp"]

entries = json.loads((old / "build" / "compile_commands.json").read_text())


def compile_command(suffix: str, orig: Path, mio: Path, obj: Path) -> str:
    cmd = next(i["command"] for i in entries if i["file"].replace("\\", "/").endswith(suffix))
    cmd, n1 = re.subn(r"/Fo\S+", lambda _: "/Fo" + str(obj).replace("\\", "/"), cmd)
    cmd, n2 = re.subn(r"/Fd\S+", lambda _: "/Fd" + str(build / "compile-llama.pdb").replace("\\", "/"), cmd)
    assert n1 == n2 == 1 and cmd.endswith(str(orig)), suffix
    return cmd[:-len(str(orig))] + str(mio)


ctx_obj, cache_obj = build / "llama-context.cpp.obj", build / "llama-moecache.cpp.obj"
ctx_cmd = compile_command("src/llama-context.cpp", ctx_orig, ctx_src, ctx_obj)
cache_cmd = compile_command("src/llama-moecache.cpp", cache_orig, cache_src, cache_obj)

# --- ricetta di link di llama.dll da build.ninja ---------------------------------------------------
ninja = (old / "build" / "build.ninja").read_text().splitlines()
i = next(k for k, line in enumerate(ninja) if line.startswith("build bin\\llama.dll "))
names = ninja[i].split(": CXX_SHARED_LIBRARY_LINKER__llama_Release ", 1)[1].split(" | ")[0].split()
assert names and all(n.endswith(".obj") for n in names)
miei = {"llama-context.cpp.obj": ctx_obj, "llama-moecache.cpp.obj": cache_obj}
objects = [next((mio for fine, mio in miei.items() if n.endswith(fine)), None) or old / "build" / n for n in names]
assert all(objects.count(mio) == 1 for mio in miei.values())
libs_line = next(line for line in ninja[i + 1:i + 16] if line.startswith("  LINK_LIBRARIES = "))
libs = []
for token in shlex.split(libs_line.split(" = ", 1)[1], posix=False):
    token = token.strip('"')
    libs.append(old / "build" / token if ("\\" in token and ":" not in token) else token)
inputs = [p for p in objects if p not in miei.values()] + [p for p in libs if isinstance(p, Path)]
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

test_exe = build / "policy_m3_test.exe"
test_cmd = [str(compiler), "/nologo", "/std:c++17", "/EHsc", "/W3", "/I" + str(overlay), "/I" + str(old / "source" / "src"),
            "/Fo" + str(build / "policy_m3_test.obj"), "/Fe" + str(test_exe), str(test_src)]
rsp = build / "llama.rsp"
rsp.write_text("\n".join('"' + str(p) + '"' for p in [*objects, *libs]), encoding="utf-8")
link_llama = [str(linker), "/nologo", "@" + str(rsp), "/out:" + str(runtime / "llama.dll"),
              "/implib:" + str(build / "llama.lib"), "/pdb:" + str(build / "llama.pdb"),
              "/dll", "/version:0.3", "/machine:x64", "/INCREMENTAL:NO", "/MANIFEST:EMBED"]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log = evidence / f"build-m3-{stamp}.log"
with log.open("w", encoding="utf-8") as output:
    for titolo, comando in (("cl policy_m3_test.cpp", test_cmd), ("policy_m3_test", [str(test_exe)]),
                            ("cl llama-moecache.cpp", cache_cmd), ("cl llama-context.cpp", ctx_cmd),
                            ("link llama.dll", link_llama)):
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

patch = ""
for a, b, nome in ((originali / "llama-moecache.cpp", cache_src, "src/llama-moecache.cpp"),
                   (originali / "llama-context.m2.cpp", ctx_src, "src/llama-context.cpp"),
                   (None, policy_src, "src/llama-moecache-policy-m3.h")):
    prima = a.read_text(encoding="utf-8").splitlines(keepends=True) if a else []
    patch += "".join(difflib.unified_diff(prima, b.read_text(encoding="utf-8").splitlines(keepends=True),
                                          fromfile=("a/" + nome) if a else "/dev/null", tofile="b/" + nome))
(evidence / "m3-banda-morta.patch").write_text(patch, encoding="utf-8")

manifest = {"built_utc": datetime.now(timezone.utc).isoformat(), "log": str(log),
            "sources": {str(p): sha(p) for p in (cache_src, ctx_src, policy_src, test_src)},
            "compile_commands": {"llama-moecache.cpp": cache_cmd, "llama-context.cpp": ctx_cmd},
            "link_commands": {"llama.dll": link_llama},
            "reused_input_sha256": input_hashes, "unchanged_runtime_sha256": unchanged,
            "m2_sha256": {"llama.dll": sha(m2 / "runtime-m2" / "llama.dll")},
            "m3_sha256": {"llama.dll": sha(runtime / "llama.dll")},
            "note": "Oggetti e librerie O2 riusati in sola lettura, SHA verificato dopo la build; ggml-cuda.dll e' quella di M2."}
(evidence / "m3-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"runtime": str(runtime), "log": str(log), "riusati": len(inputs), "m3_sha256": manifest["m3_sha256"]}))
