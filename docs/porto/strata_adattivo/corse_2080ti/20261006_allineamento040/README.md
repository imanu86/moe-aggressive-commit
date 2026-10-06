# Allineamento del fork a upstream 0.1.40 (6/10)

Fork `imanu86/Strata-2080Ti` main `0f7ec7b` = merge di upstream v0.1.40 (`1735d64`) nel main `0485ca2`; punto di
ripristino `D:\ds4_work\strata\ripristini\20261006_084929_allineamento040`. Exe di laboratorio
`20261004_routed_keep/build-m040` (merge) e `build-up0140` (upstream puro, `git archive` del tag, `build_up0140.py`).

## Identità

- CTest 99/101 passati, 2 saltati; falliti per l'ambiente `ple_parity` (modello in un percorso relativo) ed
  `expert_multi_test` (chiede AVX512).
- `q2_exact_parity`: 504 casi, 570634 righe, 0 differenze.
- `iq256_dump`: identico byte per byte a `20261005_pr930/dump_pr930*.bin`, normale e gather.
- Teacher forcing a posizionamento fisso (`tf_fixed.sh`, esiti in `20261004_routed_keep/tf_fixed_m040.txt`):
  - explain: merge identico byte per byte a upstream 0.1.40 puro; entrambi cambiano 8 posizioni su 595 rispetto alla
    0.1.39 (argmax e top-5 invariati, KL medio 2e-10).
  - code: il fork diverge da upstream gia' in 0.1.39 (enc vs up0139, KL 6,5e-4, argmax 99,4%) e con la stessa misura in
    0.1.40 (m040 vs up0140); rispetto alla 0.1.39 del fork il merge cambia 2 posizioni su 169, upstream altrettante.
  - Senza `--prompt-cache-tail` nessun esito cambia: la divergenza su code non e' il checkpoint di coda.

## Test breve 131k (config Daily, una corsa per braccio, B prima di A)

| braccio | L01 t/s | L02 t/s | ms/finestra L01 | CPU host L01 |
|---|---|---|---|---|
| B merge 0.1.40 | 48,2 | 44,4 | 41,0 | 11,9 ms |
| A Daily 0.1.39 r1 | 42,5 | 39,1 | 49,4 | 16,0 ms |

Prefill uguale (983 contro 979 tok/s). Il guadagno sta nel lavoro host per layer; probabilmente e' il nuovo
`--host-core` di upstream (thread host sul core 0, worker sui core pari). Una corsa sola per braccio e video nel
browser durante B (3,6 GB, 35% GPU): da confermare con il bis.
