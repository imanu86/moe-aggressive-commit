# Pacchetto PR upstream — sblocco MTP + SSD-streaming su CUDA (patch 0009/0010/0011)

> Destinazione: antirez/ds4 (issue #495, PR #497, thread #468). Preparato dal track
> DSpark per l'outreach coordinato da SPEX-main (task #17). Stato: [DA FINALIZZARE:
> verdetto appaiato + M8-TRIS].

## Cosa proponiamo (3 patch, tutte env-gated default OFF, base 80ebbc3)

| patch | cosa fa | env |
|---|---|---|
| `0009-dspark-mtp-streaming-unlock` | rilascia la guardia `--mtp`+`--ssd-streaming` e incorpora il fix della **PR #497** (accreditata: selected-load anche per encode single-position, senza cui il verifier va in OOM residency) | `DS4_MTP_STREAMING=1` |
| `0010-dspark-cuda-support-model-map-registration` | **bugfix**: lo slot di registrazione mappa è singolo; ogni remap streaming de-registra la mappa del support model MTP → drafter morto (silente su WSL2, mascherato dai fallback per-range su Linux nativo). Slot secondario durevole + handoff di proprietà | sempre attivo (è un fix), nessun cambio senza `--mtp` |
| `0011-dspark-mtp-host-statics` | su schede piccole il device-cache delle statics del support model (~3.5GB) compete con l'expert cache; con lo slot 0010 il drafter legge zero-copy → cache device ridondante sotto streaming | `DS4_MTP_HOST_STATICS=1` |

## Perché (la motivazione di #495, con numeri)
Regime disk-bound (issue #495: 4060Ti, gen 2.2 t/s vs prefill 28.7): il blocco di verifica
ammortizza le load expert. Misurato da noi su RTX 3060/WSL2, DeepSeek-V4-Flash 2-bit:
- union-load nel verify: blocchi da 12 slot → ~10 expert unici per layer (log
  `compact=` committati); su prefill 670 tok: 4020 slot → ~163 unici (−95.9%).
- primo spec-dec MTP in streaming funzionante: 33-34 cicli verify/100 tok, acceptance
  pos2 0.82-0.85 (code), draft ~25ms/ciclo.
- wall-clock same-state (cache off su entrambi): spec2 **+9/10%** vs baseline.

## Correttezza (validazione appaiata, no token-diff: nondeterminismo batch noto, ds4.c:27342)
**VERDETTO: EQUIVALENZA NON RIFIUTATA su DUE piattaforme** (ds4-eval, 20 domande
identiche GPQA Diamond / SuperGPQA / AIME2025, greedy, streaming, appaiamento per nome
test, McNemar esatto — `paired_verdict.py`):
- **WSL2/3060**: OFF 12/20 vs ON 13/20 — 19/20 concordanti, 1 discordante (pro-ON),
  p=1.0 (`a8ae88b`).
- **Linux nativo/3090**: OFF 12/20 vs ON 11/20 — 19/20 concordanti, 1 discordante
  (pro-OFF), p=1.0 (`b67bbc6`).
- Combinato: 40 coppie, 38 concordanti, 1 discordante per direzione = rumore near-tie.
- Contesto rumore: due repliche OFF identiche (stessa macchina/config) differiscono di
  2/20 — la differenza ON/OFF (1/20) è SOTTO il pavimento di replicazione.
  (Prima replica: sommario 10/20 da transcript, file persi per collisione path — citato
  solo come osservazione.)
- ~10h cumulative di run con lo stack attivo: zero crash, zero fallback sequenziali.
- Bolletta baseline quantificata (DS4_SPEX_STATS): 1.447M expert-load direct, 9.6 TiB
  copiati in 4h28m (~620 MiB/s sostenuti) = il bersaglio dell'ammortamento a blocchi.

## La matrice dei regimi (M8 completo — il quadro onesto per la PR)

| regime | expert cache | spec2 vs base | fonte |
|---|---|---|---|
| WSL2 12GB, disk-bound, cache-off pari | negata a entrambi | **+9/10%** | fase C smoke |
| WSL2 12GB, base cache-on | negata SOLO allo spec | −30% (0.65-0.70 vs 0.90-1.06) | M8/M8-BIS/M8-TRIS |
| Linux nativo 24GB, RAM-backed, cache-on pari | attiva a entrambi | **−50%** (2.11 vs 4.27) | M8-NATIVO |
| Linux nativo, disk-bound su NVMe datacenter (cgroup 46G e 16G di finestra cache) | attiva | **−50%** (base ~2.3 vs spec2 ~1.1; finestra irrilevante) | CELLA (`runs/dspark/20260706_lowram_cell_pod/`) |
| **3060 + storage consumer (= target DwarfStar)** | negata (WSL2) | **+9/10%** a parità | fase C smoke |

**Lettura definitiva della matrice (con la cella misurata)**: la variabile che decide non
è "disco vs RAM" ma il **costo IO per token relativo all'overhead di verifica**. Prova:
banda di copia expert misurata (DS4_SPEX_STATS) — pod NVMe **1.92 GB/s** sostenuti vs
3060 **~620 MiB/s**: a 3× di banda il per-token IO si sgonfia e lo spec paga solo il suo
overhead (stesso −50% del RAM-backed, e la finestra cache 16G vs 46G non sposta nulla).
La speculazione a blocchi in ds4 conviene **dove lo storage è lento rispetto all'appetito
del modello** — il caso consumer di #495 (4060Ti, 2.2 t/s) e del nostro 3060
(0.65-1.06 t/s), dove il +9/10% a parità di condizioni è misurato. Emulare storage
consumer sui pod richiederebbe `io.max` (cgroup non scrivibile nei container RunPod):
il regime consumer resta misurato dove vive, sul 3060.

## Limiti dichiarati (onestà da PR)
1. **WSL2**: `cudaHostRegisterMapped` della mappa support (3.55GB) viene addebitata da
   `cudaMemGetInfo` → anche con 0011 l'expert cache resta negata su 12GB (M8-BIS), e il
   cap alla q8→f16 NON basta (M8-TRIS: spec2 0.65/0.65, cache ancora negata). Su Linux
   nativo il problema non esiste (verificato). Fix strutturale progettato (0012:
   drafter via fd/staging senza registrazione) — necessario SOLO su WSL2.
2. Spec-dec solo greedy (limite upstream preesistente, `ds4_cli.c:483`).
3. `--mtp-draft` fisso: la lunghezza adattiva è ortogonale (PR #482 Metal;
   la nostra estensione confidence/STS/IO-aware è materiale per una PR successiva).

## Materiale collegato
- Dati drafter DSpark ufficiale su V4-Flash (per il thread #468): τ blocco-5 =
  5.18/5.00/2.70 (code/math/chat), curve per-posizione + confidence head ECE,
  585 cicli teacher-forcing su 2×H200 (`runs/dspark/20260705_dspark_b_v4flash_2xh200/`).
- Trace routing: blocco-8 → 24.3 expert unici/layer vs 48 (−49%), la base della tesi.

## Checklist di consegna
- [x] patch 0009/0010/0011 esportate (format-patch, worktree `dspark/unlock-streaming`)
- [x] serie 0001-0005+0009-0011 verificata: applica PULITA su stock 80ebbc3 (pod nativo)
- [x] evidenze committate (fase C smoke, M8, M8-BIS, M8-TRIS, M8-NATIVO, 2 coppie eval)
- [x] verdetto appaiato: EQUIVALENZA su 2 piattaforme (p=1.0 entrambe)
- [x] M8-TRIS: negativo (cap q8f16 insufficiente su WSL2 → 0012 per quella piattaforma)
- [x] **CONSEGNATO a SPEX-main** per l'aggancio al task #17 (outreach antirez)

## Coordinamento upstream (ricognizione 2026-07-06)
- **Finestra favorevole**: #495 resta senza risposta del maintainer — questo pacchetto
  può essere la risposta canonica. Attenzione upstream alta sul CUDA streaming
  (#503/#504).
- **#497 (giannisanni)**: volutamente parziale (il guard engine resta) — il nostro è un
  SUPERSET che la accredita; coordinarsi con l'autore prima dell'invio, non competere.
- **Rischio rebase con #504** (per-size-class expert caches, stesso `ds4_cuda.cu`):
  benchmark upstream fortissimi (0.9→25 t/s, 97% hit su Blackwell 96GB) → probabile
  merge; verificare l'ordine e ribasare le nostre 0010/0011 se atterra prima.
- **Framing**: #493 "supportereste DSpark?" chiusa *not planned* (attore non confermato)
  → pitch corretto = "sbloccare l'MTP nativo esistente nel regime streaming" (codice del
  maintainer), NON "aggiungere DSpark". Il pacchetto è già impostato così.
- **#508** (SSD streaming expert su backend CPU, pread+LRU): sinergica con l'eventuale
  drafter-CPU (design 0013, bench 43.5ms/GEMV committato in
  `runs/dspark/20260706_cpu_drafter_bench/`).
