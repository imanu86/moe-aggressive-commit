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

## 7-decies. FRONTE BYTE — una leva ritrovata, una falsificazione mai registrata, e il trasporto raddoppiato

### ⚠ CORREZIONE AL BUDGET: il trasporto è ~2× quello che questo ledger dichiarava

L'aritmetica `409 MiB/token → 17,3 ms → 20,1%` è ancorata alla finestra a **256 token** (colpi
72,6%). Sul banco vero — 102k, completion **8192**, il punto da 75,44 ms/token — il tasso di colpi
stazionario è **51,5%**:

```
buchi 976.213 / 8192 tok = 119,2 miss/token × 6,75 MiB = 804 MiB/token
a 23,07 GiB/s = 34,0 ms/token = 45,1% della parete      (NON 20,4%)
```

Confermato indipendentemente da `p1b_conf070` (73,64 ms/tok): 795 MiB/token → 33,7 ms → 45,7%.
**Il trasporto è quasi metà della parete, non un quinto.** E la derivazione «azzerare il trasporto
dà 14,5 t/s» di §5 usava l'ancora a 256 invece della SOTA lunga: **il numero regge per un'altra via
(l'elasticità empirica), la derivazione no.**

### 🔑 `LLAMA_OVERLAP_BATCH_MAX=4` — la leva ritrovata, misurata il 21/8 e mai registrata

`llama-graph.cpp:1862-1867`: `forma_ammessa = n_tokens <= batch_max`. Con `BATCH_MAX=3` **ogni
forward da 4 righe gira senza corsia CPU**, cioè con tutti e 6 gli esperti sulla cache — e a nmax=3
il forward di verifica arriva a 4 righe. Misura diretta al punto SOTA lungo: `domanda 2.011.416`
contro `4 × partizioni 123.840 = 495.360` ⇒ **≥ 75,4% della domanda gira SENZA corsia CPU.**

Coppia appaiata del 21/8, stesso checkpoint (`pos 101686, n_past 101687`), unica differenza la
variabile (`D:\ds4_work\llama_run\t24_long_restore_{control473,overlapbm4}_g1_c070_n3_b1200_20260821.server.log`):

| | control (BM=3) | **overlapbm4 (BM=4)** | Δ |
|---|---:|---:|---:|
| `partizioni` | 30.874 | **57.792** | **+87,2%** |
| `domanda` | 285.433 | 226.041 | −20,8% |
| `colpi` | 58,3% | **66,8%** | +8,5 pt |
| **`buchi`** | 119.138 | **75.152** | **−36,9%** |
| **`byte a domanda`** | **785,74 GiB** | **495,64 GiB** | **−290,1 GiB** |
| p1 / mean_len | 0,83238 / 2,56 | 0,83939 / 2,49 | in banda 2σ |
| ms/token · t/s | 77,58 · 12,89 | 76,03 · 13,15 | −2,00% · +2,02% |
| **`C_round`** | 198,6 ms | **189,3 ms** | **−4,68%** |

**Non è in nessun ledger** (grep su `docs/`), è rimasto orfano quattro giorni, e **il runner di
produzione è ancora a 3**. Il `mean_len` peggiore in B è un handicap: il t/s grezzo (+2,0%, dentro
banda) **sottostima** la leva; la metrica onesta è `C_round`.

*Trappola latente*: `build_moe_ffn_overlap` chiama `ggml_dsv4_moe_decode` senza controllare
`n_tokens` (`llama-graph.cpp:1935-1941`) mentre l'op asserisce `n_tokens <= 3` (`ggml.c:6809`).
Oggi irraggiungibile perché `LLAMA_DSV4_DECODE_TILE_VRES` è spento — ma **`BATCH_MAX≥4` +
`TILE_VRES=1` = abort**. Una riga di guardia a `:1936`.

### ⚠ LA POLITICA A TRE LIVELLI È FALSIFICATA — e il «vale 17-20%» va ritirato

La macchina è **completa e cablata end-to-end** (maschera a quattro valori `kern_fj_maschera:6042`;
pesi del router dentro la cache `:4882-4888`; «non installare» `:5046-5080`; dispatch misto
`ggml-cuda.cu:2704-2732`). Il blocco dichiarato il 13/8 («la cache non riceve i pesi») **è stato
risolto**. Non manca nulla da accendere: **manca una ragione.**

Banco 13/8, **cinque bracci contro due riferimenti**, unica variabile `peso_copia_pm`: **monotono —
più byte si eliminano, più si perde.** `p150` toglie il **97,2% dei byte** e perde il **16,9%**; col
pavimento anti-collasso toglie il 57,8% e perde il 2,4%, *pur alzando i colpi di +12,3 punti*. **Il
meccanismo funziona; è il costo per miss ad avere il segno sbagliato**: lo zero-copy mappato in situ
costa **0,43-0,68 ms/esperto contro 0,33-0,40 della copia**. Ragioni strutturali assenti dal
microbench: compete col fork stream sullo stesso PCIe, e ha il pattern d'accesso della MMVQ invece
di uno stream contiguo di `int4`. E peggiora nel regime nuovo: **la copia si de-duplica per riga, la
lettura mappata si paga UNA VOLTA PER RIGA** (`mmvq.cu:1385`) — a mean_len 3,06 sono ~4 righe.

**La discrepanza 17-20% contro 2,9-5,8% è sciolta: non regge nessuno dei due.** Il 17-20% aveva
denominatore sbagliato (55,5 s invece di 83,24) e numeratore sbagliato (contava anche il gruppo «1
uso», che in zero-copy **perde** 0,066 ms a testa): gonfiato 1,5-1,8×, e poi il segno si inverte. Il
2,9-5,8% è un canale **diverso** (`MASSA_CORSIE`), già misurato a **−5,69%** con raggiungibilità
passata (`LEDGER_17_AGOSTO.md:2405-2415`).

**Debito**: il binario **stampa a ogni corsa una raccomandazione falsificata**
(`cache-esperti.cu:8301-8303`: «in zero-copy costerebbero 0,274 invece di 0,403»).

### Il nucleo caldo esiste, ed è l'1,1% — firma di THRASHING

Al punto SOTA lungo: `mai=82,1% · 1=12,2% · 2-3=4,6% · 4+=1,1%`, riuso medio **1,06 per installato,
mediana zero**. Ma le classi 1 e 2-3 spiegano al massimo ~250k colpi su 1.035k ⇒ **i restanti ~785k
(76%) stanno nella coda `4+`, che è l'1,1% degli installati** (~75 colpi ciascuno). `vive-censurate
= 473` = esattamente la capienza: la contabilità chiude, non è un artefatto.
E **`bussate al momento del buco: 8+ = 81,9%`**: i buchi **non sono esperti freddi**, sono esperti
con storia lunga continuamente sfrattati. **È thrashing, non working set assente.** Raffina e in
parte contraddice `non-esiste-nucleo-caldo`.

### Il tetto del fronte byte, tre vie concordi

**Fattore di realizzazione, misurato** sul braccio bm4: 10,5 ms/token di trasporto seriale rimosso
hanno mosso la parete di **1,55 grezzi / 3,63 normalizzati** ⇒ **si realizza il 15-34%** del tempo
di trasporto che si toglie (il fork stream sovrappone la copia al calcolo, e la corsia CPU paga in
tempo CPU ciò che risparmia in byte).

| | ms/token | t/s |
|---|---:|---:|
| annullare **tutto** il trasporto (34,0 × realizzazione 15-34%) | 70,3 → 63,8 | **14,2 - 15,7** |
| estrapolazione lineare dell'elasticità bm4 | | 14,0 - 15,0 |
| **+ annullare anche il MoE mascherato** (10,5% = 7,9 ms) | 62,4 → 55,9 | **16,0 - 17,9** |
| *tetto assoluto*: parete senza trasporto **né** MoE (−30,9%) | **52,1** | **19,2** |

> **Un sottosistema esperti che costasse letteralmente zero — zero byte e zero calcolo — dà 19,2
> t/s.** Il bersaglio è 20,0. **La famiglia «riduzione byte» non contiene un percorso ai 50,0
> ms/token**, e la sua realizzazione plausibile si ferma a ~15 t/s.

**E l'unico item abbastanza grande resta il fronte bolle (39,3% della parete), che questo ledger ha
dichiarato chiuso a §7-octies ma che §7-septies riapre da solo**: il verdetto poggia sui bracci r43/r44,
e r45 ha accertato che R1 ha un baco. **Il fronte host-bound non è chiuso: è SOSPESO**, e va
riconfermato su un braccio non contaminato.

## 7-undecies. r48 — `BATCH_MAX=4` sul CORTO: **G1 fallito, e l'errore è di regia**

Sei corse (tre per braccio), banco corto. Ogni terna **bit-identica al proprio interno** — terza
conferma che il banco riproduce fra lanci indipendenti. Macchina **sana** (zero stalli nei log,
~15 s stabili su tutte e sei, nessuna contaminazione: la sessione precedente era un episodio, non
uno stato).

| | `partizioni` | `buchi` | `byte a domanda` | colpi | mean_len | p1 | `C_round` mediana |
|---|---:|---:|---:|---:|---:|---:|---:|
| A (BM=3) | 8.041 | 8.304 | 54,77 GiB | 74,5% | 2,01 | 0,77670 | **148,56** |
| B (BM=4) | 8.170 | 10.357 | 68,31 GiB | 67,6% | 2,06 | 0,78846 | **154,19** |
| Δ | **+1,6%** | +24,7% | +24,7% | −6,9 pt | | | **+3,79%** |

- **G1 raggiungibilità: FALLITO.** `partizioni` +1,6% contro la soglia di +50% (il 21/8 fu +87,2%).
  Per la regola pre-registrata, **l'esito è da buttare, non da interpretare**.
- **G2: fallito in direzione opposta** (+24,7% invece di −25%).
- **G4**: `C_round` **sale** del 3,79%; anche il t/s grezzo è sfavorevole (−1,26%) — qui non c'è
  nemmeno il pattern «grezzo positivo / normalizzato negativo» del 21/8.

### La lezione, e l'errore è mio

Avevo giustificato il banco corto così: *«il costo del lungo è additivo e l'81,7% è pavimento,
quindi un guadagno sul corto si trasferisce»*. **Vero per il COSTO, falso per la POPOLAZIONE dei
forward.** `BATCH_MAX` agisce sui forward da 4 righe, e quanti ce ne siano dipende dalla
distribuzione di `mean_len`: sul corto è **2,01-2,06** — quasi tutti i forward hanno 2-3 righe, già
coperti da `BATCH_MAX=3`, quindi alzare la soglia non ha bersaglio — contro il **2,56** del braccio
del 21/8.

> **REGOLA: una leva che dipende da `mean_len` va misurata dove `mean_len` è quello vero. Verificare
> PRIMA che il bersaglio della leva esista nel banco che si sceglie.**

Nota dell'esecutore, corretta e da tenere: B e A avevano già `mean_len` (2,06 vs 2,01) e p1 diversi,
quindi erano **due traiettorie diverse** e i contatori di trasporto non erano confrontabili fra loro
nemmeno in linea di principio — il peggioramento dei buchi è quasi certamente questo, non un danno
della leva.

*Episodio collaterale, chiuso senza forzature*: lo script che aveva prodotto il braccio del 21/8
(`run_p1_nudo.ps1`) ha un **cancello d'identità su cinque hash** e li rifiuta tutti, essendo tarato
su una build di cinque giorni fa; e il suo checkpoint da 1,05 GB (KV + stato drafter + checkpoint)
era stato salvato **da quel binario**. Ripristinarlo in uno nuovo rischia il caso peggiore — un
restore che «riesce» producendo numeri verosimili e falsi. **Non si aggiornano gli hash attesi di
uno script per far passare un cancello**: il cancello stava facendo il suo mestiere. Aggirato usando
un banco che non richiede restore.

Rilancio come `r49` **sul lungo**, coppia singola (i contatori sono deterministici e il banco
riproduce; le triplette servirebbero solo al t/s, che qui non decide), con G1 promosso a cancello di
esistenza: **se `partizioni` non sale nemmeno lì, il +87,2% del 21/8 dipendeva dal regime restore e
il fascicolo si chiude.**

## 7-duodecies. r49 — `BATCH_MAX=4` sul LUNGO: **CRASH, fascicolo chiuso, e un bug vero**

*Prerequisito, chiuso pulito*: `p1b_conf.ps1` hardcodava `LLAMA_OVERLAP_BATCH_MAX='3'` dentro
`Set-SotaEnvironment` e non esponeva il parametro. Esteso con **4 righe** (parametro
`$OverlapBatchMax = 3` nel `param()`, stesso parametro nella firma della funzione, il literal
sostituito, la chiamata aggiornata), backup byte-verificato, parse OK, e **cancello di
non-regressione superato con tre controlli** (nessun argomento → 3, `4` → 4, `3` → 3). *Distinzione
di principio applicata*: **estendere** uno script con difetto invariato è lecito; **aggiornare gli
hash attesi** di `run_p1_nudo.ps1` per far passare il suo cancello d'identità no — quello
disattiverebbe un controllo di sicurezza che esiste per impedire il restore di uno stato salvato da
un binario diverso.

**Esito del braccio B**: cancello di caricamento superato, prefill completato, richiesta avviata.
Poi, **subito dopo `common_reaso: forced sequence complete, done`** (il taglio forzato del
reasoning):

```
get_rows_q indice invalido: src0=markov_w1.weight src1=CPU#node_509#0 dst=node_510
            i=0 i10=0 i11=0 i12=0  indice=-1  righe=129280
ggml/src/ggml-cpu/ops.cpp:4831: GGML_ASSERT(i01 >= 0 && i01 < ne01) failed
```

**Non è l'assert previsto** (`ggml.c:6809`, legato a `TILE_VRES`, verificato assente): sito diverso,
e il tensore è **`markov_w1.weight` della testa di routing del drafter** (129.280 righe = vocab).
Processo morto da solo, nessun output, nessun `p1`/`mean_len`/`C_round` misurabile. **Il braccio A
non è stato lanciato**, correttamente: una leva che fa fallire la richiesta non è promuovibile, e
nessun controllo appaiato lo direbbe meglio di un assert con file, riga, tensore e valore
dell'indice.

**`LLAMA_OVERLAP_BATCH_MAX=4` è CHIUSA.** Il `+87,2%` di `partizioni` del 21/8 resta una domanda
aperta sul **regime restore**, non una leva viva.

### Il bug vale più del braccio

**Perché il banco corto non lo vede** [D, sostenuta dai dati]: `run_porto_hot.ps1` **non imposta
alcun reasoning-budget**, quindi la richiesta non attraversa mai il taglio forzato. La leva
interagisce male **con quella transizione**, non con la decodifica in generale.

> **REGOLA: una leva provata solo sul banco corto non è stata provata sulla transizione di
> fine-reasoning — che in produzione c'è sempre.**

E un **indice negativo in una lookup** non è mai «solo» l'interazione fra due opzioni: qui l'assert
ha salvato la corsa, ma lo stesso −1 in un cammino senza bounds-check sarebbe una **lettura fuori
tabella silenziosa**. Il progetto ha già l'idioma giusto (`voci fuori tabella`/`voci negative`
dell'ADAPTIVE-K, `NOTE_IMPLEMENTAZIONE.md` §7.2): andrebbe esteso a questa lookup. **Item aperto.**

## 7-terdecies. r50 — le tre leve insieme: **SHA divergente, G2 fallito**

Banco lungo, prefill reale 101k, `-MaxTokens 1200`, coppia appaiata.

**G1 — testimoni, e uno dei tre è debole:**

| leva | testimone | esito |
|---|---|---|
| `FORK_DOWN_TARDI` | `porto-cb: … down_tardi=1` (B) / `=0` (A) **+** manifesto | letta, **doppio** testimone |
| `FORK_STADI` | riga dedicata `cache-esperti: FORK_STADI=1 -- pipeline gate -> up -> down con join distinti` (solo in B) **+** manifesto | letta, **doppio** testimone |
| `TOPK_FUSO` | **solo** il manifesto. **Nessuna riga operativa** in nessuno dei due log | letta secondo il manifesto, **senza testimone indipendente** |

**G2 — correttezza: FALLITO, e non per rumore.**

| | B (tre leve) | A (nessuna) |
|---|---|---|
| SHA output | `b9fd992f…e252` | `a177ddaf…7479` |
| p1 (acc/gen) | 0,81766 (713/872) | 0,84073 (739/879) |
| mean_len | 2,47 | 2,61 |

Entrambi i testi letti **integralmente** (3784 e 3586 caratteri): due saggi tecnici coerenti e
pertinenti, ma **divergono già dal secondo paragrafo** — non è deriva tardiva, la traiettoria si
separa presto, coerente con un p1 diverso fin dalle prime posizioni.

**G4 — non rendibile, dati per trasparenza soltanto**: decode 12,95 contro 12,66 t/s (+2,29%),
`C_round` 190,74 contro 206,13 (**−7,47%**). Sembrerebbe superare la soglia e avvicinarsi al +6%
atteso, **ma B e A hanno calcolato output diversi**: un `C_round` più basso su una traiettoria con
`mean_len` più corto (2,47 contro 2,61) non è un guadagno comparabile, potrebbe essere solo l'effetto
di generare risposte più brevi per token accettato.

**G5 salute: pulita.** Zero assert/CUDA error, zero guasti/in ritardo/pesi mancanti, divergenze
replay a zero. Cambi di fase VRAM 36,4/10,1 ms (B) e 30,8/8,7 (A), **ben sotto i 100 ms**;
`warmup_resets` 42 e 39, comparabili. **Nessuna contaminazione di sessione.**

### La lettura, e la correzione al sospetto

L'osservazione dell'esecutore che **«due testi entrambi ottimi ma diversi fra loro sono precisamente
il sintomo di G2»** è la lettura corretta: *il cancello di qualità non è un sostituto del cancello di
identità*, e nessuno deve usare il primo per assolvere il secondo.

Il sospetto su `TOPK_FUSO` è probabilmente giusto **ma non come baco**: quella leva **fonde nove
kernel del router in uno**, e una fusione cambia l'ordine delle operazioni in virgola mobile ⇒ **lo
SHA diverge per costruzione**, stessa classe della fusione HC già adottata. L'esito atteso non è
«leva rotta» ma **«leva con cancello diverso»**: per `TOPK_FUSO` il cancello dev'essere p1 in banda
più il §4.10, mai lo SHA.

**Scomposizione ordinata come `r51`, e costa UNA corsa sola** — il controllo A di r50 è già in cassa
e questo banco riproduce bit-esatto: `DOWN_TARDI` + `STADI` accese, `TOPK_FUSO` spenta. Se lo SHA
torna `a177ddaf…7479`, le due sono pulite, la divergenza era tutta della fusione, **e il confronto
di prestazione contro A diventa valido a parità di traiettoria**. Se invece diverge ancora, allora
**è la COMBINAZIONE a non essere neutra** — fatto pesante, dato che `DOWN_TARDI` da sola era già
risultata SHA-identica in r46.

## 7-quaterdecies. r51 — scomposizione: **le due leve sono PULITE, la fusione era la causa**

Una sola corsa (il controllo A di r50 era già in cassa e il banco riproduce bit-esatto):
`DOWN_TARDI` + `STADI` accese, `TOPK_FUSO` spenta e **verificata assente** dal manifesto.

```
SHA r51    = a177ddaf3583610cde43ed768e9d0e950aa32b0f63d7acfa88e9657f26a47479
SHA A(r50) = a177ddaf3583610cde43ed768e9d0e950aa32b0f63d7acfa88e9657f26a47479   ← IDENTICO
p1  0,84073 (739/879) in entrambi · mean_len 2,61 in entrambi                    ← IDENTICI
```

**`DOWN_TARDI` + `STADI` sono correttezza-PULITE in combinazione**, e **la divergenza di r50 era
interamente di `TOPK_FUSO`** — coerente con la sua natura di fusione a nove kernel, che altera
l'ordine delle operazioni in virgola mobile **per costruzione, non per baco**. La domanda pesante
lasciata aperta da r50 («è la combinazione a non essere neutra?») è **risolta: no**.

*Nota di metodo dell'esecutore, corretta*: il §4.10 non è stato rifatto da zero perché **con SHA
identico byte per byte il testo è lo stesso già letto e giudicato**, e l'identità è una garanzia più
forte di una rilettura manuale. Averlo **dichiarato** invece di darlo per scontato è il modo giusto
di trattare un cancello.

**Prestazione, ora comparabile a parità di traiettoria:**

| | r51 (due leve) | A (r50) | Δ |
|---|---:|---:|---:|
| decode | **13,02 t/s** | 12,66 | **+2,84%** |
| ms/token | 76,80 | 78,98 | −2,76% |
| `C_round` | 200,45 | 206,14 | −2,76% |
| prefill | 138,18 | 138,08 | +0,07% (fuori verdetto) |

**Sotto la soglia di promozione (+3%) — ma il confronto che conta è un altro**: `DOWN_TARDI` **da
sola** aveva dato **+3,67%** (r47), la combinazione con `STADI` dà **+2,76%**. **`STADI` non
aggiunge nulla e semmai toglie.**

> **Lettura: si promuove `DOWN_TARDI` da sola; `STADI` resta parcheggiata.** Non serve spendere
> corse per certificare una combinazione peggiore della sua parte migliore.

Salute pulita: zero assert, divergenze replay a zero, cambi di fase VRAM 35,3/5,9 ms,
`warmup_resets` 39 identico al controllo.

## 7-quindecies. r47 — **`FORK_DOWN_TARDI` PROMOSSA** (le cifre misurate)

| | A `r47_ctrl` | B `r47_downtardi` |
|---|---:|---:|
| prefill | 7,24 ms/tok, 138,05 t/s | 7,24 ms/tok, 138,08 t/s |
| **decode** | 87,48 ms/tok, **11,43 t/s** | 84,36 ms/tok, **11,85 t/s** |
| p1 (acc/gen) | 0,74725 (136/182) | 0,74725 — **identico** |
| mean_len | 2,14 | 2,14 — **identico** |
| **SHA output** | `D2E3AE05…76D06` | `D2E3AE05…76D06` — **identico byte per byte** |

**Δ decode +3,67% t/s (−3,57% ms/token), con SHA, p1 e mean_len identici**: guadagno pulito a
parità assoluta di traiettoria, correttezza verificata *prima* dell'adozione. **PROMOSSA.**

## 7-sexdecies. r52 — `TOPK_FUSO` da sola: parcheggiata, e una triangolazione che chiude il quadro

**Triangolazione non richiesta ma decisiva**: SHA di r52 = `b9fd992f…e252`, **identico al braccio B
di r50** (tre leve insieme), con p1 e mean_len pure coincidenti. Da un terzo angolo, indipendente dal
ragionamento sulla fusione: **`TOPK_FUSO` da sola riproduce l'INTERA divergenza di r50** —
`DOWN_TARDI`+`STADI` non aggiungono nulla all'aritmetica, come r51 aveva già stabilito dal lato
opposto.

- **G1 testimone: ASSENTE.** Cercato case-insensitive su `TOPK_FUSO` e `topk`: l'unico riscontro è la
  riga di manifesto. **Debito dichiarato**: questa leva non è verificabile raggiungibile se non dal
  manifesto — se il lettore la leggesse senza usarla, dal log non lo sapremmo.
- **G2 (non SHA, per costruzione)**: p1 0,81766 contro 0,84073, banda 2σ = [0,8160 ; 0,8654].
  **Dentro banda ma a 1,87σ**, cioè 0,0017 sopra il confine: ci passa **di poco**. Testo riletto per
  intero: lingua sana, nessun loop, pertinente.
- **G4**: decode +0,79% (atteso dichiarato +0,90%), **sotto la soglia dei +3% ⇒ PARCHEGGIO**. Il
  `C_round` darebbe −6,12% ma **`mean_len` non coincide** (2,47 contro 2,61), quindi parte del calo
  può essere solo «risposte più corte per token accettato»: non lo si prende come verdetto.
- **G5**: salute pulita, cambi di fase VRAM 36,8/5,6 ms, `warmup_resets` 42.

---

## 8. BILANCIO DELLA CAMPAGNA E STATO FINALE

### I dodici bracci della notte

| # | braccio | esito |
|---|---|---|
| 1 | bonifica `run_porto_hot.ps1` | ripuntato al canonico + guardia d'identità DLL (avvisa, non blocca) |
| 2 | `r40` ancora ricostruita da log | **FALLITO** — mancava `--no-host`, OOM sul drafter |
| 3 | `r41` ancora con lo script vero | riuscita, 11,19 t/s, SHA identico all'ancora del 24/8 |
| 4 | `r42`/`r43` `CPU_BUFT_MAPPED` a ub 2048 e 1024 | OOM sul buffer di calcolo mappato (scala con l'ubatch: 524 → 260 MiB) |
| 5 | `r44`/`r45` `CPU_BUFT_MAPPED` sul corto | raggiungibile ma **ROTTA**: SHA diverge da tre lanci bit-identici ⇒ **sospesa** |
| 6 | `r46` `FORK_DOWN_TARDI` | sessione contaminata (5,46 t/s, `warmup_resets`=15) ⇒ scartato |
| 7 | **`r47` `FORK_DOWN_TARDI`** | **PROMOSSA +3,67%**, SHA identico |
| 8 | `r48` `BATCH_MAX=4` sul corto (3+3) | G1/G2 falliti — **il banco corto non ha la popolazione di forward** |
| 9 | `r49` `BATCH_MAX=4` sul lungo | **CRASH**, indice −1 sulla testa Markov ⇒ chiusa |
| 10 | `r50` tre leve insieme | G2 fallito, SHA/p1/mean_len divergenti |
| 11 | `r51` `DOWN_TARDI`+`STADI` | **correttezza pulita** (SHA identico), +2,76% ⇒ `STADI` parcheggiata |
| 12 | `r52` `TOPK_FUSO` da sola | causa unica della divergenza; +0,79% ⇒ parcheggiata |

**Netto**: **una leva promossa** (`FORK_DOWN_TARDI`, +3,67%, correttezza verificata), due parcheggiate
con dati puliti, una chiusa per crash, una sospesa per correttezza rotta. E **cinque fascicoli chiusi
per misura** senza spendere quasi macchina: speculazione, DMA, attribuzione e39, duplicazione
cache/scheduler, politica a tre livelli.

### Il verdetto sul bersaglio

**I 20 t/s non sono raggiungibili su questo banco**, e ora è quantificato da tre vie indipendenti:
un sottosistema esperti a costo **letteralmente zero** (byte *e* calcolo) darebbe **19,2 t/s**; la
speculazione con bozza perfetta **17,0**; azzerare l'intera tassa del contesto **16,2**. La somma
onesta di tutto ciò che è vivo sta intorno a **17,5**, esattamente come `COMPOSIZIONE_PIANO.md`
aveva anticipato giorni fa.

### Che cosa resta davvero aperto

1. **Il fronte bolle (39,3% della parete) è SOSPESO, non chiuso.** È l'unico item abbastanza grande.
   Il verdetto «il costo migra 1:1» viene dal braccio r44, che r45 ha poi invalidato. **Va
   riconfermato su un braccio non contaminato** — e la strada per farlo non è R1 (rotta), ma una
   misura che discrimini «attesa evitabile» da «lavoro GPU osservato» senza toccare il calcolo.
2. **Il bug dell'indice −1** (`ops.cpp:4831`, testa Markov del drafter al taglio del reasoning):
   esiste, è riproducibile, e in un cammino senza bounds-check sarebbe silenzioso. Il progetto ha
   già l'idioma `voci fuori tabella`: va esteso a quella lookup.
3. **Due esposizioni latenti** (alias d'arena, ingressi utente riscritti con memcpy nudo), oggi
   mascherate dai ~35 drenaggi di stream per grafo.
4. **`TOPK_FUSO` non ha testimone operativo**: leva non verificabile se non dal manifesto.
5. Il binario **stampa a ogni corsa una raccomandazione falsificata** (`cache-esperti.cu:8301-8303`).
6. **Contraddizione mai riconciliata**: pendenza 0,431 ms/fwd/1000ctx (turno 32) contro 0,1456 (e35).

### Regole nuove, da applicare da subito

- **Verificare che il bersaglio di una leva esista nel banco scelto**, prima di lanciare: una leva
  che dipende da `mean_len` va misurata dove `mean_len` è quello vero (costo dell'errore: sei corse).
- **Una leva provata solo sul banco corto non è stata provata sulla transizione di fine-reasoning**,
  che in produzione c'è sempre.
- **Prima di usare lo SHA come cancello, misurare che il banco riproduca** con due lanci di
  controllo: costa due corse e restituisce il cancello più economico che esista.
- **Ri-ancorare il riferimento ogni tre bracci**; e trattare **cambio di fase VRAM sotto 100 ms** e
  `warmup_resets` come indicatori di salute della sessione, su ogni corsa.
- **Non si ricostruisce un comando: si esegue lo script che l'ha prodotto.** E **non si aggiornano
  gli hash attesi** di uno script per far passare un cancello d'identità — estenderlo con un
  parametro a difetto invariato invece è lecito.
- **Il cancello di qualità non è un sostituto del cancello di identità**: due testi entrambi ottimi
  ma diversi fra loro sono il sintomo, non l'assoluzione.

### Configurazione SOTA aggiornata

Aggiungere `LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1` alla configurazione di riferimento (testimone da
grep-are: riga **`porto-cb: … down_tardi=1`**, *non* `cache-esperti:`). Restano al difetto:
`FORK_STADI`, `TOPK_FUSO`, `OVERLAP_BATCH_MAX` (=3), `SCHED_CPU_BUFT_MAPPED`.

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

---

## 9. ADDENDUM 30/8 — occupazione GPU nelle bolle: il fronte sync si chiude, il fronte vero si apre

Misura in sola lettura sui due DB nsys del 24/8 (33k e 102k, `mode=ro`), aritmetica a UNION
clippata (non somma dei kernel), calibrata contro gli artefatti e35/e36 allo 0,001%.

| | 33k | 102k |
|---|---|---|
| parete decode | 22.733,5 ms | 24.191,8 ms |
| GPU attiva (union kernel+memcpy+memset) | **61,13%** | **60,67%** |
| bolle GPU vere | **38,87%** | **39,33%** |
| finestre `cudaStreamSynchronize` (union) | 18,78% parete | 18,78% parete |
| **GPU attiva DENTRO le finestre di sync** | **93,16%** | **94,10%** |
| GPU ferma dentro il sync, in quota parete | 1,28% | 1,11% |

**Verdetto pre-registrato: >90% => il fronte «sync = overhead» si CHIUDE su dati puliti.**
Il `cudaStreamSynchronize` e' l'host che osserva lavoro GPU: la conclusione del braccio r44
(contaminato dal baco R1) e' confermata per via indipendente. Caveat dichiarato: il 93-94% e'
pesato sulla durata ed e' bimodale — l'1,6% delle sync (le lunghe) pesa l'88-93% del tempo.

**MA la premessa dell'86% host-bound non e' riproducibile da nsys**: il sync e' il 18,78% della
parete, non 50,5%; l'host dentro QUALUNQUE API CUDA e' il 44%. I contatori applicativi di
`sched-profilo` misurano un'altra grandezza. E le finestre di sync spiegano solo l'1,1-1,3%
della parete di GPU ferma: chiudere quel fronte non compra quasi nulla.

### Il fronte vero: la GPU aspetta il ramo CPU

Bolle >=20 us = 5-6% del numero ma **88,5-88,7% della massa**. I tre siti gia' noti fanno il
64,5-64,9% della massa, tutti adiacenti a MEMCPY, tutti a dispatch nuovo. E la ripartizione
dello stato host dentro le bolle dice la cosa nuova:

- host dentro una API CUDA: 35,5-36,2% della massa di bolla
- **host FUORI da ogni API CUDA: 64%** = **25,1% della parete intera**

**Sito n.1 (35% della massa, ~21 occorrenze/forward, 14,3-14,9 ms/fwd)**: `quantize_q8_1` ->
`mul_mat_vec_q_moe_maschera` -> **silenzio totale (host: zero chiamate CUDA)** -> H2D di 64/96 KiB
su stream 14 -> sync. Il silenzio **scala col payload** (64 KiB -> 723 us mediani; 96 KiB ->
1036 us; rapporto 1,44 contro 1,50 dei byte; CV 0,62-0,65): non e' latenza fissa, e' lavoro
proporzionale al carico che accade altrove. Lettura: **la GPU finisce i suoi 4 esperti mascherati
e aspetta i 2 del ramo CPU. L'overlap non sovrappone.** Il 66-70% della massa di bolla e'
bracketata dal traffico di stream 14 (la corsia host<->device), i cui trasferimenti costano 159 ms
su 22,7 s: il trasporto e' gratis, l'attesa attorno no.

### Tetti misurati (216 forward per DB)

```
forward attuale               105,25 / 112,00 ms
senza TUTTE le bolle           64,34 /  67,95 ms   = x1,64   (dal punto SOTA: ~21,8 t/s)
senza le sole bolle stream-14  76,49 /  82,66 ms   = x1,36   (~18 t/s)
```

### Cio' che i DB non possono decidere (dichiarato, nessuna stima di ripiego)

Tracciamento CUDA-only: niente OSRT, niente campionamento CPU. Per il 25,1% di parete con GPU
ferma e host fuori da CUDA **non si distingue «l'host calcola» da «l'host attende i worker»**.
Le due corse che decidono, entrambe singole: (a) nsys `--trace=cuda,osrt` (o campionamento CPU)
=> sceglie fra *velocizzare la lane* e *ribilanciare la quota*; (b) `--gpu-metrics` => dice se
il 61% di isole «busy» e' saturo o nasconde a sua volta margine.

Converge con la diagnosi dell'11/8 («il join e' il 73%, la finestra e' un solo split»), ora
quantificata al sito e con la prova di scala. Script di analisi nello scratchpad di sessione
(b00..b50), riusabili.
