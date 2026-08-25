# LEDGER 25 AGOSTO — campagna «20 t/s sul lungo»

Sessione di regia nuova (testimone dalla sessione Fable del 24-25/8, chiusa per token).
Direttiva dell'utente all'apertura: **«avanti verso i 20 t/s sul lungo dando priorità a leve
grandi»**. La coda ereditata (sonda `copy_experts`, leva D1, SLOT 473) è stata **riordinata di
conseguenza**: nessuna delle tre ha l'ordine di grandezza richiesto. Cronaca dei sei turni
notturni, tutti a costo macchina quasi zero.

---

## 0. IL BERSAGLIO, NOMINATO CON PRECISIONE

Il «lungo» non è un banco solo, e le tre ancore **non sono confrontabili**:

| banco | prompt | completion | ms/token | t/s | mean_len | p1 |
|---|---:|---:|---:|---:|---:|---:|
| corto «B1200» | 68 | 1200 | 59,97 | 16,68 | 2,80 | 0,90281 |
| lungo 33k | 33.344 | 256 | 82,223 | 12,162 | 2,07 | — |
| lungo 102k | 101.691 | 256 | 86,234 | 11,596 | 2,14 | 0,74725 |
| **SOTA lungo** | 101.691 | **8192** | **75,44** | **13,26** | 3,06-3,18 | 0,90229 |

Le statistiche a completion 256 sono una **finestra precoce**, non l'aggregato stazionario: sullo
STESSO prompt `mean_len` passa da 2,14 a 3,18 e p1 da 0,747 a 0,911. Il p1 0,747 dell'ancora e35
è la firma nota del campione-di-segmento, non una regressione.

**Obiettivo 20 t/s = 50,0 ms/token.** Dalla SOTA lungo: **−33,7%**.

---

## 1. PREFLIGHT (esecutore, 01:24) — due reperti

**Macchina pulita**: zero processi llama, VRAM 471/12.288 MiB, RAM 85,8/95,9 GB, porte libere,
C: 46 GB / D: 113 GB liberi. Binario canonico confermato: `llama.dll` =
`ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035`, in
`D:\llama-subtract\build\bin` (la variante «resto64_guardia», non «vramfaseresto»).

**Reperto 1 — la voce 3 della coda era già eseguita.** `LLAMA_CACHE_ESPERTI_SLOT=473` è **già** nel
`.bat` di produzione dell'utente (23/8 18:48) e l'ultimo banco lungo ha girato a 473 slot
(3194 MiB in VRAM) **senza OOM**. Il resto-64 era davvero il colpevole del 23/8. Fascicolo chiuso
senza spendere una corsa.

**Reperto 2 — trappola armata nel runner.** `run_porto_hot.ps1` aveva `-ServerPath` di default su
`D:\llama-overlap\build\bin\llama-server.exe`: binario **fermo al 16/8**, precedente a
chirurgo14/15, **privo della feature `LLAMA_VRAM_A_FASI`**. Chiunque avesse lanciato un braccio
senza passare il percorso a mano avrebbe misurato in silenzio il binario sbagliato — stessa classe
d'incidente di `SFRATTO_PAR` del 12/8. **Bonificato**: default ripuntato sul canonico + guardia che
stampa `IDENTITA-DLL: <sha>` a ogni avvio (avvisa, non blocca, per non impedire le build nuove).

**Reperto 3 — il cancello d'identità del runbook è insufficiente.** La riga `cache-esperti: …`
(«unica identità di configurazione valida», §4.1) **non cattura** `LLAMA_VRAM_A_FASI*`,
`LLAMA_DSV4_INDEXER_FUSO`, `LLAMA_DSV4_PREFILL_*`, `LLAMA_MMQ_X_IDS`, `GGML_SCHED_OFFLOAD_PACCHETTI`,
`LLAMA_CKPT_CRONO`: due bracci possono avere quella riga identica carattere per carattere e
differire su leve decisive. Tacca per `il-manifesto-non-e-la-configurazione`.

---

## 2. FRONTE SPECULAZIONE — **CHIUSO PER ARITMETICA**

```
C_round = ms/token × mean_len = 73,96 × 3,18 = 235,2 ms   (punto SOTA lungo)
tetto assoluto a nmax=3 = bozza PERFETTA = mean_len 4,00
  → 235,2 / 4,00 = 58,8 ms/token = 17,0 t/s   CONTRO obiettivo 50,0 ms = 20 t/s
```

**Un drafter perfetto, a costo zero, non arriva all'obiettivo.** Tetto duro della famiglia:
`block_size = 5` cotto nel GGUF (`speculative.cpp:975-981`); anche nmax=5 con accettazione 80% su
cinque posizioni (contro sopravvivenza misurata a pos-5 di **0,32**) esce a 19,5 t/s.

I tre limitatori sono tutti già alla parete: il **criterio** accetta il 91% di ciò che riceve ed è
dimostrabilmente ottimo (argmax, `sampling.cpp:638`, TOPK=1 già attivo); il **cancello** ha un
massimo interno a conf 0,70 (0,60 → mean_len 3,16 e −3,2% t/s; 0,80 peggiore); la **politica** ha un
massimo netto a nmax=3.

**Perché nmax=4 peggiora — meccanismo, non sfortuna** [C]: in DSpark il blocco è denoisato
**congiuntamente**, tutte le posizioni escono da un unico `llama_decode` non-causale
(`speculative.cpp:1178-1191`, `llama_set_causal_attn(ctx_dft,false)` a :1019). Alzare nmax non
aggiunge token allo stesso blocco: **cambia il problema di denoising**. Per questo mean_len SCENDE
(2,80 → 2,43). E il drafter **non scala con nmax** (un solo decode): il costo è la **riga di
verifica sul MoE**, la cui unione di esperti sfonda la cache (3 posizioni ≈ 535-580 esperti, colpi
57,5% → 22,2%).

**La leva nmax paga MENO sul lungo, non di più** (intuizione opposta falsificata): passo nmax2→3
rende **+1,34% sul lungo** contro **+4,01% sul corto**. Sul lungo scalano entrambi i termini e il
rapporto c_riga/C_round resta ~5% su tutti i banchi (c_riga ≈ 10,5 ms).

**Verifica ad albero: morta**, e non per mancanza di codice — la maschera si costruisce solo da
posizione (`llama-graph.cpp:443`), quindi rami fratelli alla stessa posizione si vedrebbero; e la
KV DSV4 **non sa potare rami interlacciati** (`seq_rm` rifiuta ogni rimozione parziale, :1674-1682;
esiste solo `seq_rm_tail` su una coda). In più l'economia è sbagliata: un albero non aggiunge
forward, aggiunge **righe**, ed è la riga la risorsa scarsa.

**Due caselle restano vuote** (solo-env, ~20 min, valgono come chiusura di fascicolo, non come
strada): `nmax=4 × conf=0,70` sul lungo — mai esistita, perché nmax4 fu misurato a conf 0,80 mentre
sul lungo l'ottimo è 0,70 — con **go/no-go pre-registrato: paga solo se mean_len > 3,34**; e la
scala `CONF_PRENORM` mai letta.

**Confound mai controllato nei tre bracci nmax5**: `LLAMA_KV_ROLLBACK_MARGINE=4` di difetto
(`llama-kv-cache-dsv4.cpp:73`) e `seq_rm_tail` rifiuta code sopra il margine (:1638-1641); con
`n_rollback = n_draft+1−accepted`, nmax=5 può chiedere una coda di 5 > 4 → **ripristino del
checkpoint e rigioco di un forward intero** proprio nei round che già rendono meno.

**Tre correzioni di misura** registrate in memoria: `mean_len` **include il token gratis** del
bersaglio (`= 1 + accepted/steps`, `server-context.cpp:932`) quindi 2,80 sono **1,80 token di
bozza**; sul lungo il drafter è `draft-dspark` **ma il log stampa `draft_dflash`** (struct
condivisa); i cronometri del drafter **sotto-contano di ~6×** (`process()` senza cronometro:
18,7 ms contabilizzati contro 113,4 reali).

---

## 3. BUDGET DEL LUNGO — **il costo è ADDITIVO, e l'81,7% è PAVIMENTO**

```
pavimento di regime   61,6 ms/token   81,7%   (intercetta 188,71 ms/fwd ÷ mean_len 3,18)
tassa del contesto    13,8 ms/token   18,3%   (0,431 ms/fwd/1000ctx × 101,691 ÷ 3,18)
                      ─────────────
totale                75,4                     chiude allo 0,1% col misurato
```

Controprova indipendente: corto ri-ancorato **61,84 ms/token**; 61,84 + 13,8 = **75,6 contro 75,44**
= 0,2%. La tassa è già scesa da 32,5 a 13,8 ms/token (−58%) grazie a G1 + conf 0,70.

> **Azzerando l'INTERA tassa del contesto si arriva a 16,2 t/s, non a 20.** I 20 richiedono che
> scenda il **pavimento**, cioè che il banco **corto** passi da 16,17 a 23-26 t/s.

Ogni leva che attacca solo la pendenza (D1, bolle graph-gated, kv-ring, argsort, indexer) è
limitata per costruzione al 18,3% del budget. **Somma onesta di tutte le leve vive: −24,5% → 17,5
t/s.** La proiezione già scritta in `COMPOSIZIONE_PIANO.md:496-511` concordava e nessuno l'aveva
ripescata: «il 20 sul lungo è raggiungibile solo nello scenario ottimista»; «il 30-corto NON è
raggiungibile per composizione in nessuno scenario».

**Quote della parete** (nsys e35 @102k — solo proporzioni: le voci non sommano alla parete, e il
normalizzatore assoluto è fuori di 1,7-1,8×): **bolle 39,3%** · trasporto cache 20,4% · GEMM densi
14,2% · MoE mascherate 10,5% · norm/rope/concat 4,8% · attenzione 3,2% · kv-ring 3,2% · argsort
2,2% · indexer 1,9%. **~44% è calcolo vero, non aggredibile.**

*Correzione di regime*: la tabella e35 è misurata a completion **256** (mean_len 2,14), il banco che
conta è a 8192 (mean_len 3,06) — 184,5 contro 230,8 ms/forward. Le voci che **scalano** col contesto
sono quindi **sotto**-rappresentate, quelle piatte sovrastimate. L'errore ha direzione nota e gioca
a favore delle leve sulla tassa.

---

## 4. ANATOMIA DEL SORGENTE — **e39 FALSIFICATO**

Il turno e39 (24/8) aveva nominato come emittente delle copie orfane la lambda `copy_experts` del
fallback dello scheduler. **L'aritmetica lo uccide**: `copy_experts` copia interi esperti e il suo
minimo emissibile è **2.162.688 B**; le taglie osservate sono 65.536 e 98.304, cioè lo 0,9% di un
esperto. E in tutto il modello **non esiste un tensore WEIGHTS con `nb[2]=16384`** (16384 non è
divisibile per nessuna row-size: 1056, 672, 1344, 4352).

**16384 = n_embd(4096) × sizeof(float) = una riga di stato nascosto F32.** Le taglie si spiegano
riga per riga dalle forme del grafo:

| taglia | = | tensore | sito |
|---:|---|---|---|
| **65536** | 4096 × 2 × 4B × **2 token** | `esperti_cpu`, `k_cpu=2` | `llama-graph.cpp:1978` (H2D) |
| **98304** | 4096 × 2 × 4B × **3 token** | idem | idem |
| 16384·n_tok | n_embd × 1 × n_tok × 4B | `cur` reshaped | `:1925` (D2H) |
| **2072** | 6·4 + 2·1024 | `ggml_nbytes` della vista con passo `[6,3]` dell'argsort | = **`ids`** |

Il 2072 chiude il caso al bit. E si spiega finalmente **perché le taglie non scalano ma il mix sì**:
`LLAMA_OVERLAP_BATCH_MAX=3` ammette il ramo CPU solo a `n_tokens ≤ 3`, quindi il mix 77/23 → 70/30
fra 33k e 102k **è la distribuzione delle lunghezze di accettazione speculativa**.

**La catena vera**: `LLAMA_OVERLAP_K=2` crea il ramo CPU per strato (`llama-graph.cpp:1846`) →
`llama-context.cpp:1760-1767` **pinna** i nodi `*_overlap_cpu` sul backend CPU (pin ESPLICITO, non
deduzione) → `ggml-backend.cpp:1640` crea `input_cpy` → `:2301` chiama `cpy_tensor_async` →
**`ggml-cuda.cu:3820-3826` RIFIUTA sempre** ogni confine non device-device → ripiego **strutturale,
non condizionale** (`:2302-2308`): due `cudaStreamSynchronize` + copia host-sincrona che dentro ne
fa una terza. **Tre sincronizzazioni per ingresso, per strato, per forward** ≈ 129 copie/token dal
solo bersaglio (≈277 con la bozza).

`LLAMA_MAPPED_IBRIDO=1` è **condizione necessaria del ramo CPU, non l'emittente**. E `copy_experts`
è **viva in prefill e strutturalmente morta in decode** (serve `op_offload` con batch ≥ 32,
`ggml-cuda.cu:7075-7078`; in decode il batch è 3-6): e39 misurava una finestra di decode.

**Nessuna duplicazione cache ↔ scheduler**, e la disgiunzione è **strutturale**: la cache registra
un peso solo se il buft è il mappato (`ggml-cuda.cu:1570`) e muove i byte con `kern_copia`, un
kernel device-side; lo scheduler non può mai toccare un mappato (buft mappato e CUDA condividono
`get_name`, :1520 → `supports_buft` vero → `:1640` non crea l'`input_cpy`). Le due condizioni sono
l'una la negazione dell'altra. Byte del fallback = attivazioni (32-96 KiB/strato); byte della cache
= pesi (2,06-2,62 MiB/esperto). **Nessun byte in comune.**

*Geometria verificata*: n_embd 4096, 43 strati, 256 esperti, 6 usati, n_ff_exp 2048, gate/up
IQ2_XXS + down Q2_K → **esperto = 7.077.888 B = 6,75 MiB**; 43·256·6,75 MiB = 74.304 MiB =
esattamente il `CUDA0_Mapped model buffer size` del log.

---

## 5. IL TRASPORTO È **TEMPO DI BUS** — e il «margine DMA 6×» è un artefatto

Il piano di attacco al trasporto poggiava su un margine di 6× a favore del motore DMA. **Non
esiste**, e il segno è invertito. Tre falsificazioni indipendenti:

1. **Denominatori diversi**: 0,52 ms/esperto (DMA) è corretto; **0,94 ms non è per esperto, è per
   LANCIO** (`fork cronometro → durata media della copia=0.941 ms`, LEDGER_17:1451) e un lancio
   porta più esperti (`kern_fj_copia` cicla sulla lista, `cache-esperti.cu:6329`).
2. **La citazione diceva altro**: LEDGER_17:3427/:3500 dice che il calo −0,47% del fantasma sta «un
   margine di circa 6× **sotto la soglia di rumore** del 3%».
3. Comunque **0,94/0,52 = 1,81**, mai 6.

**Misura vera, dai `.sqlite` già su disco**: le durate di `kern_fj_copia` sono **quantizzate**
(armoniche a 280-350, 560-640, 840-940, 1100-1220 µs), quanto fondamentale **285,7 µs/esperto**, e
c'è un **vuoto assoluto fra 10 e 250 µs** — nessuna seconda famiglia veloce, quindi **nessun esperto
è servito da VRAM**: passano tutti dal PCIe allo stesso prezzo.

```
6,75 MiB / 285,7 µs = 23,07 GiB/s   (limite INFERIORE: nsys gonfia del 6-7%)
motore DMA sullo stesso traffico     =  9,24 GiB/s (23.662 memcpy, 481,4 MiB)
⇒ kernel 0,29-0,32 ms/esperto CONTRO 0,52 del DMA: IL KERNEL È 1,6-1,8× PIÙ VELOCE
```

Spostare i byte sul DMA **perderebbe** 13,4% (best case) o 23,1% (banda osservata), prima ancora di
contare i sync di readback e le **tre** memcpy per esperto (gate/up/down separati) che servirebbero
a domanda — proprio il regime di taglia piccola dove il DMA fa 9,24 e non 13.

**Cosa aveva visto davvero il `carico_fantasma`**: non che il DMA sia economico per byte, ma che **il
bus è scarico** (duty ~33% → ~62% costa 0,53%). Il margine è **duty-cycle**, e raccoglierlo richiede
**slack temporale** = anticipare = prefetch, morto per capienza tre volte. **La domanda non ha
slack**: `kern_decidi` sceglie e la MMVQ consuma nello stesso strato, microsecondi dopo.

**Perché `kern_copia` costa: è il bus, non l'occupancy.** Copia grid-stride a `int4`, griglia 4×SM =
112 blocchi × 256 fili, ~450 KiB di letture in volo (`cache-esperti.cu:5528-5570`); la sorgente è
memoria host mappata, **ogni load è una lettura PCIe**. Gli SM occupati sono **in stallo sul bus**.
Ecco perché lo sweep del 17/8 scende (8→4 blocchi −6,04%, 4→2 −25,32%): ridurre la griglia
**de-satura il bus**. La griglia è già all'ottimo. Aritmetica di chiusura: 15.504 buchi × 6,75 MiB =
102,2 GiB su 256 token = **409 MiB/token**, a 23 GiB/s = 17,3 ms/token = **20,1%** (quadra col
20,4%).

`kern_copia` è **vuoto al 98%** (10.352 lanci su 10.557 sotto 10 µs): parte sempre, anche a lista
vuota, per costruzione (`:5737-5740`). Il trasporto vero è tutto in `kern_fj_copia`.

> **Azzerare COMPLETAMENTE il trasporto esperti — tutti i 102,2 GiB, gratis — dà 14,5 t/s.**
> Il bersaglio **non è nel trasporto**. E non è nella speculazione (§2: bozza perfetta = 17,0 t/s).

E «meno byte» è quasi esaurito: gli esperti sono già a **IQ2_XXS, 2,0625 bpw**.

---

## 6. DOVE È IL BERSAGLIO — le BOLLE, e due analisi vi convergono da lati opposti

Il fallback dello scheduler vale lo **0,46% del volume** di trasporto (481,4 MiB contro 102,2 GiB):
eliminarlo per i byte risparmierebbe lo 0,09% del token. **Non è un problema di byte: è un problema
di SYNC** — e le **bolle valgono 45,3 ms/fwd = 39,3% della parete** contro i 23,5 del trasporto,
con il 98,8-98,9% ai **confini fra lanci** e ~76% host-bound.

**La leva R1** (§4) e questa conclusione indicano **lo stesso sito per ragioni diverse**:
l'anatomista ci arriva dai byte delle attivazioni, il progettista dai sync. Convergenza
indipendente.

### R1 — `LLAMA_SCHED_CPU_BUFT_MAPPED` (in costruzione, chirurgo 16)

`llama-context.cpp:493-500`: dare al backend CPU un buffer di calcolo sul buft **mappato** invece
che su `CUDA_Host` pinnata. A cascata: `supports_buft` vero → **`ggml-backend.cpp:1640` non crea
l'`input_cpy`** → spariscono H2D, D2H e le tre sincronizzazioni per ingresso, **all'origine**.
- **Bersaglio**: 100% dei byte dei siti #2/#3 + gran parte della massa `cudaStreamSynchronize`
  (~19% della parete, misurata **quasi flat** col contesto = pavimento puro).
- **Rischi**: richiede IBRIDO=1 (altrimenti il backend CPU rifiuta il proprio buffer di calcolo,
  `ggml-cpu.cpp:493-494`); la pinnata è risorsa scarsa; la GPU leggerebbe quelle attivazioni via
  PCIe invece di riceverle in blocco.
- **Cancello**: `n_splits` invariato + memcpy al confine = 0 + **SHA identico** (cambia il
  trasporto, non l'aritmetica).

Nello stesso build, la **sonda `LLAMA_SCHED_SONDA_COPIE`** (4 bucket n+byte + istogramma delle
taglie) misura il bersaglio prima di colpirlo e discrimina definitivamente e39 dalla lettura nuova.

---

## 7. ALTRE AZIONI DEL TURNO

**Salvataggio dei lanciatori (commit `5641e71`).** Tutti i numeri lunghi del 24/8 — 73,79, 73,96,
75,44 e l'intera anatomia e35→e39 — erano riproducibili **solo** da script che vivevano in
`%LOCALAPPDATA%\Temp\claude\…\scratchpad\`, una directory di sessione. **79 file** portati in doppia
copia (`docs/porto/lanciatori/` e `D:\ds4_work\llama_run\lanciatori_salvati_20260825\`). Stessa
classe d'incidente già occorsa al turno 23, stavolta su 79 file invece che uno. Il lanciatore reale
del banco lungo è **`p1b_conf.ps1`** (NON `run_p1_nudo.ps1`; `sota100k_ctx150k.ps1` è un antenato
del 14/8, con `--spec-draft-conf-min 0.8` cablato ma non più in uso — il «quarto hardcode» è
**ritirato**).

**Ancora fresca `r40_ancora102k_20260825`**: lanciata 01:49:39 (l'ultima ancora aveva 2h44m e stava
per superare la soglia di 3 ore del runbook §8.5).

**Anti-pattern ricorso e corretto sul posto**: l'esecutore ha chiuso un turno con «attendo la
notifica». Un agente fermo non riparte da solo — memoria `consegna-incrociata-con-agente-fermo`,
tre ore perse il 24/8. Risvegliato con ordine di **polling attivo dentro il turno**, mai
sospensione.

---

## 7-bis. CHIRURGO 16 — BINARIO PRONTO (sonda + R1 in un solo build)

**Build riuscita alle 01:55:26.** Backup del pre in `D:\llama-subtract\build\bin\backup_pre_chirurgo16\`
(7 DLL; i due SHA pre coincidono con i canonici dichiarati).

| DLL | pre | post |
|---|---|---|
| `llama.dll` | `ECAEA60B…9C035` | **`12BF6E664EB77A15B6F4D0FF8C9A02E6C15C2414398D395A7796B0BF5F1B87EB`** |
| `ggml-base.dll` | `BAD51D94…D0C65` | **`D52DA12E652EE6324213A5376334FB098B1C4CF6A73689B6DE12A40B53501546`** |
| `ggml-cuda.dll` | `6EF5B781…C68B52` | invariata (nessun simbolo cambiato) |

```bat
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
"C:\Program Files\...\CMake\bin\cmake.exe" --build D:\llama-subtract\build --target ggml-base llama
```

**Maniglie di grep**: `sched-sonda-copie` (4 secchi n+byte + istogramma taglie + censimento
`grafi/split/ingressi`) e `sched-cpu-buft` (una riga fra ATTIVO / SPENTO / quattro varianti di
RIFIUTATO). Su **stderr**, a `sched_free`, perché il callback del server filtra gli INFO di ggml.
**Con entrambe le leve spente il log è identico a oggi.**

Il cancello della leva non è la `getenv` ma una domanda al backend: `ggml_backend_sched_new`
(`ggml-backend.cpp:2701`) fa `GGML_ASSERT(ggml_backend_supports_buft(...))` — con buft mappato e
ibrido spento **è un abort, non un ripiego** — quindi la leva pone al backend CPU la stessa domanda
*prima* di applicarsi (`llama-context.cpp:210`), coprendo in un colpo ibrido spento, proc address
non risolto e device non-CUDA. Mai un crash.

### ⚠ R-1 — vincolo di correttezza da rispettare nel banco

`ggml_sched_split_dipende_dal_worker` (`ggml-backend.cpp:2112-2128`) scorre **solo
`split->inputs[]`**, e il commento a :2096-2102 ne dichiara la premessa: *«perché uno split GPU le
legga, devono passare da una COPIA, e ogni copia è un `split->inputs[i]`»*. **R1 fa sparire proprio
quella copia**: lo split GPU leggerebbe l'uscita del worker direttamente dalla memoria mappata,
quindi la funzione torna `false`, quindi con `finestra > 0` **il join verrebbe saltato** e la GPU
leggerebbe mentre la CPU scrive.

**Verificato dalla regia**: `ggml_sched_overlap_finestra()` (`ggml-backend.cpp:2087-2093`) ha
**difetto 0**, e `LLAMA_OVERLAP_FINESTRA` **non è impostata** né nel `.bat` di produzione né nei
lanciatori dei banchi. Con `finestra == 0` la condizione a :2220 unisce comunque: **sicuro**.
Resta la regola: **mai R1 insieme a `LLAMA_OVERLAP_FINESTRA > 0`**.

Altri rischi dichiarati: `g_cuda_mapped_uva` (`ggml-cuda.cu:1461`) è **assegnato**, non messo in
AND, da ogni allocazione mappata — R1 ne aggiunge una, e se mai tornasse `host != dev` spegnerebbe
l'ibrido ovunque in silenzio (R-2); la leva richiede che una prima allocazione mappata sia **già
avvenuta** (R-3); il buffer di calcolo CPU resta pinnato ma cambia arena (R-4); il sito
`tensor_copy` a :2312 (ramo `FLAG_INPUT`) **non è strumentato**, quindi se il conto risultasse più
basso di nsys il buco è lì (R-5).

## 7-ter. ANCORA r40 — **FALLITA in caricamento**, comando ricostruito invece che eseguito

```
cudaHostAlloc di 2224.00 MiB fallita: out of memory
alloc_tensor_range: failed to allocate CUDA0_Mapped buffer of size 2332033024
llama_model_load: error loading model: unable to allocate CUDA0_Mapped buffer
```
Morta alle 01:55:17 **caricando il drafter**, zero numeri prodotti. Diagnosi dal confronto dei due
log:

| | 24/8 riuscita | 25/8 fallita |
|---|---|---|
| bersaglio, pesi CPU | `CPU model buffer size = 1010.00 MiB` | **`CUDA_Host model buffer size = 1010.00 MiB`** (pinnata) |
| drafter | `CPU model buffer size = 4458.36 MiB` | tenta `CUDA0_Mapped` 2224 MiB → OOM |

Sono sfuggiti **`--no-host`** e **`-otd`** (l'override che tiene gli esperti del drafter fuori dalla
mappata). **Nessuno dei due compare nel manifesto**: la regola di
`il-manifesto-non-e-la-configurazione` vale identica per gli argomenti CLI. Il tetto del pin è
~74,7 GiB sì / 76,9 no e il solo bersaglio ne prende 72,56: bastava poco per sfondarlo.

**Cancello di caricamento, da qui in avanti in ogni banco**: entro i primi 2 minuti deve comparire
`CPU model buffer size`, **mai** `CUDA_Host model buffer size`. Se compare, abortire subito.
**E non si ricostruisce un comando: si esegue lo script che l'ha prodotto** (`p1b_conf.ps1`, ora in
chiaro in `docs/porto/lanciatori/`).

Rilancio ordinato come **r41_ancora102k_sonda_20260825**: stesso script, tag nuovo, `LLAMA_SCHED_SONDA_COPIE=1`,
leva R1 **spenta**. Un solo banco fa due lavori — ancora fresca sul binario nuovo (che è quello su
cui girerà l'A/B) e lettura del bersaglio delle sonde.

## 7-quater. r41 — CONTROLLO CON SONDA: **e39 falsificato SPERIMENTALMENTE**

`r41_ancora102k_sonda_20260825`, binario chirurgo16, sonda accesa, leva **spenta**, script
`p1b_conf.ps1` **non modificato** (verificato prima del lancio: contiene `--no-host` alla riga 219 e
`-otd` alla 216). Cancello di caricamento superato a 15 s dall'avvio (`CPU model buffer size =
1010.00 MiB`). Durata 15m20s, chiusura pulita.

| | valore | vs ancora 24/8 |
|---|---|---|
| decode | **89,40 ms/token, 11,19 t/s** | −3,50% |
| prefill | 7,24 ms/token, 138,14 t/s | +0,44% |
| p1 / mean_len | 0,74725 / 2,14 | **identici** |
| **SHA output** | `D2E3AE05…76D06` | **identico byte per byte** |
| errori | zero assert/CUDA/nan/inf, divergenze replay 0 | |

Il −3,50% a **parità assoluta di traiettoria e output** è il costo di bookkeeping della sonda più il
binario nuovo, non un cambio di comportamento. **Il termine di paragone dei bracci successivi è
questo, non l'ancora del 24/8.**

### I dati della sonda — la lettura nuova confermata dalla misura

```
secchio 0 copy_experts      n 0,     byte 0                  <- ZERO. e39 FALSIFICATO
secchio 1 readback-ids      n 0,     byte 0
secchio 2 ripiego-sync-host n 20099, byte 2.122.607.584      <- il vero emittente
secchio 3 ripiego-sync-dev  n 836,   byte 12.155.920
taglie secchio 2: 32768x119  65536x3199  16x10332  196608x4  4x120  1024x356 | altre 5969
taglie secchio 3: 32768x4  1048x4  4x356  49152x234  2072x234  16384x2 | altre 2
censimento: grafi 13247, split 28607, ingressi 66995 | per grafo: split 2,16, ingressi 5,06
```

**`copy_experts` non emette nulla in decode: zero copie, zero byte su un'intera corsa.** La lambda
accusata il 24/8 è innocente, come l'aritmetica aveva già stabilito. E la taglia dominante del vero
emittente è **65.536 byte × 3.199**, esattamente il valore predetto dalla geometria del ramo CPU
(`4096 × 2 × 4 B`, `esperti_cpu` a 2 token): predizione fatta sul codice, confermata dalla misura.
Compaiono anche 2072 (= `ids`) e 49152 e 16384, tutti multipli di una riga di attivazione.

## 7-quinquies. r42 — LEVA R1 ACCESA: **non falsificata, BLOCCATA DA CAPACITÀ**

`r42_R1_bufmap_20260825`, stesso script, `LLAMA_SCHED_CPU_BUFT_MAPPED=1`. Verificato prima del
lancio: `LLAMA_OVERLAP_FINESTRA` non compare in `p1b_conf.ps1` → resta a 0, vincolo R-1 rispettato.

- **Cancello 1 SUPERATO**: `sched-cpu-buft: mappato ATTIVO - buffer di calcolo CPU CUDA_Host ->
  CUDA0_Mapped`, due volte, nessun `RIFIUTATO` in tutto il log. **La leva è raggiungibile e si
  attiva.**
- **Cancello 2 SUPERATO**: `CPU model buffer size = 1010.00 MiB`.
- **Poi, al cambio di fase verso il prefill (ubatch 2048):**

```
E ggml_backend_cuda_mapped_buffer_type_alloc_buffer: cudaHostAlloc di 524.17 MiB fallita: out of memory
E ggml_gallocr_reserve_n_impl: failed to allocate CUDA0_Mapped buffer of size 549632128
E graph_reserve: failed to allocate compute buffers
E srv update_slots: decode() failed: failed to allocate compute pp buffers
```

**Lo stesso identico buffer da 524,17 MiB che nel controllo r41 passa come `CUDA_Host` non passa
come `CUDA0_Mapped`**: il tetto della pinnabile è già eroso dai 74.304 MiB del modello mappato più
anello KV e stato compressore DSV4. Errore gestito (`send_error` pulito, zero `GGML_ASSERT`),
spegnimento regolare, nessun token generato → cancelli 3-6 **non valutabili**.

**Verdetto**: non è «rotta ma veloce» (la correttezza non è nemmeno stata messa alla prova) e non è
«non morde» (i contatori bassi sono l'assenza di prefill, non un trasporto rimasto sul vecchio
percorso). È **un guasto di capacità in un punto nuovo e preciso**.

**Prossimo passo, in corso**: `r43` con **ubatch ridotto** (512, poi 256), che rimpicciolisce
proporzionalmente quel buffer **senza rinunciare al contesto lungo** — il decode gira comunque a
ubatch minuscolo (`VRAM_A_FASI_UB=64`), quindi a soffrire è il prefill, che non è la metrica sotto
esame. Ordine **B-poi-A** (se B non parte, A è sprecato) e **controllo appaiato allo stesso
ubatch**: r41 non è più confrontabile. Piano C se nemmeno 256 entra: misurare R1 sul banco
**CORTO**, che è legittimo per il bersaglio perché il costo del lungo è additivo e l'81,7% è
pavimento, cioè esattamente ciò che il corto misura.

## 7-sexies. r43/r44 — R1 MORDE IL MECCANISMO 24×, MA LA PARETE NON SI MUOVE

**r43, sondaggio di capacità a ubatch ridotto: FALLITO, e conferma il modello.** Vincolo scoperto:
`p1b_conf.ps1` ha `-StartBatch` con `ValidateSet(1024, 2048, …)` e la tabella `$shapes` accoppia
sempre `Batch = UBatch` → **512 e 256 non sono raggiungibili senza modificare lo script**. A
ubatch 1024 la leva fallisce di nuovo, **ma a taglia esattamente dimezzata**: `cudaHostAlloc di
260.12 MiB fallita` contro i 524,17 di r42. Il rapporto 2:1 conferma che il buffer scala con
l'ubatch — il modello era giusto, il margine no.

**r44, banco CORTO, due bracci appaiati** (via `run_porto_hot.ps1`, già ripuntato al canonico dal
mandato 1; verificato per grep: `MAPPED_IBRIDO=1`, `OVERLAP_K=2`, `BATCH_MAX=3`, `PIN=1` intatti,
`FINESTRA` assente).

| | **B** (`r44_R1_corto`, leva ON) | **A** (`r44_ctrl_corto`, leva OFF) |
|---|---|---|
| `sched-cpu-buft` | `mappato ATTIVO` | `mappato SPENTO (difetto)` |
| censimento, **ingressi/grafo** | **22,62** | **63,83** |
| profilo, **confini blocco** (a 301 grafi) | **432** | **10.506** |
| p1 / mean_len | 0,75248 / 1,93 | 0,77670 / 2,01 |
| SHA output | `2A64594A…447B` | `AD3D3770…FE11` |
| decode t/s | 13,02 | 12,85 |
| errori | zero | zero |

- **G1 raggiungibilità: SUPERATO** — `mappato ATTIVO`, nessun `RIFIUTATO`.
- **G2 meccanismo: 2,82×**, sotto la soglia pre-registrata di 4× ma **tutt'altro che inerte**.
- **G3 conferma incrociata: 24,3×** — i confini di blocco crollano da 10.506 a **432**. Il crollo
  dei blocchi è **quasi un ordine di grandezza più grande** di quello degli ingressi: i due
  contatori sono correlati ma non equivalenti, e **è il blocco la cosa che R1 uccide**.
- **G4 correttezza: APERTO, giustamente non certificato.** SHA/p1/mean_len divergono fra B e A, ma
  sono **due lanci di processo separati** con speculazione accesa e K=2 — il regime in cui il
  progetto stesso dichiara che la bit-esattezza non è garantita
  (`cancello-sha-quando-vale`). In corso il **controllo di rumore** (`r45`): due lanci di A a
  parità di tutto. Se A1≠A2 la divergenza è rumore di lancio e il cancello diventa **a banda**; se
  A1=A2≠B, **R1 ha un baco** ed è un guasto.

### La lettura, e perché è un risultato anche se è negativo

**Il meccanismo funziona benissimo (24×), la parete si muove dell'1,3%, cioè dentro il rumore.** Se
il controllo di rumore conferma, la conclusione è netta e chiude una strada intera: **quei blocchi
host non erano overhead da togliere, erano l'host che osserva lavoro GPU vero**. È esattamente
l'ipotesi che l'analisi del rendezvous dava per «falsa quasi certamente», con l'argomento che il
costo per confine scala col **lavoro GPU** (0,24 ms a r41 contro 0,99 a t34) e non col numero di
confini. Un negativo pulito qui vale più di un positivo dubbio, perché **se togliere il 96% dei
blocchi non muove la parete, non la muoverebbe nemmeno un rendezvous perfetto** — e il fronte
host-bound si chiude in blocco, indicando che il collo è la GPU.

**Cautela dichiarata**: il corto ha p1 diversi fra i due bracci, quindi i due t/s non sono
comparabili a parità di traiettoria; e il profilo del corto non è quello del lungo (10.506 confini
su 301 grafi contro 320.661). **Il verdetto di velocità va preso sul lungo.**

### L'aritmetica della pinnata che spiega perché R1 non entra sul lungo, e come farcela entrare

```
modello mappato   74.304 MiB
draft mappato      2.224 MiB   (blocco 0, per -otd)
                  ──────────
totale             76.528 MiB = 74,73 GiB   <- il tetto noto è 74,7 sì / 76,9 no
+ buffer R1          524 MiB  =  75,2 GiB   -> SFONDA
```

Due margini da recuperare, entrambi già identificati: **(a)** `run_porto_hot.ps1` **non ha
`--no-host`** (scoperta dell'esecutore) e carica il bersaglio pinnato — 1010 MiB liberabili su quel
runner; **(b)** sul lungo, il **blocco 0 del drafter** occupa 2.224 MiB di mappata: spostarlo su
CPU normale libererebbe da solo quattro volte quel che serve a R1.

## 7-septies. r45 — CONTROLLO DI RUMORE: **R1 HA UN BACO DI CORRETTEZZA**

Tre lanci di **processo indipendenti** del braccio di controllo (leva spenta), banco corto,
configurazione di produzione (spec ON, K=2, PIN=1):

| | SHA output | p1 | acc/gen | mean_len | decode t/s |
|---|---|---|---|---|---|
| `r44_ctrl_corto` | `AD3D3770…FE11` | 0,77670 | 80/103 | 2,01 | 12,85 |
| `r45_ctrl_rumore_1` | `AD3D3770…FE11` | 0,77670 | 80/103 | 2,01 | 13,11 |
| `r45_ctrl_rumore_2` | `AD3D3770…FE11` | 0,77670 | 80/103 | 2,01 | 12,93 |
| **`r44_R1_corto` (leva ON)** | **`2A64594A…447B`** | **0,75248** | **76/101** | **1,93** | 13,02 |

**Il regime riproduce bit-esatto fra lanci indipendenti** (unica variazione: t/s entro 1,4%, che è
misura). Per lo schema pre-registrato prima di guardare i dati: **la leva cambia davvero l'output
⇒ R1 ha un baco di correttezza, non un guadagno di velocità.** **SOSPESA.**

**Rilettura obbligata del turno precedente**: il crollo dei confini di blocco (24,3×) e degli
ingressi (2,82×) restano fatti misurati, ma **non sono più leggibili come «la leva funziona»** —
sono sintomi di un calcolo alterato. E il t/s di B (13,02) **non è confrontabile** con quello di A:
sono due traiettorie diverse, non la stessa risposta calcolata più in fretta. La domanda «quei
blocchi erano overhead o lavoro GPU osservato» **resta aperta** e va riposta dopo il fix, non prima.

**Sospetto principale** [I], in diagnosi: la copia che R1 elimina non trasportava solo byte, era
anche **il punto di sincronizzazione** — `ggml_sched_split_dipende_dal_worker`
(`ggml-backend.cpp:2112-2128`) scorre **solo `split->inputs[]`**, ed è proprio quell'ingresso che
R1 fa sparire. Se il fix richiedesse di reintrodurre una sincronizzazione la leva potrebbe essere
strutturalmente vuota — ma una barriera *per split* è molto meno di *tre sync per ingresso*, quindi
non è scontato.

### Guadagno metodologico che vale più del braccio

**Su questo banco lo SHA È un cancello valido anche a spec ON + K=2.** La tabella storica
(`cancello-sha-quando-vale`) dava quel regime per non riproducibile; tre lanci indipendenti dicono
il contrario, confermando la nota della direttiva 16/8. **Regola aggiornata: prima di usare lo SHA
come cancello, misura se quel banco riproduce, con due lanci di controllo a parità di tutto.** Costa
due corse corte e restituisce lo strumento di correttezza più economico che esista — o ti dice in
anticipo che servono i cancelli sostitutivi. Senza questo controllo, il verdetto su R1 sarebbe
rimasto sospeso fra «baco» e «rumore».

## 7-octies. DIAGNOSI R1 — **IL FRONTE HOST-BOUND È CHIUSO**

### La misura che lo chiude era già sul disco, e nessuno l'aveva letta

Appaiando `sync` e `calc altri` di `sched-profilo` ai checkpoint dei due bracci r44 [M]:

| checkpoint | Δ `sync` (ON−OFF) | Δ `calc altri` (ON−OFF) |
|---|---:|---:|
| 51 grafi | **−21,47 ms/grafo** | **+21,76 ms/grafo** |
| 101 grafi | −11,15 | +15,16 |
| 301 grafi | **−4,09** | **+5,14** |

> **Il costo MIGRA 1:1, e leggermente in perdita.** Togliere il 96% dei blocchi host non fa sparire
> il tempo: lo sposta dal sito di attesa al **sito di lancio**, dove riaffiora come contropressione
> della coda. **Quei blocchi non erano overhead: erano l'host che OSSERVA lavoro GPU vero.**

**Conseguenza: cade l'intera classe «rendezvous ordinato dallo stream»** (`cudaLaunchHostFunc`,
kernel persistente, flag mappato) che l'analisi del rendezvous aveva nominato come l'unica direzione
con l'ordine di grandezza giusto. Se 24,3× di meccanismo danno zero parete, un rendezvous perfetto
darebbe zero. Precedente coerente già a ledger e mai collegato: `LLAMA_OVERLAP_JOIN_ASYNC` è la
versione plan-preserving della stessa idea sull'altro confine, **già misurata piatta** (−0,2%).

### Il piano è INVARIANTE — confermato 3× su banchi e ubatch diversi

Censimento sui grafi di riserva, appaiato per numero di grafi [M]:

| grafi | split r41 (OFF, lungo b2048) | r42 (ON, lungo b2048) | r43 (ON, ub1024) | ingressi OFF→ON |
|---|---:|---:|---:|---|
| 2 | **262** | **262** | **262** | 468 → 172 |
| 3 | **272** | **272** | **272** | 484 → 178 |
| 6 | **405** | **405** | **405** | 723 → 264 |

Conteggio degli split **identico all'unità** su tre corse indipendenti, due banchi e due ubatch,
mentre gli ingressi crollano di 2,7×. Sul decode di r44: 35,1 split/grafo a ogni checkpoint in
entrambi i bracci, `sched-sync` chiamate/grafo identiche a **tre decimali**, dispatch worker 10,30
contro 10,35. Con `GGML_CUDA_GRAPH_OPT=0` in entrambi i manifesti, **le stesse fusioni vedono gli
stessi sottografi**.

### Verdetto sulle ipotesi

| | esito | prova |
|---|---|---|
| **H1** join saltato via `dipende_dal_worker` | **REFUTATA** | `ggml-backend.cpp:2112-2128` è chiamata **solo** dentro `finestra > 0` (:2216-2219); con `FINESTRA=0` (difetto, nei manifesti) si prende `(split_id > split_spedito \|\| e_cpu)` (:2220) e con `CERCA_CPU=0` lo split spedito è `P+2` (:2537) ⇒ **join sempre eseguito**. *Il sospetto principale del ledger cade.* |
| **H3** allineamento / `nb[]` | **REFUTATA** | entrambi i buft hanno `get_alloc_size = NULL` → `ggml_nbytes`; l'allineamento 32 vs 128 cambia solo `tensor->data`, **mai** gli `nb[]` |
| **H4** cammino di calcolo diverso | **REFUTATA** | invarianza del piano, 3× |
| **H5** ordine di riduzione | **REFUTATA** | segue da H4: stessi kernel, stesse fusioni |
| **H6** l'arena CPU diventa condivisa fra worker concorrente e stream GPU | **unica superstite** [I] | i ~35 `synchronize`/grafo erano un **drenaggio di fatto dello stream**, l'unica barriera che teneva il fork/join concorrente compatibile con l'allocatore, che calcola le vite **assumendo esecuzione sequenziale** (`ggml-backend.cpp:2082-2086`) |

**«Una barriera per split costa meno di tre sync per ingresso» è FALSO su questo banco** [M]: i
confini di blocco sono 34,9 contro 35,1 split, cioè **già ~1 per split**. L'unica granularità che
comprerebbe qualcosa è *per lavoro del worker* (10,3/grafo = 3,4× in meno), che al costo misurato di
0,159 ms/confine varrebbe al massimo ~3,9 ms/grafo — e il costo migra comunque.

**R1 va ARCHIVIATA, non riparata.** Il fix plan-preserving concepibile
(`LLAMA_SCHED_INGRESSO_ASYNC`, cioè generalizzare i rami `copia_peso_host_async`/`copia_join_async`
già presenti a `:2313-2324`) è la stessa idea di `JOIN_ASYNC`, già falsificata e già marchiata «non
riproporre». Nota: `ggml_backend_cuda_cpy_tensor_async` **non aiuterà mai** a questo confine —
rifiuta guardando i **backend**, non i buffer (`ggml-cuda.cu:3824`), e al confine uno dei due è il
backend CPU per costruzione.

### ⚠ Due esposizioni di correttezza che esistono A PRESCINDERE dalla leva

Oggi mascherate **solo** dai ~35 drenaggi di stream per grafo. Chiunque tocchi quel meccanismo in
futuro le riporta a galla:
1. **Alias d'arena** [I]: un tensore dell'arena CPU il cui ultimo lettore è lo split GPU `P+1`
   (concorrente col worker) può vedersi riusare la memoria dal worker che calcola `P+2`. RAW/WAR
   reale, invisibile senza il dump delle assegnazioni.
2. **Ingressi utente** [C]: tutti i `GGML_TENSOR_FLAG_INPUT` sono assegnati al backend CPU
   (`ggml-backend.cpp:1118-1123`); il ramo `:2305-2312` fa `sync_profilato` *prima* di
   sovrascriverli, col commento «prevent the user overwriting the data before the copy is done». Il
   `set_inputs` del token successivo li riscrive con un **memcpy nudo** (`ggml-cuda.cu:1387-1390`,
   nessuna sincronizzazione) mentre i kernel del grafo precedente possono ancora leggerli.

---

## 7-nonies. r46 — `FORK_DOWN_TARDI`: correttezza SUPERATA, prestazione NON MISURABILE (sessione contaminata)

**Cancello d'identità — con una precisazione che vale per il futuro.** La riga `cache-esperti:` è
identica carattere per carattere fra i due bracci, **ma non perché la leva non sia stata letta**:
quella riga non ha un campo per `down_tardi`. Il segnale sta nella riga adiacente dello stesso
blocco d'avvio:

```
B: porto-cb: epoca=1 semina da ambiente: fork=2 blocchi=8 down_tardi=1 pf_top=0 sfratto_par=1
A: porto-cb: epoca=1 semina da ambiente: fork=2 blocchi=8 down_tardi=0 pf_top=0 sfratto_par=1
```

**Per questa leva si grep-a `porto-cb:`, non `cache-esperti:`.** Tacca ulteriore per
`il-manifesto-non-e-la-configurazione`: anche la riga «identità vera» è parziale, e quale riga porti
il segnale dipende dalla leva.

**Cancello di correttezza: SUPERATO, e più forte dell'atteso.** p1 e mean_len identici
(`0,74725 — 136/182 — 2,14`) e **SHA output identico byte per byte** fra B, A e l'ancora del 24/8.
Mi aspettavo divergenza legittima (la leva cambia l'ordine delle copie); invece **non tocca
l'aritmetica**. Dato acquisito, non va rimisurato.

**Prestazione: nessun verdetto. La coppia è inutilizzabile.**

| | B (`r46_downtardi`) | A (`r46_ctrl`) |
|---|---|---|
| prefill | 137,60 t/s | 132,00 t/s |
| decode | 92,79 ms/tok, **10,78 t/s** | 183,23 ms/tok, **5,46 t/s** |
| cambi di fase VRAM (n.1 / n.2) | 33,0 / 28,4 ms | **4234,6 / 1028,4 ms** |
| `warmup_resets` max | — | **15** |

Un B/A che darebbe +97% contro un atteso di +2,8% è la firma di un controllo rotto, non di una leva
straordinaria: verdetto correttamente **non preso**.

**E la contaminazione è più ampia del solo braccio A.** r41 (controllo **con la sonda accesa**, che
costa ~3,5%) ha fatto **11,19 t/s**; r46 B gira **senza sonda** e fa **10,78** — doveva essere più
veloce, non più lento. Quindi il degrado **precede** il braccio A e tocca tutta la coppia.

**Firma diagnostica**: cambi di fase VRAM 100-150× più lenti **con RAM libera a 87,3 GB**. Non è
esaurimento, è **frammentazione della memoria pinnabile** dopo nove lanci consecutivi di un processo
che ne prende 74 GiB ogni volta. Il `warmup_resets=15` è probabilmente conseguenza, non causa.

**Regola nuova, dal runbook §8.5 che chiedeva la rimisura a freddo dopo tre bracci mentre noi eravamo
a nove**: **ri-ancorare il riferimento ogni tre bracci**, non a fine giornata. E aggiungere ai
cancelli di sanità di ogni corsa: **cambio di fase VRAM sotto 100 ms** e `warmup_resets` basso —
sono indicatori di salute della *sessione*, non solo diagnosi a posteriori.

Rilancio ordinato come `r47`, **ordine A-poi-B** (il controllo per primo: se è già degradato lo si
scopre senza spendere anche B), con cancello di sanità pre-registrato — decode di A sopra 10,5 t/s e
cambi di fase sotto 100 ms, altrimenti la macchina va riavviata.

## 8. STATO E CODA

**Chiuso il 25/8**, tutto per misura: fascicolo SLOT 473 (era già in produzione) · **speculazione**
(tetto 17,0 t/s con bozza perfetta) · **strada DMA** (segno invertito: il kernel è 1,6-1,8× più
veloce) · **attribuzione e39** (falsificata dall'aritmetica e poi dalla sonda: `copy_experts` = 0
copie, 0 byte) · **duplicazione cache/scheduler** (non esiste, popolazioni disgiunte per
costruzione) · **R1 e con essa il fronte host-bound** (il costo migra 1:1) · **`K=0`** (è −29,8%,
non una leva) · **`FINESTRA`** (inerte per costruzione) · **`SPIN`** (spazzata) · l'anomalia del
**degrado free-run** (è composizione del testo; semmai è il banco a sovrastimare del 12-14%).

**In volo**: `r46` `FORK_DOWN_TARDI` sul lungo (B-poi-A) · progettista sulla **riduzione dei byte**.

**La direzione, dopo la chiusura dell'host-bound**: se l'host non è il collo, il collo è la GPU, e
dentro la GPU il **bus**. Le durate di `kern_fj_copia` sono quantizzate a 285,7 µs/esperto con un
**vuoto assoluto fra 10 e 250 µs** — nessun esperto è servito da VRAM, **passano tutti dal PCIe**;
409 MiB/token a 23 GiB/s. **Unica strada: ridurre i byte**, e la requantizzazione è esclusa (già
IQ2_XXS, 2,06 bpw). Restano *meno copie* (il **70,8%** di ciò che copiamo non è mai riusato, e
l'85,5% non arriva ai due usi che ripagano la copia) e *meno esperti* (adaptive-K, o spingere il
ramo CPU oltre K=2 — che già toglie 1/3 della domanda alla cache). **Discrepanza da sciogliere**: la
stessa famiglia è stimata 17-20% in una fonte e 2,9-5,8% in un'altra.

**Coda**: (1) verdetto `FORK_DOWN_TARDI`; (2) prima leva di riduzione byte, su raccomandazione del
progettista; (3) env-only mai raccolte: `FORK_STADI=1` (+2,41% bit-identico, mai sul lungo),
`LLAMA_DSV4_TOPK_FUSO=1` (+0,90% a zero righe, spenta in **ogni** manifesto mai registrato);
(4) chiusura di fascicolo `nmax=4 × conf 0,70` con go/no-go pre-registrato a mean_len > 3,34;
(5) opzionale: una corsa corta che ripete il braccio R1 per stabilire se dietro c'è una **corsa
vera** nel fork/join (H6) — vale indipendentemente da R1, perché l'esposizione esiste nel codice.

**NON riproporre**: `JOIN_ASYNC` · `LLAMA_SCHED_CPU_BUFT_MAPPED` (R1) · `OVERLAP_K=0` ·
`OVERLAP_PIN=0` · `OVERLAP_FINESTRA` · `OVERLAP_SPIN` · `LLAMA_KV_PAD` 256→1024 · repoint/B-2 ·
griglia di copia più larga · prefetch con previsione esatta · capienza (più slot) · insieme statico
· super-op CPU FFN · macro-kernel decode v2 · `GGML_SCHED_EVENT_JOIN`.

**Vincolo VRAM**: al confine prefill→decode il log dice `+473 slot, +3194 MiB … VRAM libera 0 MiB`.
**Nessuna leva può chiedere VRAM lì.** E sul versante pinnata: 74.304 MiB (modello) + 2.224 (blocco
0 del draft) = 74,73 GiB, già al tetto (74,7 sì / 76,9 no). Margini recuperabili se servissero:
`--no-host` mancante in `run_porto_hot.ps1` (1010 MiB) e il blocco 0 del draft (2.224 MiB).

**Contraddizione aperta**: pendenza **0,431 ms/fwd/1000ctx** (turno 32, 3 punti + replica bit-esatta
del 64k) contro **0,1456** (e35). Non riconciliano. Usare 0,431 per gli **assoluti**, e35 solo per
le **proporzioni**.

**Strumento riguadagnato**: su questi banchi lo **SHA riproduce bit-esatto fra lanci di processo
indipendenti anche a spec ON + K=2** (tre lanci di controllo identici). Prima di usarlo come
cancello in un regime nuovo, **misura che quel banco riproduca** con due lanci di controllo: costa
due corse corte e restituisce il cancello di correttezza più economico che esista.
