"""
ORACOLO — costruisce la pianificazione degli esperti da una traccia di decode.

A COSA SERVE (idea dell'utente, 8/8 h06): misurare il TETTO. Non e' un
meccanismo che va in produzione: e' un braccio che risponde a una domanda il cui
esito vale un fattore due sull'intera direzione "anello di rotazione".

   con lo staging PERFETTO, quanto andrebbe questa macchina?

Tre risposte in circolazione, e non vanno d'accordo:
   A) 16,3 (esperti su GPU) + 0 (staging perfetto) + 63,7 (il resto) = 80,0 ms
      = 12,5 t/s   -- assume l'orchestrazione INVARIANTE
   B) reap-loop keep-8 a residenza piena: 40 ms/token = 25,0 t/s
      -- dice che buona parte di quei 63,7 e' gestione dello streaming, e sparisce
   C) l'unico MISURATO: spostare uno strato di esperti in VRAM vera valeva
      1,64 ms/strato contro 1,13 previsti dal solo calcolo; i 0,51 di scarto per
      43 strati danno 17,2 t/s

PERCHE' E' UN ORACOLO ESATTO: a temperatura 0 la generazione e' deterministica,
quindi le route registrate in una passata sono ESATTAMENTE quelle della replica.
Errore zero per costruzione, non "un predittore molto buono". E il cancello e'
incorporato: se lo SHA dell'uscita della replica non combacia con quello della
registrazione, la replica e' divergita e il numero si butta.

COME SI PRODUCE LA TRACCIA (giro di macchina, prima di questo script):
  llama-eval-callback con lo stesso prompt, temperatura 0, 1.200 token, e la
  stessa configurazione del braccio da confrontare. Il dump va in una cartella
  con un file per (strato, passo):  ffn_moe_topk-<strato>.<passo>.bin
  ATTENZIONE: serve la traccia del DECODE. Quella in D:\\ds4_work\\dump viene dal
  PREFILL (LLAMA_PREDITTORE_ROUTE, 5/8) e NON va bene: gli id sono quelli dei
  token del prompt, non delle posizioni generate.

FORMATO PRODOTTO (letto da cache-esperti.cu, little-endian):
  char[8] "ORACOLO1" | int32 n_token | int32 n_strato | int32 n_id
  int32[n_token * n_strato * n_id]     ordine token-maggiore
  Un valore < 0 nella prima posizione di uno strato = "nessuna pianificazione":
  succede nei primi dsv4_hash_layer_count strati, che instradano per hash
  dell'id del token e non hanno router da prevedere.
"""

import sys, os, re, struct
import numpy as np

if len(sys.argv) < 3:
    print('uso: oracolo_pista.py <cartella_dump_decode> <file_uscita.bin> [n_id]')
    sys.exit(2)

SRC = sys.argv[1]
DST = sys.argv[2]
N_ID_ATTESO = int(sys.argv[3]) if len(sys.argv) > 3 else 6   # n_expert_used su DSV4

rx = re.compile(r'^ffn_moe_topk-(\d+)\.(\d+)\.bin$')

# --- raccolta: strato -> [(passo, path)] ---
per_strato = {}
for nome in os.listdir(SRC):
    m = rx.match(nome)
    if not m:
        continue
    L, passo = int(m.group(1)), int(m.group(2))
    per_strato.setdefault(L, []).append((passo, os.path.join(SRC, nome)))

if not per_strato:
    print('nessun file ffn_moe_topk-*.bin in %s' % SRC)
    sys.exit(1)

strati = sorted(per_strato)
print('strati trovati: %d  (da %d a %d)' % (len(strati), strati[0], strati[-1]))

# --- lettura: ogni file e' [n_id, n_token_del_passo] int32, ordine C ---
tracce = {}
for L in strati:
    pezzi = []
    for passo, path in sorted(per_strato[L]):
        a = np.fromfile(path, dtype=np.int32)
        if a.size % N_ID_ATTESO != 0:
            print('  !! %s: %d int32 non divisibile per n_id=%d' % (path, a.size, N_ID_ATTESO))
            sys.exit(1)
        pezzi.append(a.reshape(-1, N_ID_ATTESO))
    tracce[L] = np.concatenate(pezzi, axis=0)

lung = {L: t.shape[0] for L, t in tracce.items()}
n_token = min(lung.values())
if len(set(lung.values())) > 1:
    print('ATTENZIONE: gli strati hanno lunghezze diverse (min %d, max %d): tronco al minimo'
          % (n_token, max(lung.values())))

# --- gli strati mancanti diventano righe negative, non buchi silenziosi ---
n_strato = strati[-1] + 1
print('token utili: %d | strati in pianificazione: %d | id per strato: %d'
      % (n_token, n_strato, N_ID_ATTESO))

out = np.full((n_token, n_strato, N_ID_ATTESO), -1, dtype=np.int32)
for L in strati:
    out[:, L, :] = tracce[L][:n_token, :]

mancanti = [L for L in range(n_strato) if L not in tracce]
if mancanti:
    print('strati SENZA pianificazione (ricadono sul predittore): %s' % mancanti)

# --- CANCELLI, prima di scrivere ---
esiti = []
esiti.append(('token > 0', n_token > 0))
esiti.append(('id nel range [0,255]',
              bool(((out < 0) | ((out >= 0) & (out < 256))).all())))
# ogni riga pianificata deve avere id DISTINTI: sei esperti uguali sarebbe
# un dump letto con la forma sbagliata, non un instradamento
riga = out[:, strati[len(strati)//2], :]
esiti.append(('id distinti nella riga campione',
              bool(np.all([len(set(r.tolist())) == N_ID_ATTESO for r in riga[:200]]))))
# la traccia non deve essere costante: se lo fosse, avremmo dumpato una cosa sola
esiti.append(('la traccia VARIA nel tempo',
              bool(not np.array_equal(riga[0], riga[min(100, n_token-1)]))))

for n, ok in esiti:
    print('  %-34s %s' % (n, 'OK' if ok else '*** FALLITO ***'))
if not all(o for _, o in esiti):
    print('\nESITO: QUALCOSA NON TORNA, non scrivo')
    sys.exit(1)

with open(DST, 'wb') as f:
    f.write(b'ORACOLO1')
    f.write(struct.pack('<iii', n_token, n_strato, N_ID_ATTESO))
    out.tofile(f)

print('\nscritto: %s  (%.2f MiB)' % (DST, os.path.getsize(DST) / (1024 ** 2)))
print('ESITO: TUTTI I CANCELLI PASSATI')
print('\nBraccio: LLAMA_CACHE_ORACOLO=%s con LLAMA_CACHE_ESPERTI_W>0 e la STESSA' % DST)
print('configurazione della registrazione. Cancello: lo SHA dell uscita deve')
print('combaciare, altrimenti la replica e divergita e il tetto e falsato.')
