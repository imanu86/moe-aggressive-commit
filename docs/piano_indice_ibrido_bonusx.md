# Piano indice ibrido — BonusX KB (BM25 + semantico, su `recall`)

> Progettato sui dati reali di `bonus-kb/bonusx-kb` (mappati luglio 2026). Obiettivo: un retriever
> ibrido esposto come tool MCP che il Qwen di analisi-promo chiama per **richiamare concetti e
> associare promo simili**, specie quelli ricorrenti.

## Il fatto che cambia tutto: la scala è PICCOLA (~3000 documenti)
Conteggio reale da indicizzare:
- ~1.472 **promo** (JSONL v1 OCR + v2 vision) — record strutturati
- ~1.000 nodi **corpus** (concepts/rules/games_db/QA dei 4 corsi)
- ~300 **sezioni di lezione** (18 dispense × ~15-20 H2)
- ~200 **termini di glossario** + ~60 record **KB reference** (49 book + 10 tecniche)
- **≈ 2.900-3.000 chunk totali.**

**Implicazione ingegneristica enorme:** a 3.000 documenti **NON serve un vector-DB** (FAISS/Qdrant/…).
Tutti gli embedding stanno in **una singola matrice** (3.000 × 768 float ≈ 9 MB). La ricerca semantica
è **una moltiplicazione matrice-vettore** (query × matrice → top-k) — *istantanea*, in-process, zero
dipendenze pesanti. Coerente con la filosofia lean di `recall`. (È letteralmente il "perché vettoriale
quando è una matrice": a questa scala, è *proprio* una matrice.)

## Decisioni di design (i pezzi che fanno la qualità)

1. **Indice UNICO con facet `source_type`** (`promo` / `concept` / `rule` / `game` / `lesson` /
   `glossary` / `book` / `technique`), non 6 indici separati. Così Qwen può chiedere "promo simili"
   (filtro `source_type=promo`) *o* "spiega questa tecnica" (`source_type∈{concept,lesson}`) dallo
   stesso strumento.
2. **Filtri HARD dai campi strutturati, non solo ranking.** Una query su un promo è quasi sempre
   "goldbet cashback nessuna varianza" → **prima filtri esatto** (`book=goldbet AND
   technique=CASHBACK AND variance=NESSUNA`), *poi* ranki il residuo. È la leva di qualità n°1 sui tuoi
   dati (campi puliti in `enriched`/`extracted`). BM25 e i facet lo danno gratis.
3. **Embedda la narrativa PULITA, non il rumore OCR.** Vettorizza `enriched.che_devo_fare_clean` (v1)
   / `extracted.che_devo_fare` (v2) + i campi normalizzati — **scarta** `che_devo_fare` grezzo OCR
   (è rumore che avvelena gli embedding e penalizza il BM25).
4. **Normalizzazione sinonimi da `domain-jargon.md`.** Costruisci una mappa: `2_FASI≈due fasi≈2 fasi`,
   `rollover≈wagering≈WG≈rigiocabile`, `cashback≈rimborso`, + le correzioni ASR ("Beflag"→"Betflag").
   Usala **sia in indicizzazione** (espansione lato documento) **sia in query** (espansione lato query).
   Metà del guadagno "semantico" lo prendi già così, a costo zero.
5. **Embedding su CPU** (come deciso): non tocca la VRAM del Qwen. A 3.000 doc, indicizzare è una
   tantum da minuti; la query è ms.

## Cosa va a BM25 vs cosa al semantico

| Segnale | BM25 (esatto) | Semantico (denso) |
|---|---|---|
| bookmaker (SPORTIUM, GOLDBET…), tecnica (2_FASI, CASHBACK…), category, validity, variance | ✅ facet/filtro | — |
| sigle: WG, RTP, EV, CAP, FUN/REAL BONUS | ✅ | — |
| nome promo, provider slot (Pragmatic, NetEnt…) | ✅ | ~ |
| `che_devo_fare_clean` (procedura) | ~ | ✅ retrieva promo simili anche se scritte diverse |
| definizioni concept/glossario, prosa lezioni | ~ | ✅ "cos'è il margine statistico?" → lezione giusta |
| parafrasi ("due fasi"↔"2 fasi", "rimborso"↔"cashback") | (con sinonimi) | ✅ |

## Architettura (in-process, dentro/accanto a `recall`)
```
Ingest (per content-type) → CHUNK uniforme:
  { id, source_type, fields:{book,technique,category,variance,cap_eur,...},
    bm25_text (campi+sinonimi), embed_text (narrativa pulita), ref (file/msg_id/image) }
        │
        ├─► BM25 index         (estende recall-core: oltre al markdown, ingest JSON/JSONL + facet sui campi)
        └─► Matrice embeddings (3000×768 fp32, .npy, + id_map)  [embedding-model su CPU]

Query:
  q → (espansione sinonimi) → BM25 rank  +  (embed q) × Matrice → semantic rank
       → HARD filter sui facet (book/technique/…)  → FUSIONE RRF dei due rank → top-k
        │
        └─► esposto come tool MCP  promo_recall(query, filters?, k?)  ← chiamato dal Qwen
```

## Regole di chunking (1 chunk = 1 unità atomica)
| Content-type | Unità | embed_text | bm25_text/facet |
|---|---|---|---|
| Promo (JSONL) | 1 record | `che_devo_fare_clean` + parametri normalizzati | book, technique, validity, variance, cap_eur, name |
| Corpus concept | 1 concept | definition + rationale | id, name, scope |
| Corpus rule / game | 1 nodo | testo regola / notes gioco | id, name, provider, classification |
| Lezione | 1 sezione H2 | prosa sezione | titolo sezione, corso, keyword |
| Glossario | 1 termine | definizione | termine + cross-ref (sinonimi) |
| KB reference | 1 book / 1 tecnica | description | id/nome (facet) |

## Embedding-model (CPU, italiano)
- **Default consigliato:** `intfloat/multilingual-e5-base` (768-dim, ~278M) — buon italiano, gira bene
  su CPU, qualità/velocità ottima a questa scala.
- Più veloce: `multilingual-e5-small` (384-dim). Più forte: `-large` (1024-dim, ~560M; a 3.000 doc
  l'indicizzazione una-tantum regge anche su CPU).
- Alternativa multilingue forte: `BAAI/bge-m3` (denso+sparse insieme; più pesante).
- **Dettaglio critico e5:** richiede i prefissi `query: …` e `passage: …` (altrimenti la qualità crolla).
- **Come girarlo:** `sentence-transformers` su CPU (semplice), **oppure** un GGUF via
  `llama-server --embedding` (resta nel tuo stack llama.cpp, su CPU). Verificare qual è il migliore
  embedder-IT leggero *oggi* prima di fissarlo.

## Piano di build (fasi concrete)
1. **Normalizzatore sinonimi** da `domain-jargon.md` (dict IT + fix ASR + alias tecniche). ~mezza giornata.
2. **Chunker unico**: ingest promo(JSONL)/corpus(JSON)/lezioni(MD)/glossari → lista di chunk uniformi
   (schema sopra). Scarta OCR grezzo. Output: `chunks.jsonl` (~3000).
3. **BM25**: estendi `recall-core` per ingerire i chunk (non solo markdown) + filtro sui facet.
   (recall già fa BM25 + tokenizzazione che spacca sigle → riuso ~diretto.)
4. **Matrice embeddings**: embedda `embed_text` di tutti i chunk (CPU) → `emb.npy` + `id_map.json`.
   Una tantum. (C'è già `scripts/retrieve_similar.py` con cosine → base da cui partire/rimpiazzare.)
5. **Ricerca ibrida**: funzione `search(q, filters, k)` = espansione → BM25 + (q×matrice) → RRF + hard
   filter → top-k. Pura, in-process.
6. **Tool MCP `promo_recall`**: aggancia al server MCP esistente (stesso pattern di `recall`). Input:
   query + filtri opzionali (book/technique/category) + k. Output: chunk con campi + ref.
7. **Aggancia il Qwen** a chiamarlo (già sai fare MCP). Per un promo nuovo: recupera k simili + concept
   rilevanti → ragiona (categoria? parametri nuovi? dinamica mai vista?).

## Dopo (fuori scope indice, ma in agenda)
- **RAFT**: fine-tune il Qwen *a usare* i simili recuperati (ragionamento sui vicini) + error-analysis.
- **Studio concentrazione expert** sul modello fine-tunato (rigiro la coverage): se il narrow concentra
  → l'idea "il resto su SSD" torna misurabile.

## Perché questo piano è "serio" e non generico
- Sfrutta che i tuoi dati sono **strutturati** (filtri hard sui campi = la leva vera).
- Sfrutta la **scala piccola** (matrice in-memory, zero vector-DB, resta lean come `recall`).
- Parte da **roba tua già fatta** (`recall`, `retrieve_similar.py`, `domain-jargon.md`).
- Separa correttamente **conoscenza→retrieval** e **comportamento→fine-tuning**.
