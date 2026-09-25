"""Build a overlay del runtime Q36s: runtime Q36 (M2 + porto qwen35moe) + testa MTP condivisa, 25 settembre 2026.

Ricompila due oggetti di llama.dll coi flag O2 di Codex:
  - src/llama-context.cpp        (Q36 + ctx_other anche per la testa qwen35moe senza token_embd/output)
  - src/models/qwen35moe.cpp     (loader: token_embd/output_norm opzionali nei file solo-MTP;
                                  graph_mtp: embedding e LM head dal bersaglio se la testa non li ha)
e ricollega llama.dll dagli altri oggetti O2 in SOLA LETTURA (SHA prima e dopo); il resto del runtime e'
copiato da runtime-m2. Le teste MTP normali (con token_embd/output) e il tronco non cambiano percorso.
Laboratorio fuori da git: D:\\ds4_work\\elastico_q36s.
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

lab = Path(r"D:\ds4_work\elastico_q36s")
old = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920")
m2 = Path(r"D:\ds4_work\elastico_m2")
q36 = Path(r"D:\ds4_work\elastico_q36")
build, runtime, evidence, originali = lab / "build", lab / "runtime-q36s", lab / "evidence", lab / "originali"
overlay = lab / "source-overlay" / "src"
VCVARS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
NOWIN = subprocess.CREATE_NO_WINDOW

# (suffisso in compile_commands, sorgente O2, sorgente nostro, originale di riferimento per la patch)
FILES = [
    ("src/llama-context.cpp", old / "source" / "src" / "llama-context.cpp", overlay / "llama-context.cpp",
     originali / "llama-context.q36.cpp"),
    ("src/models/qwen35moe.cpp", old / "source" / "src" / "models" / "qwen35moe.cpp", overlay / "models" / "qwen35moe.cpp",
     originali / "qwen35moe.cpp"),
]


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


vivi = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"], capture_output=True, text=True).stdout
if "llama-server.exe" in vivi:
    sys.exit("ERRORE: c'e' un llama-server vivo: non compilo sopra un'inferenza.")
for folder in (build, runtime, evidence):
    folder.mkdir(exist_ok=True)

# basi dichiarate: contesto = quello di Q36, qwen35moe.cpp = O2 di Codex
assert sha(originali / "llama-context.q36.cpp") == sha(q36 / "source-overlay" / "src" / "llama-context.cpp")
assert sha(originali / "qwen35moe.cpp") == sha(old / "source" / "src" / "models" / "qwen35moe.cpp")

entries = json.loads((old / "build" / "compile_commands.json").read_text())
cmds, objs = {}, {}
for suffix, orig, mio, _ in FILES:
    obj = build / (Path(suffix).name + ".obj")
    cmd = next(i["command"] for i in entries if i["file"].replace("\\", "/").endswith(suffix))
    cmd, n1 = re.subn(r"/Fo\S+", lambda _: "/Fo" + str(obj).replace("\\", "/"), cmd)
    cmd, n2 = re.subn(r"/Fd\S+", lambda _: "/Fd" + str(build / "compile-llama.pdb").replace("\\", "/"), cmd)
    assert n1 == n2 == 1 and cmd.endswith(str(orig)), suffix
    # il file spostato cerca gli include "fra virgolette" prima nella SUA cartella: si aggiunge quella originale
    exe, resto = cmd.split(" ", 1)
    cmd = exe + " /I" + str(orig.parent) + " " + resto[:-len(str(orig))] + str(mio)
    cmds[suffix], objs[suffix] = cmd, obj

ninja = (old / "build" / "build.ninja").read_text().splitlines()
i = next(k for k, line in enumerate(ninja) if line.startswith("build bin\\llama.dll "))
names = ninja[i].split(": CXX_SHARED_LIBRARY_LINKER__llama_Release ", 1)[1].split(" | ")[0].split()
assert names and all(n.endswith(".obj") for n in names)
miei = {"\\llama-context.cpp.obj": objs["src/llama-context.cpp"],
        "\\models\\qwen35moe.cpp.obj": objs["src/models/qwen35moe.cpp"]}
objects = [next((mio for fine, mio in miei.items() if n.endswith(fine)), None) or old / "build" / n for n in names]
assert all(objects.count(mio) == 1 for mio in miei.values()), "oggetti da sostituire non trovati una volta sola"
libs_line = next(line for line in ninja[i + 1:i + 16] if line.startswith("  LINK_LIBRARIES = "))
libs = []
for token in libs_line.split(" = ", 1)[1].split():
    token = token.strip('"')
    libs.append(old / "build" / token if ("\\" in token and ":" not in token) else token)
inputs = [p for p in objects if p not in miei.values()] + [p for p in libs if isinstance(p, Path)]
assert all(p.is_file() for p in inputs), [str(p) for p in inputs if not p.is_file()]
input_hashes = {str(p): sha(p) for p in inputs}

for item in (m2 / "runtime-m2").iterdir():
    if item.suffix.lower() in (".dll", ".exe"):
        shutil.copy2(item, runtime / item.name)

env_script = build / "import-env.cmd"
env_script.write_text('@echo off\ncall "' + VCVARS + '" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding="ascii")
result = subprocess.run(["cmd.exe", "/d", "/c", str(env_script)], capture_output=True, text=True, check=True, creationflags=NOWIN)
env = dict(os.environ)
for line in result.stdout.splitlines():
    key, sep, value = line.partition("=")
    if sep and key:
        env[key] = value
env["TEMP"] = env["TMP"] = str(build)
compiler = Path(cmds["src/llama-context.cpp"].split()[0])
linker = compiler.with_name("link.exe")
rsp = build / "llama.rsp"
rsp.write_text("\n".join('"' + str(p) + '"' for p in [*objects, *libs]), encoding="utf-8")
link_llama = [str(linker), "/nologo", "@" + str(rsp), "/out:" + str(runtime / "llama.dll"),
              "/implib:" + str(build / "llama.lib"), "/pdb:" + str(build / "llama.pdb"),
              "/dll", "/version:0.3", "/machine:x64", "/INCREMENTAL:NO", "/MANIFEST:EMBED"]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log = evidence / f"build-q36s-{stamp}.log"
with log.open("w", encoding="utf-8") as output:
    passi = [("cl " + s, c) for s, c in cmds.items()] + [("link llama.dll", link_llama)]
    for titolo, comando in passi:
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
for suffix, _, mio, rif in FILES:
    prima = rif.read_text(encoding="utf-8").splitlines(keepends=True)
    dopo = mio.read_text(encoding="utf-8").splitlines(keepends=True)
    patch += "".join(difflib.unified_diff(prima, dopo, fromfile="a/" + suffix, tofile="b/" + suffix))
(evidence / "q36s-testa-condivisa.patch").write_text(patch, encoding="utf-8")

manifest = {"built_utc": datetime.now(timezone.utc).isoformat(), "log": str(log),
            "sources": {str(mio): sha(mio) for _, _, mio, _ in FILES},
            "compile_commands": cmds, "link_commands": {"llama.dll": link_llama},
            "reused_input_sha256": input_hashes, "unchanged_runtime_sha256": unchanged,
            "q36s_sha256": {"llama.dll": sha(runtime / "llama.dll")},
            "note": "Q36 + testa MTP condivisa; oggetti O2 in sola lettura; ggml-cuda.dll di M2. La patch e' relativa a Q36 (contesto) e O2 (qwen35moe.cpp)."}
(evidence / "q36s-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"runtime": str(runtime), "log": str(log), "riusati": len(inputs), "q36s_sha256": manifest["q36s_sha256"]}))
