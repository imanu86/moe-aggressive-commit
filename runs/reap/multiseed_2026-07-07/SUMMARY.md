# Multi-seed per il paper REAP-LOOP (2026-07-07)

> Repliche N≥3 dei claim-corona (SPEX-main §8.1/§8.2/§8.4), **stessa GPU per ogni
> confronto**, ordine ruotato, env-capture per pod. 2 pod RTX 3090 24GB, stesso host.
> `abc/env.txt`, `paired/env.txt`: ds4 `80ebbc3` + 0001-0007/0011v3/0012, cuda 12.8,
> driver 580.159.03, gguf sha256 `efc7ed60…6668`.

## ⚠️ Due correzioni oneste dalla replica

**(1) L'asimmetria HOT/COLD NON replica → RITRATTATA.** Con la mask davvero attiva
(aderenza 0.00% verificata su TUTTI e 6 i run), rep-rate (frazione 4-gram ripetuti):
- HOT: [0.026, 0.026, 0.064] · COLD: [0.033, 0.045, 0.029] — **sovrapposti, entrambi puliti**.
- Il precedente "HOT 94% vs COLD 70%" era l'artefatto della mask-inerte (bug cold-start, fix
  0011-v3) + rumore n=1. **Non c'è asimmetria di qualità hot/cold.**

**(2) I t/s del multi-seed misurano un BUILD BUGGATO (0011-v3 + staircase) → non usarli
come headline.** Diagnostica pulita sullo stesso pod:
| config (cache-1024, n=250) | hit_rate | t/s |
|---|---:|---:|
| full (no mask) | 0.607 | 3.6 |
| **file-mask keep-23 (attuatore ground-truth)** | **0.986** | **17.3** |
| runtime-v3 keep-23 STATICA da tok0 | 0.923 | 11.4 |
| runtime-v3 STAIRCASE (i run multi-seed) | 0.557 | 2.5 |
→ Il meccanismo mask dà 11-17 t/s a hit 0.92-0.99. **La staircase avvelena la cache** (le fasi
larghe di warmup caricano expert che poi non servono, cache-1024 sporca) → 2.5 t/s. È un
**trade-off coerenza-vs-velocità reale**, non un fallimento del meccanismo. [ENG-BUG aperto:
0011-v3 re-apply + cambio-mask perde il beneficio-cache; la statica no.]

## ✅ Control B / Paired ppl — il risultato pulito per il paper

**ppl teacher-forced è DETERMINISTICA** → i 3 seed sono bit-identici (nessuna varianza di
seed). La varianza vera è sul TESTO → CI bootstrap sui **chunk** (metodo `paper_ci.py`,
B=10000, seed 42), non sui seed.

**Paired eval (chiude il confondente §8.2 — full/reap/rand STESSA GPU, ordine interleaved):**
| ratio | punto | CI95 (4 chunk) | lettura |
|---|---:|---|---|
| reap(K50)/full | **1.009×** | [0.972, 1.035] | near-lossless, CI attraversa 1.0 → **[OPEN]** (onesto) |
| rand/full | **1.356×** | [1.234, 1.460] | il random degrada |
| **rand/reap** | **1.345×** | **[1.270, 1.423]** | **CI ben sopra 1.0, NON sovrapposta a reap/full → il contrasto ORDINALE saliency≪random, pulito dal confondente hardware** |

**Control B (keep-23 su un testo, punto — deterministico, no CI):**
session/full **1.06×** · domain-mean/full **4.80×** · random/full **7.02×** (ordinamento forte).

## H2H (§ scettico) — confermato per la config statica

Loop mask-statica keep-23 (cache-1024, **6.9GB**) **11-17 t/s** hit 0.92-0.99 vs stock
reattiva (cache-2048, **13.8GB**) 3.6 t/s hit 0.60 = **~3-4.8× a METÀ VRAM**. La staircase
(2.5 t/s) NON è la config da citare per la velocità: si cita la mask statica.

## Verdetto per l'innesto nel paper
- §8.1 asimmetria hot/cold: **rimuovere il claim** (non replica).
- §8.2 paired: **rand/reap 1.345× CI [1.27,1.42] non-sovrapposta** = il contrasto ordinale pulito;
  reap/full resta [OPEN] (CI attraversa 1.0).
- H2H: valido per la mask statica (3-4.8× a metà VRAM); dichiarare il costo-velocità della staircase.
- ENG: 0011-v3 ha un bug cache con la staircase; PACE (0014, in test) o file-based per i claim di velocità.

Artefatti: `abc/` (gen/tps/trace/mask 3 seed hot+cold+h2h, ppl_results), `paired/`
(36 righe ppl 3×3×4), `env.txt` per pod.
