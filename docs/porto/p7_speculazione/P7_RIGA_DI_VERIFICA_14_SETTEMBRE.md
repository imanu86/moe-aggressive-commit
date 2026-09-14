# P7 · cella 3 — il costo della riga di verifica MTP e la sua sovrapposizione col passo della testa — 14 settembre 2026

Cella di **diagnosi e progetto**. Nessuna patch applicata al motore, nessuna build, nessun commit.
Le corse sono **diagnostiche**, non banco: servono a scomporre un costo, non a produrre un t/s da
confrontare con 28,66. `bin_prod`, i sorgenti di `qwen38_clean`, il lanciatore quotidiano e i modelli
non sono stati toccati. Nessun processo residuo a fine cella (verificato).

---

## 0. Verdetto in sei righe

1. **I due controlli da dieci minuti danno entrambi esito negativo come "causa banale".**
   `get_mmvq_mmid_max_batch()` sulla nostra 3060 (sm_86 → tabella *turing_plus*) restituisce **7 per
   IQ2_S, 7 per IQ3_XXS, 8 (default) per IQ4_NL/Q4_K/Q5_K/Q6_K**: MMVQ è raggiungibile a 2 e a 3
   righe per tutti i quant del modello, nessun −1, nessun ripiego su dequant+GEMM (§2.1).
   E il batch di verifica a 2 righe **passa dalla cache esperti**: non c'è nessun cancello
   `max_batch` che la scavalchi — il percorso è obbligato da un `GGML_ASSERT` (§2.2).
2. **Sul binario di oggi la riga in più costa 15,66 ms** (era 16,51 il 10/9): la correzione del
   `concat` contiguo **è nel binario** e vale ~0,9 ms (§3).
3. **Il 60% di quei 15,66 ms sono byte sul PCIe, e il bus è già al soffitto.** Scomposizione nsys di
   oggi: `mul_mat_vec_q` +6,60 · `moe_grouped_gather_decode` +6,53 · `k_get_rows` (gather QSA) +1,73
   · H2D espliciti +1,14 (**termine nuovo, non nel profilo del 10/9**) · radix sort +0,73 · GPU
   inattiva +2,17. I contatori del device dicono che il gather muove **271,0 MiB per forward a 1
   riga e 411,2 a 2 righe**: **25,8 e 24,0 GiB/s**, e la copia DMA del bias QSA — meccanismo del
   tutto diverso — misura **23,6 GiB/s**. È il tetto pratico del PCIe 4.0 x16 (§3.2-3.3).
4. **Al momento della testa non è conoscibile nulla di utile.** Le rotte della prossima verifica
   dipendono da stati nascosti che quella passata non ha ancora calcolato; la sola informazione
   disponibile è quella della passata precedente, e la simulazione sulle tracce vere dice che
   **lo 0,00% dei miss del ciclo corrente sta fra gli esperti del ciclo precedente** — per
   costruzione, perché quelli sono residenti (§4).
5. **E anche con un oracolo la finestra non basta.** La testa dura 5,67 ms; alla banda misurata
   trasporta al massimo **136 MiB**, di cui ~50 se ne vanno per i suoi stessi esperti
   (2.550 MiB mappati / 512 esperti × 10 usati): restano **~86 MiB liberi contro i ~174 MiB** che
   la riga in più muove. Copertura massima **49%** (78% con bus del tutto libero), a fronte
   di un predittore che non esiste in quel punto del ciclo (§4.4).
   **La leva 2 della ricognizione — "prefetch della riga di verifica durante la testa" — si chiude qui.**
6. **L'alternativa che resta è muovere meno byte, non muoverli prima**, ed è la corsia CPU di
   P3/P4: sulle stesse tracce la riga in più muove **−84,6% di esperti**, cioè da +140,2 MiB a
   ~21,6 MiB, da +6,53 ms a ~1,0 ms di gather, al prezzo di 114,5 esperti/ciclo calcolati sulla CPU
   (2,39 per strato in media, p90 5, max 10). Aspettativa: **+2,2% se la corsia è per metà esposta,
   +9,7% se è coperta**; e la soglia di pareggio della seconda posizione di bozza scende da 0,633 a
   **0,501**, sotto lo 0,553 misurato in cella 1 (§5).

---

## 1. Metodo, strumenti, guardie

| | |
|---|---|
| macchina | RTX 3060 12 GB (sm_86, cc 860), Ryzen 5800X 16 thread, 96 GB DDR4, Windows 11 |
| binari misurati | `qwen38_clean\build\bin` — gli stessi di `preset_M1_p7.json`. `llama.dll` SHA256 `59A97335…` (13/9 08:39), `ggml-cuda.dll` `26BA28B4…` (13/9 12:57) |
| sorgenti letti | `qwen38_clean\source` (sola lettura). `D:\ds4_work\p3_work\source` letto per confronto, **non usato per misurare**: è un albero con l'ibrido CPU/GPU di P3/P4 dentro, mescolarlo all'MTP avrebbe reso non attribuibile ogni delta |
| strumento della misura | `paired_probe_prof.exe` (probe accoppiato di Codex + NVTX `w1`/`w2` + `cudaProfilerStart/Stop`), pilotato da `prova_verifica.py` del 10/9, ritrovati nello scratchpad della sessione del 10/9 e copiati nello scratchpad di questa. Checkpoint a **205.370 token** `qwen38_hybrid\long\f_trimfix_konly24_live262k_depth205k\long-context.bin`, 64 slot, ambiente identico a `preset_M1_p7` |
| profilatore | Nsight Systems 2024.5.1, `--trace=cuda,nvtx --cuda-graph-trace=node --capture-range=cudaProfilerApi` |
| simulatore | `docs/porto/p7_speculazione/simula_riga_p7c3.py` (nuovo) e `simula_cache.py` del 13/9, entrambi sulle rotte reali `routes.bin` (48 strati × 1024 token × k=10) |
| guardia | prima di ogni avvio: `Get-Process llama-server,paired_probe,paired_probe_prof` = 0 e porta 8100 libera (`netstat`). La guardia è dentro `prova_verifica.py` e aborta la corsa se trova un processo di inferenza. Nessun server di produzione toccato |

**Perché la misura è relativa e quindi robusta**: il probe esegue nello **stesso processo** prima la
fase `sequential` (forward a 1 riga) e poi la fase `batch` (forward a 2 righe) sullo stesso stato da
205k, e confronta i logit. `mismatch = 0` in tutte le corse: le due fasi producono gli stessi token.

### Corse eseguite

| tag | cosa | durata | esito |
|---|---|---:|---|
| `P7C3_T20_riferimento` | 1 riga contro 2 righe, senza profilatore | 208,6 s | valida, 0 mismatch |
| `P7C3_T21_profilo` | idem, sotto nsys | 219,7 s | valida, 0 mismatch |
| `P7C3_T22_contatori` | idem, con `LLAMA_MOE_HIT_REPORT=4` (contatori reali della cache) | 205,5 s | valida, 0 mismatch |
| `P7C3_T23_contatori_fini` | 8 token per fase, `LLAMA_MOE_HIT_REPORT=1`: serve a contare **quanti lanci di grafo fa un forward** a 1 e a 2 righe, senza il quale i contatori di T22 non si normalizzano | 203,7 s | valida, 0 mismatch |

Nessuna corsa invalida. Log puliti in `docs/porto/p7_speculazione/log/c3_*`.
Le quattro corse concordano sulla grandezza in esame: riga in più **15,66 · 16,03 (sotto
profilatore) · 15,99** ms.

---

## 2. A — i due controlli da dieci minuti

### 2.1 Che cosa restituisce `get_mmvq_mmid_max_batch()` da noi, e quale kernel gira a 2 e 3 righe

`ggml/src/ggml-cuda/mmvq.cu:257`:

```c
int get_mmvq_mmid_max_batch(ggml_type type, int cc) {
    if (GGML_CUDA_CC_IS_NVIDIA(cc)) {
        if (cc == GGML_CUDA_CC_VOLTA || cc >= GGML_CUDA_CC_ADA_LOVELACE) return MMVQ_MAX_BATCH_SIZE;
        if (cc >= GGML_CUDA_CC_TURING) return get_mmvq_mmid_max_batch_turing_plus(type);
        return get_mmvq_mmid_max_batch_pascal_older(type);
    }
    ...
```

La 3060 è `cc = 860`: `GGML_CUDA_CC_TURING = 750 ≤ 860 < GGML_CUDA_CC_ADA_LOVELACE = 890`
(`common.cuh:52-56`), quindi si prende **`get_mmvq_mmid_max_batch_turing_plus`**
(`mmvq.cu:149`), che elenca solo sette tipi e per tutti gli altri cade sul default
`MMVQ_MAX_BATCH_SIZE = 8` (`mmvq.cuh:3`):

| tipo | valore per sm_86 | serve 2 righe? | serve 3 righe? |
|---|---:|:--:|:--:|
| IQ2_S | **7** | sì | sì |
| IQ3_S | 6 | sì | sì |
| IQ3_XXS | **7** | sì | sì |
| MXFP4 | 7 | sì | sì |
| NVFP4 | 8 | sì | sì |
| Q2_K | 7 | sì | sì |
| Q3_K | 5 | sì | sì |
| **IQ4_NL** | **8** (default) | sì | sì |
| IQ4_XS, Q4_K, Q5_K, Q6_K, Q8_0, IQ2_XXS… | 8 (default) | sì | sì |

**Verdetto**: nessun tipo del nostro modello (UD-IQ3_XXS: mistura di IQ3_XXS / IQ4_NL / Q4_K / Q5_K
/ Q6_K / Q8_0 sui tensori non-esperti) scende sotto 5. **Non esiste il caso `−1` della issue
stamsam #2**: nel nostro albero nessun ramo restituisce valori negativi, e il minimo della tabella è
4. La spiegazione banale dei +6,6 ms di mmvq — "il MoE cade su dequantizza-a-F32 + GEMM" — **è
falsificata**.

**Quale kernel gira davvero a 2 e 3 righe**, per gate/up/down: `ggml_cuda_mul_mat_id`
(`ggml-cuda.cu:2135`) ha come **primo** controllo

```c
if (qwen_moe_demand::find(src0)) {
    GGML_ASSERT(ne2 <= 3 && ne2 <= get_mmvq_mmid_max_batch(src0->type, cc));
    ggml_cuda_mul_mat_vec_q(ctx, src0, src1, ids, dst);
    return;
}
```

cioè, per i tensori legati alla cache esperti, **MMVQ e basta**, a 1, 2 e 3 righe, senza possibilità
di ripiego. Confermato dal profilo: a 2 righe `mul_mat_vec_q` è ancora il kernel dominante
(25,5 ms, 593 lanci) e non compare nessun `mul_mat_q`, `mul_mat_f` sul percorso MoE né alcun
`dequantize_*`+cuBLAS (§3.1). Il numero di lanci `mul_mat_vec_q` passa da 545 a 593 (+48 = uno per
strato: la fusione gate/up resta, si aggiunge il `down`).

**Corollario sul tetto delle 3 righe**: l'assert combina `ne2 <= 3` (costante nostra) con la tabella.
Anche togliendo il `3` resterebbero **7** per IQ2_S/IQ3_XXS — quindi lato mmvq il muro vero non è la
tabella ma il `moe_grouped_plan_decode`, che rifiuta `n_routes > n_slots` cioè `10·righe > 64`,
**6 righe** (`fork-moe-kernels.cuh:288`, e l'assert gemello `moe-demand.cuh:231`).

### 2.2 Il batch di verifica a 2 righe passa dalla cache esperti o la scavalca?

**Passa. Non può scavalcarla.** Tre prove indipendenti.

**(a) Codice.** `qwen_moe_demand::remap()` (`moe-demand.cuh:225`) è chiamato una volta per strato e
riceve gli `ids` di **tutte** le righe: `const uint32_t routes = uint32_t(ids->ne[0]*ids->ne[1]);`
— cioè 10·righe. Il pianificatore e il gather sono lanciati con quel conteggio:

```c
moe_grouped_plan_decode<<<1, ..., ctx.stream()>>>(ids->data, routes, ids->ne[0], ...);
moe_grouped_gather_decode<false><<<blocks, ..., ctx.stream()>>>(..., routes ...);
```

Non c'è nessun cancello di tipo "sotto `max_batch` salta la cache": l'unico confronto con
`get_mmvq_mmid_max_batch` sul percorso della cache è dentro un `GGML_ASSERT`, che **aborta** invece
di scavalcare. Il rischio segnalato nella RFC #24528 (i batch di verifica sotto il gate scavalcano
la cache) **non si applica al nostro albero**. E il drafter non ci ruba colpi: il contesto della
bozza è creato con `n_moe_cache_slots = 0` (`common/speculative.cpp:2526`, commento nel sorgente:
*"light MTP draft: tiny ubatch (verification rows only), no expert cache of its own"*), quindi la
testa MTP **non ha cache e non sfratta nulla** dalla nostra.

**(b) Contatori reali del dispositivo.** `LLAMA_MOE_HIT_REPORT` legge `group->counters` dal device e
stampa `richiesti / mancanti / colpi / payload_bytes` sommati sui 48 gruppi; nel kernel del
pianificatore (`fork-moe-kernels.cuh:432-434`) `counters[0] += plan->n_unique` e
`counters[1] += plan->n_misses`, cioè **esperti unici del batch** e **miss unici**, non rotte.

La corsa `P7C3_T23_contatori_fini` riporta **a ogni lancio di grafo** e serve a contare quanti lanci
fa un forward: a 1 riga **1 lancio, esattamente 480 unici** (= 10,00 per strato, conferma che il
contatore è quello che credo); a 2 righe **3 lanci** (coerente con `graph splits = 4 (with bs=3)`
contro `2 (with bs=1)` nel log del server), con somme per forward di 684 · 737 · 722 · 838 unici,
cioè **15,53 unici per strato**. Con 20 rotte per strato il pianificatore ne trova ~15,5 distinte:
**vede entrambe le righe**. Se la seconda riga scavalcasse la cache, il contatore resterebbe a 480.

La corsa `P7C3_T22_contatori` (64 token per fase, rapporto ogni 4 lanci) dà i volumi:

| | 1 riga (fase `sequential`) | 2 righe (fase `batch`) | Δ riga in più |
|---|---:|---:|---:|
| forward | 80,8 | 32 | — |
| **unici per strato** | **10,00** | **16,47** | +6,47 |
| **miss per strato** | **2,98** | **4,53** | **+1,54** |
| miss per forward | 143,2 | 217,3 | +74,1 |
| **MiB trasferiti per forward** (1,8923 MiB/miss, dal `payload_bytes` del device) | **271,0** | **411,2** | **+140,2** |
| `moe_grouped_gather_decode` misurato (nsys) | 10,24 ms | 16,77 ms | +6,53 ms |
| **banda implicita** | **25,8 GiB/s** | **24,0 GiB/s** | **21,0 GiB/s** |

Il conteggio dei lanci per forward è il punto delicato: con 3 lanci per forward a 2 righe i 96 lanci
della fase `batch` sono 32 forward, e solo con quel divisore i 16,47 unici per strato tornano con la
simulazione (15,97) e la banda con il tetto del bus. È per questo che T23 esiste.

**(c) Simulazione contro misura.** La simulazione della politica esatta del pianificatore sulle
rotte vere (`routes.bin`, 48 strati × 1024 token × k=10) prevede **10,00 → 15,97 unici per strato**
e **2,44 → 4,19 miss per strato** passando da 1 a 2 righe. I contatori del device dicono
**10,00 → 16,47** e **2,98 → 4,53**. Le forme coincidono; lo scarto sui miss (+0,3…+0,5 per strato)
è atteso, perché la traccia è di un altro testo e di un'altra profondità.

**Perché non ho usato i binari patchati di P3/P4.** Il protocollo della cella li indicava come
sorgente dei contatori. Non sono serviti: i contatori che rispondono alla domanda — `n_unique` e
`n_misses` del pianificatore — **sono già nel binario pulito** dietro `LLAMA_MOE_HIT_REPORT`, e
usarli evita di mescolare in una stessa misura l'MTP e l'ibrido CPU/GPU di P3/P4, che cambia proprio
il percorso in esame (`moe-demand.cuh` di `p3_work` è un file diverso, ricompilato il 14/9 alle
13:05). Resta quindi **non verificato** se i contatori di P3/P4 funzionino con l'MTP acceso: non è
stato necessario chiederselo.

**Il drafter non ci ruba colpi** (l'altro avvertimento della RFC): i colpi cumulativi restano al
**71-73%** in entrambe le fasi.

---

## 3. B — anatomia della riga di verifica sul binario di oggi

### 3.0 Il numero

| corsa | 1 riga (ms) | 2 righe (ms) | **riga in più** | mismatch |
|---|---:|---:|---:|---:|
| 10/9 — T00 riferimento (prima della correzione `concat`) | 38,86 | 55,37 | 16,51 | 0 |
| 10/9 — T07 con `concat` contiguo | 38,89 | 54,52 | 15,63 | 0 |
| **14/9 — T20, binario attuale** | **39,25** | **54,91** | **15,66** | **0** |
| 14/9 — T21, stesso sotto nsys (sovraccarico del profilatore) | 40,65 | 56,68 | 16,03 | 0 |

**La correzione del `concat` contiguo è nel binario in uso.** Verificata in due modi: il sorgente
`src/models/qwen4exp.cpp:1613-1618` contiene ancora `if (!ggml_is_contiguous(x_t)) x_t =
ggml_cont(ctx0, x_t);` con il commento della correzione, e `llama.dll` (13/9 08:39) è **posteriore**
a `qwen4exp.cpp` (13/9 08:35); e il profilo di oggi non mostra più `concat_non_cont` ma
`concat_cont` + `cpy_scalar_transpose`, per un totale di **+0,24 ms** invece dei +1,2 di allora.

**Coerenza col banco M1.** Il modello di costo del banco dà
`ciclo = T1 + R + H = 40,93 + R + 5,67 = 62,37` → **R = 15,77 ms**, contro i 15,66 misurati qui.
Scarto **0,7%**. Attenzione: il probe misura a 205k e il banco fra 0 e 32k; l'accordo è in parte
fortunato (§3.3), ma il modello di costo regge.

### 3.1 Scomposizione nsys, oggi (media per forward, 60 forward a 1 riga, 28 a 2 righe)

| voce | 1 riga | 2 righe | **Δ** | 10/9 (Δ) |
|---|---:|---:|---:|---:|
| parete | 41,11 | 57,92 | **+16,80** | +17,8 |
| GPU occupata (unione dei kernel) | 37,76 | 52,39 | +14,63 | — |
| **GPU inattiva** | 3,36 | 5,53 | **+2,17** | +2,2 |
| `mul_mat_vec_q` | 18,91 | 25,51 | **+6,60** | +6,6 |
| `moe_grouped_gather_decode` (trasporto esperti) | 10,24 | 16,77 | **+6,53** | +6,4 |
| `k_get_rows` (gather QSA delle celle KV) | 1,76 | 3,49 | **+1,73** | +1,7 |
| radix sort (`OnesweepKernel`+`Histogram`) | 0,75 | 1,48 | +0,73 | +0,7 |
| `mul_mat_vec_f` | 1,66 | 1,97 | +0,31 | — |
| `moe_grouped_plan_decode` (pianificatore) | 0,53 | 0,82 | +0,30 | — |
| `flash_attn_ext_f16` | 0,27 | 0,52 | +0,25 | — |
| `concat_cont` + `cpy_scalar_transpose` | 0,11 | 0,35 | **+0,24** | +1,2 (`concat_non_cont`) |
| **H2D espliciti** | 0,53 ms / 11,3 MiB | 1,67 ms / 38,7 MiB | **+1,14 ms / +27,5 MiB** | *non misurato* |
| D2H | 0,04 | 0,08 | +0,04 | — |

Il file completo è in `log/c3_T21_profilo_nsys.txt`.

**Le due differenze rispetto al 10/9**: il `concat` non c'è più (−0,96 ms) e compare un termine che
allora non era stato guardato, gli **H2D espliciti**.

### 3.2 Il termine nuovo: 27,5 MiB di H2D per riga in più — ed è il bias QSA

Istogramma delle copie H2D per forward: **14 copie da 822.272 byte a 1 riga, 49 a 2 righe**
(il resto sono decine di byte). 822.272 / 4 = 205.568 float ≈ la profondità del checkpoint
(205.370, arrotondata): è il **bias per-cella della QSA**, `qsa->bias`, dichiarato ingresso di grafo
in `src/models/qwen4exp.cpp:854` come `ggml_new_tensor_3d(ctx0, GGML_TYPE_F32, n_kv, n_tps, n_stream)`
e `ggml_set_input`. Viene quindi **costruito sull'host e caricato per intero a ogni valutazione, una
riga di `n_kv` float per token e per gruppo di compressione**.

Conseguenze:
- costa **+1,14 ms e +27,5 MiB per la riga in più a 205k**;
- **cresce linearmente con la profondità del contesto**: a 262k sarebbe ~1,46 ms, a 32k ~0,18;
- è l'unico termine dei 15,66 ms che dipende da `n_kv`. Il gather QSA no: copia
  `indexer_top_k = 2048` celle, indipendenti dalla profondità.

### 3.3 Il conto dei byte: il trasporto è al soffitto del bus, non in attesa

| meccanismo | byte in più per riga | tempo in più | banda implicita |
|---|---:|---:|---:|
| `moe_grouped_gather_decode` (esperti, host mappato → VRAM) | **140,2 MiB** (contatori del device, §2.2b) | 6,53 ms | **21,0 GiB/s** |
| `cudaMemcpyAsync` H2D (bias QSA) | **27,5 MiB** (nsys) | 1,14 ms | **23,6 GiB/s** |
| `k_get_rows` (2048 celle KV da cache host-mappata, 136+136 B/cella × 12 strati) | ~6,5 MiB | 1,73 ms | 3,7 GiB/s |
| **totale trasporto** | **~174 MiB** | **9,40 ms (60% della riga)** | — |

E in assoluto, non solo sul delta: il gather muove **271,0 MiB in 10,24 ms a 1 riga (25,8 GiB/s)** e
**411,2 MiB in 16,77 ms a 2 righe (24,0 GiB/s)**.

I primi due meccanismi sono **completamente diversi** (un kernel che legge memoria host mappata, e
una copia DMA del driver) e misurano **la stessa banda, 21-26 GiB/s**. È il tetto pratico del
PCIe 4.0 x16 di questa macchina, coerente col valore già nel registro (DMA misurato 24,4 GiB/s,
`prefetch-falsificato-sfratto-vale-23-punti`; PCIe 4.0 x16 = 29,3 GiB/s teorici).

> **Il fatto che decide questa cella: i 6,5 ms di trasporto della riga di verifica non sono latenza
> esposta, sono byte a banda satura.** Non si spostano nel tempo: si tolgono soltanto non muovendoli.

Il terzo meccanismo invece **non** è al soffitto: `k_get_rows` fa 6,5 MiB in 1,73 ms, cioè 3,7 GiB/s,
il 16% del bus. È letture sparse da 272 byte su memoria host mappata: lì c'è margine (§5.3).

---

## 4. C — che cosa è conoscibile quando gira la testa

Ordine reale del ciclo, dal sorgente: `tools/server/server-context.cpp:3056-3066` chiama
`common_speculative_draft()` (la testa) **subito prima** che il batch di verifica venga costruito e
decodificato (`:3700`). La testa dura **5,67 ms** (M1: 49,99 s / 8.811 chiamate) ed è il solo
momento del ciclo in cui il tronco non sta girando.

### 4.1 (i) Riga 1 della prossima verifica = token appena accettato → **NON nota**

Il batch di verifica di una passata è `[t_ultimo_accettato, d_abbozzato]`. La riga 1 è un token che
**non è mai stato propagato nel tronco**: le sue rotte allo strato *L* sono `top10(W_gate[L]·h[L])`
dove `h[L]` è prodotto dagli strati 0…L−1 **di quella stessa passata**, che al momento della testa
non è iniziata. Non c'è alcun riuso dalla passata precedente: la riga 2 di allora (la bozza) è stata
sì propagata, ma il token che ne esce è quello *successivo*, e la riga 1 di adesso è il token
*accettato*, la cui KV esiste ma i cui stati intermedi sono stati consumati e non conservati.

Vale identicamente per la riga 2 (la nuova bozza), che al momento della testa **non esiste ancora**:
è la testa a produrla.

### 4.2 (ii) Le rotte della testa MTP stessa → note, ma **su un'altra cache, anzi su nessuna**

La testa **è** un blocco MoE: il modello di bozza dichiara `n_expert = 512`, `n_expert_used = 10`,
identici al tronco (log M1, righe 320-322). Ma:

- i suoi tensori esperti sono quelli del **modello di bozza**, caricati in
  `CUDA0_Mapped model buffer size = 2550.00 MiB` (log M1, riga 363), cioè **memoria host mappata,
  letta a zero-copy dai kernel**: ~4,98 MiB per esperto, **~49,8 MiB per token abbozzato**;
- il contesto della bozza ha **`n_moe_cache_slots = 0`** (`common/speculative.cpp:2526`): la testa
  **non usa la cache esperti**, non ci mette niente e non ne sfratta niente.

Quindi: conoscere le rotte della testa non aiuta la verifica (insieme di pesi diverso), e in
compenso la testa **consuma già ~40% del bus** durante i suoi 5,67 ms. È il vincolo di §4.4.

### 4.3 (iii) Predizione dallo strato precedente → **non applicabile al momento della testa**

Il predittore del registro (`predittore-route-gate-strato-dopo`, 71% di recall) è
`previsione = top6(W_gate[L+1] · h[L])`: richiede **`h[L]` della passata che si vuole predire**.
Al momento della testa quella passata non è iniziata e nessun `h[L]` esiste. L'unico stato
disponibile è quello della passata precedente, e su questo la simulazione dà il numero che chiude
la questione:

| simulazione sulle rotte vere | 1 riga | 2 righe | 3 righe |
|---|---:|---:|---:|
| unici per strato (*misurati*) | 10,00 (*10,00*) | 15,97 (*16,47*) | 21,13 |
| **trasferiti per strato** (*misurati*) | 2,44 (*2,98*) | 4,19 (*4,53*) | 5,59 |
| trasferiti per ciclo | 117,1 | 200,9 | 268,1 |
| **miss del ciclo già presenti fra le rotte del ciclo precedente** | **0,00%** | **0,00%** | **0,00%** |

Lo zero è **strutturale, non statistico**: un esperto usato nel ciclo precedente è residente per
costruzione (la cache lo ha appena ammesso), quindi non può essere un miss adesso.
**Un prefetch basato sulla passata precedente non porta un solo byte utile**: porterebbe solo copie
di cose già in VRAM, e per farle sfratterebbe residenti vivi — cioè esattamente il meccanismo già
falsificato due volte nel registro (`prefetch-piu-anticipo-meno-colpi`,
`prefetch-falsificato-sfratto-vale-23-punti`, dove la cella "rifiutate_pressione 19.885 su 40.965"
diceva che non c'è spazio).

Il predittore resta utilizzabile **dentro** la passata (§4.5), non prima.

### 4.4 La finestra della testa non basta nemmeno con un oracolo

| grandezza | valore |
|---|---:|
| durata della testa | 5,67 ms |
| banda misurata del trasporto | 24,0 GiB/s |
| **capacità massima della finestra** (bus interamente libero) | **136 MiB** |
| traffico proprio della testa (10 esperti × 4,98 MiB, zero-copy dai 2.550 MiB mappati) | ~49,8 MiB |
| **capacità libera realistica** | **~86 MiB** |
| byte che la riga in più muove | **~174 MiB** (140 esperti + 27,5 bias + 6,5 KV) |
| **copertura massima** | **78% con bus libero · 49% realistica** |

Anche nell'ipotesi irrealizzabile "conosciamo esattamente i miss futuri e il bus è vuoto", la
finestra copre al massimo 136/174 = 78% dei byte, cioè ~7,3 dei 9,4 ms di trasporto; realisticamente
~4,6 ms. E quella conoscenza **non esiste** (§4.1-4.3).

Per completezza, il valore di quel limite superiore irrealizzabile: risparmiando 4,6 ms,
`R = 11,2 ms`, ciclo 57,8 ms, 32,33 ms/token, **30,93 t/s (+7,9%)**. È il tetto di una leva che non
ha un meccanismo — e va confrontato con la §5.1, che ottiene lo stesso ordine di grandezza con un
meccanismo che esiste. **Non vale una cella.**

### 4.5 (iv) Sovrapposizione dentro la passata — esiste in parte, e il resto costa byte

Cosa esiste **già**, letto nel sorgente (`moe-demand.cuh:243-270`):

- un **secondo stream per gruppo** (`transfer_stream`) con eventi `gate_ready`/`down_ready`, attivo
  quando `QWEN_MOE_OVERLAP_DOWN=1` — **ed è acceso** in `preset_A` e in `preset_M1_p7`;
- con quella leva, il trasferimento del banco **`down`** è emesso sullo stream secondario e atteso
  solo quando serve, cioè **è già sovrapposto** al calcolo di gate/up dello stesso strato;
- il trasferimento di **gate+up** (i due terzi dei byte) è invece emesso su `ctx.stream()`
  **immediatamente prima** della `mul_mat_vec_q` che li consuma: **completamente esposto**.

Cosa **non** esiste: nessuna sovrapposizione **fra strati**. Il pianificatore dello strato *L* può
girare solo dopo il router di *L*, che a sua volta gira dopo l'attenzione di *L*. Fra "rotte di *L*
note" e "mmvq di *L* le usa" il tempo disponibile è **zero**.

Il solo modo di creare anticipo dentro la passata è predire le rotte di *L+1* da `h[L]` e far
partire il trasferimento durante l'attenzione di *L+1*. Conti:

| | valore |
|---|---:|
| byte di miss per strato a 2 righe (contatori) | 4,53 × 1,8923 = 8,57 MiB → **0,35 ms** di bus |
| tempo per strato non-MoE disponibile a coprirlo | 57,9/48 − 0,35 (gather) − 0,53 (mmvq) ≈ **0,33 ms** |
| recall del predittore (registro 5/8) | **71%** |
| byte in più mossi dalle previsioni sbagliate | ~2,9 esperti/strato = **+64% di traffico** |

La finestra c'è ed è esattamente della taglia giusta — ma il predittore la riempie di byte inutili
in proporzione al suo errore, **su un bus che nella fase MoE è già al soffitto**. In aggregato il
bus è occupato per 16,8 ms su 57,9 (29%), quindi lo spazio ci sarebbe; **per strato** no: si
coprirebbero al più 0,33 ms di trasporto con 0,33 ms di calcolo, mentre il traffico salirebbe a
0,56 ms/strato. Aspettativa: **negativa o nulla**, e con l'aggravante dello sfratto (§4.3).

### 4.6 Riepilogo di C

| opzione | conoscibile? | ms dei 6,5 copribili | rischio di sfratto |
|---|---|---:|---|
| (i) rotte della riga 1 della prossima verifica | **no**, dipendono da stati non ancora calcolati | 0 | — |
| (ii) rotte della testa MTP | sì, ma **altro insieme di pesi e nessuna cache** | 0 | nullo (non tocca la cache) |
| (iii) predittore dello strato precedente, al momento della testa | **no**: non esiste `h[L]` della passata futura. Ripiegando sul ciclo precedente: **0,00% di copertura misurata** | 0 | **alto**: sfratta residenti vivi |
| (iii-bis) stesso predittore **dentro** la passata | sì, 71% di recall, una finestra di 0,33 ms/strato | ≤ 0,33/strato, ma +69% di byte | alto |
| (iv) sovrapposizione dentro la passata | **`down` già sovrapposto** (`QWEN_MOE_OVERLAP_DOWN=1`); gate+up esposti ma senza anticipo disponibile | 0 senza predizione | — |

**Conclusione onesta: al momento della testa non è conoscibile nulla di sicuro, e la predizione
disponibile ha copertura misurata dello 0%. La leva 2 della ricognizione è chiusa.**

---

## 5. D — progetto della cella 4

Poiché C chiude la leva del prefetch, questa sezione propone **l'alternativa migliore sul costo
della riga**, ordinata per aspettativa/costo. Nessuna patch è stata applicata.

### 5.1 Proposta principale — togliere byte alla riga di bozza con la corsia CPU (P3/P4)

**Perché è questa.** Il 60% della riga sono byte a banda satura (§3.3) e il 43% è il solo trasporto
degli esperti. L'unica cosa che si può fare a byte saturi è **non muoverli**. Gli esperti che la
riga di bozza pretende e che non sono residenti sono esattamente quelli che non vale la pena
portare: servono a **una** riga, per **un** token che ha il 21,5% di probabilità di essere rifiutato.

**Il meccanismo esiste già** ed è quello di P3/P4 (`LLAMA_MOE_CPU*` in
`D:\ds4_work\p3_work\source\ggml\src\ggml-cuda\moe-demand.cuh` e `src/llama-moecpu.cpp`): gli
esperti non residenti richiesti **dalle sole righe oltre la prima** non vengono ammessi in cache né
trasferiti, e la loro FFN è calcolata sulla CPU, sommata al residuo con una guardia.

**Numeri, sulle stesse tracce reali** (`simula_cache.py --accept 0.785`, uscita in
`log/c3_sim_cpulane_accept0785.json`):

| scenario (simulazione) | trasferiti/ciclo | Δ rispetto a 1 riga | esperti su CPU/ciclo |
|---|---:|---:|---:|
| 1 riga (MTP spento) | 117,1 | — | 0 |
| 2 righe, tutto su GPU (**oggi**) | 200,9 | **+83,8 esperti** | 0 |
| **2 righe, corsia CPU sulla riga di bozza** | **130,0** | **+12,9 esperti (−84,6%)** | **114,5** (2,39/strato, p90 5, max 10) |
| 3 righe, corsia CPU | 135,9 | +18,8 esperti | 248,7 (5,18/strato) |

La simulazione va usata come **rapporto**, non in assoluto (i suoi miss sono il 18% più bassi dei
contatori veri, §2.2c). Applicando il −84,6% al Δ misurato di **140,2 MiB per riga**:
la riga in più passerebbe da 140,2 a **~21,6 MiB**, cioè **−118,6 MiB = −5,5 ms** di gather
(a 21,0 GiB/s).

**Aspettativa numerica**, col modello di costo del banco (`ciclo = T1 + R + H`, `T1 = 40,93`,
`H = 5,67`, `R_oggi = 15,77`, 1,788 token/ciclo, B = 28,66 t/s):

| ipotesi sulla corsia CPU | R | ciclo | ms/token | **t/s** | Δ su B |
|---|---:|---:|---:|---:|---:|
| gather −5,5 ms, CPU **interamente coperta** | 10,27 | 56,87 | 31,81 | **31,44** | **+9,7%** |
| gather −5,5 ms, CPU **per metà esposta** (+4,2 ms) | 14,47 | 61,07 | 34,16 | **29,28** | **+2,2%** |
| gather −5,5 ms **e** mmvq −2,0 (meno unici per strato: 16,47 → ~13,5) | 8,27 | 54,87 | 30,69 | **32,59** | **+13,7%** |

Il termine `mmvq` è un *upside* e non va messo nel cancello: la riga centrale, **+2,2%**, è
l'aspettativa conservativa; la prima, **+9,7%**, è il bersaglio.

**Effetto collaterale che vale quanto la leva**: con `R = 10,27` la soglia di pareggio della seconda
posizione di bozza scende da 0,633 a **(H + R)/ms-per-token = 15,94/31,81 = 0,501**, sotto lo 0,553
misurato in cella 1. **La bozza a 2 token tornerebbe redditizia**, e la simulazione dice che con la
corsia CPU la terza riga costa quasi nulla in byte (+5,9 esperti): è la via per uscire dal muro di
cella 1 senza toccare l'accettazione.

**File e righe da toccare** (nessuna modifica fatta):

| file | cosa |
|---|---|
| `ggml/src/ggml-cuda/moe-demand.cuh:225-270` (`remap`) | separare le rotte della **riga 0** da quelle delle righe 1..k: solo le prime entrano nel piano di ammissione |
| `ggml/src/ggml-cuda/fork-moe-kernels.cuh:175` (`moe_grouped_plan_decode`) | nuovo parametro `n_routes_admit ≤ n_routes`: le rotte oltre la soglia sono risolte se residenti, altrimenti marcate "CPU" senza scegliere una vittima |
| `src/llama-moecpu.cpp` (albero P3) | l'esecutore esiste già; va indirizzato sulle righe di bozza invece che su un elenco di strati |
| `src/models/qwen4exp.cpp:1077` | l'assert `top_k->ne[1] <= 3` resta invariato: questa leva non allunga la bozza |

**Invarianti della cache da rispettare** (letti nel sorgente, sono i vincoli veri del progetto):

1. **Ammissione solo su trasferimento completato.** `slot_for_expert`/`expert_for_slot` sono
   aggiornati **alla chiamata successiva**, in testa al pianificatore
   (`fork-moe-kernels.cuh:216-255`, "*Commit the prior admission before this call overwrites the
   shared plan*"). Qualunque modifica deve preservare questo differimento: se le righe di bozza
   marcate "CPU" toccassero `miss_experts`/`miss_slots`, il commit differito ammetterebbe esperti
   mai trasferiti — **residente fantasma**, il difetto n.1 di P1.
2. **Un solo piano per strato.** `group->plan` è unico; niente può girare fra un piano e il suo
   commit. Un eventuale prefetch avrebbe bisogno di un secondo piano, non di riusare questo.
3. **La vittima non può essere uno slot usato nella chiamata corrente** (`route_storage[slot]==0`,
   `:455`). Con la corsia CPU la regola va estesa: un esperto della riga di bozza **residente** deve
   restare protetto dallo sfratto per tutta la chiamata, altrimenti la riga 0 e la riga 1 possono
   scegliersi a vicenda la vittima.
4. `n_routes ≤ n_slots` e `ids->ne[1] ≤ 3` restano (`moe-demand.cuh:231`, `fork-moe-kernels.cuh:288`).
5. **Frequenza e LRU non devono contare le righe di bozza**: se un esperto usato solo dalla bozza
   aggiornasse `frequency`/`last_used`, la politica si sposterebbe verso token che potrebbero essere
   rifiutati. (Nel simulatore questa scelta è già quella modellata.)

**Come si misura.** Banco M1 (`preset_M1_p7.json`, profilo `solo_libero`, greedy, seed 1234,
budget 1024, 64 slot), riferimento **B = 28,66 t/s**, e le impronte SHA256 devono restare identiche
a quelle di M1 sul sottoinsieme `ctx32k` (8 su 8) — la corsia CPU calcola la stessa FFN, quindi il
testo **non deve cambiare**: è il cancello di correttezza. Criterio di successo **sul costo della
riga, non sui t/s**: `R = ciclo − T1 − H` deve scendere **sotto 13 ms**; se non scende, la leva è
morta e si chiude senza sweep. Poi, e solo poi, si rimisura la bozza a 2 token contro la soglia di
pareggio ricalcolata.

**Rischi.** (a) La corsia CPU è già un cantiere aperto (P3/P4) con i suoi difetti: questa cella non
deve duplicarlo ma **comporsi** con esso. (b) La CPU è a 16 thread e nel regime lungo è già
occupata: `p90 = 5` e `max = 10` esperti per strato significano code, e il costo per strato è
**serializzato** con quel strato. (c) Se la guardia di merge non è a costo zero, mangia il
guadagno (è il fronte `LLAMA_MOE_CPU_GUARD_LIGHT` di P4).

### 5.2 Seconda proposta, indipendente e piccola — deduplicare il gather QSA fra le righe

`k_get_rows` costa **+1,73 ms per riga** e muove solo ~6,5 MiB: **3,7 GiB/s, il 16% del bus**. Non
è un problema di byte ma di letture sparse da 272 byte su memoria host mappata, ripetute **per
riga**: `gather_query` (`src/models/qwen4exp.cpp:1088-1130`) è chiamata una volta per token e
raccoglie `indexer_top_k = 2048` celle ciascuna.

Le due righe sono **posizioni adiacenti**: le loro selezioni top-2048 si sovrappongono molto (quanto,
va misurato — è l'unico dato mancante). Raccogliere **l'unione una sola volta** e indicizzarla per
riga toglierebbe la parte comune. Se la sovrapposizione fosse l'80%, si risparmierebbero ~1,4 ms:
ciclo 60,97 → 34,10 ms/token → **29,33 t/s (+2,3%)**, greedy-lossless, patch locale.

**Prima di progettarla serve una misura di dieci minuti**: strumentare `indexer_top_k` (già
etichettato con `cb(top_k, "indexer_top_k", il)`, `:1014`) e contare l'intersezione fra le due righe
su qualche centinaio di passate. Se la sovrapposizione è sotto il 50%, la leva non vale.

### 5.3 Terza proposta — il bias QSA non va ricaricato dall'host a ogni riga

+1,14 ms e 27,5 MiB per riga **a 205k**, e **cresce col contesto** (§3.2). Due strade, entrambe
locali a `src/models/qwen4exp.cpp:854`:
(a) dichiarare il bias in **F16** invece che F32 → −50% di byte, ~−0,57 ms/riga a 205k;
(b) costruirlo **sul dispositivo** dalle strutture che già ci sono, togliendo del tutto la copia.
Irrilevante sul banco a 32k (~0,18 ms), **rilevante sul servizio a 131-262k**, dove è il termine che
peggiora con la profondità. Da tenere per la fase lunga, non per la cella 4.

### 5.4 Che cosa NON proporre

- **Prefetch durante la testa** (leva 2 della ricognizione): chiusa in §4. Motivo primario: al
  momento della testa non è conoscibile nulla; motivo indipendente e sufficiente: anche con un
  oracolo la finestra copre al massimo il 42-68% dei byte, e i byte sono già a banda satura.
- **Forzare MMQ su `MUL_MAT_ID`**: a monte l'hanno misurato −38/−62% sul MoE (PR #26079); e da noi
  la tabella non è il collo (§2.1).
- **Spegnere la precisione** (`QWEN_MOE_SCALAR_BATCH`, `QWEN4EXP_INDEXER_F32_BATCH`): misurata il
  10/9 a **−1,85 ms/riga** (T08 = 13,81), ma rompe l'identità bit-a-bit fra la riga di verifica e il
  decode a riga singola, cioè **cambia il testo accettato**. Fuori dal cancello del banco.
- **Allungare la bozza** senza prima abbassare R: chiuso in cella 1, e §5.1 spiega che l'ordine
  giusto è prima la riga, poi la lunghezza.
- **PR #28549 / am17an #45 (grafi CUDA della bozza)**: nel nostro albero la chiave del grafo è sì il
  solo primo nodo (`ggml_cuda_graph_get_key`, `ggml-cuda.cu:2820`), ma la cache è **per chiave** con
  `warmup_complete` per grafo, e il contatore del banco dice `graphs reused = 8.715` su ~8.805
  passate di verifica: **il grafo è riusato quasi sempre**, la forma del batch di verifica è fissa
  a 2 righe e non oscilla. Il difetto descritto a monte non ci morde. I +2,17 ms di GPU inattiva
  hanno un'altra causa e meritano una cella loro, non una patch presa a prestito.

---

## 6. Difetti di questa cella

1. **Il probe misura a 205k, il banco M1 fra 0 e 32k.** L'accordo fra `R` misurato (15,66) e `R`
   dedotto dal banco (15,77) è a 0,7%, ma un solo termine su sei scala con la profondità (§3.2):
   parte dell'accordo è fortuito. La scomposizione è comunque valida **come scomposizione**.
2. **Una sola replica per corsa.** Le tre corse concordano fra loro (15,66 / 16,03 sotto
   profilatore / stessa fase `sequential` a 39,25-40,65) ma non è stato calcolato un intervallo.
3. **I 140,2 MiB della riga in più dipendono da un conteggio di forward ricostruito.** I contatori
   del device sono cumulativi e il rapporto avviene ogni N **lanci di grafo**, non per forward; a 2
   righe un forward fa 3 lanci (T23). Con il divisore sbagliato (48 invece di 32) verrebbero
   10,98 unici per strato e una banda di 15,9 GiB/s — valori che né la simulazione né il tetto del
   bus sostengono. Il divisore giusto è quello che rende coerenti tre cose indipendenti (unici
   simulati, rapporto dei tempi di gather, banda), ma **non è stato letto da un contatore di
   forward**: è la fragilità principale di §2.2b. Un contatore `n_forward` nel rapporto la
   toglierebbe in tre righe.
4. **La sovrapposizione delle selezioni QSA fra le due righe non è misurata**: la proposta §5.2 ha
   un'aspettativa condizionata a un numero che non ho.
5. **La corsia CPU è simulata con la politica del pianificatore, non con l'esecutore vero.** Il
   costo per esperto sulla CPU viene dalla memoria del 10/9 (0,074-0,08 ms) e non è stato rimisurato
   qui, e il grado di copertura è l'ipotesi che separa +2,2% da +9,7%.
6. **Le rotte `routes.bin` sono del 10/9, catturate a 1 riga e a una sola profondità.** Gli scenari a
   2 e 3 righe sono ricostruiti mettendo in batch token consecutivi della stessa traccia: è
   l'approssimazione già usata il 13/9, e assume che le rotte di un token non cambino perché è
   valutato insieme al precedente (vero: la verifica è esatta e i token sono gli stessi).

---

## 7. Bozza di voce di registro

> **14 settembre 2026 — fase P7, cella 3: il costo della riga di verifica MTP e la finestra della
> testa.**
>
> *Ipotesi.* I 6,4 ms di trasferimenti esperti della riga di verifica si possono nascondere dietro i
> 5,5 ms del passo della testa MTP, portando la riga sotto i 14 ms e rendendo redditizia la bozza a
> 2 token (leva 2 della ricognizione del 14/9, ispirata a SP-MoE e DraftExpert).
>
> *File toccati.* Nuovi: `docs/porto/p7_speculazione/P7_RIGA_DI_VERIFICA_14_SETTEMBRE.md`,
> `docs/porto/p7_speculazione/simula_riga_p7c3.py`,
> `docs/porto/p7_speculazione/log/c3_*`. **Nessun sorgente del motore modificato, nessuna build,
> nessun commit.** `bin_prod`, `qwen38_clean\source`, lanciatore quotidiano e modelli invariati.
>
> *Configurazioni.* Binari `qwen38_clean\build\bin` (`llama.dll 59A97335`, `ggml-cuda.dll 26BA28B4`).
> Probe accoppiato `paired_probe_prof.exe` sul checkpoint a 205.370 token, 64 slot, ambiente
> identico a `preset_M1_p7.json` meno `LLAMA_MTP_LIGHT`. Quattro corse: T20 (riferimento), T21 (nsys
> `--trace=cuda,nvtx`), T22 (`LLAMA_MOE_HIT_REPORT=4`), T23 (`LLAMA_MOE_HIT_REPORT=1`, per contare i
> lanci di grafo per forward). Simulazioni sulle rotte reali `routes.bin` (48 strati × 1024 token ×
> k=10) con la politica esatta di `moe_grouped_plan_decode`.
>
> *Run validi / invalidi.* Quattro corse valide, zero invalide, `mismatch = 0` in tutte,
> nessun processo residuo, porta 8100 mai occupata.
>
> *Risultato e limite.* **L'ipotesi è falsificata, per due ragioni indipendenti.** (1) Al momento
> della testa non è conoscibile nulla: le rotte della prossima verifica dipendono da stati nascosti
> che quella passata non ha ancora calcolato, e sulla sola informazione disponibile — la passata
> precedente — la copertura misurata dei miss futuri è **0,00%** (strutturale: quegli esperti sono
> residenti). (2) Anche con un oracolo la finestra non basta: 5,67 ms a 24,0 GiB/s sono **136 MiB**
> di capacità, ~86 liberi una volta tolto il traffico della testa stessa (10 esperti × 4,98 MiB dai
> 2.550 MiB mappati del modello di bozza), contro i **~174 MiB** che la riga in più muove.
> In compenso la cella produce l'anatomia aggiornata: la riga in più costa oggi **15,66 ms**
> (era 16,51 il 10/9; la correzione del `concat` contiguo è nel binario e vale 0,9 ms), e si
> scompone in `mul_mat_vec_q` +6,60 · gather esperti +6,53 · `k_get_rows` QSA +1,73 · **H2D del bias
> QSA +1,14 (termine nuovo, scala con la profondità)** · radix sort +0,73 · GPU inattiva +2,17.
> **Il 60% della riga è trasporto, e il trasporto è a banda satura**: i contatori del device danno
> 271,0 MiB per forward a 1 riga e 411,2 a 2 righe, cioè 25,8 e 24,0 GiB/s sul kernel di gather, e
> la copia DMA del bias QSA — meccanismo indipendente — 23,6 GiB/s: è il tetto del PCIe 4.0 x16.
> I due controlli da dieci minuti sono entrambi negativi: `get_mmvq_mmid_max_batch` dà 7/7/8 per
> IQ2_S/IQ3_XXS/IQ4_NL su sm_86 (MMVQ raggiungibile a 2 e 3 righe, nessun −1), e il batch a 2 righe
> **passa dalla cache** — contatore `plan->n_unique` a 480 per forward a 1 riga (10,00 per strato) e
> a ~790 a 2 righe (16,47 per strato), cioè il pianificatore vede entrambe le righe; non esiste il
> cancello `max_batch` della RFC #24528 nel nostro albero, e il contesto della bozza ha
> `n_moe_cache_slots = 0`, quindi la testa non sfratta nulla. Limiti: probe a 205k contro banco a
> ≤32k; una replica per corsa; il numero di forward della fase a 2 righe è ricostruito dal numero di
> lanci di grafo, non letto da un contatore.
>
> *Decisione.* **Leva "prefetch della riga di verifica durante la testa": NON si apre.** Chiusa per
> assenza di informazione conoscibile e, indipendentemente, per capienza della finestra.
>
> *Prossima azione.* Cella 4 = **comporre la corsia CPU di P3/P4 con le righe di bozza dell'MTP**:
> gli esperti non residenti richiesti dalle sole righe oltre la prima non si trasferiscono e non si
> ammettono, si calcolano sulla CPU. Sulle tracce vere gli esperti trasferiti in più per la riga di
> bozza calano dell'**84,6%** (da +140,2 a ~21,6 MiB misurati) al prezzo di 114,5 esperti/ciclo
> sulla CPU (2,39 per strato, p90 5, max 10). Cancello sul **costo della riga**, non sui t/s:
> `R = ciclo − T1 − H` sotto **13 ms**, impronte `ctx32k` identiche a M1. Aspettativa: **+2,2%** se
> la corsia è per metà esposta, **+9,7%** se coperta; e come effetto collaterale la soglia di
> pareggio della seconda posizione di bozza scende da 0,633 a **0,501**, sotto lo 0,553 misurato in
> cella 1.

---

## 8. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/p7_speculazione/simula_riga_p7c3.py` | simulatore della riga: byte per ciclo a 1/2/3 righe, banda implicita, copertura del ciclo precedente |
| `docs/porto/p7_speculazione/log/c3_sim_riga.json` | uscita del simulatore (accettazione 0,785) |
| `docs/porto/p7_speculazione/log/c3_sim_cpulane_accept0785.json` | `simula_cache.py` del 13/9 rieseguito con l'accettazione misurata: scenari con e senza corsia CPU |
| `docs/porto/p7_speculazione/log/c3_T20_riga_in_piu.json` | riga in più sul binario attuale, senza profilatore |
| `docs/porto/p7_speculazione/log/c3_T21_profilo_nsys.txt` | scomposizione nsys completa 1 riga contro 2 righe |
| `docs/porto/p7_speculazione/log/c3_T21_summary.json` | riepilogo della corsa profilata |
| `docs/porto/p7_speculazione/log/c3_T22_contatori.txt` | contatori reali della cache esperti: T22 (ogni 4 lanci, 64 token) e T23 (ogni lancio, 8 token) |
| `docs/porto/p7_speculazione/log/c3_T22_summary.json` | riepilogo della corsa con i contatori |
| `<scratchpad>/p7c3/prove/P7C3_T2{0,1,2,3}_*` | corse complete (config, manifest, stdout/stderr, `verifica.sqlite`) |

Comandi per riprodurre:

```
# 1 riga contro 2 righe sul binario attuale
python prova_verifica.py --tag T20 --width 2 --tokens 64

# stesso con profilo nsys + scomposizione
python prova_verifica.py --tag T21 --width 2 --tokens 64 --profile
python analizza_nsys.py prove\T21\verifica.sqlite

# contatori reali della cache (volumi) e conteggio dei lanci per forward
python prova_verifica.py --tag T22 --width 2 --tokens 64 --env LLAMA_MOE_HIT_REPORT=4
python prova_verifica.py --tag T23 --width 2 --tokens 8 --warm 4 --env LLAMA_MOE_HIT_REPORT=1

# byte per ciclo e conoscibilita' dal ciclo precedente
python docs\porto\p7_speculazione\simula_riga_p7c3.py --routes docs\porto\strumenti_qwen38_13settembre\routes.bin

# scenari con corsia CPU, all'accettazione misurata
python simula_cache.py --routes routes.bin --accept 0.785
```
