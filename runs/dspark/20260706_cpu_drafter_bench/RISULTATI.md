# Bench 0013 — drafter MTP su CPU: fattibilità VERIFICATA

**Host**: workstation 3060 (WSL2, 16 core). **Domanda**: il forward del drafter MTP
può stare su CPU+RAM, liberando la VRAM dalla guerra statics/cache (M8)?

## Numeri (head_bench.c, Q8_0 blocchi-32 fedele, fp32 accumulate, OpenMP)
| | 4 thr | 8 thr | 16 thr |
|---|---|---|---|
| GEMV testa 129280×4096 (562MB) | 67.3 ms | **43.6 ms** | 43.5 ms |
| banda effettiva | 8.9 GB/s | 13.7 GB/s | 13.7 GB/s |

- Satura a 8 thread → **memory-bandwidth-bound** (la testa da 562MB Q8_0 va letta tutta
  per ogni draft). Kernel più furbo → forse ~35ms; ordine di grandezza fermo.
- **Draft completo stimato: ~47 ms/token** (testa + ~48MB di MoE 6-exp/attn/proj).
- Tipi verificati dal GGUF: output.weight Q8_0 (condivisa col main), expert MTP Q4_K.

## Conto economico (coi numeri M8 committati)
- Ciclo streaming 3060 ≈ 2-3 s → drafter CPU a draft-2 = +60-90ms/ciclo ≈ **+2-3%**;
  a draft-4 ≈ 188ms ≈ <10%.
- In cambio: la VRAM del drafter torna all'expert cache = **+30-60%** (base cache-on
  0.90-1.06 vs cache-off 0.65, M8). Elimina 0011+0012 e il bug accounting WSL2
  (il drafter non tocca più CUDA).
- GPU drafter misurato ~25-33ms/ciclo: il CPU è 2-3× più lento MA il costo è
  trascurabile rispetto al ciclo, e la risorsa era oziosa.

## Verdetto
**GO per il design 0013** (drafter CPU, env `DS4_MTP_CPU_DRAFTER=1`): 2-4 sessioni,
rischio correttezza nullo per costruzione (il target verifica tutto). Nota: per il
drafter DSpark vero (3 layer) il costo triplica il blocco ma NON la testa (condivisa):
stima ~60-70ms — ancora verde. Caveat bench: scale f32 anziché f16 (+~5% banda),
kernel naive; stima conservativa.
