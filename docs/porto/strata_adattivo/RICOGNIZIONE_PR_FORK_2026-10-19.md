# Ricognizione PR e fork di Strata dopo la 0.1.45 — 19 ottobre 2026

Sola lettura con `gh` e `git` locale: niente GPU, niente build, niente commenti né PR su GitHub. **Compilato no, installato no, provato no**
per ogni leva elencata qui: i numeri sono quelli dichiarati dagli autori (hardware indicato), tranne dove scrivo «nostro».
Segue `RICOGNIZIONE_PR_FORK_2026-10-13.md` (fatta prima della 0.1.44).

Fonti: `Niko1221/Strata` (tag, release, commit `v0.1.43..v0.1.45` = 529 non-merge, 899 PR aggiornate dal 12/10 lette per titolo, ~110 per corpo e
commenti del maintainer), 2 854 fork dall'API (489 con push dopo il 13/10 e almeno 30 min dopo la creazione, tutti scansionati: elenco branch e
`compare main...fork:branch`, 958 branch con commit propri dopo il 10/10, 487 che non sono la testa di una PR), confronto con
`stack/INDEX.md` e `docs/UPSYNC_MAIN.md` (§7 per gli interruttori) di `lab/upsync-main`, con `MULTICHAT.md` di `lab/multichat45` e con
`corse_2080ti/20261019_replay/RISULTATI.md`.

Sigle: **M** = portata a mano da upstream in una release (upstream chiude o lascia aperte le PR e le porta conservando l'autore: «chiusa» non
vuol dire «respinta»), **A** = aperta, **F** = solo in un fork, **base** = già in 0.1.45 (quindi nella nostra base), **pila** = nostra patch
`stack/NN`, **lab** = portata su `lab/multichat45`, **bw** = bitwise (stessi bit del percorso di default), **nb** = cambia i bit (arrotondamento o
formato), **S** = stima mia, **M(nostro)** = misurato da noi.

## 0. Conclusione

- **Upstream non si è mosso dopo la 0.1.45.** `main` = `477ac13c` (commit del 16/10 20:39 UTC, ultimo push 17/10 06:50), nessun commit oltre il tag
  `v0.1.45`, nessun tag né release nuovi (ultimi: `v0.1.45` 17/10, `v0.1.44.1` 14/10, `v0.1.44` 13/10, `v0.1.43.1` 12/10). Unici branch: `main` e
  `rc/0.1.30`. La base di `lab/upsync-main` è quindi ancora aggiornata. Nessuna PR risulta «merged» nel flag di GitHub (le porta a mano il maintainer).
- **PR dal 13/10**: 553 create (#2196–#3128), 488 aperte, 65 chiuse (nessuna con flag merged). Per tema: 140 report di benchmark, 133 AMD/Intel/Mac,
  135 serve/setup/doc/web, **145 motore CUDA o generali** (lette tutte per titolo). In più 346 PR più vecchie con attività dopo il 12/10; le nostre 11
  sono tutte ancora aperte.
- **Dentro la 0.1.44/0.1.45 è finito molto di ciò che il 13/10 era «da portare»**: gruppi in pipeline al posto di `--batch-mtp` (a0116b27),
  `STRATA_PIPED_CONCURRENT` (#2326, lettura accanto al decode), `STRATA_PIPED_READ_PIECE` (#2050), `--prefill-pipe` (#1441), `STRATA_SPLIT_OVERLAP`
  (#1120), `STRATA_PIN_BY_NEED` (#1905, ma solo una GPU), serie sm_75 di rafatxf, #1821/#1825, #2145, `STRATA_PCIE_BALANCE`, gli interruttori batch di
  havok2-htwo (#2364), `--prompt-cache-spread`, `--conversation-cache-park-gain`, `STRATA_DEQUANT_WIDE` **acceso di default su sm_86** (vedi §3).
- **La leva nuova più importante per il nostro carico è #3095** (`STRATA_PW_WITH_BATCH=1`, +23/−5 righe, 18/10): con `--batch` upstream spegne
  `--pipeline-windows` per tutto il motore, quindi anche la richiesta sola perde la sovrapposizione fra le schede. Da noi è la voce «solo» di
  `MULTICHAT.md`: 50–55 t/s con `--batch 4 --batch-groups 2` contro 64,5 del Daily (M(nostro)). L'autore, su 2x RX 6900 XT, recupera +20% (16–25%).
  Se regge, la config multi-chat smette di costare la chat singola.
- **Per il carico reale (3 agenti DSH, lettura = 78,5% del tempo del server) la leva è il prefill di richieste corte e medie**, non il decode:
  `agents:3:R` ha il prefill al 65–80% del wall e letture a 300–420 tok/s (chunk da ~1,6k). Due PR piccole attaccano proprio il costo fisso per chunk:
  **sibnick K37** (raccolta MMQ in blocchi, −12/−15% di prefill da 0,5K a 32K, uscite identiche, 94% di lanci in meno) e **#2774** (chunk corti,
  473 → 315 ms a 177 token).
- **Sul prefill di stadio 1 (sm_75)**: #3085/#3104 (aperte) estendono i kernel fusi int8 degli esperti a IQ3_XXS/IQ4_NL su Turing; in 0.1.45 coprono
  solo il pack Q2_0, quindi `STRATA_PF_FUSED_SM75=1` **da noi oggi non fa niente** sull'IQ3_XXS (da `moe_fused_iq.cu`, `native_supported()`).
- **Errore nostro scoperto**: l'arm `g-copy` di `MULTICHAT.md` usava `STRATA_COPY_BATCHSYNC`, che non esiste. Il nome upstream è
  `STRATA_SLOT_COPY_BATCHSYNC`. L'arm era già segnato contaminato; da rifare con il nome giusto.
- **Fork**: nessun fork ha un'idea nuova su decode a due schede eterogenee paragonabile a quelle del 13/10 (NTRYourWaifu v7/v8 = nostra patch 17,
  nessun push dopo il 12/10). Le cose nuove sono su cache di conversazione/prefisso e multi-tenant (§4).

## 1. Upstream dopo la v0.1.43: cosa è arrivato che prima non c'era

(Elenco dalle liste commit `v0.1.43..v0.1.45`; filtrato su CUDA, split, batch, prefill, cache. «lab» = presente su `lab/multichat45`.)

| cosa | commit / PR | stato | ce l'abbiamo | interruttore | guadagno dichiarato (hw) | valore per noi | sforzo |
|---|---|---|---|---|---|---|---|
| gruppi in pipeline battono `--batch-mtp` sullo split | a0116b27 (#2038) | M | base, in uso (`--batch 4 --batch-groups 2`) | default | 4 richieste 62,3 → 85,2 (2x A4000) | già incassato | — |
| lettura del prompt su thread proprio mentre i gruppi decodificano | bc90e1ac… (#2326) | M | base + lab, misurata: `c-conc` agents:4 28,6 contro 26,7 | `STRATA_PIPED_CONCURRENT=1` | stallo 11,9 → 0,8 s, stesso lavoro −6,4% (2x 5090) | alto, già in config 2 del replay (3,1–3,5x) | — |
| lettura a pezzi fra le finestre | 5d6bf8d4 (#2050) | M | base + lab, `r5-piece` | `STRATA_PIPED_READ_PIECE=N` | stallo 17,7 → 9,2 s (2x A4000) | misurata, nessun guadagno chiaro (r5: 20,6 contro 19,6 disturbato) | — |
| chunk dimensionati per la pipeline | 125025a7 (#1441) | M | base, **non misurata** | `--prefill-pipe R` / `STRATA_PREFILL_PIPE` (nb) | 10K token +17–19%, 4K +8% (2x A4000); 4 GP100 +62% | medio-alto: la 3060 limita il chunk | zero |
| hand-off con flag su GPU | 56146c4c (#1120) | M | base | `STRATA_SPLIT_OVERLAP=1` | neutro su A4000; +30% su 2x 7900 XTX | nullo: spento accanto a `--pipeline-windows` | — |
| piano di pin per bisogno | f087f780, ab6bce05 (#1905) | M | base | `STRATA_PIN_BY_NEED=1` | prompt +5–7% (3090 Win) | nullo: solo una GPU (codice: «Single GPU, profile given») | — |
| calibrazione PCIe per layer | 04be241a (#1548) | M | base | `STRATA_PCIE_BALANCE=1` | — | nullo: una GPU, senza `--batch` | — |
| punti di controllo spaziati | a7d4b754 (#1959) | M | base | `--prompt-cache-spread` | 10,2 s contro 40 s su modifica a 6 turni (2x CMP) | basso: nostro riuso già 93% con 16 slot | zero |
| park rate-limited | d9cb22d2 (#2265) | M | base | `--conversation-cache-park-gain N` | turni 2–8 6,06 → 5,07 s (3060) | basso-medio, bw | zero |
| serie Turing | 996b9f84…7f1964a6 | M | base, misurata: SM75_PERF +1,2% (M(nostro)) | `STRATA_SM75_PERF=1` | decode +5–6%, prompt fino a +30% (2080 Ti) | già provata | — |
| `STRATA_DEQUANT_WIDE` default su sm_86 | 5f843a92 | M | base | `=0` per spegnere | TTFT 150–450 token −11–15% (3060) | **regressione possibile a 4K**: §3 | zero |
| piano di split per coppia sbilanciata | 3b848837 (#2644) | M | base | automatico | prompt +52% (A4000 sbilanciate) | nullo: noi usiamo split esplicito 16 | — |

## 2. PR e idee non ancora in upstream, per tema

### 2a. Multi-chat, batch, slot

| PR | cosa | stato | ce l'abbiamo | interruttore | guadagno dichiarato (hw) | valore per noi | sforzo |
|---|---|---|---|---|---|---|---|
| [#3095](https://github.com/Niko1221/Strata/pull/3095) | pipeline-windows mantenuto per la richiesta sola accanto a `--batch` | A | no | `STRATA_PW_WITH_BATCH=1` | +20% decode singolo (2x 6900 XT) | **alto**: ripara il −15/−25% della chat singola nella config multi-chat; S: ~64 t/s di solo con batch 4 | **piccolo** (+23/−5, `generate.cpp`); parità da verificare (il verificatore a parità opposta condivide la sessione dello stadio) |
| [#2985](https://github.com/Niko1221/Strata/pull/2985) | bozze MTP nei gruppi in pipeline | A | lab (portata 18/10) | `STRATA_PIPED_MTP=1`, `--batch 2 --batch-mtp` | 4x 3090: 4 flussi più alto del default senza MTP | M(nostro) `r11` same:2 82,6 contro 64,5 di b2, solo 54 contro 53; richiede 1 slot per gruppo | fatto |
| [#3103](https://github.com/Niko1221/Strata/pull/3103) | `SPLIT_MTP_BATCH` accanto a `PIPED_CONCURRENT` | A | no | `STRATA_PIPED_CONCURRENT_SMB=1` | prompt +3–8% (da #2163) | basso-medio | piccolo (+67) |
| [#2989](https://github.com/Niko1221/Strata/pull/2989) | prompt con immagini letto accanto agli slot | A | no | con `PIPED_CONCURRENT` | stallo 6,0 → 0,1 s (2x 5090) | basso: DSH non manda quasi immagini (S) | piccolo |
| [#2527](https://github.com/Niko1221/Strata/pull/2527), [#2528](https://github.com/Niko1221/Strata/pull/2528), [#2843](https://github.com/Niko1221/Strata/pull/2843) | slot che tengono la conversazione: politica di piazzamento per lunghezza e età, checkpoint di ramo | A (898+1 859+2 361 righe) | no (lab ha #2589 e #2384) | `STRATA_SLOT_CACHE_AFFINITY`, `STRATA_SLOT_CHECKPOINTS` | richieste «classifier» di Claude Code da 15–27 s a 0; 3x A4000 6 slot 180 t/s | medio: Claude Code classifier è un nostro caso, ma il riuso del replay è già 93% con la RAM; senza risposta del maintainer | **alto** |
| [#2589](https://github.com/Niko1221/Strata/pull/2589) | un lavoro breve non prende lo slot di una conversazione lunga | A | lab | `STRATA_SLOT_EXPIRE_S` | turno successivo 14,8 → 0,3 s; −17…−21% di rilettura | in `cfg1` del replay | fatto |
| [#2384](https://github.com/Niko1221/Strata/pull/2384) | checkpoint di turno conservati slot→solo→slot | A | lab | — | letture complete evitate (2x 3090, parallel 2) | in lab | fatto |
| [#2325](https://github.com/Niko1221/Strata/pull/2325) | radici di system prompt tenute a parte in `--batch` | A | no | `--prompt-cache-roots N` | rilettura 20–35 s di 79K evitata | basso: il nostro prefisso fisso è 9 218 token | piccolo |
| [#2822](https://github.com/Niko1221/Strata/pull/2822) | prelazione per richieste corte su un solo motore | A (5 582 righe, quasi tutto Python) | no | `solo_priority: true` | TTFT corto 20,1 → 0,56 s, aggregato −3,75% | basso: noi usiamo `--batch` | alto |
| [#2109](https://github.com/Niko1221/Strata/pull/2109) | priorità delle richieste in `--batch` | A (maintainer: «serve review») | no | campo `priority` | — | basso-medio se Claude Code e DSH convivono | piccolo |
| [#1524](https://github.com/Niko1221/Strata/pull/1524) | finestre larghe condivise | A, **rifiutata** (non applicabile alla base) | no | — | 1,31x–2,07x a c=4 (5090) | invariato rispetto al 13/10 | alto |
| [#2738](https://github.com/Niko1221/Strata/pull/2738) | budget MTP diviso per slot | chiusa | no | — | **−22% misurato da terzi su 2080 Ti** | scartata | — |
| fork yi-sudo `3b8e8202` | fino a D bozze per slot | F | no | `STRATA_BATCH_MTP_D` | **nessun guadagno** (D=3: 199 contro 246) | scartata | — |
| fork Canyun `3f50685d` | righe di verifica assegnate per tasso di accettazione | F | no | `STRATA_BATCH_MTP_DYNAMIC=1` | non dichiarato | basso | medio |

### 2b. Prefill e TTFT

| PR / fonte | cosa | stato | ce l'abbiamo | interruttore | guadagno dichiarato (hw) | valore per noi | sforzo |
|---|---|---|---|---|---|---|---|
| fork [sibnick](https://github.com/sibnick/Strata/commit/97b83332) `97b83332` (branch `sibnick-per-stage-prefill-chunk`) | raccolta MMQ degli esperti residenti in blocchi: 108 078 → 6 934 lanci su 1 977 token | F | no | opt-in (flag in CMake +4 e `prefill.cpp` +51/−7) | **prefill −11,9/−12,9/−13,3% a 502/994/1 977 token, −14,7% a 32K**, uscite identiche, byte copiati uguali (CMP 170HX + RTX 3090, Linux) | **medio-alto**: chunk da 0,5–2K sono il nostro carico; S: −8…−12% sulle letture brevi | **piccolo**; da riscrivere sulla 0.1.45; serve parità |
| [#2774](https://github.com/Niko1221/Strata/pull/2774) | chunk sotto `stream_all_min`: esperti residenti con ≤8 righe fuori da MMQ, sul kernel di decode raggruppato | A (+107) | no | `STRATA_PF_DIRETTO_MAX`, `STRATA_PF_ROUTE_PRIOR` (nb) | 177 token 473 → 315 ms, 500 668 → 470, 900 826 → 677 (5070 Ti, Q2_0 non nativo) | medio: il 74% delle letture di un agente è < 1 000 token; il pack nostro è IQ3_XXS (da verificare se «canonico») | piccolo-medio |
| [#3085](https://github.com/Niko1221/Strata/pull/3085), [#3104](https://github.com/Niko1221/Strata/pull/3104) | kernel fusi int8 degli esperti anche per IQ3_XXS/IQ3_S/IQ2/IQ4_XS su Turing; gate/up IQ3_XXS e down IQ4_NL coperti | A | no (in 0.1.45 solo Q2_0) | `STRATA_PF_FUSED=1 STRATA_PF_FUSED_SM75=1` (+ `STRATA_PF_FUSED_NATIVE_SM75=1` in #3104) (nb) | PP 509 → 606 tok/s (+19,2%, RTX 2060); +11,5% con i prestiti (2080 Super Max-Q 8 GB); #2145: 2080 Ti 98K 58,3 → 53,3 s | **alto per lo stadio 1** (layer 16–47: la maggior parte del prefill); KL da misurare | piccolo (`moe_fused_iq.cu` 27/−9) |
| [#3105](https://github.com/Niko1221/Strata/pull/3105) | prestiti di VRAM per richiesta (MTP, testa, ripetizione) | A (+520) | no | `STRATA_PREFILL_ELASTIC_LOAN` e altri | +0,1% da solo; +11,5% con #3104 (2080 Super) | basso-medio | medio |
| [#2968](https://github.com/Niko1221/Strata/pull/2968) | stager con anello pieno e 8 thread quando gli esperti non sono tutti pinnati (WDDM) | A (+49/−10) | no | `STRATA_STAGE_RESIDENT=0\|1` | 32K non pinnato +5–16% (NVFP4, 64 GB) | **solo se** il pin è limitato: il Daily registra tutta l'arena (43 GB, nota del 5/10); i banchi con `ARENA_PIN_GIB=8` sì | piccolo |
| [#2672](https://github.com/Niko1221/Strata/pull/2672), [#2673](https://github.com/Niko1221/Strata/pull/2673), [#2776](https://github.com/Niko1221/Strata/pull/2776) | avvio Windows: toccare l'arena con 16 thread prima di `cudaHostRegister`, caricare i densi con 8 thread, thread di caricamento | A | no | `STRATA_ARENA_PREFAULT`, `STRATA_DENSE_UPLOAD_THREADS`, `STRATA_ARENA_THREADS` | avvio −5,1 s, −1,2 s, 5,3 → 6,5 GiB/s | basso (solo avvio, decode e prompt invariati) | piccolo |
| [#3072](https://github.com/Niko1221/Strata/pull/3072), [#3086](https://github.com/Niko1221/Strata/pull/3086) | prompt diretto e prefetch su Windows in modo RAM scarsa | A | no | `STRATA_PROMPT_DIRECT=1`, `STRATA_MMAP_PREFETCH` | primo token +33% | nullo: abbiamo 96 GB e l'arena intera | — |
| [#2761](https://github.com/Niko1221/Strata/pull/2761)/[#2830](https://github.com/Niko1221/Strata/pull/2830) | i 675 MiB di esperti del drafter prestati al prompt | A | no | `STRATA_MTP_ROOM_MIN=N` | **negativo** nei numeri dell'autore (3 080 token: 16,2 → 20,6 s) | scartata | — |
| [#2829](https://github.com/Niko1221/Strata/pull/2829), [#2833](https://github.com/Niko1221/Strata/pull/2833), [#2831](https://github.com/Niko1221/Strata/pull/2831) | tetto di chunk per stadio, slot lasciati al prestito, riga di diagnostica per chunk | A | no | `STRATA_PREFILL_MAX`, `STRATA_PREFILL_KEEP`, `STRATA_PREFILL_STAGES=1` | −6,9% su un caso; il tetto per stadio perdeva nel suo test (94,8 contro 91,7 s) | basso; `PREFILL_STAGES` è utile come strumento | piccolo |
| [#2385](https://github.com/Niko1221/Strata/pull/2385) | obiettivo del pianificatore dello split per il prompt | A | no | `--layer-split-objective` | prompt +26/+35% sullo split bilanciato contro l'auto (3080 Ti + V100) | nullo: split esplicito | — |
| fork vizdatom `2e69b6db` | prefill «layer-major» a super-chunk: ogni esperto una volta per super-chunk | F (+1 005 righe) | no | `STRATA_PREFILL_LAYER_MAJOR=1` | traffico esperti ~509 → ~79 GB su 12,9K token (Ryzen) | basso: **non per layer split**, chunk nostri già 6,4K | alto |
| fork zhou51320 (config 2x 2080 Ti) | nessuna novità di codice: usa le leve sm_75 di upstream + `BF16_TC`, `PF_FUSED(_SM75)`, `PA_V2T`, `SELECT_SIMT`, `--adapt-async 1 --adapt-every 2`, `--aux-cpus auto` | F | in parte | env | nessun numero | solo come cartina: stesse leve già in lista | — |

### 2c. Decode, split, MTP, speculativa

| PR / fonte | cosa | stato | ce l'abbiamo | interruttore | guadagno dichiarato (hw) | valore per noi | sforzo |
|---|---|---|---|---|---|---|---|
| [#2690](https://github.com/Niko1221/Strata/pull/2690) | le righe esperto CPU «leggere» di un layer si uniscono alla metà FFN del layer dopo | A (+441/−17, `verify.cpp`) | no | `STRATA_VERIFY_DEFER_CPU=1` (+`_BELOW`) | +15,4% / +17,1% (3080 10 GB sola, CPU pesante) | basso-medio: da noi hit 97%, CPU 1,2 ms per layer-finestra; S: ≤+2% | medio |
| [#2529](https://github.com/Niko1221/Strata/pull/2529), fork dsovsyannikov `4dec82bf`, fork android-imdad `ef42c2fd` | taglia le bozze MTP con il tasso atteso per ms (finestra adattiva, probabilità cumulata, aiuto del lookup) | A / F | no | `STRATA_MTP_ADAPTIVE`, `STRATA_SPEC_ADAPT`, `STRATA_SPEC_CUM`/`_LOOKUP_Q` | +0,8% (codice) / +3,2% (russo) laptop 5090; +1,4/+5,8% su 7900 XTX | basso-medio: oggi `--spec 4`, `--spec-min-p`; uscita invariata | piccolo |
| [#2591](https://github.com/Niko1221/Strata/pull/2591) | conteggio di probabilità corretto con bozze filtrate | A (+7 325) | no | `STRATA_SPEC_PROB` | +1,0% (IC −0,4…+2,3) | nullo: richieste a T=0 | — |
| [#2427](https://github.com/Niko1221/Strata/pull/2427), [#3022](https://github.com/Niko1221/Strata/pull/3022) | HC_Q8 anche sullo split, solo le righe dello stadio | A | no | `STRATA_HC_Q8=1` | VRAM libera per esperti | nullo: nb, e i nostri pack non sono UD-* | — |
| fork svgop (`STRATA_FUSE_HITS`, `POOL_DIET`, `COHORTS=2`) | combine con hit sommati, meno attese di repark, due verificatori da 3 slot | F (125 commit) | no | env | FUSE_HITS +4,35% M1 e POOL_DIET +4,06% (una scheda, ~210 t/s); COHORTS=2 6 conc 298,5 contro 244–260 (+15–18%) | basso-medio: hardware ad alta velocità, non split; COHORTS richiederebbe 276 righe in `generate.cpp` | medio / alto |
| fork noon-at-cgn `d84da294` (opt-pipe, 7/10) | `--pipeline-windows 2` accanto a `--batch` con controlli a runtime e pool KV di drain | F (vecchio) | no | `pipeline_windows 0\|2` per richiesta | 2x 3080 20 GB: documentato in `DUAL_3080_Q4XL.md` | precedente di #3095, stesso obiettivo | — |
| [#1798](https://github.com/Niko1221/Strata/pull/1798), [#1461](https://github.com/Niko1221/Strata/pull/1461), [#492](https://github.com/Niko1221/Strata/pull/492) | expert-parallel (SYCL), coppia peer elastica, catena MTP su altra scheda | A / chiusa | no | — | +13–15% (2x Arc), +55% a 2 richieste (NVLink) | invariato rispetto al 13/10 (idee per `lab/pipeline2`) | alto |

### 2d. Cache di conversazione e prefisso condiviso

Il maintainer ha scritto su più PR che **sceglierà un solo disegno di persistenza su disco per la 0.1.46** (#1090, #1331, #1480, #1937, #2077, #2119: «not measured here»): per questo conviene non portare nulla finché non esce. Le nostre patch 05, 14, 16 (`--prompt-cache-file`, `PREFIX_DISK_MULTI`, `CONV_DISK`) restano le nostre.

| PR / fonte | cosa | stato | interruttore | guadagno dichiarato (hw) | per noi |
|---|---|---|---|---|---|
| [#2510](https://github.com/Niko1221/Strata/pull/2510) (shahrokhzargarpour, 12 699 righe, chiusa) | livello durevole su disco, cascata caldo→freddo, **segmenti per stadio**, scala di ripristino | chiusa, nessuna risposta | opt-in | non confrontabili | l'unica con segmenti per stadio dello split; troppo grande |
| [#2915](https://github.com/Niko1221/Strata/pull/2915), [#2590](https://github.com/Niko1221/Strata/pull/2590) | park/ripristino via file di sessione; **sessione salvata e ripristinata con layer split (formato v3)** | A | opt-in | ripristino dopo riavvio (2x 5060 Ti Windows) | #2590 è la più vicina a ciò che serve per il riavvio con 2 schede; effort medio |
| [#2351](https://github.com/Niko1221/Strata/pull/2351) | montaggio del prefisso K/V di una conversazione parcheggiata, scala di checkpoint di stato | A (+6 268; maintainer: «lo programmeremo rebasato su 0.1.44.1») | `--cache-suffix-reuse`, `--prompt-cache-state-every` | rilettura 98,4% evitata, 3,4 contro 45,2 s | utile con modifiche a metà storia (compattazione di Claude Code); alto sforzo |
| [#2247](https://github.com/Niko1221/Strata/pull/2247) | stato di esecuzione in bf16 nei file di sessione | A (maintainer: fuori dal giro velocità) | `--session-state-codec bf16` | −50% del checkpoint | nb; basso |
| [#2443](https://github.com/Niko1221/Strata/pull/2443), [#2962](https://github.com/Niko1221/Strata/pull/2962), [#2409](https://github.com/Niko1221/Strata/pull/2409), [#2640](https://github.com/Niko1221/Strata/pull/2640) | sfratti senza perdere prefissi fissati, restituzione di RAM, OOM in ripristino, griglia geometrica | A | opt-in | correttezza / RAM | bassi |
| fork UltimateBoomer (`b3e9b085`, `efc9ff7e`), fqqdc (`09d83375`), xrip, page1, G0-0000 | file di park aggiornati sul posto, coda viva N, append differenziale su disco, uscita a SIGTERM | F | opt-in | 245K: 2 332 → 227 MiB per cambio chat (fqqdc); ~236 MB di stato scritti in meno per park | indirizzati alla scelta 0.1.46; non portare ora |
| fork ScrambledEggsOnToast (1 181 commit avanti, eterogeneo sm_70+sm_86) | **store di prefissi condivisi con autorizzazione per tenant**, prefill impacchettato per proprietario, sospensione/ripresa del prompt, piano di esecuzione risolto | F | opt-in | la loro sospensione è **negativa** (7,6 contro 8,9 tok/s, non promossa) | da leggere come idee (`bed10c18`, `55e5ac50`, `5616b222`, `383681eb`); non portabile come blocco |
| fork TheHubUser4860938 `7ceccf88` | cartuccia K/V di prefisso «permanente», ripristino in 0,1 s | F | — | ~0,1 contro ~0,5 s per 2K | solo con server a memoria; un solo slot, spento con `--batch` |
| fork itsXactlY `6d423a6f` | un'unica finestra K/V host per sessione principale e slot | F (+401) | — | non dichiarato | basso-medio, ripresa di slot più economica |

Il prestito di prefisso tra conversazioni (#1164, `c9e571e0`, `2b296987`) è in 0.1.45 ma, come già in `MULTICHAT.md`, `stages.empty()` lo spegne con lo split: da noi non agisce.

### 2e. Windows/WDDM e memoria RAM/VRAM

| fonte | cosa | stato | per noi |
|---|---|---|---|
| [#2968](https://github.com/Niko1221/Strata/pull/2968), [#2963](https://github.com/Niko1221/Strata/pull/2963) | arena non interamente pinnata: stager largo; RAM pinnata a fette quando `cudaHostAlloc` è rifiutata (32K 9,9 → 6,7 s) | A | solo se il pin è limitato; la nostra arena è registrata intera |
| [#2522](https://github.com/Niko1221/Strata/pull/2522), [#2201](https://github.com/Niko1221/Strata/pull/2201)/[#2399](https://github.com/Niko1221/Strata/pull/2399) | VRAM elastica per scheda di uno split (#533) | A | sovrapposta alla nostra `--elastic` (#1117, aperta) |
| [#3037](https://github.com/Niko1221/Strata/pull/3037) | copie di snapshot Windows/WDDM via memoria pinnata | A | correzione HIP; per CUDA non applicabile (S) |
| [#2253](https://github.com/Niko1221/Strata/pull/2253) | il cancello RAM rilascia l'heap (glibc) | A | Linux |
| [#1130](https://github.com/Niko1221/Strata/pull/1130) | limiti di commit dopo allocazione fallita | A | robustezza |
| 13/10, §2g | clock P5 e `nvidia-smi -lgc/-lmc` (#1748) | invariato | **non riletto qui**: nel lab esistono `DET-p2-pstate1/3` del 4/10; i numeri vanno riletti prima di decidere |

### 2f. Confronti con altre coppie

| fonte | hardware | dato |
|---|---|---|
| [#2976](https://github.com/Niko1221/Strata/pull/2976) | 3x 2080 Ti 22 GB, Linux, 0.1.45, Q4_K_XL 262K | primo report sm_75 sulla 0.1.45 |
| [#2662](https://github.com/Niko1221/Strata/pull/2662)/[#2665](https://github.com/Niko1221/Strata/pull/2665) | 2x 2080 Ti, doppio Xeon lento | finestra 70 → 38 ms con lo split, decode 62,2 → 75,1 (250 W: 90,8) |
| [#2593](https://github.com/Niko1221/Strata/pull/2593) | 3090 + 3060 (x4), Linux, 0.1.43 | coppia sbilanciata, entrambi gli ordini |
| [#2643](https://github.com/Niko1221/Strata/pull/2643) | 4060 Ti + 3060, sweep `layer_split` | `auto` dava 3 layer alla 3060 (poi corretto da #2644) |
| [#2439](https://github.com/Niko1221/Strata/pull/2439) | 5080 + 4070 Ti | la scheda sola batte entrambi gli ordini dello split (−30/−55% prefill) |

## 3. Interruttori opt-in della 0.1.45 che non abbiamo ancora misurato

Ricerca: nessuno dei nomi sotto compare nelle nostre misure (`HANDOFF*.md`, `RESULTS.md`, `MULTICHAT.md`, `RISULTATI.md`), tranne dove indicato.
Env nel campo `"env"` della config; i flag vanno in `args`. Tutti spenti salvo dove scritto. **bw/nb** secondo la documentazione upstream
(`DETAILS.md`, `BATCHING.md`, `MULTI_GPU.md` della 0.1.45).

### 3a. Decode e attenzione

| interruttore | cosa | bw/nb | dove agisce da noi | dichiarato | come provarlo |
|---|---|---|---|---|---|
| `STRATA_QSA_SPLIT_ATTN=1` (#1888) | attenzione di decode divisa in blocchi sul percorso int8 mma | **nb** (KL 0,0016, pavimento 0,0012) | **solo 3060** (sm_80+, KV int8) | +2,8% / +3,5% (3060 / A4000) | `"env": {"STRATA_QSA_SPLIT_ATTN":"1"}`; 131k, B-A-B + 3 aghi |
| `STRATA_HC_REQ8=1` (#1262) | proiezioni HC in int8 + scala per 32 | **nb** (KL 0,0018) | entrambe; **conflitto**: la patch 18 (`HC16_SM75`) lo rifiuta con errore | −0,2% / +2,2% decode, più slot | solo da solo, senza `HC16_SM75` |
| `STRATA_HC_UPMIX=1` (#1370) | HC up e `gr_mix_r` in un kernel | bw (sulla loro porta) | **3060** (sm_80+) | prompt +0,6% / +0,4% | env |
| `STRATA_CPU_IQ_ALL_EXACT1=1` (#1415 #1544) | righe esperto a 1 token in AVX-2 con l'ordine di ggml | **bw** | CPU Ryzen 5800X (AVX-2): ammessa; **non con `STRATA_IQ_MT_MIN=1`** (il banco lo imposta) | IQ3_XXS −5% (Zen 2) / **+1% (Zen 3)**, decode +0,4…0,5% | richiede banco senza `IQ_MT_MIN=1`; S: ~0 |
| `STRATA_VERIFY_ASYNC_LAUNCH=1` | lancio del grafo su thread a parte | bw | diagnostica; non per finestre in pipeline | — | non provare |
| `STRATA_PA_V2T=1` | attenzione prompt v2 (registri) | **nb** secondo la doc (anche se #2146 dice bitwise) | 2080 Ti | prompt +5,2% a 98K | env (vedi 3b) |

### 3b. Prompt e TTFT

| interruttore | cosa | bw/nb | dove | dichiarato | come provarlo |
|---|---|---|---|---|---|
| `STRATA_DEQUANT_WIDE=0` | **spegne** il dequant largo, ora **acceso di default su sm_86** | bw | 3060 | acceso: TTFT 150–450 token −11–15% (3060); **#3109: −10–15% del prompt a 4K su sm_89, instabile** | A/B `=0` contro default, prompt da 4K e da 1–2K; zero costo |
| `--prefill-pipe 1` o `R` / `STRATA_PREFILL_PIPE=R` (#1441) | chunk pari fra gli stadi | **nb** (cambia i confini) | split a 2 stadi | 10K +17–19%, 4K +8%, 2K/28K invariati (2x A4000) | `--prefill-pipe 1` poi R=768/1536/3072 (come `--calibrate`); prompt 4K/10K/30K/131K |
| `STRATA_HANDOFF_PIPE=P` (P 2–16) | consegna del chunk al secondo stadio in P pezzi su thread persistente | bw (solo schedulazione, secondo `BATCHING.md`) | split, prompt | non dichiarato per 2 stadi | `STRATA_HANDOFF_PIPE=4` |
| `STRATA_PF_FUSED=1` | esperti del prompt fusi in int8 per i pack nativi | **nb** | **3060** (sm_86) copre i pack IQ nativi; sulla 2080 Ti solo Q2_0 (con `_SM75=1`), **quindi per IQ3_XXS oggi inerte su stadio 1** | IQ2_XS +12% a 4K, +3% a 32K | env su 3060; 2080 Ti dopo #3104 |
| `STRATA_PF_FUSED_SM75=1` | idem su Turing, Q2_0 | nb | 2080 Ti | #2145: +9% su 2080 Ti | inerte con IQ3_XXS (non provare prima di #3104) |
| `STRATA_PROMPT_ATTN_IMMA=1` (#1367) | attenzione prompt int8 su tensor core INT8 | nb a livello di arrotondamento (KL al pavimento) | **3060** | lettura +2,5% | env |
| `STRATA_PREFILL_HELP=1` | la scheda ferma calcola una quota degli esperti nel prompt corto | nb | split | TTFT turni brevi +14…46% | **già nel lab** (`r6-help`: TTFT p50 5,95 contro 6,4–7,2 s ma arm DISTURBATO): da ripetere pulito |
| `STRATA_REFILL_PARTS=1` | rifornisce gli slot presi in prestito dal GGUF mappato | bw | solo GGUF letto in loco | −0,1…0,3 s a fine prompt | poco probabile da noi (arena) |
| `-DSTRATA_MMQ_TAB=ON` + `STRATA_MMQ_DIRECT=1`, `STRATA_MMQ_GROUP_SORT=1` | MMQ legge gli esperti residenti nei loro slot | bw | richiede **ricompilazione** | letto nella tabella batch di havok2-htwo | build separata; costo di compilazione, non di codice |
| `STRATA_ARENA_PIN_GIB=N` | tetto di registrazione dell'arena | bw | solo se non pin totale | — | il Daily registra tutta l'arena: A/B inutile; per i banchi di lab (8 GiB) cfr. #2968 |
| `STRATA_PIN_BY_NEED`, `STRATA_PCIE_MIN1`, `STRATA_PCIE_BALANCE` | — | — | **inapplicabili**: una GPU (codice) | — | non provare |
| `STRATA_SPLIT_OVERLAP`, `STRATA_POOL_UMWAIT`, `STRATA_ARENA_THP`, `STRATA_PROMPT_DIRECT`, `STRATA_PROMPT_ATTN_Q4_TC` | — | — | inapplicabili (spento con `--pipeline-windows`; Zen 3 senza WAITPKG; Linux; Linux; KV Q4) | — | non provare |

### 3c. Solo con `--batch` (config multi-chat; tutti bw, cambiano la schedulazione e non ciò che si calcola, salvo `PA_*`)

| interruttore | cosa | stato nostro | come provarlo |
|---|---|---|---|
| `STRATA_SLOT_COPY_DIRECT=1` + **`STRATA_SLOT_COPY_BATCHSYNC=1`** | ammissione e ripresa dello slot device-to-device | `g-copy` del 18/10 contaminato **e con il nome sbagliato** (`STRATA_COPY_BATCHSYNC`) | rifare l'arm con il nome giusto |
| `STRATA_SLOT_CKPT_MOVE=1`, `STRATA_CKPT_POOL=1`, `STRATA_CKPT_THREADS=1` | checkpoint senza copia / in parallelo | mai misurati | `agents:3:R` con i tre |
| `STRATA_ADMIT_SHORT_FIRST=N` (server) | prompt corti prima dei lunghi (attesa max `STRATA_ADMIT_MAX_WAIT_S`, 30) | mai misurato | N=2048, B-A-B su `agents:3:R` (p50/p90 di TTFT) |
| `STRATA_BATCH_SELF_COMMIT=1`, `STRATA_QSA_SLOTS=1`, `STRATA_BATCH_ATTN_ROWS=1`, `STRATA_BATCH_GDN_GROUPS=1` (#2234) | meno lanci per finestra di slot | mai misurati | un arm con i quattro, poi separati se c'è segnale |
| `STRATA_PIPE_BYIELD_NODRAIN=1` | cedere il passo senza svuotare i gruppi | mai misurato | accanto a `PIPED_CONCURRENT` |
| `STRATA_ADMIT_MERGE_FIRST=1` | ultimo pezzo di prompt e primo token in una finestra | **inapplicabile**: serve tutti gli esperti residenti (e rompe il banco DET) | non provare |
| `--conversation-cache-park-gain 500` | riscrive meno snapshot | mai misurato da noi (upstream: 6,06 → 5,07 s) | un arm con turni che crescono di poche centinaia di token |

## 4. Fork (489 scansionati, 150 con commit pertinenti, ~60 letti)

Criterio: fork con push dopo il 13/10, almeno 30 minuti dopo la creazione; per ciascuno fino a 14 branch confrontati con `main`; contati solo i
commit non-merge dopo il 10/10 fuori dalle teste di PR. 221 fork hanno branch propri recenti. Tra i 150 con parole chiave utili, quelli che contano
per noi sono già nelle tabelle di §2 (con commit); gli altri non hanno nulla di pertinente. Limite onesto: per i fork con più di 250 commit avanti
l'API restituisce solo i primi 250 in ordine, quindi per `ScrambledEggsOnToast` ho riletto `commits?sha=main` a parte; per gli altri fork molto
divergenti (Hcl192088, jtn0123, Rarebigshot17, cassettesgoboom) i commit recenti possono mancare.

Stato dei fork già visti il 13/10: **NTRYourWaifu** (ultimo push 12/10, nessuna novità; v7/v8 sono la nostra patch 17), **unimatrix099** (12/10), **dragomir-lekovic**
(12/10), **fushengss** (11/10), **jesdga95** (4/10): nessun push dopo il 13/10. **sensssz** (14/10, `mtp-lend` + backport sm_75, tutto già in 0.1.45), **eddoursul**
(18/10, `custom` fermo al 27/9), **SanghunYun** (`STRATA_RAM_ADAPT` ora con copia dal buffer di stage, #3060, +3,2% corto / +33,8% su 120 richieste ShareGPT:
inutile con la nostra arena intera), **noon-at-cgn** (15/10, commit vecchi).

Fork con cui vale la pena tenere il filo, oltre a quelli in §2: **ScrambledEggsOnToast** (spec208, `het-*`, `repin/upstream-0.1.45`: motore eterogeneo
sm_70+sm_86 con store di prefissi condivisi), **svgop** (micro-ottimizzazioni a ~210 t/s su una scheda, il loro laboratorio con 232 voci numerate),
**sibnick** (K37, chunk per stadio con registro di memoria), **corbinjurgens** (Windows CUDA: fase di prefill condivisa sotto pressione VRAM, copie
pronte della cache: pensato per schede da 6 GB), **jielin99/Strata-codex** (`lab/140t`, giudizio automatico di kernel, nessun dato sm_75).

## 5. Classifica finale

### 5a. Da misurare subito, a costo zero (env o flag, nessun codice)

| # | cosa | env / comando | atteso (S) | perché |
|---|---|---|---|---|
| 1 | A/B di `STRATA_DEQUANT_WIDE=0` | `"STRATA_DEQUANT_WIDE":"0"` contro default; prompt da 1K, 2K, 4K, 30K | recupero di un −10…15% sui turni da 4K, se il segnale di #3109 vale anche su sm_86 | acceso di default dalla 0.1.45 sulla nostra 3060; i turni degli agenti sono 0,5–4K |
| 2 | `--prefill-pipe 1`, poi R=768/1536/3072 | `--prefill-pipe 1` | prompt da 10K +10…17%; 131K ≈ 0 | a 2 stadi asimmetrici; nb → KL |
| 3 | `STRATA_HANDOFF_PIPE=4` | env | piccolo; verifica parità | consegna del chunk in pezzi |
| 4 | arm «pacchetto 3060» separati: `STRATA_PF_FUSED=1`, `STRATA_PROMPT_ATTN_IMMA=1`, `STRATA_QSA_SPLIT_ATTN=1`, `STRATA_HC_UPMIX=1` | env | prompt 3060 +3…10%, decode +3% | agiscono solo sullo stadio 0; nb eccetto UPMIX |
| 5 | `agents:3:R` pulito con `PREFILL_HELP=1` (ripetere `r6`) e `ADMIT_SHORT_FIRST=2048` | env | TTFT p50 −10…20% | `r6` era disturbato; nessuna misura di SHORT_FIRST |
| 6 | `g-copy` rifatto con il nome giusto + `SLOT_CKPT_MOVE` + `CKPT_POOL` + `CKPT_THREADS` + `BATCH_SELF_COMMIT` | `STRATA_SLOT_COPY_DIRECT=1 STRATA_SLOT_COPY_BATCHSYNC=1 …` | ammissione −1…2 s per turno; nessun cambio di bit | arm contaminato e con variabile inesistente |
| 7 | `--conversation-cache-park-gain 500` | flag | −1 s sui turni che crescono poco | già in 0.1.45 |
| 8 | `STRATA_HC_REQ8=1` da solo | env | decode ±2%, più slot | non combinabile con la patch 18 |

### 5b. Da portare

| # | cosa | stima (S) | sforzo | rischio / nota |
|---|---|---|---|---|
| 1 | **#3095 `STRATA_PW_WITH_BATCH`** (+23/−5) | chat sola in config multi-chat da ~52 a ~62–65 t/s; l'aggregato non cambia | piccolo | parità: la richiesta sola passa dallo slot al solo; nessuna risposta del maintainer; precedente: fork noon-at-cgn `d84da294` |
| 2 | **sibnick K37**, raccolta MMQ in blocchi (`prefill.cpp` +51/−7 e CMake) | letture brevi/medie −8…−12%; sul replay 78,5% di tempo in lettura → −5…9% di wall | piccolo (riscrittura su 0.1.45) | misurato su sm_80+sm_86; sulla 2080 Ti (sm_75) non provato; serve parità |
| 3 | **#3104 + #3085** IQ su Turing (`moe_fused_iq.cu`) | prefill dello stadio 1 +10…19% | piccolo-medio | nb → KL; coprire IQ3_XXS gate/up e IQ4_NL down; possibile conflitto con `HC16_SM75` e `BF16_TC` |
| 4 | **#2774** chunk corti, esperti residenti ≤8 righe sul kernel di decode | letture < 1K token −20…35% | piccolo-medio | il pack nostro non è Q2_0 «canonico»; `PF_ROUTE_PRIOR` è nb, usarlo spento |
| 5 | `STRATA_PIPED_CONCURRENT_SMB` (#3103) | prompt +3…8% accanto al decode | piccolo | dipende da `SPLIT_MTP_BATCH`, non da noi misurato |
| 6 | Bozze adattive: #2529 `MTP_ADAPTIVE` o `SPEC_CUM`/`LOOKUP_Q` di android-imdad | decode +1…3% | piccolo | nessuna prova su split; uscita invariata |
| 7 | #2690 `VERIFY_DEFER_CPU` | ≤+2% | medio | dichiarato su 3080 10 GB, molto più legato alla CPU del nostro caso |
| 8 | Avvio Windows: #2672 + #2673 + #2776 | avvio −7…8 s | piccolo | nessun effetto su decode o prompt |
| 9 | Persistenza su disco (qualunque disegno) | riavvio senza rilettura | — | **attendere la scelta del maintainer per la 0.1.46**; intanto #2590 (sessioni su split) è la più vicina ai nostri bisogni |
| 10 | #2527/#2528/#2843 politica di piazzamento | caso classifier di Claude Code da 15–27 s a ~0 | alto | 5 100 righe; il riuso del replay è già 93% |

Non portare: #2761/#2830 (negativa), #2738 (−22% da terzi), yi-sudo `BATCH_MTP_D` (negativa), #1524 (rifiutata), #2822 (non serve con `--batch`),
vizdatom layer-major (non per split), `STRATA_PF_FUSED_SM75` oggi (inerte con IQ3_XXS).

Stato: ricognizione in sola lettura; **compilato no, installato no, provato no**.
