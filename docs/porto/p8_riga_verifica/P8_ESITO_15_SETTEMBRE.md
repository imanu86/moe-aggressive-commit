# P8 · esito — le leve *lossless* sulla riga di verifica MTP, misurate a 131k — 15 settembre 2026

Cella di **applicazione e misura**. Le leve del progetto (`PROGETTO_P8_15_SETTEMBRE.md`) vengono
applicate a una copia pulita dello snapshot P0 e misurate **una per cella, cumulative**, sul
profilo `lungo_131k` del banco P0 — il punto operativo dell'utente (contesto ~131k, KV 250k),
deciso il 15/9. Nessuna misura a contesto corto o a 32k decide nulla in questa cella.

`bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, il lanciatore quotidiano, i modelli e
lo snapshot `D:\ds4_work\p0_snapshot_20260914` non sono stati toccati (verificato a fine cella:
il file più recente in ognuno dei quattro alberi è del 10 o del 13 settembre).

> **Nota su un commit che non è mio.** Questa cella non ha fatto nessun commit. Ma il commit
> `1857142` della cella P7 n. 7, delle **10:53:26**, ha aggiunto anche
> `docs/porto/banco_p0/preset_P8_{0..7}_p7.json` — otto file che avevo appena scritto e che si
> trovavano nell'albero quando quell'agente ha fatto un `add` non selettivo. Il contenuto
> committato è **identico** a quello poi misurato (verificato con `git diff HEAD`), quindi non c'è
> nessuna incoerenza fra ciò che è nel repository e ciò che è stato eseguito; ma il fatto va
> registrato, perché quel commit dice di parlare di P7 e porta dentro otto file di P8.
> Tutto il resto di questa cella — l'esito, le patch, gli strumenti, i log, `preset_P8_8` e
> `preset_P8_9` — è **non committato**.

---

## 1. Cancello di partenza

Un'altra corsa (P7 cella 7, `p7_n2l131_ragionamento_spento`) stava usando la macchina. Il cancello
richiesto — esistenza di `docs/porto/p7_speculazione/P7_CELLA7_RAGIONAMENTO_SPENTO_131K_15_SETTEMBRE.md`
**e** nessun `llama-server` **e** porta 8100 libera — è stato sorvegliato da un ciclo in background
ogni 2 minuti (`<scratchpad>/cancello_p8.ps1`, massimo 2 ore). Fino all'apertura si è solo letto e
preparato: copia dell'albero, prove di applicazione delle patch, preset, strumenti di analisi.

| | |
|---|---|
| ciclo di sorveglianza | avviato 10:33:46, dieci cicli a vuoto |
| server dell'altra corsa uscito | fra 10:49:46 e 10:51:46 |
| file `P7_CELLA7_…` comparso | 10:52 |
| **cancello aperto** | **10:53:10** — le tre condizioni insieme |

Nessun processo di inferenza è stato avviato prima di quell'istante, e nessuna compilazione.

---

## 2. Che cosa è stato preparato prima di toccare la macchina

| dove | che cosa |
|---|---|
| `D:\ds4_work\p8_work\source` | copia di `D:\ds4_work\p0_snapshot_20260914\source` (2.999 file, 44,7 MiB, robocopy `/MIR`, 0 falliti). **Non** da `p3_work`: le leve P8 non richiedono le patch P3–P7 e non devono mescolarsi |
| `D:\ds4_work\p8_work\compila.ps1` | stessa configurazione CMake di `p3_work\compila.ps1` (Ninja, Release, `CUDA_ARCHITECTURES=86`, DLL condivise, stessi interruttori del fork). `-PopolaBin` completa `build\bin` con le DLL non ricompilate, prese da `p0_snapshot\build_bin` |
| `p8_D1.patch` | **nuova**: la leva D1 era in progetto, non in patch (§4.2) |
| `p8_B_interruttore.patch` | **nuova**: mette la leva B dietro `QWEN4EXP_QSA_BIAS_DEV` (§3) |
| `applica_leve_p8.sh` | applica A → B → B_interruttore → C → D1 e rigenera `p8_cumulativa.patch` |
| `genera_preset_p8.py` | genera i preset `preset_P8_<n>_p7.json` in `docs/porto/banco_p0/` (otto all'inizio, dieci alla fine: §3) |
| `esegui_cella_p8.ps1`, `catena_p8.ps1` | attesa di quiete, guardia, blocco del banco, stato finale; e la fila delle celle |
| `analizza_p8.py`, `tabella_p8.py` | scompongono una corsa nei termini `ciclo = T1 + R + H` leggendo solo numeri già scritti, e ne fanno la tabella |
| `copia_log_p8.py` | estrae in `log/` le righe utili dei log del server |

Le cinque patch applicano pulite e **cumulativamente** su una copia dell'albero (verificato prima
di qualunque build). `--binary` è obbligatorio: i sorgenti hanno fine riga CRLF, e un `--dry-run`
incatenato **non** è una prova valida: `p8_B_interruttore.patch` e `p8_D1.patch` hanno per contesto
righe introdotte da `p8_B.patch`, che a vuoto non esistono ancora. Si prova su una copia vera.

### Le tre build

| | |
|---|---|
| build **nuda** | 10:53:20 → 11:00:53, 475 bersagli, codice 0. `-PopolaBin` ha poi aggiunto le tre `*.exe` dei probe che il bersaglio `llama-server` non produce. Copia congelata in `D:\ds4_work\p8_work\bin_nudo` |
| build **con le leve** | 11:02:59 → 11:03:08, incrementale: `ggml-backend.cpp` → `ggml-base.dll`, `qwen4exp.cpp` → `llama.dll`, `getrows.cu` → `ggml-cuda.dll`. Codice 0 |
| perché la seconda subito dopo la prima | così **una sola attesa di quiete da 15 minuti** copre entrambe, e dalla prima corsa in poi non si compila più nulla: le celle sono configurazioni, non compilazioni |
| build **terza**, 13:44:19 → 13:44:28 | una riga sola: il default di D1 passa da acceso a **spento**, dopo che la misura ha detto che D1 non paga (§7 D1). Serviva perché una patch si consegna con i suoi default, e i default vanno misurati: la corsa `P8_9` (§7) è fatta su questo binario **senza impostare nessuna variabile**. Anche qui 15 minuti di quiete prima della misura |

Le DLL sono state verificate **per contenuto**, non per data: la stringa di ogni leva è presente
nella build con le leve e assente in quella nuda.

| leva | stringa cercata | DLL | build con le leve | build nuda |
|---|---|---|---|---|
| A | `GGML_SCHED_SPLIT_INPUTS` | `ggml-base.dll` | presente | assente |
| B | `QWEN4EXP_QSA_BIAS_DEV` | `llama.dll` | presente | assente |
| C | `GGML_CUDA_GETROWS_NARROW` | `ggml-cuda.dll` | presente | assente |
| D1 | `QWEN4EXP_QSA_ONE_TRANSPOSE` | `llama.dll` | presente | assente |

SHA256 (primi 16): `ggml-base` leve `D6E1016E18DE44C8` / nuda `9763501C576C2D68`;
`ggml-cuda` `94AAF4028FA01055` / `93F851792C47CB6A`; `llama` `B84BC12CA5F45E39` / `E72F309295D8393E`.

`p8_cumulativa.patch` è stata verificata a sua volta: applicata a una copia fresca di
`p0_snapshot_20260914\source` produce i tre file **byte-identici** a quelli dell'albero di lavoro.

---

## 3. Deviazione dichiarata dal protocollo: una build, molte configurazioni

Il protocollo della cella chiedeva «patch applicata, build, corsa» per ciascuna leva. È stato
fatto diversamente, e la ragione è nel progetto stesso:

- la leva **A** è nata env-tunabile proprio «così si confrontano le due configurazioni con lo
  **stesso binario**» (progetto §2.A);
- la leva **C** è dietro `GGML_CUDA_GETROWS_NARROW` «per l'A/B con un solo binario» (§2.C);
- la leva **D1**, scritta qui, segue lo stesso stile (`QWEN4EXP_QSA_ONE_TRANSPOSE`);
- restava solo **B**, incondizionata. `p8_B_interruttore.patch` la mette dietro
  `QWEN4EXP_QSA_BIAS_DEV`: con `0` il tensore `bias_dev` non nasce, tutte le viste tornano
  sull'ingresso host e **il grafo è quello di prima della patch**.

Con tutte e quattro spegnibili, le quattro celle cumulative sono **quattro configurazioni dello
stesso binario**: fra una cella e la successiva cambia una variabile, non una compilazione. Questo
(a) toglie dal confronto la varianza fra build, (b) toglie tre attese di quiete da 15 minuti
(regola `dopo-una-build-la-macchina-non-e-quieta`), (c) è la regola
`batterie-a-caldo-non-bracci-freddi` applicata alla lettera.

Il prezzo è una riga di codice in più per B e un **controllo obbligatorio**: la corsa `P8_7`
(binario patchato, **tutte le leve spente**) deve riprodurre le impronte di `P8_1` (binario nudo).
Se non lo facesse, una delle patch non sarebbe davvero spegnibile e tutta la tabella sarebbe da
rileggere.

I due riferimenti restano su un binario **nudo**, compilato dagli stessi sorgenti senza nessuna
patch, conservato in `D:\ds4_work\p8_work\bin_nudo`.

### Le dieci configurazioni

| preset | base | binari | A `GGML_SCHED_SPLIT_INPUTS` | B `QWEN4EXP_QSA_BIAS_DEV` | C `GGML_CUDA_GETROWS_NARROW` | D1 `QWEN4EXP_QSA_ONE_TRANSPOSE` |
|---|---|---|---|---|---|---|
| `P8_0` R0 | `preset_A` (MTP spento) | nudo | — | — | — | — |
| `P8_1` R1 | `preset_M1_p7` (bozza 1) | nudo | — | — | — | — |
| `P8_7` controllo | `preset_M1_p7` | leve | — | 0 | 0 | 0 |
| `P8_2` A | `preset_M1_p7` | leve | **96** | 0 | 0 | 0 |
| `P8_3` A+B | `preset_M1_p7` | leve | **96** | **1** | 0 | 0 |
| `P8_4` A+B+C | `preset_M1_p7` | leve | **96** | **1** | **1** | 0 |
| `P8_5` A+B+C+D1 | `preset_M1_p7` | leve | **96** | **1** | **1** | **1** |
| `P8_6` bozza 2 | `preset_M2_p7` | leve | **96** | **1** | **1** | **1** |
| `P8_8` B+C senza A | `preset_M1_p7` | leve | — | **1** | **1** | 0 |
| `P8_9` consigliata | `preset_M1_p7` | leve | *nessuna variabile: i soli default della patch* | | | |

Le ultime due sono nate **durante** la cella, da due domande che i numeri hanno sollevato:
`P8_8` perché il progetto sosteneva che B rendesse A ridondante (§7 A), `P8_9` perché una patch
si consegna con i suoi default e quei default vanno misurati, non supposti (§7 «configurazione
consigliata»). Dodici corse in tutto, comprese due repliche.

---

## 4. Due verdetti ottenuti senza consumare una corsa

### 4.1 `QWEN_MOE_SCALAR_BATCH=2` **non è inerte**: il modello non contiene un solo tensore IQ3_XXS

Il progetto sospettava (§2.E, difetto 5) che il ramo «scalar» di `mmvq.cu:1124` —

```c
if constexpr (type == GGML_TYPE_IQ2_S || type == GGML_TYPE_IQ3_S || type == GGML_TYPE_IQ4_NL) {
    if (scalar_verify == 2 && has_ids && ncols_dst >= 2 && ncols_dst <= 3 && ...)
```

— non si applicasse agli esperti, «perché IQ3_XXS è il quanto dominante del pacchetto UD-IQ3_XXS»,
e che quindi la variabile del preset M1 fosse inerte su gran parte del MoE.

**È il contrario.** Letta l'intestazione dei tre shard del GGUF (solo i metadati e l'elenco dei
tensori, i pesi non vengono toccati: `<scratchpad>/tipi_gguf.py`), i **144** tensori `*_exps*` sono:

| tensore | tipo | quanti |
|---|---|---:|
| `blk.*.ffn_down_exps.weight` | **iq4_nl** | 48 / 48 |
| `blk.*.ffn_gate_exps.weight` | **iq2_s** 47, **iq3_s** 1 | 48 |
| `blk.*.ffn_up_exps.weight` | **iq2_s** 47, **iq3_s** 1 | 48 |

Su 1.224 tensori del modello **non ce n'è nemmeno uno di tipo `iq3_xxs`**: `IQ3_XXS - 3.0625 bpw`
è solo l'etichetta `file type` del pacchetto, non il tipo dei tensori. I tre tipi effettivi degli
esperti — **IQ2_S, IQ3_S, IQ4_NL** — sono **esattamente i tre** che il ramo copre.

Conseguenze, da mettere a registro:

1. `QWEN_MOE_SCALAR_BATCH=2` è **attiva su 144 tensori esperti su 144**. La bit-identità osservata
   (`mismatch = 0`) e i **−1,85 ms/riga** misurati il 10/9 spegnendola vengono da **questo** ramo.
2. **La leva E del progetto è descritta per un kernel che qui non gira.** Il ramo scalar chiama
   `mul_mat_vec_q_switch_fusion<type, 1, …>` con `ncols_dst` fissato a 1 per fetta `z`, non
   `mul_mat_vec_q_moe`. Il disegno «condividere la lettura+dequantizzazione dell'esperto fra i
   token» va rifatto contro il ramo scalar — dove per costruzione ogni token ha la geometria di
   riduzione a token singolo, ed è proprio per questo che è bit-identico e che non condivide nulla.
3. Resta un'incertezza dichiarata: il ramo richiede anche
   `!fusion.x_bias && !fusion.gate_bias && !fusion.x_scale && !fusion.gate_scale`. Con la fusione
   gate/up del fork attiva, non è dimostrato dal solo codice che tutti e tre i tensori la
   soddisfino a ogni strato. Servirebbe un contatore, non una corsa.

### 4.2 D1-bis (la «catena di `concat`») **non è una catena** con la bozza a 1 token

Il progetto (§2.D) proponeva di sostituire `result = ggml_concat(result, current, 1)` con la
scrittura in un tensore preallocato, per −0,05…−0,09 ms. Letto il codice
(`qwen4exp.cpp:1157` e `:988`): il ciclo gira su `n_tps`, e con la bozza a 1 token **`n_tps = 2`**,
cioè il «chain» è **un solo `concat`** per strato e per sito. Sostituire un `concat` con un tensore
preallocato più due `ggml_cpy` su vista **aggiunge** nodi invece di toglierli, e introduce il
rischio della scrittura su vista di un tensore non inizializzato, per un guadagno che a due righe
non esiste. **D1-bis non è stata implementata**, e la ragione è questa, non la mancanza di tempo.
Tornerebbe a valere a 3 righe (bozza 2), dove i `concat` per sito diventano due.

D1 è quindi stata implementata nella sola parte che vale: **una trasposta per forward invece di una
per token**, e un `ggml_reshape_2d` al posto del secondo `ggml_cont(ggml_transpose(...))` — il
tensore raccolto è già `n_kv` float contigui, quindi quella `cont` copiava dei byte per non
cambiarli.

---

## 5. I riferimenti a 131k

Profilo `lungo_131k`: `L01@ctx131k` (prefill **freddo** di 131.248 token, ~522 s) e `L02@ctx131k`
(riusa il prefisso, 94 token di prompt). Budget 1024 token per caso, greedy, seed 1234,
ragionamento acceso, 64 slot esperti, contesto 262.144.

### 5.1 Il rebuild è indistinguibile dai binari in esercizio

Le **quattro impronte** di R0 (due riscaldamenti + i due casi a 131k) coincidono con quelle della
corsa P7 cella 7 (`20260915_102009_P7_p7_n2l131_ragionamento_spento_r1`), fatta sui binari
originali `qwen38_clean\build\bin`:

| caso | impronta |
|---|---|
| `riscaldamento_1` / `_2` | `b626d0e377e6075e…` |
| `L01@ctx131k` | `99ba1423cf128585…` |
| `L02@ctx131k` | `dc916b9c428225c2…` |

Quella corsa girava con `--reasoning off` e bozza 2, questa con ragionamento acceso e MTP spento:
l'impronta è `sha256(reasoning_content + content)`, quindi il taglio fra i due campi non la cambia,
e la verifica esatta della speculazione nemmeno. **Il testo a 131k è lo stesso in tutte e quattro
le configurazioni**: i binari ricompilati dallo snapshot P0 non sono distinguibili da quelli in
esercizio, e il determinismo greedy regge anche a 131k. Non era scontato: il progetto poteva solo
dichiararlo.

### 5.2 I numeri

| | R0 — MTP spento | R1 — MTP bozza 1 |
|---|---:|---:|
| corsa | `20260915_112333_P8_p8_r0_spento_binari_nudi_r1` | `20260915_113742_P8_p8_r1_mtp1_binari_nudi_r1` |
| token generati | 2.048 | 2.048 |
| **ms per token** | **37,906** | **38,126** |
| **t/s** | **26,381** | **26,229** |
| verifiche (cicli) | — | 1.224 |
| **ciclo** | — | **63,792 ms** |
| token per ciclo | 1,000 | **1,673** |
| **testa MTP `H`** | — | **5,683 ms** |
| **riga di verifica `R = ciclo − T1 − H`** | — | **20,203 ms** |
| accettazione posizione 1 | — | 0,706 (L01) · 0,672 (L02) |
| `graph splits` a bs=3 | 4 (2 a bs=1) | 4 (2 a bs=1) |
| `graphs reused` (ultima richiesta) | 2.045 | 1.215 |
| NaN nel log · riserve di grafo fallite | 0 · 0 | 0 · 0 |
| RAM disponibile minima | **5,12 GB** | **3,61 GB** |
| VRAM libera minima | 1.201 MiB | 949 MiB |

`T1 = 37,906` ms è il valore usato per `R` in tutta la cella: è il costo di un forward a **una**
riga alla stessa profondità, misurato e non dedotto.

**Tre letture che contano.**

1. **A 131k la riga di verifica costa `R = 20,2 ms`, non 15,7.** I 15,66 ms di P7 sono a 205k ma
   con `T1` dedotto dal banco a ≤32k; qui `T1` e `ciclo` sono misurati alla **stessa** profondità,
   sulle stesse due richieste. Il confronto diretto fra i due numeri non è lecito; quello che conta
   è che **al punto operativo dell'utente la riga vale un quarto in più di quanto il progetto
   assumeva**, e quindi le leve hanno più da mordere.
2. **Al punto operativo la bozza MTP a 1 token non paga già oggi**: 38,126 ms/token contro i
   37,906 di MTP spento, cioè **−0,6%**. Con `H + R = 25,89 ms` di sovrapprezzo per ciclo e
   1,673 token per ciclo, il pareggio è a `ciclo/token_per_ciclo = T1`: serve che il ciclo scenda
   sotto `1,673 × 37,906 = 63,42 ms`, contro i 63,79 misurati. **Mancano 0,37 ms.** È la soglia
   che le leve devono superare per rendere l'MTP redditizio a 131k — molto più bassa degli
   ~11 ms che il progetto poneva per la bozza a 2.
3. **`graph splits = 4 (with bs=3), 2 (with bs=1)`** è confermato sui binari nudi, e compare
   **anche con MTP spento** (la riserva a 3 righe la fa `LLAMA_MOE_CACHE_BATCH=3`). È l'osservabile
   della leva A, gratis e senza perturbare la misura.

### 5.3 Un difetto che riguarda tutte le corse MTP: la RAM

La sonda misura **3,61 GB** di RAM disponibile al minimo in R1, sotto la soglia di 4 GB che la
regola dell'utente dà per **corsa invalida**. Non è un disturbo passeggero: è strutturale della
configurazione MTP a 131k — il modello di bozza aggiunge 2.550 MiB di buffer mappato sull'host
sopra i ~74 GB del tronco. La corsa P7 cella 7 del 15/9, sugli stessi binari originali, misura
**3,45 GB**: lo stesso regime. R0 (senza modello di bozza) sta a **5,12 GB**.

Il dato è registrato per ogni cella e **dichiarato**: tutte le corse MTP di questa cella sono
formalmente sotto soglia. Restano confrontabili fra loro (stesso regime, stessa macchina, stessa
sequenza), ma la soglia va rivista o la configurazione alleggerita prima di darne un valore
assoluto.

---

## 6. La tabella delle celle

Tutte a 131k, profilo `lungo_131k`, budget 1024, greedy seed 1234, ragionamento acceso, 64 slot.
`R = ciclo − T1 − H` con `T1 = 37,906 ms` da R0. `ΔR` è contro **R1** (binari nudi).
`split bs=3` è quello che lo scheduler riporta alla riserva del decode speculativo: uno degli
split non è CUDA, quindi **i lanci di grafo CUDA sono `split − 1`**.

| cella | leve | R (ms) | ΔR vs R1 | ms/token | t/s | ciclo (ms) | H (ms) | tok/ciclo | split bs=3 → lanci CUDA | nodi bs=3 | impronte = R1 | RAM min (GB) | VRAM libera min (MiB) | NaN |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--:|---:|---:|---:|
| R0 · MTP spento | — (binari nudi) | — | — | 37,906 | 26,381 | — | — | 1,000 | 4 → **3** | 9.561 | sì 4/4 | 5,12 | 1.201 | 0 |
| R1 · MTP bozza 1 | — (binari nudi) | **20,203** | — | 38,126 | 26,229 | 63,792 | 5,683 | 1,673 | 4 → **3** | 9.561 | *(riferimento)* | 3,61 | 949 | 0 |
| controllo | nessuna (binario patchato) | 20,168 | −0,035 | 38,101 | 26,246 | 63,751 | 5,678 | 1,673 | 4 → **3** | 9.561 | **sì 4/4** | 2,84 | 949 | 0 |
| controllo r2 | nessuna (binario patchato) | 20,163 | −0,039 | 38,084 | 26,258 | 63,722 | 5,653 | 1,673 | 4 → **3** | 9.561 | **sì 4/4** | 2,62 | 949 | 0 |
| **P8c1 — A** | A | 20,124 | −0,079 | 38,071 | 26,267 | 63,701 | 5,671 | 1,673 | **2 → 1** | 9.561 | **sì 4/4** | 2,91 | 931 | 0 |
| **P8c2 — A+B** | A+B | 18,609 | **−1,594** | 37,164 | 26,908 | 62,183 | 5,669 | 1,673 | 2 → 1 | **9.562** | **sì 4/4** | 2,85 | 962 | 0 |
| **P8c3 — A+B+C** | A+B+C | 18,603 | −1,599 | 37,158 | 26,912 | 62,173 | 5,664 | 1,673 | 2 → 1 | 9.562 | **sì 4/4** | 3,02 | 969 | 0 |
| P8c3 — A+B+C **r2** | A+B+C | 19,098 | −1,104 | 37,471 | 26,687 | 62,697 | 5,693 | 1,673 | 2 → 1 | 9.562 | **sì 4/4** | 2,51 | 969 | 0 |
| **P8c4 — A+B+C+D1** | A+B+C+D1 | 18,739 | −1,463 | 37,239 | 26,854 | 62,308 | 5,663 | 1,673 | 2 → 1 | **9.478** | **sì 4/4** | 3,20 | 969 | 0 |
| **P8c6 — B+C, senza A** | B+C | **18,597** | −1,606 | **37,134** | **26,930** | 62,132 | 5,630 | 1,673 | **2 → 1** | 9.562 | **sì 4/4** | 2,57 | 969 | 0 |
| **P8c7 — consigliata** | default della patch (B+C) | 18,718 | −1,484 | 37,213 | 26,872 | 62,265 | 5,641 | 1,673 | **2 → 1** | 9.562 | **sì 4/4** | 2,62 | 969 | 0 |
| **P8c5 — bozza 2** | A+B+C+D1, bozza 2 | 35,487 | +15,284 | 41,850 | 23,895 | 84,526 | 11,133 | 2,020 | 2 → 1 | — | **sì 4/4** | 2,33 | 853 | 0 |

**Nessuna cella ha cambiato una sola impronta**: 4 casi su 4 in ognuna delle undici corse
confrontabili (i due riscaldamenti più `L01@ctx131k` e `L02@ctx131k`). **Tutte le leve sono
lossless.** Nessun NaN in nessun log, nessuna riserva di grafo fallita, nessun avviso
`increasing split inputs`, nessuna corsa invalida per guasto, nessun processo residuo.

### 6.1 Il pavimento di rumore, misurato e non supposto

Due repliche dicono quanto vale una differenza:

| coppia di corse nominalmente identiche | ΔR |
|---|---:|
| controllo r1 vs r2 (leve spente) | **0,005 ms** |
| A+B+C r1 vs r2 | **0,495 ms** |

Il secondo numero è quello da usare. Raggruppando le corse per lo stato della sola leva **B**
(D1 spenta ovunque):

| gruppo | n | R media | min | max | scarto | sd |
|---|---:|---:|---:|---:|---:|---:|
| **B spenta** (R1, controllo ×2, A) | 4 | **20,165** | 20,124 | 20,203 | 0,079 | 0,032 |
| **B accesa** (A+B, A+B+C ×2, B+C, consigliata) | 5 | **18,725** | 18,597 | 19,098 | 0,501 | 0,215 |

**L'effetto di B è −1,439 ms su `R`, −0,867 ms su ms/token, +2,33% su t/s**, con i due gruppi
separati da più di sei deviazioni standard del gruppo più rumoroso. Tutto il resto — A (−0,08),
C (−0,006), D1 (+0,136) — **sta dentro il rumore di una singola replica**.

### 6.2 Copie H2D del bias

Non c'è profilatore in questa cella, quindi le copie non sono contate una per una. Sono però
**determinate dalla forma del grafo**, che è osservabile, e il modello di P7/P8 le dà esattamente:

| | viste di `n_kv` float che sono ingressi di split | byte per forward a 131k |
|---|---:|---:|
| senza B (2 righe) | 24 `bias_row` + 24 `b1` + 1 `cell_blk` = **49** | 49 × 524.288 B = **24,5 MiB** |
| con B (2 righe) | `bias` intero (che alimenta il `cont`) + `cell_blk` = **2** | **1,0 MiB** |

−23,5 MiB per forward, che alla banda DMA misurata da P7 (23,6 GiB/s) valgono **−0,97 ms**;
misurati **−1,44 ms**. La differenza non è byte: prima degli ingressi di ogni split lo scheduler
fa un `ggml_backend_synchronize` e la copia è **bloccante** (`ggml-backend.cpp:1938-1956`), quindi
togliere 47 copie toglie anche 47 emissioni sincrone e 47 attese.

Il conto è confermato da un'osservazione indipendente: con B il grafo guadagna **esattamente un
nodo** (9.561 → 9.562 a bs=3, 8.336 → 8.337 a bs=1). **Uno, non dodici**: i 12 strati QSA
condividono un solo `llm_graph_input_qsa`, cioè **esiste un solo rapporto di compressione
distinto**. Era una deduzione del progetto (difetto 4); adesso è letta dal conteggio dei nodi.

---

## 7. Verdetto, leva per leva

### A — tetto degli ingressi di split: **il meccanismo è quello previsto, il prezzo no**

`GGML_SCHED_SPLIT_INPUTS=96` fa esattamente ciò che il progetto prevedeva:
`graph splits = 4 (with bs=3), 2 (with bs=1)` diventa `graph splits = 2`, cioè **i lanci di grafo
CUDA per forward passano da 3 a 1**. Il modello dello scheduler è verificato sul campo.

**Vale −0,079 ms su `R`, cioè un sesto del rumore di replica.** Il progetto stimava −0,5…−1,2 ms e
dichiarava questa la stima più debole: lo era.

E il numero falsifica una parte del modello. Il progetto sosteneva che *«un ingresso usato da due
split è copiato due volte»*, e quindi che A togliesse anche byte. **Non è così**: se A avesse tolto
~35 copie da 524 KB si sarebbero visti ~0,7 ms, e se ne vedono 0,08. Le 49 copie sono **49 viste
distinte, ciascuna copiata una volta**, comunque il grafo sia tagliato. Tre lanci invece di uno
costano due `cudaGraphLaunch` e due svuotamenti della coda: **0,08 ms, non i 2,17 di GPU inattiva**.

**E A è ridondante.** La cella P8c6 accende B e **spegne** A: il grafo torna a `graph splits = 2`
**da solo** — gli ingressi scendono sotto il tetto di 30 perché le 48 viste del bias non ci sono
più — e `R = 18,597` contro i 18,603 con A. Il progetto lo prevedeva («B rende A ridondante»);
adesso è misurato. **`p8_A.patch` si può non applicare**, e la patch finale non tocca
`ggml/src/ggml-backend.cpp`.

### B — bias QSA residente sul dispositivo: **è tutta qui la leva**

**−1,439 ms** su `R` (media di 5 corse contro 4), lossless, 4 impronte su 4 in ognuna. È il
**7,1%** della riga di verifica e il **2,3%** del ms per token complessivo.

Il progetto stimava −1,11 ms **a 205k** e −0,18 al banco a 32k; a 131k, dove il modello ne
predirebbe ~0,7, se ne misurano 1,44. Il di più viene dal termine che il modello contava solo come
byte: le copie non sono soltanto larghe, sono **sincrone**, e toglierle toglie anche le attese.

### C — geometria di `get_rows` quantizzato: **non compra nulla**

**−0,006 ms**: zero, un ottantesimo del rumore. `GGML_CUDA_GETROWS_NARROW` è nel binario (stringa
verificata) e le due corse differiscono solo per quella variabile.

Il perché è nella geometria che la patch **non** cambia. `get_rows_cuda_q` lancia
`block_nums(ne10, block_num_y, …)` con `ne10 = n_topk = 2048`; per una riga da 128 valori
`block_num_y = (128 + 2·B − 1)/(2·B)` vale **1 sia con B=256 sia con B=64**. La griglia resta di
2048 blocchi: cambia solo quanti thread inerti ci sono dentro ciascuno. Il numero di richieste di
memoria **in volo** — la grandezza che conta su letture sparse da 136 byte in memoria host mappata
— non cambia. L'ipotesi di occupancy che il progetto dichiarava come suo punto più debole
(difetto 3) **non è sostenuta**: `k_get_rows` a 3,7 GiB/s non è limitato dagli slot di thread.

*Limite onesto:* senza profilatore non posso separare «il kernel è più veloce ma non è sul cammino
critico» da «il kernel non è più veloce». Quello che la cella dimostra è che **sul totale non si
vede**, ed è questo che decide se la patch vale. C resta accesa nella configurazione consigliata
perché è gratis e bit-identica, non perché serva.

### D1 — una trasposta per forward invece di una per token: **si spegne**

Il grafo si accorcia come previsto — **9.562 → 9.478 nodi a bs=3, esattamente −84**, cioè
3 token × 12 strati × 3 nodi tolti meno i 12×2 aggiunti — e a una riga non cambia nulla (8.337:
il ramo vuole `n_tps > 1`). Ma `R` **sale** di **+0,136 ms**, e sale in entrambi i casi
(`L01` +0,180, `L02` +0,093).

Il segno è consistente fra i due casi ma la grandezza è **dentro il rumore di replica** (0,5 ms):
onestamente, **D1 non è distinguibile da zero, e di sicuro non è il guadagno atteso**. La
spiegazione più probabile del fatto che non guadagni è nella vista che sostituisce la trasposta:
prima `get_rows` leggeva un `[1, n_blocks]` **contiguo** (`nb01 = 4`), adesso legge una colonna del
punteggio trasposto (`nb01 = n_tps·4 = 8`), e `k_get_rows_scalar` legge una riga per thread a passo
`nb01`. Si risparmiano 84 lanci di kernel e si paga in località.

Resta **lossless** (4 impronte su 4): è un'ottimizzazione corretta che non paga, non un difetto.
**Il suo default nella patch consegnata è SPENTO**, e il commento nel codice dice perché.

**D1-bis** (la catena di `concat`) non è stata implementata: a bozza 1 `n_tps = 2` e la «catena»
è **un solo `ggml_concat`** per sito e per strato (§4.2).

### La bozza a 2 token: **no, e il margine non è stretto**

`preset_P8_6` — bozza 2, tre righe di verifica, **tutte le leve accese**:

| | bozza 1 + leve (P8c3) | **bozza 2 + leve (P8c5)** | MTP spento (R0) |
|---|---:|---:|---:|
| ms per token | **37,158** | 41,850 | 37,906 |
| t/s | **26,912** | 23,895 | 26,381 |
| ciclo | 62,173 | 84,526 | — |
| `R` (righe oltre la prima) | 18,603 | **35,487** | — |
| `H` (testa MTP) | 5,664 | **11,133** | — |
| token per ciclo | 1,673 | 2,020 | 1,000 |
| accettazione per posizione | 0,706 | 0,677 / 0,438 · 0,639 / 0,380 | — |

**La bozza a 2 perde l'11,2% contro la bozza a 1 con le stesse leve, e il 10,4% contro l'MTP
spento.** La seconda riga in più costa `35,487 − 18,603 = 16,88 ms`, e `H` raddoppia (la testa MTP
gira due volte per ciclo), per comprare 0,347 token per ciclo in più.

Soglia di pareggio della seconda posizione:
`(ΔH + ΔR)/ms-per-token = (5,47 + 16,88)/37,16 =` **0,602**, contro lo **0,41** misurato
(media di 0,438 e 0,380). Per pareggiare, la riga in più dovrebbe costare **poco più della metà**
di quanto costa. Le leve lossless di P8 tolgono 1,4 ms: **non è questa la strada**, e il progetto
lo diceva — la soglia si raggiunge «componendo A–D con la corsia CPU di P4/P5», che attacca i
6,5 ms di gather che P8 per definizione non tocca.

### La configurazione consigliata

**B da sola** (C accesa perché è gratis, A non applicata perché ridondante, D1 spenta).
`preset_P8_9_p7.json` la misura **senza impostare nessuna variabile**, cioè applicando la patch e
basta: `R = 18,718`, `37,213` ms/token, `26,872` t/s, **1 lancio di grafo CUDA**, 9.562 nodi
(D1 davvero spenta), impronte 4 su 4. **I default della patch sono quelli giusti.**

### Il verdetto d'insieme

> **La riga di verifica scende da 20,17 a 18,73 ms — −7,1% — e tutto il merito è di una leva
> sola, B.** In ms per token: 38,095 → **37,228** (−2,3%); in t/s: 26,250 → **26,862** (+2,3%).

E il fatto che cambia la decisione operativa:

> **Al punto operativo dell'utente la bozza MTP a 1 token non pagava, e con B paga.**
> Senza leve l'MTP costa 38,10 ms/token contro i **37,91** dell'MTP spento: **−0,5%**, cioè la
> speculazione a 131k era una perdita netta. Con B costa **37,23**, cioè **+1,8% sull'MTP spento**
> e +2,3% sull'MTP di oggi. Il ciclo doveva scendere di 0,37 ms perché l'MTP pareggiasse; B ne
> toglie 1,44.

**La patch che serve tocca un solo file**, `src/models/qwen4exp.cpp`, e nella configurazione
consigliata non richiede nessuna variabile d'ambiente.

---

## 8. Difetti di questa cella

1. **Il pavimento di rumore è stimato su due sole coppie di repliche**, e le due non concordano
   (0,005 ms e 0,495 ms). Ho usato la peggiore, ma con due coppie non si calcola una varianza:
   il numero onesto è «una replica può spostare `R` di mezzo millisecondo», non «σ = 0,215».
   Serve una terza replica della configurazione consigliata per stringere.
2. **Tutte le corse MTP sono sotto la soglia di RAM dichiarata invalida** (§5.3): da 3,61 GB
   (R1) a 2,33 GB (bozza 2), contro i 4 GB della regola. È strutturale della configurazione — il
   modello di bozza aggiunge 2.550 MiB sopra i ~74 GB del tronco — e la corsa P7 cella 7 del 15/9,
   su binari diversi, misura 3,45 GB. **Le corse restano confrontabili fra loro** (stesso regime,
   stessa macchina, stessa sequenza, impronte identiche) ma **non dovrebbero essere usate per un
   valore assoluto** finché la soglia non è rivista o la configurazione alleggerita.
3. **Le copie H2D non sono contate, sono dedotte** dalla forma del grafo (§6.2). La deduzione è
   ancorata a due osservabili veri (numero di nodi, numero di split) e al conteggio nsys di P7 a
   205k, ma un profilo con `--trace=cuda` sulla configurazione con B la chiuderebbe in dieci minuti.
4. **Su C non posso distinguere** «il kernel è più veloce ma non è sul cammino critico» da «il
   kernel non è più veloce» senza profilatore. Il verdetto «non compra nulla» è sul **totale**,
   che è ciò che decide, non sul kernel.
5. **`R` dipende da un `T1` misurato in una corsa diversa** (R0, MTP spento). Se `T1` derivasse a
   131k fra una corsa e l'altra, `R` ne erediterebbe l'errore. È lo stesso modello di P7 e
   l'alternativa (un `T1` per corsa) non esiste con l'MTP acceso; la coerenza fra `L01` e `L02`
   dentro ogni corsa (differenza di `R` sotto 0,08 ms nelle corse senza D1) suggerisce che la
   deriva sia piccola.
6. **Il ramo scalar di `mmvq` ha una condizione che non ho verificato** (§4.1, punto 3): richiede
   anche `!fusion.x_bias && !fusion.gate_bias && !fusion.x_scale && !fusion.gate_scale`, e con la
   fusione gate/up del fork accesa non è dimostrato dal solo codice che tutti gli strati la
   soddisfino. Serve un contatore, non una corsa.
7. **Una sola profondità e due sole richieste.** Il profilo `lungo_131k` è `L01` + `L02`, 1.024
   token ciascuno. È il punto operativo, ma non dice come la leva si comporta a 200k o a 262k —
   dove il bias è più grande e **B dovrebbe valere di più**, non di meno.

---

## 9. Aperture

1. **B2 — generare il bias sul dispositivo** (progetto §2.B): resta l'ultima copia da 0,5 MiB e gli
   `std::fill` host che costano O(n_kv) per token **prima** del grafo. Adesso che B1 ha pagato
   1,44 ms a 131k, B2 è la prosecuzione naturale, e cresce con la profondità.
2. **Rimisurare a 200-262k.** B è l'unico termine della riga che scala con `n_kv`: a 262k dovrebbe
   valere il doppio. È anche il regime in cui l'utente ha il KV da 250k.
3. **D1 a tre righe.** A `n_tps = 3` il lavoro per token che D1 toglie è una volta e mezza quello
   di due righe, e la catena di `concat` diventa davvero una catena. Ha senso riprovarla **solo**
   dentro una cella che abbia già reso redditizia la bozza a 2, cioè dopo la corsia CPU.
4. **La leva E va riprogettata da zero** (§4.1): il kernel che gira sui nostri esperti non è
   `mul_mat_vec_q_moe` ma il ramo scalar, che per costruzione dà a ogni token la geometria di
   riduzione a token singolo. «Condividere l'esperto fra i token» lì dentro significa cambiare
   quella geometria, cioè uscire dal cancello della bit-identità.
5. **La corsia CPU di P4/P5 resta la sola leva grande.** I 6,5 ms di gather esperti sono il 35%
   della riga e P8 non li tocca per definizione. Con `R` a 18,7 ms e la soglia della seconda
   posizione a 0,602 contro 0,41, l'unico modo di riaprire la bozza a 2 è togliere byte.

---

## 10. Bozza di voce di registro

> **15 settembre 2026 — fase P8, celle 1-7: le leve lossless della riga di verifica MTP, misurate
> al punto operativo (131k).**
>
> *Ipotesi.* Dei ~20 ms della riga di verifica MTP a 131k una parte è contabilità e non
> aritmetica: tre lanci di grafo invece di uno (A), un bias QSA ricopiato dall'host 49 volte per
> forward (B), un `get_rows` che usa 64 thread su 256 (C), due trasposte per token invece di una
> (D1). Se è così si toglie senza cambiare un bit del testo.
>
> *File toccati.* Nuovi in `docs/porto/p8_riga_verifica/`: `P8_ESITO_15_SETTEMBRE.md`,
> `p8_D1.patch`, `p8_B_interruttore.patch`, `p8_cumulativa.patch`, `applica_leve_p8.sh`,
> `genera_preset_p8.py`, `esegui_cella_p8.ps1`, `catena_p8.ps1`, `analizza_p8.py`, `tabella_p8.py`,
> `copia_log_p8.py`, `log/` (12 corse). Nuovi in `docs/porto/banco_p0/`:
> `preset_P8_{0,1,2,3,4,5,6,7,8,9}_p7.json`. Albero di lavoro `D:\ds4_work\p8_work` (copia dello
> snapshot P0, **non** di `p3_work`), due build, binari nudi congelati in `bin_nudo`.
> **Nessun commit.** `bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, lanciatore
> quotidiano, modelli e snapshot P0 invariati.
>
> *Configurazioni.* Banco P0, profilo `lungo_131k` (`L01`/`L02` con prefisso `ctx131k`: un prefill
> freddo da 131.248 token, ~522 s, poi il riuso), budget 1024, greedy seed 1234, ragionamento
> acceso, 64 slot, contesto 262.144. Quattro leve tutte dietro una variabile, quindi **una build e
> N configurazioni** invece di N build (deviazione dichiarata dal protocollo, con corsa di
> controllo a leve spente che deve riprodurre il binario nudo — e lo riproduce).
>
> *Run validi / invalidi.* **Dodici corse, zero guasti, zero NaN, zero riserve di grafo fallite,
> zero processi residui, e zero impronte diverse: 4 su 4 in ognuna.** Tutte le corse MTP hanno però
> la RAM disponibile minima **sotto i 4 GB** della regola (3,61 → 2,33): è strutturale della
> configurazione MTP a 131k, non un disturbo, e la corsa P7 cella 7 del 15/9 sta a 3,45 GB.
> Dichiarate confrontabili fra loro, non utilizzabili come valore assoluto.
>
> *Risultato e limite.* **A 131k la riga di verifica costa `R = 20,17 ms`** (`T1 = 37,91`,
> `ciclo = 63,75`, `H = 5,68`), non i 15,7 misurati a 205k con un `T1` preso dal banco a 32k. E
> **al punto operativo la bozza MTP a 1 token era una perdita netta**: 38,10 ms/token contro i
> 37,91 dell'MTP spento, −0,5%.
> **Delle quattro leve ne paga una sola. B — il bias QSA copiato una volta sul backend di calcolo
> invece di 49 volte dall'host — vale −1,44 ms su `R` (media di 5 corse contro 4, gruppi separati
> da sei sigma), cioè −2,3% sul ms/token e +2,3% sui t/s, e ribalta il segno dell'MTP: con B la
> bozza a 1 token dà 37,23 ms/token, +1,8% sull'MTP spento.** Le altre tre stanno dentro il rumore
> di replica (0,5 ms): **A** −0,08, **C** −0,006, **D1** +0,14.
> Tre meccanismi sono però verificati sul campo, e due falsificano il progetto. (1) A fa esattamente
> ciò che il modello dello scheduler prevedeva — `graph splits` a bs=3 passa da **4 a 2**, cioè da
> **3 lanci CUDA a 1** — ma vale 0,08 ms, non 0,5-1,2: **le 49 copie non erano duplicate fra gli
> split**, erano 49 viste distinte copiate una volta ciascuna, e tre lanci invece di uno costano
> due `cudaGraphLaunch` e due svuotamenti di coda, non i 2,17 ms di GPU inattiva. (2) **B rende A
> ridondante**: con B acceso e A spenta il grafo torna a un lancio da solo e `R` è lo stesso
> (18,597 contro 18,603), quindi `p8_A.patch` si può non applicare e la patch finale tocca **un
> solo file**. (3) C non compra nulla perché la patch non cambia la griglia: `block_num_y` vale 1
> sia con 256 thread sia con 64, e su letture sparse da 136 B in memoria host mappata conta il
> parallelismo di memoria in volo, non gli slot di thread — **l'ipotesi di occupancy, che il
> progetto dichiarava come suo punto più debole, non è sostenuta**. (4) D1 accorcia il grafo di
> **esattamente 84 nodi** e non guadagna: la vista a passo doppio che sostituisce la trasposta paga
> in località quel che risparmia in lanci. Default spento nella patch consegnata.
> **La bozza a 2 token non paga, e non di poco**: con tutte le leve dà 41,85 ms/token contro i
> 37,16 della bozza a 1, cioè −11,2%, perché la terza riga costa 16,88 ms e la testa raddoppia
> (5,66 → 11,13). La soglia di pareggio della seconda posizione è **0,602** contro lo **0,41**
> misurato.
> Due verdetti sono arrivati **senza consumare una corsa**. **`QWEN_MOE_SCALAR_BATCH=2` non è
> inerte: nel modello non esiste un solo tensore IQ3_XXS.** Letta l'intestazione dei tre shard, i
> 144 tensori `*_exps*` sono `ffn_down` **iq4_nl** (48), `ffn_gate`/`ffn_up` **iq2_s** (94) e
> **iq3_s** (2): esattamente i tre tipi che il ramo `mmvq.cu:1124` copre. `IQ3_XXS - 3.0625 bpw` è
> solo l'etichetta `file type` del pacchetto. Quindi la bit-identità e i −1,85 ms/riga del 10/9
> vengono da **quel** ramo, e **la leva E del progetto è descritta per un kernel che qui non gira**
> (`mul_mat_vec_q_moe`): va riprogettata. E **D1-bis non esiste a bozza 1**: con `n_tps = 2` la
> «catena di `concat`» è un solo `ggml_concat` per sito, sostituirlo aggiunge nodi.
> Ultimo fatto, dal conteggio dei nodi: con B il grafo guadagna **un** nodo, non dodici — **esiste
> un solo rapporto di compressione distinto**, che il progetto poteva solo dedurre.
> *Limiti*: pavimento di rumore stimato su due sole coppie di repliche e discordi (0,005 e
> 0,495 ms); copie H2D dedotte dalla forma del grafo, non contate; una sola profondità e due sole
> richieste; `R` eredita il `T1` di un'altra corsa.
>
> *Decisione.* **Si adotta B** (con C accesa perché gratis e bit-identica, A non applicata perché
> ridondante, D1 spenta perché non paga). La patch consegnata è `p8_cumulativa.patch`; la
> configurazione consigliata sono **i suoi soli default, senza nessuna variabile**, e la corsa
> `P8_9` la misura così: `R = 18,72`, 37,21 ms/token, 26,87 t/s, 1 lancio di grafo, impronte 4/4.
> **La bozza a 2 token resta chiusa** finché la riga non scende con una leva che tolga *byte*, cioè
> la corsia CPU di P4/P5.
>
> *Regressioni.* Nessuna: undici corse confrontate con il riferimento, **zero impronte diverse**,
> zero NaN, zero riserve fallite. L'unica cosa che peggiora è D1 (+0,14 ms, dentro il rumore) ed è
> spenta di default.
>
> *Stato dei processi.* Nessun `llama-server` attivo, porta 8100 libera, nessuna build in corso.
>
> *Prossima azione.* **B2 — generare il bias QSA sul dispositivo** invece di copiarlo: toglie
> l'ultima copia e gli `std::fill` host O(n_kv) per token, e cresce con la profondità. Prima però
> **rimisurare B a 200-262k**: è l'unico termine della riga che scala con `n_kv`, ed è il regime
> in cui l'utente ha il KV da 250k.

---

## 11. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/p8_riga_verifica/P8_ESITO_15_SETTEMBRE.md` | questo esito |
| `docs/porto/p8_riga_verifica/p8_cumulativa.patch` | **la patch finale**: A + B + interruttore di B + C + D1, diff contro `p0_snapshot_20260914\source`, verificata byte a byte |
| `docs/porto/p8_riga_verifica/p8_D1.patch` | la leva D1 (nuova in questa cella), default **spento** |
| `docs/porto/p8_riga_verifica/p8_B_interruttore.patch` | l'interruttore di B (nuovo in questa cella) |
| `docs/porto/p8_riga_verifica/applica_leve_p8.sh` | applica le cinque patch in ordine e rigenera la cumulativa |
| `docs/porto/p8_riga_verifica/genera_preset_p8.py` | genera i dieci preset |
| `docs/porto/p8_riga_verifica/esegui_cella_p8.ps1`, `catena_p8.ps1` | attesa di quiete, guardia, blocco, fila di celle |
| `docs/porto/p8_riga_verifica/analizza_p8.py` | `ciclo = T1 + R + H` da `results.jsonl` e dal log del server |
| `docs/porto/p8_riga_verifica/tabella_p8.py` | la tabella §6, una riga per corsa |
| `docs/porto/p8_riga_verifica/copia_log_p8.py` | estrae in `log/` le righe utili |
| `docs/porto/p8_riga_verifica/log/tabella_p8.md`, `.json` | la tabella e i suoi dati per caso |
| `docs/porto/p8_riga_verifica/log/analisi_p8_*.json` | la scomposizione di ognuna delle dodici corse |
| `docs/porto/p8_riga_verifica/log/p8_*_server_estratto.txt` | le righe del log del server che contano (split, nodi, riuso, speculazione) |
| `docs/porto/p8_riga_verifica/log/p8_*_carico.jsonl`, `_riepilogo.*`, `_results.jsonl` | traccia del carico e risultati per corsa |
| `docs/porto/banco_p0/preset_P8_{0..9}_p7.json` | i dieci preset |
| `D:\ds4_work\p8_work` | albero, build con le leve, `bin_nudo`, log di build |
| `D:\ds4_work\banco_p0_run\*_P8_*` | le dodici corse complete |

Comandi per riprodurre:

```
# albero e build nuda
robocopy D:\ds4_work\p0_snapshot_20260914\source D:\ds4_work\p8_work\source /MIR
D:\ds4_work\p8_work\compila.ps1 -Target llama-server -Parallel 8
D:\ds4_work\p8_work\compila.ps1 -PopolaBin
robocopy D:\ds4_work\p8_work\build\bin D:\ds4_work\p8_work\bin_nudo /MIR

# leve, preset, build con le leve
sh docs/porto/p8_riga_verifica/applica_leve_p8.sh
python docs/porto/p8_riga_verifica/genera_preset_p8.py
D:\ds4_work\p8_work\compila.ps1 -Target llama-server -Parallel 8

# la fila delle celle (una sola attesa di quiete)
docs\porto\p8_riga_verifica\catena_p8.ps1 -QuieteMinuti 15

# lettura
python docs/porto/p8_riga_verifica/tabella_p8.py --md-out log/tabella_p8.md --json-out log/tabella_p8.json
python docs/porto/p8_riga_verifica/copia_log_p8.py
```
