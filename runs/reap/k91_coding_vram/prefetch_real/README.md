# Prefetcher hidden-probe: t/s REALE (2026-07-07) — il seguito engine di Part C-T2

> Part C-T2 aveva mostrato in SIMULAZIONE che il prefetch layer-ahead alza l'hit-rate (0.616 vs
> no-prefetch 0.0-0.56). SPEX: "recall != velocita', provala sul vero engine". L'ho fatto: wire-ato
> il dense-oracle in ds4 (patch 0015, `ds4_spex_predict_topk` su `cpu_router_norm` -> prefetch async
> di L+1), fittato il `.spex`, buildato ds4-probe (sm_86), misurato il t/s VERO. Full q2, cache=400.

## Il wiring FUNZIONA (verificato)
`ds4: SPEX hidden-probe loaded probe.spex (43 layer, 4096 embd, 256 expert)` +
`ds4: SPEX hidden prefetch L4->L5 experts=6 ok=1` per ogni layer. Il probe predice e prefetcha
davvero. K configurabile via `DS4_SPEX_HIDDEN_K`.

## Risultato: sul pod (RAM calda) il prefetch RALLENTA
| config | n=64 | n=256 | n=576 |
|---|---:|---:|---:|
| **baseline** (no prefetch) | **2.09** | **2.27** | **2.32** |
| 0003 selection-continuity | 0.88 | 0.61 | 0.52 |
| hidden-probe K=6 | 0.83 | 0.86 | — |

Entrambi i prefetch sono **2.5-4.5× PIU' LENTI** del baseline, consistente su tutti i segmenti.

## Perche' (e perche' NON contraddice il gate)
Il **gate** (misura precedente, binario ds4-pace, SSD/cache FREDDA) aveva mostrato il contrario:
baseline cold-start n=64 = **0.24** t/s, 0003 = **0.77** (3.2× piu' VELOCE). Differenza cruciale:
- **Gate = cache/RAM FREDDA**: le miss colpiscono l'SSD (lente) -> il prefetch le nasconde -> aiuta.
- **Questa misura = RAM CALDA** (il modello 80GB e' nella page-cache dopo ore di run): le "miss"
  sono servite dalla RAM (veloci, baseline gia' 2.2 t/s) -> il prefetch non ha latenza da nascondere,
  aggiunge solo overhead (seed async + 240 expert-load extra/token + eviction) -> **rallenta**.

## VERDETTO: recall != velocita', CONFERMATO e raffinato
Il segnale del probe e' accurato (recall 0.63, prefetcha correttamente) MA la conversione in t/s
**dipende dal regime**:
- **SSD-latency-bound** (cache fredda, RAM povera): il prefetch AIUTA (gate: 3.2× sul cold-start).
- **RAM-served** (pod con 251GB, page-cache calda): il prefetch RALLENTA (overhead > beneficio).

**Implicazione per il target reale (3060, RAM limitata):** il 3060 NON puo' tenere gli 80GB in
page-cache -> e' SSD-bound -> il prefetch probabilmente AIUTA (come il gate cold-start). Ma **sul
pod non e' misurabile** perche' la RAM ricca rende le miss gratuite (lo stesso motivo per cui i t/s
del pod sono ottimistici, vedi lo streaming-analysis). L'hit-rate simulato di Part C-T2 e' reale ma
si materializza in velocita' SOLO quando le miss sono davvero costose.

**Prossimo passo per un numero definitivo:** misurare su hardware SSD-bound reale (3060, o pod con
`echo 3 > drop_caches` che il container non permette) — li' il prefetch dovrebbe convertire il recall
in t/s. Sul pod caldo il risultato onesto e': **il prefetch e' controproducente**.

Caveat: n=1/config, cache=400, 1 prompt; effetto grande (2.5-4×) e consistente su 3 segmenti ->
robusto entro il run, ma la RAM-calda vs cold non e' stata isolata con drop_caches (bloccato nel
container). Wiring: patch `0015` (`patches/ds4/0015-*.apply.py`). Artefatti: `measure/`.
