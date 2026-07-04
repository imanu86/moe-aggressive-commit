# MoE — Commit Aggressivo Per-Sessione · Architettura & Disegno Sperimentale

> Stato: **studio + scaffold** (no implementazione pesante).
> Hardware target iniziale: Ryzen 7 5800X + RTX 3060 12 GB. Salto a 5090 solo dopo i numeri.
> Documenti collegati: [`01_positioning.md`](01_positioning.md) (prior-art verificato), [`02_models.md`](02_models.md) (scelta modelli + env 3060), [`03_risks.md`](03_risks.md) (rischi).

---

## 0. Scope e non-goal

**Goal.** Misurare la *superficie* accuratezza-vs-VRAM di una politica di residenza degli expert
("commit aggressivo per-sessione") al variare di **quattro** assi indipendenti, e stabilire se
esiste una regione robusta dove si taglia gran parte della VRAM-expert perdendo **< 2 % di
accuratezza su TUTTE le lunghezze di contesto testate**.

**Non-goal (espliciti).**
- ❌ NON costruiamo un predittore di expert migliore. Lo stato dell'arte (predittori leggeri
  pre-attention) è già a ~93–97 % — vedi [`01_positioning.md`](01_positioning.md). Noi lo *usiamo*, non lo battiamo.
- ❌ NON ottimizziamo la latenza di fetch come obiettivo primario (lo fanno MoE-Infinity, ecc.).
  La latenza è una **metrica registrata**, non la funzione obiettivo.
- ❌ NON puntiamo a zero perdita di accuratezza. La scommessa è **deliberatamente** barattare un
  filo di accuratezza per molto meno footprint, e **misurare esattamente il cambio**.

**Il delta rispetto al noto** (da confermare in `01_positioning.md`):
> Policy di **commit** aggressiva tarata sulla **località empirica del task** + **misura del
> trade-off contro un validatore deterministico** + **caratterizzazione del guadagno in funzione
> della sparsità (strutturale) e della concentrazione (empirica)**, con validazione a **contesto
> crescente**.

---

## 1. Tesi e domanda decisiva

**Tesi.** Per workload ad alta località (coding agent ripetitivo, scraping, task ripetitivi) la
distribuzione d'uso degli expert su una sessione è fortemente concentrata. Se stimo il working set
in una finestra di warm-up e *committo* su quel sottoinsieme, posso degradare il resto (offload /
quant / drop) perdendo poca accuratezza ma molta VRAM.

**Domanda decisiva (verbatim).**
> Per un task ad alta località, qual è la superficie accuratezza-vs-VRAM al variare di
> (i) aggressività del commit [K expert residenti], (ii) sparsità del modello, (iii) lunghezza di
> contesto? Esiste una regione in cui taglio gran parte degli expert dalla VRAM perdendo < 2 % di
> accuratezza **su tutte le lunghezze di contesto testate**?

**Verdetto atteso (forma).** NON un numero singolo, ma una **famiglia di curve** + un grafico
riassuntivo "guadagno VRAM a iso-accuratezza vs sparsità". Vedi §10.

---

## 2. Posizionamento (sintesi)

Dettaglio **verificato** con fonti in [`01_positioning.md`](01_positioning.md). In una riga ciascuno:

| Lavoro / tecnica | Cosa fa | Perde accuratezza? | Relazione col nostro delta |
|---|---|---|---|
| Predittori expert pre-attention ([2511.10676](https://arxiv.org/abs/2511.10676)) | predicono i top-k *prossimi* expert per prefetch (93–97 %) | No | Input riusabile: ce ne serviamo per il prefetch, non lo miglioriamo |
| **BrainStorm** (popolarità globale) | cache per frequenza di attivazione globale | No (solo placement) | È la nostra baseline **`COARSE`** |
| **MoE-Infinity** ([2401.14361](https://arxiv.org/abs/2401.14361)) | working set **per-sequenza** (EAM/EAMC, cosine match) | **No (lossless)** | **Cugino LOSSLESS** di AGGRESSIVE-COMMIT — *non* la versione semplice |
| **HOBBIT** ([2411.01433](https://arxiv.org/abs/2411.01433)) | mixed-precision **per-token** su miss (soglie `‖G(x)‖`) | Sì (≤1 %, **ctx corto**) | Prior-art più vicino al `precision-cascade`; riusiamo il proxy `‖G(x)‖` (corr. 0.99) |
| Mixtral-offloading ([2312.17238](https://arxiv.org/abs/2312.17238)) | LRU + mixed-quant HQQ + prefetch | quant statica | Il vero riferimento "LRU" (≠ ST-MoE/SP-MoE/SpecMD) |
| imatrix / antirez-ds4 | quant importance-aware **statica/offline** | Sì, ma controllata | Ortogonale: la nostra è **per-sessione/adattiva**, non statica |

> ⚠️ **Correzioni verificate al brief** (dettaglio in `01_positioning.md`):
> 1. **MoE-Infinity NON è "popularity caching semplice"** — rifiuta esplicitamente la popolarità
>    globale (quella è **BrainStorm**) e fa matching per-sequenza, ma resta **lossless**. La nostra
>    baseline `COARSE` è quindi stile **BrainStorm**, non MoE-Infinity.
> 2. **`ST-MoE`/`SP-MoE`/`SpecMD` sono misattribuiti**: ST-MoE = training stabile (Zoph 2022);
>    SP-MoE = speculative prefetching; SpecMD = benchmark di cache policy (e gira **su OLMoE**,
>    hit-rate >88 % con cache 5 % → evidenza di alta località).
> 3. **HOBBIT** fa già mixed-precision lossy (≤1 %) **ma solo su benchmark a contesto corto** →
>    è proprio il buco che il nostro Vincolo B chiude.

---

## 3. Le QUATTRO variabili indipendenti (gli assi della griglia)

Il brief ne chiede tre; ne aggiungiamo una quarta dalla decisione di sessione (miss_mode) e
*raffiniamo* l'asse sparsità.

### Asse A — Aggressività del commit `K`
Frazione di expert tenuti **residenti** in VRAM a piena precisione. Griglia:
`K ∈ {100 %, 50 %, 25 %, 12 %, 6 %}` degli expert routed.

### Asse B — Sparsità **strutturale** *e* concentrazione **empirica** (la correzione)
> **Correzione concettuale rispetto al brief.** La sparsità strutturale `s = n_active / n_total`
> è un *proxy*, non il driver reale del guadagno. Il driver reale è la **concentrazione empirica
> del working set**: quanto è skewed la distribuzione d'uso degli expert *su una sessione*. Un
> modello 8/160 può avere working set enorme se il routing è diffuso; un 8/40 può averlo piccolo
> se è concentrato.

Riportiamo **entrambi**:
- **Strutturale** (richiesto): `s = n_active / n_total` — variabile esplicita, ≥ 2 modelli a `s` diversa.
- **Empirica** (la variabile che spiega la curva): entropia normalizzata, Gini, *numero efficace di
  expert* `N_eff = exp(H)` della distribuzione d'uso per-layer e per-sessione. Vedi §7.
- **Sweep continuo (bonus metodologico):** su un singolo modello posso variare il **top-k** a parità
  di pesi (es. top-4/8/16 su OLMoE, rinormalizzando i gate) per spazzare `s` *con continuità* senza
  confondere architetture diverse. È un probe *within-model*; non è "puro" (il modello è addestrato
  a un top-k specifico) ma isola l'effetto della sparsità dai confondenti architetturali.

### Asse C — Lunghezza di contesto
`ctx ∈ {1k, 4k, 16k, 64k, max}` token. **Mai un valore fisso.** Vedi §8 (Vincolo B).

### Asse D — `miss_mode` (decisione di sessione)
Cosa fa la policy quando un token viene instradato su un expert **non residente**:
- `fetch-lossless` — carica da RAM a piena precisione. **Accuratezza = FULL**, costo = latenza PCIe.
- `precision-cascade` — serve da una copia low-bit (int4/int2) **in VRAM**. Costo = accuratezza, no PCIe.
- `hard-drop` — non serve l'expert: reroute al residente più vicino *o* contributo azzerato.
  Massimo taglio, peggior accuratezza (limite inferiore della superficie).

> Solo `precision-cascade` e `hard-drop` producono perdita di accuratezza. `fetch-lossless` fissa la
> **baseline latenza-pura** (perdita 0). La domanda "< 2 %" si valuta sui primi due.

**Cardinalità griglia (ordine di grandezza):** `5 (K) × ≥2 (modelli) × 5 (ctx) × 3 (miss_mode)` ≈
150 celle per dataset di validazione. Vedi §9 per scorciatoie (es. `fetch-lossless` non dipende da K
per l'accuratezza → si calcola una volta).

---

## 4. Le tre policy a confronto

| Policy | Cosa tiene residente | Origine della scelta | Ruolo |
|---|---|---|---|
| **`FULL`** | tutti gli expert disponibili a precisione nativa (su 12 GB → con offload CPU) | — | **ground truth** di accuratezza |
| **`COARSE`** | top-K expert più **frequenti** globalmente | popolarità globale (stile **BrainStorm**) | baseline noto |
| **`AGGRESSIVE-COMMIT`** | working set stimato in warm-up, poi **committato** | località *del task corrente* | **la nostra** |

Differenza chiave `COARSE` vs `AGGRESSIVE`: `COARSE` usa una popolarità *globale/statica*;
`AGGRESSIVE` stima il working set *per-sessione* in una finestra di warm-up e ci **committa**,
trattando il resto secondo `miss_mode`. L'ipotesi è che per task ad alta località il working set
per-sessione sia più piccolo e più predittivo della popolarità globale.

> **Nota di posizionamento (verificata).** `MoE-Infinity` stima anch'esso un working set
> per-sequenza, ma è **lossless** (riposiziona, non degrada). La nostra `AGGRESSIVE-COMMIT` si
> distingue perché **degrada deliberatamente** il complemento (`precision-cascade`/`hard-drop`) e
> **misura** il trade-off. Una quarta policy `MOE-INFINITY-LIKE` (lossless, per-sequenza) può essere
> aggiunta come *upper bound* di accuratezza a VRAM ridotta — equivale ad `AGGRESSIVE` con
> `miss_mode=fetch-lossless`.

---

## 5. Semantica della residenza e del miss-handling (cuore tecnico)

Componente centrale: **`ResidencyManager`** (`src/msc/residency/manager.py`). Decide, per ogni
layer MoE, quali expert stanno in VRAM, a che precisione, e cosa fare sui miss.

```
                       token → router → top-k expert ids
                                          │
                          ┌───────────────┴───────────────┐
                     resident?                         non-resident
                          │                                 │
                  serve fp16 (VRAM)              switch su miss_mode:
                                          ┌──────────┬───────────────┬───────────┐
                                     fetch-lossless  precision-cascade  hard-drop
                                     (RAM→VRAM fp16)  (copia int4 VRAM)  (reroute/zero)
                                          │               │                 │
                                  +latenza PCIe     +errore quant      +errore drop
```

**Contabilità VRAM esplicita** (modello di costo, dettaglio in §11). Con `N` expert routed/layer,
`L` layer MoE, `S` byte/expert a fp16, frazione residente `f = K/N`, low-bit `b` (es. 4):

| miss_mode | VRAM-expert (≈) | Δ accuratezza | Δ latenza |
|---|---|---|---|
| `fetch-lossless`  | `f·N·L·S` (+ buffer fetch) | 0 (per costruzione) | miss_rate × T_PCIe |
| `precision-cascade` | `f·N·L·S + (1−f)·N·L·S·(b/16)` | da quant del `(1−f)` | ~0 |
| `hard-drop` | `f·N·L·S` | da reroute/zero sui miss | ~0 |

> Gli **shared experts** (DeepSeek-V2-Lite, Qwen) sono **sempre residenti** → entrano nel
> *floor* di VRAM e vanno scorporati dal conteggio "tagliabile". `02_models.md` ne tiene conto.

---

## 6. Harness di logging (router hooks)

`src/msc/instrument/router_hooks.py` registra, **per layer e per token**, la top-k degli expert
attivati + i gate weights. Implementazione via forward-hook sul modulo gate/router (HF
`transformers`; per molti MoE basta `output_router_logits=True`, ma logghiamo gli **id selezionati**
non solo i logits).

**Schema della traccia** (`instrument/trace.py`):
```jsonl
{"session_id","step","layer","token_pos","topk_ids":[...],"gate_w":[...],"ctx_len","model_id"}
```
Una traccia per sessione, con metadati di lunghezza di contesto. È l'input sia per la stima del
working set (§7) sia per l'analisi di concentrazione.

---

## 7. Stima del working set + metriche di concentrazione

`src/msc/workingset/estimator.py`. Dalla traccia di warm-up, per ogni layer:

1. **Istogramma d'uso** `p_e` degli expert.
2. **Curva di copertura**: ordina per frequenza decrescente, copertura cumulata `C(k)`.
   Working set a soglia θ: `W_θ = min{ k : C(k) ≥ θ }` (es. θ = 0.95).
3. **Concentrazione** (le metriche che spiegano la curva):
   - entropia normalizzata `H = −Σ p log p / log N` (1 = diffuso, 0 = concentrato);
   - Gini;
   - numero efficace di expert `N_eff = exp(H_nat)`.
4. **Convergenza del working set**: `W_θ` in funzione del numero di token di warm-up.
   *Se `W_θ` non si stabilizza, la stima del commit è inaffidabile* → flag.

Il commit di `AGGRESSIVE` tiene residenti gli expert fino a copertura θ (o fino al budget `K`,
qual è più stringente), per-layer.

---

## 8. Validatore deterministico a contesto crescente (cuore sperimentale)

> Questo è il pezzo da **non** sbrigare. Senza, "commit aggressivo" = degrado alla cieca.

### 8.1 Segnale binario verificabile al 100 %
- **Primario:** generazione di funzioni Python validate da **unit test nascosti** (pass/fail su
  tutta la suite → 1/0). Determinismo: greedy decoding (T = 0), seed fissi, prompt fisso.
- **Secondario (closed-form):** risposte chiuse controllabili (regex/uguaglianza esatta).

### 8.2 Contesto crescente — DUE meccanismi (Vincolo B)
Il punto critico: un task di codegen *corto* può non toccare mai l'attention a lungo raggio, quindi
non esporrebbe i fallimenti che collassano a contesto lungo. Servono **entrambi**:

- **(a) Padding-con-distrattori** — task **fisso**, contesto riempito con codice/testo distrattore
  fino a {1k,4k,16k,64k,max}. Controlla la difficoltà del task e isola l'effetto della *lunghezza*.
- **(b) Probe di retrieval long-context** (needle-in-haystack / indexed) — risposta chiusa che
  **richiede** di attendere a contesto distante. È il test che cattura il "regge a 2k, sfasa a 32k".

`src/msc/validator/context_filler.py` cresce il contesto in modo controllato e ripetibile.

### 8.3 Perché long-context interagisce col commit (l'insidia, esplicita)
A contesto lungo il routing può diventare **meno locale** (più expert distinti) → un commit tarato
su warm-up corto vede **miss rate più alto** proprio dove il fallimento è difficile da vedere.
L'esperimento è disegnato per esporlo: **warm-up corto → valuta a contesto crescente → osserva
miss_rate E accuratezza divergere**. Una policy che "tiene" a 2k ma sfasa a 32k è **FALLITA**, non
promossa (vedi §12).

### 8.4 Determinismo dell'harness
Il validatore *in sé* dev'essere byte-deterministico: stesso input → stesso verdetto.
`tests/test_validator_determinism.py` lo impone (gate del repo).

---

## 9. Loop dell'esperimento (griglia 4D)

`src/msc/experiment/runner.py`. Per ogni `(modello, K, ctx, miss_mode)`:

```
1. warm-up   : gira N esempi, raccogli traccia attivazione (instrument/)
2. stima     : working set per copertura θ + metriche concentrazione (workingset/)
3. commit    : ResidencyManager tiene residenti gli expert scelti; resto → miss_mode
4. valuta    : genera → validatore deterministico a contesto ctx (validator/)
5. registra  : accuratezza, VRAM residente, miss_rate, latenza, convergenza working set (metrics/)
```

**Scorciatoie (riducono la griglia senza perdere segnale):**
- `fetch-lossless` ha accuratezza ≡ `FULL` per costruzione → si misura **una volta** (solo
  latenza/miss_rate variano con K). Risparmia ~1/3 delle celle "accuratezza".
- `K = 100 %` ≡ `FULL` → ground truth, una volta per modello/ctx.
- Warm-up trace riusabile tra `miss_mode` (il routing non dipende dal modo di servire i miss,
  *tranne* in `hard-drop` con reroute, che altera il path → in quel caso ri-traccia).

---

## 10. Metriche e deliverable (famiglia di curve)

**NON** un grafo 2D. Output:

1. **Per modello:** accuratezza vs VRAM/K, **una linea per lunghezza di contesto** (e per
   `miss_mode`). Mostra se la regione "piatta" sopravvive al crescere del contesto o collassa.
2. **Riassuntivo:** guadagno VRAM a **iso-accuratezza** (drop < 2 %) **in funzione della sparsità**
   (strutturale) — e, in overlay, vs concentrazione empirica `N_eff`.
3. **Diagnostici:** miss_rate vs ctx; convergenza `W_θ` vs warm-up; latenza vs K (per `fetch-lossless`).

`src/msc/report/curves.py` genera la famiglia di curve + il grafico riassuntivo.

---

## 11. Modello di costo VRAM (esplicito)

```
VRAM_tot ≈ VRAM_backbone(attn, embed, norm)
          + VRAM_kv(ctx_len)                      # cresce con il contesto!
          + VRAM_expert(policy, K, miss_mode)     # vedi tabella §5
          + VRAM_overhead(cuda ctx, buffers)
```
> Nota: a contesto lungo la **KV cache** può dominare e mascherare il guadagno-expert. Riportiamo
> i due contributi **separati**, altrimenti il "guadagno VRAM" a 64k sembra svanire per colpa della
> KV, non della policy.

---

## 12. Protocollo di falsificazione (quando dichiaro FALLITA una regione)

Una cella `(modello, K, miss_mode)` è **PROMOSSA** solo se:
- drop accuratezza < 2 % **su TUTTE** le `ctx` testate (non in media), **e**
- miss_rate non esplode con `ctx` (monitor di drift), **e**
- la stima del working set è **convergente** in warm-up.

Se regge a `ctx` corto ma sfora a `ctx` lungo → **FALLITA** (mai promossa per la media).
Registriamo anche i *falsi positivi a contesto corto* come categoria di rischio.

---

## 13. Rischi

Dettaglio in [`03_risks.md`](03_risks.md): workload a bassa località, costo del fallback sui miss,
overhead del predittore, validatore debole, e — il principale — **"sembra reggere a contesto corto
e collassa a contesto lungo"**.

---

## 14. Roadmap 3060 → 5090

1. **3060 (ora):** modelli che entrano comodi con offload; griglia ridotta; validatore + curve.
   Obiettivo: *esiste la regione?* e *come scala con la sparsità?* su ≥ 2 modelli.
2. **5090 (dopo i numeri):** modelli più grandi / sparsità più estreme, contesto fino a max,
   griglia piena, ripetizioni per barre d'errore.
