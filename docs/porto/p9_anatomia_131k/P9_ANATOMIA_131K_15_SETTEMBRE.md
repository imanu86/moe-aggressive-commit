# P9 · anatomia del token singolo di decode a 131k — 15 settembre 2026

Cella **diagnostica**. Domanda: dove vanno i **37,9 ms** che costa un token di decode al punto
operativo dell'utente (contesto ~131k, KV 250k, MTP spento), e quale leva sul token singolo ha il
tetto più alto.

Nessun sorgente del motore è stato modificato, nessuna build è stata fatta, nessun commit.
`bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, il lanciatore quotidiano, i modelli e
lo snapshot P0 non sono stati toccati (si è solo **letto** l'albero `D:\ds4_work\p8_work\source` e
l'**intestazione** dei tre shard del GGUF: i pesi non sono stati letti).
Verificato a fine cella per data: il file più recente è del **10/9** in `bin_prod`, del **13/9** in
`qwen38_clean\source` e in `qwen38_clean\build\bin`, e nello snapshot `p0_snapshot_20260914` non
c'è nessun file del 15/9. L'unica cartella scritta fuori dal repository è
`D:\ds4_work\banco_p0_run\20260915_145054_P9_p9_anatomia_131k`.

> **I numeri del profilatore non sono un banco.** Ogni t/s dichiarato qui viene dalla corsa
> **P8 R0** del 15/9 (stesso preset, stessi binari, senza profilatore): **37,906 ms/token,
> 26,381 t/s** a 131k. La corsa profilata di oggi serve a scomporre quel numero, non a rifarlo.

---

## 0. In una tabella

| | ms/token | quota |
|---|---:|---:|
| matvec **densi** (q6_k 9,61 + q8_0 3,11 + f32/bf16 1,65 + quantize 0,68 + punteggio QSA 0,64) | **15,69** | 41,9% |
| **trasporto esperti** dal PCIe (`moe_grouped_gather_decode`, 2 lanci per strato) | **6,69** | 17,9% |
| matvec **esperti** dalla cache in VRAM (iq2_s 3,99 + iq4_nl 1,85 + iq3_s 0,09) | **5,93** | 15,8% |
| **indicizzatore QSA** (gather delle celle 2,58 + ordinamento 0,63) | **3,21** | 8,6% |
| **GPU inattiva** | **3,32** | 8,9% |
| contabilità elementare (add/mul/scale/unary/rope/copie, 1.956 lanci) | **2,51** | 6,7% |
| instradamento MoE, GDN/SSM, norme, attenzione, altro | **2,40** | 6,4% |
| *sovrapposizione fra kernel, da sottrarre* | *−2,31* | −6,2% |
| **parete per token** | **37,44** | 100% |
| *memoria: copie H2D (14 righe di bias QSA da 514 KiB) + D2H, che si sovrappongono ai kernel e non si sommano* | *0,40* | — |

**Il pavimento di byte è 21,9 ms** (15,0 sulla corsia VRAM + 9,2 sul PCIe, meno i 2,3 già
sovrapposti): **il 58% del token è già byte obbligati.** Il resto — 15,5 ms — è dequantizzazione,
lanci, buchi e ordinamento.

---

## 1. Come è stata fatta la misura

| | |
|---|---|
| corsa | `20260915_145054_P9_p9_anatomia_131k` in `D:\ds4_work\banco_p0_run` |
| preset | `preset_P8_0_p7.json` — **MTP spento**, binari **nudi** di `D:\ds4_work\p8_work\bin_nudo`, 64 slot, contesto 262.144, `-ctk/-ctv q8_0`, `-np 1`, greedy seed 1234, ragionamento acceso |
| profilo | `lungo_131k` del banco P0: `L01@ctx131k` (prefill **freddo** di 131.248 token) e `L02@ctx131k` (riusa il prefisso), 1.024 token ciascuno |
| profilatore | Nsight Systems 2024.5.1, `nsys launch --session-new=p9anat -t cuda --cuda-graph-trace=node`; la raccolta è **spenta** per tutta la corsa e viene aperta con `nsys start` **dentro il decode**, 8 s dopo il primo delta SSE, per **4 s**, e chiusa con `nsys stop` |
| perché così | il server non chiama `cudaProfilerStart` (lo faceva `paired_probe_prof.exe` del 10/9, che **non esiste più su disco**, come non esiste più il checkpoint a 205k `qwen38_hybrid\long\...`). La finestra va quindi aperta dall'esterno, e il solo istante conoscibile è il primo token generato: lo sa il client, e il client è `sonda_p9.py` |
| guardia | prima dell'avvio: `netstat` sulla 8100 vuoto, nessun `llama-server`, nessuna build, nessuna sessione nsys. A fine corsa: gli stessi controlli, tutti vuoti |
| banda | misurata **prima** della corsa, a macchina quieta, con `banda_zerocopy.exe` (`log/p9_banda_microbanco.txt`) |

### 1.1 La corsa profilata riproduce il testo della corsa di riferimento

| caso | impronta P9 (con profilatore) | impronta P8 R0 (senza) |
|---|---|---|
| `riscaldamento_1` / `_2` | `b626d0e377e6075e` | `b626d0e377e6075e` |
| `L01@ctx131k` | `99ba1423cf128585` | `99ba1423cf128585` |
| `L02@ctx131k` | `dc916b9c428225c2` | `dc916b9c428225c2` |

**Quattro impronte su quattro identiche**: il profilatore non cambia il testo, e la corsa di oggi è
la stessa corsa di stamattina, guardata da dentro.

### 1.2 Quanto costa il profilatore, e quanto è rappresentativa la finestra

| | ms/token |
|---|---:|
| `L01` senza profilatore (P8 R0, 1.024 token) | **37,758** |
| `L01` con profilatore, media della richiesta | 39,351 (**+4,2%**) |
| `L02` senza profilatore (P8 R0) | 38,127 |
| `L02` con profilatore, media della richiesta | 38,880 (+2,0%) |
| **finestra analizzata (106 forward interi, in regime)** | **37,442** |

La finestra è **0,8% più veloce** della richiesta senza profilatore: il sovrapprezzo del
profilatore si concentra fuori dal regime (avvio della raccolta, scrittura del rapporto), e i
37,442 ms per forward che si scompongono qui sono un buon surrogato dei 37,758. **Tutti i numeri
di questo esito sono per forward dentro quella finestra.**

### 1.3 Il confine fra un forward e il successivo, e il controllo di integrità

`moe_grouped_plan_decode` gira **esattamente 48 volte** per forward (uno per strato MoE) e sempre
nello stesso ordine, quindi il suo *k*-esimo lancio e il suo (*k*+48)-esimo sono **lo stesso punto
di due forward consecutivi**: l'intervallo fra loro è un periodo intero qualunque sia la fase. La
finestra di analisi è `[marc[48], marc[48+48·n])`, che contiene *n* periodi interi; la parete per
token è la sua lunghezza diviso *n*, e le somme dei kernel dentro sono confrontabili con essa.

Il controllo che rende la cattura utilizzabile è geometrico: **48 strati MoE, 36 strati GDN, 12
strati di attenzione piena** impongono quante volte certi kernel devono comparire.

| cattura | `plan_decode` | `topk_moe` | `weighted_reduction` | `gated_delta_net` | `ssm_conv` | `flash_attn_ext` | esito |
|---|---:|---:|---:|---:|---:|---:|---|
| **L01** | 48,0 / 48 | 48,0 / 48 | 48,0 / 48 | 36,0 / 36 | 36,0 / 36 | 12,0 / 12 | **passato** |
| L02 | 48,0 / 48 | **35,2** / 48 | 45,9 / 48 | **13,9** / 36 | 30,9 / 36 | **2,1** / 12 | **fallito** |

**La seconda cattura è invalida**: nsys ha perso eventi (344.278 kernel contro i 460.155 della
prima, a parità di durata del file, e `flash_attn_ext_f16` presente 206 volte invece delle ~1.161
che la geometria impone). Probabilmente i buffer non si riciclano bene fra due raccolte nella
stessa sessione. È registrata e **non entra in nessuna tabella**; l'esito poggia sulla sola L01.
Costo: nessuna replica, ed è un difetto (§7.1).

### 1.4 Le bande della macchina, misurate

`banda_zerocopy.exe 2 16 3`, tre ripetizioni concordi entro lo 0,2%:

| corsia | misurato | nominale |
|---|---:|---|
| **lettura da VRAM** | **340,3 GB/s** | 360 GB/s teorici della 3060 (94,5%) |
| lettura GPU zero-copy da host mappato | **26,3 GB/s** | PCIe 4.0 x16 = 29,3 GB/s teorici |
| copia DMA host→device | **26,3 GB/s** | idem |
| lettura CPU a 16 thread | 33,4 GB/s | DDR4 |

Le due corsie del PCIe danno lo **stesso** numero, con due meccanismi diversi (un kernel che legge
memoria mappata e una copia del driver): 26,3 GB/s è il tetto pratico del bus su questa macchina.

---

## 2. A — dove vanno i 37,4 ms

106 forward interi, finestra 3.968,8 ms. Per forward: **parete 37,442 ms**, GPU occupata (unione
dei kernel) **34,120**, **inattiva 3,322**, somma delle durate dei kernel **36,430**
(sovrapposizione fra kernel **2,310**).

### 2.1 Per categoria

| categoria | ms/forward | quota | lanci/forward |
|---|---:|---:|---:|
| matvec densi quantizzati, **q6_k** | **9,609** | 25,7% | 202 |
| **trasporto esperti dal PCIe** (`moe_grouped_gather_decode`) | **6,688** | 17,9% | 96 |
| matvec **esperti iq2_s** (gate+up, fusi con la GLU) | **3,985** | 10,6% | 47 |
| matvec densi quantizzati, **q8_0** | 3,113 | 8,3% | 247 |
| indicizzatore QSA: gather delle celle (`k_get_rows*`) | 2,575 | 6,9% | 136 |
| elementari (add/mul/scale/unary/rope/copie) | 2,512 | 6,7% | **1.956** |
| matvec **esperti iq4_nl** (down) | 1,852 | 5,0% | 48 |
| matvec densi in virgola mobile (router f32, inject, ssm, indicizzatore bf16) | 1,651 | 4,4% | 288 |
| instradamento MoE (plan, top-k, riduzione) | 0,769 | 2,1% | 144 |
| GDN / SSM | 0,764 | 2,0% | 72 |
| quantizzazione dell'attivazione (`quantize_q8_1`) | 0,682 | 1,8% | 545 |
| punteggio QSA sui blocchi (`mul_mat_f`) | 0,640 | 1,7% | 12 |
| indicizzatore QSA: ordinamento (radix sort) | 0,631 | 1,7% | 72 |
| norme | 0,458 | 1,2% | 256 |
| attenzione (`flash_attn` + fixup) | 0,288 | 0,8% | 24 |
| altro | 0,120 | 0,3% | 110 |
| matvec **esperti iq3_s** (l'unico strato) | 0,092 | 0,2% | 1 |
| **copie H2D** (27 copie, 7,31 MiB) | 0,357 | 1,0% | — |
| **copie D2H** (1 copia, 0,95 MiB) | 0,040 | 0,1% | — |
| **GPU inattiva** | **3,322** | **8,9%** | — |
| *sovrapposizione fra kernel* | *−2,310* | — | — |
| **parete** | **37,442** | 100% | **4.256 lanci** |

Il file completo per kernel è in `log/p9_L01_nsys.md`.

### 2.2 Chi è chi — la separazione esperti/densi

I nomi demangled portano il tipo come `(ggml_type)N`: è così che si separa il matvec degli
**esperti** (iq2_s 22, iq3_s 21, iq4_nl 20) da quello **denso** (q6_k 14, q8_0 8). La geometria
conferma l'attribuzione senza bisogno di altro:

| kernel | lanci/forward | blocchi/lancio | che cos'è |
|---|---:|---:|---|
| `mul_mat_vec_q<iq2_s>` fuso | 47 | 1.600 = 10 esperti × 160 | gate+up degli esperti, **un solo lancio per strato**: gate/up e la GLU sono già fusi |
| `mul_mat_vec_q<iq4_nl>` | 48 | 6.400 = 10 × 640 | `ffn_down_exps` |
| `mul_mat_vec_q<q6_k>` | 202 = **155 + 47 fusi** | 5.616 medi | i 155: 36×(`attn_qkv`, `attn_gate`, `ssm_out`) + 12×(q,k,v,o) + testa di uscita; i 47 fusi: gate/up dell'esperto condiviso |
| `mul_mat_vec_q<q8_0>` | 247 | 1.924 / 596 | le 4 matrici `hc_*` per strato (~192) + `ffn_down_shexp` (48) |
| `mul_mat_vec_f<f32>` | 288 | 108 medi | router `ffn_gate_inp` (48), `ssm_alpha/beta` (72), `hc_*_inject` (96), … |
| `mul_mat_f<f32>` | 12 | 1.028 ≈ n_kv/4/32 | **il punteggio QSA sui 32.812 blocchi**, uno per strato di attenzione |
| `moe_grouped_gather_decode` | 96 | 112 e 28 | **due** lanci per strato: banchi gate+up sul flusso principale, banco down su `transfer_stream` |

`attn_qkv` è **un solo tensore** nel GGUF (QKV già fusi a monte) nei 36 strati GDN; nei 12 strati di
attenzione piena q/k/v/o sono separati. `ffn_gate_exps`+`ffn_up_exps`+GLU sono fusi dal backend
(`ggml_cuda_can_fuse(..., {op, op, GGML_OP_GLU})`, `ggml-cuda.cu:4214`): **47 lanci iq2_s per
forward, non 94**.

### 2.3 La somma torna

`36,430` (kernel) `+ 0,357` (H2D) `+ 0,040` (D2H) `− 2,310` (sovrapposizione) `= 34,517`, contro
i **34,120** di GPU occupata misurata come unione degli intervalli: la differenza (0,4 ms) è la
parte di copie che si sovrappone ai kernel. `34,120 + 3,322 = 37,442` = parete. **Il bilancio
chiude.**

### 2.4 Che cosa fa l'host

| chiamata CUDA | per forward | tempo host per forward |
|---|---:|---:|
| `cudaStreamSynchronize` | **78** | 30,186 ms (è attesa, si sovrappone alla GPU) |
| `cudaGraphLaunch` | **1** | 6,141 ms |
| `cudaMemcpyAsync` | 28 | 0,198 ms |

**Un solo lancio di grafo CUDA per forward**, coerente con `graph splits = 2 (with bs=1)` letto nel
log del server: dei due split uno non è CUDA. Le 78 sincronizzazioni per token sono il prezzo di
quello split e dei 27 ingressi copiati.

### 2.5 Dove sta la GPU inattiva (3,322 ms)

Misurata come somma dei buchi fra la fine di un kernel e l'inizio del successivo, dentro la
finestra:

| fascia | buchi/forward | ms/forward | che cosa |
|---|---:|---:|---|
| **> 100 µs** | **1,88** | **1,901** | **sempre alla stessa fase del forward**, sempre fra un `mul_mat_vec_q` e un `k_bin_bcast`, mediana 1,59 ms. È la consegna fra il grafo e l'host: campionamento, `set_input`, lo split non-CUDA, le 14 righe di bias costruite sull'host |
| 20-100 µs | 0,3 | 0,014 | — |
| 5-20 µs | 64,1 | 0,883 | **tutti nell'indicizzatore QSA**: 36 prima di `k_get_rows_float_vec` (3 per strato di attenzione), 12 prima dell'istogramma del radix sort, 11 prima di `mul_mat_vec_f`. Sono i punti in cui la catena esce dal grafo |
| 2-5 µs | 55,8 | 0,137 | — |
| < 2 µs | 4.053 | 0,387 | latenza fra nodi dentro il grafo, ~0,1 µs ciascuna |

**Due terzi della GPU inattiva stanno in due buchi al giorno per token**, allo stesso punto del
forward. Il terzo restante è spalmato sull'indicizzatore.

### 2.6 Le copie H2D sono il bias QSA, e sono quattordici

Istogramma delle 27 copie per forward: **14 copie da 526.336 byte** (= 131.584 float ≈ `n_kv`
arrotondato), più una da 262.144, una da 16.384, due da 10.240 e nove da meno di 40 byte.

Le 14 copie grandi sono il **bias per cella della QSA**: a 205k P7 ne contò **14** da 822.272 byte
per una riga — lo stesso numero. Sono `12` viste (una per strato di attenzione) più il tensore
intero più `cell_blk`. **La leva B di P8** (`QWEN4EXP_QSA_BIAS_DEV`, il bias residente sul
dispositivo) le riduce a 2: a 2 righe toglieva 47 copie e valeva −1,44 ms; qui ne toglierebbe 12.

---

## 3. B — il pavimento di byte, per categoria

I byte vengono dall'intestazione dei tre shard del GGUF (`composizione_gguf_p9.py`, `log/p9_composizione.json`)
e dalla geometria della QSA. **Le regole sono dichiarate, e sono un modello, non una misura:**

1. a batch 1 ogni matvec legge la matrice **intera** una volta: byte = byte del tensore;
2. `token_embd` (497 MiB) e `per_layer_token_embd` (26,8 GiB, sulla CPU) sono letti **per riga**:
   contati zero;
3. gli esperti: **10 instradati su 512**, per ognuno dei 48 strati, gate+up+down. `mmvq` legge dalla
   cache **tutti e dieci**, colpiti o no: i mancanti ci sono appena stati copiati dentro;
4. KV e indicizzatore stanno in memoria **host mappata** (`QWEN4EXP_ATTN_MAPPED=1`,
   `QWEN4EXP_INDEXER_MAPPED=1`): i loro byte passano dal bus;
5. l'attenzione non scandisce `n_kv`: il gather QSA copia le **2.048 celle scelte**
   (`indexer_top_k`) e l'attenzione è densa su quelle. Il punteggio invece legge la cache dei
   **blocchi**: `n_kv/4 = 32.812` blocchi × 128 dimensioni × 4 byte × 12 strati.

| categoria | misurato ms | MiB/token | banda effettiva | pavimento ms | efficienza | spreco ms |
|---|---:|---:|---:|---:|---:|---:|
| esperti: matvec dalla cache in VRAM | 5,929 | 905,8 | 160,2 GB/s | 2,791 | **47%** | **3,138** |
| esperti: trasporto dal PCIe (gather) | 6,688 | 168,5 | 26,4 GB/s | 6,717 | **100%** | −0,029 |
| densi quantizzati q6_k/q8_0 (+`quantize_q8_1`) | 13,404 | 3.446,4 | 269,6 GB/s | 10,620 | 79% | **2,784** |
| densi in virgola mobile (router f32, inject, ssm, bf16) | 1,651 | 336,2 | 213,5 GB/s | 1,036 | 63% | 0,615 |
| punteggio QSA sui blocchi | 0,640 | 192,3 | 315,0 GB/s | 0,592 | **93%** | 0,048 |
| indicizzatore/KV: gather delle 2.048 celle | 2,575 | 54,2 | 22,1 GB/s | 2,160 | 84% | 0,415 |
| copie H2D (bias QSA) | 0,357 | 7,3 | 21,5 GB/s | 0,292 | 82% | 0,065 |
| *instradamento, ordinamento, attenzione, GDN, norme, elementari, altro* | *5,542* | — | — | — | — | — |
| **somma** | **36,786** | **5.111** | — | **24,208** | | |
| **parete** | **37,442** | | | | | |

**Byte totali per token: 5,11 GiB.** Corsia VRAM **15,039 ms** di pavimento, corsia PCIe
**9,169 ms**.

### 3.1 Il trasporto degli esperti è esattamente al tetto del bus, e dice quanti ne mancano

I due lanci del gather (banchi gate+up, 112 blocchi; banco down, 28 blocchi) **non si sovrappongono
mai fra loro** (somma = unione = 6,688 ms) ma **si sovrappongono per 2,310 ms con il resto**: il
34,5% del trasporto è già nascosto dietro il calcolo. Entrambi, con griglie diverse di un fattore
quattro e quote di byte diverse (53% e 47%), danno **la stessa banda implicita per esperto
mancante** (13,98 e 14,05 GB/s per unità): sono limitati dal **bus**, non dall'occupazione.

Invertendo il tempo alla banda misurata: 6,688 ms × 26,3 GB/s = **168,5 MiB per forward**, cioè
**1,86 esperti mancanti per strato, colpi 81,4%**. Con un bus effettivo da 28 GB/s: 1,98 mancanti,
80,2%.

> **Questo non coincide con P7.** I contatori del dispositivo del 14/9 (`LLAMA_MOE_HIT_REPORT`)
> davano il **70,5%** di colpi in regime, cioè 2,95 mancanti per strato e **271 MiB per forward**;
> 271 MiB a 26,3 GB/s sarebbero **10,65 ms**, e il kernel ne impiega 6,69. O i colpi a 131k con una
> riga sola sono migliori di quelli misurati a 205k, o il gather supera i 26,3 GB/s del microbanco.
> **Non è decidibile senza rifare i contatori a 131k** (§7.2). Non cambia il verdetto: in un caso o
> nell'altro il trasporto è **al tetto del bus**, ed è l'unica voce del token che lo sia.

### 3.2 Il fatto che riorganizza tutto: il matvec non è limitato dai byte, è limitato dai **pesi**

La banda effettiva di ogni famiglia **cresce col numero di bit per peso** — il contrario di quello
che farebbe un kernel limitato dalla banda:

| famiglia | bpw | MiB letti | ms | banda effettiva | **ps per peso** | di cui dai byte | **di cui dequantizzazione** | bpw **effettivi** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| esperti **iq2_s** (gate+up) | 2,50 | 470,5 | 3,985 | 123,8 GB/s | 2,524 | 0,918 | **1,606 (64%)** | **6,87** |
| esperti iq3_s | 3,44 | 13,4 | 0,092 | 153,0 | 2,808 | 1,263 | 1,545 (55%) | 7,64 |
| esperti **iq4_nl** (down) | 4,50 | 421,9 | 1,852 | 238,9 | 2,355 | 1,653 | 0,702 (30%) | 6,41 |
| densi **q6_k** | 6,56 | 2.676,8 | 9,609 | 292,1 | 2,808 | 2,411 | **0,398 (14%)** | 7,65 |
| densi q8_0 | 8,50 | 769,6 | 3,113 | 259,2 | 4,098 | 3,122 | 0,976 (24%) | 11,16 |

Il modello a due termini `t = byte/340,3 GB/s + pesi × costo_di_dequantizzazione(formato)` separa
le due cause. Ne escono tre cose:

1. **IQ2_S paga 1,606 ps per peso di sola dequantizzazione, quattro volte Q6_K** (0,398). È il
   codice a tabella dei formati IQ: il kernel è limitato dalle ricerche, non dalla memoria.
2. **A una riga, 2,5 bit per peso costano come 6,87.** La compressione che fa stare gli esperti in
   RAM **non si traduce in tempo**: sulla corsia VRAM un esperto IQ2_S è veloce quanto lo sarebbe a
   quasi 7 bit.
3. **Q6_K, invece, è quasi tutto byte** (86% del suo tempo): è l'unica famiglia grande dove togliere
   byte toglie davvero tempo. È il fondamento della leva 1.

---

## 4. C — le tre leve sul token singolo

### 4.1 Leva 1 — i densi residenti da Q6_K a Q4_K

I tensori q6_k letti per token sono **2.676,8 MiB**: `attn_qkv` dei 36 strati GDN (717,8),
`attn_gate` (430,7), `ssm_out` (443,0), `attn_q`/`attn_output`/`attn_k`/`attn_v` dei 12 strati di
attenzione (470,6), la testa di uscita (497,3), gate/up dell'esperto condiviso (120,5). Q4_K è
4,5 bpw contro 6,5625: **−31,4% di byte, −841,3 MiB**.

Col modello a due termini (§3.2), assumendo per Q4_K un costo di dequantizzazione compreso fra
quello **misurato** di Q6_K (0,398 ps/peso, ottimista per Q4_K) e quello di IQ4_NL (0,702,
pessimista):

| | ms |
|---|---:|
| q6_k oggi | 9,609 |
| q4_k col costo di dequantizzazione del q6_k | 7,017 |
| q4_k col costo di dequantizzazione dell'iq4_nl | 8,058 |
| **guadagno** | **−1,55 … −2,59** |

In più libera **841 MiB di VRAM**, cioè ~**9,3 slot esperti per strato** (64 → 73). Sulla curva
degli slot del 13/9 (0/32/64 slot = 14,71/22,18/24,64 t/s) il margine vale ~+0,07 t/s per slot, in
saturazione: **da 0 a −0,8 ms**, con incertezza grande perché quella curva è di un'altra
configurazione.

| | |
|---|---|
| **ms attesi** | **−1,6 … −2,6** (fino a −3,4 contando gli slot liberati) |
| **lossless** | **NO.** Cambia i pesi: il testo cambia, e cade il cancello della bit-identità su cui poggiano P7 e P8 |
| **difficoltà** | media. `llama-quantize --allow-requantize` con tipi per tensore, lasciando gli esperti intatti, parte dal GGUF che c'è (77 GiB) senza scaricare i BF16; ma è una **ri**-quantizzazione, quindi l'errore si somma |
| **rischio qualità** | **reale**. Riguarda le proiezioni di attenzione e GDN e la testa di uscita. Escludendo la sola testa di uscita il guadagno scende a −1,3…−2,1 ms e il rischio cala molto |

### 4.2 Leva 2 — meno lanci

**Oggi un token costa 4.256 lanci di kernel.** Di questi **2.979 durano meno di 2,5 µs** e valgono
in tutto **3,986 ms**.

Il costo di un lancio «vuoto» è **misurato**, non stimato: i kernel con meno di 30 blocchi e byte
trascurabili (`scale_f32` 3,4 blocchi → 1,00 µs; `unary_op_kernel` 0,98; `init_offsets` 0,77;
`op_clamp_kernel` 0,90; `rope_multi` 1,41) costano in media **1,15 µs** ciascuno. I 2.979 lanci
piccoli portano quindi **~3,42 ms di puro lancio** sui 3,986 che costano: **l'86% del loro tempo
non è lavoro.**

**Quello che il progetto proponeva è già fatto:** `attn_qkv` è un solo tensore nel GGUF, e
gate/up+GLU sono fusi dal backend (47 lanci iq2_s per forward invece di 94; anche
`rms_norm+mul+rope+set_rows` e `topk_moe` hanno già le loro fusioni). **Non c'è un QKV da fondere.**

Il bersaglio vero è altrove: **le connessioni iper (`hc_`)**. `build_hc_mix` gira **due volte per
strato** (attenzione e FFN) e mette ~14 nodi ciascuna — `rms_norm`, `mul`, matvec down, `scale`,
`silu`, matvec up, `sigmoid`, `mul`, `cont`, tre `add` di collasso dei quattro flussi, `scale`,
matvec inject — cioè **~1.300 lanci per forward su 4.256**. I quattro `hc_*` q8_0 per strato sono
anche 656 MiB di byte (§3).

| | |
|---|---|
| **ms attesi** | **−1,0 … −1,9** fondendo la catena `hc_mix` in due o tre kernel per sito (toglie ~1.000 lanci) |
| **lossless** | **possibile**, se la fusione conserva l'ordine delle operazioni; va **dimostrato con l'impronta**, non assunto |
| **difficoltà** | **alta**: kernel CUDA nuovi più una regola di fusione nel grafo. Nessun rischio sul modello |
| **rischio qualità** | nullo se bit-identico; altrimenti la leva non passa il cancello |

### 4.3 Leva 3 — l'efficienza del kernel degli esperti

`mul_mat_vec_q<iq2_s>` legge 470,5 MiB in **3,985 ms**: **123,8 GB/s, il 36,4% del picco**. Il
pavimento di quei byte è 1,45 ms: **il 64% del tempo di quel kernel è dequantizzazione**, cioè
1,606 ps per peso contro gli 0,398 di Q6_K e gli 0,702 di IQ4_NL (§3.2).

| se la dequantizzazione IQ2_S costasse come… | ms | guadagno |
|---|---:|---:|
| IQ4_NL (0,702 ps/peso) | 2,558 | **−1,43** |
| Q6_K (0,398 ps/peso) | 2,078 | **−1,91** |
| zero (solo byte) | 1,450 | −2,54 |

Si aggiunge IQ4_NL: portarlo dalla sua banda (238,9 GB/s) a quella di Q6_K (292,1) vale **−0,34 ms**.

| | |
|---|---|
| **ms attesi** | **−1,4 … −1,9** (fino a −2,3 con IQ4_NL) |
| **lossless** | **sì, per costruzione**, se l'ordine di accumulazione non cambia: è un kernel, non un peso |
| **difficoltà** | **alta**: riscrivere il prodotto scalare IQ2_S (tabella dei codici in memoria condivisa o costante, più warp per riga, `dp4a` dove possibile). Lavoro CUDA fine |
| **rischio qualità** | nullo se bit-identico |

*Nota, contro un'idea che sembra ovvia:* cambiare il quanto degli esperti (IQ2_S → IQ4_NL) **non**
si può leggere come «−1,4 ms», perché raddoppierebbe i byte degli esperti: gate+up passerebbero da
470 a 847 MiB per token sulla VRAM **e** da 1,0 a 1,8 MiB per esperto mancante sul PCIe, che è la
corsia satura. Il conto peggiora di ~2 ms sul bus. **La leva è il kernel, non il formato.**

### 4.4 (4) Che cosa cresce col contesto

| voce | ms a 131k | come cresce |
|---|---:|---|
| punteggio QSA sui blocchi (`mul_mat_f`) | 0,640 | **∝ n_kv** (legge `n_kv/4` blocchi × 128 × 4 B × 12) |
| ordinamento dell'indicizzatore (radix sort) | 0,631 | **∝ n_kv** (ordina i punteggi dei blocchi) |
| copie H2D del bias QSA | 0,357 | **∝ n_kv** (14 righe da `n_kv` float) |
| **totale che scala col contesto** | **1,628** | **4,35% del token** |
| gather delle 2.048 celle scelte | 2,575 | **costante**: `indexer_top_k` non dipende dalla profondità |
| tutto il resto (matvec, trasporto esperti, GDN, elementari) | 33,2 | costante |

Stime: **~0,41 ms a 32k, 1,63 a 131k, ~3,26 a 262k.** Cioè il token a 262k costa ~1,6 ms più che a
131k (+4,4%), e a 32k ~1,2 ms meno (−3,3%). **È coerente con le misure**: a 205k il probe del 10/9
dava 38,9-39,7 ms contro i 37,8 di oggi a 131k.

**Confronto col profilo a contesto corto del 13/9** (`VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md`,
percentuali di durate sommate):

| voce | 13/9, contesto corto | P9, 131k |
|---|---:|---:|
| upload degli esperti | 24,48% | **18,2%** |
| moltiplicazioni Q6_K | 22,99% | **26,1%** |
| IQ2_S | 9,85% | 10,8% |
| attenzione (qui: indicizzatore + gather + FA + punteggio) | 7,93% | **11,2%** |

**La quota dell'attenzione/indicizzatore cresce di un terzo passando al contesto lungo, quella del
trasporto esperti cala di un quarto** — non perché il trasporto rallenti (è costante in ms), ma
perché il resto cresce. **Il Q6_K denso, non l'upload degli esperti, è la voce più grande al punto
operativo dell'utente.** A contesto corto era il contrario.

---

## 5. D — il verdetto: il tetto del token singolo

### 5.1 I pavimenti

| | ms | t/s |
|---|---:|---:|
| **misurato** (P8 R0, senza profilatore) | **37,91** | **26,38** |
| misurato (finestra profilata) | 37,44 | 26,71 |
| pavimento dei soli byte, **con la sovrapposizione che c'è oggi** (2,31 ms) | **21,90** | 45,7 |
| pavimento dei soli byte, **se le due corsie si sovrapponessero perfettamente** | 15,04 | 66,5 |
| — di cui corsia VRAM | 15,04 | |
| — di cui corsia PCIe | 9,17 | |

Il pavimento dei byte è **il 58%** del token. I 15,5 ms restanti sono: dequantizzazione 6,95,
kernel che non muovono byte del modello 5,54 (instradamento, ordinamento, attenzione, GDN, norme,
elementari), GPU inattiva 3,32, meno la sovrapposizione.

### 5.2 Il tetto realistico

| scenario | ms/token | t/s | che cosa richiede |
|---|---:|---:|---|
| oggi | 37,44 | 26,7 | — |
| **solo le due leve lossless** (2 + 3) | **34,3** | **29,1** | fusione delle `hc_` + kernel IQ2_S |
| **le tre leve** (1 + 2 + 3, valori centrali) | **32,4** | **30,8** | in più la ri-quantizzazione dei densi a Q4_K |
| le tre leve + i 3,3 ms di GPU inattiva ridotti a 1 | 30,1 | 33,2 | in più una cella sui due buchi da 1 ms |
| **tutto quello che si riesce a immaginare** | **~28** | **~36** | sopra, più il trasporto esperti nascosto quasi del tutto dietro il calcolo |
| pavimento fisico con la sovrapposizione di oggi | 21,9 | 45,7 | zero dequantizzazione, zero lanci, zero buchi: finzione |

> ### **Il tetto del token singolo su questa macchina con questo modello resta sopra i 30 ms.**
>
> Con le due leve **lossless** si arriva a **~34 ms** (29 t/s). Con anche la ri-quantizzazione dei
> densi — che **non** è lossless — a **~32 ms** (31 t/s). Per scendere sotto i 30 ms serve
> aggredire anche i 3,3 ms di GPU inattiva, e il risultato più ottimista che i numeri di oggi
> permettono di scrivere è **~28 ms, cioè ~36 t/s**.
>
> ### **I 50 t/s a 131k non stanno in questo hardware con questo modello.**
>
> 50 t/s sono **20,0 ms per token**. Il pavimento dei soli byte, con la quantizzazione di oggi e la
> sovrapposizione di oggi, è **21,9 ms**: i 50 t/s sono **sotto il pavimento**, prima ancora di
> pagare un solo lancio di kernel, una sola dequantizzazione, un solo buco. Portando **tutti** i
> densi a Q4_K il pavimento scende a 19,6 ms, cioè i 50 t/s diventano possibili solo in un mondo
> dove dequantizzazione, lanci, ordinamento, GDN, attenzione e GPU inattiva costano **zero**.
> **L'obiettivo onesto del token singolo su questa macchina è 30-33 t/s.**

*Che cosa resta fuori da questo verdetto:* la speculazione. P8 ha misurato che con la leva B la
bozza MTP a 1 token rende **1,673 token per ciclo** a 37,2 ms/token effettivi. Se `T1` scende a
32 ms, anche il ciclo scende e l'MTP resta redditizio: il tetto **del ciclo** è un'altra domanda,
che questa cella non affronta.

### 5.3 Quale leva si prova per prima

**Fra le tre: la 3, il kernel IQ2_S.** Motivi, in ordine:

1. è **lossless per costruzione** — è un kernel, non un peso: non tocca il cancello della
   bit-identità su cui poggiano P7 e P8, e non chiede all'utente di accettare un modello diverso;
2. è la **più grande inefficienza singola misurata contro il proprio pavimento**: 2,54 ms su un
   kernel solo, il 64% del suo tempo;
3. la causa è **nominata e locale** (il prodotto scalare IQ2_S), non diffusa come nella leva 2;
4. **non tocca il bus**, che è l'unica corsia satura: qualunque cosa faccia, non peggiora il
   trasporto.

**Prima ancora, però, due cose costano una corsa e non un ciclo di sviluppo**, e insieme valgono
più di una leva:

- **misurare la leva B di P8 su `T1`.** P8 l'ha misurata solo sulla riga di verifica. Qui si vede
  che a MTP spento il decode fa **14 copie da 514 KiB per token** di bias QSA (0,357 ms) e altrettante
  costruzioni sull'host: la patch è già scritta, è lossless, e i suoi default non richiedono
  variabili. Costo: una corsa.
- **aprire una cella sui due buchi da ~1 ms** (§2.5): 1,9 ms per token, sempre alla stessa fase,
  fra il grafo e l'host. È più di quanto valga la leva 1, e non chiede di cambiare il modello.

---

## 6. Comandi per riprodurre

```powershell
# 1. banda della macchina, PRIMA della corsa e a macchina quieta
D:\qwen38_work\banda_zerocopy.exe 2 16 3

# 2. composizione del GGUF (legge solo le intestazioni)
python docs\porto\p9_anatomia_131k\composizione_gguf_p9.py `
  --gguf D:\models\qwen38flashnext\UD-IQ3_XXS\Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf `
  --json-out docs\porto\p9_anatomia_131k\log\p9_composizione.json

# 3. la corsa profilata (guardia, nsys launch, due finestre dentro il decode, chiusura)
docs\porto\p9_anatomia_131k\avvia_p9_nsys.ps1 -Profila "L01,L02" -AttesaS 8 -FinestraS 4
```

```bash
# 4. esportazione e scomposizione
NS="/c/Program Files/NVIDIA Corporation/Nsight Systems 2024.5.1/target-windows-x64/nsys.exe"
D="/d/ds4_work/banco_p0_run/20260915_145054_P9_p9_anatomia_131k/nsys"
"$NS" export --type sqlite --force-overwrite true -o "$D/p9_L01.sqlite" "$D/p9_L01@ctx131k.nsys-rep"
python docs/porto/p9_anatomia_131k/analizza_nsys_p9.py "$D/p9_L01.sqlite" \
  --md-out docs/porto/p9_anatomia_131k/log/p9_L01_nsys.md \
  --json-out docs/porto/p9_anatomia_131k/log/p9_L01_nsys.json

# 5. pavimento di byte, tabella B, aritmetica delle leve, log puliti
python docs/porto/p9_anatomia_131k/pavimento_byte_p9.py
python docs/porto/p9_anatomia_131k/tabella_p9.py --nsys-json docs/porto/p9_anatomia_131k/log/p9_L01_nsys.json \
  --md-out docs/porto/p9_anatomia_131k/log/p9_tabella_B.md --json-out docs/porto/p9_anatomia_131k/log/p9_tabella_B.json
python docs/porto/p9_anatomia_131k/leve_p9.py
python docs/porto/p9_anatomia_131k/copia_log_p9.py
```

---

## 7. Difetti

1. **Una sola cattura valida.** La seconda ha perso eventi (§1.3) e non c'è replica. La finestra è
   di 106 forward su 1.024 token generati: rappresentativa (parete 37,442 contro i 37,758 della
   richiesta senza profilatore) ma non è una distribuzione. I periodi per forward dentro la
   finestra vanno da **33,05 a 52,56 ms** (mediana 37,29): la coda lunga esiste e non è stata
   studiata.
2. **Il numero di esperti mancanti per strato è INVERTITO dal tempo, non contato** (§3.1), e non
   coincide con i contatori di P7 a 205k (1,86 contro 2,95). Una corsa con `LLAMA_MOE_HIT_REPORT`
   a 131k la chiuderebbe. Finché non è fatta, i «168,5 MiB per forward» sono un'inferenza.
3. **Tutta la colonna «MiB/token» della tabella B è un modello**, non una misura: nsys non conta i
   byte dei kernel. Le regole sono dichiarate in §3 e le due verifiche indipendenti che reggono
   sono (a) il punteggio QSA al 93% del picco, che una geometria sbagliata non darebbe, e (b) i due
   gather che danno la stessa banda implicita con griglie diverse.
4. **Il costo di dequantizzazione per peso** (§3.2) è ricavato sottraendo il pavimento di byte dal
   tempo misurato, cioè assume che le due cause si sommino. È un modello a due termini su cinque
   punti: regge bene (Q6_K predetto 293 GB/s contro 292 misurati) ma non è dimostrato.
5. **Il guadagno di Q4_K è calcolato con il costo di dequantizzazione di *altri* formati** (Q6_K e
   IQ4_NL), perché Q4_K in questo modello non esiste. L'intervallo −1,55…−2,59 ms ha questa
   incertezza dentro, e non copre l'effetto sulla qualità, che non è stato valutato affatto.
6. **La RAM disponibile minima è 2,12 GB**, sotto la soglia di 4 GB che la regola dell'utente dà
   per corsa invalida. Qui pesa anche il profilatore (P8 R0, stessa configurazione senza nsys,
   stava a 5,12 GB). La corsa resta valida **come scomposizione** — le impronte sono identiche a
   quelle di P8 R0 — ma il suo ms/token non è un valore assoluto, e infatti non è usato come tale.
7. **La posizione dei due buchi da 1 ms è nota solo a meno della fase** (§2.5): il marcatore dice
   che sono sempre allo stesso punto del forward, non quale punto. Per saperlo serve NVTX nel
   server, che questa cella non ha aggiunto.
8. **Niente campionamento della CPU**: nsys avverte che `--sample` e `--cpuctxsw` richiedono
   privilegi di amministratore e li disabilita. Dell'host si sanno solo le chiamate CUDA (§2.4), non
   dove spende il tempo.

---

## 8. Bozza di voce di registro

> **15 settembre 2026 — fase P9: anatomia del token singolo di decode a 131k.**
>
> *Ipotesi.* I 37,9 ms di un token al punto operativo dell'utente si scompongono in categorie
> misurabili, e una di esse ha abbastanza scarto dal proprio pavimento di byte da valere una leva.
>
> *File toccati.* Nuovi in `docs/porto/p9_anatomia_131k/`: `P9_ANATOMIA_131K_15_SETTEMBRE.md`,
> `avvia_p9_nsys.ps1`, `sonda_p9.py`, `analizza_nsys_p9.py`, `composizione_gguf_p9.py`,
> `pavimento_byte_p9.py`, `tabella_p9.py`, `leve_p9.py`, `copia_log_p9.py`, `log/` (banda,
> composizione, due catture, tabelle, log della corsa ripuliti). **Nessuna modifica al motore,
> nessuna build, nessun commit.** `bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`,
> lanciatore quotidiano, modelli e snapshot P0 invariati.
>
> *Configurazioni.* `preset_P8_0_p7.json` (MTP spento, binari nudi di `p8_work\bin_nudo`, 64 slot,
> contesto 262.144), profilo `lungo_131k`, greedy seed 1234, budget 1024. Server avviato sotto
> `nsys launch -t cuda --cuda-graph-trace=node` con la raccolta **spenta**; due finestre da 4 s
> aperte con `nsys start` otto secondi dopo il primo token, chiuse con `nsys stop`. Banda della
> macchina misurata prima, a macchina quieta.
>
> *Run validi / invalidi.* **Una corsa, quattro richieste, zero guasti, zero NaN, zero processi
> residui, quattro impronte su quattro identiche a quelle di P8 R0** — il profilatore non cambia il
> testo. **Delle due catture nsys una è invalida**: la seconda ha perso eventi (344.278 kernel
> contro 460.155, `flash_attn_ext_f16` visto 2,1 volte per forward invece di 12) e il controllo di
> integrità geometrico, aggiunto allo strumento, la scarta. RAM disponibile minima **2,12 GB**,
> sotto la soglia dei 4 GB: il ms/token di questa corsa non è un valore assoluto e non è usato come
> tale (il riferimento resta P8 R0, 37,906 ms, 26,381 t/s).
>
> *Risultato e limite.* **Il token da 37,4 ms è: 15,7 ms di matvec densi, 6,7 di trasporto esperti
> dal PCIe, 5,9 di matvec esperti, 3,2 di indicizzatore QSA, 3,3 di GPU inattiva, 2,5 di kernel
> elementari, 2,4 di tutto il resto, meno 2,3 di sovrapposizione.** Muove **5,11 GiB per token** e
> il pavimento di quei byte alle bande misurate (VRAM **340,3 GB/s**, PCIe **26,3**) è **21,9 ms**
> con la sovrapposizione che c'è oggi, **15,0** se le due corsie si sovrapponessero perfettamente:
> **il 58% del token è byte obbligati.**
> Tre fatti nuovi. (1) **Al punto operativo l'upload degli esperti non è più la voce maggiore**: è
> il **Q6_K denso** (9,6 ms, 25,7%) contro i 6,7 del trasporto. A contesto corto (profilo del 13/9)
> era il contrario (24,5% contro 23,0%); la quota dell'attenzione/indicizzatore sale da 7,9% a
> 11,2%. (2) **Il matvec a una riga non è limitato dai byte ma dai pesi**: la banda effettiva
> *cresce* coi bit per peso, e il modello a due termini `t = byte/banda + pesi × dequant(formato)`
> dà un costo di dequantizzazione di **1,606 ps/peso per IQ2_S contro 0,398 per Q6_K** — quattro
> volte. **A una riga, 2,5 bit per peso costano come 6,87**: la compressione che fa stare gli
> esperti in RAM non si traduce in tempo sulla corsia VRAM. (3) **Il trasporto degli esperti è
> l'unica voce al tetto del bus**: i due gather (griglie 112 e 28 blocchi, quote di byte 53% e 47%)
> danno la **stessa** banda implicita, e il 34,5% del loro tempo è già nascosto dietro il calcolo.
> Invertendo il tempo alla banda misurata escono **168,5 MiB e 1,86 esperti mancanti per strato
> (colpi 81,4%)**, che **non coincide** coi contatori di P7 a 205k (2,95, 271 MiB): quei 271 MiB a
> 26,3 GB/s sarebbero 10,65 ms e il kernel ne impiega 6,69. Non decidibile senza rifare i contatori.
> Due cose si vedono solo qui: la **GPU inattiva (3,32 ms) è per due terzi in due buchi da ~1 ms
> per token**, sempre alla stessa fase, fra il grafo e l'host (per forward c'è **un solo
> `cudaGraphLaunch` e ci sono 78 `cudaStreamSynchronize`**); e il decode a MTP spento fa **14 copie H2D da
> 514 KiB di bias QSA per token**, che è esattamente ciò che la leva B di P8 toglie — **mai
> misurata su `T1`**.
> *Limiti*: una sola cattura valida e nessuna replica; i byte per categoria sono un modello, non una
> misura; gli esperti mancanti sono invertiti dal tempo; il costo di dequantizzazione è un modello a
> due termini su cinque punti; RAM sotto soglia.
>
> *Decisione proposta.* **Il tetto del token singolo su questa macchina con questo modello resta
> sopra i 30 ms.** Le tre leve valgono, misurate contro i loro pavimenti: **densi Q6_K → Q4_K
> −1,6…−2,6 ms (non lossless, rischio qualità reale, libera anche 841 MiB di VRAM ≈ 9 slot esperti
> per strato); fusione dei lanci −1,0…−1,9 ms (lossless da dimostrare, difficile; QKV e gate/up
> sono GIÀ fusi, il bersaglio vero sono le ~1.300 chiamate elementari delle connessioni `hc_`);
> kernel IQ2_S −1,4…−1,9 ms (lossless per costruzione, difficile).** Insieme: ~32 ms, ~31 t/s; con
> le sole lossless ~34 ms, ~29 t/s; nel caso più ottimista immaginabile ~28 ms, ~36 t/s.
> **I 50 t/s a 131k — 20,0 ms per token — sono sotto il pavimento dei soli byte (21,9 ms): non
> stanno in questo hardware con questo modello.** L'obiettivo onesto del token singolo è **30-33
> t/s**.
>
> *Regressioni.* Nessuna: nessun sorgente toccato, nessuna build, impronte identiche al riferimento.
>
> *Stato dei processi.* Nessun `llama-server`, nessun `nsys`, nessuna sessione nsys, porta 8100
> libera, nessuna build in corso.
>
> *Prossima azione.* **La leva 3 (il kernel IQ2_S)**, perché è lossless per costruzione, è la più
> grande inefficienza singola contro il proprio pavimento (2,54 ms sul solo `mul_mat_vec_q<iq2_s>`)
> e non tocca il bus. Ma **prima**, due cose che costano una corsa e non un ciclo di sviluppo:
> (a) misurare la **leva B di P8 su `T1`** — la patch esiste, è lossless, e qui si vede che a MTP
> spento toglierebbe 12 delle 14 copie di bias per token; (b) aprire una cella sui **due buchi da
> ~1 ms** di GPU inattiva, che valgono 1,9 ms per token, più della leva 1.

---

## 9. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/p9_anatomia_131k/P9_ANATOMIA_131K_15_SETTEMBRE.md` | questo esito |
| `avvia_p9_nsys.ps1` | guardia, `nsys launch`, corsa, chiusura, stato finale |
| `sonda_p9.py` | il client: stessa sequenza del banco, con le finestre di cattura dentro il decode |
| `analizza_nsys_p9.py` | scompone una cattura per forward, con il **controllo di integrità geometrico** |
| `composizione_gguf_p9.py` | legge le intestazioni dei tre shard e dà i byte per categoria |
| `pavimento_byte_p9.py` | il pavimento di byte per categoria alle bande misurate |
| `tabella_p9.py` | la tabella B: misurato contro pavimento, efficienza, spreco |
| `leve_p9.py` | l'aritmetica delle tre leve e il modello a due termini del matvec |
| `copia_log_p9.py` | porta in `log/` gli artefatti della corsa, ripuliti dalla chiave |
| `log/p9_banda_microbanco.txt` | VRAM 340,3 · PCIe 26,3 · CPU 33,4 GB/s |
| `log/p9_composizione.json` | i 1.224 tensori del GGUF con tipo, forma e byte |
| `log/p9_L01_nsys.md` / `.json` | la cattura **valida**: categorie e kernel per forward |
| `log/p9_L02_nsys.md` / `.json` | la cattura **invalida**, tenuta col suo controllo fallito |
| `log/p9_tabella_B.md` / `.json` | byte, pavimento, efficienza per categoria |
| `log/p9_leve.json` | banda effettiva, modello a due termini, leve, tetto |
| `log/p9_pavimento.json` | il pavimento calcolato dalla sola composizione |
| `log/p9_riepilogo.json`, `p9_results.jsonl`, `p9_client.log`, `p9_carico.jsonl` | la corsa |
| `log/p9_server_estratto.txt` | 260 righe del log del server (split, reserve, timing) |
| `log/p9_args.redacted.txt` | la riga di comando, chiave redatta |
| `D:\ds4_work\banco_p0_run\20260915_145054_P9_p9_anatomia_131k\nsys\` | i due `.nsys-rep` (17 MB) e i due `.sqlite` (45 MB): **non** copiati nel repository |
