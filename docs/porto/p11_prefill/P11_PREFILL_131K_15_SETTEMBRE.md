# P11 · il prefill a 131k dai 252 ai 384 t/s — componendo leve che esistevano già — 15 settembre 2026

Cella di **composizione e misura**. Domanda: **il prefill a 131k dai ~250 t/s attuali arriva a 400
componendo leve già esistenti?** Punto operativo dell'utente: prompt freddo di 131.072 token, KV
250k (contesto 262.144), MTP spento, 64 slot, greedy, `-np 1`.

Risposta breve: **no, non con queste leve. Si arriva a 376,4 t/s con le sole leve esistenti (W4) e a
384,4 con una leva nuova (W5): mancano il 3,9-5,9%.** Il guadagno sul riferimento è **+49,2%**
(e **+51,8%** sul caso `L01@ctx131k`, lo stesso con cui era stato misurato il riferimento P10).
I cancelli tengono: **5 aghi su 5**, decode **−0,1%**.

`bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, il lanciatore quotidiano, i modelli,
lo snapshot P0 e l'albero P8 non sono stati toccati. Si è lavorato solo su
`D:\ds4_work\p11_work\` (copia nuova). **Nessun commit.**

---

## 0. In undici righe

1. **Le due patch di Codex del 13/9 erano già nell'albero e già nei binari.** `gdn_tiled.patch` si
   applica al contrario (`git apply --reverse --check` passa): è già dentro. `prefill_staging.patch`
   non si applica né in avanti né al contrario perché P10 cella 2 ha riscritto il codice intorno,
   ma il codice c'è, con la correzione del padding. Entrambe le variabili compaiono per nome dentro
   `ggml-cuda.dll`. **Non è stata necessaria nessuna ricompilazione per le celle W0-W4.**
2. **Sparse FA a teste 256: +17,2%** (252,20 → 295,65). Riproduce il +18,1% del 13/9. Il guadagno
   **è zero nei primi 32k e arriva a −23% nell'ultimo tratto**: cresce con la profondità, come
   previsto.
3. **Batch 4096 a 131k: crolla.** 175,13 t/s, −40,7% rispetto a 2048. La workspace arriva a
   **8942 MiB**, la VRAM libera a 507 MiB e la RAM a 3,34 GB (sotto la soglia R-RAM di 4 GB):
   è paginazione WDDM, non calcolo. Ma **fino a kv≈115k lo stesso batch andava il 19% più veloce**:
   il muro è di memoria, non di aritmetica.
4. **Batch 3072: +12,0%** (295,65 → 331,06), nessun crollo. È il ripiego previsto dal piano ed è la
   scelta giusta: la workspace si ferma a 6819 MiB.
5. **GDN a tile: +1,6%.** Paga −4% nei primi tratti e **zero** negli ultimi due, dove l'attenzione
   domina. Da sola è sotto la regola del 5%.
6. **Staging asincrono degli esperti: +11,9%** (336,23 → 376,35). Trasferisce **45.412 MiB di pesi
   per valutazione** su un secondo stream. **Si spegne da solo negli ultimi 13 blocchi su 44** per
   mancanza di VRAM libera, e in quei blocchi i tempi tornano *identici* a quelli senza staging:
   la prova più pulita che la leva funziona e di quanto.
7. **Il candidato finale W4 = sparse FA + batch 3072 + GDN a tile + staging.** 376,35 t/s sul
   profilo di prefill, **382,85** su `L01@ctx131k` (stesso caso del riferimento P10: 252,16),
   **383,71** sul prefisso degli aghi.
8. **Qualità: 5 aghi su 5** nella risposta finale, alle profondità 5/25/50/75/95%. La domanda
   tecnica resta **inconclusiva** (768 token consumati nel ragionamento) — stesso esito del 13/9,
   e coerente con D15: al budget di screening i casi liberi non sono valutabili.
9. **Decode non regredito: 27,212 e 27,106 t/s** contro 27,245 del riferimento V3 (−0,12% e
   −0,51%; cancello −3%).
10. **Il testo cambia** rispetto al riferimento, e il cambio arriva con la sparse FA. Sulla risposta
    breve del profilo di prefill la risposta finale è **identica** ("pronto") e differisce **una
    parola** del ragionamento. Sui liberi non è giudicabile: al budget 1024 **anche il riferimento**
    finisce il budget dentro il ragionamento e consegna contenuto vuoto.
11. **W5, la leva nuova (ubatch a scaletta, `p11.patch`): 384,40 t/s, +2,14% su W4 — sotto la regola
    del 5%.** Ma fa scendere il picco della workspace da 6819 a **5614 MiB** e la VRAM libera minima
    da 400 a **1597 MiB**: il suo valore non è la velocità, è lo spazio. La scaletta provata spegne
    lo staging nella fascia centrale — va ricalcolata sul fabbisogno dello staging, non solo sul
    tetto della VRAM.

---

## 1. Cancello di partenza e stato dei processi

Guardia eseguita prima di ogni avvio e prima della build: `netstat -ano | findstr LISTENING |
findstr :8100` vuoto e `tasklist | findstr llama-server` vuoto. **Nessun server non mio è stato
trovato**: si è proceduto ogni volta. Un solo `llama-server` alla volta per tutta la cella; lo
script `avvia_blocco.ps1` rifiuta l'avvio se la porta è occupata o se esiste già un `llama-server`,
e non termina mai un processo che non ha creato lui.

**Stato a fine cella, verificato**: nessun `llama-server`, porta 8100 libera, nessuna build in
corso, nessun processo residuo.

Ordine delle corse: W0 → W1 → W2 → W2b → W3 → W4 → cancello aghi → cancello decode → build della
leva W5 → W5. Nessuna misura è partita con una build in corso; l'unica build della giornata è stata
fatta **dopo** tutte le misure di W0-W4 e dei due cancelli.

---

## 2. Che cosa è stato preparato prima di toccare la macchina

| dove | che cosa |
|---|---|
| `D:\ds4_work\p11_work\source` | copia di `D:\ds4_work\p8_work\source` (P8 cumulativa + P10 c2 + P10 c3), 3000 file |
| `D:\ds4_work\p11_work\bin` | copia **congelata** dei binari P8+P10 (`ggml-cuda.dll` `A0D9B694`, `llama.dll` `CA5B5A3C`), usata da W0-W4 |
| `D:\ds4_work\p11_work\manifest_p11.json` | impronte SHA-256 dei dodici file binari e provenienza |
| `banco_p0/banco_p0.py` | due profili nuovi: **`prefill_131k`** = `[PF_131K@ctx131k]` e **`aghi_131k`** = i cinque aghi + `Q_TEC` su `aghi131k` |
| `banco_p0/preset_W*_p11.json` | sette preset (W0, W1, W2, W2b, W3, W4, W5), JSON UTF-8 **senza BOM**, uno per cella eseguita |
| `p11_prefill/p11.patch` | la sola modifica di codice di P11 (`src/llama-context.cpp`), diff contro l'albero P8+P10 |
| `p11_prefill/genera_preset_p11.py`, `deriva_preset_p11.py` | generazione dei preset: ogni cella **aggiunge una sola manopola** al candidato precedente |
| `p11_prefill/tabella_p11.py` | estrae t/s integrale, tempo, VRAM/RAM minime **separando la finestra di prefill da quella di decode**, workspace, impronta |
| `p11_prefill/serie_workspace_p11.py` | serie della workspace e **cadenza dei tratti** di prompt |
| `p11_prefill/aghi_p11.py` | cancello di qualità: conta gli aghi nella **risposta finale**, non nel ragionamento |
| `p11_prefill/copia_log_p11.py` | raccolta dei log ripuliti (chiave API redatta) |

### 2.1 Le patch del 13/9 erano già dentro: verificato, non supposto

```
git apply --reverse --check gdn_tiled.patch        -> passa (la patch e' gia' applicata)
git apply --check          gdn_tiled.patch        -> fallisce ("already exists in working directory")
git apply --check / --reverse --check prefill_staging.patch -> falliscono entrambi
```

Per lo staging il codice **c'è comunque**, e con la correzione del padding descritta da Codex
(`std::vector<uint8_t> padding_zero` in `ggml-backend.cpp`): le due patch non riconciliano perché
**P10 cella 2 ha riscritto `ggml_backend_cuda_graph_compute`** intorno al punto d'innesto
(`ggml_cuda_graph_get_key`, `ggml_cuda_graph_check_compability_cached`). La prova indipendente è
che i nomi delle variabili d'ambiente compaiono dentro le DLL:

| variabile | dove |
|---|---|
| `QWEN_GDN_TILED` | `ggml-cuda.dll` |
| `QWEN_PREFETCH_EXPERTS` | `ggml-cuda.dll`, `ggml-base.dll` |
| `QWEN4EXP_SPARSE_FA` | `ggml-cuda.dll` |

**Conseguenza operativa: W3 e W4 non hanno richiesto nessuna ricompilazione.** Sono due variabili
d'ambiente sullo stesso binario con cui è stato misurato il riferimento — cioè un A/B pulito, senza
il rumore che segue una build (fino al 15%).

---

## 3. Le celle, una manopola alla volta

Profilo `prefill_131k`: una sola richiesta, prefisso `ctx131k` freddo (`cache_prompt=false`,
`cache_n=0`), risposta di 64 token al massimo. Il **prefill t/s è integrale**: `prompt_n / prompt_ms`
del server, cioè tutto il prompt, non il picco dei primi blocchi.

| cella | manopola aggiunta | prefill t/s | tempo prompt | workspace max | VRAM libera min (prefill) | RAM libera min | testo cambiato | esito |
|---|---|---:|---:|---:|---:|---:|---|---|
| **W0** | — (preset V3) | **252,202** | 520,10 s | 4408 MiB | 2246 MiB | 6,90 GB | riferimento `c186b3b753c6` | riferimento centrato |
| **W1** | `QWEN4EXP_SPARSE_FA=1` | **295,651** | 443,66 s | 4408 MiB | 2253 MiB | 6,86 GB | sì, `d77a042a3e08` (**risposta finale identica**) | **+17,23%**, entra |
| **W2** | `-b/-ub 4096` | **175,126** | 749,00 s | **8942 MiB** | **507 MiB** | **3,34 GB** | no, `c186b3b753c6` | **crollo, −40,7%**: esce |
| **W2b** | `-b/-ub 3072` | **331,063** | 396,21 s | 6819 MiB | 519 MiB | 5,89 GB | no (uguale a W1) | **+11,98%** su W1, entra |
| **W3** | `QWEN_GDN_TILED=1` | **336,227** | 390,12 s | 6819 MiB | 393 MiB | 6,00 GB | no (uguale a W1) | **+1,56%**, entra |
| **W4** | `QWEN_PREFETCH_EXPERTS=1` | **376,351** | 348,53 s | 6819 MiB | 400 MiB | 6,17 GB | no (uguale a W1) | **+11,93%**, entra |
| **W5** | ubatch **a scaletta** 6144/4096/3072/2048 (`p11.patch`, binari ricompilati) | **384,401** | 341,23 s | **5614 MiB** | **1597 MiB** | 6,49 GB | sì, `9b331a1bb1a4` | **+2,14%**: sotto la regola del 5%, ma **−17,7% di workspace**. Vedi §7 |

Rispetto a W0: W1 **+17,2%**, W2b **+31,3%**, W3 **+33,3%**, **W4 +49,2%**, W5 **+52,4%**.
Le percentuali nella colonna «esito» sono rispetto alla cella precedente della catena.

Il candidato W4 misurato sugli altri due prompt lunghi, nelle corse dei cancelli:

| prompt | token | prefill t/s | riferimento noto | delta |
|---|---:|---:|---:|---:|
| `PF_131K@ctx131k` | 131.170 | 376,351 | — (W0 = 252,202) | +49,2% |
| `L01@ctx131k` (cancello decode) | 131.248 | **382,849** | **252,157** (P10 V3, stesso caso) | **+51,8%** |
| `Q_AGO_05@aghi131k` (cancello qualità) | 131.313 | **383,708** | — | — |

### 3.1 Dove nasce ogni guadagno: la cadenza dei tratti

Il log del server riserva la workspace ogni 16.384 celle di KV. Il tempo fra due riserve è il costo
di quel tratto di prompt. È la misura che dice **dove** una leva paga.

| tratto di KV | W0 (base) | W1 (+sparse) | W2b (+3072) | W3 (+GDN) | W4 (+staging) |
|---|---:|---:|---:|---:|---:|
| 16k → 32k | 38,0 s | 39,2 s | 36,7 s | 35,2 s | **28,6 s** |
| 32k → 49k | 49,1 | 48,0 | 39,6 | 38,1 | **31,4** |
| 49k → 66k | 55,1 | 50,8 | 41,9 | 40,5 | **33,7** |
| 66k → 82k | 60,7 | 53,2 | 53,1 | 52,2 | **44,1** |
| 82k → 98k | 66,3 | 55,4 | 46,6 | 46,2 | **39,5** |
| 98k → 115k | 72,2 | 58,2 | 48,8 | 48,5 | **41,9** |
| 115k → 131k | 78,1 | 61,2 | 61,5 | 61,5 | 61,5 |
| 131k → 147k | 87,7 | 67,5 | 54,3 | 54,5 | 54,4 |

Tre letture, tutte non ovvie:

- **La sparse FA non fa niente all'inizio e tutto alla fine**: +3,2% nel primo tratto (rumore),
  −7,8% a 66k, −19,4% a 115k, **−23,0% nell'ultimo**. Il 13/9 si diceva «cresce con la profondità»:
  qui si vede la curva. A 250k ci si deve aspettare di più, non uguale.
- **Il GDN a tile fa l'opposto**: −4,1% nel primo tratto, −0,6% a 115k, **zero negli ultimi due**.
  Il kernel è più veloce di 1,7-1,8×, ma la sua quota del tempo crolla man mano che l'attenzione
  cresce. Le due leve sono complementari per costruzione.
- **Lo staging paga uniformemente −13,6% / −18,8%** finché c'è VRAM, e **zero** appena si spegne:
  negli ultimi due tratti W4 fa 61,5 e 54,4 contro 61,5 e 54,5 di W3. Non è una stima: è lo stesso
  binario con la leva che si spegne a metà corsa.

---

## 4. W2: perché il batch 4096 crolla, e dove esattamente

La workspace CUDA riservata cresce **con il prodotto fra token dell'ubatch e celle di KV**. Tarata
sulle nostre misure vale circa

```
workspace(T, K) ≈ cost(T) + 1,1·10⁻⁵ · T · K   [MiB]      (≈ 12 byte per coppia token×cella)
```

cioè le tre maschere `[n_kv, n_batch]` in F32 che `build_layer_attn` costruisce per i 12 strati QSA
(`kq_mask_all`, il `set_rows` del top-k e la somma con `kq_mask`). **La sparse FA non le tocca**:
comprime la maschera dentro il kernel, non nel grafo. Prova: a parità di profondità W0 e W1
riservano gli stessi identici byte (1466,28 / 1530,28 / 2008,28 / … / 4408,28 MiB).

Misure delle riserve, a 131k:

| ubatch | workspace a kv 16k | a kv 98k | a kv 147k | esito |
|---:|---:|---:|---:|---|
| 2048 | 1466 MiB | 3256 | **4408** | regge, VRAM libera ≥ 2246 MiB |
| 3072 | 1749 | 4659 | **6819** | regge, VRAM libera ≥ 393 MiB |
| 4096 | 2433 | 6446 | **8943** | **sfonda a kv ≈ 115k** |

Il crollo di W2 è netto e localizzato: i tratti costavano 27,7 / 38,8 / 41,5 / 44,1 / 46,4 / 49,1 s
— **più veloci di W1 dal 13 al 29%** — e poi **204,7 s e 233,6 s**, quattro volte tanto. Nello
stesso momento la VRAM libera scende a 507 MiB, la RAM di sistema a 3,34 GB e la potenza della GPU
cala a 84 W mediani (contro 133-142 delle altre celle): la GPU aspetta il bus, non calcola. È la
stessa firma del tentativo a 8192 di Codex (workspace 7451 MiB, blocco da 16,8 → 51,2 s).

**Fino al muro il batch grande vinceva molto**: i primi 114.688 token sono stati letti in 247,6 s,
cioè **463 t/s cumulativi**. Il tetto dei 400 non è irraggiungibile per aritmetica — è la VRAM che
decide dove ci si può stare.

---

## 5. W4: lo staging, e il fatto che si spegne da solo

Il log dice esattamente che cosa succede, valutazione per valutazione:

```
qwen_prefetch: staged 141 tensors, 45412 MiB; ring released        ×31
qwen_prefetch: skipped, insufficient free VRAM for 900 MiB plus reserve   ×13
```

Sono **45,4 GiB di pesi degli esperti per ogni blocco di prompt** (il modello tiene 46.872 MiB di
esperti in `CUDA_Host`): in prefill ogni blocco tocca praticamente tutti i 512 esperti di ogni
strato, quindi la massa passa intera sul bus a ogni blocco. Lo staging la anticipa su un secondo
stream mentre la GPU calcola il blocco precedente, e vale **−13,6% / −18,8% per tratto**.

Il codice pretende `512 MiB` di riserva più due buffer da ~450 MiB, cioè **~1,4 GiB di VRAM
libera**. Con batch 3072 la workspace in profondità arriva a 6819 MiB e la VRAM libera scende sotto
quella soglia: dal blocco 32 in poi lo staging **si disattiva da solo**, senza errori e senza
degrado — semplicemente torna il comportamento di W3. Questo è anche il motivo per cui W4 e W3
hanno gli ultimi due tratti identici al decimo di secondo.

**C'è quindi un conflitto misurato fra due leve**: il batch grande mangia la VRAM che serve allo
staging. È esattamente il conflitto che la cella W5 prova a sciogliere (§7).

---

## 6. I cancelli

### 6.1 Qualità: cinque aghi su cinque

Profilo `aghi_131k` sul candidato W4, prefisso `aghi131k` (131.208 token di riempimento, cinque
fatti piantati al 5/25/50/75/95% dei caratteri), budget 768 token, greedy.

| caso | profondità | stringa attesa | nella risposta finale | token generati | fine |
|---|---:|---|---|---:|---|
| `Q_AGO_05` | 5% | `MANDORLA-417` | **sì** | 104 | stop |
| `Q_AGO_25` | 25% | `VIOLA-CENERE` | **sì** | 92 | stop |
| `Q_AGO_50` | 50% | `Malinverni` | **sì** | 129 | stop |
| `Q_AGO_75` | 75% | `ZR-8842` | **sì** | 86 | stop |
| `Q_AGO_95` | 95% | `TRAMONTANA` | **sì** | 69 | stop |
| `Q_TEC` | — | `--moe-expert-cache` + `--moe-expert-cache-inserts` | **no**: entrambi i termini compaiono nel **ragionamento**, ma i 768 token finiscono lì dentro e la risposta finale resta vuota | 768 | length |

**5/5 sugli aghi: cancello superato**, come il riferimento del 13/9. `Q_TEC` non è una bocciatura:
è **inconclusiva** per budget, e lo era anche il 13/9 nella prova di Codex («la domanda tecnica ha
consumato 768 token nel ragionamento senza risposta finale: è inconclusiva»). Coerente con D15 del
14/9. Per farne un cancello vero serve budget 3072 o `stop`, cioè il profilo di conferma.

### 6.2 Decode: non regredito

Profilo `lungo_131k` sul candidato W4, contro il riferimento V3 (P10 cella 3, media di due
repliche: **27,245 t/s**; cancello −3%, cioè 26,43).

| caso | decode t/s | contro 27,245 |
|---|---:|---:|
| `L01@ctx131k` (dopo prefill freddo) | **27,212** | **−0,12%** |
| `L02@ctx131k` (prompt in cache) | **27,106** | **−0,51%** |

**Cancello superato.** Notevole perché W4 tiene acceso `QWEN_PREFETCH_EXPERTS=1`, che disattiva i
grafi CUDA dei grandi `MUL_MAT_ID`: nel decode quei grafi non esistono (2-3 righe di verifica),
quindi la leva è inerte lì, e la misura lo conferma invece di assumerlo.

### 6.3 Il testo cambia — che cosa si può dire e che cosa no

| corsa | impronta `PF_131K` | lettura |
|---|---|---|
| W0 | `c186b3b753c6` | riferimento |
| W1, W2b, W3, W4 | `d77a042a3e08` | **la risposta finale è identica** (`pronto`); differisce **una parola** del ragionamento («request» invece di «task») |
| W2 | `c186b3b753c6` | torna uguale a W0 |

È il comportamento già visto il 13/9: differenze numeriche minime che ogni tanto ribaltano un
pareggio fra due logit. Il fatto che W2 (batch 4096 + sparse) ricada sull'impronta di W0 dice che
non c'è una direzione sistematica.

Sui **casi liberi** a 131k il testo cambia (`L01` `b8fe0a4dfd68` contro `99ba1423cf12` del
riferimento V3), **ma la rubrica non è applicabile**: al budget di screening (1024 token) sia il
candidato sia il riferimento consegnano **contenuto finale vuoto** (2901 e 4530 caratteri di solo
ragionamento nel candidato, 2920 e 4411 nel riferimento). È D15, non una regressione. La qualità
dei liberi a 131k va misurata in conferma, e non è stata misurata qui.

---

## 7. W5 — il batch in funzione del contesto

W2 ha dimostrato che il batch grande **non è lento: è troppo grande per la VRAM in profondità**, e
W4 che lo staging **si spegne quando la workspace gli mangia lo spazio**. La conclusione naturale è
il punto 1 della «Sequenza di lavoro verso 50» di Codex: *batch più grandi all'inizio, più piccoli
in profondità*. Era l'unica cella che richiedeva codice nuovo.

### 7.1 Perché serviva una patch, e quale

Due ostacoli, entrambi in `src/llama-context.cpp`:

1. Il server manda blocchi da `n_batch` e `llama_decode` li spezza in ubatch da `cparams.n_ubatch`:
   **un solo numero per tutta la corsa**.
2. `sched_reserve` ha un **tetto monotono** (`reserve_tokens = max(reserve_tokens,
   workspace_tokens)`): una volta riservata per 6144 token, la workspace **non torna più
   indietro**, quindi rimpicciolire l'ubatch non libererebbe niente.

`p11.patch` (unico file toccato, tre punti) introduce una **scaletta**:

```
QWEN_PREFILL_UBATCH_DEEP="49152:4096,98304:3072,131072:2048"     con  -b 6144 -ub 6144
```

= 6144 token per ubatch fino a 49k di KV, poi 4096, poi 3072, poi 2048. La stessa funzione decide
sia la riserva sia lo split del batch (altrimenti si riserverebbe per un ubatch e se ne eseguirebbe
un altro), e sopra la soglia il tetto monotono viene scavalcato di proposito. **Spenta di default**:
senza la variabile il binario si comporta come prima. Non tocca il decode, che gira a 1-3 token.

### 7.2 Che cosa è successo

| cella | prefill t/s | tempo | workspace max | VRAM libera min | RAM min | staging attivo |
|---|---:|---:|---:|---:|---:|---|
| W4 (batch fisso 3072) | 376,351 | 348,53 s | 6819 MiB | 400 MiB | 6,17 GB | 31 blocchi su 44, **spento negli ultimi 13** |
| **W5 (scaletta)** | **384,401** | **341,23 s** | **5614 MiB** | **1597 MiB** | 6,49 GB | 30 blocchi, spento **in mezzo**, **riacceso alla fine** |

La serie delle riserve mostra la leva che fa esattamente quello per cui è stata scritta — la
workspace **scende** invece di crescere, tre volte:

```
t=196,6s  ubatch 6144  kv 16384   ws 3798,84 MiB
t=218,0s  ubatch 6144  kv 32768   ws 4260,84 MiB     tratto 21,3 s   (W4 a 3072: 28,6 s)
t=251,9s  ubatch 4096  kv 49152   ws 3758,56 MiB  <- scende
t=278,9s  ubatch 4096  kv 65536   ws 4526,56 MiB     tratto 27,0 s   (W4: 33,7 s)
t=322,0s  ubatch 4096  kv 81920   ws 5614,56 MiB     tratto 43,1 s   (W4: 44,1 s)
t=375,8s  ubatch 3072  kv 98304   ws 4659,42 MiB  <- scende
t=408,2s  ubatch 3072  kv 114688  ws 5571,42 MiB
t=467,3s  ubatch 2048  kv 131072  ws 4024,28 MiB  <- scende
t=515,9s  ubatch 2048  kv 147456  ws 4408,28 MiB     tratto 48,6 s   (W4: 54,4 s)
```

### 7.3 Verdetto sulla cella W5

**In velocità la leva non paga: +2,14% su W4, sotto la regola del 5%.** Il primo tratto vola
(−25,5%: 21,3 s contro 28,6), ma il guadagno si consuma nella fascia centrale, dove l'ubatch 4096
porta la workspace a 5614 MiB e **fa spegnere lo staging per dodici blocchi** — la scaletta è stata
calcolata sul tetto della VRAM, non sul fabbisogno dello staging, ed è un errore di progetto della
scaletta, non della leva.

**In memoria invece paga molto**, e questo è il risultato solido della cella: **picco della
workspace da 6819 a 5614 MiB (−17,7%) e VRAM libera minima da 400 a 1597 MiB (quattro volte
tanto)**, a parità o meglio di velocità. È lo spazio che serve a qualunque leva successiva, a
partire dallo staging tenuto acceso fino in fondo (qui **si riaccende** negli ultimi blocchi a 2048:
l'ultimo `staged` è a 8:56, dentro la coda del prompt).

**Limite grosso, dichiarato**: W5 gira su **binari ricompilati** (`p11_work\build\bin`, build delle
21:10-21:21), mentre W0-W4 girano sulla copia congelata. Non è un A/B a binario invariato e **non
è stata fatta la corsa di controllo** (stessi binari, variabile non impostata). Il +2,14% è quindi
dentro l'incertezza di una misura fatta dopo una build (regola dell'8/9: fino al 15%), mentre i
numeri di memoria — che sono conteggi di byte riservati, non tempi — restano validi.

---

## 8. Verdetto contro i 400

**Non ci si arriva. Il meglio misurato a 131k è 384,4 t/s (W5) e 376,4-383,7 t/s (W4, tre prompt
diversi): manca il 3,9-6,3%.** Partendo da 252,2, il cammino è +49,2% (W4) / +52,4% (W5) sul
profilo di prefill e **+51,8%** sul caso `L01@ctx131k`, che è lo stesso caso con cui era stato
misurato il riferimento di P10.

| | t/s | contro 400 |
|---|---:|---:|
| riferimento (P10 V3, 15/9 pomeriggio) | 252,2 | −37,0% |
| **W4** (nessuna ricompilazione) | **376,4** | **−5,9%** |
| W4 su `L01@ctx131k` | 382,8 | −4,3% |
| W4 su `aghi131k` | 383,7 | −4,1% |
| **W5** (con `p11.patch`) | **384,4** | **−3,9%** |
| per confronto: Codex 13/9, MTP acceso, prompt suo | 357,6 | −10,6% |

Che cosa manca, in ordine di quanto vale:

1. **La maschera densa `[n_kv, n_batch]` in F32.** È lei che fissa il tetto del batch: 12 byte per
   ogni coppia token×cella, cioè 3,3 GiB a 131k con ubatch 2048 e 6,6 con 4096. Se con la sparse FA
   accesa il grafo passasse gli **indici** invece di materializzare tre maschere (la strada sparsa
   già li ricostruisce dentro il kernel), il batch grande entrerebbe in VRAM **e** lascerebbe spazio
   allo staging. Vale, a occhio, il tratto che W2 ha già dimostrato: **463 t/s cumulativi fino a
   115k**. È il singolo intervento con il rapporto valore/rischio migliore, ed è un intervento di
   grafo, non di kernel.
2. **Lo staging che si spegne.** In W4 negli ultimi 13 blocchi su 44, in W5 in dodici blocchi
   centrali. Tenerlo acceso ovunque vale circa il 3-4% del prefill totale. Due strade: il punto 1
   (è la workspace che gli mangia la VRAM), oppure un **ring più piccolo** — oggi chiede due buffer
   da ~450 MiB più 512 MiB di riserva, e con buffer da 256 e riserva 256 resterebbe acceso fino in
   fondo, al prezzo di meno sovrapposizione per blocco. **La scaletta di W5 va poi ricalcolata sul
   fabbisogno dello staging** e non solo sul tetto della VRAM: è l'errore che le è costato il
   guadagno (§7.3).
3. **Il tratto 66k → 82k costa sistematicamente troppo** (44,1 s contro i ~36 che la curva
   prevede) in **tutte** le celle con batch 3072, e non nelle celle a 2048. Non è stato indagato:
   è un'anomalia riproducibile che vale ~8 s su 348, cioè il 2,3%.
4. **Il 250k non è stato misurato.** Il guadagno della sparse cresce con la profondità (da zero a
   −23% fra 32k e 147k): a 250k il quadro cambia, in meglio per la sparse e in peggio per la
   workspace. Il punto operativo dichiarato dall'utente è KV 250k con prompt ~131k, ed è quello che
   si è misurato; un prompt *davvero* da 250k è un'altra misura.

**Quello che non manca**: non manca aritmetica. Il prefill a batch 4096 ha letto i primi 115k token
a 463 t/s cumulativi sulla stessa macchina. Il tetto dei 400 a 131k è un problema di **occupazione
di VRAM**, non di velocità dei kernel.

---

## 9. Difetti di questa cella

1. **Una sola replica per cella.** Il rumore del banco fra repliche identiche è 0,06-0,2% sul
   prefill (regola del 13/9), quindi i salti da +12% in su sono fuori discussione, ma **il +1,56%
   del GDN a tile non è distinguibile da un rumore di misura più grande del solito** senza una
   seconda replica. Non è stata fatta per tempo.
2. **La cadenza dei tratti non è una misura del banco**: viene dai tempi del log del server fra due
   riserve di workspace. È robusta (le due corse di W4, su prompt diversi, danno 28,6/31,4/33,6-33,7
   /43,3-44,1/38,4-39,5/40,7-41,9) ma non ha l'accuratezza dei `timings` del server.
3. **Il GDN a tile non ha una riga di diagnostica.** Che il ramo sia stato preso si deduce dai
   vincoli (SM86, S_v=128, H=48, una sequenza, ubatch fra 16 e 8192, K=1) e dal tempo, non da un
   log. Una riga come quella della sparse FA costerebbe niente e toglierebbe l'ambiguità.
4. **`Q_TEC` non misura niente** al budget di screening: è il terzo giorno che consuma il budget nel
   ragionamento. O sale a 3072, o esce dal profilo.
5. **Il confronto W5 contro W4 non è a binario invariato** (§7): W5 gira su binari ricompilati.
   Il controllo usato è la cadenza dei primi tratti, non una corsa di controllo dedicata.
6. **Il modello di costo della workspace è tarato su tre punti** (2048, 3072, 4096 alle profondità
   misurate) più il dato di Codex a 8192. Prevede entro il 2-3% nella zona misurata; fuori non è
   stato verificato.
7. **Non è stato misurato il ramo «batch 2048 + staging»**, cioè la configurazione esatta con cui
   Codex ha ottenuto 357,61 t/s il 13/9. Il preset era pronto e non è stato eseguito per tempo:
   avrebbe separato in modo netto quanto vale il batch e quanto lo staging, invece di dedurlo dai
   tratti. È la prima corsa da fare se si vuole chiudere quel conto.
8. **`p11.patch` contiene quattro righe di rumore**: due `#include` risultano modificati perché il
   file originale ha terminatori di riga misti (CRLF e LF) e l'editor ha uniformato quelle righe a
   CRLF. Il contenuto non cambia.

---

## 10. Aperture

- **A1 — la maschera densa (punto 1 del verdetto).** Passare `top_k` al backend invece delle tre
  maschere F32 quando la sparse è accesa. È la leva che sblocca sia il batch sia lo staging.
- **A2 — ring dello staging più piccolo** (256 MiB × 2 e riserva 256): tiene la leva accesa fino in
  fondo. Misurabile in una corsa.
- **A3 — l'anomalia del tratto 66k→82k** con batch 3072.
- **A4 — sparse FA a 250k**, che è il punto operativo dichiarato e dove la leva vale di più.
- **A5 — promozione in produzione.** Il candidato W4 è quattro variabili d'ambiente e un `-b/-ub`
  sui binari già presenti in `build\bin`: non richiede ricompilazioni. La decisione di toccare il
  lanciatore quotidiano resta dell'utente (il 13/9 era già stata rimandata per la sola sparse FA).
- **A6 — il decode.** P11 non l'ha toccato: resta a 27,2 t/s, e il fronte dei 50 è quello di P7/P10.

---

## 11. Bozza di voce di registro

**Data e fase.** 15 settembre 2026, sera. Fase P11 — prefill a 131k verso i 400 t/s, componendo
leve esistenti. Cella di composizione e misura, non di ricerca.

**Ipotesi.** I 250 t/s di prefill a 131k sono lontani dai 400 perché le leve misurate il 13/9
(sparse FA, batch grande, GDN a tile, staging degli esperti) non erano mai state composte sullo
stesso binario al punto operativo dell'utente. Composte, ci si aspettava ~357 (il valore che Codex
aveva misurato il 13/9 con MTP acceso) e si voleva sapere quanto manca a 400.

**File toccati.** `docs/porto/banco_p0/banco_p0.py` (due profili nuovi: `prefill_131k`,
`aghi_131k`); `docs/porto/banco_p0/preset_W{0,1,2,2b,3,4,4b,5}_p11.json`;
`docs/porto/p11_prefill/` (documento, strumenti, log, `p11.patch`);
`D:\ds4_work\p11_work\` (copia nuova dei sorgenti, binari congelati, build).
**Non toccati e verificati**: `bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`,
lanciatore quotidiano, modelli, snapshot P0, albero P8.

**Configurazioni.** Base = `preset_V3_p10.json` (P8 cumulativa + P10 c2 + P10 c3, MTP spento, 64
slot, KV 262144, `-b/-ub 2048`, greedy seed 1234, ragionamento acceso). Manopole aggiunte una alla
volta: `QWEN4EXP_SPARSE_FA=1`, `-b/-ub` 4096 poi 3072, `QWEN_GDN_TILED=1`,
`QWEN_PREFETCH_EXPERTS=1`, e infine la leva nuova `QWEN_PREFILL_UBATCH_DEEP`.

**Run validi/invalidi.** Nove corse, tutte valide (`guasto: nessuno`): W0, W1, W2, W2b, W3, W4,
cancello aghi, cancello decode, W5. W2 è valida **come misura del crollo**, non come candidato.
Nessuna corsa interrotta, nessun server residuo.

**Risultato e limite.** Prefill a 131k **da 252,20 a 376,35 t/s** sul profilo di prefill
(**+49,2%**), **da 252,16 a 382,85** sul caso `L01@ctx131k` (**+51,8%**, stesso caso del
riferimento P10), **384,40 con la leva nuova W5**. **I 400 non sono raggiunti**: manca il 3,9-5,9%.
Limite: una replica per cella; il contributo del GDN a tile (+1,6%) è al limite del rumore; W5 gira
su binari ricompilati e senza corsa di controllo; la qualità dei liberi non è giudicabile al budget
di screening; il 250k non è stato misurato.

**Decisione.** Il candidato **W4** (sparse FA + batch/ubatch 3072 + GDN a tile + staging degli
esperti, binari P8+P10 invariati) **si adotta come configurazione di prefill lungo**: supera i due
cancelli (5/5 aghi, decode −0,1%) e non richiede ricompilazioni. **Il batch 4096 si chiude**: a
131k crolla del 40,7% per paginazione WDDM. **La leva W5 si tiene ma non si adotta**: +2,14% è sotto
la soglia del 5%, e il suo valore (−17,7% di workspace, +1,2 GiB di VRAM libera) si riscuote solo
insieme all'apertura A1. La promozione nel lanciatore quotidiano resta una decisione dell'utente.

**Regressioni.** Nessuna misurata: decode −0,12% e −0,51% (dentro il rumore, cancello −3%), aghi
5/5, risposta finale del profilo di prefill identica. Il testo del ragionamento cambia (una parola
sul caso breve, interamente sui liberi): atteso dalla sparse FA, già documentato il 13/9.

**Stato dei processi.** Nessun `llama-server`, porta 8100 libera, nessuna build in corso, nessun
processo residuo.

**Prossima azione.** A1: togliere la materializzazione delle tre maschere F32 `[n_kv, n_batch]`
quando la sparse FA è accesa. È il tetto vero del batch e, di conseguenza, dello staging: senza di
lei il prefill a 131k ha già dimostrato **463 t/s cumulativi** sui primi 115k token.

---

## 12. Come rifare queste misure

```powershell
# una cella (un processo nuovo di llama-server, la sequenza, poi chiusura)
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0
.\avvia_blocco.ps1 -Preset preset_W4_p11.json -Profilo prefill_131k -Replica 1

# cancelli
.\avvia_blocco.ps1 -Preset preset_W4_p11.json -Profilo aghi_131k   -Replica 1
.\avvia_blocco.ps1 -Preset preset_W4_p11.json -Profilo lungo_131k  -Replica 1
```

```
# lettura dei risultati
cd ..\p11_prefill
python tabella_p11.py          <cartella_corsa>
python serie_workspace_p11.py  log\p11_W4_server_estratto.txt
python aghi_p11.py             <cartella_corsa_aghi>
python copia_log_p11.py        W4=<nome_cartella_corsa>
```

Corse di questa cella, in `D:\ds4_work\banco_p0_run\`:

| cella | cartella |
|---|---|
| W0 | `20260915_193053_P11_p11_w0_riferimento_v3_r1` |
| W1 | `20260915_194334_P11_p11_w1_sparse_fa_r1` |
| W2 | `20260915_200047_P11_p11_w2_sparse_fa_batch4096_r1` |
| W2b | `20260915_201731_P11_p11_w2b_sparse_fa_batch3072_r1` |
| W3 | `20260915_202904_P11_p11_w3_gdn_tile_r1` |
| W4 | `20260915_203955_P11_p11_w4_gdn_tile_staging_r1` |
| cancello aghi | `20260915_205005_P11_p11_w4_gdn_tile_staging_r1` |
| cancello decode | `20260915_210051_P11_p11_w4_gdn_tile_staging_r1` |
| W5 | `20260915_212439_P11_p11_w5_ubatch_a_scaletta_r1` |
