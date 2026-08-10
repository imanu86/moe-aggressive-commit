# 44 — LA MACCHINA DELL'OVERLAP CPU∥GPU: audit completo del sottosistema che da' il nome al ramo

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `24fd5c2ee`,
working tree (contiene la patch VRAM-a-fasi rev.3 non committata). **Niente
compilato, niente server avviato, nessuna misura mia**: codice letto riga per
riga, ledger e audit esistenti citati per numero. Marcatura: [MISURATO] =
log/spazzata in cassa o fatto del mandato, [CONTATO] = codice letto,
[DEDOTTO] = aritmetica su misure, [IPOTESI] = da falsificare con la misura
indicata. Non ripeto i reperti degli audit 13/14 (leve, statico) e 20
(trasversale): li cito e dico solo cosa e' cambiato o cosa aggiungono al quadro.

## Il verdetto in sei righe

1. **La domanda 3 era mezza sbagliata, ed e' la meta' che vale.** I ~45 ms di
   attesa GPU non sono il prezzo della DIPENDENZA dei dati: sono il prezzo di
   COME il join e' implementato. Per ogni strato il rendezvous fa, in
   sequenza: attesa host del worker → **drenaggio COMPLETO dello stream CUDA**
   (`cudaStreamSynchronize`) → H2D **sincrona** del risultato CPU → rilancio
   WDDM. Tutti e quattro i termini sono indipendenti da K — ecco la piattezza.
   La dipendenza vera (concat dello stesso strato) ha un pavimento fisico di
   decine di µs/strato, due ordini sotto. **E' rompibile**, in tre modi ordinati
   per costo (§3.4), e il primo si decide con una corsa gia' strumentata.
2. **Su sette leve, due sole hanno un ottimo misurato** (K=2; BATCH_MAX =
   n-max+1 — imparato pagando). `SPIN=2.000.000` e' un valore di nascita mai
   spazzato; `ASYNC=1` non e' mai stato isolato a parita' di K nel regime
   attuale (il braccio ov0 spegne K e ASYNC insieme); `GRIGLIA_VARIABILE=1`
   non e' mai stata accesa; il default `BATCH_MAX=1` resta senza testimone di
   disingaggio — lo stesso silenzio che ha gia' azzoppato una campagna.
3. **`GRIGLIA_VARIABILE` non e' codice morto: e' un braccio di falsificazione
   mai sparato** — l'unico modo di riprodurre sul binario attuale il difetto
   che la griglia fissa cura. O si spara una volta (10 minuti, verdetto sul
   contatore `div[4]`) e poi si rimuove, o si documenta come leva di replica.
   `PIN` e' vivo e necessario (e' il controllo del cancello A), ma il suo
   lettore `atoi` — difetto noto — **blocca proprio l'esperimento che
   deciderebbe la domanda 3** (§3.5).
4. **Residenza: la partizione e' CONSULTIVA, e la correttezza regge per
   costruzione.** Ordina soltanto; chi serve (`kern_decidi`) ri-valida tutto
   sullo stesso stream. Una promessa invecchiata costa millisecondi (un
   trasporto), mai bit. Il residuo di rischio e' la rivittimizzazione DENTRO
   `kern_decidi` (audit 01), preesistente e non toccata dall'overlap.
5. **Dei tre cantieri di ieri, l'overlap ne "sa" due per costruzione e uno lo
   combatte senza saperlo.** Rollback e VRAM-a-fasi sono sicuri per via del
   `synchronize()` che unisce il worker e della ricattura forzata (uid nuovi a
   ogni rebuild). **AcceptMoE invece gli passa id riscritti che gli tolgono la
   ragione economica**: sulle righe riscritte non restano non-residenti da
   deviare, e il ramo CPU calcola a prezzo pieno esperti residenti o duplicati
   a peso zero. Nessuno dei rapporti 33/36/37/40 nomina la macchina. L'ottimo
   di K con AM accesa e' quasi certamente < 2, e nessun braccio l'ha misurato.
6. **Il prefill e' fuori per un effetto collaterale, non per una decisione** —
   e la motivazione scritta della guardia (replay stantio) a bs=64 e' VUOTA:
   li' i CUDA graph non possono catturare. Ma riaccenderlo non e' una leva:
   sono tre muri indipendenti (abort a n_tok>32, lista da 64, servizio MMVQ<=8)
   piu' un conto economico mai fatto. E' un disegno, non un parametro (§7).

---

## 1. La macchina, pezzo per pezzo [CONTATO]

Per orientare chi arriva dopo: il ciclo di UNO strato MoE nel decode, con
`K=2, ASYNC=1, PIN=1, BATCH_MAX=2` (la configurazione dei runner), e ogni
passaggio con la sua riga.

**Costruzione del grafo** (una volta per forma):

- `build_moe_ffn` chiama l'overlap solo su profilo DSV4 esatto
  (`llama-graph.cpp:2266-2276`); `nullptr` = percorso classico intoccato.
- `build_moe_ffn_overlap` (`llama-graph.cpp:1786-1971`): legge K con `atof`
  (1823-1826), Bresenham per strato (1827-1828), guardia batch (1847-1856),
  inserisce l'op di partizione (1864), costruisce ramo GPU poi ramo CPU coi
  nomi `_overlap_cpu` (1883-1921), **espande esplicitamente il ramo GPU prima
  della concat** (1931) perche' l'ordine di esecuzione e' l'ordine nel grafo,
  concat cpu+gpu → riordino via permutazione inversa (1938-1941), coda comune.
- Il pin dei nodi `_overlap_cpu` alla CPU sta in `llama-context.cpp:1595-1623`
  (lettore `atoi` a 1596-1599: il difetto noto di audit 13/14).
- La bozza (dflash) non costruisce mai il ramo: non e' `LLM_ARCH_DEEPSEEK4`.

**Split** (`ggml-backend.cpp`): il confine forzato dopo la partizione
(1509-1528) spezza lo strato in `1a` (attenzione+router+AcceptMoE+partizione),
`1b` (ramo GPU), split CPU, coda GPU. Ogni rebuild assegna **uid nuovi a ogni
split** (1710): e' il lucchetto contro il corto circuito dell'audit 11.

**Dispatch** (`ggml_backend_sched_compute_splits`, 1802-2156), per strato:

1. lancio async di 1a (2012);
2. **dispatch del ramo CPU** (2058-2111): D2H degli ingressi del ramo CPU
   accodate sullo stream di calcolo (2092, `tensor_get_async` — atterra in
   memoria HOST PINNED: il buft CPU dello sched e' l'host-buffer CUDA,
   `llama-context.cpp:452-458`, quindi la D2H e' davvero asincrona), evento
   registrato fra i due lanci (2104), spedizione al worker (2105-2107);
3. lancio async di 1b (2012);
4. lo split CPU e' saltato (2854, e' del worker);
5. **il join** alla coda GPU: qualunque split dopo quello spedito unisce il
   worker (1861-1878, `us_join`);
6. la copia dell'ingresso CPU→CUDA della coda: `cpy_tensor_async` CUDA rifiuta
   sorgenti non-CUDA (`ggml-cuda.cu:3021-3031`) → ramo di ripiego
   (`ggml-backend.cpp:1992-1999`): con `n_copies==1` gli eventi sono nulli →
   `ggml_backend_synchronize(CUDA)` = **`cudaStreamSynchronize` dell'intero
   stream** (`ggml-cuda.cu:3076-3080`) → `tensor_copy` = H2D su
   `cudaStreamPerThread` + **`cudaStreamSynchronize` di quello**
   (`ggml-cuda.cu:731-737`);
7. rilancio della coda GPU.

**Worker** (`ggml-backend.cpp:823-963`): un thread pigro (nasce al primo
lavoro, 2096-2098), spin `LLAMA_OVERLAP_SPIN` (difetto 2.000.000 giri,
858-865) poi condvar; aspetta l'EVENTO dei produttori, non la coda (905), e
calcola il grafo CPU col threadpool (`-t 7`; il thread worker e' worker-0 del
pool). Contatori dedicati gia' nel codice: `attesa-evento`, `calcolo`,
`attesa-lavoro`, `join (sched)` (2143-2151).

**Partizione** (`cache-esperti.cu:2021-2130`): un blocco, griglia FISSA a
`TOK_MAX=32` thread (2124); tre fasi di chiave — 0 non residente, 1 residente
con `usato==0` (prossimo allo sfratto), 2 residente fresco — dentro ogni fase
l'ordine di slot (2063-2084). `k_cpu` NON entra nel kernel: il taglio lo fanno
le viste (contratto in `cache-esperti.cuh:290-307`, con la null-safety: cache
spenta → partizione identita', grafo LEGALE). Slot IN TRANSITO = non residente:
la partizione non promette mai cio' che la cache non puo' ancora servire.
Dentro il kernel vive il rilevatore di replay stantio (2028-2058, pubblicazione
host fuori cattura in `ggml-cuda.cu:4835-4848`): `div[0]` taglia, `div[1..2]`
puntatori, `div[3]` lanci visti dal device, **`div[4]` griglia troppo piccola
al replay** — il testimone che la sonda host non poteva avere.

**Il canale del guadagno, letto nel codice** [CONTATO→DEDOTTO]: gli id del
ramo CPU non passano MAI dal dispatch della cache (il `MUL_MAT_ID` pinnato gira
sul backend CPU coi pesi mappati: nessuna domanda, nessun buco). Il fatto
misurato "l'overlap toglie ~45% delle domande" e' strutturale: K/6 = 33% delle
domande sparisce per costruzione, e siccome la partizione mette i NON residenti
per primi nel taglio CPU, la quota di BUCHI rimossa e' molto piu' alta
(min(K, non-residenti)/non-residenti ≈ 2/2,76 ≈ 72% a colpi 54%). Il
parallelismo esiste ma e' il canale minore: e' il tetto del §3.

---

## 2. Le sette leve: nascita contro misura (domanda 1)

| leva | difetto | origine del difetto | ottimo misurato | verdetto |
|---|---|---|---|---|
| `LLAMA_OVERLAP_K` | 0 (spenta) | scelta A/B (K=0 = grafo strutturalmente identico) | **2** [MISURATO: 1,5→11,53; 2→12,93; 2,5→12,80; 3→12,22] | difetto giusto (e' il controllo); il COMMENTO nel codice e' stantio (§2.1) |
| `LLAMA_OVERLAP_BATCH_MAX` | **1** | guardia di correttezza del 7/8 (`llama-graph.cpp:1835-1846`) | **n-max+1** [MISURATO: campagna azzoppata dal default; runner a 2 con `--spec-draft-n-max 1`] | difetto di nascita MAI aggiornato, e ancora senza testimone (§2.2) |
| `LLAMA_OVERLAP_PIN` | 1 (acceso) | scelta (il pin e' il comportamento dichiarato) | PIN=0 solo come braccio SHA | giusto; lettore `atoi` rotto per 0<K<1 (audit 13/14) — ora BLOCCA un esperimento chiave (§3.5) |
| `LLAMA_OVERLAP_ASYNC` | 0 (spento) | scelta (spento = bit-per-bit di prima) | mai isolato a parita' di K nel regime attuale | i runner lo accendono sempre; il braccio ov0 lega K ad ASYNC (`braccio_ov0.ps1:65`) → l'A/B "drenaggio contro worker" a K=2 fisso NON esiste nel ledger (§2.3) |
| `LLAMA_OVERLAP_SPIN` | 2.000.000 | valore di nascita con motivazione (79 µs/risveglio misurati 6/8) ma **mai spazzato**: nessun `.ps1` lo tocca | nessuno | una corsa `SPIN=0` col profilo attivo chiude la domanda (§2.4) |
| `LLAMA_OVERLAP_GRIGLIA_VARIABILE` | 0 (griglia fissa) | la CURA del replay stantio | 0 e' la cura; 1 mai acceso nel ledger | non morto: braccio di falsificazione mai sparato (§4.1) |
| `LLAMA_OVERLAP_VERIFICA` | 0 (spenta) | leva diagnostica dei cancelli | n/a | viva; budget 100 di processo (audit 14), copertura zero sotto replay — dichiarato nel codice (`ggml-cuda.cu:2563-2571`) |

### 2.1 K=2: la misura ha ragione e il commento e' rimasto al 40% di colpi

Il commento di `build_moe_ffn_overlap` (`llama-graph.cpp:1800-1811`) deriva il
pareggio K=2,33 con colpi al 40% e dichiara 2 e 3 "indistinguibili" (9,98
contro 10,02). Oggi non e' piu' vero: la spazzata da' 12,93 contro 12,22, ben
fuori rumore. **Il modello del commento non e' sbagliato: sono stantii i suoi
ingressi.** Rifacendo lo stesso conto coi numeri del mandato (GPU residente
0,063, CPU 0,242, trasporto 0,221) e colpi ~54% (non-residenti/riga ≈ 2,76):

    0,242·K = (6−K)·0,063 + (2,76−K)·0,221  →  K ≈ 1,9

[DEDOTTO]. L'ottimo misurato (2) e' esattamente dove il modello aggiornato lo
mette: **la salita dei colpi (cache bozza, AcceptMoE, RAM 3200) ha spostato il
pareggio da ~2,3 a ~1,9, e la spazzata l'ha visto prima di noi.** Conseguenza
operativa: l'ottimo di K NON e' una costante della macchina, e' una funzione
del tasso di colpi — ogni cantiere che alza i colpi (semina, capienza, AM)
deve rimisurare K, o lascia sul tavolo il delta.

*Falsificazione*: bracci `K=1,75` e `K=2,25` (TOPK=1, n≥3). Se il modello
aggiornato regge, 1,75 ≥ 2,25; se 2,25 vince, il modello di costo per-esperto
non descrive piu' il ramo e va rifatto dai contatori (`buchi/token` e
`worker calcolo` del profilo, non dai ms).

### 2.2 BATCH_MAX: il default resta il killer silenzioso, e il testimone costa 3 righe

Tutto gia' detto in audit 14 (disingaggio senza testimone, peso alto). Quello
che AGGIUNGO qui: (a) la motivazione originaria della guardia — il replay a
taglia alternata — oggi ha DUE reti sotto (griglia fissa + rilevatore `div`),
quindi il residuo di rischio ad alzarla nel regime speculativo e' sorvegliato
da un contatore, non dalla speranza; (b) il valore giusto e' derivabile in
casa: n-max lo conosce il chiamante (`--spec-draft-n-max`), e la leva potrebbe
avere semantica "0 = auto = n-max+1" senza toccare il difetto 1; (c) nel
frattempo il costo minimo e' **un fprintf una-tantum al primo
`return nullptr` per batch** in `build_moe_ffn_overlap:1852` — il silenzio e'
gia' costato una campagna, il testimone costa tre righe.

*Falsificazione del testimone*: corsa con spec n-max=2 e BATCH_MAX lasciato a
difetto: deve stampare il disingaggio e il profilo deve dare
`worker n lavori/grafo = 0`. Oggi da' zero senza dire perche'.

### 2.3 ASYNC: mai isolato dove conta

`braccio_ov0.ps1:65` fa `K = (AS=='0') ? '0' : '2'`: il braccio "overlap
spento" spegne K e ASYNC INSIEME. La differenza Fase1/Fase2 (drenaggio per
strato contro worker+evento) fu misurata al 7-8/8 (SOTA 9,9), **mai piu' nel
regime attuale** (TOPK=1, rollback, 13,2 t/s). Non e' pedanteria: tutta la
diagnosi del §3 poggia su quel confine. *Braccio mancante*: `K=2, ASYNC=0`
contro `K=2, ASYNC=1`, n≥3, con `GGML_SCHED_PROFILO=1`: la differenza DEVE
comparire in `us_sync` e `join (sched)`, o il worker non sta comprando niente.

### 2.4 SPIN: 2 milioni di giri decisi una volta e mai verificati

La motivazione (79 µs a risveglio × 43 strati = 3,4 ms/token) e' scritta nel
codice (`ggml-backend.cpp:796-801`) ed e' sensata; ma il VALORE 2M e' di
nascita e lo spin gira anche sul lato sched (`worker_unisci` usa lo stesso
`attendi`), cioe' due spinner per join. Con `-t 7` il conto dei core chiude
esattamente (7 di pool + 1 spinner) — di nuovo per costruzione, mai per
misura. *Falsificazione*: tre corse `SPIN=0 / 20000 / 2000000` a K=2 col
profilo: si legge `attesa-lavoro` (worker) e `join (sched)`. Se SPIN=0 non
muove il t/s, il parcheggio non costa e 2M sta occupando un core per niente;
se lo muove, il numero giusto sta probabilmente due ordini sotto 2M (basta
coprire 1-2 ms).

---

## 3. I 45 ms: la catena della dipendenza, e se si rompe (domanda 3)

### 3.1 La catena, riga per riga [CONTATO]

Per ogni strato con ramo CPU, nell'ordine temporale dell'host:

```
host:  lancia 1a ................................. ggml-backend.cpp:2012
host:  accoda D2H ingressi CPU (stream calcolo) ... :2092   (async, dest pinned)
host:  registra evento ............................ :2104
host:  spedisce worker ............................ :2105-2107
host:  lancia 1b ................................. :2012
       [GPU: 1a → D2H → 1b]   [worker: evento → calcolo CPU]
host:  JOIN worker (blocca) ....................... :1861-1878   → us_join
host:  cudaStreamSynchronize(stream calcolo) ...... :1997 → ggml-cuda.cu:3079
       (DRENA 1b: l'host aspetta che la GPU finisca TUTTO)
host:  H2D sincrona del risultato CPU ............. :1999 → ggml-cuda.cu:731-737
       (memcpyAsync su cudaStreamPerThread + streamSynchronize)
host:  lancia la coda GPU (concat, tail, strato+1)  :2012
```

La GPU resta a secco dal completamento di 1b fino al rilancio della coda:
**ogni strato paga almeno drenaggio-osservato + H2D sincrona + sottomissione
WDDM, e questi termini non contengono K.** Quando il ramo CPU sporge oltre 1b
si aggiunge `(fine CPU − fine 1b)` — ed e' esattamente cio' che K=4 ha
mostrato (+15,5 ms/token, GPU al 48%: la parte VARIABILE che compare solo
quando sfonda il pavimento; K_ADATTIVO §0). A 43 strati, 45 ms/43 ≈ 1,0
ms/strato di parte fissa. La piattezza su K=1,5..3 e' la firma del pavimento
fisso, non di una dipendenza insaturabile. [DEDOTTO su MISURATO]

### 3.2 Cosa e' dipendenza vera e cosa no

- **Vera e matematicamente irrompibile**: la coda dello strato L (concat →
  riordino → pesi → somma → residuo) consuma il risultato CPU dello strato L
  (`llama-graph.cpp:1938`). Non si sposta a L+1 senza cambiare la semantica.
  Il suo pavimento FISICO pero' e' la latenza dei dati: ~32 KB di H2D
  (4096 × k_cpu × n_tok × 4B) = decine di µs su PCIe, non ~1 ms.
- **Implementazione, non dipendenza** (tutta rompibile):
  a) il drenaggio completo dello stream per proteggere una copia H2D
     (`:1997`): protegge `input_cpy` dal riuso, ma la copia va sullo stesso
     stream ordinato — l'ordine di stream basta, il drain no;
  b) l'H2D **sincrona** su un altro stream (`ggml-cuda.cu:731-737`);
  c) il join **host-side** che serializza scoperta-fine-CPU → copia → lancio;
  d) un join PER STRATO anche dove il ramo CPU era gia' coperto.

### 3.3 La conferma che non costa nulla ottenere [IPOTESI → misura gratis]

Prima di qualunque patch: **una corsa `GGML_SCHED_PROFILO=1`** a K=2 (lo
strumento e' gia' nel codice, `ggml-backend.cpp:2130-2153`) e leggere per
grafo: `ingressi (di cui sync)`, `join (sched)`, `attesa-evento`, `calcolo`.
La mia previsione, scritta prima della misura come da regola:

- `us_sync/grafo` domina gli ingressi (e' il drenaggio dei 43 join);
- `join (sched)` piccolo a K=2 (il ramo CPU e' coperto: 2×0,242 ≈ 0,5 ms
  dentro una finestra 1b di ~0,7-1 ms piu' code) e grande a K=4;
- `attesa-evento` del worker ≈ durata di 1a: il worker e' AFFAMATO, non lento.

Se `us_sync/grafo` esce piccolo (<5 ms), la mia catena sovrappesa il drain e
il pavimento sta nella sottomissione WDDM: la cura cambia (grafi piu' larghi,
non copie migliori). E' il primo numero da procurarsi.

### 3.4 Le tre rotture, in ordine di costo

1. **Togliere drain e sincronia dalla copia di ritorno** (piccola, in
   `compute_splits`): per l'ingresso proveniente dal backend CPU dopo un join,
   accodare `cudaMemcpyAsync` H2D **sullo stream di calcolo** (sorgente gia'
   pinned per costruzione, §1) invece del ripiego synchronize+tensor_copy.
   L'ordine di stream serializza da solo contro 1b; l'host non osserva piu' la
   fine di 1b e la GPU riceve copia+coda in coda alla sua coda.
   *Falsificazione in contatori*: `us_sync/grafo` deve crollare al valore dei
   soli confini non-overlap; `n lavori/grafo` invariato (43); SHA invariato a
   parita' di binario (la copia cambia percorso, non valori). Attesa GPU (nsys
   o la sonda dei confini): −(drain+H2D) per strato.
2. **Dimezzare i join a massa CPU pari** (media, richiede la cura del §3.5):
   K frazionario sotto 1 produce strati a k=0 SENZA partizione (il Bresenham
   `llama-graph.cpp:1827-1831` torna nullptr → strato classico, zero join).
   `K=0,5` = 21-22 join invece di 43 a meta' massa CPU. Se il pavimento e'
   per-join, l'attesa scala con `n lavori/grafo`; se non scala, il pavimento
   sta altrove (WDDM per-split) e la cura e' un'altra.
   *Falsificazione*: `worker n lavori/grafo` 43 → 21-22 [CONTATO, aritmetica
   Bresenham]; poi leggere se `us_sync+us_join` scala nella stessa proporzione.
3. **Rendezvous device-side** (grande): l'H2D accodata dal worker su uno
   stream suo + `cudaStreamWaitEvent` pre-accodato, oppure
   `cuStreamWaitValue32` su flag host. L'host esce del tutto dal cammino;
   resta la latenza dei dati. Da NON tentare alla cieca su Windows: prima
   sondare `CU_DEVICE_ATTRIBUTE_CAN_USE_STREAM_MEM_OPS` (su WDDM
   storicamente no), e il pre-accodamento di un wait su evento non ancora
   registrato e' terreno minato coi CUDA graph. Solo se 1+2 non bastano.

Nota di perimetro: anche a rendezvous gratis, il tetto successivo e' la parte
del ramo CPU che sporge (K_ADATTIVO: α_cpu→1 a K=4). Le rotture comprano il
PAVIMENTO fisso (~1 ms × strati con lane), non il diritto di alzare K.

### 3.5 Il difetto noto che e' diventato un blocco sperimentale

Il lettore `atoi` del pin (`llama-context.cpp:1596-1599`, audit 13/14, peso
"medio" allora) oggi va rivalutato: **e' l'unico ostacolo fra noi e
l'esperimento 2 del §3.4** (K=0,5 costruisce il ramo CPU ma il pin non lo
vede: split GPU/GPU, ASYNC non spedisce — audit 13 §2). La cura e' allineare i
due lettori (`atof` anche nel pin, o un parser condiviso). Due righe, zero
rischio a K interi (2.0 legge uguale), e sblocca la misura che decide la
domanda piu' cara del mandato.

---

## 4. Codice morto? (domanda 2)

### 4.1 `GRIGLIA_VARIABILE`: il braccio di falsificazione mai sparato

Storia completa nel codice (`cache-esperti.cu:2112-2124`): la griglia fissa a
32 thread e' la CURA del replay a taglia stantia; la leva=1 rimette il
comportamento vecchio (`<<<1, n_tok>>>`) apposta "per il braccio che deve
stabilire se era quella la causa della degenerazione a batch 2", sullo stesso
binario. **Quel braccio nel ledger non esiste**: la causa fu stabilita per
altra via (A/B `GGML_CUDA_DISABLE_GRAPHS=1`, commento in
`llama-graph.cpp:1835-1846`) e la cura fu spedita insieme al rilevatore. La
leva quindi non ha mai fatto il suo unico lavoro.

Non e' morta, e' **inesplosa**, con due esiti possibili:

- *spararla una volta* (10 min): `GRIGLIA_VARIABILE=1, BATCH_MAX=2`, catena
  speculativa, graphs accesi. Attesa: la degenerazione torna E `div[4]` conta
  (il testimone della griglia, `cache-esperti.cu:2049-2056`). Doppia conferma
  causa+testimone; poi la leva si puo' RIMUOVERE con la coscienza pulita;
- *tenerla documentata* come leva di replica del difetto. Costo: una getenv.
  Rischio: l'eredita' d'ambiente — `tools/vram-recovery-run.ps1` non la fissa
  (audit 14 §runner): una sessione contaminata riaccende il difetto proprio
  nel runner di recovery. Se si tiene, va fissata a 0 anche li'.

La mia raccomandazione e' la prima: il rilevatore (`div[4]`) ha reso la leva
ridondante come strumento diagnostico permanente.

### 4.2 `PIN`: vivo, necessario, e con un difetto che ha cambiato peso

PIN=0 e' il braccio "3a puro" del cancello A (SHA identico obbligatorio,
`llama-context.cpp:1600-1609`): serve a ogni futura verifica di equivalenza
della partizione. Non e' rimovibile. Il suo lettore rotto e' il §3.5.

### 4.3 `VERIFICA`: viva, con la copertura che dichiara

Budget 100 di processo (non per build: audit 14), salto in cattura
(`ggml-cuda.cu:2586-2588` — la lezione del K2 morto 0xC0000409), quindi
copertura zero a regime e per progetto. Il commento nel codice ora lo dichiara
onestamente (2563-2571). Nulla da aggiungere ad audit 14 se non: con
l'invariante coperto anche dal rilevatore `div`, VERIFICA e' declassabile a
strumento dei soli cancelli — com'e' gia' usata.

---

## 5. Residenza: decisione contro esecuzione (domanda 4)

La domanda temeva una TOCTOU. La risposta del codice e' che **la partizione
non ha autorita' da tradire**:

1. **Chi decide davvero e' chi serve.** La partizione ORDINA gli id
   (`kern_partiziona` scrive solo `out`; "k_cpu NON serve qui: la partizione
   ordina, il taglio lo fanno le viste", `cache-esperti.cu:2019-2020`). Il
   servizio GPU (`ggml_cuda_cache_esperti_assicura` → `kern_decidi`,
   `ggml-cuda.cu:2325-2348`) ri-legge `dove/chi/usato`, decide gli slot,
   copia i mancanti e SOLO POI la MMVQ legge la vista ombra. Un id promesso
   "residente" e sfrattato nel frattempo diventa un buco pagato (0,221 ms),
   mai un dato sbagliato. Un id promesso "non residente" al ramo CPU legge i
   pesi mappati in RAM, che sono la verita' per definizione.
2. **Fra decisione ed esecuzione non passa nessuno.** Tutti i mutatori dei
   metadati di residenza (decidi, prenota, promozioni, acceptmoe, ricarica
   calda) girano **sullo stream di calcolo** o vi si ordinano; fra
   `partiziona(L)` e `assicura(L)` lo stream contiene solo le D2H
   dell'overlap. Il thread di servizio del prefetch muove BYTE e pubblica
   "atterrato"; e' `kern_prenota`/`kern_decidi` (in-stream) a promuovere
   (`cache-esperti.cu:301-310, 1401-1409`). La bozza ha runtime e slab
   separati. Il fork richiede `W=0` esplicito (`cache-esperti.cu:1004-1011`):
   i due mutatori "esterni" non coesistono.
3. **Il transito e' gia' trattato da non-residente** sia dalla partizione sia
   da AcceptMoE (`cache-esperti.cuh:296-302, 316-318`): mai promesso cio' che
   non e' atterrato.
4. **Il residuo vero** e' DENTRO `kern_decidi`: la rivittimizzazione nello
   stesso lancio (audit 01, mai osservata) — preesistente all'overlap e non
   aggravata da lui.

Quindi: nessun reperto di correttezza nuovo. Il costo della promessa
invecchiata pero' **non e' contato da nessun contatore**: i buchi del ramo GPU
non distinguono "non c'era" da "c'era alla partizione e non c'e' piu'".
*Falsificazione/strumento*: il conteggio per strato dei non-residenti alla
partizione esiste gia' progettato e MAI applicato (patch `k_adattivo`, livello
1 = sonda, `fab[strato]`): confrontare `fab` con i buchi di `decidi` sullo
stesso intervallo darebbe il numero delle promesse rotte. A oggi [IPOTESI]:
~0, perche' fra le due letture non si accoda nessun mutatore.

Un effetto di ritorno da mettere a verbale [CONTATO→IPOTESI]: la fase 1 della
partizione manda alla CPU i residenti con `usato==0` (prossimi allo sfratto).
Un esperto servito dalla CPU non fa domanda → il suo `ultimo` non avanza → lo
sfratto arriva prima: **il ramo CPU affama l'orologio LRU esattamente degli
slot che prende in prestito.** Direzione dell'effetto ignota (libera slot per
buchi veri / butta riuso futuro). Si vede gratis: `sfratti` e
`vittime_domanda` del dump a K=0 contro K=2, stesso seme, stesso TOPK.

---

## 6. I cantieri di ieri: l'overlap li conosce? (domanda 5)

### 6.1 AcceptMoE: collegata per costruzione, avversaria per economia

Il collegamento c'e' ed e' elegante: le op AM riscrivono `selected_experts` e
`weights` A MONTE, e "tutto il valle — overlap compreso — consuma id e pesi
riscritti senza una riga di modifica" (`llama-graph.cpp:2253-2257`). Anche la
validazione di residenza e' condivisa (`cache-esperti.cuh:316-318`). Fin qui
il disegno regge.

**Il conflitto e' semantico** [CONTATO→DEDOTTO]: AM trasforma i non-residenti
delle righe speculative in duplicati del miglior residente (peso 0). Su quelle
righe la fase 0 della partizione si svuota → il taglio CPU (k fisso!) pesca
dalla fase 1: **esperti residenti**, che la GPU avrebbe serviti a 0,063 ms,
calcolati a 0,242 sulla CPU; e quando nel taglio finisce un duplicato a peso
zero, il ramo CPU calcola una colonna che la pesatura annulla. Il costo del
ramo CPU e' fisso per costruzione (k colonne), il suo beneficio (deviare
trasporti) su quelle righe e' zero. Le due leve comprano la STESSA merce — i
non-residenti — e nessuno ha mai misurato il prezzo congiunto: ne' 35 ne' 36
nominano l'overlap; 36 ha appena scoperto che AM era accesa quando la si
credeva spenta, quindi **i numeri della spazzata K potrebbero gia' contenere
AM** — da verificare nel log dei bracci K prima di fidarsi dell'ottimo 2.

*Falsificazione*: (a) rileggere `c5_*`/bracci K: `acceptmoe[bersaglio]
lanci>0`? Se si', l'ottimo K=2 e' gia' "con AM" e il confronto pulito manca
dall'altra parte; (b) braccio K={1; 1,5; 2} × AM={off, soglia produzione},
n≥3: attesa [IPOTESI] — con AM accesa l'ottimo scende sotto 2 e
`righe mascherate` sale mentre `worker calcolo/grafo` resta piatto (la firma
del lavoro CPU a beneficio zero).

### 6.2 VRAM a fasi: sicura per costruzione, con una finestra dichiarata

La transizione fa `synchronize()` PRIMA di toccare un byte
(`llama-context.cpp:861-865`), e `ggml_backend_sched_synchronize` **unisce il
worker** (`ggml-backend.cpp:2362-2370`); `sched_reserve()` ricostruisce lo
scheduler → uid nuovi a ogni split (1710) → il confronto proprieta' dei CUDA
graph gira davvero e la ricattura e' forzata (gia' argomentato in audit 40
§2 — qui CONFERMATO sul lato worker/eventi, che audit 40 non guardava: anche
`sched_reset` unisce, 2272-2280, e il percorso d'errore non lascia lavori in
volo, lambda `esci` 1838-1846). Nessun reperto.

La finestra da conoscere: al ripiego (slot non entrano → cache base o spenta,
`cache-esperti.cu:717-731`), la partizione degrada a IDENTITA' per contratto
di null-safety — **K continua a mandare colonne alla CPU senza piu' alcun
segnale di residenza**. Legale e voluto; ma un braccio fasi che finisse li'
misurerebbe un overlap cieco credendolo normale. Testimone gia' esistente:
la riga `vram-a-fasi: ... ripiego` nel log + `colpi=0` nel dump con
`worker lavori>0` nel profilo. Da mettere nella checklist dei bracci fasi.

### 6.3 Rollback parziale: nessun accoppiamento, ed e' giusto cosi'

Il rollback lavora fra un decode e l'altro, host-side, dietro le stesse
sincronizzazioni; l'invariante del worker ("mai tornare con un lavoro in
volo") copre anche i suoi percorsi. 33/37 non nominano l'overlap perche' non
ce n'era bisogno — l'unico "overlap" citato da 33 (r.251) e' la finestra di
commit dei compressori, altro oggetto. Confermo: nessuna azione.

### 6.4 Prefetch e fork: mutua esclusione gia' imposta

`FORK` pretende `W=0` esplicito (`cache-esperti.cu:1004-1011`); il prefetch
promuove in-stream. L'overlap non ha bisogno di saperne di piu': tutto cio'
che muta la residenza passa dallo stream che lui gia' rispetta (§5.2).

---

## 7. Il prefill fuori per guardia: e' voluto? (la domanda del mandato)

**No: e' un effetto collaterale, e la sua motivazione scritta nel punto in cui
agisce e' vuota.** La guardia `n_tokens > batch_max` (`llama-graph.cpp:
1847-1856`) nasce il 7/8 contro il replay a taglie alternate 1/2 nella catena
speculativa; il prefill (bs=64) resta fuori come conseguenza aritmetica del
difetto 1, non per una decisione sul prefill. E a bs=64 il rischio-replay non
esiste proprio: `ggml_cuda_graph_check_compability` spegne i CUDA graph quando
`MUL_MAT_ID` ha `ne[2] > mmvq_mmid_max` (=8 per i nostri formati,
`ggml-cuda.cu:3125-3137`) — a bs=64 non c'e' cattura, quindi non c'e' replay
da temere. La guardia protegge il regime 1-2 token; il prefill lo esclude per
coincidenza di soglia.

Detto questo, **riaccendere la lane in prefill non e' "alzare BATCH_MAX"**.
Tre muri indipendenti, tutti [CONTATO]:

1. `kern_partiziona` abortisce oltre `TOK_MAX=32` (`cache-esperti.cu:
   2107-2111`) — e il commento del lanciatore che dice "non puo' accadere
   perche' l'ammissione cappa a 64 elementi" descrive un cancello che in
   `build_moe_ffn_overlap` NON esiste (gia' audit 14; il commento a 2102-2106
   e' ancora li', ancora falso);
2. la lista di copia della cache tiene 64 lavori (`c.lista`,
   `cache-esperti.cuh:154`) e il dispatch ammette `ne0*ne1 <= 64`
   (`ggml-cuda.cu:2208`): a bs=64 sono 384 id;
3. il servizio dalla cache vive solo in MMVQ (`dst->ne[2] <= 8`, 2211): a
   bs=64 il ramo GPU andrebbe su MMQ, che non ha vista ombra (gia' RACCOLTA
   Lavoro 2 §1).

Quindi il prefill-overlap sarebbe un'ALTRA macchina: partizione a griglia
per-token, lane CPU in GEMM (non GEMV), niente cache di mezzo — con un conto
economico da fare prima (a bs=64 la CPU farebbe k/6 dei FLOP MoE in un regime
compute-bound dove il rapporto per-esperto CPU/GPU non e' piu' 4:1 ma molto
peggio; in cambio toglierebbe k/6 dei ~822 MiB/token di copie H2D del percorso
prefill). Con C = 5,8-7,3 ms/token gia' padrone dell'87% del prefill (audit
40-41), questo cantiere non e' il prossimo. **La risposta alla domanda "e'
voluto?" e': non fu deciso; oggi ci sono tre ragioni tecniche perche' resti
cosi', e vanno scritte al posto della motivazione vuota** — un commento di 4
righe alla guardia, riferito a questo audit.

---

## 8. Dove il mandato sbagliava la domanda (permesso accordato)

1. **"Il tetto e' la DIPENDENZA"**: la dipendenza e' reale ma il suo prezzo
   fisico e' µs; i ~45 ms sono il prezzo dell'IMPLEMENTAZIONE del join (drain
   + copia sincrona + host nel mezzo, §3). La differenza non e' lessicale: la
   prima non si rompe, la seconda si rompe con una patch piccola e si misura
   con contatori gia' stampati.
2. **"L'overlap non parallelizza"**: parallelizza — worker ed evento
   funzionano, il ramo CPU gira davvero sotto 1b — ma il canale parallelo e'
   CAPPATO dal pavimento del rendezvous, e il canale che paga e' la rimozione
   strutturale delle domande (§1). Le due letture convivono; la formulazione
   del mandato butta via la meta' aggiustabile.
3. **"GRIGLIA_VARIABILE serve ancora?"** presuppone che sia servita: non ha
   mai sparato il suo colpo. La domanda giusta e' "spararlo o smontarla" (§4.1).
4. Una premessa implicita in tutta la campagna K: **che l'ottimo di K sia una
   proprieta' della macchina.** E' una proprieta' del TASSO DI COLPI (§2.1):
   ogni leva che muove i colpi (AM, capienza, semina, fasi) invalida la
   spazzata K precedente. Va scritto nel protocollo dei bracci, o continueremo
   a "riscoprire" ottimi che erano solo colpi diversi.

## 9. Gli esperimenti, in ordine di valore (tutti in contatori)

| # | braccio | costo | contatore che decide | attesa scritta prima |
|---|---|---|---|---|
| 1 | `GGML_SCHED_PROFILO=1`, K=2, config produzione | 1 corsa | `us_sync/grafo`, `join`, `attesa-evento`, `n lavori/grafo` | sync domina gli ingressi; lavori=43; join≈0 a K=2 |
| 2 | rilettura log bracci K: `acceptmoe[bersaglio] lanci` | 0 corse | `lanci`, `righe mascherate` | se >0, l'ottimo K=2 e' "con AM" e va dichiarato tale |
| 3 | fix lettore pin (2 righe) + `K=0,5` | 1 patch + 1 corsa | `worker n lavori/grafo` | 43 → 21-22; se `us_sync+join` non scala, pavimento WDDM |
| 4 | patch copia-di-ritorno async (§3.4.1) | patch piccola | `us_sync/grafo` crolla; SHA invariato | attesa GPU −(drain+H2D)·strati |
| 5 | `SPIN` = 0 / 20k / 2M | 3 corse | `attesa-lavoro`, `join` | se piatto, 2M e' un core bruciato |
| 6 | `ASYNC=0` contro `1` a K=2 fisso | 2×3 corse | `us_sync`, `join`, t/s | l'A/B mai fatto della Fase 2 nel regime attuale |
| 7 | `GRIGLIA_VARIABILE=1` + BATCH_MAX=2 (catena spec) | 1 corsa | `div[4]` > 0 + degenerazione | doppia conferma, poi si smonta la leva |
| 8 | K × AM (§6.1b) | 6×3 corse | ottimo K, `mascherate`, `worker calcolo` | ottimo scende sotto 2 con AM accesa |

Regola di lettura per tutti: i contatori `buchi/domande` del battito sono
istantanee (±4% fra corse identiche — nota di metodo di casa): si legge il
dump cumulativo alla chiusura, mai il battito; verdetti solo con n≥3.

## 10. In tre righe

La macchina e' sana nel disegno e sorvegliata nei punti giusti (rilevatore,
null-safety, worker con invarianti): i reperti nuovi non sono di correttezza
ma di ECONOMIA — un join che paga quattro pedaggi per strato dove ne basta
uno, tre leve mai misurate su sette, un alleato (AcceptMoE) che le svuota il
mestiere di mano senza che nessun braccio l'abbia mai guardati insieme, e un
difetto "medio" di due giorni fa (l'atoi del pin) che nel frattempo e'
diventato il tappo dell'esperimento piu' importante. Il primo passo non
richiede nemmeno di compilare: e' una corsa col profilo acceso e la tabella
del §9.
