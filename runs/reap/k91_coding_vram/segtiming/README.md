# Part A: timing SEGMENTATO (2026-07-07) — cold-start/page-in vs steady-state

> Mandato SPEX: basta t/s "blended". Per ogni generazione: TTFT + t/s per token 1-64 / 65-256 /
> 257+ (steady-state). Separa il page-in/cold-start dal regime stabile. Pod 3090, cache=400
> (~cache reale 12GB, cosi' il page-in e' visibile), prompt frontpage. Segmenti via differencing
> (run n=64/256/576, gen_time(n)=n/t/s(n), seg = dn/(t(n2)-t(n1))). Stream separati.

## Tabella (t/s per segmento, cache=400)
| config | TTFT~ | 1-64 (cold) | 65-256 | 257-576 (steady) | pattern |
|---|---:|---:|---:|---:|---|
| **full** (no mask) | 14.5s | 2.05 | 0.98 | **0.76** | DEGRADA monotono |
| **reap keep-8** | 17.8s | 12.95 | 23.55 | **25.82** | ACCELERA (page-in→steady) |
| **reap keep-32** | 14.3s | 3.71 | 4.26 | **3.38** | ~piatto (stuck) |

*(TTFT ≈ prompt ~180 tok / prefill ~12 t/s; dominato dal prefill, ~config-indipendente.)*

## Tre regimi che il blended nascondeva
1. **full DEGRADA nel tempo** (2.05→0.98→0.76). Full routing tocca sempre nuovi esperti → la cache-400
   accumula miss → rallenta. Il blended (~0.89) nasconde che lo steady-state e' **0.76 e in calo**.
2. **keep-8 ACCELERA** (12.95→23.55→25.82). Working-set piccolo (8×40=320 < cache 400): i primi 64
   token pagano il **page-in** (cold-start 12.95), poi la cache e' calda → steady-state **25.82 t/s**
   = 2× il cold-start. Il blended (~22.6) SOTTOSTIMA lo steady-state reale.
3. **keep-32 STUCK** (~3.4-4.3). Working-set 32×40=1280 >> cache 400 → thrash parziale permanente,
   nessuno steady-state veloce. Troppo grande per entrare.

## Perche' conta (mandato SPEX)
Il t/s aggregato mescola due cose opposte: la **tassa di page-in** iniziale e il **regime stabile**.
Separandoli: (a) per le mask che ENTRANO in cache (keep-8) il vero rate di deployment e' lo
steady-state (25.8), non il blended; (b) per il full il blended NASCONDE il degrado (0.76 e in calo);
(c) keep-32 non ha uno steady veloce perche' non entra. **La velocita' reale di una config si legge
nel segmento 257+, non nel t/s aggregato.** Conferma la teoria cache: entrare in VRAM (working-set
< cache) e' cio' che sblocca lo steady-state veloce.

Caveat: n=1/cella (greedy), differencing su 3 punti (assume rate costante entro segmento), 1 prompt,
cache=400. TTFT stimato (prompt-len/prefill-t/s). Artefatti: `summary.txt` (n=64/256/576 grezzi).
