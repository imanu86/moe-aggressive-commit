# Handoff Strata 13/10/2026 — da dove riprendere

Obiettivo dell'owner: **80+ t/s** in singola chat a 131k (RTX 3060 su Oculink x4 col monitor 8K = stadio 0, layer 0-15;
RTX 2080 Ti 22 GB = stadio 1, layer 16-47 + testa + MTP), **multi-chat** con aggregato vicino al doppio, TTFT basso.
Piano Max quasi esaurito (6% della settimana il 13/10): il lavoro prosegue su **agenti pagati coi crediti API** (§5).
Storia completa: `HANDOFF_STRATA_UPSYNC_2026-10-11.md` §8-13; analisi `ROOFLINE_2026-10-12.md`; ricognizione
`RICOGNIZIONE_PR_FORK_2026-10-13.md`.

## 1. In uso

| Server | Dove | Stato |
|---|---|---|
| **Strata 0.1.43 Daily** (consigliato) | `D:\ds4_work\strata\Strata\build-0143-daily\`, `strata-0143-daily.json`, bat `Desktop\SERVER IA LOCALE\Strata 0.1.43 Daily - porta 8100.bat` | = fork `lab/struct-a` 075ce875 (v0.1.43 + pila `stack/` + SA_BET/SA_CHAIN +2,5%); provato all'avvio (testo, immagini), non dall'owner |
| Strata 0.1.42 Daily r2 | `build-0142-daily`, `strata-0142-daily.json` (PLE ora da D:) | intatta, ripiego |
| Daily vecchio | `build-be4cf1c-daily` | intatto, non toccare |

Banco a 131k (DET forzato): ~77/70 t/s (L01/L02) con OktoCGControl chiuso; aperto −7% (disegna sulla 3060).
Regole di misura: solo B-A-B, di notte o a PC fermo, PLE da D:, riscaldamento prima di B1 (`coda_*.sh` in
`corse_2080ti\20261006_due_schede\`). Verifiche bitwise: `--expert-cache 1500`, senza `--elastic`, `--adapt-every 0`.

## 2. Esiti (per non rifare)

- Promossi: EXPDEC (+1,1%), QSA_ROWS (+1-1,5%), SA_BET+SA_CHAIN (+2,5%).
- Neutri o peggio: NODECUT/TOPK_GRID/HEAD_MINB (speed4), DENSE_WR (speed2), EXPDEC_WT (speed3, più lento),
  HG_PRELAUNCH, split 14, SB_FRESH (struct-b), SC_SNAP_INLINE (struct-c), pool CPU separato (≤0,2 ms, non fatto).
- **MTP affinato: abbandonato** (pod 17,6 $; guadagno solo ≤4k e nel dominio; a 131k e fuori dominio peggio).
- Diagnosi: le leve sui kernel della 2080 Ti non accorciano la finestra; il percorso critico è la serie stadio 0 →
  stadio 1 + catena MTP + attese host (~10 ms in serie su ~26). Nessun P2P fra le schede (scambi via RAM 7-46 µs).

## 3. Upstream

7 PR aperte con commento a @Niko1221: #2058 EXPDEC, #2059 QSA_ROWS (blange48: neutre su 4×5080, nota di scopo
aggiunta), #2073 PLE direct, #2075 ATTN_DAILY, #2077 prompt-cache-file, #2080 SIMT default, #2081 dequant sm_75.
Registro pubblico della pila: `stack/` (INDEX.md, BLOCKS.md, patch, `check_anchors.py`) su `main` del fork; base
`lab/upsync43-pulito`. Upstream ha la 0.1.43.1 (multi-chat `--batch-groups auto`): da portare.

## 4. Lavori aperti (stato nei doc dei rispettivi worktree `C:\Users\imanu\source\repos\Strata-wt\`)

| Lavoro | Branch / doc | Prossimo passo |
|---|---|---|
| Pipeline: post() persistente per layer (−0,7/−1,5 ms, bitwise) + tappa 0 (P-state, polling senza cudaSetDevice) | `lab/pipeline2`, `docs/PIPELINE2.md` | proseguire le tappe 0a→4; B-A-B a PC fermo |
| Tensor-parallel + MTP con modalità bivalente (stima 80-86 t/s, 4-6 settimane) | `PIPELINE2.md` (appendice verdetto) | se il verdetto regge: prototipo 1-2 giorni su crediti API (≤60 $) |
| Multi-chat: `--batch-groups auto` senza `--batch-mtp` (0.1.43.1), batching misto prefill+decode, prefisso condiviso fra sotto-agenti | `lab/multichat`, `docs/MULTICHAT.md` | dalla diagnosi alle leve; scenario multi-agente con prefisso comune |
| TTFT: un file per prefisso, salvataggio asincrono, PLE in anticipo portati su 0.1.43; banco TTFT; conversazioni su disco | `lab/ttft43`, `docs/TTFT43.md` | misurare, poi piano (conversazioni fra riavvii, cache PLE, riscaldamento) |

Decisioni dell'owner in sospeso: PLE tutta in RAM (`--ple-io ram`, 26,8 GB, toglie le attese del prefill) da
misurare; pulizia di C: (doppione PLE 28,8 GB in Downloads da cancellare dopo sha256; build vecchie del lab su D:).
Escluso per ora: cambio della 3060.

## 5. Come proseguire coi crediti API (200 $ fino al 17/10, ~120 $ per Strata, il resto a PROMO5)

`python sdk_agent.py --brief <brief.md> --cwd <worktree> --budget <dollari>` (in questa cartella): Agent SDK locale,
Opus 5.5, chiave dal registro (`STRATA_SDK_API_KEY` + `STRATA_SDK_WORKSPACE_ID`), tetto rigido di spesa, log jsonl
accanto al brief. Il brief deve ripetere le regole: GPU solo con `D:\ds4_work\strata\lab_locks\bench.lock` (O_EXCL),
pausa con `lab_locks\pause`, build con `build_lock.py`, non toccare Daily/config/bat, commit
`OPUS-STRATA-...` con Co-Authored-By e push, stato sempre nel doc del worktree, misurato vs stimato.
Ordine consigliato: (1) pipeline2 tappe 0a-2, (2) multi-chat con 0.1.43.1, (3) TTFT43 misure, (4) prototipo TP se il
verdetto lo giustifica.

## 6. Aggiornamento 13/10 mattina

- **Strata 0.1.43 Daily r2** installata (r1 in `D:\ds4_work\strataipristini61013_0143daily_r1`): build
  `lab/ttft43` a2111f8b + `STRATA_PREFIX_DISK_MULTI=24` (JSON) + `STRATA_PROMPT_ENCODER=1` (bat, ambiente del server).
  Banco TTFT: client alternati 38,2/32,5 → 16,2/4,9 s; dopo riavvio 20,2/10,3 → 6,4/5,1 s (quest'ultimo con
  `STRATA_CONV_DISK`, lasciato spento: avvio misurato 277 s, forse disco lento - in verifica). Non provata dall'owner.
- **Agenti sui crediti API** (`sdk_agent.py`, ripresa automatica fino a «FINE LAVORO»), brief e log jsonl nella scratchpad
  della sessione: pipeline2 (tetto 25 $), multichat43 (35 $), conversazioni su disco pigre su `lab/ttft43` (15 $).
  Stato di ciascuno nel doc del suo worktree (PIPELINE2.md, MULTICHAT.md, TTFT43.md).
- TP bivalente (PIPELINE2.md §9): **no**, con MTP pari a oggi (~76/66 t/s). Multi-chat: migliore configurazione misurata
  `--batch 4 --batch-groups 2` senza `--batch-mtp` (86 t/s a 4 chat) ma chat singola −10%: non nel Daily.
- Crediti API: PROMO5 fino a ~47 $; agenti Strata ~22 $ + tetti 75 $. Ci si ferma vicino all'esaurimento.
