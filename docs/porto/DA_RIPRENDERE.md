
## SPEX — 2026-08-02, parcheggiato dall'utente

Nei log del fork: `SPEX stats ... hit_rate=0.9269 miss_per_expert=0.0697`, e in un
altro run `hit_rate=0.8216 miss_per_expert=0.1702`. E' il numero che l'utente
ricordava ("miss rate sotto il 17%") ed era preciso.

Contatore **diverso** da `[moecache]`, che sta a `hit_rate=0.099` con `cap=181` sia
sul fork sia su 0731: sono due livelli, non la stessa misura letta male.

Nove variabili nel fork (`DS4_SPEX_CAP`, `_PREFETCH_K`, `_RING_SLOTS`, `_FUSED_TOPK`,
`_CPU_PROBE_K`, `_FILE`, `_AB_STAGE`, `_DRY_RUN_STATS_EVERY`, `_HIDDEN_GPU_DRY_RUN`).
**Su 0731 non esiste nulla**: e' l'unica cosa esclusa esplicitamente dal porto.

Da riprendere DOPO la mappatura. Prima domanda: perche' era stato messo da parte.
