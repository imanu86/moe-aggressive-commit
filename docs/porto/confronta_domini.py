# -*- coding: utf-8 -*-
"""Il nucleo stabile e il churn: i due parametri del gate SSD->RAM.

Dalle mappe per rango di piu' domini ricava le tre quantita' che dimensionano
la politica di ammissione dell'utente:

    NUCLEO      esperti nel 90% della massa in TUTTI i domini
                -> possono restare residenti sempre, non serve deciderli

    UNIONE      esperti nel 90% della massa in ALMENO UN dominio
                -> il tetto di RAM se non si sfratta mai nulla

    CHURN       quanti esperti entrano/escono passando da un dominio all'altro
                -> il lavoro che il gate deve reggere, cioe' la costante di
                   tempo dell'ammissione. Se il churn e' piccolo il gate puo'
                   essere lento e prudente; se e' grande dev'essere reattivo.

Nessuno dei due esiti fa cadere il disegno: cambia quanto lavoro deve fare.

    python confronta_domini.py mappa1.tsv mappa2.tsv [...]
"""
import os
import sys

MB_PER_ESPERTO = (528 + 528 + 672) / 256.0   # dai tensori visti in GGML_SCHED_DEBUG

PESI = {
    'piatta': lambda r: 1.0,          # = sola frequenza
    'ripida': lambda r: 2.0 ** (-r),  # il primo vale 32 volte il sesto
}
COPERTURA = 0.90


def leggi(percorso):
    """-> (nome, {(strato, esperto): [conteggi per rango]})"""
    dati, intestazione = {}, None
    with open(percorso, 'r', encoding='utf-8', errors='replace') as f:
        for riga in f:
            riga = riga.rstrip('\n')
            if riga.startswith('#') or not riga:
                continue
            campi = riga.split('\t')
            if intestazione is None:
                intestazione = campi
                continue
            n_rango = sum(1 for c in intestazione if c.startswith('rango'))
            dati[(int(campi[0]), int(campi[1]))] = [int(x) for x in campi[4:4 + n_rango]]
    nome = os.path.basename(percorso).replace('mappa_calore_rango_', '').replace('.tsv', '')
    return nome, dati


def insieme_coperto(dati, w):
    """Gli esperti che coprono COPERTURA della massa, ordinati per massa."""
    massa = {k: sum(c * w(i) for i, c in enumerate(v)) for k, v in dati.items()}
    ordinata = sorted(massa.items(), key=lambda kv: -kv[1])
    totale = sum(massa.values())
    acc, dentro = 0.0, []
    for k, m in ordinata:
        acc += m
        dentro.append(k)
        if acc >= COPERTURA * totale:
            break
    return dentro


def gb(n):
    return n * MB_PER_ESPERTO / 1024.0


def main():
    percorsi = sys.argv[1:]
    if len(percorsi) < 2:
        print('servono almeno due mappe'); return

    mappe = []
    for p in percorsi:
        if not os.path.exists(p):
            print(f'  MANCA: {p}'); continue
        mappe.append(leggi(p))
    if len(mappe) < 2:
        print('mappe insufficienti'); return

    print('MAPPE')
    for nome, d in mappe:
        sel = sum(sum(v) for v in d.values())
        print(f'  {nome:24s}  {len(d):5d} esperti toccati   {sel:8d} selezioni')

    for nome_peso, w in PESI.items():
        print(f'\n{"="*70}\nPESO: {nome_peso}   (copertura {COPERTURA:.0%} della massa)')
        insiemi = {nome: set(insieme_coperto(d, w)) for nome, d in mappe}

        print('\n  per dominio:')
        for nome, s in insiemi.items():
            print(f'    {nome:24s}  {len(s):5d} esperti   {gb(len(s)):5.1f} GB')

        nucleo = set.intersection(*insiemi.values())
        unione = set.union(*insiemi.values())
        print(f'\n    NUCLEO (in tutti)   {len(nucleo):5d} esperti   {gb(len(nucleo)):5.1f} GB'
              f'   = {100.0*len(nucleo)/len(unione):.0f}% dell unione')
        print(f'    UNIONE (in almeno uno) {len(unione):5d} esperti   {gb(len(unione)):5.1f} GB')

        print('\n  sovrapposizione a coppie (Jaccard, e churn passando da A a B):')
        nomi = list(insiemi)
        for i in range(len(nomi)):
            for j in range(i + 1, len(nomi)):
                a, b = insiemi[nomi[i]], insiemi[nomi[j]]
                jac = len(a & b) / float(len(a | b))
                entrano = len(b - a)
                escono  = len(a - b)
                print(f'    {nomi[i]:12s} <-> {nomi[j]:12s}  jaccard {jac:.2f}   '
                      f'entrano {entrano:4d} ({gb(entrano):4.1f} GB)  escono {escono:4d}')

        # quanto costa il churn in tempo di caricamento da SSD
        peggiore = 0
        for i in range(len(nomi)):
            for j in range(len(nomi)):
                if i != j:
                    peggiore = max(peggiore, len(insiemi[nomi[j]] - insiemi[nomi[i]]))
        # 41,6 ms/GB e' il costo misurato del trasporto dalla RAM il 3/8;
        # da SSD e' piu' lento, ma serve l'ordine di grandezza
        print(f'\n    churn peggiore fra due domini: {peggiore} esperti = {gb(peggiore):.1f} GB')
        print(f'    a 1 GB/s da SSD sono ~{gb(peggiore):.0f} s di caricamento se fatto tutto in una volta')


if __name__ == '__main__':
    main()
