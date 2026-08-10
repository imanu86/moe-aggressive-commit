"""
CANTIERE TESTA — passo 0: estrarre le coppie (stato h_L(t), id(t+1)) dalle
tracce GIA' esistenti, e passare il cancello di allineamento PRIMA di
addestrare qualunque cosa.

Perche' cosi': la validazione "su un MoE piccolo" del piano non e' eseguibile
(reap-loop non e' piu' nel repo). La sostituiamo con una validazione su POCHI
dati del modello VERO, che ha lo stesso scopo — scoprire i buchi di
allineamento — senza aggiungere il rischio di transfer fra modelli.

DUE LEZIONI GIA' PAGATE, rispettate qui:
  - gli id si leggono dal LOG dell'eval-callback, MAI ritokenizzando il testo
    (eval-callback normalizza i CRLF, llama-tokenize legge raw: 2 token extra
    per coppia \\r\\n);
  - i pezzi si concatenano NELL'ORDINE DELL'INDICE, non in ordine di nome file.

IL CANCELLO: n_stati deve combaciare ESATTAMENTE con n_token del log. Se non
combacia, tutto il resto e' spazzatura plausibile e ci si ferma qui.
"""

import io, os, re, sys
import numpy as np

TRACCE = {
    'codice': (r'D:\ds4_work\dump',       r'D:\ds4_work\llama_run\testa_ridump_log.txt'),
    'prosa':  (r'D:\ds4_work\dump_prosa', r'D:\ds4_work\llama_run\evalcb_prosa_log.txt'),
}
STRATO = 42          # l'ultimo: lo stato piu' vicino alla lm_head
N_EMBD = 4096


def id_dal_log(path):
    """Gli id stanno uno per riga DOPO 'number of input tokens = N'."""
    righe = io.open(path, encoding='utf-8', errors='replace').read().split('\n')
    inizio, atteso = None, None
    for i, r in enumerate(righe):
        m = re.search(r'number of input tokens\s*=\s*(\d+)', r)
        if m:
            inizio, atteso = i + 1, int(m.group(1))
            break
    if inizio is None:
        raise SystemExit('log senza "number of input tokens": ' + path)
    ids = []
    for r in righe[inizio:]:
        m = re.match(r'^\s*\S+\s+I\s+(\d+)\s*$', r)   # "<clock> I   <id>"
        if not m:
            if ids:
                break
            continue
        ids.append(int(m.group(1)))
    return np.array(ids, dtype=np.int64), atteso


def stati_dall_indice(dump, strato):
    """Concatena i pezzi NELL'ORDINE DELL'INDICE (non per nome file)."""
    idx = io.open(os.path.join(dump, 'INDICE.tsv'), encoding='utf-8').read().strip().split('\n')
    nome = 'ffn_norm-%d' % strato
    pezzi = []
    for riga in idx[1:]:
        c = riga.split('\t')
        if c[1] != nome:
            continue
        ne0, ne1, nbyte = int(c[4]), int(c[5]), int(c[8])
        assert ne0 == N_EMBD, 'ne0 inatteso: %d' % ne0
        n_tok = nbyte // (4 * ne0)          # righe VERE nel file, non ne1 dichiarato
        a = np.fromfile(os.path.join(dump, c[0]), dtype=np.float32, count=n_tok * ne0)
        pezzi.append(a.reshape(n_tok, ne0))
    if not pezzi:
        raise SystemExit('nessun %s in %s' % (nome, dump))
    return np.concatenate(pezzi, axis=0)


print('CANTIERE TESTA — estrazione coppie (stato h_%d, id t+1)\n' % STRATO)
tot_ok = True
for dominio, (dump, log) in TRACCE.items():
    if not os.path.isdir(dump):
        print('%-8s DUMP ASSENTE: %s' % (dominio, dump)); tot_ok = False; continue
    ids, atteso = id_dal_log(log)
    H = stati_dall_indice(dump, STRATO)
    cancello = (len(ids) == atteso == H.shape[0])
    print('%-8s stati %5d x %d | id letti %5d (log dichiara %5d) | CANCELLO %s'
          % (dominio, H.shape[0], H.shape[1], len(ids), atteso,
             'PASSATO' if cancello else '*** FALLITO ***'))
    if not cancello:
        tot_ok = False
        continue
    X = H[:-1]                 # stato a t
    y = ids[1:]                # token a t+1
    fuori = float(np.mean(~np.isfinite(H)))
    print('         coppie %5d | norma media |h| %.3f | non-finiti %.4f%% | id distinti %d'
          % (len(X), float(np.linalg.norm(H, axis=1).mean()), 100 * fuori, len(np.unique(y))))
    np.savez_compressed(os.path.join(dump, 'coppie_h%d.npz' % STRATO), X=X, y=y)
    print('         salvato -> %s' % os.path.join(dump, 'coppie_h%d.npz' % STRATO))

print('\nCANCELLO COMPLESSIVO:', 'PASSATO' if tot_ok else 'FALLITO — fermarsi qui')
