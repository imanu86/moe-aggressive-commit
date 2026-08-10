# 47 — OGNI DEFAULT DEL BINARIO, E QUALI CI DANNEGGIANO

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap` (HEAD `24fd5c2ee`).
**Niente compilato, niente eseguito, nessun server toccato** — la macchina misura.
Strumenti: lettura di `common/common.h` (la struct dei 338 default), `common/arg.cpp`
(nomi e consumo), censimento di **tutti** i `getenv` in `src` + `ggml/src` + `common`
+ `tools` (45 leve nostre + ~25 della base vive su questa build), `build/CMakeCache.txt`,
e la riga di comando + le 30 variabili di `D:\ds4_work\llama_run\cancelli_fasi.ps1`.
Marcature: [MISURATO] = letto nel sorgente/log/cache di build, [DEDOTTO] = aritmetica
o lettura del codice, [IPOTESI] = da falsificare, [RIFERITO] = numeri del mandato.
Perimetro: **non ripeto audit/31** (FA attiva, warmup, repack, op-offload, prompt-cache,
slot save/restore, conf-min, -dio, -tb, --mlock): dove serve, punto la riga di 31.

---

## LA RISPOSTA, E DOVE LA DOMANDA ERA MAL POSTA

Hai chiesto: "quale default della BASE è sbagliato per un MoE da 284G a 2,44 bit su
12 GB?". Il censimento risponde, ma ribalta il baricentro — e il mandato stesso lo
suggeriva senza dirlo: **dei tre colpi delle ultime 24 ore, due erano default NOSTRI**
(`W=2` è in `src/models/deepseek4.cpp:1378`, scritto da noi; `-ub 64` era la nostra
abitudine, l'upstream ha 512 da sempre — `common/common.h:457`). Solo `-cms 8192` era
della base.

Il quadro dei numeri:
- **338 argomenti upstream**: ~250 sono morti per noi per costruzione (multi-GPU,
  campionamento che il banco fissa, embeddings, multimodale, finetune, perplexity).
  I vivi e non ancora a verbale sono **sette** (prima fila sotto); il resto era già
  in audit/31.
- **45 leve `getenv` nostre**: il difetto di OGNUNA è "il comportamento di ieri",
  per igiene di porto. Giusto per i cancelli SHA, ma ha una conseguenza mai scritta:
  **la configurazione SOTA non esiste nel binario — esiste solo nello script.** Ogni
  riga dimenticata è una regressione muta, senza errore. E in TRE casi il default
  nostro è un ramo che il NOSTRO stesso sorgente misura come perdente (W=2: −25,6%;
  orologio invece di LRU; top-k 10 sulla bozza).
- **Gli accesi-non-dichiarati**: ne aggiungo cinque a quelli di ieri, e uno ha già
  lo strumento di misura montato e mai acceso (il cronometro dei checkpoint).

La domanda giusta quindi non è solo "quale valore è giusto", ma **"quale meccanismo
garantisce che un valore vinto non si perda"**. Oggi il meccanismo è la memoria di chi
scrive lo script. La proposta concreta è in fondo (manifesto di lancio + promozione
a default dei valori che hanno passato i cancelli).

---

## PARTE I — LA CLASSIFICA DEL DANNO ATTESO

Danno atteso = probabilità che il default morda (lancio nudo, script nuovo, braccio
dimenticato) × grandezza quando morde. Le prime otto voci hanno una scheda; il resto
è in tabella.

### 1. `LLAMA_CACHE_ESPERTI_W` — difetto **2**, e il sorgente stesso lo misura al −25,6%

- **Dove**: `src/models/deepseek4.cpp:1378` (`atoi(v) : 2`, clamp 0..8).
- **Cosa fa**: profondità del predittore di route — a W>0 il grafo espande i nodi
  `cache_pf-<strato>-<n>` che il backend CUDA intercetta e trasforma in prefetch/
  promozioni della cache esperti (deepseek4.cpp:1331-1409).
- **Perché il default è di un altro caso**: fu scritto quando il predittore sembrava
  la leva. La misura del 5/8 è NEL SORGENTE, `ggml/src/ggml-cuda/cache-esperti.cuh:32-34`:
  `W=0 → 9,26 t/s (VINCE); W=1 → 7,90; W=2 → 6,89` — il default sceglie il ramo che
  perde 37,2 ms/token, **−25,6%** [MISURATO nel commento, tabella in
  `D:\ds4_work\llama_run\cache_esperti.txt`].
- **Cosa dovrebbe valere da noi**: **0**. Nota il paradosso già codificato: il
  FORK/JOIN *pretende* `W=0 esplicito* e a W assente si RIFIUTA di partire
  (cache-esperti.cu:1008-1015) — cioè il codice nuovo già non si fida del default
  del codice vecchio.
- **Cancello**: nessuna ricompilazione per difendersi (W=0 nello script c'è già);
  la CURA vera è una riga — default 2→0 in deepseek4.cpp:1378 — e il cancello è lo
  SHA a spec off e K=0 che deve restare `33D76723EB8D` (W tocca solo residenza, non
  valori: bit-identico atteso a cache spenta; a cache accesa vale il metro 13,19-13,23).

### 2. `LLAMA_SPEC_DRAFT_TOPK` — difetto **10**: il metro si rompe da solo

- **Dove**: `common/speculative.cpp:998-1001` (`atoi(v) : 10`).
- **Cosa fa**: campionatore della bozza (`top_k=10` + `dist`, seme casuale). A 10 il
  token proposto è un'estrazione fra i primi dieci, diversa a ogni corsa; ed esiste
  la seconda incoerenza scritta nel commento: la catena Markov si propaga con
  l'argmax interno (`dflash.cpp:300`) e NON col token emesso — a top-k 1 le due cose
  tornano a coincidere (speculative.cpp:987-997).
- **Perché il default è di un altro caso**: "il default resta 10 per non cambiare il
  metro sotto i piedi" (commento a :996). Legittimo il 9/8 mattina; ma il metro È
  cambiato: tutti i cancelli dal 9/8 sera girano a TOPK=1 (tre corse, un solo SHA,
  rumore da ±4% a ±1,6%). Oggi il default protegge un metro che non usiamo più e
  rompe quello che usiamo.
- **Cosa dovrebbe valere da noi**: **1**.
- **Cancello**: già passato tre volte (SHA unico su tre corse). La promozione a
  default va dichiarata nel ledger come cambio di stirpe del metro.

### 3. `-cms 8192` (`checkpoint_min_step`, base) — colpito ieri; il RESIDUO è la taglia × il numero

- **Dove**: `common/common.h:629` (`checkpoint_min_step = 8192`), flag
  `-cms/--checkpoint-min-step` (arg.cpp:1493-1501); consumato in
  `tools/server/server-context.cpp:3568` (spezza il batch ai confini dei messaggi
  utente solo se `pos > ultimo_checkpoint + min_step`) e `:3654` (crea solo se oltre
  il passo, salvo primo checkpoint e ultimo messaggio utente).
- **Perché il default è di un altro caso**: 8192 è pensato per contesti da 32-128k
  su modelli che sanno shiftare, dove il checkpoint è un'assicurazione rara. Il
  DSV4 **non sa rimuovere una coda arbitraria** (`llama-kv-cache-dsv4.cpp:1646-1671`:
  `seq_rm` con `p0>0` → `false`; la sonda `common_context_can_seq_rm` risponde FULL)
  → fra un turno e l'altro il checkpoint è **l'unica** via di riuso: con passo 8192 e
  turni corti, i punti di ripartenza utili non esistono. Ri-prefill 288 s → 2,7 s a
  passo 32, fattore 108; col default il secondo turno moriva con un 500 [RIFERITO].
  Il meccanismo del 500 non è stato autopsiato qui; il codice offre la strada:
  divergenza del prompt renderizzato (il turno nuovo droppa il reasoning del turno
  prima) → serve una rimozione parziale che seq_rm rifiuta → `common_context_seq_rm`
  fa `GGML_ABORT` (`common/common.cpp:1523-1526`) [DEDOTTO].
- **Il residuo, in due pezzi**:
  (a) **`-ctxcp 32` × taglia**: ogni checkpoint di contesto pesa ~14,3 MiB a c=10240
  [MISURATO log, audit/31] e la taglia è ∝ capienza (difetto pre-#25325): 32 × 14 ≈
  450 MiB di RAM oggi, innocuo; a `-c 105k` ~850 MiB l'uno → **~27 GB di RAM solo di
  checkpoint** [DEDOTTO]. Sul fronte lungo `-ctxcp` va abbassato (4-8) o il pick
  #25325 portato.
  (b) **`LLAMA_KV_POSMIN_VERO` difetto 0** (`server-context.cpp:976-980`, audit/39):
  spento, il riuso fra turni passa SOLO dai checkpoint; acceso, le code corte si
  riavvolgono sul posto via `seq_rm_tail`. È il compagno strutturale di -cms 32,
  mai acceso in produzione.
- **Cancello**: il multi-turno con -cms 32 è già misurato; per (a) basta il grep dei
  `size = … MiB` nel log a contesto lungo; per (b) una corsa due-turni con
  `LLAMA_KV_POSMIN_VERO=1` confrontando latenza del secondo turno e coerenza (il
  cancello duro dell'audit 39).

### 4. Il salvataggio speculativo avviene a OGNI episodio con bozza — e il cronometro è montato, mai acceso

- **Dove**: `tools/server/server-context.cpp:3036-3074`. Per il DSV4
  `ctx_tgt_seq_rm_type == FULL` sempre (DEEPSEEK4 non è in
  `llm_arch_supports_rs_rollback`, `llama-arch.cpp:973-981` → `n_rs_seq` clampato a 0,
  `llama-context.cpp:137-142`) → `use_ckpt_tgt` è **vero a ogni episodio**:
  `update_tgt` copia ~11,7 MiB verso l'host in ~124 letture di tensore, ~599 volte
  per 1.200 token [MISURATO nel commento :3044-3049].
- **Attenzione alla trappola di lettura**: `LLAMA_KV_ROLLBACK_PARZIALE=1` (nello
  script) evita il **restore+replay** sulla bozza rifiutata (13,2% dei cicli a
  n-max 1, `server-context.cpp:3993-4018`), **NON il salvataggio**: quello non ha
  leva e gira sempre. Se costa ~8 ms è l'8% del ciclo e il tetto si sposta da 13,2
  a 14,3 [DEDOTTO nel commento].
- **Perché il default è di un altro caso**: per un target che sa riavvolgere
  (`RS`/`PART`) il salvataggio scatta solo quando la bozza supera il margine; per
  il nostro FULL scatta sempre. Il costo è dimensionato su KV piccoli; il nostro
  stato per-episodio è grande perché la capienza è grande.
- **Cosa dovrebbe valere da noi**: prima il NUMERO, poi il disegno (salvare pigro,
  o solo quando `seq_rm_tail` non può servire — ma oggi il salvataggio è la rete
  di sicurezza del ripiego, non si spegne per decreto).
- **Cancello**: **`LLAMA_CKPT_CRONO=1`, una corsa, zero rischio** — stampa media
  cumulativa ogni 200 salvataggi (:3061-3068). È lo strumento più economico
  dell'intero audit e non è mai stato acceso.

### 5. La famiglia `-ub`: l'upstream aveva ragione (512), e il compagno dimenticato è la BOZZA

- **Dove**: `common/common.h:457` (`n_ubatch = 512`); il nostro 64 era l'abitudine
  da VRAM, non un default della base [RIFERITO: 22,6 → 72,9 t/s, ×3,2]. La leva a
  fasi ha già il suo difetto GIUSTO e motivato nel sorgente:
  `LLAMA_VRAM_A_FASI_UB=64` con la misura che lo difende (ub 64 → 13,21 contro
  ub 2 → 12,88, `llama-context.cpp:2121-2131`) [MISURATO nel commento].
- **Il residuo**: `--spec-draft-ubatch-size 16` (difetto upstream: eredita il
  target, `common.h:329`, arg.cpp:3738-3745). Il 16 fu fissato quando il target
  era a 64 (e a 100k serviva `ub 16`); ora il target al prefill è a 512 e la bozza
  incassa ancora l'iniezione delle feature a fette di 16
  (`common/speculative.cpp:1072-1087`). **Interazione da dichiarare**: 16 < 32 =
  `GGML_OP_OFFLOAD_MIN_BATCH` (ggml-cuda.cu:6137) → gli exps CPU della bozza non
  vengono MAI spediti alla GPU nel suo prefill; alzando l'ubatch bozza sopra 32
  cambia il PIAZZAMENTO, non solo la fetta — i due bracci vanno separati
  (`--no-op-offload` per isolare).
- **Cancello**: una corsa senza il flag (eredita 512) o a 64, guardando prefill t/s
  e VRAM; poi una a ubatch ≥32 con e senza `--no-op-offload`.

### 6. `LLAMA_CACHE_ESPERTI_LRU` — difetto **0 = orologio**, e l'orologio perde a ogni capienza

- **Dove**: `ggml/src/ggml-cuda/cache-esperti.cu:852-855` (`v && atoi(v) != 0`,
  quindi assente = orologio). Per la BOZZA il codice forza `lru = 1` (:829) — il
  default penalizza solo il bersaglio.
- **Perché è di un altro caso**: l'orologio era la politica di partenza; la
  campagna capienze ha dato LRU sopra l'orologio a OGNI capienza (380 slot:
  45,2% contro 33,5% di colpi) [MISURATO, ledger 8/8].
- **Cosa dovrebbe valere da noi**: **1**, promosso a default (una riga; lo stesso
  file già lo fa per la bozza).
- **Cancello**: metro 13,19-13,23 invariato con LRU=1 esplicito (è la produzione
  di oggi); il braccio orologio resta raggiungibile con LRU=0.

### 7. Prompt-cache RAM 8 GiB + `cache_idle_slots`: finora dormiva, il multi-turno la SVEGLIA

- **Dove**: `common/common.h:627,630` (`cache_idle_slots = true`,
  `cache_ram_mib = 8192`); `server-context.cpp:1412-1424`.
- **Il punto nuovo rispetto a 31**: finora "mai lavorato davvero" perché ogni corsa
  aveva un prompt solo. Con -cms 32 il flusso multi-turno È il flusso, e a ogni
  task nuovo lo slot idle viene serializzato nella cache RAM ("idle slots will be
  saved to prompt cache upon starting a new task"): copia dello stato ~80 MiB a
  c=10k, per turno [DEDOTTO dalle taglie dei checkpoint]. Costo nel regime nuovo:
  mai misurato. In più è un consumo di RAM fino a 8 GiB in una macchina che tiene
  74,3 GiB di esperti bloccati + il resto: il headroom non è più quello di prima.
- **Cancello**: banco due-turni A/B con `--cache-ram 0` (una corsa; la differenza
  del secondo turno è tutta lì). Se serve la cache, dimensionarla (es. 512 MiB),
  non lasciarla a 8 GiB.

### 8. La SOTA vive SOLO nello script: 14 leve accese a mano, zero nel binario

`LLAMA_KV_RING=1, MAPPED_IBRIDO=1, CACHE_ESPERTI_SLOT=339, LRU=1, W=0,
OVERLAP_ASYNC=1, OVERLAP_K=2, OVERLAP_BATCH_MAX=2, SPEC_DRAFT_TOPK=1,
DSV4_HC_FUSO=5, ROLLBACK_PARZIALE=1, BOZZA_SLOT=32, BATTITO=45, VRAM_A_FASI=1|0`
— ogni difetto è 0/spento [MISURATO, censimento in Parte III]. Igiene di porto
voluta e giusta per i cancelli; il prezzo è che **il binario nudo è upstream** e
una riga persa non produce un errore ma un numero sbagliato che sembra vero.
- **Cura proposta (piccola, una volta sola)**: un **manifesto di lancio** — il
  server stampa all'avvio le ~45 leve nostre con valore e sorgente (env/difetto),
  una riga greppabile che finisce nel ledger di ogni corsa. In attesa della patch:
  dump di `Get-ChildItem env:LLAMA_*,env:GGML_*` nello script PRIMA del lancio,
  accanto allo SHA del binario.
- **Complemento**: promozione a default dei valori che hanno passato i cancelli
  (W=0, LRU=1, TOPK=1 — le tre righe sopra) così il danno residuo di una riga
  persa scende di categoria.

### Tabella riassuntiva (voci 9-19, ordinate per danno atteso)

| # | Default | Dove | Cosa fa da noi | Verdetto / cancello |
|---|---|---|---|---|
| 9 | `LLAMA_OVERLAP_SPIN` = 2.000.000 | ggml-backend.cpp:855-865 | il worker overlap fa attesa ATTIVA ~1-2 ms per strato prima di parcheggiarsi: un core bruciato a spin in ogni corsa con ASYNC=1, mai a verbale | una corsa `SPIN=0` (il sorgente stesso la prevede "per misurare quanto vale lo spin") |
| 10 | `LLAMA_CACHE_ESPERTI_PF_TUTTI` = acceso | ggml-cuda.cu:4648-4651 | il prefetch a domanda legge TUTTE le posizioni del tensore di route (fix 8/8) — in produzione da allora, **mai misurato in isolamento** | A/B gratis con `=0` (comportamento vecchio) |
| 11 | `-lv 4` (nostra abitudine, difetto base 3) | arg.cpp:3533-3540 | trace su OGNI riga: formatting + I/O su file a ogni token; costo mai misurato; MA i cancelli greppano righe trace | una corsa a `-lv 3`: prima verificare che `eval time`/`draft acceptance` sopravvivano al livello, o il cancello resta cieco |
| 12 | `--poll 50` | common.h:72 | **INERTE su questa build**: il threadpool con poll esiste solo `#ifndef GGML_USE_OPENMP` (ggml-cpu.c:3134-3171) e la build ha `GGML_OPENMP=ON` [MISURATO CMakeCache]. Correzione ad audit/31 riga 10: `--poll` non è una leva qui; `--prio` invece arriva (applicato nel ramo OpenMP, :3391) | niente braccio --poll; per l'attesa usare GGML_SCHED_PROFILO=1 |
| 13 | `KMP_BLOCKTIME=200` auto-impostata | ggml-cpu.c:3857-3865 | ggml la setta per tenere svegli i thread 200 ms, ma il runtime OpenMP di MSVC (vcomp) non legge KMP_* → l'intento è MUTO su Windows/MSVC; i thread parcheggiano come decide vcomp e la protesi vera è il nostro OVERLAP_SPIN | [DEDOTTO]; nessuna azione, ma a verbale: "i thread restano caldi" NON è garantito dal binario |
| 14 | `-t` difetto = 8 (tutti i core fisici) | common.cpp:203-297 | il difetto prenderebbe anche il core che alimenta la GPU; il nostro 7 è deliberato e va protetto | già coperto dallo script; `-tb 8` per il solo prefill resta il braccio di 31 r.8 |
| 15 | Spec upstream: `n_max 3, p_min 0, conf_min 0, backend_sampling true` | common.h:327-336 | n_max 3 riaprirebbe il gradino della terza posizione (colpi 55,4%→23,6%); backend_sampling è vero ma il ramo DSpark non lo consuma (31) | il nostro `--spec-draft-n-max 1` è la difesa; conf_min resta la leva 31 r.3 |
| 16 | `-to 3600` (timeout HTTP r/w) | common.h:621-622 | al fronte 105k il prefill supera l'ora: alzarlo insieme al timeout client quando il fronte apre | riga nello script del fronte lungo |
| 17 | `seed` casuale + catena samplers default | common.h:222-268 | inerte SUL BANCO (temp=0 → greedy); diventa variabile viva se un banco futuro alza temp | dichiarare nel ledger del banco |
| 18 | 133 `LLAMA_ARG_*` | arg.cpp | ogni flag ha l'equivalente env: una variabile dimenticata nell'ambiente SCAVALCA il default in silenzio (priorità: CLI > env > difetto) | igiene: il manifesto di lancio copre anche questo |
| 19 | Costanti compilate: `GGML_CACHE_ESPERTI_TOK_MAX 32`, `ANELLO_N 256`, `CACHE_ESPERTI_STRATI_MAX 128`, fasi `SLOT_MAX 1024`, margine rollback 4 | cache-esperti.cu:43-67, kv-dsv4:50-54 | capienze fisse dimensionate sul regime attuale; la regola viva è margine ≥ n-max (oggi 4 ≥ 1) | nessuna azione finché n-max resta ≤4 |

---

## PARTE II — ACCESO SENZA CHE LO SAPPIAMO (nuovi, oltre i tre di ieri)

I tre di ieri (FA sul target, prompt-cache 8 GiB, 32 checkpoint) sono in audit/31
con i loro cancelli. Questi sono i NUOVI, dal censimento di oggi:

1. **Il salvataggio speculativo per-episodio** (scheda 4): ~599 × 11,7 MiB per 1.200
   token, sempre, senza leva di spegnimento. Strumento pronto: `LLAMA_CKPT_CRONO=1`.
2. **L'attesa attiva del worker overlap** (riga 9): ~1-2 ms × strato di spin su un
   core, in ogni corsa di produzione (ASYNC=1). Dichiararla nel modello di costo del
   battito (45 ms).
3. **`LLAMA_CACHE_ESPERTI_PF_TUTTI`** (riga 10): il fix del prefetch dell'8/8 è
   VIVO in ogni corsa da allora — la memoria di progetto lo dà "corretto, non
   ancora misurato". I numeri di produzione attuali lo CONTENGONO già.
4. **La prompt-cache che ora lavora** (scheda 7): il multi-turno l'ha svegliata;
   il suo costo per-turno non è in nessun ledger.
5. **Il riuso del grafo** (`LLAMA_GRAPH_REUSE_DISABLE` assente = riuso ATTIVO,
   llama-context.cpp:322-328) e i **CUDA graph** (`GGML_CUDA_GRAPHS=ON` in build,
   niente env di spegnimento nello script): sono i due presupposti del regime
   13,23 — vanno bene, ma sono anche la famiglia del replay stantio (audit/11):
   ogni braccio con forme nuove deve dichiararli.
6. In negativo — cose che CREDIAMO accese e non lo sono: `--poll` (riga 12),
   `KMP_BLOCKTIME` (riga 13), e `GGML_CUDA_GRAPH_OPT=0` nello script è ridondante
   (il difetto è già spento, ggml-cuda.cu:4948-4951 — bene così, esplicito).

---

## PARTE III — CENSIMENTO COMPLETO DELLE LEVE NOSTRE (difetto ↔ script)

Fonte: grep `getenv` sull'albero intero, 10/8. "Script" = `cancelli_fasi.ps1`.
Legenda stato: ✓ = impostata uguale al difetto (ridondante ma protettiva — BENE),
**≠** = impostata diversa dal difetto (riga portante), ∅ = assente, vale il difetto.

**Portanti (≠): se una manca, il numero cambia e nessuno avvisa**

| Leva | Difetto | Script | Dove |
|---|---|---|---|
| `LLAMA_MAPPED_IBRIDO` | 0 | **1** | ggml-cuda.cu:1435-1439 |
| `LLAMA_CACHE_ESPERTI_SLOT` | 0 (cache spenta) | **339** | cache-esperti.cu:198-201 |
| `LLAMA_CACHE_ESPERTI_W` | **2 (ramo −25,6%)** | **0** | deepseek4.cpp:1376-1380 |
| `LLAMA_CACHE_ESPERTI_LRU` | **0 = orologio (perde)** | **1** | cache-esperti.cu:852-855 |
| `LLAMA_CACHE_ESPERTI_BATTITO` | 60 s | **45** | cache-esperti.cu:234-236 |
| `LLAMA_CACHE_BOZZA_SLOT` | 0 (bozza senza cache) | **32** | cache-esperti.cu:199 |
| `LLAMA_SPEC_DRAFT_TOPK` | **10 (metro rotto)** | **1** | speculative.cpp:998-1001 |
| `LLAMA_DSV4_HC_FUSO` | 0 (catena non fusa) | **5** (comb+post) | llama-context.cpp:299-306 |
| `LLAMA_OVERLAP_ASYNC` | 0 | **1** | ggml-backend.cpp:1794-1800 |
| `LLAMA_OVERLAP_K` | 0 | **2** (atof: ammette frazionari) | llama-graph.cpp:1823-1828 |
| `LLAMA_OVERLAP_BATCH_MAX` | 1 (guardia replay) | **2** | llama-graph.cpp:1847-1851 |
| `LLAMA_KV_RING` | 0 | **1** | kv-ring.cu:114-117 e altri 3 punti |
| `LLAMA_KV_ROLLBACK_PARZIALE` | 0 (restore+replay al 13,2% dei cicli) | **1** | llama-kv-cache-dsv4.cpp:58-61 |
| `LLAMA_VRAM_A_FASI` / `_CALDO` | 0 / 0 | braccio | llama-context.cpp:2106-2141 |

**Ridondanti-protettive (✓)**: `CURA=0, SCUDO=0, MASSA=0, PREFETCH_FILTRO=0,
CODA_MAX=0, BATCH=8 (=difetto, cache-esperti.cu:222-227), FORK=0,
GRIGLIA_VARIABILE=0, ACCEPTMOE=0, CKPT_CRONO=0 (spegne il CRONOMETRO, non i
salvataggi!), ROLLBACK_SOLO_ANELLO=0, CONF_ESENTA_POS0=0, OVERLAP_PIN=1 (=difetto,
llama-context.cpp:1610-1613), MAPPED_IBRIDO_SOGLIA=2 (=difetto, ggml-cuda.cu:5463-5466),
KV_RING_VRAM_TOKEN=2048 (=difetto, kv-dsv4:187-191), GGML_CUDA_GRAPH_OPT=0 (=difetto)`.

**Assenti (∅) con difetto che AGISCE in silenzio**

| Leva | Difetto attivo | Nota |
|---|---|---|
| `LLAMA_OVERLAP_SPIN` | 2.000.000 giri | scheda 9 — mai a verbale |
| `LLAMA_CACHE_ESPERTI_SPIN` | 256 iterazioni | attesa in-kernel sui transiti (contatore `spin_esauriti` già esposto); [IPOTESI] costo ~0 |
| `LLAMA_CACHE_ESPERTI_PF_TUTTI` | acceso | scheda II.3 |
| `LLAMA_KV_ROLLBACK_MARGINE` | 4 righe (~290 KB/riga sul checkpoint) | regola: ≥ n-max; a n-max 1 abbonda |
| `LLAMA_KV_POSMIN_VERO` | 0 | il riuso fra turni resta sui checkpoint (audit/39) |
| `LLAMA_VRAM_A_FASI_UB` | 64 (misurato nel sorgente) | pulita apposta nello script: uso corretto del difetto |
| `LLAMA_VRAM_A_FASI_MIN` / `_SLOT` / `_MARGINE` / `_SLOT_MAX` | 0 / 0=auto / 0=auto / 1024 | auto documentati |
| `LLAMA_VRAM_ZAVORRA` | 0 | braccio di controllo, giusto spento |
| `LLAMA_ACCEPTMOE_ESATTE`/`_BATCH_MAX`/`_SOGLIA`/`_SPIA` | 1 / 8 / 0 / 0 | inerti con ACCEPTMOE=0 |
| `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI` | 32 | inerte con FORK=0 |
| `LLAMA_CACHE_BOZZA_BATTITO` | 60 s | la bozza batte a 60 mentre il bersaglio a 45: solo cadenza di stampa, cosmetico |
| `LLAMA_RING` / `_PROFONDITA` / `_BATTITO` | 0 / 380 / 60 | il ring esperti VECCHIO: spento, non confonderlo con KV_RING |
| `LLAMA_CACHE_ORACOLO` | vuoto = spento | prefetch da traccia su file |
| `LLAMA_REAP*` | spento (accensione SOLO con `"1"` esatto — lezione DwarfStar dei 70 getenv!=NULL, reap.cpp:43-48) | igiene da imitare |
| `DSPARK_PROF`, `DSPARK_NO_MARKOV`, `GGML_SCHED_PROFILO`, `LLAMA_OVERLAP_VERIFICA`, `*_DEBUG`, `*_TRACE` | spenti | diagnostica a chiamata |
| `LLAMA_DSV4_SINKHORN_ITERS` / `LLAMA_DFLASH_SINKHORN_ITERS` | dal GGUF | SONDA (uscita non valida se forzata): non è un default, è uno strumento |

---

## PARTE IV — LA BASE: argomenti, env, build (delta oltre audit/31)

**Argomenti upstream coi difetti che ci riguardano** (common.h:453-698):
`-c 0→ctx di training` (il binario nudo su DSV4 tenterebbe il contesto pieno: con
`--fit` attivo di default restringerebbe DA SOLO ngl/ctx — il nostro `--fit off` +
`-c 10000` esplicito è la coppia giusta e va SEMPRE insieme), `-b 2048` (ok),
`-ub 512` (scheda 5), `n_keep 0`, `ctx_shift OFF` (e comunque il DSV4 non sa
shiftare), `-t → 8 fisici` (riga 14), `-fa auto` (31), `--mmap ON` (noi no-mmap:
coerente col mapped nostro), `warmup ON` (31), `-ctxcp 32 / -cms 8192 / -cram 8192`
(schede 3 e 7), `cache_prompt ON + similarity 0,1` (31), `--jinja ON` +
`reasoning_format deepseek` + `--reasoning-budget -1` (il banco 1.200 token genera
in registro reasoning: è il CONTENUTO del metro, da dichiarare quando si confrontano
i colpi con banchi non-pensanti), `-to 3600` (riga 16), `--slots ON` (comodo, GET
di stato), `--metrics OFF`, `sleep_idle_seconds -1`, spec (riga 15), `-ngld -1 →
eredita` (noi 99 esplicito), `--spec-draft-ubatch-size → eredita target` (scheda 5).

**Env della base vive su questa build** — tutte già schedate in 31 §3 con verdetti
che il censimento di oggi CONFERMA, con una correzione e una aggiunta:
- Correzione: `GGML_OP_OFFLOAD_MIN_BATCH=32` non è solo "riga 6 di 31": incrocia
  l'ubatch della bozza (scheda 5) — i bracci vanno accoppiati.
- Aggiunta: `OMP_WAIT_POLICY`/`KMP_BLOCKTIME` (righe 12-13): su MSVC sono lettera
  morta; l'unico controllo reale sull'attesa CPU è il nostro OVERLAP_SPIN.

**Build (CMakeCache, [MISURATO])**: `Release, CUDA arch 86, GGML_OPENMP=ON,
GGML_CUDA_FA=ON, FA_ALL_QUANTS=OFF (vivo solo se mai si prova -ctk quantizzato),
GGML_CUDA_GRAPHS=ON, FORCE_MMQ/CUBLAS=OFF, NO_VMM=OFF, GGML_CPU_REPACK=ON,
SCHED_MAX_COPIES=4 (inerte: pipeline_parallel=false), LLAMA_KV_RING_VRAM_TRACE_BUILD=OFF
(la trace VRAM del ring NON è compilata: l'env relativa è morta su questo binario),
GGML_CUDA_NCCL=ON in cache ma single-GPU → inerte`. Niente margine ISA (Zen 3 al
tetto, 31 §4).

**Morti da non riproporre** (conferma 31): unified memory su WDDM, PDL (Hopper),
REGISTER_HOST (senza chiamanti), multi-GPU/-sm/-ts/--rpc, --numa, --cache-reuse e
context-shift (il DSV4 rifiuta il parziale per costruzione), AVX-512.

---

## PARTE V — I CANCELLI, IN ORDINE DI RESA (tutte corse singole, zero ricompilazioni)

1. **`LLAMA_CKPT_CRONO=1`** sulla configurazione di produzione: mette un numero sul
   costo per-token dei 599 salvataggi. Se ≥2 ms/ciclo, si apre il fronte disegno.
2. **`--cache-ram 0`** sul banco due-turni: il costo della prompt-cache nel regime
   multi-turno appena nato.
3. **`LLAMA_OVERLAP_SPIN=0`**: quanto compra l'attesa attiva (e quanto costa in
   contesa al ramo CPU che "toglie domande alla cache").
4. **`--spec-draft-ubatch-size` assente (eredita 512)** al prefill: il compagno
   dimenticato del ×3,2 — con l'avvertenza op-offload (soglia 32) dichiarata.
5. **`LLAMA_CACHE_ESPERTI_PF_TUTTI=0`** A/B: isola il fix dell'8/8 che è già in
   ogni numero di produzione.
6. **`LLAMA_KV_POSMIN_VERO=1`** sul banco due-turni: latenza secondo turno senza
   passare dai checkpoint (cancello duro coerenza = audit/39).
7. **`-lv 3`** (dopo aver verificato che le righe del metro sopravvivono): il costo
   del trace perenne.
8. Le promozioni a default (**W=0, LRU=1, TOPK=1** — tre righe, una ricompilazione
   sola quando il banco è libero): cancello = SHA `33D76723EB8D` a leva spenta +
   metro 13,19-13,23 invariato sulla produzione.

---

## CHIUSURA

Il pericolo non abita dove la domanda lo cercava. Dei 338 argomenti della base,
quelli vivi per noi si contano su due mani e ora hanno tutti un verbale; le tre
scoperte da −25%/×3,2/×108 erano due volte NOSTRE e una della base, e tutte e tre
avevano la stessa forma: un valore scritto per il caso di ieri, applicato in
silenzio al caso di oggi. Il censimento dice che di forme così ne restano: un
salvataggio da 11,7 MiB che gira 599 volte per risposta col cronometro montato e
mai acceso; una cache da 8 GiB che il multi-turno ha appena svegliato; un core che
gira a vuoto 1-2 ms per strato; e tre default nostri che il nostro stesso sorgente
misura come perdenti. Cinque corse da dieci minuti li mettono tutti a verbale. E
una patch da venti righe — il manifesto di lancio — trasforma "ricordarsi trenta
righe di script" in "leggere una riga di log", che è l'unico modo in cui questa
classe di difetti smette di rigenerarsi.
