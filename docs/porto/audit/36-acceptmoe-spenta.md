# 36 — «AcceptMoE spenta»: era acceso, e a mentire era il lettore

**Verdetto in una riga**: le due op sono nel grafo e girano in tutti i bracci
AM=1 — `lanci` arriva a 21.280 (c5_c2) e 27.057 (c5_c2c08), con 10.941 e
14.508 righe mascherate — ma il cancello della campagna legge *l'ultima* riga
`acceptmoe` del log, che è il dump della **cache bozza** (32 slot, contesto
DSpark), dove AcceptMoE non gira **per costruzione** ed è sempre a zero.
Nessuna delle sette condizioni d'armamento fallisce in blocco; nessuna delle
condizioni della guardia del grafo fallisce. Il contatore device è sano.

Tutti i numeri qui sotto sono **[MISURATO]** dai log di stanotte
(`D:\ds4_work\llama_run\c5_*.server.log`, `c4_n2bm3*.server.log`) salvo dove
marcato **[DEDOTTO]**.

---

## 1. La radice: due cache, due dump, e un `-Last 1`

Ogni processo ha **due** runtime cache-esperti: il bersaglio (339 slot) e la
bozza (32 slot, `LLAMA_CACHE_BOZZA_SLOT=32`). Ognuno stampa il proprio blocco
`cache-esperti: dump contatori` — al battito (45 s in campagna) e alla
liberazione del contesto. Alla chiusura il bersaglio viene liberato **prima**,
la bozza **per ultima**: l'ultima riga `acceptmoe` del file è sempre la sua.

La riga della bozza è a zero per costruzione, tre barriere indipendenti:
l'arch della bozza non è `LLM_ARCH_DEEPSEEK4` (è dflash, `n_layer=3` nel log),
il suo contesto ha `ctx_other` valorizzato, e il suo runtime è un'istanza
separata con contatori propri.

Il cancello di `campagna5.ps1` (riga 168) faceva:

    Select-String -Path $log -Pattern 'acceptmoe.*' | Select-Object -Last 1

e quindi il cruscotto mostrava `lanci=0` **in ogni braccio**, inclusi quelli
che cambiavano lo SHA. I log dicono altro. `c5_c1b.server.log`:

    r.484  (battito 45s)  acceptmoe -> lanci=2844,  righe mascherate=0, ...   <- BERSAGLIO
    r.520  (battito 90s)  acceptmoe -> lanci=10967, righe mascherate=0, ...   <- BERSAGLIO
    r.545  (chiusura)     acceptmoe -> lanci=18767, righe mascherate=0, ...   <- BERSAGLIO
    r.558  (chiusura)     acceptmoe -> lanci=0,     righe mascherate=0, ...   <- BOZZA (l'ultima!)

Il blocco della bozza si riconosce al volo: `vive-censurate=32`, `spin=0`,
`rilevatore replay attivo=0`, `domanda 12`.

Nota di merito alla trappola: l'intestazione di campagna 5 aveva già schivato
il **primo** strato («la riga esce anche a leve spente») ed è caduta sul
**secondo** (la riga esce anche *per l'altra cache*). Il C1b è quindi passato
per il motivo GIUSTO: macchinario acceso, zero righe mascherate per progetto
(`ESATTE=99` > taglia batch ⇒ nessuna riga candidata ⇒ `mascherate=0` E
`senza residenti=0`, esattamente ciò che i contatori dicono).

### Riparazioni applicate (nessuna tocca il cammino di calcolo)

1. **`D:\ds4_work\llama_run\campagna5.ps1` r.167-175** — il cancello ora
   sceglie la riga col **massimo di `lanci`** (= il bersaglio), non l'ultima.
2. **`ggml/src/ggml-cuda/cache-esperti.cu` r.2096-2105** — la riga di dump ora
   porta l'identità: `acceptmoe[bersaglio]` / `acceptmoe[bozza]`. Solo testo
   di stampa; il pattern `'acceptmoe'` degli script continua a combaciare.
   (Richiede ricompila; il cancello dello script funziona anche senza.)
3. **`src/llama-graph.cpp` r.2219-2231** — irrobustita la guardia con
   `n_expert_used <= 16`: rispecchia il contratto del lanciatore (`tieni[16]`)
   e l'accettazione dei backend. Senza, un grafo costruito con la semantica
   del warmup (`n_expert_used = n_expert = 256`, `llama-graph.cpp:1366`) e
   `n_tokens <= 8` creerebbe op che nessun backend accetta. Con DSV4 normale
   (6 esperti) la condizione è sempre vera: topologia identica, SHA intatto.
4. **La spia** (`LLAMA_ACCEPTMOE_SPIA=1`, spenta di default) — vedi §3.

Verifica fine riga: `git diff --numstat` sui quattro file dà +7/+15/+5/+22
righe, zero rimozioni spurie. Albero LF rispettato.

Il cancello d'identità non è stato toccato: a leve spente niente di tutto
questo è sul cammino (statiche `getenv` una tantum e rami morti), e stanotte
è già ripassato due volte — `c5_c0` 12,87 e `c5_base` 12,90, entrambi
`CF2DEEA06E90` (SHA ricalcolati da me sui file `.output.html`).

---

## 2. Il quadro completo dei bracci [MISURATO]

1.200 token, n-max 2 (salvo c0/base), `-ub 64`, 339+32 slot, LRU, topk=1.
SHA ricalcolati sui file di output; contatori dal dump finale del bersaglio.

| braccio | leve | t/s | SHA | acc/token | acc pos-2 | bozze (tok) | mean len | colpi% | buchi | byte dom. | am lanci | mascherate | scartati | senza res. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| c5_c0 | AM=0, n-max 1 | 12,87 | CF2DEEA06E90 | 0,868 | — | 599 (599) | 1,87 | — | — | — | — | — | — | — |
| c5_base | AM=0, n-max 1 | 12,90 | CF2DEEA06E90 | 0,868 | — | 599 (599) | 1,87 | — | — | — | — | — | — | — |
| c4_n2bm3 | AM=0 | 9,43 | 23B14DCEB7CF | 0,77778 | 0,862 | 419 (837) | 2,54 | 25,1 | 158.631 | 1046,2 GiB | — | — | — | — |
| c5_c1b | AM=1 E=99 | 9,42 | 23B14DCEB7CF | 0,77778 | 0,862 | 419 (837) | 2,54 | 24,3 | 175.861 | 1159,8 GiB | 18.767 | 0 | 0 | 0 |
| c5_c2e2 | AM=1 E=2 | 9,53 | 03243B4B8178 | 0,76596 | 0,832 | 423 (846) | 2,50 | 31,0 | 164.678 | 1086,1 GiB | 19.448 | 2.801 | 11.392 | 10.967 |
| c5_c2 | AM=1 E=1 | 8,96 | E242E249EFA4 | 0,73776 | 0,793 | 429 (858) | 2,32 | 44,6 | 143.473 | 946,2 GiB | 21.280 | 10.941 | 44.470 | 15.699 |
| c4_n2bm3c08 | AM=0, conf 0,8 | 10,43 | F4488F2AFD82 | 0,96914 | 0,698 | 378 (648) | 2,66 | 30,2 | 137.458 | 906,6 GiB | — | — | — | — |
| c5_c2c08 | AM=1 E=1, conf 0,8 | 10,37 | 661C4BF983F3 | 0,95775 | 0,533 | 321 (497) | 2,44 | 58,9 | 84.499 | 557,3 GiB | 27.057 | 14.508 | 59.434 | 3.772 |

`tenuti per soglia = 0` ovunque: `LLAMA_ACCEPTMOE_SOGLIA` non è mai stata
esercitata in campagna (deliberato, ma è la leva vergine più interessante,
§5).

Tre conferme di salute del meccanismo:

- **Dose-risposta**: E=99 → bit-identico alla base (23B14DCEB7CF, come
  c4_n2bm3); E=2 → diverge poco; E=1 → diverge di più. Una maschera spenta
  non potrebbe farlo.
- **Il costo fisso del macchinario è zero**: c1b vs c4_n2bm3 = 127.393 vs
  127.309 ms di eval (+0,07%), stessa uscita bit-esatta. Le due op identità
  (80 lanci kernel per forward!) non si vedono sul muro. Si può lasciare la
  leva compilata senza pagare.
- **Attenzione ai contatori di cache fra gemelli**: c1b e c4_n2bm3 hanno la
  stessa identica computazione, ma buchi 175.861 vs 158.631 (+10,9%). La
  residenza è sensibile ai tempi (coda d'installazione asincrona), già noto
  come «istantanee a battito»: mai usare i buchi da soli come cancello fine.

---

## 3. Il cancello numerico: quanto DEVONO valere i contatori

L'aritmetica, verificabile su ogni log:

    strati armabili L = n_layer - hash_layer_count = 43 - 3 = 40
      (kv 35 del log: deepseek4.hash_layer_count=3; conferma indipendente:
       MCD(21280, 26640/2) = 40)

    lanci      = L x (n. forward del bersaglio con n_tok <= 8)
                 [verify + ripristini + decode singoli + coda del prompt (68=64+4)]
    mascherate + senza residenti
               = L x (somma delle posizioni candidabili sui soli forward ARMATI)
               = L x (n_tok - max(n_tok - n_spec, ESATTE))+  per forward armato

Attesi con QUESTO carico (1.200 token, n-max 2), da confrontare col dump
`[bersaglio]`:

| tipo braccio | lanci | mascherate + senza | mascherate |
|---|---|---|---|
| C1b (E=99) | 18.000–21.000 | **0 per progetto** | 0 |
| C2 (E=1, conf 0) | 20.000–23.000 | 80 × verify armati ≈ 26.000–34.400 | ≈ 0,40–0,45 × (masch+senza) a 339 slot |
| C2 (E=1, conf 0,8) | 25.000–29.000 | 40 × token di bozza armati ≈ 18.000–20.000 | ≈ 0,79 × (masch+senza) |
| C2e2 (E=2) | 18.500–21.500 | 40 × verify armati ≈ 13.500–17.000 | ≈ 0,20 × (masch+senza) |
| bozza, sempre | **0** | 0 | 0 |

Misurati: 21.280 / 26.640 / 10.941 (c2); 27.057 / 18.280 / 14.508 (c2c08);
19.448 / 13.768 / 2.801 (c2e2). Tutti dentro le bande. Il «×10 in più o in
meno» del mandato ora ha un metro: `lanci` sotto 1.000 = op fuori dal grafo;
`masch+senza` sotto metà banda = armamento rotto.

**Coda aperta n.1 — il 22% di verify veri non armati.** In c5_c2 i verify con
bozza vera sono 429 (`#gen drafts`, spec stats), ma i forward armati sono
26.640/80 = **333**: ne mancano 96 (22%). I forward piccoli totali sono
21.280/40 = 532: tolti 429 verify, ~1 coda prompt e ~100 ripristini attesi
(20,7% di accettazione parziale × 429 ≈ 89, che il progetto DISARMA di
proposito), i conti tornano solo se ~96 verify veri si disarmano per una
condizione ancora ignota [DEDOTTO]. La quota scende con la confidenza (≈19%
a E=2, ≈8% a conf 0,8): l'anomalia vive vicino ai ripristini. Candidati:
`spec_i_batch.front() != off` o le due uguaglianze di taglia subito dopo un
ripristino (lato server), oppure l'ubatch spezzato (lato contesto).

**Coda aperta n.2 — i resti mod 40.** `lanci` finale non è sempre multiplo di
40 (c1b: +7; c2c08: +17; c2e2: +8; c2: esatto). Sub-0,1%, non cambia nessun
verdetto; sospetti: lettura D2H del battito che corre coi kernel in volo, o
l'ultimo forward troncato dallo `Stop-Process`. Il cancello usa bande, non
multipli esatti.

### Lo strumento che chiude entrambe (scritto, da compilare)

`LLAMA_ACCEPTMOE_SPIA=1` (spenta di default, fuori dal cammino normale):

- `tools/server/server-context.cpp` r.3654-3676: per ogni decode che **porta
  una bozza ma non si arma** stampa i predicati in chiaro:
  `acceptmoe-spia: disarmo con bozza: stato=.., replay=.., catena=.., bozza=.., fronte=.., off=.., vista=..`
  → `replay=1` è il disarmo di progetto (ripristino); ogni riga con
  `replay=0` è l'anomalia, col predicato colpevole leggibile.
- `src/llama-context.cpp` r.2089-2104: se il server ha armato ma il forward
  disarma (ubatch spezzato / multi-sequenza):
  `acceptmoe-spia: contesto disarma: spec=.., ubatch=.., batch=..`

**Braccio che la stampa**: ripetere `c5_c2` con in più
`LLAMA_ACCEPTMOE_SPIA=1` e `LLAMA_TRACE=1` (leva già esistente, r.1361 del
server: stampa `accepted N/M draft tokens` e `(restore checkpoint)` per
episodio). Attesi ~199 righe di disarmo, di cui ~100 con `replay=1`
[DEDOTTO]; il conteggio `restore checkpoint` di TRACE deve combaciare con le
righe `replay=1`. Le righe `replay=0` (attese ~96) dicono quale predicato
cade. Se escono ~0 righe `replay=0`, l'anomalia sta nel contesto e la spia
del contesto la mostra.

---

## 4. Dove va il tempo risparmiato (domanda 2 del mandato)

Coppia pulita: `c4_n2bm3c08` (AM=0) vs `c5_c2c08` (AM=1, E=1), stessa
confidenza 0,8.

Il trasporto è tagliato davvero, e in grande [MISURATO]:

    buchi:            137.458 -> 84.499   (-38,5%)
    byte a domanda:   906,6   -> 557,3 GiB (-349,3 GiB, -38,5%)
    per riga di batch: -41%  (1.328 righe -> 1.380 righe calcolate)

E il ciclo si accorcia davvero: 255,0 → 235,3 ms (−19,7). Col modello a
0,221 ms/buco i buchi risparmiati per ciclo valgono ~16–20 ms [DEDOTTO]: la
conversione **a livello di ciclo c'è**, quasi piena. Il muro sta dopo:

    ms/token:  95,9 -> 96,4   (u nulla, anzi +0,5)
    t/s:      10,43 -> 10,37

Il guadagno viene mangiato da tre bocche, tutte misurate:

1. **La resa del ciclo crolla in proporzione.** `mean_len` 2,66 → 2,44
   (−8,3%); i cicli totali per gli stessi 1.200 token passano da ~572 a ~738
   (+29%) [DEDOTTO da spec stats + timing]. Il ciclo più corto ma più
   frequente lascia il ms/token fermo.
2. **La bozza rifiuta il doppio.** Chiamate gen 556 → 707, bozze prodotte
   378 → 321: i rifiuti del gate di confidenza passano da 178 a 386 (32% →
   55% delle chiamate) [MISURATO]. Ogni rifiuto è un ciclo da 1 token senza
   speculazione. E l'accettazione della posizione 2 crolla: 0,698 → 0,533.
   Il meccanismo [DEDOTTO, da verificare]: DSpark legge gli **stati nascosti
   del bersaglio** (tap 41/42/43), e la verifica mascherata glieli sporca —
   la maschera non degrada solo la verifica, degrada il **proponente**. Se è
   vero, `LLAMA_SPEC_CONF_ESENTA_POS0` / conf più bassa recuperano parte del
   danno a parità di maschera.
3. **Costi per ciclo che scalano coi cicli.** Bozza: 744 × 12,36 ms = 9,20 s
   contro 576 × 12,60 = 7,26 s (+1,94 s) [MISURATO]. Più checkpoint
   (2,36 ms/ciclo, audit 34) e la tassa di ricattura del passaggio di taglia
   2→1→2 (~46-55 ms, audit 34) che scala con l'interleaving dei cicli
   singoli — i rifiuti raddoppiati raddoppiano proprio quelli.

La coppia a conf 0 (`c4_n2bm3` vs `c5_c2`) aggiunge il pezzo strutturale:
buchi solo −9,5% (158.631 → 143.473) perché **il 59% delle righe candidate
non ha NESSUN residente fra i suoi 6 esperti** (15.699 su 26.640) e resta
esatta, trasportando come oggi. La struttura per posizione [DEDOTTO da c2 +
c2e2]: pos-1 ≈ 38% senza residenti, pos-2 ≈ 80% (c2e2 misura pos-2 da sola:
10.967/13.768 = 79,7%). È il gradino della terza posizione di
`32-seconda-posizione.md` visto dall'altro lato: proprio dove la maschera
servirebbe di più, la cache non ha niente da offrirle. A conf 0 la maschera
paga il costo in resa (acc 0,778 → 0,738, t/s 9,43 → 8,96) comprando poco
trasporto.

Nota sul metro «colpi%»: con AM=1 le righe mascherate domandano **solo
residenti** — colpi per costruzione. Il 44,6% e 58,9% non sono confrontabili
col 25-30% dei bracci AM=0; il metro pulito del trasporto sono i **byte a
domanda** e i **buchi**.

Struttura identica a ogni leva di stanotte: il collo non è la banda, è la
**resa del ciclo** (orchestration-bound, di nuovo). Le leve conseguenti, in
ordine di promessa e tutte da misurare: (a) `LLAMA_ACCEPTMOE_SOGLIA` 0,05-0,2
— mai esercitata (`tenuti per soglia=0` ovunque): compra accettazione con un
po' di trasporto, attacca direttamente la bocca n.2; (b) E=2 — l'unico segno
positivo a conf 0 (9,53 vs 9,43, +1,1%), maschera solo la posizione dove il
trasporto è massimo (80% senza residenti) e il danno alla resa minimo;
(c) riparare il 22% di verify non armati (§3), che restituisce fino a
+29% di righe mascherate gratis.

---

## 5. Il costo in qualità (domanda 3 del mandato)

Il pareggio di `32-seconda-posizione.md` chiede p2' (accettazione della
posizione 2 sotto verifica mascherata) ≥ 0,45-0,60; sotto 0,45 la via è
chiusa.

| braccio | p2' misurata | verdetto |
|---|---|---|
| c5_c2 (E=1, conf 0) | 0,793 | sopra tutta la banda ✓ |
| c5_c2e2 (E=2, conf 0) | 0,832 | sopra tutta la banda ✓ |
| c5_c2c08 (E=1, conf 0,8) | 0,533 | sopra 0,45, dentro la banda grigia |

Confermo il verdetto del mandato con una riserva di misura: **la qualità non
è il vincolo oggi**, ma le p2' qui sopra sono **diluite** — il 38-80% delle
righe speculative è verificato esatto (senza residenti), quindi la p2' delle
sole righe davvero mascherate è più bassa di quella stampata [DEDOTTO]. Nel
braccio c08, dove la diluizione è minima (20,6% senza residenti), la p2' vera
è vicina a 0,533: sopra la soglia di chiusura, non «largamente». Il braccio
spia + TRACE (§3) dà l'accettazione per episodio e chiude anche questa.
Attenzione inoltre al doppio effetto: la maschera abbassa p2' E fa rifiutare
la bozza a monte (§4, bocca 2) — il secondo effetto oggi costa più del primo.

---

## 6. Cosa è stato toccato

| file | righe | cosa |
|---|---|---|
| `D:\ds4_work\llama_run\campagna5.ps1` | 167-175 | cancello: riga acceptmoe col massimo di `lanci`, non l'ultima |
| `ggml/src/ggml-cuda/cache-esperti.cu` | 2090-2105 | etichetta `[bersaglio]`/`[bozza]` sul dump + commento trappola |
| `src/llama-graph.cpp` | 2219-2231 | guardia: `n_expert_used <= 16` (caso warmup, cammino normale intatto) |
| `tools/server/server-context.cpp` | 3654-3676 | spia disarmo lato server (`LLAMA_ACCEPTMOE_SPIA`, spenta di default) |
| `src/llama-context.cpp` | 2089-2104 | spia disarmo lato contesto (stessa leva) |

Niente di tutto questo entra nel cammino a leve spente; il C0 resta
`CF2DEEA06E90` per costruzione (verificare comunque alla prossima compilazione:
C0 prima di ogni altro braccio, come da protocollo).

## 7. Il prossimo braccio di misura (uno solo, decide tre cose)

`c5_c2` ripetuto con `LLAMA_ACCEPTMOE_SPIA=1` e `LLAMA_TRACE=1`:

1. **il predicato** che disarma i ~96 verify veri (righe `replay=0`);
2. **il conteggio ripristini** (righe TRACE `restore checkpoint` ≡ righe
   spia `replay=1`) — chiude anche i resti mod 40 se combacia;
3. **la p2' per episodio** non diluita (righe TRACE `accepted N/M`).

Dopo, i due bracci di merito: `LLAMA_ACCEPTMOE_SOGLIA=0.1` su c08, e E=2 con
soglia — con questo cancello, stavolta, letto sulla riga giusta.
