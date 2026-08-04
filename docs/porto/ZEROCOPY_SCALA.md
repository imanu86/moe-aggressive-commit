# Lo zero-copy scala: +12,1%, e i crolli spariscono

4 agosto 2026, pomeriggio. Prima cosa della campagna che **scala con un
parametro**. Tutto il resto era piatto.

## L'idea, che è dell'utente

Il tetto è orchestrazione: quattro leve sulla memoria — spostare i pesi,
eliminare il paging con Q1, anticiparlo col prefetch, negarlo con l'ammissione
— non l'hanno mosso. Questa è diversa: gli esperti restano in RAM, ma li
**calcola la GPU leggendoli dove sono**, sul PCIe.

Serviva un tipo di buffer che in ggml non esisteva. `CUDA_Host` alloca pinned
ma dichiara `is_host = true`, quindi lo scheduler manda comunque le operazioni
alla CPU: è memoria veloce da *copiare*, non memoria su cui la GPU possa
calcolare. `CUDA0_Mapped` usa `cudaHostAllocMapped` +
`cudaHostGetDevicePointer` e tiene `is_host = false`.

## Il dato

NeuraForge 8k, ctx 10000, `-ub 64`. Ordine dei bracci **W1, W0, W2**: la tesi
da dimostrare va per prima, su macchina appena riavviata, così se vince lo fa
nonostante l'handicap.

```
                  ms/token   t/s    mediana   min    p10    sotto 2 t/s
W1  17 strati      157,11    6,37    6,49    4,73   5,95     0,0%
W2   8 strati      163,59    6,11    6,71    0,92   3,91     4,1%
W0  controllo      176,17    5,68    7,01    0,18   1,53    16,6%
```

**Monotono su ogni colonna.** Otto strati danno metà del beneficio di
diciassette: è il meccanismo, non rumore — ed era la controprova che il disegno
doveva fornire.

E la mediana va nella direzione **opposta**: 7,01 → 6,71 → 6,49. Ogni strato
mappato costa picco, perché per quello strato il PCIe è più lento della RAM, e
compra pavimento. **Il pavimento vince: +12,1% netto.**

L'ordine lavorava contro il risultato — W2 aveva la cache più calda di tutti,
essendo terzo — e la monotonia sopravvive lo stesso.

## Il meccanismo non è quello che sembrava

```
                 utilizzo GPU   WATT mediani
W1  zero-copy         54%          77,7
W0  controllo         42%          75,5
```

**Due watt di differenza.** La GPU non sta calcolando di più: l'utilizzo sale
perché i kernel restano residenti aspettando il PCIe, non perché macinino.

Il guadagno viene da un'altra proprietà della memoria mappata: **è pinned,
quindi quei 17 strati non faultano mai.** È il gate portato all'estremo —
minimo 4,73 contro i 2,87 che dava `VirtualLock`, e zero crolli invece di zero
crolli *dei soli 1.200 esperti bloccati*.

Conferma indiretta ma netta: nel braccio zero-copy **il gate non ha funzionato
affatto** (0,00 GiB bloccati, 2.621 `VirtualLock` fallite, perché la quota era
già esaurita dai 28,7 GiB mappati). Quindi zero-copy *senza* gate batte gate
*senza* zero-copy. Sono due modi di ottenere la stessa immunità, e il secondo
copre più memoria.

## L'errore corretto dall'utente

Avevo letto «79 W su 170» come prova di stallo sul PCIe. Senza un riferimento
non dimostrava niente — e il riferimento, misurato dopo, dice 75,5 W nel
controllo. La GPU tirava già quei watt. L'osservazione dell'utente («la GPU
lavorava pochissimo anche prima») era corretta e la mia inferenza no.

## Cosa dice per l'hardware

Se il guadagno fosse *calcolo* spostato sulla GPU, servirebbe più potenza. Non
è così. Il guadagno è **memoria che non può essere sfrattata**, e la quantità
mappabile è limitata dalla RAM di sistema, non dalla scheda.

Quindi la leva successiva non è una GPU più grande: è **quanti strati si
riescono a mappare** prima che il pinned affami i rimanenti. È il punto di
rendimento decrescente, e non l'abbiamo ancora trovato — 17 strati (28,7 GiB)
è il massimo provato e sta ancora salendo.
