# 32 — LA SECONDA POSIZIONE: perché costa più del doppio, e come farla costare meno

Data: 10 agosto 2026, notte. Radice `D:\llama-overlap`, ramo `overlap`, HEAD
`1e07e00` (+ patch sinkhorn/strumenti applicate nel worktree di misura).
**Niente compilato, niente eseguito**: solo codice, log già su disco (compresi i
bracci di campagna 3 atterrati DURANTE la stesura: `c3_n2c0/c05/c08`), ledger e
i 31 rapporti in `audit/`. Marcatura: [MISURATO] = log o codice letto riga per
riga; [DEDOTTO] = aritmetica su misure; [IPOTESI] = da falsificare, misura
indicata. Sono il sesto agente: ogni conversione in t/s dichiara la voce, i ms
contabili e il fattore α, con la banda — mai il numero secco.

## L'esito in cinque righe

1. La seconda posizione costa più del doppio perché **non aggiunge solo buchi:
   cambia il regime in cui i buchi si pagano**. A n-max 1 i buchi sono quasi
   gratis (26.000 buchi in meno NON accorciano il ciclo — misurato nella
   spazzata K); a n-max 2 il working set (unione di 3 posizioni ≈ 535-580
   esperti) sfonda i 339 slot, i colpi crollano 57,5%→22,2%, e ogni buco torna
   a tariffa quasi piena. Il conto dei buchi da solo, a 0,221 ms, predice il
   **99% del Δ per token** (20,5 su 20,7 ms).
2. Il cancello d'ammissione della cache **NON c'entra**: a n-max 2 la cache
   resta accesa (verificato nel codice, tre condizioni su tre passano; i
   contatori vivi nei log lo confermano). Il cancello che SI spegne è un altro:
   `LLAMA_OVERLAP_BATCH_MAX` — e **la base di campagna 3 lo tiene a 2, spegnendo
   il ramo CPU proprio nei bracci n-max 2**, cosa che la campagna della notte
   prima non faceva (`BATCH_MAX = n-max+1`). Il controllo 8,69 è handicappato
   dalla configurazione, non dalla fisica.
3. `--spec-draft-conf-min` tronca DOPO la bozza ma PRIMA della verifica: spende
   gli 8-12 ms della bozza e risparmia i ~116 della posizione verificata — è il
   verso giusto. Ha però un difetto: **tronca anche la posizione 0**, e a soglia
   0,8 il 38% dei cicli gira SENZA speculazione. Esentare la posizione 0 è una
   patch da tre righe.
4. `patch_acceptmoe.diff` attacca esattamente questo problema (le righe ≥ 1
   verificate sui soli residenti: niente trasporto, niente thrashing). Il suo
   break-even chiedeva p2' ≥ 0,35-0,60: **il p2 pulito ora è misurato, 0,71-0,76**
   — c'è margine di degrado per la maschera. È l'unica via con spazio SOPRA il
   muro di n-max 1.
5. L'aritmetica del muro: al ciclo attuale di n-max 2 (261,3-261,7 ms) **nemmeno
   una bozza perfetta paga** (3 token/261,7 = 11,46 < 12,66). Per battere
   12,83-12,95 servono ≤ 201-234 ms/ciclo. Le leve gratis (lane, conf, fork,
   FUSO) chiudono metà del divario; il resto passa da AcceptMoE o dal rollback
   parziale del KV — o il fronte si chiude.

---

## 0. I numeri di riferimento (provenienza, prima di tutto)

Tutti [MISURATO] dai log in `D:\ds4_work\llama_run\` (prompt `jprompt.txt`,
1200 tk, temp 0, `TOPK=1`, 339+32 slot, K=2, ub 64, -t 7). `p1`/`p2` dalla riga
per-slot `acc per pos` (i contatori PULITI; quelli interni sono gonfiati dai
replay — audit 16). `ciclo = 1000·mean_len/t_s`.

| braccio | n-max | FUSO | conf | lane a 3 tok | t/s | ciclo ms | mean_len | p1 | p2 | domande | colpi | buchi | bozza ms/chiamata |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fu7_k2` | 1 | 7 | — | n/a (2 tok) | 12,63 | 145,7 | 1,84 | 0,841 | — | 155.796 | 57,5% | 66.261 | 8,30 |
| `c2_f5` | 1 | 5 | — | n/a | 12,83 | 145,8 | 1,87 | — | — | 153.628 | 58,1% | 64.304 | 8,43 |
| `c2_k2fork` (FORK=1) | 1 | 7 | — | n/a | **12,95** | 145,9 | 1,89 | — | — | 191.724 | 53,9% | 88.373 | 8,30 |
| `fu7_n2` | 2 | 7 | — | **SÌ** (BM=3) | 10,01 | 261,7 | 2,62 | 0,867 | 0,755 | 228.244 | 22,2% | 177.577 | 11,87 |
| `fu0_n2` | 2 | 0 | — | SÌ (BM=3) | 7,63 | 330,3 | 2,52 | — | — | 261.472 | 23,5% | 200.090 | 14,01 |
| `c3_n2c0` | 2 | 5 | 0 | **NO** (BM=2) | 8,69 | 295,7 | 2,57 | 0,863 | 0,706 | 301.000 | 31,5% | 206.203 | 12,04 |
| `c3_n2c05` | 2 | 5 | 0,5 | NO | 9,35 | 265,2 | 2,48 | 0,904 | 0,574† | 257.014 | 38,0% | 159.223 | 11,88 |
| `c3_n2c08` | 2 | 5 | 0,8 | NO | 9,99 | 261,3 | 2,61 | 0,976† | 0,630† | 240.220 | 36,7% | 152.028 | 11,81 |

† condizionati dal troncamento (sopravvivono solo le posizioni fiduciose:
p1 alto per selezione, p2 misurato sui soli secondi proposti). `c3_n2c095` era
in corsa alla stesura. La colonna "lane a 3 tok" viene dagli script:
`campagna_notte.ps1:84` imposta `LLAMA_OVERLAP_BATCH_MAX = n-max+1`,
`campagna3.ps1:92` lo fissa a **2** — è una variabile NON controllata fra le
due basi n-max 2, e i contatori la vedono (domande/token 190 contro 251).

Nota di coerenza: `mean_len` stampato (2,62) contro `1+p1+p1·p2` (2,52) scarta
del 4% — dentro la banda nota dei contatori a battito (regola di casa). Uso i
numeri stampati, come il mandato.

---

## 1. Perché più del doppio: quattro meccanismi, uno domina

### 1a. Il conto per token chiude sul trasporto [MISURATO]+[DEDOTTO]

Coppia pulita `fu7_k2 → fu7_n2` (stesso FUSO, stessa K, lane attiva in
entrambi):

```
t/token:      145,7/1,84 = 79,2   →   261,7/2,62 = 99,9     Δ = +20,7 ms
buchi/token:  66.261/1200 = 55,2  →   177.577/1200 = 148,0  Δ = +92,8
legge misurata: 0,221 × 92,8 = +20,5 ms/token               (99% del Δ)
```

**Il conto dei buchi da solo predice il 99% del degrado per token.** Il termine
prenotazioni della legge è zero (W=0 in tutti i bracci). La tariffa 0,221 è il
marginale misurato FRA 98.030 e 195.860 buchi — cioè dentro il regime n-max 2:
lì vale ~0,8 del tempo-byte nominale (0,271), quasi piena.

### 1b. Ma la stessa tariffa NON vale a n-max 1: il regime coperto [MISURATO]

La spazzata K di campagna 2 (tutta a n-max 1) è l'esperimento controllato:

```
K=2    buchi 66.261    ciclo 145,7     (campagna 2, base fusa)
K=3    buchi 40.549    ciclo 150,6     −26.000 buchi → ciclo INVARIATO (anzi +5)
K=4    buchi ~23.000   ciclo 194,6     (il ramo CPU sporge: α_cpu→1;
                                        base pre-fusione del 9/8, stesso verso)
```

A n-max 1 togliere 26.000 buchi non compra un millisecondo: sono COPERTI
(fork/join α=0,08; sonda join 98,7% copie già atterrate; K_ADATTIVO §0). Il
ciclo resta inchiodato a 145-146 su sei configurazioni con buchi da 62k a 88k.

**Questa è la risposta alla domanda del mandato.** La seconda posizione non
raddoppia il lavoro: sposta il sistema dal regime in cui il trasporto è
nascosto (α_buco 0,08-0,25) a quello in cui è la spina seriale
(`decidi → copia → MMVQ` sullo stesso stream, α→~0,8-1). Si paga due volte:
più buchi, E ogni buco a tariffa piena.

### 1c. Perché i buchi vanno per 2,7: la scomposizione [DEDOTTO su MISURATO]

```
buchi/token ×2,68  =  domande/token ×1,465  ×  tasso-buco ×1,83
                       (129,8 → 190,2)         (42,5% → 77,8%)
```

- **tasso-buco ×1,83**: il working set di un forward a 3 posizioni è l'unione
  di 3 route consecutive ≈ 535-580 esperti (§2) contro 339 slot: la LRU non ha
  dove mettere le cose. Colpi 57,5→22,2.
- **domande/token ×1,465**: tre effetti — la terza riga (+1 posizione da
  interrogare), i replay in più (§1d, forward extra che rifanno domande), e la
  minore deduplica utile per posizione. Nei bracci campagna-3 c'è il quarto
  effetto autoinflitto: lane spenta → +50% domande per posizione (258 invece
  di ~172; il commento del codice lo prezza: `llama-graph.cpp:1866-1869`,
  "~171/token a k=2"). Misurato: 251 domande/token (`c3_n2c0`, lane off)
  contro 190 (`fu7_n2`, lane on).

### 1d. Il bilancio per ciclo: +116 ms, voce per voce [DEDOTTO]

```
Δciclo misurato (fu7_k2 → fu7_n2):                       +116,0 ms
  trasporto:   Δbuchi/ciclo (101,6 → 387,7) × 0,221   =   +63,2   (54%)
  replay in più: forward/ciclo 1,137 → 1,309 (§3 del ledger 9/8:
    13,7% → 30,9% ripristini) × pavimento forward ~90-110 = +15-19
  terza riga: MMVQ esperti 258×0,063 ≈ 16; densi ~0
    (si leggono per forward); quota lanci ~0-5           =   +16-21
  bozza: blocco da 2 invece di 1 (8,30 → 11,87)         =   +3,6
  somma                                                  =   98-107
```

Chiude su 116 entro l'8-15%; il residuo è orchestrazione/host dei forward in
più. Le due contabilità (per token al 99%, per ciclo al ~90%) si riconciliano
con l'ammortamento: i costi fissi del ciclo si spalmano su 2,62 token invece
di 1,84, e quel risparmio compensa quasi esattamente MMVQ e replay extra. **La
bozza è innocente**: per token costa uguale (8,3/1,84 ≈ 11,9/2,62 ≈ 4,5 ms).

### 1e. I replay da checkpoint: la tassa strutturale [MISURATO codice + ledger]

`llama_kv_cache_dsv4::seq_rm` **rifiuta ogni rimozione parziale**
(`llama-kv-cache-dsv4.cpp:1307-1321`: `p1>=0 → false`; `p0>0` con dati →
`false` — "compressed rows are derived from running compressor state, not
reconstructible"). Quindi ogni accettazione parziale ripristina il checkpoint e
**rigioca un forward intero** (`server-context.cpp:3839-3859`). A n-max 1
capita sul ~13,7% dei cicli (i rigetti); a n-max 2 su tutto ciò che non è
accettazione piena: **30,9%** (ledger 9/8, via discrepanza contatori 517/599).
Un forward su tre non produce token nuovi. Nei log a `-lv 4` la riga
`restore checkpoint` non compare: il conteggio sul base attuale è uno dei dati
"solo eseguendo" (o solo alzando il livello di log).

---

## 2. Risposta 1 — quanto è grande davvero l'unione

Le misure in casa (tracce oracolo, `albero_unione_route.py`; ledger 6-8/8):

```
U(1) = 258        (per costruzione)
U(2) = 420-446    = 1,63-1,73×   (sovrapposizione a distanza 1: ~40%)
U(8) = 1.105-1.244               (pendenza ~114-133 esperti nuovi/posizione)
U(3) ≈ 535-580    = 2,07-2,24×   [DEDOTTO, interpolazione W2→W8]
```

Risposta alla dicotomia del mandato: **l'unione NON è quasi-2× per posizione**
(ogni posizione in più porta ~0,45-0,52 posizioni di esperti nuovi), **ma il
totale sfonda comunque**: U(3)/339 = 1,58-1,71. La cache è sotto capienza di un
fattore ~1,6-1,7 a tre posizioni — e già U(2) = 413-446 > 339 a due.

**Non è la politica.** Due prove: (a) a 401 slot i colpi risalgono a 53,4%, a
448 a 67,7% ("e la curva non si era ancora fermata") — la LRU recupera appena
la capienza si avvicina all'unione; (b) la stessa LRU tiene il 57,5% a n-max 1.
Una politica che funziona a working set ≤ capienza e collassa a working set
1,6× la capienza sta fallendo di capienza, non di politica.

**E la capienza non è finanziabile**: n-max 2 a 448 slot fa 9,00-9,17 t/s
NONOSTANTE i colpi 67,7% (ledger 9/8) — sotto il 10,40 di n-max 1 di allora —
perché la VRAM si strozza (il muro dei ~540 MiB liberi) e il resto della tassa
(replay, riga in più) resta. Su 12 GB questo ramo è chiuso con un numero.

---

## 3. Risposta 3 — il cancello della cache NON si spegne (verificato nel codice)

Il sospetto del mandato ("se il batch di verifica supera il cancello, la cache
si spegne e spiega tutto") è **falsificato**. Le condizioni d'ammissione
(`ggml-cuda.cu:2195-2200`) sul batch di verifica a n-max 2
(`ids` = [6, 3]: 6 esperti × 3 token; una sola ubatch perché 3 < ub 64):

| condizione | valore a n-max 2 | esito |
|---|---|---|
| `ids->ne[0]*ne[1] <= 64` (capienza `c.lista`) | 18 | passa |
| `ids->ne[1] <= batch_max` (`LLAMA_CACHE_ESPERTI_BATCH`, difetto 8, `cache-esperti.cu:152-168`; le campagne lo passano esplicito a 8) | 3 | passa |
| `dst->ne[2] <= get_mmvq_mmid_max_batch` (=8 per i nostri formati; il minimo di qualunque tabella è 4 — PAVIMENTO §1c) | 3 | passa |

Anche n-max 5 passerebbe (36 id, 6 token). Conferma empirica: i contatori
`domanda/colpi/buchi` a n-max 2 sono vivi e contano 228-301k domande — una
cache spenta stamperebbe `domanda 0` (è il sintomo misurato il 6/8 con np=2).

**Il cancello che SI spegne è l'overlap**: `build_moe_ffn_overlap` ritorna
`nullptr` se `n_tokens > LLAMA_OVERLAP_BATCH_MAX` (`llama-graph.cpp:1834-1843`)
— niente partizione, niente ramo CPU, tutti i 6 esperti alla cache. Il difetto
è 1; campagna 3 lo tiene a **2** (`campagna3.ps1:92`), quindi il batch di
verifica da 3 token lo sfonda e la lane muore in silenzio. La campagna della
notte del 9/8 invece scalava `BATCH_MAX = n-max+1` (`campagna_notte.ps1:84`):
`fu7_n2` girava CON la lane. Il commento di guardia in
`llama-graph.cpp:1822-1833` ("lo split si ingaggia solo a un token... finché la
cura non è scritta") è **stantio**: la cura c'è — griglia FISSA da
`GGML_CACHE_ESPERTI_TOK_MAX=32` thread con taglio a `n_tok` letto dal device
(`cache-esperti.cu:1670-1697`), variabile solo col braccio diagnostico
`GRIGLIA_VARIABILE=1` — e l'evidenza empirica pure (fu7_n2/fu0_n2: uscita sana,
p1 0,867, nessuna degenerazione). Resta prudente il rilevatore di divergenze
acceso alla prima corsa.

---

## 4. Risposta 4 — `--spec-draft-conf-min`: come è fatto, cosa paga

Consumatore letto riga per riga (`common/speculative.cpp:1146-1261`, ramo
`is_dspark`):

1. la bozza costruisce UN batch con l'intero blocco:
   `n_block_tokens = n_draft` (riga 1176: `+ (is_dspark ? 0 : 1)` — per DSpark
   niente token extra) e fa UNA `llama_decode` (riga 1189) — la testa di
   Markov `block_size=5` propaga in-grafo con `argmax` (`dflash.cpp:298-325`);
2. DOPO il decode, nel loop di campionamento, legge la confidenza e **spezza
   alla prima posizione sotto soglia** (righe 1211-1218:
   `if (conf[idx*n_embd_dec] < conf_min) break;`);
3. i token oltre la rottura non entrano in `result` → **non entrano nel batch
   di verifica** (`server-context.cpp:488-518`: il batch è
   `[campionato + spec_draft]`).

**Il troncamento avviene dopo che la bozza ha già calcolato la posizione:
risparmia la VERIFICA, non la BOZZA.** Ed è il verso giusto: la bozza costa
8,3-12,0 ms/chiamata (≈4,5 ms/token, il 4-6% del ciclo), la posizione
verificata ~116 ms. Il canale è sano anche nei dettagli: la confidenza è una
**sigmoide** (quindi in [0,1] — il dubbio di scala del mandato di campagna 3 è
chiuso: `dflash.cpp:309-317`), e il `ggml_repeat` a [n_embd, n_tok]
(`dflash.cpp:337`) allinea il passo di lettura del consumatore.

**Il difetto trovato**: il loop parte da `i = 0` — la soglia può azzerare
l'INTERA bozza. Misurato nei bracci freschi: a conf 0,5 il **27%** dei cicli
gira senza speculazione (147/543 chiamate a vuoto), a 0,8 il **38%** (225/593).
Quei cicli decodificano 1 token a ~F(1) ≈ 100+ ms: si butta il guadagno di
p1 ≈ 0,86 su cicli in cui la PRIMA posizione era comunque un buon affare
(anche a p1 0,68 la speculazione a 1 vince: 145,7/1,68 = 87 < 100+). La soglia
economica giusta gata solo la posizione ≥ 1, cioè la posizione da 116 ms.
Esenzione di `i == 0`: tre righe nel consumatore. [MISURATO + proposta]

Effetto misurato della leva così com'è (base FUSO=5, lane off — il peggiore dei
mondi): 8,69 → 9,35 → **9,99** (conf 0 → 0,5 → 0,8), buchi −26%, p2 fra i
secondi proposti 0,63-0,76. La leva morde. Ma da sola non può vincere: sceglie
QUANDO pagare il ciclo da 3 token, non quanto costa.

---

## 5. Risposta 5 — `patch_acceptmoe.diff`: attacca esattamente questo problema

Letta (13 file, +512/−3, `git apply --check` passava su HEAD 1e07e00;
struttura confermata sul diff: le due op fra router e `MUL_MAT_ID` che
riscrivono id/pesi delle righe `t ≥ n_esatte` sui soli esperti RESIDENTI, arm
one-shot dal server con guardia `!slot.spec_replay` — riga 739 del diff — e
identità bit-esatta a leva spenta). L'analisi completa è in
`audit/ACCEPTMOE.md`; qui il punto per QUESTO fronte:

- **attacca la radice, non il sintomo**: per le righe mascherate la domanda
  vede solo residenti ⇒ zero trasporti, zero installazioni, zero sfratti. Il
  working set del ciclo torna ~1 posizione: sparisce il gradino di capienza
  (§2) E la tariffa piena (§1b) insieme. È l'unica leva del catalogo che va
  nel verso del deficit di capienza.
- **cosa fa alla qualità** (dichiarato, non azzerabile): il KV delle righe
  accettate resta approssimato (~46% dei token a regime; mitigato dai
  ripristini che rigiocano esatto), correttivo e bonus campionati da logit
  approssimati quando la divergenza è su riga ≥ 1. Il paper omologo misura
  −0,27 punti sui suoi bench; il nostro va misurato (cancello di qualità sul
  testo, C3).
- **il break-even si è mosso a favore**: l'audit chiedeva p2' ≥ 0,35-0,60 con
  p2 ignoto. Ora p2 pulito è misurato: **0,706-0,755** senza maschera
  (`fu7_n2`, `c3_n2c0`), 0,63 fra i secondi fiduciosi. Il margine di degrado
  concesso alla maschera è 0,15-0,35 — non è più una scommessa alla cieca.
- verso la composizione: conf-min sceglie QUANDO bozzarne 2 (p2 condizionato
  alto), AcceptMoE rende quasi gratis VERIFICARLI. Si compongono senza
  toccarsi (territori disgiunti nel codice).

---

## 6. Le vie, ordinate per credibilità

Metrica dichiarata: `t/s = 1000 × mean_len / ms_ciclo`. Base di confronto: il
muro n-max 1 = **12,83-12,95** (c2_f5 / c2_k2fork). Ogni via dichiara cosa
tocca, l'intervallo, il costo, il cancello che la uccide.

### Via 1 — ridare la lane al batch da 3: `OVERLAP_BATCH_MAX = n-max+1` [una corsa, zero rischio nuovo]

- **Meccanismo**: già misurato per contrasto — con lane: 190 domande/token
  (`fu7_n2`); senza: 251 (`c3_n2c0`). Il ramo CPU toglie ~1/3 delle domande
  alla cache E rimette concorrenza CPU∥GPU nel regime dove il trasporto è nudo.
  La paura di correttezza del commento di guardia è superata (griglia fissa +
  corsa notturna sana, §3); rilevatore di divergenze acceso comunque.
- **Tocca**: `ms_ciclo` −10/−25 (buchi −20/−30 per token × 0,221, α qui ~1
  perché il regime è scoperto — è il canale del fit, non una speranza);
  `mean_len` invariato.
- **Intervallo**: su `c3_n2c08` (9,99): **10,4-11,0**. Già incassato di fatto
  in `fu7_n2` rispetto al suo gemello spento.
- **Cancello che la falsifica**: se il braccio `c08 + BM=3` non porta le
  domande/token sotto ~200 il cancello non sta ingaggiando (leggere il
  contatore, non il t/s); se compare UNA divergenza dal rilevatore o testo
  degenerato (la firma 41/11 righe uniche), via chiusa finché la cura non è
  ri-verificata.

### Via 2 — conf-min con la posizione 0 esente [3 righe + una corsa]

- **Meccanismo**: §4 — oggi a soglia 0,8 il 38% dei cicli perde TUTTA la
  speculazione; esentare `i==0` tiene p1 ≈ 0,85-0,86 su ogni ciclo e gata solo
  la posizione da 116 ms.
- **Tocca**: `mean_len` +0,1/+0,3 (recupera i cicli senza bozza); `ms_ciclo`
  ±0/−5 (meno decodifiche piatte da 1 token).
- **Intervallo**: +0,3/+0,8 sopra la Via 1 → **10,7-11,6** composte.
- **Cancello**: la SPIA resta `mean_len` (regola di campagna 3): se con
  l'esenzione `mean_len` non sale rispetto a c08 a parità di soglia, i cicli
  recuperati avevano p1 davvero marcio e la patch non paga. `c3_n2c095` (in
  corsa) delimita il ginocchio della soglia prima di scrivere.

### Via 3 — FUSO=7 e FORK=1 sui bracci n-max 2 [due corse gratis]

- **Meccanismo**: (a) la fusione HC pesa DI PIÙ dove i forward per token sono
  di più: fu0→fu7 a n-max 2 vale +2,38 t/s (7,63→10,01) contro +1,8 a n-max 1;
  la scelta FUSO=5 di campagna 3 (giusta a n-max 1 per il p1: 12,83 contro
  12,66) non è mai stata verificata a n-max 2 — il confronto 10,01(FUSO7)
  contro 8,69(FUSO5) è sporco della lane (§0). (b) FORK=1: copre le copie
  sotto l'MMVQ residente; a n-max 1 vale +0,32 (12,63→12,95) in regime già
  coperto — a n-max 2 il canale è 3-4 volte più grosso ma la copertura è
  limitata dal lavoro residente disponibile (~15-20 ms/ciclo).
- **Tocca**: `ms_ciclo` (FUSO: −10/−30 se il segno di n-max 2 tiene; FORK:
  −5/−15 con α 0,3-0,8 nel regime nudo); `mean_len` −0/−0,1 (FUSO=7 costa
  qualche punto di p1; il fork cambia l'accettazione — confronto a parità di
  metrica, lezione PAVIMENTO §5).
- **Intervallo composto con Vie 1-2**: **11,0-12,3**.
- **Cancello**: FUSO — il braccio appaiato `n2-fuso5/fuso7 a parità di lane`;
  se escono pari, il +1,32 era tutto lane e la voce si chiude. FORK — il
  contatore `fork` nel dump: se i join non crescono, a batch 3 non ingaggia.

### Via 4 — AcceptMoE [ricompilazione + serie C0→C3 di ACCEPTMOE.md]

- **Meccanismo**: §5. La terza posizione mascherata costa il calcolo residente
  (+25-40 ms contabili) invece di +116.
- **Tocca**: `ms_ciclo` → ciclo(3 pos) ≈ 145,7+25...40 = **171-186 ms**
  [DEDOTTO dall'audit, riscalato sulla base fusa]; `mean_len` → dipende da
  p1'≈0,84-0,87 (riga 0 esatta) e p2' = 0,71-0,76 − Δmaschera (ignoto).
- **Intervallo**: se Δmaschera ≤ 0,15 → mean_len 2,4-2,55 → **12,9-14,9**.
  Break-even contro 12,83: serve `1+p1'+p1'p2' ≥ 12,83 × ciclo/1000`, cioè a
  ciclo 178 ms: p2' ≥ 0,45-0,60. **È l'unica via con spazio sopra il muro.**
- **Costo**: applicare la patch (attenzione: scritta contro 1e07e00 pulito; il
  worktree ora ha sinkhorn/strumenti sopra — `git apply --check` va rifatto),
  ricompilare, serie C0 (identità a leva spenta, SHA `B396AB2137B2080A`) → C1
  → C2 → C3. Mezza giornata di macchina.
- **Cancello**: C0-C2 come da audit; il falsificatore vero è **C3**: p2'
  mascherato < 0,45 O testo degradato a occhio ⇒ via chiusa (e con lei il
  blocco lungo per costruzione, non solo per misura).

### Via 5 — rollback parziale del KV DSV4 [cantiere, vale su ENTRAMBI i regimi]

- **Meccanismo**: §1e. Eliminare i ripristini toglie il 30,9% di forward a
  n-max 2 (−25/−37 ms/ciclo → 11,1-11,6 da sola) e il 13,7% a n-max 1
  (−10/−14 ms → **13,5-13,9**: è l'unica via che ALZA IL MURO stesso; il
  "tetto 13,79" vale a ciclo 145 — a ciclo 132 il tetto è 15,2). α≈1: un
  forward intero è seriale per costruzione, non c'è copertura da scontare.
- **Costo**: cantiere medio dentro `llama-kv-cache-dsv4.cpp` — lo stato del
  compressore non è ricostruibile (righe 1312-1320), quindi la forma fattibile
  è il checkpoint per-posizione dello stato compressore durante la verifica.
  Fattibilità e taglia dello stato: da leggere PRIMA di stimare oltre.
- **Cancello**: (gratis, primo passo) contare e cronometrare i restore sul
  base attuale — se il loro costo reale è < 8 ms/ciclo a n-max 1, la via si
  ridimensiona sotto le vie gratis e non merita il cantiere. Falsificatore
  architetturale: snapshot del compressore ≥ costo del replay.

### Via 6 — capienza: CHIUSA [già misurata]

448 slot a n-max 2: colpi 67,7% e **9,00-9,17 t/s** — sotto n-max 1 —
per VRAM strozzata (muro ~540 MiB liberi) più la tassa replay/riga intatta.
U(3) ≈ 535-580 slot non è finanziabile su 12 GB. La scheda da 24 GB resta
l'argomento "larghezza" del ledger, fuori da questo hardware.

---

## 7. Il verdetto aritmetico: n-max 2 può pagare?

Il muro da battere è 12,83-12,95 (e con Via 5 salirebbe). La barra sul ciclo:

```
ciclo(n-max 2) ≤ 1000 × mean_len / 12,9
  a mean_len 3,00 (bozza PERFETTA):  ≤ 233 ms
  a mean_len 2,60 (realistico):      ≤ 202 ms
oggi: 261,3-295,7 ms.   Al ciclo attuale nemmeno mean_len = 3 paga (11,46).
```

- **Le vie gratis (1+2+3) arrivano a ~11,0-12,3**: chiudono metà-due terzi del
  divario e NON bastano. Dichiarato col metodo: i loro canali si sovrappongono
  sul termine buchi, li ho composti una volta sola; la banda alta assume che il
  segno di FUSO=7 a n-max 2 tenga.
- **Sopra il muro passano solo**: Via 4 (AcceptMoE, se p2' regge ≥ 0,45-0,60 —
  margine misurato 0,15-0,35) oppure Via 5 composta con 1-3 (se il cantiere è
  fattibile). Nessuna delle due è garantita; entrambe hanno il falsificatore
  scritto.
- **Se C3 di AcceptMoE fallisce E il rollback è infattibile**, la chiusura
  onesta è: su 12 GB il blocco ≥ 2 non paga, perché la posizione marginale
  chiede o capienza che non c'è (U(3) ≈ 1,6-1,7× gli slot) o una verifica che
  non trasporti — e a quel punto il fronte torna dove il rendimento è certo:
  n-max 1 è all'8,9% dal suo tetto, e Via 5 lo alzerebbe.

Nota di metodo sulla calibrazione chiesta dal mandato: il fattore 0,08-0,43
vale per i canali COPERTI (è la storia delle cinque sovrastime, tutte a
n-max 1). A n-max 2 il canale buchi converte ~1:1 — non per ottimismo, ma
perché il fit 0,221 è misurato DENTRO quel regime e chiude al 99% (§1a). Le
bande qui sopra usano α≈1 solo su quel canale; tutto il resto (coperture
FORK, composizioni, p2') resta scontato o dichiarato ignoto.

---

## Dati che si ottengono solo eseguendo (in ordine di valore, con cosa decidono)

1. **`c3_n2c095`** (già in coda, gratis): delimita il ginocchio della soglia —
   se `mean_len` crolla verso 1,9-2,0, la soglia oltre 0,8 sovra-tronca e la
   frontiera di conf-min è già vista a 0,8.
2. **Braccio `n-max 2 + conf 0,8 + FUSO=7 + BATCH_MAX=3 (+FORK=1)`** (una
   corsa): il composito delle vie gratis. Decide se il pavimento n-max 2 sale
   a 10,4-11,6 e se FUSO/lane/fork compongono; contatori da leggere: domande e
   buchi ASSOLUTI per token (mai la percentuale di colpi), rilevatore
   divergenze = 0.
3. **p2' mascherato (C3 di AcceptMoE)**: il numero che nessuna aritmetica può
   sostituire — decide l'unica via sopra il muro. Prima C0/C1 (SHA
   `B396AB2137B2080A`) che decidono se la patch è applicabile sul worktree
   attuale.
4. **Conteggio e costo dei ripristini sul base attuale** (log a livello più
   alto o discrepanza contatori 517/599): decide se la Via 5 merita il
   cantiere (soglia: ≥ 8 ms/ciclo a n-max 1).
5. **`U(3)` esatto dalle tracce oracolo** (`albero_unione_route.py`, zero
   GPU): sostituisce l'interpolazione 535-580 e fissa la quota capienza/politica
   del §2 — utile solo se qualcuno ripropone slot o politiche.
6. **Braccio appaiato FUSO 5/7 a n-max 2 a parità di lane**: separa i +1,32
   t/s di `fu7_n2 − c3_n2c0` fra fusione e lane; corregge la base di ogni
   campagna n-max 2 futura.
