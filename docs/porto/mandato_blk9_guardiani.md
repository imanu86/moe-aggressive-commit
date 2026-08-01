# MANDATO — blocco 9, guardiani: deadline, cancel, retry, respawn

LAVORO DI IMPLEMENTAZIONE. Scrivi codice, nel worktree indicato e SOLO li'.

  IL TUO WORKTREE:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-port-guard
                    branch port/blk9-guardiani, partito dal TRONCO che contiene ormai tutto:
                    adattatore, arena, observer, cache VRAM, tiering, route worker, IQ1, KV.
                    **Leggi `PORT_BLOCK8_ROUTEWORKER.md` e `PORT_BLOCK7_TIERING.md` PRIMA di
                    scrivere una riga.**
  RIFERIMENTO:      C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a
                    il nostro fork, HEAD af84c42. **SOLO LETTURA.**

**TUTTO CIO' CHE SCRIVI DEVE STARE DENTRO LA TUA RADICE.** **Non usare git per scrivere**: il
`.git` del worktree sta fuori dalla radice e `git add`/`git commit` falliranno. Leggere con git
va bene. Al commit ci pensa chi ti ha lanciato.

OBIETTIVO: i **guardiani G73** — deadline, cancellazione, retry, respawn del worker. E' l'ultimo
blocco del piano.

## IL FATTO MISURATO, ed e' il motivo per cui questo blocco esiste

Il guardiano della deadline, quando scade, fa:

```
CUDA transient route read reached absolute deadline seq=... bytes=14155776
  -> abort
  -> cache-invalidate scope=FULL
  -> altre miss
  -> altri abort
```

**Un anello che si autoalimenta.** Il conteggio `bytes=14155776` compare in **26 log di run
diversi**. La politica e' `0,050 s/MiB` con cap a `5,0 s`.

**E abbiamo gia' la cura, misurata**: `DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE=1` porta le
esaurimenti da **12 a 0** (n=2), **a costo zero** sul tempo. E' promossa nell'atlante delle
leve. **Portala, ed e' la ragione principale di questo blocco.**

## LA REGOLA CHE NON DEVI VIOLARE

Il blocco 7 ha portato **`scoped_invalidate`**, un rollback **mirato** che agisce solo dopo
prova di quiescenza. Esiste apposta per non rifare l'invalidazione totale.

> **Se porti il retry usando `cache-invalidate scope=FULL`, ricrei l'anello.** Il retry deve
> passare dallo `scoped_invalidate` del blocco 7, non da una invalidazione globale.

## L'INVENTARIO, in `ds4-p4a/ds4_cuda.cu`

```
31935-31956   g133_rotator_io_timeout_seconds / transient_io_timeout_seconds
31988-32051   transient_deadline_env_seconds, budget_seconds
32051-32079   transient_deadline_from_now, backoff
32080-32134   deadline_worker_request_begin, note
32135-32231   transient_deadline_replace_io_and_staging
32232-32269   transient_deadline_terminal_drain
32405-32570   transient_pread_chunked                    <- QUI vive l'adattivo
32571-32592   transient_timeout_cancel_for_fallback
32593-32654   transient_prepare_retry_slot
32655-32757   transient_timeout_fallback_serve
32933-33008   route_worker_cancel_and_join               (gia' portato dal blocco 8: VERIFICA)
40491         route_worker_respawn
42617-42641   g73_classify_request
42642-42658   g73_publish_pending_outcomes
```

**Attenzione**: il blocco 8 potrebbe aver gia' portato `cancel_and_join` e parte del drain.
**Verifica cosa c'e' gia' nel tronco prima di riportarlo**: duplicare un teardown e' peggio
che non averlo.

## COSA NON PORTARE

G132/corsia CPU (falsificata: +47 ms/token), DOV, nested residual, demand pipeline, rotatore
SSD. Restano fuori dal percorso critico.

## VINCOLI

- **Spento di default** come tutto il resto, e con i flag spenti il decode identico a upstream.
  Gli opt-in gia' nel tronco sono `DS4_CUDA_DYNAMIC_ARENA_GB`,
  `DS4_CUDA_PREFILL_MASS_OBSERVE`, `DS4_CUDA_VRAM_EXPERT_CACHE`, `DS4_CUDA_KV_STAGED_RING`.
- `ds4_gpu_tensor` resta `{ptr, bytes, owner, device_id}`.
- **Nessuna seconda API pubblica.** Solo single-GPU. Additivo.
- *Promozione e pruning del modello standard restano INVARIATI.*

## VERIFICA

```
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" ^
  -S . -B build-guard -G Ninja -DCMAKE_MAKE_PROGRAM="C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe" ^
  -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CUDA_COMPILER="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" ^
  -DCMAKE_CUDA_ARCHITECTURES=86 && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build build-guard --parallel 6
```

1. build **exit 0**;
2. **le cinque fixture gia' presenti restano PASS**, con i flag spenti e accesi:
   `ds4_dynamic_arena_fixture`, `ds4_prefill_observer_fixture`,
   `ds4_vram_expert_cache_fixture`, `ds4_route_worker_fixture`, `ds4_kv_staged_fixture`;
3. una fixture nuova per il guardiano: **fai scadere una deadline** e verifica che il recupero
   **non** invalidi tutto — che passi dallo `scoped_invalidate`, e che il retry riparta senza
   buttare via la cache. **E' esattamente l'anello che vogliamo evitare, quindi il test deve
   saperlo riconoscere.** Registrala anche in `add_test`, come le altre cinque.

**Rapporto** in `PORT_BLOCK9_GUARDIANI.md` **nella radice**: cosa hai portato con le righe,
**cosa hai trovato gia' presente dal blocco 8 e quindi non hai riportato**, come il retry evita
l'invalidazione totale, e la forma esatta della deadline adattiva.

Rispondi in italiano, con righe esatte.
