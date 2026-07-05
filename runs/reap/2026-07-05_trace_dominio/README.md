# Trace dominio Segnali — ds4 Flash 2-bit, gate-weights (patch 0006)

Run del 2026-07-05 su pod RunPod 3090 community (dettagli completi e costi: `meta.json`).

## Cosa contiene

- `trace_dominio.tgz` — fonte committata: 20 `trace_pNN_*.csv` (formato
  `pos,layer,n,e0..e5,w0..w5`), `warmup.csv` (scartata), `determinism_repeat_p00.csv`,
  log di generazione/build/regression. L'estratto `trace/` è gitignored.
- `prompts_manifest.json` — provenienza dei 20 prompt (raft_eval.jsonl, sha256; testi KB
  non committati qui).
- `meta.json` — pod, cmdline, metodo playbook, costi, findings operativi.

## Numeri chiave (fonte: meta.json + reap_mask_ds4_domain.json)

- 3155 token decode totali, 40 layer routed (3..42), **0 righe con pesi nan**.
- Validazione pesi: somma dei 6 pesi per riga ≈ 1.5 = `expert_weights_scale` Flash.
- Mask K50: `runs/reap/reap_mask_ds4_domain.json` — keep 128/256 per 40 layer,
  stima file potato **46.98 GiB** (target ~50 GB per i 64 GB RAM: centrato).
- Stabilità split-half del drop-set: overlap medio **0.8295** (min 0.7578) —
  `runs/reap/mask_stability_splithalf.json`.

## Findings operativi (per il playbook / prossimi pod)

1. **Greedy temp 0 NON è bit-riproducibile** su ds4 CUDA: la ripetizione di p00 diverge
   (1933/2720 righe con ID diversi). Le trace vanno trattate come campioni della
   distribuzione di decode; la robustezza si misura con split-half, non col diff.
2. **Il profiler upstream (`--expert-profile`/`DS4_EXPERT_HOTLIST`) è Metal-only davvero**:
   su build CUDA non si attiva (nessun log, nessun file). Il cross-check va fatto in altro
   modo (qui: invariante somma-pesi + split-half).
3. **Gate-check CUDA prima di scaricare il modello**: la prima macchina assegnata
   (q0nrurbibmwi) aveva CUDA rotto a livello container e RunPod la riassegnava a ogni
   deploy con gli stessi filtri; esclusa alzando `minVcpuCount`.
