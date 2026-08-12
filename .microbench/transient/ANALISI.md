# Slab transiente e percorso CPU

## Perimetro verificato

Analisi eseguita sul contenuto corrente, non modificato, di:

- `ds4-p4a/ds4_cuda.cu`, SHA-256
  `322E1B8B62DE3515B3E727C59BDD72F439C24631B4F282D5BC2FCD2012A9D369`;
- `ds4-p4a/ds4.c`, SHA-256
  `F7104BC315BA25E70F429294675D6EC76F1B81051B5BDED723D2B22385CF6F35`.

Il diff in `slabprobe.patch` è stato prodotto contro questo snapshot. Non è
stato applicato. Non sono stati compilati binari e non è stato avviato
`ds4_server`.

## 1. Peso dello slab transiente in VRAM

### Allocazione effettiva

`route_host_gate`, `route_host_up` e `route_host_down` sono staging **host
pinned**, non VRAM: il layout packed usa un solo `cudaHostAlloc` e ricava le
tre plane per offset (`ds4-p4a/ds4_cuda.cu:37603-37621`); il layout non packed
usa tre `cudaHostAlloc` (`ds4-p4a/ds4_cuda.cu:37623-37634`).

Lo slab transiente in VRAM è invece `route_transient_*`:

- layout packed: un `cudaMalloc(packed_bytes)`, con
  `packed_bytes = 2 * gate_plane_bytes + down_plane_bytes`
  (`ds4-p4a/ds4_cuda.cu:37635-37655`);
- layout non packed: tre `cudaMalloc`, uno per gate, up e down
  (`ds4-p4a/ds4_cuda.cu:37657-37670`).

`packed_route_host_alloc` descrive quindi l'allocazione host; il campo che
descrive il corrispondente slab device packed è `packed_transient_alloc`
(`ds4-p4a/ds4_cuda.cu:37756-37761`).

### Calcolo per la configurazione di riferimento

Con `CUDA_MOE_ROUTE_COUNT = 6`, gate/up da `2.162.688 B` ciascuno e down da
`2.752.512 B`:

| Componente | Formula | Byte | MiB |
|---|---:|---:|---:|
| plane gate | `6 * 2.162.688` | 12.976.128 | 12,375 |
| plane up | `6 * 2.162.688` | 12.976.128 | 12,375 |
| plane down | `6 * 2.752.512` | 16.515.072 | 15,750 |
| **slab VRAM totale** | `gate + up + down` | **42.467.328** | **40,500** |

Un expert slot è:

`2 * 2.162.688 + 2.752.512 = 7.077.888 B = 6,75 MiB`.

Quindi:

`42.467.328 / 7.077.888 = 6,000 slot`.

Risposta numerica: lo slab transiente occupa **42.467.328 B (40,5 MiB)**,
equivalenti esattamente a **6 slot residenti**. Rispetto alla cache misurata da
140 slot, l'equivalenza aritmetica è `140 -> 146`, cioè `+4,286%` di slot. È
un'equivalenza di capacità; questo mandato non misura un nuovo hit rate.

### Lifetime: una volta, non per layer

La cache è un unico oggetto statico globale
`g_moe_expert_cache` (`ds4-p4a/ds4_cuda.cu:28364`). Se configurazione e
geometria coincidono, `cuda_moe_expert_cache_prepare()` restituisce lo stesso
oggetto già allocato (`ds4-p4a/ds4_cuda.cu:37328-37374`). Le allocazioni dello
slab avvengono nel solo prepare sopra citato e sono liberate dal release
globale (`ds4-p4a/ds4_cuda.cu:36163-36175`).

Le richieste dei diversi layer scrivono slice indicizzate per route nello
stesso slab (`ds4-p4a/ds4_cuda.cu:39910-39926`) e poi pubblicano puntatori alle
medesime tre basi (`ds4-p4a/ds4_cuda.cu:39972-39992`). Dunque lo slab è
allocato **una sola volta per cache/backend**, non 43 volte. Il prodotto
ipotetico per 43, `1.826.095.104 B = 1.741,5 MiB`, non è l'allocazione eseguita
dal codice.

## 2. Percorso CPU

Nel sorgente corrente esistono due percorsi distinti.

### Backend CPU di riferimento

Il decode CPU entra da `forward_token_raw_swa_cpu_decode_scratch()` quando il
backend della sessione è `DS4_BACKEND_CPU`
(`ds4-p4a/ds4.c:20846-20866`). L'FFN chiama
`layer_routed_moe_one_prealloc()` (`ds4-p4a/ds4.c:6906-6917`).

Per ogni token/layer questo percorso:

1. seleziona sei esperti e calcola i router weights;
2. quantizza la riga F32 di input in Q8_K;
3. calcola gate e up, applica clamp, SwiGLU e router weight;
4. quantizza il mid in Q8_K;
5. calcola e accumula i down dei sei esperti.

La sequenza è visibile in `ds4-p4a/ds4.c:6572-6605`. Le matrici sono lette
direttamente tramite i puntatori del model mapping
(`ds4-p4a/ds4.c:4601-4607`): non usa lo slab CUDA.

Il contratto delle routine effettivamente chiamate è ristretto:

- gate/up **IQ2_XXS**; il tipo viene verificato esplicitamente
  (`ds4-p4a/ds4.c:4700-4713`);
- down **Q2_K**; il tipo viene verificato esplicitamente
  (`ds4-p4a/ds4.c:4817-4827`);
- attivazioni F32 quantizzate internamente in Q8_K.

Questo percorso non è chiamato dal normale decode CUDA, che passa invece a
`ds4_gpu_routed_moe_one_tensor()` o alle varianti mixed
(`ds4-p4a/ds4.c:11862-11975`).

### Lane CPU raggiungibile dal decode CUDA

Il file CUDA corrente contiene anche la lane opt-in G132. È **OFF di default**:
si abilita soltanto con `DS4_G132_CPU_LANE=1`
(`ds4-p4a/ds4_cuda.cu:48239-48244`); l'init CUDA la inizializza
(`ds4-p4a/ds4_cuda.cu:8471-8493`).

Oggi è raggiungibile dal decode CUDA, ma solo dentro
`ds4_gpu_routed_moe_mixed_q1_0_one_tensor()`, chiamato dal ramo mixed Q1_0
(`ds4-p4a/ds4.c:11862-11907`). Non è agganciata al percorso generale
`ds4_gpu_routed_moe_one_tensor()`.

La lane ammette soltanto route exact-IQ2 già in RAM negli stati warm o
probation, con slot arena pinned e riservabile
(`ds4-p4a/ds4_cuda.cu:48432-48504`,
`ds4-p4a/ds4_cuda.cu:49268-49346`). Il default è al massimo tre esperti per
layer e il massimo viene limitato dal numero di worker
(`ds4-p4a/ds4_cuda.cu:48290-48317`).

Per le route ammesse:

- copia l'input F32 `4096` GPU -> host pinned
  (`ds4-p4a/ds4_cuda.cu:48642-48665`);
- esegue su worker CPU gate/up IQ2_XXS, SwiGLU e down Q2_K direttamente dai
  puntatori RAM residenti (`ds4-p4a/ds4_cuda.cu:48141-48194`);
- pesa e somma le route in host, copia un solo parziale F32 da 4096 elementi
  host -> GPU e lo accumula nell'output CUDA
  (`ds4-p4a/ds4_cuda.cu:48668-48730`);
- in caso di errore ricade sul percorso IQ2 GPU
  (`ds4-p4a/ds4_cuda.cu:49538-49565`).

Anche qui il formato è **IQ2_XXS gate/up + Q2_K down**: il forward interpreta
direttamente quei due block type (`ds4-p4a/ds4_cuda.cu:48163-48188`) e il
prepare verifica le relative row size
(`ds4-p4a/ds4_cuda.cu:48539-48554`). Non esiste un dispatch CPU per IQ1_S,
Q1_0 o Q4_K in questa lane.

### Cosa manca per dirottare i soli passaggi transienti generali

Il resolver generale identifica già se un miss viene da snapshot/probation e
ottiene i tre puntatori RAM (`ds4-p4a/ds4_cuda.cu:39265-39273`). Oggi, però,
anche questi puntatori vengono copiati in `route_transient_*`
(`ds4-p4a/ds4_cuda.cu:39880-39926`) e poi pubblicati come route GPU
(`ds4-p4a/ds4_cuda.cu:39972-39992`).

Per dirottare **solo** quelle route, senza cambiare l'ammissione, servono
quindi questi collegamenti mancanti:

1. classificare nel resolver generale le route non residenti in VRAM ma già
   servibili da RAM, lasciando invariata la decisione di stato;
2. acquisire e mantenere una reader reservation dello slot RAM fino alla fine
   del calcolo CPU, come fa già
   `cuda_g132_cpu_lane_reserve_resident_iq2_ptrs()`;
3. escludere quelle route dalla copia e dalla pubblicazione
   `route_transient_*`, passando alla lane soltanto puntatori, expert id e
   router weight;
4. riusare il bridge input D2H e il join del parziale H2D già presenti nella
   lane;
5. per transienti letti da SSD nei `route_host_*`, estendere il contratto della
   lane, che oggi rifiuta slot pageable/non-arena
   (`ds4-p4a/ds4_cuda.cu:48482-48497`), e impedire il riuso dello staging host
   fino al completamento CPU;
6. mantenere il vincolo IQ2_XXS/Q2_K oppure aggiungere kernel CPU distinti per
   ogni altro formato; oggi tali kernel non esistono nella lane.

Sono integrazioni di esecuzione e lifetime; non richiedono di cambiare soglie,
stati o vittime della politica di ammissione.

### FLOP e competitività sulla CPU misurata

Per un expert, contando una moltiplicazione e un'addizione come 2 FLOP:

- gate `4096 x 2048`: `2 * 4096 * 2048 = 16.777.216 FLOP`;
- up `4096 x 2048`: `16.777.216 FLOP`;
- down `2048 x 4096`: `16.777.216 FLOP`;
- totale: **50.331.648 FLOP/expert = 50,33 MFLOP/expert**.

Sei esperti richiedono **301.989.888 FLOP** per layer/token, esclusi
quantizzazione, clamp, sigmoid/SwiGLU, weighting e copie.

L'hardware locale documentato è Ryzen 7 5800X + RTX 3060 12 GB
(`docs/02_models.md:82`). Il benchmark già presente nel workspace sul medesimo
percorso riporta, a mapping caldo e 12 thread, `full_expert_mean` da **0,962 a
1,072 ms/expert** (`ds4-p4a/g7_runs/g29_gate_layer10_warm5.stderr.log:10`,
`:18`, `:23`, `:28`, `:33`). Le serie calde dei sei esperti riportano
**5,629-5,845 ms** totali (`ds4-p4a/g7_runs/g29_gate_layer10_warm5.stderr.log:19`,
`:24`, `:29`, `:34`).

Confronto diretto con `0,32 ms/expert`:

- miglior expert CPU misurato: `0,962 / 0,32 = 3,006x` più lento;
- throughput aritmetico: `52,32 GFLOP/s` CPU contro `157,29 GFLOP/s`
  equivalenti a `0,32 ms`.

Risposta: **no, questa CPU non è competitiva in latenza isolata per expert**
con i circa `0,32 ms/expert` di copia+kernel. Non è presente un run che misuri
il guadagno end-to-end della sovrapposizione G132; non viene dedotto un numero
end-to-end da dati non misurati.

## 3. Strumentazione minima proposta

`slabprobe.patch` aggiunge solo:

- flag `DS4_CUDA_TRANSIENT_SLAB_PROBE=1`, OFF di default;
- una riga a decode-start, dopo l'eventuale grow definitivo della cache;
- una riga a request-end.

Formato:

```text
ds4: [transient-slab] phase=decode-start bytes=42467328 cache_slots=6
ds4: [transient-slab] phase=request-end bytes=42467328 cache_slots=6
```

Il probe calcola i byte dai puntatori realmente allocati e dalle geometrie
registrate nella cache; gestisce sia layout packed sia le tre allocazioni
separate. Non chiama `cudaMemGetInfo`, non modifica sizing, ammissione,
residenza o copie.

Verifica eseguita senza applicare il diff:

```text
git -C ds4-p4a apply --check ../.microbench/transient/slabprobe.patch
exit code: 0
```
