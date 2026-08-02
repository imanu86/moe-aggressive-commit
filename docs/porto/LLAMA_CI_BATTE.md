# llama.cpp ci batte del 64% in decode, e non ha nessuna cache esperti

Misurato il 2026-08-02. Confronto a variabile singola: **stessa macchina, stesso
file** `DS4-0731-IQ2XXS.gguf` (80,76 GiB), **stesso ctx** 10000, **stesso prompt**
(sha `38f6ec5ee5403f59`, verificato su entrambi), **stessi 1500 token**.

## I numeri

```
llama.cpp b10227  -ngl 99 -cmoe    END2END 5,397    decode 6,16 t/s   162 ms/token
DwarfStar + porto                  END2END 3,533    REGIME 3,75       237-288 ms/token
llama.cpp b10227  -ngl 0           END2END 2,665
```

`-cmoe` = **tutti** gli esperti sulla CPU. Nessuna residenza, nessuna cache,
nessuna ammissione, nessuno sfratto. Solo: backbone in VRAM, esperti letti dalla
RAM.

Noi facciamo la stessa divisione **piu'** una cache dinamica da 246 slot scelti
per calore, con bussate, isteresi, orologio e ledger delle promozioni. E siamo
indietro del 64%.

## Dove sta il divario: il TRASPORTO, non la politica

Con 1,578 GiB di esperti per token (misurato col profilo del worker sul nostro
motore):

```
noi      3,25 GB/s     misurato: [worker-prof] read_mb_s=3249
loro     9,7 GB/s      dedotto: 1,578 GiB / 162 ms
```

Circa **tre volte**. E il 70,5% del nostro tempo per token e' `read_gate`, cioe'
l'attesa di quelle letture.

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
