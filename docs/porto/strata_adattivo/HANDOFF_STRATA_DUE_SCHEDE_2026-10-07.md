# Handoff Strata due schede — 7 ottobre 2026

> **Aggiornamento successivo della sessione gpt-6-astra/DSH: vedere §9.** Tutte le nuove prove, i fallimenti e i limiti sono registrati lì. Obiettivo successivo >90 t/s a131k NON raggiunto; nessuna modifica promossa al Daily. L'owner ha ordinato di fermare il lavoro: non riprendere automaticamente esperimenti o monitoraggio. Le sezioni1–8 restano il resoconto storico originale.

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

## 9. Sessione successiva gpt-6-astra / DSH — tutte le prove del 7/10/2026 e STOP

### 9.1 Conclusione e disposizione dell'owner

**Obiettivo successivamente richiesto: >90 t/s a circa130k reali, stessi prompt e condizioni Claude, in laboratorio separato. NON raggiunto. Nessuna candidata promossa al Daily.** Ultimo tripletto completo circa70–71/64–65t/s con trattamento; il riferimento A L02 è anomalo. Il −4,421% nominale del tempo non è un beneficio causale dimostrato.

L'owner ha richiesto prima analisi invece di altre microprove, poi10minuti, infine **STOP immediato e sola integrazione di questo documento**. Tutte le build/prove erano già terminate. Timer `pwsh-50` e `pwsh-52` cancellati, `pwsh-51` concluso; inventario finale senza job in esecuzione, agenti non più al lavoro. Ultimo `get_goal`: `goal:null`. **Non riprendere automaticamente esperimenti, agenti o controlli periodici.** Serve una nuova richiesta dell'owner.

Errore di metodo: sono state provate leve locali prima di ottenere un'attribuzione affidabile del percorso critico corrente. Ridurre istruzioni o tempo host sovrapposto non bastava a giustificare una strada per90. Il registro seguente serve a non ripetere gli stessi tentativi.

### 9.2 Laboratorio, sorgenti, protocollo e protezioni

Radice indicata sotto come **L**: `C:\Users\imanu\source\repos\Strata-lab-90tps-130k`.

- `L\src`: export senza `.git`, NON branch/worktree/clone. Base `ca4371964a2d0205de37d133fbb19edd1a84f8ee`; tarSHA `0822b1d80537423afadd815291df92998116e0ebee442b6f1bc0ae4028539bae6`.
- Tutti20tentativi motore sotto `L\runs\<nome>` conservano `plan.json`; misure/log/isolamento nelle stesse directory, verdetti/audit in `L\reports`, driver in `L\bench`, binari in `L\build`. Fallimenti non cancellati.
- Main originale `Strata-2080Ti-core` verificato pulito prima delle build; nessun branch/checkout/commit/push. Questo handoff è nel preesistente branch `research/ds4-iq1-subbit-tier-planner` di `moe-aggressive-commit`, lasciato invariato; modifiche e file altrui preservati.
- Daily protetto per hash su6file e metadati cache, non aggiornato né usato come cache del banco. CGControl lasciato acceso, nessuna modifica ad app/telefoni/HAGS/clock/8K/Oculink. Jump scollegato per dichiarazione owner, non verifica tecnica.
- Lock condivisi originali; `closed` e pause/lock utente preservati. Nessuna build contemporanea a benchmark, nessuna priorità innalzata, nessun kill generalizzato.
- `L\STATUS.md` e report/cursori intermedi possono ancora indicare lavoro in corso: **questo§9 prevale per risultato finale eSTOP**. Non riarmare timer leggendo quei documenti.

Banco: adattatore dell'originale `run_long.py.main()`, P0 L01→L02, USER(prefisso), ASSISTANT`pronto`, USER(caso). Prompt effettivi **131248/131239**,1024token,temp0,seed73. L01 prefill completo, L02 riuso131072. Prefill escluso dal decode t/s.

Configurazione invariata: pack/modello/MTP originali, spec4,min-p0.5,KVint8,resident32768,maxcontext262144,layer-split16,trim-stage-weights,pipeline2,reserve-first1393MiB/later384MiB,elastic,host-core last. G1 significa finestra senza `--spec-split`, non assenza dello split fraGPU. CUDA0=3060,CUDA1=2080Ti22GB+head/MTP. Codice `generate.cpp:3978–3985` conferma MTP sull'ultimo stage.

Env congelati: POOL_SPIN_US100,PARALLEL_INTERMEDIATE_QUANT0,PREFILL_EXACT_SMALL1,QSA_PREFILL_MULTI1,IQ_MT_MIN1,NO_LARGEPAGES1,ARENA_PIN_GIB8,DECODE_TIMING1 (prefissoSTRATA_). `bench/protocol.json` fissa90helper/fixture/tokenizer; SHA `a2be7ded759e43dd39c8fab4dd3dd1d5b1c2d082e15d55043c134e1148cde145`.

Forzato:521/600finestre,503/690 e426/614bozze; traceSHA `000af0df02e3b3d325f9614ffd75ec82aa7213e82220fcb55e58f97881c7791d`, identica Claude. **IDs/trace sono controllo del carico, NON correttezza libera né identiche allocazioni/speculazioni scartate.** Verdetto in riduzione del tempo, non aumento t/s.

Wrapper inizialeSHA `80f5137f93395661bb799f19a87d016fd40bfc7e806b57731134a30f1481ef87`; successivo `46615ad4be4dc5cb0d27405fe38a9b51b679c60e344d3d1abd21fe7cc574b0c0`, entrambi archiviati in `bench/versions`. Il secondo aggiunge sorveglianza compiler nominale1s e pre/postcheck: osservazione/errore invalida, nessun processo utente fermato. Non prova assenza di compilatori brevissimi. Possibile build altrui segnalata dall'owner, non dimostrata retroattivamente.

### 9.3 Tutti i tentativi motore:19 completati,1 fallito prima del decode

Ogni completato comprende L01/L02: **38misure**, più il tentativo fallito. Numeri t/s arrotondati; file originali con precisione completa. B1–A–B2 è l'ordine. Non mescolare LIBERO e forzato.

| Directory sotto `L\runs` | Tipo | L01 t/s | L02 t/s | Esito |
|---|---|---:|---:|---|
| `DET-reference-01` | riferimento |—|—|errore adattatore prima del decode |
| `DET-reference-02` | storico forzato be4cf1c |70.589046|63.774001|baseline riprodotta |
| `DET-candidate-off-01` | candidata059 OFF |69.330192|64.904197|nessun salto rispetto storico |
| `DET-mtp-tail-v1-B1` | tailgraphON |69.931980|64.413454|tripletto non convincente |
| `DET-mtp-tail-v1-A` | tailgraphOFF |70.073632|63.885007|riferimento |
| `DET-mtp-tail-v1-B2` | tailgraphON |66.731834|63.586687|nessun beneficio ripetibile |
| `DET-host-diag-01` | sola diagnostica host |69.61|63.70|non BAB di overhead |
| `DET-host-peek-v1-B1` | hostpeekON |70.442398|64.449130|nessun beneficio confermato |
| `DET-host-peek-v1-A` | hostpeekOFF |70.389134|64.884045|riferimento |
| `DET-host-peek-v1-B2` | hostpeekON |66.416308|63.859907|cache3914vs4434 confondente |
| `DET-free-reference-01` | storico LIBERO |70.140349|60.926632|non full-answer quality |
| `DET-mtp-window64-free-v1-B1` | MTP64k LIBERO |68.397077|56.528988|confronto confondente |
| `DET-mtp-window64-free-v1-A` | MTP32k LIBERO |49.366051|59.507206|outlier L01/PLE |
| `DET-mtp-window64-free-v1-B2` | MTP64k LIBERO |64.264690|57.718106|cacheB3974vs4508 |
| `DET-mtp-window64-free-v2-B1` | MTP64k LIBERO |71.259073|58.421812|nuovo monitor compiler |
| `DET-mtp-window64-free-v2-A` | MTP32k LIBERO |71.723249|59.702885|riferimento |
| `DET-mtp-window64-free-v2-B2` | MTP64k LIBERO |68.296262|59.723429|nessun vantaggio ripetibile |
| `DET-epilogue-v1-B1` | epiloghiON forzato |70.291531|63.995200|beneficio causale non provato |
| `DET-epilogue-v1-A` | epiloghiOFF forzato |70.219229|59.703581|A L02 anomalo |
| `DET-epilogue-v1-B2` | epiloghiON forzato |71.431561|64.982866|nominale−4.421%medio tempo, confondente |

**Tailgraph** (`STRATA_MTP_CHAIN_TAIL_GRAPH=1`): stessa catena/lavoro, non CHAIN_TRIM. Nessun beneficio ripetibile; defaultOFF. `reports/MTP_CHAIN.md`.

**Hostdiag** (`STRATA_HOST_PIPELINE_STATS=1`): L02 A1service10.325ms/window,dispatch1.078(poolrun0.946); B mentreA1 attiva service1.375/run0.499;13.48milioni chiamateservice. Prevalentemente polling sovrapposto allaGPU: service−dispatch NON eliminabile. Non dimostrata readinessA1 duranteB. `HOST_PIPELINE.md`, `DET-host-diag-01-summary.json`.

**Hostpeek** (`STRATA_VERIFY_HOST_PEEK=1`): evitare switchCUDA quando doorbellnonpronta, mantenendo readiness/heartbeat/watchdog. B2cachediversa; defaultOFF. `HOST_PEEK.md`, `NEXT_HOST_HYPOTHESIS.md`.

**MTP64** (`STRATA_MTP_WINDOW_64K=1`): finestra DRAFTER32768→65536 prima di allocazioni/fingerprint. **NON è il test `--kv-resident65536/131072` della§6**: KVtargetresta32768. V1 A L01: PLEblocked≈+5873ms,1036letture>100ms. Causa buildesterna non dimostrata. V2 rifatto con nuovo wrapper: Bcache4434/9128 entrambe,A4434/9151; MTP883vs837MiB costo intenzionale. ElasticB1/A3+2shrink,B2zero. FinestreB1/A/B2 L01/L02=474/631,480/635,509/620; bozze rispettivamente550/749 e394/599,544/757 e389/610,515/736 e405/599. IDs B1/B2 divergono dopo139/22token. Exit1 dei runnerliberi = guardia parità dopo tutti3bracci, NON crash. Niente speedup esatto o qualitypass;1024token spesso ancora nel ragionamento. `MTP_WINDOW64.md`, `FREE_REFERENCE.md`, `MTP_QUALITY_NEXT.md`, `DET-mtp-window64-free-v2-free-summary.json` e cacheaudit.

### 9.4 Build e modifiche prodotte, solo nel laboratorio

4build motore Release riuscite: CUDA12.6/MSVC2022/Ninja,sm75+86,6job/below-normal. Snapshot sotto `L\build` con exe/build.json/sorgenti:

| Snapshot | Aggiunta |
|---|---|
| `candidate-059137cf6317` | tailgraph + hoststats opt-in |
| `candidate-405fe1d28bfb` | hostpeek opt-in |
| `candidate-2808e4f6fa06` | MTPwindow64 opt-in |
| `candidate-72fcfe21cbb0` | epiloghiGU/DOWN opt-in |

Exe2808SHA `2808e4f6fa06831b58d5132725799d9fbf5d647a07603bff57ac79ad6de00d80`; ultimoexeSHA `72fcfe21cbb0ddaba29fcff31b9532716653cc4e0d14071f1ed21447c37c341c`. Ultima build `reports/build-20261007-190411.log`:rc0,sorgenti eDaily invariati. Incrementale `src/build-sm7586` non è una versione da promuovere automaticamente.

File motore modificati nel SOLOexport: `src/core/mtp.cpp`, `include/strata/core/mtp.hpp`, `src/program/generate.cpp`, `src/core/verify.cpp`, `src/kernels/cuda/iq_kernels.cu`. **Tutte leve defaultOFF.** Prima dell'ultima build salvate librerievecchie in `build/reference-kernel-libs-2808`: kernelsSHA `3b5a077a8d529e37311493190371c3eaf3988141c8f1f2e932c864c4edf97908`, coreSHA `86bf5371271334b514c43a8de6ad3aef683399a4635ebf12ab5d47978f5cd535`.

### 9.5 Tutte le microprove e verifiche, incluse quelle fallite

1. **Tail-event GPU** (`bench/event_probe.py`):384run perGPU PASS; controllo negativo stale rilevato. Solo eventi/dipendenze, non qualità modello o velocità.
2. **Resource/SASS405**: solaCPU. Dump inizialeUTF16 conservato e copiaUTF8. GU18sm75 REG64/STACK80,DOWN20 REG64/STACK48,DOWN42 REG61/STACK48; LDL/STL nonostanteLOCAL0. REG64 non dimostra occupancy insufficiente suTuring.
3. **Epiloghi implementati**: `STRATA_IQ_CONST_EPILOGUE=1` exact1, defaultOFF. SoloCUDA GU18/DOWN20/42,embd2560/ff640,rispettaOLD/NO_SUB16. Noveepiloghi n2/3/4 passano da `sN[t]` a loop unrolledc con `if(t==c) sN[c]`; stessi writer/indirizzo/dot/riduzioni/quant/grid; vecchioramoOFF preservato. NC=entryperesperto, NONTwindow; non MAX_NC/tiling nuovo.
4. **Primo dump72 con nomeparziale**: rc0 ma solo warning/nessunafunzione selezionata. Conservato `sass-72fcfe21-gu18-down20-down42-sm75.txt`, NONprova. Riestratto nomimangledesatti con `bench/epilogue_sass.py`; `sass-72fcfe21-exact-sm75.txt`/sm86 e `epilogue-72fcfe21-static.json`.
5. **Probe epilogue-parity-v1**: compiler non avviato, CreateProcess non trova cl.exe bare. Lockproprio trattenuto; rimosso soltanto dopo conferma mancatoavvio/PIDowner18296 assente e nonce `505a4751a2f24b818ccf031b0de24293` invariato. Nessun lockutente rimosso. Corretto MSVCassoluto/envWindows.
6. **Probe v2**: stessoCPP linkato vecchie/nuovelibrerie.3060: vecchio,nuovoOFF,nuovoON passano, negativo rilevato.2080: vecchia registra312casi, nuovaOFF diverge alcase151 GU18/D20,base7,plan12,grid1,phase2,word145920,`c0a6f518`vs`bf3f7720`. Stop prima diON2080/banco131k; logconservati.
7. **Corretto SOLO il test**: uploadpageable/memsetdefaultstream precedevano lettureNONBLOCKING senza fenceesplicite. Aggiunte fence preparazione input/piani/guardie, protocolheader2 e controllo vecchio→vecchio. Motore invariato. PASSsuccessivo compatibile col difetto deltest, non prova guastoGPU/regressioneengine; nessuna ablation completa della causalità.
8. **Probe v3 PASS entrambeGPU**: baselinevecchia, vecchia→vecchia, nuovaOFF→vecchia, nuovaON→vecchia; bitflipCPU respinto rc1+INJECTED_MISMATCH+BITWISE_MISMATCH. Ogni confrontopositivo312casi e12,441,600floatword bitwiseuint32. NC1..8/resti4,ng0/1/4/6/8,base0/7,grid1/3/>cap,destinazionipermutate,aliaspesi,scratchstale; phase0GU/UP/DOWN,phase2DOWNisolato; finitivalori,NaNinattivi,guardie256B. Graphcapture diagnosticaNONlanciata+cudaFuncGetName attesta simboli effettivi vecchi/false/true, non soltantoENV. Nessun compiler osservato, artefatti/Daily invariati, nessunprocessoproprioresiduo. `build/epilogue-parity-v3/result.json` e log. Oracle sintetico reale, non tutti pesimodello o end-to-end.
9. **CPU unit tests**:7iniziali, poi32/37/39/42 e infine **43PASS** prima della compilazioneprobev3. Sono test infrastruttura/protocollo/summary/ownership/activation, non43test modello. RegistrazionePopen→PIDbirth corretta nel nuovorunnerprobe: handlecleanup e latch/lock su spawnincerto, nientePIDguessed. Test registrazionefallita/interruzioneinPopen/lockconservato/FileNotFoundnonavvio/nooverwrite/falsaattivazione respinta. Messaggi 'retaining lock' dei test riguardano mock temporanei.

Risorse/istruzioni statiche OFF→ON (non conteggi eseguiti o risparmio):

| Arch/kernel | REG | STACK | LDL | STL |
|---|---|---|---|---|
|75 GU18|64→64|80→80|14→10|30→17|
|75 DOWN20|64→71|48→0|3→0|17→0|
|75 DOWN42|61→62|48→0|3→0|17→0|
|86 GU18|64→64|48→48|6→3|24→12|
|86 DOWN20|64→71|48→0|3→0|17→0|
|86 DOWN42|56→48|48→0|3→0|17→0|

GU conserva trafficolocale; DOWN20 può perdereoccupancy per piùregistri. Nessun guadagnomodello derivato da questa tabella. `reports/EPILOGUE_RESULT.md` dettagliaimplementazione; se riporta BAB ancora 'incorso', è superato dai risultati conclusi qui.

### 9.6 Errori dell'infrastruttura registrati

- reference01: factoryfunction doveilbanco richiede classe con `projection_key`; corretto con sottoclasseCheckedEngine. Nessun dato velocità daquel tentativo.
- TelemetrialegacysingolaGPU: `too many values to unpack`, campo conservato; aggiunta telemetriamultiGPU conUUID/VRAM/clock/temp. Nonenginecrash.
- free-summary inizialmente pretendeva Benv_probevuoto: corretto aB`[FLAG=1]`,A`[]` e testnegativo. Misure non riscritte.
- Archivio wrapperinlinePython fallito perquoting: helper dedicato ha archiviato versioneSHAesatta.
- Agente epiloghi fallito/interrotto durantepreparazione: parent ha letto/completato ilCPP e invocazione kernel-selection, poi compilato/verificato; nessun risultato presunto.
- web_search non disponibile perAPIkey: usateAPI/rawGitHub. Agente senza permesso scritturaesterna ha restituito testo, nessunaggiramento.

### 9.7 Analisi finale dei tempi e dei contatori, senza altre prove

UltimoBAB tempi L01/L02: B1 **14.5679/16.0012s**, A **14.5829/17.1514s**, B2 **14.3354/15.7580s**. Stessoexe/IDs/trace, cacheiniziale4434/9151. Riduzioninominali deltotale vsA:3.6717%/5.1707%, media4.4212%. **NONdimostrato beneficio causale.**

L02 B1/A/B2: PLEblocked dopo−prima **260.849/1166.100/293.439ms**. A ha905.251/872.661ms inpiù rispettoB1/B2; rallentamentodecode1.1502/1.3934s. Staging .493/2.006/.551ms/window, totali≈295.8/1203.6/330.6ms: quasi lo stesso fenomeno visto da contatoriannidati, NON due costi. Non sottrarli per creare velocità normalizzate; non dimostrano SSDlento.

Cache stage0 fineL01 B1/A/B2=4237/4112/4434, fineL02=4374/3901/4025. HitL02=97.6/97.2/97.5%. B1L02 cresce2volte; A/B2 restringono2volte ma da stati diversi. Stessonumeroeventi NON stessa cache; costoelastichost non comprende conseguenze sui miss/overlap.

Codice verificato:
- `verify.cpp:3222–3228` gatherPLE incrementa ms_host ed è chiamato3323 dentro timer ms_pool3272→3327: **non sommare staging eper-layerhost**.
- Pipeline non incrementa ms_ple_gather: lo0stampato è buco diagnostico, non assenzaPLE; DECODE_TIMING eraattivo.
- ms_wait3273/3328 è tempo tra servizi conGPU/altrohost inprogresso, non GPUwaitpuro. pl_launch3186–3194 non aggiorna ms_launch: zero non prova launchgratuito.
- ple_reader.cpp486–513 collect include ticket/lock/conditionwait; ancheprefetchraccoglieticket. Percentilirolling non delta deldecode, non esclusivodisco.
- expert_source.cpp2787–2817 CPUrun è wallpool, nonCPUbusyworker; generate.cpp10420–10430 mischiaambitoDriveglobale eVerifierstage0: non partizioneadditiva.

B2L02:527Btentate,163onpath,364rollback,72sottogate;437fresh a28.68ms/163spec a19.79ms. A stessi437/163 ma31.39/21.07ms: rallentamentonon solo mix. generate.cpp11145 richiede TUTTI draftAaccettati ebonusBcorretto perpromuovereB; non è tempoliberabile con un semplice riordino.

Profilo STORICO cp_clean_host/cp_nsys5_excl riletto, non nuove misure:1198finestreclean e342Nsight; stage1nativeGU+DOWN≈3.62–3.69ms,B6≈2.6–2.7,GDNup/down≈2.6,score+topk≈1.18,wait-only≈1.98fresh/4.77spec. Scriptdivide uniformemente overlap, non risolveunDAGcritico; profiler perturbante/coortiTdiverse/crashstorici. Non trasferire percentuali al banco corrente.

**Budget90:**1024/90=11.377778s. Rispetto miglioreB2 mancano **2.957622s L01 e4.380222s L02**, cioè **5.676818/7.300370ms perwindow** o **20.63%/27.80% deltempo**. Non esiste nei logcorrenti un breakdownCUDAcorrelato cheprovi dove recuperarlo. Lacuna identificata ma NONeseguita: timelineCPU/GPUperwindow/role/T/device/stream con compute/copy/MTP,readiness/servizio,PLEissue/collect,cacheeventi,unionedegliintervalli/dipendenze eoverhead vsno-profiler. Non accendere alla ciecaSTRATA_VERIFY_PROFILE (blocco storico). Nessun90garantito.

### 9.8 Upstream, messaggi Niko e fork: controlli e approfondimento

3controllipubblici:18:32, ciclo19:03 raccolto19:07–08, ciclo19:37 raccolto19:43; poi approfondimentosololettura circa19:50. NessunTelegram/DM; Discussions404iniziale e nonritentate. Nessun censimento universale, import o buildfork.

- HEADufficiale `e8ca9afd03d839d4f8dbbe82dffce7f8a3bafd7a`, [releasev0.1.40.2](https://github.com/Niko1221/Strata/releases/tag/v0.1.40.2), invariati. Branchmirati: jklnvlink235350960d853674f0279e5838a16e68e71be2bd; Eddmain d6708a4aae15b4860000d54c8af9e84d684bce09; Eddcustom3a19944130d93d204a845234bbb61c1f1fb3b57d; kervia3c10ad41fd6b8cc56cce463244f79727b35846be, invariati.
- Prima lettura100commenti/42Niko, inline42/0Niko. Incrementali successivi nessun nuovoNiko nei recordletti. Ultimociclo2commentinonstampati perUnicodeEncodeError: recuperati conJSONASCII,9record completi since17:05:25UTC,0Niko. Inline6nuoviCopilot,0Niko. Citazioni vecchie diNiko non contate come nuovimessaggi.
- Inventario100forknewest,6nuovecreazioni nel secondociclo,5nelterzo. HEAD/diff dei nuovi nonletti: non affermare assenza patch.
- [MMVQ_IL ffac97f7](https://github.com/Niko1221/Strata/commit/ffac97f74ff4b7433d7c72737164f3541c2fd2ff): novitàdenseT2–4/CC≥80/shape selezionate, alternativa aB6 che giàriusa pesi/attivazioni.3060/layer0–15 sì,2080/head/MTP no,T5fallback. Guardperdevice corretto; port/scratch/interleave eoracle2GPU necessari. +4.2%dichiaratosu3060 non misura nostra; oracleupstream non eseguito. `reports/MMVQ_IL_SCOPE.md`.
- Routedsub16/exactN/fusedSwiGLU18/20/42 giàlocali; EXPERT_V2richiedeGU21,V2K12/13, non toggleperGU18.
- [jklnvlinkdequant ea158a93](https://github.com/jklnvlink/Strata-2080ti/blob/ea158a93ed30340092f1bf4a13522231062453f5/src/kernels/cuda/dequant_bf16.cu#L163-L227) vectorstoreSM75 **giàlocalmente** dequant_bf16.cu174–198/229–243; prefill/GEMM, non nuovo guadagnodecode.
- [Eddcustomattention3a19944](https://github.com/eddoursul/Strata/blob/3a19944130d93d204a845234bbb61c1f1fb3b57d/src/kernels/cuda/qsa_decode_attn.cu#L215-L298): fixedpoint24bit,MMA/cp.async, aritmeticadiversa e non portabile talquale su75.3060ISAcompatibile non risolve2080critica; KV4bit cambierebbe protocollo. Nonimplementato.
- [PR1355](https://github.com/Niko1221/Strata/pull/1355), head71b0279a0804bc2f32807c36cf254df28b37d1fd: **solo2Markdown,+131/−1,zerokernel**. V10032GBsm70/TCC,0.1.39,moltesingle-run. Parallel4 èaggregato, non90singoloflusso. MatrixP100 poi indicataPR1411, non kernelverificato.
- [PR1367IMMA](https://github.com/Niko1221/Strata/pull/1367): prefillqsa_prompt_attn_batch, NONdecode/verify. Autore5090≈−16%kernel,≈1%wholeprompt condispersione7%; Windows4070Laptop73.605→73.352s wholeprompt sostanzialmente invariato. Non prova nostra.
- PR1324RAM/LRU:7940HS/4070Laptop,pressionegraduale/994blob restituiti dichiarati, non speedup locale. CommentiDirectStorage/ROCm/prefillV100 non cambiano verdetto.

Reportesistenti: `UPSTREAM_20261007_1832.md`, `FORKS_20261007_1832.md`, `UPSTREAM_FORKS_20261007_1903.md`. Terzociclo/approfondimento integrati qui, non reportseparato completato. Ultimaquota47/60condivisa. Futuracursor: issue17:48:34UTC, inline completo solo17:43; con cursorcomune conservare17:05:25UTC e deduplicare id+updated_at, oppure non oltre17:41:11. Il watchfile NON autorizza prosecuzione dopoSTOP.

### 9.9 Non eseguito in questa sessione

Nessuna nuova prova multichat, RAMdedup, temperaturacampionata, Gumbel, KVresidenttarget65536/131072, MTPsu3060, sparseMTP, hostdualbatch, importMMVQ_IL, portattentionEdd, PR o nuova catturaNsight. Attivitàstoriche§1–8 distinte daqueste. SparseMTP solo nota `SPARSE_MTP_SCOPE.md`: indexer4celle/128dimensioni/RoPE64,storiciKV/snapshot mancanti; non patchtiny. MTPsu3060 solo `MTP_DEVICE_HYPOTHESIS.md`.

Non dimostrato che65–71t/s sia il limitehardware; è l'esito delle prove, non un tetto. Non dimostrato un percorso per90 o qualitàcompleta a1024token. **Lavoro operativo fermo per richiestaowner. Questo registro è consegnato nel documento originale, non una proposta di continuazione automatica.**

