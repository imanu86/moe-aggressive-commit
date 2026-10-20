# Handoff Strata — 20/10/2026 04:20 (piano Claude all'1% settimanale)

## Stato macchina
- **Strata acceso sulla 8100 per gli agenti locali**: `servi_agenti.py` (guardiano RAM: <3 GiB per 2 letture → riparte con
  `strata-0145-agenti.json`), config `D:\ds4_work\strata\Strata\strata-dyn-agenti.json` = build `build-batchdyn-c4af6851`
  (`STRATA_BATCH_DYNAMIC=1`, passaggio a caldo chat singola↔agenti). Log: `D:\ds4_work\strata\sota\servi_agenti.log`.
  Tiene `bench.lock` («SERVIZIO-AGENTI-8100»). Per spegnerlo: chiudere il python di `servi_agenti.py`, poi taskkill strata.exe,
  rimuovere `lab_locks\bench.lock`.
- **Agente locale in corso** (Claude Code via `locale_agent.py` su Strata, modello «claude-haiku-5-5» = Strata): B ad albero su
  `lab/overlap` (`Strata-wt\overlap`), brief `corse_2080ti\20261019_locale\brief_obiettivo1_d.md`, log `agente1e.log.jsonl`.
  Chiude con «FINE LAVORO»; le misure le mette in `corse_2080ti\20261019_locale\CODA_MISURE.md`.
- **Daily da usare**: 0.1.43 r2 (bat sul Desktop). La bat **0.1.45 Daily** (batch fisso) NON va usata per la chat singola (24-29 t/s).

## Come si lavora senza token Claude
1. Agente locale: `PYTHONIOENCODING=utf-8 python -u locale_agent.py --brief <brief.md> --cwd C:\Users\imanu\source\repos\Strata-wt --model claude-haiku-5-5 --log <x>.log.jsonl`
   (Strata acceso sulla 8100; l'agente non deve usare GPU né fermare strata.exe; compila con `build_lock_noeng.py`).
2. Misure: `corse_2080ti\20261019_locale\misura_ov2.py` ferma il servizio, esegue i comandi della sezione datata di
   `CODA_MISURE.md` (adattare i marcatori `# CODA ...` / `## 15.`), riaccende il servizio. **Non tenere bench.lock attorno a
   det_force.sh**: `run_long.py` lo prende da solo (il 19/10 tenerlo ha bloccato ogni braccio 50 min).
3. Piano di riferimento: `PIANO_GLOBALE_2026-10-19.md` (Fable).

## Numeri chiave (banco della comunità, stesso script dei report upstream)
| config | decode 4K/32K/128K t/s | prompt 128K t/s |
|---|---|---|
| 2x RTX 5060 Ti Linux (comunità) | 84,8 / 86,5 / 83,8 | 2440 |
| Daily 0.1.43 r2 | 75,9 / 70,4 / 75,3 | 1720 |
| 0.1.43 + `--spec-min-p 0.70` (un braccio, testi diversi) | — / 77,2 / 81,1 | — |
| 0.1.45 senza batch | 67,0 / 66,4 / 69,2 | 1519 |
| batch-dyn (chat singola) | 68,0 / 65,8 / 68,2 | 1487 |
| 0.1.45 batch fisso | 24-28 | 464 |
- batch-dyn aggregato decode 2/3/4 conversazioni: 45-57 / 71-78 / 88 t/s; replay non misurato (fix RAM c4af6851).
- 0.1.45 vs 0.1.43: decode −8/−12% a parità di bozze (+2 ms a finestra), causa non trovata (sospetto: leve struct-a non
  portate NODECUT/TOPK_GRID/B6_HEAD_MINB) → `corse_2080ti\20261019_banco_comunita\BISEZIONE.md`.
- `STRATA_BF16_TC=1`: prompt 131k −12,5% senza perdita di accettazione; `HC16_SM75=1` −11,6% → candidati al Daily.
- Overlap: `MTP_STAGE0` −17% (no), NOSWITCH/CHAIN_PRIO ~0, seconda scelta giusta 45% (seriale) / 29,5% (pipeline) → B ad albero.

## Lavori aperti (doc con comandi pronti)
- `OVERLAP_2026-10-19.md` + `lab/overlap` — B ad albero (in corso), metro A/A col pipeline (avvio >300 s), min-p B comunità.
- `PASSATA_UNICA_2026-10-19.md` + `lab/passata-unica` — `STRATA_PACK_CONCURRENT`, codice scritto, mai compilato.
- `BATCH_DINAMICO_2026-10-19.md` + `lab/batch-dyn` — replay da rimisurare, patch 21 da rigenerare, prefisso comune unico.
- `Strata-wt\upsync-main\docs\UPSYNC_020.md` + `lab/upsync-020` — 18 patch portate su 0.2.0-beta, da compilare e misurare;
  leve sm_86 a mano (ADAPT_NOWAIT, ADAPT_LAG=2, CPU_IQ_ALL_EXACT1, GR_UP75, GU_SWIGLU). PR: aggiornare #2073/#2081, ritirare #2080.
- `MISURE_STADIO0_2026-10-19.md`, `STIMA_5060TI_2026-10-19.md` — 5060 Ti allo stadio 0: decode +9/+18% (centrale +14%);
  OktoCGControl tiene ~1,9 GB sulla 3060 (ogni GiB liberato ≈ −1,48 ms/token).

## Aggiunta 20/10 mattina
- 4 agenti locali in corso sulla passata unica (`corse_2080ti/20261020_4agenti/`, brief1-4, stato in agente1-4.md). Per fermarli: chiudere i python di `locale_agent.py`.
- Misura reale 4 agenti (primi 4,4 min): ~12-13,5 t/s per agente in decode (~50 aggregati); letture seriali ~560 tok/s; durante una lettura gli altri slot decodificano 14 righe/s; motore occupato 66% del muro. Misura: `misura_4agenti.py` (segna / misura), parziale in `misura_parziale.txt`.
- Albero (lab/overlap): livelli 1-2 compilati, misure in CODA_MISURE.md blocchi 16-18; livello 3 dopo le misure.
