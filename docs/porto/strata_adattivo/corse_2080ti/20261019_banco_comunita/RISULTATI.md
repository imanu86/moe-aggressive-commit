# Banco della comunità sul nostro PC (19/10/2026)

Script identico ai report della comunità (`bench/results/2026-09-30-community-rtx-5090/benchmark.py`): prompt freschi 4K/32K/128K,
3 corse ciascuno, greedy, 256 token, ragionamento off. Runner: `community_bench.py` (sotto bench.lock, porta 8105). Jump scollegato
in tutte le corse; OktoCGControl aperto (condizione standard). Corse in sequenza, non B-A-B: una corsa per configurazione.

Mediane (prompt tok/s | decode tok/s):

| config | 4K | 32K | 128K |
|---|---|---|---|
| 2x RTX 5060 Ti, Linux (comunità, 2026-10-05, 0.1.39) | 911 / 84,8 | 2087 / 86,5 | 2440 / 83,8 |
| Daily 0.1.43 r2 (`build-0143-daily`) | 701 / 75,9 | 1439 / 70,4 | 1720 / 75,3 |
| 0.1.45 senza batch (`strata-0145-nobatch.json`) | 663 / 67,0 | 1282 / 66,4 | 1519 / 69,2 |
| Daily 0.1.45 con `--batch 4 --batch-groups 2` | 340 / 24,6 | 461 / 27,0 | 464 / 27,9 |

- Con `--batch` la chat singola crolla: cache esperti fissa, `--pipeline-windows 2` spento, 1,46 GiB di slot sulla 3060 e 0 MiB
  liberi all'avvio (paging WDDM), disk cache conversazioni spenta. La config multi-agente non va usata per la chat singola.
- 0.1.45 senza batch è sotto la 0.1.43 su tutti e 9 i punti: prompt -5/-12% (manca hc16 nella build), decode -6/-12% (da
  bisezionare: env tolte NODECUT/QFUSE_HC/TOPK_GRID/B6_HEAD_MINB, aggiunte PIPED_CONCURRENT/P2_FLUSH_NOSWITCH; il B-A-B DET del
  18/10 dava parità con finestre forzate).
- Contro la comunità: decode -10/-19%, prompt -23/-31%.
