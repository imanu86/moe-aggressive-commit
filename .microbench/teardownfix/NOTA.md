# TEARDOWNFIX — chiusura del debito di teardown ereditato dal WDDM + raccordi ledger

Data: 2026-07-29. Base verificata = tree corrente (post-rebuild 7821FFA5):

- `ds4-p4a/ds4_cuda.cu` PRE-patch SHA-256
  `F0DD5CFC6E001A61E818F8569E74E9AD07D536C55108418FEF7851712224BA36`
  (identico al perimetro degli audit `.microbench/audit10/10_teardown.md` e
  `05_ledger.md`: i file:riga degli audit sono stati riverificati uno a uno
  sul sorgente, non ripresi sulla fiducia).
- `ds4-p4a/ds4_cuda.cu` POST-patch SHA-256
  `0D6762EF36852CEC8D77189224F29236021203D929BC05B7F91345130A6F7915`.
- Unico file toccato: `ds4-p4a/ds4_cuda.cu` (+380/−30 righe). `ds4.c`,
  `os_file.c` e tutte le zone vietate sono intatti.
- `git apply --check .microbench/teardownfix/teardownfix.patch` pulito dal
  root del repo sul tree corrente; round-trip provato (apply → SHA POST
  esatto → ripristino → SHA PRE esatto). Il tree e' stato lasciato PULITO:
  la patch NON e' applicata.
- Niente build, niente server, D:\ mai toccato.

## Verifica dei claim (tutti confermati, nessuno respinto)

| Difetto | Claim audit | Verificato su |
|---|---|---|
| 10-B1 | sync di cleanup fallita ignorata salvo profilo q1 | :9056-9066 |
| 10-B2 | tracer marca released prima dell'esito API | :677-693 (+ macro :824-831 che instradano TUTTI i siti, incl. :8985-9011) |
| 10-B3 | nessun cudaDeviceReset/PrimaryCtxReset nel file | grep completo |
| 10-B4 | early-return su safe-leak salta l'intero distruttore; in piu' NON ferma nemmeno il worker di una cache quarantinata mid-run | :37707-37744 |
| 10-B5 | ramo detach del rotator non setta il latch; il chiamante fa cudaFreeHost dell'arena coi ring | :36268-36284 vs :9578-9591, :9689-9691; latch settato solo nei rami commit (:34856, :35607, :35735, :36162) |
| 05-B1 | release sincronizza l'upload ma non ritira `transport_deferred`; events_destroy azzera armed senza retire | :37725-37735, :37540-37553, fail-safe :28576-28582 |
| 05-B2 | cancel post-arm non decide il pendente | :31748-31805 (unico poll dentro il while del worker :42443-42450) |
| 05-B3 | `final` puo' dichiarare complete=1 col batch di coda omesso | :28710-28717, snapshot :28625-28650 |

## Come sono stati chiusi

**10-B1** — `ds4_gpu_cleanup`: la sync fallita viene loggata SEMPRE
(`[teardown] cleanup synchronize failed ... action=retry-once`), un solo
retry bounded dopo `cudaGetLastError()`, e lo stato entra nella nuova riga
di bilancio finale `[teardown] result=clean|degraded sync=... 
release_failures=... safe_leak_residual=... device_reset=...`, emessa
sempre (anche a tracer spento). Il blocco q1-profile preesistente resta.

**10-B2** — i tre wrapper (`ds4_trace_cuda_free/_free_host/_host_unregister`)
chiamano prima l'API e scalano il live-set SOLO su `cudaSuccess`; un esito
respinto incrementa `g_alloc_release_failures` (atomic, sempre attivo).
Campo `release_failures=` aggiunto a `[cuda-alloc-summary]` e alla riga
`[teardown]`. Il campionamento pre-free del picco VRAM resta prima della free.

**10-B3** — `cudaDeviceReset()` come ULTIMA operazione di `ds4_gpu_cleanup`,
dietro `DS4_CUDA_DEVICE_RESET_ON_EXIT` **default ON** (=0 per spegnerlo).
Motivo per cui il default ON regge: gira solo a processo morente, dopo tutti
i release, quindi non tocca le misure del run; rende sincrono il ritiro del
primary context invece di lasciarlo al process exit (il candidato dei 300 s
del secondo server). Guardia obbligatoria (dall'audit): il reset e' SALTATO
(`device_reset=skipped-safe-leak`) se resta un proprietario vivo — worker
detached, cache quarantinata non riqualificata, pread kernel pendente, o
latch arena (`g_cuda_dynamic_arena_storage_safe_leaked`) — perche' il reset
libererebbe lo staging host-pinned che quei proprietari possono ancora
scrivere. Unico caveat trovato (non un motivo per default OFF): un processo
che riaprisse un engine dopo `ds4_engine_close` paga una re-init lazy del
context; nessun problema di correttezza.

**10-B4** — teardown PARZIALE in `cuda_moe_expert_cache_release`, per
proprieta':
1. *Worker DETACHED* (nuovo latch statico `g_moe_route_worker_detached`,
   settato solo al detach :31772; nessuna struct condivisa cambia layout):
   il thread vivo puo' toccare tutto → full safe-leak come oggi, ma loggato
   (`teardown=degraded reason=route-worker-detached`).
2. *Worker joinato, pread kernel pendente*: il kernel possiede slot pread +
   fette host (`host_gate/up/down` puntano dentro `route_host_*`). Con
   upload stream PROVATO quiescente (poll bounded 5 s, mai piu' sync
   illimitata su cache quarantinata) si rilasciano slab e metadati device,
   eventi DOV, consumer event e stream; restano vivi slot pread, staging
   host-pinned e mailbox zero-copy; `safe_leaked` resta 1 (prepare continua
   a rifiutare, reset 10-B3 vietato). Riga `teardown=partial`.
3. *Worker joinato, nessun pendente, stream drenato*: quarantena evaporata →
   teardown COMPLETO (`teardown=requalified`), il debito non passa al WDDM.
4. *Stream non provato quiescente*: full safe-leak dichiarato
   (`reason=route-upload-stream-busy`).
   In piu' l'early-return cieco e' rimosso: una cache quarantinata mid-run
   ora viene comunque fermata (cancel+join) allo shutdown — prima il worker
   restava VIVO al process exit.

**10-B5** — il ramo detach del rotator `q1-0-ssd-wrap` ora setta
`g_cuda_dynamic_arena_storage_safe_leaked = 1` (stesso contratto del ramo
`commit_safe_leaked`): `cuda_dynamic_arena_storage_release` /
`cuda_primary_dynamic_arena_release` non possono piu' fare `cudaFreeHost`
del ring sotto un I/O detached vivo (UAF chiuso alla radice).

**05-B1** — nuovo `cuda_moe_drain_overlap4_decide_pending_joined(cache,
proven, force)`: con worker provabilmente morto il chiamante e' l'unico
proprietario dello slot `transport_deferred`; commit con la prova esistente
(sync/poll riuscito dell'upload stream o `cudaStreamQuery`==Success),
altrimenti batch omesso con `complete=0` (semantica del batch errato
classico). Chiamato in `release()` PRIMA di `events_destroy` (che azzerava
`armed_generation` orfanando il batch) riusando l'esito del drain — copre
shed PIN2 (:37413) e teardown (:9077), cioe' anche il B6 dell'audit 10.

**05-B2** — decisione nel cancel: dopo il join riuscito il pendente viene
deciso nei rami pread-pendente e post-quiesce (commit se provato ORA, un
NotReady non forzato resta al decisore successivo — release, request-end,
worker respawnato o fail-safe del defer — per non degradare una prova che
piu' avanti sarebbe piu' forte, es. la sync bloccante della release; il
`force=1` esiste solo dove lo stato DOV sta per essere azzerato). Il ramo
detach NON decide mai (lo slot appartiene al thread vivo). Cosi' ogni
percorso post-cancel termina in una decisione o in una dichiarazione.

**05-B3** — `ds4_transport_request_end`: prima della riga `final` il thread
di decode tenta il retire del batch di coda (`..._tail_retire`, finestra
bounded 50 ms ≈ 3× un batch da 6 esperti): con worker vivo aspetta il SUO
poll idle; con worker joinato decide da unico proprietario; con worker
detached non tocca nulla. Se resta pendente, la riga final porta
`pending=1` e `ledger_complete` viene FORZATO a 0; a coda pulita la riga
porta `pending=0`. Le righe `periodic` sono invariate.

## Residui dichiarati (fuori perimetro, non regressioni)

- `retire_at_claim` post-respawn si fida dell'invariante I3 anche dopo un
  abort del consumer: preesistente, non toccato.
- `pcie_busy_pct` resta tempo-per-osservazione (05-B4, BASSA: non in mandato).
- I 4 handle `route_io_qd_event` restano leakati nel caso `partial`
  (conservativo: 4 HANDLE, nessun oggetto CUDA).
