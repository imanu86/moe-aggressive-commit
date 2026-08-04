# Il gate per massa cancella la coda: mai sotto 2,87 t/s

4 agosto 2026, notte. Fase 2 del reap-loop: agire sulla mappa invece di
guardarla. Primo guadagno riproducibile della campagna.

## Il dato

`VirtualLock` sui primi 1.200 esperti per massa (peso `2^-rango`), ricalcolati
ogni ~100 token, con sblocco di chi esce dai primi K. Due giri a ordine
invertito, ctx 10000, 1500 token:

```
braccio                       mediana   min    <4 t/s   <2 t/s    p10
BLOCCO  (giro 1, secondo)       7,05   2,97     4,3%     0,0%    4,78
BLOCCO  (giro 2, primo)         6,98   2,87     4,3%     0,0%    4,61
controllo (giro 1, primo)       4,90   0,51    46,7%    41,1%    0,88
controllo (giro 2, secondo)     6,55   0,60     5,5%     2,7%    4,75
```

**Non alza la mediana: cancella la coda.** Col blocco la velocità non scende
mai sotto 2,87 t/s e nessun campione sta sotto i 2, in entrambi i giri. Il
controllo scende a 0,5 e passa fra il 2,7% e il 41% del tempo sotto i 2.

E il blocco è **riproducibile** dove il controllo non lo è:

```
                 media finale        mediana tg_3s
blocco             6,36 / 6,32         7,05 / 6,98
controllo          3,96 / 5,80         4,90 / 6,55
```

L'ordine non spiega niente: il blocco vince anche girando per primo, su cache
fredda.

## Il meccanismo, e cosa dice sui buchi della GPU

I crolli periodici della GPU — quelli visti a occhio sul monitor, con la VRAM
piatta e la CPU occupata — sono esperti freddi che devono arrivare da SSD sotto
pressione di memoria. Bloccare l'insieme caldo garantisce che quelli non
manchino mai, e i crolli spariscono.

Era l'ipotesi dell'utente («è roba fredda?»), lasciata a «compatibile ma non
dimostrata» perché il campionamento a 10 s non poteva allineare un buco di 2.
La cura che li fa sparire è la dimostrazione.

Nota onesta: i fault duri col blocco sono **più alti** (mediana 4.386 contro
3.300). Interpretazione, non misura: bloccare 8 GB riduce la RAM per il resto,
quindi gli esperti freddi faultano di più — ma sono fault di domanda normali,
serviti in fretta, non le riclamazioni catastrofiche che producono i crolli.
Più fault piccoli, nessuno grande.

## La politica, come gira

```
15 passate    2.340 esperti bloccati    15,50 GiB residenti
1.151 sbloccati perche' usciti dai primi K    0 falliti
quota del working set alzata a 8,4 GiB, una volta sola
```

Quei 1.151 sono un dato nuovo: **anche restando nello stesso dominio, metà di
ciò che è residente si rinnova nel corso di una corsa.** La rotazione non è
solo fra domini.

## Il prefetch, falsificato prima di arrivare qui

Il primo tentativo usava `PrefetchVirtualMemory`, che è un suggerimento:

```
                     fault duri/s   pagine/s    t/s
P0 controllo             2.793       30.838     5,95
P1 K=2400                3.479       38.457     5,85     +25%
Q0 controllo             2.315       25.692     5,71
Q1 K=600                 2.505       27.945     5,85      +8%
```

L'I/O aggiunto scala con K e non toglie un solo miss. La ragione: ogni esperto
che il router sceglie **deve** essere letto — sono miss di domanda, e un
suggerimento di caricamento non ne evita nessuno. Serviva una garanzia di
non-sfratto, cioè `VirtualLock`.

## Tre difetti miei, tutti scoperti dall'aritmetica

1. **La quota alzata a ogni fallimento.** Copiavo `llama-mmap.cpp:689`, che
   però blocca una volta sola l'intero modello; io bloccavo esperto per
   esperto, e con 1.151 tentativi la quota si è gonfiata di ~76 GB. I fault
   quadruplicati di quella misura erano il difetto, non il meccanismo.
2. **Il controllo su cache fredda.** Girava per primo subito dopo il link, che
   svuota la page cache: 46,7% dei campioni sotto 4 t/s. Risolto invertendo
   l'ordine invece di assumere.
3. **Quattro segnaposto per cinque argomenti.** La riga stampava
   `sbloccati_tot` sotto l'etichetta «fallite», e ho letto 1.151 fallimenti
   dove non ce n'era nessuno. L'ha smascherata il fatto che i byte bloccati
   (15,50 GiB = 2.351 esperti pieni su 2.340 tentati) non tornavano con quel
   numero di fallimenti.

Il terzo è in un file dove avevo scritto io, poche ore prima, che *«uno
strumento che non sa dire perché non ha misurato niente»*.

## Cosa resta

**Il caso col drafter, che è quello che interessa davvero.** L'osservatore
chiave per numero di strato ricavato dal nome, e i tre strati del draft (0,1,2)
collidono con quelli del bersaglio; le quattro caselle di geometria per strato
non bastano per sei tensori. Va corretto — chiave per base del tensore, non per
numero di strato — prima di misurare la convivenza.

**La soglia K.** 1.200 esperti (8,1 GB) è il primo valore provato, scelto come
compromesso fra i 15-18 GB dell'insieme di massa e il rischio di far thrashare
il resto. La curva su K non è stata fatta.
