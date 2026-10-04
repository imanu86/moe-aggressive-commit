# Testa in VRAM, coda su CPU a richiesta: schermo offline (braccio B)

**Esito: con l'ordine statico dei neuroni l'idea non passa; con selezione dinamica
per token passa solo l'oracolo, e a un guadagno stimato di circa +10%.** Lo schermo
usato (errore relativo L2 della somma routed, media <=3%, P99 <=10%) si e' poi
rivelato troppo severo: vedi `../20261004_routed_keep/RESULTS.md`. I numeri qui sotto
restano validi come ordinamento relativo delle varianti, non come verdetto assoluto.
Braccio A (kernel, end-to-end) non eseguito, come da protocollo "B prima di A".

## Dati

Tracce del modello completo gia' registrate (`.codex_runs/20261004_ngram_memory_v2`):
tre continuazioni greedy da 512 token (codice, spiegazione, ragionamento), layer
0/1/35/36, 61.440 chiamate esperto con `h[640]`, peso router e uscita replay GPU.
`down` decodificato dal GGUF (IQ4_NL/Q2_0); `gate`/`up` (IQ2_XXS/IQ2_XS/IQ3_XXS) con
gguf-py 0.19. Controlli: proiezione Python contro replay 0,8% mediano (Q8 di `h` nel
kernel); `h` ricalcolato da `x` contro replay 0,6% mediano.

## Statico (`analyze_head_tail.py`, `screen-v1.json`)

Ordine per esperto costruito sugli altri due testi (leave-one-text-out), copertura
81–99% delle chiamate; esperti mai visti ordinati per norma della colonna `down`.
Testa 256/320/384/448 neuroni, coda calcolata per i primi k esperti per peso o
sopra una soglia, piu' un oracolo a parita' di budget.

| Testa | Coda calcolata | Ordine statico (energy), media peggiore | Oracolo per token |
|---:|---|---:|---:|
| 448 (70%) | mai | 45,8% | 4,0% |
| 448 (70%) | top-2 per peso | 30,4% | 2,6% |
| 448 (70%) | top-3 per peso | 26,3% | 2,2% |
| 320 (50%) | top-2 per peso | 40,4% | 7,0% |

L'ordine statico e' appena meglio del taglio casuale (circa sqrt(0,3) = 55% per il
30% dei neuroni): quali neuroni contano cambia da token a token. Calibrare su altri
testi aiuta pochissimo rispetto alla sola norma dei pesi (52,3%).

## Dinamico per token (`analyze_dynamic.py`, `dynamic-v1.json`)

Nessuna calibrazione. Si calcola prima un segnale economico, si tengono i k*640
neuroni migliori, si calcola il resto solo per quelli. Opzionalmente i primi r
esperti per peso restano interi.

| Neuroni tenuti, r=2 | gate-first | up-first | oracolo `|h|*||d||` | byte letti (down trasposto) |
|---:|---:|---:|---:|---:|
| 50% | 16,0% | 15,1% | 7,0% | 0,72 |
| 60% | 11,6% | 10,6% | 4,5% | 0,78 |
| 70% | 7,6% | 6,8% | 2,6% | 0,83 |

Errore = media peggiore su testi e layer. I segnali realizzabili stanno a meta' tra
il taglio casuale e l'oracolo. A parita' di byte (-20%) la selezione gate-first sbaglia
meno che togliere due esperti interi (12% contro 21%).

## Stima di velocita' (`estimate_speed.py`), non misurata

Finestra = G + C con G parte GPU e C esperti CPU dai log del 4 ottobre (codice 41,6+69,0
ms, spiegazione 34,9+41,2). Testa al 70% e coda per top-2: +21–27%; testa al 50%:
+40–52%. Modello grezzo: non include lavoro GPU, overhead e sincronizzazioni delle code.

Daily, config e launcher non toccati. Calcolo solo CPU; nessun motore avviato.
