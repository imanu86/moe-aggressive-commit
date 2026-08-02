
## SPEX — 2026-08-02, parcheggiato dall'utente

Nei log del fork: `SPEX stats ... hit_rate=0.9269 miss_per_expert=0.0697`, e in un
altro run `hit_rate=0.8216 miss_per_expert=0.1702`. E' il numero che l'utente
ricordava ("miss rate sotto il 17%") ed era preciso.

**Cos'e' (detto dall'utente, che l'ha inventato): un sistema di PREDIZIONE basato
su hidden layer con Markov.** Non e' una politica di cache: non sceglie cosa
tenere, predice cosa servira' e lo va a prendere prima.

Per questo il confronto con `[moecache]` (`hit_rate=0.099`, `cap=181`, uguale su
fork e su 0731) non e' fra due cache: sono due cose diverse.

E per questo l'82-93% non contraddice il tetto di Belady al 47,8% misurato il 2/8:
Belady limita lo **sfratto reattivo a capienza fissa**. Un predittore che
prefetcha gioca un'altra partita. Coerente con l'altra misura dello stesso giorno:
il 90,3% degli accessi va a esperti gia' visti, ma su distanze piu' lunghe di
quanto una cache reattiva possa ricordare -- cioe' esattamente il buco che un
predittore copre.

Nove variabili nel fork (`DS4_SPEX_CAP`, `_PREFETCH_K`, `_RING_SLOTS`, `_FUSED_TOPK`,
`_CPU_PROBE_K`, `_FILE`, `_AB_STAGE`, `_DRY_RUN_STATS_EVERY`, `_HIDDEN_GPU_DRY_RUN`).
**Su 0731 non esiste nulla**: e' l'unica cosa esclusa esplicitamente dal porto.

Da riprendere DOPO la mappatura. Prima domanda: perche' era stato messo da parte.
