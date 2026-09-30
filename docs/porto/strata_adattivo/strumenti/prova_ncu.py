"""Nsight Compute sui kernel degli esperti di Strata (2080 Ti), 30/9/2026.

strata.exe da riga di comando (come prova_nsys_cli.py: stessi argomenti, prompt L01, --ple-io mmap), sotto ncu: dopo
--salta esecuzioni ne profila --quante dei kernel che fanno gli esperti (native_gu / native_down / gr_up_multi /
gr_down_multi) con le sezioni SpeedOfLight, MemoryWorkloadAnalysis, Occupancy, WarpStateStats, LaunchStats. Poi stampa
per ciascuno: durata, banda DRAM ottenuta, throughput di memoria e di SM, occupazione, griglia.
Uso:  python prova_ncu.py [--salta 400] [--quante 8]
"""
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

S = Path(r"D:\ds4_work\strata\Strata")
sys.path.insert(0, str(S / "tools"))
sys.path.insert(0, r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_prova")
import strata_tokenizer as ST  # noqa: E402
import banco_strata as B  # noqa: E402

# l'eseguibile, non ncu.bat: cmd leggerebbe il `|` del filtro sui kernel come una pipe
NCU = r"C:\Program Files\NVIDIA Corporation\Nsight Compute 2024.3.2\target\windows-desktop-win7-x64\ncu.exe"
OUT = Path(r"D:\ds4_work\strata\ncu")
METRICHE = ["Duration", "DRAM Throughput", "Memory Throughput", "Compute (SM) Throughput", "Achieved Occupancy",
            "Theoretical Occupancy", "Registers Per Thread", "Grid Size", "Block Size", "L2 Hit Rate", "L1/TEX Hit Rate"]


def opz(nome, predefinito):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else predefinito


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((S / "strata-iq3_xxs-r1032.json").read_text(encoding="utf-8-sig"))
    tp = Path(cfg["tokenizer"])
    vocab = json.loads((tp / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, (tp / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((tp / "token_type.json").read_text()))
    testo = B.P0.carica_fixture()[3]["L01"]
    ids = tok.encode("<|im_start|>user\n" + testo + "<|im_end|>\n<|im_start|>assistant\n", parse_special=True)
    args = list(cfg["args"])
    args[args.index("--vram-reserve-mib") + 1] = "1393"
    args += ["--ple-io", "mmap"]
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(cfg.get("lib_dirs", [])) + os.pathsep + env.get("PATH", "")
    rep = OUT / "esperti"
    cmd = [NCU, "--kernel-name", "regex:native_gu_kernel|native_down_kernel|gr_up_multi_kernel|gr_down_multi_kernel",
           "--launch-skip", opz("--salta", "400"), "--launch-count", opz("--quante", "8"),
           # 30/9: con le sezioni complete ncu ripete ogni kernel molte volte salvando e ripristinando la memoria che
           # potrebbe toccare (qui anche l'arena da 40 GB mappata): oltre un'ora senza arrivare in fondo. Poche metriche,
           # una passata sola, niente svuotamento delle cache fra le passate
           "--metrics", "gpu__time_duration.sum,dram__throughput.avg.pct_of_peak_sustained_elapsed,"
                        "dram__bytes.sum,sm__throughput.avg.pct_of_peak_sustained_elapsed,"
                        "sm__warps_active.avg.pct_of_peak_sustained_active,launch__grid_size,launch__block_size,"
                        "launch__registers_per_thread",
           "--cache-control", "none", "--clock-control", "none", "--force-overwrite", "-o", str(rep),
           str(S / "build-0129" / "strata.exe")] + args + ["--tokens", ",".join(map(str, ids)), "--max-new", "96"]
    r = subprocess.run(cmd, cwd=str(S), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "ncu_run.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    err = [l for l in (r.stdout + r.stderr).splitlines() if "ERR" in l or "==ERROR==" in l or "==WARNING==" in l]
    print("\n".join(err[-8:]), flush=True)
    if not (OUT / "esperti.ncu-rep").exists():
        print("nessun rapporto: vedi", OUT / "ncu_run.log")
        return 1
    e = subprocess.run([NCU, "--import", str(rep) + ".ncu-rep", "--page", "details", "--csv"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    righe = list(csv.DictReader(io.StringIO(e.stdout)))
    per_k = {}
    for row in righe:
        k = (row.get("ID"), row.get("Kernel Name", "")[:60])
        if row.get("Metric Name") in METRICHE:
            per_k.setdefault(k, {})[row["Metric Name"]] = row.get("Metric Value", "") + " " + row.get("Metric Unit", "")
    for (kid, nome), m in per_k.items():
        print("#%s %s" % (kid, nome))
        print("   " + "; ".join("%s %s" % (x, m[x].strip()) for x in METRICHE if x in m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
