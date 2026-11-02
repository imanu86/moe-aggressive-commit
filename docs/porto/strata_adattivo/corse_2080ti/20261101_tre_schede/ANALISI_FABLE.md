# Dove si perde tempo in scrittura sulla catena 3080 Ti + 2080 Ti — analisi del 2/11/2026 (Fable)

Sola lettura: codice `Strata-wt\upsync-v0.2.9` (ramo `lab/upsync-v0.2.9`, `b6ba3fa6`), registri delle corse di questa cartella
(`corse/L*`, `corse/u20_*`, `corse/n20_*`), `docs/PIPELINE2.md` (misure di ottobre), banco della comunità e issue a monte con `gh`.
Nessun motore avviato, nessuna compilazione, nessuna GPU toccata. Convenzione: **M** = misurato, **D** = dedotto dal codice o dai
registri, **S** = stima. I numeri senza marchio vengono dai registri.

## 0. Conclusione

1. **La premessa dell'owner è giusta sul riuso, sbagliata sul confronto.** Il riuso è al 98-99% (M) e 15.011 coppie (strato, esperto) su
   24.576 sono in VRAM (61%). Ma «la 3090 fa oltre 100, la 5090 130» non trova riscontro: l'unica 3090 singola misurata con IQ3_XXS a
   prompt freschi e temperatura 0 fa 89/91/79 t/s (motore 0.1.26, macchina virtuale); sopra 100 solo con IQ2_XS, con due 3090 o con
   IQ3_S più opzioni sperimentali. La 5090 con IQ3_XXS fa 172-181, non 130. Nessuna 3090 o 5090 è stata misurata col nostro motore
   (0.1.55). La nostra macchina a 96-108 sta **sopra** l'unica 3090 confrontabile e al 55-60% di una 5090. Dettaglio al §1.
2. **Il percorso CPU non pesa per il calcolo, pesa per i giri di andata e ritorno con l'host.** Ogni strato, anche senza esperti mancati,
   aspetta che l'host legga gli id dal router, scriva il piano e lo pubblichi; nelle misure di ottobre (configurazione con la 3060, M)
   queste attese valevano 3,8 ms su 28,3 di finestra fresca (piano 2,0 + righe CPU 1,8), più 2,1 ms di catena di bozze e ~2 ms di
   buchi fra i nodi. Il lavoro vero dei 7 lavoratori (0,4-1,1 esperti mancati per strato-finestra, D) è una frazione di quello.
3. **Escludere la CPU con le opzioni di oggi non si può senza perdere il modello**: `--no-pool` spegne anche il percorso degli esperti
   residenti; mandare i mancati sulla scheda via PCIe (`--pcie-frac 1` + `STRATA_ARENA_PIN_GIB=0`) è possibile sulla carta ma costa
   0,18-0,35 ms per esperto (S) contro ~0,05-0,2 della CPU, con un rischio WDDM documentato; saltarli cambia le risposte. Il modo giusto
   di «togliere la CPU dal filo» è togliere i giri con l'host dove non servono (`STRATA_VERIFY_DEVICE_PLAN=1`, lavoratori che non dormono).
4. **Due difetti di configurazione trovati nel codice, a costo zero e senza cambiare il testo**: (a) con due schede di architettura diversa
   il motore **non applica la tabella di interruttori sm_86** (verificato in `generate.cpp:3615-3627`; a monte è la #3313): mancano
   `STRATA_GU_SWIGLU=1`, `STRATA_GR_UP75=1`, `STRATA_CPU_IQ_ALL_EXACT1=1`; (b) `STRATA_POOL_SPIN_US=100` fa dormire i lavoratori 100 µs
   dopo l'ultimo lavoro (il default è 20 ms), quindi quasi ogni strato con un esperto mancato paga un risveglio da variabile di condizione.
5. **La leva misurata che rende di più è già in coda**: `STRATA_SM75_PERF=1 STRATA_EXP_MODE=8` dà scrittura 103-110 contro 92-108 delle
   due basi e lettura +6-8% a 32K/128K (M, 2 bracci contro 2 basi, `_b` ancora in corso). Attenzione: `STRATA_EXP_MODE=8` vale per
   **tutte** le schede, 3080 Ti compresa (`iq_kernels.cu:6147-6150`), quindi non si sa quale delle due guadagna.
6. Il rumore di questa macchina sulla scrittura è fino al 10% fra due corse identiche (Lbase_a 98,2 contro Lbase_b 107,8 a 4K): nessuna
   leva da meno del 5% si prova con una coppia sola. La lettura invece è stabile (±1%).

## 1. I numeri della comunità: cosa fanno davvero 3090 e 5090

Fonti: `docs/COMMUNITY_BENCHMARKS.md` (nessuna riga per 3090, 3090 Ti, 3080, 2080 Ti o 4090: solo una 5090 con IQ2_XS), le cartelle
`bench/results/*`, `docs/DETAILS.md`, issue a monte. Terne a 4K/32K/128K; «bm» = stesso `benchmark.py` dell'owner.

| macchina | motore | quant | condizioni | scrittura t/s | lettura t/s | bm |
|---|---|---|---|---|---|---|
| **noi**: 3080 Ti + 2080 Ti 22 GB, split 20, 5800X, Windows | 0.1.55 (v0.2.9+pila) | IQ3_XXS | T0, freschi, spec 4, catena doppia | 98-108 / 92-98 / 96-97 (Lbase a/b) | 922 / 1756-1775 / 2064-2072 | sì |
| 1x 3090 280 W, EPYC 7453, Ubuntu in VM | 0.1.26 | IQ3_XXS | T0, freschi, 256 | **89,2 / 90,6 / 79,3** | 1772 / 2160 / 2174 | no |
| 2x 3090, stessa macchina | 0.1.26 | IQ3_XXS | solo 32K | 96,7 | 1159 | no |
| 1x 3090 su Thunderbolt 3, Win 11 | 0.1.34 | IQ3_XXS / IQ2_XS | T0, prompt 1,7-27K | 60-81 / **101-112** | 128-618 | no |
| 1x 3090, 5600X, Win 11 | 0.1.42 | IQ3_S | T0,7, prompt da ~26 token | 97,2; con `--adapt-async 1` 107,7 | — | no |
| 1x 3090 Ti, Z840 PCIe 3 | 0.1.38 | IQ3_S | T0, prompt in cache | 94,9 / 98,8 / 90,1 | ~1300 | no |
| 1x 3080 Ti 12 GB (issue #4841) | 0.1.53 | IQ3_XXS | uso reale, spec 12-16 | 90-100, cali a 45 | — | no |
| 2x 3090, 5800X (issue #4584) | 0.1.47 → 0.1.53 | IQ3_S | T0,7 | 134/132 → 103/110 | — | no |
| 1x 5090, 9700X, Win 11 | 0.1.39 | **IQ3_XXS** | T0, freschi, 256 | **171,7 / 181,2 / 178,3** | 3775 / 6367 / 6080 | adattato |
| 1x 5090, 9700X | 0.1.39 | IQ3_S | idem | 164 / 161 / 168 | 3072 / 5963 / 5803 | adattato |
| 1x 5090, 285K, Ubuntu | 0.1.29 | IQ2_XS | idem | 179 / 176 / 165 | 4270 / 5543 / 5779 | sì |
| 2x 2080 Ti 22 GB a **100 W**, 5950X, Ubuntu | 0.1.40 | IQ3_XXS | T0, freschi | 52,8 / 42,5 / — | 411 / 477 | dichiarato |

Il confronto non è equo per questi motivi, in ordine di peso:

- **Quantizzazione**: sulla stessa 3090 IQ2_XS fa 111 e IQ3_XXS 81 (−27%). Il «>100» della 3090 viene quasi certamente da IQ2_XS o da due
  schede; l'unica stima IQ3_XXS su 3090 nel repo è in `docs/DETAILS.md` («~103/89/71, not measured, ±20%», precedente al motore 0.1.13).
- **Versione del motore**: i dati 3090/5090 sono tutti su 0.1.26-0.1.43; a monte si segnalano cali dopo 0.1.47 (−20% in #4584, −7/−14% in #4778,
  80→60 in #4841). Nessuna 3090 o 5090 misurata su 0.2.x.
- **Una scheda contro due**: a 0.1.26 la seconda 3090 alza la scrittura a 32K da 90,6 a 96,7 ma dimezza la lettura (2160 → 1159). Noi a 1760
  stiamo sopra quel valore a due schede, sotto la singola.
- **Banco**: `benchmark.py` è stato usato solo su tre cartelle 5090; le 3090 sono misurate con prompt corti, prompt in cache o temperatura 0,7.
- **CPU e link**: la nostra 3080 Ti sta su Oculink x4 (sonda 6,7 GB/s), la 2080 Ti in x16 terza generazione (13,1). Le 5090 hanno PCIe 5 x16
  e in parte AVX-512.
- `STRATA_ROUTE_PRIOR` non compare in nessun rapporto 3090/5090 (è spento di default su schede > 13 GiB): su questo siamo pari.

Il 130 della 5090 non si trova in nessun file: il valore più basso misurato con `benchmark.py` è 165 (IQ2_XS a 128K). Se il riferimento
dell'owner è un'altra fonte, va citata.

## 2. Dove va il tempo di una finestra di scrittura

### 2a. Cosa dicono i registri di oggi (M, `corse/Lbase_*`, `Lil_*`, `Lsm75*`, `Ltutte_a`)

- 256 token in 101-122 finestre: **2,1-2,5 token a finestra**; bozze accettate 65-68% (`--spec 4 --spec-min-p 0.5`).
- 2,22-2,90 s per 256 token → **20,9-27,6 ms a finestra** (D: 2606/105 = 24,8 ms in Lbase_a; 2374/102 = 23,3 in Lbase_b; 2220/106 = 20,9 in Ltutte_a).
- Riuso della cache esperti in scrittura: 94% alla prima richiesta, **97,2-99,0%** dalla seconda. Circa 200.000 ricerche per richiesta →
  2.200-5.600 voci mancate per richiesta → **20-55 per finestra, 0,4-1,1 per strato-finestra** (D).
- Esperti letti dalla scheda via PCIe: **8-177 per richiesta**, cioè sotto lo 0,1% delle ricerche e l'1-3% dei mancati. Il motivo è al §3b:
  solo gli strati 0-9 sono in memoria registrata. Il 97-99% dei mancati va alla CPU.
- Prompt: 862-948 / 1750-1886 / 2055-2230 t/s. Le letture KV da RAM (`--kv-resident 32768`) sono 22-200 MiB per richiesta, 96-99,6% dei
  blocchi in VRAM: non è un collo in scrittura.
- VRAM: 3080 Ti 10,7 GB al picco su 12,3; 2080 Ti 21,4 su 22,5. Avvisi del motore: «CUDA1: 252 MiB free ... LOW» e «only 598-756 MiB free at
  request start» (#2065, #2192). Nelle corse non c'è segno di paginazione (tempi stabili), ma il margine è sottile.
- `--pipeline-windows 2` contro il ciclo in serie, stessa build (RISULTATI.md, M): scrittura +4% a 4K e +2% a 32K, lettura −4%; con v0.2.9 la
  lettura recupera (1769).

### 2b. La struttura della finestra (D dal codice, M da `docs/PIPELINE2.md` §1, misure nsys del 13/10 con la 3060 come stadio 0)

Ogni finestra di verifica a T righe passa in serie: catena di bozze sulla **ultima** scheda (il drafter sta sulla 2080 Ti: il registro dice
«without the draft layer on the first card (STRATA_MTP_STAGE0=1 asks for it)») → stadio 0 (strati 0-19, 3080 Ti) → passaggio di ~51 KB × T
per RAM mappata (54 µs a T=2, M) → stadio 1 (strati 20-47 + testa, 2080 Ti) → verdetto. La catena doppia fa partire la finestra K+1 sullo
stadio 0 mentre lo stadio 1 verifica K, **solo** scommettendo che K sia accettata intera; se la scommessa regge la finestra è «speculativa»
e vale il massimo dei due stadi, altrimenti è «fresca» e vale la somma.

Misure di ottobre (3060 = stadio 0, 16 strati; 2080 Ti = stadio 1, 32 strati; ~25,9 ms medi a 70 t/s):

| voce della finestra fresca (72% delle finestre) | ms | si divide fra le schede? |
|---|---:|---|
| kernel che leggono pesi, stadio 0 (densi, hc, esperti in VRAM) | ~7,3 | sì |
| kernel che leggono pesi, stadio 1 (densi, hc, esperti in VRAM, testa) | ~10,8 | sì |
| **attese della GPU sui flag dell'host (piano 2,0 + righe CPU 1,8)** | ~3,8 | no: dipendono dal pool CPU |
| catena di bozze prima dello stadio 0 | 2,1 | no |
| QSA (top-k a un blocco per riga, attenzione in catena) | ~1,9 | poco: latenza |
| buchi fra i ~1400 nodi dei grafi + bolla del lancio | ~2,1 | no |
| passaggio fra le schede | 0,17 | — |
| **totale** | **28,3** | |

Finestra speculativa (28%): 19,8 ms = stadio 1 + catena forzata sulla stessa scheda. Entrambe le GPU in calcolo nello stesso istante: **24%
del tempo** (nsys). Dentro il tempo «in corsa» della 2080 Ti c'erano 1,8 ms di `wait_copy_i32` (attesa del piano) e 1,5 ms di
`copy_rows_from_mapped` (attesa delle righe CPU) per finestra: attese sulla CPU, non buchi della GPU.

### 2c. Oggi, con la 3080 Ti al posto della 3060 (S)

Lo stadio 0 ha 20 strati su una scheda con banda 2,5 volte quella della 3060: 10,1 ms × 20/16 × 360/912 ≈ 5 ms di kernel più ~2 di latenze
fisse → **~7 ms**; lo stadio 1 ha 4 strati in meno (28 contro 32): 15,9 × 28/32 ≈ **~14 ms**. Fresca ≈ 2,1 + 7 + 0,2 + 14 ≈ **23-24 ms**,
speculativa ≈ 14-16: media pesata ≈ 21-22, coerente coi 21-25 ms misurati. **Lo stadio 1 (la 2080 Ti, la scheda più lenta, con 28 strati,
testa, catena e verifica) è il tratto lungo**; la 3080 Ti è ferma per la catena e per tutto lo stadio 1 nelle finestre fresche.

### 2d. Cosa NON si deduce dai registri di stanotte

La ripartizione reale della finestra di oggi (attesa del piano, righe CPU, catena, buchi), la quota di finestre speculative, i µs per esperto
mancato del pool e l'attesa dell'adattamento. Il motore li stampa con `STRATA_DECODE_TIMING=1` (riga `strata decode timing: ... verify (GPU-reach
wait + per-layer host [plan actq jobs CPU] + stage) + commit/emit + draft; per layer-window: CPU experts, VRAM hits, PCIe; adapt wait`,
`generate.cpp:18878`) e con `STRATA_VERIFY_PROFILE=1` per il lato GPU (rallenta un po': solo per confrontare). Nessuna corsa di questa cartella
li ha. **È l'esperimento zero**: costa una corsa, non cambia il testo, e decide la discussione sulla CPU.

## 3. Il percorso CPU

### 3a. Come funziona uno strato (D, `expert_source.cpp:4905-5200`, `verify.cpp`)

1. Il router sulla scheda scrive gli id scelti in memoria mappata (il «campanello», `doorbell_publish`, `verify.cpp:2155-2170`).
2. Il thread host (`--host-core last`: processore logico 14) li legge e costruisce il **piano**: per ogni esperto distinto `kind` 0 = in VRAM
   (slot della cache), 1 = letto dalla scheda via PCIe dalla RAM registrata, −1 = CPU, −2 = saltato (`STRATA_ROUTE_TAIL_SKIP`). Il piano è
   pubblicato **prima** del lavoro CPU («the GPU's share, decided and published FIRST so the GPU starts while the CPU works», riga 4905).
3. La scheda aspetta il flag del piano (`wait_copy_i32_from_mapped`, 2291), calcola gli esperti residenti (percorso «R4 hit path», `generate.cpp:8002-8049`:
   gate/up/down dagli slot della cache con `expdec`), avvia la copia DMA degli eventuali esperti PCIe.
4. L'host quantizza le attivazioni per la CPU (5086-5094), raccoglie i blob dalla RAM e pubblica i lavori al pool; 7 lavoratori più l'host
   stesso («draining too») calcolano gli esperti mancati con i kernel AVX2 (il 5800X non ha AVX-512: riga del registro) e scrivono righe fp32
   in memoria registrata.
5. La scheda aspetta il flag delle righe, le copia (`copy_rows_from_mapped`) e combina.

Quindi **ogni strato con almeno un esperto fuori VRAM paga due andata-e-ritorno host↔scheda, e ogni strato senza mancati ne paga comunque uno**
(il piano), a meno che: (a) lo stadio sia **100% residente** → grafo «zero-doorbell» senza alcun flag (`verify.cpp:1161-1182`, impossibile qui:
servirebbero ~43 GiB di VRAM per gli esperti); (b) `STRATA_VERIFY_DEVICE_PLAN=1`: uno strato i cui esperti scelti sono tutti residenti pianifica
sul dispositivo (1193-1199; «exact, but neutral on 1-2 GPUs: off by default»). Con riuso al 98-99% la maggior parte degli strati-finestra non ha
mancati, quindi (b) qui ha più bacino che sulle macchine dove è stato misurato neutro. Da provare (esperimento 5).

«Token graph hit path: 15011 resident experts, decided on the device» (riga 8641) viene stampato sempre, ma il grafo a token (`session_capture_token`,
8644) parte solo con pacchetto non nativo e una sola GPU: **qui non è in uso**. Il numero è il conto delle coppie residenti; la tabella di
residenza viene caricata su entrambe le schede (8622-8630) e serve alle decisioni sul dispositivo del verificatore.

### 3b. Quanto pesa davvero con riuso al 99% (D + S)

- Mancati: 0,4-1,1 voci per strato-finestra (D); in una finestra fresca a T=2-3 molti strati hanno 0 mancati e alcuni ne hanno 2-4.
- Costo CPU per esperto: non misurato qui. Riferimenti: a monte il pool segna 42-45 µs per esperto mancato su una macchina HIP (`generate.cpp:2342`);
  Lamina dichiara 42,55 GB/s di banda RAM su 6 core, cioè ~55 µs per blob da 2,33 MB se limitato dalla banda. Sul 5800X con 7 lavoratori **S: 50-200 µs
  per esperto**, più il risveglio dei lavoratori (§3c) e il giro dei flag.
- Il PCIe come alternativa: 2,33 MB a 6,7 GB/s = **0,35 ms** sulla 3080 Ti, a 13,1 GB/s = **0,18 ms** sulla 2080 Ti (S): 2-6 volte la CPU per esperto.
  Per questo il motore stesso abbassa la quota PCIe quando il link è lento (`pcie_frac` 0,18 e 0,36 contro il default 0,55).
- **Perché il PCIe quasi non lavora**: sotto WDDM con più schede il motore registra al massimo 8 GiB dell'arena (`generate.cpp:6833-6846`: «pinning all
  of it into two contexts leaves WDDM refusing every later allocation - measured on the 5080 + 3090 rig»), cioè i primi 10 strati («10 slices pinned (7 GiB)»).
  La scheda legge via PCIe solo blob registrati (`expert_source.cpp:4992`: `d.src->pinned(...)`). Quindi: strati 0-9 → quota 0,18 dei mancati via PCIe;
  strati 10-19 e **tutti gli strati della 2080 Ti → 100% CPU**. La `pcie_frac 0.36` della 2080 Ti è inerte. I registri confermano (8-177 letture PCIe su
  2.200-5.600 mancati).

### 3c. Le variabili della nostra configurazione

| variabile | cosa fa (D) | giudizio |
|---|---|---|
| `--host-core last` | host sul processore logico 14 (ultimo core fisico), lavoratori su 0,2,…,12; l'host **lavora anche come lavoratore** («draining too», `host_works`). A monte: «a decode that swung ±6% became steady, 8% faster» su un altro split (`DETAILS.md:1348`) | giusto tenerlo. Con la catena doppia lo stesso host serve i campanelli di **due** stadi: mentre calcola un esperto (0,1-0,3 ms) non pubblica il piano dell'altra scheda. `--no-host-worker` esiste (`generate.cpp:1276`) ed è un braccio A/B legittimo |
| 7 lavoratori | «bounded by every physical core but the host's» (8 core fisici) | corretto; `--pool-workers` non serve |
| `STRATA_POOL_SPIN_US=100` | dopo 100 µs senza lavoro il lavoratore dorme su variabile di condizione (`pool.cpp:1016-1024`); il default è **20 ms** (`pool.hpp:282`) e il commento lo chiama «a test knob: a short spin makes the workers sleep constantly» | **sospetto principale a costo zero**. Con riuso 98-99% gli strati con lavoro CPU distano più di 100 µs: a ogni strato con mancati il `publish` fa `notify_all` (961-972) e i lavoratori si svegliano dal sonno (decine di µs su Windows, a volte molto di più). Motivo del 100 non trovato nei file letti (probabile: CPU libera per OktoCGControl) |
| `STRATA_RAM_CORE=1`, `STRATA_RAM_CORE_SLOTS_DEV1=5500` | nucleo fisso senza copia RAM: dev0 2918 slot su 5477, dev1 5500 su 9090; arena da 39,97 a 28,25 GiB; `riletti 0`, `fuori posto 0` in tutte le righe | fa il suo lavoro (RAM). Costo in velocità: la 2080 Ti ha solo 3590 slot che ruotano (`RAM_CORE.md` lo avvisa); con riuso 98-99% non sembra limitare, ma `scambi dell'adattamento` restano 320-727 a richiesta anche a regime |
| `STRATA_ROUTE_TAIL_SKIP=0` | di default 7 su CUDA (`generate.cpp:11653`): un mancato che ogni token della finestra ha al posto ≥7 su 10 non viene né copiato né calcolato; KL 0,003-0,006 (`DETAILS.md:1424`); +11,5% su una 5090 con riuso più basso | scelta di qualità dell'owner, si rispetta. Costo S: una minoranza dei mancati; con riuso 98-99% il guadagno rinunciato è nell'ordine di qualche punto, non di decine |
| «R4 hit path ON» | gli esperti residenti li calcola la scheda dagli slot | ok, è il percorso normale |

### 3d. Escludere la CPU: si può? cosa cambierebbe?

| via | con opzioni di oggi? | effetto atteso | testo |
|---|---|---|---|
| `--no-pool` | sì, ma è il «GPU-only floor»: spegne **anche** il percorso degli esperti residenti (`generate.cpp:8104-8105`: `hit_fn` nullo) | modello senza esperti: inutilizzabile | sbagliato |
| tutti i mancati via PCIe: `--pcie-frac 1` + `STRATA_ARENA_PIN_GIB=0` | sì sulla carta: `--pcie-frac` è una quota unica per entrambi gli stadi (`generate.cpp:5311`), `STRATA_ARENA_PIN_GIB=0` registra tutta l'arena (28 GiB col nucleo RAM) | S: più lento o pari (0,18-0,35 ms per esperto contro 0,05-0,2 della CPU; il tetto di 64 copie per strato, `staging_cap`); rischio WDDM misurato a monte (allocazioni rifiutate). Toglie il lavoro CPU ma **non** il giro del piano | cambia a livello di arrotondamento (la scheda arrotonda diversamente dalla CPU: stessa classe della parità di cache, `bench/results/2026-09-27-cache-parity`); nessun esperto saltato |
| saltare i mancati | solo per i posti ≥7 (`STRATA_ROUTE_TAIL_SKIP`); saltarli tutti non esiste | — | perdita di qualità vera: i mancati sono spesso ai primi posti del router |
| stadio 100% residente → grafo senza campanelli | solo se uno stadio tiene **tutti** i 512 esperti dei suoi strati: la 3080 Ti con 5477 slot regge ~10 strati, la 2080 Ti con 9090 ~17; l'altro stadio resterebbe con 31-38 strati e riuso in caduta | S: pari o peggio; non consigliato | uguale |
| pianificare sul dispositivo gli strati senza mancati | **`STRATA_VERIFY_DEVICE_PLAN=1`** | S: 0…+5% (toglie il giro del piano dove non serve; a monte neutro su 1-2 GPU con riuso più basso) | esatto per dichiarazione del codice |

Conclusione: la CPU non si esclude, e non conviene escluderla per il calcolo. Conviene **togliere i giri con l'host** (piano sul dispositivo, lavoratori
svegli, host libero di servire i campanelli). Lamina conferma dall'altro lato: anche con tre schede e il 87-98% degli esperti in VRAM tiene la CPU
per i mancati e azzera la lettura PCIe (`--pcie-frac 0` nelle sue configurazioni).

## 4. Prefetch e residenza

- **Chi sposta i top-k**: il livello adattivo (`--adapt-every 4`, `--adapt-swaps 96`; nelle prime finestre un intervallo più corto, `generate.cpp:4024-4032`).
  Ogni 4 finestre un thread («strata-adapt», `generate.cpp:17726-17739`, livello bloccante perché `--adapt-async` vale solo con una GPU) scambia fino a 96
  esperti più richiesti e mancati con i meno usati della coda, **per scheda e per i suoi strati**. Nei registri: 1781 scambi alla prima richiesta, 320-727
  dopo → 3-17 a finestra → 7-40 MB a finestra (S). I blob degli strati ≥10 **non sono registrati**, quindi le copie passano dalla memoria paginabile
  attraverso il buffer del driver (`generate.cpp:12463-12470`). È traffico sullo stesso link del passaggio e delle righe CPU; quanto fermi le finestre lo
  dice solo `adapt wait` del `DECODE_TIMING`.
- **Prestiti al prompt**: ogni lettura prende in prestito 2559 slot sulla 3080 Ti e 2026 sulla 2080 Ti («the prompt path borrows»); gli esperti sfrattati
  tornano con gli scambi dopo. È parte degli scambi visti sopra e il riuso al 94% della prima richiesta.
- **Fissi ed elastici**: elastica su dev0 nucleo 4422 + coda 1055 slot; con la catena doppia il nucleo elastico è scambiabile (`STRATA_ELASTIC_CORE_ADAPT`,
  patch 04); il nucleo RAM fissa 2918 (dev0) e 5500 (dev1) slot che non si scambiano mai.
- **Prefetch vero (prima che il router chieda)**: in Strata esiste solo lo spazio di scambio «Foresight» (`STRATA_FS_SLOTS`, dal router dello strato dopo),
  che a monte «cost more than the slots returned in every box measured. Left off» (`DETAILS.md:1030`), e il prefetch su disco di Linux (non ci riguarda).
  Lamina ha un prefetch dal router dello strato successivo con un bilancio di 12 MiB per strato, **solo su link da 20 GB/s in su**: con i nostri 6,7 e 13,1
  GB/s non partirebbe nemmeno lì.
- **Spostare i top-k sulla 2080 Ti**: nella divisione a strati ogni scheda tiene solo gli esperti dei **suoi** strati; la 2080 Ti non può prendere i mancati
  dello stadio 0. Farle tenere esperti di altri strati vuol dire il modo «scheda d'appoggio» (`--expert-cache-device1`), che spegne catena doppia, nucleo
  RAM ed elastica e con la 3060 ha perso 11-66% (RISULTATI.md). Con la 2080 Ti come appoggio la 3080 Ti farebbe tutti i 48 strati con 5477 slot per 24.576
  coppie: il riuso crollerebbe. **No**.
- **Doppioni**: nessuno per costruzione (strati disgiunti). Residenti 15.011 su 24.576 (61%): CUDA0 5477 slot per 10.240 coppie dei suoi strati (53%),
  CUDA1 9090 per 14.336 (63%). Il riuso al 98-99% dice che la coda dei non residenti è poco usata: **la cache è sfruttata bene**; lo spazio per crescere è
  la VRAM, non la politica.

## 5. Il motore e le due schede

- **Divisione 20/28**: la scheda più lenta (2080 Ti: 616 GB/s, Turing) fa 28 strati, testa, catena e verifica; la più veloce (3080 Ti: 912 GB/s) 20 strati
  su un link x4. La regola «la scheda più veloce per ultima» del motore vale per cache uguali; qui comanda la VRAM (22 contro 12 GB). Lo sweep 16-22 dà la
  20 come migliore in scrittura (99,0/96,9) con 22 a 95,1/95,7: nel rumore. In una finestra fresca le schede lavorano **in serie**; la catena doppia le
  sovrappone solo nelle finestre speculative (28% in ottobre). È il limite dell'architettura (parallelismo a stadi, una richiesta): `PIPELINE2.md` ha già
  stimato le alternative (esperti divisi fra le schede −0,5/−2 ms, tensori divisi −1/−3 ms con 4-6 settimane) e le ha scartate.
- **Tabella sm_86 non applicata** (`generate.cpp:3615-3627`: «when every visible card has that one compute capability»; a monte #3313). La configurazione
  mette a mano 4 dei 9 interruttori (`SIDE_MIXER=2`, `ATTN_DAILY=1`, `QSA_ROWS=1`, `B6_MMVQ_ROWS=1`) più `EXPDEC=1`. Mancano: `STRATA_GU_SWIGLU=1`,
  `STRATA_GR_UP75=1`, `STRATA_CPU_IQ_ALL_EXACT1=1` (quest'ultimo è il kernel CPU AVX2 esatto: proprio i nostri mancati sul 5800X), `STRATA_ADAPT_NOWAIT=1`
  e `STRATA_ADAPT_LAG=2`. I primi tre sono bit per bit e misurati a monte 0,8-1,8 punti ciascuno su 3060/A4000 (`nv_defaults.cpp:29-39`). Gli ultimi due
  con `--pipeline-windows` non agiscono («the batch paths, --pipeline-windows and the peer tier are not lagged», `generate.cpp:1822`; `adapt_nowait()` è
  letto solo nei cicli in serie, 18510 e 20355).
- **sm_75**: i kernel Turing sono spenti di default perché «nobody on the team has an sm_75 card» (`DETAILS.md:1071-1079`); `STRATA_SM75_PERF=1` li accende
  tutti (interleaved matvec `kIlRows_75`, modo 4 degli esperti, `FUSE_WAIT=2`, attenzione v3, tensor core del prompt…), dichiarati bit per bit. Misura di
  stanotte (M): da solo lettura +2/+6/+8% a 4K/32K/128K e scrittura pari o sotto (95,1/91,9/99,1 e 95,5/92,5/95,6); **con `STRATA_EXP_MODE=8`** scrittura
  104,1/103,0/103,6 e 110,4/100,3/104,9 contro le basi 98,2/91,6/96,6 e 107,8/97,7/95,8. Il modo 8 vale per tutte le schede (`exp_mode()`, 6147-6150): la
  3080 Ti lo prende al posto del suo layout CUDA. Non si sa chi guadagna: serve `STRATA_EXP_MODE=8` **senza** `SM75_PERF` (esperimento 1b), e un
  interruttore per scheda costerebbe ~10 righe.
- **`STRATA_MMVQ_IL=0`**: spegne il matvec interlacciato solo sulla 3080 Ti (tabella condivisa sm_86); sulla 2080 Ti è spento comunque senza `SM75_PERF`.
  Bracci `Lil` (M): 100,2/98,4/99,9 e 103,0/96,3/99,7 contro le basi → +1,7% medio, dentro il rumore; bit per bit per documentazione. Motivo dello 0 non
  trovato nei file letti: non c'è ragione documentata di tenerlo.
- **`STRATA_MTP_SHARED_BRANCH=0`**: l'esperto condiviso del drafter gira sullo stesso stream invece che su un ramo laterale (`mtp.cpp:1126-1142`); a monte è
  acceso di default su CUDA; stessi kernel, quindi stessi bit (D). La catena è sul percorso critico delle finestre fresche (2,1 ms in ottobre). Motivo dello
  0 non documentato; forse un problema Turing del passato.
- **`STRATA_MTP_STAGE0=1`**: drafter sulla 3080 Ti (837 MiB → ~560 slot in meno su 5477, −10% di riuso potenziale sullo stadio 0); la catena potrebbe
  partire appena finisce lo stadio 0. Provato in ottobre sulla 3060 senza guadagno (`BISEZIONE.md`, mtpst0); sulla 3080 Ti non provato. Incerto.
- Interruttori già accesi e giusti: `EXPDEC=1`, `SIDE_MIXER=2`, `ATTN_DAILY=1`, `QSA_ROWS=1`, `B6_MMVQ_ROWS=1`, `HC16_SM75=1` (prompt −11,6% di tempo a 131K
  in ottobre), `SA_BET/SA_CHAIN` (struct-a del fork), `STRATA_VRAM_FREE=device`.

## 6. Classifica degli esperimenti

Regole: ogni braccio a coppie alternate con la base, almeno 2 coppie; banco completo 4K/32K/128K. «Testo» = se cambia il testo generato a parità di stato
(il banco della comunità **non** è a finestre forzate: Lbase_a e Lbase_b danno 8 testi diversi su 9, quindi la parità bit per bit si verifica solo col
banco forzato `STRATA_FORCE_IDS`/`STRATA_FORCE_WINDOWS`, come in `RAM_CORE.md` §Come si misura).

| # | esperimento | variabili / comando | guadagno atteso | base del numero | costo | testo | compila |
|---|---|---|---|---|---|---|---|
| 0 | **misurare la finestra** | `STRATA_DECODE_TIMING=1` (una corsa a parte con `STRATA_VERIFY_PROFILE=1`) | 0, ma decide tutto il resto | — | 2 corse | uguale | no |
| 1a | kernel Turing + modo 8 | `STRATA_SM75_PERF=1 STRATA_EXP_MODE=8` (già in coda: `Lsm75m8_b`, `Ltutte_b`) | scrittura **+5-8%**, lettura **+6-8%** a 32K/128K | **M**, 2 bracci contro 2 basi | 0 | dichiarato bit per bit a monte (#2197); non verificato qui | no |
| 1b | separare le due leve | `STRATA_EXP_MODE=8` da solo | ? (dice se guadagna la 3080 Ti o la 2080 Ti) | — | 2 corse | come 1a | no |
| 2 | lavoratori svegli | togliere `STRATA_POOL_SPIN_US=100` (default 20 ms) | **+1-5%** | **S** (risveglio da variabile di condizione a ogni strato con mancati; `pool.hpp:276-282`) | 0; CPU al 100% su 7 core **durante** la generazione (fra una richiesta e l'altra dormono comunque dopo 20 ms): da pesare con OktoCGControl | uguale | no |
| 3 | tabella sm_86 a mano | `STRATA_GU_SWIGLU=1 STRATA_GR_UP75=1 STRATA_CPU_IQ_ALL_EXACT1=1` | **+1-3%** | **S** da misure a monte (0,8-1,8 punti ciascuno, `nv_defaults.cpp`) | 0 | bit per bit (gate di identità a monte) | no |
| 4 | matvec interlacciato | togliere `STRATA_MMVQ_IL=0` | +0-2% | **M**: +1,7% medio, nel rumore | 0 | bit per bit (doc) | no |
| 5 | piano sul dispositivo | `STRATA_VERIFY_DEVICE_PLAN=1` (controllare la riga di avvio) | **0…+5%** | **S**: toglie il giro host sugli strati senza mancati (2,0 ms/finestra in ottobre), a monte neutro su macchine con riuso più basso | 0 | esatto (dichiarazione nel codice) | no |
| 6 | ramo dell'esperto condiviso | togliere `STRATA_MTP_SHARED_BRANCH=0` | +0-2% | **S** (catena 2,1 ms sul percorso critico) | 0; rischio: motivo dello 0 ignoto | stessi kernel → stessi bit (D) | no |
| 7 | host che non calcola | `--no-host-worker` | **±3%** | **S** (meno 1/8 di CPU, host più pronto per due stadi) | 0 | uguale | no |
| 8 | meno scambi | `--adapt-swaps 32` oppure `--adapt-every 8` | **±2%** | **S** (320-727 scambi a richiesta da memoria paginabile; riuso già al 98-99%) | 0 | cambia **quali** esperti sono residenti → testo può cambiare, qualità uguale | no |
| 9 | drafter sulla 3080 Ti | `STRATA_MTP_STAGE0=1` | **±** (incerto) | ottobre sulla 3060: nessun guadagno; −560 slot sullo stadio 0 | 0 | uguale in principio | no |
| 10 | mancati via PCIe (diagnostico) | `STRATA_ARENA_PIN_GIB=0` + `--pcie-frac 0.5` o `1` | **S: pari o peggio**; serve solo a chiudere l'ipotesi «togliere la CPU» | 0,18-0,35 ms per esperto contro 0,05-0,2 CPU; rischio WDDM (`generate.cpp:6833-6837`) | 1-2 corse; può far fallire allocazioni | arrotondamento | no |
| 11 | codice: `STRATA_EXP_MODE` per scheda | ~10 righe in `exp_mode()` (`iq_kernels.cu:6147`) | abilita 1b in modo pulito | — | mezz'ora + build | bit per bit | **sì** |
| 12 | codice: scambi dell'adattamento da buffer registrato sulla divisione | portare il «bounce» registrato di `--adapt-async` al livello bloccante | S: +0-3% se `adapt wait` risulta alto al punto 0 | — | giorni | uguale | **sì** |
| — | non proposti | `presence_penalty=0`, `STRATA_ROUTE_PRIOR`, `STRATA_ROUTE_TAIL_SKIP=7` | +4%, +15-37% su 12 GB, +11,5% su 5090 (a monte) | scelte di qualità dell'owner | | cambiano le risposte | |

Ordine consigliato: 0 → (1a già in corso, aggiungere 1b) → 2+3+4 insieme in un braccio «pulizia», poi uno alla volta solo se il braccio rende → 5 → 6/7/8.
I bracci 2-6 sono tutti a costo zero e, salvo 8, non toccano quali esperti girano.

Cosa portare da Lamina: niente di diretto (richiede sm_80+, usa livelli di esperti al posto della divisione a strati, e il suo prefetch non parte sotto
20 GB/s). L'idea utile è di metodo: gli stadi d'appoggio non girano in attesa attiva, e l'host non viene messo a calcolare esperti (nostro #7).

## 7. Cosa resta incerto

- La ripartizione della finestra di oggi (fino al punto 0 è la fotografia di ottobre con una scheda diversa come stadio 0).
- Quale scheda guadagna con `STRATA_EXP_MODE=8` (1b), e se i kernel Turing siano davvero bit per bit **qui** (banco forzato).
- Perché la Daily ha `STRATA_POOL_SPIN_US=100`, `STRATA_MMVQ_IL=0`, `STRATA_MTP_SHARED_BRANCH=0`: nessun file letto lo spiega; se la ragione fosse un
  blocco Turing passato, i bracci 2/4/6 lo rivelerebbero subito.
- Il margine di VRAM: 252 MiB liberi sulla 2080 Ti e 600-750 sulla 3080 Ti a inizio richiesta sono sotto le soglie di avviso del motore; non ha dato
  problemi nelle corse ma qualunque leva che allarga buffer (`DEVICE_PLAN`, `MTP_STAGE0`) va letta anche su questo.
- I numeri 3090/5090 dell'owner: nessuna fonte nel repo li produce; se vengono da altrove, va confrontata quantizzazione e versione.

## Fonti lette

Codice: `src/program/generate.cpp` (1812-1824, 2300-2350, 3615-3627, 4024-4032, 4410-4458, 5199-5220, 6833-6846, 6993-7020, 8002-8160, 8600-8650,
11653-11700, 12425-12610, 17341-17400, 17726-17739, 18496-18530, 18855-18905), `src/core/expert_source.cpp` (4836-5200), `src/core/verify.cpp` (300-450,
1160-1224, 2080-2300, 4963-5017), `src/core/nv_defaults.cpp`, `src/core/mtp.cpp` (1120-1145), `src/kernels/cpu/pool.cpp` (730-830, 961-1035, 1107-1150),
`include/strata/kernels/cpu/pool.hpp` (13-30, 276-285, 338-350), `src/kernels/cuda/iq_kernels.cu` (6146-6200). Documenti: `HOW_IT_WORKS.md`, `MULTI_GPU.md`,
`RAM_CORE.md`, `ELASTIC_CACHE.md`, `DISJOINT_EXPERT_CACHE.md`, `KV_PREFETCH.md`, `UPSYNC_029.md`, `MMVQ_IL_TABLE.md`, `PIPELINE2.md` (§0-2, §8-9),
`DETAILS.md` (296-331, 1000-1079, 1160-1240, 1340-1440), `COMMUNITY_BENCHMARKS.md`, `BENCHMARK_PROTOCOL.md`, 20 cartelle di `bench/results`. Corse:
`corse/Lbase_{a,b}`, `Lil_{a,b}`, `Lsm75_{a,b}`, `Lsm75m8_a`, `Ltutte_a`, `u20_a`, `n20_a` (`engine.log`, `summary.json`, `config.json`, `schede.csv`,
`tokens-*-raw.json`), `RISULTATI.md`, `coda_notte.py`, `20261019_banco_comunita/BISEZIONE.md`, `20261026_leve/{LEVE_026,ESITO_20261027}.md`.
A monte (`gh`, sola lettura): Niko1221/Strata #2197, #4962, #4826, #4584, #4841, #4778, #3313; eddoursul/Lamina `README`, `docs/COMPARISON.md`,
`docs/HOW_IT_WORKS.md` (ultimo commit 1/11/2026, base Strata 0.1.43.1).
