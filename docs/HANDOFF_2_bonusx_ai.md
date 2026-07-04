# HANDOFF 2 — pivot: da ricerca MoE a sistema AI applicato BonusX (2026-07-01)

> Chat token-exhausted. Questo doc + i due allegati (`docs/piano_indice_ibrido_bonusx.md`,
> `docs/corso_ia_avanzato.md`) + la memory bastano per riprendere ESATTO in una chat nuova.
> Nessun codice del nuovo sistema è ancora scritto: qui c'è il piano + il workflow per farlo.

---

## 0. TL;DR (leggi questo per primo)
1. **Ricerca MoE (repo `moe-aggressive-commit`) = CHIUSA, negativo netto.** Predire-vs-reagire, osserva-poi-comprimi, engine-streaming: nessuno batte lo stato dell'arte, verificato su 3 modelli + sui prompt BonusX reali. Tutti i risultati in `runs/*.csv`. Prior-art che copre tutto: MC#, DynaExq, EASY-EP, MoE-Infinity.
2. **PIVOT deciso:** smettere di combattere la fisica del MoE; costruire un **sistema AI applicato** sugli asset unici dell'utente (2000+ promo etichettati, `recall`, infra, dati vision). È lì che ha un edge difendibile.
3. **Due filoni nuovi, complementari:**
   - **A) Retrieval ibrido** (BM25 + embedding) sulla KB BonusX → tool MCP `promo_recall` che il Qwen chiama per associare promo simili e richiamare concetti. **Piano completo in `docs/piano_indice_ibrido_bonusx.md`.**
   - **B) Fine-tuning (RAFT)** del Qwen a *ragionare* sui simili recuperati. Knowledge→retrieval, comportamento→fine-tuning (NON memorizzare i promo nei pesi).
4. **Win pratico già APPLICATO oggi:** config `llama-server` di produzione ottimizzata (`--cpu-moe`→`-ncmoe 28 -fa on -ctk/ctv q8_0 --no-mmap`), verificata LIVE (VRAM 4→10.5 GB, GPU ora sfruttata, ~36 tok/s decode). Vedi §4.

---

## 1. Cosa è successo (verdetto ricerca MoE — chiuso)
- **Predire il working-set (validate_probe)**: non batte la cache reattiva LRU su OLMoE/Qwen3/DS2. `runs/validate_probe_qwen3.csv`, `runs/validate_probe_dsv2.csv`.
- **Osserva-poi-comprimi**: niente coda comprimibile — un prompt usa ~tutti gli expert (routing denso). Su **BonusX reale (Qwen3-30B, prompt 3.7k-5.7k token) = 64/64 = 0% comprimibile**. `runs/coverage_*`, `runs/prefill_vs_decode.log` (prefill predice decode solo 0.42; hot-set globale 0.68 → statico basta).
- **Nuance:** più expert → frazione più bassa (Qwen3 128exp=66% vs DS2 64exp=95%), ma prompt lunghi saturano lo stesso. Frequency-skew esiste (top-25%≈65% massa) = leva DynaExq (già fatta).
- **Engine streaming**: funziona/lossless ma NON nuovo (llama.cpp `-ncmoe`, ktransformers, ds4 lo fanno già, spesso meglio). E l'utente lo faceva già via Q4+offload.
- **ds4/gigante**: NO-GO su 3060 (muro RAM, non BIOS; 32GB sotto floor). Cloud tradirebbe la tesi HW-basso. Scartato.
- **Pubblicabile**: i negativi puliti + l'engine come strumento. Non prioritario ora.

## 2. Il PIVOT (dove sta il valore)
La novità/valore non è battere l'inferenza-MoE generica (campo affollato, team enormi) ma **sfruttare gli asset dell'utente**: KB dominio + 2000 promo etichettati + `recall` + pipeline BonusX live. Direzione: **retrieval ibrido + fine-tuning applicato**, tutto sul suo HW/dati.

## 3. FILONE A — Indice ibrido (dettaglio in `docs/piano_indice_ibrido_bonusx.md`)
**Dati (mappati):** repo `C:\Users\imanu\source\repos\bonus-kb\bonusx-kb\` (243MB). ~**2.900-3.000 chunk**:
- ~1.472 **promo** (`examples/parsed.jsonl` 1448 v1 OCR + `examples/parsed_v2_vision.jsonl` 24 v2) — record strutturati (book, technique, validity, variance, cap_eur, `enriched.che_devo_fare_clean`…). + 1779 JPG.
- ~1.000 nodi **corpus** (`corpus/{4 corsi}/knowledge_corpus.json`: concepts/rules/games_db/QA).
- ~300 **sezioni lezione** (`lessons/*/summary.md`, 18 dispense) + `knowledge.json`.
- ~200 **glossario** (`corpus/*/glossary.md`, `corpus/_shared/domain-jargon.md`).
- KB reference: `kb/promo_targets.json` (49 book), `kb/techniques.yaml` (**10 famiglie** — vedi drift §6).

**Decisioni chiave (le leve di qualità):**
1. **Scala piccola (~3000) → NIENTE vector-DB.** Embeddings in UNA matrice (3000×768≈9MB, `.npy`); ricerca semantica = 1 moltiplicazione matrice-vettore, in-process. Resta lean come `recall`.
2. **Indice UNICO + facet `source_type`** (promo/concept/rule/game/lesson/glossary/book/technique).
3. **Filtri HARD sui campi strutturati** (`book=goldbet AND technique=CASHBACK AND variance=NESSUNA`) PRIMA del ranking = leva n°1.
4. **Embedda la narrativa PULITA** (`che_devo_fare_clean`), scarta l'OCR grezzo.
5. **Sinonimi da `domain-jargon.md`** (2_FASI≈due fasi, rollover≈wagering≈WG, fix ASR) in indicizzazione + query.
6. **Embedding su CPU** (non tocca VRAM Qwen): default `intfloat/multilingual-e5-base` (prefissi `query:`/`passage:`), via `sentence-transformers` o GGUF `llama-server --embedding`.
7. **Fusione RRF** BM25 + semantico. Esposto come tool MCP **`promo_recall(query, filters?, k?)`**.

**Riusa roba già fatta:** `recall` (`cgc-infra/src/recall-core.mjs`, BM25 + tokenizer che spacca sigle), `bonusx-kb/scripts/retrieve_similar.py` (cosine, base da estendere), `domain-jargon.md`.

## 4. Win pratico llama.cpp (FATTO oggi, verificato)
- File: `C:\Users\imanu\llama\.env.local_runner` riga 11 `LLAMA_CMD`. Cambiato `--cpu-moe -c 16384` → `-ncmoe 28 -fa on -ctk q8_0 -ctv q8_0 --no-mmap -c 16384`. Backup: `.env.local_runner.bak_ncmoe28`.
- **Root cause del "non si applicava":** i loader usano `os.environ.setdefault` → un `ia_control_server.py` vecchio (PID 15636, dal 24/06) teneva `--cpu-moe` congelato in `os.environ` e lo propagava ai figli. **Fix:** killare la RADICE (15636 con `/T`), rilanciare da shell pulita. Verificato live: nuovo server con `-ncmoe 28`, VRAM ~10.5GB (era ~4), GPU sfruttata.
- **Hardening PENDENTE (piccolo, consigliato):** cambiare `setdefault(k,v)`→`os.environ[k]=v` nei 3 loader (`local_runner_v2.py`, `ia_wake_agent.py`, `ia-console/ia_control_server.py`) così il `.env` vince sempre e lo "zombie parent" non si ripete. NON ancora applicato.
- Nota tuning: a `-c 16384` la VRAM è ~10.5GB (KV grosso), ~1.7GB liberi. Se la lane vision `:8081` si accende insieme → occhio OOM → alza `-ncmoe` a 32 o scendi `-c` a 8192.

## 5. FILONE B — Fine-tuning (dopo A)
- **RAFT** (Retrieval-Augmented Fine-Tuning): fine-tuna il Qwen a *usare* i simili recuperati da `promo_recall`. Per il COMPORTAMENTO (classificare/estrarre/confrontare), NON per memorizzare i promo.
- **Prima:** error-analysis su BonusX (dove sbaglia oggi il Qwen-30B) = go/no-go. Dati: le draft etichettate su Supabase (`SUPABASE_URL` in `.env.local_runner`).
- LoRA/QLoRA. Training pesante → forse cloud (RunPod A100 già disponibile) SOLO per l'addestramento; inferenza resta locale (non tradisce la tesi HW-basso).
- **Bonus dopo:** rigira la coverage sul modello fine-tunato → se concentra gli expert, l'idea "il resto su SSD" torna misurabile (`scripts/coverage_dsv2.py` come template).

## 6. NOTA IMPORTANTE — drift della taxonomy delle tecniche (da altra chat)
Le tecniche NON hanno sede unica: vivono su ~6 livelli in 2 repo. Rilevante perché **stiamo rimodellando la KB** e la taxonomy va consolidata (SSOT) prima/durante l'indicizzazione.
- **`cgc-ia-pipeline`** (= `C:\Users\imanu\llama`, runner+prompt+KB, lato che DECIDE):
  - `local_runner_v2.py`: `TECHNIQUES_BY_CAT` (:198, SSOT esecutivo; se una tecnica non c'è → ALTRO), `TECH_FIX` (:208), `TECH_BONUS_TYPE` (:234, sblocca EV), `ROUTE_TO_SLUG` (:224).
  - Prompt specialisti: `casino_system.txt`, `sport_system.txt`, `fun_*_system.txt`, `altre_system.txt`, `triage_system.txt` (qui l'IA "impara" le tecniche).
  - `kb_v2/family_<TECH>.json` (**21 famiglie**) + `index.json` + `confidence_schema.json`.
- **`promo-platform`** (TS, UI+EV, lato che USA/MOSTRA):
  - `lib/promo-taxonomy.ts` → `TECHNIQUES` (:14) + `normalizeTechnique` (SSOT flat).
  - `lib/play-modes.ts` → `TECHNIQUES_BY_CATEGORY` (:18).
  - `lib/bonus-economics.ts` → `TECHNIQUE_PROFILES` (:177, formula EV).
  - DB `drafts.technique` = free-text (no enum).
- **Drift concreto `PLAYBACK_LOTTO`:** esiste lato TS (promo-taxonomy, play-modes.casino) ma MANCA lato IA: runner `TECHNIQUES_BY_CAT['segnali-casino']`, `TECH_BONUS_TYPE`, `kb_v2/family_PLAYBACK_LOTTO.json`, `casino_system.txt`, `bonus-economics.ts TECHNIQUE_PROFILES`. Aggiungerla = toccare quei 5 punti (DB + 2 TS già a posto); il #3 KB va seminato con esempi da promo reali.
- **Incoerenza da sanare:** `bonusx-kb/kb/techniques.yaml` (10 famiglie) vs `cgc-ia-pipeline/kb_v2` (21). Decidere l'SSOT unico della taxonomy è parte del remodel (probabilmente gestito da un'altra chat — coordinare).

## 7. Estrazione promo aggiuntive (opzione, probabilmente NON serve)
Oggi ~1.472 record + 1.779 immagini. Si potrebbero estrarre più promo vecchie se servisse. **Decisione: rimandato.** 1.472 bastano per il retrieval; per il fine-tuning conta la QUALITÀ/etichette, non la quantità. Rivalutare solo se l'error-analysis mostra buchi di copertura su categorie/tecniche.

---

## 8. WORKFLOW (fasi ordinate, per la chat nuova)
**Fase 0 — SSOT taxonomy (coordinare con l'altra chat).** Consolidare la lista tecniche (unire techniques.yaml 10 ↔ kb_v2 21, sanare PLAYBACK_LOTTO) così la KB che indicizziamo è coerente. *Può procedere in parallelo.*

**Fase 1 — Chunker unico** (indipendente dal modello di embedding → si può fare subito).
- Ingest `examples/parsed*.jsonl` (promo), `corpus/*/knowledge_corpus.json` (concepts/rules/games/QA), `lessons/*/summary.md` (per sezione H2) + `knowledge.json`, `glossary.md`, `kb/*`.
- Output: `chunks.jsonl` (~3000) con schema `{id, source_type, fields{book,technique,category,variance,cap_eur,...}, bm25_text, embed_text(pulito), ref}`. Scartare OCR grezzo. Applicare sinonimi `domain-jargon.md`.

**Fase 2 — BM25 + matrice embeddings.**
- BM25: estendere `recall-core` per ingerire i chunk (non solo markdown) + filtro sui facet.
- Embeddings: `multilingual-e5-base` su CPU → `emb.npy` + `id_map.json` (una tantum). Verificare prima il miglior embedder-IT leggero 2026.

**Fase 3 — Ricerca ibrida + tool MCP.**
- `search(q, filters, k)` = espansione sinonimi → BM25 rank + (embed q)×matrice → HARD filter facet → RRF → top-k.
- Esporre tool MCP `promo_recall(query, filters?, k?)` (stesso pattern del server `recall` in `cgc-infra`).

**Fase 4 — Aggancio Qwen.** Il Qwen di analisi-promo chiama `promo_recall`: promo nuovo → k simili + concept → ragiona (categoria? parametri nuovi? dinamica mai vista?).

**Fase 5 — Fine-tuning (RAFT).** Error-analysis (Supabase) → go/no-go → LoRA/QLoRA sul comportamento, con context = simili recuperati.

**Fase 6 (bonus) — coverage sul modello fine-tunato** (concentra gli expert? → pruning-su-SSD misurabile).

**Cleanup — hardening llama.cpp** (`setdefault`→`os.environ[k]=v`, §4).

---

## 9. Riferimenti / paths / stato
- **Repo:** `moe-aggressive-commit` (ricerca chiusa + `docs/` deliverable), `bonus-kb/bonusx-kb` (KB da indicizzare), `cgc-ia-pipeline`≈`C:\Users\imanu\llama` (runner+KB+prompt), `promo-platform` (TS), `cgc-infra` (recall MCP, non clonato in locale di default — su GitHub `imanu86/cgc-infra`).
- **Docs prodotti oggi:** `docs/piano_indice_ibrido_bonusx.md` (piano indice), `docs/corso_ia_avanzato.md` (corso IA), questo handoff.
- **Modello prod:** Qwen3-30B-A3B Q4_K_M GGUF, `llama-server :8080`, on-demand via `local_runner_v2.py`.
- **HW:** RTX 3060 12GB + 32GB RAM + SSD; single-user; prompt lunghi (system fisso 2.4k-9k token) + prefix-cache già attivo (45× sul prefill — NON toccare, è ottimo).
- **TODO utente:** ruotare il **token HF** (`hf_CKrG...` incollato in chat oggi, va rigenerato); NON committare `.env.local_runner` (chiavi vive: Supabase service-role, Discord bot, ecc.).
- **Stato build nuovo sistema:** NIENTE scritto ancora — solo piani. Fase 1 (chunker) è il prossimo passo eseguibile.
