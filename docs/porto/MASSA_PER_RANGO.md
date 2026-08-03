# Il rango non è ridondante: 10,2 GB di differenza

3 agosto 2026, sera. Prima misura della massa su cui tarare il gate SSD→RAM,
definito dall'utente come `massa = peso di gating × frequenza di bussata`.

## Perché il rango invece del peso vero

I pesi di gating non toccano mai la CPU. Misurato con `GGML_SCHED_DEBUG=2`,
ogni strato fa:

```
SPLIT CUDA0    probs -> topk -> weights -> norm -> scale
SPLIT CPU      ingressi [ffn_norm] [ffn_moe_topk]      <- SOLO gli id scendono
               ffn_moe_gate / up / down
SPLIT CUDA0    ingresso [ffn_moe_down]                 <- il risultato RISALE
               ffn_moe_weighted = esperti x pesi
```

Lo scheduler fa risalire il risultato degli esperti (384 KB) invece di far
scendere i pesi (0 KB), perché la catena residuale a valle sta comunque su GPU.
Prendere i pesi veri costerebbe una lettura sincrona per strato — il disegno
già scartato a −18% sul prefill.

**Ma l'ordine del top-k è già sulla CPU** dentro `r.id[]`, e lo buttavamo. Il
rango 0 è l'esperto col peso più alto di quel token, il 5 il più marginale.

## Il cancello di validità

```
totali per rango   194274  194274  194274  194274  194274  194274
squilibrio         0,0000
```

Sei ranghi con conteggi identici: ogni token riempie ogni posizione, e
l'assunzione «`r.id[]` arriva ordinato per peso decrescente» regge. Senza
questo controllo l'istogramma sarebbe aria.

Costo dell'osservatore: **112,4 ns/chiamata, 21,8 ms su 255 secondi**. Il run
fa 170,07 ms/token contro i 168,32 senza — dentro il rumore.

## Il dato

Corsa di 1500 token, ctx 10000, prompt di campagna. 193.758 chiamate, 0 record
persi, **9.032 coppie (strato, esperto) distinte su 11.008 possibili** — il 18%
degli esperti non viene mai toccato su questo dominio.

Quanti esperti servono per coprire il 90% della massa, secondo tre funzioni di
peso `w(rango)`:

```
w piatta      = 1        (equivale alla sola frequenza)   3.921    25,8 GB
w armonica    = 1/(r+1)  (il primo vale 6 volte il sesto) 3.098    20,4 GB
w ripida      = 2^-r     (il primo vale 32 volte il sesto) 2.381   15,7 GB
                                                          ------  -------
                                       differenza                 10,2 GB
```

*(un esperto è 6,75 MB: 1.728 MB di gate+up+down per strato, diviso 256)*

**Il rango dimezza quasi l'insieme da tenere in RAM.** E i 10,2 GB di
differenza sono esattamente la taglia del drafter (6,8 GB a Q2_K, 10,9 a
bf16) — cioè il posto che serviva per farlo convivere.

## Il rango cambia davvero l'ordinamento

Sovrapposizione fra la classifica per sola frequenza e quella per massa ripida:

```
primi   100:   86%          primi  1000:   76%
primi   500:   77%          primi  4000:   86%
```

Nei primi mille, **240 esperti sono diversi**. Non è ridondanza.

## I due casi che spiegano il meccanismo

Dentro per frequenza, fuori per massa — quelli che un gate a sola frequenza
terrebbe in RAM per sbaglio:

```
strato 18  esperto  74   639 bussate   ranghi [0, 0, 30, 156, 213, 240]
                                       MAI scelto per primo. Nemmeno una volta.
```

E il contrario, quelli che sfratterebbe:

```
strato  2  esperto  29   159 bussate   ranghi [144, 0, 0, 0, 3, 12]
                                       il 90,6% delle sue scelte e' da PRIMO
```

Il primo bussa quattro volte più del secondo e non porta mai l'uscita. È
esattamente la distinzione che l'utente aveva descritto: *costringere il router
a usare il meglio degli esperti che ha*.

## Cosa resta aperto

**Quale `w(rango)` sia la giusta.** Le tre provate danno 3.921 / 3.098 / 2.381:
il risultato è sensibile, quindi la scelta non è indifferente e va decisa su un
criterio, non per gusto. Il criterio naturale è la qualità dell'uscita a parità
di RAM — cioè misurare, non postulare.

**Se la distribuzione regge cambiando dominio.** Questa mappa è di una landing
page HTML. Il collasso wide è documentato come dominio-di-calibrazione: una
soglia tarata qui potrebbe non valere altrove. Serve almeno una seconda mappa
su un dominio diverso prima di fissare qualunque numero.
