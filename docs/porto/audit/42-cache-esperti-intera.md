# 42 — CACHE-ESPERTI, IL FILE INTERO: il default che i log non usano, e tredici reperti vecchi ancora aperti

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `24fd5c2ee`,
working tree pulito sui due file. **Niente compilato, niente eseguito, nessun
server toccato**: lettura integrale, `git`, grep, e i log gia' in cassa in
`D:\ds4_work\llama_run\`. Marcatura: [LETTO] = codice riga per riga,
[MISURATO log] = log esistenti, [DEDOTTO] = aritmetica, [IPOTESI] = da
falsificare con la misura indicata in fondo (§7).

## La premessa del mandato va corretta due volte

1. **Il file non e' di 1.964 righe: e' di 2.547** (piu' 569 di `.cuh`). E'
   cresciuto di ~800 righe **oggi**: AcceptMoE rifusa (`c871bfa6b`), VRAM a
   fasi rev.2 (`babd15238` + `03a768c9c`, con ricarica calda e zavorra). Il
   numero del mandato fotografa l'albero di ieri.
2. **"Mai letto per intero" e' falso sei volte.** Gli audit 01, 02, 03, 05,
   06 e 07 dichiarano ciascuno la lettura integrale (alla taglia di allora,
   1.716 righe) e hanno prodotto ~15 reperti. Il problema non e' il codice mai
   letto: e' che **13 di quei reperti sono ancora aperti a HEAD** (registro in
   §6), incluso quello — l'etichetta del dump — che stanotte e' costato un
   mandato. Il valore di questo giro sta in tre cose: il delta di oggi
   (~800 righe mai auditate), le interazioni fra gli strati che nessun audit
   per-sottosistema poteva vedere, e il registro consolidato di cio' che resta
   aperto.

---

## §1 — LEVE E DEFAULT (in ordine di gravita')

### 1.1 `LLAMA_CACHE_ESPERTI_LRU` — il default e' il ramo perdente, e i log lo provano [MISURATO log]

- **Righe**: `cache-esperti.cu:853-855` (default 0 = orologio);
  `cache-esperti.cu:829` (la BOZZA hardcoda `lru=1`, senza leva);
  `cache-esperti.cuh:119-125` (il commento che promette la misura del debito).
- **Cosa succede**: a leva assente il bersaglio sfratta con l'orologio. Ma:
  (a) la misura del 9/8 dice che **l'orologio perde contro la LRU a ogni
  capienza** (45,2% contro 33,5% di colpi a 380 slot — a verbale in memoria,
  "non esiste nucleo caldo"); (b) **i bracci di produzione girano gia' con
  `lru=1` esplicito**: `bk01_339_32.server.log:237` (la configurazione SOTA
  339+32) e `bk0_380_0.server.log:237` lo stampano nella riga di init; (c) il
  file stesso, per la cache che controlla al 100% (la bozza), sceglie
  `lru=1` fisso. Il default riproduce quindi un ramo che ne' le misure ne' la
  produzione usano: e' il valore che c'era quando la leva e' nata (5/8,
  "orologio, non LRU" era la TESI di progetto), sopravvissuto alla sua
  falsificazione. Stessa classe del `W=2` di `deepseek4.cpp:1378` (audit 07,
  **ancora `2` a HEAD**, verificato oggi): il default non e' la configurazione
  vincente, e ogni braccio nuovo che dimentica una env misura il ramo
  sbagliato.
- **Caveat onesto**: colpi ≠ tempo (regola di casa: la VRAM libera batte il
  tasso di colpi). Non ho trovato nel ledger un A/B **t/s** orologio/LRU a
  parita' di tutto; finche' non c'e', "LRU e' il default giusto" resta
  [IPOTESI] — vedi §1.2 per il motivo meccanico per cui potrebbe non esserlo.
- **Falsificazione**: gratis sui log (grep `lru=` nella riga di init di ogni
  braccio del ledger: dichiara quale ramo ha girato ogni corsa storica);
  decisiva con M1 (§7).

### 1.2 Il ramo LRU viola la regola 1 del contratto: O(n_slot) per sfratto sul flusso di calcolo [LETTO][DEDOTTO]

- **Righe**: `cache-esperti.cu:1191-1236` (LRU: scansione completa per il
  minimo di `ultimo[]`, per OGNI sfratto); idem MASSA (1152-1175) e CURA
  (1245-1264); l'orologio (1307-1319) e' l'unico O(1) ammortizzato. Contratto
  violato: `cache-esperti.cuh:67-71`, regola 1 ("nessun lavoro proporzionale
  alla DIMENSIONE della cache, solo al delta") e regola 4 (budget 5 ms/token).
- **Cosa succede**: con `lru=1` — cioe' in produzione, vedi 1.1 — ogni buco
  paga una scansione sequenziale di `n_slot` letture in un kernel `<<<1,1>>>`
  sullo stream di calcolo. A 339 slot e ~116 buchi/posizione: ~39.000
  iterazioni/token. Stima 0,2-0,8 ms/token a 339 slot; ~×4 a 1400 slot
  (`bb_B2_cpu_1400` girava infatti con `lru=0`). **Il costo cresce con la
  capienza**: e' un candidato meccanico per il verdetto "la capienza migliora
  i colpi senza convertirsi in tempo" — piu' slot = piu' colpi MA piu' costo
  per ciascuno dei buchi rimasti. E' esattamente la contabilita' invariante
  che il file promette di non avere (DwarfStar).
- **Falsificazione**: non decidibile senza eseguire → M2 (§7). La lettura
  decide solo che il costo esiste ed e' proporzionale a `n_slot`.

### 1.3 `LLAMA_CACHE_ESPERTI_PF_TUTTI` acceso di default + tetto muto a 16 in `_prenota` [LETTO]

- **Righe**: `ggml-cuda.cu:4648-4651` (default ACCESO: `!(v && *v=='0')`);
  `ggml-cuda.cu:4656` (il chiamante ammette `n_id <= 64`);
  `cache-esperti.cu:1841` (`if (n_id > ANELLO_VOCI_MAX) n_id = 16` — clamp
  silenzioso); `cache-esperti.cuh:507-516` (il contratto di `_prenota` non
  dichiara nessun tetto).
- **Cosa succede**: con W>0 (che a HEAD e' il DEFAULT, `W=2`) e batch ≥3
  token, il predittore chiede 6×3=18+ id e la prenotazione ne tronca la coda
  a 16, senza contatore e senza log: il chiamante ammette fino a 64, il
  kernel ne vede 16. Due cancelli che non concordano, e il pezzo perso e'
  proprio la coda del batch — le posizioni che il fix "PF_TUTTI" (nato per
  guardare TUTTE le posizioni) doveva coprire. Oggi morde poco (batch
  speculativo = 2 → 12 id); mordera' silenziosamente appena il batch cresce.
- **Falsificazione**: statica, gia' decisa dalle righe citate. Il fix e' o il
  contatore (`scartati += n_id - 16`) o la spezzatura in piu' batch (come fa
  la patch semina di RACCOLTA).

### 1.4 `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=32` contro il suo stesso commento (~10 bastano) [LETTO]

- **Righe**: `cache-esperti.cu:1017-1019` (default 32);
  `cache-esperti.cu:1885-1888` ("per saturare il PCIe bastano ~25-50 KiB in
  volo (~10 blocchi), il resto degli SM resta alla MMVQ").
- **Cosa succede**: il default e' il triplo di quel che il commento dichiara
  sufficiente, e ogni blocco in piu' e' contesa SM con la MMVQ concorrente —
  che e' l'intero scopo del fork. FORKJOIN.md:189 lo dichiara gia': "contesa
  SM del gather concorrente non misurata: il default 32". Non lo ri-scopro:
  lo segnalo perche' e' un getenv di QUESTO file col default mai difeso da
  una misura (la spazzata 16/64/112 prescritta in FORKJOIN.md §5 non risulta
  girata). Leva spenta di default (`FORK=0`), quindi morde solo il braccio
  fork.
- **Falsificazione**: M3 (§7).

### 1.5 Il resto dei getenv del file — tabella completa [LETTO]

| Leva (riga .cu) | Default | Verdetto |
|---|---|---|
| `LLAMA_CACHE_ESPERTI_SLOT` / `_BOZZA_SLOT` (199) | 0 = spenta | giusto (opt-in) |
| `LLAMA_CACHE_ESPERTI_BATCH` (222-227) | 8 | coerente con la misura del 6/8 (crollo a cancello tolto); nota: 0 → 1, il tetto non e' disattivabile via env; il lettore gemello in `deepseek4.cpp:1383-1386` NON normalizza (audit 07, aperto) |
| `LLAMA_CACHE_ESPERTI_BATTITO` (234-236) | 60 s | difendibile in produzione; trappola nota sui bracci corti (gia' in commento 781-785) |
| `LLAMA_CACHE_ESPERTI_CURA/SPIN/FILTRO/CODA_MAX/MASSA/SCUDO` (834-863) | 0/256/0/0/0/0 | spenti = giusto; ma vivono solo con W>0, e le esclusioni per ordine dei rami sono a verbale (audit 01/07, aperte) |
| `LLAMA_VRAM_A_FASI_*`, `LLAMA_VRAM_ZAVORRA` (475, 621-632, 170) | inerti | giusto ("il difetto non scommette") |
| `LLAMA_OVERLAP_GRIGLIA_VARIABILE` (2120-2123) | 0 = griglia fissa | giusto: il default e' il ramo replay-safe |
| `LLAMA_CACHE_ORACOLO` (2344) | spento | il default e' giusto; e' la leva ACCESA che mente (§2.1) |

---

## §2 — CODICE MORTO E CAMMINI IRRAGGIUNGIBILI

### 2.1 L'oracolo: ancora scollegato a HEAD, e adesso anche il commento del chiamante mente [LETTO, conferma di audit 07]

- **Righe**: `cache-esperti.cu:2339-2423` (carica, avanza, `oracolo_ids`);
  `ggml-cuda.cu:4660-4671`; `llama-context.cpp:2007-2021`.
- **Stato verificato oggi**: `ggml_cuda_cache_esperti_oracolo_ids` ha **zero
  chiamanti** nell'intero repo (grep odierno); `kern_prenota` non contiene un
  solo riferimento all'oracolo; il secondo disegno ("orologio unico sul
  device") e' stato ABBANDONATO (`44d28db77`) ma il commento in
  `ggml-cuda.cu:4660-4668` dice ancora "ci pensa il kernel a ignorarlo se
  l'oracolo e' acceso" — descrive un kernel che non esiste. Con
  `LLAMA_CACHE_ORACOLO` settato: file letto, "oracolo: ACCESO" stampato,
  1 KiB/token copiato sul device, **niente consumato**. Un braccio "oracolo"
  misura il predittore ordinario piu' il costo delle copie.
- **In piu' rispetto ad audit 07**: anche il dump mente — la riga
  "pianificazione consumata fino al token %d" (`cache-esperti.cu:2427-2429`)
  dichiara un consumo che non avviene. Se il braccio del tetto (la domanda da
  fattore due del `.cuh`) girasse domani su questo binario, il numero sarebbe
  spazzatura con un log che giura il contrario.
- **Esclusione**: la condizione che lo esclude non e' una config: e' l'assenza
  del call site. O si ricollega (terzo disegno) o si strappa via, insieme al
  blocco `.cuh:518-563`.

### 2.2 Rami vivi solo sulla carta [LETTO]

- **`mano` sotto LRU** (`cache-esperti.cu:1192, 1227`): il ramo LRU legge la
  mano solo come punto di partenza di una scansione comunque completa e la
  riscrive; il second-chance `usato[]` viene alzato dai colpi ma **mai
  consumato per lo sfratto**. In modalita' LRU (= produzione) l'orologio e'
  un fossile che gira a vuoto — e la partizione continua a leggerlo come
  segnale di prossimita' allo sfratto (audit 05, aperto).
- **`cache_promuovi` nella BOZZA** (`cache-esperti.cu:1481` chiamata
  incondizionata; 953-962: la bozza NON alloca l'anello → `anello_dev =
  nullptr`): oggi e' salvo per costruzione — `atterrato[]` azzerato (985) e
  mai scritto per la bozza, quindi il loop esce al primo giro senza toccare
  `an`. Ma il deref di `an[...]` sta a UNA scrittura spuria di distanza dal
  nullptr. Guardia da due righe (`if (!c.anello_dev) return;`).
- **Prefetch W>0 + LRU: l'anticipo si sfratta da solo** [DEDOTTO]. La
  prenotazione azzera `ultimo[vittima]` (1663, 1746) e la promozione non lo
  timbra (1429-1434): lo slot promosso ha epoca 0 → e' il MINIMO globale →
  la LRU lo sfratta al primo buco successivo, prima che la sua domanda (1-2
  strati dopo) arrivi. E' lo stesso meccanismo che RACCOLTA ha dimostrato per
  la semina ("si mangerebbe da sola", conta=0): vale identico per il W-path.
  Con W=2 di default e `lru=1` in produzione, questa coppia gira OGGI.
  Concorre a spiegare perche' W>0 perde (oltre alle tre ragioni del `.cuh`).
- Il resto dell'inventario dei rami condizionati (CURA/SCUDO/FILTRO/CODA_MAX
  raggiungibili solo con W>0; MASSA che scavalca tutto; SPIN letto e stampato
  ma inerte senza CURA=2) e' gia' nella tabella di audit 07: confermo che a
  HEAD nulla e' cambiato.

---

## §3 — CONTATORI CHE MENTONO

### 3.1 `guasti` a domanda = output numericamente sbagliato, etichettato "prefetch" e senza urlo [LETTO]

- **Righe**: `cache-esperti.cu:1554-1560` (kern_decidi: vittima non trovata →
  `slot_out[i] = 0`, cioe' si servono I BYTE DELLO SLOT 0 per un esperto che
  non c'entra — corruzione numerica dell'uscita, dichiarata "mai attesa");
  `cache-esperti.cu:2492-2494` (il dump stampa `guasti` DENTRO la riga
  "prefetch prenotati/saltati/scartati/guasti").
- **Cosa succede**: un guasto a DOMANDA e' l'evento piu' grave che questo
  file possa produrre (matmul con pesi sbagliati, SHA rotto); il dump lo
  archivia come statistica di prefetch, in una riga che con W=0 il lettore
  salta. La riga del rilevatore replay urla ("GRAFO STANTIO: uscita NON
  valida", 2483-2490); `guasti>0` — che significa la stessa cosa — no.
- **Falsificazione**: statica (righe citate). Fix: etichetta separata
  `guasti-domanda` + lo stesso marcatore "uscita NON valida" quando >0.

### 3.2 La VRAM a fasi azzera i testimoni del rilevatore replay a ogni cambio fase [LETTO — delta di oggi]

- **Righe**: `cache-esperti.cu:1087-1088` (`free` libera `pub`/`div`);
  `cache-esperti.cu:710` (`fasi` chiama `free` a ogni ridimensionamento);
  `cache-esperti.cu:2265-2278` (`pubblica_inizio` rialloca e AZZERA `div`);
  `cache-esperti.cu:114, 2299` (`pubblicazioni`, contatore HOST, sopravvive).
- **Cosa succede**: dopo il primo confine prefill/decode, `div[0..4]`
  (divergenze + "lanci visti dal device") ripartono da zero mentre
  `pubblicazioni` continua a salire. Il dump confronta proprio quei due
  ("attivo=1, pubblicazioni=N, lanci visti=M"): dopo un cambio fase il
  lettore vede N≫M e diagnostica replay saltati che non esistono — o,
  peggio, una divergenza contata prima del cambio SPARISCE dal totale. In
  piu', fra la `free` e la successiva `pubblica_inizio` il rilevatore e'
  spento in silenzio. Stessa sorte per i contatori acceptmoe (`am_cont`,
  liberati e riallocati): il dump pre-free (702) salva i numeri sul log, ma
  ogni cancello automatico che legge "l'ultimo dump" somma fasi diverse
  credendole una serie sola.
- **Falsificazione**: statica; a macchina libera, una corsa `LLAMA_VRAM_A_FASI=2`
  con `battito` corto deve mostrare `lanci visti` che ricomincia da ~0 dopo il
  log "vram-a-fasi: fase=decode".

### 3.3 Conferme sui reperti gia' a verbale (il minimo indispensabile)

- **Il prefisso unico del dump (audit 06, il difetto che stanotte e' costato
  il mandato) e' ancora aperto a HEAD**: intestazione con `cache_nome`
  (2432), TUTTE le righe dati ancora `"cache-esperti:"` fisso (2440-2517).
  L'unica riga etichettata `[bersaglio]/[bozza]` e' acceptmoe (2531-2534),
  aggiunta dopo audit 36. Fix da un'ora: `cache_nome(runtime)` in testa a
  ogni fprintf.
- **Il dump non e' ordinato dopo lo stream di calcolo** (audit 06, aperto:
  2434 e' una `cudaMemcpy` sul default stream, gli stream ggml sono
  non-blocking): e' la spiegazione meccanica del ±4% fra run identiche gia'
  in memoria ("i contatori sono istantanee a battito"). Vale anche per
  `salva_mappa` (491) e per il censimento `installato` (2460-2467), che si
  fidano della quiete imposta dal chiamante.
- **Con ACCEPTMOE accesa la percentuale di colpi non e' confrontabile**
  (audit 35:290-291, gia' a verbale: i duplicati residenti la gonfiano;
  leggere i buchi assoluti).
- `ultimo_strato_contato` non viene azzerato da `free`/`fasi` (91, 1096):
  innocuo oggi (il primo strato dopo un confine e' sempre diverso
  dall'ultimo contato), ma e' stato host che sopravvive a una cache che non
  esiste piu' — da azzerare in `free` per igiene, una riga.

---

## §4 — CORRETTEZZA (race, indici, sincronizzazioni)

### 4.1 `esperto` non e' mai validato, e l'impacchettamento `(vittima<<16)|esperto` trasforma un id folle in una scrittura fuori dallo slab [LETTO]

- **Righe**: `cache-esperti.cu:1491` (kern_decidi legge l'id e lo usa
  mascherato a 8 bit per le tabelle: nessun OOB li'); **1571**
  (`c.lista[1+n_copie] = (vittima << 16) | esperto` — un id NEGATIVO
  imposta i bit alti della voce); **1785-1787** (kern_copia disfa:
  `slot = voce >> 16` → con id negativo lo slot diventa NEGATIVO →
  `dst = slab + slot*byte_slot` scrive ~7 MiB PRIMA dello slab, in VRAM
  altrui, in silenzio); id > 65535: `voce & 0xffff` tronca e si copia
  l'esperto sbagliato. Stesso buco in kern_prenota (1639, 1689: l'id passa
  nell'anello e il servizio fa `cudaMemcpyAsync` da
  `base + esperto*passo` — lettura host fuori dal tensore mappato).
- **Da dove puo' arrivare un id folle**: non dal router in regime sano
  (argsort su 256). Ma il file stesso documenta la famiglia di guasto che li
  produce: il replay stantio a griglia corta lascia `out` della partizione
  NON inizializzato per i token oltre la griglia catturata (2049-2056), e
  quegli int finiscono a valle come id. Il rilevatore CONTA la divergenza ma
  non blocca il lancio: oggi fra "divergenza contata" e "scrittura OOB muta"
  non c'e' nessuna guardia.
- **Peso**: media probabilita' per costruzione (serve un guasto a monte), ma
  la conseguenza e' la classe peggiore (corruzione muta di VRAM adiacente).
  Sei confronti per chiamata (`esperto < 0 || >= c.n_esperti` → `guasti++`,
  salta l'id) trasformano il muto in urlante, costo zero misurabile.
- **Falsificazione**: statica (righe citate). Runtime: fault injection su
  `ids`, fuori mandato oggi.

### 4.2 `block_reduce`: in QUESTO file non esiste — risposta secca al punto 4 del mandato [LETTO]

Nessuna riduzione in shared memory, nessun `__syncthreads`, nessun
`__shfl_*` in tutto il file: i kernel sono a un thread (decidi, prenota,
maschera), embarrassingly parallel senza comunicazione (copia, ricarica), o
per-token senza dati condivisi (partiziona, acceptmoe). La race di
`block_reduce` trovata stanotte (#26385) vive in `common.cuh`/soft_max, non
qui. Le quattro tabelle (`dove/chi/usato/ultimo`) sono mutate SOLO da kernel
a un thread sullo stream di calcolo — la regola del disegno tiene, con tre
eccezioni gia' a verbale e una nuova:

- **aperte da audit 03**: il flag `atterrato` come sincronizzazione
  inter-stream via volatile (formalmente non garantita dal modello CUDA), e
  gli errori di `cudaMemcpyAsync` del servizio pubblicati come copia
  riuscita (339-353: valori di ritorno ignorati anche a HEAD);
- **aperte da audit 01/05**: la rivittimizzazione di uno slot gia' promesso
  in `slot_out` dentro lo stesso `kern_decidi` (clock, 1307-1319 invariato —
  nota: con `lru=1` di produzione il caso e' praticamente neutralizzato,
  perche' i tocchi freschi hanno epoca massima; resta aperto sul default), e
  l'orfano da promozione tardiva col clock (1429 invariato);
- **nuova, formale**: il thread di servizio legge `runtime->reg[]` via
  `_basi()` (331-333) mentre il thread di build puo' ancora registrare
  strati (`registra`, 268-276) — nessuna atomica, ordinamento affidato al
  TSO di x86 (store order del compilatore NON garantito). Benigna oggi,
  UB formale; morde solo con W>0. Un `atomic<int>` su `visti` chiude.

### 4.3 Il fallimento dell'anello perde 2,3 GiB di VRAM, e la VRAM a fasi decuplica le occasioni [LETTO, aggrava audit 01]

- **Righe**: `cache-esperti.cu:954-960` (anello: `cudaHostAlloc` fallita →
  `attiva=false; return false` SENZA liberare slab e tabelle gia' allocate);
  1060 (`free` ritorna subito se `!attiva` → quei byte sono irrecuperabili);
  893-916, 949 (le ~12 cudaMalloc delle tabelle: valori di ritorno ignorati,
  `attiva=true` comunque a 1045).
- **Perche' oggi pesa piu' di ieri**: (a) l'anello e' memoria HOST BLOCCATA,
  e questa macchina vive a ridosso del tetto di pin misurato (74,7 GiB
  passano, 76,9 no): il fallimento di una cudaHostAlloc non e' il caso
  esotico che era quando audit 01 lo giudico' "probabilita' bassa" — e'
  il PRIMO alloc che cede in quel regime, e il fallimento costa lo slab
  intero (2,3 GiB spariti in VRAM con la cache SPENTA, nel regime dove "la
  VRAM libera batte il tasso di colpi"); (b) la VRAM a fasi rifa'
  `free`+`init` a OGNI confine prefill/decode (710-728), quindi la finestra
  non si attraversa piu' una volta per processo ma due per richiesta.
- **Falsificazione**: statica per il percorso (righe citate); il sintomo a
  runtime sarebbe il log "allocazione anello prefetch fallita, cache spenta"
  seguito da VRAM libera piu' bassa di ~2,3 GiB rispetto al riferimento.
  Fix: percorso d'errore che libera cio' che ha allocato (goto-cleanup), e
  controllo sulle tabelle prima di `attiva=true`.

### 4.4 Controlli mirati senza rilievo (fatti, e tenuti) [LETTO]

- **ACCEPTMOE ids/pesi sotto W>0**: il contratto "fra i due lanci nessun
  kernel muta dove/chi" (`cuh:321-327`) TIENE anche col prefetch acceso —
  le due op sono create adiacenti (`llama-graph.cpp:2247-2252`), i nodi
  `cache_pf` nascono a fine strato (`deepseek4.cpp:1388+`) quindi il
  `kern_prenota` di L+1 esegue PRIMA della coppia di L+1, e i transiti che
  installa sono letti "non residente" da entrambe le op (confronto di chiave
  esatto, 2180). Coerenza per costruzione, verificata.
- **Fork/join**: l'istantanea della lista (kern_fj_maschera → fj_lista)
  chiude davvero la corsa col kern_decidi dell'up; gli eventi riusati sono
  sani (il wait fotografa lo stato alla chiamata); il double-count dei
  contatori in fase 1 non c'e' (`conta` risulta 0 per costruzione, 1968 e
  2276). La guardia GGML_ABORT su terna spezzata copre il walker.
- **`atterrato` scritto a 1 byte su int32** (350-353): corretto per
  costruzione (byte alti sempre 0), ma e' un contratto implicito fragile —
  un memset a 4 byte costerebbe uguale.
- **Wraparound dell'anello a 2^31 batch**: irraggiungibile in una corsa.
- **`blocchi_copia()` interroga il device 0 fisso** (1805-1812): latente,
  il fork e' single-device per decisione (memoria); da sistemare solo se
  mai arrivasse una seconda GPU.
- **kern_ricarica/verifica** (delta di oggi): mask dello strato coerente
  (0x3f = 64 strati), ordine memcpy→tabelle→verifica corretto sullo stream
  0 con sync finale, cancello dove/chi che URLA (582-584). Ben fatto.

---

## §5 — INCOERENZE `.cuh` ↔ `.cu`

1. **`cuh:285-288`** ("LLAMA_CACHE_ESPERTI_BATCH, difetto 8") contro
   **`.cu:213-215`**: la BOZZA ritorna 32 fisso (`TOK_MAX`) e ignora la env.
   In pratica il tetto vero della bozza e' il cancello a 64 elementi
   (≤10 token a ne0=6), quindi non morde — ma il contratto non dichiara
   l'eccezione, e la bozza non e' bisezionabile via env come promesso.
   (Adiacente ad audit 02, "un token ma otto o trentadue".)
2. **`cuh:119-125`** ("qui ci si aspetta qualche punto in meno di colpi: e'
   un debito dichiarato, da misurare"): misurato il 9/8, l'orologio ha
   PERSO, il commento e il default sono rimasti alla tesi — vedi §1.1.
3. **`cuh:518-563`** (oracolo): descrive una leva che non decide niente
   (§2.1); il commento gemello in `ggml-cuda.cu:4660` descrive un kernel mai
   scritto.
4. **`cuh:507-516`** (`_prenota`): non dichiara il clamp a 16 (§1.3).
5. **`cuh:294-297`** (partizione, "dentro ogni fase per ordine di slot"):
   il kernel ordina per POSIZIONE originale dentro la fase (2078-2084). La
   frase di null-safety subito sotto equipara "ordine di slot" a "ordine
   originale", quindi e' ambiguita' di lessico, non un difetto — ma con
   K>0 chi legge il contratto per scrivere il consumatore CPU deve sapere
   che "slot" li' significa "colonna della riga", non slot di cache.
6. **`cuh:196-197`** ("contatori giu' una volta a fine corsa") e
   **`cuh:412`** ("una lettura da 32 byte al minuto"): gia' a verbale in
   audit 06 (battito periodico; 256+ byte), ancora cosi'.
7. **Il commento di init `cuh:246-250`** motiva la capienza col prefetch
   ("col prefetch la cache e' dominata da cio' che e' appena stato
   previsto"): e' la narrativa di W>0, falsificata il 5-6/8. Cosmetico ma
   fuorviante per chi dimensiona.

---

## §6 — REGISTRO CONSOLIDATO: i reperti dei sei audit precedenti, verificati a HEAD `24fd5c2ee`

| Audit | Reperto | Stato a HEAD |
|---|---|---|
| 01/05 | rivittimizzazione di slot gia' in `slot_out` nello stesso kern_decidi (clock) | **APERTO** (1307-1319 invariato; mitigato di fatto da `lru=1` in produzione) |
| 01 | taglie/tipi validati su UNA terna, copie con passi per-strato | **APERTO** (376-379; dormiente su DSV4 omogeneo) |
| 01 | leve di sfratto che si scavalcano per ordine dei rami, senza dichiararlo | **APERTO** (1152/1191/1239) |
| 01 (f.p.) | allocazioni ausiliarie non controllate, leak su fallimento anello | **APERTO e AGGRAVATO** (§4.3: pin-ceiling + fasi) |
| 02 | slab dimensionato su una terna, stride eterogenei non rifiutati | **APERTO** (idem 01) |
| 03 | `atterrato` volatile non e' una sincronizzazione CUDA formale | **APERTO** (1418, 1527-1529) |
| 03 | errori DMA del servizio pubblicati come copia riuscita | **APERTO** (339-353) |
| 05 | LRU non consuma `usato[]` ma la partizione lo legge come eta' | **APERTO** (1191-1236 vs 2070) |
| 05 | orfano da promozione tardiva, clock gli da' la seconda chance | **APERTO** (1429-1446) |
| 06 | dump: prefisso `cache-esperti:` per ENTRAMBE le cache | **APERTO** (2440-2517; solo acceptmoe etichettata) — e' il difetto che stanotte e' costato il mandato |
| 06 | dump non ordinato dopo lo stream (istantanee, ±4%) | **APERTO** (2434) |
| 06 | errore di cudaMemcpy pubblicato come zero misurato | **APERTO** (2306, 2434) |
| 06 | byte dichiarati col padding di `byte_slot` | **APERTO** (2516-2518) |
| 06 | totali vittime vs classi: popolazioni diverse sulla stessa riga | **APERTO** (1294-1302 vs 1186/1234) |
| 07 | ORACOLO scollegato | **APERTO** (§2.1) |
| 07 | default `W=2` contro il verdetto W=0 | **APERTO** (`deepseek4.cpp:1378` verificato oggi) |
| 07 | `BATCH`: normalizzazione divergente fra cache e predittore | **APERTO** (227 vs `deepseek4.cpp:1383-1386`) |

Sedici reperti verbalizzati, **sedici ancora aperti**. Nessuno e' stato
chiuso da allora; nel frattempo il file e' cresciuto di 800 righe. Questo e'
il numero che l'audit 42 consegna: il collo non e' la lettura, e' che i
verbali non tornano indietro nel codice.

---

## §7 — LE MISURE (solo quando il banco e' libero, in ordine di costo)

- **M0, gratis, sui log di cassa**: grep della riga di init (`lru=`, `cura=`,
  `coda_max=`) su TUTTO il ledger → per ogni corsa storica, quale ramo di
  sfratto ha davvero girato. Converte in fatti ogni confronto passato
  orologio/LRU.
- **M1 (decide §1.1)**: A/B `LLAMA_CACHE_ESPERTI_LRU=0/1`, 339 slot, banco
  chat, n≥3 per braccio, metro t/s + buchi assoluti. Se LRU vince anche in
  tempo → il default va girato E il commento `.cuh:119-125` riscritto; se
  perde in tempo con piu' colpi → §1.2 e' probabilmente la causa, vedi M2.
- **M2 (decide §1.2)**: una corsa con nsys, durata media di `kern_decidi`
  a `lru=0` contro `lru=1` a parita' di slot; in alternativa un contatore
  temporaneo di iterazioni di scansione. Costo: mezz'ora.
- **M3 (decide §1.4)**: spazzata `FORK_BLOCCHI` 16/32/64/112 sul braccio
  fork (gia' prescritta da FORKJOIN.md §5, mai girata).
- **M4 (chiude §3.2)**: corsa `LLAMA_VRAM_A_FASI=2` + battito 5 s: verificare
  che "lanci visti dal device" NON riparta da zero dopo il log di fase (dopo
  il fix; oggi riparte).
- **Fault injection** (per §4.1 e §4.3, solo se si vuole il testimone
  runtime): id fuori range iniettato in `ids` → oggi scrittura muta prima
  dello slab, dopo il fix `guasti++`; cudaHostAlloc forzata a fallire →
  oggi −2,3 GiB di VRAM, dopo il fix cache spenta pulita.

## Chiusura — la domanda giusta

Il mandato chiedeva "leggilo tutto perche' nessuno l'ha mai fatto". L'hanno
fatto in sei, in una notte, e hanno gia' trovato meta' di quello che c'era da
trovare: quello che NESSUNO ha fatto e' richiudere i verbali dentro il file.
I tre interventi che pagano subito, tutti da meno di un'ora l'uno:
1. il prefisso `cache_nome()` su OGNI riga del dump (chiude il difetto che
   ha gia' bruciato un mandato);
2. `git grep -n "atoi(v) : 2" src/models/deepseek4.cpp` → `0`, e
   `lru` default a 1 dopo M1 (i default allineati alla configurazione che i
   log di produzione gia' usano);
3. la validazione di `esperto` in kern_decidi/kern_prenota (sei confronti,
   trasforma la classe di guasto peggiore da muta a urlante).
