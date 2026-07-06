# Inventions Ledger — recupero + audit di novelty (2026-07-06)

> Recupero a tappeto delle invenzioni/intuizioni di imanu86, da 3 fonti (repo-doc, memoria, transcript di sessione),
> con verifica avversariale della novelty. Workflow `w3fkb00fd` (24 agenti). Scopo: **consolidare per non perdere** +
> **sapere cosa si può rivendicare nel paper** (reviewer target: antirez → i meccanismi noti vanno citati, non rivendicati).
> `[R]` = RISCOPERTA (prior-art, NON rivendicare). `[M]` = ORIGINALE-MANU.

## Verdetto in una riga (onesto)
Recuperate ~19 idee distinte. **La maggioranza sono RISCOPERTE** di prior-art applicato al regime estremo 12GB
(SPEX, skip-on-miss, axis-flip, temperature-quant, batched-decode, leva-RAM). Il **contributo difendibile non sono i
meccanismi** ma *il transfer al regime 12GB + i controlli onesti + i negativi misurati*. **Rischio-perdita BASSO**:
ogni idea ha almeno un doc nel repo (HANDOFF + EXPERIMENTS_LEDGER fanno il loro lavoro) — tranne 1 gemma trovata solo
in chat (vedi §Recuperi). Le eventuali altre gemme solo-in-chat sono nei transcript Codex/Claude, fuori da questo sweep.

## ⭐ AGGIORNAMENTO 2026-07-06 (pm) — REAP-loop v1 CHIUSO E2E e FUNZIONA (chat K91)
La leva che qui era `[M] IDEA-SOLA` è ora **misurata end-to-end con esito positivo** → passa a **`[M] IMPLEMENTATA-v1`** ed è **il contributo-headline ORIGINALE-MANU più forte del progetto**. Branch `reap/k91-coding-vram`, 11 commit, patch 0011, giornata $2.97.
- **Asimmetria salita/discesa (finding nuovo)**: potare un modello *già in delirio* NON recupera (il contesto sporco vince); ma **partire full + stringere a scalini** (keep-64→40→23) tiene il **codice pulito fino a keep-9%** — dove il keep-9% *a freddo* collassa all'istante. È il cuore del loop.
- **Mask imparata dalla sessione** (primi 150 token) copre **62% vs 15%** delle statiche, gira **~2× più veloce** (4.5 vs 2.4 t/s, hit 0.79 vs 0.57).
- **Correzione onesta**: il collasso K91/K96 era soprattutto il **criterio di selezione** (teneva specialisti rari), non solo il numero → tenere i "cavalli da tiro" ad alta massa regge 700 token dove prima crollava in 40.
- **Sensore distress** gratis (dal routing) → all'onset **rewind**, non solo allargare.
- **Ricetta v1**: full (contesto sano + osserva routing) → a ~150 tok mask-dalla-sessione + stringi a caldo (0011) → scala a gradini a keep-9% (veloce, in VRAM, coerente) → sensore acceso → se degenera, rewind.
- **Caveat**: 700 token di CSS coerente ≠ sito completo con JS verificato (il verdetto "produzione" vuole gen completa + render).
- **Novelty check FATTO** (`docs/REAP_LOOP_NOVELTY.md`): **PARZIALE** — la composizione closed-loop + l'asimmetria + il segnale gate-mass-su-potati sono difendibili; i mattoni singoli sono prior-art (GRIFFIN/Zhu-Gupta/μ-MoE). Citazioni verificate reali.

### AGGIORNAMENTO D3–D5 (2026-07-06 sera) — rafforza la novelty E valida la velocità
- **D3** (`69567e1`): il working-set a keep-estremo è **PER-SESSIONE, non di dominio** → mask statiche **morte**, session-mask **4×**. È il **perché causale**: la potatura statica (il prior-art, GRIFFIN incluso) **NON PUÒ** raggiungere keep-9% coerente perché il set giusto cambia per-sessione → il loop session-learned è **necessario, non solo migliore**. Questo *rafforza* la linea difendibile (spiega perché il prior-art statico fallisce dove il loop regge).
- **D4** (`87d2a93`): scalini session-mask CLEAN fino a keep-23 (=keep-9%); la statica **per-massa** ("cavalli da tiro") regge (conferma la correzione criterio-di-selezione).
- **D5** (`05044ac`): **sito COMPLETO** a scalini → chiude il caveat "700 token ≠ sito", a **9.2 t/s / hit 0.91**. ⚠️ **9.2 t/s è sul pod 3080Ti** (stessa arch 12GB, non il 3060); **l'hit-rate 0.91 è la metrica che TRASFERISCE**. Valida l'ipotesi "REAP-loop = leva di velocità più grossa" (da riconfermare sul 3060 con mediana-3).

## I 3 pilastri difendibili per il paper (in ordine di solidità)
1. **REAP bias-mask come protocollo di eval surgery-free** — l'unica invenzione IMPLEMENTATA + misurata lossless
   (K50/dom ppl 1.010× vs full, CI95 [0.996,1.025]; random 1.388×; dose-response K50/K67/K70; 0/11280 violazioni V0).
   Rivendicabile: scrivere il −1e9 nel `exp_probs_b` auxiliary-loss-free di DeepSeek (entra solo nella selezione, mai
   nei pesi) → equivalenza esatta col pruning fisico → eval weight-exact su runtime **stock**, senza surgery.
   **Presentare come protocollo di riproducibilità, non come saliency nuova** (la saliency è REAP/Cerebras 2510.13999).
2. **Suite di NEGATIVI onesti** (valore metodologico alto per un reviewer come antirez):
   - **F1**: markov-naive < reactive-LRU quando cache≥top-k → giustifica perché SPEX predice *loading* non *gating*.
   - **Axis-flip** [PENDING]: il prefetcher ID-only cross-layer crolla su DS4-Flash 2-bit (top6 0.0245) → motiva SPEX. Da replicare (oggi singolo prompt degenere).
   - **H4/H5 skip-on-miss**: "devi fetchare, non droppare" (59× ppl); sweet-spot ibrido non-lossless (plateau 1.3×).
   - **Confidence-cascade Gate#2 NO-GO**: pre-registrato, con controllo random, negativo misurato. Raro e credibile.
3. **By-products riusabili**: il **trigger-router black-box** (AUROC 0.984, il pezzo vivo della cascata refutata) e il
   **framing predittivo-vs-reattivo** (SPEX su expert / cascata su memoria).

## Le idee GENUINAMENTE tue (ORIGINALE-MANU) — quelle da coltivare
| Idea | Stato | Perché è tua | Fonte |
|---|---|---|---|
| **[M] REAP-loop dinamico** | IDEA-SOLA | keep-set di saliency-dominio che si allarga/stringe a runtime (sensore n_eff/deriva, attuatore bias-mask). In letteratura il domain-pruning è **sempre statico** → il loop chiuso è tuo. **Se chiuso E2E = candidato headline.** | HANDOFF.md leva-5; REAP_DS4_design §7.bis; PAPER_DRAFT §5.5 |
| **[M] Attuatore-stabile-in-ID-space** | insight | usare la bias-mask (non la surgery) mantiene gli expert-**ID originali** → Markov/.spex/hotlist/trace SPEX restano validi attraverso i cambi di mask → **REAP-loop componibile con SPEX** senza re-dump. È il collante delle due leve. | verify #23 |
| **[M] Triage-come-segnale-di-prefetch** | IDEA-SOLA | nella pipeline Segnali il triage (sempre caldo) carica il working-set dello specialista **durante il proprio decode** (SSD idle) → latenza 15ms/expert nascosta, burst specialista già warm. | COLD_WARM_SOLUTION §3 |
| **[M] Static-is-the-collo** | osservazione (confermata) | l'intuizione che il muro dei 12GB è lo **statico residente**, non la cache-expert. Ora confermata da 3 tracce (backbone/K91/memoria). | sweep + BACKBONE_COURSE |
| **[M] Rete neurale della conversazione** ⭐ NUOVA | IDEA-SOLA (solo-in-chat) | invece della cascata RAG a costo crescente, **addestrare una piccola rete sulla conversazione** che va "dritta al punto" recuperando il contesto giusto senza rung intermedi. Emersa nella chat SPEX-memory Fase 2, **mai consolidata**. | sessione "SPEX-memory Fase 2" (transcript) |

## Ledger completo
| Invenzione | Stato | Origine | Valore | Fonte chiave |
|---|---|---|---|---|
| REAP bias-mask (protocollo surgery-free) | IMPLEMENTATA | `[R]` saliency + sliver-M | MEDIO-ALTO | `scripts/reap_bias_mask_ds4.py`; `runs/reap/2026-07-05_eval_biasmask_v2/` |
| SPEX (prefetch predittivo expert) | SIMULATA | `[R]` (Pre-gated/AdapMoE/HOBBIT/SP-MoE) | MEDIO | `docs/SPEX_spec.md`; `EXPERIMENTS_LEDGER` H1/H2; `patches/ds4/ds4_spex_predict.c` |
| REAP-loop dinamico | IDEA-SOLA | **[M]** | MEDIO(-ALTO se chiuso) | `REAP_DS4_design §7.bis` |
| Confidence-cascade memory | **REFUTED** (Gate#2 NO-GO) | `[R]` sistema; rung-0 sliver | MEDIO | `experiments/cascade_memory/FINDINGS.md` |
| Axis-flip finding | BOUNDED [PENDING] | `[R]` meccanismi, misura tua | MEDIO | `runs/ds4_routing_trace_smoke/`; `PAPER_DRAFT §4.1` |
| Skip-on-miss a perdita limitata | REFUTED (puro) | `[R]` (AdapMoE/HOBBIT/BuddyMoE) | BASSO | `src/msc/residency/miss_modes.py`; `EXPERIMENTS_LEDGER:289` |
| Leva-RAM (NO_DIRECT_IO+KEEP_PAGES) | BOUNDED | `[R]` (page-cache) | MEDIO | `project_ds4_realtest_inflight.md` |
| Batched decode (→≥10 t/s aggregati) | IDEA-SOLA | `[R]` (gap motore ds4) | MEDIO | `COLD_WARM_SOLUTION` |
| Sinergia union-load × spec-dec (−49% IO) | SIMULATA | MISTA | MEDIO | sweep; guardia `ds4.c` streaming |
| Decomposizione-impatto (fetch alto-impatto / drop coda) | SIMULATA | `[R]` principio | MEDIO | `EXPERIMENTS_LEDGER` double-loop |
| Temperature-per-expert quant | IDEA-SOLA | `[R]` (mixed-precision MoE) | BASSO | doc repo |
| Prune-per-sottrazione (r=freq_unwanted/wanted) | IDEA-SOLA | `[R]` | BASSO | `SUBTRACTION_PRUNING_analysis` |
| Precisione per-sessione (sub-IQ2 del complemento) | IDEA-SOLA | `[R]` | BASSO | sweep |
| FT-router per concentrazione/predicibilità | REFUTED (concentrazione) | `[R]` | BASSO | verify #22 (FT disperde n_eff 49.9→57.1) |
| Ri-idratazione sorted-parallel | IDEA-SOLA | `[R]` | MEDIO | `COLD_WARM_SOLUTION §2` |
| Triage-come-segnale-di-prefetch | IDEA-SOLA | **[M]** | MEDIO | `COLD_WARM_SOLUTION §3` |
| Attuatore-stabile-in-ID-space | insight | **[M]** | MEDIO | verify #23 |
| Static-is-the-collo | osservazione | **[M]** | MEDIO | BACKBONE_COURSE |
| Rete neurale della conversazione | IDEA-SOLA (solo-chat) | **[M]** | da valutare | transcript Fase 2 |

## Riscoperte — NON rivendicare nel paper (con il riferimento)
1. **SPEX (meccanismo)** = Pre-gated MoE (2308.12066), AdapMoE/HOBBIT/Mixtral-offloading (gate L+1 sull'hidden di L), SP-MoE (2510.10302). Lo smentisce il tuo stesso `PRIOR_ART.md` (F4/F5). Difendibile: la calibrazione STS cross-layer + confidence-head nel regime cache≪N di dominio stretto, e il negative F1.
2. **REAP saliency** = REAP (2510.13999, Cerebras); mascherare un gate a −inf è il primitivo standard top-k. Sliver: l'equivalenza esatta via `exp_probs_b` come *protocollo di eval*.
3. **Confidence-cascade (sistema)** = MemGPT/Letta + FLARE/Self-RAG + StreamingLLM/H2O + RECOMP/Infini + cascade-ranking. Già refutata da te (Gate#2). Sopravvive il trigger-router (AUROC 0.984).
4. **Skip-on-miss** = AdapMoE (2408.10284), HOBBIT (2411.01433), BuddyMoE (2511.10054). Smentito in casa (H4 59×).
5. **Axis-flip (meccanismi)** = Consecutive Tokens Pattern (2606.15453) + Pre-gated/SiDA/ExpertFlow. Originale è solo l'osservazione empirica dell'**inversione** dei due assi su target 2-bit vs proxy Qwen (da rafforzare: oggi 1 prompt degenere).
6. **Temperature-quant** = mixed-precision MoE noto.

## Recuperi + prossimo passo
- **Gemma solo-in-chat recuperata**: "Rete neurale della conversazione" (§sopra) — mai in un doc, ora qui.
- **Dove cercare altre gemme non consolidate** (fuori da questo sweep): i transcript Codex/Claude, in particolare
  `C:/Users/imanu/Documents/Codex/2026-07-05/.../outputs/claude_session_agent_consolidation.md` (rimando da HANDOFF.md:76-78).
  Uno sweep dedicato lì è il recupero prioritario residuo.
- **Da confermare prima di citarlo nel paper**: l'identificazione "DSpark = deepseek-ai/DeepSpec" è dichiarata ma **non verificata**.
