"""Profilo Nsight Systems di strata.exe lanciato direttamente (riga di comando, niente server), 30/9/2026.

nsys non segue strata.exe quando e' figlio del server Python: qui il motore parte da solo, con gli argomenti della
configurazione del confronto equo (build-0129, riserva 1393; l'elastica e' solo del --serve), il prompt L01 del banco
tokenizzato col tokenizzatore di Strata (serve/strata_tokenizer) nel modello di chat, e --max-new 1500. La cattura
(--cuda-graph-trace=node: i kernel dentro il grafo della finestra) parte dopo --ritardo secondi e dura --durata; il motore
non viene chiuso a fine cattura (--kill=false). Poi `nsys stats` riassume i kernel per tempo GPU totale.
Uso:  python prova_nsys_cli.py [--ritardo 75] [--durata 10]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

S = Path(r"D:\ds4_work\strata\Strata")
sys.path.insert(0, str(S / "tools"))   # strata_tokenizer.py (il server lo importa da li')
sys.path.insert(0, r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_prova")
import strata_tokenizer as ST  # noqa: E402
import banco_strata as B  # noqa: E402

NSYS = r"C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe"
OUT = Path(r"D:\ds4_work\strata\nsys")


def opz(nome, predefinito):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else predefinito


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((S / "strata-iq3_xxs-r1032.json").read_text(encoding="utf-8-sig"))
    tpath = Path(cfg["tokenizer"])
    vocab = json.loads((tpath / "vocab.json").read_text(encoding="utf-8"))
    tokens = [None] * len(vocab)
    for t, i in vocab.items():
        tokens[i] = t
    tok = ST.Tokenizer(tokens, (tpath / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((tpath / "token_type.json").read_text()))
    testo = B.P0.carica_fixture()[3]["L01"]   # lo stesso testo del caso L01 del banco
    prompt = "<|im_start|>user\n" + testo + "<|im_end|>\n<|im_start|>assistant\n"
    ids = tok.encode(prompt, parse_special=True)
    args = list(cfg["args"])
    args[args.index("--vram-reserve-mib") + 1] = "1393"
    exe = str(S / "build-0129" / "strata.exe")
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(cfg.get("lib_dirs", [])) + os.pathsep + env.get("PATH", "")
    rep = OUT / "strata_2080ti_cli"
    cmd = [NSYS, "profile", "--trace=cuda", "--cuda-graph-trace=node", "--sample=none", "--cpuctxsw=none",
           "--delay", opz("--ritardo", "75"), "--duration", opz("--durata", "10"), "--kill=false",
           "--force-overwrite", "true", "-o", str(rep), exe] + args + [
           "--tokens", ",".join(str(i) for i in ids), "--max-new", "1500"]
    print("prompt di", len(ids), "token; lancio", time.strftime("%H:%M:%S"), flush=True)
    r = subprocess.run(cmd, cwd=str(S), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "strata_cli.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    righe = [l for l in (r.stdout + r.stderr).splitlines() if "tok/s" in l or "error" in l.lower()]
    print("\n".join(righe[-8:]), flush=True)
    s = subprocess.run([NSYS, "stats", "--report", "cuda_gpu_kern_sum", "--format", "csv", "--force-export", "true",
                        "-o", str(OUT / "kernel_cli"), str(rep) + ".nsys-rep"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(s.stdout[-1500:], s.stderr[-1500:], flush=True)
    print("FINE", time.strftime("%H:%M:%S"), flush=True)


if __name__ == "__main__":
    main()
