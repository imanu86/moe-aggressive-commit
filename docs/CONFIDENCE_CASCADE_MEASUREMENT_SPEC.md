# Confidence-Cascade Memory — SPEC strumenti di misura & test (paper-grade, model-agnostic)

> Fase 1 del concept (design-doc: [CONFIDENCE_CASCADE_MEMORY.md](CONFIDENCE_CASCADE_MEMORY.md)).
> Output di un workflow multi-agente (3 grounding + 8 verifiche avversariali + sintesi, 2026-07-06, `wv601zqp6`).
> **Tutti e 8 gli strumenti iniziali sono risultati FIX-NEEDED** (gameable/confusi) → qui ci sono le **versioni corrette**.
> Principio non negoziabile: **si misura PRIMA, la cascata si costruisce DOPO** e solo se i go/no-go passano.

## Headline
La metrica primaria **NON è** "costo medio condizionato al successo" (survivorship bias, gameable) ma la **FRONTIERA DI PARETO costo-totale-vs-accuracy** su denominatore fisso, con **controllo RANDOM a pari budget** e **ablation del rung-0**. Il primo pezzo da costruire non è la cascata ma l'**harness di misura model-agnostic** (endpoint OpenAI-compat) + il generatore sintetico a universo fittizio + il baseline strumentato. Il concept va testato su un substrato **MHA/GQA** (dove la KV è un costo → *può* vincere) e onestamente mostrato **inerte su MLA/ds4** (il negativo è un deliverable).

---

## 1. Metriche finali (non-gameable, model-agnostic)
Regola trasversale: **denominatore fisso = N_item_totali** (mai N_risolti). **Costo = vettore deterministico** `(prefill_tokens, decode_tokens, n_embed_calls, n_rag_calls, n_llm_calls, wall_clock_s)`; primario = token+chiamate (da `usage` dell'API, riproducibili), latenza secondaria. Scorer = **exact-match** dove possibile (passkey/valori/ID fittizi); giudice-LLM fisso anonimo con rubric pre-registrata solo per open-ended.

### KPI-1 (PRIMARIO) — Frontiera di Pareto costo-vs-accuracy
- Sweep della soglia di confidence del controller su griglia `θ∈{θ1..θk}`. Per ogni θ un punto `(accuracy_totale(θ), costo_medio_totale(θ))` con `accuracy = Σcorrect/N_totali` e `costo = Σcost/N_totali` (**il costo dei falliti resta nel conto**).
- Si confrontano le **CURVE**: la cascata vince solo se **domina Pareto** (stessa accuracy a costo minore, o più accuracy a pari costo).
- Scalare di sintesi (go/no-go): **Δcost@matched-accuracy** = costo della cascata interpolato all'accuracy di `always-RAG`, con CI bootstrap. Secondario: AUC della frontiera.
- Non-gameable: alzare θ per fermarsi presto sui facili fa **crollare l'accuracy totale** (i falliti pesano) → il punto scende sotto la baseline; "escalare sempre" alza il costo → non domina.

### KPI-2 (PRIMARIO) — Costo-a-iso-accuracy vs distanza-turno
- X = distanza-turno del fatto piantato (griglia `{5,20,40,60,80}`). Y = `costo_medio_totale` a **vincolo di iso-accuracy** (accuracy come constraint ≥ soglia comune; item sotto-soglia squalificano il braccio a quella cella, non abbassano il costo).
- **Braccio no-memory obbligatorio** per isolare l'attention-decay del backbone. Il claim difendibile è il **delta (cascata − no-memory − always-RAG)**, non la curva assoluta.

### KPI-3 (GATING, pre-cascata) — Separabilità del sensore di confidence
- **AUROC(confidence, correctness)** sul braccio baseline: se ≲0.6 l'early-exit è rumore → **no-go** (misurare PRIMA di costruire).
- Tasso di **stop-troppo-presto-ad-alta-confidence** = `P(stop precoce ∧ confidence alta ∧ errata)` deve essere basso.

### KPI-4 (NOVELTY) — Spostamento di frontiera imputabile al SOLO rung-0
- Early-exit rate per-rung (frazione risolta a rung-0/1/2/3) + **ablation rung-0 ON vs OFF** sulla stessa frontiera KPI-1. Guadagno difendibile = Δfrontiera del re-boost testuale turn-level. Se rung-0 risolve `<X%` o non sposta la frontiera → **novelty inerte, negativo onesto**.

### Controlli anti-confondente
- **Abstention = task SEPARATO** (metrica propria), mai mescolata nel costo-di-recupero.
- **Anti-leakage parametrico**: universo fittizio (fatti impossibili a priori); controllo "query senza contesto piantato" ≈ chance.
- **Stratificazione** difficoltà × distanza × categoria (neutralizza Simpson).

## 2. Harness model-agnostic (cosa costruire)
Via **endpoint OpenAI-compat** (`base_url`+`model` configurabili), zero dipendenza ds4. Gira su Qwen locale o API. Seed-deterministico.
- **A — `llm_client.py`**: `generate(messages,**p)→{text,usage}` su `/v1/chat/completions`; estrae `usage` → vettore-costo; cattura logprob dove disponibili (sensore FLARE-style), fallback schema-based (`confidence_low`).
- **B — dataset (3 substrati)**: (1) **sintetico proprio** `synth_gen.py` = CUORE (universo fittizio, distanza-turno esplicita, distrattori, N≥200-500/cella, l'unico che isola pulito il rung-0); (2) **RULER** (Variable Tracking + Multi-Value NIAH riformulati come conversazione, arxiv 2404.06654); (3) **LongMemEval_s** ~115k (arxiv 2410.10813, CC-BY 4.0, categorie knowledge_updates + abstention) per validazione realistica. LOCOMO/InfiniteBench/HELMET/MemGPT-DMR solo generalizzazione.
- **C — bracci (tutti a PARI BUDGET)**: B0 no-memory · B1 always-RAG · B2 reattivo-binario · **B3 CONTROLLO RANDOM** (rung a caso a pari budget — se la cascata non lo batte, il guadagno era il budget non il gate) · B4 cascata · B5 cascata−rung0.
- **D — controller cascata** (solo dopo il go): rung-0 re-boost testuale turno → rung-1 embed locale sul buffer (riuso `embed.py`) → rung-2 recall-promo BM25+e5 (riuso, invariato) → rung-3 compressione (fuori MVP). Early-exit; logga `(rung_di_stop, confidence, correct)`.
- **E — logger JSONL + scorer + report** (frontiere Pareto per-strato, AUROC sensore, early-exit-rate, Δfrontiera rung-0 con CI bootstrap).
- **Validità del claim (onestà)**: vince su **MHA/GQA** (KV = costo reale); **inerte su MLA/ds4** (rung-0 KV collassa in re-inject testuale = recall-promo) → il negativo MLA è parte del contributo.

## 3. Piano fase-2 (STRUMENTAZIONE prima, cascata dopo)
- **Step 0** — scaffold harness (`llm_client`/`cost`/`logger`/`scorer`); gira su prompt banale loggando il vettore-costo.
- **Step 1** — `synth_gen.py` + bracci B0/B1 + **MISURA PRIMA**: KPI-3 (AUROC sensore) + frontiera baseline. → **Gate #1**.
- **Step 2** (solo se go) — controller cascata minimo (rung-0 + rung-2, poi rung-1) + bracci B3/B4/B5 + KPI-1 + KPI-4. → **Gate #2**.
- **Step 3** (solo se go) — KPI-2 (curva distanza-turno) sul sintetico + replica **RULER**.
- **Step 4** (solo se go) — **LongMemEval_s** + run comparativa **MHA (vince) vs MLA (no)** → risultato onesto bidirezionale.
- Riuso (sola lettura fino a Step 2): `bonusx-kb/retrieval/{bm25,embed,search}.py`, `local_runner_v2.py:444 confidence_low`. Nuovo flag `USE_CONFIDENCE_CASCADE` (OFF), zero impatto produzione.

## 4. Pre-registrazione go/no-go (fissata PRIMA dei risultati)
- **Substrato atteso**: positivo su **MHA/GQA**; nullo/negativo su **MLA (ds4)** — deliverable, non fallimento.
- **Gate #1** (post Step 1): GO se `AUROC(confidence,correctness) ≥ 0.65`; NO-GO se `<0.60` (sensore non discrimina → cascata sarebbe rumore).
- **Gate #2** (post cascata+ablation): GO-novelty solo se TUTTE: (i) B4 **domina Pareto** sia RANDOM (B3) sia always-RAG (B1), `Δcost@matched-acc < 0` con CI95 che esclude 0; (ii) rung-0 risolve **≥10%** degli item recuperati con successo **E** l'ablation B5 peggiora la frontiera in modo significativo; (iii) stop-troppo-presto-ad-alta-confidence `<5%`. Altrimenti **negativo onesto**.
- **Gate #3** (post realistico): conferma se il guadagno si ripresenta su RULER **e** LongMemEval_s con segno coerente; abstention non deve degradare.
- **Anti-gaming fissati**: denominatore sempre N_totali; costo primario = token+chiamate; nessuna metrica scelta post-hoc.
