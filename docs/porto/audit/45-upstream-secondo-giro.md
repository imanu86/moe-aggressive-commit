# 45 — Upstream, secondo giro: i 390 riletti dopo la fusione HC

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `24fd5c2ee`.
**Niente compilato, nessun server toccato.** Strumenti: diff d'albero
`git diff 5c3a58686 upstream/master` (i due oggetti sono in locale), gli oggetti
upstream già scaricati (`33a75f41c`, `596a5795b`, ecc.), l'enumerazione completa dei
390 e i corpi PR del primo giro (scratchpad: `upstream_commits.txt`,
`upstream_by_file.txt`, `pr_details.txt`), e il NOSTRO albero letto riga per riga.
Marcatura: [MISURATO] = codice/diff letti o numeri di casa; [DEDOTTO] = aritmetica;
[IPOTESI] = da falsificare col cancello indicato.

Cosa è cambiato dal primo giro (`UPSTREAM_390.md`, 9/8 notte) e va tenuto a mente
leggendo: **#25585 è portata e vale +16,5%** (grafo 34.329 → 10.507 nodi);
**#26385 è portata** (i `__syncthreads()` sono in `common.cuh:631,642`); il
**rollback parziale della coda KV è costruito in casa** (commit `6e0da6d31`,
SOTA 13,21, "i 79 forward rigiocati vanno a zero") con il cronometro del
checkpoint già installato (`f8df4de8a`); la FA sul bersaglio è in uso e oggi
abbiamo scoperto che `flash_attn_mask_to_KV_max` pota solo la frontiera.

---

## 0. Prima la risposta alla domanda grossa

**"Se ne trovi uno che vale come #25585, dillo forte."**

Sul decode a contesto corto: **non c'è**. Il margine da massa-lanci rimasto nei 390
è ~600-700 nodi (lotto indexer+router, §2.1) e con la calibrazione di casa
(+16,5% per 24.000 nodi ≈ 0,0069%/nodo) vale **+0,4-0,6%**. Chi cerca un altro
+16,5% al decode corto nei 390 non lo troverà: l'abbiamo già incassato.

Sul **contesto lungo** invece un candidato di quella classe c'è, ed è lo stesso
lotto: **l'op fusa `GGML_OP_LIGHTNING_INDEXER` (#24231 + #25545)**. Non per i nodi:
per le **intermedie**. La nostra catena indexer materializza `relu(kq)` in
`[n_kv_comp × 64 teste × n_tok]` f32; a 105k di contesto e ub 512 sono
**3,4 GiB per strato** — non stanno in VRAM, ed è l'aritmetica che spiega perché a
100k siamo obbligati a `ub 16` [DEDOTTO, §2.1c]. L'op fusa non materializza
niente: scrive solo `[n_kv, n_batch]`. Se la deduzione regge, il porto riapre
`ub 64-512` a contesto lungo — ed è il fronte "prefill 82 minuti / bersaglio
10-100×" deciso dall'utente, non un punto percentuale. Al decode a 105k vale da
sola ~3-5 ms/posizione di banda [DEDOTTO]. **Questo è il pezzo forte del secondo
giro.**

E una cosa che il mandato deve sapere: **i due fronti più cari citati nel mandato
stesso non hanno una soluzione upstream da portare.** I buchi interni della
maschera top-512 non li salta NESSUNO upstream (verificato su DSV4, GLM-DSA e
MiniMax-M3: tutti a maschera, `fattn-common.cuh` mai toccata dal fork in poi —
§5). Il costo del checkpoint speculativo upstream lo elimina con un salto di
design (piani di rollback `n_rs_seq` dentro #25784) che non è pickabile, e che
noi abbiamo già replicato a modo nostro per la parte replay; resta da copiare
l'ultima idea: smettere di salvare il checkpoint a ogni episodio (§4).

---

## 1. Dove il primo giro aveva sbagliato (correzioni a verbale)

1. **#25370 — il verdetto "zavorra viva" era sbagliato due volte su tre.**
   [MISURATO nel codice upstream pre-fix e nel nostro]
   - `dsv4_repeat_streams` esce subito se `t->ne[3] == n_stream`: con
     `n_stream=1` è **sempre** un ritorno secco, zero nodi emessi. Non era
     zavorra nel pavimento.
   - i bias `kq_b` a zero nascono SOLO se `kv_unified && flash_attn &&
     kq_mask->ne[3] != 1`: da noi mai. Inerti anche loro.
   - MA la terza parte è **viva adesso che la FA sul bersaglio è accesa**: noi
     costruiamo le maschere f32 e le castiamo a f16 **per strato, ogni forward**
     (`deepseek4.cpp:763-768` CSA, `:831-836` HCA, più la nascita f32 degli
     zeri del top-k a `:697`). Sono ~80 nodi e, al prefill lungo, ~1,7 GiB di
     traffico cast per ubatch a ub 512 su 105k ≈ **~1 s sull'intero prefill**
     [DEDOTTO]. #25370 le fa nascere f16 (`llama-graph`: `type =
     cparams.flash_attn ? F16 : F32`). Quindi: la riga non si cancella, si
     riscrive — "2/3 inerte, 1/3 viva con FA, e la parte viva sta nel lotto §2.1".
2. **#25784 liquidata in blocco come "linea parallela, mai da pickare".** Vero
   per lo stack speculativo (resta vero), ma DENTRO c'è il **sottosistema di
   rollback dello stato compresso** (piani `n_rs_seq`, `seq_rm` che accetta code
   ≤ n_rs_seq segnando `rs_idx[seq]`, restore/snapshot in-grafo via
   `state_restore/snapshot_src_idxs`): è la stessa classe della nostra leva
   `seq_rm_tail` + anello margine, e in più upstream la usa per **non salvare
   il checkpoint per episodio**. È il "secondo passo" che l'audit 37 aveva già
   nominato senza sapere che upstream l'aveva implementato (§4). Da leggere,
   non da pickare.
3. **#25832 schedata solo come "compagno di #25585, cautela lane".** La PR ha
   TRE parti e la prima è la cura di un difetto nostro noto: la logica di
   offload prova a piazzare `FLASH_ATTN_EXT` sul backend del peso **quando ci
   sono le sinks** (l'unico src "weight" della FA) — ed è il "dettaglio di
   piazzamento" per cui **la FA è spenta sulla bozza**. Quella parte
   (`ggml-backend.cpp`, condizione di offload) è separabile e NON tocca la lane
   CPU K; la cautela del primo giro vale solo per la parte `l_last`-forcing.
   Pick spezzato in due (§3).
4. **Due zone cieche di metodo**: il primo giro non ha aperto
   `fattn-common.cuh` (famiglia 4: verificato ora — upstream NON l'ha toccata,
   la potatura resta solo-frontiera, `fattn-common.cuh:666-718` identica) e non
   ha guardato DENTRO le PR "da non prendere" (#25784, sopra). La copertura dei
   390 in sé era onesta (tabella da 15 + risposte per fronte): il difetto era
   nei verdetti, non nel censimento. Lo dico perché il mandato dice "ne ha
   guardati pochi": non è quello il problema da correggere, è il rigore sul
   codice.

**E la domanda del mandato che correggo** (permesso accordato): "quali dei 390
portare" è la domanda piccola. Dopo questo giro la domanda giusta è: "quali dei
390 ci cambiano i PIANI". Risposta: #24231/#25545 cambiano il piano del
contesto lungo (§0), #25784 cambia il piano del checkpoint (§4), e la famiglia 4
conferma che sulla maschera sparsa siamo davanti a tutti — lì non c'è niente da
portare, c'è (eventualmente) da contribuire.

---

## 2. TABELLA — ordinata per valore atteso NOSTRO

Numeri di riferimento: decode 13,23 t/s (75,6 ms/token; ciclo 140,6 ms,
mean_len 1,86, p1 0,865), grafo 10.507 nodi (30% stato compressori ≈ 3.200;
indexer 31 nodi × 21 strati CSA), prefill 72,9 t/s @ ub 512 (81-90% trasporto
esperti), a 100k obbligo di ub 16. Calibrazione nodi→t/s: 0,0069%/nodo
(misurata dal porto HC). Costo porto: PULITO / ADIACENZA / MANUALE come nel
primo giro.

| # | Pezzo | Cosa fa | Contro cosa nostro | Stima | Costo porto | Cancello |
|---|---|---|---|---|---|---|
| 1 | **LOTTO INDEXER**: #24231 (op `GGML_OP_LIGHTNING_INDEXER`) + #25545 (kernel CUDA 588 righe, vettoriale+wmma) + resto di #25370 (maschere f16 alla nascita) + #25702 (get_rows unificata nello stato overlap) + #25896 (sqrt_softplus in topk-moe) | catena scoring indexer 9 nodi→1 con maschera fusa dentro; niente intermedie `[n_kv×64×n_tok]`; router fuso su 41 strati; −3 split al prefill | nodi (~650-700 di 10.507), banda decode a contesto lungo, **tetto di ub a 100k**, prefill (split 5→2 a bs=64) | +0,4-0,6% decode corto [DEDOTTO]; **+3-5 ms/pos decode @105k** [DEDOTTO]; **riapre ub>16 @100k** [IPOTESI, la più pagante] | MEDIO: stessa meccanica del porto HC (enum ggml.h/c ×1 op, file CUDA nuovi puliti, glue in `deepseek4.cpp` su una catena identica alla nostra riga per riga `:589-679`, probe in llama-context come per HC; `topk-moe.cu` mai toccato da noi) | (a) conteggio nodi dal log: atteso −600÷700; (b) `test-backend-ops -o LIGHTNING_INDEXER,TOPK_MOE`; (c) t/s a parità d'accettazione sul banco chat; (d) **braccio 100k: misura del compute buffer e tentativo ub 64** — se ub sale, questo è il pezzo dell'anno per il prefill lungo |
| 2 | **#25832a — solo la condizione di offload FA-con-sinks** (`ggml-backend.cpp`, ~10 righe della PR) | la FA non viene più dirottata sul backend del peso delle sinks | **"FA spenta sulla bozza"** (difetto noto, a verbale nel mandato) | la bozza è ~30-40% del ciclo; FA vs soft_max sui suoi strati: qualche ms/ciclo [IPOTESI] | ADIACENZA sul nostro `ggml-backend.cpp` (+481 nostro, ma la condizione è puntuale) | log di piazzamento: `FLASH_ATTN_EXT` della bozza su GPU; poi ms/ciclo della bozza |
| 3 | **Secondo passo checkpoint** (nessun pick: design da #25784) | non salvare il checkpoint quando l'anello copre la profondità della bozza | C_save pagato OGNI episodio: ~12,85 MiB serializzati (audit 37) ≈ 0,7 ms di sola banda PCIe + latenze per-chiamata → 1-4 ms/ciclo = **0,7-2,8%** [DEDOTTO] | tutto il guadagno di C_save | MEDIO, tutto in casa (server-context + kv-ring nostro); #25784 serve come referenza di semantica (loro: `seq_rm` accetta code ≤ n_rs_seq e il server fa il restore pieno solo oltre) | PRIMA: una corsa con `LLAMA_CKPT_CRONO=1` (già in casa) dà C_save in ms — decide se il fronte vale; POI SHA-cancello spec-off e replay-detector |
| 4 | **#26385** race SMEM `block_reduce` | — | fiducia | — | **FATTA** (ieri notte; sync in `common.cuh:631,642`) | `test-backend-ops -o SOFT_MAX` quando il banco è libero, per chiudere a verbale |
| 5 | **#26051** 7 fix OOB (grammar/kv/model/quant/sampler/vocab) | UB silente | fiducia | ~0 perf | PULITO quasi (kv-cache.cpp 6 righe adiacenza) | compila + una corsa fumo |
| 6 | **#22789** input degli split dinamici (max 30 → dinamico) | crash-class sui grafi con molti split | i nostri 45 split della lane K e i bracci futuri | 0 oggi (siamo sotto il tetto), assicurazione domani | ADIACENZA sul nostro `ggml-backend.cpp` | insieme al prossimo intervento su quel file (es. #25832a) |
| 7 | **#24776** top_k/argsort a blocchi ≤64 MiB | tetto ai buffer temporanei | VRAM al prefill lungo (indexer top-512 su righe da n_kv) | 0 se compiliamo il ramo CUB per-riga; se no, picchi ~600 MB a 105k×ub512 [DEDOTTO] | PULITO (`top-k.cu`/`argsort.cu` non nostri) | **prima un grep di build**: `CUB_TOP_K_AVAILABLE` esige CCCL ≥ 3.2 (`top-k.cu:4-11`); i fallback allocano `ncols×nrows` pieno (`:79,:90`) |
| 8 | **#25325** stato DSV4 solo righe usate | serializzazione più piccola | C_save | **≈ ε da noi**: i nostri anelli (CSA 512, HCA 256, LID 512) sono A CAPIENZA per costruzione a regime → "solo usate" ≈ tutte; e muore del tutto se la riga 3 elimina il salvataggio | MANUALE sul kv-ring nostro | declassata: solo se la riga 3 dice che il salvataggio resta |
| 9 | **#26320** contatori spec al replay | statistiche gonfiate | fiducia nei numeri p1/mean_len | con i replay →0 (rollback in casa) l'inquinamento cumulativo si spegne da solo; resta la pezza estetica nel NOSTRO `speculative.cpp` | n/a (pezza nostra) | confronto per-slot vs cumulativo su una corsa |
| 10 | **#26531+#26672+#26577** reshape al load | −1 nodo/strato (wo_a) e fix stride quantizzati | nodi (~43) | ~0,03% | ADIACENZA (model-loader) + `deepseek4.cpp` 4 righe | solo al prossimo rebase, non come leva |
| 11 | **#25472** sfratto checkpoint entro min-step + **#26221** `common_memory` | meno checkpoint di prompt in RAM | igiene RAM del server | 0 perf | il nostro server-context è divergente | solo lettura; idea utile se i checkpoint di prompt crescono |

Ordine di pick consigliato per il lotto 1 (stesso file, conflitti minimizzati,
ricordando che `deepseek4.cpp` va normalizzato a LF PRIMA di qualsiasi pick):
resto di **#25370** (maschere f16, +llama-graph) → **#25702** (`prev_idxs/cur_idxs`
→ get_rows unica: il nostro pre-fix è a `deepseek4.cpp:531-539`) → **#24231**
(op ggml, enum e tabelle: stessa dance delle 3 op HC) → **#25545** (kernel CUDA,
file nuovi) → **#25896** (`topk-moe.cu` mai toccato da noi; la guardia
upstream ora accetta `GGML_UNARY_OP_SOFTPLUS`). Ogni passo col suo cancello
prima del successivo.

---

## 3. Le cinque famiglie del mandato, verdetti secchi

### 3.1 Fusioni di kernel e ottimizzazioni di grafo
- **Da prendere**: il lotto indexer+router (tabella riga 1). È l'ultima massa
  vera: dopo, dei 10.507 nodi ne restano ~3.200 di stato compressori (che le
  fusioni upstream NON toccano — il rework di #25784 anzi ne AGGIUNGE per i
  piani di rollback) e ~2.000 di HC residua già fusa.
- **#26767 (rms+mul+rope+view+set_rows)**: NO, confermato con la ragione di
  grafo: il nostro store è `DSV4_KV_RING_STORE` custom (il pattern con
  set_rows non matcha) e la variante corta rms+mul+rope esige adiacenza che il
  grafo DSV4 non ha (fra norm e rope c'è sempre una proiezione). Upstream
  stesso: ~1% sui modelli dove matcha.
- **#26171 (gemmv senza trasposta per pesi [·,1] f32)**: MORTA per noi — le
  candidate erano le affini HC pre-fusione, e la fusione HC le ha eliminate.
- **#26649 `ggml_build_forward_order`**: utility di ordinamento del build senza
  marcare il calcolo; utile da conoscere per la nostra lane (oggi ordiniamo con
  `build_forward_expand`), zero valore come pick.
- **Leva in casa mai provata, la ricordo di nuovo**: `GGML_CUDA_GRAPH_OPT=1`
  (stream concorrenti dentro la cattura, `ggml-cuda.cu:4886-4919`). Upstream
  non l'ha più toccata dal fork. Col grafo a 10,5k nodi e il 30% di stato
  compressori INDIPENDENTE dal flusso denso, il braccio da 30 minuti è più
  interessante di prima, non meno. La guardia fork/join abortisce ad alta voce:
  prova sicura.

### 3.2 MoE (`mul_mat_id`, routing, raggruppamento)
- **#25896**: nel lotto 1 (il loader ESIGE `sqrtsoftplus`; da noi la fusione
  del router non scatta — assenza verificata anche oggi in `topk-moe.cu`).
- **#25441 (dedup quantizzazione gate/up)**: invariato dal primo giro — copre
  dispatch standard e prefill MMQ; il decode nostro serve dalla cache via
  mmvq/maschera, l'eco va scritto a mano in `mmvq.cu` (patch nostra, non pick).
  Prefill: piccolo, dopo il lotto 1. Base driftata da #24127 (refactor MMQ):
  se il pick strappa, adattare a mano, NON portare #24127 per intero.
- **Trasporto esperti (81-90% del prefill)**: **niente nei 390**, riconfermato
  al secondo giro: `mmid.cu` cambia solo per #25441; `vecdotq.cuh` cambia solo
  per Q1_0/Q2_0 (formati nuovi, non i nostri iq2_xxs/q2_K); `mmvq.cu` = 8 righe
  Q2_0. Il fronte trasporto resta interno (cache-esperti nostra).
- **258 attivazioni/posizione**: nessun commit upstream le riduce (è struttura
  del modello + route); l'unico attacco esterno resta la famiglia AcceptMoE già
  in casa.

### 3.3 Speculazione
- Il valore vero della famiglia NON è un pick, è §4 (secondo passo checkpoint).
- **#25720 (logits della bozza)**: VERIFICATO ASSENTE da noi — i nostri batch
  bozza/iniezione viaggiano con `logits=false`/`nullptr`
  (`speculative.cpp:685,692,1132`). Riga chiusa.
- **#26320**: vedi tabella riga 9 — con i replay a zero si è quasi spenta da
  sola.
- **#26510 (refactor init), #26389 (metriche), sidecar (#26458/#26165/#25955),
  MTP di ogni specie, eagle3**: linea parallela / QoL, confermato niente.
- **#25830 (parametri adaptive esposti)**: upstream ha il draft adattivo come
  noi abbiamo il K adattivo; solo lettura per idee di tuning.

### 3.4 Attenzione e flash attention, maschere sparse
- **Verdetto principale, e vale la pena dirlo tondo**: upstream NON ha risolto
  il salto dei buchi. `fattn-common.cuh` è INTATTA dal 9/7 (unico movimento
  CUDA-FA: rimozione del kernel WMMA Volta, per noi Ampere = inerte);
  `flash_attn_mask_to_KV_max` scandisce le tile DA DESTRA e si ferma alla
  prima viva (`fattn-common.cuh:666-718`): solo frontiera, per costruzione.
  E TUTTE le attenzioni sparse upstream consumano la selezione top-k come
  MASCHERA (`deepseek4` via `set_rows` di zeri, `glm-dsa.cpp:400` idem,
  `minimax-m3.cpp:399-491` maschera a blocchi): nessuno compatta, nessuno
  salta. **Il fronte "saltare i buchi della top-512" è vergine anche fuori**:
  o skip-list per-tile dentro i kernel FA (estendere KV_max a un elenco di
  tile vive per blocco di query) o gather delle 512 selezionate + FA densa
  (a 105k = 200× di letture in meno sull'attenzione CSA). Fronte interno,
  potenziale contributo upstream, non pick.
- **#25832a**: la cura della FA sulla bozza (tabella riga 2).
- **#25871 (tipi K/V uguali + auto-FA)**: guard-rail sui flag; i flag li
  controlliamo noi. Solo-lettura se mai quantizzeremo il KV.
- Le maschere f16 alla nascita (#25370 parte viva): nel lotto 1.

### 3.5 Correttezza (race, barriere, guardie)
- **#26385**: fatta. Resta il braccio gratis `test-backend-ops -o SOFT_MAX`
  (+ racecheck se installato) per chiudere a verbale.
- **#26051**: igiene quasi gratis, riga 5.
- **#22789**: assicurazione sui bracci, riga 6.
- **#25676 (sync copie async prima di svuotare `embd_seq`)**: colpisce SOLO i
  pooled embeddings (`--pooling`), che non usiamo → inerte; pick gratuito solo
  in un rebase.
- **#26731 (cpy quantizzata)**: context-shift con KV quantizzato: non lo
  usiamo. **#26555**: file di test. **#40b740ad0/#4f37f519 (server null-ctx /
  null sampling)**: robustezza su un server-context che da noi è divergente —
  solo lettura. Windows/WDDM: **niente di runtime nei 390**, riconfermato.

---

## 4. Il fronte checkpoint: cosa upstream ha capito e cosa ne prendiamo

Ricostruzione [MISURATO nel codice upstream]:
- `llama_dsv4_comp_state` alloca `(1 + n_rs_seq)` **piani** per lo stato dei
  compressori; ogni ubatch il grafo scrive gli snapshot dei piani (indici
  `state_snapshot_*`) e, se `rs_idx[seq] = d > 0`, il grafo successivo
  RIPRISTINA il piano d (indici `state_restore_*`).
- `seq_rm(seq, p0, -1)` con coda `pos_max-(p0-1) ≤ n_rs_seq` NON fallisce più:
  arretra la cache raw e segna `rs_idx` — il ripristino avviene in-grafo al
  forward dopo. Il server upstream cade sul restore da checkpoint SOLO oltre
  n_rs_seq (è la frase esatta del corpo di #26320).
- In più: `clear_compressed(seq)` per-sequenza (non più nuke globale),
  `seq_cp` di sequenze intere supportata, `seq_add/div` senza nuke.

Da noi [MISURATO]: `seq_rm_tail` + anello con margine fa la stessa cosa per la
coda (replay→0, SOTA 13,21→13,23), MA **il checkpoint si salva ancora a ogni
episodio** (audit 37: ~12,85 MiB/salvataggio, "il termine C_save resta
pagato"; il secondo passo — smettere di salvare — è dichiarato e non fatto).
Upstream dimostra che il secondo passo è sano: con l'anello che copre la
profondità della bozza, il salvataggio per-episodio serve solo ai casi oltre
margine, che si possono coprire con un salvataggio raro (ogni N episodi o solo
su richiesta di restore profondo). Il valore è C_save × frequenza: il
cronometro `LLAMA_CKPT_CRONO=1` (già in casa, commit `f8df4de8a`) lo dà in una
corsa. Aritmetica di attesa: 12,85 MiB a 18,4 GiB/s ≈ 0,7 ms di banda pura +
latenze per-chiamata (audit 33) → 1-4 ms su un ciclo da 140,6 = **0,7-2,8%**
[DEDOTTO]. Sotto 1 ms misurato: fronte chiuso, si archivia anche #25325.

Attenzione di perimetro se si copia il disegno: i piani upstream costano nodi
(restore+snapshot ≈ 10-14 nodi × strato compresso) — è il prezzo che pagano per
la generalità multi-sequenza. Noi con UNA sequenza e l'anello già in casa
possiamo tenere il nostro meccanismo e togliere SOLO il salvataggio: zero nodi
nuovi.

---

## 5. Cosa NON esiste nei 390 (fronti che restano interni, a verbale)

1. **Salto dei buchi della maschera sparsa** — §3.4: vergine ovunque.
2. **Trasporto esperti in offload** — nessun commit tocca il nostro percorso;
   la sonda del 9/8 (98,7% atterrato al join) dice che il fronte si raffredda.
3. **MMVQ per iq2_xxs/q2_K** — 8 righe in un mese, tutte Q2_0. Il fronte LUT/
   gate-up fusi resta nostro (PAVIMENTO leva 2).
4. **WDDM / Windows runtime** — niente.
5. **Prefill 20 tok/s a contesto lungo** — upstream non ha una leva diretta;
   quella indiretta (ub sbloccato dall'op indexer) è la riga 1 ed è NOSTRA da
   dimostrare.

---

## 6. Verifiche a costo zero, in ordine di resa

1. `LLAMA_CKPT_CRONO=1` su una corsa standard → C_save in ms → decide la riga 3
   (e archivia o tiene viva #25325).
2. Grep di build per `CUB_TOP_K_AVAILABLE` (CCCL ≥ 3.2) nel log di compilazione
   → decide se #24776 è urgente o inerte.
3. Conteggio nodi dal log del server (gratis, già stampato) prima/dopo ogni
   passo del lotto 1; atteso finale ~9.800-9.900.
4. `test-backend-ops -o SOFT_MAX` (+racecheck) → chiude #26385 a verbale.
5. Braccio `GGML_CUDA_GRAPH_OPT=1` (30 min, abort rumoroso se litiga col
   fork/join) — leva in casa, mai misurata, due giri di audit che la rimandano.
6. Metadati GGUF (YaRN #26673 + template chat #25414/#26398 + tipo token_embd):
   INVARIATO dal primo giro, ancora da fare, solo lettura file. Il cancello va
   sul contenuto.

## 7. Meccanica e avvertenze

- Storia shallow: `git fetch upstream <sha> --depth=2` prima di ogni pick
  (`33a75f41c` e `596a5795b` sono già in locale).
- **Normalizzare `deepseek4.cpp` a LF prima di qualunque pick** (avvertenza
  RACCOLTA ancora valida).
- Lo SHA del binario DIVERGERÀ con l'op indexer fusa (ordine delle somme):
  legittimo — il cancello SHA vale spec off E K=0 dentro lo stesso binario.
- La ricattura dei CUDA graph cambia topologia: prima corsa col rilevatore di
  divergenze acceso (lezione audit 11 sul replay a taglia stantia).
- Il lotto 1 cambia l'accettazione? NO per costruzione (l'indexer decide le
  posizioni attese, non i logits della verifica) — ma il metro resta
  "ms/posizione a parità di accettazione" per abitudine di casa.

## 8. Fonti

Primo giro: `audit/UPSTREAM_390.md` (con le correzioni di §1); RACCOLTA:
`audit/RACCOLTA.md`. Enumerazione e corpi PR: scratchpad di sessione
(`upstream_commits.txt`, `upstream_by_file.txt`, `pr_details.txt`,
`upstream_tree_diffstat.txt`, `d2_*.diff`). Codice: diff d'albero
`5c3a58686..upstream/master` riproducibile in locale; nostro albero a HEAD
`24fd5c2ee`. Numeri di casa: audit 30 (composizione strati e nodi), 33/37
(rollback e C_save), 39 (seq_pos_min), 41 (prefill), PAVIMENTO (calibrazione
lanci), memoria di progetto (ub 16 a 100k, prefill 82', p1/mean_len).
