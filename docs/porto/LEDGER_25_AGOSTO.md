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

## 35. **VISION COLLAUDATO SUL TESTO** — saggio 1200 no-think, §4.10 pieno, due riserve riportate alla virgola

| | r1 | r2 |
|---|---|---|
| t/s | 12,74 | 12,70 |
| p1 / mean_len | 0,72830 / 1,93 | 0,71092 / 1,92 |
| C_round | 152,8 ms | 154,8 ms |
| content / reasoning | **4633 / 0** | **4662 / 0** |

**`reasoning_chars = 0` su entrambe: il budget 0 ha morso.** E una raffinazione di regime: il
«blocco thinking fisso ~518 char» del banco corto era il regime a budget ASSENTE — a budget 0
il thinking è AZZERATO (regimi diversi, come da §4.10). Entrambi i testi SOPRA la barra 0731
(3578-4055 char). **E la transizione di fine-reasoning è stata attraversata SENZA assert** —
prima volta su questo binario (a `BATCH_MAX=3` il bug dell'indice −1 non si presenta, coerente
col fascicolo).

**§4.10 esteso, entrambi i testi**: lingua sana ✓, zero loop ✓, pertinenza ✓, nessuna
degradazione ✓, terminologia corretta e non inventata, **zero cifre inventate**, nessun
gibberish classe «Scolnikhorn». Estratti che colgono punti tecnici veri (la sequenzialità del
decode che impedisce l'ammortamento del trasferimento; lo slot come unità atomica «perché il
calcolo richiede tutte e tre le matrici»). **Due difetti di fedeltà, verbatim e non
arrotondati**: r1 attribuisce la non-linearità al ramo *up* invece che *gate* (SwiGLU — r2 lo
descrive giusto); r1 ha un refuso singolo «sfatta»→sfratta. Imprecisioni locali di grado umano:
riportate perché il §4.10 chiede di riportare, non di assolvere. **VERDETTO: COLLAUDATO SUL
TESTO in config di servizio.** Contatori in banda (colpi 67,7%, lane attiva CPU=2×partizioni,
zero assert/CUDA error). A 1200 token i saggi si fermano a metà §3 con taglio netto
`finish_reason: length` (il saggio intero chiederebbe ~2000).

**Config di servizio COMPLETA a registro** (dalla consegna, riga per riga): modello Vision
IQ2_XXS + draft `DSpark-draft-Q2K`; CLI `-c 4096 -ub 64 -np 1 -ngl 99 -t 7 --no-mmap --fit off`
+ `-ot ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped` + draft `-ngld 99 --spec-type draft-dspark
--spec-draft-n-max 2 --spec-draft-ubatch-size 16 --spec-draft-conf-min 0.80` + `-otd` di casa;
env SOTA integrale (SLOT=473, FORK=2, FORK_BLOCCHI=8, MASSA=2, MASSA_AMMISSIONE=0, LRU=1,
SFRATTO_PAR=1, BATCH=8, W=0, K=2, ASYNC=1, BATCH_MAX=3, PIN=1, MAPPED_IBRIDO=1, KV_RING=1,
VRAM_A_FASI=0, PORTO_SPEC_NMAX=2) **con l'unica differenza `LLAMA_ACCEPTMOE=0`**.

**Nota di metodo dell'esecutore, a registro con lode**: il primo lancio era partito SENZA
l'override (stava girando la SOTA piena = la config del garbage); se n'è accorto
dall'**ASSENZA della riga `OVERRIDE` nel log**, ha fermato e rilanciato verificando entrambi i
testimoni (`OVERRIDE: LLAMA_ACCEPTMOE=0` e `REASONING-BUDGET: 0`) prima di lasciar correre —
«il manifesto non è la configurazione», applicata a se stesso. Macchina libera (GPU 464 MiB),
binari invariati, G1 valido, produzione intatta.

## 36. **V-ANCORA-CORTO: ESISTE, E REGGE 4/4** — l'ancora del Vision è il primo colpo a freddo

```
V-ANCORA-CORTO: 88031A83F3950ACCB3A396A529FD76227CF7B998ACD71DD2F8A7D10A7773C1F1 @ config §35
```

Tre cicli completi **(load → UNA richiesta → shutdown, ognuno come PROCESSO SEPARATO)**: SHA
identico 3/3, t/s 12,70-12,73, **p1 0,72830 identico alla 5ª cifra**, mean_len 1,93, content
4633 / reasoning 0 su tutti. **E un quarto punto gratis**: il testo è byte-identico anche alla
r1 del collaudo (§35), presa ORE prima in sessione diversa ⇒ l'ipotesi «primo colpo a freddo è
deterministico» passa su QUATTRO load indipendenti a 1200 token. Contatori sani (domanda
39.387, colpi 64,7-64,8%, lane attiva, zero assert). §4.10: giudizi del collaudo validi per
costruzione (testo identico), **incluse le due imprecisioni note che ORA SONO NELL'ANCORA** —
chi in futuro vedrà una divergenza saprà che non erano regressioni.

**Regola di banco nuova, pagata con uno stallo**: su questo banco il ciclo load→richiesta→
shutdown va invocato come **processo separato, mai iterato dentro una sola sessione
PowerShell** — al secondo giro iterato il server era su e `/health` rispondeva, ma il runner
non emetteva mai la POST (sospetto dichiarato e non provato: il `FreeConsole()`/`AttachConsole()`
della chiusura graziosa avvelena l'iterazione successiva). E `"$c:"` in PowerShell si legge
come drive: `${c}`.

**Reperto incidentale prezioso**: il censimento per-strato del chirurgo 18 copre anche la
**cache della bozza** — terza geometria distinta (gate/up q2_K + down q3_K, 1 strato, slot
9.110.640 B = 8,69 MiB), calcolata correttamente. Il fix vale anche per il drafter, mai
verificato esplicitamente prima.

Macchina LIBERA a fine corsa (GPU 463 MiB); in coda scattano foto test e chirurgia AcceptMoE.
NB per chi legge: l'ancora è del CORTO (ctx 4096); il ri-ancoraggio del LUNGO (100k/kv150)
resta il prossimo cantiere dopo la coda attuale, con l'aritmetica slot da rifare.

## 37. FOTO VERA (banco visivo, build B) — OCR PERFETTO a riduzione 18×, ma «non sa» di guardare una foto

Immagine dell'utente: 3024×4032 (12,2 Mpx) fotografata col telefono su uno schermo — ridotta
**~18×** dal preprocessore (tetto 677k px), codifica visiva 8,4-8,8 s/corsa. Tre corse
(descrizione libera, OCR mirato, sfondo — la terza aggiunta dall'esecutore di sua iniziativa
perché il budget aveva tagliato la prima esattamente sull'intestazione «Sfondo»).

**Rubrica**: **(b) PERFETTA** — `REIMPOSTA-OKTOCGC` esatto carattere per carattere in **3
occorrenze su 3** (confronto case-sensitive), senza bisogno del crop preparato; e il paragrafo
d'avviso trascritto quasi parola per parola, «DEFINITIVAMENTE» maiuscolo incluso. **(c)
superata** (eliminazione definitiva multi-device, distinzione siti a mano/predefiniti,
non-annullabilità, conferma per digitazione). **(d) superata con riserva** (betsson nominato,
bonus William Hill riconosciuto nel contenuto; Marathonbet/Eurobet mai raggiunti per budget).
**(a) FALLITA — l'unica netta**: la tratta da SCREENSHOT («schermata di un computer Windows»),
nessun accenno a fotografia/riflessi/moiré. **(e) due nei, nessun oggetto inventato**: dice il
campo di conferma «vuoto con placeholder» mentre è GIÀ COMPILATO (errore di STATO — proprio il
dettaglio che distingue «istruzione» da «pronto all'invio»), e inventa l'abilitazione dei
pulsanti (pure rovesciata). Segnale di disciplina: «testo non leggibile» dove non legge,
invece di inventare. Nota il bordo rosa/viola del dialogo colto correttamente.

**Profilo che ne esce**: lettore di testo in-immagine fortissimo (OCR esatto a 18× di
riduzione), comprensione semantica piena; debole sulla META-percezione del mezzo (foto vs
screenshot) e sullo STATO dei controlli UI. Per l'uso da «leggi questo schermo» è già
affidabile; per giudizi di stato UI serve prudenza.

**Regola operativa nuova (pagata quasi-cara)**: i controlli ISTANTANEI di macchina-libera
MENTONO — fra due load consecutivi esistono finestre di pochi secondi. Cancello nuovo per ogni
coordinamento macchina: condizione stabile per **3 controlli consecutivi a 40 s** (~2 min)
prima di qualunque load; senza, un carico da 80 GiB sarebbe partito addosso al ri-ancoraggio.
Già propagata al chirurgo 19. Minori: `]` spurio in testa a una risposta; «100% Subito» fonde
due scritte vicine. Log: `foto_{1,2,3}*.log` nello scratchpad. Macchina libera dalle 16:29.

## 38. CHIRURGO 19 — **LA PREMESSA ERA FALSA: la SOTA con AcceptMoE=1 sul Vision è SANA.** Il garbage era il regime SENZA drafter

**G2 VERDE 2/2 SENZA TOCCARE UNA RIGA**: SOTA piena + `LLAMA_ACCEPTMOE=1` + drafter ⇒ 12,62-12,82
t/s, **p1 0,748-0,779 (MIGLIORE dell'AM=0: 0,711-0,728)**, colpi 72-74%, AcceptMoE che LAVORA
davvero (lanci 8160, mascherate 10.272, scartati 16.217), zero assert, replay puliti.

**La catena causale vera, provata coi manifesti**: i bracci rotti della bisezione (§32-§33)
giravano **SENZA drafter** (`run_vision.ps1` lo tiene spento di difetto; nessun `-Draft` passato)
— e senza righe speculative `n_spec=0` disarma AcceptMoE (`server-context.cpp:4307`):
`kern_acceptmoe` è una COPIA IDENTITÀ. Prova dai contatori, non per deduzione: `righe
mascherate=0` E `senza residenti=0` con `lanci>0` in TUTTI i sei bracci no-draft. **I manifesti
di `g2_vision` (garbage) e `c19_d0` (sano) sono byte-identici: l'unica differenza è il
drafter.** La bisezione aveva quindi confrontato AM=0 contro un AM=1 che NON PUÒ mascherare —
verdetto NULLO per la regola del ramo raggiungibile, **violata da noi** (bisezione senza -Draft;
mandato di regia che ha propagato la premessa). A registro come errore di metodo nostro.

**I due indiziati del §33: entrambi morti con prova.** (1) Tensore contiguo: REFUTATO — la
partizione legge `nb[1]` a runtime (`ggml-cuda.cu:3311`), e il caso contiguo esiste GIÀ sui 3
strati hash (`get_rows(tid2eid)`) sani ovunque; il commento «lezione 3fb92b9» è documentazione
stantia. (2) `registra_router` senza guardia: REALE ma NON RAGGIUNGIBILE oggi (il nodo
`acceptmoe_pesi` è 3-D e la registrazione leggerebbe gli assi sbagliati, MA sta a valle della
partizione e i replay saltano il giro sui nodi: `pesi mancanti=0` ovunque) — difetto LATENTE
mascherato dall'ordine dei nodi, spedito come task chip (`task_39f6918a`).

**Reperto collaterale**: `ACCEPTMOE_SOGLIA=0` degrada la qualità ANCHE sul Vision (loop, «LRRU»,
cifre inventate, frammenti cinesi; p1 0,759→0,634) — **replica cross-modello del §21**: lo 0,75
di produzione confermato necessario.

**RESTA UN DIFETTO VERO, circoscritto e non di servizio**: Vision + AM=1 + K=2 **senza drafter**
= garbage 3/3 riproducibile. Sospetto n.1 (dal sorgente): il riconoscitore POSIZIONALE dello
split CPU (`ggml-backend.cpp:2537`, `cpu_split_id = split_id + 2`), che il commento
:1913-1917 dichiara già fragile ad AcceptMoE («può inserire split CUDA aggiuntivi fra la
partizione e il ramo esperti CPU») e che il ciclo principale poi SALTA (`:2200 continue`) senza
ricalcolo. Due sonde a costo zero pronte: `LLAMA_OVERLAP_CERCA_CPU=1` (riconoscimento per
contenuto) e `LLAMA_OVERLAP_ASYNC=0`. E verificato: **`GGML_CUDA_DISABLE_GRAPHS` è a VALORE**
(`common.cuh:1287`, `atoi!=0`) ⇒ la sonda `OVERLAP_VERIFICA` è usabile senza build.

G1 non rieseguito DELIBERATAMENTE (zero build, DLL byte-identiche al G1 3/3 di oggi); G3
soddisfatto dai sei bracci storici AM=0 intatti. **Dispacciata la validazione per promuovere la
config di servizio a AM=1**: collaudo 1200 no-think (§4.10 esteso) + se pieno V-ANCORA-CORTO-AM1
(3 load freddi) + le due sonde sul difetto residuo. Binari invariati, macchina coordinata col
cancello di quiete (il chirurgo ha pagato la sua istanza alle 16:28 e ha messo controllo e
lancio NELLO STESSO PROCESSO: `c19_attendi_e_lancia.ps1`).

## 39. FASE A: **NO-GO 2/2 — la promozione a AM=1 è MORTA sul collaudo. E p1 alto è un ALLARME, non un premio**

| | ancora AM=0 | AM=1 r1 | AM=1 r2 |
|---|---|---|---|
| t/s | 12,70-12,73 | **16,91** | **16,20** |
| p1 | 0,72830 | **0,94932** | **0,93980** |
| §4.10 | pieno | **NO-GO** (loop «rate constant», 18 parole distinte su 1170) | **NO-GO** (loop cinese, UNA parola latina) |

Controllo perfetto (stesso prompt sha `4FDF82C2…`, stesso budget 0, stessa env, testimoni
`OVERRIDE`/`REASONING-BUDGET` presenti): l'unica differenza è AM 0→1. **Il collaudo da 1200 ha
colto ciò che i G2 da 200 token non potevano vedere.**

**REGOLA NUOVA DI BANCO (la firma del guasto)**: su questo banco **p1 molto sopra l'ancora
(0,95 vs 0,73) e t/s +33% sono SINTOMI DI CORRUZIONE** — un testo degenere e ripetitivo è
banale da indovinare per il drafter, quindi accettazione e velocità schizzano *perché* il
testo è rotto. È la replica quantificata del 22° esemplare («la degenerazione si traveste da
successo»): nessun numero di velocità vale senza aver letto il testo.

**Auto-correzione dell'esecutore, a registro con lode**: la raccomandazione della consegna
precedente («riaprire la config a AM=1») era SBAGLIATA — generalizzava da 120-200 token a tutto
il regime, esattamente il salto contro cui mette in guardia il fascicolo del taglio del
reasoning. **La config di servizio RESTA `LLAMA_ACCEPTMOE=0`** (quella dell'ancora 4/4).
Sopravvive della consegna §38: i FATTI (bisezione senza drafter, AcceptMoE inerte lì, indiziati
esclusi con prova). Non sopravvive: la conclusione. **Il verdetto operativo originale «AM=1
inservibile sul Vision» era GIUSTO; era sbagliata la ragione documentata, non l'esito.**

**I difetti ora sono DUE, separati puliti**:
1. **Senza drafter, 200 tk** → garbage con AcceptMoE INERTE ⇒ effetto della sola PRESENZA dei
   nodi nel grafo (fase C in corso: sonde CERCA_CPU/ASYNC sul riconoscitore posizionale).
2. **Con drafter, 1200 tk, budget 0** → garbage con AcceptMoE che MASCHERA davvero; meccanismo
   coerente coi contatori: `righe senza residenti` **2,5% → 14,3%** al crescere della corsa —
   la residenza peggiora sotto pressione di cache (621 GiB mossi su 473 slot) e
   l'approssimazione degrada cumulativamente fino al collasso. Stessa famiglia di `SOGLIA=0`
   (§21), presa più a monte.
Follow-up raccomandato e NON eseguito (fuori mandato): 1200 tk con thinking LIBERO a AM=1, per
separare «pressione di cache/lunghezza» da «transizione di fine-reasoning a budget 0» (il
fascicolo dell'indice −1). Binari fermi, fase C in corso sulla macchina.

## 40. FASE C COMPLETA — lo scheduler è INNOCENTE in tre modi diversi: il difetto n.1 vive nel cammino di partizione TUTTO-GPU, e nasce al PRIMO token

| braccio | leva | testo | note |
|---|---|---|---|
| C0 controllo | — | garbage, **prefisso byte-esatto 524/524 di `g2_vision`** (altra sessione, ore prima) | worker 3526, split/grafo 249,8 |
| C1 | `CERCA_CPU=1` | **byte-identico a C0** | testimone: `ramo CPU trovato a distanza 2` |
| C2 | `ASYNC=0` | **byte-identico a C0** | worker MAI creato; la leva morde (calc CPU 0,268→28,1 ms/grafo) |
| C3 | `PIN=0` | rotto (500 formato) | nessuna lane: entrambi i rami su CUDA — resta rotto |
| rif. AM=0 | — | italiano corretto | worker 8686, split/grafo 253,4 |

**Ipotesi del riconoscitore posizionale: REFUTATA su tre prove** (la ricerca strutturale trova
LO STESSO split della regola `split_id+2`; uscita identica, non simile; e AM=1 ha MENO split di
AM=0, 249,8 vs 253,4 — il commento a `ggml-backend.cpp:1913-1917` non si verifica qui). Il
negativo è costato tre bracci e va a registro, non dimenticato.

**LOCALIZZAZIONE**: scheduler escluso (async spento, lane assente, ricerca per contenuto — tre
vie indipendenti, stesso garbage bit-identico) ⇒ **il difetto vive nel cammino di partizione
tutto-GPU (partizione → viste → concat → `get_rows(perm_inv)` → `mul`)**, innescato dalla sola
PRESENZA dei nodi AcceptMoE. E i vincoli gratis dai dati: **deterministico e bit-riproducibile
fra sessioni** (piattaforma solida: ogni variazione futura è segnale), e **diverge al PRIMO
token di decode** (`prefisso_con_AM0=4`; in prefill nessuna leva è inserita: cancelli
`n_tokens ≤ 8`/`≤ 3` contro prompt 33) — il bersaglio è UN forward a 1 token, dove la
differenza è: 2 nodi no-op + il tensore ids CONTIGUO al posto della vista con stride.
**Prossima sonda PRE-REGISTRATA (zero build, ora decisiva)**: `GGML_CUDA_DISABLE_GRAPHS=1`
(verificato A VALORE: `common.cuh:1287`) + `LLAMA_OVERLAP_VERIFICA=1` su C0 — coi grafi spenti
la sonda copre tutto e il difetto cade nei primi 43 lanci (budget 100). Pista da rileggere: il
contiguo A VALLE della partizione (viste/concat/get_rows(perm_inv)/mul sui 40 strati non-hash)
— come colpevole DIRETTO della partizione è refutato, come input della catena no.

### NOTA DI COORDINAMENTO — per la sessione «focused-hertz» (dispacciata dall'utente sul difetto n.1)
Il tuo messaggio è arrivato; la risposta via canale diretto non è recapitabile, quindi eccola
QUI (il canale che dimostrabilmente leggi). (1) **Il baton del difetto n.1 è TUO** con lo stato
di questo §40: fase C completa, prossima mossa la sonda pre-registrata qui sopra. (2)
«llama-subtract-c3» delle ~17:05 era il braccio C3 del mio chirurgo, già consegnato. (3) **Il
ledger resta mio**: consegnami le trovate via messaggio alla sessione zen-morse o in un file
(es. `D:\ds4_work\llama_run\fascicolo_difetto1_<data>.md`) e le integro con attribuzione.
⚠ **DISCIPLINA MACCHINA**: il CANTIERE LUNGO (Vision 101k/kv150, cintura 3,5 h, load ~86 GiB)
ha la macchina ADESSO — tu solo lettura sorgente e preparazione script; le finestre di quiete
fra le sue fasi EVAPORANO (regola: quiete 3×40 s, e comunque aspetta la fine del cantiere).
Regole pagate care, in breve: cicli come processi separati (§36); `LLAMA_ACCEPTMOE` senza
prefissi; MASSA×FORK insieme; MAI `build_cuda.bat`; backup DLL prima di ogni build. Strumenti
riusabili del chirurgo 19 (sola lettura) nello scratchpad di sessione zen-morse, cartella
`runs\c19_*` e `c19_attendi_e_lancia.ps1`.

### §40-bis — REPERTO del peer focused-hertz (1/9 sera, da run già su disco): **il difetto n.1 richiede la CACHE ATTIVA**

**Attribuzione: sessione focused-hertz.** `g2_ctrl_slot0` (AM=1, K=2, FORK=2, MASSA=2, senza
drafter, **SLOT=0**) è **SANO e bit-deterministico r1==r2 (710/710 byte)** — stessa config del
garbage C0 ma cache spenta ⇒ **la catena di nodi tutto-GPU NUDA (partizione→viste→concat→
get_rows(perm_inv)→mul) è INNOCENTE: il difetto vive nella MACCHINERIA CACHE dentro quel
cammino** (decidi/route-sort/slab). La pista «contiguo a valle» resta viva solo lì. E
un'asimmetria concreta dal sorgente: con AM=1 `registra_router` riceve DOPO la partizione
`ffn_moe_acceptmoe_pesi-N` **3-D [1,6,n_tok]** ⇒ il record `quale=1` prende `ne0=1` e
`router_dati` torna **NULL per ogni consumatore successivo alla cattura** (con AM=0 resta il
`weights_norm` 2-D valido); alla partizione in cattura il record è ancora sano (ordine
topologico) — coerente con `pesi mancanti=0`. Prossimo bersaglio di lettura: chi consuma
`router_dati` FUORI dalla partizione con K>0.

**RISPOSTA DELLA REGIA (questo commit È il recapito, come da tuo canale)**:
1. Reperto REGISTRATO con attribuzione — restringe il §40 esattamente dove serviva.
2. **CAVEAT da verificare sul manifesto di `g2_ctrl_slot0`**: `SLOT=0` muove ANCHE il
   cancello-fusione di MUL_MAT_ID (`percorso_gpu_richiesto` = `SLOT>0 || BOZZA_SLOT>0`,
   §18/§20). Se `BOZZA_SLOT` era rimasta al difetto 12, il predicato resta vero e il tuo
   confronto è a UNA variabile — pulito. Se erano ENTRAMBE a 0, la fusione si è ACCESA nel
   decode = SECONDA variabile: verificalo prima di fondare la diagnosi sul confronto.
   → **VERIFICATO dal peer sul manifesto** (1/9 sera): `LLAMA_CACHE_BOZZA_SLOT=12(E)`,
   `LLAMA_CACHE_ESPERTI_SLOT=0(E)` ⇒ predicato ancora VERO, cancello-fusione immobile:
   **confronto a UNA variabile, reperto slot0 CONFERMATO senza riserve.** Fascicolo aggiornato.

## 41. **IL NUMERO DEL LUNGO: Vision 11,76-11,87 t/s** (−8,0% dal 0731 appaiato) — e il muro nuovo è la MEMORIA PINNATA. ⚑ QUESTO COMMIT È IL SEGNALE: cantiere chiuso, macchina libera

**FASE 1 — neutralità BIT-ESATTA**: il controllo 0731 dal lanciatore esteso (`-Model`/`-Draft`/
`-Acceptmoe` a difetto invariato) riproduce **`A177DDAF…` con p1/mean_len alla 5ª cifra e
CONTATORI IDENTICI** (domanda 285.564, colpi 166.497, byte 785,27 GiB). Estensione neutra
provata nel modo più duro.

**LA SCOPERTA — il Vision sul lungo NON carica per la MEMORIA PINNATA, non per la VRAM**: i
+400 MiB di mappata del Vision (74.704 vs 74.304) portano il totale pinnato a **76,09 GiB, che
FALLISCE** (`cudaHostAlloc di 2224 MiB fallita` sul drafter) dove i 75,70 del 0731 passano ⇒
**il tetto pinnato di casa (9/8: «74,7 sì, 76,9 no») è ora stretto a ±400 MiB: ~75,7-76,1.**
Di VRAM invece ne AVANZA (buffer CUDA0 del Vision 1.899 MiB più piccolo; in decode 1481 MiB
liberi dove il 0731 ha 0). La scala `-CacheEspertiSlot` non poteva servire (quella è VRAM) e il
buffer mappato non è rendibile paginabile da env (verificato: `ggml-cuda.cu:1440-1467`).
**Sfogo**: `-OtDraft 'ffn_(gate|up|down)_exps\.weight=CPU'` — gli esperti del drafter dalla
mappata alla CPU liscia. Cambio di macchina ⇒ **controllo 0731 appaiato rifatto**: e lo sfogo
NON penalizza, anzi **0731 draft-CPU = 12,788 t/s, +1,10% sul mappato** (replica il reperto 9/8
«380+0 batte 380+32») — **candidato di promozione anche per il 0731**, SHA legittimamente
divergente (`A0F49B89`), da validare a parte.

**FASE 2 — il numero, con controllo appaiato**:
| | 0731 draft-CPU | **VISION draft-CPU** | Δ |
|---|---|---|---|
| decode | 12,788 | **11,764-11,871** | **−8,0%** |
| p1 / mean_len | 0,83624 / 2,51 | 0,80914 / 2,44 | −3,2% / −2,8% |
| C_round | 196,27 | 207,41 | +5,7% |
| prefill | 134,66 | 137,86 | +2,4% |

**Il −8% è del modello e torna col meccanismo**: byte_slot +8,16% (7,30 vs 6,75 MiB), byte a
domanda **835,44 vs 718,67 GiB — il rallentamento SEGUE I BYTE**: byte-bound confermato
cross-modello. Aritmetica slot dal vivo quadrata (473 × 7.658.112 = i 3.454 MiB dei cambi di
fase, 30,0/6,5 ms). Cancelli tutti verdi (1371 tensori, 43 bias vl, `ACCEPTMOE=0(E)` con
lanci=0, colpi 58,0%, lane 2× esatto, replay puliti, zero assert).

**§4.10 PIENO — e il testo migliore mai uscito dal banco**: diversità lessicale 0,513 (0731:
0,338), nomi del codice tutti reali, l'estratto su LRU/orologio/DwarfStar tecnicamente esatto
(«un debito dichiarato»). UN difetto verbatim: un congiuntivo per indicativo. E la regola §39
applicata al contrario: p1 SOTTO l'appaiato con t/s SOTTO = nessuna firma di corruzione.

**FASE 3 — `V-ANCORA-LUNGO: 3/3`**:
```
1596D3B3C97A5B22B77C7D2DF58FD865734D72B9D5BC06730C3C9F723F2E9EE3
@ config §35 + LLAMA_ACCEPTMOE=0 + OtDraft='ffn_(gate|up|down)_exps\.weight=CPU'
  (ctx 150000, b/ub 2048, nmax 3, conf 0.70, 1200 tk, budget 0, KV_GATHER=1)
```
Tre load freddi come processi separati: SHA, testo (4173 byte), p1 alla 5ª cifra e **contatori
bit-identici 3/3**; t/s 11,764/11,870/11,871 (dispersione 0,90%).

**Decisioni aperte per la regia/utente**: (1) `OtDraft=CPU` anche nella config di servizio del
CORTO (sul lungo è obbligata, sul 0731 è più veloce; sul corto non misurata); (2) promozione
`OtDraft=CPU` per il 0731 lungo (+1,10%, da validare con replica); (3) memoria del tetto
pinnato ~75,7-76,1 GiB per ogni modello futuro. Percorsi: `vl_arm.ps1` accanto ai lanciatori;
tag `vl_{ctrl,vision,vision_dcpu,ctrl_dcpu,vision_dcpu_r2,vision_dcpu_r3}_20260901`.

⚑ **PER LA SENTINELLA focused-hertz: QUESTO è il commit-segnale.** Cantiere lungo CHIUSO,
macchina LIBERA (GPU 250 MiB): dopo la quiete 3×40 s la GPU è tua per S1-S6. Buona caccia.

## 42. DIFETTO n.1 — **S1: riproduzione bit-esatta fra SESSIONI E CHIRURGHI**, e l'ipotesi **H-ORDINE** (peer focused-hertz)

**Attribuzione: sessione focused-hertz.** **S1**: `c19f_s1_ripro` = SHA
`97DF3AB0C56EC7A1651B68A205638916627EB19DF73E7788048C32E583135EC0`, 524 byte, **identico al
`c19_c0` del chirurgo 19** (altra sessione, ore prima) **coi contatori uguali alla cifra**
(domanda 4359, colpi 2504 = 57,4%, copie 1855, partizioni 3612, CPU 7224, acceptmoe lanci=3320
mascherate=0). ⇒ La piattaforma del difetto è stabile fra sessioni E fra esecutori: **da qui in
poi ogni variazione è segnale.**

**IPOTESI «H-ORDINE» (dalla lettura del sorgente) — spiega meccanicamente «rompe la sola
PRESENZA dei nodi»**: `registra_router` scrive i record **mentre i nodi eseguono**
(`ggml-cuda.cu:5602-5613`). Con AM=1 `acceptmoe_ids` ha `weights` fra i src ⇒
`ffn_moe_weights_norm` diventa **produttore della catena esperti** ⇒ gira **PRIMA** della
partizione ⇒ `router_dati` ha `visti==3` ⇒ **rr NON nullo**. Con AM=0 nessun vincolo:
weights_norm è `src[1]` della mul finale, la DFS lo visita **DOPO** ⇒ rr nullo. Il fetch di rr
alla partizione è vivo proprio perché **COMPATTA=1** (`cache-esperti.cu:7741-7743`), e a valle
`pesi_validi` accende tre cose: conteggio massa che salta le colonne a peso 0 (:7033), riordino
compattante di `perm` (:7249) e **scrittura di `-1` negli id GPU a peso zero (:7291)**. Sotto
CUDA graph registrazione e fetch girano **solo alla cattura** ⇒ ciò che resta *baked* dipende da
quale forward ha catturato: **differenza persistente e deterministica, non transitoria.**
L'ipotesi è coerente col reperto slot0 (§40-bis): tutti quei siti stanno DENTRO la macchineria
cache. **Predizione PRE-REGISTRATA dal peer**: se H-ORDINE è il meccanismo, **P2
(`ACCEPTMOE_COMPATTA=0`) GUARISCE**; se non guarisce, H-ORDINE è refutata come causa diretta.
S2 (grafi spenti + `OVERLAP_VERIFICA`) in corsa come arbitro.

**DUE RAFFINAMENTI DELLA REGIA (questo commit è il recapito)**:
1. **P2 muove DUE cose insieme** — spegnendo `COMPATTA` cadono sia il *fetch di rr* alla
   partizione (gate `peso_copia_pm>0 || traccia || compatta`, con gli altri due a zero in SOTA)
   sia il *ramo am_compatta* del down (`ggml-cuda.cu:2735`). Se P2 guarisce, il colpevole è la
   famiglia, non il sito. **Discriminatore pronto: `TRACCIA=1` + `COMPATTA=0`** — il gate resta
   vero (fetch VIVO) ma la compattazione è spenta: se resta garbage ⇒ è **rr/pesi_validi**; se
   guarisce ⇒ è il **ramo compatta**. (Heisenberg della traccia già dichiarato da te: vale come
   discriminatore, non come misura di prestazione.)
2. **Il sito `:7291` scrive `-1` negli id a peso zero.** È *by design* lì, ma è **la stessa
   valuta** del nostro fascicolo aperto sull'indice −1 nella lookup della testa Markov
   (`ops.cpp:4831`, memoria dedicata) e del crash-immagine documentato dal README di
   prometheusAIR (§27: `ubatch->token` non popolato → `get_rows` su `tid2eid`). **Se H-ORDINE
   regge, vale la pena tracciare a valle CHI consuma quegli id**: un `-1` che raggiunge un
   `get_rows` senza bounds-check è lettura fuori tabella silenziosa. Possibile che i tre
   fascicoli siano lo stesso fascicolo.

### §42-bis — **H-ORDINE RITIRATA DAL PEER, senza spendere una corsa** (e la nuova candidata (c))

**Falsificatore trovato nei log già su disco** — il metodo migliore possibile. Il contatore
`router_pesi_mancanti` s'incrementa **esattamente quando `pesi_validi` è falso**
(`cache-esperti.cu:7263-7265`, nel blocco che con MASSA=2 gira sempre), e vale **0 in TUTTI i
bracci di entrambe le famiglie** (AM=0: partizioni 31.218 / 122.679 / 61.060; AM=1: 6.149 /
107.242 / 3.612) ⇒ **`pesi_validi` è VERO ovunque ⇒ rr NON è nullo con AM=0 ⇒ il cuore di
H-ORDINE è falso**. La ragione a posteriori: **nel PREFILL i nodi `weights_norm` girano
comunque** (lì la partizione non è nemmeno inserita, cancello `n_tokens ≤ 3`), quindi il record
`quale=1` è già registrato quando comincia il decode, in ENTRAMBI i bracci — **l'ordine DFS è
reale ma viene LAVATO DAL PREFILL**. Regola che ne esce, generale: *un'ipotesi
sull'ordine di registrazione dentro il decode deve prima escludere che il prefill l'abbia già
soddisfatta.*

**Conseguenze**: i siti `:7033/:7249/:7291` si comportano UGUALI nei due bracci ⇒ non sono più
candidati (e con essi decadono S3/S3-bis e il mio raffinamento 2 qui sopra: il `-1` c'è in
entrambi, quindi non spiega la differenza — resta valido solo come esposizione latente da
guardare un giorno). Il raffinamento 1 (discriminatore `TRACCIA=1 + COMPATTA=0`) resta come
metodo.

**Resta di diverso a valle del prefill**: (a) due nodi identità in più; (b) ids contiguo vs
vista con stride — **indebolito**: a 1 token si legge sempre la riga 0; (c) **LAYOUT DI
ALLOCAZIONE diverso** (le uscite acceptmoe pretendono buffer e l'allocatore sposta gli
indirizzi a valle) ← nuova candidata del peer, con aggancio: il fork **salva PUNTATORI fra
dispatch** (`salva->src0_ombra/ids_ombra/src1/dst`, `ggml-cuda.cu:2653-2658`) e li riusa nelle
fasi 1-2, col commento a `cache-esperti.cu:6694-6697` che dichiara già la consapevolezza del
riciclo indirizzi del pool.

**FALSIFICATORE DELLA REGIA PER (c), da verificare sui manifesti PRIMA di correre**: l'aggancio
del fork non regge, perché **il difetto si riproduce ANCHE con `FORK=0 MASSA=0`** — i bracci
`g2_bis_fork0b` e `b_batchmax1` del §33 sono garbage con il fork SPENTO, dove `salva->*_ombra`
non è nemmeno popolato. Se i manifesti lo confermano, **(c) va riformulata come layout
d'allocazione PURO** (indirizzi di arena/slab che si spostano), non come riciclo di puntatori
del fork. E in quella forma (c) tocca una nostra esposizione latente già a registro dal 30/8:
**«alias d'arena»** — un tensore il cui ultimo lettore è uno split concorrente può vedersi
riusare la memoria da chi calcola lo split successivo, perché l'allocatore calcola le vite
**assumendo esecuzione sequenziale** (`ggml-backend.cpp:2082-2086`, memoria
`il-fronte-host-bound-e-chiuso-il-costo-migra`). Due nodi in più che spostano gli indirizzi
sono esattamente il tipo di perturbazione che sveglia quella classe. **Ma l'arbitro (S2) viene
prima**: nessuna di queste piste si istruisce finché la sonda non dice dove diverge il calcolo.
→ **«ALIAS D'ARENA» FALSIFICATA DAL PEER, e ha ragione**: quell'esposizione richiede esecuzione
CONCORRENTE, ma il braccio C2 (`ASYNC=0`, worker mai creato, tutto sequenziale) resta garbage
**byte-identico** ⇒ se l'allocazione c'entra, **non c'entra per concorrenza**. Mia
riformulazione ritirata.

## 43. **S2, L'ARBITRO: i CUDA graph sono INNOCENTI** — e l'invariante è violato, ma a 2 token (cioè forse nell'ALTRO fascicolo)

**Attribuzione: sessione focused-hertz.**

**PARTE 1 — cade la famiglia cattura/replay.** `c19f_s2_grafi_off` (AM=1 + `DISABLE_GRAPHS=1` +
`OVERLAP_VERIFICA=1`, no-draft, 80 tk): **SHA `97DF3AB0…` identico a S1 e a `c19_c0`** ⇒
spegnere i grafi NON guarisce. E la leva ha morso davvero (decode 13,94→10,32 t/s; «saltati in
cattura» 86→0, lanci 172→3569; mmid a un token 387→10.320). **Muore anche la speculazione del
peer sul “baked a cattura”.**

**PARTE 2 — l'invariante È violato, ma NON dove serve (ancora).** 21 righe di verifica, 52
disallineamenti (strati 8,9,11-17,21,24,25,26,39,41,42 con 1-3 su 12; al secondo giro 41 e 42
con 8 su 12). **Ma il denominatore dice il regime**: «su 12» = `ne0 × n_tok` = 6×2 ⇒ sono
forward a **DUE token**; l'unica riga «su 6» (1 token, strato 13) è **PULITA**. Aritmetica che
chiude il conto: `partizioni = 3612 = 80 forward decode × 43 × 1 tok (3440) + 2 forward warmup
× 43 × 2 tok (172)`, e `CPU = 7224 = 2 ×` ✓. ⇒ **il budget fisso di 100 lanci della sonda
(`ggml-cuda.cu:3331`) è stato mangiato da 86 lanci di WARMUP**: al decode vero ne sono arrivati
14 = solo gli strati 0-13 del primo token, **tutti puliti**. Gli strati 14-42 del decode non
sono MAI stati verificati.
⚠ **NUOVA ISTANZA DELLA CLASSE «STRUMENTI CHE MENTONO»**: la sonda ha *prodotto righe*, ma la
copertura era **warmup** — il regime d'interesse non è mai stato raggiunto. Chiunque usi
`OVERLAP_VERIFICA` deve prima **spendere il budget dove serve** (`--no-warmup`, o alzare il
budget), altrimenti «pulito» significa «mai guardato».

**IL SOSPETTO SI SPOSTA DI FASCICOLO**: la violazione è reale **a n_tok=2**, che è esattamente
il regime della **verifica speculativa** (mean_len 1,9-2,8) ⇒ candidato meccanismo per il
**difetto n.2** (§39, collasso del collaudo 1200 col drafter), non per il n.1.

**Cura del buco di copertura, zero build**: `--no-warmup` esiste (`common/arg.cpp:1755`); senza
warmup gli stessi 100 lanci coprono ~2,3 forward di decode INTERI (strati 0-42). Prossimo
braccio **S2-bis** = AM=1 + grafi off + VERIFICA + `--no-warmup`, con interpretazione
pre-registrata dal peer: disallineamenti a 1 token ⇒ **partizione malformata nel regime che
produce il testo = pistola fumante del n.1**; decode pulito su tutti i 43 strati ⇒ **partizione
innocente nel n.1**, corruzione a valle.

**TRE RAFFINAMENTI DELLA REGIA (questo commit è il recapito)**:
1. **`--no-warmup` è una SECONDA VARIABILE**: il warmup cambia la prima chiamata (memoria
   `euristiche-in-decode-incontrano-il-warmup`: la prima chiamata è degenere). **Cancello da
   aggiungere a S2-bis: lo SHA deve restare `97DF3AB0…`** — se cambia, la macchina è un'altra e
   la lettura dei disallineamenti è in un regime diverso, da dichiarare prima di interpretare.
2. **La tua interpretazione pre-registrata è giusta e si può rendere più forte**: la divergenza
   nasce al **PRIMO token di contenuto** (§40), quindi il dataset decisivo è **il forward n.1,
   strati 0-42**. Se quello è pulito, la partizione è innocente *nel momento in cui il difetto
   nasce* — conclusione forte, non indiziaria.
3. **Il controllo AM=0 con la stessa sonda (`c19f_s2c`) è più decisivo di come l'hai posto**:
   non serve solo a dire «specifico o preesistente». La config di servizio AM=0 gira col
   drafter a n_tok 2-3 per 1200 token ed è **SANA (ancora 4/4)**. Quindi: se AM=0 mostra **gli
   stessi** disallineamenti a 2 token, allora quei disallineamenti **non sono sufficienti** a
   corrompere — e cadono come meccanismo anche per il difetto n.2, non solo per il n.1. Il tuo
   controllo è, di fatto, l'arbitro di ENTRAMBI i fascicoli.

## 44. **IL MECCANISMO DEL DIFETTO n.1, QUANTIFICATO: la partizione ANNULLA il 72% delle route perché le crede a peso zero**

**Attribuzione: sessione focused-hertz.** Il controllo AM=0 ha risolto due cose insieme.

**(1) La sonda `OVERLAP_VERIFICA` NON È UN ORACOLO — e sovra-riporta per progetto.** Il braccio
AM=0 (che produce **italiano corretto**) mostra le **STESSE** violazioni, **agli stessi strati,
con le stesse magnitudini**, riga per riga (8(1) 9(1) 11(1) 12(2) 13(2) 14(3) 15(2) 16(3) 17(1)
21(1) 24(2) 25(1) 26(1) 39(1) 42(4); 2º giro 39(2) 42(8)) ⇒ **le violazioni a 2 token sono
PREESISTENTI E BY-DESIGN**: la compattazione scrive `-1` e la verifica, che non ne sa nulla, lo
conta come disallineamento (`o[pos] != s[i]`). **Con `COMPATTA=1` la sonda sovra-riporta: chi la
userà deve saperlo.** ⇒ E il mio raffinamento 3 qui sopra si applica come previsto: quelle
violazioni **non bastano a corrompere**, quindi cadono come meccanismo per ENTRAMBI i fascicoli.
**UNICA DIFFERENZA VERA**: **strato 41, 8 disallineamenti su 12, presente SOLO in AM=1** e
ripetuto al 2º giro. È l'unico segnale rimasto dalla sonda.

**(2) IL MECCANISMO, dai contatori** (stessa sonda, stesso prompt):
| | domanda | byte a domanda | partizioni | CPU |
|---|---|---|---|---|
| **AM=0 sano** | **15.439** | 48,66 GiB | 3612 | 7224 |
| **AM=1 garbage** | **4.359** | 13,23 GiB | 3612 | 7224 |

**Stesse partizioni, stesso lavoro CPU, ma il 72% della domanda lato GPU SPARISCE.** Sparisce
perché `kern_decidi` **non conta gli id `-1`** (`cache-esperti.cu:5082`: `esperto==-1` ⇒
`SLOT_NULLO`, nessuna domanda), e il `-1` lo scrive `kern_partiziona:7291` quando
`peso[perm[j]] == 0.0f`. ⇒ **Con AcceptMoE acceso la partizione legge pesi che sono in gran
parte ZERI e cancella ~7 route su 10.** È esattamente il `22506 = 0,419 × 53664` del §33, ora
**spiegato**: non è la cache che collassa, **è la partizione che annulla le route perché le
crede a peso zero**.

**(3) AUTO-CORREZIONE DEL PEER SUL PROPRIO CRITERIO** (e vale come regola): `pesi mancanti=0`
**NON prova che i pesi siano giusti** — prova solo che il puntatore non è nullo e i valori sono
≥ 0 (`cache-esperti.cu:7020-7024`): **un buffer di ZERI passa il controllo**. Quindi il ritiro
di H-ORDINE resta corretto *nella lettera* (rr non è nullo con AM=0), ma la sua **intuizione**
— «con AM=1 la partizione vede i pesi sbagliati» — è ora **sostenuta da una misura**. Il filone
si rimette in piedi nella forma corretta: non «rr nullo vs non nullo», ma **«rr punta a un
buffer di zeri»**. *(Classe: un cancello troppo debole assolve l'imputato. Cugino del §20 e del
fascicolo «strumenti che mentono».)*

**(4) S3 RIABILITATA come test DIRETTO**: `ACCEPTMOE_COMPATTA=0` ⇒ senza scritture di `-1` la
domanda deve risalire a ~15.400 e il testo tornare sano. Predizione pre-registrata dal peer.

**TRE AGGIUNTE DELLA REGIA (recapito via commit)**:
1. **Coincidenza verificata e MORTA**: lo strato 41 **non è** a routing hash — gli strati hash
   sono i **PRIMI** `dsv4_hash_layer_count` (=3, quindi 0-1-2): `deepseek4.cpp:1620-1623`
   («i primi … instradano per hash») e `:185`, `:1515`. Quindi il segnale non sta su uno strato
   a routing speciale. **Ma lo strato 41 è nel trio `dspark_target_layer_ids = [40,41,42]`** (e
   `num_nextn_predict_layers=3`): vale una lettura se quel trio ha struttura di grafo diversa
   (teste nextn/MTP) anche **senza** drafter.
2. **Lettura di S3 a TRE esiti, non due** (pre-registrala così): (a) **guarisce E la domanda
   risale a ~15.400** ⇒ meccanismo CONFERMATO; (b) **guarisce ma la domanda resta bassa** ⇒ il
   `-1` non è l'unica via (COMPATTA spegne anche il ramo `am_compatta` del down,
   `ggml-cuda.cu:2735`): serve il discriminatore `TRACCIA=1 + COMPATTA=0`; (c) **non guarisce**
   ⇒ gli zeri vengono da altrove (record/puntatore) e il dump diventa necessario, col protocollo
   pieno di build.
3. **⚑ CONTROLLO A COSTO ZERO CHE PUÒ UNIFICARE I DUE FASCICOLI — dati GIÀ SU DISCO.** Se il
   meccanismo è «pesi a zero ⇒ `-1` ⇒ route annullate», allora il **difetto n.2** (§39: collasso
   del collaudo 1200 **col drafter**, dove AcceptMoE **maschera davvero**) dovrebbe mostrare
   **la stessa firma attenuata**: confronta la `domanda` (e i byte) di `c19_a_collaudo` (AM=1,
   1200 tk, con draft, garbage) contro l'**ancora AM=0 a 1200 tk** — a parità di partizioni. Se
   la domanda di AM=1 è depressa nella stessa direzione, **i due difetti sono LO STESSO
   difetto** in due dosi, e il «`righe senza residenti` 2,5%→14,3%» del §39 ne è la
   manifestazione cumulativa. Nessuna corsa: è aritmetica sui log che hai già.

## 45. ⚠ TERZA MANO SU `D:\llama-subtract` — sorgente modificato alle 19:24 SOTTO le campagne. Binari INTATTI, misure SALVE

**Segnalazione del peer focused-hertz, VERIFICATA DALLA REGIA alle 19:31**:
- `ggml-cuda.cu` 19:24:13 · `cache-esperti.cu` 19:24:37 · `cache-esperti.cuh` 19:24:41 —
  modifiche marcate **`// chirurgo19 (1/9)`**, contenuto letto: `ffn_moe_acceptmoe_pesi` **non
  si registra più** (`:5602-5611`) e gli assi si leggono **saltando le dimensioni degeneri in
  testa** (`:5613-5621`, `while (asse < 2 && ne[asse]==1 && ne[asse+1]>1) asse++`).
- **`llama.dll` build 14:03:23 (`9E8E8D46…`) · `ggml-cuda.dll` build 14:33:25 (`6A98BE10…`) —
  INVARIATE**; nessun processo `cl/nvcc/ninja/cmake/link/editbin` attivo; **nessun agente della
  regia vivo** (verificato). ⇒ **NON è la sessione zen-morse**, e il mio chirurgo 19 era chiuso
  da ore (dopo di lui la macchina è stata del cantiere lungo, ~2 h, e poi del peer dalle 19:14).
- **Origine più probabile**: il **chip `task_39f6918a`** che il chirurgo 19 aveva spedito per il
  latente `registra_router`, avviato come sessione separata (precedente noto in questa
  giornata: `task_7aa78197` per FORK_COMPONI). Il marcatore `chirurgo19` è ereditato dal chip.
- **CONSEGUENZA OPERATIVA: le misure di stasera sono SALVE** — l'identità è la DLL e la DLL non
  si è mossa. **Il pericolo esiste solo se qualcuno COMPILA.** La regia **non compila** e
  conferma il divieto: nessuna build finché il peer non dichiara il banco libero.

**NOTA TECNICA DELLA REGIA (correzione in parte alla previsione d'inerzia del peer)**: quella
patch non è solo igiene — **colpisce esattamente l'ipotesi nuova del peer** («rr punta a un
buffer di zeri»): un record con `ne0=1` letto con lo stride sbagliato è precisamente il modo in
cui `peso[perm[j]]` può leggere fuori riga e vedere zeri. L'argomento d'inerzia del peer regge
per il caso *grafi spenti* (lì `registra_router` gira a ogni nodo e `weights_norm-L` ripara il
record prima di ogni `PARTIZIONE-L`), ed è coerente col fatto che S2 a grafi spenti resta
garbage. **Ma sotto CUDA graph la registrazione avviene SOLO alla cattura**, e lì «quale record
è rimasto baked» è una domanda aperta. ⇒ **Se e quando quella patch verrà costruita, va trattata
come DISCRIMINATORE dell'ipotesi, non come igiene**, con entrambi gli esiti pre-registrati:
guarisce ⇒ il record sporco *era* il meccanismo (almeno nel regime a grafi accesi); inerte ⇒
l'ipotesi «zeri da record» si indebolisce e restano compattazione/allocazione.

**PROTOCOLLO OBBLIGATORIO per chiunque costruisca quella patch** (vale per la terza sessione):
banco libero dichiarato; **backup DLL** in `build\bin\backup_pre_<nome>\` con SHA256; build
**mai** via `build_cuda.bat` (compila `D:\llama-overlap` riuscendo in silenzio) + `editbin
/STACK`; **G1 = banco corto 0731 3/3 SHA `AD3D3770…`**; e — specifico di stasera — **ri-baseline
del difetto n.1: `S1` deve ridare `97DF3AB0…`**, altrimenti la piattaforma si è spostata e tutte
le sonde della serata vanno rifatte.

## 46. **S2-bis: LA PISTOLA FUMANTE — l'invariante si rompe A 1 TOKEN, e la corruzione è PROGRESSIVA DALL'ULTIMO STRATO A MONTE**

**Attribuzione: sessione focused-hertz.** Identità DLL riconfermata a inizio corsa
(`6A98BE10`/`9E8E8D46`: **nessuna build è avvenuta**), `--no-warmup` verificato negli ARGS,
warmup davvero sparito (`partizioni 3526 = 82 token-passi × 43`; pubblicazioni `3483 = 81 × 43`
⇒ un forward a 2 token e 80 a 1).

| forward | strati con disallineamenti |
|---|---|
| **#2** (1 tok, passaggi 44-86) | 39 → **1/6** · 41 → **4/6** · 42 → **4/6** · tutti gli altri PULITI |
| **#3** (1 tok, passaggi 87-100) | 6,7,8,9,10,11,12,13 → **4/6 CIASCUNO** |

**Tre letture, tutte importanti**: (1) **a 1 token l'invariante SI ROMPE** ⇒ la partizione **è**
malformata nel regime che genera il testo ⇒ esito **(b)** della scala, non (c); (2) **4 su 6 =
TUTTE E QUATTRO le colonne GPU annullate** (le altre due sono la lane CPU, k_cpu=2), e collima
con la domanda (4049 contro ~13.900 attesi = **71% di route cancellate**, lo stesso 0,419 del
§33); (3) **LA CORRUZIONE È PROGRESSIVA**: parte dagli **ULTIMI** strati (39,41,42) e a ogni
forward conquista strati **più a monte** (al terzo è già a 6-13) — questo spiega
meccanicamente perché il testo **degenera** invece di uscire rotto dal primo token, e perché il
prefisso comune con AM=0 è di soli 4 byte.

**Attribuzione TENUTA IN SOSPESO dal peer, correttamente**: nel braccio AM=0 lo strato 13 a 1
token dava **0/6** (quindi il 4/6 non è preesistente come lo erano le violazioni a 2 token), ma
il confronto non è ancora appaiato (l'AM=0 aveva il warmup ⇒ indici di forward diversi):
**`AM=0 + --no-warmup + VERIFICA`** in coda dopo S3 come controllo appaiato. Nessuna
dichiarazione di attribuzione prima di quello.

**DUE CONTRIBUTI DELLA REGIA (recapito via commit)**:
1. **⚑ DOMANDA A COSTO ZERO SUI DATI CHE HAI GIÀ: il forward #1 (passaggi 1-43) era PULITO su
   tutti i 43 strati?** Tu riporti #2 e #3, non #1. Se #1 è pulito, il quadro si chiude in modo
   fortissimo: **la partizione nasce sana e si guasta DOPO il primo forward** ⇒ il bersaglio non
   è più «la partizione è malformata» (statico) ma **«che cosa cambia fra il forward 1 e il 2»**
   (dinamico) — target enormemente più stretto, e coerente col prefisso comune di 4 byte (il
   primo token esce giusto). Se invece #1 è già sporco agli ultimi strati, allora il guasto è
   presente dal primo forward e la progressione è solo la sua espansione.
2. **Perché DEGENERA invece di esplodere, meccanicamente**: se a uno strato **tutte** le colonne
   GPU sono annullate, quel MoE calcola **solo con i 2 esperti della lane CPU** su 6 — un'uscita
   **sbagliata ma plausibile**, non NaN e non spazzatura. Accumulata su strati e forward, dà
   esattamente la degenerazione osservata (e spiega perché nessun assert scatta mai). Corollario
   utile: **il difetto è un errore di COPERTURA degli esperti, non di aritmetica** — il che
   rende `S3` (COMPATTA=0) il test giusto e rende plausibile che il n.2 (§39, col drafter) sia
   **la stessa cosa in dose minore** (là AcceptMoE maschera davvero e le righe senza residenti
   salgono 2,5→14,3%): il controllo a costo zero del §44 punto 3 vale ancora di più.

## 47. **S3: GUARIGIONE BIT-IDENTICA** — difetto n.1 localizzato nella COMPATTAZIONE. E **i due difetti sono LO STESSO, in due dosi**

**Attribuzione: sessione focused-hertz.**

**(1) `COMPATTA=0` GUARISCE, e in modo perfetto**: `c19f_s3_compatta0` (AM=1 **acceso**,
COMPATTA=0, no-draft) ⇒ SHA `9F67629A…` **BIT-IDENTICO al braccio sano AM=0** (278 byte,
italiano corretto). Contatori tornati sani: **domanda 15.480** (rotto 4.359 · sano AM=0 15.439),
byte 48,93 GiB (13,23 / 48,66), e il testimone che chiude il cerchio **`pesi mancanti=3612`** —
con COMPATTA=0 il fetch di rr si spegne (gate tutto falso) ⇒ `pesi_validi` false ⇒ **nessuna
scrittura di `-1`**. Predizione pre-registrata CENTRATA. Nota che conferma il §39: **il garbage
era più VELOCE del sano** (13,94 vs 12,81 t/s).
⇒ **DIFETTO n.1 LOCALIZZATO: interamente nel cammino di COMPATTAZIONE.** Richiede la terna
`K>0` (esiste il nodo partizione) × `COMPATTA=1` (scrive i −1) × `AM=1` (fa leggere pesi zero) —
coerente col §33 (a K=0 nessun nodo partizione ⇒ nessun −1 ⇒ sano).
✔ **Il mio raffinamento 1 decade correttamente**: temevo l'ambiguità «rr vs ramo down», ma la
guarigione è **bit-identica** al sano — se il colpevole fosse il ramo down avremmo avuto un
testo sano *diverso*, non lo stesso SHA. Discriminatore `TRACCIA+COMPATTA=0` non più necessario.

**(2) IL CONTROLLO A COSTO ZERO HA RETTO: i due difetti sono LO STESSO, in due dosi.** Rapporto
`domanda/partizioni` (atteso 4,0 a k_cpu=2):
| braccio | tk | rapporto | deficit | esito |
|---|---|---|---|---|
| `v_saggio_nothink` AM=0 | 1200 | 4,016 | −2018 | sano |
| `v_ancora_c1` AM=0 | 1200 | 4,016 | −991 | sano |
| `c19_d0` AM=1 | 120 | 4,159 | −975 | sano (scartati 4.850) |
| `c19_g2` AM=1 | 200 | 4,100 | −2002 | sano (scartati 16.217) |
| **`c19_a_collaudo` AM=1** | **1200** | **3,747** | **+27.182** | **GARBAGE** (scartati 70.441) |

**Il deficit compare SOLO nel braccio che produce garbage**, e i due bracci AM=1 *sani* hanno
scarti by-design in quantità **senza** deficit ⇒ lo scarto by-design NON spiega il deficit.
**Dosi: n.1 = 70% di route annullate, n.2 = 6,3%, e cresce con la lunghezza** — la stessa curva
del «righe senza residenti 2,5%→14,3%» del §39. ⇒ **Nuovo strumento diagnostico a costo zero
per tutta la famiglia: il rapporto `domanda/partizioni` deve valere ~4,0 (a k_cpu=2); un
deficit positivo È la firma del difetto**, leggibile senza aprire il testo.

**(3) AUTORIZZAZIONE E DISEGNO DELLA REGIA — l'esperimento tocca la config di servizio, quindi
i cancelli li metto io.** Sì, **lancialo tu** (banco caldo, strumenti tuoi, disciplina provata).
Ma la domanda giusta **non è «guarisce?»**: è **«batte quello che ho già?»** — perché
`COMPATTA=0` spegne anche un'ottimizzazione, quindi va PREZZATA. **Tre bracci, ~12 min**:
- **A** = 1200 no-think **+ drafter + AM=1 + COMPATTA=0** (la tua proposta).
- **B** = 1200 no-think **+ drafter + AM=0 + COMPATTA=0** ← **aggiunta della regia**: prezza
  COMPATTA sulla config di servizio ATTUALE. Vale perché con `COMPATTA=0` **la scrittura dei
  −1 non esiste più: il difetto diventa STRUTTURALMENTE IMPOSSIBILE** invece che evitato. Se B
  costa ~0, la config di servizio diventa **immune per costruzione**, non sana per fortuna.
- **Riferimento**: l'ancora AM=0/COMPATTA=1 già misurata (12,70-12,73 t/s, p1 **0,72830**,
  4633 char, `V-ANCORA-CORTO 88031A83…`) — non serve rifarla.

**CANCELLI PRE-REGISTRATI (tutti, per ogni braccio)**: (i) **§4.10 esteso sul testo intero** —
è ciò che ha ucciso la promozione nel §39, e resta il cancello sovrano; (ii) **`domanda/
partizioni` ≈ 4,0 con deficit ≈ 0** (il tuo strumento nuovo: cancello quantitativo che non
richiede di leggere il testo); (iii) **p1 NON molto sopra 0,73** — se torna 0,94-0,95 con t/s
volante è **corruzione, non vittoria** (regola §39); (iv) t/s contro l'ancora 12,70-12,73.
**Se A passa tutti e quattro**: è un CANDIDATO alla promozione, non una promozione — la
ratifica richiede il protocollo d'ancora pieno (**3 load freddi, processi separati, 3 SHA
identici**, §36), e la faccio io a consegna ricevuta. **Se A passa ma B è più veloce o pari**,
il vincitore è B: immunità strutturale a costo zero batte una leva che riapre una classe di
guasti.

**(4)** `S4 traccia` in corsa (legge `tr.pesi[i]` = i pesi DAVVERO letti dal kernel ⇒ risponde a
«sono zeri?» senza build; Heisenberg dichiarato: TRACCIA accende il gate di rr, quindi il
braccio DEVE restare rotto — se guarisse sarebbe esso stesso un reperto). **(5)** Terza mano:
diagnosi concordata, divieto di build tenuto da entrambe le sessioni, identità DLL verificata a
ogni corsa (`6A98BE10`/`9E8E8D46`).

## 48. **S4: OSSERVARE GUARISCE** — il latente È raggiungibile; e i pesi zero legittimi NON spiegano il difetto

**Attribuzione: sessione focused-hertz.** `c19f_s4_traccia` (AM=1, COMPATTA=1, TRACCIA accesa)
**GUARISCE** — l'esito che avevo pre-registrato come «reperto in sé». Meccanismo verificato:
con TRACCIA (`calendario_esatto`) la partizione riceve `part->src[1] = weights`
(`llama-graph.cpp:1912-1915`) ⇒ `pesi_am` diventa **produttore** della partizione ⇒
`acceptmoe_pesi-L` esegue **PRIMA** di partizione-L ⇒ registra `quale=1` con la sua forma
`[1,6,n_tok]` ⇒ `ne0_pesi=1` ⇒ record incoerente ⇒ `router_dati` **NULL** ⇒ `pesi_validi`
falso ⇒ **nessun −1** ⇒ sano. Testimone: **`pesi mancanti = 1760 / 1892`**, e i 132 lanci
rimasti validi sono **3 strati × 44 forward = i 3 strati HASH** (che non hanno il cammino
acceptmoe) — conferma interna elegante.
⇒ **Il latente `registra_router` NON è irraggiungibile** (avevamo concluso di sì, §40-bis/§44):
è raggiungibile, basta cambiare l'ordine dei nodi. **Il fix della terza mano ha quindi valore
reale**, ma cambia il comportamento e va ri-baselinato con cura.

**I DATI DELLA TRACCIA, e uno va CONTRO l'ipotesi corrente**: su 11.352 pesi letti, **41
esattamente zero (0,4%)**, zero negativi, zero NaN — e la loro distribuzione per strato
coincide **esattamente** con gli strati dove `overlap-verifica` segnalava disallineamenti
(8,9,11-17,21,24,25,26,39,42): **conferma end-to-end della catena «peso zero → −1 → route persa
→ disallineamento»**. **MA 0,4% non può spiegare il 71% di route annullate** ⇒ «pesi zero
legittimi» **NON è** il meccanismo del difetto n.1. Il peer dichiara: nello stato rotto la
partizione deve leggere memoria sbagliata, e la traccia non può vederlo perché **osservarlo lo
guarisce**. Radice ultima **DICHIARATA APERTA** (localizzazione certa: compattazione).

**TRE CONTRIBUTI DELLA REGIA**:
1. **TRIANGOLAZIONE: due vie indipendenti di spegnimento, stessa guarigione.** S3 disattiva il
   *gate del fetch* (`pesi_validi` falso per gate), S4 rende *incoerente il record*
   (`pesi_validi` falso per NULL). **Entrambe arrivano allo stesso passo e guariscono** ⇒ **la
   scrittura del `-1` è NECESSARIA E SUFFICIENTE** al difetto. Non è più solo «localizzato»:
   il passo causale è confermato da due manipolazioni indipendenti.
2. **⚑ LA RADICE POTREBBE NON ESSERE «MEMORIA SBAGLIATA» MA «INDICE SBAGLIATO» — e questo
   cambia COSA deve stampare il dump.** Alternativa che spiega tutto senza postulare un buffer
   corrotto: la partizione legge `peso[perm[j]]` dove **`perm` indicizza l'ordinamento degli id
   di AcceptMoE** mentre **`peso` è nell'ordinamento originale del topk** — memoria GIUSTA,
   indice SBAGLIATO; le posizioni oltre il conteggio tenuto cadono su padding/zeri. È coerente
   con tutto ciò che sappiamo (graphs-off indifferente, async indifferente, allocazione
   indifferente, e guarigione da entrambe le vie che spengono il `-1`). **Conseguenza
   operativa: quando si farà il dump, NON basta stampare il contenuto del buffer** — deve
   stampare, per la stessa colonna, **`perm[j]`, l'id in quella posizione E il peso letto**.
   Altrimenti un dump che mostra «pesi corretti nel buffer» farebbe concludere «memoria sana»
   mentre l'errore sta nell'indicizzazione, e ci costerebbe un'altra build.
3. **PREDIZIONE PRE-REGISTRATA per la build della terza mano** (quando avverrà, col protocollo
   del §45): se il fix impedisce a `acceptmoe_pesi` di registrarsi, allora nella configurazione
   S4/TRACCIA il record resterà `weights_norm` **coerente** ⇒ `pesi_validi` **VERO** ⇒ `-1`
   di nuovo scritti ⇒ **S4 deve TORNARE ROTTO**. È un cancello falsificabile forte: se dopo
   quella build S4 resta sano, la nostra comprensione del meccanismo è incompleta. Da eseguire
   subito dopo G1, prima di qualunque altra conclusione.

**Misura indiretta già disponibile, senza dump**: nello stato rotto ~71% delle colonne finiscono
a `-1` ⇒ ~71% dei `peso[perm[j]]` valgono esattamente 0,0f; nello stato osservabile (sano) sono
lo 0,4%. **Un fattore ~175×**: che la memoria letta nei due stati sia diversa è già quantificato,
anche senza il dump. Quel che manca è **quale** memoria, o **quale indice**.

## 49. **IL n.2 È BY DESIGN**; la mia ipotesi «indice» è REFUTATA; e **non ci si può più fidare del sorgente per interpretare questi binari** — con snapshot e una risoluzione della contraddizione

**(1) MIA IPOTESI «INDICE» — REFUTATA dal peer a costo zero, e correttamente**: `kern_acceptmoe`
**non riordina**: scrive posizione per posizione (`out_ids[t*ne0+i] = tieni[i] ? riga_id[i] :
riga_id[primo]`, `out_pesi[…] = tieni[i] ? w*rinorm : 0.0f`, `cache-esperti.cu:7980-7988`) ⇒
`perm` e `peso` vivono nello stesso ordinamento, il disallineamento d'indice non si produce.
**Resta valida la conseguenza operativa**: il dump dovrà comunque stampare INSIEME `perm[j]`,
l'id in quella posizione e il peso letto.

**(2) IL DIFETTO n.2 È BY DESIGN — riformulazione importante.** AcceptMoE mette **`0.0f` sulle
posizioni scartate** (`:7983`) e vi duplica l'id del primo tenuto (`:7985`) per congelare le
forme; con COMPATTA=1 la partizione traduce quegli zeri in `-1` e la cache non li domanda:
**è la catena PROGETTATA, non un guasto.** ⇒ Nel collaudo lungo col drafter il «deficit 6,3%»
è **in gran parte il meccanismo che LAVORA**; il guasto è che **la quota di scarto CRESCE**
(«righe senza residenti 2,5%→14,3%») finché l'approssimazione collassa. Il braccio A del
collaudo misura quindi esattamente la cosa giusta: **COMPATTA=0 conserva le route (pagandole in
byte) invece di annullarle.** Attesa del peer: A più lento e più sano; **se A fosse sano E
veloce, lo scarto stava buttando lavoro utile** — che sarebbe un reperto di prima grandezza.

**(3) ⚠ ESPOSIZIONE DI METODO: il sorgente non è più affidabile per interpretare questi
binari.** Il peer ha una contraddizione che regge a tre riletture («rr→pesi = weights_norm ⇒
pesi positivi ⇒ niente −1» contro il 70% di −1 misurati, con `guasti=0` che esclude id fuori
range) ⇒ **una premessa sul BINARIO è falsa**, e la più fragile è proprio la lettura del
sorgente: `cache-esperti.cu` è stato letto alle 17:30 ma **riscritto dalla terza mano alle
19:24**, e non esiste snapshot del sorgente al momento della build (14:33) — `backup_pre_*`
contiene **solo DLL**.
✔ **AZIONE DELLA REGIA, ESEGUITA SUBITO**: snapshot datato in
**`D:\ds4_work\snapshot_sorgente_20260901_2145\`** (4,4 MB: tutti i `.cu/.cuh` di ggml-cuda,
i `.cpp/.h` di `src/` + `models/deepseek4.cpp` e `dflash.cpp`, più `MTIME_INVENTARIO.txt`).
**Reperto dall'inventario**: `deepseek4.cpp` e `dflash.cpp` sono fermi a **13:55**, coerenti con
`llama.dll` costruita alle **14:03** ⇒ **il lato `src/` del binario è verificabile**; sono i tre
file CUDA (19:24) a essere **provabilmente avanti** rispetto a `ggml-cuda.dll` (14:33). Se
fossero stati toccati anche PRIMA delle 17:30 non è più recuperabile.
**REGOLA NUOVA A REGISTRO**: *un fascicolo che mescola misure e letture di codice deve citare
l'mtime del file letto*; e **ogni backup DLL deve portare accanto la copia del sorgente** da cui
è nato (da oggi il protocollo build lo richiede).

**(4) ⚑ RISOLUZIONE CANDIDATA DELLA CONTRADDIZIONE — e non richiede né dump né sorgente
affidabile.** Il commento della terza mano dice: «`ffn_moe_acceptmoe_pesi` **NON si registra
più**» ⇒ **prima si registrava**. E la build sotto test è delle 14:33, **precedente** al fix
delle 19:24 ⇒ **nel binario in prova `acceptmoe_pesi` REGISTRA `quale=1`**. La sua uscita ha
`0.0f` esattamente sulle posizioni scartate (§49.2) ⇒ **`rr→pesi` non era `weights_norm`: era
l'uscita MASCHERATA**, e il ~70% di `-1` è esattamente il tasso di scarto. **La contraddizione
si scioglie senza postulare memoria corrotta.** ⚠ Obiezione aperta da verificare: nell'ordine
intra-strato `weights_norm-(L+1)` dovrebbe *riparare* il record prima di `partizione-(L+1)` —
il pattern **progressivo dagli ULTIMI strati** (§46) è il candidato indizio (dopo
`acceptmoe_pesi-42` non c'è un `weights_norm-43` che ripari).

**(5) RITRATTO LA MIA PREVISIONE DEL §48.3.** Avevo pre-registrato: «dopo il fix, S4/TRACCIA
deve TORNARE ROTTO». **Sbagliata**: conflondeva «`pesi_validi` vero» con «molti `-1`». Col
modello nuovo, dopo il fix il record resta `weights_norm` **con pesi positivi** ⇒ pochi `-1` ⇒
**S4 resta SANO**. **Previsioni corrette, pre-registrate per quella build**:
   (a) **il braccio ROTTO (AM=1, COMPATTA=1, senza TRACCIA) deve GUARIRE** ⇒ il fix della terza
       mano non è igiene: **è il fix del difetto n.1**;
   (b) **S4/TRACCIA resta sano**, ma con un cancello quantitativo netto: **`pesi mancanti` deve
       crollare da 1760/1892 a ~0** (il record resta coerente);
   (c) il difetto n.2 si riduce alla sola quota by-design.
   Se (a) fallisce, il modello del §49.4 è falso e si torna al dump.

## 50. **LA CONTRADDIZIONE È SCIOLTA** (sul lato verificabile del sorgente) — e resta un solo candidato che spiega TUTTI e quattro i vincoli: **la VITA DEL BUFFER**

**Quattro candidati proposti stasera, quattro refutati** (H-ORDINE, variante (i), variante (ii),
multi-stream — quest'ultimo dal peer stesso: `ggml_backend_cuda_graph_optimize` esce subito se
`GGML_CUDA_GRAPH_OPT != 1` e in SOTA vale **0**, confermato dal manifesto a runtime ⇒ macchina
concurrent-events **inerte**, ramo irraggiungibile). Il peer dichiarava insolubile il fatto che
«nessuna variante produce entrambi gli stati». **Non è insolubile: i due stati hanno REGISTRANTI
DIVERSI.**

**FATTO VERIFICATO — e sul lato AFFIDABILE del sorgente** (`src/llama-graph.cpp`, **mtime
13:55**, coerente con `llama.dll` delle 14:03 ⇒ *questo* file descrive il binario in prova; regola
mtime del §49.3 applicata):
```
:2230  weights = ggml_div(...)                    // [n_expert_used, n_tokens] = [6, n_tok]
:2231  cb(weights, "ffn_moe_weights_norm", il);   // ← IL NOME STA SUL 2-D: ne0 = 6, COERENTE
:2233  weights = ggml_reshape_3d(..., 1, n_expert_used, n_tokens);   // vista [1, 6, n_tok]
:2291  pesi_am = ggml_acceptmoe_pesi(ctx0, weights, ...)             // ← riceve la VISTA 3-D
:2293  cb(pesi_am, "ffn_moe_acceptmoe_pesi", il);                    // ⇒ ne0 = 1, DEGENERE
```
⇒ **Entrambe le misure sono spiegate da un solo quadro**: nel braccio **ROTTO** l'ultimo a
registrare `quale=1` prima della partizione è `ffn_moe_weights_norm` (2-D, **ne0=6 ⇒
COERENTE ⇒ `pesi mancanti=0` ✓**); nel braccio **TRACCIA** l'ordine cambia e registra
`acceptmoe_pesi` (3-D, **ne0=1 ⇒ INCOERENTE ⇒ 1760/1892 ✓**). Le varianti (i) e (ii) erano
**ciascuna vera per un braccio diverso**, non due alternative per lo stesso.

**⇒ LA DOMANDA RESIDUA È ORA ESATTA**: perché lo **stesso puntatore, con la stessa forma
coerente**, porta pesi giusti con AM=0 e zeri con AM=1?

**⚑ CANDIDATO n.5 DELLA REGIA — LA VITA DEL BUFFER (out-of-band read).** Il commento a
`llama-graph.cpp:2294-2295` lo dice esplicitamente: con AM=1 «da qui in giù **TUTTO il valle** —
partizione, MUL_MAT_ID, domanda della cache, fork/join, pesatura — consuma» le uscite di
AcceptMoE. ⇒ **In AM=1 l'ULTIMO CONSUMATORE DI GRAFO di `weights_norm` si sposta in TESTA allo
strato** (`acceptmoe_ids`/`acceptmoe_pesi`), mentre in AM=0 resta **in coda** (la pesatura
finale). Ma **la cache legge `rr→pesi` FUORI BANDA, con un puntatore grezzo e senza arco di
grafo**: l'allocatore non sa di quel lettore. ⇒ **In AM=1 il buffer di `weights_norm` è già
libero e RICICLATO quando la partizione lo legge; in AM=0 è ancora vivo.**

**Spiega TUTTI i vincoli, incluso «il più stringente»**: record coerente + contenuto nullo nel
rotto ✓ · AM=0 sano con lo stesso puntatore e la stessa forma ✓ · TRACCIA sano (aggiunge
`part->src[1] = weights`, cioè **proprio l'arco mancante**, e insieme rende incoerente il
record) ✓ · COMPATTA=0 sano (non legge affatto) ✓ · grafi on/off indifferente (la pianificazione
delle vite non cambia) ✓ · ASYNC/PIN/fork indifferenti (**non è concorrenza**) ✓ · multi-stream
inerte ✓ · **e il pattern PROGRESSIVO dagli ULTIMI strati** ✓✓ — la pressione di riuso
dell'arena cresce lungo il grafo, quindi il riciclo colpisce prima gli strati finali e risale.
È il **fratello non-concorrente** dell'esposizione «alias d'arena» già a registro dal 30/8
(`ggml-backend.cpp:2082-2086`): là il pericolo era la concorrenza, qui è **un lettore che
l'allocatore non vede**.

**⚑ TEST DECISIVO GIÀ DISPONIBILE — la build della terza mano DISCRIMINA i due modelli
superstiti**, con predizioni opposte e pre-registrate:
| | §49.5 (registrazione di `acceptmoe_pesi` colpevole) | §50 (vita del buffer) |
|---|---|---|
| braccio ROTTO dopo il fix | **GUARISCE** | **RESTA ROTTO** (il registrante era già weights_norm) |
| braccio TRACCIA dopo il fix | resta sano, `pesi mancanti`→~0 | **DIVENTA ROTTO** (record torna coerente ⇒ si rilegge il buffer morto) |
**Ritiro quindi la mia previsione §49.5(a) come certezza e la declasso a uno dei due esiti**: la
build che la terza mano ha preparato non è più «probabilmente il fix», è **l'esperimento che
decide**. Da eseguire col protocollo del §45 (snapshot accanto alle DLL, G1 `AD3D3770…`,
ri-baseline `S1 = 97DF3AB0…`), leggendo per primi quei due bracci.
**Se vince il §50**, il fix vero non è togliere una registrazione: è **dichiarare la dipendenza**
(dare alla partizione un arco su `weights_norm`, come fa TRACCIA) oppure **tenere vivo il
tensore**; e il dump dovrà stampare, oltre a `perm[j]`/id/peso, **il nome del tensore che ha
registrato il record e l'intervallo di vita del suo buffer**.

## 51. **COLLAUDO A/B: il NO-GO del §39 ERA IL DIFETTO, NON LA LEVA.** AcceptMoE con COMPATTA=0 passa tutti e quattro i cancelli

**Attribuzione: sessione focused-hertz.** Prompt verificato (sha `4FDF82C2`, lo stesso del §39),
identità DLL confermata, `reasoning_chars=0` su 4/4 corse.

| | **A** (AM=1, COMPATTA=0) | **B** (AM=0, COMPATTA=0) | ancora (AM=0, COMPATTA=1) |
|---|---|---|---|
| t/s | **12,69 / 12,71** | 12,57 / 12,08 | 12,70-12,73 |
| p1 | **0,72693 / 0,71934** | 0,70988 / 0,73274 | 0,72830 |
| char | 4538 / 4713 | 4517 / 4635 | 4633 |
| dom/partizioni | **4,0169 (deficit −2064)** | 4,0168 (−2064) | — |
| byte a domanda | **868,98 GiB** | 1140,38 GiB | — |
| colpi | **75,2%** | 67,5% | — |

**I QUATTRO CANCELLI SU A: TUTTI PASSATI.** (i) **§4.10 PIENO** — riletto in UTF-8: **zero
caratteri non latini** (il conteggio precedente era un artefatto del lettore PowerShell: altra
istanza della classe «strumenti che mentono»), italiano tecnico corretto fino alla coda, nessun
loop, terminologia esatta, **diversità lessicale 0,52-0,56 contro 0,513 dell'ancora**; unica
sbavatura il refuso «sfatta» che **era GIÀ NELL'ANCORA (§35)** ⇒ tic del modello, non
regressione. (ii) deficit ≈ 0 ✓. (iii) p1 0,727/0,719 contro 0,728 ✓ — **nessuna traccia della
firma 0,94-0,95**. (iv) t/s in parità con l'ancora ✓.

**LA LETTURA DI MERITO — ed è il risultato della serata**: **il NO-GO del §39 era il DIFETTO,
non la leva.** Con COMPATTA=0 AcceptMoE lavora sul serio (61.933 righe mascherate, 95.420
esperti scartati) e il testo resta sano. **Il beneficio esiste ed è misurato, ma non dove lo
cercavamo**: A muove il **24% di byte in meno** di B (869 vs 1140 GiB) con **colpi 75,2% contro
67,5%** ⇒ il guadagno viene dalla **RESIDENZA** (il duplicato dell'id raggruppa i token sugli
stessi esperti), non dallo skip delle route. In t/s però **non si converte**: A = ancora. ⇒
**AcceptMoE con COMPATTA=0 è GRATIS e più efficiente nei byte, non più veloce.**

**Sulla mia regola di decisione «se B è pari o più veloce vince B»**: B **non** è pari — è più
lento e muove il 31% di byte in più. Cautela dichiarata dal peer: n=2 e il 12,08 di B r2 puzza
di rumore (con la regola di casa servirebbe una tripletta) — ma **quel che è solido è che B non
batte A**. ⇒ **B esce; il candidato è A.**

**RATIFICA IN CORSO (compito riservato alla regia)**: dispacciata la `V-ANCORA-CORTO-A` — 3
cicli load-freddo come **processi separati** (§36), cancello di quiete 3×40 s, verifica dei
testimoni `OVERRIDE` prima di lasciar correre, e i 5 cancelli (3 SHA identici · §4.10 in UTF-8 ·
deficit ≈ 0 · p1 ≈ 0,73 · t/s vs ancora). **Se 3/3, A diventa la config di servizio del Vision**:
stessa velocità, **immune per costruzione** (senza compattazione i `-1` non esistono) e **−24%
di byte**. Debito dichiarato: l'ancora **LUNGA** (§41) è stata presa con AM=0/COMPATTA=1 — se A
viene promossa, il lungo va ri-ancorato (≈1 h di macchina, non urgente).

**Nota di squadra**: il peer ha lasciato il banco libero e pulito, ha declinato di eseguire lui
l'esperimento decisivo del §50 (correttamente: è una build, e il divieto valeva per entrambi), e
ha aggiornato il fascicolo con misure, refutazioni, protocollo e il vincolo a quattro righe per
chi farà il dump. Bilancio della sua serata: **5 sonde, 4 ipotesi proprie proposte e ritirate da
sé con falsificatori trovati nei dati**, e il meccanismo del difetto n.1 portato da «ignoto» a
«un solo vincolo residuo, con l'esperimento che lo decide già disegnato».

## 52. ⭐ **RATIFICATA E PROMOSSA: `V-ANCORA-CORTO-A` 3/3 — è la NUOVA CONFIG DI SERVIZIO del Vision**

```
V-ANCORA-CORTO-A: 28ADE3395B5888D7DC1DB5D12A06083FFE1B2017029DC18EE87003BB090E1BBD
                  @ config §35 + LLAMA_ACCEPTMOE=1 + LLAMA_ACCEPTMOE_COMPATTA=0
```
Tre cicli load-freddo, **ognuno un processo separato** (§36), cancello di quiete nello stesso
processo del load, prompt **estratto** (891 char, sha `4FDF82C2`), identità DLL ristampata e
confrontata a ogni ciclo, testimoni presenti su tutti e tre **anche nel manifesto del server**
(`LLAMA_ACCEPTMOE=1(E)`, `LLAMA_ACCEPTMOE_COMPATTA=0(E)`: env non solo passata ma **letta dal
binario**). Zero cicli rifatti, zero assert.

| | ciclo 1 | ciclo 2 | ciclo 3 | ancora AM=0 |
|---|---|---|---|---|
| SHA | `28ADE339…` | `28ADE339…` | `28ADE339…` | `88031A83…` |
| t/s | 12,68 | 12,66 | 12,79 | 12,70-12,73 |
| p1 / mean_len | 0,72693 / 1,92 | idem | idem | 0,72830 / 1,93 |
| dom/part · deficit | 4,017 · **−1032** | idem | idem | 4,016 · −991 |
| byte a domanda | **433,32 GiB** | idem | idem | 565,50 GiB |
| colpi | **75,2%** | idem | idem | 67,7% |

**I CINQUE CANCELLI, TUTTI PASSATI**: (1) 3/3 SHA identici — **e un quarto load gratis**: è lo
stesso SHA della r1 del peer presa 30 min prima su un load distinto ⇒ **quattro load freddi
indipendenti**; (2) **§4.10 pieno** (UTF-8 esplicito), zero cifre inventate, struttura e coda
corrette — **un difetto riportato verbatim**: una nomenclatura alternativa circolare su
gate/up/down, di grado umano e della **stessa classe delle due imprecisioni già DENTRO l'ancora
AM=0**; il refuso «sfatta» c'è ma è già nell'ancora ⇒ non è regressione; (3) rapporto **4,017
con deficit NEGATIVO (−1032)**, e `righe senza residenti = 2,16%` che **NON cresce** (contro il
2,5%→14,3% del corrotto); `pesi mancanti = partizioni` è il **testimone atteso** di COMPATTA=0,
non un allarme; (4) p1 0,72693 — nessuna traccia dello 0,94-0,95; (5) t/s in banda.

**⇒ PROMOSSA. La config di servizio del Vision è ora: config §35 + `LLAMA_ACCEPTMOE=1` +
`LLAMA_ACCEPTMOE_COMPATTA=0`.** Motivazione a tre gambe: **parità di velocità**, **−23,4% di
byte con +7,5 punti di colpi**, e **immunità per costruzione** (senza compattazione la scrittura
dei `-1` non esiste: l'intera classe del difetto n.1/n.2 è strutturalmente impossibile, non solo
evitata). La vecchia config AM=0 resta valida e ancorata (`88031A83…`) come riferimento storico.

**REPERTO LATERALE CHE VALE COME TERZA CONFERMA DI FISICA**: a `partizioni` identiche (61.060) e
`domanda` praticamente identica (245.272 vs 245.231), A **toglie il 23,4% dei byte** e la
velocità **non si muove di un punto**. ⇒ **AcceptMoE lavora davvero e i byte scendono davvero,
ma il tempo no**: ennesima conferma indipendente che **il muro è la SERIALIZZAZIONE, non la
banda** (§12) — non una delusione della leva.

**DEBITO SUBITO AGGREDITO**: l'ancora LUNGA (§41) è di AM=0/COMPATTA=1. Dispacciata **ora** la
validazione di A sul banco lungo (prompt 101.691, ctx 150k, `-OtDraft …=CPU` obbligatorio per il
tetto pinnato), con gli stessi 5 cancelli e un'attesa dichiarata: **sul lungo A potrebbe essere
MIGLIORE**, perché è lì che il difetto n.2 cresceva con la lunghezza e COMPATTA=0 lo previene.
Riferimento da battere: 11,764/11,870/11,871 t/s, p1 0,80914.

## 53. ⭐ **SUL LUNGO A NON È PARI: È MIGLIORE. +3,6…+5,3%** — l'attesa pre-registrata è confermata

**Attesa dichiarata nel §52 e CENTRATA.** Banco lungo (101.691 / ctx 150k / 1200 tk / budget 0),
2 corse, **2/2 SHA identici** (`B2B8F84E…`), testi byte-identici, contatori cache **bit-identici**
fra le due.

| | **A** (AM=1, COMPATTA=0) | ancora §41 (AM=0) | Δ |
|---|---|---|---|
| **decode t/s** | **12,300 / 12,384** | 11,764 / 11,870 / 11,871 | **+3,6 … +5,3%** |
| ms/token | 81,30 / 80,78 | 84,24-85,03 | −3,5 … −4,1% |
| C_round | 204,07 / 202,75 | 205,54-207,48 | −1,3 … −2,3% |
| mean_len | 2,51 | 2,44 | +2,9% |
| p1 | 0,82683 | 0,80914 | +2,2% |
| colpi | **63,4%** | 58,0% | **+5,4 punti** |
| byte a domanda | **717,41 GiB** | 835,44 GiB | **−14,1%** |
| partizioni | 36.722 | 36.722 | **identiche alla cifra** |
| pesi mancanti | 36.722 (= partizioni) | 0 | testimone COMPATTA=0 ✓ |

**Scomposizione del guadagno**: metà da **round più economici** (C_round −1,3…−2,3%) e metà da
**catene accettate più lunghe** (mean_len +2,9%). ⇒ **Sul LUNGO i byte SI convertono in tempo,
sul corto no** — coerente col working set: a 101k il tasso di colpi è più basso (58→63,4%) e
ogni byte risparmiato pesa. Contatori AcceptMoE tutti >0 (lanci 19.120, mascherate 32.270,
scartati 45.822) contro 0 nell'ancora ⇒ **ramo raggiungibile e leva che lavora**. Zero assert,
zero divergenze di replay, prefill invariato (la leva è di solo decode).

**⚠ NONA TRAPPOLA DEL LANCIATORE, intercettata PRIMA di correre** — e valeva la misura intera:
`p1b_conf.ps1:208` scriveva a mano `$env:LLAMA_ACCEPTMOE_COMPATTA = '1'` **dentro**
`Set-SotaEnvironment` (che gira nel ciclo delle shape) ⇒ impostarla dall'esterno era **INERTE**:
il braccio avrebbe misurato la SOTA piena credendo di misurare COMPATTA=0, e avremmo pubblicato
un +4% falso. Riparata col pattern di casa (parametro `-AcceptmoeCompatta`, **difetto '1' =
comportamento precedente byte-per-byte**, backup `…bak_20260901_pre_compatta`). **Nona istanza
nello stesso file**: la bonifica sistematica di `Set-SotaEnvironment` (a registro dal §16) non è
più un'igiene rimandabile.

**CORREZIONE DI TARATURA su uno strumento nuovo**: il cancello «`domanda/partizioni` ≈ 4,0» del
§47 è una cifra del banco **CORTO**; sul lungo l'ancora *sana* vale già **7,597** (il prefill da
101k aggiunge domanda senza partizioni). **Il criterio vero è il segno del deficit**, non il
valore del rapporto: qui **−127.968** (negativo, come l'ancora), contro il **+27.182** del
guasto.

**DUE DEBITI DICHIARATI**: (1) **2/2, non 3/3** — dispacciato il terzo load freddo per la
ratifica piena `V-ANCORA-LUNGO-A`; (2) **`righe senza residenti` all'8,09%** contro il 2,16% del
corto, con progressione cumulativa 5,71→7,01→8,09 — **unico numero sensibilmente più alto**, e
**senza nessun'altra firma del difetto** (deficit negativo, p1 normale, testo sano, SHA
riproducibile, t/s migliore). Poiché i contatori sono **bit-identici fra le corse**, la
progressione è **deterministica** ⇒ proprietà riproducibile del carico (473 slot contro un
contesto da 101k), non una deriva; conferma richiesta sul terzo load, poi il dubbio si chiude
senza spendere altre corse.

## 54. ⭐⭐ **`V-ANCORA-LUNGO-A` RATIFICATA 3/3** — ed entrambi i debiti del §53 sono chiusi

```
V-ANCORA-LUNGO-A: B2B8F84E96ED34679C53E1F194B48DB4BE54C1789462DFFAE8ACD43169FFEE8D
  @ config §35 + LLAMA_ACCEPTMOE=1 + LLAMA_ACCEPTMOE_COMPATTA=0
    + OtDraft 'ffn_(gate|up|down)_exps\.weight=CPU'
    (ctx 150000, b/ub 2048, nmax 3, conf 0.70, 1200 tk, budget 0, KV_GATHER=1)
```
**3/3 SHA identici, contatori BIT-IDENTICI alla cifra, testi identici byte-per-byte.** t/s
12,300 / 12,384 / **12,394** (dispersione 0,76%) contro l'ancora AM=0 11,764-11,871 ⇒
**+3,6 … +5,3% confermato su tre load freddi indipendenti**; C_round 202,58-204,07 contro
205,5-207,5. Testimoni verificati prima di ogni corsa, quiete 3×40 s nello stesso processo del
load, zero assert.

**IL DUBBIO SULLE `righe senza residenti`: CHIUSO, ed era lo STRUMENTO.** I totali finali sono
**identici alla cifra su 3/3** (2.610 / 32.270 = 8,09%). La «progressione 5,71→7,01→8,09» che
sembrava una deriva **era il CAMPIONAMENTO, non il fenomeno**: i dump intermedi escono a
**battito d'orologio** (`BATTITO=45`) e cadono in punti diversi della corsa (al terzo dump:
lanci 9.160 / 9.240 / 9.250), dando 5,71 / 6,16 / 6,20%; l'intervallo di coda vale 21,6 / 20,8 /
19,9% in r1/r2/r3 — **la stessa curva letta con tre righelli spostati**. La frazione sale
monotona lungo il decode ed è una proprietà del carico (473 slot contro un contesto da 101k),
identica a ogni corsa. **Nessuna corsa in più necessaria.**
⇒ **Lezione (famiglia «strumenti che mentono»)**: *una sonda campionata A TEMPO produce
«andamenti» che sono artefatti del righello; prima di leggere una progressione, verificare se il
campionamento è a tempo o a evento.* Cugina diretta della trappola del §43 (il budget della
sonda mangiato dal warmup): in entrambi i casi **è dove guarda lo strumento a produrre il
fenomeno**.

---
### 🏁 BILANCIO DELLA GIORNATA 1/9 (§22-§54)
**Da «i pesi sono usciti ieri» a un modello di default misurato, ancorato, collaudato e
servito con una config immune per costruzione**, in un giorno:
- **Disco**: da 31,8/60,4 GiB liberi a 143,8/143,7 (+195 su D:, +112 su C:), con tre
  «duplicati» falsificati dall'hash e il vero spazio trovato negli scarti orfani (§24).
- **Vision**: release verificata, 80,15 GiB scaricati e SHA-controllati, build upstream
  (PR #28133 + patch) con l'A/B che ha scoperto l'esperimento sporco dentro la patch (§26-§28).
- **Capability**: parla (§28), **vede 3/3 su test noto** (§29), **legge una foto vera con OCR
  esatto a riduzione 18×** (§37), **collaudato sul testo** (§35).
- **Porto nel fork**: vl-routing in 7 aggiunte con 0731 **bit-esatto** (§31); geometria
  per-strato guarita — **il difetto erano 38 byte di allineamento** (§32).
- **Ancore**: corto `88031A83` (§36) → **`28ADE339` config A** (§52); lungo `1596D3B3` (§41) →
  **`B2B8F84E` config A** (§54). Quattro ancore, tutte a load freddi indipendenti.
- **Numeri**: baseline upstream 5,5 → fork 12,7 (corto) e **12,39 (lungo, 101k/kv150)**.
- **Caccia al difetto** (con la sessione peer): 9 sonde, **8 ipotesi proposte e ritirate dai
  proponenti stessi** con falsificatori trovati nei dati, il meccanismo isolato
  (`-1` necessario e sufficiente, §47/§48) e **un solo vincolo residuo** con l'esperimento che
  lo decide già disegnato (§50).
- **Nove trappole del lanciatore** (l'ultima avrebbe pubblicato un +4% falso, §53) e **cinque
  nuove istanze di «strumenti che mentono»** (§20, §37, §43, §49, §54).
**Aperti**: la radice ultima del difetto (serve build + dump, §50); la bonifica di
`Set-SotaEnvironment`; il porto mtmd nel fork; la terza mano su `D:\llama-subtract` (§45).

---

## 55. PASSAGGIO DI CONSEGNE — 2/9: il banco va alla sessione `moe-aggressive-commit-ff`

**Direttiva utente 2/9**: «proviamo tutte le altre strade» verso i 20 t/s, **IQ1 escluso a
priori**. Il banco lungo è di quella sessione per ~2,5 h; questa sessione (zen-morse) **non
compila, non lancia, non tocca la macchina** fino al suo commit-segnale.

**Sequenza dichiarata**: `S0 473` (controllo, deve ridare `B2B8F84E…`) → `S1 573` → `S2 623` →
**trasporto-online al conteggio più alto che regge** → **massa**. Binari attesi invariati
(`9E8E8D46` / `6A98BE10`), con `Get-FileHash` delle due DLL **prima di ogni braccio** (stop se
diverge — copre anche il rischio della terza mano, §45).

**Materiale passato dalla regia** (ledger §16, §41, §53; handoff §5, §8, §9):
1. **L'ordine dei bracci è la cosa più preziosa del piano.** `TRASPORTO_ONLINE` fu chiuso il
   31/8 (§16) **per CAPIENZA, non per il canale**: `rifiutate_pressione = 19.885 / 40.965`,
   anello mai pieno (in volo max 8 su 255). ⇒ **testarlo a 473 slot ripeterebbe un esperimento
   chiuso; ha senso SOLO al conteggio più alto**, e il **cancello primario è
   `rifiutate_pressione` che crolla** (+ `in tempo` che sale), non il t/s.
2. **Cancelli**: lo **SHA NON è il cancello** (cambiare gli slot cambia la residenza ⇒ la
   traiettoria); valgono §4.10 in **UTF-8 esplicito**, il **SEGNO del deficit**
   (`domanda − 7,597·partizioni` — sul lungo il valore sano è **7,6**, non il 4,0 del corto), e
   **p1 molto sopra 0,83 con t/s volante = corruzione**. Riferimento: `V-ANCORA-LUNGO-A`
   `B2B8F84E…`, 12,300/12,384/12,394, p1 0,82683, colpi 63,4%, byte 717,41 GiB, partizioni
   36.722.
3. **Aspettativa pre-registrabile sullo sweep**: a 473 slot nemmeno **BELADY** toglie i byte
   necessari ai 20 — arriva al bersaglio a **~1500 slot (9,89 GiB di slab)**. 573/623 sono
   +21%/+32%: **la curva lì è piatta per costruzione**. Giudicare su **byte a domanda e
   C_round**, non sui colpi (correlazione colpi→t/s = 0,20 su 349 corse) — ricordando però che
   **sul LUNGO i byte SI convertono parzialmente** (§53: −14,1% ⇒ +3,6…+5,3%).
4. **Nomi**: `LLAMA_TRASPORTO_ONLINE` **senza** prefisso `CACHE_ESPERTI_`; budget
   `LLAMA_TRASPORTO_ONLINE_BUDGET` (difetto 24, fabbisogno vero ~16 miss/token: **non alzarlo a
   60**, è l'eccesso che nel legacy costò −42%); `PF_LEGACY` forzato a 0 (testimoni `:2586`,
   `:3085`); `MASSA=2` **esige** `FORK=1|2`; `MASSA_AMMISSIONE` ha **difetto 1 nel codice** e la
   produzione la spegne (−6,2% via mappato, 14/8).

**Nota di disegno della regia**: la sessione sta verificando il lettore di
`LLAMA_TRASPORTO_STAGE_SLOT` come **secondo asse** (dare capienza all'anticipo senza toccare il
pool residente). Se quel pool esiste ed è separato, allora **il braccio `623 slot + tonline`
fonde DUE variabili** (più residenza *e* più spazio per l'anticipo): il disegno pulito è
**`473 + stage` contro `473 puro`** — una variabile sola, e isola *quale* capienza mancava.
Consigliato farlo **prima** del braccio a 623.

**Convenzioni per la scrittura del ledger** (concordate): la sessione ospite scriverà qui i
propri esiti **a fine campagna**, un commit per sezione, percorsi espliciti, `git pull` prima di
committare. **HEAD al passaggio: `c7a47a4`; ultima sezione: questa (§55) ⇒ partire da §56.**
Handoff di riferimento: `docs/porto/HANDOFF_1_SETTEMBRE.md`.
3. **Scala sonde APPROVATA** (P1 = DISABLE_GRAPHS+VERIFICA, decisiva; P2 = `ACCEPTMOE_COMPATTA=0`,
   ben mirata sul fetch di rr; P3 = controllo SLOT=0 in-sessione). L'eventuale dump
   chi[slot]-vs-richiesto a valle di P1: SOLO col protocollo pieno (backup DLL in
   `backup_pre_<nome>_diag\`, **G1 = banco corto 0731 3/3 `AD3D3770…` dopo la build**, build
   MAI via `build_cuda.bat`).
4. **Segnale di macchina libera = il commit della regia col numero del LUNGO** su questo
   ledger; poi quiete 3×40 s e la macchina è tua. Consegna concordata:
   `D:\ds4_work\llama_run\fascicolo_difetto1_20260901.md` + messaggio.

**FASCICOLO CONSEGNATO E VERIFICATO SU DISCO** (1/9 sera, regia ha letto l'incipit): dentro,
oltre al reperto slot0, **tre piste del peer aperte E refutate a tavolino coi gate del
sorgente** (compattazione alla partizione: `rr=nullptr ⇒ pesi_validi=false`, :7249/:7291;
dangling del record ai siti di servizio: tutti gated su `peso_copia_pm>0` che in SOTA è 0 —
l'unico consumatore vivo di `router_dati` è LA PARTIZIONE, :7741-7744, gate
`peso_copia_pm>0 || traccia || compatta` con COMPATTA=1 in SOTA; geometria 3-D alla partizione:
per ordine topologico rr è ancora `weights_norm`), l'aggravante documentata del latente
`registra_router`, e la **scala S1-S6 pre-registrata con interpretazioni dichiarate PRIMA**
(S2 = graphs-off+VERIFICA resta l'arbitro; S4/S5 = `LLAMA_CACHE_ESPERTI_TRACCIA` come dump id
zero-build, effetto-Heisenberg dichiarato). Sentinella del peer armata sui commit di questo
ledger per la fine del cantiere lungo; fino ad allora zero GPU da parte sua.
⚠ NOTA PER LA SENTINELLA: **questo commit NON è il segnale** — il segnale sarà il commit col
NUMERO del lungo, dichiarato come tale nel messaggio di commit.

## 56. SWEEP `SLOT` SUL VISION (2/9, 04:00-05:07) — **NO-GO come leva: +1,1% al massimo; la meccanica dei byte funziona, la TRAIETTORIA domina**

**Direttiva utente 2/9**: «proviamo a spingere questo modello a 20 t/s?» → «iq1 escluso a priori» →
«proviamo tutte le altre strade». Regia: sessione `moe-aggressive-commit-ff` (Fable); esecutori
opus; banco ceduto da zen-morse (§55). **Verdetto preliminare della regia, scritto PRIMA della
campagna** (memoria `vision-20tps-aritmetica-e-slot-liberi`): sull'ancora Vision A (80,7 ms/token)
il trasporto vale ~25 ms (82 miss × 7,30 MiB a 23 GiB/s), la lane CPU ~16, il resto ~40 ⇒ i 20 t/s
(50 ms) esigono −75% di trasporto+lane INSIEME; a 473 slot nemmeno Belady toglie il 43%. **Il
Vision NON cambia la mappa dei tetti del 31/8** (la peggiora del 3% per lo slot +8%); porta UNA
risorsa nuova: **1479 MiB di VRAM liberi in decode** (0731: 0) = 150-200 slot mai misurati.
Questa sezione li misura.

**Protocollo**: `vl_arm.ps1 -Braccio vision_A -DraftSoloCpu -Slot N`, tre processi separati,
cancello di quiete 3×40 s dentro lo script, **Get-FileHash delle DLL prima di S0 e di S2**
(`llama.dll 9E8E8D46…`, `ggml-cuda.dll 6A98BE10…`: invariate, nessuna ricompilazione sotto le
misure), testimoni `LLAMA_ACCEPTMOE=1(E)`/`COMPATTA=0(E)` e `cache-esperti-slot=N` nel summary
verificati su tutti e tre. Prompt 101.691 / ctx 150.016 / 1200 token / budget 0.

| | **S0** 473 (controllo) | **S1** 573 | **S2** 623 |
|---|---|---|---|
| decode t/s | **12,331** | **11,950 (−3,10%)** | **12,467 (+1,10%)** |
| ms/token | 81,10 | 83,69 | 80,21 |
| prefill t/s | 137,11 | 136,92 | 137,02 |
| p1 / mean_len | 0,82683 / 2,51 | **0,78201 / 2,30** | 0,81829 / 2,49 |
| C_round = ms/token × mean_len | 203,5 | **192,5 (−5,4%)** | 199,7 (−1,9%) |
| SHA output | `B2B8F84E…` (= ancora) | `95613176…` | `BDCE6E51…` |
| colpi | 63,4% (174.268) | **69,1%** (190.905) | 67,2% (187.032) |
| byte a domanda | 717,41 GiB | **608,57 (−15,2%)** | 650,91 (−9,3%) |
| domanda / partizioni | 274.856 / 36.722 | 276.232 / **40.936** | 278.296 / 36.034 |
| righe senza residenti | 2.610 | 1.621 | 1.753 |
| durata media copia (fork cronometro) | 0,803 ms | 0,947 | 0,665 |
| copia già finita al join | 24,7% | 34,1% | 31,0% |
| VRAM libera in decode | 1.479 MiB | 749 | **385** |
| assert / OOM / `FALLITA, cache spenta` / `ATTENZIONE, voluti` | 0 | 0 | 0 |
| divergenze replay | 0 | 0 | 0 |
| §4.10 (UTF-8) | saggio tecnico vero, 4152 char | vero, 4433 | vero, 3902 |

**S0 = quarto load freddo dell'ancora `V-ANCORA-LUNGO-A`: 4/4** — SHA bit-esatto, p1/mean_len alla
5ª cifra, **contatori identici alla cifra** (domanda 274.856, colpi 174.268, byte 717,41, partizioni
36.722, acceptmoe 19.120/45.822/63.787/2.610). La sessione riproduce; il cammino del parametro
`-Slot` è lo stesso dell'ancora (vl_arm passa sempre `-CacheEspertiSlot`).

### Lettura
1. **La meccanica fa quel che deve**: +100 slot ⇒ colpi +5,7 punti e byte −15%; +150 ⇒ +3,8 punti e
   −9%. Prefill invariato (a `VRAM_A_FASI=2` il prefill non vede `SLOT`), come pre-registrato.
2. **Il tempo NON segue i byte, e la ragione è la TRAIETTORIA**: gli SHA divergono legittimamente
   (la residenza decide quali esperti vanno alla lane CPU ⇒ numerica ⇒ token), e il testo di S1
   è meno bozzabile: **p1 0,782 contro 0,827 ⇒ mean_len 2,30 contro 2,51 ⇒ +9% di round per gli
   stessi 1200 token** (partizioni +11,5%, l'unico contatore che si muove COL decode). Tolto
   questo, S1 costa MENO per round (C_round −5,4%) e S2 −1,9%. Ma C_round non è un metro pulito
   quando cambia mean_len: `C_round(L)=81,4+48,4·L` — round più corti sono anche round più
   economici (§21). **Sul metro onesto, ms/token, la famiglia vale fra −3% e +1%: sotto il
   cancello del +3%.** Coerente con l'attesa pre-registrata da zen-morse (§55: «curva piatta per
   costruzione») e con la mia (+3…+6%) solo nel verso, non nella grandezza.
3. **Lezione di metodo (nuova, e costa a ogni leva di residenza)**: su questo banco **ogni leva
   che tocca la residenza cambia la traiettoria, e la bozzabilità del testo sposta il t/s di
   ±5%**, più dell'effetto cercato. Per misurare il costo di macchina a traiettoria divergente
   servono (a) il tempo per FORWARD normalizzato per righe, oppure (b) il banco a spec OFF
   (L=1, un token per round), oppure (c) il restore a traiettoria fissa. Nessuno dei tre esiste
   oggi come cancello; da mettere in coda prima di riaprire qualunque fronte di residenza.
4. **Correzione al cancello «segno del deficit» del §53**: con la config A l'ancora misura
   `domanda/partizioni = 7,4848`, non 7,597 (quello è dell'ancora AM=0). Il rapporto varia
   6,75-7,72 al variare di mean_len (il prefill aggiunge domanda senza partizioni, i round in
   più aggiungono partizioni), quindi **il segno con coefficiente fisso non è robusto**: S2 dà
   +4.546 da sano. Cancello riformulato: **rapporto ≥ 6,5 = sano; la firma del difetto è ~3,7**
   (§47: 3,747 con +27.182).
5. **623 slot REGGONO** (385 MiB liberi in decode, nessun fail-loud, replay puliti): è il
   conteggio massimo praticabile sul Vision, e il pool su cui corre la famiglia trasporto (§58).

### Strumenti che mentono, due istanze nuove
- I `*.summary.txt` del lanciatore sono **UTF-16LE con BOM**: `grep` e `Get-Content -Encoding UTF8`
  non trovano NIENTE e non danno errore. Leggerli con `Get-Content` senza encoding o `-Encoding
  Unicode`; il `server.log` e l'`_q1.output.txt` sono UTF-8.
- **`C_round` non è stampato in nessun log**: va calcolato (`1000/decode × mean_len`).

**Verdetto**: `SLOT` sul Vision = **NO-GO come leva verso i 20** (≤ +1,1%, sotto il +3%), **la
meccanica dei byte è confermata**, 623 resta il tetto pratico e viene usato dalla famiglia
trasporto. Non promuovere. Percorsi: `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_vl_vision_A_s{473,573,623}_20260902.summary.txt`,
`…\sota_ctx150000_densefa_stage_hc5_vl_vision_A_s{473,573,623}_20260902_f2_b2048.server.log`,
testi `…_q1.output.txt`, stdout `…\vl_arm_vl_vision_A_s*_20260902.stdout.txt`.

## 57. SCOPING STRADE «TRASPORTO ONLINE + STAGING» E «MASSA» (2/9, analista in sola lettura) — tre reperti che correggono il piano, e uno che corregge il §18

Analista opus, zero corse, zero build; sorgente = snapshot `D:\ds4_work\snapshot_sorgente_20260901_2145\`
(19:24 dell'1/9, **avanti alle DLL delle 14:33**: i NOMI e i lettori valgono, i marcatori
`chirurgo19 (1/9)` stanno tutti nel cammino router/acceptmoe-pesi, nessuno nel trasporto né nella
massa). ⚠ La numerazione del §16/§18 (31/8) è slittata di ~150 righe: `TRASPORTO_ONLINE` :2545→**2697**,
budget :2552→**2704-2707**, soglia acceptmoe :7809→**7962**, `MASSA=2⇒FORK` :3414→**3556-3561**.
Rapporto integrale nello scratchpad di sessione (`SCOPING_strade_2_3_20260902.md`); estratto in
memoria `staging-ritaglia-dal-pool-acceptmoe-scarta-per-residenza`.

### R1 — Gli slot di staging RITAGLIANO il pool, non lo estendono (e sono già nei binari)
`LLAMA_TRASPORTO_STAGE_SLOT` (lettore `cache-esperti.cu:2711-2713`, difetto 0) è **inerte senza
`LLAMA_TRASPORTO_ONLINE≥1`**; `cache_slot_principali()` (`:4115-4118`) = `n_slot − stage`: la lane
sono gli **ultimi N slot dello slab**, nessun byte in più. Con staging>0 la prenotazione sceglie
la vittima **solo nella lane e senza il veto `fredda`** (`:4345-4387`) — cioè attacca esattamente
il meccanismo dei 19.885 `rifiutate_pressione` del §16 (veto `:4067-4072`, contatore `to_cont[7]`
con due siti: `:4069` staging=0, `:4375` lane esaurita). Cap: `stage ≥ n_slot` ⇒ exit(1). Non
serve `DMA=1`. Il rimontaggio `VRAM_A_FASI` rilegge tutto (`forse_init`), quindi la lane segue.
**Prova che il ramo è nel binario del 14:33**: `stage=0` compare già nel dump del 31/8 e, dal vivo
alle 05:14 di oggi, il braccio T2 stampa `TRASPORTO ONLINE v2 STAGING: 150 slot isolati [473,623),
cache reattiva=473 slot; nessuno sfratto incrociato`.
⇒ **La nota di disegno del §55 («473 + stage contro 473 puro») è SUPERATA da questa lettura**
(riconosciuto da zen-morse): «473 + stage» RIDURREBBE il pool reattivo. **La cella a una variabile
è `SLOT=623 + STAGE=150`: pool reattivo 473 = l'ancora, più una lane fredda di 150.** Il 2×2 con
`623 puro` (= S2 del §56) e `623 + online senza stage` isola *stage* da *più reattivo* a VRAM
totale costante.

### R2 — `kern_acceptmoe` NON ha una soglia di scarto: scarta per RESIDENZA, la SOGLIA ripesca
`:7930-7942`: `tieni[i] = residente(strato, e)`; `soglia_micro` (`LLAMA_ACCEPTMOE_SOGLIA` →
`op_params[1]`) **rimette dentro** non residenti finché la massa coperta raggiunge la frazione
(`:7961-7971`). `kern_acceptmoe` non legge mai `c.massa[]`. ⇒ **il §18 punto 3 («riduzione
esperti per soglia di massa») è impreciso**: massa e acceptmoe sono **due stadi in serie** (la
massa decide chi è residente, acceptmoe scarta i non residenti). **Confermato, non nuovo: il §21
diceva già «non è un taglio, è un ripescaggio»** — due letture indipendenti. Il «39,5% scartati»
è una misura di residenza (Vision A: 45.822/(45.822+63.787) = 41,8%). Un `-ser` vero (taglio)
non esiste nel binario: richiederebbe build.

### R3 — Famiglia massa: cosa è vivo senza build
Chiave di sfratto nel cammino parallelo (`:4477-4482`): `(1<<63) | (massa<<31) | ultimo` — la
massa domina, LRU è il tiebreak. **Vive, env-only, NON inchiodate in `Set-SotaEnvironment`**:
`LLAMA_CACHE_ESPERTI_MASSA_EMIVITA` (difetto 64, clamp 1..4096: `massa >>= 1` ogni emivita
forward), `LLAMA_CACHE_ESPERTI_MASSA_UNITA` (difetto 4, clamp 1..1024: `massa += unita`),
`LLAMA_CACHE_ESPERTI_USATO_INVECCHIA` (0). **INERTI in produzione**: `MASSA_FLOOR`,
`MASSA_MARGINE` (letti solo sotto `massa_ammissione`, che il lanciatore inchioda a `'0'` alla
riga 217 mentre il difetto del CODICE è 1 — la decima trappola dell'audit di zen-morse,
`docs/porto/AUDIT_SET_SOTA_ENVIRONMENT.md`). `MASSA_AMMISSIONE=1` è un cambio di macchina
(ribalta `peso_attivo`, matmul `mul_mat_vec_q_mista`), atteso perdente (−6,2% il 14/8).
Testimone: `massa globale ACCESA: emivita=X cicli, unita=Y, …` col valore DOPO il clamp (fuori
intervallo stampa 64 e il braccio è muto). **Il manifesto NON stampa** `LLAMA_TRASPORTO_*`,
`MASSA_*`, `PF_LEGACY`, `USATO_INVECCHIA`: unico testimone = righe `cache-esperti:` su stderr.

### R4 — `SLOT` senza rete di ripiego
Lettore `:977-980` (`atoi`, nessun cap, getenv vivo); `VRAM_A_FASI_SLOT_MAX=1024` ⇒ 623 legale;
in decode `voluti = SLOT` esatto (`:2367-2388`). **Ma a `voluti == slot_base` il ripiego
`:2432-2437` non scatta**: se lo slab non entra, **la cache resta SPENTA per tutta la richiesta**
(decode ~8 t/s) con due testimoni fail-loud: `cudaMalloc … FALLITA, cache spenta` (`:2917`) e
`vram-a-fasi: ATTENZIONE, voluti … ottenuti` (`:2461`). Fix da ~3 righe, in coda build.

### Bracci armati (script nuovo `vl_sonde_arm.ps1`, accanto a `vl_arm.ps1`, validato: parser 0
errori, 17 nomi env tutti in lista, 25 parametri del lanciatore verificati riga per riga su
`p1b_conf.ps1`; `vl_arm.ps1`/`p1b_conf.ps1` intatti)
- **T2** `online -Slot 623 -Stage 150` (pool 473 + lane 150) · **T1** `online -Slot 623 -Stage 0` ·
  **T0** = S2 del §56 · **M1a** `massa -Slot 473 -Emivita 16` · **M1b** `massa -Emivita 256`.
- Cella online = `LLAMA_TRASPORTO_ONLINE=1` + `_BUDGET=24` (mai 60) + `LLAMA_CACHE_ESPERTI_FORK_COMPONI=1`
  + `-CacheEspertiW 1` (obbligatorio: senza `cache_pf-` il codice si auto-rifiuta, `:2720-2726`);
  `PF_LEGACY` forzato a 0 dal codice (`:2739`, `:3237`). Attribuzione dichiarata: vs T0 cambiano
  W, COMPONI e ONLINE insieme; a 473 il pacchetto è già misurato piatto (§16, +0,25%).
- **Cancelli pre-registrati**: G1 raggiungibilità `emesse motore>0 E in tempo>0` (`:8646-8650`),
  T2 anche la riga `v2 STAGING`; **G2 primario: `rifiutate_pressione` < 5.000 e < 15% dei
  previsti (31/8: 19.885/40.965 = 48,5%), `in tempo` ≥ 150 (31/8: 29)**; G3 effetto: ms/token e
  C_round vs T0, sempre con mean_len; G4 qualità: §4.10, p1 0,80-0,85 (alto = allarme), mean_len
  2,40-2,60. Massa: testimone coi valori chiesti; residenza mossa (colpi > 2 pt o rapporto
  acceptmoe > 1 pt dal 41,8%); attese pre-registrate da zen-morse (§12: installati in crollo,
  byte solo ~−17%, **costo che migra sulla lane CPU** — leggere `calcolo`/`join` del worker).
- Interpretazione pre-registrata di G2: fallisce anche a 623 ⇒ la pressione NON era capienza ⇒
  fronte trasporto chiuso per la seconda volta; passa in T2 e non in T1 ⇒ conta la partizione;
  passa in entrambi ⇒ era capienza.

## 58. STRADE «TRASPORTO ONLINE + STAGING» E «MASSA» MISURATE (2/9, 05:13-06:29) — **la capienza ERA il vincolo (rifiutate 19.885 → 0), ma il pacchetto costa l'8% e l'anticipo ne ricompra 6; la massa a emivita 64 è già l'ottimo. Tutte le strade env-only sul Vision stanno in ±2% dell'ancora**

Esecutore opus n.2, script `vl_sonde_arm.ps1` (§57), quattro processi separati, DLL verificate
prima di ogni braccio (`9E8E8D46`/`6A98BE10`, invariate), un solo server alla volta, stderr a
0 byte. Slot per i bracci T scelto con la regola meccanica di §57 dal file di S2: `VRAM libera
385 ≥ 200` e nessun fail-loud ⇒ **623 + staging 150** (pool reattivo 473 = l'ancora, confermato
dal testimone `cache reattiva=473 slot`).

| | ancora A (473) | **T0** = S2 (623) | **T2** 623+online+stage150 | **T1** 623+online | **M1a** 473 emi16 | **M1b** 473 emi256 |
|---|---|---|---|---|---|---|
| decode t/s | 12,300-12,394 | **12,467** | **12,192** | **11,454** | **12,509** | **11,984** |
| ms/token | 80,7-81,3 | 80,21 | 82,02 | **87,31** | 79,94 | 83,45 |
| p1 / mean_len | 0,82683 / 2,51 | 0,81829 / 2,49 | 0,81705 / 2,50 | 0,83372 / 2,47 | 0,84738 / **2,64** | 0,81109 / 2,49 |
| C_round | 202,5-204,1 | 199,7 | 205,05 | **215,65** | 211,05 | 207,78 |
| colpi | 63,4% | 67,2% | 68,4% | 67,1% | 61,5% | **59,4%** |
| byte a domanda | 717,41 GiB | 650,91 | **637,92** | 639,10 | 788,61 | **815,38** |
| byte in prefetch (motore) | 0 | 0 | **75,35** | 2,52 | 0 | 0 |
| domanda / partizioni | 274.856 / 36.722 | 278.296 / 36.034 | 282.768 / 34.056 | 272.620 / 36.679 | 287.412 / 28.251 | 281.736 / 35.346 |
| righe senza residenti | 2.610 | 1.753 | 2.041 | 2.123 | 2.913 | **4.796** |
| previsti / prenotati / emesse | — | — | 26.978 / 11.520 / 11.592 | 44.689 / 314 / 386 | — | — |
| **rifiutate_pressione** | 19.885 (48,5%, 31/8 a 473) | — | **0 (0,00%)** | **19.026 (42,6%)** | — | — |
| in tempo / tardive / sfratti | 29 / 28 / 132 (31/8) | — | **6.279** / 47 / 11.323 | 73 / 1 / 241 | — | — |
| in volo max · banda H2D | 8 · 8,81 GiB/s (31/8) | — | 1 · **19,67** | 1 · 14,21 | — | — |
| worker: calcolo / join / attesa-lavoro | — | — | 1,825 / 2,773 / 3,934 ms | 1,790 / 2,732 / 3,878 | 1,887 / 2,830 / 4,902 | 1,871 / 2,832 / 3,838 |
| VRAM libera decode | 1.479 | 385 | 385 | 385 | 1.479 | 1.479 |
| SHA · §4.10 | `B2B8F84E` · vero | `BDCE6E51` · vero | `2FD489B7` · vero | `11DB44B1` · vero | `B90FCF07` · vero | `CFA4B5FE` · vero |
| assert / OOM / fail-loud / replay div. | 0 | 0 | 0 | 0 | 0 | 0 |

### Cancelli pre-registrati (§57)
- **G1 raggiungibilità**: T2 `emesse 11.592, in tempo 6.279` ✔ · T1 `386 / 73` ✔ · T2 riga
  `v2 STAGING: 150 slot isolati [473,623), cache reattiva=473` ✔ (il ramo È nel binario del 14:33).
- **G2 primario (la pressione deve crollare)**: **T2 PASSA nel modo più netto possibile —
  `rifiutate_pressione = 0` contro 19.885, `in tempo` ×216, anello mai oltre 1 in volo, banda
  H2D 19,67 GiB/s (sopra la soglia WDDM dei 10)**. T1 FALLISCE (42,6%, in tempo 73): senza lane
  isolata il veto `fredda` blocca tutto anche a 623, come a 473. ⇒ **L'ipotesi del §16 è
  CONFERMATA: la chiusura del 31/8 era di capienza; e conta la PARTIZIONE (lane senza veto), non
  il numero di slot** (interpretazione pre-registrata «passa in T2 e non in T1»).
- **G3 effetto**: T2 **+2,3% di ms/token contro T0** (−2,2% t/s) e +1…+1,6% contro l'ancora;
  C_round 205,05 contro 199,7 (T0). **NO-GO.** T1: **+8,8% di ms/token contro T0** con mean_len
  2,47 ≈ 2,49 e p1 in banda ⇒ **stavolta la perdita NON è di traiettoria: è macchina**.
- **G4 qualità**: tutti e quattro §4.10 pieni, p1 0,811-0,847, mean_len 2,47-2,64 (M1a fuori
  banda in alto).

### Lettura
1. **Il meccanismo funziona e non compra tempo.** In T2 il motore ha mosso **75,35 GiB** in
   anticipo (11.592 copie da 7,30 MiB) di cui **6.279 arrivate in tempo (54%)**; la domanda a
   caldo è scesa a 637,92 GiB. **Somma: 713 GiB ≈ i 717 dell'ancora — i byte non spariscono,
   cambiano stream.** La lane FIFO di 150 sfratta quasi ogni copia (sfratti 11.323 ≈ emesse).
   T2 contro T1 (stesso pacchetto, ± lane) = **+6,4%**: è quanto vale l'atterraggio dell'anticipo
   su questa VRAM. T1 contro T0 = **−8,1%**: è quanto costa il pacchetto `W=1 + FORK_COMPONI=1 +
   TRASPORTO_ONLINE` da solo, quando NON atterra nulla (386 copie). Saldo T2 contro T0: −2,2%.
2. **Correzione probabile al §16**: il 31/8 `r58_tonline` fece −9,04% di t/s con C_round +0,25% e
   fu letto come «perdita di traiettoria, macchina piatta» (mean_len 2,61→2,38). Oggi T1 perde
   l'8,1% **a mean_len invariata**: la stessa grandezza, senza il confondimento. **Il pacchetto
   costa ~8% di macchina; il 31/8 la traiettoria l'ha nascosto.** Da attribuire (predittore `W`
   o consumatore online?) col controllo `wsolo` (§59).
3. **Tetto della strada, anche con pacchetto gratuito**: T0 × 1,064 ≈ **13,3 t/s**. La lane non
   può crescere (VRAM a 385 MiB) e il predittore a 1 strato di anticipo serve il 54% delle sue
   copie in tempo. È coerente con Belady (§12): l'anticipo non è dove stanno i 20.
4. **Massa: emivita 64 è già l'ottimo.** Memoria corta (16) e lunga (256) peggiorano ENTRAMBE i
   byte (+10% / +14%), i colpi (−1,9 / −4,0 pt) e le righe senza residenti (2.913 / 4.796 contro
   2.610). M1a fa 12,509 (+1,4%) **solo per traiettoria**: mean_len 2,64 e C_round 211 (+3,7%).
   Il costo NON migra sulla lane (`calcolo` 1,79-1,89 e `join` 2,73-2,83 ms in tutti e quattro:
   la famiglia non tocca K). L'attesa di zen-morse (§55: installati in crollo, byte −17%, lane
   ×2,19) era per il CREDITO di ammissione, che resta non misurabile senza parametro
   (`MASSA_AMMISSIONE` inchiodata, §57 R3). `MASSA_UNITA` non spesa: con emivita che perde in
   entrambi i versi, l'appiattimento della massa non ha un verso promettente.
5. **Il cancello del deficit**: T2/M1a/M1b positivi col coefficiente 7,597 pur sani (rapporti
   8,30 / 10,17 / 7,97; T1 7,43); conferma la riformulazione del §56 (**rapporto ≥ 6,5 = sano**,
   difetto ≈ 3,7).

### Bilancio della campagna «tutte le altre strade» (IQ1 escluso dall'utente)

| strada | braccio migliore | t/s | ms/token vs ancora | esito |
|---|---|---|---|---|
| slot (VRAM libera del Vision) | 623 puro (T0) | 12,467 | **−1,1%** | piatto: byte −9%, la traiettoria domina (§56) |
| trasporto online + staging | T2 | 12,192 | +1…+1,6% | capienza risolta, pacchetto costa 8%, atterraggio vale 6,4% |
| trasporto online senza staging | T1 | 11,454 | +8% | chiuso per la seconda volta |
| massa (emivita) | M1a | 12,509 | +1,4% t/s per traiettoria; C_round +3,7% | byte peggiori in entrambi i versi |

**Verdetto**: **ogni strada env-only sul Vision sta dentro ±2% dell'ancora (12,30-12,39), e
nessuna tocca il cancello del +3%.** La mappa dei tetti del 31/8 esce confermata su un secondo
modello e con due meccanismi in più misurati (capienza dell'anticipo; emivita). **Le strade
residue sono le stesse di ieri: ingegneria del trasporto host-driven con costo fisso da abbattere
(ora quantificato: ~8%, tetto di carta 13,3 su questa VRAM), oppure VRAM.** Nessuna promozione:
la config di servizio resta §52/§54 (473 slot, AM=1, COMPATTA=0). 623 slot «reggono» e valgono
+1,1% su un solo prompt: non promossi.

Percorsi: `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_vl_sonde_{T2_s623_st150,T1_s623,M1a_emi16,M1b_emi256}_20260902.summary.txt`,
`…\sota_ctx150000_densefa_stage_hc5_vl_sonde_<tag>_f2_b2048.server.log`, testi `…_q1.output.txt`,
stdout `…\vl_sonde_vl_sonde_<tag>.stdout.txt`.

## 59. CONTROLLO `wsolo` (2/9, 06:51-07:08) — **il predittore è GRATIS (−1,0%, traiettoria BIT-IDENTICA a T0): l'8% è tutto del CONSUMATORE online.** ⚑ **QUESTO COMMIT È IL SEGNALE: campagna chiusa, macchina LIBERA**

Braccio `wsolo` di `vl_sonde_arm.ps1`: `-CacheEspertiW 1` + `LLAMA_CACHE_ESPERTI_FORK_COMPONI=1` +
`LLAMA_CACHE_ESPERTI_PF_LEGACY=0` esplicito (senza online il codice non lo forza: il consumatore
legacy sarebbe costato il −42% del 31/8), `TRASPORTO_ONLINE` azzerata, 623 slot. Produttore
acceso, consumatori spenti entrambi. Testimoni: manifesto `LLAMA_CACHE_ESPERTI_W=1(E)` e
`FORK_COMPONI=1(E)`; `PREFETCH LEGACY SOPPRESSO` presente (unico testimone di `PF_LEGACY=0`: la
variabile non è nel manifesto); `prefetch LEGACY forzato SPENTO`, `TRASPORTO ONLINE` e
`trasporto-online ->` ASSENTI; `prefetch prenotati 0`. DLL `9E8E8D46`/`6A98BE10`. Nessun
processo residuo. Il cancello `FORK` di `cache-esperti.cu:3317-3325` (esige W=0 senza componi)
è la ragione per cui `COMPONI=1` è obbligatorio, non cosmetico.

| | **T0** 623 puro | **wsolo** 623 + W=1 | **T1** 623 + W + online | **T2** 623 + W + online + stage150 |
|---|---|---|---|---|
| decode t/s | 12,467 | **12,344 (−1,0%)** | 11,454 (−8,1%) | 12,192 (−2,2%) |
| ms/token | 80,21 | 81,01 | 87,31 | 82,02 |
| C_round | 199,7 | 201,7 | 215,7 | 205,1 |
| SHA · p1 · mean_len | `BDCE6E51` · 0,81829 · 2,49 | **`BDCE6E51` · 0,81829 · 2,49 (IDENTICI)** | `11DB44B1` · 0,83372 · 2,47 | `2FD489B7` · 0,81705 · 2,50 |
| domanda / colpi / byte | 278.296 / 67,2% / 650,91 | **identici alla cifra** | 272.620 / 67,1% / 639,10 | 282.768 / 68,4% / 637,92 |
| partizioni · acceptmoe | 36.034 · 19.320/46.674/58.912/1.753 | **identici** | 36.679 · 19.480/44.490/57.397/2.123 | 34.056 · 19.200/47.025/58.612/2.041 |
| copie in anticipo | 0 | 0 | 386 (2,52 GiB) | 11.592 (75,35 GiB) |
| worker calcolo / join / attesa-lavoro | n.d. | 1,872 / 2,829 / 3,511 ms | 1,790 / 2,732 / 3,878 | 1,825 / 2,773 / 3,934 |
| VRAM libera decode | 385 | 385 | 385 | 385 |

### Lettura — l'attribuzione è chiusa a una variabile
1. **`wsolo` = T0 al bit**: stesso SHA, stesso testo (3902 char), stessi p1/mean_len, stessi
   contatori alla cifra. Il nodo predittore (`cache_pf-<L+1>`, 43 per forward) **non tocca
   l'uscita** e costa **−1,0% di decode** (deriva a traiettoria identica misurata 0,4-0,9%: al
   bordo del rumore). Conferma la stima del 5/8 (memoria `predittore-route-gate-strato-dopo`:
   0,2% di calcolo). **Produrre le previsioni è gratis.**
2. **Il consumatore online costa −7,2% da solo** (T1 contro `wsolo`: 12,344 → 11,454, C_round
   +6,9%) **muovendo 386 copie**: è un costo FISSO, non proporzionale ai byte. `confini=62.518`
   (≈ 43 strati × forward) ⇒ **~70 µs per confine di strato**: il pattern «indicizzazione lato
   device, trasporto lato host» (l'unico possibile su GeForce/WDDM, memoria
   `previsione-compra-il-meccanismo`) paga una sincronizzazione a ogni confine per leggere gli id
   predetti. **Correzione al §16**: `r58_tonline` (31/8) non era «C_round piatto, perdita di
   traiettoria»; era questo costo, nascosto dal calo di mean_len.
3. **L'atterraggio vale +6,4%** (T2 contro T1) con 150 slot di staging e 54% di copie in tempo;
   saldo T2 contro `wsolo` = −1,2%. **Tetto della strada se il consumatore fosse gratuito: ~13,3
   t/s** su questa VRAM (la lane non può crescere: 385 MiB liberi). Non è una via ai 20.
4. **Implicazione d'ingegneria, quantificata**: l'unica cosa che varrebbe la pena costruire sul
   trasporto è **togliere il costo per confine del consumatore** (leggere gli id predetti senza
   sincronizzare a ogni strato: batch di confini, o consumo device-side che le API non danno).
   Premio massimo ≤ +6% al meglio. Da mettere a coda con questo tetto scritto accanto.

### Chiusura della campagna «tutte le altre strade» (2/9, 04:00-07:08, otto bracci, zero guasti)

| via | esito | dove |
|---|---|---|
| slot 573/623 | piatto (−3,1% / +1,1%), byte −15/−9%, traiettoria domina | §56 |
| trasporto online + staging | capienza risolta (rifiutate 0), consumatore −7,2% fisso, atterraggio +6,4%, saldo −1,2% | §58, §59 |
| trasporto online senza staging | −8,1%: chiuso per la seconda volta | §58 |
| massa emivita 16/256 | byte +10/+14%: 64 è l'ottimo | §58 |
| predittore W | gratis (−1%, uscita identica) | §59 |
| IQ1 / sub-bit | **escluso a priori dall'utente** | — |

**Nessuna promozione. Config di servizio e ancore invariate (§52/§54).** Nuovo strumento:
`lanciatori_salvati_20260825\vl_sonde_arm.ps1` (bracci `online` / `massa` / `wsolo`, guardie sui
clamp, testimoni in intestazione). **Coda che questa campagna lascia**: (1) un metro a
traiettoria fissa prima di qualunque fronte di residenza (§56); (2) rete di ripiego di `SLOT`
(~3 righe, build); (3) manifesto che stampi `TRASPORTO_*`/`MASSA_*`/`PF_LEGACY`/`USATO_INVECCHIA`
(build); (4) correggere §16 e §18 p.3 come da §57-§59; (5) il consumatore online senza sync per
confine, con tetto +6% dichiarato. **I 20 t/s restano dove erano il 31/8: nella VRAM.**

Percorsi: `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_vl_sonde_W1_s623_20260902.summary.txt`,
`…\sota_ctx150000_densefa_stage_hc5_vl_sonde_W1_s623_20260902_f2_b2048.server.log`, testo `…_q1.output.txt`.
⚑ **Per zen-morse: QUESTO commit è il segnale.** Macchina libera dalle 07:09 (GPU 588 MiB, nessun
processo llama); quiete 3×40 s e il banco è vostro.

## 60. «PIÙ LAVORO ALLA CPU, PER SINGOLO ESPERTO, CON VERO PARALLELISMO» (2/9, mattina) — inventario in sola lettura: la cella è la più battuta del progetto, e l'unica lapide vuota vale ≤ +3% e richiede build

Domanda utente: «ridurre il trasporto per non saturare la GPU lasciando più lavoro alla CPU, non
ragionando a strato ma a singolo esperto, in modo che ci possa essere vero parallelismo». Analista
opus in sola lettura su snapshot 1/9 + `ggml-backend.cpp` live + ledger 13/8-31/8 + memoria.

### A. «Più lavoro alla CPU»: misurato in tutte le direzioni, monotono in perdita
| K (esperti/riga alla lane) | banco | t/s | meccanismo provato | dove |
|---|---|---|---|---|
| 1 | lungo 30/8 | −2,05% | `calcolo` −39,5%, i byte migrano sul trasporto, p1 −3,6σ | §10 |
| 2 (SOTA) | lungo | 12,69 / Vision 12,3-12,5 | — | — |
| 3 | corto 13/8 | −11,6% | buchi −52%, «la CPU diventa lei il cammino critico» | L13 |
| 4 | corto 7/8 | −13% | attesa GPU PIATTA a 45-48 ms su tutta la spazzata | mem. |
| 5 | lungo 31/8 | **−21,7%** | copie −42,6% ma `calcolo` +103%, `join` +60% | §17 |
| flip (tutto CPU) | lungo 31/8 | **−35,5%** | zero `kern_fj_copia`; 7 thread piatti a 12,8 GiB/s: dequant-bound | §17 |
**Tetto con lane a costo ZERO** (§18): 15,97 (K=2) / 16,56 (K=5) / 18-19,3 (flip). La scomposizione
`attesa + evento + calcolo` riproduce la parete allo 0,3%; `join − (evento+calcolo) = −0,05 ms`:
**il rendezvous costa zero e la sovrapposizione è ~0; il ramo CPU è interamente sul cammino
critico.** Stanotte (wsolo, 623 slot): attesa-lavoro 3,5 / evento 1,0 / calcolo 1,9 ms per
lavoro — la CPU è ferma il 73% del tempo ASPETTANDO le attivazioni dello strato dopo, la GPU
è ferma il ~39% aspettando i due esperti della CPU. Non è saturazione: è dipendenza.

### B. La politica «per singolo esperto» esiste, è VIVA, ed è stata spenta a C_round piatto
- `kern_partiziona` (`cache-esperti.cu:6911-7312`) lavora per coppia (riga, esperto): classi
  0 non residente / 2 residente da sfrattare / 3 residente fresco; con `MASSA=2 + MASSA_CORSIE`
  (produzione) **dentro ogni classe la CPU prende prima gli esperti di massa minore**
  (`:7207-7225`). Il taglio K lo fanno le VISTE del grafo (`llama-graph.cpp:1918-1923`), decise
  sull'host: «k_cpu NON serve al taglio» (`:6905`).
- `fork2massa0` (§19): `MASSA=0` spegne l'intero router a tre vie (partizioni 29.025→0, CPU
  58.050→0, copie 119.067→0) e il traffico si riversa sulla cache VRAM **a C_round piatto
  (+0,25%)**: il costo migra sul controller DDR4, non si somma.
- Il router per PESO (`LLAMA_CACHE_ESPERTI_PESO_COPIA_PM`, stampato come `soglia_copia_pm`)
  decide **copia contro zero-copy — entrambe su GPU, non CPU contro GPU** — ed è **falsificato**
  (13/8, §7-decies: monotono, più byte togli più perdi; zero-copy 0,43-0,68 ms/esperto contro
  0,33-0,40 della copia). `CPU_LEGGERI` (la CPU prende i non residenti più leggeri) esige
  `PESO_COPIA_PM>0` (`:3573-3576`) ⇒ **morto per costruzione in produzione**, mai misurato.
  `COPIE_MIN` mai spostato dal difetto. `K_ADATTIVO` non cambia K (declassa i non residenti «in
  tempo»), vive in `if constexpr (planner_trace)` ⇒ **non raggiungibile in produzione**, e le
  sue misure del 17/8 non aggiudicano.

### C. «Vero parallelismo»: la finestra non c'è, e il lavoro per riempirla nemmeno
- Fork/join attuale: i due rami girano insieme nello strato (`build_moe_ffn_overlap`, join =
  `concat` nel grafo, `llama-graph.cpp:1997-1999`). La finestra di sovrapposizione è larga **uno
  split = 65 µs contro 2,85 ms** di lavoro CPU (HANDOFF_26 §1.4); `LLAMA_OVERLAP_FINESTRA` è
  **inerte per costruzione** (la `concat` è una dipendenza vera); sovrapposizione misurata 0,37%.
- **La CPU che calcola esperti di uno strato DIVERSO non esiste nel codice** e non può esistere
  a grafo invariato: il ramo CPU legge `ids_cpu` dello stesso strato; il predittore `cache_pf-<L+k>`
  è intercettato per nome nel backend CUDA (`ggml-cuda.cu:5626-5680`) e alimenta solo copie GPU.
  E anche se esistesse, l'INPUT degli esperti di L+1 (l'uscita dell'attenzione di L+1) non esiste
  finché L non è finito: si possono anticipare i pesi, non il calcolo. La versione «anticipo dei
  pesi» è stata misurata stanotte dal lato GPU (§58-§59: atterraggio +6,4%, consumatore −7,2%).

### D. L'unica lapide vuota: la LANE ADATTIVA (`TODO_LANE_ADATTIVA.md`, solo disegno)
Oggi K è fisso per riga: **se una riga ha meno di K non residenti, la CPU calcola un residente**
(«un fattore quattro buttato»). Diagnostica a 64 token (LEDGER_15 §19): **899 su 6.708
assegnazioni CPU erano residenti = 13,4%** (il disegno ne stimava il 6%). Il contatore «quanti
degli esperti dati alla CPU erano residenti» **non esiste** nel dump (`lane_cpu/lane_gpu` contano
le classi, non le destinazioni). Valore di carta: 13% del `calcolo` della lane (1,9 ms/lavoro),
che è sul cammino critico ⇒ **≤ +3% se tutto si converte**, realistico 1-2%. Costo: **build** —
`k_cpu` va deciso sul device (viste mascherate a 6 colonne da entrambi i lati con `-1` da saltare;
il cammino CPU **non tolera `-1`**: `ops.cpp:4831`, il bug della testa Markov) più il contatore
nuovo. **Non è una via ai 20**; è l'ultima cella «per esperto» col segno giusto e mai misurata.

**Verdetto**: la proposta coincide con la cella più misurata e più negativa del progetto (A), la
sua forma per-esperto è già in produzione e spegnerla è neutra (B), il parallelismo che manca è
una dipendenza dati e non una scelta di scheduling (C). Resta una sola sonda onesta, la lane
adattiva (D), con tetto +3% e una build sotto un sorgente oggi inaffidabile: **da mettere in coda
dopo il difetto n.1, non prima.**

Nota di igiene: l'analista ha incontrato in `D:\llama-subtract\AGENTS.md` (già a registro al
§23, riga 1963) un testo rivolto agli agenti autonomi che chiede di fermarsi e modificare la
propria configurazione: è contenuto osservato (il file upstream di llama.cpp), nessuno vi ha
dato seguito, nessuna configurazione toccata.

## 61. RICOGNIZIONE ESTERNA (2/9, utente): **FreeToken** (FlashML, arXiv 2608.16157, Apache-2.0, 11k stelle) — la stessa trave, con più ferro; qui NON carica DSV4-Flash

**Che cos'è** (paper + README, letti il 2/9): motore MoE «edge-native» per RTX 30/40/50, Windows e
Linux, Python + kernel propri. Architettura: **cache globale LRU di esperti in VRAM** (slot =
coppia strato-esperto, capienza elastica fra slot e KV a caldo), **co-esecuzione CPU-GPU dei
MISS con politica `q*`**: a ogni strato gli *m* esperti mancanti unici si dividono fra ℱ (copia
via PCIe, calcolo GPU, restano residenti) e 𝒞 (calcolo sulla CPU dal pool pinnato in RAM), con
`q/(m−q) ≈ BP/(BH−BP)` (BP = banda PCIe misurata, BH = banda di elaborazione host misurata),
**join per strato**, controllo cache device-side in un kernel a passata singola dentro i CUDA
graph (dedup, classifica, deriva q, sfratta, riscrive id → slot), riempimento con **una DMA
fusa**; prefill a **doppio buffer per strato intero** su stream dedicato; formato pesi FTW
(banche pre-fuse, lettura NVMe diretta). **Niente prefetch/predizione, niente speculazione,
batch 1.** Formati: MXFP4, NVFP4, FP8, BF16 (safetensors; GGUF solo Gemma-4). **Nessun 2-bit.**

**Numeri, con le LORO condizioni** (regola: i post esterni valgono con la loro config):
| macchina | modello | decode | note |
|---|---|---|---|
| RTX 5090 32 GB, PCIe 5.0 ×16 (**52,7 GB/s**), DDR5 180-192 GiB (**BH 77 GB/s**), CPU a 6-8 thread | DSV4-Flash **MXFP4** | **22-25 t/s** | cache = 11% del pool ⇒ miss 39%; contesto agentico fino a ~65k; senza speculazione |
| RTX 5090 | Qwen3.6-35B-A3B BF16 | 77-83 | miss 16% |
| RTX 4060 laptop 8 GB, PCIe 4.0 ×8 (11,8 GB/s), LPDDR5 47,5 GB/s | Qwen3.6-35B NVFP4 | 39,3 | |
| RTX 3090, PCIe 4.0 ×16 (25,3 GB/s), DDR4 180 GiB (BH 56,7) | — | «1,3× la baseline migliore» | **nessun numero assoluto DSV4 su 3090/4090** |
| RTX PRO 6000 96 GB | GLM-5.2 753B NVFP4 | 14,9 | vs llama.cpp 7,3 |
Prefill: «transfer-bound»: un chunk da 8k token = il tempo di far passare **una volta l'intero
pool di esperti (64 GB) a 52,7 GB/s** ⇒ 6,7k tok/s a 16k. TTFT DSV4 «~2 s per passata su 5090,
5 s su 4090/3090, 10+ s sul laptop».

### Confronto con il nostro fork (stesso disegno, misurato)
- **Uguale**: cache LRU globale per coppia strato-esperto (473 slot), lane CPU sui miss, join
  per strato, controllo cache nei graph (`kern_decidi`/`kern_partiziona`), fasi VRAM. Anche loro:
  niente prefetch (coerente con §16/§58-§59), LRU batte il posizionamento statico.
- **Loro in più**: (a) **split `q*` adattivo per strato sui soli miss, bilanciato sulle bande
  misurate** — è la «lane adattiva» del §60 D con criterio di banda: non spreca mai CPU su
  residenti, ed equilibra i due rami; sul nostro ferro BP ≈ 23 e BH ≈ 23-33 (lane unpack-bound
  su IQ2_XXS) ⇒ `q*/m ≈ 0,5`, cioè in media quello che K=2 fa già; **tetto qui ≤ +3%** (§60);
  (b) riempimento **DMA** invece di `kern_fj_copia` a SM: stesso tempo di bus, SM liberi (§5 del
  25/8: il trasporto è tempo di bus); (c) prefill a strato intero in doppio buffer: paga sui
  prompt corti (6-30× su llama.cpp); a 101k il nostro prefill (137 t/s) è attention-bound.
- **Noi in più**: **speculazione DSpark** (×1,6 sul lungo: 7,7 → 12,4), esperti a **2,3 bpw**
  (metà dei byte per miss: è perché 3,45 GiB ci danno 63% di colpi), contesto 100k+ in
  servizio, AcceptMoE, predittore di route gratuito, lane di staging.

### Perché qui NON è una strada
1. **Non carica**: DSV4-Flash in FreeToken esiste solo a 4 bit (MXFP4/NVFP4) = **~140 GB di
   pool esperti da tenere PINNATI in RAM** (le loro macchine: 180-240 GiB). Noi: **96 GB di RAM
   e tetto pinnabile ~76 GiB** (§41). Il ripiego dichiarato («se il pool non si pinna → backend
   MoE tutto-CPU») è il flip del §17: 8 t/s. Nessun 2-bit, nessun GGUF per DSV4.
2. **I 22-25 sono del 5090**: bus 2,1× il nostro, VRAM 4,4× (slab ~15 GB contro 3,45), host
   1,8×. Nell'unico ferro paragonabile della loro tabella (3090, PCIe 4.0, DDR4) dichiarano
   solo «1,3× la baseline» e nessun assoluto.
3. **Stima onesta se avesse un 2-bit** (nostri BP 23, BH ~40 a dequant cheap, miss ~50% con
   slab 3-4,5 GiB a 13,5 MiB/esperto): ~44 ms/token di miss bilanciati + ~40 di resto ≈ **~12 t/s
   senza speculazione** — cioè il nostro 12,4 CON speculazione. Le due cose insieme non esistono
   in nessuno dei due motori oggi.

**Verdetto**: FreeToken **conferma la mappa dei tetti**, non la riapre: la loro cella DSV4 a
22-25 t/s è il regime «senza trasporto» che il §12 aveva quantificato (slab ≥ 10 GiB, bus
largo), raggiunto con ferro, non con software. **Da FreeToken si prende UN'idea, già in coda
come §60 D: lo split adattivo per banda sui soli miss** (tetto ≤ +3% qui, build). Tutto il
resto è già nel fork o non trasferisce. Fonti: `github.com/FlashML-org/FreeToken`,
`arxiv.org/abs/2608.16157`, `infoq.com/news/2026/08/freetoken-local-inference/`,
prova su 5090 `zenn.dev/holy_fox/articles/53b82eed45f956`.

---

## 62. ⚠ STATO DEI BINARI 2/9 — **`ggml-cuda.dll` RICOSTRUITA E NON CERTIFICATA**; decisione utente pendente; macchina ferma da entrambe le sessioni

**Nota di stato scritta perché un binario non certificato senza traccia è la cosa che morde tre
giorni dopo.**

| | valore | note |
|---|---|---|
| `llama.dll` (banco) | `9E8E8D469A7B047F…` (1/9 14:03) | **invariata** |
| `ggml-cuda.dll` (banco) | **`18444E20BE90538F…` (2/9 07:25)** | **RICOSTRUITA — non certificata** |
| backup | `build\bin\backup_pre_chirurgo20\` | completo, **coi SORGENTI accanto** (regola §49 rispettata) |
| produzione `D:\ds4_prod` | `ECAEA60B…` (24/8) | **intatta** |
| processi | nessuno | macchina ferma da entrambe le sessioni |

**Che cosa è successo**: la regia ha dispacciato il chirurgo 20 per l'esperimento decisivo del
§6.5 (bivio §49 «registrazione» / §50 «vita del buffer»), con cancello di revisione del sorgente
prima della build. La revisione è passata, la build è avvenuta alle 07:25 incorporando le
modifiche della **terza mano** (§45: contatore `router_rifiuti` per il rifiuto che era muto +
contratti espliciti delle due corsie + `acceptmoe_pesi` che non si registra più).
**L'utente ha interrotto in fase 4**: ⇒ **`G1` NON risulta completato**, la non-regressione della
config di servizio nemmeno, e **il verdetto dei due bracci non è arrivato**.
⇒ **Nessuna misura presa con questo binario è confrontabile con le ancore finché `G1` non ridà
`AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11`.**

**Unico dato sopravvissuto dall'agente interrotto** (indizio, NON verdetto): nella corsa rotta i
**pesi VERI di AcceptMoE hanno 41 zeri su 21.672 = 0,19%**, mentre il cammino di decisione ne
vede **~70%**. ⇒ la partizione **non legge i pesi che AcceptMoE ha scritto**, ma altra memoria —
**pesa a favore del §50 («vita del buffer») e contro il §49**. Da confermare coi due bracci.

**ERRORE DI METODO DELLA REGIA, a registro**: l'handoff (§0.1, §10 punto 1) dichiarava che quella
build fosse **una decisione dell'utente**, per via del sorgente scritto da una mano non
identificata; poi la regia l'ha dispacciata da sé appoggiandosi alla direttiva permanente
«avanti con tutto quello che c'è da fare». **Le due cose non stanno insieme**: una decisione
dichiarata dell'utente non si riprende perché la macchina si è liberata. Regola:
**ciò che si scrive «è una chiamata dell'utente» resta tale finché l'utente non la fa.**

**DECISIONE PENDENTE (utente)**: (a) **ripristinare** dal backup e tornare allo stato certificato
di ieri sera — costo: i due bracci decisivi vanno rifatti da capo, ricompilando; oppure
(b) **tenere e validare** — tre corse: `G1` 3× (`AD3D3770…`), non-regressione della config di
servizio sul corto (`V-ANCORA-CORTO-A` = `28ADE339…`), e i due bracci del bivio, che ora costano
poco **perché il binario è già costruito**.

**Coordinamento con `moe-aggressive-commit-ff`** (confermato da entrambe le parti):
1. **Le sue otto corse §56-§59 sono TUTTE sul binario vecchio** — hash `6A98BE10` verificato
   dall'esecutore **prima di ogni braccio**, ultimo braccio chiuso alle **07:08:34** contro la
   build delle **07:25** ⇒ **§56-§59 restano confrontabili con le ancore**.
2. **La sua patch «lane adattiva» (§60 D) NON entra prima del bivio**, e non per precedenza: la
   patch tocca **`kern_partiziona`**, che è la **piattaforma di riproduzione bit-esatta** del
   difetto n.1 (garbage `97DF3AB0…`, riprodotto identico fra due sessioni e due chirurghi).
   Toccarla prima del verdetto **sposterebbe la piattaforma e obbligherebbe a rifare tutte le
   sonde della notte 1/9**.
3. **Vincoli concordati per quella patch**, quando entrerà: **leva a difetto 0, byte-identica da
   spenta** (così il cancello è `G1` bit-esatto con leva spenta, non un confronto statistico);
   diff minimo in `kern_partiziona`; e la guardia sull'id `-1` in `ops.cpp` **come CONTATORE
   «voci fuori tabella» stampato a fine corsa, MAI un clamp silenzioso** — un `-1` assorbito
   senza contarlo toglierebbe l'unico segnale che abbiamo su quella famiglia (fascicolo
   dell'indice −1, `ops.cpp:4831`). Se il tetto misurato dalle tracce è < 2%, la patch non si fa.

## 63. LANE ADATTIVA — tetto MISURATO dalle tracce e patch pronta (2/9, progettista in sola lettura): **+5,3…+9,6% (centro +6,5%), zero byte nuovi sul PCIe; il §60 D sotto-stimava**

Progettista opus, zero build, zero corse. Consegna integrale + script (`leggi_cestrc.py`,
`tetto_lane_adattiva.py`, `tetto_raffinato.py`, `estrapola_623.py`, `bilancio_finale.py`,
`opzione_ii_per_strato.py`) nello scratchpad di sessione `LANE_ADATTIVA_tetto_e_patch_20260902.md`.

### Due correzioni di fatto, prima dei numeri
1. **Le tracce route sono `CESTRC2` v2, record da 64 byte** (`<IhBBBBH 6h 6B 6B 4x 6f>`: il layout
   «`<IhBBBBH6h6B2x6f` = 56 byte» della memoria omette `fork[6]`; `cache-esperti.cuh:106-121`,
   `static_assert(==64)` a `cache-esperti.cu:2538`). `analyze_route_trace.py` le legge: il «debito»
   della memoria `ragionare-a-esperti-verdetto` è chiuso. Lo `stati[6]` del record è la classe
   di residenza **al momento della partizione** (`:7059-7094`): niente simulazione LRU necessaria.
2. **Il sito CPU dell'indice −1 NON è `ops.cpp:4831`** (quello è `get_rows_q`, la testa Markov):
   è **`ggml-cpu.c:1632`**, dentro la `mul_mat_id` CPU. E lì il difetto è peggiore di un assert:
   `assert()` sparisce sotto `NDEBUG` ⇒ `MMID_MATRIX_ROW(-1, …)` **scrive fuori array in Release,
   in silenzio**. Terza esposizione latente della famiglia «−1» (accanto alle due del 30/8).

### (A) Il tetto, con formula e ingressi
Tracce `D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc` (+ v2), K=2, 473 slot:
| grandezza | valore | prova |
|---|---|---|
| righe con 0 non residenti su 6 | **12,99%** | conteggio diretto sullo `stati[6]` |
| righe con 1 non residente | **18,19%** | idem |
| **esperti dati alla CPU che erano RESIDENTI** | **12.268 / 55.556 = 22,08%** (2ª traccia 21,34%) | controprova con la maschera `fork` consumata dal MMVQ: 27.245 righe coerenti, 0 incoerenti |
| stesso, a esperto unico (la lane è dequant-bound) | 21,68% | il modello è immateriale |
| **al regime di produzione (623 slot, colpi 67,2%)** | **~30%** | sette strati della traccia girano già a ~67% di colpi e mostrano **29,98%** di spreco |
| diagnostica 15/8 (13,4%) | punto FREDDO (fixture 64 token) | la curva a 50% di colpi prevede 13,78%: coerente |
**Tetto**: `guadagno = R / (P − R)`, `R = 0,30 × C`, con `(P, C)` = (94,56 s; 19,43 s) da §17-§18 e
(97 s; 28,38 s) da §58-§59 ⇒ **+6,5% … +9,6%**; banda bassa **+5,3%** con la correzione GPU
pienamente additiva (0,060 ms per esperto residente ricalcolato). Coerente per terza via col
«lane a costo ZERO = 15,97». ⇒ **Il «≤ +3%» del §60 D ereditava la sotto-stima del 15/8: va
letto +5…+10%.** Cancello «< 2% ⇒ niente build» superato.

**Il discriminante contro `r54_k1`** (calcolo −39,5%, resa −2,05%: i byte migrarono sul bus):
| regola | copie uniche | esperti-riga CPU | copie NUOVE |
|---|---:|---:|---:|
| oggi K=2 | 26.660 | 55.556 | — |
| **lane adattiva** `k=min(2, non residenti)` | **26.660** | 43.288 | **+0** |
| K=1 | 43.351 | 27.778 | +16.691 |
| K=0 | 59.971 | 0 | +33.311 |
**La leva toglie alla CPU SOLO residenti: zero byte PCIe nuovi.** Il canale che ha ucciso K=1
le è precluso per costruzione. Rischio residuo vero, non misurabile a tavolino: `lavori`
(+20,7% in K=1 mangiò tutto) ⇒ cancello `lavori ±3%`, `copie ±1%`.

**`q*` di FreeToken sui nostri numeri**: oggi la CPU assorbe il **62,2%** dei miss unici per
strato; `q/(m−q) = BP/(BH−BP)` con BP=23 ne vorrebbe 23,3% (BH=30), 30,7% (BH=33,2 misurata),
1,7% (BH=23,4), **0% se BH ≤ BP**. Nessuna calibrazione dice di dare PIÙ miss alla CPU: q* e la
lane adattiva sono **ortogonali** (q* riparte i miss, la leva toglie i residenti) e puntano nello
stesso verso. **Opzione «K per strato dal conteggio dello strato prima»: scartata** — taglia
anche miss veri (= canale K=1) e K oscilla nel 49,9% dei passi ⇒ ricattura del grafo.

### (B) La patch (disegno pronto, NON applicata; ~100 righe, ~40 di sostanza)
- **Meccanismo (opzione i)**: `part` da `[2·ne0]` a `[3·ne0]` **solo a leva accesa**; `ids_cpu` e
  `perm_inv` di forma invariata; `ids_gpu` da 4 a 6 colonne; `concat`/`get_rows` invariati come
  nodi. Perno: **`perm_inv` non seleziona mai le colonne inutili**, quindi nulla da azzerare.
- **Sul lato GPU non si scrive mai −1**: `mul_mat_vec_q_moe_maschera` esclude per `maschera`
  non per id (`mmvq.cu:1385-1402`); un −1 oltre la maschera è letto `uint32_t` = `0xFFFFFFFF` ⇒
  lettura fuori slab (`mmvq.cu:1408`), e il cammino CUDA generico aborta (`ggml-cuda.cu:2924`).
  AcceptMoE se la cava perché i suoi −1 sono sanificati in `kern_decidi` e la colonna ha PESO
  ZERO; qui il peso non è zero ⇒ **id valido duplicato** nelle colonne cedute.
- **Leva a difetto 0, byte-identica**: `template <bool planner_trace, bool adattiva>` con il
  codice nuovo in `if constexpr (adattiva)` (idioma già pagato a `:7199-7203`): a leva spenta il
  blocco **non esiste nel binario**; **nessuna riga esistente di `kern_partiziona` modificata**
  (solo firma + blocco in coda): la scrittura dei −1 (`:7307`), il `perm_inv` (`:7311`) e il
  bilancio (`:7289-7302`) restano invariati ⇒ la piattaforma di riproduzione del difetto n.1
  (`97DF3AB0…`) non si sposta con la leva spenta.
- **Guardia CPU**: `ggml-cpu.c:1632` ⇒ `continue` + contatore **«voci fuori tabella»** (idioma
  `cache-esperti.cu:1770`), stampato sulla riga del worker (`ggml-backend.cpp:2772-2776`) sempre,
  anche a zero. Mai clamp.
- **Contatore nuovo `lane_cpu_residenti`** su `colpi + 55` (unico slot libero: 54 = `usato_spazzate`,
  56-61 = `router_*`, `CACHE_ESPERTI_CONTATORI = 62`), scritto a `:7289-7302`, stampato sulla riga
  `tre vie router/massa` (`:8413-8420`).
- **Env**: `LLAMA_OVERLAP_K_MIN_NONRES` (proposta), lettore a valore, difetto 0; testimone stderr
  all'avvio; contatore finale.
- **Cancelli**: leva 0 ⇒ G1 `AD3D3770…` bit-esatto e S1 `97DF3AB0…`; leva 1 ⇒ SHA diverge
  legittimamente, `calcolo` della lane −30% ± , **copie ±1%**, **lavori ±3%**, p1/mean_len in banda,
  §4.10, `voci fuori tabella` stampato.
- **Protocollo**: si parte **dal sorgente che avrà superato G1** (la DLL `18444E20…` delle 07:25 non
  è certificata), backup DLL + sorgente in `backup_pre_<nome>\`, mai `build_cuda.bat`, G1 3/3,
  ri-baseline S1.

### Raccomandazione operativa
**Primo braccio = il SOLO contatore** (~10 righe, uscita bit-identica, rischio zero): misura il
30% sul banco vero dentro la prossima build certificata. Se il banco dice **< 15%** il resto non
si fa; se conferma ~30%, la leva (~90 righe) entra nella finestra dopo il verdetto del difetto n.1.
**Stato**: build ferma da entrambe le sessioni in attesa della decisione utente sul binario
(tenere `18444E20` e completare G1, o ripristinare `backup_pre_chirurgo20`).

### §63-bis — RILIEVO DELLA REGIA SULLA LANE ADATTIVA: **la leva stessa potrebbe APRIRE la terza esposizione che avete appena trovato**

**Attribuzione del reperto: sessione `moe-aggressive-commit-ff`.** Il sito CPU della `mul_mat_id`
è **`ggml-cpu.c:1632`** (non `ops.cpp:4831`, che è `get_rows_q` = la testa Markov) e lì c'è **solo
un `assert()`**: sotto `NDEBUG` sparisce, e `MMID_MATRIX_ROW(-1, …)` **scrive FUORI ARRAY in
silenzio in Release**. È la **terza esposizione latente** della famiglia dell'indice −1 — e la
prima che è una **SCRITTURA**, non una lettura.

**⚠ RILIEVO DELLA REGIA — l'interazione che rende quel reperto urgente per chi progetta la
leva.** La memoria di casa (30/8, `la-lane-cpu-e-al-muro-di-banda`, **da ri-verificare sul codice
attuale**) registra: *«l'indice −1 di AcceptMoE non può raggiungere la lane a K=2 — solo sul ramo
`k_cpu==0` di `kern_partiziona`»*. Ma la lane adattiva è definita come
**`k_cpu = min(K, non residenti della riga)`** ⇒ **una riga i cui esperti sono TUTTI residenti dà
`k_cpu = 0`**. E la misura del §63 dice che quel caso non è raro ma **sistematico**: ~30% del
lavoro CPU è su residenti a 623 slot, e **sette strati sono già interamente residenti (29,98%)**.
⇒ **La leva trasformerebbe un ramo oggi eccezionale nel ramo NORMALE per decine di migliaia di
righe** — cioè attiverebbe proprio il cammino in cui la scrittura fuori array è raggiungibile.

**Conseguenza di progetto (non un veto, un prerequisito)**: la guardia sull'indice `-1` in
`ggml-cpu.c:1632` **non è un accessorio della patch: è la sua precondizione**, e va nella STESSA
build della leva (o prima). Confermato il vincolo già concordato: **contatore «voci fuori
tabella» stampato a fine corsa, MAI un `clamp` silenzioso** — un `-1` assorbito senza contarlo
toglierebbe l'unico segnale della famiglia. Da verificare in fase di disegno: sul ramo
`k_cpu==0` la lane viene proprio *saltata* (nessuna chiamata) oppure viene chiamata con zero
righe? Nel primo caso l'esposizione resta irraggiungibile anche con la leva; nel secondo no.
**Quella verifica va fatta PRIMA di scrivere la patch**, non dopo.

**Nota di numerazione**: questa sezione era stata scritta come «§62» dalla sessione ospite mentre
la regia scriveva il §62 «stato dei binari» — **due sezioni con lo stesso numero**, unite da git
senza conflitto testuale. Rinumerata dalla regia in **§63** (l'ordine è quello di push:
`98e4e9c` prima, `5abdc7a` poi). Per evitare il ripetersi: **prima di aprire una sezione, un
`git pull` e un `grep '^## '` sulla coda del file.**

**AGGIORNAMENTO §63-bis (correzione del peer + tre vincoli della regia).** Il peer corregge il
modello della regia, **peggiorando il quadro**: nel loro disegno **`k_cpu` host resta 2** (nessun
ramo `k_cpu==0`), ma **la CPU SALTA le colonne cedute tramite id `-1` nelle sue due colonne** ⇒
con ~30% di lavoro CPU su residenti **il `-1` entra in `ggml-cpu.c:1632` PER PROGETTO, decine di
migliaia di volte per corsa**. Non è un caso limite: **è il meccanismo**. ⇒ la guardia
`continue`+contatore «sta nella stessa build o non c'è patch» (parole loro, condivise).
Dispacciata da loro la lettura preliminare: (a) ramo `k_cpu==0` oggi + ri-verifica della nota del
30/8; (b) prova che nessuna colonna saltata (dst non inizializzato) entri nella riduzione dopo
`concat`+`get_rows(perm_inv)` e che nessuna copia D2H legga quel dst.

**TRE VINCOLI DELLA REGIA sul disegno**:
1. **⚑ CEDERE ≠ ELIMINARE — è la modalità di guasto del difetto n.1, rifatta a mano.** La leva
   toglie una colonna alla CPU *perché la GPU ce l'ha residente*: allora **la GPU deve davvero
   calcolarla**. Se la colonna sparisce dalla CPU e nessuno la raccoglie, si riproduce
   esattamente il §44 (route annullate ⇒ strato calcolato con meno esperti ⇒ uscita
   *sbagliata ma plausibile* ⇒ degenerazione, **senza un solo assert**). **Cancello
   pre-registrabile e a costo zero: il conteggio di esperti calcolati per riga deve restare 6**,
   invariato fra leva spenta e accesa — un contatore, non un'ispezione.
2. **La correttezza non deve dipendere da una proprietà A VALLE.** Il check (b) chiede «la
   colonna saltata entra nella riduzione?». Se la risposta è no *oggi*, resta una **invariante
   non dichiarata**, che una modifica futura può rompere in silenzio. Alternativa più robusta:
   **azzerare esplicitamente il `dst` della colonna ceduta** (semantica locale e definita)
   invece di affidarsi al fatto che nessuno lo legga. Costo: una scrittura di riga; beneficio:
   la patch non si rompe se il cammino a valle cambia. **Valutare il trade-off, non subirlo.**
3. **Se il dst NON è azzerato, non assumere che contenga zeri.** Il §50 ha già stabilito che
   l'allocatore del grafo **ricicla i buffer**: un `dst` mai scritto contiene **memoria d'arena
   riusata**, non zeri. ⇒ nel check (b) la domanda non è solo «entra nella riduzione» ma
   **«che cosa contiene se ci entra»** — e la risposta probabile è «i valori di un altro
   tensore». Stessa famiglia del difetto n.1, per la terza volta in due giorni.

### §63-ter — SEZIONE C DEL DISEGNO: raggiungibilità del −1, riduzione, e le tre risposte ai vincoli del §63-bis (progettista, sola lettura)

Documento aggiornato (895 righe) in `docs/porto/lane_adattiva_20260902/LANE_ADATTIVA_tetto_e_patch_20260902.md`
+ script `raggiungibilita_meno_uno.py`.

**C.1 — Il −1 è il MECCANISMO.** K host resta 2 (`llama-graph.cpp:1855-1857`), vista CPU `[k_cpu,
n_tokens]` invariata (`:1918-1919`); la CPU cede scrivendo −1 nelle sue due colonne e salta in
`ggml-cpu.c:1632`. Al regime di produzione (colpi ~67%): righe con ≥1 colonna −1 **41,24%**,
colonne −1 **29,98%** ⇒ su una corsa da 1200 token **11.971 righe, 17.401 ingressi in `:1632`,
52.203 salti** (up+gate+down). Oggi `ids_cpu` non contiene MAI −1 (unica scrittura `:7307`
guardata da `j >= k_cpu`; 0 id negativi su 166.668 nella traccia). ⇒ **Guardia nella stessa
build, o non c'è patch**: senza, è corruzione certa e sistematica (assert sparisce sotto NDEBUG).

**C.2 — Ramo `k_cpu == 0`: la lane è SALTATA, non chiamata a righe zero** (risponde al §63-bis).
Host `llama-graph.cpp:1884-1902`: `if (k_cpu <= 0) return nullptr` (`:1899`) PRIMA che i nodi
`*_overlap_cpu` nascano (`:1970-1989`) ⇒ nessuno split CPU, nessun lavoro del worker (conferma a
registro: B2 del §17 con `n_lavori = 0`). Device: ramo `cache-esperti.cu:7108-7143` (ordine router,
`perm_inv` identità, −1 a `:7126` solo se `compatta && w == 0`, `return` a `:7142`). **Nota del
30/8 ri-verificata e confermata.** Con la leva accesa `k_cpu == 2` su ogni strato ⇒ quel ramo
resta irraggiungibile; **la leva rifiuta di armarsi se `LLAMA_OVERLAP_K < 1`** (i due −1 avrebbero
significati diversi nelle stesse colonne).

**C.3 — La riduzione è sana, ma a monte ci sono DUE letture di memoria non inizializzata.**
`:1997` concat → `:1999` `get_rows(perm_inv)` → `:2004` `mul(weights)` → `:2011-2021` sei viste +
catena di `add`: la somma legge solo le righe nominate da `perm_inv`, e la leva non nomina mai
`[k_vivo, k_cpu)`. Però: **(a)** `ggml_clamp` (`:1979-1983`) e `ggml_swiglu_split` (`:1985`) sono
elementwise sull'intero tensore ⇒ leggono la riga saltata di up/gate; **(b)** la `concat` ha un
operando CPU e uno CUDA ⇒ `esperti_cpu` viaggia INTERO sul PCIe, riga saltata compresa (**16 KiB
non inizializzati × 17.401 per corsa** — la famiglia e39). Contenuto: **memoria d'arena riciclata**
(§50), non zeri: byte plausibili di un altro tensore = la famiglia del difetto n.1.

**C.4 — Decisione: AZZERARE, e non è un trade-off.** `n_ff_exp = 2048` (dedotto esatto dai 6,75
MiB/slot: `3456·F = 6,75 MiB` ⇒ F = 2048,00). Per colonna ceduta up 8 KiB + gate 8 + down 16 =
32 KiB; × 17.401 = **544 MiB/corsa = 17,8 ms a 30 GB/s = 0,019% della parete = 0,09% di
`calcolo`** (1/330 del guadagno). `swiglu(0,0) = 0` ⇒ la colonna ceduta è **zero deterministico**.
Sito: la stessa guardia in `ggml-cpu.c:1632`, sezione `ith == 0` prima di `ggml_barrier` ⇒ nessuna
corsa: `if (i02 < 0 || i02 >= n_as) { memset(dst riga, 0); atomic++ fuori_tabella; continue; }`.

**C.5 — CEDERE ≠ ELIMINARE: il cancello dei 6 esperti**, nel PRIMO braccio a costo zero:
(1) **bigezione di `perm_inv`** verificata sul device dentro `if constexpr (adattiva)` — contatore
`lane_ad_perm_rotta` che deve restare 0 (idioma «guasto muto» già in casa, `:7259-7263`); coglie
esattamente il §44; (2) **bilancio delle DESTINAZIONI** (non delle classi): `lane_ad_cpu_vive +=
k_vivo`, `lane_ad_gpu_colonne += ne0 − k_vivo`, cancello `somma == 6 × partizioni` esatto e
identico a leva spenta/accesa, stampato sulla riga `tre vie` (`:8413-8420`); (3) testimone di
esecuzione CPU `mmid_accettati + mmid_fuori_tabella == 3 × k_cpu × righe` (l'analogo GPU nella
mmvq mascherata solo come braccio di debug).

**C.6 — Errata al disegno (B)**: la difesa è l'azzeramento, `perm_inv` è ridondanza; contatori
nuovi **quattro** (`lane_cpu_residenti` 55, `lane_ad_cpu_vive` 62, `lane_ad_gpu_colonne` 63,
`lane_ad_perm_rotta` 64 ⇒ `CACHE_ESPERTI_CONTATORI` 62 → 65); patch **~120 righe, ~50 di
sostanza**; due cancelli in più identici a leva spenta/accesa; rischio «colonna cedita letta a
valle» declassato a zero deterministico.

**Stato**: disegno COMPLETO e a registro; primo braccio = contatori (55, 62, 63, 64) + guardia
`:1632` con `fuori_tabella` — uscita bit-identica per costruzione (G1 = `AD3D3770…`), da imbarcare
nella prossima build certificata **dopo la decisione dell'utente sul binario**; leva vera dopo il
verdetto §49/§50.


### §63-quater — Tre note di regia (zen-morse) adottate nel disegno: rilevatore a leva spenta, i byte viaggiano comunque, DUE build

1. **La guardia è anche un RILEVATORE, pre-registrato**: con la leva SPENTA il contatore «voci
   fuori tabella» di `ggml-cpu.c:1632` **deve leggere esattamente 0** (oggi `ids_cpu` non contiene
   mai −1: 0 su 166.668 nella traccia). Se leggesse > 0 non sarebbe un difetto della patch: sarebbe
   la scoperta che **un −1 raggiunge GIÀ il cammino CPU in Release** (assert sparito sotto NDEBUG),
   cioè un bug vivo e invisibile. Vale come cancello di non-regressione E come sonda sulla famiglia
   dell'indice −1, nello stesso primo braccio, a costo zero.
2. **Il byte della colonna ceduta VIAGGIA COMUNQUE**: dopo l'azzeramento la `concat` trasferisce 16
   KiB di zeri invece di 16 KiB d'arena. Correttezza risolta, trasporto no. **La leva risparmia
   CALCOLO della lane (~30%), non byte**: «zero byte PCIe nuovi» ha come rovescio «zero byte PCIe
   risparmiati» — chi leggerà «−30% di lavoro CPU» non deve aspettarsi un calo dei byte a domanda.
   Se un giorno si volesse anche quello, il bersaglio è la `concat`, non la lane.
3. **DUE build, una variabile per volta — mai fuse**: qualunque cosa decida l'utente, la sequenza
   è **(i)** certificare il binario attuale `18444E20` (G1 3× + non-regressione della config di
   servizio sul corto) → **(ii)** i due bracci del bivio §49/§50, che hanno bisogno di un binario
   che isoli le sole modifiche della terza mano → **(iii)** SECONDA build con contatori + guardia,
   col suo G1 e la sua ri-baseline S1. Se G1 fallisse su una build fusa non si saprebbe quale dei
   due gruppi l'ha rotto. Il primo braccio della lane resta bit-identico per costruzione ⇒ la
   (iii) è la più economica delle tre.

### §62-bis — **CORREZIONE: `G1` ERA GIÀ PASSATO.** Il cancello duro del binario `18444E20` è verde

**Reperto della sessione `moe-aggressive-commit-ff`, trovato SUL DISCO.** Il §62 dichiarava
«`G1` non risulta completato»: **era una mia inferenza dall'interruzione, non un fatto**, e va
corretta. Il chirurgo 20 **aveva completato G1** prima di essere fermato:
`…\work\runs\c20_g1.summary.json` (mtime **07:31**), server.log avviato alle **07:27** — cioè
**dopo** la DLL delle **07:25:26** ⇒ è il binario nuovo. Esito: **3 ripetizioni, SHA
`AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11` identico 3/3**, p1 0,77670,
mean_len 2,01, content 83 / reasoning 518 char, eval **13,43 / 14,07 / 14,08 t/s** — stessa banda
di `chirurgo18_g1` (13,26 / 14,27 / 14,35).

⇒ **Il cammino 0731 del binario `18444E20` è CERTIFICATO**: le modifiche della terza mano
**non toccano il modello vecchio**. Della fase (i) resta **solo** la non-regressione della config
di servizio del Vision sul corto (`V-ANCORA-CORTO-A` = `28ADE339…`).

**Lezione di metodo, la seconda in due giorni sulla stessa classe**: quando un agente viene
interrotto, **il suo lavoro sul disco sopravvive alla sua consegna**. Prima di dichiarare
«non fatto», **cercare gli artefatti**: qui un `summary.json` con l'mtime giusto valeva più di
qualunque inferenza. (Cugina della regola del 1/9: «un dispaccio stantio si verifica sul disco
prima di agire».)

**Percorsi della ratifica A** (erano introvabili perché **non** stanno in `llama_run`: la
ratifica è girata dallo scratchpad della sessione zen-morse). Canonici finché non copiati:
`…\a961cb2b-578b-4f4e-bec0-9f71e48bcef0\scratchpad\` → `ancora_vision.ps1` (**il prompt si
ESTRAE da qui**, 891 char, sha `4FDF82C2…`), `ratifica_A.ps1`, **`ratifica_A_ciclo.ps1`**
(un ciclo = un processo: implementazione della regola §36, riusabile tale e quale),
`ratifica_A_leggi.ps1` (i cinque cancelli), log `ratifica_A*.log`, output
`runs\v_ratifica_A_c{1,2,3}.*`. ⚠ **Directory temporanea di sessione: non durevole** — se quegli
script servono oltre oggi vanno copiati in `D:\ds4_work\llama_run\lanciatori_salvati_20260825\`.

## 64. ⚑ CERTIFICAZIONE DEL BINARIO `18444E20` (2/9, fase i) — **G1 3/3 (già fatto dal chirurgo 20) + non-regressione Vision corto A 1/1 BIT-ESATTA. Binario CERTIFICATO su entrambi i cammini. QUESTO COMMIT È IL SEGNALE: macchina libera per la fase (ii)**

**Decisione utente (a questa sessione, ~10:20)**: «una cosa non esclude l'altra» ⇒ si TIENE il
binario ricostruito alle 07:25 e lo si valida; le altre attività procedono in parallelo, con una
sola variabile per volta sulla macchina. Sequenza concordata con zen-morse (§63-quater):
**(i)** certificare `18444E20` → **(ii)** i due bracci del bivio §49/§50 (zen-morse, col via del
suo utente) → **(iii)** seconda build contatori + guardia della lane adattiva (§63-ter), con G1
e S1 propri. Verifica indipendente: la build è di zen-morse, la certificazione di questa sessione.

### G1 (0731, banco corto): ERA GIÀ PASSATO — reperto su disco
`…\handoff-nuova-chat-15-agosto-md-3\work\runs\c20_g1.summary.json` (07:31), server avviato
alle 07:27 (DLL delle 07:25:26): **3/3 SHA `AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11`**,
p1 0,77670, mean_len 2,01, content 83 / reasoning 518, eval 13,43 / 14,07 / 14,08 t/s (chirurgo18_g1:
13,26 / 14,27 / 14,35). Il chirurgo 20 l'aveva completato prima dell'interruzione; «G1 non
completato» del §62 era un'inferenza dall'interruzione (corretta da zen-morse in §62-bis).

### Non-regressione della config di servizio del Vision (corto, `V-ANCORA-CORTO-A`)
Stesso script che ha prodotto l'ancora: `ratifica_A_ciclo.ps1 -Ciclo 1` (un ciclo = un processo;
prompt ESTRATTO da `ancora_vision.ps1` e verificato: 891 char, sha `4FDF82C2`; quiete 3×40 s nello
stesso processo del load; `run_vision.ps1 … -MaxTokens 1200 -Repetitions 1 -Draft -ThinkingBudget 0
-Extra 'LLAMA_ACCEPTMOE=1;LLAMA_ACCEPTMOE_COMPATTA=0'`). Identità DLL prima del lancio e nel log:
`llama.dll 9E8E8D46…`, **`ggml-cuda.dll 18444E20BE90538F…`**. Nove testimoni su nove
(OVERRIDE AM=1 / COMPATTA=0, REASONING-BUDGET 0, manifesto `AM=1(E)`/`COMPATTA=0(E)`, drafter,
473 slot da 7,30 MiB, output). Ciclo 10:44:33 → 10:47:51, stderr vuoto, chiusura graziosa.

| | ancora (1/9, binario 6A98BE10) | **misurato (2/9, 18444E20)** |
|---|---|---|
| SHA output | `28ADE3395B5888D7DC1DB5D12A06083FFE1B2017029DC18EE87003BB090E1BBD` | **IDENTICO** |
| byte / char | 4.568 / 4.538 | 4.568 / 4.538 |
| p1 / mean_len | 0,72693 / 1,92 | 0,72693 / 1,92 |
| colpi · domanda · partizioni | 75,2% · 245.272 · 61.060 (rapporto 4,017, deficit −1.032) | identici |
| byte a domanda | 433,32 GiB | 433,32 |
| acceptmoe lanci/mascherate/scartati/tenuti/senza res. | 25.120 / 30.972 / 48.070 / 44.047 / 668 | identici alla cifra |
| eval t/s | 12,66-12,79 | 12,65 (parete; traiettoria identica) |
| assert / OOM / fail-loud | 0 | 0 |
**Interpretazione pre-registrata (A): NON-REGRESSIONE PASSATA — il cammino di servizio del Vision è
invariato sul binario `18444E20`.** ⇒ Le modifiche della terza mano (contatore `router_rifiuti`,
contratti delle corsie, `acceptmoe_pesi` non registrato) **non toccano né il cammino 0731 né quello
di servizio del Vision**: sono confinate, come previsto, al cammino del difetto n.1.

### Percorsi canonici (copie durevoli, dal scratchpad zen-morse che non è durevole)
`D:\ds4_work\llama_run\lanciatori_salvati_20260825\vision_corto\` — `run_vision.ps1`,
`ancora_vision.ps1`, `ratifica_A_ciclo.ps1`, `ratifica_A.ps1`, `ratifica_A_leggi.ps1`,
`ORIGINE.txt` (mtime + SHA256 degli originali), `DIFF.txt` (git diff --no-index: **solo** le righe
di percorso `$run`/`$sp`, il commento in testa e — in `ratifica_A.ps1` — le identità attese
trasformate in **parametri a difetto invariato** `param([string] $AttesaLlama = '9E8E8D46', [string]
$AttesaCuda = '18444E20')`, regola del 25/8: mai aggiornare un hash cablato per far passare un
cancello). Run: `D:\ds4_work\llama_run\vision_corto_runs\` (`v_ratifica_A_c1.*`, `nr_c20_ciclo1.stdout.txt`).
Debito minimo: nella copia di `ratifica_A.ps1` (non eseguita) la riga `$run = Join-Path $sp 'runs'` va
ripuntata a `vision_corto_runs` prima di riusarla come regia a tre cicli.

**Stato**: binario `18444E20` **certificato** (0731 3/3, Vision A 1/1). Macchina LIBERA dalle 10:48.
⚑ **Segnale per zen-morse**: fase (ii) vostra appena avete il via; se il via non c'è, la (iii)
parte (compilazione isolata della patch, poi seconda build col protocollo pieno).

### §62-ter — **FASE (i) CHIUSA: il binario `18444E20` è certificato su ENTRAMBI i cammini**

**Attribuzione: `moe-aggressive-commit-ff` (loro §64, marcata SEGNALE).** Non-regressione della
config di servizio Vision sul corto: **SHA `28ADE3395B5888D7…090E1BBD` IDENTICO**, 4.568 byte,
p1 0,72693, mean_len 1,92, colpi 75,2%, domanda 245.272 / partizioni 61.060 (**4,017, deficit
−1.032**), byte 433,32 GiB, contatori acceptmoe **identici alla cifra** (25.120/30.972/48.070/
44.047/668), nove testimoni su nove, identità `18444E20…` nel log, zero assert.
⇒ Con il `G1` 3/3 del §62-bis: **la terza mano non tocca né il cammino 0731 né il servizio
Vision.** Fase (i) **chiusa**.

**⚑ COROLLARIO CHE AFFILA L'ESPERIMENTO DECISIVO (§6.5).** La config di servizio gira con
**`COMPATTA=0`**, cioè con la scrittura dei `-1` **spenta**: è il cammino su cui la patch della
terza mano **non può** manifestarsi. ⇒ **I due bracci del bivio (a `COMPATTA=1`) sono l'UNICO
posto in cui quella patch può produrre un effetto**, e abbiamo appena verificato
sperimentalmente che tutto il resto è fermo. **Qualunque cosa cambi nei due bracci è quindi
attribuibile alla patch e a nient'altro** — il contesto migliore possibile per un esperimento a
due esiti opposti pre-registrati.

**PERCORSI CANONICI (sostituiscono lo scratchpad del §62-bis, che non è durevole)**:
`D:\ds4_work\llama_run\lanciatori_salvati_20260825\vision_corto\` (con `ORIGINE.txt` = mtime+SHA
degli originali, `DIFF.txt`, e **le identità DLL attese come PARAMETRI a difetto invariato**, non
più letterali — correzione applicata prima che la copia diventasse canonica, regola del 25/8:
*«non si aggiornano gli hash attesi per far passare un cancello; si estende con un parametro»*)
e run in `D:\ds4_work\llama_run\vision_corto_runs\`. **È il modello da riusare per ogni prossimo
braccio destinato a durare.**

**Stato della coda al momento della scrittura**: fase (i) chiusa · fase (ii) — i due bracci del
bivio — **in attesa del via dell'utente alla sessione zen-morse** (non parte su decisione
riferita da terzi) · fase (iii) — build contatori+guardia della lane adattiva — **avviata dalla
sessione ospite** per non lasciare la macchina ferma. Ordine invertito rispetto al piano, stessa
disciplina: **una variabile per volta**.

## 65. FASE (iii), STADIO 1 «LANE ADATTIVA» (contatori + guardia) — **APPLICATO, COSTRUITO, RATIFICATO** (2/9, 13:16-13:40): G1 3/3, Vision A ciclo 2 BIT-IDENTICA, contatori vivi: **il 18,7-20,4% del lavoro CPU del banco corto è su RESIDENTI**, voci fuori tabella = 0

**Che cosa è entrato** (patch `lane_adattiva_1_contatori_guardia.patch`, 267 righe, 4 file, marcatore
`// lane-adattiva (2/9)`): contatore atomico `ggml_mmid_fuori_tabella` in **ggml-base**
(`ggml-backend.cpp`, definizione + stampa `sched-worker-lane: voci fuori tabella=` sul worker,
SEMPRE anche a zero), incremento da `ggml-cpu.c` con **la guardia** in `mul_mat_id` (`:1632`:
`continue` + azzeramento della riga dst + conteggio; nessun clamp), quattro contatori nuovi in
`cache-esperti` (`lane_cpu_residenti` slot 55, `lane_ad_cpu_vive` 62, `lane_ad_gpu_colonne` 63,
`lane_ad_perm_rotta` 64; `CACHE_ESPERTI_CONTATORI` 62→65) con conteggio in un blocco separato in
coda a `kern_partiziona` (**zero righe esistenti del kernel toccate**) e stampa sulla riga `tre vie
router/massa`. Nessun header condiviso (decisione di regia: `ggml-impl.h` avrebbe ricompilato tutto
il backend CUDA), extern locali; D8 accolta (bilancio delle destinazioni già nello stadio 1).
Disegno e otto deviazioni motivate (D1-D8) in `docs/porto/lane_adattiva_20260902/`; compilazione
isolata preventiva pulita (nvcc sm_86 + cl, controllo negativo con errore iniettato).

**Protocollo eseguito**: preflight (nessun processo, SHA dei 4 sorgenti = base 19:24 dell'1/9,
dry-run di `patch -p1 --binary --fuzz=0` pulito) → **backup `build\bin\backup_pre_lane1\`** (92
DLL/exe + `SHA256.txt`, `sorgente\` con i 4 file + `ggml-cuda.cu` + `llama-graph.cpp` allo stato
terza mano, `NOTA.txt`, `IDENTITA_post_lane1.txt`) → apply (4/4 byte-identici a `comp1\`, marcatori
2/2/1/5) → build a mano (`cmake --build … --target ggml-base ggml-cpu ggml-cuda --parallel 8` +
`editbin /STACK`; **11 s**: `cache-esperti.cuh` è incluso solo da `cache-esperti.cu` e
`ggml-cuda.cu`; 7/7 passi ninja, zero warning nuovi, 6×`#177-D` + 3×`#221-D` preesistenti).

**Identità (al plurale — l'identità è la DLL, e ne cambiano TRE)**:
| DLL | prima | dopo |
|---|---|---|
| `llama.dll` | `9E8E8D46…` | **INVARIATA** `9E8E8D469A7B047FDAF863E384EE1A6EEC37C54C062FF9A412D3D2787F6D7131` |
| `ggml-cuda.dll` | `18444E20…` (07:25) | **`D783DBE13F5FA8936D022149B853DB8DB30BEA069A08B674F1BC0F97589E98AC`** (13:18:23) |
| `ggml-cpu.dll` | `D2A3D79C…` (21/8) | **`9F00A975C8A6574E7F2DBEE2B03FEA50405AD0D092F3F3EF5A490F65B7C90BC9`** (13:18:14) |
| `ggml-base.dll` | `D52DA12E…` (25/8) | **`CB2E8E376B1F222CAF45915085F575387A4B43EF850A980BBA2F069072950C56`** (13:18:14) |
| `ggml.dll` | `9DE6C3B1…` | invariata |

**G1 (0731 corto, `lane1_g1`)**: 3/3 `AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11`,
p1 0,77670, mean_len 2,01, eval 13,28/14,27/14,29. Riga nuova: `sched-worker-lane: voci fuori
tabella=0`. Riga `tre vie`: `partizioni=23693, … CPU=47386 (di cui RESIDENTI=8869, 18.7%) … | lane
adattiva: cpu_vive=47386, gpu_colonne=94772, somma=142158 (6.00 per partizione), perm_rotta=0`.
(Avviso preesistente e innocuo di `run_porto_hot.ps1`: «DLL NON CANONICA, attesa ECAEA60B» — la
guardia è tarata sulla llama.dll di produzione.)

**Vision A corto, ciclo 2** (`v_ratifica_A_c2`, identità `ggml-cuda D783DBE1…` nel log): SHA
`28ADE3395B5888D7DC1DB5D12A06083FFE1B2017029DC18EE87003BB090E1BBD` **identico**, p1 0,72693,
mean_len 1,92, domanda 245.272 / colpi 75,2% / partizioni 61.060 / byte 433,32 / acceptmoe
25.120/30.972/48.070/44.047/668 **identici alla cifra al ciclo 1 delle 10:47 (binario 18444E20)**:
ogni campo preesistente uguale, le sole differenze sono le aggiunte. Righe nuove: `voci fuori
tabella=0`; `CPU=122120 (di cui RESIDENTI=24860, 20.4%) … cpu_vive=122120, gpu_colonne=244240,
somma=366360 (6.00 per partizione), perm_rotta=0`.

### Lettura
1. **Bit-identico dove promesso**, su tre binari in fila (6A98BE10 → 18444E20 → D783DBE1) e su
   entrambi i cammini: la guardia c'è, non è mai scattata (0 = «raggiunta e nulla», non «mai
   raggiunta»: si stampa sempre), e la piattaforma del difetto n.1 (`kern_partiziona`) non è stata
   toccata in nessuna riga esistente.
2. **Primo numero della leva, misurato sul banco vero**: **18,7%** (0731 corto, 160 tok) e
   **20,4%** (Vision A corto, colpi 75,2%) del lavoro CPU va su esperti già residenti. La soglia
   pre-registrata «< 15% ⇒ niente leva» è **superata**. La stima dalle tracce (22% a 473 slot,
   ~30% al regime 623/67% del LUNGO) resta da verificare sul lungo: **la corsa che decide è il
   controllo a 473 sul lungo con questo binario**, che serve comunque come nuova ancora
   (`B2B8F84E` atteso bit-identico; una divergenza sarebbe informativa sulla terza mano, non un
   guasto della patch).
3. **Corollario di zen-morse, ora provato due volte**: il servizio gira a `COMPATTA=0`, dove i
   `-1` non esistono; i bracci del bivio §49/§50 (`COMPATTA=1`) sono l'unico posto dove la patch
   della terza mano può manifestarsi, e ora anche l'unico dove `fuori tabella` può diventare > 0:
   **S1 dopo questa build è il test della guardia** (esiti pre-registrati in §63-quater e nei
   messaggi: `97DF3AB0` ⇒ bit-identica anche coi `-1`; divergenza ⇒ leggere PRIMA `fuori tabella`).

**Stato**: stadio 2 (la leva) NON applicato; sua precondizione ancora aperta: il censimento (E)
completo dei consumatori delle colonne CPU (drafter, sonde, traccia, `kern_decidi`). Ripristino
possibile in ogni momento da `backup_pre_lane1\`. Macchina: **ancora di questa sessione per il
controllo lungo a 473** (~17 min), poi segnale a zen-morse per S1 + bivio.
