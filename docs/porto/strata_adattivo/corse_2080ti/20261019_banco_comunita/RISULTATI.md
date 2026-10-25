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

## 25/10/2026 - Strata v0.2.6 (motore 0.1.51): pura e con la pila

Branch `lab/upsync-026` (v0.2.6 + 18 patch, nessuna ritirata, 3 adattate: 04, 05, 06) e `lab/upsync-026-pure`; build sm_75+86 `build-up026-4b9e05a2`
(A) e `build-up026pila-ffe66174` (B); config e log in `20261025_upsync026\`; dettagli in `docs/UPSYNC_026.md` del fork. Ordine Daily, A, B, Daily
(`run_all.sh`), corse del 25/10 dalle 18:00 alle 18:53. Compilato si, installato no. **Jump Desktop (sessione 1) e OktoCGControl aperti in tutte le
corse** (Jump ~6 s di CPU a corsa), priorita' normale, `STRATA_NO_PRESET=1`. bench.lock di `LC-a1` (agente morto il 20/10) rimosso dal coordinatore.

Mediane (prompt tok/s | decode tok/s):

| config | 4K | 32K | 128K |
|---|---|---|---|
| Daily 0.1.43 r2, 19/10 (riferimento, Jump scollegato) | 701 / 75,9 | 1439 / 70,4 | 1720 / 75,3 |
| Daily 0.1.43, 25/10 corsa 1 | 494 / 39,2 | 1038 / 40,6 | 1172 / 40,1 |
| A: 0.2.6 pura, default due schede | 540 / 33,4 | 630 / 39,5 | 681 / 21,8 |
| B: 0.2.6 + pila, config Daily + `HC16_SM75=1` | 507 / 34,9 | 998 / 33,0 | 1236 / 34,6 |
| Daily 0.1.43, 25/10 corsa 2 | 481 / 37,9 | 966 / 36,7 | 1171 / 39,6 |

- **Il PC oggi e' circa la meta' del 19/10**: il Daily scende da 75/70/75 a 39/41/40 decode. Causa probabile: VRAM occupata da altri processi (la 2080 Ti
  aveva 1,7 GB gia' presi dal desktop prima della corsa; in B la scheda CUDA1 parte con 31 MiB liberi, in A con 62, nel Daily 1,3 GB liberi), paging WDDM.
  Non e' un confronto con la tabella del 19/10: contano solo le righe del 25/10, Daily prima e dopo concordi entro ~10%.
- A (pura, default) ha decode 33/40/22 con forte varianza (18-50 al 128K) e prompt 32K/128K piu' bassi di meta' del Daily: senza cache elastica, senza
  leve sm_86/sm_75 e con 62 MiB liberi su una scheda, va peggio del Daily. B (pila + config Daily) recupera il prompt 128K (1236, pari al Daily) ma il
  decode sta a 33-35 contro 37-41 del Daily (-8/-15%), compatibile con soli 31 MiB liberi in avvio (il Daily ne aveva 1,3 GB). Da ripetere a VRAM libera
  (desktop chiuso o prova fra le ore calme) prima di concludere sulla pila; qualita' (token, accettazione bozze) non confrontata.

### 25/10 PC pulito (Jump staccato, OktoCGControl aperto) — prompt / decode t/s, 3 corse per 4K, 32K, 128K
- Daily 0.1.43 (1): 629-662/66-71 · 1370-1385/67-73 · 1547-1580/71-73
- v0.2.6 pura (A): 624-655/57-64 · 1228-1241/51-59 · 1264-1294/58-62
- v0.2.6 + pila (B, build-up026pila-ffe66174): 643-690/61-69 · 1419-1432/58-66 · 1621-1640/66-69
- Daily 0.1.43 (2, interrotta): 654-675/56-78 · 1398-1401/69-72 · 1604/73
- Verdetto: pila sulla 0.2.6 = +27% prompt a 128K sulla pura e sopra la Daily (1630 vs 1570); decode -4/-6% sotto la Daily. Prossimo: braccio Bx (Daily senza NODECUT/QFUSE_HC/TOPK_GRID/B6_HEAD_MINB), non eseguito (owner ha chiesto il PC).
