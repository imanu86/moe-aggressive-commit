# P2 — Esecutore CPU e durata degli oggetti

Versione 1.0, 14 settembre 2026. Fase **P2** del [piano CPU/GPU](../PIANO_CPU_GPU_14_SETTEMBRE.md); il planner con cui questo esecutore deve combaciare è in [P1](../P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md); misure e criteri nel [protocollo](../PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md); decisioni D02, D03, D07, D09 nel [registro](../REGISTRO_CPU_GPU_14_SETTEMBRE.md).

Questo documento **progetta**. Non è una patch del motore, non contiene misure di velocità nuove e **non è stato compilato**: la compilazione è una fase separata. Le righe citate sono quelle lette il 14 settembre nell'albero sperimentale `C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source`, che questa fase **non modifica**, e nel prototipo `C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\freetoken_hybrid`. Prima di scrivere codice nel motore si riverifica il manifest: una riga spostata invalida i riferimenti, non il contratto.

Il codice sorgente prodotto è in [`src/`](src/); la prova host-only è [`src/test_esecutore.cpp`](src/test_esecutore.cpp); lo script di compilazione è [`build_test.cmd`](build_test.cmd) e **non va eseguito** finché la misura di baseline occupa la macchina.

---

## 1. Perimetro

P2 definisce **chi possiede il pool CPU, come gli si consegna un lavoro, come si scopre se è andato bene, e quando gli oggetti muoiono**. Restano fuori: la partizione dei miss (P1), la forma del graph e i kernel nuovi (P3), la scelta di core e preset (P4), la semantica a due o tre token (P5), qualunque conclusione su token al secondo.

Il perimetro numerico è quello di P1: un token per passo, al massimo due esperti CPU per strato (D03), 47 strati con gate/up IQ2_S e down IQ4_NL, strato 2 escluso perché IQ3_S (D07). La struttura ammette `max_rows = 3` per non dover riscrivere il descrittore in P5, ma il valore operativo resta 1 fino a P4.

---

## 2. Il confine d'interfaccia minimo

Il piano chiede «il confine d'interfaccia più piccolo compatibile con i backend esistenti: il CUDA backend programma il graph; un contratto host possiede il pool e offre submit/wait/status». Il confine proposto ha **tre pezzi e nessun altro**.

| Pezzo | Dove vive | Cosa è |
|---|---|---|
| `moe_cpu_executor` | `src/` di libllama | La classe C++ che possiede pool, buffer e stato. Nessuna riga CUDA. |
| `struct ggml_moe_cpu_hooks` | `ggml/include/ggml-moe-cpu.h`, implementata in `ggml/src/ggml.c` | Una tabella C globale di ggml-base: un puntatore opaco, due callback `void(*)(void*)`, quattro puntatori device e quattro interi di forma. |
| Chiamate del backend | `ggml-cuda` | `cudaLaunchHostFunc(stream, hooks->submit, hooks->user)` e `... hooks->wait ...`; i kernel scrivono/leggono `hooks->job_dev`, `x_dev`, `y_dev`, `flags_dev`. |

**Perché questa forma e non un'altra.**

1. *L'esecutore deve stare dove c'è ggml-cpu.* L'aritmetica usa `ggml_get_type_traits_cpu(...)->vec_dot` e `->from_float` (`ggml/include/ggml-cpu.h:114-124`). `ggml-cuda` non linka `ggml-cpu` (`ggml/src/ggml-cuda/CMakeLists.txt:161-189`), libllama sì. Quindi l'esecutore è di libllama.
2. *Il backend CUDA non deve conoscere `llama_context`.* Una tabella globale in ggml-base è già il meccanismo usato per esattamente questo scopo: `ggml_set_moe_obs_callback` / `ggml_get_moe_obs_callback` (`ggml/include/ggml.h:357-362`, `ggml/src/ggml.c:252-265`), installata da `llama-moecache.cpp:399`. Il nuovo header è il suo calco. Nessuna invenzione.
3. *Nessun tipo CUDA attraversa il confine.* `ggml_moe_cpu_fn_t` è `void(*)(void*)`, cioè `cudaHostFn_t`: si passa a `cudaLaunchHostFunc` senza cast. I buffer sono `void *`.
4. *La lettura della struttura interna del backend fatta dal microbenchmark non diventa un'API.* La sonda leggeva `ggml_backend_cuda_context::streams` per ottenere lo stream (`overlap_probe.cu:146-147`). Qui il backend non espone nulla: è lui a chiamare, sul proprio stream, con le proprie regole.
5. *Nessuna disattivazione globale dei CUDA graph.* `_putenv_s("GGML_CUDA_DISABLE_GRAPHS","1")` in `overlap_probe.cu:193` serviva alla cattura esterna della sonda ed è **estraneo** a questo progetto. I nodi host sono catturabili: `cudaLaunchHostFunc` durante una cattura diventa un nodo host del graph, e la sonda lo ha già dimostrato catturando l'intero blocco (`overlap_probe.cu:164`).

Una sola installazione della tabella per processo. `ggml_moe_cpu_set_hooks` restituisce `false` se una è già attiva: il percorso a domanda richiede già `n_seq_max == 1` (`llama-context.cpp:111-113`) e il contesto MTP azzera gli slot della cache (`llama-context.cpp:98-100`), quindi «un solo pool per contesto» (D09) e «un solo pool per processo» coincidono nel perimetro attuale. Se un giorno non coincideranno, la seconda installazione deve fallire in modo rumoroso, non sovrascrivere.

---

## 3. Il contratto host

`moe_cpu_executor` ([`src/moe_cpu_executor.h`](src/moe_cpu_executor.h)).

### 3.1 Creazione e distruzione

```
static std::unique_ptr<moe_cpu_executor> create(const moe_cpu_caps &,
                                                std::unique_ptr<moe_cpu_host_memory>,
                                                std::string * err);
~moe_cpu_executor();
```

`moe_cpu_caps` dichiara `n_embd`, `n_ff_exp`, i tre tipi, `max_rows`, `max_per_row`, `n_threads`, `wait_timeout_us`, `spin_us`. La creazione **fallisce con un messaggio** se un tipo non ha tratti CPU, se gate e up non condividono il `vec_dot_type`, se `n_ff_exp` non è multiplo del blocco dell'attivazione di `down`, se i processori fisici consentiti sono meno dei thread richiesti, o se il fornitore di memoria fallisce. Non esiste un percorso «crea comunque e fallisci dopo».

Il fornitore di memoria è iniettato, non scelto dall'esecutore: `moe_cpu_host_memory_plain()` (malloc, per il test host-only) oppure `moe_cpu_host_memory_cuda_mapped(device)` (per il server). Così l'esecutore non contiene una riga di CUDA e la prova di parità gira senza GPU.

`register_layer(layer, bank)` registra i **puntatori host originali** di uno strato. È idempotente per lo stesso strato con gli stessi puntatori; un puntatore cambiato è un **errore**, non un aggiornamento silenzioso: significherebbe che la memoria è stata riallocata sotto un graph già catturato.

### 3.2 Consegna di un lavoro

Il piano CPU nasce **sul dispositivo**: è il kernel del planner a decidere quali richieste vanno alla CPU (P1 §4.2, passo 5). Quindi il job non può essere consegnato dall'host al momento dell'accodamento: viene **scritto dal dispositivo in memoria host mappata** e l'host viene svegliato da un nodo host.

Il descrittore è `struct moe_cpu_job` ([`src/moe_cpu_job.h`](src/moe_cpu_job.h)), POD e includibile da `.cu`:

| Campo | Chi lo scrive | Significato |
|---|---|---|
| `magic`, `abi` | kernel di export | riconoscimento e versione; un valore sbagliato rifiuta il job |
| `layer` | kernel di export | indice di strato registrato; è così che un solo slot serve 48 strati |
| `n_rows` | kernel di export | token del passo, 1 in P3/P4, fino a 3 in P5 |
| `n_embd`, `n_ff_exp` | kernel di export | controllo di forma ridondante, a costo zero |
| `n_routes[row]` | kernel di export | route CPU di quel token, 0..`cpu_max` |
| `expert[...]` | kernel di export | **ID logico** dell'esperto, non lo slot (P1 §3.1) |
| `weight[...]` | kernel di export | peso **originale** della route, già normalizzato e scalato (`llama-graph.cpp:2089-2107`) |

Un job è quindi esattamente la terna di P1 §4.7 — `(token, esperto logico, peso originale)` — moltiplicata per il numero di route. I **pesi trasferiti** si deduplicano per esperto; il **calcolo** no: con `n_rows > 1` lo stesso esperto su due token genera due route e due calcoli (invariante 5).

L'attivazione sta in un buffer separato `x` (`float[max_rows * n_embd]`), anch'esso mappato, scritto dal kernel di export. Il risultato sta in `y` (stessa forma), scritto dal pool e **letto dal dispositivo in zero-copy**: nessuna copia H2D (§9).

### 3.3 Submit, wait, status, cancel

```
static void submit_hook(void * user);   // nodo host CUDA: pubblica e sveglia
static void wait_hook  (void * user);   // nodo host CUDA: attende con scadenza
uint64_t      submitted() / completed() / failures();
moe_cpu_state state(uint64_t generation);
uint64_t      first_failed_generation();   bool contaminated();
void          cancel();  void rearm();
bool          quiesce(uint64_t timeout_us, std::string * err);
void          set_phase(moe_cpu_phase);
```

`submit_hook` e `wait_hook` sono **le uniche due funzioni chiamabili da un nodo host**. Tutto il resto si chiama dal thread proprietario, fuori da una cattura.

**Generazione e stato.** Ogni job accettato dal coordinatore prende una generazione (contatore monotono). Lo stato è conservato in un anello di 64 voci: `state(g)` restituisce `ok`/`rejected`/`cancelled`/`timeout`/`stopped`/`running`, oppure `unknown` se la generazione è uscita dalla finestra. In più c'è un flag **appiccicoso** `contaminated()` con la prima generazione fallita: è quello che `llama_context::decode()` deve interrogare, perché in un passo di decode ci sono fino a 47 job e non si vuole controllarne 47 stati.

**Ownership seriale.** Un solo job in volo. `submit_hook` fa `in_flight.exchange(1)`: se trova 1, il job è **rifiutato** e l'attesa viene sbloccata subito. Una seconda submit senza wait non viene accodata e non viene serializzata: è un errore di programma e deve emergere come tale. Dentro un job, il **coordinatore** è il proprietario seriale di `flat`, `xq`, `hq`, `x`, `y`: nessun altro thread li tocca fuori dalle due fasi delimitate dalle barriere.

**Un solo pool per contesto.** L'esecutore è un membro di `llama_context`. Gli strati sono seriali sullo stesso stream, quindi lo strato `il+1` non può pubblicare prima che il `wait` dello strato `il` sia ritornato: **un solo slot di job serve tutti e 48 gli strati**. Niente pool per strato (D09).

### 3.4 Attesa inattiva

Il prototipo attendeva attivamente e «occupa core CPU anche fra i job» (`README.md:42-43`): inaccettabile nel server, dove fra un token e l'altro e per tutta la durata del prefill quei core servono ad altro.

L'attesa è a due livelli e **senza mutex**:

- **giro breve** (`spin_us`, proposta 60 µs) solo in fase `decode`, che è l'unico regime in cui la latenza di risveglio conta;
- **blocco vero** con `WaitOnAddress` / `WakeByAddressAll`, risolte a caldo da `api-ms-win-core-synch-l1-2-0.dll`. Non passano da un lock dell'utente e non hanno risvegli persi: il confronto col valore atteso lo fa il sistema al momento dell'attesa. Se l'API non si risolve si degrada a `Sleep(1)`, che consuma comunque quasi zero CPU.

`set_phase(prefill)` e `set_phase(idle)` fanno saltare del tutto il giro breve: il pool va a dormire immediatamente. Il risveglio è sempre corretto perché `block_until_changed` è armato sul valore atteso.

La scelta di non usare mai un mutex in questo percorso rende l'**invariante 6 vero per costruzione**, non per revisione: non c'è nessun lock che il thread in attesa del graph possa trattenere, perché non c'è nessun lock.

---

## 4. Che cosa cambia rispetto al prototipo

`fused_cpu.hpp` è la base dell'aritmetica e non viene toccata nella sostanza: stessi tratti, stesso `vec_dot`, stessa quantizzazione, stesse piastrelle (32 righe per gate/up, 16 per down), stessa somma senza atomiche. È l'aritmetica che il 13 settembre è risultata **bit-identica al riferimento GGML** sui casi verificati.

| Punto | Prototipo | P2 | Perché |
|---|---|---|---|
| Proprietario seriale | il thread chiamante crea, usa e distrugge il pool, ed **è** il worker 0 (`fused_cpu.hpp:60`, `167`) | il proprietario seriale è un **coordinatore interno**; il thread che crea non viene né affinizzato né usato per calcolare | il chiamante nel server è il thread di callback del driver: non si può affinizzare né caricare di lavoro |
| Affinità | il costruttore pinna anche il thread chiamante (`fused_cpu.hpp:134`) | ogni thread del pool pinna **sé stesso**; il thread del server resta libero | pinnare il thread principale del server è un effetto collaterale inaccettabile |
| Attesa | giro attivo con `yield` ogni 20 000 pause (`fused_cpu.hpp:120-123`) | giro breve + blocco vero, con fase | D09: il pool non deve rubare core in prefill |
| Errori | `throw std::runtime_error` da `run()` (`fused_cpu.hpp:158-160`) | stato per job; nessuna eccezione attraversa un nodo host | un'eccezione in una callback del driver termina il processo |
| Scadenza | `std::abort()` dopo 10 s (`overlap_probe.cu:28`) | `MOE_CPU_RESULT_TIMEOUT`, veleno, ritorno | un server non aborta |
| Insieme vuoto | `run(n=0)` **azzera** l'uscita (`fused_cpu.hpp:163`) | zero route è un esito **valido** con contributo nullo; un job **rifiutato** invece non tocca `y` | distinzione fra «il contributo corretto è zero» e «non c'è risultato» (invariante 7) |
| Forme | costanti `K=2560, H=640, EMAX=10` (`fused_cpu.hpp:17`) | forme da `caps`, controllate a ogni job | lo stesso codice deve poter servire lo strato 2 in una estensione futura |
| Annullamento | assente | `cancel()` / `rearm()` / `quiesce()` | serve al cambio di fase, al rollback e alla distruzione |

---

## 5. Durata degli oggetti e ordine di distruzione

La regola: **i buffer e il loro proprietario vivono fino al completamento degli utilizzatori CPU e GPU e alla distruzione dei graph che li referenziano** (invariante 6). Tradotta in punti del codice:

```
llama_context::reserve()            (llama-context.cpp:626-645)
  synchronize()                     ← già presente, riga 628
  executor->set_phase(prefill|idle) ← NUOVO
  executor->quiesce(...)            ← NUOVO: nessun job in volo
  ggml_backend_cuda_reset_transient_memory(...)   riga 634-636
      cudaDeviceSynchronize(); ctx->cuda_graphs.clear(); pools.reset()   (ggml-cuda.cu:3666-3676)
  llama_moe_cache_set_device_active(...)          riga 640
```

`reset_transient_memory` è **il punto in cui i graph muoiono** ed è già un punto di sincronizzazione del dispositivo. Il `quiesce` va *prima*, non dopo: dopo `cudaDeviceSynchronize()` nessun nodo host può più partire, ma un job potrebbe essere ancora in esecuzione se un `wait` è scaduto.

```
llama_context::~llama_context()     (llama-context.cpp:496-498)
  synchronize()
  executor->set_phase(idle); executor->quiesce(...); ggml_moe_cpu_set_hooks(nullptr)   ← NUOVO
  ... distruzione dei membri in ordine inverso di dichiarazione ...
```

**Ordine di dichiarazione dei membri.** L'esecutore va dichiarato in `llama-context.h` **prima** di `sched` (riga 344), perché i membri si distruggono in ordine inverso: così lo scheduler e i backend — che possiedono i `cudaGraphExec` — muoiono **prima** dell'esecutore e dei suoi buffer mappati. L'ordine sbagliato è un difetto silenzioso che si manifesta solo alla chiusura, quindi va messo per iscritto qui e verificato in revisione.

**Incarnazioni della cache.** P1 §5, invariante 7, dice che un job fallito dopo il gather richiede di buttare l'incarnazione: il gather può avere già sovrascritto uno slot mentre la mappatura, differita, dichiara ancora residente il vecchio esperto. Il recupero è quindi: `cancel()` → decode fallito → `unbind`/`bind` dell'incarnazione (`moe-demand.cuh:142-157`, la via che `llama_moe_cache_set_device_active(false)` già percorre). L'esecutore non conosce la cache: espone `contaminated()` e il chiamante decide.

**Registrazione degli strati.** `register_layer` va rifatta dopo ogni `bind`, perché una nuova incarnazione può avere nuovi puntatori di destinazione; i puntatori **sorgente** host non cambiano (sono i pesi del modello), ed è proprio per questo che un puntatore sorgente cambiato viene rifiutato come errore.

---

## 6. Buffer persistenti: tabella delle allocazioni

Tutto è allocato **una volta** alla creazione dell'esecutore, in **un solo blocco** mappato più due vettori host-privati, e liberato alla distruzione. Non c'è nessuna allocazione per strato, per replay, per cattura o per job. La prova T11 verifica che `allocated_bytes()` non cambi dopo una serie di job.

Byte teorici con K = 2560, H = 640 (`vec_dot_type` di IQ2_S = Q8_K, blocco 256; di IQ4_NL = Q8_0, blocco 32):

| Buffer | Formula | P3/P4 (`max_rows`=1, `cpu_max`=2) | P5 (`max_rows`=3) | Mappato | Quando |
|---|---|---:|---:|---|---|
| `job` (descrittore) | `sizeof(moe_cpu_job)` arrotondato a 64 | 192 B | 192 B | sì | creazione → distruzione |
| `flags` | 4 celle da 64 B | 256 B | 256 B | sì | creazione → distruzione |
| `x` attivazione | `max_rows * K * 4` | 10 240 B | 30 720 B | sì | creazione → distruzione |
| `y` contributo CPU | `max_rows * K * 4` | 10 240 B | 30 720 B | sì | creazione → distruzione |
| `xq` attivazione quantizzata | `max_rows * row(Q8_K, 2560)` = `max_rows * 2 920` | 2 920 B | 8 760 B | no | creazione → distruzione |
| `hq` nascosto quantizzato | `max_rows * cpu_max * row(Q8_0, 640)` = `... * 680` | 1 360 B | 4 080 B | no | creazione → distruzione |
| **Totale** | | **25 208 B** (24,6 KiB) | **74 728 B** (73,0 KiB) | | |

A parte: `n_threads` stack di thread (riserva di 1 MiB ciascuno su Windows, impegno effettivo molto minore) e l'anello di 64 stati (1,5 KiB).

**Pesi degli esperti: zero byte nuovi.** 1 971 200 byte per esperto sui 47 strati supportati e 2 329 600 sullo strato 2 restano dove sono, nella RAM pinnata e mappata già allocata dal modello. P2 non ne alloca, non ne copia, non ne duplica (§7).

Il piano chiede esplicitamente di non nascondere una nuova allocazione riducendo gli slot della cache o il margine del prefill: con 25 KiB il problema non si pone, e **questo è un risultato del progetto, non un dettaglio** — il costo di memoria dell'esecutore è irrilevante rispetto ai 2,9 GB di VRAM che valgono l'11% sulla curva degli slot. I picchi misurati e il confronto con staging/rollback a 131k appartengono a P6.

---

## 7. I pesi host originali: dove stanno e come si ottengono i puntatori

I pesi degli esperti dei layer offloadati vivono in un buffer **`CUDA<n>_Mapped`**: `cudaHostAlloc(size, cudaHostAllocMapped | cudaHostAllocPortable)` seguito da `cudaHostGetDevicePointer` (`ggml-cuda.cu:1447-1477`). È la stessa memoria che la GPU legge in zero-copy sul PCIe e che il gather copia negli slot.

La cache esperti li espone già, per strato, come tensori sorgente: `llama_moe_cache_layer::{gate_src, up_src, down_src}` (`src/llama-moecache.h:38-46`, riempiti in `llama-moecache.cpp:269-271`), raggiungibili da un tensore del modello con `llama_moe_cache_lookup(up_exps)` (`llama-moecache.h`, implementata in `llama-moecache.cpp:469-474`). Sono gli stessi tre tensori che `bind` valida come «memoria host mappata» (`moe-demand.cuh:85-95`).

**Il difetto da non commettere.** Per un tensore di quel buffer, `tensor->data` è l'indirizzo **DEVICE**, perché `get_base` restituisce `ctx->dev` (`ggml-cuda.cu:1372-1375`). Su x86-64 host e device coincidono (UVA: il log di `ggml-cuda.cu:1469-1471` lo stampa), ma il codice **non deve dipenderne**. L'indirizzo host si ottiene solo da:

```c
const void * ggml_cuda_mapped_tensor_host_ptr(const ggml_tensor * tensor, size_t offset);   // ggml-cuda.cu:1387
```

Il puntatore del singolo esperto è aritmetica di passo, senza nessuna copia:

```
gate_host(e) = ggml_cuda_mapped_tensor_host_ptr(gate_src, 0) + e * gate_src->nb[2]
up_host(e)   = ggml_cuda_mapped_tensor_host_ptr(up_src,   0) + e * up_src->nb[2]
down_host(e) = ggml_cuda_mapped_tensor_host_ptr(down_src, 0) + e * down_src->nb[2]
```

con, per i 47 strati supportati, `gate_src->nb[2] = up_src->nb[2] = row(IQ2_S, 2560) * 640 = 820 * 640 = 524 800` e `down_src->nb[2] = row(IQ4_NL, 640) * 2560 = 360 * 2560 = 921 600`, somma **1 971 200 byte per esperto**: esattamente il numero verificato dal prototipo. `register_layer` controlla questi tre passi contro le forme dichiarate e rifiuta un banco incoerente.

Se un giorno i pesi finissero in un buffer host pinnato ordinario invece che mappato (`ggml_backend_cuda_host_buffer_type`, `ggml-cuda.cu:1285`), `ggml_cuda_mapped_tensor_host_ptr` restituirebbe `nullptr` e `tensor->data` sarebbe già l'indirizzo host: P3 deve provare prima la funzione e poi il ripiego `ggml_backend_buffer_is_host(t->buffer) ? t->data : nullptr`, e **fallire** se nessuno dei due risponde, invece di dereferenziare un puntatore device.

**Da fare in P3:** `ggml_cuda_mapped_tensor_host_ptr` non è dichiarata in nessun header pubblico e non è nella tabella dei proc-address (`ggml-cuda.cu:6015-6030`). Va aggiunta lì, come `ggml_backend_cuda_moe_demand_unbind` (usata via proc-address da `llama-moecache.cpp:461-466`). Senza quella voce l'esecutore non si crea.

---

## 8. Quantizzazione delle attivazioni

Il kernel CPU consuma i pesi **nel formato originale** e l'attivazione nel `vec_dot_type` del peso. Nessuna requantizzazione dei pesi, mai.

| Passo | Tipo del peso | `vec_dot_type` | Quantizzatore | Quante volte |
|---|---|---|---|---|
| gate, up | IQ2_S | Q8_K (blocco 256) | `ggml_get_type_traits_cpu(IQ2_S)->vec_dot_type` → `from_float` su tutta la riga di `n_embd` | **una per token**, condivisa da tutte le route CPU di quel token |
| down | IQ4_NL | Q8_0 (blocco 32) | `ggml_get_type_traits_cpu(IQ4_NL)->vec_dot_type` → `from_float` su 32 elementi | una per piastrella di 32 righe di `n_ff_exp`, per ogni route |

Il prodotto è `ggml_type_traits_cpu::vec_dot(n, &s, 0, riga_del_peso, 0, attivazione_quantizzata, 0, 1)` — la stessa firma e la stessa funzione che usa `mul_mat_id` sul backend CPU. Da qui viene l'identità bit a bit col riferimento GGML misurata dal prototipo.

La quantizzazione a blocchi dello stato nascosto è la ragione per cui **la piastrella di 32 righe possiede il proprio blocco**: i blocchi Q8_0 sono indipendenti, quindi produrre `hidden[0..31]` e quantizzarlo subito dà lo stesso risultato bit a bit di quantizzare tutta la riga da 640 alla fine. Non è un'approssimazione: è la proprietà che permette il parallelismo senza perdere la parità.

Il vincolo generale è `n_ff_exp % blocco(vec_dot_type(down)) == 0` e `n_embd % blocco(vec_dot_type(gate)) == 0`, controllato alla creazione. Con 640 e 2560 vale per Q8_0 e Q8_K; vale anche per IQ3_S dello strato 2, il cui `vec_dot_type` è Q8_K: l'estensione a quello strato è quindi **una questione di politica (D07), non di codice**, e va decisa in una fase separata.

`CPU e CUDA quantizzano diversamente l'attivazione`: il contributo CPU non sarà mai bit-identico al percorso interamente GPU. Il prototipo misura NRMSE peggiore per attivazione ≈ 0,0084, e il candidato tre miss/due CPU ≈ 0,0063. La soglia 0,05 del banco rileva errori grossolani e **non è un criterio di qualità del modello**: la qualità la stabilisce il protocollo, in P6.

---

## 9. Barriere e ordine con lo stream CUDA

### 9.1 La scelta: callback, non flag del driver, e memoria mappata, non copie

La griglia del 13 settembre ha esplorato due assi indipendenti. I numeri sono microsecondi per invocazione, mediana di 80 gruppi da 16 invocazioni, sei core ([`communication_grid.json`](../../../Documents/Codex/2026-09-13/rip/work/freetoken_hybrid/communication_grid.json), tabella del [rapporto](../FREETOKEN_IBRIDO_13_SETTEMBRE.md)):

| miss / CPU | comm 1: mappata + flag driver | comm 2: mappata + callback | vantaggio della callback |
|---|---:|---:|---:|
| 1 / 1 | 184,5 | **163,9** | 11,2% |
| 2 / 1 | 272,6 | **248,3** | 8,9% |
| 2 / 2 | 232,2 | **184,5** | 20,5% |
| 3 / 1 | 348,4 | **324,5** | 6,9% |
| 3 / 2 | 270,9 | **255,2** | 5,8% |
| 3 / 3 | 293,5 | **247,1** | 15,8% |

La callback vince in **ogni** cella della griglia. E sull'asse del trasporto, a tre miss / due CPU / sei core, con baseline 337,2:

| Percorso | Tempo |
|---|---:|
| copie esplicite + flag driver | 387,7 µs |
| RAM mappata + flag driver | 279,2 µs |
| copie esplicite + callback | 308,1 µs |
| **RAM mappata + callback, lavoro concorrente** | **253,5 µs** |
| RAM mappata + callback, CPU completata prima della GPU | 339,5 µs |

Entrambe le scelte sono confermate separatamente: la memoria mappata batte le copie a parità di segnalazione (279,2 contro 387,7; 253,5 contro 308,1) e la callback batte il flag a parità di trasporto (253,5 contro 279,2; 308,1 contro 387,7). È la conferma di **D02**. L'ultima riga ricorda che il vantaggio non viene dal trasporto più leggero ma dalla **concorrenza**: se la CPU finisce prima che la GPU cominci, il guadagno sparisce.

Quindi: **nodi host `cudaLaunchHostFunc` per segnalare in entrambe le direzioni, memoria mappata per i dati, nessuna copia D2H/H2D nel percorso critico.**

`cuStreamWriteValue64`/`cuStreamWaitValue64` sono scartate anche per una seconda ragione, che non è di prestazioni: un'attesa a flag sul dispositivo non ha un modo pulito di essere annullata dall'host, e la sonda infatti si appoggiava a un watchdog esterno (`README.md:35-38`). Un nodo host, invece, è codice nostro: può scadere, marcare e ritornare.

### 9.2 L'ordine esatto sullo stream

```
   ... plan kernel (moe_grouped_plan_decode)          — decide quali route vanno alla CPU
   moe_cpu_export<<<...>>>                            — scrive job header + x in memoria mappata;
                                                        termina con __threadfence_system()
   cudaLaunchHostFunc(stream, hooks->submit, user)    — alza request, sveglia il pool
   moe_grouped_gather_decode<<<...>>>                 — i soli miss GPU
   mul_mat_id gate/up, SiLU, mul_mat_id down          — lavoro GPU, CONCORRENTE alla CPU
   pesatura e riduzione → moe_out
   cudaLaunchHostFunc(stream, hooks->wait, user)      — attende done, con scadenza
   add: moe_out += y                                  — legge y in zero-copy
   ... shared expert
```

Le tre proprietà da cui dipende la correttezza:

1. **Visibilità.** Il nodo host `submit` è accodato dopo il kernel di export sullo stesso stream: quando la callback parte, il kernel è concluso e le sue scritture in memoria host mappata sono visibili alla CPU. Il `__threadfence_system()` in coda al kernel è comunque richiesto e va scritto, non dedotto.
2. **Serialità.** `submit` → lavoro GPU → `wait` sono ordinati sullo stream. Lo strato `il+1` non può pubblicare prima che il `wait` dello strato `il` sia ritornato: **un solo slot di job è sufficiente e sicuro**. È l'argomento che consente la tabella delle allocazioni di §6.
3. **Concorrenza.** Fra `submit` e `wait` c'è tutto il lavoro GPU dello strato. È esattamente la configurazione «lavoro concorrente» da 253,5 µs, e non quella «CPU completata prima» da 339,5. Se in P3 il `wait` finisse accodato troppo presto, il guadagno sparirebbe senza che nulla sbagli: è la prima cosa da controllare se la misura non torna.

`QWEN_MOE_OVERLAP_DOWN` usa un secondo stream per il gather di `down` (`moe-demand.cuh:240-268`) con eventi `gate_ready`/`down_ready`. I nodi host restano **tutti sullo stream di calcolo**: non interagiscono con lo stream di trasferimento e non ne toccano gli eventi.

### 9.3 Che cosa fanno, e non fanno, le due callback

`submit_hook`: `in_flight.exchange`, quattro store rilasciate su celle mappate, un `WakeByAddressAll`. Nessuna API CUDA, nessun mutex, nessuna allocazione, nessuna eccezione, ritorno in decine di nanosecondi.

`wait_hook`: giro breve su `done`, poi `WaitOnAddress` con risvegli da 1 ms, fino a `wait_timeout_us`. Alla scadenza marca `timeout`, alza il veleno e **ritorna**. Nessuna API CUDA, nessun mutex, nessun `abort`.

Il fatto che anche il thread di callback del driver blocchi invece di girare a vuoto è voluto: quel thread è condiviso e girare a vuoto per millisecondi ruberebbe un core proprio mentre la CPU sta calcolando.

### 9.4 Perché non un evento CUDA per il completamento

Registrare un evento dal thread del pool richiederebbe `cudaEventRecord` **dentro** codice che può girare durante una cattura, e violerebbe la regola «nessuna API CUDA nelle callback» in senso stretto. Il flag mappato più il nodo host ottiene lo stesso effetto senza toccare il driver dal lato CPU, ed è la variante che la misura preferisce. Scartato per regola, non solo per numeri.

---

## 10. Il punto di somma del contributo CPU

Il punto è fissato da P1 §3.10 e §4.6: **`moe_out`, dopo la pesatura delle righe e la loro riduzione, prima del ritorno di `build_moe_ffn`** (`llama-graph.cpp:2373-2404`) e quindi prima dello shared expert (`qwen4exp.cpp:1484`). Il contributo CPU **non** passa una seconda volta per la moltiplicazione dei pesi: il peso originale è già dentro, applicato dal pool nella fase 2.

**Come ci arriva: memoria mappata letta da un kernel di somma, non una copia H2D.** Concretamente, la forma più piccola compatibile con il graph esistente è un semplice `ggml_add`:

```
moe_out = ggml_add(ctx0, moe_out, vista_di_y);
```

dove `vista_di_y` è un tensore F32 `[n_embd, n_tokens]` creato **una volta per contesto** sopra il buffer mappato `y` dell'esecutore. `y` è già dal lato device un indirizzo valido (`hooks->y_dev`), quindi il kernel `add` della GPU lo legge in zero-copy: 10 KiB sul PCIe per strato, contro i ~1,9 MiB per esperto che il gather non fa più.

Questo nodo `add` fa anche da **marcatore**: quando il backend CUDA incontra il nodo il cui `src[1]` è il tensore dell'esecutore, accoda prima `cudaLaunchHostFunc(wait)`. Nessun operatore ggml nuovo, nessun cambio di topologia oltre a un `add` per strato, e il punto di attesa è esattamente dove deve stare.

Il veleno: se `flags->poison` vale 1, il kernel di somma non deve sommare `y`. La raccomandazione è che scriva **NaN** nelle righe interessate. Non è un capriccio: l'alternativa «somma zero» produrrebbe silenziosamente un risultato *plausibile e sbagliato*, ed è esattamente ciò che l'invariante 7 vieta. Il NaN è una seconda cintura: la prima è che `llama_context::decode()` interroga `contaminated()` e **fallisce il decode**. La scelta finale dello schema di veleno è una decisione di P3, con la raccomandazione argomentata qui.

Resta a carico di P3, dal contratto P1: verificare che le fusioni CUDA della riduzione (`ggml_cuda_match_moe_weighted_reduction`, `ggml-cuda.cu:3719-3727`) consumino il tensore dei **pesi mascherati** e non quello originale, e che l'`add` del contributo CPU non venga assorbito da una fusione che lo scavalca.

---

## 11. Errori, annullamento, chiusura

**Un errore invalida la richiesta; non si restituiscono zeri.** Tre casi distinti, con tre comportamenti distinti:

| Caso | Esito | `y` | Veleno | Che cosa deve fare il chiamante |
|---|---|---|---|---|
| Nessuna route CPU in questo passo | `ok` | azzerato | no | niente: zero **è** il contributo corretto |
| Header non valido (magic, strato non registrato, esperto fuori dai limiti, peso o attivazione non finiti, `n_rows`/`n_routes` fuori dai limiti) | `rejected` | **non toccato** | sì | fallire il decode; l'incarnazione va buttata se il gather ha già scritto |
| Scadenza del `wait`, oppure `cancel()` | `timeout` / `cancelled` | **non toccato** | sì | idem |

Il **fallback si sceglie prima dell'invio**, come prescrive l'invariante 7: lo strato 2 (IQ3_S, D07) e qualunque strato non registrato non generano job, perché il planner non produce route CPU per loro (`n_idonei = 0` in P1 §4.3 dà un piano identico a `cpu_max = 0`). Il rifiuto dell'esecutore è la **seconda** rete, non la prima.

**Annullamento.** `cancel()` non interrompe un job in volo. La durata di un job è di decine di microsecondi: interromperlo a metà richiederebbe di controllare una bandiera dentro le barriere, con una classe di stalli in cambio di nulla. `cancel()` invece: marca lo stato, avvelena, sblocca un `wait` in corso, e **rifiuta ogni pubblicazione successiva** finché non si chiama `rearm()`. È la semantica giusta per un rollback speculativo o un cambio di fase: quello che conta è che nessun risultato dubbio venga consumato e che nessun thread resti appeso.

**Chiusura senza stallo.** `~impl` alza `stopping`, sveglia il coordinatore alzando `request` e i worker incrementando `work`, e fa `join` di tutti. Il coordinatore, prima di uscire, pubblica `done = 1` una volta: se un `wait` era già accodato, si sblocca invece di scadere. I buffer si liberano dopo il `join`, e il `join` avviene dopo la distruzione dei graph per via dell'ordine dei membri di `llama_context` (§5).

**Nessuna disattivazione globale dei CUDA graph.** Non si tocca `GGML_CUDA_DISABLE_GRAPHS`. Il `_putenv_s` della sonda (`overlap_probe.cu:193`) serviva a evitare una cattura annidata nel processo di prova ed è estraneo al server.

---

## 12. Cattura, replay e puntatori stabili

Il backend cattura il graph quando le proprietà dei nodi sono stabili per due chiamate consecutive (`ggml-cuda.cu:4723-4745`), e confronta a ogni chiamata `ggml_tensor` e puntatori dei sorgenti (`ggml_cuda_graph_update_required`, `ggml-cuda.cu:2824-2864`). La regola del progetto — «ingressi di grafo: solo puntatori stabili» — si traduce qui in tre obblighi:

1. **I quattro indirizzi device dell'esecutore non cambiano mai** fra creazione e distruzione. Un solo blocco, suddiviso una volta, mai riallocato. È la ragione per cui `allocate` è chiamata una volta sola e per cui `register_layer` rifiuta un puntatore cambiato.
2. **Il tensore `vista_di_y` è creato una volta per contesto** e riusato da tutti gli strati. Se fosse creato per strato o per replay, `node_props` cambierebbe e il graph verrebbe ricatturato a ogni passo: si pagherebbe la tassa di ricattura del grafo a ogni token.
3. **I nodi host non hanno parametri che cambiano.** `hooks->user` è l'esecutore e non cambia; la variabilità sta tutta nel **contenuto** della memoria mappata, che i nodi host non descrivono. Perciò `cudaGraphExecUpdate` non ha nulla da aggiornare e il graph si riusa.

Il corollario positivo: `n_cpu` può variare da un token all'altro **senza cambiare la forma del graph**. È il motivo per cui un job con zero route deve essere legale (§11): la topologia è fissa, la variabilità è nei dati.

Il corollario da misurare: i nodi host restano nel graph anche quando `n_cpu = 0`, quindi **`submit` e `wait` costano qualcosa anche a CPU spenta**. Il piano lo elenca già fra i rischi aperti («costo delle righe GPU fittizie e callback quando CPU=0», P3/P4). Le due callback in quel caso sono due store e un confronto, ma il costo di un nodo host in un graph non è zero e va misurato, non stimato.

---

## 13. Come si prova ogni punto

| # | Punto del progetto | Prova | Dove |
|---|---|---|---|
| 1 | Parità col riferimento CPU sui casi supportati | catena `mul_mat_id` del backend CPU GGML contro `y` dell'esecutore, una route a peso 1; NRMSE ≤ 1e-6, atteso **zero diversi** | T1 |
| 2 | La somma pesata rispetta i pesi originali | due route con pesi, confronto col riferimento sommato nello stesso ordine | T2 |
| 3 | La piastrellatura parallela non cambia il risultato | `reference_expert()` seriale a un thread contro il percorso a `n` thread; uguaglianza **esatta** | T3 |
| 4 | Zero route CPU è un esito valido, non un errore | `y` azzerato, stato `ok`, veleno 0 | T4 |
| 5 | Generazione e stato per job | la generazione cresce di uno per submit; `state(g)` corretto; `state(g+1000)` = `unknown`; `completed == submitted` dopo il wait | T5 |
| 6 | Un errore invalida la richiesta, niente zeri | sei header non validi: tutti `rejected`, tutti avvelenati, `y` conserva la sentinella `-12345` | T6 |
| 7 | Annullamento senza stallo, e riarmo | `cancel()` poi submit/wait: ritorna in meno di 200 ms, `y` intatto; dopo `rearm()` il pool torna a servire | T7 |
| 8 | Nessuna chiamata concorrente allo stesso pool | due `submit` senza `wait`: il secondo è rifiutato, l'attesa non stalla, `quiesce` riesce | T8 |
| 9 | Cambio di fase e distruzione senza stallo | `set_phase(prefill)` → `set_phase(idle)` → `quiesce` → distruzione cronometrata sotto i 2 s | T9 |
| 10 | Nessun riuso anticipato del buffer | otto job consecutivi con attivazioni diverse: ogni `y` combacia col **proprio** riferimento e differisce dal precedente | T10 |
| 11 | Buffer persistenti, nessuna crescita | `allocated_bytes()` invariato dopo l'intera batteria | T11 |
| 12 | Nessuna API CUDA né mutex nelle callback | controllo statico: nel corpo di `submit_hook`/`wait_hook` e in tutto ciò che chiamano non compaiono simboli `cuda*`/`cu*` né `std::mutex`/`lock_guard` (P1 §5, riga dell'invariante 6) | revisione + `grep` |
| 13 | Riuso dei pesi host senza duplicazione | `register_layer` confronta i tre passi con `row_size * forma` e rifiuta un banco incoerente; nel server, controllo che i puntatori registrati siano esattamente `ggml_cuda_mapped_tensor_host_ptr(*_src, 0)` | T6 (passi) + P3 |
| 14 | Ordine con lo stream e concorrenza reale | P3: confronto del tempo di blocco fra `wait` accodato dopo il lavoro GPU e `wait` accodato subito dopo `submit` — deve riprodurre il divario 253,5 / 339,5 del prototipo | P3 |
| 15 | Cattura e replay con puntatori stabili | P3: contatore di ricatture del graph invariato su una corsa lunga; `cuda_graph_update_required` non deve scattare per colpa nostra | P3 |
| 16 | Costo a CPU spenta | P4: A/B fra `cpu_max = 0` con i nodi host presenti e la build senza la funzione | P4 |

I punti 1-11 girano **senza GPU e senza server**, con `build_test.cmd`. I punti 12-16 appartengono alla revisione e alle fasi successive: dichiararli qui serve a non scoprirli dopo.

---

## 14. File del motore da toccare in P3 (elenco, non patch)

| File | Righe | Intervento |
|---|---|---|
| `ggml/include/ggml-moe-cpu.h` | nuovo | copiare [`src/ggml-moe-cpu.h`](src/ggml-moe-cpu.h) |
| `ggml/src/ggml.c` | accanto a 252-265 | `g_moe_cpu_hooks` + `ggml_moe_cpu_set_hooks` / `ggml_moe_cpu_get_hooks`, calco di `ggml_set_moe_obs_callback` |
| `ggml/src/ggml-cuda/fork-moe-kernels.cuh` | 44-51, 53-64, 80-91 | campo `n_cpu`; array `UNIQUE_IS_CPU`, `CPU_UNIQUE`, `CPU_EXPERTS`; `moe_grouped_plan_size` ricalcolata (P1 §4.1) |
| | 217-254 | commit differito con tre insiemi distinti: mappatura solo miss GPU, recenza solo unici non CPU, frequenza tutti (P1 §4.2 passo 1) |
| | 430-436 | tre contatori invece di due |
| | 455-512 | assegnazione degli slot ai soli miss GPU |
| | 514-518 | la condizione di fallimento diventa «slot mancante **e** unico non CPU» |
| | 520-525 | `remapped_ids` scrive lo slot alias per le route CPU |
| `ggml/src/ggml-cuda/moe-demand.cuh` | 226-284 (`remap`) | nuovo kernel `moe_cpu_export` dopo il plan; `cudaLaunchHostFunc(stream, hooks->submit, hooks->user)`; il gather legge `n_misses` come soli miss GPU |
| | 190-195 | schema della traccia esteso con `misses_cpu` |
| | 200-224 (`report_hits`) | due percentuali distinte: colpi GPU e quota CPU |
| `ggml/src/ggml-cuda/moe-demand-api.cuh` | 5 | firma di `ggml_cuda_moe_demand_remap` estesa con l'attivazione `src1` |
| `ggml/src/ggml-cuda/mmvq.cu` | 1407 | passare `src1` a `remap`, perché il kernel di export possa leggere l'attivazione |
| `ggml/src/ggml-cuda/ggml-cuda.cu` | 3666-3676 | `reset_transient_memory`: quiesce dell'esecutore **prima** di `cuda_graphs.clear()` |
| | 4462-4645 (ciclo dei nodi) | riconoscere il nodo `add` del contributo CPU e accodare `cudaLaunchHostFunc(hooks->wait, ...)` prima; leggere `flags->poison` nel kernel di somma |
| | 6015-6030 | aggiungere `ggml_cuda_mapped_tensor_host_ptr` alla tabella dei proc-address |
| | 3719-3727, 4801 | verificare che la fusione della riduzione pesata consumi i pesi **mascherati** e non scavalchi l'`add` del contributo CPU |
| `src/llama-graph.cpp` | 2062-2110 | conservare ID e pesi originali; produrre il peso GPU mascherato |
| | 2366-2404 | dopo la riduzione: `moe_out = ggml_add(moe_out, vista_di_y)`, prima del `return` |
| `src/llama-context.h` | prima di 344 (`sched`) | membro `std::unique_ptr<moe_cpu_executor>`, dichiarato **prima** di `sched` |
| `src/llama-context.cpp` | 87-113 | creazione dell'esecutore e `ggml_moe_cpu_set_hooks` quando la funzione è accesa |
| | 496-498 | `~llama_context`: `set_phase(idle)`, `quiesce`, `ggml_moe_cpu_set_hooks(nullptr)` dopo `synchronize()` |
| | 626-645 | `reserve()`: `set_phase` e `quiesce` prima di `reset_transient_memory` |
| | 2124-2127 | fine di `decode()`: `set_phase(decode)`; se `contaminated()`, fallire il decode e invalidare l'incarnazione |
| `src/llama-moecache.h` / `.cpp` | 38-46, 269-271 | nessuna modifica strutturale: `*_src` sono già pubblici via `llama_moe_cache_lookup` |
| `src/CMakeLists.txt` | 11-40 (elenco sorgenti) | aggiungere `moe_cpu_executor.cpp` e `moe_cpu_host_memory_cuda.cpp` |

Le opzioni di controllo (abilitazione, elenco strati, massimo esperti CPU, core, diagnostica) si introducono e si documentano in P3, come stabilito dal piano. **Non esistono ancora flag CLI/env di questa integrazione** e questo documento non ne inventa.

---

## 15. Rischi che vedo

| # | Rischio | Perché è credibile | Come lo si scopre presto |
|---|---|---|---|
| R1 | Un nodo host che blocca lo stream occupa un thread di callback del driver, condiviso con altro lavoro | il `wait` blocca per la durata del calcolo CPU, 48 volte per token | misurare il tempo di parete del decode con `cpu_max = 0` e i nodi host presenti (punto 16 di §13) prima di credere a qualunque guadagno |
| R2 | Il `wait` finisce accodato troppo presto e la concorrenza sparisce | è successo nel prototipo, ed è la riga da 339,5 µs contro 253,5 | punto 14 di §13, da fare come **prima** misura di P3, non come ultima |
| R3 | La fusione della riduzione pesata scavalca o assorbe l'`add` del contributo CPU | `ggml_cuda_try_fuse` riconosce sequenze di `MUL`+`ADD` (`ggml-cuda.cu:3276`, `3719-3727`, `4801`) | controllo numerico del `moe_out` contro il percorso interamente GPU in modalità diagnostica, prima della modalità attiva |
| R4 | I pesi host finiscono in un buffer pinnato non mappato e `ggml_cuda_mapped_tensor_host_ptr` restituisce `nullptr` | dipende da `-ot` e da `--no-mmap`; `bind` già aborta con un messaggio esplicito (`llama-moecache.cpp:367`) | `register_layer` fallisce alla creazione, con messaggio; mai un puntatore device dereferenziato |
| R5 | Ordine di distruzione sbagliato: l'esecutore muore prima dei graph che referenziano `y` | dipende dall'ordine di dichiarazione dei membri, invisibile alla lettura | §5 esplicita l'ordine; il difetto si manifesta solo alla chiusura, quindi va messo in revisione, non nel test |
| R6 | `WaitOnAddress` non risolvibile e il ripiego `Sleep(1)` aggiunge fino a 1 ms di latenza di risveglio | ambiente Windows non standard | l'esecutore dovrebbe registrare quale percorso ha scelto; P4 confronta le due latenze |
| R7 | Contesa fra i thread del pool e il threadpool del server (banda RAM e core) | il piano la elenca già per P4 | confronto quattro/sei core alla cadenza reale del server, non al banco a 16 invocazioni |
| R8 | Un secondo contesto tenta di installare i hook e la tabella globale non lo rifiuta | oggi `n_seq_max == 1` lo rende improbabile, domani no | `ggml_moe_cpu_set_hooks` deve restituire `false`, e il chiamante deve trattarlo come errore di configurazione |
| R9 | La scadenza del `wait` è troppo corta e produce falsi fallimenti sotto carico | 2 s è una proposta, non una misura | rendere `wait_timeout_us` un parametro e registrare ogni scadenza nel registro; una sola scadenza in una corsa è un difetto da investigare, non da tollerare |
| R10 | L'aritmetica CPU/GPU diversa cambia il testo generato | il prototipo lo dice: CPU e CUDA quantizzano diversamente | è previsto dal protocollo per P3-P6; qui serve solo non pretendere l'identità del testo come criterio |

---

## 16. Voce di registro (bozza da riportare nel registro)

**Data e fase.** 14 settembre 2026, **P2 — Esecutore e durata degli oggetti**. Progettazione e scrittura del codice sorgente; nessuna compilazione, nessun binario, nessun server, nessuna GPU usata: sulla macchina girava una misura di baseline.

**Ipotesi.** Il prototipo del 13 settembre può essere portato dietro un contratto host esplicito senza perdere l'aritmetica bit-identica, aggiungendo proprietà seriale, buffer persistenti, generazione/stato, attesa inattiva, errore, annullamento e chiusura, e senza che il backend CUDA debba conoscere `llama_context` né che libllama debba linkare ggml-cuda.

**ID della modifica/revisione.** P2-v1.0. Nessun file del motore toccato; nessun file sotto `qwen38_clean\source` né sotto `Documents\Codex` modificato.

**File prodotti** (tutti sotto `docs/porto/p2_esecutore/`):

| File | Contenuto |
|---|---|
| `PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md` | questo documento |
| `src/ggml-moe-cpu.h` | tabella C dei hook, calco di `ggml_set_moe_obs_callback` |
| `src/moe_cpu_job.h` | descrittore POD condiviso host/dispositivo |
| `src/moe_cpu_host_memory.h` | astrazione del fornitore di buffer mappati |
| `src/moe_cpu_host_memory_plain.cpp` | fornitore malloc, per il test host-only |
| `src/moe_cpu_host_memory_cuda.cpp` | fornitore `CUDA<n>_Mapped` via proc-address |
| `src/moe_cpu_executor.h` | il contratto host |
| `src/moe_cpu_executor.cpp` | implementazione: pool, quantizzazione, barriere, stati |
| `src/test_esecutore.cpp` | undici prove host-only (T1-T11) |
| `build_test.cmd`, `build_test.ps1` | compilazione con lo stesso metodo di `freetoken_hybrid/build.cmd` |

**Configurazioni confrontate.** Nessuna: non sono state eseguite misure. I numeri citati (griglia della comunicazione, 253,5 contro 279,2 contro 308,1 contro 387,7 µs) sono **riletture delle prove del 13 settembre**, non risultati nuovi.

**Risultato e limite.** Consegna di progetto e sorgenti. Limite dichiarato: **nulla di tutto questo è stato compilato**. La struttura interna è argomentata e coerente con i sorgenti letti, ma errori di compilazione, firme cambiate e simboli non esportati sono tutti ancora possibili.

**Cosa resta da verificare in compilazione.**
1. che `ggml-cpu.lib`, `ggml-base.lib` e `ggml.lib` della build privata bastino al test (nessun simbolo CUDA richiesto);
2. che `ggml_quantize_chunk` accetti IQ2_S con una matrice di importanza di soli uno (altrimenti il test gira solo con `--weights` e i `.bin` del prototipo);
3. che `WaitOnAddress`/`WakeByAddressAll` si risolvano su questa macchina, e con quale percorso;
4. che la parità col riferimento GGML sia davvero **bit a bit** e non solo entro 1e-6, come lo era nel prototipo;
5. che la batteria T1-T11 passi con quattro e con sei thread;
6. che `ggml_cuda_mapped_tensor_host_ptr` sia effettivamente esportata dalla DLL (oggi non è in tabella: va aggiunta in P3).

**Decisione.** Proseguire. Il confine d'interfaccia proposto è il più piccolo che soddisfi i vincoli letti nei sorgenti: una tabella C in ggml-base, due callback, quattro puntatori. Le due scelte di comunicazione (memoria mappata, nodi host) sono confermate separatamente dai dati del 13 settembre e coincidono con D02.

**Regressioni aperte.** Nessuna: non è stato modificato nulla di eseguibile.

**Stato dei processi avviati.** Nessuno. La misura di baseline dell'utente non è stata toccata.

**Prossima azione.** Nella fase di compilazione concordata: eseguire `build_test.cmd`, poi `test_esecutore.exe --threads 4` e `--threads 6`, poi `--full`, poi `--weights` con i `.bin` del prototipo. Correggere ciò che emerge e registrare l'esito qui. Solo dopo aprire P3, iniziando dalla misura del rischio R2 (concorrenza reale fra `submit` e `wait`), che è la condizione di esistenza dell'intero guadagno.
