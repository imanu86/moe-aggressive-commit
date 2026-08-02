#!/usr/bin/env python3
"""Fonde le schede degli agenti dentro il grafo estratto.

Senza questo, 119 file TSV sono 119 file TSV. Con questo, ogni funzione del
grafo ha anche categoria, ruolo, costo e trappole -- e `catena.py` puo'
rispondere non solo "cosa tocca" ma "cosa fa e quanto costa".

Controlla anche cio' che gli agenti hanno sbagliato: nomi inventati, colonne
mancanti, valori fuori dall'insieme ammesso. Un agente che allucina un nome di
funzione va scoperto, non fuso.

Uso:  python ricongiungi.py <cartella_lotti> [mappa.json]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

QUI = Path(__file__).parent

COLONNE = ['nome', 'categoria', 'ruolo', 'vram', 'frequenza', 'fase',
           'invariante', 'trappola', 'certezza']

AMMESSI = {
    'categoria': {'allocazione', 'trasporto', 'routing', 'attenzione', 'kv',
                  'quantizzazione', 'telemetria', 'piattaforma', 'controllo',
                  'parsing', 'test', 'altro'},
    'vram': {'alloca', 'libera', 'misura', 'scrive', 'legge', 'no'},
    'frequenza': {'per-token', 'per-layer', 'per-esperto', 'per-richiesta',
                  'avvio', 'mai', 'ignoto'},
    'fase': {'prefill', 'decode', 'entrambe', 'avvio', 'chiusura', 'ignoto'},
    'certezza': {'alta', 'media', 'bassa'},
}


def main(cartella, mappa_path=None):
    cartella = Path(cartella)
    mappa_path = Path(mappa_path) if mappa_path else QUI / 'mappa.json'
    m = json.loads(mappa_path.read_text(encoding='utf-8'))
    noti = {f['nome'] for f in m['funzioni']}

    schede, problemi = {}, defaultdict(list)
    n_righe = 0
    for tsv in sorted(cartella.glob('SCHEDE_*.tsv')):
        for i, riga in enumerate(tsv.read_text(encoding='utf-8',
                                               errors='replace').splitlines(), 1):
            riga = riga.rstrip('\n')
            if not riga.strip():
                continue
            campi = riga.split('\t')
            n_righe += 1
            if len(campi) != len(COLONNE):
                problemi['colonne sbagliate'].append(
                    f"{tsv.name}:{i} ha {len(campi)} campi invece di {len(COLONNE)}")
                continue
            s = dict(zip(COLONNE, (c.strip() for c in campi)))
            if s['nome'] == 'nome':          # intestazione lasciata per errore
                continue
            if s['nome'] not in noti:
                problemi['nome inventato'].append(f"{tsv.name}:{i} {s['nome']}")
                continue
            for col, valori in AMMESSI.items():
                if s[col] not in valori:
                    problemi[f'{col} fuori insieme'].append(
                        f"{tsv.name}:{i} {s['nome']} = {s[col]!r}")
                    s[col] = 'ignoto' if 'ignoto' in valori else 'altro'
            s['lotto'] = tsv.name
            if s['nome'] in schede:
                problemi['doppione'].append(f"{tsv.name}:{i} {s['nome']}")
                continue
            schede[s['nome']] = s

    for f in m['funzioni']:
        s = schede.get(f['nome'])
        if s:
            f.update({k: s[k] for k in COLONNE[1:]})
    m['schede_fuse'] = len(schede)
    mappa_path.write_text(json.dumps(m, indent=1), encoding='utf-8')

    print(f"  righe lette        {n_righe}")
    print(f"  schede fuse        {len(schede)} su {len(noti)} funzioni "
          f"({100.0 * len(schede) / len(noti):.1f}%)")
    if problemi:
        print("\n  PROBLEMI")
        for k, v in sorted(problemi.items(), key=lambda x: -len(x[1])):
            print(f"    {k}: {len(v)}")
            for r in v[:3]:
                print(f"        {r}")

    if schede:
        print("\n  QUELLO CHE ORA SAPPIAMO")
        for col in ('categoria', 'vram', 'frequenza', 'fase', 'certezza'):
            c = Counter(s[col] for s in schede.values())
            print(f"    {col:<11} " + '  '.join(
                f"{k}={n}" for k, n in c.most_common(7)))

        caldo = [s for s in schede.values()
                 if s['frequenza'] in ('per-token', 'per-layer', 'per-esperto')]
        print(f"\n  SUL CAMMINO CALDO: {len(caldo)} funzioni")
        cv = [s for s in caldo if s['vram'] in ('alloca', 'libera')]
        if cv:
            print(f"    di cui ALLOCANO O LIBERANO VRAM per token/layer/esperto: {len(cv)}")
            for s in cv[:12]:
                print(f"      {s['nome']:<44} {s['vram']:<7} {s['frequenza']}")

        trap = [s for s in schede.values() if s['trappola'] not in ('-', '', 'nessuna')]
        print(f"\n  TRAPPOLE SEGNALATE: {len(trap)}")
        for s in sorted(trap, key=lambda x: x['certezza'])[:15]:
            print(f"    [{s['certezza']}] {s['nome']}: {s['trappola'][:88]}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
