# La testa di Markov è assolta: i 538 ms erano verifica MoE-CPU

3 agosto 2026, pomeriggio. Ribalta [MARKOV_IL_COLPEVOLE](MARKOV_IL_COLPEVOLE.md)
del mattino. Il mandato era «riparare l'implementazione della testa» (concat
quadratico, argmax serializzante, tensori grandi). Nessuno dei tre sospetti
regge: **la testa costa ~2 ms, non 538, e non c'è niente da riparare.**

## Il metodo: misurare le fasi, non dedurle

I «538 ms della testa» non erano una misura: erano `ciclo − verifica`, con la
verifica stimata da una ripartizione 78/22 (P=184, T=52 ms/token) presa dal
prefill di 3.374 token — un regime diverso dal verificarne 6.

Due strumenti nuovi, entrambi di misura diretta:

1. **Micro-bench isolato** (`.microbench/markovhead/`): replica esatta del
   sottografo di `build_dspark_markov_head` (get_rows f16 + mul_mat q2_K +
   add su vista + concat accumulativo + argmax concatenato + testa di
   confidenza, 5 iterazioni, n_vocab 129.280) su `ggml_backend_sched`
   CUDA+CPU, con le varianti che triangolano i tre sospetti.

2. **DSPARK_PROF=1** (commit `236801b` del fork): cronometri per fase
   (build / alloc / set_inputs / compute / synchronize) dentro
   `process_ubatch`, per ogni contesto, draft e bersaglio distinti.
   Run appaiati P1/P2, 120 token, stessa sessione, unica variabile
   `DSPARK_NO_MARKOV`.

## Il dato

Micro-bench (mediane su 20 esecuzioni; REBUILD = build+alloc+compute a ogni
giro, come fa il server):

```
variante                          nodi  split   REUSE     REBUILD
full     (replica fedele)           73     3   2,06 ms    2,07 ms
noconf   (senza confidenza)         34     2   1,94       1,95
nochain  (senza catena argmax)      77    11   2,01       2,02
treecat  (concat ad albero)         73     3   2,05       2,13
pavimento (tocca solo i logit)       1     1   0,04       0,03
```

Tutto il sottografo — concat accumulativo, catena argmax, 5×517 KB di
intermedi — vale **2 ms**. I tre sospetti del mandato sono falsificati in
un colpo.

Server, run appaiati (differenze fra dump cumulativi, prompt scorporato):

```
COSTO UNITARIO                P1 testa ACCESA   P2 testa SPENTA
verifica bersaglio (6 pos)      954–1.203 ms      694–1.060 ms
decode bersaglio (1 pos)          289 ms            260 ms
blocco draft (5 pos)               41,6 ms           46,3 ms
encode+inject draft                 0,4 ms            0,4 ms
build+alloc blocco draft            1,1 ms            0,9 ms
eval end-to-end                   470,8 ms/tok      660,3 ms/tok
accettazione                        0,503             0,167
```

Il blocco draft con la testa è **più veloce** di quello senza (41,6 contro
46,3): la differenza vera (+2 ms dal micro-bench) sta dentro il rumore di
contesa CPU. La chiusura contabile di P1: verifica 1.076×49 + draft ~1.500 +
host ~2.300 = 56.500 ms = eval time esatto. **Non c'è nessun buco da 538 ms.**

## Dove stavano davvero i 538 ms

Due errori della contabilità del banco, entrambi nel braccio di confronto:

1. **La verifica era sottostimata di ~500 ms.** Misurata direttamente:
   ~950–1.080 ms per 6 posizioni, contro i 495 della formula. Il costo
   marginale per token in verifica è T ≈ 133 ms (da 289 ms a 1 posizione a
   954 a 6), non 52: **l'ammortamento 78/22 misurato in prefill non esiste
   nel regime a 6 posizioni**, perché su MoE-CPU ogni posizione del blocco
   attiva esperti in gran parte distinti, e i byte letti dalla RAM crescono
   quasi linearmente con le posizioni.

2. **Il divisore dei cicli era sbagliato nel braccio spento.** `cicli =
   generati/lunghezza` conta le chiamate di draft (251 in W2), ma le
   verifiche vere sono meno (~164): con accettazione 0,2 i draft si troncano
   (len 1,99 su blocchi da 5). Dividendo per 251, il ciclo di W2 appariva da
   674 ms; il ciclo vero è ~1.030–1.100 ms — **quasi identico a W1**.

Il ciclo costa ~1.100 ms in entrambi i bracci ed è verifica per l'85–90%.
La testa non sposta il costo del ciclo: sposta **quanti token il ciclo
produce** (avanzamento 4,4 contro 1,2–1,8). Per questo W1 batte W2 di 231
ms/token: accettazione, non velocità del draft.

C'è anche un termine secondario reale: la verifica di token sensati (P1)
costa ~145 ms in più della verifica di spazzatura (P2, media 931 contro
1.076) — token diversi attivano più esperti distinti. Anche questo finiva
nel conto «della testa».

## Cosa NON fare, adesso

- **Non ottimizzare la testa.** Il rimedio upstream (build-once-per-block,
  PR ggml-org/llama.cpp#25173) vale ~2 ms su un ciclo di 1.100: <0,2%.
  La sezione «quanto varrebbe ripararla» di MARKOV_IL_COLPEVOLE (+20%,
  +110% con sovrapposizione) discendeva dal draft fantasma da 872 ms e
  va cestinata.
- **Non sovrapporre draft e verifica aspettandosi il +110%**: il draft vero
  è ~50 ms/ciclo, la sovrapposizione può nasconderne al massimo il 4-5%.

## La leva vera, se esiste

Il collo è la **verifica MoE-CPU a batch piccolo**: 6 posizioni costano 4
volte una. I ~133 ms/token marginali sono letture RAM di esperti distinti
(~40 esperti/strato a 6 posizioni contro ~8 a 1). Le direzioni che questa
misura apre (da misurare, non da assumere):

- alzare l'accettazione (più avanzamento per la stessa verifica): è ciò che
  la testa già fa gratis;
- ridurre le posizioni verificate quando la confidenza è bassa
  (`--spec-draft-n-max` adattivo): meno esperti distinti per passata;
- qualunque cosa riduca i byte di esperti per passata di verifica.

## Traccia dei run

```
P1/P2 primo giro   prof_P1_markov_ON.log / prof_P2_markov_SPENTA.log (profiler solo draft)
P1/P2 secondo giro idem, profiler draft+bersaglio, dump DSPROF cumulativi
micro-bench        .microbench/markovhead/markov_bench.cpp + build.bat
fork               D:\llama-dspark dspark-dsv4, commit 236801b (strumentazione)
ledger             LLAMA_P1_prof_markovON / LLAMA_P2_prof_markovOFF
```
