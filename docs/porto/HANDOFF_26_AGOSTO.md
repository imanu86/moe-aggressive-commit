# HANDOFF — 26 agosto 2026
## Campagna «20 t/s sul lungo»: verdetto, stato, e come proseguire

Documento di consegna della sessione di regia del 25-26 agosto. Scritto per essere **l'unico
documento da leggere** prima di riprendere: contiene il verdetto, la configurazione esatta, la
cronaca di ogni braccio con le cifre, il cimitero completo, e i piani operativi per i fronti che
restano.

Cronaca dettagliata: [`LEDGER_25_AGOSTO.md`](LEDGER_25_AGOSTO.md) §7-bis … §8.
Ripresa breve in memoria: `resume-20260826-campagna-20tps-chiusa`.

---

# 1. IL VERDETTO, IN UNA PAGINA

**I 20 t/s sul banco lungo non sono raggiungibili con questo modello su questo hardware.**
Non è una resa: è un numero, ottenuto da tre vie indipendenti che convergono.

| scenario (tutti irrealizzabili, servono come **tetti**) | ms/token | t/s |
|---|---:|---:|
| punto di partenza reale (102k ctx, completion 8192) | 75,44 | **13,26** |
| azzerare l'intera **tassa del contesto** | 61,6 | 16,2 |
| **bozza speculativa perfetta** (accettazione 100%) | 58,8 | 17,0 |
| annullare **tutto il trasporto** degli esperti | 63,8 – 70,3 | 14,2 – 15,7 |
| **sottosistema esperti a costo letteralmente zero** (byte *e* calcolo) | 52,1 | **19,2** |
| **bersaglio** | **50,0** | **20,0** |
| somma onesta di tutto ciò che è vivo e misurato | ~64 | **~17,5** |

Il tetto assoluto — un MoE che non costasse **nulla** — resta sotto il bersaglio. E la proiezione
`COMPOSIZIONE_PIANO.md:496-511`, scritta giorni prima e mai ripescata, diceva già la stessa cosa:
*«il 20 sul lungo è raggiungibile solo nello scenario ottimista»*, e *«il 30-corto NON è
raggiungibile per composizione in nessuno scenario»*.

**Cosa servirebbe davvero** (nessuna di queste è una leva di questa campagna): un modello più
piccolo o diversamente quantizzato; più VRAM, così che gli esperti non attraversino il PCIe a ogni
miss; o un drafter con `block_size` maggiore di 5 (oggi cotto nel GGUF). Il tetto di silicio della
3060 è ~45-47 t/s, quindi **non è fisica: è che il modello non ci sta dentro**. Conferma esterna:
2×DGX Spark in tensor-parallel fanno 41 t/s sul corto e 40 a 100k — a meccanismo rimosso la tassa
del lungo quasi svanisce.

---

# 2. IL BILANCIO DELLA NOTTE

**Una leva promossa · due parcheggiate con dati puliti · una chiusa per crash · una sospesa per
correttezza rotta · cinque fascicoli chiusi per misura quasi senza spendere macchina.**

## 2.1 PROMOSSA — `LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1`

Braccio `r47`, banco lungo (prefill reale 101.691 token, completion 256), coppia appaiata:

| | controllo | con la leva |
|---|---:|---:|
| prefill | 7,24 ms/tok · 138,05 t/s | 7,24 ms/tok · 138,08 t/s |
| **decode** | 87,48 ms/tok · **11,43 t/s** | 84,36 ms/tok · **11,85 t/s** |
| p1 (acc/gen) | 0,74725 (136/182) | 0,74725 — identico |
| mean_len | 2,14 | 2,14 — identico |
| **SHA output** | `D2E3AE05…76D06` | `D2E3AE05…76D06` — **identico byte per byte** |

**+3,67% di decode con traiettoria identica al bit.** Correttezza verificata *prima* dell'adozione.
La leva era misurata e ferma da giorni senza che nessuno l'adottasse.

> **Testimone da grep-are: la riga `porto-cb: … down_tardi=1`, NON `cache-esperti:`** — quest'ultima
> non ha un campo per questa leva, e due bracci con `down_tardi` diverso hanno la riga
> `cache-esperti:` identica carattere per carattere.

## 2.2 Parcheggiate, con dati puliti

- **`FORK_STADI`**: correttezza pulita (in combinazione con `DOWN_TARDI` dà SHA identico al
  controllo), ma **non aggiunge**: `DOWN_TARDI` da sola vale +3,67%, la combinazione +2,76%.
- **`TOPK_FUSO`**: +0,79% (atteso dichiarato +0,90%), sotto la soglia dei +3%. Il suo SHA diverge
  **per costruzione** (fonde nove kernel del router: l'ordine delle somme in virgola mobile cambia),
  quindi il suo cancello non può essere l'identità ma p1 in banda — dove passa, ma **a 1,87σ su un
  limite di 2**. ⚠ **Non ha alcun testimone operativo**: verificabile solo dal manifesto.

## 2.3 Chiusa per crash — `LLAMA_OVERLAP_BATCH_MAX=4`

Sul banco lungo, subito dopo `common_reaso: forced sequence complete, done`:

```
get_rows_q indice invalido: src0=markov_w1.weight src1=CPU#node_509#0 dst=node_510
            i=0 i10=0 i11=0 i12=0  indice=-1  righe=129280
ggml/src/ggml-cpu/ops.cpp:4831: GGML_ASSERT(i01 >= 0 && i01 < ne01) failed
```

Il `+87,2%` di `partizioni` misurato il 21/8 resta una **domanda aperta sul regime restore**, non una
leva viva.

## 2.4 Sospesa per correttezza rotta — `LLAMA_SCHED_CPU_BUFT_MAPPED` (R1)

Uccideva il **96% delle sincronizzazioni** al confine CPU↔GPU (confini di blocco da 10.506 a 432),
ma **cambia il risultato del calcolo**: tre lanci di controllo bit-identici fra loro contro un
braccio divergente su ogni campo. Il piano dello scheduler è però **identico all'unità** (stessi
split, stesse fusioni), quindi la causa non è un cammino diverso — resta un'unica ipotesi viva, che
quei ~35 `synchronize` per grafo fossero **un drenaggio di fatto dello stream**, l'unica barriera
compatibile con un allocatore che calcola le durate di vita assumendo esecuzione sequenziale
(`ggml-backend.cpp:2082-2086`).

## 2.5 Cinque fascicoli chiusi per misura

| fascicolo | come è morto |
|---|---|
| **Speculazione** | bozza perfetta a nmax=3 = 17,0 t/s; tetto duro `block_size=5` nel GGUF; nmax=4 peggiora **per meccanismo** (il blocco è denoisato congiuntamente: allargarlo cambia il problema di denoising, non aggiunge token) |
| **Motore DMA** | il «margine 6×» era un artefatto a **segno invertito**: 0,94 ms era per *lancio* non per esperto; il kernel fa **23 GiB/s** contro 9-13 del DMA, cioè è 1,6-1,8× più veloce |
| **Attribuzione e39** | falsificata prima dall'aritmetica (`copy_experts` non può emettere sotto 2.162.688 B) poi dalla sonda: **0 copie, 0 byte** su un'intera corsa. Le copie sono **attivazioni del ramo CPU** (16384 = n_embd × 4 B) |
| **Duplicazione cache/scheduler** | non esiste: le due popolazioni di byte sono **disgiunte per costruzione** (la cache tocca solo i mappati, lo scheduler non può mai toccarli) |
| **Politica a tre livelli** | 5 bracci, curva **monotona in perdita**: togliendo il 97,2% dei byte si perde il 16,9%. Il meccanismo funziona (colpi +12,3 punti), **il costo per miss ha il segno sbagliato**: lo zero-copy mappato costa 0,43-0,68 ms/esperto contro 0,33-0,40 della copia, e si paga **una volta per riga** mentre la copia si de-duplica |

---

# 3. STATO OPERATIVO — la configurazione esatta di oggi

## 3.1 Binari

| dove | cosa | quando usarlo |
|---|---|---|
| `D:\ds4_prod\bin_stabile_20260825\` | **copia stabile di produzione**: `llama.dll` `ECAEA60B…9C035`, `ggml-cuda.dll` `6EF5B781…C68B52`, `ggml-base.dll` `BAD51D94…D0C65` | **servire il modello** |
| `D:\llama-subtract\build\bin\` | build corrente **chirurgo16**: `llama.dll` `12BF6E66…B87EB`, `ggml-base.dll` `D52DA12E…01546` | **banchi e sviluppo** |
| `D:\llama-subtract\build\bin\backup_pre_chirurgo16\` | le 7 DLL precedenti | ripristino |

Il binario chirurgo16 contiene **la sonda `LLAMA_SCHED_SONDA_COPIE` e la leva
`LLAMA_SCHED_CPU_BUFT_MAPPED`, entrambe spente di difetto**: a leve chiuse il comportamento è
identico al canonico.

> **REGOLA: la produzione non punta mai a una directory di build.** `avvia ds4 locale.bat` è stato
> ripuntato alla copia stabile (backup accanto). *L'utente ha chiarito che quel `.bat` è un
> esperimento, non la sua configurazione di lavoro.*

## 3.2 Script di banco

| script | dove | note |
|---|---|---|
| **`p1b_conf.ps1`** | `D:\ds4_work\llama_run\lanciatori_salvati_20260825\` e `docs/porto/lanciatori/` | **il lanciatore del banco lungo**. Ha `--no-host` (riga 219) e `-otd` (216). Esteso il 26/8 con `-OverlapBatchMax` (difetto 3, backup accanto, non-regressione verificata con tre controlli) |
| `run_porto_hot.ps1` | `…\Codex\2026-08-15\…\work\` | banco corto. Ripuntato al binario canonico + guardia che stampa `IDENTITA-DLL: <sha>` (avvisa, non blocca). **Non ha `--no-host`** e **non imposta reasoning-budget** |
| `run_p1_nudo.ps1` | `…\Codex\2026-08-20\…\work\` | espone `-OverlapBatchMax`, ma ha un **cancello d'identità su 5 hash** tarato su una build vecchia. **Non aggiornare quegli hash** |

**79 lanciatori sono stati salvati** da una directory temporanea di sessione: senza quel salvataggio
l'intera anatomia e35→e39 sarebbe diventata irriproducibile alla prima pulizia del disco.

## 3.3 Configurazione SOTA aggiornata

Aggiungere alla configurazione di riferimento: **`LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1`**.
Restano al difetto: `FORK_STADI`, `TOPK_FUSO`, `OVERLAP_BATCH_MAX` (=3), `SCHED_CPU_BUFT_MAPPED`,
`SCHED_SONDA_COPIE`.

## 3.4 I tre banchi, e perché non sono intercambiabili

| banco | prompt | completion | ms/token | t/s | mean_len | p1 |
|---|---:|---:|---:|---:|---:|---:|
| corto | 68 | 1200 | 59,97 | 16,68 | 2,80 | 0,90281 |
| lungo 102k «ancora» | 101.691 | 256 | 86,23 | 11,60 | 2,14 | 0,74725 |
| **SOTA lungo** | 101.691 | **8192** | **75,44** | **13,26** | **3,06-3,18** | 0,90229 |

Le statistiche a completion 256 sono una **finestra precoce**, non l'aggregato stazionario: sullo
**stesso prompt** `mean_len` passa da 2,14 a 3,18 e i colpi di cache da 72,6% a 51,5%. **Non
confrontare mai bracci a completion diverse.**

---

# 4. IL BUDGET DEL TOKEN LUNGO — dove va il tempo

## 4.1 La scomposizione additiva

```
pavimento di regime   61,6 ms/token   81,7%    (= il costo del banco corto)
tassa del contesto    13,8 ms/token   18,3%
                      ─────────────
totale                75,4                      chiude allo 0,1% col misurato
```

Controprova indipendente: corto ri-ancorato 61,84 + 13,8 = **75,6 contro 75,44** = 0,2%.
**Conseguenza che riordina ogni priorità: azzerare l'intera tassa del contesto dà 16,2 t/s.** Ogni
leva che attacca solo la pendenza (padding dei grafi, kv-ring, argsort, indexer) è limitata **per
costruzione** al 18,3% del budget.

## 4.2 Il trasporto è il 45%, non il 20%

⚠ Correzione importante a tutti i documenti precedenti. L'aritmetica «409 MiB/token → 20,1%» era
ancorata alla finestra a 256 token (colpi 72,6%). Sul banco vero:

```
buchi 976.213 / 8192 token = 119,2 miss/token × 6,75 MiB = 804 MiB/token
a 23,07 GiB/s = 34,0 ms/token = 45,1% della parete
```

Confermato da una seconda corsa (45,7%). **Ma togliere byte rende poco**: misurato sul braccio del
21/8, 10,5 ms/token di trasporto rimosso hanno mosso la parete di 1,55 (grezzi) / 3,63
(normalizzati) ⇒ **si realizza il 15-34%** di ciò che si toglie, perché il fork **sovrappone** la
copia al calcolo e la corsia CPU **paga in tempo CPU**.

## 4.3 Il trasporto è tempo di BUS, e la prova è un vuoto

Le durate di `kern_fj_copia` sono **quantizzate**: armoniche pulite a 280-350, 560-640, 840-940,
1100-1220 µs, quanto fondamentale **285,7 µs/esperto**. E c'è un **vuoto assoluto fra 10 e 250 µs**:
non esiste una seconda famiglia veloce, quindi **nessun esperto è servito dalla VRAM — passano tutti
dal PCIe allo stesso prezzo**.

`kern_copia` è grid-stride a `int4`, griglia 4×SM = 112 blocchi, sorgente **host mappata**: ogni load
è una lettura PCIe, **gli SM occupati sono in stallo sul bus, non a calcolare**. Lo sweep della
griglia è monotono decrescente (8→4 blocchi −6,04%, 4→2 −25,32%): **è già all'ottimo**, ridurla
de-satura il bus.

E «meno byte» è quasi esaurito: gli esperti sono già a **IQ2_XXS, 2,0625 bpw**.

## 4.4 Il churn, e il nucleo caldo che è l'1,1%

Al punto SOTA lungo:
```
domanda 2.011.416 (colpi 1.035.203 = 51,5%, buchi 976.213)
riusi:  mai=82,1%  ·  1 uso=12,2%  ·  2-3=4,6%  ·  4+=1,1%
bussate al momento del buco:  1=5,2%  2=2,0%  3=1,4%  4-7=9,6%  **8+=81,9%**
```
Riuso medio **1,06 per installato, mediana zero**. Ma le classi 1 e 2-3 spiegano al massimo ~250k
colpi su 1.035k ⇒ **i restanti ~785k (76%) stanno nella coda `4+`, che è l'1,1% degli installati**.
**Il nucleo caldo esiste ed è minuscolo.** E `bussate 8+ = 81,9%` dice che i buchi **non sono
esperti freddi**: sono esperti con storia lunga, continuamente sfrattati. **È thrashing, non working
set assente** — e la capienza non è il vincolo (473 slot bastano al nucleo).

## 4.5 Il rendezvous: costa il 23%, compra l'1,5%

I quattro campi di `sched-profilo-finale` **non stanno sullo stesso thread**: `attesa-lavoro`,
`evento` e `calcolo` sono del **worker**; **solo `join` è del thread principale** ed è l'unica voce
di parete. `evento` e `calcolo` sono **annidati dentro** `join`, non additivi (rapporto 97,7-98,5%).
**La sovrapposizione nasconde l'1,5-2,3% del lavoro del ramo CPU: praticamente non avviene**, perché
la finestra è larga **un solo split** (65 µs) contro 2,85 ms di lavoro.

Budget del thread principale: **sync 50,5% + join 23,4% + sched-sync 12,0% = 86% BLOCCATO**, con
controprova che chiude al 99,9%. `confini evento/blocco = 0 / 320.661`: **zero confini passano da
eventi, tutti blocchi host**.

**Ma il ramo CPU rende CAPIENZA, non calcolo**: con `k_cpu=2` su 6 esperti toglie **1/3** della
domanda alla cache. Spegnerlo costa **−19,6%**. **`OVERLAP_K=0` non è una leva: è una regressione.**

---

# 5. IL CIMITERO — non riaprire senza una ragione nuova

Ogni voce è stata **misurata**, non supposta.

| leva | come è morta |
|---|---|
| `LLAMA_SCHED_CPU_BUFT_MAPPED` (R1) | cambia il risultato del calcolo (SHA divergente contro 3 controlli bit-identici) |
| `LLAMA_OVERLAP_BATCH_MAX=4` | crash, indice −1 sulla testa Markov al taglio del reasoning |
| `LLAMA_OVERLAP_K=0` | **−19,6%** |
| `LLAMA_OVERLAP_PIN=0` | equivale a K=0 sul trasporto ma paga anche la partizione |
| `LLAMA_OVERLAP_FINESTRA` | **inerte per costruzione**: lo split dopo il ramo CPU contiene `concat(esperti_cpu, …)`, quindi la dipendenza dal worker è reale e il join scatta comunque |
| `LLAMA_OVERLAP_SPIN` | spazzata: 0/1k/10k/100k/2M dentro lo 0,9% |
| `LLAMA_OVERLAP_JOIN_ASYNC` | join worker −0,2%, t/s piatto |
| `PESO_COPIA_PM`, `MASSA_CORSIE`, `CPU_LEGGERI` | 5 bracci + 1, tutti negativi (−2,1% … −16,9%, e −5,69%) |
| `LLAMA_KV_PAD` 256→1024 | `warmup_resets` **invariato** (13.847 = 13.847) |
| capienza (più slot) | 339→480: colpi +10 punti, **t/s −8,8%** |
| prefetch (tutte le varianti) | oracolo 5,97 t/s contro cieco 5,89 contro **11,89 a prefetch spento** |
| insieme statico / nucleo caldo precalcolato | miglior set statico 37,5% contro 59,4% della LRU dinamica |
| repoint / B-2 | 3 falsificazioni; con SORT_CHUNK=8 è **perdita netta +7%** |
| griglia di copia più larga | curva **monotona decrescente**: il ginocchio è a 8, la SOTA l'aveva già |
| `GGML_SCHED_EVENT_JOIN` | **N=0 su 10.506 confini**: ramo irraggiungibile |
| super-op CPU FFN / macro-kernel decode v2 | contorno device solo 5,7 ms/token, **nessun pezzo >1%** |
| `nmax=4` e `nmax=5` | −12,79% e peggio; a nmax=4 **`mean_len` SCENDE** (2,80 → 2,43) |
| verifica ad albero | la KV DSV4 **non sa potare rami interlacciati**; e un albero aggiunge **righe**, che sono la risorsa scarsa |
| «G1 libera il PCIe» | il bus non è **mai** stato il vincolo: +222,9 MiB/token costano −0,53% |

---

# 6. COME PROSEGUIRE

Quattro fronti, in ordine di valore. **Il primo è l'unico che possa ancora muovere il numero.**

## FRONTE 1 — Riaprire le bolle con la misura che decide *(costo: zero macchina)*

**Perché**: le bolle sono il **39,3% della parete**, l'unica voce abbastanza grande. Il verdetto «il
costo migra 1:1, quindi erano lavoro GPU osservato» viene dal braccio `r44`, che il controllo di
rumore ha poi **invalidato** (la leva aveva un baco). **La domanda è aperta, non chiusa.**

**La misura che la decide, e i dati potrebbero essere già sul disco.** La domanda è: *durante le
finestre di blocco host, la GPU sta lavorando o è ferma?*

- Se la GPU è **satura** durante quelle finestre ⇒ i blocchi sono **lavoro osservato**, il fronte si
  chiude **definitivamente** e la campagna è finita per davvero.
- Se la GPU è **idle** ⇒ c'è tempo recuperabile, e vale progettare un meccanismo che non tocchi il
  calcolo (diversamente da R1).

**Come farla, in ordine di costo:**
1. **Zero corse**: rileggere i database nsys già su disco (`D:\ds4_work\l3_nsys\e35_nsys{33k,102k}_20260824*.sqlite`,
   `mode=ro`) e calcolare l'**occupazione GPU dentro le finestre di gap** già isolate dagli script
   `e36_10_gap_sites.py` / `e36_40_syncwait_overlap.py`. Serve incrociare i kernel attivi con gli
   intervalli di blocco.
   ⚠ Attenzione: c'è un indizio forte già in archivio — *«la GPU è satura al 97,3%»* — che se
   confermato **chiude il fronte senza scrivere una riga**. Verificarlo è il primo passo.
2. Se il dato non basta: **una** corsa nsys con `--gpu-metrics` sul banco lungo, che dà l'occupancy
   campionata invece che dedotta.

**Go/no-go pre-registrato**: occupazione GPU nelle finestre di blocco **> 90%** ⇒ fronte chiuso,
scriverlo nel ledger e fermare la campagna. **< 70%** ⇒ c'è spazio, si progetta. In mezzo ⇒ serve la
corsa con `--gpu-metrics`.

## FRONTE 2 — Il bug dell'indice −1 *(costo: chirurgia piccola)*

`ops.cpp:4831`, `markov_w1.weight`, indice −1 al taglio forzato del reasoning con
`OVERLAP_BATCH_MAX=4`. **Riproducibile.** Qui l'assert ha salvato la corsa, ma **lo stesso −1 in un
cammino senza bounds-check sarebbe una lettura fuori tabella silenziosa** — numeri sbagliati senza
alcun errore.

**Piano**: (a) risalire a **chi** scrive −1 in quell'indice — il sospetto è che il troncamento
forzato lasci la finestra del drafter con una posizione priva di predecessore valido, e che a
`BATCH_MAX=4` quella finestra sia più larga e il caso degenere diventi raggiungibile (**non
verificato**); (b) aggiungere il **contatore di guardia** con l'idioma già in uso nel progetto
(`voci fuori tabella` / `voci negative`, `NOTE_IMPLEMENTAZIONE.md` §7.2), che deve restare **zero**
su ogni corsa; (c) solo dopo, valutare se `BATCH_MAX=4` diventa percorribile.

## FRONTE 3 — Igiene, tutta a basso costo

| # | cosa | perché |
|---|---|---|
| 1 | **Testimone operativo per `TOPK_FUSO`** (una riga di log) | oggi è verificabile **solo dal manifesto**: se il lettore la leggesse senza usarla, non lo sapremmo |
| 2 | **Rimuovere la raccomandazione falsificata** stampata a ogni corsa (`cache-esperti.cu:8301-8303`: *«in zero-copy costerebbero 0,274 invece di 0,403»*) | il binario **consiglia una leva falsificata da 5 bracci** |
| 3 | **Guardia** a `llama-graph.cpp:1936` | `BATCH_MAX≥4` + `TILE_VRES=1` = `GGML_ASSERT` (`ggml.c:6809`) |
| 4 | Riconciliare la **pendenza**: 0,431 ms/fwd/1000ctx (turno 32) contro 0,1456 (e35) | non riconciliano nemmeno correggendo normalizzatore e distorsione nsys. Usare **0,431 per gli assoluti**, e35 solo per le proporzioni |
| 5 | Estendere il **cancello d'identità del runbook** | la riga `cache-esperti:` **non cattura** `VRAM_A_FASI*`, `DSV4_INDEXER_FUSO`, `DSV4_PREFILL_*`, `MMQ_X_IDS`, `SCHED_OFFLOAD_PACCHETTI`, `CKPT_CRONO`: due bracci possono averla identica e differire su leve decisive |

## FRONTE 4 — Le due esposizioni latenti *(da conoscere, non necessariamente da toccare)*

Oggi mascherate **solo** dai ~35 drenaggi di stream per grafo. Chiunque tocchi quel meccanismo le
riporta a galla:
1. **Alias d'arena**: un tensore dell'arena CPU il cui ultimo lettore è lo split GPU `P+1`
   (concorrente col worker) può vedersi riusare la memoria dal worker che calcola `P+2`.
2. **Ingressi utente**: tutti i `GGML_TENSOR_FLAG_INPUT` stanno sul backend CPU; il ramo che li
   protegge fa `sync` *prima* di sovrascriverli, ma il `set_inputs` del token successivo li riscrive
   con un **memcpy nudo** (`ggml-cuda.cu:1387-1390`) mentre i kernel del grafo precedente possono
   ancora leggerli.

## Se l'obiettivo resta 20 t/s

Nessuna leva software ci arriva. Le strade reali sono **strutturali**: un modello più piccolo o
diversamente quantizzato; più VRAM (così gli esperti smettono di attraversare il PCIe a ogni miss —
oggi **nessuno** è servito dalla VRAM); un drafter con `block_size` > 5. In alternativa, **cambiare
il bersaglio**: dichiarare che il banco a 8192 completion non è il carico da ottimizzare, e scegliere
un regime dove i 20 sono definibili.

---

# 7. REGOLE DI METODO — sei, tutte pagate con corse vere

1. **Verificare che il bersaglio della leva ESISTA nel banco scelto, prima di lanciare.** Una leva
   che dipende da `mean_len` va misurata dove `mean_len` è quello vero. *Costo dell'errore: sei
   corse — `BATCH_MAX=4` era stato mandato sul banco corto, dove `mean_len` 2,01 non produce forward
   a 4 righe e la leva non aveva bersaglio.*
2. **Una leva provata solo sul banco corto non è stata provata sulla transizione di fine-reasoning**,
   che in produzione c'è sempre: il runner corto non imposta reasoning-budget, ed è esattamente lì
   che `BATCH_MAX=4` crasha.
3. **Prima di usare lo SHA come cancello, misurare che il banco riproduca**, con due lanci di
   controllo a parità di tutto. Su questi banchi riproduce bit-esatto **anche con speculazione
   accesa e K=2** — contro quanto diceva la tabella storica. Senza quel controllo, il verdetto su R1
   sarebbe rimasto sospeso per sempre fra «baco» e «rumore».
4. **Ri-ancorare il riferimento ogni tre bracci** (non a fine giornata), e trattare **cambio di fase
   VRAM sotto 100 ms** e `warmup_resets` come indicatori di salute della **sessione**, su ogni corsa.
   La firma della contaminazione è: cambi di fase 100-150× più lenti **con RAM libera abbondante** =
   frammentazione della memoria pinnabile dopo molti lanci.
5. **Non si ricostruisce un comando: si esegue lo script che l'ha prodotto** (`--no-host` e `-otd`
   non compaiono nel manifesto, e la loro assenza fa esplodere la memoria pinnata in caricamento). E
   **non si aggiornano gli hash attesi** di uno script per far passare un cancello d'identità —
   **estenderlo con un parametro a difetto invariato invece è lecito**.
6. **Il cancello di qualità non è un sostituto del cancello di identità**: due testi entrambi ottimi
   ma diversi fra loro sono il **sintomo**, non l'assoluzione.

**Più tre regole ereditate che hanno retto:** una leva esiste solo se il suo ramo è raggiungibile
(sempre un contatore > 0, o il verdetto è nullo) · l'identità della build è **la DLL, non l'exe** ·
un agente che chiude il turno dicendo «resto in attesa» non riparte da solo: la sorveglianza è
**polling attivo dentro il turno**.

---

# 8. TRAPPOLE OPERATIVE — la lista da rileggere prima di toccare qualcosa

- **MAI comandi `git` dentro `D:\llama-subtract`**: è una **copia** di un worktree (il suo `.git` è
  un file che punta a `D:/llama-dspark/.git/worktrees/llama-overlap`). Un commit da lì muove il
  branch `overlap` sotto il worktree vero.
- **Backup fisico della DLL prima di ogni build**, e mai build sotto campagne altrui (su Windows la
  DLL in uso è lockata: il link fallisce con `LNK1104` — si aspetta, non si forza).
- **Cancello di caricamento in ogni banco**: entro i primi 2 minuti deve comparire
  `CPU model buffer size = 1010.00 MiB`, **mai** `CUDA_Host model buffer size`. Se compare
  `CUDA_Host`, la corsa è già persa: abortire subito.
- **Tetto della memoria pinnabile**: ~74,7 GiB sì / 76,9 no. Il modello mappato ne prende 74.304 MiB
  e il blocco 0 del drafter altri 2.224: **siamo già al confine**. Margini recuperabili se
  servissero: `--no-host` mancante in `run_porto_hot.ps1` (1010 MiB) e il blocco 0 del draft.
- **VRAM libera 0 MiB** al confine prefill→decode: **nessuna leva può chiedere VRAM lì.**
- **`p1` non è mai confrontabile** fra prompt diversi né fra finestre di completion diverse.
- **Ogni verdetto di qualità dichiara il reasoning budget** usato per leggerlo (runbook §4.10).
- Il **wrapper nsys ingoia lo stdout** del server: l'identità si verifica via SHA, non dal log.
- Il **build-id è inutile** come identità (`build 10093` identico attraverso 4 ricompilazioni): solo
  SHA256.
- Sul lungo il drafter è **`draft-dspark`** ma **il log stampa `draft_dflash`** (struct condivisa).
- **`mean_len` include il token gratis** del bersaglio: `mean_len 2,80` = **1,80 token di bozza**.
- I cronometri del drafter **sotto-contano di ~6×** (`process()` non è cronometrato).

---

# 9. DA DOVE RIPARTIRE, IN CONCRETO

**Se hai dieci minuti**: leggi §1 (il verdetto) e §6 FRONTE 1 (la misura che decide). Poi rileggi
l'indizio *«la GPU è satura al 97,3%»* nell'archivio: se regge, la campagna è chiusa e lo si scrive.

**Se hai un'ora e nessuna macchina**: esegui il FRONTE 1 punto 1 — occupazione GPU nelle finestre di
blocco, dai database nsys già su disco. È l'unica misura rimasta che possa cambiare il verdetto, e
non costa una corsa.

**Se hai la macchina**: adotta `FORK_DOWN_TARDI=1` nella configurazione di riferimento (è già
certificato) e, se vuoi una conferma indipendente, replicalo una volta — ricordando di ri-ancorare
il controllo nella stessa sessione.

**Se vuoi chiudere il cerchio con onestà**: il fascicolo `BATCH_MAX=4` ha lasciato una domanda
aperta — il `+87,2%` di partizioni del 21/8 dipendeva dal **regime restore**? Rispondere richiede un
checkpoint fresco creato col binario di oggi, ed è l'unica strada legittima (non si aggiornano gli
hash del cancello).

**Quello che non va fatto**: riaprire una qualsiasi voce del §5 senza una ragione nuova e scritta.
Ognuna è costata corse vere.
