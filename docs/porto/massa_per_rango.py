# -*- coding: utf-8 -*-
"""La domanda che decide se il rango serve.

L'utente ha definito la massa su cui tarare il gate SSD->RAM:

    massa = peso di gating x frequenza di bussata

Il peso vero non e' raggiungibile a costo zero (i pesi non toccano mai la CPU),
ma l'ORDINE del top-k si': il rango 0 e' l'esperto col peso piu' alto del token,
il 5 il piu' marginale. reap.cpp ne tiene ora l'istogramma grezzo.

QUESTO SCRIPT risponde a una sola domanda, e se la risposta e' "no" tutto il
lavoro sul rango va buttato:

    ordinare gli esperti per FREQUENZA e ordinarli per MASSA PESATA PER RANGO
    da' liste diverse?

Se le liste coincidono, il rango e' ridondante e basta contare le bussate.
Se differiscono, il rango porta informazione che la frequenza non ha -- ed e'
esattamente l'esperto "scelto spesso ma sempre da sesto" che il gate a sola
frequenza terrebbe in RAM per sbaglio.

Si provano piu' funzioni di peso invece di sceglierne una: quale sia la giusta
e' una domanda successiva, e dipende da quanto il risultato e' sensibile.
"""
import sys
from collections import defaultdict

PERCORSO = sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\llama_run\mappa_calore_rango.tsv'

# w(rango): tre ipotesi, deliberatamente diverse fra loro.
#   piatta      = ogni scelta vale 1  -> equivale alla sola frequenza
#   armonica    1/(r+1): il primo vale 6 volte il sesto
#   ripida      2^-r:    il primo vale 32 volte il sesto
PESI = {
    'piatta':   lambda r: 1.0,
    'armonica': lambda r: 1.0 / (r + 1.0),
    'ripida':   lambda r: 2.0 ** (-r),
}


def leggi(percorso):
    righe, intestazione, meta = [], None, []
    with open(percorso, 'r', encoding='utf-8', errors='replace') as f:
        for riga in f:
            riga = riga.rstrip('\n')
            if riga.startswith('#'):
                meta.append(riga)
                continue
            campi = riga.split('\t')
            if intestazione is None:
                intestazione = campi
                continue
            righe.append(campi)
    return meta, intestazione, righe


def main():
    meta, intestazione, righe = leggi(PERCORSO)
    n_rango = sum(1 for c in intestazione if c.startswith('rango'))
    print(f'mappa: {PERCORSO}')
    for m in meta:
        print('  ' + m)
    print(f'  righe {len(righe)}, ranghi {n_rango}')

    # (strato, esperto) -> [conteggi per rango]
    dati = {}
    for c in righe:
        strato, esperto = int(c[0]), int(c[1])
        rang = [int(x) for x in c[4:4 + n_rango]]
        dati[(strato, esperto)] = rang

    tot_sel = sum(sum(r) for r in dati.values())
    print(f'  selezioni totali {tot_sel}')

    # --- quanto e' concentrata la massa, per ciascuna funzione di peso ---
    print('\nCONCENTRAZIONE: quale frazione degli esperti porta il 90% della massa')
    classifiche = {}
    for nome, w in PESI.items():
        massa = {k: sum(c * w(i) for i, c in enumerate(v)) for k, v in dati.items()}
        ordinata = sorted(massa.items(), key=lambda kv: -kv[1])
        classifiche[nome] = [k for k, _ in ordinata]
        totale = sum(massa.values())
        acc, n90 = 0.0, 0
        for _, m in ordinata:
            acc += m
            n90 += 1
            if acc >= 0.90 * totale:
                break
        print(f'  {nome:9s}  {n90:5d} su {len(ordinata)} esperti  ({100.0*n90/len(ordinata):.1f}%)')

    # --- LA DOMANDA: le classifiche differiscono? ---
    print('\nSOVRAPPOSIZIONE fra la classifica per sola FREQUENZA (piatta) e le altre')
    print('  (quanti dei primi N coincidono: se e\' ~100% il rango non serve)')
    base = classifiche['piatta']
    for nome in ('armonica', 'ripida'):
        altra = classifiche[nome]
        print(f'  {nome}:')
        for n in (100, 500, 1000, 2000, 4000):
            if n > len(base):
                break
            comune = len(set(base[:n]) & set(altra[:n]))
            print(f'    primi {n:5d}:  {comune:5d} in comune  ({100.0*comune/n:.1f}%)')

    # --- gli esperti su cui i due criteri litigano ---
    print('\nI CASI CHE DECIDONO: esperti nei primi 1000 per frequenza ma NON per massa ripida')
    ripida = classifiche['ripida']
    dentro_freq = set(base[:1000])
    dentro_massa = set(ripida[:1000])
    solo_freq = dentro_freq - dentro_massa
    print(f'  sono {len(solo_freq)}. I primi dieci per numero di bussate:')
    for k in sorted(solo_freq, key=lambda k: -sum(dati[k]))[:10]:
        r = dati[k]
        tot = sum(r)
        print(f'    strato {k[0]:2d} esperto {k[1]:3d}  bussate {tot:5d}  '
              f'ranghi {r}  (frazione da rango 0: {100.0*r[0]/tot:.1f}%)')

    print('\n  e il contrario -- dentro per massa ma non per frequenza:')
    solo_massa = dentro_massa - dentro_freq
    for k in sorted(solo_massa, key=lambda k: -dati[k][0])[:10]:
        r = dati[k]
        tot = sum(r)
        print(f'    strato {k[0]:2d} esperto {k[1]:3d}  bussate {tot:5d}  '
              f'ranghi {r}  (frazione da rango 0: {100.0*r[0]/tot:.1f}%)')


if __name__ == '__main__':
    main()
