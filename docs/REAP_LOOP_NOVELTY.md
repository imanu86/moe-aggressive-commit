# REAP-loop v1 — verdetto novelty (per il paper, reviewer target: antirez)

> Novelty check avversariale a 3 fronti (workflow `w8ms2k2n1`). **Verdetto: PARZIALE.**
> ⚠️ **CAVEAT CITAZIONI**: alcuni arxiv-id sotto sono **post-cutoff (2026)** e **NON verificati** dagli agenti (2604.*, 2606.*,
> LoopGuard, LPSR, SpecRA). Potrebbero essere confabulati. **Aprire l'abstract reale (WebFetch) PRIMA di citarli** —
> una citazione inesistente davanti ad antirez azzera la credibilità dell'intero paper. Stesso caveat per l'axis-flip (2606.15453) già nel ledger.

## Verdetto in una riga
**Nessun singolo mattone è nuovo.** L'unica novità che regge a un reviewer severo è la **COMPOSIZIONE closed-loop** + il **finding causale dell'asimmetria** + il **segnale gate-mass-su-potati**. REAP-loop v1 è un'**integrazione originale**, non una primitiva nuova → si rivendica come **sistema + finding causale**, MAI come "abbiamo inventato X".

## La frase esatta rivendicabile (il contributo)
> "Un loop di potatura-per-dominio a inference-time, **training-free e senza update dei pesi**, che opera sugli esperti
> routati di un MoE reale (DeepSeek-V4-Flash, 256 expert/layer) dentro un motore di expert-offload: sul singolo stream
> (a) parte dal modello FULL con contesto sano, (b) apprende una bias-mask dagli esperti effettivamente instradati nei
> primi ~150 token, (c) la stringe a gradini fino a keep-9% via bias −1e9 al gate, (d) la riallarga/rewinda quando la
> **massa di gate che ricade sugli esperti potati** segnala l'onset di degenerazione. Finding causale centrale:
> un'**ASIMMETRIA** misurata — la stessa mask a keep-9% raggiunge coerenza se la sparsità è stretta a gradini mentre lo
> stato di contesto/KV è sano, e collassa all'istante se applicata a freddo; la leva è **la salute del contesto**, non un
> recovery via gradiente."

## Cosa NON rivendicare (o antirez lo smonta) — con riferimento
| Pezzo | Prior-art | Nota |
|---|---|---|
| "impara la mask dalla sessione / primi token" | **GRIFFIN** (arXiv:2404.01365, ICML'24) | fa esattamente questo, training-free |
| "graduale/a gradini evita il collasso" (schedule) | **Zhu & Gupta** (arXiv:1710.01878) | folklore IMP/layer-collapse |
| "test-time/dynamic pruning per prompt" | **μ-MoE** (arXiv:2505.18451) | già rivendicato lì |
| "adaptive top-k / dynamic-k per token" | DynMoE/AdaMoE (2406.13233), Ada-K, LExI (2509.02753) | **tu NON lo rivendichi — tienilo così** |
| "working-set di sessione a runtime" | MoE-Infinity (2401.14361), HOBBIT (2411.01433), AdapMoE | ⭐ ma per **prefetch/cache/offload, NON toccano il routing** → **questa è la tua linea di demarcazione, marcala netta** |
| "rewiring/re-routing on-the-fly" | arXiv:2510.14853 | |
| "detect onset → rewind/KV-edit" | LoopGuard (2604.10044), LPSR (2604.18567) | ⚠️ **id da verificare** |
| "periodicità via autocorrelazione" | SpecRA (OpenReview xVO4BqmzVD) | ⚠️ da verificare |
| "entropia/spettro attivazioni = health-signal" | EigenTrack (arXiv:2509.15735) | gate-entropy = folklore MoE-training |
| "REAP" come naming | arXiv:2510.13999 | è compressione one-shot **statica** = l'opposto; non spacciare continuità di metodo |

## Framing verso antirez + i 3 controlli obbligatori
**Apri DISARMANDO** le sue obiezioni: *"Sappiamo che GRIFFIN impara già la mask dalla sessione, che il gradual-pruning è vecchio come Zhu&Gupta 2017, e che detect-onset→rewind esiste. Non rivendichiamo nessuno di questi. Rivendichiamo tre cose specifiche e verificabili: la composizione closed-loop, l'asimmetria causale, e il segnale gate-mass-su-potati."*

**PER SOPRAVVIVERE servono 3 controlli** (senza, è confounder/cherry-picking e antirez ha ragione):
- **(A) Stessa mask a caldo vs a freddo** → isola "salute del contesto" da "mask migliore". Senza questo la causalità dell'asimmetria è aneddotica.
- **(B) Metrica di qualità DOWNSTREAM** (perplexity o task-acc, NON solo Jaccard/hit-rate) alla soglia keep-9%. Senza, "coerente" è cherry-picking.
- **(C) Lead-time del sensore** → quanti token PRIMA di un repetition-detector testuale (TTR) si accende la gate-mass-su-potati. Se non **precede**, il sensore non è un contributo.

→ Questi 3 controlli sono il work-item che rende il REAP-loop v1 pubblicabile. Sono misurabili sul setup K91 esistente.
