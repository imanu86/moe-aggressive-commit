# Banco del 35B e di Ling-3.0-tiny sulla 3060 — 25 settembre 2026

Obiettivo dell'utente: un MoE Qwen piccolo, quasi tutto residente sulla 3060, oltre i 500 t/s, con una testa MTP
buona, adattivo come il daily. Un MoE Qwen piccolo non esiste: si e' partiti dal 35B-A3B (il piu' piccolo), poi,
visto che la banda e' il tetto, si e' scesi a Ling-3.0-tiny (7,9B / 1,3B attivi). Tutte le corse: banco P0
(`avvia_blocco_q36.ps1`, copia locale con guardia MSBuild), porta 8113 isolata, greedy seed 1234, un processo
per blocco, cartelle in `D:\ds4_work\banco_35b_run`. Daily intatto (hash verificati).

## 1. Il 35B-A3B sul runtime elastico portato (profilo `fumo`, ragionamento acceso)

Desktop che occupava ~5,9 GB di VRAM. Decode in t/s; slot della cache elastica finali (resize).

| braccio | testa MTP | L01 libero | S01 JSON | accett. L01/S01 | slot (resize) |
|---|---|---:|---:|---:|---|
| A0 upstream Q4 `-fit` | Q4_0 sep. | 23,4 | 27,2 | 64/89% | — |
| A1 upstream IQ3 | interna | 26,2 | 31,6 | 64/88% | — |
| B0 elastico Q4 | nessuna | 57,0 | 47,0 | — | 73 (25) |
| B1 elastico Q4 | Q4_0 sep. | 55,7-57,6 | 60,1-63,1 | 59/83% | 58-68 (24) |
| B2 elastico Q4 | Q8_0 sep. | 52,8 | 57,5 | 63/85% | 54 (25) |
| B3 elastico Q4 | Q8_0 condivisa | 52,6 | 56,0 | 63/84% | 71 (29) |
| C0 elastico IQ3 | nessuna | 61,5 | 54,5 | — | 112 (23) |
| C1 elastico IQ3 | interna (Q2/Q3) | 54,4 | 65,5 | 61/86% | 110 (21) |
| C2 elastico IQ3 | Q8_0 sep. | 50,3 | 59,5 | 64/89% | 98 (24) |
| C3 elastico IQ3 | Q8_0 condivisa | 52,7 | 61,7 | 64/88% | 107 (23) |
| B1-M3 | Q4_0 sep. | 59,3 | 60,1 | 59/83% | 49 (9) |
| C1-M3 | interna | 58,9 | 65,6 | 61/86% | 86 (9) |

- Il runtime elastico vale 2,1-2,5x upstream. La MTP rende solo ad accettazione alta (JSON +20-30%); sul testo
  libero (~60%) e' neutra o in perdita: sul MoE ogni riga di verifica porta i suoi esperti.
- La testa Q8_0 accetta 3-4 punti in piu' ma va piu' piano: i suoi esperti stanno in RAM mappata e ogni token
  di bozza ne legge ~27 MB sul PCIe. La testa condivisa (senza embedding/output) libera VRAM ma non il passo.
- L'«IQ3_XXS» di unsloth ha gate/up IQ2_S su 39 strati: 43 MiB per slot contro 67,5 del Q4_K_M.

**Lungo a 32k** (profilo `lungo_2`, prefill freddo 32.898 token, poi decode a 32k di profondita'):

| braccio | prefill 32k | decode a 32k |
|---|---:|---:|
| A0 upstream Q4 | 768,9 t/s | 20,2 / 19,8 |
| B1 elastico Q4 + MTP | 1016,4 t/s | 50,3 / 50,2 |
| C0 elastico IQ3 | 1114,9 t/s | 45,7 / 46,7 |
| C1 elastico IQ3 + MTP interna | 1110,9 t/s | 48,8 / 46,8 |
| C1-M3 | 1105,4 t/s | 51,7 / 48,9 |

A 32k l'IQ3 non batte piu' il Q4. Colpi della cache misurati 75-83% con ~60 slot. Fase a 131k fermata su
decisione dell'utente (cambio di strada).

## 2. Contare, non cronometrare: nodi del grafo del decode (`diag_nodi.py`, GGML_SCHED_DEBUG=2)

| modello | partizioni | nodi/token | byte letti/token | tempo/token misurato |
|---|---:|---:|---:|---:|
| Ling-3.0-tiny Q4_K_M, tutto in VRAM | 2 | 1.794 | ~0,68 GB | 7,4 ms (135 t/s) |
| 35B elastico IQ3 | 2 | 2.395 | ~1,8 GB + mancanze PCIe | 16,3 ms (61,5 t/s) |

Con ~2,8 µs per nodo (calibrato su Ling): Ling = 5 ms di nodi (68%) + 2,3 ms di byte; il 35B = ~6,7 ms di nodi
+ ~5 ms di byte in VRAM + ~4 ms di mancanze sul PCIe. **Nei modelli piccoli il tetto non e' la banda ma il numero
di kernel**; il 35B tutto residente sulla 2080 Ti farebbe ~100 t/s, non 150-180 (stima corretta).

## 3. Ling-3.0-tiny (bartowski Q4_K_M, 4,58 GB, tutto in VRAM)

| | prefill | decode corto | decode a 32k |
|---|---:|---:|---:|
| upstream b10734 | 2.616 t/s a 32k | 126,8 / 128,3 | 101,3 / 99,5 |
| runtime Codex (runtime-q36, niente cache) | 2.663 t/s a 32k | 136,9 / 135,2 | 104,7 / 105,8 |

## 4. Profilo `lavoro` (C01 copia, C02 rinomina, S01/S02 JSON, S06 correzione codice, L06/L07 codice)

Con il ragionamento ACCESO quasi tutti i casi, di entrambi i modelli, sono troncati: il budget (768-1024) finisce
nel ragionamento. Per JSON/tool call/edit il ragionamento va spento. **Ragionamento SPENTO** (decode in t/s):

| | C01 copia | C02 rinomina | S06 | S01 / S02 | L06 / L07 | esiti controllati |
|---|---:|---:|---:|---:|---:|---|
| 35B C1-M3 (MTP) | 68,4 | 65,7 | 62,9 | 54,9 / 51,0 | 69,2 / 69,3 | 5/5 |
| Ling senza bozza | 132,5 | 134,1 | 140,1 | 125,8 / 130,5 | 136,1 / 136,3 | 4/5 |
| **Ling + ngram-simple** | **806,6** | **530,9** | 186,8 | 122,8 / 130,7 | 131,3 / 120,6 | 4/5 |
| Ling + ngram-mod (n-max 16) | 513,1 | 389,6 | **200,0** | 126,0 / 124,2 | 141,6 / 136,9 | 4/5 |
| Ling + mod,simple combinati | 744,8 | 524,2 | 186,5 | 122,6 / 125,0 | — | 4/5 |

Accettazioni: ngram-simple 96% (C01), 88% (C02); ngram-mod 100% (C01), 98% (C02), 79% (S06). ngram-map-k inutile
(6-23%). Esiti (`valuta_lavoro.py`): la bozza e' senza perdita (testi identici fra le varianti di Ling); copia e
rinomina 99% delle righe prodotte identiche (troncate dal budget per costruzione: il file e' ~4.000 token);
S02 e S06 corretti; **Ling sbaglia S01** (10 x 1,888 = 18,88 invece di 48 x 10 x 1,888 = 906,24), il 35B no.

**Perche' la bozza vola su Ling e non sul 35B:** Ling e' limitato dai nodi, 16 righe di verifica nello stesso
grafo costano quasi come una; nel 35B ogni riga di verifica porta i suoi esperti dalla RAM.

## 5. Conclusioni e prossimi passi

- Sulla 3060 i 500-800 t/s ci sono con Ling + ngram-simple quando l'output ricalca il contesto (copia, rinomina,
  refactoring, edit); sul testo nuovo 125-140 t/s (2x il 35B). Il 35B resta migliore nel ragionamento.
- Assetto proposto: Ling (ngram-simple, ragionamento spento) per il lavoro veloce; 35B o Flash-Next quando serve
  ragionare; con la 2080 Ti il 35B li' e Ling sulla 3060.
- Leve aperte: testa di bozza addestrata per Ling (sul testo nuovo l'n-gram non trova niente; Ling e' node-bound,
  quindi una testa MTP/DSpark renderebbe 2-3x); fusione di kernel per scendere sotto i 1.794 nodi; per il 35B
  fermare gli svuotamenti della cache (M3 + tetto di slot), `LLAMA_MOE_HIT_REPORT=0`, `-c` piu' piccolo.

Strumenti: `sequenza_q36.py` (blocchi in serie + tabella), `diag_nodi.py` (nodi/partizioni), `valuta_lavoro.py`
(esiti), `banco_q36.py` (copia locale del banco con il profilo `lavoro`), `genera_preset_q36.py`.
