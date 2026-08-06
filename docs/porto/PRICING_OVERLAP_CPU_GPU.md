# PRICING — sovrapposizione CPU/GPU sugli esperti (prima di scrivere codice)

*Chat Jacobi, 6/8/2026 pomeriggio. Fase 1 del mandato "eventi CPU + overlap"
passato da DS4 L3 su tesi dell'utente. Regola applicata: prezzare contro le
costanti misurate PRIMA di costruire (come per Jacobi, che è morta così).*

## La struttura del guadagno (dal sorgente, non congetturata)

Oggi, per ogni strato: attenzione (GPU) → mul_mat_id esperti (GPU, che paga
trasporto mappato per i non-residenti) → strato dopo. Il tempo token del
braccio vincente: **108 ms = 69 di pavimento + 39 di trasporto** (0,953
GiB/token a 24,35 GiB/s, 44% di colpi cache).

La proposta: per ogni strato, DUE rami esperti — i residenti in cache alla
GPU, i NON residenti alla CPU (che li legge dalla RAM dove già stanno: quel
trasporto **sparisce**, non si nasconde). I rami si sommano al join.

**La dipendenza L→L+1 non morde**: l'overlap è DENTRO lo strato, fra i due
rami. Il tetto di ciò che è sovrapponibile è la sola parte esperti:
trasporto 39 + calcolo GPU esperti ~16 ≈ **55 ms dei 108**. Il pavimento
restante (~53: attenzione, dense, orchestrazione) resta seriale e NON è
promesso dal disegno.

## Il conto, con le costanti del ledger

Per token, 43 strati, 258 attivazioni, 44% residenti (misurato):
- ramo GPU (residenti, ~113 att.): calcolo ~7 ms/token, trasporto 0
- ramo CPU (non residenti, ~145 att.): 145 × 0,242 ms = **35 ms/token**
- oggi la stessa quota costa: 39 (trasporto) + ~9 (calcolo GPU) = 48 ms

Per strato: max(0,81 ms CPU, 0,16 GPU) ≈ 0,81 + costo_confine, contro 1,11
di oggi. **Guadagno lordo ≈ 13 ms/token** (108 → ~95, ~10,5 t/s, +13%)…
che è MENO del +27% stimato a monte, perché lo split 20/80 ottimo di quella
stima presuppone di scegliere CHI va alla CPU per bilanciare i rami, mentre
il criterio "non residenti alla CPU" fissa lo split a ~56/44. I due criteri
divergono: **bilanciare i rami** (ottimo ~20% CPU) vs **cancellare il
trasporto** (56% CPU). Il punto di lavoro vero sta in mezzo e va scelto:
- 56% CPU (zero trasporto): 108 → ~95 ms (+13%)
- 20% CPU (rami pari, l'80% GPU ripaga trasporto sui non-residenti che
  restano): il trasporto NON sparisce per quella quota → guadagno ~9-17 ms
  secondo il colpo cache → simile.
- CON PIÙ CACHE (la curva K3/K4 dice che i colpi salgono a 48% coi 550
  slot ma la VRAM strozza): il criterio migliore è "alla CPU solo ciò che
  la cache non tiene", e il guadagno cresce col tasso di colpi.

**Forbice onesta: +9-17 ms/token → 9,9-10,9 t/s (+8-19%) sul 9,26.**
Il +27% richiede ANCHE più residenza (cioè la scheda da 24 GB, di nuovo).

## Il costo dei confini (la variabile assassina, dal sorgente)

86 confini CPU-GPU/token (2 per strato). Tre scenari:
- threadpool persistente CON polling (esiste già:
  `ggml_backend_cpu_set_threadpool`, spin configurabile): sveglia ~1-5 µs
  → 86 × ~3 µs ≈ **0,3 ms/token**: trascurabile.
- condvar senza polling: 10-50 µs → **1-4 ms/token**: tollerabile.
- pool riavviato per pezzo (NON è il nostro caso, verificato: il pool è
  esterno e persistente): 100-300 µs → 9-26 ms → morte. Da evitare e basta.

Più il join: la somma dei rami vuole l'output CPU sulla GPU: ~4096 × f32 ×
n_token = 16 KB/strato → 0,7 MB/token su PCIe ≈ **0,03 ms/token**: niente.

## Il lavoro vero (rivisto dal sorgente)

1. **ggml**: `graph_compute` CPU asincrono (worker + il threadpool
   esistente). NOTA: per la v1 gli EVENTI possono non servire — la
   dipendenza fra split è imposta dalle sync sulle copie di input
   (`ggml-backend.cpp:1555-1575`); se il ramo CPU parte async e il join
   fa la `ggml_backend_synchronize(cpu)` bloccante DOPO che il ramo GPU è
   stato lanciato, l'overlap c'è già. Gli eventi aggiungono pipelining, non
   l'overlap di base.
2. **fork**: spezzare il mul_mat_id per strato in due per residenza
   (cache-esperti sa già chi è residente: si aggancia dove già intercetta).
   Questo è il pezzo GRANDE: cambia il grafo, tocca la bit-esattezza
   (l'ordine di accumulazione della somma dei rami va fissato), e lo
   scheduler deve assegnare i due rami a backend diversi SENZA che la
   collocazione dei pesi lo costringa (è il problema inverso del
   supports_op dell'ibrido).

## La misura che manca (5 min di macchina, da coordinare)

Il costo REALE del confine oggi: un grafo giocattolo con N split alternati
CPU/GPU, cronometrato a N crescente → ms/confine. Se esce >50 µs con
polling attivo, il conto sopra si aggiorna prima di scrivere codice.

## Verdetto preliminare (da confermare col microbench)

La leva è VIVA e prezzabile a +8-19% — più piccola del +27% sperato, sopra
la soglia del rumore (0,4-1,4%), e **ortogonale alla cache** (si compone:
più colpi → più quota GPU senza trasporto). Non è ricerca: sono due pezzi
delimitati. Il rischio tecnico è tutto nel pezzo 2 (split del grafo per
residenza). Il pezzo 1 da solo non compra niente per il regime attuale
(senza split, la CPU non ha rami MoE da sovrapporre a batch 1 con l'ibrido
attivo: oggi TUTTO il MoE di decode sta o di qua o di là).
