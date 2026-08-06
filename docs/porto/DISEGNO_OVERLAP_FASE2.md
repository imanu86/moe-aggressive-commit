# DISEGNO — Fase 2: la sovrapposizione dei due rami (cantiere overlap)

*7/8 notte. Scritto DOPO i cancelli di Fase 1, sui numeri misurati del braccio
K2 sequenziale. Documento prima del codice; passa in lettura al coordinatore.
Base: Fase 1 meccanicamente dimostrata (B/T/V verdi, A emendato, nopin in
chiusura notarile).*

## Cosa la Fase 1 ha misurato (la base di questo disegno)

```
  K2 sequenziale:  8,9 t/s ≈ 112 ms/token   (K0: 9,0 ≈ 111)
  sonda:           87,7 split/grafo — calc CPU 23,2 ms — sync 73,8 — copie ~3
  colpi ramo GPU:  55,0%  (la politica sposta fuori i meno-residenti)
  id partizione:   perfetti (100 passaggi di verifica a zero)
```

Il ramo CPU costa 23,2 ms (20,8 di kernel + risveglio) e OGGI sta in fila:
il token paga att+resto, POI il ramo GPU, POI il ramo CPU. La Fase 2 fa
pagare `max(ramo GPU, ramo CPU)` invece della somma.

## La scoperta strutturale: NON servono gli eventi del backend CPU (in v1)

Il mandato inquadrava il bloccante come "il backend CPU non ha eventi". Il
flusso dati REALE della Fase 1 è più gentile:

```
  split CUDA-1:  attenzione → partizione → RAMO GPU     (gia' cosi': GPU-prima, 3a)
  split CPU-2:   RAMO CPU   — ingressi: cur (dall'attenzione) + ids_cpu (dalla partizione)
  split CUDA-3:  concat → riordino → pesi → somma → resto
```

Gli ingressi del ramo CPU dipendono da attenzione+partizione, **NON dal ramo
GPU**: i rami si toccano solo al join (CUDA-3). Oggi la serializzazione nasce
dal fatto che la copia-ingressi di CPU-2 fa `ggml_backend_synchronize(CUDA)`
= DRENA TUTTA LA CODA, ramo GPU incluso. La cura non è un'interfaccia eventi
per la CPU (la CPU qui è il *waiter*, non l'emettitore):

1. **Evento CUDA dopo i produttori** (`cudaEventRecord` sullo stream subito
   dopo partizione — o meglio: le copie-ingressi D2H accodate sullo stream
   PRIMA del ramo GPU, chiuse da un evento). API esistente, zero interfacce
   nuove.
2. **`cudaEventSynchronize` sull'host** al posto del drain: il thread che
   serve CPU-2 aspetta L'EVENTO (attenzione+partizione fatti), non la coda
   (ramo GPU incluso). Il ramo GPU continua a girare MENTRE la CPU calcola.
3. **CPU-2 su un worker** (il pezzo async vero): il thread dello sched lancia
   CUDA-1, stacca CPU-2 sul worker gated dall'evento, e prosegue... fino alla
   copia-ingressi di CUDA-3, che fa JOIN sul worker (attesa host del ramo CPU
   — a quel punto il ramo GPU è tipicamente già finito, o finisce lui per
   ultimo e il join è gratis).

L'interfaccia eventi-CPU del mandato resta la generalizzazione PULITA (e la
via se lo sched dovesse servire più casi): questa è la v1 minima che compra
la sovrapposizione con superficie di codice minima, tutta in
`ggml_backend_sched_compute_splits` + un helper CUDA. Il fallback/evoluzione
è dichiarato, non nascosto.

**La costruzione GPU-prima del 3a è il prerequisito già in tasca**: il ramo
GPU sta in CUDA-1, prima del ramo CPU — la scelta dichiarata (contatore +
ordine di lancio) paga la terza volta.

## Il conto, sui numeri misurati (non sul pricing di ieri)

```
  oggi (sequenziale):  att+resto ≈ 50  +  ramo GPU ≈ 28  +  ramo CPU ≈ 23  +  pedaggio ≈ 8-10  ≈ 112
  Fase 2:              att+resto ≈ 50  +  max(28, 23)    +  pedaggio ridotto              ≈  88-92 ms
                                                                                          ≈ 11,0-11,4 t/s a K=2
```

(ramo GPU ≈ 4/6 del calcolo 10,9 + trasporto dei suoi miss a 55% di colpi
~17-21 ms; da raffinare con la finestra marginale del braccio K2.) Il
12,3-12,6 del pricing presupponeva x*≈91-96 con rami bilanciati a ~23/23:
**a K=2 (86 esperti/token alla CPU) siamo vicini a x* ma il ramo GPU paga
più trasporto del prezzato** (colpi 55 misurati sul ramo, non i 2/3 circa
assunti). La strada dell'ottimo passa da: (a) K=3 da provare (129/token:
sopra x*, CPU ~31 ms — probabilmente troppo); (b) più colpi sul ramo GPU
(la cache che si concentra sui residenti: già visibile, +14 punti). Il
cancello di Fase 2 resta il token: **verso 88-92 ms misurati, poi si
raffina verso gli 80 col pedaggio e il bilancio**.

## I cancelli di Fase 2

- **N (nopin, ereditato)**: K2-nopin SHA == K0 same-binary — la meccanica
  dello split resta bit-verificabile a ogni build (il braccio notarile).
- **O (overlap reale)**: la sonda deve mostrare il sync di CUDA-1 che NON
  include più il ramo GPU al confine CPU (sync per grafo GIÙ di ~20 ms) e il
  token a 88-92 ms. Se il token non scende, guardare PRIMA i confini (sonda)
  e POI lo split — ordine del mandato.
- **S (stabilità)**: SHA del K2-pin stabile fra ripetizioni della stessa
  config (la divergenza cross-device è lecita ma DEVE essere deterministica).
- **-t 7 ENTRA QUI** (decisione 3 emendata): nel regime concorrente un core
  nutre la GPU. Braccio a coppie -t 7/-t 8 alla prima misura, una variabile.

## Rischi dichiarati

1. **Il worker e il threadpool**: CPU-2 sul worker deve usare il threadpool
   esistente senza corse col thread dello sched (pool con un solo owner per
   graph_compute: da verificare nel sorgente prima di scrivere).
2. **Cattura CUDA graph**: eventi e copie D2H accodate sullo stream DENTRO
   la cattura sono legali (sono operazioni di stream), ma il
   `cudaEventSynchronize` HOST non può stare nel grafo catturato — il replay
   non esegue host code. La sovrapposizione vive FUORI dal graph catturato o
   con cattura parziale per-split: da decidere leggendo come lo sched
   interagisce con la cattura oggi (i graph valgono 2×: non si rinuncia).
   QUESTO È IL RISCHIO N.1 e va sciolto per primo, a tavolino.
3. **Il join di CUDA-3**: l'attesa-host del worker dentro compute_splits è
   un blocco del thread sched — legale e voluto, ma va misurato (la sonda
   lo vedrà come ingressi di CUDA-3).

## Ordine di costruzione

1. Sciogliere il rischio 2 a tavolino (lettura: sched × cattura).
2. Worker CPU + evento (sched), dietro `LLAMA_OVERLAP_ASYNC=1`.
3. Bracci: K2-async contro K2-sequenziale (una variabile), coppia -t 7/8.
4. Raffinazione: pedaggio (polling), bilancio K, join per-parziale (la
   decisione 4 la permette DOPO, con la bit-esattezza del nopin in tasca).
