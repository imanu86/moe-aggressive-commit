# PORTO SU UPSTREAM — piano operativo

**Stato al 2026-08-01 12:04.** Aggiornare questo file a ogni blocco chiuso.

## Obiettivo e ritorno

Portare le nostre estensioni su `upstream/main`, che ha **DSpark** e la **route Q4_K**
(`upstream:ds4_cuda.cu:20838`, kernel `moe_gate_up_mid_decode_q4K_qwarp32` e
`moe_down_q4K_sum6_qwarp32`). Da noi `Q4_K` in `ds4_cuda.cu` compare **zero** volte: e' la
ragione per cui la testa MTP fallisce in silenzio e il drafter scivola sulla CPU fuori dal grafo.

**Il ritorno**: drafter dentro il grafo, piu' DSpark con accettazione **0,82 alla quinta
posizione su codice** — sopra la soglia **0,72** oltre la quale l'issue upstream #636 misura
perdita netta, e sotto il tetto **1,83x** che la stessa issue calcola per la speculazione con
esperti in streaming.

**Cosa il porto NON risolve**: i 107,6 ms/token di letture fredde. Quello e' capienza (30 GiB di
arena contro un working set di 66-73 GB) e si compra con la RAM. Sono due conti separati.

## Coordinate

```
albero di lavoro   ds4-port        branch port/upstream-substrate -> upstream/main 54b36ed
sorgente           ds4-p4a         HEAD af84c42  (SOLO LETTURA)
base comune        8809b90         12 maggio
divergenza         344 nostri commit / 314 loro
ds4.c              loro 64.891 righe   noi 25.043
ds4_cuda.cu        loro 27.666         noi 56.765
```

## La strategia, decisa e non in discussione

**Upstream e' il substrato, incluso il suo `ds4_cuda.cu`.** Non si sostituisce il file: upstream
ha implementazioni per **147 su 147** delle funzioni GPU che ci mancherebbero, piu' `device_id` e
il plumbing multi-device.

**E upstream ha lasciato la sede.** `cuda_stream_selected_cache_begin_load`
(`UCU:22953-23087`) gia' deduplica gli ID, alloca buffer compatti, fa le copie selettive e
costruisce la remap degli slot. **Ma budget, hotness e seed sono stub e no-op a
`UCU:27260-27431`.** Loro il trasporto, noi le decisioni.

**Granularita'**: si trapiantano blocchi che possiedono uno stato, non funzioni. Primo porto
limitato a `g_n_gpus == 1` e al ramo DSV4 non-TP/non-EP.

## Ordine dei blocchi

| # | Blocco | Isolabile | Stato |
|---|---|---|---|
| 0 | Contratto upstream + POSIX + guard `g_n_gpus==1` | si | **FATTO** — build exit 0, `ds4.exe` 6,9 MB gira |
| 1 | `os_file`, pread cancellabile, mmap, thread | **si** | **FATTO** f878e71, 11 file, compila |
| 1b | CMake MSVC/nvcc esteso alle unita' nuove upstream | si | **FATTO** configura e genera, 10/36 unita' compilano |
| 2 | Telemetria passiva: alloc, hostpin, worker-prof, transport ledger | si | **in corso** (D1) |
| 2b | **`ds4-server` su Windows** — e' il binario di OGNI misura, oggi e' uno stub | si | **in corso** (E1) |
| 3 | Adattatore dietro `ds4_gpu_stream_expert_cache_*` upstream | si | da fare |
| 4 | Arena core: slot, transaction, wrap, checksum, snapshot | **si** | da fare |
| 5 | Async readback/SPEX, observer prefill/REAP | parziale | da fare |
| 6 | Cache VRAM esperti: capacity, eviction, publish | parziale | da fare |
| 7 | Tiering/promozione/G133, admission, knocks, mass-LFRU | no | da fare |
| 8 | Route worker, mailbox, selected-load, seam routed-MoE | no | **primo end-to-end** |
| 9 | Guardiani G73: deadline, cancel, retry, respawn | no | da fare |
| 10 | IQ1/Q1/nested residual/SSD rotator | no | da fare |
| 11 | KV staged e G132 CPU lane | no | fuori dal primo traguardo |

**Non separabili**: `route_worker + expert_cache + tiering_enforce_request`;
`deadline + I/O cancellabile + teardown`; `Q1 mixed + nested residual + SSD rotator`;
`G132 + reservation + dispatcher`; `observer + ranked prefill + REAP`.

## Avanzamento misurato

```
oggetti di build      25 / 36
blocchi del piano     1,5 / 12
giornate stimate     ~2,5 / 19-27      ->  ~10% del core single-GPU
```

Le prime due scale ingannano: un'unita' piccola conta quanto `ds4_cuda.cu`, e i blocchi 4-9
(arena, cache VRAM, tiering, route worker, guardiani) contengono **quasi tutte** le nostre
29.000 righe. Finora abbiamo fatto la parte meccanica, quella con la risposta gia' scritta nel
fork; **quello che resta e' il trapianto della politica, dove non c'e' niente da copiare.**

### Come riprendere il build

Directory gia' configurata: `ds4-port/build-verify` (MSVC 14.44, CUDA 12.6, sm_86, Ninja).
Da PowerShell, dentro `cmd /c`, con `vcvars64.bat` chiamato prima di cmake.

**Nota che costa tempo se dimenticata**: in fase di *configure* servono
`-DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl` espliciti. Anche sotto `vcvars64` CMake trova
il compilatore CUDA ma non quello C/C++, e fallisce con `No CMAKE_C_COMPILER could be found`.

## Decisioni gia' prese

**`ds4_gpu_tensor` resta INVARIATA** (`{ptr, bytes, owner, device_id}`). `host_ptr` serve al KV
staged, non all'arena esperti; l'arena si porta coi suoi record. Il KV staged usa una tabella
laterale **limitata al registry KV** — e non basta una mappa `tensore -> host_ptr`, perche' le
view ereditano `host_ptr + offset` e con `ptr == NULL` l'offset non e' ricavabile.

**Non creare una seconda API pubblica per la cache esperti.** Il nostro backend va dietro
`UH:146-205`, che `ds4.c` chiama gia' in decine di punti.

## Cosa NON portare

| Nostro | Perche' |
|---|---|
| "riempire il buco Q4_K" | upstream ha 7 occorrenze e kernel dedicati |
| alloc/view/free/read/write/copy generiche | upstream e' device-aware |
| resolver globale `cuda_model_range_ptr` | upstream ha `cuda_resolve_weight_ptr` per tier |
| allocator globale G6 + stream pool | non inizialmente |
| policy `graph_tensor_device_requested` | upstream sceglie managed/device per tier |
| stub Metal del fork | API upstream molto piu' ampia |
| trim globale WRAP working-set | gia' respinto nella nostra cronologia |
| secondo pass checksum globale | ridondante |
| prototipo mailbox precedente | gia' respinto |
| cache residente layer-local | gia' respinta |
| catena CPU Q4_K/MTP del fork | scarto probabile, ma serve un confronto numerico MTP prima |

## Stima

```
ABI/guard, Windows I/O, adapter        3-4 gg
arena core + fixture                   3-4
cache VRAM + tiering/promozione        5-7
route worker + dispatcher              4-6
guardiani + teardown                   2-3
controllo numerico single-GPU          2-3
                                     -------
core single-GPU                       19-27 gg
+ Q1/IQ1/nested residual               3-5
+ KV staged e G132                     4-7
parita' col working tree attuale      26-36 gg
```

## Cancelli

- **Neutralita'**: a flag spenti il testo deve restare intatto. Riferimento storico:
  sha `c7525d909341a57a` su 8145 caratteri (ma quello e' un frammento troncato a 2250 token —
  vedi il ledger sulle pagine complete).
- **Le leve misurate devono riprodursi**: `DS4_EXPERT_TIER_ADMIT_KNOCKS_SSD=3` +4,0%,
  `DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE=1` azzera gli sforamenti del guardiano.
- **Igiene dei run**: mai misurare con agenti Codex attivi; uptime sotto 180 min.

## Documenti

- `P1_inventario_trapianto.md` — 869 simboli, 63 confini, ordine, collisioni, cosa buttare
- `P2_strato_windows.md` — upstream POSIX-only, i nostri 10 file, le trappole
- `P3_layout_tensor.md` — `host_ptr` vs `device_id`, la conciliazione, le 12 firme
- `mandato_*.txt` — i mandati come sono stati dati, per riprodurli o correggerli

Il ledger completo e' in `reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md`, commit `38d6336`.
