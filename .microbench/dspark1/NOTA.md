# DSPARK-1 — kernel CPU Q4_K routed e forward CPU NextN

Data: 2026-07-29. Tree bersaglio: `ds4-p4a`. Revisione 2 (integra la verifica incrociata
del secondo passaggio; storico in fondo, sez. "Revisioni").

## Esito

`dspark1.patch` aggiunge soltanto codice non chiamato in `ds4-p4a/ds4.c`
(**748 inserimenti, zero rimozioni**). Non aggiunge flag di ingaggio, non modifica
loader, dispatcher CUDA, ammissione, residenza, cache del backbone o ciclo
speculativo. A flag spenti non esiste alcun branch nuovo nel percorso caldo: i punti
d'ingresso sono `static DS4_MAYBE_UNUSED` senza alcun call-site, quindi il codice
nuovo non e' raggiungibile da NESSUN percorso finche' i pezzi 3-5 non lo agganciano.

La patch contiene i soli pezzi 1-2:

1. kernel CPU routed Q4_K x Q8_K:
   - decodifica scale/min Q4_K uguale al golden dequantizer
     (`reap-loop-ledger-main/tools/mtp_q4k_requant.c:600-637`);
   - dequantizzazione fusa nel dot, senza riga F32 materializzata (il termine
     `-dmin*min` usa i `bsums` del Q8_K, stessa identita' del quantizzatore in-tree
     `ds4_quantize_row_q8_K`);
   - gate/up accoppiati e down accumulato sui 6 esperti selezionati;
   - parallelismo per righe tramite `ds4_parallel_for` (pool G132), stessa
     scomposizione slot/riga, stesso clamp e stesso `silu(gate)*up*peso` dei kernel
     expert IQ2/Q2 di riferimento;
   - una sola prequant Q8_K dell'ingresso, riusata da gate/up, e una prequant
     per ciascuno dei 6 mid riusata dal down (buffer scratch esistenti
     `routed_xq`/`routed_midq`/`routed_mid_all`, gia' dimensionati per questo).
2. forward CPU chiamabile del blocco NextN a un layer:
   - combinatore `enorm(token_embedding) -> e_proj` piu'
     `hnorm(prev_hc[h]) -> h_proj` per ciascuna delle 4 corsie HC;
   - HC attention pre, attenzione dense del modulo con KV raw SWA-128 propria,
     HC attention post;
   - HC FFN pre, router appreso 256->top-6, 6 esperti routed Q4_K, shared Q8_0
     (riusa `layer_shared_ffn_one_decode_scratch` senza modificarla), somma e
     HC FFN post;
   - HC head MTP e `mtp.0.norm`;
   - output `head_hidden[4096]` pronto per la matrice vocab Q8_0 del modello base
     residente su GPU, piu' `out_hc[4*4096]` per il draft ricorsivo.

## Stato del tree alla consegna (leggere prima di applicare)

La patch e' GIA' APPLICATA al tree: alle 07:55:05 del 29/07 e' stata composta in
`ds4-p4a/ds4.c` secondo la convenzione di campagna, con snapshot pre-applicazione
`.microbench/ds4_c.pre_dspark1.c` (e gemello `ds4_cuda.pre_dspark1.cu`, non toccato
dalla patch). Catena di verifica eseguita:

- `git apply --check dspark1.patch` su copia dello snapshot pre-dspark1: **PASS**;
- applicazione sulla copia -> risultato **byte-identico** all'attuale
  `ds4-p4a/ds4.c` (stessi SHA-256, sez. finale);
- `git apply --reverse --check dspark1.patch` sul tree attuale: **PASS** (il tree
  contiene esattamente la patch, ne' piu' ne' meno).

Quindi NON riapplicare sul tree corrente (fallirebbe: il contenuto c'e' gia').
Il requisito "git apply --check pulito" vale contro la baseline
`ds4_c.pre_dspark1.c`, cioe' il tree di campagna con lane+kernel+econ+SCOPED+DOV
gia' composti. Coordinate: le righe citate come "baseline" si riferiscono allo
snapshot; il tree attuale e' spostato di +68 dopo l'hunk 1, +401 dopo l'hunk 2,
+748 dopo l'hunk 3.

## Contratto esatto del forward

La funzione aggiunta e' (tree attuale ds4.c:9630):

```c
ds4_mtp_cpu_forward_nextn_q4_k(
    state, base_model, base_weights, mtp_model, mtp,
    prev_hc, token, pos, out_hc, head_hidden, telemetry);
```

`prev_hc` e' lo stato HC F32 finale `4 x 4096` del token appena committato per il
primo draft (su CPU arrivera' col D2H di `cur_hc`, 64 KB/token — pezzo 3). Nei draft
successivi e' `out_hc` del forward NextN precedente (ping-pong come
`mtp_state_hc`/`mtp_next_hc` su GPU). `token` e' il token vero noto al primo
ingresso (campionato in testa al loop server, `ds4_server.c:7466`); nella catena
autoregressiva e' il draft precedente. `pos` avanza di 1 per draft. Questo replica
il contratto corrente di `metal_graph_eval_mtp_draft_from_hc`
(baseline `ds4-p4a/ds4.c:15286-15402`) e la ricorsione (baseline `21227-21250`).

La testa LM non e' nel GGUF MTP: embedding e matrice output sono condivisi col
target. Percio' il pezzo 2 termina intenzionalmente a `head_hidden` (dopo
`mtp.0.norm`, specchio di `metal_graph_encode_output_head_mtp` baseline
`12474-12514` senza la GEMV vocab), seguendo `DSPARK.md:203-206`; H2D, GEMV
vocab/top-1 GPU e relativo innesto appartengono ai pezzi successivi.

Lo stato CPU (`ds4_mtp_cpu_state`, init/reset/free a ds4.c:9596/9608/9614 del tree
attuale) possiede soltanto la KV raw del modulo, cap 128; nessuna funzione e'
collegata a `ds4_engine`. Rollback della lunghezza KV dopo verifica e gestione
accepted-prefix restano fuori mandato. Avvertenza progettuale per il pezzo 4:
il rollback GPU e' un contatore su cache ad anello (`mtp_n_raw` +
`DS4_MTP_KEEP_ACCEPTED`, baseline `21214-21225`); la `ds4_layer_cache` CPU e' una
finestra a scorrimento (`kv_cache_push_raw` fa memmove quando piena), quindi a
finestra piena i push speculativi distruggono le righe piu' vecchie e il rollback a
contatore NON basta: serviranno o una variante ad anello o uno snapshot della
finestra (<=128x512 F32 = 256 KB). Qui e' fornita la primitiva `reset()`.

## Router e semantica del blocco

Il router MTP (`mtp_cpu_router_select`) usa il peso plain del proprio GGUF, che puo'
essere F32 (validatore: `tensor_expect_plain_layout`, baseline ds4.c:3086); percio'
usa `matvec_any` e non l'helper backbone che assume F16. Non usa hash routing e non
applica maschere REAP del backbone: coerente col percorso GPU, dove
`use_hash = (ffn_gate_tid2eid != NULL)` (baseline ds4.c:11996) e il bind MTP lascia
`tid2eid` NULL (baseline 3629-3667); il bias REAP e' registrato solo per tensori del
backbone. Aritmetica identica al riferimento: `probs = sqrt(softplus(logit))`,
selezione su `probs + exp_probs_b`, `topk_desc`, pesi normalizzati con clamp
`6.103515625e-5` e scala `DS4_EXPERT_WEIGHT_SCALE` (baseline 6226-6237, 6601-6638).

Stessa ragione per l'unica ri-implementazione di un helper esistente:
`mtp_cpu_hc_pre_from_state_one_scratch` duplica `hc_pre_from_state_one_scratch`
(baseline 5341-5372) sostituendo `matvec_f16` con `matvec_any`, perche' gli
`hc_attn_fn`/`hc_ffn_fn` del file MTP sono plain F32/F16. Sinkhorn, eps e copie
post/comb identici; nessuna funzione esistente modificata.

L'attenzione e' presente nel GGUF ispezionato ed e' quindi eseguita. Il forward
usa l'indice logico dense `1`, come il percorso GPU MTP corrente
(baseline `15359-15369`): `ds4_layer_compress_ratio(1)=0` -> niente
compressore/indexer, parametri RoPE base e KV raw SWA. La catena attenzione e' la
stessa di `layer_forward_raw_swa_one` (baseline 8827-8992) nel ramo ratio==0,
inclusi fp8-quantize della riga KV prima del push e softmax sink-aware.

## Telemetria

`ds4_mtp_cpu_telemetry` espone per ogni draft:

- `total_ms`;
- `q8_prequant_ms` (quantizzazioni Q8_K del percorso routed: 1x input 4096 +
  6x mid 2048);
- `q4_dequant_ms`;
- `q4_matvec_ms` (passata gate/up sui 6 esperti + passata down accumulata);
- `other_ms`.

`q4_dequant_ms` e' zero per progetto: la decodifica/dequantizzazione Q4_K e' fusa
nel dot e il suo costo e' dentro `q4_matvec_ms` (la voce esiste perche' la
scomposizione dequant/matvec/altro chiesta dal mandato resti esplicita e onesta:
zero perche' fusa, non perche' non misurata). `other_ms` comprende proiezioni dense
Q8/plain, norm, attenzione, router, shared expert e HC (incluse le quantizzazioni
Q8_0 interne a e_proj/h_proj/shared). Non viene aggiunto logging ne' un nuovo env
flag. Il puntatore telemetria e' opzionale: con NULL i timer del routed sono saltati.

Costo atteso, NON misurato (il mandato vieta build/bench): routed Q4_K
6 x 14.155.776 B = 84,9 MB/draft -> 2,8-4,2 ms; denso Q8 ~176 MB -> 5,9-8,8 ms;
classe 12-16 ms/draft con testa su GPU (DSPARK.md sez. 2). Nota: i dot K-quant del
tree hanno solo il ramo NEON sotto ifdef, su x64 girano scalari; il kernel nuovo e'
scalare come i riferimenti. Se il bench del pezzo 5 indichera' il routed Q4K come
collo, un ramo AVX2 del dot e' il primo candidato — non prima di una misura.

## Convivenza con l'agente shared1 (ancore hunk e rimappatura)

I 3 hunk sono blocchi contigui autosufficienti agganciati a confini di funzione
stabili; la patch non modifica alcuna riga esistente, quindi il conflitto e'
possibile solo sulle righe-ancora di contesto. Coordinate BASELINE:

| hunk | contenuto | inserito dopo | prima di | ancore (baseline) |
|---|---|---|---|---|
| 1 (+68) | scale/min + dot Q4_K | fine `ds4_vec_dot_q2_K_q8_K` | `ds4_vec_dot_iq2_xxs_q8_K` | 2334-2336 / 2338-2340 |
| 2 (+333) | telemetria, kernel Q4K, router MTP, moe-one | fine `layer_topk_selected_experts_from_probs` | `ds4_reap_mask_validate_selected` | 6636-6639 / 6640-6642 |
| 3 (+347) | stato + forward NextN | fine `layer_forward_raw_swa_one` | `output_logits_one_decode_scratch` | 8991-8993 / 8994-8996 |

I punti caldi presumibili di shared1 (shared Q8 CPU baseline 6094-6142; join GPU
baseline 12233-12282; lane in ds4_cuda.cu) NON coincidono con le ancore. Il pezzo 2
CHIAMA `layer_shared_ffn_one_decode_scratch` senza toccarla: se shared1 ne cambiasse
la firma, l'unica chiamata nuova da aggiornare e' in `mtp_cpu_layer_ffn_one`
(tree attuale ds4.c:9475). Poiche' la patch e' gia' applicata, un diff di shared1
preso dal tree attuale inglobera' queste righe come contesto: e' lo stato atteso.

## Correzioni/imprecisioni del dossier sui punti toccati (file:riga)

- Il bersaglio 10-13 ms/draft e 70-90 ms/ciclo k=7 non e' quello Q4_K:
  `DSPARK.md:94` assegna 10-13 ms al Q1_0 e 12-16 ms al Q4_K;
  `DSPARK.md:98-100` assegna 70-90 ms al Q1_0 e 85-115 ms al Q4_K.
  Questa patch non dichiara di aver raggiunto un costo: niente build/bench.
- `DSPARK.md:196-197` cita `tools/mtp_q4k_requant.c`, ma nel workspace corrente il
  file esiste come `reap-loop-ledger-main/tools/mtp_q4k_requant.c`; non esiste un
  omonimo sotto `tools/` alla radice.
- `DSPARK.md:115` (e `ANALISI_FABLE.md:114-116`): il range citato "ds4.c:15404-15425"
  per `metal_graph_eval_mtp_draft_from_hc` e' in realta' il WRAPPER
  `metal_graph_eval_mtp_draft` (baseline 15404-15425), che passa `g->cur_hc` alla
  vera `_from_hc` (baseline 15286-15402). La sostanza (ingresso = cur_hc + token)
  resta corretta.
- Verificati CORRETTI sui punti toccati: raw_window/SWA baseline 10879-10886;
  drafting ricorsivo 21227-21250; shared Q8 CPU 6094-6141; predicato loader
  2907-2912 (Q4_K incluso, Q1_0 omesso — non toccato, e' il pezzo 3);
  14,16 MB/expert Q4_K (ricalcolo: 3 x 4.718.592 B = 14.155.776 B).

## Verifiche eseguite

- `git apply --check` sulla baseline pre-dspark1: PASS; `--reverse --check` sul
  tree attuale: PASS; applicazione su copia -> SHA identico al tree attuale.
- `git apply --numstat`: `748  0  ds4-p4a/ds4.c` (patch puramente additiva).
- Golden Q4_K: il dot fuso sul vettore di
  `reap-loop-ledger-main/tools/mtp_q4k_requant.c:682-706` produce `6336`, uguale
  al dot della riga dequantizzata golden (`6336`) [rev. 1]; in rev. 2 verifica
  strutturale indipendente dell'identita' scale/min e del termine bsums.
- Verifica simbolo-per-simbolo di tutte le firme, i campi scratch e le costanti
  usate contro il sorgente (scratch 204-260 e init 7513-7586; ds4_layer_cache
  7460-7476; kv push 7696; attention rows 5954; rope 5815; hc 5243-5443; router
  6226-6280 e 6601-6638; kernel di riferimento 4766/4864/5019/6761; bind+validate
  MTP 3629-3667/3053-3097; head GPU 12474-12514 e CPU 9354-9377; eval GPU
  15286-15425; loop draft 21179-21263 — coordinate baseline). Ordinamento delle
  definizioni verificato: ogni simbolo usato e' definito prima del punto di
  inserzione che lo usa. Zero collisioni di nomi sulla baseline.
- Nessuna compilazione, nessun server, nessun accesso in scrittura a `D:\`.

## Revisioni

- Rev. 1 (07:41): consegna iniziale — patch 745 inserimenti, SHA
  `e1af0a24bc03275b7077aee87a09f949ffa46740877817dc002b4a865aab5f73`.
- Rev. 2 (adesso): verifica incrociata integrale del secondo passaggio + UNA
  modifica sostanziale a `layer_routed_moe_q4_k_one_prealloc`: aggiunta la guardia
  `down_in != DS4_N_FF_EXP` (con commento), perche' i buffer scratch
  `mid_all/xq/midq` sono dimensionati su `DS4_N_FF_EXP` e i kernel di riferimento
  hanno la stessa guardia esplicita (baseline ds4.c:6778). Patch: 748 inserimenti.
  E' la versione applicata al tree alle 07:55:05.

## SHA-256

```text
.microbench/dspark1/dspark1.patch  (rev. 2, CRLF come ds4.c)
f4f5a08544e357f8f18bf58392f4eb0438c8441cdb5ee3c92f9af97bd4e34b6b

ds4-p4a/ds4.c PRIMA della patch (= .microbench/ds4_c.pre_dspark1.c, 21761 righe)
3be7ce5fbbbf83ba5ea33bf73a598e27b10255959c0000b6eecbaa938821e495

ds4-p4a/ds4.c DOPO la patch (= tree attuale, 22509 righe)
f658e09c1c01a0bc5ad71e14058e50ba9dc95a29fd390e435acc8071698395fb
```
