# LEDGER 13 AGOSTO 2026 — il prefetch device-side, e la misura che ribalta la direzione

Sedici ore. Il ramo prefetch è stato portato dal non essere mai eseguito al
funzionare completamente, e **non paga**. La misura che conta è arrivata alla
fine e va nella direzione opposta a tutta la giornata.

---

## 1. IL RISULTATO CHE CONTA

**Il 70,8% degli esperti copiati in VRAM non viene mai riusato.**

| | mai | 1 uso | 2-3 | 4+ | installati |
|---|---|---|---|---|---|
| SOTA (no prefetch) | **70,8%** | 14,7% | 8,1% | 6,4% | 100.103 |
| col prefetch | 69,4% | 14,7% | 8,8% | 7,1% | 92.022 |

Il pareggio copia / zero-copy è a **due usi** (microbench 3060,
`ggml-cuda.cu:1291`):

```
GPU residente in VRAM   0,079 ms/esperto   0 byte PCIe
CPU da mappato          0,242              0 byte PCIe   capienza ~2/strato
GPU zero-copy in posto  0,274              6,75 MiB      nessuno slot
GPU copia + calcolo     0,403              6,75 MiB      slot + SFRATTO
```

Copiare costa 0,403 il primo uso e 0,079 dopo; leggere in posto 0,274 sempre.
**L'85,5% degli installati è copiato in perdita**: 85.594 × 0,129 ms = 11,0 s
su una corsa da 55,5 = **20%** (≈17% scontando la quota già nascosta dal fork).
E sopra ci sono **85.594 sfratti** che non avverrebbero: la cache si ricicla
**223 volte per corsa** su 448 slot per portare roba che serve una volta.

I contatori esistevano (`installati_riusi_0..3`, indici 28-31) e nessuno li
stampava.

---

## 2. LA TABELLA DELLA GIORNATA

Riferimento SOTA (`FORK=2`, niente DMA): **14,74-14,79** a macchina fredda,
**14,42** nell'ultima campagna (deriva a caldo).

| braccio | configurazione | t/s | COLPI | note |
|---|---|---|---|---|
| `g_rif` | SOTA | 14,74 | 54,9% | riferimento |
| `y_dev2` | prefetch, consegna 2% | 14,31 | 53,3% | meglio del ramo prima delle riparazioni |
| `t2_top1` | prefetch `PF_TOP=1` | **14,17** | 58,8% | il migliore del ramo |
| `t2_top3` | `PF_TOP=3` | 13,12 | **63,1%** | colpi alti, velocità no |
| `g2_d2` | prefetch pieno | 10,64 | 62,8% | 51% del traffico in anticipo |
| `kk_30` | `K=3` | 12,53 | **73,8%** | massimo storico di colpi |
| `w_off` | lane CPU spenta | 11,85 | 53,4% | la lane vale il 19% |

**Niente batte la SOTA.**

### La curva della selettività (`PF_TOP`)

| `TOP` | prenotati | buchi | efficienza marginale | COLPI | t/s |
|---|---|---|---|---|---|
| — | 0 | ~106.000 | — | 53,3% | **14,31** |
| 1 | 8.993 | 91.544 | 161% | 58,8% | 14,17 |
| 2 | 20.334 | 86.566 | 44% | 61,1% | 13,69 |
| 3 | 33.311 | 82.094 | 34% | 63,1% | 13,12 |
| 6 | 89.568 | 84.500 | **negativa** | 62,8% | 10,60 |

Oltre tre esperti anticipati **peggiorano anche i colpi**: 56.000 prenotazioni
in più per perdere 0,3 punti. L'eccesso sfratta più di quanto porti.

### Il taglio della lane CPU (`OVERLAP_K`), nel regime nuovo

| K | t/s | domanda alla cache | buchi | COLPI |
|---|---|---|---|---|
| 1 | 13,67 | 276.017 | 134.663 | 51,2% |
| 1,8 | 13,11 | 244.839 | 99.302 | 59,4% |
| **2** | **14,17** | 222.052 | 91.544 | 58,8% |
| 3 | 12,53 | 168.087 | **43.990** | **73,8%** |

`K=2` regge. `K=3` dimezza i buchi e va più piano: la CPU diventa lei il
cammino critico (3 × 0,242 = 0,726 ms contro ~0,44 del ramo GPU). Anomalia da
spiegare: `K=1` (13,67) batte `K=1,8` (13,11) — sospetto la distribuzione di
Bresenham, che a valori frazionari alterna forme fra strati adiacenti.

---

## 3. I QUATTRO DIFETTI DI RAGGIUNGIBILITÀ

Il prefetch device-side non funzionava per **quattro difetti in fila**, ognuno
dei quali nascondeva il successivo. Ogni volta il banco restituiva numeri
plausibili e ci ho costruito sopra una spiegazione.

1. **La chiamata stava in `fork_gate`**, che gira solo con `fj_attivo`; ma il
   fork si spegne sia con `W>0` (`:1688`) sia con DMA acceso (`:1723`) — le due
   condizioni che devono valere perché esistano prenotazioni. Il codice non è
   **mai** stato eseguito. La riga `FORK=2 richiede LLAMA_CACHE_ESPERTI_W=0
   esplicito: fork SPENTO` era nel log dal primo minuto.
2. **`pf_lista` era allocata dentro `if (fj_leva > 0)`** (`:1759`). Chiamata
   spostata su un ramo raggiungibile, memoria no: `pf_dev=1` con `batch
   serviti=0`.
3. **`stream_pf` era fuori dal grafo catturato.** Accodavo 86 drenaggi per
   passata, ne giravano **1,7**: i kernel su uno stream non in cattura girano
   una volta e sul replay non esistono. Cura: forcella e ricongiungimento a
   eventi, come fa il fork con `ev_fork`/`ev_copia`.
4. **Il contatore delle prenotazioni riuscite stava nel ramo `!dma_strato`**,
   che qui non gira mai — da cui `riuscite=0` con `testa` a 518. E
   `lane_cpu+16` sforava `CACHE_ESPERTI_CONTATORI`.

**La regola che ne esce**: stampare il contatore **sempre, anche a zero** —
è lo zero che dimostra che il ramo è stato raggiunto. E fermare il processo
quando una leva chiesta non si accende, invece di lasciar girare il banco su
un'altra configurazione.

---

## 4. LE CORREZIONI CHE RESTANO NEL BINARIO

| commit | cosa |
|---|---|
| `9e40c9ed6` | **abort di chiusura chiuso**: `ggml_cuda_kv_ring_dump`/`_free` giravano da `atexit` chiamando CUDA a driver spento. Causa dei server orfani con 74 GB. E `ggml_cuda_error` ora stampa anche su `stderr` diretto: le tre righe che dicono quale chiamata è fallita passavano dalla callback di log, già distrutta |
| `192bcac5a` | **protezione «in volo»**: gli slot che lo strato in corso leggerà non sono più vittime, in tutti e quattro i siti di `cache_vittima`. È ciò che rende componibili fork e prefetch (`LLAMA_CACHE_ESPERTI_FORK_COMPONI=1`) |
| `1c2456ff2` | **scudo del transito**: `kern_partiziona` dava alla CPU per primi gli esperti in transito, perché `chi[slot] == (k\|TRANSITO)` non è uguale a `k`. Pagavamo la copia e il lavoro lo faceva la CPU |
| — | **cancello di avvio**: una leva chiesta e spenta in silenzio **ferma il processo**. `LLAMA_CACHE_ESPERTI_STRICT=0` per proseguire |
| — | **diagnostica nuova**: i tre cursori dell'anello, il bilancio della domanda per classe, l'istogramma dei riusi |

---

## 5. LE RILETTURE — numeri che significavano altro

- **`in ritardo` NON misura spreco.** A `TOP=1` è l'89,7% e i colpi salgono:
  misura l'arrivo rispetto alla **prima** domanda, ma l'esperto resta residente
  e serve quelle dopo. Inseguito per ore come se fosse spreco.
- **`colpi` non è una quota della domanda**, è una quota di ciò che la cache
  riesce a vedere. Con `K=1` la domanda sale a 276.017, con `K=3` scende a
  168.087: il denominatore si muove. Il numero pulito è **`buchi` assoluti**.
- **La lane CPU non toglie domande alla cache**: misurato, `domanda` è la
  stessa a lane accesa e spenta (227.384 contro 226.008). Quello che toglie è
  **trasporto**: un esperto calcolato su CPU non attraversa il PCIe. Per questo
  spegnerla costa il 19%.
- **`LLAMA_MAPPED_IBRIDO=0` non è l'interruttore dello zero-copy.** Spegnendolo
  il buffer mappato diventa VRAM vera e il modello non entra (fallisce
  l'allocazione di 2,3 GB per il drafter). La lettura diretta è ciò che fa
  entrare il modello: **si instrada, non si spegne**.

---

## 6. L'ERRORE DI METODO, TRE VOLTE LO STESSO

Ho preso un numero misurato in un braccio e l'ho usato per ragionare su un
altro. La copertura dell'81,8% veniva da `PF_TOP=6`; il braccio che stavo
tarando girava a `PF_TOP=1`, dove è il 21,4%. Rifatto il conto col numero del
braccio giusto, il modello prediceva `K≈2,26` — cioè esattamente ciò che la
macchina ha misurato.

**Ogni numero che entra in un calcolo deve venire dal log del braccio di cui si
sta parlando.** Nei tre casi in cui ho seguito questa regola (i cursori
dell'anello, il contatore del consumatore, la curva `PF_TOP`) la risposta è
arrivata al primo colpo.

E un danno vero: uno script con indici calcolati ha trovato la **dichiarazione
anticipata** invece della definizione e ha cancellato **3.593 righe**.
Ripristinato dal commit e rifatto con ancore testuali e assert sul numero di
righe tolte.

---

## 7. IL LAVORO CHE RESTA

**Uno solo, e non è una taratura: portare il peso del router dentro la cache.**
Tutte le firme sono `const int32_t * ids` e la massa si ferma prima. Il
tensore esiste nel grafo (`ffn_moe_weights_norm`, `llama-graph.cpp:2170`) e
c'è già il modo di intercettarlo per nome nel backend CUDA — è il pattern usato
per `cache_pf-<strato>-<n>` (`ggml-cuda.cu:4724`).

Con quello, la politica a tre livelli:

```
massa alta       -> COPIA in VRAM        rientra al secondo uso
massa bassa      -> ZERO-COPY in posto   nessuno slot, nessuno sfratto
massa bassissima -> CPU, fino a K=2      zero byte sul bus, capienza dura
```

L'ordine CPU-in-fondo è per **capienza**, non per costo: `K=3` porta i colpi al
73,8% e perde il 12%.

Il predittore della riusabilità c'è: il peso del router separa la persistenza
di **+40,2 punti** (27,3% nel quintile leggero contro 67,5% nel pesante,
misurato il 12/8).

**La macchina per instradare esiste già**: il fork maschera le colonne
residenti e calcola mentre copia le mancanti. Serve una maschera a **tre**
valori invece che a due, e la terza passata è il `mul_mat_id` originale di
llama.cpp sul tensore mappato — già scritto, già collaudato.

Aperto anche: `docs/porto/TODO_LANE_ADATTIVA.md` — `k_cpu` deve adattarsi a
quanti non residenti veri esistono, o con il prefetch acceso la CPU si prende
dei residenti (0,242 contro 0,060, fattore quattro buttato).

**Da rimisurare a macchina fredda**: la SOTA (14,42 a caldo contro 14,74-14,79)
e l'ottimo di capienza, perché tutte le tarature vecchie sono state fatte con
la copia esposta all'84,5% e adesso la copertura è un parametro di progetto.
