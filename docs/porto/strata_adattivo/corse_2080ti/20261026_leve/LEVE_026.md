# Leve sulla Daily 0.2.6: build pronta, coda da lanciare - 26 ottobre 2026

**Stato: compilato si (sm_75+86), installato no, provato no, misurato no.** Nessun `strata.exe` e nessuna GPU usati oggi; la Daily
(`build-026-daily`, `strata-026-daily.json`) non e' stata toccata.

## 1. Cosa e' pronto

Branch `lab/leve-026` del fork (`imanu86/Strata-2080Ti`), worktree `C:\Users\imanu\source\repos\Strata-wt\leve-026`, da `lab/upsync-026`
(v0.2.6 + 19 patch). Quattro patch nuove in `stack/` (20-23), registrate con `check_anchors.py --build` (23 patch, 426 punti) e `--verify-docs`
(ok); le 23 patch applicate a v0.2.6 danno lo stesso codice del branch. **Tutte spente di default**: senza le loro variabili la build e' la Daily.

| patch | PR upstream (tutte aperte) | interruttore | esito |
|---|---|---|---|
| 20 piped-mtp | #4121 bozze MTP nei gruppi di slot in pipeline | `STRATA_PIPED_MTP=N` + `--batch-mtp` | pulita |
| 21 pipe-adapt-every | #4010 i gruppi in pipeline adattano il livello VRAM | `STRATA_PIPE_ADAPT_EVERY=N` | 2 conflitti con 20, risolti (tengono entrambe) |
| 22 pw-with-batch | #3095 la richiesta sola tiene `--pipeline-windows` con `--batch` | `STRATA_PW_WITH_BATCH=1` | commit `890bbca5` di `lab/multichat45b` ripreso, 1 conflitto (su 0.2.6 non c'e' `batch_pipe`) |
| 23 branch-checkpoints | #2527 + #2528 + #2843 (impilate: #2843 le contiene) | `STRATA_PIPELINE_ACTIVE_ROWS=1`, `STRATA_SLOT_CACHE_AFFINITY=1`, `STRATA_SLOT_CHECKPOINTS=N`, `STRATA_BRANCH_CHECKPOINT=<margine>`, `STRATA_CACHE_TRACE=1` | 4 conflitti con 20, risolti; un solo errore di compilazione (doppio `PGroup::rows`), corretto |

Nessuna PR saltata. Due punti da sapere: (1) con `STRATA_PIPED_MTP` acceso le righe attive (`STRATA_PIPELINE_ACTIVE_ROWS`) restano spente (si escludono: ognuno dei due ha le sue righe di finestra);
(2) la PR #4121 dice «non provato: piu' di uno slot per gruppo», e con `--batch 4 --batch-groups 2` i gruppi sono da 2 slot.

Build: `Strata-wt\leve-026\build-sm7586` (4 job, priorita' normale, `build_lock_noeng_norm.py`, 14 + 1 minuti). Copia in
`20261004_routed_keep\build-leve026-fa5963d5\` (`strata.exe` sha256 `5d6b7274...a464`, `strata-vision.exe` dalla Daily 026, `source\`, `build.json`).

Script toccati (compatibili all'indietro): `20261019_replay\replay_trace.py` (+`--config`, `--only`, `--out-base`; prima la Daily 0.1.43 era fissa nel codice),
`20261025_bisezione\camp_bisezione.py` (+`--config`, `--build`, `--out`), `community_bench_camp.py` (+`CAMP_TARGETS`).

## 2. La coda

`20261026_leve\coda_leve_026.py`, **non eseguita**. Config come copie in questa cartella (`make_configs.py`, gia' lanciato): `cfg-daily-base.json` (identica alla Daily, verificata),
`cfg-daily-bf16tc.json`, `cfg-leve-r3.json`, `cfg-leve-r3-pw.json`; i bracci del replay partono dalla Daily e applicano `--extra`/`--env` (visibili con la prova a secco).

```
python coda_leve_026.py              # prova a secco: ordine, durate, file mancanti
python coda_leve_026.py --vai        # esegue tutto (PC libero)
python coda_leve_026.py --vai --fino 4 | --riprendi
python coda_leve_026.py --analisi    # tabella base | leva | base con scarti
```
Rifiuta di partire, e si ferma tra un passo e l'altro, se c'e' un `strata.exe` vivo, `lab_locks\pause`, `bench.lock` o `build.lock`. Scarta la prima richiesta di ogni avvio
(warmup del banco, piu' la prima da 4K ancora fredda; nel replay le letture a `max_tokens 1` prima del cronometro). Terne concatenate: la base in mezzo e' unica
(base-L1-base-L2-base), ogni leva ha una base subito prima e dopo; una terna con le basi a piu' del 3% (banchi) / 5% (replay) e' marcata instabile.

Replay: traccia DSH del 16/10, finestra 3600-4800 s, **tre agenti = sessioni A, B, C** (i tre sotto-agenti; l'orchestratore P, 140K di contesto, e' escluso: se serve
anche P, togliere `--only`). Batch: `--batch 4`, cache conversazioni 18432 MiB / 16 posti, riserva 1905 / 700 MiB. Arm: R0 Daily senza batch, R1 `--batch 4` (default 0.2.6),
R2 `--batch-groups 2`, R3 = R2 + `STRATA_PIPED_CONCURRENT=1`, R3L = R3 sulla build leve026, L1 +`--batch-mtp` +`STRATA_PIPED_MTP=1`, L2 `STRATA_PW_WITH_BATCH=1`,
L3 `STRATA_PIPE_ADAPT_EVERY=128`, L4 righe attive + affinita' + `STRATA_BRANCH_CHECKPOINT=1024` + `STRATA_SLOT_CHECKPOINTS=2`.

| # | passi | prova | durata | perche' in questo posto |
|---|---|---|---|---|
| 1 | 01 | a1: `presence_penalty` 0 contro 1,5 a T=0,7, Daily 0.2.6 (`camp_bisezione.py --solo nopp`, 3 avvii) | 18 min | con la penalita' la pipeline a due finestre si spegne (-12% a T=0,7): costo minimo, guadagno noto |
| 2 | 02-04 | b1: R3L / L1 `PIPED_MTP` / R3L | 60 | upstream +20-30% su 4 stream; e' il carico vero |
| 3 | 05-11 | b2-b4: R0 / R3 / R0 / R2 / R0 / R1 / R0 | 140 | quanto vale il batch di per se' e quanto PIPED_CONCURRENT |
| 4 | 12-14 | a2: `STRATA_BF16_TC=1` a T=0, banco completo 4K/32K/128K (hc16 gia' in uso: atteso poco) | 33 | |
| 5 | 15-17 | a3 (extra): chat singola con batch acceso, `STRATA_PW_WITH_BATCH=1`, 4K/32K | 21 | e' il caso vero di #3095 |
| 6 | 18-24 | b5-b7: R3L / L2 / R3L / L3 / R3L / L4 / R3L | 140 | la traccia non ha rami: L4 e' un controllo di non-regressione |

**Totale stimato 6 h 52 min** (24 passi: 20 min per braccio del replay, 11 min il banco lungo, 7 il corto; stime da avvii di 75-105 s e dai replay del 19/10, non misurate su 0.2.6).
Cumulo ai punti di taglio: 1 h 18 dopo b1, 3 h 38 dopo la scala del batch, 4 h 32 dopo i banchi, 6 h 52 alla fine. Vincoli: 18 GiB di RAM per la cache conversazioni nei bracci con batch;
Jump Desktop va annotato (il runner scrive `ambiente.txt`).

Non nella coda: Daily contro R3L a leve spente (controllo che la build leve026 equivalga alla Daily) e `STRATA_BF16_TC=1` con `STRATA_HC16_SM75=0`.
