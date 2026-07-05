# Piano eval REAP-ds4 — pruned vs full vs random (deliverable 4, track `reap/ds4-domain-prune`)

> PIANO, non esecuzione. Presuppone: `reap_mask_ds4_domain.json` (deliverable 3) e il design
> `docs/REAP_DS4_design.md` (Stage A bias-mask §2). Budget: dentro il tetto $1-2 TOTALE del track
> (spesa trace già sostenuta); la fase generativa completa è opzionale e fuori budget → richiede ok.
>
> **REVISIONE ESECUZIONE 2026-07-05** (ok utente: "non abbiamo un budget se non temporale"):
> (a) vincolo di costo rimosso per la fase eval → **3 pod sm_86 in parallelo, uno per config**
> (full/reap/rand), niente apply→restore sequenziale: ogni pod applica la bias-mask alla propria
> copia; il confronto resta appaiato sul TESTO (teacher-forced sugli stessi token; il jitter
> numerico cross-run/cross-macchina si media su 850 tok/chunk). Runner: `run_eval_one.sh` (in
> `runs/reap/2026-07-05_eval_biasmask/`). (b) `--perplexity-file` scora in decode ~1.5 t/s →
> i 30k tok/config del §3 sono infattibili in tempi utili: cap **-n 850/chunk dom (×4) e
> -n 800/chunk gen (×2)** ≈ 5k tok/config; col design appaiato il SE sul delta-NLL resta ~1e-2,
> ampiamente sotto gli effetti attesi (criteri §3 invariati).

> **ESTENSIONE PAPER-GRADE 2026-07-05** (mandato SPEX-main): ppl v2 con ≥10 chunk/config +
> bootstrap CI95, random multi-seed {0,1,2}, reap sul generale, dose-response K25/50/70
> (`run_eval_v2.sh`, `reap_eval_summary_v2.py`, corpora in `2026-07-05_eval_biasmask_v2/`).
> Più t/s bench 3060-proxy mask ON/OFF × RAM {60,28}GB (`run_tps_hog.sh`).
>
> **Metodologia RAM-capping (t/s) — realtà del container RunPod:** l'idea originale
> `--simulate-used-memory` (flag ds4 nativo) **FALLISCE**: usa `mlock`, e i container RunPod
> non hanno `CAP_IPC_LOCK` (`mlock: Cannot allocate memory`). Anche la **scrittura su cgroup**
> (`/sys/fs/cgroup/*/memory.max`) è **negata** (cgroupfs read-only, no delega). L'unico
> meccanismo che funziona senza privilegi è un **hog-process**: un processo Python che alloca
> e tocca `CG_GB − avail` GB di RAM anonima; con **swap=0** sul pod le pagine restano residenti
> e non evictabili → la page-cache del modello mmap'd si comprime → streaming SSD come su una
> workstation con `avail` GB. I **DELTA** (mask ON/OFF, 60/28) trasferiscono al 3060; gli
> **ASSOLUTI** no (banda/SM del 3090 ≠ 3060) — dichiarato in ogni numero.

## 0. Principio

Tutte le eval di qualità si fanno in **Stage A (bias-mask)**: si scrive `-1e9` nel bias di
selezione (`exp_probs_b.bias`) degli expert potati su una copia (o in-place con backup dei
40×1024 byte) del gguf 2-bit. Selezione e pesi diventano **identici** al modello fisicamente
potato (design §1.1/§2) senza surgery, su runtime ds4 stock. Le tre config condividono lo stesso
file modello: full → patch REAP → restore → patch RANDOM → restore (un solo download da 80.76 GiB).

## 1. Config (tutte dalla STESSA mask json — nessun disallineamento possibile)

| Config | Fonte keep-list | Note |
|---|---|---|
| `full` | — | baseline, file intatto |
| `reap_k50` | `keep` della mask (g-only conditional mean) | K=50% sui 40 layer non-hash |
| `rand_k50` | `random_control.keep` della mask (seed loggato) | stesso K per-layer, controllo obbligatorio |

Opzionali a budget permettendo: `freq_k50` (ranking per soli hits dalla stessa trace — ablation
"la pesatura g conta?", design §4.2 mitigazione b); `reap_k25` (dose-response).

## 2. Verifica meccanismo (V0, PRIMA di ogni metrica — costo ~2 min)

Con bias-mask REAP attiva: run generativa breve (1 prompt dominio, `-n 64`) con
`DS4_SPEX_TRACE_ROUTING` attivo → **asserzione: ogni expert-id nel CSV ∈ keep-list del layer**.
Un solo id fuori lista = il meccanismo non regge, STOP (niente metriche da un meccanismo rotto).
Bonus: `exp_probs_b` restore → run identica alla baseline (diff CSV routing = zero righe diverse).

## 3. Metrica primaria: perplexity teacher-forced (`--perplexity-file`, nativa ds4)

`ds4 --perplexity-file FILE` calcola NLL teacher-forced su testo raw (ds4_cli.c:790, prefisso
fisso 32 tok). Nessuna generazione → costo ~prefill; su pod con modello in RAM è la metrica che
il budget consente.

- **Corpus DOM**: concatenazione dei 152 item raft_eval (system+user+gold), ~140k token; tagliato
  a **30k token** (`-n 30000`), stesso file per tutte le config. Sorgente:
  `bonus-kb/.../ft/raft_eval.jsonl` (mai committato qui; sha256 nel meta.json).
- **Corpus GEN**: testo italiano generico (wiki-it, ricostruibile con
  `scripts_pod/build_general_it.py`), stesso budget 30k token — quantifica il costo dom-vs-gen
  (F3/ledger: atteso peggio del dominio, va DICHIARATO non nascosto).
- Per config: 1 run (teacher-forced deterministico; niente mediana necessaria — etichetta
  comunque cold/warm da log).
- Output per run: log completo + nll/ppl → `runs/reap/<data>_eval_biasmask/` + `meta.json`
  (GPU, cmdline, sha file modello patchato, costo pod, balance prima/dopo).

**Criteri pre-registrati** (prior: 30B A23 ppl-ratio K50 REAP 0.99×, 235B C6/C8 massa 4.3×>rand 2.1×):
- successo: `reap_k50` dom ≤ **1.10×** ppl full; `rand_k50` dom ≥ **1.5×** full e > reap_k50.
- red flag: `rand_k50 ≈ reap_k50` → a K50 la selezione non discrimina su ds4 (→ provare K60/70
  o sospettare la saliency g-only: eseguire ablation freq_k50 prima di conclusioni).
- `gen`: atteso 1.5-2.5× full per reap_k50 — misura del "turbo Segnali, non modello generale".

## 4. Metrica secondaria: field-accuracy Segnali (generativa, N=152 gold)

Come A1-A12/ledger: greedy, thinking OFF, estrazione 7 campi, metrica `overall_excl_validity`
(validity=0 strutturale, nota ledger). Logica di grading: `bonus-kb/.../ft/eval_extract.py`.

- **Costo stimato**: 152 prompt × ~150-250 tok decode. Con modello in RAM su 3090
  (~1-2 t/s decode osservati da misurare in trace-run): **4-8 h/config** → 3 config = fuori budget.
- **Decisione**: fase 2 SOLO sulla config vincente della ppl, su **subset N=50** stratificato
  (~1.5-2.5 h ≈ $0.4-0.6) e SOLO se il budget residuo del track lo consente; N=152 completo
  rimandato a dopo l'ok dell'utente (o alla workstation 64GB quando arriva la RAM, gratis).
- Controllo random anche qui (stesso subset N=50) se si esegue.

## 5. Sequenza operativa on-pod (stessa sessione, un download)

1. deploy 3090/A5000 sm_86 (playbook; gate-check CUDA con torch PRIMA di scaricare — lezione
   pod q0nrurbibmwi, vedi meta trace).
2. build stock+0001..0006, download modello, scp corpora + mask json + tool bias-mask.
3. `full`: ppl dom, ppl gen.
4. `reap_bias_mask_ds4.py --apply reap` (backup bias) → **V0 (§2)** → ppl dom, gen.
5. `--restore` → `--apply random` → ppl dom, gen → `--restore`.
6. scp log/risultati → `runs/reap/<data>_eval_biasmask/` → commit → **podTerminate + verifica**.

Tool prerequisito da scrivere: `scripts/reap_bias_mask_ds4.py` (design §2: parser gguf già in
`scripts/gguf_inspect_ds4.py`; patch in-place dei 256 float F32 di `blk.N.exp_probs_b.bias`
per i layer potati, `--apply reap|random --maskfile ... / --restore` da backup `.bias.bak`).

## 6. Cosa NON si misura qui (fuori scope, dichiarato)

- t/s wall-clock (non trasferiscono dal pod, playbook §4.3) — il claim velocità arriva dalla
  workstation 64GB con file fisicamente potato (Stage B).
- qualità del modello fisicamente potato Stage B: attesa identica a Stage A per costruzione;
  la conferma bit-level si fa con la "identity surgery" (prune K=0 → logits identici) quando
  il tool Stage B esiste.
- healing/fine-tune post-prune (REAP paper): fuori scope track; se ppl delude a K50, è la
  leva successiva (cfr. I10: reroute 8.2% a keep50 è il danno pre-healing).
