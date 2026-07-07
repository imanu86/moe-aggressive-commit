# Dense/early-layer routing oracle (2026-07-07) — primo segnale per SPEX-main

> Mandato SPEX-main: i layer densi 0-2 girano per primi, sono residenti, costano poco. Si può
> usare la loro hidden per PREDIRE quali esperti instraderanno i layer MoE profondi → prefetch
> anticipato → nasconde la latenza SSD? Predittore su hidden-state (NON sui logprob del router,
> che erano morti). Pod 3090, ds4+0007(hidden)+0006(routing), prompt coding, n=299 decode.
> Metrica: recall@k = frazione dei 6 esperti realmente instradati che stanno nei top-k predetti.
> Baseline: n-gram (routing del token precedente) + caso (23/256=0.09). Split temporale 70/30.

## ⚠️ Vincolo della cattura: densi 0-2 solo in prefill
Il patch 0007 dumpa l'hidden di **tutti i 43 layer in PREFILL** (pos 0-72) ma in **DECODE solo i
layer MoE 3-42**; il routing (0006) è **decode-only**. → zero overlap densi↔routing in decode.
**Non posso testare "denso L0-2 → routing decode" con questa cattura** (servirebbe un 0007 che
dumpi anche i densi in decode — follow-up). Testo invece il proxy più vicino e più utile al
prefetch: **hidden del primo MoE (L3, = uscita front-end denso + attention di L3) → routing dei
layer profondi.** L3 è dove avresti la hidden PRIMA di calcolare L4+.

## Risultato: c'è segnale reale, forte per i layer vicini, che decade con la profondità

| src→tgt | recall@6 | recall@12 | **recall@23** | n-gram@23 | caso@23 |
|---|---:|---:|---:|---:|---:|
| L3→L4 | 0.511 | 0.633 | **0.731** | 0.326 | 0.090 |
| L3→L5 | 0.393 | 0.493 | 0.589 | 0.372 | 0.090 |
| L3→L6 | 0.469 | 0.580 | 0.656 | 0.291 | 0.090 |
| L3→L8 | 0.507 | 0.607 | **0.685** | 0.317 | 0.090 |
| L3→L12 | 0.387 | 0.520 | 0.596 | 0.409 | 0.090 |
| L3→L22 | 0.317 | 0.433 | 0.520 | 0.431 | 0.090 |
| L3→L32 | 0.170 | 0.265 | 0.354 | **0.435** | 0.090 |
| L3→L42 | 0.354 | 0.485 | 0.550 | 0.209 | 0.090 |

Upper-bound adiacente (hidden del layer M-1 → routing M): **L3→L4 0.731, L9→L10 0.807, L41→L42 0.683.**

## Verdetto (primo segnale, positivo con struttura)
1. **Il segnale c'è ed è forte**: recall@23 0.35–0.73 vs caso 0.09 → l'hidden di un layer precoce
   porta informazione reale sul routing a valle. **Batte l'n-gram di ~2× per i layer vicini**
   (L3→L4 0.73 vs 0.33; L3→L8 0.69 vs 0.32).
2. **Decade con la distanza**: L3→L4 0.73 → L3→L32 0.35. Più profondo il target, meno L3 lo predice
   (il routing profondo dipende da calcolo intermedio invisibile a L3). **Ai layer molto profondi
   l'n-gram pareggia o vince** (L3→L32: n-gram 0.435 > probe 0.354) → il routing profondo è più
   *stabile nel tempo* che *predicibile-da-L3*.
3. **Il pattern prefetch pratico = layer-ahead**: usare la hidden del layer M-1 per prefetchare gli
   esperti di M dà **recall@23 ~0.68–0.81** (adiacente). Cioè: mentre M-1 calcola, predici i top-23
   esperti di M e li prefetchi → ~70-80% degli esperti che serviranno sono già in cache. Con 1
   layer di lead-time, esattamente la finestra che serve per nascondere la latenza SSD.

## Implicazione per il prefetch
Un prefetcher su hidden-probe **layer-ahead** (M-1→M, ~0.7-0.8 recall@23) è nettamente meglio di
n-gram e di nessun-prefetch. Il "salto lungo" front-end→profondo (L3→L42) è più debole ma comunque
> caso — utile come prefetch grossolano di secondo livello. **Combinare probe (vicino) + n-gram
(profondo/stabile)** coprirebbe entrambi i regimi. Prossimo passo per il claim puro di SPEX-main
(densi 0-2 → tutto il MoE): un 0007 che dumpi i densi anche in decode, poi ri-misura L0/L1/L2→L3..42.

Caveat: 1 prompt (coding), n=299 decode, split temporale singolo, ridge+PCA(48) alpha=10 (non
tunato). recall su top-23 (budget prefetch 9%); a budget diverso i numeri cambiano. Artefatti:
`scripts/dense_oracle.py`, trace su pod (hidden.bin 123MB, routing.csv).
