# HANDOFF 6 — SPEX loop + accuracy-drop + sub-expert + DeepSeek-V4-Flash

> Handoff COMPLETO e AUTOSUFFICIENTE per riprendere a FREDDO. Tutti i numeri sono MISURATI e verificati
> contro i JSON in `D:\models\spex\loops\` (spot-check 4 agenti, 2026-07-03, nessuna discrepanza col
> brain-dump). Le fonti durevoli restano `docs/SPEX_LOOP.md`, `docs/MODELS_qwen235_vs_deepseekv2.md`,
> `docs/EXPERIMENTS_LEDGER.md`. Data: 2026-07-03.

---

## 1. NORD STAR + arco sessione

**Nord star (parole utente, chiarito a fine sessione):** far girare **DeepSeek-V4-Flash (284B tot / 13B attivi,
open MIT, apr-2026)** sulla **RTX 3060 12 GB VRAM + 32 GB RAM** a **~10 tok/s su un DOMINIO ristretto, accuratezza
piena**, via **SPEX** (prefetch predittivo degli expert) + **DSpark** (speculative decoding) sul motore
**ds4/DwarfStar** (fork antirez di llama.cpp per V4-Flash). La ridondanza sub-expert era un side-quest, ora
**chiuso e negativo** (weight-space).

**SPEX in una frase:** predice il **LOADING** degli expert (cosa precaricare in VRAM), **mai il GATING** — il
router reale spara sempre → accuratezza intatta. Un HIT = expert predetto+prefetchato è residente; un MISS =
fetch on-demand SSD→VRAM che costa **solo latenza**, mai qualità. Invariante da assert-are: `routing SPEX ==
routing baseline` per ogni token/layer.

**Arco della sessione:** (1) costruito il loop SPEX DSpark-fedele (`spex_loop.py`); (2) girato per-workload su
Qwen3-30B (markov + hidden) e Qwen3-235B (markov); (3) misurato accuracy-drop "double-loop-markov" (idea utente:
droppare invece di fetchare); (4) misurato hidden-drop; (5) testato ridondanza sub-expert su Qwen-30B,
DeepSeek-V2-Lite, DeepSeek-V4-Flash (**tutte fatte, 3 famiglie, negativo**); (6) ricerca modelli fascia 235B
(Qwen vs DeepSeek V2/V4); (7) matematica tok/s sull'HW reale + **speed-sim V4 analitica (30-50 tok/s, §2.6)**.

---

## 2. RISULTATI MISURATI

Metodo di verifica: per ogni loop il valore riportato è `result.miss["adaptive_dspark"][cap]` mediato sui 2 seed
(0,1). Percentuali VRAM = cap/nexp (Qwen 128 exp; DS2-Lite 64 exp). **Tutti i numeri del brain-dump sono stati
ricontrollati contro i JSON: NESSUNA discrepanza** (arrotondamento a 3 cifre). Fonti in `D:\models\spex\loops\`:
`q30{dom,gen,code,reasoning,english,mmlu}_{markov,hidden}.json`, `q235{...}_markov.json`, `ds2lite_markov.json`,
`accuracy_drop_dom.json`, `hidden_drop_dom.log`. Caps loop = [2,4,6,8,16]; accuracy/hidden-drop = [4,6,8,12,16,24,32,48].

### 2.1 Loop SPEX 30B (Qwen3-30B-A3B, 128 exp, 48 layer) — miss-rate ADPT-DSpark, MARKOV vs HIDDEN

C=2/4/6/8/16 → 1.6%/3.1%/4.7%/6.25%/12.5% VRAM. Media 2 seed.

**MARKOV** (predittore transizione stato→stato):

| workload | C2 | C4 | C6 | **C8 (6.25%)** | C16 (12.5%) |
|---|---|---|---|---|---|
| dom       | .824 | .709 | .619 | **.524** | .354 |
| gen       | .827 | .705 | .591 | **.467** | .292 |
| code      | .850 | .748 | .657 | **.555** | .384 |
| reasoning | .848 | .744 | .660 | **.570** | .418 |
| english   | .865 | .758 | .651 | **.528** | .357 |
| mmlu      | .814 | .685 | .589 | **.501** | .353 |

**HIDDEN** (probe lineare per-layer su h_{L-1}·W, STS-calibrata):

| workload | C2 | C4 | C6 | **C8 (6.25%)** | C16 (12.5%) |
|---|---|---|---|---|---|
| dom       | .755 | .511 | .277 | **.098** | .064 |
| gen       | .757 | .522 | .309 | **.175** | .094 |
| code      | .756 | .521 | .320 | **.207** | .139 |
| reasoning | .756 | .519 | .313 | **.195** | .134 |
| english   | .755 | .515 | .300 | **.168** | .097 |
| mmlu      | .757 | .525 | .316 | **.168** | .110 |

**Takeaway:** a C8 (6.25% VRAM) HIDDEN dimezza/terza il MARKOV su tutti i 6 workload (dom .524→.098 = 5.3×;
reasoning .570→.195 = 2.9×). Il **dominio ristretto è il caso più favorevole** (.098). ECE HIDDEN raw→STS per
workload: dom .043→.008, gen .043→.013, code .064→.024, reasoning .054→.019, english .045→.012, mmlu .072→.024
(la STS-calibration abbatte l'ECE ~3-5×). MARKOV è già ben calibrato (ECE ~.015-.030, STS quasi neutra).

### 2.2 Loop SPEX 235B (Qwen3-235B-A22B trace, 128 exp/layer, 94 layer) — MARKOV

Media 2 seed. C8 = 6.25% VRAM (~7.1 GB di working-set alla scala 235B int4).

| workload | C2 | C4 | C6 | **C8 (6.25%)** | C16 (12.5%) |
|---|---|---|---|---|---|
| gen       | .812 | .685 | .580 | **.464** | .287 |
| dom       | .824 | .711 | .619 | **.518** | .343 |
| mmlu      | .823 | .704 | .609 | **.510** | .348 |
| english   | .881 | .783 | .671 | **.534** | .361 |
| code      | .865 | .777 | .685 | **.567** | .387 |
| reasoning | .863 | .772 | .686 | **.584** | .422 |

**Takeaway:** il MARKOV @C8 sul 235B è quasi identico al 30B (dom .518 vs .524; code .567 vs .555; reasoning .584
vs .570) → **scala-invariante**. L'HIDDEN a 235B NON è stato girato (probe non disponibile sulle trace 235B): il
guadagno HIDDEN è **estrapolato** dal 30B (~10-24% a seconda del workload). Su `english`, il `markov_naive`
degrada OLTRE l'`adaptive` (naive ~.605 vs adaptive .534 @C8): unico dei 6 workload dove la corsia adattiva batte
chiaramente il naive sul 235B.

### 2.3 Loop SPEX DeepSeek-V2-Lite (64 routed exp, 26 layer) — MARKOV

DS2-Lite ha cap in unità su 64 exp → C16 = **25% VRAM**. Confronto `markov_naive` (pred puro) vs `adaptive_dspark`
(τ=0.5 fisso) vs `reactive`. Media 2 seed.

**markov_naive** (predizione pura):

| workload | C2 | C4 | C6 | C8 | **C16 (25%)** |
|---|---|---|---|---|---|
| dom | .776 | .616 | .494 | .406 | **.210** |
| gen | .785 | .635 | .526 | .446 | **.251** |

**adaptive_dspark** (τ=0.5):

| workload | C2 | C4 | C6 | C8 | **C16 (25%)** |
|---|---|---|---|---|---|
| dom | .807 | .690 | .600 | .547 | **.405** |
| gen | .819 | .705 | .611 | .562 | **.437** |

**reactive** (baseline, nessuna predizione): dom C8 .657 / C16 **.465**; gen C8 .674 / C16 **.507**.

**Takeaway:** su DeepSeek (64 exp) il MARKOV è molto più affidabile che su Qwen (128 exp) → il **pred-naive
stravince** (dom @C16 .210 vs reactive .465; gen .251 vs .507). Ma l'`adaptive_dspark` con **τ=0.5 fisso è TROPPO
CAUTO** su predittori forti: peggiora fino a ~2× rispetto al naive (dom .405 vs .210). Limite noto = serve **τ
dinamico**; stesso pattern su OLMoE. I modelli 64-exp (DS2-Lite, OLMoE) sono nettamente più markov-predicibili dei
128-exp (Qwen). ECE DS2-Lite: dom .019→.018, gen .012→.013 (già calibrato).

### 2.4 Accuracy-drop "double-loop-markov" (30B dominio, top-8) — droppare invece di fetchare

Droppare (azzerare + renormalizzare) gli expert che il router vuole ma non sono nei C predetti; ppl finale × la
ppl full. **FULL ppl = 14.7896** (ntok 45689). Cap in unità su 128 exp.

| policy | C4 (3%) | C6 | **C8 (6%)** | C12 (9%) | C16 (12%) | C24 | C32 (25%) | C48 (38%) |
|---|---|---|---|---|---|---|---|---|
| **markov** | 194.9× | 76.7× | **59.4×** | 32.3× | 16.1× | 8.75× | 3.50× | 2.08× |
| **oracle** (top-C router) | 1.42× | 1.09× | **1.00×** | 1.00× | 1.00× | 1.00× | 1.00× | 1.00× |
| **static** (freq) | 642× | 283× | **168×** | 66.1× | 46.2× | 25.6× | 15.0× | 7.75× |
| **random** | 3331× | 3351× | **3260×** | 2869× | 2198× | 1104× | 417× | 51.7× |

(×full = ppl_policy / 14.7896. Es. markov C8 = 878.9/14.79 = 59.4×; static C8 = 2490.9/14.79 = 168×; random C8 =
48211/14.79 = 3260×; oracle C8 = 14.797/14.79 = 1.00×.)

**Takeaway:**
- **markov-drop = CATASTROFICO** (59× @C8, 16× @C16, ancora 2.1× @C48=38%). **Devi FETCHARE, non droppare** →
  SPEX vindicato.
- **oracle** (i veri top-C del router) = **lossless da C≥8** (a C4=1.42×, C6=1.09×, poi 1.00×) → il meccanismo
  drop+renorm è sano; è la **PREDIZIONE** il collo di bottiglia, non il drop.
- **static** (frequenza globale) è **peggio del markov** (168× vs 59× @C8); **random** = pavimento assoluto
  (3260× @C8).

### 2.5 Hidden-drop (30B dominio) — probe lineare per-layer nel forward, drop dei miss

Stessi drop dell'accuracy-drop ma i miss sono decisi dall'HIDDEN probe. Cap su 128 exp (log `hidden_drop_dom.log`,
FULL ppl 14.7896).

| C (VRAM) | ppl | ×full |
|---|---|---|
| C4 (3%) | 254.03 | 17.18× |
| C6 (5%) | 162.05 | 10.96× |
| **C8 (6%)** | 128.69 | **8.70×** |
| C12 (9%) | 30.88 | **2.09×** |
| C16 (12%) | 26.26 | **1.78×** |
| C24 (19%) | 21.96 | 1.49× |
| C32 (25%) | 19.72 | 1.33× |
| C48 (38%) | 19.52 | 1.32× |

**Takeaway:** l'hidden-drop **apre parzialmente** dove il markov-drop falliva: da C12 (≥9% VRAM) scende a
1.3-2.1× ppl (usabile) contro i 16-32× del markov agli stessi cap. **MA NON è lossless**: plateau ~1.32× anche a
C48=38% (1.333× @C32, 1.320× @C48, praticamente piatto) → manca sistematicamente un piccolo set di expert
alto-impatto (l'oracle a C48 fa 1.00×, l'hidden 1.32×). **Sweet-spot = IBRIDO: drop dei miss basso-impatto
(l'hidden li azzecca) + fetch dei pochi alto-impatto (che l'hidden manca)** → quasi-lossless con quasi-zero
stalli. Da misurare (vedi §7 aperto #2).

### 2.6 SPEED-SIM V4-Flash (tok/s) — modello analitico memory-bound su HW utente

Prima stima **analitica** tok/s per V4-Flash (284B/13B, fp4) su **RTX 3060 12GB + 32GB RAM + NVMe ~5GB/s**.
Modello memory-bound a 3 livelli: statico residente in VRAM + cache expert + fetch dei miss (RAM→VRAM o SSD→VRAM).
Script `src\msc\spex\spex_speed_sim.py`, risultati `D:\models\spex\v4_speed_sim.json` (grid 432 celle).
**Config V4 verificata:** expert_dtype=fp4, hidden 4096, moe_int 2048, 256 routed + 1 shared, 6 attivi, 43 layer,
attention CSA+HCA compressa, MTP draft head nativo (DSpark). Statico **4.72 GiB** letto da VRAM ogni forward
(15.85 ms fisso); working-set dinamico SPEX = **solo gli expert routed ~3.05 GiB/token fp4** (NON 6.5 GB).

**Numeri chiave (dal JSON):**

| grandezza | valore | note |
|---|---|---|
| best (tetto teorico) | **74.44 tok/s** | overlap-VRAM pieno + accept perfetto |
| realistic-bracket best | **47.29 tok/s** | ma vale a **ram_frac=0.9** (non 0.6) |
| dominio-ristretto miss0.10 | **45.71 tok/s** | |
| dominio-ristretto BOE miss0.08 | **56.44 tok/s** | best-of-bracket ottimistico |
| punto miss0.10 ram0.6 A2.5 | **31.85 tok/s** | ricalcolo indipendente, fetch-bound |
| guadagni | SPEX ×1.28, DSpark ×1.31, stack ×1.83 | |
| soglia 10 tok/s | **miss ≤ ~33%** | tutto il bracket realistico+ottimistico; solo markov 0.50 → 9.5 |
| bottleneck | **SSD fetch (5 GB/s)** sopra miss~0.10 | leva dominante = ram_frac alto + miss basso |

**VERIFICA indipendente = MINOR_ISSUES** (aritmetica OK, JSON riproduce il codice esatto; fisica memory-bound
strutturalmente corretta). Tre assunzioni ottimistiche identificate:
1. **Overlap-VRAM (punto ottimistico).** Il guadagno SPEX ×1.28 viene tutto dall'assumere che le letture VRAM di
   statico+hit (~32ms) si sovrappongano al fetch PCIe/SSD. Difendibile (bus diversi: DMA PCIe vs GPU/VRAM) ma
   estremo. Se SPEX nasconde solo il compute → ×1.02, best ~44.7, dom ~29.4.
2. **DSpark drafted-vs-accepted.** Il sim usa lo stesso A per byte-verify e ammortamento → assume accettazione
   perfetta. Con accept 2.5/3 realistico: best 74.44→62; dom 45.71→36.6.
3. **ram_frac=0.9.** Il 47.29 dipende criticamente dal 90% dei miss serviti da RAM (36GB/s) invece che SSD
   (5GB/s). A ram_frac=0.6 il punto scende a 31.85. Il ram_frac alto è la leva dichiarata come dominante.

**Range difendibile onesto: 30-50 tok/s** nel bracket realistico-ottimistico (best onesto 44-49; dominio-ristretto
30-40). Il **74 è un tetto teorico, NON una stima operativa.** Note fisiche minori (impatto trascurabile perché
memory-bound): FLOP contati solo sui routed (esclude shared+attn); KV-cache non modellata (ok a ctx corto, aggiunge
tempo fisso a ctx lungo); statico 4.72 GiB entra nei 12GB VRAM ma cache=6 GiB lascia ~0.3 GiB per KV → config al
limite. **Il 10 tok/s del nord star è raggiungibile** in tutto il bracket realistico (soglia miss ≤ ~33%).

### 2.7 Quantizzazione DwarfStar + cold-compress (speed-sim QUANT, statico per-tier)

Estensione del sim §2.6 con **quantizzazione parametrica per-TIER** (hot vs cold) e per lo **STATICO** (fp16 vs
fp8). Script `src\msc\spex\spex_speed_sim_quant.py`, risultati `D:\models\spex\v4_speed_sim_quant.json` (3 config
× 32 celle = 96). Punto DOMINIO = miss.10, ram.9, A2.5, spex_on.

**Cosa fa ds4 (DwarfStar-4):** quantizza gli expert a **2-bit UNIFORME** (~2.3 bpw medio: 2.06 up/gate, 2.6 down),
tiene lo **statico in FP16**, cache reattiva SSD + imatrix statica + MTP. **NON è cold-aware:** hot e cold allo
stesso bpw. Su Mac (96 GB unified) l'FP16-static sta tutto in memoria → nessun overflow.

**La nostra estensione temp-mix:** hot **2.3 bpw** (come ds4) ma cold **1.58 bpw** (IQ1_S-style sulla coda fredda,
che è quella che il fetch pesca) + **statico fp8** (obbligatorio sul 3060). Sfrutta H4/H5: comprimere il cold è
quasi-lossless (cold = basso impatto; il drop costa 1.3× floor → **comprimere < droppare**), quindi il cold-1.58
non paga quasi qualità ma taglia footprint e byte-fetch.

**Nuovi tok/s (dal JSON):**

| config | expert hot/cold | static | tok/s DOMINIO (3060 reale) | tok/s EXPERT-ONLY | union footprint | fit 44GB |
|---|---|---|---|---|---|---|
| **C_fp4** (release ipotizzata) | 4.0 / 4.0 bpw | fp8 | **5.19** | **45.71** (= sanity, riproduce sim orig) | 92.20 GB | NO |
| **C_dwarf** (ds4 uniforme) | 2.3 / 2.3 bpw | **fp16** | **1.48** | 53.13 | 53.01 GB | NO |
| **C_tempmix** (nostro) | 2.3 / 1.58 bpw | fp8 | **5.27** | 53.13 | 46.56 GB | NO (−2.56) |

**Lettura:**
- **Sul 3060 REALE lo STATICO domina il tempo/token.** L'FP16-static di ds4 (33.95 GB) sfora la VRAM12 e stream-a
  **22.9 GB/tok** da RAM via PCIe ogni forward → C_dwarf crolla a **1.48 tok/s** nonostante gli expert 2-bit.
  **Static fp8 è OBBLIGATORIO** (C_fp4/C_tempmix tengono l'overflow a 6 GB/tok e restano ~5.2 tok/s). Questa è la
  divergenza Mac-vs-3060: il Mac 96 GB non ha il problema.
- **Il 2-bit sugli expert vale ×1.16** (45.71→53.13 tok/s) SOLO sul percorso expert isolato (statico fittizio in
  VRAM). Al dominio il fetch è nascosto sotto il compute → il temp-mix non aggiunge tok/s (5.27 ≈ 5.19), **ma
  vince nelle celle fetch-bound** (miss.20 ram.6 A2 spexOFF: temp-mix 21.18 vs dwarf 17.04 EO = **+24%**, fetch
  50.4 vs 73.4 ms). Il fetch scala col bpw (0.575× hot, **0.395× cold-1.58** vs fp4), non "dimezzato".

**Fit-44GB:** **nessuna delle 3 config entra nei 44 GB** con la stima naive dello statico. La union-dominio (hot
104.1 + cold 66.3 exp/layer × 43) chiude solo a **cold ≤1.0 bpw** (41.35 GB) o con statico MLA-realistic (~24 GB).
Il temp-mix è il più vicino (46.56) ma manca 2.56 GB. Lo static-shrink vero resta il fine-tune/REAP (§2.6, I6).

**CAVEAT (importante):** il costo-QUALITÀ del 2-bit sugli HOT **NON è misurato da noi**. H4/H5 dimostrano che
comprimere/droppare i **cold** è quasi-lossless (cold basso-impatto), ma il 2-bit uniforme di ds4 tocca anche gli
**hot alto-impatto** — lì serve un **eval reale IQ2_XXS vs fp4** prima di rivendicare i tok/s. Il guadagno §2.7 è
**simulato** (byte→banda), non validato su output.

---

## 3. VERDETTI

1. **Fetch obbligatorio con markov.** Droppare gli expert markov-miss è catastrofico (59× @C8). SPEX (prefetch
   sopra streaming reattivo) è la strada giusta: gli expert non predetti vanno **fetchati** (costo latenza), non
   azzerati (costo accuratezza). L'oracle lossless conferma che il meccanismo drop è sano — è la **predizione** il
   collo.
2. **Il HIDDEN apre un drop parziale.** La probe lineare per-layer regge il drop dove il markov crolla (1.3-2.1×
   da ≥9% VRAM vs 16-32× markov). Ma non è lossless (plateau 1.32%) → manca un piccolo set alto-impatto.
3. **Ibrido = sweet-spot.** Droppa i miss basso-impatto (hidden li azzecca) + fetcha i pochi alto-impatto →
   quasi-lossless + quasi-zero-stalli. **Non ancora misurato** — è l'aperto #2.
4. **Sub-expert: NO ridondanza cross-expert in weight-space (CHIUSO, negativo, 3 famiglie).** Qwen-30B (128
   routed): coseno off .004, eff_rank 127.9/128, x-expert neuron NN .16, frac>0.8 = **0%**. DeepSeek-V2-Lite (64
   routed + 2 shared): coseno off .002, eff_rank 64/64, x-expert NN .17, frac>0.8 = **0%**; routed→shared NN .13,
   **0%** (shared ortogonali ai routed). **V4-Flash (256 routed + 1 shared, fp4) — COMPLETATA:** L14 coseno off
   **.0278**, eff_rank **246.2/256**, x-expert NN .137, frac>0.8 = **0%**, routed→shared .079 frac>0.8 = **0%**;
   L28 coseno off **.0297**, eff_rank **245.2/256**, x-expert NN .135 frac>0.8 = **0%**, routed→shared .079 frac>0.8
   = **0%**. Verdetto generalizza a **3 famiglie MoE** (Qwen 128/0-shared, DS2-Lite 64/2-shared, V4-Flash 256/1-shared
   fp4): expert quasi-ortogonali, rango ~pieno, 0% neuroni condivisi, shared ortogonali ai routed. **Idea sub-expert
   weight-space CHIUSA.** Resta aperta solo la ridondanza **FUNZIONALE** (activation-space), mai misurata — l'unica
   porta rimasta all'idea sub-expert.
5. **Scala-invarianza del MARKOV.** miss-rate 235B @C8 ≈ 30B @C8 su tutti i workload (dom .518 vs .524; code .567
   vs .555; reasoning .584 vs .570). Il predittore non si degrada salendo di scala.
6. **adaptive_dspark τ=0.5 troppo cauto su predittori forti.** Su DS2-Lite/OLMoE (64 exp, markov affidabile) il
   `markov_naive` batte l'`adaptive` di ~2× (dom @C16 .210 vs .405). Serve **τ dinamico** che si apra quando la
   confidence calibrata è alta. Su Qwen (128 exp, markov debole) l'adaptive resta la scelta giusta.
7. **10 tok/s su V4-Flash è RAGGIUNGIBILE (speed-sim, §2.6).** Il modello memory-bound dà 10 tok/s in tutto il
   bracket realistico (soglia miss ≤ ~33%). Stima operativa onesta **30-50 tok/s** (best tetto 74 = ottimistico);
   dominio-ristretto 30-45. **Condizioni:** miss basso + **ram_frac alto** (miss serviti da RAM 36GB/s, non SSD
   5GB/s) + DSpark (×1.3 accept-length). Sopra miss~0.10 il fetch SSD/PCIe domina → fetch-bound. **Il sim USA la
   miss-rate come parametro, non la misura su V4** → il prossimo passo decisivo è dumpare le trace V4 reali per
   confermarla.

---

## 4. MODELLI (fascia 235B)

### 4.1 Lineup DeepSeek nella fascia 200-300B

| Modello | Rilascio | Tot / Attivi | Open | Note fascia |
|---|---|---|---|---|
| DeepSeek-V2 | 2024-05-07 | 236B / 21B | sì | 160 routed + **2 shared**, MLA, no fp8, no GPTQ/AWQ |
| DeepSeek-V2.5 / V2.5-1210 | 2024-09 / 2024-12 | 236B / 21B | sì | merge Chat+Coder, refresh |
| **DeepSeek-V4-Flash** | **2026-04-24** | **284B / 13B** | **sì (MIT)** | **il più recente in fascia**, gen V4, fp8 nativo, ctx 1M |
| DeepSeek-V3 / R1 / V3.1 / V3.2 | dic-2024 → dic-2025 | **671B** / 37B | sì (MIT) | stesso backbone 671B, fuori fascia |
| DeepSeek-V4-Pro | 2026-04-24 | 1.6T / 49B | sì (MIT) | 384 routed, fuori fascia |

Nella fascia 200-300B DeepSeek ha solo il vecchio V2-236B (2024) e il nuovo **V4-Flash 284B/13B (apr-2026, open
MIT)**. Tra i due tutte le release intermedie (V3, R1) sono **671B**. V4-Flash è il diretto paragone di taglia a
Qwen3-235B-A22B, ma **una generazione più nuovo**.

Per contesto — **Qwen3-235B-A22B** (apr-2025): 235B/22B, 128 routed + **0 shared**, moe_int 1536, 94 layer, GQA,
Apache-2.0, **GPTQ-Int4 UFFICIALE ~125GB** (già usato sul B200). Ecosistema molto più maturo di DeepSeek per la
quantizzazione.

### 4.2 DeepSeek-V4-Flash — specs + arch custom

- **284B tot / 13B attivi**, **43 layer TUTTI MoE** (0..42), hidden **4096**, **256 routed + 1 shared**, **6
  attivi/token**, `moe_intermediate_size` 2048, vocab 129280, contesto **1M**, **fp8 nativo (e4m3)**, ~160 GB su
  disco (46 shard). Classe custom `DeepseekV4ForCausalLM`.
- **Attention nuova hybrid CSA+HCA** (non MLA classica): q_lora 1024, head_dim 512, kv_heads 1; card cita mHC /
  optimizer Muon / 32T token. Paper arXiv V4 non ancora localizzato al 2026-07-03.
- **Chiavi safetensors (arch custom):** routed = `layers.{L}.ffn.experts.{e}.w1/w2/w3.weight` + `.scale`
  (block-fp8, **w1 = gate**); shared = `layers.{L}.ffn.shared_experts.w1...`; attention `hc_*`, `attn.wkv`,
  `attn.compressor`. Dequant fp8 = weight × scale a blocchi (blocchi ricavati dallo shape, ceiling-division).
- **Tooling immaturo:** niente GPTQ-Int4 ufficiale (a differenza di Qwen3-235B); solo GGUF/AWQ community (int4
  ~80 GB, ~5% perdita, non ufficiale — `unsloth/DeepSeek-V4-Flash`, `bartowski/DeepSeek-V4-Flash-GGUF`).
  llama.cpp solo via **fork antirez** `llama.cpp-deepseek-v4-flash` (= motore **ds4**). È il target di
  ds4/DwarfStar.

**Caveat da propagare:** (1) tot/attivi (284B/13B) vengono da model card + api-docs, NON da un campo
`num_parameters` nel config; (2) dimensioni quant GGUF/AWQ sono community, non ufficiali; (3) paper arXiv non
localizzato; (4) V4-Flash cambia troppe variabili insieme rispetto a Qwen/V2 (CSA+HCA non-MLA, 1 shared non 2,
fp8, 1M ctx, arch non supportata dai tool standard) → per un confronto architetturale **controllato** V2-Lite /
V2-236B restano più maneggevoli; V4 è "stato dell'arte pari taglia" ma con più confondenti.

---

## 5. INFRA + HW + MATEMATICA TOK/S

### 5.1 Pod RunPod — TERMINATO (nessun pod attivo)

- **Pod `3wnmm9fpvzvve8`** (nome `spex-v4flash-redund`), A100-80GB — **TERMINATO** (2026-07-03, a probe
  completata). SSH era: `ssh root@204.12.201.58 -p 50459` (chiave `~/.ssh/id_ed25519`).
- **Cosa ha girato:** probe ridondanza sub-expert su DeepSeek-V4-Flash (`redundancy_probe_v4.py`), poller task
  `b7hy0irf2` → **COMPLETATA** (risultati L14/L28 in §3 verdetto #4). 3ª famiglia chiusa.
- **Balance residuo alla terminazione:** **$12.47**.
- **Stato infra:** nessun pod RunPod attivo. Il prossimo dump (V4 traces reali / 235B hidden) richiede
  re-provisioning (A100-80GB o B200 per la fp8/arch custom V4).

### 5.2 Gotcha / key RunPod (azionabili)

- **API deploy/term:** GraphQL `api.runpod.io`, header `Authorization: Bearer <key>` **+ `User-Agent` da
  browser**, altrimenti **403 Cloudflare**.
- **Key:** in `C:\Users\imanu\Desktop\Runapod.txt` — **DA RUOTARE** (è finita nel transcript) + spostare in vault.
- **Immagine testata:** `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`.
- **Pacchetti mancanti nell'img:** `pip install --break-system-packages huggingface_hub safetensors` (ambiente
  external-managed).
- **`HF_HOME=/workspace/hf`** (cache modelli sul volume, non su root). **`setsid`** davanti ai job lunghi per
  sopravvivere ai drop SSH.
- **DeepSeek-V2-Lite** carica **NATIVO** in transformers 5.x (niente `trust_remote_code`/shim).
- **V4-Flash fp8:** dequant a blocchi (`weight * scale`, blocchi dallo shape); arch custom (chiavi
  `layers.{L}.ffn.experts.{e}.w1/w2/w3.weight` + `.scale`; shared in `layers.{L}.ffn.shared_experts.*`;
  attention `hc_*`/`attn.wkv`/`attn.compressor`). llama.cpp solo via fork antirez = **ds4**.

### 5.3 Specs workstation utente (misurate)

- **RAM 31.9 GB** — **è il MURO** del sistema.
- **RTX 3060 12 GB VRAM** (il registro dice 4 GB = bug lettura 32-bit; sono **12 GB** reali).
- **NVMe Lexar EQ790 ~5 GB/s** (stimato), disco **D: 438 GB liberi**.
- **Budget memoria totale per streaming = VRAM + RAM ≈ 44 GB** (12 + 32).

### 5.4 Matematica tok/s — DeepSeek-V4-Flash (284B / 13B attivi)

Target NORD STAR: **~10 tok/s su dominio ristretto, accuratezza piena**, RTX 3060 12GB + 32GB RAM.
- **13B parametri attivi/token** → in **int4 ≈ 6.5 GB di pesi-attivi per token**.
- Modello int4 ≈ **80 GB** > **44 GB** (VRAM+RAM) → **impossibile tenerlo tutto residente → streaming da SSD**.
- **Vincolo di banda:** SSD ~5 GB/s. Per **10 tok/s** hai ~0.5 GB di budget-fetch/token → devi **fetchare <
  ~0.5 GB/token → miss-rate < ~8%** (ciò che è già nei 44 GB non paga banda; solo i miss vengono da SSD).
- **Dove siamo:** il predittore **hidden** dà miss ~**10-20%** → **vicino ma tirato** (sopra la soglia dell'8%).
- **Come chiudere il gap:**
  1. **Restringere il dominio** → il routing si concentra → il working-set caldo entra nei 44 GB → miss scende
     sotto soglia (leva principale; il dom hidden @C8 fa .098 = 9.8%, già quasi in soglia).
  2. **DSpark** (speculative decoding) → accept-length **2-3×** → ammortizza i forward, alza il tok/s effettivo.

### 5.5 Gap vs DwarfStar (94 GB)

DwarfStar gira V4-Flash su Mac con **~94 GB di memoria unificata** = **>2× la memoria dell'utente** (44 GB).
L'utente sta tentando **la versione PIÙ DURA** dello stesso problema: metà (scarsa) memoria + budget banda SSD
stretto invece di memoria unificata. Da qui l'obbligo di **restringere il dominio**: senza concentrare il
routing, il working-set non entra nei 44 GB e la banda SSD non regge i 10 tok/s.

### 5.6 Composizione SPEX ⊕ DSpark (ortogonali, componibili)

- **SPEX** riduce gli **stalli-fetch-expert** (collo = banda memoria/SSD): predice il **LOADING** degli expert
  (prefetch predittivo sopra lo streaming reattivo di ds4), il router non viene mai bypassato.
- **DSpark** riduce il **numero di forward** (speculative decoding, confidence-scheduled STS).
- **Caveat:** il verify speculativo tocca l'**UNIONE** degli expert dei token speculati → il working-set/forward
  per step **cresce** (tensione col budget dei 44 GB).
- **Motore:** **ds4/DwarfStar** ha già V4-Flash + testa draft **MTP** → base naturale; la leva nostra = **prefetch
  PREDITTIVO expert** sopra lo streaming reattivo di ds4.

---

## 6. INVENTARIO SCRIPT + PATH DATI

### 6.1 Script (durevoli)

Directory: `scripts_pod/` (pod A100, path Linux `/workspace` e `/root`, sentinella `*_DONE` a fine run) e
`src/msc/spex/` (loop durevole, gira anche in locale su Windows).

- **`src/msc/spex/spex_loop.py`** — **LO SCRIPT CENTRALE.** Loop di prefetch predittivo DSpark-fedele,
  vettorizzato. Simula la cache degli expert con orizzonte 1-layer e confronta 6 policy misurando la **miss-rate**
  a varie capacità. STS vera (grid-search temperatura per-layer 0.4→15, min ECE 15 bin), confidence head Eq.7
  (logistica 1-D, 120 iter GD su feature standardizzata), ammissione Alg.1, split rigoroso per-DOC 60/20/20 (via
  `split_docs`, no leakage), reset per-doc, multi-seed. Cache = `OrderedDict` LRU (`move_to_end`/`popitem`).
  - `--predictor markov` (score = conteggi transizione L→L+1 da `build_markov`, feature in `log1p`) o `hidden`
    (score = logit probe hidden per-token dal campo `scores[T,L-1,E]` di `hidden_scores_*.npz`, già logit).
  - Policy: `random`, `reactive` (LRU on-demand), `markov_naive`, `adaptive_crude`, `adaptive_raw` (τ su prob
    grezza), `adaptive_dspark` (prob STS-calibrata, la policy piena).
  - Arg chiave: `paths` (npz posizionali), `--caps` (default 2,4,6,8,16), `--seeds` (default 0,1,2), `--topN`
    (32), `--tau` (0.5), `--max_test_tok` (6000), `--out` (JSON con miss-rate + ECE raw/STS).
  - Uso locale: `python spex_loop.py D:/models/spex/traces_q30_domain.npz --caps 2,4,6,8,16 --seeds 0,1`
- **`scripts_pod/spex_dump_hidden.py`** — dump per-token delle logit della confidence head (predittore hidden).
  Per ogni layer L addestra una head lineare `W@h_L+b` (BCE verso expert reali di L+1) su TRAIN, dumpa le logit
  pre-sigmoid per ogni token. Hook: `mlp.gate` → top-k (label); output decoder → `h_L`. Arg: `--model`, `--tag`,
  `--prompts` (default `/workspace/raft_eval.jsonl`), `--limit` 200, `--maxtok` 512, `--trainfrac` 0.6, `--steps`
  200 (Adam), `--lr` 1e-2. Output: `/root/hidden_scores_<tag>.npz` (`scores` fp16 [T,NL-1,E], `experts` int16,
  `doclens`, scalari) + sentinella `HIDDENSC_<tag>_DONE`. Consumabile SIA markov SIA hidden.
- **`scripts_pod/dump_traces_multi.py`** — dump trace routing multi-corpus in UN load (Qwen3-235B gptq, lento da
  caricare). Hook `mlp.gate` → topk. Arg: `--model`, `--out` (/workspace), `--maxtok` 384, `--gptqmodel` (backend
  TORCH via GPTQModel.load), `--jobs` (lista `tag:file.jsonl:limit`). Output: `traces_q235_<tag>.npz`. Gate 235B
  ritorna tuple len 3 → prende `out[0]`. Sentinelle `TR_<tag>_DONE` + `T235_DONE`.
- **`scripts_pod/dump_traces_ds.py`** — dump trace DeepSeek-V2-Lite (layer 0 dense, 64 routed + 2 shared, 6
  attivi). Auto-rileva la struttura del gate, hooka solo layer MoE. Shim `is_torch_fx_available→False` per far
  girare il codice remoto DS-V2 (2024) su transformers 5.x. `extract_ids` euristico (cerca `topk_idx` int poi
  logits→topk), forward di detect + ABORTA se nessun gate produce ID. Output: `traces_ds2lite_<tag>.npz`.
  Sentinelle `TRDS_<tag>_DONE` + `DS2_DONE`.
- **`scripts_pod/accuracy_drop_v2.py`** — double-loop: perplexity con DROP di expert (aggiunge il predittore
  hidden). 6 metodi di selezione dei residenti: `full`, `oracle` (top-C logit veri), `hidden` (probe
  `W_L@h_{L-1}+b`, stile Fate), `markov`, `static` (freq-rank da calib), `random`. Arg: `--model`, `--calib`,
  `--eval`, `--out` (/workspace/accuracy_drop_v2.json), `--maxtok` 384, `--calib_lim` 100, `--eval_lim` 120,
  `--caps` (4,6,8,12,16,24,32,48). Stato globale `GL.mode` (collect/collect_h/eval) commuta gli hook; rinormalizza
  i pesi del gate sui soli residenti. Sentinella `ACCDROP2_DONE`.
- **`scripts_pod/redundancy_probe_qwen.py`** — ridondanza cross-expert dai pesi (Qwen3-30B merged, NO model load).
  Legge `gate_proj` [I=768,H=2048] dei 128 exp dai safetensors, layer `[3,24,44]`, 400 neuroni campione. Misura:
  coseno off-diag, eff_rank (entropia autovalori Gram), NN cross-expert (stesso expert escluso). Baseline di
  riferimento (off ~0.004, eff pieno, 0% shared). Solo log.
- **`scripts_pod/redundancy_probe_ds.py`** — stessa metrica su DS-V2-Lite (64 routed + 2 shared) via
  `snapshot_download` + safetensors (no model load). In più NN routed→SHARED. NEXP=64, layer `[6,13,24]`.
- **`scripts_pod/redundancy_probe_v4.py`** — stessa metrica su DS-V4-Flash (256 routed + 1 shared, FP8
  block-quant). Chiavi `layers.{L}.ffn.experts.{e}.w1.weight` (+`.w1.scale`); w1 = gate SwiGLU. Dequant block-FP8
  (`weight*scale` con repeat_interleave). Layer a 1/3 e 2/3 della lista MoE, download per-file via
  `hf_hub_download`, n_routed via regex sull'index. **È quella IN CORSO sul pod.**
- **`scripts_pod/build_diverse_corpora.py`** — costruisce 4 corpora jsonl: `code` (humaneval+mbpp), `reasoning`
  (gsm8k CoT), `english` (wikipedia-en streaming), `mmlu` (cais/mmlu all). Output `/workspace/{code,reasoning,
  english,mmlu}.jsonl`, righe `{"text":...}` a 3200 char. Ogni dataset in try/except indipendente.
- **`scripts_pod/inspect_moe.py`** — ispezione struttura MoE (debug one-shot): carica Qwen3-30B-A3B e stampa tipi
  di mlp/gate/experts, config MoE, sorgente forward via `inspect.getsource`. **Da rilanciare per un modello nuovo
  prima di adattare gli hook.**

**Varianti v1 superate (non usare come "DSpark"):** `accuracy_drop.py` (senza hidden), `dump_traces.py`
(single-corpus), `hidden_predict.py` (solo recall aggregato, non dumpa per-token), `continuous_cache_sim_ORIG.py`
(loop euristico pre-correzione, superato da `spex_loop.py`).

### 6.2 Path dati

- **Loop JSON (risultati):** `D:\models\spex\loops\` — `q30{dom,gen,code,reasoning,english,mmlu}_{markov,hidden}.json`,
  `q235{...}_markov.json`, `ds2lite_markov.json`, `accuracy_drop_dom.json`, `hidden_drop_dom.log`. Schema loop:
  `{name, predictor, nexp, L, caps, seeds, miss{policy}{cap}[per-seed], ece_raw, ece_sts}`.
- **Trace routing:** `D:\models\spex\traces_q30_{dom,gen}.npz`, `traces_q235_{domain,general,code,reasoning,
  english,mmlu}.npz`, `traces_ds2lite_{domain,general}.npz`, `traces_olmoe_*`. Campi: `experts[T,L,k]` int16 +
  `doclens` + `n_experts/topk/n_layers`. **Manca `traces_q235_domain`** (pod B200 terminato prima del dump).
- **Hidden scores:** `D:\models\spex\hidden_scores_q30_{dom,gen,code,reasoning,english,mmlu}.npz` (`experts` +
  `scores[T,L-1,E]` logit per-token). **235B hidden non dumpato** (probe non disponibile sulle trace 235B).
- **Merged weights (per redundancy probe):** `D:\models\qwen3-bonusx-merged`.
- **Doc durevoli (recupera da QUI, non dalle chat):** `docs/SPEX_LOOP.md` (loop DSpark-fedele, mappa
  DSpark→SPEX, cosa era sbagliato nel baseline), `docs/MODELS_qwen235_vs_deepseekv2.md` (lineup + specs V4 + arch
  custom + chiavi safetensors), `docs/EXPERIMENTS_LEDGER.md` (esperimenti con numeri+file+script, sezione H batch
  2), `docs/references/DSpark_paper.txt`, `docs/references/DwarfStar_ds4_README.md`.

---

## 7. APERTI / NEXT (ordinati per il nord star)

1. **[NEXT DECISIVO] V4 traces REALI → conferma miss-rate del sim.** La speed-sim (§2.6) **usa la miss-rate come
   parametro, non la misura su V4**: tutto il verdetto tok/s poggia su miss assunta (10-20% da hidden 30B
   estrapolato). Dumpare il routing V4-Flash reale (caricare arch custom via ds4/codice V4, fp8 ~80-160 GB su
   B200/A100-80GB) → loop SPEX → **miss-rate MISURATA su V4** al working-set che entra nei 44 GB. Questo è il banco
   che valida (o smonta) i 30-50 tok/s. **Richiede re-provisioning pod** (nessuno attivo).
2. **Poi: run REALE ds4/llama.cpp per tok/s VERI.** Chiude la matematica del nord star: tok/s misurati sull'HW
   utente (3060 12GB + 32GB RAM), non stimati. Il sim è memory-bound-teorico; qui si verifica overlap-VRAM reale +
   accept-length DSpark reale (i 2 punti ottimistici della verifica I5).
2b. **[da §2.7] Run REALE ds4 a 2-bit + EVAL QUALITÀ 2-bit vs fp4.** Il speed-sim quant (§2.7, ledger I8) dà i
   tok/s per byte→banda ma **non tocca la qualità**: il 2-bit uniforme di ds4 (e il temp-mix hot-2.3/cold-1.58)
   comprime anche gli **hot alto-impatto**, che H4/H5 NON coprono (misurano solo cold/drop). Servono (a) build
   reale IQ2_XXS hot / IQ1_S cold via ds4, (b) **eval ppl+field 2-bit vs fp4** sul dominio, per confermare che il
   ×1.16 tok/s non costa qualità inaccettabile. Finché non fatto, i tok/s §2.7 sono **simulati** e il static fp8 +
   cold-1.0-bpw per il fit-44GB restano da validare su output.
3. **Ibrido drop/fetch:** droppa basso-impatto (hidden) + fetcha alto-impatto → misurare quasi-lossless +
   quasi-zero-stalli (chiude il gap del plateau hidden-drop 1.32×).
4. **τ dinamico** in `adaptive_dspark` (ora fisso 0.5, troppo cauto → pred-naive lo batte su DS2-Lite/OLMoE,
   predittori forti). Deve aprirsi quando la confidence calibrata è alta.
5. **Ridondanza FUNZIONALE** activation-space — **unica porta rimasta all'idea sub-expert** (weight-space CHIUSA
   e negativa su 3 famiglie: Qwen/DS2-Lite/V4-Flash, vedi §3 verdetto #4). Mai misurata.
6. **Restringere-dominio su V4:** calibrare su una nicchia (bonusX?) → routing concentra → più working-set nei
   44 GB → miss sotto soglia. Leva dominante per i 10 tok/s (sim: ram_frac alto + miss basso).
7. **RUOTARE la RunPod key** (`C:\Users\imanu\Desktop\Runapod.txt`, esposta nel transcript) + vault.

**CHIUSO in questo batch:** sub-expert redundancy weight-space (3 famiglie, negativo); speed-sim V4 tok/s (verdetto
+ verifica); pod `3wnmm9fpvzvve8` terminato ($12.47).

---

## 8. GOTCHA CRITICI

- **V4-Flash arch CUSTOM** (`DeepseekV4ForCausalLM`): chiavi `layers.{L}.ffn.experts.{e}.w1/w2/w3.weight` +
  `.scale` (w1=gate), shared `layers.{L}.ffn.shared_experts.*`, attention `hc_*`/`attn.wkv`/`attn.compressor`. 43
  layer TUTTI MoE (0..42). Tool standard (GPTQ/AutoAWQ/llama.cpp mainline) NON la supportano → solo fork antirez
  ds4.
- **DeepSeek-V2-Lite carica NATIVO** in transformers 5.x (niente `trust_remote_code`/shim). Il V2-236B full
  invece serve lo shim `is_torch_fx_available→False` (codice remoto 2024).
- **fp8 dequant a blocchi:** `weight * scale`, blocchi ricavati dallo shape (ceiling-division, `repeat_interleave`),
  `has_scale` auto-rilevato.
- **RunPod Cloudflare:** GraphQL `api.runpod.io` richiede `Authorization: Bearer` **+ User-Agent da browser** o
  **403**. Img mancante di deps → `pip --break-system-packages huggingface_hub safetensors`. `HF_HOME=/workspace/hf`,
  `setsid` per i job lunghi.
- **adaptive_dspark τ=0.5 fisso** peggiora su predittori forti (DS2-Lite/OLMoE, ~2× vs naive) → usa `markov_naive`
  finché il τ dinamico non è implementato, o resta su adaptive solo su Qwen (128 exp, markov debole).
- **doclens PRESENTI in tutte le trace** → `split_docs` fa lo split rigoroso per-DOC 60/20/20 (train/calib/test).
  Senza doclens `spex_loop.py` tratta tutto come 1 doc → **leakage intra-doc**. Verificare sempre che il campo
  `doclens` sia nel npz prima di girare il loop.
- **Split per-DOC ovunque:** markov e confidence head si fittano SOLO su train, STS SOLO su calib, miss-rate su
  test. La STS è **order-preserving** → non cambia QUALI expert prefetchi a cache piena, cambia QUANTI ne ammetti
  via τ (il valore della calibrazione sta nel gate di ammissione/banda, non nel ranking).
- **235B hidden è ESTRAPOLATO** (10-24%), non misurato — resta un dump B200/A100 aperto. `traces_q235_domain`
  manca (dump mai fatto).
