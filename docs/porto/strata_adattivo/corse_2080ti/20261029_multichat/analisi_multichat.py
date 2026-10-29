"""Analisi per fasi delle corse multichat 0.2.7.1 (29/10/2026): stesso metodo di 20261026_leve/analisi_fasi.py (importato, non copiato).

    python analisi_multichat.py > fasi_generato.md
"""
import importlib.util, inspect, re, sys
from pathlib import Path

H = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('analisi_fasi', H.parent / '20261026_leve' / 'analisi_fasi.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
A.CORSE = H / 'corse'
runs = sorted(p for p in A.CORSE.iterdir() if p.name.startswith('replay_') and (p / 'res.json').exists())
rid = {}
print('# Dati generati da analisi_multichat.py (non editare a mano)\n')
for p in runs:
    j, rs = A.carica(p)
    nome = p.name.replace('replay_', '')
    rid[nome] = (A.stampa_run(nome, p, rs, j, p), rs, j, p)
# tabelle_fasi: stessa funzione, elenco dei bracci sostituito con quelli presenti
src = inspect.getsource(A.tabelle_fasi)
src = re.sub(r"for nome in \(.*?\):", "for nome in NOMI:", src, count=1, flags=re.S)
ns = dict(vars(A), NOMI=tuple(rid))
exec(src, ns)
A.riepilogo(rid)
ns['tabelle_fasi'](rid)
A.tabella_grande(rid)
