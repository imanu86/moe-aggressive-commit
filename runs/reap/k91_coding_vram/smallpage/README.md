# Task piccolo-completo (2026-07-07) — il render VERO, non "qualche riga di CSS"

> Domanda utente: non basta "produce qualche riga coerente di CSS", serve una PAGINA
> COMPLETA che renderizza. Task minimo (card + h1 + p + bottone con alert) che il modello
> FINISCE in ~600 tok. Pod 3090 (R2: modello + binario PACE prebuilt, no build), cache-1024,
> n=1200. Render verificato in Chrome + snapshot DOM.

| config | rep-rate | renderizza | bottone funziona | t/s | verdetto |
|---|---:|:-:|:-:|---:|---|
| **full** | 0.00 | ✅ card completa | ✅ `addEventListener` corretto | 3.6 | **pagina che funziona** |
| **PACE** | 0.01 | ✅ card completa (h1+p+btn) | ❌ JS rotto: `.clicked(){}` invalido | 5.2 | renderizza, bottone morto |
| static-23 (tok0) | 0.64 | ⚠️ card + leak `</` + ripetizione | ❌ | 19.3 | malformata |
| w40 direct | 0.45 | ❌ degenera | ❌ | 16.2 | loop |
| PACE breath-K0 | 0.63 | ❌ degenera | ❌ | 4.6 | loop |

## Verdetto (il punto dell'utente, confermato)
Guardando la **pagina vera** (non le righe di CSS): il costo della mask si vede nei **dettagli
fini del JS**. `full` scrive `getElementById('hi').addEventListener('click',...)` — funziona.
`PACE` scrive `getElementById('hi').clicked() { }` — sintassi inventata, bottone morto, ma la
STRUTTURA (card, titolo, bottone, CSS) è perfetta. Le config statiche/aggressive (static23, w40,
paceK0) degenerano proprio.

Gerarchia sul task piccolo-finibile: **full (funziona) > PACE (renderizza, JS rotto) > static/w40
(malformato/degenere)**. PACE-default è il migliore tra i mascherati (unica card pulita), ma la
2-bit + potatura rompe la sintassi JS fine. NB: PACE-default (breath keep-64) pulito, PACE-breath-K0
(256) degenera — il respiro troppo largo peggiora, non migliora (dato, controintuitivo).
Caveat: n=1/config, 1 task.
