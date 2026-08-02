# Come ragiona il modello, e perche' la nostra residenza non poteva funzionare

Misurato il 2026-08-02 sul tracciato `[route-ids]` di DeepSeek-V4-Flash 2-bit
(`DS4-0731-IQ2XXS.gguf`), 43 strati, 6 esperti scelti su 256 per strato, ctx
10000, braccio G. Analisi in `router.py`, **solo la fase di decode** — il prefill
ha una forma di accesso completamente diversa e va separato.

## Il numero che falsifica tutto

```
POLITICHE su 72.240 accessi di decode, 181 slot

LRU  (cio' che usiamo)      0,0 %
FIFO                        0,0 %
casuale                    11,1 %
insieme caldo statico      28,2 %
Belady (vede il futuro)    47,8 %
cache infinita             90,3 %
```

**LRU e FIFO prendono zero colpi.** Non pochi: zero.

Non e' un difetto di implementazione, e' la patologia da manuale della recency su
un accesso ciclico piu' lungo della cache. Il modello tocca **258 esperti
distinti a ogni token** — sempre esattamente 258, mai uno di piu' o di meno — e la
cache ne tiene 181. Quando il modello torna su un esperto, ne ha toccati 258 nel
frattempo e la LRU l'ha gia' sfrattato per far posto proprio a quelli.

Su questo schema la LRU non e' una politica mediocre: **e' la peggiore
costruibile**, perche' sfratta con precisione cio' che servira' subito dopo.

## La nostra politica rende come un dado

Il runtime misura ~10% di colpi (`vram_hits=38.427` su ~387.000 accessi in 1500
token). La sostituzione **casuale** simulata ne fa 11,1%.

Tutta la macchina di mass-LFRU, hysteresis, `clock_calls`, `replacement_budget` e
bussate di ammissione produce il risultato di un dado. Non peggio — ma nemmeno
meglio, e costa decisioni sul cammino critico di un runtime che sappiamo essere
orchestration-bound.

## Il riuso c'e', ed e' enorme

Con cache infinita i colpi sarebbero il **90,3%**: solo un accesso su dieci e' a
un esperto mai visto prima.

Non e' un modello che cambia idea di continuo. E' un modello che riusa moltissimo,
ma **su distanze temporali piu' lunghe di quanto la nostra cache sappia
ricordare**. La residenza e' l'attrezzo giusto; la politica e' quella sbagliata.

## Le altre misure

```
esperti distinti per token       258   (mediana = min = max: e' una costante)
Jaccard fra token consecutivi  0,232
esperti NUOVI a ogni token       161 su 258
                                       -> con residenza perfetta si evita
                                          il 37,6% dei caricamenti a un passo

i  181 piu' caldi coprono il 27,2% degli accessi
i  320 piu' caldi coprono il 37,4%
i  512 piu' caldi coprono il 46,8%
i 1024 piu' caldi coprono il 62,3%

insieme di lavoro     1 token ->   258 esperti distinti
                      4 token ->   687
                     16 token ->  1773
                     64 token ->  3980
                    256 token ->  6803
```

## Quanto varrebbe piu' capienza (Belady)

```
 181 slot  ->  47,8 %      <- quello che abbiamo oggi
 274 slot  ->  56,1 %      <- quanti ne aveva il fork
 320 slot  ->  59,0 %
 512 slot  ->  67,3 %
1024 slot  ->  77,8 %
```

La capienza rende, ma **meno della politica**: passare da 181 a 320 slot vale
+11 punti di tetto; passare da casuale a insieme caldo statico ne vale +17 subito,
e non costa un byte di VRAM.

## Cosa ne segue

L'insieme caldo statico e' anche **piu' semplice** di cio' che abbiamo: si misurano
le frequenze su un campione, si pinnano i piu' caldi, e non si decide piu' nulla
per accesso — niente ledger, niente scelta della vittima, niente bussate. Su un
runtime orchestration-bound questo vale due volte: meglio come tasso di colpi, e
meno lavoro sul cammino critico.

## I limiti di questa misura, da rispettare

- **Un prompt solo.** L'insieme caldo e' quello di questo dominio. La memoria
  `collapse-root-cause-domain-mismatch` dice gia' che il disallineamento fra mask
  e dominio e' la radice del collasso sui domini larghi: la versione onesta non e'
  "pinna questi 181 per sempre", e' "l'insieme caldo va misurato per dominio, o
  adattato lentamente".
- **Il verdetto sulla recency invece non dipende dal dominio**: 258 > 181 e'
  aritmetica.
- Belady non e' implementabile: e' il tetto, non un obiettivo.
- `casuale` usa un generatore lineare con seme fisso: e' riproducibile ma e' un
  campione singolo.
- Il tracciato costa: 43 righe per token su `stderr` sotto mutex. **I run con
  `DS4_EXPERT_TIERING_LOG_IDS=1` non misurano la velocita'.**

## Come rifarla

```bash
# 1. il run che produce il tracciato (NON misura la velocita')
.\docs\porto\braccio.ps1 -Arm G -Tokens 600 -Ctx 10000 `
    -Override @{ 'DS4_EXPERT_TIERING_LOG_IDS' = '1' }

# 2. l'analisi
python docs/porto/mappa/router.py <log> 181
```

Precondizione della traccia, verificata: `log_ids` sta dentro
`if (config.publish_runtime_counters)`, e quello e'
`runtime.mode != tiering_off` (`vram_expert_cache.cpp:995`). Serve quindi
`DS4_EXPERT_TIERING=enforce` oppure `observe`, altrimenti la variabile e' accesa
e non stampa niente.
