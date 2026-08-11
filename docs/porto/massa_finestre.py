"""
MASSA = PESO x FREQUENZA IN UN INTERVALLO. Quanto copre il top-K?

Definizione dell'utente, 11/8. Il conteggio delle bussate da solo NON e' massa:
un esperto chiamato spesso con peso minuscolo pesa meno di uno chiamato di rado
con peso grosso. Il peso operativo e' `ffn_moe_weights_norm`, normalizzato a
somma 1 per token, quindi ogni token porta esattamente 1,0 di massa da spartire
fra i suoi 6 esperti scelti, su ognuno dei 43 strati con router.

E l'intervallo cambia tutto. Su UN token servono 43x6 = 258 coppie
(strato, esperto): meno dei 448 slot che teniamo. Il problema non e' la
capienza di un token, e' quanto in fretta l'insieme RUOTA. Questa e' la misura
di quella rotazione.

TRE COSE, per ogni ampiezza di finestra W:

  (1) DISTINTI      quante coppie diverse compaiono in W token consecutivi.
                    Il tetto banale e' 258*W; quanto sta sotto e' il riuso.

  (2) ORACOLO       prendendo i migliori K per massa DENTRO la finestra
                    (sapendo gia' come va a finire), quanta massa e quante
                    domande di quella finestra coprono. E' un TETTO.

  (3) PREDITTIVO    prendendo i migliori K per massa sui W token PRECEDENTI,
                    quanta massa e quante domande del token SEGUENTE coprono.
                    Questa non e' un tetto: e' una politica implementabile
                    (LFU pesata a finestra scorrevole) e si confronta
                    direttamente con la LRU che gira oggi.

INGRESSO: cartella di dump di common/debug.cpp con LLAMA_DEBUG_FILTER che
prende sia `ffn_moe_topk` sia `ffn_moe_weights`.
"""

import sys, os, re
import numpy as np

if len(sys.argv) < 2:
    print('uso: massa_finestre.py <cartella_dump> [K] [n_id] [n_esperti]')
    sys.exit(2)

SRC   = sys.argv[1]
K     = int(sys.argv[2]) if len(sys.argv) > 2 else 448
N_ID  = int(sys.argv[3]) if len(sys.argv) > 3 else 6
N_EXP = int(sys.argv[4]) if len(sys.argv) > 4 else 256
FINESTRE = (1, 2, 3, 5, 10, 20, 50, 100, 300, 1000)
p = lambda n: format(int(n), ',d').replace(',', '.')


def carica_indice(src):
    idx, forme = os.path.join(src, 'INDICE.tsv'), {}
    if not os.path.exists(idx):
        return forme
    with open(idx, 'r', encoding='utf-8', errors='replace') as f:
        intest = f.readline().rstrip('\n').split('\t')
        col = {n: i for i, n in enumerate(intest)}
        for riga in f:
            c = riga.rstrip('\n').split('\t')
            if len(c) >= len(intest):
                ne0, ne1, ne2 = int(c[col['ne0']]), int(c[col['ne1']]), int(c[col['ne2']])
                # i pesi escono come [1, n_expert_used, n_token]: si appiattisce
                # la prima dimensione, la memoria e' la stessa
                if ne0 == 1 and ne1 == N_ID:
                    ne0, ne1 = ne1, ne2
                forme[c[col['file']]] = (ne0, ne1, int(c[col['byte']]))
    return forme


def leggi(path, forma, dtype):
    """[n_token, N_ID] saltando il passo quando il tensore e' una VISTA.
    `ffn_moe_topk` lo e' (dei primi 6 di ogni riga di argsort, che ne ha 256):
    ggml_nbytes misura l'estensione, non il contenuto."""
    a = np.fromfile(path, dtype=dtype)
    if forma is None:
        return (a.reshape(-1, N_ID), None) if a.size % N_ID == 0 else (None, None)
    ne0, ne1, byte = forma
    if ne0 != N_ID:
        return None, None
    if ne1 == 1 or byte == ne0 * ne1 * 4:
        return a[:ne0 * ne1].reshape(ne1, ne0), None
    resto = byte - ne0 * 4
    if resto % ((ne1 - 1) * 4):
        return None, None
    passo = resto // ((ne1 - 1) * 4)
    piena = a[:(ne1 - 1) * passo].reshape(ne1 - 1, passo)
    out = np.empty((ne1, N_ID), dtype=dtype)
    out[:ne1 - 1] = piena[:, :N_ID]
    out[ne1 - 1] = a[(ne1 - 1) * passo:(ne1 - 1) * passo + N_ID]
    return out, (piena[0] if passo == N_EXP else None)


def raccogli(prefisso, dtype):
    rx = re.compile(r'^' + prefisso + r'-(\d+)\.(\d+)\.bin$')
    per_strato, campione = {}, None
    for nome in os.listdir(SRC):
        m = rx.match(nome)
        if m:
            per_strato.setdefault(int(m.group(1)), []).append((int(m.group(2)), os.path.join(SRC, nome)))
    if not per_strato:
        return None, None, None
    strati, tracce = sorted(per_strato), {}
    for L in strati:
        pezzi = []
        for _, path in sorted(per_strato[L]):
            v, riga = leggi(path, FORME.get(os.path.basename(path)), dtype)
            if v is None:
                print('  !! %s: passo non deducibile (forma %s)' % (path, FORME.get(os.path.basename(path))))
                sys.exit(1)
            if campione is None and riga is not None:
                campione = riga
            pezzi.append(v)
        tracce[L] = np.concatenate(pezzi, axis=0)
    return strati, tracce, campione


FORME = carica_indice(SRC)
strati, topk, campione = raccogli('ffn_moe_topk', np.int32)
if strati is None:
    print('nessun ffn_moe_topk-*.bin in %s' % SRC)
    sys.exit(1)

# il peso: si prende la variante piu' a valle presente (norm > scaled > grezzo),
# perche' e' quella che moltiplica davvero l'uscita dell'esperto
pesi = None
for nome in ('ffn_moe_weights_norm', 'ffn_moe_weights_scaled', 'ffn_moe_weights_softmax', 'ffn_moe_weights'):
    st_w, tr_w, _ = raccogli(nome, np.float32)
    if st_w is not None:
        pesi, nome_pesi = tr_w, nome
        break
if pesi is None:
    print('nessun ffn_moe_weights*-*.bin: rilancia il dump con il filtro giusto')
    sys.exit(1)

n_tok = min(min(t.shape[0] for t in topk.values()), min(t.shape[0] for t in pesi.values()))
print('strati con router : %d   posizioni: %s   peso letto da: %s' % (len(strati), p(n_tok), nome_pesi))

# --- CANCELLI -------------------------------------------------------------
ok_perm = campione is None or bool(np.array_equal(np.sort(campione), np.arange(N_EXP)))
W0 = np.stack([pesi[L][:n_tok] for L in strati], axis=1)          # [t, L, k]
E0 = np.stack([topk[L][:n_tok] for L in strati], axis=1)
somme = W0.sum(axis=2)
ok_somma = bool(np.allclose(somme, somme.mean(), rtol=0.02))
print('  la riga intera e\' una permutazione di 0..%-4d      %s' % (N_EXP - 1, 'OK' if ok_perm else '*** FALLITO ***'))
print('  il peso per token somma a una costante (%.4f)      %s' % (somme.mean(), 'OK' if ok_somma else '*** FALLITO ***'))
print('  id nel range [0,%d]                               %s'
      % (N_EXP - 1, 'OK' if bool(((E0 >= 0) & (E0 < N_EXP)).all()) else '*** FALLITO ***'))
if not ok_perm:
    sys.exit(1)

# coppia globale (strato, esperto) -> un intero; e' l'unita' di residenza
G = (np.arange(len(strati))[None, :, None] * N_EXP + E0).reshape(n_tok, -1)   # [t, 258]
P = (W0 / somme[:, :, None]).reshape(n_tok, -1)                               # massa per domanda
N_COPPIE = len(strati) * N_EXP
DOM_TOK = G.shape[1]
print('  domande per token : %d   coppie possibili: %s   K in prova: %s'
      % (DOM_TOK, p(N_COPPIE), p(K)))

print()
print('=' * 74)
print('  W = ampiezza della finestra, in token.  K = %s slot.' % p(K))
print('=' * 74)
print('   W   distinti   /258W    ORACOLO sulla finestra    PREDITTIVO sul token dopo')
print('                          massa      domande         massa      domande')

for W in FINESTRE:
    if W > n_tok:
        break
    # (1)+(2): finestre non sovrapposte, per non contare due volte lo stesso tratto
    dist, mass_or, dom_or, n = 0.0, 0.0, 0.0, 0
    for a in range(0, n_tok - W + 1, max(1, W)):
        g, w = G[a:a + W].ravel(), P[a:a + W].ravel()
        acc = np.bincount(g, weights=w, minlength=N_COPPIE)
        cnt = np.bincount(g, minlength=N_COPPIE)
        d = int((cnt > 0).sum())
        dist += d
        if d <= K:
            mass_or += 1.0; dom_or += 1.0
        else:
            top = np.argpartition(-acc, K)[:K]
            mass_or += acc[top].sum() / acc.sum()
            dom_or  += cnt[top].sum() / cnt.sum()
        n += 1
    # (3): la finestra scorre, e si giudica sul token SUCCESSIVO
    mass_pr, dom_pr, m = 0.0, 0.0, 0
    passo = max(1, (n_tok - W) // 400)          # ~400 campioni: basta e avanza
    for a in range(0, n_tok - W, passo):
        g, w = G[a:a + W].ravel(), P[a:a + W].ravel()
        acc = np.bincount(g, weights=w, minlength=N_COPPIE)
        vivi = int((acc > 0).sum())
        tenuti = np.flatnonzero(acc) if vivi <= K else np.argpartition(-acc, K)[:K]
        residente = np.zeros(N_COPPIE, dtype=bool)
        residente[tenuti] = True
        colpito = residente[G[a + W]]
        mass_pr += P[a + W][colpito].sum() / P[a + W].sum()
        dom_pr  += colpito.mean()
        m += 1
    print('%4d %9s   %5.1f%%      %6.1f%%     %6.1f%%        %6.1f%%     %6.1f%%'
          % (W, p(dist / n), 100.0 * (dist / n) / (DOM_TOK * W),
             100.0 * mass_or / n, 100.0 * dom_or / n,
             100.0 * mass_pr / m, 100.0 * dom_pr / m))

print()
print('  ORACOLO   = i migliori K della finestra, scelti sapendo gia\' la finestra. TETTO.')
print('  PREDITTIVO= i migliori K dei W token precedenti, giudicati sul token dopo.')
print('              e\' una politica vera, e si confronta con la LRU di oggi:')
print('              53,6%% a 339 slot | 59,4%% a 448 | 63,8%% a 480 (domande, non massa)')
