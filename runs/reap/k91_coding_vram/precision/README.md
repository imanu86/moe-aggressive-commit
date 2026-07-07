# Test precisione: q2 vs q2-q4 — bit o taglia? (2026-07-07)

> Mandato SPEX: (Q1) il soffitto sul task-hard e' i BIT o la TAGLIA? (q2→q4 il livello sale?)
> Se resta L1 → e' la taglia → mixed-precision NON salva. (Q2) se la precisione aiuta la qualita',
> la paga in fit? Varianti che ds4 gia' spedisce (niente build). Task-hard = todo-app interattiva
> (dove q2 dava L1). Due assi: QUALITA' (L0-L3, full no-mask) + FIT/VELOCITA' (segmentato cache=400).
> q4-full ESCLUSO (~150-170GB > 130GB disco pod; SPEX: "salta se non ≥256GB").

## Tabella a due assi
| variante | GB | **QUALITA' (hard)** | seg 1-64 | seg 65-256 | seg 257+ | completamento (1300 tok) |
|---|---:|:---:|---:|---:|---:|---:|
| **q2** (baseline) | 81 | **L1** | 1.74 | 2.18 | 1.27* | ~12.4 min |
| **q2-q4** (layer 37-42 in Q4) | 98 | **L1** | 1.49 | 1.58 | 1.54 | ~14.8 min |

*(q2 seg 257+ poco affidabile: il run n=576 ha beccato uno stallo di rete, prefill anomalo 1.67.)*

## Q1 — bit o taglia? → LA TAGLIA (la precisione non alza il soffitto)
**Entrambi L1.** Aggiungere 4-bit agli ultimi 6 layer NON sposta il livello sul task-hard: il
todo-app resta "si apre ma le feature sono rotte" (bottone add/delete non cablati, form no) in
entrambe. → il soffitto L1 sul task complesso e' **capacita'/taglia-bound, non quantizzazione-bound**.
Il mixed-precision parziale non salva. (Caveat: q2-q4 aggiorna solo 6/40 layer; il q4-pieno non e'
testabile — non entra — ma il trend e' scoraggiante: la precisione parziale non fa nulla.)

## Q2 — la precisione la paghi in fit? → SÌ
q2-q4 (98GB) e' piu' lento di q2 (81GB) su ogni segmento (1.49-1.58 vs 1.74-2.18 t/s) e completa
il task-hard in **14.8 min vs 12.4** (+19%). Esperti piu' grossi (4-bit sui 6 layer) → piu' byte
da streammare → piu' lento. **Lose-lose**: nessun guadagno di qualita' + costo di velocita' e tempo.

## Verdetto per il paper
Su questo task-hard la strada **mixed-precision (q2→q2-q4) e' chiusa**: non alza il soffitto (L1→L1)
e costa velocita' (+19% tempo). Il collo del todo-app e' la **taglia/capacita' del DeepSeek-V4-Flash
a 2-bit**, non i bit degli ultimi layer. Coerente con: il ginocchio graded mostra che il modello
regge task stretti (JSON/Python L3) ma non quelli larghi/complessi (frontpage-hard L1 anche full).
Per alzare il soffitto serve piu' capacita' (modello piu' grande) o full-q4 su hardware con disco
≥200GB, NON un rattoppo di precisione parziale. Artefatti: `q2/`, `q2q4/` (quality_hard.txt, summary).
Costo: download q2-q4 98GB (~5 min a 330 MiB/s), 2 pod ~35 min.
