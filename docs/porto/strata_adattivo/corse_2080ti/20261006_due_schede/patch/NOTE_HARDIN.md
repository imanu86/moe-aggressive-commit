# Porto da Hardin22/Strata-DualGPU, PR #910 e PR #1091 sul fork Strata-2080Ti-core

Base: `Strata-2080Ti-core` `main` @ `3f85784`. Si applicano dalla radice del fork con `git apply <file>`.
Stato: **compilato no, installato no, provato no**. Il checkout del fork non è stato toccato: ho lavorato su copie
dei file in una cartella di appoggio.

Tutte le patch:
- sono opt-in, dietro una variabile d'ambiente spenta di default;
- passano `git apply --check` su 3f85784 una per una;
- si applicano anche impilate, nell'ordine di prova consigliato in fondo (provato su una copia).

Il porto riprende il contenuto e non i commit, perché i commit di Hardin22 stanno sulla vecchia storia di upstream.

## In breve

| file | origine | cosa | variabile | conta per noi |
|---|---|---|---|---|
| `pr1091.diff` | upstream #1091 (konijiwa110) | punteggi dei blocchi QSA in FP32 a tile sotto sm_80 (prefill) | `STRATA_SELECT_SIMT=1` | sì: prefill lungo sul 2080 Ti |
| `hardin_commit_async.diff` | Hardin bce7fbb3 | i commit di un layer split accodati senza attesa | `STRATA_COMMIT_ASYNC=1` | sì: commit/emit 0,75–0,9 ms a finestra nei log |
| `hardin_xstage.diff` | Hardin bce7fbb3 | passaggio tra blocchi con flag in memoria mappata, tutti i grafi lanciati insieme | `STRATA_XSTAGE=1` | sì: è il cuore del lavoro di Hardin |
| `hardin_ple_first.diff` | Hardin bce7fbb3 | righe PLE raccolte prima del campanello del layer 0 | `STRATA_PLE_FIRST=1` | forse: dipende dall'SSD |
| `hardin_mtp_chain.diff` | Hardin bce7fbb3 | giro di draft MTP in un solo grafo CUDA con nodi condizionali | `STRATA_MTP_CHAIN=1` | sì, se `--spec-min-p > 0` (le config lo usano) |
| `hardin_adapt_gate.diff` | Hardin bce7fbb3 | le copie del tier adattivo aspettano mentre gira il pool CPU | `STRATA_ADAPT_GATE=1` | solo con `--adapt-async 1` |
| `pr910.diff` | upstream #910 (730d6c89) | PLE letto in anticipo, ticket PLE per finestra, catena MTP prima della contabilità del verdetto | `STRATA_PL_PLE_PREFETCH=1`, `STRATA_PL_PLE_LATE=1`, `STRATA_PL_EARLY_CHAIN=1` | solo con `--pipeline-windows 2` |

**Attenzione ai file `pr1120.diff`, `pr1122.diff` e `NOTE.md`** di questa cartella: vengono da un altro lavoro, non da
questo. Le interazioni le ho verificate su una copia, applicando le patch senza i `docs/`:
- `pr1120` (`STRATA_SPLIT_OVERLAP`) fa la stessa cosa di `hardin_xstage`, quindi **va scelta una delle due**: non si
  impilano. `pr1120` limita l'attesa lato GPU (`STRATA_SPLIT_WAIT_MS`), un vantaggio contro il TDR di WDDM, ed è già
  passata da una revisione upstream. `hardin_xstage` invece lancia tutti i blocchi dallo stesso thread, senza thread di
  appoggio.
- `pr1122` (pipeline + tier asincrono insieme) va in conflitto con `hardin_adapt_gate` e con `pr910`. Toccano tutte e
  tre il tier asincrono o il ciclo pipelined.
- Le altre combinazioni si applicano.

## Contesto misurato sulla nostra macchina (dai log di `20261006_due_schede` e `20261004_routed_keep`)

Valori per finestra:

| voce | ms |
|---|---|
| finestra intera | 27–48 |
| attesa che la GPU arrivi al layer | 9–22 |
| commit/emit | 0,75–0,9 |
| draft | 2,1–3,5 |

Commit e draft sono sincroni sul percorso critico. Le stime di guadagno qui sotto sono mie: le misure le ha fatte
Hardin su un altro hardware.

---

## 1. `pr1091.diff`: punteggi dei blocchi QSA in FP32 a tile (prefill, sm_75)

**Cosa fa.** Sotto sm_80 non ci sono tensor core TF32, quindi il prefill assegna i punteggi ai blocchi QSA con il kernel
a warp, a circa 1 TFLOPS sul 2080 Ti. La PR aggiunge `block_scores_simt_kernel`, una GEMM FP32 a tile in memoria
condivisa (circa 6,9 TFLOPS). Il blocco di coda resta quello del kernel a warp. Il 3060 (sm_86) usa già i tensor core,
quindi conta solo il blocco del 2080 Ti. Il decode non cambia.

**Come si accende.** `STRATA_SELECT_SIMT=1`. Upstream la mette **attiva di default** sotto sm_80. Io l'ho resa opt-in,
così il default resta identico bit per bit. `STRATA_SELECT_OLD=1` forza sempre il kernel a warp.

**Numeri riportati.** Da konijiwa110, su RTX 2080 Ti 22 GB, i5-12490F e 64 GB, con Swift 1.5 IQ3_XXS a 256K e
`--kv k8v4 --kv-resident 32768`.

Banco `qsa_select_bench`:

| contesto | prima | dopo |
|---|---|---|
| 32K | 2,110 ms | 0,329 ms |
| 131K | 8,516 ms | 1,253 ms |

Selezioni identiche 256/256. Errore massimo rispetto a FP64: 5,6e-5 su una scala di punteggio di circa 268.

Prefill in tok/s:

| prompt | prima | dopo |
|---|---|---|
| 4K | 972 | 984 |
| 32K | 1173 | 1221 (+4%) |
| 128K | 1003 | 1228 (+22%) |
| 248K | 802 | 1151 (+44%) |

**Conflitti.** Nessuno: la patch si applica con offset. Ho aggiunto solo:
- l'opt-in;
- `STRATA_SELECT_SIMT=1` nell'ambiente dei due test CTest `qsa_select_bench`, che altrimenti sul 2080 Ti direbbero SKIP.

**Rischi.**
- **Numerica:** non è bit-identica. Somma in FP32 in un altro ordine, come il punteggio a tensor core sulle sm_80+. A
  contesti lunghi, vicino a un pareggio, la selezione può cambiare. Va controllata con `qsa_select_bench` sul 2080 Ti
  e con una A/B di qualità su un prompt lungo.
- **WDDM:** nessuno in particolare.

## 2. `hardin_commit_async.diff`: commit asincroni anche con il layer split

**Cosa fa.** Il fork accoda già il commit senza aspettarlo su una sola scheda (`set_commit_async`), ma con il layer split
lo esclude: `set_commit_async(!multi_gpu)`, e `commit()` aspetta se `next_ != nullptr`. Con la variabile accesa, ogni
blocco accoda il grafo di commit sul proprio stream e la finestra successiva di quel blocco lo segue lì. Il drafter, sul
2080 Ti, legge solo le righe finali della finestra e il proprio K/V, come su una scheda sola. `wait_commit()` era già a
catena su `next_` e viene chiamato prima di prompt, checkpoint, sessioni e fine richiesta.

**Come si accende.** `STRATA_COMMIT_ASYNC=1`. `STRATA_COMMIT_SYNC=1` vince su tutto. All'avvio il log dice
`STRATA_COMMIT_ASYNC=1, every stage's commit is queued`.

**Numeri riportati.** Non isolati. Fanno parte del pacchetto «attese dell'host» di bce7fbb3: su 5080 + 4060 Ti (la
4060 Ti su PCIe 4.0 x4 dal chipset), i9-14900KF, Windows 11, IQ2_XS a 256K, `--spec 4`, il code va da 95 a 108 tok/s
e la prosa da 75 a 85. Mia stima per noi: fino a 0,5–0,8 ms a finestra, circa il 2–3%.

**Conflitti.** Il fork ha già `commit_done_`/`wait_commit` per la scheda singola. Ho riusato quelli, invece della
`commit_async`/`commit_wait` separata di Hardin.

**Rischi.**
- **Numerica:** nessun cambiamento. Cambiano solo le attese.
- **Stato non atteso:** un percorso che legge lo stato della sessione di un blocco senza `wait_commit()` vedrebbe un
  commit non finito. Ho controllato i punti noti:
  - `kvg_ensure` sincronizza CUDA0, dove sta il commit del blocco 0;
  - `el_shrink` fa `cudaDeviceSynchronize` su CUDA0;
  - i file di sessione rifiutano lo split;
  - parcheggio e prompt passano da `wait_commit`.
- **WDDM:** nessuno in particolare. Dopo il lancio c'è già il `cudaStreamQuery` che svuota il batch.

## 3. `hardin_xstage.diff`: passaggio tra blocchi con flag sul device

**Cosa fa.** Il blocco 0 finisce il suo grafo con `xstage_publish`: un kernel che copia R | bo | inj2 nell'hand-off
mappato, fa il fence di sistema e poi l'ultimo blocco CUDA alza il flag. Il grafo del blocco 1 comincia con
`wait_flag_ge(flag)` e `xstage_take`, che legge con `__ldcv`. `Verifier::run` diventa `run_prepare`, `run_launch`,
`run_serve` e `run_finish`. Con i flag, `run_chain` fa in quest'ordine:
1. prepara tutti i blocchi (le catture prima di ogni lancio);
2. li lancia tutti;
3. li serve in ordine dallo stesso thread;
4. li chiude.

Fra blocco 0 e blocco 1 non restano sync, staging o lancio dell'host. Se un blocco fallisce, quelli già lanciati
vengono rilasciati (piani vuoti, flag a UINT32_MAX), come in #267. Anche `release_gpu_waits` alza il flag in ingresso.

**Come si accende.** `STRATA_XSTAGE=1`. Vale solo con:
- il serve;
- blocchi su schede diverse;
- `--pipeline-windows` spento: con la pipeline la variabile viene ignorata e il log lo dice.

Le finestre batch (`run_slots`) restano con le copie di prima.

**Numeri riportati.** Stesso pacchetto di bce7fbb3: code da 95 a 108 tok/s, prosa da 75 a 85. Il giro di un flag fra
due GPU attraverso la memoria mappata misurava 7–10 µs. Mia stima per noi: si risparmiano la sync del blocco 0, lo
staging e il lancio del blocco 1, cioè 0,1–0,5 ms a finestra, di più se il lancio su WDDM è lento.

**Conflitti risolti.**
- Il fork ha un altro layout dell'hand-off: R di tutte le T righe, poi bo, poi inj2, contigui, al posto di
  [R|bo|inj] per token. Ho riscritto `handoff_publish`/`handoff_take` per questo layout, con la variante float4
  quando gli allineamenti lo permettono.
- `run()` del fork ha in più ar_on/#871, la sonda lookahead, il bilanciamento PCIe del #1038, la modalità closed, la
  traccia #649, `neuron_trace` e la raccolta PLE a k==0. Ho tenuto tutto, spezzando la funzione nei quattro passi senza
  cambiare l'ordine delle istruzioni.
- Il contatore dei blocchi viene allocato al primo `run_prepare`, prima della cattura. Così il carve dell'arena non
  cambia e il default resta identico.

**Rischi.**
- **Numerica:** bit-identica. Sono gli stessi byte, cambia solo chi aspetta.
  - Da provare: `STRATA_XSTAGE=1` contro 0, con `STRATA_IQ_MT_MIN=1 --adapt-every 0` in greedy, deve dare lo stesso
    testo.
- **WDDM:**
  - il 2080 Ti gira in un kernel di attesa a un thread dal lancio fino al flag, cioè per tutta la durata del blocco 0
    (circa 11 ms con 16 layer). È lo stesso tipo di attesa dei campanelli già presenti.
  - Il rischio TDR esiste solo se il blocco 0 resta fermo più di 2 s. In quel caso il timeout dell'host (20 s) chiama
    `release_gpu_waits`, che ora alza anche il flag. `pr1120` invece limita l'attesa anche lato GPU.
  - Senza P2P il flag passa dalla RAM di sistema: con la scheda su Oculink la latenza va rimisurata.
- **Ordine di inizializzazione:** i flag vanno impostati prima della prima cattura. Lo fa il serve, prima di
  `ver.init` e delle prime finestre.

## 4. `hardin_ple_first.diff`: righe PLE prima del campanello del layer 0

**Cosa fa.** Oggi il fork raccoglie le righe PLE a k==0, dopo il piano del layer 0 e prima di alzarne il flag. Con la
variabile le raccoglie prima del ciclo, mentre la GPU fa l'embedding e l'attenzione del layer 0 e l'host aspetterebbe
comunque. Il grafo copia le righe dopo il flag del layer 0 in entrambi i casi.

**Come si accende.** `STRATA_PLE_FIRST=1`. Non vale in modalità closed né con il grafo all-resident, che hanno già il
loro ordine.

**Numeri riportati.** Nessuno isolato. Sta nel pacchetto bce7fbb3, dove era attiva di default.

**Rischi.**
- **Numerica:** bit-identica.
- **Prestazioni:** se l'SSD è lento e il campanello del layer 0 suona durante la raccolta, gli esperti CPU del layer 0
  partono in ritardo. Va misurata con `STRATA_DECODE_TIMING=1`, che accende anche il contatore `ms_ple_gather`.

## 5. `hardin_mtp_chain.diff`: giro di draft MTP in un solo grafo

**Cosa fa.** Con un min_p, `draft()` del fork lancia il round e poi un grafo per passo, decidendo sull'host fra un passo
e l'altro (attesa attiva su `h_out_`). Con la variabile, il round e i passi 1..jmax-1 stanno in un solo grafo. Ogni
passo j è dentro un nodo condizionale IF, il cui valore lo decide un kernel a un thread (`mtp_chain_gate`) con lo
stesso confronto float dell'host: prob[0..j-1] >= min_p. L'host fa un solo lancio, legge le bozze appena arrivano (il
prefetch PLE delle bozze resta) e alla fine sincronizza.

I nodi sono quelli di `capture_round`/`capture_step`, nello stesso ordine, quindi le bozze sono identiche. Se la cattura
o l'istanziazione falliscono, lo scrive nel log e torna da sola ai grafi per passo per tutto il processo.

**Come si accende.** `STRATA_MTP_CHAIN=1`. Lavora solo con:
- `--spec-min-p > 0`;
- bozze argmax: non con coupled, non con il forcing della pipeline.

**Numeri riportati.** Non isolati, stesso pacchetto bce7fbb3. Mia stima: si tolgono (passi-1) intervalli di
lancio+poll, 30–60 µs l'uno su WDDM, quindi 0,05–0,2 ms a finestra.

**Conflitti risolti.**
- Hardin usa le API di CUDA 13 (`cudaGraphAddNode` e `cudaStreamUpdateCaptureDependencies` con gli edge,
  `cudaStreamGetCaptureInfo` a 7 argomenti).
- Per CUDA 12.x ho usato `_v2`/`_v3`, come fa già il fork in `pdl`. Ho controllato che ci siano negli header di
  CUDA 12.6 di questa macchina: `cudaStreamBeginCaptureToGraph`, `cudaGraphConditionalHandleCreate`,
  `cudaGraphAddNode_v2`, `cudaStreamUpdateCaptureDependencies_v2`, `cudaStreamGetCaptureInfo_v3`, e
  `cudaGraphSetConditional` lato device.
- Serve CUDA 12.3 o più recente; su HIP è spenta.
- Il round del fork usa `copy_from_mapped_multi` e, con la pipeline, `force_token`: li ho copiati come sono.

**Rischi.**
- **Numerica:** identica. Stesse bozze, quindi stesse finestre.
- **Non provato:** nessuno ha provato i nodi condizionali su sm_75 con WDDM. Se il link di `cudaGraphSetConditional`
  richiede cudadevrt, l'errore arriva in compilazione.
- **Cattura del body:** il body include il ramo `side_` dello shared expert, catturato da un altro stream verso il grafo
  del body. Se fallisse a metà, `side_` potrebbe restare in uno stato di cattura invalido. Primo controllo: il log
  all'avvio della prima richiesta, che deve dire `captured as one graph` e non `not available`.

## 6. `hardin_adapt_gate.diff`: tier adattivo fuori dalla banda del pool CPU

**Cosa fa.** `drive_pool_multi` alza `g_pool_active` mentre gira il pool degli esperti CPU. Due cose aspettano
(`yield`) finché è alto:
- le letture di rimbalzo del tier asincrono, prima di `copy_blob` e `cudaMemcpyAsync`;
- `commit_copies`, che con la variabile copia a pezzi da 256 KiB.

Così le copie prendono banda RAM mentre l'host aspetta la GPU e non durante il pool.

**Come si accende.** `STRATA_ADAPT_GATE=1`, con `--adapt-async 1`.

**Numeri riportati.** Non isolati (pacchetto bce7fbb3).

**Conflitti risolti.** L'`a_copy_in` del fork è diverso da quello di Hardin (`copy_blob` in un buffer di rimbalzo,
`STRATA_EXCHANGE_ROTATE`). Ho messo l'attesa prima della lettura e lasciato intatto il ramo rotate.

**Rischi.**
- **Numerica:** stessi byte. Però il tier cambia residenza più tardi, quindi quali esperti girano su GPU o su CPU in una
  certa finestra può cambiare gli ultimi bit, come qualunque cambio di tempistica del tier.
- **Round lenti:** con un pool sempre attivo i round del tier si allungano.

## 7. `pr910.diff`: i tre interruttori della pipeline (upstream #910, commit 730d6c89)

**Cosa fa.** Agisce solo dentro `--pipeline-windows 2`; `run()`, il batch e il ciclo seriale non cambiano.
- `STRATA_PL_PLE_PREFETCH=1`, solo per letture PLE Direct: legge le righe PLE della prossima finestra man mano che si
  conoscono i token (la riga 0 al verdetto, ogni uscita della catena, i token di un B di lookup). `PleReader::prefetch`
  le mette nella row cache dietro le letture dei ticket. Un `issue` che chiede una riga ancora in lettura si attacca a
  quella lettura invece di rileggere la pagina.
- `STRATA_PL_PLE_LATE=1`: ogni finestra del blocco 0 legge le sue righe con un ticket proprio (`gather_issue_t`). In
  quel caso `service` non si blocca: se il layer 0 è servito prima che arrivino, ne tiene il flag e intanto serve le
  altre finestre. Timeout di 20 s, come #267.
- `STRATA_PL_EARLY_CHAIN=1`: la catena MTP parte al verdetto, prima di stampa, suffisso, calibrazione, policy e tier.

**Numeri riportati.** Su 4060 Ti + 5080, IQ3_XXS a 160K q4_0, residente in RAM (#848),
`--pipeline-windows 2 --adapt-async 1 --trim-stage-weights`:
- tutto spento: 117,5 / 117,5 tok/s;
- tutto acceso (con `STRATA_MTP_KV=f16` e il merge v2): 132,1 / 130,6, cioè +12%, non diviso per interruttore;
- sul fork di Hardin, i soli tre interruttori: da 125,4 / 124,2 a 131,4 / 129,3.

Testo greedy uguale acceso e spento, 4 prompt su 4.

**Conflitti risolti.**
- `ngram.cpp`: il fork ha già la serie Q8_0 PLE (`decode`, `rb`) e include `<algorithm>`. Ho inserito `Batch` e `reap`
  dopo `decode`.
- `generate.cpp`, due hunk: il fork chiama `pl_adapt()` senza `!ajob`, e il ciclo seriale che segue comincia con
  `int T = use_mtp ? ...`. Li ho riapplicati a mano con lo stesso contenuto.
- Il resto della PR, cioè merge v2 e `STRATA_MTP_KV`, c'è già nel fork (3effa9d). Lì il merge v2 resta attivo di
  default, verificato bit per bit sul 2080 Ti: 768 casi su 768. Upstream invece l'ha reso opt-in con 9d27f7e, non per
  numerica ma perché non era stato misurato da solo.

**Rischi.**
- **Lettore PLE:** il prefetch cambia la parte interna del lettore (`retire`, `attach`, `done_epoch`). Hardin dice che
  finché non c'è un prefetch il lettore resta invariato, e ha esteso `ple_reader_test --selftest`, che va lanciato.
- **Numerica:** i byte PLE sono quelli della tabella. Cambia solo l'host.

---

## Non portato, o portato solo in parte, e perché

- **`STRATA_MTP_EARLY` (bce7fbb3): draft lanciato prima dell'emissione dei token.**
  - `draft()` del fork è sincrono e fa il prefetch PLE delle bozze nel suo ciclo, quindi servirebbe spezzarlo in
    `draft_begin`/`draft_end` su tre rami (min_p nullo, per passo, catena).
  - Il guadagno sarebbe la sola emissione, qualche decina di µs: non vale il rischio adesso.
  - Con `hardin_mtp_chain` basterebbe spostare lancio e poll in due metodi.
- **`STRATA_PLE_LATE` del ciclo seriale (bce7fbb3): il grafo aspetta un flag PLE prima del blocco PLE del layer 1.**
  Richiede un nuovo flag mappato catturato nel grafo. Il blocco PLE di `record_window` nel fork è molto diverso
  (`ple_batch_kv`, `ple_post`, batched/native). Troppo intrecciato per farlo alla cieca. La parte host la copre
  `hardin_ple_first`.
- **Diagnostica di bce7fbb3.** Parlo della seconda riga di `STRATA_DECODE_TIMING`, con il tempo dell'host per blocco,
  e di `STRATA_WINDOW_TRACE`, con gli hash per finestra. Il fork ha già il suo `STRATA_DECODE_TIMING`. Se serve per
  misurare xstage, si porta a parte.
- **58ec6198, kernel densi.** Upstream ha già `STRATA_DF_BRANCH`, `DF_PDL`, `DF_PLE`, `DF_KVAPP` e `DF_QB_Q4`. Mancano:
  - `STRATA_DF_MMVQW`: un warp per riga quando le righe in uscita sono almeno 2048. Riportato -10…-30% su IQ4_XS da
    6144 a 248320 righe sulla 5080 e sulla 4060 Ti. Per noi è il candidato più interessante, perché la testa da 248K
    righe gira sul 2080 Ti, ma va misurato su sm_75.
  - `STRATA_DF_SHARED`: SwiGLU dentro la quantizzazione del down dello shared expert.
  - `STRATA_DF_ATTN`: caricamenti in batch nei cicli di attenzione.
  - `STRATA_DF_HANDOFF`: superato da xstage.
  - `L2PF`: non aiutava neanche da loro.

  Sono circa 600 righe di kernel, da portare con test di parità e una build. Le lascio per un giro dedicato.
- **Già nel fork:** pipeline (301e5107 = #859), trim dei pesi per blocco (d9ff5144 = #880), residente in RAM con lo
  split (#848), tier asincrono (11b1f253 → `--adapt-async`), AVX-VNNI.
- **badfdb26, scelte del server:**
  - ordine delle schede con la più veloce in fondo: da noi c'è già, il 3060 sta prima e il 2080 Ti in fondo;
  - riserve VRAM, worker del pool sulle CPU ibride, EcoQoS: lato setup/server, fuori da questo giro.
- **f42c58f9, kernel CPU.** Il ramo IQ3_S multi-token per un token solo cambia i bit. Fuori tema.

## Ordine di prova consigliato

Tutte impilabili in quest'ordine, verificato su una copia di 3f85784:

1. **`pr1091`.** È isolata (solo prefill).
   - `qsa_select_bench 131072 256 3 262144` con `STRATA_SELECT_SIMT=1` sul 2080 Ti.
   - Poi una A/B su un prompt da 128K, con la variabile accesa e spenta.
2. **`hardin_commit_async`.** È la modifica più piccola con il guadagno atteso più chiaro, sulla voce commit/emit.
   - A/B con `STRATA_DECODE_TIMING=1`, guardando commit/emit.
   - Controllo: lo stato dopo una richiesta (`STRATA_STATE_HASH`, se usato) deve essere uguale.
3. **Una sola fra `hardin_xstage` e `pr1120`.**
   - Prima la prova di identità: `STRATA_IQ_MT_MIN=1 --adapt-every 0` in greedy, testo uguale con la variabile a 1 e a 0.
   - Poi velocità, con e senza `STRATA_COMMIT_ASYNC=1`.
   - Un'interruzione a metà richiesta non deve lasciare la GPU appesa.
4. **`hardin_ple_first`.** A/B su `ms_ple_gather` e sull'attesa del layer 0.
5. **`hardin_mtp_chain`.** Con `--spec-min-p` come nelle config.
   - Nel log ci deve essere `captured as one graph`.
   - Draft per finestra in `STRATA_DECODE_TIMING`.
   - Stesse bozze: stesso testo con `STRATA_IQ_MT_MIN=1`.
6. **`hardin_adapt_gate`.** Solo se la Daily usa `--adapt-async 1`.
7. **`pr910`.** Solo per la strada `--pipeline-windows 2`. Prima `ple_reader_test --selftest`, poi i tre interruttori
   insieme. Va in conflitto con `pr1122`: se si sceglie anche quella, bisogna riconciliarle.

Le misure di velocità vanno rifatte dopo Oculink, prima di confrontarle con i numeri di Hardin.
