# Revisione critica della testa speculativa

*7 agosto 2026. Revisione solo documentale: nessuna run eseguita. Sono stati
letti il piano, la metrica, l'aritmetica e gli script di estrazione, ridge,
adapter e predizione di stato presenti nel cantiere.*

## Verdetto in una pagina

La strada **testa senza stato** non è condannata. È anzi l'unica forma di
drafter compatibile con il costo osservato di `process()`. È però da fermare
**l'architettura candidata così com'è scritta**:

```text
h(t) -> adapter -> stato predetto -> output_norm + lm_head congelate -> t+2
```

Ha tre difetti sostanziali.

1. Il bersaglio MSE usato oggi, `output.weight[token_vero]`, **non è lo stato
   futuro vero**. È una riga del classificatore. Non c'è motivo perché la
   rappresentazione che precede la lm_head debba coincidere con quella riga;
   molte rappresentazioni diverse producono lo stesso argmax. RMSNorm rende
   l'identificazione ancora meno giustificata. La ridge interpola bene un
   sistema sottodeterminato: questo prova che c'è segnale, non che il bersaglio
   geometrico sia corretto.
2. La testa non riceve il token `t+1` appena scelto dal bersaglio. È proprio
   l'informazione che EAGLE, Hydra e il modulo MTP di DeepSeek usano per
   eliminare l'ambiguità della transizione futura. Passarglielo **non introduce
   stato**: è un ID già calcolato, non una KV da mantenere.
3. `testa_adapter.py` distilla la posizione sbagliata. Le etichette dure sono
   spostate a `t+2`, ma i soft target sono calcolati con
   `rms(ffn_norm_42(t)) @ W_out.T`: descrivono al massimo `t+1`, e neppure
   esattamente, perché manca l'ultima FFN. Inoltre la KL vede solo i 32 token
   scelti dal teacher e non penalizza un qualunque token esterno ai 32 che lo
   student mette sopra tutti. Il fallimento dell'MLP è quindi inconcludente
   sull'apprendibilità, ma molto conclusivo sul fatto che **quella loss non va
   scalata**.

La scorciatoia consigliata è questa:

```text
                  calcolabile in anticipo
h_k(t) -- A_k --> contesto low-rank c_t ------------------+
                                                         +--> piccolo head vocab --> token t+2
argmax del target = token t+1 --> embedding low-rank ----+
```

Una prima implementazione sensata ha rango 128, un solo non-lineare e una
matrice vocabolario nuova da circa 16,5 M parametri (33 MiB FP16), usata anche
come embedding di `t+1`. È categorica, non predice uno stato 4096-D, e si
addestra direttamente contro l'argmax e i logit **del bersaglio IQ2 realmente
servito**.

La cifra 0,614 della ridge giustifica un esperimento, non la costruzione. La
ridge sceglie la migliore lambda guardando il test, il test prosa contiene solo
~399 punti ed è autocorrelato, e il target è il token del corpus, non l'argmax
del teacher. L'intervallo binomiale ingenuo è già largo circa ±0,05; con
correlazione sequenziale è peggio. Il vantaggio sul bigramma è reale, il
margine sulla soglia 0,56 non è ancora reale.

## Il contratto temporale da non sbagliare più

Fissiamo i nomi. Dopo il forward sul token `x_t`, il bersaglio ha:

```text
h_t
q_t = P_target(. | x_<=t)
y1  = argmax(q_t)                 # token t+1, già prodotto dal bersaglio
q_{t+1} = P_target(. | x_<=t,y1)
y2  = argmax(q_{t+1})             # proposta che deve fare la testa
```

La metrica giusta per la testa è:

```text
p1_head = P[argmax Head(h_t, y1) == y2]
```

Non è `P[Head(h_t)==token_del_corpus(t+2)]`, salvo che la sequenza del corpus
segua davvero il greedy del target. Ogni dataset deve salvare esplicitamente
`h_t`, `y1`, top-k/logsumexp di `q_{t+1}` e `y2`, con un cancello che verifichi
l'indice. Questo elimina l'off-by-one che oggi attraversa piano e script.

## 1. Obiettivo di addestramento

### Scelta consigliata

Per greedy decoding userei una loss **categorica distillata**, con prevalenza
del bersaglio duro del teacher:

```text
L = CE(logits_head, argmax(q_{t+1}))
    + alpha * T^2 * KL(q_{t+1}^T || p_head^T)
```

`alpha` e temperatura si scelgono sul validation set, mai sul test. Come punto
di partenza basta dare pesi comparabili ai due termini; se il solo obiettivo è
p1 greedy, la CE sull'argmax deve restare il termine dominante. Niente label
smoothing al primo giro: attenua proprio il margine top-1 che vogliamo
massimizzare.

Se si possono calcolare tutti i 129.280 logit durante il training, farei
**softmax esatta**: con una testa low-rank è sostenibile e impedisce falsi
positivi fuori dalla shortlist. Se su disco si possono salvare solo top-k,
salverei almeno:

- top-64 ID e logit del teacher;
- `logsumexp` sull'intero vocabolario, oppure la massa fuori top-64;
- argmax duro;
- a ogni epoca, gli hard negative top-k dello student.

La KL va allora calcolata su `teacher top-k ∪ student top-k` più un bucket
"resto". La KL rinormalizzata sui soli top-32 attuali è una loss diversa e
troppo facile.

### Cosa non userei

- **MSE verso la riga di lm_head del token vero:** bersaglio geometrico
  arbitrario e mal condizionato. Va eliminata.
- **MSE verso lo stato futuro vero come loss principale:** è legittima, ma
  ottimizza migliaia di direzioni che non cambiano l'argmax. Il cantiere ha già
  un avvertimento concreto in `testa_stato_avanti.py`: in prosa la catena
  stato→decoder arriva a 0,439 contro 0,536 della via diretta.
- **Solo token del corpus:** ottimizza language modeling, non l'accordo con il
  bersaglio quantizzato verificatore.
- **Solo distillazione soft:** per greedy può spendere capacità sulla coda
  della distribuzione senza aumentare p1.

Se si vuole conservare una loss di feature per stabilizzare l'inizio, deve
essere Smooth-L1/coseno verso il **vero `result_norm(t+1)`**, con peso piccolo
(per esempio ≤0,1), mai verso `W_out[y]`. Deve essere un ausilio, non il
contratto del modello.

### Perché la ridge impara e l'MLP no

Non è evidenza che serva una rete più grande. La ridge duale:

- risolve esattamente un problema sottodeterminato nello spazio dei campioni;
- può interpolare quasi per costruzione quando `d=4096 > n_train`;
- seleziona oggi lambda sul test;
- sfrutta un proxy denso (`W_out[y]`) che rende facile una soluzione ai minimi
  quadrati, pur non essendo lo stato desiderato.

L'MLP invece ha 4,5 M o 9,4 M parametri su ~1.276 esempi di train, nessun
residuo identità, statistiche per-dimensione stimate su pochissimi punti e due
loss temporalmente in conflitto. Prima di discutere GELU, width o optimizer va
fatto un sanity gate: 512 esempi devono essere sovra-adattati a >95% top-1 con
la loss categorica corretta. Se non succede, c'è ancora un bug di pipeline.

## 2. Quale stato leggere e quando

### `result_norm` è l'oracolo di accuratezza, non la scelta automatica

`result_norm(t)` è esattamente ciò che la lm_head del bersaglio ha consumato.
È quindi il primo tap con cui verificare se la funzione `h,y1 -> y2` è
apprendibile senza il rumore dell'ultima FFN. Se una testa economica non supera
0,56 nemmeno da `result_norm`, la strada va chiusa.

Ma `result_norm` arriva dopo tutti i 43 strati e offre zero anticipo. Non è
"gratis": la testa gira dopo il target e compete per la stessa RTX 3060.

### `ffn_norm-42` è un buon tap di latenza, ma oggi è usato come se fosse finale

`ffn_norm-42` è l'ingresso dell'ultima FFN, non lo stato della lm_head. Il fatto
che il test `t+1` faccia 0,749 invece di quasi 1,0 lo rende visibile. Il suo
vantaggio è temporale: la proiezione del contesto della testa può partire mentre
il bersaglio completa ultima FFN, norm e lm_head.

La parola corretta per avere più parallelismo non è stato "più profondo", ma
tap **più precoce**. Proporrei un'unica sweep con:

```text
ffn_norm-38, ffn_norm-40, ffn_norm-42, result_norm
```

Per ogni tap va tracciata la frontiera `p1` contro millisecondi di calcolo del
bersaglio rimasti dopo il tap. Non serve scegliere intuitivamente.

### Parallelismo quasi zero: possibile solo in parte

Con il token-conditioning corretto, `y1` è noto solo dopo la lm_head principale.
Quindi la testa intera non può terminare in parallelo agli ultimi strati. Si può
però pre-calcolare la parte costosa `A_k h_k` mentre il target prosegue; dopo
l'argmax restano lookup dell'embedding di `y1`, attivazione e proiezione vocab
low-rank.

Inoltre due stream CUDA non creano risorse. La testa può nascondersi nelle
attese del percorso MoE zero-copy, ma può anche contendere SM, cache e banda
PCIe. "In parallelo" va accettato solo da CUDA event/end-to-end, non dal grafo.

### Multi-layer fusion

EAGLE-3 ha abbandonato la feature prediction e usa feature multi-layer per
predizione diretta. Qui la versione economica è sommare proiezioni low-rank:

```text
c_t = A_38 h_38 + A_40 h_40 + A_42 h_42
```

Ogni termine può essere calcolato quando il relativo stato diventa disponibile.
Attenzione: l'ultimo tap incluso determina quando `c_t` è completo. La fusion è
un esperimento di accuratezza, non una promessa di anticipo.

## 3. Più dati senza pagare la generazione

### Prefill: sì, ma solo con l'allineamento giusto

Il prefill dà gratuitamente per ogni posizione:

```text
(h_t, token_corpus(t+1)) -> q_{t+1}
```

Questa è supervisione valida per una testa **condizionata su
`token_corpus(t+1)`**: insegna la transizione dato il token intermedio. Non è
on-policy greedy, ma non è temporalmente sbagliata.

Per una testa non condizionata, userei solo le posizioni in cui:

```text
token_corpus(t+1) == argmax(q_t)
```

Altrimenti il label `q_{t+1}` è condizionato su un token diverso da quello che
il bersaglio avrebbe scelto. Questo filtro è la maniera più economica per
ottenere coppie localmente on-policy da corpus esistenti.

Il dato deve venire dal **modello IQ2 servito**, non da pesi FP/BF16: il giudice
di accettazione è quell'argmax quantizzato, incluse le sue discontinuità.

### Riutilizzare le run è migliore del prefill generico

Le uscite greedy sane già prodotte dalle campagne sono il dataset più prezioso:
sono on-policy e costano zero generazione aggiuntiva. Vanno rilette con
`llama-eval-callback`, salvando tuple compatte. Se possibile, la rilettura deve
essere token-per-token o deve prima passare un cancello che confronti logit e
stati fra percorso prefill e percorso decode: kernel con batch diverso possono
cambiare l'argmax, e il repo ha già documentato differenze fra percorsi batch.

Per le future misure, aggiungerei un recorder leggero, non un dump completo:

```text
stati dei 3-4 tap in FP16 + y1 + top-64/logsumexp di q_{t+1}
```

A 4 tap sono circa 32 KiB/token di stati; a un solo tap circa 8 KiB/token. Si
scrive a ring buffer asincrono e si ottengono dati ogni volta che la macchina
fa comunque una corsa valida. Non serve conservare tutti i tensori intermedi.

### Come usare i 1.952 record di calibrazione

Non bisogna chiamarli 1.952 esempi indipendenti. I 976 `think`/976 `nothink`
sono coppie fortemente correlate e 1.886 record sono sorgente dello stesso
repo. Regole minime:

- split per `source`/file e per coppia think-nothink, mai per token casuale;
- deduplica per hash normalizzato e limite di token per file;
- test separati codice, prosa/documentazione e agent/tool use;
- campionamento bilanciato: altre 50.000 righe dallo stesso boilerplate non
  comprano generalizzazione;
- sequenze di almeno 256-512 token e reset netto fra documenti.

La finestra scorrevole 128 riduce il bisogno di prompt da 10k per il percorso
locale, ma il percorso MLA compresso può ancora portare contesto più lungo:
non troncherei tutto a 128 senza un'ablation.

### Augmentation: quasi tutta falsa economia

Rumore gaussiano sugli hidden, mixup e duplicazione con dropout sono
regolarizzazione, non nuovi target. Possono aiutare dopo, ma non aumentano il
numero effettivo di contesti. L'unica augmentation con semantica corretta è
variare il token intermedio e far ricalcolare al teacher il ramo conseguente;
quello però è un forward aggiuntivo. Prima userei prefill condizionato e run
già pagate.

## 4. Architettura dell'adapter sotto 40 ms

### Prima scelta: classificatore condizionato low-rank

Con `r=128`:

```text
c = A * RMSNorm(h_k)                 A: 4096 x 128
u = SiLU(c + B[y1])                  B: vocab x 128
logits_head = B * u + bias           B condivisa input/output
```

Taglia approssimativa:

- `A`: 0,52 M parametri;
- `B`: 16,55 M parametri con vocab 129.280;
- totale: ~17,1 M, cioè ~34 MiB FP16;
- proiezione vocab: ~16,5 M MAC per chiamata.

È molto sotto il budget aritmetico. Il rischio vero, insegnato da DSpark, è
l'orchestrazione: deve essere un ramo CUDA nello stesso grafo, senza PyTorch,
callback host, sincronizzazione intermedia o allocazioni per passo.

`B` può essere inizializzata proiettando la lm_head congelata in un sottospazio
di rango 128 (randomized SVD/PCA, oppure proiezione ortogonale) e poi
fine-tuned. Così si importa la geometria del vocabolario senza leggere 536 MiB
di `output.weight` una seconda volta a ogni token.

Se rango 128 è insufficiente, il solo aumento ammesso al secondo giro è 256:
~67 MiB per `B`, ancora piccolo. Non aggiungerei tre/quattro layer finché una
testa lineare/gated non ha passato il gate.

### Seconda scelta: adapter low-rank più lm_head congelata

È utile come controllo data-efficient:

```text
z = h_k + U * SiLU(V*h_k + E(y1))
logits = W_out * RMSNorm(z)
```

Va addestrata con CE/KL sui logit, non con MSE verso una riga di `W_out`.
Potrebbe richiedere meno dati, ma dopo aver conosciuto `y1` obbliga a una
**seconda lettura** della lm_head Q8 da ~536 MiB. Non può essere fusa con la
lm_head principale nello stesso matmul, perché il suo input dipende
dall'argmax di quel primo matmul. Per questa macchina è quindi il controllo di
accuratezza, non la favorita di serving.

### Confidence gate

La testa deve emettere anche `margin = logit1-logit2` o entropia calibrata. Se
la confidenza è bassa, si fa decode normale e non si paga il batch di verifica
a due posizioni. Vanno riportati insieme:

```text
coverage, p1_condizionato, p1 complessivo, t/s end-to-end
```

Ottimizzare p1 scartando quasi tutto sarebbe un falso successo. Il gate va
tarato direttamente sul costo misurato del verificatore e sui colpi cache.

### Il router corretto non va infilato a forza nella testa token

La nuova semantica `sqrt_softplus + bias + gruppi + top-k nel gruppo` invalida
un surrogato `topk(W*h)` per predire le route. Non invalida la testa token:
essa vede come teacher i logit finali.

Se si aggiunge un ausilio di route/prefetch, bisogna predire gli **ID realmente
selezionati** oppure usare una loss gerarchica gruppo→esperto coerente col
router. Un BCE piatto sui 256 esperti può ancora funzionare come classificatore
dei set osservati, ma non deve essere raccontato come replica del gate. La sua
metrica utile è richiamo degli esperti che causerebbero miss, pesato per costo
di trasporto, non recall medio astratto.

## 5. Cosa copiare dalla letteratura, e cosa lasciare lì

| Metodo | Da copiare | Da non copiare qui |
|---|---|---|
| Medusa | backbone congelato; heads addestrate con obiettivo categorico/self-distillation; verifica lossless | heads future indipendenti e alberi larghi: aumentano il batch di verifica e l'unione delle route oltre i 380 slot |
| EAGLE / EAGLE-2 | token avanzato `t+1` come input; confidence calibrata per decidere quanto draftare | autoregressione di feature con propria cache/loop; tree dinamico largo su una macchina dove ogni ramo tocca esperti host |
| EAGLE-3 | predizione diretta del token e fusion di feature multi-layer: è esattamente la correzione suggerita dai dati locali | draft model più ricco e ricette di larga scala; i suoi speedup su GPU HBM non prezzano UVA, PCIe e cache esperti |
| Hydra | dipendenza sequenziale tramite embedding dei token candidati; distillazione dal target | MLP a 4 layer, decoder Transformer extra e tree decoding prima di avere dati e un budget di verifica sano |
| DeepSeek MTP | RMSNorm/fusione di hidden principale e embedding del token avanzato; possibile riuso della lm_head; CE per token futuro | il modulo originale: per V3 sono 11,5 B parametri unici e 2,4 B attivi, addestrati insieme al backbone su 14,8 T token. Non è una "testina" per 12 GB |

Tre punti della letteratura sono particolarmente decisivi.

1. EAGLE mostra che predire la feature futura senza il token futuro è ambiguo;
   il token shiftato risolve il problema. Questo input è compatibile col
   vincolo senza stato.
2. Hydra trova vantaggiosa la distillazione della distribuzione del target,
   non la regressione verso un embedding etichetta.
3. EAGLE-3 abbandona esplicitamente la feature prediction per token prediction
   diretta e feature multi-layer. È coerente con il risultato locale di
   `testa_stato_avanti.py`, non una moda da importare alla cieca.

Il numero DeepSeek V3 di 85-90% di accettazione del secondo token non è un
prior utilizzabile: viene da un MTP co-addestrato col backbone, non da un
adapter post-hoc su poche migliaia di token e su un teacher a 2 bit.

Fonti primarie:

- [Medusa](https://arxiv.org/abs/2401.10774)
- [EAGLE](https://arxiv.org/abs/2401.15077)
- [EAGLE-2](https://arxiv.org/abs/2406.16858)
- [EAGLE-3](https://arxiv.org/abs/2503.01840)
- [Hydra](https://arxiv.org/abs/2402.05109) e [implementazione ufficiale](https://github.com/zankner/Hydra)
- [DistillSpec](https://arxiv.org/abs/2310.08461)
- [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437) e [struttura ufficiale dei pesi MTP](https://github.com/deepseek-ai/DeepSeek-V3/blob/main/README_WEIGHTS.md)

## 6. Il singolo esperimento che decide adesso

### Nome: `HEAD_ONPOLICY_12K_CONDITIONED_GATE`

Non farei una nuova generazione lunga. Riutilizzerei **10-12 output batch-1
greedy sani già catalogati**, per un totale di circa 12.000 token e con intere
run di codice, prosa e agent/reasoning. Una sola rilettura con eval-callback,
preferibilmente token-per-token, salva:

```text
ffn_norm-38, ffn_norm-40, ffn_norm-42, result_norm   (FP16)
token ID
top-64 + logsumexp dei logit del target
```

Cancelli prima del training:

1. per ogni posizione di completion,
   `token_salvato(t+1) == argmax(q_t)`; mismatch = run non on-policy o percorso
   numerico diverso, da scartare;
2. nessuna coppia think/nothink o stesso file attraversa train/val/test;
3. split per **intere run**, circa 60/20/20, con almeno un test prosa e uno
   codice;
4. il modello deve sovra-adattare 512 esempi a >95%, altrimenti pipeline rotta.

Si addestra una sola famiglia preregistrata, rango 128, tre seed:

```text
Head(h_k, y1) = B * SiLU(A_k*RMSNorm(h_k) + B[y1]) + bias
```

Due ablation costano quasi nulla e fanno parte dello stesso esperimento:

- con e senza `y1`, per misurare il valore del conditioning;
- quattro tap, per ottenere la frontiera accuratezza/anticipo.

Nessun tuning sul test. Sul test si riportano top-1 contro **argmax teacher a
t+2**, per-run, mediana, forbice e bootstrap a cluster per run; inoltre curva
coverage/p1 del confidence gate. Bigramma e moda si stimano solo sul train.

### Regola go/no-go

- **GO:** almeno un tap implementabile (`ffn_norm-42` o più precoce) ha mediana
  `p1 >= 0,60` e limite inferiore 95% cluster-bootstrap `> 0,56` sia fuori dal
  solo boilerplate sia sul totale. A quel punto si scrive il kernel e si misura
  `c_head` end-to-end; target di progetto ≤25 ms, non 40, per lasciare margine
  alla variabilità del verificatore.
- **GO condizionato:** passa solo `result_norm`. La funzione è apprendibile,
  ma non c'è anticipo; si implementa solo se il classificatore diretto
  low-rank ha costo misurato sufficientemente basso.
- **STOP:** anche `result_norm` resta sotto 0,56, oppure il risultato vive solo
  nel codice ripetitivo. Non si raccolgono milioni di token e non si aumenta la
  profondità dell'MLP: la mappa economica non è abbastanza allineata.

### Costo macchina

L'ancora già annotata nel cantiere è circa 15 minuti di callback per ~2.000
token. Linearmente, 12.000 token costano ~1,5 ore di rilettura; quattro tap,
top-k e margine operativo portano la previsione prudente a **1,5-2 ore**.
Training della testa rango 128 e tre seed sulla 3060: **~0,5-1 ora**. Totale:

```text
2-3 ore macchina, zero generazione nuova
```

Se gli output puliti non sono recuperabili, generarne 12.000 a 10 t/s aggiunge
circa 20 minuti, non ore. La parte costosa resta la rilettura/dump.

## Ordine operativo dopo il verdetto

1. Fare solo `HEAD_ONPOLICY_12K_CONDITIONED_GATE`.
2. Se STOP, chiudere la testa token e lavorare sul costo del verificatore/cache.
3. Se GO, implementare **prima** il classificatore rango 128 in un unico ramo
   CUDA graph e misurare costo/coverage, senza profondità >1.
4. Solo se p1 passa ma il costo no: provare rango 64/Q8 o fusion del solo
   contesto anticipata; non tornare a un drafter con KV.
5. Solo se p1 e costo passano: valutare profondità speculativa >1. Ogni token
   aggiunto deve riprezzare unione delle route, colpi cache e correttezza del
   batch; i risultati Medusa/EAGLE su HBM non sostituiscono questa misura.

La conclusione critica è quindi: **non serve ancora più MLP; serve un target
teacher corretto, il token `t+1` come input e un head categorico low-rank.** Il
prossimo investimento ragionevole è 2-3 ore, non una raccolta massiva.
