# La testa di Markov: 538 ms per fare 0,02 ms di conti

> **RIBALTATO il 3/8 pomeriggio — vedi [MARKOV_ASSOLTA](MARKOV_ASSOLTA.md).**
> I 538 ms erano dedotti, non misurati: la misura diretta per fase
> (DSPARK_PROF) dà testa ~2 ms e verifica MoE-CPU 954–1.203 ms per 6
> posizioni. La ripartizione 78/22 usata qui sotto non vale nel regime di
> verifica, e il conteggio dei cicli del braccio spento divideva per le
> chiamate draft (251) invece che per le verifiche vere (~164). Le sezioni
> «quanto varrebbe ripararla» e «cosa resta da fare» sono cestinate.

3 agosto 2026, mattina. Chiude la caccia aperta da «un modello da 6,8 GB su
una 3060 non può costare un secondo — sistema la configurazione».

## Il dato

Tre bracci, stesso binario, unica variabile la testa di Markov (cancello
`DSPARK_NO_MARKOV`, spento per difetto, in `dflash.cpp`):

```
                        ms/token   accettaz.  lung.  cicli   ciclo    draft
W0  controllo             235,88       —        —      —       —        —
W1  Markov ACCESA         333,05     0,636     4,14    76    1.315    872 ms
W2  Markov SPENTA         563,89     0,202     1,99   251      674    334 ms
```

Il blocco decodificato è di cinque posizioni in entrambi i bracci col draft:
cambia solo se la testa viene costruita nel grafo.

**La testa costa 538 ms per chiamata di draft — il 62% del costo del draft.**

## E non è calcolo

```
matematica della testa   5 x (get_rows + mul_mat 129.280 x 256 + add + argmax)
                       = 165 M MAC   ->  ~0,02 ms sulla 3060
misurati                 538 ms                       27.000 volte tanto
```

È esattamente ciò che la [PR ggml-org/llama.cpp#25173](https://github.com/ggml-org/llama.cpp/pull/25173),
che implementa DSpark, dichiara come costo noto: il bias è calcolato come *un
piccolo grafo ggml per-passo sullo scheduler del contesto del draft*, e il
rimedio indicato è costruirlo **una volta per blocco** riusandolo con nuovi
ingressi.

## Ma la testa si guadagna il posto

Spenta, l'accettazione crolla da **0,636 a 0,202** e il risultato complessivo
peggiora (563,89 contro 333,05). Non va tolta: va riparata l'implementazione.

## Quanto varrebbe ripararla

Se l'overhead sparisse mantenendo il bias — cioè draft a ~334 ms con
accettazione 0,636:

```
                          ciclo      ms/token    contro il controllo 235,88
oggi                    1.315 ms      333,05          -41%
overhead rimosso          777 ms      197            +20%     4,24 -> 5,08 t/s
   piu' la sovrapposizione max(443,334) = 443       +110%     4,24 -> 8,9 t/s
```

Sarebbe la prima configurazione della campagna in cui la speculazione batte
il controllo. **E qui, e solo qui, la sovrapposizione diventa la leva grossa**:
una volta che il draft (334) scende sotto la verifica (443), sovrapporre
nasconde il termine giusto.

## Le cinque ipotesi falsificate per arrivarci

```
grafi CUDA non attivi        LLAMA_GRAPH_REUSE_DISABLE=1 -> 10,75 ms, 2,8%
travaso in condivisa         draft caricato ma fermo     -> 20,59 ms, 5,3%
collocazione dei pesi        6,8 GB fra VRAM/RAM/misto   -> 7% di differenza
il contesto                  ctx 1024 contro 4096        -> identico
markov_w1 forzato su CPU     riquantizzato in f16        -> nessun cambiamento
```

L'ultima meritava di essere provata: `ggml-cuda.cu:4691` non ammette Q2_K in
`GET_ROWS`, e il log diceva a chiare lettere *«tensor 'markov_w1.weight'
(q2_K) cannot be used with preferred buffer type CUDA0, using CPU instead»*.
Era un difetto vero, introdotto da me requantizzando il draft, ed è stato
corretto — ma non era il costo.

## Il contesto che nessuna misura locale poteva dare

La [scheda del modello](https://huggingface.co/YanissAmz/DeepSeek-V4-Flash-DSpark-draft-GGUF)
documenta che DSpark perde proprio nel nostro caso d'uso:

```
prompt ripetitivi   accettazione 0,95-1,00    12,53 -> 14,65 t/s
codice aperto       accettazione 0,72         12,53 ->  9,75 t/s     PERDE
contesto lungo                                        0,70x          PERDE
```

Il nostro banco è una landing page HTML — codice aperto — e la nostra
accettazione è 0,63, sotto la loro. Non stavamo sbagliando configurazione:
stavamo riproducendo il loro caso di fallimento documentato, su un bersaglio
(284 B con esperti su CPU) ancora più sfavorevole del loro.

## Cosa resta da fare, in ordine

1. **Costruire il grafo della testa una volta per blocco** invece che per
   passo (il rimedio che l'upstream indica). Vale +20%.
2. **Poi** sovrapporre draft e verifica. Vale il resto.

Prima di 1, la sovrapposizione vale zero: nasconderebbe il termine più
piccolo.
