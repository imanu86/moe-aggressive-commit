"""Genera sul Desktop il lanciatore della modalita' ADATTIVA (runtime elastico M1, senza MTP).

Parte dal lanciatore quotidiano «Qwen - CGControl - senza MTP - 40 slot.bat» e ne cambia solo:
binari (runtime-m1 copiato in D:\\ds4_work\\bin_elastico_m1), slot di partenza (70), variabili
della cache elastica e della RAM dinamica, cartelle di log e di slot. La chiave API passa dal
file sorgente al file generato senza essere mai stampata; in git non entra nessun valore.

La politica non ha manopole nel bat: sta nel runtime (moe-ram-store.cuh e llama-moecache.cpp).
  VRAM: la cache esperti parte da 70 slot e si ridimensiona da sola tenendo ~200 MB liberi.
  RAM : otto strati di esperti in un deposito sfrattabile; sotto i 2 GiB disponibili sfratta
        verso SSD (rilegge dal GGUF), sotto 1 GiB o a commit quasi pieno va in emergenza;
        il tetto si riapre dopo 15 s sopra i 2,5 GiB.
"""
from __future__ import annotations
import hashlib
import shutil
import sys
from pathlib import Path

DESKTOP = Path(r"C:\Users\imanu\Desktop")
SORGENTE = DESKTOP / "Qwen - CGControl - senza MTP - 40 slot.bat"
USCITA = DESKTOP / "Qwen - ADATTIVO VRAM+RAM - senza MTP.bat"
RUNTIME_LAB = Path(r"C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_mtp_20260920\runtime-m1")
RUNTIME = Path(r"D:\ds4_work\bin_elastico_m1")
EXE_DAILY = r"D:\ds4_work\p11_work\build\bin\llama-server.exe"

ELASTICO = [
    "REM ---- modalita' adattiva (runtime elastico M1 di Codex, 20-21/9): stessa configurazione delle corse validate",
    'set "LLAMA_MOE_ELASTIC=1"',
    'set "LLAMA_MOE_ELASTIC_MAX=512"',
    'set "LLAMA_MOE_RAM_LAYERS=8"',
    'set "QWEN_MOE_RAM_OVERLAP_DOWN=1"',
    'set "LLAMA_MOE_RAM_EVICT=1"',
    'set "LLAMA_MOE_MTP=0"',
    'set "LLAMA_MOE_NGRAM=0"',
    'set "LLAMA_MTP_LIGHT=1"',
    'set "LLAMA_MTP_LIGHT_CTX=8192"',
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    assert SORGENTE.exists(), f"manca {SORGENTE}"
    if USCITA.exists():
        sys.exit(f"esiste gia': {USCITA} - non lo sovrascrivo")

    # 1) copia del runtime in una posizione stabile, verificata per SHA
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for f in sorted(RUNTIME_LAB.iterdir()):
        if f.is_file():
            dst = RUNTIME / f.name
            if not dst.exists():
                shutil.copy2(f, dst)
            assert sha(dst) == sha(f), f"copia non fedele: {f.name}"
            print(f"  {f.name:<28} {sha(dst)[:16]}")

    # 2) il bat
    testo = SORGENTE.read_bytes().decode("latin-1")
    exe = str(RUNTIME / "llama-server.exe")

    def cambia(vecchio: str, nuovo: str, volte: int | None = None) -> None:
        nonlocal testo
        n = testo.count(vecchio)
        assert n > 0 and (volte is None or n == volte), (vecchio[:50], n)
        testo = testo.replace(vecchio, nuovo)

    cambia("REM Qwen GSQ-RCO P11 X4 - profilo CGControl, senza MTP, 40 slot esperti.\r\n"
           "REM Cache ridotta per convivere con CGControl e desktop 8K.\r\n"
           "REM Margine di memoria da verificare al primo avvio, anche con prompt lunghi.\r\n",
           "REM Qwen GSQ-RCO - modalita' ADATTIVA, senza MTP (runtime elastico M1).\r\n"
           "REM VRAM: la cache esperti parte da 70 slot e si adatta ai programmi aperti (circa 200 MB liberi).\r\n"
           "REM RAM : sotto i 2 GiB disponibili otto strati di esperti vengono sfrattati verso SSD e ricaricati.\r\n"
           "REM Generato il 21/9/2026 da docs/porto/banco_followup/genera_bat_elastico.py. Assetto temporaneo.\r\n", 1)
    cambia(EXE_DAILY, exe, 3)
    cambia("--moe-expert-cache ^\r\n  40 ^", "--moe-expert-cache ^\r\n  70 ^", 1)
    ubatch = 'set "QWEN_PREFILL_UBATCH_DEEP=81920:3072,114688:2048"\r\n'
    cambia(ubatch, ubatch + "\r\n".join(ELASTICO) + "\r\n", 1)
    cambia("qwen38_gsq_rco_p11_no_mtp_40_cgcontrol_slots", "qwen38_gsq_rco_elastico_slots")
    cambia("qwen38_gsq_rco_p11_logs", "qwen38_gsq_rco_elastico_logs")
    cambia("gsq_rco_P11_X4_NO_MTP_40_CGCONTROL_DIAG_", "gsq_rco_ELASTICO_M1_NO_MTP_")
    cambia("echo Avvio Qwen GSQ-RCO P11 X4 - CGControl, NO MTP, 40 slot - su",
           "echo Avvio Qwen GSQ-RCO ADATTIVO (cache esperti da 70 dinamica, RAM dinamica, NO MTP) - su", 1)
    assert "p11_work" not in testo and "  40 ^" not in testo
    USCITA.write_bytes(testo.encode("latin-1"))
    print("scritto:", USCITA, f"({len(testo.splitlines())} righe)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
