"""Prova riproducibile del difetto «canary del prefill» del runtime elastico M1 (21 settembre 2026).

Difetto: quando la politica RAM del deposito esperti (moe-ram-store.cuh) sfratta anche una sola terna,
`llama_context::decode` rifiuta OGNI batch con piu' di 3 token (`RAM decode canary rejects new prefill
while expert pages are absent`, ret = -3, il client riceve 500 «Compute error»). Le pagine tornano solo
dentro il decode, quindi un server che ha sfrattato non accetta piu' nessun prompt.

Sequenza della prova (server ISOLATO su 127.0.0.1:8113, mai la produzione sulla 8100):
  0. avvio come `docs/porto/qwen_gateway/server_locale.py` (reference_gsq_64.json + env elastiche);
  1. controllo: prompt corto e prompt lungo in chat, due volte ciascuno (l'oracolo greedy deve ripetersi);
  2. pressione: durante un decode in streaming un processo di servizio alloca e blocca RAM finche' il
     disponibile scende sotto `--target-mib` (predefinito 1536, cioe' sotto il pavimento di 2 GiB); si
     aspetta che RAM_STORE riporti sfratti, poi la RAM viene rilasciata;
  3. dopo lo sfratto: gli stessi due prompt in chat (`/v1/chat/completions`, mai `/completion` grezzo).

Verdetto: SUPERATA = 200 e testo identico al controllo; DIFETTO RIPRODOTTO = 500 col canary nel log;
INCONCLUSIVA = nessuno sfratto ottenuto. Se lo sfratto avviene gia' nel warmup (RAM scarsa all'avvio)
il difetto compare al controllo e la fase di pressione viene saltata.

Uso, STACCATO dalla shell di Claude (vedi LEGGIMI.md):  python prova_canary_prefill.py --run
Senza --run stampa solo il piano. `--runtime` prova un altro llama-server.exe (i binari corretti).
Esito in D:\\ds4_work\\elastico_m1_canary_run\\<data_ora>_<etichetta>\\: STATO.txt, rapporto.json, runner.log, logs\\.
"""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

OUT = Path(r"D:\ds4_work\elastico_m1_canary_run")
CANARY = "RAM decode canary rejects new prefill"
MIB = 1024 * 1024

CORTO = "Rispondi con una sola frase: qual e' la capitale d'Italia e su quale fiume sorge?"
# oltre 512 token in un solo ubatch: e' la soglia dello staging a tensore intero (qwen_prefetch_eval)
LUNGO = ("Qui sotto c'e' un registro. Dimmi in una frase quale riga ha il valore piu' alto.\n"
         + "\n".join(f"Riga {i}: il registro {i} contiene il valore {(i * 37) % 1000}." for i in range(1, 161)))
CARICO = "Scrivi in lettere i numeri da 1 a 300, uno per riga, senza commenti."


class MEMORYSTATUSEX(C.Structure):
    _fields_ = [("dwLength", C.c_uint32), ("dwMemoryLoad", C.c_uint32)] + [
        (n, C.c_uint64) for n in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                                  "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]


def memoria() -> MEMORYSTATUSEX:
    m = MEMORYSTATUSEX()
    m.dwLength = C.sizeof(m)
    assert C.windll.kernel32.GlobalMemoryStatusEx(C.byref(m)), "GlobalMemoryStatusEx"
    return m


def disponibile_mib() -> int:
    return memoria().ullAvailPhys // MIB


# ---------------------------------------------------------------------------------------------------
# Processo di servizio: alloca, tocca e BLOCCA (VirtualLock) RAM finche' il disponibile scende al target,
# e continua a riempire quando gli sfratti del server ne liberano. Rilascia tutto se compare il file di
# rilascio, se il genitore muore o allo scadere di --max-secondi: la macchina non resta mai sotto pressione.
def pressione(args) -> int:
    K = C.WinDLL("kernel32", use_last_error=True)
    K.VirtualAlloc.restype = C.c_void_p
    K.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
    K.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
    K.VirtualLock.argtypes = [C.c_void_p, C.c_size_t]
    K.OpenProcess.restype = C.c_void_p
    K.WaitForSingleObject.argtypes = [C.c_void_p, C.c_uint32]
    K.GetCurrentProcess.restype = C.c_void_p
    K.SetProcessWorkingSetSize.argtypes = [C.c_void_p, C.c_size_t, C.c_size_t]
    genitore = K.OpenProcess(0x100000, 0, args.pressione)  # SYNCHRONIZE
    blocchi: list[tuple[int, int, bool]] = []
    totale, t0, ritocco, motivo = 0, time.monotonic(), time.monotonic(), "rilascio"
    registro = Path(args.registro).open("w", encoding="utf-8")

    def scrivi(evento: str, **dati) -> None:
        registro.write(json.dumps({"t": round(time.monotonic() - t0, 2), "evento": evento,
                                   "disponibile_mib": disponibile_mib(), "allocato_mib": totale // MIB, **dati}) + "\n")
        registro.flush()

    scrivi("avvio", target_mib=args.target_mib, max_mib=args.max_mib)
    try:
        while True:
            if Path(args.rilascio).exists():
                break
            if genitore and K.WaitForSingleObject(genitore, 0) == 0:
                motivo = "genitore uscito"
                break
            if time.monotonic() - t0 > args.max_secondi:
                motivo = "scadenza"
                break
            margine = disponibile_mib() - args.target_mib
            if margine > 32 and totale < args.max_mib * MIB:
                passo = min(256, margine, args.max_mib - totale // MIB) * MIB
                K.SetProcessWorkingSetSize(K.GetCurrentProcess(), totale + passo + 64 * MIB, totale + passo + 320 * MIB)
                ptr = K.VirtualAlloc(None, passo, 0x3000, 4)  # MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
                if not ptr:
                    scrivi("VirtualAlloc fallita", errore=C.get_last_error())
                    time.sleep(0.5)
                    continue
                C.memset(ptr, 0xA5, passo)
                bloccato = bool(K.VirtualLock(ptr, passo))
                blocchi.append((ptr, passo, bloccato))
                totale += passo
                scrivi("allocato", passo_mib=passo // MIB, bloccato=bloccato)
                continue
            if time.monotonic() - ritocco > 1.0:  # i blocchi non bloccati vanno tenuti nel working set
                for ptr, passo, bloccato in blocchi:
                    if not bloccato:
                        C.memset(ptr, 0x5A, passo)
                ritocco = time.monotonic()
                scrivi("tenuta")
            time.sleep(0.1)
    finally:
        for ptr, _, _ in blocchi:
            K.VirtualFree(ptr, 0, 0x8000)  # MEM_RELEASE
        totale = 0
        scrivi("rilasciato", motivo=motivo)
    return 0


# ---------------------------------------------------------------------------------------------------
def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stato_deposito(stderr_path: Path) -> dict:
    """Ultima riga RAM_STORE del server (contatori cumulativi) + quante volte ha parlato il canary."""
    testo = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    righe = re.findall(r"^RAM_STORE (\{.*\})\s*$", testo, flags=re.M)
    ultimo = json.loads(righe[-1]) if righe else {}
    return {"missing": ultimo.get("missing"), "evictions": ultimo.get("evictions"), "restores": ultimo.get("restores"),
            "emergency": ultimo.get("emergency"), "avail_mib": (ultimo.get("avail") or 0) // MIB,
            "resident_mib": (ultimo.get("resident") or 0) // MIB, "righe": len(righe), "canary": testo.count(CANARY)}


def chat(base: str, key: str, prompt: str, max_tokens: int, su_delta=None) -> dict:
    """Una richiesta a /v1/chat/completions. Greedy e senza cache del prompt: il prefill si rifa' per intero."""
    corpo = {"model": "qwen", "messages": [{"role": "user", "content": prompt}], "temperature": 0, "seed": 1234,
             "max_tokens": max_tokens, "cache_prompt": False, "stream": su_delta is not None}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8",
                                          "Authorization": "Bearer " + key})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            if su_delta is None:
                dati = json.loads(r.read())
                msg = dati["choices"][0]["message"]
                testo = (msg.get("reasoning_content") or "") + "\x00" + (msg.get("content") or "")
                return {"status": r.status, "secondi": round(time.perf_counter() - t0, 2),
                        "impronta": hashlib.sha256(testo.encode("utf-8")).hexdigest()[:12],
                        "testo": (msg.get("content") or "")[:200], "timings": dati.get("timings"), "usage": dati.get("usage")}
            n = 0
            for riga in r:
                if not riga.startswith(b"data: ") or riga.strip() == b"data: [DONE]":
                    continue
                scelte = json.loads(riga[6:]).get("choices") or [{}]
                delta = scelte[0].get("delta") or {}
                if delta.get("content") or delta.get("reasoning_content"):
                    n += 1
                    su_delta(n)
            return {"status": r.status, "secondi": round(time.perf_counter() - t0, 2), "delta": n}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "secondi": round(time.perf_counter() - t0, 2),
                "errore": e.read().decode("utf-8", "replace")[:400]}
    except Exception as e:  # server caduto, timeout: e' un esito, non un'eccezione della prova
        return {"status": None, "secondi": round(time.perf_counter() - t0, 2), "errore": f"{type(e).__name__}: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--braccio", default="m1", help="braccio di banco_followup.BRACCI (predefinito m1)")
    ap.add_argument("--runtime", default=None, help="altro llama-server.exe da provare (stessa configurazione di m1)")
    ap.add_argument("--etichetta", default="")
    ap.add_argument("--target-mib", type=int, default=1536, help="RAM disponibile a cui portare la macchina")
    ap.add_argument("--max-mib", type=int, default=24576, help="tetto di RAM che il processo di servizio puo' allocare")
    ap.add_argument("--max-secondi", type=int, default=150, help="scadenza dura della pressione")
    ap.add_argument("--max-tokens-carico", type=int, default=768, help="token del decode tenuto sotto pressione")
    ap.add_argument("--senza-pressione", action="store_true", help="solo controllo: serve per il caso «sfratto nel warmup»")
    # modo processo di servizio (non si usa a mano)
    ap.add_argument("--pressione", type=int, default=None, metavar="PID_GENITORE")
    ap.add_argument("--rilascio", default=None)
    ap.add_argument("--registro", default=None)
    args = ap.parse_args()
    if args.pressione is not None:
        return pressione(args)
    if not args.run:
        print(__doc__)
        print(f"A secco: nessun server avviato. RAM disponibile ora: {disponibile_mib()} MiB. Usa --run.")
        return 0

    qui = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("server_locale", qui.parent / "qwen_gateway" / "server_locale.py")
    server_locale = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_locale)
    B = server_locale.B
    braccio = args.braccio
    if args.runtime:
        config, _, extra_env, slots = B.BRACCI["m1"]
        B.BRACCI["prova"] = (config, Path(args.runtime), extra_env, slots)
        braccio = "prova"
    assert braccio in B.BRACCI, f"braccio sconosciuto: {braccio}"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + (args.etichetta or braccio)
    run = OUT / stamp
    run.mkdir(parents=True, exist_ok=False)
    runner_log = (run / "runner.log").open("w", encoding="utf-8")

    def log(msg: str) -> None:
        runner_log.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        runner_log.flush()

    def stato(msg: str) -> None:
        (run / "STATO.txt").write_text(msg + "\n", encoding="utf-8")
        log("STATO " + msg)

    rapporto: dict = {"corsa": stamp, "argomenti": vars(args), "fasi": {}}
    stderr_path = run / "logs" / "server.stderr.txt"
    verdetto, errore = "INCONCLUSIVA", None
    try:
        stato("preflight")
        esegui = Path(B.BRACCI[braccio][1] or "")
        rapporto["runtime"] = {"exe": str(esegui), **{n: sha_file(esegui.parent / n)[:16] for n in ("llama.dll", "ggml-cuda.dll")
                                                         if (esegui.parent / n).is_file()}}
        m = memoria()
        rapporto["preflight"] = {"disponibile_mib": m.ullAvailPhys // MIB, "totale_mib": m.ullTotalPhys // MIB,
                                 "commit_libero_mib": m.ullAvailPageFile // MIB}
        log(f"preflight {rapporto['preflight']} runtime {rapporto['runtime']}")

        stato("avvio del server")
        with server_locale.server(braccio, run, log) as (base, key):
            def fase(nome: str, prompt: str, max_tokens: int = 48) -> dict:
                prima = stato_deposito(stderr_path)
                esito = chat(base, key, prompt, max_tokens)
                dopo = stato_deposito(stderr_path)
                esito.update({"missing_prima": prima["missing"], "missing_dopo": dopo["missing"],
                              "restores": dopo["restores"], "canary": dopo["canary"] - prima["canary"],
                              "disponibile_mib": disponibile_mib()})
                rapporto["fasi"][nome] = esito
                log(f"{nome}: {json.dumps({k: v for k, v in esito.items() if k not in ('timings', 'usage', 'testo')})}")
                return esito

            rapporto["a_server_pronto"] = {**stato_deposito(stderr_path), "disponibile_mib": disponibile_mib()}
            log(f"a server pronto: {rapporto['a_server_pronto']}")

            stato("fase 1: controllo")
            controllo = [fase("controllo_corto_1", CORTO), fase("controllo_lungo_1", LUNGO),
                         fase("controllo_corto_2", CORTO), fase("controllo_lungo_2", LUNGO)]
            controllo_ok = all(c["status"] == 200 for c in controllo)
            oracolo_ok = controllo_ok and controllo[0]["impronta"] == controllo[2]["impronta"] \
                and controllo[1]["impronta"] == controllo[3]["impronta"]
            rapporto["oracolo_ripetibile"] = oracolo_ok

            if controllo_ok and not args.senza_pressione:
                stato("fase 2: decode sotto pressione")
                rilascio, servizio, partito = run / "rilascia.flag", [None], threading.Event()

                def su_delta(n: int) -> None:
                    if n == 16 and not partito.is_set():
                        servizio[0] = subprocess.Popen(
                            [sys.executable, "-B", str(Path(__file__).resolve()), "--pressione", str(os.getpid()),
                             "--target-mib", str(args.target_mib), "--max-mib", str(args.max_mib),
                             "--max-secondi", str(args.max_secondi), "--rilascio", str(rilascio),
                             "--registro", str(run / "logs" / "pressione.jsonl")],
                            stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
                        partito.set()

                campioni, fine = [], threading.Event()

                def osserva() -> None:
                    while not fine.wait(0.5):
                        campioni.append({"t": round(time.time(), 1), "disponibile_mib": disponibile_mib(),
                                         **{k: v for k, v in stato_deposito(stderr_path).items() if k in ("missing", "evictions", "restores", "emergency")}})

                osservatore = threading.Thread(target=osserva, daemon=True)
                osservatore.start()
                try:
                    carico = chat(base, key, CARICO, args.max_tokens_carico, su_delta=su_delta)
                finally:
                    rilascio.write_text("rilascia\n", encoding="ascii")
                    if servizio[0] is not None:
                        try:
                            servizio[0].wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            servizio[0].kill()
                            log("ANOMALIA: processo di pressione ucciso")
                    fine.set()
                    osservatore.join(timeout=5)
                t0 = time.monotonic()
                while disponibile_mib() < 3072 and time.monotonic() - t0 < 30:
                    time.sleep(0.5)
                dopo = stato_deposito(stderr_path)
                rapporto["fasi"]["pressione"] = {
                    **carico, "pressione_partita": partito.is_set(), "campioni": campioni,
                    "disponibile_min_mib": min((c["disponibile_mib"] for c in campioni), default=None),
                    "missing_max": max((c["missing"] or 0 for c in campioni), default=0), "deposito_dopo": dopo,
                    "disponibile_dopo_rilascio_mib": disponibile_mib()}
                log(f"pressione: carico {carico} | minimo {rapporto['fasi']['pressione']['disponibile_min_mib']} MiB | deposito {dopo}")

            deposito = stato_deposito(stderr_path)
            sfrattato = (deposito["evictions"] or 0) > 0
            rapporto["sfratti_ottenuti"] = sfrattato
            if controllo_ok and sfrattato:
                stato("fase 3: prompt dopo lo sfratto")
                dopo = [fase("dopo_corto", CORTO), fase("dopo_lungo", LUNGO)]
                time.sleep(5)
                dopo.append(fase("dopo_corto_bis", CORTO))
                if all(d["status"] == 200 for d in dopo):
                    uguale = dopo[0]["impronta"] == controllo[0]["impronta"] and dopo[1]["impronta"] == controllo[1]["impronta"] \
                        and dopo[2]["impronta"] == controllo[0]["impronta"]
                    verdetto = "SUPERATA" if uguale or not oracolo_ok else "RISPOSTA DIVERSA DAL CONTROLLO"
                    if not oracolo_ok:
                        verdetto += " (oracolo non ripetibile gia' al controllo: testo non confrontato)"
                else:
                    verdetto = "DIFETTO RIPRODOTTO" if any(d["canary"] for d in dopo) else "ERRORE DIVERSO DAL CANARY"
            elif not controllo_ok:
                col_canary = any(c["canary"] for c in controllo)
                verdetto = ("DIFETTO RIPRODOTTO (sfratto gia' nel warmup)" if col_canary and sfrattato
                            else "CONTROLLO FALLITO SENZA CANARY")
            rapporto["deposito_finale"] = stato_deposito(stderr_path)
    except BaseException as exc:  # compreso KeyboardInterrupt: l'esito deve finire su file
        errore = f"{type(exc).__name__}: {exc}"
        log("ERRORE " + errore)
    finally:
        rapporto["verdetto"], rapporto["errore"] = verdetto, errore
        (run / "rapporto.json").write_text(json.dumps(rapporto, indent=2, ensure_ascii=False), encoding="utf-8")
        stato(f"FINE errore: {errore}" if errore else f"FINE ok: {verdetto}")
        runner_log.close()
    return 0 if verdetto.startswith("SUPERATA") and not errore else 1


if __name__ == "__main__":
    sys.exit(main())
