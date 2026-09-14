# HANDOFF — Qwen3.8 Flash Next, 13 settembre 2026

Destinatario: chi riprende il lavoro sul Qwen (nuova sessione, o Codex).
Scritto a fine giornata del 13/9. **Leggere per intero prima di toccare qualsiasi cosa.**

---

## 0. In una pagina

> **Piano del 14 settembre:** documentati [piano di integrazione CPU/GPU](PIANO_CPU_GPU_14_SETTEMBRE.md), [protocollo A/B e qualità](PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md) e [registro di avanzamento](REGISTRO_CPU_GPU_14_SETTEMBRE.md). Stato: prototipo concluso, integrazione nel server ancora da avviare; prossima fase P0 (baseline isolata e prompt congelati), poi contratto della cache e ammissioni CPU/GPU prima del decode reale e di MTP. Nessun nuovo benchmark in questa sessione di pianificazione; produzione invariata, Q4 rinviato. Le soglie nel protocollo sono criteri per le prove future, non prestazioni già raggiunte.

> **Aggiornamento prototipo CPU/GPU FreeToken:** implementato e provato un esecutore CPU fuso sui pesi originali IQ2_S/IQ4_NL. La variante RAM pinnata mappata + callback, con tre miss e due esperti CPU, riduce un blocco da circa 337 a 242 µs (quattro core, mediana di tre processi); il controllo a singola invocazione è più variabile. Copie esplicite + flag invece rallentano. Sono misure di un blocco, non nuovi t/s: generazione libera ancora al precedente 25,08 t/s; obiettivo 50 aperto. Compatibilità dei formati verificata per 47/48 strati, strato 2 IQ3_S da gestire separatamente. Prototipo non integrato nel server, MTP non ancora coperto; produzione invariata. Risultati, limiti e replica: [FREETOKEN_IBRIDO_13_SETTEMBRE.md](FREETOKEN_IBRIDO_13_SETTEMBRE.md), `freetoken_ibrido_evidence.zip`.

> **Aggiornamento FreeToken/Bonsai:** priorità a FreeToken e al motore attuale; ipotesi Q4 CPU rinviata, nessun download completo Q4 avviato. FreeToken main `9535656` non carica il Qwen GGUF corrente e il suo esecutore CPU non supporta IQ2_S/IQ4_NL. Replay a pari memoria: cache attuale calda 75,55%, LRU globale ideale 74,82%; non sostituire la cache sulla sola base del paper. Sonda CPU con pesi originali e catena gate/up-SiLU-down: circa 0,085 ms per un esperto a 8 thread; sono componenti, non nuovi t/s del modello. Le primitive CUDA di sincronizzazione con memoria host funzionano sulla 3060/Windows. Dettagli, limiti e percorso successivo: [FREETOKEN_BONSAI_13_SETTEMBRE.md](FREETOKEN_BONSAI_13_SETTEMBRE.md). I 39 t/s restano un risultato di copia, circa 25 t/s il precedente riferimento di risposta libera.

> **Aggiornamento prestazioni Codex, successivo alla ripresa cache:** implementati e misurati GDN a tile, correzione dei draft n-gram corti, rollback a due token e staging asincrono degli esperti. **414,83 t/s di prefill a 32k con MTP attivo**; **357,61 t/s a 131k, cinque fatti recuperati su cinque**. In copia/modifica del codice **39,19 / 37,76 t/s**, con gli stessi output del riferimento; nel banco di risposta libera a 32k la configurazione combinata dà **25,08 t/s**, quindi i **50 t/s generali restano aperti**. Il profilo mostra un contributo importante anche dei matvec Q6_K residenti: il decode non va più descritto come vincolato esclusivamente al bus. Produzione invariata e server di prova arrestati. Dettagli e limiti: [VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md](VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md); patch, JSON e prove in `strumenti_50_tps_13settembre/`.

> **Aggiornamento Codex, ripresa del 13/9:** il divario della priorità A è stato verificato sul banco HTTP, MTP spento e 64 slot. Su **36.913 piani GPU, zero differenze dal simulatore**; colpi diretti **75,55%** escludendo i primi 64 passi di ciascuna cache. Il **41% dedotto dal PCIe non è un tasso di colpi valido**. Corretta anche la stampa dei contatori, che prima non avanzava durante il replay CUDA. Resta da attribuire il traffico PCIe eccedente il payload degli esperti. Dettagli, replica con CUDA graph attivi, hash e strumenti: [RIPRESA_CACHE_13_SETTEMBRE_CODEX.md](RIPRESA_CACHE_13_SETTEMBRE_CODEX.md). I dati storici sotto sono conservati come contesto; la produzione resta invariata.

Oggi si è lavorato su tre fronti. Uno ha prodotto una vittoria, due sono stati **chiusi** con
misure, e restano **due priorità massime**, entrambe sul decode:

| fronte | esito |
|---|---|
| Sparse flash attention a teste 256 | **VINTA**: +18,1% di prefill a 131k. Spenta di default, gate di qualità in corso |
| Testa MTP e suoi esperti in VRAM | **CHIUSO, perdente di 7×**. Non riproporre |
| Bozza Q4_K_M | **CHIUSO, neutra**. Non riproporre come leva di velocità |
| **A. Divario colpi cache: 41% reale contro 75% simulato** | **APERTO — PRIORITÀ MASSIMA**, vale ~metà del traffico sul bus |
| **B. Speculatori a n-grammi accanto alla testa MTP** | **APERTO — PRIORITÀ MASSIMA**, mai provato, esiste già nell'albero |

Il decode è **legato al bus**: 562 MB per token generato a 64 slot, ~15 GB/s misurati sul PCIe.
Non è legato al calcolo. Ogni proposta va pesata in byte sul bus, non in FLOP.

---

## 1. Che cosa gira, e dove

### 1.1 Binari

Albero: `C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean`

| | percorso | uso |
|---|---|---|
| **Produzione** | `qwen38_clean\bin_prod\` | **CONGELATO**. È ciò che usa il lanciatore di tutti i giorni. Non ricompilare mai qui |
| **Sperimentale** | `qwen38_clean\build\bin\` | Ricompilabile. Solo il lanciatore SPERIMENTALE lo usa |

Impronte (SHA256, primi 8) al 13/9 sera. **Fra i due insiemi differiscono SOLO due file**:

| file | bin_prod | build\bin |
|---|---|---|
| `ggml-cuda.dll` | `481D89C6` (183,2 MB) | **`321BA4AC`** (183,4 MB, 13/09 10:38) |
| `llama.dll` | `2D558CA0` (2,5 MB) | **`59A97335`** (2,5 MB, 13/09 08:39) |
| `ggml.dll` | `093DCDAB` | identico |
| `ggml-base.dll` | `5F4BA614` | identico |
| `ggml-cpu.dll` | `245C1E78` | identico |
| `llama-common.dll` | `13648095` | identico |
| `llama-server.exe` | `50F9F83B` | identico |
| `llama-server-impl.dll` | `352E70EC` | identico |
| `mtmd.dll` | `77BBDDF8` | identico |
| `paired_probe.exe` | `AD90A6E2` | identico |
| `incremental_probe.exe` | `986D9677` | identico |
| `moe_batch_math_probe.exe` | `93E91852` | identico |

**Conseguenza pratica:** tutta la sparse FA vive in quelle due DLL. Per promuoverla in produzione
basta copiarle in `bin_prod`. Per annullarla basta non copiarle.

> **Nota del 14/9 (P0 del registro CPU/GPU).** La tabella sopra è **superata**: allo snapshot di
> P0 (`D:\ds4_work\p0_snapshot_20260914\`) fra `bin_prod` e `build\bin` differiscono **quattro**
> file, non due. Si sono aggiunte `ggml-base.dll` (`D3842EB1` contro `5F4BA614`) e
> `llama-common.dll` (`2253BD46` contro `13648095`), ricompilate il 13/9 alle 13:09-13:10 durante
> il lavoro sulle prestazioni successivo alla stesura di questo handoff. Conseguenza pratica
> aggiornata: «promuovere la sparse FA copiando due DLL» **non è più vero**; una copia di
> quattro DLL non sarebbe più una promozione isolata della sparse FA. Inoltre la `ggml-cuda.dll`
> effettivamente presente in `build\bin` allo snapshot è `26BA28B4` (13/9 12:57), non `321BA4AC`
> come indicato al §4.A: chi cercasse `LLAMA_MOE_HIT_REPORT` "nella DLL della §4.A" guarderebbe un
> binario diverso da quello descritto. Dettagli in
> [REGISTRO_CPU_GPU_14_SETTEMBRE.md](REGISTRO_CPU_GPU_14_SETTEMBRE.md), voce P0.

`ggml-cuda.dll` è stata ricostruita tre volte il 13/9: `20653E30` (sparse FA + log),
poi **`321BA4AC`** (aggiunge il contatore dei colpi di cache, §4.A). Entrambe le aggiunte sono
**spente di default** e si accendono da variabile d'ambiente, quindi la DLL nuova si comporta
esattamente come quella di produzione finché non si chiede altro.

### 1.2 Backup dei sorgenti

`qwen38_clean\backup_pre_sparse_fa_20260913\` — contiene i tre sorgenti **prima** della patch di oggi
più le due DLL di allora:

```
fattn-mma-f16.cuh  2117218C
fattn.cu           7918AE88
qwen4exp.cpp       38BC6F4E
ggml-cuda.dll      481D89C6
llama.dll          2D558CA0
```

Altri backup già presenti: `backup_pre_concat_cont_20260910`, `backup_pre_mtp_light_20260910`,
`backup_pre_pool_seqrm_20260910`, `backup_pre_spec_profile_20260910`.

### 1.3 Modello e bozze su disco

```
Modello   D:\models\qwen38flashnext\UD-IQ3_XXS\Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf
          176,94 B, arch qwen4exp, 512 esperti / 10 attivi, 48 strati, teste 256, IQ3_XXS 76,32 GiB
mmproj    D:\models\qwen38flashnext\mmproj-F16.gguf
Bozze MTP D:\models\qwen38flashnext\MTP\
          mtp-...-shared-Q8_0.gguf     2786 MB  <- quella in uso (97 MiB VRAM + 2550 mappati)
          mtp-...-shared-Q4_K_M.gguf   1907 MB  <- provata: NEUTRA (§3.2)
          mtp-...-Q8_0.gguf            4137 MB  <- non condivisa, MAI PROVATA
```

Hardware: RTX 3060 12 GB, Ryzen 5800X (16 thread), 96 GB DDR4, PCIe 4.0 x16 (~25-28 GB/s pratici).

### 1.4 Lanciatori

**Produzione** — `C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat`
Punta a `bin_prod`, contesto 262144, porta 8100, API key `Sticazzi86`, vision + WebP attivi.
Non è stato toccato oggi.

**Sperimentale** — `C:\Users\imanu\Desktop\avvia Qwen38 SPERIMENTALE.bat`
Punta a `build\bin`, log in `qwen38_server_logs_sperimentali`. Primo argomento = `USE_MTP` (0/1).
Guardia di istanza unica: rifiuta l'avvio se c'è già un `llama-server.exe`.

Manopole, tutte da variabile d'ambiente prima del lancio:

| variabile | default | significato |
|---|---|---|
| `QWEN4EXP_SPARSE_FA` | `0` | **NUOVA.** Sparse FA a teste 256. Vedi §2 |
| `SPEC_TYPES` | `draft-mtp` | **NUOVA.** Elenco separato da virgole. Vedi §4.2 |
| `MOE_SLOTS` | `64` | Slot della cache esperti per strato |
| `DRAFT_FILE` | shared-Q8_0 | Percorso del .gguf della testa MTP |
| `DRAFT_EXPERTS` | `ram` | `ram` = esperti bozza mappati; `vram` = residenti. **Ramo `vram` MAI ESEGUITO** |
| `SPEC_N_MAX` / `SPEC_N_MIN` / `SPEC_P_MIN` | `1` / `1` / `0` | Manopole della bozza. **La configurazione storica resta la migliore** |

Il nome del log riporta l'assetto: `sper_mtp<N>_n<N>_p<N>_<ram|vram>_s<slot>_sfa<0|1>_<data>.log`.

> **TRAPPOLA, già pagata due volte oggi.** `cmd` legge i file batch **per posizione in byte**:
> modificare il .bat mentre un `cmd` lo sta eseguendo fa riprendere l'esecuzione da un punto
> sbagliato. Modificare il lanciatore **solo** quando nessun server è attivo.
> Seconda trappola: una variabile che contiene `|` viene espansa **prima** dell'analisi dei
> caratteri speciali, quindi il pipe spezza il comando. Per questo la regex degli esperti è
> `.*ffn_.*_exps.*` e non `.*ffn_(gate|up|down)_exps.*` (verificato equivalente: aggancia gli
> stessi 3 tensori e non tocca gli `_shexp`).

### 1.5 Strumenti di misura

Copiati oggi in `docs/porto/strumenti_qwen38_13settembre/` (prima erano in una cartella temporanea
di sessione e sarebbero andati persi):

| file | cosa fa |
|---|---|
| `banco_http.py` | Banco HTTP: prefill + decode, `--ctx-tokens`, `--temperature`. Stampa `text_sha` e salva il testo |
| `misura_bus.py` | Come sopra ma campiona `nvidia-smi dmon -s t` attorno alla corsa: dà i **MB per token sul PCIe** |
| `prova_reale.py` | Qualità: 5 aghi a profondità note (5/25/50/75/95%) + una domanda tecnica. Rileva il troncamento |
| `arm_sparse.ps1` | Un braccio: ferma il server, lo riavvia con le manopole, aspetta, misura |
| `ab_long.ps1` | Coppia accesa/spenta a contesto lungo, parametro `-Ctx` |
| `ab_reale.ps1` | Coppia accesa/spenta sulla prova di qualità |
| `simula_cache.py` | Simulatore della cache esperti sulle tracce del router |
| `build_sparse_fa.cmd` | Ricompila `ggml-cuda`, `llama`, `llama-server` (Ninja, arch 86) |
| `build_llama_dll.cmd` | Ricompila la sola `llama.dll` (3 s) |
| `banco_ripetizione.py` | Carico a **ripetizione**: fa riprodurre al modello un file che ha nel prompt. È il solo regime in cui un n-grammo aggancia (§4.B) |
| `ab_ngram.ps1` | Coppia `draft-mtp` contro `draft-mtp,ngram-mod` sul carico a ripetizione |

---

## 2. La vittoria di oggi: sparse FA a teste 256

### 2.1 Che cos'era

La ricognizione dell'11/9 diceva «resta la sparse FA a teste 256, giorni di lavoro sui kernel».
**Stima sbagliata.** Non mancava il kernel: mancava il permesso. Tre righe:

1. `source\ggml\src\ggml-cuda\fattn-mma-f16.cuh:1758`, `ggml_cuda_flash_attn_ext_mma_f16_may_use_sparse`:
   ammessa la forma `(256, 256, 1, 8)` accanto alle due MLA.
   Non serviva istanziare niente: `DECL_FATTN_MMA_F16_CASE(256,256,1,8)` esisteva già in
   `template-instances\fattn-mma-f16-instance-ncols1_1-ncols2_8.cu`, e la variante `use_sparse=true`
   si compila dentro la stessa funzione di caso sotto `if constexpr (may_use_sparse(...))`.
2. `source\src\models\qwen4exp.cpp:1197`: passato `top_k->ne[0]` invece di `0` come `n_kv_max` a
   `build_attn_mha`. **La riga era già scritta e commentata**, con un TODO e il riferimento alla
   pull upstream 27970.
3. `source\ggml\src\ggml-cuda\fattn.cu`, `ggml_cuda_flash_attn_ext_mma_f16_shall_use_sparse`:
   cancello d'ambiente `QWEN4EXP_SPARSE_FA` (spento di default) + una riga di log.

Perché `ncols2 = 8`: 24 teste su 2 danno rapporto GQA 12 (> 4), e la strada sparsa impone
`ncols1 = 1`. Il resto dell'impianto è già generico: `launch_fattn` alloca il buffer degli indici e
chiama `ggml_cuda_flash_attn_ext_compact_mask`, che **comprime la maschera** in un elenco di indici
(`fattn-common.cuh:1095-1102`). Gli indici non vanno inventati: la nostra QSA una maschera quasi
tutta a meno infinito la produce già.

### 2.2 Quanto vale

Server sperimentale, MTP spento, 64 slot, greedy, `prompt_tps`:

| contesto | spenta | accesa | delta |
|---|---|---|---|
| 32k | 337,58 / 338,22 | 337,21 / 337,34 / 337,92 | **zero** |
| 131k | **249,78** (525,5 s) | **294,95** (445,1 s) | **+18,1%**, 80 secondi risparmiati |

**Non estrapolare da uno zero.** A 32k avevo dedotto «al massimo 3-4% a 250k» partendo dal nulla
misurato lì: sbagliato, con rumore ±0,2% quello zero vincola poco e il termine quadratico
dell'attenzione cresce in fretta. Il guadagno **cresce con la profondità**: a 250k ci si aspetta di
più del 18%. **Da misurare** (§4.1).

### 2.3 Dove agisce e dove no

- Solo nel **prefill**, e solo nei **12 strati QSA** (`compress_ratios` non nullo, uno ogni quattro).
- **Nel decode no, per costruzione.** Lì `build_layer_attn` usa il *gather*: con al massimo tre
  token in volo e cache profonda, `build_attn_qsa` copia le celle scelte e ci fa attenzione densa
  sopra, senza arrivare alla chiamata che la sparse intercetta. Vale anche con MTP acceso, perché
  la verifica gira a 2-3 righe.
- Il backend la rifiuta sotto `n_kv >= max(4096, 2*n_kv_max)`, cioè ~4608 celle. Giusto così: la
  strada sparsa lavora a **una** colonna di query per tile invece di quattro, e sotto contesto medio
  perderebbe.

### 2.4 Diagnostica

Il log stampa una riga sola: `sparse FA 256: ATTIVA|rifiutata | n_kv_max=.. n_kv=.. mask=[..] n_q=..`.
A 131k con la leva accesa: `ATTIVA | n_kv_max=2051 n_kv=4352 mask=[4352,2048,1] n_q=2048`.

> **Tace sotto 4096 celle di proposito.** Al primo tentativo l'annuncio «una volta sola» era stato
> consumato dalla chiamata di **riscaldamento** (n_kv=256, n_q=2) e il prefill vero restava muto.
> Regola generale: una diagnostica one-shot va sempre esclusa dal warmup.

### 2.5 Identità dell'uscita

A 131k i due bracci danno testo **identico byte per byte** (`8222304f01a9`). A 32k invece divergevano
al carattere 15. La macchina **è deterministica** (verificato: due corse identiche, stesso testo, vedi
§6), quindi la divergenza era della leva. Lettura: differenze numeriche minime che ogni tanto
ribaltano un pareggio fra due logit, non un errore sistematico.

---

## 3. Fronti CHIUSI (non riaprire senza un motivo nuovo)

### 3.1 Testa MTP e suoi esperti in VRAM — perde di 7×

Curva degli slot **misurata** (senza MTP, contesto corto, 768 token, seconda richiesta):

| slot | VRAM cache | t/s | MB/token sul bus |
|---|---|---|---|
| 0 | 0 | 14,71 | 190 — *gli esperti li calcola la CPU, non passano dal bus* |
| 32 | 2898 MiB | 22,18 | 742 |
| 64 | 5797 MiB | 24,64 | 562 |

**Tasso di cambio da usare per ogni proposta che chiede VRAM: 2,9 GB = +11% di velocità.**

Gli esperti della bozza valgono ~52 MB/token, cioè **il 6% del traffico** (446 bozze × 52 MB su 26 s
= 0,9 GB/s dentro i 15,4 misurati). Metterli in VRAM costa 2,5 GiB in Q8 (28 slot, ≈ −10%) o 1,7 in
Q4 (19 slot). **Perde di circa sette a uno.**

Corollario sulle bozze lunghe: il ciclo modellato (verifica 38,9 ms base + 13,8 per riga, misurati a
205k) ha il massimo a **n = 2** con accettazione 0,753, sia con bozza in RAM sia in VRAM. Servirebbe
accettazione ≥ 0,85 perché n = 3-4 diventi il migliore. E c'è una collisione: n righe pretendono fino
a `unici max` esperti per strato (1..8 righe: 10/20/30/40/50/59/69/77), quindi 7 righe sforano già i
64 slot, e mettere la bozza in VRAM taglierebbe gli slot a 36. Le due cose sono nemiche.

### 3.2 Bozza Q4_K_M — neutra

1750 MiB mappati contro 2550 della Q8, 58 MiB VRAM contro 97. Velocità **29,54 / 29,57** contro
29,62 / 29,57 della Q8: identiche. Accettazione 0,717 contro 0,729. Guadagna 800 MiB di RAM e nulla
di più. Non riproporla come leva di velocità.

### 3.3 `--moe-expert-cache-inserts` — leva scollegata

Il log stampa «2 inserts/step» anche quando quel ramo non gira. Con `LLAMA_MOE_DEMAND_GPU=1`,
`llama-graph.cpp:2136-2142` ricollega i tensori e azzera `mcache`, e `llama-moecache.cpp:398`
registra l'osservatore che riempie `pending` **solo se `demand_gpu` è spento**. Il tetto vive in
`llama_moe_cache_step()`, che non ha nulla da fare. Il cammino a domanda installa **ogni** mancanza.

### 3.4 «La speculazione sporca la cache» — falsificata

Con MTP 451 MB/token, senza 562: la speculazione **riduce** i byte per token del 20%, perché la riga
di verifica ammortizza gli stessi esperti su 1,75 token accettati.

---

## 4. LE DUE PRIORITÀ

### 4.A — Il divario dei colpi di cache: 41% reale contro 75% simulato

**Perché è la cosa più grossa rimasta.** Il decode è legato al bus. Senza cache servirebbero
48 × 10 × 1,888 MiB = **906 MiB per token**. A 64 slot ne misuriamo **562 MB**, cioè un tasso di
colpi reale del **~41%**. Il simulatore, sulle stesse tracce e con la stessa politica, ne promette il
**75,4%**. Chiudere il divario significa quasi **dimezzare il traffico sul bus**, e siamo bus-bound:
è un ordine di grandezza sopra qualunque cosa riguardi l'attenzione.

A 32 slot: misurati 742 MB/token (~22% di colpi) contro il 63,1% simulato. **Il divario c'è a
entrambe le capienze**, e anche la pendenza non torna (misurata +32% di traffico da 64 a 32 slot,
simulata +50%).

**Che cosa è già stato escluso:**
- La **politica di sfratto** è identica fra simulatore e kernel: vittima con frequenza efficace
  minima, a pari merito la meno recente, a pari merito indice minore, scelta solo fra slot non usati
  dal passo corrente (`fork-moe-kernels.cuh:445-502`).
- Il **decadimento** è identico: epoca = passo ≫ 6, frequenza efficace = `freq >> epoche_trascorse`,
  azzerata oltre 32, incremento che riscrive valore ed epoca (`fork-moe-kernels.cuh:105-113`, `242-265`).
- Il tetto di inserimenti **non c'entra** (§3.3).
- Il traffico misurato **è** trasferimento di esperti: a 0 slot crolla a 190 MB/token perché gli
  esperti li calcola la CPU e non attraversano il bus. Non esiste una «costante» di altra natura.

**Sospetto principale:** le tracce. `routes.bin` è stato raccolto su un carico diverso dal banco, e la
località degli esperti dipende dal testo. Ma è un sospetto, non una misura.

**Piano proposto, in ordine:**

1. **Contare i colpi veri, non dedurli. FATTO il 13/9, è nella DLL `321BA4AC`.**
   Il 41% era calcolato per differenza dai byte sul PCIe; ora c'è un contatore diretto.
   Due contatori sul dispositivo per gruppo (cioè per strato) accumulano `n_unique` e `n_misses`
   del piano; l'inserzione è unica, subito dopo il punto in cui i due cammini del kernel (a warp e
   a blocco) si ricongiungono, e la lettura somma tutti gli strati.
   **Uso: `LLAMA_MOE_HIT_REPORT=<N>`** stampa nel log `moe cache: richiesti .., mancanti .., colpi ..%`
   ogni N chiamate al piano. Spento di default; la copia dal dispositivo sincronizza, quindi N va
   tenuto grande (4096 è già innocuo). Codice: `fork-moe-kernels.cuh` (parametro `demand_counters`
   e accumulo) e `moe-demand.cuh` (campo `counters`, allocazione, lettura e stampa in `remap`).
   *Con questo il resto del fronte diventa falsificabile: confrontare il numero misurato con il
   75,4% del simulatore sulle stesse tracce.*
2. **Ricalibrare le tracce sul carico vero.** Esiste `route_capture.cpp` (probe di una sessione
   precedente). Raccogliere le rotte **durante il banco** e rilanciare `simula_cache.py`: se il
   simulato scende verso il 41%, il modello è sano e il tetto è quello; se resta al 75%, c'è
   qualcosa di strutturale nel cammino reale che il simulatore non vede.
3. Solo dopo, se il divario è strutturale: guardare l'ordine di inserimento, la finestra di
   `LLAMA_MOE_CACHE_BATCH=3` e la cache di fase (`LLAMA_MOE_PHASE_CACHE=1`), che rilascia e
   ripristina fra prefill e decode.

**Riferimenti di codice:** `source\ggml\src\ggml-cuda\moe-demand.cuh` (binding, `remap`),
`source\ggml\src\ggml-cuda\fork-moe-kernels.cuh` (piano, sfratto, trasferimento),
`source\src\llama-moecache.cpp` (cache lato host, inerte con demand attivo),
`source\src\llama-graph.cpp:2112-2155` (scelta del cammino).

**Strumento:** `misura_bus.py` dà i MB/token; il riferimento da battere è **562 MB/token a 64 slot**,
24,64 t/s senza MTP e 29,6 t/s con MTP a contesto corto.

### 4.B — Speculatori a n-grammi accanto alla testa MTP

**Perché vale la pena.** Il harness è un assistente di codice: buona parte dell'uscita **ricopia**
pezzi del prompt. Un n-grammo che aggancia una ripetizione esatta produce una bozza a costo quasi
nullo, mentre la testa MTP costa 5,0 ms per token abbozzato (di cui ~3,5 di bus). Mai provato.

**Esiste già tutto nell'albero.** Nomi accettati da `--spec-type` (elenco separato da virgole,
`speculative.cpp:34-46`):

```
none, draft-simple, draft-eagle3, draft-mtp, draft-dflash, draft-dspark,
ngram-simple, ngram-map-k, ngram-map-k4v, ngram-mod, ngram-cache
```

Manopole già esposte al server: `--spec-ngram-mod-n-min/-n-max/-n-match`,
`--spec-ngram-simple-size-n`, `--spec-ngram-map-k-size-n`, `--spec-ngram-map-k4v-size-n`,
`--lookup-cache-static` / `--lookup-cache-dynamic` (per `ngram-cache`).

**L'avvertimento che decide l'esito.** Non si sommano: è una **catena di fallback con precedenza**.
`common_speculative_init` (`speculative.cpp:2672-2684`) mette gli n-grammi **prima** dei tipi con
modello di bozza, e il commento è esplicito («questa lista definisce la priorità»). In
`common_speculative_draft` (`speculative.cpp:2868-2903`) gli implementatori vengono provati in ordine
e appena uno produce una bozza per una sequenza quella viene marcata `drafting = false`: gli
implementatori successivi la saltano. **Quindi l'n-grammo scavalca la testa MTP ogni volta che
aggancia**, e conviene solo se, quando spara, accetta più dello **0,75** attuale della testa.

**Osservabilità: c'è già.** `server-context.cpp:713` chiama `common_speculative_print_stats(spec)`
**dentro `print_timings()`**, cioè a ogni richiesta, subito dopo la riga `draft acceptance = ...`.
Stampa per **ogni implementatore** `n_call_begin`, `n_call_draft`, `n_call_accept` e `t_draft_us`.
Si vede quindi quante volte l'n-grammo ha sparato e quanto è costato, senza ricompilare nulla.

**Piano proposto:**

1. Braccio di riferimento: `SPEC_TYPES=draft-mtp` (com'è oggi). Riferimenti da battere:
   **27,2 t/s greedy a 32k**, 29,6 a contesto corto, accettazione 0,75, 1,76 token per ciclo.
2. Bracci di prova: `SPEC_TYPES=draft-mtp,ngram-mod`, poi `draft-mtp,ngram-simple`, poi
   `draft-mtp,ngram-map-k`. Un braccio per volta, stesso banco.
3. Leggere nel log, per ciascuno: quante bozze ha prodotto l'n-grammo contro la testa, e
   l'accettazione di ciascuno. **Se l'n-grammo spara spesso ma accetta meno di 0,75, la
   combinazione perde** ed è colpa della precedenza, non dell'idea.
4. Carico realistico obbligatorio: un banco che rigenera testo già presente nel prompt (rifattorizza
   questo file, riscrivi questa funzione). Sul testo libero l'n-grammo non aggancia quasi mai, e si
   misurerebbe il nulla.
5. Se la precedenza è il problema e l'idea è buona, il passo successivo è invertirla o renderla
   condizionale (soglia di lunghezza del match) in `speculative.cpp:2672-2684`.

---

## 5. Lavoro in volo al momento della consegna

### Gate di qualità della sparse FA — **PASSATO**

`ab_reale.ps1 -Ctx 131072`: cinque fatti verificabili piantati al 5/25/50/75/95% di un contesto da
131k, sui due bracci. **5 su 5 ritrovati da entrambi**, compreso quello al 95%. La sparse **non
ampute il contesto**. Ha senso: il top-k è **per strato**, i 12 strati QSA scelgono ciascuno le
proprie 2051 celle, e i 36 strati ricorrenti trasportano informazione a prescindere.

Una corsa precedente aveva mostrato un ago perso dal braccio sparso: era **un artefatto dello
strumento**, non della leva. Tre difetti indipendenti, tutti corretti: cattura del testo che
ignorava `reasoning_content` (con `--reasoning on` l'impronta era quella della stringa vuota),
budget di 120 token che poteva esaurirsi dentro il ragionamento, e un solo ago in un solo braccio.

La **domanda tecnica** dello stesso test invece **non misura nulla e va corretta prima di
riusarla**: il riempimento scorre i file in ordine alfabetico e a 131k si ferma dentro `common/`,
quindi chiedeva di codice che non era nel contesto. Entrambi i bracci hanno risposto correttamente
che quel codice non c'era — comportamento sano, ma domanda inutile. Nella versione in repo la
domanda è già stata spostata su `common/arg.cpp`, che nel riempimento c'è sempre.

**Resta da fare sulla sparse:**
1. Misurare la coppia a **250k**: `ab_long.ps1 -Ctx 250000`. È il punto operativo vero del harness,
   e il guadagno cresce con la profondità.
2. Decidere la promozione: copiare `ggml-cuda.dll` e `llama.dll` da `build\bin` a `bin_prod` e
   accendere `QWEN4EXP_SPARSE_FA=1` nel lanciatore di produzione. **Non ancora fatto**: richiede
   una decisione esplicita perché tocca ciò che gira tutti i giorni.

---

## 6. Regole di metodo apprese oggi (le più costose)

1. **Il banco è deterministico.** Due corse identiche danno testo **byte per byte identico**
   (greedy, `-np 1`, MTP spento): il testo generato è un **oracolo** di correttezza, non un indizio.
   Pavimento di rilevabilità sul prefill: **±0,2%**. Prima di giudicare una leva sulla correttezza,
   girare due volte il braccio di riferimento e verificare che le impronte coincidano.
2. **Firmare `content` da solo non basta.** Con `--reasoning on` il modello può mettere tutto in
   `reasoning_content`: l'impronta diventa quella della stringa vuota (`e3b0c44298fc`) e il controllo
   non controlla niente.
3. **Una diagnostica one-shot va esclusa dal warmup**, altrimenti la prima chiamata (minuscola) le
   consuma il colpo e il caso vero resta muto.
4. **Non estrapolare da uno zero misurato.** Uno zero con rumore ±0,2% vincola molto meno di quanto
   sembri se il fenomeno è quadratico.
5. **Una leva esiste solo se il ramo è raggiungibile.** Due casi oggi: il tetto di inserimenti della
   cache, e il log che lo stampa lo stesso.
6. **Non modificare un .bat mentre un `cmd` lo esegue** (lettura per offset), e **niente `|` dentro
   una variabile** espansa in un comando.
7. **A/B sullo stesso binario.** Mettere ogni nuova leva dietro una variabile d'ambiente costa una
   riga e toglie di mezzo il rumore che segue una compilazione (fino al 15%).

---

## 7. Numeri di riferimento da battere

| grandezza | valore | condizioni |
|---|---|---|
| Prefill a 131k | 249,78 t/s densa · **294,95 sparsa** | MTP off, 64 slot |
| Prefill a 32k | ~337,5 t/s | indifferente alla sparse |
| Decode contesto corto, MTP on | **29,6 t/s** | 64 slot, greedy |
| Decode contesto corto, MTP off | 24,64 t/s | 64 slot |
| Decode a 32k, MTP on greedy | 27,2 t/s | accettazione 0,756, 1,76 token/ciclo |
| Decode a 187k | 24,1-24,6 t/s | MTP in parità con no-MTP |
| Traffico PCIe | **562 MB/token** a 64 slot · 742 a 32 · 190 a 0 | MTP off |
| Colpi cache reali | **~41%** a 64 slot · ~22% a 32 | contro 75,4% / 63,1% simulati |
| Accettazione MTP | 0,75 | il numero da battere per gli n-grammi |

---

## 8. Cose mai provate, in coda

- Testa MTP **non condivisa** `mtp-Qwen3.8-Flash-Next-Q8_0.gguf` (4137 MB): sta in RAM, non costa
  slot. L'accettazione è l'unica variabile che sposterebbe l'ottimo verso bozze più lunghe.
- Sidecar a 8 bit sui tensori `o_proj` (idea da halogen-flash-server): qualità, non velocità.
- Ramo `DRAFT_EXPERTS=vram` del lanciatore: scritto ma **mai eseguito**; i conti dicono di non farlo,
  la prima corsa va considerata un collaudo.
- Crash CUDA intermittente (2 casi su ~1400 richieste, 10-11/9): mai riprodotto, causa ignota.
