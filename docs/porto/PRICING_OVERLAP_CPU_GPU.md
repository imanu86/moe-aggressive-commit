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

## Il conto, con lo SPLIT COME PARAMETRO (rivisto su nota DS4 L3)

Costanti (ledger): 258 attivazioni/token, 113 residenti (44%), 145 no;
per esperto: CPU 0,242 ms, GPU 0,063 ms (16,3/258), trasporto mappato
0,271 ms. Oggi la parte esperti costa 39 (trasporto) + 16,3 (calcolo GPU)
= **55,3 ms/token**. Sia x = non-residenti affidati alla CPU:

    ramo CPU:  0,242·x
    ramo GPU:  7,1 + (145−x)·(0,271+0,063)   ← i non-residenti lasciati
                                                alla GPU RIPAGANO il bus
    t_esperti = max(rami) + sync

I due criteri "puri" sono entrambi sub-ottimi, il massimo sta in mezzo:

| x (CPU) | ramo CPU | ramo GPU | t_esperti (sync 9,3) | token | t/s | Δ |
|---|---|---|---|---|---|---|
| 52 (20%) | 12,6 | 38,2 | 47,5 | 100,2 | 10,0 | +8% |
| **96 (ottimo)** | **23,3** | **23,4** | **32,6** | **85,3** | **11,7** | **+27%** |
| 145 (tutti) | 35,1 | 7,1 | 44,4 | 97,1 | 10,3 | +11% |

L'equazione di bilancio: 0,242x = 7,1 + (145−x)·0,334 → **x* ≈ 96** (66%
dei non-residenti alla CPU). Il "+44%" della stima a monte presupponeva il
ramo GPU tutto-residente (12,3 ms): vero solo con molta più cache — è il
regime da 24 GB travestito. x* si sposta col tasso di colpi: più residenza
→ più capienza GPU libera → più quota CPU trasferibile → il guadagno
CRESCE con la cache (le due leve si compongono, non competono).

**Forbice onesta: 10,0-13,1 t/s (+8-41%), centrata a 11,7 (+27%) col
confine a 108 µs; l'estremo alto richiede confine ≤ 30 µs (polling).**

## Il costo dei confini (la variabile assassina)

**~108 µs/confine, GIÀ NEI DATI** (derivazione DS4 L3): il "resto" della
configurazione ibrida (86 confini/token) è 62,0 ms, quello della cache W=0
(zero confini) è 52,7 → 9,3 ms / 86 = 108 µs. È un residuo di sottrazione
fra configurazioni diverse, non una misura pulita: il microbench (sotto)
serve a FALSIFICARLO, non a scoprirlo. Come ordine di grandezza colloca il
sistema attuale nello scenario intermedio dei tre:

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

## Verdetto preliminare (da confermare col microbench di falsificazione)

La leva è VIVA: **+8-41% secondo split e confine, +27% (11,7 t/s) al punto
di lavoro ottimo x*≈96 col confine a 108 µs** — sopra la soglia del rumore
(0,4-1,4%) di un ordine di grandezza, e **si COMPONE con la cache** (più
colpi → x* più alto → guadagno maggiore). Non è ricerca: due pezzi
delimitati. Il rischio tecnico è tutto nel pezzo 2 (split del grafo per
residenza: bit-esattezza dell'ordine di accumulazione al join, e lo
scheduler non deve farsi dettare l'assegnazione dalla collocazione dei
pesi). Il pezzo 1 da solo non compra niente per il regime attuale: senza
split, a batch 1 con l'ibrido il MoE di decode sta TUTTO da una parte —
non c'è niente da sovrapporre finché il grafo non ha due rami.
