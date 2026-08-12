# Audit 10 — zero-copy e memoria pinnata sommate

Perimetro: sola lettura statica del tree corrente. Il conto sotto è la somma
delle richieste di pin/lock del massimo assetto **compatibile** con la campagna.
La configurazione letterale «tutte le leve accese» non esiste: NextN CPU e lane
G132 sono respinte insieme già in apertura (`ds4-p4a/ds4.c:22681-22690`).

## (1) BUG

### Conto verificato prima dei bug

| componente vivo nell'assetto compatibile | byte/GiB richiesti | prova nel codice |
|---|---:|---|
| NextN `DS4_NEXTN_PIN=2` | circa **4,27 GiB** | il modo 2 somma testa, tensori dense e i tre tensori routed completi (`ds4-p4a/ds4.c:22409-22417`) e poi applica `VirtualLock` a dense, testa ed esperti (`ds4-p4a/ds4.c:22423-22442`); il commento verificato quantifica ~741 MB + ~3,54 GiB (`ds4-p4a/ds4.c:22315-22318`) |
| finestra masked zero-copy | **2,000 GiB** | il budget env viene convertito in GiB binari (`ds4-p4a/ds4_cuda.cu:3736-3745`) e la finestra contigua viene troncata a quel budget e registrata (`ds4-p4a/ds4_cuda.cu:17282-17298`) |
| arena `KV_STAGED_RING`, ctx 150000 | **2.075.425.792 B = 1,9329 GiB** | 43 raw cache da 128×512×4 B, 21 compresse ratio 4, 20 ratio 128 e 21 indexer cache ratio 4: geometria a `ds4-p4a/ds4.c:105-124`, alternanza a `ds4-p4a/ds4.c:450-455`, cap `ctx/ratio+2` a `ds4-p4a/ds4.c:13109-13116`, allocazioni a `ds4-p4a/ds4.c:13153-13160` e `ds4-p4a/ds4.c:13178-13182`; l'intera somma viene passata a un solo `cudaHostAlloc` (`ds4-p4a/ds4_cuda.cu:21854-21885`) |
| `indexerzc` completo | **363.331.668 B = 0,3384 GiB** su Windows | payload: 21×(1024×8192×2 + 4096×64×2), dalle shape verificate (`ds4-p4a/ds4.c:105`, `ds4-p4a/ds4.c:114`, `ds4-p4a/ds4.c:122-123`, `ds4-p4a/ds4.c:3178-3183`); sono 42 allocazioni e su Windows `g_model_direct_align` resta 1 (`ds4-p4a/ds4_cuda.cu:1902-1904`; l'unica crescita è nel ramo Linux a `ds4-p4a/ds4_cuda.cu:17463-17470`), quindi il codice aggiunge 2 B di slack per tensore (`ds4-p4a/ds4_cuda.cu:4017-4027`) |
| pool staging modello | circa **256 MiB** | chunk default 64 MiB (`ds4-p4a/ds4_cuda.cu:6172-6183`), quattro buffer host pinnati (`ds4-p4a/ds4_cuda.cu:6532-6554`) |
| staging route DOV/ENFORCE | **42.467.328 B = 40,5 MiB** | 6 route (`ds4-p4a/ds4_cuda.cu:28175-28178`) × 7.077.888 B/esperto nativo (`ds4-p4a/ds4_cuda.cu:51669-51675`), allocati come gate+up+down host (`ds4-p4a/ds4_cuda.cu:39313-39343`) |
| due ring shared1 | **128 KiB** | 4 slot da 16 KiB per ring (`ds4-p4a/ds4.c:11262-11264`, `ds4-p4a/ds4.c:11917-11920`) |

Totale additivo verificabile: **circa 8,831 GiB**, esclusi piccoli control
buffer, top-k host ed eventuale embedding staging. È il **13,8% di 64 GiB**
(oppure circa il 14,8% di 64 GB decimali). Non è necessariamente il numero di
pagine fisiche *distinte*: la testa NextN appartiene alla mappa primaria
(`ds4-p4a/ds4.c:22370-22373`) e il tree non consente di provare dal solo codice
se una sua parte cade nei primi 2 GiB della finestra. È invece il totale delle
richieste che i due sottosistemi presentano a Windows/CUDA.

Il solo lato CUDA vale già circa **4,561 GiB**: finestra 2 GiB + KV 1,9329 GiB
+ indexer 0,3384 GiB + stage 0,25 GiB + route 0,0396 GiB. `VirtualLock` NextN
aggiunge separatamente circa 4,27 GiB.

### BUG ZC-1 — il budget da 2 GiB non è un budget globale e viene superato

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:1071-1079`,
  `ds4-p4a/ds4_cuda.cu:17282-17298`,
  `ds4-p4a/ds4_cuda.cu:4017-4052`,
  `ds4-p4a/ds4_cuda.cu:21873-21885`.
- **Severità: ALTA.**
- **Prova:** la finestra contigua usa fino a tutto
  `cuda_host_register_budget_bytes()` ma, dopo il successo, scrive soltanto
  `g_model_window_bytes`; non incrementa
  `g_model_registered_range_bytes` (`ds4-p4a/ds4_cuda.cu:17287-17298`).
  `indexerzc` decide invece l'ammissione usando esclusivamente
  `g_model_registered_range_bytes + alloc_bytes` e incrementa quel solo
  accumulatore (`ds4-p4a/ds4_cuda.cu:4019-4052`). Anche l'arena KV da 1,93
  GiB è un `cudaHostAlloc` che non tocca l'accumulatore
  (`ds4-p4a/ds4_cuda.cu:21873-21885`), come pure pool e staging route.
- **Scenario concreto di fallimento:** input env
  `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB=2`, finestra primaria registrata
  con successo, KV staged migrata, poi pos>=2051. Stato reale prima
  dell'indexer: già circa 4,22 GiB di `hostreg+hostpin` CUDA; stato visto
  dall'ammissione indexer: 0. Il flag ammette altri 346,5 MiB pur dichiarando
  lo stesso tetto. Esito sbagliato: il limite operativo di 2 GiB è violato di
  oltre 2,5 GiB; un `cudaHostAlloc` tardivo può fallire e cambiare braccio di
  esecuzione a metà decode. Il sintomo certo è
  `[cuda-alloc-kind] hostreg live_mib` + `hostpin live_mib` molto maggiore del
  budget mentre `[indexer-zc]` non riporta `host-pin-budget-exceeded`; il
  tracciatore espone entrambi i kind a `ds4-p4a/ds4_cuda.cu:791-799`.

### BUG ZC-2 — su esaurimento host-pin, il retry della cache riduce la VRAM ma non l'allocazione che ha fallito

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:39231-39269`,
  `ds4-p4a/ds4_cuda.cu:39313-39343`,
  `ds4-p4a/ds4_cuda.cu:39703-39760`.
- **Severità: MEDIA.**
- **Prova:** il ciclo riduce `cap` del 10% dopo qualunque errore
  (`ds4-p4a/ds4_cuda.cu:39744-39750`), ma lo staging host del route worker è
  sempre dimensionato su `CUDA_MOE_ROUTE_COUNT`, non su `cap`
  (`ds4-p4a/ds4_cuda.cu:39313-39343`). Ridurre gli slot può curare un OOM
  VRAM del resident slab, non un `cudaHostAlloc` rifiutato.
- **Scenario concreto di fallimento:** NextN PIN=2, finestra, KV e pool hanno
  già consumato il lock/pin disponibile; `cudaHostAlloc(host_packed_base)`
  fallisce durante `cuda_moe_expert_cache_prepare`. Ogni retry ripresenta lo
  stesso buffer host da 40,5 MiB, cammina inutilmente fino a `cap=0` e infine
  rilascia/disabilita la cache (`ds4-p4a/ds4_cuda.cu:39751-39761`). Esito:
  perdita completa del resident expert cache pur potendo esserci VRAM
  sufficiente per una capacità ridotta. A banco: sequenza
  `CUDA resident expert cache allocation failed at N slots ... retry=...`
  con `N` decrescente e righe `[cuda-alloc-row] ... hostpin ... fails>0`
  (`ds4-p4a/ds4_cuda.cu:783-788`).

### BUG ZC-3 — l'arena KV resta pinnata anche dopo il restore di fine richiesta

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:21806-21817`,
  `ds4-p4a/ds4_cuda.cu:21832-21838`,
  `ds4-p4a/ds4_cuda.cu:31107-31114`.
- **Severità: MEDIA.**
- **Prova:** a fine richiesta `cuda_kv_staged_restore_to_device()` passa
  `release_arena=sticky`; nel caso sano `sticky=0`, quindi copia i tensori in
  device, mette `host_resident=0`, ma non esegue `cudaFreeHost`
  (`ds4-p4a/ds4_cuda.cu:21806-21817`, `ds4-p4a/ds4_cuda.cu:21832-21838`).
- **Scenario concreto di fallimento:** richiesta ctx 150000 conclusa
  correttamente, KV ripristinata in VRAM, sessione ancora viva; l'arena da
  1,9329 GiB rimane pinnata pur non servendo alcun tensore host. Una richiesta
  successiva o un'allocazione indexer tardiva trova 1,93 GiB di headroom in
  meno e può fare sticky-off/fail-open. A banco:
  `[cuda-alloc-kind] kind=hostpin live_mib` resta alto nel summary
  `phase=request-end`, emesso proprio dopo il restore
  (`ds4-p4a/ds4_cuda.cu:31111-31114`).

### BUG ZC-4 — `active=1` non distingue indexer completo da indexer parziale

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:3967-3975`,
  `ds4-p4a/ds4_cuda.cu:3983-4005`.
- **Severità: BASSA.**
- **Prova:** dopo un fail-open le entry precedenti restano; al loro primo
  riuso viene comunque stampato `active=1`, con il numero reale di tensori ma
  senza un campo `partial/full` (`ds4-p4a/ds4_cuda.cu:3987-4005`).
- **Scenario concreto di fallimento:** 20 allocazioni su 42 riescono, la
  ventunesima fallisce; il run seguente nel medesimo decode stampa prima
  `pin_failed ... tensors=20`, poi `active=1 tensors=20`. Un harness che
  qualifica il braccio soltanto su `active=1` classifica come indexerzc pieno
  un percorso misto e attribuisce in modo errato tempi/sfratti alla leva
  completa.

## (2) INTERFERENZE FRA LEVE

### `MASKED_BUDGET=2` + `KV_STAGED_RING=1` + `INDEXER_HOST_ZEROCOPY=1`

- **Meccanismo:** sono tre proprietari della stessa risorsa fisica, ma solo
  l'indexer consulta `g_model_registered_range_bytes`; finestra e KV non lo
  alimentano (`ds4-p4a/ds4_cuda.cu:17287-17298`,
  `ds4-p4a/ds4_cuda.cu:21873-21885`,
  `ds4-p4a/ds4_cuda.cu:4019-4052`). La somma CUDA è circa 4,56 GiB, non 2
  GiB.
- **Manifestazione a banco:** divergenza tra
  `[cuda-alloc-kind] kind=hostreg/hostpin live_mib`
  (`ds4-p4a/ds4_cuda.cu:791-799`) e il budget; possibili
  `[kv-staged] sticky-off reason=pinned arena allocation failed`
  (`ds4-p4a/ds4_cuda.cu:21752-21759`) o
  `[indexer-zc] pin_failed reason=cudaHostAlloc`
  (`ds4-p4a/ds4_cuda.cu:4025-4031`).
- **Guardia suggerita/combinazione da vietare:** non chiamare «budget 2 GiB»
  questo braccio se `hostreg_live + hostpin_live` supera 2048 MiB. Per la
  campagna, considerare valido il triplo ON solo con preflight che riservi la
  somma intera e con `kv migrated` + `indexer tensors=42`; altrimenti vietare
  il triplo e testare indexerzc senza KV staged.

### tripla precedente + `NEXTN_CPU_DRAFTER=1, NEXTN_PIN=2`

- **Meccanismo:** `VirtualLock` ha un'ammissione distinta da CUDA. Il codice
  prova ad aumentare min/max working set una sola volta ma ignora l'esito di
  `SetProcessWorkingSetSize` (`ds4-p4a/ds4.c:22347-22355`), poi tenta ogni
  tensore separatamente e continua dopo i fallimenti
  (`ds4-p4a/ds4.c:22423-22442`). Non esiste un contatore che sottragga questi
  ~4,27 GiB dal budget CUDA.
- **Manifestazione a banco / chi fallisce per primo:** staticamente non è
  determinabile quale quota Windows si esaurisca prima, perché working-set
  lock e host-pin CUDA non hanno un arbitro comune nel tree. L'ordine
  temporale è però verificato: NextN tenta `VirtualLock` prima di
  `ds4_gpu_init` (`ds4-p4a/ds4.c:22718-22743`); la finestra CUDA viene dopo;
  KV migra a decode-start (`ds4-p4a/ds4_cuda.cu:30995-31002`); indexer arriva
  solo quando `layer_n_comp > top_k` (`ds4-p4a/ds4.c:13925-13947`).
  Quindi:
  1. se non cresce il working set, falliscono per primi alcuni `VirtualLock`
     e NextN degrada a page cache, visibile in
     `pin mode=2 locked=... failed=...`
     (`ds4-p4a/ds4.c:22444-22449`);
  2. se NextN riesce, il candidato tardivo più esposto è indexerzc, che fa
     fail-open; KV può però fallire prima a decode-start e restare in device;
  3. se fallisce lo staging route, scatta il BUG ZC-2 e si perde la cache.
- **Guardia suggerita/combinazione da vietare:** il totale additivo è ~8,831
  GiB. Non accettare il braccio all-levers se `failed!=0`, se la somma
  `hostpin+hostreg` del trace non coincide con le allocazioni attese, o se
  `indexer tensors!=42`. Per un verdetto causale su indexerzc, vietare PIN=2
  nel primo A/B e aggiungerlo solo in un braccio separato.

### `INDEXER_HOST_ZEROCOPY=1` parziale + fallback fd-cache

- **Meccanismo:** il primo GEMV indexer viene lanciato asincrono su stream 0
  (`ds4-p4a/ds4_cuda.cu:23049-23059`). Se il tensore successivo non è stato
  pinnato, il fallback legge e accoda H2D su `g_model_upload_stream`, poi
  sincronizza solo quello stream (`ds4-p4a/ds4_cuda.cu:8832-8869`). Il GEMV
  UVA precedente può quindi essere ancora in volo mentre parte l'H2D del
  tensore fd-cache: questa è la contesa PCIe diretta che il percorso pieno
  non ha.
- **Manifestazione a banco:** `pin_failed pinned_so_far>0`, poi
  `active=1 tensors<42`; con `DS4_CUDA_WEIGHT_CACHE_VERBOSE=1` compaiono
  `CUDA fd-cached indexer_f16` (`ds4-p4a/ds4_cuda.cu:8882-8887`). Sintomo:
  spike del primo encode post-2051 e aumento degli sfratti; il transport
  ledger non vede né letture UVA né questi pesi, perché esclude
  esplicitamente host-mapped GPU reads (`ds4-p4a/ds4_cuda.cu:28196-28201`).
- **Guardia suggerita/combinazione da vietare:** per i banchi di promozione,
  vietare il modo misto: `pin_failed` o `tensors!=42` rende il run invalido.
  Non usare `h2d_bytes_total` come prova di assenza di contesa.

### `INDEXER_HOST_ZEROCOPY=1` + `KV_STAGED_RING=1`

- **Meccanismo:** a regime pieno non sono concorrenti all'inizio dello
  scoring: i due GEMV indexer sono accodati prima della chiamata score
  (`ds4-p4a/ds4.c:13943-13982`); lo staged-indexer registra
  `producer_ready` su stream 0 e il copy stream lo aspetta
  (`ds4-p4a/ds4_cuda.cu:21743-21749`), quindi il primo burst H2D della
  K-cache parte solo dopo i GEMV UVA. Restano però traffici PCIe
  **consecutivi** molto grandi; i batch H2D successivi sono pipelinati col
  kernel score mediante `slot_ready/slot_consumed`
  (`ds4-p4a/ds4_cuda.cu:22360-22394`).
- **Manifestazione a banco:** aumento additivo di `decode_score`/tempo encode
  senza aumento corrispondente del transport ledger; gli eventi KV wait sono
  contati nel trace in `cuda_decode_trace_kv_wait_event`
  (`ds4-p4a/ds4_cuda.cu:22373-22380`), mentre i 363 MB UVA non hanno contatore
  host.
- **Guardia suggerita/combinazione da vietare:** nessun divieto di
  correttezza; per attribuire il costo servono bracci `indexerzc ON/KV OFF`,
  `OFF/ON`, `ON/ON`. Vietare conclusioni basate sul solo `pcie_busy_pct`,
  che deriva esclusivamente dai batch esperto del ledger
  (`ds4-p4a/ds4_cuda.cu:28659-28684`).

### `INDEXER_HOST_ZEROCOPY=1` + `DRAIN_OVERLAP4=1`

- **Meccanismo:** il DOV può sovrapporre H2D esperti alla passata hit dello
  stesso layer, perché il fence è posto dopo gli hit e prima dei miss
  (`ds4-p4a/ds4_cuda.cu:49846-49861`). Non si sovrappone invece al GEMV
  indexer dello stesso layer: l'indexer è accodato prima del router
  (`ds4-p4a/ds4.c:13943-13995`, `ds4-p4a/ds4.c:14192-14212`) e il worker non
  vede la richiesta finché il resolver, accodato successivamente su stream
  0, non viene eseguito (`ds4-p4a/ds4_cuda.cu:47741-47775`).
- **Manifestazione a banco:** nessuna crescita causale attesa di
  `drain_overlap_ms` dovuta ai GEMV indexer; se cresce insieme a
  `indexer-zc`, cercare prima il modo parziale/fd-cache o altro traffico
  host-mapped. Il DOV espone `drain_overlap_ms` solo quando ritira lo stream
  upload (`ds4-p4a/ds4_cuda.cu:37563-37585`).
- **Guardia suggerita/combinazione da vietare:** combinazione ammessa; vietare
  l'interpretazione «stesso PCIe quindi sicuramente simultanei». Invalidare
  invece il run se indexer è parziale.

### `INDEXER_HOST_ZEROCOPY=1` + `NEXTN_PIN=2` + `CPU_SHARED_EXPERT_DEDICATED=N`

- **Meccanismo:** non condividono un lock, ma condividono banda DRAM.
  Il drafter esegue fino a `k+1` forward+head sul worker e sul pool G132
  (`ds4-p4a/ds4.c:10093-10116`); shared1 avvia per ogni layer il D2H e il
  lavoro CPU prima del router (`ds4-p4a/ds4.c:12069-12130`,
  `ds4-p4a/ds4.c:14192-14200`). L'affinità dedicata sposta i thread, non
  separa il memory controller (`ds4-p4a/ds4.c:11496-11504`). I GEMV UVA
  indexer devono attraversare sia DRAM sia PCIe.
- **Manifestazione a banco:** `indexer decode_score` peggiora, ma anche
  `nextn step_ms/fwd_dense/head_avg` e `shared_cpu_ms` crescono; il
  `h2d_bytes_total` resta invariato. Le statistiche NextN sono emesse a
  `ds4-p4a/ds4.c:20811-20821`; shared1 misura CPU e wait nel worker
  (`ds4-p4a/ds4.c:11761-11777`).
- **Guardia suggerita/combinazione da vietare:** per giudicare indexerzc,
  vietare il triplo nel braccio iniziale. L'affinità può restare per la prova
  core, ma non va trattata come isolamento della banda.

### `NEXTN_CPU_DRAFTER=1` + `G132_CPU_LANE=1`

- **Meccanismo:** entrambi reclamano la lane/pool G132; il codice li dichiara
  mutuamente esclusivi (`ds4-p4a/ds4.c:22681-22690`).
- **Manifestazione a banco:** nessun banco: engine-open stampa la riga di
  mutua esclusione, chiude l'engine e ritorna errore.
- **Guardia suggerita/combinazione da vietare:** combinazione già vietata.
  Il conto di 8,831 GiB assume lane G132 OFF e pool G132 creato dal drafter
  (`ds4-p4a/ds4.c:22701-22721`).

## (3) ESCLUSIONI

- **Il fail-open indexer è corretto sui dati, pur lasciando intenzionalmente
  un assetto misto.** Ogni lookup cerca prima tutte le entry già valide e
  restituisce il loro UVA (`ds4-p4a/ds4_cuda.cu:3983-4007`); dopo il latch
  una miss torna NULL (`ds4-p4a/ds4_cuda.cu:4009-4012`) e il chiamante
  prosegue nella fd-cache (`ds4-p4a/ds4_cuda.cu:4113-4127`). Il puntatore è
  risolto per singolo GEMV (`ds4-p4a/ds4_cuda.cu:22999-23008`): non esiste
  un'invariante che richieda tutti i 42 tensori nello stesso dominio. Su
  fallimento di lettura o mapping, il buffer corrente viene liberato prima
  del latch (`ds4-p4a/ds4_cuda.cu:4033-4046`). Quindi «metà qua e metà là» è
  performance/telemetria, non byte sbagliati.

- **Non c'è doppio conteggio fra entry indexer e per-range registrate
  nell'accumulatore.** Entrambe verificano e poi incrementano lo stesso
  `g_model_registered_range_bytes`
  (`ds4-p4a/ds4_cuda.cu:4019-4052`,
  `ds4-p4a/ds4_cuda.cu:4143-4155`). Su Windows le per-range sono inoltre
  disabilitate dopo il tentativo di finestra
  (`ds4-p4a/ds4_cuda.cu:17312-17314`). Il difetto è l'opposto: finestra e
  altri `cudaHostAlloc` sono omessi.

- **Un indexer già coperto dalla finestra non viene duplicato.** Il fast path
  della finestra precede il gate indexerzc
  (`ds4-p4a/ds4_cuda.cu:4075-4081`,
  `ds4-p4a/ds4_cuda.cu:4113-4123`). Solo i tensori fuori finestra possono
  creare i buffer indexer dedicati.

- **Il fallimento dell'arena KV è fail-safe.** Se il suo `cudaHostAlloc`
  fallisce, viene impostato sticky-off e la migrazione ritorna prima di
  liberare i tensori device (`ds4-p4a/ds4_cuda.cu:21873-21881`); il chiamante
  di decode-start ignora il mancato guadagno VRAM ma continua con la KV
  originale (`ds4-p4a/ds4_cuda.cu:30999-31002`). Nessun mezzo trasferimento
  viene pubblicato come host-resident.

- **I fallimenti `VirtualLock` NextN non rendono il modello inaccessibile.**
  Ogni regione fallita viene solo sommata a `failed` e il loop continua
  (`ds4-p4a/ds4.c:22423-22442`); i pesi restano nella mmap e il worker li
  legge normalmente. Il degrado concreto è page fault/page-cache, non
  corruzione.

- **`DS4_CUDA_PIN_BACKBONE` non aggiunge RAM host pinnata.** La leva protegge
  vittime VRAM e cede il resident expert slab (`ds4-p4a/ds4_cuda.cu:8086-8096`,
  `ds4-p4a/ds4_cuda.cu:8701-8726`); non contiene `VirtualLock`,
  `cudaHostAlloc` o `cudaHostRegister`. Non va sommata agli 8,831 GiB.

- **DOV non legge indexer host e il ledger non può misurarlo.** Il fence DOV
  governa esclusivamente gli slot/route pointer degli esperti
  (`ds4-p4a/ds4_cuda.cu:37446-37457`); il ledger dichiara fuori dominio le
  letture GPU host-mapped (`ds4-p4a/ds4_cuda.cu:28196-28201`). Un
  `h2d_bytes_total` stabile non esclude traffico indexer UVA.

- **Il rilascio finale indexer è ordinato nel cleanup normale.**
  `ds4_gpu_cleanup` sincronizza il device prima dei rilasci
  (`ds4-p4a/ds4_cuda.cu:9056-9068`); i buffer indexer vengono liberati nel
  ciclo di vita dei range (`ds4-p4a/ds4_cuda.cu:3953-3965`,
  `ds4-p4a/ds4_cuda.cu:8985-9011`). Non risulta un use-after-free nel
  teardown ordinario.
