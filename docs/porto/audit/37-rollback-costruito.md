# 37 — IL ROLLBACK PARZIALE, COSTRUITO: non serviva copiare l'anello, bastava allargarlo

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `c871bfa6b`.
**Niente compilato, niente eseguito** (la macchina misura). Codice sull'albero, non
committato. Marcatura: [MISURATO] = codice letto riga per riga o log su disco;
[DEDOTTO] = aritmetica su misure; [ATTESO] = predizione da falsificare domani.

## L'esito in cinque righe

1. **Il progetto dell'audit 33 e' giusto nella diagnosi e piu' caro del necessario
   nel rimedio.** La sua tesi centrale — "il pezzo da versionare e' il ring di stato
   dei compressori, ~290 KB per posizione, con ripristino selettivo device-side" — e'
   corretta ma non serve: **quelle righe non vanno fotografate, basta che il forward
   annullato non le sovrascriva.** Si allarga l'anello di M righe e il problema
   sparisce per costruzione. Zero copie, zero ms per forward, zero codice nel grafo.
2. Costo del rimedio: **+1,16 MiB di VRAM** (margine 4 righe) e nient'altro.
   Il progetto dell'audit 33 avrebbe pagato una copia DtoD per forward su **ogni**
   forward per servire il 13% che ne ha bisogno.
3. La patch e' dietro `LLAMA_KV_ROLLBACK_PARZIALE`, **spenta di default**, e ha una
   posizione intermedia (`LLAMA_KV_ROLLBACK_SOLO_ANELLO`) che alloca il margine ma
   continua a rifiutare il rollback: serve a separare "l'anello piu' largo cambia i
   numeri" da "il rollback cambia i numeri" **prima** di guardare il t/s.
4. `PART` non e' dichiarato globalmente. Il probe resta a FULL, i checkpoint restano
   la rete di sicurezza, e il riuso del prompt a `server-context.cpp:3404` non e'
   toccato. La via nuova e' una **API nuova e separata** (`llama_memory_seq_rm_tail`)
   che il probe non usa e non puo' attivare.
5. **Correzione al premio atteso dell'audit 33**: la banda 13,2-14,3 non e' raggiungibile
   con questa patch. Il termine `C_save` **resta pagato** (il checkpoint continua a
   essere salvato come ritirata), e quando lo si tiene su entrambi i lati il conto
   si chiude a **13,44 t/s indipendentemente da `C_save`**. Atteso onesto:
   **13,2-13,7, centro 13,44, cioe' +4,8%** da 12,83. La meta' alta della banda
   dell'audit 33 richiede un secondo passo (smettere di salvare il checkpoint), che
   ho lasciato indietro apposta — vedi §5.

---

## 1. Dove l'audit 33 sbaglia il rimedio (e perche' il suo falsificatore era quello giusto)

L'audit 33 individua esattamente il punto: `state_size` e' dimensionato sulla
finestra di lettura del commit e **non c'e' margine gratuito**. Da li' conclude che
serve il delta, cioe' fotografare le B righe prima del forward e ripristinarle
selettivamente dopo.

La conclusione non segue dalla premessa. Il conto, riga per riga sul codice
[MISURATO, `llama-kv-cache-dsv4.cpp:504-575`]:

- ogni posizione `pos` scrive la riga `pos % S` (`state_source_idx`, `:518,537`);
- il commit di un blocco a `pos` rilegge le posizioni `[pos+1-2*ratio, pos]` con
  sovrapposizione (CSA e LID, `:560-568`) o `[pos+1-ratio, pos]` senza (HCA, `:570`);
- CSA e LID: `ratio = 4`, `S = 2*ratio = 8`. HCA: `ratio = 128`, `S = ratio = 128`.
  Le finestre coincidono con l'anello: margine zero, come dice l'audit 33.

Ma la domanda giusta non e' "quali righe distrugge il forward", e' **"quali righe
servono dopo il riavvolgimento"**. Dopo un rollback a `p0` il ri-forward riparte da
`p0`, e la sua lettura piu' profonda arriva a `p0 + 1 - 2*ratio`. Il forward annullato
di B posizioni ha distrutto le righe che contenevano le posizioni
`[p0-S, p0+B-1-S]`. Le due cose sono disgiunte se e solo se

```
p0 + B - 1 - S  <  p0 + 1 - 2*ratio     cioe'     S >= 2*ratio + B
```

Cioe': **il delta serve solo perche' l'anello e' stretto di B righe.** Allargarlo di
M righe rende il riavvolgimento gratuito fino a profondita' M. Le righe delle
posizioni annullate restano scritte e sbagliate, ma **nessuno le rilegge**: le sole
letture di posizioni `>= p0` dopo il riavvolgimento sono quelle dell'ubatch corrente,
che passano dalle righe di scratch e non dall'anello (`state_source_idx`, `:512-515`),
e quando quelle posizioni tornano vengono riscritte prima di poter essere lette.

E' anche piu' corretto dell'alternativa, per la stessa ragione che l'audit 33 gia'
argomenta contro il ripristino pieno: non si tocca niente delle posizioni accettate.

**Costo del margine, misurato dalle taglie a log** [MISURATO, `c4_gate.server.log`]:
CSA 1,31 MiB / 8 righe = 168 KB per riga; HCA 10,00 MiB / 128 = 80 KB; LID 0,33 MiB
/ 8 = 42 KB. Margine 4 → **+1,16 MiB di VRAM**, e lo stesso +1,16 MiB su ogni
checkpoint salvato (11,693 → ~12,85 MiB, +10%).

## 2. Il rischio che l'audit 33 segnalava come aperto: la SWA grezza. E' chiuso, e va bene

L'audit 33 dichiara il margine di pruning della SWA raw come "l'unico punto di
correttezza aperto". L'ho letto [MISURATO, `llama-kv-cache.cpp:1045-1064`,
`1100-1176`, `llama-hparams.h:375-409`]. Il verdetto e' **favorevole, con margine
esattamente zero e dalla parte giusta**:

- `find_slot` ricicla una cella occupata se e solo se
  `is_masked_swa(n_swa, tipo, pos_cella, pos_max_prima + 1)`, cioe' — per SWA
  standard — `pos_cella <= P - n_swa`, dove `P` e' la **prima posizione del nuovo
  ubatch**;
- una query a posizione `Q` vede le celle con `pos_cella > Q - n_swa`;
- dopo il riavvolgimento tutte le query stanno a `Q >= p0 >= P`, quindi chiedono
  `pos_cella > P - n_swa`. **Disgiunto dall'insieme riciclato, senza margine e senza
  eccezioni.** Vale identico per SWA chunked.
- `apply_ubatch` fa anche una purga esplicita di tutto cio' che sta sotto la cella
  riciclata (`:1150-1168`), per l'invariante di contiguita': stesse posizioni, gia'
  invisibili. Non cambia il conto.

Il prezzo di questa garanzia e' che il riavvolgimento **non deve scendere sotto la
prima posizione dell'ultimo ubatch**. E' il secondo guardiano della patch, e nel
ciclo speculativo non morde mai: `p0 = P + accettati >= P + 1` [DEDOTTO
dall'aritmetica del server, §4].

`swa_full` non serve. Non ho toccato quel ramo.

## 3. Che cosa c'e' sull'albero

### `git diff --numstat`, file per file

```
 12    0  include/llama.h
 11    0  src/llama-context.cpp
209    3  src/llama-kv-cache-dsv4.cpp
 34    0  src/llama-kv-cache-dsv4.h
  9    0  src/llama-memory.h
 53    2  tools/server/server-context.cpp
```

Verificato con scansione byte diretta: **zero byte CR** in tutti e sei i file.

- **`include/llama.h` (+12, -0)** — dichiarazione di `llama_memory_seq_rm_tail(mem,
  seq_id, p0)`, con il contratto scritto nel commento: toglie la coda **solo** se la
  memoria sa disfarla esattamente, ritorna `false` senza aver tolto niente altrimenti,
  non aborta mai. E' l'unico punto d'ingresso nuovo, ed e' separato da `seq_rm` proprio
  perche' il probe `common_context_can_seq_rm` non lo veda: il probe continua a
  chiamare `seq_rm(0,1,-1)`, continua a ricevere `false`, e il server continua a
  dichiarare FULL. **Questo e' il pezzo che protegge `server-context.cpp:3404`.**
- **`src/llama-memory.cpp`→`src/llama-context.cpp` (+11, -0)** — il wrapper C, accanto
  a `llama_memory_seq_rm`. Su `mem == nullptr` ritorna `false` (non `true` come
  `seq_rm`): "non l'ho fatto", non "non c'era niente da fare".
- **`src/llama-memory.h` (+9, -0)** — `virtual bool seq_rm_tail(...) { return false; }`
  sull'interfaccia. **Default = non supportato**, cosi' le altre cinque memorie
  (iswa, kv_cache, recurrent, hybrid, hybrid_iswa, dsa) restano bit-identiche senza
  toccarle.
- **`src/llama-kv-cache-dsv4.h` (+34, -0)** — l'override, il margine `rb_margine`, la
  leva `rb_attivo`, il confine per sequenza `rb_pos_min_ultimo`, due contatori, e il
  puntatore `kv_owner` nel contesto di batch (nullo per i contesti di reserve/update,
  che non scrivono niente).
- **`src/llama-kv-cache-dsv4.cpp` (+209, -3)** — le tre righe sostituite sono le
  taglie di `csa_state`/`hca_state`/`lid_state`, che diventano `... + rb_margine`
  (a leva spenta `rb_margine == 0`: **stessa identica taglia di oggi**). Il resto e'
  aggiunta: le funzioni della leva, `seq_rm_tail`, `rb_nota_ubatch` (chiamata da
  `apply()`, che gira subito prima del grafo), `rb_invalida` su clear / seq_rm /
  seq_cp / seq_keep / seq_add / seq_div / **state_read** (uno stato riletto non ha
  piu' relazione con l'ultimo forward), e la tracciatura del primo rifiuto per tipo.
  CSA e LID condividono il piano (`plans_lid = plans_csa`, `:2047`): **hanno la stessa
  taglia di stato per forza**, ed e' scritto nel commento perche' non venga rotto.
- **`tools/server/server-context.cpp` (+53, -2)** — due righe cambiate: la guardia
  `if (n_rollback > 0)` diventa `if (n_rollback > 0 && !rb_parziale)`, e la `seq_rm`
  sul contesto della **bozza** viene saltata quando la coda e' stata riavvolta e la
  bozza usa i checkpoint (altrimenti si abortirebbe li' per la stessa ragione per cui
  il bersaglio usa i checkpoint). Tutto il resto e' aggiunta: il tentativo di
  riavvolgimento prima del ripristino, e due contatori con la loro riga di stampa.
  **Su un rifiuto si cade nel ramo di oggi, invariato.** Su un successo si cade nel
  ramo standard gia' scritto da upstream (`common_speculative_accept` + emissione
  immediata + `seq_rm(pos_next,-1)`, che dopo il riavvolgimento e' il no-op).

### Il contorno della leva

| variabile | effetto |
|---|---|
| (nessuna) | **spento.** Anello della taglia di oggi, `seq_rm_tail` rifiuta sempre. |
| `LLAMA_KV_ROLLBACK_PARZIALE=1` | acceso, margine 4 righe. |
| `LLAMA_KV_ROLLBACK_MARGINE=<n>` | margine in righe. **Deve valere almeno n-max.** |
| `LLAMA_KV_ROLLBACK_SOLO_ANELLO=1` | anello allargato **ma rollback ancora rifiutato**. |

## 4. I cancelli, in ordine

Configurazione: quella del cancello di riferimento, n-max 1, 1200 token,
`LLAMA_SPEC_DRAFT_TOPK=1`. Le righe nuove sono a livello INFO: **non serve
`LLAMA_TRACE` per nessuno dei cancelli**, e a n-max 1 `draft acceptance` stampata
a INF **e'** p1.

### Cancello 1 — IDENTITA' (leva spenta)

Nessuna variabile nuova.

- **deve uscire**: SHA `CF2DEEA06E90`, 12,83-12,92 t/s, `draft acceptance` 0,868
  (520/599).
- **novita' attesa nel log**: una riga in piu' a fine richiesta,
  `coda riavvolta = 0 parziali / 79 ripristini (79 episodi non pieni su 599 verifiche)`.
  **Attenzione**: e' l'unica differenza visibile a leva spenta, ed e' voluta —
  misura direttamente il 79 che l'audit 33 aveva dedotto. Se il vostro cancello SHA
  digerisce il log del server invece del testo generato, questa riga lo sposta:
  in quel caso e' il cancello a doversi adattare, non la patch.
- **se cade**: il cammino normale e' stato toccato. Le uniche cose che lo attraversano
  a leva spenta sono `rb_invalida()` (uno `std::fill` su un vettore di `n_seq_max`
  elementi) e una chiamata virtuale che ritorna `false`. Guardare li'.

### Cancello 2 — L'ANELLO NUDO (il cancello che separa "gira" da "cambia")

`LLAMA_KV_ROLLBACK_PARZIALE=1 LLAMA_KV_ROLLBACK_SOLO_ANELLO=1`

- **deve uscire**: `rollback parziale KV: margine anello = 4 righe ... -- SOLO ANELLO:
  il rollback resta rifiutato` all'avvio, e poi **di nuovo SHA `CF2DEEA06E90`,
  12,83-12,92 t/s, `coda riavvolta = 0 parziali / 79 ripristini`.**
- **cosa prova**: che allargare l'anello e' numericamente neutro. La mappa `pos % S`
  cambia tutti gli indici di riga, ma ogni riga resta scritta dalla sua posizione e
  letta dalla stessa: i **valori** letti sono identici [DEDOTTO]. Se il testo cambia
  QUI, la premessa dell'anello e' falsa e tutto il resto e' nullo — e lo si sa **senza
  che il rollback confonda la misura**.
- **prezzo atteso**: +1,16 MiB di VRAM, checkpoint da 11,693 a ~12,85 MiB (la taglia
  e' gia' stampata: `size = %.3f MiB`). Il t/s puo' scendere di ~0,1-0,5% se `C_save`
  e' dominato dai byte invece che dalla latenza per chiamata; se scende di piu' di
  cosi', **quel dato e' interessante di suo**: vuol dire che `C_save` e' grosso, e
  allora il passo lasciato indietro (§5) vale molto piu' di quanto stimo.

### Cancello 3 — IL MECCANISMO GIRA (leggere i contatori PRIMA del t/s)

`LLAMA_KV_ROLLBACK_PARZIALE=1`

- **deve uscire, e va guardato in quest'ordine**:
  1. `coda riavvolta = ~85 parziali / 0 ripristini`. Il numero e' [ATTESO]:
     ~641 episodi × (1 − 0,868) = 85. **Zero ripristini e' la condizione, non un
     dettaglio.**
  2. se `parziali == 0`: il meccanismo non gira. Il motivo e' gia' nel log, riga
     `dsv4: coda NON riavvolgibile (<motivo>)`, che stampa il **primo rifiuto di
     ogni tipo** — sono tre cause con tre rimedi diversi (coda piu' lunga del margine
     → alzare `LLAMA_KV_ROLLBACK_MARGINE`; coda fuori dall'ultimo ubatch → il
     confine SWA, e allora l'aritmetica del §2 e' sbagliata; la cache grezza ha
     rifiutato → guardare `llama_kv_cache_iswa`).
  3. se `parziali > 0` **ma anche** `ripristini > 0`: meccanismo parziale, stesso
     log, stesso ragionamento. **Ne' zero ne' tutti e' il secondo difetto** che il
     mandato chiede di riconoscere.
  4. `n_draft_verif_steps` deve salire da 599 a ~641 e `n_draft_total` con lui:
     e' la controprova aritmetica che gli episodi sono aumentati e i forward
     diminuiti (678 → 641). Se le verifiche restano 599, il ramo standard non e'
     stato preso.
- **poi** il t/s: **atteso 13,2-13,7, centro 13,44** [DEDOTTO, §6]. Sotto 13,2 il
  modello di costo e' falsificato e il candidato numero uno e' p1 post-rigetto.
- **correttezza**: `draft acceptance` deve restare 0,84-0,90. Se p1 crolla, il
  riavvolgimento e' sbagliato e la via si chiude.
- **il cancello di correttezza forte, quasi gratis**: confrontare il **testo** con
  quello del cancello 1. Il mondo riparato calcola la **stessa** sequenza, solo
  schedulata meglio: se il riavvolgimento e' giusto, il testo deve coincidere per
  molti token, e una divergenza va cercata tardi e attribuita al rumore in virgola
  mobile (il collocamento delle celle SWA dopo un riavvolgimento non e' identico a
  quello dopo un ripristino, e l'ordine di riduzione nell'attenzione con lui). **Una
  divergenza nei primi token non e' rumore: e' un difetto.** Se lo SHA resta
  `CF2DEEA06E90` anche qui, e' la prova di correttezza piu' forte che possiamo avere,
  ma non la pretendo come cancello.

### Cancello 4 — opzionale, chiude l'incognita dell'audit 33

`LLAMA_KV_ROLLBACK_PARZIALE=1 LLAMA_CKPT_CRONO=1` (il cronometro esiste gia',
`server-context.cpp:3022`)

- da' `C_save` in ms medi. Non cambia il verdetto di stasera: **decide quanto vale
  il passo lasciato indietro**, che e' `C_save × ~641` per 1200 token. Se `C_save`
  e' 8 ms, sono altri 5,1 s su 93 → il secondo +5%.

### Il numero atteso, in una riga

**79 ripristini → 0**, sostituiti da **~85 riavvolgimenti a costo nullo**; forward da
678 a ~641 (−5,5%); **t/s 12,83-12,92 → 13,44 [ATTESO], banda 13,2-13,7.**

## 5. Cosa ho lasciato indietro, e perche'

1. **Il checkpoint continua a essere salvato a ogni episodio** (11,7 → 12,85 MiB di
   D2H, 641 volte). E' la ritirata: se `seq_rm_tail` rifiuta, il ramo di oggi deve
   funzionare. Toglierlo vale `C_save × 641` — potenzialmente quanto tutta questa
   patch — ma renderlo sicuro richiede che il rifiuto diventi un **errore duro**
   (senza checkpoint, `load_tgt` ripristinerebbe uno stato vecchio e corromperebbe in
   silenzio). Il pezzo giusto da costruire dopo, **e solo dopo che il cancello 3 ha
   mostrato zero ripristini su una corsa intera**. Questa e' anche la ragione per cui
   correggo la banda dell'audit 33: la sua riga "anche questo sparisce con la
   riparazione" e' vera solo con quel secondo passo.
2. **Non ho fatto lo snapshot dell'anello** (il passo 2.1 del progetto dell'audit 33).
   Se il cancello 2 dovesse cadere — cioe' se allargare l'anello cambiasse i numeri —
   quel progetto torna in gioco, ma allora sarebbe da capire prima *perche'*, perche'
   significherebbe che qualcosa legge l'anello per indice assoluto e non per posizione.
3. **n-max >= 2 non e' stato pensato oltre il margine.** La profondita' di
   riavvolgimento e' `n_rollback <= n_draft <= n-max`, quindi margine 4 copre fino a
   n-max 4. A n-max piu' alto va alzato `LLAMA_KV_ROLLBACK_MARGINE`, e il contatore
   lo dice subito (rifiuto "coda piu' lunga del margine").
4. **Il contesto della bozza non riavvolge**: dopo un riavvolgimento sul bersaglio, la
   coda resta nel contesto della bozza e viene ripulita dal ripristino di inizio ciclo
   (`TAG_SPEC_AVOID_DRAFT_REEVAL`), come oggi. Non ho toccato quel cammino.
5. **Non ho compilato e non ho eseguito niente.** Il rischio residuo e' di
   compilazione, e i punti piu' probabili sono l'ordine della lista d'inizializzazione
   di `llama_kv_cache_dsv4_context` (`kv_owner` e' dichiarato prima di `ubatches` e
   inizializzato prima, apposta) e la firma di `pos_next(int64_t)`.

## 6. Il conto rifatto (perche' 13,44 e non 14,3)

Modello a episodi dell'audit 33, con la sola differenza che `C_save` resta pagato
anche nel mondo riparato. Base `c2_f5` [MISURATO]: T = 93.557 ms, E = 599, R = 79,
T_bozza = 8,43 ms, p1 = 0,868, T/E = 156,2 ms.

```
oggi:      T/E  = T_bozza + C_save + (1 + R/E)·T_fwd + (R/E)·C_load   = 156,2
riparato:  T'/E = T_bozza + C_save + T_fwd  =  T/E − (R/E)·(T_fwd + C_load)
           token per episodio: da 2,004 a 1 + p1 = 1,868
```

Il termine tolto e' `0,132·(T_fwd + C_load)`, e il fit conserva la somma: qualunque
ipotesi su `C_save`/`C_load`, `T_fwd + C_load` esce ~130,6 ms e
`T'/E = 156,2 − 17,2 = 139,0 ms`.

| `C_save` = `C_load` | T_fwd fittato | T'/E | t/s riparato |
|---|---:|---:|---:|
| 0 ms  | 130,5 | 139,0 | **13,44** |
| 4 ms  | 126,6 | 139,0 | **13,44** |
| 8 ms  | 122,6 | 139,0 | **13,44** |

**Il premio e' insensibile al costo del checkpoint**, perche' il checkpoint si paga
da entrambe le parti. La banda residua e' tutta p1 post-rigetto: con p1' globale a
0,83 si scende a 13,17, con 0,90 si sale a 13,67. Da qui **13,2-13,7**.

L'audit 33 arrivava a 14,25 perche' nel mondo riparato azzerava anche `C_save`.
Quello e' il passo 5.1, non questo.

Il tetto della base resta quello dell'audit 33 (~14,4): questa patch incassa
**il 55-60% della distanza dal tetto**, non tutta.
