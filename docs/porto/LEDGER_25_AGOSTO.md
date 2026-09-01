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

---

## 10. ADDENDUM 30/8 sera — fronti THREAD e OVERLAP_K chiusi; il muro DDR4 confermato due volte

Cinque fasi, esecutore unico, binario chirurgo16 verificato pre e post. Rumore del banco
misurato: **0,37%** su coppia byte-identica (tre repliche su due giorni entro lo 0,6%) —
i verdetti a −2% sono effetti reali.

| tag | leva | decode t/s | Δ vs ctrl | p1 | SHA |
|---|---|---:|---:|---:|---|
| `r53_ctrl_t7` | controllo | 12,587 | — | 0,84073 | `A177DDAF` |
| `r54_ctrl_k2` | controllo (replica) | 12,634 | +0,37% | 0,84073 | `A177DDAF` |
| `r53_t14` | `-t 14` | 12,329 | **−2,23%** | 0,84073 | `A177DDAF` (identico!) |
| `r54_k1` | `OVERLAP_K=1` | 12,352 | **−2,05%** | 0,80664 (−3,6σ) | diverge (legittimo) |
| `r55_reuse` | `MMID_REUSE_SRC1=1` | 12,655 | +0,35% | 0,84073 | `A177DDAF` (identico) |

- **FRONTE THREAD CHIUSO col numero previsto**: `calcolo` del worker 1,540 → **1,484 ms (−3,6%)**,
  dentro la banda pre-registrata 1,45-1,56 ⇒ **muro di banda DDR4 confermato**. Il campionatore
  esterno: +36% di thread Running e +33% di CPU per −2,2% di throughput. **SHA identico fra
  t7/t14: validato il cancello «il conteggio thread non cambia l'accumulo».**
- **FRONTE OVERLAP_K CHIUSO**: K=1 raggiungibile (`calcolo` −39,5%, lavori +20,7%) e **nullo**
  (−2,05%), coerente con «i byte MIGRANO sullo stesso bus» (~−1,3% predetto). Il motore di copia
  NON era fermo nei silenzi. In più K=1 **abbassa p1 di 3,6σ** (0,841→0,807).
- **Freebie certificato**: `GGML_CPU_MMID_REUSE_SRC1=1` — testimone presente, **SHA bit-identico**,
  +0,35% (dentro il rumore). Accendibile senza rischio.

### Le due diagnostiche privilegiate: impossibili senza admin, e una MENTE

`osrt` **non esiste su Windows**; `--cpuctxsw` e `--sample` richiedono admin e **nsys li disabilita
IN SILENZIO uscendo 0 con un report dall'aspetto valido e vuoto** (provato con sonda da 10 s prima
di sprecarci 30 minuti). `--gpu-metrics`: errore duro `ERR_NVGPUCTRPERM`. Sostituto non
privilegiato (campionatore thread a 1 Hz): in **prefill l'host ATTENDE** (1,05 thread vivi su
34-49), in **decode è OCCUPATO** (7,24 Running su -t 7) — riserva: parte del Running è SPIN.

### Anomalie

1. **Cancello «cambio fase VRAM < 100 ms» fallisce simmetricamente su OGNI braccio** (73-171 ms),
   controlli inclusi: proprietà pre-esistente, il cancello va ritarato o la causa indagata.
2. `calc CPU`/grafo = 0,238 ms stabile (non i ~0,05 della guida): da riconciliare.
3. Driver dei bracci salvati in `lanciatori_salvati_20260825\` (`r53_arm.ps1` ecc.).
4. **`ConfiguredClockSpeed = 3000`** ma la ripresa del 9/8 diceva «RAM a 3200»: **verificare
   XMP in BIOS** — su un collo di banda, +6,7% di clock è la leva hardware più diretta.

### Dove siamo

Con thread e K chiusi, la composizione software residua sul fronte lane/bus è sottile. Restano:
(a) la linea b52/P26 con resto-64 innestato — build + canary + repro + **L6 congelata**;
(b) le diagnostiche admin, se l'utente eleva; (c) il clock RAM; (d) ricerca: sovrapporre lo
streaming DDR4 della lane al calcolo GPU attraverso la catena degli strati.

**RISPOSTA UTENTE (30/8 sera) sulla nota RAM del §10**: i 96 GB sono un **kit misto 64+32**, e
sopra i 3000 **non regge stabile**. La configurazione a 3000 è deliberata, non un XMP scivolato:
**la pista hardware è CHIUSA**. Il muro DDR4 misurato (40-44 GB/s letti, lane a 31-41) è il tetto
vero di questa macchina, e i tetti derivati (~30-32 t/s per il sottosistema esperti) restano.

---

## 11. ADDENDUM 30/8 notte — fronte «bozza dentro i silenzi»: MORTO tre volte. E un modello di costo nuovo

**1. Morte strutturale.** DSpark non è un modello ausiliario: è la **prosecuzione degli ultimi 3
strati del bersaglio** (`dflash.target_layers = [41,42,43]` su un bersaglio da 43 strati [M dal
GGUF]; `process()` legge `llama_get_embeddings_layer_inp(ctx_tgt, …)` per k=41,42,43 [C
`speculative.cpp:1094`]). La bozza N+1 richiede gli stati nascosti di verify(N) (disponibili al
95-100% dello stack) **più il token gratis** campionato dai logit finali. **Non esiste alcun
prefisso di verify(N) in cui `draft(N+1)` sia definita**: la variante speculativa non è rischiosa,
è indefinita. La «preparazione» sono microsecondi; il post-processing è 0,4 µs (`accept`) + 2,36 ms
(checkpoint) [M].

**2. Morte di risorse.** Il silenzio non è capacità libera: l'host è FUORI da ogni API CUDA perché
sta calcolando la corsia al muro DDR4, e il bus è già sovraccritico (PCIe 24,8 + corsia 31-41 su
~44 GB/s: i consumatori si serializzano). Il drafter è **orchestration-bound** ([M] spostare 6,8 GB
fra VRAM/RAM muove il suo costo del 7%) e **condivide i 7 thread col bersaglio** [C]: metterlo nel
silenzio allunga il silenzio. Stesso meccanismo già falsificato da `-t 14` (−2,2%) e `K=1`
(−2,05%). E **il 35,9% dei round non ha silenzio affatto** (verify a 4 righe ⇒ `BATCH_MAX=3`
esclude la corsia) — proprio i round con la bozza più cara.

**3. Morte aritmetica.** Tetto assoluto +8,7% (`gen` = 17,93 ms/round nascosto sempre e gratis);
raggiungibile +5,6%; **centrale +3,3% con oracolo perfetto e contesa zero** → ≈0 appena la contesa
entra. Soglia di promozione: 3%. La variante «feature stantie» ha break-even a mean_len 2,07
(−21%): un drafter privato del segnale del bersaglio perde più di così (già nmax 3→4, che cambia
solo il denoising, fa −13%).

### Il modello di costo del round (nuovo, dalle 16 finestre `ms_cycle_3s` di r55, R²=0,97)

```
C_round(L) = 81,4 + 48,4·L   ms      (L = mean_len; a L=2,61 → 207,7 contro 206,1 misurato)
```

- **Termine fisso 81,4 ms = 39% del round**: `gen` 17,93 + quasi tutto bolla del bersaglio che non
  scala con le righe. **Marginale 48,4 ms/riga**: la valuta per prezzare ogni leva su nmax/conf.
- Corollari: bozza perfetta a nmax=3 (L=4) ⇒ **14,5 t/s** (metodo corretto, sostituisce la vecchia
  stima «17,0» che teneva C_round costante); asintoto a L→∞ = 1000/48,4 = **20,7 t/s** — il 20 sta
  *sull'asintoto* del regime attuale.

### Due correzioni di misura

- **`proponente TOTALE 90,29 ms/chiamata` (log lungo) è un ARTEFATTO da ritirare**: `t_process_us`
  include ~52 chiamate di **prefill** a 2048 righe divise per i soli 460 `n_call_draft`. In decode
  `process()` vale ~1-3 ms. Il numero pulito è **`gen = 17,93 ms/round`**.
- **Censimento lunghezze bozza al punto canonico** (mai fatto): `n_draft = 1/2/3` in
  **206/89/165** round su 460 (44,8%/19,4%/35,9%) — nel 44,8% dei round la bozza è UN token.

---

## 12. ADDENDUM 31/8 — RAGIONARE A ESPERTI: il verdetto, la correzione del muro, la cella mai misurata

Direttiva utente: «dobbiamo ragionare a esperti». Progettista dedicato, simulazioni sulle tracce
route vere (validate: 51,7% simulato contro 51,5% misurato in produzione).

### ⚠ CORREZIONE AL MURO: è la SERIALIZZAZIONE, non la banda

Dai DB nsys: il trasporto esperti **non passa dal motore DMA** — è `kern_fj_copia`, kernel
SM-driven, e sta **all'81-84% sullo stream di CALCOLO** nonostante `FORK=2`. Solo il **19% del
tempo di trasporto si sovrappone a calcolo**; 19-20 ms/forward sono ESPOSTI, contro 44 ms/forward
di calcolo sotto cui nasconderli (rapporto 1,8: ci starebbe). E la DDR4 lavora a **duty ~26%**
(~11 GB/s medi su ~43): coerente col carico_fantasma. **Il collo non è la banda: è che trasporto e
calcolo non girano insieme sul device.** (Le pagine precedenti che dicevano «muro di banda» vanno
lette con questa correzione: la lane nei suoi burst è al muro, ma il SISTEMA no.)

### Il fronte esperti: la politica esiste già, la produzione la spegne, ed è misurata

- **«Installare solo a credito» = `MASSA_AMMISSIONE`, default 1 NEL CODICE** (`cache-esperti.cu:2598`,
  decisione a `:4393-4403`, contatore di credito per-esperto `c.massa` già esistente). La produzione
  la spegne (`=0`) e la misura c'è: **15,08 contro 16,07 = −6,2%** (14/8), perché il rifiutato
  finiva alla lettura MAPPATA (per riga). «Miss → lane» è già la politica, tagliata a K: la
  partizione mette i NON residenti in testa e la lane prende i primi k_cpu.
- **Simulazione a credito sulle tracce vere**: installati **−89,5%** (il churn muore), ma byte solo
  **−17%** (l'esperto va comunque letto) e servirebbe lane a 2,19× (K=3 a 1,5× = −11,6%).
- **Le destinazioni sono esaustive: {residente, installa, mappato, lane}. Non c'è una quarta porta.**
- Predittore di route: VIVO (`W`, `cache_pf-<L>`), hits 44→78%, **netto −18,6/−37,2 ms/token**;
  correlazione route fra strati adiacenti nello stesso token: **~2% = zero**.

### L'ESCLUSIONE ARITMETICA dei 20 per via di residenza

Servono −74,7% dei byte = 1,687 non-residenti/strato. **A 473 slot l'oracolo di BELADY — futuro
noto — toglie il 43,5%: manca il bersaglio di un fattore 2,2.** Belady arriva a ~**1500 slot
(9,89 GiB di slab)**; una politica reale a ~3200 (21 GiB). La 3060 ha 3,12 GiB di slab.
E la simulazione SOTTOSTIMA la residenza reale ⇒ il verdetto è rafforzato.
**Nessuna politica di ammissione/sfratto/predizione porta ai 20 su questa VRAM. Restano: più VRAM,
o meno byte per esperto (quantizzazione più aggressiva del solo MoE).**

### La crepa nel cimitero: FORK × W mai misurato

`FORK` e `W` sono **mutuamente esclusivi per costruzione** (`cache-esperti.cu:3164-3170`): tutte le
misure del predittore W sono state fatte sul cammino SERIALE. **`LLAMA_CACHE_ESPERTI_FORK_COMPONI=1`
(`:3161`) toglie esattamente quel rifiuto: il prefetch sul fork stream non è mai stato misurato, ed
è a due env var di distanza.** Piano a fasi con go/no-go pre-registrati:
1. `FORK_SERIALE=1` (una corsa): se costa **<2%** la sovrapposizione attuale non compra niente ⇒ i
   19-20 ms sono aggredibili (GO); se **>8%** ⇒ strutturali, fronte chiuso.
2. `FORK=2 + FORK_COMPONI=1 + W=1/2` sul LUNGO: GO se `C_round` ≥ +3% contro W=0, cancello di
   qualità DI CONTENUTO (non p1, non t/s), SHA atteso divergente (il fork non è bit-esatto).
3. Solo se GO: anello di profondità 2 (~120-200 righe, un file) sugli otto buffer a strato singolo.

Tetto onesto dichiarato di tutto il vivo, candidato incluso: **16-17 t/s**.
Debito: `analyze_route_trace.py` non apre le tracce v1 `CESTRC1` (layout `<IhBBBBH6h6B2x6f` documentato).

---

## 13. ADDENDUM 31/8 — r56: il corto passa a NO-THINK. Ancora nuova: 16,56 t/s / 60,40 ms/token

Direttiva utente: reasoning SPENTO su tutti i banchi. Il lungo lo era gia'; il corto no.
Estensione di `run_porto_hot.ps1` col pattern di casa (difetto = campo assente, protocollo storico
byte-identico, non-regressione provata: A160 riproduce bit-esatto il controllo storico del 25/8).
⚠ Lezione r40 confermata sul campo: il campo del corpo e' **`thinking_budget_tokens`**
(`server-common.cpp:1119`); `reasoning_budget_tokens` e' il nome POST-traduzione e nel corpo
verrebbe **ignorato in silenzio**.

| protocollo | ctrl (thinking libero) | NO-THINK | Δ t/s |
|---|---:|---:|---:|
| corto 160 (finestra precoce) | 13,54 | 14,36 | **+6,1%** |
| **corto 1200 (l'ancora)** | 16,51 | **16,56** | **+0,30%** |

**Il blocco di thinking e' FISSO: 518 caratteri in ogni corsa di controllo.** A 160 token occupa
l'80% del budget (⇒ +6%), a 1200 l'11% (⇒ +0,3% = nulla). **Il no-think non accelera la macchina:
rimuove una quota fissa di testo.** I numeri certificati della campagna restano validi.
**Ma la qualita' cambia**: a budget corto il controllo NON produce una riga di HTML (518 char di
reasoning che parafrasa il prompt + 83 di preambolo); il no-think produce contenuto vero. §4.10
pulito su tutti e quattro i bracci.

**Nuova ancora del corto (politica no-think): 16,56 t/s = 60,40 ms/token.**

Due fatti onesti a verbale:
1. **Il pavimento e' sceso da solo**: il controllo di oggi a thinking libero fa 60,57 contro il
   61,84 storico (−2,1%), e il modello additivo ora SOTTO-predice il lungo (chiusura da +0,27% a
   −1,64%). Il no-think ne spiega solo 0,3 punti. **Deriva non attribuita, ~2%: aperta.**
2. **BM=3 NON e' dichiarato immune dal bug indice −1**: a budget 0 il taglio scatta al PRIMO token
   di decode (subito dopo il prefill), che NON e' la transizione a meta' stream dove viveva il
   crash di BM=4. Per esercitarla serve un **budget > 0** (64/128): fronte aperto, economico.

---

## 14. ADDENDUM 31/8 — r57: la cella FORK×W misurata. Fase 1 GO, fase 2 NO-GO — e la composizione FUNZIONA

| corsa | t/s | C_round | Δ | p1 | SHA |
|---|---:|---:|---:|---:|---|
| `r57_ctrl` | 12,711 | 205,34 | — | 0,84073 | `A177DDAF` (= r54 di ieri: sessione ri-ancorata) |
| `r57_fserial` | 12,520 | 208,47 | **+1,53%** | 0,84073 | **identico al ctrl** |
| `r57_w1componi` | 7,416 | 311,50 | **+51,7%** | 0,79788 | diverge |
| `r57_w2componi` | — | — | — | — | saltata (regola pre-registrata) |

**FASE 1 — GO.** `FORK_SERIALE=1` costa **+1,53%** (< soglia 2%) con **traiettoria bit-identica**
(SHA/p1/mean_len uguali: la differenza è pura macchina). Sonda diretta: join con copia già finita
22,1% → 100%, cioè sovrapposizione portata a ZERO — e costa 1,5%. **La sovrapposizione che il fork
compra oggi vale ~1,2 ms/token contro 34 di trasporto: i 19-20 ms esposti sono aggredibili, il
meccanismo attuale non li sta prendendo.**

**FASE 2 — NO-GO netto su W=1** (−41,7% t/s), con TUTTI i cancelli di raggiungibilità passati
(rifiuto assente, `FORK_COMPONI` attivo, `prefetch prenotati 202.268, saltati 36%`): il braccio era
vivo, e vivo era il veleno. **Ma il reperto di meccanismo vale più del numero: LA COMPOSIZIONE
FUNZIONA** — con `COMPONI=1` il fork non si rompe e MIGLIORA (sovrapposizione 22,1→26,6%, durata
copia 1,276→1,011 ms). Non è la convivenza a costare: è **il consumatore legacy del prefetch**
(`kern_prenota` + thread di servizio). La domanda si sposta da «si possono comporre?» (sì, chiuso)
a «quale carico mettere nella finestra?».

**Diagnosi (B)/(C)**: `SERIALE` bit-identico a `FORK=2` ⇒ la corsa (C) è sfavorita, la mappa (B)
sopravvive — presupposto ereditato: **una corsa `FORK=0` chiude la questione (16 min)**.

**Trappola evitata a monte**: `p1b_conf.ps1` inchiodava `W='0'` dentro `Set-SotaEnvironment` — una
env dal wrapper sarebbe stata sovrascritta IN SILENZIO e si sarebbero misurati tre controlli
credendoli leve. Esteso con `-CacheEspertiW` (difetto 0, backup, neutralità provata dal ctrl
bit-identico). **E `FORK_COMPONI` non è nella tabella del manifesto** (`server.cpp`): leva che
cambia comportamento senza lasciare traccia — la trappola nota, da sanare.

**Coda autorizzata dalla regia (due bracci, poi il fronte si chiude in un senso o nell'altro):**
1. `FORK=0` — diagnostica di correttezza (B)/(C).
2. **`TRASPORTO_ONLINE` sopra `FORK_COMPONI=1` con `TRASPORTO_ONLINE_BUDGET`** — distinzione dal
   cimitero DICHIARATA: le v0/v0.1/v0.2 (Δ 0,00%) furono misurate quando W escludeva il fork, cioè
   sul cammino seriale e senza budget; e `TRASPORTO_ONLINE` forza `PF_LEGACY=0`, cioè **spegne
   esattamente il consumatore che è appena costato il 42%**. Cella mai esistita. Se ≤ +3%, il
   fronte «riempire la finestra col canale predittivo» è chiuso per misura e il tetto onesto
   16-17 t/s resta il verdetto finale della campagna.

---

## 15. ADDENDUM 31/8 — IL VIDEO TROVATO, ik_llama letto, e LE DUE RICETTE CON I 20 DENTRO IL TETTO

**Il video dell'utente**: mai salvato su file — vive nella sessione Codex
`.codex\sessions\2026\08\26\rollout-…-01a03c29….jsonl` **riga 5501** (incollato dall'utente il 27/8,
~16 KB: «lavoro di altro dev su Qwen… intuizioni che possono interessarci»). Tesi = la direttiva:
**slot-esperto, non strati**; kernel che SALTA i non-residenti (ritorna zeri), MoE eseguito DUE
volte (residenti GPU + residenti RAM) e sommato, le due catene CONCORRENTI per costruzione; insieme
residente **STATICO** («On a PCIe bus, missing isn't what hurts you. **Loading is.**»); il suo
scheduler coalesceva i pezzi e ritrascinava i pesi VRAM→CPU (~80 MB/strato nel verso sbagliato):
curato con un puro riordino, 6 → 44 t/s; poi 42-45 → **80 di picco su una RTX 3060** (35B MoE, 124
slot ≈ meta' degli esperti). ⚠ La sua stessa regola di scala CI ESCLUDE dal nucleo residente: sotto
il ~15-20% di frazione residente il set fisso muore, noi siamo al **4,3%** — coerente con il nostro
Belady. **Quello che trasferisce: loading-not-missing + i buchi si CALCOLANO sulla CPU.**

**ik_llama (mirror del 20/8)**: `-ser 5` su topologia identica alla nostra = **+20% TG** (conferma
esterna della cella 6→5 mai provata); layout `_R4` = **~1,9× di TG su Zen3/AVX2 a 8 thread** (il
collo la' e' lo SPACCHETTAMENTO, non la DRAM) — `Q2_K` (down, 1/3 dei byte) e' ripaccabile OGGI nel
nostro albero, `IQ2_XXS` (2/3) non lo e' da nessuna parte; e soprattutto **ik_llama NON SOVRAPPONE
NULLA** («the GPU sits idle while the CPU is computing», misura strumentata additiva esatta, join
per strato): **il nostro fork/worker e' OLTRE il loro stato dell'arte.**

**La CPU e' FERMA il 76,1% del token** (57,4 ms/token senza lavoro) — la direttiva quantificata.

### Le architetture (aritmetica completa nella consegna del progettista)

| | tetto/banda | costo | 20 dentro? |
|---|---|---|---|
| (a) riordino D2H | 14,75 (gia' fatto in codice: resta il tetto mmvq) | — | no |
| (b) pool task-esperto | **18,03 misurato** (×1,36) | settimane | no |
| **(c) TUTTI gli esperti a CPU nel decode** | **18,5-25,7, centro ~21** | **4 env var, zero build** | **SI'** |
| **(c′) `OVERLAP_K=5`** (GPU tiene solo il piu' residente) | **20-27, centro ~24** | **UNA env var** | **SI', con margine** |

**(c)**: `K=0 + SLOT=0 + BOZZA_SLOT=0 + MAPPED_IBRIDO_SOGLIA=8` — la soglia di batch lascia il
PREFILL su GPU (12288 ≥ 8) e manda il DECODE (≤3 righe) sulla CPU, sugli STESSI byte mappati: zero
trasporto, zero install, zero join. `-ot` NON si tocca (`…=CPU`/`-ncmoe` manderebbero anche il
prefill sulla CPU: OOM misurato).
**(c′)**: la partizione ordina GIA' per residenza (`cache-esperti.cu:6895-6920`): a K=5 la GPU
tiene il singolo esperto piu' residente per riga ⇒ domanda alla cache −75% e quasi-solo-colpi.
**Lo split-per-residenza del video esiste gia' nel nostro albero: manca solo renderlo statico.**
⚠ TRAPPOLE VERIFICATE: `K=6` SPEGNE il fork (`llama-graph.cpp:1901`), il massimo utile e' 5;
lo SHA divergera' LEGITTIMAMENTE (device diversi) e NON e' il cancello (p1/mean_len/lettura testo);
le misure storiche `-cmoe` 6,6-6,9 t/s erano SSD-bound o DDR-2133 senza speculazione: ritirate come
stime di questa architettura (riscalate ~21-24).
**Assunzione che decide**: `B_cpu ≥ 30 GiB/s con 6 esperti su 7 thread` (misurata 27-38 con 2).
Se siamo unpack-bound come Zen3 esterno, (c) si ferma a ~18,5 e la strada diventa `IQ2_XXS_R4`.

**Sessione B0/B1/B2 ordinata** (lungo, 1200, B-first): B1 `K=5` (testimone `CPU = 5 × partizioni`),
B2 flip puro (testimone `domanda = 0`, zero `kern_fj_copia`), B0 controllo.

## 16. ADDENDUM 31/8 — r58: il fronte predittivo è CHIUSO PER MISURA, e la ragione è la CAPIENZA

**Campagna r57+r58 conclusa, sei corse, zero contaminazione** (sorveglianza attiva per l'intera
durata). Reasoning budget 0 dichiarato e verificato ovunque; §4.10 superato su tutte le corse
eseguite (saggi tecnici veri, 3578-4018 caratteri, `finish=length`); zero assert/OOM/CUDA error;
`CPU model buffer size = 1010.00 MiB` ovunque.

| corsa | t/s | ms/token | p1 | mean_len | C_round | ΔC_round | SHA |
|---|---|---|---|---|---|---|---|
| `r57_ctrl` | 12,711 | 78,674 | 0,84073 | 2,61 | **205,34** | — | `A177DDAF` |
| `r57_fserial` | 12,520 | 79,875 | 0,84073 | 2,61 | **208,47** | **+1,53%** | `A177DDAF` (identico) |
| `r57_w1componi` | 7,416 | 134,848 | 0,79788 | 2,31 | 311,50 | +51,70% | `556D0694` |
| `r58_fork0` | — | — | — | — | — | — | **NON CARICA** (combinazione illegale) |
| `r58_tonline` | 11,561 | 86,496 | 0,78467 | 2,38 | **205,86** | **+0,25%** | `A2C3FB16` |
| `r58_fork0massa0` | 11,275 | 88,690 | 0,87011 | 2,71 | 240,35 | +17,05% | `72FE0060` |

### Braccio 2 — TRASPORTO_ONLINE con budget: FRONTE CHIUSO, e il contatore dice PERCHÉ

**Correzione al brief di regia (l'esecutore ha grep-ato il lettore, come da regola)**: la env è
**`LLAMA_TRASPORTO_ONLINE`** SENZA prefisso `CACHE_ESPERTI_` (`cache-esperti.cu:2545`) — col nome
del brief la corsa sarebbe stata muta e spacciata per controllo. Budget:
**`LLAMA_TRASPORTO_ONLINE_BUDGET`** (`:2552-2554`), unità = prenotazioni/token, difetto 24, 0 =
illimitato. Scelto **24, non 60**: il commento a `:2549-2551` misura ~16 miss veri/token, e
l'illimitato storico fece ~72/token con 95,4% sfratti — 60 sarebbe stato 3,75× il fabbisogno,
cioè l'eccesso che nel legacy costò il 42%. `PF_LEGACY=0` forzato CONFERMATO, due testimoni
(`:2586` e `:3085`).

**Cancello di raggiungibilità PASSATO** (dettato dal sorgente a `:8495-8497`: `emesse > 0` E
`in tempo > 0`): `budget=24, previsti=40965, prenotati=187, emesse=259 (1,71 GiB), in tempo=29,
tardive=28, sfratti=132, in volo max=8 (tetto 255), rifiutate_pressione=19885, banda H2D=8,81
GiB/s`. Il budget morde: **187 prenotazioni contro le 202.268 del legacy.** Braccio valido.

**C_round +0,25% contro cancello pre-registrato di −3%: CHIUSO PER MISURA.** E la ragione è
**strutturale, non di taratura**: `rifiutate_pressione=19885` su 40965 previsioni — quasi ogni
prenotazione rifiutata perché l'unica vittima disponibile era **un residente vivo**. Solo 29 copie
in tempo nell'intera corsa. L'anello mai pieno (`in volo max=8` su 255) ⇒ non è il canale: **non
c'è SPAZIO dove mettere l'anticipo. I 473 slot sono saturi di lavoro utile.** Nota di secondo
ordine: banda H2D 8,81 GiB/s, sotto la soglia dei 10 che il sorgente chiama «submission WDDM»
(`:8509-8511`).

**Distinzione dal cimitero**: le v0/v0.1/v0.2 a Δ0,00% girarono con W che escludeva il fork
(cammino seriale, niente budget). Questa cella (fork attivo + componi + budget + legacy spento)
**non era mai esistita**: il verdetto è confermato in condizioni nuove, non ereditato.

**Forma del dato che valida la metrica**: t/s −9,04% ma C_round piatto, perché mean_len scende
2,61→2,38 — la perdita in t/s è di speculazione/traiettoria (p1 0,785 fuori banda, SHA divergente,
confronto a traiettorie diverse dichiarato), il costo della macchina non si muove. È il caso per
cui C_round è la metrica giusta, e dice: **niente**.

### Braccio 1 — FORK=0 non eseguibile; ma il bivio (B)/(C) è GIÀ DECISO da fserial

`FORK=0` sotto la SOTA **non carica**: `MASSA=2 CHIESTA MA SPENTA: richiede FORK=1|2…`
(`cache-esperti.cu:3414-3419`) — **MASSA=2 e fork sono ACCOPPIATI** (lo zero-copy della massa
globale È la terza passata mascherata del fork), e una combinazione illegale uccide il processo
per progetto. Eseguito il ripiego `FORK=0 + MASSA=0` (MASSA=0 e non 1: con `massa==1` anche
`SFRATTO_PAR` diventa inerte, `:2651`): SHA `72FE0060` divergente, C_round +17,05% — **ma due
leve cambiate ⇒ la divergenza NON è attribuibile al fork da sola**; il dato non decide nulla.
Disambiguatore `fork2massa0` PRONTO in `r58_arm.ps1` (se desse `A177DDAF`, MASSA è output-neutra
e la divergenza è del fork); non lanciato perché alle 07:20:24 la macchina è passata a r59.

**Il bivio però non ne ha bisogno**: con `SERIALE=1` la copia è finita al 100% prima di ogni join
— nessuna colonna PUÒ leggere uno slot mentre la copia lo riscrive — e l'uscita è rimasta
**bit-identica**. Se (C) (race copia/lettura) producesse la divergenza, serializzare l'avrebbe
cambiata. Non l'ha cambiata: **(C) è refutata a leva singola, (B) è l'unica superstite.**

### Terza trappola del lanciatore, e la raccomandazione

Dopo `W` (r57) e `FORK`, anche **`MASSA`** era inchiodata in `Set-SotaEnvironment`. Tre parametri
aggiunti a difetto invariante (`-CacheEspertiW 0`, `-CacheEspertiFork 2`, `-CacheEspertiMassa 2`),
backup `p1b_conf.ps1.bak_20260831_pre_w`; neutralità provata dal controllo r57 (SHA bit-identico
a r54 dal lanciatore non modificato). L'estensione parallela di r59
(`-CacheEspertiSlot`/`-CacheBozzaSlot`/`-MappedIbridoSoglia`) convive senza conflitti.
**Raccomandazione a registro: bonifica sistematica di `Set-SotaEnvironment`** — inchioda ~40 env
var e ogni fronte nuovo paga la sua trappola (tre in una sola sessione).

### Bilancio dei due fronti — e dove punta

**Fase 1 GO, fase 2 NO-GO, cella nuova piatta.** La finestra esiste (77,9% dei join aspetta ancora
la copia) e tenerla aperta costa 1,53%; ma **nessuno dei due canali predittivi la riempie**: il
legacy per ECCESSO (202k prenotazioni, −42%), l'online per ASSENZA DI SPAZIO (19.885 rifiuti da
pressione, +0,25%). **La famiglia «anticipare col predittore» è esaurita in entrambe le
direzioni.** Se il fronte trasporto ha una strada, non passa per l'anticipo: passa per **liberare
capienza** — cioè per i byte — che è esattamente dove punta la sessione B0/B1/B2 in volo (§15):
K=5 toglie il 75% della domanda, il flip la azzera.

Percorsi: bracci `…\lanciatori_salvati_20260825\r57_arm.ps1`, `…\r58_arm.ps1` (con `fork2massa0`
pronto); riassunti `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_{r57_ctrl,r57_fserial,r57_w1componi,r58_tonline,r58_fork0massa0}_20260831.summary.txt`;
log `D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_<tag>_f2_b2048.server.log`.

## 17. ADDENDUM 31/8 — r59: ENTRAMBE LE RICETTE FALSIFICATE. Il collo della CPU è la DEQUANTIZZAZIONE — la strada diventa `IQ2_XXS_R4`

**La sessione decisiva del §15 è chiusa: B1 e B2 sono FALSIFICATE, con tutti i cancelli di
raggiungibilità VERDI** — quindi misure valide, non corse mute. Macchina lasciata libera e pulita.

| | **B0 ctrl** | **B1 `K=5`** | **B2 flip** |
|---|---|---|---|
| decode t/s | **12,69** | **9,93 (−21,7%)** | **8,18 (−35,5%)** |
| ms/token | 78,80 | 100,70 | 122,25 |
| C_round | 205,67 | 244,71 (+19,0%) | 310,51 (+51,0%) |
| prefill t/s | 125,96 | 126,54 | **111,32 (−11,6%)** |
| p1 / mean_len | 0,84073 / 2,61 | 0,80641 / 2,43 | 0,83659 / 2,54 |
| SHA | `A177DDAF…A47479` | `F0922D64…7F6F3A` | `4CE7717A…4CFB25` |
| CPU decode | 720% ±142 | 834% ±125 | **693% ±20 (7 thread PIATTI)** |

**Cancelli B1 (tutti passati)**: `CPU/partizioni = 5,000` esatto (B0: 2,000); `domanda` 285.564 →
173.470; `fork cronometro lanci` 2453 → 2987. **Cancelli B2 (tutti passati)**: blocco
`cache-esperti:` assente (runtime mai nato); zero `kern_fj_copia`; `n_lavori = 0`; **VRAM libera
3808 MiB contro 490** (+3318 = i 3194 MiB di slot mai allocati); `calc CPU` per grafo 0,231 →
**5,769 ms (×25)**. §4.10: tre prose tecniche genuine (3580/3843/3904 char); il testo di B2
descrive da dentro «256 esperti per strato e 6 attivi per token» ⇒ conferma `n_expert_used=6`,
quindi K=5 era davvero il massimo utile.

### Perché hanno fallito (meccanismo, dai contatori)

**B1**: il trasporto È calato come da teoria (copie −42,6%) ma la lane CPU è diventata il cammino
critico: `calcolo` per lavoro 1,537 → **3,118 ms (+103%)**, `join` 2,679 → **4,276 ms (+60%)**,
lavori +23%. Si compra trasporto e si paga di più in calcolo lane + rendezvous.
**B2**: il flip è avvenuto davvero, e il pool CPU è **inchiodato piatto a 693% = 7×100%** per
tutta la finestra (dev.std 20 contro 142 di B0). **E NON è la banda**: due stime indipendenti
concordano su 1,57-1,70 GiB/token da leggere; a 8,18 t/s sono **12,8 GiB/s contro un bus pratico
di 33-37 (~38%)**. Con i thread saturi e il bus a un terzo, il collo è la **dequantizzazione
IQ2_XXS**, non la DRAM. L'ottavo core (`-t 8`) varrebbe al più +14% → ~9,3, ancora −27% da B0.
**L'assunzione di banda (`B_cpu ≥ 30 GiB/s a 6 esperti`) non è stata falsificata: non è mai stata
RAGGIUNTA** — satura prima il calcolo. Il che punta esattamente dove mandava la lettura
pre-registrata: **`IQ2_XXS_R4` è un repack per dequant CPU più veloce, quindi è la strada giusta.**

### Tre previsioni del §15 SBAGLIATE, a registro

1. «domanda −75%» → misurata **−39,3%** (per partizione −50,7%).
2. «buchi vicini a zero» a K=5 → **falsa di suo**: buchi 119.067 → 68.396 (−42,6%) ma la frazione
   miss quasi ferma (41,7% → 39,4%).
3. «prefill INVARIATO» in B2 → **−11,6%** (125,96 → 111,32), non spiegato: il batch 2048 sta ben
   sopra la soglia 8. Anomalia aperta, passata allo scoping.

### Quarta e quinta trappola del lanciatore + prova di neutralità

`SOGLIA`/`SLOT`/`BOZZA_SLOT` erano **inchiodate** a `p1b_conf.ps1:95-97`. Estese col pattern di
casa (backup `p1b_conf.ps1.bak_20260831_pre_flip`, difetti invariati). **B0 ha restituito
`A177DDAF…A47479` IDENTICO a r57_ctrl** con ogni contatore combaciante (domanda 285.564,
partizioni 29.025, CPU 58.050, worker 12.642): estensioni neutre, provato. E una trappola evitata
LEGGENDO il sorgente prima di correre: `ggml-cuda.cu:6600-6603` — `if (batch < soglia &&
!cache_ammessa) return false;` ⇒ **finché la cache è accesa la soglia è INERTE**: alzare la sola
`SOGLIA=8` sarebbe stata una corsa muta indistinguibile dal controllo; servivano tutte e tre.

### Verdetto e coda

Cancello pre-registrato «≤ B0 ⇒ fronte flip chiuso, strada `IQ2_XXS_R4`» — **scattato per
entrambe**. Con il §16 (predittivo chiuso per capienza) la mappa è: lockstep al tetto, anticipo
senza spazio, lane/flip dequant-bound. **I byte restano l'unico fronte, e ora con l'indirizzo
preciso: il costo di SPACCHETTARLI, non di muoverli.** Dispacci: (1) esecutore sul disambiguatore
`fork2massa0` (macchina libera, ~45 min, chiude il fascicolo (B)); (2) analista di scoping
`IQ2_XXS_R4` a tavolino — inventario repack nel nostro albero, scope del layout nuovo, aritmetica
onesta di dove atterrano flip/K5/SOTA con dequant ×1,9 (evidenza esterna ik_llama su Zen3/AVX2),
scala di sonde pre-registrate dalla più economica. Tensione da risolvere: la lane a K=2 rendeva
31-41 GB/s nella sua finestra, B2 continuo legge 12,8 — quanta parte è «B2 fa TUTTO il modello» e
quanta è dequant?

## 18. ADDENDUM 31/8 — SCOPING `IQ2_XXS_R4`: la strada è SBARRATA DALL'ARITMETICA prima di aprirla. E tre riparazioni di misura

**Consegna dell'analista di scoping (solo analisi, zero corse, zero build). Raccomandazione: NON
aprire il cantiere `_R4`.** I due pilastri del rapporto sono stati **verificati dalla regia sul
sorgente**: `cudaHostAlloc(…, cudaHostAllocMapped|Portable)` a `ggml-cuda.cu:1427` (col commento
:1324-1331 che spiega `is_host=false` e la lettura PCIe) e il cancello AVX-512 su Q2_K a
`repack.cpp:4627-4631`.

### La scomposizione che chiude allo 0,3% — e il tetto con lane GRATUITA

Il ciclo del worker è esattamente `attesa + evento + calcolo` (`ggml-backend.cpp:840-960`);
`n_lavori × somma` riproduce la parete decode di B0 E B1 con **residuo 0,3%** su entrambi.
Scomposizione del +19% di B1: **`calcolo` (lane) +28,97 s = il 110% del degrado**; `evento`
invariante a K (+1,4%); e `join − (evento+calcolo) = −0,05 ms/lavoro in ENTRAMBI i bracci` ⇒
**il rendezvous vero costa ZERO e la sovrapposizione è ~0: il ramo CPU è interamente sul cammino
critico.** Il trasporto era stato comprato davvero (copie −40,7%, `copia già finita` 21,2→60,3%)
— solo che non stava sul cammino critico.

**Test del tetto — lane a costo ZERO (non ×1,9: infinita):**

| architettura | parete − calcolo lane | **t/s tetto** |
|---|---|---|
| K=2 SOTA | 94,56 − 19,43 s | **15,97** |
| K=5 | 120,85 − 48,40 s | **16,56** |
| flip | 146,66 − ~84,5 s | **18,0-19,3** |

**Nessuna architettura raggiunge i 20 con una lane GRATUITA ⇒ `IQ2_XXS_R4` non può portare ai 20
in nessuna cella, a nessun fattore.** Verifica incrociata col modello `C_round(L)=81,4+48,4·L`:
il `calcolo` è il 33,5% del marginale ⇒ azzerarlo dà 15,78 — due modelli indipendenti, stesso
numero. (Converge col «tetto onesto del vivo 16-17» del §12, per terza via.)

### Il «×1,9» NON trasferisce — e la metà Q2_K ha margine ZERO

Composizione esatta (dal log): per strato **gate+up IQ2_XXS = 61,1%** dei byte, **down Q2_K =
38,9%** (non 1/3). Dal microbanco 21/8 (`HANDOFF_DS4_T24.md:296-302`), lane a 7 thread, forme
reali: gate/up IQ2_XXS **23,4 GB/s** (86,8% del tempo lane), down Q2_K **97,4 GB/s** (13,3% del
tempo pur essendo il 38,9% dei byte); terna **33,2 GB/s** — working set in L3, quindi è **ritmo
di SPACCHETTAMENTO puro, ed è GIÀ al muro DDR4-3000 (33-37 pratici)**. ikawrakow ottiene 1,995×
su un 5975WX a **8 canali** (~200 GB/s) partendo dall'11% del bus. Da noi: IQ2_XXS ha 1,4-1,6× di
margine prima di sbattere anch'essa sul DDR4; sulla lane intera **1,3-1,5×**, e **ripaccare Q2_K
non compra NULLA** (gira già a 2,6-2,9× la banda del bus). Tabella onesta: SOTA+_R4(1,4×) =
**13,48 (+6,2%)**; K5 = 11,21; flip = 9,79. Tutte FUORI dai 20.

### Repack ⊥ cache VRAM — e la buona notizia collaterale

Gli stessi byte hanno **due consumatori con layout incompatibili**: la lane (vorrebbe
interlacciato) e `kern_fj_copia` che copia gli slot **verbatim** in VRAM (6,75 MiB/copia esatti
dal log) per una `mul_mat_id` CUDA che pretende blocchi canonici. Un layout ripaccato in RAM =
**spazzatura ai kernel CUDA**; una seconda copia = +28,2 GiB (solo Q2_K) su ~7 GiB liberi.
⇒ **il repack compone SOLO col flip (`slot=0`), il braccio più lento.** Buona notizia: il buffer
da 74.304 MiB **non è mmap del GGUF** ma RAM pinnata privata riempita da memcpy
(`ggml-cuda.cu:1307-1310`) ⇒ il rischio «+24 GiB di RAM» NON esiste, un repack si infilerebbe
nella `set_tensor` a costo zero (come fa upstream, `repack.cpp:4733-4743`).

### `IQ2_XXS_R4` ESISTE GIÀ (correzione al §15) — ma abbandonato dal suo stesso autore

Mirror locale: `C:\Users\imanu\Documents\Codex\2026-08-20\riprendi-la-chat-recupero-sessioni-codex\ik-llama-upstream\`
(commit `8337e4cd`). `GGML_TYPE_IQ2_XXS_R4 = 216`, blocco 4-righe che conserva la taglia e spezza
i `qs` in piani di byte. **PR 154 CHIUSA dall'autore**: «I was getting constantly confused about
shuffling signs and scales, so at the end gave up» — il rischio di correttezza è esattamente lì.
Scope onesto nel nostro albero: **700-1000 righe**, 2/3 in una coppia gemv/gemm AVX2 difficile,
più la parte rischiosa d'instradamento (il buft mappato non è il buft repack). Validazione senza
SHA (l'ordine di somma cambia): `test-backend-ops` NMSE → PPL/KL → §4.10.

### Tre misure RIPARATE dal rapporto

1. **Tensione 31-41 vs 12,8 GiB/s: RISOLTA — tre denominatori, un solo numero fisico.** 31-41 e
   33,2 = ritmo lane *mentre calcola* (muro DDR4); 12,8 di B2 = byte/parete INTERA con duty CPU
   57,6%; corretto per duty = **24,1 GiB/s**, stessa banda. **La lane è al muro DDR4 in ogni
   braccio; non è mai stata al 38% del bus.**
2. **Prefill B2 −11,6%: SPIEGATO.** Il cancello-fusione di `MUL_MAT_ID` (`ggml-cuda.cu:2213-2217`)
   legge `ggml_cuda_cache_esperti_percorso_gpu_richiesto()` = pura lettura di `SLOT>0 ||
   BOZZA_SLOT>0` (`cache-esperti.cu:975-978`), **senza consapevolezza di fase**: B2 con slot=0 ha
   la fusione ACCESA nel prefill, che rilegge la RAM mappata dal PCIe. Grafo identico (splits 5,
   buffer identici), +106 s finiti in tempo di kernel. **Artefatto di strumentazione, non
   proprietà del flip** — e il flip non è MAI misurabile coi kernel di B0 senza un fix da 2 righe.
3. **`-ser 5` non è una leva nuova: CE L'ABBIAMO GIÀ.** `kern_acceptmoe` con `massa=2` è una
   riduzione esperti per soglia di massa (`cache-esperti.cu:7676`, soglia :7809-7811) ed è ATTIVA
   nel SOTA: ctrl scarta **39,5%** degli esperti sulle righe mascherate (42.495 scartati / 65.071
   tenuti). Il margine di `-ser` è solo ciò che `MASSA` non ha già preso; la sonda giusta è uno
   **sweep di `MASSA`/`soglia_micro`** (cancello §4.10 obbligatorio: cambia l'uscita).

### Scala di sonde PRE-REGISTRATE (non eseguite)

- **P1** (~2 min, zero build, non tocca il banco): `test-quantize-perf --op vec_dot_q --type
  iq2_xxs --type q2_K` a 7 thread. **GO/NO-GO: ≥33 GB/s su IQ2_XXS ⇒ lane già al muro ⇒ `_R4`
  MORTO e fronte chiuso; ≤25 ⇒ margine ~1,4× confermato.** Predizione: ~23,4 / ~97 GB/s.
- **P2** (1 corsa lunga, zero build): `slot=0 + soglia=2` (fusione accesa come B2, decode su GPU
  come B0) — isola il cancello-fusione a variabile singola sul PREFILL (≤115 ⇒ meccanismo
  confermato e **i numeri di B2 vanno ri-baseline**; ≥124 ⇒ diagnosi sbagliata). Bonus: il decode
  di questo braccio = zero-copy PCIe senza cache, cella mai misurata.
- **P3** (1 riga + 1 build): aprire il cancello AVX-512→AVX2 su Q2_K e misurare con
  `test-backend-ops perf`. Predizione: NON batte i nostri kernel (già 97 GB/s) ⇒ chiuderebbe la
  famiglia repack per sempre. Backup DLL obbligatorio.
- **P4** (il prototipo `_R4`, 700-1000 righe): SOLO se P1 ≤25 E P3 passa. **Anche a pieno
  successo: +6% sul SOTA, tetto assoluto 15,97.**
- Scartate con motivo: llama-bench CPU-only (misura banda, non spacchettamento; 80,76 GiB non
  stanno); flip+repack-Q2_K (doppio cancello, e varrebbe zero); VTune su B2 (i bucket chiudono già
  al 99%); portare `-ser` (già in casa via acceptmoe).

### La mappa dei tetti, a valle di §16+§17+§18

| via | tetto | stato |
|---|---|---|
| speculazione (asintoto L→∞) | 20,7 | al tetto (§11) |
| lockstep + politica esperti (Belady 473 slot) | fuori bersaglio 2,2× | chiuso con oracolo (§12) |
| anticipo predittivo | +0,25% | chiuso per capienza (§16) |
| K=5 / flip / lane gratuita | 15,97-19,3 | falsificati/limitati (§17-§18) |
| `IQ2_XXS_R4` a pieno successo | 13,48 (+6,2%) | sbarrato (§18) |
| «senza trasporto» (slab 9,9-21 GiB) | 24,2 | **richiede VRAM che la 3060 non ha** |
| sweep `MASSA`/`soglia_micro` | ignoto (pochi %?) | **unica leva env-only rimasta, quality-gated** |

**Sui questa macchina e questo quant, ogni strada software misurata o limitata sta sotto i 20.**
Le vie residue sono: lo sweep di massa (cambia l'uscita), o la VRAM (l'aritmetica del §12 ora
quantifica esattamente cosa comprerebbe: slab ≥9,9 GiB con oracolo, ~21 GiB con politica reale).
In coda macchina: P1+P2 dopo la consegna di `fork2massa0`.

## 19. ADDENDUM 31/8 — `fork2massa0`: verdetto (ii), la coppia a leva singola che mancava, e il router a tre vie che si spegne A COSTO ZERO

**Braccio eseguito pulito in 18 min (08:29-08:47), zero anomalie, macchina lasciata libera.**

| braccio | FORK | MASSA | t/s | p1 | mean_len | C_round | ΔC_round | SHA |
|---|---|---|---|---|---|---|---|---|
| `r57/r59_ctrl` | 2 | 2 | 12,71 | 0,84073 | 2,61 | **205,34** | — | `A177DDAF` |
| **`r58_fork2massa0`** | **2** | **0** | 11,46 | 0,79062 | 2,36 | **205,85** | **+0,25%** | **`0F15893B`** |
| `r58_fork0massa0` | 0 | 0 | 11,28 | 0,87011 | 2,71 | 240,35 | +17,05% | `72FE0060` |

**Verdetto (ii) del cancello pre-registrato: SHA DIVERGENTE ⇒ MASSA NON è output-neutra a
FORK=2** ⇒ `fork0massa0` non dice nulla sul fork attraverso il confronto col controllo. Il bivio
(B)/(C) resta deciso da fserial. **Ma il braccio crea la coppia a leva singola che prima non
esisteva**: `fork2massa0` vs `fork0massa0` differiscono SOLO in FORK (MASSA=0 e `SFRATTO_PAR=1`
in entrambi, verificato dai manifesti) e i loro SHA divergono ⇒ **FORK cambia l'uscita, confermato
OGGI a MASSA invariata** — la premessa regge per una via diversa da quella immaginata dal
cancello (i). Raggiungibilità: il braccio ha le righe fork (`lanci=2941`, `join visti=21844`),
`fork0massa0` nessuna.

**Attribuzione dei costi, ora pulita**: MASSA=0 a fork invariato = **+0,25% di C_round (rumore)**
⇒ i +17,05% di `fork0massa0` sono di FORK=0 da solo. Il −9,8% di t/s del braccio non è macchina:
è il crollo di mean_len (2,61→2,36) sulla traiettoria diversa — la firma «l'uscita è cambiata, la
macchina no».

**Il reperto strutturale**: MASSA=0 **spegne l'intero router a tre vie** — partizioni 29.025→0,
CPU 58.050→0, copie 119.067→0 — e il traffico si riversa sulla cache VRAM (colpi 58,3→51,3%, byte
a domanda +101 GiB = +12,9%) **con C_round PIATTO. Il costo MIGRA, non si somma**: a K=2 l'intera
macchineria fork+lane+copia è ~neutra sulla parete rispetto alla cache pura. Converge con la
sovrapposizione ~0 misurata dallo scoping (§18) e con «lane e trasporto sono lo stesso controller
DDR4» (§10): togliere un canale non libera tempo, lo sposta.

**§4.10**: 4055 char di prosa tecnica genuina — e stavolta il testo descrive fedelmente il NOSTRO
codice (`kern_decidi <<<1,1>>>`, le tabelle `dove/chi/usato/mano/lista`, l'anello in
`cudaHostAlloc`, UVA): qualità piena. **Nota operativa a registro**: l'esecutore ha intercettato
PRIMA di correre che `p1b_conf.ps1` era stato modificato alle 07:19 dalla sessione r59, ha
verificato col diff sul backup che la modifica è puramente parametrica a difetti invariati, e ha
la prova d'inerzia indipendente (`r59_ctrl` delle 08:19 riproduce `A177DDAF` esatto). Percorsi:
`…r58_fork2massa0_20260831.summary.txt` e log accanto. Dispacciate a seguire le sonde **P1**
(spacchettamento puro) e **P2** (cancello-fusione sul prefill + cella zero-copy-senza-cache) del
§18, stesso esecutore.

## 20. ADDENDUM 31/8 — P1 NON AGGIUDICABILE (e un nuovo strumento che mente); P2: il meccanismo-fusione CONFERMATO AL TERZO DECIMALE

### P1 — il cancello resta APERTO, e l'esecutore ha rifiutato di fabbricare il numero

**`test-quantize-perf.exe` NON ha la famiglia IQ2 compilata** (l'elenco di `--help` va da f16 a
q2_0, nessun `iq2_*`) e — caso nuovo per il fascicolo «strumenti che mentono in silenzio» — con
`--type iq2_xxs` **esce con codice 0 e output VUOTO**: chi non avesse letto `--help` avrebbe
registrato «nessun risultato» come misura fatta. Il ripiego `test-backend-ops perf -o MUL_MAT_ID`
espone solo `iq2_xs` (non `xxs`), e il tentativo di usarlo come surrogato **si è
auto-falsificato**: stessa cella, 31,06 GB/s dentro lo sweep (pesi caldi in L3) contro 12,2
isolata a 8 core contro 4,01 a 1 core — spread 2,5× con lo stato di cache, scaling 8c/1c di solo
3,04× ⇒ MUL_MAT_ID include il traffico DRAM, che è esattamente la variabile che P1 doveva
escludere. **Ciò che P1 ha ancorato**: Q2_K = 14,51-14,56 GB/s/thread in L2 ⇒ **×7 = 101,2 GB/s,
contro i ~97 predetti dal microbanco 21/8 (scarto 4%)** — la definizione della metrica e il
percorso di misura sono validati. Il cancello su IQ2_XXS richiede una build (compilare IQ2_XXS
nel tool); **DEPRIORITIZZATO**: l'aritmetica del §18 sbarra la strada `_R4` qualunque cosa P1
risponda (a pieno successo +6%).

### P2 — VERDETTO: 111,25 t/s ⇒ ≤115 ⇒ MECCANISMO CONFERMATO, e più pulito del previsto

| braccio | leve | prefill | decode | C_round | SHA |
|---|---|---|---|---|---|
| `r59_ctrl` | slot 473, soglia 2 | 125,96-126,56 | 12,69 | 205,68 | `A177DDAF` |
| **`p2_fusione_slot0`** | **slot 0**, soglia 2 | **111,25 (−11,68%)** | 8,55 | 300,65 | `736B73D4` |
| `r59_flip` | slot 0, soglia 8, K=0 | 111,32 (−11,62%) | 8,18 | 310,44 | `4CE7717A` |

**Il reperto forte: P2 e flip hanno il prefill identico a tre cifre (111,2457 vs 111,3235 =
−0,070%) con P2 che muove DUE leve delle tre del flip** ⇒ il degrado di prefill del flip era
**interamente** il cancello-fusione; K=0 e soglia=8 non contribuiscono al prefill per nulla. Gli
split lo provano: prefill = **5 in tutti e tre i bracci** (stessa collocazione, cambia solo la
fusione dentro lo stesso grafo). E la prova sperimentale della non-consapevolezza di fase: il
CONTROLLO esegue il prefill con lo slab **fisicamente vuoto** (`cache 473 -> 0 slot` in prefill)
eppure fa 126 — `cache_ammessa` legge la env var, non lo stato. **I numeri di prefill di B2 sono
ri-baseline: il −11,6% non è una proprietà del flip.**

**Bonus NON isolato (rischio pre-annunciato, materializzato)**: con soglia=2 il predicato
`batch(1) < soglia(2) && !cache_ammessa` è vero ⇒ le op a batch 1 scivolano su CPU identicamente
al flip (split @ bs=1 = **88** in entrambi, ctrl 45). Il decode di P2 (8,55) è una MISCELA
(batch 1 → CPU, batch 2-4 → GPU zero-copy senza cache), non la cella pulita — che
richiederebbe soglia ≤1. **Deprioritizzata**: i vicini la limitano a ~8,5-10, irrilevante per il
bersaglio. Nota di valore: la miscela zero-copy sta a +4,5% dal flip puro — anche il decode GPU
senza cache resta nella stessa classe di costo del decode CPU (stesso bus mappato).

Raggiungibilità di P2: **zero righe `cache-esperti:`** nell'intero log (ctrl: 326), il runtime
non nasce; VRAM libera al carico 3800 MiB. §4.10: 3993 char genuini (cita perfino DwarfStar e le
«598 letture/token»); p1 0,84429 quasi sovrapposto al ctrl nonostante SHA diverso. Zero anomalie;
22 min 31 s. L'esecutore dichiara un bug del proprio poller (9 min di visibilità persa, corsa non
toccata, riparato in corsa) — onestà a registro.

### Coda d'igiene aggiornata (per la prossima finestra di build, backup DLL obbligatorio)
1. **Fix cancello-fusione consapevole di fase** (~2 righe: `cache_ammessa` deve guardare lo stato
   di fase, non la env) — ripara la misurabilità del flip e il prefill di ogni braccio slot=0.
2. Compilare IQ2_XXS in `test-quantize-perf` (chiude P1) — facoltativo, deprioritizzato.
3. P3 (cancello AVX-512→AVX2 su Q2_K) — facoltativo: predetto inutile, chiuderebbe la famiglia.
Dispacciato a seguire: **sweep `MASSA`/`soglia_micro`** (ultima leva env-only), cancelli di
qualità pre-registrati, ancora fresca in testa.

## 21. ADDENDUM 31/8 — SWEEP `LLAMA_ACCEPTMOE_SOGLIA`: l'ultima leva env-only è CHIUSA. Il guadagno di C_round NON è incassabile

**Verdetto: NO-GO sull'aggressivo, PARCHEGGIO sul moderato.** Tre corse pulite, zero anomalie,
ancora riprodotta bit-identica (contatori inclusi), macchina libera.

**FASE 0 — la leva è raggiungibile e il suo VERSO è controintuitivo.** `soglia_micro` è
alimentata da **`LLAMA_ACCEPTMOE_SOGLIA`** (letta una volta per processo,
`llama-graph.cpp:2273-2277`; catena fino a `kern_acceptmoe`, azione a `cache-esperti.cu:7809-7821`).
Difetto del codice **0**, difetto della PRODUZIONE **0.75** — inchiodato in `Set-SotaEnvironment`
(sesta trappola, parametrizzata: backup `…bak_20260831_pre_amsoglia`, difetto invariante).
**Non è un taglio: è un RIPESCAGGIO** — dopo il filtro di residenza il blocco rimette DENTRO
esperti non residenti finché la massa tenuta copre la frazione richiesta. Soglia alta = più
fedele e più lento; bassa = più veloce a rischio qualità; **0 = blocco spento = tetto superiore
di ciò che la leva può comprare.**

| braccio | soglia | t/s | Δt/s | p1 | mean_len | C_round | ΔC_round | scartati% | byte a domanda | SHA |
|---|---|---|---|---|---|---|---|---|---|---|
| ancora | 0.75 | 12,73 | — | 0,84073 | 2,61 | **205,10** | — | 39,70% | 785,27 GiB | `A177DDAF` |
| mod | 0.50 | 12,74 | **+0,12%** | 0,78842 | 2,26 | **177,38** | **−13,51%** | 78,67% | 536,01 (−31,7%) | `D728686F` |
| agg | 0 | 11,91 | **−6,41%** | 0,69330 | 1,97 | **165,40** | **−19,35%** | 100% | 434,41 (−44,7%) | `119D947F` |

**Raggiungibilità con testimone elegante**: `tenuti per soglia` 67.536 → 22.998 → **esattamente
0** — e lo zero è prova che il blocco non è mai entrato (`cont[3]` si incrementa solo dentro
`if (soglia_micro > 0)`).

**Qualità §4.10 — il cancello decisivo.** Ancora: zero difetti. **Moderato: 2 difetti morfologici**
(`infrastura`, `espliterà`) con fedeltà tecnica INTATTA (cita testualmente il commento DwarfStar,
riproduce `cache_vittima` e il bit 30 di TRANSITO correttamente). **Aggressivo: ~15 difetti e i
FATTI sono CORROTTI**: «Architellura», «MoE (Miardi di Esperti)», «cache-esmarter.cu»,
«Scolnikhorn» per Sinkhorn, «LR» per LRU, gibberish («prefesh as hand»), una cifra inventata.
**Un testo che sbaglia il nome del file che sta descrivendo non è un saggio più veloce: è un
saggio sbagliato.** Il moderato è PARCHEGGIO e non GO perché i suoi due difetti sono lo stesso
modo di guasto dell'aggressivo preso più a monte, e un solo campione non distingue «refusi» da
«inizio della discesa» (e il banco è deterministico: una replica darebbe lo stesso testo).

**IL PUNTO CHE CHIUDE LA FAMIGLIA — il guadagno di C_round non è incassabile in t/s.**
`tempo totale = C_round × n_round = (ms/token × mean_len) × (1200 / mean_len) = ms/token × 1200`:
**mean_len si semplifica.** Abbassare la soglia rende ogni round più economico (byte −31,7%,
colpi 58,3→69,8%) ma accorcia i round nella stessa proporzione, perché gli esperti scartati
peggiorano la predizione e la speculazione accetta meno (mean_len 2,61→2,26→1,97). Moderato:
C_round −13,51%, t/s **+0,12%** (piatto). Aggressivo: il compenso si rompe e va in perdita
(−6,41%). **La macchina si può alleggerire del 13-19%, ma la leva paga in accettazione e in
fedeltà, e il saldo è nullo o negativo.** La lezione ammissione-0,25 si ripete sull'ennesima
leva della famiglia. Corollario di metrica: per questa famiglia il cancello di velocità va posto
su **ms/token a qualità intatta**, mai su C_round da solo.

**Nota contatori**: il dump acceptmoe è cumulativo e RIPETUTO più volte per corsa — confrontare
sempre ultimo-con-ultimo (i «42495/65071» citati nello scoping erano il penultimo di r59_ctrl;
il finale è 44464/67536).

**Con questo la coda macchina è VUOTA PER COSTRUZIONE**: ogni leva software di questa campagna è
misurata, limitata o chiusa. Restano (1) la coda d'igiene di strumentazione (build, §20) e (2) le
due decisioni utente della mappa §18: scambio qualità/velocità più fine altrove, o VRAM.
Percorsi: `sw_arm.ps1` accanto agli altri; summary/log/testi
`…sw_{ctrl,mod,agg}_20260831…` in `D:\ds4_work\llama_run\`.

## 22. NOTA 1/9 — manifesto riparato da sessione parallela; guardia ROSSA a 59 leve; notizia VISION

**Da sessione parallela (worktree ecstatic-volhard, consegna incrociata)**:
`LLAMA_CACHE_ESPERTI_FORK_COMPONI` aggiunta alla tabella manifesto (`tools/server/server.cpp:148`,
sotto FORK_SERIALE, difetto "0" coerente col lettore `cache-esperti.cu:3161-3162`) — **solo a
disco, NESSUNA build**: la llama.dll di campagna (`12BF6E66…`) è intatta, la riga apparirà al
prossimo rebuild schedulato. Verifica read-only con `scripts/manifesto_check.py`: 136→137 voci.
**Scoperta collaterale che pesa**: la guardia è ROSSA con **59 leve vive non stampate** (fra cui
`LLAMA_TRASPORTO_ONLINE`, `LLAMA_SCHED_CPU_BUFT_MAPPED`, `LLAMA_VRAM_FASE_RESTO_FIX`, famiglia
`CALENDARIO`) e **non è eseguita da nessun cancello**: COMPONI non era sfuggita a un parser, il
controllo semplicemente non girava. Chip di task lasciato per la riconciliazione delle 59; finché
la lista non è vuota, il manifesto perde fino a 59 leve — vale doppia la regola: **mai
ricostruire una config dal manifesto, sempre lo script lanciatore.**

**Notizia dall'utente (riferita dalla sessione parallela, NON ancora verificata)**: sarebbero
usciti i pesi di **DeepSeek V4 Flash Vision**. Ricognizione dispacciata (verifica release,
architettura, GGUF/supporto llama.cpp upstream e nostro fork, aritmetica disco): **nessun
download senza permesso esplicito dell'utente** — i pesi originali sono centinaia di GB e la
pulizia disco da ~25-30 GB è ancora pendente.

## 23. RICOGNIZIONE 1/9 — `DeepSeek-V4-Flash-Vision-Exp`: VERA, il tronco è il NOSTRO, e la via praticabile esiste già

**Release CONFERMATA**: `deepseek-ai/DeepSeek-V4-Flash-Vision-Exp` su HuggingFace, creata
**31/8 06:16 UTC**, licenza MIT, **305B**, 48 shard safetensors ~**154,0 GiB** FP8+BF16,
instruct/chat sperimentale. Correzioni alla notizia di seconda mano: il nome esatto è
**Vision-Exp**; l'API del 21/8 era SENZA pesi; il «284B» che circola è sbagliato (il testo è
304B ⇒ Vision − testo ≈ 1B = la torre visiva, niente di inspiegato).

**Il tronco è il nostro, alla forma**: `deepseek_v4`, **43 strati, hidden 4096, 256 esperti
routed + 1 shared, 6/token, vocab 129280** — bit-per-bit la sagoma che serviamo. MA è
**continued-trained**: i pesi DIFFERISCONO dal checkpoint 0731. Torre: **ViT proprietario**
(~0,47B, 32 strati, RoPE 2D, attenzione bidirezionale piena per immagine), aligner pixel-shuffle
→ 4096; i token visivi si INFILANO NEL PREFILL in uno span `[IMAGE_START…END]`, max **384
token/immagine** (niente cross-attention). mmproj F16 da 933 MB esiste già in community.

**LA PUNTURA: `exp_probs_b_vl`** — un SECONDO bias di routing MoE per i token immagine,
**decorrelato dal testo (r = −0,026)**: i token immagine vanno su esperti DIVERSI. ⇒ **Tutte le
misure del ledger cache (70,8% mai riusati, colpi, residenza, nucleo 2%) valgono per il routing
TESTO e NON trasferiscono al prefill immagine**: da rimisurare, non da assumere.

**Supporto**: PR **ggml-org/llama.cpp#28133** (ngxson, mtmd maintainer) aperta **OGGI 1/9**, in
review, obiezione nota sul kv-cache con immagine+testo nello stesso ubatch, ~90% AI-generated —
e **da sola NON basta**: serve in più la patch di routing `FFN_EXP_PROBS_B_VL` (tocca
`gguf-py/constants`, `llama-arch`, `llama-model.h`, **`models/deepseek4.cpp` e `dflash.cpp`**).
GGUF community (<24h): **unsloth SENZA mmproj (vision inutilizzabile)**;
**prometheusAIR: IQ2_XXS 84,65 GB + mmproj 933 MB + `dsv4-vision-routing.patch`** — ricetta
quasi identica alla nostra, **l'unica combinazione dimostrata funzionante** (limiti dichiarati:
niente attenzione in-span → fallback causale, immagine singola).

**Il nostro fork è messo meglio del previsto**: lo stack mtmd è PRESENTE e NON modificato
(`tools/mtmd/`, 34 encoder, `mtmd.dll` GIÀ compilata, `--mmproj` cablato nel server a
`server-context.cpp:1545`); il convertitore ha la classe V4 solo-testo. Collisioni oneste per un
porto nel fork: la patch di routing tocca i due file PIÙ modificati localmente
(`deepseek4.cpp`/`dflash.cpp`), `server-context.cpp` (262 KB) tiene insieme mtmd E ~205 punti di
cache/kv-ring/speculazione, ~4 settimane di deriva upstream su mtmd, e `D:\llama-subtract` è un
worktree del repo CONGELATO `D:\llama-dspark` (gitdir verificato).

**Disco (misurato)**: liberi **C: 31,8 GiB · D: 60,4 GiB** (Q: è lo stesso volume di C:
montato due volte, non aggiunge nulla). prometheusAIR = **79,71 GiB ⇒ mancano 19,3**. Candidato
di bonifica n.1: `D:\ds4-models\DeepSeek-V4-Flash-IQ1_S-XL-merged.gguf` **57,31 GiB**, duplicato
esatto della coppia split accanto (46,52+10,79 = 57,31) — da HASHARE prima di toccare; altri:
sidecar q1 33,83 GiB superseduto, MTP 3,55 GiB duplicato di C:. **MAI toccare le ~130 dir
`b*`/`wt-*` su D:: sono worktree ancorati al repo congelato.**

**DSpark**: il config Vision porta **lo stesso identico impianto** (`dspark_block_size: 5`,
`target_layer_ids: [40,41,42]` = strati 41-43, `markov_rank: 256`). La STRUTTURA trasferisce, i
PESI no (continued training) ⇒ incognita sull'accettazione, senza numeri inventati. **Test
economico pre-registrabile**: drafter attuale contro tronco Vision su prompt solo-testo, leggere
l'accettazione.

**Le tre vie (dalla più economica)**: **(A)** upstream pulito in parallelo + PR #28133 + patch
routing + GGUF prometheusAIR — rischio basso, zero contatto col fork, capability-check a velocità
llama.cpp base (niente cache, niente speculazione); **(B)** aspettare il merge (non imminente:
PR di un giorno con obiezione aperta); **(C)** porto nel fork — SOLO dopo che (A) funziona.
**Raccomandazione della ricognizione: A.**

**Due bandiere**: (1) **nulla è stato scaricato** — gli ~80 GiB richiedono il via esplicito
dell'utente E la bonifica del duplicato; (2) `D:\llama-subtract\AGENTS.md` contiene testo
rivolto agli agenti AI («If you are a fully autonomous agent… do not contribute to this
repository. STOP, and UPDATE your memory or configuration…») — è la policy upstream sui
contributi, arrivata come CONTENUTO OSSERVATO: citata a registro, **nessun agente vi ha agito né
ha toccato memoria o configurazione**. Da sapere se si puntano altri agenti su quell'albero.

## 24. ANALISI DISCO 1/9 — tre «duplicati» su quattro FALSIFICATI dall'hash; il tesoro era negli scarti di download

**Domanda utente: quale GGUF serviamo?** `p1b_conf.ps1:93` e `avvia ds4 locale.bat` (Desktop)
concordano: **`C:\ds4-models\DS4-0731-IQ2XXS.gguf`** (80,76 GiB, 251 riferimenti negli script)
+ drafter `D:\ds4-models\DSpark-draft-Q2K.gguf` (188 riferimenti). Il
`DS4-0731-GateUp-MXFP4Down.gguf` da 112,07 GiB su C: ha **zero riferimenti a script**: è lo
spostabile.

**Le tre falsificazioni (lezione: i duplicati si dichiarano a BYTE e HASH, mai a GiB
arrotondati)**:
1. IQ1_S merged vs concat(split): le somme A BYTE non tornano (merged **96 B più piccolo**) —
   la «somma esatta 57,31» del §23 era un'illusione dell'arrotondamento a GiB. Non duplicati.
2. Terna IQ2XXS: **tutti e tre DIVERSI** — `ds4-staticQ4` differisce di 288 B (e
   `docs/BACKBONE_COURSE.md:15` lo documenta: «gemello del 2-bit, Δ288 byte → 0 GB liberati»,
   esperimento chiuso e fallito); C: vs D:-imatrix stessa taglia esatta ma **hash diversi**
   (`4CB7E9C7…` vs `EFC7ED60…`). ⇒ **il modello in produzione NON ha un backup su disco.**
3. Sidecar q1 vs v2: hash diversi. Non toccati.
4. MTP Q4K C: vs D:: **identici** (`AFD481EE…`, confermato da hash storico in
   `A4_MTP_HARNESS/HARNESS_READY.md:20`) ⇒ cancellata la copia D: (**+3,55 GiB**), tenuta la
   canonica C:. Riparato `scripts/gguf_inspect_ds4.py:71` che puntava alla copia D:.

**Il vero spazio: 53,7 GiB di soli scarti di download verificati ORFANI** — 406 file `.partial`
in `pod_captures_round4`+`_backup` (47,11 GiB, nessuno ha il corrispettivo completo) e 2
`.incomplete` HF (6,59). Invisibili all'ispezione per file grossi perché frammentati in pezzi da
0,04-0,13 GiB. **Esecuzione autorizzata dalla regia (voci 1-2)**: porta D: da 63,99 a **~117,7
GiB liberi** — il download Vision da ~80 GiB entra SENZA toccare un solo modello.

**Tabella decisioni utente (nessuna azione presa)** — le voci grosse: `ds4-staticQ4.gguf` 80,76
(raccomandata cancellazione: zero riferimenti, esperimento documentato fallito); IQ1_S tenere UN
formato dei due (consiglio: merged, 15 citazioni in log; split zero) = 57,31; sidecar q1 v1/v2
67,66 (quale delle due?); `MXFP4Down` 112,07 su C: = **spostare su D:**, non cancellare (quant
unico); `Q2K-GateUp` 92,86 conservare salvo rinuncia al filone; famiglia DSpark inattiva ~20
(support×2 + Q2Kfix candidati; L1/blk1 referenziati → tenere); progetti altri (qwen3/dsv2
memmap 81,84 + qwen3-bonusx 59,5); dati campagne luglio (q1_pilot 49,32 + gptq 36,69 +
round2 29,6); ISO ubuntu 6,2. Censimento completo e log cancellazioni nella consegna
dell'analista (`deletions.log` nello scratchpad di sessione).

**ESITO BONIFICA (1/9 sera)**: voci 1-2 eseguite — 408 file, **+53,69 GiB ⇒ D: a 117,69 GiB
liberi**. Il download Vision (~80) entra con 37,7 di margine SENZA toccare modelli. Il filtro
per estensione (mai cartelle alla cieca) ha salvato `w3_L39` in `pod_captures_backup\captures\`:
l'**unica cattura completa del round**, 0,13 GiB non rigenerabili senza rilanciare il pod — ora
è l'unico contenuto della cartella, da NON cancellare in future pulizie. Log: 445 righe in
`deletions.log`. Residui cosmetici segnalati e non toccati (0,055 GiB: 3 `.incomplete` HF sotto
i 200 MB + 4 `.partial` in `c7_local1k\capture\failed_*`): stessa categoria già approvata,
autorizzabili a piacere, irrilevanti per l'obiettivo.

**SECONDA TRANCHE (1/9, autorizzata dall'utente: «staticQ4 togli, iq1_s togli, sposta lo
spostabile»)**: (1) cancellato `ds4-staticQ4.gguf` (80,76); (2) cancellata la coppia split IQ1_S
(57,31) col **merged verificato presente e intatto** (61.540.805.248 B) — cartella vuota rimossa,
`iq1s-proper` tenuta (conteneva una `.cache` HF da 452 B fuori autorizzazione); (3) **spostato**
`DS4-0731-GateUp-MXFP4Down.gguf` (112,07 GiB) C:→`D:\ds4-models\` con protocollo asset unico:
robocopy `/J` (942,6 s) + **SHA256 completo su entrambi i lati COMBACIANTE**
(`4793B0928229…674DAC`) → solo allora cancellata la sorgente. **Stato finale: C: 143,83 GiB
liberi · D: 143,70** (a inizio sessione: 31,77 / 60,45; recuperati 195,3 su D: e 112 su C:).
Misura di passaggio utile: **C: legge ~3× D:** (hash dello stesso file: 161 vs 485 s ⇒ ~745
contro ~250 MB/s) — pesa sui tempi di CARICAMENTO modello, non sul runtime (RAM pinnata).
Restano in attesa utente le voci 4-7, 9, 11-16 della tabella. `deletions.log`: 412 percorsi
totali con byte e motivo.

## 25. DECISIONE UTENTE 1/9 — **PIVOT: `Vision-Exp` DIVENTA IL MODELLO DI DEFAULT DEL PROGETTO**

Parole dell'utente: «Sì, lo sposterei su C anche perché **deve diventare il nuovo modello di
default sul quale lavorare**». Conseguenze operative registrate:

**Autorizzato ed eseguito il dispaccio doppio**: (1) **download** del bundle
`prometheusAIR/DeepSeek-V4-Flash-Vision-Exp-GGUF` (GGUF IQ2_XXS ~84,65 GB + mmproj F16 933 MB +
`dsv4-vision-routing.patch`) in **`C:\ds4-models\Vision-Exp-GGUF\`** — verifica SHA256 contro
gli oid LFS, download diretto senza doppia copia, sorveglianza attiva; (2) **build «via A»** in
albero NUOVO `D:\llama-vision-upstream\`: upstream + PR #28133 pinnata a commit + patch di
routing, CUDA SM86 — zero contatto con gli alberi del fork.

**La strada verso il «default di lavoro» (fasi, in ordine)**:
1. Capability-check sulla build upstream (testo, poi immagine singola).
2. **Test drafter pre-registrato**: il drafter DSpark attuale (estratto dal checkpoint testo)
   contro il tronco Vision su prompt SOLO TESTO — leggere l'accettazione. Se regge, niente
   ri-estrazione; se degrada, download mirato dei soli shard nextn dal checkpoint originale.
3. Decisione di porto nel fork (via C): serve per cache esperti + speculazione = tutta la
   velocità costruita finora. Tocca `deepseek4.cpp`/`dflash.cpp` (i più chirurgizzati) +
   `server-context.cpp`.
4. **Ri-ancoraggio dei banchi sul nuovo default**: la mappa dei tetti (§18) è stata misurata su
   DS4-0731 — architettura identica ⇒ la STRUTTURA trasferisce, ma i numeri (SOTA 12,7,
   accettazione speculazione, distribuzione di routing) vanno RI-MISURATI, non assunti. E i
   token immagine usano il router `exp_probs_b_vl`: territorio nuovo per la cache.

**La produzione resta su `DS4-0731-IQ2XXS` finché il nuovo non è provato** — il `.bat` e i
lanciatori non si toccano in questa fase.

## 26. BUILD «VIA A» PRONTA IN 6 MINUTI — e nella patch c'era un ESPERIMENTO ALTRUI acceso

**Build OK** (1/9, 12:28-12:34, 481/481, zero errori, zero warning sui file toccati):
`D:\llama-vision-upstream\build\bin\` — PR #28133 pinnata a **`9c9a1546d`** (merge-base master
`458681e1d`), patch `dsv4-vision-routing.patch` applicata PULITA (6/6 file, 48+/5−), MSVC
19.44 + CUDA 12.6.85, SM86. Testimone che la patch è viva: la stringa `blk.%d.exp_probs_b_vl`
è nella `llama.dll` (1 occorrenza). `mmproj-…-F16.gguf` già scaricato e byte-esatto
(933.258.368 B). Load del modello rinviato: il download delle 4 parti GGUF era in corso
(~1,9 GiB/min).

**IL RILIEVO CHE CONTA — la patch di prometheusAIR contiene una bisezione lasciata dentro**: in
`src/models/deepseek4.cpp` COMMENTA tre `ggml_build_forward_expand` (residual/post/comb sugli
strati hash-routed) con commento dell'autore «LOCAL (bisect experiment…): the other half of
dee2a846b's deepseek4 change. Disabled to test whether graph node ordering rather than backend
pinning is what shifts the numerics». Cioè: **la ricetta dimostrata gira con metà di un fix di
grafo upstream (`dee2a846b`, «dsv4 graph fixes») DISABILITATA per un esperimento numerico di
qualcun altro**, estraneo al routing vision. Decisione di regia: variante `pr28133-fixrestored`
con le tre righe ripristinate, build separata in `build-fix\`, e **A/B deterministico fra le due
al completamento del download** (stesso prompt, temp 0, seed 1) — nessuna misura di qualità si
fa su una build con fix upstream spenti da terzi senza prima vedere se la numerica diverge.

Minori a registro: web UI non pinnata (asset `b10734` irraggiungibile, fallback `latest`);
OpenSSL assente ⇒ server senza HTTPS (irrilevante in locale); il riferimento del README a
`2b5621094` riguarda kernel IQ rotti solo su Blackwell sm_120, irrilevante per SM86. Comando di
smoke pronto a valle del download, con guardia «nessun llama-server in esecuzione» (il load a
`-ngl 0` occupa ~80 GiB di RAM).

## 27. DOWNLOAD COMPLETO E VERIFICATO — e il crash su immagine del README È IL NOSTRO BUG

**8/8 file in `C:\ds4-models\Vision-Exp-GGUF\`, SHA256 combacianti uno a uno con gli oid LFS**:
4 parti IQ2_XXS (84,65 GB) + mmproj F16 + imatrix + patch + README = **80,15 GiB totali**, 49,4
min a 27,7 MiB/s medi (un solo reset di rete, retry+resume validato empiricamente: la parte
colpita ha passato lo SHA). **C: 143,83 → 63,64 GiB liberi**; `DS4-0731-IQ2XXS.gguf` di
produzione intatto (mtime invariato). Niente cache HF, zero file estranei.

**I tre reperti della consegna**:
1. **La patch viene da un working tree sporco** — conferma indipendente della bisezione del §26,
   più un indizio: il commento rimanda a una «l_out note below» che NELLA PATCH NON ESISTE.
   Regola confermata: una patch di terzi si legge riga per riga, mai dal titolo. (La variante
   `fixrestored` era già ordinata.)
2. **IL CRASH SU IMMAGINE È LA NOSTRA STESSA CLASSE DI BUG.** Il README attribuisce l'abort a
   `llm_graph_input_embd::set_input` che popola il tensore dei token **solo se `ubatch->token`
   è impostato**: sui layer hash-routed il gather `tid2eid[t_inp_tokens]` legge memoria non
   inizializzata e muore in `ggml_compute_forward_get_rows` su
   `GGML_ASSERT(i01 >= 0 && i01 < ne01)` — **stesso assert e stesso meccanismo del nostro
   fascicolo aperto «indice −1 nella testa Markov al taglio del reasoning»** (`ops.cpp:4831`,
   `OVERLAP_BATCH_MAX=4`). Classe comune: *un batch col tensore token non popolato che raggiunge
   un get_rows su `tid2eid`*. Movente forte per riaprire quel fronte con una pista concreta.
3. **La parte 4 è condivisa fra i tre quant del repo ED È LEGITTIMO**: header GGUF parsato —
   `split.no=3`, 1239/1371 tensori = tutti i NON-esperti (identici fra ricette); i quant
   differiscono solo nelle parti 1-3. E il 1371 conferma l'aritmetica: 1328 + 43 bias `_vl`.
   **Compatibilità chiave dal codice della patch**: `exp_probs_b_vl` è `TENSOR_NOT_REQUIRED`
   («Absent from text-only checkpoints (0731)») ⇒ **il binario patchato carica ANCHE il modello
   di produzione 0731** — un solo binario per entrambi, rilevante per il porto nel fork.

**Riferimenti hardware del README (NON trasferibili al nostro banco)**: misure su RTX PRO 6000
Blackwell 96 GB — 129,4 t/s in decode **con bozza DSpark Q2_K al 63,9% di accettazione** (punto
di riferimento per la domanda «il drafter trasferisce?»); per la classe 3060 il README dà «CPU
only: works, slowly» / «48 GB + offload: fattibile». Header GGUF: `deepseek4`, 43 blocchi,
256/6 esperti, 3 layer hash-routed, ctx 1.048.576, hyper_connection 4, sliding window 128,
indexer top_k 512. Limiti dichiarati: visibilità in-span NON implementata (fallback causale),
multi-immagine e contesti lunghi non misurati. Nel repo esiste anche un `IQ3_XXS` MONCO (solo
parte 1 di 4): inservibile, non scaricato.

## 28. IL MODELLO PARLA — e l'A/B DIVERGE: le tre righe cambiano la numerica. DECISIONE: variante B

**Via A: OBIETTIVO RAGGIUNTO.** Su entrambe le varianti il loader accetta i **1371 tensori**
(esattamente il conteggio che lo stock rifiuta), riconosce tutti i **43 `exp_probs_b_vl.bias`**
(blk.0…blk.42), `arch=deepseek4`, 284,33B parametri, e il modello genera italiano coerente
(smoke `-ngl 0`, tutto CPU: prompt ~5 t/s, generazione ~3,3 — non è un banco).

**L'A/B deterministico DIVERGE dai primissimi token**: A (as-is prometheusAIR) e B
(fix-restored) sono ciascuna riprodotta identica su doppio lancio (A=A, B=B, A≠B) ⇒ **i tre
`ggml_build_forward_expand` di `dee2a846b` cambiano la numerica su questo modello** — non era
un dettaglio innocuo. Varianti: A = `build\bin` (banner `b10734-9c9a1546d`, llama.dll
`F3EB9B20…`); B = `build-fix\bin` (`b10736-5c8e5d50b`, `316A1CBC…`; branch locale
`pr28133-fixrestored`, 2 commit: patch verbatim + revert del hunk spurio, regione byte-identica
alla PR pristina).

**DECISIONE DI REGIA (registrata)**: **B è la build di lavoro** — è l'unica coerente con
l'intento upstream (`dee2a846b` è un FIX di grafo mergiato, il disable era l'esperimento
personale dell'autore della patch, sfuggito nell'export). **A si conserva intatta** come
riferimento: la validazione end-to-end pubblicata da prometheusAIR (didascalia, tabella 135,8 /
129,4 t/s) fu prodotta con A, quindi ogni confronto coi loro numeri passa da lì. Il conflitto
«pubblicato vs upstream-corretto» è reale e va tenuto a mente se emergono anomalie di qualità:
la coppia A/B pronta è l'arma per deciderlo in tre minuti.

Nota d'esercizio dal fumo: a 48 token il modello spende TUTTO il budget in reasoning
(`[Start thinking]…`) senza arrivare alla risposta — per i capability test servono budget
maggiori o il no-think lato server. Dispacciato il passo successivo: **prima immagine** su B
(test a contenuto noto generato localmente: cerchio rosso + quadrato blu + scritta «DS4»), con
cross-check su A se B abortisse (sospetto di famiglia: l'assert `i01 >= 0` del §27), e a
seguire un riferimento di velocità upstream con esperti su CPU (`--n-cpu-moe`) se la VRAM regge.

## 29. IL MODELLO VEDE: didascalia 3/3 al primo colpo. E la baseline upstream è 5,5 t/s

**Capability immagine su B: RIUSCITO, exit 0, nessun assert** (il caso critico ipotizzato — le
tre righe ripristinate che rompono il cammino immagine — NON si è materializzato; cross-check
su A non necessario). Immagine di test generata in locale (448×448, contenuto noto verificato
al pixel: cerchio rosso alto-sx, quadrato blu basso-dx, «DS4» nero al centro). **Didascalia
verbatim**: «L'immagine mostra un cerchio rosso in alto a sinistra, un quadrato blu in basso a
destra e la scritta "DS4" in nero al centro.» — **3 su 3, posizioni e colori esatti, OCR
corretto, zero allucinazioni, riprodotta identica su due corse.** Torre visiva: `Deepseek
Vision`, 427 tensori, `CLIP using CPU backend` (`--no-mmproj-offload` onorato), 448×448 nativa
→ **148 token visivi**, encode **2,70 s** su CPU; marcatori `<｜deepseek_image｜>` &co.
caricati.

**Riferimento di velocità upstream (B, testo, non-banco)**: `-ngl 999 --n-cpu-moe 43 -c 4096`
⇒ `offloaded 44/44 layers to GPU`, **VRAM totale ~6,5 GiB su 12** (model 5485 MiB + KV 63,5 +
compute 947), esperti in `CPU_Mapped` ~73,5 GiB. **Generazione 5,5 t/s** (identica su due
corse; prompt 5,8-5,9), contro 3,3 a `-ngl 0` ⇒ l'offload standard vale 1,67× qui. **Termine
di paragone per il porto**: il nostro fork sul 0731 fa 12,69 ⇒ **il valore del porto (cache
esperti + DSpark) è ~2,3× sopra la baseline upstream** su questa macchina — da ri-verificare
sul Vision a porto fatto.

Dispacciata la **fase 2** (§25): accettazione del drafter attuale su DUE bersagli con lo stesso
binario B (0731 = controllo, Vision = domanda), lettura dal `print_timing` (MAI dalla riga
`statistics`, che mente), cancelli pre-registrati: Δ ≤10 punti ⇒ trasferisce; crollo >25 ⇒
ri-estrazione da shard nextn mirati.

## 30. FASE 2 — **IL DRAFTER TRASFERISCE** (Δ 0,64 punti). E DSpark è cittadino upstream

| | T0731 (controllo) | TVIS (Vision) | Δ |
|---|---:|---:|---:|
| draft acceptance (print_timing, verbatim) | **0,66146** (127/192) | **0,65504** (338/516) | **−0,64 pt** |
| mean len accettata | 2,98 | 2,97 | −0,01 |
| accettazione per posizione | 0,797/0,672/0,516 | 0,831/0,657/0,477 | ≈ (pos-1 meglio su TVIS) |

**Cancelli**: T0731 sano (66,15% > 50) ✓; **Δ 0,64 punti contro soglia 10 ⇒ TRASFERISCE, non è
zona grigia: è INDISTINGUIBILE** (errori standard ±3,4/±2,1 punti: regge anche al netto del
campione). **Niente ri-estrazione, niente shard nextn.** Coerente col riferimento esterno
prometheusAIR (63,9% immagine / 68,2% testo). Stessa build B, stesso drafter, `-ngl 999
--n-cpu-moe 43 -ngld 0`, temp 0, prompt identico.

**Le tre scoperte collaterali che pesano sul porto**:
1. **DSpark è upstream A PIENO TITOLO**: `DSpark-draft-Q2K.gguf` (arch `dflash`, 81 tensori)
   carica senza conversioni e viene **auto-riconosciuto** («auto-detected speculative type
   'draft-dspark' from the draft model metadata», discriminato dalla presenza della testa
   Markov, `speculative.cpp:2312`). Ricetta nel repo stesso: `docs/speculative.md` §DSpark
   (il README HF invece NON documenta il comando — buco loro).
2. **La riga `statistics` upstream NON mente**: numeri coerenti col print_timing + accettazione
   per posizione gratis. Il bug dell'1.000 fisso è DEL NOSTRO FORK ⇒ **al porto è un
   differenziale da recuperare, non da replicare.**
3. **Sulla baseline la speculazione NON compra velocità**: 5,46/5,04 t/s con bozza contro 5,5
   senza, ad accettazione 65% — la macchina upstream è byte-bound e i colpi non pagano.
   **È la quantificazione del perché serve il porto: è la NOSTRA cache a far fruttare la
   speculazione** (il fork sul 0731: 12,69).

Note: `--spec-draft-n-max` rimasto al difetto 3 (confronto interno valido; il valore assoluto
non è comparabile 1:1 col 63,9% esterno a n-max ignoto); T0731 fermo a 192 per fine sequenza,
TVIS a budget 512 (taglie campione diverse, già nel calcolo degli errori standard). Log:
`spec_T0731.log`/`spec_TVIS.log` nello scratchpad di sessione.

**Dispacciata la FASE 3 — porto MINIMO nel fork** (chirurgo17): solo il vl-routing
(arch/model/deepseek4/dflash, tensore `NOT_REQUIRED`, ramo `is_image_ubatch` inerte su testo),
SENZA l'hunk spurio della bisezione; protocollo: baseline corta PRE, backup DLL, build, **G1 =
regressione 0731 bit-esatta**, **G2 = il Vision carica e parla nel fork con la cache attiva**.
Immagini per ora dalla build upstream; mtmd nel fork = decisione successiva.

## 31. CHIRURGO 17 — G1 VERDE (0731 bit-esatto), il Vision CARICA nel fork… e LA CACHE LO CORROMPE: geometria mista scoperta

**Porto vl-routing eseguito pulito**: 7 aggiunte marcate (`llama-arch.h:428`, `llama-arch.cpp:407,789`,
`llama-model.h:338`, `deepseek4.cpp:195,1511-1524`, `dflash.cpp:200`), ricostruita SOLO
`llama.dll` (ggml-* byte-identiche al backup), 43 s di build, zero warning nuovi. **G1: SHA
`AD3D3770…BFCBFE11` IDENTICO su 6 corse (3 baseline + 3 post)** — il banco corto si è dimostrato
deterministico da solo. Identità nuova: llama.dll **`9E8E8D46…`** (chirurgo17), backup completo
in `backup_pre_chirurgo17\`.

**Reperto sulla numerica di casa**: le tre `ggml_build_forward_expand(residual/post/comb)` di
`dee2a846b` **NON esistono nel nostro deepseek4.cpp** (né attive né commentate) — il fork è già
sul lato «senza expand», lo stesso EFFETTO dell'hunk spurio della patch. Quindi la nostra ancora
numerica corrisponde al lato «A» del bivio upstream. Non toccato (l'ancora non si cambia in un
porto), ma da sapere per futuri confronti di qualità con la build upstream-B.

**G2: carica (1371 tensori, esperti su `CUDA0_Mapped = 74704 MiB`, 25 righe `cache-esperti:`)
MA CON LA CACHE ATTIVA L'OUTPUT È SPAZZATURA** (96 `<` di fila). Matrice di isolamento a 4 corse:
env SOTA ⇒ garbage · env pulito ⇒ coerente · upstream ⇒ coerente · **env SOTA +
`CACHE_ESPERTI_SLOT=0` ⇒ coerente** ⇒ colpevole certa la cache. **Causa trovata nel sorgente**:
`cache-esperti.cu:1913-1920` — «la prima terna completa dà le taglie»: passo/tipo presi dal
PRIMO strato e applicati a TUTTI, senza verifica di uniformità. Sul 0731 (down tutti Q2_K) è
mascherato; sul Vision i down sono **MISTI (IQ2_XS ×23, IQ3_XXS ×20)** ⇒ 23 strati letti con
stride e tipo sbagliati IN SILENZIO. Il punto presidia già due ALTRI rischi di troncamento
silenzioso: l'omissione stona, e oggi **cache e correttezza sul Vision si escludono a vicenda**
(`SLOT=0` = unico modo sicuro di servirlo col fork).

Note collaterali: i due checkpoint divergono su 746 tensori comuni (Q8_0→Q6_K ×344, F16→Q6_K
×315, `ffn_gate_inp` F16→**BF16** ×43, `token_embd`→Q8_0) — il router BF16 non ha dato problemi
nelle corse buone; `build_cuda.bat` dell'albero punta a `D:\llama-overlap` (albero SBAGLIATO):
trappola nota da oggi, usare la procedura sull'albero giusto.

**Dispacciato CHIRURGO 18 — geometria PER-STRATO nella cache**: slot uniformi alla taglia max
(~7,19 MiB sul Vision, aritmetica slot rifatta nel budget), array per-strato tipo/passo/byte
per copia e lettura mmvq, **guardia esplicita anti-corruzione-silenziosa** (rifiuto + fallback
senza cache), cammino 0731 degenere INVARIATO. Cancelli: G1 bit-esatto `AD3D3770…`, G2 Vision
COERENTE con cache attiva e contatori sensati, G3 primo assaggio con drafter.

## 32. CHIRURGO 18 — la geometria è GUARITA (e il difetto vero erano 38 BYTE). Ma sotto c'era un SECONDO colpevole

**Diagnosi più fine dell'ipotesi**: gli array per-strato ESISTEVANO già (`reg[strato]`, 43 voci;
la vista ombra mmvq eredita già `src0->type` dello strato). Il difetto vero, provato
aritmeticamente: **`allinea` nasceva dal mcm della SOLA terna dello strato 0** ⇒ sul Vision
(strato 0 = IQ3_XXS) `byte_slot` = 7.554.624, **NON multiplo di 74** = type_size(IQ2_XS); e
`mmvq.cu:1254` fa `s02 = nb[2]/ts` in divisione INTERA ⇒ sui 23 strati IQ2_XS lo slot k veniva
letto a `k·7.554.586` invece di `k·7.554.624`: **deriva di 38 byte per slot, senza assert né
errore**. Fix in `cache-esperti.cu` (:146-151, :1920-2086): censimento su TUTTI gli strati,
`byte_max[]` per posizione, `allinea` = mcm su tutte le taglie, **guardia esplicita**
(slot incapiente o `byte_slot` non multiplo di una taglia ⇒ cache spenta A VOCE ALTA, server
prosegue). Aritmetica dal log: Vision = 2 terne (20× IQ3_XXS + 23× IQ2_XS), byte_slot
**7.658.112 (7,3033 MiB)**, 473 slot = 3.454,5 MiB — **CI STANNO** (il Vision ha il model
buffer CUDA0 1,9 GiB più piccolo del 0731: 5.484 vs 7.384 MiB, attn Q6_K vs Q8_0).

**G1 VERDE** (3/3 SHA `AD3D3770…` byte-per-byte; il degenere stampa esattamente il byte_slot di
oggi). **G2 ROSSO ma il fix è VALIDATO dalla bisezione**: cache spenta ⇒ coerente · **cache 473
+ acceleratori spenti ⇒ COERENTE con colpi 55-76%** (la slab e la lettura mmvq sono corrette
sulla geometria mista) · cache + FORK/MASSA spenti + resto SOTA ⇒ garbage (riproduce i `<`) ·
SOTA completa ⇒ garbage non deterministico. ⇒ **SECONDO difetto indipendente**, colpevole fra
gli acceleratori sopra la cache (sospetti: `ACCEPTMOE_SOGLIA`, `MAPPED_IBRIDO`,
`OVERLAP_ASYNC`); caccia additiva dispacciata (stesso chirurgo, base positiva + una env alla
volta, drafter acceso come stabilizzatore — **il Vision senza drafter è NON deterministico**,
coerente con [[determinismo-viene-dalla-speculazione]]).

Identità: `llama.dll` invariata `9E8E8D46…`; **`ggml-cuda.dll` `6EF5B781…` → `6A98BE10…`**
(backup `backup_pre_chirurgo18\`). ⚠ TRAPPOLA A REGISTRO: **`build_cuda.bat` fa
`cd /d D:\llama-overlap`** — costruirebbe un ALTRO worktree riuscendo in silenzio; procedura
corretta a mano + `editbin /STACK` obbligatorio. E il cancello STRICT ferma la corsa se
MASSA e FORK si muovono separatamente: si spengono INSIEME. Completion positiva verbatim (cache
attiva, geometria mista): descrizione corretta di LRU con lista e sfratto dal fondo.

**Verifica indipendente (1/9, sessione parallela charming-faraday, dispacciata su un chip
stantio e fermatasi correttamente senza toccare nulla)**: mcm(16, 66, 74, 98) = **957.264** ⇒
byte_slot **7.658.112** ricalcolato A MANO e combaciante col log del chirurgo 18; stack reserve
64 MiB presente su tutti e tre gli exe post-build. Due numeri chiave confermati da mani diverse.

## 33. LA CACCIA: il secondo colpevole è **AcceptMoE × K=2**, Vision-specifico — e le route COLLASSANO

**Bisezione additiva (Vision, tutte con FORK=0 MASSA=0)**: AM=0/K=2 coerente (61,2% colpi) ·
+IBRIDO coerente (e NON inerte: 0,2→10,66 t/s) · +ASYNC coerente ma **INERTE** (SHA e contatori
identici ⇒ verdetto NULLO, regola del ramo raggiungibile) · AM=1/**K=0** coerente ·
**AM=1/K=2 ⇒ GARBAGE** (e `BATCH_MAX=1` non guarisce).

**L'aritmetica che inchioda il sintomo**: a K=0 la domanda è 53.664; l'attesa a K=2 è ×4/6 =
35.776 e l'arm sano misura 36.102 (esatto); **l'arm rotto misura 22.506 = ×0,419 ≈ 2,5 esperti
su 6, coi colpi al 94,3%: le route COLLASSANO su pochi esperti ripetuti** — che è precisamente
il testo ripetitivo osservato. **Il 0731 con le stesse leve è coerente e deterministico (2/2
SHA `C0B19551…`): il difetto è Vision-specifico.** Esclusi con prova: geometria (l'arm AM=0
gira con colpi veri), FORK (spento ovunque nei rotti), IBRIDO (da solo coerente), lane
(`partizioni=0, CPU=0` ovunque), replay stantio (divergenze=0), e il kernel acceptmoe stesso
(senza drafter è una COPIA: righe mascherate=0 — il danno sta in ciò che la sua PRESENZA cambia
a valle).

**Due indizi concreti nel sorgente (nessuno ancora provato)**:
1. `ggml.c:5405` — `ggml_acceptmoe_ids` produce un tensore 2D **CONTIGUO** (`nb[1]=24`) dove
   l'originale `selected_experts` è la vista con stride dell'argsort (`nb[1]=1024`); la
   partizione legge `s0->nb[1]/4` (`ggml-cuda.cu:3311`) e il commento della op dichiara il
   presupposto «src0 è la vista con stride dell'argsort (lezione 3fb92b9)» — **che con
   AcceptMoE acceso non vale più**.
2. `cache-esperti.cu:1065-1097` — `registra_router` mappa sia `ffn_moe_topk-N` sia
   `ffn_moe_acceptmoe_ids-N` su `quale=0` e **SOVRASCRIVE SENZA GUARDIA** (a differenza di
   `registra`): con AcceptMoE i due tensori coesistono e vince l'ultimo registrato.

**Perché il fix è «largo» e la fermata è giusta**: discriminare richiede dumpare gli id visti
da `kern_partiziona` e dal mmvq nei due arm — e `LLAMA_OVERLAP_VERIFICA` sotto CUDA graph gira
**solo alla cattura, mai ai replay** (copertura ~nulla, dichiarata dal suo stesso commento): va
resa raggiungibile prima di fidarsene. Nessuna ricompilazione dopo G1: identità DLL invariate,
G1 `AD3D3770…` resta valido.

**Dispacciato il braccio pratico che la bisezione non copriva**: **V-SOTA-AM0** — la SOTA
COMPLETA (FORK=2+MASSA=2, K=2, cache 473) con la sola `ACCEPTMOE=0`, drafter acceso, 2 corse.
Se coerente ⇒ è la **config di servizio del Vision** da oggi (lo sweep §21 dice che questa
famiglia non muove i t/s) e arriva il primo numero di velocità sulla macchineria piena; se
garbage ⇒ c'è un terzo colpevole in interazione col fork, e un solo arm K=0 lo localizza.

## 34. **IL VISION È IN SERVIZIO SULLA MACCHINERIA PIENA: 12,4-12,9 t/s, accettazione 0,70-0,73**

**V-SOTA-AM0: VERDE sulla coerenza** — 4/4 corse coerenti (lette davvero), zero assert, e
stavolta la lane è INGAGGIATA: `partizioni=30.917, CPU=61.834 (=2×, k_cpu=2)`, colpi **64,6%**
(in banda), copie 44.528, `acceptmoe lanci=0` ✓, replay puliti. **Decode 12,4-12,9 t/s**
(0731 sul corto: 13,3-14,3 — stesso ordine, un filo sotto, coerente con slot 7,30 vs 6,75 MiB e
colpi più bassi), accettazione draft 0,70-0,73. Numeri indicativi (ctx 4096, prompt corto), non
banco. **AcceptMoE confermato UNICO colpevole anche a fork/massa PIENI**: nessuna interazione
fork×altro.

**CONFIG DI SERVIZIO DEL VISION (da oggi)**: SOTA integrale con UNA differenza —
**`LLAMA_ACCEPTMOE=0`**. ⚠ Il nome è `LLAMA_ACCEPTMOE`, NON `LLAMA_CACHE_ESPERTI_ACCEPTMOE`
(quel nome non ha lettori: sarebbe stato assente in silenzio e il braccio avrebbe misurato la
SOTA piena — l'esecutore ha grep-ato il lettore e corretto il mandato di regia; ennesima
istanza della regola). Le dipendenti `ACCEPTMOE_*` restano inerti sotto l'interruttore maestro,
nessun rifiuto STRICT. `-c 4096` con 473 slot: VRAM ~10/11,8 GiB; **ctx maggiori richiedono di
rifare l'aritmetica slot** (nota per il ri-ancoraggio del lungo).

**Il determinismo NON si chiude — e la diagnosi CORREGGE una convinzione di casa**: la PRIMA
richiesta dopo un load freddo è bit-riproducibile fra server distinti (r1 = r1, SHA
`E7547ABB…`, p1 alla 5ª cifra); è la SECONDA a divergere, e **nemmeno `porto_hot_snapshot`
basta**: la residenza della cache esperti evolve fra le richieste e (sul Vision) il restore non
la copre ⇒ partizione diversa ⇒ ordine di riduzione diverso ⇒ divergenza FP amplificata su 300
token greedy. **Il determinismo del 0731 veniva dal RESTORE (residenza compresa), non dalla
speculazione da sola** — converge col reperto mask=8 del 25/8 («la residenza decide QUALE
traiettoria si prende»). Sul Vision il cancello d'identità fra richieste successive resta
aperto finché il restore non copre la cache nuova.

In coda: (1) cantiere fix AcceptMoE (i due indiziati del §33; prerequisito: rendere
`OVERLAP_VERIFICA` raggiungibile ai replay); (2) ri-ancoraggio dei banchi sul Vision (corto
prima, poi il lungo con l'aritmetica slot rifatta); (3) test vero sul testo dispacciato
(saggio 1200 no-think + §4.10 esteso). Binari fermi (`9E8E8D46…`/`6A98BE10…`), G1 valido,
produzione intatta.
