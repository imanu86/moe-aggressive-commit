# FASE A — Analisi gestore VRAM a priorita' invertita (runtime DS4, Windows)

Target: `C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a\ds4_cuda.cu` (47.845 righe).
Tutti i riferimenti sono `file:riga` su quel file salvo diverso avviso.

---

## (a) Chi scegle la vittima e chi stampa `CUDA evicted streamed range`

| Cosa | Dove |
|---|---|
| Funzione che sceglie la vittima | `cuda_model_pick_victim()` — **ds4_cuda.cu:6823-6839** |
| Commento di progetto della due-tier | ds4_cuda.cu:6818-6822 |
| Allocatore che invoca lo sfratto | `cuda_model_stream_alloc()` — ds4_cuda.cu:6931-6971 |
| Chiamata di sfratto + contatore | ds4_cuda.cu:6962-6965 |
| **Log `CUDA evicted streamed range`** | **ds4_cuda.cu:6967** (gated `DS4_CUDA_WEIGHT_CACHE_VERBOSE`) |
| Rimozione range + parcheggio buffer | `cuda_model_range_evict_to_pool()` — ds4_cuda.cu:6910-6926 |
| Contatore globale | `g_model_evict_count` — ds4_cuda.cu:747 |

### CORREZIONE ALLA PREMESSA (importante)

La preferenza "prima gli esperti, il backbone solo come ultima risorsa" **esiste gia'**
ed e' esplicita nel codice (ds4_cuda.cu:6825-6837):

```c
for (int tier = 0; tier < 2; tier++) {
    ...
    if (tier == 0 && r.pinned) continue;      /* pass 1: experts only */
    if (tier == 1 && !r.pinned) continue;     /* pass 2: pinned last resort */
```

Quindi il requisito 1 *nel senso stretto di riordinare i due tier* e' già soddisfatto
**dentro `g_model_ranges`**. Il degrado 8-9x NON e' spiegato dall'ordine dei tier.

### La causa vera del degrado 8-9x

Il pool delle vittime e' **solo** `g_model_ranges` (ds4_cuda.cu:1517), che contiene
esclusivamente i *range di modello streammati*. Invece:

* la **cache esperti residente** e' uno slab contiguo separato,
  `g_moe_expert_cache.packed_base` (struct ds4_cuda.cu:26554-26680, istanza :26681),
  allocato da una `cudaMalloc` dentro `cuda_moe_expert_cache_prepare()` (:35079 e segg.);
* la **KV** e' allocata a parte e non e' mai registrata come range;

**nessuna delle due e' raggiungibile da `cuda_model_pick_victim()`.**

Conseguenza a ctx 150k con 320 slot: gli slice esperti vengono serviti dallo slab
(hit), quindi in `g_model_ranges` i range `moe_*` non pinnati sono pochissimi o
assenti -> il **tier 0 resta vuoto** -> il tier 1 sfratta **backbone contro backbone**,
a ogni token. Il fenomeno e' quindi una **sovra-sottoscrizione di capacita'**, non un
errore di ordinamento: lo slab + KV si prendono la VRAM *prima*, e al backbone resta
un residuo in cui non ci sta, cosi' si ri-streamma in loop (2066 ms/token).

### Inversione di priorita' REALE trovata (secondaria ma vera)

ds4_cuda.cu:6824 e :6831:

```c
const uint64_t pin_floor = (g_model_tick > 4u) ? (g_model_tick - 4u) : 0u;
...
if (r.last_used_tick > pin_floor) continue;
```

Lo scudo di recency a 4 tick e' applicato **a entrambe le classi**. Quindi un range
**esperto appena toccato e' protetto** mentre un range **backbone piu' freddo viene
sfrattato**: esattamente l'opposto della specifica. Questo e' correggibile a costo
quasi nullo (ed e' letteralmente il requisito 1), ma da solo **non** risolve il caso
150k, perche' se nel pool non ci sono esperti non c'e' nulla da rilassare. Va corretto
per correttezza, non come leva di performance: la leva e' il sizing.

---

## (b) Dove si decide il numero di slot della cache esperti, e chi compete per la stessa VRAM

| Cosa | Dove |
|---|---|
| Funzione di sizing/allocazione | `cuda_moe_expert_cache_prepare()` — **ds4_cuda.cu:34863** |
| **Formula della capacita'** | **ds4_cuda.cu:35045-35061** |
| Riserva (default 0.5 GiB, env `DS4_CUDA_STREAMING_EXPERT_CACHE_RESERVE_GB`) | `cuda_moe_expert_cache_reserve_bytes()` — ds4_cuda.cu:29058-29070 |
| Clamp riserva a total/2 | ds4_cuda.cu:35056 |
| Slot richiesti (env `DS4_CUDA_STREAMING_EXPERT_CACHE_N`, clamp hard 512) | `cuda_moe_expert_cache_requested()` — ds4_cuda.cu:29030-29039 |
| Guardia di riuso "config identica" (confronta `requested`, NON `capacity`) | ds4_cuda.cu:34986-35042 |

Formula attuale (:35057-35061):

```c
cap = min(requested, (free_b - reserve) / per_expert)
```

cioe' **fissata dall'env**, con `free_b` letto da `cudaMemGetInfo` in quel preciso
istante. Non tiene conto di quanto servira' al backbone.

### Chi altro compete per la stessa VRAM

1. **Cache LRU VRAM Q1 (sidecar)** — sizing a ds4_cuda.cu:34091-34128, log `[q1-vram-lru]`.
   Stesso schema `cudaMemGetInfo` meno riserva propria (:34099-34104).
2. **Allocatore dei range streammati** — riserva propria `cuda_model_stream_reserve_bytes()`
   (ds4_cuda.cu:6793-6801, **default 2048 MiB**; variante hot :6809-6816), pretesa a :6953
   (`freeb >= aligned + reserve`).
3. **Scratch di prefill** `g_cuda_tmp` (rilasciato a decode-start, vedi (c)).
4. **KV** (+ KV staged migrabile su host, ds4_cuda.cu:28224).

### La "sizing race" documentata nel codice (requisito 5)

E' citata **due volte**, in prima persona dai due consumatori:

* **ds4_cuda.cu:34118-34119** — `/* Diagnostic only: records this consumer's position in the VRAM sizing race (free it observed, what it asked for, what it got). */`
* **ds4_cuda.cu:35068-35069** — `/* Diagnostic only: the other consumer sized from cudaMemGetInfo. Emitted in the order it executes so the sizing race against [q1-vram-lru] is readable. */`

Cioe': il codice **sa** di avere piu' consumatori che si dimensionano
indipendentemente sullo stesso `cudaMemGetInfo`, in conteggi separati e non in un
budget di byte condiviso. E' esattamente il difetto del requisito 5.

---

## (c) Dove viene rilasciato lo scratch di prefill (momento giusto per il sizing elastico)

| Cosa | Dove |
|---|---|
| Hook di decode-start | `ds4_gpu_vram_ledger_decode_start()` — **ds4_cuda.cu:28221-28300** |
| Migrazione KV staged su host | ds4_cuda.cu:28224 |
| `DS4_CUDA_RELEASE_PREFILL_SCRATCH` | ds4_cuda.cu:28226 |
| `cudaFree(g_cuda_tmp)` effettiva | ds4_cuda.cu:28246-28251 |
| Log `[vram-ledger] phase=decode-start` | `cuda_vram_ledger_log()` — ds4_cuda.cu:28198-28219, chiamata :28259 |
| Hook di fine richiesta | `ds4_gpu_vram_ledger_request_end()` — ds4_cuda.cu:28302-28316 |

**Buona notizia: la plumbing per il sizing a decode-start esiste gia'.** E' la
"F10 two-phase sizing":

* gate `cuda_moe_expert_cache_grow_requested()` = env **`DS4_CUDA_EXPERT_CACHE_GROW`** — ds4_cuda.cu:28193-28196;
* geometria catturata in prefill e allocazione rimandata — ds4_cuda.cu:34895-34911;
* early-return che rimanda l'allocazione — ds4_cuda.cu:34981-34985 (commento :34975-34980);
* **allocazione definitiva a decode-start** — ds4_cuda.cu:28264-28292 (log `[expert-cache-grow]`).

Quindi per il requisito 2 bisogna cambiare **la formula**, non costruire il meccanismo.

---

## (d) Strutture che sanno se un range e' backbone o expert

La classificazione **esiste ed e' affidabile**, non serve progettarla:

| Cosa | Dove |
|---|---|
| Campo di classe | `cuda_model_range::pinned` — **ds4_cuda.cu:1486-1488** (commento: "1 => non-expert (attn/norm/router) weight ... experts are unpinned") |
| Calcolo della classe | **ds4_cuda.cu:6983** — `const int is_hot = (what == NULL) \|\| (strncmp(what, "moe_", 4) != 0);` |
| Passaggio nel record | ds4_cuda.cu:7056 (ultimo campo del `push_back`) |
| Clock LRU | `g_model_tick` — ds4_cuda.cu:744; stamp `last_used_tick` :1485 |

`what` e' il tag del tensore; tutti gli slice esperti sono `moe_*`. Quindi
backbone = `pinned==1`, expert = `pinned==0`.

**KV: non e' in `g_model_ranges` per costruzione** -> un contatore `evict_kv` e'
strutturalmente sempre 0 su questo percorso. Lo emetto comunque (a 0) per avere la
stessa riga nei due bracci dell'A/B, e lo documento come N/A anziche' far credere
che sia una classe di vittima esistente.

---

## Verdetto di fattibilita' (richiesto esplicitamente dal brief)

### NON implementabile in questa passata senza rifacimenti profondi

**Sfrattare esperti "a domanda" restringendo lo slab residente mentre il decode gira**
(la lettura piu' forte dei requisiti 1 e 3). Motivi concreti:

* lo slab e' **una singola `cudaMalloc` contigua** con i piani `gate`/`up`/`down` a
  offset fissi calcolati sulla capacita' (ds4_cuda.cu:34129-34133 per l'analogo Q1,
  e il blocco di allocazione da :35079);
* esiste una **mappa slot lato device** (`device_slot_by_layer_expert`, :26576) piu'
  la copia host (:26575) da ripubblicare atomicamente;
* c'e' un **route worker thread vivo** con mailbox e sequenze
  (:26595-26621) e H2D in volo: restringere a caldo richiede quiescenza del worker;
* invariante `slots.size() == capacity` (:34147).

Restringere a caldo = realloc + ripacchettamento + ripubblicazione mappa + quiesce
del worker. Alto rischio di corrompere slot residenti. **Lo dichiaro non fatto.**

### Versione minima che cattura il grosso del beneficio (implementata)

L'equivalente **preventivo** dello stesso obiettivo: invece di curare la
sovra-sottoscrizione sfrattando, **impedirla al sizing**.

1. **Riserva backbone nel sizing a decode-start.** La formula sottrae anche un
   headroom di crescita del backbone + isteresi. A ctx 150k `free_b` a decode-start
   e' piccolo, quindi la capacita' **si autolimita** (invece di onorare ciecamente
   320) -> il backbone non viene piu' spinto fuori. A ctx piccolo `free_b` e' grande
   e la capacita' cresce: "sfruttare sempre la VRAM al massimo".
   Nota: a decode-start il backbone gia' residente e' **gia' escluso** da `free_b`
   (e' allocato), quindi la riserva copre solo la *crescita futura*, non la taglia
   corrente. Questo evita di riservare due volte.
2. **Correzione dell'inversione dello scudo di recency** con un passo intermedio
   sicuro (mai piu' recente di `tick - shield`), cosi' gli esperti sono davvero
   sacrificati prima di *qualsiasi* backbone.
3. **Strumentazione completa** per l'A/B, emessa in entrambi i bracci.

### Rischi noti / limiti

* Nessuno sfratto dello slab a caldo: se il backbone cresce **dopo** il sizing oltre
  la riserva, si torna a sfrattare backbone. Il caso e' **contato e loggato** come
  anomalo (`evict_backbone`) e l'oscillazione viene dichiarata, ma non curata.
* `evict_kv` resta strutturalmente 0 (KV fuori dal pool).
* La capacita' elastica oltre 512 slot e' fuori dai bound testati: clampata, con env
  dedicata per alzarla consapevolmente.
* **La capacita' e' decisa una volta per processo**, al primo decode-start: a
  `request-end` la cache non viene rilasciata (ds4_cuda.cu:28646-28648 azzera solo
  `g_moe_expert_cache_decode_started`) e la guardia di riuso (:35300 ca.) confronta
  `requested`, non `capacity`. Quindi richieste successive con ctx molto diverso **non**
  ri-adattano la capacita'. Per un A/B pulito: **un processo per braccio**.
* Il passo esperti rilassato non aiuta quando nel pool **non ci sono** range esperti
  (caso 150k con cache grande): li' agisce solo il sizing. Sono due leve distinte.

---

## FASE B — Riferimento di implementazione (per l'A/B)

### Flag (tutti OFF/neutri per default)

| Env | Default | Effetto |
|---|---|---|
| `DS4_CUDA_VRAM_INVERTED_PRIORITY` | `0` | Master. 1 = passo esperti rilassato nel picker + riserva backbone nel sizing. Letto una volta e **memoizzato**. |
| `DS4_CUDA_VRAM_ELASTIC_EXPERT_SLOTS` | `0` | Secondo flag. 1 = la capacita' puo' superare `DS4_CUDA_STREAMING_EXPERT_CACHE_N` fino al tetto elastico. Richiede `DS4_CUDA_EXPERT_CACHE_GROW=1`, altrimenti **auto-disabilitato con messaggio**. |
| `DS4_CUDA_VRAM_BACKBONE_RESERVE_MB` | `1536` | Headroom di crescita del backbone. **Manopola principale da sweepare.** |
| `DS4_CUDA_VRAM_HYSTERESIS_MB` | `256` | Banda morta anti-thrash, sottratta in aggiunta. |
| `DS4_CUDA_VRAM_EXPERT_SHIELD_TICKS` | `2` | Scudo di recency del passo esperti rilassato (>=1, memoizzato). |
| `DS4_CUDA_VRAM_MIN_EXPERT_SLOTS` | `32` | Pavimento di slot se la riserva azzererebbe la cache. `0` = lascia disabilitare. |
| `DS4_CUDA_VRAM_ELASTIC_MAX_SLOTS` | `512` | Tetto elastico (= clamp hard esistente; oltre = fuori bound testati). |
| `DS4_CUDA_VRAM_THRASH_LIMIT` | `64` | Sfratti backbone in finestra che dichiarano l'oscillazione. |
| `DS4_CUDA_VRAM_THRASH_WINDOW` | `4096` | Ampiezza finestra in sfratti totali. |

### Contatori (riga `[vram-prio]`, emessa in ENTRAMBI i bracci)

`evict_backbone`, `evict_expert`, `evict_kv` (sempre 0, N/A),
`backbone_evicted_bytes`, `backbone_reload_bytes`, `backbone_reloads`,
`expert_relaxed_saves`, `expert_slots_current`, `expert_slots_resident`,
`expert_slots_requested`, `vram_free_at_decode_start`, `vram_free_now`,
`backbone_reserve_mib`, `hysteresis_mib`, `stabilized`, `stabilized_slots`,
`evicts_total`.

### Righe di log introdotte

* `[vram-prio] phase=decode-start ...` e `phase=request-end ...` — sempre, entrambi i bracci.
  **`phase=request-end` e' la riga da diffare fra i due bracci.**
* `[vram-prio] ANOMALY evict_backbone=... reason=no-expert-victim` — primi 8 sfratti di
  backbone, poi 1 ogni 256.
* `[vram-prio] sizing=<decode-start|prefill> requested=... target=... capacity=...` — solo con flag ON.
* `[vram-prio] stabilized=1 reason=backbone-evict-thrash ... action=freeze-elastic-capacity`.
* `[vram-prio] expert_cache=floor reason=backbone-reserve-exceeds-free`.
* `[vram-prio] elastic=auto-disabled reason=requires-DS4_CUDA_EXPERT_CACHE_GROW=1`.

### Metrica attesa per il verdetto

Il braccio ON dovrebbe mostrare, a ctx 150k, `evict_backbone` e
`backbone_reload_bytes` crollare (idealmente a ~0) con `expert_slots_current` **minore**
di 320, e il decode tornare nell'ordine dei 238 ms/token invece di 2066.
