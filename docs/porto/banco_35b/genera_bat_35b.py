"""Genera sul Desktop un lanciatore per la rotta Haiku del gateway, 26/9/2026.  Uso: genera_bat_35b.py [35b|ling]

Il gateway (docs/porto/qwen_gateway, rotta_locale.py) senza locale.json manda le chat Haiku (streaming + tool) al
server di PRODUZIONE su 127.0.0.1:8100 con la chiave dei lanciatori del daily. Questi bat accendono li' un altro
modello al posto del daily: stessa porta, stessa chiave, nessuna modifica al gateway ne' ai bat esistenti.
Ascoltano SOLO su 127.0.0.1. La chiave API passa dal lanciatore sorgente al file generato senza essere mai
stampata; in git non entra.

Profili (banco del 25-26/9, docs/porto/banco_35b/RISULTATI_25_SETTEMBRE.md):
  35b  Qwen3.6-35B-A3B UD-IQ3_XXS con testa MTP interna, runtime elastico Q36-M3 (esperti fuori, cache elastica
       da 70 slot), esperti della testa in CUDA0_Mapped, bozza n-max 2.
  ling Ling-3.0-tiny Q4_K_M tutto in VRAM (niente cache esperti), bozza ngram-simple (senza perdita), instradamento
       a gruppi originale. Voluto dall'utente per «vedere quanto fa schifo» sul lavoro vero.
Entrambi: contesto 131072, un solo slot con checkpoint del prompt (-ctxcp 8) come il daily, ragionamento acceso.
"""
from __future__ import annotations
import hashlib
import re
import shutil
import sys
from pathlib import Path

DESKTOP = Path(r"C:\Users\imanu\Desktop")
SORGENTE_CHIAVE = DESKTOP / "Qwen - ADATTIVO M2 VRAM+RAM - senza MTP.bat"
RUNTIME_LAB = Path(r"D:\ds4_work\elastico_q36_m3\runtime-q36m3")
RUNTIME = Path(r"D:\ds4_work\bin_q36m3")

COMUNI_FINE = ["--metrics", "-t", "16", "-c", "131072", "-np", "1",
               "--jinja", "--reasoning", "on", "--reasoning-preserve", "--no-context-shift",
               "--cache-ram", "0", "-ctxcp", "8"]

PROFILI = {
    "35b": dict(
        uscita=DESKTOP / "Qwen 35B - ADATTIVO + MTP - porta 8100.bat",
        modello=r"D:\models\qwen36moe\Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf",
        base=r"D:\ds4_work\qwen35b_servizio",
        sigla="q35b",
        titolo=["REM Qwen3.6-35B-A3B MoE (IQ3 + testa MTP interna) - runtime elastico Q36-M3 - al posto del daily sulla 8100.",
                "REM VRAM: cache esperti da 70 slot, si adatta ai programmi aperti."],
        env=[("LLAMA_MOE_HIT_REPORT", "0"), ("GGML_CUDA_MOE_CPU_PREFILL", "0"), ("LLAMA_MOE_DEMAND_GPU", "1"),
             ("LLAMA_MOE_DYNAMIC_WORKSPACE", "1"), ("GGML_CUDA_SCALAR_GATHER", "1"), ("GGML_CUDA_MOE_FREQUENCY", "1"),
             ("QWEN_MOE_OVERLAP_DOWN", "1"), ("LLAMA_MOE_CACHE_BATCH", "3"), ("LLAMA_MOE_PHASE_CACHE", "1"),
             ("QWEN_MOE_SHARED_CARVEOUT", "1"), ("GGML_SCHED_ASYNC_INPUTS", "1"), ("GGML_CUDA_GRAPH_COMPAT_CACHE", "1"),
             ("GGML_CUDA_MMVQ_OCCUPANCY", "1"), ("QWEN_MOE_SCALAR_BATCH", "2"), ("LLAMA_MOE_ELASTIC", "1"),
             ("LLAMA_MOE_ELASTIC_MAX", "512"), ("LLAMA_MOE_RAM_LAYERS", "0"), ("LLAMA_MTP_LIGHT", "1"),
             ("LLAMA_MTP_LIGHT_CTX", "8192")],
        args=["--tensor-split", "1", "-fit", "off", "-ngl", "99", "-fa", "on", "--lazy-mode", "off",
              # niente "|" nella regex: dentro un .bat cmd lo leggerebbe come pipe e spezzerebbe la riga
              "-ot", r"blk\.40\.ffn_.*_exps\.weight=CUDA0_Mapped",
              "--n-cpu-moe", "40", "--moe-expert-cache", "70", "--no-mmap", "-ctk", "q8_0", "-ctv", "q8_0",
              "--spec-type", "draft-mtp", "--spec-draft-n-max", "2", "--spec-draft-p-min", "0",
              "-ctkd", "q8_0", "-ctvd", "q8_0", "-b", "4096", "-ub", "2048"],
    ),
    "ling": dict(
        uscita=DESKTOP / "Qwen Ling-3.0-tiny - PROVA - porta 8100.bat",
        modello=r"D:\models\ling3tiny\Ling-3.0-tiny-Q4_K_M.gguf",
        base=r"D:\ds4_work\ling_servizio",
        sigla="ling",
        titolo=["REM Ling-3.0-tiny (inclusionAI, MoE 7,9B / 1,3B attivi) Q4_K_M tutto in VRAM - al posto del daily sulla 8100.",
                "REM Bozza ngram-simple (non cambia il testo), instradamento a gruppi originale. Modello di PROVA."],
        env=[("GGML_SCHED_ASYNC_INPUTS", "1"), ("GGML_CUDA_GRAPH_COMPAT_CACHE", "1"), ("GGML_CUDA_MMVQ_OCCUPANCY", "1")],
        args=["-ngl", "99", "-fit", "off", "-fa", "on", "--no-mmap", "-ctk", "q8_0", "-ctv", "q8_0",
              "--spec-type", "ngram-simple", "-b", "2048", "-ub", "2048",
              # 200k voluti dall'utente (26/9): nativo 128k, la scheda dichiara 256k con YaRN. YaRN da solo non basta
              # (il server tronca a n_ctx_train, lezione del 35B l'8/9): serve anche l'override di context_length.
              "--override-kv", "bailingmoe3.context_length=int:262144",
              "--rope-scaling", "yarn", "--rope-scale", "2", "--yarn-orig-ctx", "131072"],
        ctx="204800",
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    nome = sys.argv[1] if len(sys.argv) > 1 else "35b"
    P = PROFILI[nome]
    uscita, modello, base = P["uscita"], P["modello"], P["base"]
    if uscita.exists():
        sys.exit(f"esiste gia': {uscita} - non lo sovrascrivo")
    m = re.search(r'set "API_KEY=([^"]+)"', SORGENTE_CHIAVE.read_bytes().decode("latin-1"))
    assert m, f"chiave non trovata in {SORGENTE_CHIAVE}"
    chiave = m.group(1)
    assert Path(modello).exists(), modello

    RUNTIME.mkdir(parents=True, exist_ok=True)
    for f in sorted(RUNTIME_LAB.iterdir()):
        if f.is_file():
            dst = RUNTIME / f.name
            if not dst.exists():
                shutil.copy2(f, dst)
            assert sha(dst) == sha(f), f"copia non fedele: {f.name}"
            print(f"  {f.name:<28} {sha(dst)[:16]}")
    exe = RUNTIME / "llama-server.exe"
    comuni = [x if x != "131072" else P.get("ctx", "131072") for x in COMUNI_FINE]
    args = (["-m", f'"{modello}"'] + P["args"] + comuni +
            ["--slot-save-path", f'"{base}\\slots"', "--host", "%HOST%", "--port", "%PORT%", "--api-key", "%API_KEY%",
             "--log-file", f'"{base}\\logs\\{P["sigla"]}_%STAMP%.log"', "-lv", "3"])

    righe = ["@echo off"] + P["titolo"] + [
        "REM Il gateway Qwen-al-posto-di-Haiku lo trova da solo (stessa porta e stessa chiave del daily). Solo 127.0.0.1.",
        f"REM Generato il 26/9/2026 da docs/porto/banco_35b/genera_bat_35b.py {nome}. Per fermarlo: chiudi questa finestra.",
        "setlocal",
        'set "HOST=127.0.0.1"',
        'set "PORT=8100"',
        f'set "API_KEY={chiave}"',
        'for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "D=%%c%%b%%a"',
        'for /f "tokens=1-2 delims=:." %%a in ("%time%") do set "T=%%a%%b"',
        'set "STAMP=%D%_%T: =0%"',
        "REM ---- guardia istanza unica: se la porta e gia in ascolto NON avvio un secondo server",
        'netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul',
        "if not errorlevel 1 (",
        "  echo ERRORE: la porta %PORT% e gia in ascolto. Chiudi il server esistente e rilancia.",
        "  timeout /t 20",
        "  exit /b 1",
        ")",
        'tasklist /FI "IMAGENAME eq llama-server.exe" /NH | findstr /I /C:"llama-server.exe" >nul',
        "if not errorlevel 1 (",
        "  echo ERRORE: un llama-server e gia attivo. Chiudilo prima di avviare questo modello.",
        "  timeout /t 20",
        "  exit /b 1",
        ")",
    ]
    for f in (modello, str(exe)):
        righe += [f'if not exist "{f}" (', f'  echo ERRORE: file richiesto mancante: "{f}"', "  timeout /t 20",
                  "  exit /b 1", ")"]
    righe += [f'set "{k}={v}"' for k, v in P["env"]]
    righe += [
        f'if not exist "{base}\\logs" mkdir "{base}\\logs"',
        f'if not exist "{base}\\slots" mkdir "{base}\\slots"',
        f'cd /d "{base}"',
        f"echo Avvio {Path(modello).stem} su %HOST%:%PORT%  (log: {base}\\logs\\{P['sigla']}_%STAMP%.log)",
        f'"{exe}" ^',
    ]
    righe += [f"  {a} ^" for a in args[:-1]] + [f"  {args[-1]}"]
    righe += ["if errorlevel 1 (", "  echo Il server e uscito con errore %errorlevel%. Vedi il log.", "  timeout /t 60",
              ")", "endlocal"]
    uscita.write_bytes(("\r\n".join(righe) + "\r\n").encode("latin-1"))
    print("scritto:", uscita, f"({len(righe)} righe)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
