# HANDOFF 4 — ESECUZIONE fine-tuning (riprendi da QUI) — 2026-07-02

> Continua `HANDOFF_3_taxonomy_v3_ft.md` (stato ecosistema) + memory `project_moe_aggressive_commit.md`.
> Questo doc = **workflow passo-passo per finire il fine-tuning**, da dove ci siamo fermati.
> Tutto il resto (tassonomia V3.1, retrieval, DB, dropdown) è FATTO E LIVE — vedi HANDOFF_3.

## STATO ESATTO AL MOMENTO DELLO STOP
- **Dataset RAFT pronto e verificato** in `C:\Users\imanu\source\repos\bonus-kb\bonusx-kb\retrieval\ft\`:
  `raft_train.jsonl` (1299) · `raft_eval.jsonl` (152) · `REPORT.md`. Anti-leakage OK (split per cluster
  di near-dup; 0 cloni cross-split a 150-char, 0 Jaccard≥0.6). Formato chat "messages" gold V3.1.
- **Kit training pronto** stessa cartella `ft/`: `pod_setup.sh`, `train_qlora_pod.py`, `eval_extract.py`,
  `FT_RUNBOOK.md`, `build_raft_dataset.py`. **LEGGI `FT_RUNBOOK.md`: ha i comandi pod-side dettagliati.**
- **Pod RunPod CONFIGURATO ma NON deployato.** Console: `https://console.runpod.io/deploy`.
  Saldo account **$25** (sufficiente; il run costa ~$6-9). Chrome = **Browser 1 (Windows)**,
  deviceId `4b36f728-6f70-4115-a239-e6f6ac8eb6e0` (usa Claude-in-Chrome → select_browser con quel deviceId).
  Config impostata: nome `qwen3-bonusx-ft`, template **Runpod Pytorch 2.8.0**
  (`runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`), **1× A100 SXM 80GB $1.49/hr**, GPU count 1, On-Demand.
  ⚠️ **STORAGE ANCORA AI DEFAULT (container 30 / volume 50) — VA CAMBIATO prima del deploy:
  container disk 50 GB, network volume 250 GB** (servono per i 61GB modello + merged + GGUF).
  ⚠️ Il form RunPod **si RESETTA a ogni refresh pagina** → riconfigurare tutto in un colpo.
- **SSH key già salvata sull'account RunPod** ("Public key updated"). Chiave sulla workstation:
  priv `~/.ssh/id_ed25519`, pub `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBemeSIwxUJLebRyiUq2mM5fQ7Iqzuo6fG35k2OOBFqt imanu-workstation-runpod`.

## WORKFLOW (ordine esatto)

### STEP A — deployare il pod
Due strade (preferisci la 2 se la key RunPod è nel vault: il browser-form si resetta ed è fragile):
1. **Browser** (Claude-in-Chrome, Browser 1 Windows): apri `console.runpod.io/deploy`, riconfigura in
   UN batch (il refresh resetta): nome `qwen3-bonusx-ft` → cerca GPU "A100" → tab **All** → click **A100 SXM**
   ($1.49) → Storage: container disk **50**, network volume **250** → **Deploy Pod** (in fondo). Il saldo
   $25 basta (niente più popup "add funds"). NB: se ricompare il box "SSH key not configured" la chiave è
   comunque salvata sull'account, ignoralo o ri-incollala.
2. **RunPod API/CLI** (più robusto): cerca una `RUNPOD_API_KEY` nel vault (`C:\Users\imanu\.cgc\`, decrypt
   vedi cgc-infra SYSTEM_MAP §13; grep `important.txt` per "runpod"). Se c'è → `runpodctl` o GraphQL
   `podFindAndDeployOnDemand` (gpuTypeId "NVIDIA A100 80GB PCIe"/"A100 SXM", volumeInGb 250, containerDiskInGb 50,
   imageName runpod/pytorch:..., ports "22/tcp", volumeMountPath /workspace).

### STEP B — connettersi + caricare il kit
- Dal pod (console → Connect → SSH over exposed TCP): `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519`.
- Upload (da workstation, cartella `retrieval/ft/`):
  `scp -P <PORT> -i ~/.ssh/id_ed25519 pod_setup.sh train_qlora_pod.py eval_extract.py raft_train.jsonl raft_eval.jsonl root@<IP>:/workspace/`

### STEP C — training (sul pod, ~1-2h)
```
cd /workspace && bash pod_setup.sh        # deps + download Qwen3-30B-A3B (~61GB, HF_HOME=/workspace/hf)
python train_qlora_pod.py --out /workspace/qwen3-bonusx-lora
```
Controlli: log "router/gate: ~48" (router in training); assert blocca l'aux-loss load-balancing (NON attivarla).
QLoRA r=32 attn+MLP, `mlp.gate` full-train, 3 epoche, lr 1e-4, batch eff 16, cutoff 4096, seed 42.

### STEP D — merge + GGUF (sul pod) → scarica solo il Q4
Istruzioni in coda a `pod_setup.sh`: merge LoRA+router → `convert_hf_to_gguf.py` → `llama-quantize Q4_K_M`.
Scarica **solo** `Qwen3-30B-A3B-bonusx-Q4_K_M.gguf` (~18.6GB) in `D:\models\`.

### STEP E — eval qualità FT-vs-base (la vittoria "garantita")
`eval_extract.py` per-campo su `raft_eval.jsonl`:
- baseline (locale, modello prod :8080): `python eval_extract.py --base-url http://127.0.0.1:8080/v1 --tag base`
  (si può fare ANCHE PRIMA/durante il training — è indipendente).
- FT (GGUF nuovo su llama-server locale, o vLLM sul pod): `--tag ft`. Confronta `eval_base.json` vs `eval_ft.json`
  (technique/variance/validity/cap_eur/rollover_x/cashback_pct/stake_min_eur + confusion matrix technique).

### STEP F — L'ESPERIMENTO aggressive-commit (la domanda vera)
Col **merged HF bf16** (sul pod, o scaricato): coverage/probe FT-vs-base sugli STESSI prompt BonusX reali.
Script esistenti repo `moe-aggressive-commit`: `scripts/build_qwen3_memmap.py` + `scripts/validate_probe_qwen3.py`
(memmap base già su `D:/qwen3_memmap`). Metriche: `committed_fraction@θ{0.8,0.9,0.95}` + `N_eff` per layer.
Baseline nota: Qwen3 128exp ≈ 66% @0.95. **Se FT concentra (fraction↓/N_eff↓)** → più expert su SSD →
VRAM liberata → modello più grosso o più contesto. Misurabile ANCHE SUL POD (torch c'è) senza scaricare 61GB.
⚠️ Perché è genuinamente aperta: il "no" del vecchio verdetto MoE era sul WORKLOAD, non sui PESI fine-tunati.

### STEP G — deploy locale del FT
`C:\Users\imanu\llama\.env.local_runner` → `LLAMA_CMD` punta al GGUF nuovo, STESSI flag
(`-ncmoe 28 -fa on -ctk/ctv q8_0 --no-mmap -c 16384`). Restart pulito wake-agent (attenzione zombie-env:
kill della RADICE, vedi memory §4). Rollback = ripuntare al GGUF vecchio. **SPEGNI IL POD** a fine lavoro.

## CREDENZIALI / PATH
- Vault: `C:\Users\imanu\.cgc\cgc-secrets.vault.enc` + `cgc-vault.key` (OpenSSL AES-256-CBC PBKDF2 600k;
  cmd in cgc-infra SYSTEM_MAP §13). Token Railway/Netlify/GitHub in `important.txt`. Cercare `RUNPOD` lì.
- Supabase: ref `ommcxachjukbbighzpqc` (URL NON in env → hardcodare), service-key in `C:\Users\imanu\llama\.env.local_runner`.
- Scratchpad helper vault già scritti (sessione precedente): `…\scratchpad\vault_capture.py`,
  `vault_capture_after.py` (ma lo scratchpad è per-sessione: potrebbero non esserci più → riscrivibili in 1 min).

## GOTCHAS (già pagati)
- RunPod form si resetta a ogni refresh → riconfigurare in un batch.
- HF_HOME DEVE stare sul volume (`/workspace/hf`, già in pod_setup.sh): il container disk 50GB non regge 61GB.
- flash-attn può fallire l'install → pod_setup ha fallback; se manca, in train_qlora_pod.py cambia
  `attn_implementation="flash_attention_2"` → `"sdpa"`.
- Router = `mlp.gate` (nn.Linear), NON `gate_proj` (quello è l'MLP degli expert). In LoRA: gate_proj sì (target),
  gate no (va in modules_to_save = full-train).
- Il 30B NON si allena in locale (pesi 4-bit ~15-16GB > 12GB della 3060). Training SOLO cloud, inferenza locale.

## COSA È GIÀ FATTO E LIVE (non rifare)
Tassonomia V3.1 unificata: KB (chunks V3.1 + Railway redeploy) · runner `cgc-ia-pipeline@3b2b4bf` (bilingue) ·
TS `promo-platform@254a168`+`3cadf8f` (compat + dropdown puliti) · **DB drafts backfillato 68/68** ·
Fase 4 kb_block raffinato dietro flag `USE_PROMO_RECALL_KB` OFF (shadow-run prima del flip).
Backup: `retrieval/out/chunks.jsonl.v1bak/.v2bak`, `drafts_technique_backup_2026-07-02.jsonl`.
