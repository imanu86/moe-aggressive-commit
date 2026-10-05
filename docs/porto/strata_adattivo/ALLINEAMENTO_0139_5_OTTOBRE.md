# Daily 0.1.39 — 5 ottobre 2026

Il Daily operativo e il fork `main` sono allineati a upstream **v0.1.39** (`6f32ec0`). Sorgente congelata e
testata: fork `73cb2d4` (`git archive`, 921 file); manifest e validazione nel commit `46aa04b`; eseguibile
shipping `dd82377ab682108bb6a8e2480727a27e211400df8dd01a4801144a0843270791`.

Conservati: port SM75, cache elastica a due zone (nucleo fisso, coda VMM che ruota e viene prestata al prompt;
solo nel fork), top-k largo #603, checkpoint tail #614, exact-small, QSA grouped-query, prefisso #652. Opzioni di
laboratorio presenti e spente: `STRATA_PREFETCH_NEXT`, `STRATA_ELASTIC_CORE_ADAPT`, `STRATA_LOOKAHEAD_PROBE`,
`STRATA_ROUTED_*`, `STRATA_GATE_KEEP`, `STRATA_LOGPOS`, `STRATA_TRACE` (con budget WDDM e NVML).

## Misure (configurazione del Daily, arena intera registrata)

| | L01 t/s | L02 t/s | prefill L01 (131k) |
|---|---:|---:|---:|
| Daily 0.1.39 shipping | **51,4** | **44,2** | 123 s |
| port 0.1.39 senza i commit di laboratorio | 46,4 · 43,4 | 41,3 · 41,8 | 128 s |
| Daily 0.1.38 | 38,7 | 38,0 | 129 s |

Il guadagno viene dal lavoro dell'host per strato (da ~2,8 a ~0,5 ms per finestra). Una corsa ha avuto 294 s di
prefill: la tabella PLE letta dall'SSD (195 s bloccati in letture contro 6 s), non il motore.

Fedelta' in teacher forcing contro il Daily 0.1.38 (risposte greedy del Daily su code/explain/ledger; A/A = Daily
contro se stesso): KL 0,0004 / 0,0020 / 0,0001 (A/A 0,0004 / 0,0005 / 0,0001); perplessita' -0,16% / -2,10% /
+1,07% (A/A +0,32% / -0,19% / +0,13%). Nessuno spostamento sistematico; su explain 2 dei 524 token sicuri cambiano.

Controlli: CTest 8/8 (top-k attivo, gr, gdn, router dot, cache elastica, cache per strato, profilo); pool CPU
64 casi sul GGUF reale bitwise; test server 262/271 (7 saltati; `test_winjob` legge `tasklist` come UTF-8 su
Windows italiano; `test_responses` json_schema 502 fallisce identico su upstream 0.1.39). Avvio del server
installato sulla 8100: salute e oracolo JSON `DAILY-039-READY` superati, avvio in 41 s.

## Installazione e ripristino

Cartella `D:\ds4_work\strata\Strata\build-0139-daily` (eseguibile, sorgente congelata, manifest); config e BAT
del desktop puntano li'; checkout del Daily avanzato in fast-forward a `46aa04b`; 48 file non tracciati preservati;
`build-0138-daily` intatta. Ripristino: `D:\ds4_work\strata\ripristini\20261005_093653_allineamento039` (bundle dei
due repository, config, BAT, manifest, file non tracciati): per tornare alla 0.1.38 basta ricopiare config e BAT.

[Release](https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.39-sm75-20261005-r1). Script e registri:
`corse_2080ti/20261005_daily0139/`. Limiti: una corsa di velocita' per braccio, fedelta' su tre compiti corti;
qualita' generale, schede da 11 GB e multi-GPU non validate.
