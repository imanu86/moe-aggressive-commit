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
