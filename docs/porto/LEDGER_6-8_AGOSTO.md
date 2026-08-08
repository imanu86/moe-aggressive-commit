# LEDGER RICOSTRUITO — 6, 7 e 8 agosto (97 run)

`LEDGER_RUN.tsv` si era fermato al **5 agosto**. Questo documento ricostruisce i due
giorni successivi dai `<tag>.server.log` su disco, uniti alle variabili d'ambiente
prese dagli script `braccio_*.ps1` che li hanno prodotti. Dati grezzi in
`D:\ds4_work\llama_run\RICOSTRUITO.csv`.

La ricostruzione ha fatto emergere **tre cose che non erano note** — sono in fondo,
sezione VERDETTI NUOVI.

---

## 0. LE TRE LINEE DI FRATTURA — nessun confronto le attraversa

Prima delle tabelle, le tre discontinuità che rendono NON confrontabili run su lati
opposti. Erano tutte silenziose.

**(a) Il banco è cambiato alle 05:06.** Fino a `braccio_conf` (04:56) si postava su
`/completion` con prompt grezzo: **il chat template non veniva applicato** e il modello
derivava fuori bersaglio. Da `braccio_ovlspec` (05:06) in poi si usa
`/v1/chat/completions`. **22 run sono sul banco rotto**: `blk1cmp_*`, `b1_*`, `L1_*`,
`nmax*`, `conf00`. I loro p1 e colpi non valgono; i confronti relativi interni sì.

**(b) Gli slot sono passati da 380 a 320 alle 07:00**, senza motivo registrato.
`braccio_blk1/blk1_extra/L1/nmax/conf/ovlspec` girano a **380**; tutto il resto a **320**.
Lo storico dice che 380 slot davano 9,26 ([[working-set-curva-cache-vram]]).

**(c) La sovrapposizione era SPENTA in tutto il filone prefetch.** Gli arm
`oracolo`, `nodomanda`, `tetto`, `sfasate`, `oracolo2`, `diff`, `cura`, `kvring`
girano con `K=0` e `BATCH_MAX=1`, cioè **senza overlap**. Il loro metro è 8,4-8,6,
non 10. **Il prefetch non è mai stato misurato nella configurazione di produzione.**

E una quarta, che non è una frattura ma un cestino: **`max_tokens=300` produce
contenuto VUOTO** (il blocco di ragionamento consuma tutti i token). Le run con
`car=0` e sha `F01A374E` non hanno generato niente: `nd_N1`, `nd_N2`, `o2_P3`,
`kv_G`, `kv_A`, `kv_B`. **Il 10,44 di `nd_N2` non è una SOTA: è una pagina bianca.**

---

## 1. IL PAVIMENTO DI RUMORE — misurato oggi per la prima volta

Due run **identiche**, temperatura 0, stesso binario (`st_S1` / `st_S2`):

| | t/s | p1 | colpi | caratteri | sha |
|---|---:|---:|---:|---:|---|
| S1 | 9,91 | 0,840 | 39,7% | 2.681 | `0CDF8330` |
| S2 | 9,55 | 0,756 | 43,9% | 1.552 | `DA070C9A` |

**±4% sul t/s, ±8 punti di p1, ±4 punti di colpi, a configurazione invariata.**
Tutti i confronti a n=1 di questi due giorni vanno riletti dentro questo pavimento.

Ma il pavimento **non è uniforme** — e questo è un dato, non un fastidio:

| regime | ripetizioni | dispersione |
|---|---|---:|
| `b1_blk1_R3/R4/R5` (bozza rotta) | 4,82 / 4,80 / 4,83 | **0,6%** |
| `sf_S_*` (prefetch on, spec off) | 5,72 / 5,70 / 5,74 / 5,71 | **0,7%** |
| `cu_D0/D1/D2` (prefetch on) | 5,47 / 5,53 / 5,50 | **1,1%** |
| `rg_K4_R1/R2/R3` | 8,83 / 8,93 / 8,86 | **1,1%** |
| `rg_K2_R1/R2/R3` | 9,66 / 9,52 / 9,84 | 3,4% |
| `k_K3_R1/R2` | 9,84 / 10,19 | 3,6% |
| `st_S1/S2` | 9,91 / 9,55 | 3,8% |
| `nmax1_R1/R2` (banco rotto) | 7,89 / 7,36 | 7,2% |

---

## 2. TUTTE LE RUN, con la configurazione completa

Colonne: `ctx` contesto; `slot` slot cache; `W` finestra prefetch; `K` taglio overlap;
`BM` `BATCH_MAX`; `CU` cura; `RG` anello KV; `t` thread; `sp` speculazione;
`nm` `n-max`. Vuoto = non impostato dallo script.

### 2.1 BANCO ROTTO (`/completion` senza template) — 380 slot, overlap non impostato

| tag | ora | t/s | p1 | colpi | config | nota |
|---|---|---:|---:|---:|---|---|
| `b1_blk3_R1/R2/R3` | 03:41-03:52 | 7,44 / 7,50 / 7,72 | 0,77 / 0,79 / 0,86 | 24,6 / 23,8 / 19,7 | bozza 3 blocchi, t=8 | riferimento del confronto |
| `b1_blk1_R3/R4/R5` | 03:58-04:10 | 4,82 / 4,80 / 4,83 | 0,14 / 0,16 / 0,12 | 11,0 / 10,7 / 14,8 | bozza **blk1 troncata** | **VOID**: `target_layers` troncata → due variabili |
| `L1_R1/R2/R3` | 04:24-04:34 | 5,30 / 5,10 / 5,81 | 0,28 / 0,28 / 0,40 | 16,6 / 10,8 / 19,7 | bozza **L1** ricostruita | p1 0,28-0,40 contro 0,77-0,86: il taglio a 1 blocco costa davvero |
| `nmax1_R1/R2` | 04:39, 04:53 | 7,89 / 7,36 | 0,873 / 0,756 | 19,8 / 23,7 | n-max 1 | banco rotto |
| `nmax3_R1` | 04:43 | 8,89 | 0,890 | 22,4 | n-max 3 | banco rotto |
| `nmax5_R1` | 04:47 | 7,89 | 0,840 | 30,6 | n-max 5 | banco rotto |
| `conf00_R1` | 04:56 | — | | | `--spec-draft-conf-min` | nessuna metrica |

### 2.2 BANCO CHAT — la spazzata overlap × speculazione (380 slot fino a `ch_*`, poi 320)

| tag | ora | t/s | p1 | colpi | config |
|---|---|---:|---:|---:|---|
| `os_A_ovl_nospec` | 05:06 | 8,92 | — | 34,6 | overlap on, spec off, 380 slot |
| `os_A0_noovl` | 05:12 | 8,58 | — | 34,7 | overlap off, spec off |
| `os_B_spec_noovl` | 05:16 | 4,67 | 0,421 | 38,3 | spec on, overlap off, n-max 3 |
| `ch_A_ovl_nospec` | 05:21 | 9,47 | — | 51,0 | overlap on, spec off |
| `ch_A0_noovl` | 05:24 | 8,87 | — | 39,2 | overlap off, spec off |
| `ch_B_spec_noovl` | 05:29 | 5,87 | 0,575 | 40,7 | spec on, overlap off |
| `o2_S1_on` | 05:42 | **9,88** | 0,813 | 43,2 | overlap ON + spec n-max 1 |
| `o2_S1_off` | 05:55 | 8,12 | 0,833 | 20,7 | overlap OFF + spec n-max 1 |
| `o2_M_ovl` | 05:51 | 9,29 | — | 45,7 | metro: overlap, no spec |
| `o2_S5_on` | 05:47 | 6,00 | 0,605 | 34,8 | n-max 5, overlap on |
| `o2_S5_off` | 06:00 | 6,28 | 0,629 | 41,3 | n-max 5, overlap off |

**È qui che nasce la SOTA di stamattina**: 9,88 con entrambi, 9,29 solo overlap,
8,12 solo testa. La testa da sola **perde**; insieme vincono.

### 2.3 La spazzata K — 320 slot, spec n-max 1, BATCH_MAX 2

| tag | ora | t/s | p1 | colpi | K | thread |
|---|---|---:|---:|---:|---:|---:|
| `k_S1_R2` | 06:11 | 10,07 | 0,871 | 39,2 | **2** | 7 |
| `k_K3_R1` | 06:07 | 9,84 | 0,843 | 50,3 | **3** | 7 |
| `k_K3_R2` | 06:28 | **10,19** | 0,886 | 49,0 | **3** | 7 |
| `k_K3t8_R1` | 06:18 | 9,54 | 0,801 | 56,2 | 3 | 8 |
| `k_K3t8_R2` | 06:32 | 9,99 | 0,856 | 50,1 | 3 | 8 |
| `k_K4_R1` | 06:24 | 8,80 | 0,850 | 69,9 | 4 | 7 |
| `k_M_R2` | 06:14 | 9,28 | — | 45,6 | 2, no spec | 7 |

> **⚠ LA SOTA 10,19 ERA A K=3, NON K=2.** Tutti i bracci di oggi pomeriggio
> (`tutto`, `regola`, `stride`, `determ`) girano a **K=2**. La configurazione che ha
> prodotto il numero di riferimento non è quella che stiamo usando come base.

### 2.4 Il filone prefetch — **overlap SPENTO** (K=0, BM=1), 320 slot

| tag | ora | t/s | colpi | in ritardo | config |
|---|---|---:|---:|---:|---|
| `or_0_registra` | 07:00 | 8,43 | 33,0 | 0,0 | W=0, registra la pista |
| `or_1_metro` | 07:04 | 8,49 | 33,0 | 0,0 | W=0 metro |
| `or_2_predit` | 07:09 | 5,59 | 2,3 | **58,7** | W=2 predittore |
| `or_3_oracolo` | 07:14 | 5,75 | 1,3 | **32,0** | W=2 oracolo (piano esatto) |
| `tt_T1/T2` | 07:43-07:48 | 5,74 / 5,72 | 1,5 / 0,8 | 31,9 / 32,4 | tetto transiti 40 / 160 |
| `sf_S_m1/p1/m2/p2` | 07:57-08:17 | 5,72 / 5,70 / 5,74 / 5,71 | 1,4 / 1,2 / 1,5 / 1,1 | 35,2 / 30,0 / 40,4 / 29,0 | fasi sfasate |
| `o2_P0/P1` | 08:27-08:33 | 8,55 / 8,57 | 33,7 / 33,8 | 0,0 | metro |
| `o2_P2_oracolo` | 08:37 | 6,08 | 1,7 | 36,4 | oracolo |
| `o2_P3_nodomanda` | 08:41 | 9,82 | 2,9 | 9,2 | **contenuto VUOTO** |
| `diff` | 09:04 | 6,13 | 3,7 | **97,8** | diagnostica |
| `cu_M_W0` / `cu_M2_W0` | 09:59, 12:52 | 8,57 / 8,54 | 33,7 / 33,7 | 0,0 | metro, bit-identico |
| `cu_C0_W2_off` / `cu_D0_W2_off` | 10:07, 12:57 | 5,58 / 5,47 | 2,3 / 3,4 | 58,7 / 57,7 | prefetch on, cura OFF |
| `cu_D1_W2_cura1` | 13:02 | 5,53 | **28,9** | 50,3 | **cura 1** |
| `cu_D2_W2_cura2` | 13:07 | 5,50 | **30,2** | 51,5 | **cura 2** |

> **La cura FUNZIONA sul suo bersaglio e non paga**: i colpi salgono da 2,3-3,4% a
> **28,9-30,2%**, cioè ~10×, e il t/s non si muove (5,47 → 5,53). Il prefetch resta
> a −36% contro il proprio metro (8,54). Ma **tutto questo con l'overlap spento**.

### 2.5 K frazionario — 320 slot, BM=2, spec n-max 1

| tag | ora | t/s | p1 | colpi | K |
|---|---|---:|---:|---:|---:|
| `kf_C_200` | 11:11 | 10,16 | 0,865 | 38,7 | 2,00 |
| `kf_A_233` | 11:01 | 10,14 | 0,860 | 42,6 | 2,33 |
| `kf_B_250` | 11:07 | **10,41** | 0,888 | 42,4 | 2,50 |

Tre valori dentro il 2,7%: **indistinguibili nel pavimento di rumore**. Il verdetto
"K frazionario falsificato" regge, ma va detto così: *non separabile*, non *peggiore*.

### 2.6 Anello KV

| tag | ora | ctx | t/s | p1 | colpi | anello | nota |
|---|---|---:|---:|---:|---:|---|---|
| `kv_G_cancello` | 11:49 | 10k | 8,66 | — | 34,3 | off | **VUOTO** (300 tk) |
| `kv_A_100k_off` | 11:51 | 100k | 7,49 | — | 34,6 | off | **VUOTO** |
| `kv_B_100k_on` | 11:53 | 100k | 8,54 | — | 34,5 | on | **VUOTO** |
| `k2_A_10k_off` | 12:09 | 10k | 10,31 | 0,880 | 38,3 | off | valido |
| `k2_B_10k_on` | 12:12 | 10k | 10,23 | 0,868 | 38,4 | on | valido |
| `k2_C_100k_off` | 12:17 | 100k | 8,62 | 0,818 | 41,7 | off | valido |
| `k2_D_100k_on` | 12:20 | 100k | **9,29** | 0,826 | 40,1 | on | valido |

**Il +14% del primo giro era su uscite vuote.** Il numero vero dell'anello è la coppia
`k2_C/k2_D`: **8,62 → 9,29 a 100k, +7,8%**, e costo nullo a 10k (10,31 → 10,23).

### 2.7 Binario unito, regola dell'utente, stride, determinismo — 320 slot, anello ON

| tag | ora | ctx | t/s | p1 | colpi | config |
|---|---|---:|---:|---:|---:|---|
| `tt_A_10k_tutto` | 13:37 | 10k | 9,97 | 0,865 | 41,5 | tutto acceso, anello on |
| `tt_C_10k_rif` | 13:46 | 10k | 9,86 | 0,878 | 39,9 | anello off |
| `tt_B_100k_tutto` | 13:42 | 100k | 8,05 | 0,780 | 43,9 | anello on |
| `tt_D_100k_rif` | 13:54 | 100k | 8,54 | 0,823 | 40,7 | anello off |
| `rg_K4_R1/R2/R3` | 14:07-14:22 | 10k | 8,83 / 8,93 / 8,86 | 0,873 / 0,886 / 0,870 | **67,6 / 66,2 / 69,1** | **K=4, regola utente** |
| `rg_K2_R1/R2/R3` | 14:11-14:26 | 10k | 9,66 / 9,52 / 9,84 | 0,840 / 0,796 / 0,838 | 41,7 / 40,9 / 38,8 | K=2 controllo |
| `st_S1_prod` | 16:15 | 10k | 9,91 | 0,840 | 39,7 | produzione |
| `st_S2_prod_bis` | 16:19 | 10k | 9,55 | 0,756 | 43,9 | **identico a S1** |
| `st_S3_nospec` | 16:22 | 10k | 9,24 | — | 43,6 | speculazione OFF |
| `st_S4_nmax2` | 16:27 | 10k | 8,21 | 0,751 | 30,1 | n-max 2 |
| `dt_D1_async0` | 17:04 | 10k | 8,52 | 0,856 | 38,5 | **ASYNC=0** |
| `dt_D2_async0bis` | 17:08 | 10k | 8,87 | 0,875 | 38,2 | **identico a D1** |

**La regola dell'utente, n=3 per braccio**: K=4 quadruplica i colpi (66-69% contro
39-42%) e perde il **9,0%** (8,87 contro 9,67 di mediana). Il traffico DMA si
sovrappone, il calcolo CPU no.

**Nota sul binario unito**: a 100k l'anello ORA PERDE (8,05 contro 8,54), il contrario
di `k2_C/k2_D`. È la regressione che Codex ha poi attribuito alla sonda VRAM compilata
nel cammino caldo; binario ricompilato alle 15:20 con la sonda rimossa.

---

## 3. LA CLASSIFICA VERA, tolte le uscite vuote

| t/s | tag | config | dentro il rumore di 10,41? |
|---:|---|---|---|
| 10,41 | `kf_B_250` | K=2,50 | — |
| 10,31 | `k2_A_10k_off` | K=2, anello off | sì |
| 10,23 | `k2_B_10k_on` | K=2, anello on | sì |
| 10,19 | `k_K3_R2` | **K=3** | sì |
| 10,16 | `kf_C_200` | K=2,00 | sì |
| 10,14 | `kf_A_233` | K=2,33 | sì |
| 10,07 | `k_S1_R2` | K=2 | sì |
| 9,97 | `tt_A_10k_tutto` | binario unito | sì |

**Otto configurazioni diverse, tutte statisticamente indistinguibili.** La lettura
onesta è **SOTA ≈ 10,2 ± 0,4 a 1200 token**, contro il metro 9,28-9,29 senza testa.
Nessun valore di K è separabile dagli altri.

---

## 4. VERDETTI NUOVI — emersi dalla ricostruzione, non dai singoli bracci

### 4.1 La sorgente del non-determinismo è la SPECULAZIONE

Undici run con `spec=no`, sparse su tre ore, su configurazioni **completamente
diverse** — metro, oracolo, prefetch, fasi sfasate, cura — e con t/s da **5,47 a
8,87**, hanno prodotto tutte lo **stesso identico testo**:

```
sha 7B61FD95, 2.991 caratteri
  ch_A0_noovl 8,87 | or_0 8,43 | or_1 8,49 | or_2 5,59 | or_3 5,75
  sf_m1 5,72 | sf_p1 5,70 | sf_m2 5,74 | sf_p2 5,71
  o2_P0 8,55 | o2_P1 8,57 | o2_P2 6,08 | diff 6,13
  cu_M 8,57 | cu_C0 5,58 | cu_M2 8,54 | cu_D0 5,47
```

**Nessuna coppia di run con `spec=si` condivide lo sha.** Quindi: cache, prefetch,
oracolo, overlap e anello sono **bit-esatti**; il non-determinismo entra **solo con la
speculazione**. Questo falsifica l'ipotesi che fosse `kern_partiziona` a ordinare per
residenza — `dt_D1/D2` con `ASYNC=0` sono infatti ancora diversi fra loro, ed erano
entrambi `spec=si`.

Sospetto principale, da falsificare: la bozza DSpark gira **sulla CPU** (`-ngld 0`)
con 7 thread, e `process()` fa due forward CPU per iniettare gli stati nella sua KV.
Un ordine di riduzione OpenMP non deterministico basta a cambiare un token di bozza,
e da lì diverge tutto il testo.

### 4.2 Il +14% dell'anello KV era su pagine bianche

Vedi §2.6. Il numero valido è **+7,8% a 100k**, e a 10k l'anello è gratis.

### 4.3 La cura del prefetch centra il bersaglio e non paga

Colpi 2,3% → **30,2%** (10×), t/s invariato (5,47 → 5,50). Ma misurato con
**l'overlap spento**: nella configurazione di produzione il prefetch non è mai stato
provato. È la lacuna più grossa rimasta.

---

## 5. COSA RESTA APERTO

1. **Il prefetch + la cura nella configurazione di produzione** (overlap K=2, BM=2,
   spec on). Mai fatto: tutto il filone gira a K=0, BM=1.
2. **Slot 320 contro 380.** Cambiati alle 07:00 senza motivo; lo storico dice 380.
3. **La sorgente del non-determinismo**: bozza su GPU (`-ngld` alto) o a 1 thread,
   due volte, per chiudere §4.1.
4. **K=3 contro K=2** con n≥3 per lato: la SOTA di riferimento è a K=3 e giriamo a K=2.
5. **Il trasporto a contesto pieno** con un prompt lungo davvero (30-50k token):
   ogni misura dell'anello finora aveva la cache compressa allo 0,4%.
