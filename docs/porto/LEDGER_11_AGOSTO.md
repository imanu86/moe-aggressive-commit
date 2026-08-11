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
