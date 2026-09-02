# LANE ADATTIVA — tetto misurato dalle tracce e patch pronta (2/9/2026)

Progettista in sola lettura. Zero build, zero corse sul banco, nessun file esistente
modificato. Sorgente citato dallo snapshot `D:\ds4_work\snapshot_sorgente_20260901_2145\`
(1/9 19:24) e dal repo vivo `D:\llama-subtract` (solo lettura).

Script di analisi (tutti nuovi, in questa cartella):
`leggi_cestrc.py`, `tetto_lane_adattiva.py`, `tetto_raffinato.py`,
`estrapola_623.py`, `bilancio_finale.py`, `opzione_ii_per_strato.py`.

---

## 0. Due correzioni al mandato, subito

1. **Le tracce NON sono `CESTRC1` a 56 byte.** Sono **`CESTRC2` v2, record da 64 byte**
   (`cache-esperti.cuh:106-121`, `static_assert(sizeof(...) == 64)` a
   `cache-esperti.cu:2538`). Il layout `<IhBBBBH6h6B2x6f>` del mandato manca il campo
   `fork[6]`. Layout vero: `<IhBBBBH 6h 6B 6B 4x 6f>`.
   Di conseguenza **`analyze_route_trace.py` NON le rifiuta**: le legge (rifiuta la v1, che
   qui non esiste). Ho scritto lo stesso un lettore indipendente, come chiesto.
2. **`ops.cpp:4831` non è la `mul_mat_id` CPU**: è
   `ggml_compute_forward_get_rows_q` (`D:\llama-subtract\ggml\src\ggml-cpu\ops.cpp:4824-4831`),
   cioè la testa Markov del fascicolo «indice −1». Il cammino che ci riguarda è
   **`ggml-cpu.c:1628-1636`**, e lì il difetto è **peggiore di un assert**: vedi §B.3.

---

# (A) IL TETTO DELLA LEVA, SENZA BUILD

## A.1 Il formato, dedotto e provato

Header 36 B `<8s 7I>` = magic `CESTRC2\0`, version, record_size, n_record, totale,
capacità, **slot**, esperti. Record 64 B:

| campo | tipo | significato |
|---|---|---|
| `ordine` | u32 | indice progressivo del record |
| `strato` | i16 | strato MoE 0..42 |
| `riga` | u8 | riga (token) dentro il forward |
| `n_tok` | u8 | righe del forward |
| `k_cpu` | u8 | esperti dati alla lane CPU |
| `n_esperti` | u8 | `ne0` = 6 |
| `riservato` | u16 | 0 |
| `ids[6]` | i16 | id esperto in ordine ROUTER (non permutato) |
| `stati[6]` | u8 | **classe di residenza al momento della partizione** |
| `fork[6]` | u8 | maschera consumata dal MMVQ (255 = lane CPU / non vista) |
| pad | 4 B | — |
| `pesi[6]` | f32 | pesi router |

Prove della deduzione (output di `leggi_cestrc.py`, traccia principale):

```
META: version 2, record_size 64, n_record 27778, capacita 200000, slot 473, esperti 256
id: min=0 max=255   id fuori intervallo: 0
strati distinti: 43  (0..42)          n_esperti: {6: 27778}
k_cpu: {2: 27778}                     n_tok: {2: 16254, 3: 11481, 1: 43}
somma pesi: 1,500000 esatta su tutti i record (routed_scaling_factor)
campo `ordine` == indice del record: True
gruppi (strato, taglia) coerenti: 11997   rotti: 0
istogramma STATI: {0: 72286, 3: 94382}
istogramma FORK : {0: 89716, 1: 32018, 255: 44934}
```

43 strati e id in 0..255: **deduzione confermata**. Il regime della traccia
(`k_cpu=2`, `n_tok` 2-3) è **esattamente quello di produzione**: `p1b_conf.ps1:109-111`
imposta `LLAMA_OVERLAP_ASYNC=1`, `LLAMA_OVERLAP_K=2`, `LLAMA_OVERLAP_BATCH_MAX=3`.

Controprova incrociata sui conteggi: nella corsa B0/SOTA del 31/8 (§17)
`partizioni = 29.025` e `CPU = 58.050 = 2×29.025`, cioè **2,296 righe per lavoro**;
la traccia dà 27778/11997 = **2,315**. Stesso regime.

## A.2 La classe di residenza c'è: non serve simulare

`kern_partiziona` scrive `tr.stati[i]` (`cache-esperti.cu:7094`) **prima** di qualunque
override, dal valore osservato in cache a `:7059-7062`:

```
stato = 3  residente e usato        stato = 2  residente non usato
stato = 1  in transito              stato = 0  non residente (MISS)
```

Nella traccia compaiono **solo 0 e 3**: nessun transito, quindi lo `SCUDO_TRANSITO` è
inerte su questi dati e la partizione fra «miss» e «residente» è netta.

Colpi cache misurati: **56,63%** (94.382 / 166.668). Coerente con 473 slot.

**Non ho quindi usato una LRU simulata per il numero principale.** L'ho scritta lo stesso
(`tetto_raffinato.py`) e la dichiaro **non calibrata**: a 473 slot rende 48,29% di colpi
contro i 56,63% registrati — sotto-stima sia il tasso sia la clusterizzazione, perché non
modella prefetch e politica di ammissione `MASSA`. I suoi numeri non entrano nel verdetto.

## A.3 (a) Distribuzione dei non residenti per riga — K=2, 473 slot

| non residenti su 6 | righe | % |
|---:|---:|---:|
| 0 | 3.608 | **12,99%** |
| 1 | 5.052 | **18,19%** |
| 2 | 5.447 | 19,61% |
| 3 | 5.129 | 18,46% |
| 4 | 4.025 | 14,49% |
| 5 | 2.249 | 8,10% |
| 6 | 2.268 | 8,16% |

- righe in cui la CPU calcola **2 residenti**: 12,99%
- righe in cui la CPU calcola **1 residente**: 18,19%
- righe senza spreco (≥ 2 miss): 68,82%

Seconda traccia (`_v2_`): 12,44% / 17,79% / 69,76%. Le due tracce concordano.

## A.4 (b) Frazione di lavoro CPU sprecato

Ricostruzione della permutazione da `cache-esperti.cu:7205-7250` (ordinamento per classe
crescente). **Il conteggio dello spreco è invariante rispetto a quale delle tre varianti
di permutazione è attiva** (`massa_corsie`, `cpu_leggeri`, semplice): dipende solo da
*quanti* membri ha la classe 0, non dall'ordine dentro la classe. Verificato per
costruzione: `spreco == max(0, k_cpu − n_miss)` su tutte le 27.778 righe (assert nello
script, mai scattato).

```
esperti dati alla CPU : 55.556  (= 27.778 righe x k_cpu 2)
di cui RESIDENTI      : 12.268
frazione sprecata     : 22,08%          (seconda traccia: 21,34%)
```

**Controprova indipendente** con la maschera `fork` realmente consumata dal MMVQ
(`cache-esperti.cuh:116-118`): le colonne marcate 255 (lane CPU) sono un sottoinsieme
della testa della permutazione ricostruita su **27.245 righe coerenti, 0 incoerenti**,
533 non decidibili (fork tutto a 255). La ricostruzione è corretta.

**Il modello di costo non cambia il numero.** La lane è dequant-bound (§17-§18: gate/up
IQ2_XXS a 23,4 GB/s = 86,8% del tempo lane), quindi il costo è per **esperto unico** per
lavoro, non per esperto-riga. Contati entrambi:

| modello | oggi | con la leva | risparmio |
|---|---:|---:|---:|
| esperti-**riga** alla CPU | 55.556 | 43.288 | **22,08%** |
| esperti **unici** alla CPU | 47.635 | 37.307 | **21,68%** |

Differenza 0,4 punti: **la scelta del modello è immateriale**. Uso 22,08%.

## A.5 Estrapolazione al regime di produzione (623 slot)

La traccia è a **473 slot / 56,63% colpi**; la produzione gira a **623 slot / 67,2% colpi**
(LEDGER_25 §58-59). Più colpi ⇒ più spreco, quindi 22,08% è un **pavimento**, non il numero
di produzione.

Non estrapolo con una binomiale: la residenza è **clusterizzata**. Misurato:
spreco reale 0,2208 contro binomiale iid `(2h⁶ + 6h⁵(1−h))/2 = 0,1087` a h=0,5663 ⇒
**fattore 2,03**. Estrapolo invece dalla **variazione interna alla traccia**: i 43 strati
hanno tassi di colpi diversi, e la coppia (colpi, spreco) per strato porta dentro la
clusterizzazione vera.

Regressione pesata `logit(spreco) = −4,8250 + 5,9826 · colpi` (40 strati):

| colpi | spreco previsto | spreco OSSERVATO su strati vicini (±0,02) |
|---:|---:|---|
| 0,50 | 0,1378 | 0,1358 (n=2) |
| 0,5663 | 0,1920 | 0,2046 (n=8) |
| 0,60 | 0,2252 | 0,2278 (n=14) |
| 0,65 | 0,2816 | 0,2861 (n=10) |
| **0,672** | **0,3090** | **0,2998 (n=7)** ← produzione |
| 0,70 | 0,3459 | 0,3491 (n=3) |

Non è una vera estrapolazione: **sette strati della traccia girano già a ~67% di colpi e
mostrano 29,98% di spreco.** Seconda traccia: 0,2964 su 3 strati. Prendo **30%**.

**Riconciliazione con la diagnostica del 15/8 (13,4%).** LEDGER_15 §19: «6.708 assegnazioni
CPU: 5.809 miss, 899 residenti = 13,4%», su fixture da **64 token** — cache fredda. La mia
curva a colpi = 0,50 prevede **13,78%**. Il 13,4% non è sbagliato: è misurato in un punto
di lavoro freddo. **Il §60 di stamattina («valore di carta 13%, tetto ≤ +3%») eredita quella
sotto-stima**: il numero di regime è più del doppio.

## A.6 (c) Tempo recuperabile — formula e ingressi

```
guadagno_t/s = R / (P − R)          R = frazione_spreco × C
```
con `P` = parete decode, `C` = tempo `calcolo` della lane (che è **interamente sul cammino
critico**: §18, «join − (evento+calcolo) = −0,05 ms/lavoro ⇒ il rendezvous costa ZERO e la
sovrapposizione è ~0»).

Due ancore indipendenti per `(P, C)`:

| ancora | P | C | C/P | provenienza |
|---|---:|---:|---:|---|
| **B0/SOTA** | 94,56 s | 19,43 s | 20,55% | LEDGER_25 §18 (tabella tetto) + §17 (`calcolo` 1,537 ms × 12.642 lavori); t/s 12,69 |
| **wsolo** | 97,0 s | 28,38 s | 29,26% | LEDGER_25 §58-59 (623 slot, 2/9): 15.179 lavori × 1,87 ms |

> Nota sull'ingresso «0,93 ms per esperto-riga» del mandato: **non torna**. Un «lavoro» del
> worker copre TUTTE le righe dello strato (2,3 in media), non una: 1,87 / (2,3 × 2) =
> **0,404 ms**. Ma il costo unitario **si semplifica**: entra solo la *frazione*. Lo dichiaro
> e non lo uso.

**Regola 1 — `K = min(k_cpu, non residenti)`** (la leva):

| ancora | spreco | R | guadagno t/s | t/s |
|---|---:|---:|---:|---:|
| B0 | 22,08% (473 slot, misurato) | 4,29 s | **+4,75%** | 13,29 |
| wsolo | 22,08% | 6,27 s | **+6,91%** | 13,57 |
| B0 | **30%** (623 slot) | 5,83 s | **+6,57%** | 13,52 |
| wsolo | **30%** | 8,51 s | **+9,62%** | 13,91 |

**Correzione lato GPU.** Gli esperti tolti alla CPU li deve calcolare la GPU, a
**0,060 ms/esperto residente** (`llama-graph.cpp:1819-1820`). A 30%: 17.415 esperti-riga
× 0,060 = **1,045 s**. Se la GPU **non** avesse margine, il netto scende:

| ancora | guadagno lordo | guadagno con GPU pienamente additiva |
|---|---:|---:|
| B0, 30% | +6,57% | **+5,33%** |
| wsolo, 30% | +9,62% | **+8,34%** |

Il caso pessimistico è conservativo: §60 misura che **«la GPU è ferma il ~39% aspettando i
due esperti della CPU»**, quindi il lavoro spostato cade dentro un ozio che esiste già.

### **TETTO ONESTO: +5,3% … +9,6% di t/s, centro ~+6,5%.**
### Ampiamente sopra la soglia del 2%: **la build si fa.**

Coerenza col tetto assoluto: `lane a costo ZERO = 15,97 t/s` (§18) cioè +25,8% per il 100%
del `calcolo`; togliendone il 30% ⇒ +7,7% in scala lineare. Dentro la banda. Terza via.

## A.7 Il discriminante che decide: le COPIE NUOVE

Il precedente che pesa contro è `r54_k1` (§10): **K=1 ha tagliato il `calcolo` del 39,5% e
ha reso −2,05%**. Se quella funzione di trasferimento valesse qui, la leva sarebbe negativa.
**Non vale**, e il motivo è misurabile sulla stessa traccia:

| regola | copie uniche | esperti-riga CPU | **copie NUOVE** |
|---|---:|---:|---:|
| R0 oggi, K=2 fisso | 26.660 | 55.556 | — |
| **R1 lane adattiva** | **26.660** | 43.288 | **+0** |
| R2 K=1 | 43.351 | 27.778 | **+16.691 (+62,6%)** |
| R3 K=0 (tutto GPU) | 59.971 | 0 | +33.311 (+125%) |

**R1 non crea nemmeno una copia, per costruzione**: toglie alla CPU solo esperti **già
residenti in VRAM**, che la GPU serve senza trasporto. K=1 e K=0 spostano invece dei *miss*,
e ogni miss spostato è una copia PCIe — il canale per cui §10 conclude «i byte MIGRANO sullo
stesso bus (~−1,3% predetto)». **Il canale di morte di K=1 è strutturalmente assente da R1.**

L'altra metà del danno di K=1 — **`lavori` +20,7%** — resta il rischio residuo vero: cambiare
chi calcola cosa cambia i numerici, quindi il testo, quindi il numero di forward. È
imprevedibile senza build. È il motivo per cui `lavori` deve stare nei cancelli (§B.8).

## A.8 La regola q* di FreeToken

`q/(m−q) = BP/(BH−BP)` ⇒ `q = m · BP/BH`, con `q` = miss unici dello strato mandati in
**copia** (GPU) e `m−q` alla CPU. Misurato sulla traccia: **m = 4,999 miss unici per
(strato, passo)**, di cui **la CPU ne assorbe oggi 3,110 = 62,2%**.

| BP | BH | q*/m | quota CPU ottima | fonte di BH | verso |
|---:|---:|---:|---:|---|---|
| 23 | 30,0 | 0,767 | 23,3% | ipotesi del mandato | **togliere** alla CPU |
| 23 | 33,2 | 0,693 | 30,7% | terna misurata, §18 | **togliere** |
| 23 | 23,4 | 0,983 | 1,7% | gate+up IQ2_XXS (86,8% del tempo lane), §18 | **togliere** |
| 23 | 12,8 | 1,000 | 0% | B2 continuo misurato, §17 | BH ≤ BP ⇒ **l'ottimo è K=0** |

**Nessuna calibrazione di BH dice di dare più miss alla CPU; tutte dicono di darne meno.**
Alla banda del mandato (BH=30) la CPU dovrebbe passare da 62,2% a 23,3% dei miss.

**Segno del bilancio se si applicasse q\* alla lettera** (BH=30, costo lane 0,935 ms per
esperto-riga come da mandato, copia 0,32 ms): lane **−41.502 esperti-riga = −38,8 s**,
trasporto **+19.318 copie = +6,2 s**, bilancio **−32,6 s** sulla traccia — apparentemente
enorme. **Non è credibile e non lo propongo**: è la stessa aritmetica che prediceva bene
K=5 e ha sbagliato di 21,7 punti (§17), perché ignora che i byte migrano sullo stesso
controller DDR4. La famiglia «meno CPU sui miss» è già stata misurata tre volte
(K=1 −2,05%, K=0 storico 12,83 contro 14,03 della base K=2 il 15/8) e **non è la leva qui
proposta**.

**q\* e la lane adattiva sono ortogonali**: q\* riparte i *miss*, la lane adattiva toglie i
*residenti*. Non si contraddicono, e puntano nella stessa direzione (meno lavoro CPU inutile).
La lane adattiva è la parte del movimento che **non costa byte**.

## A.9 Perché NON la variante «K per strato» (opzione ii)

Calcolata sulla traccia (`opzione_ii_per_strato.py`), con `k_strato = min(2, min_righe(miss))`:

```
R1 per RIGA (il tetto)         risparmio 12.268 = 22,08%
ii-a K per strato, ORACOLO     risparmio 23.209 = 41,78%
ii-b K per strato, RITARDO 1   risparmio 22.528 = 40,55%
   di cui ANCORA sprecato       4.458 =  8,02%
OSCILLAZIONE di K fra passi consecutivi dello stesso strato: 5.969/11.954 = 49,9%
```

Il «189% del tetto» è un **allarme, non un premio**: un K per strato deve valere per tutte
le righe, quindi taglia anche righe che avevano 2 miss veri ⇒ **spinge miss sulla GPU ⇒ crea
copie ⇒ è il canale di K=1**. E il taglio cambierebbe fra passi consecutivi dello stesso
strato **una volta su due**, cioè forme nuove, cioè **ricattura del CUDA graph** ad ogni
oscillazione (la famiglia di difetti del replay stantio, `llama-graph.cpp:1857-1866`).
**Scartata.**

---

# (B) LA PATCH (disegno pronto, non applicato)

Vincoli di regia recepiti: **(1)** leva a difetto 0 **byte-identica** — con la env spenta il
codice generato percorre esattamente il cammino attuale; **(2)** diff minimo in
`kern_partiziona` (regione sotto indagine del difetto n.1); **(3)** la guardia sull'id −1 nel
cammino CPU **conta, non clampa**; **(4)** la patch parte dal sorgente che avrà superato G1,
non dallo snapshot 19:24.

## B.1 Il vincolo di forma, con le righe

- `k_cpu` deciso sull'**host** alla costruzione del grafo, Bresenham su `il`:
  `llama-graph.cpp:1846-1849`.
- Guardia di taglia `forma_ammessa = n_tokens <= LLAMA_OVERLAP_BATCH_MAX`:
  `llama-graph.cpp:1863-1866`.
- Le viste: `llama-graph.cpp:1918-1923`
  ```
  ids_cpu  = view_2d(part, k_cpu,                n_tokens, part->nb[1], 0)
  ids_gpu  = view_2d(part, n_expert_used-k_cpu,  n_tokens, part->nb[1], k_cpu*part->nb[0])
  perm_inv = view_2d(part, n_expert_used,        n_tokens, part->nb[1], n_expert_used*part->nb[0])
  ```
- Ricomposizione: `llama-graph.cpp:1997-1999`
  ```
  esperti = ggml_concat(ctx0, esperti_cpu, esperti_gpu, 1);   // ordine di partizione
  esperti = ggml_get_rows(ctx0, esperti, perm_inv);            // ordine di slot originale
  esperti = ggml_mul(ctx0, esperti, weights);                  // pesi in ordine ORIGINALE
  ```
- Il device conosce la classe al momento della partizione: `cache-esperti.cu:7054-7066`.
- La scrittura dei −1 di AcceptMoE: **`cache-esperti.cu:7307`**
  (il mandato dice «:7291»: nello snapshot è 7307).
- Il bilancio `lane_cpu/lane_gpu/lane_scudati`: **`cache-esperti.cu:7289-7302`**.

**Perché una forma deve cambiare, senza scampo.** Se la riga ha `n_miss < k_cpu`, la CPU deve
lasciare vuota una colonna; l'esperto va comunque calcolato, e la vista GPU ha solo
`6−k_cpu` colonne. Non esiste scambio possibile: quando la CPU declina, *tutti* gli esperti
rimasti sono residenti, quindi non c'è un miss da tirare su al suo posto. **La vista GPU deve
allargarsi.** Il punto è farlo **solo a leva accesa**.

## B.2 Le tre opzioni, valutate

### (i) Vista GPU a 6 colonne — **SCELTA**

`part` passa da `[2·ne0, n_tokens]` a `[3·ne0, n_tokens]` **solo a leva accesa**:

| blocco | colonne | contenuto |
|---|---|---|
| A `[0, ne0)` | ne0 | id in ordine di partizione (**invariato**); la CPU legge le prime `k_cpu` |
| B `[ne0, 2·ne0)` | ne0 | `perm_inv` (**invariato in forma**, valori ricalibrati) |
| C `[2·ne0, 3·ne0)` | ne0 | **NUOVO** — id per la lane GPU, 6 colonne |

- `ids_cpu` = view `[k_cpu, n_tokens]` offset 0 — **forma invariata**; nelle colonne
  declinate va `-1`.
- `ids_gpu` = view `[ne0, n_tokens]` offset `2·ne0` — allargata da 4 a 6.
- `perm_inv` = view `[ne0, n_tokens]` offset `ne0` — **forma invariata**; i valori ora
  indicizzano il concat largo `k_cpu + ne0` = 8: per lo slot originale `i`,
  `perm_inv[i] = j` se la CPU lo calcola (`j < k_cpu`), altrimenti `k_cpu + g` con `g` la
  colonna GPU.
- Ricomposizione: `concat(esperti_cpu[k_cpu], esperti_gpu[ne0]) → [n_embd, 8, n_tok]`,
  poi `get_rows(perm_inv) → [n_embd, 6, n_tok]`. **`concat` e `get_rows` restano gli stessi
  nodi**, cambia solo la larghezza intermedia.

**Il trucco che rende tutto sicuro: `perm_inv` non seleziona mai le colonne inutili.**
Le colonne GPU che la CPU si tiene, e le colonne CPU declinate, **non vengono lette da
nessuno**. Quindi non serve azzerarle: basta che nessuno scriva fuori posto.

**Come tratta la maschera gli id −1** (risposta alla domanda del mandato, con le righe):
`mul_mat_vec_q_moe_maschera` (`mmvq.cu:1344`) **non guarda l'id**: esclude per `maschera`
(`mmvq.cu:1385-1402`, `if (voluto == -1 ? classe == 3 : classe != voluto) return;`) e la
`return` avviene **prima di ogni scrittura di dst** ⇒ le colonne escluse restano **non
scritte**, non azzerate. E se un −1 supera la maschera, `mmvq.cu:1408` fa
`const uint32_t channel_x = ids[...]` — **cast a `uint32_t`** ⇒ `-1` diventa `0xFFFFFFFF`
⇒ lettura fuori slab. Inoltre il **cammino CUDA generico** (`ggml-cuda.cu:2912-2924`) non
tollera −1 affatto: nessun esperto combacia, niente viene inserito, e scatta
`GGML_ASSERT(ids_to_sorted_host.size() == ne_get_rows)` ⇒ **abort duro**.
Ecco perché AcceptMoE se la cava oggi: i suoi −1 sono **sanificati in `kern_decidi`** e la
colonna è annullata a valle dal **peso zero** (`cache-esperti.cu:7118-7124`, commento
esplicito). **Da noi il peso NON è zero**, quindi non possiamo appoggiarci a quel meccanismo.

⇒ **Sul lato GPU non si scrive mai −1.** Nelle colonne GPU che la CPU si tiene si scrive un
**id valido duplicato** (quello già presente alla colonna `k_cpu`): sicuro su entrambi i
cammini, e il risultato è scartato da `perm_inv`.
Costo: al più `k_cpu` colonne MMVQ in più per riga su un esperto **già residente o già
copiato — zero byte PCIe nuovi**. Ordine di grandezza: 2 × 29.025 × 0,060 ms = **3,48 s**,
contro 5,83 s risparmiati ⇒ netto +2,35 s = **+2,5%**. **Ottimizzazione di secondo giro**
(non nella prima build): escludere quelle colonne con la maschera del fork già esistente
(`fj_maschera`, `cache-esperti.cu:434`, `ggml-cuda.cu:2606-2730`) — l'id resta valido (il
cammino generico resta corretto) e il cammino mascherato le salta ⇒ costo 0 e si torna a
**+5,3…+8,3%**.

### (ii) K per strato dal conteggio dello strato precedente — **SCARTATA**
Numeri in §A.9: cattura più del tetto **perché taglia anche i miss** (crea copie: il canale
di K=1) e **K oscilla nel 49,9% dei passi** ⇒ ricattura del grafo. Il ritardo di uno strato
lascia comunque **8,02%** di spreco. Non è la stessa leva ed è peggiore su entrambi i fronti.

### (iii) La CPU calcola su un esperto «vuoto» — **SCARTATA**
Non ha senso: o l'esperto entra nella somma pesata (e allora va calcolato davvero), o non ci
entra (e allora si è cambiato il modello, non lo scheduling). L'unica forma sensata di
«vuoto» è la colonna saltata, che è esattamente l'opzione (i).

## B.3 Il cammino CPU: dove e come saltare le colonne con id −1

**Sito esatto** — `D:\llama-subtract\ggml\src\ggml-cpu\ggml-cpu.c:1628-1636`:

```c
for (int64_t iid1 = 0; iid1 < ids->ne[1]; ++iid1) {
    for (int id = 0; id < n_ids; ++id) {
        const int32_t i02 = *(const int32_t *) ((const char *) ids->data + iid1*ids->nb[1] + id*ids->nb[0]);
        assert(i02 >= 0 && i02 < n_as);                       // <-- riga 1632
        MMID_MATRIX_ROW(i02, matrix_row_counts[i02]) = (struct mmid_row_mapping) {id, iid1};
        matrix_row_counts[i02] += 1;
    }
}
```

**Il difetto è peggiore di un assert.** `assert` è la macro C: sotto `NDEBUG` (build Release)
**sparisce**, e `MMID_MATRIX_ROW(-1, …)` scrive **fuori dall'array** `matrix_rows` — corruzione
silenziosa, non un crash. Va messa una guardia vera.

**Patch (idioma «voci fuori tabella», già di casa a `cache-esperti.cu:1770`) — NON un clamp:**

```c
        if (i02 < 0 || i02 >= n_as) {
            // VOCI FUORI TABELLA: la colonna e' stata declinata dalla lane
            // adattiva (o e' un indice rotto). Si SALTA e si CONTA: assorbirla
            // in silenzio toglierebbe il segnale del fascicolo «indice -1».
            atomic_fetch_add_explicit(&ggml_mmid_fuori_tabella, 1, memory_order_relaxed);
            continue;
        }
```

Conseguenza dichiarata: la riga di `dst` per quella colonna **non viene scritta** da
`ggml_compute_forward_mul_mat_id_one_chunk` (`ggml-cpu.c:1463-1533`, scrittura a `:1514/1520`)
⇒ resta il contenuto precedente del buffer. **Nel disegno (i) è innocuo perché `perm_inv` non
la seleziona mai.** Lo scrivo come **invariante della patch**, non come dettaglio: chiunque
riusi la guardia fuori da questo disegno deve azzerare.

**Dove stamparlo**: `ggml-backend.cpp:2772-2776` stampa già a fine corsa
`worker: … calcolo … attesa-lavoro … join …`. Il contatore va **su quella riga**, che è la
riga della lane: `voci fuori tabella=%llu`. Esposizione: `ggml_cpu_mmid_fuori_tabella()` in
`ggml-cpu.h`. **Si stampa sempre, anche a zero** (la regola dei contatori muti), perché a
leva spenta il valore zero è il testimone che nessun −1 è entrato.

**Ricomposizione dell'uscita** (`llama-graph.cpp:1997-1999`): non cambia nulla. La `concat`
mette CPU (k_cpu colonne) e GPU (ne0 colonne) in un tensore da `k_cpu+ne0`; la
`get_rows(perm_inv)` sceglie **per ogni slot originale la copia che è stata davvero
calcolata**. La somma pesata `ggml_mul(esperti, weights)` continua a moltiplicare pesi in
ordine originale per uscite in ordine originale: **il contributo GPU sostituisce quello CPU
nella stessa posizione**, non si somma. Nessuno zero da iniettare.

## B.4 Il contatore che manca

**Definizione**: «esperti dati alla CPU che erano già residenti».

**Dove si scrive**: dentro `kern_partiziona`, accanto al bilancio di
`cache-esperti.cu:7289-7302`, dove `perm[]` è già costruito:

```c
    if (attiva && c.lane_cpu) {
        int n0 = 0, n1 = 0, n23 = 0;
        ...                                     // invariato
        if (n0)  atomicAdd(... c.lane_cpu, n0);
        if (n23) atomicAdd(... c.lane_gpu, n23);
        if (n1)  atomicAdd(... c.lane_scudati, n1);
        // NUOVO, sempre attivo (e' una DIAGNOSTICA, non la leva): quanti dei
        // k_cpu presi dalla testa non erano di classe 0.
        if (c.lane_cpu_residenti) {
            int spr = 0;
            for (int j = 0; j < k_cpu && j < ne0; ++j) if (chiave[perm[j]] != 0) spr++;
            if (spr) atomicAdd((unsigned long long *) c.lane_cpu_residenti, (unsigned long long) spr);
        }
    }
```

**Slot del contatore**: `runtime->cache.colpi + 55` — **l'unico libero**
(`cache-esperti.cu:3020-3031`: 49-53 = `k_ad_*`, 54 = `usato_spazzate`, 56-61 = `router_*`;
`CACHE_ESPERTI_CONTATORI 62` a `cache-esperti.cu:83`). Dichiarazione in `cache-esperti.cuh`
accanto a `:415-419`.

**Dove si stampa**: sulla riga `tre vie router/massa` (`cache-esperti.cu:8413-8420`), che è
già la riga del router a tre vie e porta `partizioni` e `CPU`:

```
cache-esperti: tre vie router/massa -> soglia_copia_pm=%d, copie_min=%d, cpu_leggeri=%d,
  partizioni=%llu, pesi mancanti=%llu, CPU=%llu (di cui RESIDENTI=%llu, %.1f%%),
  zero-copy=%llu, copie=%llu (forzate=%llu), rifiuti registro=%llu
```

**Questo contatore va nella build anche da solo.** È il primo braccio: **spesa zero,
rischio zero, e misura sul banco vero il numero che qui ho estrapolato** (attesa: ~30%).
Se il banco dicesse 13%, il resto della patch non si fa.

## B.5 La leva, i testimoni, i cancelli

**Env**: `LLAMA_OVERLAP_K_MIN_NONRES`, **lettore a VALORE** (idioma di
`cache-esperti.cu:2615-2617`, non «a presenza»):

| valore | comportamento |
|---|---|
| **0 / assente** | **comportamento di oggi, byte per byte** |
| 1 | **SONDA**: conta e non decide (solo il contatore §B.4; forme invariate) |
| 2 | **DECIDE**: la leva è attiva |
| altro | vale 0 (un refuso non deve accendere una leva) |

**Sorgente unica della verità.** Il livello lo legge **`llama-graph.cpp`** (che decide le
forme) e lo passa al kernel **come parametro dell'op**, accanto a `k_cpu`
(`ggml_cache_esperti_partiziona(ctx0, selected_experts, il, k_cpu)` a
`llama-graph.cpp:1912-1913`). **Mai due `getenv` indipendenti**: se host e device
divergessero, le forme e i contenuti non combacerebbero e l'uscita sarebbe spazzatura
plausibile.

**Riga di stderr all'avvio** (una sola, come le altre leve):
```
cache-esperti: LANE ADATTIVA livello %d (%s): k_cpu = min(%d, non residenti per riga),
               viste gpu %d->%d colonne, concat %d colonne
```
con `%s` = `SONDA: conta e non decide` / `DECIDE: la CPU salta i residenti`.

**Cancelli**

| cancello | leva 0 | leva 1 (sonda) | leva 2 (decide) |
|---|---|---|---|
| SHA G1 corto 0731 | `AD3D3770…FE11` **identico** | `AD3D3770…FE11` **identico** | **diverge, legittimo** |
| ri-baseline S1 difetto n.1 | `97DF3AB0…5EC0` | `97DF3AB0…5EC0` | `97DF3AB0…5EC0` (non tocca quel cammino) |
| `p1` | 0,84073 | 0,84073 | **dentro ±3σ**; sotto ⇒ respinta (K=1 perse 3,6σ) |
| `mean_len` / §4.10 | 2,61 | 2,61 | prosa tecnica genuina, lunghezza in banda |
| `CPU=` (esperti-riga) | invariato | invariato | **−30% atteso** |
| `di cui RESIDENTI=` | ~30% | ~30% | **0 esatto** ← il cancello di raggiungibilità |
| `calcolo` per lavoro | 1,87 ms | 1,87 ms | **−(28±5)%**, cioè 1,31-1,44 ms |
| **`lavori`** | 15.179 | 15.179 | **± 3%**; oltre ⇒ il testo è cambiato e il verdetto è nullo |
| copie / `kern_fj_copia` | — | — | **invariate ±1%** ← la firma che nessun byte è migrato |
| `voci fuori tabella` (CPU) | **0** | **0** | > 0 e ≈ agli esperti declinati |

Il cancello **«copie invariate»** è quello che distingue questa leva da K=1 a banco. Se le
copie salgono, si è ricreato il canale che ha ucciso `r54_k1` e va fermata lì.

## B.6 File, righe, pseudo-diff, stime

| file | righe | intervento | righe stimate |
|---|---|---|---|
| `ggml-cuda/cache-esperti.cuh` | ~118, ~415-419, ~272 | campo `lane_cpu_residenti`; campo `lane_adattiva` in `cache_esperti` | **+4** |
| `ggml-cuda/cache-esperti.cu` | 83 | `CACHE_ESPERTI_CONTATORI` 62 → 63 se servisse un secondo slot (con 55 libero: **non serve**) | 0 |
| `ggml-cuda/cache-esperti.cu` | 3020-3031 | `lane_cpu_residenti = colpi + 55` | **+1** |
| `ggml-cuda/cache-esperti.cu` | 2615-2617 | lettore env a valore + riga stderr | **+14** |
| `ggml-cuda/cache-esperti.cu` | **6911** | firma: `template <bool planner_trace, bool adattiva>`, nuovo argomento `int lane_adattiva` | **+2** |
| `ggml-cuda/cache-esperti.cu` | 7289-7302 | contatore residenti (sempre attivo) | **+5** |
| `ggml-cuda/cache-esperti.cu` | **dopo 7312** | blocco `if constexpr (adattiva) { … }`: scrive il blocco C, mette `-1` nelle colonne CPU declinate, ricalibra `perm_inv` | **+35** |
| `ggml-cuda/cache-esperti.cu` | 7764/7772 | quarta istanziazione al lancio | **+8** |
| `ggml-cuda/cache-esperti.cu` | 8413-8420 | stampa `di cui RESIDENTI=` | **+3** |
| `src/llama-graph.cpp` | 1912-1923 | larghezza di `part` e le tre viste dietro `if (adattiva)` | **+18** |
| `src/llama-graph.cpp` | 1997-1999 | nessuna modifica (concat/get_rows invariati) | 0 |
| `ggml/src/ggml-cpu/ggml-cpu.c` | **1632** | guardia + contatore «voci fuori tabella» | **+8** |
| `ggml/src/ggml-cpu/ggml-cpu.h` | — | `ggml_cpu_mmid_fuori_tabella()` | **+2** |
| `ggml/src/ggml-backend.cpp` | 2772-2776 | stampa del contatore sulla riga del worker | **+2** |

**Totale ≈ 100 righe**, di cui ~40 di sostanza.

**Pseudo-diff del cuore** (`cache-esperti.cu`, coda di `kern_partiziona`):

```diff
-__global__ static void kern_partiziona(
-        cache_esperti c, int attiva, const int32_t * __restrict__ ids,
+template <bool planner_trace, bool adattiva>
+__global__ static void kern_partiziona(
+        cache_esperti c, int attiva, const int32_t * __restrict__ ids,
@@ coda, DOPO la scrittura invariata di :7305-7312 @@
     int32_t * o = out + (size_t) t * 2 * ne0;
     for (int j = 0; j < ne0; j++) {
         o[j] = compatta && j >= k_cpu && pesi_validi && peso[perm[j]] == 0.0f
-                ? -1 : riga[perm[j]];              // :7307  INVARIATO
+                ? -1 : riga[perm[j]];              // :7307  INVARIATO
     }
     for (int j = 0; j < ne0; j++) {
-        o[ne0 + perm[j]] = j;                      // :7311  INVARIATO
+        o[ne0 + perm[j]] = j;                      // :7311  INVARIATO (leva spenta)
     }
+    // ---- LANE ADATTIVA. Non esiste nell'istanziazione <_, false>. ----------
+    if constexpr (adattiva) {
+        int32_t * g = out + (size_t) t * 3 * ne0 + 2 * ne0;   // blocco C
+        int n_miss = 0;
+        for (int i = 0; i < ne0; i++) n_miss += (chiave[i] == 0);
+        const int k_vivo = k_cpu < n_miss ? k_cpu : n_miss;   // K = min(k_cpu, miss)
+        // blocco C: tutte e sei le colonne in ordine di partizione; le prime
+        // k_vivo restano alla CPU -> si mette un id VALIDO duplicato (mai -1:
+        // ggml-cuda.cu:2924 aborta, mmvq.cu:1408 legge l'id come uint32_t).
+        for (int j = 0; j < ne0; j++) {
+            g[j] = j < k_vivo ? riga[perm[k_cpu]] : riga[perm[j]];
+        }
+        // colonne CPU declinate: -1 (la CPU le salta e le CONTA, ggml-cpu.c:1632)
+        for (int j = k_vivo; j < k_cpu; j++) o[j] = -1;
+        // perm_inv verso il concat largo k_cpu + ne0
+        for (int j = 0; j < ne0; j++) {
+            o[ne0 + perm[j]] = j < k_vivo ? j : k_cpu + j;
+        }
+        if (c.lane_ad_declinati && k_cpu > k_vivo) {
+            atomicAdd((unsigned long long *) c.lane_ad_declinati,
+                      (unsigned long long) (k_cpu - k_vivo));
+        }
+    }
 }
```

**Dichiarazione esplicita richiesta dalla regia**: con la leva spenta si compila
l'istanziazione `<planner_trace, false>`; il blocco `if constexpr (adattiva)` **non esiste
nel binario**, la scrittura dei −1 di `:7307`, il `perm_inv` di `:7311`, il bilancio di
`:7289-7302` e ogni altra istruzione di `kern_partiziona` restano **invariati**. È lo stesso
idioma già pagato nel file per la classe 4 di ADAPTIVE-K (`cache-esperti.cu:7199-7203`).

## B.7 Rischi

1. **CUDA graph.** Le forme **non cambiano a runtime**: `part` è più largo, ma di una
   larghezza fissa decisa alla costruzione del grafo, per strato, come già fa il K di
   Bresenham. Nessuna ricattura, nessuna forma variabile per token. **È il vincolo che rende
   la cosa fattibile** e la ragione per cui l'opzione (ii) è scartata.
2. **Replay stantio.** Il rilevatore di `cache-esperti.cu:6934-6957` confronta `n_tok`
   pubblicato e catturato; il nuovo blocco gira **dopo** e usa `n_lav`, quindi è coperto
   dallo stesso rilevatore. Da verificare che `div[4]` (testimone della griglia) resti a 0.
3. **AcceptMoE.** Scrive già `-1` nelle colonne GPU a peso zero (`:7307`) e le sanifica in
   `kern_decidi`. Il blocco C **non eredita quei −1** (li riscrive con id validi): va
   verificato che la compattazione a peso zero continui a valere sul blocco C, altrimenti si
   ricaricano colonne matematicamente nulle. **Braccio di prova obbligatorio con
   `LLAMA_ACCEPTMOE=1` + `COMPATTA=0` (la config di servizio) e anche `COMPATTA=1`.**
4. **`ggml_concat` a 8 colonne.** Il trasferimento CPU→GPU resta di `k_cpu` colonne (il ramo
   CPU non si allarga): volume di confine **invariato**. Cresce solo il tensore intermedio
   sul lato CUDA (8 colonne invece di 6, ~qualche decina di KiB per strato).
5. **Colonne non scritte.** Sia le colonne CPU declinate sia le colonne GPU duplicate
   contengono valori non definiti. **L'invariante di correttezza è che `perm_inv` non le
   selezioni mai.** Va messo un `GGML_ASSERT` di costruzione sull'host (i valori di
   `perm_inv` stanno in `[0, k_cpu+ne0)` e sono una permutazione iniettiva) in un braccio di
   debug, non in produzione.
6. **Il rischio che non si può misurare a tavolino**: i numerici cambiano ⇒ lo SHA diverge ⇒
   il testo cambia ⇒ `lavori` può muoversi. K=1 ha visto `lavori` +20,7%: **è il canale che
   ha mangiato tutto il suo guadagno**. Per questo `lavori` è un cancello, non una nota.
7. **Difetto n.1.** `kern_partiziona` è la regione sotto indagine. La patch **non tocca una
   riga esistente** del kernel (solo la firma template e un blocco in coda che non si compila
   a leva spenta). La ri-baseline `S1 = 97DF3AB0…` va comunque rieseguita dopo la build.

## B.8 Protocollo di build

1. **La patch parte dal sorgente che avrà superato G1**, non dallo snapshot 19:24. Stato al
   2/9 07:25: `ggml-cuda.dll` `18444E20…` (chirurgo 20) **non certificata, G1 non completato**;
   tutte le misure §56-§59 sono sul `6A98BE10`. **Prima si chiude G1, poi si parte da lì.**
2. Banco libero dichiarato: nessun `llama-server`/`llama-cli`/`llama-mtmd-cli`, RAM > 82 GiB,
   **stabile su 3 controlli consecutivi a 40 s** (HANDOFF_1_SETTEMBRE §0.1 p.1).
3. **Backup** in `D:\llama-subtract\build\bin\backup_pre_lane_adattiva\` con `SHA256.txt`
   **e copia del sorgente accanto** (regola §49).
4. **Build MAI via `D:\llama-subtract\build_cuda.bat`** — fa `cd /d D:\llama-overlap` e
   compila l'albero sbagliato **riuscendo in silenzio**. Procedura a mano + `editbin /STACK`.
5. **G1 obbligatorio**: banco corto 0731, 3 corse, SHA
   `AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11`, **a leva spenta**.
   Se diverge ⇒ ripristino dal backup: la leva non è a difetto 0 e il disegno è sbagliato.
6. **Ri-baseline S1**: `97DF3AB0C56EC7A1651B68A205638916627EB19DF73E7788048C32E583135EC0`.
   Se cambia, le sonde della sera 1/9 vanno rifatte.
7. **Mai `git` in `D:\llama-subtract`.**
8. Ordine dei bracci (ognuno è un cancello per il successivo):
   **B-a** solo il contatore §B.4 (leva assente) ⇒ SHA identico, e **misura il 30% sul banco
   vero**. Se < 15%, si ferma qui.
   **B-b** leva = 1 (sonda) ⇒ SHA identico, forme invariate.
   **B-c** leva = 2, fixture corta 64 token ⇒ `di cui RESIDENTI = 0`, `voci fuori tabella > 0`,
   copie invariate.
   **B-d** lungo 1200 token contro l'ancora appaiata, 3 corse, mediana vera (non il massimo).

---

## Verdetto

- Lo spreco **esiste ed è il doppio di quanto messo a registro**: **22,08%** misurato a 473
  slot, **~30%** al punto di lavoro di produzione (sette strati della traccia ci girano già).
  Il 13,4% del 15/8 è un punto **freddo**, e il «≤ +3%» del §60 lo eredita.
- Il tetto onesto è **+5,3% … +9,6% di t/s**, centro **~+6,5%**. **Sopra il 2%: la build si fa.**
- La leva è **l'unica della famiglia «meno CPU» che non crea una sola copia** (+0 contro
  +16.691 di K=1 e +33.311 di K=0). Il canale che ha ucciso `r54_k1` le è precluso per
  costruzione.
- Il rischio residuo vero non è il trasporto: è che il cambio di numerici sposti la
  traiettoria del testo (`lavori` +20,7% su K=1). Va nei cancelli.
- Il primo braccio costa **~10 righe e zero rischio**: il contatore. Prima si misura il 30%
  sul banco, poi si spende la patch.
