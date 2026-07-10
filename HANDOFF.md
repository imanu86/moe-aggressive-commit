# HANDOFF — moe-aggressive-commit

> **PUNTO D'INGRESSO UNICO.** Leggi §0-LIVE (stato più recente). Sotto: §0-STORICO e STORICO = contesto precedente.

## §0-LIVE (2026-07-10) — REAP-LOOP: il lavoro vivo è nel repo `reap-loop`; questo repo = storico + dati multiseed + cockpit

### Dove si lavora ADESSO
Dal **2026-07-07** runtime ed esperimenti vivono nel repo **`reap-loop`**
(`C:\Users\imanu\source\repos\reap-loop`, GitHub `imanu86/reap-loop`, `main` aggiornato al 2026-07-10):
- **Piano operativo corrente:** `reap-loop/docs/NEXT_STEPS_PLAN_20260710.md` (igiene → pavimento di misura n=3 + grading funzionale L0-L3 → test decisionali T1-T5 → leve L1-L7). Goal: **>3 t/s stabili sul 3060 con qualità coding/HTML ≥L2 al render**. SOTA_LOCAL_3060 oggi: static K23 3.03-3.39 t/s (degenera ~tok116) / rotate32 2.61-3.03 t/s.
- **Paper CANONICO:** `reap-loop/docs/paper/PAPER.md` (più avanti di 2 commit rispetto al draft qui). **Single source of truth dei claim:** `reap-loop/docs/CLAIMS_CURRENT.md`.

### Questo repo (moe-aggressive-commit) al 2026-07-10
- `main` @ `d021685` su GitHub PRIVATO `imanu86/moe-aggressive-commit` (include il merge K91 `f7aefc5`).
- **Verdetto K91 coding→VRAM** (`f7aefc5`): NESSUN K entra in 12GB reali E scrive ancora codice — muro netto per il dominio largo coding. Cache reale ~407 expert (non ~910: ignorava ~2GiB di arene ds4), backbone reserve misurato 5.82 GiB.
- Branch (tutti pushati su origin):
  - `cascade-memory/harness` — **paper v2 CONGELATO** (`docs/paper/PAPER_DRAFT_v2.md`, banner FROZEN: canonico in reap-loop) + **cockpit** `tools/cockpit/ds4_cockpit.html` (UI leve + telemetria live + controllo RAM WSL).
  - `reap/k91-coding-vram` @ `c8a7569` — contiene **`runs/reap/multiseed_2026-07-07/`** (N=3: ritrattazione asimmetria HOT/COLD, paired rand/reap 1.345× CI[1.27,1.42]), citato dal paper canonico; pointer in `reap-loop/runs/reap/multiseed_2026-07-07_POINTER.md`. Checkout attivo nel worktree `.claude/worktrees/elastic-bose-6ae1c7`.
  - `dspark/mtp-spec-dec` @ `082aaa3` — probe 0013: VERDETTO NO-GO (meccanismo assente nella config daily; delta dentro il rumore ±50%).
- `docs/PAPER_STATE.md` = SUPERSEDED (fotografa la vecchia tesi impact-weighted prefetch; vedi banner nel file).
- La sezione sotto (§0-STORICO 2026-07-06) resta com'era: contesto valido ma numeri/stati NON più live.

---

## §0-STORICO (2026-07-06) — ds4flash-dwarf-spex-reap_loop: 5 leve + paper

### Cos'è il progetto (in una riga)
Far girare **DeepSeek-V4-Flash 158B** (2-bit, 256 exp/layer, 6 attivi, 40 layer MoE, expert 6.75MiB) sul motore
**ds4/DwarfStar** (antirez) su **RTX 3060 12GB + 28GB RAM** (64GB in arrivo), via uno stack di leve componibili.
Utente = **imanu86** (dominio + intuizioni; io = manovale/integratore). Paper in bozza. Reviewer target: **antirez** (S. Sanfilippo).

### Repo / branch (fonte di verità = i file committati, MAI i numeri a memoria)
- `main` HEAD `dfd99fb` su GitHub PRIVATO `imanu86/moe-aggressive-commit`. Tutto mergiato qui.
- Branch paralleli (worktree in `.claude/worktrees/`): `dspark/mtp-spec-dec` (HEAD `44b24c9`), `reap/ds4-domain-prune` (HEAD `af67048`), `reap/public-domain-replica` (agente, in corso).
- **Sorgente ds4:** WSL `/root/ds4` (⚠️ distro **Ubuntu-24.04**, non `Ubuntu`), upstream `github.com/antirez/ds4` base `80ebbc3`, nostro tip `bee9eb3`. Worktree DSpark: `/root/ds4-dspark`. Le patch nostre stanno in `patches/ds4/0001..0011` (applicare in ordine 0001→0011).

### LE 5 LEVE — stato e numeri (ogni numero ha fonte nel repo)
1. **Cache expert VRAM** — MISURATA (`runs/ds4_bench_clean_ext4_20260705/`): hit 0→44% ma t/s piatto su ext4+28GB (collo = coda SSD, non copie H2D). Sweet-spot cache PICCOLA (reserve=1, ~700-880 slot). Si ACCENDE con RAM 64GB.
2. **Spec-dec a blocchi (DSpark-ispirato)** — Fase C SBLOCCATA e funzionante sul 3060 (`patches 0009+0010`, `runs/dspark/20260705_fase_c_smoke_3060/`): union-load −49%, acceptance pos2 0.848, spec2 +10% col freno tirato. Strada B (drafter ufficiale, 2×H200): τ=5.18/5.00/2.70 (`runs/dspark/20260705_dspark_b_v4flash_2xh200/RISULTATI.md`). MTP-1 baseline 0.872/0.846/0.604.
3. **REAP bias-mask** — PAPER-GRADE (`runs/reap/2026-07-05_eval_biasmask/`, verdetto v2 `e32649b`): **K50 LOSSLESS dominio** ppl 1.010× CI[0.996,1.025] (replicato cross-macchina), **K67 = 1.076× = operating-point che entra nei 28GB di oggi**, F3 generale 1.403×, random 1.388× (controllo, selezione ~5×). Dial RAM-cap: K70 prefill **+87%**, expert-load −57%. V0 attuatore 0/11280 violazioni.
4. **SPEX hidden prefetch (D2)** — MISURATO sul target (`runs/spex/fit_results.json`, paper §5.4): probe next-layer **DOMINIO 0.68@6/0.83@12/0.92@32 vs recency 0.28/0.41/0.60**; generale/coding +5-8pt; next-token più debole → design NEXT-LAYER-centric. **Export .spex FATTO** (`runs/spex/spex_model/ds4flash_d2_nextlayer.spex`, 90MB, gitignored — rigenera con `python scripts/spex_fit_predictor.py --export-spex <path> --export-only`). Loader C di riferimento: `patches/ds4/ds4_spex_predict.{c,h}`.
5. **REAP-loop + skip-on-miss** — DESIGN (task #13/#14): la bias-mask è l'ATTUATORE (hard=mai-selezionare / soft=skip-on-miss); sensore = n_eff/deriva del profilo dal router. Da valutare in sim quando arrivano le trace generali.

### Il collo strutturale del 3060 (ricorrente, 3 volte) e la sua chiave
**Conflitto VRAM: statics MTP (~3.5GB device-cachate) vs expert-cache, su 12GB non ci stanno insieme** → spec-dec e cache si escludono. **La patch 0011** (`DS4_MTP_HOST_STATICS`, statics host-side zero-copy, `44b24c9`) è IL fix — sviluppata+buildata; il suo test sotto carico è l'eval ON in corso.

### IN VOLO ADESSO (owner + risorsa, NON toccare fuori dal proprio)
- **JOB1 validazione appaiata ON/OFF** — 3060, owner **chat DSpark** (`local_3e05c04f...`): OFF completato+committato (`44b24c9`, trace in worktree dspark `runs/dspark/20260706_night_validation_m8/out/eval_off.trace`), ON in corso con binario 0011 dalle ~05:35. A fine (~pom.) → verdetto appaiato + **M8-bis** (spec2+cache CON 0011, atteso ~1.2 t/s) + **pacchetto PR 0009+0010+0011** per antirez. DSpark ha keepalive `sleep infinity` sulla distro (da uccidere a fine).
- **Replica REAP dominio pubblico (#16)** — pod, owner agente `afa597020a8de4eb6`: sceglie corpus pubblico → verifica equivalenza routing (n_eff ~40-47 come BonusX) → mask K50 → eval ppl+CI. Chiude M1 del paper (riproducibilità senza KB privata).
- **Corso cold-vs-warm** — chat-tutor separata (task_fed362be), per l'utente: armarlo a progettare la soluzione al cold-start (= futuro §6 paper).

### PAPER (`docs/paper/PAPER_DRAFT.md` + `docs/paper/GAPS_AND_FIXES.md`)
Bozza completa, tesi = "estendere gli engine di expert-offload giù per la scala di memoria: anatomia misurata + stack di leve". Panel avversariale 5-lenti incorporato (§7 Threats). **M1-M5 RISOLTI** (M1=KB proprietaria withheld+surrogato pubblico #16; M5=scope 158B-only, Qwen=preliminary; M2=sim-t/s ritirati; M3=REAP soglia FAIL onesto; M4=`scripts/paper_ci.py` bootstrap CI). D2 dentro (§5.4). **RESTA: M8-bis** (il numero che sblocca la tesi-velocità, in corso via DSpark) + camera-ready.

### PROSSIMI PASSI (in ordine)
1. [attesa] Verdetto JOB1 + M8-bis + pacchetto PR (DSpark, pomeriggio) → poi mergiare su main.
2. **Hook C del predittore SPEX**: cablare `ds4_spex_predict` all'hook `ds4.c:19415` (dopo `g->cur_hc=hidden(L)`) → top-K → `seed_experts_async` (plumbing 0002). COORDINARE con 0011 (stesso file ds4_cuda.cu). = ultimo miglio Stadio 2/3.
3. [attesa] Replica pubblica #16 → aggiorna paper §7.9.1.
4. **Test K67 bias-mask sul 3060 vero** (dominio ON vs OFF): conferma "turbo Segnali oggi su 28GB" + il `gen` del dial sulla macchina target.
5. **Pacchetto antirez** (#17): PR 0009+0010+0011 validate → poi outreach reviewer (bozza msg in italiano da scrivere con l'utente).
6. STS (Stadio 3, task #6) + camera-ready.

### LEZIONI OPERATIVE (vedi anche `docs/briefs/POD_PLAYBOOK.md` §6-7)
- **DUE distro WSL**: usa SEMPRE `wsl -d Ubuntu-24.04`, mai `wsl` nudo (l'altra è `Ubuntu`, modello via /mnt/d 9p lento).
- **Processi persistenti**: Windows-side = `Start-Process -WindowStyle Hidden`; WSL run lunghi = `systemd-run` transiente (systemd c'è su 24.04). `nohup` da Git Bash MUORE col padre.
- **NON toccare working-dir/GPU condivise senza coordinare** (cross-message): ho troncato una trace altrui rilanciando un job — salvata solo perché committata. Verifica sul box prima di dichiarare morto un run.
- **Determinismo**: greedy CUDA NON bit-riproducibile → correttezza via equivalenza statistica (ppl/CI), mai diff-token.
- **Pod**: playbook alla lettera; secure a volte non alza sshd (×3, ~$2 persi) → community/piggyback o cambia macchina; terminate+verifica `myself.pods` a fine; parser manifest sha = `filename hash size`.
- **Trasferibilità**: routing/saliency/acceptance/recall = proprietà del MODELLO → i pod trasferiscono. I **t/s NO** (solo hardware target).

### MACCHINE / SOLDI (stato ~2026-07-06 mattina)
RunPod balance **$20.06** (utente ha ricaricato +$15). Pod attivi: 1 (replica pubblica #16). 3060 = DSpark (JOB1). Hardware in arrivo: **kit RAM 2×32 DDR4-3600 (64GB) a €300** (Corsair CMK64GX4M2D3600C16 usato, TuttoSubito) — all'arrivo: DOCP 3600→fallback 3200, memtest, poi test K67+leve a warm reale.
⚠️ **Segreti da ROTARE** (esposti in vecchi transcript, mai committati nel repo): RunPod key (`Desktop\Runapod.txt`), token HF, Supabase service_role, Discord — azione utente.

---

## §0-STORICO (2026-07-05 mattina) — dettaglio branch codex/spex-integration

**Branch attivo:** `codex/spex-integration` su `imanu86/moe-aggressive-commit`.
`main` resta stabile a `ffc1ca1` (piano SPEX + Fase 1b race). Il branch di lavoro contiene:
- `1b1e403 feat(spex): export markov params for ds4`
- `fa48071 chore(ds4): record spex stage0 cuda stats patch`
- `47ba91e docs: refresh spex handoff checkpoint`
- `5d57e07 chore(ds4): add stage0 baseline runner`
- `cdeaa71 chore(ds4): add selected upload event patch`
- `2846ff6 chore(ds4): add stage1 prefetch scaffold`
- `9a8755f chore(ds4): add markov spex loader patch`
- nuovo checkpoint in corso: DS4 routing trace capture + nearby-token finding

**Sorgente ds4 reale:** WSL `/root/ds4`, upstream `github.com/antirez/ds4`, base `80ebbc3`.
Branch locale attivo: `codex/spex-stage0`, commit nostro:
`bee9eb3 chore(spex): add routing trace capture`.
Nota: ds4 ha artifact non tracciati da build/test (`build_smoke.log`, `ds4-server.prebuild.bak`,
`tests/cuda_long_context_smoke`). Non cancellarli senza motivo.

**Transcript Claude recuperato e letto con 4 agenti:** output in
`C:\Users\imanu\Documents\Codex\2026-07-05\imanu86-moe-aggressive-commit-https-github\outputs\`.
Il punto d'ingresso sintetico è `claude_session_agent_consolidation.md`.
Verdetto importante: lo "Stadio 0" delegato nella vecchia sessione Claude era stato smentito
come non verificato/confabulato. I numeri vecchi non sono source of truth.

**Stato SPEX oggi:**
- Offline: `src/msc/spex/spex_loop.py` contiene il loop DSpark-fedele.
- Export C Markov: implementato in `src/msc/spex/c_export.py`, CLI `--export-c`, testato.
- Test Python repo: `166 passed, 1 skipped`.
- Hidden+STS è il salto vero nei risultati offline: Markov è utile ma insufficiente.
- 235B hidden resta extrapolazione nel transcript, non misura finale.

**Stadio 0 reale (nuovo, Codex 2026-07-05):**
- Patch ds4 registrata in `patches/ds4/0001-spex-stage0-cuda-stats.patch`.
- La patch aggiunge `DS4_SPEX_STATS=1` con contatori hit/miss/direct load e timing copy/sync.
- Build verificata: `make cuda CUDA_ARCH=sm_86`.
- Regression verificata: `make cuda-regression`.
- Smoke log: `runs/ds4_spex_stage0_smoke.log`.
- Smoke stats NON sono baseline paper: prompt corto, cold-ish, solo prova che la strumentazione funziona.

**Stadio 1a reale (Codex 2026-07-05):**
- Patch ds4 registrata in `patches/ds4/0002-spex-selected-upload-event.patch`.
- La patch aggiunge `DS4_SELECTED_UPLOAD_EVENT=1` (alias `DS4_CUDA_SELECTED_UPLOAD_EVENT=1`).
- Default invariato: senza flag, il path selected resta sincrono come upstream+0001.
- Con flag, le copie H2D degli expert selected registrano un CUDA event su `g_stream_selected_upload_stream`;
  i consumer chiamano `ds4_gpu_wait_selected_upload()` prima del MoE.
- Build verificata su WSL RTX 3060: `make cuda CUDA_ARCH=sm_86`.
- Regression verificata su WSL RTX 3060: `make cuda-regression`.
- Build pulita verificata su RunPod RTX 3090: stock `antirez/ds4` `80ebbc3` + patch `0001` + `0002`,
  `make cuda CUDA_ARCH=sm_86`, `make cuda-regression`.
- Runtime smoke vero su `/root/models/ds4-2bit.gguf`: `runs/ds4_selected_upload_event_smoke/`.
  ON: sync selected 216 / 25.738 ms; OFF: sync selected 9288 / 1491.401 ms. Questo prova plumbing,
  non ancora una baseline chat.

**Stadio 1b reale (Codex 2026-07-05):**
- Patch ds4 registrata in `patches/ds4/0003-spex-stage1-next-layer-prefetch.patch`.
- La patch aggiunge `DS4_SPEX_PREFETCH_NEXT_LAYER=1` sopra `DS4_SELECTED_UPLOAD_EVENT=1`.
- Default invariato: senza flag, il nuovo prefetch L+1 non parte.
- Implementa la variante async `ds4_gpu_stream_expert_cache_seed_experts_async()` e un hook decode-only:
  gli expert selected del layer L vengono usati come prefetch per L+1.
- Build verificata su WSL RTX 3060: `make cuda CUDA_ARCH=sm_86`.
- Regression verificata su WSL RTX 3060: `make cuda-regression`.
- Runtime smoke vero su `/root/models/ds4-2bit.gguf`: `runs/ds4_stage1_prefetch_smoke/`.
  Event-only: generation 0.70 t/s. Prefetch L+1: generation 0.43 t/s, hit-rate 0.0000.
- Interpretazione: questo è uno scaffold async valido, non una ottimizzazione. Il predictor ingenuo
  "stessi expert L -> L+1" non è utile sullo smoke locale e aggiunge copie. Serve collegare il predictor
  SPEX/Markov reale.

**Stadio 2a reale (Codex 2026-07-05):**
- Patch ds4 registrata in `patches/ds4/0004-spex-markov-loader-prefetch.patch`.
- La patch aggiunge loader `.spex` Markov in `ds4.c`, dietro `DS4_SPEX_FILE` / `DS4_SPEX_PATH` /
  `DS4_SPEX_MARKOV_FILE`.
- Valida shape contro il modello caricato (`L=43 E=256` per Flash, `L=61 E=384` per Pro); un file Qwen/DS2Lite
  viene rifiutato e non ricade più sul fallback L+1.
- Env runtime: `DS4_SPEX_CAP` (default `DS4_N_EXPERT_USED`) e `DS4_SPEX_TAU` (default `0.5`).
- Build verificata su WSL RTX 3060: `make cuda CUDA_ARCH=sm_86`.
- Regression verificata su WSL RTX 3060: `make cuda-regression`.
- Smoke su `/root/models/ds4-2bit.gguf`: `runs/ds4_stage2_markov_loader_smoke/`.
  File usato: `/root/ds4_synthetic_flash.spex` sintetico, Flash-shaped. Risultato: loader carica una volta,
  prefetch `SPEX markov` attivo, generation 0.44 t/s, hit-rate 0.0037. Questo prova plumbing, non predizione.

**Trace routing DS4 reale (Codex 2026-07-05):**
- Patch ds4 in corso: `patches/ds4/0005-spex-routing-trace-capture.patch`.
- Env nuovo: `DS4_SPEX_TRACE_ROUTING=/path/trace.csv`.
- Formato CSV: `pos,layer,n,e0,e1,e2,e3,e4,e5`, solo decode/logits, zero overhead se env assente.
- Build verificata su WSL RTX 3060: `make cuda CUDA_ARCH=sm_86`.
- Regression verificata su WSL RTX 3060: `make cuda-regression`.
- Run reale su `/root/models/ds4-2bit.gguf`: `runs/ds4_routing_trace_smoke/`, prompt `Conta da 1 a 200:`,
  65 token decode, 40 layer routed, 2600 righe dati.
- Finding chiave DS4 Flash: stesso-token layer precedente è quasi nullo (`~0.025` recall top6), mentre
  token recenti stesso layer sono molto informativi: window4 top6/top12 `0.342/0.507`, window8 top6/top12
  `0.366/0.550`. Quindi il prossimo predictor live deve usare memoria temporale per layer, non solo L->L+1.

**Prossima azione obbligatoria:** implementare una variante prefetch "nearby temporal" nel nuovo hook:
per ogni layer, mantieni una piccola finestra degli expert selected dei token recenti e prefetcha top-N per
lo stesso layer al token successivo. Solo dopo ha senso rilanciare benchmark lunghi e, se serve, parallelizzare
su pod economici. Stock/RunPod va bene per build, regression e plumbing, ma i claim restano sul setup
DwarfStar reale (`/root/models/ds4-2bit.gguf`, `--cuda --ssd-streaming`, stesso profilo cache).

**Regola di sicurezza:** ogni misura o claim deve avere diff/build/log/output committato.
Non fidarsi di report agentici senza artifact verificabili.

---

## §0. STATO CORRENTE (2026-07-04) — SPEX → ds4 (integrazione live)

**Direzione attiva:** integrare **SPEX** (prefetch predittivo degli expert MoE) DENTRO il motore live
**ds4/DwarfStar** (antirez, C/CUDA). È il contributo centrale del paper. SPEX predice il LOADING (mai il
GATING): il router vero decide sempre → accuratezza preservata, un miss = latenza non errore.

**Mappa durevole (dov'è cosa):**
- **Piano d'integrazione completo e VERIFICATO sul sorgente:** `docs/SPEX_INTEGRATION_PLAN.md` ← leggi QUESTO.
- **Sorgente ds4:** repo git in WSL `/root/ds4`, upstream `github.com/antirez/ds4`, **pin commit `80ebbc3`**
  (branch `main`, pulito, nessuna nostra modifica ancora). Binari buildati lì. Copia d'analisi effimera: scratchpad `ds4-src/`.
- **SPEX (simulatore, esistente):** `src/msc/spex/spex_loop.py` (loop DSpark-fedele su tracce) + `continuous_cache_sim_ORIG.py`
  (baseline euristica). Spec: `docs/SPEX_spec.md`, `docs/SPEX_LOOP.md`.
- **DSpark** = paper esterno (`docs/references/DSpark_paper.txt`), SOLO ispirazione. **SPEX ≠ DSpark.**
- **Tracce routing (esterne, non in git):** `D:\models\spex\*.npz` (q30/q235 domain/general). Risultati: `D:\models\*.json`.
- **Modelli ds4 locali:** `D:\models\ds4\` — 2-bit imatrix 86.7GB (daily driver) + static-Q4 riparato (solo confronto).
- **Registro esperimenti anti-ripetizione:** `docs/EXPERIMENTS_LEDGER.md`.

**Stato SPEX oggi:** implementato SOLO come simulatore offline (miss-rate −38/−51% su tracce), MAI in un
motore live. L'integrazione in ds4 è il progetto grosso, appena avviato.

**Roadmap (dettagli nel PLAN):**
- [x] **Fase 1** — capire ds4 + progettare l'aggancio → `docs/SPEX_INTEGRATION_PLAN.md`
- [ ] Setup build: CUDA toolkit in WSL per sm_86 (nvcc manca in WSL)
- [ ] **Stadio 0** — strumentazione + BASELINE reale sul 3060 (DECIDE se c'è margine da inseguire)
- [ ] Stadio 1 — prefetch minimo (prova plumbing async; output identico alla baseline = niente race)
- [ ] Stadio 2 — predittore SPEX vero (esportatore Python→C + `ds4_spex.c/.h`)
- [ ] Stadio 3 — STS + tuning + misura paper-worthy

**Aggancio confermato:** `ds4.c:19415` (gemello del readahead non-expert a 19391); primitiva riusabile
`ds4_gpu_stream_expert_cache_seed_experts` (ds4_cuda.cu:3246) → serve variante async.
**Rischio #1 da chiudere PER PRIMO:** race cross-stream (`cudaStreamWaitEvent` assente in ds4_cuda.cu) —
leggere il consumer `cuda_stream_selected_load` prima di scrivere il prefetch async.

**Ambiente:** WSL2 ora FUNZIONA (SVM abilitato → il blocco BIOS del vecchio handoff §7 è RISOLTO). ds4-server
gira sul 3060 col 2-bit + leve RAM; `.wslconfig` ok. **nvcc NON in WSL** = blocco build da sciogliere.
**Leva hardware parallela:** RAM 32→64/128GB = il salto di velocità più grosso, indipendente da SPEX.

---

# STORICO — fase probe/memmap (2026-06-30)

> Chat token-exhausted. Questo doc + `~/.claude/.../memory/project_moe_aggressive_commit.md` bastano
> per riprendere esatto. Tutto il codice è scritto, testato (163 pytest passed) e committabile.

## 1. Obiettivo
Far girare MoE **molto più grandi della VRAM** su una **RTX 3060 12GB** (+ RAM + SSD), tenendo in VRAM
solo il working-set di expert della sessione e streammando il resto da SSD. Latenza accettabile,
**capacità** è l'obiettivo. Repo: `C:\Users\imanu\source\repos\moe-aggressive-commit`.

## 2. Il delta genuinamente NOSTRO (vs antirez/ds4 = DwarfStar, già stato dell'arte)
ds4 fa GIÀ: SSD-streaming expert, cache reattiva LFU per-sessione (anche su CUDA), quant statica imatrix
(IQ2). **Il nostro unico delta reale = PER-SESSIONE PREDITTIVO:**
- **probe ultra-quant** sul prompt → predice il working-set PRIMA dell'inference → pre-staging (vs il
  REAGIRE di ds4 + la sua hotlist statica cotta su un corpus fisso);
- **specializzazione di precisione per-sessione**: comprimere gli expert che *questa sessione* non usa
  SOTTO il pavimento IQ2 di ds4 (lui non può: deve coprire ogni task) → più capacità/qualità a iso-footprint.

## 3. Findings (ONESTI)
- ✅ Engine slice-cache funziona e VERIFICATO: OLMoE-14GB gira in ~1.5GB VRAM, token IDENTICI al full
  (always-fetch lossless). `src/msc/hierarchy/olmoe_cache.py`.
- ⚠️ Su OLMoE (64 expert, DIFFUSO ~80% WS): il probe predittivo batte la reattiva SOLO a cache<top_k
  (impraticabile); a cache adeguata la reattiva basta. Limite strutturale (cold-start). → serve un
  modello a TANTI expert + routing concentrato per vedere il valore. `runs/validate_probe_olmoe.csv`.
- ⚠️ hard-drop (droppare expert) = accuratezza ZERO. int2 cieco = zero. int4/int8 ≈ FULL. → la coda di
  expert conta; mai droppare (sempre fetch); int4 è il pavimento sicuro. `runs/modes_granite.csv`.
- ✅ Probe-fidelity (gate): routing di un modello ultra-quant (router fp16, expert int4) predice il
  working-set del full (Jaccard ~1.0 a int4). `runs/probe_fidelity_granite.json`.
- VRAM su 3060: il muro NON sono gli expert (streammano da SSD) ma i **non-routed RESIDENTI**, che vanno
  quantizzati per entrare. Es. DS-V4 Flash non-routed ~9GB@Q8 (entra), ~18GB@bf16 (NO). Qwen3-235B
  non-routed 7.4GB@int8 (entra), 14.9GB@bf16 (NO). Quindi quant obbligatoria; il probe ci va SOPRA.

## 4. STATO ATTUALE (download + pipeline)
⚠️ **I RIAVVII/FREEZE DELLA SESSIONE UCCIDONO i task background** (harness-tracked E nohup). Solo i
processi lanciati con **`Start-Process -WindowStyle Hidden`** (PowerShell) SOPRAVVIVONO. I download
girano ora via **`scripts/download_all.py`** (sequenziale 30B→235B→DS-V4, riprendibile/idempotente)
lanciato detached. RILANCIO se morti (PowerShell):
`$env:HF_HUB_ENABLE_HF_TRANSFER='0'; Start-Process python -ArgumentList '-u','<REPO>\scripts\download_all.py' -WindowStyle Hidden -RedirectStandardOutput '<REPO>\runs\download_all.log' -RedirectStandardError '<REPO>\runs\download_all.err'`
Stato: `tail runs/download_all.log` (cerca `30B DONE` / `235B DONE` / `DS-V4 DONE`). Verifica viva:
`Get-Process python`. HW: 32GB RAM, C:704/D:590GB liberi, 3060 12GB, torch 2.6+cu124, transformers 5.12.1.
I 3 download (sequenziali, banda piena ciascuno; i task-id sotto sono MORTI dopo i riavvii):
- **Qwen3-30B-A3B bf16** (~61GB, 16 shard) → cache HF C:, ~90% (task era bdh32n2et). **Validazione metodo.**
- **Qwen3-235B-A22B Q3_K_M** (3 file split ~105GB) → `D:/models/qwen3-235b` (task bpsmdf0da). **Scale Win-nativo.**
- **DeepSeek-V4 Flash IQ2** (80.8GB) → `D:/models/ds4` — **WAITER** (task b62uz7h3o) lo avvia DA SOLO a
  235B completo. File: `DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf` da
  `antirez/deepseek-v4-gguf`. (formato custom ds4, NON llama.cpp; pre-stage per path ds4/BIOS).
- Baseline GGUF Qwen3-30B Q4 su llama.cpp (`~/llama`): task bl8o8hymk → `runs/baseline_qwen30b_gguf.log`
  (solo "gira" + tok/s rif., NON il nostro metodo).

## 5. PIPELINE DEL METODO — pronta, parte appena il 30B bf16 è completo
Verifica completamento 30B: 16 *.safetensors + model.safetensors.index.json (~61GB) nello snapshot
`~/.cache/huggingface/hub/models--Qwen--Qwen3-30B-A3B/snapshots/*/`. POI (PYTHONPATH=src):
```
python -u scripts/build_qwen3_memmap.py --out D:/qwen3_memmap        # expert → 2 memmap fp16 su SSD (RAM-safe)
python -u scripts/validate_probe_qwen3.py --memmap D:/qwen3_memmap   # probe-vs-reattiva su 128 expert
```
→ `runs/validate_probe_qwen3.csv`. Colonne: cap, react_miss, pred_miss, probe_miss, saving, net_vs_probe,
tok/s, acc. **LA DOMANDA: predire batte reagire a 128 expert?** (dove a 64-diffuso non bastava).
Componenti chiave già scritti: `MemmapBacking` + `backing_factory` in olmoe_cache.py; loader RAM-safe
(meta-init + carica solo non-expert su GPU via load_state_dict assign=True) dentro validate_probe_qwen3.py;
voce hook `Qwen/Qwen3-30B-A3B`=(mlp.gate,0,8,True). ASSUNZIONE: Qwen3-30B all-MoE (no dense layers).

## 6. NEXT STEPS (in ordine)
1. Quando 30B bf16 completo → esegui la pipeline §5 → leggi `runs/validate_probe_qwen3.csv`. Interpreta:
   net_vs_probe>0 in qualche cap = metodo valido; saving≈0 ovunque = come OLMoE (reattiva basta).
   NB: il "probe cost" nello script è sovrastimato (prefill separato a piena prec); il segnale robusto è
   il SAVING in miss (precision-independent). Considera anche tok/s.
2. Aggiungi (se promettente) la **precisione per-sessione**: working-set a bit alti, resto sotto IQ2.
3. Scala: 235B (Win-nativo, serve backbone-int8 + expert da GGUF→plumbing) O DS-V4 via ds4.
4. **DS-V4/gigante vero**: richiede WSL2 → BLOCCATO dal BIOS. L'utente deve abilitare **SVM Mode** nel
   BIOS (riavvio→Canc/F2→SVM→Enabled). Poi `~/ds4` build (`make cuda-generic`), e il prefill-seed di ds4
   (`DS4_METAL_ENABLE_STREAMING_PREFILL_CACHE_SEED=1`, gira anche su CUDA) È quasi il nostro probe →
   primo test sul gigante = accenderlo. Punto d'innesto nostro: `ds4_gpu_stream_expert_cache_seed_selected`.

## 7. Gotchas ambiente
- Il mio shell è **NON elevato** (no UAC, no reboot, no `wsl --install`). WSL2 ora INSTALLATO ma
  bloccato da virtualizzazione BIOS spenta (`VirtualizationFirmwareEnabled=False`).
- `tasklist` si impalla nello shell — non usarlo.
- I download via `&`/nohup si STACCANO dal tracking harness; usa Bash `run_in_background:true` per la notifica.
- Python stdout bufferizza in pipe → usa `python -u` per output live.
- Suite: `PYTHONPATH=src python -m pytest -q` → 163 passed, 1 skipped.

## 8. Mappa repo
docs/00-04 (architettura, positioning, modelli, rischi, **04_hierarchy_design.md**=gerarchia 3-tier).
src/msc/: instrument(router_hooks,trace) workingset policies residency validator experiment report
**hierarchy**(olmoe_cache=engine slice-cache+MemmapBacking, calibrate, metrics).
scripts/: build_qwen3_memmap, validate_probe_qwen3, validate_probe_olmoe, measure_modes_granite,
probe_fidelity_granite, coverage_curve, smoke_granite. runs/: tutti i CSV/log dei risultati.
