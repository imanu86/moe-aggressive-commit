# LEDGER PORTO — 15-16 AGOSTO 2026

## Bracci e verdetti nuovi

| Braccio | Forma | Risultato | Correttezza | Verdetto |
|---|---|---:|---|---|
| Residente denseFA + staging + HC scheduler, long | 101.597+64, ctx150k, B/UB2048, 3 run | prefill 110,7005 / 111,0928 / 126,8021; media **116,1985**. Decode media **7,9492** | output identico/coerente, p1=.61702, zero errori | **Nuova base lunga corretta** |
| Profilo CPU + packetizer phase-safe + bsparse | 20.749+64, ctx40k, UB12288 | crash al primo draft | `markov_w1`, poi diagnosticato `i01=-1` | **Bocciato, niente repliche** |
| Diagnostica packetizer 1 | 6.720 token, ctx12k, UB8192 | crash | `markov_w1.weight`, secondo argmax resta -1 | packetizer-off nel draft non ripara hidden/KV prefill |
| Profilo CPU + packetizer 0 + bsparse | 6.716 token effettivi, ctx12k, UB8192 | **259,39 t/s** prefill, poi crash; PC bloccato | stesso `markov_w1`, `i01=-1` | packetizer assolto; non rilanciare identico |
| EXACT_DMA kernel-spin | warm-up target, nessuna richiesta | fermo al primo comando `seq=1 strato=0 miss=8`, poi `unspecified launch failure` | nessun output; nessun B t/s consumato | **Falsificato** |
| EXACT_DMA memops64/runtime | warm-up target, nessuna richiesta | fermo al primo comando; query/sync runtime non fanno progredire la coda reale | microtest wait/write isolato verde, grafo reale bloccato | **Falsificato** |
| EXACT_DMA memops64/Driver API, target graph off | warm-up target, nessuna richiesta | fermo al primo comando anche con `cuMemcpyHtoDAsync`/`cuStreamSynchronize` | microtest concorrente 8 MiB verde, grafo reale bloccato | **Falsificato e codice rimosso** |
| Decode whole-FFN combinato | 1.200 token | **14,57 t/s**, p1=.86752 | output coerente, length | **-9,35%, respinto; gia' in Ledger 14** |
| Decode shared-overlap, cache base-parity | 1.200 token | **14,55 t/s**, p1=.86752 | output coerente, length | **-9,48%, respinto; codice rimosso** |
| RCI mapped, fixture fine | 64 token | **11,65 t/s**, p1=.92308 | output coerente, length | caricamenti fini PCIe inefficaci |
| RCI mapped, fixture burst `uint4` | 64 token | **14,02 t/s**, p1=.83333 | output coerente, length | recupera la coalescenza; ammesso al solo B |
| RCI mapped burst, MASSA2 473+12 | 1.200 token | **14,97 t/s**, 66,81 ms/token, p1=.84129 | NeuraForge HTML coerente, length, zero ID invalidi | **-6,86%, respinto; nessuna replica, codice rimosso** |
| Diagnostica lane CPU K=2 | 64 token | **13,39 t/s**, p1=.77273; 6.708 assegnazioni CPU: 5.809 miss, 899 residenti | output coerente | solo **13,4%** del ramo CPU era gia' residente; lane adattiva non ha budget macro |
| CPU FFN super-op v1 | 64 token | **12,60 t/s**, p1=.77273; worker CPU 2,073 ms/layer | output identico, stesso SHA della fixture | peggiore della fixture diagnostica; audit codice, niente B 1.200 |
| CPU FFN super-op v1, accessi contigui | 64 token | **11,40 t/s**, p1=.77273; worker CPU 2,454 ms/layer | output identico, stesso SHA | chiaramente peggiore; **respinto e codice rimosso** |
| GPU lane B transiente, multi-stream smoke 1 | nessuna completion | errore CUDA `capturing stream has unjoined work` | nessun output | fork B aperto, consumer rimasto CPU; non conta come B |
| GPU lane B transiente, multi-stream smoke 2 | nessuna completion | deadlock al primo decode dopo `cached n_tokens = 1` | nessun output | pin CUDA esplicito non risolve il ciclo WDDM/graph; **famiglia multi-stream respinta e rimossa** |
| GPU lane B transiente, single-stream | 64 token | **11,37 t/s**, p1=.88372; stage 1,487 ms/ciclo, tail 0,993 ms/ciclo | output coerente, length, invalidi=0 | **-15,1%, respinto; codice rimosso** |
| Decode VRES graphlet, GPU-only K=0 fixture | 64 token | **12,10 t/s**, p1=.87805 | output coerente, length | cancello correttezza superato; ammesso al solo B GPU-only |
| Decode VRES graphlet, GPU-only K=0 | 1.200 token | **12,83 t/s**, p1=.78025 | output coerente, length | circa **+8%** contro il riferimento GPU-only storico; guadagno reale ma non batte la base K=2 |
| Decode VRES graphlet, K=2 fixture r3 | 64 token | **12,68 t/s**, p1=.80952 | output coerente, stesso SHA della reference K=2 | corretto dopo gestione del sentinel route `-1` |
| Decode VRES graphlet, MASSA2 K=2 | 1.200 token | **14,03 t/s**, p1=.87391; miss 21,8%; 312,87 GiB H2D | NeuraForge HTML coerente, length, zero errori/divergenze | **-12,7%, respinto; nessuna replica** |
| Decode TILE GPU-driven, layer 3 | 64 token | **10,15 t/s**, p1=.77273; 87 miss unici su 99 route-miss | `length`, stesso SHA K=2; install gate/up/down=87/87/87 | corretto e deduplicato, ma costo gia' fuori budget |
| Decode TILE GPU-driven, tutti i layer | 64 token | **10,45 t/s**, p1=.80952; 3.815 miss unici, circa 25,15 GiB mapped | `length`, stesso SHA K=2; install gate/up/down=3.815/3.815/3.815, zero errori/divergenze | **-35,0% dalla base; respinto, niente B 1.200** |

## Evidenza diagnostica

```text
GET_ROWS_Q invalid index: src0='markov_w1.weight'
src1='CPU#node_509#0' dst='node_510'
i=0 i01=-1 ne01=129280 src1_ne=[1,1,1,1]
```

`dflash.cpp` costruisce il secondo indice Markov con `argmax(col)`; il kernel
CUDA lascia -1 se la colonna è tutta NaN/non-finita. La corruzione è già negli
hidden/KV DFlash prodotti durante il prefill full, non un indice host casuale.

## Decisione

- 275,506 t/s resta misura target-only/non certificata, non SOTA end-to-end.
- SOTA lunga corretta = prefill 116,1985 t/s.
- Packetizer non è causa necessaria: con packetizer 0 il guasto resta.
- Prossimo discriminatore prefill: block-sparse ON con densi residenti,
  packetizer 0, UB2048/4096, completion >=32; niente wildcard CPU.
- Il solo overlap DMA ha tetto 19,453 t/s e non basta.
- Aggiornamento: exact-demand H2D con rendez-vous host interno al grafo reale e'
  bocciato; non ripeterlo.
- Anche whole-FFN/shared-overlap (14,55--14,57) e RCI MMVQ diretto mapped
  (14,97) sono bocciati e rimossi. La base copia ogni miss dal PCIe una sola
  volta e poi calcola dalla slab VRAM: non esiste una seconda lettura PCIe da
  fondere.
- Lo split CPU/GPU per residenza e' gia' nella base a K=2. Il prossimo braccio
  deve essere ortogonale alle famiglie gia' falsificate e dimostrare a priori
  un budget vicino ai 12,214 ms/token necessari, non un altro incremento locale.
- La misura esatta dei tre MMID CPU isolati e' 414,022581 us gate + 414,022581 us
  up + 141,364466 us down = **0,969410 ms/layer**. Il super-op manuale non ha
  raggiunto quel tetto: ha perso blocking/scheduling del motore MMID esistente.
  Non riscrivere di nuovo i dot CPU; preservare i kernel esistenti.
- Candidato macro successivo: sostituire le due route CPU con una banca GPU
  transiente **exact-demand device-only**, senza host rendez-vous e senza
  inquinare A. A ogni row-layer la diagnostica vede due route CPU, in media
  1,732 miss dopo il filtro residenti: circa 11,69 MiB, ~0,469 ms fisici a
  24,35 GiB/s. Il cancello richiede ridurre il critical path di almeno
  **0,700 ms/layer**; staging e calcolo transiente devono sovrapporsi al ramo
  GPU delle quattro route residenti/miss.
- Aggiornamento: la variante multi-stream e' falsificata da cattura non
  ricongiunta e poi deadlock reale; non ripeterla, neppure con graph-off. Resta
  distinto un solo sottocancello **single-stream**: copia esatta di 2 esperti
  (~0,541 ms) seguita dagli MMVQ locali (~0,158 ms stimati), senza eventi o
  stream esterni. Se il critical path misurato non batte 1,056 ms/layer, si
  chiude anche la banca B exact-demand.
- Aggiornamento conclusivo: anche il single-stream e' chiuso a 11,37 t/s. Il
  successivo VRES graphlet ha dimostrato un +8% pulito a K=0, ma con K=2 scende
  a 14,03: il confine host sincrono impedisce al scheduler di comporre la lane
  CPU col ramo CUDA. Non cercare varianti locali dello stesso graphlet/H2D.
- Aggiornamento conclusivo TILE: il WIP e' stato completato, isolato dal vecchio
  VRES, compilato Release e verificato prima su layer 3 e poi su tutti i layer.
  La correzione essenziale deduplica i miss tra token speculativi usando la
  lista device dei soli miss unici: nessuna rilettura/installazione concorrente
  dello stesso esperto; route `-1`, MASSA2, K=2, pesi e ordine restano invariati.
  Entrambe le fixture sono bit-identiche alla reference K=2, ma il full TILE fa
  solo **10,45 t/s**. I 3.815 tile da 6,75 MiB valgono circa **25,15 GiB** letti
  via SM/UVA in 6,127 s: tetto end-to-end circa **4,10 GiB/s**. Per 20 t/s gli
  stessi byte richiederebbero almeno 7,86 GiB/s prima ancora del compute. Il
  meccanismo GPU-driven mapped read/compute/install e' quindi falsificato nel
  regime Porto; niente B 1.200 e niente varianti locali di griglia/coalescenza.

## Planner globale target+DSpark e trasporto persistente (15 agosto, sera)

Questo braccio e' distinto da FIDDLER/K dinamico/prefetch locale: un piano
globale dell'intero ciclo speculativo assegna in anticipo `(layer, expert,
slot, release, deadline)`. Le vittime `-1` sono libere a inizio ciclo; le altre
vengono sovrascritte solo dopo il `down` dell'ultimo layer che le legge. Il
trasporto usa uno stream persistente dedicato e gli eventi vengono accodati dal
backend **fuori** dalla cattura dei circa 45 sottografi CUDA target. DSpark e i
CUDA Graph target restano attivi; nessun callback o rendez-vous host per layer.

| Braccio | Risultato | Correttezza / contatori | Verdetto |
|---|---:|---|---|
| Reference normalizzata CESTRC2, B160 | **9,96 t/s**, p1=.81443 | SHA `EFC752C5...` | clock contingente basso; riferimento del microcancello |
| Piano sincrono, B160 | **8,39 t/s** | stesso SHA/p1; 80/80, 6.806 copie verificate byte per byte | corretto ma seriale |
| Async con target graph spenti, B160 | **9,03 t/s** | stesso SHA/p1; 80/80, zero miss/divergenze | trasporto corretto, costo graph-off dominante |
| Async persistente fuori cattura, target graph attivi, B160 | **10,11 t/s** | stesso SHA/p1; 80/80, zero miss/divergenze | **+1,5%** sul riferimento breve |
| Reference normalizzata CESTRC2, B1200 | **11,38 t/s**, p1=.88010 | SHA `1A210205...`; 690 accettati | riferimento lungo a clock contingente |
| Async persistente, tail decode 509 cicli, B1200 | **11,49 t/s**, p1=.88010 | stesso SHA; 509/509, 43.244 copie, 222.396/222.396 hit allineati, zero miss/divergenze | **+0,97%, valido ma non macro** |

La traccia lunga contiene 514 cicli completi, di cui 5 preliminari
warm-up/prompt. Il decode corretto e' la coda da `1200 - 690 - 1 = 509` cicli;
usare tutti i 514 lascia il replay disarmato (`0/55986`) e non misura il piano.
Il piano tail509 ha working set medio 272,13 slot (max 401) su 473, 84,19 copie
per ciclo e riduce offline i miss unici da 52.421 a 37.157 (-29,12%), ma il
guadagno end-to-end resta circa un punto percentuale.

**Decisione:** infrastruttura e semantica del planner/trasportatore sono
promosse (parita' esatta e zero deadline miss), ma il planner oracle da solo
non e' il macro-guadagno necessario per 20 t/s. Non iterare altre politiche
locali di release/K/lane. Il fronte principale passa al macro-kernel decode v2
che preserva la MMQ/MMVQ Porto e fonde il contorno (route/partizione,
quantizzazione, maschere, dispatch e code/tail); il planner resta sotto come
fornitore di residenza. I valori 9--11 t/s non sostituiscono la SOTA 16,0733:
sono stati raccolti con clock GPU contingente inferiore e servono come A/B
relativo sullo stesso binario/banco.

## Macro-kernel decode v2: planner -> slot diretto

Il primo sottocancello ha rimosso il lookup reattivo `kern_decidi` dal ramo
K0: il planner precarica il ciclo zero al confine caldo prompt/decode, assegna
gli slot esatti e la partizione passa gli slot direttamente alla MMVQ Porto.
Il cambio di fase entra nell'identita' dei CUDA Graph, quindi il grafo del
prompt non puo' essere riusato per errore nel decode. Questo braccio non e'
`FORK_RIUSA_SLOT`: ownership e generazioni provengono dal calendario globale.

| Braccio | Risultato | Correttezza / contatori | Verdetto |
|---|---:|---|---|
| Calendario Q9 lungo, K0 | **11,50 t/s**, p1=.84036 | stesso SHA del K0 lungo, 658 accettati / 783 generati, zero divergenze | valido; circa +31% sul K0, ma solo circa +1% sulla base K2 contingente |
| Calendario Q8 burst | picco apparente non valido | output corrotto alla prima pressione del trasporto | falsificato; nessuna promozione |
| Slot diretto, Q8, B160 | **10,22 t/s**, p1=.80583 | SHA `EE1E260F...`, 7.740/7.740 route, 78/78 cicli, 19.787 copie, zero guasti/divergenze | corretto, ma sotto il calendario standard breve da 10,54 t/s |
| Slot diretto + maschera compact, Q8, B160 | **10,22 t/s**, p1=.80583 | stesso SHA; 7.740/7.740 route, 78/78 cicli, zero guasti/divergenze | nessun recupero: le colonne compact nulle non erano il collo |

Due bring-up precedenti non sono misure: attivare gli slot diretti durante il
prompt lasciava il calendario disarmato e produceva 45.408 lookup invalidi;
usare solo 76 cicli ometteva il primo ciclo decode a un token. Il piano corretto
contiene tutti i 77 cicli piu' drain e viene attivato soltanto dopo il restore
hot target+draft+slab.

**Decisione:** l'infrastruttura planner -> ownership -> slot -> MMVQ e' corretta,
ma il solo bypass del lookup non e' un macro-guadagno. La maschera compact non
va inseguita con altri microtuning. Per il prossimo v2 bisogna misurare e fondere
un contorno piu' ampio della MMVQ esistente (route/sort, quantizzazione,
dispatch e tail), mantenendo il planner come residenza e senza riscrivere i dot
Porto. Nessun risultato di questa sezione sostituisce la SOTA 16,0733 o dimostra
20 t/s.

## Macro-v2: gate+up cache-aware e riuso expert-major tra token

Il profilo invasivo K0/calendario, con graph spenti, misura per layer target
`gate -> up -> GLU -> down` = **1,9256 ms**. Le tre MMVQ mascherate valgono
**1,4816 ms/layer**, mentre clamp/GLU/dispatch/tail valgono solo
**0,4440 ms/layer**. Il profilo non e' una misura t/s, ma fissa il budget:
per arrivare da 16,0733 a 20 t/s servono circa **0,284 ms/layer**.

E' stata implementata dietro `LLAMA_DSV4_DECODE_GATE_UP_FUSO=1` una fusione
cache-aware che riconosce i due MMID, conserva slot e maschere del planner,
chiama la MMVQ Porto esistente in un solo passaggio e scrive direttamente il
GLU. Il braccio B160 e' bit-identico alla reference slot-diretto:

| Braccio | Risultato | Correttezza / contatori | Verdetto |
|---|---:|---|---|
| Slot diretto compact, B160 | **10,22 t/s**, 97,83 ms/token | SHA `EE1E260F...`, p1=.80583 | reference contingente |
| Slot diretto + gate/up fuso, B160 | **10,37 t/s**, 96,40 ms/token | stesso SHA/p1; planner 7.740/7.740, trasporto 78/78, zero divergenze | **+1,47%, corretto ma respinto** |

Il recupero e' solo **1,43 ms/token**, circa **0,033 ms/layer**: dimostra che
launch, clamp e GLU non contengono il guadagno macro richiesto. La leva resta
spenta di default e non merita un B lungo.

Il cancello offline successivo usa la coda lunga esistente da 509 cicli e non
aggiunge sonde al runtime. Con K0/AcceptMoE compact ci sono 291.000 occorrenze
di route contro 222.644 esperti unici per `(ciclo, layer)`: **68.356 duplicati,
23,490%** di letture-peso idealmente eliminabili. La riduzione e' 20,198% nei
cicli a due token e 26,060% nei cicli a tre token; 19.834/21.887 gruppi-layer
presentano almeno un riuso. Applicata ottimisticamente alle MMVQ profilate, la
forbice massima e' circa **0,348 ms/layer**, quindi supera di poco il cancello
0,284 e giustifica un solo microbraccio.

Questo fronte non e' il TILE GPU-driven falsificato: TILE deduplicava e leggeva
via SM/UVA soltanto i miss da installare. Qui gli esperti sono gia' residenti
nella slab e si vuole riusare una riga quantizzata tra input diversi nello
stesso kernel. L'idea, pero', non e' nuova nell'altro runtime: `ds4_cuda.cu`
contiene `glm_routed_moe_gateup_tok2_reuse_kernel`, attivo nel verify a due token,
che mantiene la riduzione nativa e valuta due input con un solo caricamento dei
pesi gate/up. Il port corretto deve quindi riusare quella conoscenza sul runtime
llama corrente, estenderla a n=3 e al down, e preservare i dot Q8_1 Porto; non
riscrivere una nuova aritmetica Q8_K/Q8_0.

Primo port sperimentale, dietro `LLAMA_DSV4_DECODE_EXPERT_REUSE=1`: build
Release Windows riuscita, ma nessuna misura t/s valida. Al primo forward decode,
subito dopo l'attivazione della fusione gate/up, il server termina con:

```text
D:\llama-overlap\ggml\src\ggml-cpu\ops.cpp:4823:
GGML_ASSERT(i01 >= 0 && i01 < ne01) failed
```

Il banco aveva profilo/sonde spenti, graph attivi, K0, Q8, slot diretti e piano
77+drain. Prompt 21,02 t/s; il crash arriva prima di qualsiasi riga `eval time`,
quindi **non esiste un decode t/s da riportare**. La nuova leva resta spenta e
non va combinata con altri bracci. Prima di un eventuale secondo tentativo va
isolata separatamente su gate/up IQ2_XXS e down Q2_K, confrontando direttamente
l'uscita MMID prima del router; non diagnosticare dal successivo GET_ROWS CPU.
La SOTA resta 16,0733 t/s e l'ultimo B160 valido resta 10,37 t/s nel regime di
clock contingente, non confrontabile in assoluto con la SOTA.

## Rettifica 16 agosto - il record da 16,07 non e' riprodotto dal binario corrente

Questa sezione e' piu recente e sostituisce l'ultima frase sopra. Il record
16,0733 resta una misura storica certificata, ma **non** e' la baseline
operativa corrente.

### Banco lungo K2, stesso output del record

| run | snapshot | profiler | t/s | p1 | correttezza |
|---|---:|---:|---:|---:|---|
| storico `mass2_copyall_stablelane_t473_d12_b1` | no | on | **16,04** | .90025 | 713/792, 47.906 copie, SHA file `4FDCFADF...` |
| `sota_k2_current_codegen_b1200_r1_20260816` | si | off | **9,87** | .85316 | traiettoria diversa |
| `sota_k2_no_hot_snapshot_b1200_r1_20260816` | no | off | **10,54** | .90025 | testo normalizzato identico allo storico |
| `sota_k2_no_hot_profile_diag_b1200_r1_20260816` | no | on | **10,53** | .90025 | stesso testo e contatori |
| `sota_k2_calendar_scan_gated_b1200_r1_20260816` | no | on | **10,53** | .90025 | gate scansione calendario neutro |

Il testo storico e quello nuovo hanno entrambi 3.571 caratteri dopo rimozione
CR e trim finale e sono uguali case-sensitive. Accessi target 216.737, hit
168.831 (77,9%), miss/copie 47.906; 486 cicli DSpark, 713/792 e mean len 2,47.

### Localizzazione quantitativa

Profiler a 1.951 grafi, 35,6 split/grafo:

| ms/grafo | storico | corrente | delta |
|---|---:|---:|---:|
| ingressi | 3,692 | 6,022 | +2,330 |
| sync | 2,741 | 5,120 | +2,379 |
| CPU | 1,358 | 1,655 | +.297 |
| **altri backend / graph_compute_async** | **4,080** | **22,318** | **+18,238** |
| dispatch | .193 | .308 | +.115 |
| sched-sync | .133 | .238 | +.105 |

Il delta `calc altri` vale ~35,58 s su 1.951 grafi e spiega quasi tutta la
regressione 74.804,71 -> 113.997,15 ms. Il join worker migliora 2,631 -> 2,495
ms/lavoro; CPU worker 1,772 -> 1,885. DSpark passa 14,12 -> 21,54
ms/chiamata e spiega solo ~3,4 s.

**Verdetto:** prima di 20, bisect di `ggml_cuda_graph_compute_one`/replay CUDA
con output storico fisso. Cancello: `calc altri <=5 ms/grafo`, p1=.90025,
47.906 copie, testo identico, >=15,8 t/s. Il profiler on/off nel binario
corrente vale 10,53/10,54, quindi qui misura il difetto ma non lo causa.

### Rettifica macro expert-reuse

I primi B20/crash omettevano `LLAMA_CACHE_ESPERTI_CALENDARIO_K0=1` pur usando
slot diretti: expert-id venivano interpretati come slot. Sono contaminati e non
sono una prova contro il kernel.

Banco corretto K0 + slot diretti + Q8 77+drain:

| run | t/s | esito |
|---|---:|---|
| no-dedup, dot nativo, zero-dst | **10,38** | p1=.80583, SHA `EE1E260F...`, 7.740/7.740, 78/78, bit-esatto |
| dedup globale multi | 7,71 | p1=.16197, errato |
| dedup globale dot nativo | 7,39 | stesso output errato |
| owner DS4 8 warp | 7,71 | stesso output errato |
| logical owner | 5,50 | p1=.00417, errato |
| stessa corsia nativo | 6,96 | acceptance .13014, divergenza ciclo19 |
| stessa corsia multi | 7,18 | stesso output errato |

Il no-dedup prova topologia, indirizzo slot, fusione e dot. Il difetto e'
nell'adozione owner/mate. Stessa-corsia copre solo 3.240/41.987 route = 7,7167%
e non ha ceiling sufficiente per 20: ramo sospeso finche' non torna il 16.

### Fix infrastrutturali neutri

- `kern_partiziona<planner_trace>` separa a compile time fast e strumentato:
  9,84 vs 9,87 nello snapshot-on, nessun recupero materiale.
- scansione confini calendario gated da async/slot-diretti: `calc altri`
  22,318 -> 22,014 ms/grafo, neutra.
- runner aggiunge `-PortoHotSnapshot 0|1`; il record va riprodotto con 0.

Nessun commit, push o WSL. Handoff dettagliato aggiornato nella sezione 18 di
`HANDOFF_NUOVA_CHAT_15_AGOSTO_NOTTE.md`.

## Rettifica autoritativa 16 agosto - clock GPU fuori regime

Questa sezione e' il record piu' recente e sostituisce, dove confligge, il
verdetto precedente "prima bisect del replay CUDA". Il profilo software resta
un reperto valido, ma la priorita' e' ripristinare lo stato hardware.

### Tabellone consolidato

| Braccio/reperto | Risultato | Semantica | Verdetto |
|---|---:|---|---|
| SOTA storica, tre B1200 | **16,04 / 16,11 / 16,07 = 16,0733 t/s** | p1=.90025 nel B1, 713/792, 47.906 copie, output storico | record certificato; log `D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.server.log` |
| Corrente B1200 pulito, snapshot off | **12,12 t/s** | p1=.90025, SHA `3BAC3069...`, testo normalizzato identico | baseline corrente pulita; profiler/graph-stats/polling esplicitamente off; non SOTA per clock anomalo |
| Vecchio corrente B1200 snapshot off | **10,54 t/s** | p1=.90025, 713/792, 47.906 copie, testo normalizzato identico | strumentato: il runner lasciava `LLAMA_SCHED_PROFILO=1` |
| Corrente B1200 denominato profiler on | **10,53 t/s** | stesso testo/p1/contatori | stesso regime strumentato; il vecchio confronto on/off e' ritirato |
| Worktree `893a...`, B160 | **7,97 t/s** | p1=.84848, SHA `013755F5...`, diverso dal corrente | non soluzione e non bisect valido |
| Current graph stats B160 | **10,45 t/s** | p1=.77670, graphs reused=62 | diagnostica: niente recapture per token |
| Current clean/no probes B160 | **12,34 t/s** | p1=.77670, SHA `991AF3E1...`, 83 char, length | primo riferimento breve corrente pulito; **non SOTA** e non confrontabile direttamente col B1200 |
| Hot replay richiesta 1 | **10,46 t/s** | p1=.77670, SHA `991AF3E1...` | processo caldo |
| Hot replay richiesta 2 | **10,58 t/s** | p1=.73148, SHA `54D8AE0B...` | traiettoria diversa; snapshot KV incompleto |
| Current hardware probe B160 | **10,10 t/s** | p1=.77670 | solo probe; sampling potenzialmente invasivo |

### Profiler storico contro corrente

Su 1.951 grafi, 35,6 split/grafo:

| ms/grafo | storico 16,04 | corrente 10,53 | delta |
|---|---:|---:|---:|
| ingressi | 3,692 | 6,022 | +2,330 |
| sync | 2,741 | 5,120 | +2,379 |
| CPU | 1,358 | 1,655 | +.297 |
| **altri backend / `graph_compute_async`** | **4,080** | **22,318** | **+18,238** |
| dispatch | .193 | .308 | +.115 |
| sched-sync | .133 | .238 | +.105 |

Il delta `calc altri` vale circa 35,58 s e spiega quasi tutto il delta totale,
ma non e' una prova autonoma di regressione software: la chiamata host puo'
attendere lavoro CUDA precedente. Il nuovo confronto clock/potenza rende una
GPU sottocloccata la prima variabile da correggere.

### Bisect `893a...`: isolamento riuscito, confronto fallito

```text
worktree: D:\llama-bisect-893
HEAD: 893a4867147db8185b0fd2fac44338ee3f292b05
build log: build 10090 (893a48671), MSVC Windows, CUDA arch 860
file portati/modificati: ggml/src/ggml-cuda/topk-moe.cu e topk-moe.cuh
run: bisect893_topk_profile_b160_r1_20260816
```

Il run produce 7,97 t/s, p1=.84848 e SHA `013755F5...`; il B160 corrente di
controllo ha p1=.77670 e SHA `991AF3E1...`. Poiche' top-k e traiettoria non sono
identici, non e' un punto valido di bisect e non identifica una soluzione. La
ricerca di DLL preservate del 14 agosto nelle directory storiche disponibili
non ha trovato un set attribuibile con sicurezza alla SOTA.

Il runner `work\run_porto_hot.ps1` accetta ora `-ServerPath` per selezionare il
binario del worktree isolato senza sostituire quello di `D:\llama-overlap`.

### CUDA Graph: ricattura-per-token falsificata

Nel log `current_graphstats_b160_r1_20260816.server.log`, le chiavi stabili di
decode mostrano tipicamente:

```text
calls=42 direct=1 launches=41 captures=1 incompatible=0
calls=9  direct=1 launches=8  captures=1 incompatible=0
```

Le capture aggiuntive coincidono con warm-up/cambi di forma o fase. Il replay
e' quindi effettivo; non avviene una ricattura a ogni token. La sonda graph
stats e il suo grande log restano fuori dai banchi puliti.

### Primo B160 corrente realmente pulito

```text
tag current_clean_noprobes_b160_r1_20260816
B160, R1, snapshot OFF
LLAMA_SCHED_PROFILO=0
GGML_CUDA_GRAPH_STATS=0
nessun nvidia-smi concorrente
eval 12,34 t/s; wall 16.197,9 ms
prompt 21,53 t/s
p1 .77670
SHA 991AF3E11ACEC20A7DCBB01317A7D8F4312B94592EF596721ECB4B1842899C1B
finish length; 83 caratteri
```

La semantica e' uguale al controllo B160 graph-stats (stesso p1, SHA e
lunghezza). Usando 10,49 t/s come centro dei bracci B160 con sonde, il banco
pulito guadagna `12,34 / 10,49 - 1 = 17,6%` relativo; la penalita' vale circa
il 15,0% del throughput pulito. Il numero quantifica l'invasivita' della
composizione di sonde/sampling, ma **non** sostituisce la SOTA B1200: il B160 ha
p1=.77670, mentre lo storico equivalente lungo ha p1=.90025. Classificazione:
reference breve pulita corrente, non promozione SOTA. Runner/server arrestato
con Ctrl-C; nessun processo residuo atteso.

### Prima baseline B1200 corrente realmente pulita

```text
tag current_clean_noprobes_b1200_r1_20260816
B1200, R1, snapshot OFF
LLAMA_SCHED_PROFILO=0 (override esplicito)
GGML_CUDA_GRAPH_STATS=0 (override esplicito)
nessun nvidia-smi concorrente
eval 12,12 t/s; wall richiesta 102.460,6 ms
prompt 20,31 t/s
p1 .90025
SHA 3BAC3069DD0E47D38F09CD6A0608E6B6F47B95CDE64D1CE79A79B30E3F4CA31A
finish length; 3.572 caratteri
```

Lo SHA e' quello gia' verificato equivalente allo storico dopo normalizzazione
di BOM/CR/newline; p1 coincide esattamente. La chiamata precedente etichettata
come profiler-off non conteneva l'override e il runner impostava il profiler a
1: il verdetto 10,54 off / 10,53 on e' ritirato. Il guadagno 10,53 -> 12,12 e'
**+15,1% relativo**, equivalente a circa **13,1% del throughput pulito** perso
alla strumentazione. Restano 3,9533 t/s rispetto alla media storica 16,0733.
Classificazione: baseline operativa corrente pulita, non nuova SOTA finche' il
regime clock/potenza non viene ripristinato e verificato. Server arrestato con
Ctrl-C.

### Hot replay e riuso KV: snapshot ancora incompleto

Il prompt cache salva 227 token e 89,538 MiB totali, ma solo 0,754 MiB sono
dichiarati draft. Alla seconda richiesta il restore contiene:

```text
pos_min=0, pos_max=0, n_tokens=1, n_past=1, size=12,826 MiB
prompt eval successivo: 67 token su 68
```

Quasi tutto il prompt viene rivalutato; p1 e SHA cambiano. 10,46/10,58 prova
soltanto che processo, modelli e DLL restano caldi, non che target KV, stato
DSpark, cache esperti e slab siano ripristinati in modo completo e neutro.

### Telemetria hardware: prova che cambia la priorita'

CSV storico SOTA (`mass2_copyall_stablelane_t473_d12_b1.hw.csv`, confermato
da B2/B3), durante decode:

```text
SM clock 1927-1950 MHz, stabilizzato a 1950 MHz
memory clock 7301 MHz
power circa 95-100 W nella parte stabile
PCIe Gen4 x16
throttle mask 0 durante il carico
```

Sonda corrente sotto carico:

```text
SM/core clock circa 780 MHz
power circa 50-56 W
PCIe Gen4 x16
nessun thermal throttle
counter/evento software power capping presente
piano Windows: Prestazioni elevate
```

Il PCIe non e' degradato e non c'e' evidenza termica. Il regime corrente e'
compatibile con un profilo driver/potenza software. `nvidia-smi -rgc` e' stato
negato per privilegi insufficienti: nessun reset clock e' avvenuto. Non
aggirare il controllo. Il sampling `nvidia-smi` puo' rallentare e va usato solo
in un probe breve separato, mai nel B1200 finale.

### Decisione e cancello

1. La baseline operativa corrente pulita e' 12,12 t/s su B1200; non e' una
   nuova SOTA finche' clock e potenza non sono corretti. 12,34 resta la
   reference breve B160.
2. Questa decisione hardware e' ritirata dalla rettifica seguente: il driver
   raggiunge 1950 MHz sotto carico compute e il keeper peggiora Porto.

Nessun commit, nessun push, nessun WSL. Le build/run gia' registrate erano
Windows native. In questo aggiornamento documentale non sono stati eseguiti
run o build e non e' stato modificato alcun repository.

## Rettifica autoritativa: hot snapshot corretto e switch verificato

Il microprobe CUDA raggiunge 1950 MHz e 126 W senza throttle. Un keeper da un
blocco porta il core a circa 1792 MHz ma peggiora il B160 corretto a 10,14 t/s;
non esiste un blocco hardware globale da rimuovere come prerequisito.

La divergenza hot nasceva dal prompt forzato in 67+1 invece del batching
naturale 64+4. Rimosso il break sull'ultimo token, la cattura avviene prima del
decode dell'ultimo ubatch naturale. Sono inoltre usati snapshot ON_DEVICE per
target/draft e il formato ON_DEVICE DS4 include i tre KV ring hot; il formato
host resta invariato.

Tabellone valido:

| Braccio | Risultato | Correttezza |
|---|---:|---|
| B160 mask0 naturale | 10,04 t/s | p1=.77670, SHA `991AF3...` |
| B160 target-only naturale | 10,08 t/s | p1=.77670, SHA `991AF3...` |
| B160 full mask15 naturale | 10,31 t/s | p1=.77670, SHA `991AF3...` |
| B160 full R1/R2 | 10,05 / 10,64 t/s | stesso p1 e SHA; wall 19,51 -> 15,67 s |
| B1200 full R1/R2 | **12,12 / 12,22 t/s** | entrambi p1=.90025, SHA `3BAC3069...` |

Switch `ON -> OFF -> ON` B160:

```text
ON  10,35 t/s p1 .77670 SHA 991AF3...
OFF 10,11 t/s p1 .73148 SHA 54D8AE...
ON  10,68 t/s p1 .77670 SHA 991AF3...
```

Lo snapshot target+DSpark+stato spec+cache esperti e lo switch per-request sono
quindi verificati. La SOTA resta 16,0733 e l'obiettivo 20 t/s resta aperto.
Prossimo fronte: macro-kernel decode v2 attorno alla MMQ Porto, poi planner
globale target+DSpark/trasporto persistente. Nessun commit, push o WSL.
