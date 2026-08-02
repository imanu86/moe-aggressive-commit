# llama.cpp ci batte del 64% in decode, e non ha nessuna cache esperti

Misurato il 2026-08-02. Confronto a variabile singola: **stessa macchina, stesso
file** `DS4-0731-IQ2XXS.gguf` (80,76 GiB), **stesso ctx** 10000, **stesso prompt**
(sha `38f6ec5ee5403f59`, verificato su entrambi), **stessi 1500 token**.

## I numeri

**A VRAM SPORCA** (la prima misura, con ~2,2 GB non rilasciati da un processo
ucciso a forza):

```
llama.cpp b10227  -ngl 99 -cmoe    END2END 5,397    decode 6,16 t/s   162 ms/token
DwarfStar + porto                  END2END 3,533    REGIME 3,75       237-288 ms/token
llama.cpp b10227  -ngl 0           END2END 2,665
```

**A VRAM PULITA** (dopo il riavvio, base 742 MiB, entrambi rimisurati):

```
llama.cpp b10227  -ngl 99 -cmoe    END2END 5,694    decode 6,61 t/s   151 ms/token
DwarfStar + porto                  END2END 3,989    decode 4,13       242 ms/token
                                                    REGIME 4,37
```

Il divario **resta**: ~60% in decode. Non era un artefatto della memoria sporca.
Entrambi migliorano pulendo, ma noi di piu' (+16,5% contro +5,5%), perche'
occupiamo quasi tutta la scheda.

`-cmoe` = **tutti** gli esperti sulla CPU. Nessuna residenza, nessuna cache,
nessuna ammissione, nessuno sfratto. Solo: backbone in VRAM, esperti letti dalla
RAM.

Noi facciamo la stessa divisione **piu'** una cache dinamica da 246 slot scelti
per calore, con bussate, isteresi, orologio e ledger delle promozioni. E siamo
indietro del 64%.

## Dove sta il divario: NON HANNO UN TRASPORTO

**Correzione del 2/8 pomeriggio.** Avevo scritto che leggono a 9,7 GB/s contro i
nostri 3,25. **E' sbagliato: quei byte sul bus non li mandano affatto.**

Con `-cmoe` i tensori degli esperti stanno in memoria host, e ggml esegue
l'operazione **dove sta il dato**: gli esperti li calcola la CPU. Lo si vede dal
carico -- durante il loro run la CPU sta al **49%**, la nostra al 5-7%.

```
noi      258 esperti/token portati in VRAM   1,578 GiB sul bus, 70,5% del tempo in read_gate
loro     258 esperti/token calcolati in RAM  zero bus, la CPU lavora
```

Non e' un trasporto piu' veloce: e' **spostare il calcolo verso il dato** invece
del dato verso il calcolo. E' una differenza architetturale, non di
sintonizzazione.

Nota: la nostra falsificazione della "lane CPU" (G132, -47 ms/token) **non copre
questo caso**: era una route su cinque, non il calcolo completo degli esperti.

La prova che non e' la politica: **loro non ne hanno una**. llama.cpp offre solo
collocazione statica (`-cmoe`, `-ncmoe N` per strato, `-ot` per pattern) e
nessuna residenza guidata dalla frequenza.

## Cosa NON dimostra

- **Non e' il loro massimo.** Il loro log avvisa: *"tensor overrides to CPU are
  used with mmap enabled - consider using --no-mmap for better performance"*.
- Il loro **prefill e' molto peggiore**: 34 s per 43 token (1,26 t/s), quasi
  certamente page fault a freddo. Il nostro prefill e' molto piu' rapido.
- Un run per configurazione, come tutto il resto della giornata: la varianza fra
  run non e' ancora misurata.
- `-ncmoe N` (residenza statica per strato) non e' ancora stata provata: e' il
  confronto piu' informativo, statica-per-strato contro dinamica-per-calore.

## Perche' conta

Tutta la giornata e' stata spesa sulla residenza: nove leve provate, due vinte,
da 2,70 a 3,75. Il divario vero era altrove, e questo confronto lo localizza in
un punto solo — **come i byte degli esperti arrivano dalla RAM**.

La domanda giusta da qui in avanti non e' "quale politica di cache", e'
**"perche' leggiamo a 3,25 GB/s dove ggml legge a 9,7"**.

La domanda l'ha posta l'utente: *"abbiamo costruito il porting windows sulla
versione dwarfstar... capiamo questa cos'ha rispetto al motore ufficiale?"*
