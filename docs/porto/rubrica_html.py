# -*- coding: utf-8 -*-
"""Metro oggettivo per l'HTML prodotto dal prompt NeuraForge.

Serve al confronto Q1 contro Q2, dove i pesi cambiano davvero e l'uscita non e'
piu' identica. NON serve ai bracci del gate: quelli producono lo stesso testo
bit per bit, ed e' la dimostrazione che il gate non tocca il calcolo.

Il metro e' CONTABILE, non di giudizio: il prompt chiede sei cose precise e o
ci sono o non ci sono. Un mio parere sulla "bellezza" non sarebbe verificabile
e non varrebbe niente in un ledger.

    python rubrica_html.py file1.resp.json [file2.resp.json ...]
"""
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser


class Conta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tag = Counter()
        self.aperti = []
        self.sbilanci = 0
        self.prof_max = 0

    def handle_starttag(self, tag, attrs):
        self.tag[tag] += 1
        if tag not in ('br', 'img', 'input', 'meta', 'link', 'hr', 'source'):
            self.aperti.append(tag)
            self.prof_max = max(self.prof_max, len(self.aperti))

    def handle_endtag(self, tag):
        if tag in self.aperti:
            while self.aperti and self.aperti.pop() != tag:
                self.sbilanci += 1
        else:
            self.sbilanci += 1


# le sei richieste del prompt, ciascuna con un riscontro cercabile
RICHIESTE = [
    ('CSS interno',      lambda t, c: c.tag.get('style', 0) >= 1),
    ('nav',              lambda t, c: c.tag.get('nav', 0) >= 1 or 'class="nav' in t),
    ('hero',             lambda t, c: re.search(r'hero', t, re.I) is not None),
    ('3 feature card',   lambda t, c: len(re.findall(r'(?:class|id)="[^"]*(?:feature|card)', t, re.I)) >= 3),
    # NON si pretende <table>: la prima versione lo faceva e segnava come
    # mancante una pagina che i tre livelli ce li aveva eccome, con una griglia
    # CSS repeat(3, 1fr) e le classi .price-tier -- cioe' markup MIGLIORE di una
    # tabella. Il rilevatore era sbagliato, non il modello. Si conta il markup:
    # il regex su class="..." non puo' agganciare i selettori CSS, che si
    # scrivono .price-tier senza virgolette.
    ('prezzi 3 tier',    lambda t, c: len(re.findall(r'(?:class|id)="[^"]*(?:tier|pricing|price|plan)', t, re.I)) >= 3),
    ('form + validaz. JS', lambda t, c: c.tag.get('form', 0) >= 1 and
                                        c.tag.get('script', 0) >= 1 and
                                        re.search(r'preventDefault|checkValidity|addEventListener', t) is not None),
    ('footer',           lambda t, c: c.tag.get('footer', 0) >= 1 or '<footer' in t.lower()),
]


def degenerazione(testo):
    """Righe non banali ripetute: e' il modo in cui i modelli a basso bit
    collassano, ed e' il criterio che la campagna usa dal 24/7."""
    righe = [r.strip() for r in testo.splitlines()]
    righe = [r for r in righe if len(r) > 24]
    if not righe:
        return 0, 0.0
    c = Counter(righe)
    piu_ripetuta = c.most_common(1)[0][1]
    duplicate = sum(v - 1 for v in c.values() if v > 1)
    return piu_ripetuta, 100.0 * duplicate / len(righe)


def analizza(percorso):
    with open(percorso, encoding='utf-8') as f:
        d = json.load(f)
    t = d['choices'][0]['message']['content']
    c = Conta()
    try:
        c.feed(t)
    except Exception:
        pass
    rip, dup = degenerazione(t)
    soddisfatte = [nome for nome, prova in RICHIESTE if prova(t, c)]
    return {
        'file': percorso.split('\\')[-1].split('/')[-1],
        'caratteri': len(t),
        'righe': t.count('\n') + 1,
        'tag': sum(c.tag.values()),
        'tag_distinti': len(c.tag),
        'profondita': c.prof_max,
        'sbilanci': c.sbilanci,
        'regole_css': t.count('{'),
        'richieste': soddisfatte,
        'rip_max': rip,
        'dup_pct': dup,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    ris = [analizza(p) for p in sys.argv[1:]]
    print(f"{'file':34s} {'car.':>7s} {'righe':>6s} {'tag':>5s} {'prof':>5s} "
          f"{'sbil':>5s} {'css{':>5s} {'req':>4s} {'rip':>4s} {'dup%':>6s}")
    for r in ris:
        print(f"{r['file'][:34]:34s} {r['caratteri']:7d} {r['righe']:6d} {r['tag']:5d} "
              f"{r['profondita']:5d} {r['sbilanci']:5d} {r['regole_css']:5d} "
              f"{len(r['richieste']):d}/{len(RICHIESTE):d} {r['rip_max']:4d} {r['dup_pct']:5.1f}%")
    print()
    print("richieste del prompt soddisfatte, per file:")
    for r in ris:
        mancano = [n for n, _ in RICHIESTE if n not in r['richieste']]
        print(f"  {r['file'][:40]:40s} " +
              (f"TUTTE" if not mancano else "manca: " + ", ".join(mancano)))
    print()
    print("Nota: 'rip' e' la riga non banale piu' ripetuta e 'dup%' la frazione di")
    print("righe duplicate: sono gli indicatori di degenerazione, il modo in cui i")
    print("modelli a basso numero di bit collassano. 'sbil' sono i tag non chiusi.")


if __name__ == '__main__':
    main()
