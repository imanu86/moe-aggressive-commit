# Modelli + Setup Ambiente RTX 3060 12 GB

> Specifiche **verificate** da config.json / model card ufficiali (vedi citazioni in
> `01_positioning.md` e nel log di verifica). Dimensioni: fp16 ≈ `params·2 B`, int4 ≈ `params·0.55 B`.

## 1. Candidati verificati

| Modello | tot exp | top-k | shared | params (tot/att) | fp16 | int4 | fit 12GB | sparsità `s` | expert layout |
|---|---:|---:|---:|---|---:|---:|:--:|---:|---|
| **OLMoE-1B-7B-0924** | 64 | 8 | 0 | 6.9 / 1.3 B | 13.8 GB | 3.8 GB | int4 ✓ / fp16 ✗ | **0.125** | ModuleList ✅ |
| **Granite-3.1-3B-A800M** | 40 | 8 | 0 | 3.3 / 0.8 B | 6.6 GB | 1.8 GB | **fp16 ✓** | **0.20** | fused ⚠️ |
| Granite-3.1-1B-A400M | 32 | 8 | 0 | 1.3 / 0.4 B | 2.6 GB | 0.7 GB | **fp16 ✓** | 0.25 | fused ⚠️ |
| DeepSeek-V2-Lite | 64 | 6 | 2 | 15.7 / 2.4 B | 31.4 GB | 8.6 GB | int4 ✓ / fp16 ✗ | 0.094 | ModuleList ✅ |
| Qwen1.5-MoE-A2.7B | 60 | 4 | 4* | 14.3 / 2.7 B | 28.6 GB | 7.9 GB | int4 ✓ / fp16 ✗ | 0.067 | ModuleList ✅ |
| ~~Phi-3.5-MoE~~ | 16 | 2 | 0 | 41.9 / 6.6 B | 83.8 GB | 23 GB | **✗ ✗** | 0.125 | — (scartato: non entra) |

\* Qwen: i "4 shared" sono fusi in un singolo modulo `shared_expert` (4×). `s` = routed-active/routed-total.

## 2. Scelta motivata — pairing primario + sweep

### 2.1 La coppia che isola la sparsità (raccomandata)
**OLMoE-1B-7B (s=0.125)** + **Granite-3.1-3B-A800M (s=0.20)**.

Perché questa coppia è quasi un esperimento controllato:
> **Entrambi hanno `top-k = 8`.** Il numero di expert *attivi* è identico (8); cambia solo il
> **pool totale** (64 vs 40) e quindi `s`. Isola l'effetto di **n_total** (= quanti expert *potresti*
> dover cachare) a **n_active costante** — il confondente principale (R7) quasi sparisce.

In più: Granite-3B **entra a fp16 in 12 GB** → ground-truth `FULL` pulito **senza offload**.
OLMoE no (serve int4/int8 o CPU-offload degli expert per il FULL).

### 2.2 Sweep a tre punti a top-k fisso (estensione naturale)
Aggiungendo **Granite-1B-A400M (32 exp, s=0.25)** si ottiene una **sequenza a top-k=8 fisso**:

`n_total ∈ {32, 40, 64} → s ∈ {0.25, 0.20, 0.125}`

Tre punti sull'asse sparsità con `n_active` costante. I due Granite entrano a fp16. È il modo più
pulito per rispondere a *"come scala il guadagno con la sparsità?"* (Vincolo A).

### 2.3 Sweep continuo within-model (probe, non confronto)
Su **OLMoE** vario il **top-k** a parità di pesi (4 / 8 / 16, rinormalizzando i gate) → spazza `s`
**con continuità** senza confondere architetture. Non è "puro" (il modello è addestrato a top-8),
ma isola l'effetto sparsità dai confondenti architetturali. Da riportare **accanto**, non al posto,
del confronto between-model.

### 2.4 Punti ad alta sparsità opzionali (post-numeri / 5090)
**DeepSeek-V2-Lite (s=0.094, +2 shared)** e **Qwen1.5-MoE (s=0.067, +shared)** estendono l'asse
verso l'alta sparsità e aggiungono il **realismo degli shared expert** (sempre residenti → entrano
nel *floor* di VRAM, vanno scorporati dal "tagliabile"). Entrambi ModuleList → offload per-expert
facile. Tenuti come estensione perché non entrano a fp16 (FULL via offload/int4).

## 3. ⚠️ Caveat implementativo: ModuleList vs fused experts

Determina quanto è facile rendere un singolo expert "non residente" (cuore del `ResidencyManager`):

- **ModuleList** (OLMoE, DeepSeek, Qwen): `mlp.experts[i]` è un `nn.Module` separato →
  spostarlo CPU↔GPU / quantizzarlo / bypassarlo è **diretto** (`.to()`, hook, swap). ✅
- **fused / parallel** (Granite: `input_linear`/`output_linear` impacchettano *tutti* gli expert in
  tensori unici `[n_expert, …]`): rendere non-residente l'expert *i* significa **slicing del tensore
  fuso**, non spostare un modulo. ⚠️ Conseguenze per i `miss_mode`:
  - `precision-cascade`: ok (quantizzi le slice non-residenti) — il più naturale sul layout fuso.
  - `hard-drop` (mask/zero): ok (azzeri le slice).
  - `fetch-lossless`: **il più scomodo** (gather/scatter di slice su PCIe) — ma è lossless, quindi
    meno centrale per la domanda accuratezza.

→ `ResidencyManager` astrae i due layout dietro un'interfaccia `ExpertStore` (vedi
`src/msc/residency/manager.py`): backend `module_list` vs `fused_slice`.

## 4. Accesso al router (hook) — ricette verificate per modello

| Modello | Modulo gate | `output_router_logits`? | Ricetta hook |
|---|---|---|---|
| OLMoE | `model.model.layers[i].mlp.gate` | sì (config+kwarg) | forward-hook su `mlp.gate` (raw logits, no flag) |
| Granite 3B/1B | `…layers[i].block_sparse_moe.router` | sì | forward-hook su `block_sparse_moe.router` (expert fusi → no hook per-expert) |
| DeepSeek-V2-Lite | `…layers[i].mlp.gate` (`DeepseekV2TopkRouter`) | **NO flag** | **deve** essere forward-hook su `.mlp.gate`; layer 0 è dense |
| Qwen1.5-MoE | `…layers[i].mlp.gate` (`qwen2_moe`) | sì | flag o hook; shared expert separato `mlp.shared_expert` |

> DeepSeek-V2-Lite **non espone** `output_router_logits` e non ha aux-loss integrata (strategia
> aux-loss-free) → l'hook sul `.gate` è **obbligatorio**, non opzionale. Lo schema dell'harness
> (`instrument/router_hooks.py`) usa hook ovunque per uniformità.

## 5. Setup ambiente — RTX 3060 12 GB · Ryzen 7 5800X · Windows 11

```powershell
# Python 3.10–3.12; venv consigliato
python -m venv .venv ; .\.venv\Scripts\Activate.ps1

# torch CUDA (NON da PyPI puro) — cu124 per Ada/Ampere recenti
pip install torch --index-url https://download.pytorch.org/whl/cu124

# stack
pip install -e .              # transformers>=4.47, accelerate, ecc. (vedi pyproject.toml)
pip install -e ".[quant,dev]" # bitsandbytes (wheel Windows ok da 0.43), pytest, nvidia-ml-py
```

**Vincoli e note 3060 (12 GB):**
- **transformers ≥ 4.47** necessario per `granitemoe`; OLMoE/qwen2_moe ok; `deepseek_v2` integrato
  di recente (se assente, `trust_remote_code=True` col `modeling_deepseek.py` del repo).
- **FULL ground-truth:** Granite-3B/1B → **fp16 nativo** (6.6/2.6 GB, entra). OLMoE/DeepSeek/Qwen →
  FULL = **bf16 con CPU-offload degli expert** (`accelerate` `device_map`) *oppure* riferimento
  **int8 uniforme** in VRAM. Riportiamo da quale dei due si parte (incide sul *baseline accuracy*).
- **KV cache (R6):** a 64k token la KV può diventare GB e **mascherare** il guadagno-expert.
  Misurare `VRAM_kv` e `VRAM_expert` **separati** (`experiment/metrics.py`). Valutare anche le
  lunghezze max effettive dei modelli (context window) prima di promettere 64k/max.
- **bitsandbytes su Windows:** ok per int8/NF4 globale; il **mixed-precision per-expert** richiesto
  da `precision-cascade` non è nativo in bnb → path alternativo possibile via GGUF/llama.cpp (vedi
  `pyproject.toml [quant]`). Decidere in fase di implementazione del `precision-cascade`.
- **Disco:** download ≈ OLMoE 14 GB · Granite-3B 6.6 GB · Granite-1B 2.6 GB (· DeepSeek 31 GB se usato).

## 6. Verdetto operativo per la sessione 3060

1. **Implementare e validare la pipeline su Granite-3B-A800M** (entra fp16 → FULL pulito, niente
   offload da debuggare): è il banco di prova più semplice.
2. **Aggiungere OLMoE** come punto ad alta sparsità (e per confrontarsi con SpecMD, che lo usa).
3. **Granite-1B** come terzo punto a top-k=8 fisso, quasi gratis (modello piccolo).
4. DeepSeek/Qwen → rimandati al post-numeri / 5090 (alta sparsità + shared expert).
