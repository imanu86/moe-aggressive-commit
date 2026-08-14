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
- Priorità immediata: decode macro exact-demand DMA + riduzione gestione; il solo
  overlap DMA ha tetto 19,453 t/s e non basta.
- Aggiornamento: exact-demand H2D con rendez-vous host interno al grafo reale e'
  bocciato; non ripeterlo. Prossimo macro: super-op FFN decode interamente GPU,
  expert-tile/fusione DwarfStar, trasporto FORK invariato nel primo sottocancello.
