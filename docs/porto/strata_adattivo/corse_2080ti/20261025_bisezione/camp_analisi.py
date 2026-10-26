"""Scomposizione del decode: token per finestra, ms per finestra, accettazione, dai soli engine.log.
  python camp_analisi.py storico <cartella banco_comunita>          -> T=0 contro T=0.7 (D e B, 4K e 32K)
  python camp_analisi.py corse   <cartella con camp_NN_<braccio>>   -> ogni braccio contro i suoi due base adiacenti
La richiesta 0 di ogni avvio (19 token, riscaldamento) e' scartata; con --senza-prima anche la prima da 4K
(ancora fredda: ms/finestra 36-58 contro 28-33 delle successive)."""
import glob, math, os, re, statistics as st, sys

WORK = re.compile(r"strata work: request (\d+), (\d+) windows, rows/window [^,]*, accepted (\d+) of (\d+) drafts, (\d+) tokens")
SERVE = re.compile(r"strata serve: prompt (\d+) tokens = \d+ reused \+ \d+ read in \d+ ms .*?, \d+ generated in (\d+) ms")


def load(d, skip_first=False):
    p = os.path.join(d, "engine.log")
    if not os.path.exists(p):
        return [], False
    text = open(p, encoding="utf-8", errors="replace").read()
    serial = "decodes serially" in text   # la riga che il motore scrive quando la pipeline a due finestre e' spenta
    rows, w, n = [], None, 0
    for line in text.splitlines():
        m = WORK.search(line)
        if m:
            w = m
            continue
        m = SERVE.search(line)
        if m and w:
            n += 1
            ptok, ms = int(m.group(1)), int(m.group(2))
            if n > 1 and ptok > 100 and not (skip_first and n == 2):
                win, a, b, t = int(w.group(2)), int(w.group(3)), int(w.group(4)), int(w.group(5))
                rows.append(dict(ctx=ptok, W=win, A=a, B=b, T=t, ms=ms, tpw=t / win, mspw=ms / win,
                                 acc=a / b, tps=t / ms * 1000))
            w = None
    return rows, serial


def med(rows, k):
    return st.median(r[k] for r in rows) if rows else float("nan")


def line(rows):
    return (f"n {len(rows):2d}  tok/fin {med(rows, 'tpw'):.3f}  ms/fin {med(rows, 'mspw'):.2f}  "
            f"accett {med(rows, 'acc'):.3f}  t/s {med(rows, 'tps'):.1f}")


def storico(base, skip_first):
    arms = {}
    for d in sorted(glob.glob(os.path.join(base, "samp*")) + glob.glob(os.path.join(base, "s7r_*"))):
        b = os.path.basename(d)
        eng = "B" if b in ("samp0_B", "samp7_B") or b.startswith("s7r_B") else "D"
        temp = "0" if b.startswith("samp0") else "0.7"
        rows, serial = load(d, skip_first)
        arms.setdefault((eng, temp), []).extend(rows)
        print(f"{b:14s} serial={'si' if serial else 'no'}  {line(rows)}")
    print()
    for ctx in (4096, 32768):
        for eng in ("D", "B"):
            a = [r for r in arms[(eng, "0")] if r["ctx"] == ctx]
            b = [r for r in arms[(eng, "0.7")] if r["ctx"] == ctx]
            lt = math.log(med(b, "tpw") / med(a, "tpw"))
            lm = -math.log(med(b, "mspw") / med(a, "mspw"))
            print(f"{ctx // 1024:2d}K {eng}  T0 : {line(a)}\n       T.7: {line(b)}\n"
                  f"       t/s {100 * (med(b, 'tps') / med(a, 'tps') - 1):+.1f}% = "
                  f"token/finestra {100 * lt:+.1f} pt, ms/finestra {100 * lm:+.1f} pt")


def corse(base, skip_first):
    runs = []
    for d in sorted(glob.glob(os.path.join(base, "camp_*_*"))):
        m = re.match(r"camp_(\d+)_(.+)$", os.path.basename(d))
        if m:
            rows, serial = load(d, skip_first)
            runs.append((int(m.group(1)), m.group(2), rows, serial))
    for n, arm, rows, serial in runs:
        print(f"{n:02d} {arm:8s} serial={'si' if serial else 'no'}  {line(rows)}")
        if arm != "base":
            nb = [r for (k, a, r, s) in runs if a == "base" and abs(k - n) == 1]
            if len(nb) == 2:
                ref = nb[0] + nb[1]
                print(f"     contro i due base adiacenti: t/s {100 * (med(rows, 'tps') / med(ref, 'tps') - 1):+.1f}%  "
                      f"tok/fin {100 * (med(rows, 'tpw') / med(ref, 'tpw') - 1):+.1f}%  "
                      f"ms/fin {100 * (med(rows, 'mspw') / med(ref, 'mspw') - 1):+.1f}%")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--senza-prima"]
    skip = "--senza-prima" in sys.argv
    if len(args) != 2 or args[0] not in ("storico", "corse"):
        raise SystemExit(__doc__)
    (storico if args[0] == "storico" else corse)(args[1], skip)
