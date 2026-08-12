# 01 — Ingresso della richiesta e ciclo di decode

Lettura statica (nessuna esecuzione) del repo `D:\llama-overlap`, antenato upstream `5c3a58686`.
Blocco: `tools/server/server-context.cpp` (386 righe nostre), `tools/server/server.cpp` (136), `tools/server/server-stream.cpp` (31).
Il diff tocca anche `tools/server/server-schema.cpp` (+4: espone `speculative.conf_min` via `/props`) e `tools/server/CMakeLists.txt` (+2: linka `sha256.c`) — sono dello stesso commit e li includo.

Ogni riga è marcata **[L]** = LETTO NEL CODICE, **[D]** = DEDOTTO, non verificato.
Tutti i `file:riga` si riferiscono al file **finale** (HEAD), non al diff.

Configurazione di riferimento per i giudizi di raggiungibilità (quella del mandato):
`-np 1`, `-c 10000`, `-ub 64`, `--spec-type draft-dspark`, `--spec-draft-n-max 1`, `--spec-draft-ubatch-size 16`;
env accese: `LLAMA_KV_RING=1`, `LLAMA_KV_ROLLBACK_PARZIALE=1`, `LLAMA_MAPPED_IBRIDO=1`, `LLAMA_OVERLAP_ASYNC=1`,
`LLAMA_CACHE_ESPERTI_*`, `LLAMA_SPEC_DRAFT_TOPK=1`, `LLAMA_DSV4_HC_FUSO=5`.
**Non** accese (rilevanti per il mio blocco): `LLAMA_TRACE`, `LLAMA_ACCEPTMOE`, `LLAMA_CACHE_ESPERTI_DMA`,
`LLAMA_CKPT_CRONO`, `LLAMA_KV_POSMIN_VERO`, `LLAMA_SERVER_SLOTS_DEBUG`, `LLAMA_STREAM_*`.

---

## A. CONTATORI

### A.1 — La riga di battito: `print_timings_tg()`

**Dove nasce**: `server-context.cpp:685-691` (unica `SLT_INF`), dentro `server_slot::print_timings_tg()` (`:622`).
**Chi la chiama**: due siti, entrambi in `post_decode()`:
- `:4059` — cammino **senza** bozza (un token campionato);
- `:4241` — cammino **speculativo**, dopo aver emesso tutti i token accettati.
[L]

**Cancelli** (entrambi devono passare, altrimenti la funzione esce senza stampare **e senza chiudere la finestra**):
- `:623` `if (n_decoded < 100) return;` → nessuna riga prima del 100° token della richiesta;
- `:629` `if (t_now - t_print_last < 3*1000*1000) return;` → almeno 3 s dall'ultima stampa. [L]

> **La finestra non è "3 s": è "il tempo trascorso dall'ultima stampa riuscita"**, chiusa al primo token
> generato dopo che i 3 s sono passati. Il denominatore è `t_now - t_print_last` (`:634`, `:654`), cioè il
> valore vero, non 3 s. Con `ms_cycle ≈ 130 ms` la finestra reale è 3,0-3,13 s. [L]

Formato esatto della riga nel log:

```
n_decoded = %6d, tg = %6.2f t/s, tg_3s = %6.2f t/s, p1_3s = %s, mean_len_3s = %s, ms_cycle_3s = %s, spec_mean_len_3s = %s, cache_hits_3s = %s
```

| nome nel log | natura | formula (riga) | incrementato a | unità |
|---|---|---|---|---|
| `n_decoded` | **CUMULATIVO** per slot dall'inizio della generazione | campo `slot.n_decoded` | `:4019` (non-spec, `+=1`), `:4229` (spec, `+=1` per token accettato); azzerato a `:3682` quando il prompt finisce | token |
| `tg` | **CUMULATIVO** | `:633` `1e3/t_token_generation*n_decoded` | `t_token_generation` aggiornato a `:4038` e `:4192` | token/s |
| `tg_3s` | **FINESTRA** (azzerata a ogni stampa) | `:634` `1e6/(t_now-t_print_last)*(n_decoded-n_decoded_last)` | `n_decoded_last` a `:679` | token/s |
| `p1_3s` | **FINESTRA** | `:646` `n_p1_win/n_verif_win` | `n_accepted_per_pos[0]` in `update_spec_stats` `:335-347`; base a `:683` | frazione 0..1 (accettazione della **prima** posizione della bozza) |
| `mean_len_3s` | **FINESTRA** | `:653` `n_decoded_win/n_cycles_win` | `n_target_cycles` a `:3886`; base a `:680` | token per **ciclo target** |
| `ms_cycle_3s` | **FINESTRA** | `:654` `(t_now-t_print_last)/1000/n_cycles_win` | idem | ms per **ciclo target** |
| `spec_mean_len_3s` | **FINESTRA** | `:647` `1 + n_accepted_win/n_verif_win` | `n_draft_accepted`/`n_draft_verif_steps` in `update_spec_stats` `:336-337` | token per **verifica** |
| `cache_hits_3s` | **FINESTRA** (differenza di due letture di contatori cumulativi) | `:662-668` | letto da `llama_cache_esperti_get_stats` `:659`; basi a `:671-672` | `"%.1f%% (hits/lookups)"` |

**Trappola numerica** (fonte di due metriche che sembrano la stessa cosa e non lo sono):
`mean_len_3s` divide per **`n_target_cycles`** (ogni `llama_decode` sul bersaglio che tocca lo slot, **replay compresi e cicli senza bozza compresi**, `:3877-3891`), mentre `spec_mean_len_3s` divide per **`n_draft_verif_steps`** (solo le verifiche vere, e il replay è escluso da `:4197`). Con i ripristini da checkpoint `mean_len_3s < spec_mean_len_3s` **per costruzione**. [L]

**Se un cancello non passa la finestra NON si chiude**: le basi (`:678-683`) si aggiornano solo dopo i due
`return`, quindi una richiesta che genera 99 token non produce nessuna riga e non tocca le basi; e se un
battito salta (per esempio perché lo slot si è fermato), la finestra successiva è più lunga di 3 s ed è
correttamente normalizzata dal tempo, ma `n_cycles_win`/`n_verif_win` coprono anche la parte "saltata". [L]

**Inizializzazione della finestra**: `:4021-4036`, solo quando `n_decoded == 1`. Quel ramo è nel cammino
**non speculativo**, ma è comunque raggiunto: al primo token dopo il prompt `spec_draft` è ancora vuoto
(la bozza si genera in `pre_decode()` del ciclo successivo), quindi la guardia `:3991` non scatta. [L]
`slot.n_decoded_last = 1` (`:4025`, era `0` upstream) esclude dalla prima finestra il token che nasce
dall'ultimo decode del prompt. [L]

### A.2 — Riepilogo di fine richiesta: `print_timings()`

`server-context.cpp:706-755`. Chiamata da `post_decode()` a `:4051` e `:4232`, subito prima di
`send_final_response()`. Tutti i valori sono **CUMULATIVI per la richiesta** (azzerati in `reset()` `:353`). [L]

| riga nel log | file:riga stampa | natura | unità |
|---|---|---|---|
| `prompt eval time = ... ms / N tokens (... ms per token, ... tokens per second)` | `:713-715` | cumulativo | ms, token, t/s |
| `       eval time = ...` | `:717-719` | cumulativo | ms, token, t/s |
| `      total time = ...` | `:721-723` | cumulativo | ms, token |
| `   graphs reused = %10d` | `:725-727` | **CUMULATIVO DI CONTESTO, NON DI RICHIESTA** | conteggio |
| `draft acceptance = %0.5f (%5d accepted / %5d generated), mean len = %5.2f` | `:743-745` | cumulativo per richiesta | frazione, conteggi, token/verifica |
| `  coda riavvolta = %5d parziali / %5d ripristini (%5d episodi non pieni su %5d verifiche)` | `:746-749` | cumulativo per richiesta | conteggi |
| `     acc per pos = (...)` | `:750-751` | cumulativo, **solo a livello TRC** | frazioni |

- **`graphs reused`** viene da `llama_perf_context(ctx_tgt).n_reused` (`:727`), incrementato in
  `src/llama-context.cpp:1599` e azzerato **solo** da `llama_perf_context_reset` (`src/llama-context.cpp:3751`),
  che il server non chiama mai. **Cresce attraverso le richieste**: la seconda richiesta di una sessione
  stampa il totale dalla nascita del contesto, non i grafi riusati in quella richiesta. [L]
- `draft acceptance` = `n_draft_accepted / n_draft_total`. `n_draft_total` cresce **solo** in
  `:3090` (`slot.n_draft_total += draft.size()`), cioè solo nei cicli in cui una bozza è stata
  effettivamente generata — non nei replay. [L]
- `mean len` = `1 + n_draft_accepted / n_draft_verif_steps` (`:731`). Stessa base di
  `spec_mean_len_3s`. [L]
- `coda riavvolta`: `n_spec_rb_parziale` incrementato a `:4125` (rollback della sola coda riuscito),
  `n_spec_rb_ckpt` a `:4137` (ripristino del checkpoint). Sono **mutuamente esclusivi** per episodio
  (`:4135` ha `&& !rb_parziale`). La loro somma è il numero di accettazioni **non piene**. [L]

### A.3 — Altre righe prodotte dal blocco

| riga nel log | file:riga | natura | cancello |
|---|---|---|---|
| `manifesto: E=ambiente D=difetto; LLAMA_MANIFESTO=...` + una riga `manifesto/<gruppo>: NOME=valore(E\|D) ...` per gruppo | `server.cpp:126` e `:132`/`:147`; chiamata a `:245` | **una volta per processo** (`atomic_flag`, `:113-116`) | `LLAMA_MANIFESTO` assente o ≠0 |
| `[kv-ring-output] task=%d bytes=%zu sha256=%s` | `server-context.cpp:2221-2223`, in `send_final_response()` | **una per task completato**, istantanea | `getenv("LLAMA_KV_RING")` **non nullo** (`:2219`) |
| `checkpoint: %lld salvataggi, %.3f ms medi, %.1f ms totali (%.3f MiB l'uno)` | `:3132-3134` | **CUMULATIVO DI PROCESSO** (`static int64_t` a `:3122-3123`), stampato ogni 200 salvataggi | `LLAMA_CKPT_CRONO` (`:3119`) — **spento** |
| `acceptmoe-spia: disarmo con bozza: stato=..., replay=..., catena=..., bozza=..., fronte=..., off=..., vista=...` | `:3813-3817` | istantanea, una per decode non armato | `LLAMA_ACCEPTMOE` **e** `LLAMA_ACCEPTMOE_SPIA` — **spenti** |
| `accepted %2zu/%2zu draft tokens (coda riavvolta a pos %d)` | `:4128` | istantanea per episodio | `trace > 0` — **spento** |
| `accepted %2zu/%2zu draft tokens (restore checkpoint)` | `:4140` | istantanea | `trace > 0` — **spento** |
| `accepted %2zu/%2zu draft tokens` | `:4180` | istantanea | `trace > 0` — **spento** |
| `riuso del prompt con coda da togliere: p0=..., pos_max=..., coda=... -> ...` | `:3517-3521` (SLT_WRN) | istantanea | `posmin_vero` — **spento** |
| `prompt processing, n_tokens = ..., progress = ..., t = ... s / ... tokens per second` | `:702-703` (`print_timings_pp`, chiamata a `:3493`) | cumulativo sul prompt, stampato solo se `t_prompt_processing >= 3000 ms` (`:698`) | — |
| `n_pre_decode`, `avg t_pre_decode`, `avg t_decode`, `avg t_post_decode`, `avg t_sampl` | `:2857-2860` | medie cumulative di processo, ogni 5 s | `#ifdef DEBUG_TIMINGS` — **la define è commentata a `:2830`, codice non compilato** |

**Conseguenza operativa**: nella configurazione in uso, del mio blocco escono nei log **solo**
il manifesto, la riga `[kv-ring-output]`, `prompt processing`, il battito `tg_3s`, e il riepilogo
finale con `graphs reused` / `draft acceptance` / `coda riavvolta`. Tutte le righe per-ciclo
(`accepted N/M ...`) sono spente perché `LLAMA_TRACE` non è impostata. [L]

---

## B. VARIABILI D'AMBIENTE LETTE NEL MIO BLOCCO

| variabile | file:riga della lettura | difetto | forma del cancello | raggiungibile **oggi**? |
|---|---|---|---|---|
| `LLAMA_MANIFESTO` | `server.cpp:118` | assente = **acceso** | spegne solo se vuoto o `atoi()==0` | **SÌ** — il manifesto si stampa |
| `LLAMA_TRACE` | `server-context.cpp:1447` | `0` | `atoi()` | **NO** — `trace=0`, tre `SLT_INF` per-ciclo morte (`:4127`, `:4139`, `:4179`) |
| `LLAMA_SERVER_SLOTS_DEBUG` | `:1456` | `0` | `atoi()` | **NO** |
| `LLAMA_KV_POSMIN_VERO` | `:1465` | `0` | `!= '0'` | **NO** — `posmin_vero=false`: morti il riavvolgimento di coda nel riuso del prompt (`:3512-3536`) e il pin di `pos_min_ckpt` (`:3705-3709`) |
| `LLAMA_KV_RING` | `:2219` | assente | **solo `getenv() != nullptr`** | **SÌ** (=1) — stampa lo sha256 di ogni risposta |
| `LLAMA_CKPT_CRONO` | `:3119` | `0` | `!= '0'`, `static` (una volta) | **NO** |
| `LLAMA_ACCEPTMOE` | `:3783` | `0` | `atoi()`, `static` | **NO** — **`llama_acceptmoe_arma()` non viene mai chiamata dal server** |
| `LLAMA_ACCEPTMOE_SPIA` | `:3805` | `0` | `atoi()`, `static`, **annidata dentro `LLAMA_ACCEPTMOE`** | **NO** (doppiamente) |
| `LLAMA_CACHE_ESPERTI_DMA` | `:4009` **e** `:4093` (due `static` distinti) | `0` | `atoi()`, `static` | **NO** — `llama_cache_esperti_dma_prefetch()` mai chiamata |
| `LLAMA_STREAM_TTL` | `server-stream.cpp:38` (via `env_i64`, `:27`) | `300` s | `strtoll`, scarta `<=0` | **SÌ** ma non impostata → 300 s |
| `LLAMA_STREAM_MAX_MB` | `server-stream.cpp:41` | `4` MiB | idem | **SÌ** ma non impostata → 4 MiB |
| `LLAMA_STREAM_GC` | `server-stream.cpp:42` | `60` s | idem | **SÌ** ma non impostata → 60 s |

Note importanti:
- Le tre `LLAMA_STREAM_*` sono **inizializzatori di variabili globali a durata statica** in un namespace
  anonimo (`server-stream.cpp:38-42`): vengono lette all'**inizializzazione dinamica del modulo**,
  prima di `main()`. Non c'è modo di cambiarle a caldo, e non compaiono nel manifesto con il loro
  valore effettivo se qualcuno le imposta dopo l'avvio. [L]
- `LLAMA_KV_RING` a `:2219` è l'**unico** cancello del repo che non confronta con `"0"`: altrove
  (`src/llama-kv-cache-dsv4.cpp:183-186`, `src/llama-context.cpp:551-552`) la forma è
  `v && *v && strcmp(v,"0") != 0`. Con `LLAMA_KV_RING=0` la stampa sha256 resterebbe accesa. [L]
- Il **manifesto** (`server.cpp:36-109`) è solo una stampa: **non legge nessuna leva per usarla**,
  legge 66 nomi con `getenv` e stampa valore + `(E)`/`(D)`. I difetti elencati sono una copia manuale
  dei siti di lettura veri. Spot-check fatti da me e **coincidono**: `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=32`
  (`ggml/src/ggml-cuda/cache-esperti.cu:1645`), `LLAMA_DSV4_HC_FUSO=0` (`src/llama-context.cpp:307`),
  `LLAMA_SPEC_DRAFT_TOPK=1` (`common/speculative.cpp:999-1000`), `LLAMA_MAPPED_IBRIDO_SOGLIA=2`
  (`ggml/src/ggml-cuda/ggml-cuda.cu:5535`). [L]

---

## C. COMPLESSITÀ SUL CAMMINO CALDO

Simboli: `S` = numero di slot (`-np 1` → **S=1**), `T` = token nella vista di batch
(decode speculativo con n-max 1 → **T=2**: token campionato + 1 bozza), `D` = dimensione della bozza
(**D≤1**), `E` = esperti (non compare in questo blocco: il mio blocco non tocca gli esperti).

Un "ciclo" = una iterazione di `update_slots()`.

| funzione | file:riga | chiamate per ciclo | costo |
|---|---|---|---|
| `update_slots()` | `:2851` | **1** | O(S) per il controllo idle + il resto sotto |
| `pre_decode()` | `:2941` | **1** | O(S) per il context-shift + O(S) per determinare generating/drafting |
| `common_speculative_draft()` | `:3082` | **1** | 1 `llama_decode` su `ctx_dft` con `n_max` token (=1, `common/speculative.cpp:1189`) + `D` campionamenti |
| `slot.spec_ckpt.update_pos/update_dft` | `:3054`, `:3060` | 1 (solo quando si inizia una bozza nuova) | `update_dft` **non eseguita** oggi (vedi D) |
| `ckpt.update_tgt()` | `:3127` | **1 per ciclo con bozza** | O(dimensione dello stato KV parziale). Il commento a `:3113-3117` dichiara **~11,7 MiB verso l'host in ~124 letture di tensore** per salvataggio [L, è un commento dell'autore: il numero è **[D]** rispetto al codice] |
| `handle_last_sampled_token()` | `:511`, chiamata a `:3152` | 1 per slot generante | O(D) |
| `batch.render()` + `get_view()` | `:2892`, `:2906` | 1 + 1 per sotto-batch | O(T) |
| `decode()` | `:3741` | **1 per sotto-batch**; con T=2 e `n_batch` grande → **1** | contiene la `llama_decode` del bersaglio |
| conteggio `n_target_cycles` | `:3879-3891` | 1 | **O(S · T · n_seq_id)** — doppio ciclo annidato, oggi 1×2×1. In un regime a np>1 e prompt lunghi diventa O(S·n_batch) per sotto-batch |
| `common_speculative_process()` | `:3896` | **1** | per ogni seq: `ceil(T / ubatch_dft)` iterazioni; ognuna 1 `llama_encode` + 1 `llama_decode` su `ctx_dft` (`common/speculative.cpp:1114`, `:1134`). Con T=2 e `--spec-draft-ubatch-size 16` → **1 encode + 1 decode** |
| `post_decode()` | `:3929` | **1 per sotto-batch** | vedi sotto |
| verifica `is_inside_view` | `:3937-3943` | 1 | O(S · D) |
| `common_sampler_clone()` | `:4080` | **1 per ciclo con bozza** | O(dimensione dello stato del sampler) — copia su CPU a ogni ciclo, anche quando l'accettazione è piena e non serve |
| `common_sampler_sample_and_accept_n()` | `:4083` | **1** | O(D+1) campionamenti = 2 |
| `llama_memory_seq_rm_tail()` | `:4122` | **1 per accettazione non piena** | O(1) di logica + `kv_raw->seq_rm` (vedi §Domanda 3) |
| `process_token()` | `:1941`, chiamate a `:4049` e `:4231` | 1 per token emesso | O(len(testo)) + O(n_antiprompt · len) in `find_stopping_strings` (`:591`) |
| `print_timings_tg()` | `:622` | 1 per token emesso, ma **esce subito** in 99 casi su 100 | O(1) + `llama_cache_esperti_get_stats` O(n_backend) solo quando stampa |
| `send_final_response()` | `:2206` | 1 per richiesta | O(len(testo)) + **sha256 su tutto il testo generato** (`:2220`, `kv_ring_output_sha256` `:48-60`) |

**Totale lanci di grafo per ciclo di decode speculativo (n-max 1, dspark)**: **1 `llama_decode` bersaglio
+ 1 `llama_encode` bozza + 2 `llama_decode` bozza = 4**. [L]
Nel **ciclo di replay** (dopo un ripristino da checkpoint) la bozza non viene rigenerata (`:3046`
riusa `spec_draft` e non spinge lo slot in `drafting`), quindi restano **1 decode bersaglio + il
`process` della bozza**. [L]

---

## D. HOST vs DEVICE E CONFINI DI SINCRONIZZAZIONE

**Tutto il mio blocco gira su CPU.** Non lancia kernel direttamente: nessuna chiamata `ggml_*` di calcolo,
nessun `cuda*`. Lancia lavoro GPU solo attraverso quattro porte:

1. `llama_decode(ctx_tgt, batch_view)` — `:3823`. **1 per sotto-batch.**
2. `llama_encode(ctx_dft, ...)` — dentro `common_speculative_process` (`common/speculative.cpp:1114`). 1 per chunk.
3. `llama_decode(ctx_dft, batch_inject)` — `common/speculative.cpp:1134`. 1 per chunk.
4. `llama_decode(ctx_dft, batch)` — `common/speculative.cpp:1189` (generazione della bozza). 1 per ciclo.

**Confini CPU-GPU visibili dal mio blocco, per ciclo di decode speculativo:**

| # | sito | file:riga | volte per ciclo | cosa forza |
|---|---|---|---|---|
| 1 | `ckpt.update_tgt()` → `llama_state_seq_get_data` | `:3127` | **1** (ogni ciclo con bozza) | sincronizza e **copia lo stato KV parziale D2H** [D per il meccanismo interno; il sito è [L]] |
| 2 | `common_sampler_sample_and_accept_n()` | `:4083` | **1** | legge i logit del bersaglio → sincronizzazione implicita [L per il sito, [D] per il fatto che sia il sync] |
| 3 | `common_sampler_sample()` (cammino senza bozza) | `:4001` | 0 o 1 (mutuamente esclusivo con #2) | idem |
| 4 | `llama_get_embeddings_layer_inp(ctx_tgt, …)` | `common/speculative.cpp:1092` | 1 per chunk | legge le feature del **bersaglio** dopo la sua decode |
| 5 | `llama_get_embeddings_nextn(ctx_dft)` dopo l'encode | `common/speculative.cpp:1121` | 1 per chunk | legge l'uscita dell'encoder della bozza |
| 6 | `common_sampler_sample(smpl, ctx_dft, idx)` in `draft()` | `common/speculative.cpp:1231` | 1 per token di bozza (=1) | legge i logit della bozza |
| 7 | `llama_synchronize(ctx_tgt)` esplicita | `:2910` | **0** — dentro `#ifdef DEBUG_TIMINGS`, non compilato (`:2830`) | — |

**Non sincronizzano**: `llama_memory_seq_pos_min/max` (`:3056-3057`, `:3694-3695`, `:4122` interno) —
metadati host; `llama_cache_esperti_get_stats` (`:659`, `:4031`) — legge contatori host dentro la
struct del backend CUDA (`src/llama-context.cpp:3754-3773` → `ggml/src/ggml-cuda/ggml-cuda.cu:1507`),
nessuna `cudaDeviceSynchronize` sul percorso [L per la catena di chiamate, **[D]** per l'assenza di sync
dentro `ggml_cuda_cache_esperti_contatori`, che non ho aperto].

**Quindi il mio blocco contribuisce ~5-6 confini per ciclo.** I ~76 confini per token della nota di
memoria non nascono qui: nascono dentro `llama_decode`/`ggml-backend` (blocco di un altro lettore). [D]

---

# DOMANDE SPECIFICHE

## 1. Come nasce un ciclo di decode speculativo

Catena delle chiamate, per una iterazione di `update_slots()`:

```
server_context::start_loop()                       server-context.cpp:4267
 └─ queue_tasks.start_loop()  →  callback on_update_slots  (registrata a :1540-1542)
     └─ update_slots()                              :2851
         ├─ pre_decode()                            :2892  → :2941
         │   ├─ context shift (se serve)            :2944-3007
         │   ├─ batch.clear()                       :3010
         │   ├─ iterate(slots): chi genera / chi bozza  :3021-3078
         │   │     · get_n_draft_max()              :489   (n_ctx - n_tokens - 2, poi min con n_remaining-1)
         │   │     · spec_ckpt.update_pos()         :3054
         │   │     · imposta draft_params{drafting=true, n_max, n_past, id_last, prompt, result}  :3065-3072
         │   ├─ common_speculative_draft(spec)      :3082  →  1 llama_decode su ctx_dft (1 token)
         │   ├─ iterate(drafting): checkpoint       :3086-3148
         │   │     · n_draft_total += draft.size()  :3090
         │   │     · seq_rm sul ctx_dft             :3100
         │   │     · ckpt.update_tgt(...)           :3127   ← il salvataggio da ~11,7 MiB
         │   ├─ iterate(generating): handle_last_sampled_token(batch)  :3151-3153
         │   └─ riempimento dei prompt pendenti     :3163-3730
         ├─ ciclo sui sotto-batch                   :2901-2938
         │   ├─ batch.get_view(off, n_tokens)       :2906
         │   ├─ decode(n_batch, off, batch_view)    :2908 → :3741
         │   │     · [ACCEPTMOE: morto]             :3782-3821
         │   │     · llama_decode(ctx_tgt, view)    :3823     ← IL decode del bersaglio
         │   │     · metrics.on_decoded(slots)      :3825
         │   │     · n_target_cycles++              :3886
         │   │     · common_speculative_process()   :3896    → 1 encode + 1 decode su ctx_dft
         │   └─ post_decode(n_tokens, off, view)    :2931 → :3929
         │         ├─ [cammino senza bozza] sample :4001, n_decoded++ :4019, process_token :4049
         │         └─ [cammino speculativo]        :4063-4244
         │               · common_sampler_clone     :4080
         │               · sample_and_accept_n      :4083
         │               · n_rollback = D+1-|accepted|  :4101
         │               · [rollback parziale]      :4116-4132
         │               · [ripristino checkpoint]  :4135-4177  (fa `return`)
         │               · update_spec_stats        :4198
         │               · prompt.tokens keep/insert :4204-4205
         │               · process_token × |ids|    :4220-4239
         │               · print_timings_tg         :4241
```
[L]

**Quante `llama_decode` per ciclo**: vedi §C. Con `--spec-draft-n-max 1`, `-np 1`, `-ub 64`,
`--spec-draft-ubatch-size 16`:
- ciclo normale: **1 sul bersaglio + 3 sulla bozza** (1 decode di generazione, 1 encode + 1 decode di iniezione);
- ciclo di **replay** (dopo ripristino da checkpoint): **1 sul bersaglio**, nessuna generazione di bozza
  nuova (`:3046` riusa la bozza troncata), più l'iniezione in `process`. [L]

**Come si compone il batch di verifica con n-max 1** — `handle_last_sampled_token()` `:511-544`:
- `spec_i_batch` = `[k, k+1]` dove `k = batch.size()` prima dell'inserimento (`:527-530`);
- `batch.add(id, sampled, pos0++, true)` — il token appena campionato, **con logit richiesti** (`:534`);
- `batch.add(id, draft[0], pos0++, true)` — l'unico token di bozza, anch'esso con logit (`:536`);
- **entrambi i token vengono inseriti in `prompt.tokens`** già ora (`:542-543`), cioè il prompt contiene
  la bozza **prima** che sia verificata; è per questo che dopo la verifica serve
  `keep_first(n_tokens - n_draft)` a `:4204`.

Quindi la **vista di batch di verifica ha esattamente 2 righe** e `spec_i_batch.size() == n_draft + 1 == 2`
(asserito a `:4082`). Con `-ub 64` le due righe stanno in un solo ubatch, e con `n_batch` di difetto in un
solo sotto-batch → **una sola `llama_decode` del bersaglio per ciclo**. [L]

`common_sampler_sample_and_accept_n` restituisce `accepted` con `1 <= |accepted| <= 2`:
- `|accepted| == 2` → accettazione piena, `n_rollback == 0`, si esce da `:4179` in poi;
- `|accepted| == 1` → la bozza è stata rifiutata, `n_rollback == 1` → cammino di rollback. [L]

## 2. Dove nascono le metriche citate

| metrica | dove nasce | cumulativa o a finestra | finestra |
|---|---|---|---|
| `draft acceptance` | stampa `:743-745`; numeratore `n_draft_accepted` in `update_spec_stats` `:336`; denominatore `n_draft_total` a `:3090` | **cumulativa per richiesta** (azzerata in `reset()` `:375-376`) | l'intera richiesta |
| `mean len` | `:731`, `1 + n_draft_accepted/n_draft_verif_steps` | **cumulativa per richiesta** | l'intera richiesta |
| `n_decoded` | campo, `+=1` a `:4019` e `:4229`; azzerato a `:3682` | **cumulativo per richiesta** | l'intera richiesta |
| `tg_3s` | `:634`, stampa `:685-691` | **a finestra** | `t_now - t_print_last`, ≥ 3 s, chiusa al primo token utile dopo i 3 s |
| `ms_cycle_3s` | `:654` | **a finestra** | idem, denominatore `n_target_cycles` (`:3886`) |
| `cache_hits_3s` | `:662-668` | **a finestra**, calcolata come differenza fra due letture di contatori globali del backend CUDA | idem. **Attenzione: i contatori sono di CONTESTO, non di slot**: con np>1 la finestra dello slot A ingloba anche i lookup dello slot B |
| `graphs reused` | `:727`, `llama_perf_context(ctx_tgt).n_reused` | **cumulativa di CONTESTO** (mai azzerata dal server) | dalla nascita del contesto |
| `coda riavvolta` | `:746-749`; `++` a `:4125` e `:4137` | **cumulativa per richiesta** | l'intera richiesta |

**Le due `mean len` non sono la stessa metrica**: `mean len` del riepilogo e `spec_mean_len_3s` usano
`n_draft_verif_steps`; `mean_len_3s` usa `n_target_cycles`. Se in una finestra ci sono `R` replay,
`mean_len_3s = spec_mean_len_3s · V/(V+R)`. [L, algebra [D]]

## 3. KV ring e rollback parziale: cosa fanno per ciclo e quanto costano

**Il KV ring** (`LLAMA_KV_RING=1`, `LLAMA_KV_RING_VRAM_TOKEN=2048`) **non fa niente per ciclo nel mio
blocco**. È una decisione di **collocazione** presa a costruzione della memoria:
`src/llama-kv-cache-dsv4.cpp:182-186` (gate) e `:236-245` (`dsv4_kv_ring_buft` → buffer CUDA "mapped").
L'unica cosa che il mio blocco fa con quella variabile è la stampa dello sha256 a fine risposta
(`server-context.cpp:2219-2224`), che costa **un SHA-256 su tutto il testo generato, una volta per
richiesta** (`kv_ring_output_sha256`, `:48-60`). [L]

**Il rollback parziale** (`LLAMA_KV_ROLLBACK_PARZIALE=1`) è invece **sul cammino caldo**, e nella
configurazione in uso **è raggiungibile**:

- Il bersaglio è DSV4: `llama_kv_cache_dsv4::seq_rm` (`src/llama-kv-cache-dsv4.cpp:1646-1668`)
  **rifiuta ogni rimozione parziale con `p0 > 0`** che non sia il no-op oltre `pos_max`. Perciò
  `common_context_can_seq_rm(ctx_tgt)` (`common/common.cpp:1481-1520`, che prova
  `llama_memory_seq_rm(mem, 0, 1, -1)` dopo 2 token) restituisce **`COMMON_CONTEXT_SEQ_RM_TYPE_FULL`**.
  → `use_ckpt_tgt == true` a `:4103-4105` **sempre**. [L]
- Quindi il ramo `if (n_rollback > 0 && use_ckpt_tgt)` a `:4116` **si raggiunge a ogni accettazione
  non piena**, e chiama `llama_memory_seq_rm_tail(mem_tgt, slot.id, p0)` (`:4122`).
- `p0` è calcolato a `:4119-4120` come `pos_next(n_tokens - n_draft + |accepted| - 1)`, cioè la posizione
  del primo token rifiutato. Con n-max 1 e `|accepted| == 1`: `p0 = pos_next(n_tokens - 1)`. [L]

**Costo per ciclo del rollback parziale** (`llama_kv_cache_dsv4::seq_rm_tail`, `:1582-1642`):
- tre guardie **O(1)**: coda ≤ `rb_margine` (difetto 4, `:1608`), `p0 >= rb_pos_min_ultimo[seq]`
  (confine dell'ultimo ubatch, `:1616`), `p0 > 0` (`:1600`);
- se passano: **una sola** `kv_raw->seq_rm(seq_id, p0, -1)` (`:1626`) — rimozione di **al più 4 celle**
  dalla cache grezza;
- **nessuna copia**, **nessuna sincronizzazione**, nessuna riscrittura delle righe compresse
  (il commento `:1631-1634` spiega che restano scritte ma invisibili perché la visibilità è derivata
  dalla posizione);
- aggiorna `rb_pos_min_ultimo[seq_id] = p0` (`:1638`) e `++rb_n_ok`. [L]

**Contro cosa si misura**: il cammino alternativo (`:4136-4176`) fa `ckpt.load_tgt` (uno
`state_seq_set_data` da ~11,7 MiB), `common_context_seq_rm`, `ckpt.load_dft`, `prompt.tokens.keep_first`,
ripristino del sampler clonato, **e poi un intero ciclo di forward che non verifica nessuna bozza nuova**.
Il commento a `:4109-4111` quantifica: **13,2% dei cicli a n-max 1**. [L per il commento; il 13,2% è
un numero dell'autore, **[D]** rispetto al codice]

Il **prezzo** del rollback parziale, dal lato memoria, è `rb_margine` righe di margine allocate
nell'anello (`LLAMA_KV_ROLLBACK_MARGINE`, difetto 4, `src/llama-kv-cache-dsv4.cpp:73-83`).

**Un dettaglio che conta**: quando `rb_parziale` riesce, la coda della **bozza** non viene toccata dallo
stesso rollback; `:4212` chiede comunque `common_context_seq_rm` sul `ctx_dft` perché
`ctx_dft_seq_rm_type` non è FULL (la bozza è una iswa normale che il parziale lo sa fare —
affermazione del commento a `:4213-4216`, **[D]** perché il tipo si stabilisce solo a runtime a `:1414`). [L/D]

## 4. Percorso di arresto pulito

**Esiste, ed è solo per segnale.** `tools/server/server.cpp`:

- `signal_handler` (`:162-171`): al **primo** segnale chiama `shutdown_handler(signal)`; al **secondo**
  (`is_terminating.test_and_set()`) fa `exit(1)` immediato. [L]
- Registrazione (`:573-586`), **solo se `!is_run_by_cli`** (cioè `argv != nullptr`, che è il caso quando
  si lancia `llama-server`):
  - POSIX: `sigaction` su **SIGINT** e **SIGTERM** (`:578-579`);
  - Windows: `SetConsoleCtrlHandler` che gestisce **solo `CTRL_C_EVENT`** (`:581-584`). [L]
- `shutdown_handler` in modo normale (`:565-568`) chiama `ctx_server.terminate()`, che sblocca
  `start_loop()` (`:613`). Poi `clean_up()` (`:528-535`):
  1. `server_stream_session_manager_stop()` — **prima di tutto**, così le sessioni SSE vive vengono
     finalizzate e i lettori in attesa svegliati;
  2. `ctx_http.stop()`;
  3. `ctx_server.terminate()`;
  4. `llama_backend_free()`.
  Infine `ctx_http.thread.join()`, `monitor_thread.join()` e `common_memory_breakdown_print(ll_ctx)`
  (`:624-627`). [L]
- `llama_server_terminate()` (`:178-183`) è il punto di uscita per l'uso **embedded**: invoca
  `shutdown_handler(0)`. [L]

**Endpoint HTTP di arresto**: **non esiste** in modo normale. Le rotte registrate (`:361-389`) non
comprendono nessuno stop/shutdown; `/models/unload` (`:356`) esiste **solo in modo router**
(`is_router_server`), e lì `shutdown_handler` fa solo `ctx_http.stop()` (`:518-525`). [L]

**Buco su Windows**: il handler copre solo `CTRL_C_EVENT`. `CTRL_CLOSE_EVENT` (chiusura della finestra
della console), `CTRL_BREAK_EVENT`, `CTRL_LOGOFF_EVENT`, `CTRL_SHUTDOWN_EVENT` **non sono gestiti** →
il processo muore senza `clean_up()`, senza finalizzare le sessioni di stream e senza
`common_memory_breakdown_print`. Sulla nostra macchina questo è il modo più comune di fermare il server. [L]

---

# COSE CHE NON TORNANO

1. **`LLAMA_CACHE_ESPERTI_DMA` è una leva fantasma nel manifesto.** È letta a
   `server-context.cpp:4009` e `:4093` (due `static` indipendenti nello stesso file) ma **non compare**
   nell'elenco `server_manifesto_leve` (`server.cpp:36-109`). Il record di lancio, che è la nostra difesa
   contro i verdetti presi nel regime sbagliato, non la stampa. Inoltre entrambi i suoi rami sono morti
   oggi, quindi `llama_cache_esperti_dma_prefetch()` non è mai chiamata dal server. [L]

2. **`getenv("LLAMA_KV_RING")` a `:2219` non confronta con `"0"`.** È l'unico sito del repo con questa
   forma; `LLAMA_KV_RING=0` (che spegne l'anello ovunque) lascerebbe **accesa** la stampa sha256.
   Chiunque tenti un braccio "anello spento" continua a pagare uno SHA-256 per risposta e a vedere una
   riga `[kv-ring-output]` che suggerisce il contrario. [L]

3. **`spec_replay` non viene azzerato in `reset()`.** Il campo è dichiarato a `:199-202` e messo a `true`
   a `:4154` prima del `return` del cammino di ripristino; viene rimesso a `false` solo a `:4201`, cioè
   nel ciclo successivo. Ma `reset()` (`:353-400`) azzera quattordici campi di statistica e **non tocca
   `spec_replay`**. Se lo slot viene rilasciato mentre è in stato di replay (per esempio perché
   `process_token` incontra una stop-string durante il replay), la richiesta successiva parte con
   `spec_replay == true` e **la sua prima verifica non entra nelle statistiche di accettazione**
   (guardia a `:4197`). Con `LLAMA_ACCEPTMOE` acceso sarebbe anche un disarmo spurio (`:3790`). [L]

4. **`graphs reused` è per-contesto ma viene stampato come se fosse per-richiesta.**
   `llama_perf_context(ctx_tgt).n_reused` (`:727`) non viene mai azzerato dal server: il numero della
   seconda richiesta include la prima. Chi confronta due richieste della stessa sessione confronta due
   somme parziali. [L]

5. **`cache_hits_3s` è per-contesto ma normalizzato per slot.** `llama_cache_esperti_get_stats`
   (`:659`) somma i contatori di **tutti i backend** del contesto (`src/llama-context.cpp:3758-3771`).
   Con `-np 1` è corretto; con np>1 la finestra di uno slot ingloberebbe i lookup degli altri.
   Non è un problema oggi, ma è un contatore che cambia significato con la configurazione. [L]

6. **`common_sampler_clone()` a `:4080` si paga a ogni ciclo con bozza**, anche quando l'accettazione è
   piena e il clone non serve. È un salvataggio "in caso servisse" ripristinato solo a `:4173`.
   Su n-max 1 con accettazione ~50% metà dei cloni sono buttati. (Codice upstream, non nostro — ma è sul
   cammino caldo del regime che misuriamo.) [L]

7. **Il cronometro dei checkpoint tiene statistiche `static` di processo, non di slot** (`:3122-3123`).
   Con np>1 mescolerebbe gli slot. Irrilevante oggi (np=1), ma la riga di log dice "salvataggi" senza
   qualificare a chi appartengono. [L]

8. **`DEBUG_TIMINGS` è codice morto per compilazione** (`:2830` la define è commentata). Con essa
   verrebbe anche accesa una `llama_synchronize(ctx_tgt)` esplicita a `:2910` **dentro il ciclo dei
   sotto-batch** — cioè un confine CPU-GPU in più per sotto-batch. Chi la accendesse per misurare
   cambierebbe il regime che sta misurando. Vale la pena scriverlo accanto alla define. [L]

9. **Il cammino di ripristino aggiorna le statistiche in due posti diversi**: `update_spec_stats` a
   `:4147` (ramo checkpoint, prima del `return`) e a `:4198` (ramo normale). Il ramo del **rollback
   parziale** non fa `return`, quindi cade su `:4198` — corretto, ma la simmetria è fragile: qualunque
   `return` aggiunto fra `:4132` e `:4197` perderebbe silenziosamente una verifica. Nessun assert lo
   protegge. [L]

10. **`n_target_cycles` conta per *vista di sotto-batch*, non per iterazione di `update_slots`**
    (`:3879-3891`, dentro `decode()`). Oggi coincidono (2 token in una vista sola). Se il batch di
    verifica dovesse mai eccedere `n_batch` — o se un prompt lungo venisse decodificato mentre lo slot è
    già `GENERATING` — `ms_cycle_3s` e `mean_len_3s` cambierebbero denominatore senza che nulla lo
    segnali. [L]

11. **Il `TODO` a `:3893-3895` [TAG_SPEC_AVOID_DRAFT_REEVAL] è ancora aperto**: `common_speculative_process`
    viene chiamata **dopo ogni** `llama_decode` del bersaglio, replay compresi. Nel ciclo di replay si
    paga quindi un `llama_encode` + un `llama_decode` sulla bozza per iniettare stati che il ciclo
    precedente aveva già iniettato. Sui ~13% di cicli di ripristino è lavoro puramente perso. [L per il
    sito e la struttura; il fatto che sia *identico* al ciclo precedente è **[D]**]

12. **`server-schema.cpp:212-215` espone `speculative.conf_min` come campo scrivibile via `/props`**,
    ma la nostra configurazione non usa `conf_min` (non compare nella CLI). Il ramo che lo consuma
    (`common/speculative.cpp:1211`, `conf = params.conf_min > 0.0f ? ... : nullptr`) è quindi **spento**:
    il difetto di `conf_min` è `0.0f` (`common/common.h:334`), quindi `conf == nullptr` e la condizione a
    `:1227` è sempre falsa. Con lui è inerte anche la leva `LLAMA_SPEC_CONF_ESENTA_POS0`
    (`common/speculative.cpp:1219-1222`), il cui effetto vive solo dentro `conf != nullptr`. Una leva del
    manifesto (gruppo `spec`) che oggi **non può fare niente** qualunque valore abbia. [L]
