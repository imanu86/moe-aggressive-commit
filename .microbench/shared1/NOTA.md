# SHARED-1 — shared expert su CPU (`DS4_CPU_SHARED_EXPERT=1`)

Data: 2026-07-29. Mandato: `scratchpad/mandato_shared.txt` (traccia 6 di
`.microbench/pilot/ANALISI_FABLE.md`). Nessuna compilazione, nessun server,
`D:\` non toccato. Scritto solo in `.microbench/shared1/`.

Patch: `shared1.patch` — 4 file, **+939/−4** (`git apply --numstat`:
`754/4 ds4.c`, `131/0 ds4_cuda.cu`, `16/0 ds4_gpu.h`, `38/0 ds4_metal.m`).

## 0. Base del diff e stato del tree (leggere prima di applicare)

Durante questo lavoro il cantiere parallelo ha COMPOSTO `dspark1.patch` nel
tree (ds4.c 21761→22509 righe, ore 07:55), salvando le pre-immagini in
`.microbench/ds4_c.pre_dspark1.c` / `ds4_cuda.pre_dspark1.cu`. Questo diff e'
prodotto sulla **baseline pre-dspark1** (= tree di campagna con
lane+kernel+econ+SCOPED+DOV composti, come da mandato) e verificato su
ENTRAMBI gli stati:

- `git apply --check` su copia della baseline pre-dspark1: **PASS**, e il
  risultato e' **byte-identico** ai file attesi (roundtrip, SHA in fondo);
- `git apply --check` sul **tree corrente** (dspark1 gia' composto): **PASS**
  — le ancore di dspark1 (baseline ds4.c 2336 / 6639 / 8991) e le mie non si
  toccano, come previsto dalla loro NOTA (sez. coordinate).

Le righe citate sotto come «base :N» sono della baseline pre-dspark1; nel
tree corrente valgono gli slittamenti dichiarati da dspark1 (+68 dopo il loro
hunk 1, +401 dopo il 2, +748 dopo il 3; ds4_cuda.cu +24 a 36164, +1 a 41743).

## 1. Cosa fa la patch (percorso dati)

A flag acceso, per ogni layer del decode:

```
ffn_norm (GPU, 16 KiB)
   └─ D2H ordinato su stream 0 (ring pinnato 4 slot)     [schedule, base :11978]
        └─ worker CPU dedicato: quantizza Q8_0 → pair gate/up → SwiGLU →
           down (row-parallel sul pool g132; pesi dal mmap del modello)
             └─ join al punto di somma NON fuso [base :12252]:
                attesa del worker SOLO qui → H2D asincrono 16 KiB in
                g->shared_out → kernel esistente
                ds4_gpu_hc_expand_add_split_tensor [base :12275-12282]
                (o ds4_gpu_add_tensor con keep_ffn_out [base :12256-12258])
```

I kernel GPU dello shared (gate/up/SwiGLU fusi o separati, down, join fuso
`shared_down_hc_expand`) vengono saltati; `routed_moe_prepare_selected` resta
invariato (il prepare del trasporto routed parte come oggi). Su QUALUNQUE
fallimento (slot esauriti, D2H non accodabile, eval CPU fallita, H2D non
accodabile) il join ricalcola lo shared su GPU **identico al percorso odierno
non-overlap non-fuso** — mai silenzioso: contatore esatto + log (primi 8
eventi, poi 1 ogni 256, per non trasformare un guasto sistemico in tempesta).

Il forward CPU riusa la matematica di `layer_shared_ffn_one` (base
:6086-6118) come chiesto dal mandato: stessi kernel di riga
(`matvec_q8_0_pair_worker`, `matvec_q8_0_worker`, `quantize_q8_0_activation`,
`swiglu`), reincapsulati row-parallel sul **pool g132** (base :827-958, fermo
in decode) come fu fatto per il kernel della lane — non sul pool del backend
CPU, che non sopporta submitter concorrenti (commento in base :826-833).

## 2. VERIFICA T0.4 — i range shexp sono rilasciabili singolarmente? (il punto critico)

Risposta articolata in TRE meccanismi, tutti verificati sul sorgente; la
patch agisce di conseguenza su ciascuno:

1. **Pre-cache di avvio: NO, non sono rilasciabili.**
   `accelerator_cache_model_tensor_spans` (base ds4.c :1862-1942) fonde tutti
   i tensori non-routed in span contigui `tensor-span:N` fino a 1 GiB (merge
   con gap ≤64 KiB): gli shexp finiscono FUSI negli span insieme ad
   attention/norm/router. Rilasciare "il range shexp" li' e' impossibile
   senza buttare pesi backbone vivi. ⇒ la patch li **esclude alla fonte**
   dal walker (stesso meccanismo gia' usato per i routed expert,
   :1876-1879), con log dei byte esclusi. L'esclusione spezza lo span in
   quel punto da sola (il buco shexp e' ≥8,5 MiB ≫ 64 KiB di merge window).
2. **Staging on-demand a runtime: SI', sono gia' individuali, ma PINNATI.**
   Il percorso fd-cache (`cuda_model_range_ptr_from_fd`, base cu :8426-8538)
   alloca un range per-peso con l'offset esatto del tensore (le etichette
   `q8_0`/`q8_0_pair0`/`q8_0_pair1`; gli «alloc failed … 8.50 MiB» dei log
   L2/L3 citati dalla fattibilita' sono esattamente questo). Pero'
   `pinned = is_hot` (base cu :8436, :8515-8517: tutto cio' che non inizia
   per `moe_` e' pinnato) ⇒ la LRU li sfratta solo come ultima risorsa
   (pass 2 di `cuda_model_pick_victim`, :8236-8265): senza rilascio
   esplicito, i range shexp staggiati dal PREFILL resterebbero in VRAM per
   tutto il decode. ⇒ implementato il **rilascio per-range SOLO per shexp**
   previsto dal mandato: `ds4_gpu_model_span_release` sfratta nel pool di
   riciclo (free posticipato con fence-evento su stream 0 =
   `cuda_model_range_evict_to_pool`, la stessa sicurezza dello sfratto LRU)
   ogni range streamed interamente contenuto nello span del tensore.
3. **Cache dequant f16/f32: il buco che la fattibilita' non aveva visto.**
   Le forme shexp passano la shape-rule della cache f16 anche con etichetta
   generica (`cuda_q8_f16_cache_allowed`, base cu :4206-4207: `4096x2048` e
   `2048x4096`): al prefill (`n_tok>1` + cublas) ogni matrice shexp verrebbe
   dequantizzata in un'entry VRAM PERMANENTE (16,8 MiB f16 l'una, mai
   evicted). Con `DS4_CUDA_NO_Q8_F16_CACHE=1` (config sicura di campagna,
   memoria bit-exact) il problema non esiste; la patch lo chiude comunque
   con un registro «CPU-owned» scritto una volta all'avvio: `cuda_q8_f16_ptr`
   e `cuda_q8_f32_ptr` rifiutano gli span registrati e ricadono sui kernel
   Q8 batch esistenti (fallback gia' NULL-tolerante per costruzione).

**Regimi senza beneficio di capacita' (dichiarati, non nascosti):** window
zero-copy (`g_model_window_bytes`, base cu :3889-3892 — shexp su RAM pinnata,
zero VRAM) e copia-intera (`DS4_CUDA_COPY_MODEL`/device-owned) non hanno
range da liberare: le spazzate riportano `released=0`, il summary lo rende
visibile (`vram_freed_mb=0`) e resta il solo offload di calcolo. In quei
regimi il guadagno cambia natura: nel window-mode lo shared su CPU evita
26,7 MB/layer di letture PCIe per token.

**Aritmetica del beneficio (regime campagna, staging/esclusione):**
3×8.912.896 B ×43 layer = 1.149.763.584 B = **1096,5 MiB ≈ 162 slot IQ2**
mai caricati (esclusione all'avvio) + rilascio dei re-staging da
prefill/verify. La cache esperti NON viene ridimensionata: `CACHE_N` resta
dell'operatore, la VRAM liberata e' headroom (mandato, punto 3).

### Ciclo di vita della residenza a flag acceso

- avvio: esclusione dal pre-cache (+ marcatura CPU-owned prima di qualunque
  preload) → gli shexp non entrano mai in VRAM;
- prefill/verify batch: lo staging Q8 grezzo e' PERMESSO (il batch GPU ne ha
  bisogno: `metal_graph_encode_layer_ffn_batch`, base :15095-15126) e marca
  `vram_dirty`;
- primo layer del token di decode successivo: spazzata
  `ds4_gpu_model_span_release` sui 129 span (solo thread di decode, lo
  stesso che gia' muta `g_model_ranges` → nessuna concorrenza nuova sul
  registro) → i range tornano al pool di riciclo;
- fallback GPU del join: marca anch'esso `vram_dirty` (stessa pulizia).

Nota MTP: con lo speculativo attivo il verify batch ri-staggerebbe gli shexp
a ogni passata e la spazzata li rilascerebbe a ogni token — un ping-pong
visibile nei contatori (`vram_sweeps`), non un errore. La combinazione
shared1+MTP va misurata prima di usarla; nel regime di campagna l'MTP e'
spento.

## 3. Cosa tocca la patch (mappa degli hunk, per il remap di dspark1)

Hunk «freddi» (blocchi contigui autosufficienti, fuori dai punti caldi):

| pezzo | file, posizione (base) |
|---|---|
| helper env + globale byte esclusi (sempre compilati, `DS4_MAYBE_UNUSED`) | ds4.c prima di :1801 |
| predicato `accelerator_tensor_is_base_shared_expert` (prefisso `blk.` ⇒ mai `mtp.0.*`) | ds4.c dopo :1845 |
| esclusione dal walker span + log | ds4.c :1865-1868, :1879+, :1936+ (3 micro-hunk) |
| marcatura CPU-owned all'avvio | ds4.c in `accelerator_cache_model_tensors`, dopo :1949 |
| forward typedef + campo `g->shared1` | ds4.c :9435+, :9548+ |
| **modulo shared1** (struct, worker, create/destroy, schedule, join, spazzate, telemetria — 673 righe) | ds4.c prima di :10029 |
| init/teardown | ds4.c :11081+ (`metal_graph_shared1_init`), :10501+ (release in `metal_graph_free`) |
| registro CPU-owned + export | ds4_cuda.cu dopo :1989 |
| `ds4_gpu_model_span_release` | ds4_cuda.cu dopo :8366 (prima di `cuda_model_stream_alloc`) |
| `ds4_gpu_tensor_write_async_ordered_slot` (gemello in scrittura del read ordinato) | ds4_cuda.cu dopo :16331 |
| 2 dichiarazioni | ds4_gpu.h :156+, :255+ |
| 3 stub di link per il backend Metal | ds4_metal.m append in coda |

Hunk sui **punti caldi condivisi** (piccoli e isolati, da rimappare a mano se
dspark1 tocca le stesse righe in futuro — oggi NON le tocca):

| dove (base) | modifica |
|---|---|
| ds4.c :11978+ | +1 riga: `metal_graph_shared1_schedule(g, layer, il)` accanto allo schedule SPEX |
| ds4.c :12024+ | +5 righe: `const bool shared_cpu = …` (identita' tensori per-layer) |
| ds4.c :12031 | `if (ok && overlap_shared)` → `&& !shared_cpu` (1 riga) |
| ds4.c :12202 | `if (ok && !overlap_shared)` → `&& !shared_cpu` (1 riga) |
| ds4.c :12230 | `fuse_shared_down_hc` → `&& !shared_cpu` (1 riga) |
| ds4.c :12246 | ramo down non-fuso → `&& !shared_cpu` (1 riga) |
| ds4.c :12251+ | +4 righe: chiamata `metal_graph_shared1_join_or_gpu(...)` prima del marker `shared_down` |
| ds4.c :15126+ | +3 righe: `metal_graph_shared1_note_gpu_use(g)` dopo lo shared batch |
| ds4_cuda.cu :4260, :4315 | +1 riga ciascuno: guardia CPU-owned nelle cache dequant f16/f32 |

## 4. Neutralita' a flag spento

- `g->shared1` resta NULL (sessione `xcalloc`, create ritorna NULL senza
  side-effect se l'env manca): `shared_cpu` e' un confronto puntatore-nullo
  per layer, e `metal_graph_shared1_schedule` rientra subito su `!s` —
  identica classe di costo del probe SPEX gia' chiamato incondizionatamente
  alla riga sopra (base :11978). Nessuna getenv nel percorso caldo (l'env e'
  letto a startup-cache e a graph-create).
- Le condizioni dei rami esistenti diventano `X && !shared_cpu` con
  `shared_cpu=false` ⇒ decisioni bit-identiche a oggi.
- Lato CUDA: registro vuoto ⇒ `cuda_shared1_span_cpu_owned` rientra sul
  check `empty()` (e viene chiamato solo nei percorsi di POPOLAZIONE delle
  cache dequant, gia' freddi); `span_release`/`write_async` non vengono mai
  chiamati; nessuna chiamata CUDA aggiunta su percorsi OFF; nessuna struct
  condivisa modificata (il campo nuovo del grafo e' in coda al blocco SPEX).
- Residuo OFF dichiarato: la `.bss`/le dimensioni di struct del grafo
  cambiano come per qualunque ricompilazione (classe di perturbazione gia'
  accettata dal protocollo con il run di controllo a flag spenti).

## 5. Composizione con le patch nel tree e col cantiere dspark1

- **Fix Fable split / kernel row-parallel / join asincrono lane / SCOPED /
  DOV (drain4): zero righe toccate.** Il join shared1 sta a valle del launch
  routed: l'H2D del parziale e' un normale op su stream 0 accodato DOPO il
  ritorno del launch (quindi dopo le fence DOV del ramo split e dopo il
  join-add della lane, che sono accodati dentro il launch) e PRIMA del
  kernel di somma — ordine di stream, nessun nuovo attore su slot/registri
  route. `ds4_gpu_moe_route_consumer_done` (base :12292) resta l'ultimo
  consumer del layer, dopo il mio join.
- **Pool g132**: la lane ha la precedenza per contratto — se
  `DS4_G132_CPU_LANE`/`_GENERAL` sono nell'ambiente, shared1 degrada a
  single-thread nel proprio worker (log esplicito). Un mutex di processo
  (`g_shared1_pool_mutex`) serializza le submit di shared1 (caso multi-grafo
  nello stesso processo). Nota per il futuro aggancio dei pezzi 3-5 di
  dspark1: il loro kernel Q4_K usa `ds4_parallel_for` (pool del backend CPU,
  non il g132) — oggi nessun conflitto; se migrassero sul g132 da un thread
  proprio, coordinarsi con questo mutex.
- **dspark1 pezzo 2** chiama `layer_shared_ffn_one_decode_scratch`: questa
  patch NON ne cambia la firma (non tocca :6086-6142), quindi il punto di
  attenzione segnalato nella loro NOTA non scatta.
- **Q1/IQ1**: nessun sito `q1_0`/`iq1_s` toccato. Sui layer con sidecar
  mixed il percorso shared e' lo stesso ramo non-fuso di oggi: il join CPU
  si comporta identicamente (i rami routed non c'entrano con lo shared).
- **REAP/bake**: lo shared viene sempre dal modello primario
  (`layer->ffn_*_shexp`); il check di identita' dei tensori esclude per
  costruzione qualunque chiamante con pesi diversi (es. il blocco MTP, che
  ha `mtp.0.ffn_*_shexp` e resta al 100% sul suo percorso GPU).

## 6. Scelte dove il mandato lasciava liberta' (dichiarate)

1. **Ponte D2H = gemello del ring SPEX, non la lane CUDA.** Il mandato dice
   «stesso ponte D2H della lane»; la lane porta a terra lo stesso identico
   vettore (`ffn_norm`, 16.384 B) ma la sua idraulica vive nel route worker
   CUDA del percorso enforce — un cammino dichiarato PERDITA STRUTTURALE per
   il calcolo generale (LEDGER:18104-18116) e pieno di stato condiviso che il
   mandato stesso chiede di non toccare. Ho usato il ponte omologo lato
   ds4.c gia' esistente e provato (ring pinnato + `read_async_ordered_slot`,
   lo stesso del probe SPEX, base :9969-9978): stessi byte, stesso
   ordinamento su stream 0, zero righe nuove nelle strutture della lane.
2. **H2D del parziale: export nuovo invece di `ds4_gpu_tensor_write`.**
   La write esistente e' una `cudaMemcpy` sincrona (base cu :9015-9023): al
   punto di join avrebbe bloccato l'host fino al COMPLETAMENTO di tutti i
   kernel gia' accodati (drain per layer — la classe di stallo che drain4 e'
   appena servito a togliere). Il gemello `write_async_ordered_slot` accoda
   su stream 0 da memoria pinnata e prova il riuso dello slot con l'evento
   done, speculare alla read ordinata.
3. **Attesa al join = condvar host.** «Il join deve tollerare l'arrivo
   tardivo senza bloccare la GPU»: la GPU non viene mai messa in attesa —
   i kernel gia' accodati (attention, router, routed) continuano a girare;
   ad attendere e' il thread di ENQUEUE, solo al punto di somma, e
   l'attesa e' misurata (`shared_wait_ms`). Niente timeout: il worker ha
   lavoro bounded (~1-3 ms) e ogni suo errore termina in DONE_FAIL →
   fallback; un hang del device emergerebbe comunque prima nei watchdog
   esistenti del percorso route.
4. **Fallback GPU dentro una funzione propria** (`shared1_join_or_gpu`)
   che replica le 4 chiamate del percorso odierno invece di ristrutturare
   il testo esistente in una funzione condivisa: costa ~20 righe duplicate
   di chiamate API stabili, tiene i hunk caldi a 1 riga l'uno (requisito
   anti-conflitto del mandato).
5. **Prefill/verify restano su GPU.** Il costo CPU del batch sarebbe
   proibitivo (stessi pesi ma n_tok× compute) e il mandato copre il decode;
   la conseguenza sulla residenza (re-staging transitorio) e' gestita dal
   ciclo dirty→spazzata, par. 2.
6. **Stub Metal.** I tre export nuovi hanno stub in `ds4_metal.m` (il file
   implementa l'API ds4_gpu_* per Mac): senza, un build Metal non
   linkerebbe. Su Metal il flag arma ma ogni join fa fallback GPU dichiarato
   (`h2d-enqueue-failed`): leva nulla, mai scorretta — e' una leva del
   backend CUDA di campagna.
7. **Slot ring = 4** (un solo job in volo per costruzione: schedule e join
   dello stesso layer stanno nello stesso encode; i 4 slot assorbono solo
   gli orfani di encode falliti a meta', che il worker e lo scheduler
   riciclano via `stale_reclaimed`).

## 7. Qualita' (punto 6 del mandato)

Q8 su CPU = stessa precisione di formato; cambia l'ordine di somma float
(riduzioni GPU vs accumulo sequenziale per riga su CPU) ⇒ **non bit-exact
con il decode GPU odierno per costruzione**: il gate di promozione e' il
rubric cieco (protocollo fail-fast, n≥3), non lo sha del testo. Due fatti
utili gia' nel tree: (a) il forward CPU qui usato e' matematicamente
identico al riferimento CPU del graph-test (`shared=%g/%g`, base
:12535-12601), che quindi resta il metro per quantificare il delta per
stadio; (b) i due percorsi GPU esistenti dello shared differiscono GIA' tra
loro (il fuso gate/up clampa a ±10 — base cu :24292-24298 — il non-fuso
usa clamp 0): la CPU segue il non-fuso/riferimento (nessun clamp). Nessun
cambio di formato, nessun fallback dinamico non deterministico oltre a
quello dichiarato e contato (che a regime sano deve stare a zero:
`fallback_count` nel summary e' il numero da guardare).

## 8. Telemetria (punto 5 del mandato)

- Per layer (solo con `DS4_CPU_SHARED_EXPERT_VERBOSE=1`, per non sporcare i
  run di protocollo): `[shared-cpu] layer=N cpu_ms=… wait_ms=… ok=…`.
- Summary a fine sessione (`[shared-cpu] final …`): `shared_cpu_ms{p50/p90}`
  (mediana da istogramma a bucket di 50 µs), `shared_wait_ms{p50/p90}`
  (attesa della GPU—cioe' dell'enqueue—al join), `vram_freed_mb` (byte
  davvero rilasciati dalle spazzate) + `startup_excluded_mb` (byte mai
  caricati per esclusione: e' la componente grossa, 1096,5 MiB attesi) +
  `vram_release_blocked_mb` (residenze non rilasciabili incontrate),
  `fallback_count`, `dropped`, `sched_failures`, `stale`, `vram_sweeps`,
  `pool=g132|single-thread`.
- Eventi: riga di arm a create, riga per spazzata non vuota, fallback
  loggati (primi 8 + 1/256, contatore sempre esatto).

## 9. Limiti e residui dichiarati

- Il beneficio VRAM esiste nel regime staging/esclusione (quello della
  campagna); in window/copy-model e' zero e il summary lo mostra. La curva
  di capacita' promette +0,4-1,0 t/s ai 302 slot SOLO se l'operatore alza la
  cache in un test separato (gate 2 di T1-bis): questa patch libera
  l'headroom, non ridimensiona nulla.
- La tassa CPU (~0,6-1,2 ms/layer stimati, da misurare: `shared_cpu_ms`)
  convive oggi con finestre di staffetta di ~4,9 ms/layer; nei layer
  all-hit la finestra e' ~0,4 ms e l'attesa finisce in `shared_wait_ms`
  (arm A di T1-bis: a slot invariati il gate 1 misura esattamente questa
  tassa, PRE ≤ +2%).
- `blocked_bytes` cattura range fusi che attraversano il confine dello span:
  con l'esclusione all'avvio non dovrebbero esistere (valore atteso 0); se
  compare, e' il segnale che un percorso ha staggiato uno span sovrapposto
  e va guardato prima di fidarsi del numero di headroom.
- Il worker attende l'evento D2H con `cudaEventSynchronize` fuori dal
  mutex; un contesto avvelenato fa fallire la wait → DONE_FAIL → fallback
  (che a sua volta fallira' → `ok=false` → stesso fail-closed di oggi sui
  kernel del layer).
- Con piu' sessioni/grafi armati nello stesso processo i due worker
  serializzano le submit sul pool (mutex): peggiora solo la latenza CPU di
  quel caso, mai la correttezza.
- Non implementato (fuori mandato): l'attribuzione degli sfratti shexp nei
  722/token di fondo (T0.4 diagnostico); il contatore delle spazzate ne da'
  una lettura equivalente a valle (quanti byte shexp rientrano per prefill).

## 10. Verifiche eseguite (statiche, come da mandato)

- Nessuna build, nessun server, `D:\` mai aperto; nessun file modificato
  fuori da `.microbench/shared1/` (il tree NON e' stato toccato: a
  differenza di dspark1, questo mandato prescrive di scrivere solo qui).
- `git apply --check` PASS sia sulla baseline pre-dspark1 sia sul tree
  corrente (dspark1 composto); roundtrip sulla baseline → file attesi
  byte-identici (SHA sotto).
- `git apply --numstat`: 754/4, 131/0, 16/0, 38/0.
- Bilanciamento `{}()[]` verificato su tutti e 4 i file (delta simmetrici).
- Verifica simbolo-per-simbolo di firme/campi usati contro il sorgente:
  ring API (base cu :16143-16331), `ds4_gpu_tensor` (:9015-9033),
  `cuda_model_range` (:1940-1957), pick_victim/evict_to_pool (:8236-8366),
  fd-staging e pinning (:8426-8538), cache f16/f32 (:4185-4340), walker
  span (ds4.c :1862-1942), pool g132 (:827-958), worker/ctx matvec Q8
  (:3788-3816, :4114-4184), shared CPU di riferimento (:6086-6142), punti
  del grafo (:11978, :12005-12292, :15095-15130), spex probe come modello
  di concorrenza (:9651-10028), `os_once`/`OS_ONCE_INIT` (:346).

## 11. SHA-256

Base del diff (pre-immagini dspark1 per i 2 file che dspark1 tocca; tree
corrente per gli altri 2, che nessuno ha toccato):

```text
3be7ce5fbbbf83ba5ea33bf73a598e27b10255959c0000b6eecbaa938821e495  ds4-p4a/ds4.c        (= .microbench/ds4_c.pre_dspark1.c)
3ad385c1ad819bda27ac0abc28c500eaa38c3b6035d2c5fd0cbd7593ffbd34da  ds4-p4a/ds4_cuda.cu  (= .microbench/ds4_cuda.pre_dspark1.cu)
ac597ea9603181a33f4146012f1e7423ef7365904b965a7e6d1a0a47f9ad7136  ds4-p4a/ds4_gpu.h    (tree corrente)
a996dfcda4469f3bb6d4961e81fd8ed6062480009a0e664542aae20bf6e32063  ds4-p4a/ds4_metal.m  (tree corrente)
```

Attesi dopo `git apply` sulla baseline:

```text
42ad52d8874701ecf30abaf9ffb30fa65f0d2b9ff770bfb69faa96edf057f4e5  ds4-p4a/ds4.c
43fffe8c7648ed04ffcb516196067d3008ae96da2dd582942aa5c75b681589ee  ds4-p4a/ds4_cuda.cu
50bbbc22986a3105915a3a441a5490347e616f0f6bac83cac3dacb225d013aef  ds4-p4a/ds4_gpu.h
4947dd47f547a54a3c03d72e6ca47de3ecdaf95f6c19d7d59c20c1f981a5bda4  ds4-p4a/ds4_metal.m
```

Artefatto:

```text
e6870246e5cd4b09be1ee5bef58141bf93fcd09d8d3bba56ea7b3ff65ff9c1ae  shared1.patch
```
