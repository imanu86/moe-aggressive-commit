"""
LRU CONTRO LRU+PESO, sulla traccia vera, a parita' di slot.

LA DOMANDA. La misura del 12/8 dice che il peso del router predice la
persistenza in modo forte: 27,3% di riselezione nel quintile leggero contro
67,5% nel pesante, +40,2 punti. Ma la politica "tengo i K piu' pesanti" da sola
PERDE contro la LRU a parita' di capienza (37,5% con 516 slot contro il 55,2%
misurato con 448). Il motivo e' che la LRU cattura gia' l'inerzia -- la
persistenza di base e' 42,8% contro il 2,3% del caso -- piu' la recency su piu'
token, mentre "tengo i pesanti" butta chi e' stato usato due token fa per
tenere chi fu pesante dieci token fa.

Quindi il peso non e' un rimpiazzo della LRU: e' l'informazione che le manca.
La LRU sa QUANDO, il peso sa QUANTO FORTE. Questo script misura se combinarli
paga, sulla stessa traccia e a parita' di slot, senza toccare il codice.

LA FAMIGLIA A UN PARAMETRO:
    punteggio(slot) = ultimo_uso + bonus * peso
con `ultimo_uso` in unita' di domanda (il contatore globale) e `peso` in [0,1].
    bonus = 0        -> LRU pura
    bonus -> grande  -> peso puro
Un bonus di B significa: essere pesante 1,0 vale quanto essere stato usato B
domande piu' tardi. E' il "termometro" con isteresi implicita -- un esperto che
si raffredda di colpo conserva il bonus finche' non scade per anzianita'.

BELADY e' calcolato come tetto: sfratta chi servira' piu' tardi. Non e'
implementabile (richiede il futuro) ma dice quanto margine resta.

ORDINE DELLA DOMANDA, che e' quello vero: per ogni token, gli strati 0..42 in
ordine, sei esperti per strato. La distanza di riuso di un esperto e' quindi
~258 domande, ed e' per questo che con 448 slot si sta al 55%.
"""
import sys, struct, pathlib, re
from collections import defaultdict

CART = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\dump_peso')
K = 6

def leggi(p, tipo):
    b = p.read_bytes()
    return list(struct.unpack('<%d%s' % (len(b)//4, 'i' if tipo == 'i32' else 'f'), b))

def traccia():
    ids, pesi = defaultdict(dict), defaultdict(dict)
    rex = re.compile(r'^(ffn_moe_topk|ffn_moe_weights_norm)-(\d+)\.(\d+)\.bin$')
    for f in CART.glob('*.bin'):
        m = rex.match(f.name)
        if not m: continue
        nome, strato = m.group(1), int(m.group(2))
        v = leggi(f, 'i32' if nome == 'ffn_moe_topk' else 'f32')
        n_tok = 64 if len(v) >= 64*K else len(v)//K
        passo = (len(v) - K) // (n_tok - 1) if n_tok > 1 else K
        dove = ids if nome == 'ffn_moe_topk' else pesi
        for t in range(n_tok):
            i = t*passo
            if i + K <= len(v): dove[strato][t] = v[i:i+K]
    strati = sorted(ids)
    n_tok = min(len(ids[s]) for s in strati)
    dom = []                      # (chiave, peso) nell'ordine vero
    for t in range(n_tok):
        for s in strati:
            if t not in ids[s] or t not in pesi[s]: continue
            for e, w in zip(ids[s][t], pesi[s][t]):
                dom.append(((s << 16) | e, w))
    return dom, len(strati), n_tok

def simula(dom, n_slot, bonus):
    """LRU generalizzata: vittima = min(ultimo_uso + bonus*peso)."""
    ultimo, peso_di = {}, {}      # chiave -> istante / peso all'ultimo uso
    colpi = 0
    for i, (k, w) in enumerate(dom):
        if k in ultimo:
            colpi += 1
        elif len(ultimo) >= n_slot:
            vittima = min(ultimo, key=lambda x: ultimo[x] + bonus*peso_di[x])
            del ultimo[vittima]; del peso_di[vittima]
        ultimo[k] = i; peso_di[k] = w
    return 100.0*colpi/len(dom)

def belady(dom, n_slot):
    prossimo = defaultdict(list)
    for i, (k, _) in enumerate(dom): prossimo[k].append(i)
    pos = {k: 0 for k in prossimo}
    dentro, colpi = set(), 0
    for i, (k, _) in enumerate(dom):
        pos[k] += 1
        if k in dentro: colpi += 1
        else:
            if len(dentro) >= n_slot:
                def quando(x):
                    p = prossimo[x]; j = pos[x]
                    return p[j] if j < len(p) else 1 << 30
                dentro.discard(max(dentro, key=quando))
            dentro.add(k)
    return 100.0*colpi/len(dom)

def main():
    dom, n_strati, n_tok = traccia()
    if not dom: print("  traccia vuota"); return 1
    print(f"  traccia: {len(dom)} domande  ({n_tok} token x {n_strati} strati x {K} esperti)")
    print(f"  chiavi distinte: {len(set(k for k,_ in dom))}\n")
    print(f"  {'slot':<7} {'LRU':<9} {'+peso (bonus migliore)':<26} {'guadagno':<10} {'Belady'}")
    for n_slot in (256, 339, 448, 512, 768):
        base = simula(dom, n_slot, 0.0)
        migliore, b_migliore = base, 0.0
        for b in (5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560):
            r = simula(dom, n_slot, float(b))
            if r > migliore: migliore, b_migliore = r, float(b)
        bel = belady(dom, n_slot)
        print(f"  {n_slot:<7} {base:<9.1f} {migliore:.1f}  (bonus {b_migliore:.0f})".ljust(45)
              + f"{migliore-base:+.1f}".ljust(11) + f"{bel:.1f}")
    print("\n  Il bonus e' in unita' di domanda: bonus B vuol dire che pesare 1,0")
    print("  vale quanto essere stato usato B domande piu' tardi. Un token intero")
    print(f"  e' {n_strati*K} domande, quindi B={n_strati*K} = 'un token di vantaggio'.")
    print("\n  ATTENZIONE: la traccia e' di PREFILL (64 token del prompt) e corta.")
    print("  Serve a decidere SE vale la pena, non a tarare il parametro.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
