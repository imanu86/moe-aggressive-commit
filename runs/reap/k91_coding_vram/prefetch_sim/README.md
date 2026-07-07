# Part C-T2: prefetcher layer-ahead — "recall != velocita'" (2026-07-07)

> Mandato SPEX (il critico): il dense-oracle predice il routing a valle (L3->L4 recall@23=0.73),
> ma un segnale accurato NON e' automaticamente velocita'. Il trappolone-PACE: provala. Attento a
> recall x lead-time (1 layer di anticipo basta a nascondere il fetch SSD? o serve predire 2-3
> avanti dove il recall cala?). Qui: SIMULAZIONE cache LRU su trace reale (hidden 0007 + routing
> 0006, 299 token, split 70/30). Misuro l'HIT-RATE (= meno stall SSD = piu' veloce) di:
> nessun-prefetch vs n-gram-prefetch vs layer-ahead(d=1,2,3), a varie dimensioni cache.

## Recall per distanza di anticipo (budget prefetch P=23)
| lead d | recall@23 | lead-time |
|---|---:|---|
| d=1 | 0.631 | 1 layer di compute |
| d=2 | 0.622 | 2 layer |
| d=3 | 0.610 | 3 layer |

**Il recall NON cala con la distanza** (0.63→0.61 da d=1 a d=3). → si puo' predire 2-3 layer avanti
(piu' lead-time per nascondere letture SSD lente) senza perdere accuratezza. Il "trappolone"
recall-vs-lead-time **non si verifica** qui.

## Hit-rate cache simulata (test), P=23
| cache | no-prefetch | n-gram | **ahead d=1** | ahead d=2 | ahead d=3 |
|---:|---:|---:|---:|---:|---:|
| 120 | **0.000** | 0.334 | **0.616** | 0.591 | 0.565 |
| 200 | 0.000 | 0.334 | 0.616 | 0.591 | 0.565 |
| 400 | 0.369 | 0.369 | 0.616 | 0.591 | 0.565 |
| 800 | 0.556 | 0.556 | 0.616 | 0.591 | 0.565 |

## VERDETTO: sì, il recall si traduce in velocità (e il guadagno e' massimo dove serve)
1. **Il prefetch layer-ahead DISACCOPPIA l'hit-rate dalla dimensione cache**: 0.616 costante anche
   a cache=120, dove no-prefetch = **0.000** (thrash totale). Prefetchi just-in-time cio' che
   servira' → non ti serve una cache grande per tenerlo. **Esattamente lo scenario 12GB reale**
   (cache piccola): il prefetch la rende utile dove da sola collassa.
2. **Batte n-gram a ogni cache** (0.616 vs 0.33-0.56). Il segnale hidden-probe > autocorrelazione
   temporale del routing.
3. **recall(0.63) ≈ hit-rate(0.616)**: il prefetch e' efficiente, poco spreco da eviction → il
   recall si converte quasi 1:1 in hit-rate. QUESTA volta recall ~ velocita' (a differenza di PACE,
   dove il segnale c'era ma il controllo non convergeva).
4. Con lead d=2/3 (per nascondere SSD piu' lenti) l'hit-rate scende poco (0.59/0.57) → margine reale.

## Prossimo passo (engine, non simulato)
Questo e' un test di HIT-RATE simulato — il t/s vero dipende dal rapporto SSD-read-time /
compute-time. Il segnale e' promettente abbastanza da giustificare una patch ds4 che: al layer M-d
calcoli la hidden → probe (ridge+PCA, embeddabile) → prefetch async dei top-23 per M → misura t/s
steady-state reale. Caveat: 1 trace (prompt coding, 299 token), probe per-coppia-layer ridge+PCA(48),
budget P=23. Tool: `scripts/prefetch_sim.py`. Dati grezzi: `results.txt`.
