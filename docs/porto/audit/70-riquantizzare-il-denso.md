# 70 — Riquantizzare il denso: inventario, cancello tecnico, ricetta, verdetto

Data: 2026-08-11. Mandato: **sola lettura e conto**. Nessuna compilazione, nessun
`llama-server`, nessun `llama-quantize` eseguito. Il prodotto è questo documento.

Motore: `D:\llama-overlap` (fork llama.cpp, ramo `overlap`).
Modello: `C:\ds4-models\DS4-0731-IQ2XXS.gguf`, `86.720.111.488 B`, GGUF v3,
1.328 tensori, 62 KV, `general.architecture = deepseek4`,
`general.file_type = 19` (`LLAMA_FTYPE_MOSTLY_IQ2_XXS`), alignment 32,
tensor-data offset `5.333.824 B`.

> **Nota di provenienza**: il file ha byte per byte la stessa taglia di
> `C:\ds4-models\ds4-2bit.gguf` ispezionato il 30/7 in
> `.microbench\backboneq\NOTA.md`. L'inventario qui sotto, ricalcolato da zero
> dalla directory del GGUF, **conferma** quella nota tensore per tensore.
> Quella era però sul fork `ds4`; questa è sul fork llama.cpp, dove il
> validatore `weights_validate_layout` **non esiste** e le conclusioni sui
> cancelli vanno rifatte. È quello che fa il §3.

---

## 1. L'inventario vero, e la somma torna

### 1.1 La somma torna a 7383,67 MiB — esatta

Il buffer `CUDA0 model buffer size = 7383.67 MiB` corrisponde a
**tutti i tensori tranne (a) i 129 routed expert e (b) `token_embd.weight`**,
sommati **con l'allineamento a 128 B che `ggml_backend_alloc_ctx_tensors_from_buft`
applica a ogni tensore**:

| insieme | tensori | byte | MiB |
|---|---:|---:|---:|
| file intero (payload) | 1.328 | 86.714.775.900 | 82.697,65 |
| routed expert `ffn_{gate,up,down}_exps.weight` | 129 | 77.913.391.104 | 74.304,00 |
| `token_embd.weight` (F16 4096×129280) | 1 | 1.059.061.760 | 1.010,00 |
| **BACKBONE = resto, byte grezzi** | **1.198** | **7.742.323.036** | **7.383,6546** |
| **BACKBONE, allineato a 128 B** | 1.198 | **7.742.336.000** | **7.383,6670** |

`7.742.336.000 / 1048576 = 7383,66699…` → stampato **`7383.67`**. Coincidenza esatta.
La somma grezza darebbe `7383.65`: **è l'allineamento a 128 B che chiude il conto**,
e questo verifica due cose insieme — l'inventario *e* il modello di padding da usare
per i delta.

Quindi: **stai ragionando sull'inventario giusto**. E `token_embd` è confermato
fuori dai 7,38 GiB (i suoi 1010 MiB stanno altrove: è il motivo per cui spostarlo
ha liberato 109 MiB e non 1 GiB).

### 1.2 Il backbone per tipo

| tipo | tensori | byte | MiB | quota |
|---|---:|---:|---:|---:|
| Q8_0 | 345 | 6.598.885.376 | 6.293,188 | 85,231% |
| F16 | 358 | 1.132.283.904 | 1.079,830 | 14,625% |
| I32 | 3 | 9.308.160 | 8,877 | 0,120% |
| F32 | 492 | 1.845.596 | 1,760 | 0,024% |

Identico al conto di `backboneq` del 30/7. **Nessuna sorpresa: il backbone non è F16,
è già Q8_0 all'85%.**

### 1.3 Il backbone per famiglia, ordinato per taglia

`blk.*` = tutte le occorrenze. r4 = strati `2,4,…,42` (21); r128 = strati `3,5,…,41` (20).

| # | famiglia | tipo | dims | n | byte | MiB | % |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | `blk.*.attn_output_a.weight` | Q8_0 | 4096×8192 | 43 | 1.533.018.112 | 1462,000 | 19,800 |
| 2 | `blk.*.attn_output_b.weight` | Q8_0 | 8192×4096 | 43 | 1.533.018.112 | 1462,000 | 19,800 |
| 3 | `blk.*.attn_q_b.weight` | Q8_0 | 1024×32768 | 43 | 1.533.018.112 | 1462,000 | 19,800 |
| 4 | **`output.weight`** | Q8_0 | 4096×129280 | 1 | 562.626.560 | **536,562** | 7,267 |
| 5 | `blk.*.ffn_gate_shexp.weight` | Q8_0 | 4096×2048 | 43 | 383.254.528 | 365,500 | 4,950 |
| 6 | `blk.*.ffn_down_shexp.weight` | Q8_0 | 2048×4096 | 43 | 383.254.528 | 365,500 | 4,950 |
| 7 | `blk.*.ffn_up_shexp.weight` | Q8_0 | 4096×2048 | 43 | 383.254.528 | 365,500 | 4,950 |
| 8 | `blk.*.indexer.attn_q_b.weight` | F16 | 1024×8192 | 21 | 352.321.536 | 336,000 | 4,551 |
| 9 | `blk.*.attn_q_a.weight` | Q8_0 | 4096×1024 | 43 | 191.627.264 | 182,750 | 2,475 |
| 10 | `blk.*.attn_compressor_gate.weight` | F16 | 4096×1024 | 21 | 176.160.768 | 168,000 | 2,275 |
| 11 | `blk.*.attn_compressor_kv.weight` | F16 | 4096×1024 | 21 | 176.160.768 | 168,000 | 2,275 |
| 12 | `blk.*.attn_kv.weight` | Q8_0 | 4096×512 | 43 | 95.813.632 | 91,375 | 1,238 |
| 13 | `blk.*.ffn_gate_inp.weight` | F16 | 4096×256 | 43 | 90.177.536 | 86,000 | 1,165 |
| 14 | `blk.*.attn_compressor_gate.weight` | F16 | 4096×512 | 20 | 83.886.080 | 80,000 | 1,083 |
| 15 | `blk.*.attn_compressor_kv.weight` | F16 | 4096×512 | 20 | 83.886.080 | 80,000 | 1,083 |
| 16 | `blk.*.indexer_compressor_gate.weight` | F16 | 4096×256 | 21 | 44.040.192 | 42,000 | 0,569 |
| 17 | `blk.*.indexer_compressor_kv.weight` | F16 | 4096×256 | 21 | 44.040.192 | 42,000 | 0,569 |
| 18 | `blk.*.hc_attn_fn.weight` | F16 | 16384×24 | 43 | 33.816.576 | 32,250 | 0,437 |
| 19 | `blk.*.hc_ffn_fn.weight` | F16 | 16384×24 | 43 | 33.816.576 | 32,250 | 0,437 |
| 20 | `blk.*.indexer.proj.weight` | F16 | 4096×64 | 21 | 11.010.048 | 10,500 | 0,142 |
| 21 | `blk.*.ffn_gate_tid2eid.weight` | **I32** | 6×129280 | 3 | 9.308.160 | 8,877 | 0,120 |
| 22 | `blk.*.attn_compressor_ape.weight` | F16 | 512×128 | 20 | 2.621.440 | 2,500 | 0,034 |
| 23 | `blk.*.attn_norm.weight` | F32 | 4096 | 43 | 704.512 | 0,672 | 0,009 |
| 24 | `blk.*.ffn_norm.weight` | F32 | 4096 | 43 | 704.512 | 0,672 | 0,009 |
| 25 | `blk.*.attn_q_a_norm.weight` | F32 | 1024 | 43 | 176.128 | 0,168 | 0,002 |
| 26 | `blk.*.attn_compressor_ape.weight` | F16 | 1024×4 | 21 | 172.032 | 0,164 | 0,002 |
| 27 | `output_hc_fn.weight` | F16 | 16384×4 | 1 | 131.072 | 0,125 | 0,002 |
| 28 | `blk.*.attn_kv_a_norm.weight` | F32 | 512 | 43 | 88.064 | 0,084 | 0,001 |
| 29 | `blk.*.attn_compressor_norm.weight` | F32 | 512 | 41 | 83.968 | 0,080 | 0,001 |
| 30 | `blk.*.indexer_compressor_ape.weight` | F16 | 256×4 | 21 | 43.008 | 0,041 | 0,001 |
| 31 | `blk.*.exp_probs_b.bias` | F32 | 256 | 40 | 40.960 | 0,039 | 0,001 |
| 32 | `output_norm.weight` | F32 | 4096 | 1 | 16.384 | 0,016 | — |
| 33 | `blk.*.attn_sinks.weight` | F32 | 64 | 43 | 11.008 | 0,010 | — |
| 34 | `blk.*.indexer_compressor_norm.weight` | F32 | 128 | 21 | 10.752 | 0,010 | — |
| 35 | `blk.*.hc_attn_base.weight` | F32 | 24 | 43 | 4.128 | 0,004 | — |
| 36 | `blk.*.hc_ffn_base.weight` | F32 | 24 | 43 | 4.128 | 0,004 | — |
| 37 | `blk.*.hc_attn_scale.weight` | F32 | 3 | 43 | 516 | — | — |
| 38 | `blk.*.hc_ffn_scale.weight` | F32 | 3 | 43 | 516 | — | — |
| 39 | `output_hc_base.weight` | F32 | 4 | 1 | 16 | — | — |
| 40 | `output_hc_scale.weight` | F32 | 1 | 1 | 4 | — | — |

**Le prime tre righe da sole sono 4386 MiB = 59,4% del buffer.** Tutto il resto —
testa, shared expert, indexer, compressori, HC — è il 40,6%.

### 1.4 Fuori dal buffer CUDA0 (per contesto)

| famiglia | tipo | dims | n | byte | MiB |
|---|---|---|---:|---:|---:|
| `blk.*.ffn_down_exps.weight` | **Q2_K** | 2048×4096×256 | 43 | 30.299.652.096 | 28.896,0 |
| `blk.*.ffn_gate_exps.weight` | IQ2_XXS | 4096×2048×256 | 43 | 23.806.869.504 | 22.704,0 |
| `blk.*.ffn_up_exps.weight` | IQ2_XXS | 4096×2048×256 | 43 | 23.806.869.504 | 22.704,0 |
| `token_embd.weight` | F16 | 4096×129280 | 1 | 1.059.061.760 | 1.010,0 |

> **Da segnare**: il modello non è "IQ2_XXS" uniforme. `ffn_down_exps` è **Q2_K**.
> Conta per la ricetta (§4): una riquantizzazione mal specificata li tocca.

### 1.5 Una correzione ai numeri di partenza

Nel mandato `output.weight` è dato come «562,6 MiB». Sono **562.626.560 byte**, che
fanno **536,56 MiB**. La confusione MB/MiB vale 26 MiB — cioè ~3,9 slot — su una leva
che nel migliore dei casi ne vale poche decine. Tutti i numeri di questo documento
sono in MiB veri (`/1048576`).

---

## 2. Quanto libera ogni candidato

Convenzioni: byte **allineati a 128 B** (il modello verificato al §1.1);
1 slot cache esperti = **6,75 MiB = 7.077.888 B**; geometrie GGML
Q8_0 `34 B/32`, Q6_K `210 B/256`, Q5_K `176 B/256`, Q4_K `144 B/256`,
IQ4_XS `136 B/256`.
Tutte le famiglie candidate hanno `dim0` divisibile per 256 → nessun blocco parziale,
nessun fallback di forma.

**Base: CUDA0 = 7383,667 MiB.**

### 2.1 `output.weight` — la testa (Q8_0, 4096×129280, 536,562 MiB)

| destinazione | byte dopo | MiB dopo | delta B | delta MiB | **slot** | CUDA0 dopo |
|---|---:|---:|---:|---:|---:|---:|
| Q6_K | 434.380.800 | 414,258 | 128.245.760 | **122,305** | **18,1** | 7261,36 |
| Q5_K | 364.052.480 | 347,188 | 198.574.080 | **189,375** | **28,1** | 7194,29 |
| Q4_K | 297.861.120 | 284,062 | 264.765.440 | **252,500** | **37,4** | 7131,17 |
| IQ4_XS | 281.313.280 | 268,281 | 281.313.280 | 268,281 | 39,7 | 7115,39 |

> `Q5_K_M` e `Q4_K_M` sono **nomi di mixture**, non di tipo. Per un singolo tensore
> via `--output-tensor-type` si passa il tipo concreto (`q5_k`, `q4_k`): il codice
> chiama `parse_ggml_type`, che confronta con `ggml_type_name` — `q4_k_m` **non
> esiste** e verrebbe rifiutato (`tools/quantize/quantize.cpp:302-312`).

### 2.2 Il "primo gradino" — 169 F16 non decisionali (560,625 MiB)

`blk.*.hc_attn_fn` (43) + `blk.*.hc_ffn_fn` (43) + `blk.*.attn_compressor_kv` (41)
+ `blk.*.attn_compressor_gate` (41) + `output_hc_fn` (1) = **169 tensori**,
`587.857.920 B` F16.

| destinazione | byte dopo | MiB dopo | delta B | delta MiB | **slot** | CUDA0 dopo |
|---|---:|---:|---:|---:|---:|---:|
| Q8_0 | 312.299.520 | 297,832 | 275.558.400 | **262,793** | **38,9** | 7120,87 |
| Q6_K | 241.113.600 | 229,944 | 346.744.320 | **330,681** | **49,0** | 7052,99 |
| Q5_K | 202.076.160 | 192,715 | 385.781.760 | 367,910 | 54,5 | 7015,76 |
| Q4_K | 165.335.040 | 157,676 | 422.522.880 | 402,949 | 59,7 | 6980,72 |

Scomposto nelle due metà (perché sono ablazioni separate):

| sotto-gruppo | oggi | → Q8_0 | slot | → Q6_K | slot |
|---|---:|---:|---:|---:|---:|
| `hc_{attn,ffn}_fn` + `output_hc_fn` (87) | 64,625 MiB | 30,293 MiB | 4,5 | 38,119 MiB | 5,6 |
| `attn_compressor_{kv,gate}` (82) | 496,000 MiB | 232,500 MiB | 34,4 | 292,562 MiB | 43,3 |

> **Il "primo gradino" è per il 92% i compressori.** Gli HC valgono 4,5 slot: sono
> 86 tensori di rischio in cambio di niente. Se si fa questo gradino, si fanno i
> compressori — gli HC si lasciano stare.

### 2.3 Quello che l'inventario fa emergere e non era in lista

| candidato | tipo | n | oggi MiB | →Q8_0 slot | →Q6_K slot | →Q4_K slot | giudizio |
|---|---|---:|---:|---:|---:|---:|---|
| `attn_q_b`+`attn_output_a`+`attn_output_b` | Q8_0 | 129 | 4386,000 | — | **148,1** | 305,8 | **l'elefante** |
| `ffn_{gate,up,down}_shexp` | Q8_0 | 129 | 1096,500 | — | 37,0 | 76,4 | grosso |
| `indexer.attn_q_b` | F16 | 21 | 336,000 | 23,3 | 29,4 | 35,8 | decisionale |
| `attn_q_a`+`attn_kv` | Q8_0 | 86 | 274,125 | — | 9,3 | 19,1 | piccolo |
| `ffn_gate_inp` (router) | F16 | 43 | 86,000 | 6,0 | 7,5 | 9,2 | **il quantizer lo salta comunque** |
| `indexer_compressor_{kv,gate}` | F16 | 42 | 84,000 | 5,8 | 7,3 | 8,9 | decisionale |
| `indexer.proj` | F16 | 21 | 10,500 | 0,7 | 0,9 | 1,1 | irrilevante |

Aggregati:

| aggregato | oggi MiB | →Q8_0 slot | →Q6_K slot | →Q5_K slot | →Q4_K slot |
|---|---:|---:|---:|---:|---:|
| **tutti i 358 F16** | 1079,830 | 75,0 | 94,4 | 105,0 | 115,0 |
| **tutti i 345 Q8_0** (testa inclusa) | 6293,188 | — | 212,5 | 329,1 | 438,7 |

### 2.4 Combinazioni, e il muro

**Il muro**: 512 slot = 3456 MiB, 576 slot = 3888 MiB. Per salire da 512 a 576
servono **432 MiB**, e oggi ne restano liberi ~374. **Mancano ~58 MiB, cioè 8,6 slot.**

| ricetta | delta MiB | slot | CUDA0 dopo | arriva a 576? |
|---|---:|---:|---:|---|
| testa → Q6_K | 122,3 | 18,1 | 7261,4 | **sì**, +64 slot con 64 MiB di margine |
| testa → Q5_K | 189,4 | 28,1 | 7194,3 | sì, +131 MiB di margine |
| testa Q6_K + gradino1 Q8_0 | 385,1 | 57,1 | 6998,6 | sì |
| testa Q6_K + gradino1 Q6_K | 453,0 | 67,1 | 6930,7 | sì |
| testa Q6_K + tutti gli F16 Q6_K | 759,2 | 112,5 | 6624,4 | sì, si arriva a ~624 slot |
| tutto Q8_0→Q6_K + tutti F16→Q6_K | 2071,4 | 306,9 | 5312,3 | sì, ~818 slot |
| tutto Q8_0→Q4_K + tutti F16→Q4_K | 3737,6 | 553,7 | 3646,0 | sì, ~1065 slot |

> **Il numero che conta**: per passare 512→576 servono 432 MiB e ne hai 374.
> **La sola testa a Q6_K (122,3 MiB) copre il buco con 64 MiB di avanzo.**
> Il "primo gradino" da 169 tensori è, per questo scopo, **superfluo**.

---

## 3. IL CANCELLO TECNICO — è **APERTO**

Su questo albero il cancello **non chiude**. È la differenza sostanziale col fork
`ds4`, dove `weights_validate_layout` (`ds4.c:3144-3151`) pretendeva i tipi
dichiarati e il dispatch plain accettava solo F16/F32. Qui non c'è niente di tutto
questo: si passa dal dispatch generico di `ggml_cuda_mul_mat`.

### 3.1 Chi consuma i tensori candidati

Tutti e tre i gruppi finiscono in un **`ggml_mul_mat` normale**:

| tensore | consumatore | file:riga |
|---|---|---|
| `output.weight` | `ggml_mul_mat(ctx0, model.output, cur)` | `src/models/deepseek4.cpp:1473` |
| `hc_{attn,ffn}_fn`, `output_hc_fn` | `ggml_mul_mat(ctx0, hc_fn, flat_norm)` dentro `build_hc_pre` | `src/models/deepseek4.cpp:346` |
| `attn_compressor_{kv,gate}` | `build_lora_mm(layer.attn_comp_{wkv,wgate}, cur)` | `deepseek4.cpp:1070,1073,1085,1088` |
| `indexer.attn_q_b`, `indexer.proj` | `build_lora_mm(...)` | `deepseek4.cpp:608,630` |
| `indexer_compressor_{kv,gate}` | `build_lora_mm(...)` | `deepseek4.cpp:1137,1140` |
| `ffn_gate_inp` (router) | `build_lora_mm(lk.ffn_gate_inp, cur)` | `deepseek4.cpp:1432` |

Punto importante su `hc_*_fn`: le `ggml_view_2d` / `dsv4_view_*` che seguono lavorano
su **`mixes`**, cioè sull'**uscita F32** della `mul_mat`, non sul peso. Il peso non
viene mai visto per elemento. Nessun ostacolo strutturale alla quantizzazione.

### 3.2 L'albero di dispatch CUDA

`ggml/src/ggml-cuda/ggml-cuda.cu:2076-2116`, catena ordinata, vince il primo che
risponde sì:

```
  src1 non-F32 o dst non-F32 ............... cuBLAS
  should_use_mmvf(src0)  .. F32/F16/BF16 ... mul_mat_vec_f
  should_use_mmf(src0)   .. F32/F16/BF16 ... mul_mat_f
  should_use_mmvq(src0)  .. quantizzati .... mul_mat_vec_q      (MMVQ)
  should_use_mmq(src0)   .. quantizzati .... mul_mat_q          (MMQ)
  altrimenti ............................... cuBLAS (dequant -> F16)
```

### 3.3 I tipi di destinazione hanno tutti il kernel

| tipo | MMVQ (`mmvq.cu:1018-1154`) | MMQ (`mmq.cu:7-74`, allowlist `mmq.cu:274-301`) | `supports_op` (`ggml-cuda.cu:5573-5603`) | `to_fp16` (`convert.cu:764-820`) |
|---|:--:|:--:|:--:|:--:|
| Q8_0 (oggi) | sì | sì | sì | sì |
| **Q6_K** | sì (`mmvq.cu:1091`) | sì | sì | sì |
| **Q5_K** | sì (`mmvq.cu:1085`) | sì | sì | sì |
| **Q4_K** | sì (`mmvq.cu:1079`) | sì | sì | sì |
| Q5_0 / Q4_0 | sì | sì | sì | sì |
| IQ4_XS | sì | sì | sì | sì |
| F16 (oggi) | — (esce a `mmvq.cu:281`) | — | sì | — |

E su una **3060 (Ampere, cc 8.6)** `ggml_cuda_should_use_mmq` risponde **sì
incondizionatamente**, senza alcuna soglia su `ne11`:

```c
    if (!mmq_supported) { return false; }
    if (turing_mma_available(cc)) { return true; }      // <-- 3060 esce qui
```
(`ggml/src/ggml-cuda/mmq.cu:303-309`) — le soglie `ne11` che si leggono più sotto
sono pre-Turing o AMD, **non ci riguardano**.

Per MMVQ, il ritorno per NVIDIA è `ne11 <= MMVQ_MAX_BATCH_SIZE` con
`MMVQ_MAX_BATCH_SIZE = 8` (`mmvq.cuh:3`, `mmvq.cu:327`).

**Quindi per la testa in decode**: `ne11` = numero di posizioni di uscita.
Con la speculazione a `K` token, `ne11 = K+1`. Sotto/uguale a 8 → **MMVQ**;
sopra → **MMQ**. Entrambi esistono per Q6_K, Q5_K, Q4_K. **Nessun cambio di
cammino, nessuna caduta.**

### 3.4 E se un kernel mancasse?

Non cadrebbe comunque sulla CPU. Il fallback della CPU è deciso **solo** dalla
allowlist di tipi in `ggml_backend_cuda_device_supports_op`
(`ggml-cuda.cu:5573-5603`, 26 tipi, tutti i nostri candidati dentro). Un tipo
nella allowlist senza kernel cade su `ggml_cuda_mul_mat_cublas`, che dequantizza
in F16 nel pool e chiama cuBLAS — **più lento, ma sempre sulla GPU**.
`ggml_get_to_fp16_cuda` copre 25 tipi, compresi tutti i K-quant.

L'unico fallback su CPU di questo fork è deliberato e **non dipende dal tipo**:
`ggml-cuda.cu:5474-5492`, `MUL_MAT_ID` su buffer mapped-UVA sotto soglia di batch
con `LLAMA_MAPPED_IBRIDO`. Riguarda gli esperti, non il denso.

### 3.5 Ma c'è una mina, e non è dove la si cercava: gli `_ape`

`blk.*.attn_compressor_ape.weight` e `blk.*.indexer_compressor_ape.weight` sono
dichiarati nella tabella arch come **`GGML_OP_ADD`**:

```c
    {LLM_TENSOR_ATTN_COMPRESSOR_APE,    {LLM_TENSOR_LAYER_REPEATING, GGML_OP_ADD}},   // llama-arch.cpp:670
    {LLM_TENSOR_INDEXER_COMPRESSOR_APE, {LLM_TENSOR_LAYER_REPEATING, GGML_OP_ADD}},   // llama-arch.cpp:837
```

ma nel grafo sono consumati da **`ggml_get_rows`**
(`deepseek4.cpp:1078`, `:1093`, `:1145`). E `GET_ROWS` su CUDA accetta un insieme
di tipi **molto più stretto** di `MUL_MAT`: solo F32/F16/BF16/I32 e i quant a
blocco 32 (Q4_0, Q4_1, Q5_0, Q5_1, Q8_0) — **nessun K-quant**
(`ggml-cuda.cu:5630-5646`).

Il guaio è doppio, perché `select_weight_buft` prova l'op **dichiarata** (`ADD`),
non quella vera:
- a **Q8_0**: la prova `ADD` fallisce su CUDA (`ADD` vuole F32/F16,
  `ggml-cuda.cu:5814-5820`), il tensore viene appuntato al **buffer CPU** anche
  con offload pieno — a runtime `GET_ROWS` su Q8_0 funziona, quindi **niente
  errore**, solo 41+21 punti di frammentazione del grafo in più;
- a **Q6_K / Q4_K**: stessa collocazione su CPU **e** `GET_ROWS` li rifiuterebbe
  comunque.

Valgono in tutto **2,8 MiB** (0,4 slot). Erano già "NO" nel piano del 30/7 perché
si legge una riga per token. **Ora sono NO per un secondo motivo, strutturale.**
La ricetta del §4.5 li appunta esplicitamente a `f16`: quella riga non è
decorativa, è load-bearing.

*(È anche un bug latente dell'albero, indipendente da questa leva: la tabella arch
dichiara un'op che il grafo non usa. Vale la pena segnarlo a parte.)*

Sullo stesso registro, protetti ma da non toccare mai:
- `ffn_gate_tid2eid.weight` **deve restare I32**: `ggml_get_rows` preserva il tipo
  solo per I32 (`ggml.c:3902-3906`); qualunque altro tipo lo fa diventare F32 e
  fa scattare `GGML_ASSERT(b->type == GGML_TYPE_I32)` a `ggml.c:3900` e
  `GGML_ASSERT(ids->type == GGML_TYPE_I32)` a `ggml.c:3337`;
- `hc_*_scale` / `hc_*_base` **devono restare F32**: sono letti con
  `ggml_view_1d` a offset calcolato via `ggml_row_size(t->type, i)`
  (`deepseek4.cpp:177-183`, `:349-353`), che su un tipo a blocchi darebbe un
  offset **dentro** un blocco; e `ggml_dsv4_hc_comb` ha
  `GGML_ASSERT(scale->type == GGML_TYPE_F32)` (`ggml.c:6494-6496`).
  Oggi sono salvi solo perché sono 1-D e `tensor_allows_quantization` esce a
  `llama-quant.cpp:293`;
- il router `ffn_gate_inp` chiede esplicitamente
  `ggml_mul_mat_set_prec(logits, GGML_PREC_F32)` (`llama-graph.cpp:2052`), una
  garanzia che **MMQ/MMVQ su un src0 quantizzato ignorano**. Terzo motivo per non
  toccarlo, oltre ai due del 30/7 e all'esclusione d'ufficio del quantizzatore.

### 3.6 Verdetto del cancello

> **Per i candidati che contano — `output.weight`, `hc_*_fn`,
> `attn_compressor_{kv,gate}`, `indexer.*` — il cancello è APERTO** a Q8_0, Q6_K,
> Q5_K, Q4_K: tutti consumati da `ggml_mul_mat`/`build_lora_mm`, `ne[0]`
> divisibile per 256, nessuna vista/reshape/cast sul peso, nessun controllo di
> tipo nel loader (`check_tensor_dims` valida **solo le forme**,
> `llama-model-loader.cpp:871-899`).
>
> **Non è il cancello a fermare questa leva.** Il motivo è al §6.

Due segnalazioni raccolte strada facendo, non bloccanti:
- `GGML_TYPE_Q8_K` è nella allowlist di `supports_op` ma **non ha** né MMVQ né MMQ
  né `to_fp16`: un `src0` Q8_K farebbe `GGML_ABORT` a `mmvq.cu:1152` invece di
  cadere su cuBLAS. Oggi innocuo (Q8_K è solo tipo di attivazione).
- `extern DECL_MMQ_CASE(GGML_TYPE_Q1_0)` manca dalla lista `mmq.cuh:4174-4193`
  pur essendo istanziato: istanziazione doppia, gonfia la build, non è un bug.

---

## 4. La ricetta — e le tre trappole che la disarmano

`llama-quantize` di questo albero supporta tutte le opzioni proposte:
`--allow-requantize` (`quantize.cpp:446`), `--output-tensor-type` (`:410`),
`--token-embedding-type` (`:419` — **si chiama così, non `--token-embd-type`**),
`--tensor-type` con regex (`:428`), `--tensor-type-file` (`:432`),
`--pure` (`:448`), `--dry-run` (`:444`), `--keep-split` (`:468`),
`--prune-layers` (`:436`).

### 4.1 Trappola 1 — `COPY` è inerte, non selettivo

`COPY` mappa su `LLAMA_FTYPE_ALL_F32` e accende `params.only_copy`
(`quantize.cpp:571-573`). E la prima riga di `tensor_allows_quantization` è:

```c
    if (params->only_copy)       return false;       // llama-quant.cpp:290
```

Con `allows_quantization == false`, `llama_tensor_get_type` non viene **nemmeno
chiamato** (`llama-quant.cpp:1035-1039`), quindi `--output-tensor-type` e
`--tensor-type` sono **completamente inerti**. `COPY` produce un file identico.
Non è la strada.

### 4.2 Trappola 2 — chi non è coperto da un pattern viene requantizzato

Gli override `--tensor-type` sono consultati **solo** dentro

```c
    if (!params->pure && ggml_is_quantized(default_type)) {     // llama-quant.cpp:676
```

e chi non matcha nessun pattern finisce in `llama_tensor_get_type_impl`, cioè nella
**mixture standard del ftype di base** (`llama-quant.cpp:695-697`). Vince il **primo**
pattern che matcha, con `break` (`:681-691`).

Conseguenza operativa: il ftype di base deve essere un tipo quantizzato, `--pure`
**non** va passato, e **ogni** tensore del file deve essere coperto da un pattern —
altrimenti i 74 GiB di esperti IQ2_XXS/Q2_K vengono riquantizzati.

La via d'uscita esiste ed è pulita: se il tipo bersaglio **coincide** con quello
attuale, il tensore viene copiato grezzo, senza dequantizzare:

```c
    // If we've decided to quantize to the same type the tensor is already in
    // then there's nothing to do.
    bool quantize = cur_type != new_type;               // llama-quant.cpp:1150
```

Quindi si "protegge" un tensore **appuntandolo al proprio tipo attuale**.

### 4.3 Trappola 3 — i tre `ffn_gate_tid2eid.weight` I32 fanno abortire

Sono `6×129280` I32, 2D, finiscono in `.weight`, e **nessuna esclusione di
`tensor_allows_quantization` li prende**. Non protetti:
`ncols = 6` non è divisibile per 256 → `tensor_type_fallback` (`llama-quant.cpp:362`)
degrada Q6_K→Q8_0→**F16**; poi `llama_tensor_dequantize_impl` non sa dequantizzare
I32 e tira

```c
    throw std::runtime_error(format("cannot dequantize/convert tensor type %s", ...));  // :228
```

**Aborto rumoroso, non corruzione silenziosa** — ma la corsa muore. Vanno appuntati
a `i32` (`parse_ggml_type` accetta qualunque nome di `ggml_type_name`, quindi
`i32` è valido — `quantize.cpp:302-312`).

### 4.4 Trappola 4 — il precheck imatrix uccide la corsa vera

Questa è la peggiore, ed è **strutturale**. Nel giro preliminare:

```c
    metadata[i].requires_imatrix = tensor_requires_imatrix(tensor->name, metadata[i].target_type, ftype);
    if (params->imatrix) { ... }
    else if (metadata[i].allows_quantization && metadata[i].requires_imatrix) {
        if (params->dry_run) { will_require_imatrix = true; }
        else { ... throw std::runtime_error("this quantization requires an imatrix!"); }
    }
```
(`llama-quant.cpp:1041-1057`)

e `tensor_requires_imatrix` risponde **true per `GGML_TYPE_IQ2_XXS`**
(`llama-quant.cpp:774`). Gli 86 `ffn_{gate,up}_exps.weight` appuntati a `iq2_xxs`
hanno `allows_quantization = true` e `target_type = IQ2_XXS` → **throw**, anche se
poi al giro vero sarebbero stati copiati grezzi (`quantize == false`).
Il controllo guarda il tipo bersaglio, non se ci sarà davvero una conversione.

`ffn_down_exps` a `q2_k` è invece salvo: Q2_K richiede l'imatrix solo con
ftype `Q2_K_S` (`llama-quant.cpp:780-783`).

**Sul disco non esiste nessun file imatrix** (cercato in `C:\ds4-models`,
`D:\llama-overlap`, `D:\ds4_work`, nel repo: solo il binario `llama-imatrix.exe`
e gli script che costruiscono il *dataset*). Quindi:

- **`--dry-run` funziona oggi, senza imatrix** (il ramo `dry_run` mette solo un
  flag) e stampa la taglia finale tensore per tensore: **è la verifica da fare
  per prima**;
- **la corsa vera no.** Servirebbe (a) un imatrix vero — `llama-imatrix` su questo
  modello è fuori portata: il prefill va a 20 token/s — oppure (b) un **imatrix
  fittizio** che superi il cancello. Il loader accetta sia il formato legacy sia
  un GGUF con coppie `<nome>.in_sum2` / `<nome>.counts`
  (`common/imatrix-loader.cpp:117-158`): basta una voce qualsiasi perché
  `imatrix_data` non sia vuoto e `params.imatrix` venga valorizzato
  (`quantize.cpp:489-495`). Per i tensori con `quantize == false` l'imatrix non
  viene mai consultato. È un trucco, e sporca il GGUF con una chiave
  `quantize.imatrix.file` che mente sulla provenienza (`quantize.cpp:498-500`);
  oppure (c) una patch di una riga al precheck.

### 4.5 La ricetta, pronta

**Passo 0 — il file dei tipi.** L'ordine conta: vince il primo che matcha.
`indexer.attn_q_b` deve stare **prima** di `attn_q_b`, altrimenti se lo mangia.

`C:\ds4-models\tipi_testa_q6k.txt`:

```
indexer\.attn_q_b\.weight=f16
indexer\.proj\.weight=f16
indexer_compressor_kv\.weight=f16
indexer_compressor_gate\.weight=f16
indexer_compressor_ape\.weight=f16
attn_compressor_kv\.weight=f16
attn_compressor_gate\.weight=f16
attn_compressor_ape\.weight=f16
hc_attn_fn\.weight=f16
hc_ffn_fn\.weight=f16
output_hc_fn\.weight=f16
ffn_gate_inp\.weight=f16
attn_q_a\.weight=q8_0
attn_q_b\.weight=q8_0
attn_kv\.weight=q8_0
attn_output_a\.weight=q8_0
attn_output_b\.weight=q8_0
ffn_gate_shexp\.weight=q8_0
ffn_up_shexp\.weight=q8_0
ffn_down_shexp\.weight=q8_0
ffn_gate_tid2eid\.weight=i32
ffn_gate_exps\.weight=iq2_xxs
ffn_up_exps\.weight=iq2_xxs
ffn_down_exps\.weight=q2_k
token_embd\.weight=f16
```

25 righe che coprono i 793 tensori esposti al quantizzatore
(3 I32 + 86 IQ2_XXS + 43 Q2_K + 316 F16 + 345 Q8_0). I 492 F32 e i 1-D sono già
esclusi da `tensor_allows_quantization` (`_norm.weight`, `ggml_n_dims < 2`,
`.bias`): **non c'è nessun `.weight` 2-D F32 nel file**, verificato.

Tre righe di quel file **non sono decorative**, e toglierle rompe qualcosa:

| riga | cosa impedisce |
|---|---|
| `ffn_gate_tid2eid\.weight=i32` | senza, la corsa **aborta** con `cannot dequantize/convert tensor type i32` (§4.3) |
| `attn_compressor_ape\.weight=f16` | senza, i 41 tensori finiscono nel **buffer CPU** o rompono `GET_ROWS` (§3.5) |
| `indexer_compressor_ape\.weight=f16` | idem, 21 tensori (§3.5) |

E l'ordine `indexer\.attn_q_b` **prima** di `attn_q_b` è obbligatorio: il secondo
pattern matcherebbe anche `blk.N.indexer.attn_q_b.weight` e i 21 tensori F16
dell'indexer verrebbero riquantizzati a Q8_0 senza che nessuno se ne accorga.

**Passo 1 — dry-run (questo si può fare oggi, non scrive niente):**

```
D:\llama-overlap\build\bin\llama-quantize.exe ^
  --dry-run ^
  --allow-requantize ^
  --tensor-type-file C:\ds4-models\tipi_testa_q6k.txt ^
  --output-tensor-type q6_k ^
  --token-embedding-type f16 ^
  C:\ds4-models\DS4-0731-IQ2XXS.gguf ^
  Q8_0
```

Cosa deve stampare per essere valida:
- **una sola** riga `converting to q6_k` / `size = 536.56 MiB -> 414.26 MiB`, ed è
  `output.weight`;
- **tutte** le altre 1.327 righe nel formato `size = %8.3f MiB` senza
  `converting to` (copia grezza);
- in coda, esattamente:
  `model size = 82697.65 MiB` e **`quant size = 82575.35 MiB`**
  (sono somme di `ggml_nbytes`, cioè `86.714.775.900` e
  `86.714.775.900 − 128.245.760 = 86.586.530.140`; il **file** risultante sarà
  ≈ 86,59 GB, header e padding inclusi);
- il warning finale `will require an imatrix` — atteso, è la trappola 4.4;
- **zero** righe `not divisible by ... falling back to`.
  Se ne compare anche una, un pattern non ha coperto qualcosa.

**Passo 2 — la corsa vera** (bloccata dalla trappola 4.4 finché non c'è un imatrix):
identico al passo 1, togliendo `--dry-run`, aggiungendo `--imatrix <file>` e il
path di uscita, e mettendo il numero di thread in coda:

```
  ... C:\ds4-models\DS4-0731-IQ2XXS.gguf D:\ds4-models\DS4-0731-IQ2XXS-headQ6K.gguf Q8_0 12
```

L'uscita è su `D:` **di proposito**: vedi §4.6, `C:` non tiene i due file insieme.

Il ftype `Q8_0` in coda **non ha effetto sui tensori**, serve solo perché
`ggml_is_quantized(default_type)` sia vero e il blocco `--tensor-type` si accenda
(§4.2). Cambia solo la chiave `general.file_type` del GGUF prodotto — da tenere a
mente se qualcosa a valle la legge.

### 4.6 Spazio su disco e tempo

| voce | valore |
|---|---|
| ingresso | 86.720.111.488 B = **80,76 GiB** |
| uscita (solo testa → Q6_K) | ≈ 86.591.865.728 B = **80,64 GiB** |
| picco (i due file coesistono) | **≈ 161,4 GiB** |
| libero oggi | C: **91,3 GiB** · D: **123,4 GiB** |

> **Nessuno dei due volumi ha spazio per la coppia.** L'uscita deve andare su un
> disco diverso dall'ingresso: `in` su `C:`, `out` su `D:` (o viceversa). Con
> entrambi su `C:` la corsa muore a metà.

Tempo stimato: **35-55 minuti**, e il 99,85% è I/O, non calcolo.
- 86,6 GB da leggere + 86,6 GB da scrivere = 173 GB di traffico su disco;
- di questi, **un solo tensore** (536 MiB) viene davvero dequantizzato e
  riquantizzato: Q8_0→F32 (2,1 GB di buffer) → Q6_K. Su 12 thread sono
  **secondi**, non minuti. Tutto il resto è `memcpy` da mmap a `ofstream`;
- su NVMe a 1,5-2,5 GB/s sostenuti: 70-115 s teorici, ma la scrittura
  sequenziale di 86 GB su Windows con cache in pressione è realisticamente
  **3-6× peggio**. Da qui la forchetta.
- **RAM**: `work` viene dimensionato `nelements * 4` = 2,1 GB per la testa, più
  `f32_conv_buf` altri 2,1 GB. Circa **4,5 GiB di picco**, non un problema.

Con il "primo gradino" (169 tensori F16→Q8_0) in aggiunta, il tempo sale poco:
588 MB di dequantizzazione F16→F32→Q8_0, ancora ordine di secondi.

---

## 5. Il rischio di qualità, e il protocollo

### 5.1 Dov'è davvero il rischio

La ricetta `PESI_0731.md` è esplicita: **`AProj/SExp/Out Q8`** su un modello che
altrove è IQ2_XXS/Q2_K. La testa è a Q8_0 *apposta*. Due osservazioni, opposte:

**A favore.** La logica di mixture di llama.cpp stessa, per un file di ftype
IQ2_XXS, mette la testa a **Q5_K**:

```c
    else if (ftype == LLAMA_FTYPE_MOSTLY_IQ2_XXS || ... ) { new_type = GGML_TYPE_Q5_K; }
```
(`llama-quant.cpp:453-457`). Q6_K sarebbe quindi **più prudente** di quello che
upstream farebbe di suo su questo file.

**Contro, ed è il punto che conta qui.** `output.weight` produce i logit che il
bersaglio usa per **accettare o rifiutare i token della bozza**. Questo banco
gira in speculativa, e:
- «IL CICLO È INCHIODATO A 145 ms — tutto il t/s che resta è **p1**»;
- «**FUSO=5 batte FUSO=7**: ogni kernel fuso in più abbassa l'accordo
  bozza-bersaglio»;
- «LA RETROAZIONE BERSAGLIO → DRAFTER: qualunque cosa cambi come il bersaglio
  ricostruisce il suo stato **degrada la bozza**»; e il 10/8 il p1 si è mosso
  **non monotonamente** (0,865 → 0,808 → 0,832) al solo variare degli slot.

Cioè: **la testa è esattamente il tensore il cui output decide `p1`**, e `p1` è
l'unica leva di t/s rimasta. Una perdita di p1 dell'1% mangia da sola tutto il
guadagno della leva. E per la terza conferma a verbale, l'effetto su p1 **è
erratico: non si prevede, si misura**.

Il "primo gradino" (compressori + HC) è meno esposto sulla carta — nessuno dei
due produce direttamente un indice — ma i compressori costruiscono la KV
compressa e gli HC si accumulano per 43 strati. Indexer e router restano **NO**
per lo stesso motivo del 30/7: producono selezioni discrete (top-k delle entry KV
e top-6 degli esperti), dove un errore cambia *quali* memorie/esperti si usano,
non solo il valore. Nota che il router è comunque **saltato d'ufficio** dal
quantizzatore (`llama-quant.cpp:307`).

### 5.2 Il protocollo, pronto all'uso

Ripreso da `.microbench\backboneq\NOTA.md` §6, con l'aggiunta del gate su `p1`
che nel 2026-07-30 non era ancora in vista.

**Matrice di prova.** Per **entrambe** le famiglie di prompt deterministici della campagna:

1. congelare byte del prompt, system prompt, temperatura 0, seed 12345, ctx 150k
   e **ogni** env; registrarli in un manifest con SHA-256;
2. baseline (GGUF attuale): due processi indipendenti, max 8000 token;
   candidate (GGUF nuovo): due processi indipendenti, max 8000;
3. richiedere **determinismo interno**: i due SHA candidate devono coincidere fra
   loro. Non è richiesto che coincidano col baseline;
4. ordine bilanciato **`B-Q-Q-B`** su macchina pulita, `QUIETE=300` fra i bracci,
   **mediana** primaria. La posizione nel batch è una variabile reale;
5. conservare risposta JSON completa, HTML estratto, stderr, manifest, receipt e
   screenshot desktop/mobile;
6. affiancare il corpus NLL: 100 prompt e continuazioni deterministiche
   (`gguf-tools/quality-testing/`), con `avg_nll`, wins, first-token match e
   greedy LCP.

**Hard gate automatici sull'HTML completo.** Fallimento immediato se uno dei due
prompt non soddisfa **tutti**:

- `finish_reason=stop` entro 8000; un solo fence HTML chiuso; un solo
  `<!DOCTYPE html>`, `</head>`, `</body>`, `</html>`;
- parser HTML: zero errori fatal. Parser CSS: zero regole troncate, zero graffe
  non chiuse. Parser JS: sintassi valida;
- tutti i requisiti del prompt trasformati in assert: titolo/brand NeuraForge,
  header/nav, hero+CTA, feature cards, **esattamente 3** tier pricing, form con
  label/input/textarea/submit, footer, breakpoint responsive, validazione form.
  **La lista va generata dal testo del prompt congelato, non adattata dopo aver
  visto l'output**;
- ogni `href="#id"` risolve un id unico; ogni label `for` risolve un input;
  nessun id duplicato; zero URL `javascript:`; zero tag estranei al compito;
- rendering headless a 1440×900 e 390×844: `scrollWidth <= clientWidth+1`,
  sezioni con bounding box non vuota, zero eccezioni console; click di ogni nav
  anchor e submit vuoto producono il comportamento previsto;
- nessuna sequenza di 4 parole ripetuta tre volte di fila, nessun run di
  caratteri corrotti, nessun passaggio brusco a testo non-HTML dentro il fence.

**Rubrica 100 punti** — due valutatori ciechi rispetto a B/Q; divergenza > 10
punti va arbitrata.

| voce | punti | criterio verificabile |
|---|---:|---|
| Completezza requisiti | 30 | 3 punti per ciascuno dei 10 assert congelati; niente credito parziale |
| Validità HTML/CSS/JS | 20 | 10 parse/struttura, 5 link/label/id, 5 interazioni senza errori |
| Coerenza contenuto | 15 | brand, lingua, testi pertinenti, prezzi/feature coerenti fra sezioni |
| Layout desktop | 10 | gerarchia, leggibilità, nessuna sovrapposizione/clipping |
| Layout mobile | 10 | stessa verifica a 390×844; nav/form/tier usabili |
| Qualità visiva | 10 | cyberpunk neon coerente, contrasto e spaziatura; voto cieco 0..10 |
| Assenza degenerazioni | 5 | zero loop, glifi corrotti, frasi spezzate, filler |

**Gate di promozione**: hard gate 100% su quattro corse; score medio candidate
**≥ 90/100** su ciascuna famiglia; nessuna corsa candidate oltre **5 punti** sotto
la peggiore baseline; delta `avg_nll` **≤ +2%** sul corpus da 100 prompt.
(La soglia NLL resta una proposta, non una misura esistente.)

**Gate meccanico, separato dalla qualità.** Il candidato passa solo se **anche**:

- il buffer stampato è **`CUDA0 model buffer size = 7261.36 MiB`** con la testa a
  Q6_K (o 7194,29 con Q5_K). Se il numero non è quello, il conto del §2 è
  sbagliato e ci si ferma lì;
- **`p1` non scende oltre il rumore** rispetto al baseline, sugli stessi prompt e
  con `LLAMA_SPEC_DRAFT_TOPK=1`. **Questo è il gate che decide**, ed è nuovo
  rispetto alla nota del 30/7;
- `colpi`, `ms/ciclo` e `t/s` riportati **insieme**, mai i colpi da soli;
- la deriva del banco è **2,4%**: qualunque delta sotto il 3% va dichiarato
  **non misurato**, non "piccolo miglioramento".

---

## 6. IL VERDETTO — **non vale. Chiudere il fronte.**

### 6.1 Il conto è giusto: la leva funziona

Tutto quello che il mandato chiedeva di verificare **passa**:

- l'inventario torna al byte (§1.1);
- la testa a Q6_K libera **122,3 MiB = 18,1 slot**, e questo **basta** a portare
  512→576 (servono 432 MiB, ce ne sono 374, +122,3 = 496,3) (§2.4);
- il cancello tecnico è **aperto**: MMVQ e MMQ esistono per Q6_K/Q5_K/Q4_K, e su
  Ampere MMQ non ha nemmeno soglie di batch (§3);
- la ricetta esiste, il tool la supporta, e il `--dry-run` la può validare oggi
  senza scrivere niente (§4).

**È il valore di quello che si compra che non c'è.**

### 6.2 Gli slot sopra 512 non valgono niente — è già misurato

La curva della capienza nel regime giusto (11/8, `LLAMA_OVERLAP_ASYNC=0`, il banco
GPU-only):

| slot | t/s | colpi | Δt/s | Δcolpi |
|---:|---:|---:|---:|---:|
| 339 | 9,93 | 18,9% | — | — |
| 448 | 12,32 | 46,5% | +24,1% | +27,6 pt |
| 480 | 12,41 | 48,6% | **+0,73%** | **+2,1 pt** |
| 512 | 12,64 | 49,0% | **+1,85%** | **+0,4 pt** |
| 544 | **MORTO** | | | |

**La derivata dei colpi è già collassata a 512**: da +2,1 punti ogni 32 slot a
**+0,4**. Estrapolando, 512→576 vale **mezzo punto di colpi**, e la correlazione
colpi→t/s misurata su **349 corse è 0,20**.

E il guadagno di t/s che resterebbe sta **sotto la deriva del banco**, che è
**2,4%**: l'intero salto 448→512 (+64 slot) vale +2,60%, cioè **appena sopra il
rumore**. Il salto successivo, più piccolo, sarebbe **dentro il rumore**.
**Anche se pagasse, non lo si potrebbe dimostrare.**

### 6.3 E c'è un costo che cresce con gli slot

Lo sfratto sceglie la vittima con una **scansione sequenziale** di `ultimo[]`
(`cache_vittima`, `cache-esperti.cu:1879`). Il ramo parallelo esiste ma il
**difetto è 0** (`cache-esperti.cu:1247`, `LLAMA_CACHE_ESPERTI_SFRATTO_PAR`), e
all'ultima verifica si impiccava nel warmup: **in produzione gira la scansione
sequenziale**. Costo misurato: **0,07-0,08 ms per slot per ciclo**.

`+64 slot × 0,075 ms = +4,8 ms` su un ciclo di ~144 ms = **−3,3% di t/s**.

Contro un guadagno estrapolato di **+0,5/+1,5%**. **Il bilancio atteso è
negativo**, ed è coerente con la curva: 480→512 ha reso +1,85% netti *pagando già*
2,4 ms di scansione; il passo dopo ha meno colpi da raccogliere e la stessa
tassa.

### 6.4 Il margine di VRAM non è quello che sembra

Il log dell'11/8 dice **«512 slot, massimo che carica, 270 MiB liberi — 544
MORTO»**. Ma 32 slot sono **216 MiB**, e 216 < 270. **Sono morti con 54 MiB di
margine nominale.** Cioè il "libero" sovrastima di almeno ~54 MiB quello che è
davvero allocabile (frammentazione del pool, workspace CUDA, grafi).

Con la testa a Q6_K si arriverebbe a 576 slot con **64 MiB di margine nominale** —
cioè **appena sopra la soglia che ha già ucciso 544**. Non è un margine, è una
scommessa. Per stare tranquilli servirebbe almeno la testa a Q5_K (189,4 MiB,
margine 131) o testa+compressori (385,1 MiB, margine 327) — e a quel punto si è
riquantizzato molto di più, per comprare qualcosa che vale zero.

### 6.5 Il soffitto della versione massimalista

E la versione grossa? Il backbone è riletto al **99,843% a ogni token**: 7383,67
MiB. Su una 3060 a ~300 GB/s effettivi sono **~25,8 ms**, cioè **il 18% di un
ciclo da 144 ms**. Quindi:

| versione | MiB risparmiati | ms/token risparmiati | % del ciclo |
|---|---:|---:|---:|
| testa → Q6_K | 122,3 | 0,43 | **0,30%** |
| testa Q6_K + gradino1 Q8_0 | 385,1 | 1,35 | 0,94% |
| tutti gli F16 → Q6_K + testa | 759,2 | 2,66 | 1,85% |
| **tutto il denso → Q6_K** | 2071,4 | 7,25 | **5,0%** |
| tutto il denso → Q4_K | 3737,6 | 13,08 | 9,1% |

**Il soffitto assoluto della leva, contando solo la banda e ignorando gli slot, è
il 5% — e per prenderlo bisogna riquantizzare il 100% del denso, incluso il 63%
di attenzione che regge la qualità di un modello già a 2,44 BPW.** Sotto quella
soglia, ogni variante prudente vale meno della deriva del banco.

### 6.6 E il costo operativo non è zero

- rigenerare un GGUF da **80,6 GiB**, 35-55 minuti, **su un disco diverso**
  dall'originale perché nessuno dei due volumi tiene la coppia (161,4 GiB) (§4.6);
- la corsa vera **è bloccata** dal precheck imatrix e richiede un imatrix
  fittizio o una patch (§4.4);
- il protocollo di qualità del §5.2 è **quattro corse da 8000 token** più il
  corpus NLL da 100 prompt, più una rubrica in doppio cieco. Sulla stessa macchina
  che è già occupata.

### 6.7 La conclusione

> **Il tuo conto a spanne era giusto nel verso, ottimista nella taglia.**
> La testa a Q6_K dà **18,1 slot** (non 20-40), e i 64 slot che servono per il
> gradino 512→576 valgono **meno della deriva del banco 2,4%**, contro una tassa
> di sfratto di **−3,3%** che cresce proprio con gli slot. Il bilancio atteso è
> **negativo**, il margine di VRAM è **sotto la soglia che ha già ucciso 544**, e
> il tensore che si tocca è **quello che decide `p1`**, cioè l'unica leva di t/s
> rimasta.
>
> **Chiudere il fronte.** Non rigenerare il GGUF.

### 6.8 Se un giorno lo si riapre, si riapre così

Non per gli slot. Per la **banda**, e solo nella versione grossa: `attn_q_b` +
`attn_output_a` + `attn_output_b` (4386 MiB, il 59,4% del buffer) → Q6_K vale
**999,75 MiB = 3,5 ms/token = 2,4% del ciclo**, ed è il solo blocco abbastanza
grande da uscire dal rumore da solo. Costa il rischio di qualità più alto del
file. Prima di provarlo servono due cose che oggi non ci sono: un **imatrix vero**
e un `p1` **stabile abbastanza** da distinguere 2,4% dal rumore.

E i MiB liberati, quando ci saranno, **non vanno spesi in slot**. Vanno dove
`LLAMA_VRAM_A_FASI` già li manda: nel buffer di un ubatch grande in prefill, dove
`ub 512` vale **3,2×** — non lo 0,3% della testa.

---

## Appendice — come sono stati prodotti i numeri

Header e directory del GGUF letti con un parser scritto per l'occasione
(`inv.py` nello scratchpad di sessione): magic, versione, 62 KV, 1.328 descrittori
di tensore. **Il payload non è stato letto** — 5,3 MB su 86,7 GB.
Per ogni tensore: `elementi = prodotto(dims)`,
`byte = elementi / block_elems × block_bytes`, poi
`GGML_PAD(byte, 128)` per la somma di buffer. Le geometrie GGML usate:
F32 `4/1`, F16 `2/1`, I32 `4/1`, Q8_0 `34/32`, Q6_K `210/256`, Q5_K `176/256`,
Q4_K `144/256`, IQ4_XS `136/256`, Q2_K `84/256`, IQ2_XXS `66/256`.

Verifica indipendente della taglia di slot: un esperto per strato è
`gate 4096×2048 IQ2_XXS` + `up 4096×2048 IQ2_XXS` + `down 2048×4096 Q2_K`
= `2.162.688 + 2.162.688 + 2.752.512` = **7.077.888 B = 6,75 MiB esatti**.
Coincide col valore del mandato: la conversione delta→slot è esatta, non stimata.

Nessun file toccato tranne questo. Nessuna compilazione, nessun server,
nessun `llama-quantize` eseguito.

