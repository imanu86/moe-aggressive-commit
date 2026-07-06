# REAP K91 coding — "quanto posso strizzare un 158B finché non entra in un 3060"

> Track `reap/k91-coding-vram`. Esperimento: una mask REAP **estrema K91** (tieni ~9% degli
> expert, 23/256 per layer) guidata dalla saliency del **dominio CODING** fa entrare il
> working-set del DeepSeek-V4-Flash 2-bit **interamente nella VRAM di una GPU 12GB** — e il
> modello sa ancora scrivere codice? **STATO: IN CORSO** (risultati sotto man mano).

## Ipotesi e matematica (da verificare, non ancora confermata)

- 12GB VRAM − backbone (~5.8 GiB atteso, **da misurare**) = ~6.2 GiB liberi → cache expert.
- K91 = keep **23/256** (`round(256*0.09)=23`), drop 233, sui **40 layer non-hash** (3..42).
  Layer 0-2 = hash routing, mai potati (design doc §0.2).
- Expert residenti a regime = 23 × 40 = **920 expert** × 6,75 MiB/expert (=7.077.888 B, geometria
  `runs/reap/gguf_flash_expert_geometry.txt`) = **6,06 GiB**.
- **"Entra in VRAM"** = PROVA che, con la bias-mask K91 attiva e cache VRAM ≤ budget 12GB, dopo
  warm-up `DS4_SPEX_STATS` mostra `direct_loads` a plateau (0 nuovi stream) e hit-rate → ~1.0.
  La bias-mask NON rimpicciolisce il file (86GB mmap): mette -1e9 sui bias dei potati → solo
  23/layer vengono MAI selezionati → resident-set effettivo ~6 GiB.

## Tre esiti possibili (tutti da riportare onestamente)

- **(A)** entra + codifica bene = risultato forte.
- **(B)** entra ma codifica male = K91 troppo aggressivo per un dominio largo (datapoint curva K-qualità).
- **(C)** non entra = tieni la matematica backbone.

## Contesto: curva K-qualità già misurata (dominio "Segnali", NON coding)

Da `runs/reap/2026-07-05_eval_biasmask_v2/` (H200, ppl teacher-forced, CI95):
K50 dom **1.010×** (lossless), K67 **1.076×**, K70 ~1.11×, random **1.388×**. Nessun punto
oltre K70, nessun dominio coding, nessun target 12GB → **questo esperimento è nuovo su tutti e tre**.

## Setup (verificato)

- **GPU: RTX 3080 Ti 12288 MiB (sm_86)** = stessa architettura del RTX 3060 dell'utente, e VRAM
  reale 12GB → il tetto 12GB è **hardware vero, non un budget forzato** (risultato più forte).
- Pod RunPod community, dettagli/costi in `meta.json`.
- ds4 `80ebbc3` + patch **0001-0007**, `make cuda CUDA_ARCH=sm_86` → BUILD_OK,
  `make cuda-regression` → "cuda long-context regression: OK".
- Modello `DeepSeek-V4-Flash-IQ2XXS-...-imatrix.gguf` (86.720.111.488 B, byte-identico al
  daily-driver locale), da HF `antirez/deepseek-v4-gguf`.
- Trace coding: **generata sul pod** dai 12 prompt `coding_en/c00..c11` (i CSV coding non
  esistevano in repo; solo i prompt) con `DS4_SPEX_TRACE_ROUTING`+`DS4_SPEX_TRACE_ROUTING_WEIGHTS=1`
  (patch 0006).

## Metodo (playbook §4)

1. Trace coding (12 prompt, greedy temp0, `--nothink`, `-n` fisso, weights) → CSV.
2. Saliency g-only (`reap_saliency_ds4.py`) → mask **K91** (keep-frac 0.09) + **K50-coding**
   (keep-frac 0.50, controllo qualità intermedio) + random control embedded.
3. Fit: bias-mask K91 applicata, `DS4_SPEX_STATS=1`, cache VRAM entro 12GB → hit-rate/direct_loads.
4. Qualità: prompt fisso sito web HTML+CSS+JS, stesso seed, config **K0 (full) / K50-coding / K91-coding**.
5. Report qui + `meta.json`.

## Risultati

_PENDING — compilati man mano che le misure arrivano dal pod._

### Fit (entra in VRAM?)
_pending_

### Qualità (3 siti)
_pending_

### Verdetto A/B/C
_pending_
