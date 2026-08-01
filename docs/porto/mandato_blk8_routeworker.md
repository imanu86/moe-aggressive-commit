# MANDATO — blocco 8, route worker: e' il passo che ACCENDE

LAVORO DI IMPLEMENTAZIONE. Scrivi codice, nel worktree indicato e SOLO li'.

  IL TUO WORKTREE:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-port-nucleo
                    branch port/nucleo-78, allineato al tronco: contiene adattatore (3),
                    arena (4), observer (5), cache VRAM (6) e tiering (7).
                    **Leggi `PORT_BLOCK7_TIERING.md` e `PORT_BLOCK6_VRAMCACHE.md` PRIMA di
                    scrivere una riga**: il blocco 7 ti ha lasciato un contratto esplicito.
  RIFERIMENTO:      C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a
                    il nostro fork, HEAD af84c42. **SOLO LETTURA.**

**TUTTO CIO' CHE SCRIVI DEVE STARE DENTRO LA TUA RADICE.** Sotto `workspace-write` il resto del
disco e' negato. **Non usare git per scrivere**: il `.git` del worktree sta fuori dalla radice e
`git add`/`git commit` falliranno con *Permission denied*. Leggere con git va bene. Al commit ci
pensa chi ti ha lanciato.

## QUESTO E' L'UNICO BLOCCO CHE ACCENDE, e va capito prima di iniziare

Il nucleo 6-7-8 e' atterrato **spento**, di proposito. Oggi
`ds4_cuda_vram_cache::enabled()` richiede `route_transaction_ready()`, che ritorna **false**
(`src/cuda/vram_expert_cache.cpp:33-44`).

> **Tu installi il route worker e SOLTANTO ALLORA sostituisci quel gate.** Non aggiungere un
> flag che accenda il tiering per conto suo: `reservation`, `victim`, `publish` e `refund` o
> funzionano tutti e quattro insieme, o non si attiva niente.

## LE SETTE CONDIZIONI, scritte dal blocco 7 e vincolanti

Prima di rendere vera quella capacita' devi:

```
1  osservare ID e pesi PRIMA della decisione di enforce
2  serializzare le reservation della richiesta e conservare le generation
3  trattenere ogni reader RAM fino all'evento terminale delle H2D, se rendi le copie asincrone
4  chiamare publish() SOLO dopo drain riuscito
5  chiamare refund() su OGNI uscita fallita o cancellata
6  impedire release/cambio modello mentre esistono reader o reservation
7  conservare il trasporto compatto esatto come fallback
```

**La 5 e' quella che si dimentica**: le uscite fallite sono molte piu' di quelle che vengono in
mente scrivendo il percorso felice.

## L'INVENTARIO, gia' verificato — in `ds4-p4a/ds4_cuda.cu`

```
31922-31928     route_memory_barrier                 7   pubblicazione host/device
31935-32268     deadline e accounting transient    334   deadline, retry, drain
32270-32552     read-whole, prefetch, pread chunked 283   trasporto SSD del worker
32571-32756     cancel/retry/fallback transient    186   recupero bounded e fallback esatto
32758-32787     mailbox_fail_closed                 30   quarantena
32789-32857     mailbox_worker_claim                69   claim generation + prova consumer-done
32859-32878     mailbox_publish_upload              20   WORKER_OWNS -> UPLOAD_ENQUEUED
32880-32888     worker_publish_completed             9   sequence/generation terminali
32895-32924     upload_stream_quiesce               30   prova che il worker joined non ha producer
32933-33008     worker_cancel_and_join              76   stop bounded, join, fail-closed
33010-33061     worker_drain_completed              52   consuma i completamenti prima di reset
33063-33103     ds4_gpu_moe_route_consumer_done     41   *** NON portarla come API pubblica ***
41611-41631     worker_pick_slot                    21
41633-41685     copy_expert_h2d_async               53   H2D packed su upload stream
41687-41727     legacy_copy_expert_h2d_async        41   fallback in tre copie
41729-41814     append/flush publish batch          86
44299-45243     cuda_moe_route_worker              945   IL CUORE
45245-45262     expert_cache_copy_to_compact_async  18   ponte verso il compact fallback
49501-49886     resident_routes_begin              386   generation/mailbox, resolver, publish request
49889-50411     resident_routes_finish             523   attesa, fallback, route valide
50414-50437     resident_routes_submit              24
```

**Il worker copia una request solo dopo aver osservato `sequence`, verifica anche
`host_generation`, poi reclama la mailbox** (`FORK:44335-44411`). Valida geometria ed epoch
(`:44422-44436`), osserva ogni route prima della policy (`:44539-44569`), e chiama l'enforce
solo in modalita' tiering enforce (`:44717-44725`).

**L'innesto e' INTERNO, non una nuova API**: il backend prova il provider resident con
`selected`, `weights`, offset e dimensioni gia' disponibili (`FORK:50739-50790`); nei percorsi
split completa il rendezvous prima della fase miss (`FORK:52046-52050`). **Questa e' la forma
da replicare dietro l'adattatore**, non qualcosa che `ds4.c` chiama.

## COSA NON PORTARE

`init/stage/flush demand pipeline` (`FORK:41816-41948`), G73, G132, nested residual, DOV. Sono
decorazioni, **fuori dal percorso critico** per decisione del piano. E la **demand pipeline e' gia'
stata respinta** una volta perche' violava il vincolo su promozione e pruning.

## UN FATTO MISURATO CHE TI RIGUARDA

Il guardiano della deadline, quando scade, fa **abort -> `cache-invalidate scope=FULL`**, e
questo genera altre miss che generano altri abort: un anello che si autoalimenta. Il conteggio
`bytes=14155776` compare in **26 log di run diversi**. Se porti il retry senza portare il
`scoped_invalidate` mirato del blocco 7, **ricrei quell'anello**.

## VINCOLI

- `ds4_gpu_tensor` resta `{ptr, bytes, owner, device_id}`. **Niente campi aggiunti.**
- **Nessuna seconda API pubblica.** Dietro `ds4_gpu_stream_expert_cache_*`.
- **Solo single-GPU**: guard esistente su `g_n_gpus != 1`.
- **Additivo**: upstream resta compilabile su Linux.
- *I meccanismi di promozione e pruning del modello standard restano INVARIATI.*

## VERIFICA — quattro cose

```
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" ^
  -S . -B build-blk8 -G Ninja -DCMAKE_MAKE_PROGRAM="C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe" ^
  -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CUDA_COMPILER="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" ^
  -DCMAKE_CUDA_ARCHITECTURES=86 && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build build-blk8 --parallel 6
```

1. build **exit 0**;
2. le tre fixture esistenti restano **PASS** (`ds4_dynamic_arena_fixture`,
   `ds4_prefill_observer_fixture`, `ds4_vram_expert_cache_fixture`);
3. **con i flag spenti** il decode resta identico a upstream — e' il criterio di sempre;
4. una fixture nuova per il **rendezvous**: request pubblicata, worker che la reclama,
   publish dopo drain, e **almeno un percorso di fallimento che finisce in `refund()`**.

**Se dopo il tuo lavoro l'accensione non e' sicura, NON accendere.** Lascia il gate a `false`,
scrivi cosa manca, e sara' un blocco 8b. **Un nucleo che si accende e corrompe uno slot e'
molto peggio di un nucleo che non si accende ancora.**

**Rapporto** in `PORT_BLOCK8_ROUTEWORKER.md` **nella radice**: le sette condizioni una per una
con dove le soddisfi, la forma del rendezvous, e **se hai acceso il gate, perche' te la sei
sentita**.

Rispondi in italiano, con righe esatte.
