# Elastico M3 — banda morta sui ridimensionamenti della cache esperti (21 settembre 2026)

> **Aggiornamento della sera: la leva vera non era questa.** Il 13-16% del decode a 100k lo mangia il deposito RAM
> degli 8 strati; con `LLAMA_MOE_RAM_LAYERS=0` l'adattivo (M2 o M3) fa 22,4-22,9 t/s. Vedi `SCOMPOSIZIONE_DECODE.md`.

**Conclusione.** M3 fa quello che deve (zero ridimensionamenti a metà decode, un solo ridimensionamento dopo ogni
prefill, prova del canary ancora SUPERATA), ma al punto operativo **guadagna il 3,0% su M2 (18,93 contro 18,38 t/s a
~100k): sotto la soglia del 5%, quindi NON si promuove.** A contesto corto vale +10,7%; a 50k pareggia. Resta il 4%
sotto i 40 slot fissi di x4 a 100k. `D:\ds4_work\bin_elastico_m2` e il bat sul Desktop non sono stati toccati.

| contesto | M3 | M2 | x4 (40 slot fissi) | M3 su M2 | M3 su x4 |
|---|---|---|---|---|---|
| ~1k (a freddo) | 16,33 t/s | 14,75 | 15,03 | **+10,7%** | +8,6% |
| ~50k | 18,23 | 18,23 | 19,38 | 0,0% | −5,9% |
| ~100k (punto operativo) | 18,93 | 18,38 | 19,75 | **+3,0%** | −4,2% |
| prefill 1k / 50k / 100k | 189 / 392 / 276 | 202 / 378 / 278 | 219 / 388 / 291 | | |

`banco_decode.py --run --braccio m3|m2|x4`, server isolato su 127.0.0.1:8113, 512 token generati, greedy, senza MTP,
una corsa per braccio una dopo l'altra (M3 per primo), produzione spenta:
`D:\ds4_work\qwen_gateway_run\20260921_154645_decode_m3`, `…_155500_decode_m2`, `…_160327_decode_x4`.

## Cosa si è trovato in M2 (codice + log)

**Un ridimensionamento non ritocca la cache: la butta via.** `llama_moe_cache_resize` (`src/llama-moecache.cpp:770-849`
nel sorgente di Codex) fa `release_elastic_buffers` (unbind + free di tutti i buffer) → alloc alla nuova taglia →
`ggml_backend_buffer_clear` → `bind`, e `qwen_moe_demand::bind` (`ggml-cuda/moe-demand.cuh:310-401`) crea un
`bound_group` nuovo con le tabelle slot↔esperto a −1 e i contatori a zero. Un 67→66 perde ~5,3 GB di esperti
residenti, come un prefill. Si vede nei rapporti «moe cache: richiesti…», che ripartono a ogni bind: 10 token dopo un
65→63 i colpi sono al 46% con 453 MB/token, contro 67% e 276 MB/token a regime (~1k di contesto).

Misure sul log di produzione del pomeriggio (`gsq_rco_ELASTICO_M2_NO_MTP_20260921_1425.log`, generazioni da 512 token):

| contesto | resize nel decode | di cui ±1-2 slot a metà decode | pause `before_resize→workspace_ready` |
|---|---|---|---|
| ~1k | 8 | 6 | 1,89 s = 5,0% dell'eval time |
| ~50k | 5 | 3 | 1,28 s = 4,3% |
| ~100k | 5 | 3 | 1,18 s = 4,2% |

- **Perché oscilla.** La crescita riempie fino all'orlo (restano 64 MiB di transiente; i 200 MB di riserva fisica
  stanno dentro `policy_headroom`); a taglia fissa `cuda_free` balla di ±150 MiB con punte a 0-85 MiB; ogni punta
  sotto i 64 MiB fa scendere di 1-2 slot, e dieci secondi dopo la politica ricresce di +1/+2. Il polling del budget
  non c'entra (~100 µs a lettura).
- **Dopo ogni prefill** la sequenza è `workspace_change` 0→30 e poi la crescita forzata 30→66
  (`llama-context.cpp`, fondo di `sched_reserve_impl`): ~0,3 s più il riempimento dei 30 slot buttato subito. Anche
  il passaggio di secchio del KV durante il decode (ogni 16384 celle) passava da 30.
- **L'area di lavoro del prefill non entra mai nella VRAM libera a regime**: 462-484 MiB già a 42 token, 1188 MiB a
  1k token, 2,4-6,5 GB con ubatch da 4096; sopra i 512 token serve anche l'anello di `qwen_prefetch` (2 × ~283 MiB +
  512 MiB di riserva sua), altrimenti lo staging si spegne in silenzio e il prefill rallenta.
- **Uso reale** (`…_1444.log`, generazioni di DSH fino a 4280 token, 10,5-11 t/s a 50-80k): un resize ogni ~16 s,
  pause misurate 1,4-3,4% dell'eval time. **Gli 11 t/s dell'uso reale non si spiegano coi ridimensionamenti.**
- **M2 muove circa la metà dei byte di x4** (a 100k 168-181 MB/token con colpi al 78-80%; x4 sta a ~310-320
  MB/token con colpi al 61-63% a ogni profondità) eppure è più lento:
  il resto del divario non sta né nei byte né nei ridimensionamenti. Candidati non verificati: il deposito RAM degli 8
  strati (sorgente paginabile → staging), il piano a 60-70 slot, la ricattura dei grafi CUDA dopo ogni reset.

## Cosa cambia in M3

Patch: `m3-banda-morta.patch` (3 file). Logica pura in `src/llama-moecache-policy-m3.h`, con test autonomo
`policy_m3_test.cpp` (nessuna GPU; lo script di build lo esegue prima di collegare: se non passa non si collega).

- **A — banda morta** (`llama_moe_choose_capacity_banded`). La riduzione scatta *esattamente* dove scattava in M2
  (margine sotto i 64 MiB: la regola di sicurezza non è indebolita) ma scende fino a lasciare anche un cuscino di
  256 MiB: un solo svuotamento invece della scaletta 67→66→65→64→62. La crescita parte solo se guadagna ≥ 4 slot
  col cuscino intatto, sul margine stabile a 10 s; dopo una riduzione per budget niente crescita per 30 s (M2: solo
  per +1). Nessun ridimensionamento finché il margine sta fra 64 e ~640 MiB; regime 61-64 slot invece di 66-67.
- **B — ripartenza** (`llama_moe_restart_capacity`, `llama_moe_cache_m3_restart`). Allo svuotamento si salva
  l'ultima taglia buona; al ritorno in decode un solo ridimensionamento alla capacità fresca (cache vuota, area del
  prefill già liberata, cuscino e ≥128 MiB di area del decode tolti), o esattamente all'ultima taglia buona se dista
  meno di 4 slot e lascia almeno metà cuscino. Se la cache è già allocata (cambio di secchio del KV) non si tocca.
- **C — prefill senza svuotamento** (`llama_moe_cache_m3_keep_for_prefill`). La taglia dell'area si impara a ogni
  riserva (differenza di VRAM libera prima/dopo, il massimo fra CUDA e fisica); per un prefill nuovo vale la più
  piccola area già misurata con token e kv non inferiori. La cache resta solo se area + 64 MiB + 256 MiB di margine
  (+ 1200 MiB di anello di prefetch da 512 token in su) stanno nel margine corrente. Se poi la riserva viene violata
  durante il prefill, `llama_moe_cache_elastic_plan` svuota come prima (evento `m3_prefill_pressure`).
- Env: `LLAMA_MOE_ELASTIC_M3=0` = politica di M2 bit per bit (stesso binario); `LLAMA_MOE_ELASTIC_KEEP=0` spegne C;
  `LLAMA_MOE_ELASTIC_CUSHION_MB` (256), `LLAMA_MOE_ELASTIC_MIN_GROW` (4), `LLAMA_MOE_ELASTIC_PREFETCH_MB` (1200).
- Eventi nuovi nel log: `m3_restart`, `m3_prefill` (con `keep`, `workspace_bound`, `policy_headroom`), `m3_prefill_pressure`.
- Nessun membro nuovo in `llama_context` (si ricompilano due oggetti: il layout della classe è condiviso con gli altri
  .obj di O2): lo stato sta in `moe_cache`, locale a `llama-moecache.cpp`; le quattro funzioni nuove sono dichiarate
  in `llama-context.cpp`, non in `llama-moecache.h`.

## Build

`build_m3_overlay.py` (schema di `elastico_m1_canary/m2/build_m2_overlay.py`): laboratorio `D:\ds4_work\elastico_m3`
fuori da git, overlay di `src/llama-moecache.cpp` (base: sorgente O2 di Codex), `src/llama-context.cpp` (base: overlay
M2) e del nuovo header; ricompila i due oggetti coi flag di `compile_commands.json`, ricollega la sola `llama.dll` da
186 oggetti/librerie O2 letti in sola lettura (SHA verificato prima e dopo); tutto il resto di `runtime-m3` è copia
byte per byte di `runtime-m2`, `ggml-cuda.dll` compresa (`a8e6d2a9…`). Rifiuta di partire con un `llama-server` vivo.

| binario | M2 | M3 |
|---|---|---|
| `llama.dll` | `5b219d2127faf219…` | `2d8f2d57be8db7afea4f62c70ab1f251db8c812504adb517eb09249e047d5484` |

## Collaudo

1. `policy_m3_test`: **PASS** (banda, punto di scatto identico a M2, crescita minima, minimo preservato, 100 000
   letture con jitter ±150 MiB = zero ridimensionamenti, equivalenza con M2 a cuscino 0, ripartenza, prefill).
2. Prova del canary, `prova_canary_prefill.py --run --runtime D:\ds4_work\elastico_m3\runtime-m3\llama-server.exe`
   (`D:\ds4_work\elastico_m1_canary_run\20260921_154235_m3_banda`): **SUPERATA**, impronte identiche al controllo e a
   M2 (`25bcfc3488db`, `1235d4b1aad7`), 4108 sfratti e 4108 ripristini, zero righe di canary. Nei 53 s di decode sotto
   pressione **zero ridimensionamenti**; dopo ogni prefill un solo `resize` 0→61/62.
3. Banco decode (tabella in cima). Nei log: M3 zero resize a metà decode e pause 0,0%; M2 nella stessa sessione 1-2
   resize a metà decode per generazione e pause 2,1/2,7/3,4% (`analizza_resize.py <server.log>`). Il guadagno a 100k
   (+3,0%) coincide con le pause tolte; a 50k i 5-6 slot in meno del cuscino (colpi 72,8% contro 73,9%) lo annullano.
4. Punto C: in tutte le corse `m3_prefill keep=0` (area appresa 484 MiB a 42 token contro 370-560 MiB di margine):
   **il ramo «la cache resta» non è mai stato esercitato da una prova**.

## Cosa NON è provato, e cosa resta

- Una corsa per braccio: il rumore del banco è dell'ordine dell'1-2%. Con la scrivania più agitata (il log del
  pomeriggio: 3-6 resize per generazione, pause 4,2-5%) il guadagno di M3 sarebbe più alto, ma non è stato misurato
  a pari condizioni; generazioni lunghe (2-4k token) non misurate; MTP acceso non provato.
- Il ramo C con `keep=1`, e il suo paracadute `m3_prefill_pressure`, non sono mai scattati.
- Strada strutturale (M4, non fatta): ridimensionamento che conserva il contenuto con la memoria virtuale CUDA
  (`cuMemMap`/unmap della coda dei tensori della cache). Renderebbe quasi gratuiti sia i ritocchi sia lo svuotamento
  parziale per i prefill piccoli; tocca l'allocazione in ggml-cuda e `moe-demand`, non è da overlay.
- Il divario da x4 a 50-100k (4-6%) e gli 11 t/s dell'uso reale vanno cercati altrove (vedi sopra).
- `docs/porto/qwen_gateway/spegni_server.py` lanciato staccato con l'uscita su file manda il CTRL_C (il server esce
  pulito) ma poi cade in `processi()` con `WinError 6` (dopo `FreeConsole` lo stdin ereditato non è valido: manca
  `stdin=subprocess.DEVNULL`), quindi non chiude il `cmd.exe` del lanciatore. Non corretto qui.
