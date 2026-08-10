# Audit 46 - i sottosistemi dormienti: ring-esperti, reap, kv-ring

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `24fd5c2ee`.
Niente compilato, nessun server avviato: solo lettura di codice, rapporti, script
e log gia' in cassa. Marcatura: [MISURATO] = codice letto riga per riga o log
esistente; [DEDOTTO] = aritmetica su misure; [IPOTESI] = da falsificare con la
misura indicata. `cache-esperti` e' fuori perimetro (altro agente); la tocco solo
dove un sottosistema del mio perimetro la intreccia.

## Esito in cinque righe

1. **`ring-esperti` va CANCELLATO, non risvegliato.** Il difetto noto e'
   l'aliasing di processo fra bersaglio e bozza (stato globale, chiave senza
   identita' di modello): nella configurazione due-cache di produzione, che
   mappa `blk.0` della bozza, basta `LLAMA_RING=1` per servire un modello coi
   pesi dell'altro. In piu', accenderlo SPEGNE la cache esperti in silenzio.
   Risvegliarlo = riscriverlo per-istanza, cioe' ri-ottenere la cache-esperti
   che gia' esiste. Valore residuo: zero (il suo piano di misura non fu mai
   eseguito, e la curva di capienza della cache ha gia' risposto alle stesse
   domande).
2. **`reap` va cancellato quasi tutto.** La sua ragione fisica (modello 80,76 GB
   su 64 GB di RAM, residenza decisa dalla LRU di Windows) e' morta col banco a
   96 GB e col modello in RAM pinnata. Acceso OGGI non e' inerte: e' peggio —
   la mappa si riempie con gli id della bozza CPU e col ramo overlap riordinato
   per residenza, e `LLAMA_REAP_AMMISSIONE<1` altererebbe l'uscita del bersaglio
   con quella mappa avvelenata. Da salvare solo `reap_fissa_working_set` (25
   righe).
3. **`kv-ring` e' vivo e il suo bilancio va corretto, non il suo codice.** Il
   backing pinnato era dichiarato (KV_RING.md), ma nessun log lo somma; il
   reperto nuovo e' un TERZO consumatore di pinnata mai contato:
   `CUDA_Host model buffer = 1.010 MiB` (pesi non offloadati su `cudaMallocHost`
   per difetto). Con quel GiB il conto della morte a 104k quadra; senza
   (`--no-host`, il flag esiste gia') il carico probabilmente passa.
4. **La scelta del buffer del backing e' parametrizzabile in ~10 righe**: il
   solo punto cablato e' `dsv4_kv_ring_buft`; kernel, supports_op e costruttore
   sono gia' agnostici. Ma non e' la cura del 104k: e' un A/B utile altrove.
5. **Tre semantiche di accensione diverse nei tre sottosistemi** (`reap`: solo
   `"1"`; `ring`: tutto tranne `0`; `kv-ring`: `!=0` nel runtime ma PRESENZA nel
   server): igiene degli script gia' oggi corretta per caso, non per contratto.

---

# 1. ring-esperti - dormiente, e con un difetto di correttezza armato

## Che cos'e' e perche' dorme

`ggml/src/ggml-cuda/ring-esperti.cu` (383 righe) + `.cuh` (47): l'anello di
transito degli esperti, il PREDECESSORE della cache-esperti. Slab in VRAM,
testa che avanza sui miss, nessuna politica di sfratto: era lo strumento per
misurare la curva di riuso "senza politica" (piano in `ANELLO.md`). La riga 3
del file lo dice da sola: `// Superato: cache-esperti.cu contiene l'anello
esperti corrente con sfratto clock.` [MISURATO]

- Leva: `LLAMA_RING` (spenta di default, `ring-esperti.cu:46-52`);
  `LLAMA_RING_PROFONDITA` default 380 (`:54-63`); `LLAMA_RING_BATTITO` 60 s.
- Nessuno script del repo lo accende; tre lo mettono esplicitamente a `0`
  (`braccio_bussate.ps1:46`, `braccio_fusione_cure.ps1:48`,
  `braccio_scudo.ps1:49`); la produzione (`braccio_verdetto.ps1`) non lo tocca.
  [MISURATO]
- Il piano di misura di `ANELLO.md` (spazzata profondita' 6..380) **non risulta
  mai eseguito**: nessun log `ring-esperti:` in cassa, nessun braccio_*.ps1 che
  imposti `LLAMA_RING=1`. Le domande a cui doveva rispondere (quanta VRAM per
  quanto riuso) hanno avuto risposta dalla curva di capienza della
  cache-esperti. [MISURATO sull'assenza]

## Il difetto noto: stato di processo, chiave senza modello

**Dove**: `ring-esperti.cu:27-31` (`g_ring`, `g_reg`, `g_attivo` statici di
processo), `:95-111` (`ggml_cuda_ring_registra`: la seconda registrazione della
stessa coppia strato/tensore viene SCARTATA, `:104-106`), `:213-215`
(`ring_chiave = (strato<<16)|esperto`, senza identita' di modello);
`ggml-cuda.cu:2101-2146` (il bivio ring in `ggml_cuda_mul_mat_id` viene provato
PRIMA della cache per-istanza, e il `return` a `:2143` la rende
irraggiungibile), `:5469-5472` (registrazione anche da `supports_op`).

**Cosa succede**: bersaglio e bozza hanno pesi distinti ma gli stessi nomi
logici `blk.N.ffn_*_exps`. Il registro globale conserva solo la PRIMA base
vista per chiave; slab e tag sono unici nel processo. Con due modelli con terne
mappate e `LLAMA_RING=1`, il modello registrato per secondo esegue la MMVQ
sulle basi, sullo slab e perfino sui tag residenti dell'altro: pesi del modello
sbagliato, corruzione silenziosa dell'uscita. Documentato tre volte:
`audit/08-runtime-per-contesto.md` ("L'anello globale del bersaglio intercetta
il runtime per-istanza della bozza", peso alto), `audit/09-registro-terne.md:33`
(peso alto), `audit/20-leve-trasversale.md:110` (peso alto). [MISURATO, statico]

**Perche' oggi e' ARMATO e non teorico**: la configurazione due-cache — quella
del riferimento 10,47 t/s — mappa `blk.0` della bozza in `CUDA0_Mapped`
(`braccio_bozza.ps1:10-11`, bracci B/C) accanto ai 43 strati mappati del
bersaglio. E' esattamente la precondizione del difetto. Chi "risveglia" il ring
per una prova comparativa nella configurazione corrente ottiene un binario che
puo' rispondere con l'uscita contaminata — e nessun contatore lo dice.

**Come si falsifica**: statica gia' decisiva (nessun identificatore di
modello/runtime negli scrittori di `g_reg` e dei tag). A macchina libera, prova
da 10 minuti: asserzione temporanea in `ggml_cuda_ring_registra` che sul bit
gia' visto confronti `r.base[quale]` con `base`; un avvio con `LLAMA_RING=1` e
`blk.0` bozza mappato deve mostrare due basi diverse per la stessa chiave.

## Le quattro aggravanti (tutte spariscono con la cancellazione)

1. **Accendere il ring spegne la cache di produzione, in silenzio.**
   `ggml-cuda.cu:4797-4803`: con `LLAMA_RING` richiesto il bersaglio prende
   `ggml_cuda_ring_forse_init()` e l'init della cache-esperti sta nel ramo
   ELSE — non gira. `ANELLO.md:44-46` lo dichiara ("il percorso cache residente
   non viene inizializzato, anche se LLAMA_CACHE_ESPERTI_SLOT e' impostata"),
   ma nessun log all'avvio lo urla. Chi prova "ring + cache" misura in realta'
   "ring senza cache". Falsifica: avvio con entrambe le leve e grep del log:
   manca `cache-esperti: init`. [MISURATO, statico]
2. **Leva contaminata**: il ring ammette il batch con
   `ggml_cuda_cache_esperti_batch_max(ctx.cache_esperti)` (`ggml-cuda.cu:2110`
   → `cache-esperti.cu:212-228`, legge `LLAMA_CACHE_ESPERTI_BATCH`): una leva
   della cache governa il sottosistema che la esclude. Null-safe (runtime nullo
   → default 8) ma semanticamente falso. Gia' in `audit/20:308`. [MISURATO]
3. **`__trap()` come guardia di replay** (`ring-esperti.cu:231-235`): se un
   CUDA graph catturato viene riprodotto con `n_id` oltre la profondita', il
   kernel scrive `guasti`, poi `__trap()` — che uccide l'INTERO contesto CUDA
   del processo, bozza e KV comprese. Scelta dichiarata (`ANELLO.md:52-55`,
   preferita alla corruzione), ma resta un abort non recuperabile dentro un
   percorso "sperimentale" raggiungibile da una sola variabile d'ambiente.
   [MISURATO]
4. **Contatore che mente**: `static int ultimo_strato_contato`
   (`ggml-cuda.cu:2119-2121`) e' statico DI FUNZIONE, condiviso fra tutte le
   istanze backend: con due modelli nel ring il `conta` campiona a caso.
   Coerente col resto del difetto: stato di processo dove serve stato per
   istanza. [MISURATO]

## Verdetto: cancellare. La lista dei tagli

Risvegliarlo richiederebbe: stato per-istanza, chiave con identita' del
modello, leva batch propria, guardia di replay non distruttiva. Cioe' la
cache-esperti, che esiste, e' misurata, ed e' SOTA. Un sottosistema morto con
un bug armato dentro la configurazione di produzione e' un costo senza
contropartita.

Tagli precisi (tutto raggiungibile solo da `LLAMA_RING`, quindi a leva assente
il comportamento non puo' cambiare):

| Dove | Cosa |
|---|---|
| `ggml/src/ggml-cuda/ring-esperti.cu` + `.cuh` | interi (430 righe) |
| `ggml-cuda.cu:46` | `#include "ring-esperti.cuh"` |
| `ggml-cuda.cu:2020-2024` | in `should_fuse`: togliere `ggml_cuda_ring_percorso_gpu() \|\|` dalla condizione |
| `ggml-cuda.cu:2097-2146` | il bivio ring intero in `ggml_cuda_mul_mat_id` |
| `ggml-cuda.cu:4797-4803` | l'if/else: resta SOLO il ramo cache, incondizionato. ATTENZIONE a non toccare `:4805-4807` (`ggml_cuda_kv_ring_init`, sottosistema DIVERSO) |
| `ggml-cuda.cu:4811-4824` | pubblicazione `n_tok` del ring |
| `ggml-cuda.cu:5469-5476` | registrazione in `supports_op` + `ring_ammesso`; semplificare `cache_ammessa` a `:5477` (cade il `!ggml_cuda_ring_richiesto()`) |
| `ANELLO.md` | spostare in `docs/` come archivio o cancellare (la storia sta in git) |
| `braccio_bussate.ps1:46`, `braccio_fusione_cure.ps1:48`, `braccio_scudo.ps1:49` | le righe `LLAMA_RING='0'` |

**Cancello di non-regressione** (mezz'ora): stesso binario prima/dopo con la
configurazione di produzione (`LLAMA_RING` assente), spec off e K=0 → SHA
identico e conteggio nodi identico. A leva assente ogni funzione tolta
restituiva gia' `false`; se lo SHA cambia, il taglio ha toccato altro e va
fermato. Poi `grep LLAMA_RING` nel worktree = zero risultati vivi.

---

# 2. reap - a cosa serviva, cosa e' diventato, cosa succede ad accenderlo

## A cosa serviva [MISURATO, reap.h:1-59 e REAP_CONFLITTI.md]

Residenza degli esperti guidata dal calore sul gradino **SSD<->RAM**, nato
quando il modello (80,76 GB) non entrava nei 64 GB di allora e la cache di
Windows sfrattava per recency un carico che rilegge il 90,3% degli accessi.
Tre meccanismi distinti nello stesso modulo (`common/reap.cpp`, 1.241 righe):

1. osservatore sul `MUL_MAT_ID` CPU + politica `LOCK`/`PREFETCH`
   (VirtualLock / PrefetchVirtualMemory sugli intervalli caldi);
2. `LLAMA_REAP_AMMISSIONE < 1`: maschera sul router PRIMA del top-k — modifica
   l'uscita;
3. `reap_fissa_working_set` (`LLAMA_REAP_WS_MIN_GB`): minimo vincolante al
   working set, indipendente da `LLAMA_REAP` (gira comunque, no-op a default 0,
   `reap.cpp:1022-1049`).

Ogni braccio lo spegne (`Remove-Item` / `SetEnvironmentVariable $null` /
`'0'`): tutti e tre i pattern sono sicuri perche' `reap_enabled` esige il
valore ESATTO `"1"` (`reap.cpp:44-53`). [MISURATO]

## Funziona ancora? No: il canale che osservava non esiste piu'

L'unico invocatore dell'osservatore e' il `MUL_MAT_ID` del backend CPU
(audit 19). Nel regime attuale:

- gli esperti del bersaglio stanno su `CUDA0_Mapped` e la MMVQ resta su GPU
  (cache o zero-copy): alla CPU arriva solo il ramo overlap, `K=2` id su 6,
  GIA' riordinati per residenza dalla partizione
  (`braccio_verdetto.ps1:59`, `cache-esperti.cu` kern_partiziona);
- la bozza DSpark in configurazione verdetto gira con
  `-otd 'ffn_*_exps=CPU'` (`braccio_verdetto.ps1:31,71`): i SUOI mul_mat_id
  CPU alimenterebbero l'osservatore.

Quindi la risposta alla domanda "funziona ancora?" e': **il meccanismo scatta,
ma osserva la cosa sbagliata due volte**. Non e' rotto nel senso di inerte; e'
rotto nel senso peggiore: produce numeri con l'aria di essere giusti.

## Cosa succede se qualcuno lo accende oggi [MISURATO, statico]

Con `LLAMA_REAP=1` sulla configurazione di produzione:

1. **La mappa del calore si riempie di dati misti**: gli strati 0-2 della bozza
   collidono con gli strati 0-2 del bersaglio nella stessa chiave
   `(strato<<32)|esperto` (`reap.cpp:203,375`, nessun id di modello); le
   geometrie hanno `GEO_MAX=4` basi per strato contro 3+3 necessarie: due basi
   scartate in silenzio (`reap.cpp:288-301`). Audit 19, peso alto, invariato.
2. **Il "rango" appreso e' un rango di residenza**, non di gating: il ramo CPU
   riceve gli id dopo `kern_partiziona` (non residenti prima), e il "CANCELLO
   DI VALIDITA'" del dump non puo' accorgersene (somma per colonne invariante
   per qualunque permutazione, `reap.cpp:1203-1224`). Audit 19, peso alto.
3. **Se qualcuno aggiunge `LLAMA_REAP_AMMISSIONE=0.25`**: la maschera DIVENTA
   pronta (i record della bozza fanno avanzare il tick) e viene applicata al
   routing del BERSAGLIO (`reap.cpp:1070-1076` stampa onestamente "questo
   cambia l'uscita"). Uscita alterata da una mappa avvelenata.
4. **`LOCK`/`PREFETCH` operano su memoria gia' pinnata**: i pesi oggi sono
   `cudaHostAlloc` (non-pageable per costruzione), non mmap del file come nel
   2/8. `VirtualLock` su pagine gia' bloccate e' ridondante; in piu' un lock
   fallito viene comunque marcato `bloccato=true` e mai ritentato
   (`reap.cpp:848-889,917`; audit 19, peso alto): la COPERTURA stampata puo'
   essere finta.
5. **Nei binari non-server** (`llama-cli`, esempi): `reap_install` parte da
   `common_context_params_to_llama` (`common/common.cpp:1621`), il join sta
   solo in `reap_dump`, chiamato solo da `tools/server/server.cpp:397` → il
   thread joinable mai joinato fa `std::terminate` all'uscita. Audit 19.

**Come si falsifica in blocco** (5 minuti a macchina libera): produzione +
`LLAMA_REAP=1` + `LLAMA_REAP_DUMP=reap.txt`, una richiesta corta, chiusura
ordinata. Atteso: la mappa contiene chiavi di strati 0-2 con volumi da bozza
(3 nodi x K record) e il conteggio bussate del bersaglio limitato a K=2 id per
strato — la prova diretta che l'osservatorio non vede il routing completo.

## Contatori che mentono (ereditati, confermati alle righe attuali)

- `GiB residenti` nel dump = **cumulativo mai decrementato**
  (`reap.cpp:919-922` somma, `:831-836` sblocca senza sottrarre,
  `:1131-1137` stampa come stato corrente);
- una selezione del router = **3 bussate** (nodi gate/up/down sullo stesso
  `ids`), quindi `LLAMA_REAP_SOGLIA=3` scatta alla prima selezione;
- `LLAMA_REAP_ISTERESI` default ACCESA impedisce l'ordinamento per massa del
  ramo `PREFETCH`, che finisce in ordine di `unordered_map` (audit 19): l'unico
  default acceso del modulo e' quello che ne invalida la modalita' superstite.

## Verdetto: cancellare l'osservatore e la politica, salvare 25 righe

- **Cancellare**: osservatore, consumatore, mappa, politica LOCK/PREFETCH,
  ammissione, dump — `common/reap.cpp` e `reap.h` salvo la funzione sotto, piu'
  i call-site: `common/common.cpp:1618-1621`, `tools/server/server.cpp:397`,
  il gancio `ggml_cpu_set_moe_ids_observer` in ggml-cpu e (secondo taglio,
  opzionale) l'infrastruttura `moe_admit_provider` in llama.h/llama-graph se
  nessun altro la usa. La ragione fisica del modulo e' morta: con 96 GB e
  modello pinnato non esiste piu' un gradino SSD<->RAM da governare. Le
  falsificazioni storiche (90,3% riletture, LRU zero colpi) vivono nei ledger,
  non servono 1.200 righe vive per ricordarle.
- **Salvare**: `reap_fissa_working_set` + `LLAMA_REAP_WS_MIN_GB`
  (`reap.cpp:1022-1044`, `reap.h:84-98`) — l'unico pezzo con un incidente reale
  alle spalle (4/8: 36 GB sfrattati in 7 secondi dal trimmer) e costo zero a
  default. Nota onesta: anche la sua superficie e' ridotta (la massa pinnata
  non e' trimmabile), ma protegge cio' che resta pageable e sono 25 righe.
  Spostarla in un file suo (`common/working-set.cpp`) cosi' il nome `reap`
  sparisce dal codice vivo.
- **Cancello di non-regressione**: build senza il modulo, avvio produzione:
  l'unico diff atteso nel log e' l'assenza della riga `reap:`; SHA invariato
  (il modulo a leva spenta non tocca il calcolo).

`REAP_CONFLITTI.md` resta valido come documento storico dell'ipotesi
"ammissione a monte della cache" — che se mai tornasse va reimplementata con
una sorgente id indipendente dalla partizione, come quel documento gia'
conclude (":32-34").

---

# 3. kv-ring - vivo: il bilancio della memoria pinnata, riga per riga

Prima una correzione al mandato, a cui ho il permesso esplicito: che il
backing sia RAM pinnata mappata **era scritto** — `KV_RING.md:55-61`
("backing completo nel buffer type CUDA mapped"), `:74` ("legge il backing
pinned mapped"), `:172-175` (stessi flag `cudaHostAllocMapped|Portable` degli
esperti). Quello che NESSUNO aveva scritto e' il **bilancio**: quanta pinnata
consuma il processo intero, chi altro attinge allo stesso tetto, e che a
contesto lungo il vincolo di sistema non e' piu' la VRAM ma il pin. Su questo
il mandato ha ragione, e i reperti stanno qui sotto.

## 3.1 Il bilancio misurato, e il GiB che nessuno contava

Dal log di produzione piu' recente in cassa
(`scudo_gate_on_w2.server.log`, 9/8, contesto 10k) [MISURATO]:

| Voce | Buffer | MiB | Natura |
|---|---|---:|---|
| pesi esperti bersaglio | `CUDA0_Mapped model` | 74.304,00 | pinnata (cudaHostAlloc, `ggml-cuda.cu:1357-1404`) |
| **pesi non offloadati** | **`CUDA_Host model`** | **1.010,00** | **pinnata (cudaMallocHost)** |
| backing kv-ring CSA+HCA+LID | `CUDA0_Mapped KV` | 52,50+5,00+13,12 | pinnata, cresce con ctx |
| output (logits) | `CUDA_Host output` | 0,49 | pinnata |
| compute del backend CPU | `CUDA_Host compute` | 3,41 | pinnata |
| densi bersaglio | `CUDA0 model` | 7.383,67 | VRAM |
| prefissi caldi ring + KV grezza | `CUDA0 KV` | 18,12+10,75 | VRAM |
| VRAM libera dopo il load | | 3.709 | |

**Il reperto**: `CUDA_Host model buffer = 1.010 MiB`. Non e' del kv-ring: e' il
comportamento di DEFAULT del loader — `llama-model.cpp:887-901` inserisce il
buffer host pinned del primo device CUDA nella lista dei buft per i pesi, e i
tensori non offloadati (token_embd e compagnia) finiscono li' invece che in RAM
pageable. Un GiB che conta contro il tetto del pin e che in tre settimane di
conti VRAM/RAM non e' mai comparso in un bilancio. La leva esiste gia':
`--no-host` (`common/arg.cpp:2203-2206`) sposta quei tensori su `CPU` pageable.

**L'aritmetica della morte a 104k** [DEDOTTO dai numeri di casa]:

```
tetto del pin:        fra 74,7 e 76,9 GiB (misura di casa: 74,7 passa, 76,9 no)
                      = fra 76.492 e 78.746 MiB
bersaglio mappato     74.304 MiB
pesi CUDA_Host         1.010 MiB
backing kv-ring 104k    ~689 MiB   (6,6 MiB / 1000 tk, KV_RING.md:12-19)
output+compute host       ~4 MiB
                      -------
                      76.007 MiB   gia' impegnati
bozza mappata          2.224 MiB   -> totale 78.231 MiB = 76,4 GiB: nella banda
                                      in cui il caricamento muore. Quadra.
con --no-host:        77.221 MiB = 75,4 GiB -> sotto il punto di morte noto,
                                      sopra il punto che passa: FORSE entra.
```

**Come si falsifica** (braccio da 20 minuti, quando la macchina e' libera):
configurazione 104k identica a quella morta + `--no-host`. Se carica, il GiB
era la differenza; misurare poi il prefill (quei tensori ora viaggiano da RAM
pageable: atteso un costo piccolo sul prompt, nullo sul decode servito dalla
GPU). Se muore ancora, il tetto reale e' sotto 75,4 GiB e il conto sopra
stringe il vero limite a meno di 1,4 GiB dal totale senza bozza. Attenzione
all'unita' (regola di casa): il log stampa MiB, il tetto e' in GiB — 74.304 MiB
sono 72,6 GiB, non "74,3".

Nota di igiene sui numeri del mandato: "il modello ne usa 74,3" coincide con
74.304 MiB letti col separatore sbagliato. Il consumo pinnato del solo modello
e' 72,6 GiB + 1,0 GiB di `CUDA_Host` = 73,6 GiB: il resto fino al tetto lo
mangiano bozza e backing. La sostanza del mandato non cambia; le cifre nei
prossimi conti si'.

## 3.2 La scelta del buffer E' parametrizzabile senza riscrivere

**Dove**: `src/llama-kv-cache-dsv4.cpp:236-246` (`dsv4_kv_ring_buft`), oggi:
chiede `ggml_backend_cuda_mapped_buffer_type_for_device` via proc-address e
lancia `LLAMA_KV_RING cannot allocate CUDA-mapped DSV4 storage` se manca.

**Perche' bastano ~10 righe** [MISURATO, statico]:

- il costruttore accetta gia' un callback per-layer: `ring_buft` e' una
  `layer_buft_cb` passata alle tre cache backing (`:1244-1247`, `:1252-1273`);
- i kernel sono agnostici: `store_rows_kernel` e `materialize_all_kernel`
  ricevono puntatori device qualunque (`kv-ring.cu:57-104`) — con un backing in
  VRAM funzionano identici, byte per byte;
- `supports_op` non controlla il buft delle due op, solo i tipi F16/F32
  (`ggml-cuda.cu:5613-5620`);
- il salvataggio/ripristino passa dal backing "autorevole" via
  `get_tensor`/`set_tensor` del buffer, che esistono per ogni buft.

La patch: `LLAMA_KV_RING_BUFT=mapped|vram` (default `mapped`) dentro
`dsv4_kv_ring_buft`, ramo `vram` = `ggml_backend_dev_buffer_type(dev)`.
Due avvertenze da scrivere nel commit:

1. con `vram` l'anello NON salva piu' VRAM (torna il costo ∝ ctx che l'anello
   e' nato per togliere: a 102k, 687 MiB e 390 MiB liberi, `KV_RING.md:158`).
   La leva serve come A/B pulito (stesso grafo, solo il buft cambia) e come via
   d'uscita su GPU piu' grandi o contesti medi dove il vincolo e' il PIN e non
   la VRAM — esattamente il regime scoperto oggi;
2. i contatori si chiamerebbero col nome sbagliato: `h2d_copies`/`bytes_h2d`
   (`kv-ring.cu:10-16`, `:250-253`) contano le righe fredde lette dal backing —
   con backing in VRAM sarebbero letture D2D. Rinominare o annotare nel dump.

**Come si falsifica**: braccio A/B con `LLAMA_KV_RING_BUFT` nei due valori,
stesso seme: SHA identico atteso (stessi kernel, stessi byte), VRAM libera
-676 MiB e pinnata -676 MiB nel ramo `vram` a 102k. Se lo SHA cambia, i kernel
non erano agnostici e la patch si ferma.

## 3.3 Contatori e log del kv-ring: tre bugie piccole e una omissione grossa

1. **L'omissione**: `KV ring resident allocated: ... total = 18.12 MiB`
   (`llama-kv-cache-dsv4.cpp:1355-1369`) somma SOLO i prefissi caldi in VRAM.
   Nessuna riga gemella per il backing pinnato — cioe' per l'unico consumo che
   oggi decide se il carico entra. Patch da 3 righe nello stesso blocco:
   sommare `memory_breakdown()` dei tre backing e stampare
   `KV ring pinned backing = X MiB`. Falsifica: il numero deve coincidere con
   la somma delle tre righe `CUDA0_Mapped KV buffer size` gia' nel log.
2. **Gate congelato nell'istanza ma riletto vivo dal backend**: costruttore a
   `llama-kv-cache-dsv4.cpp:1235` contro `getenv` per chiamata in
   `kv-ring.cu:114-117` e `ggml-cuda.cu:4805,5614,5619` (audit 15, righe
   aggiornate). Innocuo per gli script attuali che non mutano l'ambiente;
   resta una doppia autorita' sullo stesso nome.
3. **`LLAMA_KV_RING=0` accende il log SHA del server**:
   `server-context.cpp:2151` testa la PRESENZA (`getenv("LLAMA_KV_RING")`), non
   il valore — documentato (`KV_RING.md:115-120`) e voluto per gli A/B, ma e'
   la terza semantica di accensione nel repo (reap: solo `"1"`; ring/kv-ring
   runtime: `!=0`; server: presenza). Chi confronta "assente" contro "=1" ha
   l'hashing solo nel braccio B: i due bracci differiscono di DUE cose. Igiene:
   negli A/B impostare sempre `0` esplicito nel braccio di controllo (gli
   script attuali lo fanno gia', per caso o per lezione).
4. **`tokens` parte tardi** sui primi 3 token (audit 15, invariato:
   l'addebito avviene solo in `ggml_cuda_kv_ring_materialize`,
   `kv-ring.cu:250-253`): `bytes_h2d_per_token` sovrastima sui contesti
   cortissimi. Peso basso, gia' a verbale.

## 3.4 Il costo strutturale da non dimenticare (non e' un difetto, e' il patto)

Ogni forward, per ogni strato compresso, `materialize()` ricostruisce sul
device l'INTERO prefisso visibile leggendo le righe fredde dal backing pinnato
via PCIe (`deepseek4.cpp:635-638, 745, 812`;
`llama-kv-cache-dsv4.cpp:2147-2167`; `kv-ring.cu:85-104`): il traffico per
token cresce linearmente col contesto, e `bytes_h2d_per_token` del profilo e'
la misura giusta. `KV_RING.md:81-83` lo dichiara: la gather top-k e' il "passo
2" mai costruito. Se il decode a contesto lungo rallenta oltre il previsto, il
primo indiziato e' questo numero, non la capienza. [MISURATO nel disegno;
il valore a 104k va letto dal profilo della prossima corsa lunga]

---

# 4. Trasversale: leve, default, configurazioni morte

- **Default vivi solo dentro sottosistemi morti** — muoiono coi tagli:
  `LLAMA_RING_PROFONDITA=380`, `LLAMA_RING_BATTITO=60`,
  `LLAMA_REAP_ISTERESI` accesa (l'unico default acceso di reap, e invalida il
  suo stesso prefetch), `LLAMA_REAP_SOGLIA=3` (= una selezione, per l'unita'
  tripla delle bussate).
- **Nessuna leva dei tre sottosistemi e' accesa di default nel senso proprio**:
  `LLAMA_RING`, `LLAMA_REAP`, `LLAMA_KV_RING` sono tutte opt-in. Le accensioni
  improprie sono di SEMANTICA (presenza vs valore) e di ADIACENZA (una leva che
  governa il sottosistema dell'altro): entrambe censite sopra.
- **Codice raggiungibile solo da configurazioni che non usiamo piu'**: il ramo
  ring dentro `supports_op` vive dentro il blocco `LLAMA_MAPPED_IBRIDO`
  (`ggml-cuda.cu:5458-5482`) — l'ibrido E' produzione (`braccio_verdetto:49`),
  quindi il contenitore e' vivo e il taglio deve rimuovere solo le righe ring
  (`5469-5476`), non il blocco. Il resto del codice-solo-per-config-morte
  coincide coi due sottosistemi da cancellare, ed e' la risposta piu' pulita:
  non annotarlo, toglierlo.

# Chiusura

Il mandato chiedeva cosa si possa togliere, per la prima volta in tre
settimane di sole aggiunte. Risposta: **~1.650 righe subito** (ring-esperti
430, reap ~1.220 salvo 25) piu' quattro agganci nel cammino caldo, con due
cancelli di non-regressione da mezz'ora l'uno e nessuna perdita di capacita'
di misura — tutto cio' che quei sottosistemi dovevano misurare o e' gia' stato
misurato meglio dalla cache-esperti, o vive nei ledger. Sul kv-ring, vivo, il
lavoro non e' togliere ma CONTARE: una riga di log per il backing pinnato, il
braccio `--no-host` per il GiB nascosto, e la leva buft da 10 righe come A/B.
La coda aperta vera del kv-ring resta il passo 2 (gather), e il suo metro e'
gia' nel profilo.
