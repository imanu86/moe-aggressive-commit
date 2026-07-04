# Prune-per-sottrazione: analisi + esperimento

> Idea in esame: *"fine-tunare il modello sui domini che NON mi interessano (storia, geografia, prosa) per capire PER SOTTRAZIONE quali expert/pesi eliminare, dato che il mio dominio target è AMPIO ma esclude alcuni topic."*

Data: 2026-07-04 · Curatore ricerca (rigore-da-paper) · ancorato a `project_moe_reap_spex_closed` (I6, I10, E10) e a `HANDOFF_7`.

---

## Verdetto in 3 righe (l'idea funziona? quanto? cosa cambiare)

1. **Il segnale "misura cosa usano i domini non-voluti" è VALIDO e nuovo** rispetto al ledger (I6/I10 misurano solo frequenza *positiva* sul dominio target): è il controllo negativo `set-diff vs cold-globale` che la nota paper-grade chiedeva.
2. **Ma il payoff è modesto e cade rapidamente col dominio AMPIO**: più il target è ampio, più `non_usati_da_voluti → 0`, quindi l'insieme rimovibile "puro-unwanted" si restringe a una minoranza (ordine 10-30%, non il 50% che REAP-positivo già ottiene), e superare quel confine richiede FT/REAP che **riscrive il router** — cioè l'opposto di "identifica-e-rimuovi senza toccare il modello".
3. **Cambio da fare**: NON fare il FT-negativo (inutile per la misura e cambia il router che poi spedisci), e NON usare il segnale come taglio binario — usalo come **rapporto continuo `r = freq_unwanted/freq_wanted` che mappa la BIT-WIDTH** (temperature-per-expert quant). Questo è l'unico innesto che tocca i byte in VRAM ed è già il contributo-paper #5.

---

## Le 3 correzioni chiave

### 1. Perché NON serve il fine-tuning per misurare (anzi lo invalida)
Il router è una funzione **fissa** `h → top-k(gate(h))`. Per sapere "quali expert servono ai domini non-voluti" basta un **forward pass** su quei corpora e leggere gli indici di routing — zero backward, zero optimizer. Fare FT sul dominio non-voluto è peggio che inutile: il gate si sposta, quindi la mappa `expert→dominio` che misuri appartiene a un **modello diverso** da quello che poi quantizzi/spedisci. Misureresti il routing del modello sbagliato. Il no-FT non è una scorciatoia economica: è la **condizione di validità**.

Corollario sul framing dell'idea: "fine-tune sul non-voluto poi sottrai" è letteralmente la **task-vector negation** (Ilharco et al. 2022, arXiv:2212.04089). Ma quella tecnica rimuove **capacità**, non **memoria/parametri**: `θ_new = θ_pre − λ·τ` è element-wise, lascia invariati architettura, param-count, shape, dtype e **byte occupati**. Un 30B fp16 dopo negazione è ancora 30B fp16. Sul 3060/12GB non risparmia un solo byte. Errore di categoria: unlearning ≠ compression.

### 2. Perché il guadagno è modesto su un dominio AMPIO
Il set rimovibile è l'intersezione `usati_da_non_voluti ∩ non_usati_da_voluti`. Il collo di bottiglia è il **secondo termine**:

- I dati I6 mostrano che un solo prompt di dominio ristretto tocca già **100/128 expert** (union@99% = **81.8/128** su Qwen-30B). Cioè `non_usati_da_voluti` è **già piccolo** (~35-45% expert freddi) anche per un dominio STRETTO.
- Per un target AMPIO ("generale meno pochi topic"), `voluti ≈ quasi-tutto-il-modello` → `non_usati_da_voluti → 0` **per costruzione** → set rimovibile → 0.
- Peggio: la tabella pruning 2.2 dimostra che gli expert che il dominio non usa **non sono liberi** — reggono il *generale* (pruning dom-guidato keep50 fa esplodere `gen ppl` a 21.9x su 235B). Quindi `non_usati_da_voluti` è proprio l'insieme-salvagente: rimuoverlo perché "usato dai non-voluti" è esattamente ciò che il ledger mostra distruggere la capacità generale.

**La finestra dove la sottrazione è strettamente migliore è stretta**: si accende solo con dominio STRETTO, ed è lì che REAP-positivo già vince (keep50 = -50% expert, 99.3% massa, con healing).

### 3. Perché il payoff vero è modulare i bit, non tagliare
Sul regime memory-bound del 3060 (V4-Flash 158B/13B, expert fp4 streammati da RAM/SSD):

- **Prune binario a router intatto** ha un tetto ~5% (E10: 302/6144 expert a massa ~0). In GB sul working-set effettivo ≈ **zero**, perché ciò che streami per token è comunque la coda che il router visita.
- **Droppare è catastrofico** (H4/H5: fino a 59x ppl); **comprimere è quasi-lossless**. La compressione agisce su OGNI expert quindi su OGNI token, e **non toglie capacità** (i freddi restano, solo a meno bit).
- Quindi il segnale set-difference va usato come **continuo → bit-width**, non come maschera 0/1: un expert usato 10x più dai non-voluti crolla a int2; uno del dominio resta a int8/bf16; i borderline si degradano di *un livello* invece di essere uccisi.

Priorità footprint reale: **static-fp8 (attn+shared+embed ~7-9 GB) >> temp-quant expert >> prune binario (~0)**. Il collo sul 3060 è lo statico, non gli expert.

---

## Cosa dice la letteratura

### MoE: specializzazione per TOPIC vs per TOKEN
- **Mixtral / Switch (contro topic)**: *"Surprisingly, we do not observe obvious patterns in the assignment of experts based on the topic"* — routing quasi identico su ArXiv/PubMed/PhilPapers; ciò che il router cattura è **sintassi e posizione** (token consecutivi, indentazione, `self`/`Question`), non semantica.
- **DeepSeek-V3/R1, OLMoE (a favore, ma bounded)**: nei MoE fine-grained many-expert la specializzazione di dominio ESISTE (OLMoE Expert 43 = termini geografici; shared-expert drena il generale). Semantic routing confermato (arXiv:2502.10928) ma **solo >100B**; sotto è debole ed è su **vocabolario/output-token nei layer tardivi**, non su "topic astratto".
- **Riconciliazione**: dipende da granularità + aux-loss-free + shared-expert. La leva sfruttabile è per **dominio AMPIO** (code/math/reasoning), **non** per topic enciclopedico (storia/geografia). Non esiste un mapping pulito "questo expert = storia" da sottrarre a mano — *illusione dell'etichetta topic*.
- **Prior-art diretto pruning**: EASY-EP (arXiv:2504.06792) — top-16 expert disgiunti tra dataset, ma la coda è condivisa; ~50% prunabile con calibrazione, >75% degrada. REAP conferma 50% near-lossless su code. La sottrazione è una **variante di expert-pruning informato**, non un meccanismo nuovo.

### Task arithmetic: memoria vs capacità
La negazione (Ilharco 2022) è editing di **comportamento**. Riduce footprint **solo** se accoppiata a ciò che tocca struttura/precisione: **pruning strutturato** (arXiv:2403.01267; REAP per MoE), **quantizzazione** (fp16→Q4 = ~4x), **distillazione**. La negazione da sola: zero byte. L'unico angolo non-ridondante è usarla come **pre-condizionamento** (spingere a zero i pesi del dominio da scartare prima di REAP) — ma è il pruning/quant a fare il lavoro sui byte, e λ va tarato o degrada anche il target (weight entanglement).

---

## Cosa dicono GIÀ i dati dell'utente e cosa aggiunge la sottrazione

| | Cosa misura | Numeri chiave | Limite vs sottrazione |
|---|---|---|---|
| **I6** (`expert_union_coverage.py`) | union/coverage **positiva** del dominio | 1 prompt tocca 100/128; union@99% = 81.8/128; DS2-Lite 58.8/64 | è solo `voluti`; il complemento (`non_usati_da_voluti`) è già ~35-45%, →0 su target ampio |
| **I10** (`reap_union_sim.py`) | saliency-mass REAP **positiva** + reroute | keep50: reroute 8.2%, mass 99.3%, union 40→20 GB; keep25: 30% / 93.5% / 10 GB (entra); keep12.5: 49.6% / 82.9% | quantifica già il set rimovibile via frequenza positiva; una sottrazione deve **battere** questo per giustificarsi |
| **E10** (`reap_saliency.py`) | expert cold-a-zero | 302/6144 (~4.9%) | tetto del prune binario a router intatto |

**Cosa aggiunge davvero la sottrazione**: il termine `usati_da_non_voluti` **non è mai stato dumpato** con quello scopo. Le trace multi-workload esistenti (`code/reasoning/english/mmlu/general`) sono un **proxy** disponibile ma non sono state usate come "anti-domini". Novità reale **solo se**: (1) porti trace REALI dei domini-da-escludere, e (2) dimostri che l'intersezione batte il keep-ratio di REAP-positivo **a pari qualità post-healing**. Predizione onesta dai loro numeri: per target AMPIO aggiunge ~nulla; per target STRETTO è dominata da REAP-50 già near-lossless. Il valore residuo è come **controllo negativo** e come **sorgente del rapporto `r` per la quant continua**.

---

## L'esperimento economico decisivo (runnable, senza FT)

Costo: **1 caricamento modello + N forward pass** (~mezza giornata GPU, nessun backward). Riusa la toolchain trace esistente.

**Passo 1 — Corpora bilanciati per-token.**
`WANTED` = mix AMPIO del dominio (bonus/fiscale/normativo IT: query+prosa+tabelle+FAQ), ~300 passaggi — **non** solo `raft_eval.jsonl` (misureresti overfit al formato). `UNWANTED` = 3 corpora ORTOGONALI e disgiunti: storia, geografia, prosa/narrativa (wiki per categoria via template `build_general_en.py`). Target ~120k token/corpus. **Regola d'oro: normalizza a pari NUMERO DI TOKEN** tra wanted e unwanted, altrimenti il rapporto misura la dimensione del corpus, non il dominio.

**Passo 2 — Dump routing (solo forward).**
Con `dump_traces_multi.py` registra `experts[T,L,k]` per ogni corpus. Per ogni `(l,e)`: `freq_c[l,e] = bincount(e[:,l,:]) / T` (normalizza per **T token**, non T·k, e sii coerente tra corpora). Salva `freq[C,L,E]` + copertura (`touched`). Solo indici di routing (int16), nessun peso.

**Passo 3 — Metrica set-difference + rapporto continuo.**
`freq_wanted` = corpus dominio; `freq_unwanted` = **MAX** sui 3 corpora (conservativo: un expert che serve molto anche a un solo unwanted non è "puro-unwanted"). Due quantità: (a) rimovibile se `freq_unwanted > τ_hi AND freq_wanted < τ_lo`; (b) **rapporto** `r[l,e] = (freq_unwanted+ε)/(freq_wanted+ε)`. Soglie **data-driven per-layer**: `τ_lo` = p10 di `freq_wanted`, `τ_hi` = p50 di `freq_unwanted`. Il **k emerge dai dati**, non è fisso al 50%. Nuovo script `scripts_pod/setdiff_freq.py` che consuma i `traces_*.npz`.

**Passo 4 — Gate anti-illusione (3 check obbligatori).**
(1) `|set rimovibile|` totale e per-layer — se ~0, la separazione non esiste (**verdetto negativo onesto, da riportare**). (2) `coverage_lost` sul WANTED **pesata per massa** deve essere <1-2%. (3) **Controllo negativo paper-grade**: set-diff vs (i) RANDOM stesso k, (ii) **cold-globale** (bottom-k per `freq_wanted` ignorando unwanted). Se set-diff non batte cold-globale, il segnale "unwanted" non aggiunge nulla oltre "freddo". In `mixed_precision_eval.py`: droppa/quantizza i set e misura `ppl_domain` vs `ppl_general` — set-diff deve dare il miglior trade-off (degradazione concentrata sui domini unwanted). **Doppia versione frequenza vs saliency** (`reap_saliency.py`): se il ranking cambia molto, la metrica frequency-only è fragile e va dichiarato.

**Passo 5 — Innesto quant continua (il salto oltre il binario).**
Estendi `mixed_precision_eval.py` da bottom-k-fisso a **bit-width-per-expert** derivata da `r`: `bits(e) = clip(round(base_bits − α·log(r[l,e])), 2, 8)`. Metrica finale: `ppl_domain` (~1.00x del full) vs **bytes totali (VRAM)**, con 4° corpus **HOLDOUT generale-misto** mai usato per costruire il set (deve degradare **gradualmente**, non a scalino). Aggiungi la riga a `EXPERIMENTS_LEDGER.md`.

**Rischi da tenere in nota**: frequenza≠salienza (expert jolly ad alto conteggio, basso contributo `g·||f||`); i 3 unwanted devono attivare set parzialmente diversi (Jaccard sui caldi <0.7, altrimenti stai testando 1 dominio); se l'uso reale tocca occasionalmente storia/citazioni, degradi quelle → l'holdout lo cattura; soglie per-percentile instabili sui primi/ultimi layer (riporta per-layer: atteso concentrato nei layer centrali).

---

## Come si innesta nel paper

Il framing corretto **non è "prune per sottrazione"** ma **"temperature-per-expert quant col rapporto unwanted/wanted"** — che è già il **contributo #5** (bit-width per frequenza-routing, ortogonale all'imatrix; PAPER_STATE, HANDOFF_7 roadmap #3). La sottrazione fornisce il **secondo segnale** (`freq_unwanted`) che trasforma il "freddo globale" di REAP-50 in "freddo SOLO per ciò che vuoi, caldo per ciò che NON vuoi" — segnale strettamente più informativo, ed è **esattamente il controllo negativo mancante** che la nota paper-grade richiede.

Componibilità: **ortogonale a SPEX** (SPEX predice il LOADING a runtime; questo decide la BIT-WIDTH statica offline) → comprimi i solo-unwanted **E** prefetchi i caldi. File da toccare: nuovo `scripts_pod/setdiff_freq.py`, estensione `scripts_pod/mixed_precision_eval.py`, template `build_general_en.py` per i 3 unwanted, riga in `docs/EXPERIMENTS_LEDGER.md`.

**Onestà finale**: se il Passo 4 mostra che set-diff non batte cold-globale (probabile su dominio molto ampio), il risultato **è comunque pubblicabile** come controllo negativo pulito — chiude la domanda "la sottrazione topic-based aggiunge oltre la saliency?" con un numero, invece di lasciarla aperta.
