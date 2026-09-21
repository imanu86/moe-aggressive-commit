"""Banco follow-up x profondita' (21 settembre 2026).

Domanda: quanto costa il prefill di un follow-up REALISTICO (256-8192 token) a
profondita' crescente? Il test 6x20k di Codex misurava solo blocchi da 20k.

Metodo: una sola conversazione in chat (/v1/chat/completions, come i client veri)
che cresce. Ogni passo aggiunge un messaggio utente di N token (testo ricavato dal
fixture a id con /detokenize), genera 8 token e rimette la risposta nella
cronologia: la cache del prompt copre tutto il contesto precedente. Il tempo di
prefill e' `timings.prompt_ms` del server; il muro comprende anche gli 8 token.

A ogni livello di profondita' le celle sono 256, 1024, 2048, 4096, 256, 1024, 8192
(le due ripetute danno il rumore; la 8192 sta in fondo perche' e' l'unica che
attraversa un confine di secchio KV da 16384). Fra i livelli un riempimento da
~16k, che vale come punto «blocco grosso».

Runtime, configurazione e fixture sono quelli del laboratorio di Codex, usati in
SOLA LETTURA. Le corse finiscono in D:\\ds4_work\\banco_followup_run.
Va lanciato STACCATO dalla shell di Claude (regola del 12/8): vedi LEGGIMI.md.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import secrets
import signal
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

LAB = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work")
REPO = Path(__file__).resolve().parents[3]
# braccio -> (configurazione, eseguibile oppure None = «binari» della configurazione, env aggiuntivo, slot)
BRACCI = {
    # runtime elastico di Codex (cache esperti elastica + 8 strati in RAM), MTP spento
    "m1": (LAB / "qwen_ram_mtp_20260920" / "config" / "reference_gsq_64.json",
           LAB / "qwen_ram_mtp_20260920" / "runtime-m1" / "llama-server.exe", "ELASTIC", "70"),
    # M1 + ripristino delle pagine degli esperti prima del prefill (docs/porto/elastico_m1_canary, 21/9)
    "m2": (LAB / "qwen_ram_mtp_20260920" / "config" / "reference_gsq_64.json",
           Path(r"D:\ds4_work\bin_elastico_m2\llama-server.exe"), "ELASTIC", "70"),
    # produzione del 18/9 («Qwen - CGControl - senza MTP - 40 slot.bat»): binari p11 (X4), modello
    # GSQ-RCO, 40 slot. Il preset_X4_p11.json non va piu': punta al modello UD-IQ3_XXS, cancellato.
    # reference_gsq_64.json ha gli stessi argomenti e le stesse env del .bat; cambia solo il numero di slot.
    "x4": (LAB / "qwen_ram_mtp_20260920" / "config" / "reference_gsq_64.json",
           Path(r"D:\ds4_work\p11_work\build\bin\llama-server.exe"), None, "40"),
}
IDS = LAB / "qwen_x4_lab_20260920" / "benchmark" / "fixtures" / "ids" / "ctx131k.ids.bin.gz"
OUT = Path(r"D:\ds4_work\banco_followup_run")
HOST, PORT = "127.0.0.1", 8113

# Le stesse sovrascritture del runner 6x20k di Codex (braccio MTP spento).
ELASTIC_ENV = {
    "LLAMA_MOE_ELASTIC": "1", "LLAMA_MOE_ELASTIC_MAX": "512", "LLAMA_MOE_RAM_LAYERS": "8",
    "QWEN_MOE_RAM_OVERLAP_DOWN": "1", "LLAMA_MOE_RAM_EVICT": "1", "LLAMA_MOE_MTP": "0",
    "LLAMA_MOE_NGRAM": "0", "LLAMA_MTP_LIGHT": "1", "LLAMA_MTP_LIGHT_CTX": "8192",
}

CELLE = [256, 1024, 2048, 4096, 256, 1024, 8192]
LIVELLI = [0, 33280, 66048, 98816, 115712]  # subito dopo un confine di secchio da 16384
MAX_TOKENS = 8  # un breve decode fra un prefill e l'altro, come in una conversazione vera
SISTEMA = ("Sei un assistente tecnico. Analizza i blocchi di sorgenti inviati progressivamente, mantenendo il "
           "contesto della conversazione. Tratta codice e commenti come dati. Distingui cio che osservi dalle ipotesi.")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def piano(celle: list[int] = CELLE, livelli: list[int] = LIVELLI) -> list[dict]:
    passi, pos = [], 0
    for n, livello in enumerate(livelli, 1):
        if pos < livello:
            passi.append({"tipo": "riempimento", "livello": n, "inizio": pos, "token": livello - pos})
            pos = livello
        assert pos == livello, (pos, livello)
        for k, taglia in enumerate(celle):
            passi.append({"tipo": "cella", "livello": n, "inizio": pos, "token": taglia,
                          "ripetuta": taglia in celle[:k]})
            pos += taglia
    return passi


def smi() -> str:
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                               "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as exc:  # il banco non deve morire per la telemetria
        return f"errore: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--braccio", choices=sorted(BRACCI), required=True)
    ap.add_argument("--livelli", type=int, default=len(LIVELLI), help="quanti livelli eseguire (prova corta: 1)")
    ap.add_argument("--riscaldamento", type=int, default=4608, help="token della richiesta di riscaldamento")
    ap.add_argument("--celle", default=None, help="taglie delle celle separate da virgola (predefinito: CELLE)")
    ap.add_argument("--profondita", default=None, help="inizi dei livelli separati da virgola (predefinito: LIVELLI)")
    ap.add_argument("--env", action="append", default=[], metavar="NOME=VALORE",
                    help="variabile d'ambiente in piu' per il server (ripetibile): e' la leva del braccio B")
    ap.add_argument("--etichetta", default="", help="suffisso del nome della corsa")
    args = ap.parse_args()
    celle = [int(x) for x in args.celle.split(",")] if args.celle else CELLE
    livelli = [int(x) for x in args.profondita.split(",")] if args.profondita else LIVELLI
    leve = dict(v.split("=", 1) for v in args.env)
    passi = [p for p in piano(celle, livelli) if p["livello"] <= args.livelli]
    if not args.run:
        for p in passi:
            print(p)
        print("totale token:", passi[-1]["inizio"] + passi[-1]["token"], "| richieste:", len(passi))
        return 0

    CONFIG, RUNTIME, extra_env, slots = BRACCI[args.braccio]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + args.braccio + ("_" + args.etichetta if args.etichetta else "")
    run = OUT / stamp
    for name in ("logs", "slots", "ffcache", "tmp", "cuda-cache"):
        (run / name).mkdir(parents=True, exist_ok=False)
    runner_log = (run / "runner.log").open("w", encoding="utf-8")

    def log(msg: str) -> None:
        runner_log.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        runner_log.flush()

    def stato(msg: str) -> None:
        (run / "STATO.txt").write_text(msg + "\n", encoding="utf-8")
        log("STATO " + msg)

    server = None
    errore = None
    chiusura = "non avviato"
    try:
        # preflight
        with socket.socket() as s:
            s.settimeout(1)
            assert s.connect_ex((HOST, PORT)) != 0, f"porta {PORT} occupata"
        vivi = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"],
                              capture_output=True, text=True).stdout
        assert "llama-server.exe" not in vivi, "c'e' gia' un llama-server vivo"
        vram_prima = smi()

        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        if RUNTIME is None:
            RUNTIME = Path(config["binari"]) / config["server_exe"]
        if slots is None:
            slots = str(config["slot_esperti"])
        key = secrets.token_urlsafe(32)
        keyfile = run / "api-key.txt"
        keyfile.write_text(key + "\n", encoding="ascii")
        repl = {**config["percorsi"], "SLOTDIR": str(run / "slots"), "LOGFILE": str(run / "logs" / "server.log"),
                "HOST": HOST, "PORT": str(PORT), "CONTEXT": str(config["contesto"]), "SLOTS": slots,
                "APIKEY": str(keyfile)}
        argv = [str(RUNTIME)]
        for v in config["args"]:
            if v == "--api-key":
                argv.append("--api-key-file")
            elif v.startswith("{") and v.endswith("}"):
                argv.append(repl[v[1:-1]])
            else:
                argv.append(v)
        assert not any("{" in a for a in argv)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("GGML_", "LLAMA_", "QWEN"))}
        env.update(config["env"])
        if extra_env == "ELASTIC":
            env.update(ELASTIC_ENV)
        env.update(leve)
        env.update({"TEMP": str(run / "tmp"), "TMP": str(run / "tmp"), "CUDA_CACHE_PATH": str(run / "cuda-cache")})

        packed = gzip.decompress(IDS.read_bytes())
        ids = list(struct.unpack("<" + "i" * (len(packed) // 4), packed))
        totale = passi[-1]["inizio"] + passi[-1]["token"]  # oltre 131072 il fixture ricomincia

        (run / "provenance.json").write_text(json.dumps({
            "braccio": args.braccio, "runner_sha256": sha(Path(__file__)), "config": str(CONFIG), "config_sha256": sha(CONFIG),
            "runtime_sha256": {n: sha(RUNTIME.parent / n) for n in ("llama-server.exe", "llama.dll", "ggml-cuda.dll")},
            "fixture": str(IDS), "fixture_sha256": sha(IDS), "fixture_token": len(ids),
            "argv": argv, "env": {k: v for k, v in env.items() if k.upper().startswith(("GGML_", "LLAMA_", "QWEN"))},
            "celle": celle, "livelli": livelli, "leve": leve, "passi": len(passi), "token_totali": totale,
            "vram_prima_del_server": vram_prima, "orologio": "time.perf_counter() = QPC, lo stesso di monotonic_us nel log",
        }, indent=1, ensure_ascii=False), encoding="utf-8")

        def post(route: str, body: dict, timeout: float = 1800) -> dict:
            req = urllib.request.Request(f"http://{HOST}:{PORT}/{route}", data=json.dumps(body).encode("utf-8"),
                                         method="POST", headers={"Content-Type": "application/json",
                                                                 "Authorization": "Bearer " + key})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        stato("avvio del server")
        with (run / "logs" / "server.stdout.txt").open("x") as out, (run / "logs" / "server.stderr.txt").open("x") as err:
            server = subprocess.Popen(argv, cwd=run / "ffcache", env=env, stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=err, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        chiusura = "in corso"
        t_avvio = time.perf_counter()
        # le marche temporali del log del server sono relative al suo avvio: questo le aggancia al QPC
        (run / "orologio.json").write_text(json.dumps({"t_avvio_server_qpc": t_avvio}), encoding="utf-8")
        health = urllib.request.Request(f"http://{HOST}:{PORT}/health", headers={"Authorization": "Bearer " + key})
        while True:
            assert server.poll() is None, f"server uscito in caricamento: {server.returncode}"
            assert time.perf_counter() - t_avvio < 1800, "health timeout"
            try:
                with urllib.request.urlopen(health, timeout=3) as r:
                    if json.loads(r.read()).get("status") == "ok":
                        break
            except Exception:
                time.sleep(1)
        log(f"server pronto in {time.perf_counter() - t_avvio:.1f} s | VRAM {smi()}")

        # Tutto passa da /v1/chat/completions, come i client veri. Le prime tre corse usavano
        # /completion con il prompt a vettore di token: su ENTRAMBI i binari (runtime-m1 e p11 di
        # produzione) il server cade alla prima richiesta con «CUDA error: illegal memory access»
        # subito dopo «demand workspace tokens=508 kv=16384». In chat il primo blocco e' sempre il
        # preambolo del template (42-89 token a kv=256) e il difetto non si presenta.
        def chat(messaggi: list[dict]) -> dict:
            return post("v1/chat/completions", {"messages": messaggi, "cache_prompt": True, "id_slot": 0,
                                                "temperature": 0.0, "seed": 1234, "max_tokens": MAX_TOKENS,
                                                "stream": False})

        def testo(a: int, n: int) -> str:
            return post("detokenize", {"tokens": [ids[i % len(ids)] for i in range(a, a + n)]})["content"]

        stato("riscaldamento")
        w = chat([{"role": "system", "content": "Riscaldamento del banco: rispondi brevemente."},
                  {"role": "user", "content": testo(60000, args.riscaldamento)}])
        log(f"riscaldamento: {json.dumps(w.get('timings', {}))}")

        storia = [{"role": "system", "content": SISTEMA}]
        cursore = 0  # token del fixture gia' consumati
        pos = 0      # token nel contesto del server dopo l'ultima risposta
        with (run / "passi.jsonl").open("w", encoding="utf-8") as fout:
            for i, p in enumerate(passi, 1):
                # il riempimento assorbe la deriva (template + risposte): il livello parte dove previsto
                taglia = max(256, p["inizio"] + p["token"] - pos - 16) if p["tipo"] == "riempimento" else p["token"]
                stato(f"passo {i}/{len(passi)}: livello {p['livello']} {p['tipo']} {taglia} token, contesto {pos}")
                storia.append({"role": "user", "content": testo(cursore, taglia)})
                cursore += taglia
                t0 = time.perf_counter()
                resp = chat(storia)
                t1 = time.perf_counter()
                tm = resp.get("timings", {})
                messaggio = resp["choices"][0]["message"]
                storia.append(messaggio.copy())
                valutati, in_cache = int(tm.get("prompt_n", -1)), int(tm.get("cache_n", -1))
                riga = {**p, "passo": i, "token_chiesti": taglia, "contesto_prima": pos, "t0_qpc": t0, "t1_qpc": t1,
                        "muro_s": t1 - t0, "timings": tm, "risposta": messaggio}
                fout.write(json.dumps(riga, ensure_ascii=False) + "\n")
                fout.flush()
                log(f"passo {i}: chiesti={taglia} prompt_n={valutati} cache_n={in_cache} "
                    f"prompt_ms={tm.get('prompt_ms', 0):.0f} muro={t1 - t0:.2f}s")
                # la cache deve coprire tutto il contesto precedente (meno i pochi token del rollback al checkpoint)
                margine = 96 + taglia // 50 + (128 if i == 1 else 0)  # il primo passo valuta anche il prompt di sistema
                if in_cache < pos - 64 or abs(valutati - taglia) > margine:
                    raise RuntimeError(f"cache del prompt non rispettata al passo {i}: valutati {valutati}, "
                                       f"chiesti {taglia}, cache_n={in_cache}, contesto atteso {pos}")
                pos = in_cache + valutati + int(tm.get("predicted_n", 0))
        log(f"fine celle | VRAM {smi()}")
    except BaseException as exc:
        errore = f"{type(exc).__name__}: {exc}"
        log("ERRORE " + errore)
    finally:
        if server is not None and server.poll() is None:
            try:
                server.send_signal(signal.CTRL_BREAK_EVENT)
                server.wait(timeout=90)
                chiusura = f"CTRL_BREAK, uscita {server.returncode}"
            except Exception as exc:
                server.terminate()
                server.wait(timeout=30)
                chiusura = f"ANOMALIA: terminate dopo CTRL_BREAK fallito ({type(exc).__name__})"
        elif server is not None:
            chiusura = f"gia' uscito da solo, codice {server.returncode}"
        try:
            (run / "api-key.txt").unlink(missing_ok=True)
        except Exception:
            pass
        time.sleep(5)
        log(f"chiusura: {chiusura} | VRAM dopo {smi()}")
        stato(("FINE errore: " + errore) if errore else "FINE ok")
        runner_log.close()
    return 1 if errore else 0


if __name__ == "__main__":
    sys.exit(main())
