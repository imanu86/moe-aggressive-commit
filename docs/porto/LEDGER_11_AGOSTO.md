# Ledger dell'11 agosto

## 1. QUANTI ESPERTI DISTINTI CHIAMA UNA SESSIONE — la domanda mai posta

Domanda dell'utente: *«quanti esperti chiamiamo nel prompt neuraforge durante
tutta la corsa fino a 8k»*.

In tre mesi non l'avevamo mai misurata. Abbiamo misurato i **colpi** centinaia
di volte — quante volte la cache aveva gia' quello che serviva — e mai i
**distinti**: di quanti esperti diversi ha bisogno una generazione intera. Sono
due numeri diversi, e il secondo e' quello che decide se «tenere fermo il
miglior insieme residente» sia un'idea o un'illusione.

### 1.1 Due strumenti rotti trovati per strada

**(a) `LLAMA_CACHE_REGISTRA` non e' mai esistito.** Avevo scritto e lanciato
uno script che registrava le route mettendo questa variabile d'ambiente. Il
codice non la legge: `grep` su tutto `D:\llama-overlap` da' zero occorrenze.
La corsa e' girata regolarmente per quattro minuti, ha stampato t/s, p1 e
colpi — e non ha scritto nessuna pista. Nessun errore, nessun avviso.

Le route si dumpano davvero con `LLAMA_DEBUG_DUMP` + `LLAMA_DEBUG_FILTER`
(`common/debug.cpp:207`), e il callback lo installa **solo**
`llama-eval-callback`, che fa un prefill e basta.

**(b) `oracolo_pista.py` legge male i dump di prefill.** `ffn_moe_topk` non e'
un tensore suo: e' una **vista** dei primi 6 elementi di ogni riga di
`ffn_moe_argsort`, che ha 256 colonne. `ggml_nbytes` di una vista misura
l'ESTENSIONE, non il contenuto:

```
  ffn_moe_topk-3.000.bin   INDICE dice ne0=6 ne1=64   ->  384 int32 attesi
                           il file pesa 64.536 byte   ->  16.134 int32
                           6*4 + 63*1024 = 64.536          esatto
```

Con `reshape(-1, 6)` si leggono 2.689 righe invece di 64: le 2.625 in piu' sono
coda di argsort spacciata per route. **E i cancelli non se ne accorgono**:
l'argsort di 256 elementi e' una permutazione, quindi sei valori consecutivi
sono sempre distinti e sempre in [0,255]. Entrambi i cancelli di
`oracolo_pista.py` passano su dati inventati.

Il cancello che se ne accorge e' uno solo, ed e' quello che ho messo nel nuovo
contatore: **la riga intera dev'essere una permutazione di 0..255**.

Sui dump di **decode** (un token per chiamata) non c'e' passo da saltare e la
lettura ingenua e' corretta: le piste `ORACOLO1` dell'8 agosto stanno in piedi.
Il difetto colpisce solo i dump multi-token, cioe' il prefill.

Terza trappola dentro la stessa lettura: **il passo non e' uniforme fra gli
strati**. Nei primi (instradamento per hash) `ffn_moe_topk` e' un tensore vero
e contiguo — `ffn_moe_topk-0.000.bin` pesa esattamente 6x64x4 = 1.536 byte.
Dedurre il passo dal solo file sbaglia in un verso o nell'altro; va letto
`INDICE.tsv`, che porta forma e byte di ognuno.

Strumento nuovo: `docs/porto/conta_esperti.py`.

### 1.2 I numeri

Due tracce gia' su disco, prefill, stesso modello e stessa configurazione:

| traccia | posizioni | distinti | su 11.008 | MiB se residenti |
|---|---:|---:|---:|---:|
| prosa   | 1.996 | **10.152** | 92,2% | 68.526 |
| codice  | 1.678 | **8.827**  | 80,2% | 59.582 |

Nessuno strato usa meno di 157 dei suoi 256, e **tutti e 43** ne usano piu'
della meta'. Non c'e' un sottoinsieme.

E la curva di copertura, che e' il numero che decide il keep-level:

```
                    prosa                  codice
   50% domande <-   1.074 esperti  7,2 GiB    732   4,9 GiB
   70%         <-   2.377         16,0        1.679 11,3
   90%         <-   5.035         34,0        3.750 25,3
   99%         <-   8.311         56,1        6.834 46,1

   quello che ci sta in VRAM: 339 slot = 2,3 GiB | 448 = 3,0 | 512 = 3,5
```

**Per coprire meta' delle domande servirebbe il doppio-triplo della VRAM che
abbiamo.** Con 3,0 GiB (448 slot) si copre circa un quarto delle domande con un
insieme statico — contro il 59,4% che la LRU dinamica ottiene alla stessa
capienza. L'insieme statico non e' migliore di quello dinamico: e' molto
peggio, ed e' coerente con [[non-esiste-nucleo-caldo]] (la sovrapposizione
ruota, zero esperti oltre il 90% dei token).

La coda e' sottile — 4,8-8,6% dei distinti si chiama una volta sola, e vale
meno dello 0,2% delle domande — quindi non e' nemmeno un problema di outlier
da potare: e' il corpo della distribuzione a essere largo.

### 1.3 Come si e' misurato neuraforge

Serve una traccia di **decode**, e nessun binario genera col callback
installato. A temperatura 0 il routing di una posizione dipende solo dal
prefisso, quindi si rigioca: genero, salvo `prompt formattato + testo`, e
ripasso quella sequenza in **un prefill** sotto `llama-eval-callback`.

Caveat onesto: prefill e decode girano a batch diverso e l'aritmetica GPU non
e' identica al bit, quindi qualche scelta top-6 al limite puo' cambiare. Su un
CONTEGGIO DI DISTINTI e' rumore, non un errore sistematico.

Tre inciampi lungo la strada, tutti e tre nostri:

- `-b 512` con una sequenza da 7.268 token: `eval-callback` fa **una sola**
  `llama_decode`, quindi `GGML_ASSERT(n_tokens_all <= cparams.n_batch)`.
  `-ub` spezza, `-b` no.
- il template DeepSeek chiude con `<｜Assistant｜><think>` e l'uscita grezza e'
  `ragionamento</think>risposta`. Il server le restituisce separate, e
  riconcatenarle senza il tag perde un token e sfasa tutte le posizioni.
- `--no-warmup` non e' un argomento di `eval-callback` (lo spegne da se').

### 1.4 IL COSTO DEL CALLBACK ERA UNA RIGA

Il dump girava a **16 file ogni due minuti**: quattro ore per una corsa. La
causa e' in `common/debug.cpp`:

```c
    if (ask) {
        return true;  // Always retrieve data
    }
```

«true» a `ask` non e' gratis: lo scheduler **spezza il grafo su quel nodo** e ne
copia l'uscita su host. Dirlo per ogni nodo significa una barriera per nodo — e
il nostro grafo ne ha ~10.500 per ubatch, di cui ne volevamo 129.

Corretto: col dump acceso, `ask` risponde di si' solo per cio' che verra'
scritto. Senza `LLAMA_DEBUG_DUMP` il comportamento resta quello di prima.

## 2. MASSA = PESO x FREQUENZA, e l'intervallo cambia la domanda

Precisazione dell'utente: **massa = peso × frequenza in un dato intervallo**.
Il conteggio delle bussate da solo non e' massa.

Nota sul nostro codice: `LLAMA_CACHE_ESPERTI_MASSA` non implementa questa
definizione. `c.massa[indice]` e' il contatore delle bussate (`+= 1` a ogni
domanda, `cache-esperti.cu:2400`) con dimezzamento nella scansione di sfratto
(`:1719`). E' frequenza con decadimento, **senza il peso**. La leva si chiama
massa ma pesa solo le volte.

Il peso vero e' `ffn_moe_weights` (`llama-graph.cpp:2149`). Su questo modello
non compaiono `_norm` ne' `_scaled` nel dump, quindi e' la probabilita' grezza
del router per gli esperti scelti.

E l'intervallo e' il punto. Su UN token servono 43x6 = **258** coppie
(strato, esperto): **meno dei 448 slot che teniamo**. Il problema non e' la
capienza di un token — e' quanto in fretta l'insieme RUOTA. Strumento:
`docs/porto/massa_finestre.py`, che per ogni ampiezza W misura i distinti nella
finestra, il tetto dell'oracolo sulla finestra, e la politica implementabile
(migliori K dei W token precedenti, giudicata sul token dopo).

### 2.1 La misura, su neuraforge (7.267 posizioni, K = 448 slot)

```
   W   distinti   /258W    ORACOLO sulla finestra    PREDITTIVO sul token dopo
                          massa      domande         massa      domande
   1       258   100,0%      100,0%      100,0%         43,5%      36,4%
   2       420    81,4%       99,5%       98,9%         53,5%      46,2%
   3       557    72,0%       92,5%       85,9%         55,2%      47,1%
   5       795    61,7%       82,6%       72,8%         55,6%      46,9%
  10     1.278    49,6%       73,3%       63,5%         54,9%      46,3%
  20     1.986    38,5%       66,8%       57,0%         55,6%      46,6%
  50     3.284    25,5%       61,2%       51,6%         54,7%      45,7%
 100     4.492    17,4%       58,2%       48,6%         53,8%      44,5%
1000     8.422     3,3%       51,0%       41,9%         48,0%      38,9%
```

**Tre cose, e la terza ribalta il quadro.**

**(1) La rotazione da token a token e' del 64%.** Tenendo esattamente le 258
coppie del token precedente, del token dopo se ne indovina il **36,4%**. Due
token consecutivi condividono poco piu' di un terzo del loro instradamento.

**(2) La massa pesa piu' delle volte, ma di poco.** Il PREDITTIVO in massa sta
sempre 8-9 punti sopra quello in domande (55,6% contro 46,9% a W=5): gli
esperti che restano caldi sono anche quelli col peso piu' grosso. Non e'
niente, ma non e' il fattore due che servirebbe.

**(3) IL PREDITTIVO NON DIPENDE DALLA FINESTRA.** Da W=2 a W=100 sta fra 44,5%
e 47,1%: **due punti e mezzo su un fattore cinquanta di ampiezza**. Il massimo
e' a W=3 e vale 47,1%. Guardare piu' indietro non aiuta, e guardare meno
indietro nemmeno. Non c'e' una finestra giusta da trovare: la storia recente
contiene circa la stessa informazione qualunque sia la sua lunghezza, e non
basta.

E l'oracolo dice perche': a W=1 copre il **100%** (258 domande in 448 slot,
ci stanno tutte), a W=3 gia' l'85,9%, a W=10 il 63,5%. **L'unica cosa che
sposta il numero e' il FUTURO, non il passato.** Con un token di anticipo la
cache e' gia' abbastanza grande cosi' com'e'.

## 3. IL COSTO NON E' IL TRASPORTO, E' QUANDO LO PAGHI

Correzione dell'utente, e ha ragione. Avevo scritto che portare un esperto in
VRAM (~0,20 ms) costa quanto calcolarlo su CPU (0,242 ms), e quindi che
spostare il lavoro non serve. Il paragone e' sbagliato: **quei due numeri non
stanno sullo stesso orologio**.

I 0,20 ms del trasporto oggi si pagano *a domanda*, dentro `kern_copia`, che
gira **sugli SM e sullo stream di calcolo** — mentre copia, la GPU non calcola.
Anticipati sul motore di copia si pagano in parallelo, e non esistono.

L'aritmetica, tutta misurata:

```
  mancanti per token          164        (258 domande, 36,4% gia' residenti)
  per strato                    3,8      -> 25,7 MiB
  tempo di uno strato           1,78 ms  (ciclo 145 ms / 1,9 token / 43 strati)
  banda necessaria             14,4 GiB/s
  banda DMA misurata           24,4 GiB/s    <- ci sta, 40% di margine
```

E il premio e' la voce piu' grossa del profilo Nsight: i **34 ms** di
`kern_copia` per ciclo escono dal percorso critico.

```
  145 ms -> 111 ms per ciclo   =   13,2 -> 17,1 t/s
```

### 3.1 Perche' non l'abbiamo gia': il prefetch predice dal PASSATO

Il prefetch fra token e' gia' stato provato e vale 41,8% di sovrapposizione —
ed e' esattamente il numero che questa tabella spiega: predire dal token
precedente **non puo'** fare meglio del 36-47%, qualunque finestra si usi.

Il pezzo che serve esiste, e' misurato, e non e' mai stato collegato al
prefetch: il **predittore di route** ([[predittore-route-gate-strato-dopo]]),
cioe' il gate dello strato L+1 applicato allo stato nascosto di L. Fa **71% da
solo e 90,2% con la recency**, allo 0,2% del calcolo. E' anticipo di **un solo
strato**, che e' quanto basta: servono 1,78 ms di finestra e il trasporto ne
chiede 1,05.

**Il cantiere e': predittore di route -> coda DMA a uno strato di anticipo.**
Non e' una leva nuova, e' una composizione di due cose gia' in casa e mai
messe insieme.

### 3.2 DOMANDA_DMA misurato: ZERO, e il perche' e' istruttivo

Cancello e prima misura, 11/8 h07:54-08:03. Il cancello SHA passa su tutti e
tre i bracci — la build che ha rilinkato `ggml-cuda.dll` e' neutra.

```
  braccio          t/s     ciclo    p1        colpi    SHA
  g_rif           14,24    130,6    0,86470   53,3%    33D76723EB8D   passa
  g_dom           14,25    130,5    0,86470   53,4%    33D76723EB8D   passa
  g_rifb          14,26    130,4    0,86470   53,5%    33D76723EB8D   passa
  deriva del banco fra i due riferimenti: 0,14%
```

La leva vale **zero**. E i contatori dicono perche':

```
  g_rif   a domanda (stream CALCOLO) 549,52 GiB   in prefetch (stream DMA) 0,00 GiB
  g_dom   a domanda (stream CALCOLO) 541,41 GiB   H2D 11,23 GiB, fallback cattura=129
```

Ha spostato **11,2 GiB su 552,6 — il 2,0%**. Il cancello che avevo dichiarato
(`fallback cattura == 0`) **non passa**: 129 ricadute in cattura del grafo.

Guardando `cache-esperti.cu:2774-2819`, tre scelte glielo impediscono per
costruzione:

```c
  2789:  CUDA_CHECK(cudaStreamSynchronize(stream));        // un sync PER STRATO
  2812:  cudaMemcpyAsync(dst, src, passi[q], ..., stream); // lo STESSO stream di calcolo
  2781:  if (cattura != None) { fallback++; return false; } // solo fuori cattura
```

Il commento in cima al blocco lo dichiara: «Sostituisce il trasporto del primo
`kern_copia` della terna con DMA **sullo stesso stream**».

**Cambia il MECCANISMO, non il MOMENTO.** Resta a domanda, resta sullo stream
di calcolo, e ci aggiunge una sincronizzazione per strato — il costo che il
disegno originale evitava apposta. Che sia uscita neutra invece che peggiore e'
quasi fortuna. E' [[costo-non-e-quanto-ma-quando]] scritto in codice: abbiamo
misurato *quanto*, non *quando*.

### 3.3 Il numero che nessuno aveva mai visto in chiaro

```
  549,52 GiB di esperti attraversano il bus in 1.200 token
  = 469 MiB per token,  e lo stream di prefetch ne ha mossi 0,00
```

Non e' una brutta notizia: e' la conferma che il corridoio esiste. 469 MiB a
24,4 GiB/s sono 19,2 ms per token, cioe' **36,5 ms su un ciclo da 130** — sul
motore di copia ci stanno con tre volte il margine.

E `runtime->stream_pf`, lo stream di prefetch, **viene creato all'avvio**
(`cache-esperti.cu:1535`) e in questa configurazione trasporta zero. Il canale
e' gia' aperto e inutilizzato.

## 4. IL MANDATO «ANTICIPO» E' FALSIFICATO — e non dove pensavo

Quattro ore dopo averlo scritto. Tre esperimenti, in ordine di costo crescente.

### 4.1 Accendere il prefetch: il ciclo raddoppia

```
  braccio    t/s     ciclo     colpi    byte CALCOLO / PREFETCH
  g_rif     14,24   130,6 ms   53,3%     549,52 GiB /    0,00 GiB
  w2         6,03   300,2      55,1%          -    /      -
  w4         4,68   393,2      49,8%     715,06    / 3081,44
```

Il canale funziona: 3.081 GiB si sono davvero mossi sul motore di copia. Ma il
prefetch cieco trasporta **5,6 volte i byte** e ne scarta 386.100, e satura:
3.796 GiB in 256 s sono 14,8 GiB/s. Saturandolo rallenta anche il traffico a
domanda, che infatti SALE da 549 a 715 GiB.

### 4.2 Il tetto con la pianificazione ESATTA: identico al cieco

Catena in tre passi (`oracolo_1_rif` -> `oracolo_2_pista` -> `oracolo_3_tetto`),
tutta a speculazione spenta, perche' l'oracolo avanza una riga per PASSO di
decode (`llama-context.cpp:2057`, solo con `n_tokens == 1`) e con la bozza ogni
passo porta due token: l'indice sfaserebbe per costruzione.

```
  o_w0    prefetch spento              11,89 t/s   84,1 ms   colpi 52,7%    555 GiB
  o_w2    prefetch, previsione CIECA     5,89     169,8       55,8%       2.048 GiB
  o_ora   prefetch, previsione ESATTA    5,97     167,5       57,0%       1.984 GiB
  o_w0b   controllo di deriva           11,86      84,3       53,3%         505 GiB
```

I due bracci a prefetch spento danno lo **stesso SHA `10EDB3A9C39B`** e deriva
0,25%: la base non si muove, e il raddoppio del ciclo non e' rumore.

**L'oracolo vale +1,2 punti di colpi e +1,4% di velocita' sul cieco.** Sapere
tutto in anticipo, token per token e strato per strato, non cambia niente.

E il numero che spiega perche': con la previsione perfetta il prefetch muove
**1.984 GiB contro i 2.048 del cieco, il 3% in meno**. Se il collo fosse la
precisione, l'oracolo trasporterebbe solo i mancanti (~970 GiB). Ne muove il
doppio: con `W=2` ogni strato viene predetto da due punti di vista, quindi
**ogni esperto viene trasportato due volte**.

**Il costo e' del MECCANISMO, non della previsione.** E la banda lo conferma:

```
  a domanda, W=0        554,93 GiB in 101 s  =  5,5 GiB/s
  oracolo,   W=2       1.984,18 GiB in 201 s  =  9,9 GiB/s
  letto mappato, misurato                       18,4 GiB/s
  DMA, misurato                                 24,4 GiB/s
```

Non siamo vicini al limite di banda in nessuno dei due casi. Il trasporto un
pezzo per volta e' **orchestration-bound** ([[orchestration-bound-not-byte-bound]]),
e l'aritmetica del mandato («469 MiB/token a 24,4 GiB/s stanno in 36,5 ms»)
usava una banda che su questo cammino non abbiamo mai visto.

### 4.3 E dove sono invece i punti: nello SFRATTO

Simulazione sulla traccia vera, nessuna GPU (`docs/porto/simula_sfratto.py`):
1.268 token x 43 strati x 6 id = 327.144 accessi, 9.164 coppie distinte, di cui
il 2,8% sono miss obbligatorie.

```
  capienza     LRU     "sfratta il consumato"     BELADY (ottimo)
    339      40,3%            12,6%                  63,4%      +23,1
    448      47,5%            14,8%                  68,3%      +20,8
    512      50,8%            16,1%                  70,5%      +19,7
```

**Ventitre punti di colpi sul tavolo a parita' di capienza**, solo cambiando chi
si butta. Nessuna politica puo' superare Belady: e' il tetto, non una proposta.

E una mia idea falsificata nella stessa corsa. Avevo scritto all'utente che
l'esperto appena usato e' «il candidato allo sfratto perfetto», perche' non
serve piu' per 43 strati. Sui dati veri e' **il peggiore possibile**: 12,6%
contro 40,3%. Il motivo e' aritmetico e me l'ero perso: 43 strati sono 258
accessi, **esattamente un token** — e la cache ne tiene 339. Non e' lontano, e'
vicino. Buttandolo subito si distrugge proprio il 36,4% che sopravvive da un
token all'altro.

### 4.4 Cosa resta

Due strade, entrambe indicate dall'utente e coerenti con tutto il misurato:

1. **Trasporto IN BLOCCO** (idea dell'utente): un evento per token invece di
   43xW. E' l'unica leva che attacca il costo per-operazione, che e' il collo
   dimostrato. Il cammino esiste gia' spento: `LLAMA_VRAM_A_FASI_CALDO` con
   `kern_ricarica` (`cache-esperti.cu:812`), che dichiara 2.289 MiB a
   ~18,4 GiB/s = 124 ms prevedibili invece di 339 buchi sparsi. **Quel 18,4 e'
   la banda del letto mappato, non una misura di quel cammino**: e' la prima
   cosa da mettere sul banco.
2. **La conoscenza serve allo SFRATTO, non al prefetch.** L'oracolo sa quali
   coppie il token corrente deve ancora usare; la leva `LLAMA_CACHE_ESPERTI_CURA`
   («lo sfratto deve conoscere la previsione») esiste dal 27/7 e non e' mai
   stata composta con l'oracolo.

## 5. COSA CHIEDE L'ATTESA: il ramo CPU, e non e' sovrapposto

Domanda dell'utente: se il trasporto usa 5,5 GiB/s su 24 ed e' sempre fermo,
cosa chiede quell'attesa?

### 5.1 Il profilo di ieri, riletto

Il `.sqlite` era su disco dalle 06:26 e non l'avevo mai interrogato oltre i
kernel. `cuda_api_sum`:

```
  57,0%  cudaEventSynchronize   17,6 s   28.320 chiamate, mediana 0,65 ms
   9,0%  cudaStreamSynchronize   2,8 s   78.046
   5,0%  cudaLaunchKernel        1,6 s   75.687
   5,0%  cudaMemcpyAsync         1,6 s   64.416
```

L'host passa il **57% del tempo di parete bloccato su eventi**. Nei sorgenti
che compiliamo l'unico chiamante caldo e' `ggml-backend.cpp:906`, nel ciclo del
lavoratore dell'overlap CPU||GPU.

E il profilo lanciato apposta per rispondere (`--sample`, `--cpuctxsw`) e'
inutilizzabile due volte: `osrt` non esiste su Windows, e sostituito con `wddm`
**ha fatto cadere la macchina**. Campionamento CPU e context switch richiedono
privilegi di amministratore. Non serviva: la sonda era gia' in casa.

### 5.2 `GGML_SCHED_PROFILO=1`, spenta da sempre

```
                    spec OFF (83,3 ms/token)   spec ON, adottata (137,9 ms/ciclo)
  split per grafo          130,7                        36,3
  ingressi                  14,56 ms (sync 12,18)        4,51 (sync 3,78)
  calc altri (lanci)         8,01                        3,07
  worker, lavori/grafo         42                          11
    attesa-evento            32,81                        8,68
    calcolo                  29,49                       16,10
  JOIN (sched)               62,03                       24,89
  join su tempo di parete    74,5%                       73,4%
```

Il commento di chi ha messo la sonda (`ggml-backend.cpp:847`) dice: «join ~0
significa che il ramo CPU e' stato interamente coperto dal ramo GPU, cioe'
sovrapposizione riuscita». **Il join e' i tre quarti del tempo, in entrambe le
configurazioni.**

Bilancio della configurazione adottata, su 61 s e 1.800 grafi:

```
  47,5%   il lavoratore CPU CALCOLA        <- e la GPU aspetta
  25,6%   il lavoratore CPU aspetta la GPU
  11,1%   sync ai confini degli split
   9,1%   lanci GPU
  ------
  95,8%   contato
```

### 5.3 Perche' non si sovrappone: la finestra e' larga UNO SPLIT

`ggml-backend.cpp:2147`: allo split **N** (GPU) si spedisce al lavoratore lo
split **N+2** (CPU), se N+1 e' GPU. Poi `ggml-backend.cpp:1881`:

```c
  // - qualunque split che viene DOPO quello spedito PUO' dipenderne;
  // - qualunque split CPU va unito comunque (un solo proprietario del threadpool)
  if (split_id > split_spedito || e_cpu) { ggml_sched_worker_unisci(...); }
```

Gli split si scorrono in ordine, quindi il join scatta al primo split dopo
N+2. **La finestra di sovrapposizione e' esattamente lo split N+1.**

```
  lavoro GPU per split    ~33 ms / 130,7  =  0,25 ms
  lavoro CPU per lavoro    29,5 ms / 42   =  0,70 ms
```

**Tre volte piu' stretta del lavoro che deve coprire.** Per questo il
lavoratore aspetta 32,8 ms (la GPU che drena) e poi calcola 29,5 ms con la GPU
vuota: in serie. E spiega perche' la spazzata su `LLAMA_OVERLAP_K` non aveva
dato niente — K allarga il batch, non la finestra
([[overlap-fase2-tetto-cpu]]).

La condizione e' **cautelativa**: dice «*puo'* dipenderne». Dentro uno strato lo
split degli esperti GPU e quello degli esperti CPU sono fratelli e non
dipendono l'uno dall'altro. Il controllo di dipendenza vera esiste gia' poche
righe sotto (`prodotto_dallo_split_unito`, `:1908-1916`), usato per un'altra
ottimizzazione.

Se i due rami girassero davvero insieme: `max(32,8; 29,5) + 22,6 = 55,4 ms`
invece di 83,3. **+50%.**

### 5.4 Che cosa calcola la CPU: NON il drafter

Prima ipotesi: gli esperti della bozza, che `-otd` mette su CPU (DSpark e' al
97,5% esperti). **Caduta prima di provarla**, dal confronto gia' in mano:

```
                      drafter    calcolo CPU per TOKEN
  spec OFF (c_off)      NO          29,5 ms
  spec ON  (b_rif)      SI          34,2 ms   (15,62 x 2,19 grafi/token)
```

Senza drafter la CPU calcola quanto o piu' che con. Il braccio di conferma
(`-otd` tutto su `CUDA0_Mapped`) e' comunque morto sul tetto della pinnata —
`cudaHostAlloc di 6672,00 MiB fallita: out of memory`, perche' i 74.304 MiB del
bersaglio piu' i 6.672 della bozza fanno 79,1 GiB contro un tetto misurato fra
74,7 e 76,9 ([[doublekvring-pinnata-e-la-risorsa-scarsa]]).

Il candidato che resta, e torna coi numeri: **i MANCANTI della cache**.

```
  colpi 53-56%  ->  ~113-121 mancanti per token
  x ~0,25 ms l'uno  ->  ~30 ms per token       = il calcolo del worker
```

Da verificare col nome (`GGML_SCHED_DEBUG=1` stampa gli split e le loro
operazioni): per ora e' un'inferenza da tre numeri che tornano.

Il braccio di controllo chiude con **deriva zero**: `b_rifb` riproduce `b_rif`
cifra per cifra (13,78 t/s, 131,3 ms, p1 0,81364, colpi 56,0 contro 56,1).

## 6. LA POLITICA DI SFRATTO: il margine di Belady NON e' raccoglibile

Domanda dell'utente: la politica degli esperti che portiamo in VRAM non e'
ottimale, e resta quel punto da sistemare.

E' vero, e ho provato a prenderlo. Cinque euristiche implementabili, sulla
stessa traccia, contro il tetto:

```
  capienza     LRU     LFU    MASSA    SLRU   RIUSO  CONSUMATO   BELADY
    339      40,3%   37,7%   10,7%    6,8%    7,8%     12,6%     63,4%
    448      47,5%   42,3%   14,3%   50,4%   15,1%     14,8%     68,3%
    512      50,8%   44,6%   16,4%   52,8%   18,9%     16,1%     70,5%
```

**Nessuna batte la LRU**, tranne SLRU da 448 in su (+2,9 e +2,0 punti) — e a
339 crolla al 6,8%, comportamento sospetto da non prendere per buono.

**CORREZIONE A QUELLO CHE AVEVO DETTO.** Avevo presentato i +24 punti di Belady
come se valessero ~+25% di t/s. Erano un TETTO, e l'ho passato per raccoglibile.
Non lo e': il margine sta quasi tutto in informazione che nessuna statistica del
passato possiede, ed e' lo stesso muro che ha fermato il prefetch stamattina,
visto dall'altro lato.

```
  copertura del top-K da QUALUNQUE finestra passata   44-47%   (§2.1)
  colpi della LRU                                     40,3%
  ------
  raccoglibile con una politica a finestra            +4..7 punti
  in tempo                                            ~4 ms/token   ~+6%
```

## 7. L'ORDINE CHE NE ESCE

| fronte | raccoglibile | perche' |
|---|---:|---|
| **finestra dell'overlap** | fino a **+50%** | difetto di meccanismo, causa nota, riga nota |
| politica di sfratto | ~+6% | il resto e' informazione che non abbiamo |
| trasporto (DMA / anticipo / blocco) | **0** | chiuso da tre angoli, §4 |

La tesi dell'utente — «se portassimo gli esperti in VRAM al momento giusto
andremmo come un modello interamente residente» — **regge**, e oggi ha un
prezzo: il costo della non-residenza e' i ~30 ms per token di CPU seriale. Ma
non si recupera indovinando meglio COSA tenere: si recupera non pagandolo in
serie.

## 8. IL BANCO ERA SBAGLIATO, E CON ESSO META' DEI VERDETTI

Intuizione dell'utente, confermata dalla misura:

> «abbiamo nascosto qualcosa che non sapevamo fare bene (trasporto e
> orchestrazione GPU) dietro un'altra leva che ci aiuta tanto (CPU)»

### 8.1 Che cosa calcola la CPU: LETTO, dopo quattro ipotesi sbagliate

Quattro congetture, quattro falsificazioni, e ogni volta un ragionamento che
tornava: gli esperti del drafter (smentita dal confronto spec-off/spec-on), i
mancanti della cache (smentita dal codice: `supports_op` sospende il rifiuto
quando la cache e' accesa), l'indexer non fuso (`FUSO=1` e' neutro), la soglia
di offload a 32 (quattro bracci, gli split non si muovono).

La risposta stava in una stampa che il logger buttava via. `GGML_LOG_DEBUG` non
esce dal server nemmeno con `-lv 4`; aggiunto `GGML_SCHED_DEBUG_INFO=1` per
farla uscire a INFO (commit `b839bf1ee`), i 978 nodi su CPU sono **tutti**:

```
  MUL_MAT_ID   ffn_moe_gate_overlap   x129
  MUL_MAT_ID   ffn_moe_up_overlap     x129
  MUL_MAT_ID   ffn_moe_down_overlap   x129
```

Il suffisso dice tutto: li crea **il nostro `LLAMA_OVERLAP_ASYNC`**, la leva del
7/8. Non un ripiego, non un difetto: un secondo ramo degli esperti, messo li'
apposta.

**REGOLA: quando un numero grosso non ha un nome, il primo lavoro e' dargli un
nome, non spiegarlo.** Se avessi forzato quella stampa alle 09:00 invece che
alle 12:20, le quattro congetture non sarebbero servite.

### 8.2 Spegnendo la lane, i verdetti si ribaltano

```
                        t/s    ciclo   colpi   split/grafo   ingressi (sync)
  overlap K=2         13,96   129,7   56,0%      35,1        4,73 ( 4,07)
  overlap K=1         10,76   164,5   28,3%      35,2       20,07 (19,45)
  overlap SPENTO       9,80   185,7   18,8%       3,7       36,24 (35,80)
```

Gli **stessi 339 slot** passano da 56,0% a 18,8% di colpi: la cache comincia a
vedere TUTTE le domande. Il 56% era misurato sulla frazione che restava alla GPU.

E la capienza, che il 10/8 avevamo chiuso come «non paga» (339→448: +6,5 punti
di colpi, **−8,3%** di t/s), sul banco senza lane **paga moltissimo**:

```
  339 slot   9,93 t/s   colpi 18,9%   sync 35,34 ms/grafo
  448       12,32       46,5%         28,20
  480       12,41       48,6%         27,81
  512       12,64       49,0%         27,21   <- massimo che carica, 270 MiB liberi
  544       MORTO
```

Il ginocchio cade dove deve: a 448 slot il working set di un token (258 coppie)
ci sta con 190 di margine, a 339 no. E **il simulatore aveva previsto 50,8% a
512; misurato 49,0%** — si puo' usare per scartare idee senza toccare la macchina.

`LLAMA_CACHE_ESPERTI_BATCH` e' **inerte** (18,9% contro 19,3% a 8 e 64): risposta
alla domanda aperta del mandato RING, quel cancello non e' il vincolo.

### 8.3 IL VERO COLLO: 277 copie per token, e non sono nostre

Profilo per kernel sul banco GPU-only (512 slot, lane spenta):

```
  GPU                              host, dentro le API CUDA
  30%  mul_mat_q<16,64>     86     69%  cudaStreamSynchronize  368.765
  19%  mul_mat_q<10,64>     43     16%  cudaMemcpyAsync        221.963
  20%  kern_copia        1.425
   3%  mul_mat_vec_q_moe   774
```

**221.963 `cudaMemcpyAsync` su 800 token = 277 per token**, contro 258 domande
di esperti. Non sono della nostra cache — `kern_copia` fa 1.425 lanci in tutto.
Sono del fallback dello scheduler, `ggml-backend.cpp:1946`:

> «when offloading MoE weights, we can reduce the amount of data copied by
> copying only the experts that are used»

Copia **un esperto per volta**, e l'host ci sta dentro 82 us di media. Ci sono
**due trasporti in concorrenza**, e quello di ggml fa 156 volte i lanci del
nostro — il che spiega perche' nessuna leva sulla cache morde: **i byte non
passano di li'**.

La condizione che lo accende (`:1948`) e'
`ggml_backend_buffer_is_host(input->buffer)`, cioe' esattamente cio' che decide
`LLAMA_MAPPED_IBRIDO` (`ggml-cuda.cu:1439`). Con `IBRIDO=0` il buffer diventa
CUDA puro e non c'e' niente da copiare al confine.

```
  IBRIDO=1  ASYNC=1   configurazione adottata          13,96 t/s
  IBRIDO=1  ASYNC=0   banco nuovo                      12,64
  IBRIDO=0  ASYNC=1   disastro (212 split, 3.266 ms)       -
  IBRIDO=0  ASYNC=0   MAI PROVATA
```

### 8.4 E il moltiplicatore: la bozza paga il pedaggio della residenza

```
  senza bozza   12,01 t/s  ->  1 token ogni  83,3 ms
  con bozza     14,26      ->  1,91 token ogni 134 ms
```

La bozza produce **+91% di token** e il ciclo si allunga del **+61%**: resta
+18,7%. E quel 61% e' residenza — verificare due token non raddoppia il
calcolo (i pesi sono gli stessi) ma **raddoppia l'insieme da tenere in VRAM**,
perche' due token consecutivi condividono solo il 36,4% delle route: l'unione e'
~420 coppie invece di 258.

```
  se la residenza non costasse: 1,91 token in 83,3 ms = 22,9 t/s
```

**La residenza non e' un fronte fra i tanti: e' il moltiplicatore di tutti gli
altri.** Ogni leva che aggiunge token per ciclo paga quel pedaggio, e il pedaggio
cresce col batch. E' anche il motivo per cui `n-max 1` e' rimasto: a 2 o 3
servirebbero 700-900 coppie contro 512 slot.

### 8.5 La lane CPU si e' svuotata mentre il resto migliorava

Dai 349 log storici (`residenza.csv`), il migliore per giorno:

```
  08/08  10,74 t/s   |  drafter ON 10,74  OFF 10,44   (la bozza valeva +2,9%)
  08/09  12,83       |
  08/10  13,73       |  ON 13,73  OFF 11,89          (+15,5%)
  08/11  14,26       |  ON 14,26  OFF 12,01          (+18,7%)
```

Il drafter era **gia' acceso l'8/8**: non l'abbiamo acceso, l'abbiamo fatto
funzionare (TOPK=1 il 9/8, fusione HC il 10/8). Le due leve si sono mosse in
direzioni opposte: la lane CPU dalla SOTA di allora a **+10,4%** oggi, la
speculazione da +2,9% a **+18,7%**.

(Sono «il migliore del giorno» su configurazioni eterogenee: indicano la
direzione, non la misurano. I due numeri controllati di oggi sono lane +10,4% e
speculazione +18,7%.)
