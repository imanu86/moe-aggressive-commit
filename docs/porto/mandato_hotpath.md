# MANDATO — perche' l'arena portata non si aggancia al percorso caldo

LAVORO DI LETTURA E DIAGNOSI. **Non modificare sorgenti, non compilare, non lanciare run.**

  DOVE LEGGI:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-port
               il TRONCO portato (branch port/upstream-substrate, HEAD fb57329).
               E' il codice da diagnosticare, non un riferimento.
  RIFERIMENTO: ...\ds4-p4a   il nostro fork, dove la stessa arena FUNZIONA. Sola lettura.
  DOVE SCRIVI: `PERCHE_C_NON_SI_ACCENDE.md` nella radice di `ds4-port`.

**Non usare git per scrivere.**

## SCRIVI IN CORSO D'OPERA, NON ALLA FINE

**Ogni volta che stabilisci un fatto, aggiungilo subito in append al rapporto**, con la riga di
codice. Non aspettare di aver capito tutto: un'analisi lunga che arriva intera dopo un'ora vale
meno di tre fatti certi consegnati mentre lavori.

Formato di ogni voce, corto:

```
[HH:MM] STABILITO/IPOTESI/ESCLUSO — <affermazione>   (file:riga)
```

Se scopri che una pista e' chiusa, **scrivi anche quella**: sapere cosa e' escluso vale quanto
sapere cosa e' vero.

## IL FATTO

Il tronco portato gira, ma **la nostra politica non si accende**. Run del 1/8, 200 token,
`ctx=8000`, modello reale da 81 GB, con queste variabili impostate:

```
DS4_CUDA_DYNAMIC_ARENA_GB=30
DS4_CUDA_PREFILL_MASS_OBSERVE=1
DS4_CUDA_VRAM_EXPERT_CACHE=1
```

Prove che sono state **ignorate**:

```
processo         2,3 GB        con l'arena host pinnata sarebbero ~32
RAM libera       50,0 GB       durante lo stesso run sul FORK, che riempie 30 GiB, era 46
log del server   ZERO righe contenenti "arena", "expert cache", "tiering"
                 (il fork ne stampa decine: [arena] begin, [arena-wrap-profile],
                  [iq2-expert-cache-size], [vram-prio], [prefill-mass] ...)
velocita'        identica al run SENZA quelle variabili: 2,34 contro 2,28 chunk t/s
```

Il run si comporta **esattamente** come il substrato upstream nudo.

## L'INDIZIO CHE AVEVO E NON HO SEGUITO

La fixture del blocco 4 stampa da sempre:

```
ds4: [arena] allocated mapped-pinned=0.000 GiB slots=3 slot_bytes=192 hot_path=disconnected
```

L'ho letto come una proprieta' **voluta** del blocco ("l'arena si alloca ma non e' ancora nel
percorso caldo, ci pensa un blocco successivo"). **Nessuno ha mai verificato chi la colleghi
dopo**, e il porto e' arrivato a "compila e le fixture passano" senza provarlo su un modello
vero.

## LA DOMANDA, ed e' UNA

**Chi dovrebbe portare `hot_path` da `disconnected` a collegato, e perche' non succede?**

In particolare:

1. **Dove viene deciso** `hot_path=disconnected`, e quale condizione lo cambierebbe.
2. **`DS4_CUDA_DYNAMIC_ARENA_GB=30` viene letta?** Se si', cosa fa il codice subito dopo, e
   dove si ferma. Se la variabile e' letta ma il risultato scartato, **il punto dove viene
   scartato e' la risposta.**
3. **`DS4_CUDA_VRAM_EXPERT_CACHE=1`**: nel blocco 8 `route_transaction_ready()` e' stato portato
   a `true`. Verifica che lo sia **in questo binario** e, se si', cosa manca ancora.
4. **Il confronto col fork**: nel fork la stessa arena si aggancia. **Cosa fa il fork che il
   tronco non fa?** E' la via piu' rapida alla risposta: due implementazioni, una funziona.
5. Se manca proprio un pezzo di cablaggio — cioe' se nel porto qualcuno ha scritto il
   sottosistema ma **non l'ha mai chiamato dal decode** — dillo chiaramente e indica **quale
   chiamata manca e dove andrebbe**.

## COSA NON MI SERVE

Non voglio un inventario di tutto il sottosistema: ce l'ho gia' nei rapporti dei blocchi
(`PORT_BLOCK4_ARENA.md`, `PORT_BLOCK6_VRAMCACHE.md`, `PORT_BLOCK7_TIERING.md`,
`PORT_BLOCK8_ROUTEWORKER.md`, tutti nella radice). Voglio **il punto preciso in cui la catena
si interrompe.**

Ogni affermazione con file:riga. Se e' un'ipotesi, scrivi che lo e'. Italiano.
