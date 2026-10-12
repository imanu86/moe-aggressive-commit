# Ricognizione PR e fork di Strata dopo la 0.1.43 — 13 ottobre 2026

Ricognizione in sola lettura con `gh`: niente GPU, niente build, niente commenti né PR su GitHub. Fonti:
- `Niko1221/Strata`: commit `v0.1.43...main`, release v0.1.43.1, 1 310 PR (tutte quelle del repo, dal 25/09). Ho letto
  per intero corpo e commenti di 78 PR tematiche e, tramite un sub-agente, di 63 PR di benchmark;
- fork: 2 217, di cui ~50 attivi esaminati da un sub-agente (§4);
- confronto con il registro `stack/INDEX.md` del fork (`lab/upsync43-pulito`, 17 leve), con `strata-0143-daily.json` e
  con il log `strata_0143_daily.log`.

Abbreviazioni: **M** = merged o portata in una release (upstream chiude quasi tutte le PR e le porta a mano conservando
l'autore: «chiusa» non vuol dire «respinta»); **A** = aperta; **F** = solo nel fork; **ce l'abbiamo** = leva già nella
pila o nella Daily.

## 0. Conclusione

- **Upstream dopo la 0.1.43** ha solo la hotfix **0.1.43.1** (33 commit, nessuna leva di velocità per la singola chat).
  Per noi conta **a0116b27**: su un layer split con `--batch`, i gruppi in pipeline battono `--batch-mtp`
  (2x A4000, 4 richieste: 62,3 → 85,2 t/s). È la causa più probabile del nostro tetto di ~45 t/s in multi-chat, che
  misuravamo proprio con `--batch-mtp` e un solo gruppo. Sulla 0.1.43 si ottiene già senza codice:
  `--batch-groups auto` (o `2`) e niente `--batch-mtp`.
- **Trovato nel nostro log**: «multi-GPU under WDDM: at most 8 GiB of the expert arena is pinned … 10 slices pinned
  (7 GiB)». Su 29,6 GiB di arena, quindi, i ~22 GiB restanti sono pageable: sono gli stessi riempimenti di cache
  «pageable sulla 2080 Ti» del roofline. #1905 (`STRATA_PIN_BY_NEED`) registra gli esperti che non stanno in VRAM,
  ordinati per profilo, e non il prefisso dell'arena. Il primo passo costa zero: un A/B di `STRATA_ARENA_PIN_GIB`
  (16, 24) sulla Daily.
- **Due leve sm_75 nuove e bit per bit**, di rafatxf su 2080 Ti:
  - #2069 parte 2: layout degli esperti «mode 4» (gate/up −9/−14% e down −17/−22% a 1-2 voci per esperto, misurato su
    righe Q2_0). Si prova senza codice con `STRATA_EXP_MODE=4`, con due avvertenze: le finestre da 4 token e i
    nostri down IQ4_NL;
  - #2070: kernel hyper-connection up per 3+ token e down a coppie (+0,6/+2,3%).

  La parte «tabelle MMVQ» di #2069 si sovrappone invece a B6 (da noi #1437 dava 0,0%).
- **Windows abbassa i clock della scheda che aspetta** (#1748): una 3070 in P5 con la memoria a 810 MHz fra una finestra e
  l'altra. Con `nvidia-smi -lgc/-lmc` è passata da 12-22 a 3,7-4,1 ms di attesa (decode 33,8 → 41,8). Da noi le schede
  lavorano insieme solo il 24% del tempo, quindi ciascuna resta ferma per molti ms a finestra: è la leva a costo zero
  più promettente da misurare. Bloccare i clock è un'azione di sistema: la fa l'owner, da amministratore. In
  alternativa, il fork NTRYourWaifu tiene sveglia la scheda con un kernel (`keep_warm.cu`).
- **Dai fork, la leva più vicina al nostro collo di bottiglia**: NTRYourWaifu v7/v8 interroga eventi e stream della
  pipeline **senza `cudaSetDevice`**, cioè il flush WDDM ogni 2 ms di `Verifier::service`, `done()` e i polling della
  catena MTP (+52 righe, 88,2 → 90,6 t/s dichiarati). Le nostre ~2 ms di attesa host per stadio hanno la stessa
  firma.
- **Per il ridisegno** (`lab/pipeline2`) le idee strutturali con numeri veri sono:
  - expert-parallel per layer (#1798, SYCL): +13-15% contro il layer split su 2x Arc, con l'handshake per layer a
    26 µs;
  - finestre di verifica larghe condivise fra le chat (#1524: 1,3-2,1x a 4 stream, una sola scheda);
  - gruppi in pipeline che tengono le bozze MTP per slot: oggi upstream deve scegliere fra pipeline e `--batch-mtp`;
  - hand-off con flag su GPU e lancio anticipato dello stadio successivo (#1120);
  - catena MTP su un'altra scheda o lanciata con una sola attesa per giro (#492).
- **Benchmark della community**: a 131k il nostro 77/70 t/s è nella fascia alta delle coppie Turing/Ampere. Per GB/s
  di banda siamo sopra la 2x 2080 Ti a 250 W (#1509: 84,1/75,1 a 4K/32K). Sotto di noi c'è la sola coppia
  eterogenea simile su Windows (3060 + 4060 Ti, #2000: 46,8). Il margine vero è nel multi-chat: `--batch-groups` dà
  +46…78% aggregato (#1834, #1508).

## 1. Upstream dopo v0.1.43 (`v0.1.43...main` = 33 commit, tutti nella release v0.1.43.1 del 12/10)

| commit | cosa | per noi | ce l'abbiamo | sforzo |
|---|---|---|---|---|
| [a0116b27](https://github.com/Niko1221/Strata/commit/a0116b27) | layer split + `--batch`: i gruppi in pipeline vincono su `--batch-mtp`. 2x A4000: 4 richieste 62,3 → 85,2 t/s, 2 richieste 55,9 → 69,6 (#2038) | **alto per il multi-chat**: il nostro 45,6 aggregato era misurato con `--batch-mtp` e un solo gruppo | no; sulla 0.1.43 si ottiene a mano con `--batch-groups auto` senza `--batch-mtp` | config: zero; port: +29/−11, `generate.cpp` |
| [af6affb8](https://github.com/Niko1221/Strata/commit/af6affb8), 4468e0e6 | prestito del prompt: un chunk più piccolo di quello automatico può avere bisogno di più slot; ora si dimezza invece di chiudere il motore (#2090) | robustezza, tocca la stessa zona della nostra patch 02 (prestito per stadio) | no | piccolo, conflitto probabile con 02 |
| [7bab660b](https://github.com/Niko1221/Strata/commit/7bab660b) | ogni copia H2D pageable del prompt passa da un anello di buffer pinned (#1996: crash AMD) | correttezza; prompt invariato (±0,2%) | no | +215/−17 (`mtp.cpp`, `prefill.cpp`) |
| [25e0a2ef](https://github.com/Niko1221/Strata/commit/25e0a2ef), 0e20d9ae, c08fd902 | overlap adattivo: segnale «copie arrivate» con una copia di 4 byte in memoria pinned al posto di un host callback; thread dei callback avviato prima del pinning dell'host | solo con `STRATA_ADAPT_OVERLAP=1` (noi spento) | no | piccolo |
| 661ff293 | `STRATA_ADAPT_OVERLAP` torna opt-in ovunque | nessuno (su Windows era già opt-in) | — | — |
| 62497bff, 0cf3d510 | sonda PLE lenta: solo avviso, resta direct; mmap con prefetch delle righe | è la nostra patch 13 (ple-direct): upstream ora fa lo stesso | **sì** (13) | la 13 si riduce alle diagnostiche |
| 38032f54, 3804b43f, 0613cc00 | watchdog: I/O lento e parcheggio di una conversazione su Windows non sono più stalli (#2049 #2065) | robustezza su Windows (paging) | no | medio, `generate.cpp` |
| c5fa1b58, c7838c52 | serve: slot BGEN rifiutato → altro slot; hook `before_load` | multi-chat: niente 400 permanenti | no | piccolo |
| 85f839d8 | hip gfx103x: side stream del drafter | non ci riguarda | — | — |

Nessun commit nuovo su decode a una chat, layer split, pipeline o speculative oltre a quelli sopra.

## 2. PR upstream per tema

### 2a. Multi-GPU, layer split, pipeline, expert-parallel, hand-off

| PR | cosa fa | stato | ce l'abbiamo | valore per noi | sforzo |
|---|---|---|---|---|---|
| [#1798](https://github.com/Niko1221/Strata/pull/1798) | `--expert-parallel-device N` (SYCL): la scheda 0 esegue tutti i layer; gli esperti di ogni layer sono divisi fra le due schede (i più caldi a coppie alternate) e calcolati insieme. Handshake per layer: id e input q8_1 nella inbox dell'altra scheda, le righe tornano dritte nei `parts_` della 0; flag con epoca, letture che scavalcano le cache | A | no | **strutturale**. 2x B70: +14,4/+13,1%; 2x B60: +15,3%. Esperti 11,8 → 8,2 ms a finestra, attesa per layer 26 µs. Limiti: tutti gli esperti in VRAM, niente swap adattivi, non compatibile con split e pipeline. Per noi: densi + testa sulla 2080 Ti, esperti divisi per banda (3060 ~37%) | alto (porto CUDA dell'idea, ~1 500 righe) |
| [#1120](https://github.com/Niko1221/Strata/pull/1120) | `STRATA_SPLIT_OVERLAP`: flag «pronto» per hand-off in memoria pinned mappata, attesa sulla GPU nel grafo dello stadio successivo, lanciato in anticipo da un thread | A | patch preparata il 6/10 (`corse_2080ti/20261006_due_schede/patch/pr1120.diff`), mai misurata | basso così com'è (si spegne con `--pipeline-windows`, su NVIDIA nel rumore); **utile come mattone** del ridisegno (hand-off senza sync host) | medio |
| [#1099](https://github.com/Niko1221/Strata/pull/1099) | hand-off via peer access/NVLink (0,137 → 0,018 ms a finestra) | A | no | nullo: niente P2P fra 3060 e 2080 Ti su GeForce. In byte l'hand-off è trascurabile anche da noi (51 KB × T) | — |
| [#1748](https://github.com/Niko1221/Strata/pull/1748) + [#1887](https://github.com/Niko1221/Strata/pull/1887) | remote stage su TCP: i layer finali su altri PC, arena per intervallo, relay a 3+ stadi | A | no | nullo per la velocità. **Dato chiave**: su Windows lo stadio che aspetta scende in P5 (memoria 810 MHz); bloccando i clock l'attesa passa da 12-22 a 3,7-4,1 ms | — (vedi §5, clock) |
| [#1461](https://github.com/Niko1221/Strata/pull/1461) | coppia peer elastica: con 2 richieste la seconda scheda diventa un motore suo e i due si calcolano a vicenda gli esperti («mutual help») | A | no | multi-chat: 2x 3090 NVLink, 2 richieste 155 t/s contro 99 in serie (+55%). Su schede asimmetriche senza NVLink non provato | alto |
| [#1438](https://github.com/Niko1221/Strata/pull/1438) | posizionamento peer per capacità in byte (`STRATA_PEER_CAPACITY_AWARE`) | A | no | solo `--peer-device`: non è la nostra strada | — |
| [#1441](https://github.com/Niko1221/Strata/pull/1441) | `--prefill-pipe R`: chunk di prompt dimensionati per la pipeline del layer split | A | no | TTFT: +62% su 4 stadi GP100. Su 2 stadi asimmetrici è da misurare: il nostro prefill è già a 75 s/131k | medio |
| [#761](https://github.com/Niko1221/Strata/pull/761) | lo stadio di prefill non aspetta che finisca tutto lo split sotto di lui | M (è nella base: `prefill.cpp` aspetta solo il successore diretto) | sì (base) | già dentro | — |
| [#1656](https://github.com/Niko1221/Strata/pull/1656) | `--pipeline-windows` su 3+ stadi | M (0.1.42, opt-in) | sì (base) | non ci serve con 2 schede | — |
| [#1122](https://github.com/Niko1221/Strata/pull/1122) / #905 | pipeline + `--adapt-async 1` insieme (4060 Ti + 5080: +18% sulla sola pipeline) | M (0.1.40.2) | nel codice sì; nella Daily **no** (richiede il modo RAM residente, non l'elastico) | medio: con hit al 97% il tier ha poco da spostare; la tabella in `MULTI_GPU.md` dà 136,7 → 142,0 su 2x 3090 | config, ma alternativo a `--elastic` |
| [#910](https://github.com/Niko1221/Strata/pull/910) | merge di attenzione limitato (bit per bit), lettura anticipata del PLE, catena MTP anticipata | chiusa dal force-push del 6/10, mai riproposta; upstream non ha il merge v2 | sì: merge v2 nella patch 10; `PL_EARLY_CHAIN` portato il 6/10, opt-in e spento nella Daily | esaurito | — |
| [#492](https://github.com/Niko1221/Strata/pull/492) | ruoli eterogenei: modello su una scheda, testa MTP sull'altra (`--draft-device`); `--draft-chain-batch` (bozza 4,63 → 4,14 ms) | chiusa (da rifare) | no | **strutturale**: spostare la catena MTP (6,5 ms di 2080 Ti a finestra) fuori dal percorso critico, per esempio sulla 3060 nelle finestre speculative | alto |
| [#1888](https://github.com/Niko1221/Strata/pull/1888) | attenzione QSA di decode spezzata per blocchi sul path int8 mma | A | no | +4,2% su 5080 (sm_89). Usa il path int8 mma del prompt, che su sm_75 ha un'altra forma; non bit per bit | medio, da provare solo sulla 3060 |

### 2b. Batch e multi-chat

| PR | cosa fa | stato | ce l'abbiamo | valore per noi | sforzo |
|---|---|---|---|---|---|
| [a0116b27](https://github.com/Niko1221/Strata/commit/a0116b27) / #2038 | gruppi in pipeline al posto di `--batch-mtp` sullo split | M (0.1.43.1) | no | **alto**: vedi §0 | config zero |
| [#1636](https://github.com/Niko1221/Strata/pull/1636) / [#1253](https://github.com/Niko1221/Strata/pull/1253) | `--batch-mtp` con layer split (finestre seriali, drafter per slot sull'ultima scheda) | M (0.1.42) / A | sì (base) | +15% a 2 stream contro le finestre seriali, ma perde contro i gruppi in pipeline da 4 stream in su | — |
| [#1524](https://github.com/Niko1221/Strata/pull/1524) | finestre speculative larghe (8/12/16 righe) condivise da 2-4 stream, esperti eseguiti insieme, bozze MTP per stream con pesi condivisi | A | no | **strutturale**: 5090, c=4: 1,31x (testo), 2,07x (codice). Solo singola NVIDIA; da combinare con la pipeline | alto |
| [#1010](https://github.com/Niko1221/Strata/pull/1010) | fino a 3 bozze MTP per slot nella finestra da 8 righe (2 stream: 71,6 → 84,3 sul codice) | chiusa dal force-push, mai riproposta | no | idea per il ridisegno: riempire la finestra in multi-chat | medio |
| [#2050](https://github.com/Niko1221/Strata/pull/2050) | `--batch-groups`: un prompt freddo non ferma più tutti gli stream (pausa max 12,2 → 4,2 s su 2x 5090) | A | no | multi-chat con prompt diversi (da noi 5-15 t/s: il prefill blocca il decode) | medio |
| [#2170](https://github.com/Niko1221/Strata/pull/2170) | race nel cedere il passo di un prompt lungo a una richiesta corta (TTFT −64% dove capitava) | A | no | multi-chat con agenti | piccolo |
| [#2109](https://github.com/Niko1221/Strata/pull/2109) | priorità delle richieste in `--batch` | A | no | utile se Claude Code e DSH convivono | piccolo |
| [#1614](https://github.com/Niko1221/Strata/pull/1614) | un solo pool KV per tutte le corsie (−3,1 GiB di RAM pinned a 2 corsie) | A | no | RAM, nessuna velocità | medio |

### 2c. Decodifica speculativa (MTP, catena, drafter, alberi)

| PR | cosa fa | stato | ce l'abbiamo | valore per noi | sforzo |
|---|---|---|---|---|---|
| [#1316](https://github.com/Niko1221/Strata/pull/1316) | rimisura le catene di lookup «stale» quando una catena più corta rende | A | no | piccolo, riguarda suffix/lookup e non l'MTP | piccolo |
| [#1426](https://github.com/Niko1221/Strata/pull/1426) / #1961 | drafter a blocchi DFlash | A | no | negativo: 73-76 t/s contro 83,6 dell'MTP | — |
| [#1281](https://github.com/Niko1221/Strata/pull/1281) | bozze accoppiate con Gumbel-max (+7 punti di accettazione a temperatura 1) | M (0.1.40.2, opt-in) | nel codice sì | solo per richieste campionate; in `MULTI_GPU.md` la velocità non si muove, e con la pipeline le bozze accoppiate **serializzano** | — |
| [#1779](https://github.com/Niko1221/Strata/pull/1779) | barriere del tier adattivo sui soli token accettati | A | no | determinismo, non velocità | — |
| [#2105](https://github.com/Niko1221/Strata/pull/2105) | MTP con esperti nativi Q4_0/Q8_0 | A | no | qualità e accettazione del drafter: il nostro esperimento MTP è chiuso | — |
| [#492](https://github.com/Niko1221/Strata/pull/492) `--draft-chain-batch` | i grafi dei passi della catena lanciati uno dopo l'altro con una sola attesa per giro (−11% di bozza) | chiusa | no; chain-fuse ritirata (kernel fusi, +0,4%) | piccolo/medio: da noi la catena è 7 passi e 6,5 ms; la fusione dei kernel non ha reso, il costo è di lancio e attesa | medio |

Nessuna PR propone alberi di bozze: tutte restano a catena singola o a più slot.

### 2d. Esperti su CPU, pinning, residenza

| PR | cosa fa | stato | ce l'abbiamo | valore per noi | sforzo |
|---|---|---|---|---|---|
| [#1905](https://github.com/Niko1221/Strata/pull/1905) | `STRATA_PIN_BY_NEED=1`: su Windows registra gli esperti non residenti in VRAM per rango del profilo (fino a `STRATA_ARENA_PIN_GIB`) invece del prefisso dell'arena; `STRATA_PCIE_MIN1` | A | no. **Il nostro log dice 7 GiB pinned su 29,6** | prompt +5-7% (3090, Windows); decode x1,02-1,03 con `--adapt-async`. Da noi rende pinned anche le copie di riempimento della cache elastica | medio (loader + `pinned.cu`); prima l'A/B di `STRATA_ARENA_PIN_GIB` |
| [#1237](https://github.com/Niko1221/Strata/pull/1237) | buffer di stage pinned (`STRATA_STAGE_PIN=1`) | M (0.1.41, opt-in) | nel codice sì | conta solo con `--mmap-experts` o con l'arena troppo piccola; con IQ3_S aveva corrotto le risposte. Non per noi | — |
| [#1989](https://github.com/Niko1221/Strata/pull/1989) | `STRATA_HC_HOST=1`: le hyper-connection down/up (BF16) in RAM pinned, VRAM agli esperti (+29% di slot) | A | no | negativo per noi: l'HC è il 23% dei densi letti a ogni finestra; via PCIe x4 sulla 3060 costerebbe molto | — |
| [#1838](https://github.com/Niko1221/Strata/pull/1838) | `STRATA_RAM_ADAPT`: la copia in RAM segue la conversazione (+16,5% con RAM scarsa) | A | no | nullo: abbiamo 96 GB e l'arena intera | — |
| [#1904](https://github.com/Niko1221/Strata/pull/1904) | `--adapt-async 1` nel modo arena (una GPU) | A | no | solo una scheda | — |
| [#2176](https://github.com/Niko1221/Strata/pull/2176) | `STRATA_ROUTE_PRIOR_MAP` per layer | A | no | cambia l'output (KL): non bit per bit | — |
| [#1166](https://github.com/Niko1221/Strata/pull/1166) / [#1912](https://github.com/Niko1221/Strata/pull/1912) | `--host-core sibling`, `--pool-affinity measure` | A | `--host-core last` sì | nullo: Ryzen 7 5800X non è ibrido | — |
| [#1598](https://github.com/Niko1221/Strata/pull/1598) | `--aux-cpus` (+1,7…10% di decode sullo split) | M (0.1.42) | nel codice sì | **solo Linux** | — |
| [#1416](https://github.com/Niko1221/Strata/pull/1416) | quota CPU del prefill quantizzata su GPU | A | no | −2…−4% di tempo di prompt (3060 + 5070 Ti) | piccolo |

### 2e. Prefill e TTFT

| PR | cosa fa | stato | ce l'abbiamo | valore per noi | sforzo |
|---|---|---|---|---|---|
| `STRATA_PREFILL_HELP=1` (base) | per i prompt da un chunk (< ~3,3K) la scheda ferma calcola una quota degli esperti in streaming | M | nel codice sì, nella Daily **no** | **TTFT dei turni agentici** (prefisso in cache e coda corta): +18% (#2032, 2x 2080 Ti), +46…14% (2x 3090). Ripetibile ma non bit per bit | config zero |
| `STRATA_SPLIT_MTP_BATCH=1` (base) | K/V del draft in batch sullo split | M | nel codice sì, nella Daily no | prompt +3…8% (#2163, #1640); decode −3%…+8% secondo la combinazione | config zero |
| [#2145](https://github.com/Niko1221/Strata/pull/2145) | esperti di prompt int8 fusi su sm_75 | A | no | 2080 Ti: 98K da 58,3 a 53,3 s (+9,4%); cambia il PPL | medio |
| [#2092](https://github.com/Niko1221/Strata/pull/2092) + [#2146](https://github.com/Niko1221/Strata/pull/2146) | attenzione di prompt int8 v2 su Turing (registri invece di `cp.async`), poi in un solo stadio | A | no | +5,2% del prompt a 98K; attenzione 1,66x | medio |
| [#1821](https://github.com/Niko1221/Strata/pull/1821) | attenzione di prompt v1 int8 su Turing con prefetch in registri | A | no | kernel −40% (alternativa a #2092) | piccolo |
| [#1825](https://github.com/Niko1221/Strata/pull/1825) / [#2071](https://github.com/Niko1221/Strata/pull/2071) | punteggi di blocco QSA sotto sm_80: un thread per testa (4,6-5,2x) / SIMT=2 | A | SIMT=1 sì (patch 14, PR #2080) | sopra la nostra 14 conta solo il guadagno di SIMT=2 su SIMT=1: kernel a 131K 1,21 → 0,95 ms per chiamata (il +16,6% a 98K della PR è contro il kernel warp, cioè SIMT=0). Lo scorer cambia l'ordine delle somme: argmax diverso su ~1% delle posizioni non in parità | piccolo |
| [#2091](https://github.com/Niko1221/Strata/pull/2091) | `xn16` scritto già in FP16 per le GEMM tensor-core (+3%) | A | l'hc16 della patch 14 copre la stessa zona | da confrontare con hc16 | piccolo |
| [#2016](https://github.com/Niko1221/Strata/pull/2016) | top-k radix del prompt con una scan cooperativa (stessi id) | A | no | 3060: top-k −15…−54% a 4K-64K; a 128K invariato | piccolo |
| [#1742](https://github.com/Niko1221/Strata/pull/1742) / [#1744](https://github.com/Niko1221/Strata/pull/1744) | build sm_86 specializzate per il prefill fuso | A | no | +0,2…0,8%: rumore | — |
| [#1822](https://github.com/Niko1221/Strata/pull/1822) | MMQ gate/up che legge gli esperti in place | A | no | −0,7% | — |

### 2f. Decode Turing sm_75 (la 2080 Ti è lo stadio 1)

| PR | cosa fa | stato | ce l'abbiamo | valore per noi | sforzo |
|---|---|---|---|---|---|
| [#2069](https://github.com/Niko1221/Strata/pull/2069) parte 2 | layout degli esperti «mode 4» su sm_75, bit per bit col mode 0: gate/up −9…−14%, down −16…−22% a 1-2 voci per esperto; il down resta a mode 0 da 4 token | A | no. `STRATA_EXP_MODE` esiste già nella 0.1.43 | **medio**: tocca il down (la EXPDEC non lo copre) e il drafter. Misurato solo su righe Q2_0; i nostri down dei layer 28-47 sono IQ4_NL, e su IQ4_NL il layout interleaved di #2089 perdeva il 31% a 4 token. Senza codice: `STRATA_EXP_MODE=4`, che però vale anche per il down a T=4, dove perde il 21% | zero (env) / piccolo (port del default per T) |
| [#2069](https://github.com/Niko1221/Strata/pull/2069) parte 1 | tabella `kIlRows_75` per le matvec interleaved (+6,5% insieme alla parte 2, su Q2_0 e senza B6) | A | sovrapposta: B6 + `MMVQ_IL=0`; la #1437 dava 0,0% contro B6 | basso | — |
| [#2070](https://github.com/Niko1221/Strata/pull/2070) | hyper-connection: up per 3+ token (righe di `w_up` caricate a lotti di 4) e down a coppie di token, bit per bit | A | no | basso-medio: +0,6% (4K), +2,3% (32K) sulla 2080 Ti. L'HC è il 19% del GPU di decode sulla 2080 Ti | piccolo |
| [#2072](https://github.com/Niko1221/Strata/pull/2072) | selezione QSA di decode: scorer a dimezzamento + top-k diviso, bit per bit | A | lo scorer coincide con QSA_ROWS (patch 16, PR #2059); il top-k diviso no | scorer a 131K e T=4: 113,6 → 67,1 µs (la nostra 16: 101 → 55). Utile il top-k diviso, a contesti lunghi | piccolo |
| [#1653](https://github.com/Niko1221/Strata/pull/1653) | B6 IQ4_XS a 3 warp su sm_75 (sopra la nostra #1418) | A, WIP | variante della 04 | +3,5% con IC95 ±29%: non dimostrato | piccolo |
| [#1654](https://github.com/Niko1221/Strata/pull/1654) | attenzione QSA in MMA FP16 su sm_75 | A, WIP | no | −2,6…−2,9%: negativo | — |

### 2g. Windows / WDDM

| PR / fonte | cosa | valore per noi | sforzo |
|---|---|---|---|
| [#1748](https://github.com/Niko1221/Strata/pull/1748), nota misurata | Windows (e WSL2) abbassa i clock della GPU che aspetta: P5, memoria a 810 MHz; `nvidia-smi -lgc 1500,1905 -lmc 7001,7001` → P2 fisso, attesa 12-22 → 3,7-4,1 ms | **da misurare subito**: stato P e clock memoria di 3060 e 2080 Ti durante il decode (lettura `nvidia-smi --query-gpu=pstate,clocks.mem -lms 100`), poi un B-A-B con clock bloccati. Sulla Turing GeForce `-lmc` potrebbe non essere supportato | zero codice; azione admin dell'owner |
| [#1905](https://github.com/Niko1221/Strata/pull/1905) | registrazione dell'arena su Windows (vedi 2d) | medio | medio |
| [#2185](https://github.com/Niko1221/Strata/pull/2185) | script per dare `SeLockMemoryPrivilege` (large pages) | il nostro log: «large pages refused … error 1314». Beneficio non misurato (TLB su 30 GiB di arena) | zero codice, impostazione di sicurezza: la decide l'owner |
| [#1130](https://github.com/Niko1221/Strata/pull/1130) | limiti di commit dopo un'allocazione fallita | robustezza | — |
| doc `MULTI_GPU.md` | `penalty_last_n` > 0 o bozze accoppiate → la pipeline decodifica **in serie** | verificare che gateway, Claude Code e DSH non mandino penalità di ripetizione | zero |

## 3. Benchmark della community (2+ schede, sintesi del sub-agente su 63 PR lette)

| PR | schede, link | OS | quant / ctx | versione | opzioni chiave | decode |
|---|---|---|---|---|---|---|
| [#1509](https://github.com/Niko1221/Strata/pull/1509) | 2x 2080 Ti 22G, Gen3 x16, 250 W | Linux | IQ3_XXS / 131k | 0.1.40.2 | auto K=26 | 84,1 (4K) / 75,1 (32K) |
| [#2032](https://github.com/Niko1221/Strata/pull/2032) | 2x 2080 Ti 22G | Linux | IQ3_S / 262k | 0.1.43 | split 24, `PREFILL_HELP=1`, `--pcie-frac 0.17`, `--spec-min-p 0.70` | chat 78,9 |
| [#2000](https://github.com/Niko1221/Strata/pull/2000) | 3060 x4 Gen3 (stadio 0) + 4060 Ti | **Windows** | IQ3_XXS / 100k | 0.1.43 | split 21 a mano, pw2, trim | 46,8 chat / 56,8 agent |
| [#2083](https://github.com/Niko1221/Strata/pull/2083) | 5060 Ti x8 Gen5 + 3060 x4 Gen3 **ultima con 8 layer** | Linux | IQ3_S / 512k | 0.1.43 | split 40, `--pcie-frac 0`, trim | 74,4 chat / 80,7 agent |
| [#2163](https://github.com/Niko1221/Strata/pull/2163) | 2x 3080 Ti, la seconda x4 | Linux | Q4_K_M / 196k | 0.1.43 | trim + split 27 a mano, `SPLIT_MTP_BATCH=1`, `TAIL_SKIP=5` | 104,5 |
| [#2012](https://github.com/Niko1221/Strata/pull/2012) | 5090 + 3090 | Windows | IQ3_S / 131k | 0.1.43 | default | 79,1 chat / 115,8 agent |
| [#1508](https://github.com/Niko1221/Strata/pull/1508) | 2x V100 PCIe | Linux | UD-IQ4_XS / 131k | 0.1.40.2 | `--batch 8 --batch-groups 2 --trim` | 77,3 singola, **117,7 a 8 client (+78%)** |
| [#1834](https://github.com/Niko1221/Strata/pull/1834) | 2x PRO 4500 | Linux | IQ3_XXS / 262k | 0.1.41 | `--batch 8`, groups auto contro 1 | 115/152/208/256 contro 109/126/159/175 (1/2/4/8 client) |
| [#2142](https://github.com/Niko1221/Strata/pull/2142) | 2x V100 + PRO 4000 | Windows | IQ2_XS / 262k | 0.1.40 | 3 stadi; vision su un'altra scheda | 85,8 → 94,6 a 4K con la vision spostata |
| [#1921](https://github.com/Niko1221/Strata/pull/1921) | 5070 Ti + 2x 5060 Ti | Linux | UD-IQ4_XS | 0.1.42 | pw2 | pw2 +3,4…6%; seriale con `penalty_last_n` > 0 |

Lezioni utili per noi:
- la scheda lenta su x4 con pochi layer rende meglio (#2083: con 3 layer −25% di prefill, con 42 pari). La
  proporzione per banda (360:616) darebbe 17-18 layer alla 3060, ma il monitor 8K spinge verso meno. Uno sweep di
  `--layer-split` 13/14/16/18 non è mai stato fatto sulla 0.1.43 con la pila;
- `--pcie-frac 0` sui link x4 (#2083, #2076): da noi `auto` era già ottimo il 5/10;
- `--prefill auto:32768` costa −32% sullo split (#1508): non usarlo;
- normalizzando per banda (nostro calcolo, non delle PR) siamo a ~0,155 t/s per GB/s contro 0,137 di #1509. Solo
  #2083 (IQ3_S, contesto corto, DDR5) fa meglio per GB/s.

## 4. Fork

Criterio del sub-agente: 2 158 fork restituiti dall'API su 2 217. Di questi, 641 hanno avuto un push negli ultimi 12
giorni, almeno 10 minuti dopo la creazione. 515 hanno branch con commit propri dopo l'1/10 (1 869 branch), filtrati per
parola chiave. Ho confrontato con upstream ~100 branch di ~60 fork, incrociandoli con le 1 310 PR; il nostro fork è
escluso. I numeri sono quelli dichiarati dagli autori. Ho verificato a mano il diff del primo della tabella.

| fork / branch | ultimo push | cosa fa | numeri dichiarati | upstream | per noi | sforzo |
|---|---|---|---|---|---|---|
| [NTRYourWaifu/two-pc-042](https://github.com/NTRYourWaifu/Strata/tree/two-pc-042) v7/v8 (909b4eed, 3cf0e5cc) | 12/10 | i polling della pipeline (flush WDDM ogni 2 ms in `Verifier::service`, `done()`, `MtpDrafter::chain_outputs_ready/chain_poll`) interrogano evento e stream **senza `cudaSetDevice`** (`STRATA_FLUSH_NO_SWITCH`, ripiega sul cambio di scheda se la query è rifiutata) | v7: 88,2 → 90,6 t/s (due PC). Nasce da uno stallo: host bloccato in `cudaSetDevice` | F (upstream #1741 copre solo il ramo veloce di `service`) | **alto**: Windows, `--pipeline-windows 2`, è la stessa firma delle nostre ~2 ms di attesa host per stadio. Da noi `verify.cpp:3480` ha lo stesso flush a 2 ms | basso (+52 righe in `verify.cpp`, più `mtp.cpp`) |
| stesso fork, `keep_warm.cu` (v4) | 11/10 | kernel che tiene sveglia la GPU poco carica e le impedisce di scendere in P5 | 1660S: da 6,8 a 1,4 ms per layer | F | **alto se** la lettura dei P-state conferma il calo: è l'alternativa software (niente admin) a `nvidia-smi -lgc/-lmc` | basso |
| [unimatrix099/pr/amd-ffn-fusion](https://github.com/unimatrix099/Strata/tree/pr/amd-ffn-fusion), [main](https://github.com/unimatrix099/Strata/tree/main) | 12/10 | `post()` in 2 lanci persistenti, fronte FFN fuso (da 23 a 11 kernel per metà FFN), commit asincrono sullo split, lancio anticipato dello stadio 1 | +3,5% e +2,7%; due schede in pipeline +9%; commit asincrono +3,4%; lancio anticipato +29% senza pipeline, **~0 con la pipeline** (come il nostro prelaunch) | F, solo HIP | medio-alto: meno nodi del grafo da 1 397 (i nostri buchi fra i nodi valgono 1,3-1,8 ms a finestra) | medio-alto (porto CUDA) |
| [ScrambledEggsOnToast/spec208](https://github.com/ScrambledEggsOnToast/Strata/tree/spec208) | 12/10 | `--batch-mtp-pipeline --batch-groups 2`: bozze MTP **dentro i gruppi in pipeline** sullo split, a ondate rotanti di 2 slot (2-8 slot) | nessuno | F | **alto per il multi-chat** (è l'idea 5 del §5) | alto: fork 957 commit avanti |
| [eddoursul/custom](https://github.com/eddoursul/Strata/tree/custom) (40★) + [jesdga95/basalt](https://github.com/jesdga95/basalt) (motore a parte) | 12/10 | draft layer auto-distillato; K/V del PLE del layer 1 su un ramo del grafo; in basalt la testa del draft valutata su una copia a 2 bit, con ri-valutazione esatta delle righe migliori, e tutti i grafi di bozza catturati all'avvio | draft distillato +5,6% (ragionamento); PLE +4,1% (codice) | F | medio: il nostro MTP distillato non ha reso a 131k (+0,7%); la **testa a 2 bit** accorcia invece la catena (testa 48k Q5_K = 68 MB a passo). Il K/V PLE va confrontato col nostro DF_PLE | medio |
| [noon-at-cgn/opt/01-aux-io-threads](https://github.com/noon-at-cgn/Strata/tree/opt/01-aux-io-threads) | 6-8/10 | `STRATA_SPLIT_COMMIT_ASYNC`, `STRATA_BATCH_PLE_LATE`, `--batch-overlap` (commit di tutti gli stadi, poi una sola sync) | — | F (pool KV = #1614) | medio (multi-chat, commit asincrono) | medio (storia vecchia) |
| [sensssz/mtp-lend](https://github.com/sensssz/Strata/tree/mtp-lend) | 12/10 | `--mtp-lend`: i 675 MiB di esperti del draft layer prestati al prefill | nessun TTFT dichiarato | F | medio (TTFT sulla 2080 Ti) | basso-medio |
| [fushengss/main](https://github.com/fushengss/Strata/tree/main) | 11/10 | `--split-chunks N`: prompt a chunk da 2-4K in pipeline fra gli stadi | nessuno | F | medio (come #1441) | basso-medio |
| [dragomir-lekovic/feat/conversation-vram-slots](https://github.com/dragomir-lekovic/Strata/tree/feat/conversation-vram-slots) | 12/10 | due conversazioni residenti (stato in VRAM, K/V in RAM bloccata): cambiare chat non rilegge | evita ~40 s a 120k | F | medio (Claude Code + DSH alternati); non provato su split | medio |
| [SanghunYun/decode-timing](https://github.com/SanghunYun/Strata/tree/decode-timing) | 10/10 | `STRATA_DECODE_TIMING` conta anche gli swap in sospeso e il join adattivo | 0.1.42: 11,9 ms a finestra non conteggiati | #1864 A | medio (diagnosi) | basso |
| [unimatrix099/bonus-branch](https://github.com/unimatrix099/Strata/tree/bonus-branch) | 7/10 | seconda bozza per il token bonus | giusta nel 31% dei casi, **nessun guadagno** | F | esito negativo, utile per scartare l'idea | — |
| KarlGrier (#1888), SuperDistance (#2050), xrip (#2089), j-luwierski (DFlash), lask3802, eelgaev `EP_TWINS` (expert parallel su NVLink), missdeer (multi-host) | 9-12/10 | già nel §2, oppure richiedono NVLink o più PC | — | — | basso | — |

## 5. Classifica

### Da portare subito (costo basso)

| # | leva | tipo | atteso | come si misura |
|---|---|---|---|---|
| 1 | multi-chat: `--batch N --batch-groups auto` senza `--batch-mtp` (a0116b27 / #2038) | config, poi port del default 0.1.43.1 (+29/−11) | aggregato a 4 chat da ~45 a 60-70 t/s (+37% a 4 richieste su 2x A4000; +46…78% in #1834/#1508) | `multi_chat_mc.py` a 2/4/6 chat, B-A-B contro `--batch-mtp` |
| 2 | clock bloccati durante il decode (#1748), o `keep_warm.cu` del fork NTRYourWaifu | azione admin dell'owner, zero codice / port piccolo | sconosciuto; potenzialmente il più grande se la 3060 scende in P5 fra le finestre | prima la lettura di `pstate` e `clocks.mem` ogni 100 ms durante il banco; poi B-A-B |
| 2b | polling della pipeline senza `cudaSetDevice` (NTRYourWaifu v7/v8, `STRATA_FLUSH_NO_SWITCH`) | port piccolo (+52 righe in `verify.cpp`, più `mtp.cpp`) | +1-3% (dichiarato +2,7%); meno attesa host per stadio | `strata decode timing` (attese host), B-A-B |
| 3 | `STRATA_ARENA_PIN_GIB=16/24`, poi port di #1905 `STRATA_PIN_BY_NEED` | env, poi medio | riempimenti della cache e scambi elastici non più pageable; TTFT +5-7% | `strata decode timing`, prompt 131k, attenzione ai rifiuti di allocazione WDDM |
| 4 | `STRATA_PREFILL_HELP=1` | env | TTFT dei turni corti (+14…46% sotto ~3K token nuovi) | TTFT B-A-B su un turno agentico con il prefisso in cache |
| 5 | `STRATA_EXP_MODE=4` sulla 2080 Ti, poi il default per T di #2069 (mode 4 solo fino a 3 token per il down) | env, poi piccolo | +1-3% (down e drafter; la EXPDEC copre già gate/up) | bench forzato 131k; parità con `expdec_bench`, che elenca `STRATA_EXP_MODE` fra le variabili che interferiscono |
| 6 | #2070 (HC up/down sm_75) | port piccolo, bit per bit | +0,6…2,3% | B-A-B |
| 7 | #2072, solo il top-k diviso | port piccolo | piccolo a 131k, di più oltre 256k | `qsa_rows_bench` |
| 8 | prefill sm_75: #2092 o #1821, #2145, #1825/#2071 SIMT=2, #2016 (3060) | port piccoli o medi | prefill 131k −10…−20% sommati (75 → ~62-65 s) | prefill 131k, parità |
| 9 | `STRATA_SPLIT_MTP_BATCH=1` | env | prompt +3…8% | prefill 131k e decode |
| 10 | controllo delle penalità di ripetizione nelle richieste | lettura del gateway | evita una pipeline seriale silenziosa | log `strata pipeline classes` |
| 11 | af6affb8 + 7bab660b + watchdog 0.1.43.1 | port di robustezza | niente velocità; meno crash e stalli | — |

### Da passare al ridisegno della pipeline (`lab/pipeline2`)

| # | idea | fonte | perché per noi | rischio |
|---|---|---|---|---|
| 1 | **expert-parallel per layer**: densi, testa e MTP sulla 2080 Ti, esperti di ogni layer divisi fra le schede in proporzione alla banda (i più caldi a coppie alternate); handshake per layer con inbox q8_1 e righe di ritorno in memoria mappata, flag a epoca nel grafo | #1798 (SYCL, +13-15%); #1251 (somme pesate per token in FP16 invece delle righe: 10x meno byte) | elimina la serie stadio 0 → stadio 1. Le due schede lavorano insieme su ogni layer. Il costo è il round trip per layer (×48) sull'Oculink x4: da misurare per primo con un microbench | la 3060 regge pochi esperti; senza P2P ogni handshake passa dalla RAM mappata. Nessuno swap a metà richiesta |
| 2 | **ibrido**: layer split per i densi + expert-parallel solo nei layer dello stadio 1 (la 3060, finito lo stadio 0, calcola una quota degli esperti dei layer 16-47) | #1798 + #1461 (mutual help) | riempie il 76% di tempo in cui la 3060 aspetta senza cambiare il percorso dei densi | sincronizzazione per layer a ogni finestra |
| 3 | **catena MTP su un'altra scheda** o in un grafo unico con una sola attesa per giro | #492 (`--draft-device`, `--draft-chain-batch`: −11% di bozza) | la catena (6,5 ms di 2080 Ti a finestra) sta sul percorso critico delle finestre fresche; la 3060 potrebbe redigere mentre la 2080 Ti verifica | la testa (437 MB Q5_K) e la vocabolario-draft vanno duplicate |
| 4 | **hand-off senza sync host**: flag «pronto» scritto dal grafo che produce e atteso sulla GPU da quello che consuma; lancio anticipato dello stadio successivo | #1120 (patch già pronta del 6/10) | toglie le ~2 ms per stadio di attesa dei flag host e il lancio del grafo di 1 397 nodi dal percorso critico | timeout TDR su WDDM: tenere il limite `STRATA_SPLIT_WAIT_MS` |
| 5 | **multi-chat: gruppi in pipeline con le bozze MTP per slot** (oggi upstream deve scegliere fra le due) e finestre larghe condivise (8-16 righe, esperti eseguiti una volta per gruppo) | #1524 (1,3-2,1x a c=4), #1010 (3 bozze per slot), a0116b27; fork ScrambledEggsOnToast `spec208` (`--batch-mtp-pipeline`, già scritto, senza numeri) | il multi-chat è il punto debole (45 t/s); con la pipeline ogni scheda serve un gruppo diverso | VRAM per slot (~0,56 GiB di cache a slot sulla 3060) |
| 6 | **prefill pipelinato a chunk dimensionati** e prompt freddi che non fermano gli altri stream | #1441 (`--prefill-pipe`), #2050, #2170 | multi-chat con prompt diversi: oggi 5-15 t/s, perché il prefill blocca il decode | — |
| 7 | **meno nodi per layer**: `post()` in lanci persistenti, fronte FFN fuso (da 23 a 11 kernel per metà FFN), commit asincrono sullo split | fork unimatrix099 (HIP: +9% su due schede in pipeline), noon-at-cgn `STRATA_SPLIT_COMMIT_ASYNC` | i buchi fra i 1 397 nodi (1,3-1,8 ms) e il lancio del grafo stanno sul percorso critico | porto CUDA di kernel HIP |
| 8 | **testa del draft a 2 bit con ri-valutazione esatta** e grafi di bozza catturati all'avvio | basalt / eddoursul | la catena MTP rilegge la testa 48k Q5_K (68 MB) a ogni passo | qualità delle bozze da misurare |
| 9 | **bilanciamento dei layer per banda** (sweep 13-18) prima di ogni ridisegno | #2083, #2048 | il punto di partenza giusto per misurare il guadagno del ridisegno | — |

Stato: ricognizione in sola lettura; **compilato no, installato no, provato no** per ogni leva elencata.
