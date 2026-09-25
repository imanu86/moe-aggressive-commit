# Runtime elastico per Qwen3.6-35B-A3B (qwen35moe) — 25 settembre 2026

Obiettivo dell'utente: il MoE Qwen piu' piccolo che esiste (35B-A3B), con una testa MTP buona e gli esperti
che escono dalla VRAM da soli quando il desktop la occupa, come il runtime elastico del daily (M2).

## Cosa si e' fatto

Il macchinario elastico di M2 (cache esperti in VRAM ridimensionata a caldo, esperti letti dalla GPU a
domanda, area di lavoro dinamica) e' generico nel grafo (`build_moe_ffn` in `llama-graph.cpp`) e nella cache
(`llama-moecache.cpp`). Era chiuso a `qwen4exp` in quattro punti di `llama-context.cpp`, due dei quali
sarebbero andati in crash se si fosse solo tolta la guardia (cast a `llama_memory_hybrid_idx`, che esiste
solo in qwen4exp). Patch: [`q36-qwen35moe.patch`](q36-qwen35moe.patch); i percorsi qwen4exp restano identici.

1. niente `llama_moe_cache_init` per il contesto MTP di qwen35moe (col DEMAND acceso la seconda init lanciava
   «one inference context per process» e il server non partiva);
2. area di lavoro dinamica ammessa anche per `LLM_ARCH_QWEN35MOE`;
3. `limit_reserve_kv` sulla sola cache d'attenzione della memoria ibrida normale;
4. nel decode `used` letto da `llama_memory_hybrid`; la cache `idx_` solo per qwen4exp.

Build a overlay ([`build_q36_overlay.py`](build_q36_overlay.py)): ricompila solo `llama-context.cpp` coi
flag O2 di Codex, ricollega `llama.dll` sui 187 oggetti O2 in sola lettura (SHA verificati prima e dopo),
copia il resto da `runtime-m2`. Laboratorio fuori da git: `D:\ds4_work\elastico_q36`, runtime in
`runtime-q36` (`llama.dll` 0a718110…, `ggml-cuda.dll` di M2 a8e6d2a9…). **Daily intatto**:
`bin_elastico_m2`, `.bat` del Desktop e modelli verificati invariati dopo le prove.

Ambiente: solo manopole generiche del preset di produzione. Vanno tolte le `QWEN4EXP_*`
(`QWEN4EXP_ATTN_MAPPED=1` fa lanciare la KV di ogni arch diversa da qwen4exp); `QWEN_PREFETCH_EXPERTS` e'
inerte con 256 esperti (`ggml-backend.cpp:1715` vuole 512); `QWEN_PREFILL_UBATCH_DEEP` e' tarata su
qwen4exp. La verifica MTP deve restare entro 3 righe (`--spec-draft-n-max` <= 2, `LLAMA_MOE_CACHE_BATCH=3`).

## Misure (banco P0, profilo `fumo`, greedy seed 1234, ragionamento acceso, porta 8113 isolata)

Stessa macchina, stesso momento: il desktop occupava 5,9 GB di VRAM. Q4_K_M di ggml-org, testa MTP
separata Q4_0 di ggml-org, bozza n-max 2. Preset in [`../banco_35b/`](../banco_35b/).

| braccio | L01 libero | S01 riassunto JSON | accettazione L01 / S01 | carico |
|---|---:|---:|---:|---:|
| A0 upstream b10734, `-fit on` | 23,35 t/s | 27,24 t/s | 64,0% / 88,6% | 67 s |
| **B1 runtime-q36 elastico** | **57,60 t/s** | **60,05 t/s** | 59,0% / 83,2% | 15,5 s |

B1: cache partita da 24 slot, cresciuta a 67 sul budget, scesa da sola a 63 quando si e' caricata la testa
MTP (4,46 GB di esperti, 25% dei 256 per strato); esperti della testa in `CUDA0_Mapped` (432 MiB); GPU al
96%. Testi sani in entrambi; divergono per numerica (L01 dopo 1.689 caratteri, S01 dopo 158), come atteso
fra piazzamenti e kernel diversi. Cartelle: `D:\ds4_work\banco_35b_run\20260925_210857_*` (A0) e
`…_211944_*` (B1).

## Non ancora provato

Contesto lungo (32k/131k), pressione di VRAM a meta' generazione (resize sotto carico), testa MTP Q8_0 o
interna al file, quantizzazioni IQ3 (piu' slot a parita' di VRAM), deposito RAM (`LLAMA_MOE_RAM_LAYERS`),
lanciatore per l'uso quotidiano.
