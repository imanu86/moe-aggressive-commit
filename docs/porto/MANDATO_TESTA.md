# MANDATO — la testa che indovina il token dopo (RICERCA)

*Scritto il 6/8/2026 sera. Autosufficiente. L'origine è l'intuizione
dell'utente del 5/8 («il punto è sempre parallelismo... una testa che
parallelizzi è il pezzo finale», registrata in
`reap-loop/docs/INTUITION_REGISTER.md`, commit 925b315) più il verdetto del
6/8 che, chiuse tutte le altre strade, lascia aperta SOLO questa — e le dà una
soglia numerica.*

## L'obiettivo, in una riga

Una testa piccola (~90 MB), addestrata **sul modello congelato** (i 284
miliardi non si toccano), che proponga il token successivo con **p1 > 0,56 sul
carico d'uso**: sopra quella soglia una catena di profondità 1 (corrente +
proposta nello stesso passaggio) produce più di quanto costa, e il decode
supera il tetto della strada-memoria.

## Da dove viene lo 0,56 — e da cosa dipende (IMPORTANTE)

Una catena di profondità 1 mette **due posizioni consecutive** nello stesso
passaggio. La loro unione di route è ~**446 esperti** (misurata: 446 sui
consecutivi; NON i 343 dei rami stessa-posizione — quello era la *larghezza*,
che non produce token). Contro i 380 slot della cache l'unione sborda, i colpi
misurati a batch 2 sono **17,3%**, e il passaggio costa:

```
52,7 (pavimento) + 16,3 (calcolo GPU) + 99,8 (trasporto a 17,3% di colpi)
  = 168,8 ms  =  1,56 × il token normale (108)   →   serve  1 + p1 > 1,56
```

**La soglia è funzione dei colpi della cache in quel regime:**

```
colpi 17,3% (misurato oggi a np=2)   →  p1 > 0,56
colpi 44%   (se il regime a 2 token tenesse quelli di np=1)  →  p1 > 0,26
```

Due conseguenze: (a) c'è un margine di collaborazione con il cantiere OVERLAP
(la capienza/politica della cache muove la TUA soglia — il punto di contatto
passa dal coordinatore); (b) il 17,3% è misurato su **due slot separati**
(np=2): per la catena vera — un grafo solo, stesso contesto — potrebbe essere
un po' meglio, ma l'unione 446>380 sborda per costruzione. Misurarlo è uno dei
primi bracci.

## I numeri di partenza (misurati)

```
0,26    p1 degli n-grammi sul carico CODICE (P(≥1 accettato) = 192/733)
0,076   idem su PROSA — l'accettazione ha un forte pedice di dominio
        (la CACHE invece no: −1,6% fra codice e prosa, misurato)
0,594   recall di una RETTA sugli stati nascosti nel predire la ROUTE
        del token dopo (1.173 campioni) — è la route, NON il token:
        è un pavimento di apprendibilità, non un p1
0,767   p1 prima-posizione del drafter DSpark ADDESTRATO — ma su
        TRADUZIONE, e su DGX. Mai misurato sul nostro carico
0,0017  accettazione del drafter DSpark Q2K con lo spec di llama.cpp
        sul nostro carico: sospetto FILE ROTTO vs METODO mai separato
        (braccio "Q2Kfix" progettato e mai eseguito)
```

## Il programma, dal più economico

1. **Definire la metrica una volta per tutte**: p1 = accettazione greedy per
   posizione (temperatura 0, il bersaglio verifica). Con la verifica
   speculativa la sequenza finale è IDENTICA alla greedy per costruzione: la
   bit-esattezza qui è gratis, il cancello è solo sul meccanismo.
2. **Chiudere file-vs-metodo sul drafter DSpark** (run GPU, breve): se lo
   0,0017 era il file (quantizzazione della bozza) e il drafter vero vale
   0,3-0,5 sul nostro carico, il gap verso 0,56 si stringe molto e la strada
   diventa «migliorare», non «inventare».
3. **Misurare i colpi della catena vera** (run GPU, breve, col cantiere
   overlap che oggi ha la cache batch>1 funzionante): fissa la TUA soglia
   fra 0,26 e 0,56.
4. **Testa su stati nascosti (stile EAGLE/Medusa)**: il modello ha già dato
   il segnale (retta al 59,4% sulla route). Validare la pipeline di
   addestramento su un MoE piccolo PRIMA di toccare il grande:
   `reap-loop/configs/models/` ha granite_1b_a400m e olmoe_1b_7b, e
   `llama-finetune` è nel build. Dataset dal carico d'uso: i prompt e le
   uscite esistono (`D:\ds4_work\llama_run\par_*.req.json`, output catalogati,
   traccia da 1.678 token con stati nascosti di 43 strati in
   `D:\ds4_work\dump`).
5. **Solo dopo**: generazione di un dataset grande dal modello vero (run GPU
   lunghe → coordinatore) e addestramento della testa vera.

## Avvertenze strumentali (errori già pagati — non ripagarli)

- **Il router di DSV4 non è `top-k(W·h + bias)`**: un ricostruttore così
  fedele al 90,4%, non al 100% (punteggio sigmoide con selezione a gruppi,
  node-limited). Se ricostruisci route invece di leggerle dalla traccia,
  valida il ricostruttore PRIMA di usarlo.
- **La traccia esistente è di dominio CODICE** (prompt NeuraForge). Per la
  testa è il dominio giusto (è il carico d'uso), ma ogni numero che ne esce
  porta quel pedice.
- **`ids` (ffn_moe_topk) è una VISTA CON STRIDE** nei dump: le prime 6 righe
  di un argsort su 256. Letta come contigua dà spazzatura plausibile.
- **La lentezza non è l'unico modo di fallire**: un difetto nel meccanismo di
  proposta può essere *veloce e corrotto*. Il cancello è sempre l'uscita
  identica alla greedy, verificata con SHA su testo.
- Lo 0731 **non ha la testa MTP** nei pesi (la PR upstream #25784 la aggiunge
  per modelli che la portano; il nostro GGUF no). La testa va addestrata,
  non estratta.

## Cosa NON rifare (chiuso con misure, 6/8)

Speculazione batch-8 (unione route esplode), drafter CPU, lane G132, DSpark
con spec llama.cpp (salvo il punto 2 sopra), Jacobi/lookahead (pareggio
impossibile per aritmetica), **catena K=2 a n-grammi** (p1 0,26 < 0,56),
**larghezza pura** (K candidati nella stessa posizione producono al massimo 1
token per definizione), **Jacobi sugli strati** (warm start 27,1% contro il
~90% necessario, e il profilo peggiora proprio dove l'errore si propaga).
Dettagli: `docs/porto/JACOBI_VERDETTO.md` e ledger
(`docs/porto/LEDGER_RUN.tsv`, righe LLAMA_ALBERO_UNIONE,
LLAMA_WARM_START_STRATI, LLAMA_CURVA_BATCH_VERA).

## Protocollo macchina e report

**`docs/porto/PROTOCOLLO_MACCHINA.md`, vincolante.** Il lavoro offline
(analisi sulle tracce, disegno, script) è libero; **qualunque cosa tocchi GPU
o RAM in grande — build, serving, finetune anche piccolo — passa dal
coordinatore**: `[RICHIESTA MACCHINA]` a
titolo "DS4 L3", da risolvere con list_sessions, si parte dopo `[MACCHINA A TE]`.
Report continui con i numeri. Il dubbio si passa all'altra sessione. Se serve
un worktree per compilare, chiederlo al coordinatore (`D:\llama-testa`, non
ancora creato).
