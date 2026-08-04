# Ammissione al routing: taglia il paging del 72%, la velocità non si muove

4 agosto 2026, pomeriggio. L'ultima leva della campagna — l'unica che **toglie**
lavoro invece di spostarlo — costruita, misurata, e conclusa.

## Cosa è

Il gate SSD→RAM impedisce lo *sfratto* degli esperti che contano, ma se il
router ne chiede uno freddo glielo diamo: la lettura da disco avviene e il token
aspetta. Per questo l'uscita è identica bit per bit, e per questo il guadagno si
ferma al 7,7%.

Qui si **nega**: gli esperti sotto soglia di massa non entrano nella selezione.

```cpp
selection_probs += maschera        // 0 ammette, -INFINITY nega
selected_experts = top_k(selection_probs, n_expert_used)
```

Il punto giusto era già nel codice: `probs` e `selection_probs` sono due tensori
**distinti** — la selezione usa il secondo, i pesi il primo. E llama.cpp usa già
`-INFINITY` su `selection_probs` per mascherare i gruppi di esperti. Il token
prende comunque sei esperti, i migliori fra gli ammessi, e i pesi si
rinormalizzano da soli perché `ffn_moe_weights_norm` divide per la somma dei
selezionati.

Il nodo si costruisce solo se il fornitore è installato: senza, la topologia del
grafo è identica e il costo è zero.

## Il dato

NeuraForge 8k, ctx 10000, gate acceso in tutti e tre, varia solo l'ammissione.

```
                      ms/token    t/s    fault duri/s    qualita'
A100  niente amm.      159,68    6,26      1.225        7/7, 0 sbilanciati
A050  ammissione 0,50  161,69    6,18        346        7/7, 0 sbilanciati
A025  ammissione 0,25     —       —            0        FALLITA
```

**Il meccanismo funziona**: negare metà degli esperti per strato fa crollare i
fault duri del **72%**.

**La qualità regge**: 7/7 requisiti, zero tag sbilanciati, e anzi *più* regole
CSS (74 contro 59) e *meno* righe duplicate (14,3% contro 17,2%).

**La velocità non si muove**: −1,3%, dentro il rumore.

## Il tranello che ha quasi prodotto il peggior errore della campagna

Il braccio a 0,25 riportava **7,22 t/s** — il numero più alto mai misurato,
oltre il tetto di 6,55.

Era degenerazione. La richiesta è finita in `HTTP 500 — "the model produced
output that does not match the expected peg-native format"`, dopo aver generato
8000 token, cioè il tetto, invece di fermarsi a ~5.800 come tutti gli altri.

Macinava spazzatura più in fretta perché non doveva più scegliere. L'ha
smascherata il file di risposta: **133 byte contro i 25 KB degli altri.**

Negare il 75% degli esperti rompe il modello. Negarne il 50% no.

## La quarta dimostrazione della stessa cosa

```
6,8 GB di draft spostati fra VRAM e RAM     costo invariato entro il 7%
tutto il modello in RAM (Q1)                 fault a zero, velocita' uguale
prefetch dei primi K per massa               +25% di I/O, nessun guadagno
ammissione al routing                        paging -72%, velocita' uguale
```

Quattro leve che toccano la memoria in quattro modi diversi — spostare,
eliminare, anticipare, negare. Nessuna sposta il tetto di ~6,5 t/s.

## Cosa resta, e cosa no

**Non resta niente sulla memoria.** Ogni forma di intervento sulla gerarchia è
stata provata e misurata.

La sola direzione mai tentata è quella che l'utente ha indicato oggi: portare il
**calcolo** degli esperti sulla GPU leggendone i pesi dalla RAM host, con un
buffer type `cudaHostAllocMapped` che oggi non esiste in ggml (`CUDA_Host` è
pinned ma con `is_host = true`, quindi le op restano sulla CPU).

Il microbench dell'era DwarfStar l'aveva già misurato su questa stessa 3060:
**51,6 ms/token** di consegna esperti in zero-copy, contro i 75,9 del copiare in
VRAM e i 14,9 dell'averli residenti. Sono ~60-80 righe in `ggml-cuda.cu`, e
sarebbe la prima leva che toglie lavoro alla CPU invece di riorganizzare la
memoria.
