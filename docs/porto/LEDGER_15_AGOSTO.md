# LEDGER PORTO — 15 AGOSTO 2026

## Bracci e verdetti nuovi

| Braccio | Forma | Risultato | Correttezza | Verdetto |
|---|---|---:|---|---|
| Residente denseFA + staging + HC scheduler, long | 101.597+64, ctx150k, B/UB2048, 3 run | prefill 110,7005 / 111,0928 / 126,8021; media **116,1985**. Decode media **7,9492** | output identico/coerente, p1=.61702, zero errori | **Nuova base lunga corretta** |
| Profilo CPU + packetizer phase-safe + bsparse | 20.749+64, ctx40k, UB12288 | crash al primo draft | `markov_w1`, poi diagnosticato `i01=-1` | **Bocciato, niente repliche** |
| Diagnostica packetizer 1 | 6.720 token, ctx12k, UB8192 | crash | `markov_w1.weight`, secondo argmax resta -1 | packetizer-off nel draft non ripara hidden/KV prefill |
| Profilo CPU + packetizer 0 + bsparse | 6.716 token effettivi, ctx12k, UB8192 | **259,39 t/s** prefill, poi crash; PC bloccato | stesso `markov_w1`, `i01=-1` | packetizer assolto; non rilanciare identico |
| EXACT_DMA kernel-spin | warm-up target, nessuna richiesta | fermo al primo comando `seq=1 strato=0 miss=8`, poi `unspecified launch failure` | nessun output; nessun B t/s consumato | **Falsificato** |
| EXACT_DMA memops64/runtime | warm-up target, nessuna richiesta | fermo al primo comando; query/sync runtime non fanno progredire la coda reale | microtest wait/write isolato verde, grafo reale bloccato | **Falsificato** |
| EXACT_DMA memops64/Driver API, target graph off | warm-up target, nessuna richiesta | fermo al primo comando anche con `cuMemcpyHtoDAsync`/`cuStreamSynchronize` | microtest concorrente 8 MiB verde, grafo reale bloccato | **Falsificato e codice rimosso** |
| Decode whole-FFN combinato | 1.200 token | **14,57 t/s**, p1=.86752 | output coerente, length | **-9,35%, respinto; gia' in Ledger 14** |
| Decode shared-overlap, cache base-parity | 1.200 token | **14,55 t/s**, p1=.86752 | output coerente, length | **-9,48%, respinto; codice rimosso** |
| RCI mapped, fixture fine | 64 token | **11,65 t/s**, p1=.92308 | output coerente, length | caricamenti fini PCIe inefficaci |
| RCI mapped, fixture burst `uint4` | 64 token | **14,02 t/s**, p1=.83333 | output coerente, length | recupera la coalescenza; ammesso al solo B |
| RCI mapped burst, MASSA2 473+12 | 1.200 token | **14,97 t/s**, 66,81 ms/token, p1=.84129 | NeuraForge HTML coerente, length, zero ID invalidi | **-6,86%, respinto; nessuna replica, codice rimosso** |
| Diagnostica lane CPU K=2 | 64 token | **13,39 t/s**, p1=.77273; 6.708 assegnazioni CPU: 5.809 miss, 899 residenti | output coerente | solo **13,4%** del ramo CPU era gia' residente; lane adattiva non ha budget macro |
| CPU FFN super-op v1 | 64 token | **12,60 t/s**, p1=.77273; worker CPU 2,073 ms/layer | output identico, stesso SHA della fixture | peggiore della fixture diagnostica; audit codice, niente B 1.200 |
| CPU FFN super-op v1, accessi contigui | 64 token | **11,40 t/s**, p1=.77273; worker CPU 2,454 ms/layer | output identico, stesso SHA | chiaramente peggiore; **respinto e codice rimosso** |
| GPU lane B transiente, multi-stream smoke 1 | nessuna completion | errore CUDA `capturing stream has unjoined work` | nessun output | fork B aperto, consumer rimasto CPU; non conta come B |
| GPU lane B transiente, multi-stream smoke 2 | nessuna completion | deadlock al primo decode dopo `cached n_tokens = 1` | nessun output | pin CUDA esplicito non risolve il ciclo WDDM/graph; **famiglia multi-stream respinta e rimossa** |

## Evidenza diagnostica

```text
GET_ROWS_Q invalid index: src0='markov_w1.weight'
src1='CPU#node_509#0' dst='node_510'
i=0 i01=-1 ne01=129280 src1_ne=[1,1,1,1]
```

`dflash.cpp` costruisce il secondo indice Markov con `argmax(col)`; il kernel
CUDA lascia -1 se la colonna è tutta NaN/non-finita. La corruzione è già negli
hidden/KV DFlash prodotti durante il prefill full, non un indice host casuale.

## Decisione

- 275,506 t/s resta misura target-only/non certificata, non SOTA end-to-end.
- SOTA lunga corretta = prefill 116,1985 t/s.
- Packetizer non è causa necessaria: con packetizer 0 il guasto resta.
- Prossimo discriminatore prefill: block-sparse ON con densi residenti,
  packetizer 0, UB2048/4096, completion >=32; niente wildcard CPU.
- Il solo overlap DMA ha tetto 19,453 t/s e non basta.
- Aggiornamento: exact-demand H2D con rendez-vous host interno al grafo reale e'
  bocciato; non ripeterlo.
- Anche whole-FFN/shared-overlap (14,55--14,57) e RCI MMVQ diretto mapped
  (14,97) sono bocciati e rimossi. La base copia ogni miss dal PCIe una sola
  volta e poi calcola dalla slab VRAM: non esiste una seconda lettura PCIe da
  fondere.
- Lo split CPU/GPU per residenza e' gia' nella base a K=2. Il prossimo braccio
  deve essere ortogonale alle famiglie gia' falsificate e dimostrare a priori
  un budget vicino ai 12,214 ms/token necessari, non un altro incremento locale.
- La misura esatta dei tre MMID CPU isolati e' 414,022581 us gate + 414,022581 us
  up + 141,364466 us down = **0,969410 ms/layer**. Il super-op manuale non ha
  raggiunto quel tetto: ha perso blocking/scheduling del motore MMID esistente.
  Non riscrivere di nuovo i dot CPU; preservare i kernel esistenti.
- Candidato macro successivo: sostituire le due route CPU con una banca GPU
  transiente **exact-demand device-only**, senza host rendez-vous e senza
  inquinare A. A ogni row-layer la diagnostica vede due route CPU, in media
  1,732 miss dopo il filtro residenti: circa 11,69 MiB, ~0,469 ms fisici a
  24,35 GiB/s. Il cancello richiede ridurre il critical path di almeno
  **0,700 ms/layer**; staging e calcolo transiente devono sovrapporsi al ramo
  GPU delle quattro route residenti/miss.
- Aggiornamento: la variante multi-stream e' falsificata da cattura non
  ricongiunta e poi deadlock reale; non ripeterla, neppure con graph-off. Resta
  distinto un solo sottocancello **single-stream**: copia esatta di 2 esperti
  (~0,541 ms) seguita dagli MMVQ locali (~0,158 ms stimati), senza eventi o
  stream esterni. Se il critical path misurato non batte 1,056 ms/layer, si
  chiude anche la banca B exact-demand.
