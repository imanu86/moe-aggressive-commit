# TODO — la lane CPU deve SOMMARSI, non competere

Chiesto dall'utente il 13/8. Non e' «riaccendere la lane»: la lane e' gia'
accesa (`LLAMA_OVERLAP_ASYNC=1`, `LLAMA_OVERLAP_K=2`) in tutti i bracci. Il
punto e' che oggi prende un numero FISSO di esperti per strato senza sapere
cosa le altre due vie stanno gia' facendo.

## Perche' adesso e' diventato urgente

Col prefetch device-side che copre il 51% del traffico, il mucchio dei non
residenti si sta svuotando. `kern_partiziona` ordina in classi e la CPU si
serve dalla testa:

    classe 0   non residente        <- quello che la CPU deve prendere
    classe 1   in transito          <- SCUDO_TRANSITO=1 lo mette qui
    classe 2/3 residente            <- la CPU non dovrebbe toccarlo MAI

Quando la classe 0 ha meno di `k_cpu` membri, la CPU **scende nelle classi
successive** e si prende dei residenti. Costo misurato (llama-graph.cpp:1800):

    esperto su CPU              0,242 ms
    esperto su GPU se residente 0,060 ms
    esperto su GPU se da copiare 0,271 ms (0,060 + copia)

Prendere un residente per darlo alla CPU e' un **fattore quattro buttato**, e
succede tanto piu' spesso quanto meglio funziona il prefetch. Le due leve si
mangiano a vicenda proprio quando cominciano a funzionare tutte e due.

## La regola

`k_cpu` non e' una costante ma il **minimo fra il taglio voluto e quanti non
residenti veri ci sono**. La CPU prende cio' che nessun altro puo' servire in
tempo; se non c'e' niente, non prende niente e lo strato costa solo la GPU.

## Cosa serve, e c'e' gia' quasi tutto

- il conteggio delle tre classi: **fatto**, `kern_partiziona` scrive
  `lane_cpu` / `lane_scudati` / `lane_gpu` e il rapporto stampa il bilancio;
- il taglio per strato: gia' variabile (Bresenham su `il`), quindi le forme
  restano fisse e i CUDA graph non se ne accorgono — **e' il vincolo che
  rende la cosa fattibile**: un taglio variabile per TOKEN romperebbe la
  cattura (famiglia di difetti del replay stantio);
- manca: portare il conteggio della classe 0 **dentro** la decisione del
  taglio. Il numero e' noto sul device al momento della partizione, ma
  `k_cpu` e' deciso sull'host alla costruzione del grafo. Questa e' la vera
  difficolta', ed e' la stessa forma del problema gia' risolto per il
  consumatore dell'anello: **chi decide deve stare dove il dato e', e dentro
  il grafo**.

## Come si verifica che paghi

Il bilancio della domanda a fine corsa deve mostrare la CPU che consuma
**solo** classe 0. Oggi non lo si vede perche' il conteggio e' per classe, non
per destinazione: serve un contatore in piu' — quanti degli esperti dati alla
CPU erano residenti. Se quel numero e' zero, la lane si sta sommando; se e'
grande, si sta mangiando il prefetch.

Vedi anche [[il-confine-costa-27ms-per-ciclo]]: spostare lavoro fra CPU e GPU
crea rendezvous, e ognuno costa 0,94 ms. Un taglio adattivo che oscilla puo'
pagare piu' confini di quanti ne risparmia — il taglio deve restare per
strato, mai per token.
