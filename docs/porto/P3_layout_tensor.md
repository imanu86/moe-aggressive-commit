## Esito

La diagnosi conferma la classificazione **56 + 12**:

- il log contiene 68 errori ([primo errore](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-upstream-cuda-measure/build-port-measure/nvcc-full-contract-preinclude.log:9), [totale finale](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-upstream-cuda-measure/build-port-measure/nvcc-full-contract-preinclude.log:407));
- il confronto delle dichiarazioni pubbliche trova esattamente 12 firme realmente diverse;
- gli altri 56 sono la ridefinizione di `ds4_gpu_tensor` più 55 conseguenze sul tipo C/C++.

Conclusione principale: **non porterei `host_ptr` dentro il tensore upstream**. Il `host_ptr` di `ds4_gpu_tensor` serve al KV cache staged, non all’arena esperti da 30 GiB. Il percorso esperti ha già propri puntatori host in strutture separate e può essere portato mantenendo intatto il contratto upstream.

Nessun file modificato e nessuna compilazione eseguita.

## 1. Il contratto vero

### Definizioni

Nostro albero, working tree corrente, [ds4_cuda.cu:1040](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:1040):

```c
struct ds4_gpu_tensor {
    void *ptr;
    void *host_ptr;
    uint64_t bytes;
    int owner;
};
```

Nel blob di `646f3be` la stessa definizione è a riga 508; il working tree `ds4-p4a` contiene modifiche locali, quindi i link qui indicano le righe correnti.

Upstream CUDA, [ds4_gpu_mgpu.h:39](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu_mgpu.h:39):

```c
struct ds4_gpu_tensor {
    void *ptr;
    uint64_t bytes;
    int owner;
    int device_id; /* -1 means legacy/untagged → treat as device 0 */
};
```

Il normale [ds4_gpu.h:20](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:20) espone solo il typedef opaco. CUDA include la definizione multi-GPU da [ds4_cuda.cu:74](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:74).

Se i due layout venissero mescolati binariamente, non sarebbe una semplice perdita di campo:

- upstream leggerebbe `host_ptr` come `bytes`;
- leggerebbe i 64 bit di `bytes` come `owner` e `device_id`;
- il nostro codice leggerebbe `bytes` upstream come `host_ptr`.

Il rifiuto del compilatore evita quindi una corruzione catastrofica.

### `ptr`

**Upstream, verificato**

È il puntatore CUDA associato al device logico indicato da `device_id`.

- Scritto dagli allocator in [ds4_cuda.cu:2344](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2344).
- Ereditato e traslato dalle view in [ds4_cuda.cu:2516](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2516).
- Letto da copie, fill, kernel e free in [ds4_cuda.cu:2538](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2538).
- Azzerato dopo il free in-place in [ds4_cuda.cu:2374](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2374).

Se manca, upstream non ha uno stato generico “tensore residente solo su host”: le operazioni normali falliscono oppure finirebbero per passare un puntatore nullo a CUDA.

**Nostro, verificato**

È normalmente il puntatore CUDA, ma può diventare `NULL` mentre il contenuto sopravvive in `host_ptr`. Allocazione e inizializzazione sono in [ds4_cuda.cu:9890](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:9890).

### `bytes`

In entrambi gli alberi rappresenta l’estensione logica del tensore.

- Scritto da allocazione e view.
- Letto da bounds check, copie, view e accounting.
- Upstream: [allocazione](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2344), [view](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2516), [I/O](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2561).
- Nostro: [allocazione](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:9890), [view](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:9958).

Se manca o vale zero, le operazioni vengono rifiutate dai controlli oppure il tensore risulta vuoto. Un valore errato elimina la protezione dagli accessi fuori limite.

### `owner`

In entrambi indica se il tensore possiede la risorsa e deve liberarla.

Upstream:

- allocator: `owner = 1`;
- view/alias: `owner = 0`;
- free consulta `owner`: [ds4_cuda.cu:2527](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2527).

Nel nostro codice `owner` governa anche la liberazione dell’eventuale memoria pinned in `host_ptr`, con eccezioni per l’arena condivisa: [ds4_cuda.cu:9969](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:9969).

Se erroneamente zero: leak. Se erroneamente uno su view o memoria condivisa: double free o free di un indirizzo interno all’arena.

### `device_id` upstream

È un **indice di device logico/tier**, non necessariamente il numero CUDA fisico. Viene tradotto attraverso `g_gpu[device_id].device_id`; valori negativi/legacy ricadono sul tier zero: [ds4_cuda.cu:254](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:254).

Scritto da:

- `alloc_on`: [ds4_cuda.cu:2344](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2344);
- managed allocation: [ds4_cuda.cu:2397](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2397);
- view, che lo eredita: [ds4_cuda.cu:2523](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2523);
- tensori sintetici del cache esperti: [ds4_cuda.cu:23079](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:23079).

Letto da:

- free, fill, read/write;
- copie cross-device: [ds4_cuda.cu:2671](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:2671);
- controlli di colocazione e percorsi TP/multi-GPU.

Se manca o è errato:

- viene selezionato il contesto CUDA sbagliato;
- il free può avvenire sul device sbagliato;
- una copia può essere classificata come locale invece che peer/cross-device;
- TP può usare o convalidare il tier sbagliato.

Per il substrato upstream, `device_id` è quindi obbligatorio.

### `host_ptr` nostro

Il sospetto va corretto: **il campo nel tensore è principalmente il backing host del KV cache staged**, non quello dell’arena esperti.

Percorso verificato:

1. La modalità è descritta in [ds4_gpu.h:109](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:109): il KV cache viene migrato a memoria pinned host tra prefill e decode.
2. Il registry conserva arena e stato host-resident in [ds4_cuda.cu:1071](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:1071).
3. L’arena pinned viene allocata con `cudaHostAlloc` in [ds4_cuda.cu:22560](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:22560).
4. Il contenuto viene copiato device→host in [ds4_cuda.cu:22575](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:22575).
5. Il tensore riceve `host_ptr` in [ds4_cuda.cu:22603](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:22603), poi `ptr` viene liberato e azzerato in [ds4_cuda.cu:22610](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:22610).
6. Il restore rialloca VRAM in [ds4_cuda.cu:22440](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:22440), copia host→device e azzera `host_ptr` in [ds4_cuda.cu:22449](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:22449).
7. View, read/write e copy sono consapevoli del backing host: [view](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:9958), [I/O](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:9986), [copy](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:17794).

Se `host_ptr` viene eliminato senza sostituto:

- si perde `DS4_CUDA_KV_STAGED_RING`;
- non si possono rappresentare i KV tensor con `ptr == NULL` ma backing pinned valido;
- si perdono i rami staged di attention/quantizzazione;
- aumentano permanenza e pressione VRAM del KV cache.

**Non si perde automaticamente l’arena esperti.**

I suoi puntatori host sono separati:

- `ds4_gpu_dynamic_arena_load.host_ptr`: [ds4_cuda.cu:2349](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:2349);
- `cuda_dynamic_arena_slot.host_ptr`: [ds4_cuda.cu:2358](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:2358);
- upload slot host→device: [ds4_cuda.cu:40351](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:40351);
- risoluzione degli slot: [ds4_cuda.cu:53827](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:53827).

## 2. Conciliazione

### Ricerca dell’opzione (c)

**Verificato:** upstream possiede meccanismi equivalenti per due parti importanti, ma non per tutte.

Per model-map/zero-copy:

- base host globale e risoluzione dei pesi: [ds4_cuda.cu:536](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:536);
- `cudaHostRegisterMapped` e alias CUDA: [ds4_cuda.cu:585](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:585);
- registrazione del model map: [ds4_cuda.cu:3124](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:3124).

Per gli esperti:

- contratto della tabella streaming: [ds4_gpu.h:151](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:151);
- staging pinned e trasferimenti: [ds4_cuda.cu:1598](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:1598);
- caricamento degli esperti selezionati in buffer VRAM compatti: [ds4_cuda.cu:23030](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:23030).

Limite importante: il cache esperti upstream è esplicitamente single-GPU in [ds4_cuda.cu:22963](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:22963), e non equivale alla nostra politica completa SSD→RAM→VRAM con arena da 30 GiB.

Quindi:

- **(c) vale per il concetto di zero-copy/model-map e per l’infrastruttura base di streaming esperti;**
- **(c) non vale per un generico tensore host-resident e non sostituisce il KV staged.**

### Decisione raccomandata: (c) + (b)

Terrei invariato:

```c
{ ptr, bytes, owner, device_id }
```

e porterei l’arena esperti usando i suoi record `dynamic_arena_load`/`dynamic_arena_slot`, integrandoli con il resolver e il device routing upstream.

Per conservare il KV staged userei una tabella laterale, ma **limitata al registry KV**, non una tabella globale per ogni `ds4_gpu_tensor`.

La tabella deve rappresentare almeno:

- tensore base;
- host base;
- dimensione;
- offset delle view;
- stato resident/transient;
- generazione o altra protezione contro il riuso dell’indirizzo dell’oggetto.

Una semplice hash map `ds4_gpu_tensor* → host_ptr` non basta: le view sono oggetti diversi e oggi ereditano `host_ptr + offset`. Con `ptr == NULL` non si può neppure ricavare l’offset dal vecchio device pointer.

Costo stimato di (b): più modifiche circoscritte al KV staged e un lookup nei rami host-resident, ma nessun cambiamento al contratto multi-device upstream.

### Opzione (a): tecnicamente possibile, ma seconda scelta

Layout combinato plausibile:

```c
{ ptr, host_ptr, bytes, owner, device_id }
```

Dimensioni calcolate per ABI x64 corrente, non compilate:

- upstream: 24 byte;
- nostro: 32 byte;
- combinato: 32 byte.

Audit verificato:

- non ho trovato serializzazione su disco/rete della struttura;
- non ho trovato kernel CUDA che ricevano `ds4_gpu_tensor` per valore;
- gli allocator usano `sizeof(*t)`, quindi si adeguerebbero;
- esistono però strutture incorporate, stack object e copie CPU per valore: servirebbe un rebuild completo di tutti gli oggetti.

I rischi reali sarebbero semantici:

- ogni allocator e tensore sintetico deve inizializzare entrambi `host_ptr` e `device_id`;
- ogni view deve propagare `host_ptr + offset` e `device_id`;
- `owner` deve distinguere VRAM, pinned privata e slice dell’arena condivisa;
- le operazioni multi-device devono trattare esplicitamente `ptr == NULL && host_ptr != NULL`;
- TP e kernel normali devono rifiutare i tensori host-only o materializzarli prima.

Se l’obiettivo fosse conservare subito il KV staged col minor numero di cambiamenti interni, (a) sarebbe probabilmente più semplice di (b). Ma allargherebbe il contratto centrale upstream per una funzione che non è necessaria all’arena esperti.

## 3. I dodici cambi di firma

Le porzioni non riportate come differenza sono identiche; i link puntano alle dichiarazioni complete.

1. `ds4_gpu_set_model_map_range` — [nostra:208](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:208), [upstream:98](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:98)

```c
// nostra
(..., uint64_t map_offset, uint64_t map_size)

// upstream
(..., uint64_t map_offset, uint64_t map_size,
      uint64_t max_tensor_bytes)
```

CUDA upstream attualmente ignora l’argomento; Metal lo usa per segmentare le view. **Meccanico nel backend CUDA, semantico nell’API multipiattaforma.** L’adattatore deve passare `model.max_tensor_bytes`.

2. `ds4_gpu_attention_decode_heads_tensor` — [nostra:673](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:673), [upstream:1677](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1677)

```c
// nostra
..., comp_kv, uint32_t n_comp, comp_mask, ...

// upstream
..., comp_kv, uint32_t comp_kv_f16, uint32_t n_comp, comp_mask, ...
```

3. `ds4_gpu_attention_decode_mixed_batch_heads_tensor` — [nostra:718](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:718), [upstream:1818](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1818)

```c
// nostra
..., comp_kv, comp_mask, ...

// upstream
..., comp_kv, uint32_t comp_kv_f16, comp_mask, ...
```

4. `ds4_gpu_attention_indexed_mixed_batch_heads_tensor` — [nostra:739](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:739), [upstream:1840](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1840)

```c
// nostra
..., comp_kv, topk, ...

// upstream
..., comp_kv, uint32_t comp_kv_f16, topk, ...
```

5. `ds4_gpu_attention_prefill_static_mixed_heads_tensor` — [nostra:760](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:760), [upstream:1862](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1862)

```c
// nostra
..., comp_kv, uint32_t n_tokens, ...

// upstream
..., comp_kv, uint32_t comp_kv_f16, uint32_t n_tokens, ...
```

6. `ds4_gpu_attention_prefill_masked_mixed_heads_tensor` — [nostra:775](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:775), [upstream:1901](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1901)

```c
// nostra
..., comp_kv, comp_mask, ...

// upstream
..., comp_kv, uint32_t comp_kv_f16, comp_mask, ...
```

Per tutte e cinque: il flag distingue compressed KV F16 da F32. Upstream usa F16 nel cache persistente Metal e F32 altrove; CUDA rifiuta attualmente `comp_kv_f16 != 0`, per esempio [decode:14480](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:14480).

**Adattamento CUDA meccanico:** passare zero.  
**Adattamento nel codice condiviso semantico:** passare il valore prodotto dalla policy upstream, altrimenti si rompe Metal.

7. `ds4_gpu_compressor_update_tensor` — [nostra:568](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:568), [upstream:1571](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1571)

```c
// nostra
..., float rms_eps)

// upstream
..., float rms_eps, bool state_already_stored)
```

Upstream evita un secondo store quando proiezione e store sono già stati fusi. **Cambio semantico.** Le vecchie chiamate isolate possono passare `false`; le chiamate inserite nel percorso fused devono propagare il flag reale.

8. `ds4_gpu_router_select_tensor` — [nostra:847](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:847), [upstream:2049](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:2049)

```c
// nostra, subito dopo model_size
uint32_t layer_index, ...

// upstream, dopo token
uint32_t n_expert,
uint32_t n_expert_used,
float expert_weight_scale,
...
```

Upstream elimina `layer_index` e rende espliciti forma e scaling del router. L’implementazione corrente valida ancora 256/6/1.5.

Il nostro `layer_index` alimenta bias/mask e osservatori per-layer. **Non va semplicemente eliminato.** La firma combinata deve conservare `layer_index` e accettare i tre parametri upstream.

9. `ds4_gpu_router_select_batch_tensor` — [nostra:864](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:864), [upstream:2068](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:2068)

Stessa differenza semantica:

```c
// nostra
model_size, layer_index, ... tokens, n_tokens

// upstream
model_size, ... tokens,
n_expert, n_expert_used, expert_weight_scale, n_tokens
```

Adattatore richiesto, non semplice cambio posizionale.

10. `ds4_gpu_routed_moe_one_tensor` — [nostra:882](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:882), [upstream:2309](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:2309)

Differenze esatte:

```c
// nostra
model_size, layer_index, gate_offset, ...
...
selected, weights,
n_expert, clamp, x,
g133_epoch, spex_queue, spex_key

// upstream
model_size, gate_offset, ...
...
selected, weights,
n_total_expert, n_expert, clamp, x,
add_in, layer_index, force_resident
```

`add_in` viene sommato all’output ed è usato anche nel folding TP; `force_resident` impedisce il percorso streaming. Noi aggiungiamo epoch G133 e coda/chiave SPEX.

**Cambio profondamente semantico.** La firma risultante deve conservare entrambe le famiglie:

- `n_total_expert`;
- `add_in`;
- `layer_index`;
- `force_resident`;
- `g133_epoch`, `spex_queue`, `spex_key`.

Il dispatcher avanzato nostro può essere usato solo per le forme che supporta; altrimenti deve ricadere nel percorso upstream.

11. `ds4_gpu_routed_moe_batch_tensor` — [nostra:1006](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:1006), [upstream:2339](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:2339)

```c
// nostra
model_size, layer_index, ...
...
selected, weights, probs,
n_expert, clamp, x,
n_tokens, mid_is_f16

// upstream
model_size, ...
...
selected, weights,
n_total_expert, n_expert, clamp, x,
layer_index, n_tokens, mid_is_f16,
force_resident
```

`probs` nostro serve all’osservatore/composizione della massa in prefill. Upstream aggiunge la cardinalità totale e il controllo di residenza; nella wrapper batch corrente `force_resident` è ancora ignorato.

**Cambio profondamente semantico.** Eliminare `probs` disattiva o rende impossibile la nostra logica di prefill-mass.

12. `ds4_gpu_shared_gate_up_swiglu_q8_0_tensor` — [nostra:395](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:395), [upstream:634](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:634)

```c
// nostra
..., const ds4_gpu_tensor *x)

// upstream
..., const ds4_gpu_tensor *x, float clamp)
```

Noi fissiamo internamente `10.0`; upstream riceve il clamp dalla shape del modello. **Meccanico per DSV4 se si passa 10.0, semantico per modelli/shape differenti.**

## 4. Ordine raccomandato

1. **Eliminare per prima la doppia definizione del tensore.** Il port deve includere e usare la definizione upstream di `ds4_gpu_mgpu.h`; nessun frammento nostro deve ridefinire `ds4_gpu_tensor`.

2. **Adattare ogni estensione nostra al contratto `{ptr,bytes,owner,device_id}`.** Ogni tensore allocato, view o sintetico deve ricevere il tier corretto. Le nostre strutture arena mantengono i propri `host_ptr`.

3. **Portare il resolver/arene esperti senza coinvolgere il tensore host-only.** Se inizialmente non è multi-device-safe, deve fallire esplicitamente fuori dal tier supportato, come fa oggi il cache esperti upstream, non fingere `device_id = 0`.

4. **Adattare le firme a rischio basso:** `max_tensor_bytes`, cinque `comp_kv_f16`, `state_already_stored`, `clamp`.

5. **Unificare i router.** Prima dei MoE perché producono `selected`, `weights`, `probs` e stato per-layer.

6. **Unificare i due routed-MoE**, conservando sia i parametri upstream/TP sia G133, SPEX e `probs`.

7. **Solo dopo reintrodurre il KV staged tramite tabella laterale.** Può essere temporaneamente escluso senza sacrificare strutturalmente lo streaming degli esperti.

Il passo 1 è quello che, secondo il log e il confronto delle firme, sblocca i 55 errori dipendenti. È una conclusione verificata staticamente; la scomparsa effettiva dei 56 errori resta da confermare con la prima compilazione successiva, che qui non ho eseguito.

Codex session ID: 019fbc41-f4d2-70c2-b2c9-e96401ff6b55
Resume in Codex: codex resume 019fbc41-f4d2-70c2-b2c9-e96401ff6b55
