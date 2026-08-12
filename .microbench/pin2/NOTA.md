# PIN2 — pin del backbone rebasato + ricostruzione ridotta dello slab; indexer-da-RAM misurato e scartato

Data: 2026-07-29. Nessuna compilazione, nessun server, `D:\` mai toccato, nessun
file del tree modificato (deliverable solo in `.microbench/pin2/`).

Mandato: due strade dietro flag separati. **(A)** rebase di
`.microbench/backbone/pin.patch` (28/7, non applica piu') sul tree corrente,
con il miglioramento "dopo la cessione dello slab ricostruiscilo piu' piccolo".
**(B)** indexer servito da RAM (`DS4_CUDA_INDEXER_HOST=1`) — ma SOLO dopo aver
misurato i byte dell'indexer letti per token; se riletto interamente,
dichiararla non conveniente e consegnare solo la A.

## Esito in breve

- **B: MISURATA E NON CONVENIENTE.** I pesi dell'indexer (`indexer_f16`) sono
  riletti al **100% ogni token** quando l'indexer e' attivo (pos >= 2051):
  363.331.584 B/token, GEMV denso sull'intera matrice, nessun accesso
  selettivo. L'accesso sparso della DS4-attention sta nella selezione top-k
  della K-cache, non nei pesi dell'indexer. Servirli da RAM costerebbe
  >= 10-14 ms/token PERMANENTI (numeri misurati del microbench zerocopy, caso
  migliore) per liberare al massimo 346,5 MiB. La strada A libera 945 MiB
  (slab 140) una tantum a costo di regime zero. **Consegnata solo la A**,
  come il mandato prescrive per questo esito. Il flag `DS4_CUDA_INDEXER_HOST`
  NON esiste nella patch: non e' stato costruito apposta.
- **A: CONSEGNATA.** `pin2.patch` (+328/-14, solo `ds4-p4a/ds4_cuda.cu`),
  `git apply --check` pulito sul tree CORRENTE, flag `DS4_CUDA_PIN_BACKBONE=1`,
  default 0 = neutrale. Rispetto al disegno del 28/7: stesso impianto
  (pin nel selettore vittime -> cessione dell'intero slab -> exact
  selected-load -> `PIN ESCAPE` fail-open), piu' la **ricostruzione a
  capacita' dimezzata** alla prima `prepare()` dopo lo shed, piu' tre
  correzioni di sicurezza/misurabilita' dichiarate al §4.

---

## 1. Strada B — la misura (fatta PRIMA, come da mandato)

### 1.1 Cosa e' esattamente "la parte che si allarga"

L'etichetta di trasporto `indexer_f16` (quella gia' privilegiata da
`DS4_CUDA_STREAM_HOT_RESERVE_MB`, base `ds4_cuda.cu:8526-8527`) copre
esattamente DUE famiglie di tensori, e nient'altro:

| tensore | dtype/dims | B/layer | layer | residenza totale |
|---|---|---:|---:|---:|
| `blk.*.indexer.attn_q_b` | F16 1024 x 8192 | 16.777.216 | 21 | 352.321.536 |
| `blk.*.indexer.proj` | F16 4096 x 64 | 524.288 | 21 | 11.010.048 |
| **totale `indexer_f16`** | | | | **363.331.584 B = 346,5 MiB** |

Prova (tree corrente): l'unico costruttore dell'etichetta e'
`ds4_gpu_matmul_f16_indexer_tensor` (`ds4_cuda.cu:22804-22816` ->
`matmul_f16_tensor_labeled(..., "indexer_f16")`), chiamato SOLO da
`ds4.c:13597-13601` (attn_q_b: in_dim=q_rank=1024, out_dim=64x128=8192) e
`ds4.c:13615-13619` (proj: in_dim=4096, out_dim=64). Dei "536 MiB" citati nel
mandato, questi 346,5 MiB sono la sola parte file-backed e streammabile: il
resto (score buffer, K-cache compressa dell'indexer, workspace attenzione) e'
dato CALCOLATO, non servibile da RAM con un flag di residenza pesi.

### 1.2 Quando si accende

Guardia a `ds4.c:13580-13581`: `layer_n_comp[il] > decode_top_k`, con
`decode_top_k = DS4_N_INDEXER_TOP_K = 512` (`ds4.c:124`, `ds4.c:13091-13093`).
`layer_n_comp` cresce di 1 ogni ratio=4 token -> soglia a pos >= 2051: e' il
cliff gia' documentato (`.microbench/atlante/REVISIONE.md`: primo token
22.791 ms a pos=2051, poi ~26 ms; `fd-cache load 0 -> 1.066`). A ctx 150k
(campagna) l'indexer e' attivo per TUTTA la generazione.

### 1.3 Byte letti per token: TUTTI, ogni token

In decode `n_tok==1`, quindi `matmul_f16_tensor_labeled` prende il puntatore
all'INTERO tensore (`weight_bytes = out_dim * in_dim * 2`,
`ds4_cuda.cu:22729-22735`) e lancia il kernel
`matmul_f16_ordered_chunks_kernel` (default per n_tok==1,
`ds4_cuda.cu:22782-22785`; corpo `ds4_cuda.cu:17815-17845`): un blocco per
riga di output, ogni blocco legge `wr[i]` per i in [0, in_dim) -> **ogni byte
del tensore letto esattamente una volta per token**. Idem per il ramo
`matmul_f16_kernel` (17767-17793) e per quello seriale. Non esiste alcun ramo
che legga un sottoinsieme delle righe: la selezione top-k avviene DOPO, sugli
score (`ds4_gpu_indexer_topk_tensor`, `ds4.c:13645-13649`), non sui pesi.

**Risposta alla domanda del mandato: 363.331.584 B/token = 100% della
residenza `indexer_f16`, ogni token con pos >= 2051.** Il profilo e' identico
al backbone (99,84%, `.microbench/backbone_bytes/MISURA.md` riga 31-32, che
gia' listava questi due tensori al 100% — confermato sul tree corrente dove
le righe ds4.c sono slittate da 11513/11531/11549 a 13581/13597/13615).

### 1.4 Il conto economico (numeri misurati, non stimati)

Da `.microbench/zerocopy/results.txt` (RTX 3060, due run riproducibili):

| forma | banda misurata | 363,3 MB/token costano |
|---|---:|---:|
| lettura da VRAM (S1) | 89,4 GB/s | 4,1 ms/token (oggi) |
| zero-copy da RAM pinned (S2a) | 25,86 GB/s | 14,1 ms/token |
| copy H2D poi compute (S3a/S3b) | 17,6-19,8 GB/s | 18,4-20,6 ms/token |
| H2D grezzo (S4) | 26,33 GB/s | 13,8 ms/token (solo filo) |

Quindi **>= +10 ms/token netti permanenti nel caso MIGLIORE** (zero-copy alla
banda del microbench). Ma il caso migliore non e' nemmeno raggiungibile senza
riscrivere il kernel: `ordered_chunks` fa leggere a ogni thread un chunk
CONTIGUO di in_dim/32 half -> i 32 thread di un warp toccano indirizzi
distanti ~512 B -> transazioni non coalescenti, che su PCIe (zero-copy)
crollano ben sotto i 25,86 GB/s del bench (che usava blocchi da 256 thread
coalescenti). L'alternativa (staging H2D per token) ripaga il costo S3 e
rioccupa comunque VRAM di atterraggio.

Contro: la strada A libera 945,0 MiB (slab 140 slot, 990.904.320 B) in un
colpo solo a costo di regime nullo, e la misura C1 di stamattina (shared-CPU
che libera 1.096,5 MiB -> 586 sfratti, nessun precipizio) prova che ~1 GiB
liberato BASTA. **B non conveniente: dichiarata e non costruita.**

---

## 2. Strada A — cosa consegna la patch

Flag: `DS4_CUDA_PIN_BACKBONE=1` (memoizzato, `:7928-7936`). Tutto il resto a
flag spento e' morto (§5). Righe «:N» = file DOPO la patch.

### 2.1 Il pin (rebase fedele del disegno 28/7)

Nel ciclo di sfratto di `cuda_model_stream_alloc` (`:8536-8605`): quando
`cuda_model_pick_victim()` designa una vittima `pinned` (backbone),

1. la vittima e' bloccata (`PIN blocked_backbone`, rate-limited 8 poi 1/256);
2. si cede l'INTERO slab resident-expert via
   `cuda_vram_pin_shed_expert_cache()` (`:37040-37135`) e si riprova
   l'allocazione (`continue`);
3. se lo slab non puo' cedere (assente, gia' ceduto, worker non quiesciuto,
   job in volo, sync fallita): `PIN ESCAPE` dichiarato e fail-open sul
   backbone (il runtime non ha un backend CPU per i pesi dense mancanti);
4. `vi < 0` (nessuna vittima): prima si tenta lo shed, poi `PIN EXHAUSTED`
   + NULL al chiamante (fallback originario).

L'ordine di cessione resta: pool event-fenced -> range expert streamed non
pinned (contati in `pin_expert_range_ceded`) -> slab intero -> exact
selected-load -> fail-open. Il campo `what` di
`cuda_vram_prio_account_eviction` e' rinominato `requester` e la riga ANOMALY
espone `victim_category=backbone victim_offset=` (`:8241-8262`): i vecchi
conteggi per `q8_0`/`attn_out_a` erano richiedenti, non vittime (correzione
gia' motivata in `.microbench/backbone/ANALISI.md`).

Nel ramo `!G73` di `routed_moe_launch_impl` (`:48098-48127`), SOLO con shed
attivo e MAI per nested-residual GPU-cache, il refusing-fallback si apre
sull'exact selected-load gia' collaudato dal ramo G73 (stesso disegno 28/7).

### 2.2 Il miglioramento richiesto: ricostruzione a capacita' ridotta

Il disegno 28/7 lasciava la richiesta senza cache dopo lo shed. Ora:

- lo shed registra `rebuild_target = capacita_ceduta / 2` (`:37104`);
- la prima `cuda_moe_expert_cache_prepare()` successiva (chiamata per-layer
  dai percorsi routed) NON torna piu' NULL: prosegue e il sizing ordinario
  (riserve incluse) viene **clampato al target** (`:38848-38856`), cosi' la
  capacita' nei log e' quella vera;
- successo: `PIN rebuild result=ok capacity=... target=... requested=...`
  (`:39362-39377`), `shed=0`, percorso routed di nuovo ordinario. Il
  config-match della prepare fa SOPRAVVIVERE la capacita' ridotta alle
  richieste successive (nessun release a fine richiesta): e' la
  configurazione misurata come utile (140-220 slot), non un ripiego;
- fallimento (sizing a zero `:38860-38870` o retry di allocazione esauriti
  `:39425-39434`): `PIN rebuild result=failed reason=...`, target azzerato
  -> **UN tentativo per shed, non uno per layer**; la richiesta continua in
  exact selected-load come nel disegno originale;
- un eventuale NUOVO shed sulla cache ridotta dimezza ancora: spirale
  decrescente che termina a 0 (exact-streaming), mai ping-pong;
- a request-end (`:30826-30835`) si riarma solo lo stato di shed non
  consumato: se la ricostruzione e' avvenuta non c'e' nulla da riarmare.

Con `DS4_CUDA_EXPERT_CACHE_GROW=1` la ricostruzione mid-decode passa dagli
stessi cancelli della prepare (decode_started=1 -> il blocco two-phase non
scatta); in prefill con GROW lo slab non esiste ancora e lo shed e' un no-op
dichiarato (ESCAPE fail-open, come oggi il churn di prefill).

### 2.3 Tre correzioni dichiarate rispetto al disegno 28/7

1. **Drain una-tantum di stream 0 prima dei `cudaFree` dello slab**
   (`:37077-37098`). I kernel MoE del layer corrente sono lanciati async su
   stream 0 e leggono gli slot dello slab; `release()` quiesce worker e
   upload stream, NON stream 0. Liberare lo slab con kernel in volo sarebbe
   use-after-free device. Lo sfratto ordinario evita il sync col pool
   event-fenced, ma lo slab non passa dal pool. Costo: un drain per shed
   (evento raro, 1-2 per richiesta), non per token. Sync fallita = shed
   bloccato, dichiarato, fail-open.
2. **Rinvio con job di route in volo** (`:37047-37068`):
   `route_submitted_sequence != route_completed_sequence` -> shed rinviato
   (`PIN degrade result=deferred`, contatore `pin_shed_deferrals`).
   Sul tree corrente la finestra begin->finish non contiene stream_alloc
   (verificato: i `cuda_model_range_ptr("moe_*")` stanno sui rami fallback
   mutuamente esclusivi con la route attiva, e `prepare_selected` si
   auto-disabilita con expert cache configurata, base `:43573-43576`),
   quindi il ramo non dovrebbe MAI scattare: e' una cintura contro derive
   future. Il consumer e lo shed vivono sullo stesso thread di decode, e il
   release gia' esistente cancella/join-a il worker prima dei free.
3. **Rate-limit (8 poi 1/256) su `PIN ESCAPE` e `PIN EXHAUSTED`**: nel regime
   post-shed con pressione residua sono eventi PER SFRATTO; il disegno 28/7
   li stampava senza limite e a 188k sfratti (C2) il log stesso avrebbe
   falsato il braccio ON.

### 2.4 Telemetria

`[vram-prio]` (`:30646-30700`, emessa identica in entrambi i bracci) aggiunge:
`pin_backbone` (stato flag), `pin_backbone_blocked`, `pin_expert_range_ceded`,
`pin_expert_cache_sheds/slots_ceded/resident_ceded/bytes_ceded`,
`pin_expert_cache_shed_failures`, `pin_shed_deferrals`,
`pin_expert_cache_rebuilds`, `pin_rebuild_slots` (target corrente),
`pin_exact_stream_fallbacks`, `pin_backbone_failopen`, `pin_no_victim`.
Righe evento: `PIN blocked_backbone`, `PIN degrade result=ok|blocked|deferred`,
`PIN rebuild result=ok|failed`, `PIN degrade category=exact-streaming`,
`PIN ESCAPE`, `PIN EXHAUSTED` — ognuna giudicabile da sola.

---

## 3. Rebase: cosa e' cambiato dal 28/7 e come e' stato assorbito

| delta del tree | effetto sul disegno |
|---|---|
| sei patch in piu' (lane/kernel/econ/SCOPED/DOV+drain4fix/shared1/dspark1/dspark2+fix/logids) | tutte le righe slittate; nessun hunk della vecchia patch applicava piu' su `cuda_moe_expert_cache_invalidate` (ora ha il parametro `site`) |
| `cuda_moe_expert_cache_invalidate(const char *site)` | la shed function NON la chiama; inserita DOPO di essa (`:37029`), prima del blocco DRAIN4 |
| worker template `<G73,G132,SCOPED,DOV>`, launch_impl `<G73,G132,DOV>` | nessuna interazione: il pin vive nel model stream allocator globale (come il 28/7: il template routed non domina quel call graph); l'hunk launch_impl tocca solo il ramo `if constexpr (!G73)` del refusing-fallback, che DOV/SCOPED non hanno spostato |
| probe `ds4_vram_peak_*` dentro `cuda_model_stream_alloc` | coabita: il blocco pin sta DOPO `pick_victim()` e prima della contabilita', il probe non e' toccato |
| shared1 (`ds4_gpu_model_span_release`) | non toccato; lo shed usa il release della cache, non lo span release |
| `use_hot_reserve`/`indexer_f16` gia' nel tree | non toccati (sono il mitigatore esistente del cliff, ortogonale al pin) |

Non toccati, zero hunk: shared1, dspark1, dspark2+fix, drain4+fix, logids,
lane, econ, Q1, `ds4.c`. La patch tocca UN file (`git apply --numstat`:
+328/-14 su `ds4-p4a/ds4_cuda.cu`).

---

## 4. Neutralita' a flag spenti

Con `DS4_CUDA_PIN_BACKBONE` assente/0 (`g_vram_pin_expert_cache_shed` e'
scrivibile solo dentro la shed function, che esce subito a flag spento):

- `cuda_model_pick_victim()`: INVARIATA (zero diff);
- ciclo di sfratto: un `const int pin_backbone = ...` (int statico
  memoizzato) e rami sempre falsi; stessi account/swap-erase, stessi
  contatori preesistenti, stessi incrementi;
- `cuda_moe_expert_cache_prepare`: un test su due interi globali a zero
  (`:38571`), poi percorso identico byte per byte (clamp e hook mai
  raggiunti con shed=0);
- `routed_moe_launch_impl` `!G73`: un test su un intero a zero dentro un
  ramo di errore gia' esistente; refusing-fallback identico;
- request-end: un ramo su flag memoizzato, nessuno stato scritto;
- ammissione, frequenze, soglie, sizing: invariati; i contatori `pin_*`
  valgono zero.

Uniche differenze osservabili OFF, entrambe SOLO diagnostiche e identiche per
scelta al disegno 28/7 (che le dichiarava, e il cui protocollo di controllo
richiede i campi `pin_*` visibili a zero nel braccio di controllo):

1. la riga ANOMALY dice `victim_category=backbone victim_offset=N
   requester=X` invece di `what=X` (correzione semantica: `what` NON era la
   vittima);
2. la riga `[vram-prio]` espone i campi `pin_*` a zero (stessa riga nei due
   bracci, confrontabile campo per campo).

Nessuna struct condivisa modificata (la shed function LEGGE
`g_moe_expert_cache` e chiama il release esistente; gli unici stati nuovi
sono globali `static` file-local sul thread di decode).

---

## 5. Bracci minimi per giudicare la patch (aggiornati per il rebuild)

1. **Controllo**: flag OFF. Output hash e contatori preesistenti identici;
   campi `pin_*` a zero.
2. **Pin-140**: solo `DS4_CUDA_PIN_BACKBONE=1`. Atteso: al primo conflitto
   uno shed da 140 slot (945 MiB) + `PIN rebuild result=ok capacity=70`;
   poi `evict_backbone` piatto e `pin_backbone_failopen=0`. Se
   `failopen>0` dopo lo shed, il live set dense non entra nemmeno senza
   slab: e' il fondo non-expert reale, misurato.
3. **Pin-300 (il C2 di stamattina)**: capacita' 300 senza shared. Atteso:
   shed da 300 -> rebuild a 150 -> regime; confronto diretto col precipizio
   C2 (188.672 sfratti / 170 token, 2041 ms/token). E' il braccio che decide.
4. **No-slab**: `capacity=0` reale + pin. Separa la pressione dello slab dal
   live set dense: gli `PIN ESCAPE` restanti sono il fondo non-expert.

Nota di lettura: `pin_rebuild_slots` nel `[vram-prio]` e' il target vivo;
`expert_slots_current` la capacita' effettiva post-rebuild;
`pin_shed_deferrals` deve restare 0 (se sale, una deriva del tree ha messo
stream_alloc dentro la finestra begin->finish: investigare prima di fidarsi
dei numeri).

---

## 6. Applicabilita' e hash

```text
base:  ds4-p4a/ds4_cuda.cu (tree corrente, NON modificato dal deliverable)
       SHA-256 F759225AA817B539295C986BD50CAB7A999ECF3B60930E68120472BF1C24B142
dopo:  ds4-p4a/ds4_cuda.cu + pin2.patch
       SHA-256 DD1E4CD8B3B2D93C4414B6A80A2DFE153FD0BD20A11125DECECE4ADDDA14AD71
patch: .microbench/pin2/pin2.patch
       SHA-256 5DCBBF52E727F8943857F0873C093F1E86A8360733D495B4443B1484D1A82A58

git apply --check .microbench/pin2/pin2.patch   -> OK (tree corrente)
git apply --numstat                             -> +328 -14, solo ds4-p4a/ds4_cuda.cu
roundtrip base+patch                            -> byte-identico al file di lavoro
bilanciamento ()/{}/[]                          -> identico alla base
formati/argomenti di ogni fprintf nuova         -> verificati 1:1 (35 campi [vram-prio])
```

Verifica B condotta su: `ds4-p4a/ds4.c` (righe 124, 3156-3161, 13580-13673),
`ds4-p4a/ds4_cuda.cu` base (17767-17845, 22717-22816, 8526-8527),
`.microbench/backbone_bytes/MISURA.md`, `.microbench/zerocopy/results.txt`,
`.microbench/atlante/REVISIONE.md`. Nessuno di questi file e' stato modificato.
