# HANDOFF 5 — Studio MoE Pruning + FT BonusX (Qwen3-30B / 235B)

**Data:** 2026-07-03
**Progetto:** `moe-aggressive-commit` → PIVOT BonusX (MoE pruning paper + FT dominio)
**Scopo:** far riprendere A FREDDO l'intero studio a una nuova sessione Claude, senza perdere path, comandi, numeri, versioni, gotcha.

---

## TL;DR / STATO IN 10 RIGHE

1. **FT eseguito** (Qwen3-30B-A3B, QLoRA r=32 + router full-train, aux-loss OFF): `train_loss 0.418`, eval token-acc `94.5%`.
2. **Merge manuale** version-independent riuscito → `D:\models\qwen3-bonusx-merged` (bf16, 16 shard, ~57GB, integrità ok).
3. **STEP E (qualità per-campo)**: FT VINCE su tutti i 6 campi reali — media **65.3% → 79.4% (+14pt)**; rollover +28, stake +21. `validity` 0%/0% (campo mal-definito).
4. **STEP F (routing concentration)**: FT **DISPERDE** il routing (N_eff 49.9→57.1) → ipotesi "FT concentra" **FALSIFICATA** (coerente con ReMoE). È il **DOMINIO** a concentrare.
5. **Pruning K50 frequency**: overall **57.1% vs base full 56.0% → ZERO degrado** → 50% degli expert parcheggiabili SUL DOMINIO (REAP-style sul BASE, non sul FT).
6. **Per-neurone (sub-expert)**: neuroni DIFFUSI (~88-89% N_eff/I) → sub-expert parking rende poco.
7. **235B GPTQ-Int4 NON carica**: problema SOFTWARE (transformers fonde gli expert, i pesi int4 per-expert non mappano) → OOM/kernel error, NON capacità GPU. 2×A100 NON risolve.
8. **Buco grosso paper**: mancano TUTTI i CONTROLLI (random, K multipli, saliency-vs-frequency, dominio-vs-generale). Finora solo 1 selezione, 1 K, 1 dominio.
9. **Piano corrente = "entrambi in parallelo"**: Pod A100 (controlli 30B rigorosi) + Pod B200 (tentativo 235B auto-gptq+tf4.x).
10. **Azioni sicurezza aperte**: RunPod key nel transcript → **RUOTARE + vault (task #13)**. Chiudere sempre i pod (bruciano $).

---

## INDICE

1. [Infrastruttura & Pod (RunPod API, deploy/terminate, GPU, costi, SSH, key/vault, lezioni operative)](#1-infrastruttura--pod)
2. [Risultati 30B completi (FT, STEP E, STEP F, pruning K50, per-neurone, file json — numeri esatti)](#2-risultati-30b-completi)
3. [Blocco 235B (perché non carica: fused vs per-expert, versioni provate, errori esatti, soluzioni in ordine)](#3-blocco-235b)
4. [Mappa scripts & file (cosa fa ogni script, argomenti, dove sta, come si lancia; risultati e modelli)](#4-mappa-scripts--file)
5. [Rigore paper & prossimi passi (controlli mancanti, disegno esperimenti, altri TODO progetto)](#5-rigore-paper--prossimi-passi)
6. [RIPRENDI DA QUI (sequenza di azioni concrete)](#6-riprendi-da-qui)

---

# 1. INFRASTRUTTURA & POD

## RunPod API (GraphQL) — endpoint, auth, gotcha Cloudflare

- **Endpoint:** `https://api.runpod.io/graphql`
- **Auth:** header `Authorization: Bearer <API_KEY>`.
- **⚠️ Cloudflare WAF:** l'endpoint è dietro Cloudflare. Una richiesta **senza header `User-Agent` da browser** viene bloccata con **403** (stesso pattern già visto su Railway, err 1010). **SEMPRE settare uno `User-Agent` browser** (es. `Mozilla/5.0 ...`). `curl` col suo UA default passa; `urllib`/Python default no.
- Le operazioni si fanno con query GraphQL POST. Le tre chiave:
  - **Deploy on-demand:** mutation `podFindAndDeployOnDemand`.
  - **Terminate:** mutation `podTerminate`.
  - (Query di stato pod / balance secondo schema RunPod standard.)

### Argomenti di `podFindAndDeployOnDemand` (verificati in uso)
- `cloudType`: `SECURE` oppure `COMMUNITY`.
- `gpuTypeId`: stringa esatta del tipo GPU. Valori usati:
  - `"NVIDIA A100-SXM4-80GB"`
  - `"NVIDIA B200"`
  - `"NVIDIA H200 NVL"`
- `containerDiskInGb`: **usare disco CONTAINER generoso** (vedi lezione sul volume lento).
- `volumeInGb: 0` — **niente volume di rete** (è il collo di bottiglia a 1MB/s in scrittura).
- `startSsh: true` — abilita SSH.

### Key & rotazione (SICUREZZA — azione richiesta)
- La RunPod API key è in **`C:\Users\imanu\Desktop\Runapod.txt`** (nota: filename con refuso "Runapod").
- **La key è finita nel transcript → VA RUOTATA** dal pannello RunPod.
- **TODO vault (task #13):** aggiungere la key ruotata al vault locale `C:\Users\imanu\.cgc\cgc-secrets.vault.enc` (chiave `cgc-vault.key`, decrypt OpenSSL AES-256-CBC PBKDF2 600k) invece di tenerla in chiaro sul Desktop.

## GPU disponibili, prezzi (60h) e verdetti operativi

| GPU (`gpuTypeId`)          | VRAM   | Prezzo/h (secure) | Esito sui task 235B                                  |
|----------------------------|--------|-------------------|------------------------------------------------------|
| `NVIDIA A100-SXM4-80GB`    | 80 GB  | **$1.49/h**       | OK per 30B (training + tutti gli STEP E/F)           |
| `NVIDIA H200 NVL`          | 143 GB | **$3.79/h**       | Troppo piccola per 235B → **OOM**                    |
| `NVIDIA B200`              | 180 GB | **$5.89/h**       | OOM per fp16 fusi del 235B (problema software, non GPU) |

- **Community cloud $0.5/h = "fantasma-non-disponibile"** (mai realmente allocabile) → usare **SECURE**.
- **Balance:** ~$93 (l'utente ha caricato $80). Le GPU grosse bruciano in fretta: B200 a $5.89/h → **terminare sempre il pod appena finito il run** (vedi task #1 auto start/stop).

## SSH

- **Abilitare con `startSsh: true`** al deploy.
- **Chiave privata locale:** `~/.ssh/id_ed25519` (sul PC Windows dell'utente).
- SSH **flaky** sui pod con host sovraccarico (host load osservato 56) → non affidarsi a sessioni SSH interattive lunghe per l'orchestrazione (vedi lezione `setsid`).

## Piano corrente pod (parallelo)

L'utente ha scelto **"entrambi in parallelo"**:
1. **Pod A100 80GB** → controlli rigorosi 30B paper-grade (random/saliency/K multipli/dominio-vs-generale).
2. **Pod B200** → tentativo 235B con **auto-gptq + transformers 4.x** (lo stack per cui il GPTQ Int4 è stato prodotto).

**NB 235B: 2×A100 NON risolve** — il blocco è **software** (transformers 5.x fonde i `gate_up_proj` per-expert → i pesi int4 per-expert non mappano → ricrea fp16 vuoti → 177GB OOM anche su B200 180GB; transformers 4.57 + gptqmodel → kernel error `b_q_weight type is not kInt`), non capacità GPU. Se auto-gptq fallisce: dequantizzare GPTQ→bf16-per-expert, oppure vLLM-logit-extraction, oppure archiviare il 235B come future-work.

## LEZIONI OPERATIVE CRITICHE sui pod (imparate a caro prezzo)

1. **Orchestrazione SUL POD con `setsid` (non catene bash locali).** Le pipeline lanciate da bash locale **muoiono ai confini di sessione**. Mettere lo script orchestratore sul pod e lanciarlo detached (`setsid ... &`), con file-sentinella di completamento (gli script scrivono marker tipo `/root/EVAL_<tag>_DONE`, `/root/STEPF_<tag>_DONE`, `/root/PRUNE_<tag>_DONE`, `/root/SUBEXP_<tag>_DONE`, `/root/MANUAL_MERGE_DONE`).

2. **`HF_HOME=/workspace/hf` SEMPRE settato.** Senza, ri-scarica i **61GB** del Qwen3-30B sul container piccolo. Lo snapshot atteso è `/workspace/hf/hub/models--Qwen--Qwen3-30B-A3B/snapshots/*/`.

3. **Volume di rete a 1MB/s in scrittura → usare disco CONTAINER (4–8GB/s).** Il volume RunPod è disastrosamente lento in write. Per questo il **merge del 30B è stato fatto A MANO su disco container** (`manual_merge.py`, ~4 min; su volume sarebbe stato ore). Deploy con `volumeInGb: 0` + `containerDiskInGb` grande.

4. **torchvision DEVE matchare torch** (`0.23.0+cu128` per torch `2.8.0`) per far girare **gptqmodel**. Se non serve la parte vision, si può togliere transformers text-only.

5. **Evitare `pip install transformers>=5`** → tira **torch CPU** e rompe CUDA. Se capita, **reinstallare torch cu128**.

6. **Processi duplicati → OOM.** Una chain morta + un orchestratore nuovo che partono insieme saturano la VRAM. **Verificare `pgrep` prima di lanciare** qualsiasi nuovo job.

7. **Infra pod spesso pessima** (volume 1MB/s, host load 56, SSH flaky) → il merge e i passi delicati si sono fatti a mano; **GGUF Q4 + deploy si fanno in LOCALE** dal merged scaricato (`llama-quantize.exe` è in `C:\Users\imanu\llama`).

## Merge manuale del 30B (perché e come) — `manual_merge.py`

`peft`/`llama` `merge_and_unload` è **rotto per version-hell** (peft/transformers) e il volume pod è troppo lento → **merge manuale sui safetensors, version-independent**. Path sul pod:
- Base snapshot: `/workspace/hf/hub/models--Qwen--Qwen3-30B-A3B/snapshots/*/`
- Adapter: `/workspace/qwen3-bonusx-lora/adapter_model.safetensors`
- Output: `/workspace/qwen3-bonusx-merged`

Meccanica: l'adapter LoRA è **fuso** (transformers 5.x rappresenta gli expert come `gate_up_proj` unico). Lo script **splitta il delta fuso → per-expert** via `bmm` (no loop): per il blocco gate_up `de[e] = scale·(B_e @ A_e)` → `[2I,H]`, poi `gate = de[:I]`, `up = de[I:]` (**gate PRIMA di up**); il router `mlp.gate` è **modules_to_save → full replace** (non delta). `SCALE = alpha/r = 2.0` (gate_up 128/64, down 64/32), `I = 768` (moe_intermediate_size). Mismatch di shape → **errore esplicito, mai corruzione silenziosa**.
- **`python manual_merge.py --check`** = dry-run solo sul layer 0 (stampa norme `||d||/||W||`, verificate **0.0087 / 0.0093**), poi STOP.
- **`python manual_merge.py`** = merge completo, salva 16 shard bf16 (**~57GB**) + copia config/tokenizer, scrive `/root/MANUAL_MERGE_DONE`.

Risultato verificato: merged bf16 57GB in `D:\models\qwen3-bonusx-merged` (16 shard, integrità ok).

## Script di misura (tutti GPTQ-aware, girano sul pod)

Tutti caricano con `device_map={'': 0}`; se il nome modello contiene `GPTQ`/`Int4`/`AWQ` **omettono `dtype=bf16`** (lascia il caricatore quant nativo), altrimenti `dtype=torch.bfloat16`. Prompt di default `/workspace/raft_eval.jsonl` (152 held-out). Output json in `/root` poi copiati in `D:\models\`.

- **`step_f.py`** `--model <path> --tag <base|ft>` — concentrazione routing. Hook forward su ogni `model.model.layers[i].mlp.gate` (forward-only, no generate); ricostruisce le prob top-k con `norm_topk_prob`, accumula la **massa di routing per-expert**. Calcola `committed_fraction@{0.8,0.9,0.95}` e `N_eff = exp(entropia)` per layer + medie. Salva `experts_by_mass_asc` (**tutti** gli expert ordinati per massa ascendente per layer = candidati pruning a **qualsiasi K**) e `low_mass_experts_bottom50pct` (backward-compat). Scrive `stepf_<tag>.json`.

- **`eval_quality.py`** (STEP E) `--model <path> --tag <base|ft>` — qualità per-campo. `model.generate` diretto, **`enable_thinking=False`** (Qwen3 è ibrido-reasoning: senza, il base fa parse_fail=152 mangiando token in `<think>`). `max_new_tokens=160`, greedy. Confronta 6 campi vs gold: CAT `technique/variance/validity` (exact), NUM `cap_eur/rollover_x/cashback_pct/stake_min_eur` (tol 0.01). Salva accuracy + `technique_confusion`. Scrive `eval_<tag>.json`.

- **`prune_validate.py`** (STEP F+) `--model <path> --k <pct> --tag <...>` — pruning via **gate-masking + reroute**. Hook sul `mlp.gate` che mette a `-inf` i logit dei `K%` expert mascherati e ri-normalizza il top-k → il modello instrada solo tra i superstiti. Poi rigira l'eval qualità come STEP E.
  - `--k 0` = full (nessuna maschera).
  - `--random` = **CONTROLLO paper-grade**: maschera `K%` expert **a caso** (seed `--seed`, default 0) invece dei freddi → è il test random-vs-saliency che rende pubblicabile.
  - `--maskfile` (default `/root/stepf_base.json`) = da dove legge il ranking; usa `experts_by_mass_asc` (fallback `low_mass_experts_bottom50pct`).
  - `--k` accetta **qualsiasi valore** (K multipli 25/50/70 per il paper).
  - Scrive `eval_<tag>.json`.

- **`subexpert.py`** (STEP F+ per-neurone) `--model <path> --tag <...>` — sparsità **dentro** gli expert (idea sub-expert). **Monkeypatch di `Qwen3MoeExperts.forward`** (da `transformers.models.qwen3_moe`) per accumulare `|act(gate)·up|` per-neurone su `(layer,expert)`. Calcola committed_fraction/N_eff a grana neurone (I=768). Scrive `subexpert_<tag>.json`. **Nota:** questo carica sempre bf16 (NON GPTQ-aware — il monkeypatch usa `gate_up_proj`/`down_proj` densi).

## File risultati (già scaricati in `D:\models\`)
`eval_base.json`, `eval_ft.json`, `eval_prune50.json`, `stepf_base.json`, `stepf_ft.json`, `subexpert_base.json`, `subexpert_ft.json`. Held-out prompts: `bonus-kb\bonusx-kb\retrieval\ft\raft_eval.jsonl` (152), sul pod copiato in `/workspace/raft_eval.jsonl`.

## Stato pod a fine sessione
- **Pod1** (volume di rete 1MB/s) → **terminato** dopo aver estratto i risultati.
- **Pod2** (disco container veloce) → usato per il merge manuale (4 min), poi terminato.
- Storicamente l'account RunPod ha anche un pod ComfyUI A100 SXM 80GB separato (progetto video, path `/workspace/runpod-slim/ComfyUI/`) — **non** legato a questo studio, ma consuma storage se lasciato Stopped.

**Percorsi assoluti chiave:** key RunPod `C:\Users\imanu\Desktop\Runapod.txt` (DA RUOTARE + vault task #13); vault `C:\Users\imanu\.cgc\cgc-secrets.vault.enc` + `cgc-vault.key`; scripts in `C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos\d9c25753-1d5b-40b0-abbc-89928fcceeca\scratchpad\` (`manual_merge.py`, `step_f.py`, `eval_quality.py`, `prune_validate.py`, `subexpert.py`); merged 57GB `D:\models\qwen3-bonusx-merged`; adapter `D:\models\qwen3-bonusx-lora`; llama-quantize `C:\Users\imanu\llama`; SSH key `~/.ssh/id_ed25519`.

---

# 2. RISULTATI 30B COMPLETI

Tutti i risultati provengono dallo studio del **2026-07-03** su Qwen3-30B-A3B (128 expert/layer, top-k=8, 48 layer MoE), 2 pod A100-80GB in parallelo, **152 held-out KB** (`raft_eval.jsonl`, split per-cluster anti-leakage), **thinking OFF** (`enable_thinking=False`). File gold V3.1: `{technique, variance, cap_eur, rollover_x, cashback_pct, stake_min_eur, validity}`.

## 2.1 Fine-tuning (baseline dell'intero studio)

- **Metodo**: QLoRA r=32 su attn+MLP + **router `mlp.gate` in `modules_to_save` = FULL-TRAIN** (~48 layer), **aux-loss load-balancing OFF** (assert anti-aux nel training script, altrimenti il routing si ri-diffonde).
- **Iperparametri**: 3 epoche, lr 1e-4, batch-eff 16, cutoff 4096, seed 42. Dataset: `raft_train.jsonl` = 1299 esempi (chat messages, 86% con vicini da `promo_recall`, 14% senza).
- **Risultati training**: `train_loss 0.418`, eval token-acc **94.5%**.
- **Adapter**: `D:\models\qwen3-bonusx-lora` (4 GB, formato fused come lo rappresenta transformers 5.x).
- **Merge**: fatto A MANO con `manual_merge.py` (`merge_and_unload` di peft/llama rotto per version-hell peft/transformers; volume pod a 1MB/s). Norme delta verificate **0.0087 / 0.0093** (‖d‖/‖W‖ sugli expert.0). Output: `D:\models\qwen3-bonusx-merged`, bf16 57 GB, 16 shard, integrità verificata. Merge in ~4 min sul pod2 (disco veloce).

## 2.2 STEP E — qualità per-campo FT-vs-base (exact-match / tol numerica 0.01)

Esattizzato con `eval_quality.py` (generate `max_new_tokens=160`, greedy `do_sample=False`, `enable_thinking=False`). Confronto: CAT `{technique, variance, validity}` exact, NUM `{cap_eur, rollover_x, cashback_pct, stake_min_eur}` con `abs(a-b)<0.01`.

**IL FT VINCE SU TUTTI I 6 CAMPI REALI. Media base 65.3% → FT 79.4% (+14 pt).**

| Campo | Base | FT | Δ |
|---|---|---|---|
| technique | 63.8% | 71.1% | +7.3 |
| variance | 71.7% | 82.2% | +10.5 |
| cap_eur | 77.6% | 83.6% | +6.0 |
| **rollover_x** | 43.4% | **71.7%** | **+28.3** |
| cashback_pct | 69.1% | 80.3% | +11.2 |
| **stake_min_eur** | 66.4% | **87.5%** | **+21.1** |
| **media 6 campi** | **65.3%** | **79.4%** | **+14** |
| validity | 0% | 0% | campo MAL-DEFINITO |

- **`validity` = 0%/0%**: campo mal-definito (l'audience TUTTI/RISERVATA non è sempre nel testo). Da sistemare NEL DATASET, non è un difetto del FT.
- **Gotcha critico**: Qwen3-30B è ibrido-reasoning. Base con **thinking ON** → `parse_fail=152` (mangia i token dentro `<think>`, JSON mai emesso). Serve `enable_thinking=False` per confronto equo. Il FT ha imparato a saltare il thinking → `parse_fail=0` sempre.
- **File**: `D:\models\eval_base.json`, `D:\models\eval_ft.json` (contengono `accuracy` per-campo + `technique_confusion` matrice per-tecnica + `parse_fail`).

## 2.3 STEP F — concentrazione del routing FT-vs-base

Misurato con `step_f.py` (hook forward su ogni `model.model.layers[i].mlp.gate`, forward-only, softmax → topk → norm_topk_prob, accumula massa di routing per-expert; `committed_fraction@θ` = frazione di expert che copre θ della massa, `N_eff = exp(entropia)`). 152 prompt BonusX reali.

| Metrica | Base | FT |
|---|---|---|
| cf@0.95 | 0.506 | **0.572** |
| cf@0.90 | 0.406 | 0.461 |
| cf@0.80 | 0.286 | 0.326 |
| **N_eff / 128** | **49.9** | **57.1** |

- **IL FT HA DISPERSO IL ROUTING, NON CONCENTRATO** (N_eff 49.9→57.1, +6.6pt su cf@0.95). L'ipotesi utente "router sbloccato + aux-loss off ⇒ concentrazione" è **FALSIFICATA** sui dati reali — esattamente come predetto da ReMoE (serve un obiettivo ESPLICITO di località, non basta sbloccare il gate).
- **Notizia buona**: il BASE su dominio BonusX = cf@0.95 **0.51** vs **66%** su prompt generici (misura di giugno) → **è il DOMINIO che concentra** (ESFT-style, pesi congelati). Parking/REAP vanno fatti sul **BASE ristretto al dominio**, non sul FT.
- **File**: `D:\models\stepf_base.json`, `D:\models\stepf_ft.json`. Chiavi utili per il pruning: `experts_by_mass_asc` (per ogni layer, tutti gli expert ordinati per massa ASCENDENTE = candidati pruning per qualsiasi K) + `low_mass_experts_bottom50pct` (backward-compat) + `mean_committed_fraction` + `mean_n_eff` + `layers[i]`.

## 2.4 Pruning K50 (payoff VRAM) — NEAR-LOSSLESS

Validato con `prune_validate.py` (maschera i bottom-K% expert per massa via reroute nel gate: setta i logit degli expert freddi a `-inf`, ricalcola softmax+topk+norm tra i superstiti; poi rigenera e valuta la qualità per-campo come STEP E). Maschera letta da `experts_by_mass_asc` in `stepf_base.json`.

- Mascherando **64/128 expert freddi per layer** (K=50%, per massa routing) sul dominio BonusX: **overall field-acc 57.1% vs base full 56.0%** → **ZERO degrado** (dentro il rumore).
- ⇒ **50% degli expert parcheggiabili/prunabili sul dominio** (Q4 stimato 18.6GB → ~10-11GB). Il pruning va sul **BASE** (il dominio concentra), NON serve il FT.
- **File**: `D:\models\eval_prune50.json` (contiene `k`, `overall`, `accuracy` per-campo, `parse_fail`). Per-campo: technique 70.4%, variance 75.7%, rollover 44.1%, stake 57.9%.
- **Gotcha operativo**: l'hook di pruning si aspetta che `mlp.gate` ritorni la tripla `(logits, routing_weights, selected_experts)` — vero per Qwen3Moe in transformers 5.x. Il flag `--random` (con `--seed`) fa il **CONTROLLO paper** (maschera K% expert A CASO invece dei freddi); `--k` accetta qualsiasi valore (25/50/70); `--maskfile` default `/root/stepf_base.json`. GPTQ-aware (salta `dtype=bf16` se il nome contiene GPTQ/Int4/AWQ). **Il controllo random + saliency-vs-frequency + K multipli NON sono ancora stati eseguiti** (è il prossimo blocco "rigore paper").

## 2.5 Per-neurone (idea sub-expert) — neuroni DIFFUSI, poco margine

Misurato con `subexpert.py` (monkeypatch di `Qwen3MoeExperts.forward`: accumula `|act_fn(gate)*up|` per-neurone per ogni (layer, expert) attivato; committed_fraction/N_eff a grana neurone, I=768).

| Metrica | Base | FT |
|---|---|---|
| N_eff / 768 | 679.5 (88.5%) | 683.3 (89.0%) |

- **Dentro gli expert i neuroni NON si concentrano** (né base né FT, entrambi ~88-89%) → **sub-expert / per-neuron parking rende POCO**.
- **File**: `D:\models\subexpert_base.json`, `D:\models\subexpert_ft.json` (chiavi `neuron_committed_fraction` @0.8/0.9/0.95, `neuron_mean_n_eff`, `neuron_n_eff_over_I`).

## 2.6 Sintesi studio 30B

1. **FT = win QUALITÀ** (+14 pt media, rollover +28, stake +21) — confermato, ma su distribuzione KB curata in-distribution (v1 NON production-ready: input reale = raw_text scrapato, non embed_text KB).
2. **FT NON aiuta la VRAM** (disperde il routing, STEP F).
3. **VRAM win = PRUNING DOMINIO 50% near-lossless** (REAP-style sul BASE, non sul FT).
4. **Sub-expert/per-neuron = poco margine** (neuroni diffusi).

## 2.7 Elenco file JSON risultati (tutti in `D:\models\`)

`eval_base.json`, `eval_ft.json`, `eval_prune50.json`, `stepf_base.json`, `stepf_ft.json`, `subexpert_base.json`, `subexpert_ft.json`.

Script sorgente (nello scratchpad `...\d9c25753-1d5b-40b0-abbc-89928fcceeca\scratchpad\`): `eval_quality.py`, `step_f.py`, `prune_validate.py`, `subexpert.py`, `manual_merge.py`. Tutti girano sul pod con `--model` + `--tag`, prompts default `/workspace/raft_eval.jsonl`, output default `/root`, e scrivono un sentinel `/root/*_DONE` a fine run.

---

# 3. BLOCCO 235B

Perché `Qwen/Qwen3-235B-A22B-GPTQ-Int4` non carica.

## 3.0 TL;DR operativo
Il 235B è **fermo al passo 0: caricare i pesi in memoria**. Non è un problema di GPU (H200 143GB e B200 180GB entrambe OOM) né di codice nostro: è un **mismatch tra il formato del checkpoint GPTQ (quantizzato int4 PER-EXPERT, expert separati) e come `transformers` 5.x rappresenta il MoE di Qwen3 (expert FUSI in un unico tensore `gate_up_proj`/`down_proj`)**. Nessuno dei nostri script (`step_f.py`, `eval_quality.py`, `prune_validate.py`, `subexpert.py`) è mai arrivato a girare sul 235B: sono già GPTQ-aware (vedi §3.5) ma si fermano tutti alla `from_pretrained`.

Modello target: `Qwen/Qwen3-235B-A22B-GPTQ-Int4` (ufficiale Qwen, ~120GB su disco in int4, checkpoint con expert quantizzati **per-expert**). Confronto onesto per il paper: 235B-**GPTQ-int4** vs 30B-**bf16** → confondente da dichiarare (quant diverso, non solo scala).

## 3.1 La radice: FUSED vs PER-EXPERT
Due layout incompatibili degli expert MoE:

- **Checkpoint GPTQ (su disco, come lo pubblica Qwen)**: ogni expert è un tensore **separato e quantizzato int4** con i suoi buffer GPTQ (`qweight` int32-packed, `qzeros`, `scales`, `g_idx`). Le chiavi sono nella forma `...mlp.experts.{e}.{gate,up,down}_proj.{qweight,qzeros,scales,g_idx}`. È lo **stesso layout per-expert-separato** che vediamo sul 30B (verificato con `inspect_base.py`: `model.layers.L.mlp.experts.{e}.{gate,up,down}_proj.weight`, 128 expert distinti nel layer 0) — solo che qui i pesi sono int4 GPTQ invece che bf16.

- **`transformers` 5.x per Qwen3-MoE (in memoria)**: la classe `Qwen3MoeExperts` **fonde tutti gli E expert in due soli tensori 3D** per layer: `gate_up_proj` `[E, H, 2I]` e `down_proj` `[E, I, H]` (batched, per fare la forward con una `bmm` invece di un loop Python). È la stessa fusione che ci ha costretti al **merge manuale** dell'adapter sul 30B (`manual_merge.py`: l'adapter LoRA arriva fuso `gate_up: lora_A [E*64,H]`, e va **splittato per-expert** per rimappare sul base separato — la fusione è documentata lì).

**Conseguenza esatta sul 235B**: quando `from_pretrained` istanzia il modello con lo state-dict fuso e prova a caricare i pesi GPTQ per-expert:
1. le chiavi per-expert del checkpoint (`experts.0.gate_proj.qweight`, `experts.1...`, …) **non trovano corrispondenza** nel modello fuso (che ha `experts.gate_up_proj` unico) → valanga di **UNEXPECTED keys** (dal checkpoint) e **MISSING keys** (nel modello);
2. per i tensori "missing" transformers **ricrea placeholder fp16 vuoti** della dimensione fusa → il modello si materializza **de-quantizzato a fp16** invece che int4: **~177GB** invece di ~120GB → **OOM anche su B200 180GB**;
3. i buffer GPTQ per-expert (scales/zeros/g_idx) restano orfani → **expert rotti** anche se la memoria bastasse. Doppio fallimento: memoria E correttezza.

## 3.2 Versioni provate ed errori ESATTI

| Stack | GPU | Esito | Errore/causa |
|---|---|---|---|
| `transformers` 5.x (default) | B200 180GB | **OOM** | Fonde gli expert → placeholder fp16 → ~177GB, non mappa i pesi int4 per-expert (UNEXPECTED/MISSING) |
| `transformers` 5.x | H200 NVL 143GB | **OOM** | Come sopra, GPU ancora più piccola |
| `transformers` 4.57 + `gptqmodel` | (pod dedicato) | **kernel error** | `b_q_weight type is not kInt` (il kernel GPTQ di gptqmodel rifiuta il tensore packed così com'è) |

Tutti e tre i pod **terminati**. Note:
- Il `2xA100` **NON risolve**: è un problema **software** (layout fuso/per-expert), non di capacità aggregata; e comunque device_map su 2 GPU non ri-quantizza i placeholder fp16.
- `transformers >= 5` va evitato installarlo alla leggera: **tira torch CPU** → poi va reinstallato torch cu128 (lezione operativa #5 del progetto).
- `torchvision` DEVE matchare torch (`0.23.0+cu128` per torch `2.8.0`) o `gptqmodel` non importa; senza torchvision, togliere il ramo text-only di transformers (lezione #4).

## 3.3 Perché il 30B "funziona" e il 235B no
Identico layout per-expert su disco, **ma**:
- Il **30B lo carichiamo bf16** (`Qwen/Qwen3-30B-A3B` non-quantizzato, oppure il nostro `qwen3-bonusx-merged` bf16 57GB). In bf16 la fusione di transformers è innocua: i pesi ci sono tutti, li fonde e basta, entra in A100 80GB. **Nessun buffer GPTQ da rimappare.**
- Il **235B esiste in pratica solo in int4** (bf16 sarebbe ~470GB, fuori portata). Quindi siamo **obbligati** a passare per il checkpoint GPTQ per-expert → e lì la fusione rompe tutto.

In una riga: **il problema non è "235B", è "GPTQ-int4 per-expert dentro transformers-che-fonde".**

## 3.4 Soluzioni da provare, IN ORDINE

### Tentativo 1 (PROSSIMO, già deciso) — `auto-gptq` + `transformers` 4.x
Lo **stack per cui il checkpoint GPTQ è stato prodotto**. `auto-gptq` (non `gptqmodel`) su `transformers` 4.x conosce il layout per-expert quantizzato e installa i **kernel GPTQ CUDA** che caricano `qweight/qzeros/scales/g_idx` senza de-quantizzare a fp16.
- GPU: **B200 180GB** (preferita) o 2xA100 80GB (160GB aggregati, device_map=auto) — ma vedi caveat 2xA100 in §3.2.
- Gotcha da evitare in anticipo:
  - **NON** far tirare `transformers>=5` (ri-fonde → sei punto e a capo). Pinnare es. `transformers==4.44/4.45.x` compatibile con la release di `auto-gptq`.
  - torch cu128 + torchvision matchato PRIMA di installare auto-gptq (kernel compilati contro quel torch).
  - `HF_HOME=/workspace/hf` sempre settato (lezione #2, il 235B int4 è ~120GB, non ri-scaricarlo).
  - Orchestrazione **sul pod con `setsid`** (lezione #1: le catene bash locali muoiono ai confini di sessione).
  - `pgrep` prima di lanciare: niente processi duplicati (chain morta + orch nuovo → OOM, lezione #6).
- **Se carica**: girano subito i nostri script GPTQ-aware (§3.5) — il codice è già pronto.

### Tentativo 2 — Dequantizzare GPTQ → bf16 PER-EXPERT (offline, su disco)
Se auto-gptq dà ancora `kInt`/kernel error: **dequantizzare il checkpoint una volta** (GPTQ int4 → bf16, mantenendo il layout **per-expert separato**, NON fuso), salvare su disco veloce (container disk 4-8GB/s, **non** volume di rete 1MB/s — lezione #3), poi caricare bf16 come facciamo col 30B merged.
- Costo: ~470GB bf16 su disco → non entra in una GPU, ma serve solo per **estrarre logit/routing** layer-per-layer (hook forward), non per generare a piena velocità. Si può dequantizzare + shardare + caricare con offload CPU/NVMe.
- È l'analogo del nostro `manual_merge.py` (operare sui safetensors, version-independent, mismatch → errore esplicito no-corruzione): stessa filosofia, applicata al de-quant per-expert.

### Tentativo 3 — vLLM logit/router extraction
`vLLM` ha kernel GPTQ/Marlin propri per MoE quantizzato e **non passa per la fusione di transformers**. Caricare in vLLM e **estrarre i router-logits** (per `step_f.py`-equivalente) via hook/logprobs. Sufficiente per lo studio di concentrazione routing (STEP F); più scomodo per l'eval per-campo (serve generazione controllata, `enable_thinking=False`).

### Tentativo 4 — 235B come FUTURE-WORK nel paper
Se 1-3 falliscono in tempi ragionevoli: **archiviare il 235B**. La tesi del paper regge sul **30B con i controlli rigorosi** (random-vs-saliency, K 25/50/70, dominio-vs-generale). Il 235B diventa "scaling: lasciato a lavoro futuro per via del gap toolchain GPTQ-per-expert ↔ transformers-fused". Onestà da dichiarare comunque: 235B avrebbe introdotto il confondente **GPTQ-int4 vs bf16**.

## 3.5 Stato dei nostri script rispetto al 235B (già pronti)
Tutti gli script nello scratchpad sono **già GPTQ-aware**: rilevano il quant dal nome modello e NON forzano `dtype=bf16` (che de-quantizzerebbe). Pattern identico in `step_f.py`, `eval_quality.py`, `prune_validate.py`:
```python
is_quant = ('GPTQ' in a.model or 'Int4' in a.model or 'AWQ' in a.model)
kw = {} if is_quant else {'dtype': torch.bfloat16}
model = AutoModelForCausalLM.from_pretrained(a.model, device_map={'': 0}, **kw)
```
Quindi appena il 235B **carica** (qualunque tentativo 1-3), basta lanciare:
- `python step_f.py --model Qwen/Qwen3-235B-A22B-GPTQ-Int4 --tag base235` → concentrazione routing (hook su `mlp.gate`, `committed_fraction@θ` + `N_eff`, `experts_by_mass_asc` per il pruning).
- `python prune_validate.py --model ... --k 50 --tag prune235` (+ `--random` per il controllo paper).
- `python eval_quality.py --model ... --tag q235` (eval per-campo, `enable_thinking=False`).

**Caveat da verificare quando carica**: gli script assumono `model.model.layers[i].mlp.gate` come router e `cfg.num_experts`/`num_experts_per_tok`. Sul 235B `E=128`, `num_experts_per_tok=8` (A22B) — controllare che i nomi dei moduli combacino (se auto-gptq/vLLM cambiano la classe MoE, l'attach dell'hook va riadattato, come già dovemmo fare per OLMoE/Granite in passato).

## 3.6 Riferimenti path/infra 235B
- Modello: `Qwen/Qwen3-235B-A22B-GPTQ-Int4` (HF hub; su pod cache in `/workspace/hf`).
- Script pronti: `C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos\d9c25753-1d5b-40b0-abbc-89928fcceeca\scratchpad\{step_f,eval_quality,prune_validate,subexpert}.py`.
- Riferimento layout fuso↔per-expert: stesso scratchpad, `manual_merge.py` (split fused→per-expert dell'adapter, con norme e orientamenti) e `inspect_base.py` (dump chiavi/shape `experts.J` del 30B).
- Infra RunPod: vedi §1.

---

# 4. MAPPA SCRIPTS & FILE

Tutti gli script Python/bash stanno **SUL DISCO LOCALE** in:
`C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos\d9c25753-1d5b-40b0-abbc-89928fcceeca\scratchpad\`
(scratchpad della sessione precedente, NON la sessione corrente — path hard-coded, copiarlo se serve). In esecuzione vengono `scp`-ati sul pod RunPod e girano da `/workspace` (script) leggendo `/workspace/raft_eval.jsonl`, scrivendo output in `/root/`. **Tutti gli script assumono path POD (`/workspace/...`, `/root/...`), non Windows.**

I **risultati** sono già stati ri-scaricati in `D:\models\*.json`. I **modelli** stanno tutti in `D:\models\`.

## 4.1 Script di analisi paper (i 4 core, GPTQ-aware)

Ogni script ha lo stesso preambolo GPTQ-aware:
`_kw = {} if ('GPTQ' in model or 'Int4' in model or 'AWQ' in model) else {'dtype': torch.bfloat16}` — cioè per il 235B GPTQ NON forza bf16 (lascia decidere al loader quantizzato); per il 30B bf16 forza `dtype=torch.bfloat16`. Tutti caricano con `device_map={'': 0}` (GPU singola, tutto su cuda:0). Tutti droppano un sentinel file `/root/<STEP>_<tag>_DONE` a fine run (per orchestrazione via `setsid` + polling del sentinel).

### `step_f.py` — router concentration (STEP F)
- **Cosa fa**: registra un `forward_hook` su OGNI `model.model.layers[i].mlp.gate` (il router). Per ogni token calcola `softmax(logits)`, prende `topk` (8), rinormalizza (`norm_topk_prob`), accumula la **massa di routing per-expert** per layer. A fine run calcola per ogni layer `committed_fraction@theta` (frazione di expert che copre θ=0.8/0.9/0.95 della massa) e `N_eff = exp(entropia)`. Salva `experts_by_mass_asc` = TUTTI gli expert ordinati per massa **ascendente** per layer (i primi = i più freddi = candidati pruning per qualsiasi K). Mantiene anche `low_mass_experts_bottom50pct` per backward-compat.
- **Args**: `--model` (req), `--tag` (req), `--prompts` (def `/workspace/raft_eval.jsonl`), `--out` (def `/root`), `--limit` (def 152).
- **Solo FORWARD** (no generate), usa `messages[:2]` (system+user) con `add_generation_prompt=True`.
- **Lancio**: `python step_f.py --model Qwen/Qwen3-30B-A3B --tag base` / `--model /workspace/qwen3-bonusx-merged --tag ft`.
- **Output**: `/root/stepf_<tag>.json` → in `D:\models\stepf_base.json` / `stepf_ft.json`.

### `eval_quality.py` — qualità per-campo (STEP E)
- **Cosa fa**: `model.generate` (greedy, `do_sample=False`, `max_new_tokens=160`) su tutti i 152 prompt, estrae il primo blocco `{...}` dal decode, confronta col gold `messages[2]`. Campi: CAT=`[technique, variance, validity]` (match esatto), NUM=`[cap_eur, rollover_x, cashback_pct, stake_min_eur]` (tolleranza `abs<0.01`). Conta `parse_fail`, salva confusion matrix su `technique`.
- **GOTCHA CRITICO**: `enable_thinking=False` nell'`apply_chat_template` — Qwen3 è ibrido-reasoning; senza questo la base va in `parse_fail=152` (thinking ON rompe il parse JSON).
- **Args**: `--model` (req), `--tag` (req), `--prompts`, `--out`.
- **Lancio**: `python eval_quality.py --model Qwen/Qwen3-30B-A3B --tag base` / `--model /workspace/qwen3-bonusx-merged --tag ft`.
- **Output**: `/root/eval_<tag>.json` → `D:\models\eval_base.json` / `eval_ft.json`.

### `prune_validate.py` — pruning gate-masking (STEP F+) — **lo script chiave per i controlli paper**
- **Cosa fa**: maschera i bottom-K% expert per layer mettendone i logit del gate a `-inf` (reroute nel top-k tra i rimanenti), poi rifà la stessa eval per-campo di `eval_quality.py` (stessi CAT/NUM, `enable_thinking=False`). Calcola anche `overall` = accuratezza media su tutti i campi.
- **Args**: `--model` (req), `--tag` (req), `--k` (def 50, % expert mascherati per layer; **0 = full/no mask**), **`--random`** (CONTROLLO: maschera K% a CASO invece dei freddi — **è il controllo random che rende il paper pubblicabile**), `--seed` (def 0), `--maskfile` (def `/root/stepf_base.json`, da cui legge `experts_by_mass_asc`), `--prompts`, `--out`.
- **Lancio K freddi**: `python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --tag prune50`
- **Lancio controllo random**: `python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 0 --tag prune50_random`
- **Per K multipli** (25/50/70 richiesti dal rigore paper): variare `--k 25 --tag prune25` ecc.
- **Output**: `/root/eval_<tag>.json` → `D:\models\eval_prune50.json` (finora solo K50 freddi eseguito).
- **NOTA saliency**: attualmente maskfile usa massa-di-routing (proxy FREQUENZA). Per il controllo **saliency vs frequency** richiesto serve un maskfile alternativo con ranking saliency (REAP-style) — da produrre, `prune_validate.py` lo accetta già via `--maskfile`.

### `subexpert.py` — sparsità per-neurone (STEP F+, idea sub-expert)
- **Cosa fa**: **monkeypatch** di `transformers.models.qwen3_moe.modeling_qwen3_moe.Qwen3MoeExperts.forward` per accumulare `|act_fn(gate)*up|` per-neurone per ogni coppia `(layer, expert)` sui 152 prompt (I=768 neuroni intermedi). Calcola `committed_fraction`/`N_eff` a grana neurone, mediati sugli slot expert attivati.
- **NON è GPTQ-aware** (forza sempre `dtype=torch.bfloat16`) — solo 30B bf16.
- **Args**: `--model` (req), `--tag` (req), `--prompts`, `--out`, `--limit` (def 152).
- **Lancio**: `python subexpert.py --model Qwen/Qwen3-30B-A3B --tag base` / `--model /workspace/qwen3-bonusx-merged --tag ft`.
- **Output**: `/root/subexpert_<tag>.json` → `D:\models\subexpert_base.json` / `subexpert_ft.json`.

## 4.2 Script di merge (LoRA → merged bf16)

### `manual_merge.py` — merge manuale version-independent (**questo è quello VERIFICATO e usato**)
- **Perché esiste**: `merge_and_unload` di peft/llama rotto per version-hell peft/transformers + volume pod a 1MB/s. Fa il merge a mano sui safetensors, split del **delta LoRA fuso** (come lo rappresenta transformers 5.x) in per-expert.
- **Path hard-coded nello script**: `BASE_SNAP = glob('/workspace/hf/hub/models--Qwen--Qwen3-30B-A3B/snapshots/*/')[0]`, `ADP = /workspace/qwen3-bonusx-lora/adapter_model.safetensors`, `OUT = /workspace/qwen3-bonusx-merged`, `SCALE = 2.0` (alpha/r: gate_up 128/64, down 64/32), `I = 768`.
- **Matematica dello split** (documentata nel docstring, VERIFICATA): adapter fuso `gate_up`: `lora_A [E*64,H]=[8192,2048]`, `lora_B [2I,E*64]=[1536,8192]`; `down`: `lora_A [E*32,I]=[4096,768]`, `lora_B [H,E*32]=[2048,4096]`. Split fuso→per-expert via `batched_de` (bmm, no loop): `de_gu[e] = 2.0*(B_gu[:,e*r:] @ A_gu[e*r:]) = [2I,H]`; **gate = de_gu[:768], up = de_gu[768:]** (gate PRIMA di up). Attn q/k/v/o: LoRA standard `scale*(B@A)`. `mlp.gate` (router): **full replace** da `modules_to_save` (`assert` shape identica). Ogni mismatch shape → `SystemExit` esplicito (no corruzione silenziosa).
- **Args**: `--check` (dry-run: processa solo layer 0, stampa norme `||d||/||W||` e si ferma, NON scrive).
- **Verifica fatta**: norme delta `0.0087`/`0.0093` (gate/up layer0 expert0) — sanity check superato.
- **Lancio dry-run**: `python manual_merge.py --check` → **Lancio vero**: `python manual_merge.py`.
- **Output**: 16 shard bf16 in `/workspace/qwen3-bonusx-merged/` + copia di config/tokenizer/index. Sentinel `/root/MANUAL_MERGE_DONE`. → **risultato in `D:\models\qwen3-bonusx-merged\` (16 shard, integrità verificata, ~57GB)**.

### `merge_manual_full.sh` — orchestratore merge→GGUF (catena completa)
- **Cosa fa**: (1) `python manual_merge.py`; (2) clona `llama.cpp` + reqs; (3) `convert_hf_to_gguf.py` merged → `qwen3-bonusx-f16.gguf --outtype f16`; (4) build `llama-quantize` (`-DGGML_CUDA=OFF`); (5) quantize → `Qwen3-30B-A3B-bonusx-Q4_K_M.gguf Q4_K_M`. Setta `HF_HOME=/workspace/hf`, droppa `/root/ALL_DONE`.
- **Lancio (sul pod, sopravvive alla sessione)**: `setsid bash /workspace/merge_manual_full.sh > /workspace/merge.log 2>&1 &`
- **NOTA**: localmente `llama-quantize.exe` è già in `C:\Users\imanu\llama` (via memoria) → il GGUF Q4 finale si può fare anche in locale dal merged senza il pod.

### Altri script di merge (SUPERATI, tenuti per storia)
`merge_v2.py` + `merge_v2.sh`, `merge_gguf.sh`, `go.sh`, `run_ft.sh`, `fix_and_train.sh` — tentativi/orchestratori precedenti (merge automatico peft rotto, training). `inspect_base.py` = utility che stampa shape/pattern delle chiavi `layers.0.mlp` del base (per verificare la struttura per-expert prima del merge). **Non servono per i prossimi passi**, ma documentano la struttura pesi.

## 4.3 Dati / input

- **`raft_eval.jsonl`** — i **152 held-out** (formato chat `messages`: `[0]`=system, `[1]`=user, `[2]`=gold JSON). Sul pod in `/workspace/raft_eval.jsonl`. **Originale locale**: `C:\Users\imanu\source\repos\bonus-kb\bonusx-kb\retrieval\ft\raft_eval.jsonl`.
- **`raft_train.jsonl`** — 1299 esempi di training (86% con vicini `promo_recall`, 14% senza).

## 4.4 Modelli e risultati in `D:\models\`

### Adapter e modelli
- **`D:\models\qwen3-bonusx-lora\`** — adapter QLoRA (r=32 + router `mlp.gate` full-train, aux-loss OFF). `adapter_model.safetensors` **4.00GB** (4004598352 byte) + `adapter_config.json`, `chat_template.jinja`, tokenizer. train_loss **0.418**, eval token-acc **94.5%**.
- **`D:\models\qwen3-bonusx-merged\`** — merged bf16, **16 shard** `model-0000N-of-00016.safetensors` (~57GB) + `model.safetensors.index.json`, config, tokenizer, vocab, merges. Integrità verificata. **Questo è il modello da cui fare GGUF Q4 e deploy locale.**
- **`D:\models\qwen3-235b\`** — contiene solo sottodir `Q3_K_M` (vuota) — placeholder, il 235B GPTQ-Int4 vero è ancora sul pod/bloccato.
- **`D:\models\Q3_K_M\`** — vuota (placeholder GGUF).
- **`D:\models\.cache\`** — cache HF.

### Risultati JSON (numeri ESATTI)

**STEP E — qualità per-campo (152 held-out, thinking OFF), `parse_fail=0` in entrambi:**

| campo | base (`eval_base.json`) | ft (`eval_ft.json`) | Δ |
|---|---|---|---|
| technique | 63.8% | 71.1% | +7.3 |
| variance | 71.7% | 82.2% | +10.5 |
| **validity** | **0.0%** | **0.0%** | campo mal-definito (audience non nel testo) |
| cap_eur | 77.6% | 83.6% | +6.0 |
| rollover_x | 43.4% | 71.7% | **+28.3** |
| cashback_pct | 69.1% | 80.3% | +11.2 |
| stake_min_eur | 66.4% | 87.5% | **+21.1** |

Media 6 campi (escl. validity): base **65.3%** → FT **79.4%** (**+14pt**). FT vince su tutti. La confusion matrix `technique` è dentro i due JSON.

**STEP F — router concentration (`stepf_base.json` / `stepf_ft.json`)** — E=128, topk=8, 48 layer, ~130k token:
- `mean_committed_fraction@0.95`: base **0.506** → ft **0.572**
- `mean_committed_fraction@0.9`: base 0.406 → ft 0.461; `@0.8`: base 0.286 → ft 0.326
- `mean_n_eff`: base **49.9** → ft **57.1**
- → **FT DISPERDE il routing** (N_eff SALE, cf sale): ipotesi "FT concentra" FALSIFICATA (coerente con ReMoE). È il **dominio** a concentrare (cf@0.95 0.51 su dominio vs ~66% generico).
- Ranking `experts_by_mass_asc` per layer salvato dentro → input di `prune_validate.py --maskfile`.

**STEP F+ pruning K50 freddi (`eval_prune50.json`)** — k=50, `parse_fail=0`, `overall`=**0.5714** (57.1%) — near-lossless vs base full 56.0% → **64/128 expert parcheggiabili sul dominio**. (Per-campo: technique 70.4%, variance 75.7%, rollover 44.1%, stake 57.9%.)

**STEP F+ per-neurone (`subexpert_base.json` / `subexpert_ft.json`)** — I=768, ~5842/5915 slot expert attivati:
- `neuron_n_eff_over_I`: base **88.5%** (679.5/768) → ft **89.0%** (683.3/768)
- neuroni **diffusi** in entrambi → sub-expert/per-neuron parking rende poco.

---

# 5. RIGORE PAPER & PROSSIMI PASSI

## 5.0 Dove siamo (baseline da cui ripartire)

Tutti i risultati 30B sono **misurati e salvati** (JSON in `D:\models\`). Numeri esatti già ottenuti, da NON rifare:

- **Qualità per-campo (STEP E, 152 held-out, thinking OFF)**: media base **65.3% → FT 79.4% (+14pt)**. Per campo: technique 63.8→71.1, variance 71.7→82.2, cap_eur 77.6→83.6, rollover_x +28, stake +21. `validity` **0%/0%** (campo mal-definito, `audience` non presente nel testo → **da escludere o ridefinire**, non è un risultato).
- **Routing concentration (STEP F)**: BASE `cf@0.95=0.506 / cf@0.90=0.406 / cf@0.80=0.286`, **N_eff=49.9/128**. FT `cf@0.95=0.572 / cf@0.90=0.461 / cf@0.80=0.326`, **N_eff=57.1**. → **FT DISPERDE** (ipotesi "FT concentra" FALSIFICATA, come ReMoE). Il DOMINIO concentra (cf@0.95 0.51 su BonusX vs 66% su prompt generici).
- **Pruning K50 frequency**: overall **57.1% vs base full 56.0% → zero degrado**. (NB: `eval_prune50.json` overall 57.1% è l'accuracy-per-campo del pruned, non confondere con N_eff 57.1 di STEP F: stesso numero, metriche diverse.)
- **Per-neuron (sub-expert)**: neuroni DIFFUSI, base N_eff 679.5/768 = **88.5%**, FT 89.0% → parking sub-expert rende poco.

**Il grosso buco per la pubblicabilità: manca l'intero blocco di CONTROLLI.** Finora è stato misurato SOLO il pruning frequency (una selezione, un K, un dominio). Un reviewer lo demolisce senza i controlli sotto.

## 5.1 Controlli mancanti — priorità e disegno esatto

### 5.1.1 CONTROLLO RANDOM (il più importante — senza questo il risultato NON vale)
Prunare 50% expert **a caso** e confrontare col frequency. Se il random regge uguale → la tesi "expert freddi prunabili" è FALSA (il modello è solo robusto al pruning). Lo script è **già pronto**: `prune_validate.py` ha il flag `--random` (con `--seed`, default 0) che maschera `n_mask = round(E*k/100)` expert casuali per layer invece dei bottom-mass.

Comandi (sul pod A100, dopo aver copiato `raft_eval.jsonl` e `stepf_base.json` come da §6):
```
python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 0 --tag prune50_rand_s0
python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 1 --tag prune50_rand_s1
python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 2 --tag prune50_rand_s2
```
(gen greedy = deterministica; la varianza random va da SEED, non da sampling → servono ≥3 seed per una media/std onesta). Output: `eval_prune50_rand_s{0,1,2}.json`, sentinel `/root/PRUNE_<tag>_DONE`. **Atteso per la tesi**: random a 50% deve degradare visibilmente più del frequency (57.1%). Se non degrada, riportarlo comunque — è il dato più importante del paper.

### 5.1.2 Gerarchia dei metodi di selezione: random < frequency < REAP-saliency
- **random**: §5.1.1.
- **frequency (massa routing)**: già fatto (`experts_by_mass_asc` in `stepf_base.json`, usato di default da `prune_validate.py`).
- **REAP-saliency** (arxiv 2510.13999, saliency = gate-value × ‖output-attivazione‖): **DA IMPLEMENTARE**. `step_f.py` oggi accumula solo la **massa di routing** (softmax topk normalizzato, hook su `mlp.gate`), NON la norma dell'output dell'expert. Serve un nuovo script (o estendere `subexpert.py`, che già intercetta `Qwen3MoeExperts.forward` e ha accesso a `inter = act_fn(gate)*up` e `down_proj`): accumulare per (layer, expert) `saliency = Σ_token routing_weight × ‖down_proj(inter)‖`, ordinare ascendente, salvare in un JSON con la stessa struttura `experts_by_mass_asc` così che `prune_validate.py --maskfile` lo consumi tal quale. Poi:
```
python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --maskfile /root/reap_saliency_base.json --tag prune50_reap
```
Il `--maskfile` di `prune_validate.py` è già parametrico (default `/root/stepf_base.json`, legge `experts_by_mass_asc` o fallback `low_mass_experts_bottom50pct`).

### 5.1.3 K multipli — curva qualità-vs-taglio, trovare il cliff
`--k` accetta qualsiasi valore. Sweep su BASE, per **frequency** e (una volta pronto) **saliency** e **random**:
```
for K in 10 25 40 50 60 70 80 90; do
  python prune_validate.py --model Qwen/Qwen3-30B-A3B --k $K --tag prune_freq_k$K
done
```
Produce la curva overall-field-acc vs K. Serve per il grafico centrale del paper (dove sta il cliff: 56% full → cerca il ginocchio). Lo stesso sweep va replicato con `--random` (3 seed) e `--maskfile <reap>`.

### 5.1.4 DOMINIO vs GENERALE (il cuore della tesi — oggi NON esiste)
Questa è **la tesi vera**: "narrow domain = più prunabile". Regge SOLO se, applicando lo stesso pruning, il **generale degrada PRIMA del dominio**. Serve:
- un **eval set generale** (MMLU o subset, o perplexity su testo generico italiano/inglese) da mettere accanto ai 152 BonusX;
- misurare, allo stesso K e stessa maschera (maschera scelta SUL DOMINIO), la degradazione su BonusX vs generale.
- Metrica pulita: **perplexity BonusX vs perplexity testo generale** al variare di K. `prune_validate.py` oggi misura solo accuracy-per-campo sul formato BonusX → **va aggiunto un ramo perplexity** (forward-only con `labels=input_ids`, niente `generate`) e un `--prompts` alternativo per il corpus generale. Atteso: la curva perplexity-generale sale ripida ben prima di quella BonusX. **Questo esperimento è da progettare da zero**, è il gap più grande verso la pubblicabilità dopo il random.

### 5.1.5 Confondenti da DICHIARARE esplicitamente nel paper (non risolvibili, ma vanno scritti)
- (a) 235B è **GPTQ-Int4**, il 30B era **bf16** → precisione diversa, non confrontare i numeri assoluti cross-modello.
- (b) eval **N=152** (piccolo) → riportare, niente over-claim; dare intervalli.
- (c) FT v1 allenato su **narrative KB curate** (spesso contengono la risposta) ≠ produzione raw_text scrapato → il **+14pt è in-distribution**, dirlo esplicito.
- (d) `validity` 0% = campo mal-definito → escluderlo dalle medie o ridefinirlo.
- (e) generazione **greedy = deterministica** → nessuna varianza da seed nella qualità; la varianza è nel set eval (e nei seed del solo controllo random).

## 5.2 235B — risolvere o archiviare (non bloccare il paper 30B)

Vedi dettaglio §3. Prossimo tentativo: (1) auto-gptq + transformers 4.x su B200 o 2xA100; (2) dequant GPTQ→bf16 per-expert; (3) vLLM logit-extraction; (4) archiviare come future-work. **Decisione operativa: il 235B NON deve bloccare il paper.** Se dopo il tentativo auto-gptq è ancora rotto → future-work e avanti.

## 5.3 Altri TODO progetto (non-paper, non perdere)

- **Produzione IA** (task #1): pod on-demand con auto start/stop dalla plancia Segnali — attualmente **spento**.
- **Prompts V3.1**: PUSHATI su `cgc-ia-pipeline` (commit `dcaa8ec`) → **l'utente deve premere PULL dalla console 8770** (io suggerisco, non scrivo — console ownership è dell'utente).
- **Recall promo LIVE**: flag `USE_PROMO_RECALL_KB=1` in `.env.local_runner`.
- **Scraping da pannello Telefoni ROTTO** → usare "Scraper Promo".
- **Training 2.0 raw_text→gold**: il FT v1 è **in-distribution** (KB curate); per produzione serve raw_text **scrapato**. Questo è anche il confondente (c) del paper → il training 2.0 lo risolverebbe.
- **Audit CIECO 205 draft Supabase**: in corso (workflow `blind_audit_wf.js`/`build_blind_wf.py` nello scratchpad), per eval Binario B.
- **Vault**: aggiungere la RunPod key (task #13) e **ruotarla** (è nel transcript).

---

# 6. RIPRENDI DA QUI

Sequenza di azioni concrete per la nuova sessione. **Piano utente = "entrambi in parallelo"**: Pod A100 (controlli 30B rigorosi) + Pod B200 (235B auto-gptq).

## 6.0 Setup pod (SEMPRE, prima gotcha killer)
1. Deploy pod via GraphQL `podFindAndDeployOnDemand` (`gpuTypeId` A100/B200, `volumeInGb:0`, `containerDiskInGb` grande, `startSsh:true`, `cloudType SECURE`). Header `User-Agent` browser o **403 Cloudflare**. Key in `C:\Users\imanu\Desktop\Runapod.txt` (**ruotarla prima**).
2. `export HF_HOME=/workspace/hf` (senza → ri-scarica 61GB sul container piccolo).
3. Lavorare su **container disk** (4–8GB/s), NON sul volume di rete (1MB/s scrittura).
4. Copiare sul pod: script scratchpad (`C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos\d9c25753-1d5b-40b0-abbc-89928fcceeca\scratchpad\`) + `raft_eval.jsonl` (sorgente `C:\Users\imanu\source\repos\bonus-kb\bonusx-kb\retrieval\ft\raft_eval.jsonl`) → `/workspace/raft_eval.jsonl` + `stepf_base.json` (da `D:\models\`) → `/root/stepf_base.json` (maskfile del pruning frequency).
5. **Orchestrazione SUL POD con `setsid`** (le catene bash locali muoiono ai confini di sessione). Prima di lanciare: `pgrep -f python` per evitare processi duplicati (chain morta + orch nuovo → OOM).

## 6.1 Ordine esperimenti 30B (Pod A100)
1. **Controllo random** K50 × 3 seed (§5.1.1) — **priorità massima**, script già pronto:
   ```
   python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 0 --tag prune50_rand_s0
   python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 1 --tag prune50_rand_s1
   python prune_validate.py --model Qwen/Qwen3-30B-A3B --k 50 --random --seed 2 --tag prune50_rand_s2
   ```
2. **Sweep K** frequency (§5.1.3) — script già pronto (loop `--k` 10/25/40/50/60/70/80/90).
3. **REAP-saliency**: implementare accumulo saliency (estendere `subexpert.py` → produrre `reap_saliency_base.json`), poi `prune_validate.py --maskfile /root/reap_saliency_base.json` a K multipli (§5.1.2). Replicare lo sweep K anche in modalità saliency e random.
4. **Dominio vs generale** (§5.1.4): procurare eval generale (MMLU/perplexity), aggiungere ramo perplexity a `prune_validate.py`, misurare le due curve. **Esperimento nuovo, il più oneroso.**
5. Consolidare tabelle/curve; scrivere §confondenti (§5.1.5).

## 6.2 In parallelo (Pod B200) — 235B
- Tentativo 235B **auto-gptq + transformers 4.x** (§3.4 Tentativo 1). Pinnare transformers 4.44/4.45.x, torch cu128 + torchvision matchato, NON far tirare transformers>=5.
- Se carica → lanciare `step_f.py` / `prune_validate.py` / `eval_quality.py` con `--model Qwen/Qwen3-235B-A22B-GPTQ-Int4` (già GPTQ-aware).
- Se rotto → tentativi 2/3 (dequant / vLLM) o **archiviare come future-work** e non bloccare il paper.

## 6.3 Poi (chiusura)
- Risolto/archiviato il 235B → **GGUF Q4 locale** dal merged: `llama-quantize.exe` in `C:\Users\imanu\llama`, sorgente `D:\models\qwen3-bonusx-merged` → deploy locale produzione.
- **Scrivere il paper** (30B con controlli rigorosi come tesi principale, 235B come scaling/future-work se non risolto).

## 6.4 Chiusura pod (SEMPRE)
- `podTerminate` via GraphQL `https://api.runpod.io/graphql` (Bearer + header User-Agent browser). Balance ~$93. Prezzi/h: A100 80G $1.49, B200 $5.89, H200 NVL $3.79 → **non lasciare pod grossi accesi**.
- Ricordare: **ruotare RunPod key + vault (task #13)**.

---

*Fine handoff. Fonte dati: sessione studio 2026-07-03, scratchpad `...d9c25753...`, risultati `D:\models\`, memoria `project_moe_aggressive_commit.md`.*

---

# 5b. NUOVA IDEA: SPEX (Speculative Prefetch of EXperts) — 2026-07-03

Spec completa in `docs/SPEX_spec.md`. Sistema di **prefetch predittivo degli expert** per far girare MoE
grossi su HW memory-constrained, nascondendo la latenza di load dietro il compute (adattato da DSpark).
Predice quali expert servono al layer L+1 (Markov+hidden state) e precarica SSD→VRAM durante il compute di L.
Il router reale non è mai bypassato → **accuratezza preservata gratis** (predice il LOADING, non il GATING).
Ipotesi core: SPEX vince sse `t_prefetch < t_compute(finestra sovrapposta)`.

**CONNESSIONE COL NOSTRO STUDIO (perché è il seguito naturale):** lo studio 30B→235B ha MISURATO le 3
premesse di SPEX — (1) expert freddi tanti (50-70% prunabili near-lossless su dominio); (2) routing
concentrato/PREVEDIBILE (cf@0.95≈0.52, N_eff≈49.9 identico 30B/235B → alto ρ → SPEX rende di più su dominio
stretto); (3) mai droppare il router (hard-drop=acc 0, validato). Abbiamo già gli hook (`step_f.py`/
`prune_validate.py`) per DUMPARE trace di routing reali → dataset per il predittore. Delta vs vecchio
verdetto MoE ("predire non batte reagire a cache≥topk"): SPEX è cross-layer + calibrato + bandwidth-aware
nel regime cache≪N (dominio). Da validare col framework rigoroso (baselines B0/B1/B2, ablation, sweep ρ e
expert_size/bandwidth → "SPEX-viable zone", correttezza SPEX≡baseline routing).

Deliverables in ordine: simulatore numpy N=8 + assert correttezza → baselines → predittore Markov+hidden →
STS calibration → scheduler+eviction+verifier → sweep/Pareto/heatmap. Incrementale, validare ogni stadio.

---

# 5c. NORD STAR CHIARITO + IDEA AFFILATA (2026-07-03, fine sessione)

**⚠️ CORREZIONE UTENTE — il vero obiettivo NON è il 30B né il FT di dominio:** far girare modelli GRANDI
(235B / DeepSeek-class) su HW ridicolo (RTX 3060 12GB), **accuratezza PIENA + veloce**, per uso GENERALE.

**Conseguenza onesta:** il pruning STATICO 50% che abbiamo misurato è un TRUCCO DI DOMINIO — funziona solo
perché il dominio stretto concentra il routing (50% freddi); su uso generale il routing è DIFFUSO (66%) →
prunare staticamente perde accuratezza. NON è la risposta al nord.

**IDEA AFFILATA DELL'UTENTE (= SPEX dinamico aggressivo):** sfruttare la DIFFUSIVITÀ invece di subirla.
- Offloadare il ~75% degli expert (non tenerne un set fisso).
- Tenere residente solo il ~25% **che sta per servire**.
- In un LOOP CONTINUO: **predire i prossimi expert chiamati → prefetcharli → evict gli altri**.
- "Prunare gli altri" = **OFFLOAD, non drop**: se la predizione sbaglia e un expert serve, lo si FETCHA
  (mai zero — hard-drop=acc 0 già FALSIFICATO). Accuratezza PIENA garantita (router mai bypassato).
- Il colpo: la diffusività UCCIDE il pruning statico ma è la RAGIONE per andare dinamici — nessun set fisso
  regge, ma se predici bene l'imminente basta una fetta piccola (25% < 50% statico), sempre fresca.

**PREDIZIONE = MATRICE DI MARKOV** (come SPEX spec §1): first-order transition sugli expert-ID precedenti,
low-rank B=W1@W2 rank r=64, COMBINATA con hidden state h_L. Ablation: Markov-only vs Markov+hidden.

**IL NUMERO CHE DECIDE TUTTO (misurabile ORA, prima di costruire):** accuratezza di predizione dei
next-called experts. Se su workload GENERALE (non solo dominio) predici ~90% dei prossimi → schema vivo
(25% residente + fetch del ~10% mancante nascosto dietro compute). Se ~50% → troppi stalli, muore.
Targetta ESATTAMENTE il regime cache≪N (25% su 235B) dove il vecchio verdetto "predire non batte reagire"
(validate_probe_olmoe, valido per cache≥top-k) NON si applica.

**PROSSIMO PASSO CONCRETO (riprendere da qui):**
1. Dumpare trace di routing per-layer top-k da Qwen3-30B-A3B E 235B, su prompt GENERALI (non solo BonusX) +
   domain, riusando gli hook `step_f.py` (mlp.gate). Salvare le sequenze di expert-ID per-layer.
2. Misurare accuratezza predizione next-expert con matrice di Markov (first-order, low-rank r=64) ±hidden:
   quanti dei top-k reali del layer L+1 predice dallo stato a L. Su generale vs dominio, per-layer.
3. Se il numero regge (~alto) → costruire il simulatore SPEX (spec `SPEX_spec.md`): predictor→scheduler
   bandwidth-aware→verifier loop→sweep t_prefetch<t_compute (SPEX-viable zone) su (expert_size, banda).
4. Se non regge → il nord "grande+accurato+veloce su 12GB" richiede altro (quant per-tier, o accettare
   lento). Ma la matrice di Markov + hidden è il primo test, cheap, da fare per primo.

Questo (5c) SUPERA il framing "pruning" delle sezioni precedenti come deliverable: il pruning statico resta
valido SOLO per la produzione BonusX di dominio; per il nord (modelli grandi generali su 12GB) la strada è
l'OFFLOAD DINAMICO PREDITTIVO (SPEX), e il primo gate e' la predicibilità Markov del next-expert.

---

# 6. STATO POD ATTUALI & LOG SESSIONE (live)

> **Cattura live: 2026-07-03 07:47 UTC.** Sezione operativa autosufficiente per riprendere e CHIUDERE lo
> studio dei controlli paper a freddo (budget token chat esaurito). NB: la vecchia sottosezione "6. RIPRENDI
> DA QUI" (righe ~495, piano generico di ripresa) resta valida come procedura; QUESTA sezione la SPECIALIZZA
> con lo stato reale dei pod RUNNING adesso. **Le sezioni 1–5c sopra NON sono state toccate.**

## 6.0 ⚠️ ALLERTA #1 — TERZO POD ORFANO che BRUCIA SOLDI

L'API RunPod ritorna **3 pod RUNNING**, non 2. Oltre ai due noti c'è un **duplicato idle** nato da un lancio
doppio di `study-30b`:

| pod id | name | GPU | $/h | SSH | stato reale |
|---|---|---|---|---|---|
| **`t4qjgnckhjpdce`** | study-30b | A100-SXM4-80GB | **1.49** | `root@216.81.245.83 -p 36073` | **ORFANO / MORTO** |

Dentro il pod orfano: **nessun** `/root/orch.sh`, **nessun** processo python, **nessun** log in
`/workspace/logs`, **nessun** marker, **GPU 0 MiB / 81920 usati**. Affittato `Fri Jul 03 2026 06:12:59 UTC`
(stessa sessione). È il gemello di `g9fyu5g9pkfsi6`: solo quest'ultimo ha ricevuto l'orchestratore, questo è
rimasto idle. **Sta bruciando $1.49/h a vuoto** (~$2.35 sprecati alla cattura). **VA TERMINATO al wakeup
insieme agli altri due.** Non l'ho terminato ora (start/stop è competenza dell'utente / job del wakeup).

## 6.1 POD 30B — `g9fyu5g9pkfsi6` — RUNNING, SANO

- **SSH:** `ssh root@154.54.102.51 -p 15939` · **A100-SXM4-80GB** · **$1.49/h** · uptime ~5405s (~1h30m alla cattura).
- **Cosa gira:** `/root/orch.sh` autonomo (PID 642, lanciato con `setsid`). Catena: download Qwen3-30B-A3B →
  `step_f` (rigenera `/root/stepf_base.json` con `experts_by_mass_asc` = ranking completo per qualsiasi K) →
  `prune_validate.py` per i tag `full / sal25 / sal50 / sal70 / rnd25 / rnd50 / rnd70` (`--random` per gli `rnd`).
  Alla cattura girava `prune_validate.py --k 50 --random --tag rnd50` (PID 1340), modello caricato, generazione 0/152.
- **Log:** `/workspace/logs/*.log`. **Marker:** `/root/D_<tag>` per ogni tag finito + `/root/POD30_DONE` a fine catena.
- **Marker presenti alla cattura:** `D_stepf, D_full, D_sal25, D_sal50, D_sal70, D_rnd25`.
  **Mancano:** `D_rnd50, D_rnd70, POD30_DONE`.
- `stepf_base.json` (74KB, con `experts_by_mass_asc`) rigenerato OK.

**step_f (30B):** `committed_fraction {0.8: 0.286, 0.9: 0.406, 0.95: 0.506}` · **N_eff 49.9**.

**overall_field_acc — RISULTATI (n=152 ciascuno):**

| tag | K | parse_fail | overall |
|---|---|---|---|
| full | 0% | 0 | **56.0%** |
| sal25 | 25% | 1 | **57.7%** |
| rnd25 | 25% | 0 | **57.8%** |
| sal50 | 50% | 0 | **57.3%** |
| sal70 | 70% | 14 | **54.7%** |
| **rnd50** | 50% | — | **IN CORSO** (0/152 alla cattura) |
| **rnd70** | 70% | — | **IN CODA** |

- **ETA:** ~13 min/tag (dai timestamp) → `rnd50`+`rnd70` finiscono ~**08:13 UTC**, ben prima del wakeup ~10:02.
  **POD30 completerà da solo** (arriverà a `POD30_DONE`).
- **Nota parser:** campo `validity` = 0.0 su TUTTI i tag (il parser fallisce sempre su quel campo — campo
  mal-definito, §2.2/§5.1.5 (d)). Non incide sul verdetto saliency-vs-random.

## 6.2 POD 235B — `xhmoaz0cj6827x` — RUNNING, ma LENTISSIMO

- **SSH:** `ssh root@216.243.220.141 -p 13575` · **B200 180GB** · **$5.89/h** · uptime ~5398s.
- **Cosa gira:** `/root/orch.sh` (PID 2363). Backend `gptqmodel` **`BACKEND.TORCH`** carica
  `Qwen3-235B-A22B-GPTQ-Int4` (~125GB, **SMOKE_OK, genera coerente**) — **QUESTA È LA SOLUZIONE al blocco
  235B di §3**: transformers 5.x fondeva gli expert e non mappava l'int4; `gptqmodel` torch-backend li carica
  **per-expert**. Catena: `step_f --gptqmodel` (FATTO) → `prune_validate --gptqmodel` per `full235 /
  sal235_50 / rnd235_50`. Alla cattura girava `prune_validate.py --gptqmodel --k 0 --tag full235` (PID 2778),
  backend `[TorchLinear]` + 32 inductor compile-worker.
- **Log:** `/workspace/logs/*.log`. **Marker:** `/root/D_<tag>` + `/root/POD235_DONE`.
- **Marker presenti alla cattura:** **solo `D_stepf`.** Mancano `D_full235, D_sal235_50, D_rnd235_50, POD235_DONE`.
- `stepf_base235.json` (145KB) generato OK.

**step_f (235B):** `committed_fraction {0.8: 0.290, 0.9: 0.417, 0.95: 0.524}` · **N_eff 49.9**
→ **concentrazione a scala IDENTICA al 30B** (0.524 vs 0.506 @0.95; N_eff 49.9 identico). **Confermato: la
concentrazione del routing NON dipende dalla scala del modello** (dato acquisito, robusto al wakeup).

**overall_field_acc 235B: NESSUNO ancora.** `full235` a **25/152** dopo ~14 min (07:27→07:41) ≈ **0.56 iter/min**.

### ⚠️ ALLERTA #2 — il 235B NON finirà entro il wakeup ~10:02 UTC
Solo `full235` richiede **~4h** a questo ritmo; poi restano `sal235_50` e `rnd235_50`. torch-backend LENTO
**come previsto nell'handoff §3.4/§3.2**. Al wakeup avrai al massimo `full235`, probabilmente nemmeno quello.
**Il confronto saliency-vs-random sul 235B con ogni probabilità NON sarà disponibile.** Decidi al wakeup se
prolungare il B200 (costoso, $5.89/h) o **chiudere accettando solo il dato step_f** (concentrazione a scala,
già acquisita e sufficiente per la tesi cross-scala).

## 6.3 API RunPod / costi (stato live)

- Endpoint GraphQL `https://api.runpod.io/graphql` + header **`User-Agent` Mozilla** + `Authorization: Bearer`: **OK**.
- **clientBalance: $80.36** (l'handoff §1 diceva ~$85; il delta è consumo pod).
- **Burn rate coi 3 pod: 1.49 + 1.49 + 5.89 = $8.87/h.** Se non spegni l'orfano: **~$1.49/h buttati**.

## 6.4 VERDETTO PRELIMINARE saliency-vs-random (30B)

Dati completi K25/K50 (K50 saliency fatto, K50 random in corso); K70 solo saliency finora.

- **K25:** rnd25 **57.8** ≈ sal25 **57.7** → **pari** (Δ +0.1 a favore del random).
- **K50:** sal50 **57.3** vs rnd50 **IN CORSO** → **dato mancante, è IL confronto chiave.**
- **K70:** sal70 **54.7** vs rnd70 **IN CODA** → **secondo confronto chiave.**

**Onestà scientifica:** finora **ZERO evidenza di cold-expert speciali** — a K25 il pruning random pareggia
il saliency. Il paper si decide su `rnd50` e `rnd70` (mancano ~26 min su POD30 alla cattura):
- se saliency **stacca** random a K50/K70 → **cold-expert reali** (tesi forte);
- se **pari** → "**MoE robusti al pruning statico**", nessun expert privilegiato (tesi debole ma onesta).

Coerente col framing §5c (Nord Star): il pruning statico è un trucco di dominio; la strada vera è l'offload
dinamico predittivo (SPEX). Il verdetto qui NON cambia il Nord Star — lo informa soltanto.

## 6.5 SCRIPTS aggiornati questa sessione

Nello scratchpad **`C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos\d9c25753-1d5b-40b0-abbc-89928fcceeca\scratchpad\`**
(stesso della sessione precedente, path storico), tutti già caricati sui pod in `/workspace`:
- `step_f.py` — ora salva `experts_by_mass_asc` + flag **`--gptqmodel`**.
- `prune_validate.py` — flag **`--random`** (controllo) + **`--gptqmodel`** + **`--k` qualsiasi**.
- `eval_quality.py`, `subexpert.py`, `manual_merge.py` — invariati (vedi §4).

## 6.6 WAKEUP SCHEDULATO ~10:02 UTC — AZIONI

1. **Ricontrolla POD30** (`g9fyu5g9pkfsi6`): dovrebbe avere `POD30_DONE` + `rnd50`/`rnd70` → **chiudi il
   verdetto saliency-vs-random** (§6.4).
2. **Valuta POD235** (`xhmoaz0cj6827x`): quasi certamente incompleto → decidi se **aspettare** (costoso) o
   **troncare** accettando solo `step_f235` (§6.2).
3. **Scarica i JSON in `D:\models\`** (vedi comandi §6.7): POD30 `/root/eval_*.json` + `/root/stepf_base.json`;
   POD235 `/root/stepf_base235.json` + eventuali `/root/eval_*235*.json`.
4. **`podTerminate` di TUTTI E TRE:** `g9fyu5g9pkfsi6`, `xhmoaz0cj6827x`, **`t4qjgnckhjpdce`** (l'orfano, §6.0).
5. Aggiorna handoff + memoria `project_moe_aggressive_commit.md` col verdetto finale. **Ruota RunPod key + vault (task #13).**

## 6.7 COMANDI DI RIPRESA (copincollabili)

**API key** (Bearer, header User-Agent browser obbligatorio per Cloudflare): `C:\Users\imanu\Desktop\Runapod.txt`.

### Leggere lo stato / i log via SSH
```bash
# POD 30B — marker, log tail, risultati parziali
ssh root@154.54.102.51 -p 15939 'ls -1 /root/D_* /root/POD30_DONE 2>/dev/null; echo ---; tail -n 40 /workspace/logs/*.log; echo ---; ls -la /root/eval_*.json /root/stepf_base.json'

# POD 30B — grep degli overall già calcolati
ssh root@154.54.102.51 -p 15939 'grep -h overall /root/eval_*.json'

# POD 235B — marker, log, progresso generazione
ssh root@216.243.220.141 -p 13575 'ls -1 /root/D_* /root/POD235_DONE 2>/dev/null; echo ---; tail -n 40 /workspace/logs/*.log; echo ---; ls -la /root/*235*.json'

# POD ORFANO — conferma che è idle (nessun processo/marker) prima di terminarlo
ssh root@216.81.245.83 -p 36073 'pgrep -af python; ls /root/D_* /root/orch.sh 2>/dev/null; nvidia-smi --query-gpu=memory.used --format=csv'
```

### Scaricare i JSON in D:\models (scp — eseguire da PowerShell locale)
```powershell
scp -P 15939 "root@154.54.102.51:/root/eval_*.json"      "D:/models/"
scp -P 15939 "root@154.54.102.51:/root/stepf_base.json"  "D:/models/"
scp -P 13575 "root@216.243.220.141:/root/stepf_base235.json" "D:/models/"
scp -P 13575 "root@216.243.220.141:/root/eval_*235*.json"    "D:/models/"   # se esistono
```

### Terminare i pod via API (Python, GraphQL Bearer + User-Agent per Cloudflare)
```python
import json, urllib.request
KEY = open(r"C:\Users\imanu\Desktop\Runapod.txt").read().strip()
POD_IDS = ["g9fyu5g9pkfsi6", "xhmoaz0cj6827x", "t4qjgnckhjpdce"]  # 30B, 235B, ORFANO
for pid in POD_IDS:
    body = {"query": "mutation($id:String!){ podTerminate(input:{podId:$id}) }",
            "variables": {"id": pid}}
    req = urllib.request.Request(
        "https://api.runpod.io/graphql",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {KEY}",
                 "User-Agent": "Mozilla/5.0"})   # <-- senza UA browser: 403 Cloudflare
    print(pid, "->", urllib.request.urlopen(req).read().decode())
```

### Verificare balance / lista pod RUNNING (Python)
```python
import json, urllib.request
KEY = open(r"C:\Users\imanu\Desktop\Runapod.txt").read().strip()
q = "query{ myself { clientBalance pods { id name desiredStatus runtime { uptimeInSeconds } machine { gpuDisplayName } } } }"
req = urllib.request.Request("https://api.runpod.io/graphql",
    data=json.dumps({"query": q}).encode(),
    headers={"Content-Type":"application/json","Authorization":f"Bearer {KEY}","User-Agent":"Mozilla/5.0"})
print(urllib.request.urlopen(req).read().decode())
```

## 6.8 COSA MANCA per chiudere lo studio dei controlli

- **[POD30, si chiude da solo ~08:13 UTC]** `rnd50` + `rnd70` → completa la tabella saliency-vs-random a K50/K70.
- **[POD235, a rischio]** `full235` / `sal235_50` / `rnd235_50` → probabilmente NON pronti al wakeup (torch-backend lento).
- **[wakeup]** scarico JSON, verdetto finale, **terminare i 3 pod**, aggiornare memoria, ruotare la key.
- **[ancora aperti dal §5.1, NON in questa run]** sweep K multipli completo, REAP-saliency vero (norma output,
  non massa), dominio-vs-generale (perplexity) — restano i gap più grossi verso la pubblicabilità.

---

*Fine sezione live 6 (cattura 2026-07-03 07:47 UTC). Sezioni 1–5c preservate integralmente sopra.*

## VERDETTO RANDOM (2026-07-03): full 56.0 | sal25 57.7=rnd25 57.8 | sal50 57.3 >> rnd50 37.3 (+20pt) | sal70 54.7. A K50 saliency STRACCIA random -> cold-expert REALI/pubblicabile. 235B pruning incompleto (torch lento), STEP F cf@0.95 0.52 scala.
## rnd70=0.0% (vs sal70 54.7) — random collassa, gap enorme a K70. TABELLA FINALE: full 56.0 | K25 sal57.7=rnd57.8 | K50 sal57.3>>rnd37.3 | K70 sal54.7>>rnd0.0. VERDETTO: pruning saliency REALE, gap cresce con K. Pod terminati.
