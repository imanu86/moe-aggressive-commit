# Lane G132 concorrente sul percorso MoE generale

## Esito e perimetro

`lane.patch` modifica soltanto `ds4-p4a/ds4_cuda.cu` e collega la lane CPU
IQ2_XXS/Q2_K al solo `ds4_gpu_routed_moe_one_tensor()` generale. Non modifica
ammissione alla cache, politica di residenza, soglie, vittime o dimensionamento
della cache esperti.

L'abilitazione richiede **entrambi**:

```text
DS4_G132_CPU_LANE=1
DS4_G132_CPU_LANE_GENERAL=1
```

`DS4_G132_CPU_LANE_MAX` resta il limite/seed già esistente (default 3).
`GENERAL` è il solo flag nuovo.

La patch è prodotta sul working tree corrente di `ds4-p4a`, HEAD
`646f3beb77732ca286e9bf9f38cf0d63d3ecc78a`. Il file sorgente era già
modificato rispetto a HEAD; il diff è quindi intenzionalmente ancorato al suo
contenuto corrente, non al blob di HEAD.

## Correzione della premessa numerica

Il valore 0,97 ms è reale, ma non è una misura del worker G132:

- `ds4-p4a/g7_runs/g29_gate_layer10_warm5.stderr.log:18` misura un expert in
  0,970 ms con `threads=12`;
- `ds4-p4a/g7_runs/g29_gate_layer10_warm5.stderr.log:19` misura sei expert in
  5,629 ms;
- quel benchmark chiama `matvec_iq2_xxs_expert_pair_prequant()` e
  `matvec_q2_k_expert()` (`ds4-p4a/ds4.c:12665` e
  `ds4-p4a/ds4.c:12682`), che a loro volta usano il pool
  `ds4_parallel_for()` per le righe (`ds4-p4a/ds4.c:4659` e
  `ds4-p4a/ds4.c:4788`).

G132 usa invece al massimo sei worker persistenti e assegna un expert intero a
ciascun worker (`ds4-p4a/ds4_cuda.cu:49105` dopo applicazione); ciascun worker
esegue i dot scalar della lane. Quindi l'inferenza
`tempo_cpu_lane = n_cpu * 0,97 ms` non è dimostrata dal g29: sotto questa patch
gli expert CPU possono anche procedere in parallelo fra loro, ma con kernel CPU
diverso. Anche la contesa concorrente CPU/GPU resta da misurare.

La previsione di circa 7,00 t/s resta perciò un bersaglio falsificabile, non una
conseguenza già provata dei due benchmark separati. I criteri indicati nel
mandato restano validi: circa 4,2 t/s indica assenza di leva; meno di 4,15 t/s
indica serializzazione/regressione. Il bilanciatore non incorpora 0,97 o 0,88:
usa esclusivamente i tempi osservati in concorrenza.

## Esclusione assoluta di Q1/IQ1

Il dispatch generale è separato dal dispatch storico
(`ds4-p4a/ds4_cuda.cu:48663-48703`):

- `ds4_gpu_routed_moe_one_tensor()` usa
  `g_cuda_routed_moe_general_launch_dispatch`;
- il chiamante mixed/Q1 conserva `g_cuda_routed_moe_launch_dispatch`, sempre
  specializzato con `G132=false`;
- MTP usa esplicitamente `<false, false>`;
- la richiesta route abilita la lane solo nella specializzazione generale;
- l'ingresso al route cache che può costruire il piano esclude già
  `route_iq1_s` e `route_q1_0` (`ds4-p4a/ds4_cuda.cu:46722`).

La lane generale accetta soltanto `route_iq2_q2`, un token, e il contratto
nativo esatto IQ2_XXS gate/up + Q2_K down. Non introduce, richiede o percorre
Q1_0/IQ1_S. La semantica del vecchio chiamante mixed resta invariata quando
`GENERAL=0`: in particolare mantiene il suo ordine storico del router weight.
La lane generale applica invece il router weight prima della quantizzazione
Q8_K del mid, come il percorso GPU (`ds4-p4a/ds4_cuda.cu:49015-49092`).

## Dove avviene la partizione e perché i byte non attraversano il bus

Il resolver pubblica nel mailbox il bit compile-time `cpu_lane_allowed`
(`ds4-p4a/ds4_cuda.cu:873` e `:25650-25699`). Il worker costruisce un piano
per la generazione corrente (`:39626`) e valuta solo route già decise
transienti: l'ammissione avviene nel ramo `promote == false`, dopo che esiste un
puntatore host esatto ma **prima** di ogni H2D e prima della pubblicazione in
`route_transient_*` (`:39650-39739` e `:40609-40625`).

Per una route accettata il worker:

1. conserva solo puntatori gate/up/down, expert id, indice route e router
   weight;
2. prende la reservation del backing;
3. marca il bit CPU e fa `continue`, saltando copia, contatori H2D e publish.

Dopo il drain del worker, un kernel 1x1 compatta nei buffer lane soltanto i
puntatori e i weight delle route GPU, rispettandone l'ordine originale
(`ds4-p4a/ds4_cuda.cu:25793` e `:47106-47145`). `n_expert` viene ridotto solo
dopo l'eventuale classificazione G73, così G73 vede sempre tutte le route.

Il contratto controlla che:

```text
2 * gate_expert_bytes + down_expert_bytes == 7.077.888
```

(`ds4-p4a/ds4_cuda.cu:49608-49646`). Una route CPU evita quindi esattamente
7.077.888 byte H2D. L'unico ritorno della lane è il parziale F32 da 4096
elementi, 16 KiB.

La demand pipeline è stata resa consapevole del numero di route CPU:
`publish.count + cpu_routes == miss_count` (`ds4-p4a/ds4_cuda.cu:38844` e
`:40790`). Non cambia la sua politica; evita soltanto che l'assenza intenzionale
di publish CPU venga interpretata come batch incompleto.

## Concorrenza reale e sincronizzazione

La sequenza è:

1. stream CUDA 0 registra `input_source_ready` immediatamente prima dello
   stadio MoE GPU;
2. `bridge_stream`, creato `cudaStreamNonBlocking`, attende quell'evento,
   copia D2H i 16 KiB dell'input e lancia una host callback;
3. la callback segna `cpu_started`, pubblica `input_ready` sotto mutex e fa
   broadcast ai worker CPU;
4. senza attendere la CPU, stream 0 esegue quantizzazione input, gate/up,
   quantizzazione mid, down e accumulo delle route GPU;
5. due host callback brevi sullo stream 0 delimitano il wall-time GPU; quella
   finale pubblica `gpu_done`;
6. il thread chiamante attende su `done_cond` finché sono veri sia
   `completed_jobs == job_count` sia `gpu_done`;
7. solo allora `bridge_stream` copia H2D il parziale CPU da 16 KiB, registra
   `partial_copy_done`; stream 0 attende l'evento e lancia l'add finale.

Le primitive sono quindi eventi CUDA cross-stream, `cudaLaunchHostFunc`,
mutex/condition variable OS e un unico evento di join. I punti di codice sono
`ds4-p4a/ds4_cuda.cu:49734-49839` e `:49842-50031`.

Non esiste un'attesa CPU prima del lancio GPU. La sola coda seriale obbligatoria
è il join del parziale 16 KiB dopo il completamento di entrambi i lati.

Le route CPU sono ridotte in ordine di ammissione, che coincide con l'ordine
delle route miss prodotto dal resolver. Il weight viene applicato prima del
mid Q8_K per ogni route; il parziale CPU viene poi sommato all'accumulo GPU.
Questo preserva la semantica dei router weight, pur non promettendo identità
bit-a-bit per il diverso raggruppamento delle somme F32.

## Bilanciamento adattivo

Lo stato è separato per i 43 layer. Il target iniziale è
`min(DS4_G132_CPU_LANE_MAX, route_count - 1)`; resta sempre almeno una route sul
lato GPU. Dopo ogni layer completato si misurano sullo stesso clock host:

```text
cpu_wall = cpu_finished - cpu_started
gpu_wall = gpu_finished - gpu_started
hysteresis = max(0,150 ms, 10% * max(cpu_wall, gpu_wall))
```

Se `cpu_wall - gpu_wall` supera l'isteresi, il target CPU scende di una route;
se è inferiore all'isteresi negativa, sale di una route. Una modifica richiede
tre campioni consecutivi nella stessa direzione e impone poi quattro chiamate
di cooldown. Un campione dentro l'isteresi azzera la streak
(`ds4-p4a/ds4_cuda.cu:49933-49963`).

Il target è vincolato a `[1, min(max_configurato, route_totali - 1)]`.
L'ammissione effettiva può essere inferiore se non ci sono abbastanza
transienti sicuri. Le route ulteriori sono contate separatamente come
`rejected_cap` quando domina il massimo configurato, oppure
`rejected_balance` quando domina il target adattivo/il vincolo di lasciare un
lato GPU.

### Cosa limita oggi il tetto

Prima della patch il massimo configurato veniva clampato a
`min(8, worker_count)`. Quel limite non è strutturale: i worker prelevano job da
una coda atomica sotto mutex e uno stesso worker può consumare più expert in
sequenza. La patch rimuove solo quel clamp; non cambia il numero di worker.

I limiti effettivi sono ora:

- default/configurazione `DS4_G132_CPU_LANE_MAX` (default 3, hard max 8);
- massimo sei route nel modello e almeno una lasciata alla GPU, quindi al più
  cinque CPU;
- numero di route transienti con backing sicuro;
- capacità coda 8.

Con sei route totali, il massimo di sei worker persistenti è già sufficiente a
servire ogni route CPU ammissibile contemporaneamente; non è quindi il limite
strutturale del layer. Su macchine con meno worker la coda resta corretta ma i
job CPU diventano parzialmente sequenziali, e il bilanciatore li vede nel
wall-time.

## Lifetime e reservation

### Slot arena

Per RAM warm/probation la route prende
`cuda_dynamic_arena_slot_reader_acquire()`, ricontrolla slot, generation,
layer, expert e tripletta di puntatori, e trattiene il reader fino a riduzione
CPU completata (`ds4-p4a/ds4_cuda.cu:39692-39726`,
`:48987-48996`, `:49886-49898`).

### Staging SSD `route_host_*`

Per lo staging standard, allocato pinned con `cudaHostAlloc`, il piano prende
un lease CAS sulla `host_generation`. Il claim del mailbox successivo fallisce
chiuso se la generazione precedente ha ancora un reader CPU
(`ds4-p4a/ds4_cuda.cu:30927-30932`). Ogni worker ricontrolla generazione e
range dei tre plane prima di leggere (`:49025-49071`). Il lease viene rilasciato
solo dopo che tutti i worker hanno terminato, anche nei percorsi cancel/error.

Sono lasciati aperti, con fallback GPU e causa distinta, due casi in cui il
lifetime non è dimostrabile senza cambiare il proprietario del trasporto:

- `fallback_pipeline`: per una route SSD con demand pipeline attiva, perché la
  pipeline compatta le miss GPU verso gli slice bassi di `route_host_*` e può
  sovrascrivere lo slice trattenuto dalla CPU;
- `fallback_wrap`: quando il loader ha sostituito i puntatori con uno slot del
  ring SSD-wrap.

Le route arena restano ammissibili anche con demand pipeline. Le route nested
sono `fallback_contract` perché hanno un contratto di staging diverso. Non è
stato aggiunto un flag staging separato: il caso standard è protetto dal lease;
i due casi non risolti sono rifiutati automaticamente e misurati.

## Telemetria

Ogni layer completato emette `[g132-general-layer]` con:

- `route_cpu`, `route_gpu`;
- `bytes_non_attraversati`;
- `cpu_wall_ms`, `gpu_wall_ms`;
- `gpu_wait_cpu_ms`: intervallo fra fine GPU e fine CPU quando la CPU finisce
  dopo;
- `cpu_wait_gpu_ms`: intervallo opposto;
- `eligible`, `rejected_cap`, `rejected_balance`;
- `next_target_cpu`.

Alla release vengono emessi `[g132-general-summary]` totale e un
`[g132-general-layer-summary]` aggregato per ogni layer attivo
(`ds4-p4a/ds4_cuda.cu:49293-49343`).

I fallback totali sono separati:

- `fallback_contract`;
- `fallback_reservation`;
- `fallback_wrap`;
- `fallback_pipeline`;
- `fallback_runtime`.

`staging_routes` distingue quante route CPU provenivano da `route_host_*`.
La misura di attesa incrociata rende osservabile la serializzazione: un
`gpu_wait_cpu_ms` sistematicamente grande è il fallimento previsto dal mandato.

## Neutralità a flag spenti

Le uscite anticipate/neutralità sono costruite in quattro punti:

1. `cuda_g73_route_dispatch_init()` sceglie
   `routed_moe_launch_impl<..., false>` e
   `cuda_moe_route_worker<..., false>` se `GENERAL` non è 1
   (`ds4-p4a/ds4_cuda.cu:48666-48691`);
2. i rami del piano nel launch e nel worker sono racchiusi in
   `if constexpr (G132)`, quindi non esistono nel binario della
   specializzazione OFF;
3. il bit mailbox vale zero per tutti i chiamanti non generali e la condizione
   di ammissione è short-circuit;
4. i due buffer device di compattazione vengono allocati soltanto se
   `GENERAL=1` (`ds4-p4a/ds4_cuda.cu:49147-49207`).

Resta una scrittura aggiuntiva del bit `cpu_lane_allowed` nel piccolo payload
del resolver, ma nessun nuovo ramo caldo e nessun contatore cambia con i flag
spenti. Il dispatch mixed/Q1, l'ordine del weight mixed, le decisioni di
residenza e i contatori di trasporto restano quelli precedenti.

## Rischi e verifica non eseguita

- Per mandato non ho compilato e non ho avviato `ds4_server`.
- È stata eseguita soltanto verifica statica: `git diff --check` e
  `git apply --check --whitespace=error-all`.
- Il costo del worker scalar G132, la contesa DRAM/PCIe e la precisione finale
  devono essere misurati. Sono proprio le variabili che il bilanciatore deve
  apprendere.
- Le host callback CUDA sono volutamente brevi e non chiamano API CUDA; fanno
  solo timestamp e signal sotto mutex.
- Un errore runtime dopo che una route CPU è stata esclusa non può ripiegare
  nello stesso layer sulla GPU senza ricopiare e rilanciare l'intero layer:
  fallisce chiuso ed incrementa `fallback_runtime`. I rifiuti di ammissione,
  invece, ricadono normalmente sul trasporto GPU prima di escludere byte.

## SHA-256

File sorgente su cui è stato prodotto il diff:

```text
A40FFEE8CEBECB1F57AD98F229CE9F7AD8D3248FEE103A20F4922022B38ACC95  ds4-p4a/ds4_cuda.cu
```

Risultato atteso dopo applicazione:

```text
83B85C51358B9E0EC6D31B29914513D23099E146DC49FD87B6725D0BCE578948  ds4-p4a/ds4_cuda.cu
422718E44D4A2BBA4F244A2489248008A66045F064D34DC318512ECA7980B32E  .microbench/lane/lane.patch
```

Nota di audit finale: dopo la generazione e il primo `git apply --check`
riuscito, il file sorgente condiviso è cambiato alle 15:15:51 UTC e contiene
già tutti gli hunk della lane. `git apply --reverse --check lane.patch` riesce,
quindi non si tratta di divergenza degli hunk ma di patch già applicata da un
altro attore/processo del workspace; non ho modificato né ripristinato quel
file. Il suo SHA-256 osservato a fine lavoro è:

```text
7CC4377593E054D9BD4FFB97A4091F351FE9FAD3FB8C6B89276D0A1534D0029D  ds4-p4a/ds4_cuda.cu (lane già presente)
```

Di conseguenza un secondo `git apply` sullo stato finale rifiuta correttamente
il duplicato; il patch resta applicabile alla preimage dichiarata
`A40F...ACC95`.
