# 43 — IL CAMMINO DELLA BOZZA: da dove viene p1, e chi lo muove davvero

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `24fd5c2ee`.
**Niente compilato, niente eseguito**: codice letto riga per riga
(`common/speculative.cpp` 2.297 righe non vuote, `src/models/dflash.cpp` intero,
i tratti speculativi di `tools/server/server-context.cpp`, più `common/sampling.cpp`,
`common/common.cpp`, `src/llama-context.cpp`, `src/llama-kv-cache.cpp`,
`src/models/deepseek4.cpp` per i punti di aggancio) e i log già in cassa in
`D:\ds4_work\llama_run\` (289 righe `acc per pos` su ~2.680 file, serie `g*`,
`lungo_rb*`, `df_*`, famiglie `c2..c7`). Marcatura: [MISURATO] = codice o log;
[DEDOTTO] = aritmetica su misure; [IPOTESI] = da falsificare, contatore indicato.
Non ripeto i reperti di audit 16/18/32/34/36/37: li cito e correggo dove il
codice di oggi li smentisce.

## L'esito in sei righe

1. **p1 è una funzione deterministica della traiettoria di testo, non una
   proprietà stabile del drafter.** Corse identiche danno p1 identico alla
   quinta cifra (g1/g1b: 0,86470 entrambe); bracci che differiscono per UN
   pomello numerico del bersaglio (K, slot, FUSO, fork) danno testi diversi e
   p1 sparso su **0,763–0,891** nella stessa campagna. Regola nuova di metodo:
   **p1 è confrontabile solo fra corse con lo stesso SHA**; fra SHA diversi una
   differenza < ±0,05 non dice niente sul drafter. [MISURATO §1.4]
2. Il drafter legge dal bersaglio UNA cosa numericamente viva: **la media dei
   4 flussi hyper-connection all'ingresso degli strati 41/42/43**
   (`deepseek4.cpp:1260-1268`). Tutto ciò che tocca quell'aritmetica
   (AcceptMoE, rollback, lane CPU∥GPU, fusioni, Sinkhorn) arriva a p1 per due
   canali distinti: (i) inquinamento dello stato iniettato, (ii) divergenza di
   traiettoria. I contatori per separarli sono in §1.5–1.6.
3. **Il calo 0,912→0,899 col rollback parziale è spiegabile per composizione,
   non per danno al drafter** [DEDOTTO]: il mondo-rollback bozza 365 episodi
   ancorati ESATTAMENTE sul punto di divergenza (che il mondo-ripristino
   risolve col replay, senza bozza); basta p1≈0,78 su quei 365 per produrre
   l'intera differenza. Falsificatore per-episodio in §1.6 — una corsa con
   `LLAMA_TRACE=1`, zero patch.
4. **La coda del blocco NON è marcia.** L'accettazione condizionale per
   posizione (rapporto fra voci adiacenti di `acc per pos`) sta in una banda
   quasi piatta **0,75–0,85** fino alla posizione 5, senza collasso monotono;
   è la SOPRAVVIVENZA (il prodotto) che crolla. Il gradiente si ricava GIÀ dai
   log in cassa (289 righe a TRACE), **non** dai `-lv 4` (in cassa non
   esistono: l'unico probe alto-verboso ha ~8 episodi). [MISURATO §4]
5. Del mazzo di leve del cammino, **quasi tutte sono morte, inerti o già al
   loro ottimo**: `p_min` non è mai letto nel ramo DSpark, `p_split` non è
   letto da nessuno, `backend_sampling` non decide (audit 18), `n_min`=0
   inerte, `conf_min` chiusa a n-max 1 per aritmetica (audit 34), la Sinkhorn
   della bozza è già misurata piatta (df_20/4/1: p1 0,863/0,851/0,826, t/s
   10,47/10,52/10,24 — pareggio nel rumore). L'unica correzione di default che
   il codice stesso dimostra: **`LLAMA_SPEC_DRAFT_TOPK=1` dovrebbe essere il
   difetto** — con accettazione a confronto esatto l'argmax della bozza è
   ottimale per QUALSIASI temperatura del bersaglio (dimostrazione in §3.1).
6. **La domanda del mandato è giusta a metà** (permesso usato, §6): p1 è
   davvero tutto il margine residuo a n-max 1 — t/s = (1+p1)/ciclo, e a ciclo
   140,6 ms fisso siamo ESATTAMENTE a (1+0,865)/0,1406 = 13,26 — ma dentro il
   cammino della bozza non c'è p1 gratis da raccogliere: p1 abita nel
   CONTENUTO (0,865 HTML / 0,667-0,676 prosa), nella fedeltà dello stato del
   bersaglio (da non degradare) e nella composizione degli episodi. L'audit
   consegna parapetti e leve chiuse, non un giacimento.

---

## 0. La mappa del cammino (per fissare i nomi)

Un ciclo di decode speculativo a n-max 1, coi punti esatti [MISURATO]:

1. **Arruolamento** (`server-context.cpp:2967-3006`): per lo slot in
   generazione con `spec_draft` vuoto si compila `dparams` — `n_past =
   prompt.n_tokens()` (posizione del token appena campionato), `id_last =
   slot.sampled`, `result = &slot.spec_draft`. Riga 2995: copia INTERA del
   prompt in `slot.spec_prompt` (vedi §2.4).
2. **Bozza** (`common/speculative.cpp:1146-1272`): `seq_rm` della coda del
   contesto bozza (1169), poi UN batch `[id_last @ n_past]` — a n-max 1
   **nessun token MASK entra mai nel batch** (1176-1181: `n_block_tokens =
   n_draft` per DSpark, quindi 1) — e UNA `llama_decode` (1189). Il grafo
   (`dflash.cpp:347-471`) è 3 blocchi DSV4 + testa hc + `output_norm` +
   lm_head del bersaglio; la testa di Markov (256-344) somma ai logit
   dell'àncora il bias `w2·w1[id_last]` e, se `conf_proj` esiste, calcola
   `conf = sigmoid(proj([t_embd; w1[id_last]]))`. Campionamento host
   (1224-1244): catena `TOP_K(spec_top_k)` + `dist(seed)` (`sampling.cpp:376`).
3. **Verifica** (`server-context.cpp:494-528, 3755`): batch bersaglio
   `[campionato, bozza...]`, un decode.
4. **Semina** (`server-context.cpp:3812` → `speculative.cpp:1043-1144`):
   `process()` sull'INTERA vista di verifica — righe rifiutate comprese —
   concatena i tap 41/42/43 (`llama_get_embeddings_layer_inp`), li fonde con
   `fc` via `llama_encode`, e INIETTA il risultato come K/V della bozza alle
   posizioni della vista (grafo d'iniezione: `dflash.cpp:500-574`).
5. **Accettazione** (`server-context.cpp:3982`,
   `sampling.cpp:624-652`): **confronto esatto** token per token
   (`draft[i] != id → break`), poi il token correttivo/bonus. Contabilità
   per-slot pulita (`update_spec_stats`, 332-343); contatori interni del
   proponente ancora sporchi di replay (§5.6).

Il cammino della bozza tocca il bersaglio SOLO qui: tap 41/42/43 (passo 4),
`tok_embd` e `output` condivisi (`dflash.cpp:576-584, 452-463` — statici),
`id_last` e `n_past` (passo 1). Non legge sampler, non legge KV del bersaglio,
non legge la route.

---

## 1. Risposta 1 — cosa determina p1, e cosa lo degrada in silenzio

### 1.1 L'inventario completo di ciò che il drafter legge dal bersaglio

| ingresso | riga | natura | se cambia |
|---|---|---|---|
| media dei flussi HC all'input degli strati 41/42/43 | `deepseek4.cpp:1260-1268` (produzione), `speculative.cpp:1091-1101` (consumo) | **numericamente viva**: cambia con qualunque riordino di somme del bersaglio | p1 si muove per i due canali di §1.5 |
| `tok_embd` del bersaglio (embedding di `id_last` e delle MASK) | `dflash.cpp:576-584` | statico (pesi) | solo con un modello diverso |
| `output` (lm_head) del bersaglio | `dflash.cpp:452-463` | statico | idem |
| `id_last` (token campionato) | `server-context.cpp:3001` | per costruzione | è l'àncora: il suo valore È la traiettoria |
| `n_past` / posizioni | `server-context.cpp:3000`, `speculative.cpp:1180` | contabile | un disallineamento = KV iniettato a posizioni sbagliate (mai osservato; guardia in `begin()`, 1035-1040) |
| vista di verifica come indice riga | `speculative.cpp:1054-1067` | assume righe per-sequenza contigue | con np>1 e viste miste vale l'avvertenza di audit 18 (blocchi non uniformi) |

Nota strutturale (non un difetto, un tetto): **l'àncora è sempre un passo
indietro** — al momento della bozza lo stato iniettato più recente è quello
del token PRIMA di `id_last`; di `id_last` la bozza ha solo l'embedding. È il
disegno del riferimento DSpark; qualunque idea di «iniettare anche l'àncora»
è impossibile per costruzione (il forward del bersaglio su `id_last` non è
ancora avvenuto).

### 1.2 AcceptMoE: inquinamento vero del proponente [MISURATO, da audit 36 + codice]

Con la verifica mascherata, le righe `t ≥ ESATTE` calcolano la MoE sui soli
residenti → i tap di QUELLE righe escono approssimati → `process()` li
inietta nel KV della bozza (`speculative.cpp:1121-1139`) e lì restano per
sempre se il ciclo accetta (nessun replay li rigioca). La dose-risposta è già
nei log: a parità di conf, i rifiuti del gate di confidenza passano
**178 → 386** (c4_n2bm3c08 → c5_c2c08) e l'accettazione della seconda
posizione scende 0,862 (E=99, bit-identico alla base) → 0,832 (E=2) →
0,793 (E=1) → 0,533 (E=1+conf 0,8). Il meccanismo passa anche dalla
confidenza: `conf` è calcolata su `t_embd` della bozza (`dflash.cpp:291,308`),
che discende dagli stessi KV iniettati — **la maschera sporca sia la proposta
sia il giudice della proposta**.

**Falsificatore (contatori)**: braccio AM=1 E=1 conf 0 con `LLAMA_TRACE=1`:
per ogni episodio la riga `accepted N/M`; p1 condizionato alla distanza
dall'ultima riga mascherata-accettata. Se p1 degli episodi con àncora entro 2
posizioni da una riga mascherata ≈ p1 degli altri, l'inquinamento del
proponente è falsificato e resta solo la selezione del gate. Attesi, se la
tesi regge: Δ ≥ 5 punti fra le due classi.

### 1.3 Rollback parziale: quasi certamente composizione, non danno [DEDOTTO]

I numeri del mandato vengono da `lungo_rb0/rb1.server.log` (10/8, 04:19-04:32,
6.823/6.854 token) [MISURATO]:

```
rb0 (ripristino): 3.415 verifiche, 303 ripristini,   p1 0,912, 12,73 t/s
rb1 (rollback):   3.609 verifiche, 365 code riavvolte, p1 0,899, 12,94 t/s
```

Nel mondo-ripristino, l'episodio dopo un rigetto è un REPLAY senza bozza: il
token correttivo viene commesso da un forward del bersaglio e la bozza
successiva si àncora al BONUS, un token DOPO il punto di divergenza. Nel
mondo-rollback quel replay non esiste: la bozza si àncora sul token correttivo
stesso, cioè NEL punto dove il bersaglio ha appena sorpreso il drafter. Il
mondo-rollback aggiunge quindi ~365 episodi «duri» che l'altro mondo non
bozza mai. Aritmetica: `0,899·3609 = p_clean·3244 + p_r·365`; con
`p_clean = 0,912` esce **p_r = 0,78** — plausibile per posizioni
post-divergenza, e il t/s intanto SALE (+1,6%), che è ciò che conta.

Attenzione: questa derivazione è circolare (usa i totali); il test vero è lo
spezzamento per-episodio. **Falsificatore (contatori)**: una corsa rb1 con
`LLAMA_TRACE=1`; contare `accepted 1/1` fra gli episodi che seguono
immediatamente una riga `coda riavvolta a pos` contro gli altri. Predizione:
p1|post-riavvolgimento = 0,74–0,82 su ~365 episodi, p1|altri = 0,905–0,918.
Se ENTRAMBE le classi stanno a ~0,899, il calo è danno reale (allora il
candidato è il collocamento delle celle SWA dopo il riavvolgimento, audit 37
cancello 3) e va cercato lì.

### 1.4 Il canale che nessuno aveva messo a verbale: la divergenza di traiettoria

`acc per pos` estratto da TUTTA la cassa [MISURATO]:

```
stessa configurazione, corse ripetute:   g1 = g1b = 0,86470   g2 = g2b = g4 = 0,86025
famiglia c2 (stesso binario, un pomello cambiato per braccio):
  base 0,841 | k15 0,888 | k25 0,839 | k3 0,838 | k2fork 0,891 | f3 0,877 | f5 0,868 | s300 0,855 | s380 0,872
c3_f5s380 0,763 | c6_k15 0,797 | c6_base 0,868
```

Con spec accesa e TOPK=1 il sistema è deterministico: stessa corsa → stesso
testo → **p1 identico alla quinta cifra**. Ma quasi ogni leva (K, slot,
fork, FUSO) cambia chi arrotonda cosa nel bersaglio → il testo diverge →
p1 misura la difficoltà di UN ALTRO testo. Lo spread misurato fra bracci
«equivalenti» è ±0,05, cioè **più grande dell'effetto di quasi ogni leva che
inseguiamo**. Non è rumore (è riproducibile), non è qualità del drafter: è
un'altra domanda posta a un altro compito.

**Regola operativa che questo audit chiede di adottare**: nel ledger, p1 si
confronta solo a SHA uguale; a SHA diverso si confrontano t/s e ciclo, e p1
si annota con l'etichetta «traiettoria diversa». Le tre coppie identiche
della serie `g*` sono il campione di controllo che rende la regola gratuita.

### 1.5 I due canali, riassunti coi loro strumenti

| canale | meccanismo | strumento che lo isola |
|---|---|---|
| (i) inquinamento dello stato | tap approssimati/iniettati sporchi (AcceptMoE; in teoria anche graph-replay a taglia stantia, audit 11) | p1 per-episodio condizionato alla distanza dall'evento sporco (§1.2) |
| (ii) divergenza di traiettoria | il pomello cambia gli arrotondamenti del bersaglio → altro testo → altro compito | coppie same-SHA (§1.4); prefisso comune fino alla prima divergenza dei due output |

### 1.6 Cosa manca al parco strumenti (e costa una riga di campagna, non codice)

Le righe per-episodio `accepted N/M draft tokens` esistono GIÀ a
`LLAMA_TRACE=1` (`server-context.cpp:4014-4026, 4065-4067`) e in cassa non ci
sono (solo `dperche_R0_sonda_lv10.log`, ~8 episodi, 3/8). Ogni falsificatore
di questo capitolo si paga accendendo quella variabile in campagna. Nessun
altro strumento nuovo è necessario per p1.

---

## 2. Risposta 2 — la testa di Markov: scritto e mai usato, scritto e usato male

### 2.1 Cosa è VIVO nel cammino attuale (per non buttare il bambino)

A n-max 1 il «blocco» degenera: niente MASK nel batch (§0.2), niente catena
argmax (il ciclo di `build_dspark_markov_head` gira una sola iterazione,
`dflash.cpp:298-325`), niente attenzione fra posizioni della bozza. Restano
vivi: il bias di Markov sull'àncora (`w2·w1[id_last]`, righe 299-304) e la
confidence head (308-319). DSpark a n-max 1 è di fatto un drafter
EAGLE-simile a un token con bias bigramma — tutta la macchineria «diffusione
a blocchi» (MASK, non-causalità: `speculative.cpp:1017`) è presente e inerte.

### 2.2 Morti nel ramo DSpark [MISURATO, codice]

- **`p_min` non è mai letto**: il gate `cur_p->data[0].p < params.p_min`
  esiste solo nel ramo DFlash (`speculative.cpp:1258`); il ramo DSpark
  (1224-1244) non lo consulta. `--spec-draft-p-min` su DSpark è un no-op
  totale. Falsificatore statico già concluso; contatore di conferma: due
  corse p-min 0 / p-min 0,9 → `#gen drafts` e p1 identici a parità di SHA.
- **`p_split` non è letto da NESSUNO in tutto l'albero** (definito
  `common.h:331`, scritto da `arg.cpp:3763-3766`, zero altri riferimenti):
  fossile del vecchio esempio speculativo.
- **`backend_sampling`** — già a verbale (audit 18): il costruttore DSpark
  crea sempre sampler host.
- **`n_min`** (difetto 0, inerte): da acceso interagirebbe male con la
  confidenza — il troncamento a `k < n_min` butta l'intera bozza già pagata
  (`speculative.cpp:1268-1270`).

### 2.3 Usati male (citazioni, non ripetizioni)

- catena Markov su argmax ma emissione campionata (audit 18): **sanata di
  fatto da TOPK=1**, che rende argmax ed emissione la stessa cosa. Resta un
  difetto latente per chi rialzasse il top-k.
- `conf_proj` su stato post-norm invece che pre-norm (audit 18): la soglia
  `--spec-draft-conf-min` lavora su una confidenza non calibrata col
  riferimento. Vivo, pesa solo a conf accesa.
- buffer nextn stantio se `conf_proj` manca dal GGUF (audit 18): combinazione
  oggi non esercitata (il nostro GGUF la contiene).
- blocchi per-sequenza non uniformi reinterpretati uniformi (audit 18):
  dorme finché `-np 1`.

### 2.4 Trovati in QUESTO audit

1. **La copia del prompt a ogni ciclo che nessuno legge.**
   `server-context.cpp:2995` copia l'intero vettore dei token
   (`get_text_tokens()` ritorna per valore, `server-common.h:201`) in
   `slot.spec_prompt` a OGNI ciclo di bozza; `dp.prompt` è letto solo dagli
   n-gram (`speculative.cpp:1766,1818`) e da una stampa DBG (2690). In
   configurazione solo-DSpark: 4,8 KB/ciclo a 1.200 token — spiccioli — ma
   **0,4 MB/ciclo a contesto 100k**, sul cammino seriale del server. Il TODO
   upstream esiste già (`speculative.h:46`). Peso: basso oggi, medio sul
   fronte contesto-lungo. Falsificatore: è statico (nessun consumatore); la
   conferma dinamica è il profilo del ciclo a 100k con e senza la riga.
2. **La confidenza è calcolata, gonfiata 4096× ed estratta anche quando
   nessuno la leggerà.** Il grafo la produce sempre (`dflash.cpp:332-339`:
   `ggml_repeat` porta `[1, n_tok]` a `[n_embd, n_tok]` solo per compiacere
   il buffer nextn) e l'estrazione D2H è sempre attiva
   (`speculative.cpp:1016`); il consumatore la legge solo se `conf_min > 0`
   (1211) e ne usa UN float per riga (1227). A conf 0: ~5 op in più per
   posizione nel grafo + 16 KiB/ciclo D2H buttati. Peso: basso (audit 34 lo
   delimita a ≤0,13 ms dentro `gen`), ma è la voce «fa una cosa che non
   serve» più pulita del cammino. Nota: NON si può spegnere l'estrazione
   nextn in blocco — la usa `process()` per l'uscita dell'encoder (1121).
3. **I checkpoint della bozza sono codice morto a runtime** — correzione ad
   audit 16 («il server salva e ripristina lo stato del contesto bozza con
   update_dft/load_dft»). Il probe (`common.cpp:1481-1521`) chiama
   `seq_rm(0,1,-1)` e `llama_kv_cache::seq_rm` **ritorna sempre true**
   (`llama-kv-cache.cpp:386-452`; iswa inoltra e ANDa,
   `llama-kv-cache-iswa.cpp:113-120`) → `ctx_dft_seq_rm_type = PART` →
   `use_ckpt_dft` è falso ovunque (`server-context.cpp:2971,2991,3025`):
   `update_dft` non gira mai e le due `load_dft` (3029, 4053) girano su un
   checkpoint vuoto. La pulizia vera della bozza la fanno le `seq_rm` di coda
   (3032, 4055, 4103, più `speculative.cpp:1084,1169`). Conseguenze: (a) il
   costo-bozza dei checkpoint è zero, non «escluso dal cronometro»; (b) i
   ritorni ignorati delle `seq_rm` in `speculative.cpp` sono sani perché la
   rimozione di coda riesce sempre su questa memoria. Contatore di conferma
   (gratis, una corsa DBG): la riga `created speculative checkpoint ...
   draft = X MiB` (3070-3073) deve stampare **0.000** — se stampa >0 questa
   sezione è falsificata.

---

## 3. Risposta 3 — leve e difetti: nascita o merito?

| leva | difetto | chi la legge | verdetto |
|---|---|---|---|
| `--spec-draft-n-max` | 3 (`common.h:327`) | driver + clamp a `block_size` (`speculative.cpp:971-979`) | **nascita**. Il merito misurato è 1 (famiglia n-max≥2 chiusa con l'aritmetica; il clamp a 5 vale solo come tetto). Il valore RICHIESTO, non clampato, dimensiona ancora gli output del server (audit 18, basso). |
| `--spec-draft-n-min` | 0 (`common.h:328`) | 1268-1270 | difetto giusto; >0 sarebbe dannoso con conf accesa (§2.2). |
| `--spec-draft-p-min` | 0,0 (`common.h:332`) | **nessuno nel ramo DSpark** | irrilevante per costruzione (§2.2). |
| `--spec-draft-conf-min` | 0,0 | 1211-1229 | difetto giusto a n-max 1 (chiusa per aritmetica, audit 34: anche a sovrapprezzo zero perde 0,2%); a n-max 2 paga solo con `LLAMA_SPEC_CONF_ESENTA_POS0=1` (misurato 10,71 vs 9,43) — fronte comunque chiuso dal mandato. |
| `--spec-draft-ubatch-size` | 0 = eredita (`common.h:329`, applicata in `speculative.cpp:2329-2331`) | `process()` per lo spezzamento (1072,1086) | **decode-inerte per costruzione** (batch bozza ≤ n-max+1 righe); morde solo sul prefill (encode+iniezione a blocchi di 64) — pertinenza del fronte prefill, non di questo. |
| `LLAMA_SPEC_DRAFT_TOPK` | **10** (998-1001) | catena sampler (1002-1008) | **nascita, e dominato** — sotto. |
| `LLAMA_DFLASH_SINKHORN_ITERS` | 20 (dal GGUF; override `dflash.cpp:76-85`) | grafo bozza | **misurata il 9/8** (`df_1/4/20.server.log`, 21:44-21:51): p1 0,826/0,851/0,863, gen 9,52/9,58/10,89 ms, t/s 10,24/10,52/10,47. A 4 iterazioni si scambia −1,2 pp di p1 con −1,3 ms di gen: pareggio dentro il rumore. Tenere 20; riaprire solo se `gen` diventasse >10% del ciclo. |
| `LLAMA_SPEC_CONF_ESENTA_POS0` | spento (1219-1222) | 1227 | giusto spento a n-max 1 (no-op esatto); da accendere SOLO con conf a n-max≥2. |
| `DSPARK_NO_MARKOV` | spento (`dflash.cpp:13-23`) | 468-470 | diagnostica, resta tale. |

### 3.1 Perché TOPK=1 dovrebbe diventare il difetto del fork (non solo una leva da ricordarsi)

L'accettazione è a **confronto esatto** (`sampling.cpp:638`): il bersaglio
campiona `t*` col SUO sampler e la bozza vince se ha proposto esattamente
`t*`. La probabilità di vittoria è `Σ_t P_tgt(t)·q(t)` con `q` la
distribuzione di proposta: è una forma lineare in `q`, massimizzata mettendo
tutta la massa sul singolo token che massimizza `P_tgt` — cioè **l'argmax
della bozza è la proposta ottima per QUALSIASI temperatura del bersaglio**,
non solo a temp 0. Il difetto attuale (top-10 + `dist` a seme casuale,
`sampling.cpp:376`) è quindi strettamente dominato: paga p1 E paga la
riproducibilità (il pavimento di rumore del 4% chiuso il 9/8). Il commento in
codice (996-997: «il default resta 10 per non cambiare il metro») era giusto
come igiene di campagna; come scelta di prodotto è una perdita secca. In più
TOPK=1 sana strutturalmente l'incoerenza argmax/campione della catena Markov
(§2.3). Costo del cambio: una riga; il cancello è la serie `g*` (p1 0,86470 /
0,86025 riproducibili per SHA).

Nota di regime da mettere a verbale: **tutti i p1 del ledger sono p1 a
temp 0**. In esercizio con temp>0 il confronto esatto abbassa p1 per
costruzione (`P(match) = Σ P_tgt·q ≤ max P_tgt < 1` anche a bozza perfetta):
il tetto 14,4 è un tetto da banco greedy.

---

## 4. Risposta 4 — il gradiente di p1 dentro il blocco

### 4.1 Prima l'unità del contatore (regola di casa)

`acc per pos` per-slot è una **curva di sopravvivenza**:
`n_accepted_per_pos[i]/n_draft_verif_steps` = P(accettati ≥ i+1)
(`server-context.cpp:332-343, 665-683`). Il «gradiente» chiesto dal mandato è
il **condizionale** `p_{i+1|i} = v[i+1]/v[i]`. Due trappole: (a) con conf
accesa i denominatori delle posizioni profonde restano TUTTI i cicli, anche
quelli troncati prima → diluizione (già annotata in audit 32 col †); (b) a
conf 0 e n-max fisso ogni bozza ha lunghezza piena e i condizionali sono
puliti.

### 4.2 I numeri, dalla cassa [MISURATO]

Bracci moderni (dopo il 9/8: TOPK=1, banco col template):

| log | data | sopravvivenza | condizionali |
|---|---|---|---|
| `c3_n2c0` | 10/8 | 0,863, 0,706 | p2|1 = **0,818** |
| `c4_n2bm3` / `c5_c1b` | 10/8 | 0,865, 0,674 | p2|1 = **0,779** |
| `gr_n3` | 9/8 14:40 | 0,837, 0,651, 0,490 | 0,778, **0,753** |
| `np_pin0_n5` | 9/8 13:25 | 0,800, 0,676, 0,505, 0,422, 0,324 | 0,845, 0,747, 0,836, **0,768** |

Bracci vecchi (8/8, PRIMA di TOPK=1 e del banco corretto — provenienza da
dichiarare, p1 assoluti non comparabili):

| log | sopravvivenza | condizionali |
|---|---|---|
| `nmax5_R1` | 0,954, 0,890, 0,844, 0,817, 0,688 | 0,933, 0,948, 0,968, 0,842 |
| `ch_B_spec_noovl_R1` | 0,821, 0,664, 0,529, 0,431, 0,361 | 0,809, 0,797, 0,815, 0,838 |
| `o2_S5_off_R1` | 0,860, 0,690, 0,609, 0,527, 0,419 | 0,802, 0,883, 0,865, 0,795 |

### 4.3 Il verdetto

**La bozza NON sbaglia progressivamente di più in coda al blocco.** Il
condizionale sta in banda 0,75–0,85 dalla posizione 2 alla 5, senza pendenza
monotona (in tre serie su cinque la posizione 4 è MIGLIORE della 3). Il
gradino vero è UNO ed è fra la posizione 1 e la 2 (0,86 → 0,78): l'àncora ha
lo stato quasi-fresco, le posizioni dopo pagano il condizionamento via catena
Markov — e poi il costo resta ~costante. La sopravvivenza (0,80→0,32 a 5)
crolla perché è un prodotto, non perché la coda sia marcia. Conseguenza per
il registro: il fronte n-max≥2 è morto di TRASPORTO (audit 32), non di
qualità della coda — se AcceptMoE o il KV-ring un giorno riaprissero
l'economia del blocco, la testa addestrata a 5 c'è ancora.

### 4.4 «Si ricava dai log a -lv 4?» — no, e non serve

In cassa non esistono corse `-lv 4` di campagna: l'unico log alto-verboso è
`dperche_R0_sonda_lv10.log` (3/8, ~8 episodi, 30 righe `draft candidate`).
Il gradiente si ricava dalle **289 righe `acc per pos`** già su disco (query
usata: `Select-String 'acc per pos = \(([^)]*)\)'`). Ciò che i log in cassa
NON danno è il per-episodio (per §1.3 e §1.2): quello costa una corsa con
`LLAMA_TRACE=1`, che stampa a INFO — niente `-lv 4`, niente ricompilazione.

---

## 5. Risposta 5 — cosa fa che non serve, cosa non fa che servirebbe

In ordine di peso, col contatore che decide.

1. **[fa, non serve — ma è già noto e sta altrove] il checkpoint del
   bersaglio a ogni ciclo con bozza** (11,7 MiB D2H × 599,
   `server-context.cpp:3043-3074`): è la voce grossa del contorno; il passo
   5.1 di audit 37 (smettere di salvarlo quando il rollback ha mostrato zero
   ripristini) resta il candidato con più millisecondi di tutto il capitolo.
   Contatore: `LLAMA_CKPT_CRONO=1` (già in albero, 3050-3068).
2. **[fa, non serve] semina anche le righe rifiutate** (`process()` su tutta
   la vista, `server-context.cpp:3809-3812`): a n-max 1 è 1 riga
   encode+inject buttata per ogni rigetto (~13% dei cicli) e la coda viene
   comunque rimossa al ciclo dopo. Piccolo per costruzione; upstream lo sa
   (TODO `TAG_SPEC_AVOID_DRAFT_REEVAL`, commento a 3809-3811 e il ref alla
   PR #22728). Contatore se mai si volesse prezzarlo: `PROC` per chiamata
   (già stampato) confrontato fra una corsa normale e una a p1 artificialmente
   basso (prompt prosa).
3. **[fa, non serve] la copia del prompt per ciclo** (§2.4.1) — spiccioli a
   1.200 token, reale a 100k.
4. **[fa, non serve] confidenza calcolata/gonfiata/estratta a conf 0**
   (§2.4.2) — ≤0,13 ms, igiene di grafo.
5. **[fa, non serve] due `load_dft` su checkpoint vuoto** (§2.4.3) — costo
   zero, ma il codice mente al lettore: chi legge crede che la bozza venga
   ripristinata. Una riga di log all'avvio col tipo di `ctx_dft_seq_rm_type`
   chiuderebbe l'ambiguità per sempre.
6. **[non fa, servirebbe] contatori del proponente puliti dal replay**: la
   contaminazione trovata da audit 16 è ancora lì — sul ciclo di replay
   `common_speculative_accept` viene chiamata coi token rigiocati
   (`server-context.cpp:4069`; la guardia `!slot.spec_replay` protegge solo i
   contatori per-slot, 4083-4085). Le statistiche `statistics draft-dspark`
   restano gonfiate (~+13% di eventi tutti-accettati a n-max 1). Finché non
   si ripara: leggere SOLO `draft acceptance`/`acc per pos` per-slot, mai il
   blocco `statistics`.
7. **[non fa, servirebbe] p1 per-episodio in campagna**: `LLAMA_TRACE=1`
   nelle righe di lancio degli script (costa ~700 righe di log per corsa).
   È il prerequisito dei falsificatori §1.2, §1.3 e §4.
8. **[non fa, servirebbe] la stampa `draft acceptance` chiamata col suo
   nome**: è token accettati/generati, non p1 (audit 16). A n-max 1
   coincidono; a n-max≥2 il ledger ha già rischiato di leggerli scambiati due
   volte. Una parola nella stringa di stampa.
9. **[non fa, e va bene così] allineare la bozza al sampler del bersaglio**:
   per il confronto esatto la proposta ottima è l'argmax della bozza (§3.1)
   qualunque cosa faccia il bersaglio — non serve leggere i parametri di
   sampling dello slot. Chiudo la pista prima che qualcuno la apra.

---

## 6. La domanda era giusta? (permesso usato)

**Metà sì, metà no.** Sì: a ciclo inchiodato (140-143 ms su ogni leva
provata), t/s = (1+p1)/ciclo e p1 è aritmeticamente TUTTO il margine —
13,23-13,26 misurato = (1+0,865)/0,1406 esatto; a p1 0,90 il banco darebbe
~13,5; il tetto 14,4 chiede p1→1. No: **il cammino della bozza non è dove p1
si guadagna** — dentro il cammino le leve sono morte (p_min, p_split,
backend_sampling), chiuse (conf a n-max 1, Sinkhorn bozza misurata piatta) o
già all'ottimo raggiunto per altra via (TOPK=1). Ciò che muove p1 nel ledger
sono: il contenuto (0,865 HTML / 0,667-0,676 prosa — non governabile), la
fedeltà dello stato del bersaglio (governabile in negativo: non degradarla),
e la composizione degli episodi (artefatti di misura, §1.3-1.4).

Il valore residuo di questo fronte è quindi di **parapetto e di metro**, in
quest'ordine: (a) adottare la regola same-SHA per p1; (b) accendere
`LLAMA_TRACE=1` in campagna e chiudere i tre falsificatori per-episodio;
(c) promuovere TOPK=1 a difetto del fork; (d) tenere i tap esatti (ogni
futura leva sul bersaglio va accompagnata dalla colonna p1 same-SHA prima di
attribuirle il Δt/s). I millisecondi veri del decode, a valle di questo
audit, restano dove RACCOLTA li ha già messi: il ciclo (fusioni #25585) e il
contorno del ciclo (checkpoint, audit 37 §5.1) — non la bozza.

---

## Dati che si ottengono solo eseguendo (in ordine di valore)

1. **`lungo_rb1` + `LLAMA_TRACE=1`** (una corsa): spezza p1 0,899 fra episodi
   post-riavvolgimento e ordinari (§1.3). Decide se il rollback ha un costo
   di qualità vero o solo ottico — e con lui la lettura di ogni A/B futuro
   che tocchi il recupero dal rigetto.
2. **`c5_c2` (AM=1 E=1, conf 0) + `LLAMA_TRACE=1` (+ spia AM già in albero)**:
   p1 condizionato alla distanza dall'ultima riga mascherata (§1.2). Decide
   se AcceptMoE ha un margine di riparazione (rigiocare esatte le righe
   accettate-mascherate) o se il danno è nella selezione.
3. **Un braccio n-max 5, conf 0, TOPK=1, banco attuale** (una corsa): la
   versione pulita della tabella §4.2 — condizionali per posizione senza
   diluizione e con la provenienza a posto. Non cambia decisioni oggi (fronte
   chiuso), fissa il numero per quando AcceptMoE/KV-ring riaprissero il blocco.
4. **Corsa DBG breve per il contatore `draft = X MiB`** del checkpoint
   (§2.4.3): 0.000 atteso; qualunque altro valore falsifica la sezione e
   riapre la contabilità dei checkpoint bozza.
5. **A/B della riga 2995** (`spec_prompt`) sul banco 100k del fronte
   contesto-lungo: unico punto dove il §2.4.1 può valere millisecondi.
