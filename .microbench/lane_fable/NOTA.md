# IMA lane G132 sul percorso generale: causa trovata e correzione

## Verdetto sull'indiziato

L'indiziato del mandato (l'installazione di `cuda_moe_route_worker<false, true>`
con `DS4_G73_OPEN=0`) e' **corretto come localizzazione ma non come meccanismo**.
L'installazione della specializzazione non tocca puntatori, slot o stream:
assegna un puntatore a funzione. Il guasto non e' nemmeno nello staging del
modello: gli errori su `q8_0_pair0`/`q8_0_pair1` sono la **prima osservazione**
di un errore CUDA asincrono e sticky prodotto prima, da un kernel del percorso
MoE. Una volta che un kernel fa un accesso illegale, ogni successiva chiamata
CUDA dello stesso contesto (staging record a `ds4-p4a/ds4_cuda.cu:8400`, range
alloc a `:3933`, synchronize, KV restore a `:21286`, la query dello stream in
`cuda_moe_route_upload_stream_quiesce` a `:31033`) restituisce lo stesso
errore. La quarantena `site=cancel-and-join` (`:31048`) e' teardown, non
sorgente.

## La causa vera (catena completa, con file:riga)

Ambiente di campagna: `DS4_CUDA_MOE_SPLIT_FUSED=1` e' lo standard dei run P4A
(vedi `reap-loop-p4a-ledger-sparse/docs/EXPERIMENTS_LEDGER.md:6180` e decine di
repliche). Quindi il primo MoE di decode del percorso generale entra nel ramo
split, non nel ramo che consuma il piano CPU.

1. `ds4_gpu_routed_moe_one_tensor` (`ds4-p4a/ds4_cuda.cu:48695`) usa il
   dispatch generale `routed_moe_launch_impl<false, true>`.
2. Con split richiesto, il launch chiama
   `cuda_moe_gpu_resident_routes_begin<G73, G132>` (`:46729`), che passa
   `cpu_lane_allowed = G132 ? 1 : 0` al resolver (`:46093`).
3. Il resolver device (`moe_resolve_resident_routes_kernel`) scrive
   `route_ptrs = {0,0,0}` per **ogni** route miss (`:25686-25688`) e il bit
   della hit mask resta 0 (`:25676-25692`). I puntatori delle miss vengono
   pubblicati solo dopo, dal worker, con
   `moe_publish_transient_route_kernel` (`:25768`).
4. Il route worker `cuda_moe_route_worker<false, true>` esegue
   `cuda_moe_tiering_enforce_request<false, true>`; per una miss transiente
   eleggibile `cuda_g132_general_plan_admit` (definizione `:39650`, chiamata
   `:40609`) la assegna alla CPU e
   il `continue` a `:40624` **salta sia l'H2D sia la publish**: i suoi
   `route_ptrs` restano zero, il suo bit hit resta 0. Questo e' il
   comportamento voluto della lane — ma solo il consumer non-split lo gestiva.
5. Il consumer non-split riconosce il piano solo con
   `!use_split_fused && !use_split_hit_miss` (`:46835-46841`,
   `g132_general_candidate`). Nel ramo split (`:47918`) il piano non viene
   mai consumato: dopo `finish()` (`:47963`) i kernel della passata miss
   (`select_hits=0`) processano **tutti** gli slot con bit hit 0, compresa la
   route assegnata alla CPU:
   - `moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel` a `:48086` dereferenzia
     `route_ptrs[slot]` e `route_ptrs[n_expert+slot]` senza alcun controllo di
     nullita' (`:25603-25609`);
   - `moe_down_ptrs_masked_qwarp32_kernel` a `:48110` e
     `moe_down_split_fused_finish_qwarp32_kernel` a `:48121` dereferenziano
     `down_ptrs[slot]` (`:26758-26760`, `:26792-26795`).
   Lettura da indirizzo ~0 sul device → **illegal memory access**, asincrono,
   che avvelena il contesto.

## Perche' si manifestava prima di `calls=1`

`general_calls` viene incrementato solo dentro
`cuda_g132_cpu_lane_wait_and_join` (`:49913`), raggiungibile solo via
`g132_general_active`, cioe' solo dal consumer non-split. Nel ramo split la
lane non veniva mai agganciata: il worker creava il piano (route claimate),
i kernel miss dereferenziavano gli zeri, e il join non veniva mai eseguito.
Quindi `calls=0`, `route_cpu=0` e' coerente: il contatore conta i **join
completati**, non i tentativi. `seq=1` nella quarantena conferma che la prima
richiesta route e' stata l'ultima: il contesto e' morto li'.

Non e' il calcolo CPU (mai partito), non e' il join (mai raggiunto), non e' il
bilanciatore (mai consultato): e' il **contratto di pubblicazione delle route
violato verso un consumer (split) che non era stato aggiornato**.

## Nota sul lavoro parallelo in `.microbench/lane/`

La diagnosi in `.microbench/lane/NOTA_FIX.md` coincide con la mia e la
confermo in ogni punto meccanico. Il loro `fix.patch` pero' ha due difetti,
per cui consegno il mio:

1. **Non compila**: passa `hit_mask` (dichiarato `const uint32_t *` a
   `:47922`) al parametro `uint32_t *route_hit_mask` del loro kernel.
   Conversione `const T* -> T*` e' un errore hard di compilazione.
2. **Piano orfano nei rami senza attach**: se dopo `finish()` `ok==0`, o se
   scatta il replay G73, il loro fix salta l'attach ma non rilascia il piano.
   Restano trattenuti i reader arena e soprattutto il lease
   `route_cpu_staging_generation`: il claim del mailbox successivo fallisce
   chiuso con `cpu-staging-reader-active` (`:30927-30932`), trasformando un
   errore transitorio in un percorso route permanentemente morto.

## Cosa ho cambiato (fix.patch, 3 hunk, +125/-0)

1. **Nuovo kernel** `moe_g132_split_own_cpu_routes_kernel` (dopo `:25819`):
   su stream 0, azzera gli slot `split_down` delle route CPU e fa OR di
   `cpu_mask` nella hit mask device.
2. **Aggancio/rilascio nel ramo split** (dopo il blocco finish/replay,
   `:48016`): se `route_cpu_plan.cpu_count != 0`:
   - con `!ok || g73_split_replay`: rilascio del piano con
     `cuda_g132_general_plan_release` (saltato solo se
     `route_worker_safe_leaked`, dove un worker detached potrebbe ancora
     possedere il piano e la semantica e' "leak deliberato");
   - altrimenti: `cuda_g132_cpu_lane_prepare_general` (stesso contratto del
     consumer non-split: sequence/generation/layer, formato nativo IQ2_XXS
     gate/up + Q2_K down, 7.077.888 byte), `cuda_g132_cpu_lane_begin_general`
     (copia input 16 KiB + avvio worker CPU), poi il kernel di ownership.
     Su fallimento: fail chiuso con rilascio/cancel, mai kernel miss su
     puntatori zero.
3. **Coda del ramo split** (`:48145-:48159`): `cancel_dispatch` sui due
   return G73 post-attach; poi, se attiva,
   `end_general_gpu` + `wait_and_join(out, ...)` che somma il parziale CPU
   da 16 KiB su stream 0. Identico al pattern gia' usato dal consumer
   non-split.

## Perche' e' sicuro

- **Ordinamento stream**: i kernel hit sono gia' accodati su stream 0 prima
  del kernel di ownership e vedono la mask originale; i kernel miss sono
  accodati dopo e vedono i bit CPU a 1, quindi saltano gli slot CPU. La mask
  e' letta dai kernel **dal device** (`:25588`, `:26756`, `:26783`), non da
  un valore host: la mutazione device-side e' effettiva. L'unico altro
  scrittore della mask e' il resolver della richiesta successiva, che la
  riscrive per intero (`:25692`), sempre su stream 0: nessuna corsa.
- **Riduttori esatti**: `moe_sum_kernel` (`:27319`) somma tutti gli slot di
  `split_down`; il fused finish somma `hit_down[slot]` per i bit 1. Gli slot
  CPU sono azzerati dal kernel di ownership, quindi entrambi aggiungono uno
  zero esatto; il contributo vero arriva dal join (add su stream 0 dopo il
  riduttore: ordine di stream garantito).
- **Nessun cambiamento con flag spenti**: tutto il codice host nuovo e'
  dentro `if constexpr (G132)`; nelle istanze `<false,*>` e `<*,false>` non
  esiste nel binario del percorso (il kernel nuovo esiste come simbolo, come
  gia' il kernel di compaction di lane.patch, ma non viene mai lanciato).
  Contatori e comportamento a flag spenti: invariati cifra per cifra.
- **Nessuna modifica prima dell'ingaggio**: con piano vuoto
  (`cpu_count == 0`) il ramo split e' bit-identico al pre-patch: nessun
  evento, nessun kernel, nessuna scrittura. Model staging e upload stream
  non sono toccati in alcun punto del fix.
- **Niente Q1/IQ1**: il ramo split e' raggiungibile solo con
  `!route_iq1_s && !route_q1_0` (`:46708-46716`, `:46722`);
  `prepare_general` impone il contratto nativo IQ2_XXS+Q2_K. Il dispatch
  mixed/Q1 resta `<false,false>` / `<G73,false>`, MTP resta `<false>`.
- **Niente ammissione/residenza/soglie/vittime/dimensionamento**: il fix
  tocca solo hit mask (stato per-richiesta), slot `split_down` delle route
  CPU (scratch per-richiesta) e il ciclo di vita del piano gia' introdotto
  da lane.patch.
- **Rilascio senza corse**: il rilascio consumer-side avviene solo quando il
  worker e' provabilmente fuori dalla richiesta: `finish()` fallito passa da
  `cancel_and_join` (thread joinato) o da `route_failed` (il worker ha gia'
  rilasciato il piano nel suo ramo `!ok` a `:40860` prima di pubblicare il
  fallimento: il mio release e' idempotente su piano azzerato) o dal
  contratto telemetrico fused (`:46400`, worker idle). Il caso safe-leaked
  (worker detached, `:31071-31088`) e' escluso esplicitamente.
- **Overlap**: nel ramo split l'evento input viene registrato dopo la
  passata hit, quindi la CPU parte piu' tardi che nel ramo non-split e si
  sovrappone solo alla passata miss. E' una perdita di overlap misurabile
  (gpu_wait_cpu_ms), non un errore: il bilanciatore la vede e riduce il
  target CPU se non rende. Anticipare l'evento prima delle hit
  significherebbe toccare lo stream anche quando nessuna route e' CPU,
  violando il vincolo 2 del mandato.

## Residuo noto, dichiarato (non introdotto dal fix)

Se `begin()` fallisce **dopo** aver lanciato il resolver (es. timeout
`request-consume-timeout`) il launch esce a `:46758` con piano potenzialmente
non rilasciato (stesso limite del lane.patch originale sul ramo non-split).
Non puo' produrre IMA (nessun kernel viene lanciato per quella richiesta e il
resolver successivo riscrive mask e puntatori); puo' lasciare lease/reader
orfani su un percorso che ha gia' fallito chiuso. Rilasciarlo li' non e'
provabilmente sicuro (il worker puo' essere ancora dentro la richiesta
precedente), quindi non l'ho toccato: serve la prova worker-done
(route_completed_*) che oggi non e' esposta in quel punto.

## Verifiche eseguite (statiche, come da mandato)

- Nessuna compilazione, nessun `ds4_server`, nessun accesso a `D:\`,
  nessun file modificato fuori da `.microbench/lane_fable/`.
- `git apply --check --whitespace=error-all .microbench/lane_fable/fix.patch`
  sul working tree corrente: OK.
- `git apply --numstat`: `125 0 ds4-p4a/ds4_cuda.cu`.

## SHA-256

Preimage su cui e' prodotto il diff (working tree corrente, lane.patch gia'
applicato):

```text
7CC4377593E054D9BD4FFB97A4091F351FE9FAD3FB8C6B89276D0A1534D0029D  ds4-p4a/ds4_cuda.cu
```

Artefatto consegnato:

```text
9FDF8C7EECEFE3F6D80553E7764101C43E5361D009F50FAC892E5737107360D2  .microbench/lane_fable/fix.patch
```

Risultato atteso dopo `git apply`:

```text
5688DCD362DEB80FB25A95715A9EF350CBB87C5F9515B56E1D31D041FFFA51B4  ds4-p4a/ds4_cuda.cu
```

Nota di mutua esclusione: questo fix.patch e quello in `.microbench/lane/`
correggono la stessa regione e NON sono applicabili entrambi. Applicarne uno
solo (questo applica pulito sulla preimage dichiarata).
