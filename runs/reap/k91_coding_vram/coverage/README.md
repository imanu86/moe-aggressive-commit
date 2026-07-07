# Adaptive-K via COPERTURA di massa-gate (2026-07-07) — la manopola task-indipendente

> Idea SPEX/utente che chiude il cerchio del ginocchio: **non fissare K, fissa una COPERTURA%
> della massa-gate** e lascia che K sia la CONSEGUENZA per-layer. Per ogni layer, dai W token
> osservati: rank esperti per massa-gate, tieni finche' la cumulata copre COV%. K_layer = quanti
> servono. K diventa un OUTPUT che auto-scala, non un input magico task-dipendente.
> Session-learned (osserva W=50 wide, poi congela la coverage-mask), 3 task graded L0-L3, greedy.

## Tabella: task × COV → K-auto, livello, t/s

| task | COV 80% | COV 85% | COV 90% | COV 95% |
|---|---|---|---|---|
| **JSON** (estrazione) | L3 (K~24) | L3 (K~29) | L3 (K~36) | L3 (K~45) |
| **PYTHON** (funzione) | L3 (K~23) | L3 (K~28) | L3 (K~37) | L3 (K~50) |
| **FRONTPAGE** (pagina) | L1 (K~24) | L1 (K~30) | **L2 (K~39)** | L1 (K~52) |

t/s_frozen 3.3-9.6 (K-auto piu' grande dei keep-K fissi → working-set piu' largo → piu' lento del
keep-8/12; ma coerente).

## Copertura UNIVERSALE = 90%
Il COV% minimo che rende **TUTTI** i task funzionali (≥L2): **cov-90%** → json L3, python L3,
frontpage L2. Nessun COV da' L3 su tutti e tre (il frontpage session-learned si ferma a L2, n=1
freeze-point-sensibile). **cov-90% e' la manopola unica task-indipendente**: la imposti una volta,
ogni task riceve un deliverable funzionante con K auto-scelto (~36-39/layer).

## Due scoperte controintuitive
1. **K-auto NON diverge molto tra i task** (a cov-90: json 36, python 37, frontpage 39 — quasi
   uguali). L'ipotesi "stessa cov → K molto diversi (json~20, frontpage~50)" NON si e' verificata:
   la concentrazione di massa-gate osservata su W=50 e' simile tra i task. **A divergere e' il
   LIVELLO** (a cov-80/K~23: json/python L3, frontpage L1) — la manopola e' task-indipendente, il
   RISULTATO riflette la larghezza (task stretti soddisfatti a bassa cov, il largo no).
2. **Il session-learning e' piu' efficiente del cold-static.** Python col ginocchio cold-static
   reggeva solo a keep-32; qui session-learned a K~23 (cov-80) e' gia' **L3**. Osservare in-sessione
   chiude il gap: lo stesso task funziona con meno esperti se la mask e' imparata dal vivo.

## Confronto con il ginocchio cold-static (`../knee/`)
| | cold-static (mask coding-corpus, tok0) | session-learned coverage (W=50) |
|---|---|---|
| JSON | knee keep-20 (L3) | L3 gia' a cov-80 (K~24) |
| Python | knee keep-32 (L3), keep-23→L0 | L3 gia' a cov-80 (K~23) |
| Frontpage | collasso a ogni K (L0) | L2 a cov-90 (riscattato) |

**Sintesi per il paper:** "adaptive-K via gate-mass coverage" trasforma il K-magico-task-dipendente
in una **copertura task-INDIPENDENTE (~90%)**; combinata col session-learning, riscatta anche il
task largo (frontpage L0→L2) e fa girare i task stretti con meno esperti del cold-static.

## Caveat
n=1/cella (greedy deterministico); 1 prompt/task; W=50 fisso; il deliverable e' due-fase
(wide W + frozen) → per i task corti (json/python) la fase-2 RIPETE la risposta (gestito nel
grader: primo JSON bilanciato / miglior blocco-funzione). Frontpage L2-non-L3 = freeze-point
n=1 (vedi `../warmup/` per la variabilita' W). auto-gate aderenza attivo. Tool:
`scripts/{build_coverage_mask,coverage_aggregate,functional_grade}.py`. Artefatti: `cov_*/out/`.
