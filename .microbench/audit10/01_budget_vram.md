# Audit 10 — budget VRAM combinato

Perimetro: analisi statica del tree corrente, configurazione Windows/WDDM e `ctx=150000`. I byte sotto sono byte richiesti dal codice, senza arrotondamenti del driver. Su WDDM sia `cudaMalloc` sia `cudaMallocManaged` gravano sulla VRAM (`ds4-p4a/ds4_cuda.cu:91`, `ds4-p4a/ds4_cuda.cu:103`-`106`); i tensori del grafo usano managed memory salvo opt-in contrario (`ds4-p4a/ds4_cuda.cu:9280`-`9298`).

## 1. BUG

### B1 — Il tetto host-pin da 2 GiB non è un budget globale

**Severità: ALTA.**

**Prova.** `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB` determina `cuda_host_register_budget_bytes()` (`ds4-p4a/ds4_cuda.cu:3736`-`3750`) e l’unico accumulatore dichiarato per quel tetto è `g_model_registered_range_bytes` (`ds4-p4a/ds4_cuda.cu:1071`-`1082`). L’indexer ZC controlla e incrementa questo accumulatore (`ds4-p4a/ds4_cuda.cu:4017`-`4053`); lo fa anche il register-mmap masked (`ds4-p4a/ds4_cuda.cu:4139`-`4156`). Non lo incrementano invece:

- l’arena KV staged, allocata con `cudaHostAlloc` dopo aver sommato tutti i row-cache (`ds4-p4a/ds4_cuda.cu:21854`-`21884`);
- i quattro buffer di staging modello, ciascuno allocato con `cudaMallocHost` (`ds4-p4a/ds4_cuda.cu:6480`-`6481`, `ds4-p4a/ds4_cuda.cu:6532`-`6555`);
- lo staging host delle sei route, allocato con `cudaHostAlloc` (`ds4-p4a/ds4_cuda.cu:39313`-`39344`).

A `ctx=150000`, dalle capacità costruite in `ds4.c` risultano 2.162,030 MiB di KV host-pinned: 43 raw-cache con `raw_cap=2304`, più 21 layer ratio-4 e 20 ratio-128, più i 21 index-cache ratio-4 (`ds4-p4a/ds4.c:450`-`455`, `ds4-p4a/ds4.c:13107`-`13117`, `ds4-p4a/ds4.c:13153`-`13183`, `ds4-p4a/ds4.c:18616`-`18632`). Con chunk di default 64 MiB, lo staging modello aggiunge circa 256 MiB (`ds4-p4a/ds4_cuda.cu:6172`-`6183`, `ds4-p4a/ds4_cuda.cu:6532`-`6554`); sei route da 7.077.888 byte aggiungono 40,5 MiB (`ds4-p4a/ds4_cuda.cu:28175`-`28187`, `ds4-p4a/ds4_cuda.cu:51662`-`51675`). Il processo può quindi avere circa **4.506,5 MiB di host CUDA pinned** quando il contatore “da 2 GiB” è pieno: 2.048 MiB contabilizzati, 2.162,030 MiB KV, circa 256 MiB staging modello e 40,5 MiB route.

**Scenario concreto.** Input: `ctx=150000`, masked budget già vicino a 2 GiB, INDEXERZC attivo, KV staged e route cache attive. Stato: il contatore accetta/ha già accettato fino a 2 GiB, ma WDDM vede anche oltre 2,45 GiB non contabilizzati. Esito sbagliato: un successivo `cudaHostAlloc` può fallire benché il budget software dichiari il run ammissibile; se fallisce l’arena KV, il gate diventa sticky-off e la migrazione non libera la KV device (`ds4-p4a/ds4_cuda.cu:21873`-`21880`), alterando improvvisamente il budget VRAM sul quale si dimensionano slab e backbone (`ds4-p4a/ds4_cuda.cu:30995`-`31053`).

### B2 — `PIN EXHAUSTED` ricade in una copia VRAM non evictable che scavalca la riserva

**Severità: ALTA.**

**Prova.** Quando non trova una vittima, l’allocatore logga `PIN EXHAUSTED` e restituisce `NULL` (`ds4-p4a/ds4_cuda.cu:8746`-`8762`). Il chiamante non termina lì: dopo il fallimento fd-cache tenta il register-mmap (`ds4-p4a/ds4_cuda.cu:4125`-`4144`) e, se il budget host è pieno, arriva a un `cudaMalloc` diretto (`ds4-p4a/ds4_cuda.cu:4183`-`4195`). Questa allocazione non verifica né la riserva normale da 2.048 MiB né quella hot da 256 MiB, mentre il percorso streaming le verifica esplicitamente prima del `cudaMalloc` (`ds4-p4a/ds4_cuda.cu:8025`-`8047`, `ds4-p4a/ds4_cuda.cu:8671`-`8701`). Il range risultante viene inserito con gli ultimi campi implicitamente a zero (`ds4-p4a/ds4_cuda.cu:4214`-`4216`): per la definizione della struct è quindi `streamed=0` (`ds4-p4a/ds4_cuda.cu:1940`-`1956`) e `pick_victim` lo ignora (`ds4-p4a/ds4_cuda.cu:8496`-`8502`).

**Scenario concreto.** Input: `PIN_BACKBONE=1`, budget host 2 GiB esaurito, slab già ceduto, tutti i range streamed o troppo recenti o assenti. Stato: `pick_victim=-1`. Esito sbagliato: il fallback può consumare la riserva con un range permanentemente fuori dal pool delle vittime; ripetendo il caso, il numero di vittime legali diminuisce e si arriva a `cudaMalloc` fallito/`NULL`, invece di preservare la riserva dichiarata o fallire subito in modo stabile.

## 2. INTERFERENZE FRA LEVE

### I1 — `PIN_BACKBONE` + `DRAIN_OVERLAP4` + `INDEXER_HOST_ZEROCOPY` + cache richiesta 220: stato senza vittima e comportamento esatto

**Meccanismo.** Sì, uno stato senza vittima è raggiungibile, ma non perché lo slab, DOV o INDEXERZC diventino vittime: lo slab è esterno a `g_model_ranges` (`ds4-p4a/ds4_cuda.cu:8050`-`8055`), le entry ZC sono volutamente fuori da quel registro (`ds4-p4a/ds4_cuda.cu:3924`-`3938`) e DOV possiede solo un sidecar con due eventi e bookkeeping (`ds4-p4a/ds4_cuda.cu:37471`-`37500`). `pick_victim` considera soltanto range `streamed`, con `device_ptr` e con `last_used_tick <= tick-4`; fa prima i pass non-pinned e infine i pinned (`ds4-p4a/ds4_cuda.cu:8481`-`8509`). Quindi ritorna `-1` se tutti i range sono non-streamed, nulli o dentro lo scudo di recency.

Non c’è loop:

1. se esiste un backbone streamed abbastanza vecchio, il selettore lo restituisce; PIN tenta una sola cessione dello slab (`ds4-p4a/ds4_cuda.cu:8701`-`8727`);
2. se lo shed riesce, il ciclo riprova dopo il `cudaFree`; se non basta, lo shed risulta già consumato e il codice logga `PIN ESCAPE`, poi sfratta davvero il backbone (`ds4-p4a/ds4_cuda.cu:8728`-`8745`, `ds4-p4a/ds4_cuda.cu:8764`-`8776`);
3. se `vi<0`, tenta ancora una sola volta lo shed e poi ritorna `NULL` con `PIN EXHAUSTED` (`ds4-p4a/ds4_cuda.cu:8746`-`8762`); da lì interviene il fallback B2.

La cache “220” non garantisce 220 slot effettivi: il sizing usa `min(requested, (free-reserve)/per_expert)` (`ds4-p4a/ds4_cuda.cu:39081`-`39092`, `ds4-p4a/ds4_cuda.cu:39147`-`39150`). Se la capacità effettiva è 220, lo slab vale 220 × 7.077.888 = **1.557.135.360 byte = 1.485 MiB**; il byte-per-slot è verificato dal contratto route del modello (`ds4-p4a/ds4_cuda.cu:51662`-`51675`).

**Manifestazione a banco.** Sequenza attesa: `PIN blocked_backbone`, una riga `PIN degrade ... slots=220 ... rebuild_target_slots=110`, poi o `PIN rebuild result=ok`, o `PIN ESCAPE`, oppure `PIN EXHAUSTED ... action=caller-fallback` (`ds4-p4a/ds4_cuda.cu:8710`-`8743`, `ds4-p4a/ds4_cuda.cu:8750`-`8759`, `ds4-p4a/ds4_cuda.cu:37431`-`37441`). I contatori discriminanti sono `pin_expert_cache_sheds`, `pin_backbone_failopen`, `pin_no_victim`, `evict_backbone` e `expert_slots_current`, tutti stampati nel ledger VRAM di chiusura (`ds4-p4a/ds4_cuda.cu:30980`-`30992`).

**Guardia suggerita.** Vietare questo braccio come test “pin hard” se `pin_backbone_failopen != 0` o `pin_no_victim != 0`; quei valori provano che la semantica osservata non è più “backbone non reclamabile”. Accettare “cache 220” solo se il log di sizing riporta davvero `capacity=220`, non dal solo valore env (`ds4-p4a/ds4_cuda.cu:39220`-`39229`).

### I2 — Footprint combinato a `ctx=150000`: il nucleo fisso entra, il worst case residente no

**Meccanismo e prova numerica.** Con prompt lungo il prefill cap di default è 2.048 e `raw_cap=align(128+2048,256)=2304` (`ds4-p4a/ds4.c:7998`-`8016`, `ds4-p4a/ds4.c:18616`-`18632`). Il footprint device/managed noto in decode, con capacità effettiva 220, è:

| Consumatore | MiB | Prova sorgente |
|---|---:|---|
| Grafo non-KV, inclusi batch prefill persistenti e scratch indexer | 2.624,062 | allocazioni base/stato `ds4-p4a/ds4.c:13134`-`13233`; score/mask/selected `ds4-p4a/ds4.c:13205`-`13208`; famiglia batch `ds4-p4a/ds4.c:13255`-`13292`; `batch_ffn_out` lazy `ds4-p4a/ds4.c:13065`-`13069` |
| Extra grafo MTP ancora allocato col NextN CPU drafter | 36,234 | stati spec `ds4-p4a/ds4.c:13163`-`13188`; tensori MTP `ds4-p4a/ds4.c:13234`-`13252`; la sessione passa comunque `e->mtp_ready` `ds4-p4a/ds4.c:23260`-`23267` |
| Slab resident expert 220 | 1.485,000 | formula/allocazioni `ds4-p4a/ds4_cuda.cu:39081`, `ds4-p4a/ds4_cuda.cu:39258`-`39280`; slot da 7.077.888 `ds4-p4a/ds4_cuda.cu:51662`-`51675` |
| Staging route device ENFORCE, sei esperti | 40,500 | `ds4-p4a/ds4_cuda.cu:39345`-`39380` |
| Compact gather exact-selected | 40,500 in decode; fino a 1.728,000 high-water | il modello ha 256 esperti (`ds4-p4a/ds4.c:116`) e il dedupe può conservarli tutti `ds4-p4a/ds4_cuda.cu:45427`-`45445`; senza `DS4_CUDA_PREFILL_WAVES` (default off) i buffer sono grow-only `ds4-p4a/ds4_cuda.cu:43839`-`43842`, `ds4-p4a/ds4_cuda.cu:45523`-`45552`; rilascio solo globale `ds4-p4a/ds4_cuda.cu:38305`-`38338` |
| Ring KV staged | 8,000 | due slot da 4 MiB `ds4-p4a/ds4_cuda.cu:851`-`855`, allocati in `ds4-p4a/ds4_cuda.cu:21689`-`21710` |
| **Subtotale noto** | **4.234,296 MiB minimo decode; 5.921,796 MiB = 5,783 GiB col gather high-water 256** | somma delle righe sopra |

Anche 5.921,796 MiB è un **lower bound** del worst case completo: mancano range di modello vivi, pool di range sfrattati, piccoli map/buffer, eventuali altri sidecar, temporanei backend e contesto/librerie CUDA. Il sorgente registra inoltre circa 3,2 GiB misurati ma non allocati dal translation unit (driver, moduli e buffer interni) (`ds4-p4a/ds4_cuda.cu:81`-`87`). Su 12 GiB, col gather high-water, restano quindi circa 3.089,4 MiB fisici per backbone e consumatori non enumerati; applicando anche la riserva normale di 2.048 MiB, il margine operativo per i range di modello scende a circa **1.041,4 MiB** (`ds4-p4a/ds4_cuda.cu:8025`-`8033`). Nel caso minimo decode, gli stessi margini sono rispettivamente 4.776,9 e 2.728,9 MiB. INDEXERZC può togliere al device al massimo 346,5 MiB, non di più: ci sono 21 layer ratio-4, ciascuno con `1024×8192` F16 più `4096×64` F16 (`ds4-p4a/ds4.c:450`-`455`, `ds4-p4a/ds4.c:3178`-`3186`), cioè 363.331.584 byte totali.

**Risposta (b).** **No, il footprint peggiore combinato non entra come insieme residente garantito in 12 GiB.** Il nucleo minimo decode è circa 4,135 GiB, ma il solo high-water grow-only del gather può portarlo a circa 5,783 GiB prima di backbone e runtime CUDA; il backbone è una quantità dinamica non limitata da un budget globale e il runtime si affida a riserva, pool, shed e sfratti (`ds4-p4a/ds4_cuda.cu:8662`-`8701`). La misura già incorporata nel sorgente conferma il precipizio: +331 MiB passando da 140 a 189 slot produce circa 1.120 sfratti backbone/token (`ds4-p4a/ds4_cuda.cu:114`-`119`). Cache 220 è oltre quel punto di pressione se gli altri risparmi non hanno davvero liberato i range previsti.

**Manifestazione a banco.** `free_at_decode_start` può sembrare sufficiente, ma `what_at_min`, `range_bytes_at_min`, `pool_bytes_at_min`, `evict_backbone` e `backbone_reloads` esplodono intra-token; il ciclo libera prima un solo buffer di pool e poi una sola vittima (`ds4-p4a/ds4_cuda.cu:8575`-`8590`, `ds4-p4a/ds4_cuda.cu:8678`-`8701`). È la forma statica compatibile con la tempesta 885–1.104 sfratti/token.

**Guardia suggerita.** Non autorizzare cache effettiva 220 dal solo totale 12 GiB. Il gate di campagna deve richiedere contemporaneamente `capacity=220`, `pin_no_victim=0`, `pin_backbone_failopen=0`, nessuna `PIN degrade`, e un minimo intra-token sopra la riserva del requester; la sola fotografia inter-token è dichiaratamente insufficiente dal codice (`ds4-p4a/ds4_cuda.cu:114`-`125`).

### I3 — `PIN_BACKBONE` + cache-size richiesta + risparmi tardivi (`INDEXERZC`/`shared1`): la ricostruzione ridotta diventa permanente

**Meccanismo.** Lo shed usa la **capacità viva**, non il valore env: salva `slots=capacity`, imposta `rebuild_slots=slots/2`, quindi rilascia tutto lo slab (`ds4-p4a/ds4_cuda.cu:37378`-`37413`). Il nuovo sizing clampa la capacità a quel target (`ds4-p4a/ds4_cuda.cu:39174`-`39182`). Se riesce, però, la cache memorizza ancora `requested=220` insieme alla capacità ridotta (`ds4-p4a/ds4_cuda.cu:39431`-`39440`); le prepare successive considerano la configurazione identica confrontando `requested`, geometria e flag, ma **non** `capacity==requested`, e ritornano subito la cache ridotta (`ds4-p4a/ds4_cuda.cu:39020`-`39066`). Il comportamento permanente è anche dichiarato nel ramo di successo (`ds4-p4a/ds4_cuda.cu:39687`-`39701`) e al request-end (`ds4-p4a/ds4_cuda.cu:31120`-`31128`).

**Risposta (c).** Con capacità iniziale effettiva 220, il primo shed punta a 110; con capacità iniziale già autolimitata a `C<220`, punta a `floor(C/2)`. Un successivo shed dimezza ancora. INDEXERZC che libera fino a 346,5 MiB e shared1 che esclude i tensori shared dalla startup cache (`ds4-p4a/ds4.c:1931`-`1937`, `ds4-p4a/ds4.c:1996`-`2001`) non fanno rieseguire il sizing finché il config-match resta vero. Quindi la richiesta 220 diventa un’etichetta/ceiling, non una capacità mantenuta.

**Manifestazione a banco.** `[PIN rebuild result=ok capacity=110 target=110 requested=220]`, seguito nelle richieste successive da `expert_slots_current=110` senza nuova riga di sizing; aumentano miss, `direct_loads` ed eventualmente `pin_exact_stream_fallbacks` (`ds4-p4a/ds4_cuda.cu:39687`-`39701`, `ds4-p4a/ds4_cuda.cu:46168`-`46185`).

**Guardia suggerita.** Vietare `PIN_BACKBONE=1` nei run che richiedono semanticamente “cache sempre 220”. Nei run pin2, definire invece l’accettazione sulla capacità effettiva e scartare ogni run in cui una capacità ridotta sopravvive mentre si pretende di confrontare cache-size 220.

### I4 — `DRAIN_OVERLAP4` + `PIN_BACKBONE`: lo shed trasforma l’overlap residuo in uno stallo sincrono

**Meccanismo.** DOV arma l’evento dopo l’ultimo publish senza sincronizzare l’upload (`ds4-p4a/ds4_cuda.cu:43117`-`43132`), poi il worker pubblica `route_completed` sul piano host (`ds4-p4a/ds4_cuda.cu:43255`-`43289`). Per questo la guardia shed `submitted != completed` (`ds4-p4a/ds4_cuda.cu:37355`-`37375`) normalmente non vede l’upload CUDA ancora outstanding. Lo shed però sincronizza stream 0 prima di liberare lo slab (`ds4-p4a/ds4_cuda.cu:37385`-`37405`); stream 0 è dietro il wait-event DOV (`ds4-p4a/ds4_cuda.cu:37649`-`37676`), e il release sincronizza anche l’upload stream prima di distruggere gli eventi (`ds4-p4a/ds4_cuda.cu:37725`-`37735`). È memory-safe, ma il drain differito torna improvvisamente sul critical path dello shed.

**Manifestazione a banco.** Spike sul token del primo `PIN degrade`, aumento di `gpu_stall_on_drain_ms`/latenza e calo di `drain_overlap_ms`; non è atteso un aumento sistematico di `pin_shed_deferrals`, perché `route_completed` è già pubblicato (`ds4-p4a/ds4_cuda.cu:37589`-`37614`, `ds4-p4a/ds4_cuda.cu:37679`-`37704`).

**Guardia suggerita.** Vietare la coppia nei run che misurano il solo beneficio DOV se `pin_expert_cache_sheds != 0`; in alternativa separare i token di shed dal percentile DOV. Non usare `pin_shed_deferrals=0` come prova che non ci sia stata attesa CUDA.

### I5 — `INDEXER_HOST_ZEROCOPY` + masked budget 2 GiB: competizione per ordine di arrivo e fail-open parziale

**Meccanismo.** INDEXERZC e register-mmap condividono esattamente contatore e tetto (`ds4-p4a/ds4_cuda.cu:4017`-`4053`, `ds4-p4a/ds4_cuda.cu:4143`-`4156`). Il primo pin indexer che non entra mette un latch; le entry già create restano ZC e tutte le successive ricadono nella fd-cache (`ds4-p4a/ds4_cuda.cu:3967`-`3975`, `ds4-p4a/ds4_cuda.cu:4009`-`4012`, `ds4-p4a/ds4_cuda.cu:4113`-`4127`). La parte ricaduta in fd-cache usa la riserva hot da 256 MiB solo perché `what=="indexer_f16"` (`ds4-p4a/ds4_cuda.cu:8794`-`8803`), mentre gli altri requester conservano 2.048 MiB (`ds4-p4a/ds4_cuda.cu:8025`-`8047`): può quindi riempire l’headroom e riaprire gli sfratti backbone.

**Manifestazione a banco.** `[indexer-zc] pin_failed ... pinned_so_far=<346.5 MiB`, numero tensori inferiore a 42, poi richieste `indexer_f16` nella fd-cache, `PIN blocked_backbone`/`PIN ESCAPE` e `evict_backbone` dopo l’attivazione dell’indexer (`ds4-p4a/ds4_cuda.cu:3978`-`4004`, `ds4-p4a/ds4_cuda.cu:8872`-`8886`).

**Guardia suggerita.** Considerare valido il braccio INDEXERZC solo con la riga `active=1 tensors=42 pinned_bytes=363331584`; vietare confronti “ZC ON” quando il latch è parziale. Il budget unico non riserva 346,5 MiB per l’indexer, quindi il solo valore env `2` non è una guardia sufficiente.

### I6 — `RELEASE_PREFILL_SCRATCH` + cache 220: quasi 2,6 GiB di grafo restano residenti

**Meccanismo.** Il flag libera soltanto `g_cuda_tmp`; il codice dichiara esplicitamente che `prefill_tokens` e tutti i `batch_*` appartengono al grafo e non vengono rilasciati (`ds4-p4a/ds4_cuda.cu:31003`-`31034`). A prefill cap 2.048, la famiglia batch più `batch_ffn_out` vale circa 2.020,977 MiB e score/mask/selected dell’indexer altri 589,969 MiB (`ds4-p4a/ds4.c:13065`-`13069`, `ds4-p4a/ds4.c:13205`-`13208`, `ds4-p4a/ds4.c:13255`-`13292`). Lo slab viene dimensionato dopo il rilascio, usando correttamente il `cudaMemGetInfo` reale (`ds4-p4a/ds4_cuda.cu:31041`-`31065`), ma il nome del flag non implica che quei 2,6 GiB siano disponibili.

**Manifestazione a banco.** `release_status=released` e `released_bytes>0`, ma `free_at_decode_start` cresce solo della dimensione di `g_cuda_tmp` più la KV migrata, non della famiglia batch; `capacity` può quindi essere minore di 220 o il margine intra-token restare insufficiente (`ds4-p4a/ds4_cuda.cu:31022`-`31038`, `ds4-p4a/ds4_cuda.cu:39147`-`39150`).

**Guardia suggerita.** Nei fogli di budget chiamare il flag “backend tmp release” e usare esclusivamente `free_at_decode_start`/`capacity` misurati come input del braccio 220; vietare un calcolo che sottragga tutta la memoria prefill.

### I7 — NextN pin + host CUDA pinned: pressione di RAM/working-set non visibile nel budget VRAM

**Meccanismo.** `DS4_NEXTN_PIN=1` fa `VirtualLock` di circa 741 MB; `PIN=2` include anche circa 3,54 GiB di esperti (`ds4-p4a/ds4.c:22305`-`22319`). Il codice aumenta il working set del processo e poi blocca ogni regione (`ds4-p4a/ds4.c:22333`-`22356`, `ds4-p4a/ds4.c:22409`-`22449`), ma non tocca `g_model_registered_range_bytes`. Non è VRAM e non è host pin CUDA; tuttavia si somma alla RAM non facilmente reclamabile mentre B1 può già impegnare circa 4,5 GiB di host CUDA pinned.

**Manifestazione a banco.** `[nextn-cpu] pin mode=2 locked≈4270 MB`, riduzione della memoria disponibile/working-set e possibili fallimenti `cudaHostAlloc` o crescita dei fault in altri mmap, senza alcun aumento del contatore masked (`ds4-p4a/ds4.c:22444`-`22449`, `ds4-p4a/ds4_cuda.cu:1078`).

**Guardia suggerita.** Vietare `DS4_NEXTN_PIN=2` nel braccio a masked budget pieno + KV staged + INDEXERZC, salvo verifica esplicita della RAM committed/locked. `PIN=1` resta separato dal conto VRAM ma va comunque sommato al budget host di processo.

## 3. ESCLUSIONI

- **Nessun loop infinito in `pick_victim`/stream allocator.** Ogni iterazione o alloca, libera un buffer di pool, consuma una vittima, esegue al massimo uno shed oppure ritorna `NULL`; lo shed riuscito è marcato prima del retry (`ds4-p4a/ds4_cuda.cu:8678`-`8701`, `ds4-p4a/ds4_cuda.cu:8723`-`8762`, `ds4-p4a/ds4_cuda.cu:37408`-`37413`). Il rischio reale è B2, non un loop.

- **`PIN_BACKBONE` non è un pin hard, per disegno leggibile.** Il pass 2 seleziona deliberatamente i range pinned come ultima risorsa (`ds4-p4a/ds4_cuda.cu:8490`-`8507`) e il chiamante dichiara `PIN ESCAPE` prima dello sfratto (`ds4-p4a/ds4_cuda.cu:8728`-`8776`). Non va riclassificato come violazione silenziosa.

- **Lo slab esperti non è accidentalmente eleggibile dall’LRU.** È fuori da `g_model_ranges` e viene restituito solo dal percorso esplicito di shed, dopo quiescenza stream 0 e release del worker (`ds4-p4a/ds4_cuda.cu:8050`-`8055`, `ds4-p4a/ds4_cuda.cu:37337`-`37413`). La granularità “tutto lo slab” deriva dalle tre allocazioni per capacità (`ds4-p4a/ds4_cuda.cu:39258`-`39280`).

- **DOV non quadruplica lo staging e non aggiunge uno slab VRAM.** Il suo stato materiale sono due eventi CUDA, atomici e un batch ledger (`ds4-p4a/ds4_cuda.cu:37471`-`37500`, `ds4-p4a/ds4_cuda.cu:37520`-`37537`); i buffer route esistono già nella cache (`ds4-p4a/ds4_cuda.cu:39313`-`39380`). L’interferenza verificata è temporale, descritta in I4.

- **LEDGERFIX non trattiene un secondo payload.** Salva solo la descrizione `ds4_transport_h2d_batch` nel sidecar e committa al retire (`ds4-p4a/ds4_cuda.cu:37483`-`37489`, `ds4-p4a/ds4_cuda.cu:37570`-`37580`); non compare alcuna allocazione CUDA nel percorso.

- **La migrazione KV è ordinata correttamente.** Prima completa tutte le D2H, poi assegna gli `host_ptr`, quindi libera ogni tensore device; su errore di copia libera l’arena host e non cede la KV device (`ds4-p4a/ds4_cuda.cu:21887`-`21920`, `ds4-p4a/ds4_cuda.cu:21922`-`21945`). Dopo una migrazione riuscita restano in VRAM i due slot da 4 MiB e i piccoli accumulatori (`ds4-p4a/ds4_cuda.cu:21689`-`21740`).

- **Cleanup INDEXERZC sano.** Tutte le entry vengono `cudaFreeHost` e azzerate (`ds4-p4a/ds4_cuda.cu:3953`-`3965`); il cleanup globale lo invoca prima di riportare a zero il contatore condiviso (`ds4-p4a/ds4_cuda.cu:8985`-`9010`). Non ho trovato doppio free né byte fantasma su teardown normale.

- **Retry dell’allocazione cache esperti sano.** Un fallimento libera slab, map, host staging, transient device, stream ed eventi prima di ridurre la capacità del 10% (`ds4-p4a/ds4_cuda.cu:39703`-`39749`).

- **Il retry dello staging modello non perde i buffer parziali.** Un fallimento intermedio ritorna prima di pubblicare `g_model_stage_bytes`, ma la chiamata successiva percorre comunque il ciclo di cleanup e libera ogni `g_model_stage_raw[i]` non nullo prima di riallocare (`ds4-p4a/ds4_cuda.cu:6480`-`6512`, `ds4-p4a/ds4_cuda.cu:6532`-`6555`).

- **sharedcore è CPU-only rispetto a questo budget.** La leva crea un pool dedicato e opzionalmente assegna affinità ai suoi thread (`ds4-p4a/ds4.c:11314`-`11342`); non cambia il numero o la dimensione degli slot CUDA. shared1 può invece evitare il caricamento dei pesi shared alla startup, ma non modifica automaticamente la cache richiesta (`ds4-p4a/ds4.c:1905`-`1912`, `ds4-p4a/ds4.c:1931`-`1937`).

- **INDEXERZC completo ha footprint device nullo per le proprie entry, ma non è “gratis”.** I puntatori sono UVA su `cudaHostAllocMapped`, fuori dall’LRU (`ds4-p4a/ds4_cuda.cu:3907`-`3926`, `ds4-p4a/ds4_cuda.cu:4025`-`4053`); i kernel leggono comunque i due tensori F16 densi per ciascun layer indexer (`ds4-p4a/ds4.c:13943`-`13965`). Ho escluso quindi 346,5 MiB dalla VRAM solo nel caso `tensors=42`, conservandoli nel conto host-pin.
