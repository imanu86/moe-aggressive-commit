# MANDATO — allargare la finestra dell'overlap

Lavori in `D:\llama-overlap`, ramo `overlap`, HEAD `b397c55a5`.

**NON compilare e NON avviare `llama-server`.** Compilo e misuro io: la macchina
e' una sola e la arbitro. Tu produci il codice e l'audit.

## Il fatto, misurato l'11/8

`GGML_SCHED_PROFILO=1` (sonda gia' in casa, mai accesa prima):

```
                    spec OFF (83,3 ms/token)   spec ON, adottata (131,3 ms/ciclo)
  split per grafo          130,7                        35,1
  ingressi                  14,56 ms (sync 12,18)        4,51 (sync 3,82)
  calc altri (lanci)         8,01                        3,11
  worker, lavori/grafo         42                          10
    attesa-evento            32,81                        8,36
    calcolo                  29,49                       15,77
  JOIN (sched)               62,03                       24,21
  join su tempo di parete    74,5%                       73,4%
```

Bilancio della configurazione adottata (61 s, 1.750 grafi):

```
  47,5%   il lavoratore CPU CALCOLA        <- e la GPU aspetta
  25,6%   il lavoratore CPU aspetta la GPU
  11,1%   sync ai confini degli split
   9,1%   lanci GPU        = 95,8% contato
```

Il commento di chi ha messo la sonda (`ggml-backend.cpp:847`): «join ~0
significa che il ramo CPU e' stato interamente coperto dal ramo GPU, cioe'
sovrapposizione riuscita». **Il join e' i tre quarti del tempo.**

## La causa, e sono due righe

**Invio** — `ggml-backend.cpp:2147`. Stando allo split **N** (GPU) si spedisce
al worker lo split **N+2** (CPU), a patto che N+1 sia sullo stesso backend GPU.

**Join** — `ggml-backend.cpp:1881`:

```c
  // - qualunque split che viene DOPO quello spedito PUO' dipenderne;
  // - qualunque split CPU va unito comunque, perche' il threadpool ha
  //   un solo proprietario
  if (split_id > split_spedito || e_cpu) { ggml_sched_worker_unisci(...); }
```

Gli split si scorrono in ordine crescente, quindi `split_id > split_spedito` e'
vero al **primo** split dopo N+2. La finestra di sovrapposizione e' esattamente
lo split N+1.

```
  lavoro GPU per split   ~33 ms / 130,7  =  0,25 ms
  lavoro CPU per lavoro   29,5 ms / 42   =  0,70 ms      <- 3x la finestra
```

Per questo il worker aspetta 32,8 ms (la GPU che drena) e poi calcola 29,5 ms
con la GPU vuota: **in serie**.

Se i due rami girassero insieme: `max(32,8; 29,5) + 22,6 = 55,4` invece di
83,3 ms. **+50%.**

## Il compito

La condizione di join e' **cautelativa**: dice «*puo'* dipenderne». Dentro uno
strato, lo split degli esperti GPU e quello degli esperti CPU sono **fratelli**:
entrambi alimentano la stessa combinazione e non dipendono l'uno dall'altro. E'
esattamente la coppia che dovrebbe sovrapporsi.

Il controllo di dipendenza VERA esiste gia' nello stesso file, venti righe
sotto (`:1908-1916`), usato per un'altra ottimizzazione:

```c
  for (int i = 0; i < graph_worker.n_nodes; i++) {
      if (graph_worker.nodes[i] == input) { prodotto_dallo_split_unito = true; break; }
  }
```

**Sostituire «qualunque split successivo» con «qualunque split che LEGGE
davvero un tensore prodotto dallo split del worker».** Dietro una leva nuova,
spenta di difetto.

Il secondo termine della condizione (`|| e_cpu`) e' un **vincolo vero**, non
cautela: due split CPU non possono girare insieme sullo stesso threadpool. Va
mantenuto. (Nota: `calc CPU` lato sched e' 0,8 ms/grafo, quindi quel ramo pesa
poco — ma non e' zero e non va rotto.)

## Le tre cose da non rompere, in ordine di gravita'

1. **Un worker non deve mai scrivere in un grafo liberato.** Il percorso
   d'uscita (`esci`, `:1851-1859`) esiste apposta e va rispettato su ogni
   ritorno anticipato che aggiungi.
2. **Le dipendenze indirette.** Un tensore puo' essere letto attraverso una
   vista (`view_src`) o come `src` di un nodo che non e' un ingresso dichiarato
   dello split. Se il tuo controllo guarda solo `split->inputs`, argomenta
   perche' basta — o allargalo. **Una dipendenza mancata qui e' una corruzione
   silenziosa, non un crash.**
3. **Il threadpool ha un solo proprietario.** Non spedire un secondo lavoro
   mentre il primo e' in volo, a meno che tu non aggiunga anche la coda — e in
   quel caso dillo esplicitamente, perche' e' un cambiamento piu' grosso.

## I cancelli, scritti PRIMA

1. **Leva spenta di difetto**, e a leva spenta il binario si comporta come
   oggi. Nome a tua scelta, in linea con gli altri (`LLAMA_OVERLAP_*`).
2. **NON pretendo lo SHA identico.** Cambiare l'ordine di esecuzione fra CPU e
   GPU cambia gli arrotondamenti: divergere e' lecito qui
   ([[cancello-sha-quando-vale]]). Il cancello e' che l'uscita resti **sensata
   e stabile fra due corse identiche**.
3. **Il numero da guardare NON e' il t/s**: e' `join (sched)` nella riga
   `sched-profilo`. Deve **scendere**. Se scende e il t/s non si muove, il collo
   si e' spostato e va detto, non nascosto.
4. **Attesa dichiarata prima**, in `audit/65-finestra.md`, coi numeri qui sopra.

## Riferimenti, misurati oggi

```
  senza sonda   14,19-14,26 t/s, ciclo 130,4-131,1, colpi 53,3-53,5, SHA 33D76723EB8D
  con sonda     13,78 t/s, ciclo 131,3, p1 0,81364, colpi 56,0-56,1  (deriva ZERO su due bracci)
                join 23,99-24,21 ms/grafo | worker calcolo 15,62-15,77 | attesa-evento 8,30-8,36
```

DS4-Flash IQ2_XXS, 43 strati, 256 esperti, 6 per token, RTX 3060 12 GB, Ryzen
5800X (`-t 7`), PCIe Gen4 x16, Windows/WDDM. Esperti in RAM bloccata mappata
(74.304 MiB), cache 339 slot x 6,75 MiB.

## Cosa NON fare, perche' e' gia' chiuso oggi con misura

- **Il trasporto.** DMA a domanda: neutro. Anticipo con pianificazione esatta
  (oracolo): 5,97 t/s contro 5,89 del cieco. Trasporto in blocco: microbench
  dice che tutte le modalita' vanno gia' a 24 GiB/s, al limite del PCIe, e il
  `kern_copia` di oggi pareggia il tetto contiguo. Dettaglio in
  `docs/porto/LEDGER_11_AGOSTO.md` §4.
- **La politica di sfratto.** Cinque euristiche provate sulla traccia vera,
  nessuna batte la LRU. §6.

Fine riga LF, `core.autocrlf` false: scansione byte diretta.
