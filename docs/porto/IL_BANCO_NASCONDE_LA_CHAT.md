# Il banco nasconde il costo della chat, e i batch larghi costano

4 agosto 2026, sera. Tre risultati che vanno insieme.

## 1. La speculazione gratis perde, e falsifica la sua stessa premessa

Il fork ha cinque speculatori n-gram gia' dentro: drafter senza pesi, che
copiano dal testo gia' generato. Sembrava la leva giusta per l'orchestrazione --
i 43 rendezvous per token si pagano per PASSAGGIO IN AVANTI, quindi verificarne
otto insieme dovrebbe dividerli per otto.

```
Z2  ngram-cache, draft capato a 8      217,61 ms/token    4,60 t/s
riferimento (17 mappati, ub 64)                           6,37 t/s
                                                          -27,9%
```

L'accettazione sta in `timings.draft_n` dentro la risposta JSON, non nel log:

```
token generati     5.545
token abbozzati    1.797
token accettati      108      6,0%
```

**E l'aritmetica chiude da sola.** 1.797 abbozzati su 5.545 generati sono
+32,4% di lavoro attraverso il modello; la perdita e' 27,9%. I due numeri
coincidono, quindi **ogni token abbozzato e' costato quanto un token vero**.

La verifica larga non ha ammortizzato niente: i 43 rendezvous si sono pagati
otto volte invece di dividersi per otto. Con questo, la speculazione qui non
puo' funzionare in nessun caso -- per andare in pari servirebbe accettare quasi
il 100%.

### L'errore nella premessa

Avevo scritto che su MoE c'era un guadagno in piu': «verificando N token
insieme gli esperti si sovrappongono, il 90,3% degli accessi sono riletture».

Sbagliato. Quel 90,3% e' una statistica sull'**intera corsa**, non sulla
sovrapposizione fra token **adiacenti**. E il dato che avevamo gia' sulla LRU
dice il contrario: 258 esperti distinti per token, e la recency «sfratta con
precisione cio' che serve dopo». I token vicini usano esperti diversi, quindi
un batch da 8 legge otto volte i byte invece di una.

### Tre conferme indipendenti della stessa cosa

```
1.  speculazione (verifica larga da 8)          -28%
2.  il prefill BATCHATO e' piu' lento del decode uno-a-uno   (2,31 contro 6,35)
3.  ubatch 16 invece di 64 -> prefill quasi RADDOPPIATO      (4,90 contro 2,31)
```

**Su questo modello i batch larghi non ammortizzano: costano.** Contano i byte
per token, non le passate. E' lo stesso meccanismo per cui lo zero-copy vince.

## 2. --no-mmap e' peggio qui, e llama.cpp lo consiglia lo stesso

Nel log del server c'e' scritto dal primo avvio:

> tensor overrides to CPU are used with mmap enabled -- consider using --no-mmap
> for better performance

Provato. E' peggio:

```
pages input/s   con mmap  ~2.100 a regime      senza mmap  40.388
```

Il consiglio vale dove il modello **ci sta**. Qui non ci sta: 17 strati mappati
(28,7 GiB immobili) piu' 26 strati su CPU (43,9 GiB) fanno 72,6 GiB su 63,9 di
RAM. L'eccedenza esiste comunque, e cambia solo dove va:

```
con mmap    pagina PULITA file-backed -> si sfratta gratis, si rilegge dal GGUF
senza mmap  pagina anonima -> va SCRITTA nel pagefile, poi riletta.  Doppio I/O.
```

I 13,4 GB di RAM libera visti subito dopo il caricamento erano commit pigro, non
una cura: sotto carico sono tornati a 1.185 MB.

## 3. Il banco nasconde il costo della chat

Questo e' il risultato che conta, ed e' venuto da un'osservazione dell'utente
(«perche' in chat c'e' questo calo esagerato? stiamo leggendo tutto da disco!»).

**Decode e prefill leggono cose diverse.**

```
decode    6 esperti x 43 strati = 258 per token, e sono i CALDI, residenti
prefill   un batch da 64 instrada fino a 384 esperti per strato
          -> tocca quasi tutti i 256, inclusi i FREDDI che stanno su SSD
```

Misurato nei bracci Y: **il prefill paga 3,1 volte il paging del decode** (6.648
contro 2.119 pagine/s su Y0). E non li legge soltanto: li fa entrare mentre la
RAM e' al 100%, quindi **sfratta proprio quelli che al decode servono**. Dopo
ogni prefill il decode si ricostruisce l'insieme di lavoro da capo.

**Il banco lo nasconde per costruzione:**

```
                    prefill      decode      il prefill pesa
NeuraForge 8k        74 tok    8.000 tok          0,9%
chat, un turno      300+ tok    ~200 tok           60%
```

Nel banco il danno si paga una volta e si spalma su ottomila token. In chat si
paga a ogni turno e domina.

**Quindi il 6,37 t/s e' misurato sul carico piu' favorevole possibile, e la
chat e' vicina al peggiore.** Ogni verdetto della campagna -- gate, decadimento,
ammissione, prefetch, zero-copy, VRAM -- viene da quel banco.

### La prima misura in chat vera

```
LLAMA_CHAT_sota2   max 6,52   p90 6,33   mediana 5,99   p10 5,17   min 4,21
                   ZERO crolli
```

Sana. Il cumulativo (5,55) si porta dietro i token freddi del riavvio;
l'istantanea sta a 6,3-6,5, cioe' il numero del banco. Ma la sessione non ha
ancora attraversato un cambio di dominio, che e' il caso non misurato.

## 4. Le punte sono del CONTROLLO, non dello zero-copy

Domanda dell'utente sulle punte a 7-8 t/s. Ci sono state:

```
                      max    p99    p90   mediana   MEDIA FINALE
W0  controllo        7,69   7,65   7,48    7,04       5,68
W2   8 mappati       7,36   7,29   7,16    6,71       6,11
Y0  17 mappati       7,00   6,93   6,82    6,52       6,35
W1  17 mappati       6,91   6,86   6,73    6,50       6,37
```

Le punte piu' alte le fa il braccio **senza** zero-copy -- che chiude ultimo.
Monotono all'incontrario su ogni colonna: piu' strati mappati, punte piu' basse.

E' la conferma piu' netta della tesi: per uno strato mappato il PCIe e' piu'
lento della RAM, quindi quando tutto va bene si va piu' piano; ma quello strato
non faulta mai, quindi quando va male non si crolla.

```
                     punta    minimo   tempo sotto 2 t/s
W0  controllo         7,69     0,18         16,6%
W1  17 mappati        6,91     4,73          0,0%
```

**Su turni corti questa scelta potrebbe rovesciarsi.** Una risposta da 200 token
che parte in un momento buono la finisci a 7,5 e forse non incontri mai un
crollo; su 8.000 token il crollo lo incontri per forza. Non e' mai stato
misurato -- serve un banco a turni corti.

## Cosa resta da fare

1. **`ub 16` a ctx 10000.** Mai provato: la prima volta l'ho combinato con ctx
   50k, che era il vero problema. Il prefill quasi raddoppia e ora sappiamo
   perche' (meno esperti distinti per passata, meno sfratti).
2. **Rimettere in funzione il gate.** `VirtualLock` fallisce con errore 1453 da
   stamattina -- quota del working set esaurita dai 28,7 GiB mappati. Serviva
   esattamente a impedire che il prefill sfratti i caldi, cioe' al problema di
   adesso, e non sta girando.
3. **Un banco di chat a piu' turni**, con cambio di dominio, per smettere di
   ottimizzare su un carico che non e' quello d'uso.
4. **M22** (22 mappati senza strato in VRAM) resta non misurato.
