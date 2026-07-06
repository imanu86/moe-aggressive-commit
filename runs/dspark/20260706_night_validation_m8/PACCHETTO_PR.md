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
- ds4-eval 20 domande identiche (GPQA Diamond / SuperGPQA / AIME2025), greedy, streaming:
  - **ON** (stack completo + drafter attivo a ogni token via probe): **13/20**, 4h10m,
    log+trace committati (`fef89d1`).
  - **OFF** (baseline): [TBD: rerun pulito in corso, appaiamento per nome test +
    McNemar esatto — `paired_verdict.py`]. Primo run (file persi per collisione di
    path, sommario 10/20 nel transcript): non citato come fonte.
- Nessun crash/fallback in ~9h cumulative di run con lo stack attivo.

## Limiti dichiarati (onestà da PR)
1. **WSL2**: `cudaHostRegisterMapped` della mappa support (3.55GB) viene addebitata da
   `cudaMemGetInfo` → anche con 0011 l'expert cache resta negata su 12GB
   (M8-BIS committato: base cache-on 0.90/0.79 vs spec2 0.58). Su Linux nativo il
   problema non esiste (verificato su pod 3090). Mitigazione in corso: cap alla
   q8→f16 cache ([TBD: M8-TRIS]); alternativa strutturale: fd-slot per la mappa support.
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
- [x] evidenze committate (fase C smoke, M8, M8-BIS, eval ON)
- [ ] verdetto appaiato OFF-rerun vs ON ([TBD ~14:30])
- [ ] M8-TRIS ([TBD ~15:00])
- [ ] testo PR finale (dopo i due TBD) → SPEX-main per invio
