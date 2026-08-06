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

## Il costo dei confini — MISURATO il 6/8 sera (LLAMA_SONDA_CONFINI)

**Pedaggio totale ≈ 3,15 ms/token = 72 µs/confine** (sonda nel grafo vero,
braccio F3 ibrido, finestra marginale 550→600 grafi): conteggio 86,9-87,0
split/grafo (l'86 assunto regge); calc CPU marginale 65,55 contro 62,4 da
FLOP → wake+plan. **CHIUSO 6/8 notte col timer sync-vs-copia** (quattro
finestre marginali indipendenti sulla stessa run ibrida, copie stabili
all'1%):

    copie degli ingressi   3,29 ms/token = 37,8 µs/confine
    risveglio+piano CPU    3,43 ms/token = 78,9 µs/confine
    sync                  44,53 ms/token = attesa di calcolo GPU vero

La conferma NON identitaria che mancava: il timer separa sync e copie
DENTRO ingressi — 93% attesa, 7% copie, nessun residuo inspiegato. La
distinzione che il pricing adotta (proposta DS4 L3, giusta): le COPIE
sono costo STRUTTURALE del disegno (le attivazioni attraversano comunque,
e il join per-esperto ne aggiunge 0,16), non pedaggio recuperabile; il
PEDAGGIO vero è il risveglio+piano: **3,4 ms/token = 79 µs/confine**,
fascia condvar, che il polling può limare.

**Le due voci scalano con GRANDEZZE DIVERSE (gemello H2, 6/8 notte): le
copie coi BYTE, il risveglio col CONTEGGIO.** H1 ibrido: 87 attraversa-
menti, copie 3,29 (37,8 µs l'uno); H2 cache: 5 attraversamenti, copie
1,63 (326 µs l'uno) — stessa struttura, byte diversi. Il 37,8 è una
MEDIA su attraversamenti di taglia diversa, NON una costante: chi domani
lo moltiplicasse per un conteggio diverso sbaglierebbe. Nel pricing si
addebita il TOTALE (~3,3 ms/token, stessa struttura fork/join per
strato), mai l'unitario. Nota di contorno per pricing FUTURI sulla
config cache: lì il residuo fuori-loop è 21 ms (~19% del token, replay
del grafo CUDA presumibilmente), non i 4 dell'ibrido — da capire prima
di prezzare qualsiasi cosa su quella configurazione. La sottrazione storica (11,0)
conflazionava ~7,6 ms di dispatch. Unica stima residua nella catena: il
62,4 da FLOP — un suo errore del 20% muove il finale dell'1%.
**Numero di lavoro CHIUSO: tassa 3,4 → all'ottimo x*≈91-96 con -t 7:
12,3-12,6 t/s = +33-36%.** Storia della stima (per il registro del metodo):

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

## Decisioni di disegno FISSATE (concordate con DS4 L3, 6/8 pomeriggio)

1. **Bit-esattezza comprata, non sperata**: i due rami restituiscono i 6
   risultati per-esperto SEPARATI e il join accumula nell'ORDINE D'INDICE
   originale → ordine identico a oggi per costruzione. Costo: 6×4096 f32 ×
   43 strati = 4,0 MiB/token = 0,16 ms (0,2%). Il join per-parziale è
   un'ottimizzazione successiva, con la proprietà già in tasca.
2. **Il cancello SHA giusto**: stabile fra ripetizioni della stessa config,
   e uguale al braccio CACHE W=0 (il vero predecessore) — NON al metro, che
   ha gli esperti su CPU e un altro ordine di accumulazione (riga 98:
   c1c7c5c3 vs metro divergente "legittimamente"). "SHA = metro" come
   cancello ucciderebbe un'implementazione corretta.
3. **-t 7, non 8, nel regime di sovrapposizione**: un core nutre la GPU.
   A 7/8 di resa CPU: x* = 90,8, rami 25,1/25,1, totale 87,1 ms =
   **11,48 t/s (+25%) — numero di lavoro**. (La tariffa confini 9,3 ms è
   PESSIMISTICA: è il percorso bloccante che il pezzo async toglie; con
   eventi il residuo è il risveglio del pool → 11,5 è pavimento, 13,1 non
   richiede niente di esotico.)
4. **Il ramo CPU legge dalla RAM, mai far leggere la GPU dal bus**: il
   punto zero-copy (riga 98: 6,35 t/s = 157,5 ms, ZERO confini, 33 ms PIÙ
   LENTO dell'ibrido a 86) dimostra che il pedaggio PCIe a batch 1
   seppellisce qualunque risparmio di confini. Dare alla CPU i non
   residenti non è bilanciamento: è toglierli dal bus.
5. **Ordine di costruzione**: split del grafo PRIMA, sequenziale, bit-
   esattezza verificabile subito e senza eventi; l'async DOPO. Bonus dello
   split sequenziale da misurare da solo: −26 MiB/token dal bus (96
   esperti che smettono di attraversare).

## La misura del confine (due strumenti complementari)

- **Sonda nel grafo vero** (branch jacobi afa62f0, GGML_SCHED_PROFILO=1):
  ingressi (sync+copie), calcolo CPU bloccante, lanci — per grafo, nel
  regime ibrido reale a 86 confini + controllo cache-W0 a zero. Misura il
  costo del confine DI OGGI (percorso bloccante) senza sottrazioni fra
  configurazioni diverse. Due run da 5 min.
- **Retta sintetica** (disegno DS4 L3, se serve il coefficiente puro): un
  grafo che alterna N op banali GPU/CPU su tensori minuscoli, pendenza del
  tempo contro N = costo/confine; scheduler, threadpool e synchronize
  veri, il calcolo tende a zero, l'intercetta assorbe il resto. La scala
  della residenza (4/8 strati) è RITIRATA: non entra nella VRAM (1.727
  MiB/strato sopra 8,6 GiB fissi; R2 già strozzato a 305 MiB liberi).
- Prior da falsificare: **255 µs** (eccesso R1, segnale=rumore) contro
  tetto **≤128 µs** (sottrazione ibrido−cache). Se la sonda esce sopra i
  255, una delle due letture ha un difetto da trovare.

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
