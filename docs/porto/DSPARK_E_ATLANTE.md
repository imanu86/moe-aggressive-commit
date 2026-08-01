# DSpark: cosa serve per accenderlo — e le leve nuove del tronco

Letto sul tronco (`ds4-port`) l'1/8. Ogni affermazione ha file:riga.

---

## 1. DSpark — la catena di attivazione

### C'E' un interruttore esplicito (mi ero sbagliato)

Avevo scritto "nessun interruttore, il cancello e' la presenza dei tensori GGUF".
E' **falso**. Ci sono tre flag CLI (`ds4_server.c:13002-13011`):

```
--dspark                      c.engine.dspark = true
--dspark-confidence <0..1>    accende dspark + soglia di confidenza
--dspark-strict               accende dspark + modo stretto
```

Le `DS4_DSPARK_*` d'ambiente sono davvero tutte di tipo DISABILITA
(`NO_MARKOV`, `NO_GPU_MARKOV`, `DISABLE_*`): regolano un DSpark **gia' acceso dal flag**.

### I due vincoli, in ordine

```
ds4.c:55951   --dspark senza --mtp FILE       ->  "requires --mtp FILE", esce
ds4.c:56365   --mtp insieme a --ssd-streaming ->  "not compatible with --mtp yet", esce
```

Il secondo e' il muro. E il punto e' **da che parte sta il muro**:

```
ds4.c:55921   e->ssd_streaming = opt->ssd_streaming;
```

Assegnazione unica e diretta dal flag CLI. Nessun'altra riga scrive `e->ssd_streaming`.
Quindi il guardiano **non** sta dicendo "DSpark e' incompatibile con lo streaming da disco":
sta dicendo "DSpark e' incompatibile con **il meccanismo di streaming di upstream**".

### Percio' il blocco NON e' il guardiano

Togliere quell'`if` e' una riga. Il blocco e' che oggi, senza `--ssd-streaming`, il tronco
non ha **nessuna** residenza funzionante: prova a mappare il modello intero e muore.
Misurato l'1/8, macchina pulita al lancio:

```
42,70 -> 47,76 -> 52,57 -> 52,84 GiB, poi
"CUDA model arena alloc failed for tensor-span:99 (1792 MiB): out of memory"
a offset 59808639808
```

**Il fork e' la prova che si puo' fare.** In `ds4-p4a` il flag `--ssd-streaming`
non esiste proprio: lo streaming *e'* l'arena. Stesso modello, stessa arena da 30 GiB,
32 GB di commit, 4423/4551 residenti, zero sfratti del backbone.

Quindi la sequenza e' obbligata, e coincide con un lavoro gia' in mandato:

```
1.  UNA RESIDENZA sul tronco: l'arena serve il modello senza --ssd-streaming
2.  a quel punto e->ssd_streaming e' false e --mtp diventa legale DA SOLO,
    senza toccare il guardiano
3.  --dspark --mtp <sidecar>
```

Il passo 1 non e' un prerequisito burocratico di DSpark: **e' lo stesso identico lavoro**
che serve per far smettere al tronco di bruciare 15 GB piu' del fork.

### Un costo che invece NON paghiamo

La riserva VRAM da 4,5 GiB (`ds4.c:55542`, `DS4_DSPARK_CACHE_RESERVE_GB`) sta dentro
`engine_install_dspark_support_cache`, che esce subito se `!e->multi_tier`
(`ds4.c:55497`). E `multi_tier` vale 1 solo se il piazzamento mette gli strati su tier
diversi (`ds4.c:55184-55193`): su una 3060 sola e' **0**.

Su GPU singola quella riserva non si applica. Avevo detto il contrario.
Le allocazioni per sessione di DSpark (`ds4.c:57584-57594`) sono host e trascurabili:
`markov_bias` = n_vocab float, `conf_features` = (n_embd + markov_rank) float.

Resta invece da capire **dove vanno i 7,83 GB del sidecar**, che e' la domanda vera.

### Il sidecar che abbiamo

`D:\ds4-models\DSpark-support-Q2K-w2Q4K.gguf`, 7,83 GB, metadati verificati:

```
dspark.block_size       5        propone 5 token per giro
dspark.markov_rank    256
dspark.target_layer_ids [40,41,42]   entrano nei nostri 43 strati
dspark.n_layers         3
dspark.stage_count      3
```

---

## 2. La scoperta che vale il viaggio: la route Q4_K

```
occorrenze Q4_K nel dispatcher MoE     TRONCO 7     FORK 0
```

Nel tronco esiste il **dispatch MoE Q4_K** (`ds4_cuda.cu:24254`) con kernel veri:
tile8 gate/up e down (`:24266`), kernel di prefill down che rispecchia
`moe_down_qwarp32` (`:22818`), prodotto scalare su superblocchi Q4_K x Q8_K (`:22911`),
blocco Q4_K con nove load da 16B (`:19612`), gate/up di decode indicizzato per token (`:24814`).

Questo chiude una voce dell'atlante che era aperta da giorni. La memoria diceva:
*il dispatcher CUDA non ha route Q4_K, la testa MTP fallisce ogni token in silenzio e il
lavoro passa alla CPU, che costa il 48% del tempo reale FUORI dal grafo.* Era vero **sul
fork**. Sul tronco la route c'e'.

E il sidecar che abbiamo scaricato si chiama `...w2Q4K.gguf`. Sul fork sarebbe caduto
in silenzio sulla CPU — cioe' avremmo rimisurato il -25% del drafter. Sul tronco no.

Il PIANO lo aveva gia' scritto in "Cosa NON portare": *«riempire il buco Q4_K — upstream
ha 7 occorrenze e kernel dedicati»*. Era registrato, non l'avevo collegato a DSpark.

---

## 3. L'atlante — le leve nuove

219 nomi passano per `getenv` nel tronco e non nel fork. Tolte le famiglie che non ci
riguardano — `DS4_GLM_*` (altro modello), `DS4_METAL_*` (Mac), `DS4_TP_*` e
`DS4_*_DISTRIBUTED` (multi-GPU) — resta questo.

### Da provare, in ordine di quanto il nostro modello di costo le sostiene

| Leva | Riga | Perche' proprio questa |
|---|---|---|
| `DS4_CUDA_MOE_DECODE_GRAPH` | `ds4_cuda.cu:1769` | grafo CUDA sul decode MoE. Siamo **orchestration-bound**: 121 ms di orchestrazione, GPU al 7%, niente saturo. Un grafo collassa i lanci. E' la forma esatta di leva che il modello di costo prevede vincente — e non sposta un solo byte, quindi la regola del trasporto non la tocca. Presenza-sola: qualunque valore la accende |
| `DS4_CUDA_PREFILL_PIPELINE` + `_MB` | `ds4.c:17014`, `:17029` | pipeline di prefill a microbatch, default 512. **Non e' vincolata al multi-GPU**: `if (env && env[0]) return strcmp(env,"0") != 0` — l'ambiente vince sul default, che per noi sarebbe spento. E il prefill_chunk e' gia' la leva piu' grossa che abbiamo trovato |
| `DS4_CUDA_PREFILL_PIPELINE_SEQUENTIAL` / `_SYNC_BOUNDARY` | `ds4.c:33109`, `:33156` | le due varianti di sincronizzazione della pipeline sopra |
| `DS4_CUDA_END_STREAM_SYNC`, `DS4_CUDA_SYNC_XDEV`, `DS4_CUDA_NO_SETDEVICE_CACHE` | — | tre sincronizzazioni. Rimuovere attese e' esattamente cio' che la regola del trasporto **non** copre |
| `DS4_CUDA_STREAMING_EXPERT_CACHE_PROFILE` | — | strumentazione sul percorso che oggi non vediamo. Non e' una leva di velocita', e' l'occhio che ci manca |
| `DS4_CUDA_MOE_MIDQ_SIDECAR` / `_DIRECT_MIDQ` | — | percorso sidecar nel MoE. Da capire se e' la cucitura che serve a DSpark |
| famiglia `DS4_CUDA_SPLITKV_SPEC_*` | — | verifica speculativa su split-KV, gia' dentro upstream |
| famiglia Q4 MoE (`MOE_Q4_GATE_W32R16`, `MOE_NO_Q4_MMA`, `MOE_Q4_DOWN_SLOT3`, ...) | — | le manopole dei kernel Q4_K del punto 2 |

### Vicolo cieco, verificato

`DS4_EXPERT_HOTLIST` e `DS4_EXPERT_PROFILE` sembrano nostri per nome. Non lo sono:
fuori da Metal il tronco stampa *«expert profile/hotlist is Metal-only for now; ignoring
for %s backend»* ed esce (`ds4.c:56042-56047`).

---

## 4. Quello che il porto NON ha portato

Verso opposto: 324 simboli `DS4_*` esistono nel fork e non nel tronco. Una parte sono
enum interni (`DS4_HOSTPIN_KIND_*`, `DS4_GPU_ARENA_*`, `DS4_NEXTN_DEAD_*`, `DS4_BAKE_*`),
non leve. Tolti quelli, restano tre gruppi con statuti diversi.

**(a) Fuori ambito per progetto** — il PIANO le mette esplicitamente dopo il core
(`docs/porto/PIANO.md`, stima: *+ Q1/IQ1/nested residual 3-5 gg*, *+ KV staged e G132 4-7 gg*):
`DS4_Q1_0_*` (32), `DS4_IQ1_*` (14), `DS4_NESTED_RESIDUAL_*` (14), `DS4_G132_CPU_LANE*`.
Assenti **come previsto**.

**(b) Il meccanismo c'e', mancano le manopole.** Questo e' il gruppo che conta.
Il tronco ha la scelta della vittima — `mass_lfru_policy::choose_victim`
(`src/cuda/vram_expert_cache.cpp:166`), esposta via
`cuda_stream_expert_cache_policy_choose_victim` (`ds4_cuda.cu:26570`). E' il nostro
blocco 3, portato. Ma di tutta la superficie di regolazione del fork sopravvive **solo**
`DS4_CUDA_VRAM_EXPERT_CACHE` e `DS4_CUDA_VRAM_PRIO_LOG_EVERY_TOKENS`. Mancano:

```
DS4_CUDA_VRAM_PREFER_EXPERT_VICTIM        <- la cura diretta di "reason=no-expert-victim"
DS4_CUDA_VRAM_BACKBONE_RESERVE_MB         <- il backbone e' usato dal 99,84% dei token
DS4_CUDA_VRAM_MIN_EXPERT_SLOTS
DS4_CUDA_VRAM_ELASTIC_EXPERT_SLOTS / _MAX_SLOTS
DS4_CUDA_VRAM_EXPERT_SHIELD_TICKS
DS4_CUDA_VRAM_THRASH_LIMIT / _WINDOW
DS4_CUDA_VRAM_HYSTERESIS_MB
DS4_CUDA_VRAM_INVERTED_PRIORITY
tutta la famiglia DS4_EXPERT_TIER_* (17): admit knocks SSD/VRAM/WARM,
   mass bypass, budget adattivo, isteresi, budget di rimpiazzo
DS4_CUDA_PRESERVE_ACROSS_REQUESTS, DS4_CUDA_DYNAMIC_ARENA_CARRY_ACROSS_REQUESTS
DS4_CUDA_REAP_MASS_* (5), DS4_CUDA_ARENA_WRAP_* (8), DS4_SPEX_* , DS4_CPU_SHARED_EXPERT_*
```

Il PIANO li metteva nel core (*cache VRAM + tiering/promozione, 5-7 gg*), non fra le
esclusioni. **Il porto e' 14/14 sui blocchi ma non sulla superficie di politica.**
Questa e' la differenza fra "gira" e "gira come il fork".

**(c) Nate dopo.** `DS4_CUDA_TRANSIENT_VERBOSE` l'ho creata oggi sul fork: assente
dal tronco per costruzione, non e' un buco.

---

## Conseguenze operative

1. **DSpark non e' bloccato dal suo guardiano.** E' bloccato dalla residenza doppia,
   che e' gia' il mandato aperto. Una cura, due risultati.
2. **La route Q4_K c'e'**: il sidecar `w2Q4K` puo' girare su GPU, cosa impossibile sul fork.
3. **`MOE_DECODE_GRAPH` va provata subito**, prima di DSpark: e' a variabile singola,
   costa un run, e il modello di costo la sostiene piu' di qualunque altra cosa
   nell'elenco.
4. **Le manopole della vittima vanno riportate** prima di dichiarare la parita' col fork.
