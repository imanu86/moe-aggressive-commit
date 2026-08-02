# Sintesi della mappa

Generato da `ricongiungi.py`. **Non modificare a mano**: si rifa'.

Copertura: **886 funzioni schedate su 5164** (17.2%).

Di queste, 2 con certezza non alta: dequant_q8_0_to_f16_kernel (media), dequant_q8_0_to_f32_kernel (media)

## Cosa gli agenti hanno sbagliato

- **doppione**: 7 — es. SCHEDE_004.tsv:20 cuda_moe_io_queue_depth

## Il cammino caldo

650 funzioni girano per token, per strato o per esperto.

### Allocano o liberano VRAM sul cammino caldo

Su una scheda dove il gigabyte e' la partita, questa e' la lista che conta.

| funzione | vram | frequenza | dove | cosa fa |
|---|---|---|---|---|
| `cuda_model_arena_alloc` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:5517` | Serve una slice allineata da un'arena VRAM esistente o alloca un nuovo blocco. |
| `cuda_model_range_ptr_from_fd` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:5569` | Alloca e carica dal file una range di pesi nella cache VRAM, poi la indicizza. |
| `cuda_stream_resident_cache_prepare_locked` | alloca | per-esperto | `ds4_cuda.cu:28067` | Dimensiona e alloca la cache residente dopo che il workspace attenzione è già presente. |
| `attention_decode_batch_launch` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:214` | Esegue attenzione decode raw o mista per un lotto scegliendo il kernel compatibile |
| `attention_decode_score_split_launch` | alloca | per-layer | `ds4_cuda.cu:11458` | Seleziona e lancia il percorso score-split esatto, allocandone lo scratch temporaneo. |
| `attention_decode_splitkv_launch` | alloca | per-layer | `ds4_cuda.cu:18456` | Suddivide lo score KV del decode singolo e combina i parziali con softmax |
| `attention_prefill_mixed_launch` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:619` | Calcola prefill su KV raw e compresso scegliendo online, cuBLAS o kernel base |
| `cuda_matmul_q8_0_hc_expand_tensor_labeled` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:641` | Fonde proiezione Q8_0, addendi opzionali ed espansione hidden-copy |
| `cuda_matmul_q8_0_tensor_labeled` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:311` | Esegue una matmul Q8_0 scegliendo cache cuBLAS, GEMM F16 o kernel nativi |
| `cuda_model_range_ptr` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:4589` | Rende un range di pesi accessibile alla GPU tramite cache, mapping host o copia. |
| `cuda_q8_f16_ptr` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5015` | Restituisce o crea sul device una copia fp16 dequantizzata di un peso q8. |
| `cuda_q8_f32_ptr` | alloca | per-layer | `ds4_cuda.cu:3212` | Restituisce o crea sul device una copia fp32 dequantizzata di un peso q8. |
| `cuda_resolve_weight_ptr` | alloca | per-layer | `ds4_cuda.cu:2750` | Risolve il puntatore device di un peso sul tier richiesto o sul device CUDA corrente. |
| `cuda_stream_selected_ensure_bytes` | alloca | per-layer | `ds4_cuda.cu:28942` | Assicura un buffer CUDA di almeno i byte richiesti, riallocandolo se serve. |
| `cuda_stream_selected_ensure_i32` | alloca | per-layer | `ds4_cuda.cu:29021` | Alloca remap selezioni |
| `cuda_stream_selected_weight_storage_prepare` | alloca | per-layer | `ds4_cuda.cu:28962` | Prepara i buffer VRAM gate, up e down in layout packed o in tre allocazioni. |
| `cuda_stream_selected_weight_storage_release` | libera | per-layer | `ds4_cuda.cu:1912` | Libera lo storage VRAM dei pesi selected e ne azzera puntatori e capacità. |
| `cuda_tmp_alloc` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:567` | Alloca o amplia lo scratch CUDA globale riusabile. |
| `cuda_tmp_alloc_on` | alloca | per-layer | `ds4_cuda.cu:2463` | Fornisce scratch riusabile globale su una GPU o separato per tier in multi-GPU. |
| `ds4_gpu_attention_decode_heads_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:27` | Calcola l'attenzione decode per head scegliendo staging, online, score-split o kernel base |
| `ds4_gpu_attention_decode_mixed_batch_heads_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:327` | Avvia attenzione mista |
| `ds4_gpu_attention_decode_raw_batch_heads_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:306` | Avvia attenzione grezza |
| `ds4_gpu_attention_decode_rows_rope_tensor` | alloca | per-layer | `ds4_cuda.cu:18836` | Esegue decode raggruppato su righe dense o indicizzate e applica RoPE inversa |
| `ds4_gpu_attention_indexed_mixed_batch_heads_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:355` | Calcola attenzione mista usando top-k di righe compresse per ogni token |
| `ds4_gpu_attention_output_low_q8_rows_exact_tensor` | alloca | per-layer | `ds4_cuda.cu:19879` | Calcola il fattore basso Q8 per un intervallo di gruppi e più righe |
| `ds4_gpu_attention_output_low_q8_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:1258` | Proietta heads quantizzati |
| `ds4_gpu_attention_output_q8_batch_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:953` | Proietta gli head tramite fattore A raggruppato e fattore B con pesi Q8 |
| `ds4_gpu_attention_output_q8_tp_tensor` | alloca | per-layer | `ds4_rocm.cu:193` | Proietta una slice TP degli head con fattori Q8 A e B |
| `ds4_gpu_attention_prefill_raw_heads_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:115` | Calcola attenzione causale di prefill su KV raw scegliendo online, cuBLAS o kernel base |
| `ds4_gpu_attention_prefill_static_mixed_heads_tensor` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:803` | Avvia prefill misto |
| `ds4_gpu_glm_attention_indexed_decode_typed_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:351` | Valida e lancia l'attenzione MLA indicizzata, scegliendo percorso fuso, staged o MTP a due token. |
| `ds4_gpu_glm_qk_lowrank_typed_batch_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:329` | Proietta Q nel rango KV con pesi Q8_0, usando cuBLAS dequantizzato sui batch grandi. |
| `ds4_gpu_glm_routed_moe_batch_tensor` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:4077` | Esegue l'intero MoE routed batch: quantizza, calcola gate/up, requantizza e proietta down. |
| `ds4_gpu_indexer_topk_tensor` | alloca | per-layer | `rocm/ds4_rocm_indexer.cuh:856` | Seleziona gli indici dei top-k score per ogni token |
| `ds4_gpu_matmul_f16_pair_tensor` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:785` | Calcola due proiezioni F16 dalla stessa attivazione |
| `ds4_gpu_matmul_f16_router_rows_exact_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:229` | Calcola il router F16 fisso 4096x256 preservando l'ordine per riga |
| `ds4_gpu_matmul_q8_0_decode_rows_exact_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:210` | Esegue la proiezione Q8_0 esatta sulle righe di decode |
| `ds4_gpu_matmul_q8_0_hc_expand_tensor` | alloca | per-layer | `rocm/ds4_rocm_hc_output_launch.cuh:420` | Fonde una proiezione Q8_0 con l'espansione e la miscela dei flussi HC. |
| `ds4_gpu_matmul_q8_0_kslice_hc_expand_add_tensor` | alloca | per-layer | `ds4_cuda.cu:16485` | Fonde K-slice Q8, somma del blocco ed espansione hidden-copy |
| `ds4_gpu_matmul_q8_0_kslice_rows_tensor` | alloca | per-layer | `ds4_cuda.cu:16420` | Calcola per piu righe una proiezione Q8_0 limitata a una K-slice |
| `ds4_gpu_matmul_q8_0_pair_decode_rows_exact_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:219` | Esegue due proiezioni Q8_0 esatte sulle stesse righe di decode |
| `ds4_gpu_matmul_q8_0_pair_tensor` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:568` | Riusa la quantizzazione dell'input per due proiezioni Q8_0 |
| `ds4_gpu_matmul_q8_0_tensor` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:509` | Delega matmul Q8 |
| `ds4_gpu_shared_down_hc_expand_add_q8_0_tensor` | alloca | per-layer | `ds4_cuda.cu:27257` | Fonde down Q8_0 condiviso, due contributi routed ed espansione HC. |
| `ds4_gpu_shared_down_hc_expand_owned_q8_0_tensor` | alloca | per-layer | `ds4_cuda.cu:27294` | Fonde down Q8_0 condiviso, contributi MoE posseduti ed espansione HC. |
| `ds4_gpu_shared_down_hc_expand_q8_0_tensor` | alloca | per-layer | `rocm/ds4_rocm_hc_output_launch.cuh:394` | Fonde down Q8_0 condiviso, contributo routed ed espansione HC. |
| `ds4_gpu_shared_gate_up_swiglu_q8_0_tensor` | alloca | per-layer | `rocm/ds4_rocm_shared_expert.cuh:7` | Calcola gate e up condivisi con pesi Q8 e produce SwiGLU |
| `ds4_gpu_shared_mid_swiglu_q8_0_decode_exact_tensor` | alloca | per-layer | `ds4_cuda.cu:20058` | Fonde matmul Q8 di gate e up con SwiGLU esatta per il decode |
| `ds4_gpu_shared_mid_swiglu_q8_0_tensor` | alloca | per-layer | `rocm/ds4_rocm_shared_expert.cuh:101` | Alloca o riusa due scratch gate/up e calcola lo SwiGLU condiviso per un token. |
| `ds4_gpu_tensor_alloc_kv_cache` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5920` | Alloca un KV cache sulla GPU 0 e lo registra per lo staging host quando richiesto. |
| `ds4_gpu_tensor_alloc_managed` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5907` | Crea un tensor CUDA managed e lo associa contabilmente alla GPU logica 0. |
| `ds4_gpu_tensor_alloc_managed_on` | alloca | per-layer | `ds4_rocm_compat.cu:56` | Alloca memoria CUDA managed sotto il device del tier e registra quel tier nel tensor. |
| `routed_moe_launch` | alloca | per-layer | `rocm/ds4_rocm_moe_launch.cuh:520` | Valida i tensori e orchestra quantizzazione, routing ordinato, gate-up, down e somma MoE CUDA |
| `cuda_embed_row_stage_alloc` | alloca | per-token | `ds4_cuda.cu:2398` | Crea o amplia lo staging pinned-host più device per copiare righe embedding. |
| `cuda_kv_staged_ring_ensure_locked` | alloca | per-token | `ds4_cuda.cu:4959` | Crea o ridimensiona ring, accumulatori, eventi e stream richiesti dal KV staged. |
| `ds4_gpu_matmul_q8_0_top1_tensor` | alloca | per-token | `ds4_cuda.cu:16345` | Fonde proiezione Q8_0 e selezione top-1 senza materializzare tutti i logit |

## Trappole

Comportamenti che sorprenderebbero chi usa la funzione. Ordinate per certezza dichiarata dall'agente.

### Certezza alta (850)

- **`abort_transaction`** `src/cuda/dynamic_arena.cu:401`  
  Non ripristina vittime sovrascritte: elimina i binding non più ready
- **`accumulate_locked`** `src/cuda/prefill_observer.cu:165`  
  Scarta in silenzio esperti invalidi e pesi non finiti o non positivi.
- **`acquire_vram_reader`** `src/cuda/dynamic_arena.cu:1174`  
  Ricalcola FNV dell'intero slot sotto il mutex globale a ogni hit
- **`append_pseudo_layer_tags`** `ds4_layer_pack.c:49`  
  Ignora in silenzio l'output head se n_layers+1 non rientra in n_entries.
- **`attention_compact_topk_stable`** `ds4_cuda.cu:11912`  
  Esamina al massimo 512 posizioni e conserva anche eventuali duplicati
- **`attention_decode_batch_launch`** `rocm/ds4_rocm_attention_launch.cuh:214`  
  Con più token e cache staged disabilita e ripristina la migrazione KV
- **`attention_decode_global_softmax_kernel`** `ds4_cuda.cu:11145`  
  Gli score riscritti sono esponenziali non normalizzati; il sink resta solo nel denominatore
- **`attention_decode_mixed_heads8_online_kernel`** `rocm/ds4_rocm_attention.cuh:1315`  
  Con ratio 0 include i compressi soltanto quando n_tokens è esattamente 1
- **`attention_decode_mixed_kernel`** `rocm/ds4_rocm_attention.cuh:617`  
  Con ratio=0 include tutte le righe compresse e limita le righe raw a 256.
- **`attention_decode_score_split_finalize_dim2_kernel`** `ds4_cuda.cu:11033`  
  Ricalcola l'intero softmax due volte, una per ciascuna metà della testa
- **`attention_decode_score_split_finalize_kernel`** `ds4_cuda.cu:10742`  
  Il sink aggiunge massa solo al denominatore, come se il suo valore fosse zero
- **`attention_decode_score_split_finalize_rows_kernel`** `ds4_cuda.cu:10890`  
  Le sessioni indexed vengono saltate senza azzerare la relativa uscita
- **`attention_decode_score_split_graph_destroy_one`** `ds4_cuda.cu:11279`  
  Viene chiamata anche su cambio shape o errore, non soltanto in chiusura
- **`attention_decode_score_split_graph_launch`** `ds4_cuda.cu:11287`  
  Il grafo viene sempre lanciato sullo stream CUDA 0
- **`attention_decode_score_split_launch`** `ds4_cuda.cu:11458`  
  DS4_CUDA_NO_SCORE_TILE è letto una sola volta: basta la presenza, anche con valore 0
- **`attention_decode_score_split_scores_kernel`** `ds4_cuda.cu:10073`  
  Calcola solo gli score; softmax e combinazione dei valori spettano a kernel successivi.
- **`attention_decode_score_split_scores_ldg_kernel`** `ds4_cuda.cu:10163`  
  Le righe raw visibili sono comunque troncate a 256
- **`attention_decode_score_split_scores_tile512_kernel`** `ds4_cuda.cu:10261`  
  Una maschera <= -1e20 evita anche il caricamento della riga KV
- **`attention_decode_score_split_scores_tile512_rows_kernel`** `ds4_cuda.cu:10420`  
  Ritorna senza scrivere per righe indexed e non applica maschere ai compressi
- **`attention_decode_score_split_scores_vec4_kernel`** `ds4_cuda.cu:10584`  
  La dimensione 512 è implicita e non è ricevuta né verificata
- **`attention_decode_score_split_scores_vec4_plain_kernel`** `ds4_cuda.cu:10663`  
  Può produrre ultimi bit diversi dal percorso esatto per contrazione FMA
- **`attention_decode_split_value_combine_kernel`** `ds4_cuda.cu:11246`  
  Un denominatore nullo o non finito viene usato senza guardia
- **`attention_decode_split_value_kernel`** `ds4_cuda.cu:11206`  
  Scrive somme pesate non normalizzate e non incorpora il sink
- **`attention_decode_splitkv_combine_kernel`** `ds4_cuda.cu:11858`  
  Il riordinamento online FP32 non è garantito bit-identico al kernel di riferimento
- **`attention_decode_splitkv_kernel`** `ds4_cuda.cu:11686`  
  Non include il sink; chunk vuoti o mascherati scrivono m=-INF, l=0 e numeratore zero
- **`attention_decode_splitkv_launch`** `ds4_cuda.cu:18456`  
  0 richiede fallback, -1 segnala errore; S uguale a 1 forza il kernel legacy
- **`attention_indexed_mixed_decode_rows_kernel`** `ds4_cuda.cu:12104`  
  I descrittori non indexed vengono saltati lasciando intatta l'uscita
- **`attention_indexed_mixed_heads8_online_kernel`** `rocm/ds4_rocm_attention.cuh:1028`  
  Non valida gli indici top-k: valori negativi o fuori range indirizzano KV errata
- **`attention_indexed_mixed_heads8_rb4_kernel`** `ds4_cuda.cu:12275`  
  La compattazione seriale conserva duplicati top-k, che ricevono massa più volte
- **`attention_indexed_mixed_kernel`** `rocm/ds4_rocm_attention.cuh:871`  
  Se esiste un compresso cambia l'ordine di riduzione anche degli score raw
- **`attention_noncausal_raw_batch_heads_kernel`** `ds4_cuda.cu:17438`  
  Il sink entra nel denominatore ma non aggiunge alcun vettore value
- **`attention_pack_group_heads_f16_kernel`** `rocm/ds4_rocm_attention.cuh:343`  
  La conversione FP16 è lossy e avviene solo nel percorso cuBLAS.
- **`attention_prefill_mixed_kernel`** `rocm/ds4_rocm_attention.cuh:67`  
  Il sink assorbe probabilità senza aggiungere un vettore valore all'output.
- **`attention_prefill_mixed_launch`** `rocm/ds4_rocm_attention_launch.cuh:619`  
  Il percorso cuBLAS riserva scratch quadratico nel numero di token e chiavi
- **`attention_prefill_mixed_softmax_kernel`** `rocm/ds4_rocm_attention.cuh:192`  
  Un valore di maschera <= -1e20 esclude silenziosamente la chiave compressa.
- **`attention_prefill_pack_mixed_kv_kernel`** `rocm/ds4_rocm_attention.cuh:311`  
  Le righe raw precedono sempre tutte le righe compresse.
- **`attention_prefill_raw_kernel`** `rocm/ds4_rocm_attention.cuh:11`  
  Il sink entra nel denominatore ma non contribuisce alcun vettore valore.
- **`attention_prefill_raw_softmax_kernel`** `rocm/ds4_rocm_attention.cuh:147`  
  Sovrascrive gli score e include nel denominatore una massa sink non presente nelle righe.
- **`attention_prefill_unpack_heads_kernel`** `rocm/ds4_rocm_attention.cuh:327`  
  Il kernel non copia soltanto: scambia gli assi testa e token.
- **`attention_staged_ring_heads8_online_kernel`** `ds4_cuda.cu:12909`  
  Prima dell'ultimo chunk heads contiene un numeratore riscalato ma non normalizzato
- **`attention_static_mixed_heads8_online_kernel`** `rocm/ds4_rocm_attention.cuh:1191`  
  Con ratio uguale a 0 ignora completamente comp_kv
- **`attention_unpack_group_low_kernel`** `rocm/ds4_rocm_attention.cuh:359`  
  Scambia implicitamente gli assi gruppo e token.
- **`begin_transaction`** `src/cuda/dynamic_arena.cu:667`  
  Una sola vittima con reader attivi fa fallire l'intera transazione
- **`bind_layer_locked`** `src/cuda/dynamic_arena.cu:567`  
  Assume UP grande quanto GATE perché non esiste una misura UP separata
- **`binding_valid`** `src/cuda/dynamic_arena.cu:378`  
  Non controlla il checksum del contenuto
- **`bitrev5`** `ds4_cuda.cu:8543`  
  I bit oltre i cinque meno significativi vengono scartati.
- **`bool_requested`** `src/cuda/prefill_observer.cu:71`  
  Valori diversi da 0 e 1 disabilitano con warning; non accetta true.
- **`budget_for_expert_size`** `src/cuda/dynamic_arena.cu:1146`  
  Qualunque input invalido azzera anche il conteggio configurato globale
- **`build_source_parts`** `src/cuda/dynamic_arena.cu:876`  
  Ordina prima per tipo gate/up/down, non solo per offset sorgente
- **`clear_locked`** `src/cuda/prefill_observer.cu:268`  
  Ignora errori di synchronize e destroy, poi azzera comunque tutto lo stato.
- **`compressor_prefill_pool_kernel`** `rocm/ds4_rocm_compressor.cuh:54`  
  Con ratio 4, c=0 senza replay ignora la prima metà dei candidati
- **`compressor_set_rows_kernel`** `rocm/ds4_rocm_compressor.cuh:27`  
  Gli score destinazione non sono copie pure: ricevono sempre anche l'APE
- **`compressor_shift_ratio4_kernel`** `rocm/ds4_rocm_compressor.cuh:162`  
  Non è uno shift conservativo: sovrascrive entrambe le metà con gli stessi valori
- **`compressor_store_kernel`** `rocm/ds4_rocm_compressor.cuh:1`  
  Con ratio 4 scrive nelle righe ratio+fase, cioè nella metà alta dello stato
- **`compressor_update_pool_kernel`** `rocm/ds4_rocm_compressor.cuh:121`  
  Con ratio 4 fonde otto candidati presi da due metà e canali diversi
- **`configured_count`** `src/cuda/dynamic_arena.cu:1162`  
  Dopo l'allocazione ignora il valore stimato e usa la dimensione reale dell'arena
- **`copy_worker`** `src/cuda/dynamic_arena.cu:834`  
  Non esegue controlli di bounds prima di memcpy
- **`cublas_ok`** `rocm/ds4_rocm_runtime.cuh:5786`  
  Restituisce solo 0 o 1 e stampa lo status numerico, senza tradurlo.
- **`cuda_attention_score_buffer_fits`** `rocm/ds4_rocm_runtime.cuh:588`  
  La sottrazione unsigned va in underflow se le due capacità vengono definite al contrario.
- **`cuda_cublas_for_tier`** `ds4_cuda.cu:2676`  
  Un tier invalido ricade silenziosamente sull'handle del tier 0.
- **`cuda_current_tier`** `ds4_cuda.cu:29490`  
  Se cudaGetDevice fallisce ritorna silenziosamente il tier 0.
- **`cuda_decode_dispatch_env_refresh`** `ds4_cuda.cu:2184`  
  Quasi tutti i flag usano la sola presenza; NO_EXACT_SCORE_SPLIT_DIM2 prevale sul flag positivo.
- **`cuda_dynamic_arena_table_from_stream`** `ds4_cuda.cu:27485`  
  Con input nullo restituisce una struttura interamente azzerata.
- **`cuda_embed_row_stage_alloc`** `ds4_cuda.cu:2398`  
  Ogni resize sincronizza il device e scarta lo staging precedente prima del nuovo malloc.
- **`cuda_embed_row_stage_release`** `ds4_cuda.cu:2385`  
  Gli errori di free sono ignorati e il bookkeeping viene comunque azzerato.
- **`cuda_env_flag_enabled`** `ds4_cuda.cu:2856`  
  Solo la stringa esatta 0 disabilita; valori come false abilitano.
- **`cuda_iq1_s_sidecar_clear`** `ds4_cuda.cu:1737`  
  Non smappa host_base: azzera il riferimento e chiude solo il file.
- **`cuda_kv_staged_abort_locked`** `ds4_cuda.cu:15187`  
  Ignora l'esito del ripristino e restituisce sempre 0.
- **`cuda_kv_staged_append_comp_batches`** `ds4_cuda.cu:15308`  
  Conserva la stessa maschera globale con un offset logico per batch
- **`cuda_kv_staged_append_device`** `ds4_cuda.cu:15169`  
  Un errore disabilita staged KV in modo sticky e ripristina l'intera cache in VRAM.
- **`cuda_kv_staged_append_device_locked`** `ds4_cuda.cu:15117`  
  Il successo è asincrono: lascia append_pending e i dati host possono non essere ancora pronti.
- **`cuda_kv_staged_append_raw_batches`** `ds4_cuda.cu:15280`  
  Il giro del ring produce due span nello stesso batch
- **`cuda_kv_staged_append_selected_batch`** `ds4_cuda.cu:15327`  
  Indici negativi o fuori range vengono ignorati silenziosamente
- **`cuda_kv_staged_attention_batches_locked`** `ds4_cuda.cu:15355`  
  Un errore rende lo staging sticky-off e ripristina i dati sul device
- **`cuda_kv_staged_attention_launch`** `ds4_cuda.cu:15400`  
  Un layout non supportato disabilita lo staging e ripristina il KV sul device
- **`cuda_kv_staged_begin_locked`** `ds4_cuda.cu:5014`  
  La dipendenza dal produttore viene registrata sullo stream 0, non sullo stream del tensor.
- **`cuda_kv_staged_bind_view`** `ds4_cuda.cu:4856`  
  Restituisce 1 se lo staging non si applica, 2 se registra e 0 su errore.
- **`cuda_kv_staged_disable_and_restore`** `ds4_cuda.cu:5110`  
  Un singolo errore disabilita lo staging fino alla pulizia globale del registro.
- **`cuda_kv_staged_enqueue_batch_locked`** `ds4_cuda.cu:15230`  
  Il riuso dello slot inserisce una dipendenza evento sullo stream di copia
- **`cuda_kv_staged_event_spin_wait`** `ds4_cuda.cu:15194`  
  Occupa un core CPU senza sleep o yield finche l'evento non termina
- **`cuda_kv_staged_find_root_locked`** `ds4_cuda.cu:4788`  
  La ricerca è lineare nel numero di root.
- **`cuda_kv_staged_host`** `ds4_cuda.cu:4819`  
  Controlla solo il gate statico, non sticky_off, prima dei binding già esistenti.
- **`cuda_kv_staged_host_locked`** `ds4_cuda.cu:4796`  
  bytes uguale a 0 può riuscire ed è usato come test di presenza.
- **`cuda_kv_staged_host_quiesce`** `ds4_cuda.cu:4917`  
  Un accesso apparentemente host puo bloccare la CPU sullo stream CUDA.
- **`cuda_kv_staged_indexer_launch`** `ds4_cuda.cu:15463`  
  Un batch vuoto o un errore disabilita lo staging tramite abort
- **`cuda_kv_staged_migrate_to_host`** `ds4_cuda.cu:5125`  
  Un solo cudaFree fallito riabilita la VRAM, disabilita lo staging e annulla la migrazione.
- **`cuda_kv_staged_note_sticky_off_locked`** `ds4_cuda.cu:5023`  
  Dopo il primo errore le motivazioni successive non vengono stampate.
- **`cuda_kv_staged_prepare_compute_slot_locked`** `ds4_cuda.cu:15106`  
  Azzera append_pending dopo aver accodato l'attesa, senza sincronizzare la CPU.
- **`cuda_kv_staged_read_topk_locked`** `ds4_cuda.cu:15207`  
  La copia e asincrona, ma la funzione attende in spin prima di restituire
- **`cuda_kv_staged_rebuild_device_views_locked`** `ds4_cuda.cu:5034`  
  Una radice o un ptr nullo rende nulla anche la view senza segnalare errore.
- **`cuda_kv_staged_register_tensor`** `ds4_cuda.cu:4832`  
  Restituisce successo senza registrare se staging è disattivato, sticky-off o tensor è nullo.
- **`cuda_kv_staged_registry_release`** `ds4_cuda.cu:4946`  
  Azzera anche sticky-off e il flag che limita il log degli errori.
- **`cuda_kv_staged_restore_to_device`** `ds4_cuda.cu:5116`  
  Il normale request-end conserva l'arena host pinned; sticky-off invece tenta di liberarla.
- **`cuda_kv_staged_restore_to_device_locked`** `ds4_cuda.cu:5044`  
  Il fallimento di cudaFreeHost viene ignorato e la funzione restituisce comunque successo.
- **`cuda_kv_staged_ring_ensure_locked`** `ds4_cuda.cu:4959`  
  Crescere n_head impone cudaDeviceSynchronize e ricrea tutto il ring.
- **`cuda_kv_staged_ring_release`** `ds4_cuda.cu:4925`  
  Ignora tutti gli errori di distruzione e azzera comunque l'intera struttura.
- **`cuda_kv_staged_unregister_tensor`** `ds4_cuda.cu:4881`  
  L'ultima radice libera l'intera arena host pinned dopo aver sincronizzato lo stream.
- **`cuda_managed_kv_reserve_bytes`** `rocm/ds4_rocm_runtime.cuh:5924`  
  La riserva minima resta 8 GiB anche quando un quarto della VRAM e molto inferiore.
- **`cuda_matmul_q8_0_hc_expand_tensor_labeled`** `rocm/ds4_rocm_matmul.cuh:641`  
  I tre tensori di ownership sono obbligatori tutti insieme oppure tutti assenti
- **`cuda_matmul_q8_0_tensor_labeled`** `rocm/ds4_rocm_matmul.cuh:311`  
  Il fallimento della cache F16 ricade silenziosamente sui kernel Q8 nativi
- **`cuda_model_arena_alloc`** `rocm/ds4_rocm_runtime.cuh:5517`  
  Il primo cudaMalloc fallito imposta un blocco sticky che impedisce i tentativi successivi.
- **`cuda_model_arena_chunk_bytes`** `rocm/ds4_rocm_runtime.cuh:5508`  
  Il limite 8192 MiB non vale se need è maggiore: il blocco cresce fino a coprirlo.
- **`cuda_model_cache_limit_bytes`** `rocm/ds4_rocm_runtime.cuh:5438`  
  Zero, assente o non numerico significa nessun limite; l'ambiente è riletto ogni volta.
- **`cuda_model_copy_chunk_bytes`** `rocm/ds4_rocm_runtime.cuh:5290`  
  Valore assente o non valido usa 64 MiB; il risultato è limitato a 16-4096 MiB.
- **`cuda_model_copy_chunked`** `rocm/ds4_rocm_runtime.cuh:5669`  
  Alloca model_size intero anche quando map_size è solo un sottointervallo.
- **`cuda_model_copy_to_device_streamed`** `ds4_cuda.cu:4024`  
  Se fd o mapping non coincidono, usa cudaMemcpy sincrona dal mapping anziché il file.
- **`cuda_model_discard_source_pages`** `rocm/ds4_rocm_runtime.cuh:5294`  
  DS4_CUDA_KEEP_MODEL_PAGES presente disabilita lo scarto, qualunque sia il valore.
- **`cuda_model_drop_file_pages`** `rocm/ds4_rocm_runtime.cuh:5313`  
  DS4_CUDA_KEEP_MODEL_PAGES presente disabilita lo scarto, qualunque sia il valore.
- **`cuda_model_load_progress_enabled`** `rocm/ds4_rocm_runtime.cuh:5241`  
  La presenza di WEIGHT_CACHE_VERBOSE, anche con valore 0, disabilita questa telemetria.
- **`cuda_model_load_progress_note`** `rocm/ds4_rocm_runtime.cuh:5252`  
  Su TTY aggiorna ogni 2 GiB o 2 s; senza TTY ogni 16 GiB o 10 s.
- **`cuda_model_load_progress_reset`** `rocm/ds4_rocm_runtime.cuh:5245`  
  Il prossimo aggiornamento ricalcola il TTY e ristampa il messaggio iniziale.
- **`cuda_model_masked_budget_bytes`** `ds4_cuda.cu:6101`  
  Variabile assente vale UINT64_MAX; invalida vale 0 e avvisa una sola volta
- **`cuda_model_prefetch_range`** `ds4_cuda.cu:3386`  
  Su Windows restituisce sempre 0; altrove variabili presenti lo disabilitano senza errore.
- **`cuda_model_ptr`** `rocm/ds4_rocm_runtime.cuh:4555`  
  In sola modalità finestra, un offset al bordo ricade sul mapping host.
- **`cuda_model_range_is_cached`** `rocm/ds4_rocm_runtime.cuh:4690`  
  Un modello globalmente owned o registered fa restituire vero senza verificare mappa e range.
- **`cuda_model_range_ptr`** `rocm/ds4_rocm_runtime.cuh:4589`  
  Se mapping host e cache FD falliscono, alloca e copia silenziosamente il range in VRAM.
- **`cuda_model_range_ptr_from_fd`** `rocm/ds4_rocm_runtime.cuh:5569`  
  A budget esaurito cade sul puntatore host anche con DS4_CUDA_STRICT_WEIGHT_CACHE presente.
- **`cuda_model_range_release_all`** `rocm/ds4_rocm_runtime.cuh:5779`  
  Le slice arena_allocated si liberano solo insieme al blocco arena condiviso.
- **`cuda_model_register_mapping`** `ds4_cuda.cu:6127`  
  Errori di registrazione o lookup vengono trattati come successo senza mappatura
- **`cuda_model_stage_pool_alloc`** `rocm/ds4_rocm_runtime.cuh:5341`  
  Un errore parziale lascia risorse allocate fino alla chiamata o al rilascio successivo.
- **`cuda_model_stage_read`** `rocm/ds4_rocm_runtime.cuh:5404`  
  Solo alcuni errori O_DIRECT disattivano definitivamente il fd diretto e attivano il fallback.
- **`cuda_moe_expert_cache_lru_requested`** `ds4_cuda.cu:27811`  
  Legge l'env solo alla prima chiamata e accetta esclusivamente la stringa esatta lru.
- **`cuda_moe_expert_cache_stats_interval`** `ds4_cuda.cu:27819`  
  La sola presenza di STATS abilita; un intervallo invalido diventa 128 e resta statico.
- **`cuda_moe_io_queue_depth`** `ds4_cuda.cu:4014`  
  Rilegge l'ambiente a ogni chiamata; valori oltre 4 vengono troncati a 4.
- **`cuda_moe_prefill_vram_seed_floor_per_layer_requested`** `src/cuda/prefill_observer.cu:106`  
  A differenza delle altre quote, ammette esplicitamente lo zero.
- **`cuda_moe_prefill_vram_seed_per_layer_requested`** `src/cuda/prefill_observer.cu:96`  
  Accetta solo 0 oppure valori da 1 a 32; gli invalidi restituiscono -1.
- **`cuda_moe_prefill_vram_seed_total_requested`** `src/cuda/prefill_observer.cu:101`  
  Accetta solo 0 oppure valori da 1 a 512; gli invalidi restituiscono -1.
- **`cuda_moe_route_packed_copy_requested`** `ds4_cuda.cu:3726`  
  L'ambiente è letto una sola volta e solo il valore esatto 1 abilita.
- **`cuda_moe_route_prefetch_hint_requested`** `ds4_cuda.cu:3734`  
  L'ambiente è letto una sola volta e solo il valore esatto 1 abilita.
- **`cuda_ok`** `rocm/ds4_rocm_runtime.cuh:5229`  
  Stampa e restituisce 0, ma non interrompe l'esecuzione né pulisce lo stato CUDA.
- **`cuda_page_size`** `ds4_cuda.cu:1580`  
  Un valore nullo o errore della query ricade silenziosamente su 4096 byte.
- **`cuda_parse_mib_env`** `ds4_cuda.cu:2828`  
  Valori negativi o enormi saturano a UINT64_MAX; sintassi invalida equivale ad assenza.
- **`cuda_parse_u32_env_clamped`** `ds4_cuda.cu:2840`  
  Un numero valido fuori intervallo viene clampato, non sostituito dal fallback.
- **`cuda_pread_full`** `rocm/ds4_rocm_runtime.cuh:5389`  
  Su Windows una lettura corta fallisce subito; su POSIX EINTR viene ritentato.
- **`cuda_prefill_union_stats_report_and_reset`** `ds4_cuda.cu:1866`  
  Azzera sempre le statistiche, anche quando non stampa alcun report.
- **`cuda_q1_0_sidecar_clear`** `ds4_cuda.cu:1748`  
  Non smappa host_base: azzera il riferimento e chiude solo il file.
- **`cuda_q4_mma_ok`** `ds4_cuda.cu:1983`  
  La presenza di DS4_CUDA_MOE_NO_Q4_MMA disabilita; l'ambiente è letto una sola volta.
- **`cuda_q4_mma_tile16_shmem_ok`** `ds4_cuda.cu:24615`  
  Un solo errore imposta failed statico e disabilita entrambe le varianti su tutti i device
- **`cuda_q8_exact_threads`** `ds4_cuda.cu:3058`  
  Anche zero blocchi produce 64 thread; ogni valore oltre 128 ne produce 256.
- **`cuda_q8_f16_cache_allowed`** `rocm/ds4_rocm_runtime.cuh:4972`  
  Quality mode e soppressione prevalgono anche sull'override Q8_F16_ALL.
- **`cuda_q8_f16_cache_budget_notice`** `rocm/ds4_rocm_runtime.cuh:4882`  
  Senza verbose stampa una sola volta globale; con verbose stampa ogni rifiuto.
- **`cuda_q8_f16_cache_disable_after_failure`** `rocm/ds4_rocm_runtime.cuh:4955`  
  Un solo errore di allocazione o launch disabilita definitivamente la cache fino al reset globale.
- **`cuda_q8_f16_cache_has_budget`** `rocm/ds4_rocm_runtime.cuh:4923`  
  Il limite cached è globale tra GPU, ma la VRAM libera è misurata solo sul device corrente.
- **`cuda_q8_f16_cache_limit_bytes`** `rocm/ds4_rocm_runtime.cuh:4833`  
  Variabile assente o invalida significa nessun limite; il valore esplicito 0 disabilita la cache.
- **`cuda_q8_f16_cache_release_all`** `rocm/ds4_rocm_runtime.cuh:4716`  
  Ignora gli errori di cudaFree ma elimina i riferimenti, rendendo invisibili eventuali leak.
- **`cuda_q8_f16_cache_reserve_bytes`** `rocm/ds4_rocm_runtime.cuh:4865`  
  Sotto 40 GiB riserva almeno 4 GiB; un override esplicito può invece impostare anche zero.
- **`cuda_q8_f16_preload_allowed`** `rocm/ds4_rocm_runtime.cuh:5007`  
  Gli output attenzione richiedono opt-in al preload anche quando la cache lazy sarebbe ammessa.
- **`cuda_q8_f16_ptr`** `rocm/ds4_rocm_runtime.cuh:5015`  
  Un errore di malloc o launch elimina tutta la cache fp16 e forza i kernel q8 successivi.
- **`cuda_q8_f32_cache_allowed`** `ds4_cuda.cu:3073`  
  A differenza della fp16 non applica quality mode né limite o budget di VRAM.
- **`cuda_q8_f32_ptr`** `ds4_cuda.cu:3212`  
  A differenza della fp16, un fallimento non disabilita né svuota globalmente la cache fp32.
- **`cuda_q8_label_is_attention_output`** `rocm/ds4_rocm_runtime.cuh:4999`  
  Usa sottostringhe, quindi può classificare anche label più lunghe non canoniche.
- **`cuda_q8_mma_try_launch`** `ds4_cuda.cu:8705`  
  Env letto una volta; un errore di attributo disabilita il percorso per tutto il processo.
- **`cuda_q8_use_dp4a`** `ds4_cuda.cu:3054`  
  La sola presenza di DS4_CUDA_NO_Q8_DP4A, anche con valore 0, lo disabilita.
- **`cuda_resolve_weight_ptr`** `ds4_cuda.cu:2750`  
  In multi-GPU non fa fallback host; prova però il device corrente prima di restituire NULL.
- **`cuda_saturating_add_u64`** `ds4_cuda.cu:1857`  
  In overflow restituisce UINT64_MAX invece di segnalare errore.
- **`cuda_saturating_mul_u64`** `ds4_cuda.cu:1861`  
  In overflow restituisce UINT64_MAX invece di segnalare errore.
- **`cuda_selected_readback_consumer_fence`** `ds4_cuda.cu:33732`  
  UINT64_MAX è considerato già completato e non sincronizza.
- **`cuda_selected_readback_consumer_sync_enter`** `ds4_cuda.cu:33726`  
  Hook vuoto sul backend CUDA.
- **`cuda_selected_readback_consumer_sync_exit`** `ds4_cuda.cu:33729`  
  Hook vuoto sul backend CUDA.
- **`cuda_selected_readback_events_create`** `ds4_cuda.cu:33671`  
  Se la seconda creazione fallisce distrugge la prima ma non marca events_created.
- **`cuda_selected_readback_events_destroy`** `ds4_cuda.cu:33773`  
  Ignora il fallimento del drain e azzera comunque le generazioni.
- **`cuda_selected_readback_events_ready`** `ds4_cuda.cu:33665`  
  Richiede sia il flag sia entrambi gli handle non nulli.
- **`cuda_selected_readback_outstanding`** `ds4_cuda.cu:33690`  
  Conta slot di parità occupati, non la distanza fra generazioni.
- **`cuda_selected_readback_poll`** `ds4_cuda.cu:33706`  
  Un errore di query pulisce l'ultimo errore CUDA e interrompe il polling dell'altro slot.
- **`cuda_selected_readback_retire`** `ds4_cuda.cu:33695`  
  Parità o generazione discordanti vengono ignorate senza segnalazione.
- **`cuda_selected_readback_tail_retire`** `ds4_cuda.cu:33756`  
  Al primo errore interrompe il drain e lascia eventuali altri slot armati.
- **`cuda_splitkv_decode_requested`** `ds4_cuda.cu:2874`  
  NO_SPLITKV prevale sia sul fast mode sia su SPLITKV_DECODE.
- **`cuda_stream_dynamic_arena_copy_hit`** `ds4_cuda.cu:28347`  
  Qualunque errore H2D diventa un miss; il chiamante ricarica dalla sorgente esatta.
- **`cuda_stream_expert_cache_adapter_begin_load`** `ds4_cuda.cu:29369`  
  La cache residente è usata solo con n_tokens uguale a 1; il prefill non promuove slot.
- **`cuda_stream_expert_cache_adapter_current_count`** `ds4_cuda.cu:29454`  
  Se la cache residente è abilitata, non consulta l'arena anche quando conta zero.
- **`cuda_stream_expert_cache_adapter_release`** `ds4_cuda.cu:28929`  
  La release stampa e azzera anche le statistiche di unione prefill.
- **`cuda_stream_expert_cache_policy_budget`** `ds4_cuda.cu:27605`  
  Con cache VRAM attiva, una config nulla o zero restituisce capacità zero.
- **`cuda_stream_expert_cache_policy_choose_victim`** `ds4_cuda.cu:27660`  
  Allocazioni o eccezioni della policy diventano silenziosamente nessuna vittima.
- **`cuda_stream_expert_cache_policy_note_hotness`** `ds4_cuda.cu:27636`  
  È invocata via puntatore di funzione; qualsiasi eccezione viene ignorata.
- **`cuda_stream_expert_cache_policy_release`** `ds4_cuda.cu:27735`  
  Non libera la cache residente VRAM, che ha un teardown separato.
- **`cuda_stream_expert_cache_policy_reset_hotness`** `ds4_cuda.cu:27717`  
  Gli errori del reset sono inghiottiti e non vengono propagati al chiamante.
- **`cuda_stream_expert_cache_policy_seed`** `ds4_cuda.cu:27700`  
  Se l'arena dinamica è disabilitata restituisce successo senza seminare nulla.
- **`cuda_stream_resident_cache_capacity`** `ds4_cuda.cu:28026`  
  Passando 0,0 accetta qualsiasi taglia; una sola differenza restituisce capacità zero.
- **`cuda_stream_resident_cache_copy_hit`** `ds4_cuda.cu:28262`  
  Un errore D2D invalida lo slot e diventa un miss per attivare il fallback.
- **`cuda_stream_resident_cache_current_count`** `ds4_cuda.cu:28045`  
  Se il buffer packed è nullo restituisce zero anche se count non lo è.
- **`cuda_stream_resident_cache_next_age_locked`** `ds4_cuda.cu:27834`  
  Arrivata a UINT64_MAX l'età resta saturata e non avanza più.
- **`cuda_stream_resident_cache_note_call`** `ds4_cuda.cu:27841`  
  Con statistiche disabilitate non aggiorna neppure i contatori di chiamata e load diretto.
- **`cuda_stream_resident_cache_prepare_locked`** `ds4_cuda.cu:28067`  
  Su errore di allocazione dimezza gli slot; a capacità zero il log è una tantum.
- **`cuda_stream_resident_cache_promote`** `ds4_cuda.cu:28387`  
  Sincronizza l'intero device dopo ogni esperto copiato, prima di pubblicare lo slot.
- **`cuda_stream_resident_cache_recovery_complete`** `ds4_cuda.cu:28748`  
  Con sequenza diversa ritorna senza segnalare né pulire.
- **`cuda_stream_resident_cache_release`** `rocm/ds4_rocm_runtime.cuh:648`  
  Tiene il mutex mentre l'helper sincronizza l'intero device prima di liberare.
- **`cuda_stream_resident_cache_release_locked`** `ds4_cuda.cu:28007`  
  Ignora gli errori di synchronize e cudaFree, poi azzera comunque tutto lo stato.
- **`cuda_stream_resident_cache_scoped_invalidate`** `ds4_cuda.cu:28760`  
  Le promozioni già commit restano residenti e vengono conservate per il retry.
- **`cuda_stream_resident_cache_telemetry_snapshot`** `ds4_cuda.cu:28051`  
  Senza buffer packed azzera capacità, count e byte, ma conserva gli slot richiesti.
- **`cuda_stream_resident_key_equal`** `ds4_cuda.cu:27968`  
  Confronta l'indirizzo model_map, non il contenuto del modello.
- **`cuda_stream_resident_key_make`** `ds4_cuda.cu:27950`  
  Con tabella nulla restituisce la chiave predefinita e ignora expert.
- **`cuda_stream_resident_reserve_bytes`** `ds4_cuda.cu:27983`  
  Zero è valido e rimuove la riserva; un valore invalido avvisa una sola volta e usa 0,5 GiB.
- **`cuda_stream_resident_route_key`** `ds4_cuda.cu:27870`  
  Concatena layer ed expert in 32+32 bit: non applica hashing.
- **`cuda_stream_resident_sizing_policy_read`** `ds4_cuda.cu:27926`  
  Riserve e minimo contano solo con INVERTED_PRIORITY esattamente uguale a 1.
- **`cuda_stream_route_worker_handle`** `ds4_cuda.cu:28808`  
  Registra la hotness prima di cudaSetDevice e anche se la promozione poi fallisce.
- **`cuda_stream_route_worker_submit`** `ds4_cuda.cu:28865`  
  Copia ID e pesi, ma conserva solo puntatori VRAM ai tre piani compatti.
- **`cuda_stream_router_capture_output`** `ds4_cuda.cu:2096`  
  Fa due copie D2H sincrone; oltre 64 record espelle in silenzio il più vecchio.
- **`cuda_stream_router_capture_release`** `ds4_cuda.cu:2091`  
  Libera memoria host, non la VRAM dei tensori catturati.
- **`cuda_stream_router_capture_take`** `ds4_cuda.cu:27502`  
  Alla corrispondenza sposta i pesi nel risultato e cancella definitivamente la cattura.
- **`cuda_stream_selected_cache_invalidate`** `ds4_cuda.cu:1897`  
  Non libera puntatori o capacità VRAM della cache selected.
- **`cuda_stream_selected_cache_release_at_decode_start`** `ds4_cuda.cu:2046`  
  DS4_CUDA_RELEASE_PREFILL_COMPACT=0 disabilita; assente o vuota lascia attivo il rilascio.
- **`cuda_stream_selected_cache_transport_begin_load`** `ds4_cuda.cu:29056`  
  Con SSD streaming spento invalida lo stato e ritorna successo senza caricare.
- **`cuda_stream_selected_cache_transport_release`** `ds4_cuda.cu:1936`  
  Ignora errori di set-device e cudaFree, poi cancella comunque lo stato.
- **`cuda_stream_selected_capacity_bytes`** `ds4_cuda.cu:1902`  
  Satura a UINT64_MAX, mascherando un eventuale overflow della somma.
- **`cuda_stream_selected_ensure_bytes`** `ds4_cuda.cu:28942`  
  Libera prima il vecchio buffer: se cudaMalloc fallisce, la capacità precedente è persa.
- **`cuda_stream_selected_fill_spans_overlapped`** `ds4_cuda.cu:3865`  
  Sincronizza prima del ritorno; al fallimento il chiamante ripete tutto in seriale.
- **`cuda_stream_selected_io_cancel_pending`** `ds4_cuda.cu:3838`  
  Aspetta ogni richiesta annullata con GetOverlappedResult bloccante.
- **`cuda_stream_selected_io_events_ensure`** `ds4_cuda.cu:3823`  
  Un errore dopo creazioni parziali lascia nel pool gli eventi già creati.
- **`cuda_stream_selected_prefetch_hint`** `ds4_cuda.cu:4018`  
  API risolta una volta; assenza o errore vengono ignorati e registrati una sola volta.
- **`cuda_stream_selected_stage_pool_alloc`** `ds4_cuda.cu:3678`  
  Una richiesta più grande distrugge l'intero pool prima di tentare quello nuovo.
- **`cuda_stream_selected_stage_release`** `rocm/ds4_rocm_runtime.cuh:1020`  
  Non sincronizza stream o I/O prima di distruggere le risorse.
- **`cuda_stream_selected_weight_storage_prepare`** `ds4_cuda.cu:28962`  
  Se packed fallisce ripiega su tre allocazioni; il mismatch viene loggato una sola volta.
- **`cuda_stream_selected_weight_storage_release`** `ds4_cuda.cu:1912`  
  Non libera slot_selected_ptr; il remap resta allocato.
- **`cuda_tensor_has_staged_host`** `ds4_cuda.cu:4828`  
  Usa una lookup di zero byte: verifica il binding, non l'estensione del tensore.
- **`cuda_tmp_alloc`** `rocm/ds4_rocm_runtime.cuh:567`  
  Prima del grow libera il vecchio buffer: se cudaMalloc fallisce, lo scratch è perso.
- **`cuda_tmp_alloc_on`** `ds4_cuda.cu:2463`  
  Un grow fallito perde il vecchio scratch; in single-GPU usa un buffer globale distinto.
- **`cuda_vram_exact_one`** `ds4_cuda.cu:27875`  
  Valori come true o 01 sono falsi; la variabile viene riletta a ogni chiamata.
- **`cuda_vram_prio_env_mb`** `ds4_cuda.cu:27880`  
  Un valore invalido stampa un warning a ogni chiamata, poi usa il fallback.
- **`cuda_vram_prio_env_slots`** `ds4_cuda.cu:27898`  
  Un valore fuori intervallo non viene limitato: genera warning e torna al fallback.
- **`cuda_wall_sec`** `rocm/ds4_rocm_runtime.cuh:5235`  
  Nonostante il nome wall, restituisce tempo monotono e non l'ora civile.
- **`cuda_xdev_env_refresh`** `ds4_cuda.cu:2178`  
  Conta la sola presenza: anche un valore 0 abilita ciascun flag.
- **`current_count`** `src/cuda/dynamic_arena.cu:1169`  
  Conta esperti pubblicati, non slot allocati
- **`dev_dequant_iq1_s_value`** `ds4_cuda.cu:20449`  
  È marcata unused e nel file serve solo al test condizionale DS4_IQ1_TEST_API
- **`dev_dequant_q1_0_value`** `ds4_cuda.cu:20495`  
  Non ha chiamanti ed è marcata unused
- **`dev_dot_iq1_s_q8_K_block`** `ds4_cuda.cu:20467`  
  La correzione delta usa le somme Q8 precomputate, non solo i valori quantizzati
- **`dev_dot_iq2_pair_16`** `rocm/ds4_rocm_moe.cuh:46`  
  I byte grid indicizzano direttamente una LUT globale
- **`dev_dot_iq2_xxs_q8_K_block`** `rocm/ds4_rocm_moe.cuh:101`  
  Applica un fattore fisso 0.125 al prodotto scalato
- **`dev_dot_iq2_xxs_q8_K_block4`** `rocm/ds4_rocm_moe.cuh:174`  
  Aggiorna acc in-place invece di restituire i quattro risultati
- **`dev_dot_iq2_xxs_q8_K_block8`** `rocm/ds4_rocm_moe.cuh:211`  
  È marcata unused e non ha chiamanti
- **`dev_dot_iq2_xxs_q8_K_block8_deq_lut`** `rocm/ds4_rocm_moe.cuh:125`  
  I puntatori oltre n possono essere nulli, ma uno nullo entro n causa accesso invalido
- **`dev_dot_iq2_xxs_q8_K_block_lut`** `rocm/ds4_rocm_moe.cuh:68`  
  Applica al risultato il fattore fisso 0.125 oltre alle scale dei blocchi
- **`dev_dot_q1_0_q8_K_half128`** `ds4_cuda.cu:20502`  
  Ricava i valori negativi sottraendo la somma totale Q8
- **`dev_dot_q1_0_q8_K_pair`** `ds4_cuda.cu:20527`  
  Il blocco Q8_K è condiviso fra due blocchi Q1_0 distinti
- **`dev_dot_q2_16`** `rocm/ds4_rocm_moe.cuh:36`  
  Interpreta entrambi gli ingressi a gruppi di int32
- **`dev_dot_q2_K_q8_K_block`** `rocm/ds4_rocm_moe.cuh:355`  
  Il termine dei minimi dipende dalle bsums già presenti nel blocco Q8_K
- **`dev_dot_q2_K_q8_K_block4`** `rocm/ds4_rocm_moe.cuh:381`  
  Non controlla n e aggiorna acc in-place
- **`dev_dot_q2_K_q8_K_block8`** `rocm/ds4_rocm_moe.cuh:421`  
  Non controlla n e aggiorna acc in-place
- **`dev_dot_q4_32`** `rocm/ds4_rocm_moe.cuh:264`  
  Legge qs in parole int32 e maschera i nibble senza dequantizzare in float
- **`dev_dot_q4_K_q8_K_block`** `rocm/ds4_rocm_moe.cuh:274`  
  Sottrae separatamente il contributo dei minimi tramite le bsums Q8
- **`dev_dot_q4_K_q8_K_block8`** `rocm/ds4_rocm_moe.cuh:321`  
  Aggiorna acc in-place e non controlla n né puntatori
- **`dev_dot_q4_K_q8_K_block_vec`** `ds4_cuda.cu:20707`  
  Un input non allineato viola il requisito dei carichi uint4
- **`dev_f16_to_f32`** `rocm/ds4_rocm_moe.cuh:10`  
  Reinterpreta i bit tramite puntatore a __half, non converte numericamente uint16_t
- **`dev_iq2_dp4a_8`** `rocm/ds4_rocm_moe.cuh:25`  
  Usa due carichi int32 e istruzioni packed CUDA specifiche
- **`dev_iq2_i8x8_lut`** `rocm/ds4_rocm_moe.cuh:53`  
  Restituisce pesi packed in int32, non un array di otto int8
- **`dev_iq2_xxs_dot_f32`** `rocm/ds4_rocm_moe.cuh:4282`  
  Usa LUT globali per griglie e segni, non valori autosufficienti nel blocco
- **`dev_q2_K_dot_f32`** `rocm/ds4_rocm_moe.cuh:4317`  
  Ignora qualsiasi coda se la dimensione non è multipla di 256
- **`dev_q4_K_get_scale_min`** `rocm/ds4_rocm_moe.cuh:250`  
  Per j da 4 a 7 ricompone i valori da nibble e bit alti in byte diversi
- **`dev_unpack_iq2_signs`** `rocm/ds4_rocm_moe.cuh:19`  
  Il bit di parità viene reiniettato nel bit 7 prima della replica
- **`directional_steering_project_kernel`** `rocm/ds4_rocm_output.cuh:53`  
  Modifica x in place; è una vera proiezione solo con direzione normalizzata.
- **`dot4_f32`** `rocm/ds4_rocm_common.cuh:396`  
  Non usa FMA esplicite: l'ordine delle quattro somme dipende dal compilatore CUDA.
- **`dot_i8_block`** `rocm/ds4_rocm_q8.cuh:31`  
  Anche con use_dp4a attivo, ogni lunghezza diversa da 32 ricade sul ciclo scalare.
- **`dot_i8x32_dp4a`** `rocm/ds4_rocm_q8.cuh:22`  
  a usa load non allineate, b usa dereferenziazioni int32 allineate.
- **`ds4_alloc_basename`** `ds4_cuda.cu:475`  
  Restituisce un puntatore dentro path, non una copia; per NULL restituisce ?.
- **`ds4_alloc_note`** `ds4_cuda.cu:495`  
  La label pendente si applica solo alle allocazioni managed e viene comunque cancellata.
- **`ds4_alloc_release`** `ds4_cuda.cu:572`  
  Un puntatore sconosciuto non genera errore: incrementa solo un contatore.
- **`ds4_alloc_site_live_greater`** `ds4_cuda.cu:795`  
  A parità di byte vivi usa il picco, non i byte cumulativi.
- **`ds4_alloc_site_tag`** `ds4_cuda.cu:484`  
  Per le label conserva solo il basename e perde il percorso originale.
- **`ds4_alloc_tracked_vram_live`** `ds4_cuda.cu:6936`  
  Se alloc_trace e' spento restituisce 0 anche con VRAM realmente occupata
- **`ds4_compute_layer_placement`** `ds4_layer_pack.c:14`  
  Dopo il primo spill su CPU, tutti gli elementi successivi restano su CPU; un fit esatto passa.
- **`ds4_cuda_env_double`** `ds4_cuda.cu:103`  
  Zero è valido; negativi, NaN e infiniti producono un warning e il fallback.
- **`ds4_cuda_env_enabled`** `ds4_cuda.cu:82`  
  Qualunque valore non vuoto diverso da 0 abilita, inclusi false e stringhe arbitrarie.
- **`ds4_cuda_env_u64`** `ds4_cuda.cu:87`  
  Accetta spazi iniziali e il segno + perché usa strtoull.
- **`ds4_cuda_telemetry_env_refresh`** `ds4_cuda.cu:118`  
  Dopo il primo richiamo ignora ogni modifica alle variabili d'ambiente.
- **`ds4_dot512_float4_ordered`** `ds4_cuda.cu:10548`  
  Impedisce la contrazione FMA, quindi può differire dalla variante plain
- **`ds4_dot512_float4_plain`** `ds4_cuda.cu:10566`  
  Il compilatore può contrarre dot += prodotto in FMA e cambiare gli ultimi bit
- **`ds4_dot_scalar_ldg`** `ds4_cuda.cu:10154`  
  __ldg presume dati di sola lettura durante il kernel
- **`ds4_gpu_add3_tensor`** `rocm/ds4_rocm_misc_launch.cuh:37`  
  Controlla solo i byte, non il tipo né il device dei tensori.
- **`ds4_gpu_add_rms_norm_weight_tensor`** `rocm/ds4_rocm_norm_rope.cuh:451`  
  Interpreta sempre il peso come float32 e non offre fallback agli operatori separati.
- **`ds4_gpu_add_xdev_tensor`** `ds4_cuda.cu:20153`  
  Con n uguale a 0 restituisce 1 prima di verificare la coerenza dei device
- **`ds4_gpu_alloc_site_label`** `ds4_cuda.cu:801`  
  Una allocazione non-managed cancella la label senza usarla.
- **`ds4_gpu_alloc_trace_mark`** `ds4_cuda.cu:805`  
  Se cudaMemGetInfo fallisce stampa comunque valori iniziali pari a zero.
- **`ds4_gpu_alloc_trace_summary`** `ds4_cuda.cu:829`  
  Ordina i siti per byte vivi e poi picco, non per consumo cumulativo.
- **`ds4_gpu_argmax_tensor`** `rocm/ds4_rocm_indexer.cuh:1088`  
  A parità vince l'indice minore.
- **`ds4_gpu_args_probe_auto_cuda`** `ds4_rocm_compat.cu:136`  
  Cambia il device CUDA corrente durante il probe e non lo ripristina.
- **`ds4_gpu_attention_decode_heads_rope_tensor`** `ds4_cuda.cu:18734`  
  Azzera fused_inv_rope anche quando ripiega sul percorso standard
- **`ds4_gpu_attention_decode_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:27`  
  Score troppo grande fallisce salvo il percorso online non mascherato con head_dim 512
- **`ds4_gpu_attention_decode_mixed_batch_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:327`  
  Il parametro comp_kv_f16 esiste ma se vero la funzione rifiuta la chiamata
- **`ds4_gpu_attention_decode_raw_batch_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:306`  
  Imposta ratio a 1 anche senza cache compressa
- **`ds4_gpu_attention_decode_rows_rope_tensor`** `ds4_cuda.cu:18836`  
  Qualunque tuning exact-score via ambiente fa restituire 0 senza fallback interno
- **`ds4_gpu_attention_indexed_mixed_batch_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:355`  
  Per top_k 512 e più token ordina una copia degli indici salvo variabile di disabilitazione
- **`ds4_gpu_attention_noncausal_raw_batch_heads_tensor`** `ds4_cuda.cu:17504`  
  Il flag di verifica e letto una volta e sincronizza solo le prime tre chiamate
- **`ds4_gpu_attention_output_low_q4_K_slice_tensor`** `ds4_cuda.cu:34244`  
  Ignora tutti gli argomenti e restituisce 0: il percorso Q4_K fallisce senza scrivere low
- **`ds4_gpu_attention_output_low_q8_rows_exact_tensor`** `ds4_cuda.cu:19879`  
  Quantizza gli head in scratch ma lascia l'output low in float
- **`ds4_gpu_attention_output_low_q8_tensor`** `rocm/ds4_rocm_attention_launch.cuh:1258`  
  Fissa sempre n_rows a 1 e seleziona tutti i gruppi
- **`ds4_gpu_attention_output_q4_K_batch_tensor`** `ds4_cuda.cu:34230`  
  Restituisce 0 in silenzio e lascia gli output invariati.
- **`ds4_gpu_attention_output_q8_batch_f16_tensor`** `rocm/ds4_rocm_attention_launch.cuh:845`  
  Restituisce 0 in silenzio e lascia out_h invariato.
- **`ds4_gpu_attention_output_q8_batch_tensor`** `rocm/ds4_rocm_attention_launch.cuh:953`  
  I parametri group_tmp e low_tmp vengono ignorati completamente
- **`ds4_gpu_attention_output_q8_tp_tensor`** `ds4_rocm.cu:193`  
  Elabora sempre una sola riga e non accetta slice Q8 non allineate a 32
- **`ds4_gpu_attention_prefill_masked_mixed_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:824`  
  Non ha chiamanti nel grafo estratto
- **`ds4_gpu_attention_prefill_raw_heads_range_tensor`** `ds4_cuda.cu:34192`  
  Restituisce sempre 0 senza log.
- **`ds4_gpu_attention_prefill_raw_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:115`  
  Fuori quality mode il kernel window si attiva automaticamente da 128 token
- **`ds4_gpu_attention_prefill_static_mixed_heads_range_tensor`** `ds4_cuda.cu:34204`  
  Restituisce sempre 0 senza log.
- **`ds4_gpu_attention_prefill_static_mixed_heads_tensor`** `rocm/ds4_rocm_attention_launch.cuh:803`  
  comp_kv_f16 è accettato come parametro ma il valore vero viene rifiutato
- **`ds4_gpu_attn_q_b_f16_head_rms_rope_tail_tensor`** `rocm/ds4_rocm_norm_rope.cuh:532`  
  Restituisce 0 in silenzio senza toccare out o q_half.
- **`ds4_gpu_begin_commands`** `rocm/ds4_rocm_runtime.cuh:6019`  
  E' un no-op che restituisce sempre 1
- **`ds4_gpu_cache_model_range`** `rocm/ds4_rocm_runtime.cuh:6276`  
  Mappa nulla o zero byte restituiscono successo senza caricare nulla
- **`ds4_gpu_cache_q8_f16_range`** `rocm/ds4_rocm_runtime.cuh:6283`  
  Il primo preload fallito disabilita staticamente i successivi ma restituisce 1
- **`ds4_gpu_cleanup`** `rocm/ds4_rocm_runtime.cuh:5817`  
  Ignora tutti gli errori di sincronizzazione, distruzione e rilascio.
- **`ds4_gpu_commands_active`** `rocm/ds4_rocm_runtime.cuh:6022`  
  Ritorna sempre false: il percorso CUDA non accumula command buffer.
- **`ds4_gpu_commit_and_wait_selected_readback`** `rocm/ds4_rocm_runtime.cuh:6049`  
  Non esegue un commit distinto: su CUDA equivale al solo wait.
- **`ds4_gpu_compressor_prefill_ratio4_replay_tensor`** `rocm/ds4_rocm_compressor.cuh:436`  
  Azzera lo stato e lo ricostruisce soltanto dalle ultime quattro righe
- **`ds4_gpu_compressor_prefill_state_ratio4_tensor`** `rocm/ds4_rocm_compressor.cuh:519`  
  Azzera sempre tutto lo stato prima di caricare la coda
- **`ds4_gpu_compressor_prefill_tensor`** `rocm/ds4_rocm_compressor.cuh:324`  
  Se la cache era migrata disabilita lo staging e la ripristina su device
- **`ds4_gpu_compressor_update_tensor`** `rocm/ds4_rocm_compressor.cuh:239`  
  Se il token non chiude il gruppo restituisce 1 senza scrivere la cache compressa
- **`ds4_gpu_cuda_request_begin`** `ds4_cuda.cu:33994`  
  Non azzera la hotness SSD, che ha un reset separato.
- **`ds4_gpu_device_cache_support_tensors`** `ds4_cuda.cu:6573`  
  Le entry possono dichiarare un device diverso da quello fisico della slab
- **`ds4_gpu_device_cache_tensors`** `ds4_cuda.cu:6419`  
  Un errore H2D puo' lasciare la slab cresciuta senza rollback
- **`ds4_gpu_directional_steering_project_tensor`** `rocm/ds4_rocm_misc_launch.cuh:58`  
  scale 0 restituisce errore anziché fare no-op; il lancio usa stream e device correnti
- **`ds4_gpu_dspark_markov_argmax_tensor`** `ds4_cuda.cu:15672`  
  Cambia device CUDA per il tier dei logit e poi tenta di ripristinarlo
- **`ds4_gpu_dsv4_fp8_kv_quantize_tensor`** `rocm/ds4_rocm_fp8_kv_launch.cuh:1`  
  Il risultato resta float dequantizzato, non un buffer FP8 impacchettato
- **`ds4_gpu_dsv4_indexer_qat_tensor`** `rocm/ds4_rocm_indexer.cuh:1125`  
  I valori FP4 sono subito dequantizzati e riscritti come float
- **`ds4_gpu_dsv4_qkv_rms_norm_rows_kv_rope_tensor`** `ds4_rocm_compat.cu:236`  
  Con la fusione QKV disabilitata restituisce 0 senza fallback
- **`ds4_gpu_dsv4_qkv_rms_norm_rows_tensor`** `rocm/ds4_rocm_norm_rope.cuh:471`  
  Se la fusione è disabilitata ripiega su due RMSNorm separate
- **`ds4_gpu_dsv4_topk_mask_tensor`** `rocm/ds4_rocm_indexer.cuh:1105`  
  Un solo kernel inizializza la maschera e marca gli indici
- **`ds4_gpu_embed_token_hc_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:1`  
  La mera presenza dell'env abilita staging; solo lì un token invalido viene rimappato a 0.
- **`ds4_gpu_embed_token_q8_0_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:115`  
  Il codice numerico 8 è fissato internamente come tipo Q8_0.
- **`ds4_gpu_embed_token_quant_tensor`** `ds4_rocm_compat.cu:255`  
  Supporta soltanto Q8_0; ogni altro tipo fallisce dopo un log.
- **`ds4_gpu_embed_tokens_hc_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:17`  
  Con env presente legge gli ID D2H e ricarica righe H2D; anche il valore 0 abilita.
- **`ds4_gpu_embed_tokens_q8_0_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:133`  
  Gli ID nel tensor tokens non vengono validati prima del kernel.
- **`ds4_gpu_embed_tokens_quant_tensor`** `ds4_rocm_compat.cu:265`  
  Non controlla i valori del tensore tokens, solo la sua dimensione in byte.
- **`ds4_gpu_enable_q8_dequant_gemm`** `ds4_rocm_compat.cu:187`  
  Il flag viene solo acceso e non esiste qui un percorso per spegnerlo
- **`ds4_gpu_end_commands`** `rocm/ds4_rocm_runtime.cuh:6059`  
  g_cuda_end_stream_sync cambia la barriera da device globale a solo stream 0
- **`ds4_gpu_flush_commands`** `rocm/ds4_rocm_runtime.cuh:6020`  
  Il flush blocca l'intero device, non solo uno stream
- **`ds4_gpu_flush_encoder`** `rocm/ds4_rocm_runtime.cuh:6021`  
  È un no-op che restituisce sempre successo perché CUDA usa l'ordine dello stream.
- **`ds4_gpu_glm_attention_flash_staged_tensor`** `rocm/ds4_rocm_glm.cuh:1684`  
  Stampa su stderr e ritorna sempre 0 senza leggere o scrivere i tensori.
- **`ds4_gpu_glm_attention_flash_tensor`** `rocm/ds4_rocm_glm.cuh:1702`  
  Stampa su stderr e ritorna sempre 0 senza leggere o scrivere i tensori.
- **`ds4_gpu_glm_attention_full_tensor`** `rocm/ds4_rocm_glm.cuh:1640`  
  Stampa su stderr e ritorna sempre 0 senza leggere o scrivere i tensori.
- **`ds4_gpu_glm_attention_indexed_batch_lora_causal_tensor`** `rocm/ds4_rocm_glm.cuh:3381`  
  Non verifica i byte dei tensori né che cache_cap sia diverso da zero.
- **`ds4_gpu_glm_attention_indexed_batch_lora_valid_tensor`** `rocm/ds4_rocm_glm.cuh:3412`  
  Gli indici selected fuori cache vengono ignorati silenziosamente dal kernel.
- **`ds4_gpu_glm_attention_indexed_batch_typed_tensor`** `ds4_rocm_compat.cu:371`  
  Stampa su stderr e ritorna sempre 0 senza leggere o scrivere i tensori.
- **`ds4_gpu_glm_attention_indexed_decode_split_group8_typed_tensor`** `ds4_cuda.cu:30072`  
  Stampa su stderr e restituisce sempre 0.
- **`ds4_gpu_glm_attention_indexed_decode_typed_tensor`** `ds4_rocm_compat.cu:351`  
  Da 512 righe, se lo scratch non si alloca restituisce 0 senza fallback fuso.
- **`ds4_gpu_glm_build_kv_cache_flash_tensor`** `rocm/ds4_rocm_glm.cuh:1609`  
  Stampa su stderr e restituisce sempre 0.
- **`ds4_gpu_glm_build_kv_cache_tensor`** `rocm/ds4_rocm_glm.cuh:1545`  
  Stampa su stderr e restituisce sempre 0.
- **`ds4_gpu_glm_fill_selected_range_batch_tensor`** `rocm/ds4_rocm_glm.cuh:1727`  
  Il wrapper usa uint64_t, ma il kernel ricalcola total in uint32_t.
- **`ds4_gpu_glm_fill_selected_range_tensor`** `rocm/ds4_rocm_glm.cuh:1720`  
  Input non valido restituisce 0 senza diagnostica.
- **`ds4_gpu_glm_indexer_rope_tail_tensor`** `rocm/ds4_rocm_glm.cuh:1753`  
  Nonostante il nome tail, usa rot_offset=0 e ruota l'inizio della testa.
- **`ds4_gpu_glm_indexer_score_one_tensor`** `rocm/ds4_rocm_glm.cuh:1797`  
  Disattiva sempre il mascheramento causale.
- **`ds4_gpu_glm_indexer_scores_batch_tensor`** `rocm/ds4_rocm_glm.cuh:1828`  
  Attiva sempre il mascheramento causale.
- **`ds4_gpu_glm_k_b_project_tensor`** `rocm/ds4_rocm_glm.cuh:1355`  
  Delega a uno stub CUDA che restituisce sempre 0.
- **`ds4_gpu_glm_k_b_project_typed_tensor`** `ds4_rocm_compat.cu:307`  
  Stampa su stderr e restituisce sempre 0.
- **`ds4_gpu_glm_qk_lowrank_typed_batch_tensor`** `ds4_rocm_compat.cu:329`  
  Da 128 token, scratch o cuBLAS non disponibili causano fallback nativo.
- **`ds4_gpu_glm_qk_lowrank_typed_tensor`** `ds4_rocm_compat.cu:318`  
  Forza n_tokens a 1.
- **`ds4_gpu_glm_qkv_norm_store_compact_kv_tensor`** `rocm/ds4_rocm_glm.cuh:1427`  
  Se pos supera cache_cap scrive Q ma salta le cache e puo comunque restituire successo.
- **`ds4_gpu_glm_rope_tail_tensor`** `rocm/ds4_rocm_glm.cuh:1303`  
  L'offset e sempre head_dim-rot_dim: ruota la coda, non l'intera testa.
- **`ds4_gpu_glm_routed_moe_batch_direct_scalar_q4_tensor`** `rocm/ds4_rocm_glm.cuh:4116`  
  Stampa su stderr e restituisce sempre 0.
- **`ds4_gpu_glm_routed_moe_batch_tensor`** `rocm/ds4_rocm_glm.cuh:4077`  
  Gli scratch statici crescono e restano allocati; variabili d'ambiente cambiano il percorso.
- **`ds4_gpu_glm_routed_moe_one_tensor`** `rocm/ds4_rocm_glm.cuh:4040`  
  force_resident viene ignorato e il batch è forzato a un token.
- **`ds4_gpu_glm_router_select_batch_tensor`** `rocm/ds4_rocm_glm.cuh:3942`  
  Non valida n_expert_used<=n_expert; oltre 256 esperti usa il kernel seriale.
- **`ds4_gpu_glm_router_select_tensor`** `rocm/ds4_rocm_glm.cuh:3926`  
  Forza sempre n_tokens a 1.
- **`ds4_gpu_glm_store_compact_kv_tensor`** `rocm/ds4_rocm_glm.cuh:1390`  
  Il controllo su kv_raw_dim non include davvero qk_rope e può accettare una sorgente corta.
- **`ds4_gpu_glm_store_indexer_k_tensor`** `rocm/ds4_rocm_glm.cuh:1488`  
  Non valida pos0+n_tokens contro cache_cap: il kernel può non scrivere ma il wrapper riesce.
- **`ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor`** `rocm/ds4_rocm_glm.cuh:1284`  
  Con SSD streaming disattivo restituisce successo senza leggere né caricare.
- **`ds4_gpu_glm_value_project_typed_batch_heads_tensor`** `ds4_rocm_compat.cu:340`  
  DS4_GLM_VALUE_NO_TILE16 presente disabilita il tile16 per almeno 16 token.
- **`ds4_gpu_graph_tensor_managed_requested`** `ds4_cuda.cu:5232`  
  Legge DS4_CUDA_GRAPH_TENSOR_MANAGED una sola volta e accetta soltanto il valore esatto 1.
- **`ds4_gpu_hc_expand_add2_split_tensor`** `ds4_cuda.cu:27203`  
  Abilita il terzo addendo solo insieme al secondo; non esiste una modalità add2 isolata.
- **`ds4_gpu_hc_expand_add_split_half_add_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:358`  
  Ignora i tensori e restituisce 0: il post-FFN F16 abortisce senza fallback
- **`ds4_gpu_hc_expand_add_split_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:323`  
  Non controlla alcuna taglia oltre out_hc e può leggere input sottodimensionati.
- **`ds4_gpu_hc_expand_add_tensor`** `ds4_rocm.cu:207`  
  Non verifica le taglie degli input e tronca n_tokens in base ai byte di out_hc.
- **`ds4_gpu_hc_expand_split_half_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:291`  
  Ignora i tensori e restituisce 0: l'ottimizzazione F16 abortisce senza fallback
- **`ds4_gpu_hc_expand_split_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:258`  
  Salta i primi n_hc valori di split: usa soltanto le sezioni post e comb.
- **`ds4_gpu_hc_expand_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:235`  
  Non verifica la capienza degli input: deduce n_tokens soltanto da out_hc.
- **`ds4_gpu_hc_split_sinkhorn_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:27`  
  Il numero di righe è il minimo implicito tra mix e out; la coda più lunga viene ignorata.
- **`ds4_gpu_hc_split_weighted_sum_norm_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:146`  
  Qualsiasi valore dell'env disabilita il fuso; più righe usano sempre il fallback.
- **`ds4_gpu_hc_split_weighted_sum_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:101`  
  Scrive sia out sia split; il numero di righe dipende esclusivamente dalla taglia di out.
- **`ds4_gpu_hc_weighted_sum_split_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:86`  
  Di ogni riga split usa solo i primi n_hc valori come pesi.
- **`ds4_gpu_hc_weighted_sum_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:73`  
  Ricava n_tokens per divisione intera da out e ignora eventuali byte finali.
- **`ds4_gpu_head_rms_norm_rope_tail_tensor`** `rocm/ds4_rocm_norm_rope.cuh:523`  
  Modifica il tensore sorgente in-place
- **`ds4_gpu_indexer_score_one_tensor`** `rocm/ds4_rocm_indexer.cuh:812`  
  Wrapper non causale con pos0 zero e ratio uno
- **`ds4_gpu_indexer_scores_decode_batch_tensor`** `rocm/ds4_rocm_indexer.cuh:840`  
  Abilita sempre la causalita
- **`ds4_gpu_indexer_scores_prefill_tensor`** `rocm/ds4_rocm_indexer.cuh:825`  
  Imposta pos0 a zero e abilita sempre la causalita
- **`ds4_gpu_indexer_top1_value_tensor`** `ds4_cuda.cu:15961`  
  L'offset modifica gli indici scritti, non l'accesso agli score
- **`ds4_gpu_indexer_top2_value_tensor`** `ds4_cuda.cu:15983`  
  Nessun chiamante nel grafo estratto
- **`ds4_gpu_indexer_topk_tensor`** `rocm/ds4_rocm_indexer.cuh:856`  
  Senza fast path ricade in un kernel seriale con un solo thread per token
- **`ds4_gpu_init`** `rocm/ds4_rocm_runtime.cuh:5793`  
  Configura sempre una sola GPU con indice 0.
- **`ds4_gpu_init_multi`** `ds4_rocm_compat.cu:19`  
  Rifiuta n_gpus diverso da 1, rendendo irraggiungibile la validazione peer multi-GPU.
- **`ds4_gpu_kv_fp8_store_raw_decode_rows_tensor`** `ds4_cuda.cu:17915`  
  Una sola cache staged forza disattivazione e ripristino globale dello staging
- **`ds4_gpu_kv_fp8_store_raw_tensor`** `rocm/ds4_rocm_attention_launch.cuh:2`  
  La riga di destinazione viene ridotta modulo raw_cap
- **`ds4_gpu_lookup_cache`** `ds4_cuda.cu:6675`  
  Puo' allocare VRAM e restituire una entry di un'altra GPU o del device 0
- **`ds4_gpu_lookup_cache_device`** `ds4_cuda.cu:6737`  
  Espone solo l'ID, ma il lookup sottostante puo' popolare la cache VRAM
- **`ds4_gpu_lookup_cache_strict`** `ds4_cuda.cu:6757`  
  Sul miss non modifica out_device_ptr e non usa alcun fallback
- **`ds4_gpu_matmul_f16_pair_compressor_store_tensor`** `rocm/ds4_rocm_matmul.cuh:845`  
  Ignora tutti gli argomenti, non scrive nulla e restituisce sempre zero
- **`ds4_gpu_matmul_f16_pair_tensor`** `rocm/ds4_rocm_matmul.cuh:785`  
  Flag seriali o tier diversi trasformano la coppia in due matmul separate
- **`ds4_gpu_matmul_f16_router_rows_exact_tensor`** `ds4_rocm_compat.cu:229`  
  Oltre una riga non offre fallback se manca cuBLAS
- **`ds4_gpu_matmul_f16_tensor`** `rocm/ds4_rocm_matmul.cuh:716`  
  Le variabili SERIAL scelgono kernel a un solo thread per output
- **`ds4_gpu_matmul_f32_tensor`** `rocm/ds4_rocm_matmul.cuh:879`  
  cuBLAS e usato solo con piu di un token
- **`ds4_gpu_matmul_q8_0_decode_rows_exact_tensor`** `ds4_rocm_compat.cu:210`  
  Un tier diverso causa fallimento senza fallback
- **`ds4_gpu_matmul_q8_0_f16_out_tensor`** `rocm/ds4_rocm_matmul.cuh:297`  
  Restituisce 0 in silenzio e non scrive out_h.
- **`ds4_gpu_matmul_q8_0_hc_expand_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:420`  
  Qualsiasi valore dell'env di disable seleziona il fallback in due passaggi.
- **`ds4_gpu_matmul_q8_0_kslice_hc_expand_add_tensor`** `ds4_cuda.cu:16485`  
  Opera su una sola riga x, senza parametro n_tok
- **`ds4_gpu_matmul_q8_0_kslice_rows_tensor`** `ds4_cuda.cu:16420`  
  L'output e il contributo della sola slice, senza accumulo con altre slice
- **`ds4_gpu_matmul_q8_0_kslice_tensor`** `ds4_rocm.cu:181`  
  Crea una view non proprietaria e forza una sola riga.
- **`ds4_gpu_matmul_q8_0_pair_decode_rows_exact_tensor`** `ds4_rocm_compat.cu:219`  
  Qualsiasi differenza di tier fallisce senza delegare alle matmul generiche
- **`ds4_gpu_matmul_q8_0_pair_tensor`** `rocm/ds4_rocm_matmul.cuh:568`  
  Nei batch il nome pair non implica fusione: di default delega due matmul separate
- **`ds4_gpu_matmul_q8_0_tensor`** `rocm/ds4_rocm_matmul.cuh:509`  
  Usa sempre l'etichetta fissa q8_0
- **`ds4_gpu_matmul_q8_0_top1_tensor`** `ds4_cuda.cu:16345`  
  Azzera una chiave scratch e restituisce soltanto indice e valore migliori
- **`ds4_gpu_matmul_quant_decode_mpp_model_view_tensor`** `ds4_rocm_compat.cu:293`  
  Il nome MPP non indica un kernel specializzato: usa il dispatcher generico.
- **`ds4_gpu_matmul_quant_kslice_tensor`** `ds4_cuda.cu:34143`  
  Qualsiasi weight_type diverso da 8 fallisce senza fallback interno.
- **`ds4_gpu_matmul_quant_rows_scalar_tensor`** `ds4_cuda.cu:33291`  
  Restituisce sempre 0 senza calcolare l'uscita.
- **`ds4_gpu_matmul_quant_tensor`** `ds4_rocm_compat.cu:276`  
  Nonostante il nome quant, accetta anche F16 e rifiuta gli altri formati dopo un log.
- **`ds4_gpu_model_residency_skip`** `ds4_rocm.cu:159`  
  skip e ignorato e non cambia alcuna politica di residenza CUDA
- **`ds4_gpu_moe_handoff_pack_tensor`** `ds4_cuda.cu:5604`  
  Controlla soltanto l'errore di lancio: non attende il completamento del kernel.
- **`ds4_gpu_output_hc_weights_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:203`  
  I gate sono indipendenti, non normalizzati; epsilon può portarli oltre uno.
- **`ds4_gpu_pack_slot_rows_f32_tensor`** `rocm/ds4_rocm_misc_launch.cuh:8`  
  n_rows=0 e' errore; le righe di slot oltre n_rows vengono ignorate
- **`ds4_gpu_preload_q4_expert_tables`** `rocm/ds4_rocm_current_api_compat.cuh:99`  
  Restituisce successo senza precaricare alcuna tabella.
- **`ds4_gpu_print_memory_report`** `rocm/ds4_rocm_runtime.cuh:6319`  
  Ignora l'errore di cudaMemGetInfo e puo' stampare due zeri
- **`ds4_gpu_pro_q4_expert_table_auto_available`** `rocm/ds4_rocm_current_api_compat.cuh:95`  
  Restituisce sempre 0 e disabilita la selezione automatica delle tabelle Q4.
- **`ds4_gpu_q8_cache_suppressed`** `ds4_rocm_compat.cu:192`  
  Restituisce il flag globale senza sincronizzazione
- **`ds4_gpu_recommended_working_set_size`** `rocm/ds4_rocm_current_api_compat.cuh:144`  
  Ignora la VRAM libera e sovrastima sistemi con GPU eterogenee.
- **`ds4_gpu_register_model_map_no_copy`** `ds4_cuda.cu:6297`  
  Libera cache range e Q8 esistenti prima della registrazione
- **`ds4_gpu_register_support_map`** `ds4_cuda.cu:2742`  
  Il resolver somma il bias all'offset senza controllare l'overflow.
- **`ds4_gpu_repeat_hc_rows_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:12`  
  Rifiuta lanci con piu di UINT32_MAX blocchi
- **`ds4_gpu_repeat_hc_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:1`  
  Materializza copie complete invece di usare una vista o broadcasting
- **`ds4_gpu_rms_norm_plain_rows_tensor`** `rocm/ds4_rocm_norm_rope.cuh:418`  
  Dimensioni multiple di 2048 scelgono sempre il kernel batch8
- **`ds4_gpu_rms_norm_plain_tensor`** `rocm/ds4_rocm_norm_rope.cuh:412`  
  Dimensioni multiple di 2048 scelgono un kernel batch8 anche per una sola riga
- **`ds4_gpu_rope_tail_decode_rows_tensor`** `ds4_cuda.cu:17854`  
  Copia dalle descrizioni solo il campo pos; gli altri campi sono ignorati
- **`ds4_gpu_rope_tail_tensor`** `rocm/ds4_rocm_norm_rope.cuh:610`  
  n_rot uguale a 0 supera i controlli ma produce un lancio CUDA con griglia nulla
- **`ds4_gpu_routed_moe_batch_owned_tensor`** `ds4_cuda.cu:26868`  
  Distrugge gli ID globali e azzera i pesi delle coppie non residenti.
- **`ds4_gpu_routed_moe_batch_tensor`** `rocm/ds4_rocm_moe_launch.cuh:2359`  
  Ignora force_resident e imposta sempre mid_is_f16 a false
- **`ds4_gpu_routed_moe_one_owned_tensor`** `ds4_cuda.cu:26526`  
  pack_fixed3 viene rifiutato quando resident_expert_base è zero
- **`ds4_gpu_routed_moe_one_tensor`** `rocm/ds4_rocm_moe_launch.cuh:2345`  
  add_in viene sommato prima che il percorso MoE riscriva out e può quindi andare perso
- **`ds4_gpu_routed_moe_owned_packed_combine_tensor`** `ds4_cuda.cu:26811`  
  Controlla le dimensioni ma non il device dei tensori
- **`ds4_gpu_routed_moe_owned_slots_combine_rows_tensor`** `ds4_cuda.cu:26766`  
  Verifica le dimensioni ma non verifica che i tensori appartengano allo stesso device
- **`ds4_gpu_routed_moe_owned_slots_combine_tensor`** `ds4_cuda.cu:26799`  
  Forza sempre rows=1
- **`ds4_gpu_routed_moe_set_selected_override`** `rocm/ds4_rocm_current_api_compat.cuh:309`  
  Restituisce successo ma non salva selected né n_selected.
- **`ds4_gpu_router_select_batch_tensor`** `rocm/ds4_rocm_router.cuh:168`  
  Accetta solo 256/top-6/1.5; qualunque valore di NO_WARP o NO_PARALLEL attiva il fallback
- **`ds4_gpu_router_select_tensor`** `rocm/ds4_rocm_router.cuh:121`  
  Accetta solo 256/top-6/1.5; la presenza di NO_WARP o NO_PARALLEL rallenta il kernel
- **`ds4_gpu_set_current_device`** `ds4_rocm_compat.cu:29`  
  La cache del tier puo' saltare cudaSetDevice anche se il device reale e' cambiato
- **`ds4_gpu_set_current_device_fenced`** `ds4_rocm_compat.cu:34`  
  Se la creazione evento fallisce cambia device senza alcuna fence
- **`ds4_gpu_set_decode_fast_attention`** `ds4_rocm_compat.cu:200`  
  Restituisce il valore precedente, non quello appena impostato.
- **`ds4_gpu_set_decode_score_vec4`** `ds4_rocm_compat.cu:205`  
  Restituisce il valore precedente, non quello appena impostato.
- **`ds4_gpu_set_glm_model`** `rocm/ds4_rocm_current_api_compat.cuh:128`  
  Il flag non modifica alcuno stato CUDA.
- **`ds4_gpu_set_glm_mtp_verify_mode`** `ds4_cuda.cu:33352`  
  Modifica un globale di processo, non uno stato per device o richiesta.
- **`ds4_gpu_set_glm_streaming_prefill_full_layer`** `rocm/ds4_rocm_current_api_compat.cuh:132`  
  Su CUDA è un no-op anche quando enabled è true.
- **`ds4_gpu_set_iq1_s_sidecar`** `ds4_cuda.cu:6836`  
  Tre argomenti vuoti cancellano il sidecar e restituiscono successo
- **`ds4_gpu_set_model_fd`** `rocm/ds4_rocm_runtime.cuh:6246`  
  Restituisce sempre 1; la presenza di NO_DIRECT_IO disabilita O_DIRECT
- **`ds4_gpu_set_model_fd_for_map`** `rocm/ds4_rocm_current_api_compat.cuh:68`  
  Aggiorna la base host solo se ds4_gpu_set_model_fd riesce.
- **`ds4_gpu_set_model_map`** `rocm/ds4_rocm_runtime.cuh:6064`  
  Basta la presenza di COPY_MODEL; un errore ricade sulla mappatura host
- **`ds4_gpu_set_model_map_range`** `rocm/ds4_rocm_runtime.cuh:6102`  
  Se la copia chunked fallisce tenta prefetch e restituisce comunque successo
- **`ds4_gpu_set_model_map_spans`** `rocm/ds4_rocm_runtime.cuh:6145`  
  Ignora max_tensor_bytes e anche gli errori dei singoli prefetch.
- **`ds4_gpu_set_q1_0_sidecar`** `ds4_cuda.cu:6868`  
  Tre argomenti vuoti cancellano il sidecar e restituiscono successo
- **`ds4_gpu_set_q8_cache_suppressed`** `ds4_rocm_compat.cu:196`  
  Qualunque valore non nullo viene normalizzato a 1
- **`ds4_gpu_set_quality`** `rocm/ds4_rocm_runtime.cuh:6346`  
  quality=false abilita TF32; gli errori per tier vengono saltati
- **`ds4_gpu_set_ssd_streaming`** `rocm/ds4_rocm_current_api_compat.cuh:119`  
  Disabilitarlo libera le cache; abilitarlo le invalida ma non le alloca.
- **`ds4_gpu_set_streaming_expert_cache_budget`** `rocm/ds4_rocm_current_api_compat.cuh:136`  
  Cambiare anche di un solo slot libera subito la cache residente.
- **`ds4_gpu_set_streaming_expert_cache_expert_bytes`** `rocm/ds4_rocm_current_api_compat.cuh:140`  
  Anche impostare 0 dopo un valore diverso libera la cache esistente.
- **`ds4_gpu_shared_down_hc_expand_add_q8_0_tensor`** `ds4_cuda.cu:27257`  
  Con l'env di disable presente esegue matmul e poi expand separati, senza segnalare il cambio.
- **`ds4_gpu_shared_down_hc_expand_owned_q8_0_tensor`** `ds4_cuda.cu:27294`  
  Se l'env di disable è presente fallisce con 0: non offre alcun fallback non fuso.
- **`ds4_gpu_shared_down_hc_expand_q8_0_tensor`** `rocm/ds4_rocm_hc_output_launch.cuh:394`  
  La sola presenza di DISABLE_Q8_HC_EXPAND_FUSED passa silenziosamente a due kernel.
- **`ds4_gpu_shared_gate_up_swiglu_q8_0_model_view_tensor`** `rocm/ds4_rocm_shared_expert.cuh:133`  
  Forza sempre n_tok a 1.
- **`ds4_gpu_shared_gate_up_swiglu_q8_0_rows_scalar_tensor`** `rocm/ds4_rocm_shared_expert.cuh:69`  
  Ignora tutti gli argomenti e restituisce sempre 0, senza log.
- **`ds4_gpu_shared_gate_up_swiglu_q8_0_rows_tensor`** `rocm/ds4_rocm_shared_expert.cuh:158`  
  DS4_GLM_SHARED_SPLIT non disabilita il percorso fused a due token.
- **`ds4_gpu_shared_gate_up_swiglu_q8_0_tensor`** `rocm/ds4_rocm_shared_expert.cuh:7`  
  La presenza di DISABLE_SHARED_GATE_UP_PAIR sceglie due matmul separate
- **`ds4_gpu_shared_mid_swiglu_q8_0_decode_exact_tensor`** `ds4_cuda.cu:20058`  
  Se prequant è fornito, i valori di x non vengono letti dopo i controlli
- **`ds4_gpu_shared_mid_swiglu_q8_0_tensor`** `rocm/ds4_rocm_shared_expert.cuh:101`  
  Gli scratch statici crescono e non vengono liberati dalla funzione.
- **`ds4_gpu_should_use_managed_kv_cache`** `rocm/ds4_rocm_runtime.cuh:5933`  
  KV da almeno 8 GiB abilita managed senza misurare VRAM; errore cudaMemGetInfo lo disabilita.
- **`ds4_gpu_should_use_staged_kv_cache`** `ds4_cuda.cu:4778`  
  Anche col flag attivo richiede una GPU e sticky_off falso.
- **`ds4_gpu_signal_selected_readback_ready`** `rocm/ds4_rocm_runtime.cuh:6023`  
  Se gli eventi falliscono sincronizza tutto il device e restituisce UINT64_MAX.
- **`ds4_gpu_staged_kv_gate_requested`** `ds4_cuda.cu:4769`  
  DS4_CUDA_KV_STAGED_RING è letto una volta sola e solo 1 abilita.
- **`ds4_gpu_store_raw_kv_batch_tensor`** `rocm/ds4_rocm_attention_launch.cuh:19`  
  Un lotto più lungo della capacità può sovrascrivere righe scritte nello stesso lotto
- **`ds4_gpu_store_raw_kv_tensor`** `rocm/ds4_rocm_attention_launch.cuh:12`  
  Con cache normale converte a FP16 e torna a float; row avvolge modulo capacità
- **`ds4_gpu_stream_expert_cache_begin_selected_load`** `rocm/ds4_rocm_current_api_compat.cuh:199`  
  Forza n_tokens=1 anche se il chiamante non lo esplicita.
- **`ds4_gpu_stream_expert_cache_budget_for_expert_size`** `rocm/ds4_rocm_current_api_compat.cuh:170`  
  Con cache e arena disabilitate restituisce 0 senza errore.
- **`ds4_gpu_stream_expert_cache_configured_count`** `rocm/ds4_rocm_current_api_compat.cuh:155`  
  Può restituire 0 con slot richiesti se cache e arena sono disabilitate.
- **`ds4_gpu_stream_expert_cache_current_count`** `rocm/ds4_rocm_current_api_compat.cuh:159`  
  Restituisce 0 se né cache VRAM né arena dinamica sono abilitate.
- **`ds4_gpu_stream_expert_cache_prepare_selected_batch`** `rocm/ds4_rocm_current_api_compat.cuh:217`  
  Per batch non popola slot residenti: usa il trasporto compatto.
- **`ds4_gpu_stream_expert_cache_release_resident`** `rocm/ds4_rocm_current_api_compat.cuh:166`  
  Il nome suggerisce solo i residenti, ma rilascia anche observer e arena.
- **`ds4_gpu_stream_expert_cache_reset_route_hotness`** `rocm/ds4_rocm_current_api_compat.cuh:163`  
  Azzera anche in modalità observe, ma non svuota gli esperti residenti.
- **`ds4_gpu_stream_expert_cache_seed_experts`** `rocm/ds4_rocm_current_api_compat.cuh:289`  
  Se l'arena dinamica è spenta, riesce ma non carica nulla.
- **`ds4_gpu_stream_expert_cache_seed_selected`** `rocm/ds4_rocm_current_api_compat.cuh:178`  
  Con WRAP attivo riesce senza aggiungere il seed legacy.
- **`ds4_gpu_synchronize`** `rocm/ds4_rocm_runtime.cuh:6062`  
  Blocca tutto il device e non distingue gli stream
- **`ds4_gpu_tensor_alloc`** `rocm/ds4_rocm_runtime.cuh:5894`  
  Zero byte diventa un'allocazione da un byte.
- **`ds4_gpu_tensor_alloc_kv_cache`** `rocm/ds4_rocm_runtime.cuh:5920`  
  Anche in modalita staged alloca prima l'intero KV in VRAM; la migrazione avviene dopo.
- **`ds4_gpu_tensor_alloc_managed`** `rocm/ds4_rocm_runtime.cuh:5907`  
  Non incrementa used_bytes e la memoria non e realmente vincolata al device_id registrato.
- **`ds4_gpu_tensor_alloc_managed_on`** `ds4_rocm_compat.cu:56`  
  Il device_id e solo la home iniziale: le pagine managed possono migrare tra GPU.
- **`ds4_gpu_tensor_alloc_on`** `ds4_rocm_compat.cu:38`  
  Una richiesta di zero byte ne alloca uno; gli errori sono codici 1, 2 o 3.
- **`ds4_gpu_tensor_alloc_ptr_on`** `ds4_rocm_compat.cu:50`  
  Un tier invalido stampa su stderr; zero byte diventa un byte.
- **`ds4_gpu_tensor_bytes`** `rocm/ds4_rocm_runtime.cuh:5976`  
  Con un tensor nullo restituisce zero.
- **`ds4_gpu_tensor_contents`** `rocm/ds4_rocm_runtime.cuh:5980`  
  Senza staging esegue cudaDeviceSynchronize completo prima di restituire un ptr device.
- **`ds4_gpu_tensor_copy`** `rocm/ds4_rocm_runtime.cuh:6003`  
  Se almeno un lato e staged la copia diventa sincrona; tra due staged usa memmove CPU.
- **`ds4_gpu_tensor_copy_async`** `ds4_rocm_compat.cu:72`  
  Con un tensor staged degrada alla copia sincrona generale.
- **`ds4_gpu_tensor_copy_f32_to_f16`** `rocm/ds4_rocm_current_api_compat.cuh:74`  
  count è in elementi, mentre src_offset e dst_offset sono in byte.
- **`ds4_gpu_tensor_copy_xdev`** `ds4_rocm_compat.cu:81`  
  Non ordina preventivamente lo stream di destinazione prima della scrittura peer.
- **`ds4_gpu_tensor_copy_xdev3`** `ds4_rocm_compat.cu:99`  
  Device discordi o peer assente degradano a copie singole
- **`ds4_gpu_tensor_copy_xdev3_default_dst`** `ds4_rocm_compat.cu:108`  
  Senza peer degrada a tre copie separate e sincrone via host; entry vuote possono essere nulle.
- **`ds4_gpu_tensor_copy_xdev_default`** `ds4_rocm_compat.cu:87`  
  Usa lo stream CUDA 0 invece dello stream per-GPU impiegato dal wrapper non-default.
- **`ds4_gpu_tensor_copy_xdev_default_impl`** `ds4_cuda.cu:5741`  
  Il fallback host usa due cudaMemcpy sincrone, pur condividendo il nome con percorsi async.
- **`ds4_gpu_tensor_copy_xdev_impl`** `ds4_cuda.cu:5641`  
  Il bounce sincronizza la destinazione; FORCE_CUDA_PEER ignora la validazione peer iniziale.
- **`ds4_gpu_tensor_copy_xdev_ordered`** `ds4_rocm_compat.cu:93`  
  Forza sempre ordered=true nell'implementazione interna
- **`ds4_gpu_tensor_device`** `ds4_rocm_compat.cu:68`  
  Con un tensor nullo restituisce -1.
- **`ds4_gpu_tensor_fill_f32`** `rocm/ds4_rocm_runtime.cuh:5986`  
  Il percorso staged usa un ciclo CPU sincrono; il kernel normale viene solo accodato.
- **`ds4_gpu_tensor_free`** `rocm/ds4_rocm_runtime.cuh:5970`  
  Non decrementa g_gpu.used_bytes, quindi la contabilita puo crescere dopo i free.
- **`ds4_gpu_tensor_free_in_place`** `ds4_rocm_compat.cu:62`  
  Non aggiorna used_bytes e non rimuove binding KV staged; inoltre non ha chiamanti.
- **`ds4_gpu_tensor_read`** `rocm/ds4_rocm_runtime.cuh:5998`  
  La chiamata blocca: attende lo stream staged oppure usa cudaMemcpy sincrona.
- **`ds4_gpu_tensor_read_after_selected_event`** `rocm/ds4_rocm_current_api_compat.cuh:1`  
  Con observer spento sincronizza l'intero device prima della copia.
- **`ds4_gpu_tensor_view`** `rocm/ds4_rocm_runtime.cuh:5960`  
  Per una base staged la view registrata ha ptr nullo e dipende dal registro per ogni accesso.
- **`ds4_gpu_tensor_wait_xdev`** `ds4_rocm_compat.cu:116`  
  Con il debug attivo sincronizza anche l'host sullo stream destinazione
- **`ds4_gpu_tensor_wait_xdev_default`** `ds4_rocm_compat.cu:121`  
  Usa sempre lo stream 0, non gli stream configurati in g_gpu
- **`ds4_gpu_tensor_write`** `rocm/ds4_rocm_runtime.cuh:5993`  
  Sul KV staged modifica solo l'arena host mentre il ptr device puo essere nullo.
- **`ds4_gpu_test_dequant_iq1_s_block`** `ds4_cuda.cu:20972`  
  Compilata solo con DS4_IQ1_TEST_API; ignora gli errori di cudaFree
- **`ds4_gpu_tier_free_vram`** `ds4_rocm_compat.cu:126`  
  Tier invalido o errore CUDA restituiscono 0, indistinguibile da VRAM esaurita.
- **`ds4_gpu_token_watch_begin`** `ds4_cuda.cu:1507`  
  Con slow_token_log spento avvia comunque la misura del picco VRAM.
- **`ds4_gpu_token_watch_end`** `ds4_cuda.cu:1524`  
  token_count può superare uno pur usando una sola finestra temporale.
- **`ds4_gpu_tp_batch_gate_encode`** `ds4_rocm.cu:175`  
  Ignora layer e rows e restituisce 0; nessun batch TP viene scambiato
- **`ds4_gpu_tp_big_gate_encode`** `ds4_rocm.cu:167`  
  Su CUDA fallisce sempre: il TP di rete è solo Metal.
- **`ds4_gpu_tp_big_gate_kick`** `ds4_rocm_unavailable.cu:40`  
  Non pubblica eventi ne scambia buffer; restituisce sempre seq 0
- **`ds4_gpu_tp_big_gate_wait`** `ds4_cuda.cu:34293`  
  Ignora seq e restituisce 0; non attende ne codifica alcun rilascio
- **`ds4_gpu_tp_gate_encode`** `ds4_rocm.cu:137`  
  Su CUDA fallisce sempre: il TP di rete è solo Metal.
- **`ds4_gpu_tp_keepalive_pause`** `ds4_rocm.cu:151`  
  paused e ignorato: nessun keepalive CUDA viene sospeso o ripreso
- **`ds4_gpu_tp_set_attn_head_split`** `ds4_rocm.cu:155`  
  Il flag è ignorato: lo split TP delle teste è solo Mac.
- **`ds4_gpu_tp_suspend_expert_sharding`** `ds4_rocm.cu:147`  
  Sia suspend=1 sia suspend=0 non cambiano alcuno stato CUDA
- **`ds4_gpu_vram_ledger_decode_start`** `ds4_cuda.cu:7031`  
  Non e' sola telemetria: puo' liberare realmente la VRAM del KV
- **`ds4_gpu_vram_ledger_request_end`** `ds4_cuda.cu:7060`  
  Puo' riallocare e ricopiare il KV in VRAM; ignora l'esito del ripristino
- **`ds4_gpu_wait_selected_readback_ready`** `rocm/ds4_rocm_runtime.cuh:6054`  
  Con observer spento esegue cudaDeviceSynchronize sull'intero device.
- **`ds4_hostpin_note_alloc`** `ds4_cuda.cu:623`  
  Il budget è solo stampato: non limita né rifiuta allocazioni.
- **`ds4_hostpin_note_failed`** `ds4_cuda.cu:658`  
  Con diagnostica disabilitata lascia invariato il tag pendente.
- **`ds4_hostpin_note_free`** `ds4_cuda.cu:664`  
  Un puntatore non registrato viene ignorato senza contatore né avviso.
- **`ds4_hostpin_summary`** `ds4_cuda.cu:680`  
  kv_arena resta uno zero strutturale e il budget stampato non è applicato.
- **`ds4_hostpin_tag`** `ds4_cuda.cu:617`  
  Un kind fuori intervallo viene convertito silenziosamente in other.
- **`ds4_layer_pack_print`** `ds4_layer_pack.c:90`  
  Non cancella "(no transformer layers)" quando il tier contiene solo pseudo-layer.
- **`ds4_slow_token_note_read`** `ds4_cuda.cu:1023`  
  Anche EOF e letture fallite incrementano il numero di chiamate.
- **`ds4_telemetry_now_ns`** `ds4_cuda.cu:963`  
  Un tempo nullo o negativo diventa 0, usato altrove come sentinella disabilitata.
- **`ds4_tensor_device_idx`** `ds4_cuda.cu:2169`  
  Un tensore nullo o con device_id negativo viene attribuito al device zero.
- **`ds4_trace_cuda_free`** `ds4_cuda.cu:770`  
  Conta e campiona il free prima dell'esito CUDA, anche se cudaFree poi fallisce.
- **`ds4_trace_cuda_free_host`** `ds4_cuda.cu:777`  
  Un errore CUDA lascia entrambi i registri invariati.
- **`ds4_trace_cuda_host_alloc`** `ds4_cuda.cu:740`  
  Il tag host-pinned viene consumato anche quando l'allocazione fallisce.
- **`ds4_trace_cuda_host_register`** `ds4_cuda.cu:756`  
  Conta come allocazione diagnostica anche se la memoria esisteva già.
- **`ds4_trace_cuda_host_unregister`** `ds4_cuda.cu:786`  
  Un errore CUDA lascia l'intervallo contabilizzato come ancora registrato.
- **`ds4_trace_cuda_malloc`** `ds4_cuda.cu:697`  
  Il campione del picco avviene solo se cudaMalloc riesce.
- **`ds4_trace_cuda_malloc_host`** `ds4_cuda.cu:725`  
  Alloca RAM host-pinned, non VRAM, pur passando dal tracer CUDA.
- **`ds4_trace_cuda_malloc_managed`** `ds4_cuda.cu:710`  
  Forza sempre cudaMemAttachGlobal, senza esporre la scelta al chiamante.
- **`ds4_transport_decode_begin`** `ds4_cuda.cu:1374`  
  Se la telemetria è spenta lascia intatto lo stato precedente.
- **`ds4_transport_h2d_active_begin`** `ds4_cuda.cu:1299`  
  Operazioni sovrapposte condividono una sola finestra temporale.
- **`ds4_transport_h2d_active_end`** `ds4_cuda.cu:1312`  
  Un end senza operazioni attive rende incompleto l'intero ledger.
- **`ds4_transport_load_begin`** `ds4_cuda.cu:1258`  
  Incrementa file_loads prima di sapere se il caricamento riuscirà.
- **`ds4_transport_load_end`** `ds4_cuda.cu:1340`  
  Un fallimento invalida la completezza della richiesta e non accredita i byte H2D.
- **`ds4_transport_lock`** `ds4_cuda.cu:1231`  
  Attende con spin puro, senza yield né backoff.
- **`ds4_transport_mark_incomplete`** `ds4_cuda.cu:1250`  
  Non fa nulla se il ledger è disabilitato o non ancora armato.
- **`ds4_transport_pair_index`** `ds4_cuda.cu:1240`  
  Su input invalido restituisce zero e non scrive index.
- **`ds4_transport_record_file_bytes`** `ds4_cuda.cu:1286`  
  Ignora deliberatamente i byte della prima lettura da file.
- **`ds4_transport_record_h2d_bytes`** `ds4_cuda.cu:1330`  
  I byte zero sono ignorati e l'overflow non satura il contatore.
- **`ds4_transport_report`** `ds4_cuda.cu:1394`  
  pcie_busy_pct_derived è un rapporto di tempi host, non un contatore hardware PCIe.
- **`ds4_transport_request_end`** `ds4_cuda.cu:1472`  
  Disarma il ledger solo dopo aver stampato il report finale.
- **`ds4_transport_token_end`** `ds4_cuda.cu:1449`  
  transport_every_tokens uguale a zero genera un report a ogni chiamata.
- **`ds4_transport_unlock`** `ds4_cuda.cu:1236`  
  Non verifica proprietà o doppio rilascio.
- **`ds4_vram_ledger_log`** `ds4_cuda.cu:7001`  
  Con vram_boundary_log spento non misura e non stampa nulla
- **`ds4_vram_peak_device_event`** `ds4_cuda.cu:242`  
  L'evento cudaFree viene campionato prima della liberazione effettiva.
- **`ds4_vram_peak_query_free`** `ds4_cuda.cu:205`  
  Un errore viene cancellato e restituito come 0, indistinguibile da nessuna VRAM libera.
- **`ds4_vram_peak_run_reset`** `ds4_cuda.cu:280`  
  Il reset lascia il probe disarmato; sarà token_begin ad armarlo.
- **`ds4_vram_peak_summary`** `ds4_cuda.cu:383`  
  Il riepilogo disarma il probe e non lo riattiva.
- **`ds4_vram_peak_token_begin`** `ds4_cuda.cu:305`  
  Anche una query fallita arma il probe con baseline pari a zero.
- **`ds4_vram_peak_token_end`** `ds4_cuda.cu:320`  
  Senza eventi di allocazione usa la VRAM iniziale come minimo sintetico.
- **`ds4_vram_peak_update_min`** `ds4_cuda.cu:223`  
  Minimo e metadati sono store separati e possono non corrispondere in caso di gara.
- **`ds4_vram_prio_log`** `ds4_cuda.cu:6943`  
  Elasticita' e riserve contano solo se INVERTED_PRIORITY vale esattamente 1
- **`ds4_workerprof_cache_invalidate`** `ds4_cuda.cu:1093`  
  Conta l'evento ma non invalida né libera alcuna cache.
- **`ds4_workerprof_faults_now`** `ds4_cuda.cu:968`  
  Fuori da Windows restituisce uno zero strutturale, non una misura reale.
- **`ds4_workerprof_inflight_advance`** `ds4_cuda.cu:991`  
  Un decremento eccessivo satura silenziosamente il conteggio a zero.
- **`ds4_workerprof_inflight_guard_lock`** `ds4_cuda.cu:981`  
  Attende in ciclo stretto senza yield né backoff.
- **`ds4_workerprof_inflight_guard_unlock`** `ds4_cuda.cu:987`  
  Non verifica proprietà o corretta associazione lock-unlock.
- **`ds4_workerprof_job_begin`** `ds4_cuda.cu:1063`  
  slow_token_log da solo attiva il job, ma non campiona i page fault.
- **`ds4_workerprof_job_end`** `ds4_cuda.cu:1074`  
  Con started_ns zero non ripristina job_active né il piano.
- **`ds4_workerprof_read_begin`** `ds4_cuda.cu:1016`  
  Se profiling o job sono inattivi restituisce 0, che rende read_end un no-op.
- **`ds4_workerprof_read_end`** `ds4_cuda.cu:1032`  
  Una lettura fallita conta come chiamata e tempo, ma non come byte.
- **`ds4_workerprof_report`** `ds4_cuda.cu:1114`  
  Anche il report cumulativo aggiorna la baseline delle finestre successive.
- **`ds4_workerprof_reset`** `ds4_cuda.cu:1100`  
  Con il worker profiler disattivato non azzera nemmeno i contatori usati dallo slow-token log.
- **`ds4_workerprof_set_plane`** `ds4_cuda.cu:959`  
  Senza profiling lascia invariato il valore thread-local precedente.
- **`ds4_workerprof_span_begin`** `ds4_cuda.cu:1050`  
  Restituisce zero se il profiler è spento o non è attivo alcun job.
- **`ds4_workerprof_span_end`** `ds4_cuda.cu:1055`  
  Non valida index: un valore errato accede fuori dai contatori.
- **`ds4_workerprof_token_end`** `ds4_cuda.cu:1177`  
  worker_every_tokens uguale a zero fa scattare un report a ogni chiamata.
- **`dspark_markov_argmax_kernel`** `ds4_cuda.cu:14348`  
  Ogni passo rilegge l'intera matrice w2 e riduce con atomicMax su una chiave impacchettata.
- **`dsv4_e2m1fn_dequant_dev`** `rocm/ds4_rocm_norm_rope.cuh:345`  
  Satura a 6 e risolve i pareggi verso un indice pari.
- **`dsv4_e2m1fn_value_dev`** `rocm/ds4_rocm_norm_rope.cuh:332`  
  Maschera l'indice con 7, quindi valori fuori intervallo ricominciano da zero.
- **`dsv4_e4m3fn_dequant_dev`** `rocm/ds4_rocm_norm_rope.cuh:314`  
  Satura a 448 e risolve i pareggi verso un codice pari.
- **`dsv4_e4m3fn_value_dev`** `rocm/ds4_rocm_norm_rope.cuh:307`  
  Non gestisce il segno né il codice 127.
- **`dsv4_qkv_rms_norm_rows_kernel`** `rocm/ds4_rocm_norm_rope.cuh:47`  
  blockIdx.y sceglie Q o KV; ogni altro piano termina senza scrivere.
- **`dsv4_qkv_rms_norm_rows_kv_rope_kernel`** `ds4_cuda.cu:9066`  
  Q viene soltanto normalizzato; il RoPE fuso è applicato esclusivamente a KV.
- **`embed_staged_rows_hc_kernel`** `ds4_cuda.cu:7143`  
  Ogni riga viene duplicata identica per tutti i canali HC
- **`embed_token_hc_kernel`** `rocm/ds4_rocm_common.cuh:11`  
  Non riceve n_vocab: un token fuori range legge oltre i pesi
- **`embed_tokens_hc_kernel`** `rocm/ds4_rocm_common.cuh:65`  
  Token negativo o fuori vocabolario viene sostituito silenziosamente con 0
- **`enabled`** `src/cuda/vram_expert_cache.cpp:288`  
  Rilegge l'ambiente a ogni chiamata; un valore invalido avvisa una sola volta
- **`f32_to_f16_kernel`** `rocm/ds4_rocm_common.cuh:345`  
  Overflow e valori fini fuori gamma diventano half inf; la conversione perde precisione.
- **`finalize`** `src/cuda/prefill_observer.cu:490`  
  Se il flag viene tolto dopo request_begin, ritorna true senza ritirare i readback.
- **`fp8_kv_quantize_kernel`** `rocm/ds4_rocm_fp8_kv.cuh:7`  
  Il tensore resta float32: emula l'errore FP8 senza compattare i dati.
- **`fp8_kv_quantize_row`** `ds4_cuda.cu:9439`  
  Lascia intatta la coda RoPE e conserva float dequantizzati, non byte FP8.
- **`fp8_kv_quantize_store_rows_kernel`** `ds4_cuda.cu:9476`  
  Nel raw cache salva float32 arrotondati a FP16, non byte FP8.
- **`glm_add_rms_norm_weight_kernel`** `ds4_cuda.cu:29527`  
  Gestisce una sola riga: un batch va spezzato dal chiamante.
- **`glm_attention_decode_lora_staged_kernel`** `ds4_cuda.cu:30260`  
  Con RANGE_TOK2 ignora selected e usa le righe dense da zero.
- **`glm_attention_decode_value_staged_kernel`** `ds4_cuda.cu:30297`  
  Assume righe Q8_0 da 34 byte per 32 colonne senza verificarne il formato.
- **`glm_attention_decode_weights_staged_kernel`** `ds4_cuda.cu:30147`  
  Con RANGE_TOK2 ignora selected e usa le righe dense da zero.
- **`glm_attention_indexed_decode_kernel`** `ds4_cuda.cu:30345`  
  Con RANGE_TOK2 ignora selected e usa una finestra densa crescente.
- **`glm_attention_lora_causal_kernel`** `ds4_cuda.cu:29779`  
  Le righe fuori cache vengono ignorate; se lo sono tutte produce un output zero.
- **`glm_cache_rope_pair_f16_dev`** `ds4_cuda.cu:29759`  
  Usa row sia per indirizzare la cache sia come posizione RoPE.
- **`glm_embed_token_q8_0_kernel`** `ds4_cuda.cu:29597`  
  Interpreta ogni blocco come 2 byte FP16 più 32 int8, senza metadati di tipo.
- **`glm_embed_tokens_q8_0_kernel`** `ds4_cuda.cu:29645`  
  Un ID negativo o fuori range provoca una lettura pesi fuori bounds.
- **`glm_fill_selected_range_batch_kernel`** `rocm/ds4_rocm_glm.cuh:653`  
  Le posizioni future ricevono pad_row, non un indice negativo.
- **`glm_indexer_scores_f32_kernel`** `ds4_cuda.cu:30920`  
  Applica ReLU a ogni dot di testa prima della somma pesata.
- **`glm_indexer_scores_launch`** `ds4_cuda.cu:31082`  
  g_quality_mode falso sceglie WMMA e riduce Q e K a f16.
- **`glm_indexer_scores_wmma128_kernel`** `ds4_cuda.cu:30969`  
  Con cache f32 converte comunque Q e K in f16 nello shared.
- **`glm_kv_lora_rms_norm_kernel`** `rocm/ds4_rocm_glm.cuh:176`  
  La coda rope della riga sorgente non viene letta ne copiata.
- **`glm_moe_build_expert_tiles8_kernel`** `ds4_cuda.cu:31972`  
  Usa un solo thread GPU e serializza tutti gli esperti.
- **`glm_moe_expert_map_kernel`** `ds4_cuda.cu:31955`  
  L'ordine nelle liste e non deterministico per via degli atomicAdd concorrenti.
- **`glm_q8_0_dot_row_dev`** `ds4_cuda.cu:30107`  
  Le colonne residue oltre l'ultimo blocco da 32 sono ignorate.
- **`glm_qk_lowrank_q8_0_batch_kernel`** `ds4_cuda.cu:31251`  
  qk_dim determina solo lo stride; il prodotto usa esclusivamente qk_nope colonne.
- **`glm_qkv_norm_store_compact_kv_kernel`** `rocm/ds4_rocm_glm.cuh:236`  
  Salva la coda RoPE non ruotata: la rotazione avviene durante la lettura in attenzione.
- **`glm_rope_tail_offset_kernel`** `ds4_cuda.cu:31544`  
  Usa coppie interlacciate adiacenti, non la convenzione split-half.
- **`glm_rope_tail_offset_launch`** `ds4_cuda.cu:31592`  
  Qualsiasi parametro non valido restituisce 0 senza lanciare ne diagnosticare.
- **`glm_rope_yarn_corr_factor_dev`** `ds4_cuda.cu:29464`  
  Non valida gli argomenti: valori degeneri producono NaN o divisioni per zero.
- **`glm_rope_yarn_dev`** `ds4_cuda.cu:29474`  
  ext_factor zero disattiva anche l'aggiustamento logaritmico di mscale.
- **`glm_rope_yarn_ramp_dev`** `ds4_cuda.cu:29469`  
  Usa la divisione intera i0 diviso 2 prima di calcolare il mix.
- **`glm_routed_moe_batch_q2K_down_kernel`** `ds4_cuda.cu:31708`  
  Sovrascrive out con la somma, non accumula su un valore preesistente.
- **`glm_routed_moe_batch_q2K_gateup_kernel`** `ds4_cuda.cu:31671`  
  Un esperto negativo lascia la corrispondente riga mid invariata.
- **`glm_routed_moe_down_expert_kernel`** `ds4_cuda.cu:32123`  
  Usa atomicAdd: l'ordine delle somme non è deterministico.
- **`glm_routed_moe_down_expert_tile8_terms_kernel`** `ds4_cuda.cu:32169`  
  Scrive termini non pesati e non ridotti; serve il kernel di riduzione successivo.
- **`glm_routed_moe_down_terms_reduce_kernel`** `ds4_cuda.cu:32226`  
  Sovrascrive l'uscita invece di accumularla.
- **`glm_routed_moe_down_warp_kernel`** `ds4_cuda.cu:31900`  
  Carica nello shared anche le righe mid degli slot poi scartati come invalidi.
- **`glm_routed_moe_finish_batch`** `ds4_cuda.cu:32257`  
  Se i puntatori coincidono considera concluso il lavoro senza copia.
- **`glm_routed_moe_gateup_expert_tile8_kernel`** `ds4_cuda.cu:31995`  
  Legge tile_total dalla VRAM in ogni blocco di una griglia sovradimensionata.
- **`glm_routed_moe_gateup_tok2_reuse_kernel`** `ds4_cuda.cu:31807`  
  Il lavoro del token 1 condiviso viene saltato e prodotto dal blocco proprietario del token 0.
- **`glm_routed_moe_gateup_warp_kernel`** `ds4_cuda.cu:31746`  
  Copia l'attivazione nello shared anche per slot con esperto negativo.
- **`glm_router_select_batch_kernel`** `ds4_cuda.cu:32756`  
  Il blocco ha 32 thread ma soltanto il thread 0 svolge tutto il lavoro.
- **`glm_router_select_parallel_kernel`** `ds4_cuda.cu:32689`  
  Il bias decide il top-k, ma i pesi normalizzati usano le probabilità senza bias.
- **`glm_shared_gate_up_swiglu_one_kernel`** `ds4_cuda.cu:33423`  
  Il clamp è asimmetrico: gate ha solo limite superiore, up anche quello inferiore.
- **`glm_shared_gate_up_swiglu_tok2_exact_kernel`** `ds4_cuda.cu:33480`  
  Il clamp è asimmetrico: gate ha solo limite superiore, up anche quello inferiore.
- **`glm_store_compact_kv_kernel`** `rocm/ds4_rocm_glm.cuh:206`  
  Le posizioni oltre cache_cap vengono saltate senza errore.
- **`glm_store_indexer_k_kernel`** `rocm/ds4_rocm_glm.cuh:298`  
  Le posizioni oltre cache_cap vengono saltate senza errore.
- **`glm_value_project_q8_0_batch_heads_tiled_kernel`** `ds4_cuda.cu:33155`  
  La specializzazione assume il formato Q8_0 da 34 byte per blocco.
- **`grouped_q8_0_a_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:1794`  
  Solo la lane 0 di ogni warp scrive il risultato ridotto.
- **`grouped_q8_0_a_preq_warp8_tok2_kernel`** `ds4_cuda.cu:8834`  
  La seconda metà del blocco serve esclusivamente il secondo token.
- **`half_warp_sum_f32`** `rocm/ds4_rocm_moe.cuh:465`  
  Il parametro lane16 è ignorato; il gruppo deriva solo da threadIdx.x
- **`hc4_split_one`** `rocm/ds4_rocm_hc.cuh:6`  
  Anche sinkhorn_iters uguale a 0 esegue già una normalizzazione per righe e colonne
- **`hc_expand_kernel`** `rocm/ds4_rocm_hc.cuh:74`  
  Se has_add2 è vero ma has_add è falso, block_add2 viene comunque ignorato
- **`hc_split_sinkhorn_kernel`** `rocm/ds4_rocm_hc.cuh:54`  
  Con zero iterazioni richiede comunque e svolge il primo passo riga-colonna
- **`hc_split_weighted_sum_fused_kernel`** `rocm/ds4_rocm_hc.cuh:300`  
  Con n_hc diverso da 4 ritorna senza scrivere alcun output
- **`hc_split_weighted_sum_norm_fused_kernel`** `rocm/ds4_rocm_hc.cuh:328`  
  Riscrive out come intermedio grezzo prima di produrre norm_out
- **`head_rms_norm_kernel`** `rocm/ds4_rocm_norm_rope.cuh:83`  
  Modifica il tensore x in-place.
- **`head_rms_norm_rope_tail_kernel`** `rocm/ds4_rocm_norm_rope.cuh:105`  
  Il flag inverse cambia solo il segno del seno.
- **`host_page_size`** `src/cuda/dynamic_arena.cu:778`  
  In caso di errore assume 4096 byte
- **`indexed_topk_sort_512_asc_kernel`** `rocm/ds4_rocm_indexer.cuh:712`  
  Perde l'ordine per score e conserva soltanto l'ordine crescente degli indici.
- **`indexer_hadamard_fp4_kernel`** `rocm/ds4_rocm_indexer.cuh:1`  
  Scrive valori float dequantizzati, non una rappresentazione FP4 compatta.
- **`indexer_score_one_direct_kernel`** `rocm/ds4_rocm_indexer.cuh:85`  
  Con causal e ratio uguale a 0 considera visibili tutte le componenti.
- **`indexer_score_one_staged_kernel`** `ds4_cuda.cu:13789`  
  Scrive scores a global_c, non in posizioni locali contigue al lotto.
- **`indexer_scores_kernel`** `rocm/ds4_rocm_indexer.cuh:43`  
  Ogni prodotto scalare negativo viene troncato a zero prima della somma.
- **`indexer_scores_launch`** `rocm/ds4_rocm_indexer.cuh:761`  
  Un layout staged non singolo forza restore e disabilita lo staging
- **`indexer_scores_wmma128_kernel`** `rocm/ds4_rocm_indexer.cuh:128`  
  Accumula otto risultati per thread in registri dopo prodotti su half.
- **`indexer_scores_wmma32_kernel`** `ds4_cuda.cu:13949`  
  Su sm minore di 70 il corpo è vuoto e non scrive score.
- **`indexer_scores_wmma64_kernel`** `ds4_cuda.cu:14065`  
  Converte gli input float in half anche se l'output resta float.
- **`indexer_scores_wmma_kernel`** `ds4_cuda.cu:13841`  
  Converte q e index_comp da float a half prima dei prodotti scalari.
- **`indexer_top1_kernel`** `ds4_cuda.cu:14413`  
  Le parità scelgono sempre l'indice minore.
- **`indexer_top1_value_kernel`** `ds4_cuda.cu:14454`  
  selected contiene l'indice globale, mentre il confronto legge la riga locale.
- **`indexer_top2_value_kernel`** `ds4_cuda.cu:14504`  
  Restituisce indici già incrementati di index_offset.
- **`indexer_topk_1024_kernel`** `rocm/ds4_rocm_indexer.cuh:361`  
  Ordina sempre tutti i 1024 slot, anche quando top_k è molto più piccolo.
- **`indexer_topk_8192_cub_kernel`** `rocm/ds4_rocm_indexer.cuh:321`  
  Richiede shared memory dinamica opt-in; il wrapper può ripiegare su un altro kernel.
- **`indexer_topk_chunk_pow2_kernel`** `rocm/ds4_rocm_indexer.cuh:519`  
  L'output non è una top-k globale: deve essere fuso da kernel successivi.
- **`indexer_topk_kernel`** `rocm/ds4_rocm_indexer.cuh:290`  
  È il fallback a un solo thread per token e scala male con n_comp.
- **`indexer_topk_merge_pow2_kernel`** `rocm/ds4_rocm_indexer.cuh:581`  
  Non deduplica i candidati, quindi duplicati possono occupare più posizioni.
- **`indexer_topk_pow2_kernel`** `rocm/ds4_rocm_indexer.cuh:409`  
  Il costo resta quello del sort completo di SORT_N, non di una selezione parziale.
- **`indexer_topk_pow2_u16_kernel`** `rocm/ds4_rocm_indexer.cuh:464`  
  Gli indici vengono troncati a 16 bit prima del sort.
- **`indexer_topk_tree_merge_pow2_kernel`** `rocm/ds4_rocm_indexer.cuh:641`  
  Produce set intermedi separati per gruppo, non la top-k globale finale.
- **`iq1_s_fixture_dequant_kernel`** `ds4_cuda.cu:20965`  
  Non esiste nella build normale senza DS4_IQ1_TEST_API
- **`ldu32_unaligned`** `ds4_cuda.cu:8522`  
  Puo' leggere fino a tre byte prima di p e quattro byte oltre i quattro richiesti.
- **`load_i8x4_i32_aligned`** `rocm/ds4_rocm_q8.cuh:10`  
  Un puntatore non allineato viene reinterpretato comunque come int32_t.
- **`load_i8x4_i32_unaligned`** `rocm/ds4_rocm_q8.cuh:14`  
  Ricostruisce sempre ordine little-endian invece di fare una singola load a 32 bit.
- **`matmul_f16_kernel`** `rocm/ds4_rocm_common.cuh:87`  
  Oltre 256 thread sfora partial; una blockDim non potenza di due perde termini
- **`matmul_f16_ordered_chunks_kernel`** `rocm/ds4_rocm_common.cuh:115`  
  Il thread 0 somma serialmente i 32 parziali; il percorso e' usato solo senza cuBLAS.
- **`matmul_f16_pair_ordered_chunks_kernel`** `rocm/ds4_rocm_common.cuh:245`  
  Supporta dimensioni d'uscita diverse, ma il chiamante corrente passa la stessa dimensione.
- **`matmul_f16_serial_kernel`** `ds4_cuda.cu:7186`  
  Solo thread 0 lavora; ogni altro thread del blocco esce subito
- **`matmul_f16_small_out_batch_kernel`** `ds4_cuda.cu:7268`  
  Con blocchi diversi da 256 o out_dim oltre 32 termina senza scrivere ne' segnalare errore.
- **`matmul_f16_small_out_hx_ordered_chunks_kernel`** `ds4_cuda.cu:7238`  
  Converte ogni valore di x F32 in F16 prima del prodotto, perdendo precisione intenzionalmente.
- **`matmul_f32_kernel`** `rocm/ds4_rocm_common.cuh:288`  
  Nel batch cuBLAS la precede normalmente; resta soprattutto fallback o percorso a un token.
- **`matmul_q8_0_hc_expand_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:302`  
  Se has_owned_slots e' vero ignora completamente block_add e block_add2.
- **`matmul_q8_0_kernel`** `rocm/ds4_rocm_q8.cuh:38`  
  Riquantizza gli stessi blocchi di attivazione separatamente per ogni riga d'uscita.
- **`matmul_q8_0_kslice_hc_expand_add_preq_warp8_kernel`** `ds4_cuda.cu:8119`  
  block_out riceve solo il dot della fetta, mentre out_hc include sempre block_add.
- **`matmul_q8_0_kslice_preq_warp8_kernel`** `ds4_cuda.cu:7737`  
  Scrive il prodotto della sola fetta: non lo accumula su un valore d'uscita preesistente.
- **`matmul_q8_0_mma_exact_kernel`** `ds4_cuda.cu:8547`  
  Su architetture precedenti a SM80 l'MMA non accumula e l'output diventa zero.
- **`matmul_q8_0_pair_preq_batch_kernel`** `ds4_cuda.cu:7886`  
  Riduce sempre entrambi gli accumulatori anche quando una delle due righe non esiste.
- **`matmul_q8_0_pair_preq_batch_tok2_exact_kernel`** `ds4_cuda.cu:7950`  
  Con n_tok dispari riusa i puntatori del primo token, ma azzera e non scrive il secondo risultato.
- **`matmul_q8_0_pair_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:205`  
  Le dimensioni d'uscita possono differire e ogni warp salta separatamente la matrice assente.
- **`matmul_q8_0_preq_batch_tok2_exact_kernel`** `ds4_cuda.cu:8454`  
  Con un token finale dispari riusa il primo puntatore ma non scrive il risultato duplicato.
- **`matmul_q8_0_preq_batch_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:352`  
  Non riceve n_tok: una grid.y eccessiva leggerebbe e scriverebbe oltre i buffer.
- **`matmul_q8_0_preq_batch_warp8_tok2_kernel`** `ds4_cuda.cu:8201`  
  Non ha n_tok ne' controlli di validita': legge e scrive sempre anche il secondo token.
- **`matmul_q8_0_preq_batch_warp8_tok4_kernel`** `ds4_cuda.cu:8253`  
  Costruisce puntatori per quattro righe, ma evita letture e scritture per i token finali assenti.
- **`matmul_q8_0_preq_batch_warp8_tok8_kernel`** `ds4_cuda.cu:8331`  
  La variante e' scelta solo con blocks <= 32 e n_tok >= 8, salvo chiamate dirette non validate.
- **`matmul_q8_0_preq_kernel`** `rocm/ds4_rocm_q8.cuh:114`  
  DP4A vale solo sui blocchi interi; l'ultimo blocco incompleto usa sempre il ciclo scalare.
- **`matmul_q8_0_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:150`  
  Il tok deriva da blockIdx.y senza un parametro n_tok: la griglia deve limitarlo correttamente.
- **`matmul_q8_0_top1_preq_warp8_kernel`** `ds4_cuda.cu:7677`  
  Le parita' di score scelgono l'indice globale minore grazie alla codifica della chiave.
- **`matmul_q8_0_top1_unpack_kernel`** `ds4_cuda.cu:7725`  
  Se nessun candidato aggiorna la chiave zero, emette indice UINT32_MAX e un NaN.
- **`min_available_gib_from_env`** `src/cuda/dynamic_arena.cu:285`  
  Un valore invalido restituisce 0 ma marca valid=false e avvisa una sola volta
- **`mma16_m16n8k32_s8`** `ds4_cuda.cu:24295`  
  Sotto sm_80 è un no-op silenzioso e lascia invariati gli accumulatori
- **`mma_m16n8k32_s8`** `ds4_cuda.cu:8530`  
  Sotto sm_80 il ramo compilato non fa nulla e lascia invariati gli accumulatori senza errore.
- **`mma_m8n8k16_s8`** `ds4_cuda.cu:24009`  
  Sotto sm_75 è un no-op silenzioso e lascia invariati gli accumulatori
- **`model_scalar_dev`** `rocm/ds4_rocm_norm_rope.cuh:360`  
  Qualsiasi type diverso da 1 viene interpretato come float32.
- **`moe_build_expert_tile_offsets_kernel`** `rocm/ds4_rocm_moe.cuh:1050`  
  Il calcolo degli offset è seriale nel thread 0
- **`moe_count_sorted_pairs_kernel`** `rocm/ds4_rocm_moe.cuh:988`  
  Selezioni negative o fuori intervallo vengono ignorate, non rimappate all'esperto 0
- **`moe_down_expert_tile16_row2048_kernel`** `rocm/ds4_rocm_moe.cuh:2697`  
  Se tile_starts ha il bit 8 impostato, l'intero tile viene saltato
- **`moe_down_expert_tile16_row32_kernel`** `rocm/ds4_rocm_moe.cuh:2627`  
  Se tile_starts ha il bit 8 impostato, l'intero tile termina senza scrivere
- **`moe_down_expert_tile16_rowspan_kernel`** `rocm/ds4_rocm_moe.cuh:2770`  
  atomic_out scrive somme per token; altrimenti conserva un output per coppia
- **`moe_down_expert_tile4_row32_kernel`** `rocm/ds4_rocm_moe.cuh:2503`  
  atomic_out cambia la destinazione da matrice per coppia a somma per token
- **`moe_down_expert_tile8_kernel`** `rocm/ds4_rocm_moe.cuh:2464`  
  È marcato unused e non ha alcun lancio nel percorso corrente
- **`moe_down_expert_tile8_row32_kernel`** `rocm/ds4_rocm_moe.cuh:2564`  
  atomic_out accumula direttamente per token invece di scrivere risultati per coppia
- **`moe_down_f32_kernel`** `rocm/ds4_rocm_moe.cuh:4461`  
  Un selected negativo indirizza l'esperto 0 invece di annullare la coppia
- **`moe_down_hwarp16_kernel`** `rocm/ds4_rocm_moe.cuh:1899`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_down_iq1_s_qwarp32_kernel`** `ds4_cuda.cu:21283`  
  Un ID negativo viene sostituito con l'esperto 0 e produce comunque un dot product
- **`moe_down_kernel`** `rocm/ds4_rocm_moe.cuh:1841`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_down_owned_packed_qwarp32_kernel`** `ds4_cuda.cu:23347`  
  Se una componente non esiste scrive esplicitamente zero, invece di lasciare l'output invariato
- **`moe_down_owned_slots_qwarp32_kernel`** `ds4_cuda.cu:23278`  
  Gli slot non posseduti lasciano la rispettiva uscita invariata
- **`moe_down_q1_0_qwarp32_kernel`** `ds4_cuda.cu:21368`  
  Un esperto selezionato negativo viene sostituito silenziosamente con l'esperto 0
- **`moe_down_q4K_expert_tile8_rowspan_kernel`** `ds4_cuda.cu:23939`  
  Con oltre 8 blocchi midq usa i puntatori globali invece della copia in shared
- **`moe_down_q4K_owned_packed_qwarp32_kernel`** `ds4_cuda.cu:23498`  
  Una coppia prefissa viene già sommata; una componente senza slot viene invece azzerata
- **`moe_down_q4K_owned_slots_qwarp32_kernel`** `ds4_cuda.cu:23458`  
  Uno slot non locale termina senza azzerare la destinazione, che può restare stantia
- **`moe_down_q4K_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2260`  
  Un selected negativo usa l'esperto 0 e scrive comunque un risultato
- **`moe_down_q4K_sum3_qwarp32_kernel`** `ds4_cuda.cu:23668`  
  Un esperto negativo viene sostituito con l'esperto 0, non ignorato
- **`moe_down_q4K_sum3_slotwarp_kernel`** `ds4_cuda.cu:23700`  
  Un esperto negativo viene sostituito con l'esperto 0, non ignorato
- **`moe_down_q4K_sum6_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2231`  
  Con base o stride non allineati a 16 byte usa silenziosamente il dot scalare
- **`moe_down_q4K_tile16_mma_kernel`** `ds4_cuda.cu:24482`  
  Le righe mancanti del tile vengono zero-fillate prima della MMA
- **`moe_down_q4K_tile8_mma_kernel`** `ds4_cuda.cu:24186`  
  Con più di 8 blocchi midq legge shared memory non inizializzata
- **`moe_down_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:1925`  
  Un esperto selezionato negativo viene sostituito silenziosamente con l'esperto 0
- **`moe_down_sorted_p2_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2844`  
  Un selected negativo usa l'esperto 0 anziché produrre zero
- **`moe_down_sorted_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2437`  
  Un selected negativo viene convertito nell'esperto 0
- **`moe_down_sum3_qwarp32_kernel`** `ds4_cuda.cu:23399`  
  Un esperto negativo viene sostituito con l'esperto 0 prima della somma
- **`moe_down_sum6_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2065`  
  Un esperto negativo viene sostituito con l'esperto 0 prima della somma
- **`moe_down_warp8_kernel`** `rocm/ds4_rocm_moe.cuh:1872`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_filter_owned_pairs_kernel`** `ds4_cuda.cu:21157`  
  Distrugge gli ID globali originali e azzera i pesi non residenti
- **`moe_gate_up_mid_decode_lut_owned_qwarp32_kernel`** `ds4_cuda.cu:21685`  
  Per uno slot non posseduto esce senza azzerare mid_out
- **`moe_gate_up_mid_decode_lut_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:854`  
  Con write_aux a zero scrive mid ma lascia invariati gate_out e up_out
- **`moe_gate_up_mid_decode_q4K_hwarp16_kernel`** `ds4_cuda.cu:22615`  
  Il nome decode è fuorviante: può coprire anche il prefill non ordinato
- **`moe_gate_up_mid_decode_q4K_hwarp16_row8_kernel`** `ds4_cuda.cu:22673`  
  Metà del blocco ritorna senza calcolare dopo l'eventuale staging condiviso
- **`moe_gate_up_mid_decode_q4K_owned_warp32_noaux_kernel`** `ds4_cuda.cu:22855`  
  Uno slot non posseduto ritorna lasciando mid_out invariato
- **`moe_gate_up_mid_decode_q4K_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:1951`  
  Con write_aux a zero scrive mid ma lascia invariati gate_out e up_out
- **`moe_gate_up_mid_decode_q4K_warp32_kernel`** `ds4_cuda.cu:22733`  
  Con write_aux a zero scrive mid ma lascia invariati gate_out e up_out
- **`moe_gate_up_mid_decode_q4K_warp32_noaux_kernel`** `ds4_cuda.cu:22791`  
  Se base o stride non sono allineati a 16 byte passa silenziosamente al dot scalare
- **`moe_gate_up_mid_decode_q4K_warp32_noaux_sidecar_kernel`** `ds4_cuda.cu:22917`  
  Il sidecar conserva il valore con segno, non il suo valore assoluto
- **`moe_gate_up_mid_decode_q4K_warp32_row16_kernel`** `ds4_cuda.cu:22999`  
  Con write_aux a zero scrive mid ma lascia invariati gate_out e up_out
- **`moe_gate_up_mid_expert_tile4_row32_kernel`** `rocm/ds4_rocm_moe.cuh:1195`  
  Con write_aux a zero non aggiorna gate_out e up_out
- **`moe_gate_up_mid_expert_tile8_kernel`** `rocm/ds4_rocm_moe.cuh:1133`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_gate_up_mid_expert_tile8_row2048_kernel`** `rocm/ds4_rocm_moe.cuh:1373`  
  Le LUT shared restano non inizializzate quando xq_blocks supera 16
- **`moe_gate_up_mid_expert_tile8_row32_kernel`** `rocm/ds4_rocm_moe.cuh:1278`  
  Con write_aux a zero non aggiorna gate_out e up_out
- **`moe_gate_up_mid_expert_tile8_rowspan_kernel`** `rocm/ds4_rocm_moe.cuh:1471`  
  Le LUT shared restano non inizializzate quando xq_blocks supera 16
- **`moe_gate_up_mid_f32_kernel`** `rocm/ds4_rocm_moe.cuh:4341`  
  Un selected negativo indirizza l'esperto 0 invece di annullare la coppia
- **`moe_gate_up_mid_hwarp16_kernel`** `rocm/ds4_rocm_moe.cuh:640`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_gate_up_mid_iq1_s_qwarp32_kernel`** `ds4_cuda.cu:21231`  
  Un ID negativo legge l'esperto 0; il clamp non limita i valori gate negativi
- **`moe_gate_up_mid_kernel`** `rocm/ds4_rocm_moe.cuh:532`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_gate_up_mid_q1_0_qwarp32_kernel`** `ds4_cuda.cu:21316`  
  Un ID negativo legge l'esperto 0; il clamp non limita i valori gate negativi
- **`moe_gate_up_mid_q4K_expert_tile8_rowspan_kernel`** `ds4_cuda.cu:23163`  
  Con write_aux a zero non aggiorna gate_out e up_out
- **`moe_gate_up_mid_q4K_tile16_mma_kernel`** `ds4_cuda.cu:24386`  
  Le coppie mancanti sono azzerate in shared, ma gate e up restano intatti se write_aux è falso
- **`moe_gate_up_mid_q4K_tile8_mma_kernel`** `ds4_cuda.cu:24018`  
  write_aux falso lascia gate_out e up_out intatti mentre mid_out viene sempre scritto
- **`moe_gate_up_mid_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:688`  
  Un esperto negativo diventa l'esperto 0 e gate/up vengono sempre scritti
- **`moe_gate_up_mid_sorted_p2_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:1570`  
  L'ultima mezza coppia di un numero dispari viene scartata tramite ritorno anticipato
- **`moe_gate_up_mid_sorted_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:1084`  
  Un esperto negativo viene comunque rimappato all'esperto 0
- **`moe_gate_up_mid_warp8_kernel`** `rocm/ds4_rocm_moe.cuh:591`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_gate_up_midq_decode_q4K_qwarp32_kernel`** `ds4_cuda.cu:23058`  
  La scala Q8_K può essere negativa perché segue il segno del massimo assoluto
- **`moe_handoff_pack_kernel`** `ds4_cuda.cu:5585`  
  Il layout concatena float, int32 e float senza intestazione o padding.
- **`moe_owned_local_expert`** `ds4_cuda.cu:21084`  
  Un expert negativo fallisce senza scrivere local_expert
- **`moe_owned_packed_combine_row`** `ds4_cuda.cu:23595`  
  Se i primi due slot del gruppo sono peer, packed[0] è già la loro somma
- **`moe_owned_packed_component`** `ds4_cuda.cu:23314`  
  Solo il prefisso di slot 0 e 1 del gruppo può essere fuso in una componente
- **`moe_owned_slots_combine_fixed3_kernel`** `ds4_cuda.cu:23558`  
  Esperti negativi o fuori dal doppio intervallo contribuiscono silenziosamente zero
- **`moe_prefix_sorted_pairs_kernel`** `rocm/ds4_rocm_moe.cuh:1001`  
  Il prefisso è interamente seriale nel thread 0
- **`moe_prepare_sorted_tiles_small_kernel`** `ds4_cuda.cu:21828`  
  cursors riceve gli offset finali, non gli inizi usati dal percorso scatter
- **`moe_scatter_sorted_pairs_kernel`** `rocm/ds4_rocm_moe.cuh:1017`  
  L'ordine delle coppie dentro ciascun esperto è nondeterministico
- **`moe_sum_kernel`** `rocm/ds4_rocm_moe.cuh:2874`  
  Non consulta selected: anche gli slot invalidi o stantii entrano nella somma
- **`moe_sum_owned_kernel`** `ds4_cuda.cu:25111`  
  Oltre sei esperti vengono ignorati silenziosamente
- **`moe_tile16_mma_pass`** `ds4_cuda.cu:24311`  
  Restituisce i risultati nei registri e non scrive direttamente alcun tensore
- **`next_generation`** `src/cuda/dynamic_arena.cu:157`  
  Al wrap salta zero e riparte da uno
- **`observe_device`** `src/cuda/prefill_observer.cu:407`  
  Con n_tokens minore o uguale a 1 finalizza senza osservare i buffer passati.
- **`observe_host`** `src/cuda/prefill_observer.cu:477`  
  Non controlla enabled: richiede che request_begin abbia già armato lo stato.
- **`options_from_env`** `src/cuda/dynamic_arena.cu:330`  
  UNLOCK_WAVE_GIB non abilita lo sblocco; serve UNLOCK_SOURCE_RANGES=1
- **`output_hc_weights_kernel`** `rocm/ds4_rocm_output.cuh:6`  
  I gate non sono normalizzati e l'aggiunta di eps può portarli sopra 1
- **`pack_slot_rows_f32_kernel`** `rocm/ds4_rocm_common.cuh:334`  
  Trasforma un layout slot-major in row-major; non copia le righe oltre n_rows.
- **`parse_bool`** `src/cuda/vram_expert_cache.cpp:115`  
  Qualunque testo diverso da 0 o 1 restituisce il default ma marca valid=false
- **`physical_memory_available`** `src/cuda/dynamic_arena.cu:310`  
  Misura RAM host, non memoria CUDA né VRAM
- **`prepare_locked`** `src/cuda/dynamic_arena.cu:446`  
  Alloca RAM host, non VRAM; l'alias device ottenuto non viene conservato
- **`print_layer_range_for_tier`** `ds4_layer_pack.c:66`  
  Stampa un solo intervallo primo-ultimo anche se le assegnazioni del tier sono discontinue.
- **`publish_transaction`** `src/cuda/dynamic_arena.cu:606`  
  Accetta checksum già memorizzati senza ricalcolarli
- **`q8_0_dequant_f16_kernel`** `ds4_cuda.cu:16032`  
  Due thread cooperano su ogni blocco Q8_0 da 32 valori
- **`q8_K_q8_0_quantize_kernel`** `ds4_cuda.cu:21003`  
  Scrive otto blocchi Q8_0 per ogni blocco Q8_K
- **`q8_K_quantize_kernel`** `rocm/ds4_rocm_moe.cuh:483`  
  La scala può essere negativa perché conserva il segno del massimo assoluto
- **`q8_K_quantize_owned_kernel`** `ds4_cuda.cu:21099`  
  Le righe non possedute restano intatte, non vengono azzerate
- **`q8_K_quantize_sidecar_kernel`** `ds4_cuda.cu:21177`  
  La scala deriva dal sidecar, non dai 256 valori x che vengono quantizzati
- **`q8_top1_float_ordered_key`** `ds4_cuda.cu:7660`  
  Distingue -0 da +0 e ordina i NaN secondo il payload binario, non semanticamente.
- **`q8_top1_pack_key`** `ds4_cuda.cu:7665`  
  A parita' di valore, 0xffffffff - idx fa vincere l'indice piu' piccolo.
- **`q8_top1_unpack_value`** `ds4_cuda.cu:7670`  
  Una chiave ordinata zero viene ricostruita come NaN negativo.
- **`quantize_q8_0_f32_kernel`** `rocm/ds4_rocm_q8.cuh:81`  
  Il blocco finale viene sempre riempito a zero fino a 32 elementi.
- **`quantize_q8_0_group_slice_rows_kernel`** `ds4_cuda.cu:7550`  
  L'uscita usa indici di gruppo compatti, non gli indici originali n_groups_total.
- **`quarter_warp_sum_f32`** `rocm/ds4_rocm_moe.cuh:474`  
  Il parametro lane8 è ignorato; il gruppo deriva solo da threadIdx.x
- **`rank_less`** `src/cuda/prefill_observer.cu:283`  
  A parità di massa usa la chiave layer-esperto crescente.
- **`ranked_target`** `src/cuda/dynamic_arena.cu:1039`  
  A pari priorità vince l'osservazione più recente
- **`readback_consumer_fence`** `src/cuda/prefill_observer.cu:205`  
  Può bloccare la CPU fino al completamento delle copie device-host.
- **`readback_consumer_sync_enter`** `src/cuda/prefill_observer.cu:218`  
  Non esegue alcuna sincronizzazione né modifica di stato.
- **`readback_consumer_sync_exit`** `src/cuda/prefill_observer.cu:222`  
  Non esegue alcuna operazione.
- **`readback_events_create`** `src/cuda/prefill_observer.cu:125`  
  Un errore CUDA viene ridotto a false dopo aver cancellato l'ultimo errore.
- **`readback_events_destroy`** `src/cuda/prefill_observer.cu:111`  
  Ignora gli errori CUDA e azzera comunque lo stato.
- **`readback_events_ready`** `src/cuda/prefill_observer.cu:153`  
  Non interroga CUDA: ready significa predisposto, non completato.
- **`readback_outstanding_locked`** `src/cuda/prefill_observer.cu:157`  
  Conta come outstanding anche un evento già completato ma non ritirato.
- **`readback_poll_locked`** `src/cuda/prefill_observer.cu:253`  
  Restituisce true anche quando alcuni readback non sono ancora pronti.
- **`readback_retire_locked`** `src/cuda/prefill_observer.cu:225`  
  Con wait=false può restituire true lasciando il readback ancora pendente.
- **`readback_tail_retire_locked`** `src/cuda/prefill_observer.cu:260`  
  Controlla gli outstanding dopo clear, quindi il conteggio finale è necessariamente zero.
- **`release`** `src/cuda/prefill_observer.cu:402`  
  Anche se cudaFreeHost fallisce, azzera lo stato e perde il puntatore.
- **`release_locked`** `src/cuda/dynamic_arena.cu:432`  
  Un errore di cudaFreeHost non impedisce l'azzeramento dello stato
- **`release_vram_reader`** `src/cuda/dynamic_arena.cu:1228`  
  Se slot o generazione non coincidono, azzera il reader senza rilasciare il claim.
- **`release_writer_claims`** `src/cuda/dynamic_arena.cu:392`  
  Gli indici fuori arena vengono ignorati silenziosamente
- **`repeat_hc_kernel`** `rocm/ds4_rocm_common.cuh:316`  
  Ogni copia e' identica: non applica pesi o trasformazioni hyper-connection.
- **`repeat_hc_rows_kernel`** `rocm/ds4_rocm_common.cuh:323`  
  L'ordine di uscita e' token, hyper-connection, embedding.
- **`request_begin`** `src/cuda/prefill_observer.cu:385`  
  Può contare due volte: è chiamata sia dal boundary CUDA sia dal reset hotness.
- **`requested_bytes_from_env`** `src/cuda/dynamic_arena.cu:260`  
  Assenza, stringa vuota e 0 sono disabilitazioni valide; gli altri errori rendono valid=false
- **`requested_u32`** `src/cuda/prefill_observer.cu:79`  
  La stringa esatta 0 bypassa zero_allowed; 00 può invece risultare invalida.
- **`restore_env`** `src/cuda/prefill_observer.cu:369`  
  Ignora completamente un eventuale errore di ripristino.
- **`rms_norm_plain_batch8_kernel`** `ds4_cuda.cu:8931`  
  Gli otto carichi sono incondizionati; una coda parziale accede fuori dai limiti.
- **`rms_norm_plain_fast4096_kernel`** `ds4_cuda.cu:8903`  
  Ignora la generalità del parametro n e legge sempre sedici valori per thread.
- **`rms_norm_plain_kernel`** `rocm/ds4_rocm_norm_rope.cuh:1`  
  La riduzione condivisa è corretta solo con la geometria di lancio prevista.
- **`rope_tail_decode_rows_kernel`** `ds4_cuda.cu:9288`  
  Le posizioni arrivano dalla tabella e non devono essere contigue.
- **`rope_tail_kernel`** `rocm/ds4_rocm_norm_rope.cuh:251`  
  La posizione avanza di pos_stride, che nel compressore vale il rapporto di compressione.
- **`rope_tail_one_dev`** `rocm/ds4_rocm_norm_rope.cuh:385`  
  È marcata unused e non ha chiamanti nel runtime.
- **`rope_yarn_ramp_cpu_equiv_dev`** `rocm/ds4_rocm_norm_rope.cuh:380`  
  Il suo unico chiamante è marcato unused e non è invocato.
- **`rope_yarn_ramp_dev`** `rocm/ds4_rocm_norm_rope.cuh:246`  
  Usa divisione intera i0/2, quindi coppie adiacenti condividono la rampa.
- **`routed_moe_decode_graph_destroy_one`** `ds4_cuda.cu:23739`  
  Ignora gli errori di destroy e azzera comunque gli handle in cache
- **`routed_moe_decode_q4_graph_launch`** `ds4_cuda.cu:23747`  
  Usa sempre lo stream CUDA 0; ogni errore distrugge l'intera cache del tier
- **`routed_moe_launch`** `rocm/ds4_rocm_moe_launch.cuh:520`  
  Le variabili DS4_CUDA_MOE_* sono flag di presenza: anche il valore "0" le attiva
- **`router_score_better`** `rocm/ds4_rocm_router.cuh:7`  
  A parità di score vince l'indice minore.
- **`router_select_kernel`** `ds4_cuda.cu:13424`  
  hash_mode salta il top-6: prende gli indici dalla hash ma i pesi dai logit.
- **`router_select_parallel_kernel`** `ds4_cuda.cu:13476`  
  Dopo le probabilità, solo il thread 0 esegue la selezione seriale.
- **`router_select_warp_topk_kernel`** `rocm/ds4_rocm_router.cuh:11`  
  hash_mode ignora il bias e rimappa token fuori intervallo sulla riga 0.
- **`run_copy_workers`** `src/cuda/dynamic_arena.cu:857`  
  Se creare un thread fallisce completa il lavoro residuo ma restituisce false
- **`run_fixture`** `src/cuda/prefill_observer.cu:582`  
  Azzera l'arena globale all'inizio e alla fine, distruggendo eventuale stato vivo.
- **`save_env`** `src/cuda/prefill_observer.cu:364`  
  Copia il valore ma conserva il puntatore originale al nome.
- **`seed_ranked`** `src/cuda/dynamic_arena.cu:1245`  
  Arena disabilitata o lista vuota restituiscono successo senza seminare.
- **`seed_request_ranked`** `src/cuda/dynamic_arena.cu:1288`  
  Con n_experts zero ritorna successo ma conserva ranking e snapshot precedenti.
- **`seed_selected`** `src/cuda/dynamic_arena.cu:1267`  
  Ogni ID ripetuto aumenta ancora il peso; lista vuota o arena spenta danno successo.
- **`select_ranking_locked`** `src/cuda/prefill_observer.cu:290`  
  La quota fallisce se anche un solo layer ha meno candidati del richiesto.
- **`set_env_value`** `src/cuda/prefill_observer.cu:350`  
  Su Windows la rimozione passa una stringa vuota a _putenv_s.
- **`shared_mid_q8_0_preq_warp8_exact_kernel`** `ds4_cuda.cu:7820`  
  In parita' tra esperti home e peer scrive il rank home; l'altro termina senza scrivere.
- **`slot_capacity`** `src/cuda/dynamic_arena.cu:279`  
  Il risultato satura a UINT32_MAX
- **`slot_reader_acquire`** `src/cuda/dynamic_arena.cu:186`  
  Non attende: writer presente o contatore saturo causano subito false
- **`slot_reader_release`** `src/cuda/dynamic_arena.cu:211`  
  Un rilascio sbilanciato manda il contatore in underflow
- **`slot_refs_load`** `src/cuda/dynamic_arena.cu:176`  
  Su Windows una CAS 0 su 0 simula la sola lettura
- **`slot_writer_release`** `src/cuda/dynamic_arena.cu:233`  
  Azzera l'intero contatore invece di rimuovere un singolo bit
- **`slot_writer_try_acquire`** `src/cuda/dynamic_arena.cu:220`  
  Non attende la fine dei reader: fallisce immediatamente
- **`softplus_dev`** `rocm/ds4_rocm_router.cuh:1`  
  Per x minore di -20 approssima softplus con exp(x).
- **`store_raw_kv_batch_kernel`** `rocm/ds4_rocm_fp8_kv.cuh:31`  
  Memorizza il valore arrotondato come float32 e sovrascrive le righe modulo raw_cap.
- **`swiglu_kernel`** `rocm/ds4_rocm_output.cuh:23`  
  Il clamp del gate è solo superiore; quello di up è simmetrico.
- **`top2_insert_candidate`** `ds4_cuda.cu:14325`  
  Ignora in silenzio un indice già presente in una delle due posizioni.
- **`topk_float_ordered_key`** `rocm/ds4_rocm_indexer.cuh:312`  
  I NaN vengono ordinati per rappresentazione binaria, non per semantica numerica.
- **`topk_mask_kernel`** `rocm/ds4_rocm_indexer.cuh:745`  
  Indici fuori intervallo o duplicati non danno errore e lasciano meno di top_k zeri.
- **`topk_pack_key`** `rocm/ds4_rocm_indexer.cuh:317`  
  L'indice è complementato, quindi a parità vince quello minore.
- **`topk_score_better`** `rocm/ds4_rocm_indexer.cuh:308`  
  A parità di score vince l'indice minore.
- **`unlock_source_range`** `src/cuda/dynamic_arena.cu:789`  
  Su Windows ERROR_NOT_LOCKED vale successo; su POSIX usa posix_madvise
- **`update_and_wrap_locked`** `src/cuda/dynamic_arena.cu:1063`  
  Con accumulate=true il ranking persiste e può saturare UINT64_MAX
- **`verify_active_locked`** `src/cuda/dynamic_arena.cu:1109`  
  Rifiuta anche uno snapshot coerente ma vuoto
- **`warp_max_f32`** `rocm/ds4_rocm_common.cuh:361`  
  Solo la lane 0 riceve il massimo globale; le altre conservano massimi parziali.
- **`warp_sum_f32`** `rocm/ds4_rocm_common.cuh:350`  
  Solo la lane 0 riceve la somma completa; le altre conservano somme parziali.
- **`wrap_enabled`** `src/cuda/prefill_observer.cu:376`  
  Rilegge l'ambiente a ogni chiamata, quindi può cambiare durante una richiesta.
- **`wrap_transaction`** `src/cuda/dynamic_arena.cu:917`  
  Con trust=false calcola FNV due volte per slot; con true salta la verifica indipendente

### Certezza media (2)

- **`dequant_q8_0_to_f16_kernel`** `rocm/ds4_rocm_q8.cuh:1737`  
  Materializza tutta la matrice e può espandere molto l'uso di VRAM.
- **`dequant_q8_0_to_f32_kernel`** `rocm/ds4_rocm_q8.cuh:1756`  
  Materializza tutta la matrice in FP32, ampliandola di circa quattro volte.

## Come rifare questo documento

```bash
python ricongiungi.py ../../../ds4-port/lotti
```
