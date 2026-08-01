# PORTO SU UPSTREAM — piano operativo

**Stato al 2026-08-01 12:57.** Aggiornare questo file a ogni blocco chiuso.

## Obiettivo e ritorno

Portare le nostre estensioni su `upstream/main`, che ha **DSpark** e la **route Q4_K**
(`upstream:ds4_cuda.cu:20838`, kernel `moe_gate_up_mid_decode_q4K_qwarp32` e
`moe_down_q4K_sum6_qwarp32`). Da noi `Q4_K` in `ds4_cuda.cu` compare **zero** volte: e' la
ragione per cui la testa MTP fallisce in silenzio e il drafter scivola sulla CPU fuori dal grafo.

**Il ritorno, in due pezzi che NON arrivano insieme** (verificato l'1/8, correzione a una mia
affermazione precedente):

```
route Q4_K       la da' il PORTO     la testa MTP smette di fallire in silenzio,
                                      il drafter rientra nel grafo (48% del tempo)
DSpark, 5 bozze  la danno i PESI     accettazione 0,82 alla quinta posizione su codice,
                                      sopra la soglia 0,72 dell'issue #636, sotto il tetto 1,83x
```

**DSpark non ha un interruttore: ha dei tensori.** In `ds4.c` le env `DS4_DSPARK_*` sono quasi
tutte di *spegnimento* (`NO_MARKOV`, `NO_GPU_MARKOV`, `DISABLE_*`) e non esiste nessun
`use_dspark`. Il cancello e' il file dei pesi: `ds4.c:2700` cerca
`main_proj / main_norm / markov / confidence / final_head`, e
`dspark_weights_validate_metadata` (`ds4.c:5247`) rifiuta senza block size, rango di Markov,
token di rumore e lista dei layer bersaglio.

**Nessuno dei nostri tre GGUF li ha** (`ds4-2bit` 1328 tensori, `IQ2XXS-imatrix` 1328,
`IQ1_S-XL` 1066): l'unico nome speculativo e' la chiave `deepseek4.nextn_predict_layers`, cioe'
la testa NextN che abbiamo gia'. **A pesi invariati il porto non accende DSpark.**

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

**E upstream ha lasciato la sede.** `cuda_stream_selected_cache_begin_load` gia' deduplica gli
ID, alloca buffer compatti, fa le copie selettive e costruisce la remap degli slot. **Ma
budget, hotness e seed sono stub e no-op** (`UCU:28684-28690`, `:28804-28834`, `:28849-28855`;
superficie pubblica `UH:166-229`). Loro il trasporto, noi le decisioni.

> **Righe corrette l'1/8**: avevo scritto `UCU:27260-27431` e `UH:146-205`. Erano giuste prima
> che la telemetria (blocco 2) aggiungesse 1419 righe a `ds4_cuda.cu` e 20 a `ds4_gpu.h`.
> **Ogni riferimento di riga in questo documento invecchia a ogni blocco che atterra.**

### E la politica vuota NON basta riempirla

Dal piano del nucleo: il substrato ha il trasporto ma **non ha l'autorita' persistente**.
Manca, con la riga:

```
mappa persistente (layer,expert) -> slot   upstream ha solo i metadati dell'ultimo batch  UCU:1377-1401
stato slot EMPTY / LOADING / VALID         l'invalidate upstream abbassa solo `valid`     UCU:1403-1406
scelta della vittima + reservation         gli stub non contengono nessuna decisione      UCU:28684-28690
publish atomico di mappa e route pointer   il consumer ricava gli indirizzi da 3 buffer   UCU:22287-22301
refund di una vittima sovrascritta a meta  nessuno stato corrispondente                   UCU:1377-1401
route worker e mailbox di ownership        l'assenza e' DICHIARATA da upstream            UCU:619-625
```

**Conseguenza vincolante**: i blocchi 6, 7 e 8 devono atterrare come **sottosistema interno
disattivato** e diventare raggiungibili **in un solo passo finale**. Non e' sicuro accendere
prima la cache e aggiungere dopo politica o worker: `reservation`, `victim`, `publish` e
`refund` o ci sono tutti e quattro, o non si attiva niente.

**Stima del nucleo**: 10-12 giornate dopo l'atterraggio di 3 e 4. Le decorazioni del fork
(DOV, rotatore G73, corsia G132) valgono altre 4-7 giornate e **non devono stare sul percorso
critico**.

**Granularita'**: si trapiantano blocchi che possiedono uno stato, non funzioni. Primo porto
limitato a `g_n_gpus == 1` e al ramo DSV4 non-TP/non-EP.

## Ordine dei blocchi

| # | Blocco | Isolabile | Stato |
|---|---|---|---|
| 0 | Contratto upstream + POSIX + guard `g_n_gpus==1` | si | **FATTO** — build exit 0, `ds4.exe` 6,9 MB gira |
| 1 | `os_file`, pread cancellabile, mmap, thread | **si** | **FATTO** f878e71, 11 file, compila |
| 1b | CMake MSVC/nvcc esteso alle unita' nuove upstream | si | **FATTO** configura e genera, 10/36 unita' compilano |
| 2 | Telemetria passiva: alloc, hostpin, worker-prof, transport ledger | si | **FATTO** 2952760, 1419 righe, compila |
| 2b | **`ds4-server` su Windows** — e' il binario di OGNI misura, oggi e' uno stub | si | **FATTO** b46b391, thread scheduler su os_thread |
| 3 | Adattatore dietro `ds4_gpu_stream_expert_cache_*` upstream | si | **FATTO** eab720a, 190 righe, build OK |
| 4 | Arena core: slot, transaction, wrap, checksum, snapshot | **si** | **FATTO** 2b4c934, 1255 righe, fixture PASS verificata a mano |
| 5 | Async readback/SPEX, observer prefill/REAP | parziale | da fare |
| 6 | Cache VRAM esperti: capacity, eviction, publish | parziale | **in corso** worktree `ds4-port-blk6` (sopra l'adattatore) |
| 7 | Tiering/promozione/G133, admission, knocks, mass-LFRU | no | **piano in corso** (nucleo 6-7-8) |
| 8 | Route worker, mailbox, selected-load, seam routed-MoE | no | **piano in corso** — poi primo end-to-end |
| 9 | Guardiani G73: deadline, cancel, retry, respawn | no | da fare |
| 10 | IQ1/Q1/nested residual/SSD rotator | no | **in corso** worktree `ds4-port-blk10` |
| 11 | KV staged e G132 CPU lane | no | fuori dal primo traguardo |

## I fronti, aggiornati (1/8, 13:20)

Un **worktree git per agente**: la regola "un agente per file disgiunti" era prudenza, non una
legge, e i blocchi 4-9 stanno quasi tutti nello stesso `ds4_cuda.cu`.

```
FATTI     ds4-port-blk3    port/blk3-cache-api   adattatore      eab720a
          ds4-port-blk4    port/blk4-arena       arena core      2b4c934

APERTI    ds4-port-blk6    port/blk6-vramcache   cache VRAM      parte DALL'adattatore
          ds4-port-obs     port/blk5-observer    observer        parte DALL'arena
          ds4-port-blk10   port/blk10-iq1        IQ1_S / Q1_0
          ds4-port-merge   port/merge-1          MERGE dei tre rami sul tronco
```

### E i blocchi 7 e 8 NON avranno un ramo proprio

Il vincolo tutto-o-niente ha una conseguenza sulla regia che vale la pena scrivere prima di
sbagliarla: **7 e 8 devono continuare sullo STESSO ramo del 6**, non su worktree paralleli.

```
6 cache VRAM  ->  7 tiering  ->  8 route worker      tutti su port/blk6-vramcache
                                                      poi UN passo che accende
```

Il parallelismo per worktree funziona quando i blocchi possiedono stati diversi. Qui i tre
condividono `reservation`, `victim`, `publish` e `refund`: tre agenti in parallelo
scriverebbero tre transazioni diverse, e il merge non sarebbe una riconciliazione ma una
riscrittura. **Questo e' il caso in cui la serializzazione e' una dipendenza vera, non
prudenza.**

**I rami nuovi partono dal ramo che gli serve, non dal substrato nudo.** La cache VRAM eredita
il contratto dell'adattatore; l'observer eredita l'arena che deve riempire. Costa un merge in
piu' e risparmia di far inventare a un agente un contratto che esiste gia'.

Il quarto non scrive sorgenti: prepara il trapianto del nucleo accoppiato, che non puo'
partire finche' 3 e 4 non atterrano. Quando atterrano, il piano c'e' gia'.

**Poi serve un agente di MERGE** che riconcilia i tre rami di codice su
`port/upstream-substrate`. Vede tutti i diff insieme, quindi trova le incoerenze fra blocchi
meglio di chi legge tre rapporti in fila.

### Come si lanciano (il companion perde i job)

```powershell
Get-Content -Raw mandato.txt | & codex exec -C "<worktree>" -s workspace-write - *> "log.txt"
```

Il prompt **da stdin**: come argomento PowerShell lo spezza in un argomento per riga. Il
`NativeCommandError` nel log e' solo stderr avvolto, non un errore. **Si verifica coi file
(`git log`, `git status`), non col registro del companion**: c'e' una cartella di registro per
repo e prendere la prima e' come non guardare.

**Non separabili**: `route_worker + expert_cache + tiering_enforce_request`;
`deadline + I/O cancellabile + teardown`; `Q1 mixed + nested residual + SSD rotator`;
`G132 + reservation + dispatcher`; `observer + ranked prefill + REAP`.

## Avanzamento misurato

```
blocchi chiusi        7 / 14        0, 1, 1b, 2, 2b, 3, 4
giornate stimate    6-8 / 19-27      ->  ~30% del core single-GPU
                    6-8 / 26-36      ->  ~23% della parita' piena
righe di politica  1445 / ~27700     ->  ~5%   (adattatore 190 + arena 1255)
```

**Le tre scale non concordano, e la ragione e' il punto.** Per blocchi siamo a meta'; per
giornate a un terzo; per righe di politica al 5%. Non e' una contraddizione: **i blocchi
chiusi sono quelli che avevano la risposta gia' scritta nel fork**, e i blocchi 6-7-8-9
contengono quasi tutte le 27.700 righe. La scala per righe e' quella onesta sul lavoro che
resta; quella per giornate tiene conto che le righe rimaste sono anche piu' difficili.

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
