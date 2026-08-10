# 39 — `seq_pos_min` NON mente. Mente il commento, e la domanda era un'altra

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `6e0da6d31`.
**Niente compilato, niente eseguito** (la macchina misura). Codice sull'albero, non
committato. Marcatura: [MISURATO] = codice letto riga per riga o log su disco;
[DEDOTTO] = aritmetica su misure; [ATTESO] = predizione da falsificare.

## L'esito in sei righe

1. **`return kv_raw->seq_pos_max(seq_id)` e' il valore ESATTO, non una bugia.**
   Il consumatore e' uno solo (`server-context.cpp:3275`) e decide con
   `pos_min >= pos_next - n_swa - (ha_nuovi ? 0 : 1)`. Per DEEPSEEK4 quel `n_swa`
   vale **ZERO**: `llama_model_n_swa()` lo azzera apposta
   (`src/llama-model.cpp:2369-2376`), e `server-context.cpp:1297` ci costruisce
   sopra la soglia. Con `n_swa = 0` la soglia e' `pos_next`, e "pos_min = pos_max"
   significa esattamente **"posso ripartire solo da pos_max + 1"**. Che e' vero.
2. **Quindi il caso del §4 del mandato — secondo turno, prefisso identico, solo da
   estendere — non e' bloccato: passa gia' oggi, ed e' MISURATO.**
   `LLAMA_AGENTE.server.log:556-562`, task 261: `task.n_tokens = 1778`,
   `cached n_tokens = 1759`, **nessun** `forcing full prompt re-processing`,
   **nessun** `restored context checkpoint`. Estensione pura servita dalla cache.
   Quello stesso log e' anche la **conferma empirica che `n_swa = 0`**: con 128 la
   soglia sarebbe stata `1759 - 128 = 1631`, il ramo dei checkpoint sarebbe scattato
   e avrebbe ripristinato il checkpoint 2 (`pos_min = 1491 < 1631`), lasciando la
   riga `restored context checkpoint` che invece **non c'e'**.
3. **Il caso del §3 — buttare 199 posizioni di coda dopo il ripristino da disco —
   NON e' servibile**, e non per il margine dell'anello. Lo blocca la **cache SWA
   grezza**: 256 celle, `n_swa` fisico 128, quindi al piu' **128 posizioni** di coda
   [MISURATO, `kvd_B.server.log:102,182`]. Servirebbero `199 + 128 = 327` celle. Il
   margine dell'anello e' il *secondo* muro (4 posizioni), non il primo. Alzare
   `LLAMA_KV_ROLLBACK_MARGINE` a 199 **non basta e da solo non fa niente**.
4. **La formula del limite vero c'e', e' derivata dal codice ed e' nel file.** Tre
   vincoli, non uno. Il fatto notevole e' che a margine 0 **riproduce il valore di
   oggi per aritmetica**: il cancello d'identita' non e' una speranza, e' un
   teorema.
5. **La patch e' sull'albero dietro `LLAMA_KV_POSMIN_VERO`, default 0.** Accesa da
   sola e' *dimostrabilmente* un no-op. Accesa **insieme** a
   `LLAMA_KV_ROLLBACK_PARZIALE` sposta il minimo a `pos_max - min(M, X+1-U)` e apre
   due casi veri ma piccoli (vedi §5).
6. **Ho trovato dove la bugia era GIUSTA, ed e' un cammino di abort**: il campo
   `pos_min` del checkpoint di contesto non significa "minimo in memoria", significa
   "da dove questo checkpoint riparte". Scriverci il minimo vero fa chiedere una
   rimozione di coda di 1 posizione **subito dopo uno `state_read`**, cioe' proprio
   quando il riavvolgimento e' cieco. Quel sito e' pinnato, dalla stessa leva.

**E il vero rimedio per i 288 secondi e' un terzo, che non passa da `seq_pos_min`
(§6).** I checkpoint di contesto non nascono ogni N token: nascono ai **punti di
rottura** del ciclo di riempimento, e `-cms 8192` li veta tutti su ogni prompt sotto
gli 8.192 token. **`-cms 32`** sblocca il checkpoint a 4 token dalla fine del prompt
e porta il prefill del secondo turno da 6.510 token a **4** — `288,2 s -> ~0,2 s`
[DEDOTTO da due punti misurati]. Costo: **582 MiB di RAM host**, zero VRAM, +0-20 ms
per richiesta. Sul cammino del **disco** pero' non basta: `SLOT_RESTORE` ripristina
solo i token e perde la lista dei checkpoint, che la cache in RAM invece conserva.

---

## 1. La catena vera, riga per riga [MISURATO]

Il mandato descrive la catena cosi': `pos_min = pos_max` -> la condizione a
`:3272-3275` e' SEMPRE vera -> checkpoint -> lista vuota -> `do_reset`. **Il primo
anello e' sbagliato, e cambia la diagnosi.**

```
server-context.cpp:1297   n_swa = params_base.swa_full ? 0 : llama_model_n_swa(model_tgt);
llama-model.cpp:2369-2376 int32_t llama_model_n_swa(...) {
                              // dsv4 kv-cache has SWA but it cannot be used as a rollback
                              // because of other compression ratios, so we return 0 here
                              if (model->arch == LLM_ARCH_DEEPSEEK4) return 0;
                              return model->hparams.n_swa;
                          }
server-context.cpp:3272   pos_min_thold = max(0, pos_next - n_swa - (has_new_tokens ? 0 : 1));
server-context.cpp:3324   if (pos_min >= pos_min_thold) { ...cerca un checkpoint... }
```

Con `n_swa = 0` la soglia e' `pos_next` (o `pos_next - 1`). Sostituendo il valore
dichiarato oggi, `pos_min = pos_max`:

| caso | `pos_next` | `ha_nuovi` | soglia | `pos_max >= soglia`? | esito |
|---|---|---|---|---|---|
| **estensione pura** (2° turno) | `pos_max+1` | si | `pos_max+1` | **no** | **riuso, nessun checkpoint** |
| coda vera di D>=1 | `pos_max+1-D` | si | `pos_max+1-D` | si | checkpoint |
| prompt gia' tutto in cache | `pos_max+1` | no | `pos_max` | si | checkpoint |

**La prima riga e' il §4 del mandato, e non e' bloccata.** La riga che il mandato ha
misurato e' la seconda, con `D = 199`.

### Il controllo positivo, e il controllo che discrimina [MISURATO, `LLAMA_AGENTE.server.log`]

```
:556  task 261 | new prompt, n_ctx_slot = 102400, task.n_tokens = 1778
:557  task 261 | cached n_tokens = 1759, memory_seq_rm [1759, end)
:560  task 261 | created context checkpoint 4 of 32 (pos_min = 1759, pos_max = 1759, ...)
```

Dopo il task 169 la cache teneva 1.759 token; il task 261 ne porta 1.778 con
prefisso comune 1.759 -> `pos_next = 1759`, `pos_max = 1758`, `ha_nuovi` vero,
soglia `1759`. `1758 >= 1759` e' **falso**: il ramo dei checkpoint viene saltato,
`p0 = 1759 > pos_max` e la `seq_rm` e' il no-op. **19 token elaborati su 1.778.**

Questa riga fa due cose in una. E' il **controllo positivo** dell'estensione pura,
e **discrimina `n_swa = 0` da `n_swa = 128`**: se la soglia fosse `1759 - 128`, il
ramo sarebbe scattato e avrebbe trovato il checkpoint 2 (`pos_min = 1491`), che
avrebbe lasciato a log un `restored context checkpoint`. Non c'e'. La lettura di
`llama_model_n_swa()` regge anche sui numeri, non solo sul codice.

Il task 169 dello stesso log e' il controllo dell'altro ramo: prefisso comune che
**non** arriva alla fine della cache -> ramo dei checkpoint -> ripristino a
`pos_max = 1491` -> `prompt eval 20.617 ms / 189 token` invece di ~186 s. **E'
esattamente il meccanismo del §6, gia' misurato**, e l'unica differenza con
`kvd_B` e' che li' un checkpoint recente esisteva e qui no.

Verifica sul log del ripristino [MISURATO, `kvd_B.server.log`]: stato ripristinato a
6.709 token, `task.n_tokens = 6510`, quindi `n_past = 6510`, `pos_next = 6510`,
`pos_max = 6708`, `has_new_tokens = (6510 < 6510) = false` -> soglia `6509` ->
`6708 >= 6509` vero -> checkpoint -> lista vuota -> `do_reset` -> `forcing full
prompt re-processing` alle `1.30.207.351` -> `prompt eval 288.223 ms / 6.510 token`.
La catena del mandato e' giusta **per questo caso**; la sua generalizzazione a
"blocca ogni riuso" no.

### La geometria, dai log e non a occhio [MISURATO, `kvd_B.server.log`]

| cosa | valore | riga |
|---|---|---|
| `n_swa` fisico del modello | **128** | `:102` (`print_info`) |
| `n_swa` visto dal server | **0** | codice, `llama-model.cpp:2372` |
| cache SWA grezza | **256 celle**, 10,75 MiB, 43 strati | `:180-182` |
| cache non-SWA (base) | 10240 celle, **0 strati, 0,00 MiB** | `:401` |
| CSA compressa / HCA / LID | 2560 / 80 / 2560 celle | `:185,191,197` |
| margine anello attivo nella corsa | 4 righe | `:224` |
| checkpoint di contesto | max 32, **spaziatura minima 8192** | `:load_model` |

La riga "base = 0 strati" e' importante: `llama_kv_cache_iswa::seq_pos_min` ritorna
`kv_swa->seq_pos_min` (`llama-kv-cache-iswa.cpp:142-144`), e con la base vuota **il
minimo grezzo e' esattamente il minimo della finestra SWA**.

## 2. La formula del limite vero

Sia `X = kv_raw->seq_pos_max(seq)` e sia **P** la posizione piu' vecchia da cui si
puo' ripartire senza corrompere lo stato compresso. Tre vincoli, tutti necessari.

### (1) Anello dei compressori — da `dsv4_build_comp_plan`

Ogni posizione scrive la riga `pos % S` (`llama-kv-cache-dsv4.cpp:592`, e
`state_source_idx` a `:572-573`). Il commit del primo blocco dopo `p0` rilegge
`[p0-2r, p0-1]` per CSA/LID (compressore con sovrapposizione, `:609,616-623`) e
`[p0-r, p0-1]` per HCA (`:609,625-627`). L'anello conserva solo le ultime `S`
posizioni, cioe' `[X-S+1, X]`. Con `S = 2r + M` per CSA/LID e `S = r + M` per HCA
(`:1215,1221,1227`, `M = rb_margine`):

```
p0 - 2r >= X - (2r + M) + 1   <=>   p0 >= X + 1 - M        (CSA/LID)
p0 -  r >= X - ( r + M) + 1   <=>   p0 >= X + 1 - M        (HCA, identico)
```

**`P_anello = X + 1 - M`.** A `M = 0`: `X + 1`, cioe' nessun riavvolgimento.
Coincide con l'aritmetica dell'audit 37 (`S >= 2*ratio + B`), vista dall'altro capo.

### (2) Finestra SWA grezza — il muro che il mandato non contava

Una query a `Q` vede le celle con `pos > Q - n_swa`
(`llama_hparams::is_masked_swa`, `llama-hparams.h:382-387`, ramo STANDARD). La prima
query del ri-forward sta a `p0` e chiede `[p0-n_swa+1, p0-1]`. Quelle celle esistono
solo se il minimo grezzo `L = kv_raw->seq_pos_min(seq)` e' abbastanza indietro:

```
P_grezzo = L + n_swa                    (una posizione conservativa sul >=)
```

La cache SWA e' di `W` celle, e `W = GGML_PAD(min(kv_size, n_swa + n_ubatch), 256)`
(`llama-kv-cache-iswa.cpp:73`); il pruning tiene le celle contigue, quindi
`L >= X - W + 1`. Il vincolo (2) da solo permette al piu'

```
D_grezzo = W - n_swa = 256 - 128 = 128 posizioni
```

**Questo e' il muro dei 199, ed e' fuori dalla portata di `seq_pos_min`**: dipende
dalla taglia della cache grezza, non da cosa dichiariamo. Per SWA CHUNKED la
finestra vera e' un sottoinsieme: il conto resta valido perche' e' conservativo.

### (3) Celle riciclate dall'ultimo forward

`find_slot` ricicla le celle mascherate rispetto alla **prima** posizione
dell'ultimo ubatch (`llama-kv-cache.cpp:1045-1064`, argomentato nell'audit 37 §2).
E' la stessa guardia che applica gia' `seq_rm_tail` (`:1469-1476`):

```
P_ubatch = rb_pos_min_ultimo[seq]      (X + 1 quando e' ignoto, cioe' dopo state_read)
```

Va applicata **qui**, non solo dentro `seq_rm_tail`: se il server accettasse una coda
che poi `seq_rm_tail` rifiuta, `common_context_seq_rm` la trasformerebbe in
`GGML_ABORT` (`common/common.cpp:1523-1528`).

### Il risultato

```
P = max( X + 1 - M ,  L + n_swa_fisico ,  P_ubatch )

seq_pos_min = max( L ,  P - n_swa_consumatore - 1 )        con n_swa_consumatore = 0
```

Profondita' di coda servibile: `D = X + 1 - P = min(M, W - n_swa, X + 1 - U)`.
**Oggi: `min(4, 128, 1..2)` = 1 o 2 posizioni.** Il mandato ne chiedeva 199.

**I due `n_swa` sono diversi e non vanno confusi**: il vincolo (2) e' mascheramento
vero e usa i 128 fisici; l'inversione della soglia usa lo 0 del consumatore. Usare
128 nell'inversione dichiarerebbe un minimo 128 posizioni troppo basso, il server
accetterebbe code fino a 128, `seq_rm_tail` (margine 4) le rifiuterebbe e il server
abortirebbe. E' il modo piu' facile di rompere questa patch, ed e' scritto nel file.

### Il cancello d'identita' e' aritmetico

Con `M = 0`: `P = max(X+1, L+128, ...)`, e siccome `L >= X-255` si ha
`L + 128 >= X - 127`, che e' `< X + 1`. Il termine `P_ubatch` e' consultato solo se
`M > 0`. Quindi `P = X + 1` e

```
seq_pos_min = max(L, X + 1 - 0 - 1) = max(L, X) = X = seq_pos_max
```

**identico al valore di oggi, per costruzione.** Non e' un cancello da sperare: e'
una dimostrazione. Se il cancello 1 cade, e' un difetto di scrittura, non di tesi.

## 3. Che cosa c'e' sull'albero

### `git diff --numstat`

```
167   4  src/llama-kv-cache-dsv4.cpp
  9   0  src/llama-kv-cache-dsv4.h
 67   3  tools/server/server-context.cpp
```

Scansione byte diretta: **0 byte CR** in tutti e tre. (I 3 byte non-ASCII in
`server-context.cpp` sono a riga 423 e sono **preesistenti**: `git show HEAD:` ne
conta 3 identici.) `core.autocrlf = false`, nessun `.gitattributes`.

Delle 174 righe aggiunte, **~95 sono il commento con la derivazione** in testa a
`llama-kv-cache-dsv4.cpp`: la formula sta nel codice, non solo qui.

- **`src/llama-kv-cache-dsv4.h` (+9, -0)** — `rb_p0_min()` (pubblica, restituisce
  `P`), il campo `pm_vero`. Nessuna riga tolta.
- **`src/llama-kv-cache-dsv4.cpp` (+167, -4)** — le 4 righe sostituite sono il corpo
  di `seq_pos_min()`, che diventa un ramo (`if (!pm_vero) { ...il codice di prima,
  commento compreso... }`). Il resto e' aggiunta: la derivazione, la costante
  `DSV4_N_SWA_CONSUMATORE`, il lettore della leva, `rb_p0_min()`, e una riga di log
  all'avvio che stampa i **due tetti** invece di farli dedurre.
- **`tools/server/server-context.cpp` (+67, -3)** — tre righe cambiate:
  `common_context_seq_rm(ctx_tgt, ...)` a `:3417` diventa condizionale su un
  tentativo di `seq_rm_tail`; la gemella su `ctx_dft`; e `create_checkpoint(...,
  pos_min, ...)` diventa `pos_min_ckpt`. Tutto il resto e' aggiunta: il campo
  `posmin_vero`, la sua lettura accanto a `LLAMA_TRACE`, e il pin del §6.

### Il contorno della leva

| variabile | effetto |
|---|---|
| (nessuna) | **spento.** `seq_pos_min` = `seq_pos_max`, server invariato. |
| `LLAMA_KV_POSMIN_VERO=1` | formula attiva. **Da sola: aritmeticamente identica** (M=0). |
| `LLAMA_KV_POSMIN_VERO=1` + `LLAMA_KV_ROLLBACK_PARZIALE=1` | minimo = `X - min(M, X+1-U)`; il riuso del prompt puo' chiedere una coda, servita da `seq_rm_tail`. |
| `LLAMA_KV_ROLLBACK_MARGINE=<n>` | come nell'audit 37. **Oltre 128 non serve a niente**: il vincolo (2) taglia prima. |

## 4. La sequenza dei cancelli, in ordine

### Cancello 1 — IDENTITA' (nessuna leva nuova)

- **deve uscire**: SHA `CF2DEEA06E90`, **12,83-12,92 t/s** a contesto corto, e la
  riga `coda riavvolta = 0 parziali / 79 ripristini` dell'audit 37.
- **novita' attesa nel log**: nessuna. Nemmeno una riga.
- **se cade**: e' l'unico cancello di questa patch che *non puo'* cadere per
  ragioni di tesi (§2). Guardare il ramo `if (!pm_vero)` e il campo `posmin_vero`
  non inizializzato.

### Cancello 2 — IDENTITA' A LEVA ACCESA, DA SOLA

`LLAMA_KV_POSMIN_VERO=1`

- **deve uscire**: all'avvio
  `seq_pos_min VERO: n_swa = 128, celle SWA grezze = 256 -> tetto grezzo 128
  posizioni; margine anello 0 -> coda servibile = 0 posizioni (identico al
  comportamento di oggi)`,
  e poi **di nuovo SHA `CF2DEEA06E90` e 12,83-12,92 t/s**.
- **cosa prova**: che la formula riproduce il valore di oggi. E' il §2 in forma
  eseguibile. Se qui il testo cambia, **la derivazione e' sbagliata** e tutto il
  resto e' nullo — e lo si sa senza che il rollback confonda la misura.
- **la riga di log e' anche il numero che il mandato chiedeva**: "128" e' il limite
  vero imposto dalla cache grezza, stampato invece che dedotto.

### Cancello 3 — IL CASO DUE-TURNI, **A LEVA SPENTA** (fatelo per primo, non costa nulla)

Nessuna leva. Server su, una richiesta di chat che genera, **poi una seconda
richiesta che contiene la prima piu' il turno nuovo** (cioe' `/v1/chat/completions`
con la conversazione intera, come fa un client vero).

- **gia' misurato sul build dell'5 agosto** (`LLAMA_AGENTE:556-562`, 19 token su
  1.778). Qui si sta solo verificando che il build di oggi non abbia regredito.
- **deve uscire**: **niente** `forcing full prompt re-processing`, **niente**
  `restored context checkpoint`, `cached n_tokens` grande sulla seconda richiesta,
  `prompt eval` sulla seconda vicino a **0 token processati**.
- **contate i caratteri della risposta, non lo SHA**: `E3B0C44298FC` e' la stringa
  vuota e ha gia' fatto passare due cancelli su corse che non avevano prodotto
  niente.
- **se invece esce `forcing full prompt re-processing`**: la mia lettura di
  `llama_model_n_swa()` e' sbagliata o il prefisso comune non arriva a
  `slot.prompt.n_tokens()` (ri-tokenizzazione del turno assistente che divergre). Il
  log dice quale: `cached n_tokens = N` con `N < 6709` e' il secondo caso. **Solo in
  quel caso il cancello 4 vale qualcosa**, e vale per `6709 - N <= 2` posizioni.

### Cancello 4 — IL RIAVVOLGIMENTO AL RIUSO DEL PROMPT

`LLAMA_KV_POSMIN_VERO=1 LLAMA_KV_ROLLBACK_PARZIALE=1`

Caso piu' semplice che lo esercita: **mandare due volte lo stesso identico prompt**
(e' il ramo `has_new_tokens == false`, che chiede esattamente 1 posizione per il
`n_past--` di `[TAG_PROMPT_LOGITS]`).

- **deve uscire**: `riuso del prompt con coda da togliere: p0 = N, pos_max = N,
  coda = 1 posizioni -> riavvolta sul posto`, e `prompt eval` quasi nullo.
- **se esce `RIFIUTATA`**: **non proseguire, il server abortisce alla riga dopo.**
  Vuol dire che `rb_p0_min` e' piu' largo di cio' che `seq_rm_tail` serve: i due
  usano gli stessi tre vincoli, quindi sarebbe un difetto di scrittura in uno dei
  due. La riga `dsv4: coda NON riavvolgibile (<motivo>)` dice quale dei tre.
- **correttezza**: il testo deve coincidere con quello della corsa senza cache. Una
  divergenza nei primi token e' un difetto, non rumore.

### Cancello 5 — IL CASO DISCO, che **deve fallire** (ed e' un cancello lo stesso)

`LLAMA_KV_POSMIN_VERO=1 LLAMA_KV_ROLLBACK_PARZIALE=1 LLAMA_KV_ROLLBACK_MARGINE=199`,
protocollo di `kvd_A`/`kvd_B`.

- **deve uscire**: di nuovo `forcing full prompt re-processing` e ~288 s.
- **cosa prova**: che il muro e' il vincolo (2) e non il margine. Se invece
  *riuscisse*, la mia aritmetica sulla finestra SWA e' sbagliata e va rifatta.
- **prezzo se lo lanciate**: margine 199 costa ~57,7 MiB di VRAM **e gonfia ogni
  checkpoint speculativo** (da 12,826 a ~70 MiB, salvato ~641 volte per 1200 token).
  **Non lasciatelo acceso in una corsa di velocita'.**

## 5. Che cosa compra davvero questa patch (poco, e lo dico)

A margine 4 e con il confine dell'ultimo ubatch che stringe a 1-2 posizioni, i casi
che si aprono sono due:

1. **stesso prompt mandato due volte** (`has_new_tokens == false`): chiede esattamente
   1 posizione. Oggi rifa il prefill intero.
2. **deriva di ri-tokenizzazione di 1-2 token** fra un turno e il successivo. Oggi
   basta un token di scarto per buttare tutto il contesto.

Il secondo e' il piu' interessante perche' rende **robusto** il caso del cancello 3,
che oggi funziona solo se il prefisso comune arriva **esattamente** all'ultimo token
in cache. E **sappiamo che non ci arriva sempre**: nello stesso `LLAMA_AGENTE`, il
task 261 ci arriva (19 token) e il **task 169 no** — e li' e' costato un ripristino
di checkpoint e 189 token. Ma la tolleranza che questa patch compra e' di 1-2
posizioni, e lo scarto del task 169 era molto piu' grande: **quel caso lo copre il
§6, non il §5.**

**Non compra il caso del mandato.** Se il bersaglio sono i 288 secondi, la patch
giusta e' il §6.

## 6. I 288 secondi: la regola vera dei checkpoint, e il numero da provare

**Correzione a me stesso.** Avevo scritto che i checkpoint nascono ogni `-cms` token
e che `-cms 512` ne avrebbe messo uno a ~6.144. **E' sbagliato.** I checkpoint non
sono spaziati: nascono in **punti di rottura** del ciclo di riempimento del prompt
(`server-context.cpp:3537-3593`), e `-cms` e' solo un **veto** su quei punti
(`:3629`). I due log lo dimostrano, perche' hanno spaziature di 178/142/126 token
con `min spacing = 8192`.

### La regola, dal codice e confermata su due log

Un checkpoint nasce quando il batch **comincia** in uno di questi punti:

- **(a) inizio di un messaggio utente**, `spans.is_user_start(n_tokens_start)`
  (`:3564,3602`);
- **(b) vicino alla fine del prompt**: il ciclo rompe apposta a
  `N - min(n_batch, 4 + n_ubatch)` e a `N - min(n_batch, 4)` (`:3578-3592`,
  upstream PR 20288), e `near_prompt_end` lo lascia passare (`:3600,3611`);

**e** il veto passa (`:3629`):
`checkpoints.empty() || is_last_user_message || n_tokens_start > ultimo.n_tokens + cms`.

| log | N | n_batch/n_ubatch | rotture vicino alla fine | checkpoint creati | perche' |
|---|---:|---|---|---|---|
| `LLAMA_AGENTE` t0 | 1567 | 16 / 16 | 1551, 1563 | **1314**, **1492** | 1314 = primo user start (lista vuota); 1492 = `last_user_pos` (scavalca il veto). A 1551: `1551 > 1492 + 8192` falso |
| `kvd_A` t0 | 6510 | 2048 / 64 | **6442**, **6506** | **1** | 1 = primo user start (lista vuota). A 6442: `6442 > 1 + 8192` falso |

Le rotture tornano alla cifra: `1567-16 = 1551`, `1567-4 = 1563`,
`6510-min(2048,68) = 6442`, `6510-4 = 6506`, e sono **tutte e quattro nei log** come
righe `cached n_tokens`. **Stessa regola, stesso veto, due esiti diversi solo per la
lunghezza del prompt.** Con 8192 il veto e' inattaccabile per ogni prompt sotto gli
8.192 token: **il default rende i checkpoint di fine prompt impossibili.**

### Il numero

Per la forma di `kvd_A` (un solo messaggio utente, `N = 6510`, ultimo checkpoint a
`n_tokens = 1`):

```
checkpoint a 6442  <=>  6442 > 1 + cms      <=>  cms <= 6440
checkpoint a 6506  <=>  6506 > 6442 + cms   <=>  cms <=   63
```

**Il numero da provare e' `-cms 32`.** E' la piu' grande potenza di due che sta sotto
63, quindi prende **entrambi** i checkpoint di fine prompt, e non e' 0: due messaggi
utente a meno di 32 token l'uno dall'altro continuano a fondersi.

### La banda attesa, in secondi

Con il checkpoint a `n_tokens = 6506` (`pos_max = 6505`), il predicato di `:3351`
lo accetta (`6505 < 6509`, `6505 <= 6510`), `pos_next = 6506`, `n_past = 6506`, e
`[TAG_PROMPT_LOGITS]` non decrementa (`6506 != 6510`):

| `-cms` | checkpoint utile | token da rifare | prefill atteso |
|---|---|---:|---|
| 8192 (oggi) | solo `pos 0` | **6.510** | **288,2 s** [MISURATO] |
| 64 … 6440 | `n_tokens = 6442` | **68** | **3,0 s** (banda 2,8-3,5) |
| **32** | `n_tokens = 6506` | **4** | **0,2 s** (banda 0,2-0,5) |

Conversione a 44,27 ms/token [MISURATO, `kvd_A:595`]. La banda e' costo fisso, non
incertezza per token: `LLAMA_AGENTE` mostra 109,09 ms/token su 189 token contro
110,79 su 1.567, cioe' **il ms/token non peggiora sui prefill corti** [MISURATO].

### Il costo in MiB

Taglia di un checkpoint, dai due punti misurati:
`12,826 MiB` a 1 token con margine 4 (`kvd_A:470`) e `17,021 MiB` a >=1.314 token
senza margine (`LLAMA_AGENTE:445,470,526,560`). Decomposizione [DEDOTTO]:

```
11,64 MiB  stati compressori (CSA 1,31 + HCA 10,00 + LID 0,33, audit 33)   fisso
 1,16 MiB  margine anello 4 righe (audit 37)                               fisso, solo col rollback
~5,38 MiB  celle SWA grezze, satura a 128 celle x 42 KiB                   cresce col contesto
```

Verifica: `11,64 + 1,16 + 0,03 = 12,83` contro `12,826` misurato;
`11,64 + 0 + 5,38 = 17,02` contro `17,021` misurato. E `43,00 MiB / 256 celle /
4 seq = 42 KiB per cella`, che e' esattamente la pendenza. Il modello regge su
entrambi.

- **Checkpoint maturo con la patch di stanotte: ~18,2 MiB.**
- Il tetto e' `-ctxcp`, oggi 32: **582 MiB di RAM HOST** (`data_tgt`/`data_dft` sono
  `std::vector<uint8_t>`, `common.h:1091-1092`), **non VRAM**. Su 96 GB e' niente.
- Costo in tempo: un D2H di ~18 MiB per checkpoint creato. Con `-cms 32` sulla forma
  di `kvd_A` si passa da 1 a 3 checkpoint per richiesta: **+2 x C_save**, cioe'
  **+0-20 ms** con la forcella `C_save` dell'audit 33. Contro 288 s.

### L'avvertenza che rende questo numero meta' di una risposta

`-cms 32` **non copre il caso disco da solo.** `SERVER_TASK_TYPE_SLOT_RESTORE`
(`server-context.cpp:2602-2634`) ripristina `slot->prompt.tokens` e **basta**:
`slot->prompt.checkpoints` non viene scritto — e **non viene nemmeno azzerato**
(`:2633` pulisce solo `tokens`), cosa che con uno slot gia' usato lascerebbe
checkpoint **di un altro prompt** nella lista, con `pos_min == 0` che passa il
predicato. E' un difetto latente upstream, non nostro, ma va guardato prima di
alzare il numero di checkpoint.

La **cache dei prompt in RAM** invece i checkpoint li porta con se'
(`server-task.cpp:1666-1672,1729`; `server-task.h:601,623`). Quindi:

| cammino | `-cms 32` serve? |
|---|---|
| secondo turno, stessa sessione | **si', subito** — e' il cammino del task 169 |
| cache prompt in RAM (slot riusato, server vivo) | **si', subito** |
| `--slot-save-path` dopo un riavvio | **no**, finche' i checkpoint non stanno nel file |

Serializzare `checkpoints` nel file di slot e' ~50 righe e nessun tocco al motore.
E' il passo che chiude il caso che avete misurato; `-cms 32` chiude gli altri due,
**stasera, senza ricompilare.**

## 7. I casi in cui la bugia era GIUSTA

1. **Il campo `pos_min` del checkpoint di contesto** (`server-context.cpp:3616` ->
   `create_checkpoint` -> `common.h:1088`). Non significa "minimo in memoria": e'
   consumato a `:3364` come `pos_next = min(pos_next, max(it->pos_min + 1,
   it->pos_max))`, cioe' **"da dove questo checkpoint puo' ripartire"**. Finche'
   `seq_pos_min` valeva `seq_pos_max`, `max(pos_min+1, pos_max)` dava `pos_max+1` e
   il `seq_rm` successivo era il no-op. Col minimo vero da' `pos_max`, cioe' una
   rimozione di coda di 1 posizione **subito dopo `load_tgt`** — e `state_read`
   chiama `rb_invalida()`, quindi il confine (3) e' ignoto e `seq_rm_tail` rifiuta
   **per costruzione**. Abort garantito. **Escluso dal predicato**: il sito e'
   pinnato a `pos_max` quando `posmin_vero && ctx_tgt_seq_rm_type == FULL`. Il
   commento upstream `[TAG_CHECKPOINTS_FIX_POS_MIN]` dice gia' che quel campo e'
   dichiarato male; qui e' anche pericoloso.
2. **La rimozione totale** (`p0 == 0`, il `do_reset`): non e' una coda e ha gia' la
   sua via in `seq_rm`. Il tentativo di `seq_rm_tail` e' escluso esplicitamente,
   altrimenti sporcherebbe i contatori dell'audit 37 e stamperebbe un rifiuto
   fuorviante a ogni reset.
3. **`--swa-full`**: `llama_model_n_swa()` ritorna 0 per DEEPSEEK4, quindi
   `server-context.cpp:1290-1295` **disabilita `swa_full`** con un avviso. Non e'
   una via d'uscita per allargare la finestra grezza. La via e' `-ub`:
   `W = GGML_PAD(n_swa + n_ubatch, 256)`, e con `-ub 256` diventerebbe 512 celle
   (+10,75 MiB) e il tetto (2) salirebbe da 128 a 384. Non l'ho toccato: `-ub`
   sposta molte altre cose e va misurato per conto suo.
4. **`--cache-reuse`**: gia' morto per altra via (`get_can_shift()` false ->
   `cache_reuse is not supported by this context, it will be disabled`, presente in
   8 log). Il ramo a `:3239` con `p1 >= 0` abortirebbe subito: non e' raggiungibile e
   non l'ho toccato.

## 8. Dove ho sbagliato io, e cosa resta aperto

- **L'universale "non esiste una sola corsa con due prompt" era FALSA, e l'ha
  falsificata l'utente.** Ce ne sono almeno quattro (`ammortamento`, `LLAMA_AGENTE`,
  `LLAMA_CHAT_sota2`, `LLAMA_ngl99_sota8k_nothink_194125`), e una di queste e' il
  controllo positivo della mia stessa tesi. **Come avevo cercato, cioe' dove sta il
  buco**: `Get-ChildItem -Filter *.server.log | Sort-Object LastWriteTime
  -Descending | Select-Object -First 40`. Due difetti in una riga: `-First 40` su
  **395** file che matchano (e 2.604 nella cartella), e l'ordine per data, che rende
  quei 40 esattamente la campagna di stanotte — fatta per costruzione di corse a
  prompt singolo. **Ho guardato il 10% del corpus, e il 10% peggiore per la domanda
  che stavo facendo.** La forma giusta dell'affermazione era: "cercando fra i 40 log
  piu' recenti non ne ho trovate", che si vede subito che non e' una prova.
- **Il §6 era sbagliato nel meccanismo**, non solo nel numero: avevo dedotto dal solo
  codice una regola di spaziatura che non esiste. La regola vera (punti di rottura +
  veto) si legge solo mettendo insieme il codice e le posizioni reali dei checkpoint
  nei due log. **La lezione e' la stessa del ledger: prima i numeri, poi l'ipotesi.**
- **Non ho misurato quanto valga davvero il §5.** Se la ri-tokenizzazione fra turni
  diverge di piu' di 2 token, la patch non serve e serve invece il §6.
- **Non ho compilato.** I punti piu' probabili di rottura sono `kv_raw->get_swa()`
  nel costruttore (chiamato dopo la costruzione di `kv_raw`, verificato) e la
  deduzione di tipo su `pos_min_ckpt` (ternario fra due `llama_pos`).
- **Il `kv_ring` (mirror caldi CSA/HCA/LID in VRAM) non e' stato ri-analizzato per il
  riavvolgimento.** A `M = 0` non c'e' riavvolgimento e la domanda non si pone; a
  `M > 0` l'esposizione e' la stessa gia' aperta dall'audit 37, non nuova.

## 9. Il contesto da 100k che si e' caricato: cosa c'era di diverso

`LLAMA_AGENTE.server.log`, 5 agosto, **build 11 `4b4094d`**, modello
`C:\ds4-models\DS4-0731-IQ2XXS.gguf`. `n_ctx = n_ctx_seq = 102400`, `n_parallel = 4`,
`kv_unified = true`, `n_batch = n_ubatch = 16`. Tutto quello che segue e' [MISURATO],
riga per riga; **non ho il log della corsa fallita di stanotte**, quindi dico cosa
c'era li', non cosa ha ucciso l'altra.

**Le tre assenze, che sono la risposta:**

1. **Nessuna bozza.** `:243 spec common_specu: no implementations specified for
   speculative decoding`. Nessun secondo contesto, nessuna `cache-bozza`, e quindi
   **nessun `cudaHostAlloc` per il `blk.0` della bozza**. La riga
   `speculative decoding will use checkpoints` a `:241` e' solo l'esito della sonda
   sul bersaglio, non una bozza attiva.
2. **Nessuna cache esperti.** La riga `cache-esperti: ... slot da ... MiB in VRAM`
   **non compare mai** (0 occorrenze). Oggi vale 339 slot x 6,75 MiB = **2.289 MiB
   di VRAM**.
3. **Nessuna `cache-bozza`.** Oggi 32 slot x 8,69 MiB = **278 MiB di VRAM**.

**Dove sono finiti i byte, invece:**

```
:172  ggml_backend_cuda_mapped_buffer_type_alloc_buffer: 74304.00 MiB mappati
                                       host->device (zero-copy) -> UVA SI
:176  load_tensors:        CUDA0 model buffer size =  7383.67 MiB   (denso, residente)
:177  load_tensors: CUDA0_Mapped model buffer size = 74304.00 MiB   (esperti, mappati)
:178  load_tensors:    CUDA_Host model buffer size =  1010.00 MiB   (pinned)
```

VRAM per il KV a 102.400 (`:201-216`), tutta in `CUDA0`:

| cache | celle | strati | MiB |
|---|---:|---:|---:|
| raw non-SWA | 102400 | **0** | 0,00 |
| raw SWA | 256 | 43 | 43,00 |
| CSA compressa | 25600 | 21 | 2100,00 |
| HCA compressa | 1024 | 20 | 80,00 |
| LID | 25600 | 21 | 525,00 |
| | | **totale** | **2748,00** |

Bilancio: `7383,67 (denso) + 2748 (KV) = 10.132 MiB` su **11.255 MiB liberi**
(`:4`, 3060 da 12.287). Passa con ~1,1 GiB di margine.

**Il conto che conta**: `2.289 (cache esperti) + 278 (cache bozza) = 2.567 MiB`,
contro i **2.748 MiB** che costa il KV compresso a 100k. **Sono la stessa cifra.**
Il contesto lungo e la cache esperti si contendono lo stesso spazio quasi in
rapporto 1:1, e il 5 agosto la scelta era gia' stata fatta — dall'altra parte.

Nota sulla velocita', perche' non venga letta come un pasto gratis: quella
configurazione girava a **110,79 ms per token di prefill (9,03 tok/s)** contro i
**44,27 ms (22,59 tok/s)** di `kvd_A`. Zero-copy su 74,3 GiB di esperti costa 2,5x
per token. Il contesto da 100k c'era; la velocita' no.

**Cosa NON si capisce dal log e non ricostruisco a naso**: se il fallimento di
stanotte sia dovuto alla sola somma delle allocazioni pinned (1.010 MiB qui contro i
2.224 MiB del `blk.0` della bozza) o a un limite del WDDM sul singolo
`cudaHostAlloc`. Per deciderlo serve il log della corsa fallita, che non e' in
`D:\ds4_work\llama_run\` con un nome che ho saputo riconoscere.
