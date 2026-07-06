# Confidence-Cascade Hierarchical Memory — idea utente, grounding + verifica avversariale

> Idea di imanu86 (ispirata a un vlog di antirez): memoria a 3 livelli (Working / Attention-Decay-Buffer / Full-RAG)
> con **Confidence Cascade** (re-boost < embed locale < compressione < RAG persistente, early-exit su confidence).
> Questo doc è l'output di un workflow multi-agente (3 grounding + 5 verifiche avversariali + sintesi, 2026-07-06,
> `wlg8aqep5`). Ogni claim ha fonte; ciò che non è verificato è marcato **(da misurare)**.

## Verdetto in una riga
Non è un'idea nuova nel suo insieme: è la **convergenza esatta di 4 filoni già pubblicati** (MemGPT/Letta per i tier,
FLARE/Self-RAG per il gate su confidence, StreamingLLM/H2O per l'attention-decay, RECOMP/Infini-attention per la
compressione), e **recall-promo in produzione È già un L2** (ma binario, rule-based, su corpus di dominio — non 1:1
riusabile). Il premio reale **NON è la VRAM** (su V4-Flash con MLA la KV è già un latent minuscolo) ma
**context-length/coerenza**. L'unico pezzo che regge come non-visto è l'accoppiamento *re-boost = re-idratazione KV
turn-level, gated da confidence per-dato, come rung-1 di una cascata eterogenea* — il **gemello di SPEX sull'asse memoria** —
ma anche quello è doppiamente debole (vedi rischi).

## Verdetti di verifica (5 claim, avversariali)
| # | Claim | Verdetto |
|---|-------|----------|
| 1 | La cascata graduata a costo crescente come controller è nuova (il RAG confidence-gated noto è binario) | **PARZIALE** — premessa vera (è binario), conclusione sovra-venduta (cascade+early-exit è >10 anni: Cascade Ranking SIGIR'11, model cascades, FunnelRAG, RAEE) |
| 2 | Re-boost = re-idratazione KV evictata, nuovo e fattibile su ds4 | **SMENTITO** — meccanismo già pubblicato (RetrievalAttention/ShadowKV/OmniKV) E forse infattibile su MLA (niente KV densi per-turno) |
| 3 | Su V4-Flash (MLA) la VRAM è un premio marginale; il vero premio è context-length/coerenza | **PARZIALE** — regge nella sostanza, una correzione quantitativa |
| 4 | recall-promo è riusabile ~1:1 come L2 sulla storia conversazione | **SMENTITO** — è un RAG su corpus di dominio STATICO con gate rule-based, non accesso alla storia; 3 disallineamenti strutturali |
| 5 | Il sensore di confidence pratico è token-prob/entropia FLARE-style, senza training | **PARZIALE** — esiste e non serve training, MA il sensore reale di recall-promo è un **gate deterministico schema-based**, non logprob |

## Cosa è preso vs cosa è nuovo
| Pezzo dell'idea | Prior art | Uguale / Diverso |
|---|---|---|
| L1/L2/L3 tiered memory + re-inject on-demand | **MemGPT/Letta** (arxiv 2310.08560) | UGUALE la struttura hot-window+cold-store; DIVERSO: paging via tool-call espliciti, binario RAM/disk, re-inject sempre TESTO mai KV |
| L2 micro-RAG confidence-gated | **FLARE** (2305.06983), **Self-RAG** (2310.11511), **DRAGIN** (2405.18727), **CtrlA** | UGUALE il trigger su incertezza; DIVERSO: tutti BINARI, verso corpus esterno, nessuno distingue buffer-recente vs KB-persistente |
| "Attention Decay Buffer" | **StreamingLLM** (2309.17453), **H2O**, **SnapKV**, **PyramidKV** | UGUALE l'intuizione; DIVERSO: sono eviction LOSSY senza recovery (token evicted = perso). Il layer di recupero è il pezzo che aggiungi tu |
| Compressione in key-facts + store persistente | **RECOMP**, **AutoCompressor**, **Infini-attention** (2404.07143) | UGUALE il comprimere; DIVERSO: comprimono incondizionatamente come architettura, non dietro un gate |
| Cascata a costo crescente (early-exit) | **Cascade Ranking** (SIGIR 2011), **CascadeBERT**, **FunnelRAG**, **RAEE**, **Adaptive-RAG** | UGUALE lo spirito cheap-first; DIVERSO: applicato ad altri assi. Il meccanismo cascata-early-exit è vecchio >10 anni |
| L1/L2/L3 conversazionale con escalation al fallimento | **Hierarchical Memory Orchestration** (2604.01670) | UGUALE la struttura a 3 tier con ricerca ricorsiva — già pubblicata; DIVERSO: tier = vector-search uniforme, trigger = risultato-vuoto non confidence |
| Re-boost = re-idratazione KV | **RetrievalAttention, ShadowKV, OmniKV, HeteroCache** (2412.19442, 2410.21465, 2407.02328) | UGUALE il KV-recall on-demand; DIVERSO: triggerati da attention-score per-step dentro il forward, non da un gate turn-level |
| **recall-promo** (draft low-conf → BM25+e5 → re-inject) | È letteralmente **una rung binaria di L2**, già spedita | Caso base FLARE/Self-RAG-like. Mancano solo le rung più economiche PRIMA. `local_runner_v2.py:527-538`, `bonusx-kb/retrieval/{bm25,embed,search,kb_block}.py` |

## Obiettivo, riformulato sulla realtà MLA
La VRAM **non** è il premio: V4-Flash usa **MLA** → la KV è compressa in un latent condiviso minuscolo
(kv_lora_rank≈512 per token). StreamingLLM/H2O/SnapKV nascono per far dimagrire KV *dense* — su MLA quel guadagno
è già incassato dall'architettura. Il muro dei 12GB sono i **pesi non-routed RESIDENTI** (~9GB@Q8 / ~18GB@bf16 per
V4-Flash), stessa conclusione della traccia backbone. Conseguenza dura: il "re-boost = re-idratazione KV" (il pezzo
più nuovo) su MLA **rischia di collassare in re-inject di TESTO + ri-prefill**, cioè esattamente ciò che recall-promo
fa già.

**Il premio reale (da misurare):** (1) **context-length effettiva / coerenza a lungo raggio** (context nativo piccolo,
prefill basso, recupero del vecchio senza esplodere la finestra — guadagno su coerenza a turno 60+); (2) **costo medio
di accesso alla memoria** (se la rung economica risolve una frazione delle query, eviti l'embed/compress/RAG più caro).

## Novelty difendibile (formulata STRETTA)
> "Una cascata a costo crescente il cui **rung-1 è re-idratazione KV turn-level**, gated da **confidence per-dato**, che
> escala attraverso meccanismi di accesso alla memoria **qualitativamente diversi** (KV re-boost → embed locale →
> compressione → RAG persistente) con **early-exit**, dentro una memoria conversazionale, non risulta pubblicata come
> sistema unico."

Qualunque claim più largo di questa frase viene smentito. E anche questa è **condizionata** all'esistere di KV
per-turno re-idratabili su MLA → **(da misurare)** prima di rivendicarla.

## Angolo paper — il gemello di SPEX (l'unica storia che regge)
SPEX (`docs/SPEX_spec.md`) fa **prefetch predittivo degli EXPERT** (predice il LOADING, non il gating). La Confidence
Cascade è il **duale reattivo**: paging dell'informazione conversazionale triggerato dalla confidence.
> **"Predictive vs reactive memory paging in a small-VRAM MoE runtime."** SPEX pagina gli expert in modo *predittivo*;
> la Confidence Cascade pagina l'informazione conversazionale in modo *reattivo* (recupera solo quando il modello segnala
> incertezza, al costo più basso che risolve). Due metà dello stesso controller di paging su un budget VRAM condiviso.

Questo evita il claim smentito (la cascata in sé non è nuova) e sposta il contributo su un asse difendibile. Il rung-1
reattivo può poi diventare **predittivo** (pre-scaldare i turni che probabilmente serviranno) = trasferimento del
principio SPEX all'asse memoria.

## Prototipo minimo (MVP) — estende recall-promo, non riscrive
recall-promo È già la rung binaria di L2. L'MVP aggiunge **le rung più economiche PRIMA** e trasforma il gate binario in
un controller multi-scalino con early-exit e strumentazione, dietro un **nuovo flag `USE_CONFIDENCE_CASCADE` (OFF di
default)**, senza toccare né la produzione né la KV nativa del modello.
1. **Strumenta la baseline**: logga confidence, se il RAG scatta, correttezza, costo/latenza (denominatore).
2. **Rung-0 = re-boost testuale del turno specifico** (finestra L2): re-inietta il TESTO del turno più probabile, ri-genera. Su MLA è l'onesto sostituto della "re-idratazione KV". Early-exit se la confidence risale.
3. **Rung-1 = embed locale sul solo buffer recente** (e5 già in `embed.py`, ristretto al buffer, non full-KB).
4. **Rung-2 = recall-promo attuale** (BM25+e5 su KB) — invariato, scalino più caro.
5. **Rung-3 = compressione key-facts** (RECOMP-like) solo se il context esplode — probabilmente fuori MVP.
6. **Controller + early-exit + metriche**: state-machine che ferma al primo rung che alza la confidence e registra *a quale rung*. Deliverable = **curva costo-medio-per-recupero-riuscito vs baseline always-RAG**.

**Nota-correzione:** il sensore di confidence di recall-promo NON è logprob/entropy — è `confidence_low(parsed, technique)`,
un gate **deterministico schema-based** (required_field mancante / valore numerico fuori [p10,p90] / `ambiguous_between`).
Per una memoria conversazionale il sensore FLARE/DRAGIN-style va **costruito nuovo**; trasferisce l'idea, non il codice.

## Rischi (dai claim SMENTITI/PARZIALI)
1. **[affonda la novelty più forte]** Su MLA non esistono KV per-turno da re-idratare → il rung-1 collassa in re-inject testuale = recall-promo. **(da misurare, gating della novelty.)**
2. **[novelty sovra-venduta]** "La cascata è nuova" è smentito (SIGIR'11, model cascades, FunnelRAG). Restringere ESATTAMENTE alla frase in Novelty.
3. **[struttura già pubblicata]** Hierarchical Memory Orchestration (2604.01670) va citata come baseline diretta, non ignorata.
4. **[premio sbagliato]** Vendere "risparmio VRAM" è falso sul target (MLA). Riformulare su context-length + costo di recupero.
5. **[il sensore può non discriminare]** Portare il gate a per-span può essere rumoroso → misurare la separabilità PRIMA di costruire la cascata.
6. **[complessità > guadagno]** Se rung-0 risolve <X% o e5-locale non è molto più economico di e5-full-KB, la cascata aggiunge latenza senza tagliare il costo medio → KPI go/no-go esplicito.

## Fonti
Prior art via WebSearch (arxiv IDs sopra); codice proprio verificato questa sessione (`local_runner_v2.py`,
`bonusx-kb/retrieval/`); realtà VRAM/MLA da `HANDOFF.md` + WebSearch su MLA DeepSeek-V3. Workflow `wlg8aqep5`, 9 agenti.
