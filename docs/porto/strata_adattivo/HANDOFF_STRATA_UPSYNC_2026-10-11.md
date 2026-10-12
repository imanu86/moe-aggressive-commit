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

## 8. Notte 11-12/10 (OktoCGControl acceso, B-A-B sul banco forzato 131k)

| Leva | Esito |
|---|---|
| fusioni catena MTP (`STRATA_CHAIN_FUSE2`, mask 62) da sole | +0,4% (rumore); attenzione fusa rifatta da Fable: pari all'originale, non serve |
| `STRATA_MTP_SHARED_BRANCH=0` | **+1,3%** (tenuto) |
| `STRATA_SIDE_MIXER=2` (port #1889) | **+0,9%** (tenuto) |
| MMVQ_IL upstream / tabella sm_75 (#1437) | −3,0% / 0,0%: resta B6 |
| PLE su NVMe `C:` (sulla base upsync) | +3,9% decode, prefill 260→100 s, MA era la regressione sotto (sul Daily: −0,1%) |
| cache righe PLE 64M | +0,5% (rumore) |
| `STRATA_ROUTE_RESIDENT=1` | −1,6% |
| `STRATA_LOOKAHEAD=0` / `STRATA_LFUSE=1` | −0,3 / +0,3 |
| taglia finestre di Fable (`STRATA_DW=1`, lab/draftwin) | −1,5% |
| attenzione QSA multi-riga (ipotesi) | **falsa**: l'attenzione è ~8% del costo per riga (lab/qsarows, `qsa_rows_bench`) |

**Regressione trovata e corretta:** v0.1.42 misura il PLE all'avvio e sotto 15.000 righe/s (SATA a freddo: 1.259) passa da sola
a mmap → prefill 131k 260 s e decode più lento. `lab/ports1` `aaf2e069`: PLE sempre diretto (`STRATA_PLE_AUTO_MMAP=1` per il
vecchio comportamento), più le patch di prefill del Daily (SELECT_SIMT, dequant 16 B, hc16 sm_75) e la diagnostica PLE.
Risultato: **base pari al Daily: decode +0,6%, prefill 75,4 contro 74,9 s, PLE sul SATA come il Daily.**

Costo vero di una riga in più nella finestra (Fable): 5,7 ms nelle fresche, 3,7 nelle speculative (~2,5-3 ms per stadio).
Attenzione QSA 0,2-0,35 ms; il resto: esperti (+~9 per riga e layer, più quelli su CPU), GDN ricorrente, hc, host.
Nsys per T in corso (Fable, `lab/qsarows`).

Multi-chat su v0.1.42 (`--batch 3`, gruppi automatici; con/senza `--batch-mtp`; un gruppo): 38-53 t/s aggregati; con `--batch`
anche la chat singola scende a 47-49 (niente pipeline). Stesso nodo: costo degli esperti per riga.

## 9. Candidato Daily

`lab/candidate` 5dea5258 = ports1 + nucleo RAM. Build `build-candidate-5dea5258` (con `strata-vision.exe`, `source\serve`,
`source\tools`). Config `D:\ds4_work\strata\Strata\strata-candidate.json`, bat `Desktop\SERVER IA LOCALE\Strata CANDIDATE - porta 8100.bat`.
Provato all'avvio con immagini (OpenAI e Anthropic) e testo: ok. Nucleo: working set 48,7 → 33,6 GB, privata 77,5 → 67,3 GiB,
riletti 0, fuori posto 0. Velocità pari al Daily (misura sulla base ports1 + leve, OktoCGControl acceso). Il Daily non è toccato.

## 10. Fine notte 12/10: mappa del costo per riga e punteggi QSA multi-riga

Nsys per T (Fable, `lab/qsarows` `docs/QSAROWS.md` §3, L02 131k, ms per riga in più):

| Famiglia | 3060 (stadio 0) | 2080 Ti (stadio 1) |
|---|---|---|
| esperti VRAM | +1,04 | +1,31 |
| MMVQ densi (B6) | +0,59 | +0,63 |
| hyper-connection | +0,41 | +0,48 |
| attese host | ~0 (2 ms fissi) | +0,36 |
| QSA | +0,24 | +0,30 |
| GDN | +0,05 | +0,09 |
| totale | +2,45 | +3,26 (più 3,5 ms fissi di buchi fra 1397 nodi) |

`STRATA_QSA_ROWS=1` (punteggi QSA multi-riga, bit per bit, `build-qsarows-4d8ba8bb`): B-A-B +3,2% poi +0,1% → circa +1-1,5%,
sicuro: da portare nel candidato. In corso: Fable su `lab/expertdec` (esperti a più righe, `STRATA_EXPDEC=1`, bit per bit,
obiettivo pendenza per riga dimezzata) — è la leva principale per 80 t/s e per il multi-chat.

## 11. Mattina 12/10: Strata 0.1.42 Daily, esperti, tempi morti, TTFT, multi-chat, MTP

**Strata 0.1.42 Daily** (nome dato dall'owner al candidato): `D:\ds4_work\strata\Strata\build-0142-daily\` (copia di
`build-candidate-5dea5258` + `VERSIONE.txt`), config `strata-0142-daily.json`, bat `Desktop\SERVER IA LOCALE\Strata 0.1.42 Daily -
porta 8100.bat`. Env in più rispetto al candidato: `STRATA_MTP_SHARED_BRANCH=0`, `STRATA_SIDE_MIXER=2`; PLE da `C:` (NVMe);
visione su CPU a 1024 token. Il Daily vecchio (`build-be4cf1c-daily`) resta intatto. I launcher di prova sono in
`D:\ds4_work\strata\ripristini\20261012_launcher_prova\`.

**Esperti a più righe** (Fable, `lab/expertdec`, `docs/EXPERTDEC.md`): `STRATA_EXPDEC=1`, bit per bit, gate/up −11/−23% per T 1-4
nel motore (nsys); down Q2_0 più lento nel motore → dietro `STRATA_EXPDEC_DOWN=1`. B-A-B `DET-x3-expdec` (build
`build-expertdec-52a74f6a`): **+1,1%** (B +0,0/+2,1) → da portare nel prossimo Daily. Vale poco perché gli esperti VRAM sono
il 15-20% del muro dello stadio 1. Un primo B-A-B (`DET-x1`) è stato falsato da un training CPU in parallelo: tutto ciò che
pesa su CPU passa da `bench.lock`.

**Tempi morti della finestra** (Fable, `lab/hostgap`, `docs/HOSTGAP.md`): ~6 ms di host fra finestre = lancio del grafo dei
1397 nodi dello stadio 1 (la GPU resta ferma finché l'API non ritorna) + polling di fine stadio 0. `STRATA_HG_PRELAUNCH=2`
(grafo dello stadio 1 lanciato su `std::async` e in attesa di una parola mappata): nsys −3,2%, B-A-B `DET-x5-hostgap`
−6,4/+0,1 (B1 outlier PLE dall'SSD) → **neutro, chiuso**. Lezione: nsys gonfia 2-3× i costi host; per l'host fa fede
`strata decode timing`. I buchi veri fra i nodi sono 1,3-1,8 ms/finestra (solo fusioni).

**Crash all'avvio** (~1 su 8): `nvcuda64.dll` 32.0.15.9621 +0x46c025, `0xC0000409` (stack cookie) durante `Prefill::init`,
dopo «prompt path borrows»; visto su 5 build compreso il Daily be4cf1c. Non è EXPDEC. Harness: `run_long.py`/`run_nsys.py`
ritentano l'avvio una volta e registrano `start_failures` (commit `9707e10`). Dump in `%LOCALAPPDATA%\CrashDumps`.

**TTFT** (agente, `lab/ttft`, `docs/TTFT.md`, build `build-ttft-48ce5f27`, non provato): salvataggio del prefisso su thread
(default), un file per prefisso `STRATA_PREFIX_DISK_MULTI=<GiB>` (Claude Code da ~42 s a 16-20 s quando DSH ha sovrascritto il
file unico), righe PLE in anticipo (default). Da misurare con un B-A-B di TTFT.

**Multi-chat 4-6** (`build-candidate-5dea5258`, `--batch 6`): massimo 45,6 t/s aggregati (4 chat stesso prompt, batch-mtp,
un gruppo); con prompt diversi 5-15 t/s (il prefill blocca il decode). Servono: pipeline anche in batch, prefill a pezzi
alternato al decode, esperti caldi in VRAM per finestre larghe.

**MTP** (`docs/porto/strata_adattivo/mtp_distill/`, fork `lab/mtp-capture`): corpus bonificato pronto (2 354 conversazioni,
3,5M token, 81 744 bonifiche, solo conteggi), export identico byte per byte, selftest CPU verde (`53994f4`). Analisi
indipendente di Fable: cattura dal prefill (non a finestre da 8), top-k su GPU, test di parità PyTorch↔motore, diagnosi
del costo degli esperti Q2_0, pod **A100 80 GB** (~1,6 $/h, 4-6 $ in tutto) invece di H100; pilota con cancello
(+2 punti di accettazione al passo 0). In attesa dell'owner: via al passo 0 locale, ricarica RunPod (saldo 0), temperatura
delle richieste di Claude Code/DSH.
