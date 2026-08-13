"""
IL PESO DEL ROUTER PREDICE LA PERSISTENZA?

LA DOMANDA, posta dall'utente il 12/8: un esperto scelto con peso alto viene
riscelto al token dopo piu' spesso di uno scelto con peso basso? Se si', la
politica di residenza si scrive da sola -- si tengono i pesanti e si fanno
circolare i freddi -- e NON serve indovinare il futuro: basta non buttare via
chi probabilmente torna. Essere sbagliati al 30% su una politica di residenza
costa poco; sbagliare al 30% una previsione costa banda.

PERCHE' NON E' `massa`. `massa` conta le BUSSATE (frequenza, con decadimento
>>= 1) ed e' data per perdente contro la LRU dall'archivio, insieme a LFU,
SLRU, riuso e consumato. Il peso del gate e' un'altra grandezza: dice quanto
FORTE il router l'ha scelto adesso, non quante volte l'ha scelto prima. La
cache oggi non lo riceve nemmeno: tutte le firme sono `const int32_t * ids`.

COSA LEGGE: la cartella prodotta da docs/porto/dump_peso.ps1, cioe'
  ffn_moe_topk-<strato>.<NNN>.bin        I32, gli id scelti
  ffn_moe_weights-<strato>.<NNN>.bin     F32, il peso del router
  ffn_moe_weights_norm-<strato>.<NNN>.bin F32, il peso applicato (se c'e')
  INDICE.tsv                             forma e tipo, scritti dal binario
dove <NNN> e' il passo di decode.

COSA STAMPA, in ordine di quanto conta:
  1. la persistenza di base: P(e scelto a t+1 | e scelto a t). Se e' gia' alta,
     tenere e' facile e il peso serve solo a scegliere CHI tenere.
  2. la persistenza per quintile di peso. E' la risposta alla domanda.
  3. la politica: "tengo i K piu' pesanti per strato" -- quanti dei sei del
     token dopo sono gia' li'. E' il numero che diventerebbe colpi.
"""
import sys, struct, pathlib, re
from collections import defaultdict

CART = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r'D:\ds4_work\dump_peso')

def indice():
    """nome -> (tipo, ne) letti da INDICE.tsv; se manca, si deduce dalla taglia."""
    f = CART / 'INDICE.tsv'
    if not f.exists(): return {}
    out = {}
    for r in f.read_text(encoding='utf8', errors='ignore').splitlines()[1:]:
        p = r.split('\t')
        if len(p) >= 3: out[p[0]] = (p[1], p[2])
    return out

def leggi(p, tipo):
    b = p.read_bytes()
    if tipo == 'i32': return list(struct.unpack('<%di' % (len(b)//4), b))
    return list(struct.unpack('<%df' % (len(b)//4), b))

def raccogli():
    """strato -> passo -> (ids, pesi), con K id per passo.

    ATTENZIONE AL FORMATO. `llama-eval-callback` valuta il PROMPT e non genera:
    esce un file per strato, non uno per token. Ma quel file contiene TUTTI i
    token dell'ubatch -- ne=[6,64] -- quindi le 63 transizioni consecutive per
    strato ci sono lo stesso, e per una domanda statistica sul router valgono
    quanto quelle del decode. (Per l'ORACOLO invece no: li' serve la traccia
    esatta del decode, come avverte oracolo_pista.py.)
    """
    ids  = defaultdict(dict)
    pesi = defaultdict(dict)
    rex = re.compile(r'^(ffn_moe_topk|ffn_moe_weights_norm)-(\d+)\.(\d+)\.bin$')
    K = 6
    for f in CART.glob('*.bin'):
        m = rex.match(f.name)
        if not m: continue
        nome, strato = m.group(1), int(m.group(2))
        v = leggi(f, 'i32' if nome == 'ffn_moe_topk' else 'f32')
        # ATTENZIONE ALLO STRIDE. L'INDICE dichiara ne=[6,64] ma per 40 strati su
        # 43 il file e' di 64.536 byte invece di 1536: `ffn_moe_topk` e' una
        # VISTA dei primi 6 di un argsort su tutti i 256 esperti, e ggml_nbytes
        # conta l'estensione sottostante. Il passo si ricava dalla taglia:
        #     passo = (totale - ne0) / (ne1 - 1)
        # che da' 6 sui file impacchettati e 256 sulle viste. Leggendo
        # impacchettato si prendevano numeri a caso -- e infatti la persistenza
        # usciva allo 0,1%, cioe' SOTTO il 2,3% del caso puro: il segno che il
        # dato era spazzatura, non che il segnale non c'era.
        n_tok = 64 if len(v) >= 64*6 else len(v)//K
        passo = (len(v) - K) // (n_tok - 1) if n_tok > 1 else K
        dove = ids if nome == 'ffn_moe_topk' else pesi
        for t in range(n_tok):
            i = t*passo
            if i + K <= len(v): dove[strato][t] = v[i:i+K]
    return ids, pesi

def main():
    if not CART.exists():
        print(f"  cartella non trovata: {CART}"); return 1
    ids, pesi = raccogli()
    if not ids:
        print("  nessun file ffn_moe_topk: il dump non ha prodotto niente"); return 1

    strati = sorted(ids)
    passi  = sorted(set().union(*[set(ids[s]) for s in strati]))
    print(f"  strati {len(strati)}   passi {len(passi)}   pesi presenti: {'si' if pesi else 'NO'}")

    # 1. persistenza di base
    tot = riscelti = 0
    for s in strati:
        ps = sorted(ids[s])
        for a, b in zip(ps, ps[1:]):
            A, B = set(ids[s][a]), set(ids[s][b])
            tot += len(A); riscelti += len(A & B)
    if tot == 0: print("  meno di due passi per strato: niente da confrontare"); return 1
    base = 100.0*riscelti/tot
    print(f"\n  1. PERSISTENZA DI BASE   P(riscelto a t+1 | scelto a t) = {base:.1f}%")
    print(f"     (a caso sarebbe 6/256 = 2,3%: gia' cosi' dice quanto la scelta e' inerziale)")

    if not pesi:
        print("\n  senza i pesi non si risponde alla domanda 2. Controllare il filtro del dump.")
        return 0

    # 2. persistenza per quintile di peso
    coppie = []   # (peso, riscelto)
    for s in strati:
        ps = sorted(set(ids[s]) & set(pesi[s]))
        for a, b in zip(ps, ps[1:]):
            B = set(ids[b] if False else ids[s][b])
            for e, w in zip(ids[s][a], pesi[s][a]):
                coppie.append((w, 1 if e in B else 0))
    coppie.sort()
    n = len(coppie)
    print(f"\n  2. PERSISTENZA PER QUINTILE DI PESO   ({n} osservazioni)")
    print(f"     {'quintile':<10} {'peso medio':<12} {'riscelto a t+1'}")
    for q in range(5):
        i0, i1 = q*n//5, (q+1)*n//5
        fetta = coppie[i0:i1]
        if not fetta: continue
        pm = sum(w for w, _ in fetta)/len(fetta)
        rs = 100.0*sum(r for _, r in fetta)/len(fetta)
        print(f"     {q+1:<10} {pm:<12.4f} {rs:.1f}%")
    q1 = coppie[:n//5]; q5 = coppie[4*n//5:]
    r1 = 100.0*sum(r for _, r in q1)/max(1,len(q1))
    r5 = 100.0*sum(r for _, r in q5)/max(1,len(q5))
    print(f"\n     divario fra il quintile alto e quello basso: {r5-r1:+.1f} punti")
    print(f"     ({'IL SEGNALE C E' if r5-r1 > 10 else 'segnale debole: il peso non separa'})")

    # 3. la politica: tengo i K piu' pesanti per strato
    print(f"\n  3. POLITICA 'tengo i K piu' pesanti per strato'")
    print("     K      dei 6 del token dopo, quanti sono gia' residenti")
    for K in (6, 12, 24, 48):
        tot2 = colpi2 = 0
        for s in strati:
            ps = sorted(set(ids[s]) & set(pesi[s]))
            tenuti = []
            for a, b in zip(ps, ps[1:]):
                # aggiorna il set tenuto con i piu' pesanti visti finora
                for e, w in zip(ids[s][a], pesi[s][a]):
                    tenuti = [x for x in tenuti if x[1] != e]
                    tenuti.append((w, e))
                tenuti.sort(reverse=True)
                tenuti = tenuti[:K]
                dentro = set(e for _, e in tenuti)
                for e in ids[s][b]:
                    tot2 += 1
                    if e in dentro: colpi2 += 1
        print(f"     {K:<6} {100.0*colpi2/max(1,tot2):.1f}%")
    print("\n     Da confrontare con i colpi veri della cache a 448 slot: 55,2%.")
    print("     Attenzione: qui K e' PER STRATO, la cache ha slot condivisi fra 43 strati.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
