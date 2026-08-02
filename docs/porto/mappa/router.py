#!/usr/bin/env python3
"""Come ragiona il modello: analisi del tracciato delle scelte del router.

Legge le righe `[route-ids] token=N layer=L ids=a,b,c,d,e,f` e risponde alle
domande che finora abbiamo indovinato:

  - quanti esperti distinti servono davvero a un token
  - quanto si ripetono fra token consecutivi  (il tetto di QUALUNQUE residenza)
  - se la scelta di uno strato predice quella del successivo
  - e soprattutto: con N slot, quanto puo' fare una politica che VEDE IL FUTURO
    (Belady) contro la LRU che usiamo oggi

L'ultima e' quella che decide: se Belady e LRU sono vicine, il problema e' la
capienza e nessuna politica ci salva; se sono lontane, il problema e' la politica.

Uso:  python router.py <log> [slot]
"""
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

RIGA = re.compile(r'\[route-ids\] token=(\d+) layer=(\d+) ids=([\d,\-]+)')


def leggi(percorso):
    """Restituisce [(token, layer, (id, ...)), ...] nell'ordine di esecuzione."""
    eventi = []
    with open(percorso, encoding='utf-8', errors='replace') as fh:
        for riga in fh:
            m = RIGA.search(riga)
            if not m:
                continue
            tok, lay = int(m.group(1)), int(m.group(2))
            ids = tuple(int(x) for x in m.group(3).split(',') if x != '')
            eventi.append((tok, lay, ids))
    return eventi


def separa_fasi(eventi):
    """Divide il tracciato in prefill e decode guardando la FORMA, non le etichette.

    In prefill n_tokens>1: il ciclo stampa tutti i token dello strato 0, poi
    tutti quelli dello strato 1. Righe consecutive hanno lo STESSO strato.
    In decode n_tokens=1: un token attraversa i 43 strati, quindi righe
    consecutive hanno strati CRESCENTI e lo stesso token.

    Serve anche perche' `log_token_pos` avanza di uno per CHUNK e non per token
    (vram_expert_cache.cpp:498): in prefill le etichette si sovrappongono fra
    chunk. Qui l'identita' del token la ricostruiamo, non la leggiamo.
    """
    if not eventi:
        return [], []
    prefill, decode = [], []
    i, n = 0, len(eventi)
    while i < n:
        tok, lay, ids = eventi[i]
        stesso_strato = (i + 1 < n and eventi[i + 1][1] == lay)
        (prefill if stesso_strato else decode).append(eventi[i])
        i += 1
    # la riga di confine finisce nel gruppo sbagliato: la lasciamo, e' una su 25000
    return prefill, decode


def per_token_decode(decode):
    """Raggruppa il decode in token veri: un gruppo per ogni passaggio 0..42."""
    gruppi, corrente, ultimo = [], [], None
    for tok, lay, ids in decode:
        if ultimo is not None and lay <= ultimo:
            gruppi.append(corrente)
            corrente = []
        corrente.append((lay, ids))
        ultimo = lay
    if corrente:
        gruppi.append(corrente)
    return gruppi


def belady(accessi, capienza):
    """Tasso di successo con sostituzione ottima (sfratta l'uso piu' lontano).

    accessi: sequenza di chiavi. Restituisce (colpi, mancati).
    """
    prossimo = defaultdict(deque)
    for i, k in enumerate(accessi):
        prossimo[k].append(i)

    cache = set()
    colpi = mancati = 0
    for i, k in enumerate(accessi):
        prossimo[k].popleft()
        if k in cache:
            colpi += 1
            continue
        mancati += 1
        if len(cache) >= capienza:
            # sfratta quello il cui prossimo uso e' piu' lontano
            peggiore, quando = None, -1
            for c in cache:
                p = prossimo[c][0] if prossimo[c] else float('inf')
                if p > quando:
                    peggiore, quando = c, p
                    if p == float('inf'):
                        break
            cache.discard(peggiore)
        cache.add(k)
    return colpi, mancati


def fifo(accessi, capienza):
    from collections import OrderedDict
    cache, colpi, mancati = OrderedDict(), 0, 0
    for k in accessi:
        if k in cache:
            colpi += 1
            continue
        mancati += 1
        if len(cache) >= capienza:
            cache.popitem(last=False)
        cache[k] = True
    return colpi, mancati


def casuale(accessi, capienza, seme=12345):
    """Sostituzione casuale. Su schema ciclico batte la LRU, che va a zero."""
    stato = seme
    cache, lista = set(), []
    colpi = mancati = 0
    for k in accessi:
        if k in cache:
            colpi += 1
            continue
        mancati += 1
        if len(cache) >= capienza:
            stato = (1103515245 * stato + 12345) & 0x7fffffff
            j = stato % len(lista)
            cache.discard(lista[j])
            lista[j] = k
        else:
            lista.append(k)
        cache.add(k)
    return colpi, mancati


def bussate(accessi, capienza, soglia=3, decadimento=0, isteresi=1.25):
    """Mask APERTA con costo d'ingresso: entri dopo `soglia` bussate.

    Non e' una potatura: nessuno e' escluso per sempre. Chi non e' residente
    accumula bussate a ogni richiesta, e alla soglia entra sfrattando il
    residente meno caldo. Il costo d'ingresso governa le RILETTURE -- che sul
    nostro tracciato sono il 90,3% degli accessi.

    `decadimento`: ogni quanti accessi dimezzare i contatori delle bussate, per
    non far entrare chi ha bussato tanto ma molto tempo fa. 0 = mai.
    """
    from collections import OrderedDict
    residenti = OrderedDict()          # chiave -> punteggio da residente
    knock = Counter()
    colpi = mancati = ammessi = 0
    for i, k in enumerate(accessi):
        # L'OROLOGIO (DS4_EXPERT_TIER_CLOCK_CALLS): invecchia i punteggi dei
        # residenti. Senza, il vantaggio di chi e' entrato per primo cresce
        # all'infinito e la cache si congela dopo il primo riempimento.
        if decadimento and i and i % decadimento == 0:
            for x in list(residenti):
                residenti[x] = residenti[x] * 3 // 4
            for x in list(knock):
                knock[x] = knock[x] * 3 // 4
                if not knock[x]:
                    del knock[x]
        if k in residenti:
            colpi += 1
            residenti[k] += 1
            continue
        mancati += 1
        knock[k] += 1
        if knock[k] < soglia:
            continue                   # ha bussato, ma non abbastanza
        # Il candidato entra col credito delle bussate che si e' guadagnato:
        # senza questo un nuovo ammesso vale 1 ed e' la prima vittima della
        # ammissione successiva -- muore prima di poter dimostrare qualcosa.
        credito = knock[k]
        if len(residenti) >= capienza:
            vittima = min(residenti, key=lambda x: residenti[x])
            # ISTERESI: il candidato deve battere la vittima di un margine,
            # altrimenti non vale la pena scambiare. Senza, la cache oscilla.
            if residenti[vittima] * isteresi > credito:
                continue               # respinto, ma TIENE le bussate e insiste
            del residenti[vittima]
        residenti[k] = credito
        ammessi += 1
        del knock[k]
    return colpi, mancati, ammessi


def lfu_oracolo(accessi, capienza):
    """Tiene fissi i `capienza` esperti piu' frequenti dell'INTERO tracciato.

    E' un oracolo di frequenza, non implementabile cosi' com'e' -- ma dice
    quanto varrebbe un insieme caldo STATICO, che invece e' implementabile
    misurando su un campione e pinnando.
    """
    freq = Counter(accessi)
    caldi = {k for k, _ in freq.most_common(capienza)}
    colpi = sum(1 for k in accessi if k in caldi)
    return colpi, len(accessi) - colpi


def lfru(accessi, capienza, quota_calda=0.5):
    """Approssimazione della nostra mass-LFRU: meta' cache protetta per frequenza,
    meta' gestita a LRU. Serve a spiegare il ~10% che il runtime misura davvero.
    """
    from collections import OrderedDict
    n_caldi = int(capienza * quota_calda)
    conteggi = Counter()
    protetti, lru_parte = OrderedDict(), OrderedDict()
    colpi = mancati = 0
    for k in accessi:
        conteggi[k] += 1
        if k in protetti:
            colpi += 1
            continue
        if k in lru_parte:
            colpi += 1
            lru_parte.move_to_end(k)
            # promuove se e' diventato piu' caldo del piu' freddo dei protetti
            if len(protetti) < n_caldi:
                del lru_parte[k]
                protetti[k] = True
            else:
                freddo = min(protetti, key=lambda x: conteggi[x])
                if conteggi[k] > conteggi[freddo]:
                    del protetti[freddo]
                    del lru_parte[k]
                    protetti[k] = True
                    lru_parte[freddo] = True
            continue
        mancati += 1
        if len(protetti) + len(lru_parte) >= capienza:
            if lru_parte:
                lru_parte.popitem(last=False)
            else:
                protetti.popitem(last=False)
        lru_parte[k] = True
    return colpi, mancati


def lru(accessi, capienza):
    from collections import OrderedDict
    cache = OrderedDict()
    colpi = mancati = 0
    for k in accessi:
        if k in cache:
            cache.move_to_end(k)
            colpi += 1
            continue
        mancati += 1
        if len(cache) >= capienza:
            cache.popitem(last=False)
        cache[k] = True
    return colpi, mancati


def analizza(percorso, slot=181):
    eventi = leggi(percorso)
    if not eventi:
        print("  nessuna riga [route-ids] nel log")
        return

    n_strati = max(e[1] for e in eventi) + 1
    prefill, decode = separa_fasi(eventi)
    gruppi = per_token_decode(decode)
    # scartiamo il primo e l'ultimo gruppo: possono essere tronchi al confine
    gruppi = [g for g in gruppi if len(g) >= n_strati - 2][1:-1] or gruppi

    print(f"  righe di tracciato   {len(eventi)}   strati {n_strati}")
    print(f"  di cui prefill       {len(prefill)}")
    print(f"  di cui decode        {len(decode)}  ->  {len(gruppi)} token interi")
    print(f"  esperti per scelta   {len(eventi[0][2])}")
    if not gruppi:
        print("\n  NESSUN token di decode completo: run troppo corto o solo prefill")
        return

    # da qui in poi si analizza SOLO il decode: e' li' che siamo lenti,
    # e ha una struttura di accesso completamente diversa dal prefill
    per_token = {i: g for i, g in enumerate(gruppi)}
    token = sorted(per_token)

    # --- quanti esperti distinti serve un token
    distinti = [len({(l, i) for l, ids in per_token[t] for i in ids})
                for t in token]
    med = sorted(distinti)[len(distinti) // 2]
    print(f"\n  ESPERTI DISTINTI PER TOKEN   mediana {med}   "
          f"min {min(distinti)}   max {max(distinti)}")

    # --- riuso fra token consecutivi: il tetto di qualunque residenza
    insiemi = [{(l, i) for l, ids in per_token[t] for i in ids} for t in token]
    jac, nuovi = [], []
    for a, b in zip(insiemi, insiemi[1:]):
        u = len(a | b)
        jac.append(len(a & b) / u if u else 0.0)
        nuovi.append(len(b - a))
    if jac:
        jm = sorted(jac)[len(jac) // 2]
        nm = sorted(nuovi)[len(nuovi) // 2]
        print(f"  RIUSO fra token consecutivi  Jaccard mediano {jm:.3f}")
        print(f"    -> esperti NUOVI a ogni token, mediana {nm} su {med}")
        print(f"    -> con residenza perfetta si evita il "
              f"{100.0 * (1 - nm / med):.1f}% dei caricamenti")

    # --- concentrazione: pochi esperti fanno tanto lavoro?
    freq = Counter((l, i) for g in gruppi for l, ids in g for i in ids)
    tot = sum(freq.values())
    ordinati = [c for _, c in freq.most_common()]
    print(f"\n  ESPERTI DISTINTI VISTI       {len(freq)}")
    for q in (slot, 320, 512, 1024):
        if q <= len(ordinati):
            massa = 100.0 * sum(ordinati[:q]) / tot
            print(f"    i {q:>4} piu' caldi coprono il {massa:5.1f}% degli accessi")

    # --- la curva dell'insieme di lavoro
    print("\n  INSIEME DI LAVORO su finestra di token")
    for w in (1, 4, 16, 64, 256):
        if w > len(insiemi):
            continue
        campioni = [len(set().union(*insiemi[i:i + w]))
                    for i in range(0, max(1, len(insiemi) - w), max(1, w // 2))]
        if campioni:
            m = sorted(campioni)[len(campioni) // 2]
            print(f"    {w:>4} token -> {m:>5} esperti distinti (mediana)")

    # --- IL CONFRONTO CHE DECIDE
    accessi = [(l, i) for g in gruppi for l, ids in g for i in ids]
    print(f"\n  POLITICHE su {len(accessi)} accessi, {slot} slot")
    for nome, fn in (('LRU  (cio\' che usiamo)', lru),
                     ('FIFO', fifo),
                     ('casuale', casuale),
                     ('LFRU ~ la nostra', lfru),
                     ('insieme caldo statico', lfu_oracolo),
                     ('Belady (vede il futuro)', belady)):
        c, m = fn(accessi, slot)
        print(f"    {nome:<24} colpi {100.0 * c / (c + m):5.1f}%")
    obbl = len(freq)
    print(f"    {'obbligati (cache infinita)':<24} colpi "
          f"{100.0 * (len(accessi) - obbl) / len(accessi):5.1f}%")

    # --- quanto renderebbe piu' capienza
    print(f"\n  SE AVESSIMO PIU' SLOT (Belady)")
    for q in (181, 274, 320, 512, 1024):
        if q > len(freq):
            break
        c, m = belady(accessi, q)
        print(f"    {q:>5} slot -> {100.0 * c / (c + m):5.1f}%")


if __name__ == '__main__':
    analizza(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 181)
