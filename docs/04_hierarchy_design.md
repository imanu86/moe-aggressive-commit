# Gerarchia di Memoria a 3 Livelli — Disegno del Sistema di Inferenza MoE

> Stato: **design allineato ai numeri misurati** (CPU/torch-free dove possibile; HW target RTX 3060 12 GB).
> Documenti collegati: [`00_architecture.md`](00_architecture.md) (assi sperimentali), [`01_positioning.md`](01_positioning.md) (prior-art), [`02_models.md`](02_models.md) (modelli + env), [`03_risks.md`](03_risks.md) (rischi).
> Evidenza che fonda questo disegno (`runs/`): `modes_granite.csv`, `accuracy_vs_k_olmoe.csv`.

---

## 1. SCOPO e RIFRAME — l'asse vero non è accuratezza-vs-VRAM, è CAPACITÀ-vs-LATENZA

Lo scopo del progetto **non** è "quanta accuratezza perdo tagliando VRAM". È: **far girare modelli
MoE enormi su HW minimo** (3060 + RAM + SSD) sfruttando la gerarchia di memoria, accettando latenza,
con **capacità (footprint massimo runnabile)** come obiettivo.

**Riframe dell'asse.** L'accuratezza è ~**costante** perché **non si droppa mai davvero**: un expert
non residente viene **demoto** (RAM o SSD), non eliminato, e viene **fetchato alla chiamata**. Quindi
l'asse reale è:

> **CAPACITÀ (footprint su disco/RAM) vs LATENZA**, ad accuratezza ~ FULL.

Questo è confermato dai numeri (`modes_granite.csv`): finché l'expert non residente è servito a
precisione sufficiente (`fetch-lossless` o `precision-cascade` ≥ int4) l'accuratezza resta ≈ FULL
(0.4–0.5); è **solo l'hard-drop** (eliminazione vera) che porta l'accuratezza a 0 (vedi §4).

**Metrica nord (due numeri, sempre accoppiati):**
1. **Modello massimo runnabile per GB di VRAM** — "capacità per GB" (footprint che entra grazie alla
   demozione su RAM/SSD, non alla VRAM).
2. **tok/s a quel footprint** — la latenza al punto di capacità scelto.

Una configurazione è interessante solo se **migliora (1) senza affondare (2)**. L'accuratezza è un
vincolo (≈ FULL), non un asse da spazzare: è il significato operativo di "non si droppa mai".

---

## 2. GERARCHIA 3-TIER

Tre livelli di memoria, dal più caldo al più freddo. La **copia a piena precisione (fp16) vive
sempre nel tier più freddo che la contiene** (di norma SSD, e in RAM se ci sta): è la verità di
riferimento da cui si fetcha. I tier caldi contengono **viste** (residenti fp16, o placeholder
compressi), non l'unica copia — così demuovere non è mai "perdere".

| Tier | Dove | Contenuto | Precisione | Stato expert | Costo d'accesso |
|---|---|---|---|---|---|
| **T0 — VRAM** | GPU 12 GB | working-set **caldo** della sessione | fp16 piena | residenti | ~0 (in-VRAM) |
| **T1 — RAM** | system RAM | **tiepidi**: placeholder **compressi** (int4) + copia fp16 se ci sta | int4 servibile / fp16 di riserva | demoti, pronti a salire | latenza PCIe (RAM→VRAM) |
| **T2 — SSD** | NVMe | **freddi e mai-usati** + copia fp16 canonica | fp16 on-disk | demoti profondi | latenza SSD + PCIe (dominante) |

**Dove vive la copia a piena precisione.** Canonicamente su **T2 (SSD)** per ogni expert; se la RAM
è capiente, T1 ne tiene una replica fp16 per il fetch lossless veloce. T0 ospita solo il sottoinsieme
residente caldo. Questo garantisce che **un fetch sia sempre possibile** (la mossa vietata di §4 è
proprio rifiutarlo).

**Regole di promozione / demozione** (chi sale e chi scende tra i tier):
- **Promozione T2→T1**: un expert freddo previsto/chiamato viene materializzato in RAM (come
  placeholder int4 e/o fp16) per ammortizzare i fetch successivi.
- **Promozione T1→T0** (*upgrade-on-call*, §4): un placeholder compresso che **viene effettivamente
  chiamato** sale a fp16 residente in VRAM.
- **Demozione T0→T1**: expert residente **non più usato** (LRU/least-recently-routed sul working-set
  della sessione) scende a placeholder compresso in RAM.
- **Demozione T1→T2**: tiepido che resta non chiamato a lungo torna freddo su SSD.
- **Invariante**: una demozione **non cancella mai** la copia fp16 canonica (resta in T2); cambia
  solo *quale vista* è materializzata e *dove*.

Il budget T0 (frazione residente `K`) è l'asse A di `00_architecture.md`; qui K è **dinamico per
sessione**, non fisso: lo calibra il probe (§3) e lo aggiusta l'adattività (§4).

---

## 3. PROBE PER-SESSIONE (delta vs dwarf)

Prima dell'inference vera, un **passaggio di probe** scopre il **working-set della sessione** sul task
**vivo**, e da quello calibra tier + precisione.

**Cos'è.** Un forward con modello **ULTRA-QUANTIZZATO** — **router in fp16** (la selezione top-k
dev'essere fedele), **expert in int2/int4** (servono solo a far girare il forward velocemente e a
basso footprint per *osservare il routing*, non a produrre l'output finale). Si gira il prompt/le
prime richieste della sessione, si raccoglie la traccia di attivazione (gli hook di
`instrument/router_hooks.py`), si stima il working-set per copertura θ e le metriche di
concentrazione (`workingset/estimator.py`, `N_eff`).

**Output del probe → piano di residenza:**
- expert nel working-set (copertura θ) → **T0** fp16;
- complemento prevedibilmente chiamato → **T1** placeholder int4 (candidati upgrade-on-call);
- coda lunga mai-toccata → resta **T2** freddo.

**Delta vs dwarf (antirez/ds4).** `dwarf`/DwarfStar calibra l'importanza **offline, una volta**, su
prompt generici di calibrazione (~4.682 prompt, imatrix statica — vedi `01_positioning.md` §5). Qui
la calibrazione è **online, sul task vivo**, e produce un **piano di tier per-sessione**, non una
quantizzazione fissa dei pesi. dwarf risponde "quali pesi sono importanti in generale"; il probe
risponde "quali expert servono *a questa sessione*, ora".

**Riuso del predittore pre-attention (93–97 %).** La predizione anticipata degli expert
(`01_positioning.md` §1, [2511.10676]) è **input riusabile, non da reinventare**: serve a (a)
**prefetch** dei placeholder T1→T0 *prima* della chiamata, sovrapponendo il fetch al compute di
attention, e (b) come **predizione del working-set** complementare al probe (cosa il probe non ha
ancora visto ma sta per arrivare). Il probe dà la *foto* del working-set; il predittore dà
l'*anticipo* token-per-token.

> ⚠️ Assunzione critica del probe: la selezione top-k sotto ultra-quant deve **coincidere** con
> quella a piena precisione. È il rischio (a) di §7 — lo **stiamo misurando**, non assumendo.

---

## 4. ADATTIVITÀ ONLINE

Il piano del probe è un **punto di partenza**, non una decisione finale. Durante l'inference vera la
residenza si adatta:

- **Upgrade-on-call.** Un expert compresso (placeholder int4 in T1, o freddo in T2) che **viene
  chiamato** dal router → **sale di precisione e di tier**: fetch da RAM/SSD, materializzazione fp16,
  promozione a T0. La prima chiamata paga la latenza di fetch; le successive sono in-VRAM. Il
  predittore pre-attention anticipa questa salita (prefetch) per nasconderne la latenza.
- **Demozione dei non-usati.** Expert residenti che smettono di essere routati scendono (T0→T1→T2)
  liberando VRAM per i nuovi caldi. È il flusso che mantiene il footprint VRAM dentro il budget
  mentre il working-set della sessione **deriva**.

**L'UNICA mossa vietata: rifiutare il fetch (hard-drop).** Non servire un expert chiamato — azzerarne
il contributo o reroutarlo — **non è una degradazione graduale: è accuratezza a zero**. Dimostrato
(`runs/`):

| Evidenza | hard-drop | precision-cascade | nota |
|---|---|---|---|
| `accuracy_vs_k_olmoe.csv` | **0.0** a K=50/25/12/6 % | — | FULL=0.5; ogni taglio "secco" → 0 |
| `modes_granite.csv` | **0.0** a ogni K | int8/int4 ≈ FULL (0.4–0.5) | il drop annienta, la demozione no |

Il meccanismo è esplicito in `enforce/granite_cascade.py`: hard-drop **azzera i pesi** dei non
residenti (`w.zero_()`), la cascade li **fake-quantizza**. Azzerare = distruggere; quantizzare =
demuovere. **Demoto su SSD e fetcho alla chiamata, sempre. Mai hard-drop.**

---

## 5. COME LA SPARSITÀ GUIDA LA CAPACITÀ

Più il modello è **sparso** (top-k piccolo su pool grande), più il **working-set della sessione è
piccolo** in proporzione al totale → più expert restano **freddi su SSD** → più modello (totale)
**entra** a parità di VRAM. La sparsità è il **moltiplicatore di capacità**.

- **Caso migliore (alta sparsità).** **DeepSeek-V4 top-8/256 ≈ 3 % attivo**: il 97 % degli expert può
  vivere su SSD/RAM, in VRAM sta solo il sottoinsieme caldo. Massima capacità per GB di VRAM.
- **Trend sui nostri modelli (`02_models.md`).** `s = n_active/n_total`: OLMoE 8/64 (s=0.125) e
  DeepSeek-V2-Lite 6/64 (s=0.094) lasciano molto su SSD; più sparso = più demovibile.
- **Caso peggiore (Granite diffuso).** Routing poco concentrato → working-set ≈ pool → poco da
  demuovere → la gerarchia non compra capacità (e il fetch-rate sale, §7b). Granite-3B è il **floor**
  contro cui misurare il guadagno.

> La sparsità **strutturale** `s` è il proxy; il driver reale è la **concentrazione empirica**
> (`N_eff = exp(H)`, §7 di `00_architecture.md`). Capacità alta richiede **entrambe**: pool grande +
> uso concentrato. Lo riportiamo come "capacità per GB **in funzione di `N_eff`**".

---

## 6. BASELINE DA BATTERE

| Baseline | Cosa fa | Limite che sfruttiamo |
|---|---|---|
| **`accelerate` device_map + offload_folder (SSD)** | offload a disco **cieco**: LRU, **nessuna predizione**, **nessuna precisione adattiva** (l'expert o è in VRAM o è su disco a piena precisione) | non anticipa (miss costoso ogni volta), non comprime in RAM (niente tier intermedio int4), non calibra per-sessione. È il **riferimento naïve** di capacità-vs-latenza |
| **MoE-Infinity** ([2401.14361]) | working-set per-**sequenza** (EAM/EAMC, match coseno), **lossless** | non degrada → niente tier int4 in RAM; battibile su **footprint** (noi teniamo placeholder compressi, non solo placement) |
| **HOBBIT** ([2411.01433]) | mixed-precision **per-token** sui miss (soglie `‖G(x)‖`) | per-token, non commit per-sessione; misura **un solo numero ≤1 % a ctx corto**, non capacità-vs-latenza a ctx crescente |
| **Mixtral-offloading** ([2312.17238]) | LRU + mixed-quant HQQ statica + prefetch | quant **statica**, LRU senza working-set per-sessione; niente upgrade-on-call adattivo |

**Il claim da dimostrare**: a **iso-accuratezza (≈ FULL)** e **iso-latenza accettabile**, la gerarchia
a 3 tier con probe + upgrade-on-call fa entrare un **modello più grande per GB di VRAM** della
baseline `accelerate` offload cieco. La metrica nord (§1) è esattamente questo confronto.

---

## 7. RISCHI (concreti)

- **(a) Drift del routing sotto ultra-quant → il probe mente.** Se il router osservato con expert
  int2/int4 seleziona top-k **diversi** da quelli a fp16, il working-set stimato è sbagliato e si
  calibra il tier sui bersagli errati. **Lo stiamo misurando** (router fp16 nel probe per
  minimizzarlo; confronto top-k probe vs FULL come diagnostico). Mitigazione di backstop:
  upgrade-on-call corregge online (§4) anche se il probe sbaglia il piano iniziale.
- **(b) Latenza SSD che domina.** Se il fetch-rate è alto (working-set grande, sparsità bassa,
  routing diffuso — vedi Granite, §5), la latenza SSD→RAM→VRAM serializza e divora i tok/s. La
  capacità sale ma diventa **inutilizzabile**. La latenza è metrica registrata (`experiment/metrics.py`,
  `pcie_bytes` in `miss_modes.py`); il caso "diffuso" è il control negativo.
- **(c) Errore di predizione → miss costosi.** Il predittore pre-attention è 93–97 %, non 100 %: il
  3–7 % di miss non prefetchati paga la latenza piena al momento della chiamata. Su modelli/layer dove
  l'exact-match scende, i miss si accumulano e degradano i tok/s (non l'accuratezza — il fetch avviene
  comunque, solo tardi).
- **(d) Accuratezza dei placeholder int2 senza upgrade.** Se un placeholder **int2** viene servito
  **senza salire** a precisione piena, l'accuratezza crolla — **misurato**: `modes_granite.csv`
  cascade-**int2** → 0.0–0.1 a ogni K, contro int4/int8 ≈ FULL. **Implicazione di design**: int2 è
  ammesso **solo** come placeholder freddo da cui fare upgrade-on-call, **mai** come precisione di
  servizio finale. int4 è la soglia minima di servizio sicura sui dati attuali.
- **(e) Vincolo B — regge a contesto lungo?** A ctx crescente il routing diventa **meno locale**
  (`03_risks.md` R1): il working-set del probe (stimato su warm-up corto) si **sotto-dimensiona**, il
  fetch-rate sale a 16k–64k proprio dove non si guarda, e la KV cache compete per la VRAM
  (`00_architecture.md` §11, R6). Una config che "tiene" capacità+latenza a 2k ma sfasa a 32k è
  **FALLITA** (protocollo §12 di `00_architecture.md`): validare a **contesto crescente**, mai in
  media, con probe long-context (needle-in-haystack), `VRAM_kv` e `VRAM_expert` riportate separate.
