# MANDATO — nel tronco ci sono DUE residenze host, e devono diventare una

LAVORO DI LETTURA E PROGETTO. **Non modificare sorgenti, non compilare, non lanciare run.**

  DA DIAGNOSTICARE:  ...\ds4-port     il TRONCO (port/upstream-substrate)
  DOVE FUNZIONA:     ...\ds4-p4a      il FORK. Sola lettura. **La stessa arena qui sta comoda.**
  DOVE SCRIVI:       `UNA_RESIDENZA.md` nella radice di `ds4-port`.

**Scrivi in append ogni fatto stabilito, non alla fine.** Formato:
`[HH:MM] STABILITO/IPOTESI/ESCLUSO — <affermazione>   (file:riga)`
Non usare git per scrivere.

## I TRE FATTI MISURATI, stasera, stesso modello e stessa arena da 30 GiB

```
FORK    con la sua arena          commit ~32 GB    arena resident 4423/4551
                                  cache esperti 306/320, ZERO sfratti backbone
                                  chunk 2,74 t/s   la macchina sta comoda

TRONCO  arena + --ssd-streaming   commit 47-60 GB  sistema a 63,7/63,9, satura
                                  la page cache di Windows crolla da 54,7 a 4,1 GB
                                  SEI ricarichi del modello DURANTE il decode
                                  chunk 0,66 -> 0,79 -> 0,42 -> 0,22, degrada sempre

TRONCO  arena SENZA streaming     NON PARTE, e non ha mai servito una richiesta.
                                  Prova a mappare il modello in VRAM e cresce senza
                                  fermarsi: 42,70 -> 47,76 -> 52,57 -> 52,84 GiB,
                                  poi muore. Macchina PULITA al lancio (preflight:
                                  VRAM 584 MiB, RAM 57 GB libera, zero daemon).
   ATTENZIONE, correzione: avevo scritto qui "commit 32,3 GB, come il fork" come
   prova della doppia residenza. E' FALSO: quei 32,3 erano un'istantanea presa
   MENTRE allocava ancora, non un valore a regime. Questo run non dimostra nulla
   sulla doppia residenza. I 15 GB di differenza fra fork e tronco restano
   misurati, ma la loro SPIEGAZIONE e' tutta da stabilire: e' la tua domanda (1).
                                  "CUDA model arena alloc failed for tensor-span:99
                                   (1792 MiB): out of memory" a offset 59808639808
```

## LA DIAGNOSI, da confermare o smentire

Nel tronco convivono **due meccanismi di residenza host che non si conoscono**:

```
upstream   sotto --ssd-streaming tiene i SUOI buffer degli esperti
noi        l'arena trapiantata tiene i SUOI 30 GiB pinnati
somma      ~47 GB, e su 64 GB di RAM sfratta la page cache che serviva il modello
```

Nel **fork** invece il meccanismo e' uno solo: lo streaming *e'* l'arena.

E il commento dell'adattatore lo ammette gia': l'arena residente
**«is deliberately not fed from the decode wrapper yet»** (`ds4_cuda.cu:26544`), e riceve
ranking solo dalla superficie di cold seed.

## COSA DEVI PRODURRE

**(1) Conferma o smentita**, con le righe: upstream sotto `--ssd-streaming` alloca davvero
buffer host per gli esperti, in aggiunta alla nostra arena? **Quanti e dove?** Se la mia
diagnosi e' sbagliata, dirlo subito e' l'informazione piu' utile.

**(2) Il punto di cucitura**: dove upstream, durante il decode, cerca un esperto sull'host.
Quella e' la chiamata che deve trovare **la nostra arena** invece della sua copia. Voglio la
funzione e la riga.

**(3) Come lo fa il FORK.** E' la via piu' rapida: due implementazioni, una funziona. Nel fork
chi serve l'esperto durante il decode, e come arriva all'arena? Il confronto fra i due percorsi
e' la risposta.

**(4) Il progetto della cucitura**, a passi verificabili. Non voglio codice: voglio **quale
chiamata va reindirizzata, cosa deve restare invariato, e cosa si rompe se sbagliamo**. In
particolare: upstream deve continuare a decidere cosa sta in VRAM — quello funziona — e va
cambiato solo **dove prende i byte quando non ci sono**.

**(5) Il criterio di verifica**: quale riga di log, con quale valore, dimostrerebbe che la
residenza e' diventata una sola. Il segnale ovvio e' il commit del processo a ~32 GB invece di
47 **con lo streaming acceso**, ma se c'e' un contatore migliore dimmelo.

## UN VINCOLO E UNA TRAPPOLA

Il vincolo dell'utente vale sempre: *i meccanismi di promozione e pruning del modello standard
restano INVARIATI*. La cucitura si affianca.

E la trappola: nel tronco **non esiste piu' la contabilita' `[host-pin]`** che nel fork somma
ogni allocazione pinnata per categoria (`total_live_mib`). L'abbiamo portata col blocco 2 ma su
questo percorso non stampa nulla. **Se scopri perche', dillo**: senza quel contabile non
possiamo attribuire i 15 GB, e stasera ho dovuto dedurli per differenza.

Ogni affermazione con file:riga. Italiano.
