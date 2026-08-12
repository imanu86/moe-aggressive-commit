# Economia della lane G132: dove muore il guadagno, e la correzione

## Verdetto in cinque righe

I ~47-50 ms/token di perdita NON sono il calcolo CPU e NON sono un costo fisso
di quantizzazione/sveglia: sono il **join sincrono**. `wait_and_join` blocca il
thread chiamante per `gpu_wall + gpu_wait_cpu + code` ≈ 1,15 ms per layer
ingaggiato — e 1,15 × 43 ≈ 49 ms/token, entro il rumore dell'intera perdita
misurata (47 PRE, 50 POST). Il pedaggio evitato, nel config di stanotte, è ≈ 0
perché la route tolta non stava sul percorso seriale. `econ.patch` rende il
join **asincrono** (il chiamante accoda e riparte), sposta la riduzione nel
worker, misura ogni voce della scomposizione e sostituisce il criterio del
bilanciatore. A parità di tutto il resto il costo marginale di una route CPU
scende da ~1,15 ms a ~0,03 ms di accodamento.

## Perimetro

- Letti: `.microbench/lane/ANALISI.md`, `.microbench/lane_fable/NOTA.md`,
  `.microbench/lane_kernel/NOTA.md`, ledger (`reap-loop-ledger-main/docs/
  EXPERIMENTS_LEDGER.md:17889-18011`), sorgente `ds4-p4a/ds4_cuda.cu` (tree
  corrente, SHA `C110C560...386F`).
- Scritto solo in `.microbench/lane_econ/`. Nessuna compilazione, nessun
  server, nessun accesso a `D:\`. Fix Fable e kernel row-parallel intatti.
- Tutte le righe citate sono del **preimage corrente** (`C110C560...`).

---

## 1. LA SCOMPOSIZIONE DEL COSTO PER LAYER (punto 1 del mandato)

### 1a. Dentro `cpu_wall` il costo fisso è ~0,02 ms, non domina

`cpu_wall` è misurato dal callback input-pronto alla fine degli expert
(`ds4_cuda.cu:49348-49357` per l'inizio, `:49341` per la fine). Contiene:

```
cpu_wall = sveglia_worker + quantizzazione_Q8K_input + n × expert + firma
  1,10   =            ~0,02 (misurato per differenza)  + 1 × 1,08
```

Con `expert_ms = 1,08` misurato e `cpu_wall = 1,10` a 1 route, la parte fissa
interna (sveglia + quantizzazione dell'input, una volta per dispatch a
`:49322`) è **~0,02 ms**: irrilevante. L'ipotesi del mandato ("se il costo
fisso domina, la lane conviene solo con più route") è giusta nello spirito ma
il costo fisso dominante NON sta dentro `cpu_wall`.

### 1b. Il costo fisso vero è il blocco del chiamante nel join

`cuda_g132_cpu_lane_wait_and_join` (`:50073`) blocca il thread di decode su
`completed_jobs == job_count && gpu_done` (`:50079-50083`). `gpu_done` è un
host-callback accodato su stream 0 DOPO i kernel miss (`:49999-50009`,
accodato a `:48351`/`:48803`): quindi il chiamante non aspetta solo la CPU,
aspetta che la GPU **esegua** lo stadio MoE che senza lane avrebbe soltanto
accodato. Poi, ancora sul chiamante: riduzione host del parziale
(`:50094-50105`), H2D 16 KiB + add (`:50209-50227`).

Timeline del ramo split (quello di stanotte, `SPLIT_FUSED=1`):

```
finish() :48074 ──> attach lane :48157-48193 ──> kernel miss :48265-48314
                        │ (D2H input ~0,05)          (GPU ~0,2 ms)
                        └─> CPU parte, calcola 1,10 ────────────┐
chiamante BLOCCATO in wait_and_join da :48355 ──────────────────┴─> +1,15 ms
```

Ricostruzione con i numeri di stanotte: blocco ≈ gpu_wall (0,21) +
gpu_wait_cpu (0,89) + sveglia/riduzione/accodature (~0,05) ≈ **1,15 ms** per
layer ingaggiato. Misurato end-to-end: PRE 220→267 = **+1,09 ms/layer**, POST
295→345 = **+1,16 ms/layer** (assumendo ~43 layer ingaggiati/token; i
`general_layer_calls` del log lo verificano). Il conto torna senza residuo:
**il blocco È l'intera perdita, e il pedaggio evitato è ≈ 0** (§2).

### 1c. Perché il bilanciatore a 1 non era un errore di misura

Col join sincrono `cpu_wall` cresce linearmente con n (`= 0,02 + n × 1,08`,
expert in sequenza, `.microbench/lane_kernel/NOTA.md`) e il blocco cresce con
lui. Quindi OGNI n perde e n=1 perde meno: il bilanciatore (`:50171-50202`,
pavimento `target > 1u` a `:50194`) stava minimizzando correttamente una
perdita strutturale. Non serviva "misurare meglio": serviva togliere il blocco.
Dopo di che il confronto cpu_wall/gpu_wall misura la grandezza sbagliata
(nessuno aspetta più quei wall) — da qui il criterio nuovo (§4).

### 1d. Strumentazione consegnata (ogni voce ora misurabile)

`econ.patch` scompone e stampa per layer in `[g132-general-layer]`:

| voce | cosa misura | dove |
|---|---|---|
| `wake_ms` | input-pronto → dequeue del worker | worker `:49317+` (patch) |
| `quant_ms` | Q8_K dell'input (una volta/dispatch) | idem |
| `reduce_ms` | riduzione parziale (ora nel worker) | idem |
| `enqueue_ms` | costo caller della catena di join asincrona | `enqueue_join_general` |
| `worker_window_ms` | plan_begin → prepare: finestra di staffetta sovrapponibile | plan_begin `:39731` + prepare |
| `prepare_wait_ms` | attesa indotta dalla coda del dispatch precedente | prepare (patch) |
| `join=async` | marca del percorso nuovo | emitter |

più i totali nel `[g132-general-summary]` (`join_async`, `prepare_waits`,
`prepare_wait_ms`, `stats_dropped`, ecc.) e `prepare_wait_charged_ms` per
layer nel layer-summary. Il lato GPU/trasporto è GIÀ scomposto dal
WORKER-PROF esistente (`:4328-4419`: `WP_READ_*`, `WP_COPY_NS`,
`WP_DELIVER_NS`, `WP_DRAIN_NS`, `WP_PUBLISH_NS`): per attribuire il pedaggio
evitato basta un run con `DS4_CUDA_WORKER_PROFILE=1`, lane on/off.

---

## 2. IL PEDAGGIO EVITATO: la lettura del mandato è mezza giusta (verifica richiesta)

Il mandato dice: "quella route sulla strada GPU costava ~0,7 ms (staging ~0,6 +
quota H2D + quota drain)". Due correzioni dal codice:

1. **Lo staging SSD non è MAI evitato dalla lane.** L'ammissione avviene nel
   worker quando il puntatore host esiste già (`cuda_g132_general_plan_admit`
   chiamata a `:40719-40736`, dopo che `host_gate/up/down` sono validi): per
   una route staging la lettura SSD è già stata fatta (e la lane la CONSUMA:
   il forward legge `route_host_*`, contratto verificato a `:49234-49263`).
   Il `continue` a `:40735` salta solo H2D + wrap-record + publish
   (`:40757-40859`). Lo 0,6 di staging si paga su ENTRAMBE le strade.
2. **Con demand pipeline attiva le route staging non sono nemmeno
   ammissibili** (`:39774-39779`, `fallback_pipeline`): restano solo le route
   ARENA (RAM-warm). Per quelle il pedaggio evitabile è: accodatura H2D (µs,
   è la sola enqueue — commento a `:40617-40624`), publish (µs) e la quota di
   **drain** dei 7.077.888 byte. Ma l'H2D corre sull'upload stream in
   sovrapposizione al resto della fase worker: se il drain non è il termine
   vincolante in quella finestra, togliere una route non accorcia niente.

I numeri di stanotte dicono esattamente questo: perdita ≈ blocco intero ⇒
**pedaggio evitato ≈ 0,0-0,05 ms/route nel config misurato**. Il contatore
`staging_routes` nel summary (già esistente) e `WP_DRAIN_NS` discriminano al
prossimo run quale dei due meccanismi (esclusione pipeline vs drain
sovrapposto) pesa quanto.

**Dove la lane PUÒ comprare staffetta vera** (non implementato qui, misurabile
dopo la patch): i layer in cui la CPU prende TUTTE le miss ammissibili — lì
crolla l'intero passo di trasporto del layer (publish + drain + interlock),
non una quota. Il vincolo `cpu_count < route_count` (`:49864-49865`) conta
anche le hit, quindi "tutte le miss alla CPU" è già ammesso oggi quando le
miss sono ≤ target e RAM-warm. Con il criterio nuovo del bilanciatore il
target sale finché non induce attese: su quei layer ci arriva da solo.

---

## 3. QUANTIZZAZIONE RIPETUTA (punto 2): esiste, ma vale ~0,02 ms — non riusarla

- Il percorso GPU quantizza lo stesso input x in Q8_K **sul device** a
  `:47382` (`q8_K_quantize_kernel`, prima dei kernel hit/miss).
- La lane lo ri-quantizza host-side UNA volta per dispatch (`:49322`), non
  per route. Costo misurato per differenza: `cpu_wall − n×expert_ms` ≈
  0,02 ms (ora misurato esattamente da `quant_ms`).
- Riusare il risultato device (D2H di ~4,7 KB di blocchi Q8_K invece dei
  16 KiB F32) farebbe risparmiare ≤ 20 µs ma **aggancerebbe la partenza CPU
  all'esecuzione di un kernel su stream 0** (oggi la copia parte dall'evento
  input, prima di qualunque kernel dello stadio): peggiora l'overlap per
  guadagnare rumore. La quantizzazione del mid dentro `matvec_q2_k_expert` è
  per-route ma è inerente (il mid è diverso per expert) ed è già dentro
  l'`expert_ms` = 1,08 ≈ bench 0,97.

**Risposta: nessun riuso. La voce è ora strumentata (`quant_ms`); se un run la
mostrasse > 0,1 ms si riapre il discorso con i numeri.**

---

## 4. SOVRAPPOSIZIONE VERA (punto 3) e CRITERIO DEL BILANCIATORE (punto 4)

### 4a. Cosa compra la patch subito

Col join asincrono `gpu_wait_cpu` smette di essere un costo del chiamante: la
coda CPU (0,89 ms oggi) si nasconde sotto la staffetta del layer successivo
(~5-6 ms). L'unico costo residuo possibile è la collisione della coda con il
`prepare` del layer dopo — misurata da `prepare_wait_ms` e usata dal
bilanciatore. A target 3 (default) la coda è ~3,3 ms contro una staffetta di
~5-6: attese attese ≈ 0.

### 4b. La partenza anticipata (non in questa patch, dimensionata da essa)

Oggi la CPU parte all'attach post-`finish()` (split `:48174`, non-split
`:47256`): si sovrappone SOLO ai kernel miss (~0,2 ms di GPU). La forma
giusta è: D2H input + sveglia all'INGRESSO del launch (x è pronto lì) e push
dei job **al momento dell'ammissione** (`:40719`), route per route, mentre il
worker continua con staging/drain delle altre. Richiede di spezzare
`begin_general` in `begin_input`/`begin_jobs` e un epoch dell'input (il
callback a `:49348-49357` oggi scarta l'input se `!job_active`). Non la
consegno nella stessa patch del join: è un secondo cambio di stretta di mano
su un percorso misurato funzionante 5 ore fa. La misura che decide se serve
è già nella patch: se dopo il join asincrono `prepare_wait_ms` resta > 0 ai
target alti, `worker_window_ms` (plan_begin→prepare, cioè quanta staffetta la
CPU avrebbe potuto sovrapporre) dice esattamente quanto si recupera
anticipando la partenza.

### 4c. Route "pesanti" alla CPU

Sotto demand pipeline tutte le route ammissibili sono arena-backed: pedaggio
evitato identico (7.077.888 byte di H2D ciascuna) ⇒ nessuna preferenza da
implementare. Senza pipeline, le route staging pagano comunque l'SSD su
entrambe le strade (§2.1) ⇒ ancora nessuna preferenza. Il punto 3b si chiude
così: **non esistono route più pesanti dal punto di vista del pedaggio
evitabile**, finché il trasporto resta l'unico termine.

### 4d. Il criterio nuovo (nella patch)

Vecchio: pareggio dei wall (`cpu_wall` vs `gpu_wall`, `:50171-50202`) —
minimizza la cosa sbagliata e non può dire "questa route ha tolto staffetta".
Nuovo (in `prepare_general`, un campione per dispatch, stessa isteresi
0,15 ms, stessa maccanica streak-3/cooldown-4, stessi limiti [1, MAX]):

```
guadagno  = quota di trasporto tolta dalla staffetta   (cresce con n, ≥ 0)
costo     = serializzazione indotta = prepare_wait_ms  (unico costo reale residuo)
regola    : prepare_wait ≈ 0  →  +1 route (fino a MAX)
            prepare_wait > isteresi → −1 route (charged al layer che l'ha causata)
```

Massimizza il numero di route dirottate (= byte tolti al bus, = candidati
layer all-miss §2) sotto il vincolo di zero attesa indotta, che è esattamente
"massimizzare la staffetta tolta" quando il costo marginale è ~0. Se i byte
tolti non valgono niente (drain non vincolante), il criterio satura a MAX
senza fare danni — e il confronto end-to-end lo dichiara.

---

## 5. COSA FA econ.patch (tutto in `ds4-p4a/ds4_cuda.cu`, +458/−13)

1. **Join asincrono per il percorso GENERAL** (i due call-site `:48355` e
   `:48807` passano a `cuda_g132_cpu_lane_enqueue_join_general`):
   il chiamante accoda su `bridge_stream`
   `[gate hostfunc] → [H2D parziale] → [event] → [idle hostfunc]`
   e su stream 0 `[waitEvent] → [add]`, poi RITORNA. Il gate hostfunc aspetta
   i worker (dipendenza solo da thread OS: nessun ciclo con CUDA), rilascia
   reader arena + lease staging, emette la telemetria; l'idle hostfunc rende
   riusabile il dispatch solo DOPO che il parziale è sul device. La riduzione
   del parziale passa dal chiamante al worker-orchestratore.
2. **Percorso mixed intoccato**: `wait_and_join` resta e resta sincrono per
   il chiamante mixed (`:51471`); i suoi rami general diventano morti.
3. **Bilanciatore v2** come da §4d, con `prepare_wait` addebitata al layer
   causante (`general_layer_prepare_wait_seconds`).
4. **Strumentazione** §1d.
5. **Fail-closed nuovo**: se un job CPU fallisce DOPO l'accodatura della
   catena (evento non raggiungibile con reservation/lease trattenuti e
   contratto validato in admit+prepare: è difensivo), il worker ha già
   azzerato il parziale (l'add somma zero esatto), il gate latch-a
   `async_fault`, stampa una riga forte e la lane si spegne fail-closed dal
   layer successivo (`plan_begin` e `prepare` rifiutano). Prima falliva
   l'intera richiesta nello stesso layer: il delta di semantica è dichiarato
   qui ed è confinato a un percorso mai osservato nei run.
6. **Coordinazione cancel/join**: revoca idempotente (`join_enqueued`),
   broadcast al posto di signal (ora i waiter possono essere gate callback,
   cancel e prepare insieme), spegnimento pulito nel release (nessun hang su
   `cudaStreamDestroy`).

### Neutralità a flag spenti (il punto dove sono morte due patch)

- Il template `<G73,G132>` e il dispatch (`:48666-48691`) NON sono toccati:
  a `DS4_G132_CPU_LANE_GENERAL≠1` le specializzazioni `<*,false>` non
  contengono nulla di tutto questo nel percorso compilato (stessa forma di
  lane.patch, L0 passata "in pieno" il 28/7).
- Nessuna struttura condivisa cambia layout: il timestamp del piano sta nel
  singleton della lane, NON in `cuda_moe_expert_cache` (lezione
  dell'autopsia drain: il layout spostato fu contestato come non-neutralità).
- Nessun getenv nuovo, nessun ramo nuovo su percorsi caldi non-lane, nessun
  contatore preesistente cambia significato a flag spenti. I simboli nuovi
  esistono nel binario come già il kernel di compaction/ownership: mai
  eseguiti a flag spenti.
- A lane accesa ma percorso mixed: uniche differenze = broadcast vs signal
  (semantica identica con un waiter) e campi telemetrici scritti dal worker.

### Limiti dichiarati

- Se stream 0 è > 100 ms indietro, la telemetria GPU di un dispatch può
  essere scartata o sporcata (contata in `stats_dropped`; nessun effetto
  funzionale: la catena di join non dipende da `gpu_done`).
- `prepare` ha un'attesa limite di 100 ms sulla coda del dispatch precedente,
  poi fallisce chiuso come oggi (contesto già morto in quel caso).
- La finestra `worker_window_ms` può essere rumorosa su percorsi che fanno
  begin/finish senza consumare il piano (helper `:46550`): è telemetria, non
  stato.

---

## 6. PREVISIONE FALSIFICABILE E PROTOCOLLO

Protocollo invariato di stanotte (2.250 tok, ctx 150k, HOT_RESERVE_MB=256,
guardiano recoverable, PRE/POST):

1. **L0 neutralità** (flag spenti): sha del testo identico all'ancora,
   contatori identici. Se fallisce, la patch è morta lì come le altre due.
2. **L2e (lane MAX=3, default)**: attese `prepare_waits ≈ 0`, target che
   salgono verso 3, `gpu_wait_cpu` ancora ~0,9 ma **irrilevante** (nessun
   blocco), `enqueue_ms ≤ 0,05`. Bersagli:
   - PRE ≈ 220 ± 3% e POST ≈ 295 ± 3% ⇒ **pareggio**: il blocco era tutto,
     il pedaggio evitato è zero anche a 3 route ⇒ la lane su questa
     architettura non compra velocità col trasporto; resta solo capacità
     (il backend CPU che manca al pin del backbone, ledger `:17872`) e la
     strada all-miss/partenza anticipata SE `worker_window_ms` e
     `WP_DRAIN_NS` la giustificano. Filone velocità: da chiudere con questi
     numeri.
   - POST < 290 con `bytes_non_attraversati` × route in crescita ⇒ la quota
     drain esiste: spingere MAX e valutare la partenza anticipata.
   - POST > 305 o `prepare_waits` sistematici ⇒ il join asincrono non ha
     mantenuto la promessa: tornare qui coi numeri, non insistere.

Nota di metodo (regola fail-fast): se L2e degenera al primo run, STOP, niente
2/3.

## SHA-256

Preimage (tree corrente al momento della produzione, identico a inizio e fine
lavoro):

```text
C110C5603A417D7DA9CF4A75F1F5168D170FFF1E26827746A252C4E17D52386F  ds4-p4a/ds4_cuda.cu
```

Artefatto:

```text
6979BE2FED106AEBE4ECFFE90536B10CB54A3D0BF6E7729723194E03279F6B44  .microbench/lane_econ/econ.patch
```

Postimage atteso dopo `git apply .microbench/lane_econ/econ.patch`:

```text
CDCC406F4125BB6491D6FE02026A3ADE60B4D55A946FE86D81817B6C6070EA30  ds4-p4a/ds4_cuda.cu
```

Verifiche eseguite: `git apply --check --whitespace=error-all` OK sul tree
corrente; `--numstat` = 458/13 su un solo file; postimage riprodotto
bit-identico applicando la patch a una copia del preimage. Nessuna
compilazione (vietata dal mandato): la revisione è statica; primo passo
obbligato del prossimo braccio è la build + L0.
