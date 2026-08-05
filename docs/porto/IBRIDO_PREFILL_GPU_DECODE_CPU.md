# L'ibrido: prefill sulla GPU, decode sulla CPU, stessi byte

5 agosto 2026. Il risultato piu' grande della campagna, e l'idea e' dell'utente.

## Da dove nasce

Con tutti e 43 gli strati mappati la CPU segnava **1-6%** e la GPU 99%. Sua
osservazione: *«la cosa che vedo e' che la cpu lavora pochissimo!»* e poi
*«switchare a caldo in base al fatto che sei in decoding o in prefill sarebbe
il top di due mondi»*.

Aveva ragione, e la curva completa lo mostrava gia':

```
strati mappati    decode    prefill
      0            6,91      6,94
     14            6,50      9,68
     30            6,13        -
     43            5,95     15,01
```

Monotona su tutta la scala: **ogni strato mappato costa decode e compra
prefill**. Il prefill ha batch grande e il PCIe si ammortizza; il decode ha
batch 1 e la RAM batte il PCIe. Due regimi opposti, e finora dovevamo sceglierne
uno.

## Perche' si puo' fare senza copiare niente

`cudaHostAlloc(cudaHostAllocMapped)` piu' `cudaHostGetDevicePointer` sotto
indirizzamento unificato restituiscono **lo stesso indirizzo**:

```
host=0000000204C00000  dev=0000000204C00000  ->  UVA SI
```

Quindi CPU e GPU vedono gli stessi byte allo stesso indirizzo. Non c'e' niente
da spostare: cambia solo **chi esegue l'operazione**, che e' puro scheduling.

## L'implementazione, due punti

**1. `is_host` a true.** Il backend CPU accetta il buffer, perche'
`ggml_backend_cpu_device_supports_buft` guarda esattamente quello. E CUDA
continua ad accettarlo lo stesso, perche' `ggml_backend_buft_is_cuda` confronta
il **puntatore a funzione** di `get_name`, che condividiamo di proposito col
tipo CUDA normale.

Accettato da entrambi.

**2. `supports_op` che rifiuta.** Non basta il punto 1: i pesi stanno in un
buffer che CUDA accetta, quindi lo scheduler li assegna a CUDA per
**collocazione** e non arriva mai a chiedersi se convenga. Serve declinare
esplicitamente `MUL_MAT_ID` con batch < 2 sui pesi mappati, e allora ripiega
sulla CPU -- l'unica altra che accetta quel buffer.

Provato con il solo punto 1: decode 5,99, cioe' **niente**. Con entrambi: 6,99.

**Guardia**: `g_cuda_mapped_uva`. Se host e dev non coincidessero, la CPU
leggerebbe un puntatore device; in quel caso l'ibrido si spegne da solo.

Due manopole: `LLAMA_MAPPED_IBRIDO=1` per accenderlo,
`LLAMA_MAPPED_IBRIDO_SOGLIA` per spostare il confine (difetto 2).

## Il dato

```
                     prefill    decode
 0 mappati            6,94      6,91
43 mappati           15,01      5,95
IBRIDO               15,31      6,99
```

**Batte entrambi gli estremi**, non li media. Su un turno di chat da 300 token
di prompt e 200 di risposta:

```
 0 mappati    72,1 s
43 mappati    53,6 s
IBRIDO        48,2 s        -33% sul primo
```

## Il contorno che l'ha reso possibile

**I due banchi da 16 GB** (che l'utente aveva gia' in casa) portano la macchina
a 95,9 GiB e fanno entrare i 72,7 GiB di esperti. Da soli hanno comprato il
**prefill x4,2** e lasciato il decode dov'era -- quinta conferma che il tetto
del decode e' orchestrazione. Ma senza di loro l'ibrido non sarebbe stato
possibile: 43 strati mappati non entravano.

**`--no-mmap`**, obbligatorio quando si pinna. Con mmap gli stessi byte stanno
due volte -- pagine del file piu' buffer pinnato -- e servono 153 GiB su 96: il
caricamento non finiva in quattro minuti. Senza: 82 secondi. Ma con **zero**
mappati mmap e' il percorso efficiente (i tensori SONO le pagine, nessuna
copia), quindi la regola vale solo nel suo regime. Ieri sera avevo concluso il
contrario misurando nell'altro.

**Lo stack a 64 MiB.** Con 1 MiB llama.cpp va in `0xC00000FD` (stack overflow in
ntdll) su grafi molto frammentati -- 34.054 nodi e 204 split. Si rimette con
`editbin /STACK:67108864`, e va rifatto dopo ogni link.

## Cosa e' stato falsificato per strada

**Il ginocchio non era fame di page cache.** Ieri avevo attribuito il declino
oltre i 14 strati alla RAM satura. Con 23 GiB di margine e zero paging, 30
strati vanno comunque peggio di 14. Il declino e' intrinseco: PCIe contro RAM.

**Il PP col mini-PC e' morto**, con tre misure invece di una stima: 0,26 t/s
con `-ot` e zero-copy (204 split), 1,23 con la distribuzione automatica (67),
e 743 split con blocchi contigui. Ogni piazzamento a mano peggiora: `-ot`
combatte con lo scheduler. Il migliore resta 5 volte peggio del locale, e il
motivo e' la geometria -- tre device con la CPU in mezzo, contro i due di chi
lo usa con successo.

## Cosa resta aperto

**La frequenza della RAM.** I 96 GB girano a 2133 contro i 3600 di prima:
-41% di banda. Finora l'avevo escluso perche' il decode stava sulla GPU, ma
l'ibrido lo manda sulla **CPU**, che legge dalla RAM. Adesso e' la variabile
piu' probabile fra quelle rimaste.
