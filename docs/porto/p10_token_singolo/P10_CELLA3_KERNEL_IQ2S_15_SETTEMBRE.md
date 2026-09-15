# P10 · cella 3 — il kernel MMVQ degli esperti IQ2_S a una riga: la causa era l'**occupazione**, non la tabella dei codici — 15 settembre 2026

Cella di **diagnosi e correzione**. Domanda: perché `mul_mat_vec_q<iq2_s>` (gate+up degli
esperti, 47 lanci per forward, 470,5 MiB per token) gira al **36% del pavimento di byte**
(3,985 ms misurati contro 1,45 di pavimento), e quanto si recupera **senza cambiare un bit del
testo generato**.

Riferimento di partenza: **V2 = 37,332 ms/token, 26,786 t/s** (media di due repliche, P10 cella 2),
rumore fra repliche 0,152 ms.

`bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, il lanciatore quotidiano, i modelli e
lo snapshot P0 non sono stati toccati. Si è lavorato solo sull'albero P8
(`D:\ds4_work\p8_work\source`, build in `D:\ds4_work\p8_work\build`). **Nessun commit.**

---

## 0. In otto righe

1. **La causa non è la ricerca in tabella: è l'occupazione.** L'istanza che gira davvero —
   `mul_mat_vec_q<iq2_s, ncols_dst=1, has_fusion=true, small_k=true>` — usa **110 registri per
   thread**. A 128 thread per blocco sono **4 blocchi per SM: 512 thread su 1536, il 33%**. Un
   kernel che legge i pesi degli esperti **senza nessun riuso** vive solo di letture in volo, e con
   un terzo dei thread non ne ha abbastanza per coprire la latenza della VRAM.
2. **La correzione è una riga**: il secondo argomento di `__launch_bounds__` passa da `1` a `8` sul
   solo percorso «una riga + `small_k`» dei tipi a tabella. `ptxas` scende a **64 registri, zero
   sversamenti**, e i blocchi residenti passano da **4 a 8** (512 → 1024 thread per SM).
   **Non cambia una sola operazione aritmetica né il loro ordine: lossless per costruzione.**
3. **Al kernel, in situ: 82,88 → 66,21 µs per lancio (−20,1%)**; per token la voce iq2_s passa da
   **3,895 a 3,112 ms** (−0,783). La banda effettiva del kernel va da **126,6 a 158,5 GB/s**,
   l'efficienza sul pavimento di byte dal **36,4% al 46,6%**.
4. **Al banco: 37,332 → 36,703 ms/token, 26,786 → 27,245 t/s** (media di due repliche ciascuno).
   **−0,629 ms/token, +1,71%.** Il cancello di −0,5 ms **è superato** (nove volte il rumore fra
   repliche di V3, che è 0,068 ms).
5. **Impronte identiche 4 su 4 in entrambe le repliche** (`b626d0e377e6075e` ×2,
   `99ba1423cf128585`, `dc916b9c428225c2`): stesso testo byte per byte di V2, V1 e R0.
6. **Nessun altro tipo è toccato**, e si vede nel profilo: `q6_k` 41,023 → 41,022 µs, `q8_0` 12,479
   → 12,448, `iq4_nl` 38,526 → 38,399. Solo `iq2_s` si muove.
7. **Le tre idee «ovvie» sono tutte falsificate dalla misura**: tabella dei codici in memoria
   condivisa (+3,0%), attivazioni q8_1 in memoria condivisa (+7,1%), pesi letti fuori dalla L1
   con `.cg` (+23,6%). Tutte bit-identiche, tutte **più lente**.
8. **L'estensione a IQ4_NL (il down) non paga**: 72 → 64 registri, 7 → 8 blocchi per SM, ma al banco
   36,760 ms/token, dentro lo scarto fra le due repliche di V3. Resta dietro un interruttore
   (livello 2), **spenta di default**.

---

## 1. Cancello di partenza e stato dei processi

Guardia eseguita prima di ogni avvio e prima della build:
`netstat -ano | findstr LISTENING | findstr :8100` vuoto, `tasklist | findstr llama-server` vuoto,
nessun processo di compilazione. Nessun server non mio è stato trovato: si è proceduto ogni volta.
Un solo server, una sola sonda, un solo microbanco alla volta per tutta la cella.

**Stato a fine cella, verificato**: nessun `llama-server`, nessun `nsys`, `nsys sessions list` vuota,
porta 8100 libera, nessuna build in corso, nessun processo residuo.

Ordine delle corse: (1) microbanco isolato, molte varianti → (2) `cuobjdump -res-usage` sull'oggetto
`mmvq.cu.obj` **prima** della patch → (3) build → (4) `cuobjdump` **dopo** → (5) V3 al banco
replica 1 → (6) V3 profilata con nsys → (7) V3 al banco replica 2 → (8) V3b (livello 2) al banco.
**Nessuna corsa è partita con una build in corso**, e fra la build (fine 17:30:15) e la prima
misura (17:35:05) è passato il tempo perché la macchina tornasse quieta.

---

## 2. A — la diagnosi, fatta con un microbanco isolato

### 2.1 Perché un microbanco e non `ncu`

`ncu` è installato (Nsight Compute 2024.3.2) ma **rifiuta di leggere i contatori**:
`ERR_NVGPUCTRPERM — The user does not have permission to access NVIDIA GPU Performance Counters`.
Sbloccarlo richiede una modifica alle impostazioni di sistema (chiave di registro o driver in
modalità permissiva): **non è stata fatta**. Di conseguenza **non ci sono numeri di occupancy,
stalli o transazioni letti dall'hardware**: tutta la diagnosi di questa cella è per **ablazione**
(togliere un pezzo e misurare quanto costava) e per **risorse dichiarate dal compilatore**
(`cuobjdump -res-usage`), che non richiede permessi.

### 2.2 Il microbanco riproduce esattamente uno dei 47 lanci

`micro_iq2s_p10.cu` è un `.cu` autonomo (include solo `ggml-common.h`) che contiene una **copia
fedele** di `vec_dot_iq2_s_q8_1` e dell'istanza di `mul_mat_vec_q` che la 3060 lancia davvero.
Non usa la DLL del fork: il kernel è ricompilato dentro il microbanco, così si può cambiarlo,
rimisurarlo e **confrontare l'uscita elemento per elemento** con quella originale.

| | |
|---|---|
| forma | `x` = esperti gate/up **iq2_s reali estratti dal GGUF** (`blk.10.ffn_gate_exps.weight` e `..._up_exps`, 48 esperti, 25,2 MB ciascuno), `[n_embd 2560, n_ff_exp 640]` |
| token | 1 riga, `ids` = 10 esperti, attivazioni q8_1 deterministiche (80 blocchi) |
| fusione | gate+up fusi con SWIGLU (`has_fusion=true`, `use_gate=true`): è quello che gira nel modello |
| geometria | quella scelta dal dispatcher su cc 8.6 (tabella `GENERIC`, `has_ids`, `ncols_dst=1`): `nwarps=4`, **`small_k=true` → `rows_per_cuda_block=4`**, griglia 160×10, blocco 32×4 |
| byte per lancio | 10 × 640 × 10 × 82 B × 2 = **10,010 MiB** — cioè 470,5 MiB / 47, la voce iq2_s di P9 divisa per i suoi lanci |
| misura | 9 round da 100 lanci, si riporta il **minimo** (il round più quieto) e la mediana |
| controllo | l'uscita (6.400 float) confrontata con `memcmp` contro quella di V0 |

Il microbanco misura **57,63 µs** per lancio dove il server ne misura **82,88**: i due numeri non
sono lo stesso esperimento (§6, difetto 3). Il microbanco serve a **ordinare le varianti**, non a
prevedere il guadagno.

### 2.3 La scomposizione per ablazione: dove vanno i 57,6 µs

Le ablazioni **cambiano il risultato** (non sono adottabili): servono a pesare le voci.

| ablazione | µs (min) | GB/s | costo della voce tolta |
|---|---:|---:|---:|
| **V0, kernel intero** | **57,63** | **182,1** | — |
| senza la ricerca in `iq2s_grid` (indice fisso) | 45,75 | 229,4 | **11,88 µs (20,6%)** |
| senza l'aritmetica dei segni | 50,46 | 208,0 | **7,17 µs (12,4%)** |
| senza né tabella né segni | **35,19** | **298,2** | 22,44 µs (38,9%) |

Il fondo a **35,19 µs / 298,2 GB/s** è il **pavimento dello schema d'accesso**: stessi byte, stessa
griglia, stessi `dp4a`, ma senza dequantizzazione a tabella. È l'**87,6%** della banda VRAM
misurata da P9 (340,3 GB/s). Quindi il kernel di oggi lascia sul tavolo **22,4 µs per lancio**, cioè
**1,05 ms per token**, ed è di questi che parlava la leva 3 di P9 (−1,4…−1,9 ms stimati con un
modello a due termini: la misura diretta dice **−1,05 ms**, meno di quella stima).

### 2.4 La causa vera: 110 registri, 4 blocchi per SM

`cuobjdump -res-usage` sull'oggetto **reale** (`mmvq.cu.obj` del binario V2), per le sole istanze a
`ncols_dst = 1` (128 thread per blocco su sm_86: 65.536 registri, 102.400 B di shared, 1.536 thread
per SM):

| tipo | fusione | `small_k` | REG | SHARED | LOCAL | blocchi/SM | thread/SM | occupazione |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **iq2_s** | **sì** | **sì** | **110** | 3.072 | 0 | **4** | **512** | **33,3%** |
| iq2_s | sì | no | 53 | 768 | 0 | 9 | 1.152 | 75,0% |
| iq2_s | no | sì | 94 | 1.536 | 0 | 5 | 640 | 41,7% |
| iq4_nl | sì | sì | 72 | 3.072 | 0 | 7 | 896 | 58,3% |
| q6_k | sì | sì | 96 | 3.072 | 0 | 5 | 640 | 41,7% |
| q6_k | no | no | 40 | 384 | 0 | 12 | 1.536 | 100,0% |
| iq3_s | sì | sì | 134 | 3.072 | 0 | 3 | 384 | 25,0% |
| q3_k | sì | sì | 207 | 3.072 | 0 | 2 | 256 | 16,7% |

L'istanza che il modello usa per gate+up è la prima riga. **`small_k` e la fusione, messe insieme,
raddoppiano il lavoro srotolato dentro il ciclo** (4 righe × 2 tensori = 8 chiamate di `vec_dot`
completamente inline, ognuna con 4 ricerche in tabella), il compilatore tiene tutto in volo e
arriva a 110 registri. `__launch_bounds__` dichiara `1` come minimo di blocchi per SM, cioè
**non gli chiede niente**: `ptxas` è libero di salire fino a 255.

Il conto torna col resto: la voce `q6_k` (9,6 ms per token, la più grande) **non** passa per
`small_k` — i suoi tensori densi hanno `blocks_per_row_x = 10` e `blocks_per_iter_1warp = 1`,
quindi il cancello `blocks_per_row_x < nwarps * blocks_per_iter_1warp` (10 < 4) è falso — e infatti
gira a 40 registri, 12 blocchi per SM, 100% di occupazione e 292 GB/s (P9). **La famiglia lenta è
esattamente quella con l'occupazione bassa.**

### 2.5 Le tre idee che sembravano ovvie, e sono tutte sbagliate

Tutte e tre sono **bit-identiche** a V0 (verificato su tutti i 6.400 elementi dell'uscita): sono
state scartate per il tempo, non per la correttezza.

| variante candidata | µs (min) | contro V0 | bit=V0 | perché non paga |
|---|---:|---:|:--:|---|
| **S1** `iq2s_grid` (8 KiB) in memoria condivisa | 59,35 | **+3,0%** | sì | ogni blocco deve ricopiarsi 8 KiB, e sono 1.600 blocchi per lancio: la copia costa più di quello che risparmia. Inoltre 8 KiB di shared per blocco tagliano l'occupazione |
| **S2** attivazioni q8_1 in memoria condivisa (passo 9 int, senza conflitti di banco) | 61,73 | **+7,1%** | sì | le attivazioni sono 2,8 KiB e stanno già in L1: spostarle aggiunge una `__syncthreads` e un giro di copie senza togliere niente |
| **S3** entrambe | 62,29 | +8,1% | sì | — |
| **S4** griglia in shared come due vettori a 32 bit (lo/hi) | 60,26 | +4,6% | sì | idem S1 |
| **C1** pesi letti con `.cs` (sfratto per primo dalla L1) | 59,08 | +2,5% | sì | i pesi degli esperti non hanno riuso, ma toglierli dalla L1 non libera niente di utile |
| **C2** pesi letti con `.cg` (fuori dalla L1) | 71,22 | **+23,6%** | sì | **la L1 serviva**: senza, ogni lettura a 2 byte di `qs`/`qh`/`scales` diventa una transazione verso la L2 |
| **U2** ciclo sulle righe srotolato per due | 60,87 | +5,6% | sì | meno registri ma anche meno letture in volo |

Il verdetto della leva 3 di P9 («tabella dei codici in memoria condivisa o costante, più warp per
riga») era una **ipotesi ragionevole e falsa**: il collo non è dove si trova la tabella, è quanti
thread stanno contemporaneamente in volo.

---

## 3. B — la correzione, e la prova che è lossless

### 3.1 Che cosa cambia

Un solo file, `ggml/src/ggml-cuda/mmvq.cu`. Il template `mul_mat_vec_q` prende un parametro in più,
`int min_blocks = 1`, che finisce nel secondo argomento di `__launch_bounds__`:

```
__launch_bounds__(calc_nwarps(...)*ggml_cuda_get_physical_warp_size(), min_blocks)
```

Il dispatcher del percorso `ncols_dst == 1` sceglie `min_blocks = 8` **solo** quando tutte queste
cose sono vere insieme: `ncols_dst == 1`, `small_k`, scheda NVIDIA, build non-HIP/non-MUSA, e il
tipo è uno di quelli dichiarati (`iq2_s` al livello 1, `iq4_nl` al livello 2). In ogni altro caso
resta `1`, e **nessuna istanza aggiuntiva viene generata**: le istanze in più sono quattro
(`iq2_s` e `iq4_nl`, con e senza fusione, solo `small_k`).

Interruttore `GGML_CUDA_MMVQ_OCCUPANCY`: `0` = comportamento di V2, **`1` = solo `iq2_s` (default)**,
`2` = anche `iq4_nl`.

### 3.2 Perché è lossless **per costruzione**

`__launch_bounds__` è una dichiarazione al compilatore su quanti blocchi devono poter stare
residenti su un SM. Non tocca:

* le operazioni aritmetiche (stesse `dp4a`, stessi `__vsub4`, stesse moltiplicazioni);
* il loro **ordine** (stesso ciclo su `l0`, stessi `sumi0`/`sumi1`, stessa riduzione
  `tmp_shared` → `warp_reduce_sum`, stesso `nwarps`, stesso `rows_per_cuda_block`);
* la mappa da thread a dati (`kbx = tid/(qi/vdr)`, `kqs = vdr*(tid%(qi/vdr))` invariati);
* la geometria di lancio (`calc_launch_params` non vede `min_blocks`).

Cambia solo **quanti registri `ptxas` può usare** e quindi come schedula le stesse istruzioni.
Non è però un argomento sufficiente da solo — un compilatore che cambia allocazione potrebbe
cambiare la contrazione in FMA — quindi è stato **verificato due volte**:

1. **nel microbanco**, confrontando con `memcmp` tutti i 6.400 float dell'uscita contro il kernel
   originale, su pesi iq2_s **veri**: identici;
2. **al banco**, con le impronte del testo generato: **4 su 4 identiche, in entrambe le repliche**.

Verifica sul binario compilato (`cuobjdump -res-usage`, `registri_mmvq_p10.py`):

| istanza | REG prima | REG dopo | LOCAL (sversamenti) | blocchi/SM prima → dopo | occupazione |
|---|---:|---:|---:|---|---|
| `iq2_s` fusione + `small_k` | 110 | **64** | **0** | **4 → 8** | 33,3% → 66,7% |
| `iq2_s` senza fusione + `small_k` | 94 | 64 | 0 | 5 → 8 | 41,7% → 66,7% |
| `iq4_nl` fusione + `small_k` (livello 2) | 72 | 64 | 0 | 7 → 8 | 58,3% → 66,7% |
| tutti gli altri tipi | invariati | invariati | 0 | invariati | invariata |

**Zero sversamenti**: il tetto a 64 registri è stretto ma non costringe a usare memoria locale.

### 3.3 Perché 8 e non di più

Il tetto è stato scelto **per misura**, non per modello. Nel microbanco:

| tetto `__launch_bounds__(128, N)` | µs (min) | GB/s | bit=V0 |
|---|---:|---:|:--:|
| 1 (originale) | 57,63 | 182,1 | rif. |
| 2 | 57,54 | 182,4 | sì |
| 3 | 55,99 | 187,5 | sì |
| 4 | 56,38 | 186,2 | sì |
| 5 | 54,69 | 191,9 | sì |
| 6 | 53,35 | 196,7 | sì |
| **8** | **52,60** | **199,5** | **sì** |
| 10 | 54,21 | 193,6 | sì |
| **12** | **119,02** | 88,2 | sì | 

A 12 blocchi il tetto scende a 40 registri, `ptxas` sversa in memoria locale e il kernel **raddoppia**
il tempo. A 10 comincia già a peggiorare. **8 è il massimo prima del muro**, e coincide col punto in
cui il vincolo passa dai registri alla memoria condivisa (3.072 B × 8 = 24.576 B, ancora larghi).

### 3.4 La variante migliore del microbanco **non** è quella adottata

`S4+R8` (griglia in shared come due vettori a 32 bit **e** tetto a 8) dà 51,75 µs contro i 52,60 di
`R8`: **−0,85 µs per lancio, cioè −0,04 ms per token**. È un quarto del rumore del banco, in cambio
di 8 KiB di memoria condivisa e di una `__syncthreads` in un kernel condiviso da tutti i tipi.
**Non adottata**, e registrata qui perché è misurata: la memoria condivisa aiuta **solo** dopo che
l'occupazione è stata sistemata, e anche allora quasi per niente.

---

## 4. C — la misura nel server

### 4.1 Il kernel, prima e dopo, dentro il server

Profili nsys, finestra di 5 s dentro il decode di `L01@ctx131k`, stesso strumento e stesso
protocollo della cella 2 (`avvia_p10_nsys.ps1`, `nsys launch -t cuda --cuda-graph-trace=node`,
cattura aperta 8 s dopo il primo delta SSE). Il «prima» è la corsa profilata di V2 già in archivio
(`20260915_163619_P10_p10_c2_dopo_v2`), il «dopo» è `20260915_181857_P10_p10_c3_dopo_v3`.
`kernel_mmvq_p10.py` riporta il tempo **per lancio**, che non dipende da quanti forward ci sono
nella finestra.

| `mul_mat_vec_q<...>` | lanci (V2) | µs mediana V2 | lanci (V3) | µs mediana V3 | **delta** |
|---|---:|---:|---:|---:|---:|
| **iq2_s** (gate+up esperti) | 6.421 | **82,879** | 6.575 | **66,208** | **−16,671 (−20,1%)** |
| iq4_nl (down esperti) | 6.557 | 38,526 | 6.715 | 38,399 | −0,127 (−0,3%) |
| q6_k (densi, testa) | 27.595 | 41,023 | 28.257 | 41,022 | **−0,001 (0,0%)** |
| q8_0 (connessioni `hc_`) | 33.735 | 12,479 | 34.552 | 12,448 | −0,031 (−0,2%) |
| iq3_s | 136 | 97,296 | 140 | 97,344 | +0,048 |

Sulla media invece che sulla mediana: iq2_s **84,547 → 69,267 µs (−18,1%)**; sul minimo
**76,191 → 51,488 µs**. Il minimo è interessante: è il lancio meno disturbato della finestra, e
scende del 32,4% — praticamente il valore del microbanco.

Che `q6_k` si muova di **un nanosecondo** su 27.595 lanci è la miglior prova che la patch tocca solo
quello che dice di toccare.

**Per token** (47 lanci di iq2_s per forward):

| | V2 | V3 | delta |
|---|---:|---:|---:|
| voce iq2_s, mediana | 3,895 ms | **3,112 ms** | **−0,783** |
| voce iq2_s, media | 3,974 ms | 3,256 ms | −0,718 |
| banda effettiva del kernel | 126,6 GB/s | **158,5 GB/s** | +25,2% |
| efficienza sul pavimento di byte (1,45 ms) | 36,4% | **46,6%** | +10,2 punti |

### 4.2 Il banco

Profilo `lungo_131k`, budget `screening` (1.024 token per caso, 2 casi = 2.048 token), greedy
seed 1234, ragionamento acceso, MTP spento, 64 slot, `-np 1`, contesto 262.144.

| corsa | ms/token | t/s | impronte |
|---|---:|---:|---|
| V2 r1 (`20260915_162514`) | 37,408 | 26,732 | 4/4 |
| V2 r2 (`20260915_165455`) | 37,256 | 26,841 | 4/4 |
| **V2 media** | **37,332** | **26,786** | |
| V3 r1 (`20260915_173505`) | 36,669 | 27,271 | 4/4 |
| V3 r2 (`20260915_180825`) | 36,737 | 27,220 | 4/4 |
| **V3 media** | **36,703** | **27,245** | |
| **delta V3 − V2** | **−0,629** | **+0,459 (+1,71%)** | |
| V3b, livello 2 (`20260915_184154`) | 36,760 | 27,203 | 4/4 |

Impronte, identiche in tutte e cinque le corse e uguali a V1 e R0:
`riscaldamento_1 = riscaldamento_2 = b626d0e377e6075e`, `L01@ctx131k = 99ba1423cf128585`,
`L02@ctx131k = dc916b9c428225c2`.

**Rumore fra le due repliche di V3: 0,068 ms** (quello di V2 era 0,152). Il guadagno è
**nove volte** il rumore di V3 e **quattro volte** quello di V2. **Cancello di −0,5 ms superato**:
la ripetizione prevista per la fascia 0,15-0,5 non era necessaria, ma la seconda replica è stata
fatta comunque per avere due medie confrontabili.

Carico misurato durante le corse:

| corsa | RAM disponibile minima | VRAM libera minima | clock SM mediano | uso GPU mediano |
|---|---:|---:|---:|---:|
| V3 r1 | 6,88 GB | 1.189 MiB | 1.927 MHz | 99% |
| V3 r2 | 7,08 GB | 1.185 MiB | 1.920 MHz | 99% |
| V3 profilata | 6,74 GB | 1.126 MiB | 1.920 MHz | 99% |
| V3b | 7,07 GB | 1.185 MiB | 1.920 MHz | 99% |

(per confronto: V2 r1 2,77 GB / 1.213 MiB — quella corsa aveva il profilatore di cella 2 attaccato
in un'altra finestra; V2 r2 6,77 GB / 1.221 MiB.)

### 4.3 Il conto che non torna del tutto

Il kernel guadagna **0,783 ms** per token (mediana) ma il banco ne guadagna **0,629**. I 0,15 ms di
differenza sono **riassorbiti**, e la spiegazione più probabile è quella che la cella 2 aveva già
incontrato: il `moe_grouped_gather_decode` gira sovrapposto e prende parte del tempo che il kernel
libera (nella finestra profilata è passato da 887,8 a 909,8 ms, +2,5%, su un numero di forward
cresciuto del 2,4%: quindi sostanzialmente invariato per forward, ma occupa una fetta maggiore di un
forward più corto). **Non è stato isolato**: resta un fronte aperto.

### 4.4 IQ4_NL: la stessa correzione, e non paga

Al livello 2 il tetto vale anche per il `down` degli esperti (`iq4_nl`, 421,9 MiB per token,
1,852 ms in P9): i registri scendono da 72 a 64 e i blocchi per SM da 7 a 8 (58,3% → 66,7%).
Al banco: **36,760 ms/token**, cioè **+0,057 rispetto alla media di V3** e dentro lo scarto fra le
due repliche di V3 (36,669 e 36,737). Impronte 4/4.

**Verdetto: neutro, non adottato.** È coerente con la diagnosi: `iq4_nl` non ha una ricerca in
tabella (usa `get_int_from_table_16` con `__byte_perm` su 16 byte), partiva già a 238,9 GB/s (70%
del picco) e a 7 blocchi per SM; il margine di occupazione da recuperare era un settimo, non due
terzi. L'interruttore resta, spento, per chi volesse riprovarlo su un'altra scheda.

---

## 5. Verdetto

**Adottata: `GGML_CUDA_MMVQ_OCCUPANCY=1`** (tetto di 8 blocchi per SM sul percorso a una riga con
`small_k`, solo `iq2_s`). È il default della patch.

* **lossless**: dimostrato, non assunto — `memcmp` su tutta l'uscita del microbanco con pesi reali, e
  impronte 4/4 al banco su due repliche;
* **guadagno**: −0,629 ms/token, +0,459 t/s (**26,786 → 27,245**), kernel −20,1%;
* **costo**: una riga di `__launch_bounds__`, quattro istanze di template in più, nessun rischio sul
  modello, nessuna memoria in più;
* **rischio residuo**: il tetto è tarato sulla 3060 (sm_86, 1.536 thread e 65.536 registri per SM).
  Su una scheda con altri limiti il valore 8 va rimisurato; l'interruttore a 0 lo disattiva.

La leva 3 di P9 stimava **−1,4…−1,9 ms** e la definiva «alta difficoltà, riscrivere il prodotto
scalare». Il risultato reale è **−0,63 ms senza toccare il prodotto scalare**: la stima era giusta
nel segno, sbagliata nella causa e ottimista nel valore, perché il modello a due termini attribuiva
alla *dequantizzazione* un tempo che era in buona parte *latenza non coperta*.

Posizione nel piano: V1 37,486 → V2 37,332 (cella 2, −0,154) → **V3 36,703** (cella 3, −0,629).
Dal punto di partenza R0 (37,906) siamo a **−1,203 ms/token, +0,864 t/s**, tutto lossless.

---

## 6. Difetti di questa misura

1. **Niente contatori hardware.** `ncu` è bloccato da `ERR_NVGPUCTRPERM` e sbloccarlo è una modifica
   di sistema che non è stata fatta. Non ci sono numeri letti dall'hardware su occupancy raggiunta,
   stalli, transazioni o conflitti di banco: l'occupazione qui è **calcolata** dai registri
   dichiarati da `ptxas`, non osservata. Il legame «registri → blocchi per SM → tempo» è provato
   dalla curva dei tetti (§3.3), non da un contatore.
2. **Il microbanco sottostima il guadagno di un fattore due**: −9,4% contro −20,1% in situ. Il
   microbanco lancia il kernel da solo, in un ciclo stretto, con le stesse 10 schede di esperti; nel
   server lo stesso kernel divide il bus col trasporto PCIe degli esperti mancanti e vede una L2
   sporcata da altri 4.000 kernel per forward. **Il microbanco ordina le varianti, non predice il
   tempo.** Le varianti scartate (S1-S4, C1-C2, U1-U2) sono state scartate su quel banco: una di
   esse potrebbe comportarsi diversamente in situ. Non è stato verificato.
3. **25 µs per lancio non spiegati.** 57,63 µs nel microbanco contro 82,88 nel server, sulla stessa
   forma, sugli stessi byte, con la stessa geometria. Contesa sul bus, clock, sporcizia della L2,
   disposizione degli esperti nel pool: nessuna di queste è stata isolata. Fronte aperto.
4. **Il valore 8 è empirico.** Non c'è un modello che dica perché 8 e non 6 o 10; c'è una curva
   misurata su una scheda. Il salto a 12 (crollo a 119 µs) dice solo dove sta il muro degli
   sversamenti.
5. **V3b ha una sola replica.** Il verdetto «neutro» su `iq4_nl` regge perché il valore cade dentro
   lo scarto delle due repliche di V3, non perché sia stato misurato due volte.
6. **I pesi del microbanco vengono da un solo strato** (`blk.10`). La distribuzione degli indici
   della griglia potrebbe non essere identica in tutti gli strati; il costo della ricerca (§2.3)
   potrebbe variare leggermente.
7. **Le impronte coprono il testo, non i numeri interni.** Due kernel possono dare lo stesso testo
   greedy con logit leggermente diversi. Il controllo forte è il `memcmp` del microbanco, che però
   gira su una forma sola.

---

## 7. Aperture

1. **Il 37,5% dei thread del blocco non fa nessun `vec_dot`.** Con `ncols_x = 2560` ci sono
   `blocks_per_row_x = 10` superblocchi per riga, ma il blocco da 4 warp ne copre
   `blocks_per_iter = 16`: solo i thread con `tid < 80` entrano nel ciclo. **48 thread su 128 sono
   morti**, e il warp 3 per intero. Sommato all'occupazione di oggi (66,7%) vuol dire che i thread
   che lavorano davvero sono il **41,7%** del massimo. Correggerlo (per esempio 5 warp con 2 righe
   per blocco, 160 thread tutti attivi) **cambia l'ordine delle riduzioni** e non è lossless: è la
   prossima leva grossa, ma costa il cancello dell'impronta.
2. **Restano 22,4 µs per lancio sopra il pavimento** (§2.3): 11,9 di ricerca in tabella e 7,2 di
   aritmetica dei segni. Sono **1,05 ms per token**. Per prenderli servirebbe un formato
   ripacchettato (segni già applicati, griglia espansa) — lossless sull'uscita ma non sui byte del
   GGUF — oppure una riscrittura del prodotto scalare che condivida qualcosa fra `gate` e `up`, cosa
   che oggi non si può perché i due tensori hanno indici diversi.
3. **`q6_k` con fusione e `small_k` sta a 96 registri, 5 blocchi per SM (41,7%).** Non è la voce
   grande di `q6_k` (i densi non passano per `small_k`), ma è l'esperto condiviso: vale la pena
   provare il livello anche lì, è gratis. Stesso discorso per `iq2_xs`/`iq2_xxs`/`iq3_xxs` (tutti a
   4 blocchi per SM) se un giorno il modello li usasse.
4. **`iq3_s` sta a 3 blocchi per SM e `q3_k` a 2** (134 e 207 registri). Nel nostro modello `iq3_s`
   sono due tensori e valgono 12,4 ms su 4.952 nella finestra: trascurabile. Ma è la stessa malattia,
   peggiore.
5. **`S4+R8` vale un altro −0,04 ms/token nel microbanco.** Sotto il rumore del banco, ma se un
   giorno la geometria cambia (apertura 1) la memoria condivisa potrebbe tornare a pagare: la
   variante è già scritta e verificata bit a bit nel microbanco.
6. **I 0,15 ms che il gather si riprende** (§4.3). È la stessa cosa vista nella cella 2 col buco 2:
   ogni volta che si libera tempo sulla GPU, una parte la riprende il trasporto. Va capito una volta
   per tutte, perché altrimenti ogni leva futura pagherà la stessa tassa.

---

## 8. Bozza di voce di registro

> **15 settembre 2026 — P10, cella 3 (il kernel MMVQ degli esperti IQ2_S a una riga).**
>
> *Ipotesi.* P9 attribuiva il 64% del tempo di `mul_mat_vec_q<iq2_s>` (3,985 ms per token, 36%
> del pavimento di byte) alla dequantizzazione a tabella, e proponeva di spostare `iq2s_grid` in
> memoria condivisa. **Ipotesi falsificata.** La causa è l'**occupazione**: l'istanza reale
> (`ncols_dst=1`, fusione gate+up, `small_k`) usa **110 registri** per thread e resta a **4 blocchi
> per SM su 12 possibili (33%)**; un kernel che legge pesi senza nessun riuso non ha abbastanza
> letture in volo. Le tre idee «ovvie» (griglia in shared, attivazioni in shared, pesi fuori dalla
> L1) sono tutte bit-identiche e tutte **più lente** (+3,0%, +7,1%, +23,6%).
>
> *File toccati.* Solo `ggml/src/ggml-cuda/mmvq.cu` nell'albero P8
> (`D:\ds4_work\p8_work\source`). Patch `docs/porto/p10_token_singolo/p10_cella3.patch` (130 righe)
> rispetto allo stato dopo la cella 2. Il template `mul_mat_vec_q` prende `int min_blocks = 1`, che
> finisce nel secondo argomento di `__launch_bounds__`; il dispatcher mette 8 solo su
> «una riga + `small_k` + NVIDIA + tipo dichiarato». Quattro istanze di template in più, nessun'altra
> famiglia toccata. Nuovi strumenti: `micro_iq2s_p10.cu` (microbanco isolato con pesi iq2_s veri e
> confronto bit a bit), `registri_mmvq_p10.py`, `kernel_mmvq_p10.py`, `estrai_iq2s_p10.py`.
>
> *Configurazioni.* `GGML_CUDA_MMVQ_OCCUPANCY`: 0 = V2, **1 = solo iq2_s (default)**, 2 = anche
> iq4_nl. Preset `preset_V3_p10.json` e `preset_V3b_p10.json`, derivati da `preset_V2_p10.json`
> senza altre differenze. Profilo `lungo_131k`, budget 1.024, greedy seed 1234, ragionamento acceso,
> MTP spento, 64 slot, contesto 262.144, `-np 1`.
>
> *Corse valide.* V3 r1 `20260915_173505` (36,669 ms/token), V3 r2 `20260915_180825` (36,737),
> V3 profilata `20260915_181857`, V3b `20260915_184154` (36,760). **Impronte 4/4 identiche a V2, V1
> e R0 in tutte.** RAM disponibile minima 6,74-7,08 GB, VRAM libera minima 1.126-1.189 MiB, uso GPU
> mediano 99%. *Corse invalide:* nessuna. Un lancio della replica 2 in finestra separata non è
> partito (`Start-Process` con percorso relativo) e non ha prodotto niente: non è una corsa.
>
> *Risultato e limite.* Registri **110 → 64** senza sversamenti, blocchi per SM **4 → 8**. Kernel
> in situ **82,88 → 66,21 µs** per lancio (**−20,1%**), banda **126,6 → 158,5 GB/s**, efficienza sul
> pavimento **36,4% → 46,6%**. Al banco **37,332 → 36,703 ms/token**, **26,786 → 27,245 t/s**
> (**−0,629 ms, +1,71%**), contro un rumore fra repliche di 0,068 ms. **Cancello di −0,5 ms
> superato.** Il limite: il kernel libera 0,783 ms ma al token ne arrivano 0,629 — 0,15 se li
> riprende il trasporto sovrapposto, come nella cella 2. E `ncu` è bloccato dai permessi sui
> contatori: l'occupazione è calcolata dai registri, non osservata.
>
> *Decisione.* **Adottata al livello 1.** `iq4_nl` (livello 2) misurato separatamente:
> 36,760 ms/token, dentro lo scarto delle repliche di V3 → **neutro, non adottato**, interruttore
> lasciato spento. Scartata `S4+R8` (griglia lo/hi a 32 bit in shared + tetto): vale un altro
> −0,04 ms/token nel microbanco, un quarto del rumore del banco, in cambio di 8 KiB di shared e una
> `__syncthreads` in un kernel condiviso da tutti i tipi.
>
> *Regressioni.* Nessuna. `q6_k` 41,023 → 41,022 µs su 27.595 lanci, `q8_0` 12,479 → 12,448,
> `iq4_nl` 38,526 → 38,399: solo `iq2_s` si muove. Nessun `bin_prod`, nessun `qwen38_clean`, nessun
> lanciatore quotidiano, nessun modello, nessuno snapshot toccato. **Nessun commit.**
>
> *Stato processi.* A fine cella: nessun `llama-server`, nessun `nsys`, `nsys sessions list` vuota,
> porta 8100 libera, nessuna build in corso.
>
> *Prossima azione.* Il fatto nuovo da cui ripartire: **nel blocco da 128 thread, 48 non fanno
> nessun `vec_dot`** — `blocks_per_row_x = 10` contro `blocks_per_iter = 16`, il warp 3 è morto per
> intero. Coi 66,7% di occupazione di oggi i thread utili sono il **41,7%** del massimo. Recuperarli
> (5 warp, 2 righe per blocco, 160 thread tutti attivi) è la leva più grande rimasta sul kernel, ma
> **cambia l'ordine delle riduzioni**: va deciso se si accetta di perdere il cancello dell'impronta
> bit a bit, oppure se si può trovare una geometria a somme invarianti.

---

## 9. Consegne

| file | che cos'è |
|---|---|
| `docs/porto/p10_token_singolo/P10_CELLA3_KERNEL_IQ2S_15_SETTEMBRE.md` | questo documento |
| `docs/porto/p10_token_singolo/p10_cella3.patch` | il diff (`diff -d -u`) di `mmvq.cu` rispetto allo stato dopo la cella 2, 130 righe, UTF-8 senza BOM |
| `docs/porto/p10_token_singolo/micro_iq2s_p10.cu` | il microbanco isolato: copia fedele del kernel, 16 varianti candidate + 4 ablazioni, confronto bit a bit su pesi reali |
| `docs/porto/p10_token_singolo/compila_micro_p10.ps1` | compila il microbanco (nvcc, sm_86); non tocca l'albero P8 |
| `docs/porto/p10_token_singolo/estrai_iq2s_p10.py` | estrae dal GGUF i byte grezzi di un tensore di esperti (legge solo intestazione + fetta) |
| `docs/porto/p10_token_singolo/registri_mmvq_p10.py` | registri, shared e blocchi per SM di ogni istanza di `mul_mat_vec_q` da `cuobjdump -res-usage` |
| `docs/porto/p10_token_singolo/kernel_mmvq_p10.py` | tempo per lancio di `mul_mat_vec_q` per famiglia di quanto, da una traccia nsys |
| `docs/porto/p10_token_singolo/fai_patch_p10_c3.ps1` | genera la patch |
| `docs/porto/p10_token_singolo/copia_log_p10c3.py` | raccoglie i log puliti e la tabella di confronto |
| `docs/porto/p10_token_singolo/log/p10c3_microbanco.txt` | l'uscita completa del microbanco |
| `docs/porto/p10_token_singolo/log/p10c3_registri_prima.txt` · `..._dopo.txt` | le tabelle dei registri prima e dopo |
| `docs/porto/p10_token_singolo/log/p10c3_kernel_prima_V2.json` · `..._dopo_V3.json` | i tempi per lancio dai due profili nsys |
| `docs/porto/p10_token_singolo/log/p10c3_V3r1_*` · `p10c3_V3r2_*` · `p10c3_V3b_*` | riepiloghi, risultati, argomenti redatti e minimi di carico delle corse |
| `docs/porto/p10_token_singolo/log/p10c3_confronto_V2_V3.md` · `.json` | la tabella V2/V3/V3b |
| `docs/porto/banco_p0/preset_V3_p10.json` | il preset adottato (livello 1), JSON senza BOM |
| `docs/porto/banco_p0/preset_V3b_p10.json` | il preset del livello 2 (iq4_nl), misurato e non adottato |
