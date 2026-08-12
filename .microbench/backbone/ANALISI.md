# Pin del backbone: analisi e patch sperimentale

## Esito in breve

La direzione generale e' corretta, ma due premesse vanno corrette.

1. `states_vram=0` non significa che la cache expert occupi zero VRAM. Lo slab
   e' allocato per `capacity`, non per `count`: una cache da 140 slot logicamente
   vuota continua a prenotare 990.904.320 byte (945 MiB).
2. Il selettore citato intorno a `ds4_cuda.cu:33171` non e' il selettore delle
   vittime VRAM del backbone. E' il selettore degli slot della dynamic arena in
   RAM. Il selettore che incrementa `evict_backbone` e'
   `cuda_model_pick_victim()`.

`pin.patch` introduce `DS4_CUDA_PIN_BACKBONE=1`. Quando il selettore ordinario
arriva alla vittima pinned:

- blocca quella vittima;
- usa ancora eventuali range expert streamed non pinned;
- se non ce ne sono, quiesce il route worker e cede l'intero slab resident
  expert, poi lascia il resto della richiesta all'exact selected-load;
- se lo slab non esiste o non puo' essere liberato in sicurezza, fa fail-open
  sul backbone e lo dichiara come `PIN ESCAPE`, invece di trasformare il caso in
  un OOM opaco.

Il sacrificio e' dell'intero slab, non di un singolo expert. Con l'allocazione
contigua attuale un singolo slot puo' essere sovrascritto, ma non restituito al
driver CUDA. Una cache riducibile slot per slot richiederebbe un allocator
diverso o un re-pack/realloc quiescente; sarebbe una modifica di struttura e
dimensionamento, fuori dal mandato.

Quindi il flag e' un pin forte finche' esiste una categoria expert
reclamabile. Non puo' essere contemporaneamente un pin assoluto e garantire
forward progress quando nessuna categoria puo' cedere: il runtime non ha un
backend CPU/external-memory per i pesi dense mancanti. La patch rende questo
confine esplicito e misurabile.

## 1. Chi decide oggi che backbone ed expert sono sfrattabili

### Il percorso corretto

La classificazione nasce in `ds4-p4a/ds4_cuda.cu:8341-8350`:

```cpp
const int is_hot = (what == NULL) || (strncmp(what, "moe_", 4) != 0);
...
cuda_model_stream_alloc(...);
```

Il range appena caricato viene registrato con `pinned=is_hot` in
`ds4-p4a/ds4_cuda.cu:8419-8422`. La struttura documenta esplicitamente il
significato: non-expert pinned, expert non pinned
(`ds4-p4a/ds4_cuda.cu:1880-1896`).

La decisione effettiva e' in
`ds4-p4a/ds4_cuda.cu:8141-8169`:

- pass 0: soli range non pinned;
- pass 1: ancora soli non pinned, con recency rilassata se
  `DS4_CUDA_VRAM_INVERTED_PRIORITY=1`;
- pass 2: soli pinned, cioe' il backbone, come ultima risorsa.

Il ciclo di allocazione chiama quel selettore in
`ds4-p4a/ds4_cuda.cu:8289-8323`; subito prima prova il pool di riciclo, subito
dopo incrementa il contatore e rimuove il range.

Quindi la policy non dice in astratto "gli expert sono intoccabili". Dice
"prima i range streamed non pinned, poi i pinned". Il problema e' che gli
expert del percorso corrente quasi mai sono range del pool:

- il selected-load expert streamma direttamente in buffer posseduti dal
  chiamante, senza `cudaMalloc`, eviction o inserimento in `g_model_ranges`
  (`ds4-p4a/ds4_cuda.cu:41677-41682`);
- la cache resident expert e' uno slab separato
  (`ds4-p4a/ds4_cuda.cu:28390-28430`);
- per questo `cuda_model_pick_victim()` non vede ne' gli slot resident ne' i
  transient buffer, e `evict_expert=0` e' il risultato naturale.

`evict_expert` conta dunque range `moe_*` streamed rimossi da
`g_model_ranges`; non conta sostituzioni logiche della resident cache.

### Il percorso a 33171 non decide questa eviction

I predicati su reference attive, slot WRAP riservati, `last_call` e
`reclaimable_vram_backing` sono in
`cuda_moe_tiering_pick_ram_slot()` e nella sua variante, oggi a
`ds4-p4a/ds4_cuda.cu:33501-33610` e
`ds4-p4a/ds4_cuda.cu:33638-33731`.

Quelle funzioni scelgono uno slot di `g_dynamic_arena.slots`, cioe' backing
expert in RAM. In particolare, `reclaimable_vram_backing` a
`ds4-p4a/ds4_cuda.cu:33671-33685` permette di sacrificare la copia RAM quando
esiste gia' la copia esatta in VRAM. Non rende reclamabile la VRAM e non consulta
`g_model_ranges`.

Toccare quel percorso non cambierebbe `evict_backbone`; cambierebbe la
residenza RAM/admission, vietata dal mandato.

## 2. Da dove viene il fondo di circa 730 eviction

### Correzione: cache logicamente vuota, slab fisicamente pieno

`capacity` e `count` sono campi distinti
(`ds4-p4a/ds4_cuda.cu:28404-28406`). La memoria viene allocata una volta per
tutta la capacita':

- `per_expert = gate * 2 + down` a
  `ds4-p4a/ds4_cuda.cu:37940`;
- packed slab `capacity * per_expert` a
  `ds4-p4a/ds4_cuda.cu:38100-38115`;
- anche il layout non packed alloca tutte e tre le plane per `capacity` a
  `ds4-p4a/ds4_cuda.cu:38117-38120`.

`count` cresce quando una promozione occupa logicamente uno slot
(`ds4-p4a/ds4_cuda.cu:39219-39226`), ma nessun `cudaFree` corrisponde a
`count=0`. Il `cudaFree` dello slab avviene solo nel release della cache
(`ds4-p4a/ds4_cuda.cu:36577-36697`).

Pertanto V1 con `states_vram=0, vram_promotions=0` non elimina la pressione
expert: elimina i contenuti validi, ma conserva circa 945 MiB riservati per i
140 slot. La prova "cache vuota" non era una prova "slab assente".

### Meccanismo del fondo

Il model stream allocator ammette un nuovo range solo se
`free >= aligned + reserve` (`ds4-p4a/ds4_cuda.cu:8282-8307`). Sotto quella
soglia:

1. recupera un buffer parcheggiato;
2. cerca un range expert non pinned;
3. non trovandolo, ruota un range pinned del working set dense.

Questo produce churn anche con zero promozioni: lo slab continua a occupare
VRAM, i transient expert non sono nel pool vittime, e il working set dense
eccede il budget disponibile al picco. Il valore circa uno per token e'
compatibile con una rotazione ricorrente del working set, non con eviction
degli slot resident expert.

### Limite della telemetria esistente

La vecchia riga:

```text
ANOMALY ... what=q8_0 reason=no-expert-victim
```

non identifica la vittima. `what` e' il nome della nuova allocazione passato da
`cuda_model_stream_alloc()` a `cuda_vram_prio_account_eviction()`
(`ds4-p4a/ds4_cuda.cu:8317-8320`); la funzione non riceve il nome della vittima
(`ds4-p4a/ds4_cuda.cu:8064-8084`). Quindi i conteggi per `q8_0`,
`attn_out_a`, `f16_pair*` osservati finora sono categorie che hanno richiesto
spazio, non prova che quei tensori fossero i range espulsi.

La conclusione stretta sostenuta dal codice e' quindi:

- il fondo e' innescato da miss/allocazioni dense nel model stream cache;
- sopravvive a `states_vram=0` perche' lo slab da 140 slot resta allocato;
- la quota esatta attenzione/indexer/altro non e' ricostruibile dai log
  rate-limited esistenti.

La patch rinomina correttamente il campo in `requester`, aggiunge
`victim_category=backbone` e `victim_offset`, e rende attribuibile il prossimo
run senza pretendere che i dati vecchi dicano piu' di quanto dicono.

## 3. Chi cede con il pin e cosa succede all'esaurimento

L'ordine ON e':

1. pool di buffer event-fenced gia' esistente;
2. range expert streamed non pinned, se presenti;
3. intero resident-expert slab;
4. exact selected-load per il resto della richiesta;
5. solo se 1-4 non sono disponibili/sicuri, `PIN ESCAPE` sul backbone.

Il punto 3 usa il release gia' esistente, che cancella/join-a il worker e
quiesce il suo upload stream prima dei `cudaFree`
(`ds4-p4a/ds4_cuda.cu:36577-36597` e
`ds4-p4a/ds4_cuda.cu:31020-31113`). Se la quiescenza non e' dimostrabile, il
runtime mantiene il safe leak e la patch conta
`pin_expert_cache_shed_failures`.

Dopo lo shed, `cuda_moe_expert_cache_prepare()` viene chiusa per il resto della
richiesta. Nel ramo G73 l'exact selected-load era gia' il fallback
(`ds4-p4a/ds4_cuda.cu:46749-46770`). La patch apre lo stesso fallback esatto
nel ramo non-G73 solo quando lo shed e' avvenuto; il comportamento fail-closed
originale resta identico in tutti gli altri casi. I nested-residual GPU cache
restano fail-closed: non sono degradabili con selected-load senza violarne il
contratto.

Al request-end lo stato "shed" viene riarmato, cosi' una richiesta successiva
puo' ricostruire la cache. I contatori restano cumulativi come gli attuali
`evict_*`.

Se non esiste nemmeno una vittima pinned (per esempio tutti i range sono dentro
la finestra di recency), il chiamante riceve il fallback `NULL` gia' previsto
dal percorso originale e la patch emette `PIN EXHAUSTED`. Eliminare anche
questo ultimo limite richiederebbe un backend dense alternativo o spendere la
riserva di allocazione: entrambe sono leve diverse dall'eleggibilita' delle
vittime.

## Telemetria aggiunta

La riga `[vram-prio]` aggiunge:

- `pin_backbone`: stato del flag;
- `pin_backbone_blocked`: candidate backbone fermate dal pin;
- `pin_expert_range_ceded`: range expert streamed che hanno ceduto;
- `pin_expert_cache_sheds`: numero di slab ceduti;
- `pin_expert_cache_slots_ceded`: capacita' fisica sacrificata;
- `pin_expert_cache_resident_ceded`: slot logicamente resident al momento;
- `pin_expert_cache_bytes_ceded`: soli byte del resident slab;
- `pin_expert_cache_shed_failures`: worker/slab non liberabile;
- `pin_exact_stream_fallbacks`: layer serviti dal degrado esatto;
- `pin_backbone_failopen`: eviction backbone avvenute comunque;
- `pin_no_victim`: nessuna categoria disponibile.

Le righe evento distinguono esplicitamente:

```text
PIN blocked_backbone ... action=seek-expert-category
PIN degrade result=ok category=resident-expert-slab ... action=disable-cache-exact-streaming
PIN degrade category=exact-streaming ...
PIN ESCAPE category=backbone reason=no-reclaimable-expert ...
PIN EXHAUSTED category=none ...
```

Questo separa "eviction evitata dal pin", "expert/slab che ha ceduto" ed
"eviction backbone inevitabile/fail-open".

## Neutralita' a flag spento

Non ho usato un parametro del template `routed_moe_launch_impl<G73,G132>`:
l'eviction avviene nel model stream allocator globale, usato anche da
attenzione, norm, router, output e caricamento. Il template routed non domina
quel call graph; mettervi il flag lascerebbe intatto il vero selettore.

Le uscite anticipate sono:

- `cuda_model_stream_alloc`: prima viene eseguito il selettore originale; con
  `DS4_CUDA_PIN_BACKBONE` spento la nuova branch e' falsa e si percorrono gli
  stessi account/swap-erase;
- `cuda_moe_expert_cache_prepare`: l'early return scatta solo dopo uno shed ON;
- `routed_moe_launch_impl`: il bypass del fail-closed scatta solo dopo uno shed
  ON e mai per nested residual;
- request-end: nessuno stato nuovo viene scritto se il flag e' spento.

Con flag OFF:

- `cuda_model_pick_victim()` e' invariata;
- ordine e predicati delle vittime sono invariati;
- ammissione, frequenze, soglie e sizing sono invariati;
- i nuovi contatori valgono zero;
- i contatori esistenti ricevono gli stessi incrementi.

La sola differenza osservabile OFF e' diagnostica: la riga ANOMALY corregge
`what` in `requester` e aggiunge offset/categoria della vittima; `[vram-prio]`
espone i nuovi campi a zero.

## Verifica dell'aritmetica

Il valore esatto del modello e':

```text
gate 2.162.688 + up 2.162.688 + down 2.752.512
= 7.077.888 byte = 6,75 MiB per expert
```

Il codice calcola la stessa somma a `ds4-p4a/ds4_cuda.cu:37940`.

| slot | byte slab | MiB | incremento su 140 |
|---:|---:|---:|---:|
| 140 | 990.904.320 | 945,00 | - |
| 211 | 1.493.434.368 | 1.424,25 | 479,25 MiB |
| 250 | 1.769.472.000 | 1.687,50 | 742,50 MiB |

La formula "backbone 7 GB fissi + attenzione 3,3 GB -> 1,7 GB per 250 slot"
non e' valida:

1. Il backbone non e' fisso. `cuda_model_stream_alloc()` continua ad allargare
   `g_model_ranges` finche' resta la riserva
   (`ds4-p4a/ds4_cuda.cu:8282-8307`). La riga startup da circa 7,21 GiB e' una
   fotografia, non un cap.
2. I circa 3,3 GB citati nei run sono `vram_free_at_decode_start`, non una
   costante "picco attenzione". La telemetria salva proprio quella fotografia a
   `ds4-p4a/ds4_cuda.cu:30273-30309`.
3. Dal bilancio mancano contesto/driver CUDA, tensori del grafo, transient e
   sovrapprezzi di allocazione.
4. Il dato sperimentale gia' disponibile e' piu' forte della stima: aggiungere
   solo 71 slot (479,25 MiB) ha gia' prodotto il cliff a 211. Non si puo'
   dedurre che aggiungerne 110 sia sicuro.

Quello che la patch puo' verificare e':

- se cedere i 945 MiB dello slab 140 elimina il fondo circa 730;
- se cedere i 1.424,25 MiB dello slab 211 elimina il thrash catastrofico;
- se resta `pin_backbone_failopen>0` dopo lo shed, il live set dense/riserva non
  entra neppure senza resident cache.

Non puo' dimostrare "250 slot sostenuti e zero churn", perche' al primo
conflitto lo slab contiguo deve essere ceduto interamente. Quel test richiede
una resident cache fisicamente shrinkable.

## Bracci minimi per giudicare la patch

1. Controllo: tutti i flag nuovi OFF. Richiedere output hash e tutti i contatori
   preesistenti identici; i campi `pin_*` devono essere zero.
2. Pin-140: solo `DS4_CUDA_PIN_BACKBONE=1`, senza inverted/grow/elastic.
   Atteso: uno shed da 140 slot; poi exact streaming; idealmente
   `pin_backbone_failopen=0` e `evict_backbone` piatto dopo lo shed.
3. Pin-211: capacita' 211 impostata direttamente, ancora senza
   inverted/grow/elastic. Atteso: shed da 211; se il crollo era causato dal
   churn, il regime deve riprendersi dopo lo shed. Non e' un test di cache 211
   sostenuta.
4. No-slab: resident cache realmente disabilitata (`capacity=0`, non soltanto
   `states_vram=0`) + pin. Questo separa la pressione dello slab dal live set
   dense: eventuali `PIN ESCAPE` sono il fondo non expert reale.

## Applicabilita' e hash della base

Non ho compilato, avviato `ds4_server` o toccato `D:\`.

Verifica eseguita:

```text
git apply --check .microbench/backbone/pin.patch
OK
```

Il diff e' prodotto sul file corrente, gia' comprensivo della lane:

```text
ds4-p4a/ds4_cuda.cu
SHA-256 7CC4377593E054D9BD4FFB97A4091F351FE9FAD3FB8C6B89276D0A1534D0029D
git blob 67d66c5a64e7a7d4b138b972845a88bfc9fdb4bf
ds4-p4a HEAD 646f3beb77732ca286e9bf9f38cf0d63d3ecc78a
```
