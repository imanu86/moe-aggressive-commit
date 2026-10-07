# Handoff Strata due schede — 7 ottobre 2026

Per chi riprende (altra IA o owner). Obiettivi dell'owner:
- **chat singola: 80 t/s di decode a 131k** di contesto;
- **multi-chat: ~120 t/s aggregati** (1,5 × 80) con batch + MTP + pipeline insieme;
- **≥ 10 GB di RAM in meno** (il PC non è un server dedicato).

Stato in una riga: Daily aggiornato alle due schede (83,7 t/s reali a 40-71k su un caso SWE), a 131k siamo a ~71,8/65 t/s
(L01/L02), multi-chat con pipeline compilato ma non ancora provato.

## 1. Repo, worktree, cartelle

| Cosa | Dove |
|---|---|
| Fork del motore (GitHub) | https://github.com/imanu86/Strata-2080Ti — locale `C:\Users\imanu\source\repos\Strata-2080Ti-core` (branch `main`, head `ca43719`) |
| Upstream | https://github.com/Niko1221/Strata (remote `upstream`); main upstream fermo a `82f46a8` = nostra base |
| Worktree di laboratorio | `C:\Users\imanu\source\repos\Strata-wt\<nome>` (vedi §5) |
| Repo di laboratorio (questo) | `C:\Users\imanu\source\repos\moe-aggressive-commit` (branch `research/ds4-iq1-subbit-tier-planner`) |
| Banco e script | `docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\` |
| Build in scena (exe + build.json con sha) | `docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-*` |
| Corse (log, jsonl, ambiente.json) | `...\20261004_routed_keep\DET-*` |
| Lock del laboratorio | `D:\ds4_work\strata\lab_locks\` (`bench.lock` esclusivo per corsa, `build.lock`, `pause`, `closed`) |
| Daily | `D:\ds4_work\strata\Strata\` (exe, JSON, `.venv`), dati `D:\ds4_work\strata\Strata-data\` |
| Modello | shard 1 `C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf`, shard 2 (PLE) su `D:\ds4_work\strata\Strata-data\gguf\` |
| Banco SWE via Claude Code | `docs\porto\strata_adattivo\banco_swe\` (`banco_cc.py`, `cc_caso.sh`), casi in `D:\ds4_work\swe_casa\` |
| Gateway Haiku → Strata | `docs\porto\qwen_gateway\` (porta 8787, log `D:\ds4_work\qwen_gateway_run\log_gateway\`) |
| Memoria di progetto | `C:\Users\imanu\.claude\projects\C--Users-imanu-source-repos-MultiPhoneControls\memory\project_strata_dual_gpu_obiettivo_80.md` |

Hardware: RTX 3060 12 GB su Oculink x4 (pilota il monitor 8K) = **stadio 0** (layer 0-15); RTX 2080 Ti 22 GB su x16 =
**stadio 1** (layer 16-47 + head + MTP). `CUDA_VISIBLE_DEVICES=1,0`. Ryzen 5800X, 96 GB RAM, Windows 11/WDDM.

## 2. Daily (fatto oggi)

- Bat: `C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat` → avvia
  `D:\ds4_work\strata\Strata\build-be4cf1c-daily\source\serve\server.py` con `strata-dueschede.json`.
- Exe: `build-be4cf1c-daily\strata.exe` (= fork main `be4cf1c`, sha `eccd5db3…`), sorgenti `serve` e `tools` copiati dal
  fork. Opzioni in più: `--layer-split 16 --trim-stage-weights --pipeline-windows 2 --vram-reserve-later-mib 384
  --host-core last`, env `CUDA_VISIBLE_DEVICES=1,0`, `STRATA_POOL_SPIN_US=100`, prefisso su disco nuovo
  `D:\ds4_work\strata\sota\prompt-prefix-dueschede-v1.bin`.
- Avvio verificato (health ok, split e host-core attivi). **Ripristino**: `D:\ds4_work\strata\ripristini\20261007_daily_dueschede\`
  (bat e JSON del 5/10, una scheda).
- Prova reale: SWE `django__django-14434` via sotto-agente Haiku di Claude Code (gateway → 8100): **risolto** (f2p 1/1,
  nessun p2p rotto), 5,1 min, 26 richieste locali, **decode medio 83,7 t/s** (71-105) a 40-71k, riuso 96,1%,
  primo prompt 40k in 41,8 s. Una scheda il 6/10: 45,4 t/s. Run: `D:\ds4_work\swe_casa\runs_cc\cc-split-0710b\`.
- Nota: il `claude -p` della shell degli agenti non è loggato; i casi SWE si lanciano con un sotto-agente **Haiku** di
  Claude Code desktop (il gateway lo instrada a Strata) oppure da un terminale loggato con `cc_caso.sh`.

## 3. Come si misura (regole dell'owner)

- Banco deterministico: testo e finestre forzati (`STRATA_FORCE_IDS`, `STRATA_FORCE_WINDOWS`, trace
  `20261006_due_schede\force_ids\ref_def1_trace.txt`), L01/L02 a 131k. Script: `det_force.sh` (un processo per braccio,
  usa `run_long.py`) + `bab_verdict.py`. Leve di processo: **solo B A B**.
- Leve a caldo (build con `fp_lab.hpp`, chiave `lab=` / campo `strata_lab`): `hot_ab.py` (A e B alternati nello stesso
  processo, **giri pari**: c'è un effetto posizione ~2%), verdetto `verdetto_hot.py` (scarto richieste disturbate,
  effetto posizione tolto). `--switch` alterna i casi senza riscaldamento; `--ctx2` usa un secondo contesto 131k.
- Campionato (temperatura): `samp_ab.py` (20 richieste per processo, stessi semi, accettazione bozze).
- Multi-chat: `multi_chat_mc.py` (scenari serial/same2/same3/diff2/diff3, TTFT, controllo testi).
- Base attuale a 131k: **~71,8 / 65,1 t/s** (L01/L02) con `--host-core last` e cache calda; ~68,5/63 al primo giro di un processo.
- Rumore: con `--host-core first` ~1 richiesta su 6 lenta (worker CPU interrotti); con `last` zero su 72. Sempre `last`.
- Mai: compilare durante una corsa, alzare la priorità di strata.exe, `find`/grep su dischi interi durante le corse,
  screencap/Jump sulla 2080 Ti. Lock: `bench.lock` per ogni uso GPU, `build_lock.py` per ogni build (-j6, priorità bassa).
- Dopo TaskStop su Windows verificare e uccidere a mano i figli (strata.exe, python, timeout).

## 4. Risultati del 7/10 (verdetti)

| Leva | Esito |
|---|---|
| `--host-core last` | **tenuta** (zero richieste lente, costo zero) — nel Daily |
| Priorità minima catena MTP (`MTP_PRIORITY:-1` e `STRATA_MTP_PRIORITY=0`) | no (≈0) |
| `EARLY_L1` | rumore (~+0,5%); l'analisi del percorso critico stima 0,45 ms: rifare con molti giri |
| `CHAIN_TRIM` | **crolla** (−14/−36% a strappi): difetto da capire |
| `EL_ASYNC`, `HC_FUSE_NORM`, `SHEXP_FUSE` | no |
| `DEVPLAN` | peggiora −6% (il percorso critico dice che il principio è giusto: capire perché) |
| `EXPERT_V:4` (kernel persistente) | peggiora −3/4% (più lento a T≥2) |
| `EXPERT_V:1` (codebook IQ3_S in shared) | **~+1%**, bit per bit → candidata da accendere |
| Gruppo leve neutre insieme | nel rumore |
| `STRATA_IQ_STAGE_GRID=0` | no |
| Seme cache esperti dalla prefill (v1 e v2, anche 2 contesti) | no: la massa del contesto non è quella del decode |
| Kernel esperti T=1 riorganizzato (`DEF_TILES_T1`) | 1,3-1,4× nel micro-bench, **zero nel decode** (scatta 31.500 volte) |

**Lezione chiave:** il tempo dei kernel ≠ percorso critico. La tabella «ms recuperabili per efficienza» sommava kernel.

### Percorso critico a 131k (agente nsys, file in scratchpad `cp_*`, corse `DET-cp-*`)
Finestra = catena seriale. Fresche 73%: catena MTP (1,24) + stadio 0 3060 (6,88 pesato) + passaggio (0,63) + stadio 1
2080 Ti (16,77). Speculative 27%: solo stadio 1, allungato 2,5-3,6 ms dalla catena MTP sulla stessa scheda. Dentro gli
stadi i kernel sono ~80-88% del tempo, attesa flag host 11-22%, buchi del grafo ~6% (~1,1 ms).
**Dove togliere ms (stima 3-3,5 ms → ~78-80 t/s):**
1. attese dell'host per layer sullo stadio 1 (il thread serve anche la B speculativa): ~1-1,5 ms;
2. catena MTP: passo da 0,93 ms (54 kernel piccoli) → fondere, accodare round+primo passo al grafo dello stadio 1: ~1 ms;
3. stadio 1 lanciato dopo la B speculativa: invertire o `EARLY_L1`: ~0,45 ms;
4. grafo stadio 1 da 1397 nodi, buchi ~1,1 ms: fusioni: ~0,5 ms.
Difetti trovati: **strata.exe crasha sotto nsys** (access violation ~finestra 323); **`STRATA_VERIFY_PROFILE=1` blocca il
decode a due finestre** (dump `D:\ds4_work\strata\Strata\strata-stall-7440.dmp`).

### 131k più lento che 40-70k
A 131k ogni richiesta legge **~20 GiB di K/V dalla RAM** (1,7% di miss su 293M letture, ~1,3 GB/s sul PCIe);
a 40-70k 99,7% hit. K/V in VRAM oggi solo ~130 MB (`--kv-resident 32768`).

## 5. Branch e lavori aperti (tutti sul fork, worktree in `Strata-wt\`)

| Branch | Worktree | Stato | Prossimo passo |
|---|---|---|---|
| `lab/multichat-mtp` (`be4f623`) | `Strata-wt\multichat-mtp` | **compilato** (build `build-mc-be4f623`), mai provato | prova `multi_chat_mc.py --scen serial,same2` con `--batch 3 --batch-mtp --conversation-cache-mib 16384 --conversation-cache-slots 4 --host-core last`, env `STRATA_BATCH_PIPELINE=2 STRATA_BATCH_MTP_SPLIT=1`; poi same3/diff2; esattezza con `tools/batch_test.py`. Obiettivo 120 t/s aggregati. Doc: `docs/BATCH_PIPELINE.md`, `docs/MULTICHAT_MTP.md` |
| `lab/ram-dedup` (`258e5ff`) | `Strata-wt\ramdedup` | scritto, **mai compilato** | build, `STRATA_RAM_DEDUP=1`: atteso −13 GiB RAM; verificare `riletti da file 0`, testo identico, t/s pari; riga `strata ram:` per la ripartizione della RAM privata (79,5 GB privati vs 49,6 working set: ~30 GB probabilmente commit WDDM della VRAM). Doc `docs/RAM_DEDUP.md` |
| `lab/gumbel` (`59ae43d`) | `Strata-wt\gumbel` | **compilato** (`build-gumbel-59ae43d`) | `samp_ab.py` B A B a T=1,0 e 0,7: B = `STRATA_SPEC_COUPLED=1 STRATA_SPEC_GUMBEL=1` (oggi COUPLED spegne la pipeline!) vs A base con pipeline. Owner: tenerlo acceso se aiuta con temperatura (uso reale via harness). Se l'accettazione sale ma la pipeline persa costa di più → far girare COUPLED in pipeline. Doc `docs/GUMBEL.md` |
| `lab/expert-persist` (`954f24c`) | `Strata-wt\fable` | compilato (`build-persist-954f24c`) | contiene leve a caldo + `EXPERT_V:1` (+1%) e `DEF_TILES_T1` (zero). Valutare di portare `EXPERT_V:1` in main |
| `lab/fable-plan` (`93be6e0`) | (stesso worktree, prima del checkout) | provato | leve 1-6 di Fable bocciate; tenere `fp_lab.hpp`/`hot_ab` come infrastruttura |
| `lab/prefill-seed` (`7e6b9f7`) | `Strata-wt\seed` | provato, no | archiviato |
| `lab/multichat` | `Strata-wt\multichat` | base del multichat-mtp | — |
| `pr/split-prompt-borrow`, `pr/b6-mmvq-rows`, `pr/forced-bench` | `Strata-wt\pr-*` | branch pronti, **build e PR non ancora fatti** (corpi in scratchpad `prwork\body_pr*.md`) | owner ha approvato 1, 2, 3: compilare con `build_lock.py` e aprire con `gh pr create -R Niko1221/Strata --head imanu86:pr/<nome>`. PR1 su upstream è solo coerenza (dirlo / eventualmente saltarlo) |

PR upstream: #1110 chiuso oggi in favore di #1329. Aperto: #1117 (elastica). Commit su lab/expert-persist `1ba59de`/`a173807`
hanno il titolo sbagliato (collisione file messaggi): non riscritti (niente force-push).

## 6. Da testare / su cui lavorare, in ordine

1. **Multi-chat batch+MTP+pipeline** (build pronta) → 120 t/s aggregati.
2. **`--kv-resident` 65536 / 131072** B A B a 131k (atteso: meno dei 20 GiB/richiesta dalla RAM; costo 130-390 MB VRAM).
3. **Percorso critico, punti 1-4 di §4** (codice: thread host dello stadio 1 prima di B, catena MTP fusa in coda allo
   stadio 1, ordine di lancio, fusioni nel grafo). È la strada stimata per gli 80 t/s a 131k.
4. **RAM dedup** (−13 GiB).
5. **Gumbel** a temperatura.
6. **PR 1-3** upstream (build + apertura).
7. Accendere `EXPERT_V:1` nel Daily dopo un B A B di conferma.
8. Difetti: crash sotto nsys; blocco con `STRATA_VERIFY_PROFILE`; `CHAIN_TRIM` a strappi; perché `DEVPLAN` peggiora.
9. In coda (priorità bassa): maschera dinamica di neuroni negli esperti (stile TEAL; la statica è già bocciata);
   hc in int8 (upstream #1262, non bit per bit: decisione dell'owner); upstream #1316 (re-probe della policy bozze) se
   nell'uso reale i token/finestra calano col tempo.

## 7. Decisioni dell'owner da rispettare

Linux escluso; 8K e Oculink restano; niente due copie del modello (data parallel scartato); le release dell'app le fa
l'owner; mai alzare la priorità di strata.exe; niente agenti Haiku per lavoro (il gateway li manda a Strata: solo per
test voluti); impostazioni di sistema le cambia l'owner; segreti mai in git né in chat.

## 8. Aggiornamento sera 7/10: multi-chat provato (build-mc-be4f623)

Funziona (nessun blocco, testi sani, la pipeline a due gruppi si accende), ma **non scala**:
- 1 chat: 64-71 t/s. 2 chat, 1 bozza per chat: 36 + 40 t/s per chat, 59 t/s aggregati dai client (motore 86 righe/s);
  stadio 1 (2080 Ti) occupato **96%**, 18,9 ms per finestra di gruppo con 2 righe; bozze accettate 68%.
- `STRATA_BATCH_MTP_DRAFTS=3`: peggio (2 chat 44,5, 3 chat 52,5 t/s aggregati): ogni riga in più costa ~6-10 ms sullo
  stadio 1, perché righe di conversazioni diverse chiamano esperti diversi (traffico esperti ~lineare nelle righe):
  su MoE 512×top-10 il batch non ammortizza i pesi come su un modello denso.
- Conclusione provvisoria: a 131k il collo è la banda della 2080 Ti per gli esperti; 120 t/s aggregati non arrivano dal
  batch così com'è. Da capire: quota di esperti condivisi fra slot, batch a 1 bozza con 3 chat, raggruppare slot con
  routing simile. Log: `20261006_due_schede\mc_pb2-1`, `mc_pb2-2`.
