# Decisione di scope — track DSpark (2026-07-05)

Presa dall'utente dopo la correzione del brief (`--mtp` ds4 = baseline MTP-1, non DSpark)
e la scoperta che la macchina del primo pod aveva un guasto hardware critico.

## Cosa NON stiamo facendo
- NON reimplementiamo il drafter DSpark addestrato dentro ds4 (= Strada B / integrazione
  C-CUDA del backbone parallelo). È il pezzo "più complicato" e non è il nostro contributo:
  è già documentato dal paper.

## Cosa stiamo facendo (deciso)
**Strada A + twist expert-IO** = il nostro contributo originale, NON nel paper.
- Drafter: MTP-1 nativo di ds4 (quello che c'è già).
- Aggiunta: verifica confidence-scheduled sopra, nel regime **streaming** del 3060.
- Tesi paper-worthy: nel regime streaming-MoE il costo di verifica si ammortizza col
  blocco (−49% IO expert a k=8, misurato in `runs/ds4_routing_trace_smoke/`) → la lunghezza
  ottima del draft è più lunga che nel paper denso.

## Binari e GPU (deciso: A su pod economico, B su pod separato)
- **Strada A**: pod **3090 community** (sm_86 = 3060), $0.22/h. Corretto e NON inquina per
  ciò che il pod può misurare:
  - **acceptance-rate**: proprietà del modello (greedy argmax match) → TRASFERISCE al 3060.
  - **conteggi union-load** (expert unici/blocco = numeratore del 49%): proprietà del
    modello → TRASFERISCONO. Il pod prova MECCANISMO + CONTEGGI.
  - Regime streaming emulato con `--simulate-used-memory` (ds4_cli.c:1501) che blocca RAM
    per riprodurre la fame di memoria del 3060 (28GB) su macchina con più RAM.
  - ⚠️ Il guadagno **t/s** dell'IO NON è misurabile su NESSUN pod (banda NVMe + 28GB RAM =
    setup fisico del 3060). Quel claim finale resta sul 3060 reale.
- **Strada B (validazione paper, pod separato)**: NON il V4-Flash-DSpark (48 shard fp8,
  multi-GPU, fuori budget) ma il checkpoint offline **`deepseek-ai/dspark_qwen3_4b_block7`**
  (draft head minuscola) + Qwen3-4B target su un solo 3090/4090. Riproduce l'accepted-length
  della Tabella 1 del paper = tetto teorico del metodo. Accepted-length è GPU-indipendente →
  un pod capace non inquina. Serve l'harness DeepSpec (repo ufficiale non su HF; fork
  community su GitHub: `47thtechcorner/RayCodes_Deepspec`, `Extended-Systems-Intelligence/
  nemotron-dspark-recipe` — da verificare). Da deployare DOPO che A ha i numeri, per non
  correre due pod a lungo dentro il budget $1-2.

## Perché un pod PIÙ POTENTE inquina la Strada A
La tesi è il collo di bottiglia **IO da SSD del 3060**. Su GPU con VRAM grande (A100/H100
80GB) gli expert diventano residenti in VRAM → niente IO da risparmiare → il 49% svanisce.
Più potenza = più lontano dal regime da dimostrare. Per la Strada A la GPU giusta è il
3060 reale (o 3090 sm_86 solo per acceptance + correttezza union-load).

## Stato budget / pod (aggiornato 15:15 UTC)
- Pod #1 `o6ksysllgnpuxk`: GUASTO HARDWARE (alert RunPod) → terminato. Spiega gli
  `illegal memory access` visti sui run non-streaming.
- Pod #2 `oot30v9rb3ho8a` (machine gkckwlfw6fwt): rete 10MB/s anche con aria2c x16 →
  terminato (2h di download non giustificate a $0.22/h).
- Pod #3 `jr0c4j4484jwab` "dspark-A-candidate2" (machine 0qh6584rg5n2): deployato con
  `minDownload: 800`; speedtest reale 109MB/s, 251GB RAM → ATTIVO per Strada A.
- Lezione playbook: sempre `minDownload` nel deploy + speedtest da HF prima del download
  grosso.
- Track speso finora ≈ $0.6 (pod1 ~2h + pod2 ~35min + pod3). Saldo account $22.08
  (drenato anche dai 3 pod REAP, non nostri). Tetto autorizzato $1-2: ancora dentro,
  margine ridotto — pod B (Strada B Qwen3-4B) solo dopo i numeri di A.
