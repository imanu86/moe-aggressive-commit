# HANDOFF — 26 agosto 2026
## Campagna 25-26/8: fatti misurati, condizioni, misure sospette, lavoro aperto

**Questo documento riporta misure e condizioni, non verdetti.** Dove compare una stima, è marcata
come tale con la sua derivazione, così che chi legge possa rifarla.

---

# MAPPA DEI PERCORSI

## Repository e worktree

| percorso | cos'è |
|---|---|
| `C:\Users\imanu\source\repos\moe-aggressive-commit` | **repo principale** (docs, ledger, tools). Branch con i docs del porto: `research/ds4-iq1-subbit-tier-planner` |
| `…\.claude\worktrees\zen-morse-a2ee4b` | worktree della sessione 25-26/8, branch `claude/jovial-sammet-3f148f` (allineato al padre con merge) |
| `…\docs\porto\` | **tutti i ledger, gli handoff, il runbook**, e `lanciatori/` |

## Alberi sorgente C++ — attenzione, tre alberi con ruoli diversi

| percorso | ruolo | vincolo |
|---|---|---|
| `D:\llama-subtract` | **albero di lavoro**: qui si edita e si compila | ⚠ **è una COPIA di un worktree** (il suo `.git` è un file che punta a `D:/llama-dspark/.git/worktrees/llama-overlap`). **MAI comandi `git` qui dentro**: un commit muoverebbe il branch `overlap` sotto il worktree vero |
| `D:\llama-overlap` | **worktree vero** del branch `overlap` | qui i commit sorgente sono legittimi. Stato: `overlap` = `5804c9f` (fix resto-64 v2) |
| `D:\llama-dspark` | **repo padre** | contiene `stash@{0}` «pre-atterraggio chirurgo15» — **non droppare**. I commit sorgente si fanno da qui via plumbing o dal worktree vero |

Percorsi sorgente citati in questo documento (tutti relativi a `D:\llama-subtract`):
`ggml\src\ggml-backend.cpp` · `ggml\src\ggml-cuda\ggml-cuda.cu` · `ggml\src\ggml-cuda\cache-esperti.cu`
· `ggml\src\ggml-cuda\kv-ring.cu` · `ggml\src\ggml-cuda\argsort.cu` · `ggml\src\ggml-cuda\lightning-indexer.cu`
· `ggml\src\ggml-cuda\mmvq.cu` · `ggml\src\ggml-cpu\ops.cpp` · `src\llama-context.cpp` · `src\llama-graph.cpp`
· `src\llama-kv-cache-dsv4.cpp` · `src\models\deepseek4.cpp`

## Binari

| percorso | cosa |
|---|---|
| `D:\ds4_prod\bin_stabile_20260825\` | **copia stabile di produzione** — `llama.dll` `ECAEA60B…9C035`, `ggml-cuda.dll` `6EF5B781…C68B52`, `ggml-base.dll` `BAD51D94…D0C65` |
| `D:\llama-subtract\build\bin\` | build corrente **chirurgo16** — `llama.dll` `12BF6E66…B87EB`, `ggml-base.dll` `D52DA12E…01546`; contiene sonda e leva R1, **entrambe spente di difetto** |
| `…\build\bin\backup_pre_chirurgo16\` | le 7 DLL precedenti |
| `…\build\bin\backup_*` | backup delle build precedenti (`pre_chirurgo14`, `post_chirurgo14`, `pre_chirurgo15`, `post_chirurgo15`, `canonico_bonifica_23ago` con `SHA256SUMS.txt`) |

**Toolchain**: `cmake` e `cl` sono **fuori PATH**. Servono
`C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat` e il cmake
di VS (`…\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`). Build tipica:
`cmake --build D:\llama-subtract\build --target ggml-base llama`.

## Modelli

| percorso | cosa |
|---|---|
| `C:\ds4-models\DS4-0731-IQ2XXS.gguf` | bersaglio (74.304 MiB mappati) |
| `D:\ds4-models\DSpark-draft-Q2K.gguf` | drafter |
| `D:\llama-subtract\models\templates\deepseek-ai-DeepSeek-V4-Flash-0731.jinja` | chat template |

## Script di banco

| percorso | cosa |
|---|---|
| `D:\ds4_work\llama_run\lanciatori_salvati_20260825\` | **79 lanciatori salvati** da una directory temporanea di sessione; copia in `docs\porto\lanciatori\` |
| `…\lanciatori_salvati_20260825\p1b_conf.ps1` | **lanciatore del banco lungo**. Ha `--no-host` (:219) e `-otd` (:216). Esteso il 26/8 con `-OverlapBatchMax` (difetto 3, backup accanto) |
| `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1` | banco **corto**. Ripuntato al canonico + guardia SHA. **Non ha `--no-host`**, **non imposta reasoning-budget** |
| `C:\Users\imanu\Documents\Codex\2026-08-20\riprendi-la-chat-recupero-sessioni-codex\work\run_p1_nudo.ps1` | espone `-OverlapBatchMax`, ma ha un **cancello d'identità su 5 hash** tarato su una build vecchia |
| `C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1` | runner canonico storico (`Set-SotaEnvironment`) |
| `C:\Users\imanu\source\repos\…\docs\porto\dopo_il_riavvio.ps1` | Runner A, lancio a freddo |
| `C:\Users\imanu\Desktop\avvia ds4 locale.bat` | avvio locale dell'utente (**è un esperimento, non la config di lavoro**); ripuntato alla copia stabile, backup accanto |

## Dati, log, artefatti

| percorso | cosa |
|---|---|
| `D:\ds4_work\llama_run\` | log dei banchi lunghi/prefill (`sota_ctx150000_*`, `r4*`, `r5*`) |
| `C:\Users\imanu\Documents\Codex\2026-08-15\…\work\runs\` | log del **Runner B** / banco corto (`t24_*`, `r44_*`, `warm_anchor*`, `mask_*`) — **albero diverso: cercare un tag qui se non è nell'altro** |
| `D:\ds4_work\l3_nsys\` | database nsys (`e35_nsys{33k,102k}_20260824*.sqlite`, ~213 MB l'uno) e script di analisi |
| `D:\ds4_work\kv_store\` | checkpoint KV serializzati (`ds4_long_101691_…_20260821.bin`, 1,05 GB) — **legati al binario che li ha salvati** |
| `D:\ds4_work\design\` | i venti documenti di disegno (elenco sotto) |
| `D:\ds4_work\prefill_lungo\`, `long_nsys\`, `prof\`, `telemetry\` | artefatti di campagne precedenti |

## Memoria dell'assistente

`C:\Users\imanu\.claude\projects\C--Users-imanu-source-repos-moe-aggressive-commit\memory\`
— `MEMORY.md` è l'indice; la ripresa di questa campagna è `resume-20260826-campagna-20tps-chiusa.md`.

---

# INDICE DEI DOCUMENTI

## Ledger — la cronaca giorno per giorno (in `docs\porto\`)

| file | KB | cosa contiene |
|---|---:|---|
| `LEDGER_25_AGOSTO.md` | 68 | **questa campagna**: i dodici bracci, le sonde, le falsificazioni, i cancelli |
| `LEDGER_23_AGOSTO.md` | 259 | fix resto-64; catena e35→e39 (nsys, bolle, correlationId, impronta taglie); sweep conf; crash `VRAM_A_FASI` |
| `LEDGER_17_AGOSTO.md` | 462 | il più grande: `fserial`, sweep blocchi, `carico_fantasma`, `LLAMA_KV_PAD`, `MASSA_CORSIE`, collasso lungo e fix grafi |
| `LEDGER_16_AGOSTO.md` | 203 | regressione `DISABLE_GRAPHS`; sweep `nmax`/`conf`; F2-A/F2-B; mappa nsys |
| `LEDGER_11_AGOSTO.md` | 74 | fork/join, 277 copie, GPU satura, prefetch |
| `LEDGER_10/13/14/15/18/9/6-8_AGOSTO.md` | 9-28 | campagne precedenti |
| `RUNBOOK_BANCO_DS4.md` | 89 | **procedura di banco**: preflight §1, lanci, protocollo B-first §8.7, §4.10 lettura qualità, §8.5 rimisura a freddo |
| `ATLANTE_LEVE.md` | 14 | censimento storico delle leve |
| `AMMISSIONE_ROUTING.md` | 4 | il precedente sulla **qualità che degrada**: `ammissione 0,25` ⇒ HTTP 500 e 133 byte col t/s più alto mai visto |
| `RIFERIMENTO_API_DEEPSEEK_V4.md` | 6 | API ufficiali DS4 (thinking di default, cache a tagli fissi) |
| `HANDOFF_13/14/15/16_AGOSTO.md` | 22-59 | handoff precedenti |

## Documenti di disegno (in `D:\ds4_work\design\`)

| file | KB | cosa contiene |
|---|---:|---|
| `COMPOSIZIONE_PIANO.md` | 46 | proiezioni di composizione delle leve (§496-511) |
| `BOLLE_HOST_GRAFI_PIANO.md` | 35 | l'AND rigido del riuso grafi, i due siti di padding, il piano sonde |
| `SELETTIVITA_INSTALLAZIONE_PIANO.md` | 25 | **il documento che falsifica la politica a tre livelli** (5 bracci) |
| `GRAFI_MORTE_RICHIESTE_RIPETUTE.md` | 18 | **esiste** (un agente l'aveva dato per introvabile): la morte per retroazione dei grafi CUDA |
| `TRASPORTO_ONLINE_PIANO.md` · `TRASPORTO_KV_RIGHE_PIANO.md` | 61 · 55 | disegni del trasporto |
| `MACRO_V2_PIANO.md` · `CURA_PER_ESPERTO_PIANO.md` | 57 · 57 | macro-kernel e cura per esperto (entrambi con tetti misurati) |
| `ADAPTIVE_K_PIANO.md` | 33 | il disegno di `K_ADATTIVO` (oggi non raggiungibile in produzione) |
| `TASSA_ATTENZIONE_LUNGO.md` | 26 | la tassa del contesto |
| `P1_DEGRADO_ROOT_CAUSE.md` · `KV_REUSE_VERIFICA.md` · `REPOINT_OOM_ANALISI.md` | 22 · 26 · 7 | root-cause precedenti |
| `RICOGNIZIONE_UPSTREAM_LLAMACPP.md` · `RICOGNIZIONE_ECOSISTEMA_DS.md` | 27 · 23 | stato dell'arte esterno |
| `impl\NOTE_IMPLEMENTAZIONE.md` | — | note di implementazione; **§7.2 ha l'idioma `voci fuori tabella`**, §14 il sito A del padding |

---

# 0. ERRATA — un errore aritmetico della versione precedente di questo handoff

La versione del 26/8 mattina concludeva che *«un sottosistema esperti a costo zero darebbe 19,2
t/s, quindi i 20 non sono raggiungibili»*. **Quel numero è sbagliato.** Era calcolato sulla quota
`trasporto 20,4% + MoE mascherata 10,5% = 30,9%`, cioè con la **quota vecchia del trasporto**,
mentre lo stesso documento riportava poche righe sopra la misura corretta: **45,1%**.

Rifatto con la quota misurata:

```
parete                     75,44 ms/token   (13,26 t/s)
trasporto esperti misurato 34,06 ms/token   (45,1%)   [119,17 miss/tok x 6,75 MiB / 23,07 GiB/s]
MoE mascherata               7,92 ms/token   (10,5%)
──────────────────────────────────────────
senza trasporto            41,38 ms/token = 24,2 t/s
senza trasporto e MoE      33,46 ms/token = 29,9 t/s
```

**Il tetto del sottosistema esperti è ~30 t/s, non 19,2.** E il tetto di silicio della 3060 misurato
in archivio è **~45-47 t/s**. Quindi i 20 t/s (50,0 ms/token) **non sono esclusi da alcuna misura**:
richiedono di togliere **25,4 ms/token, cioè il 74,7% del trasporto** — che tradotto in termini di
cache significa passare da **119 miss/token a ~30**, cioè da un tasso di colpi del **51,5% a ~88%**.
È un obiettivo difficile e specifico, non un muro.

**Altri due «tetti» della versione precedente vanno ritirati perché mal posti**, non solo mal
calcolati:
- *«bozza perfetta = 17,0 t/s»*: derivava da `C_round / mean_len` tenendo `C_round` **costante**
  mentre `mean_len` sale a 4. Ma `C_round` non è invariante rispetto a `mean_len` — meno round
  significano meno forward del bersaglio *e* una diversa unione di esperti per riga. La stima non ha
  una base misurata.
- *«tassa del contesto azzerata = 16,2 t/s»*: il pavimento (61,6 ms) **contiene** il trasporto (34,06
  ms). Presentarlo accanto al tetto del trasporto come se fossero alternative indipendenti è un
  doppio conteggio.

**Regola che ne esce, da applicare a ogni proiezione futura:** una stima si scrive con la formula,
gli ingressi e la loro provenienza accanto. Le quote di due misure diverse non si mescolano nello
stesso calcolo, e i tetti che condividono voci non si affiancano in tabella come se fossero
alternative.

---

# 1. FATTI MISURATI, con le condizioni esatte

Tutto ciò che segue è misurato. Le condizioni contano quanto i numeri: **misure prese in condizioni
diverse non sono confrontabili**, ed è stato il singolo errore più ricorrente della campagna.

## 1.1 I tre banchi

| banco | prompt | completion | ms/token | t/s | mean_len | p1 | colpi cache |
|---|---:|---:|---:|---:|---:|---:|---:|
| corto | 68 | 1200 | 59,97 | 16,68 | 2,80 | 0,90281 | ~68% |
| lungo «ancora» | 101.691 | 256 | 86,23 | 11,60 | 2,14 | 0,74725 | 72,6% |
| **lungo SOTA** | 101.691 | **8192** | **75,44** | **13,26** | 3,06-3,18 | 0,90229 | **51,5%** |

Sullo **stesso prompt**, passando da 256 a 8192 token di completion: `mean_len` 2,14 → 3,18, colpi
72,6% → 51,5%, p1 0,747 → 0,902. **Le statistiche a completion 256 sono una finestra precoce**, non
il regime stazionario.

## 1.2 Trasporto degli esperti — il numero centrale

Condizioni: banco lungo SOTA (102k, completion 8192), configurazione di produzione.

```
domanda 2.011.416  ·  colpi 1.035.203 (51,5%)  ·  buchi 976.213
119,17 miss/token x 6,75 MiB/esperto = 804,4 MiB/token
804,4 MiB / 23,07 GiB/s = 34,06 ms/token = 45,1% della parete
```
Confermato indipendentemente da una seconda corsa (`p1b_conf070`, 73,64 ms/tok): 795 MiB/token →
33,7 ms → 45,7%.

**Banda 23,07 GiB/s** — ricavata dalla **quantizzazione delle durate** di `kern_fj_copia`: armoniche
pulite a 280-350, 560-640, 840-940, 1100-1220 µs, quanto fondamentale **285,7 µs/esperto**. È un
**limite inferiore**: nsys con `--cuda-graph-trace=node` gonfia del 6-7%.

**Vuoto assoluto fra 10 e 250 µs** nella distribuzione: non esiste una seconda famiglia di copie
veloci ⇒ **nessun esperto è servito dalla VRAM, passano tutti dal PCIe**.

Geometria verificata: n_embd 4096 · 43 strati · 256 esperti · 6 usati · n_ff_exp 2048 · gate/up
IQ2_XXS + down Q2_K ⇒ **esperto = 7.077.888 B = 6,75 MiB**; 43 × 256 × 6,75 MiB = 74.304 MiB =
esattamente il `CUDA0_Mapped model buffer size` del log.

## 1.3 Riuso e churn

Condizioni: stesso banco lungo SOTA.

```
riusi dell'installato:  mai 82,1%  ·  1 uso 12,2%  ·  2-3 usi 4,6%  ·  4+ usi 1,1%
bussate al momento del buco:  1=5,2%  2=2,0%  3=1,4%  4-7=9,6%  8+=81,9%
vive-censurate = 473  (= esattamente la capienza: la contabilita' chiude)
```
Riuso medio **1,06 per installato**, mediana **zero**. Le classi «1» e «2-3» spiegano al massimo
~250k colpi su 1.035k ⇒ **i restanti ~785k (76%) stanno nella coda «4+», che è l'1,1% degli
installati** (~75 colpi ciascuno) — *questa è una deduzione aritmetica dai contatori, non una misura
diretta: il contatore dei colpi per classe non esiste* (§3.4).

**`bussate 8+ = 81,9%`**: al momento del buco, l'esperto mancante era già stato richiesto otto o più
volte. **I buchi non sono esperti freddi: sono esperti con storia lunga, sfrattati e richiesti di
nuovo.**

## 1.4 Chi blocca il thread principale

Condizioni: banco lungo SOTA, `GGML_SCHED_PROFILO=1`, contatori differenziati fra il grafo 12.749
(fine prefill) e 23.450 (fine corsa) = 10.701 grafi di decode; 51.643 lavori worker / 8.192 token =
6,303 lavori/token.

| voce | ms/token | % | thread |
|---|---:|---:|---|
| ingressi — blocco host (`sync`) | 38,09 | 50,5% | principale, **blocca** |
| join (attesa del ramo CPU) | 17,68 | 23,4% | principale, **blocca** |
| sched-sync (fine grafo) | 9,02 | 12,0% | principale, **blocca** |
| calc altri (accodamento CUDA) | 3,93 | 5,2% | principale, lavora |
| calc CPU (split non dati al worker) | 2,33 | 3,1% | principale, blocca |
| ingressi — copie vere | 0,77 | 1,0% | |
| **nascosto dalla sovrapposizione** | **0,28** | **0,37%** | |

Controprova che chiude al **99,9%**: `(evento 1,208 + calcolo 1,641 + attesa-lavoro 9,109) × 6,303 =
75,37` contro 75,44 misurato. **Il timer del worker è una partizione esatta della parete.**

`confini evento/blocco = 0 / 320.661`: **zero confini passano da eventi CUDA, tutti e 320 mila sono
blocchi host.**

⚠ **Nota di lettura obbligatoria**: `evento` e `calcolo` sono del **thread worker** e sono
**annidati dentro `join`**, non additivi (rapporto join/(evento+calcolo) = 97,7-98,5%). L'unica voce
di parete del ramo CPU è `join`.

**La sovrapposizione nasconde lo 0,37% della parete.** La finestra è larga **un solo split** (65 µs
misurati fra dispatch e ingresso nel join) contro 2,85 ms di lavoro CPU da nascondere.

## 1.5 Il ramo CPU come riduttore di domanda

Condizioni: banco corto, 448/473 slot, 13/8. Riferimento SOTA 14,74 t/s.

| K | t/s | domanda | buchi | colpi |
|---:|---:|---:|---:|---:|
| 1 | 13,67 | 276.017 | 134.663 | 51,2% |
| 1,8 | 13,11 | 244.839 | 99.302 | 59,4% |
| **2** | **14,17** | 222.052 | 91.544 | 58,8% |
| 3 | 12,53 | 168.087 | **43.990** | **73,8%** |
| lane spenta | 11,85 | — | — | 53,4% |

Con `k_cpu=2` la cache vede **4 esperti per riga invece di 6** (confermato dal log: `CPU=20382 = 2 ×
partizioni=10191`). **K=3 dimezza i buchi (−52%) e perde comunque l'11,6%** sul corto.
**K frazionario è misurato NON monotono** (K=1,8 peggio sia di 1 sia di 2): usare solo interi.

## 1.6 La leva promossa

`LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1`, braccio `r47`, banco lungo (101.691 / completion 256),
coppia appaiata nella stessa sessione:

| | controllo | con la leva |
|---|---:|---:|
| decode | 87,48 ms/tok · **11,43 t/s** | 84,36 ms/tok · **11,85 t/s** |
| p1 (acc/gen) | 0,74725 (136/182) | 0,74725 — identico |
| mean_len | 2,14 | 2,14 — identico |
| SHA output | `D2E3AE05…76D06` | `D2E3AE05…76D06` — **identico byte per byte** |

**+3,67% con traiettoria identica al bit.** Testimone: riga **`porto-cb: … down_tardi=1`** — *non*
`cache-esperti:`, che non ha il campo.

## 1.7 Riproducibilità dei banchi

**Misurata, non assunta**: tre lanci di **processo indipendenti** del banco corto, in configurazione
di produzione (speculazione accesa, `OVERLAP_K=2`, `PIN=1`), danno **SHA, p1, accepted/generated e
mean_len identici**. Varia solo il t/s, dell'1,4%.

Vale anche sul lungo: due bracci con la stessa configurazione danno SHA identico byte per byte.

**Conseguenza pratica**: su questi banchi **lo SHA è un cancello di correttezza valido** anche in
regime speculativo — contro quanto affermava la tabella storica in `cancello-sha-quando-vale`.

---

# 2. PROVE ESEGUITE — cosa è stato provato, in quali condizioni, con quale esito

## 2.1 I dodici bracci

| # | tag | leva / oggetto | banco | esito |
|---|---|---|---|---|
| 1 | — | bonifica `run_porto_hot.ps1` | — | ripuntato al canonico + guardia SHA (avvisa, non blocca) |
| 2 | `r40` | ancora ricostruita **dal log** | lungo | **fallita in caricamento**: mancavano `--no-host` e `-otd` ⇒ OOM pinnata sul drafter |
| 3 | `r41` | ancora con lo script vero + sonda | lungo | riuscita: 11,19 t/s, SHA identico all'ancora del 24/8 |
| 4 | `r42`,`r43` | `SCHED_CPU_BUFT_MAPPED`, ub 2048 e 1024 | lungo | **OOM** sul buffer di calcolo mappato: 524 MiB a ub2048, **260 MiB** a ub1024 (scala con l'ubatch) |
| 5 | `r44`,`r45` | `SCHED_CPU_BUFT_MAPPED` | corto | ramo **raggiungibile** (`mappato ATTIVO`), confini di blocco 10.506 → **432**; ma **SHA divergente** contro **tre** lanci di controllo bit-identici ⇒ **cambia il risultato del calcolo** |
| 6 | `r46` | `FORK_DOWN_TARDI` | lungo | **sessione contaminata** (controllo a 5,46 t/s, cambi di fase VRAM 4234 ms, `warmup_resets`=15) ⇒ scartato |
| 7 | `r47` | `FORK_DOWN_TARDI` | lungo | **+3,67%, SHA identico** (§1.6) |
| 8 | `r48` | `OVERLAP_BATCH_MAX=4`, 3+3 lanci | **corto** | `partizioni` **+1,6%** contro il +50% richiesto ⇒ **bersaglio assente nel banco** (`mean_len` 2,01: non ci sono forward a 4 righe) |
| 9 | `r49` | `OVERLAP_BATCH_MAX=4` | lungo | **crash** (§4.1) |
| 10 | `r50` | `DOWN_TARDI`+`STADI`+`TOPK_FUSO` | lungo | SHA/p1/mean_len divergenti dal controllo |
| 11 | `r51` | `DOWN_TARDI`+`STADI` | lungo | **SHA identico** al controllo ⇒ le due sono pulite; +2,76% (meno di `DOWN_TARDI` da sola) |
| 12 | `r52` | `TOPK_FUSO` da sola | lungo | SHA identico a `r50`-B ⇒ **è lei l'unica causa della divergenza**; +0,79% |

## 2.2 Prove precedenti riprese e verificate in questa campagna

| oggetto | condizioni | esito |
|---|---|---|
| `PESO_COPIA_PM` (politica a tre livelli) | banco 13/8, 448 slot, `nmax=1`, 5 bracci contro 2 riferimenti | **monotono in perdita**: togliendo il 97,2% dei byte si perde il 16,9%; col pavimento anti-collasso −57,8% byte e −2,4% t/s, *pur alzando i colpi di 12,3 punti* |
| `MASSA_CORSIE=1` | banco 17/8, 473 slot, raggiungibilità verificata (`corsie=1` nel log) | **−5,69%**, fuori banda |
| `LLAMA_KV_PAD` 256→1024 | banco lungo 17/8 | `warmup_resets` **invariato** (13.847 = 13.847) |
| `OVERLAP_SPIN` | 0 / 1k / 10k / 100k / 2M | spread **0,9%** |
| `OVERLAP_JOIN_ASYNC` | banco 16/8 | join worker −0,2%, t/s piatto |
| `carico_fantasma` | 4 bracci, parità **bit-esatta 16/16** | +220 MiB/token sul motore DMA costano **−0,53%** (banda 13 GiB/s su copie streaming ideali) |
| sonde diagnostiche accese/spente | a disco, 23/8 | **−1,2%** (14,45 contro 14,28), non il −24% che il commento nel `.bat` attribuiva loro |

## 2.3 Fatti di sorgente verificati (lettura, non misura)

- Le copie host da 65.536 / 98.304 B **non** vengono da `copy_experts`: il suo minimo emissibile è
  2.162.688 B. **16384 = n_embd × 4 B = una riga di stato F32**; 65.536 = `4096 × 2 × 4 × 2 token`,
  98.304 = `× 3 token`, e 2.072 = `ggml_nbytes` della vista con passo di `ids`. **Confermato dalla
  sonda: `copy_experts` = 0 copie, 0 byte su un'intera corsa.**
- L'emettitore è il ripiego strutturale a `ggml-backend.cpp:2302-2308`, perché
  `ggml-cuda.cu:3820-3826` rifiuta `cpy_tensor_async` su **ogni** confine non device-device. Tre
  sincronizzazioni per ingresso, per strato, per forward.
- **Nessuna duplicazione cache/scheduler**: la cache registra un peso solo se il buft è il mappato
  (`ggml-cuda.cu:1570`); il buft mappato condivide `get_name` con CUDA (`:1520`) ⇒
  `sched_buffer_supported` vero ⇒ `ggml-backend.cpp:1640` non crea `input_cpy`. Le due condizioni
  sono l'una la negazione dell'altra.
- `n_expert_used` viene dal GGUF (`deepseek4.expert_used_count`), **nessuna env var lo scavalca**, ma
  `--override-kv deepseek4.expert_used_count=int:5` passa dal loader.
- `K_ADATTIVO` **non è raggiungibile in produzione**: vive dentro `if constexpr (planner_trace)`
  (`cache-esperti.cu:7004`), istanziato solo con `CALENDARIO_TRACE`.
- `OVERLAP_FINESTRA` è **inerte per costruzione**: lo split dopo il ramo CPU contiene
  `concat(esperti_cpu, …)`, quindi la dipendenza dal worker è reale e il join scatta comunque.

---

# 3. MISURE SOSPETTE — non usarle senza rifarle

Questa sezione esiste perché più di un ragionamento della campagna ha poggiato su numeri che non
reggono.

## 3.1 Il normalizzatore nsys è fuori di 1,7-1,8×

Le tabelle nsys `e35` danno proporzioni utilizzabili ma **assoluti no**: il normalizzatore
`n_target_fwd` è dichiarato fuori di 1,7-1,8×. Inoltre nsys con `--cuda-graph-trace=node` **gonfia
del 6-7%**. Usare quelle tabelle **solo per rapporti**, mai per ms/token.

## 3.2 Le due pendenze non riconciliano

**0,431 ms/fwd/1000ctx** (turno 32, tre punti puliti + replica bit-esatta del 64k) contro **0,1456**
(e35, nei suoi propri ms/fwd). Non riconciliano nemmeno correggendo per normalizzatore e distorsione
nsys. **Usare 0,431 per gli assoluti, e35 solo per le proporzioni.** *Item aperto, mai risolto.*

## 3.3 Il regime della tabella nsys non è quello del banco che conta

La tabella `e35` è misurata a **completion 256** (`mean_len` 2,14, colpi 72,6%), il punto SOTA è a
**8192** (`mean_len` 3,06, colpi 51,5%). Sono **184,5 contro 230,8 ms/forward**. Conseguenza:
**le voci che scalano col contesto sono sotto-rappresentate** in quella tabella, quelle piatte
sovrastimate. È **esattamente l'errore che ha prodotto il «trasporto 20,4%»** poi corretto a 45,1%.

## 3.4 Contatori che non esistono e che servirebbero

- **Colpi per classe di riuso**: l'istogramma classifica gli *sfratti* per numero di riusi, ma non
  esiste un contatore dei *colpi* attribuiti a ciascuna classe. L'affermazione «l'1,1% assorbe il
  76% dei colpi» (§1.3) è **dedotta per differenza**, non misurata. Servirebbero ~3 righe.
- **Testimone operativo di `TOPK_FUSO`**: non esiste. La leva è verificabile **solo dal manifesto**:
  se il lettore la leggesse senza usarla, dal log non lo sapremmo.
- **Guardia sugli indici negativi** nella lookup della testa Markov (§4.1): il progetto ha già
  l'idioma (`voci fuori tabella` / `voci negative`, `NOTE_IMPLEMENTAZIONE.md` §7.2), non applicato lì.

## 3.5 Il binario stampa una raccomandazione falsificata

`cache-esperti.cu:8301-8303` stampa a ogni corsa: *«questi in zero-copy costerebbero 0,274 invece di
0,403»*. **Il costo 0,274 è un microbench in isolamento**; misurato in situ lo zero-copy mappato
costa **0,43-0,68 ms/esperto**, cioè **più** della copia. Il binario consiglia una strada falsificata
da cinque bracci.

## 3.6 Misure prese in sessione contaminata

Il braccio `r46` è stato preso dopo nove lanci consecutivi senza riavvio. Firma: **cambi di fase VRAM
100-150× più lenti (4234 ms contro 33) con RAM libera a 87,3 GB** — frammentazione della memoria
pinnabile, non esaurimento. **Qualunque numero preso in quelle condizioni va buttato**, e il
controllo va ri-ancorato **ogni tre bracci**.

## 3.7 Il «costo migra 1:1» viene da un braccio con un baco

L'osservazione che togliendo i blocchi host il tempo migri da `us_sync` a `us_calc_altro`
(−21,47/+21,76 a 51 grafi; −4,09/+5,14 a 301) viene dal braccio `r44`, la cui leva **cambia il
risultato del calcolo**. **Non è utilizzabile come prova** che i blocchi siano lavoro GPU osservato.
La domanda resta aperta e §5.1 dice come chiuderla.

## 3.8 Il `+87,2%` di `partizioni` del 21/8

Misurato in **regime restore** (checkpoint ripristinato), mai riprodotto: sul corto la stessa leva dà
+1,6%, sul lungo il braccio crasha prima di produrre il contatore. **Non sappiamo se dipendesse dal
regime.**

---

# 4. GUASTI APERTI

## 4.1 Indice −1 nella testa Markov del drafter

**Riproducibile.** Condizioni: banco lungo, `-MaxTokens 1200`, reasoning budget 0,
`LLAMA_OVERLAP_BATCH_MAX=4`. Innesco: subito dopo `common_reaso: forced sequence complete, done`.

```
get_rows_q indice invalido: src0=markov_w1.weight src1=CPU#node_509#0 dst=node_510
            i=0 i10=0 i11=0 i12=0  indice=-1  righe=129280
ggml/src/ggml-cpu/ops.cpp:4831: GGML_ASSERT(i01 >= 0 && i01 < ne01) failed
```

Non è l'assert atteso (`ggml.c:6809`, legato a `TILE_VRES`, verificato assente). Il banco corto non
lo incontra perché **`run_porto_hot.ps1` non imposta reasoning-budget** e la richiesta non attraversa
mai il taglio forzato. **In un cammino senza bounds-check quel −1 sarebbe una lettura fuori tabella
silenziosa.**

**Ipotesi non verificata**: il troncamento forzato lascia la finestra del drafter con una posizione
priva di predecessore valido, e a `BATCH_MAX=4` quella finestra è più larga.

## 4.2 `SCHED_CPU_BUFT_MAPPED` altera il calcolo

Il piano dello scheduler è **identico all'unità** (split 262/272/405 su tre corse indipendenti, due
banchi e due ubatch; 35,1 split/grafo a ogni checkpoint; `sched-sync` identico a tre decimali), quindi
non è un cammino di calcolo diverso. Ipotesi superstite: quei ~35 `synchronize` per grafo erano un
**drenaggio di fatto dello stream**, l'unica barriera compatibile con un allocatore che calcola le
durate di vita **assumendo esecuzione sequenziale** (`ggml-backend.cpp:2082-2086`).

## 4.3 Due esposizioni latenti, indipendenti da qualsiasi leva

Oggi mascherate **solo** dai ~35 drenaggi di stream per grafo:
1. **Alias d'arena**: un tensore dell'arena CPU il cui ultimo lettore è lo split GPU `P+1`
   (concorrente col worker) può vedersi riusare la memoria dal worker che calcola `P+2`.
2. **Ingressi utente**: tutti i `GGML_TENSOR_FLAG_INPUT` stanno sul backend CPU; il ramo che li
   protegge fa `sync` prima di sovrascriverli, ma il `set_inputs` del token successivo li riscrive con
   un **memcpy nudo** (`ggml-cuda.cu:1387-1390`) mentre i kernel del grafo precedente possono ancora
   leggerli.

## 4.4 `BATCH_MAX≥4` + `TILE_VRES=1` = abort

`build_moe_ffn_overlap` chiama `ggml_dsv4_moe_decode` senza controllare `n_tokens`
(`llama-graph.cpp:1935-1941`) mentre l'op asserisce `n_tokens <= 3` (`ggml.c:6809`). Oggi
irraggiungibile perché `TILE_VRES` è spento. **Guardia da una riga a `:1936`.**

---

# 5. LAVORO APERTO

## 5.1 Discriminare i blocchi host: lavoro GPU osservato o attesa recuperabile?

**Perché conta**: `sync` + `join` + `sched-sync` = **86% della parete** (§1.4). Se anche solo una
parte fosse attesa recuperabile, sarebbe la voce più grande in gioco.

**La misura**: durante le finestre di blocco host, la GPU sta lavorando o è ferma?

1. **Costo zero**: rileggere i database nsys già su disco (`D:\ds4_work\l3_nsys\e35_nsys{33k,102k}_20260824*.sqlite`,
   `mode=ro`) e calcolare l'occupazione GPU **dentro** gli intervalli di gap già isolati da
   `e36_10_gap_sites.py` / `e36_40_syncwait_overlap.py`.
2. Se il dato non basta: **una** corsa nsys con `--gpu-metrics`, che dà l'occupancy campionata invece
   che dedotta.

**Attenzione al precedente**: in archivio c'è un *«GPU satura al 97,3%»* **misurato in un altro
regime** (13/8, banco e configurazione diversi). **Non usarlo come risposta**: va rifatto sul banco
lungo SOTA, che ha colpi 51,5% invece di ~68% e quindi un profilo di occupazione diverso.

> **ESITO (30/8, misura eseguita sui due DB, dati puliti — vedi `LEDGER_25_AGOSTO.md` §finale):**
> dentro le finestre di `cudaStreamSynchronize` la GPU è attiva al **93,2% / 94,1%** (33k / 102k)
> ⇒ soglia >90% ⇒ **quel fronte si CHIUDE**: il sync è l'host che osserva lavoro GPU, confermato
> per via indipendente. **Ma la premessa era sbagliata**: sotto nsys il sync è il **18,78%** della
> parete (non 50,5% — i contatori applicativi misurano altro), e le sue finestre spiegano solo
> l'**1,1-1,3% della parete** di GPU ferma. Chiuderlo non compra quasi nulla.
> **Il fronte vero riaperto**: la GPU è del tutto ferma per il **38,9-39,3%** della parete, e per
> il **64%** di quel tempo l'host è FUORI da ogni API CUDA (**25,1% della parete**). Il sito n.1
> (35% della massa): dopo `mul_mat_vec_q_moe_maschera` la GPU tace finché le attivazioni del ramo
> CPU non rientrano via H2D su stream 14 — e il silenzio **scala col payload** (723 µs a 64 KiB,
> 1036 a 96 KiB): **la GPU finisce i suoi 4 esperti e aspetta i 2 della CPU. L'overlap non
> sovrappone.** Tetti misurati: senza tutte le bolle **×1,64**; senza le sole bolle del ramo CPU
> **×1,36**. Indecidibile da questi DB (tracciamento CUDA-only): se in quel 25,1% l'host **calcola**
> o **attende** i worker. Le due corse che decidono: (a) nsys `--trace=cuda,osrt` o campionamento
> CPU; (b) `--gpu-metrics` per sapere se le isole «busy» sono sature.

## 5.2 Ridurre i miss — l'unica strada quantificata verso i 20 t/s

Dall'errata: servono **~30 miss/token invece di 119**, cioè **colpi ~88% invece di 51,5%**.

Cosa è già stato provato e come:
- **più slot**: 339→480 alza i colpi di 10 punti ma costa **−8,8%** di t/s (banco e regime del 13/8).
- **`OVERLAP_K=3`**: dimezza i buchi (−52%) e costa **−11,6%** — ma **misurato sul CORTO**, dove uno
  strato dura 3,90 ms contro i 5,37 del lungo (+38% di finestra di giunta) mentre il lavoro CPU non
  dipende dal contesto. **Mai misurato sul lungo.**
- **`n_expert_used` 6→5 / 6→4**: mai provato. Con K=2 la cache vede 4 esperti per riga, quindi
  togliere un esperto è **−25% della domanda GPU**, non −16,7%. Qui **la qualità degrada davvero**:
  cancello obbligatorio di contenuto, non p1 e non t/s (precedente: `ammissione 0,25` produsse HTTP
  500 e 133 byte di risposta **col t/s più alto mai visto**).
- **politica a tre livelli**: falsificata (§2.2), ma **la falsificazione è del 13/8, a `nmax=1` e 448
  slot** — regime in cui una colonna mappata si paga una volta per riga e le righe erano 2 invece di
  ~4. Se qualcuno la riapre, deve dichiarare perché il regime nuovo cambierebbe il segno.

## 5.3 Kernel e codice da riscrivere

| # | sito | cosa | perché |
|---|---|---|---|
| 1 | `kv-ring.cu:365-419` | **materializzazione incrementale**: oggi ricostruisce l'**intero prefisso** a ogni chiamata; il ramo `dbuf` incrementale esiste ma è gated a `n_tokens <= 8`, **mai attivo a ub2048** | è la voce n.1 della pendenza (+0,0350 ms/fwd/1000ctx = 44% della crescita classificata). Il gather G1 è **piatto**: scala la contabilità, non il trasporto. Chirurgo 14 rifiutò `kvring_incr.patch` **per la VRAM, non per il tempo** |
| 2 | `argsort.cu:276` | **top-k reale** al posto di argsort completo: senza `DeviceTopK` cade su argsort+copy con `ncols = n_kv` ⇒ O(n_kv log n_kv) su 26.368 righe per tenerne 512 | 25% della crescita classificata. **Verificare prima** che il tensore ordinato sia davvero lo score-per-posizione: il ledger lo marca **ipotesi** |
| 3 | `lightning-indexer.cu:19-115` | **selezione gerarchica / a blocchi**: il kernel prende `n_kv` a runtime, O(n_kv) **per costruzione** | 27% della crescita classificata. È ricerca, non ingegneria: l'indexer è ciò che *seleziona* le righe |
| 4 | `llama-kv-cache-dsv4.cpp:788` | padding del piano compresso: `GGML_PAD(plan.n_kv, 256u)` **cablato**, e l'allocazione a `:1276`/`:1285` usa la stessa costante **senza clamp** | mai testato indipendentemente. ⚠ alzare il passo **senza** alzare l'allocazione = accesso fuori buffer. E al confine prefill→decode la **VRAM libera è 0 MiB** |
| 5 | `ggml-backend.cpp:2302-2308` | il ripiego a tre sincronizzazioni per ingresso | strutturale, non condizionale: `cpy_tensor_async` rifiuta **ogni** confine CPU↔CUDA (`ggml-cuda.cu:3824`) guardando i **backend**, non i buffer. Qualsiasi fix passa da lì |

## 5.4 Igiene

1. Testimone operativo per `TOPK_FUSO` (§3.4).
2. Rimuovere la raccomandazione falsificata (§3.5).
3. Guardia a `llama-graph.cpp:1936` (§4.4).
4. Contatore dei colpi per classe di riuso (§3.4).
5. Riconciliare le due pendenze (§3.2).
6. Estendere il cancello d'identità del runbook: la riga `cache-esperti:` **non cattura**
   `VRAM_A_FASI*`, `DSV4_INDEXER_FUSO`, `DSV4_PREFILL_*`, `MMQ_X_IDS`, `SCHED_OFFLOAD_PACCHETTI`,
   `CKPT_CRONO`, né `FORK_DOWN_TARDI` (che sta in `porto-cb:`).

---

# 6. STATO OPERATIVO

## 6.1 Binari

| dove | cosa |
|---|---|
| `D:\ds4_prod\bin_stabile_20260825\` | copia stabile: `llama.dll` `ECAEA60B…9C035`, `ggml-cuda.dll` `6EF5B781…C68B52`, `ggml-base.dll` `BAD51D94…D0C65` |
| `D:\llama-subtract\build\bin\` | build chirurgo16: `llama.dll` `12BF6E66…B87EB`, `ggml-base.dll` `D52DA12E…01546` — contiene sonda e leva R1, **entrambe spente di difetto** |
| `…\backup_pre_chirurgo16\` | le 7 DLL precedenti |

## 6.2 Script

- **`p1b_conf.ps1`** (`D:\ds4_work\llama_run\lanciatori_salvati_20260825\`, copia in
  `docs/porto/lanciatori/`): lanciatore del banco lungo. Ha `--no-host` (:219) e `-otd` (:216).
  Esteso il 26/8 con `-OverlapBatchMax` (difetto 3, backup accanto, non-regressione verificata).
- `run_porto_hot.ps1`: banco corto. Ripuntato al canonico + guardia SHA. **Non ha `--no-host`**,
  **non imposta reasoning-budget** (§4.1).
- `run_p1_nudo.ps1`: espone `-OverlapBatchMax` ma ha un cancello d'identità su 5 hash tarato su una
  build vecchia, e il suo checkpoint da 1,05 GB è stato salvato **da quel binario**.

**79 lanciatori salvati** da una directory temporanea di sessione.

## 6.3 Configurazione

Aggiungere `LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1`. Al difetto: `FORK_STADI`, `TOPK_FUSO`,
`OVERLAP_BATCH_MAX` (=3), `SCHED_CPU_BUFT_MAPPED`, `SCHED_SONDA_COPIE`.

---

# 7. PROTOCOLLO — regole verificate sul campo in questa campagna

1. **Verificare che il bersaglio della leva esista nel banco scelto.** `BATCH_MAX=4` mandato sul
   corto, dove `mean_len` 2,01 non produce forward a 4 righe: sei corse perse.
2. **Una leva provata solo sul corto non è provata sulla transizione di fine-reasoning**, che in
   produzione c'è sempre (§4.1).
3. **Misurare che il banco riproduca prima di usare lo SHA come cancello** (§1.7): due lanci di
   controllo. Senza, un verdetto di correttezza resta sospeso fra baco e rumore.
4. **Ri-ancorare il riferimento ogni tre bracci.** Indicatori di salute su ogni corsa: **cambio di
   fase VRAM sotto 100 ms**, `warmup_resets` basso (§3.6).
5. **Non ricostruire un comando: eseguire lo script che l'ha prodotto** (`--no-host` e `-otd` non
   compaiono nel manifesto). **Non aggiornare gli hash attesi** di un cancello d'identità;
   estendere uno script con un parametro a difetto invariato è invece lecito.
6. **Il cancello di qualità non sostituisce quello di identità**: due testi entrambi buoni ma diversi
   sono il sintomo, non l'assoluzione.
7. **Una leva esiste solo se il suo ramo è raggiungibile**: sempre un contatore > 0, altrimenti il
   verdetto è nullo.
8. **L'identità della build è la DLL, non l'exe.** Il build-id è inutile (`build 10093` identico
   attraverso quattro ricompilazioni).
9. **Cancello di caricamento in ogni banco**: entro 2 minuti deve comparire
   `CPU model buffer size = 1010.00 MiB`, **mai** `CUDA_Host model buffer size`.

## Vincoli fisici

- **Tetto della memoria pinnabile ~74,7 GiB**: il modello mappato ne prende 74.304 MiB e il blocco 0
  del drafter altri 2.224 ⇒ **siamo al confine**. Margini: `--no-host` mancante in
  `run_porto_hot.ps1` (1010 MiB), blocco 0 del draft (2.224 MiB).
- **VRAM libera 0 MiB** al confine prefill→decode.
- **MAI `git` dentro `D:\llama-subtract`** (è una copia di worktree).
- Backup della DLL prima di ogni build; mai build sotto campagne altrui (la DLL in uso è lockata).

## Trappole di lettura

- `p1` non è confrontabile fra prompt diversi né fra completion diverse.
- `mean_len` **include il token gratis** del bersaglio: 2,80 = **1,80 token di bozza**.
- Sul lungo il drafter è `draft-dspark` ma **il log stampa `draft_dflash`**.
- I cronometri del drafter **sotto-contano di ~6×** (`process()` non è cronometrato).
- Il wrapper nsys **ingoia lo stdout**: identità via SHA.
- Ogni verdetto di qualità dichiara il **reasoning budget** usato per leggerlo.
