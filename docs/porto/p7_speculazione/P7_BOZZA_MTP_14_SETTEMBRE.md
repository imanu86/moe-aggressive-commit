# P7 · cella 1 — lunghezza della bozza MTP — 14 settembre 2026

Operatore: prima cella di P7 del piano CPU/GPU verso 50 t/s. Macchina: RTX 3060 12 GB, Ryzen 5800X
(16 thread), 96 GB DDR4, Windows 11. Modello Qwen3.8-Flash-Next UD-IQ3_XXS, 64 slot di cache esperti.

**Nessuna modifica di codice e nessuna build in questa cella: solo preset e corse.** Binari
sperimentali ORIGINALI `qwen38_clean\build\bin` (gli stessi di `preset_A.json`), non quelli patchati
di `D:\ds4_work\p3_work`. `bin_prod`, i sorgenti, il lanciatore quotidiano e il modello non sono
stati toccati. Nessun commit.

---

## 0. Verdetto in tre righe

1. **La bozza a 2 token PERDE il 4,05%** contro la bozza a 1 token sullo stesso banco
   (27,50 contro 28,66 t/s). Sul solo sottoinsieme a 32k, dove i tre bracci producono testo
   **identico byte per byte**, la perdita è **−4,74%**. La soglia era +5%: **non raggiunta, e di
   segno opposto**.
2. Di conseguenza **M3 (bozza a 3 token) non è stato eseguito**, ed è bene così: il percorso veloce
   locale ammette **al massimo 3 righe di verifica**, cioè esattamente una bozza di 2 token. Una
   bozza di 3 token chiederebbe 4 righe e farebbe scattare due `GGML_ASSERT` (§5).
3. Il risultato utile della cella non è la leva in esame ma il suo riferimento: **la bozza MTP a 1
   token vale +17,31%** sul riferimento MTP spento di questo banco (28,66 contro 24,43 t/s), a costo
   di ~550 MiB di VRAM e ~3,2 GB di RAM.

---

## 1. Manopole usate (nomi esatti e valori)

Entrambe le celle partono da `docs/porto/banco_p0/preset_A.json` e aggiungono **solo** il ramo
`:con_mtp` del lanciatore sperimentale. I preset sono in repo:
`docs/porto/banco_p0/preset_M2_p7.json` e `preset_M1_p7.json`.

| manopola | M2 (candidato) | M1 (riferimento della leva) | dove |
|---|---|---|---|
| `--spec-type` | `draft-mtp` | `draft-mtp` | argomento — **n-grammi SPENTI** |
| `--spec-draft-n-max` | **2** | **1** | argomento — *è la sola leva in esame* |
| `--spec-draft-n-min` | 1 | 1 | argomento |
| `--spec-draft-p-min` | 0 | 0 | argomento |
| `-md` | `mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf` | idem | argomento |
| `-ngld` | 99 | 99 | argomento |
| `-otd` | `.*ffn_.*_exps.*=CUDA0_Mapped` | idem | argomento — esperti della bozza in RAM |
| `-ctkd` / `-ctvd` | `q8_0` / `q8_0` | idem | argomento |
| `LLAMA_MTP_LIGHT` | 1 | 1 | ambiente |
| `QWEN4EXP_INDEXER_F32_BATCH` | 1 | 1 | ambiente |
| `QWEN_MOE_SCALAR_BATCH` | 2 | 2 | ambiente |
| `QWEN4EXP_SPARSE_FA` | 0 | 0 | ambiente (come in `preset_A`) |
| `MOE_SLOTS` / `--moe-expert-cache` | 64 | 64 | argomento |

Tutto il resto è identico a `preset_A.json`: contesto 262144, `-b`/`-ub` 2048, `-t 16`, `-np 1`,
`--jinja --reasoning on --reasoning-preserve`, `-ctk`/`-ctv q8_0`, `--no-mmap`, `--n-cpu-moe 48`,
greedy `temperature 0`, `seed 1234`, profilo `solo_libero`, budget `screening` = **1024 token**.

### Rollback: la manopola non serviva, lo stato è già coerente

`QWEN_NGRAM_ROLLBACK` **esiste** in `build\bin\llama-common.dll` (verificato per stringa), ma
riguarda i soli draft **n-gram** brevi, qui assenti. Con la bozza MTP la lunghezza del draft
dimensiona da sola gli stati ricorrenti, e il log lo conferma:

| cella | `llama_context: n_rs_seq` | `llama_memory_recurrent: size` |
|---|---|---|
| M1 (bozza 1) | **1** | **225,14 MiB** (1 cella, 48 strati, 1 rs_seq) |
| M2 (bozza 2) | **2** | **337,71 MiB** (1 cella, 48 strati, 2 rs_seq) |

I **+112,57 MiB** sono esattamente il costo che Codex attribuiva al rollback a due stati in
`VERSO_50_TPS_400_PREFILL_13_SETTEMBRE_CODEX.md`. **Nessuna variabile è stata impostata per
ottenerlo.** Corollario: lo «stato di rollback coerente» è un problema dei soli n-gram; per la testa
MTP è automatico.

---

## 2. Tabella per cella

Profilo `solo_libero`: 8 prompt liberi a contesto corto + gli stessi 8 dopo un prefisso da 32.768
token. `t/s` = **somma dei token accettati finali / somma del tempo di generazione del server**
(`predicted_n` / `predicted_ms`), come prescrive il protocollo. Una replica per cella.

| cella | bozza | t/s libero | ms/token accettato | corto | ctx32k | accettazione | token per passata |
|---|---:|---:|---:|---:|---:|---:|---:|
| **RIF — MTP spento** (14/9 07:20) | — | **24,4344** | 40,926 | 23,008 | 26,069 | — | 1,000 |
| **M2 — bozza 2** | 2 | **27,5030** | 36,360 | 28,928 | 26,224 | **0,660** | **2,323** |
| **M1 — bozza 1** | 1 | **28,6646** | 34,886 | 29,875 | 27,529 | **0,785** | **1,788** |

Token accettati / tempo, per cella: RIF 15.687 / 642,004 s · M2 15.523 / 564,411 s ·
M1 15.741 / 549,145 s. Nessun guasto, nessun NaN, nessun `error`/`assert` nei due log del server.

### Delta

| confronto | insieme libero | solo corto | solo ctx32k (testi identici) |
|---|---:|---:|---:|
| **M2 / M1** | **−4,05%** | −3,17% | **−4,74%** |
| M1 / RIF | **+17,31%** | +29,85% | +5,60% |
| M2 / RIF | **+12,56%** | +25,73% | +0,60% |
| M3 / M1 | *non eseguita* (§5) | — | — |

**Il confronto pulito è la colonna ctx32k**: lì i tre bracci generano **gli stessi 7.800 token con le
stesse otto impronte SHA256**, quindi il rapporto non è contaminato da traiettorie diverse. Dà
**−4,74%** per M2 su M1 e **+5,60%** per M1 sul MTP spento.

**Termine di paragone per la variabilità:** l'A/B nullo di P0 (due processi identici, stesso preset)
aveva dato un rapporto **1,00057**, cioè **+0,06%**
(`D:\ds4_work\banco_p0_run\aggregato_baseline_libero_20260914.json`). Il −4,05% è ~70 volte quella
variabilità.

### Accettazione per posizione

Dalla riga cumulativa `common_specu: statistics draft-mtp` a fine corsa (log del server, `-lv 4`):

| cella | passate | token abbozzati | token di bozza accettati | accettazione | `mean acc len` | accettazione per posizione |
|---|---:|---:|---:|---:|---:|---|
| M1 | 8.811 | 8.811 | 6.919 | 0,785 | 1,79 | **(0,785)** |
| M2 | 6.690 | 13.375 | 8.823 | 0,660 | 2,32 | **(0,766 · 0,553)** |

Per singola richiesta l'escursione è larga: da 0,49 (L02, ragionamento lungo) a 0,90-0,91 (L05,
aritmetica) in M2; da 0,63 a 0,96 in M1. È la stessa banda 0,70-0,75 dichiarata da Codex, misurata
qui su un carico di sola risposta libera.

### Aritmetica del ciclo — perché la seconda posizione non paga

Con `draft_n` dell'insieme libero si ricavano le passate di verifica (M1: 8.805; M2: 13.367/2 =
6.683,5) e quindi il costo di un ciclo:

| | M1 (2 righe di verifica) | M2 (3 righe di verifica) |
|---|---:|---:|
| ms per ciclo | **62,37** | **84,45** |
| token accettati per ciclo | 1,788 | 2,323 |
| di cui costo della testa di bozza | 5,67 ms (49,99 s / 8.811) | 11,10 ms (74,23 s / 6.690) |
| costo della verifica | 56,7 ms | 73,3 ms |

La testa di bozza costa **5,5-5,7 ms per token abbozzato, perfettamente lineare** (coerente con i
5,0 ms dell'handoff). La terza riga di verifica costa **+16,6 ms**. In totale la seconda posizione
di bozza costa **22,08 ms** e rende **0,535 token**, che al ritmo di M1 (34,886 ms/token) valgono
**18,67 ms**: perdita netta **3,4 ms per ciclo**, cioè 22,8 s sulla corsa — ed è esattamente il
divario misurato (564,4 s contro i 541,6 s che M1 impiegherebbe per gli stessi 15.523 token).

> **Il numero da battere, in forma falsificabile: perché una bozza di 2 token pareggi, la SECONDA
> posizione deve accettare ≥ 0,633. Accetta 0,553.** Mancano ~8 punti. Non serve alzare
> l'accettazione media: serve alzare quella della seconda posizione, che è l'unica che paga la terza
> riga di verifica.

---

## 3. Impronte contro il riferimento MTP spento

Riferimento: `D:\ds4_work\banco_p0_run\20260914_072049_P0_sper_ibrido_assente_r1`.

| cella | impronte uguali al riferimento | diverse |
|---|---:|---|
| M2 | **10 / 18** (2 riscaldamenti + **tutti e 8** i casi `ctx32k`) | **tutti e 8** i casi `corto` |
| M1 | **10 / 18** (2 riscaldamenti + **tutti e 8** i casi `ctx32k`) | **tutti e 8** i casi `corto` |

Lo schema è netto e va riportato così com'è:

- **A 32k la speculazione non cambia una virgola.** Otto casi su otto, in entrambe le celle, con
  impronta identica a quella del MTP spento e identico numero di token (7.800). Con verifica esatta
  in greedy è il comportamento atteso, ed è la prova che la verifica è corretta.
- **A contesto corto i tre bracci divergono, e divergono anche fra loro** (M1 ≠ M2 ≠ RIF). La
  divergenza non è al primo token: compare al carattere 561 (L01), 340 (L04), 138 (L05) — cioè a
  metà di un ragionamento, dopo centinaia di token identici. È la firma di un pareggio fra due logit
  ribaltato da differenze numeriche minime, non di un errore sistematico (stessa lettura di §2.5
  dell'handoff sulla sparse FA).

**Ipotesi, non misurata**, su perché i corti divergono e i 32k no: a contesto corto `n_kv` è piccolo
e `qwen4exp.cpp:1239` non prende il cammino *gather* (`gather = ... && n_kv >= 4*width`), quindi
l'attenzione gira densa e la sua configurazione di kernel dipende dal numero di righe del batch; con
il prefisso da 32k il *gather* scatta sempre e i numeri smettono di dipendere dal numero di righe.
**Da falsificare** ripetendo un braccio corto due volte (regola di metodo: due corse identiche devono
dare lo stesso testo; non è stato fatto in questa cella).

Conseguenza pratica per chi legge la tabella: **la metà `corto` dei delta non è iso-testo** e va
usata con prudenza; la metà `ctx32k` sì.

---

## 4. Carico, memoria, prefill

| | RIF (MTP off) | M1 (bozza 1) | M2 (bozza 2) |
|---|---:|---:|---:|
| VRAM di picco | 11.039 MiB | 11.588 MiB | **11.706 MiB** (su 12.288) |
| RAM usata di picco | 87,87 GB | 91,03 GB | 91,13 GB |
| GPU media | 96,4% | 93,8% | 94,6% |
| caricamento del server | — | 201 s | 176 s |
| prefill L01@ctx32k, cache vuota (32.944 token) | **333,79 t/s** | 329,19 t/s | 329,27 t/s |

- Il MTP costa **+549 MiB di VRAM** (97 MiB della testa + stato ricorrente + contesto bozza) e
  **~3,2 GB di RAM** (2.550 MiB di esperti della bozza mappati, come da handoff).
- Passare da bozza 1 a bozza 2 costa **+118 MiB di VRAM**, cioè i +112,57 MiB del secondo stato di
  rollback più spiccioli. Al tasso di cambio dell'handoff (2,9 GB = +11%) sono ~0,45% di velocità
  sottratti alla cache esperti: **non è questa la causa del −4%**, che è di ciclo (§2).
- Il MTP costa **1,35-1,38% di prefill**, e la lunghezza della bozza **non lo cambia** (329,19
  contro 329,27: 0,02%, sotto il pavimento di rilevabilità dello 0,2%). Nessuna regressione di
  prefill imputabile alla leva.
- Nessun NaN, nessun errore, nessun crash. Entrambi i server chiusi, porta 8100 libera, nessun
  processo residuo.

### Controllo D15 (casi finiti per `length` con testo vuoto)

**Zero casi** in tutte e tre le corse: nessuna richiesta ha esaurito il budget producendo testo
vuoto. **Ma** — ed è un difetto del banco, non della leva — **14 casi su 16** finiscono per `length`
con `content` **vuoto** e tutto il budget consumato in `reasoning_content` (stesso identico
comportamento nel riferimento del mattino: 14 su 16). L'impronta del banco firma
`reasoning_content + content`, quindi resta un oracolo valido; però **questo banco, così com'è,
misura quasi solo ragionamento e quasi mai prosa finale**. Vedi §6.

---

## 5. Perché M3 non è stata eseguita

Il protocollo della cella autorizzava M3 solo se M2 > M1 **e** se le guardie a tre token lo
permettevano. **Nessuna delle due condizioni è soddisfatta**, e la seconda è dirimente.

Una bozza di *n* token si verifica con *n+1* righe. Il percorso veloce è chiuso a **3 righe** in
cinque punti indipendenti del sorgente:

```
ggml/src/ggml-cuda/moe-demand.cuh:232   GGML_ASSERT(ids->ne[1] >= 1 && ids->ne[1] <= 3 && ...)
ggml/src/ggml-cuda/ggml-cuda.cu:2146    GGML_ASSERT(ne2 <= 3 && ne2 <= get_mmvq_mmid_max_batch(...))
src/models/qwen4exp.cpp:1077            GGML_ASSERT(top_k->ne[1] >= 1 && top_k->ne[1] <= 3 && ...)
src/models/qwen4exp.cpp:760, 826        ... && params.ubatch.n_tokens >= 1 && n_tokens <= 3 && n_stream == 1
src/models/qwen4exp.cpp:1239            gather = (... n_tokens >= 1 && n_tokens <= 3) && n_kv >= 4*width
```

I primi tre sono `GGML_ASSERT`: non «ricadono nel percorso costoso», **abortiscono il processo**. Gli
ultimi due sono condizioni che spengono in silenzio il pool veloce dell'indexer e il gather QSA.
Il log di M2 conferma il regime: `sched_reserve: graph nodes = 8595 (with bs=3)`.

**Quindi una bozza di 2 token è già il massimo del percorso veloce**, e l'abbiamo misurata: perde.
Anche l'aritmetica dice di fermarsi — la terza posizione accetterebbe meno della seconda (0,553), e
la soglia di pareggio sale con ogni riga aggiunta.

---

## 6. Difetti

1. **Una sola replica per cella.** Il protocollo chiede tre coppie in screening. Attenuanti: l'A/B
   nullo di P0 misura una variabilità del controllo dello 0,06% e il segnale è −4,05%; e il
   confronto iso-testo a 32k (−4,74%) è indipendente dalle traiettorie. Resta che un intervallo non
   è stato calcolato.
2. **Metà del banco non è iso-testo.** Gli otto casi `corto` divergono fra tutti e tre i bracci
   (§3). La divergenza è plausibilmente numerica, ma **non è stata falsificata** con una seconda
   corsa dello stesso braccio.
3. **Il banco misura ragionamento, non prosa.** 14 casi su 16 consumano i 1024 token di budget
   dentro `reasoning_content` senza mai arrivare alla risposta. Un budget da 1024 con
   `--reasoning on` su prompt di ragionamento non lascia spazio al testo finale. Chi userà questi
   numeri per parlare di «risposta libera» deve saperlo.
4. **Le passate di verifica sono ricavate, non lette.** Il server espone `draft_n` e
   `draft_n_accepted` nei `timings`, ma non il numero di verifiche; l'ho diviso per la lunghezza
   della bozza (13.375/6.690 = 1,9993: la bozza è quasi sempre piena, quindi l'approssimazione è
   buona, ma è un'approssimazione). Il numero esatto sta solo nel log testuale
   (`#calls(b,g,a)` di `common_specu`).
5. **La cella non misura il contesto lungo.** Il profilo `solo_libero` si ferma a 32k. Dalla memoria
   del 9/9 sappiamo che al lungo il MTP va in parità e sul servizio a 262k può **perdere il 31%**:
   nulla qui autorizza a estendere il verdetto oltre 32k.
6. **`QWEN_NGRAM_ROLLBACK` non è stato esercitato.** Esiste nel binario ma è inerte senza n-gram: la
   cella non dice nulla sulla sua correttezza.

---

## 7. Aperture

**Che cosa servirebbe per allungare la bozza oltre tre righe** (in ordine di costo crescente):

1. **Alzare il tetto delle tre righe in modo coordinato.** Non basta toccare una costante: servono
   `moe-demand.cuh` (piano e asserzione), `get_mmvq_mmid_max_batch` per IQ2_S/IQ3_XXS/IQ4_NL su
   Ampere, il pool dell'indexer e il gather QSA di `qwen4exp.cpp`, più gli stati di rollback. È
   esattamente il punto 3 della «sequenza di lavoro verso 50» di Codex, e resta vero.
2. **La collisione con la cache esperti resta.** L'handoff misura che *n* righe pretendono fino a
   10/20/30/40/50/59/69/77 esperti unici per strato: già a 7 righe si sforano i 64 slot. Allungare
   la bozza e tenere 64 slot sono **nemici**; qualunque piano oltre le 3 righe deve dire che cosa fa
   della cache.
3. **Prima di tutto questo, però, serve una bozza più accurata, non più lunga.** Il dato di questa
   cella è che la seconda posizione accetta 0,553 e che la soglia di pareggio è 0,633. Con una testa
   che accettasse ~0,85 a ogni posizione, 2 token pagherebbero e 3 diventerebbero interessanti. Due
   candidati mai provati: la **testa MTP non condivisa** (`mtp-...-Q8_0.gguf`, 4.137 MB, sta in RAM
   e non costa slot — §8 dell'handoff) e una bozza addestrata meglio. **Questa è l'apertura con il
   miglior rapporto valore/costo della cella.**
4. **Misurare la stessa coppia a 131k/250k.** Il verdetto vale fino a 32k. Il profilo
   `solo_prefill` e un profilo lungo direbbero se il +17,3% di M1 sopravvive alla profondità: la
   memoria del 9/9 dice di no, ma su un altro albero.
5. **Falsificare la divergenza dei testi corti**: due corse identiche di M1, confronto delle otto
   impronte `corto`. Se coincidono, la divergenza è della leva (attesa e benigna); se non
   coincidono, il banco a contesto corto **non è un oracolo** e va corretto prima di usarlo per
   giudicare la correttezza.
6. **Non riproporre `--spec-draft-p-min`.** La memoria del 9/9 lo misura: a n=2 e n=3 toglie l'8% e
   il 7% perché taglia bozze che sarebbero state accettate. È rimasto a 0 in entrambe le celle.

---

## 8. Bozza di voce di registro

> **14 settembre 2026 — fase P7, cella 1: lunghezza della bozza MTP.**
>
> *Ipotesi.* Con la testa MTP accesa e gli n-grammi spenti, allungare la bozza da 1 a 2 token
> aumenta il throughput della risposta libera di almeno il 5%, perché ammortizza la riga di verifica
> su più token accettati.
>
> *File toccati.* Nuovi: `docs/porto/banco_p0/preset_M2_p7.json`,
> `docs/porto/banco_p0/preset_M1_p7.json`, `docs/porto/p7_speculazione/P7_BOZZA_MTP_14_SETTEMBRE.md`,
> `docs/porto/p7_speculazione/analizza_p7.py`, `docs/porto/p7_speculazione/log/*`. Nessun sorgente,
> nessuna build, nessun commit. `bin_prod`, lanciatore quotidiano e modello invariati.
>
> *Configurazioni.* Binari `qwen38_clean\build\bin`. Da `preset_A.json` più: `--spec-type draft-mtp`,
> `-md mtp-...-shared-Q8_0.gguf`, `-ngld 99`, `-otd .*ffn_.*_exps.*=CUDA0_Mapped`, `-ctkd/-ctvd q8_0`,
> `--spec-draft-n-min 1`, `--spec-draft-p-min 0`, `LLAMA_MTP_LIGHT=1`,
> `QWEN4EXP_INDEXER_F32_BATCH=1`, `QWEN_MOE_SCALAR_BATCH=2`. Unica differenza fra le celle:
> `--spec-draft-n-max` = 2 (M2) contro 1 (M1). Profilo `solo_libero`, budget 1024, greedy, seed 1234,
> 64 slot, sparse FA spenta.
>
> *Run validi / invalidi.* Due corse valide, una per cella, nell'ordine candidato-prima (D14):
> `20260914_142328_P7_p7_mtp_bozza2_r1` e `20260914_143936_P7_p7_mtp_bozza1_r1`. Nessuna corsa
> invalida, nessun guasto, nessun processo residuo. Riferimento MTP spento riusato:
> `20260914_072049_P0_sper_ibrido_assente_r1` (24,4344 t/s). M3 **non eseguita**.
>
> *Risultato e limite.* M2 = **27,5030 t/s**, M1 = **28,6646 t/s**, riferimento MTP spento =
> **24,4344 t/s**. **M2/M1 = −4,05%** sull'insieme libero e **−4,74%** sul solo sottoinsieme a 32k,
> dove i testi sono identici byte per byte in tutti e tre i bracci. M1/riferimento = **+17,31%**.
> Aritmetica del ciclo: la seconda posizione di bozza costa 22,08 ms (11,1 di testa + 16,6 di terza
> riga di verifica, misurati) e rende 0,535 token, cioè 18,67 ms: **perde 3,4 ms per ciclo**. Soglia
> di pareggio della seconda posizione: **0,633; misurata 0,553**. Limiti: una sola replica per cella;
> gli otto casi a contesto corto non sono iso-testo fra i bracci; il banco si ferma a 32k; 14 casi su
> 16 consumano il budget nel ragionamento senza produrre risposta finale.
>
> *Decisione.* **Leva chiusa a 2 token: non si adotta.** Si tiene `--spec-draft-n-max 1` come
> configurazione della bozza MTP. M3 (3 token) **non va provata**: il percorso veloce è chiuso a 3
> righe di verifica da due `GGML_ASSERT` e da tre condizioni silenziose
> (`moe-demand.cuh:232`, `ggml-cuda.cu:2146`, `qwen4exp.cpp:760/826/1077/1239`), e una bozza di 2
> token è già quel massimo.
>
> *Prossima azione.* Non allungare la bozza: **renderla più accurata**. Provare la testa MTP **non
> condivisa** (`mtp-Qwen3.8-Flash-Next-Q8_0.gguf`, 4.137 MB, in RAM, non costa slot di cache) con
> bozza 1 e bozza 2 sullo stesso banco, giudicandola per **accettazione alla seconda posizione**
> contro la soglia di pareggio 0,633. In parallelo, falsificare la divergenza dei testi corti con
> due corse identiche di M1.

---

## 9. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/banco_p0/preset_M2_p7.json` | preset della cella M2 (bozza 2) |
| `docs/porto/banco_p0/preset_M1_p7.json` | preset della cella M1 (bozza 1) |
| `docs/porto/p7_speculazione/analizza_p7.py` | lettore delle corse: t/s per contesto, ms/token, conteggi di bozza, D15, picchi, impronte |
| `docs/porto/p7_speculazione/log/blocco_M{1,2}_r1.txt` | uscita completa di `avvia_blocco.ps1` (chiave redatta a monte) |
| `docs/porto/p7_speculazione/log/riepilogo_M{1,2}_r1.txt`, `riepilogo_RIF_mtp_spento.txt` | riepiloghi del banco con tutte le impronte |
| `docs/porto/p7_speculazione/log/results_M{1,2}_r1.jsonl` | una riga per richiesta: timings del server, `draft_n`, `draft_n_accepted`, impronte |
| `docs/porto/p7_speculazione/log/analisi_M{1,2}_r1.json`, `analisi_RIF_mtp_spento.json` | uscita di `analizza_p7.py` |
| `docs/porto/p7_speculazione/log/server_estratto_M{1,2}_r1.txt` | righe `n_rs_seq`, `graph nodes`, `print_timing`, `acc per pos`, `common_specu` del log del server |
| `D:\ds4_work\banco_p0_run\20260914_142328_P7_p7_mtp_bozza2_r1` | corsa M2 completa (output, carico, manifest) |
| `D:\ds4_work\banco_p0_run\20260914_143936_P7_p7_mtp_bozza1_r1` | corsa M1 completa |

Comando per rigenerare l'analisi:

```
python docs\porto\p7_speculazione\analizza_p7.py ^
  --corsa D:\ds4_work\banco_p0_run\20260914_143936_P7_p7_mtp_bozza1_r1 ^
  --riferimento D:\ds4_work\banco_p0_run\20260914_072049_P0_sper_ibrido_assente_r1
```
