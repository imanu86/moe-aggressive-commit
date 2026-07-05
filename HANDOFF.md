# HANDOFF — moe-aggressive-commit

> **PUNTO D'INGRESSO UNICO.** Leggi §0 per riprendere il lavoro attivo. Le sezioni "STORICO" più sotto
> (fase probe/memmap Python, giu-2026) sono contesto precedente, non la direzione corrente.

## §0. STATO CORRENTE (2026-07-05) — SPEX → ds4 (integrazione live)

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
