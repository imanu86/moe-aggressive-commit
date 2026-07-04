# Qwen3-235B-A22B vs DeepSeek-V2/V2.5 — confronto per lo studio SPEX / sub-expert

> Scopo: capire i due MoE alla scala ~235B per (a) lo studio offload/prefetch predittivo (SPEX) e (b)
> l'ipotesi di ridondanza sub-expert. **Tutti i numeri verificati su fonti primarie** (config.json, paper,
> HF card) da agenti di ricerca — non a memoria. Data compilazione: 2026-07-03.

## 1. Timeline / recency (verificata)

| Modello | Rilascio | Fonte |
|---|---|---|
| **DeepSeek-V2** (236B) | **2024-05-07** (arXiv v1) | https://arxiv.org/abs/2405.04434 |
| DeepSeek-V2.5 (merge Chat+Coder) | 2024-09-05 | https://api-docs.deepseek.com/news/news0905 |
| DeepSeek-V2.5-1210 (ultimo refresh V2) | 2024-12-10 | https://api-docs.deepseek.com/news/news1210 |
| **Qwen3-235B-A22B** | **2025-04-29** | https://qwenlm.github.io/blog/qwen3/ |

→ **Qwen3-235B è ~1 anno PIÙ RECENTE** di DeepSeek-V2. DeepSeek-V2 è il modello che introdusse **MLA** +
**DeepSeekMoE** (fine-grained + shared); Qwen3 è la generazione più recente di Qwen e **adotta** la
segmentazione fine-grained di DeepSeekMoE (ma senza shared expert).

## 2. Architettura a confronto (verificata da config.json + paper)

| Campo | **Qwen3-235B-A22B** | **DeepSeek-V2 / V2.5 (236B)** |
|---|---|---|
| Totali / attivi | 235B / **22B** | 236B / **21B** |
| `hidden_size` | 4096 | 5120 |
| `num_hidden_layers` | **94** | **60** |
| Layer MoE | tutti (decoder_sparse_step 1) | tutti tranne il **1° (dense)** (first_k_dense_replace 1) |
| **Expert routed totali** | **128** | **160** |
| **Expert attivi/token (routed)** | **8** | **6** |
| **Shared expert** | **0** ("excludes shared experts") | **2** (sempre attivi) → 6+2 = 8 attivi/token |
| `moe_intermediate_size` (dim per-expert) | **1536** | **1536** (identico!) |
| Fine-grained? | **Sì** (deepseekmoe segmentation) | **Sì** (originale) |
| Attention | **GQA** (64 Q / 4 KV, head_dim 128) | **MLA** (kv_lora_rank 512, q_lora 1536) |
| `vocab_size` | 151936 | 102400 |
| Contesto | 32K nativo / 128K YaRN | 128K (YaRN) |
| dtype / disco bf16 | bf16 / **~470 GB** (118 shard) | bf16 / **~471 GB** (55 shard) |
| Licenza | **Apache 2.0** | DeepSeek Model License (uso commerciale OK); code MIT |

**Fonti:** config.json Qwen https://huggingface.co/Qwen/Qwen3-235B-A22B/raw/main/config.json ·
config.json DS-V2 https://huggingface.co/deepseek-ai/DeepSeek-V2/raw/main/config.json ·
paper Qwen3 https://arxiv.org/abs/2505.09388 · paper DS-V2 https://arxiv.org/abs/2405.04434

## 3. Perché contano per lo studio (il punto chiave)

**Correzione a un'assunzione iniziale:** NON è vero che "Qwen usa expert grossi e DeepSeek fine-grained".
**Entrambi sono fine-grained** (`moe_intermediate_size` = 1536 identico, ~1/8 della FFN densa 12288).
La differenza MoE rilevante è **UNA**:

> **DeepSeek-V2 isola la capacità CONDIVISA in 2 shared-expert sempre attivi; Qwen3 NON ha shared-expert.**

Conseguenze per l'ipotesi di ridondanza sub-expert:
- Sul **nostro test Qwen (30B, fine-grained, no-shared)** gli expert sono risultati **quasi-ortogonali**
  (coseno ~0.004, rango pieno 128/128, 0% neuroni condivisi tra expert). Nessuna ridondanza da sfruttare.
- Su **DeepSeek** la capacità condivisa è **già estratta** nei 2 shared → i 160 routed potrebbero essere
  ancora più ortogonali (la parte comune è fuori), OPPURE restare ridondanti. **Domanda aperta, da misurare.**
- **Implicazione per la visione "gira in 8GB":** il meccanismo shared-expert di DeepSeek **è già** una forma
  della tua idea — tieni residenti i 2 shared (piccoli, sempre utili) + prefetcha i routed. Se i routed sono
  ortogonali come su Qwen, il guadagno sub-expert extra è limitato; se sono ridondanti, si può comprimere.

**Test in corso:** probe di ridondanza su **DeepSeek-V2-Lite** (16B, **64 routed + 2 shared**, stessa arch,
economico) → misura (a) coseno/rango tra i routed, (b) energia coperta dai 2 shared. Se mostra sharing dove
Qwen no → confermare su V2-236B (B200) per la coppia pubblicabile alla scala di Qwen-235B.

## 4. Disponibilità pratica + quantizzazioni (VERIFICATO — caveat importante)

**DeepSeek-V2-Lite** (`deepseek-ai/DeepSeek-V2-Lite`, verificato da config.json): 15.7B (2.4B attivi), **27 layer**,
hidden **2048**, **64 routed + 2 shared**, 6 attivi, `moe_intermediate_size` **1408** (NB: V2-236B è 1536),
MLA **senza compressione query** (`q_lora_rank: null`, a differenza del V2 full che ha 1536), ~**31 GB bf16**
(4 shard), classe `DeepseekV2ForCausalLM` (serve `trust_remote_code=True`). Esiste **AWQ** (`TechxGenus/
DeepSeek-V2-Lite-AWQ`), **NON** GPTQ/int4. → **Per la probe di ridondanza carico il bf16 via transformers** (entra in A100).

**⚠️ DeepSeek-V2 / V2.5 (236B) — quantizzazione DIFFICILE (verificato):**
- **NON esistono AWQ/GPTQ per il 236B** — l'ecosistema AutoGPTQ/AWQ **si rompe sull'architettura MLA+MoE**
  (richiesta community "GPTQ plz" senza risposta; confermato il nostro sospetto pregresso).
- Solo **GGUF** (`bartowski/DeepSeek-V2.5-GGUF`: Q4_K_M 142GB / IQ4_XS 126GB), MA **il supporto MLA in
  llama.cpp era tardivo/imperfetto** → mainline gira come MHA (KV-cache gonfiata); per MLA corretto serve
  **`ik_llama.cpp`** (fork). GGUF non è comodo per l'analisi per-expert dei pesi in numpy.
- **Conseguenza per NOI:** far girare/analizzare il V2-236B è **più ostico** di Qwen-235B (che ha GPTQ-Int4
  ufficiale). Per il probe di ridondonza alla scala piena servirebbe il bf16 471GB (troppo per una GPU) o un
  parsing dei GGUF. **V2-Lite bf16 è la via pulita** per la domanda architetturale; V2-236B pieno = lavoro extra.

**Qwen3-235B** (verificato): ~470GB bf16; **GPTQ-Int4 UFFICIALE** `Qwen/Qwen3-235B-A22B-GPTQ-Int4` (~125GB,
già usato sul nostro B200) + FP8 + GGUF ufficiali + AWQ community. Ecosistema molto più maturo (vLLM/SGLang/llama.cpp).

## 5. Caveat per un confronto onesto (da dichiarare in un paper)

1. **Recency: ~1 anno di distanza** (DS-V2 mag-2024 vs Qwen3 apr-2025) → dati di training, ricette e qualità
   di base diverse. Non attribuire differenze di ridondanza SOLO all'architettura.
2. **Shared-expert**: DeepSeek ha 2 shared, Qwen 0 → è LA variabile architetturale isolata, ma confusa con (1).
3. **MLA vs GQA**: attention diversa (non tocca gli expert, ma cambia il backbone e il footprint KV).
4. **Quantizzazione**: se confrontati in int4 (per stare in VRAM), sono quant diverse → confondente, come già
   dichiarato per il nostro 235B-GPTQ vs 30B-bf16.
5. **Scala non identica dei routed**: 160 (DS) vs 128 (Qwen) expert, 6 vs 8 attivi → il "budget di ridondanza"
   parte da popolazioni diverse.

## Verdetto
- **Più recente:** Qwen3-235B (apr-2025), di ~1 anno su DeepSeek-V2 (mag-2024).
- **Caveat principale:** la vera differenza MoE è il **shared-expert** di DeepSeek (Qwen non ce l'ha), ma è
  **confusa con 1 anno di differenza di training** → il confronto isola l'architettura solo parzialmente.
- **Rilevanza per la tua idea:** DeepSeek **implementa già** la separazione condiviso-vs-specializzato via
  shared-expert; il sub-expert-splitting sarebbe un passo oltre, e va misurato se i routed DeepSeek lasciano
  margine (probe V2-Lite in corso).

---

## Lineup DeepSeek MoE attuale (verificato mid-2026)

> Aggiornamento **2026-07-03**. Verifica su fonti primarie (config.json su HF `deepseek-ai`, api-docs.deepseek.com,
> arXiv). **Non a memoria** — ogni release ha URL. Dove un numero non è verificabile sulla fonte primaria è
> marcato esplicitamente "non verificato".

### RISPOSTA SECCA alla domanda "esiste un DeepSeek recente ~200-300B?"
**SÌ.** **DeepSeek-V4-Flash** = **284B totali / 13B attivi**, rilasciato **2026-04-24**, **open-weights MIT** su
HF (`deepseek-ai/DeepSeek-V4-Flash`, ~160 GB, 46 shard safetensors, pesi **FP8** nativi). È il **DeepSeek più
recente e più piccolo** nella fascia di Qwen3-235B-A22B — anzi, **è la generazione V4** (più nuovo di Qwen3-235B
di ~1 anno). Le altre release grandi (V3/V3.1/V3.2 = 671B, V4-Pro = 1.6T) restano oltre la fascia.

### Timeline completa dei MoE DeepSeek (verificata)

| Modello | Rilascio | Tot / Attivi | Open-weights | Fonte (URL) |
|---|---|---|---|---|
| **DeepSeek-V2** | 2024-05-07 | 236B / 21B | sì | https://arxiv.org/abs/2405.04434 |
| DeepSeek-V2.5 | 2024-09-05 | 236B / 21B | sì | https://api-docs.deepseek.com/news/news0905 |
| DeepSeek-V2.5-1210 | 2024-12-10 | 236B / 21B | sì | https://api-docs.deepseek.com/news/news1210 |
| **DeepSeek-V3** | 2024-12 (report v1 2024-12-27) | 671B / 37B | sì (MIT) | https://arxiv.org/html/2412.19437v1 · https://huggingface.co/deepseek-ai/DeepSeek-V3 |
| **DeepSeek-R1** | 2025-01 | 671B / 37B | sì (MIT) | https://arxiv.org/pdf/2501.12948 |
| DeepSeek-V3-0324 | 2025-03-24 | 671B / 37B | sì (MIT) | https://api-docs.deepseek.com/news/news250325 |
| **DeepSeek-R1-0528** | 2025-05-28 | 671B / 37B | sì (MIT) | https://api-docs.deepseek.com/news/news250528 |
| **DeepSeek-V3.1** | 2025-08-19/21 | 671B / 37B | sì (MIT) | https://technode.com/2025/08/21/deepseek-open-sources-new-v3-1-model/ |
| DeepSeek-V3.2-Exp | 2025-09-29 | 671B / 37B | sì | https://api-docs.deepseek.com/news/news251201 |
| **DeepSeek-V3.2** | 2025-12-01 | 671B / 37B | sì | https://api-docs.deepseek.com/news/news251201 · https://huggingface.co/deepseek-ai/DeepSeek-V3.2 |
| **DeepSeek-V4-Flash** | **2026-04-24** | **284B / 13B** | **sì (MIT)** | https://api-docs.deepseek.com/news/news260424 · https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash |
| **DeepSeek-V4-Pro** | 2026-04-24 | **1.6T / 49B** | sì (MIT) | https://api-docs.deepseek.com/news/news260424 · https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro |

Note: la famiglia V3 → V3.1 → V3.2 condivide lo **stesso backbone 671B/37B** (config identico, cambia solo il
post-training e, in V3.2, l'attenzione sparsa DSA). Il "685B su disco" citato per V3 include il modulo MTP (~14B).

### Tabella architetturale (da config.json su HF — verbatim)

| Campo | V2 (236B) | V3 / V3.1 (671B) | V3.2(-Exp) (671B) | **V4-Flash (284B)** | V4-Pro (1.6T) |
|---|---|---|---|---|---|
| `architectures` | DeepseekV2 | DeepseekV3 | DeepseekV32 | **DeepseekV4** | DeepseekV4 |
| Tot / Attivi | 236B / 21B | 671B / 37B | 671B / 37B | **284B / 13B** | 1.6T / 49B |
| `hidden_size` | 5120 | 7168 | 7168 | **4096** | 7168 |
| `num_hidden_layers` | 60 | 61 | 61 | **43** | 61 |
| `n_routed_experts` | 160 | 256 | 256 | **256** | 384 |
| `num_experts_per_tok` | 6 | 8 | 8 | **6** | 6 |
| `n_shared_experts` | 2 | 1 | 1 | **1** | 1 |
| `moe_intermediate_size` | 1536 | 2048 | 2048 | **2048** | 3072 |
| `first_k_dense_replace` | 1 | 3 | 3 | (n.v.) | (n.v.) |
| `vocab_size` | 102400 | 129280 | 129280 | **129280** | 129280 |
| Attention | MLA (kv_lora 512, q_lora 1536) | MLA (kv_lora 512, q_lora 1536) | MLA + **DSA** (index_topk 2048) | **hybrid CSA+HCA** (q_lora 1024, head_dim 512, kv_heads 1) | MLA-like (q_lora 1536) |
| `max_position_embeddings` | 128K (YaRN) | 163840 | 163840 | **1048576 (1M)** | 1048576 (1M) |
| dtype nativo | bf16 | fp8 | fp8 | **fp8 (e4m3)** | fp8 |

Fonti config.json (raw): V2 https://huggingface.co/deepseek-ai/DeepSeek-V2/raw/main/config.json ·
V3 https://huggingface.co/deepseek-ai/DeepSeek-V3/raw/main/config.json ·
V3.1 https://huggingface.co/deepseek-ai/DeepSeek-V3.1/raw/main/config.json ·
V3.2-Exp https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Exp/raw/main/config.json ·
V4-Flash https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/raw/main/config.json ·
V4-Pro https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/raw/main/config.json

### Chi sta ESATTAMENTE nella fascia 200-300B

| Modello | Tot / Attivi | Data | Note |
|---|---|---|---|
| DeepSeek-V2 / V2.5 / V2.5-1210 | 236B / 21B | mag–dic 2024 | vecchio (MLA + 2 shared, no fp8) |
| **DeepSeek-V4-Flash** | **284B / 13B** | **2026-04-24** | **il più recente in fascia**; gen V4, MIT, fp8 nativo, 1M ctx |

→ **Il più recente nella fascia 200-300B è DeepSeek-V4-Flash (284B, apr-2026).** Nel mezzo (giu-2024 → apr-2026)
DeepSeek NON ha pubblicato nulla in questa fascia: tutte le release intermedie (V3 famiglia, R1) sono **671B**.
V4-Flash è quindi il **diretto paragone di taglia** a Qwen3-235B-A22B, ma **una generazione più nuovo**.

### Disponibilità pratica — V4-Flash (284B)

- **Pesi ufficiali**: `deepseek-ai/DeepSeek-V4-Flash`, **FP8 nativo (e4m3)**, ~**160 GB** su disco (46 shard
  safetensors). Non c'è un bf16 ufficiale separato: il modello nasce fp8 (come V3). https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash
- **Mirror / quant**: `unsloth/DeepSeek-V4-Flash` (mirror + GGUF), `bartowski/DeepSeek-V4-Flash-GGUF`.
  Q4_K_M ≈ entra in **1× 80GB** o 2× 48GB (fonte community, non ufficiale). Esistono build **AWQ/INT4 ~80 GB**
  (community, ~5% perdita — **non verificato su repo ufficiale**). https://huggingface.co/unsloth/DeepSeek-V4-Flash · https://huggingface.co/bartowski/DeepSeek-V4-Flash-GGUF
- **Attenzione**: architettura nuova (`DeepseekV4ForCausalLM`, hybrid CSA+HCA) → il supporto in llama.cpp è
  **sperimentale** (fork antirez `llama.cpp-deepseek-v4-flash`). Per l'analisi per-expert dei pesi va parsato
  l'fp8; non esiste (ancora) GPTQ-Int4 ufficiale come per Qwen3-235B. https://github.com/antirez/llama.cpp-deepseek-v4-flash

### Caveat / cose NON verificate su fonte primaria
- Il **conteggio esatto tot/attivi** (284B/13B, 1.6T/49B) viene dai **model card + api-docs ufficiali**, non
  da un campo `num_parameters` nel config.json (che non lo espone). L'aritmetica dal config (256 exp × 2048 ×
  hidden 4096 × ~42 layer MoE) è **coerente** con ~284B tot e ~13B attivi, ma è una stima di controllo, non un
  dato pubblicato nel config.
- Il model card V4-Flash descrive l'attenzione come **CSA+HCA / "Manifold-Constrained Hyper-Connections (mHC)"
  / optimizer Muon / 32T token**: dettagli dal card, **paper arXiv V4 non ancora localizzato** al 2026-07-03.
- Le dimensioni delle quantizzazioni GGUF/AWQ specifiche (GB per livello) provengono da repo/blog **community**,
  non dai repo ufficiali `deepseek-ai` → trattare come indicativi.

### Verdetto per lo studio (SPEX / pruning)
- **Esiste** e **è open-weights** un DeepSeek recente in fascia Qwen-235B: **V4-Flash 284B/13B (MIT, apr-2026)**.
  Come coppia di scala per Qwen3-235B è **più pulito** (stessa generazione ~2025-26) del vecchio V2-236B.
- **MA** V4-Flash **cambia troppe variabili insieme** rispetto a V2/Qwen: nuova attention (CSA+HCA, non MLA
  classica), 256 routed + **1** shared (non 2), 1M ctx, fp8 nativo, arch `DeepseekV4` non supportata dai tool
  standard. Per un confronto architetturale **controllato** sul meccanismo shared/sub-expert, V2-Lite/V2-236B
  restano più maneggevoli; V4-Flash è il riferimento "stato dell'arte di pari taglia" ma con più confondenti e
  tooling immaturo.
