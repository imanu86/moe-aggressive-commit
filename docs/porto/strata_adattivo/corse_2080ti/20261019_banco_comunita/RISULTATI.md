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

## 25/10/2026 - Strata v0.2.6 (motore 0.1.51): pura e con la pila (banco NON eseguito)

Fatto: branch `lab/upsync-026` (v0.2.6 + 18 patch, nessuna ritirata, 3 adattate: 04, 05, 06) e `lab/upsync-026-pure`; due build sm_75+86
(`build-up026-4b9e05a2`, `build-up026pila-ffe66174`) e config in `20261025_upsync026\`. Dettagli: `docs/UPSYNC_026.md` del fork.
Compilato si, installato no, provato no, misurato no.

Bloccato: `D:\ds4_work\strata\lab_locks\bench.lock` contiene `LC-a1` dal 20/10 08:05; nessun `strata.exe` e nessun processo del banco in vita,
GPU a riposo. Il runner aspetterebbe all'infinito e il lock non lo cancella un agente. Sbloccato, lanciare `bash 20261025_upsync026/run_all.sh`
(ordine Daily, A, B, Daily; tag `up026-daily-1`, `up026-A-pura`, `up026-B-pila`, `up026-daily-2`; Jump e OktoCGControl restano aperti, annotato in `ambiente.txt`).
`community_bench.py` ora accetta una config senza `--prompt-cache-file` (A).

| config | 4K | 32K | 128K |
|---|---|---|---|
| Daily 0.1.43 r2 (riferimento del 19/10) | 701 / 75,9 | 1439 / 70,4 | 1720 / 75,3 |
| A: 0.2.6 pura, default due schede | da misurare | | |
| B: 0.2.6 + pila, config Daily | da misurare | | |
