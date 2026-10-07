# B5 — meno nodi per layer nel grafo della finestra di verifica

Fronte B5 del lavoro «80 t/s a 131k con due schede». Fork: `Strata-2080Ti-core` @ 434ddca; worktree di lavoro
`C:\Users\imanu\source\repos\Strata-wt\b5`, branch `lab/b5-fusioni`.

## Conclusione in breve

Il grafo per layer ha ~38 nodi (GDN) e ~50 (QSA). Sulla catena critica del flusso principale ci sono 7 nodi per layer
che sono solo attese, copie o lanci quasi sempre vuoti, attaccati a un nodo vicino: si possono fondere senza toccare la
matematica (bit identici). Taglio previsto: **−7 nodi per layer = −112 sullo stadio 0 (711) e −224 sullo stadio 1
(1397)**. A ~2–3 µs per nodo sulla catena: **~0,5–0,8 ms per finestra (~2%)**. Non porta da solo a 80 t/s; è la parte
sicura del fronte. Le fusioni più grosse (lettura HC, conv+ricorrenza GDN, gate dell'esperto condiviso nel router)
toccano la matematica e restano fuori.

## Configurazione misurata (Daily + split)

`--layer-split 16 --trim-stage-weights`, `CUDA_VISIBLE_DEVICES=1,0` (stadio 0 = 3060 layer 0–15, stadio 1 = 2080 Ti
layer 16–47), `--pcie-mode auto` (= 2, copia per kernel), `STRATA_DF_BRANCH` acceso (default), esperto condiviso su
stream laterale (default), nessun `all_resident` (esperti CPU presenti), `device_plan` spento, `m_bal_` spento,
finestre di 2–2,4 righe, G = 1 (niente split di gruppo).

## Inventario: catena per layer (da `Verifier::record_window`, src/core/verify.cpp)

`[S0]`/`[S1]` = stream laterali `df_side_`, `[SH]` = stream dell'esperto condiviso; il resto è sul flusso principale.

### Mixer GDN (12 layer su 16 nello stadio 0, 24 su 32 nello stadio 1)

| # | nodo | kernel | file |
|---|------|--------|------|
| 1-3 | lettura HC attn | gr_norm/_split, gr_down/_staged, gr_up | fused_gr.cu |
| 4 | q8_1 di xm | native_quantize_q8_1_kernel | native_mmvq.cu |
| [S0] | a/b | gdn_ab_multi_kernel | verify_kernels.cu |
| [S1] | z | native mmvq (attn_gate) | native_mmvq.cu |
| 5 | qkv | native mmvq | native_mmvq.cu |
| 6 | conv + l2 | gdn_conv_l2_multi_kernel | verify_kernels.cu |
| 7 | ricorrenza + norma | gdn_step_norm_multi_kernel | verify_kernels.cu |
| 8 | q8_1 di y | native_quantize_q8_1_kernel | native_mmvq.cu |
| 9 | ssm_out | native mmvq | native_mmvq.cu |

### Mixer QSA (4 layer nello stadio 0, 8 nello stadio 1)

lettura HC (3) · q8_1 · [S0] mmvq q + norm_rope q (+fwht se kv_rot) · [S1] bf16 q-indexer + norm_rope · bf16 k-indexer ·
mmvq k · mmvq v · norm_rope k · copia coda indexer (copy_from_mapped) · kv_append_q8_steps · indexer_append_steps ·
block_scores · block_topk · kv_resolve · attn_chunk + attn_merge · gate · q8_1 · mmvq out ≈ 21 nodi.

### Parte MoE (tutti i layer)

| # | nodo | kernel | note |
|---|------|--------|------|
| 1-3 | lettura HC ffn | gr_norm, gr_down, gr_up | |
| 4 | router | bf16_f32_mmvf_multi_kernel (512 blocchi) | |
| 5 | top-10 | route_multi | |
| 6 | campanello | doorbell_publish_res_kernel | x e id verso l'host |
| [SH] | esperto condiviso | q8_1, gate, up, swiglu+q8_1, down, bf16 gate, sigmoid_scale | 7 nodi |
| 7 | q8_1 per gli esperti | quantize_q8_1_kernel (iq_kernels) | |
| 8 | **attesa A** | wait_flag_ge_kernel (1 thread) | il piano dell'host |
| 9 | **copia piano** | copy_i32_from_mapped_kernel (1×128) | |
| 10-12 | esperti VRAM | gu, swiglu_q8_1_entries, down | |
| 13 | **attesa B** | wait_flag_ge_kernel | in pcie_mode 2 B sale subito dopo A |
| 14 | **fetch PCIe** | fetch_blobs_kernel (384 blocchi, quasi sempre n = 0) | |
| 15 | **rebase** | rebase_ptrs_kernel | |
| 16-18 | esperti PCIe | gu, swiglu, down (4 righe di gruppi, quasi sempre vuoti: «PCIe 0.00») | |
| 19 | **attesa CPU** | wait_flag_ge_kernel | |
| 20 | **copia righe CPU** | copy_rows_from_mapped_kernel (n·K blocchi) | |
| 21 | **somma hit** | add_hits_kernel | |
| 22 | combine | combine_k10_vec4 | |

Conteggio: GDN ≈ 9 + 2 + 22 + 7 = 40, QSA ≈ 21 + 22 + 7 = 50; per lo stadio 0 12·40 + 4·50 + finestra (ingressi,
PLE, consegna) ≈ 711, coerente col grafo stampato (`STRATA_VERIFY_NODES`). Grassetto = nodi senza aritmetica.

### Dove va il tempo (profilo C-prof, split 32, ms/finestra divisi per 24 layer GDN della 3060)

waitA 58 µs (andata e ritorno dall'host), esperti VRAM 142, hc-read1+router 84, q8+qkv 65, out 47, z 44, condiviso 42,
waitB 18, waitCPU 16, copy+combine 14, PCIe 9, norm hc 16, conv 5, ab 8. Sulla 2080 Ti waitA è ~5 µs: lo stadio 1
è legato alla GPU, quindi lì ogni nodo tolto dalla catena conta per intero.

## Le fusioni scelte (in ordine di guadagno/rischio)

Ogni fusione dietro `STRATA_B5_<NOME>=1`, spenta di default; valgono solo nel percorso misurato (doorbell, non
`device_plan`, non `m_bal_`, non `remote_opt_`, `dec_batch`, n > 1 dove serve); altrove il codice resta quello di oggi.

1. **COMBINE** — attesa CPU + copia righe CPU + somma hit + combine → un kernel. Ogni (token, colonna) legge le 10 righe
   dalla sorgente giusta: riga hit = `0.0f + hit_out` (lo stesso arrotondamento di add_hits, `__fadd_rn`), riga CPU =
   memoria mappata; poi lo stesso ordine di combine_k10_vec4 (primo prodotto arrotondato, fmaf per esperto, + condiviso).
   `STRATA_B5_COMBINE=1`: copia+somma+combine (−2); `=2`: anche l'attesa (−3; ogni blocco del combine fa il polling).
   Bit identico. Il join dell'esperto condiviso passa prima del kernel fuso. `parts_` non viene più scritto: nessun
   lettore dopo il combine (escluso `neuron_trace_`, dove la fusione è spenta).
2. **WAITPLAN** — attesa A + attesa B + copia piano → un kernel (un thread attende A e B, `__threadfence_system`,
   poi i 128 thread copiano). Solo con `pcie_mode != 0`, dove l'host alza B subito dopo A (fetch_dma con n = 0).
   −2 nodi, bit identico.
3. **PCIEFETCH** — fetch_blobs + rebase_ptrs → un kernel. Il rebase scrive in un array a parte (non sovrascrive
   `ptr2` che gli altri blocchi stanno leggendo) e gli esperti PCIe leggono quello. −1, bit identico.
4. **DOORQ** — campanello + q8_1 per gli esperti → un kernel (blocco 0 = campanello come oggi, gli altri = q8_1 con lo
   stesso `q8_1_store`). −1, bit identico. Il fork dell'esperto condiviso parte dopo il kernel fuso (pochi µs dopo).
5. **HANDOFF** (per finestra, non per layer) — le 3 copie di consegna tra stadi in una `copy_from_mapped_multi`, e le
   3 in ingresso allo stadio 1 lo stesso. −4 nodi per finestra sulla giunzione tra le schede. Bit identico.

Riserva, solo se le prime danno misura: **ROUTER** (GEMV del router + top-10 con l'ultimo blocco che fa il top-10:
contatore atomico, −1, bit identico ma più invasivo per via di PDL e dei template).

Scartate: lettura HC in meno kernel (servono barriere di griglia), conv+ricorrenza GDN, q8_1 scritto dal produttore
(è STRATA_QFUSE: testo rotto su Turing), salto condizionale del ramo PCIe (nodi condizionali CUDA 12.4: troppo rischio
per il guadagno).

## Misura

- Un solo binario, bracci on/off con `--env STRATA_B5_*=1` e `--env STRATA_VERIFY_NODES=1` (conteggio nodi).
- Giudizio su ms/finestra a T medio simile, riga per stadio («decode stage»); t/s solo come contorno.
- Qualità: L01/L02 in prosa o codice normale, senza loop, rapporto parole distinte/totali ~0,5; per le fusioni bit
  identiche gli id generati devono coincidere con il braccio spento a parità di finestre (l'accettazione delle bozze
  dipende solo dai logit).

## Esito (6/10 sera) — misure fermate su ordine dell'owner

Codice: worktree `C:\Users\imanu\source\repos\Strata-wt\b5`, branch `lab/b5-fusioni`, non pushato. Binario di tutte
le prove: `20261004_routed_keep/build-b5-1` (sha bd6b0738…, contenuto = f1511df), fusioni spente di default.

| commit | fusione | nodi in meno / layer | stadio 0 (711) | stadio 1 (1397) |
|---|---|---|---|---|
| 0f8fd8f | WAITPLAN (attesa A + attesa B + copia piano) | 2 | −32 | −64 |
| 2cba1ee | PCIEFETCH (fetch_blobs + rebase) | 1 | −16 | −32 |
| ae1ec6e | COMBINE=2 (attesa CPU + righe CPU + hit + combine; =1 senza attesa: −2) | 3 | −48 | −96 |
| 5acb474 | DOORQ (campanello + q8_1 esperti) | 1 | −16 | −32 |
| f1511df | EDGE (copie di step/posizioni e consegna, per finestra) | — | −3 | −3 |
| | **tutte** | **7** | **596 (−115)** | **1170 (−227)** |

Il totale con tutto acceso è misurato (`STRATA_VERIFY_NODES`, finestre da 2 a 6 righe); il dettaglio per fusione è per
costruzione e torna esatto sul totale. Finestra da 1 riga: 713→646 e 1397→1266 (COMBINE vale solo da 2 righe in su).

ms/finestra (L01 / L02, T medio tra parentesi):

| braccio | priorità | L01 | L02 |
|---|---|---|---|
| B5-1off | HIGH | 32,97 (2,31) | 29,78 (2,00) |
| B5-2off | HIGH | 34,18 (2,46) | 30,10 (1,90) |
| B5-4off | Normal | 42,38 (2,53; CPU host 7,8 ms: disturbato) | 31,26 (1,91) |
| B5-4on | Normal | 35,76 (2,30) | 30,79 (1,83) |
| B5-5off | Normal | 31,92 (2,22) | 28,89 (1,91) |
| B5-5on | Normal | 33,86 (2,43) | 34,71 (1,92; CPU host 3,96: disturbato) |

Il guadagno atteso (~0,5–0,8 ms) sta sotto il rumore (±3 ms tra bracci identici): **nessun effetto misurabile** con
questo metodo. B5-1on, B5-2on, B5-3on rifiutati all'avvio da un msbuild.exe estraneo; B5-6on ucciso allo stop.

Qualità: tutti i testi L01/L02 accesi in prosa normale, nessuna ripetizione di 12-grammi, parole distinte/totali
0,37–0,42 (le spente 0,38–0,44; i riferimenti P-base 0,36–0,41). Identità bit a bit: per costruzione (stesse
operazioni nello stesso ordine, COMBINE nello stesso file di combine_k10_vec4 per gli stessi flag `--use_fast_math`);
non verificabile confrontando gli id tra corse, perché lo stesso binario spento non si ripete (P-base2 contro P-base3:
L01 diverge al token 113, L02 al token 9).

Verdetto: **nessuna fusione va su main per ora.** Restano sul branch di laboratorio, spente, finché il banco
deterministico non misura il loro effetto sullo stadio che toccano.

## Banco deterministico (6/10 notte) — NON PASSA

Ramo `lab/b5-fusioni` 472044c = fork main a0ebf74 + le 5 fusioni; binario `build-b5-m1` (sha c896b909…). Coppie
alternate spente/accese (tutte le fusioni: WAITPLAN=1 PCIEFETCH=1 COMBINE=2 DOORQ=1 EDGE=1), `det_force.sh` con
STRATA_FORCE_WINDOWS e `--pipeline-windows=2`.

`det_verdict.py DET-b5-off1b,DET-b5-off2b,DET-b5-off3 DET-b5-on1b,DET-b5-on2b,DET-b5-on3`:

| coppia | L01 spento → acceso (s) | L02 spento → acceso (s) | L01 % | L02 % | L01+L02 % |
|---|---|---|---|---|---|
| 1b | 15,45 → 15,18 | 16,43 → 17,19 | +1,7 | −4,6 | −1,5 |
| 2b | 14,94 → 14,91 | 16,30 → 16,36 | +0,2 | −0,4 | −0,1 |
| 3 | 16,18 → 15,05 | 16,34 → 17,17 | +7,0 | −5,1 | +0,9 |
| | | | | | **media −0,2 %** (soglia +2,7 %) |

Ripetizioni: coppia 1 rifatta (off1 è morto all'avvio prima dell'init del verificatore su CUDA1, a fusioni spente);
coppia 2 rifatta (off2 L01 ha perso la traccia delle finestre: 174 finestre di traccia, 525 finestre contro 521).
Anche off1b L01 ha perso la traccia (523 finestre): «lavoro identico» = False. Tutti e cinque i bracci accesi
riproducono il lavoro di riferimento (521/600). on3 ha un «0 MiB free»: la coppia 3 non è stata rifatta perché non
può cambiare l'esito (la 1b fallisce già su L02).

Nota: L02 acceso è bimodale (27,2 o 28,6 ms/finestra; 2 bracci accesi su 5 lenti), L02 spento sempre 27,2–27,4.
Non indagato (niente prove aperte). Verdetto: le fusioni B5 restano sul ramo di laboratorio, spente; main be4cf1c
non integrato.
