"""pilot_local.py - il pilota locale della distillazione MTP, in sequenza e sotto un solo bench.lock (lab_run.py):

    python lab_run.py --name mtp-pilot --max-min 180 -- python pilot_local.py --work D:\\ds4_work\\mtp_distill --count 300 [--from STAGE]

Tappe (ognuna salta se gia' fatta, --from STAGE riparte da li'):
  capture   le prime --count sequenze dell'indice (train + le heldout per conversazione che vi cadono) e TUTTE le heldout per
            conversazione (--by-conv) dell'intero indice, dal prefill del motore (capture_driver.py) -> <work>/capture_pilot
  eval      diagnosi D: eval del drafter attuale sulla heldout con gli esperti Q2_0 del pacco e con quelli BF16 del checkpoint
            (train_mtp.py --eval-only) -> <work>/runs/pilot_eval_{q2,bf16}/eval.json
  train     1 epoca sulle sequenze catturate (train_mtp.py) -> <work>/runs/pilot_ft1 (eval prima, ogni --eval-every passi, alla fine)
  export    il pacco del motore (export_mtp.py) -> <work>/runs/pilot_ft1/rt_pilot (verifica d'identita' del percorso compresa)
Stampa alla fine la tabella del cancello: accettazione per passo prima/dopo (greedy e campionata), costo di Q2_0, tempi.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGES = ["capture", "eval", "train", "export"]


def run(cmd: list[str], log: Path) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            f.write(line)
            f.flush()
            sys.stdout.write(line)
            sys.stdout.flush()
        return p.wait()


def fmt_eval(ev: dict) -> str:
    cols = []
    for j, s in enumerate(ev["steps"]):
        samp = " ".join(f"{k}={v:.3f}" for k, v in s.get("sampled", {}).items())
        cols.append(f"  passo {j}: n={s['n']} kl={s['kl']:.3f} greedy acc={s['acc']:.3f} offerte={s['offered']:.3f} acc&off={s['acc_offered']:.3f} {samp}")
    cols.append(f"  catena greedy media {ev['chain_len_mean']:.3f} su {ev['chain_cells']} celle; {ev.get('tokens', 0)} token in {ev.get('seconds', 0)} s")
    return "\n".join(cols)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=r"D:\ds4_work\mtp_distill")
    ap.add_argument("--exe", default=r"C:\Users\imanu\source\repos\Strata-wt\mtp-capture\build-mtpcap\strata.exe")
    ap.add_argument("--config", default=r"D:\ds4_work\strata\Strata\strata-dueschede.json")
    ap.add_argument("--driver-env", action="append", default=["STRATA_VRAM_FREE=device"], help="KEY=VAL per il motore della cattura")
    ap.add_argument("--bf16", default=r"D:\ds4_work\strata\Strata-data\mtp")
    ap.add_argument("--rt", default=r"D:\ds4_work\strata\Strata-data\mtp\rt_it48k")
    ap.add_argument("--gguf", default=r"C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf")
    ap.add_argument("--strata", default=r"C:\Users\imanu\source\repos\Strata-wt\mtp-capture")
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--by-conv", type=int, default=10)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--eval-every", type=int, default=20)
    ap.add_argument("--eval-items", type=int, default=120)
    ap.add_argument("--train-extra", default="", help="altri argomenti per train_mtp.py (es. --nll-weight --step-weights 1,0.8,0.6,0.5)")
    ap.add_argument("--from", dest="from_stage", default="capture", choices=STAGES)
    ap.add_argument("--only", default="", help="solo questa tappa")
    ap.add_argument("--tag", default="pilot")
    a = ap.parse_args()
    work = Path(a.work)
    cap = work / f"capture_{a.tag}"
    runs = work / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    log = work / "work" / f"{a.tag}_local.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    common = ["--bf16", a.bf16, "--rt", a.rt, "--gguf", a.gguf, "--strata", a.strata, "--seqs", str(work / "seqs"),
              "--capture", str(cap), "--cache", str(work / "work" / "cache"), "--steps", str(a.steps),
              "--split-by-conv", str(a.by_conv), "--eval-items", str(a.eval_items)]
    todo = [a.only] if a.only else STAGES[STAGES.index(a.from_stage):]
    times = {}
    t_all = time.time()
    for stage in todo:
        t0 = time.time()
        print(f"\n===== {stage} =====", flush=True)
        if stage == "capture":
            drv = [py, str(HERE / "capture_driver.py"), "--exe", a.exe, "--config", a.config, "--seqs", str(work / "seqs"), "--out", str(cap)]
            for kv in a.driver_env:
                drv += ["--env", kv]
            if run(drv + ["--count", str(a.count)], log) != 0:
                return 1
            if run(drv + ["--split", "heldout", "--by-conv", str(a.by_conv)], log) != 0:
                return 1
        elif stage == "eval":
            for experts in ("q2", "bf16"):
                out = runs / f"{a.tag}_eval_{experts}"
                if (out / "eval.json").exists():
                    print(f"  {out} gia' fatto", flush=True)
                    continue
                if run([py, str(HERE / "train_mtp.py"), *common, "--out", str(out), "--eval-only", "--experts", experts], log) != 0:
                    return 1
        elif stage == "train":
            out = runs / f"{a.tag}_ft1"
            cmd = [py, str(HERE / "train_mtp.py"), *common, "--out", str(out), "--epochs", str(a.epochs), "--lr", str(a.lr),
                   "--accum", str(a.accum), "--eval-every", str(a.eval_every)] + a.train_extra.split()
            if run(cmd, log) != 0:
                return 1
        elif stage == "export":
            out = runs / f"{a.tag}_ft1"
            if run([py, str(HERE / "export_mtp.py"), "--bf16", a.bf16, "--rt", a.rt, "--weights", str(out / "trainable.safetensors"),
                    "--out", str(out / "rt_pilot")], log) != 0:
                return 1
            if run([py, str(HERE / "export_mtp.py"), "--bf16", a.bf16, "--rt", a.rt, "--out", str(work / "work" / "rt_identity_check"),
                    "--check-against", a.rt], log) != 0:
                return 1
        times[stage] = round((time.time() - t0) / 60, 1)
        print(f"===== {stage}: {times[stage]} min =====", flush=True)
    # la tabella del cancello
    print("\n===== RIEPILOGO =====")
    print("tempi (min):", json.dumps(times), f"totale {(time.time() - t_all) / 60:.1f}")
    for name in (f"{a.tag}_eval_q2", f"{a.tag}_eval_bf16"):
        p = runs / name / "eval.json"
        if p.exists():
            ev = json.loads(p.read_text())["step_0"]
            print(f"drafter attuale, esperti {name.split('_')[-1]}:\n{fmt_eval(ev)}")
    p = runs / f"{a.tag}_ft1" / "eval.json"
    if p.exists():
        evs = json.loads(p.read_text())
        for key in [k for k in evs if k != "config"]:
            print(f"training {key}:\n{fmt_eval(evs[key])}")
        if "step_0" in evs and "final" in evs:
            d = [(f["acc_offered"] - s["acc_offered"]) * 100 for s, f in zip(evs["step_0"]["steps"], evs["final"]["steps"])]
            print("delta acc&offerte per passo (punti):", " ".join(f"{x:+.1f}" for x in d))
            print("CANCELLO +2 al passo 0:", "PASSATO" if d and d[0] >= 2.0 else "NON passato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
