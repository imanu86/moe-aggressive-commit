# Handoff Strata due schede — 11 ottobre 2026 (riallineamento upstream v0.1.42)

Segue `HANDOFF_STRATA_DUE_SCHEDE_2026-10-07.md` (§1-8 sessione Opus del 7/10, §9 sessione DSH gpt-6-astra).
Obiettivi dell'owner invariati: **80 t/s di decode in chat singola a 131k**, **~120 t/s aggregati in multi-chat**,
**≥ 10 GB di RAM in meno**, visione accesa. Il Daily (`build-be4cf1c-daily`, bat «Strata 2080 Ti - SOTA 30-9 - porta 8100»)
NON va toccato: tutto il nuovo sta sulla base `lab/upsync` con config e bat propri.

## 1. Diagnosi della variabilità («programmi spenti lento, accesi 60-70, spenti 90»)

- Causa principale: **la cache elastica della 3060 si dimensiona sulla VRAM libera vista da CUDA**, che sotto WDDM vede solo il
  processo (es. CUDA 9687 MiB liberi, NVML 8116). Cresce fino a ~500-700 MiB «liberi», poi Windows va in paging e lo
  stadio 0 crolla (log Daily 11/10: richieste 128-146 a 103 ms/finestra e 7-36 t/s con 5879 slot; 32 ms/finestra e 77 t/s
  appena la cache cede 1,1 GiB). Hit rate esperti identico con 4935 o 5879 slot. Upstream #1354 e #1911 descrivono lo stesso.
- Correzione: **#1911 `STRATA_VRAM_FREE=device`** (NVML) portato su `lab/upsync` e usato dall'elastica.
- Il resto della differenza 90 contro 60-70 è il tipo di testo: risposte corte 80-96% di bozze accettate (85-110 t/s),
  lunghe 55-62% (55-86 t/s).
- Altre fonti trovate: 2080 Ti al tetto di potenza (250 W) nell'88% del tempo (alzata a 280 W, 3060 a 200 W, con
  Afterburner; ventola della 3060 con curva minima 35%); intoppi di «host staging» (PLE dal SATA `D:`?) visti una volta a
  40 ms/finestra; worker CPU sul core 0 (`--host-core last` già nel Daily).
- Il motore non è deterministico fra corse anche in greedy (adattamento e CPU/GPU dipendono dai tempi, upstream #410/#1235):
  `target picks replaced` cambia anche fra due A. Per l'identità bit per bit usare i micro-bench dei kernel.

## 2. Prompt cache dentro Claude Code (Haiku → gateway 8787 → Strata)

Sessione 11/10 04:13-04:41: riuso 84,8% contro 97% di DSH. Cause: (1) richieste laterali e conversazioni parallele cancellano
l'unica conversazione viva (455k token persi in 5 cadute); (2) `max_tokens` 128000 → 400 «exceeds the context» → Claude Code
riscrive la cronologia (191k token in 2 cadute). Correzioni nella config nuova: `fit_max_tokens: true`,
`--conversation-cache-mib 6144 --conversation-cache-slots 2`, `--prompt-cache 16`. Da fare: nel gateway
(`docs/porto/qwen_gateway/rotta_locale.py`) non mandare in locale le richieste laterali che restano senza tool, o mandarle
senza ragionamento e senza checkpoint (il gateway va riavviato: chiedere all'owner).

## 3. Branch del fork (imanu86/Strata-2080Ti), worktree in `C:\Users\imanu\source\repos\Strata-wt\`

| Branch | Worktree | Stato |
|---|---|---|
| `lab/upsync` | `upsync` | upstream v0.1.42 + patch del Daily (elastica, prestito prompt, banco forzato, B6 opt-in, elastica col split e la pipeline, prefisso su disco, #1911, #1503, pipeline di architectds theta 0,10, DF_BRANCH/DF_PLE di default, attenzione del Daily `STRATA_ATTN_DAILY=1`, visione CPU). Doc `docs/UPSYNC.md`. **Pari al Daily: +0,7% B-A-B** (build `build-upsync-133e3a69`) |
| `lab/critpath2` | `critpath2` | leve `STRATA_CP_L1FIRST/S1FIRST/CHAIN_PRE/RESPLAN`: **tutte nel rumore** (−0,4/−2,5/+0,1/−0,1%). Doc `docs/CRITPATH.md` |
| `lab/chainfuse` | `chainfuse` | Fable: fusioni della catena MTP `STRATA_CHAIN_FUSE2` (+`_MASK`), micro-bench `chain_step_bench` PASS bit per bit. 2080 Ti: head tail 85→12 µs, merge 45→33, norm/gate/combine −37/−49%; **attenzione fusa più lenta (244→362 µs)**. Motore: MASK 63 −0,9%; **MASK 62 + `STRATA_MTP_SHARED_BRANCH=0` +1,6%** (2,9 / 0,3). Fable sta rifacendo l'attenzione |
| `lab/core-ram` | `core-ram` | nucleo fisso per scheda fuori da scambi/prestiti/shrink, senza copia RAM: **`STRATA_RAM_CORE=1 STRATA_RAM_CORE_SLOTS_DEV1=5500` → arena 39,97 → 29,62 GiB (−10,35), working set 36 GB, t/s +0,1%, hit rate invariato, riletti 0**. Doc `docs/RAM_CORE.md` |
| `lab/wip-0809` | `wip0809` | lavoro non committato della sessione 8-9/10 salvato (dedup V5, merge QSA del Daily) |
| `lab/multichat-mtp`, `lab/ram-dedup`, `lab/gumbel`, `lab/expert-persist`, `lab/prefill-seed` | vedi handoff 7/10 | invariati |

PR upstream aperti: #1117, #1417, #1418 (validato in modo indipendente da Unmaple su 2080 Ti/Windows: bit per bit, −17/−33% kernel), #1419.

## 4. Verdetti dell'11/10 (banco forzato 131k, B-A-B, OktoCGControl SPENTO)

| Leva | Esito |
|---|---|
| upsync (v0.1.42) senza DF_BRANCH/PLE né pipeline di architectds | −4,6 / −7,3 / −7,8% |
| upsync completo (133e3a69) contro Daily | **+0,7% (pari)** |
| `STRATA_ROUTE_TAIL_SKIP=7` (default upstream) | −1,6%: lasciato spento (con 96-98% di hit non serve) |
| leve critpath2 | nessun effetto |
| nucleo RAM | +0,1% e −10,35 GiB: **promosso** |
| catena fusa senza attenzione | +1,6%: da confermare e separare |
| memoria 2080 Ti +250 (involontaria, una corsa) | nessun effetto visibile |

## 5. Visione

Encoder `D:\ds4_work\strata\Strata-data\vision\mmproj-Qwen3.8-Flash-Next-BF16.gguf` (sha256 b1a82259…) e Q8_0
(`...-Q8_0.gguf`, 588 MiB), `strata-vision.exe` CPU in `build-upsync-133e3a69\`. Prova (`prova_vision.py`): immagine letta
correttamente, 9,8 s per 300 token generati. Ora `min_tokens`/`max_tokens` 1024 (backup a 300 in `.bak-0300tok`).

## 6. File per l'owner

- Config nuova: `D:\ds4_work\strata\Strata\strata-upsync-vision.json`; bat `Desktop\SERVER IA LOCALE\Strata upsync VISION - porta 8100.bat`.
- `Desktop\SERVER IA LOCALE\2080Ti-limite-280W.ps1` (non usato: i limiti li applica Afterburner) e
  `Afterburner-attivita-profili.ps1` (da lanciare come amministratore: crea «AB profilo 1/2» per i B-A-B dell'overclock).
- Afterburner: profilo 1 = potenza 112%/117%, memoria +0; profilo 2 = memoria +250 su entrambe. Lasciare applicato il 1.
- Registro GPU/VRAM: `20261006_due_schede\gpu_logger.py`.

## 7. Prossimi passi

1. Owner: script attività Afterburner + aprire OktoCGControl; poi B-A-B con OktoCGControl acceso: upsync+nucleo RAM+catena
   fusa contro Daily; poi overclock memoria a passi (3060 +500/+1000/+1250, 2080 Ti +250/+500/+1000).
2. Catena: attenzione fusa rifatta da Fable (obiettivo < 150 µs), separare MASK 62 e SHARED_BRANCH.
3. PLE: `--ple-row-cache 67108864` (~5,6 GB) e tabella da `C:` (NVMe); rimettere la riga diagnostica PLE.
4. IQ2_XS su tutto il modello (shard 1 in `D:\ds4_work\strata\Strata-data\gguf\`): velocità e qualità.
5. Gateway: richieste laterali (vedi §2).
6. Multi-chat: base 0.1.42 ha `--batch-groups auto` e cache adattiva in batch; rifare le prove con nucleo RAM e NVML.
