#!/usr/bin/env python3
"""Divide le 5164 funzioni in lotti, e scrive per ciascuno un mandato completo.

Il mandato porta gia' dentro i fatti meccanici (righe, chiamanti, chiamate,
variabili lette, guardie): l'agente ANNOTA, non riscopre. Cosi' il lavoro e'
denso e l'esito e' strutturato, non prosa.

Uso:  python sharda.py <cartella_uscita>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

QUI = Path(__file__).parent

# quanto vale il file per il nostro problema: decide la granularita' del lotto.
# Piu' e' rilevante, piu' funzioni per agente sono poche e l'analisi profonda.
PRIORITA = [
    (['ds4_cuda.cu', 'src/cuda/'], 40, 'IL CAMMINO CUDA: e\' dove giriamo'),
    (['ds4.c'], 55, 'IL MOTORE: forward pass, modello, streaming'),
    (['ds4_server.c', 'ds4_cli.c', 'ds4_kvstore.c'], 80, 'servizio e CLI'),
    (['ds4_agent.c', 'ds4_eval.c', 'ds4_distributed.c', 'ds4_tp.c'], 110,
     'agente, valutazione, distribuito: non girano da noi'),
]
RESTO = (150, 'resto: piattaforme che non usiamo, utilita\'')


def priorita_di(percorso):
    for i, (prefissi, dim, etichetta) in enumerate(PRIORITA):
        if any(percorso == p or percorso.startswith(p) for p in prefissi):
            return i, dim, etichetta
    return len(PRIORITA), RESTO[0], RESTO[1]


def main(uscita):
    uscita = Path(uscita)
    uscita.mkdir(parents=True, exist_ok=True)
    m = json.loads((QUI / 'mappa.json').read_text(encoding='utf-8'))
    g = json.loads((QUI / 'guardie.json').read_text(encoding='utf-8'))

    chiamata_da = defaultdict(set)
    chiama = defaultdict(set)
    for c in m['chiamate']:
        chiamata_da[c['a']].add(c['da'])
        chiama[c['da']].add(c['a'])

    env_in = defaultdict(set)
    sem_di = {}
    for l in m['letture_env']:
        if l['funzione']:
            env_in[l['funzione']].add(l['variabile'])
        sem_di[l['variabile']] = l['semantica']

    guardie_in = defaultdict(list)
    for s in g['siti']:
        if s['tipo'] == 'env' and s['guardie']:
            guardie_in[s['funzione']].append((s['nome'], s['guardie']))

    globali_in = defaultdict(set)
    for w in m['globali_scritte']:
        globali_in[w['funzione']].add(w['globale'])

    per_file = defaultdict(list)
    for f in m['funzioni']:
        per_file[f['file']].append(f)

    lotti = []
    for percorso in sorted(per_file, key=lambda p: (priorita_di(p)[0], p)):
        pri, dim, etichetta = priorita_di(percorso)
        fs = sorted(per_file[percorso], key=lambda x: x['riga'])
        for i in range(0, len(fs), dim):
            lotti.append({'file': percorso, 'etichetta': etichetta,
                          'priorita': pri, 'funzioni': fs[i:i + dim]})

    lotti.sort(key=lambda L: (L['priorita'], L['file'], L['funzioni'][0]['riga']))

    for n, L in enumerate(lotti, 1):
        righe = []
        for f in L['funzioni']:
            nome = f['nome']
            pezzi = [f"### {nome}   `{f['file']}:{f['riga']}-{f['riga_fine']}`"]
            attr = []
            if f['statica']:
                attr.append('static')
            if f.get('kernel'):
                attr.append('__global__ (kernel CUDA)')
            if attr:
                pezzi.append(f"- attributi: {', '.join(attr)}")
            ch = sorted(chiamata_da.get(nome, ()))
            pezzi.append(f"- chiamata da: {', '.join(ch[:6]) if ch else 'NESSUNO'}"
                         + (f" (+{len(ch) - 6})" if len(ch) > 6 else ''))
            va = sorted(chiama.get(nome, ()))
            if va:
                pezzi.append(f"- chiama: {', '.join(va[:8])}"
                             + (f" (+{len(va) - 8})" if len(va) > 8 else ''))
            ev = sorted(env_in.get(nome, ()))
            if ev:
                pezzi.append("- legge: " + ', '.join(
                    f"{v}{' [PRESENZA]' if sem_di.get(v) == 'PRESENZA' else ''}"
                    for v in ev))
            for var, gg in guardie_in.get(nome, [])[:2]:
                pezzi.append(f"- {var} letta solo se: " + ' AND '.join(c[:60] for c in gg[:3]))
            gl = sorted(globali_in.get(nome, ()))
            if gl:
                pezzi.append(f"- scrive globali: {', '.join(gl[:6])}")
            righe.append('\n'.join(pezzi))

        testo = MANDATO.format(
            n=n, totale=len(lotti), file=L['file'], etichetta=L['etichetta'],
            quante=len(L['funzioni']),
            da=L['funzioni'][0]['riga'], a=L['funzioni'][-1]['riga_fine'],
            elenco='\n\n'.join(righe),
            uscita=f"SCHEDE_{n:03d}.tsv")
        (uscita / f'lotto_{n:03d}.md').write_text(testo, encoding='utf-8')

    print(f"  {len(lotti)} lotti scritti in {uscita}")
    for pri, (_, _, et) in enumerate(PRIORITA):
        k = sum(1 for L in lotti if L['priorita'] == pri)
        nf = sum(len(L['funzioni']) for L in lotti if L['priorita'] == pri)
        print(f"    priorita {pri}: {k:>3} lotti, {nf:>5} funzioni   {et}")
    k = sum(1 for L in lotti if L['priorita'] == len(PRIORITA))
    nf = sum(len(L['funzioni']) for L in lotti if L['priorita'] == len(PRIORITA))
    print(f"    priorita {len(PRIORITA)}: {k:>3} lotti, {nf:>5} funzioni   {RESTO[1]}")


MANDATO = """# Lotto {n} di {totale} — `{file}` righe {da}-{a}

{etichetta}

Sei uno di molti agenti. **Resta sulle tue {quante} funzioni.** Sola lettura,
tranne il tuo file di uscita.

## Il contesto, in due righe

Stiamo spremendo un runtime CUDA per MoE su una RTX 3060 12 GB con un modello da
80,76 GiB. Abbiamo il grafo delle chiamate estratto meccanicamente; **manca il
significato**. Tu lo aggiungi, in forma strutturata, per le funzioni qui sotto.

## COSA DEVI PRODURRE

Un file TSV chiamato **`{uscita}`**, in append, **una riga per funzione**, con
esattamente queste 9 colonne separate da TAB e nient'altro (niente intestazione,
niente righe vuote, niente commenti):

```
nome<TAB>categoria<TAB>ruolo<TAB>vram<TAB>frequenza<TAB>fase<TAB>invariante<TAB>trappola<TAB>certezza
```

- **nome** — esattamente come qui sotto
- **categoria** — UNA di: `allocazione` `trasporto` `routing` `attenzione` `kv`
  `quantizzazione` `telemetria` `piattaforma` `controllo` `parsing` `test` `altro`
- **ruolo** — cosa fa, **una frase, max 120 caratteri**, in italiano
- **vram** — `alloca` `libera` `misura` `scrive` `legge` `no`
- **frequenza** — quante volte gira: `per-token` `per-layer` `per-esperto`
  `per-richiesta` `avvio` `mai` `ignoto`
- **fase** — `prefill` `decode` `entrambe` `avvio` `chiusura` `ignoto`
- **invariante** — cosa DA' PER SCONTATO che, se falso, la rompe. `-` se niente.
  Max 100 caratteri.
- **trappola** — un comportamento che sorprenderebbe chi la usa (una variabile a 0
  che accende, un valore letto una volta sola in una `static`, un consumer che non
  legge cio' che scrive, un fallback muto). `-` se niente. Max 100 caratteri.
- **certezza** — `alta` se l'hai letta davvero, `media` se hai dedotto dal
  contesto, `bassa` se stai tirando a indovinare. **Non barare: una riga `bassa`
  onesta vale piu' di una `alta` inventata.**

Niente TAB dentro i campi. Niente a capo dentro i campi.

## Regole

- Se una funzione e' banale (getter, wrapper di una riga), scrivi comunque la riga:
  `categoria=altro`, `ruolo` in tre parole. **Non saltare righe.**
- Se e' sotto `#if defined(__APPLE__)`, `__HIP_PLATFORM`, o simili, mettilo nel
  ruolo: non gira sul nostro hardware.
- **Non modificare codice. Non compilare. Non committare.**

## Le tue funzioni, coi fatti gia' estratti

{elenco}
"""


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'lotti')
