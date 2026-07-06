# Cold vs Warm — soluzione candidata + principi (corso 2026-07-05/06)

> Output del corso-tutor cold/warm (chat separata). Progettato con l'utente sui numeri reali del repo.
> Diventa il futuro **§6 del paper** ("orchestrating the warm working-set"). Ogni numero ha fonte nel repo.

## Il modello mentale (i numeri che governano tutto)
- Anatomia per-token: 240 load expert/token (40 layer × 6), ~1.6 GiB toccati. Latenze: VRAM ~0 · **RAM ~1ms · SSD ~15ms**.
- Formula cold-start (coverage *c* del profilo in page-cache): **`t_token ≈ 943ms + 240·(1−c)·15ms`** → c=100%→1.06 t/s, 95%→0.89, 80%→0.60. Fonte forma-profilo: `runs/ds4_routing_trace_smoke/routing_trace_count64.csv` (il working-set SATURA: token1=240 exp nuovi, token65=+14).
- Asimmetria 15:1 → **sforare 7% in GB costa ~20% in t/s**; a pattern ciclico + LRU è un *dirupo* (thrash), non un degrado.
- **Il regime warm è SYNC-BOUND, non bandwidth-bound**: PCIe tetto single-stream ~11 t/s; misurato stage-1a: sync-path 9288 sync/1491ms vs event-path 216/25.7ms (patch 0002/0003 sono il coltello). Muovere 1.6GiB/token ≈ 85ms → il collo è la sincronizzazione per-copia, non la banda.

## Principio d'architettura (la regola d'oro)
**Prima DIFENDI il regime (stare warm), poi ALZI il tetto.** Ordine leve: concentrazione/RAM (allontana dal dirupo) finché il working-set non è comodamente residente → POI precisione SPEX (post-async) per alzare il tetto warm.
Corollario: *ogni tier lo nasconde un predittore con orizzonte ≥ della sua latenza.* Hidden-state = orizzonte 1 layer (~ms) → nasconde RAM→VRAM. Profilo offline = orizzonte infinito → unica cosa che nasconde l'SSD (15ms). Il predittore hidden NON può nascondere l'SSD (troppo tardi) — per quello serve il profilo.

## SOLUZIONE CANDIDATA — orchestrazione del warm-set (7 punti)
1. **Profilo expert per specialista**: trace routing (patch 0005) su ≥20 prompt reali; validazione **leave-one-out**, coverage *pesata per load*. Pre-reg: **c ≥ 0.95** (sotto → il profilo da solo non basta).
2. **Ri-idratazione all'avvio del burst**: lettura del profilo **ordinata per offset nel gguf, parallela** → ~22 GiB in page-cache in **~9s** (vs minuti di demand-fault a 0.15 t/s). Da verificare con microbench (banda sorted+parallel vs 15ms/load seriale @ QD1).
3. **Triage sempre caldo** (profilo piccolo, pinnato): la sua decisione **È** il segnale di prefetch → carica il profilo dello specialista **DURANTE il decode del triage** (l'SSD è idle in quel momento: banda gratis, latenza nascosta).
4. **Burst in batch** (N fino a ~50; limite reale = KV/attivazioni su 12GB, da misurare) **+ spec-dec a blocchi**: union expert per step, miss residui scoperti insieme e risolti con load **async paralleli**, mai seriali.
5. **Precondizione impianto**: path async (0002/0003) per uccidere il sync per-copia — vedi sopra, il warm è sync-bound.
6. *(Opzionale)* **HOBBIT-style**: expert low-bit sul miss residuo — unica leva che tocca la QUALITÀ (dosabile, ortogonale).
7. **Pre-reg finale**: metrica = t/s **aggregato** su burst di 50 segnali; target **≥10 aggregato / 3-5 per stream**; baseline = one-at-a-time.

## LA SCOPERTA GROSSA: il percorso ai 10 t/s è il BATCH, non il single-stream
Single-stream, anche con async+spec-dec, realistico ~**3-6 t/s** (sync-bound, non banda). Il salto a ≥10 lo dà il **batched decode** perché i costi cambiano struttura: a ogni step si carica la **union** degli expert dei N stream (sub-lineare, satura sul working-set del dominio) mentre i token/step crescono lineari. Stima (con concentrazione REAP): N=20 → ~18 t/s aggregato, N=50 → ~28 t/s. **+ prompt condiviso** (i 50 segnali hanno lo stesso template → prefill una volta, + K70 prefill +87%).
⚠️ **GAP DI MOTORE: ds4 oggi NON fa batched decode.** È il work-item più impattante emerso, e calza a pennello sull'uso reale (la pipeline Segnali processa i draft in batch).

## Leve secondarie valutate (verdetti)
- **FT router-only per concentrazione**: possibile (gate matrices piccole), proxy-first su Qwen-30B. NB: il negativo Qwen A25/A26 è sub-expert *weight-space* (FT non compatta i neuroni), NON risponde alla domanda routing-concentration (non misurata). Idea gemella: FT per *predicibilità* (più località temporale → SPEX più preciso) — letteratura quasi vuota.
- **RAID 0**: solo DOPO che le letture sorted+parallel saturano il singolo NVMe (oggi usi ~450MB/s di ~3GB/s, QD1 bloccante = una corsia su tre). Ri-idratazione 22GiB: ~9s → ~4.5-5s con stripe. Ultimo in ordine cheap-first; il rischio-dato è irrilevante (gguf riscaricabili).

## Work-item generati (task nel main)
- Profilo pre-warming + ri-idratazione sorted-parallel (misura coverage leave-one-out + microbench banda).
- **Batched decode in ds4** (gap motore → percorso ai ≥10 t/s aggregati; il pezzo più grosso rimasto).
