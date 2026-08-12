# DSPARK-2fix3 — diagnosi del blocco mailbox (fuori perimetro drafter) + attribuzione dei 99 ms

Data: 2026-07-29. Tree bersaglio: `ds4-p4a` CORRENTE (= tree del binario
3585BEBD132A4573; verificato: ds4.c corrente == preimage fix2 + dspark2fix2, hash
sotto). `dspark2fix3.patch`: solo `ds4-p4a/ds4.c`, 24 inserimenti / 2 sostituzioni
(attribuzione per-passo nel summary — il pezzo IN perimetro). Il blocco del Fatto 2
è del route worker/tiering, NON del drafter: qui c'è la diagnosi completa con
file:riga da passare a chi di dovere. `git apply --check` PASS. Niente build.

## FATTO 2 — il blocco: catena ricostruita, con file:riga

### La sequenza esatta

seq/gen contano solo i job single-token del route worker (43/token; il batch non
li usa). 129 = 3×43. Il ciclo 2 aveva `k_accepted=0` = free-check miss ⇒ al token
2 NESSUN batch-verify è girato. Il PRIMO batch-verify in fase decode della storia
di questa config gira al ciclo 3 (il drafter GPU non ha mai consegnato: percorso
vergine), cioè FRA seq 129 e seq 130. Poi:

1. Token 4, layer 0 ⇒ submit gen 130 (`cuda_moe_gpu_resident_routes_begin`,
   ds4_cuda.cu:47155; attesa consumo prior a 47280-47305; claim slot a
   47312-47333). Il worker-claim di 130 (31317-31385) valida l'handoff della 129
   e PASSA: l'evento consumer-done della 129 era stato registrato dal decode
   thread — unico call-site `ds4_gpu_moe_route_consumer_done()` in coda a
   `metal_graph_encode_decode_layer`, **ds4.c:14176-14181** (il batch-verify non
   lo chiama e non ne ha bisogno: non crea generazioni). NOTA:
   `route_consumed_sequence/generation` sono scritti AL CLAIM (31380-31383),
   PRIMA della validazione della richiesta.
2. La RICHIESTA 130 è bocciata dal precheck del worker
   (**ds4_cuda.cu:42193-42232**) ⇒ `precheck_failure_reason="request-invalid"`
   (**42286**, UNICO produttore della stringa; funnel a 42382-42385) ⇒ riga
   `route worker failed seq=130 layer=0 routes=6 misses=6 reason=request-invalid
   cuda=none` (42843).
3. Layer 0 abortisce ⇒ `consumer_done(130)` non gira mai ⇒
   `route_consumer_event_generation` resta 129 (store: ds4_cuda.cu:31604).
4. Il submit successivo (gen 131) claima il suo slot (stato legittimamente
   `gpu-writing`), e il worker-claim di 131 valida la PRIOR 130:
   `recorded_generation(129) != prior(130)` ⇒ **"consumer-event-generation"**
   (**31341-31351**) ⇒ failed-closed (31286-31315) ⇒ "cuda decode failed".

**Risposta alla domanda "chi doveva rilasciare lo slot"**: la riga
`generation=131 observed_generation=131 state=gpu-writing` stampa i campi dello
slot CORRENTE (131), che è in gpu-writing per costruzione (appena claimato dal
begin): è un red herring. Il mismatch è sull'EVENTO della generazione 130, che
doveva registrare il decode thread via `ds4_gpu_moe_route_consumer_done`
(ds4.c:14180) e non ha registrato perché il layer era già morto al passo 2. Il
mancato rilascio è EFFETTO del guasto, non causa. Il ring gen&1 non ha wrappato
male: tutti i numeri stampati sono coerenti con questa catena.

### Il predicato radice e la sensibilità al tempo

**NON è sensibile al tempo.** In questa catena non c'è nessuna deadline: il
"request-invalid" è un check di CONTRATTO sul contenuto della richiesta (la firma
a deadline è quella del drain4: `reason=none`, guardiano I/O — diversa, come
correttamente notato). Termini del precheck (42193-42232) per una richiesta
single-token di decode:

| riga | termine | esito atteso |
|---|---|---|
| 42194-42197 | route_count 1..6, miss<=route, layer<43 | ✓ costanti (stampati: 6/6/0) |
| 42198-42199 | gate/down_expert_bytes == cache | ✓ costanti del modello base |
| 42200-42201 | epoch G133 valida | pass (richiede DS4_G133_TIER=1 + enforce per essere armato) |
| 42202-42208 | sparse bake selected | assente (no bake) — **stampa se fallisce** |
| **42221-42227** | **compose prefill-mass-tiering: `g_dynamic_arena.snapshot_generation != g_moe_tiering.snapshot_generation`** | **UNICO ramo SILENZIOSO** |
| 42228-42232 | tick (solo overflow uint64) | impossibile — e stampa |
| 42250-42269 | selected 0..255 (solo tiering attivo) | **stampa se fallisce** |

**Candidato principe: 42221-42227.** Il batch-verify serve i propri esperti con
lo staging a WAVE del ramo batch del launcher (chiamate a
`cuda_moe_selected_stage_wave`: ds4_cuda.cu:48806/48912/49088), che transita
dall'arena dinamica e può avanzare `g_dynamic_arena.snapshot_generation`; il lato
tiering resta alla generazione pre-verify; la PRIMA richiesta single-token dopo il
verify fallisce il confronto IN SILENZIO. Combacia con: determinismo (sempre il
primo token dopo il primo verify), assenza di deadline, e assenza (apparente)
della riga di dettaglio.

**Discriminatore da una riga** (nel log già esistente del run): subito prima di
"route worker failed seq=130" c'è oppure NO la riga
`ds4: [gpu-route-request] result=invalid sequence=130 ... gate_bytes=X/Y ...`
(stampata a 42210-42219)?
- **NO** ⇒ è il ramo silenzioso 42221-42227 (compose snapshot): confermato.
- **SÌ** ⇒ i campi stampati nominano direttamente il termine fallito.

**Fix suggerito a chi di dovere** (route worker/tiering, fuori dal mio
perimetro): (a) strumentare il ramo 42221-42227 con una riga
`result=invalid-compose-snapshot arena=%llu tiering=%llu` (oggi è l'unico veto
muto del precheck); (b) risincronizzare la snapshot generation del tiering quando
una pubblicazione d'arena avviene in FASE DECODE (batch-verify), o esentare dal
confronto le pubblicazioni non-prefill. Ripiego immediato per il runner: braccio
NextN con la leva compose/tiering spenta, se l'assetto lo consente.

### Q1 e Q3 — l'ancora D2H è esonerata

`ds4_gpu_tensor_read` (**ds4_cuda.cu:9221-9229**) per cur_hc/batch_cur_hc è una
`cudaMemcpy` DeviceToHost sullo **stream legacy** (sincronizza l'intero device).
Non legge né scrive alcuno stato della mailbox (atomics host + un solo cudaEvent
registrato dal decode thread stesso): può solo rendere l'ordinamento PIÙ stretto
— semmai fa trovare l'evento consumer-done già completo al claim successivo. Il
trigger è il batch-verify, non il D2H. (Q3: volendo, esiste comunque la via senza
D2H nuovo — il ring pinnato `ds4_gpu_tensor_read_async_ordered_slot`, lo stesso
di shared1 — ma non serve al caso.)

### Q2 — perché il terzo token

Perché è il primo token DOPO il primo batch-verify mai eseguito in fase decode su
questa config. Non c'entrano il secondo re-base (il ciclo 2 non ha nemmeno
verificato: free-check miss) né il wrap del ring.

## FATTO 1 — dove vivono i 99 ms (quantificazione)

Composizione del passo con PIN=1: denso 178,5 MB (pinnato) + testa 536,6 MB
(pinnata) + 6 esperti ≈ 85 MB (NON pinnati: solo prewarmed). I numeri misurati si
decompongono così:

- `head=36,8 ms` per 536,6 MB ⇒ **14,6 GB/s**: la banda DRAM effettiva durante il
  decode vivo (H2D del route worker + 12 thread di pool + decode thread) è
  ~15 GB/s, non i 35-44 GB/s del mio conto — che valeva a memoria scarica.
  Prima correzione: il pavimento reale della testa è ~30-37 ms.
- `fwd=96,3 ms` ⇒ denso pooled ~10-12 ms + **routed ~85 ms ⇒ ~1,0 GB/s = i 6
  esperti si RIPAGANO DA SSD a ogni passo**: il prewarm degli esperti (fatto a
  engine-open) è stato sfrattato dalla page cache durante il prefill 150k
  (minuti di streaming della mappa primaria + KV host). 85 MB a velocità di
  fault ≈ 80-90 ms. 99 ≈ 85 + 10 + spiccioli: torna.

Terapia, nell'ordine:
1. **`DS4_NEXTN_PIN=2` nel runner** (già implementato in fix2): blocca anche il
   pool esperti (+3,54 GiB; working set totale ≈ 4,27 GiB). Con gli esperti
   pinnati il termine da 85 ms diventa ~5-8 ms.
2. **Aspettativa rivista (onesta)**: passo ≈ **45-60 ms** a regime (testa 30-37
   alla banda contesa + denso 8-12 + esperti pinnati 5-8), non i 19-24 del conto
   a banda piena. Ciclo k=7 = 8 passi ≈ 360-480 ms > finestra ~230 ms: con la
   catena persistente e il re-base si consegna comunque (k_eff ~3-5 per
   finestra), oppure `DS4_NEXTN_DRAFT_K=4..5` per stare in finestra. Sotto i
   ~35 ms/passo si scende solo tagliando i byte della testa (GPU head =
   arbitraggio del command context, fuori perimetro; requant fuori mandato).
3. **Il patch di questa consegna**: attribuzione per-passo nel summary —
   `fwd_q4_avg` (esperti routed: l'unico working set non pinnato a PIN=1),
   `fwd_dense_avg` (Q8/attention/router/prequant), `head_avg`. Il prossimo run
   VERIFICA la decomposizione senza interpretazioni: se con PIN=2 `fwd_q4_avg`
   crolla da ~85 a <10, confermato; se resta alto, il collo è altrove e i tre
   numeri dicono dove.

## Hunk del patch (righe preimage) e neutralità

- ~9950 (struct drafter): +3 accumulatori `stat_q4/dense/head_ms_sum` (+ commento).
- ~10105 (worker): telemetria dspark1 agganciata al forward (`step_tm` al posto
  di NULL) e accumulo sotto mu accanto alle stats esistenti.
- ~20510 (request_begin): reset dei tre campi.
- ~20530 (request_end): summary esteso con `fwd_q4_avg/fwd_dense_avg/head_avg`.

Tutto dentro codice dspark2 (flag-gated); a flag spento zero costi nuovi. Nessuna
riga di shared1/dspark1/drain4/drain4fix/logids toccata. La telemetria dspark1 nel
forward aggiunge ~4 letture d'orologio per sezione routed per passo: trascurabile
rispetto ai ms in gioco.

## Verifiche eseguite

- `git apply --check .microbench/dspark2fix3/dspark2fix3.patch`: PASS sul tree
  corrente; `--numstat`: `24  2  ds4-p4a/ds4.c` (unico file).
- Tree corrente verificato == preimage fix2 + dspark2fix2 (ricostruito e hashato).
- Bilanciamento `{} () []` sul file patchato: OK.
- Nessuna compilazione, nessun server, D:\ non toccato.

## SHA-256

Preimage (tree corrente = tree del binario 3585BEBD132A4573):

```text
ds4-p4a/ds4.c
716718325c7f3d8e57543301419c3f586b62de8ea0710b7fe4f6e9111dbbcd58
```

Artefatto patch:

```text
.microbench/dspark2fix3/dspark2fix3.patch
9ef391bfaea7f1e75f663206cad7083641d0ce231d7a8e96a8388c13375b6003
```
