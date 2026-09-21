"""Banco follow-up sui binari M2 (ripristino prima del prefill), senza toccare banco_followup.py.

Aggiunge a caldo il braccio `m2` (stessa configurazione ed env di `m1`, binari in
D:\\ds4_work\\elastico_m2\\runtime-m2) e passa gli argomenti al banco. Serve per il confronto a regime
contro M1: con `missing == 0` il percorso del prefill e' lo stesso, i tempi devono stare nel rumore.

Uso (staccato dalla shell di Claude):  python banco_m2.py --run --braccio m2 --livelli 1
"""
import importlib.util
import sys
from pathlib import Path

_BANCO = Path(__file__).resolve().parents[1] / "banco_followup" / "banco_followup.py"
_spec = importlib.util.spec_from_file_location("banco_followup", _BANCO)
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

config, _, extra_env, slots = B.BRACCI["m1"]
B.BRACCI["m2"] = (config, Path(r"D:\ds4_work\elastico_m2\runtime-m2\llama-server.exe"), extra_env, slots)

if __name__ == "__main__":
    sys.exit(B.main())
