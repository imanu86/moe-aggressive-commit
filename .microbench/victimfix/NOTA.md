# VICTIMFIX — preferenza effettiva per la vittima esperto

Data: 2026-07-30.

## Esito

`victimfix.patch` introduce il flag opt-in:

```text
DS4_CUDA_VRAM_PREFER_EXPERT_VICTIM=1
```

Il flag accetta soltanto la stringa esatta `1`; il default è spento. La patch
tocca soltanto `ds4-p4a/ds4_cuda.cu` e non è stata applicata ai sorgenti.
Non sono stati compilati binari e non è stato avviato alcun server.

Il fix non si limita a riordinare due classi già presenti nel selettore. Nel
run patologico non esisteva infatti alcun range esperto candidabile:
`evict_expert=0` per tutte e quattro le richieste. Gli esperti utili erano
nello slab residente separato da 140 slot, non in `g_model_ranges`. La patch:

1. per un richiedente non esperto ripete la ricerca sui range esperto
   streamed con una finestra di recency meno larga, scegliendo sempre l'LRU;
2. se anche questa ricerca è vuota, prova a cedere in sicurezza l'intero slab
   residente-esperti, usando la meccanica di quiescenza e ricostruzione
   dimezzata già presente per PIN2 ma preservando esplicitamente l'autorità
   host di TURNO2FIX;
3. ricade sul backbone soltanto se nessuna delle due forme di residenza
   esperto è reclamabile in sicurezza.

## Preimage e SHA-256 correnti

Gli hash sono stati ricalcolati sul tree realmente presente, non copiati dal
mandato:

| file | SHA-256 corrente |
|---|---|
| `ds4-p4a/ds4.c` | `c4bdf27f63e290a67fcd180c5c19783c6bc09fff535d227809b1d01ed7691f06` |
| `ds4-p4a/ds4_cuda.cu` | `7c011c08293701088f0211ea87fc8b8361bb407992d1f8ce2103db6dbf29c7f3` |

Il secondo hash è diverso da `9cd020...` riportato nel mandato. La patch è
costruita e verificata contro il file corrente `7c011c...`, che include il
build-fix TURNO2FIX ora presente.

Tutti i riferimenti `ds4_cuda.cu:riga` sotto sono alla preimage corrente.

## Evidenza del guasto

Il contatore è cumulativo; i delta per richiesta nei log indicati dal mandato
sono:

| run/richiesta | righe start/end | `evict_backbone` start→end | delta |
|---|---:|---:|---:|
| `T1_richieste` 1 | 1174 / 11975 | 70→888 | 818 |
| `T1_richieste` 2 | 12849 / 15029 | 888→888 | 0 |
| `T1_richieste` 3 | 17809 / 310463 | 2448→143479 | **141031** |
| `T1_richieste` 4 | 347421 / 420338 | 161510→196495 | **34985** |
| `T1b_stesso_dominio` 2 | 12852 / 15032 | 891→891 | 0 |
| `T1b_stesso_dominio` 3 | 16088 / 18318 | 891→891 | 0 |

`T1b` finisce a 891 sfratti complessivi. Nel finale della richiesta 3
patologica, `backbone_reloads=143406` contro `evict_backbone=143479`: il
rapporto quasi uno-a-uno conferma il ping-pong, non una crescita una tantum.

La riga evento nasce in
`cuda_vram_prio_account_eviction()` a
`ds4-p4a/ds4_cuda.cu:8814-8835`. Il selettore effettivo è
`cuda_model_pick_victim()` a `:8877-8920`; viene invocato dal ciclo di
`cuda_model_stream_alloc()` a `:9120-9249`, precisamente a `:9169`, e la
vittima viene classificata/contata a `:9232-9244`.

La classificazione è già affidabile:

- `cuda_model_range::pinned` a `:2136-2150`: `0` è un range esperto,
  `1` è backbone/non-esperto;
- il valore nasce da `what`: soltanto il prefisso `moe_` è esperto
  (`:9262`, registrazione a `:9341-9345`);
- il picker prova prima `pinned=0`, poi `pinned=1` (`:8901-8918`).

Il difetto osservato non è quindi che il tier backbone preceda formalmente il
tier esperto. È che il tier esperto è vuoto: i 140 esperti GPU-residenti sono
in un'unica allocazione contigua `g_moe_expert_cache`, fuori da
`g_model_ranges`. Il log lo prova direttamente: alla fine della richiesta 3
`expert_slots_current=140`, `expert_slots_resident=140`, ma
`evict_expert=0`.

Gli ulteriori 4423 slot preservati appartengono invece alla dynamic arena con
backing host. La preservazione conserva binding/generation di quei byte e
spiega il cambio di working set, ma non offre memoria al `cudaMalloc` denso:
rilasciarla non sarebbe una vittima VRAM e toccherebbe inutilmente
TURNO2FIX.

## Policy della patch

### Perimetro del richiedente

La preferenza è armata solo se il richiedente non è un expert weight.
La classificazione riusa esattamente il criterio esistente:

```text
requester_is_expert = requester != NULL && starts_with(requester, "moe_")
```

Quindi `f16`, `q8_0`, `q8_hc_expand`, `shared_down_hc_expand`,
`attn_out_*`, `indexer_f16` e i buffer `moe gather ...` sono allocazioni
non-expert per questo contratto; i soli `moe_*` sono richieste di pesi
esperto.

### Primo livello: LRU fra i range esperto streamed

Il passo ordinario conserva lo scudo storico di quattro tick. Se non trova
nulla, il flag abilita il passo rilassato già disponibile nel codice:

```text
last_used_tick <= g_model_tick - DS4_CUDA_VRAM_EXPERT_SHIELD_TICKS
```

Il default dello shield è 2 e il minimo accettato è 1
(`ds4_cuda.cu:8576-8597`). Fra i candidati viene scelto il
`last_used_tick` minimo (`:8905-8917`), quindi il criterio è **LRU fra gli
esperti sicuri**.

Non viene usata `frequency`: `cuda_model_range` possiede già
`last_used_tick` ma non una frequenza. Il campo `frequency` esistente
appartiene al tiering/dynamic arena host e non descrive la vita dei range
streamed; collegarlo qui richiederebbe una nuova mappa concorrente e
mescolerebbe due autorità diverse.

### Secondo livello: slab residente-esperti

Se il picker arriva comunque a una vittima backbone, la patch tenta
`cuda_vram_pin_shed_expert_cache()` prima di sfrattarla. Il singolo slot dello
slab ha un'`age` e può essere rimpiazzato logicamente, ma lo slab è una sola
`cudaMalloc` con piani gate/up/down a pitch fisso: invalidare uno slot non
restituisce un byte al driver CUDA. Per questo non esiste un criterio LRU
individuale capace di soddisfare la richiesta densa.

La vittima fisica minima con il layout corrente è dunque **l'intero slab
esperti**. Con 140 slot libera:

```text
140 × 7.077.888 B = 990.904.320 B = 945 MiB
```

Non viene introdotto un allocator nuovo. Dopo la cessione, la prima
`cuda_moe_expert_cache_prepare()` ricostruisce lo slab al massimo a metà
capacità; eventuali nuove pressioni producono 140→70→35→… e infine exact
selected-load, invece di ripristinare subito la sovrasottoscrizione.

Questa scelta è coerente anche economicamente: il backbone è circa
7.742.323.036 B e viene letto quasi integralmente ogni token, mentre un
esperto da 7.077.888 B viene letto soltanto se selezionato.

## Invarianti di correttezza

### Range esperto streamed

Un range viene inserito in `g_model_ranges` soltanto dopo il completamento
dell'upload (`cudaStreamSynchronize(g_model_upload_stream)` a
`ds4_cuda.cu:9333-9339`). Il passo rilassato non considera mai il tick
corrente: shield `>=1` impedisce di invalidare un puntatore appena consegnato
ma non ancora usato.

Lo sfratto non riusa né libera immediatamente il buffer. A
`:8923-8932` il codice documenta che tutti i lettori di questi pesi usano
stream 0; `cuda_stream_pool_push()` registra un evento sullo stesso stream
(`:8955-8968`) e il buffer può essere riusato o liberato soltanto dopo
l'evento (`:8971-9019`). Le letture già accodate restano quindi protette.
Una `pread` non scrive nel range vittima: alimenta staging/upload separati e
l'inserimento nel registro avviene soltanto dopo il loro drain.

### Slab residente

La cessione usa le cinture già presenti a
`cuda_vram_pin_shed_expert_cache()` (`ds4_cuda.cu:38602-38696`):

1. `route_submitted_sequence == route_completed_sequence`; altrimenti la
   cessione è rinviata;
2. `cudaStreamSynchronize(0)` prova che nessun kernel MoE legge più lo slab;
3. prima del release, `cuda_moe_expert_cache_invalidate()` demote ogni slot
   `VALID` da `VRAM_PROTECTED` a `RAM_WARM`, `RAM_PROBATION` o `SSD_COLD`
   secondo il binding già verificato (`:38487-38579`), e azzera le mappe
   cache host/device;
4. `cuda_moe_expert_cache_release()` cancella e join-a il route worker e
   drena l'upload stream prima dei `cudaFree`;
5. dopo il release, `capacity`, `packed_base`, `gate`, `up` e `down` devono
   essere tutti nulli/zero; in caso contrario la cessione è fallita.

Il release storico chiama `cuda_moe_tiering_report_and_reset(1)`
(`:39227`), che attraverso `cuda_q1_0_ssd_wrap_tier_reset_begin()` libera
anche gli slot host posseduti e azzera `g_moe_tiering`
(`:33953-34159`, `:35934-35939`). Sarebbe incompatibile con i 4423 binding
preservati. La patch aggiunge quindi un parametro interno
`preserve_tiering`: vale `1` soltanto per una cessione VICTIMFIX, dopo la
demozione coerente descritta sopra, e salta esclusivamente quel reset.
Tutte le chiamate storiche usano il default `0` e restano identiche. Non
vengono modificati né il preservatore né le sue generation.

Se una qualunque prova fallisce, lo slab non viene contato come vittima e
resta intatto. Soltanto allora il codice può fare fail-open sul backbone,
incrementando `victim_backbone_no_safe_expert`. Non viene mai liberato un
buffer sul quale sia dimostrata una route, una copia H2D o una lettura kernel
pendente.

## Contatori

La riga aggiuntiva è:

```text
ds4: [victimfix] phase=... prefer_expert_victim=...
  victim_expert=...
  victim_backbone_no_safe_expert=...
  victim_backbone_flag_off=...
  victim_backbone_expert_requester=...
```

I primi tre campi realizzano la distinzione richiesta:

| contatore | incremento |
|---|---|
| `victim_expert` | range esperto streamed realmente sfrattato oppure slab esperti ceduto con successo |
| `victim_backbone_no_safe_expert` | flag attivo, richiedente non esperto, entrambe le categorie esperto non sicure/assenti, backbone realmente sfrattato |
| `victim_backbone_flag_off` | backbone realmente sfrattato con il flag di preferenza spento |

Il quarto campo separa il caso fuori perimetro in cui il flag è acceso ma il
richiedente è esso stesso `moe_*`; evita di attribuirlo falsamente a
“nessun esperto sicuro”.

Con il flag di comportamento acceso la riga viene emessa a decode-start e
request-end. Per osservare il contatore di controllo con comportamento
spento si può impostare esplicitamente:

```text
DS4_CUDA_VRAM_PREFER_EXPERT_VICTIM_LOG=1
```

Questo secondo flag abilita soltanto la riga diagnostica. Con entrambi i flag
assenti non viene aggiunto alcun byte a stderr.

## Neutralità a flag spento

Con `DS4_CUDA_VRAM_PREFER_EXPERT_VICTIM` assente, vuoto, `0` o diverso da
`1`:

- `cuda_model_pick_victim(false)` salta il passo aggiuntivo e conserva
  predicati, ordine e tie-break originali;
- la cessione dello slab non diventa raggiungibile per VICTIMFIX;
- PIN2, se attivato separatamente, conserva comportamento e testo delle
  proprie righe (`%s` riceve ancora esattamente `PIN`);
- ammissione, hot-reserve, transiente/deadline, host-pin, preservazione,
  nextnfix e indexerzc non sono toccati;
- senza il log gate esplicito non compare la riga `[victimfix]`.

Le sole nuove operazioni nel percorso OFF sono letture di interi memoizzati e
incrementi diagnostici file-local; puntatori, byte scelti, allocazioni,
fallback e stderr restano quelli della preimage.

## Criterio di accettazione

Collaudo non eseguito per il vincolo esplicito di non compilare e non avviare
server.

Usare sullo stesso binario:

```text
DS4_CUDA_PRESERVE_ACROSS_REQUESTS=1
DS4_CUDA_VRAM_PREFER_EXPERT_VICTIM=1
```

Eseguire quattro richieste consecutive sullo stesso server: due famiglie,
due turni ciascuna, cap 128/32.

Accettazione obbligatoria:

1. **4/4 richieste OK**;
2. nella richiesta 3, delta `evict_backbone` sotto le migliaia, non 141031;
3. riferimento sano: `T1b_stesso_dominio`, 891 sfratti complessivi;
4. a request-end `victim_expert > 0`;
5. `victim_backbone_no_safe_expert` basso e coerente con gli eventuali
   `reason=no-expert-victim`, che devono crollare;
6. `backbone_reloads` non deve più inseguire `evict_backbone` con rapporto
   quasi uno-a-uno.

Controllo di neutralità: stesso protocollo con entrambi i flag VICTIMFIX
assenti; raw response e stderr devono coincidere byte-per-byte con la
preimage. Per il solo confronto dei tre contatori, ripetere il controllo con
`DS4_CUDA_VRAM_PREFER_EXPERT_VICTIM_LOG=1`, accettando come unica differenza
la riga diagnostica richiesta esplicitamente.

## Verifica statica e perimetro

```text
git apply --check --whitespace=error-all .microbench/victimfix/victimfix.patch
OK

git apply --numstat .microbench/victimfix/victimfix.patch
121  29  ds4-p4a/ds4_cuda.cu
```

SHA-256 di `victimfix.patch`:
`3e79130639a96306cba6e4dff0b18f8bc46deadbb81359df511680cac4bd9b9b`.

La patch non contiene hunk in `ds4.c`, transiente/deadline, host-pin,
TURNO2FIX, ADMIT/hot-reserve, nextnfix o indexerzc. I soli file scritti sono
questa nota e `victimfix.patch`.
