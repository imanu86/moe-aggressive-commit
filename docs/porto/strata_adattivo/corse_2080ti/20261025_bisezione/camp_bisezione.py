"""Bisezione del costo del campionamento a T=0.7 (B-A-B): UN parametro per volta, ogni variante tra due base.
NON parte da sola: senza --vai stampa soltanto la sequenza. Usa la GPU per ~5 min a corsa: lanciare a PC libero.

  python camp_bisezione.py                      # prova a secco: elenca le corse
  python camp_bisezione.py --vai                # sequenza completa (10 avvii, ~50 min)
  python camp_bisezione.py --vai --solo nopp    # una sola terna base-nopp-base (3 avvii, ~15 min)
  python camp_bisezione.py --vai --motore D     # stesso con la Daily 0.1.43 invece della 0.2.6 + pila

Bracci (il corpo della richiesta porta SOLO questi campi; un campo a 0 / 1.0 e' esplicito e batte la scheda del modello,
che altrimenti rimetterebbe 0.8 / 20 / 1.5 su ogni richiesta con temperatura > 0):
  base    T=0.7 top_p 0.8 top_k 20 presence 1.5     (come in uso reale)
  nopp    come base, presence_penalty 0             -> hist_n = 0: la pipeline a due finestre resta accesa
  notopp  come base, top_p 1.0                      -> il taglio per massa non c'e' piu'
  topk64  come base, top_k 64                       -> 64 giri di argmax invece di 20 (il kernel non ha "off")
  puro    T=0.7, top_p 1.0, top_k 20, presence 0    -> solo temperatura (top_k 20 e' il minimo del motore sul percorso campionato)
  t0      temperature 0                             -> riferimento greedy
Esito atteso se il sospetto regge: nopp e puro recuperano quasi tutto il divario (e il log NON ha la riga "decodes serially");
notopp e topk64 restano a livello di base."""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
LOCKS = Path(r"D:\ds4_work\strata\lab_locks")
RUNNER = HERE / "community_bench_camp.py"

SAMPLING = {
    "base":   {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
    "nopp":   {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 0},
    "notopp": {"temperature": 0.7, "top_p": 1.0, "top_k": 20, "presence_penalty": 1.5},
    "topk64": {"temperature": 0.7, "top_p": 0.8, "top_k": 64, "presence_penalty": 1.5},
    "puro":   {"temperature": 0.7, "top_p": 1.0, "top_k": 20, "presence_penalty": 0},
    "t0":     {"temperature": 0},
}
MOTORI = {
    "B": (str(CORSE / "20261019_banco_comunita" / "up026p-B-pila" / "config.json"),
          str(CORSE / "20261004_routed_keep" / "build-up026pila-ffe66174")),
    "D": (r"D:\ds4_work\strata\Strata\strata-0143-daily.json", r"D:\ds4_work\strata\Strata\build-0143-daily"),
}
SEQUENZA = ["base", "nopp", "base", "notopp", "base", "topk64", "base", "puro", "base", "t0"]


def pc_libero():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq strata.exe"], capture_output=True, text=True).stdout
    problemi = []
    if "strata.exe" in out.lower():
        problemi.append("un strata.exe e' in corsa (il runner lo ucciderebbe a fine corsa)")
    for nome in ("pause", "bench.lock"):
        if (LOCKS / nome).exists():
            problemi.append(f"{LOCKS / nome} esiste")
    return problemi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vai", action="store_true", help="lancia davvero (usa la GPU)")
    ap.add_argument("--solo", choices=[k for k in SAMPLING if k not in ("base",)], help="una terna base-X-base")
    ap.add_argument("--motore", choices=sorted(MOTORI), default="B")
    ap.add_argument("--corse", type=int, default=4, help="richieste per contesto (4K e 32K); la prima da 4K e' fredda")
    a = ap.parse_args()
    seq = ["base", a.solo, "base"] if a.solo else SEQUENZA
    cfg, build = MOTORI[a.motore]
    print(f"motore {a.motore}: config {cfg}\n  build {build}\nuscita {HERE}\\camp_NN_<braccio>\n")
    for i, arm in enumerate(seq, 1):
        print(f"{i:02d} {arm:7s} {json.dumps(SAMPLING[arm])}")
    if not a.vai:
        print("\n(prova a secco: niente lanciato)")
        return
    problemi = pc_libero()
    if problemi:
        raise SystemExit("PC non libero: " + "; ".join(problemi))
    for i, arm in enumerate(seq, 1):
        tag = f"camp_{i:02d}_{arm}"
        env = dict(os.environ, CAMP_SAMPLING=json.dumps(SAMPLING[arm]), CAMP_RUNS=str(a.corse), CAMP_OUT=str(HERE))
        print(f"[{time.strftime('%H:%M:%S')}] {tag}", flush=True)
        r = subprocess.run([sys.executable, str(RUNNER), tag, cfg, build], env=env)
        log = HERE / tag / "engine.log"
        seriale = log.exists() and "decodes serially" in log.read_text(encoding="utf-8", errors="replace")
        print(f"[{time.strftime('%H:%M:%S')}] {tag} uscita {r.returncode}; pipeline spenta dalla penalita': {'SI' if seriale else 'no'}", flush=True)
        if r.returncode != 0:
            raise SystemExit(f"{tag} fallita: sequenza interrotta")
    print("fatto. Analisi: python camp_analisi.py corse", HERE)


if __name__ == "__main__":
    main()
