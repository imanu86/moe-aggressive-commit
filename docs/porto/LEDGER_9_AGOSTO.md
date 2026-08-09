# Ledger del 9 agosto

Giornata di **misure che si potevano finalmente fare**. Il risultato piu' grosso
non e' un t/s: e' che la bozza ha smesso di estrarre a sorte, il rumore e' passato
da ±4% a ±0,1-1,6%, e da meta' pomeriggio in poi un confronto a n=1 vale.

## Il tabellone

| configurazione | t/s | note |
|---|---:|---|
| 339 slot + 32 bozza, blk.0 mappato | **10,40** | il migliore, media di tre corse deterministiche |
| 380 slot, nessuna cache bozza | 10,33 | tre corse, dispersione **0,1%** |
| 380 + 32 | 10,08 | VRAM libera 277 MiB, strozzata |
| 380 + 64 | 9,39 | VRAM libera 195 |
| 300 + 32 | 9,59 | 829 MiB liberi e perde: il margine non e' una leva |
| n-max 2, 448 slot | 9,00 | (~9,17 correggendo un mio confondimento) |
| n-max 2, 339+32 | 7,26 | colpi crollati al 23,6% |
| n-max 5, 339+32 | 5,46 | p1 0,554 |
| W=1 prefetch a copertura piena | 5,84 | colpi 39%, prenotazioni > domande |

Metro senza speculazione: **107,7 ms per token**, cioe' 9,285 t/s.

## Il risultato della giornata: il pavimento di rumore era una riga

`common_sampler_init` accoda **sempre** un `llama_sampler_init_dist(seed)`
(`sampling.cpp:375`) e il seme di default e' casuale a ogni processo. Con
`top_k = 10` (`speculative.cpp:988`) il token proposto dalla bozza era
un'**estrazione a sorte fra i primi dieci**, diversa a ogni corsa.

Con `LLAMA_SPEC_DRAFT_TOPK=1`, tre corse identiche:

```
  10,30 / 10,46 / 10,44 t/s    p1 0,86311 identico alla quinta cifra
  mean_len 1,85   3.006 caratteri   UN SOLO SHA B396AB2137B2080A
```

Bit-identiche **con la speculazione accesa**, cosa mai successa in tutta la
campagna. Non e' un guadagno di velocita' (10,40 contro 10,47, stessa cosa): e'
aver riguadagnato la capacita' di misurare. Muore anche l'ipotesi che il
non-determinismo venisse dal replay dei grafi CUDA -- e infatti a grafi spenti lo
SHA e' identico.

Seconda incoerenza sullo stesso punto: la catena Markov si propaga con l'argmax
interno (`prev = ggml_argmax(col)`, `dflash.cpp:300`) ma emette un token
campionato. Con `top_k=1` le due cose tornano a coincidere.

## Il modello di costo, ricostruito dai contatori

Con `c1 = 107,7 ms` come unico ingresso esterno, il costo del batch di verifica:

```
  posizioni     costo      marginale
      1        107,7 ms        —
      2        163,0        +55,3
      3        339,8       +176,8      <- la terza costa 3,2 volte la seconda
      6        709,0       +123,1
```

Il gradino ha **due meccanismi**, entrambi misurati:

**Thrashing della cache.** Colpi 55,1% a due posizioni, **23,6%** a tre: il ciclo
passa da 516 a 774 attivazioni contro 339 slot fissi. A 401 slot i colpi
risalgono a 53,4%, a 448 a 67,7% -- e la curva non si era ancora fermata.

**Ripristini da checkpoint.** `llama_kv_cache_dsv4::seq_rm` rifiuta il rollback
parziale, quindi ogni accettazione parziale ripristina il checkpoint e rigioca un
forward. 13,7% dei cicli a n-max 1, **30,9%** a n-max 2. Il conteggio si ricava
dalla discrepanza fra le due contabilita' (slot 517 accettati contro 599 interni
= 82 ripristini), che e' anche il difetto che gonfia il p1 stampato.

## Il potenziale lasciato a terra

```
  senza speculazione                              107,7 ms/token
  con speculazione oggi        174,7 / 1,85    =   94,4    (+12,4%)
  se la posizione extra fosse gratis  119,4/1,85 =  64,5   (+67%)
```

**Prendiamo 12 punti su 67.** E il proponente e' solo 11,73 ms su un ciclo di 178,
cioe' il 6,5%: anche azzerando la bozza si guadagnerebbe il 7%. Tutto il fronte
della bozza vive dentro quel 6,5%; il gradino sta nel restante 93%.

## Fronti chiusi, con il numero

- **Blocco lungo**: n-max 1 -> 2 -> 5 da'ANNO 10,47 / 7,26 / 5,46. La bozza fa il suo
  mestiere (5 posizioni costano 2,3x invece di 5x: la testa semi-autoregressiva
  `block_size=5` e' reale) e si perde comunque, perche' il p1 crolla e ogni
  posizione buttata il bersaglio l'ha verificata.
- **Secondo blocco pinnato**: tetto misurato fra 76.528 MiB (passano) e 78.752
  (`cudaHostAlloc ... out of memory` su UNA richiesta contigua da 4,3 GiB).
- **Residenza contro esecuzione**: mappare `blk.0` senza cache PEGGIORA (gen 14,29
  contro 11,88). Leggere un esperto in zero-copy costa 0,72 ms, calcolarlo su CPU
  0,242. La leva e' la residenza, non l'esecuzione.
- **CUDA graph**: scagionati due volte. SHA identico a grafi spenti, e spegnerli
  costa il 24%.
- **VRAM libera oltre il necessario**: sopra ~540 MiB e' spazio sprecato.
- **Blocchi contigui invece di copie sparse**: bocciati con l'aritmetica. Alla
  parita' fra motore di copia e kernel il pareggio arriva a densita' utile ≥99%;
  la densita' vera e' 6 esperti su 256, ~5%.

## Il prefetch: il verdetto era giusto per la ragione sbagliata

`ggml-cuda.cu:4486` ricavava quanti id prenotare dal **nome del tensore**, e il
nome porta `n_expert_used` = 6, costante, mentre il tensore e'
`[n_expert_used, n_tokens]`. Il prefetch prenotava per la **sola posizione 0**:
meta' delle domande a n-max 1, due terzi a n-max 2. Lo stesso errore era gia'
stato corretto trenta righe piu' su sul cammino a domanda, e non portato qui.

Terza volta nella stessa giornata dello stesso presupposto -- che il decode abbia
un token per volta -- in un sistema che ne ha 2, 3 o 6.

Corretto e rimisurato, con la cura dello sfratto accesa e spenta:

| | t/s | colpi | buchi | prenotati | in ritardo |
|---|---:|---:|---:|---:|---:|
| W=0, niente prefetch | **10,40** | 55,1% | 102.842 | 0 | — |
| W=1 solo posizione 0, CURA=0 | 7,45 | 42,9% | 128.841 | 120.080 | 41.010 |
| W=1 copertura piena, CURA=0 | 5,84 | 39,0% | 134.928 | 257.281 | 63.884 |
| W=1 copertura piena, CURA=2 | 6,11 | 46,2% | 120.376 | 244.815 | 50.213 |

Tre cose, in ordine.

**La copertura non era il difetto: coprire meno era una protezione accidentale.**
Raddoppiando le prenotazioni si perdono altri 1,6 t/s -- il danno scala col numero
di ordini, perche' ogni ordine sfratta uno slot.

**La cura funziona sul meccanismo.** Bit `predetto`, cinque classi di vittima,
usato/predetto intoccabile: colpi da 39,0 a 46,2%, buchi -14.500, ritardi dal
24,8% al 20,5%. Il disegno e' corretto e si vede.

**E non basta.** Anche con la cura i colpi restano **sotto** quelli di chi non
prefetcha affatto: 46,2% contro 55,1%. Prevedere al 90% di accuratezza,
proteggendo il working set dallo sfratto, produce **meno colpi che non prevedere**.

Il motivo e' aritmetico e definitivo: **244.815 prenotazioni per ~221.000 domande
su 339 slot**, con un working set di 516 attivazioni per ciclo. Non c'e' nessuno
spazio libero da speculare. Il prefetch non e' morto per predizione sbagliata, ne'
per latenza, ne' per sfratto cattivo -- tutte cose che abbiamo creduto in momenti
diversi. E' morto perche' **prefetchare richiede capienza in eccesso e noi siamo in
deficit di capienza**. E' la stessa frase che spiega ogni altro risultato della
giornata.

Il p1 in questi bracci e' il piu' alto di tutta la campagna (0,881-0,902): la
previsione non e' mai stata il problema.

## Il trasporto, e una mia ipotesi demolita

Avevo calcolato che il link fosse saturo (9,4 GB/s richiesti su 11-14 disponibili)
e che il prefetch fosse quindi morto per aritmetica. **Sbagliato**: la scheda e'
su PCIe 4.0, non 3.0. E la banda vera durante la copia e' **24,1-24,4 GiB/s**, in
parita' col motore di copia -- il 4,5-7,8 GB/s che avevo misurato era duty cycle,
non inefficienza. Il costo marginale di un buco e' **0,221 ms**, che a 6,75 MiB fa
30,6 GiB/s: velocita' di linea.

Lo stream DMA trasporta **zero byte esatti**: tutto passa da `kern_copia` sullo
stream di calcolo. Non e' una svista -- i copy engine si programmano solo
dall'host, i buchi li decide un kernel dentro il grafo, e 43 sincronizzazioni per
token romperebbero i CUDA graph che valgono 95,5 ms per forward su WDDM.

Sul forward a due posizioni il trasporto e' il **40%** (62,8 ms su 158) ed e'
seriale per costruzione: `decidi -> copia -> MMVQ` sullo stesso stream.

## Lo scandaglio a 20 agenti

Venti perimetri disgiunti, mandato "trova codice che contraddice se stesso".
**Otto reperti alti, due trovati due volte da perimetri diversi.** 3.550 righe in
`audit/`, commit `6d8ae7f`. I due che contano di piu':

- il **default `W=2`** sceglie il prefetch che il sorgente stesso misura come il
  25% peggiore, trenta righe piu' in la';
- l'**anello esperti e' stato di processo** e intercetta la bozza prima della sua
  cache per-istanza: con `LLAMA_RING=1` puo' leggere i pesi del modello sbagliato.
  Dormiente -- il default e' spento e non compare nei log -- ma e' una trappola
  armata.

## Errori di metodo, per non ripagarli

1. **Ho variato due cose insieme** nei bracci di capienza: spenta la cache bozza
   ma lasciato `blk.0` mappato, cioe' la combinazione gia' misurata come dannosa
   (+5,3 ms/chiamata). Il "+24% dalla capienza" era gonfiato: corretto, fra 380 e
   401 slot non c'e' guadagno e il salto vero e' solo a 448, +8%. Trovato
   dall'utente, non da me.
2. **Ho chiamato "costo di verifica" un numero che conteneva un forward di
   troppo** (i ripristini da checkpoint), e su quello ho annunciato il rapporto
   0,77 fra verificare e generare come risultato strutturale.
3. **Ho detto che il trasporto spiega il 100% del tempo del batch** assumendo 258
   domande per posizione, quando i contatori ne mostrano ~191.
4. **Ho mandato un agente su una premessa morta** (link saturo), corretta solo
   dopo che l'utente ha fatto notare che la scheda e' PCIe 4.

## Cosa resta aperto

- **Fork/join dentro il grafo**: gather concorrente alla MMVQ dei residenti
  invece che in serie. Tetto stimato -14/-22% sul forward. Patch in corso.
- **Rollback parziale del KV DSV4**: eliminerebbe i ripristini, cioe' un forward
  su tre a n-max 2.
- **Verifica per residenza**: la GPU calcola solo cio' che ha in VRAM, la CPU il
  resto, nessuno sposta niente. Toglie il trasporto E il thrashing insieme. Il
  punto duro e' `k_cpu` fisso per le forme congelate nel grafo -- ma
  `LLAMA_OVERLAP_GRIGLIA_VARIABILE` esiste e non e' mai stata accesa.
- **Prefill a 20 tok/s**: la GPU e' satura al 96% con la CPU ferma a 0,34 core.
  Non e' attesa di CPU. Traccia aperta piu' grossa del progetto.
