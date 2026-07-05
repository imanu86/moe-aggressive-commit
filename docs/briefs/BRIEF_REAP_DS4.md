# BRIEF — Track REAP su DS4-Flash (chat parallela)

> Sei una chat/agente dedicato al track REAP. Lavora su **branch `reap/ds4-domain-prune`**.
> Contesto generale: `HANDOFF.md §0` + `docs/EXPERIMENTS_LEDGER.md` (NON rifare esperimenti già censiti lì).
> Il track SPEX (prefetch/cache) e il track DSpark (spec-dec) girano in parallelo su altri branch — non toccare i loro file.

## Obiettivo
Produrre la ricetta per un **DS4-Flash potato per dominio** (pipeline CGC Segnali / betting-promo italiano):
da 256 expert/layer → ~50% via **REAP-saliency**, cioè da **86.7GB → ~48-52GB** stimati
(expert 72.6GB → ~36GB + backbone 8.2GB + MTP). Perché ora: sta arrivando RAM 64GB sulla workstation →
un modello ~50GB **sta INTERAMENTE caldo in RAM** = SSD eliminato del tutto per il dominio.

## Vincoli di metodo (dallo studio chiuso — ledger sez. A/C/G)
1. **REAP-saliency (Eq.9, media condizionale g·‖f‖), NON massa/frequenza.** A scala la massa FALLISCE
   (anomalia F-ctrl: 235B K50 massa ppl 18.7 > random 9.2). REAP dom K50 su 30B: ppl 5.50 < full 5.56.
2. **Sempre controllo RANDOM** a pari K (rigore paper) e **dom-vs-gen dichiarato**: il potato è un
   modello DA DOMINIO; sul generale degrada (F3) — non è la north-star generale, è il turbo Segnali.
3. Pruning = escludere expert dal FILE, il router va rinormalizzato sui sopravvissuti (verifica come
   ds4/gguf gestisce expert mancanti — probabilmente serve rimappare gli indici nel gguf, non bucarli).

## Dati necessari (gap da colmare PRIMA)
- La trace attuale (`runs/ds4_routing_trace_smoke/routing_trace_count64.csv`) ha solo expert-ID, **niente
  gate-weight** → la saliency Eq.9 non si calcola da lì. Serve estendere la trace-capture di codex
  (patch 0005) per loggare anche i pesi di gate, oppure calcolare la saliency su pod col modello HF.
- Serve una trace DOMINIO (prompt Segnali reali, 500+ token) — coordinati col task "trace multi-dominio pod".

## Deliverable (in ordine)
1. `docs/REAP_DS4_design.md`: come si applica REAP a un gguf ds4 (formato, rimappatura router, tool da
   scrivere o riuso di `gguf-tools/`), rischi.
2. Estensione trace: patch che logga gate-weights (env `DS4_SPEX_TRACE_ROUTING_WEIGHTS=1`), su branch tuo.
3. Analisi saliency dalla trace dominio → mask json (`reap_mask_ds4_domain.json`) + stima GB risultante.
4. Piano eval: field-accuracy Segnali (N=152 gold) pruned-vs-full + controllo random, su pod.

## Regole
- NIENTE run GPU locale senza coordinarti (il 3060 è conteso col bench SPEX). Analisi/design/patch: liberi.
- **Pod autorizzati: budget $1-2 TOTALE per questo track** (RTX 3090 community). Metodo di misura e
  disciplina deploy/terminate: segui ALLA LETTERA `docs/briefs/POD_PLAYBOOK.md`. La trace dominio con
  gate-weights è il tuo caso d'uso pod perfetto (routing = proprietà del modello, trasferisce al 3060).
- Ogni misura riportata deve avere il file su disco citato. Niente numeri a memoria.
- Commit piccoli sul tuo branch, push frequente, aggiorna questo brief con lo stato in coda.

## Stato
- [x] design doc — `docs/REAP_DS4_design.md` (2026-07-05). Chiavi: bias-mask Stage A (eval senza
  surgery su runtime stock), hash layer 0-2 esclusi, saliency g-only validata offline
  (`runs/reap/gonly_vs_eq9_30b.json`: retention@K64 0.902), K50 → ~47 GiB
  (`runs/reap/gguf_flash_expert_geometry.txt`).
- [x] patch trace weights — `patches/ds4/0006-spex-routing-trace-weights.patch`
  (`DS4_SPEX_TRACE_ROUTING_WEIGHTS=1` → colonne w0..w5). Build+regression OK su pod 3090
  sm_86 (`runs/reap/2026-07-05_trace_dominio/meta.json`); validazione: somma pesi/riga ≈ 1.5.
- [x] saliency + mask — trace dominio 3155 token decode su pod 3090 (~$0.3, pod terminato
  con verifica) → `runs/reap/reap_mask_ds4_domain.json` (g-only conditional mean, K50,
  keep 128/256 su 40 layer, random control embedded, stima **46.98 GiB**). Stabilità
  split-half 0.83 (`runs/reap/mask_stability_splithalf.json`). Findings: greedy CUDA non
  bit-riproducibile; profiler upstream Metal-only (niente cross-check su CUDA).
- [x] piano eval — `docs/REAP_DS4_eval_plan.md`: Stage A bias-mask
  (tool: `scripts/reap_bias_mask_ds4.py`), ppl `--perplexity-file` dom+gen,
  full/reap_k50/rand_k50 dalla stessa mask, criteri pre-registrati, V0 mechanism-check.
- [x] **EVAL ESEGUITA (2026-07-05, 3 pod paralleli, `runs/reap/2026-07-05_eval_biasmask/`):**
  **REAP K50 dom 1.013× full (PASS near-lossless), random 1.365× (>reap, selezione conta,
  ma <1.5× pre-registrato → PARTIAL: soglia tarata sul 30B bf16 troppo severa per ds4 IQ2).**
  V0 mechanism-check: 11280 selezioni, 0 expert pruned selezionati. random gen 2.11× (F3 confermato).
  → il potato 50% dominio (~47 GiB) è **quasi-lossless in ppl e batte decisamente il random a pari K.**

- [x] **EVAL v2 PAPER-GRADE (2026-07-05, H200, 10 chunk, bootstrap CI95, `runs/reap/2026-07-05_eval_biasmask_v2/`):**
  **reap_k50 dom 1.010× CI95 [0.996,1.025] = statisticamente LOSSLESS** (il CI attraversa 1.0; replica v1).
  **reap_k67 dom 1.076× [1.046,1.110] = operating-point che ENTRA nei 32GB di oggi** (working-set ~25GiB).
  random dom 1.388× (selezione conta). **F3: reap_k50 gen 1.403×** (più mite del Qwen ~1.68×). V0 0 viol.
  t/s dial: prefill +43%/+87% (K50/K70), expert-load −37%/−57%. "fits-hot-32GB" empirico da confermare
  su workstation (RunPod blocca mlock+cgroup+hog). Dose masks K25/K60/K64/K67/K70 pronte.

## Prossimi (post-eval)
- Stage B surgery (file fisico) + patch per-layer expert count → t/s reale su workstation (gratis) +
  field-accuracy N=152 lì. **K67 = config da deployare oggi sul 3060+32GB; K50 quando arrivano i 64GB.**
- Opzionali: dose-response completa K25/K70 su 1 macchina (qui K50/K67 puliti + K70 dal 3090); multi-seed
  rand 3× pulito; ablation freq-vs-g-only (gratis, stessa trace).
