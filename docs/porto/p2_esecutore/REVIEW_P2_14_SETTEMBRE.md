# Revisione indipendente — P2 Esecutore CPU (14 settembre)

Revisore economico, sola lettura. Nessun sorgente modificato, nessuna compilazione, nessun processo lanciato. Verifica svolta leggendo `PIANO_CPU_GPU_14_SETTEMBRE.md`, `P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md`, `p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md` e tutti i file in `p2_esecutore/src/`, con riscontro diretto sull'albero `C:\Users\imanu\Documents\Codex\2026-09-09\...\qwen38_clean\source` (stato attuale su disco, 14 settembre).

**Sintesi anticipata:** l'interfaccia (tre pezzi, tabella C, callback) è ben motivata e i riferimenti a riga sono quasi tutti esatti. Ma ho trovato un difetto di correttezza reale e non banale nella gestione di `cancel()`/scadenza del `wait`, che rompe esattamente l'invariante "un solo job in volo" su cui si regge tutto l'argomento di sicurezza della memoria (§B1), più un secondo difetto che rende **irreversibile** il primo annullamento di routine secondo il contratto che il progetto stesso descrive per `decode()` (§B2). Nessuno dei due è coperto da T1-T11. Ci sono anche due difetti di compilazione/collegamento concreti (§E).

---

## A. Verifica dei riferimenti file:riga

| Riferimento citato | Verificato | Nota |
|---|---|---|
| `ggml/src/ggml.c:252-265` (`ggml_set_moe_obs_callback`/`get`) | Sì | Corrisponde esattamente: `g_moe_obs_cb` a 252-253, `set` a 255-258, `get` a 260-265. |
| `ggml/include/ggml.h:357-362` | Sì | `ggml_moe_obs_cb_t` e le due dichiarazioni combaciano. |
| `src/llama-moecache.cpp:399` (installazione callback) | Sì | `if (!mc->demand_gpu) ggml_set_moe_obs_callback(moe_obs_cb, mc);` alla riga citata. |
| `src/llama-moecache.cpp:404-440` (`llama_moe_cache_set_device_active`) | Sì | Funzione e `unbind` via proc-address confermati; unbind a ~427. |
| `ggml-cuda.cu:1387` (`ggml_cuda_mapped_tensor_host_ptr`) | Sì | Definita esattamente lì. **Confermato anche**: non è nella tabella dei proc-address (vedi E1) — il progetto lo dichiara già come lavoro di P3, corretto. |
| `ggml-cuda.cu:1372-1375` (`get_base` → `ctx->dev`) | Sì (riga reale ~1372) | `ggml_backend_cuda_mapped_buffer_get_base` restituisce `ctx->dev`. |
| `ggml-cuda.cu:1447-1477` (`cudaHostAlloc`/`cudaHostGetDevicePointer`) | Sì | `ggml_backend_cuda_mapped_buffer_type_alloc_buffer`, righe reali ~1442-1480, stesso contenuto. |
| `ggml-cuda.cu:6015-6030` (tabella proc-address) | Sì, posizione reale ~5999-6035 | Tabella `strcmp` confermata; **ma il nome usato dal fornitore CUDA di P2 non è in questa tabella** (vedi E1). |
| `ggml-cuda.cu:3666` (`ggml_backend_cuda_reset_transient_memory`) | Sì, esatto | `cudaDeviceSynchronize(); cuda_graphs.clear(); pools.reset()` confermati. |
| `ggml-cuda.cu:3719-3727` e `4801` (fusione riduzione pesata) | Sì | `ggml_cuda_match_moe_weighted_reduction` al nodo `GGML_OP_MUL`, righe reali 3718-3727; dipendenze di allocazione a ~4801. |
| `ggml-cuda.cu:4462-4645` (ciclo di valutazione/cattura del grafo) | Sì | `ggml_cuda_graph_evaluate_and_capture` inizia esattamente a 4462. |
| `ggml/src/ggml-cuda/moe-demand-api.cuh:5` | Sì | Firma di `ggml_cuda_moe_demand_remap` a riga 5 esatta. |
| `ggml/src/ggml-cuda/mmvq.cu:1407` | Sì, esatto | `if (ids && ggml_cuda_moe_demand_remap(ctx, src0, ids, demand_ids, ...))`. |
| `moe-demand.cuh:62` (`bindings_mutex`) | Sì, esatto | |
| `moe-demand.cuh:70-140` (`bind`), `142-157` (`unbind`) | Sì, sostanzialmente | `bind` termina a ~133, `unbind` a ~156; scarto di poche righe, contenuto identico. |
| `moe-demand.cuh:226-284` (`remap`), `232` (`ids->ne[1]` in [1,3]) | Non riverificato riga per riga (file coerente, 291 righe totali; la sezione esiste nell'intervallo dichiarato) | Basso rischio: struttura del file compatibile con quanto descritto in P1. |
| `fork-moe-kernels.cuh:44-51`, `53-64` (struct piano, enum array) | Sì | Corrisponde: `moe_grouped_decode_plan` e `moe_grouped_plan_array_index`. |
| `fork-moe-kernels.cuh:217-254` (commit differito) | Sì, scarto di poche righe | Mappatura miss a ~218-232, frequenza/recenza a ~235-249; stesso contenuto descritto. |
| `llama-graph.cpp:2062-2110` (argsort, norm_w, w_scale) | Sì | `ggml_argsort_top_k` (~2064), blocco `norm_w` (~2089-2103), `w_scale` (~2104-2107). |
| `llama-graph.cpp:2366-2404` (pesatura, riduzione, `moe_out`) | Sì, esatto | `experts = ggml_mul(...)` e `return moe_out;` a riga 2404 **esatta**. |
| `qwen4exp.cpp:1446-1460`, `1484` | Sì, esatto | `moe_out = build_moe_ffn(...)` a 1446, `cur = ggml_add(ctx0, moe_out, ffn_shexp)` a 1484 **esatta**. |
| `src/llama-context.cpp:87-113` (costruttore, `n_seq_max==1`) | Sì | Condizione `cparams.n_seq_max == 1` presente nel calcolo di `demand_dynamic_workspace`. |
| `src/llama-context.cpp:496-498` (distruttore, `synchronize()`) | Sì | `~llama_context()` chiama `synchronize()` in apertura. |
| `src/llama-context.cpp:626-645` (`reserve()`, `reset_transient_memory`) | Sì | `synchronize()` a riga 628, proc-address `ggml_backend_cuda_reset_transient_memory` a ~634. |
| `src/llama-context.cpp:2124-2127` (fine `decode()`) | Sì, sostanzialmente | `llama_moe_cache_step()` poi `return 0;` a riga 2127. |
| `src/llama-context.h:344` (`sched`) | Sì, esatto | `ggml_backend_sched_ptr sched;` a riga 344. |
| `ggml_backend_cuda_moe_demand_unbind` via proc-address (§2 punto 2 del progetto) | Sì | Pattern confermato in `llama-moecache.cpp` e nella tabella di `ggml-cuda.cu`. |
| **`"ggml_backend_cuda_mapped_buffer_type"`** (usato in `moe_cpu_host_memory_cuda.cpp:53`) | **NO** | Il nome registrato in tabella è `"ggml_backend_cuda_mapped_buffer_type_for_device"` (`ggml-cuda.cu:6032-6033`), con **firma diversa**: prende un `ggml_backend_dev_t`, non un `int device`. Vedi difetto E1. |

Conclusione di A: quasi tutte le citazioni sono esatte o con scarto di poche righe (accettabile, dichiarato dal documento stesso come "istantanea del 14 settembre"). L'unica citazione effettivamente **sbagliata** è quella interna al codice sorgente di P2 (non del motore): il nome di proc-address per il buffer mappato in `moe_cpu_host_memory_cuda.cpp`.

---

## B. Invarianti 6 e 7: verifica concreta

**B1 — BLOCCA. `cancel()` e la scadenza del `wait` rilasciano `in_flight` senza attendere il vero completamento del coordinatore: rompono "un solo job in volo" e possono far leggere alla GPU un contributo sbagliato senza segnalarlo.**

File: `src/moe_cpu_executor.cpp:635-661` (`wait_hook`), `677-685` (`cancel`), `394-415` (`coordinator_loop`).

Il coordinatore è un thread dedicato che esegue, in sequenza e senza controlli intermedi: `validate_and_prepare()` → `compute()` (bloccante, sincronizzato da barriere con tutti i worker) → `publish()` (che scrive `flags_h->result/poison/done` e incrementa `n_completed`). `in_flight` viene rilasciato **solo** dentro `wait_hook`, quando osserva `done==1`.

Il problema: sia `cancel()` sia la scadenza dentro `wait_hook` (righe 643-652) scrivono `done=1` **direttamente**, senza alcuna sincronizzazione con lo stato reale del coordinatore. Se il coordinatore ha già superato `validate_and_prepare()` (risultato `ok`) ed è nel mezzo di `compute()` quando `cancel()`/il timeout intervengono:

1. Il `wait_hook` in corso (o quello successivo) vede `done==1` **prima** che il coordinatore abbia davvero finito, e rilascia `in_flight=0`.
2. Per l'ordinamento di stream, questo permette alla GPU di procedere: il nodo `add` legge (o salta, se avvelenato) `y`, poi si passa allo strato successivo, che accoda un **nuovo** `submit_hook`. Poiché `in_flight` è già 0, questo nuovo submit viene **accettato**, sovrascrivendo `flags_h` con `done=0, poison=0, result=running, request=1`.
3. Il coordinatore, che nel frattempo ha *davvero* finito di calcolare il job vecchio (ha solo terminato tardi, non è bloccato), chiama `publish(generation_vecchia, result_vecchio)`. Questo **sovrascrive di nuovo** `flags_h->done/poison/result` con l'esito del job vecchio — **prima ancora che il coordinatore stesso abbia iniziato a occuparsi della nuova richiesta**, perché `publish()` avviene nella stessa iterazione di loop, prima di tornare a leggere `request`.
4. Se il `wait_hook` del **nuovo** job (strato successivo) viene invocato in questa finestra, vede `done==1` con `result` del **job vecchio** (che potrebbe essere `ok`!) e conclude erroneamente che il nuovo job è già concluso — la GPU consumerebbe `y_h`, che a quel punto contiene ancora il contributo del job vecchio, **spacciandolo per il contributo del nuovo strato**. Questo è esattamente ciò che l'invariante 7 vieta: un risultato plausibile ma sbagliato, consumato senza segnalazione.

Un secondo effetto, più grave perché può causare un crash e non solo un risultato sbagliato: `register_layer()` (righe 585-608) è protetta solo da `in_flight.load()==0` prima di toccare `p_->layers` (un `unordered_map`). Se `in_flight` è stato rilasciato prematuramente come sopra, il thread proprietario può legittimamente chiamare `register_layer()` per un nuovo strato **mentre il coordinatore sta ancora leggendo `cur_bank` (un puntatore dentro la mappa) nelle fasi `phase_gate_up`/`phase_down` del job "vecchio"**. Un `emplace()` che causa un rehash invaliderebbe quel puntatore: riferimento pendente, comportamento indefinito.

Causa radice: `flags_h` (celle condivise, non taggate per generazione) viene scritto sia dai callback `submit_hook`/`wait_hook`/`cancel()` sia dal `publish()` del coordinatore, senza che nessuno verifichi "sto ancora pubblicando per il job che il chiamante si aspetta". Il campo `sequence` in `struct moe_cpu_job` (`moe_cpu_job.h:85`, "scritto dal dispositivo o 0") esiste già ma **non viene mai controllato** da `moe_cpu_executor.cpp`.

Proposta concreta: dare al coordinatore un modo di scoprire, **dopo** `compute()` e prima di `publish_flags()`, se questa generazione è stata superata (es. un contatore `superseded_generation` scritto da `cancel()`/dal ramo di scadenza di `wait_hook`, confrontato con la `generation` locale del coordinatore prima di toccare `flags_h`). Se superata, il coordinatore aggiorna solo l'anello (`record()`, per `state()`/`contaminated()`) e **non tocca** `flags_h`/`in_flight`. In alternativa più semplice: non rilasciare mai `in_flight` da `cancel()`/timeout finché il coordinatore non conferma davvero l'uscita da `compute()` per quella generazione (es. un `std::atomic<uint64_t> coordinator_gen_done` che il coordinatore incrementa a fine `compute()`, e che `wait_hook`/`cancel()` attendono con lo stesso limite di tempo prima di dichiarare `timeout`/`cancelled` in modo definitivo).

**B2 — BLOCCA. `contaminated()` è un flag appiccicoso senza alcun modo di azzerarlo, ma `cancel()` — usato per operazioni di routine (cambio di fase, rollback) — lo attiva. Il contratto descritto per `decode()` diventa irreversibile dal primo annullamento in poi.**

File: `src/moe_cpu_executor.h:121-129` (nessun metodo di reset/`ack`), `src/moe_cpu_executor.cpp:263-272` (`record`, incrementa `n_failed` e fissa `gen_first_failed` con un solo `compare_exchange_strong` da `UINT64_MAX`, mai più modificabile).

Il progetto stesso (§3.3, §14 riga `llama-context.cpp:2124-2127`) dice: "`llama_context::decode()`: fine di `decode()`: `set_phase(decode)`; se `contaminated()`, fallire il decode e invalidare l'incarnazione." Ma `cancel()` è anche il meccanismo per "rollback" e "cambio di fase" (§3.3, §11) — eventi che avvengono **regolarmente**, non solo in presenza di un guasto. Ogni `cancel()`/scadenza produce (tramite `record()`) uno stato diverso da `ok`, che marca `gen_first_failed` **una volta per sempre**: non esiste `un metodo `ack_failure()`/`reset_contamination()` che il chiamante possa invocare dopo aver gestito il recupero (unbind/bind dell'incarnazione, come descritto in §5). Risultato: al primo rollback speculativo o cambio di fase che intercetta un job in volo, `contaminated()` resta vero **per tutta la vita del processo**, e — se il chiamante segue alla lettera quanto descritto nel progetto — ogni `decode()` successivo fallirebbe.

Proposta concreta: aggiungere `void acknowledge_contamination()` (o un parametro a `rearm()`) che il chiamante invoca **dopo** aver eseguito `unbind`/`bind` dell'incarnazione, azzerando `gen_first_failed` a `UINT64_MAX`. Va documentato chi ha l'autorità di chiamarlo (solo il thread proprietario, mai da un nodo host).

**Altri controlli dell'invariante 6/7, esito positivo:**
- Nessun simbolo `cuda*`/`cu*` né `std::mutex`/`lock_guard` nel corpo di `submit_hook`/`wait_hook` (grep manuale su `moe_cpu_executor.cpp`): confermato.
- Un job rifiutato (`validate_and_prepare()` → `rejected`) non tocca mai `y_h`: confermato a livello di codice (il branch che chiama `compute()`/`memset` è condizionato a `result==ok`).
- L'attesa usa solo primitive senza lock utente (`WaitOnAddress`/`Sleep`), coerente con "invariante 6 vero per costruzione".

---

## C. Compatibilità con il contratto P1

| Requisito P1 | Stato | Nota |
|---|---|---|
| Il job porta token, esperto logico, peso originale | **Sì** | `moe_cpu_job::n_routes/expert/weight` (`moe_cpu_job.h:79-84`), riempiti per token (`row`). |
| Il contributo si somma una volta sola su `moe_out`, dopo pesatura/riduzione | **Sì, lato CPU** | `phase_down()`: `sum += flat[r].weight * value;` (`moe_cpu_executor.cpp:328`) applica il peso originale una sola volta, senza rinormalizzare. Il punto di innesto lato GPU (`ggml_add(moe_out, vista_di_y)`) è correttamente descritto ma appartiene a P3, non a questo codice: non verificabile qui. |
| Zero route CPU è un contributo valido, non un errore | **Sì** | `coordinator_loop()`: `memset(y_h, 0, ...)` con stato `ok`, non `rejected`. |
| Caso "job fallito dopo il gather" trova un aggancio (invalidazione dell'incarnazione) | **Parziale, difettoso** | `contaminated()`/`first_failed_generation()` segnalano il guasto, ma **B2** rende il segnale irreversibile: l'aggancio esiste per rilevare, non per **recuperare**. Il contratto P1 (§5, invariante 7) richiede un recupero completo tramite `unbind`/`bind`; l'esecutore, così com'è, non permette al chiamante di tornare in servizio dopo. |
| Deduplica dei pesi trasferiti, non del calcolo (route diverse = job diversi) | **Sì** | `n_rows>1` produce route/job distinti per token (struttura `flat` indicizzata per riga), coerente con P1 §4.7. |
| ID esperto logico, non slot | **Sì** | Commento e uso in `validate_and_prepare()`: `expert < 0 || expert >= cur_bank->n_experts`, mai uno slot. |

---

## D. Copertura di T1-T11: buchi

1. **Buco maggiore, collegato a B1.** Tutti i test (T5, T7, T8, T10) chiamano `submit_hook` e `wait_hook` **in sequenza, sullo stesso thread, senza alcun lavoro intermedio**. Non esiste un test in cui: (a) il coordinatore sia genuinamente occupato in `compute()` (job con K/H grandi, o un ritardo artificiale iniettato) mentre (b) un secondo thread chiama `cancel()` o forza la scadenza del `wait`. È esattamente lo scenario di B1, e non è testabile senza questa modifica al banco. Andrebbe aggiunto un T12: thread A avvia un job "lento" (usare `--full`, K=2560/H=640, o un ritardo di test), thread B chiama `cancel()` a metà mentre il job è ancora genuinamente in calcolo, poi si verifica che un **terzo** job successivo non osservi mai `done==1` prima di aver effettivamente calcolato (es. tramite un contatore di generazione dentro `y_h` stesso, o osservando `n_completed` cresce coerentemente con generazioni distinte).
2. **Nessun test di `contaminated()`/recupero (B2).** T6 verifica solo che `contaminated()` diventi vero; nessun test verifica cosa succede a un job **successivo** dopo la contaminazione (dovrebbe restare bloccato per sempre, il che è proprio il difetto da correggere) né esiste un test per l'eventuale `acknowledge`/reset proposto.
3. **Nessun test dei percorsi di fallimento in `create()`.** "La creazione fallisce con un messaggio se un tipo non ha tratti CPU, se gate e up non condividono il `vec_dot_type`, se `n_ff_exp` non è multiplo del blocco..." (§3.1 del progetto) — nessuno di questi casi è esercitato da `test_esecutore.cpp`; solo il percorso felice è testato.
4. **Nessun test di idempotenza/errore di `register_layer`.** Il comportamento dichiarato ("idempotente con gli stessi puntatori, errore se cambiano") non è mai esercitato: il test registra lo strato 7 una sola volta.
5. **T6 copre 6 casi di header non valido ma non tutti quelli enumerati nel codice**: manca un test con `n_routes[row] < 0`, con `weight` infinito (solo NaN è testato), con attivazione (`x`) non finita, e con `layer < 0`.
6. **`max_rows = 3` (P5) non è mai esercitato**, nemmeno come semplice controllo di forma con `n_rows=2` o `3`: accettabile per lo scope di P2 ("il valore operativo resta 1 fino a P4"), ma vale la pena annotarlo esplicitamente come lavoro futuro invece di lasciarlo implicito.
7. **Nessun test per la scadenza vera del `wait`** (`MOE_CPU_RESULT_TIMEOUT`): tutti i job nei test si concludono correttamente; il ramo di scadenza in `wait_hook` (righe 643-652) non è mai eseguito da T1-T11.

---

## E. Compilabilità a occhio

**E1 — Correggere prima della build (P3, non blocca il test host-only). Nome e firma di proc-address sbagliati in `moe_cpu_host_memory_cuda.cpp:43-58`.**

```cpp
using mapped_buft_fn = ggml_backend_buffer_type_t (*)(int);
...
auto buft_fn = (mapped_buft_fn) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cuda_mapped_buffer_type");
```

Verificato sull'albero reale: la funzione registrata in tabella (`ggml-cuda.cu:6032-6033`) si chiama `"ggml_backend_cuda_mapped_buffer_type_for_device"` e ha firma `ggml_backend_buffer_type_t (ggml_backend_dev_t)`, **non** `(int)`. La stringa usata da P2 non esiste in tabella: a runtime `buft_fn` sarà sempre `nullptr` e la creazione fallirà con "buffer type mappato non esposto dal backend" — fallimento sicuro (nessun crash), ma la funzione è comunque **non operativa così com'è**. Va corretto il nome della stringa **e** il tipo (`ggml_backend_dev_t`, ottenuto dalla stessa `dev` già risolta due righe sopra) prima di collegare questo file nel server.

**E2 — Correggere prima della build. `moe_cpu_host_memory_plain.cpp` usa `_aligned_malloc`/`_aligned_free` senza includere `<malloc.h>`.**

File: `src/moe_cpu_host_memory_plain.cpp:1-8`. Include solo `"moe_cpu_host_memory.h"`, `<cstdlib>`, `<cstring>`. Su MSVC, `_aligned_malloc`/`_aligned_free` sono documentate come dichiarate in `<malloc.h>`; non è garantito che `<cstdlib>` le porti in ambito. Rischio concreto di errore "identificatore non trovato" in compilazione. Correzione: aggiungere `#include <malloc.h>`.

**Controlli con esito positivo:**
- Nessun uso di `Synchronization.lib`/`synchapi.h` statico: `WaitOnAddress`/`WakeByAddressAll` sono risolte dinamicamente via `LoadLibraryA`/`GetProcAddress` (righe 62-69), quindi non serve linkare nulla in più e il fallback a `Sleep(1)` è già gestito. Scelta corretta e più portabile di un link statico.
- `ggml-moe-cpu.h` è incluso da un file C (`ggml.c`, dichiarato dal progetto) e usa `bool`: `ggml.h`, incluso a monte, porta già `<stdbool.h>` (riga 211), quindi nessun problema di compilazione in C.
- `build_test.cmd` compila solo `test_esecutore.cpp + moe_cpu_executor.cpp + moe_cpu_host_memory_plain.cpp`, escludendo correttamente `moe_cpu_host_memory_cuda.cpp` (che richiede `ggml-backend.h`/simboli del backend CUDA non necessari al test host-only). `build_test.ps1` è un wrapper coerente, nessuna discrepanza fra i due.
- Nessuna incoerenza di firma trovata fra `moe_cpu_executor.h` e `.cpp`, né fra `ggml-moe-cpu.h` e il suo uso previsto.
- Punto già dichiarato correttamente dal progetto come lavoro aperto (non lo ripeto come nuovo difetto): `ggml_cuda_mapped_tensor_host_ptr` non è ancora in tabella proc-address (confermato, E1 lo richiede comunque separatamente per il nome del buffer type).

---

## F. Rischi R1-R9: quali misurare per primi, cosa manca

Il progetto ordina già correttamente R2 come prima misura di P3 ("non come ultima"), e R1 come verifica preliminare di credibilità di qualunque guadagno. Concordo con questo ordine: **R2 (concorrenza reale submit/wait) e R1 (costo del blocco sul thread di callback del driver) restano la coppia da misurare per prima**, perché senza R2 non c'è motivo di credere a nessun numero di velocità, e R1 stabilisce se l'intero meccanismo è compatibile con il resto del traffico CUDA del processo.

Rischi che mancano dall'elenco, emersi da questa revisione:

- **R11 (nuovo).** Il rilascio prematuro di `in_flight` da `cancel()`/scadenza del `wait` (B1) non è un rischio di prestazioni ma di **correttezza**: va corretto in codice, non misurato. Andrebbe aggiunto all'elenco come promemoria che B1 blocca l'ingresso in P3 finché non risolto, altrimenti rischia di essere silenziosamente riscoperto come "risultato ogni tanto sbagliato" durante le misure di P4/P6, molto più costoso da diagnosticare a quel punto (coerente con la regola di metodo "verifica dopo, non prima" del progetto più ampio: qui vale il contrario, va verificato **prima**).
- **R12 (nuovo).** La sticky-ness di `contaminated()` senza `ack`/reset (B2) è un rischio operativo: se non corretto, la prima volta che P4/P5 esercitano un rollback speculativo con un job CPU in volo, ogni `decode()` successivo fallirebbe fino al riavvio del processo. Da misurare/verificare esplicitamente come primo test funzionale in P3, prima di qualunque banco di velocità, perché altrimenti un banco lungo si interromperebbe al primo rollback senza una diagnosi ovvia.
- **R13 (nuovo, minore).** Il join dei thread in `impl::shutdown()` non ha un limite di tempo: se, per una finestra molto stretta, il coordinatore fosse bloccato su una barriera senza tutti i partecipanti (possibile in teoria se `stopping` si intreccia con un `work.fetch_add` legittimo proprio nell'istante sbagliato — analisi a parte, probabilità bassa ma non nulla dato B1), la distruzione dell'esecutore si bloccherebbe indefinitamente, in contraddizione con T9 ("distruzione senza stallo... sotto i 2 s") che però non esercita questo caso specifico. Basso rischio isolato, ma vale la pena una guardia con timeout esplicito su `join()` o un contatore di generazione confermata prima di fermare i thread.

---

## Giudizio

Non compilare/collegare così com'è: i due difetti B1 e B2 sono di correttezza, non di stile, e minano esattamente le proprietà (invariante 6/7, "un solo job in volo", recupero dopo un errore) che P2 doveva dimostrare per iscritto. Vanno corretti nel codice sorgente di `moe_cpu_executor.cpp`/`.h` prima di aprire P3, con un test aggiuntivo (T12, vedi D1) che eserciti davvero la concorrenza fra `cancel()`/scadenza e un `compute()` in corso, non solo la sequenza sincrona attuale.

I difetti E1/E2 sono invece meccanici e a basso rischio (falliscono in modo sicuro o si correggono con un include/una stringa), da sistemare nello stesso giro prima di lanciare `build_test.cmd`: aggiungere `#include <malloc.h>` in `moe_cpu_host_memory_plain.cpp` costa nulla e va fatto comunque; il fornitore CUDA (E1) può restare rotto per ora perché non è collegato dal test host-only, ma va segnato esplicitamente come bloccante per l'inizio di P3, in aggiunta — non in sostituzione — al lavoro già previsto sul proc-address di `ggml_cuda_mapped_tensor_host_ptr`.

Il resto del progetto (confine d'interfaccia, tabella delle allocazioni, ordine sullo stream, quantizzazione) è coerente con i sorgenti letti e i riferimenti citati sono, salvo un caso, esatti: la revisione non mette in discussione l'impostazione generale, solo l'implementazione concreta della gestione di errore/annullamento.
