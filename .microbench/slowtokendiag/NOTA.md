# Diagnosi della sonda `slow-token`

## Verdetto

L'ipotesi forte del mandato non regge: `DS4_CUDA_SLOW_TOKEN_LOG` non esegue
`cudaMemGetInfo`, non drena CUDA e non prende un lock del route worker. Accende
pero' un osservatore per ogni token **prima** di conoscere la durata del token:
legge il clock, fotografa cinque valori di baseline (due atomici e tre plain,
due dei quali condivisi senza sincronizzazione) e scrive lo stato globale
dell'osservatore. `DS4_CUDA_SLOW_TOKEN_MS` viene consultata solo a
fine token, dopo una seconda lettura del clock, e governa le letture dei delta e
la `fprintf`; non governa l'arming/la raccolta iniziale
(`ds4-p4a/ds4_cuda.cu:35213-35238`, `:35241-35279`). Quindi:

* non esiste un valore di `MS` che renda il percorso caldo identico al default;
  l'unica configurazione neutra e' `DS4_CUDA_SLOW_TOKEN_LOG=0`/assente (e, per
  spegnere l'intero watcher condiviso, anche VRAM-prio periodica a 0 e
  VRAM-peak spenta);
* l'effetto osservato e' compatibile con una perturbazione deterministica di
  fase fra thread di decode, route worker e allocatore al confine di capacita',
  non con una query di ammissione fatta dalla sonda;
* i dati disponibili non separano definitivamente il costo della raccolta
  iniziale dal costo della stampa inter-token: manca, sul binario di T7, il
  braccio `LOG=1, MS` maggiore di qualunque token. La lettura statica basta pero'
  a dire che neppure quel braccio avrebbe un hot path identico al default.

I riferimenti `ds4_cuda.cu:7083/:7094/:31424` del mandato appartengono alla
fotografia precedente del sorgente; nel working tree corrente le stesse
funzioni/righe sono a `:8760/:8769/:35270`
(`.microbench/atlante/REVISIONE.md:34-36` documenta ancora la numerazione
precedente).

## 1. Percorso esatto e campi della riga

Il server arma il watcher prima di sample/eval e lo chiude dopo che il passo ha
prodotto e gestito i token (`ds4-p4a/ds4_server.c:7428-7442`,
`:7466-7515`, `:7660-7669`). Il flag e la soglia sono letti e cachati
separatamente: `LOG` abilita il watcher, mentre `MS` accetta un `double` finito
non negativo e ha default 1500 (`ds4-p4a/ds4_cuda.cu:8760-8786`).

All'inizio di **ogni** passo con watcher attivo
(`ds4-p4a/ds4_cuda.cu:35219-35238`) vengono raccolti:

* `started`: `cuda_wall_sec()`, che e' `os_monotonic_sec()`
  (`ds4-p4a/ds4_cuda.cu:4918-4920`); su Windows e'
  `QueryPerformanceCounter`, non una chiamata CUDA
  (`ds4-p4a/src/platform/os_clock.h:4-14`);
* baseline di `worker_wait_ms`: lettura plain di
  `g_moe_expert_cache.route_ready_wait_seconds`; il delta finale moltiplicato
  per 1000 e' `worker_wait_ms` (`ds4-p4a/ds4_cuda.cu:35231-35232`,
  `:35256-35258`). Il contatore misura il tempo in cui il decode aspetta
  `route_ready`, ed e' aggiornato sul thread di decode
  (`ds4-p4a/ds4_cuda.cu:49794-49805`);
* baseline di `pread_calls` e `pread_bytes`: due load atomici relaxed; i delta
  finali sono altri due load relaxed (`ds4-p4a/ds4_cuda.cu:35233-35236`,
  `:35259-35264`). I contatori vengono comunque incrementati sul percorso I/O
  anche con la sonda spenta, rispettivamente all'emissione della lettura e sui
  byte effettivamente restituiti
  (`ds4-p4a/ds4_cuda.cu:32374-32389`, `:32395-32402`);
* baseline di `transient_serves`: lettura plain di
  `g_moe_zerocopy.ssd_served`, poi differenza a fine token
  (`ds4-p4a/ds4_cuda.cu:35237`, `:35265-35266`); il route worker incrementa il
  campo quando serve la via SSD (`ds4-p4a/ds4_cuda.cu:43346-43352`);
* baseline di `evict_backbone_delta`: lettura plain di
  `g_vram_prio_evict_backbone`, poi differenza a fine token
  (`ds4-p4a/ds4_cuda.cu:35238`, `:35267-35268`); il contatore e' incrementato
  nel sito di sfratto (`ds4-p4a/ds4_cuda.cu:8815-8826`);
* `tokens_in_step` non richiede una query: e' il `token_count` passato dal
  server, calcolato come delta di `completion`
  (`ds4-p4a/ds4_server.c:7440-7442`, `:7666-7668`) e stampato direttamente
  (`ds4-p4a/ds4_cuda.cu:35269-35278`).

Le letture plain di `ssd_served` ed `evict_backbone` sono esplicitamente
dichiarate non sincronizzate sebbene scritte dal route worker
(`ds4-p4a/ds4_cuda.cu:35193-35197`): in C++ sono data race, oltre a toccare
cache line condivise. Non c'e' un lock, ma non e' corretto chiamarle letture
neutre. Le letture del clock, delle baseline e dello stato globale
`g_token_watch` sono tutte operazioni che l'early return del percorso normale
non esegue (`ds4-p4a/ds4_cuda.cu:35213-35238`).

A fine token `total_ms` viene calcolato **prima** del test della soglia; solo se
`total_ms > MS` vengono letti i delta e chiamata `fprintf(stderr, ...)`
(`ds4-p4a/ds4_cuda.cu:35252-35279`). Percio' `MS=1` aggiunge le letture finali
e una stampa a ogni token, ma anche `MS=1500` o `MS=1e308` conservano arming,
clock e baseline a ogni token. Una soglia enorme sopprime la stampa, non
ristabilisce il default.

## 2. Perche' non e' `cudaMemGetInfo`, e quale catena resta

`ds4_gpu_token_watch_begin` chiama anche `ds4_vram_peak_token_begin`, ma questa
funzione ritorna subito se il flag separato `DS4_CUDA_VRAM_PEAK_PROBE` e'
spento (`ds4-p4a/ds4_cuda.cu:35224-35227`,
`:31438-31440`). Solo con quel flag acceso chiama
`ds4_vram_peak_query_free_bytes`, che contiene la vera `cudaMemGetInfo`
(`ds4-p4a/ds4_cuda.cu:31390-31404`). Nei manifest T7 il flag VRAM-peak non
esiste e nei log non ci sono righe `[vram-peak]`; `X_T7a2_soloslow` differisce
da T0 soltanto per `SLOW_TOKEN_LOG=1` e `MS=1`
(`D:\ds4_work\lane_ab\runs\X_T0_neutralita\manifest.txt:26-30`,
`D:\ds4_work\lane_ab\runs\X_T7a2_soloslow\manifest.txt:20-32`).

L'ammissione che decide davvero fra allocazione, reclaim e sfratto esegue la
propria `cudaMemGetInfo` nel loop normale e confronta `freeb` con
`aligned + reserve` (`ds4-p4a/ds4_cuda.cu:9120-9169`). La catena sostenuta dal
codice e dai dati e' quindi:

`watcher a inizio token -> perturbazione di fase/cache-line -> diverso istante
delle normali query dell'allocatore -> diverso lato del test di riserva ->
reclaim/sfratto -> ping-pong`.

L'ultimo passaggio e' un'inferenza causale, non l'identificazione della singola
istruzione colpevole. I bracci disponibili provano il trigger complessivo: T0
ha 895 sfratti in 2250 token e finisce
(`D:\ds4_work\lane_ab\REPORT.md:555-562`), mentre il solo slow watcher porta
T7a2 a sette token tutti in stallo e all'abort
(`D:\ds4_work\lane_ab\REPORT.md:603-623`). Le sequenze quasi identiche sono
nelle righe `[slow-token]` di T7a/T7a2/T7b
(`D:\ds4_work\lane_ab\runs\X_T7a_diagnostica\server.stderr.log:3261`,
`:5498`, `:7735`; `D:\ds4_work\lane_ab\runs\X_T7a2_soloslow\server.stderr.log:3261`,
`:5498`, `:7735`; `D:\ds4_work\lane_ab\runs\X_T7b_diag\server.stderr.log:3261`,
`:5498`, `:7735`). Gia' la prima riga, emessa solo dopo l'eval, contabilizza
947 sfratti; quindi la stampa di quella riga non puo' aver causato gli sfratti
del primo token. Puo' ancora contribuire a mantenere il regime dal token
successivo: per separare le due componenti serve il braccio a soglia
irraggiungibile, che oggi manca.

Questo e' un secondo grilletto **fenomenologico** della bistabilita' gia'
comandata dalla riserva 1792/2048 (ledger
`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:18986-19004`), ma non e' una
seconda query di ammissione. La deterministica ripetizione dei conteggi e la
rumorosita' dei tempi sono coerenti con un cambio discreto di ramo, non con un
costo additivo della telemetria.

## 3. Audit delle altre sonde

### `DS4_CUDA_VRAM_PRIO_LOG_EVERY_TOKENS`

**Condivide il difetto del watcher.** Qualunque valore non zero rende vero
`cuda_token_watch_requested`, quindi esegue a ogni token gli stessi clock e le
stesse baseline della slow-token, anche quando non emette
(`ds4-p4a/ds4_cuda.cu:8789-8806`, `:35213-35238`). Ogni N token chiama poi
`cuda_vram_prio_log` (`ds4-p4a/ds4_cuda.cu:35280-35291`), e quell'emettitore
fa esplicitamente `cudaMemGetInfo` e `fprintf`
(`ds4-p4a/ds4_cuda.cu:31619-31625`). L'unico valore che spegne sia raccolta sia
stampa e' `N=0`. Non e' la causa necessaria dei T7, perche' T7a2 non la imposta,
ma non e' una sonda neutra da aggiungere a un braccio di prestazione.

### `DS4_CUDA_WORKER_PROFILE_EVERY_TOKENS`

`EVERY_TOKENS` governa solo il report periodico; la raccolta e' governata dal
flag separato `DS4_CUDA_WORKER_PROFILE`
(`ds4-p4a/ds4_cuda.cu:5095-5102`, `:5138-5157`,
`:5519-5533`). A profiler acceso, i siti caldi leggono clock e aggiornano
atomici (`ds4-p4a/ds4_cuda.cu:5160-5167`, `:5237-5261`) e, su Windows,
campionano anche `GetProcessMemoryInfo` per i page fault del job
(`ds4-p4a/ds4_cuda.cu:5221-5234`, `:5327-5336`). Dunque non e' "stampa
soltanto" e alzare `EVERY_TOKENS` non elimina la raccolta.

Non condivide pero' il **trigger osservato**: non arma `g_token_watch` (i suoi
marker sono intenzionalmente prima dell'early return,
`ds4-p4a/ds4_cuda.cu:35219-35224`) ed era acceso a finestre di 64 sia in T0
sia in T7 (`D:\ds4_work\lane_ab\runs\X_T0_neutralita\manifest.txt:29-30`,
`D:\ds4_work\lane_ab\runs\X_T7a2_soloslow\manifest.txt:31-32`). T0 completo e
sano e' la controprova sperimentale richiesta; il ledger la riassume a
`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:19701-19717`. La differenza
centrale non e' "profilazione contro nessuna profilazione", ma l'aggiunta di un
nuovo punto di osservazione esattamente al confine del token; in un sistema
bistabile il costo totale non e' una misura sufficiente della perturbazione di
fase.

### `DS4_CUDA_TRANSPORT_LEDGER_EVERY_TOKENS`

Anche qui `EVERY_TOKENS` decide solo quando stampare; il flag
`DS4_CUDA_TRANSPORT_LEDGER` arma la raccolta
(`ds4-p4a/ds4_cuda.cu:28883-28910`, `:29318-29338`). La raccolta aggiorna la
tabella per coppia e usa uno spinlock condiviso fra i siti di trasporto
(`ds4-p4a/ds4_cuda.cu:28913-28920`, `:28951-28989`); non fa query CUDA. Non e'
costo zero e aumentare N non rimuove il lock. Tuttavia e' acceso a N=64 anche
nel T0 sano (`D:\ds4_work\lane_ab\runs\X_T0_neutralita\manifest.txt:26-27`) e
resta identico nel T7a2 (`D:\ds4_work\lane_ab\runs\X_T7a2_soloslow\manifest.txt:28-29`):
non spiega il delta T0/T7.

### Le quattro `DS4_METAL_*_STAGE_PROFILE`

Queste sono molto piu' perturbanti della slow-token e il piano non puo'
classificarle "costo zero":

* `DS4_METAL_DECODE_STAGE_PROFILE` chiama un boundary dopo i sottostadi del
  decode (`ds4-p4a/ds4.c:13703-13709`, con chiamate da `:13741` in avanti);
* `DS4_METAL_INDEXER_STAGE_PROFILE` chiama boundary nel decode e nel percorso
  batch/indexer (`ds4-p4a/ds4.c:13856`, `:14045-14080`,
  `:15915`, `:16793-16841`);
* `DS4_METAL_LAYER_STAGE_PROFILE` chiama boundary per attention e FFN batch
  (`ds4-p4a/ds4.c:15916-15924`, `:17247-17253`);
* `DS4_METAL_Q_STAGE_PROFILE` chiama boundary lungo il Q path batch
  (`ds4-p4a/ds4.c:15917-15928`).

I tre emettitori di boundary fanno `ds4_gpu_end_commands`, leggono il clock,
stampano e riaprono i comandi (`ds4-p4a/ds4.c:15828-15849`,
`:15851-15873`, `:15876-15892`). Sul backend di questi run
`ds4_gpu_end_commands()` e' letteralmente
`cudaDeviceSynchronize()` (`ds4-p4a/ds4_cuda.cu:17750-17753`). Ogni boundary
quindi spezza la pipeline e cambia scheduling/ammissioni; perfino il boundary
iniziale dell'indexer con `stage == NULL` sincronizza senza stampare
(`ds4-p4a/ds4.c:15828-15848`).

**Conseguenza per il piano:** i quattro bracci vanno rifatti come diagnostica
intrusiva, uno alla volta, con controllo OFF coevo e cancello di regime sugli
sfratti. I tempi di sottostadio possono servire per attribuzione interna al
regime sincronizzato, non come decomposizione del throughput normale. Per una
misura prestazionale non perturbante serve un'altra implementazione (eventi
GPU/trace asincrono); non basta cambiare una soglia.

## 4. Verdetto sui numeri storici

### D1, `worker_wait = 86,7%`

Il D1 storico **non era nel regime di tempesta**, contrariamente alla frase
successiva del ledger che lo dichiara "ribaltato"
(`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:19672-19680`). Il receipt
del run dice: binario `99ed54f6...`, slow-token a MS=1, VRAM-peak e VRAM-prio
attivi, 800/800 token, mediana 218,9 ms e soli 734 sfratti totali =
0,92/token (`D:\ds4_work\diag_ab\REPORT.md:1-10`;
`D:\ds4_work\diag_ab\runner.sh:131-135`). La riga finale conferma 734
(`D:\ds4_work\diag_ab\runs\D1_diag\server.stderr.log:5324`) e l'ultimo token
ha `evict_backbone_delta=0`
(`D:\ds4_work\diag_ab\runs\D1_diag\server.stderr.log:5320`). Questo e' il
regime normale dopo il caricamento iniziale, non i ~1100 sfratti per token di
T7. D1 aveva inoltre attivo `DS4_CUDA_VRAM_PEAK_PROBE`, che esegue davvero
`cudaMemGetInfo()` a ogni token, e nondimeno rimase nel regime normale: e' un
controesempio all'idea che la sola query CUDA sia causa sufficiente, pur non
essendo un confronto controllato perche' binario e stato iniziale sono diversi.

Ricalcolando le 800 righe D1 si ottengono 253,394 ms medi, 219,677 ms di
worker-wait e rapporto 0,86694, coerente con il ledger
(`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:17288-17292`). Il numero va
quindi etichettato **"regime normale, ma strumentato e senza controllo OFF
capace di misurare la stessa grandezza"**: il nuovo T7 non lo trasforma
retroattivamente in un dato di tempesta, ma vieta di chiamarlo costo-zero o
counterfactual pulito.

### Fatto 5 dell'atlante

Anche il fatto 5 viene dalla stessa sonda `[slow-token]`, non dal worker
profile: i due campi citati sono esattamente quelli emessi insieme dalla riga
slow-token (`ds4-p4a/ds4_cuda.cu:35256-35278`) e, quando il ledger lo formula,
il profilatore worker e' ancora dichiarato "in implementazione"
(`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:17270`,
`:17297-17298`). I receipt D1 mostrano esempi normali con
`evict_backbone_delta=0` e wait 95-97%: pos 12 = 680,071/702,579 ms e pos 45 =
679,435/702,289 ms
(`D:\ds4_work\diag_ab\runs\D1_diag\server.stderr.log:2739`, `:2845`).

Il fatto e' dunque vero **per le raffiche di attesa osservate nel D1 normale**.
E' falsa la generalizzazione con cui l'atlante scarta ogni leva sugli sfratti
(`.microbench/atlante/REVISIONE.md:51-58`, `:387-397`): T7 espone un secondo
fenomeno, la tempesta di capacita', nel quale i token 2-7 hanno ~1094
sfratti/token e `worker_wait` solo ~13-27% del totale
(`D:\ds4_work\lane_ab\runs\X_T7b_diag\server.stderr.log:5498-16604`;
ledger `reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:19725-19734`). Leve
anti-sfratto restano irrilevanti per le raffiche I/O di D1, ma non possono
essere scartate come cura/prevenzione del regime di tempesta. Questa
separazione dei due fenomeni e' il verdetto storico corretto.
