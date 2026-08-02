# Sintesi della mappa

Generato da `ricongiungi.py`. **Non modificare a mano**: si rifa'.

Copertura: **4538 funzioni schedate su 5164** (87.9%).

Di queste, 4 con certezza non alta: dequant_q8_0_to_f16_kernel (media), dequant_q8_0_to_f32_kernel (media), matvec_f16_serial (media), ds4_engine_tp_batch_exchange (media)

## Cosa gli agenti hanno sbagliato

- **doppione**: 626 — es. SCHEDE_004.tsv:20 cuda_moe_io_queue_depth

## Il cammino caldo

1861 funzioni girano per token, per strato o per esperto.

### Allocano o liberano VRAM sul cammino caldo

Su una scheda dove il gigabyte e' la partita, questa e' la lista che conta.

| funzione | vram | frequenza | dove | cosa fa |
|---|---|---|---|---|
| `cuda_model_arena_alloc` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:5517` | Serve una slice allineata da un'arena VRAM esistente o alloca un nuovo blocco. |
| `cuda_model_range_ptr_from_fd` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:5569` | Alloca e carica dal file una range di pesi nella cache VRAM, poi la indicizza. |
| `cuda_stream_expert_slab_grow` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:1568` | Alloca una slab fino a 1 GiB e la suddivide in slot esperto uguali. |
| `cuda_stream_expert_slot_acquire` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:1616` | Preleva uno slot libero, cresce una slab o espelle un esperto per riciclarlo. |
| `cuda_stream_resident_alloc` | alloca | per-esperto | `rocm/ds4_rocm_runtime.cuh:1639` | Riserva VRAM contigua per gate, up e down di un esperto e lo indicizza. |
| `cuda_stream_resident_cache_prepare_locked` | alloca | per-esperto | `ds4_cuda.cu:28067` | Dimensiona e alloca la cache residente dopo che il workspace attenzione è già presente. |
| `cuda_stream_resident_evict_at` | libera | per-esperto | `rocm/ds4_rocm_runtime.cuh:1442` | Espelle un esperto residente, riciclando lo slot pooled o liberando la sua VRAM. |
| `cuda_stream_resident_evict_one` | libera | per-esperto | `rocm/ds4_rocm_runtime.cuh:1475` | Sceglie una vittima LRU evitando gli esperti correnti e la espelle. |
| `cuda_stream_resident_make_room` | libera | per-esperto | `rocm/ds4_rocm_runtime.cuh:1540` | Espelle esperti finché rispetta budget numerico e riserva di VRAM libera. |
| `attention_decode_batch_launch` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:214` | Esegue attenzione decode raw o mista per un lotto scegliendo il kernel compatibile |
| `attention_decode_score_split_launch` | alloca | per-layer | `ds4_cuda.cu:11458` | Seleziona e lancia il percorso score-split esatto, allocandone lo scratch temporaneo. |
| `attention_decode_splitkv_launch` | alloca | per-layer | `ds4_cuda.cu:18456` | Suddivide lo score KV del decode singolo e combina i parziali con softmax |
| `attention_prefill_mixed_launch` | alloca | per-layer | `rocm/ds4_rocm_attention_launch.cuh:619` | Calcola prefill su KV raw e compresso scegliendo online, cuBLAS o kernel base |
| `cuda_matmul_q8_0_hc_expand_tensor_labeled` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:641` | Fonde proiezione Q8_0, addendi opzionali ed espansione hidden-copy |
| `cuda_matmul_q8_0_tensor_f16_gemm` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:183` | Converte le attivazioni in F16 e usa cuBLAS sui pesi Q8_0 dequantizzati, producendo F32 |
| `cuda_matmul_q8_0_tensor_f16_gemm_out_half` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:240` | Converte le attivazioni in F16 e usa cuBLAS sui pesi Q8_0 dequantizzati, producendo F16 |
| `cuda_matmul_q8_0_tensor_labeled` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:311` | Esegue una matmul Q8_0 scegliendo cache cuBLAS, GEMM F16 o kernel nativi |
| `cuda_model_range_copy_uncached` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:4562` | Alloca e copia in VRAM un range da una mappa modello non principale. |
| `cuda_model_range_ptr` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:4589` | Rende un range di pesi accessibile alla GPU tramite cache, mapping host o copia. |
| `cuda_q8_f16_ptr` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5015` | Restituisce o crea sul device una copia fp16 dequantizzata di un peso q8. |
| `cuda_q8_f16_transpose_ptr` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5073` | Restituisce o crea in VRAM la trasposta F16 dequantizzata da pesi Q8. |
| `cuda_q8_f32_ptr` | alloca | per-layer | `ds4_cuda.cu:3212` | Restituisce o crea sul device una copia fp32 dequantizzata di un peso q8. |
| `cuda_resolve_weight_ptr` | alloca | per-layer | `ds4_cuda.cu:2750` | Risolve il puntatore device di un peso sul tier richiesto o sul device CUDA corrente. |
| `cuda_stream_batch_selected_ensure_buffers` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:1190` | Dimensiona ID, flag e sette tabelle puntatori per le selezioni batch. |
| `cuda_stream_batch_selected_prepare_from_host` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:3108` | Compatta gli ID batch, alloca miss residenti e prepara tabelle per esecuzione split. |
| `cuda_stream_layer_expert_cache_load` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:2548` | Carica da file gate, up e down di tutti gli esperti in un buffer full-layer. |
| `cuda_stream_layer_expert_cache_seed_selected` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:3821` | Copia nella cache residente gli esperti unici degli ultimi token selezionati. |
| `cuda_stream_resident_seed_experts` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:2679` | Precarica nella cache residente gli esperti prioritari di una hotlist. |
| `cuda_stream_selected_ensure_buffers` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:1035` | Dimensiona buffer esperti, slot e tabelle puntatori della cache selettiva. |
| `cuda_stream_selected_ensure_bytes` | alloca | per-layer | `ds4_cuda.cu:28942` | Assicura un buffer CUDA di almeno i byte richiesti, riallocandolo se serve. |
| `cuda_stream_selected_ensure_i32` | alloca | per-layer | `ds4_cuda.cu:29021` | Alloca remap selezioni |
| `cuda_stream_selected_load` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:4040` | Avvia o completa il caricamento degli esperti selezionati per un singolo token. |
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
| `ds4_gpu_glm_attention_indexed_batch_tensor` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:3443` | Calcola attenzione indicizzata batch e proietta i valori Q8_0 usando uno scratch LoRA |
| `ds4_gpu_glm_attention_indexed_decode_tensor` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:3528` | Calcola attenzione indicizzata per un token e proietta i valori Q8_0 |
| `ds4_gpu_glm_attention_indexed_decode_typed_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:351` | Valida e lancia l'attenzione MLA indicizzata, scegliendo percorso fuso, staged o MTP a due token. |
| `ds4_gpu_glm_qk_lowrank_typed_batch_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:329` | Proietta Q nel rango KV con pesi Q8_0, usando cuBLAS dequantizzato sui batch grandi. |
| `ds4_gpu_glm_routed_moe_batch_tensor` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:4077` | Esegue l'intero MoE routed batch: quantizza, calcola gate/up, requantizza e proietta down. |
| `ds4_gpu_indexer_topk_tensor` | alloca | per-layer | `rocm/ds4_rocm_indexer.cuh:856` | Seleziona gli indici dei top-k score per ogni token |
| `ds4_gpu_matmul_f16_pair_tensor` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:785` | Calcola due proiezioni F16 dalla stessa attivazione |
| `ds4_gpu_matmul_f16_router_rows_exact_tensor` | alloca | per-layer | `ds4_rocm_compat.cu:229` | Calcola il router F16 fisso 4096x256 preservando l'ordine per riga |
| `ds4_gpu_matmul_q8_0_decode_mpp_model_view_tensor` | alloca | per-layer | `rocm/ds4_rocm_matmul.cuh:534` | Delega matmul model-view |
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
| `ds4_gpu_stream_expert_cache_load_layer` | alloca | per-layer | `rocm/ds4_rocm_current_api_compat.cuh:248` | Carica intero layer |
| `ds4_gpu_tensor_alloc_kv_cache` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5920` | Alloca un KV cache sulla GPU 0 e lo registra per lo staging host quando richiesto. |
| `ds4_gpu_tensor_alloc_managed` | alloca | per-layer | `rocm/ds4_rocm_runtime.cuh:5907` | Crea un tensor CUDA managed e lo associa contabilmente alla GPU logica 0. |
| `ds4_gpu_tensor_alloc_managed_on` | alloca | per-layer | `ds4_rocm_compat.cu:56` | Alloca memoria CUDA managed sotto il device del tier e registra quel tier nel tensor. |
| `glm_attention_indexed_lora_causal_gemm` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:2612` | Esegue l'attenzione causale prefill tramite GEMM FP16 cuBLAS e scratch temporaneo |
| `glm_attention_indexed_lora_selected_gemm` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:2828` | Esegue attenzione prefill selezionata con GEMM FP16 batched e mattonelle di teste |
| `glm_graph_tp_batch_bounce_ready` | alloca | per-layer | `ds4.c:40090` | Garantisce due buffer bounce TP abbastanza grandi per il batch. |
| `glm_rocm_routed_moe_wrap` | alloca | per-layer | `rocm/ds4_rocm_glm.cuh:3959` | Alloca scratch FP32 e inoltra il MoE instradato al percorso singolo o batch |
| `metal_graph_attn_comp_prefill_target_free` | libera | per-layer | `ds4.c:20205` | Libera target prefill |
| `metal_graph_check_hc_norm_fusion` | alloca | per-layer | `ds4.c:19998` | Ricalcola HC e norma di riferimento, legge i risultati e confronta gli errori. |
| `metal_graph_ensure_batch_ffn_out` | alloca | per-layer | `ds4.c:16603` | Garantisce output FFN. |
| `metal_graph_ensure_batch_ffn_out_on` | alloca | per-layer | `ds4.c:16594` | Alloca pigramente lo scratch FFN batch sul tier indicato. |
| `metal_graph_ensure_ffn_out` | alloca | per-layer | `ds4.c:16585` | Alloca pigramente lo scratch FFN del token sul tier attivo. |
| `routed_moe_launch` | alloca | per-layer | `rocm/ds4_rocm_moe_launch.cuh:520` | Valida i tensori e orchestra quantizzazione, routing ordinato, gate-up, down e somma MoE CUDA |
| `cuda_embed_row_stage_alloc` | alloca | per-token | `ds4_cuda.cu:2398` | Crea o amplia lo staging pinned-host più device per copiare righe embedding. |
| `cuda_kv_staged_ring_ensure_locked` | alloca | per-token | `ds4_cuda.cu:4959` | Crea o ridimensiona ring, accumulatori, eventi e stream richiesti dal KV staged. |
| `dist_worker_get_session_locked` | alloca | per-token | `ds4_distributed.c:6944` | Trova o crea una sessione worker. Solo POSIX: non gira su Windows. |
| `ds4_gpu_matmul_q8_0_top1_tensor` | alloca | per-token | `ds4_cuda.cu:16345` | Fonde proiezione Q8_0 e selezione top-1 senza materializzare tutti i logit |
| `glm_graph_mtp_ensure` | alloca | per-token | `ds4.c:42473` | Alloca una sola volta cache KV privata e scratch del blocco MTP. |
| `session_greedy_splitkv_reset` | libera | per-token | `ds4.c:49894` | Azzera segmento e ancora del fallback greedy split-KV e libera la frontiera salvata. |

## Trappole

Comportamenti che sorprenderebbero chi usa la funzione. Ordinate per certezza dichiarata dall'agente.

### Certezza alta (4405)

- **`__dp4a`** `ds4_rocm.h:117`  
  Il terzo argomento c è già l'accumulatore, non un altro fattore.
- **`__vcmpne4`** `ds4_rocm.h:95`  
  Restituisce una maschera 0xFF per lane, non un booleano scalare.
- **`__vsub4`** `ds4_rocm.h:105`  
  La sottrazione è modulo 256 per lane, non saturante.
- **`abAppend`** `linenoise.c:980`  
  Se realloc fallisce, l'append viene saltato senza segnalazione.
- **`abAppendUtf8Clipped`** `linenoise.c:1010`  
  Può accodare CSI anche quando non resta spazio per testo visibile.
- **`abFree`** `linenoise.c:989`  
  Non azzera il puntatore dopo free.
- **`abInit`** `linenoise.c:975`  
  Non registra capacità separata dalla lunghezza.
- **`abort_transaction`** `src/cuda/dynamic_arena.cu:401`  
  Non ripristina vittime sovrascritte: elimina i binding non più ready
- **`accelerator_cache_model_tensors`** `ds4.c:3123`  
  Su CUDA la presenza di DS4_CUDA_DIRECT_MODEL salta tutta la preparazione, anche se vuoto
- **`accelerator_cache_q8_tensors`** `ds4.c:3068`  
  Il callee può disabilitare i preload dopo un errore opzionale e restituire comunque successo
- **`accelerator_cuda_preload_span_bytes`** `ds4.c:2902`  
  Su ROCm ignora l'ambiente; valori vuoti, invalidi o zero lasciano 1024 MiB
- **`accelerator_prepare_model_tensor_spans`** `ds4.c:2955`  
  Un singolo tensore più grande del limite viene comunque preparato intero
- **`accelerator_span_filter_contains`** `ds4.c:2938`  
  Nessun filtro o zero byte restituisce vero; una semplice sovrapposizione non basta
- **`accelerator_tensor_name_has_suffix`** `ds4.c:2917`  
  Un tensore o suffisso nullo restituisce falso
- **`accelerator_tensor_span_cmp`** `ds4.c:2892`  
  È usata indirettamente da qsort, sebbene il grafo meccanico non rilevi chiamanti
- **`accelerator_tensor_uses_embedding_row_staging`** `ds4.c:2927`  
  La sola presenza di DS4_CUDA_EMBED_ROW_STAGING, anche vuoto, abilita lo staging
- **`accumulate_locked`** `src/cuda/prefill_observer.cu:165`  
  Scarta in silenzio esperti invalidi e pesi non finiti o non positivi.
- **`acquire_vram_reader`** `src/cuda/dynamic_arena.cu:1174`  
  Ricalcola FNV dell'intero slot sotto il mutex globale a ogni hit
- **`agent_append_system_prompt`** `ds4_agent.c:1141`  
  Il testo utente extra evita il tokenizer dei marker di controllo ed entra come messaggio separato.
- **`agent_apply_file_splice`** `ds4_agent.c:7013`  
  Riscrive l'intero file in modo non atomico.
- **`agent_apply_model_sampling_defaults`** `ds4_agent.c:783`  
  Non modifica modelli non GLM-DSA e preserva ogni parametro marcato come impostato.
- **`agent_bash_display_lines`** `ds4_agent.c:7455`  
  L'ultimo segmento senza LF conta come riga aggiuntiva.
- **`agent_bash_drain`** `ds4_agent.c:7512`  
  Gli errori di write_all sul file temporaneo non vengono controllati qui.
- **`agent_bash_finalize`** `ds4_agent.c:7534`  
  Un segnale diventa exit_status 128 più il numero del segnale.
- **`agent_bash_find_job`** `ds4_agent.c:7491`  
  Un ID positivo fa ignorare completamente un PID eventualmente fornito.
- **`agent_bash_job_free`** `ds4_agent.c:7468`  
  Se ancora attivo usa SIGKILL; chiude ma non elimina il file temporaneo di output.
- **`agent_bash_job_tool_result`** `ds4_agent.c:7885`  
  Uno status su job già finito può rimuoverlo subito, rendendo impossibili richieste successive.
- **`agent_bash_jobs_compaction_observation`** `ds4_agent.c:8009`  
  Marca ogni job osservato e rimuove quelli finiti mentre costruisce il promemoria.
- **`agent_bash_jobs_free`** `ds4_agent.c:7481`  
  La chiusura del worker uccide i processi ancora attivi.
- **`agent_bash_note_output`** `ds4_agent.c:7460`  
  Conta soltanto LF, non CR isolati.
- **`agent_bash_observation`** `ds4_agent.c:7745`  
  Aggiorna observed, ma le osservazioni successive ristampano comunque la tail completa.
- **`agent_bash_poll`** `ds4_agent.c:7557`  
  Non esiste reaper in background: timeout e uscita sono rilevati solo quando qualcuno effettua poll.
- **`agent_bash_publish_observation`** `ds4_agent.c:7828`  
  Nasconde dalla pubblicazione interattiva metadati come stato, PID e percorso.
- **`agent_bash_read_head`** `ds4_agent.c:7676`  
  Un errore di apertura diventa testo di output, non un errore separato.
- **`agent_bash_read_tail_lines`** `ds4_agent.c:7709`  
  Prima limita a 32 KiB per byte, quindi può perdere parte delle righe richieste.
- **`agent_bash_refresh_for`** `ds4_agent.c:7871`  
  Può bloccare sincronicamente fino a refresh_sec, a scatti di poll da 100 ms.
- **`agent_bash_remove_job`** `ds4_agent.c:7499`  
  Se il target non è nella lista non segnala nulla; il file temporaneo resta sul disco.
- **`agent_bash_start`** `ds4_agent.c:7592`  
  stdin è /dev/null; stdout e stderr sono fusi e il file temporaneo non viene eliminato.
- **`agent_buf_append`** `ds4_agent.c:3958`  
  Superati 128 KiB tronca una volta e ignora per sempre ogni append successiva.
- **`agent_buf_puts`** `ds4_agent.c:3977`  
  Eredita il limite silenzioso di 128 KiB del buffer.
- **`agent_buf_take`** `ds4_agent.c:3981`  
  Se il buffer è vuoto alloca e restituisce comunque una stringa vuota.
- **`agent_build_dsml_tools_prompt`** `ds4_agent.c:1046`  
  Il chiamante acquisisce ownership del buffer restituito.
- **`agent_build_glm_tools_prompt`** `ds4_agent.c:1096`  
  Il chiamante acquisisce ownership del buffer restituito.
- **`agent_build_system_prompt_reminder`** `ds4_agent.c:1130`  
  Ricostruisce e incorpora l'intero prompt dei tool, non il breve reminder di sintassi statico.
- **`agent_build_tools_prompt`** `ds4_agent.c:1109`  
  Solo GLM-DSA riceve il formato GLM; ogni altro engine riceve DSML.
- **`agent_bytes_partial_prefix_at`** `ds4_agent.c:1627`  
  Restituisce false per una corrispondenza già completa.
- **`agent_bytes_starts_with`** `ds4_agent.c:1621`  
  Un prefisso vuoto corrisponde sempre.
- **`agent_compact_make_prompt`** `ds4_agent.c:8090`  
  Il motivo è inserito senza escaping nel prompt interno.
- **`agent_compact_tail_start`** `ds4_agent.c:8060`  
  Se il marker non è un token singolo ripiega sul target, anche nel mezzo di un turno.
- **`agent_completion_session_cmp`** `ds4_agent.c:5521`  
  A parità di data ordina lessicograficamente per SHA.
- **`agent_completion_sessions_push`** `ds4_agent.c:5509`  
  Copia sempre 41 byte dallo SHA passato.
- **`agent_count_lines`** `ds4_agent.c:7282`  
  Conta come riga anche l'ultimo segmento privo di LF.
- **`agent_default_cache_dir`** `ds4_agent.c:4013`  
  Senza HOME usa la directory corrente, non una home ricavata dal sistema.
- **`agent_dsml_close_tag_at`** `ds4_agent.c:1520`  
  Accetta spazi e una barra DSML opzionale prima di >.
- **`agent_dsml_feed`** `ds4_agent.c:1875`  
  Dopo DONE o ERROR ignora ogni byte successivo; la coda di ricerca è limitata a 64 byte.
- **`agent_dsml_find_close_tag`** `ds4_agent.c:1612`  
  Scansiona solo occorrenze del prefisso DSML e tollera le varianti ammesse dalla verifica finale.
- **`agent_dsml_finish`** `ds4_agent.c:1763`  
  Finalizza solo GLM dopo una chiamata completa e solo se il resto contiene esclusivamente spazi.
- **`agent_dsml_marker_detector_feed`** `ds4_agent.c:3669`  
  Conserva solo la coda fissa e segnala anche varianti ASCII o con barra mancante.
- **`agent_dsml_open_tag_is`** `ds4_agent.c:1511`  
  Accetta il nome solo se seguito da > o spazio ASCII, rendendo l'apertura più rigida della chiusura.
- **`agent_dsml_parameter_close_tail`** `ds4_agent.c:1539`  
  Una chiusura è completa solo se > è esattamente l'ultimo byte del tail.
- **`agent_dsml_parse`** `ds4_agent.c:1783`  
  Per GLM delega subito; in DSML le chiusure sono tolleranti ma le aperture restano rigide.
- **`agent_dsml_parser_free`** `ds4_agent.c:1452`  
  Dopo memset ripristina deliberatamente la sintassi precedente.
- **`agent_dsml_parser_reset`** `ds4_agent.c:1463`  
  Libera anche chiamate già raccolte, ma conserva la sintassi selezionata.
- **`agent_dsml_raw_append`** `ds4_agent.c:1468`  
  La capacità parte da 512 e raddoppia senza limite o controllo di overflow.
- **`agent_dsml_set_error`** `ds4_agent.c:1492`  
  Il testo viene troncato alla dimensione fissa del campo error.
- **`agent_dsml_start`** `ds4_agent.c:1866`  
  Inserisce autonomamente nel raw la marca iniziale invece di copiarla dal buffer di ricerca.
- **`agent_dsml_update_param_close_prefix`** `ds4_agent.c:1587`  
  Considera solo l'ultimo < e ignora tail oltre 64 byte.
- **`agent_echo_user_prompt`** `ds4_agent.c:9207`  
  Usa printf su stringa NUL-terminata, quindi eventuali byte dopo un NUL non sono emessi.
- **`agent_edit_find_old_span`** `ds4_agent.c:6527`  
  Dopo [upto] elimina CR e LF iniziali; la tail deve essere unica solo dopo la head.
- **`agent_edit_old_is_only_space`** `ds4_agent.c:6434`  
  Il buffer vuoto è considerato composto solo da spazi.
- **`agent_edit_old_may_be_closing_tag`** `ds4_agent.c:6426`  
  Qualunque carattere minore dopo spazi vale, anche se non forma davvero un tag di chiusura.
- **`agent_edit_old_prefix_mature_for_upto`** `ds4_agent.c:6450`  
  Conta solo righe non vuote già chiuse da LF; l'ultima riga aperta non vale.
- **`agent_edit_old_ready_for_upto`** `ds4_agent.c:6465`  
  Qualunque stringa [upto] nel contenuto disabilita il forcing.
- **`agent_edit_result`** `ds4_agent.c:6025`  
  Per delta zero omette del tutto l'avviso sullo spostamento.
- **`agent_edit_result_append_context`** `ds4_agent.c:6295`  
  Se l'area editata è lunga omette le righe centrali, mostrando 18 di testa e 18 di coda.
- **`agent_edit_result_append_line`** `ds4_agent.c:6282`  
  Esclude CR e LF originali e aggiunge sempre LF.
- **`agent_edit_upto_forcer_should_replace`** `ds4_agent.c:6480`  
  Errori di lettura o anchor non unico disattivano il forcing senza errore visibile.
- **`agent_err_is_interrupted`** `ds4_agent.c:3943`  
  Richiede la stringa esatta e minuscola, senza prefissi o dettagli.
- **`agent_execute_tool_call`** `ds4_agent.c:7927`  
  bash attende di default fino a 60 secondi; tool sconosciuti producono errore ma non abortiscono.
- **`agent_execute_tool_calls`** `ds4_agent.c:7989`  
  Non c'è rollback: gli effetti delle chiamate precedenti restano se una successiva fallisce.
- **`agent_find_unique`** `ds4_agent.c:6362`  
  Cerca la seconda occorrenza da un byte dopo la prima, rilevando anche sovrapposizioni.
- **`agent_find_unique_after`** `ds4_agent.c:6394`  
  Occorrenze precedenti a start sono intenzionalmente ignorate.
- **`agent_footer_is_multiline`** `ds4_agent.c:9431`  
  Qualunque newline, anche finale e senza seconda riga visibile, vale multilinea.
- **`agent_format_age`** `ds4_agent.c:4829`  
  Timestamp zero o nel futuro vengono mostrati come 0s ago.
- **`agent_format_ctx_size`** `ds4_agent.c:10310`  
  Usa migliaia decimali: 1024 diventa 1.0k, mentre i multipli esatti di 1000 non hanno decimali.
- **`agent_format_user_prompt_echo`** `ds4_agent.c:9193`  
  Inserisce ANSI solo se stdout è TTY e restituisce sempre testo heap da liberare.
- **`agent_format_welcome_banner`** `ds4_agent.c:10319`  
  I colori e l'emoji dipendono solo dal fatto che stdout sia un TTY.
- **`agent_glm_arg_value_close_tail`** `ds4_agent.c:1567`  
  Accetta esclusivamente il tag esatto, senza spazi o varianti tollerate dal parser DSML.
- **`agent_glm_tool_parse`** `ds4_agent.c:1632`  
  Tutti gli arg_value diventano stringhe e può raccogliere più tool_call adiacenti.
- **`agent_history_has_prefix`** `ds4_agent.c:5008`  
  Non richiede un delimitatore dopo il prefisso.
- **`agent_history_is_tool_user`** `ds4_agent.c:5038`  
  Un normale messaggio che inizi con Tool: o Tool result viene classificato come output tool.
- **`agent_history_latest_compaction_summary`** `ds4_agent.c:5116`  
  Un blocco finale incompleto lascia valido il precedente blocco completo.
- **`agent_history_next_marker`** `ds4_agent.c:4975`  
  Riconosce marker ovunque nei byte, anche se compaiono nel contenuto del messaggio.
- **`agent_history_ptrs_free`** `ds4_agent.c:5045`  
  Azzera l'intera struttura dopo aver liberato gli array.
- **`agent_history_ptrs_push`** `ds4_agent.c:4951`  
  I puntatori al testo non vengono copiati né posseduti.
- **`agent_history_publish_limited`** `ds4_agent.c:5206`  
  In caso di limite mostra la coda, non l'inizio del contenuto.
- **`agent_history_render_assistant`** `ds4_agent.c:5219`  
  Il replay dei tool è solo grafico e non muta trascrizione o stato.
- **`agent_history_render_compaction_summary`** `ds4_agent.c:5152`  
  Mostra solo la coda entro 80 righe e 12000 byte.
- **`agent_history_render_text`** `ds4_agent.c:5289`  
  Limita user e tool separatamente e ripiega su eventi tool se mancano utenti umani.
- **`agent_history_skip_utf8_continuation`** `ds4_agent.c:5168`  
  Non valida UTF-8: scarta soltanto byte con prefisso 10.
- **`agent_history_start_for_turns`** `ds4_agent.c:5057`  
  Esclude i pseudo-utenti tool finché esiste almeno un turno umano.
- **`agent_history_tail_start`** `ds4_agent.c:5174`  
  I due limiti si combinano scegliendo il taglio più restrittivo.
- **`agent_history_tool_result_payload`** `ds4_agent.c:5017`  
  Se manca il tag di chiusura restituisce comunque true e usa tutto il resto come payload.
- **`agent_history_trim`** `ds4_agent.c:5003`  
  Usa isspace sulla locale corrente, non solo spazi ASCII espliciti.
- **`agent_input_buf_append`** `ds4_agent.c:449`  
  La capacità raddoppia senza controllo esplicito dell'overflow.
- **`agent_input_buf_free`** `ds4_agent.c:469`  
  Azzera anche lunghezza e capacità dopo free.
- **`agent_input_buf_take`** `ds4_agent.c:462`  
  Svuota la struttura trasferendo l'ownership; se manca il buffer alloca una stringa vuota.
- **`agent_kv_identity_sha`** `ds4_agent.c:4160`  
  I file moderni ignorano il transcript; quelli legacy ne hashano tutti i byte.
- **`agent_kv_load_path`** `ds4_agent.c:4175`  
  Payload zero ricostruisce i token dal testo ed esegue un prefill invece di caricare KV.
- **`agent_kv_path_for_sha`** `ds4_agent.c:4023`  
  Copia esattamente 40 byte del digest senza verificarne formato o terminatore.
- **`agent_kv_read_text`** `ds4_agent.c:4092`  
  Aggiunge NUL, ma eventuali NUL già presenti nel file restano nel contenuto.
- **`agent_kv_read_title_trailer`** `ds4_agent.c:4121`  
  Il titolo dichiarato viene allocato senza un limite applicativo prima della lettura.
- **`agent_kv_save_path`** `ds4_agent.c:4277`  
  Usa file temporaneo e rename, ma fflush senza fsync non garantisce persistenza dopo crash.
- **`agent_kv_session_meta_free`** `ds4_agent.c:4066`  
  Dopo free azzera anche flag, timestamp e SHA.
- **`agent_kv_write_title_trailer`** `ds4_agent.c:4105`  
  Un errore fwrite restituisce false senza compilare necessariamente err.
- **`agent_le_put64`** `ds4_agent.c:4030`  
  Il formato è sempre little-endian indipendentemente dall'host.
- **`agent_line_for_offset`** `ds4_agent.c:5988`  
  Senza righe restituisce 1; oltre la fine restituisce l'ultima riga.
- **`agent_line_spans_free`** `ds4_agent.c:5907`  
  Azzera anche lunghezza e capacità dopo free.
- **`agent_line_spans_push`** `ds4_agent.c:5912`  
  La capacità iniziale è 128 anche per una sola riga.
- **`agent_literal_match`** `ds4_agent.c:7107`  
  Una query vuota coincide con ogni riga.
- **`agent_maybe_save_before_exiting`** `ds4_agent.c:10517`  
  Rifiutare il salvataggio produce EXIT_NOW, che può saltare il teardown ordinato.
- **`agent_maybe_save_before_leaving_session`** `ds4_agent.c:10499`  
  Rispondere no consente comunque di scartare la sessione; solo un save fallito richiede conferma ulteriore.
- **`agent_memmem`** `ds4_agent.c:4963`  
  Una needle vuota coincide subito con l'inizio di hay.
- **`agent_memmem_simple`** `ds4_agent.c:6350`  
  Un pattern vuoto coincide con l'inizio del buffer.
- **`agent_mkdir_p`** `ds4_agent.c:3996`  
  EEXIST vale come successo anche se il percorso esistente non è una directory.
- **`agent_next_prefill_label`** `ds4_agent.c:9289`  
  Il contatore statico è condiviso, non atomico e riparte solo col processo.
- **`agent_noninteractive_marker`** `ds4_agent.c:10532`  
  Aggiunge sempre una newline separata, anche se msg ne contiene già una finale.
- **`agent_old_new_line_effect`** `ds4_agent.c:5996`  
  Su file vecchio vuoto restituisce false e non produce coordinate utili.
- **`agent_parse_attr`** `ds4_agent.c:1481`  
  Usa strstr senza verificare confini di attributo e non decodifica entità o escape.
- **`agent_parse_bool_default`** `ds4_agent.c:5871`  
  Ogni valore sconosciuto restituisce silenziosamente il default del chiamante.
- **`agent_parse_int_default`** `ds4_agent.c:5859`  
  Testo con suffisso non bianco usa il default invece di segnalare errore.
- **`agent_parse_timeout`** `ds4_agent.c:5849`  
  Valori invalidi tornano a 3600; quelli validi sono limitati tra 1 e 86400.
- **`agent_power_status_suffix`** `ds4_agent.c:9280`  
  Nasconde sia 100 sia valori zero o superiori a 100.
- **`agent_prefill_label`** `ds4_agent.c:9296`  
  Con stato NULL sceglie la prima etichetta e gli indici eccedenti ruotano modulo sei.
- **`agent_preflight_edit_old`** `ds4_agent.c:6987`  
  Se path manca restituisce true e rinvia ogni controllo.
- **`agent_progress_append`** `ds4_agent.c:9230`  
  Se tronca porta pos a len-1, rendendo silenziosamente inerti le append successive.
- **`agent_progress_bar`** `ds4_agent.c:9245`  
  In modalità colore mostra una cella piena anche con avanzamento zero.
- **`agent_prompt_queue_free`** `ds4_agent.c:9425`  
  Dopo i free azzera l'intera struttura, rendendo sicuro un riuso immediato.
- **`agent_prompt_queue_peek`** `ds4_agent.c:9421`  
  Restituisce un puntatore preso in prestito, invalidato da pop, free o riallocazioni logiche.
- **`agent_prompt_queue_pop`** `ds4_agent.c:9375`  
  Trasferisce ownership e lascia oltre len un puntatore duplicato ormai fuori coda.
- **`agent_prompt_queue_push`** `ds4_agent.c:9367`  
  Un testo NULL diventa una stringa vuota valida.
- **`agent_prompt_queue_push_front`** `ds4_agent.c:9383`  
  Non duplica text: il chiamante perde l'ownership appena l'inserimento riesce.
- **`agent_prompt_queue_take_all`** `ds4_agent.c:9393`  
  Con una sola voce restituisce l'originale; con più voci aggiunge intestazioni non presenti nell'input.
- **`agent_prompt_queue_take_all_echo`** `ds4_agent.c:9410`  
  Malgrado il nome take_all non rimuove né libera alcun elemento della coda.
- **`agent_prompt_yes_no`** `ds4_agent.c:10493`  
  Senza opzioni attende indefinitamente una risposta y o n valida.
- **`agent_prompt_yes_no_ex`** `ds4_agent.c:10436`  
  EOF, errore poll e risposta no restituiscono tutti false; il timeout esiste solo con auto-answer.
- **`agent_publish`** `ds4_agent.c:1229`  
  Se realloc fallisce, scarta silenziosamente l'intero frammento senza errore al worker.
- **`agent_publish_system_status`** `ds4_agent.c:4408`  
  In modalità non interattiva non pubblica nulla.
- **`agent_publishf`** `ds4_agent.c:1250`  
  Usa lo stack fino a 1023 byte; un errore di formattazione scarta silenziosamente il messaggio.
- **`agent_publishf_system_status`** `ds4_agent.c:4422`  
  Un risultato vuoto o un errore vsnprintf viene ignorato senza messaggio.
- **`agent_read_default_lines`** `ds4_agent.c:6086`  
  Un contesto ignoto o non positivo riceve il massimo di 500 righe.
- **`agent_read_file_bytes`** `ds4_agent.c:5942`  
  Rifiuta oltre 16 MiB; un file vuoto restituisce comunque una stringa allocata.
- **`agent_read_range`** `ds4_agent.c:6098`  
  whole ignora il limite; raw aggiunge comunque una nota se il risultato è troncato.
- **`agent_read_stdin_available`** `ds4_agent.c:10537`  
  Legge fino a EAGAIN; imposta eof solo su read zero e non lo azzera mai.
- **`agent_search_emit_line`** `ds4_agent.c:7141`  
  Normalizza sempre il terminatore in LF.
- **`agent_search_file`** `ds4_agent.c:7151`  
  File binari, errori di lettura e mismatch glob vengono ignorati senza messaggio.
- **`agent_search_line_matches`** `ds4_agent.c:7131`  
  In modalità regex alloca una copia NUL-terminata per ogni riga.
- **`agent_search_path`** `ds4_agent.c:7198`  
  Salta .git, link a directory ed errori; oltre profondità 24 termina in silenzio.
- **`agent_session_identity_sha`** `ds4_agent.c:4037`  
  L'hash usa solo titolo e creazione, quindi non cambia quando evolve il transcript.
- **`agent_session_list_cmp_recent`** `ds4_agent.c:5399`  
  Se last_used è zero usa created_at, poi lo SHA come spareggio.
- **`agent_session_list_free`** `ds4_agent.c:5408`  
  Libera memoria host, non il payload KV persistente.
- **`agent_session_list_push`** `ds4_agent.c:5416`  
  Acquisisce la proprietà di entry e title senza copiarli.
- **`agent_session_title_clip`** `ds4_agent.c:4899`  
  Taglia per byte e può spezzare UTF-8 prima dei tre punti ASCII.
- **`agent_session_title_from_file`** `ds4_agent.c:4910`  
  Preferisce sempre il trailer moderno; ogni errore restituisce il fallback unreadable session.
- **`agent_session_title_from_prompt`** `ds4_agent.c:4873`  
  Un prompt vuoto diventa il titolo letterale empty user prompt.
- **`agent_session_title_from_span`** `ds4_agent.c:4838`  
  Il limite conta byte e può troncare nel mezzo di un carattere UTF-8.
- **`agent_session_title_from_text`** `ds4_agent.c:4883`  
  Usa strstr: un NUL incorporato può nascondere marker validi successivi.
- **`agent_set_error`** `ds4_agent.c:1283`  
  Un messaggio NULL diventa "unknown error" e i messaggi lunghi vengono troncati.
- **`agent_set_status`** `ds4_agent.c:1272`  
  Uscire da prefill azzera i TPS; uscire da generating disattiva sempre il flag greedy.
- **`agent_sigint_handler`** `ds4_agent.c:393`  
  Ignora quale segnale sia arrivato e imposta soltanto un flag globale.
- **`agent_skip_ascii_space`** `ds4_agent.c:1497`  
  Non riconosce spazi Unicode né altri caratteri accettati da isspace.
- **`agent_slash_command_known`** `ds4_agent.c:508`  
  /help con argomenti è ignoto, mentre /power senza argomento risulta noto.
- **`agent_slash_command_with_args`** `ds4_agent.c:502`  
  Accetta anche il solo nome senza argomenti, ma rifiuta suffissi non separati da spazio.
- **`agent_span_has_nonspace`** `ds4_agent.c:6443`  
  Usa isspace della locale corrente.
- **`agent_special_token_id`** `ds4_agent.c:8050`  
  Se la stringa genera zero o più token restituisce -1 senza dettaglio.
- **`agent_split_lines`** `ds4_agent.c:5922`  
  Un buffer vuoto produce zero righe; anche un CR isolato termina la riga.
- **`agent_stream_dsml_start_match`** `ds4_agent.c:3616`  
  Per DSML accetta anche barra iniziale mancante e invoke senza blocco esterno.
- **`agent_stream_feed_dsml_byte`** `ds4_agent.c:3544`  
  Il parser riceve il byte prima della UI; gli errori mostrano anche il DSML raw rifiutato.
- **`agent_stream_finish_ignored_dsml`** `ds4_agent.c:3463`  
  Imposta stabilmente dsml_in_think e azzera il parser dopo aver mostrato l'errore.
- **`agent_stream_flush_start_tail`** `ds4_agent.c:3605`  
  I byte scaricati possono subito trasformare il parser in errore DSML malformato.
- **`agent_stream_malformed_dsml`** `ds4_agent.c:3482`  
  Dopo il primo stato ERROR ignora tutte le segnalazioni successive.
- **`agent_stream_normal_byte`** `ds4_agent.c:3711`  
  Sopprime tutti gli spazi subito dopo think e tollera aperture DSML malformate comuni.
- **`agent_stream_note_plain_dsml_byte`** `ds4_agent.c:3698`  
  Un marker letterale nel testo, anche dimostrativo, viene trattato come tool call invalida.
- **`agent_stream_note_thinking_dsml_byte`** `ds4_agent.c:3691`  
  Rileva soltanto il marker e rimanda il messaggio d'errore alla finalizzazione.
- **`agent_stream_preflight_closed_param`** `ds4_agent.c:3521`  
  Replay, DSML ignorato o un errore precedente saltano silenziosamente il controllo.
- **`agent_stream_start_dsml`** `ds4_agent.c:3587`  
  Se ignored è vero avvia il parser ma non la visualizzazione.
- **`agent_stream_text`** `ds4_agent.c:3785`  
  Al finish una call incompleta diventa interrupted; quelle nel think sono sempre scartate.
- **`agent_stream_tool_events`** `ds4_agent.c:3500`  
  Quando sparisce current.name azzera anche tutti i dettagli read raccolti.
- **`agent_stream_wants_greedy_sampling`** `ds4_agent.c:8382`  
  Un singolo '<' non basta; dal secondo byte di un marker parziale abilita greedy.
- **`agent_string_head`** `ds4_agent.c:7292`  
  Il limite in byte può troncare nel mezzo di un carattere UTF-8.
- **`agent_switch_completion_callback`** `ds4_agent.c:5530`  
  Con prefissi fino a 8 caratteri propone solo 8 cifre, altrimenti tutte e 40.
- **`agent_syntax_alias_match`** `ds4_agent.c:2342`  
  Il confronto è case-insensitive ma richiede che l'alias occupi l'intero token.
- **`agent_syntax_color`** `ds4_agent.c:2395`  
  Valori ignoti e NORMAL ricadono entrambi sul colore 252.
- **`agent_syntax_for_lang`** `ds4_agent.c:2356`  
  Lingua nulla, vuota o sconosciuta ricade silenziosamente sulla prima sintassi.
- **`agent_syntax_for_path`** `ds4_agent.c:2367`  
  Dockerfile e Makefile diventano shell; considera separatore solo / e usa l'ultima estensione.
- **`agent_syntax_keyword_len`** `ds4_agent.c:2439`  
  Un | finale non fa parte della keyword: la marca come secondaria.
- **`agent_syntax_line_comment`** `ds4_agent.c:2384`  
  Controlla al massimo tre marcatori e restituisce il primo secondo l'ordine della tabella.
- **`agent_syntax_match_keyword`** `ds4_agent.c:2445`  
  Legge p[klen] anche quando la keyword termina esattamente a line_end.
- **`agent_syntax_number_len`** `ds4_agent.c:2475`  
  Consuma avidamente lettere, underscore, punti, più e meno, quindi 123abc è un solo numero.
- **`agent_syntax_number_start`** `ds4_agent.c:2467`  
  Un punto non avvia un numero: lo continua solo se il token precedente era già numerico.
- **`agent_syntax_separator`** `ds4_agent.c:2379`  
  Backslash e virgolette non sono separatori, mentre NUL lo è.
- **`agent_tail_append`** `ds4_agent.c:7664`  
  Il taglio è per byte e può iniziare nel mezzo di UTF-8 o di una riga.
- **`agent_tail_capture_append`** `ds4_agent.c:1913`  
  Con cap zero scarta i dati senza incrementare total; input oltre cap conserva solo gli ultimi byte.
- **`agent_tail_capture_take`** `ds4_agent.c:1951`  
  Restituisce sempre un nuovo buffer, libera quello interno e azzera l'intera cattura.
- **`agent_tail_ends_with`** `ds4_agent.c:9559`  
  Opera su byte grezzi e non su caratteri o stringhe terminate.
- **`agent_tail_has_seq_prefix`** `ds4_agent.c:9565`  
  Esclude volutamente la sequenza completa limitandosi al più lungo prefisso proprio.
- **`agent_tail_matches`** `ds4_agent.c:3658`  
  Con needle_len zero restituisce sempre true.
- **`agent_test_assert`** `ds4_agent.c:6581`  
  Accumula errori invece di abortire al primo fallimento.
- **`agent_test_stream_capture`** `ds4_agent.c:6641`  
  La cattura è limitata a 16384 byte e può perdere l'inizio.
- **`agent_tokens_append_range`** `ds4_agent.c:8080`  
  Limita start solo sotto zero ed end solo oltre len; un intervallo inverso diventa un no-op.
- **`agent_tokens_equal`** `ds4_agent.c:3988`  
  Due puntatori NULL sono considerati diversi, non due sequenze vuote uguali.
- **`agent_tool_arg_value`** `ds4_agent.c:1444`  
  Con nomi duplicati vince il primo; distingue argomento assente da valore NULL, reso stringa vuota.
- **`agent_tool_call_add_arg`** `ds4_agent.c:1420`  
  La capacità parte da quattro e l'argomento conserva una copia, non i puntatori ricevuti.
- **`agent_tool_call_free`** `ds4_agent.c:1402`  
  Azzera l'intera struttura dopo la liberazione.
- **`agent_tool_calls_free`** `ds4_agent.c:1413`  
  Azzera anche len e cap dopo aver liberato ricorsivamente gli elementi.
- **`agent_tool_calls_push`** `ds4_agent.c:1434`  
  Se call non ha nome non fa nulla; altrimenti trasferisce ownership e azzera la sorgente.
- **`agent_tool_edit`** `ds4_agent.c:7051`  
  Rilegge e sovrascrive tutto il file; non preserva atomicamente modifiche concorrenti.
- **`agent_tool_google_search`** `ds4_agent.c:7342`  
  Pubblica lo stato prima di sapere se la ricerca riuscirà.
- **`agent_tool_job_id`** `ds4_agent.c:7911`  
  Valori mancanti o invalidi diventano zero.
- **`agent_tool_list`** `ds4_agent.c:6220`  
  Ordine del filesystem, massimo 300 voci e errori lstat ignorati.
- **`agent_tool_more`** `ds4_agent.c:6183`  
  Esiste un solo cursore globale per worker: una nuova lettura sostituisce il precedente.
- **`agent_tool_param_color`** `ds4_agent.c:3072`  
  Tipi ignoti ricadono silenziosamente sul bianco.
- **`agent_tool_param_kind_for`** `ds4_agent.c:3052`  
  La maggior parte delle classi dipende solo dal nome parametro, non dal tool.
- **`agent_tool_pid`** `ds4_agent.c:7915`  
  Valori mancanti, negativi o invalidi diventano zero.
- **`agent_tool_read`** `ds4_agent.c:6172`  
  whole=true rende max_lines irrilevante.
- **`agent_tool_result_fits_context`** `ds4_agent.c:6062`  
  La verifica è stretta: l'uguaglianza al contesto non è considerata sufficiente.
- **`agent_tool_result_reserve_tokens`** `ds4_agent.c:6075`  
  Con contesto non positivo conserva 1024; con contesti piccoli impone almeno 16.
- **`agent_tool_search`** `ds4_agent.c:7221`  
  Il limite conta le righe in match, non tutte le righe di contesto emesse.
- **`agent_tool_syntax_assistant_turn_uses_eos`** `ds4_agent.c:371`  
  La sintassi GLM è l'unica che non usa EOS per chiudere il turno assistente.
- **`agent_tool_syntax_for_engine`** `ds4_agent.c:366`  
  Solo i modelli GLM-DSA usano GLM; tutti gli altri ricadono silenziosamente su DSML.
- **`agent_tool_value_close_tail`** `ds4_agent.c:1579`  
  Ogni sintassi diversa da GLM viene trattata come DSML.
- **`agent_tool_visit_page`** `ds4_agent.c:7358`  
  Crea sempre un file temporaneo persistente, anche quando la pagina entra tutta nel risultato.
- **`agent_tool_viz_append`** `ds4_agent.c:3158`  
  Quando il buffer è pieno scarta silenziosamente il byte.
- **`agent_tool_viz_code_begin`** `ds4_agent.c:3259`  
  Se path arriva dopo il corpo, la sintassi è già stata scelta col percorso incompleto.
- **`agent_tool_viz_code_byte`** `ds4_agent.c:3289`  
  Aggiorna lo stato riga dal byte originale anche se il renderer lo bufferizza.
- **`agent_tool_viz_code_end`** `ds4_agent.c:3280`  
  Se il parametro non è attivo ritorna senza normalizzare altri flag di riga.
- **`agent_tool_viz_code_prefix`** `ds4_agent.c:3244`  
  Senza tipo diff lascia at_line_start invariato e non emette nulla.
- **`agent_tool_viz_diff_prefix`** `ds4_agent.c:3230`  
  Azzera sempre color prima di classificare; tipi non diff restituiscono NULL.
- **`agent_tool_viz_dump_invalid_dsml`** `ds4_agent.c:3440`  
  Se il buffer raw manca stampa il fallback letterale empty DSML.
- **`agent_tool_viz_finish`** `ds4_agent.c:3425`  
  Con status non vuoto non completa la riga riepilogativa speciale di read.
- **`agent_tool_viz_line_prefix`** `ds4_agent.c:3113`  
  Forza prima un newline se la riga precedente non era chiusa.
- **`agent_tool_viz_param_begin`** `ds4_agent.c:3297`  
  Per bash omette nome e segno uguale; per read non emette subito quasi nulla.
- **`agent_tool_viz_param_end`** `ds4_agent.c:3345`  
  In stile read non ripristina il colore terminale.
- **`agent_tool_viz_param_is_code_body`** `ds4_agent.c:3218`  
  Un parametro content di tool diversi da write o edit non viene trattato come codice.
- **`agent_tool_viz_param_raw_byte`** `ds4_agent.c:3354`  
  Il percorso è raccolto in un buffer fisso e viene troncato senza avviso.
- **`agent_tool_viz_param_value_byte`** `ds4_agent.c:3392`  
  Trattiene ogni minore iniziale finché non sa se appartiene al tag di chiusura.
- **`agent_tool_viz_prefix`** `ds4_agent.c:3120`  
  Tool non riconosciuti restituiscono NULL e saranno mostrati col nome grezzo.
- **`agent_tool_viz_puts`** `ds4_agent.c:3089`  
  Usa strlen, quindi non può visualizzare byte NUL incorporati.
- **`agent_tool_viz_read_value_byte`** `ds4_agent.c:3165`  
  Solo path viene stampato in streaming; gli altri valori restano nascosti fino al riepilogo.
- **`agent_tool_viz_render_read`** `ds4_agent.c:3179`  
  Valori mancanti diventano path unknown, start 1 e numero righe configurato.
- **`agent_tool_viz_restore_param_color`** `ds4_agent.c:3383`  
  Non ripristina nulla per read, anche con un parametro attivo.
- **`agent_tool_viz_start`** `ds4_agent.c:3093`  
  In terminale colorato live cancella l'intera riga corrente con escape ANSI.
- **`agent_tool_viz_tool`** `ds4_agent.c:3131`  
  Un nome lungo viene troncato e read usa una resa speciale senza prefisso generico.
- **`agent_tool_viz_write`** `ds4_agent.c:3084`  
  Ricalcola last_output_newline scorrendo ogni byte; con n zero conserva il valore precedente.
- **`agent_tool_write`** `ds4_agent.c:6191`  
  Apre con wb: tronca subito e non usa sostituzione atomica.
- **`agent_trace`** `ds4_agent.c:1308`  
  Con trace assente non fa nulla; con trace presente forza un flush per ogni riga.
- **`agent_trace_escaped`** `ds4_agent.c:1322`  
  Escapa solo controlli ASCII selezionati; i byte non ASCII vengono emessi grezzi.
- **`agent_trace_text`** `ds4_agent.c:1370`  
  Con text NULL e len positivo passa una stringa vuota troppo corta all'escaper.
- **`agent_trace_time`** `ds4_agent.c:1298`  
  Usa CLOCK_REALTIME, quindi i timestamp possono arretrare se cambia l'orologio di sistema.
- **`agent_trace_token`** `ds4_agent.c:1339`  
  Se text è NULL ma text_len è positivo, il fallback a stringa vuota viene letto oltre il limite.
- **`agent_trace_tokens`** `ds4_agent.c:1355`  
  Clampa start tra zero e len e converte ogni token separatamente, allocando e liberando il testo.
- **`agent_trim_span`** `ds4_agent.c:1502`  
  Modifica i due puntatori ricevuti invece di copiare o terminare la sottostringa.
- **`agent_wake_locked`** `ds4_agent.c:1219`  
  Imposta wake_pending prima della write e ne ignora l'errore, rischiando una notifica persa.
- **`agent_web_cancel`** `ds4_agent.c:4483`  
  Anche stop produce true, non solo l'interruzione utente.
- **`agent_web_confirm`** `ds4_agent.c:4442`  
  In non interattivo nega subito; altrimenti blocca il worker fino a risposta, stop o interrupt.
- **`agent_web_log`** `ds4_agent.c:4477`  
  Worker nullo o messaggio vuoto vengono ignorati silenziosamente.
- **`agent_worker_append_assistant_turn_end`** `ds4_agent.c:375`  
  Per GLM non aggiunge alcun token di chiusura.
- **`agent_worker_build_system_tokens`** `ds4_agent.c:4395`  
  GLM inserisce l'effort come messaggio system; altri modelli usano un prefisso solo per MAX.
- **`agent_worker_clear_session_identity`** `ds4_agent.c:4049`  
  Libera anche il percorso legacy pianificato per la cancellazione senza cancellare il file.
- **`agent_worker_compact`** `ds4_agent.c:8115`  
  Durante il riassunto la KV contiene istruzioni private; ogni errore deve invalidarla.
- **`agent_worker_compact_if_needed`** `ds4_agent.c:8305`  
  Se la soglia non è superata restituisce successo senza fare nulla.
- **`agent_worker_delete_session`** `ds4_agent.c:5649`  
  Usa unlink immediato senza conferma o cestino.
- **`agent_worker_effective_ctx_size`** `ds4_agent.c:381`  
  Senza sessione o con ctx non positivo usa quello configurato; altrimenti può restituire zero.
- **`agent_worker_find_session`** `ds4_agent.c:5588`  
  Sessioni di altri modelli non contano; più corrispondenze producono errore.
- **`agent_worker_free`** `ds4_agent.c:10393`  
  Può attendere indefinitamente nel join se il worker non raggiunge il controllo stop.
- **`agent_worker_has_user_session`** `ds4_agent.c:4739`  
  Misura user_activity, non la presenza di token oltre il system prompt.
- **`agent_worker_init`** `ds4_agent.c:10344`  
  Un errore intermedio ritorna senza liberare le risorse già create.
- **`agent_worker_list_sessions`** `ds4_agent.c:5431`  
  Ignora sysprompt.kv, file corrotti e sessioni di altri modelli.
- **`agent_worker_maybe_append_datetime_context`** `ds4_agent.c:1168`  
  Il timestamp rappresenta la prima chiamata, benché il testo lo descriva come inizio sessione.
- **`agent_worker_maybe_append_system_prompt_reminder`** `ds4_agent.c:1188`  
  La prima chiamata registra la baseline; il promemoria include di nuovo il sistema personalizzato.
- **`agent_worker_needs_save`** `ds4_agent.c:4746`  
  Richiede insieme attività utente e dirty; dirty da solo non basta.
- **`agent_worker_note_system_prompt_seen`** `ds4_agent.c:1164`  
  Registra la lunghezza corrente, non cerca realmente un prompt nel transcript.
- **`agent_worker_note_terminal_mode_may_have_changed`** `ds4_agent.c:7527`  
  Non ripristina il terminale: imposta soltanto un flag per il thread UI.
- **`agent_worker_reset_to_sysprompt`** `ds4_agent.c:4606`  
  Un errore nel salvataggio cache viene solo segnalato e la funzione restituisce comunque successo.
- **`agent_worker_save_session`** `ds4_agent.c:4812`  
  Se il modello è occupato fallisce subito invece di accodare il salvataggio.
- **`agent_worker_save_session_now`** `ds4_agent.c:4756`  
  Titolo e created_at fissano il nome; un salvataggio riuscito può cancellare il vecchio file legacy.
- **`agent_worker_set_more`** `ds4_agent.c:6054`  
  Un path vuoto o next_line non positivo disattiva implicitamente more.
- **`agent_worker_should_compact`** `ds4_agent.c:8039`  
  La soglia libera è minore tra 8192 e un ottavo del contesto; l'uguaglianza compatta.
- **`agent_worker_should_stop`** `ds4_agent.c:4690`  
  Ignora completamente il flag interrupt.
- **`agent_worker_show_history`** `ds4_agent.c:5376`  
  Rifiuta la richiesta con model is busy senza attendere.
- **`agent_worker_strip_session`** `ds4_agent.c:5669`  
  Al caricamento successivo forza tokenizzazione e prefill completo dal testo.
- **`agent_worker_switch_session`** `ds4_agent.c:5784`  
  Una sessione stripped scatena un prefill completo invece di ripristinare il payload.
- **`agent_worker_sync_tokens`** `ds4_agent.c:4557`  
  Riusa il prefisso solo se coincide con tutta la posizione live; altrimenti riparte da zero.
- **`agent_worker_wait_distributed_route`** `ds4_agent.c:4697`  
  Attende a polling ogni 250 ms e reagisce a stop ma non a interrupt.
- **`agent_write_file_bytes`** `ds4_agent.c:6262`  
  La scrittura non è atomica e può lasciare un file parziale.
- **`agent_write_temp_text`** `ds4_agent.c:7308`  
  Il file creato non viene rimosso da questa funzione.
- **`agent_yes_no_auto_name`** `ds4_agent.c:10425`  
  NONE e valori sconosciuti restituiscono entrambi la stringa vuota.
- **`ansiEscapeLen`** `linenoise.c:511`  
  Riconosce solo CSI; altre sequenze ANSI risultano testo visibile.
- **`answer_matches`** `ds4_eval.c:3057`  
  Per scelta multipla confronta soltanto il primo carattere.
- **`anthropic_final_response`** `ds4_server.c:7656`  
  Invia HTTP 200 anche quando finish interno è error, mappato a end_turn.
- **`anthropic_live_clear`** `ds4_server.c:8826`  
  Con server o slot nullo non fa nulla.
- **`anthropic_live_continuation_prompt`** `ds4_server.c:9764`  
  Ogni mismatch restituisce zero ed è indistinguibile da una normale cache miss.
- **`anthropic_live_has_call_id`** `ds4_server.c:8845`  
  La ricerca è globale fra slot, non limitata alla richiesta corrente.
- **`anthropic_live_matches_request`** `ds4_server.c:8872`  
  L'ordine degli ID non conta, ma i duplicati nella richiesta fanno fallire il conteggio.
- **`anthropic_live_remember`** `ds4_server.c:8806`  
  Gli ID duplicati vengono eliminati silenziosamente.
- **`anthropic_msg_is_tool_result_tail`** `ds4_server.c:3085`  
  Classifica tramite presenza degli ID, senza ispezionare il contenuto dei blocchi.
- **`anthropic_prepare_live_continuation`** `ds4_server.c:3138`  
  Ignora ruoli system finali nel rilevare la coda, ma li attraversa poi durante la raccolta.
- **`anthropic_sse_close_block_live`** `ds4_server.c:7892`  
  Per thinking emette prima una signature_delta uguale all'ID del messaggio.
- **`anthropic_sse_delta_live`** `ds4_server.c:7848`  
  Con len zero non emette eventi.
- **`anthropic_sse_finish_live`** `ds4_server.c:8339`  
  Se è uscito solo thinking senza tool aggiunge un blocco text vuoto.
- **`anthropic_sse_open_block`** `ds4_server.c:7803`  
  Se è aperto un blocco di altro tipo fallisce invece di chiuderlo.
- **`anthropic_sse_open_tool_block`** `ds4_server.c:7827`  
  Se un blocco tool è già aperto restituisce successo senza verificare ID o nome.
- **`anthropic_sse_start_live`** `ds4_server.c:7731`  
  Azzera lo stato anche se l'invio iniziale fallisce, lasciando active a false.
- **`anthropic_sse_stop_live`** `ds4_server.c:8326`  
  message_stop viene omesso se l'invio di message_delta fallisce.
- **`anthropic_sse_stream_update`** `ds4_server.c:8184`  
  Nel flush finale non avvia il parser tool incrementale: lascia i blocchi al final emitter.
- **`anthropic_sse_tool_blocks_live`** `ds4_server.c:8278`  
  Considera già emesse solo le call chiuse, non una call live ancora aperta.
- **`anthropic_sse_tool_delta_live`** `ds4_server.c:7877`  
  Con len zero non emette eventi.
- **`anthropic_stop_reason`** `ds4_server.c:7581`  
  Error e motivi sconosciuti vengono silenziosamente tradotti in end_turn.
- **`anthropic_stream_free`** `ds4_server.c:7762`  
  Libera soltanto il sottostato tool.
- **`anthropic_system_part_is_private`** `ds4_server.c:2196`  
  Il confronto è case-sensitive e riguarda solo il prefisso x-anthropic-.
- **`anthropic_tool_emit_args_fragment`** `ds4_server.c:7921`  
  È solo un wrapper del delta tool Anthropic.
- **`anthropic_tool_emit_param_prefix`** `ds4_server.c:7942`  
  Apre la virgoletta solo se l'attributo DSML string è vero.
- **`anthropic_tool_emit_string_value`** `ds4_server.c:7926`  
  Non emette nulla per frammenti vuoti.
- **`anthropic_tool_finish_param`** `ds4_server.c:8044`  
  Per valori stringa vuoti emette soltanto la virgoletta di chiusura.
- **`anthropic_tool_start_invoke`** `ds4_server.c:7988`  
  Un tag incompleto attende; un nome mancante marca errore ma restituisce successo.
- **`anthropic_tool_start_param`** `ds4_server.c:8017`  
  Mancando name o string marca errore ma lo segnala come successo.
- **`anthropic_tool_stream_fail`** `ds4_server.c:7982`  
  Restituisce true nonostante abbia registrato un errore.
- **`anthropic_tool_stream_free`** `ds4_server.c:7754`  
  Azzera solo puntatore e capacità, non gli altri campi dello stato.
- **`anthropic_tool_stream_has_id`** `ds4_server.c:7767`  
  upto viene limitato a ids_cap e gli elementi successivi non sono controllati.
- **`anthropic_tool_stream_id`** `ds4_server.c:7777`  
  Può ripetere indefinitamente la generazione finché trova un ID non usato.
- **`anthropic_tool_stream_init`** `ds4_server.c:7962`  
  Un marker non ancora completo porta subito lo stato in errore.
- **`anthropic_tool_stream_update`** `ds4_server.c:8062`  
  Gli errori sintattici disattivano il parser ma spesso ritornano true al chiamante.
- **`anthropic_validate_tool_results`** `ds4_server.c:3100`  
  Un ID non live è accettato se una chiamata assistant precedente è nella stessa richiesta.
- **`append_anthropic_block_content`** `ds4_server.c:1958`  
  Testo nullo o vuoto è considerato un successo senza modifiche.
- **`append_anthropic_content`** `ds4_server.c:7609`  
  Se c'è solo thinking aggiunge anche un blocco text vuoto.
- **`append_anthropic_system_part`** `ds4_server.c:2200`  
  Scarta in silenzio parti vuote o che iniziano con x-anthropic-.
- **`append_anthropic_thinking`** `ds4_server.c:7601`  
  I valori nulli diventano stringhe vuote.
- **`append_anthropic_tool_use`** `ds4_server.c:7587`  
  Ignora gli ordini schema, quindi non ripristina nomi o namespace di wire.
- **`append_anthropic_usage_json`** `ds4_server.c:7642`  
  input_tokens esclude i token cache, diversamente dal totale prompt interno.
- **`append_cors_headers`** `ds4_server.c:5539`  
  Abilita origine, metodi e intestazioni con wildcard
- **`append_dsml_arg`** `ds4_server.c:2495`  
  Il flag string deriva dal token JSON originario, non dallo schema dello strumento.
- **`append_dsml_arguments_from_json`** `ds4_server.c:2514`  
  Un JSON non oggetto restituisce false senza emettere un fallback proprio.
- **`append_dsml_attr_escaped`** `ds4_server.c:2417`  
  Un puntatore nullo viene trattato come stringa vuota.
- **`append_dsml_json_literal`** `ds4_server.c:2482`  
  Usa la sequenza JSON \u003c, diversa dall'escape testuale &lt;.
- **`append_dsml_parameter_text`** `ds4_server.c:2427`  
  Non fa escaping XML generale: sostituisce solo il primo carattere del tag di chiusura esatto.
- **`append_dsml_tool_calls_text`** `ds4_server.c:2576`  
  Se raw_tool_text è presente prevale interamente sulle chiamate strutturate.
- **`append_glm_arg`** `ds4_server.c:2506`  
  Le coppie consecutive non hanno separatore esterno oltre ai propri tag.
- **`append_glm_arg_key_text`** `ds4_server.c:2452`  
  Protegge soltanto la chiusura esatta di arg_key.
- **`append_glm_arg_value_text`** `ds4_server.c:2456`  
  Protegge soltanto la chiusura esatta di arg_value.
- **`append_glm_arguments_from_json`** `ds4_server.c:2533`  
  Un JSON non oggetto restituisce false senza emettere un fallback proprio.
- **`append_glm_assistant_message_prefix`** `ds4_server.c:2738`  
  Se content inizia già con un tag think, il reasoning separato non viene aggiunto.
- **`append_glm_tag_body_text`** `ds4_server.c:2440`  
  Non fa escaping XML generale e protegge solo la chiusura esatta indicata.
- **`append_glm_tool_calls_text`** `ds4_server.c:2598`  
  Se raw_tool_text è presente prevale; argomenti invalidi diventano un solo campo arguments.
- **`append_glm_tool_response_text`** `ds4_server.c:2460`  
  Protegge soltanto la chiusura esatta di tool_response.
- **`append_glm_tools_prompt_text`** `ds4_server.c:2314`  
  Con schemi nulli o vuoti non aggiunge neppure le istruzioni.
- **`append_json_object_or_empty`** `ds4_server.c:2559`  
  Qualsiasi input non analizzabile viene sostituito silenziosamente con {}.
- **`append_json_object_string`** `ds4_server.c:5490`  
  Un oggetto non analizzabile viene sostituito silenziosamente con {}
- **`append_model_json`** `ds4_server.c:12594`  
  Usa sempre nome, contesto e default token del server corrente.
- **`append_model_json_values`** `ds4_server.c:12558`  
  Il timestamp created è fisso e max_completion viene limitato al contesto.
- **`append_openai_usage_json`** `ds4_server.c:5699`  
  cache_write_tokens è limitato al prompt rimasto dopo i token cached
- **`append_pseudo_layer_tags`** `ds4_layer_pack.c:49`  
  Ignora in silenzio l'output head se n_layers+1 non rientra in n_entries.
- **`append_raw_json_line`** `ds4_server.c:1443`  
  JSON nullo o vuoto viene ignorato senza segnalazione.
- **`append_rendered_suffix_to_live_session`** `ds4_server.c:10573`  
  Un suffisso nullo o vuoto è considerato successo senza fare nulla.
- **`append_responses_namespace_tool_schemas`** `ds4_server.c:1741`  
  Se non appende funzioni restituisce false e il chiamante può conservare l'oggetto grezzo.
- **`append_responses_usage_json`** `ds4_server.c:7199`  
  Clampa i token cache e riporta reasoning_tokens sempre a zero.
- **`append_tool_call_deltas_json`** `ds4_server.c:5517`  
  Ignora orders e genera ID prevedibili quando tc non ne ha uno
- **`append_tool_calls_json`** `ds4_server.c:5497`  
  Ignora completamente gli ordini di schema ricevuti
- **`append_tool_calls_text_for_syntax`** `ds4_server.c:2621`  
  Ogni sintassi diversa da GLM ricade implicitamente su DSML.
- **`append_tool_heavy_messages`** `ds4_server.c:16488`  
  Genera sempre 24 turni e 98 messaggi totali, con tre call per turno.
- **`append_tool_heavy_schema`** `ds4_server.c:16460`  
  Per idx diverso da zero antepone una virgola; non produce un array completo.
- **`append_tool_result_text`** `ds4_server.c:2464`  
  Conserva letteralmente minore, maggiore e ampersand salvo il sentinel di chiusura.
- **`append_tools_prompt_text`** `ds4_server.c:2287`  
  Con schemi nulli o vuoti non aggiunge neppure le istruzioni.
- **`apply_anthropic_stream_tool_ids`** `ds4_server.c:9019`  
  Copia solo fino a ids_cap e non sovrascrive ID già presenti.
- **`apply_openai_stream_tool_ids`** `ds4_server.c:9009`  
  Copia solo fino a ids_cap e non sovrascrive ID già presenti.
- **`argmax_f32`** `ds4.c:15181`  
  Con n zero restituisce comunque 0; a parità mantiene il primo indice.
- **`argmax_kernel`** `rocm/ds4_rocm_indexer.cuh:254`  
  I pareggi scelgono l'indice minore e i NaN vengono ignorati.
- **`ascii_alpha`** `ds4.c:36112`  
  Le lettere non ASCII non corrispondono
- **`ascii_digit`** `ds4.c:36116`  
  Le cifre Unicode non corrispondono
- **`ascii_newline`** `ds4.c:36125`  
  CR e LF sono riconosciuti separatamente
- **`ascii_space`** `ds4.c:36120`  
  Include sei whitespace C, non soltanto lo spazio
- **`ascii_tolower_cp`** `ds4.c:36308`  
  Non applica case folding Unicode
- **`assign_tool_call_ids`** `ds4_server.c:8996`  
  Conserva senza validazione ogni ID non vuoto già presente.
- **`atomic_max`** `src/cuda/vram_expert_cache.cpp:65`  
  L'ordine relaxed rende atomico il massimo, non uno snapshot coerente circostante.
- **`attention_block_max_oldhip_w32`** `rocm/ds4_rocm_attention.cuh:414`  
  Restituisce a ogni thread lo stesso risultato via shared memory.
- **`attention_block_sum_oldhip_w32`** `rocm/ds4_rocm_attention.cuh:398`  
  Restituisce a ogni thread lo stesso risultato via shared memory.
- **`attention_compact_topk_stable`** `ds4_cuda.cu:11912`  
  Esamina al massimo 512 posizioni e conserva anche eventuali duplicati
- **`attention_decode_batch_launch`** `rocm/ds4_rocm_attention_launch.cuh:214`  
  Con più token e cache staged disabilita e ripristina la migrazione KV
- **`attention_decode_global_softmax_kernel`** `ds4_cuda.cu:11145`  
  Gli score riscritti sono esponenziali non normalizzati; il sink resta solo nel denominatore
- **`attention_decode_indexed_mixed_one_fast_oldhip_kernel`** `rocm/ds4_rocm_attention.cuh:522`  
  Indici Top-K duplicati vengono pesati più volte, senza deduplica.
- **`attention_decode_mixed_heads8_online_kernel`** `rocm/ds4_rocm_attention.cuh:1315`  
  Con ratio 0 include i compressi soltanto quando n_tokens è esattamente 1
- **`attention_decode_mixed_kernel`** `rocm/ds4_rocm_attention.cuh:617`  
  Con ratio=0 include tutte le righe compresse e limita le righe raw a 256.
- **`attention_decode_mixed_one_fast_oldhip_kernel`** `rocm/ds4_rocm_attention.cuh:448`  
  La shared cresce col contesto e può far fallire il launch.
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
- **`attention_dot_f32_vec4_oldhip`** `rocm/ds4_rocm_attention.cuh:430`  
  Gestisce una coda scalare anche se il nome suggerisce soli vec4.
- **`attention_indexed_mixed_decode_rows_kernel`** `ds4_cuda.cu:12104`  
  I descrittori non indexed vengono saltati lasciando intatta l'uscita
- **`attention_indexed_mixed_heads8_online_kernel`** `rocm/ds4_rocm_attention.cuh:1028`  
  Non valida gli indici top-k: valori negativi o fuori range indirizzano KV errata
- **`attention_indexed_mixed_heads8_rb4_kernel`** `ds4_cuda.cu:12275`  
  La compattazione seriale conserva duplicati top-k, che ricevono massa più volte
- **`attention_indexed_mixed_kernel`** `rocm/ds4_rocm_attention.cuh:871`  
  Se esiste un compresso cambia l'ordine di riduzione anche degli score raw
- **`attention_indexed_mixed_scalar_kernel`** `rocm/ds4_rocm_attention.cuh:785`  
  Nessun launcher lo invoca: è codice morto nel backend corrente.
- **`attention_mixed_cublas_tmp_bytes`** `rocm/ds4_rocm_attention_launch.cuh:492`  
  Allinea a 256 byte solo gli offset intermedi, non il totale finale
- **`attention_noncausal_raw_batch_heads_kernel`** `ds4_cuda.cu:17438`  
  Il sink entra nel denominatore ma non aggiunge alcun vettore value
- **`attention_pack_group_heads_f16_kernel`** `rocm/ds4_rocm_attention.cuh:343`  
  La conversione FP16 è lossy e avviene solo nel percorso cuBLAS.
- **`attention_prefill_mixed_cublas_tiled`** `rocm/ds4_rocm_attention_launch.cuh:507`  
  Con tile_tokens=1 lo scratch può superare comunque il tetto di 4 GiB
- **`attention_prefill_mixed_kernel`** `rocm/ds4_rocm_attention.cuh:67`  
  Il sink assorbe probabilità senza aggiungere un vettore valore all'output.
- **`attention_prefill_mixed_launch`** `rocm/ds4_rocm_attention_launch.cuh:619`  
  Il percorso cuBLAS riserva scratch quadratico nel numero di token e chiavi
- **`attention_prefill_mixed_softmax_kernel`** `rocm/ds4_rocm_attention.cuh:192`  
  Un valore di maschera <= -1e20 esclude silenziosamente la chiave compressa.
- **`attention_prefill_mixed_softmax_tile_kernel`** `rocm/ds4_rocm_attention.cuh:250`  
  ratio=0 lascia il tile invariato con un return silenzioso.
- **`attention_prefill_pack_mixed_kv_kernel`** `rocm/ds4_rocm_attention.cuh:311`  
  Le righe raw precedono sempre tutte le righe compresse.
- **`attention_prefill_raw_kernel`** `rocm/ds4_rocm_attention.cuh:11`  
  Il sink entra nel denominatore ma non contribuisce alcun vettore valore.
- **`attention_prefill_raw_softmax_kernel`** `rocm/ds4_rocm_attention.cuh:147`  
  Sovrascrive gli score e include nel denominatore una massa sink non presente nelle righe.
- **`attention_prefill_unpack_heads_kernel`** `rocm/ds4_rocm_attention.cuh:327`  
  Il kernel non copia soltanto: scambia gli assi testa e token.
- **`attention_prefix_comp_allowed`** `ds4.c:13100`  
  Bitset assente o mask del token a zero abilita tutte le righe.
- **`attention_staged_ring_heads8_online_kernel`** `ds4_cuda.cu:12909`  
  Prima dell'ultimo chunk heads contiene un numeratore riscalato ma non normalizzato
- **`attention_static_mixed_heads8_online_kernel`** `rocm/ds4_rocm_attention.cuh:1191`  
  Con ratio uguale a 0 ignora completamente comp_kv
- **`attention_unpack_group_low_kernel`** `rocm/ds4_rocm_attention.cuh:359`  
  Scambia implicitamente gli assi gruppo e token.
- **`attention_warp_max_oldhip_w32`** `rocm/ds4_rocm_attention.cuh:387`  
  Il nome old-HIP cela anche un ramo shuffle CUDA.
- **`attention_warp_sum_oldhip_w32`** `rocm/ds4_rocm_attention.cuh:376`  
  Il nome old-HIP cela anche un ramo shuffle CUDA.
- **`axpy_f32`** `ds4.c:10660`  
  La variante NEON gira solo su ARM; altrove usa il ciclo scalare.
- **`begin_transaction`** `src/cuda/dynamic_arena.cu:667`  
  Una sola vittima con reader attivi fa fallire l'intera transazione
- **`bench_sleep_ms`** `ds4_bench.c:37`  
  Su POSIX non riprende nanosleep se viene interrotta da un segnale.
- **`bench_snapshot_max_bytes`** `ds4_bench.c:88`  
  strtoull accetta segni e spazi iniziali e gli overflow non sono controllati.
- **`bind_layer_locked`** `src/cuda/dynamic_arena.cu:567`  
  Assume UP grande quanto GATE perché non esiste una misura UP separata
- **`binding_valid`** `src/cuda/dynamic_arena.cu:378`  
  Non controlla il checksum del contenuto
- **`bitrev5`** `ds4_cuda.cu:8543`  
  I bit oltre i cinque meno significativi vengono scartati.
- **`bool_requested`** `src/cuda/prefill_observer.cu:71`  
  Valori diversi da 0 e 1 disabilitano con warning; non accetta true.
- **`bounded_strstr`** `ds4_eval.c:3111`  
  Il range può contenere NUL, ma needle deve essere una stringa C.
- **`bpe_emit_piece`** `ds4.c:36039`  
  I simboli assenti vengono ripiegati a byte e i byte ancora assenti sono ignorati
- **`bpe_rank`** `ds4.c:36022`  
  La chiave di ricerca inserisce uno spazio tra i simboli
- **`bpe_tokenize_text`** `ds4.c:36450`  
  La famiglia GLM seleziona un pretokenizer completamente diverso
- **`bpe_tokenize_text_glm4`** `ds4.c:36315`  
  Le sequenze numeriche vengono spezzate ogni tre cifre
- **`bpe_tokenize_tool_response_text`** `ds4.c:36822`  
  Escapa soltanto la chiusura esatta tool_response
- **`bpe_tokenize_tool_result_text`** `ds4.c:36818`  
  Escapa soltanto la chiusura esatta tool_result
- **`bpe_tokenize_wrapped_payload_text`** `ds4.c:36796`  
  Escapa solo la sentinella di chiusura esatta; gli altri caratteri HTML restano letterali
- **`budget_for_expert_size`** `src/cuda/dynamic_arena.cu:1146`  
  Qualunque input invalido azzera anche il conteggio configurato globale
- **`buf_append`** `ds4_server.c:360`  
  Anche dati binari vengono seguiti da NUL senza cambiare la lunghezza logica
- **`buf_appendf`** `ds4_eval.c:1372`  
  Un errore di formattazione viene ignorato senza segnalazione.
- **`buf_free`** `ds4_server.c:396`  
  Azzera anche lunghezza e capacita
- **`buf_printf`** `ds4_server.c:375`  
  Un errore di vsnprintf termina l'intero processo
- **`buf_putc`** `ds4_server.c:367`  
  Puo riallocare il buffer tramite buf_append
- **`buf_puts`** `ds4_server.c:371`  
  Non puo accodare byte dopo un NUL interno
- **`buf_reserve`** `ds4_server.c:344`  
  La prima crescita riserva almeno 256 byte e gli overflow terminano il processo
- **`buf_take`** `ds4_server.c:389`  
  Un buffer mai allocato restituisce comunque una nuova stringa vuota
- **`build_footer_text`** `ds4_agent.c:9437`  
  Forza almeno 40 colonne e tronca per byte, potendo spezzare UTF-8 nell'anteprima.
- **`build_invalid_dsml_tool_error_suffix`** `ds4_server.c:10389`  
  Include nel recupero l'intero system prompt estratto come promemoria.
- **`build_invalid_glm_tool_error_suffix`** `ds4_server.c:10421`  
  Riapre sempre think: in modalità disattiva emette comunque <think></think>.
- **`build_invalid_tool_call_error_suffix`** `ds4_server.c:10450`  
  Ogni sintassi non GLM ricade silenziosamente sul formato DSML.
- **`build_prompt`** `ds4_cli.c:524`  
  Il riconoscimento euristico può evitare o duplicare il template chat.
- **`build_prompt_from_exact_prefix_and_text_suffix`** `ds4_server.c:9435`  
  Ritokenizza il suffisso testuale invece di copiare i token del prompt completo.
- **`build_prompt_text`** `ds4_agent.c:9240`  
  Ignora completamente lo stato ricevuto.
- **`build_question_prompt`** `ds4_eval.c:2430`  
  Il chiamante deve liberare la stringa restituita.
- **`build_responses_visible_assistant_suffix`** `ds4_server.c:10770`  
  Include reasoning solo nei turni con tool call e summary richiesto.
- **`build_source_parts`** `src/cuda/dynamic_arena.cu:876`  
  Ordina prima per tipo gate/up/down, non solo per offset sorgente
- **`build_status_text`** `ds4_agent.c:9311`  
  Un totale prefill non positivo viene mostrato come 1; STOPPED viene etichettato interrupted.
- **`build_tool_checkpoint_suffix`** `ds4_server.c:10752`  
  La sintassi GLM omette il token EOS aggiunto alle altre sintassi.
- **`build_toolless_thinking_visible_text`** `ds4_server.c:10813`  
  Se il prompt non finisce esattamente con <think> restituisce NULL senza fallback.
- **`byte_encode`** `ds4.c:35988`  
  Restituisce memoria host che il chiamante deve liberare
- **`byte_prefix_match`** `ds4_server.c:9424`  
  Confronta byte e lunghezze, non testo Unicode normalizzato.
- **`bytes_is_partial_prefix`** `ds4_eval.c:2161`  
  Con n=0 restituisce true per qualunque prefisso non vuoto.
- **`calculate_capacity`** `src/cuda/vram_expert_cache.cpp:329`  
  Riserva sempre uno slot fisico non pubblicabile oltre agli slot utilizzabili.
- **`canonicalize_tool_checkpoint`** `ds4_server.c:10855`  
  Se riscrittura o rebuild falliscono, registra l'errore ma lascia proseguire la risposta.
- **`chat_history_uses_tool_context`** `ds4_server.c:2640`  
  La sola presenza di schemi non vuoti basta, anche senza chiamate nella cronologia.
- **`chat_msg_add_tool_call_id`** `ds4_server.c:913`  
  tool_call_id resta il primo ID anche quando la lista ne contiene altri
- **`chat_msg_collect_tool_call_ids`** `ds4_server.c:2971`  
  Non raccoglie gli ID delle chiamate in m->calls, nonostante il nome generico.
- **`chat_msg_free`** `ds4_server.c:927`  
  Libera sia tool_call_id sia ogni copia nella lista tool_call_ids
- **`chat_msg_has_call_id`** `ds4_server.c:2963`  
  Ignora gli ID dei risultati memorizzati in tool_call_id e tool_call_ids.
- **`chat_msgs_push`** `ds4_server.c:944`  
  La copia e superficiale e trasferisce di fatto la proprieta dei campi
- **`chat_push_bos_sequence`** `ds4.c:36631`  
  Per GLM può aggiungere anche SOP dopo BOS
- **`chat_push_think_prefix`** `ds4.c:36646`  
  GLM inserisce anche il marcatore system; non GLM gestisce solo MAX
- **`chat_think_tool_recovery`** `ds4_server.c:10317`  
  Con budget insufficiente rinuncia in silenzio e non ritenta quel marker.
- **`clamp_usage_tokens`** `ds4_server.c:5693`  
  Un massimo negativo disabilita il limite superiore
- **`clear_locked`** `src/cuda/prefill_observer.cu:268`  
  Ignora errori di synchronize e destroy, poi azzera comunque tutto lo stato.
- **`cli_apply_model_sampling_defaults`** `ds4_cli.c:535`  
  Non tocca modelli non GLM-DSA e preserva le opzioni esplicite.
- **`cli_dist_busy_set`** `ds4_cli.c:164`  
  Sui worker non fa nulla; busy=false riabilita l'avviso SIGINT.
- **`cli_distributed_coordinator`** `ds4_cli.c:160`  
  Un cfg nullo equivale a non coordinatore.
- **`cli_effective_think_mode`** `ds4_cli.c:308`  
  Think Max può diventare High quando il contesto è insufficiente.
- **`cli_env_flag_enabled`** `ds4_cli.c:46`  
  Qualsiasi valore non vuoto diverso da "0" abilita il flag, anche "false".
- **`cli_greedy_argmax_requested`** `ds4_cli.c:71`  
  Il default di DS4_CUDA_GREEDY_TOP1 è attivo, ma la speculazione lo disattiva.
- **`cli_greedy_fast_attention_requested`** `ds4_cli.c:57`  
  Basta una variante abilitata; i rispettivi flag NO hanno precedenza.
- **`cli_interrupt_clear`** `ds4_cli.c:155`  
  Cancella anche il latch dell'avviso distribuito.
- **`cli_prefill_progress_cb`** `ds4_cli.c:340`  
  Senza colore ignora gli eventi display ma stampa una riga per ogni chunk.
- **`cli_sigint_handler`** `ds4_cli.c:139`  
  Usa write nel signal handler; l'avviso appare solo durante attività distribuita.
- **`cli_sleep_ms`** `ds4_cli.c:124`  
  Su POSIX non riprende nanosleep dopo EINTR; quel ramo non gira su Windows.
- **`cli_splitkv_spec_requested`** `ds4_cli.c:52`  
  DS4_CUDA_NO_SPLITKV_SPEC ha precedenza assoluta sul flag positivo.
- **`cli_think_max_downgraded`** `ds4_cli.c:312`  
  Segnala solo il caso richiesto Max; ignora altri cambi di modalità.
- **`cli_wait_distributed_route`** `ds4_cli.c:170`  
  Può attendere senza timeout, stampando lo stato ogni cinque secondi.
- **`cli_warn_think_max_downgraded`** `ds4_cli.c:317`  
  Non modifica la configurazione; descrive un downgrade calcolato altrove.
- **`client_done`** `ds4_server.c:12631`  
  Se il contatore è già zero non segnala lo sbilanciamento.
- **`client_main`** `ds4_server.c:12640`  
  L'endpoint shutdown disarmato risponde 404 ed è limitato al loopback IPv4.
- **`closedir`** `src/win32/win_dirent.h:68`  
  Ignora l'esito di FindClose e restituisce sempre 0 per un puntatore non nullo
- **`collect_tool_call_ids`** `ds4_server.c:9133`  
  Unifica nello stesso insieme ID di risultati, richieste e chiamate annidate.
- **`completeLine`** `linenoise.c:875`  
  snprintf può impostare len oltre buflen quando il completamento è troppo lungo.
- **`compressor_decode_one`** `ds4.c:12776`  
  Negli altri token aggiorna lo stato ma ritorna false senza produrre una riga.
- **`compressor_decode_one_decode_scratch`** `ds4.c:12873`  
  Negli altri token aggiorna lo stato e ritorna false; non alloca temporanei.
- **`compressor_finish_prefill_state_cpu`** `ds4.c:12676`  
  Con buffer nullo o dimensioni zero ritorna senza segnalare errore.
- **`compressor_pool_decode_state`** `ds4.c:12721`  
  Con rapporto 4 fonde due corsie; se tutti gli score sono invalidi produce zero.
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
- **`compsec_answer_matches`** `ds4_eval.c:3024`  
  Accetta qualunque sottoinsieme non vuoto dell'atteso, non richiede uguaglianza esatta.
- **`config_expect_bool`** `ds4.c:5649`  
  Una differenza termina immediatamente il processo.
- **`config_expect_f32`** `ds4.c:5641`  
  La tolleranza è almeno 1e-6 assoluta; NaN fallisce sempre.
- **`config_expect_u32`** `ds4.c:5627`  
  Una differenza termina immediatamente il processo.
- **`config_expect_u64`** `ds4.c:5634`  
  Una differenza termina immediatamente il processo.
- **`config_validate_deepseek4_model`** `ds4.c:5662`  
  I campi RoPE compatibili assenti ereditano il valore atteso e passano.
- **`config_validate_fixed_shape`** `ds4.c:5656`  
  Una differenza termina subito il processo.
- **`config_validate_glm_dsa_model`** `ds4.c:5774`  
  Azzera globalmente i rapporti di compressione prima di finire la validazione.
- **`config_validate_model`** `ds4.c:5842`  
  Architettura assente o diversa da glm-dsa ricade silenziosamente su DeepSeek4.
- **`configure_client_socket`** `ds4_server.c:12798`  
  Ignora tutti gli errori di setsockopt.
- **`configured_count`** `src/cuda/dynamic_arena.cu:1162`  
  Dopo l'allocazione ignora il valore stimato e usa la dimensione reale dell'arena
- **`content_length`** `ds4_server.c:12486`  
  strtol senza end pointer accetta suffissi non numerici e assenza vale zero.
- **`context_length_error_param`** `ds4_server.c:5582`  
  Una richiesta NULL viene classificata come prompt
- **`continue_after_invalid_dsml`** `ds4_server.c:10597`  
  L'errore diventa testo visibile al modello e consuma contesto.
- **`copy_span`** `ds4_eval.c:3122`  
  Rimuove solo CR e LF finali e tronca senza segnalare.
- **`copy_worker`** `src/cuda/dynamic_arena.cu:834`  
  Non esegue controlli di bounds prima di memcpy
- **`cpr_candidate_state`** `ds4_agent.c:9534`  
  Accetta numeri di riga o colonna zero e non controlla overflow durante la sola classificazione.
- **`cpu_decode_quantize_q8_0`** `ds4.c:7930`  
  Il controllo usa in_dim, mentre il kernel scrive fino al blocco da 32 arrotondato.
- **`cpu_decode_scratch_free`** `ds4.c:12540`  
  Dopo i free azzera l'intera struttura; un puntatore scratch nullo è ignorato.
- **`cpu_decode_scratch_init`** `ds4.c:12456`  
  Un ctx_size pari a zero diventa 1; la memoria è heap host residente per la generazione.
- **`cpu_directional_steering_enabled`** `ds4.c:35896`  
  Una scala NaN abilita lo steering
- **`cpu_directional_steering_project_rows`** `ds4.c:35902`  
  La proiezione è corretta come tale solo con direzioni normalizzate
- **`cpu_load_directional_steering`** `ds4.c:35924`  
  Con entrambe le scale a zero ignora anche un file mancante
- **`cublas_ok`** `rocm/ds4_rocm_runtime.cuh:5786`  
  Restituisce solo 0 o 1 e stampa lo status numerico, senza tradurlo.
- **`cuda_ape_type_supported`** `rocm/ds4_rocm_compressor.cuh:181`  
  Accetta esclusivamente i codici 0, 1 e 8
- **`cuda_attention_score_buffer_fits`** `rocm/ds4_rocm_runtime.cuh:588`  
  La sottrazione unsigned va in underflow se le due capacità vengono definite al contrario.
- **`cuda_compressor_shape_supported`** `rocm/ds4_rocm_compressor.cuh:185`  
  Solo ratio 4 raddoppia la larghezza considerata nel controllo overflow
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
- **`cuda_env_present`** `rocm/ds4_rocm_runtime.cuh:4730`  
  Una stringa qualsiasi diversa da vuota e 0 vale vero, inclusa false.
- **`cuda_hc_flat_token_count`** `rocm/ds4_rocm_hc_output_launch.cuh:45`  
  Deduce i token dalla capacità totale di out, non da un conteggio attivo
- **`cuda_hc_hc_token_count`** `rocm/ds4_rocm_hc_output_launch.cuh:54`  
  Deduce i token dalla capacità totale di out_hc, non da un conteggio attivo
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
- **`cuda_launch_grouped_q8_a_sharedx`** `rocm/ds4_rocm_matmul.cuh:77`  
  Un block_tile diverso da 8 o 32 seleziona silenziosamente 16
- **`cuda_launch_grouped_q8_a_sharedx_bt`** `rocm/ds4_rocm_matmul.cuh:50`  
  Qualunque tile diverso da 2, 4, 8 o 16 seleziona la specializzazione 32
- **`cuda_launch_grouped_q8_a_sharedx_strided`** `rocm/ds4_rocm_matmul.cuh:146`  
  Un block_tile diverso da 8 o 32 seleziona silenziosamente 16
- **`cuda_launch_grouped_q8_a_sharedx_strided_bt`** `rocm/ds4_rocm_matmul.cuh:102`  
  Qualunque tile diverso da 2, 4, 8 o 16 seleziona la specializzazione 32
- **`cuda_launch_q8_batch_sharedx`** `rocm/ds4_rocm_matmul.cuh:27`  
  Un block_tile diverso da 8 o 32 seleziona silenziosamente 16
- **`cuda_launch_q8_batch_sharedx_bt`** `rocm/ds4_rocm_matmul.cuh:1`  
  Qualunque tile diverso da 2, 4, 8 o 16 seleziona la specializzazione 32
- **`cuda_managed_kv_reserve_bytes`** `rocm/ds4_rocm_runtime.cuh:5924`  
  La riserva minima resta 8 GiB anche quando un quarto della VRAM e molto inferiore.
- **`cuda_matmul_q8_0_hc_expand_tensor_labeled`** `rocm/ds4_rocm_matmul.cuh:641`  
  I tre tensori di ownership sono obbligatori tutti insieme oppure tutti assenti
- **`cuda_matmul_q8_0_tensor_f16_gemm`** `rocm/ds4_rocm_matmul.cuh:183`  
  Un errore cuBLAS disabilita la cache F16 e lascia al chiamante l'eventuale fallback
- **`cuda_matmul_q8_0_tensor_f16_gemm_out_half`** `rocm/ds4_rocm_matmul.cuh:240`  
  Un errore cuBLAS disabilita la cache F16 e restituisce 0 senza fallback nativo
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
- **`cuda_model_image_bytes`** `rocm/ds4_rocm_runtime.cuh:629`  
  La somma uint64 non controlla overflow.
- **`cuda_model_image_find`** `rocm/ds4_rocm_runtime.cuh:592`  
  Restituisce -1 sia per base nulla sia per immagine assente.
- **`cuda_model_image_owned`** `rocm/ds4_rocm_runtime.cuh:625`  
  Il possesso dipende solo dall'identità della base host.
- **`cuda_model_image_ptr`** `rocm/ds4_rocm_runtime.cuh:600`  
  Con immagini sovrapposte restituisce la prima inserita che contiene l'offset.
- **`cuda_model_image_range_ptr`** `rocm/ds4_rocm_runtime.cuh:610`  
  Per zero byte delega alla ricerca puntuale, anche esattamente a fine immagine fallisce.
- **`cuda_model_image_release_all`** `rocm/ds4_rocm_runtime.cuh:635`  
  Non azzera gli altri globali che possono ancora descrivere il modello.
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
- **`cuda_model_range_copy_uncached`** `rocm/ds4_rocm_runtime.cuh:4562`  
  Ogni range viene conservato nella cache globale nonostante il nome uncached.
- **`cuda_model_range_fits`** `rocm/ds4_rocm_runtime.cuh:490`  
  Evita overflow usando una sottrazione dopo il controllo dell'offset.
- **`cuda_model_range_is_cached`** `rocm/ds4_rocm_runtime.cuh:4690`  
  Un modello globalmente owned o registered fa restituire vero senza verificare mappa e range.
- **`cuda_model_range_ptr`** `rocm/ds4_rocm_runtime.cuh:4589`  
  Se mapping host e cache FD falliscono, alloca e copia silenziosamente il range in VRAM.
- **`cuda_model_range_ptr_from_fd`** `rocm/ds4_rocm_runtime.cuh:5569`  
  A budget esaurito cade sul puntatore host anche con DS4_CUDA_STRICT_WEIGHT_CACHE presente.
- **`cuda_model_range_release_all`** `rocm/ds4_rocm_runtime.cuh:5779`  
  Le slice arena_allocated si liberano solo insieme al blocco arena condiviso.
- **`cuda_model_range_release_ranges_only`** `rocm/ds4_rocm_runtime.cuh:5761`  
  I range arena non sono liberati singolarmente; viene liberata ogni arena intera.
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
- **`cuda_prefill_warmup_tokens`** `rocm/ds4_rocm_runtime.cuh:5128`  
  Nel runtime ROCm/CUDA legge la variabile chiamata DS4_METAL_PREFILL_CHUNK.
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
- **`cuda_q8_f16_transpose_ptr`** `rocm/ds4_rocm_runtime.cuh:5073`  
  Mantiene una seconda cache separata, quindi lo stesso peso può occupare VRAM due volte.
- **`cuda_q8_f16_warmup_attention_output_a_gemm`** `rocm/ds4_rocm_runtime.cuh:5139`  
  Imposta warmed prima di allocazione e GEMM: un fallimento impedisce ogni retry.
- **`cuda_q8_f16_warmup_attention_output_b_gemm`** `rocm/ds4_rocm_runtime.cuh:5187`  
  Imposta warmed prima di allocazione e GEMM: un fallimento impedisce ogni retry.
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
- **`cuda_rope_tail_stride_tensor`** `rocm/ds4_rocm_norm_rope.cuh:603`  
  n_rot uguale a zero supera i controlli ma produce un lancio con griglia nulla.
- **`cuda_rows_per_block_env_or_default`** `rocm/ds4_rocm_runtime.cuh:4739`  
  Accetta suffissi dopo il numero perché non richiede che *end sia nullo.
- **`cuda_rows_per_block_or_default`** `rocm/ds4_rocm_runtime.cuh:4735`  
  Accetta solo potenze di due da 1 a 32, altrimenti usa il default senza errore.
- **`cuda_runtime_config`** `rocm/ds4_rocm_runtime.cuh:4767`  
  I valori sono congelati; un graph dump può cambiare i kernel se non è noninvasivo.
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
- **`cuda_shared_gate_up_async_cleanup`** `rocm/ds4_rocm_shared_expert.cuh:238`  
  Ignora gli errori di attesa, cudaFree e distruzione delle risorse.
- **`cuda_shared_gate_up_async_tmp_alloc`** `rocm/ds4_rocm_shared_expert.cuh:216`  
  Se è già capiente lo restituisce senza attesa; resta allocato fino al cleanup.
- **`cuda_shared_gate_up_async_wait_internal`** `rocm/ds4_rocm_shared_expert.cuh:204`  
  Azzera pending anche quando la sincronizzazione fallisce.
- **`cuda_splitkv_decode_requested`** `ds4_cuda.cu:2874`  
  NO_SPLITKV prevale sia sul fast mode sia su SPLITKV_DECODE.
- **`cuda_stream_batch_selected_abort_pending`** `rocm/ds4_rocm_runtime.cuh:2434`  
  Abort è bloccante: aspetta comunque tutte le letture prima di azzerare lo stato.
- **`cuda_stream_batch_selected_apply_split`** `rocm/ds4_rocm_runtime.cuh:2353`  
  Ritorna puntatori ai missing anche mentre le letture possono essere ancora pendenti.
- **`cuda_stream_batch_selected_cache_release`** `rocm/ds4_rocm_runtime.cuh:711`  
  Ignora l'esito dei wait e libera comunque i buffer.
- **`cuda_stream_batch_selected_ensure_buffers`** `rocm/ds4_rocm_runtime.cuh:1190`  
  Una crescita rialloca intere famiglie di buffer e staging, non solo quello insufficiente.
- **`cuda_stream_batch_selected_finish_pending_missing`** `rocm/ds4_rocm_runtime.cuh:2410`  
  Su errore svuota l'intera cache residente, non solo gli esperti mancanti.
- **`cuda_stream_batch_selected_mark_inflight`** `rocm/ds4_rocm_runtime.cuh:1004`  
  Fuori modalità SSD non registra eventi ma ritorna successo.
- **`cuda_stream_batch_selected_pending_matches`** `rocm/ds4_rocm_runtime.cuh:2329`  
  Non confronta direttamente gli ID selezionati, solo forma, offset e taglie.
- **`cuda_stream_batch_selected_prepare`** `rocm/ds4_rocm_runtime.cuh:3578`  
  La copia DeviceToHost è sincrona e serializza il chiamante.
- **`cuda_stream_batch_selected_prepare_from_host`** `rocm/ds4_rocm_runtime.cuh:3108`  
  Con begin_pending espone subito puntatori a destinazioni ancora in caricamento.
- **`cuda_stream_batch_selected_reuse_ensure_event`** `rocm/ds4_rocm_runtime.cuh:909`  
  La creazione fallita viene ritentata al prossimo uso.
- **`cuda_stream_batch_selected_reuse_wait`** `rocm/ds4_rocm_runtime.cuh:989`  
  Azzera pending solo dopo un wait riuscito.
- **`cuda_stream_batch_selected_stage_release`** `rocm/ds4_rocm_runtime.cuh:1148`  
  Azzera capacità e puntatori ma non le corrispondenti tabelle in VRAM.
- **`cuda_stream_batch_selected_upload_ensure_event`** `rocm/ds4_rocm_runtime.cuh:924`  
  La creazione fallita viene ritentata al prossimo uso.
- **`cuda_stream_batch_selected_upload_record_ready`** `rocm/ds4_rocm_runtime.cuh:955`  
  Condivide lo stream upload della cache singola, non uno stream batch dedicato.
- **`cuda_stream_batch_selected_upload_wait_host`** `rocm/ds4_rocm_runtime.cuh:939`  
  Il flag resta pending se la sincronizzazione fallisce.
- **`cuda_stream_batch_selected_wait_upload_ready`** `rocm/ds4_rocm_runtime.cuh:970`  
  Non azzera il flag pending dopo aver inserito la dipendenza.
- **`cuda_stream_cache_layer_stats_on`** `rocm/ds4_rocm_runtime.cuh:386`  
  La sola presenza della variabile abilita: anche il valore 0.
- **`cuda_stream_cache_stats_note_resident`** `rocm/ds4_rocm_runtime.cuh:412`  
  Non misura il driver: usa contatori e dimensione del vettore globali.
- **`cuda_stream_cache_stats_on`** `rocm/ds4_rocm_runtime.cuh:394`  
  Le statistiche per layer abilitano anche quelle aggregate; 0 conta come presente.
- **`cuda_stream_cache_stats_print`** `rocm/ds4_rocm_runtime.cuh:423`  
  Non stampa nulla se le statistiche non erano abilitate.
- **`cuda_stream_dynamic_arena_copy_hit`** `ds4_cuda.cu:28347`  
  Qualunque errore H2D diventa un miss; il chiamante ricarica dalla sorgente esatta.
- **`cuda_stream_evict_past_layers_first`** `rocm/ds4_rocm_runtime.cuh:403`  
  Solo una stringa non vuota diversa da 0 abilita; il valore resta memorizzato.
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
- **`cuda_stream_expert_slab_grow`** `rocm/ds4_rocm_runtime.cuh:1568`  
  Dimezza silenziosamente la slab finché una cudaMalloc riesce.
- **`cuda_stream_expert_slot_acquire`** `rocm/ds4_rocm_runtime.cuh:1616`  
  Una taglia diversa non prova altre classi slab e ritorna NULL subito.
- **`cuda_stream_flush_read_jobs`** `rocm/ds4_rocm_runtime.cuh:2499`  
  Azzera count anche in caso di errore, perdendo il lotto per un retry.
- **`cuda_stream_layer_expert_cache_apply`** `rocm/ds4_rocm_runtime.cuh:2514`  
  Cerca solo due slot indicizzati altrove per parità di layer.
- **`cuda_stream_layer_expert_cache_load`** `rocm/ds4_rocm_runtime.cuh:2548`  
  Per crescere svuota la cache residente; un read fallito lascia il buffer inattivo allocato.
- **`cuda_stream_layer_expert_cache_prepare_batch`** `rocm/ds4_rocm_runtime.cuh:3636`  
  Non ha chiamanti diretti e sincronizza lo stream dopo upload da memoria malloc ordinaria.
- **`cuda_stream_layer_expert_cache_release`** `rocm/ds4_rocm_runtime.cuh:669`  
  Anche se la sincronizzazione fallisce procede comunque con cudaFree.
- **`cuda_stream_layer_expert_cache_seed_selected`** `rocm/ds4_rocm_runtime.cuh:3821`  
  Su qualunque errore svuota tutta la cache residente.
- **`cuda_stream_model_cache_prepare_memory`** `rocm/ds4_rocm_runtime.cuh:5471`  
  Se cudaMemGetInfo fallisce ritorna successo senza liberare spazio.
- **`cuda_stream_read_direct_disabled`** `rocm/ds4_rocm_runtime.cuh:1929`  
  Il valore resta memorizzato; su piattaforme senza O_DIRECT il flag è irrilevante.
- **`cuda_stream_read_job_run`** `rocm/ds4_rocm_runtime.cuh:1938`  
  Un errore direct fa fallback per il job ma non disabilita il fd direct condiviso.
- **`cuda_stream_read_job_upload`** `rocm/ds4_rocm_runtime.cuh:1987`  
  Ogni upload è reso sincrono nel worker, riducendo l'overlap sullo stesso stream.
- **`cuda_stream_read_jobs_free`** `rocm/ds4_rocm_runtime.cuh:2315`  
  Non libera alcuna memoria nonostante il nome free.
- **`cuda_stream_read_jobs_parallel`** `rocm/ds4_rocm_runtime.cuh:2309`  
  È sincrona per il chiamante: start è seguito subito da wait.
- **`cuda_stream_read_jobs_prepare`** `rocm/ds4_rocm_runtime.cuh:2187`  
  La crescita libera il vecchio staging prima di sapere se il nuovo sarà allocato.
- **`cuda_stream_read_jobs_start`** `rocm/ds4_rocm_runtime.cuh:2233`  
  Una chiamata annidata dallo stesso owner fallisce; gli altri thread aspettano.
- **`cuda_stream_read_jobs_wait`** `rocm/ds4_rocm_runtime.cuh:2265`  
  Il pool viene reso disponibile prima di scandire e stampare gli errori dei job.
- **`cuda_stream_read_pool_ensure`** `rocm/ds4_rocm_runtime.cuh:2120`  
  L'inizializzazione avviene al primo job, non durante ds4_gpu_init.
- **`cuda_stream_read_pool_shutdown`** `rocm/ds4_rocm_runtime.cuh:2165`  
  Non distrugge qui gli stream upload; lo fa il rilascio dello staging.
- **`cuda_stream_read_profile_coalesce`** `rocm/ds4_rocm_runtime.cuh:1802`  
  Gli intervalli invalidi vengono saltati senza segnalazione.
- **`cuda_stream_read_profile_enabled`** `rocm/ds4_rocm_runtime.cuh:1915`  
  Valori vuoti e 0 disabilitano; modifiche successive all'ambiente non contano.
- **`cuda_stream_read_profile_note_jobs`** `rocm/ds4_rocm_runtime.cuh:1835`  
  Se il profiling non vale esattamente 1 ignora tutto.
- **`cuda_stream_read_profile_print`** `rocm/ds4_rocm_runtime.cuh:1882`  
  Non ha chiamanti diretti: viene registrata indirettamente con atexit.
- **`cuda_stream_read_profile_us`** `rocm/ds4_rocm_runtime.cuh:1798`  
  Arrotonda al microsecondo più vicino e satura implicitamente solo al cast.
- **`cuda_stream_read_stage_release`** `rocm/ds4_rocm_runtime.cuh:694`  
  La VRAM non cambia: libera memoria host pinned, non device.
- **`cuda_stream_read_upload_streams_destroy`** `rocm/ds4_rocm_runtime.cuh:2092`  
  Scorre il massimo compilato, non solo il numero di worker attivi.
- **`cuda_stream_read_upload_streams_ensure`** `rocm/ds4_rocm_runtime.cuh:2101`  
  Se una creazione fallisce distrugge anche gli stream creati prima.
- **`cuda_stream_read_worker`** `rocm/ds4_rocm_runtime.cuh:2014`  
  È avviata via puntatore pthread, quindi il grafo meccanico non mostra chiamanti.
- **`cuda_stream_read_worker_count`** `rocm/ds4_rocm_runtime.cuh:2075`  
  0 diventa 1 e un suffisso non numerico dopo le cifre viene accettato.
- **`cuda_stream_resident_alloc`** `rocm/ds4_rocm_runtime.cuh:1639`  
  Taglie diverse dalla slab usano cudaMalloc dedicate; OOM provoca espulsioni e retry.
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
- **`cuda_stream_resident_entry_key`** `rocm/ds4_rocm_runtime.cuh:1404`  
  Copia tutti i campi identificativi, non il puntatore VRAM.
- **`cuda_stream_resident_evict_at`** `rocm/ds4_rocm_runtime.cuh:1442`  
  Sposta l'ultimo elemento nel buco, invalidando indici vettoriali esterni.
- **`cuda_stream_resident_evict_one`** `rocm/ds4_rocm_runtime.cuh:1475`  
  La preferenza past-layer ignora i layer futuri, poi ricade su LRU globale.
- **`cuda_stream_resident_find`** `rocm/ds4_rocm_runtime.cuh:1416`  
  Una chiave presente con indice fuori limite viene trattata come miss senza ripararla.
- **`cuda_stream_resident_free_reserve_bytes`** `rocm/ds4_rocm_runtime.cuh:1516`  
  Default 16 GiB: su una RTX 12 GB impedisce di fatto la crescita della cache.
- **`cuda_stream_resident_key_equal`** `ds4_cuda.cu:27968`  
  Confronta l'indirizzo model_map, non il contenuto del modello.
- **`cuda_stream_resident_key_make`** `ds4_cuda.cu:27950`  
  Con tabella nulla restituisce la chiave predefinita e ignora expert.
- **`cuda_stream_resident_make_key`** `rocm/ds4_rocm_runtime.cuh:1383`  
  La chiave include model_map: la stessa regione con base diversa non coincide.
- **`cuda_stream_resident_make_room`** `rocm/ds4_rocm_runtime.cuh:1540`  
  Se cudaMemGetInfo fallisce ritorna successo dopo aver consumato l'errore.
- **`cuda_stream_resident_reclaim_wait`** `rocm/ds4_rocm_runtime.cuh:642`  
  Il secondo wait non viene eseguito se fallisce il primo.
- **`cuda_stream_resident_reserve_bytes`** `ds4_cuda.cu:27983`  
  Zero è valido e rimuove la riserva; un valore invalido avvisa una sola volta e usa 0,5 GiB.
- **`cuda_stream_resident_route_key`** `ds4_cuda.cu:27870`  
  Concatena layer ed expert in 32+32 bit: non applica hashing.
- **`cuda_stream_resident_seed_experts`** `rocm/ds4_rocm_runtime.cuh:2679`  
  Un caricamento parziale fallito svuota la cache ma ritorna comunque successo.
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
- **`cuda_stream_selected_abort_pending`** `rocm/ds4_rocm_runtime.cuh:2446`  
  Abort è bloccante e non libera gli esperti già allocati.
- **`cuda_stream_selected_apply`** `rocm/ds4_rocm_runtime.cuh:4499`  
  La sola presenza di DISABLE_STREAMING_SPLIT_SELECTED, anche 0, forza il completamento.
- **`cuda_stream_selected_apply_split`** `rocm/ds4_rocm_runtime.cuh:4407`  
  Azzera subito override_n mentre i miss possono essere ancora in lettura.
- **`cuda_stream_selected_cache_header`** `rocm/ds4_rocm_runtime.cuh:2925`  
  Non imposta loaded né gli offset dei tre pesi.
- **`cuda_stream_selected_cache_invalidate`** `ds4_cuda.cu:1897`  
  Non libera puntatori o capacità VRAM della cache selected.
- **`cuda_stream_selected_cache_release`** `rocm/ds4_rocm_runtime.cuh:757`  
  Ignora i wait iniziali e richiama rilasci che possono sincronizzare di nuovo.
- **`cuda_stream_selected_cache_release_at_decode_start`** `ds4_cuda.cu:2046`  
  DS4_CUDA_RELEASE_PREFILL_COMPACT=0 disabilita; assente o vuota lascia attivo il rilascio.
- **`cuda_stream_selected_cache_transport_begin_load`** `ds4_cuda.cu:29056`  
  Con SSD streaming spento invalida lo stato e ritorna successo senza caricare.
- **`cuda_stream_selected_cache_transport_release`** `ds4_cuda.cu:1936`  
  Ignora errori di set-device e cudaFree, poi cancella comunque lo stato.
- **`cuda_stream_selected_capacity_bytes`** `ds4_cuda.cu:1902`  
  Satura a UINT64_MAX, mascherando un eventuale overflow della somma.
- **`cuda_stream_selected_compact_mask`** `rocm/ds4_rocm_runtime.cuh:2944`  
  Registra un evento anche se la maschera non produce copie valide oltre n_selected.
- **`cuda_stream_selected_ensure_buffers`** `rocm/ds4_rocm_runtime.cuh:1035`  
  Se l'allocazione up fallisce, gate resta allocato con capacità zero fino al retry.
- **`cuda_stream_selected_ensure_bytes`** `ds4_cuda.cu:28942`  
  Libera prima il vecchio buffer: se cudaMalloc fallisce, la capacità precedente è persa.
- **`cuda_stream_selected_ensure_stream`** `rocm/ds4_rocm_runtime.cuh:787`  
  Lo stream globale viene creato sul device corrente al primo uso.
- **`cuda_stream_selected_fill_spans_overlapped`** `ds4_cuda.cu:3865`  
  Sincronizza prima del ritorno; al fallimento il chiamante ripete tutto in seriale.
- **`cuda_stream_selected_finish_pending_missing`** `rocm/ds4_rocm_runtime.cuh:4461`  
  Su errore libera tutta la cache residente.
- **`cuda_stream_selected_io_cancel_pending`** `ds4_cuda.cu:3838`  
  Aspetta ogni richiesta annullata con GetOverlappedResult bloccante.
- **`cuda_stream_selected_io_events_ensure`** `ds4_cuda.cu:3823`  
  Un errore dopo creazioni parziali lascia nel pool gli eventi già creati.
- **`cuda_stream_selected_is_current`** `rocm/ds4_rocm_runtime.cuh:1371`  
  Un puntatore nullo rende falso anche se n_selected è zero.
- **`cuda_stream_selected_load`** `rocm/ds4_rocm_runtime.cuh:4040`  
  Può ritornare successo con read pendenti e loaded ancora falso per consentire lo split.
- **`cuda_stream_selected_mark_inflight`** `rocm/ds4_rocm_runtime.cuh:893`  
  Fuori modalità SSD ritorna successo senza registrare nulla.
- **`cuda_stream_selected_pending_matches`** `rocm/ds4_rocm_runtime.cuh:4379`  
  Non confronta gli offset gate, up e down, solo modello, layer e taglie.
- **`cuda_stream_selected_prefetch_hint`** `ds4_cuda.cu:4018`  
  API risolta una volta; assenza o errore vengono ignorati e registrati una sola volta.
- **`cuda_stream_selected_prepare_ptrs`** `rocm/ds4_rocm_runtime.cuh:3016`  
  Aggiorna last_used già durante la preparazione, prima del consumo effettivo.
- **`cuda_stream_selected_reuse_ensure_event`** `rocm/ds4_rocm_runtime.cuh:799`  
  Un errore viene consumato con cudaGetLastError e sarà ritentato al prossimo uso.
- **`cuda_stream_selected_reuse_wait`** `rocm/ds4_rocm_runtime.cuh:814`  
  Azzera pending solo dopo una sincronizzazione riuscita.
- **`cuda_stream_selected_stage_pool_alloc`** `ds4_cuda.cu:3678`  
  Una richiesta più grande distrugge l'intero pool prima di tentare quello nuovo.
- **`cuda_stream_selected_stage_release`** `rocm/ds4_rocm_runtime.cuh:1020`  
  Non sincronizza stream o I/O prima di distruggere le risorse.
- **`cuda_stream_selected_upload_ensure_event`** `rocm/ds4_rocm_runtime.cuh:829`  
  Un errore di creazione lascia l'evento nullo e consente un retry.
- **`cuda_stream_selected_upload_read_jobs`** `rocm/ds4_rocm_runtime.cuh:2458`  
  Dopo il fallback non imposta uploaded: una seconda chiamata ricopia gli stessi dati.
- **`cuda_stream_selected_upload_record_ready`** `rocm/ds4_rocm_runtime.cuh:859`  
  Imposta pending solo dopo una registrazione riuscita.
- **`cuda_stream_selected_upload_wait_host`** `rocm/ds4_rocm_runtime.cuh:844`  
  Il flag resta acceso se cudaEventSynchronize fallisce.
- **`cuda_stream_selected_wait_upload_ready`** `rocm/ds4_rocm_runtime.cuh:874`  
  Non azzera pending; lo farà la marcatura inflight successiva.
- **`cuda_stream_selected_weight_storage_prepare`** `ds4_cuda.cu:28962`  
  Se packed fallisce ripiega su tre allocazioni; il mismatch viene loggato una sola volta.
- **`cuda_stream_selected_weight_storage_release`** `ds4_cuda.cu:1912`  
  Non libera slot_selected_ptr; il remap resta allocato.
- **`cuda_tensor_2d_bytes`** `rocm/ds4_rocm_compressor.cuh:174`  
  Tipo ignoto restituisce 0; i calcoli per FP32 e FP16 possono traboccare
- **`cuda_tensor_has_bytes`** `rocm/ds4_rocm_runtime.cuh:494`  
  Richiede anche ptr non nullo; un tensore vuoto con ptr nullo fallisce.
- **`cuda_tensor_has_elems`** `rocm/ds4_rocm_runtime.cuh:498`  
  Un overflow nel calcolo dei byte viene riportato come tensore insufficiente.
- **`cuda_tensor_has_elems2`** `rocm/ds4_rocm_runtime.cuh:503`  
  Overflow e capacità insufficiente producono lo stesso falso.
- **`cuda_tensor_has_elems3`** `rocm/ds4_rocm_runtime.cuh:508`  
  Overflow e capacità insufficiente producono lo stesso falso.
- **`cuda_tensor_has_f16`** `rocm/ds4_rocm_runtime.cuh:524`  
  Non ha chiamanti diretti nel grafo estratto.
- **`cuda_tensor_has_f32`** `rocm/ds4_rocm_runtime.cuh:516`  
  Controlla solo byte e puntatore, non il tipo dichiarato del tensore.
- **`cuda_tensor_has_i32`** `rocm/ds4_rocm_runtime.cuh:520`  
  Controlla solo byte e puntatore, non il tipo dichiarato del tensore.
- **`cuda_tensor_has_staged_host`** `ds4_cuda.cu:4828`  
  Usa una lookup di zero byte: verifica il binding, non l'estensione del tensore.
- **`cuda_tensor_has_u16`** `rocm/ds4_rocm_runtime.cuh:528`  
  Non ha chiamanti diretti nel grafo estratto.
- **`cuda_tmp_alloc`** `rocm/ds4_rocm_runtime.cuh:567`  
  Prima del grow libera il vecchio buffer: se cudaMalloc fallisce, lo scratch è perso.
- **`cuda_tmp_alloc_on`** `ds4_cuda.cu:2463`  
  Un grow fallito perde il vecchio scratch; in single-GPU usa un buffer globale distinto.
- **`cuda_u64_add_checked`** `rocm/ds4_rocm_runtime.cuh:375`  
  Su errore lascia *out invariato.
- **`cuda_u64_mul3_checked`** `rocm/ds4_rocm_runtime.cuh:381`  
  Il secondo prodotto non parte se il primo trabocca.
- **`cuda_u64_mul_checked`** `rocm/ds4_rocm_runtime.cuh:368`  
  Su errore lascia *out invariato.
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
- **`cursor_at`** `ds4.c:2236`  
  Non verifica subito che pos sia entro la mappatura.
- **`cursor_error`** `ds4.c:1972`  
  Gli errori successivi vengono ignorati e resta soltanto il primo.
- **`cursor_has`** `ds4.c:1978`  
  Al fallimento registra un errore persistente nel cursore.
- **`cursor_read`** `ds4.c:1986`  
  La lettura usa byte nativi senza conversione di endianness.
- **`cursor_skip`** `ds4.c:1993`  
  In caso di troncamento non avanza ma rende persistente il primo errore.
- **`cursor_string`** `ds4.c:2007`  
  La stringa non è terminata da NUL.
- **`cursor_u32`** `ds4.c:1999`  
  Non converte l'endianness.
- **`cursor_u64`** `ds4.c:2003`  
  Non converte l'endianness.
- **`deadline_backoff`** `src/cuda/route_worker.cpp:86`  
  Zero e valori negativi saltano silenziosamente l'attesa.
- **`deadline_budget_seconds`** `src/cuda/route_worker.cpp:128`  
  Normalizza una copia: il chiamante non vede le correzioni alla policy.
- **`deadline_from_now_ns`** `src/cuda/route_worker.cpp:44`  
  Forza almeno 1 ns e satura a INT64_MAX invece di segnalare overflow.
- **`deadline_policy_from_environment`** `src/cuda/route_worker.cpp:93`  
  Solo il valore esatto "1" abilita la policy; se disabilitata le altre variabili non sono lette.
- **`decode_worker_main`** `ds4_server.c:11104`  
  La sola presenza di DS4_SERVER_BATCH_LOG abilita i log, anche con valore vuoto.
- **`default_backend`** `ds4_eval.c:1528`  
  La scelta è di compilazione, non rileva l'hardware a runtime.
- **`default_server_backend`** `ds4_server.c:12960`  
  DS4_NO_GPU prevale su Apple e forza CPU.
- **`dequant_q8_0_to_f16_transpose_kernel`** `rocm/ds4_rocm_q8.cuh:1775`  
  L'output usa indice i*out_dim+row, non il layout per righe dei pesi
- **`dequeue`** `ds4_server.c:12405`  
  Con stopping attivo drena comunque i job già accodati.
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
- **`dev_dot_q4_K_q8_K_block4`** `rocm/ds4_rocm_moe.cuh:291`  
  I puntatori nulli vengono saltati silenziosamente.
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
- **`dev_pack_half2_bits`** `rocm/ds4_rocm_moe.cuh:14`  
  Arrotonda entrambi i valori a FP16 prima di restituire i bit.
- **`dev_q2_K_dot_f32`** `rocm/ds4_rocm_moe.cuh:4317`  
  Ignora qualsiasi coda se la dimensione non è multipla di 256
- **`dev_q4_K_get_scale_min`** `rocm/ds4_rocm_moe.cuh:250`  
  Per j da 4 a 7 ricompone i valori da nibble e bit alti in byte diversi
- **`dev_unpack_iq2_signs`** `rocm/ds4_rocm_moe.cuh:19`  
  Il bit di parità viene reiniettato nel bit 7 prima della replica
- **`die`** `ds4_server.c:201`  
  Non restituisce e non esegue pulizia locale
- **`directional_steering_project_kernel`** `rocm/ds4_rocm_output.cuh:53`  
  Modifica x in place; è una vera proiezione solo con direzione normalizzata.
- **`disableRawMode`** `linenoise.c:706`  
  Se tcsetattr fallisce lascia rawmode attivo e non disabilita il bracketed paste.
- **`dispatch_jobs_locked`** `ds4_server.c:12344`  
  Salta i job bloccati e assegna il primo successivo eseguibile.
- **`dist_activation_bits_or_default`** `ds4_distributed.c:932`  
  Il valore 0 significa 32 bit, non una larghezza nulla.
- **`dist_activation_bits_valid`** `ds4_distributed.c:936`  
  Considera valido 0 perché viene normalizzato a 32 bit.
- **`dist_activation_values_from_wire_bytes`** `ds4_distributed.c:950`  
  Con bits=0 assume 32 bit.
- **`dist_activation_wire_bytes`** `ds4_distributed.c:941`  
  La moltiplicazione uint64 può traboccare prima del controllo su UINT32_MAX.
- **`dist_activation_wire_bytes_from_f32_bytes`** `ds4_distributed.c:959`  
  Eredita il default a 32 bit quando bits è zero.
- **`dist_bind_connect_interface`** `ds4_distributed.c:1439`  
  Fallisce ENOTSUP se IP_BOUND_IF o IPV6_BOUND_IF non sono disponibili.
- **`dist_bind_connect_source`** `ds4_distributed.c:1407`  
  Host vuoto significa successo senza effettuare bind.
- **`dist_bytes_have_nul`** `ds4_distributed.c:1674`  
  Con len zero restituisce falso anche se p è NULL.
- **`dist_cli_need_arg`** `ds4_distributed.c:8236`  
  Incrementa index solo se il valore esiste; un errore lascia l'indice sull'opzione.
- **`dist_cli_parse_port`** `ds4_distributed.c:8250`  
  Accetta spazi iniziali e il segno +, ma rifiuta zero e limita a 65535.
- **`dist_connect_endpoint`** `ds4_distributed.c:1589`  
  Esegue fino a 200 tentativi ogni 25 ms, ma si ferma subito per errori non classificati.
- **`dist_connect_endpoint_once`** `ds4_distributed.c:1474`  
  Le env di bind, se presenti, rendono obbligatori sia interfaccia sia sorgente.
- **`dist_connect_errno_retryable`** `ds4_distributed.c:1399`  
  L'elenco è chiuso e non include EINTR o EAGAIN.
- **`dist_connect_trace_enabled`** `ds4_distributed.c:1257`  
  La sola presenza di DS4_DIST_CONNECT_TRACE abilita, anche se vuota o "0".
- **`dist_coordinator_accept_main`** `ds4_distributed.c:4426`  
  Su errori accept diversi da EBADF o EINVAL continua senza limite.
- **`dist_coordinator_add_worker`** `ds4_distributed.c:2002`  
  Un worker con stessa identità logica sostituisce il vecchio ignorando le porte.
- **`dist_coordinator_build_route_plan`** `ds4_distributed.c:2347`  
  Può riuscire con piano vuoto se il coordinatore copre già tutto il modello.
- **`dist_coordinator_can_pipeline_prefill`** `ds4_distributed.c:3567`  
  La sola presenza di DS4_DIST_DISABLE_PREFILL_PIPELINE disabilita la pipeline.
- **`dist_coordinator_client_main`** `ds4_distributed.c:4292`  
  Con canale dati separato scarta ogni frame non atteso fino alla chiusura.
- **`dist_coordinator_debug_enabled`** `ds4_distributed.c:1985`  
  Con state NULL restituisce falso.
- **`dist_coordinator_ensure_route`** `ds4_distributed.c:2469`  
  Non conserva né riusa un piano precedente.
- **`dist_coordinator_eval_remote_on_fd`** `ds4_distributed.c:2700`  
  Se torna hidden state, calcola localmente la testa di output.
- **`dist_coordinator_eval_span`** `ds4_distributed.c:2816`  
  Senza worker remoti produce i logits interamente in locale.
- **`dist_coordinator_forget_route_workers`** `ds4_distributed.c:2248`  
  Chiude anche il fd di controllo registrato e incrementa la generazione una sola volta.
- **`dist_coordinator_generation`** `ds4_distributed.c:2478`  
  Con state NULL restituisce 0.
- **`dist_coordinator_monitor_worker_fd`** `ds4_distributed.c:4266`  
  Un poll senza eventi viene ripetuto per sempre ogni secondo.
- **`dist_coordinator_prefill_chunk_cap`** `ds4_distributed.c:3587`  
  Un valore configurato nello state fa ignorare la variabile ambiente.
- **`dist_coordinator_prefill_prompt`** `ds4_distributed.c:3926`  
  Se la pipeline non e applicabile passa in serie senza segnalarlo.
- **`dist_coordinator_prefill_prompt_pipelined`** `ds4_distributed.c:3659`  
  La presenza di DS4_DIST_DISABLE_PREFILL_ACK_ONLY forza risultati completi intermedi.
- **`dist_coordinator_prefill_window`** `ds4_distributed.c:3622`  
  Zero sceglie automaticamente stages+2, limitato tra 2 e 8.
- **`dist_coordinator_rebuild_from_transcript`** `ds4_distributed.c:3094`  
  Dopo un guasto puo dimenticare tutti i worker della rotta e rifarla.
- **`dist_coordinator_remove_worker`** `ds4_distributed.c:4241`  
  Se il fd non esiste termina senza errore o log obbligatorio.
- **`dist_coordinator_report_plan`** `ds4_distributed.c:2137`  
  Se debug è spento non esamina né stampa alcun piano.
- **`dist_coordinator_send_remote_work_on_fd`** `ds4_distributed.c:2639`  
  Con ack_only il worker intermedio restituisce solo un ACK.
- **`dist_copy_file_range`** `ds4_distributed.c:795`  
  Modifica permanentemente la posizione corrente di src.
- **`dist_decode_activation_payload`** `ds4_distributed.c:1112`  
  A 32 bit restituisce un alias del buffer wire; a 8/16 alloca un nuovo buffer.
- **`dist_decode_profile_enabled`** `ds4_distributed.c:898`  
  La sola presenza di DS4_DIST_DECODE_PROFILE abilita, anche se vuota o "0".
- **`dist_discard_bytes`** `ds4_distributed.c:1302`  
  EOF restituisce 0, distinto dall'errore -1.
- **`dist_f16_to_f32`** `ds4_distributed.c:996`  
  Preserva payload NaN solo nei bit disponibili dell'half.
- **`dist_f32_to_f16`** `ds4_distributed.c:964`  
  I NaN vengono canonicalizzati e gli overflow diventano infinito.
- **`dist_f32_to_f8_e4m3`** `ds4_distributed.c:1025`  
  NaN, infiniti e valori grandi saturano al massimo finito 240.
- **`dist_f8_e4m3_to_f32`** `ds4_distributed.c:1058`  
  Ogni esponente 15 viene interpretato come ±240, non NaN o infinito.
- **`dist_forward_work_to_next`** `ds4_distributed.c:6864`  
  Un errore di invio chiude sia la connessione downstream sia quella upstream.
- **`dist_hello_from_wire`** `ds4_distributed.c:1618`  
  Modifica il record in place.
- **`dist_hello_to_wire`** `ds4_distributed.c:1605`  
  Modifica il record in place.
- **`dist_json_utf8_valid`** `ds4_distributed.c:2941`  
  Non verifica caratteri non validi oltre U+10FFFF se il primo byte supera F4.
- **`dist_json_write_string`** `ds4_distributed.c:2969`  
  Se l'intera stringa non e UTF-8, ogni byte alto diventa un escape separato.
- **`dist_json_write_token`** `ds4_distributed.c:2994`  
  Se il testo del token manca, emette testo vuoto e bytes vuoti.
- **`dist_kv_layer_tensor_bytes`** `ds4_distributed.c:4757`  
  Per GLM-DSA delega a un formato di payload completamente diverso.
- **`dist_kv_layout_matches`** `ds4_distributed.c:4812`  
  Non confronta il campo vocab.
- **`dist_kv_parse_layer_payload`** `ds4_distributed.c:4838`  
  Rewind del file e obbligatorio e lascia il cursore all'inizio dei tensori.
- **`dist_kv_raw_live_valid`** `ds4_distributed.c:4827`  
  GLM-DSA accetta raw_live inferiore al massimo, gli altri engine no.
- **`dist_kv_route_shard`** `ds4_distributed.c:5019`  
  Non controlla i limiti dell'indice remoto.
- **`dist_kv_route_shard_count`** `ds4_distributed.c:5015`  
  Include sempre uno shard locale oltre a quelli remoti.
- **`dist_kv_route_validate`** `ds4_distributed.c:5037`  
  Una rotta senza worker e valida solo se la slice locale copre ogni layer.
- **`dist_kv_shards_close`** `ds4_distributed.c:5066`  
  Non libera l'array e non azzera i FILE chiusi.
- **`dist_kv_state_bytes`** `ds4_distributed.c:4743`  
  Ogni ratio diverso da 4 usa coff uguale a 1 senza rifiutarlo.
- **`dist_kv_write_layer_header`** `ds4_distributed.c:4978`  
  I due array sono serializzati in blocchi separati, non interlacciati.
- **`dist_kv_write_session_header`** `ds4_distributed.c:4952`  
  Scrive i campi uno a uno in formato payload, non la struct grezza.
- **`dist_listener_port`** `ds4_distributed.c:1382`  
  Qualunque errore restituisce 0, indistinguibile da una porta non assegnata.
- **`dist_load_remote_shard_from_payload`** `ds4_distributed.c:5190`  
  Apre una nuova connessione dati per ogni shard.
- **`dist_logits_argmax`** `ds4_distributed.c:2461`  
  NaN e pareggi conservano il primo indice, inizialmente zero.
- **`dist_logits_top_logprobs`** `ds4_distributed.c:3057`  
  Ignora silenziosamente NaN e infiniti; con tutti non finiti restituisce zero.
- **`dist_make_session_id`** `ds4_distributed.c:4471`  
  Non garantisce unicita crittografica; sostituisce solo lo zero con uno.
- **`dist_measure_file`** `ds4_distributed.c:817`  
  Misura la posizione corrente, non la dimensione totale del file.
- **`dist_mem_read`** `ds4_distributed.c:7000`  
  Con dst nullo e len positivo esegue comunque memcpy e puo fallire.
- **`dist_now_sec`** `ds4_distributed.c:693`  
  Non restituisce tempo civile e non è confrontabile con timestamp reali.
- **`dist_open_listener`** `ds4_distributed.c:1339`  
  Ignora gli errori di SO_REUSEADDR e delle opzioni low-latency.
- **`dist_parse_layers`** `ds4_distributed.c:8194`  
  output diventa UINT32_MAX; i limiti del modello sono validati solo dopo il caricamento.
- **`dist_parse_positive_u32`** `ds4_distributed.c:902`  
  Rifiuta esplicitamente zero e qualsiasi carattere finale.
- **`dist_parse_role`** `ds4_distributed.c:8162`  
  Accetta solo none, coordinator e worker con confronto case-sensitive.
- **`dist_parse_u32_component`** `ds4_distributed.c:8179`  
  Accetta spazi iniziali e il segno + perché usa strtoul.
- **`dist_payload_copy_bytes`** `ds4_distributed.c:757`  
  Alloca sempre un buffer host da 8 MiB, anche per copie minime.
- **`dist_payload_read_bytes`** `ds4_distributed.c:717`  
  remaining cala solo dopo una lettura interamente riuscita.
- **`dist_payload_read_u32`** `ds4_distributed.c:747`  
  Il formato file è little-endian, non network byte order.
- **`dist_payload_write_bytes`** `ds4_distributed.c:703`  
  Può spezzare una richiesta oltre SIZE_MAX in più fwrite.
- **`dist_payload_write_u32`** `ds4_distributed.c:737`  
  Il formato file è sempre little-endian, indipendente dall'host.
- **`dist_peer_name`** `ds4_distributed.c:1321`  
  Ogni errore ricade silenziosamente su host "unknown" e porta "0".
- **`dist_prefill_reader_emit_progress`** `ds4_distributed.c:3425`  
  Emette piu callback arretrate in un'unica chiamata.
- **`dist_prefill_reader_signal_progress`** `ds4_distributed.c:3414`  
  Il contatore puo solo crescere; valori inferiori vengono ignorati.
- **`dist_prefill_reader_wait_emit_progress`** `ds4_distributed.c:3447`  
  Restituisce true solo quando done e tutto il progresso e stato emesso.
- **`dist_prefill_reader_wait_flow_window`** `ds4_distributed.c:3466`  
  Con reader nullo o window zero disabilita silenziosamente il limite.
- **`dist_prefill_result_reader_main`** `ds4_distributed.c:3489`  
  Un risultato logits anticipato e accettato ma scartato se non e l'ultimo chunk.
- **`dist_prefill_send_depth`** `ds4_distributed.c:614`  
  Env invalida usa 2; con zero chunk restituisce comunque 1.
- **`dist_prefill_sender_acquire_slot`** `ds4_distributed.c:3298`  
  Restituisce lo slot senza mantenerne bloccato il mutex.
- **`dist_prefill_sender_cancel`** `ds4_distributed.c:3342`  
  Esegue shutdown del socket, interrompendo anche il reader concorrente.
- **`dist_prefill_sender_destroy`** `ds4_distributed.c:3285`  
  Non azzera i puntatori dopo la liberazione.
- **`dist_prefill_sender_enqueue_slot`** `ds4_distributed.c:3317`  
  Non riceve lo slot: avanza sempre tail implicitamente.
- **`dist_prefill_sender_finish`** `ds4_distributed.c:3335`  
  Non svuota ne cancella gli slot gia accodati.
- **`dist_prefill_sender_init`** `ds4_distributed.c:3248`  
  Un errore parziale richiede comunque destroy per liberare i buffer gia creati.
- **`dist_prefill_sender_main`** `ds4_distributed.c:3352`  
  Conta i byte inviati anche quando l'invio del chunk fallisce.
- **`dist_prepare_shard_from_session_payload`** `ds4_distributed.c:5144`  
  Consuma definitivamente dal file sorgente mentre costruisce lo shard.
- **`dist_prompt_is_rendered_chat`** `ds4_distributed.c:2936`  
  Controlla solo il prefisso BOS, non valida il resto del template.
- **`dist_read_frame_header`** `ds4_distributed.c:1285`  
  Con magic errato lascia il corpo sul socket.
- **`dist_read_full`** `ds4_distributed.c:1242`  
  Usa ritorno tri-stato: 1 completo, 0 EOF, -1 errore.
- **`dist_read_snapshot_begin_frame`** `ds4_distributed.c:4524`  
  Scarta sempre gli eventuali token della risposta invece di restituirli.
- **`dist_read_snapshot_done_frame`** `ds4_distributed.c:4598`  
  Tronca il messaggio remoto a 255 byte ma scarta correttamente il resto.
- **`dist_receive_snapshot_chunks_to_file`** `ds4_distributed.c:4668`  
  Non attende un frame DONE; lo lascia al chiamante.
- **`dist_recv_hello`** `ds4_distributed.c:1937`  
  Rifiuta NUL incorporati e nomi oltre 127 byte.
- **`dist_recv_result_alloc`** `ds4_distributed.c:2490`  
  Scarta tutta la telemetria se debug è disattivato.
- **`dist_replay_check_logits`** `ds4_distributed.c:3978`  
  Usa uguaglianza esatta; anche scarti minimi o NaN fanno fallire il controllo.
- **`dist_report_prefill_progress`** `ds4_distributed.c:3652`  
  Valori oltre INT_MAX vengono saturati.
- **`dist_resolved_layer_end`** `ds4_distributed.c:675`  
  has_output forza n_layers-1 e ignora layers.end.
- **`dist_result_from_wire`** `ds4_distributed.c:1770`  
  Non valida coerenza tra conteggi e dimensioni.
- **`dist_result_to_wire`** `ds4_distributed.c:1757`  
  Non converte telemetria o payload allegati.
- **`dist_rewind_file`** `ds4_distributed.c:809`  
  Anche per riavvolgere tenta prima un flush.
- **`dist_role_name`** `ds4_distributed.c:680`  
  Valori enum sconosciuti diventano la stringa "unknown".
- **`dist_route_entry_matches_worker`** `ds4_distributed.c:2237`  
  Confronta l'host testualmente, senza normalizzazione DNS.
- **`dist_route_from_wire`** `ds4_distributed.c:1729`  
  Non valida host_len, porta, layer o flag.
- **`dist_route_get_entry`** `ds4_distributed.c:6157`  
  Se trova il target ritorna prima di validare le entry e i byte successivi.
- **`dist_route_get_return_target`** `ds4_distributed.c:6210`  
  Consente host_len zero per la destinazione finale.
- **`dist_route_plan_append_blob`** `ds4_distributed.c:2281`  
  Il nome host è copiato senza terminatore NUL.
- **`dist_route_plan_append_return_upstream`** `ds4_distributed.c:2319`  
  Aggiunge un record con host_len e porta pari a zero.
- **`dist_route_plan_free`** `ds4_distributed.c:2227`  
  Azzera l'intera struttura dopo la liberazione.
- **`dist_route_return_from_wire`** `ds4_distributed.c:1745`  
  Non valida il kind del ritorno.
- **`dist_route_return_to_wire`** `ds4_distributed.c:1751`  
  Modifica il record in place.
- **`dist_route_search_workers`** `ds4_distributed.c:2100`  
  Sceglie la prima soluzione DFS nell'ordine ricevuto.
- **`dist_route_to_wire`** `ds4_distributed.c:1737`  
  Modifica il record in place.
- **`dist_route_validate_blob`** `ds4_distributed.c:6277`  
  Con route_count zero accetta solo un blob di zero byte.
- **`dist_run_coordinator`** `ds4_distributed.c:5853`  
  Senza prompt entra direttamente nell'accept loop e non ritorna normalmente.
- **`dist_run_coordinator_generation`** `ds4_distributed.c:4010`  
  In modalita dump termina subito dopo aver scritto il file.
- **`dist_run_worker`** `ds4_distributed.c:8073`  
  Dopo ogni disconnessione libera tutte le sessioni e riprova per sempre.
- **`dist_save_remote_shard_to_file`** `ds4_distributed.c:5073`  
  Apre una nuova connessione dati per ogni shard.
- **`dist_send_error`** `ds4_distributed.c:1313`  
  Un messaggio NULL viene sostituito con un testo predefinito.
- **`dist_send_hello`** `ds4_distributed.c:1908`  
  Dichiara has_hidden=1 in modo incondizionato.
- **`dist_send_snapshot_begin`** `ds4_distributed.c:6059`  
  Restituisce 1 al successo, non zero.
- **`dist_send_snapshot_done`** `ds4_distributed.c:6105`  
  Un messaggio nullo diventa stringa vuota.
- **`dist_send_snapshot_error`** `ds4_distributed.c:6082`  
  L'errore usa un frame BEGIN, non un frame DONE.
- **`dist_send_snapshot_file_chunks`** `ds4_distributed.c:6124`  
  Non riavvolge il file e non invia il frame DONE.
- **`dist_send_work_error`** `ds4_distributed.c:6052`  
  Un messaggio nullo viene sostituito con un testo generico.
- **`dist_send_work_frame`** `ds4_distributed.c:6377`  
  Quantizza le attivazioni durante la scrittura in base a input_hc_bits.
- **`dist_send_work_result`** `ds4_distributed.c:5986`  
  Gli hidden state possono essere quantizzati; i logits restano sempre a 32 bit.
- **`dist_session_ensure_route`** `ds4_distributed.c:4478`  
  Libera il vecchio piano prima di sapere se il nuovo e costruibile.
- **`dist_session_token_hash_prefix`** `ds4_distributed.c:1659`  
  Fallisce se il checkpoint ha lunghezza negativa.
- **`dist_set_socket_low_latency`** `ds4_distributed.c:1173`  
  Continua dopo errori; il timeout ricezione è assente salvo env esplicita.
- **`dist_sleep_reconnect`** `ds4_distributed.c:689`  
  Il ritardo è fisso e non usa backoff.
- **`dist_snapshot_begin_from_wire`** `ds4_distributed.c:1827`  
  Non valida le dimensioni dichiarate del seguito.
- **`dist_snapshot_begin_to_wire`** `ds4_distributed.c:1809`  
  Modifica il record in place.
- **`dist_snapshot_chunk_from_wire`** `ds4_distributed.c:1851`  
  Non valida chunk_bytes rispetto al frame.
- **`dist_snapshot_chunk_to_wire`** `ds4_distributed.c:1845`  
  Non converte i byte del chunk.
- **`dist_snapshot_done_from_wire`** `ds4_distributed.c:1864`  
  Non valida message_bytes rispetto al frame.
- **`dist_snapshot_done_to_wire`** `ds4_distributed.c:1857`  
  Non converte il messaggio di errore allegato.
- **`dist_snapshot_req_from_wire`** `ds4_distributed.c:1796`  
  Non valida modello, layer o conteggio token.
- **`dist_snapshot_req_to_wire`** `ds4_distributed.c:1783`  
  Modifica il record in place.
- **`dist_sockaddr_string`** `ds4_distributed.c:1261`  
  In caso di errore produce "unknown" senza segnalarlo al chiamante.
- **`dist_socket_buffer_bytes`** `ds4_distributed.c:856`  
  Zero disabilita i setsockopt; env invalida ricade silenziosamente a 128 MiB.
- **`dist_telemetry_from_wire`** `ds4_distributed.c:1884`  
  Modifica il record in place senza validarne i campi.
- **`dist_telemetry_to_wire`** `ds4_distributed.c:1871`  
  Tempi e byte sono limitati a uint32.
- **`dist_temp_file`** `ds4_distributed.c:7008`  
  Il file resta sul filesystem finche il chiamante non esegue unlink.
- **`dist_tmpfile_or_err`** `ds4_distributed.c:832`  
  Il percorso del file temporaneo non viene esposto.
- **`dist_token_hash_prefix`** `ds4_distributed.c:1655`  
  Non è un hash crittografico, serve solo come invariante KV.
- **`dist_token_hash_update`** `ds4_distributed.c:1641`  
  Il token signed viene reinterpretato come uint32.
- **`dist_token_hash_update_span`** `ds4_distributed.c:1650`  
  L'ordine dei token influenza il risultato.
- **`dist_u64_add`** `ds4_distributed.c:839`  
  In caso di overflow lascia invariato l'accumulatore.
- **`dist_u64_from_halves`** `ds4_distributed.c:1631`  
  Interpreta sempre il primo argomento come metà alta già in host order.
- **`dist_u64_mul`** `ds4_distributed.c:845`  
  Con out NULL fallisce anche se il prodotto sarebbe valido.
- **`dist_u64_to_halves`** `ds4_distributed.c:1678`  
  Produce metà in host order; la conversione di rete avviene dopo.
- **`dist_usec_since`** `ds4_distributed.c:1897`  
  Intervalli negativi diventano 0 e quelli enormi saturano a UINT32_MAX.
- **`dist_validate_layers_for_model`** `ds4_distributed.c:8526`  
  Opt NULL, ruolo NONE o layers non impostato saltano ogni verifica con successo.
- **`dist_validate_options`** `ds4_distributed.c:8438`  
  Con ruolo NONE ignora replay_check e debug; il vincolo del replay è verificato solo altrove.
- **`dist_windows_unavailable`** `ds4_distributed.c:29`  
  Scrive l'errore solo se err e la lunghezza sono validi.
- **`dist_work_from_wire`** `ds4_distributed.c:1683`  
  Modifica il record in place ma non valida flag o dimensioni.
- **`dist_work_to_wire`** `ds4_distributed.c:1706`  
  Modifica il record in place.
- **`dist_worker_clear_sessions`** `ds4_distributed.c:6978`  
  Ogni disconnessione dal coordinatore elimina tutte le KV residenti.
- **`dist_worker_data_client_main`** `ds4_distributed.c:8003`  
  La presenza di DS4_DIST_DISABLE_WORKER_PREFETCH seleziona il loop seriale.
- **`dist_worker_data_listener_main`** `ds4_distributed.c:8027`  
  Su qualunque errore accept continua per sempre, anche con fd chiuso.
- **`dist_worker_find_session_locked`** `ds4_distributed.c:6969`  
  Non crea la sessione se manca.
- **`dist_worker_forward_window`** `ds4_distributed.c:884`  
  Env assente o invalida ricade silenziosamente a 4.
- **`dist_worker_forwarder_clear_requests`** `ds4_distributed.c:6560`  
  Non invia errori upstream per le richieste eliminate.
- **`dist_worker_forwarder_close_queue`** `ds4_distributed.c:6576`  
  Sveglia solo i producer in attesa; il relay non attende su questa condition.
- **`dist_worker_forwarder_enqueue_request`** `ds4_distributed.c:6465`  
  pending_depth zero disabilita il limite della coda.
- **`dist_worker_forwarder_note_send_done`** `ds4_distributed.c:6544`  
  Se l'ID non viene trovato non segnala alcun errore.
- **`dist_worker_forwarder_pop_request`** `ds4_distributed.c:6496`  
  Libera il nodo prima che il chiamante usi i valori copiati.
- **`dist_worker_forwarder_relay_main`** `ds4_distributed.c:6583`  
  Al termine chiude anche il socket upstream, invalidando tutta la connessione.
- **`dist_worker_forwarder_remove_request`** `ds4_distributed.c:6520`  
  Se l'ID non esiste fallisce senza chiudere la coda.
- **`dist_worker_get_forwarder`** `ds4_distributed.c:6780`  
  Mantiene forward_mu bloccato durante connect e creazione del thread.
- **`dist_worker_get_session_locked`** `ds4_distributed.c:6944`  
  La VRAM della sessione viene allocata pigramente al primo WORK o restore.
- **`dist_worker_handle_snapshot_load`** `ds4_distributed.c:7130`  
  Se il flusso si tronca dopo un errore puo chiudere la connessione senza DONE.
- **`dist_worker_handle_snapshot_save`** `ds4_distributed.c:7024`  
  Tiene state->mu durante tutta la serializzazione dello shard su file.
- **`dist_worker_handle_work`** `ds4_distributed.c:7750`  
  Alloca in RAM una copia completa del frame prima di validarlo.
- **`dist_worker_job_free`** `ds4_distributed.c:7773`  
  Accetta job nullo senza effetto.
- **`dist_worker_job_queue_cancel`** `ds4_distributed.c:7821`  
  Libera immediatamente anche i job non ancora valutati.
- **`dist_worker_job_queue_clear_locked`** `ds4_distributed.c:7792`  
  Non segnala le condition variable; lo fa il chiamante se necessario.
- **`dist_worker_job_queue_destroy`** `ds4_distributed.c:7804`  
  Svuota eventuali job ancora pendenti prima di distruggere i lock.
- **`dist_worker_job_queue_enqueue`** `ds4_distributed.c:7831`  
  Se la coda si chiude lascia al chiamante la liberazione del job.
- **`dist_worker_job_queue_finish`** `ds4_distributed.c:7813`  
  Closed non implica canceled: il consumer drena ancora la coda.
- **`dist_worker_job_queue_init`** `ds4_distributed.c:7779`  
  La profondita viene decisa una sola volta all'inizializzazione.
- **`dist_worker_job_queue_pop`** `ds4_distributed.c:7851`  
  Se closed ma la coda non e vuota continua a restituire job.
- **`dist_worker_prefetch_depth`** `ds4_distributed.c:870`  
  Env assente o invalida ricade silenziosamente a 2.
- **`dist_worker_prefetch_eval_main`** `ds4_distributed.c:7870`  
  Al primo errore cancella tutti i job pendenti e chiude il socket.
- **`dist_worker_process_work_payload`** `ds4_distributed.c:7306`  
  Tiene il mutex globale worker durante tutta la valutazione GPU.
- **`dist_worker_read_loop`** `ds4_distributed.c:5916`  
  Un tipo sconosciuto viene scartato, riceve errore e chiude l'intero loop.
- **`dist_worker_read_loop_prefetch`** `ds4_distributed.c:7892`  
  Gli snapshot sono gestiti dal reader e possono correre mentre restano WORK in coda.
- **`dist_worker_route_candidate_ok`** `ds4_distributed.c:2090`  
  Un worker finale senza output è ammesso solo se il coordinatore ha la testa locale.
- **`dist_worker_route_cmp`** `ds4_distributed.c:2079`  
  Il grafo la segna non chiamata, ma qsort la usa come callback.
- **`dist_worker_upstream_destroy`** `ds4_distributed.c:6838`  
  Attende con join ogni relay e puo bloccare finche il socket non si chiude.
- **`dist_worker_upstream_init`** `ds4_distributed.c:6454`  
  Non inizializza o valida la connessione di rete.
- **`dist_worker_upstream_send_work_error`** `ds4_distributed.c:6444`  
  Puo bloccare dietro un risultato grande gia in trasmissione.
- **`dist_worker_upstream_send_work_result`** `ds4_distributed.c:6418`  
  Serializza tutte le risposte della connessione sullo stesso mutex.
- **`dist_write_activation_payload`** `ds4_distributed.c:1071`  
  A 32 bit invia src direttamente; a 8/16 usa chunk host da massimo 1M valori.
- **`dist_write_frame_header`** `ds4_distributed.c:1276`  
  Non invia il corpo del frame.
- **`dist_write_full`** `ds4_distributed.c:1227`  
  Riprova solo EINTR; send che restituisce zero è errore.
- **`dist_write_logits_dump`** `ds4_distributed.c:3011`  
  Logits non finiti vengono scritti come null.
- **`dist_write_logprobs_dump`** `ds4_distributed.c:3135`  
  Usa sempre argmax, non il campionamento configurato per la generazione.
- **`dist_write_snapshot_load_begin`** `ds4_distributed.c:4500`  
  Restituisce 1 al successo, non zero.
- **`dot4_f32`** `rocm/ds4_rocm_common.cuh:396`  
  Non usa FMA esplicite: l'ordine delle quattro somme dipende dal compilatore CUDA.
- **`dot_f16_row`** `ds4.c:7059`  
  Sul nostro hardware non usa il ramo NEON e converte gli F16 uno per uno.
- **`dot_f32`** `ds4.c:10641`  
  La variante NEON gira solo su ARM; altrove usa il ciclo scalare.
- **`dot_i8_32`** `ds4.c:7195`  
  La variante NEON si attiva solo con n uguale a 32; altrimenti usa il ciclo scalare.
- **`dot_i8_block`** `rocm/ds4_rocm_q8.cuh:31`  
  Anche con use_dp4a attivo, ogni lunghezza diversa da 32 ricade sul ciclo scalare.
- **`dot_i8x32_dp4a`** `rocm/ds4_rocm_q8.cuh:22`  
  a usa load non allineate, b usa dereferenziazioni int32 allineate.
- **`dot_iq2_pair_16`** `ds4.c:1006`  
  Su ARM usa NEON; sugli altri target esegue due cicli scalari.
- **`dot_q2_16`** `ds4.c:1025`  
  Nel ramo NEON dotprod ogni altro shift viene trattato come 6.
- **`dot_q8_0_row`** `ds4.c:7209`  
  Il fast path ARM richiede in_dim multiplo di 32 e non gira sulla RTX.
- **`dot_q8_0_row_2`** `ds4.c:7272`  
  Senza ARM dot-product richiama due volte il kernel per una sola attivazione.
- **`dot_q8_0_row_f32_ref`** `ds4.c:7869`  
  Non quantizza l'attivazione, quindi non replica l'errore del percorso Q8_0 veloce.
- **`dot_q8_0_row_pair`** `ds4.c:7348`  
  Il fast path ARM non gira sulla RTX; resta il doppio accumulo scalare.
- **`drain_wake_fd`** `ds4_agent.c:9073`  
  Scarta tutti i byte e tratta EAGAIN, EOF e gli errori non-EINTR allo stesso modo.
- **`ds4_acquire_instance_lock`** `ds4.c:47917`  
  Qualunque errore o lock occupato termina subito l'intero processo con exit(2).
- **`ds4_add_sat_u64`** `ds4.c:4759`  
  Un overflow restituisce UINT64_MAX invece di segnalare errore.
- **`ds4_agent_unit_tests_run`** `ds4_agent.c:6969`  
  Non azzera né restituisce il contatore globale dei fallimenti.
- **`ds4_alloc_basename`** `ds4_cuda.cu:475`  
  Restituisce un puntatore dentro path, non una copia; per NULL restituisce ?.
- **`ds4_alloc_guard_begin`** `ds4.c:1154`  
  Lo stato è globale, non thread-local, e phase non viene copiato.
- **`ds4_alloc_guard_check`** `ds4.c:1164`  
  Non segnala soltanto l'errore: termina alla prima allocazione protetta.
- **`ds4_alloc_guard_end`** `ds4.c:1159`  
  Non verifica che il guard fosse attivo.
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
- **`ds4_backend_name`** `ds4.c:47816`  
  Nella build ROCm l'enum CUDA viene chiamato rocm.
- **`ds4_backend_supports_glm_streaming_full_layers`** `ds4.c:428`  
  Sul CUDA NVIDIA restituisce sempre false.
- **`ds4_backend_supports_ssd_streaming`** `ds4.c:406`  
  CUDA è rifiutato nei build Apple o DS4_NO_GPU; ROCm usa l'enum CUDA.
- **`ds4_backend_supports_streaming_auto_cache`** `ds4.c:418`  
  Sul CUDA NVIDIA restituisce false anche se lo streaming SSD è supportato.
- **`ds4_backend_uses_graph`** `ds4.c:402`  
  Solo gli enum Metal e CUDA restituiscono true.
- **`ds4_bytes_to_gib`** `ds4.c:4768`  
  Usa GiB binari, non GB decimali.
- **`ds4_chat_append_assistant_prefix`** `ds4.c:36875`  
  Su GLM senza thinking aggiunge sia apertura sia chiusura del blocco thinking.
- **`ds4_chat_append_max_effort_prefix`** `ds4.c:36792`  
  Aggiunge solo testo BPE, senza marcatore di ruolo
- **`ds4_chat_append_message`** `ds4.c:36826`  
  Un ruolo NULL o sconosciuto viene trattato come user
- **`ds4_chat_begin`** `ds4.c:36779`  
  Su GLM può aggiungere anche il token SOP
- **`ds4_compute_layer_placement`** `ds4_layer_pack.c:14`  
  Dopo il primo spill su CPU, tutti gli elementi successivi restano su CPU; un fit esatto passa.
- **`ds4_context_memory_estimate`** `ds4.c:47387`  
  Non ha chiamanti interni e forza prefill_chunk a zero oltre a disattivare lo streaming.
- **`ds4_context_memory_estimate_with_prefill`** `ds4.c:47377`  
  Forza sempre ssd_streaming a false.
- **`ds4_context_memory_estimate_with_prefill_mode`** `ds4.c:47339`  
  Un ctx_size non positivo viene silenziosamente trasformato in un contesto da un token.
- **`ds4_cuda_env_double`** `ds4_cuda.cu:103`  
  Zero è valido; negativi, NaN e infiniti producono un warning e il fallback.
- **`ds4_cuda_env_enabled`** `ds4_cuda.cu:82`  
  Qualunque valore non vuoto diverso da 0 abilita, inclusi false e stringhe arbitrarie.
- **`ds4_cuda_env_u64`** `ds4_cuda.cu:87`  
  Accetta spazi iniziali e il segno + perché usa strtoull.
- **`ds4_cuda_streaming_expert_cache_env`** `ds4.c:55947`  
  Un valore invalido conta come override valido e disabilita la cache; oltre 512 viene troncato.
- **`ds4_cuda_telemetry_env_refresh`** `ds4_cuda.cu:118`  
  Dopo il primo richiamo ignora ogni modifica alle variabili d'ambiente.
- **`ds4_default_raw_cap`** `ds4.c:12413`  
  Non restituisce mai zero: anche un contesto nullo produce capacità 1.
- **`ds4_die`** `ds4.c:1083`  
  Termina l'intero processo con exit(1).
- **`ds4_die_errno`** `ds4.c:1112`  
  Chiamate intermedie possono cambiare errno prima della stampa.
- **`ds4_dist_enabled`** `ds4_distributed.c:8266`  
  Qualunque ruolo diverso da NONE abilita la modalità.
- **`ds4_dist_options_create`** `ds4_distributed.c:8270`  
  Il fallimento di calloc è restituito come NULL senza errore.
- **`ds4_dist_options_free`** `ds4_distributed.c:8274`  
  free accetta anche NULL.
- **`ds4_dist_parse_cli_arg`** `ds4_distributed.c:8302`  
  Non consuma argomenti: per un'opzione nota restituisce subito errore.
- **`ds4_dist_prepare_engine_options`** `ds4_distributed.c:8504`  
  Con ruolo NONE può riuscire anche con puntatori NULL.
- **`ds4_dist_run`** `ds4_distributed.c:8549`  
  Scrive direttamente su stderr e restituisce sempre 1.
- **`ds4_dist_session_create`** `ds4_distributed.c:5548`  
  Fallisce sempre, indipendentemente dalle opzioni ricevute.
- **`ds4_dist_session_eval`** `ds4_distributed.c:5796`  
  Ignora token, checkpoint e logits prima di fallire.
- **`ds4_dist_session_free`** `ds4_distributed.c:5629`  
  Non libera nulla: è intenzionalmente un no-op.
- **`ds4_dist_session_load_payload`** `ds4_distributed.c:5371`  
  Non consuma alcun byte dal FILE ricevuto.
- **`ds4_dist_session_route_ready`** `ds4_distributed.c:5648`  
  Restituisce -1, mentre gli altri stub operativi restituiscono 1.
- **`ds4_dist_session_save_payload`** `ds4_distributed.c:5238`  
  Non scrive alcun byte nel FILE ricevuto.
- **`ds4_dist_session_sync`** `ds4_distributed.c:5663`  
  Ignora checkpoint, prompt e logits prima di fallire.
- **`ds4_dist_usage`** `ds4_distributed.c:8278`  
  Non è chiamata da alcun punto del grafo estratto.
- **`ds4_dot512_float4_ordered`** `ds4_cuda.cu:10548`  
  Impedisce la contrazione FMA, quindi può differire dalla variante plain
- **`ds4_dot512_float4_plain`** `ds4_cuda.cu:10566`  
  Il compilatore può contrarre dot += prodotto in FMA e cambiare gli ultimi bit
- **`ds4_dot_scalar_ldg`** `ds4_cuda.cu:10154`  
  __ldg presume dati di sola lettura durante il kernel
- **`ds4_dspark_env_u32`** `ds4.c:48144`  
  Accetta un prefisso numerico seguito da caratteri arbitrari, perche non verifica la fine.
- **`ds4_dspark_scheduler_break_even_window`** `ds4.c:48184`  
  Il default zero disabilita il controllo anticipato di break-even.
- **`ds4_dspark_scheduler_cold_low_confidence_skip_cycles`** `ds4.c:48196`  
  Si applica solo prima di qualunque accept e con confidence iniziale bassa.
- **`ds4_dspark_scheduler_cold_low_confidence_threshold`** `ds4.c:48204`  
  Divide per 1000 ma non limita a uno: valori oltre 1000 producono soglie oltre 1.
- **`ds4_dspark_scheduler_enabled`** `ds4.c:48154`  
  Assenza, stringa vuota e qualunque valore diverso esattamente da 0 lo abilitano.
- **`ds4_dspark_scheduler_max_extra_saved_ratio_milli`** `ds4.c:48180`  
  Zero disabilita il controllo fra tempo extra e tempo risparmiato.
- **`ds4_dspark_scheduler_max_ms_per_accept_milli`** `ds4.c:48176`  
  Il default 28000 equivale a 28 ms dopo la conversione del chiamante.
- **`ds4_dspark_scheduler_min_avg_milli`** `ds4.c:48172`  
  Restituisce millesimi interi senza imporre alcun limite superiore.
- **`ds4_dspark_scheduler_no_draft_skip_cycles`** `ds4.c:48188`  
  Zero disabilita soltanto la pausa immediata causata da no-draft.
- **`ds4_dspark_scheduler_short_accept_no_draft_skip_cycles`** `ds4.c:48192`  
  E solo un minimo aggiuntivo e si applica dopo accept brevi ma nessun accept lungo.
- **`ds4_dspark_scheduler_skip_cycles`** `ds4.c:48164`  
  Zero e accettato e annulla i cicli di pausa standard.
- **`ds4_dspark_scheduler_slow_skip_cycles`** `ds4.c:48168`  
  Zero e accettato anche se il default della pausa lenta e 4.
- **`ds4_dspark_scheduler_tail_min_tokens`** `ds4.c:48200`  
  Zero disabilita lo skip DSpARK per richieste con pochi token residui.
- **`ds4_dspark_scheduler_window`** `ds4.c:48159`  
  Zero non disabilita la finestra: viene sostituito con il default 4.
- **`ds4_dspark_stats_enabled`** `ds4.c:57285`  
  Qualunque stringa non vuota diversa da 0 abilita; la variabile non è memorizzata in static.
- **`ds4_dspark_stats_note_len`** `ds4.c:48137`  
  Ogni lunghezza oltre il massimo confluisce nello stesso ultimo bucket.
- **`ds4_dump_text_tokenization`** `ds4.c:51052`  
  Con testo NULL tokenizza la stringa vuota; con flusso NULL scrive su stdout.
- **`ds4_effective_prefill_chunk`** `ds4.c:12422`  
  Il default 2048 si applica solo al tensor parallel CUDA; altrimenti resta 0.
- **`ds4_encode_chat_prompt`** `ds4.c:36783`  
  Un prompt NULL diventa una stringa vuota
- **`ds4_engine_close`** `ds4.c:57231`  
  Non è idempotente: libera e stesso e chiude anche risorse GPU e thread globali.
- **`ds4_engine_collect_imatrix`** `ds4.c:51117`  
  Richiede Metal: sulla RTX/CUDA termina con errore.
- **`ds4_engine_configure_streaming_auto_cache`** `ds4.c:53931`  
  DS4_GLM_MEMORY_GUARD_* è ignorato fuori dalle build ROCm.
- **`ds4_engine_configure_streaming_cache_budget`** `ds4.c:54252`  
  Azzera sempre i globali dei layer residenti anche se lo streaming è disattivato.
- **`ds4_engine_create_with_gpu_config`** `ds4.c:55938`  
  Delega integralmente validazione e apertura alla routine interna.
- **`ds4_engine_dump_tokens`** `ds4.c:51048`  
  Non valida i puntatori prima di inoltrarli.
- **`ds4_engine_dynamic_expert_cache_bytes`** `ds4.c:35773`  
  I byte espliciti prevalgono; una stima fallita restituisce zero
- **`ds4_engine_embd_dim`** `ds4.c:57097`  
  Ignora il motore e restituisce una costante di compilazione.
- **`ds4_engine_first_token_test`** `ds4.c:53853`  
  Ignora tutti i token del prompt dopo il primo.
- **`ds4_engine_generate_argmax`** `ds4.c:51913`  
  Il fast top-1 CUDA è attivo di default e va disabilitato esplicitamente.
- **`ds4_engine_glm_layer_payload_bytes`** `ds4.c:57039`  
  Su build senza GPU o modello non GLM restituisce falso senza scrivere il risultato.
- **`ds4_engine_glm_mtp_spec_enabled`** `ds4.c:49743`  
  Non richiede mtp_ready né assenza di distribuzione, diversamente da has_mtp.
- **`ds4_engine_glm_streaming_memory_guard`** `ds4.c:54534`  
  Se i byte transienti sono zero salta completamente il controllo memoria.
- **`ds4_engine_has_mtp`** `ds4.c:49750`  
  In modalità distribuita restituisce false anche con pesi MTP pronti.
- **`ds4_engine_has_output_head`** `ds4.c:49738`  
  Un engine nullo restituisce false.
- **`ds4_engine_head_test`** `ds4.c:53756`  
  Usa l'ultimo embedding del prompt senza costruire cache per le posizioni precedenti.
- **`ds4_engine_hidden_f32_values`** `ds4.c:57033`  
  GLM restituisce N_EMBD, gli altri modelli N_HC per N_EMBD.
- **`ds4_engine_is_glm_dsa`** `ds4.c:57226`  
  Ignora il motore e legge solo la famiglia compilata.
- **`ds4_engine_layer_compress_ratio`** `ds4.c:57027`  
  Per un layer fuori intervallo restituisce zero.
- **`ds4_engine_layer_count`** `ds4.c:57018`  
  Per GLM esclude i layer next-token-prediction dal conteggio.
- **`ds4_engine_metal_graph_full_test`** `ds4.c:53723`  
  Non ha un ramo GLM dedicato, a differenza del test grafo base.
- **`ds4_engine_metal_graph_prompt_test`** `ds4.c:53739`  
  Su build senza supporto GPU ritorna errore senza eseguire il test.
- **`ds4_engine_metal_graph_test`** `ds4.c:53704`  
  Su build senza supporto GPU ritorna errore senza eseguire alcun test.
- **`ds4_engine_model_bytes`** `ds4.c:57102`  
  Non controlla il puntatore prima di dereferenziarlo.
- **`ds4_engine_model_id`** `ds4.c:57070`  
  Ignora il motore e restituisce una costante di compilazione.
- **`ds4_engine_model_name`** `ds4.c:57013`  
  Ignora il motore e restituisce una costante di compilazione.
- **`ds4_engine_mtp_draft_tokens`** `ds4.c:49756`  
  Il ramo GLM può restituire 2 senza controllare backend, distribuzione o mtp_ready.
- **`ds4_engine_open`** `ds4.c:55934`  
  Passa una config GPU nulla, quindi non abilita il placement multi-tier esplicito.
- **`ds4_engine_open_internal`** `ds4.c:55966`  
  La variabile cache CUDA, anche invalida, prevale sulla CLI; inspect-only esce prima della GPU.
- **`ds4_engine_power`** `ds4.c:57003`  
  Con motore nullo restituisce 100.
- **`ds4_engine_prefill_chunk`** `ds4.c:56998`  
  Con motore nullo restituisce zero.
- **`ds4_engine_preload_pro_q4_expert_tables`** `ds4.c:54585`  
  I flag AUTO sono letti solo dopo l'opt-in Q4; il flag disable agisce per presenza.
- **`ds4_engine_print_startup_memory`** `ds4.c:35801`  
  Con motore nullo o contesto non positivo non stampa nulla
- **`ds4_engine_routed_quant_bits`** `ds4.c:49728`  
  Qualunque tipo diverso da Q4_K viene riportato come 2 bit; decide il primo gate.
- **`ds4_engine_set_power`** `ds4.c:57007`  
  Rifiuta i valori fuori intervallo invece di limitarli.
- **`ds4_engine_streaming_transient_guard_bytes`** `ds4.c:35792`  
  Le somme saturano a UINT64_MAX invece di fallire
- **`ds4_engine_summary`** `ds4.c:56972`  
  Il riepilogo di supporto appare solo se la sua mappa è aperta.
- **`ds4_engine_tp_big_exchange`** `ds4.c:57126`  
  Qualunque valore presente di DS4_GLM_TP_DEBUG abilita il log; non gira sulla nostra CUDA.
- **`ds4_engine_tp_bind`** `ds4.c:57145`  
  Sulla nostra CUDA restituisce sempre 0 con errore Metal, senza tentare un bind CUDA.
- **`ds4_engine_tp_exchange`** `ds4.c:57111`  
  Un singolo errore marca permanentemente fallito il contesto TP; non gira sulla nostra CUDA.
- **`ds4_engine_tp_gate_schedule`** `ds4.c:57078`  
  GLM salta i blocchi densi iniziali e il blocco next-n finale.
- **`ds4_engine_tp_vocab_split`** `ds4.c:57106`  
  È vero solo con TP attivo e split; un motore nullo vale falso.
- **`ds4_engine_vocab_size`** `ds4.c:56994`  
  Con motore nullo restituisce zero.
- **`ds4_expected_layer_compress_ratio`** `ds4.c:1096`  
  Flash usa 0 nei primi due layer; Pro usa 128, poi entrambi alternano 4 e 128.
- **`ds4_expert_hotlist_sort_cmp`** `ds4.c:1307`  
  A parità ordina per layer e ID, non conserva l'ordine originale.
- **`ds4_expert_profile_cache_use`** `ds4.c:1376`  
  Simula una cache, ma non carica né espelle alcun peso reale.
- **`ds4_expert_profile_close`** `ds4.c:1630`  
  Gli errori di output sono solo loggati e la chiusura prosegue.
- **`ds4_expert_profile_init`** `ds4.c:1344`  
  Due percorsi vuoti non disattivano un profilo già attivo.
- **`ds4_expert_profile_record`** `ds4.c:1412`  
  Un esperto non valido entra nel confronto adiacente prima di essere scartato dagli istogrammi.
- **`ds4_expert_profile_sort_cmp`** `ds4.c:1290`  
  Ordina prima per conteggio, poi peso, infine ID esperto.
- **`ds4_expert_profile_write_cache_summary`** `ds4.c:1463`  
  Con peso totale non positivo il tasso pesato diventa zero.
- **`ds4_expert_profile_write_hotlist_file`** `ds4.c:1566`  
  Scrive anche tutte le coppie layer-esperto con conteggio zero.
- **`ds4_expert_profile_write_layer`** `ds4.c:1490`  
  Nel dettaglio JSON conserva solo i primi 16 esperti.
- **`ds4_format_len_hist`** `ds4.c:57290`  
  Se il buffer finisce tronca silenziosamente; un istogramma vuoto diventa none.
- **`ds4_glm_reasoning_effort_text`** `ds4.c:36637`  
  NONE e valori non riconosciuti restituiscono NULL
- **`ds4_glm_streaming_auto_full_layers`** `ds4.c:54223`  
  Usa solo un settimo del budget e comunque non oltre 10 GiB.
- **`ds4_glm_streaming_normal_layer_count`** `ds4.c:54157`  
  Se NEXTN è almeno N_LAYER restituisce N_LAYER, non zero.
- **`ds4_glm_streaming_resident_prefix_bytes`** `ds4.c:54192`  
  Con layers uguale a zero restituisce successo e zero byte.
- **`ds4_glm_streaming_supported_resident_prefix_layers`** `ds4.c:54164`  
  Salta un prefisso non supportato, poi si ferma al primo buco.
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
- **`ds4_gpu_embed_token_hc_q8_0_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:49`  
  Controlla solo il lancio: errori asincroni possono emergere dopo.
- **`ds4_gpu_embed_token_hc_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:1`  
  La mera presenza dell'env abilita staging; solo lì un token invalido viene rimappato a 0.
- **`ds4_gpu_embed_token_q8_0_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:115`  
  Il codice numerico 8 è fissato internamente come tipo Q8_0.
- **`ds4_gpu_embed_token_quant_tensor`** `ds4_rocm_compat.cu:255`  
  Supporta soltanto Q8_0; ogni altro tipo fallisce dopo un log.
- **`ds4_gpu_embed_tokens_hc_q8_0_tensor`** `rocm/ds4_rocm_embedding_launch.cuh:80`  
  ID token negativo o fuori vocabolario viene sostituito silenziosamente con 0.
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
- **`ds4_gpu_glm_attention_indexed_batch_lora_tensor`** `rocm/ds4_rocm_glm.cuh:3350`  
  Forza pos0 a zero e usa sempre righe selezionate esplicite
- **`ds4_gpu_glm_attention_indexed_batch_lora_valid_tensor`** `rocm/ds4_rocm_glm.cuh:3412`  
  Gli indici selected fuori cache vengono ignorati silenziosamente dal kernel.
- **`ds4_gpu_glm_attention_indexed_batch_tensor`** `rocm/ds4_rocm_glm.cuh:3443`  
  Alloca un temporaneo FP32 n_tokens*n_head*kv_lora_dim senza liberarlo qui
- **`ds4_gpu_glm_attention_indexed_batch_typed_tensor`** `ds4_rocm_compat.cu:371`  
  Stampa su stderr e ritorna sempre 0 senza leggere o scrivere i tensori.
- **`ds4_gpu_glm_attention_indexed_decode_split_group8_tensor`** `rocm/ds4_rocm_glm.cuh:3621`  
  Anche il percorso generico è rifiutato se non valgono i vincoli specializzati group8
- **`ds4_gpu_glm_attention_indexed_decode_split_group8_typed_tensor`** `ds4_cuda.cu:30072`  
  Stampa su stderr e restituisce sempre 0.
- **`ds4_gpu_glm_attention_indexed_decode_tensor`** `rocm/ds4_rocm_glm.cuh:3528`  
  Crea viste con bytes ridotti e alloca uno scratch LoRA senza liberarlo qui
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
- **`ds4_gpu_glm_qk_lowrank_q8_0_batch_tensor`** `rocm/ds4_rocm_glm.cuh:1907`  
  Usa il kernel grouped solo per batch, colonne multiple di 32 e opzione runtime attiva
- **`ds4_gpu_glm_qk_lowrank_q8_0_tensor`** `rocm/ds4_rocm_glm.cuh:1867`  
  Copia qk_nope float in shared memory, quindi il limite score vincola la proiezione
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
- **`ds4_gpu_glm_value_project_q8_0_batch_heads_tensor`** `rocm/ds4_rocm_glm.cuh:1972`  
  Nel decode il kernel wave è attivo di default; env uguale a 0 forza il fallback seriale
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
- **`ds4_gpu_matmul_q8_0_decode_mpp_model_view_tensor`** `rocm/ds4_rocm_matmul.cuh:534`  
  La model view cambia solo l'etichetta diagnostica, non il calcolo
- **`ds4_gpu_matmul_q8_0_decode_mpp_tensor`** `rocm/ds4_rocm_matmul.cuh:514`  
  MPP compare solo nell'etichetta: usa lo stesso dispatcher Q8 generico
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
- **`ds4_gpu_matmul_q8_0_rows_scalar_tensor`** `rocm/ds4_rocm_matmul.cuh:554`  
  Ignora tutti gli argomenti, non scrive l'output e restituisce sempre 0
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
- **`ds4_gpu_release_q8_f16_cache`** `rocm/ds4_rocm_runtime.cuh:6313`  
  Azzera anche il flag OOM e l'avviso di budget, consentendo nuove allocazioni.
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
- **`ds4_gpu_shared_gate_up_async_wait`** `rocm/ds4_rocm_shared_expert.cuh:386`  
  Non ha chiamanti; senza lavoro pendente restituisce comunque successo.
- **`ds4_gpu_shared_gate_up_swiglu_q8_0_async_tensor`** `rocm/ds4_rocm_shared_expert.cuh:257`  
  È esportata ma senza chiamanti; quality mode e graph_dump la disabilitano restituendo 0.
- **`ds4_gpu_shared_gate_up_swiglu_q8_0_batch_tensor`** `rocm/ds4_rocm_shared_expert.cuh:390`  
  Gate e up non vengono salvati salvo quality mode o graph_dump.
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
- **`ds4_gpu_stream_expert_cache_load_layer`** `rocm/ds4_rocm_current_api_compat.cuh:248`  
  Se rialloca il buffer del layer, svuota prima tutta la cache residente.
- **`ds4_gpu_stream_expert_cache_prepare_selected_batch`** `rocm/ds4_rocm_current_api_compat.cuh:217`  
  Per batch non popola slot residenti: usa il trasporto compatto.
- **`ds4_gpu_stream_expert_cache_release_layer_cache`** `rocm/ds4_rocm_current_api_compat.cuh:284`  
  Restituisce sempre 1 anche se la sincronizzazione prima del free fallisce.
- **`ds4_gpu_stream_expert_cache_release_resident`** `rocm/ds4_rocm_current_api_compat.cuh:166`  
  Il nome suggerisce solo i residenti, ma rilascia anche observer e arena.
- **`ds4_gpu_stream_expert_cache_reset_route_hotness`** `rocm/ds4_rocm_current_api_compat.cuh:163`  
  Azzera anche in modalità observe, ma non svuota gli esperti residenti.
- **`ds4_gpu_stream_expert_cache_seed_experts`** `rocm/ds4_rocm_current_api_compat.cuh:289`  
  Se l'arena dinamica è spenta, riesce ma non carica nulla.
- **`ds4_gpu_stream_expert_cache_seed_from_layer_selected`** `rocm/ds4_rocm_current_api_compat.cuh:262`  
  Riduce in silenzio n_seed_tokens a n_tokens.
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
- **`ds4_gpu_tp_set_batch_exchange`** `ds4_rocm.cu:143`  
  No-op silenzioso: non registra la callback di scambio batch.
- **`ds4_gpu_tp_set_big_exchange`** `ds4_rocm.cu:163`  
  No-op silenzioso: non registra la callback di scambio bulk.
- **`ds4_gpu_tp_suspend_expert_sharding`** `ds4_rocm.cu:147`  
  Sia suspend=1 sia suspend=0 non cambiano alcuno stato CUDA
- **`ds4_gpu_vram_ledger_decode_start`** `ds4_cuda.cu:7031`  
  Non e' sola telemetria: puo' liberare realmente la VRAM del KV
- **`ds4_gpu_vram_ledger_request_end`** `ds4_cuda.cu:7060`  
  Puo' riallocare e ricopiare il KV in VRAM; ignora l'esito del ripristino
- **`ds4_gpu_wait_selected_readback_ready`** `rocm/ds4_rocm_runtime.cuh:6054`  
  Con observer spento esegue cudaDeviceSynchronize sull'intero device.
- **`ds4_help_print`** `ds4_help.c:575`  
  Un topic non supportato stampa un errore e ricade silenziosamente sull'help predefinito
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
- **`ds4_json_write_string`** `ds4.c:1322`  
  Un puntatore s NULL viene serializzato come stringa vuota, non come null.
- **`ds4_kvstore_build_prompt_from_exact_prefix_and_text_suffix`** `ds4_kvstore.c:820`  
  La coda usa il tokenizer chat renderizzato, non il BPE di testo semplice
- **`ds4_kvstore_byte_prefix_match`** `ds4_kvstore.c:802`  
  Un prefisso vuoto corrisponde sempre
- **`ds4_kvstore_chat_anchor_pos`** `ds4_kvstore.c:846`  
  Restituisce l'indice del marcatore, non una lunghezza che lo include
- **`ds4_kvstore_clear`** `ds4_kvstore.c:512`  
  Non libera la directory kc->dir
- **`ds4_kvstore_close`** `ds4_kvstore.c:782`  
  Non elimina alcun file cache dal disco
- **`ds4_kvstore_continued_store_target`** `ds4_kvstore.c:876`  
  Saltare una frontiera esatta impedisce quel salvataggio
- **`ds4_kvstore_default_options`** `ds4_kvstore.c:282`  
  L'intervallo continued predefinito non e' ancora allineato qui
- **`ds4_kvstore_entry_eviction_score`** `ds4_kvstore.c:667`  
  Il parametro live viene ignorato completamente
- **`ds4_kvstore_entry_free`** `ds4_kvstore.c:507`  
  Azzera anche tutti i metadati della voce
- **`ds4_kvstore_evict`** `ds4_kvstore.c:696`  
  Se una cancellazione fallisce, smette e rimuove comunque la voce dall'indice
- **`ds4_kvstore_file_size_fits`** `ds4_kvstore.c:931`  
  Con cache NULL o budget zero accetta ogni dimensione valida
- **`ds4_kvstore_fill_header`** `ds4_kvstore.c:528`  
  Scrive sempre ABI payload corrente e azzera i byte riservati
- **`ds4_kvstore_find_text_prefix`** `ds4_kvstore.c:1323`  
  Riscansiona tutta la directory a ogni ricerca
- **`ds4_kvstore_key_kind`** `ds4_kvstore.c:303`  
  Se entrambi i flag sono attivi, responses-visible ha priorita'
- **`ds4_kvstore_load_result_free`** `ds4_kvstore.c:1488`  
  Dopo la chiamata anche metriche e flag vengono persi
- **`ds4_kvstore_maybe_store_continued`** `ds4_kvstore.c:1304`  
  Nel grafo estratto non ha chiamanti, quindi la politica automatica non gira
- **`ds4_kvstore_note_store`** `ds4_kvstore.c:885`  
  Valori inferiori o uguali vengono ignorati
- **`ds4_kvstore_open`** `ds4_kvstore.c:744`  
  budget_mb uguale a zero seleziona il default, non disabilita il budget
- **`ds4_kvstore_path_for_sha`** `ds4_kvstore.c:466`  
  Copia sempre 40 byte da sha senza verificarne la lunghezza
- **`ds4_kvstore_path_join`** `ds4_kvstore.c:458`  
  Usa sempre la barra '/', anche su Windows
- **`ds4_kvstore_read_entry_file`** `ds4_kvstore.c:577`  
  Accetta byte extra dopo il payload come trailer
- **`ds4_kvstore_read_header`** `ds4_kvstore.c:552`  
  Rifiuta token zero e ogni quantizzazione diversa da 2 o 4 bit
- **`ds4_kvstore_reason_code`** `ds4_kvstore.c:292`  
  Stringhe sconosciute e NULL diventano UNKNOWN senza errore
- **`ds4_kvstore_render_tokens_text`** `ds4_kvstore.c:788`  
  La concatenazione testuale puo' ritokenizzarsi diversamente al confine
- **`ds4_kvstore_restore_suppressed_continued`** `ds4_kvstore.c:898`  
  Il ripristino e' silenziosamente ignorato se il contatore e' cambiato
- **`ds4_kvstore_sha1_bytes_hex`** `ds4_kvstore.c:439`  
  SHA-1 non protegge da collisioni intenzionali
- **`ds4_kvstore_sha_hex_name`** `ds4_kvstore.c:448`  
  Accetta lettere esadecimali maiuscole ma richiede esattamente il suffisso .kv
- **`ds4_kvstore_store_len`** `ds4_kvstore.c:835`  
  Se il taglio scende sotto il minimo restituisce la lunghezza originale non allineata
- **`ds4_kvstore_store_live_prefix`** `ds4_kvstore.c:1290`  
  Disabilita sempre override testuale e relativi flag
- **`ds4_kvstore_store_live_prefix_text`** `ds4_kvstore.c:1056`  
  Puo' sfrattare file prima che il nuovo salvataggio riesca
- **`ds4_kvstore_suppress_continued_store`** `ds4_kvstore.c:891`  
  Restituisce -1 se tokens non e' esattamente un target
- **`ds4_kvstore_tokens_copy_prefix`** `ds4_kvstore.c:808`  
  Azzera solo len; una capacita' gia' allocata resta posseduta
- **`ds4_kvstore_touch_file`** `ds4_kvstore.c:620`  
  Non controlla l'esito di fclose e non aggiorna l'indice in memoria
- **`ds4_kvstore_try_load_text`** `ds4_kvstore.c:1348`  
  Un hit oltre cold_max_tokens consuma e cancella il file dopo il caricamento
- **`ds4_layer_compress_ratio`** `ds4.c:1090`  
  Per altre famiglie restituisce 0 senza validare l'indice.
- **`ds4_layer_pack_print`** `ds4_layer_pack.c:90`  
  Non cancella "(no transformer layers)" quando il tier contiene solo pseudo-layer.
- **`ds4_layer_payload_range_valid`** `ds4.c:48971`  
  I layer MTP GLM sono esclusi dall'intervallo valido.
- **`ds4_linux_graph_backend_set_oom_score`** `ds4.c:47830`  
  Marca il tentativo prima dell'I/O: un fallimento non viene mai ritentato.
- **`ds4_log`** `ds4.c:1746`  
  Non aggiunge newline e non forza il flush.
- **`ds4_log_color_code`** `ds4.c:1713`  
  Tipi non riconosciuti disattivano silenziosamente il colore.
- **`ds4_log_is_tty`** `ds4.c:1734`  
  Un descrittore negativo viene trattato semplicemente come non TTY.
- **`ds4_model_normal_layer_count`** `ds4.c:48916`  
  Per GLM sottrae i layer MTP; una configurazione invalida produce zero.
- **`ds4_mul_sat_u64`** `ds4.c:4763`  
  Un overflow restituisce UINT64_MAX invece di segnalare errore.
- **`ds4_page_size`** `ds4.c:1225`  
  Se la query di sistema fallisce usa silenziosamente 4096 byte.
- **`ds4_parallel_for`** `ds4.c:1968`  
  La soglia seriale è fissata a 512 righe.
- **`ds4_parallel_for_min_rows`** `ds4.c:1934`  
  Chiamate annidate e lavori sotto soglia diventano seriali senza avviso.
- **`ds4_parse_gib_arg`** `ds4_ssd.c:25`  
  GB significa GiB; anche un numero senza suffisso viene interpretato in GiB.
- **`ds4_parse_streaming_cache_experts_arg`** `ds4_ssd.c:53`  
  Solo il suffisso GB seleziona i byte; un numero nudo indica esperti.
- **`ds4_precise_expf`** `ds4_rocm.h:140`  
  Forza OCML precisa anche con -fapprox-func.
- **`ds4_precise_log1pf`** `ds4_rocm.h:141`  
  Forza OCML precisa anche con -fapprox-func.
- **`ds4_precise_sqrtf`** `ds4_rocm.h:142`  
  Forza OCML precisa anche con -fapprox-func.
- **`ds4_prefill_cap_for_prompt`** `ds4.c:12428`  
  Una variabile ambiente non numerica impedisce anche il fallback automatico oltre 4096.
- **`ds4_quantize_row_q8_K`** `ds4.c:3397`  
  La scala d può essere negativa perché segue il segno del massimo assoluto
- **`ds4_release_instance_lock`** `ds4.c:47901`  
  Il file di lock resta sul filesystem; viene chiuso soltanto handle o fd.
- **`ds4_remove_utf8`** `ds4.c:49967`  
  Su Windows un errore di conversione è restituito come semplice -1.
- **`ds4_sample_logits`** `ds4.c:59689`  
  Input invalido restituisce il token zero invece di un errore
- **`ds4_select_shape_from_metadata`** `ds4.c:5503`  
  Modifica g_ds4_shape globale; una forma ignota termina il processo.
- **`ds4_server_unit_tests_run`** `ds4_server.c:17737`  
  Gli assert accumulano test_failures e la suite continua dopo un fallimento
- **`ds4_session_argmax`** `ds4.c:59670`  
  Non valida il puntatore di sessione
- **`ds4_session_argmax_excluding`** `ds4.c:59674`  
  Un ID escluso fuori vocabolario non esclude nulla
- **`ds4_session_cancelled`** `ds4.c:57850`  
  Callback assente equivale sempre a non annullato
- **`ds4_session_cancelled_cb`** `ds4.c:57854`  
  Nessun chiamante diretto: viene passata come puntatore a funzione
- **`ds4_session_common_prefix`** `ds4.c:59662`  
  Checkpoint invalido restituisce zero senza confrontare token
- **`ds4_session_copy_logits`** `ds4.c:59764`  
  Capienza insufficiente restituisce zero e non copia nulla
- **`ds4_session_create`** `ds4.c:57412`  
  Con workspace condiviso la prima sessione ne cede la proprieta all'engine
- **`ds4_session_distributed_route_ready`** `ds4.c:57756`  
  Una sessione non distribuita produce errore, non false
- **`ds4_session_dspark_capture_batch_current`** `ds4.c:59808`  
  Accetta un batch catturato che termina prima del checkpoint corrente
- **`ds4_session_dspark_capture_current`** `ds4.c:59800`  
  Richiede che la cattura singola coincida esattamente col checkpoint
- **`ds4_session_dspark_capture_invalidate`** `ds4.c:48855`  
  Su CPU azzera la bozza ma non tocca la cattura del grafo.
- **`ds4_session_dspark_capture_note_checkpoint`** `ds4.c:48867`  
  Se checkpoint o cattura non sono validi, invalida l'intera cattura.
- **`ds4_session_dspark_scheduler_note`** `ds4.c:48232`  
  Un ciclo già saltato azzera solo il flag e non entra nelle statistiche.
- **`ds4_session_dspark_scheduler_reset`** `ds4.c:48208`  
  Non azzera skip, statistiche lifetime, flag long-accept o stato skipped_cycle.
- **`ds4_session_dspark_scheduler_should_skip`** `ds4.c:48217`  
  Con skip a zero non salta; ogni skip positivo viene decrementato prima del ritorno.
- **`ds4_session_eval`** `ds4.c:60614`  
  Per DSpark disattiva il probe, quindi l'eval ordinario non prepara bozze
- **`ds4_session_eval_argmax`** `ds4.c:51453`  
  CPU e GLM bypassano i percorsi veloci split-KV e vec4.
- **`ds4_session_eval_dspark_speculative_argmax`** `ds4.c:61525`  
  Un verificatore indisponibile vale zero draft accettati, non un errore.
- **`ds4_session_eval_internal`** `ds4.c:60407`  
  I contatori DS4_GLM_MTP_PROBE sono static e condivisi tra sessioni
- **`ds4_session_eval_layer_slice`** `ds4.c:58181`  
  Senza output forza una sincronizzazione GPU per materializzare il solo effetto KV
- **`ds4_session_eval_output_head_from_hc`** `ds4.c:57894`  
  Ignora tutte le righe hidden tranne l'ultima
- **`ds4_session_eval_probe_tp`** `ds4.c:60573`  
  Il controllo del fallimento del trasporto gate GPU esiste solo su Apple
- **`ds4_session_eval_speculative_argmax`** `ds4.c:64817`  
  Con sessione distribuita o CPU emette sempre un solo token e salta la speculazione.
- **`ds4_session_eval_splitkv_spec_after_first`** `ds4.c:51627`  
  Con commit prefix-1 la seconda riga rifiutata resta come spazzatura invisibile.
- **`ds4_session_free`** `ds4.c:57708`  
  Se il TP e gia fallito salta la distruzione remota
- **`ds4_session_glm_cap_dense_cache`** `ds4.c:48891`  
  Se manca full_kv_cache forza la lunghezza densa a zero.
- **`ds4_session_glm_note_dense_cache`** `ds4.c:48902`  
  Uno span che inizia dopo un buco viene ignorato senza errore.
- **`ds4_session_glm_reset_dense_cache`** `ds4.c:48887`  
  Nelle build senza GPU la funzione non esiste.
- **`ds4_session_glm_spec_cycle`** `ds4.c:57992`  
  Puo commettere due token e lasciare i logits sulla seconda posizione
- **`ds4_session_gpu_warmup`** `ds4.c:59783`  
  Ignora l'esito del warmup e fa no-op silenzioso su CPU o GLM
- **`ds4_session_greedy_splitkv_replay_exact`** `ds4.c:51272`  
  Con trust-replay salta i controlli degli argmax intermedi.
- **`ds4_session_invalidate`** `ds4.c:65539`  
  Ignora l'errore d'invio TP e invalida comunque lo stato locale.
- **`ds4_session_is_cpu`** `ds4.c:48851`  
  Una sessione o un engine nullo vale non-CPU.
- **`ds4_session_is_glm`** `ds4.c:48882`  
  Controlla la famiglia compilata, non backend o glm_graph_ready.
- **`ds4_session_layer_payload_bytes`** `ds4.c:48976`  
  Zero segnala indistintamente input invalido, backend CPU, overflow o slice GLM diversa.
- **`ds4_session_layer_slice_reset`** `ds4.c:57863`  
  Su CPU azzera la cache ma l'eval layer-slice resta non supportato
- **`ds4_session_load_layer_payload`** `ds4.c:49282`  
  Un errore durante il restore può lasciare cache parziali e checkpoint invalido.
- **`ds4_session_load_payload`** `ds4.c:50380`  
  Invalida il checkpoint prima delle copie; un errore può lasciare la sessione inutilizzabile.
- **`ds4_session_load_snapshot`** `ds4.c:51001`  
  Su Windows ricopia prima tutto lo snapshot in un file temporaneo.
- **`ds4_session_note_legacy_mtp_probe`** `ds4.c:59824`  
  Invalida la bozza anche quando il logging del probe e disattivato
- **`ds4_session_note_prefill_progress`** `ds4.c:58682`  
  Viene usata indirettamente come callback, pur senza chiamanti diretti
- **`ds4_session_payload_bytes`** `ds4.c:49903`  
  Per sessioni distribuite o checkpoint invalidi restituisce 0, come un payload vuoto.
- **`ds4_session_payload_file_free`** `ds4.c:49977`  
  Ignora l'errore di cancellazione e azzera comunque il descrittore.
- **`ds4_session_power`** `ds4.c:57764`  
  Con sessione o engine nullo restituisce 100
- **`ds4_session_prefill_cap`** `ds4.c:65577`  
  Una sessione NULL restituisce zero.
- **`ds4_session_prepare_dspark_draft`** `ds4.c:60366`  
  Un errore nel ripristino restituisce false anche dopo una proposta riuscita
- **`ds4_session_prepare_dspark_draft_impl`** `ds4.c:59871`  
  DS4_DSPARK_FAKE_ARGMAX_PROPOSAL puo fabbricare una bozza dai logits target
- **`ds4_session_prepare_legacy_mtp_draft`** `ds4.c:59841`  
  Il probe puo attivarlo anche quando mtp_draft_tokens vale uno
- **`ds4_session_prepare_support_draft`** `ds4.c:60386`  
  Con probe_mtp false non prepara nemmeno DSpark
- **`ds4_session_print_dspark_stats`** `ds4.c:57317`  
  Non stampa nulla senza env o attività; net_saved può essere negativo.
- **`ds4_session_report_progress`** `ds4.c:57858`  
  Sessione, callback o evento mancanti causano un no-op
- **`ds4_session_rewind`** `ds4.c:65554`  
  Invia al worker il pos non clampato, poi lo limita solo localmente.
- **`ds4_session_rewrite_from_common`** `ds4.c:59615`  
  Una sostituzione dietro la coda viva non muta nulla e chiede rebuild
- **`ds4_session_rewrite_requires_rebuild`** `ds4.c:59599`  
  Input invalido richiede rebuild invece di produrre un errore distinto
- **`ds4_session_sample`** `ds4.c:59700`  
  Non valida il puntatore di sessione
- **`ds4_session_save_layer_payload`** `ds4.c:49047`  
  La sincronizzazione GPU blocca; il backend CPU è rifiutato.
- **`ds4_session_save_payload`** `ds4.c:50071`  
  Sincronizza la GPU e salva solo le righe vive, non l'intera capacità delle cache.
- **`ds4_session_save_snapshot`** `ds4.c:50945`  
  Su Windows usa un file temporaneo anziché un flusso di memoria.
- **`ds4_session_set_cancel`** `ds4.c:57844`  
  Una callback nulla disabilita l'annullamento
- **`ds4_session_set_display_progress`** `ds4.c:57838`  
  E una callback distinta da quella di progresso logico
- **`ds4_session_set_logits`** `ds4.c:59770`  
  Rifiuta aggiornamenti parziali dei logits
- **`ds4_session_set_power`** `ds4.c:57773`  
  Modifica l'engine condiviso, quindi puo influire su altre sessioni
- **`ds4_session_slice_check_timeline`** `ds4.c:58142`  
  Un checkpoint invalido accetta soltanto pos0 uguale a zero
- **`ds4_session_slice_commit_timeline`** `ds4.c:58174`  
  Invalida sempre una bozza MTP pendente
- **`ds4_session_stage_payload`** `ds4.c:49986`  
  Il file resta sul disco finché il chiamante non libera il descrittore restituito.
- **`ds4_session_sync`** `ds4.c:58718`  
  Con DS4_GLM_KV_DUMP legge KV dalla GPU e li scrive su file
- **`ds4_session_sync_internal`** `ds4.c:58776`  
  DS4_GLM_PREFILL_TRUNC tronca davvero il prompt, non solo il dump
- **`ds4_session_token_logprob`** `ds4.c:59742`  
  Logits tutti non finiti producono zero senza valorizzare l'output
- **`ds4_session_token_watch_begin`** `ds4.c:57814`  
  Fuori da CUDA non fa nulla senza segnalarlo
- **`ds4_session_token_watch_end`** `ds4.c:57825`  
  Fuori da CUDA non fa nulla senza segnalarlo
- **`ds4_session_tokens`** `ds4.c:49774`  
  Restituisce un puntatore interno che diventa obsoleto quando cambia il checkpoint.
- **`ds4_session_top_logprobs`** `ds4.c:59705`  
  Restituisce k anche se meno di k logits sono finite
- **`ds4_session_tp_leader`** `ds4.c:57391`  
  Sessioni nulle, TP inattivo e rank non zero sono tutti indistinguibili come falso.
- **`ds4_session_tp_register`** `ds4.c:57395`  
  Sul non-leader ritorna successo senza fare nulla; evita esplicitamente l'ID zero.
- **`ds4_session_tp_spec_cycle`** `ds4.c:61897`  
  Il worker calcola la verifica ma obbedisce al commit del leader.
- **`ds4_session_vram_ledger_decode_start`** `ds4.c:57794`  
  Fuori da CUDA non fa nulla senza segnalarlo
- **`ds4_session_vram_ledger_request_end`** `ds4.c:57804`  
  Fuori da CUDA non fa nulla senza segnalarlo
- **`ds4_session_write_staged_payload`** `ds4.c:49948`  
  Copia solo payload->bytes; eventuali byte extra nel file temporaneo vengono ignorati.
- **`ds4_sessions_eval_batch`** `ds4.c:61386`  
  Con un solo elemento delega direttamente alla valutazione singola.
- **`ds4_sessions_eval_batch_cuda`** `ds4.c:64578`  
  Se il batch fallisce invalida tutti i checkpoint, anche quelli non ancora avanzati.
- **`ds4_sessions_eval_batch_metal`** `ds4.c:61018`  
  Su errore invalida ogni sessione del batch
- **`ds4_sessions_eval_batch_metal_supported`** `ds4.c:60625`  
  Dump o profiling Metal disabilitano il batching senza errore
- **`ds4_sessions_eval_batch_with_prefill`** `ds4.c:61460`  
  Se il percorso nativo non è supportato, sincronizza e valuta in serie senza avviso.
- **`ds4_sessions_eval_batch_with_prefill_cuda`** `ds4.c:64712`  
  Su CUDA prompt.len == ctx_size è rifiutato, benché il wrapper pubblico lo ammetta.
- **`ds4_sessions_eval_batch_with_prefill_metal`** `ds4.c:61188`  
  Un errore invalida sia il prefill sia tutte le sessioni decode.
- **`ds4_sessions_eval_batch_with_prefill_metal_supported`** `ds4.c:61138`  
  La sola presenza di dump o profiling forza il fallback.
- **`ds4_sessions_tp_batch_items`** `ds4.c:60972`  
  Un solo item invalido scarta l'intero batch costruito
- **`ds4_sessions_tp_recv_logits`** `ds4.c:60989`  
  Fuori dal leader TP con vocab split restituisce successo senza ricevere
- **`ds4_shape_matches_metadata`** `ds4.c:5455`  
  Richiede uguaglianza esatta di ogni campo, senza valori predefiniti o tolleranze.
- **`ds4_slow_token_note_read`** `ds4_cuda.cu:1023`  
  Anche EOF e letture fallite incrementano il numero di chiamate.
- **`ds4_ssd_auto_cache_percent`** `ds4_ssd.c:87`  
  Valori assenti, vuoti o invalidi usano 80; solo gli invalidi non vuoti avvisano.
- **`ds4_ssd_auto_cache_plan`** `ds4_ssd.c:115`  
  Forza almeno un esperto anche se il budget residuo e' zero.
- **`ds4_ssd_cache_experts_for_byte_budget`** `ds4_ssd.c:79`  
  Un quoziente oltre UINT32_MAX restituisce zero invece di saturare.
- **`ds4_ssd_memory_lock_acquire`** `ds4_ssd.c:144`  
  Un solo mlock o VirtualLock fallito annulla e libera anche i chunk gia' bloccati.
- **`ds4_ssd_memory_lock_release`** `ds4_ssd.c:240`  
  Con ptr NULL o bytes zero non libera nulla, anche se l'altro campo indica una risorsa.
- **`ds4_str_contains`** `ds4.c:1127`  
  Una needle vuota restituisce true.
- **`ds4_strdup`** `ds4.c:1189`  
  Passa dalla guardia globale delle allocazioni tramite xmalloc.
- **`ds4_streaming_cache_experts_for_byte_budget`** `ds4.c:4683`  
  Budget nullo o modello non misurabile restituiscono zero senza errore.
- **`ds4_streaming_cacheable_expert_count`** `ds4.c:4602`  
  I layer con quantizzazione outlier non entrano nel conteggio cacheabile.
- **`ds4_streaming_manual_cache_safe_bytes`** `ds4.c:4721`  
  Arrotonda in basso ai GiB ma forza almeno 1 GiB; nelle build senza GPU restituisce zero.
- **`ds4_streaming_prefill_headroom_bytes`** `ds4.c:4632`  
  Riserva interi layer con tutti gli esperti, non solo quelli instradati dal token.
- **`ds4_streaming_routed_expert_bytes`** `ds4.c:4563`  
  Ignora le classi outlier; a parità conserva la prima classe incontrata.
- **`ds4_telemetry_now_ns`** `ds4_cuda.cu:963`  
  Un tempo nullo o negativo diventa 0, usato altrove come sentinella disabilitata.
- **`ds4_tensor_device_idx`** `ds4_cuda.cu:2169`  
  Un tensore nullo o con device_id negativo viene attribuito al device zero.
- **`ds4_tensor_mtp_stage`** `ds4.c:2613`  
  Accetta anche un nome che termina subito dopo il punto seguente all'indice
- **`ds4_test_classify_multi_tier`** `ds4.c:55796`  
  Forza contesto zero e TP CUDA disattivato.
- **`ds4_test_classify_multi_tier_impl`** `ds4.c:55765`  
  Copia il placement solo se la classificazione riesce.
- **`ds4_test_classify_multi_tier_with_ctx`** `ds4.c:55808`  
  Forza TP CUDA disattivato.
- **`ds4_test_classify_multi_tier_with_ctx_cuda_tp`** `ds4.c:55821`  
  Forza TP CUDA attivato.
- **`ds4_test_clear_compress_ratios`** `ds4.c:55840`  
  Sovrascrive stato globale usato da altri test.
- **`ds4_test_compute_entry_bytes_sum`** `ds4.c:55896`  
  Forza prefill_chunk a zero.
- **`ds4_test_compute_entry_bytes_sum_with_prefill`** `ds4.c:55874`  
  Restituisce zero sia per errore sia per una somma realmente nulla.
- **`ds4_test_dspark_cache_window_crop`** `ds4.c:26156`  
  Non viene chiamato dal runtime.
- **`ds4_test_effective_prefill_chunk`** `ds4.c:55844`  
  Un valore richiesto zero può selezionare il default del planner.
- **`ds4_test_engine_placement`** `ds4.c:55923`  
  Restituisce un puntatore interno, non una copia.
- **`ds4_test_glm_per_layer_kv_bytes`** `ds4.c:55904`  
  Cambia temporaneamente g_ds4_shape: non è sicura tra thread.
- **`ds4_test_make_engine`** `ds4.c:55728`  
  Riconosce output e routed gate solo da nomi esatti.
- **`ds4_test_mixed_native_count`** `ds4.c:64707`  
  Esiste solo nelle build con DS4_TEST_HOOKS.
- **`ds4_test_per_tier_graph_overhead_bytes`** `ds4.c:55869`  
  Forza prefill_chunk a zero.
- **`ds4_test_sample_logits`** `ds4.c:37465`  
  Esiste solo nelle build con DS4_TEST_HOOKS.
- **`ds4_test_seed_compress_ratios`** `ds4.c:55834`  
  Sovrascrive stato globale usato da altri test.
- **`ds4_test_session_read_logits`** `ds4.c:55913`  
  Non consente letture parziali e accetta solo una copia di lunghezza esatta.
- **`ds4_test_tensor_to_entry`** `ds4.c:55720`  
  Un name_len negativo viene trasformato in zero.
- **`ds4_think_mode_enabled`** `ds4.c:47873`  
  Solo HIGH e MAX sono attivi; NONE e valori sconosciuti risultano falsi.
- **`ds4_think_mode_for_context`** `ds4.c:47894`  
  Un ctx_size nullo o negativo viene trattato come zero e forza il downgrade.
- **`ds4_think_mode_name`** `ds4.c:47877`  
  Un valore enum sconosciuto diventa la stringa unknown.
- **`ds4_threads_init`** `ds4.c:1876`  
  DS4_THREADS è letto solo al primo init e g_requested_threads lo sovrascrive.
- **`ds4_threads_shutdown`** `ds4.c:1913`  
  Dopo l'azzeramento una chiamata successiva può reinizializzare il pool.
- **`ds4_token_is_stop`** `ds4.c:37008`  
  Con engine nullo restituisce false.
- **`ds4_token_is_stop_for_think_mode`** `ds4.c:37020`  
  In modalita no-thinking un marker thinking viene scartato come stop.
- **`ds4_token_is_thinking_control`** `ds4.c:37012`  
  ID negativi o engine nullo non sono mai controlli thinking.
- **`ds4_token_text`** `ds4.c:36962`  
  Scarta silenziosamente i codepoint non mappati; il risultato allocato va liberato.
- **`ds4_tokenize_rendered_chat`** `ds4.c:36775`  
  Un testo NULL viene trattato come stringa vuota
- **`ds4_tokenize_text`** `ds4.c:36698`  
  Un testo NULL viene trattato come stringa vuota
- **`ds4_tokens_copy`** `ds4.c:35642`  
  Conserva la capacità già allocata nel destinatario
- **`ds4_tokens_free`** `ds4.c:35638`  
  Azzera anche lunghezza e capacità
- **`ds4_tokens_push`** `ds4.c:35634`  
  Può riallocare il buffer host
- **`ds4_tokens_starts_with`** `ds4.c:35647`  
  Il prefisso vuoto corrisponde sempre
- **`ds4_tp_adopt_distributed_options`** `ds4_tp.c:627`  
  Con tp NULL o requested falso restituisce successo.
- **`ds4_tp_attach_slab`** `ds4_tp.c:1603`  
  Non tocca base né tp.
- **`ds4_tp_batch_gate_exchange`** `ds4_tp.c:1684`  
  Restituisce zero senza I/O.
- **`ds4_tp_big_gate_exchange`** `ds4_tp.c:1755`  
  Restituisce zero senza leggere o scrivere i buffer.
- **`ds4_tp_command_free`** `ds4_tp.c:1963`  
  Azzera anche tipo e metadati.
- **`ds4_tp_create`** `ds4_tp.c:1521`  
  Scrive NULL in out se fornito, poi fallisce sempre.
- **`ds4_tp_enabled`** `ds4_tp.c:560`  
  Non verifica requested: basta role diverso da NONE.
- **`ds4_tp_failed`** `ds4_tp.c:1627`  
  Restituisce true anche con tp NULL.
- **`ds4_tp_free`** `ds4_tp.c:1614`  
  Non libera nulla.
- **`ds4_tp_gate_exchange`** `ds4_tp.c:1638`  
  Restituisce zero senza I/O.
- **`ds4_tp_hash_check`** `ds4_tp.c:2148`  
  Non confronta alcun hash e fallisce sempre.
- **`ds4_tp_is_rdma`** `ds4_tp.c:1625`  
  Ignora tp e restituisce sempre false.
- **`ds4_tp_mark_failed`** `ds4_tp.c:1630`  
  Non modifica alcuno stato.
- **`ds4_tp_parse_cli_arg`** `ds4_tp.c:576`  
  Non consuma l'argomento successivo prima di restituire errore.
- **`ds4_tp_peer_ctx`** `ds4_tp.c:1626`  
  Non ha chiamanti e ignora tp.
- **`ds4_tp_rank`** `ds4_tp.c:1624`  
  Ignora tp e restituisce sempre zero.
- **`ds4_tp_recv_command`** `ds4_tp.c:1993`  
  Modifica command prima di fallire.
- **`ds4_tp_recv_logits_half`** `ds4_tp.c:2111`  
  Non scrive nel buffer di destinazione.
- **`ds4_tp_recv_verify_commit`** `ds4_tp.c:2133`  
  Non scrive full_accept né replay_n.
- **`ds4_tp_send_command_ack`** `ds4_tp.c:1931`  
  Restituisce zero senza I/O.
- **`ds4_tp_send_eval`** `ds4_tp.c:1869`  
  Restituisce zero senza I/O.
- **`ds4_tp_send_eval_batch`** `ds4_tp.c:1886`  
  Restituisce zero senza leggere gli elementi.
- **`ds4_tp_send_invalidate`** `ds4_tp.c:1881`  
  Restituisce zero senza I/O.
- **`ds4_tp_send_logits_half`** `ds4_tp.c:2106`  
  Ignora buffer e conteggio.
- **`ds4_tp_send_mixed_batch`** `ds4_tp.c:1903`  
  Restituisce zero senza leggere prompt o elementi.
- **`ds4_tp_send_rewind`** `ds4_tp.c:1875`  
  Restituisce zero senza I/O.
- **`ds4_tp_send_session_create`** `ds4_tp.c:1852`  
  Restituisce zero senza I/O.
- **`ds4_tp_send_session_destroy`** `ds4_tp.c:1858`  
  Restituisce zero senza I/O.
- **`ds4_tp_send_stop`** `ds4_tp.c:1959`  
  Restituisce sempre zero.
- **`ds4_tp_send_sync`** `ds4_tp.c:1863`  
  Restituisce zero senza leggere i token.
- **`ds4_tp_send_verify`** `ds4_tp.c:2121`  
  Ignora tutti i draft.
- **`ds4_tp_send_verify_commit`** `ds4_tp.c:2127`  
  Restituisce zero senza I/O.
- **`ds4_tp_slab_batch_in_offset`** `ds4_tp.c:782`  
  Ignora layer.
- **`ds4_tp_slab_batch_out_offset`** `ds4_tp.c:777`  
  Ignora layer.
- **`ds4_tp_slab_bytes`** `ds4_tp.c:734`  
  Ignora le dimensioni e restituisce zero.
- **`ds4_tp_slab_gpu_flags_offset`** `ds4_tp.c:760`  
  Ignora tp.
- **`ds4_tp_slab_in_offset`** `ds4_tp.c:773`  
  Ignora layer e gate.
- **`ds4_tp_slab_out_offset`** `ds4_tp.c:769`  
  Ignora layer e gate.
- **`ds4_tp_usage`** `ds4_tp.c:564`  
  Non ha chiamanti nel grafo estratto.
- **`ds4_tp_validate_engine_options`** `ds4_tp.c:693`  
  Un opt NULL è considerato valido.
- **`ds4_tp_wait_command_ack`** `ds4_tp.c:1937`  
  Non legge il canale e fallisce sempre.
- **`ds4_tp_worker_run`** `ds4_tp.c:2236`  
  Restituisce sempre uno.
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
- **`ds4_vec_dot_iq2_xxs_f32`** `ds4.c:3870`  
  La prima chiamata inizializza una tabella globale tramite os_once
- **`ds4_vec_dot_iq2_xxs_pair_q8_K`** `ds4.c:4054`  
  Fuori da ARM NEON richiama due volte il kernel singolo invece di condividere il lavoro
- **`ds4_vec_dot_iq2_xxs_q8_K`** `ds4.c:3965`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q2_K_f32`** `ds4.c:3571`  
  Decodifica ogni elemento singolarmente, senza il percorso Q8_K più veloce
- **`ds4_vec_dot_q2_K_q8_K`** `ds4.c:3437`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q4_K_f32`** `ds4.c:3764`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q4_K_q8_K`** `ds4.c:3589`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q5_K_f32`** `ds4.c:3793`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q5_K_q8_K`** `ds4.c:3681`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q5_q6_K_f32`** `ds4.c:3859`  
  Un tipo diverso termina il processo invece di restituire un errore
- **`ds4_vec_dot_q5_q6_K_q8_K`** `ds4.c:9353`  
  Un tipo diverso termina il processo invece di restituire errore.
- **`ds4_vec_dot_q6_K_f32`** `ds4.c:3825`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q6_K_q8_K`** `ds4.c:3727`  
  Un resto non allineato viene ignorato senza errore
- **`ds4_vec_dot_q8_K_pair_q8_K`** `ds4.c:3929`  
  Su x86 non usa SIMD e percorre scalarmente entrambi i pesi
- **`ds4_vec_dot_q8_K_q8_K`** `ds4.c:3903`  
  Su x86 usa il ciclo scalare; il dot-product NEON esiste solo su ARM
- **`ds4_vlog`** `ds4.c:1739`  
  Non aggiunge newline e non forza il flush del flusso.
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
- **`ds4_web_create`** `ds4_web.c:1363`  
  Ignora la configurazione e restituisce sempre NULL
- **`ds4_web_free`** `ds4_web.c:1385`  
  Non esegue alcuna operazione
- **`ds4_web_google_search`** `ds4_web.c:1392`  
  Ignora web e query e restituisce sempre NULL
- **`ds4_web_visit_page`** `ds4_web.c:1413`  
  Ignora web e URL e restituisce sempre NULL
- **`ds4_worker_main`** `ds4.c:1834`  
  Anche un worker senza righe incrementa il contatore di completamento.
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
- **`dsml_attr`** `ds4_server.c:4886`  
  Cerca una sottostringa e non verifica il confine iniziale del nome attributo
- **`dsml_attr_is_string_true`** `ds4_server.c:6071`  
  Solo il valore minuscolo esatto true produce vero
- **`dsml_decode_scan_json_param`** `ds4_server.c:6094`  
  Una chiusura DSML parziale fuori stringa è già classificata strutturale
- **`dsml_decode_state_for_text`** `ds4_server.c:6124`  
  Dopo la prima chiusura tool_calls restituisce outside senza esaminare la coda
- **`dsml_decode_state_is_tool`** `ds4_server.c:6196`  
  Anche un valore enum sconosciuto diverso da outside risulta tool
- **`dsml_decode_state_uses_payload_sampling`** `ds4_server.c:6200`  
  Il JSON strutturale non usa il campionamento payload
- **`dsml_decode_tracker_init`** `ds4_server.c:6204`  
  Cancella senza liberare eventuale stato precedente
- **`dsml_decode_tracker_update`** `ds4_server.c:6214`  
  Dopo DONE ignora eventuali blocchi tool successivi
- **`dsml_entity_stream_safe_len`** `ds4_server.c:6355`  
  Protegge soltanto cinque entità nominate note
- **`dsml_find_tool_start`** `ds4_server.c:6040`  
  pos_out indica il byte dopo il marcatore, non il suo inizio
- **`dsml_find_tool_start_from`** `ds4_server.c:6058`  
  La posizione restituita è dopo il marcatore trovato
- **`dsml_max_tool_start_len`** `ds4_server.c:6031`  
  Ricalcola il massimo a ogni chiamata invece di conservarlo
- **`dsml_parse_leaf_param_json`** `ds4_server.c:4925`  
  Se manca l'attributo string il valore viene trattato come stringa
- **`dsml_parse_nested_params_object`** `ds4_server.c:4963`  
  Non consuma il tag di chiusura del parametro contenitore
- **`dsml_unescape_text`** `ds4_server.c:4859`  
  Entità numeriche e sconosciute restano invariate
- **`dspark_apply_markov_confidence_lazy_runtime`** `ds4.c:32387`  
  Se il kernel CUDA Markov fallisce, ripiega silenziosamente sul percorso CPU.
- **`dspark_apply_markov_greedy_probe`** `ds4.c:32268`  
  Modifica in place ogni riga di logits quando il bias Markov è attivo.
- **`dspark_argmax_f32`** `ds4.c:32115`  
  In caso di parità conserva il primo indice; un NaN iniziale resta imbattibile.
- **`dspark_bind_block`** `ds4.c:6876`  
  Le mancanze vengono accumulate e non interrompono questo binding.
- **`dspark_bind_tensor`** `ds4.c:6861`  
  Un tensore required mancante incrementa un contatore ma non termina qui.
- **`dspark_confident_prefix_len`** `ds4.c:32610`  
  Input nullo, lunghezza zero o soglia non positiva accettano l'intera lunghezza.
- **`dspark_dense_row_to_f32`** `ds4.c:32073`  
  Qualunque tipo diverso da F32, F16 o Q8_0 fallisce senza conversione.
- **`dspark_disable_fused_cpu_markov_argmax`** `ds4.c:32250`  
  Il valore è cached alla prima chiamata; stringa vuota e 0 non disabilitano.
- **`dspark_disable_reuse_confidence0_markov`** `ds4.c:32259`  
  Il valore è cached alla prima chiamata; stringa vuota e 0 non disabilitano.
- **`dspark_eval_confidence0_runtime`** `ds4.c:32556`  
  Legge soltanto la prima riga, anche se il blocco contiene più draft.
- **`dspark_eval_confidence_probe`** `ds4.c:32333`  
  Usa come token precedente la proposta della riga precedente.
- **`dspark_final_head_ready`** `ds4.c:31716`  
  La sorgente HC può essere uno scratch aliasato invece del buffer dedicato.
- **`dspark_layout_kind_name`** `ds4.c:5203`  
  Un enum sconosciuto produce la stringa unknown invece di fallire.
- **`dspark_markov_argmax_kernel`** `ds4_cuda.cu:14348`  
  Ogni passo rilegge l'intera matrice w2 e riduce con atomicMax su una chiave impacchettata.
- **`dspark_markov_bias_disabled`** `ds4.c:32241`  
  Il valore è cached alla prima chiamata; stringa vuota e 0 non disabilitano.
- **`dspark_markov_q8_0_argmax`** `ds4.c:32164`  
  Quantizza lo stato prima del confronto, quindi il risultato segue l'approssimazione Q8_0.
- **`dspark_markov_q8_0_argmax_worker`** `ds4.c:32139`  
  È invocata come callback di ds4_parallel_for, non tramite una chiamata diretta.
- **`dspark_stage0_batch_ready`** `ds4.c:30342`  
  Richiede scratch FFN e HC generici, riusati come output dello stadio 0.
- **`dspark_stage0_weights_ready`** `ds4.c:30283`  
  Accetta main_proj solo dense compatibile e main_norm solo F32.
- **`dspark_stage_block_ready`** `ds4.c:30761`  
  Richiede tipi routed-expert specifici, non solo dimensioni compatibili.
- **`dspark_stage_cache_ready`** `ds4.c:30484`  
  Basta una cache di stadio sottodimensionata per bocciare l'intero set.
- **`dspark_stage_input_ready`** `ds4.c:30461`  
  Richiede block_size+1 righe: una target e le righe draft.
- **`dspark_tensor_type_matches`** `ds4.c:5213`  
  La classe dense DSpark accetta F16, F32 o Q8_0, ma non Q4.
- **`dspark_validate_tensor_layout`** `ds4.c:5230`  
  Un tensore NULL viene ignorato; più difetti dello stesso tensore valgono un solo errore.
- **`dspark_weights_bind_optional`** `ds4.c:6907`  
  Gli stadi oltre il massimo aggiungono una sola mancanza complessiva.
- **`dspark_weights_note_metadata_error`** `ds4.c:5281`  
  Non termina il processo e con struttura NULL non registra nulla.
- **`dspark_weights_validate_block_layout`** `ds4.c:5320`  
  I tensori mancanti non incrementano invalid_tensors perché il validatore li ignora.
- **`dspark_weights_validate_layout`** `ds4.c:5409`  
  Con zero stadi ritorna senza registrare esplicitamente l'assenza di stadi.
- **`dspark_weights_validate_metadata`** `ds4.c:5289`  
  Accumula errori senza fallire; se manca la lista target ritorna subito.
- **`dsv4_e2m1fn_dequant_cpu`** `ds4.c:3329`  
  NaN diventa +6 e lo zero negativo perde il segno
- **`dsv4_e2m1fn_dequant_dev`** `rocm/ds4_rocm_norm_rope.cuh:345`  
  Satura a 6 e risolve i pareggi verso un indice pari.
- **`dsv4_e2m1fn_value_cpu`** `ds4.c:3322`  
  Maschera l'indice con 7, quindi valori fuori intervallo riciclano la tabella
- **`dsv4_e2m1fn_value_dev`** `rocm/ds4_rocm_norm_rope.cuh:332`  
  Maschera l'indice con 7, quindi valori fuori intervallo ricominciano da zero.
- **`dsv4_e4m3fn_dequant_cpu`** `ds4.c:3272`  
  NaN diventa +448 e lo zero negativo perde il segno
- **`dsv4_e4m3fn_dequant_dev`** `rocm/ds4_rocm_norm_rope.cuh:314`  
  Satura a 448 e risolve i pareggi verso un codice pari.
- **`dsv4_e4m3fn_value_cpu`** `ds4.c:3257`  
  Il codice 127 non è trattato come NaN e produrrebbe 480
- **`dsv4_e4m3fn_value_dev`** `rocm/ds4_rocm_norm_rope.cuh:307`  
  Non gestisce il segno né il codice 127.
- **`dsv4_fp4_act_quantize_row_inplace_cpu`** `ds4.c:3359`  
  L'output resta F32 dequantizzato, non una rappresentazione FP4 impacchettata
- **`dsv4_fp8_kv_quantize_row_inplace_cpu`** `ds4.c:3302`  
  La coda RoPE non viene modificata e l'output resta memorizzato in F32
- **`dsv4_indexer_qat_row_inplace_cpu`** `ds4.c:3383`  
  Termina il processo per qualunque larghezza diversa da 128
- **`dsv4_indexer_qat_rows_inplace_cpu`** `ds4.c:3389`  
  Con rows uguale a zero non fa nulla
- **`dsv4_qkv_rms_norm_rows_kernel`** `rocm/ds4_rocm_norm_rope.cuh:47`  
  blockIdx.y sceglie Q o KV; ogni altro piano termina senza scrivere.
- **`dsv4_qkv_rms_norm_rows_kv_rope_kernel`** `ds4_cuda.cu:9066`  
  Q viene soltanto normalizzato; il RoPE fuso è applicato esclusivamente a KV.
- **`dump_tokens`** `ds4.c:36903`  
  Scrive sempre su stdout.
- **`dump_tokens_fp`** `ds4.c:36887`  
  Gli ID fuori vocabolario compaiono nella lista ma non nel dettaglio testuale.
- **`editor_cancel_input_with_hint`** `ds4_agent.c:10278`  
  Ctrl+C da idle cancella il testo ma non esce: invita esplicitamente a usare Ctrl+D.
- **`editor_clear_prompt_region`** `ds4_agent.c:9868`  
  Oltre a cancellare righe azzera la contabilità di rendering interna di linenoise.
- **`editor_clear_row`** `ds4_agent.c:9863`  
  Azzera gli attributi dalla colonna uno solo fino a fine riga.
- **`editor_configure_scroll_region`** `ds4_agent.c:9983`  
  Imposta scroll_region prima del layout; se quest'ultimo fallisce il flag resta true.
- **`editor_csi_cursor`** `ds4_agent.c:9828`  
  Non limita coordinate zero o negative prima di inserirle nella sequenza ANSI.
- **`editor_filter_input_byte`** `ds4_agent.c:9613`  
  Una CPR completa viene scartata; un prefisso invalido viene riversato interamente come input.
- **`editor_flush_cpr_candidate`** `ds4_agent.c:9553`  
  Un candidato CPR incompleto o invalido diventa input utente letterale.
- **`editor_get_terminal_size`** `ds4_agent.c:9819`  
  Righe o colonne zero sono trattate come errore senza fallback interno.
- **`editor_hide`** `ds4_agent.c:10104`  
  Nel fallback risale di una sola riga se il prompt era sotto un output parziale.
- **`editor_linenoise_layout_changed`** `ds4_agent.c:9966`  
  Ritorna zero sia quando non usa scroll-region sia quando il ridimensionamento fallisce.
- **`editor_move_to_output_cursor`** `ds4_agent.c:9812`  
  Sale sempre di una riga e usa la colonna stimata, anche se Unicode l'ha resa imprecisa.
- **`editor_move_to_prompt_cursor`** `ds4_agent.c:9854`  
  Con coordinate non positive ricade all'inizio della riga prompt.
- **`editor_move_to_prompt_row`** `ds4_agent.c:9849`  
  Fuori scroll-region ritorna silenziosamente senza muovere il cursore.
- **`editor_note_output`** `ds4_agent.c:9685`  
  Le sequenze CSI sono saltate, ma ogni codepoint Unicode largo conta approssimativamente una colonna.
- **`editor_prompt_redraw_due`** `ds4_agent.c:10190`  
  Prima del primo redraw restituisce sempre true; non aggiorna da sé il timestamp.
- **`editor_query_cursor`** `ds4_agent.c:9776`  
  Durante otto poll da 5 ms legge anche tasti utente e li reinserisce solo dopo aver cercato la CPR.
- **`editor_queue_bytes`** `ds4_agent.c:9632`  
  Il tracker paste vede anche byte che il filtro CPR può poi scartare.
- **`editor_read_stdin`** `ds4_agent.c:9641`  
  Senza modalità non bloccante continua a leggere e può bloccare l'intero event loop.
- **`editor_redraw_visible_prompt`** `ds4_agent.c:10181`  
  Fuori scroll-region ritorna senza aggiornare neppure il timestamp del redraw.
- **`editor_replace_input`** `ds4_agent.c:9676`  
  Se il prompt è nascosto lo mostra prima di cancellare e inserire il nuovo testo.
- **`editor_restore_output_cursor`** `ds4_agent.c:9840`  
  Se non esiste un salvataggio salta direttamente a output_bottom, colonna uno.
- **`editor_restore_terminal_layout`** `ds4_agent.c:10014`  
  Alla chiusura cancella l'ultima riga e aggiunge sempre una nuova riga.
- **`editor_save_output_cursor`** `ds4_agent.c:9834`  
  Fuori scroll-region non fa nulla; usa le sequenze DEC legacy ESC 7.
- **`editor_scroll_output_up`** `ds4_agent.c:9890`  
  Lascia installato il nuovo margine e simula lo scroll scrivendo newline una per volta.
- **`editor_set_prompt_status`** `ds4_agent.c:10165`  
  Se l'editor non è attivo scarta l'aggiornamento; se è nascosto non lo mostra.
- **`editor_set_scroll_layout`** `ds4_agent.c:9898`  
  Può rifiutare lo shrink e limita le righe riservate tra 2 e rows-2.
- **`editor_set_scroll_margin`** `ds4_agent.c:9884`  
  Fissa sempre il margine superiore a riga uno e non conserva quello precedente.
- **`editor_show`** `ds4_agent.c:10123`  
  Nel fallback inserisce CRLF quando l'output è parziale e azzera sempre gli attributi SGR.
- **`editor_start`** `ds4_agent.c:10029`  
  Il fallimento di set_nonblock non fallisce l'avvio: salva -1 e continua.
- **`editor_stop`** `ds4_agent.c:10078`  
  Non ripristina la scroll-region: il chiamante deve invocare separatamente il restore del layout.
- **`editor_take_bare_escape`** `ds4_agent.c:9668`  
  Riconosce ESC solo se è l'unico byte ancora trattenuto nel buffer CPR.
- **`editor_take_queued_byte`** `ds4_agent.c:9654`  
  Rimuove la prima occorrenza ovunque tra i byte non letti, non necessariamente il prossimo byte.
- **`editor_track_bracketed_paste`** `ds4_agent.c:9577`  
  Finché manca ESC[201~ sospende il feed linenoise, quindi un marker perso può congelare l'input.
- **`editor_update_prompt`** `ds4_agent.c:10148`  
  Tronca silenziosamente a 159 byte e ritargetizza direttamente il puntatore di linenoise.
- **`editor_update_status`** `ds4_agent.c:10154`  
  Tronca a 4095 byte e omette lo stile iniziale quando il footer contiene newline.
- **`editor_write_async`** `ds4_agent.c:10223`  
  Con output continuo rinvia fino a 200 ms il redraw di prompt o stato cambiati.
- **`editor_write_scroll_output_preserve_prompt`** `ds4_agent.c:10200`  
  Usa synchronized output senza negoziare il supporto del terminale.
- **`editor_write_terminal_text`** `ds4_agent.c:9735`  
  Converte ogni LF anche se preceduto da CR, producendo in quel caso CRCRLF.
- **`editor_write_welcome_banner`** `ds4_agent.c:10332`  
  Forza sempre la visualizzazione del prompt dopo il banner.
- **`effective_think_mode`** `ds4_agent.c:793`  
  La dimensione del contesto può degradare silenziosamente il livello think richiesto.
- **`embed_prompt`** `ds4.c:35535`  
  Non controlla dimensione di out né validità degli ID.
- **`embed_q8_0_scale`** `rocm/ds4_rocm_common.cuh:19`  
  Assume sempre l'ordine little-endian dei due byte.
- **`embed_staged_rows_hc_kernel`** `ds4_cuda.cu:7143`  
  Ogni riga viene duplicata identica per tutti i canali HC
- **`embed_token_any`** `ds4.c:7008`  
  Qualunque tipo diverso da F16 e Q8_0 termina il processo.
- **`embed_token_f16`** `ds4.c:6964`  
  Assume righe contigue con stride pari a dim0.
- **`embed_token_hc_kernel`** `rocm/ds4_rocm_common.cuh:11`  
  Non riceve n_vocab: un token fuori range legge oltre i pesi
- **`embed_token_hc_q8_0_kernel`** `rocm/ds4_rocm_common.cuh:24`  
  Il kernel non controlla token né la capacità dei buffer.
- **`embed_token_q8_0`** `ds4.c:6982`  
  Calcola l'offset di riga usando blocchi completi anche per l'ultimo blocco parziale.
- **`embed_tokens_hc_kernel`** `rocm/ds4_rocm_common.cuh:65`  
  Token negativo o fuori vocabolario viene sostituito silenziosamente con 0
- **`embed_tokens_hc_q8_0_kernel`** `rocm/ds4_rocm_common.cuh:41`  
  Token negativi o fuori vocabolario diventano silenziosamente token 0.
- **`enableRawMode`** `linenoise.c:674`  
  LINENOISE_ASSUME_TTY dichiara raw mode senza modificare il terminale.
- **`enabled`** `src/cuda/vram_expert_cache.cpp:288`  
  Rilegge l'ambiente a ogni chiamata; un valore invalido avvisa una sola volta
- **`encode_chat_prompt`** `ds4.c:36660`  
  GLM senza reasoning emette comunque la coppia think aperta e chiusa
- **`engine_adjust_output_head_for_cuda_tp`** `ds4.c:55001`  
  Se nessun tier ha spazio non segnala errore e lascia il placement invariato.
- **`engine_append_device_cache_range`** `ds4.c:55264`  
  Rifiuta anche i tensor nulli prima di delegare.
- **`engine_append_device_cache_span`** `ds4.c:55237`  
  La capacità host parte da 64 e raddoppia; non trasferisce ancora alcun dato in VRAM.
- **`engine_classify_multi_tier`** `ds4.c:55142`  
  Un cfg NULL azzera il placement; lo scratch è sottratto a ogni GPU prima del packing.
- **`engine_compute_cuda_ep_placement`** `ds4.c:55051`  
  Impone almeno un layer per stage e può fallire pur con capacità totale sufficiente.
- **`engine_compute_entry_bytes`** `ds4.c:54850`  
  Se la stima contesto fallisce usa 128 MiB per layer; un ctx non impostato vale 4096.
- **`engine_cuda_tp_decode_requested`** `ds4.c:54907`  
  Una sola RTX o un numero dispari di GPU lo disattiva senza errore.
- **`engine_cuda_tp_ep_requested`** `ds4.c:54917`  
  Eredita il requisito di almeno due GPU pari; con una RTX è sempre falso.
- **`engine_cuda_tp_output_env_requested`** `ds4.c:54928`  
  Variabile assente o vuota abilita; solo il valore esatto 0 disabilita.
- **`engine_cuda_tp_output_shard_span`** `ds4.c:54941`  
  Restituisce 0 per tier non partecipante e -1 per configurazione invalida.
- **`engine_deepseek_routed_expert_tensor`** `ds4.c:54815`  
  Un layout non divisibile stampa errore ma ritorna false come un tensore non routed.
- **`engine_glm_layer_uses_full_indexer`** `ds4.c:47494`  
  I layer dense sono sempre completi; dal layer 6 lo e soltanto uno ogni quattro.
- **`engine_glm_per_layer_kv_bytes_planner`** `ds4.c:47502`  
  Esclude i layer MTP; usa F16 solo su Apple e F32 sulla RTX.
- **`engine_install_dspark_support_cache`** `ds4.c:55535`  
  Un override tier non valido è ignorato; un tensor non collocato fa fallire l'avvio.
- **`engine_install_gpu_placement`** `ds4.c:55693`  
  Stampa il layout prima dei controlli e rifiuta sempre qualunque CPU spill.
- **`engine_install_per_device_caches`** `ds4.c:55280`  
  I tensor su CPU sono saltati; il rifiuto del CPU spill avviene altrove.
- **`engine_per_layer_kv_bytes_planner`** `ds4.c:47518`  
  Usa sempre F32 anche su Apple, sovrastimando intenzionalmente.
- **`engine_per_tier_graph_overhead_bytes`** `ds4.c:47589`  
  Per GLM restituisce solo scratch_bytes; altrove addebita extra head-only a ogni tier.
- **`engine_planner_raw_cap`** `ds4.c:47454`  
  Con ctx_size non positivo restituisce uno; un override non valido viene ignorato.
- **`engine_print_layout`** `ds4.c:55471`  
  Ignora il fallimento del calcolo dei byte e può stampare valori incompleti.
- **`engine_reserve_cuda_ep_output_shards`** `ds4.c:54974`  
  Modifica i budget in-place prima di sapere se un tier successivo fallirà.
- **`enqueue`** `ds4_server.c:12387`  
  Durante lo shutdown rifiuta il job senza inserirlo.
- **`environment_seconds`** `src/cuda/route_worker.cpp:22`  
  Valori non validi fanno fallback con solo un messaggio su stderr; zero dipende da positive_only.
- **`errbuf_set`** `ds4_gpu_args.c:20`  
  Con out nullo o vuoto non segnala l'errore; tronca in silenzio.
- **`errbuf_setf`** `ds4_gpu_args.c:28`  
  Con out nullo o vuoto non segnala l'errore; vsnprintf può troncare.
- **`eval_auto_context_size`** `ds4_eval.c:2500`  
  Esegue al massimo tre iterazioni e può terminare con exit(2) se supera il cap.
- **`eval_case_is_compsec`** `ds4_eval.c:1404`  
  Il confronto della sorgente è esatto e sensibile alle maiuscole.
- **`eval_case_is_multiple_choice`** `ds4_eval.c:1400`  
  Basta una sola scelta non nulla per classificare il caso.
- **`eval_case_nchoices`** `ds4_eval.c:1394`  
  Si ferma al primo NULL e ignora eventuali scelte successive.
- **`eval_max_prompt_tokens`** `ds4_eval.c:2469`  
  Ritokenizza ogni caso e termina il processo se un prompt non viene allocato.
- **`eval_prefill_progress`** `ds4_eval.c:3672`  
  Ignora silenziosamente tutti gli eventi salvo prefill_chunk e prefill_display.
- **`eval_sleep_ms`** `ds4_eval.c:1455`  
  La durata reale può superare quella richiesta.
- **`eval_status_running`** `ds4_eval.c:1809`  
  Considera attivi solo PREFILL e THINKING.
- **`eval_system_prompt`** `ds4_eval.c:2425`  
  Il testo è fisso, in inglese e condiviso da tutti i casi.
- **`eval_warn_context_budget`** `ds4_eval.c:2546`  
  Segnala il problema ma non ridimensiona contesto o token.
- **`eval_warn_think_max_downgraded`** `ds4_eval.c:2535`  
  Non modifica la modalità: emette soltanto un warning.
- **`exact_one`** `src/cuda/vram_expert_cache.cpp:18`  
  Valori come true, 01 o spazi attorno a 1 risultano falsi.
- **`expert_sidecar_apply_window`** `ds4.c:6257`  
  Non ricontrolla tipo, forma o identità del sidecar.
- **`expert_sidecar_identity_compare_tensor`** `ds4.c:6095`  
  Confronta l'intero tensore byte per byte prima di aggiornare l'hash.
- **`expert_sidecar_mixed_mode`** `ds4.c:6039`  
  Qualunque valore diverso da 0 o 1 termina il processo.
- **`expert_sidecar_validate_checkpoint_identity`** `ds4.c:6129`  
  Non confronta i pesi esperti; il router è verificato solo quando richiesto.
- **`expert_sidecar_window`** `ds4.c:6048`  
  Se manca un solo estremo usa rispettivamente 0 o l'ultimo layer.
- **`extractor_self_test_case`** `ds4_eval.c:3394`  
  Non può collaudare un'estrazione volutamente diversa dalla risposta corretta.
- **`f16_round_inplace_cpu`** `ds4.c:3253`  
  Il buffer resta F32, ma i valori originali sono sostituiti da quelli rappresentabili in F16
- **`f32_to_f16`** `ds4.c:3215`  
  Canonicalizza i NaN e trasforma gli overflow finiti in infinito
- **`f32_to_f16_bits_hip_round`** `rocm/ds4_rocm_common.cuh:372`  
  NaN diventa infinito e i pareggi non usano round-to-nearest-even.
- **`f32_to_f16_kernel`** `rocm/ds4_rocm_common.cuh:345`  
  Overflow e valori fini fuori gamma diventano half inf; la conversione perde precisione.
- **`final_response`** `ds4_server.c:7543`  
  reasoning_content compare solo nel ramo chat.
- **`finalize`** `src/cuda/prefill_observer.cu:490`  
  Se il flag viene tolto dopo request_begin, ritorna true senza ritirare i readback.
- **`find_answer_letter`** `ds4_eval.c:2823`  
  Esamina solo 96 byte dal marker, poi ripiega sull'ultima lettera isolata.
- **`find_any_tool_end`** `ds4_server.c:4804`  
  Riconosce anche il singolare </tool_call>
- **`find_any_tool_start`** `ds4_server.c:4790`  
  Riconosce solo marcatori completi, non prefissi ricevuti a metà
- **`find_case_answer`** `ds4_eval.c:3044`  
  Con dstlen uno la scelta multipla non può ricevere il terminatore NUL.
- **`find_compsec_answer`** `ds4_eval.c:2976`  
  Se la normalizzazione fallisce ripiega sull'estrattore di un singolo intero.
- **`find_cpr_reply`** `ds4_agent.c:9748`  
  Restituisce la prima forma sintattica valida senza verificare range o overflow di riga e colonna.
- **`find_eval_case_by_source_id`** `ds4_eval.c:3234`  
  Il confronto è esatto e sensibile alle maiuscole.
- **`find_integer_answer`** `ds4_eval.c:2896`  
  Con uguaglianze prende il primo intero dopo l'ultimo uguale, non l'ultimo della riga.
- **`find_last_answer_marker`** `ds4_eval.c:2749`  
  Senza marcatore stretto ripiega sulla prima occorrenza libera di answer.
- **`find_last_substr`** `ds4_server.c:4844`  
  Considera anche occorrenze sovrapposte perché avanza di un solo byte
- **`find_lit_bounded`** `ds4_server.c:5961`  
  Un letterale vuoto restituisce s anche se n è zero
- **`find_next_dsml_tool_block`** `ds4_server.c:9160`  
  Ignora in silenzio un blocco aperto ma privo del terminatore.
- **`foldCountLines`** `linenoise.c:1085`  
  Anche un intervallo vuoto conta come una riga.
- **`foldSetRenderedText`** `linenoise.c:1110`  
  Per una riga mostra byte nascosti come pasted chars, non grafemi.
- **`format_gpu_layout_line`** `ds4_gpu_args.c:198`  
  Un ritorno positivo non garantisce la riga completa: i buffer corti vengono troncati.
- **`format_run_elapsed`** `ds4_eval.c:1328`  
  Tronca i secondi e non limita il numero di ore.
- **`format_short_count`** `ds4_eval.c:2297`  
  Arrotonda: 999999 può essere mostrato come 1000k.
- **`forward_first_token_cpu`** `ds4.c:14243`  
  Non produce logits e ignora ogni cronologia KV.
- **`forward_glm_first_token_cpu`** `ds4.c:15090`  
  Non esegue i layer MTP finali.
- **`forward_glm_first_token_cpu_f32_ref`** `ds4.c:14953`  
  Esclude gli ultimi DS4_N_NEXTN_PREDICT layer dal forward.
- **`forward_token_raw_swa_cpu`** `ds4.c:14001`  
  Alloca e libera l'intero scratch a ogni chiamata.
- **`forward_token_raw_swa_cpu_decode_scratch`** `ds4.c:13966`  
  Con logits NULL esegue tutto il forward ma salta la testa di uscita.
- **`fp8_kv_quantize_kernel`** `rocm/ds4_rocm_fp8_kv.cuh:7`  
  Il tensore resta float32: emula l'errore FP8 senza compattare i dati.
- **`fp8_kv_quantize_row`** `ds4_cuda.cu:9439`  
  Lascia intatta la coda RoPE e conserva float dequantizzati, non byte FP8.
- **`fp8_kv_quantize_store_rows_kernel`** `ds4_cuda.cu:9476`  
  Nel raw cache salva float32 arrotondati a FP16, non byte FP8.
- **`freeCompletions`** `linenoise.c:820`  
  Non azzera puntatori né lunghezza dopo la liberazione.
- **`freeHistory`** `linenoise.c:2639`  
  Non azzera history né history_len, lasciando puntatori pendenti.
- **`g130_u1_peer_is_ipv4_loopback`** `ds4_server.c:155`  
  Rifiuta il loopback IPv6 e gli indirizzi IPv4 mappati in IPv6
- **`g130_u1_shutdown_body_matches`** `ds4_server.c:136`  
  Spazi, campi extra o diversa formattazione JSON fanno fallire il confronto
- **`g130_u1_shutdown_token`** `ds4_server.c:126`  
  Rifiuta lettere esadecimali maiuscole e restituisce memoria posseduta dall'ambiente
- **`generate_glm_metal_argmax`** `ds4.c:46944`  
  La crescita cache col headroom esiste solo su ROCm; CUDA ignora quei byte.
- **`generate_glm_metal_first_token`** `ds4.c:46890`  
  Anche con n_predict maggiore di uno emette al massimo un token e termina con successo.
- **`generate_job`** `ds4_server.c:11208`  
  Nel batching disabilita MTP; il recupero tool malformato ritenta solo non streaming.
- **`generate_metal_graph_raw_swa`** `ds4.c:47143`  
  Per GLM rifiuta power, prefill_chunk e directional steering invece di ignorarli.
- **`generate_raw_swa_cpu`** `ds4.c:37509`  
  Ignora il callback progress e campiona sempre con argmax.
- **`generation_done`** `ds4_cli.c:496`  
  Aggiunge sempre una newline se l'ultimo output non la contiene.
- **`getColumns`** `linenoise.c:766`  
  LINENOISE_COLS passa da atoi senza validazione; un valore invalido produce zero.
- **`getCursorPosition`** `linenoise.c:742`  
  Può bloccarsi aspettando la risposta e tronca oltre 31 byte.
- **`glm4_char_at`** `ds4.c:36288`  
  Un non ASCII non classificato come spazio, numero o simbolo diventa lettera
- **`glm4_unicode_number`** `ds4.c:36216`  
  Non riconosce tutte le categorie numeriche Unicode
- **`glm4_unicode_punct_symbol`** `ds4.c:36241`  
  Intervalli molto ampi classificano anche pittogrammi come simboli
- **`glm4_unicode_whitespace`** `ds4.c:36203`  
  La lista è codificata a mano e non segue automaticamente Unicode
- **`glm_add_rms_norm_weight_kernel`** `ds4_cuda.cu:29527`  
  Gestisce una sola riga: un batch va spezzato dal chiamante.
- **`glm_attention_decode_lora_staged_kernel`** `ds4_cuda.cu:30260`  
  Con RANGE_TOK2 ignora selected e usa le righe dense da zero.
- **`glm_attention_decode_value_staged_kernel`** `ds4_cuda.cu:30297`  
  Assume righe Q8_0 da 34 byte per 32 colonne senza verificarne il formato.
- **`glm_attention_decode_weights_staged_kernel`** `ds4_cuda.cu:30147`  
  Con RANGE_TOK2 ignora selected e usa le righe dense da zero.
- **`glm_attention_full_kernel`** `rocm/ds4_rocm_glm.cuh:582`  
  Usa un buffer score proporzionale a cache_len per ogni blocco
- **`glm_attention_indexed_decode_kernel`** `ds4_cuda.cu:30345`  
  Con RANGE_TOK2 ignora selected e usa una finestra densa crescente.
- **`glm_attention_indexed_decode_split_group8_partial_valid_kernel`** `rocm/ds4_rocm_glm.cuh:1025`  
  Converte sempre le cache come FP16 e non verifica gli indici selected
- **`glm_attention_indexed_decode_split_partial_kernel`** `rocm/ds4_rocm_glm.cuh:892`  
  Con selected_rows_valid vero salta ogni controllo degli indici di cache
- **`glm_attention_indexed_decode_split_reduce_kernel`** `rocm/ds4_rocm_glm.cuh:1190`  
  Se tutti i blocchi sono vuoti produce teste nulle senza errore
- **`glm_attention_indexed_lora_causal_gemm`** `rocm/ds4_rocm_glm.cuh:2612`  
  Restituisce zero su inapplicabilità o errore e il chiamante ricade sul kernel scalare
- **`glm_attention_indexed_lora_kernel`** `rocm/ds4_rocm_glm.cuh:773`  
  Se nessuna riga è valida scrive un vettore di zeri e segnala comunque successo
- **`glm_attention_indexed_lora_launch`** `rocm/ds4_rocm_glm.cuh:3178`  
  Le GEMM sono attive di default; env uguale a 0 o un errore causano fallback scalare silenzioso
- **`glm_attention_indexed_lora_selected_gemm`** `rocm/ds4_rocm_glm.cuh:2828`  
  Lo scratch può arrivare a centinaia di MiB; un fallimento attiva il fallback scalare
- **`glm_attention_lora_causal_kernel`** `ds4_cuda.cu:29779`  
  Le righe fuori cache vengono ignorate; se lo sono tutte produce un output zero.
- **`glm_build_kv_cache_kernel`** `rocm/ds4_rocm_glm.cuh:530`  
  La parte K non RoPE arriva già proiettata, mentre solo la coda viene ruotata qui
- **`glm_cache_rope_pair_f16_dev`** `ds4_cuda.cu:29759`  
  Usa row sia per indirizzare la cache sia come posizione RoPE.
- **`glm_causal_gemm_cache_to_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2071`  
  Anche una cache già FP16 passa da float e viene riscritta in FP16
- **`glm_causal_gemm_gather_head_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2116`  
  Un solo lancio scrive due buffer di dimensioni diverse con la stessa griglia
- **`glm_causal_gemm_rope_to_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2080`  
  La posizione RoPE coincide implicitamente con l'indice della riga cache
- **`glm_causal_gemm_scratch_part`** `rocm/ds4_rocm_glm.cuh:2467`  
  Aggiunge fino a 255 byte di padding prima di ogni sezione
- **`glm_causal_gemm_softmax_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2149`  
  Sovrascrive scores prima con valori scalati e poi con esponenziali non normalizzati
- **`glm_debug_dump_hidden_row`** `ds4.c:34855`  
  Apre sempre con wb: ogni chiamata sovrascrive il dump precedente.
- **`glm_debug_dump_prefill_logits`** `ds4.c:34932`  
  Dopo il primo dump riuscito ignora per sempre le chiamate successive nel processo.
- **`glm_debug_dump_raw_layer`** `ds4.c:34887`  
  Se pos è negativo omette il suffisso token e può sovrascrivere lo stesso file.
- **`glm_debug_hidden_dump_layer`** `ds4.c:34875`  
  La stringa all vale -2; variabile assente o vuota vale -1.
- **`glm_debug_hidden_dump_layer_match`** `ds4.c:34882`  
  Il valore speciale -2 fa corrispondere qualunque layer.
- **`glm_decode_ablate_mask`** `ds4.c:40352`  
  Legge DS4_GLM_DECODE_ABLATE una sola volta e gli stadi saltati lasciano output obsoleto.
- **`glm_embed_token_q8_0_kernel`** `ds4_cuda.cu:29597`  
  Interpreta ogni blocco come 2 byte FP16 più 32 int8, senza metadati di tipo.
- **`glm_embed_tokens_q8_0_kernel`** `ds4_cuda.cu:29645`  
  Un ID negativo o fuori range provoca una lettura pesi fuori bounds.
- **`glm_fill_selected_range_batch_kernel`** `rocm/ds4_rocm_glm.cuh:653`  
  Le posizioni future ricevono pad_row, non un indice negativo.
- **`glm_graph_alloc`** `ds4.c:39661`  
  Richiede sempre embedding token e output head completi.
- **`glm_graph_alloc_slice`** `ds4.c:39358`  
  Azzera tutto il grafo preservando soltanto placement; un errore libera anche il già allocato.
- **`glm_graph_begin_commands_if_needed`** `ds4.c:45694`  
  Se i comandi sono gia attivi restituisce true senza aprirne altri.
- **`glm_graph_bytes_to_gib`** `ds4.c:37770`  
  Usa GiB binari, non GB decimali.
- **`glm_graph_capture_prefill_seed_router_selected`** `ds4.c:41450`  
  Cattura gli ultimi K token del batch, non i primi.
- **`glm_graph_compact_cache_bytes_for_cap`** `ds4.c:35008`  
  Le moltiplicazioni non sono saturanti e possono traboccare.
- **`glm_graph_compact_cache_elem_bytes`** `ds4.c:34799`  
  Il formato è deciso a compile-time.
- **`glm_graph_compact_cache_initial_cap`** `ds4.c:34996`  
  Per ogni ctx non nullo restituisce sempre ctx: full_attention_cap non limita il risultato.
- **`glm_graph_compact_cache_is_f16`** `ds4.c:34803`  
  Il risultato è deciso a compile-time, non a runtime.
- **`glm_graph_context_memory_estimate_for_compact_cap`** `ds4.c:35229`  
  Con zero layer normali restituisce una stima tutta a zero.
- **`glm_graph_context_memory_estimate_for_compact_cap_slice`** `ds4.c:35179`  
  Lo scratch è globale e completo anche per una fetta: sommare stime di fette lo duplica.
- **`glm_graph_context_request`** `ds4.c:38407`  
  Rifiuta l'intera richiesta anziché ridurre il contesto al massimo.
- **`glm_graph_decode_updates_dense_cache`** `ds4.c:41051`  
  Richiedere logits può selezionare l'indicizzato e quindi saltare l'aggiornamento denso.
- **`glm_graph_decode_uses_indexed_attention`** `ds4.c:41041`  
  Un logits_out non nullo forza l'indicizzato anche entro ctx_cap, salvo override di disabilitazione.
- **`glm_graph_dense_tensor_layout`** `ds4.c:38463`  
  Non richiede un tipo quantizzato preciso, solo uno della famiglia densa GLM.
- **`glm_graph_disable_add3_residual`** `ds4.c:42026`  
  Restituisce sempre false, quindi il residuale add3 non viene mai disabilitato.
- **`glm_graph_disable_indexed_decode`** `ds4.c:41037`  
  Restituisce sempre false.
- **`glm_graph_down_type_supported`** `ds4.c:14719`  
  Accetta Q6_K per down, che non è ammesso nella coppia gate/up.
- **`glm_graph_encode_ffn_batch`** `ds4.c:42030`  
  Sui piccoli batch una maschera diagnostica puo saltare il MoE routed lasciando attivo il gate.
- **`glm_graph_encode_ffn_one_from`** `ds4.c:40941`  
  Un errore di normalizzazione impedisce ogni calcolo FFN successivo.
- **`glm_graph_encode_ffn_one_normed_from`** `ds4.c:40799`  
  Se la fusione Q8 gate/up fallisce, ripiega silenziosamente sui kernel separati.
- **`glm_graph_encode_output_head`** `ds4.c:39810`  
  È solo un wrapper e non apre né chiude un batch di comandi.
- **`glm_graph_encode_output_head_from`** `ds4.c:39788`  
  Usa il percorso matmul decode anche quando viene chiamata dopo un prefill batch.
- **`glm_graph_encode_shared_swiglu_one`** `ds4.c:40374`  
  Il percorso Q8 fuso evita i kernel e i profili separati di gate e up.
- **`glm_graph_encode_sparse_ffn_indexed_batch_routed_moe`** `ds4.c:41660`  
  Se il kernel shared batch non riesce, ripiega silenziosamente sul ciclo per token.
- **`glm_graph_encode_sparse_ffn_one`** `ds4.c:40458`  
  Le ablation routed/shared lasciano buffer obsoleti ma il flusso può continuare.
- **`glm_graph_end_commands_if_active`** `ds4.c:45698`  
  Se non esistono comandi attivi restituisce comunque true.
- **`glm_graph_ensure_compact_cache`** `ds4.c:39275`  
  Con cache compatta assente accetta solo richieste entro ctx_cap.
- **`glm_graph_env_disabled`** `ds4.c:37778`  
  Qualsiasi altro valore non vuoto, anche non valido, non disabilita.
- **`glm_graph_env_double`** `ds4.c:37787`  
  Accetta anche suffissi spuri dopo un prefisso numerico valido.
- **`glm_graph_env_present`** `ds4.c:438`  
  Una variabile definita ma vuota conta come presente.
- **`glm_graph_env_truthy`** `ds4.c:38321`  
  Spazi, yes e valori sconosciuti sono tutti considerati veri.
- **`glm_graph_env_value`** `ds4.c:447`  
  Una variabile ROCm vuota ricade in silenzio sul nome Metal.
- **`glm_graph_expanded_kv_cache_enabled`** `ds4.c:34807`  
  Ignora ssd_streaming e restituisce sempre false.
- **`glm_graph_flash_attention_prefill_enabled`** `ds4.c:41012`  
  La sola presenza di DS4_GLM_DISABLE_FLASH_PREFILL la disabilita.
- **`glm_graph_flash_attention_prefill_min_tokens`** `ds4.c:41016`  
  La soglia è fissa a 24 token.
- **`glm_graph_force_indexed_decode`** `ds4.c:41033`  
  Restituisce sempre false.
- **`glm_graph_forward_indexed_tokens`** `ds4.c:44079`  
  Un chunk che attraversa la soglia top-k viene rifiutato e va spezzato dal chiamante.
- **`glm_graph_forward_output_head`** `ds4.c:39817`  
  Il readback impone un confine comandi; il dump hidden scatta quando il layer debug è negativo.
- **`glm_graph_forward_token`** `ds4.c:45714`  
  Con defer_completion non chiude i comandi e non legge hidden o logits su host.
- **`glm_graph_forward_tokens`** `ds4.c:43175`  
  Rifiuta span oltre full-attention; non passa da solo al percorso indicizzato.
- **`glm_graph_free`** `ds4.c:39177`  
  Azzera anche configurazione e placement, non solo le risorse allocate.
- **`glm_graph_full_attention_cap`** `ds4.c:38196`  
  Con ctx_size zero conserva il cap predefinito invece di azzerarlo.
- **`glm_graph_full_indexer_layer_count_range`** `ds4.c:34824`  
  layer_end è incluso; un intervallo inverso restituisce zero.
- **`glm_graph_full_kv_cache_elem_bytes`** `ds4.c:34834`  
  Restituisce sempre due byte, indipendentemente dalla configurazione.
- **`glm_graph_full_prefill_drain_interval`** `ds4.c:34972`  
  Restituisce sempre 16.
- **`glm_graph_full_prefill_layer_flush_interval`** `ds4.c:38210`  
  Passaggi piccoli con logits restituiscono zero per evitare un flush per layer.
- **`glm_graph_full_prefill_trace_all`** `ds4.c:34964`  
  È hardcoded a false.
- **`glm_graph_full_prefill_trace_enabled`** `ds4.c:34960`  
  È hardcoded a false.
- **`glm_graph_full_prefill_trace_slow_ms`** `ds4.c:34968`  
  La soglia fissa di 100 ms resta inutilizzata finché il tracing è spento.
- **`glm_graph_full_prefill_tracef`** `ds4.c:34976`  
  Non gira nel percorso corrente perché il tracing è hardcoded a false.
- **`glm_graph_gate_pair_type_supported`** `ds4.c:14711`  
  Richiede gate e up dello stesso tipo.
- **`glm_graph_host_memory_bytes`** `ds4.c:37803`  
  Un errore sysctl e ogni piattaforma non-Apple producono lo stesso zero.
- **`glm_graph_indexed_decode_split_block_rows_for`** `ds4.c:38284`  
  Passa bruscamente da 32 a 128 righe oltre 1024 selezioni.
- **`glm_graph_indexed_decode_split_blocks`** `ds4.c:38278`  
  Usa il top-k massimo, non il numero effettivo di elementi selezionati.
- **`glm_graph_indexed_decode_split_group8_available`** `ds4.c:38288`  
  Richiede cache compatta f16 e piu di 512 selezioni oltre a dimensioni esatte.
- **`glm_graph_indexed_decode_split_min_block_rows`** `ds4.c:38274`  
  Il valore e fisso e non dipende dall'hardware.
- **`glm_graph_indexed_prefill_attention_boundary`** `ds4.c:38308`  
  Su ROCm restituisce true senza eseguire alcun flush.
- **`glm_graph_indexed_prefill_batch_attn_kernel`** `ds4.c:41078`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_attn_slice_tokens`** `ds4.c:41082`  
  La slice è fissa a 2048 token.
- **`glm_graph_indexed_prefill_batch_available`** `ds4.c:38352`  
  Un'allocazione parziale produce solo false, senza diagnostica.
- **`glm_graph_indexed_prefill_batch_f32_rows`** `ds4.c:41110`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_ffn`** `ds4.c:41090`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_ffn_norm`** `ds4.c:41094`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_indexer`** `ds4.c:41066`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_q8_rows`** `ds4.c:41114`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_qk_low`** `ds4.c:41074`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_ready`** `ds4.c:38366`  
  Senza full KV è pronto anche dalla posizione zero.
- **`glm_graph_indexed_prefill_batch_residual`** `ds4.c:41106`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_routed_moe`** `ds4.c:41098`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_router_select`** `ds4.c:41102`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_batch_shared_expert`** `ds4.c:41118`  
  Restituisce sempre true.
- **`glm_graph_indexed_prefill_chunk_tokens`** `ds4.c:38384`  
  Ignora full_attention_cap e forza almeno un token.
- **`glm_graph_indexed_prefill_drain_interval`** `ds4.c:34956`  
  Restituisce sempre 16.
- **`glm_graph_indexed_prefill_grouped_moe_default`** `ds4.c:41385`  
  La modalità quality disabilita il MoE raggruppato.
- **`glm_graph_indexed_prefill_scalar_attn`** `ds4.c:41070`  
  Restituisce sempre false.
- **`glm_graph_indexed_prefill_scalar_indexer`** `ds4.c:41062`  
  Restituisce sempre false.
- **`glm_graph_indexed_prefill_scalar_kernels`** `ds4.c:41058`  
  Restituisce sempre false.
- **`glm_graph_indexed_prefill_score_tokens`** `ds4.c:38394`  
  Con capacità abilitate assegna almeno una riga anche se il budget non basta.
- **`glm_graph_indexed_prefill_trace_all`** `ds4.c:34948`  
  È hardcoded a false.
- **`glm_graph_indexed_prefill_trace_enabled`** `ds4.c:34944`  
  È hardcoded a false.
- **`glm_graph_indexed_prefill_trace_slow_ms`** `ds4.c:34952`  
  La soglia fissa di 100 ms resta inutilizzata finché il tracing è spento.
- **`glm_graph_indexed_prefill_tracef`** `ds4.c:34986`  
  Non gira nel percorso corrente perché il tracing è hardcoded a false.
- **`glm_graph_indexed_scratch_bytes_for_cap`** `ds4.c:35027`  
  Le somme e moltiplicazioni non sono saturanti.
- **`glm_graph_indexer_qat`** `ds4.c:41086`  
  Restituisce sempre false.
- **`glm_graph_indexer_top_k_limit`** `ds4.c:34838`  
  Il limite è fissato a compile-time.
- **`glm_graph_layer_uses_full_indexer`** `ds4.c:34812`  
  Include tutti i leading dense, poi i layer 6, 10, 14 e così via.
- **`glm_graph_layer_uses_generic_routed_moe`** `ds4.c:38476`  
  Non controlla i tipi dei tensori up e down.
- **`glm_graph_limit_indexed_prefill_chunk`** `ds4.c:38373`  
  Limita solo il chunk che attraversa top-k; oltre la soglia non applica limiti.
- **`glm_graph_log_full_attention_limit`** `ds4.c:38435`  
  Scrive sempre su stderr; non verifica autonomamente che il limite sia superato.
- **`glm_graph_matmul_f32_rows_scalar`** `ds4.c:41243`  
  Con il batch abilitato, un errore non attiva il fallback riga per riga.
- **`glm_graph_matmul_q8_0_decode_profiled_tensor`** `ds4.c:39747`  
  Il profiling è codice morto perché il relativo helper restituisce sempre false.
- **`glm_graph_matmul_q8_0_decode_tensor`** `ds4.c:39690`  
  Il nome Q8_0 è fuorviante: usa il tipo trovato nei metadati, che può essere diverso.
- **`glm_graph_matmul_q8_0_rows_scalar`** `ds4.c:41190`  
  Il fallimento del kernel batch causa un fallback scalare silenzioso e molto più lento.
- **`glm_graph_matmul_q8_0_tensor`** `ds4.c:41122`  
  Una coda fino a 16 righe viene separata per mantenere allineato il blocco TensorOps.
- **`glm_graph_maybe_warm_compact_indexer_after_prefill`** `ds4.c:45679`  
  Prima di ctx_cap e da ctx_size in poi restituisce successo senza fare nulla.
- **`glm_graph_memory_guard`** `ds4.c:38088`  
  Include sempre embedding e testa di output nella stima.
- **`glm_graph_memory_guard_default_reserve_gib`** `ds4.c:37910`  
  La riserva scende da 32 a 24 GiB solo nel caso base 480-640 GiB quasi saturo.
- **`glm_graph_memory_guard_for_compact_cap`** `ds4.c:37923`  
  Con guardia disabilitata, modello nullo o budget ignoto autorizza silenziosamente.
- **`glm_graph_memory_guard_slice`** `ds4.c:38138`  
  La stima dei pesi usa gli span della slice, non l'intero file modello.
- **`glm_graph_memory_guard_slice_with_transient`** `ds4.c:38166`  
  Puo rifiutare una slice valida solo per il picco transient dichiarato.
- **`glm_graph_memory_guard_with_transient`** `ds4.c:38112`  
  La somma dei byte satura a UINT64_MAX.
- **`glm_graph_model_bytes_for_guard`** `ds4.c:37863`  
  Un valore globale TP non nullo prevale anche sulle richieste di slice.
- **`glm_graph_model_context_limit`** `ds4.c:37765`  
  Satura a UINT32_MAX se il contesto RoPE e maggiore.
- **`glm_graph_mtp_ensure`** `ds4.c:42473`  
  Se un'allocazione intermedia fallisce non libera quelle gia riuscite.
- **`glm_graph_mtp_step`** `ds4.c:42496`  
  Sovrascrive lo scratch decode e legge tutti i logits su host per fare argmax.
- **`glm_graph_normal_layer_count`** `ds4.c:34817`  
  Con costanti incoerenti restituisce zero senza errore.
- **`glm_graph_prefill_chunk_tokens`** `ds4.c:44075`  
  Con cap zero usa il contesto full-attention predefinito.
- **`glm_graph_prefill_progress_flush_interval`** `ds4.c:38223`  
  Se l'intervallo e zero ignora token, callback e lavoro totale e restituisce zero.
- **`glm_graph_prefill_range`** `ds4.c:45396`  
  Con n_tokens zero restituisce successo senza produrre logits.
- **`glm_graph_prefill_stage_boundary`** `ds4.c:39963`  
  Il profiling ha precedenza: se entrambi i flag sono veri la sync esplicita viene ignorata.
- **`glm_graph_prefill_stage_sync_boundary`** `ds4.c:38303`  
  Se la chiusura restituisce zero non tenta di riaprire i comandi.
- **`glm_graph_prefill_token_major`** `ds4.c:45638`  
  Riusa il lento percorso decode un token alla volta per scaldare la cache esperti.
- **`glm_graph_profile_router_selection`** `ds4.c:39852`  
  Quando attivo chiude e riapre il batch di comandi per il readback.
- **`glm_graph_profile_router_selection_batch`** `ds4.c:39896`  
  Alloca memoria host e interrompe il batch di comandi a ogni layer profilato.
- **`glm_graph_profile_stage`** `ds4.c:39839`  
  Se disabilitato restituisce successo senza validare stage_t0.
- **`glm_graph_q8_decode_profile_enabled`** `ds4.c:39722`  
  Ignora layer ed etichetta e restituisce sempre false.
- **`glm_graph_q8_stripe_tokens`** `ds4.c:41008`  
  La soglia è fissa a 2048 token.
- **`glm_graph_report_prefill_display_progress`** `ds4.c:38235`  
  Se allow_complete e false limita il progresso a work_total meno uno.
- **`glm_graph_reset_prefill_seed_capture`** `ds4.c:41422`  
  Cancella in blocco anche catture di layer fuori dall'intervallo attivo.
- **`glm_graph_resume_prefill_min_tokens`** `ds4.c:34765`  
  Su ROCm ignora l'env; altrove un valore non positivo disabilita il prefill ripreso.
- **`glm_graph_routed_moe_batch_dispatch`** `ds4.c:40128`  
  Azzera sempre batch_routed_mid_is_f16 prima di scegliere il kernel.
- **`glm_graph_routed_moe_one_dispatch`** `ds4.c:39979`  
  Un guard fallito restituisce 0; il debug appare solo con DS4_GLM_TP_DEBUG.
- **`glm_graph_saturating_add_u64`** `ds4.c:37774`  
  L'overflow restituisce UINT64_MAX anziche avvolgere.
- **`glm_graph_seed_streaming_expert_cache_from_full_layer`** `ds4.c:41588`  
  Restituisce sempre true; un fallimento degrada al seed finale e avvisa una sola volta.
- **`glm_graph_seed_streaming_expert_cache_from_prefill`** `ds4.c:41485`  
  Legge dalla GPU l'intero slab di tutte le layer, anche se poche sono state catturate.
- **`glm_graph_shared_gate_up_swiglu_q8_0_tensor`** `ds4.c:41293`  
  Con pesi non Q8 restituisce false invece di usare un percorso generico.
- **`glm_graph_small_prefill_stage_sync`** `ds4.c:38266`  
  Zero token non richiede sync anche se sono richiesti logits.
- **`glm_graph_span_fits_full_attention`** `ds4.c:38428`  
  La capacità di lavoro può essere minore del contesto logico.
- **`glm_graph_stream_layer_expert_cache_supported`** `ds4.c:38494`  
  I layer densi iniziali risultano supportati senza consultare la cache.
- **`glm_graph_stream_map_decode_layer`** `ds4.c:38536`  
  La sola presenza dell'env, anche valore 0, forza la mappa completa; il fallback è sempre completo.
- **`glm_graph_stream_map_output`** `ds4.c:38758`  
  Con streaming disattivo restituisce successo senza mappare nulla.
- **`glm_graph_stream_map_prefill_layer`** `ds4.c:38561`  
  Su ROCm il full-layer compatibile usa la routine di mapping decode.
- **`glm_graph_stream_map_token`** `ds4.c:38485`  
  Con streaming disattivo restituisce successo senza mappare nulla.
- **`glm_graph_stream_prefill_expert_addr_supported`** `ds4.c:38503`  
  Un layer denso iniziale è accettato anche con un solo token.
- **`glm_graph_stream_prefill_full_layer_enabled`** `ds4.c:38632`  
  Gli override sono testati per presenza: anche il valore 0 abilita o disabilita.
- **`glm_graph_stream_prefill_full_layer_min_tokens`** `ds4.c:38618`  
  Zero o valori malformati non disabilitano la soglia ma ripristinano il default.
- **`glm_graph_stream_prefill_full_layer_prepare_enabled`** `ds4.c:38648`  
  Anche un valore 0 nella variabile di disattivazione spegne la preparazione.
- **`glm_graph_streaming_active_model_bytes`** `ds4.c:37814`  
  Gli span non ottenibili vengono saltati e il risultato puo restare zero.
- **`glm_graph_streaming_async_profile_enabled`** `ds4.c:40288`  
  Conta la presenza dell'env, non il suo valore.
- **`glm_graph_streaming_async_profile_print`** `ds4.c:40293`  
  Non stampa nulla se entrambi i contatori di chiamate sono zero.
- **`glm_graph_streaming_async_profile_register`** `ds4.c:40327`  
  La callback viene registrata solo quando il profiling risulta abilitato.
- **`glm_graph_streaming_decode_sync_each_layer`** `ds4.c:45702`  
  Sulla RTX ignora entrambe le variabili STREAMING_DECODE_SYNC_EACH_LAYER.
- **`glm_graph_streaming_expert_cache_seed_layer_expected`** `ds4.c:41430`  
  Quality mode e layer residenti escludono sempre il seed.
- **`glm_graph_streaming_prefill_cache_seed_enabled`** `ds4.c:41417`  
  Riparsa le variabili d'ambiente a ogni chiamata.
- **`glm_graph_streaming_prefill_cache_seed_k`** `ds4.c:41391`  
  Un K non valido vale 1, zero disabilita e valori grandi vengono saturati al massimo.
- **`glm_graph_streaming_prefill_sync_each_layer`** `ds4.c:38330`  
  Il full-layer sincronizza sempre; fuori ROCm restituisce sempre true.
- **`glm_graph_streaming_token_prefill_default_max_tokens`** `ds4.c:45598`  
  Il default ROCm disabilita del tutto il token-major.
- **`glm_graph_streaming_token_prefill_max_tokens`** `ds4.c:45606`  
  Zero e valido e disabilita il percorso; valori malformati ricadono sul default di piattaforma.
- **`glm_graph_tensor_layout`** `ds4.c:38449`  
  Per ranghi maggiori di tre ignora tutte le dimensioni successive.
- **`glm_graph_tensor_row_view_strided`** `ds4.c:40998`  
  Stride e dimensione sono sempre interpretati come valori float.
- **`glm_graph_tp_batch_bounce_ready`** `ds4.c:40090`  
  Controlla la capacità solo di tp_bounce_out, non quella del buffer in.
- **`glm_graph_tp_batch_ffn_combine`** `ds4.c:40102`  
  DS4_GLM_ABLATE_COMBINE evita lo scambio e produce volutamente output errato.
- **`glm_graph_upload_tokens`** `ds4.c:42010`  
  Alloca sempre un buffer host temporaneo anche se int è già a 32 bit.
- **`glm_graph_use_flash_attention_prefill`** `ds4.c:41020`  
  La soglia è inclusiva: 24 token attivano già flash attention.
- **`glm_graph_use_flash_attention_staged_kv`** `ds4.c:41025`  
  È vero solo a posizione zero e quando n_tokens coincide esattamente con cache_len.
- **`glm_graph_use_streaming_selected_async_load`** `ds4.c:40251`  
  Su ROCm è predefinito; su Metal richiede esplicita abilitazione.
- **`glm_graph_use_streaming_token_prefill`** `ds4.c:45623`  
  La sola presenza di DS4_GLM_DISABLE_STREAMING_TOKEN_PREFILL disabilita, anche se vale 0.
- **`glm_graph_validate_expert_layout`** `ds4.c:38767`  
  Ignora i codici di ritorno di tensor_expert_bytes e decide dai valori prodotti.
- **`glm_graph_validate_layer_layout`** `ds4.c:38805`  
  Può aggiornare kv_raw_dim_out prima di scoprire un layout FFN non valido.
- **`glm_graph_validate_layout`** `ds4.c:38875`  
  generic_routed_moe viene solo acceso, mai azzerato dalla funzione.
- **`glm_graph_verify_rows`** `ds4.c:42921`  
  Calcola logits solo sull'ultima riga; output_hc, se richiesto, contiene tutte le righe.
- **`glm_graph_verify_ws_free`** `ds4.c:39085`  
  Se verify_ws_ready è falso non libera eventuali puntatori parziali.
- **`glm_graph_verify_ws_init`** `ds4.c:39098`  
  Senza placement marca il workspace pronto senza allocare mirror.
- **`glm_graph_verify_ws_restore`** `ds4.c:39076`  
  Con workspace non pronto non modifica neppure il tier corrente.
- **`glm_graph_verify_ws_slot`** `ds4.c:39067`  
  Un indice fuori intervallo restituisce NULL.
- **`glm_graph_verify_ws_switch`** `ds4.c:39146`  
  L'inizializzazione dei mirror avviene pigramente al primo switch.
- **`glm_graph_warm_compact_indexer_store`** `ds4.c:39291`  
  Una warm_pos eccessiva viene ridotta all'ultima riga senza errore.
- **`glm_graph_weight_type_for_offset`** `ds4.c:39728`  
  Modello assente o offset sconosciuto vengono trattati silenziosamente come Q8_0.
- **`glm_graph_weights_are_q8_0`** `ds4.c:39739`  
  Offset sconosciuti risultano Q8_0 per effetto del fallback del lookup.
- **`glm_graph_wired_limit_bytes`** `ds4.c:37851`  
  Errore sysctl, limite non positivo e piattaforma non-Apple producono zero.
- **`glm_graph_workspace_add_bytes`** `ds4.c:35051`  
  In caso di overflow satura invece di segnalare un errore.
- **`glm_graph_workspace_bytes_for_cap`** `ds4.c:35060`  
  Lo scratch indicizzato iniziale non usa aritmetica saturante, il resto sì.
- **`glm_graph_ws_free`** `ds4.c:38975`  
  Se ws_ready è falso non ripristina né libera alcunché.
- **`glm_graph_ws_init`** `ds4.c:38991`  
  Un fallimento libera le copie e ripiega sui buffer base senza propagare errore.
- **`glm_graph_ws_slot`** `ds4.c:38967`  
  Un indice fuori intervallo restituisce NULL.
- **`glm_graph_ws_switch`** `ds4.c:39029`  
  Se i mirror non sono pronti cambia comunque device e restituisce successo.
- **`glm_indexer_rope_tail_kernel`** `rocm/ds4_rocm_glm.cuh:668`  
  Ruota le prime rot_dim componenti, non una coda fisica del vettore
- **`glm_indexer_score_one_kernel`** `rocm/ds4_rocm_glm.cuh:700`  
  Applica ReLU al punteggio di ogni testa prima della somma pesata
- **`glm_indexer_scores_batch_kernel`** `rocm/ds4_rocm_glm.cuh:732`  
  Le righe future vengono scritte a meno infinito invece di essere omesse
- **`glm_indexer_scores_f32_kernel`** `ds4_cuda.cu:30920`  
  Applica ReLU a ogni dot di testa prima della somma pesata.
- **`glm_indexer_scores_launch`** `ds4_cuda.cu:31082`  
  g_quality_mode falso sceglie WMMA e riduce Q e K a f16.
- **`glm_indexer_scores_wmma128_kernel`** `ds4_cuda.cu:30969`  
  Con cache f32 converte comunque Q e K in f16 nello shared.
- **`glm_k_b_project_f32_ref`** `ds4.c:14398`  
  È una proiezione reference scalare, non il normale matvec.
- **`glm_k_b_project_q8_0_head_kernel`** `rocm/ds4_rocm_glm.cuh:390`  
  La matrice dei pesi è trasposta rispetto a una classica riga per output
- **`glm_k_b_project_q8_0_kernel`** `rocm/ds4_rocm_glm.cuh:365`  
  Ogni thread rilegge serialmente tutto kv_lora_dim senza memoria condivisa
- **`glm_kv_lora_rms_norm_kernel`** `rocm/ds4_rocm_glm.cuh:176`  
  La coda rope della riga sorgente non viene letta ne copiata.
- **`glm_layer_payload_tensor_bytes`** `ds4.c:48626`  
  Rifiuta dimensioni alternative invece di calcolarne la dimensione.
- **`glm_metal_compare_f32`** `ds4.c:52019`  
  Il valore RMS viene solo stampato; non partecipa al verdetto.
- **`glm_metal_compare_i32_list`** `ds4.c:52047`  
  Stampa entrambe le liste anche quando il confronto è riuscito.
- **`glm_metal_first_token_logits`** `ds4.c:46469`  
  L'attenzione a un solo token salta Q/K e usa direttamente la proiezione V.
- **`glm_metal_graph_test`** `ds4.c:52876`  
  Il sottotest Q8 prefill invocato qui è disabilitato e passa sempre.
- **`glm_metal_graph_test_decode_attention`** `ds4.c:52573`  
  Un prompt con meno di due token è considerato test superato.
- **`glm_metal_graph_test_multitok_attention`** `ds4.c:52252`  
  Un prompt con meno di due token è considerato test superato.
- **`glm_metal_graph_test_q8_prefill`** `ds4.c:52208`  
  Tutto il codice diagnostico successivo è irraggiungibile.
- **`glm_metal_graph_test_q8_prefill_one`** `ds4.c:52103`  
  Con strict=0 tollera ogni errore numerico e restituisce successo anche dopo altri fallimenti.
- **`glm_moe_build_expert_tiles8_kernel`** `ds4_cuda.cu:31972`  
  Usa un solo thread GPU e serializza tutti gli esperti.
- **`glm_moe_expert_map_kernel`** `ds4_cuda.cu:31955`  
  L'ordine nelle liste e non deterministico per via degli atomicAdd concorrenti.
- **`glm_q8_0_dot_row_dev`** `ds4_cuda.cu:30107`  
  Le colonne residue oltre l'ultimo blocco da 32 sono ignorate.
- **`glm_q8_project_head_kernel`** `rocm/ds4_rocm_glm.cuh:464`  
  Ogni thread calcola serialmente interi prodotti scalari per gli output assegnati
- **`glm_q8_project_head_wave_kernel`** `rocm/ds4_rocm_glm.cuh:495`  
  Cambia l'ordine delle somme FP32 e quindi può cambiare numericamente l'output
- **`glm_q8_project_rows_kernel`** `rocm/ds4_rocm_glm.cuh:424`  
  La riduzione richiede una blockDim potenza di due non maggiore di 256
- **`glm_qk_lowrank_q8_0_batch_kernel`** `ds4_cuda.cu:31251`  
  qk_dim determina solo lo stride; il prodotto usa esclusivamente qk_nope colonne.
- **`glm_qkv_norm_store_compact_kv_kernel`** `rocm/ds4_rocm_glm.cuh:236`  
  Salva la coda RoPE non ruotata: la rotazione avviene durante la lettura in attenzione.
- **`glm_rocm_cache_load`** `rocm/ds4_rocm_glm.cuh:5`  
  Un flag errato reinterpreta silenziosamente l'intera cache con il tipo sbagliato
- **`glm_rocm_cache_store`** `rocm/ds4_rocm_glm.cuh:13`  
  In modalità FP16 arrotonda il valore prima di salvarlo
- **`glm_rocm_check_pos_span`** `rocm/ds4_rocm_glm.cuh:168`  
  Eredita il rifiuto degli intervalli con zero token
- **`glm_rocm_check_q8_rows`** `rocm/ds4_rocm_glm.cuh:1261`  
  Il cast finale a uint32 non ha un controllo esplicito separato
- **`glm_rocm_check_token_span`** `rocm/ds4_rocm_glm.cuh:159`  
  Rifiuta sempre n_tokens uguale a zero
- **`glm_rocm_launch_blocks`** `rocm/ds4_rocm_glm.cuh:120`  
  Per n zero restituisce successo con zero blocchi, che il chiamante non deve lanciare
- **`glm_rocm_model_f32_range`** `rocm/ds4_rocm_glm.cuh:145`  
  bytes_out può essere nullo e allora la dimensione calcolata viene scartata
- **`glm_rocm_q8_0_dot_row`** `rocm/ds4_rocm_glm.cuh:94`  
  Accetta una coda sotto 32 colonne ma presume che il blocco quantizzato esista per intero
- **`glm_rocm_rope_pair`** `rocm/ds4_rocm_glm.cuh:22`  
  Con ext_factor zero salta del tutto la correzione YaRN
- **`glm_rocm_rotated_cache_rope_pair`** `rocm/ds4_rocm_glm.cuh:57`  
  Applica la rotazione al momento della lettura, non quando la coda viene salvata
- **`glm_rocm_routed_moe_wrap`** `rocm/ds4_rocm_glm.cuh:3959`  
  Ignora mid_token_stride e sceglie il percorso solo da n_tokens uguale a uno
- **`glm_rocm_u32_add_checked`** `rocm/ds4_rocm_glm.cuh:113`  
  Non modifica out quando la somma non è rappresentabile
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
- **`glm_routed_moe_dot_f32`** `ds4.c:14727`  
  Q5_K e Q6_K condividono lo stesso dispatcher di prodotto.
- **`glm_routed_moe_down_expert_kernel`** `ds4_cuda.cu:32123`  
  Usa atomicAdd: l'ordine delle somme non è deterministico.
- **`glm_routed_moe_down_expert_tile8_terms_kernel`** `ds4_cuda.cu:32169`  
  Scrive termini non pesati e non ridotti; serve il kernel di riduzione successivo.
- **`glm_routed_moe_down_terms_reduce_kernel`** `ds4_cuda.cu:32226`  
  Sovrascrive l'uscita invece di accumularla.
- **`glm_routed_moe_down_warp_kernel`** `ds4_cuda.cu:31900`  
  Carica nello shared anche le righe mid degli slot poi scartati come invalidi.
- **`glm_routed_moe_f32_down_worker`** `ds4.c:14769`  
  Ogni worker percorre tutti gli esperti selezionati per ciascuna riga.
- **`glm_routed_moe_f32_mid_worker`** `ds4.c:14744`  
  Applica il peso esperto al mid prima della proiezione down.
- **`glm_routed_moe_finish_batch`** `ds4_cuda.cu:32257`  
  Se i puntatori coincidono considera concluso il lavoro senza copia.
- **`glm_routed_moe_gateup_expert_tile8_kernel`** `ds4_cuda.cu:31995`  
  Legge tile_total dalla VRAM in ogni blocco di una griglia sovradimensionata.
- **`glm_routed_moe_gateup_tok2_reuse_kernel`** `ds4_cuda.cu:31807`  
  Il lavoro del token 1 condiviso viene saltato e prodotto dal blocco proprietario del token 0.
- **`glm_routed_moe_gateup_warp_kernel`** `ds4_cuda.cu:31746`  
  Copia l'attivazione nello shared anche per slot con esperto negativo.
- **`glm_router_score_better`** `rocm/ds4_rocm_glm.cuh:3773`  
  A parità di punteggio vince sempre l'indice esperto più basso
- **`glm_router_select_batch_kernel`** `ds4_cuda.cu:32756`  
  Il blocco ha 32 thread ma soltanto il thread 0 svolge tutto il lavoro.
- **`glm_router_select_launch`** `rocm/ds4_rocm_glm.cuh:3865`  
  Valori zero per numero esperti, top-k o scala vengono sostituiti con default compilati
- **`glm_router_select_parallel_kernel`** `ds4_cuda.cu:32689`  
  Il bias decide il top-k, ma i pesi normalizzati usano le probabilità senza bias.
- **`glm_router_select_warp_topk_kernel`** `rocm/ds4_rocm_glm.cuh:3777`  
  Il bias decide il ranking ma i pesi finali usano le probabilità senza bias
- **`glm_router_sigmoid_dev`** `rocm/ds4_rocm_glm.cuh:3764`  
  Usa due formule diverse ai lati dello zero per evitare overflow
- **`glm_selected_gemm_gather_heads_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2338`  
  Le slot oltre head_count non vengono inizializzate
- **`glm_selected_gemm_head_tile`** `rocm/ds4_rocm_glm.cuh:2504`  
  La variabile ambiente è letta solo al primo uso; valori invalidi ricadono a 16
- **`glm_selected_gemm_kv_to_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2214`  
  Gli indici non validi diventano righe di zeri invece di causare errore
- **`glm_selected_gemm_profile_begin`** `rocm/ds4_rocm_glm.cuh:2552`  
  Un errore disabilita silenziosamente il resto del profilo
- **`glm_selected_gemm_profile_end`** `rocm/ds4_rocm_glm.cuh:2560`  
  Sincronizza la GPU a ogni fase e altera sensibilmente il tempo osservato
- **`glm_selected_gemm_profile_init`** `rocm/ds4_rocm_glm.cuh:2529`  
  La prima chiamata reclama per sempre il profiling, anche se la creazione degli eventi fallisce
- **`glm_selected_gemm_profile_report`** `rocm/ds4_rocm_glm.cuh:2579`  
  Viene stampato solo il profilo della prima chiamata globale reclamata
- **`glm_selected_gemm_rope_to_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2242`  
  Gli indici non validi producono coppie zero e restano nel softmax
- **`glm_selected_gemm_scatter_heads_kernel`** `rocm/ds4_rocm_glm.cuh:2441`  
  Legge head_out con stride head_capacity, non head_count
- **`glm_selected_gemm_softmax_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2291`  
  Sovrascrive il buffer scores durante il calcolo
- **`glm_selected_gemm_softmax_heads_f16_kernel`** `rocm/ds4_rocm_glm.cuh:2389`  
  Le righe usano head_capacity come stride anche nell'ultima mattonella parziale
- **`glm_session_logits_argmax`** `ds4.c:57977`  
  In caso di parita vince l'indice minore
- **`glm_shared_gate_up_swiglu_one_kernel`** `ds4_cuda.cu:33423`  
  Il clamp è asimmetrico: gate ha solo limite superiore, up anche quello inferiore.
- **`glm_shared_gate_up_swiglu_tok2_exact_kernel`** `ds4_cuda.cu:33480`  
  Il clamp è asimmetrico: gate ha solo limite superiore, up anche quello inferiore.
- **`glm_store_compact_kv_kernel`** `rocm/ds4_rocm_glm.cuh:206`  
  Le posizioni oltre cache_cap vengono saltate senza errore.
- **`glm_store_indexer_k_kernel`** `rocm/ds4_rocm_glm.cuh:298`  
  Le posizioni oltre cache_cap vengono saltate senza errore.
- **`glm_stream_decode_experts_are_streamed`** `ds4.c:6585`  
  Per Q2_K e Q4_K controlla il layout, non il budget GPU effettivo della cache.
- **`glm_stream_expert_cache_addr_layout_supported`** `ds4.c:6493`  
  La sola presenza della variabile DISABLE, anche con valore 0, disabilita il percorso.
- **`glm_stream_expert_cache_addr_supported`** `ds4.c:6524`  
  Con DS4_NO_GPU restituisce sempre falso.
- **`glm_stream_resident_decode_layer_enabled`** `ds4.c:6483`  
  Un conteggio globale pari a zero disabilita ogni layer.
- **`glm_stream_resident_decode_layer_supported`** `ds4.c:6457`  
  IQ2_XXS per gate e up ammette down sia IQ2_XXS sia Q2_K.
- **`glm_stream_selected_expert_cache_supported`** `ds4.c:6548`  
  Ogni variabile DISABLE conta per presenza: anche il valore 0 spegne il percorso.
- **`glm_tp_head_split_min`** `ds4.c:34842`  
  Legge l'ambiente solo alla prima chiamata; un valore negativo diventa zero.
- **`glm_value_project_q8_0_batch_heads_tiled_kernel`** `ds4_cuda.cu:33155`  
  La specializzazione assume il formato Q8_0 da 34 byte per blocco.
- **`gpt2_byte_to_codepoint`** `ds4.c:35970`  
  I byte non stampabili diventano code point da U+0100 in su
- **`gpt2_codepoint_to_byte`** `ds4.c:36937`  
  Restituisce -1 per codepoint non mappati.
- **`gpu_graph_report_prefill_display_progress`** `ds4.c:33010`  
  Clampa layer_done e forza esattamente n_tokens all'ultimo layer.
- **`graph_power_note_decode_token`** `ds4.c:15912`  
  Dorme sulla media mobile, non sul solo tempo del token corrente.
- **`graph_power_note_prefill_layer`** `ds4.c:15902`  
  Un indice layer fuori intervallo viene ignorato senza errore.
- **`graph_power_sleep`** `ds4.c:15892`  
  power_percent maggiore di 100 disabilita il sonno invece di saturarlo.
- **`graph_power_throttle_enabled`** `ds4.c:15882`  
  Zero e valori almeno 100 disabilitano il throttling.
- **`graph_power_update_avg`** `ds4.c:15886`  
  Campioni non positivi o non finiti sono ignorati; il primo valido sostituisce la media.
- **`graph_stream_expert_table_make`** `ds4.c:4699`  
  Modello o layer NULL danno una tabella zero; tensori mancanti producono offset zero.
- **`grouped_q8_0_a_f32_batch_sharedx_chunked_strided_w32_kernel`** `rocm/ds4_rocm_q8.cuh:1576`  
  Legge un input strided ma produce sempre un output compatto token-gruppo-rank
- **`grouped_q8_0_a_f32_batch_sharedx_chunked_w32_kernel`** `rocm/ds4_rocm_q8.cuh:1508`  
  Le righe di output invalide partecipano alle sincronizzazioni ma non scrivono
- **`grouped_q8_0_a_f32_batch_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:1476`  
  L'input usa il layout token, gruppo, feature; l'output token, gruppo, rank
- **`grouped_q8_0_a_f32_batch_wmma_onthefly_kernel`** `rocm/ds4_rocm_q8.cuh:1658`  
  Converte input e pesi dequantizzati in FP16 prima dell'accumulo
- **`grouped_q8_0_a_f32_sharedx_rows_w32_2row_kernel`** `rocm/ds4_rocm_q8.cuh:1375`  
  Un solo gruppo e' fissato per blocco; attraversarne il confine darebbe risultati errati
- **`grouped_q8_0_a_f32_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:1345`  
  L'input e' group-major e rappresenta un solo token
- **`grouped_q8_0_a_partial16_w32_kernel`** `rocm/ds4_rocm_q8.cuh:1428`  
  Lo stride di ogni gruppo di heads e' fissato nel codice a 4096 float
- **`grouped_q8_0_a_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:1794`  
  Solo la lane 0 di ogni warp scrive il risultato ridotto.
- **`grouped_q8_0_a_preq_warp8_tok2_kernel`** `ds4_cuda.cu:8834`  
  La seconda metà del blocco serve esclusivamente il secondo token.
- **`half_warp_sum_f32`** `rocm/ds4_rocm_moe.cuh:465`  
  Il parametro lane16 è ignorato; il gruppo deriva solo da threadIdx.x
- **`hash_bytes`** `ds4.c:1141`  
  Il seed differisce dall'offset basis FNV-1a standard per una cifra mancante.
- **`hc4_split_one`** `rocm/ds4_rocm_hc.cuh:6`  
  Anche sinkhorn_iters uguale a 0 esegue già una normalizzazione per righe e colonne
- **`hc_expand4_add_half_kernel`** `rocm/ds4_rocm_hc.cuh:266`  
  Converte solo l'addendo da FP16; blocco, residui e output sono FP32.
- **`hc_expand4_add_kernel`** `rocm/ds4_rocm_hc.cuh:199`  
  Ogni thread scrive quattro canali HC, non un solo elemento di output.
- **`hc_expand4_half_kernel`** `rocm/ds4_rocm_hc.cuh:233`  
  L'input blocco è FP16 ma l'output espanso resta FP32.
- **`hc_expand4_kernel`** `rocm/ds4_rocm_hc.cuh:166`  
  Ignora i primi quattro valori pre di ogni record split.
- **`hc_expand_add_half_kernel`** `rocm/ds4_rocm_hc.cuh:135`  
  Converte solo block_add da FP16; block_out e output sono FP32.
- **`hc_expand_add_partial4_kernel`** `rocm/ds4_rocm_q8.cuh:1291`  
  Somma sempre quattro split: il numero non e' parametrico
- **`hc_expand_add_partial_kernel`** `rocm/ds4_rocm_q8.cuh:1263`  
  block_add influenza out_hc anche quando store_block_out vale zero
- **`hc_expand_half_kernel`** `rocm/ds4_rocm_hc.cuh:106`  
  Solo block_out è FP16; residui, coefficienti e output restano FP32.
- **`hc_expand_kernel`** `rocm/ds4_rocm_hc.cuh:74`  
  Se has_add2 è vero ma has_add è falso, block_add2 viene comunque ignorato
- **`hc_expand_partial16_kernel`** `rocm/ds4_rocm_q8.cuh:1319`  
  Somma sempre sedici split: il numero non e' parametrico
- **`hc_expand_partial_kernel`** `rocm/ds4_rocm_q8.cuh:1237`  
  Con store_block_out a zero lascia block_out invariato ma scrive out_hc
- **`hc_from_plain_embedding`** `ds4.c:10159`  
  Tutti gli stream partono come copie identiche.
- **`hc_post_batch`** `ds4.c:10213`  
  Usa granularità minima di un token.
- **`hc_post_batch_worker`** `ds4.c:10200`  
  È una callback indiretta di parallel_for, non una funzione morta.
- **`hc_post_one`** `ds4.c:10167`  
  comb è letto con indice dst + src*n_hc, cioè per colonne.
- **`hc_post_sum_batch`** `ds4.c:10270`  
  Fonde la somma FFN nel post HC, evitando un buffer di somma separato.
- **`hc_post_sum_batch_worker`** `ds4.c:10247`  
  Somma moe e shared prima di moltiplicare per il gate post.
- **`hc_pre_from_state_one`** `ds4.c:10118`  
  Alloca e libera hc_dim float a ogni chiamata.
- **`hc_pre_from_state_one_scratch`** `ds4.c:10085`  
  serial_fn cambia silenziosamente il matvec in versione seriale.
- **`hc_pre_norm_batch`** `ds4.c:10345`  
  Passa al worker un matvec HC seriale per evitare parallelismo annidato.
- **`hc_pre_norm_batch_worker`** `ds4.c:10310`  
  Alloca un flat per worker; residual_hc nullo evita la copia dell'input.
- **`hc_split_sinkhorn_kernel`** `rocm/ds4_rocm_hc.cuh:54`  
  Con zero iterazioni richiede comunque e svolge il primo passo riga-colonna
- **`hc_split_sinkhorn_one`** `ds4.c:9987`  
  Il buffer locale è fisso a 16x16 e non esiste controllo su n_hc.
- **`hc_split_weighted_sum_fused_kernel`** `rocm/ds4_rocm_hc.cuh:300`  
  Con n_hc diverso da 4 ritorna senza scrivere alcun output
- **`hc_split_weighted_sum_norm_fused_kernel`** `rocm/ds4_rocm_hc.cuh:328`  
  Riscrive out come intermedio grezzo prima di produrre norm_out
- **`hc_weighted_sum_one`** `ds4.c:10068`  
  Non normalizza i pesi ricevuti.
- **`head_rms_norm_inplace`** `ds4.c:7041`  
  Ogni testa usa una propria RMS, non una normalizzazione globale della proiezione.
- **`head_rms_norm_kernel`** `rocm/ds4_rocm_norm_rope.cuh:83`  
  Modifica il tensore x in-place.
- **`head_rms_norm_rope_tail_from_half_kernel`** `rocm/ds4_rocm_norm_rope.cuh:174`  
  Converte e normalizza in un output separato, lasciando intatto l'input FP16.
- **`head_rms_norm_rope_tail_kernel`** `rocm/ds4_rocm_norm_rope.cuh:105`  
  Il flag inverse cambia solo il segno del seno.
- **`header_end`** `ds4_server.c:12476`  
  Accetta la separazione non standard con due soli LF.
- **`help_make_colors`** `ds4_help.c:25`  
  Su output non TTY restituisce una palette interamente nulla
- **`hex20`** `ds4_kvstore.c:430`  
  Aggiunge sempre il terminatore NUL al byte 40
- **`hipblaslt_gemm_plan_clear`** `rocm/ds4_rocm_hipblaslt.cuh:20`  
  Ignora silenziosamente gli errori restituiti dalle funzioni di distruzione.
- **`hipblaslt_gemm_plan_get`** `rocm/ds4_rocm_hipblaslt.cuh:38`  
  Il puntatore restituito può essere invalidato da un successivo push_back del vector.
- **`hipblaslt_gemm_tn_f16_out_f16`** `rocm/ds4_rocm_hipblaslt.cuh:114`  
  Usa sempre stream 0 e zero workspace, ignorando lo stream del chiamante.
- **`hipblaslt_ok`** `rocm/ds4_rocm_hipblaslt.cuh:32`  
  Ogni errore viene scritto su stderr prima di restituire zero.
- **`history_file_path`** `ds4_cli.c:1315`  
  Se HOME manca usa ./; snprintf può troncare il percorso senza segnalarlo.
- **`host_page_size`** `src/cuda/dynamic_arena.cu:778`  
  In caso di errore assume 4096 byte
- **`http_error`** `ds4_server.c:5572`  
  Il tipo resta invalid_request_error indipendentemente dal codice HTTP
- **`http_error_context_length_exceeded`** `ds4_server.c:5595`  
  Anthropic omette param e code presenti nella forma OpenAI
- **`http_request_free`** `ds4_server.c:12471`  
  Azzera anche metodo, percorso e lunghezza dopo la free.
- **`http_response`** `ds4_server.c:5546`  
  I codici non elencati ricevono sempre la reason phrase Error
- **`id_list_contains`** `ds4_server.c:9114`  
  ID nullo o vuoto viene sempre trattato come assente.
- **`id_list_free`** `ds4_server.c:9127`  
  Non accetta un puntatore lista nullo.
- **`id_list_push_unique`** `ds4_server.c:9122`  
  ID nullo, vuoto o duplicato viene ignorato senza esito.
- **`imatrix_collect_layer_batch`** `ds4.c:32843`  
  Esperti selezionati fuori intervallo vengono saltati silenziosamente.
- **`imatrix_collector_free`** `ds4.c:32823`  
  Dopo la free azzera anche capienza, contatori e dataset_path.
- **`imatrix_collector_init`** `ds4.c:32806`  
  cap_tokens uguale a zero viene trasformato silenziosamente in uno.
- **`imatrix_collector_save`** `ds4.c:32932`  
  Gate e up ricevono intenzionalmente gli stessi accumulatori gate_up.
- **`imatrix_down_ptr`** `ds4.c:32839`  
  Non esegue alcun controllo degli indici.
- **`imatrix_gate_up_ptr`** `ds4.c:32835`  
  Non esegue alcun controllo degli indici.
- **`imatrix_read_text_file`** `ds4.c:51071`  
  Dereferenzia out e len_out prima di qualunque controllo.
- **`imatrix_trim_block`** `ds4.c:51109`  
  Scrive un NUL in end, modificando il buffer del dataset.
- **`imatrix_write_entry`** `ds4.c:32902`  
  Per un esperto mai osservato scrive 1.0 in tutte le colonne.
- **`imatrix_write_i32`** `ds4.c:32898`  
  Una short write termina il processo con ds4_die.
- **`indexed_topk_sort_512_asc_kernel`** `rocm/ds4_rocm_indexer.cuh:712`  
  Perde l'ordine per score e conserva soltanto l'ordine crescente degli indici.
- **`indexer_allowed_decode_one`** `ds4.c:13205`  
  Se n_comp non supera top-k abilita tutto senza calcolare l'indexer.
- **`indexer_allowed_decode_one_decode_scratch`** `ds4.c:13268`  
  Il puntatore restituito è un alias riusabile dello scratch e non va liberato.
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
- **`input_queue_key`** `ds4_eval.c:1868`  
  Le frecce si sommano, mentre invio, pausa e uscita collassano in booleani.
- **`input_thread_main`** `ds4_eval.c:1884`  
  Lo stato di una sequenza Escape sopravvive tra letture separate.
- **`iq1_s_fixture_dequant_kernel`** `ds4_cuda.cu:20965`  
  Non esiste nella build normale senza DS4_IQ1_TEST_API
- **`iq1_s_sidecar_bind`** `ds4.c:6178`  
  Nei primi tre layer il tensore down deve essere Q2_K, non IQ1_S.
- **`iq2_xxs_dequant_256_direct`** `rocm/ds4_rocm_moe.cuh:3690`  
  La scala locale è ricostruita dal nibble alto dei bit dei segni.
- **`iq2_xxs_dequant_dual_pair_tile_half_rowwise`** `rocm/ds4_rocm_moe.cuh:3709`  
  Le righe fuori dimensione vengono scritte come bit zero in entrambi i tile.
- **`iq2xxs_signed_grid_init`** `ds4.c:986`  
  È invocata indirettamente tramite os_once, invisibile al grafo dei caller.
- **`isCombiningMark`** `linenoise.c:307`  
  La tabella è parziale e non equivale alla proprietà Unicode Grapheme_Extend.
- **`isGraphemeExtend`** `linenoise.c:316`  
  Usa una regola euristica, non l'algoritmo completo dei cluster Unicode.
- **`isUnsupportedTerm`** `linenoise.c:644`  
  TERM assente viene considerato supportato.
- **`isVariationSelector`** `linenoise.c:287`  
  Non riconosce i variation selector supplementari U+E0100-U+E01EF.
- **`is_letter_boundary`** `ds4_eval.c:2745`  
  Cifre e punteggiatura valgono entrambe come confine.
- **`is_rendered_chat_prompt`** `ds4_cli.c:381`  
  Spazi iniziali o un template non elencato causano una nuova codifica chat.
- **`job_required_slot_locked`** `ds4_server.c:12316`  
  Un binding richiesto ma assente restituisce -1, come una richiesta senza binding.
- **`job_slot_score`** `ds4_server.c:12335`  
  Uno slot esplicitamente richiesto ottiene INT_MAX indipendentemente dal prefix.
- **`joyai_ascii_punct_symbol`** `ds4.c:36129`  
  Classifica anche underscore e backtick come simboli
- **`joyai_cjk_at`** `ds4.c:36187`  
  Usa intervalli CJK limitati e una decodifica UTF-8 permissiva
- **`joyai_consume_letters`** `ds4.c:36180`  
  Eredita l'approssimazione che tratta ogni byte non ASCII come lettera
- **`joyai_letter_like_at`** `ds4.c:36164`  
  Ogni byte non ASCII è considerato lettera
- **`json_args_find_unused`** `ds4_server.c:2364`  
  Con chiavi duplicate restituisce ogni volta la prima ancora non marcata used.
- **`json_args_free`** `ds4_server.c:2347`  
  Dopo la liberazione azzera anche lunghezza e capacità.
- **`json_args_parse`** `ds4_server.c:2372`  
  Accetta testo residuo dopo la prima graffa chiusa e non avanza un cursore esterno.
- **`json_args_push`** `ds4_server.c:2356`  
  La prima crescita riserva otto elementi e xrealloc gestisce fatalmente l'eventuale OOM.
- **`json_bool`** `ds4_server.c:520`  
  Eredita il confronto per prefisso: trueX puo essere accettato
- **`json_content`** `ds4_server.c:649`  
  Tipi non supportati e campi non text vengono scartati silenziosamente come testo vuoto
- **`json_escape`** `ds4_server.c:4727`  
  Un NUL incorporato tronca l'output
- **`json_escape_fragment_n`** `ds4_server.c:4755`  
  Non aggiunge le virgolette JSON esterne
- **`json_escape_n`** `ds4_server.c:4749`  
  La copia temporanea e json_escape troncano al primo NUL
- **`json_hex`** `ds4_server.c:412`  
  Accetta sia lettere maiuscole sia minuscole
- **`json_int`** `ds4_server.c:511`  
  Negativi diventano zero, valori enormi INT_MAX e frazioni vengono troncate
- **`json_lit`** `ds4_server.c:405`  
  Non verifica il delimitatore: trueX viene accettato come prefisso true
- **`json_minify_raw_value`** `ds4_server.c:622`  
  Se il parse fallisce restituisce silenziosamente l'input invariato, o null per NULL
- **`json_number`** `ds4_server.c:501`  
  strtod puo accettare forme non JSON come nan, inf o esadecimali
- **`json_raw_value`** `ds4_server.c:610`  
  Gli spazi iniziali sono esclusi mentre quelli interni restano intatti
- **`json_skip_array_depth`** `ds4_server.c:541`  
  Un annidamento che raggiunge 256 viene rifiutato
- **`json_skip_object_depth`** `ds4_server.c:563`  
  Un annidamento che raggiunge 256 viene rifiutato
- **`json_skip_value`** `ds4_server.c:606`  
  La profondita massima parte da zero ed e fissata a 256
- **`json_skip_value_depth`** `ds4_server.c:591`  
  Letterali e numeri ereditano parser permissivi e possono lasciare suffissi non validi
- **`json_string`** `ds4_server.c:451`  
  Accetta caratteri di controllo non escapati, vietati dal JSON standard
- **`json_u16`** `ds4_server.c:438`  
  Il cursore avanza solo se tutte le quattro cifre sono valide
- **`json_utf8_valid`** `ds4_cli.c:695`  
  Un token che spezza un carattere multibyte risulta invalido.
- **`json_write_string`** `ds4_cli.c:720`  
  Se un byte invalida UTF-8, tutti i byte da 128 in su diventano escape u00xx.
- **`json_write_token`** `ds4_cli.c:747`  
  Il campo bytes resta autorevole anche quando text è escapato byte per byte.
- **`json_ws`** `ds4_server.c:401`  
  La classe di spazi dipende dalla locale C attiva
- **`key_for`** `src/cuda/vram_expert_cache.cpp:261`  
  Concatena layer ed expert nei 32 bit alti e bassi, senza hashing.
- **`kv_buf_append`** `ds4_kvstore.c:218`  
  Accetta dati binari ma aggiunge sempre un NUL finale
- **`kv_buf_printf`** `ds4_kvstore.c:233`  
  Un errore di formattazione termina il processo
- **`kv_buf_reserve`** `ds4_kvstore.c:208`  
  La crescita per raddoppio non controlla l'overflow di cap
- **`kv_buf_take`** `ds4_kvstore.c:247`  
  Anche un buffer mai allocato restituisce una stringa allocata vuota
- **`kv_cache_budget_required`** `ds4_kvstore.c:919`  
  Anche file sotto 100 byte richiedono un byte extra
- **`kv_cache_chat_anchor_pos`** `ds4_server.c:9449`  
  Ignora la coda dopo l'ultima frontiera utente-assistente utile.
- **`kv_cache_close`** `ds4_server.c:9416`  
  Non libera la sessione KV residente in VRAM.
- **`kv_cache_continued_step`** `ds4_kvstore.c:865`  
  L'intervallo viene arrotondato verso l'alto, per esempio 10000 diventa 10240
- **`kv_cache_continued_store_target`** `ds4_server.c:9457`  
  Restituisce zero quando non è ancora dovuto alcun salvataggio.
- **`kv_cache_discard_failed_disk_entry`** `ds4_server.c:9625`  
  Azzera e invalida anche se il file manca o non può essere eliminato.
- **`kv_cache_evict`** `ds4_server.c:9395`  
  Espelle file su disco, non memoria KV residente.
- **`kv_cache_existing_compatible`** `ds4_kvstore.c:978`  
  Un file malformato non leggibile non viene eliminato in questa funzione
- **`kv_cache_file_size_bytes`** `ds4_kvstore.c:906`  
  Include sempre quattro byte per la lunghezza del testo
- **`kv_cache_file_size_fits`** `ds4_server.c:9469`  
  Valuta byte di file e spazio richiesto separatamente.
- **`kv_cache_file_text_matches`** `ds4_kvstore.c:949`  
  Legge e alloca l'intero testo memorizzato anche se basta scoprire una differenza
- **`kv_cache_find_text_prefix`** `ds4_server.c:9659`  
  Forza model_id a zero.
- **`kv_cache_finish_prefill_states`** `ds4.c:12698`  
  Finalizza lo stato indexer soltanto per rapporto di compressione 4.
- **`kv_cache_free`** `ds4.c:12637`  
  Azzera il contenitore dopo i free; una cache nulla è ignorata.
- **`kv_cache_incoming_supersedes_continued`** `ds4_kvstore.c:639`  
  Un incoming con contesto maggiore non e' considerato sostitutivo
- **`kv_cache_init`** `ds4.c:12595`  
  La cache indexer esiste solo nei layer con rapporto di compressione 4.
- **`kv_cache_log_cb`** `ds4_server.c:9402`  
  Il grafo statico non vede chiamanti perché la funzione è un callback.
- **`kv_cache_maybe_store_continued`** `ds4_server.c:9645`  
  Target zero o errore di scrittura vengono ignorati senza log locale.
- **`kv_cache_open`** `ds4_server.c:9410`  
  Registra implicitamente il callback di log del server.
- **`kv_cache_push`** `ds4_kvstore.c:520`  
  Il raddoppio di capacita' non controlla overflow
- **`kv_cache_push_comp`** `ds4.c:12667`  
  A capacità piena termina il processo invece di scorrere o scartare righe.
- **`kv_cache_push_raw`** `ds4.c:12652`  
  Quando è piena sposta tutta la finestra di una riga con memmove.
- **`kv_cache_reason_is_anchor`** `ds4_kvstore.c:661`  
  Le ragioni agent non sono considerate ancore
- **`kv_cache_refresh`** `ds4_kvstore.c:603`  
  File illeggibili o malformati vengono ignorati senza log
- **`kv_cache_restore_suppressed_continued`** `ds4_server.c:9587`  
  Ripristina solo se il marcatore non è cambiato nel frattempo.
- **`kv_cache_restore_tool_memory_for_messages`** `ds4_server.c:9345`  
  File illeggibili, incompatibili o senza trailer vengono saltati silenziosamente.
- **`kv_cache_rewrite_trailer`** `ds4_kvstore.c:1018`  
  Gli errori sono ignorati e un fallimento dopo truncate puo' perdere il vecchio trailer
- **`kv_cache_slot_continued_target`** `ds4_server.c:9594`  
  Opera su una copia della cache e non aggiorna lo stato globale.
- **`kv_cache_slot_note_store`** `ds4_server.c:9602`  
  Non permette mai di abbassare il marcatore.
- **`kv_cache_slot_restore_suppressed`** `ds4_server.c:9616`  
  Non ripristina se nel frattempo è stato registrato un altro salvataggio.
- **`kv_cache_slot_suppress_continued`** `ds4_server.c:9608`  
  Avanza il marcatore senza scrivere; -1 indica che non ha soppresso nulla.
- **`kv_cache_store_current`** `ds4_server.c:9539`  
  Se entrambi validi, lo stato Responses ha precedenza su thinking.
- **`kv_cache_store_len`** `ds4_server.c:9445`  
  Può restituire zero e sopprimere il salvataggio.
- **`kv_cache_store_live_prefix`** `ds4_server.c:9532`  
  Usa sempre il testo renderizzato dai token come chiave cache.
- **`kv_cache_store_live_prefix_text`** `ds4_server.c:9509`  
  L'errore dettagliato viene raccolto ma qui non viene registrato.
- **`kv_cache_suppress_continued_store`** `ds4_server.c:9583`  
  Aggiorna un marcatore senza scrivere alcuna cache.
- **`kv_cache_tool_map_hooks`** `ds4_server.c:9497`  
  I callback risultano senza chiamanti diretti nel grafo statico.
- **`kv_cache_tool_map_load_cb`** `ds4_server.c:9493`  
  È invocata indirettamente tramite gli hook del KV store.
- **`kv_cache_tool_map_size_cb`** `ds4_server.c:9483`  
  È invocata indirettamente tramite gli hook del KV store.
- **`kv_cache_tool_map_write_cb`** `ds4_server.c:9488`  
  È invocata indirettamente tramite gli hook del KV store.
- **`kv_cache_try_load`** `ds4_server.c:9691`  
  Una richiesta nulla viene inoltrata come prompt nullo e protocollo non-Responses.
- **`kv_cache_try_load_text`** `ds4_server.c:9665`  
  Azzera gli output prima del tentativo e copia il path solo su successo.
- **`kv_die`** `ds4_kvstore.c:76`  
  Un errore di allocazione termina l'intero servizio
- **`kv_entry_eviction_score`** `ds4_server.c:9387`  
  Non esiste nella build di produzione.
- **`kv_file_size`** `ds4_kvstore.c:131`  
  UINT64_MAX dal backend viene trattato come errore
- **`kv_fill_header`** `ds4_server.c:9328`  
  Forza model_id a zero.
- **`kv_fseek64`** `ds4_kvstore.c:186`  
  Offset oltre INT64_MAX fallisce senza impostare errno
- **`kv_ftruncate`** `ds4_kvstore.c:195`  
  Su POSIX rifiuta dimensioni oltre INT64_MAX
- **`kv_log_name`** `ds4_kvstore.c:258`  
  Senza nome configurato restituisce sempre "ds4"
- **`kv_logf`** `ds4_kvstore.c:262`  
  Senza callback o con errore di formattazione non segnala nulla
- **`kv_mkdir_one`** `ds4_kvstore.c:116`  
  Non considera EEXIST un successo; lo gestisce il chiamante
- **`kv_mkdir_p`** `ds4_kvstore.c:473`  
  EEXIST e' successo anche se il componente esistente non e' una directory
- **`kv_path_exists`** `ds4_kvstore.c:141`  
  Su Windows una conversione UTF-8 fallita equivale a inesistente
- **`kv_rename_replace`** `ds4_kvstore.c:166`  
  Su Windows forza anche la scrittura su disco
- **`kv_tool_map_load_from_pos`** `ds4_server.c:9291`  
  Un record troncato o invalido restituisce il conteggio parziale, non un errore.
- **`kv_tool_map_measure_locked`** `ds4_server.c:9188`  
  La misurazione incrementa scan_clock e modifica i marcatori seen.
- **`kv_tool_map_serialized_size`** `ds4_server.c:9224`  
  Se replay è disabilitato o il testo è vuoto, riporta successo e zero byte.
- **`kv_tool_map_write`** `ds4_server.c:9235`  
  Con replay disabilitato o nessun blocco ritorna successo senza scrivere.
- **`kv_trailer_serialized_size`** `ds4_kvstore.c:1002`  
  Senza callback dichiara successo e dimensione zero
- **`kv_trailer_write`** `ds4_kvstore.c:1010`  
  Senza callback dichiara successo e zero byte
- **`kv_unlink`** `ds4_kvstore.c:151`  
  Su Windows traduce molti errori sconosciuti nel generico EIO
- **`kv_win_error_to_errno`** `ds4_kvstore.c:101`  
  Gli errori non elencati diventano tutti EIO
- **`kv_xmalloc`** `ds4_kvstore.c:81`  
  Una richiesta di zero byte alloca comunque un byte
- **`kv_xrealloc`** `ds4_kvstore.c:87`  
  Una dimensione zero viene trasformata in un byte
- **`kv_xstrdup`** `ds4_kvstore.c:93`  
  Non restituisce mai NULL: termina il processo
- **`layer_attention_mixed_one`** `ds4.c:12962`  
  Il sink aggiunge massa al denominatore ma nessun vettore valore.
- **`layer_attention_mixed_one_decode_scratch`** `ds4.c:13024`  
  Se la capacità non basta termina il processo invece di riallocare.
- **`layer_attention_prefix_batch`** `ds4.c:13170`  
  È valida per un prefisso fresco, non per continuare una cache già popolata.
- **`layer_attention_prefix_batch_worker`** `ds4.c:13109`  
  Il sink resta solo nel denominatore della softmax.
- **`layer_attention_raw_swa_batch`** `ds4.c:13443`  
  Il fast path parallelo è opt-in per presenza di DS4_PARALLEL_ATTN_ROWS.
- **`layer_attention_raw_swa_one`** `ds4.c:13331`  
  Aggiorna la cache prima di calcolare l'attenzione del token.
- **`layer_attention_rows_one`** `ds4.c:10700`  
  Il sink pesa nel denominatore ma non contribuisce alcun vettore valore.
- **`layer_attn_pre_one`** `ds4.c:10137`  
  È chiamata solo dal test della testata motore.
- **`layer_attn_state_bytes`** `ds4.c:48523`  
  Solo ratio 4 raddoppia entrambe le dimensioni interne.
- **`layer_ffn_batch`** `ds4.c:12015`  
  Con steering disattivo evita il buffer somma e usa direttamente hc_post_sum_batch.
- **`layer_ffn_one`** `ds4.c:11832`  
  La sola presenza di DS4_DECODE_PROFILE_DETAIL abilita timing e stampa per ogni layer.
- **`layer_ffn_one_decode_scratch`** `ds4.c:11937`  
  La sola presenza di DS4_DECODE_PROFILE_DETAIL abilita stampa sincrona per layer.
- **`layer_ffn_shared_batch`** `ds4.c:12179`  
  Da 64 token abilita il routing parallelo salvo NO; ROUTED presente vince sempre.
- **`layer_ffn_tokens_parallel`** `ds4.c:12350`  
  Usa layer_ffn_one con trace sempre disattivato.
- **`layer_ffn_tokens_worker`** `ds4.c:12335`  
  È un callback indiretto e richiama il percorso per-token che alloca temporanei.
- **`layer_forward_raw_swa_one`** `ds4.c:13790`  
  DS4_DECODE_PROFILE_DETAIL è un interruttore per sola presenza.
- **`layer_forward_self_one`** `ds4.c:14188`  
  Arrotonda la KV a F16 dopo la quantizzazione FP8 e non conserva alcuna cache.
- **`layer_glm_attention_prefill_f32_ref`** `ds4.c:14438`  
  Con n_tok zero ritorna senza inizializzare l'output.
- **`layer_glm_dense_ffn_one`** `ds4.c:14596`  
  Quantizza una sola volta l'ingresso e riusa i blocchi per gate e up.
- **`layer_glm_dense_ffn_one_f32_ref`** `ds4.c:14632`  
  È F32 solo nell'accumulo: i pesi restano memorizzati Q8_0.
- **`layer_glm_ffn_one`** `ds4.c:15051`  
  La soglia DS4_N_LEADING_DENSE cambia completamente il percorso FFN.
- **`layer_glm_ffn_one_f32_ref`** `ds4.c:14900`  
  Nei layer sparsi somma sempre l'esperto condiviso al ramo routed.
- **`layer_glm_first_token_attention_one`** `ds4.c:14316`  
  Essendo autoattenzione su un solo token, non calcola né query né chiavi.
- **`layer_glm_first_token_attention_one_f32_ref`** `ds4.c:14362`  
  La reference del primo token omette interamente query, chiavi e softmax.
- **`layer_glm_first_token_one`** `ds4.c:15069`  
  Usa l'attenzione speciale che evita Q/K per il singolo token.
- **`layer_glm_first_token_one_f32_ref`** `ds4.c:14932`  
  La reference usa il percorso speciale di autoattenzione a un solo token.
- **`layer_glm_routed_moe_one`** `ds4.c:14989`  
  Il parametro il viene ignorato completamente.
- **`layer_glm_routed_moe_one_f32_ref`** `ds4.c:14785`  
  Riceve mid_all dal chiamante e non lo alloca internamente.
- **`layer_glm_router_selected_experts`** `ds4.c:14663`  
  Il bias influenza la selezione ma non i pesi finali, ricavati dalle probabilità senza bias.
- **`layer_glm_shared_ffn_one_f32_ref`** `ds4.c:14864`  
  Non applica alcun peso router all'esperto condiviso.
- **`layer_glm_sparse_ffn_one`** `ds4.c:15034`  
  L'esperto condiviso viene eseguito sempre, indipendentemente dal router.
- **`layer_grouped_out_batch`** `ds4.c:10786`  
  Alloca su heap host un buffer low proporzionale a n_tok.
- **`layer_grouped_out_one`** `ds4.c:10751`  
  Otto gruppi e rango 1024 sono costanti rigide.
- **`layer_grouped_out_one_decode_scratch`** `ds4.c:10769`  
  Azzera sempre attn_low prima della prima proiezione.
- **`layer_hash_router_weights_from_probs`** `ds4.c:10996`  
  Impone al denominatore un minimo di 2^-14 prima di scalare.
- **`layer_hash_router_weights_one`** `ds4.c:11013`  
  Calcola probabilità per tutti gli esperti anche se l'hash ne ha già scelti sei.
- **`layer_hash_selected_experts`** `ds4.c:10962`  
  La scelta dipende solo dal token ID, non dall'attivazione corrente.
- **`layer_index_state_bytes`** `ds4.c:48528`  
  Solo ratio 4 raddoppia entrambe le dimensioni interne.
- **`layer_kv_projection_normed_one`** `ds4.c:10436`  
  Alloca un buffer raw host a ogni chiamata.
- **`layer_kv_projection_normed_one_decode_scratch`** `ds4.c:10466`  
  Il percorso chiamato decode_scratch è usato anche dal fallback prefill seriale.
- **`layer_q_projection_normed_one`** `ds4.c:10397`  
  Alloca due temporanei host a ogni chiamata.
- **`layer_q_projection_with_lora_one`** `ds4.c:10417`  
  Scrive anche qr_norm oltre all'output q.
- **`layer_q_projection_with_lora_one_decode_scratch`** `ds4.c:10451`  
  Non alloca, ma il fallback prefill seriale usa comunque questo percorso decode.
- **`layer_rope_freq_base`** `ds4.c:10548`  
  Una base compressa non positiva fa usare silenziosamente quella standard.
- **`layer_rope_freq_scale`** `ds4.c:10554`  
  Layer non compresso o fattore non positivo restituisce sempre 1.
- **`layer_routed_moe_batch`** `ds4.c:11362`  
  Raggruppa per esperto attivo; un tipo quantizzato non supportato termina il processo.
- **`layer_routed_moe_one`** `ds4.c:11092`  
  La modalità trace disabilita i kernel fusi ed è vietata per esperti Q8_0 o Q8_K.
- **`layer_routed_moe_one_prealloc`** `ds4.c:11253`  
  Nel percorso Q8_0 ritorna subito dopo la proiezione down.
- **`layer_routed_moe_tokens_parallel`** `ds4.c:12140`  
  La validazione esplicita del layout speciale copre Q8_K, non Q8_0.
- **`layer_router_probs_one`** `ds4.c:10983`  
  Produce punteggi non normalizzati; la normalizzazione avviene dopo la selezione.
- **`layer_shared_ffn_batch`** `ds4.c:10917`  
  Alloca tre buffer host proporzionali a n_tok per gate, up e mid.
- **`layer_shared_ffn_one`** `ds4.c:10839`  
  Alloca cinque buffer host a ogni chiamata.
- **`layer_shared_ffn_one_decode_scratch`** `ds4.c:10873`  
  Evita allocazioni nel percorso caldo usando esclusivamente scratch.
- **`layer_topk_selected_experts`** `ds4.c:11048`  
  La selezione può usare bias che non entrano nei pesi finali.
- **`layer_topk_selected_experts_from_probs`** `ds4.c:11060`  
  Il bias cambia gli esperti scelti, ma i pesi usano i punteggi originali.
- **`ldu32_unaligned`** `ds4_cuda.cu:8522`  
  Puo' leggere fino a tre byte prima di p e quattro byte oltre i quattro richiesti.
- **`le_get32`** `ds4_server.c:9103`  
  Non controlla la dimensione del buffer.
- **`le_put32`** `ds4_server.c:9098`  
  Non controlla dimensione o allineamento del buffer.
- **`linenoise`** `linenoise.c:2600`  
  Accetta al massimo 4095 byte e lascia il resto per la chiamata seguente.
- **`linenoiseAddCompletion`** `linenoise.c:948`  
  Non segnala che la proposta è stata scartata.
- **`linenoiseAdjustFoldsAfterDelete`** `linenoise.c:1356`  
  Qualsiasi sovrapposizione elimina l'intero fold visuale.
- **`linenoiseAdjustFoldsAfterInsert`** `linenoise.c:1338`  
  Inserire esattamente all'inizio sposta il fold invece di estenderlo.
- **`linenoiseAtExit`** `linenoise.c:2650`  
  È registrata indirettamente da enableRawMode, quindi il grafo mostra nessun chiamante.
- **`linenoiseBeep`** `linenoise.c:812`  
  Il segnale va su stderr, non sul descrittore di output dello stato.
- **`linenoiseBlockingEdit`** `linenoise.c:2491`  
  Libera il buffer editor ma restituisce una distinta strdup della riga.
- **`linenoiseBuildHistoryFold`** `linenoise.c:1127`  
  In mask mode disabilita del tutto il folding della cronologia.
- **`linenoiseClearScreen`** `linenoise.c:804`  
  Non controlla errori e non forza il flush.
- **`linenoiseEditBackspace`** `linenoise.c:1980`  
  Dopo un fold cancella tutto l'intervallo nascosto.
- **`linenoiseEditClear`** `linenoise.c:1706`  
  Non scrive il terminatore NUL nel buffer.
- **`linenoiseEditDelete`** `linenoise.c:1968`  
  Sul marcatore di fold cancella tutto l'intervallo nascosto.
- **`linenoiseEditDeletePrevWord`** `linenoise.c:1994`  
  Considera separatore soltanto lo spazio ASCII, non tab o spazi Unicode.
- **`linenoiseEditFeed`** `linenoise.c:2238`  
  NULL simula fine input o errore, non lo stato di continuazione.
- **`linenoiseEditFeedByte`** `linenoise.c:2443`  
  Restituisce sempre NULL.
- **`linenoiseEditGrow`** `linenoise.c:1719`  
  Un buffer fornito dall'API multiplexed non cresce mai perché buflen_max vale zero.
- **`linenoiseEditHistoryNext`** `linenoise.c:1925`  
  Una voce troppo lunga viene troncata silenziosamente con buffer fisso.
- **`linenoiseEditInsert`** `linenoise.c:1775`  
  Un fallimento di crescita restituisce 0, indistinguibile dal successo.
- **`linenoiseEditInsertNoRefresh`** `linenoise.c:1752`  
  Il chiamante deve eseguire il refresh e gestire il fallimento.
- **`linenoiseEditMoveLeft`** `linenoise.c:1890`  
  Attraversare un fold salta tutto il testo nascosto.
- **`linenoiseEditMoveRight`** `linenoise.c:1898`  
  Attraversare un fold salta tutto il testo nascosto.
- **`linenoiseEditNextLen`** `linenoise.c:1266`  
  Un singolo movimento salta tutto il testo nascosto dal fold.
- **`linenoiseEditPaste`** `linenoise.c:2139`  
  Se supera il limite consuma il resto dell'incolla, poi scarta tutto e suona.
- **`linenoiseEditPrevLen`** `linenoise.c:1281`  
  Un singolo movimento salta tutto il testo nascosto dal fold.
- **`linenoiseEditQueueInput`** `linenoise.c:1809`  
  Restituisce sempre -1 senza impostare errno.
- **`linenoiseEditQueuedInput`** `linenoise.c:1805`  
  Ignora completamente lo stato passato.
- **`linenoiseEditSetLayoutCallback`** `linenoise.c:1870`  
  Il callback viene memorizzato ma l'editor fallback non lo invoca.
- **`linenoiseEditSetStatus`** `linenoise.c:1839`  
  Restituisce successo pur ignorando testo e sequenze ANSI.
- **`linenoiseEditStart`** `linenoise.c:2035`  
  Non abilita raw mode né inizializza cronologia o colonne.
- **`linenoiseEditStop`** `linenoise.c:2455`  
  Non ripristina alcuna modalità terminale.
- **`linenoiseFoldAdd`** `linenoise.c:1295`  
  A capacità piena ignora il fold e non impedisce sovrapposizioni.
- **`linenoiseFoldClear`** `linenoise.c:1311`  
  Lascia i vecchi offset nell'array, resi inattivi solo dal conteggio.
- **`linenoiseFoldRemove`** `linenoise.c:1316`  
  Un indice invalido rende enorme la dimensione delle memmove.
- **`linenoiseFree`** `linenoise.c:2630`  
  Non protegge il sentinella linenoiseEditMore.
- **`linenoiseGetRenderFolds`** `linenoise.c:1173`  
  Scarta silenziosamente intervalli vuoti o fuori buffer.
- **`linenoiseHide`** `linenoise.c:1690`  
  Non cancella il prompt visualizzato.
- **`linenoiseHistoryAdd`** `linenoise.c:2662`  
  Restituisce 1 per righe non vuote pur senza creare cronologia.
- **`linenoiseHistoryLoad`** `linenoise.c:2753`  
  Restituisce sempre -1 senza tentare I/O.
- **`linenoiseHistorySave`** `linenoise.c:2725`  
  Restituisce sempre -1 senza tentare I/O.
- **`linenoiseHistorySetMaxLen`** `linenoise.c:2695`  
  Restituisce 1 per limiti positivi ma non memorizza il valore.
- **`linenoiseMakeRawMode`** `linenoise.c:654`  
  Non applica le impostazioni: modifica soltanto la struttura ricevuta.
- **`linenoiseMaskModeDisable`** `linenoise.c:633`  
  È un no-op.
- **`linenoiseMaskModeEnable`** `linenoise.c:628`  
  Non protegge visivamente l'input.
- **`linenoiseNoTTY`** `linenoise.c:2591`  
  Ignora l'eventuale descrittore l->ifd della sessione multiplexed.
- **`linenoisePrintKeyCodes`** `linenoise.c:2518`  
  Non stampa nulla.
- **`linenoiseRangeOverlapsFold`** `linenoise.c:1325`  
  Un intervallo di lunghezza zero non si sovrappone.
- **`linenoiseReadByte`** `linenoise.c:1877`  
  Quando consuma l'ultimo byte azzera gli indici ma conserva la capacità allocata.
- **`linenoiseReadLine`** `linenoise.c:2546`  
  Conserva un CR finale e a EOF restituisce comunque l'ultima riga parziale.
- **`linenoiseRenderBuffer`** `linenoise.c:1198`  
  Anche senza fold alloca e copia l'intero buffer.
- **`linenoiseRestoreRawMode`** `linenoise.c:726`  
  È un no-op.
- **`linenoiseSetCompletionCallback`** `linenoise.c:928`  
  La registrazione sembra riuscire ma non conserva il callback.
- **`linenoiseSetFreeHintsCallback`** `linenoise.c:940`  
  La registrazione è un no-op silenzioso.
- **`linenoiseSetHintsCallback`** `linenoise.c:934`  
  La registrazione è un no-op silenzioso.
- **`linenoiseSetMultiLine`** `linenoise.c:638`  
  L'impostazione è un no-op silenzioso.
- **`linenoiseShow`** `linenoise.c:1695`  
  Non ridisegna il prompt.
- **`linenoiseStatusActive`** `linenoise.c:993`  
  Una stringa vuota equivale a stato disattivato.
- **`linenoiseStatusRows`** `linenoise.c:997`  
  Conta una riga finale anche se il testo termina con newline.
- **`linenoiseTermiosRawFieldsEqual`** `linenoise.c:663`  
  Ignora tutti i campi termios non gestiti da linenoiseMakeRawMode.
- **`listen_on`** `ds4_server.c:12763`  
  Non risolve nomi host diversi da localhost e non supporta IPv6.
- **`live_state_contains_all`** `ds4_server.c:12304`  
  Una lista richiesta vuota restituisce false, non true vacuo.
- **`live_text_prefix_prompt`** `ds4_server.c:9702`  
  Ritokenizza il suffisso per evitare fusioni BPE attraverso la frontiera.
- **`live_tool_state_clear_locked`** `ds4_server.c:8737`  
  Svuota gli ID ma conserva la capacità allocata del loro vettore.
- **`live_tool_state_free`** `ds4_server.c:8747`  
  Prima conserva la capacità durante clear, poi libera esplicitamente il vettore.
- **`load_i8x4_i32_aligned`** `rocm/ds4_rocm_q8.cuh:10`  
  Un puntatore non allineato viene reinterpretato comunque come int32_t.
- **`load_i8x4_i32_unaligned`** `rocm/ds4_rocm_q8.cuh:14`  
  Ricostruisce sempre ordine little-endian invece di fare una singola load a 32 bit.
- **`log_context_memory`** `ds4_server.c:12885`  
  È una stima; capacità e consumo reali dipendono dal backend.
- **`log_decode_progress`** `ds4_server.c:10224`  
  Aggiorna i riferimenti temporali anche se il logging è filtrato altrove.
- **`log_flags`** `ds4_server.c:10207`  
  La lunghezza usata cresce anche oltre il buffer dopo un troncamento snprintf.
- **`log_tool_calls_summary`** `ds4_server.c:10622`  
  Sostituisce campi mancanti con ? e non segnala l'anomalia.
- **`logits_top2`** `ds4.c:37056`  
  Con meno di due valori utili lascia un indice a -1.
- **`main`** `ds4_server.c:17851`  
  Con --dump-tokens non apre il motore e termina dopo la tokenizzazione statica.
- **`make_bash_order`** `ds4_server.c:13810`  
  Lo schema non elenca timeout, presente in alcune call di test.
- **`make_swapped_bash_call`** `ds4_server.c:13801`  
  L'ordine intenzionale è description, command, timeout.
- **`mark_case_pending`** `ds4_eval.c:3651`  
  Conserva i contatori di token precedenti.
- **`matmul_f16_f32_sharedx_warp_rows_w32_kernel`** `rocm/ds4_rocm_common.cuh:147`  
  Gestisce un solo vettore x; il launcher la usa solo con n_tok uguale a 1.
- **`matmul_f16_kernel`** `rocm/ds4_rocm_common.cuh:87`  
  Oltre 256 thread sfora partial; una blockDim non potenza di due perde termini
- **`matmul_f16_ordered_chunks_kernel`** `rocm/ds4_rocm_common.cuh:115`  
  Il thread 0 somma serialmente i 32 parziali; il percorso e' usato solo senza cuBLAS.
- **`matmul_f16_pair_f32_sharedx_warp_rows_w32_kernel`** `rocm/ds4_rocm_common.cuh:183`  
  Scrive due output per riga ma non supporta batch.
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
- **`matmul_q8_0_batch`** `ds4.c:7796`  
  Alloca e libera due buffer CPU proporzionali a n_tok a ogni chiamata.
- **`matmul_q8_0_batch_prequant`** `ds4.c:7741`  
  Parallelizza sulle righe d'uscita, non sui token.
- **`matmul_q8_0_batch_worker`** `ds4.c:7567`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matmul_q8_0_f32_batch_sharedx_warp_rows_w32_toktile_kernel`** `rocm/ds4_rocm_q8.cuh:611`  
  I token mancanti nell'ultima tile vengono materializzati come zeri in shared
- **`matmul_q8_0_f32_batch_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:495`  
  Rilegge le attivazioni per ogni riga di output senza condividerle
- **`matmul_q8_0_f32_batch_wmma_4w_kernel`** `rocm/ds4_rocm_q8.cuh:683`  
  Converte attivazioni e pesi dequantizzati in FP16 prima della WMMA
- **`matmul_q8_0_f32_batch_wmma_onthefly_kernel`** `rocm/ds4_rocm_q8.cuh:785`  
  Converte sia input sia pesi dequantizzati in FP16 prima dell'accumulo
- **`matmul_q8_0_f32_sharedx_warp_rows_w32_kernel`** `rocm/ds4_rocm_q8.cuh:465`  
  Ricopia l'intero input in shared per ogni blocco di righe di output
- **`matmul_q8_0_f32_small_block_w32_kernel`** `rocm/ds4_rocm_q8.cuh:415`  
  Usa un intero blocco GPU per una sola riga di output
- **`matmul_q8_0_f32_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:440`  
  Non quantizza x: dequantizza i pesi durante ogni prodotto
- **`matmul_q8_0_grouped_batch`** `ds4.c:8049`  
  Alloca scratch CPU proporzionale a token per gruppi per blocchi.
- **`matmul_q8_0_grouped_batch_worker`** `ds4.c:7532`  
  Il token dispari finale passa per un kernel diverso da quello a coppie.
- **`matmul_q8_0_hc_expand_f32_sharedx_warp_rows_w32_kernel`** `rocm/ds4_rocm_q8.cuh:1095`  
  block_out esclude sempre block_add, che entra soltanto in out_hc
- **`matmul_q8_0_hc_expand_f32_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:1047`  
  block_out riceve il dot puro, mentre out_hc include block_add se presente
- **`matmul_q8_0_hc_expand_preq_rows_w32_kernel`** `rocm/ds4_rocm_q8.cuh:998`  
  Ignora i primi n_hc valori di split
- **`matmul_q8_0_hc_expand_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:302`  
  Se has_owned_slots e' vero ignora completamente block_add e block_add2.
- **`matmul_q8_0_hc_partial16_w32_kernel`** `rocm/ds4_rocm_q8.cuh:1169`  
  Non riceve n_blocks: ogni split legge sempre esattamente 512 valori
- **`matmul_q8_0_hc_partial_w32_kernel`** `rocm/ds4_rocm_q8.cuh:1201`  
  Split eccedenti producono silenziosamente una matrice parziale di zeri
- **`matmul_q8_0_kernel`** `rocm/ds4_rocm_q8.cuh:38`  
  Riquantizza gli stessi blocchi di attivazione separatamente per ogni riga d'uscita.
- **`matmul_q8_0_kslice_hc_expand_add_preq_warp8_kernel`** `ds4_cuda.cu:8119`  
  block_out riceve solo il dot della fetta, mentre out_hc include sempre block_add.
- **`matmul_q8_0_kslice_preq_warp8_kernel`** `ds4_cuda.cu:7737`  
  Scrive il prodotto della sola fetta: non lo accumula su un valore d'uscita preesistente.
- **`matmul_q8_0_mma_exact_kernel`** `ds4_cuda.cu:8547`  
  Su architetture precedenti a SM80 l'MMA non accumula e l'output diventa zero.
- **`matmul_q8_0_pair_batch`** `ds4.c:7816`  
  Alloca e libera due buffer CPU proporzionali al batch a ogni chiamata.
- **`matmul_q8_0_pair_batch_prequant`** `ds4.c:7763`  
  Parallelizza sulle righe d'uscita e condivide xq fra le due matrici.
- **`matmul_q8_0_pair_batch_worker`** `ds4.c:7595`  
  Per token dispari usa il kernel a due righe invece di quello a due token.
- **`matmul_q8_0_pair_f32_sharedx_warp_rows_w32_kernel`** `rocm/ds4_rocm_q8.cuh:900`  
  Non gestisce una coda K parziale: il chiamante deve escluderla
- **`matmul_q8_0_pair_f32_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:858`  
  Supporta dimensioni di output diverse senza richiedere padding
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
- **`matmul_q8_0_preq_rows_w32_kernel`** `rocm/ds4_rocm_q8.cuh:177`  
  Un rows_per_block incoerente salta o sovrappone righe senza errore
- **`matmul_q8_0_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:150`  
  Il tok deriva da blockIdx.y senza un parametro n_tok: la griglia deve limitarlo correttamente.
- **`matmul_q8_0_top1_preq_warp8_kernel`** `ds4_cuda.cu:7677`  
  Le parita' di score scelgono l'indice globale minore grazie alla codifica della chiave.
- **`matmul_q8_0_top1_unpack_kernel`** `ds4_cuda.cu:7725`  
  Se nessun candidato aggiorna la chiave zero, emette indice UINT32_MAX e un NaN.
- **`matvec_any`** `ds4.c:8127`  
  Ogni altro tipo termina il processo invece di usare un fallback generico.
- **`matvec_any_decode_scratch`** `ds4.c:7960`  
  Per F32 e F16 il fallback ignora lo scratch e può usare un percorso con allocazioni.
- **`matvec_expert_down`** `ds4.c:9827`  
  I rami IQ2_XXS e Q4_K riallocano e riquantizzano l'input a ogni chiamata.
- **`matvec_expert_pair_prequant`** `ds4.c:9770`  
  Nel ramo Q4_K il tipo di w1 non viene verificato esplicitamente.
- **`matvec_experts_down_accum_prequant`** `ds4.c:9749`  
  Non esiste fallback generico: un tipo non supportato termina il processo.
- **`matvec_experts_mid_prequant`** `ds4.c:9721`  
  Il dispatch considera il tipo gate; un formato non previsto termina il processo.
- **`matvec_f16`** `ds4.c:7092`  
  Riconosce F16 tramite il valore numerico 1 del tipo.
- **`matvec_f16_worker`** `ds4.c:7082`  
  Non ha chiamate dirette: il parallel-for la invoca come callback.
- **`matvec_f32`** `ds4.c:8114`  
  Usa accumulo double nel worker, quindi può differire da un kernel F32 puro.
- **`matvec_f32_worker`** `ds4.c:8101`  
  Accumula in double e converte in float solo alla fine.
- **`matvec_iq2_xxs_accum_worker`** `ds4.c:8834`  
  Sovrascrive out con la somma, non accumula sul valore precedente.
- **`matvec_iq2_xxs_batch_accum_rows_worker`** `ds4.c:9693`  
  L'azzeramento di moe avviene dentro il worker per intervallo di righe.
- **`matvec_iq2_xxs_batch_mid_worker`** `ds4.c:8984`  
  Moltiplica il peso di routing prima della proiezione down.
- **`matvec_iq2_xxs_expert_pair_prequant`** `ds4.c:8203`  
  Non applica né SiLU né peso del router: restituisce le due proiezioni grezze.
- **`matvec_iq2_xxs_experts_accum_prequant`** `ds4.c:8849`  
  Le attivazioni xq sono contigue per slot di routing.
- **`matvec_iq2_xxs_experts_mid_prequant`** `ds4.c:8348`  
  Applica il peso del router nello hidden prima della successiva proiezione down.
- **`matvec_iq2_xxs_mid_worker`** `ds4.c:8279`  
  clamp minore o uguale a 1e-6 lo disabilita; gate è limitato solo superiormente.
- **`matvec_iq2_xxs_pair_worker`** `ds4.c:8192`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matvec_q2_k_accum_worker`** `ds4.c:8549`  
  Non applica pesi del router: presume che siano già incorporati negli hidden quantizzati.
- **`matvec_q2_k_batch_accum_rows_worker`** `ds4.c:9170`  
  Azzera prima ogni riga di tutti i token.
- **`matvec_q2_k_batch_down_worker`** `ds4.c:9133`  
  È marcata MAYBE_UNUSED e non viene referenziata.
- **`matvec_q2_k_batch_mid_worker`** `ds4.c:8914`  
  Il clamp è disattivato quando vale al massimo 1e-6.
- **`matvec_q2_k_expert`** `ds4.c:8513`  
  Alloca scratch CPU per chiamata; il commento la destina soprattutto a tracing e diagnostica.
- **`matvec_q2_k_experts_accum_prequant`** `ds4.c:8566`  
  xq deve concatenare un'attivazione Q8_K distinta per esperto, senza metadati di lunghezza.
- **`matvec_q2_k_experts_mid_prequant`** `ds4.c:8646`  
  Applica il peso del router prima che gli hidden siano quantizzati per la proiezione down.
- **`matvec_q2_k_mid_worker`** `ds4.c:8622`  
  clamp minore o uguale a 1e-6 lo disabilita; gate è limitato solo superiormente.
- **`matvec_q2_k_worker`** `ds4.c:8504`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matvec_q4_k_accum_worker`** `ds4.c:9296`  
  Sovrascrive out anziché aggiungere al contenuto esistente.
- **`matvec_q4_k_batch_accum_rows_worker`** `ds4.c:9650`  
  Azzera l'output per tutti i token prima della somma.
- **`matvec_q4_k_batch_mid_worker`** `ds4.c:9599`  
  Applica il peso di routing direttamente al mid.
- **`matvec_q4_k_experts_accum_prequant`** `ds4.c:9311`  
  xq è suddiviso per slot nell'ordine di selected.
- **`matvec_q4_k_experts_mid_prequant`** `ds4.c:9239`  
  Copia i pesi di routing in un array fisso per slot.
- **`matvec_q4_k_mid_worker`** `ds4.c:9215`  
  Il clamp si attiva solo oltre 1e-6 e non limita gate negativo.
- **`matvec_q5_q6_k_accum_worker`** `ds4.c:9519`  
  Sovrascrive out con la somma calcolata.
- **`matvec_q5_q6_k_expert`** `ds4.c:9479`  
  Alloca e quantizza un temporaneo host a ogni chiamata.
- **`matvec_q5_q6_k_experts_accum_prequant`** `ds4.c:9535`  
  Un solo type del tensore governa tutti gli esperti.
- **`matvec_q5_q6_k_experts_mid_prequant`** `ds4.c:9427`  
  Accetta una coppia mista Q5_K e Q6_K.
- **`matvec_q5_q6_k_mid_worker`** `ds4.c:9402`  
  Gate e up possono avere formati diversi tra Q5_K e Q6_K.
- **`matvec_q5_q6_k_worker`** `ds4.c:9377`  
  È una callback parallela usata dalla sola proiezione esperto di tracing.
- **`matvec_q8_0`** `ds4.c:7865`  
  È un wrapper di una riga; la variante normale alloca scratch CPU ogni volta.
- **`matvec_q8_0_3d_slice`** `ds4.c:7690`  
  Alloca due buffer heap a ogni chiamata, ma nel grafo corrente non ha chiamanti.
- **`matvec_q8_0_3d_slice_prequant`** `ds4.c:7662`  
  Calcola lo stride della slice dal formato, non da metadati espliciti.
- **`matvec_q8_0_accum_worker`** `ds4.c:8706`  
  Non accumula su out: lo sovrascrive con la somma.
- **`matvec_q8_0_batch_accum_rows_worker`** `ds4.c:9928`  
  Azzera l'output prima della somma delle coppie.
- **`matvec_q8_0_batch_mid_worker`** `ds4.c:9069`  
  Il peso del router è incorporato nel mid, non applicato dopo la down.
- **`matvec_q8_0_decode_scratch`** `ds4.c:7938`  
  Quantizza di nuovo l'input a ogni proiezione che non condivide lo scratch quantizzato.
- **`matvec_q8_0_experts_accum_prequant`** `ds4.c:8720`  
  xq e xscale sono impacchettati per slot, non indicizzati per ID esperto.
- **`matvec_q8_0_experts_mid_prequant`** `ds4.c:8395`  
  È marcata MAYBE_UNUSED anche se compare nei percorsi MoE CPU.
- **`matvec_q8_0_f32_ref`** `ds4.c:7908`  
  Accetta ndim maggiore di 2 e appiattisce tutte le righe tramite elements/dim[0].
- **`matvec_q8_0_f32_ref_worker`** `ds4.c:7897`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matvec_q8_0_grouped_rows`** `ds4.c:7973`  
  Alloca buffer CPU separati per tutti i gruppi a ogni chiamata.
- **`matvec_q8_0_grouped_rows_decode_scratch`** `ds4.c:8012`  
  Il check di capacità usa n_groups*group_dim e non include il padding per gruppo.
- **`matvec_q8_0_grouped_worker`** `ds4.c:7518`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matvec_q8_0_mid_worker`** `ds4.c:8301`  
  clamp minore o uguale a 1e-6 lo disabilita; gate è limitato solo superiormente.
- **`matvec_q8_0_pair_decode_scratch`** `ds4.c:7948`  
  La capacità è verificata sulla prima matrice prima di validare la coppia.
- **`matvec_q8_0_pair_prequant`** `ds4.c:7712`  
  Non controlla la capacità dei due output o dei buffer quantizzati.
- **`matvec_q8_0_pair_worker`** `ds4.c:7507`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matvec_q8_0_prequant`** `ds4.c:7653`  
  È solo un wrapper e delega ogni controllo alla funzione per intervalli.
- **`matvec_q8_0_rows`** `ds4.c:7843`  
  Alloca e libera xq e scale anche quando si richiedono poche righe.
- **`matvec_q8_0_rows_prequant`** `ds4.c:7626`  
  Non verifica la capacità né la provenienza dei buffer xq e xscale.
- **`matvec_q8_0_worker`** `ds4.c:7497`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`matvec_q8_k_accum_worker`** `ds4.c:8771`  
  Sovrascrive ogni elemento di out invece di aggiungerlo.
- **`matvec_q8_k_batch_accum_rows_worker`** `ds4.c:9884`  
  Azzera ogni elemento moe prima di visitare gli esperti.
- **`matvec_q8_k_batch_mid_worker`** `ds4.c:9017`  
  Un clamp pari a zero non limita nulla.
- **`matvec_q8_k_experts_accum_prequant`** `ds4.c:8786`  
  Il blocco xq è ordinato per slot selezionato, non per ID esperto.
- **`matvec_q8_k_experts_mid_prequant`** `ds4.c:8447`  
  È marcata MAYBE_UNUSED anche se compare nei percorsi MoE CPU.
- **`matvec_q8_k_mid_worker`** `ds4.c:8324`  
  clamp minore o uguale a 1e-6 lo disabilita; gate è limitato solo superiormente.
- **`max_abs_diff`** `ds4.c:15163`  
  I NaN possono essere ignorati perché il confronto con max_diff risulta falso.
- **`maybe_warn_distributed_step_shape`** `ds4_bench.c:550`  
  Con passo moltiplicativo non avverte anche se gli incrementi iniziali sono sotto il chunk.
- **`mc_letter_is_negated`** `ds4_eval.c:2776`  
  Non attraversa newline e ignora formulazioni di negazione fuori dal piccolo elenco.
- **`metal_graph_align_mixed_workspace`** `ds4.c:64237`  
  Cambia solo i puntatori: non copia né sincronizza la VRAM.
- **`metal_graph_alloc`** `ds4.c:17726`  
  Fissa raw e contesto a DS4_N_SWA, prefill a 1 e disabilita MTP e TP.
- **`metal_graph_alloc_kv_cache_tensor`** `ds4.c:16409`  
  Forza sempre l'allocazione sul tier zero.
- **`metal_graph_alloc_kv_cache_tensor_on`** `ds4.c:16391`  
  DS4_CUDA_KV_STAGED_RING vale solo su CUDA mono-GPU e con 1 ignora managed.
- **`metal_graph_alloc_raw_cap`** `ds4.c:17098`  
  Capacità raw, contesto o prefill pari a zero vengono corrette almeno a uno.
- **`metal_graph_apply_directional_steering`** `ds4.c:16204`  
  Se grafo, direzioni o scala mancano, restituisce successo senza modificare x.
- **`metal_graph_apply_directional_steering_attn`** `ds4.c:16219`  
  Con g nullo passa scala zero e produce un no-op riuscito.
- **`metal_graph_apply_directional_steering_ffn`** `ds4.c:16227`  
  Con g nullo passa scala zero e produce un no-op riuscito.
- **`metal_graph_attention_output_dense_quant_batch`** `ds4.c:25198`  
  Se il kernel Q4_K batch fallisce, ripiega silenziosamente sul lento ciclo per token.
- **`metal_graph_attention_output_dense_quant_low`** `ds4.c:25078`  
  Il fast path Q8_0 vale solo da group0 zero; altrimenti crea e libera viste per ogni gruppo.
- **`metal_graph_attention_output_dense_quant_tp`** `ds4.c:25143`  
  Il kernel TP fuso si usa solo se entrambi i pesi sono Q8_0; altrimenti esegue due passaggi.
- **`metal_graph_attn_comp_cache_is_f16`** `ds4.c:20123`  
  È un valore fissato a compilazione, non una proprietà del tensore.
- **`metal_graph_attn_comp_cache_row_bytes`** `ds4.c:20118`  
  La dimensione dipende da una costante di compilazione FP16/F32.
- **`metal_graph_attn_comp_prefill_target`** `ds4.c:20193`  
  In FP16 ignora layer, prima riga e numero di righe e restituisce lo staging.
- **`metal_graph_attn_comp_prefill_target_free`** `ds4.c:20205`  
  In FP16 non libera nulla.
- **`metal_graph_attn_comp_row_view`** `ds4.c:20179`  
  In FP16 ignora layer e riga e crea sempre la vista sullo staging a offset zero.
- **`metal_graph_attn_comp_update_row`** `ds4.c:20166`  
  In FP16 qualsiasi riga diventa zero.
- **`metal_graph_attn_comp_update_target`** `ds4.c:20158`  
  In FP16 ignora il e restituisce sempre lo staging condiviso.
- **`metal_graph_bind_attn_pre_batch_row`** `ds4.c:62692`  
  I puntatori diventano viste contenute nell'alias: occorre fare unbind prima del ritorno.
- **`metal_graph_borrow_tensor_view`** `ds4.c:21748`  
  La vista ha owner=0: liberarla non deve liberare né trattenere il backing.
- **`metal_graph_build_prefill_stages`** `ds4.c:33031`  
  Tornare a un tier già visto crea un nuovo stadio e può eccedere il limite.
- **`metal_graph_capture_prefill_seed_router_selected`** `ds4.c:29874`  
  Con k zero restituisce true senza azzerare un eventuale prefill_seed_tokens precedente.
- **`metal_graph_capture_prefix1_attn_state`** `ds4.c:19801`  
  Se capture o destinazione KV mancano restituisce successo senza copiare.
- **`metal_graph_capture_prefix1_index_state`** `ds4.c:19811`  
  Se capture o destinazione KV mancano restituisce successo senza copiare.
- **`metal_graph_check_hc_norm_fusion`** `ds4.c:19998`  
  Sincronizza la GPU, alloca tre tensori e fa quattro readback a ogni verifica.
- **`metal_graph_commit_attn_comp_stage`** `ds4.c:20170`  
  In F32 restituisce successo senza copiare nulla.
- **`metal_graph_configure_dspark_capture`** `ds4.c:16235`  
  Un errore lascia allocazioni parziali nel grafo, da liberare in seguito.
- **`metal_graph_context_bytes_for_kv_policy`** `ds4.c:16366`  
  Il totale include scratch oltre alla cache restituita separatamente.
- **`metal_graph_copy_prefill_workspace_pointers`** `ds4.c:15919`  
  È una copia superficiale: entrambi i grafi puntano agli stessi tensori.
- **`metal_graph_cuda_greedy_max_segment`** `ds4.c:16949`  
  Zero o un valore invalido disabilita il limite; gli invalidi producono un avviso.
- **`metal_graph_cuda_greedy_split_top1_requested`** `ds4.c:16783`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_greedy_splitkv_fallback_requested`** `ds4.c:16911`  
  È attivo di default tramite soglia 0,25; NO oppure soglia zero lo spegne.
- **`metal_graph_cuda_greedy_splitkv_margin_threshold`** `ds4.c:16891`  
  Assente o invalida vale 0,25; zero disabilita il fallback esatto.
- **`metal_graph_cuda_greedy_splitkv_max_segment`** `ds4.c:16967`  
  Zero, assenza o valore invalido significano limite disabilitato.
- **`metal_graph_cuda_greedy_splitkv_may_engage`** `ds4.c:19780`  
  Se la richiesta greedy è spenta non valuta nemmeno il numero di score.
- **`metal_graph_cuda_greedy_splitkv_min_score`** `ds4.c:16983`  
  Valori invalidi sono ignorati; il default è 0 con SPLITKV_DECODE, altrimenti 512.
- **`metal_graph_cuda_greedy_splitkv_pair_replay_requested`** `ds4.c:16939`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_greedy_splitkv_requested`** `ds4.c:16811`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_greedy_splitkv_top2_requested`** `ds4.c:16921`  
  È attivo di default, ma il flag NO non vuoto e diverso da 0 prevale.
- **`metal_graph_cuda_greedy_splitkv_trust_replay_requested`** `ds4.c:16931`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_greedy_vec4_fallback_requested`** `ds4.c:16881`  
  È attivo di default tramite soglia 0,25; NO oppure soglia zero lo spegne.
- **`metal_graph_cuda_greedy_vec4_margin_threshold`** `ds4.c:16861`  
  Assente o invalida vale 0,25; zero disabilita il fallback esatto.
- **`metal_graph_cuda_greedy_vec4_max_segment`** `ds4.c:16975`  
  Zero, assenza o valore invalido significano limite disabilitato.
- **`metal_graph_cuda_greedy_vec4_requested`** `ds4.c:16821`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_output_fused_top1_requested`** `ds4.c:16793`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_prefill_pipeline_microbatch`** `ds4.c:17050`  
  Accetta anche un numero con suffisso non numerico; zero o invalido usa 512.
- **`metal_graph_cuda_prefill_pipeline_q8_cache_requested`** `ds4.c:17042`  
  È spenta di default; qualunque valore non vuoto diverso da 0 la abilita.
- **`metal_graph_cuda_prefill_pipeline_requested`** `ds4.c:17031`  
  Senza override segue cuda_tp_decode; una stringa vuota è trattata come assente.
- **`metal_graph_cuda_q_norm_rope_fuse_requested`** `ds4.c:16996`  
  È attiva di default; solo il valore esatto 0 la disabilita.
- **`metal_graph_cuda_qkv_kv_rope_fuse_requested`** `ds4.c:17004`  
  La sola presenza di DISABLE_QKV_RMS_FUSED, anche con valore 0, la disabilita.
- **`metal_graph_cuda_splitkv_score_may_engage`** `ds4.c:19757`  
  Basta un solo layer sopra soglia per attivarlo globalmente.
- **`metal_graph_cuda_splitkv_spec_batch_verify_requested`** `ds4.c:16851`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_splitkv_spec_requested`** `ds4.c:16831`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_splitkv_spec_toponly_row0_requested`** `ds4.c:16841`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_cuda_stream_prefill_batch_selected_addr_enabled`** `ds4.c:18145`  
  Anche le variabili DS4_METAL_DISABLE, presenti con valore 0, disabilitano il percorso.
- **`metal_graph_cuda_stream_prefill_batch_selected_load`** `ds4.c:21183`  
  DISABLE restituisce successo senza caricare; fuori CUDA il percorso è un no-op riuscito.
- **`metal_graph_cuda_tp_attn_cache_copy_row`** `ds4.c:20227`  
  Con zero byte restituisce successo anche se i tensori sono nulli.
- **`metal_graph_cuda_tp_attn_cache_dup_layer_ready`** `ds4.c:20209`  
  Con rapporto zero non richiede le cache compresse duplicate.
- **`metal_graph_cuda_tp_attn_cache_dup_requested`** `ds4.c:16637`  
  Su Apple è sempre falso; su CUDA il default è disattivo.
- **`metal_graph_cuda_tp_attn_cache_sync_all`** `ds4.c:20255`  
  Se la duplicazione è disattiva restituisce successo senza controllare i layer.
- **`metal_graph_cuda_tp_attn_cache_sync_raw_row`** `ds4.c:20241`  
  Se il layer non è duplicabile restituisce successo senza sincronizzare.
- **`metal_graph_cuda_tp_attn_heads_requested`** `ds4.c:16629`  
  Su Apple è sempre falso; su CUDA il default è disattivo.
- **`metal_graph_cuda_tp_attn_peer_read_requested`** `ds4.c:16621`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_attn_requested`** `ds4.c:16613`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_ep_balanced_shared_mid_requested`** `ds4.c:16693`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_ep_delay_reduce_requested`** `ds4.c:16669`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_ep_direct_return_requested`** `ds4.c:16661`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_ep_dual_prequant_requested`** `ds4.c:16702`  
  È attiva di default; solo il valore esatto 0 la disabilita.
- **`metal_graph_cuda_tp_ep_finish_reduce`** `ds4.c:21764`  
  Con direct_return attende soltanto il peer; con combine=false lascia il risultato non combinato.
- **`metal_graph_cuda_tp_ep_fused_hc_reduce_requested`** `ds4.c:16677`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_ep_fused_shared_mid_requested`** `ds4.c:16685`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_ep_pack_exact_requested`** `ds4.c:16653`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_moe_copy3_handoff_requested`** `ds4.c:16727`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_tp_moe_delay_reduce_requested`** `ds4.c:16711`  
  È attiva di default; solo il valore esatto 0 la disabilita.
- **`metal_graph_cuda_tp_moe_pack_handoff_requested`** `ds4.c:16719`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_tp_moe_peer_read_requested`** `ds4.c:16735`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_tp_moe_peer_router_requested`** `ds4.c:16743`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_tp_moe_requested`** `ds4.c:16645`  
  Su Apple è sempre falso; su CUDA il default è attivo.
- **`metal_graph_cuda_tp_output_requested`** `ds4.c:16775`  
  È attiva di default; solo il valore esatto 0 la disabilita.
- **`metal_graph_cuda_tp_output_requested_ways`** `ds4.c:70`  
  Il default è 8, ma un valore non valido forza 2 dopo un avviso.
- **`metal_graph_cuda_tp_output_tiers`** `ds4.c:17067`  
  Con grafo nullo restituisce zero senza modificare l'array.
- **`metal_graph_cuda_tp_output_tiers_for_head`** `ds4.c:84`  
  Restituisce 0 senza errore se TP è disattivo o la topologia non è valida.
- **`metal_graph_cuda_tp_partner_tier`** `ds4.c:17060`  
  Un tier della metà superiore restituisce -1 invece del partner simmetrico.
- **`metal_graph_cuda_tp_prefill_attn_output_requested`** `ds4.c:17023`  
  È attivo di default; solo il valore esatto 0 lo disabilita.
- **`metal_graph_cuda_tp_prefill_ffn_requested`** `ds4.c:17015`  
  È attivo di default; solo il valore esatto 0 lo disabilita.
- **`metal_graph_cuda_tp_q_requested`** `ds4.c:16767`  
  È spenta di default; qualunque valore non vuoto diverso da 0 la abilita.
- **`metal_graph_cuda_tp_shared_fold_requested`** `ds4.c:16759`  
  È attivo di default; solo il valore esatto 0 lo disabilita.
- **`metal_graph_cuda_tp_shared_requested`** `ds4.c:16751`  
  È spento di default; qualunque valore non vuoto diverso da 0 lo abilita.
- **`metal_graph_cuda_verify_decode2_split_top1_requested`** `ds4.c:16801`  
  Il flag NO non vuoto e diverso da 0 prevale sempre sull'abilitazione.
- **`metal_graph_debug_dump_f16_tensor`** `ds4.c:16508`  
  Il prefisso del file è riletto, ma il consenso al dump usa la configurazione in cache.
- **`metal_graph_debug_dump_i32_tensor`** `ds4.c:16541`  
  Ogni dump sincronizza la GPU e poi riavvia il batch di comandi.
- **`metal_graph_debug_dump_tensor`** `ds4.c:16474`  
  Ogni dump sincronizza la GPU e poi riavvia il batch di comandi.
- **`metal_graph_debug_get_config`** `ds4.c:16433`  
  La configurazione è static e ignora modifiche successive all'ambiente.
- **`metal_graph_debug_prefix_for`** `ds4.c:16461`  
  Il filtro cerca il nome richiesto dentro la stringa configurata, non il contrario.
- **`metal_graph_debug_wants`** `ds4.c:16470`  
  Eredita una configurazione ambientale letta una sola volta.
- **`metal_graph_decode_cpu_router`** `ds4.c:20918`  
  Chiude e riapre il batch comandi, imponendo readback e sincronizzazione per ogni layer.
- **`metal_graph_decode_cpu_router_applicable`** `ds4.c:20462`  
  Il ramo Pro Q4 può risultare vero anche con g nullo.
- **`metal_graph_decode_cuda_selected_load`** `ds4.c:21111`  
  Su ROCm, Apple o build senza GPU restituisce false senza operare.
- **`metal_graph_decode_cuda_selected_slots_expected`** `ds4.c:20604`  
  Su CUDA consulta env DS4_METAL_*; la loro sola presenza disabilita.
- **`metal_graph_decode_hc_pre`** `ds4.c:19937`  
  Il flag DISABLE_HC_FUSION sceglie il percorso più lento a due kernel.
- **`metal_graph_decode_indexer_sparse_threshold`** `ds4.c:19821`  
  Legge l'env una sola volta; valori invalidi stampano errore e lasciano 1024.
- **`metal_graph_decode_iq2_selected_slots_expected`** `ds4.c:20546`  
  Richiede top-6, almeno 128 esperti e tipi IQ2/IQ2/Q2 esatti.
- **`metal_graph_decode_kv_store`** `ds4.c:20100`  
  Il percorso di riferimento quantizza prima kv e poi lo copia nella cache.
- **`metal_graph_decode_pro_q4_expert_table_expected`** `ds4.c:20491`  
  Richiede esattamente 384 esperti, top-6 e almeno 2 GiB per gate e down.
- **`metal_graph_decode_q4_selected_slots_expected`** `ds4.c:20517`  
  Se è attesa la tabella Pro Q4 restituisce falso: i due percorsi sono esclusivi.
- **`metal_graph_decode_raw_score_count`** `ds4.c:19734`  
  Il conteggio è sempre troncato a 256 score.
- **`metal_graph_decode_selected_readahead_override`** `ds4.c:21004`  
  Termina e riavvia i comandi GPU; deduplica gli ID prima del solo readahead, non dell'override.
- **`metal_graph_decode_set_hash_selected_override`** `ds4.c:20867`  
  Senza routing hash o slot selettivi applicabili restituisce successo senza fare nulla.
- **`metal_graph_decode_stage_profile_enabled`** `ds4.c:26959`  
  Basta che uno dei due set di variabili ROCm o Metal corrisponda.
- **`metal_graph_decode_test`** `ds4.c:25596`  
  Non testa il prompt intero né altri layer; scambia i puntatori HC prima dell'head.
- **`metal_graph_dense_quant_row_bytes`** `ds4.c:25005`  
  Azzera row_bytes prima di validare, quindi un fallimento sovrascrive il valore precedente.
- **`metal_graph_directional_steering_attn_enabled`** `ds4.c:16194`  
  Una scala nonzero non basta: serve il tensore direzioni sul tier attivo.
- **`metal_graph_directional_steering_ffn_enabled`** `ds4.c:16199`  
  Una scala nonzero non basta: serve il tensore direzioni sul tier attivo.
- **`metal_graph_dspark_cache_claim_appended_row`** `ds4.c:26141`  
  Non puo' iniziare una cache vuota: in quel caso restituisce false.
- **`metal_graph_dspark_cache_crop_to_prefix`** `ds4.c:26117`  
  Un prefisso fuori finestra azzera la cache ma restituisce true.
- **`metal_graph_dspark_cache_current_window_valid`** `ds4.c:26090`  
  La finestra vuota risulta valida.
- **`metal_graph_dspark_cache_ends_at`** `ds4.c:26133`  
  Una cache vuota termina a qualunque posizione.
- **`metal_graph_dspark_cache_reset`** `ds4.c:26067`  
  Resetta solo start e lunghezza: non cancella né libera il contenuto sottostante.
- **`metal_graph_dspark_cache_set_window`** `ds4.c:26099`  
  Con len zero azzera entrambi gli indici ignorando token_start.
- **`metal_graph_dspark_cache_window_valid`** `ds4.c:26074`  
  Una finestra vuota e' valida anche con capacita' zero.
- **`metal_graph_dspark_capture_batch_invalidate`** `ds4.c:26054`  
  Se capture_enabled è falso non pulisce eventuale stato residuo.
- **`metal_graph_dspark_capture_batch_note_slot`** `ds4.c:26226`  
  Una finestra diversa invalida l'intera cattura batch.
- **`metal_graph_dspark_capture_begin`** `ds4.c:26193`  
  Se la cattura e' disabilitata non pulisce eventuale stato residuo.
- **`metal_graph_dspark_capture_begin_prefill`** `ds4.c:26197`  
  Se la cattura e' disabilitata entrambi gli invalidatori sono no-op.
- **`metal_graph_dspark_capture_complete_mask`** `ds4.c:26032`  
  Con 32 o più layer target satura a UINT32_MAX invece di costruire i soli bit richiesti.
- **`metal_graph_dspark_capture_decode_layer`** `ds4.c:26249`  
  Un layer non target restituisce successo senza scrivere.
- **`metal_graph_dspark_capture_hc`** `ds4.c:26201`  
  Marca lo slot acquisito solo dopo il successo della riduzione GPU.
- **`metal_graph_dspark_capture_invalidate`** `ds4.c:26062`  
  Entrambi gli invalidatori sono no-op quando capture_enabled è falso.
- **`metal_graph_dspark_capture_note_slot`** `ds4.c:26039`  
  Uno slot fuori conteggio viene ignorato senza segnalazione.
- **`metal_graph_dspark_capture_prefill_layer`** `ds4.c:26257`  
  Senza buffer batch cattura solo l'ultimo token e non valida il batch.
- **`metal_graph_dspark_capture_prefill_rows`** `ds4.c:26319`  
  Buffer o intervalli non idonei danno successo senza catturare nulla.
- **`metal_graph_dspark_capture_row_invalidate`** `ds4.c:26047`  
  Se capture_enabled è falso non pulisce eventuale stato residuo.
- **`metal_graph_dspark_capture_verified_suffix_begin`** `ds4.c:26379`  
  Un prerequisito mancante invalida sia la cattura riga sia quella batch.
- **`metal_graph_dspark_capture_verified_suffix_layer`** `ds4.c:26426`  
  Registra il batch da start-1 e con n_tokens+1 righe.
- **`metal_graph_dspark_final_output_hc`** `ds4.c:31707`  
  Per default aliasa lo scratch next_hc; la presenza dell'env seleziona il buffer dedicato.
- **`metal_graph_dspark_ring_maintain`** `ds4.c:31608`  
  Ignora il risultato di cache_claim_appended_row dopo aver scritto il KV.
- **`metal_graph_dspark_stage_profile_boundary`** `ds4.c:31153`  
  Ogni misura spezza il command buffer e può alterare sensibilmente le prestazioni.
- **`metal_graph_dspark_stage_profile_enabled`** `ds4.c:31147`  
  La sola presenza di DS4_DSPARK_STAGE_PROFILE, anche con valore 0, abilita il profiling.
- **`metal_graph_dspark_target_slot`** `ds4.c:26022`  
  Restituisce -1 anche per un layer presente se la cattura DSpARK è disabilitata.
- **`metal_graph_dspark_verify_selected_profile_enabled`** `ds4.c:34213`  
  DISABLE prevale anche quando VERIFY_SELECTED_PROFILE è presente.
- **`metal_graph_enable_batch_hc_norm_fusion`** `ds4.c:19910`  
  È attiva di default; il vecchio ENABLE impostato a 0 la disattiva.
- **`metal_graph_encode_attention_session_batch`** `ds4.c:62859`  
  Sotto la soglia sparse usa attenzione non indicizzata anche con cache compressa.
- **`metal_graph_encode_attn_post_session_batch`** `ds4.c:62968`  
  Anche dopo un errore sul peer tenta di riportare il device corrente su home.
- **`metal_graph_encode_attn_pre_session_batch`** `ds4.c:62392`  
  Con scatter_rows falso i risultati restano solo nel workspace batch.
- **`metal_graph_encode_decode_layer`** `ds4.c:24321`  
  È solo il wrapper della fase FULL.
- **`metal_graph_encode_decode_layer_phase`** `ds4.c:21817`  
  La fase può fermare o riprendere il layer; DS4_MOE_REPLAY_SELECTED_IDS disabilita vari overlap.
- **`metal_graph_encode_dspark_next_stage_draft_input_from`** `ds4.c:31112`  
  Scrive dopo la prima riga HC e conserva la riga target già presente.
- **`metal_graph_encode_ffn_pre_session_batch`** `ds4.c:63143`  
  Con gather_after_attn_rows falso presume il workspace già popolato.
- **`metal_graph_encode_layer_attention_batch`** `ds4.c:27058`  
  Il profiling opzionale spezza ripetutamente i command buffer e cambia le prestazioni.
- **`metal_graph_encode_layer_batch`** `ds4.c:29446`  
  Scambia i puntatori HC solo se attenzione e FFN riescono entrambe.
- **`metal_graph_encode_layer_ffn_batch`** `ds4.c:28821`  
  In TP i rank devono seguire gli stessi rami e gate per restare in lockstep.
- **`metal_graph_encode_mixed_routed_rows`** `ds4.c:63535`  
  DS4_CUDA_MIXED_ROUTED_SCATTER è falso di default: non aggiorna i tensori privati.
- **`metal_graph_encode_native_session_batch_shared`** `ds4.c:60739`  
  Un errore puo lasciare lavoro GPU parziale; il chiamante deve invalidare le sessioni
- **`metal_graph_encode_output_head`** `ds4.c:24347`  
  Su RTX l'env REQUIRE_OUTPUT_HC_SUM_NORM_FUSION è ignorata perché la fusione è solo Apple.
- **`metal_graph_encode_output_head_batch`** `ds4.c:24896`  
  Riusa buffer batch FFN come viste temporanee dell'output head.
- **`metal_graph_encode_output_head_mtp`** `ds4.c:25314`  
  La proiezione finale usa esplicitamente base_weights->output, non un peso vocab MTP.
- **`metal_graph_encode_output_head_split_top1`** `ds4.c:24483`  
  Lascia i logits completi sui tier proprietari e fallisce invece di usare un head non splittato.
- **`metal_graph_encode_prefill_stage_batch`** `ds4.c:33056`  
  Cattura righe DSpark solo quando pipeline_capture_chunk_len è non nullo.
- **`metal_graph_encode_qkv_session_batch`** `ds4.c:62521`  
  Con store_private_kv falso non aggiorna le cache private.
- **`metal_graph_encode_routed_session_batch`** `ds4.c:63302`  
  Con combine_rows attivo e scatter_rows falso, l'output resta nel workspace condiviso.
- **`metal_graph_encode_session_pipeline_batch`** `ds4.c:63936`  
  Le ottimizzazioni sono gerarchiche: disabilitare MoE spegne anche shared, FFN e attenzione.
- **`metal_graph_encode_shared_session_batch`** `ds4.c:63823`  
  Con gather_hc_rows falso assume residuale e split già nel workspace batch.
- **`metal_graph_encode_token_raw_swa`** `ds4.c:26484`  
  In TP il rank 1 puo' annullare need_logits se non possiede il relativo half-buffer.
- **`metal_graph_ensure_batch_ffn_out`** `ds4.c:16603`  
  Inoltra active_tier; se è invalido fallisce senza allocare.
- **`metal_graph_ensure_batch_ffn_out_on`** `ds4.c:16594`  
  La capacità è fissata a prefill_cap, indipendentemente dalle righe correnti.
- **`metal_graph_ensure_ffn_out`** `ds4.c:16585`  
  Riusa lo slot esistente senza verificarne dimensione o device.
- **`metal_graph_env_flag`** `ds4.c:19867`  
  L'env è letto una volta; in build ROCm ogni flag risulta falso.
- **`metal_graph_env_trim`** `ds4.c:26891`  
  Restituisce una vista senza aggiungere NUL dopo gli spazi finali rimossi.
- **`metal_graph_env_value_eq`** `ds4.c:26877`  
  Non elimina spazi: il chiamante deve fare il trim.
- **`metal_graph_eval_dspark_base_logits`** `ds4.c:31783`  
  I tensori view vengono liberati, ma i logits restano nel backing spec_logits.
- **`metal_graph_eval_dspark_base_logits_from_hidden`** `ds4.c:31994`  
  Consuma implicitamente batch_ffn_norm prodotto da una chiamata precedente.
- **`metal_graph_eval_dspark_final_hidden`** `ds4.c:31875`  
  Il risultato resta nello scratch batch_ffn_norm e non viene restituito esplicitamente.
- **`metal_graph_eval_dspark_stage0`** `ds4.c:30308`  
  Al fallimento sincronizza la GPU ignorando l'esito della sincronizzazione.
- **`metal_graph_eval_dspark_stage0_batch`** `ds4.c:30390`  
  Riusa lo scratch packed globale; se è piccolo alloca un temporaneo.
- **`metal_graph_eval_dspark_stage_block`** `ds4.c:31172`  
  Disattiva temporaneamente SSD streaming; l'env alias può forzare una copia finale.
- **`metal_graph_eval_dspark_stage_chain`** `ds4.c:31516`  
  Azzera temporaneamente tp_world e sospende lo sharding esperti sul coordinator.
- **`metal_graph_eval_mixed_prefill_decode`** `ds4.c:64320`  
  Un errore può lasciare cache mutate; questa funzione non invalida le sessioni.
- **`metal_graph_eval_mtp_draft`** `ds4.c:32751`  
  Usa implicitamente metal_graph_cur_hc come input e mtp_state_hc come output.
- **`metal_graph_eval_mtp_draft_from_hc`** `ds4.c:32623`  
  Disabilita temporaneamente TP; se logits o top_id sono null evita il relativo readback.
- **`metal_graph_eval_token_raw_swa`** `ds4.c:29661`  
  In TP il rank 1 senza half-logits non legge nulla nel buffer logits ma puo' riuscire.
- **`metal_graph_eval_token_raw_swa_streaming`** `ds4.c:29481`  
  La mappa statica puo' restare corrente tra token; un errore forza la sincronizzazione.
- **`metal_graph_eval_token_raw_swa_top`** `ds4.c:30132`  
  Il ramo split top-1 evita i logits completi e risolve i candidati sulla CPU.
- **`metal_graph_first_token_full_test`** `ds4.c:25859`  
  TEACHER_FORCE è letto e applicato solo quando TRACE_LAYERS è presente.
- **`metal_graph_free`** `ds4.c:15972`  
  Il memset finale cancella anche configurazione e alias del grafo.
- **`metal_graph_free_prefill_workspace`** `ds4.c:15955`  
  Su un grafo non proprietario non libera né azzera gli alias.
- **`metal_graph_hc_norm_fusion_check_enabled`** `ds4.c:19976`  
  L'env della verifica è letto soltanto alla prima chiamata.
- **`metal_graph_hc_norm_fusion_check_tolerance`** `ds4.c:19981`  
  Valori assenti o invalidi mantengono 2e-4 senza avviso.
- **`metal_graph_hc_rms_scale_project`** `ds4.c:26756`  
  Su Apple usa un kernel fuso; sulla RTX esegue norma e matmul separati.
- **`metal_graph_indexer_stage_profile_boundary`** `ds4.c:26854`  
  Ogni misura spezza il command buffer e altera lo scheduling.
- **`metal_graph_install_model_spans`** `ds4.c:17736`  
  Un vettore nullo o vuoto fallisce senza installare alcuno span.
- **`metal_graph_kv_cache_bytes_for_context`** `ds4.c:16347`  
  Solo i layer con rapporto 4 aggiungono la cache indexer.
- **`metal_graph_layer_stage_profile_boundary`** `ds4.c:26980`  
  Ogni misura introduce sincronizzazione e cambia lo scheduling.
- **`metal_graph_layer_stage_profile_enabled`** `ds4.c:26948`  
  Basta che uno dei due set di variabili ROCm o Metal corrisponda.
- **`metal_graph_layer_stage_profile_start`** `ds4.c:26970`  
  Il profiling cambia i confini di esecuzione anche prima della prima misura.
- **`metal_graph_load_directional_steering`** `ds4.c:16146`  
  Con entrambe le scale a zero ignora anche un percorso file invalido.
- **`metal_graph_logits`** `ds4.c:15585`  
  Usa head_tier catturato, non active_tier.
- **`metal_graph_matmul_dense_quant_abs`** `ds4.c:25014`  
  Non verifica che weight_offset coincida con abs_offset o resti nei byte del tensore.
- **`metal_graph_matmul_dense_quant_kslice`** `ds4.c:25054`  
  x_elem_off è indipendente da k_off e un abbinamento errato produce una fetta semanticamente falsa.
- **`metal_graph_matmul_dense_quant_tensor`** `ds4.c:25035`  
  Delega ogni controllo del buffer al wrapper con offset assoluto.
- **`metal_graph_matmul_plain_tensor`** `ds4.c:24970`  
  Un tipo non supportato stampa un errore e restituisce false, senza fallback CPU.
- **`metal_graph_matmul_q8_0_named_tensor`** `ds4.c:25291`  
  Ignora completamente module, il e pos: il nome non influenza calcolo né diagnostica.
- **`metal_graph_mixed_prefill_decode_supported`** `ds4.c:64258`  
  Variabili METAL di dump o profiling disabilitano anche il percorso CUDA.
- **`metal_graph_mixed_routed_max_prefill_rows`** `ds4.c:64249`  
  Un valore assente o non valido torna a 512; zero invece disabilita il percorso.
- **`metal_graph_mixed_workspace_compatible`** `ds4.c:64204`  
  Accetta cur e next scambiati, non solo nella stessa orientazione.
- **`metal_graph_native_session_batch_qkv_supported`** `ds4.c:60708`  
  La sola presenza di DS4_METAL_Q8_DECODE_MPP lo disabilita
- **`metal_graph_native_session_batch_shared_supported`** `ds4.c:60657`  
  La sola presenza di DS4_METAL_ENABLE_Q8_DECODE_EXACT_VIEWS lo disabilita
- **`metal_graph_needs_ffn_out`** `ds4.c:16575`  
  Abilitare il dump ffn_out forza allocazione e materializzazione nel percorso normale.
- **`metal_graph_output_embd`** `ds4.c:15594`  
  Usa head_tier catturato, non active_tier.
- **`metal_graph_output_logits_head_matmul`** `ds4.c:24737`  
  Batch da 2 a 7 righe può essere portato a 8; in CUDA EP non esiste fallback full-head.
- **`metal_graph_output_norm`** `ds4.c:15597`  
  Usa head_tier catturato, non active_tier.
- **`metal_graph_output_pre`** `ds4.c:15588`  
  Usa head_tier catturato, non active_tier.
- **`metal_graph_output_weights`** `ds4.c:15591`  
  Usa head_tier catturato, non active_tier.
- **`metal_graph_pack_dspark_target_hidden_batch`** `ds4.c:30365`  
  Trasforma il layout slot-per-riga; non esegue una semplice copia lineare.
- **`metal_graph_prefill_chunked`** `ds4.c:34171`  
  Con n_tokens non positivo fallisce senza elaborare il prompt.
- **`metal_graph_prefill_chunked_range`** `ds4.c:34050`  
  Su ripresa limita il primo chunk al prossimo confine assoluto di prefill_cap.
- **`metal_graph_prefill_decode_streaming_range`** `ds4.c:29785`  
  La cancellazione restituisce true; solo cancelled distingue l'uscita anticipata dal successo.
- **`metal_graph_prefill_layer_major`** `ds4.c:33336`  
  DS4_ROCM_GRAPH_OUTPUT_ROW può calcolare i logits da una riga diversa dall'ultima.
- **`metal_graph_prefill_pipeline_stage_major`** `ds4.c:33088`  
  Sopprime di default la cache Q8; la presenza di SEQUENTIAL forza il percorso seriale.
- **`metal_graph_prefill_raw_swa`** `ds4.c:33988`  
  Nel fallback layer-major ignora cancel, cancel_ud e cancelled fino alla generazione.
- **`metal_graph_prefill_tokens`** `ds4.c:15605`  
  Usa il tier embedding, non il tier attivo del layer.
- **`metal_graph_prefill_workspace_bytes`** `ds4.c:15942`  
  Misura le allocazioni presenti, non la capacità teorica richiesta.
- **`metal_graph_prepare_dspark_setup_block`** `ds4.c:30568`  
  La riga target e il primo draft usano entrambi la posizione pos; gli altri token sono noise.
- **`metal_graph_prepare_dspark_stage0_setup_block`** `ds4.c:30645`  
  DS4_DSPARK_PROP_PROFILE è per presenza: anche 0 abilita la stampa dei tempi.
- **`metal_graph_probe_dspark_noncausal_attention`** `ds4.c:30530`  
  Azzera query e cache raw dello stadio 0 senza ripristinarle.
- **`metal_graph_profile_layer_env_match`** `ds4.c:31135`  
  Variabile assente o vuota corrisponde a qualunque layer.
- **`metal_graph_profile_layer_value_match`** `ds4.c:26903`  
  Un valore assente o vuoto corrisponde a qualunque layer.
- **`metal_graph_profile_router_selection`** `ds4.c:21690`  
  Quando il profilo è attivo chiude e riapre il batch comandi a ogni layer.
- **`metal_graph_prompt_logits_test`** `ds4.c:35350`  
  Un file oracle illeggibile disabilita silenziosamente il confronto con l'oracle.
- **`metal_graph_q4_non_streaming_opt_in_enabled`** `ds4.c:20402`  
  Qualunque dei sei env abilita, anche se contiene 0 o stringa vuota.
- **`metal_graph_q4_selected_paths_allowed`** `ds4.c:20411`  
  Lo streaming è sempre ammesso; GLM DSA non streaming è sempre negato.
- **`metal_graph_q8_0_row_bytes`** `ds4.c:17077`  
  Anche un blocco parziale costa tutti i 34 byte del blocco Q8_0.
- **`metal_graph_q_stage_profile_boundary`** `ds4.c:27003`  
  Profila sempre con una stampa e spezza il command buffer.
- **`metal_graph_raw_cap_for_context`** `ds4.c:34703`  
  Su ROCm ignora DS4_METAL_GRAPH_RAW_CAP; la capacità resta limitata a 8192.
- **`metal_graph_raw_span_for_batch`** `ds4.c:19707`  
  Un token aggiunge window-1, un batch aggiunge window.
- **`metal_graph_raw_start_for_span`** `ds4.c:19725`  
  Restituisce zero anche per input invalidi, indistinguibile da una riga valida.
- **`metal_graph_read_output_split_top1`** `ds4.c:24691`  
  A parità di logit vince l'ID token numericamente minore.
- **`metal_graph_read_spec_logits_row`** `ds4.c:34454`  
  Legge sempre DS4_N_VOCAB float, senza accettare una dimensione del buffer.
- **`metal_graph_refresh_ratio4_compressor_state`** `ds4.c:26591`  
  Con meno di quattro token restituisce true senza aggiornare lo stato.
- **`metal_graph_reset_prefill_state`** `ds4.c:32983`  
  Salta i layer senza raw cache o con ratio zero, lasciandone gli altri tensori intatti.
- **`metal_graph_resume_prefill_min_tokens`** `ds4.c:34750`  
  Su ROCm ignora l'env; altrove un valore non positivo disabilita il prefill ripreso.
- **`metal_graph_seed_dspark_initial_cache_from_prefill`** `ds4.c:31057`  
  Pubblica la finestra cache solo dopo il successo di tutti gli stadi.
- **`metal_graph_seed_dspark_stage_target_cache`** `ds4.c:30918`  
  Quantizza FP8 in place il buffer KV prima di copiarlo nella cache raw.
- **`metal_graph_seed_streaming_expert_cache_from_hotlist`** `ds4.c:29975`  
  File esplicito e hotlist GLM52 non saltano il seed in base a current_count.
- **`metal_graph_seed_streaming_expert_cache_from_prefill`** `ds4.c:29900`  
  Legge il tensore alla capacita' massima, non soltanto le righe seed effettive.
- **`metal_graph_selected_async_load_ensure_worker`** `ds4.c:21395`  
  Un fallimento di creazione lascia thread_started falso e viene ritentato alla chiamata successiva.
- **`metal_graph_selected_async_load_finish`** `ds4.c:21474`  
  Blocca senza timeout e consuma il flag globale done anche se il job è fallito.
- **`metal_graph_selected_async_load_run`** `ds4.c:21302`  
  Marca ids_ok prima del load, consentendo al chiamante un retry sincrono se il load fallisce.
- **`metal_graph_selected_async_load_start`** `ds4.c:21454`  
  È solo un wrapper e passa NULL se il grafo è assente, causando false.
- **`metal_graph_selected_async_load_start_tensor`** `ds4.c:21419`  
  Non accoda: se esiste un job pendente o completato ma non raccolto restituisce false.
- **`metal_graph_selected_async_load_sync_init`** `ds4.c:21294`  
  Un errore di inizializzazione termina il processo con ds4_die.
- **`metal_graph_selected_async_load_worker_main`** `ds4.c:21365`  
  Il thread non ha condizione di arresto e la coda globale contiene un solo job.
- **`metal_graph_selected_profile_layer_impl`** `ds4.c:18448`  
  Stima i byte di up duplicando gate senza consultare ffn_up_exps.
- **`metal_graph_selected_profile_summary_impl`** `ds4.c:18569`  
  Con zero layer non stampa nulla; la sentinella min_unique viene mostrata come 0.
- **`metal_graph_session_batch_attn_core_supported`** `ds4.c:62154`  
  La presenza di molte variabili CUDA di tuning forza il fallback.
- **`metal_graph_session_batch_attn_post_supported`** `ds4.c:62245`  
  Richiede cuda_tp_attn attivo ma rifiuta cuda_tp_attn_heads.
- **`metal_graph_session_batch_attn_pre_supported`** `ds4.c:62117`  
  Il predicato richiede almeno 3 righe, mentre l'encoder ne accetta 2.
- **`metal_graph_session_batch_ffn_pre_supported`** `ds4.c:63097`  
  Il predicato richiede almeno 3 righe, mentre l'encoder ne accetta 2.
- **`metal_graph_session_batch_kv_store_supported`** `ds4.c:62361`  
  La duplicazione TP della cache d'attenzione disabilita lo store batch.
- **`metal_graph_session_batch_moe_supported`** `ds4.c:62011`  
  DS4_METAL_GRAPH_DUMP_PREFIX disabilita anche questo percorso CUDA.
- **`metal_graph_session_batch_qkv_supported`** `ds4.c:62310`  
  Il predicato richiede almeno 3 righe, mentre l'encoder ne accetta 2.
- **`metal_graph_session_batch_shared_supported`** `ds4.c:62066`  
  Il batch shared è rifiutato proprio quando cuda_tp_shared è attivo.
- **`metal_graph_set_active_tier_batch`** `ds4.c:15843`  
  Se manca uno slot, aggiorna comunque active_tier senza copiare.
- **`metal_graph_set_active_tier_decode`** `ds4.c:15817`  
  Se manca uno slot, aggiorna comunque active_tier senza copiare.
- **`metal_graph_set_active_tier_no_copy`** `ds4.c:15865`  
  Il cambio di tier riesce anche se nessun dato viene copiato.
- **`metal_graph_stage_profile_enabled_for_layer`** `ds4.c:26917`  
  Un flag presente ma vuoto abilita tutti i layer se manca il filtro.
- **`metal_graph_store_attn_comp_stage`** `ds4.c:20127`  
  Con rows uguale a zero restituisce successo senza accedere allo staging.
- **`metal_graph_stream_decode_layer_batch_enabled`** `ds4.c:17797`  
  Profiling, dump o tabella indirizzi esperti completa disabilitano il batch.
- **`metal_graph_stream_decode_static_map_enabled`** `ds4.c:17779`  
  Fuori da ROCm è attiva di default; in ROCm richiede un enable esplicito.
- **`metal_graph_stream_decode_static_map_state_cache_enabled`** `ds4.c:17792`  
  È attiva di default e la presenza del disable, anche con valore 0, la spegne.
- **`metal_graph_stream_madvise_willneed_enabled`** `ds4.c:17772`  
  Serve un enable esplicito e qualunque disable presente prevale.
- **`metal_graph_stream_madvise_willneed_range_impl`** `ds4.c:17852`  
  Se disabilitata o non supportata può restituire vero senza impartire alcun consiglio.
- **`metal_graph_stream_map_decode_static_all`** `ds4.c:19653`  
  Su CUDA senza COPY_MODEL_CHUNKED gli span non vengono prefetchati in VRAM.
- **`metal_graph_stream_map_layer`** `ds4.c:19666`  
  Su CUDA senza COPY_MODEL_CHUNKED gli span non vengono prefetchati in VRAM.
- **`metal_graph_stream_map_layer_decode`** `ds4.c:19680`  
  Su CUDA senza COPY_MODEL_CHUNKED gli span non vengono prefetchati in VRAM.
- **`metal_graph_stream_map_output`** `ds4.c:19694`  
  Su CUDA senza COPY_MODEL_CHUNKED gli span non vengono prefetchati in VRAM.
- **`metal_graph_stream_map_token`** `ds4.c:19640`  
  Su CUDA senza COPY_MODEL_CHUNKED gli span non vengono prefetchati in VRAM.
- **`metal_graph_stream_pagein_thread_main`** `ds4.c:18737`  
  Si ferma al primo intervallo fallito e comunica l'errore solo tramite job->ok.
- **`metal_graph_stream_pagein_touch_range`** `ds4.c:18606`  
  Ignora l'esito di posix_madvise e legge anche l'ultimo byte dell'intervallo allineato.
- **`metal_graph_stream_pagein_worker_main`** `ds4.c:18758`  
  Un argomento NULL viene dereferenziato prima del controllo e può causare crash.
- **`metal_graph_stream_pread_range`** `ds4.c:18656`  
  Alloca sempre un buffer da 1 MiB e considera errore anche un EOF prematuro.
- **`metal_graph_stream_prefill_batch_selected_addr_auto_max`** `ds4.c:18033`  
  Accetta suffissi non numerici; valori non positivi danno 0 e testo invalido usa il default.
- **`metal_graph_stream_prefill_batch_selected_addr_auto_min`** `ds4.c:18056`  
  Accetta suffissi non numerici; valori non positivi danno 0, mentre PRO e FLASH usano 2.
- **`metal_graph_stream_prefill_batch_selected_addr_enabled`** `ds4.c:18077`  
  ENABLE non forza il percorso: qualità, batch singolo, cache o layout incompatibili vincono.
- **`metal_graph_stream_prefill_layer_madvise_enabled`** `ds4.c:18023`  
  È attivo per default: la presenza di DISABLE_MADVISE o DISABLE_PREPARE lo spegne.
- **`metal_graph_stream_prefill_layer_pagein_enabled`** `ds4.c:17991`  
  Richiede enable esplicito; la presenza del disable prevale anche se vale 0.
- **`metal_graph_stream_prefill_layer_pagein_join`** `ds4.c:19245`  
  Un job nullo o non avviato è considerato completato con successo.
- **`metal_graph_stream_prefill_layer_pagein_overlap_enabled`** `ds4.c:18829`  
  È attiva per default; qualunque NO_OVERLAP o DISABLE presente la spegne.
- **`metal_graph_stream_prefill_layer_pagein_start`** `ds4.c:19094`  
  Se la modalità è disabilitata restituisce vero lasciando job->started falso.
- **`metal_graph_stream_prefill_layer_pagein_threads`** `ds4.c:18784`  
  Default 8; invalido o zero diventa 1, massimo 16; PREPARE prevale su PAGEIN.
- **`metal_graph_stream_prefill_layer_pread_enabled`** `ds4.c:18013`  
  È attivo per default: la presenza di DISABLE_PREAD o DISABLE_PREPARE lo spegne.
- **`metal_graph_stream_prefill_layer_prepare_ahead`** `ds4.c:18842`  
  Default, zero e input invalido valgono 1; il massimo è 4.
- **`metal_graph_stream_prefill_layer_readahead_enabled`** `ds4.c:18001`  
  DISABLE_LAYER_PREPARE lo spegne anche quando l'enable specifico è presente.
- **`metal_graph_stream_prefill_selected_madvise_enabled`** `ds4.c:17981`  
  Richiede enable esplicito; la presenza del disable prevale anche se vale 0.
- **`metal_graph_stream_prefill_selected_pagein_enabled`** `ds4.c:17971`  
  Richiede enable esplicito; la presenza del disable prevale anche se vale 0.
- **`metal_graph_stream_prefill_selected_pagein_join`** `ds4.c:19040`  
  Un job nullo o non avviato è successo; dopo il join tutto lo stato viene azzerato.
- **`metal_graph_stream_prefill_selected_pagein_start`** `ds4.c:18856`  
  Se disabilitata o senza range, restituisce vero senza avviare il job.
- **`metal_graph_stream_prefill_selected_prepare_gap`** `ds4.c:18818`  
  Valore assente o invalido diventa 0 e ogni valore oltre 8 viene troncato a 8.
- **`metal_graph_stream_prefill_selected_prepare_threads`** `ds4.c:18800`  
  Se non è madvise forza 1 e ignora le variabili; madvise eredita fino a 16 thread.
- **`metal_graph_stream_prefill_selected_profile_add_bytes`** `ds4.c:18442`  
  In overflow restituisce UINT64_MAX anziché segnalare errore.
- **`metal_graph_stream_prefill_selected_profile_enabled`** `ds4.c:18420`  
  Richiede l'ENABLE esplicito; la presenza di DISABLE ha sempre precedenza.
- **`metal_graph_stream_prefill_selected_profile_layer`** `ds4.c:18555`  
  Con profiling disattivo restituisce vero senza validare layer o tensor.
- **`metal_graph_stream_prefill_selected_profile_reset`** `ds4.c:18430`  
  min_unique viene inizializzato a UINT32_MAX, non a zero.
- **`metal_graph_stream_prefill_selected_profile_summary`** `ds4.c:18598`  
  Con profiling disattivo non stampa nulla.
- **`metal_graph_stream_prefill_selected_readahead_enabled`** `ds4.c:19449`  
  ENABLE_SHARED abilita anche il percorso base; DISABLE generale vince sempre.
- **`metal_graph_stream_prefill_selected_readahead_gap`** `ds4.c:19473`  
  Valore assente o invalido diventa 0 e ogni valore oltre 8 viene troncato a 8.
- **`metal_graph_stream_prefill_selected_readahead_shared_enabled`** `ds4.c:19461`  
  Richiede ENABLE_SHARED; DISABLE_SHARED o DISABLE generale hanno precedenza.
- **`metal_graph_stream_prepare_join_all`** `ds4.c:19406`  
  Continua a unire e azzerare gli altri slot anche dopo un fallimento.
- **`metal_graph_stream_prepare_join_layer`** `ds4.c:19370`  
  Se manca lo slot anticipato, avvia e unisce subito un job locale anziché fallire.
- **`metal_graph_stream_prepare_range`** `ds4.c:18698`  
  Con più flag veri, la priorità è pread, readahead, madvise, poi touch.
- **`metal_graph_stream_prepare_slot_find`** `ds4.c:19308`  
  Ignora gli slot non attivi anche se conservano lo stesso numero di layer.
- **`metal_graph_stream_prepare_slot_free`** `ds4.c:19318`  
  Restituisce il primo slot inattivo senza verificarne il contenuto residuo.
- **`metal_graph_stream_prepare_start_if_needed`** `ds4.c:19327`  
  Un layer fuori modello è successo; una coda piena è invece errore.
- **`metal_graph_stream_readahead_enabled`** `ds4.c:17765`  
  Serve un enable esplicito e qualunque disable presente prevale.
- **`metal_graph_stream_readahead_layer`** `ds4.c:19420`  
  Se la costruzione degli span fallisce, ritorna senza errore né log.
- **`metal_graph_stream_readahead_layer_decode`** `ds4.c:19430`  
  Se la costruzione degli span fallisce, ritorna senza errore né log.
- **`metal_graph_stream_readahead_output`** `ds4.c:19440`  
  Se la costruzione degli span fallisce, ritorna senza errore né log.
- **`metal_graph_stream_readahead_range`** `ds4.c:17905`  
  Ignora il risultato booleano di madvise e non segnala il fallimento al chiamante.
- **`metal_graph_stream_readahead_range_impl`** `ds4.c:17814`  
  Ignora ogni errore di fcntl e divide richieste grandi in blocchi da INT_MAX.
- **`metal_graph_stream_readahead_selected_experts_from_gpu`** `ds4.c:19539`  
  La selezione richiede una copia D2H sincrona prima di inviare gli hint.
- **`metal_graph_stream_readahead_selected_run`** `ds4.c:19484`  
  Restituisce vero anche se gli hint sottostanti vengono ignorati dal sistema operativo.
- **`metal_graph_stream_readahead_spans`** `ds4.c:17921`  
  Un vettore nullo produce silenziosamente un no-op.
- **`metal_graph_streaming_decode_prefill_max_tokens`** `ds4.c:29722`  
  Un env non numerico ricade sul default; un valore non positivo disabilita il percorso.
- **`metal_graph_streaming_decode_prefill_wide_default`** `ds4.c:29712`  
  Richiede Q4_K per gate, up e down routed; basta un tipo diverso per negare il default.
- **`metal_graph_streaming_expert_cache_seed_layer_expected`** `ds4.c:20565`  
  Il caso IQ2 selected restituisce vero prima di consultare DISABLE_STREAMING_EXPERT_CACHE.
- **`metal_graph_streaming_expert_hotlist_add`** `ds4.c:20676`  
  Ignora come successo duplicati e indici fuori modello; la priorità zero diventa uno.
- **`metal_graph_streaming_expert_hotlist_enabled`** `ds4.c:20668`  
  La modalità cold o la sola presenza dell'env DISABLE lo spegne.
- **`metal_graph_streaming_expert_hotlist_load_default`** `ds4.c:20784`  
  Per varianti sconosciute restituisce successo con zero esperti.
- **`metal_graph_streaming_expert_hotlist_load_file`** `ds4.c:20697`  
  Una sola riga malformata annulla l'intero caricamento; gli hit zero sono ignorati.
- **`metal_graph_streaming_expert_preload_count`** `ds4.c:20829`  
  In auto il cap predefinito è 4096; cap zero significa nessun limite, non nessun preload.
- **`metal_graph_streaming_prefill_cache_seed_enabled`** `ds4.c:20664`  
  Ricalcola K e rilegge gli env a ogni chiamata.
- **`metal_graph_streaming_prefill_cache_seed_k`** `ds4.c:20639`  
  K non valido lascia 1, zero disattiva e valori oltre il massimo vengono troncati.
- **`metal_graph_tensor_row_range_view`** `ds4.c:27022`  
  Offset e dimensione sono sempre calcolati in float.
- **`metal_graph_tensor_row_view`** `ds4.c:26559`  
  Offset e dimensione sono sempre calcolati in float.
- **`metal_graph_token_split_after_layers`** `ds4.c:26009`  
  Nelle build ROCm ignora sempre l'env Metal; valori non validi lasciano silenziosamente quattro.
- **`metal_graph_tp_ablate`** `ds4.c:21738`  
  Legge DS4_TP_ABLATE una sola volta e cerca sottostringhe, non nomi tokenizzati.
- **`metal_graph_tp_env_flag`** `ds4.c:16607`  
  Qualunque stringa non vuota diversa da 0 abilita, inclusa false.
- **`metal_graph_tp_prefill_split_min`** `ds4.c:27034`  
  Legge l'env solo alla prima chiamata e forza sempre un minimo di due.
- **`metal_graph_tp_subgate_pipeline`** `ds4.c:27049`  
  Il valore dell'env viene memorizzato alla prima chiamata.
- **`metal_graph_trace_layer_stages`** `ds4.c:25364`  
  Legge anche ffn_out, che in produzione può non essere materializzato; è solo diagnostica.
- **`metal_graph_transfer_prefill_workspace`** `ds4.c:15931`  
  src conserva alias non proprietari; dst viene azzerato senza liberarlo.
- **`metal_graph_unbind_attn_pre_batch_row`** `ds4.c:62831`  
  Un alias inattivo rende l'operazione un no-op silenzioso.
- **`metal_graph_upload_prompt_embeddings_hc`** `ds4.c:26716`  
  La soglia env viene riletta a ogni chiamata; sotto soglia replica tutto lato CPU.
- **`metal_graph_upload_prompt_embeddings_hc_cpu`** `ds4.c:26684`  
  Costruisce in RAM l'intero tensore token per HC prima di una sola scrittura GPU.
- **`metal_graph_upload_prompt_tokens`** `ds4.c:26569`  
  Con out_tokens valido e prompt NULL dereferenzia prompt.
- **`metal_graph_use_cuda_selected_shared_overlap`** `ds4.c:20391`  
  La sola presenza di DS4_CUDA_DISABLE_STREAMING_SELECTED_SHARED_OVERLAP lo spegne.
- **`metal_graph_use_iq2_selected_async_early_commit`** `ds4.c:20435`  
  In ROCm restituisce sempre falso anche nello streaming.
- **`metal_graph_use_iq2_selected_async_load`** `ds4.c:20425`  
  In ROCm il flag DISABLE è ignorato e il caricamento risulta sempre attivo.
- **`metal_graph_use_iq2_selected_readahead_shared_delay`** `ds4.c:20996`  
  È spento di default e, se entrambe le variabili sono presenti, DISABLE prevale.
- **`metal_graph_use_iq2_selected_shared_overlap`** `ds4.c:20418`  
  La presenza di uno dei due env DISABLE lo spegne, anche con valore 0.
- **`metal_graph_use_pro_q4_cpu_router`** `ds4.c:20376`  
  Il valore dell'env è memorizzato alla prima chiamata.
- **`metal_graph_use_pro_q4_expert_table_auto`** `ds4.c:20446`  
  Un env DISABLE presente vale anche 0; in streaming non serve ENABLE esplicito.
- **`metal_graph_use_q4_selected_shared_overlap`** `ds4.c:20386`  
  Il valore dell'env è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_attn_out_hc`** `ds4.c:19932`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_compressor_pair_proj`** `ds4.c:19900`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_hc_decode`** `ds4.c:19880`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_hc_norm_decode`** `ds4.c:19905`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_kv_decode`** `ds4.c:19885`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_qkv_norm`** `ds4.c:19890`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_qkv_pair_proj`** `ds4.c:19895`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_reference_shared_down_hc`** `ds4.c:19927`  
  Il flag di disabilitazione fusione è memorizzato alla prima chiamata.
- **`metal_graph_use_streaming_decode_prefill`** `ds4.c:29751`  
  La modalita' quality lo disabilita anche con SSD streaming attivo.
- **`metal_graph_use_streaming_decode_prefill_range`** `ds4.c:29765`  
  Il flag disable-cold viene consultato solo quando start e' zero.
- **`metal_graph_use_streaming_iq2_cpu_router`** `ds4.c:20381`  
  Rilegge gli env ogni volta e DISABLE prevale su ENABLE.
- **`metal_graph_verify_decode2_exact`** `ds4.c:34471`  
  È specializzata a due token e modifica temporaneamente i puntatori tensoriali del grafo.
- **`metal_graph_verify_suffix_tops_impl`** `ds4.c:34228`  
  DS4_DSPARK_VERIFY_PROFILE è campionata una volta e profila una sola verifica.
- **`metal_graph_warmup_prefill_kernels`** `ds4.c:26802`  
  Streaming, batch fino a 8 o env presente saltano il warmup senza impostare warmed.
- **`min_available_gib_from_env`** `src/cuda/dynamic_arena.cu:285`  
  Un valore invalido restituisce 0 ma marca valid=false e avvisa una sola volta
- **`mma16_m16n8k32_s8`** `ds4_cuda.cu:24295`  
  Sotto sm_80 è un no-op silenzioso e lascia invariati gli accumulatori
- **`mma_m16n8k32_s8`** `ds4_cuda.cu:8530`  
  Sotto sm_80 il ramo compilato non fa nulla e lascia invariati gli accumulatori senza errore.
- **`mma_m8n8k16_s8`** `ds4_cuda.cu:24009`  
  Sotto sm_75 è un no-op silenzioso e lascia invariati gli accumulatori
- **`model_alias_disables_thinking`** `ds4_server.c:1144`  
  Il confronto e esatto e sensibile alle maiuscole
- **`model_alias_enables_thinking`** `ds4_server.c:1153`  
  Il confronto e esatto e sensibile alle maiuscole
- **`model_ape_value_dev`** `rocm/ds4_rocm_norm_rope.cuh:366`  
  Qualsiasi type diverso da 1 o 8 viene interpretato come F32.
- **`model_close`** `ds4.c:2373`  
  Dopo la chiusura lo stato viene reinizializzato, non lasciato semplicemente azzerato.
- **`model_dspark_summary`** `ds4.c:2630`  
  Conta gli stadi come massimo più uno, quindi eventuali buchi gonfiano il totale
- **`model_find_kv`** `ds4.c:2246`  
  Con chiavi duplicate restituisce la prima.
- **`model_find_tensor`** `ds4.c:2836`  
  Con nomi duplicati restituisce il primo senza segnalarli
- **`model_get_array`** `ds4.c:2362`  
  Non verifica che il payload dichiarato dall'array rientri nella mappatura.
- **`model_get_bool`** `ds4.c:2346`  
  Qualunque byte non zero viene accettato come true.
- **`model_get_f32_compat`** `ds4.c:2318`  
  Le conversioni da float64 e interi possono perdere precisione senza segnalarlo.
- **`model_get_string`** `ds4.c:2253`  
  La vista restituita non è terminata da NUL.
- **`model_get_token_id`** `ds4.c:2267`  
  Accetta uint32, int32, uint64 e int64 invece di un solo tipo canonico.
- **`model_get_u32`** `ds4.c:2260`  
  Rifiuta valori numerici equivalenti codificati con altri tipi interi.
- **`model_get_u32_any`** `ds4.c:2579`  
  Se più alias esistono prevale il primo, senza verificarne la coerenza
- **`model_get_u32_array_any`** `ds4.c:2587`  
  Tronca silenziosamente gli array più lunghi di cap
- **`model_get_u64_compat`** `ds4.c:2302`  
  Non accetta interi signed anche se positivi.
- **`model_gpu_fd`** `ds4.c:2139`  
  Fuori da Windows restituisce il fd del file mmap, non un descrittore GPU dedicato.
- **`model_map_q4_pro_group_views`** `ds4.c:6306`  
  Valori non validi della variabile d'ambiente ricadono silenziosamente a 1.
- **`model_map_span_cmp`** `ds4.c:6625`  
  Non ha chiamate dirette: qsort la invoca come callback.
- **`model_map_span_include_tensor`** `ds4.c:6284`  
  Tensori nulli o vuoti vengono ignorati senza errore.
- **`model_map_span_vec_append`** `ds4.c:6296`  
  Intervalli vuoti o con estremi invertiti sono ignorati silenziosamente.
- **`model_map_span_vec_finish`** `ds4.c:6635`  
  Gli intervalli isolati non vengono mai fusi, neppure se sovrapposti.
- **`model_map_span_vec_include_layer`** `ds4.c:6352`  
  I puntatori nulli vengono saltati, producendo anche layer parziali senza errore.
- **`model_map_span_vec_include_layer_decode`** `ds4.c:6601`  
  Un layer reso residente riaggiunge esplicitamente tutti e tre i blob esperti.
- **`model_map_span_vec_include_layer_decode_static`** `ds4.c:6406`  
  Include router ed esperto condiviso; esclude solo gate, up e down degli esperti instradati.
- **`model_map_span_vec_include_one`** `ds4.c:6319`  
  Solo i Q4_K 3D da almeno 2 GiB con 384 esperti vengono suddivisi in gruppi.
- **`model_map_span_vec_include_output`** `ds4.c:6617`  
  Una testata mancante o parziale produce semplicemente meno intervalli.
- **`model_map_span_vec_total_bytes`** `ds4.c:6770`  
  In caso di overflow restituisce UINT64_MAX invece di segnalare errore.
- **`model_open`** `ds4.c:2487`  
  Con prefetch_cpu falso mappa il modello ma non ne scalda il payload
- **`model_platform_init`** `ds4.c:2147`  
  Su Windows imposta gpu_fd a -1; altrove non esiste quel campo.
- **`model_prefetch_cpu_mapping`** `ds4.c:2385`  
  È solo un hint: non copia, non blocca in RAM e non garantisce la residenza delle pagine.
- **`model_print_dspark_summary`** `ds4.c:2700`  
  Non stampa nulla se mancano sia stadi sia metadati
- **`model_scalar_dev`** `rocm/ds4_rocm_norm_rope.cuh:360`  
  Qualsiasi type diverso da 1 viene interpretato come float32.
- **`model_summary`** `ds4.c:2726`  
  Chiavi assenti restano a zero e possono sparire dal riepilogo senza errore
- **`model_warm_weights`** `ds4.c:3144`  
  Il checksum legge un byte per pagina e non valida né percorre tutti i pesi
- **`model_warm_weights_sharded`** `ds4.c:54678`  
  Un rank diverso da 0 o 1 ritorna in silenzio.
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
- **`moe_down_iq2_sum_qwarp32_batch_kernel`** `rocm/ds4_rocm_moe.cuh:2157`  
  Il ciclo è limitato a DS4_ROCM_N_EXPERT_USED anche se n_expert è maggiore.
- **`moe_down_iq2_sum_qwarp32_ptrs_batch_kernel`** `rocm/ds4_rocm_moe.cuh:2194`  
  Puntatori nulli saltano silenziosamente interi contributi esperto.
- **`moe_down_kernel`** `rocm/ds4_rocm_moe.cuh:1841`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_down_owned_packed_qwarp32_kernel`** `ds4_cuda.cu:23347`  
  Se una componente non esiste scrive esplicitamente zero, invece di lasciare l'output invariato
- **`moe_down_owned_slots_qwarp32_kernel`** `ds4_cuda.cu:23278`  
  Gli slot non posseduti lasciano la rispettiva uscita invariata
- **`moe_down_q1_0_qwarp32_kernel`** `ds4_cuda.cu:21368`  
  Un esperto selezionato negativo viene sostituito silenziosamente con l'esperto 0
- **`moe_down_q2K_expert_batch_sharedmid_kernel`** `rocm/ds4_rocm_moe.cuh:3595`  
  I flag template cambiano tipo e layout; SLOT_MAJOR richiede n_tokens corretto.
- **`moe_down_q2K_hotlist_wmma_kernel`** `rocm/ds4_rocm_moe.cuh:4065`  
  Scrive un risultato separato per coppia, senza somma tra esperti.
- **`moe_down_q2K_hotlist_wmma_n2_kernel`** `rocm/ds4_rocm_moe.cuh:4144`  
  MID_F16, OUT_F16 e SLOT_MAJOR cambiano silenziosamente tipo e layout dei buffer.
- **`moe_down_q2K_sum_rows_w32_kernel`** `rocm/ds4_rocm_moe.cuh:3319`  
  Il ciclo considera al massimo DS4_ROCM_N_EXPERT_USED slot.
- **`moe_down_q2K_sum_rows_w32_ptrs_batch_kernel`** `rocm/ds4_rocm_moe.cuh:3444`  
  Un puntatore nullo elimina silenziosamente il contributo dell'esperto.
- **`moe_down_q4K_expert_tile4_row32_kernel`** `rocm/ds4_rocm_moe.cuh:2313`  
  atomic_out cambia sia accumulo sia layout logico dell'uscita.
- **`moe_down_q4K_expert_tile8_row32_kernel`** `rocm/ds4_rocm_moe.cuh:2374`  
  atomic_out somma per token; a zero scrive invece un risultato per coppia.
- **`moe_down_q4K_expert_tile8_rowspan_kernel`** `ds4_cuda.cu:23939`  
  Con oltre 8 blocchi midq usa i puntatori globali invece della copia in shared
- **`moe_down_q4K_owned_packed_qwarp32_kernel`** `ds4_cuda.cu:23498`  
  Una coppia prefissa viene già sommata; una componente senza slot viene invece azzerata
- **`moe_down_q4K_owned_slots_qwarp32_kernel`** `ds4_cuda.cu:23458`  
  Uno slot non locale termina senza azzerare la destinazione, che può restare stantia
- **`moe_down_q4K_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2260`  
  Un selected negativo usa l'esperto 0 e scrive comunque un risultato
- **`moe_down_q4K_sorted_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2286`  
  Scrive ancora in layout per coppia, non in ordine sorted.
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
- **`moe_down_sum6_qwarp32_ptrs_batch_kernel`** `rocm/ds4_rocm_moe.cuh:2121`  
  Selected negativo diventa slot compatto 0; un puntatore nullo viene ignorato.
- **`moe_down_sum6_qwarp32_ptrs_kernel`** `rocm/ds4_rocm_moe.cuh:2094`  
  Un puntatore nullo elimina silenziosamente il contributo dello slot.
- **`moe_down_warp8_kernel`** `rocm/ds4_rocm_moe.cuh:1872`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_filter_owned_pairs_kernel`** `ds4_cuda.cu:21157`  
  Distrugge gli ID globali originali e azzera i pesi non residenti
- **`moe_gate_up_mid_decode_lut_owned_qwarp32_kernel`** `ds4_cuda.cu:21685`  
  Per uno slot non posseduto esce senza azzerare mid_out
- **`moe_gate_up_mid_decode_lut_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:854`  
  Con write_aux a zero scrive mid ma lascia invariati gate_out e up_out
- **`moe_gate_up_mid_decode_lut_qwarp32_ptrs_kernel`** `rocm/ds4_rocm_moe.cuh:920`  
  Puntatori nulli saltano la coppia; write_aux a zero lascia gate/up invariati.
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
- **`moe_gate_up_mid_iq2_hotlist_wmma_n2_kernel`** `rocm/ds4_rocm_moe.cuh:3759`  
  Quando X_F16 è falso divide pair per 6, ignorando un eventuale diverso n_expert.
- **`moe_gate_up_mid_kernel`** `rocm/ds4_rocm_moe.cuh:532`  
  Non ha alcun sito di lancio ed è marcato DS4_CUDA_UNUSED
- **`moe_gate_up_mid_q1_0_qwarp32_kernel`** `ds4_cuda.cu:21316`  
  Un ID negativo legge l'esperto 0; il clamp non limita i valori gate negativi
- **`moe_gate_up_mid_q2K_decode_q8_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:2005`  
  La clamp del gate è solo superiore; write_aux controlla soltanto gate/up.
- **`moe_gate_up_mid_q2K_expert_batch_sharedx_kernel`** `rocm/ds4_rocm_moe.cuh:3493`  
  max_count è esclusivo; OUT_F16 decide quale solo puntatore di uscita viene scritto.
- **`moe_gate_up_mid_q2K_f32_kernel`** `rocm/ds4_rocm_moe.cuh:4401`  
  La riduzione shared presume blockDim potenza di due; selected negativo diventa zero.
- **`moe_gate_up_mid_q2K_hotlist_wmma_n2_kernel`** `rocm/ds4_rocm_moe.cuh:3905`  
  OUT_F16 sceglie un solo buffer di uscita; l'altro non viene toccato.
- **`moe_gate_up_mid_q2K_rows_w32_kernel`** `rocm/ds4_rocm_moe.cuh:3251`  
  store_gate_up a zero sopprime gate/up ma non mid_out.
- **`moe_gate_up_mid_q2K_rows_w32_ptrs_kernel`** `rocm/ds4_rocm_moe.cuh:3363`  
  pair_missing nullo disabilita il filtro e processa tutte le coppie.
- **`moe_gate_up_mid_q4K_expert_tile4_row32_kernel`** `rocm/ds4_rocm_moe.cuh:1671`  
  max_count zero disattiva il filtro e write_aux zero sopprime solo gate/up.
- **`moe_gate_up_mid_q4K_expert_tile8_row32_kernel`** `rocm/ds4_rocm_moe.cuh:1754`  
  atomicità assente: ogni coppia-riga deve avere un solo produttore.
- **`moe_gate_up_mid_q4K_expert_tile8_rowspan_kernel`** `ds4_cuda.cu:23163`  
  Con write_aux a zero non aggiorna gate_out e up_out
- **`moe_gate_up_mid_q4K_sorted_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:1622`  
  Gli esperti negativi vengono sostituiti con l'esperto 0.
- **`moe_gate_up_mid_q4K_tile16_mma_kernel`** `ds4_cuda.cu:24386`  
  Le coppie mancanti sono azzerate in shared, ma gate e up restano intatti se write_aux è falso
- **`moe_gate_up_mid_q4K_tile8_mma_kernel`** `ds4_cuda.cu:24018`  
  write_aux falso lascia gate_out e up_out intatti mentre mid_out viene sempre scritto
- **`moe_gate_up_mid_qwarp32_kernel`** `rocm/ds4_rocm_moe.cuh:688`  
  Un esperto negativo diventa l'esperto 0 e gate/up vengono sempre scritti
- **`moe_gate_up_mid_qwarp32_ptrs_kernel`** `rocm/ds4_rocm_moe.cuh:741`  
  Un puntatore nullo fa uscire il gruppo lasciando l'output invariato.
- **`moe_gate_up_mid_qwarp32_ptrs_split_kernel`** `rocm/ds4_rocm_moe.cuh:796`  
  Se pair_missing è nullo il kernel non elabora alcuna coppia.
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
- **`moe_scatter_sorted_pairs_deterministic_kernel`** `rocm/ds4_rocm_moe.cuh:1034`  
  Ogni esperto scandisce serialmente tutte le coppie, con costo O(E per coppie).
- **`moe_scatter_sorted_pairs_kernel`** `rocm/ds4_rocm_moe.cuh:1017`  
  L'ordine delle coppie dentro ciascun esperto è nondeterministico
- **`moe_silu_oldhip`** `rocm/ds4_rocm_moe.cuh:3182`  
  Il nome oldhip non implica un'approssimazione: usa expf direttamente.
- **`moe_sum_f16_kernel`** `rocm/ds4_rocm_moe.cuh:2885`  
  Converte ogni addendo separatamente da FP16 a FP32.
- **`moe_sum_f16x2_kernel`** `rocm/ds4_rocm_moe.cuh:2896`  
  Una out_dim dispari perde silenziosamente l'ultima colonna.
- **`moe_sum_kernel`** `rocm/ds4_rocm_moe.cuh:2874`  
  Non consulta selected: anche gli slot invalidi o stantii entrano nella somma
- **`moe_sum_owned_kernel`** `ds4_cuda.cu:25111`  
  Oltre sei esperti vengono ignorati silenziosamente
- **`moe_tile16_mma_pass`** `ds4_cuda.cu:24311`  
  Restituisce i risultati nei registri e non scrive direttamente alcun tensore
- **`more_line`** `ds4_help.c:428`  
  L'indice colore statico persiste tra chiamate e invocazioni di help
- **`mtp_weights_bind`** `ds4.c:6820`  
  I nomi sono fissati esclusivamente allo stadio mtp.0.
- **`mtp_weights_validate_layout`** `ds4.c:5150`  
  Alcuni tensori plain accettano F16 o F32 mentre le proiezioni principali esigono Q8_0.
- **`need_arg`** `ds4_server.c:12877`  
  Incrementa direttamente l'indice del ciclo del chiamante.
- **`next_frontier`** `ds4_bench.c:490`  
  A ctx_max restituisce ancora ctx_max: il chiamante deve interrompere il ciclo.
- **`next_generation`** `src/cuda/dynamic_arena.cu:157`  
  Al wrap salta zero e riparte da uno
- **`next_pending_case`** `ds4_eval.c:4017`  
  La ricerca è circolare e include subito l'indice start.
- **`next_pow2`** `ds4.c:35569`  
  Per n uguale a zero restituisce uno; non rileva overflow dello shift.
- **`next_utf8_char`** `ds4.c:36106`  
  Si fida del byte iniziale e non verifica i byte di continuazione
- **`normalize_compsec_line_spec`** `ds4_eval.c:2936`  
  Ignora tutto salvo cifre e trattini e tronca silenziosamente l'output.
- **`normalize_integer_answer`** `ds4_eval.c:2869`  
  Tronca silenziosamente se il buffer è corto e conserva uno zero finale.
- **`normalized_policy`** `src/cuda/route_worker.cpp:57`  
  Non corregge enabled e accetta zero; un cap sotto il floor viene alzato senza avviso.
- **`now_ns`** `src/cuda/route_worker.cpp:39`  
  Il valore è relativo a un'epoca arbitraria, non al tempo civile.
- **`observe_device`** `src/cuda/prefill_observer.cu:407`  
  Con n_tokens minore o uguale a 1 finalizza senza osservare i buffer passati.
- **`observe_host`** `src/cuda/prefill_observer.cu:477`  
  Non controlla enabled: richiede che request_begin abbia già armato lo stato.
- **`observe_tool_markers`** `ds4_server.c:4818`  
  Un end prima di uno start nello stesso buffer non viene marcato orfano
- **`openai_function_schema_from_tool`** `ds4_server.c:1451`  
  Restituisce al primo membro function senza verificare il resto dell'oggetto.
- **`openai_sse_finish_live`** `ds4_server.c:6692`  
  Il fallback strutturato scatta solo se nessun tool live è mai stato emesso
- **`openai_sse_stream_update`** `ds4_server.c:6610`  
  A fine stream senza </think> invia tutto come reasoning e sopprime content
- **`openai_stream_free`** `ds4_server.c:5845`  
  Libera solo gli ID tool e non azzera active o gli altri campi
- **`openai_stream_start`** `ds4_server.c:5831`  
  Il think mode parte in reasoning anche prima di vedere il tag <think>
- **`openai_tool_emit_args_fragment`** `ds4_server.c:6389`  
  Usa sempre l'indice tool corrente dello stato
- **`openai_tool_emit_param_prefix`** `ds4_server.c:6410`  
  Aggiorna first_param prima di sapere se l'invio riesce
- **`openai_tool_emit_string_value`** `ds4_server.c:6395`  
  Le entità sconosciute restano letterali negli arguments
- **`openai_tool_finish_param`** `ds4_server.c:6516`  
  I valori non stringa vengono inoltrati senza validazione JSON
- **`openai_tool_start_invoke`** `ds4_server.c:6466`  
  Un tag incompleto restituisce true senza avanzare
- **`openai_tool_start_param`** `ds4_server.c:6490`  
  Richiede string esplicito, mentre il parser finale lo assume true se manca
- **`openai_tool_stream_fail`** `ds4_server.c:6460`  
  Restituisce true anche se ha appena marcato un errore
- **`openai_tool_stream_free`** `ds4_server.c:5837`  
  ids_cap è capacità, quindi visita anche slot mai usati
- **`openai_tool_stream_has_id`** `ds4_server.c:5850`  
  Il limite upto è esclusivo e viene tagliato solo superiormente
- **`openai_tool_stream_id`** `ds4_server.c:5860`  
  Il ciclo di generazione non ha un limite ai tentativi di collisione
- **`openai_tool_stream_init`** `ds4_server.c:6424`  
  Un marcatore sconosciuto distrugge lo stato precedente e imposta errore
- **`openai_tool_stream_update`** `ds4_server.c:6534`  
  Una sintassi malformata disattiva lo stream ma spesso restituisce true
- **`opendir`** `src/win32/win_dirent.h:33`  
  Restituisce NULL anche per directory vuota o senza elementi corrispondenti
- **`opt`** `ds4_help.c:77`  
  Il layout cambia del tutto quando il colore ciano è disponibile
- **`option_name_has_switch`** `ds4_help.c:48`  
  Riconosce lo switch solo a inizio stringa o dopo uno spazio
- **`options_from_env`** `src/cuda/dynamic_arena.cu:330`  
  UNLOCK_WAVE_GIB non abilita lo sblocco; serve UNLOCK_SOURCE_RANGES=1
- **`os_cond_broadcast`** `src/platform/os_thread.h:96`  
  I waiter devono ricontrollare il predicato dopo il risveglio
- **`os_cond_destroy`** `src/platform/os_thread.h:97`  
  Su Windows non esegue alcuna distruzione
- **`os_cond_init`** `src/platform/os_thread.h:79`  
  Ritorna sempre 0: l'inizializzazione non segnala errori
- **`os_cond_signal`** `src/platform/os_thread.h:95`  
  Una notifica senza waiter attivi viene persa
- **`os_cond_timedwait_ms`** `src/platform/os_thread.h:82`  
  Distingue timeout con 1 ed errori con -1
- **`os_cond_wait`** `src/platform/os_thread.h:80`  
  Può svegliarsi senza che il predicato atteso sia vero
- **`os_console_init`** `src/platform/os_console.h:17`  
  Disabilita globalmente il buffering e ignora gli errori delle chiamate.
- **`os_cpu_count`** `src/platform/os_thread.h:111`  
  Se Windows riporta zero, restituisce silenziosamente uno
- **`os_file_close`** `src/platform/os_file.c:204`  
  Scarta ogni errore restituito da CloseHandle o close.
- **`os_file_dup`** `src/platform/os_file.c:123`  
  Il duplicato condivide l'offset con la sorgente; non riapre il percorso.
- **`os_file_init`** `src/platform/os_file.c:70`  
  Con f nullo non segnala errore e non fa nulla.
- **`os_file_open_read`** `src/platform/os_file.c:88`  
  Su Windows forza I/O overlapped e suggerimento random access.
- **`os_file_reopen_read_sequential`** `src/platform/os_file.c:146`  
  Su POSIX esegue solo dup e ignora overlapped e il suggerimento sequenziale.
- **`os_file_size`** `src/platform/os_file.c:215`  
  Su errore restituisce UINT64_MAX, valore confondibile con una dimensione valida.
- **`os_fopen`** `src/platform/os_file.c:183`  
  Su Windows ricalcola errno da GetLastError dopo _wfopen, forse non pertinente.
- **`os_localtime`** `ds4_server.c:233`  
  Ignora l'eventuale errore della conversione
- **`os_mmap_close`** `src/platform/os_mmap.c:76`  
  Dopo la chiusura reinizializza m, rendendo innocua una chiusura successiva.
- **`os_mmap_cold`** `src/platform/os_mmap.c:102`  
  Limita len alla mappa ma ignora gli errori, inclusi offset non allineati.
- **`os_mmap_init`** `src/platform/os_mmap.c:13`  
  Su una struttura già aperta azzera i riferimenti senza liberarne le risorse.
- **`os_mmap_open`** `src/platform/os_mmap.c:23`  
  Passa sempre shared=0, quindi su POSIX crea un mapping privato.
- **`os_mmap_open_read`** `src/platform/os_mmap.c:27`  
  Su Windows shared è ignorato; i file vuoti sono rifiutati con EINVAL.
- **`os_mmap_warm`** `src/platform/os_mmap.c:91`  
  Ignora gli errori di posix_madvise ed è un no-op se l'advice non è disponibile.
- **`os_monotonic_sec`** `src/platform/os_clock.h:18`  
  La frequenza e' memorizzata in una static locale distinta per ogni unita' di traduzione.
- **`os_mutex_destroy`** `src/platform/os_thread.h:78`  
  Su Windows non esegue alcuna distruzione
- **`os_mutex_init`** `src/platform/os_thread.h:75`  
  Ritorna sempre 0: InitializeSRWLock non segnala errori
- **`os_mutex_lock`** `src/platform/os_thread.h:76`  
  Non supporta ricorsione e può causare deadlock
- **`os_mutex_unlock`** `src/platform/os_thread.h:77`  
  Il rilascio da un thread non proprietario è comportamento indefinito
- **`os_once`** `src/platform/os_thread.h:98`  
  Ignora l'esito di InitOnceExecuteOnce, quindi il chiamante non rileva errori
- **`os_once_trampoline`** `src/platform/os_thread.c:16`  
  È richiamata indirettamente da Win32 e restituisce sempre successo
- **`os_pread`** `src/platform/os_file.c:606`  
  Su Windows crea un evento per chiamata; un risultato corto indica EOF.
- **`os_pread_cancel`** `src/platform/os_file.c:329`  
  Registra la cancellazione anche senza AIO attivo e su POSIX restituisce sempre 1.
- **`os_pread_cancellable`** `src/platform/os_file.c:543`  
  UINT32_MAX disabilita il timeout ma non la cancellazione per sequenza.
- **`os_pread_cancellable_destroy`** `src/platform/os_file.c:289`  
  Può attendere senza limite se la cancellazione non conclude l'I/O.
- **`os_pread_cancellable_init`** `src/platform/os_file.c:234`  
  Azzera l'intera struttura, quindi distrugge senza avviso un eventuale stato attivo.
- **`os_pread_cancellable_max_chunk`** `src/platform/os_file.c:550`  
  Il limite richiesto viene ridotto a 1 GiB su Windows o a SSIZE_MAX su POSIX.
- **`os_pread_cancellable_pending`** `src/platform/os_file.c:262`  
  Scarta l'esito dell'AIO completato e restituisce solo se è ancora in corso.
- **`os_pread_cancellable_prepare`** `src/platform/os_file.c:246`  
  Su POSIX restituisce sempre successo senza preparare alcuna risorsa.
- **`os_pread_cancellable_reset`** `src/platform/os_file.c:317`  
  Dopo il reset, una lettura con sequence 0 risulta già cancellata.
- **`os_pread_cancellable_timeout`** `src/platform/os_file.c:351`  
  Può tornare timeout o cancellazione lasciando l'AIO e il buffer ancora attivi.
- **`os_pread_plain`** `src/platform/os_file.c:574`  
  Su Windows sposta il file pointer; su ogni piattaforma può leggere meno di len.
- **`os_random_bytes`** `src/platform/os_random.h:20`  
  Il cast di len a ULONG tronca richieste oltre 4 GiB
- **`os_thread_create`** `src/platform/os_thread.h:99`  
  Il thread può partire prima che l'handle venga scritto in t
- **`os_thread_detach`** `src/platform/os_thread.h:110`  
  Chiudere l'handle non ferma il thread, che continua in background
- **`os_thread_join`** `src/platform/os_thread.h:102`  
  Consuma l'handle: dopo il join non può più essere usato
- **`os_thread_join_timeout`** `src/platform/os_thread.c:76`  
  Timeout ed errore valgono entrambi 0 e lasciano aperto l'handle
- **`os_thread_trampoline`** `src/platform/os_thread.c:27`  
  Libera il descrittore prima della callback e ne scarta il valore di ritorno
- **`os_utf8_to_wide`** `src/platform/os_path.h:22`  
  Restituisce -1 per conversione fallita e -2 per output insufficiente; il conteggio include il NUL.
- **`os_wide_to_utf8`** `src/platform/os_path.h:16`  
  Il valore restituito conta anche il NUL; ogni errore e riportato come -1.
- **`os_win_error_to_errno`** `src/platform/os_file.c:41`  
  ERROR_HANDLE_EOF diventa 0; ogni errore sconosciuto diventa EIO.
- **`output_hc_head_one`** `ds4.c:14271`  
  I pesi sigmoid ricevono epsilon ma non vengono normalizzati a somma uno.
- **`output_hc_weights_kernel`** `rocm/ds4_rocm_output.cuh:6`  
  I gate non sono normalizzati e l'aggiunta di eps può portarli sopra 1
- **`output_logits_glm_one`** `ds4.c:15113`  
  Alloca il buffer norm a ogni chiamata.
- **`output_logits_glm_one_f32_ref`** `ds4.c:14976`  
  I pesi output sono Q8_0 benché l'accumulo sia F32 reference.
- **`output_logits_one`** `ds4.c:14299`  
  Alloca due buffer heap a ogni testa calcolata.
- **`output_logits_one_decode_scratch`** `ds4.c:15127`  
  Sovrascrive i buffer output condivisi dello scratch a ogni chiamata.
- **`owned_copy`** `ds4.c:36013`  
  La copia non aggiunge il terminatore NUL
- **`pack_slot_rows_f32_kernel`** `rocm/ds4_rocm_common.cuh:334`  
  Trasforma un layout slot-major in row-major; non copia le righe oltre n_rows.
- **`para`** `ds4_help.c:96`  
  Senza giallo stampa comunque il testo
- **`parse_anthropic_content`** `ds4_server.c:2100`  
  Un tipo top-level non supportato viene solo saltato e può risultare in contenuto vuoto.
- **`parse_anthropic_content_block`** `ds4_server.c:1968`  
  Ignora role e classifica solo tramite type, tollerando membri fuori ordine.
- **`parse_anthropic_messages`** `ds4_server.c:2135`  
  Ruolo e contenuto mancanti diventano rispettivamente user e stringa vuota.
- **`parse_anthropic_request`** `ds4_server.c:3345`  
  Inserisce system in coda ai messaggi, ma il renderer lo colloca semanticamente in testa.
- **`parse_anthropic_system`** `ds4_server.c:2241`  
  Un tipo top-level non supportato viene saltato e trasformato in stringa vuota.
- **`parse_anthropic_system_object`** `ds4_server.c:2206`  
  Campi diversi da text sono ignorati e il filtro può eliminare il testo senza errore.
- **`parse_backend`** `ds4_eval.c:1511`  
  Un nome invalido termina il processo con exit(2).
- **`parse_backend_arg`** `ds4_server.c:12943`  
  Nelle build ROCm accetta rocm ma non la parola cuda.
- **`parse_bool`** `src/cuda/vram_expert_cache.cpp:115`  
  Qualunque testo diverso da 0 o 1 restituisce il default ma marca valid=false
- **`parse_case_sequence`** `ds4_eval.c:4026`  
  Accetta duplicati e anche una virgola finale.
- **`parse_chat_request`** `ds4_server.c:3168`  
  Un tool_choice oggetto è ignorato; solo la stringa none disabilita gli strumenti.
- **`parse_completion_request`** `ds4_server.c:4539`  
  Aggiunge sempre il system You are a helpful assistant, quindi non usa il prompt completion grezzo.
- **`parse_csv_int_list`** `ds4_gpu_args.c:45`  
  Accetta spazi iniziali, nonostante il commento dica di vietarli.
- **`parse_deepseek_generated_message_ex`** `ds4_server.c:5010`  
  Senza </think> richiesto restituisce successo ma ignora ogni DSML nel reasoning
- **`parse_double`** `src/cuda/vram_expert_cache.cpp:94`  
  Un valore presente ma invalido lascia result invariato e restituisce false.
- **`parse_double_arg`** `ds4_bench.c:135`  
  Accetta zero e negativi; i vincoli semantici restano al chiamante.
- **`parse_float_arg`** `ds4_server.c:12867`  
  La stringa nan supera i confronti di intervallo e viene accettata.
- **`parse_float_range`** `ds4_cli.c:233`  
  Gli estremi min e max sono accettati.
- **`parse_function_call`** `ds4_server.c:1335`  
  Può riuscire senza nome o argomenti; sarà il chiamante a scartare la chiamata.
- **`parse_generated_message_ex`** `ds4_server.c:5343`  
  La sintassi è fissata a DeepSeek
- **`parse_generated_message_ex_for_syntax`** `ds4_server.c:5327`  
  Qualunque valore diverso da GLM ricade silenziosamente su DeepSeek
- **`parse_generated_message_for_response`** `ds4_server.c:5472`  
  La sintassi è fissata a DeepSeek
- **`parse_generated_message_for_response_for_syntax`** `ds4_server.c:5430`  
  Sul fallback riempie content col testo grezzo ma restituisce false
- **`parse_glm_generated_message_ex`** `ds4_server.c:5197`  
  Il testo dopo l'ultimo tool_call non viene restituito come content
- **`parse_gpu_vram_arg`** `ds4_gpu_args.c:101`  
  Il valore 0 disabilita CUDA; --gpu-devices senza --gpu-vram attiva auto.
- **`parse_int`** `ds4_cli.c:203`  
  Su errore chiama exit(2) anziché restituire un codice.
- **`parse_int_arg`** `ds4_server.c:12847`  
  Su errore termina direttamente il processo con exit 2.
- **`parse_line_spec`** `ds4_eval.c:2994`  
  Inverte gli intervalli discendenti e scarta di fatto valori interamente oltre il limite.
- **`parse_messages`** `ds4_server.c:1876`  
  Ruolo assente diventa user e contenuto assente diventa stringa vuota.
- **`parse_metadata`** `ds4.c:2401`  
  Un allineamento assente, nullo o mal tipizzato lascia silenziosamente il default 32
- **`parse_nonneg_int_arg`** `ds4_server.c:12857`  
  Su errore termina direttamente il processo con exit 2.
- **`parse_nonnegative_int`** `ds4_cli.c:213`  
  A differenza di parse_int, accetta zero.
- **`parse_nonnegative_int_arg`** `ds4_eval.c:1473`  
  Su input invalido termina direttamente con exit(2).
- **`parse_options`** `ds4_server.c:12970`  
  --imatrix-out imposta Metal, ma un'opzione backend successiva può sovrascriverlo.
- **`parse_output_config_effort`** `ds4_server.c:1110`  
  Null o valori non oggetto hanno successo senza cambiare l'effort
- **`parse_power_percent`** `ds4_cli.c:1307`  
  Non stampa errori e non modifica out se la conversione fallisce.
- **`parse_prompt`** `ds4_server.c:4509`  
  Ignora tutti gli elementi dopo il primo; un tipo scalare non supportato diventa stringa vuota.
- **`parse_reasoning_effort_name`** `ds4_server.c:1038`  
  minimal, low, medium, high e xhigh collassano tutti su HIGH
- **`parse_reasoning_effort_value`** `ds4_server.c:1061`  
  Il valore null ha successo senza modificare l'output
- **`parse_responses_content_array`** `ds4_server.c:3567`  
  null top-level e text:null sono ammessi, ma un elemento null nell'array è rifiutato.
- **`parse_responses_input`** `ds4_server.c:3697`  
  Un type assente diventa message; compaction e context_compaction sono ignorati.
- **`parse_responses_reasoning`** `ds4_server.c:4173`  
  Un valore non oggetto viene saltato con successo; effort:null non conta come controllo esplicito.
- **`parse_responses_request`** `ds4_server.c:4240`  
  Rifiuta tool forzati e riferimenti durable non null; instructions viene inserito in testa.
- **`parse_schema_properties`** `ds4_server.c:1633`  
  Può avere già aggiunto proprietà quando un errore successivo fa restituire false.
- **`parse_stop`** `ds4_server.c:1205`  
  Valori non stringa sono ignorati; uno scalare non stringa può riuscire con lista vuota.
- **`parse_stream_options`** `ds4_server.c:1302`  
  Un valore non oggetto viene saltato e considerato valido senza cambiare include_usage.
- **`parse_tensors`** `ds4.c:2431`  
  Un tipo ignoto genera solo un warning e lascia bytes a zero, saltando il controllo dei limiti
- **`parse_thinking_control_value`** `ds4_server.c:1071`  
  Null, tipi estranei e oggetti senza type hanno successo lasciando invariato l'output
- **`parse_tool_calls_value`** `ds4_server.c:1383`  
  Le voci prive di nome o argomenti sono scartate in silenzio; null è accettato.
- **`parse_tools_value`** `ds4_server.c:1831`  
  Un oggetto tool non riconosciuto viene conservato grezzo; null diventa stringa vuota.
- **`parse_u32`** `src/cuda/vram_expert_cache.cpp:72`  
  Un valore presente ma invalido lascia result invariato e restituisce false.
- **`parse_u64`** `ds4_cli.c:223`  
  Accetta input negativi come grandi uint64_t e non controlla ERANGE.
- **`parse_u64_arg`** `ds4_eval.c:1483`  
  Non controlla errno: una stringa negativa può essere accettata da strtoull.
- **`pasteBufferAppend`** `linenoise.c:2122`  
  Può espandere il buffer editor anche se la successiva riserva temporanea fallisce.
- **`pasteBufferReserve`** `linenoise.c:2091`  
  Può portare la capacità direttamente al massimo prima di rifiutare la richiesta.
- **`path_join`** `ds4_server.c:9151`  
  Restituisce memoria allocata che il chiamante deve liberare.
- **`payload_copy_file_bytes`** `ds4.c:48502`  
  In caso di errore il file destinazione resta parzialmente scritto.
- **`payload_get_u32`** `ds4.c:48415`  
  Il formato è sempre little-endian, indipendente dall'host.
- **`payload_put_u32`** `ds4.c:48408`  
  Il formato è sempre little-endian, indipendente dall'host.
- **`payload_read_bytes`** `ds4.c:48436`  
  Dopo una lettura parziale fallita, remaining resta invariato.
- **`payload_read_glm_compact_span`** `ds4.c:48798`  
  Un file f32 viene ristretto a f16 quando così è configurata la cache.
- **`payload_read_glm_full_kv_span`** `ds4.c:48816`  
  Con count zero non valida tensore né buffer.
- **`payload_read_or_skip_glm_full_kv_span`** `ds4.c:48826`  
  Un tensore nullo fa scartare silenziosamente tutto lo span full-KV.
- **`payload_read_tensor_span`** `ds4.c:48687`  
  Un errore può lasciare il tensore aggiornato solo in parte.
- **`payload_read_tensor_span_f32_as_f16`** `ds4.c:48749`  
  La conversione f32-f16 può perdere precisione rispetto al file.
- **`payload_read_u32`** `ds4.c:48487`  
  Dopo una lettura parziale fallita, remaining non viene decrementato.
- **`payload_set_err`** `ds4.c:48404`  
  Con errlen zero ignora silenziosamente anche msg.
- **`payload_skip_bytes`** `ds4.c:48456`  
  Con bytes zero rifiuta comunque un buffer nullo o cap zero.
- **`payload_u64_add`** `ds4.c:48605`  
  Su overflow restituisce false e lascia invariato l'accumulatore.
- **`payload_u64_add_tensor_bytes`** `ds4.c:48618`  
  Conta sempre sizeof(float), anche per cache residenti f16.
- **`payload_u64_mul`** `ds4.c:48611`  
  Su overflow restituisce false senza impostare out.
- **`payload_write_bytes`** `ds4.c:48422`  
  Un errore può lasciare sul file un payload scritto solo in parte.
- **`payload_write_glm_compact_span`** `ds4.c:48789`  
  Il formato su disco resta f32 anche quando la cache è f16.
- **`payload_write_glm_full_kv_span`** `ds4.c:48807`  
  Con count zero non valida tensore né buffer.
- **`payload_write_tensor_span`** `ds4.c:48665`  
  Un errore può lasciare sul file solo la prima parte dello span.
- **`payload_write_tensor_span_f16_as_f32`** `ds4.c:48710`  
  offset_f16 è espresso in byte, mentre count è espresso in elementi.
- **`payload_write_u32`** `ds4.c:48481`  
  Un errore può lasciare meno di quattro byte nel file.
- **`physical_memory_available`** `src/cuda/dynamic_arena.cu:310`  
  Misura RAM host, non memoria CUDA né VRAM
- **`plain_reset_color`** `ds4_eval.c:2421`  
  Con use_color falso non emette nulla.
- **`plain_set_thinking_color`** `ds4_eval.c:2417`  
  Con use_color falso non emette nulla.
- **`positive_slot_request`** `src/cuda/vram_expert_cache.cpp:25`  
  Anche -1 o un overflow sono accettati come richiesta positiva.
- **`prefill_layer_major_cpu`** `ds4.c:14026`  
  Attenzione batch è default; FFN batch si abilita solo con DS4_BATCHED_FFN presente.
- **`prepare_locked`** `src/cuda/dynamic_arena.cu:446`  
  Alloca RAM host, non VRAM; l'alias device ottenuto non viene conservato
- **`print_agent_sessions`** `ds4_help.c:319`  
  /strip elimina il payload KV ma conserva la cronologia ricostruibile
- **`print_agent_specific`** `ds4_help.c:308`  
  Il prompt grezzo vale soltanto con -p non interattivo
- **`print_bench_specific`** `ds4_help.c:371`  
  Un valore gen-tokens pari a zero trasforma il benchmark in solo prefill
- **`print_cli_commands`** `ds4_help.c:296`  
  Il titolo rosso perde enfasi quando l'output non è un TTY
- **`print_cli_diagnostics`** `ds4_help.c:274`  
  Documenta test Metal anche nelle build non Metal
- **`print_cli_specific`** `ds4_help.c:263`  
  Le diagnostiche compaiono solo quando full è vero
- **`print_colored_option_name`** `ds4_help.c:58`  
  Senza switch colora ogni parola come opzione
- **`print_default`** `ds4_help.c:556`  
  Il riepilogo server omette le regole di thinking
- **`print_diag_top`** `ds4_cli.c:946`  
  Si arresta al primo id negativo anche se n è maggiore.
- **`print_distributed`** `ds4_help.c:233`  
  Presenta il tensor parallelism come un solo worker diviso 50/50
- **`print_eval_report`** `ds4_eval.c:4142`  
  Array token assenti valgono zero; una risposta vuota viene mostrata come '-'.
- **`print_eval_specific`** `ds4_help.c:389`  
  Il regrade di una trace non carica il modello
- **`print_examples`** `ds4_help.c:467`  
  Gli argomenti api e kv-cache selezionano gli stessi esempi server
- **`print_generated_token`** `ds4_cli.c:515`  
  Esegue fflush per ogni token.
- **`print_kv_cache`** `ds4_help.c:356`  
  Descrive la cache KV ma non legge né scrive cache o VRAM
- **`print_layer_range_for_tier`** `ds4_layer_pack.c:66`  
  Stampa un solo intervallo primo-ultimo anche se le assegnazioni del tier sono discontinue.
- **`print_model_runtime`** `ds4_help.c:152`  
  Il testo cambia a compilazione ROCm e full nasconde o mostra opzioni avanzate
- **`print_more_info`** `ds4_help.c:440`  
  La sequenza cromatica dipende dalle precedenti chiamate a more_line
- **`print_repl_help`** `ds4_cli.c:1294`  
  La soglia Think Max è scritta letteralmente come 393216 token.
- **`print_sampling`** `ds4_help.c:205`  
  full decide se mostrare input e system prompt, non solo dettagli di sampling
- **`print_server_api`** `ds4_help.c:334`  
  Alias di modelli diversi servono entrambi lo stesso GGUF caricato
- **`print_server_thinking`** `ds4_help.c:346`  
  In thinking ignora i parametri di sampling del client
- **`print_steering`** `ds4_help.c:225`  
  Indica FFN attivo di default col file, mentre attenzione resta a zero
- **`print_top_logits`** `ds4.c:37475`  
  k viene silenziosamente limitato a 16.
- **`print_topic`** `ds4_help.c:511`  
  Per l'agente commands stampa la stessa sezione sessions
- **`print_trimmed`** `ds4_eval.c:1813`  
  Misura e tronca byte, non colonne Unicode.
- **`print_vec_stats`** `ds4.c:15191`  
  Scrive su stdout e con n zero divide per zero.
- **`publish_transaction`** `src/cuda/dynamic_arena.cu:606`  
  Accetta checksum già memorizzati senza ricalcolarli
- **`q1_0_sidecar_bind`** `ds4.c:6218`  
  Con apply falso valida e misura tutto ma non collega alcun peso.
- **`q2_K_dequant_256_direct`** `rocm/ds4_rocm_moe.cuh:2953`  
  Non ha chiamanti nel sorgente analizzato.
- **`q2_K_dequant_256_scaled_w32`** `rocm/ds4_rocm_moe.cuh:2934`  
  Non valida lane o kk e usa direttamente il layout compatto a 84 byte.
- **`q2_K_dequant_dual_pair_tile_half_rowwise`** `rocm/ds4_rocm_moe.cuh:3109`  
  È consumata soltanto dal kernel WMMA compilato nel blocco HIP.
- **`q2_K_dequant_dual_tile_half_rowwise`** `rocm/ds4_rocm_moe.cuh:3008`  
  Non ha chiamanti nel sorgente analizzato.
- **`q2_K_dequant_pair_tile_half_rowwise`** `rocm/ds4_rocm_moe.cuh:3060`  
  È usata soltanto dal percorso WMMA racchiuso nel blocco HIP.
- **`q2_K_dequant_tile_half_rowwise`** `rocm/ds4_rocm_moe.cuh:2968`  
  Le righe oltre out_dim vengono riempite esplicitamente con zeri.
- **`q2_K_scale_broadcast_w32`** `rocm/ds4_rocm_moe.cuh:2916`  
  Scala e minimo sono letti dagli offset fissi 80 e 82.
- **`q2_k_value_f32`** `ds4.c:3557`  
  Non controlla i limiti dell'indice
- **`q4_k_get_scale_min`** `ds4.c:3579`  
  Non valida j e usa layout diversi per i primi e gli ultimi quattro gruppi
- **`q8_0_dequant_f16_kernel`** `ds4_cuda.cu:16032`  
  Due thread cooperano su ogni blocco Q8_0 da 32 valori
- **`q8_0_scale_broadcast_oldhip_w32`** `rocm/ds4_rocm_q8.cuh:1159`  
  Solo la lane 0 legge la scala dalla memoria
- **`q8_0_scale_broadcast_w32`** `rocm/ds4_rocm_q8.cuh:389`  
  Solo la lane 0 accede davvero ai due byte della scala
- **`q8_0_scale_scalar`** `rocm/ds4_rocm_q8.cuh:384`  
  Ricostruisce esplicitamente l'ordine little-endian
- **`q8_K_q8_0_quantize_kernel`** `ds4_cuda.cu:21003`  
  Scrive otto blocchi Q8_0 per ogni blocco Q8_K
- **`q8_K_quantize_kernel`** `rocm/ds4_rocm_moe.cuh:483`  
  La scala può essere negativa perché conserva il segno del massimo assoluto
- **`q8_K_quantize_owned_kernel`** `ds4_cuda.cu:21099`  
  Le righe non possedute restano intatte, non vengono azzerate
- **`q8_K_quantize_sidecar_kernel`** `ds4_cuda.cu:21177`  
  La scala deriva dal sidecar, non dai 256 valori x che vengono quantizzati
- **`q8_block_sum_w32`** `rocm/ds4_rocm_q8.cuh:399`  
  Restituisce la somma totale a tutti i thread, non soltanto al thread zero
- **`q8_partial_sum8_kernel`** `rocm/ds4_rocm_q8.cuh:1467`  
  Somma sempre otto piani, senza parametro per cambiarne il numero
- **`q8_top1_float_ordered_key`** `ds4_cuda.cu:7660`  
  Distingue -0 da +0 e ordina i NaN secondo il payload binario, non semanticamente.
- **`q8_top1_pack_key`** `ds4_cuda.cu:7665`  
  A parita' di valore, 0xffffffff - idx fa vincere l'indice piu' piccolo.
- **`q8_top1_unpack_value`** `ds4_cuda.cu:7670`  
  Una chiave ordinata zero viene ricostruita come NaN negativo.
- **`quantize_mid_pairs_worker`** `ds4.c:9111`  
  È definita ma non referenziata nel file.
- **`quantize_q8_0_activation`** `ds4.c:7446`  
  Azzera il padding finale; un blocco tutto zero riceve scala zero.
- **`quantize_q8_0_activation_batch`** `ds4.c:7481`  
  La parallelizzazione è sui token, non sui blocchi di un singolo token.
- **`quantize_q8_0_batch_worker`** `ds4.c:7471`  
  Il grafo la vede senza chiamanti, ma ds4_parallel_for la invoca come callback.
- **`quantize_q8_0_f32_kernel`** `rocm/ds4_rocm_q8.cuh:81`  
  Il blocco finale viene sempre riempito a zero fino a 32 elementi.
- **`quantize_q8_0_group_slice_rows_kernel`** `ds4_cuda.cu:7550`  
  L'uscita usa indici di gruppo compatti, non gli indici originali n_groups_total.
- **`quarter_warp_sum_f32`** `rocm/ds4_rocm_moe.cuh:474`  
  Il parametro lane8 è ignorato; il gruppo deriva solo da threadIdx.x
- **`random_bytes`** `ds4_server.c:333`  
  Converte il ritorno OS zero in true
- **`random_tool_id`** `ds4_server.c:734`  
  Con poca entropia usa un contatore statico non atomico e tronca se il buffer e corto
- **`rank_less`** `src/cuda/prefill_observer.cu:283`  
  A parità di massa usa la chiave layer-esperto crescente.
- **`ranked_target`** `src/cuda/dynamic_arena.cu:1039`  
  A pari priorità vince l'osservazione più recente
- **`raw_full_lit`** `ds4_server.c:5945`  
  Una posizione oltre raw_len fallisce senza distinguere input invalido
- **`raw_partial_any`** `ds4_server.c:5956`  
  Restituisce vero se basta uno dei due letterali parziali
- **`raw_partial_lit`** `ds4_server.c:5950`  
  La coda vuota in pos uguale a raw_len conta come prefisso parziale
- **`raw_partial_lit_min`** `ds4_server.c:6023`  
  Con min_len zero anche una coda vuota può risultare valida
- **`raw_suffix_partial_lit`** `ds4_server.c:6083`  
  Non esiste nella build server normale
- **`raxAddChild`** `rax.c:465`  
  Il puntatore del padre restituito può differire da quello passato.
- **`raxAddChildNoAlloc`** `rax.c:307`  
  Un OOM nel materializzare lo slot 12 può seguire un realloc che ha già spostato il padre.
- **`raxCompare`** `rax.c:2220`  
  Un operatore ignoto di due caratteri che termina con = viene trattato come uguaglianza.
- **`raxCompressNode`** `rax.c:514`  
  Il nodo padre può cambiare indirizzo dopo la riallocazione.
- **`raxCompressNodeNoAlloc`** `rax.c:488`  
  Lo slot del figlio resta da inizializzare al chiamante.
- **`raxDebugShowNode`** `rax.c:2686`  
  Le foglie inline sono stampate come se il valore fosse un puntatore a nodo figlio.
- **`raxDefragAddChars`** `rax.c:2371`  
  Usa memcpy, quindi sorgente e destinazione non devono sovrapporsi.
- **`raxDefragDelChars`** `rax.c:2394`  
  Non controlla l'underflow di key_len.
- **`raxDefragNext`** `rax.c:2436`  
  Restituisce 0 sia a EOF sia su OOM; inoltre salta completamente i valori inline NULL.
- **`raxDefragNodeFlags`** `rax.c:2400`  
  Considera root ogni nodo visitato quando nello stack resta un solo frame.
- **`raxDefragReplaceData`** `rax.c:2564`  
  Accetta newptr NULL, ma il nodo reale resta marcato come dato non-null nel layout.
- **`raxDefragReplaceNode`** `rax.c:2523`  
  Non alloca, copia né valida la dimensione; restituisce il vecchio nodo da liberare al chiamante.
- **`raxDefragStackFree`** `rax.c:2364`  
  Non ripristina i campi; una seconda chiamata può fare double free.
- **`raxDefragStackInit`** `rax.c:2310`  
  Reinizializzare dopo un'espansione perde il buffer heap precedente.
- **`raxDefragStackPeek`** `rax.c:2353`  
  Il puntatore restituito può essere invalidato dal successivo push che rialloca lo stack.
- **`raxDefragStackPop`** `rax.c:2359`  
  Su stack vuoto non segnala errore e non modifica nulla.
- **`raxDefragStackPush`** `rax.c:2319`  
  Su OOM restituisce 0 e imposta errno, senza un flag OOM persistente.
- **`raxDefragStart`** `rax.c:2410`  
  Una tree con head NULL viene trattata come già a EOF.
- **`raxDefragStop`** `rax.c:2588`  
  Non azzera i puntatori; una seconda chiamata può liberare due volte.
- **`raxEOF`** `rax.c:2603`  
  Restituisce il bitmask EOF, non necessariamente il valore intero 1.
- **`raxFind`** `rax.c:1101`  
  Una chiave con valore NULL restituisce NULL; solo raxNotFound segnala l'assenza.
- **`raxFindParentLink`** `rax.c:1124`  
  Se il figlio manca continua a leggere memoria senza alcun limite.
- **`raxFree`** `rax.c:1505`  
  Libera solo i nodi: i payload puntati restano responsabilità del chiamante.
- **`raxFreeWithCallback`** `rax.c:1498`  
  I valori NULL, inclusi quelli inline, non vengono passati alla callback.
- **`raxGenericInsert`** `rax.c:629`  
  Restituisce 0 sia per chiave esistente sia per OOM; errno distingue i casi.
- **`raxGetData`** `rax.c:284`  
  NULL può essere un valore valido; l'assenza di chiave non viene controllata.
- **`raxInsert`** `rax.c:1087`  
  Un aggiornamento riuscito di una chiave esistente restituisce comunque 0.
- **`raxIsInlineLeaf`** `rax.c:189`  
  Gli indici negativi o da 13 in su restituiscono sempre falso.
- **`raxIteratorAddChars`** `rax.c:1529`  
  Su OOM conserva il buffer precedente e imposta errno.
- **`raxIteratorClearInlineLeaf`** `rax.c:1561`  
  Non azzera node, node_child o data associati alla foglia virtuale.
- **`raxIteratorCurrentParentLink`** `rax.c:1603`  
  Se node_child è obsoleto esegue una scansione di recupero e può restituire NULL.
- **`raxIteratorDelChars`** `rax.c:1553`  
  Non controlla l'underflow di key_len.
- **`raxIteratorEnterChild`** `rax.c:1578`  
  Se il push fallisce, la chiave è già stata allungata e lo stato resta parziale.
- **`raxIteratorIsInlineLeaf`** `rax.c:1557`  
  Restituisce il bitmask, non necessariamente il valore intero 1.
- **`raxIteratorNextStep`** `rax.c:1680`  
  La prima chiamata dopo seek non avanza: elimina solo RAX_ITER_JUST_SEEKED.
- **`raxIteratorPrevStep`** `rax.c:1803`  
  La prima chiamata dopo seek non arretra: elimina solo RAX_ITER_JUST_SEEKED.
- **`raxIteratorSetData`** `rax.c:2256`  
  Per una foglia inline scrive anche NULL direttamente nello slot senza materializzarla.
- **`raxIteratorSetInlineLeaf`** `rax.c:1565`  
  Non verifica il bitmap né aggiorna la chiave corrente.
- **`raxLowWalk`** `rax.c:559`  
  Ignora il fallimento di push: il risultato arriva comunque, con stack marcato OOM.
- **`raxMaterializeInlineLeaf`** `rax.c:212`  
  Incrementa numnodes ma non numele, perché la chiave esisteva già.
- **`raxNew`** `rax.c:248`  
  L'inizializzazione è pigra nel chiamante, non avviene necessariamente all'avvio.
- **`raxNewNode`** `rax.c:232`  
  Inizializza solo l'header: byte degli archi, padding e puntatori figli restano indefiniti.
- **`raxNewValueNode`** `rax.c:198`  
  Un valore NULL non occupa uno slot dati: viene rappresentato dal flag isnull.
- **`raxNext`** `rax.c:2113`  
  Restituisce 0 sia a EOF sia su OOM; errno vale zero solo nel primo caso.
- **`raxNodeFindChildPos`** `rax.c:294`  
  Con un arco duplicato restituisce la posizione dopo quello esistente.
- **`raxPrev`** `rax.c:2128`  
  Restituisce 0 sia a EOF sia su OOM; errno vale zero solo nel primo caso.
- **`raxRandomWalk`** `rax.c:2152`  
  Con steps zero sceglie una durata casuale e la distribuzione delle chiavi è fortemente distorta.
- **`raxReallocForData`** `rax.c:264`  
  Con data NULL restituisce lo stesso nodo senza riallocare.
- **`raxRecursiveFree`** `rax.c:1469`  
  Una tree molto profonda può esaurire lo stack C.
- **`raxRecursiveShow`** `rax.c:2640`  
  Byte non stampabili nelle chiavi vengono inviati direttamente al terminale.
- **`raxRemove`** `rax.c:1269`  
  Se la ricompressione va in OOM, la rimozione riesce comunque lasciando il ramo non ottimizzato.
- **`raxRemoveChild`** `rax.c:1211`  
  Se il figlio manca la scansione prosegue fuori dal nodo senza limite.
- **`raxRemoveChildAtPtr`** `rax.c:1141`  
  Non riduce l'allocazione heap, anche quando il nodo diventa molto più piccolo.
- **`raxRemoveCleanup`** `rax.c:1226`  
  Può impostare trycompress e restituire un nodo diverso da quello iniziale.
- **`raxSeek`** `rax.c:1899`  
  Controlla solo i primi due caratteri dell'operatore e accetta suffissi spuri.
- **`raxSeekGreatest`** `rax.c:1790`  
  Su nodo reale non aggiorna it->data; il chiamante deve farlo.
- **`raxSetData`** `rax.c:271`  
  Con data NULL imposta isnull ma non cancella eventuali byte del vecchio puntatore.
- **`raxSetDebugMsg`** `rax.c:81`  
  Senza RAX_DEBUG_MSG il flag cambia, ma i messaggi restano compilati via.
- **`raxShow`** `rax.c:2680`  
  Scrive direttamente su stdout e aggiunge sempre un newline finale.
- **`raxSize`** `rax.c:2608`  
  Legge il contatore mantenuto dalle mutazioni, senza verificare la struttura.
- **`raxStackFree`** `rax.c:145`  
  Non ripristina stack, items o maxitems; una seconda chiamata può fare double free.
- **`raxStackInit`** `rax.c:94`  
  Reinizializzare uno stack espanso perde l'allocazione dinamica precedente.
- **`raxStackPeek`** `rax.c:139`  
  NULL indica sia stack vuoto sia un eventuale elemento NULL.
- **`raxStackPop`** `rax.c:131`  
  NULL indica sia stack vuoto sia un eventuale elemento NULL.
- **`raxStackPush`** `rax.c:102`  
  Su OOM imposta un flag permanente e conserva intatti gli elementi già presenti.
- **`raxStart`** `rax.c:1514`  
  Parte in EOF: senza una successiva raxSeek, next e prev non iterano nulla.
- **`raxStop`** `rax.c:2594`  
  Non azzera i puntatori; una seconda chiamata può liberare due volte.
- **`raxTouch`** `rax.c:2719`  
  Termina il processo se incontra due volte il puntatore magico 0x65d1760.
- **`raxTryInsert`** `rax.c:1094`  
  Il valore 0 indica sia chiave esistente sia OOM; va controllato errno.
- **`read_f32_binary_file`** `ds4.c:1768`  
  Una lettura corta salta fclose per il corto circuito logico.
- **`read_file`** `ds4_bench.c:180`  
  Non supporta stream non seekable e termina il processo a ogni errore.
- **`read_http_request`** `ds4_server.c:12503`  
  Non supporta chunked; limita header a 64 KiB e body a 64 MiB.
- **`read_prompt_file`** `ds4_cli.c:1745`  
  Con fatal=true termina con exit(2); altrimenti gli stessi errori restituiscono NULL.
- **`read_runtime_configuration`** `src/cuda/vram_expert_cache.cpp:131`  
  ADMIT_KNOCKS_VRAM=0 abilita comunque l'ammissione per mera presenza.
- **`read_socket_text`** `ds4_server.c:13819`  
  Blocca finché read non restituisce zero o errore.
- **`read_text_file`** `ds4_eval.c:3069`  
  OOM e problemi I/O restituiscono entrambi NULL dopo un messaggio.
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
- **`readdir`** `src/win32/win_dirent.h:55`  
  Riusa lo stesso dirent; se la conversione fallisce restituisce comunque un nome vuoto
- **`refreshLine`** `linenoise.c:1685`  
  Richiede sempre sia pulizia sia riscrittura.
- **`refreshLineWithCompletion`** `linenoise.c:834`  
  La tabella creata internamente non viene liberata per una condizione invertita.
- **`refreshLineWithFlags`** `linenoise.c:1677`  
  Uno stato vecchio ancora visibile forza il renderer multilinea anche con mlmode disattivo.
- **`refreshMultiLine`** `linenoise.c:1512`  
  Gli errori di scrittura vengono ignorati e lo stato visuale può divergere dal terminale.
- **`refreshShowHints`** `linenoise.c:1375`  
  Senza freeHintsCallback un suggerimento allocato dal callback può perdere memoria.
- **`refreshSingleLine`** `linenoise.c:1424`  
  Errori di allocazione o scrittura producono un refresh parziale o nullo senza segnalazione.
- **`refreshStatusLine`** `linenoise.c:1058`  
  Una newline finale è contata nelle righe ma non viene renderizzata.
- **`refreshStatusLinePart`** `linenoise.c:1037`  
  Disabilita temporaneamente l'autowrap del terminale.
- **`regrade_case_outcome`** `ds4_eval.c:3294`  
  Uno stato vuoto è considerato graduabile per compatibilità con trace legacy.
- **`regrade_status_self_test_case`** `ds4_eval.c:3457`  
  Uno status vuoto deve restare graduabile per far passare il test.
- **`regrade_trace_file`** `ds4_eval.c:3309`  
  Fallimenti e cambi di voto non rendono l'esito nonzero; contano solo parse, ignoti o zero casi.
- **`release`** `src/cuda/prefill_observer.cu:402`  
  Anche se cudaFreeHost fallisce, azzera lo stato e perde il puntatore.
- **`release_locked`** `src/cuda/dynamic_arena.cu:432`  
  Un errore di cudaFreeHost non impedisce l'azzeramento dello stato
- **`release_vram_reader`** `src/cuda/dynamic_arena.cu:1228`  
  Se slot o generazione non coincidono, azzera il reader senza rilasciare il claim.
- **`release_writer_claims`** `src/cuda/dynamic_arena.cu:392`  
  Gli indici fuori arena vengono ignorati silenziosamente
- **`remember_thinking_checkpoint`** `ds4_server.c:10834`  
  Non riscrive il KV: memorizza una chiave visibile per lo stato già campionato.
- **`render_chat_prompt_text`** `ds4_server.c:2834`  
  Fissa sempre la sintassi DeepSeek.
- **`render_chat_prompt_text_for_syntax`** `ds4_server.c:2821`  
  Ogni sintassi diversa da GLM ricade implicitamente su DeepSeek.
- **`render_deepseek_chat_prompt_text`** `ds4_server.c:2654`  
  Gli schemi tool precedono il system client; reasoning vecchio può sparire senza contesto tool.
- **`render_deepseek_live_tool_tail`** `ds4_server.c:2860`  
  Anteponde sempre EOS, anche se dalla posizione start non emerge alcun contenuto.
- **`render_glm_chat_prompt_text`** `ds4_server.c:2752`  
  Anche con thinking disattivato inserisce blocchi think vuoti nei messaggi assistant.
- **`render_glm_live_tool_tail`** `ds4_server.c:2910`  
  A differenza della variante DeepSeek non antepone un token EOS.
- **`render_live_tool_tail`** `ds4_server.c:2956`  
  Non è chiamata e forza DeepSeek senza ordini schema.
- **`render_live_tool_tail_for_syntax`** `ds4_server.c:2946`  
  Ogni sintassi diversa da GLM ricade implicitamente su DeepSeek.
- **`render_tokens_text`** `ds4_server.c:9420`  
  Restituisce memoria allocata che il chiamante deve liberare.
- **`rendered_chat_system_region`** `ds4_server.c:10366`  
  Senza marker User o Assistant restituisce tutto il testo residuo come sistema.
- **`renderer_code_begin`** `ds4_agent.c:2730`  
  Imposta fence_info e usa la sintassi predefinita prima di leggere la lingua del fence.
- **`renderer_code_byte`** `ds4_agent.c:2715`  
  Gli spazi iniziali non disattivano md_code_line_start; newline finalizza senza entrare nel buffer.
- **`renderer_code_emit_backtick_literals`** `ds4_agent.c:2725`  
  Ogni backtick attraversa il normale buffering del codice e viene pubblicato subito.
- **`renderer_code_emit_buffered_line`** `ds4_agent.c:2693`  
  Il testo è già stato emesso: l'highlight avviene cancellando e ridisegnando solo righe ASCII corte.
- **`renderer_code_end`** `ds4_agent.c:2775`  
  Una riga finale composta solo da spazi viene scartata invece di essere emessa.
- **`renderer_code_line_append`** `ds4_agent.c:2620`  
  La capacità parte da 256 e raddoppia senza controllo esplicito dell'overflow.
- **`renderer_code_line_can_repaint`** `ds4_agent.c:2641`  
  Rifiuta UTF-8, tab, ESC e righe che arrivano esattamente alla larghezza del terminale.
- **`renderer_code_scan_line`** `ds4_agent.c:2671`  
  Ripristina lo stato commento originale e restituisce separatamente quello finale simulato.
- **`renderer_code_stream_begin`** `ds4_agent.c:2746`  
  A differenza del fence Markdown parte con fence_info disattivato.
- **`renderer_code_stream_set_prefix`** `ds4_agent.c:2763`  
  Memorizza i puntatori senza copiarne il contenuto.
- **`renderer_code_stream_set_upto_marker`** `ds4_agent.c:2770`  
  Il flag ha effetto solo se il renderer incontra il marker speciale previsto.
- **`renderer_code_write_line_prefix`** `ds4_agent.c:2656`  
  Dopo l'eventuale reset ANSI forza color_open a false.
- **`renderer_color`** `ds4_agent.c:3020`  
  Con colori disabilitati non scrive escape ma aggiorna comunque color_open.
- **`renderer_finish`** `ds4_agent.c:3006`  
  Se è uscito testo visibile aggiunge sempre una riga vuota finale.
- **`renderer_flush_utf8`** `ds4_agent.c:2028`  
  Emette anche una sequenza UTF-8 incompleta così com'è.
- **`renderer_has_text_attrs`** `ds4_agent.c:1989`  
  Basta uno qualunque tra think, grassetto, corsivo, inline code o code block.
- **`renderer_markdown_clear_pending`** `ds4_agent.c:2806`  
  Cancella i byte pendenti senza emetterli.
- **`renderer_markdown_commit_backticks`** `ds4_agent.c:2830`  
  Tre o più backtick commutano sempre il blocco, anche se la sequenza è più lunga di tre.
- **`renderer_markdown_emit_pending_literals`** `ds4_agent.c:2811`  
  Nel blocco codice i backtick seguono un percorso diverso dagli asterischi.
- **`renderer_markdown_feed`** `ds4_agent.c:2855`  
  Riconosce solo una sintassi ridotta e filtra la lingua del fence in un buffer fisso.
- **`renderer_markdown_finish`** `ds4_agent.c:2921`  
  Chiude forzatamente anche formattazioni e blocchi lasciati incompleti.
- **`renderer_plain`** `ds4_agent.c:3028`  
  Qualunque n positivo marca output visibile, anche se contiene solo sequenze di controllo.
- **`renderer_process`** `ds4_agent.c:2963`  
  Alla chiusura di think inserisce fino a due newline visibili.
- **`renderer_reset_color`** `ds4_agent.c:1976`  
  Azzera color_open anche quando i colori sono disabilitati e non emette byte.
- **`renderer_restore_text_attrs`** `ds4_agent.c:2010`  
  Non ripristina nulla se color_open è falso, anche quando gli attributi logici sono attivi.
- **`renderer_set_grey`** `ds4_agent.c:1972`  
  Con colori disabilitati non scrive nulla e non aggiorna altro stato.
- **`renderer_set_text_attrs`** `ds4_agent.c:1994`  
  Think e code block hanno precedenza e ritornano prima di grassetto e corsivo.
- **`renderer_space_byte`** `ds4_agent.c:2848`  
  Considera spazio anche ritorno carrello e newline.
- **`renderer_syntax_emit_line`** `ds4_agent.c:2485`  
  I commenti multilinea persistono tra righe, ma una stringa non chiusa no.
- **`renderer_syntax_write`** `ds4_agent.c:2406`  
  In modalità silent registra la presenza di highlight ma non aggiorna stato visibile né scrive byte.
- **`renderer_syntax_write_upto_marker`** `ds4_agent.c:2422`  
  Segna sempre la riga come evidenziata; in modalità silent non emette il marcatore.
- **`renderer_terminal_cols`** `ds4_agent.c:2634`  
  Se ioctl fallisce o riporta zero usa silenziosamente 80 colonne.
- **`renderer_utf8_need`** `ds4_agent.c:1981`  
  Lead byte invalidi o continuation isolati vengono trattati come caratteri da un byte.
- **`renderer_write`** `ds4_agent.c:1967`  
  Se capture è presente non pubblica nulla alla UI: le due destinazioni sono mutuamente esclusive.
- **`renderer_write_char`** `ds4_agent.c:2951`  
  Durante thinking o con Markdown spento scarica prima i delimitatori come letterali.
- **`renderer_write_char_raw`** `ds4_agent.c:2035`  
  Una continuation invalida scarica prima la sequenza parziale; non valida overlong o code point.
- **`renderer_write_complete_char_raw`** `ds4_agent.c:2015`  
  last_output_newline diventa true solo per un singolo byte newline, non per buffer più lunghi.
- **`renderer_write_plain_byte`** `ds4_agent.c:2057`  
  Disabilita gli attributi solo temporaneamente e poi ripristina i flag, non il colore emesso.
- **`repeat_hc_kernel`** `rocm/ds4_rocm_common.cuh:316`  
  Ogni copia e' identica: non applica pesi o trasformazioni hyper-connection.
- **`repeat_hc_rows_kernel`** `rocm/ds4_rocm_common.cuh:323`  
  L'ordine di uscita e' token, hyper-connection, embedding.
- **`repl_chat_apply_think_prefix`** `ds4_cli.c:1379`  
  Un cambio modalità invalida la sessione, anche se varia solo il prefisso.
- **`repl_chat_assistant_turn_uses_eos`** `ds4_cli.c:1438`  
  GLM-DSA non aggiunge EOS al transcript; gli altri modelli sì.
- **`repl_chat_build_think_prefix`** `ds4_cli.c:1365`  
  GLM-DSA usa un messaggio system; gli altri modelli aggiungono solo il prefisso Max.
- **`repl_chat_create_session`** `ds4_cli.c:1401`  
  Libera la vecchia sessione solo dopo aver creato con successo la nuova.
- **`repl_chat_free`** `ds4_cli.c:1424`  
  Azzera anche contesto e metadati dopo la liberazione.
- **`repl_chat_init`** `ds4_cli.c:1413`  
  Il prefisso think entra subito dopo il BOS, prima del messaggio system.
- **`repl_chat_set_ctx`** `ds4_cli.c:1431`  
  Libera la sessione corrente prima di sapere se la nuova creazione riuscirà.
- **`repl_glm_reasoning_effort_text`** `ds4_cli.c:1356`  
  DS4_THINK_NONE e qualunque valore non gestito restituiscono NULL.
- **`report_status_name`** `ds4_eval.c:4129`  
  Stati sconosciuti e PENDING vengono entrambi riportati come PENDING.
- **`request_begin`** `src/cuda/prefill_observer.cu:385`  
  Può contare due volte: è chiamata sia dal boundary CUDA sia dal reset hotness.
- **`request_ctx_span`** `ds4_server.c:10201`  
  Se cached supera prompt, forza la lunghezza del suffisso a zero.
- **`request_exceeds_context`** `ds4_server.c:5588`  
  Anche l'uguaglianza al limite viene rifiutata per lasciare uno slot
- **`request_free`** `ds4_server.c:1016`  
  Dopo la chiamata spariscono anche gli ID e i suffissi dello stato tool live
- **`request_init`** `ds4_server.c:1002`  
  Il ragionamento parte da HIGH e il modello da deepseek-v4-flash
- **`request_uses_openai_live_stream`** `ds4_server.c:6720`  
  Esclude completions e ogni richiesta non chat
- **`request_uses_responses_live_stream`** `ds4_server.c:6724`  
  Richiede REQ_CHAT anche per l'API Responses
- **`request_uses_structured_stream`** `ds4_server.c:6728`  
  Anthropic e Responses non richiedono REQ_CHAT, a differenza di OpenAI.
- **`requested_bytes_from_env`** `src/cuda/dynamic_arena.cu:260`  
  Assenza, stringa vuota e 0 sono disabilitazioni valide; gli altri errori rendono valid=false
- **`requested_u32`** `src/cuda/prefill_observer.cu:79`  
  La stringa esatta 0 bypassa zero_allowed; 00 può invece risultare invalida.
- **`required_bool`** `ds4.c:4277`  
  Una chiave assente termina il processo invece di restituire un errore.
- **`required_f32`** `ds4.c:4268`  
  Una chiave assente termina il processo invece di restituire un errore.
- **`required_tensor`** `ds4.c:4286`  
  L'assenza del tensore termina l'intero processo.
- **`required_tensorf`** `ds4.c:4302`  
  Nome troppo lungo o tensore assente terminano il processo.
- **`required_u32`** `ds4.c:4250`  
  Una chiave assente chiama exit(1), senza propagare un errore al chiamante
- **`required_u64_compat`** `ds4.c:4259`  
  Una chiave assente chiama exit(1), senza propagare un errore al chiamante
- **`responses_append_function_call_item`** `ds4_server.c:7083`  
  tool_search usa un oggetto arguments, mentre function_call usa una stringa JSON.
- **`responses_final_response`** `ds4_server.c:7469`  
  Ignora l'ID ricevuto e genera nuovi ID response, reasoning e message.
- **`responses_find_prior_call_msg`** `ds4_server.c:2979`  
  Limita before solo verso l'alto; un valore negativo produce semplicemente nessuna ricerca.
- **`responses_item_status_for_finish`** `ds4_server.c:6893`  
  Solo length ed error producono incomplete; ogni altro valore diventa completed.
- **`responses_live_clear`** `ds4_server.c:8819`  
  Con server o slot nullo non fa nulla.
- **`responses_live_continuation_prompt`** `ds4_server.c:9736`  
  Ogni mismatch restituisce zero ed è indistinguibile da una normale cache miss.
- **`responses_live_has_call_id`** `ds4_server.c:8833`  
  La ricerca è globale fra slot, non limitata alla richiesta corrente.
- **`responses_live_matches_request`** `ds4_server.c:8857`  
  L'ordine degli ID non conta, ma i duplicati nella richiesta fanno fallire il conteggio.
- **`responses_live_remember`** `ds4_server.c:8788`  
  Marca lo stato valido anche quando non riceve chiamate strumento.
- **`responses_live_visible_prefix_prompt`** `ds4_server.c:9799`  
  Richiede un suffisso non vuoto: un transcript esattamente uguale non basta.
- **`responses_namespace_function_schema_from_tool`** `ds4_server.c:1548`  
  Namespace e nome sono concatenati senza separatore.
- **`responses_prepare_live_continuation`** `ds4_server.c:3052`  
  Considera solo output tool finali; con un anchor non-assistant abbandona la preparazione.
- **`responses_random_id`** `ds4_server.c:6737`  
  Il fallback è prevedibile e usa un contatore statico non sincronizzato.
- **`responses_special_schema_from_tool`** `ds4_server.c:1481`  
  Descrizione e parametri mancanti ricevono default; altri tipi producono NULL.
- **`responses_sse_completed`** `ds4_server.c:7213`  
  Reasoning senza tag di chiusura resta incomplete anche se la risposta è completed.
- **`responses_sse_created`** `ds4_server.c:6840`  
  L'output iniziale è sempre vuoto.
- **`responses_sse_emit_event`** `ds4_server.c:6807`  
  Se body non inizia con type nel formato atteso, invia senza sequence_number.
- **`responses_sse_finish_live`** `ds4_server.c:7403`  
  Se recovered_content è non nullo, emette la coda di raw e non quel contenuto.
- **`responses_sse_function_call_arguments_done`** `ds4_server.c:7151`  
  Salta del tutto custom_tool_call e tool_search; il delta contiene tutti gli argomenti insieme.
- **`responses_sse_function_call_event`** `ds4_server.c:7124`  
  L'evento added contiene argomenti vuoti per evitare il doppio accumulo client.
- **`responses_sse_message_added`** `ds4_server.c:6958`  
  Il content iniziale è sempre vuoto.
- **`responses_sse_message_done`** `ds4_server.c:6997`  
  Anche finish error produce stato item incomplete, non failed.
- **`responses_sse_message_text_part_added`** `ds4_server.c:6970`  
  Usa sempre content_index 0 e annotations vuote.
- **`responses_sse_output_text_delta`** `ds4_server.c:6982`  
  Con len zero non emette alcun evento ma restituisce successo.
- **`responses_sse_reasoning_added`** `ds4_server.c:6854`  
  Non apre ancora la parte summary_text.
- **`responses_sse_reasoning_delta`** `ds4_server.c:6878`  
  Con len zero non emette alcun evento ma restituisce successo.
- **`responses_sse_reasoning_done`** `ds4_server.c:6898`  
  Ignora finish: senza chiusura naturale del tag, marca sempre incomplete.
- **`responses_sse_reasoning_summary_part_added`** `ds4_server.c:6866`  
  Usa sempre summary_index 0.
- **`responses_sse_stream_update`** `ds4_server.c:7293`  
  Il reasoning viene consumato ma non emesso se reasoning.summary non è richiesto.
- **`responses_status_for_finish`** `ds4_server.c:7193`  
  Solo error diventa failed e solo length incomplete; tutto il resto completed.
- **`responses_stream_free`** `ds4_server.c:6797`  
  Non azzera il resto dello stato.
- **`responses_stream_init`** `ds4_server.c:6787`  
  La modalità parte in reasoning anche senza tag iniziale se il think mode è attivo.
- **`responses_tool_call_is_tool_search`** `ds4_server.c:7051`  
  Un ordine schema può disattivare il trattamento speciale pur mantenendo quel nome.
- **`responses_tool_items_build`** `ds4_server.c:7063`  
  Forza is_custom a false e tronca silenziosamente call_id oltre il buffer fisso.
- **`responses_validate_tool_outputs`** `ds4_server.c:3005`  
  Messaggi tool senza alcun ID passano senza validazione.
- **`restore_env`** `src/cuda/prefill_observer.cu:369`  
  Ignora completamente un eventuale errore di ripristino.
- **`rms_abs_diff`** `ds4.c:15172`  
  Con n zero restituisce 0, mascherando un confronto vuoto.
- **`rms_norm_no_weight`** `ds4.c:7023`  
  Con n uguale a zero divide per zero.
- **`rms_norm_plain_batch8_kernel`** `ds4_cuda.cu:8931`  
  Gli otto carichi sono incondizionati; una coda parziale accede fuori dai limiti.
- **`rms_norm_plain_fast4096_kernel`** `ds4_cuda.cu:8903`  
  Ignora la generalità del parametro n e legge sempre sedici valori per thread.
- **`rms_norm_plain_kernel`** `rocm/ds4_rocm_norm_rope.cuh:1`  
  La riduzione condivisa è corretta solo con la geometria di lancio prevista.
- **`rms_norm_weight`** `ds4.c:7032`  
  Accumula i quadrati in double ma calcola scala e uscita in float.
- **`rocm_graph_batch_selected_async_load_ensure_worker`** `ds4.c:21601`  
  La creazione fallita viene ritentata da una chiamata successiva.
- **`rocm_graph_batch_selected_async_load_finish`** `ds4.c:21672`  
  Attende senza timeout e azzera il job anche quando il caricamento fallisce.
- **`rocm_graph_batch_selected_async_load_run`** `ds4.c:21525`  
  Un solo ID fuori intervallo fa fallire tutto il caricamento del batch.
- **`rocm_graph_batch_selected_async_load_start`** `ds4.c:21626`  
  Se il worker è occupato libera il buffer e fallisce, senza accodare il job.
- **`rocm_graph_batch_selected_async_load_sync_init`** `ds4.c:21517`  
  Qualunque errore di sincronizzazione termina il processo.
- **`rocm_graph_batch_selected_async_load_worker_main`** `ds4.c:21577`  
  Non esiste arresto del thread né coda per più job.
- **`rocm_graph_glm_stream_layer_expert_load_ready`** `ds4.c:38705`  
  Se manca un job attivo passa silenziosamente al caricamento sincrono.
- **`rocm_graph_glm_stream_layer_expert_load_start_next`** `ds4.c:38670`  
  Argomenti mancanti o intervallo invertito restituiscono successo senza caricare.
- **`rocm_graph_glm_stream_prefill_full_layer_enabled`** `ds4.c:38745`  
  Il solo superamento della soglia token non basta senza supporto resident decode.
- **`rocm_graph_stream_layer_expert_load_join`** `ds4.c:18269`  
  Un job nullo o inattivo è considerato già completato con successo.
- **`rocm_graph_stream_layer_expert_load_ready`** `ds4.c:18341`  
  Se non trova un job attivo, effettua il caricamento sincrono.
- **`rocm_graph_stream_layer_expert_load_start`** `ds4.c:18278`  
  Se la creazione del thread fallisce, azzera il job e restituisce falso.
- **`rocm_graph_stream_layer_expert_load_start_next`** `ds4.c:18309`  
  Se il percorso non è applicabile restituisce vero senza avviare alcun worker.
- **`rocm_graph_stream_layer_expert_load_sync`** `ds4.c:18241`  
  Non espone quanti esperti sono stati caricati, solo successo o fallimento.
- **`rocm_graph_stream_layer_expert_load_thread_main`** `ds4.c:18258`  
  Restituisce sempre NULL; l'errore resta soltanto in job->ok.
- **`rocm_graph_stream_prefill_full_layer_enabled`** `ds4.c:18206`  
  Richiede almeno 1024 token e quality disattivo.
- **`rocm_graph_stream_prefill_full_layer_seed_tokens`** `ds4.c:18219`  
  Restituisce almeno 1 anche con budget zero e tronca sempre il risultato a 8.
- **`rocm_graph_stream_seed_full_layer_selected`** `ds4.c:18380`  
  Il seed fallito emette un solo warning globale e la funzione restituisce comunque vero.
- **`rol32`** `ds4_kvstore.c:340`  
  Con n pari a 0 o 32 esegue uno shift indefinito
- **`role_is_system`** `ds4_server.c:2632`  
  Considera developer equivalente a system.
- **`role_is_user_like`** `ds4_server.c:2636`  
  Considera tool e function ruoli user-like.
- **`rope_tail_batch_worker`** `ds4.c:10605`  
  È un callback indiretto: il grafo statico lo mostra senza chiamanti.
- **`rope_tail_decode_rows_kernel`** `ds4_cuda.cu:9288`  
  Le posizioni arrivano dalla tabella e non devono essere contigue.
- **`rope_tail_ext_inplace`** `ds4.c:10497`  
  inverse cambia il segno del seno ma non annulla lo scaling di ampiezza.
- **`rope_tail_kernel`** `rocm/ds4_rocm_norm_rope.cuh:251`  
  La posizione avanza di pos_stride, che nel compressore vale il rapporto di compressione.
- **`rope_tail_layer_batch_inplace`** `ds4.c:10618`  
  Usa granularità minima di una riga, anche per batch piccoli.
- **`rope_tail_layer_inplace`** `ds4.c:10561`  
  Compensa lo scaling di ampiezza interno di YaRN per aderire al riferimento.
- **`rope_tail_one_dev`** `rocm/ds4_rocm_norm_rope.cuh:385`  
  È marcata unused e non ha chiamanti nel runtime.
- **`rope_yarn_corr_dim`** `ds4.c:10483`  
  Restituisce una coordinata non limitata; il chiamante la arrotonda e la satura.
- **`rope_yarn_corr_dims`** `ds4.c:10487`  
  Arrotonda l'inizio in basso e la fine in alto prima di limitarli.
- **`rope_yarn_ramp`** `ds4.c:10478`  
  i0/2 usa divisione intera, quindi due dimensioni consecutive condividono il valore.
- **`rope_yarn_ramp_cpu_equiv_dev`** `rocm/ds4_rocm_norm_rope.cuh:380`  
  Il suo unico chiamante è marcato unused e non è invocato.
- **`rope_yarn_ramp_dev`** `rocm/ds4_rocm_norm_rope.cuh:246`  
  Usa divisione intera i0/2, quindi coppie adiacenti condividono la rampa.
- **`route_transaction_ready`** `src/cuda/vram_expert_cache.cpp:322`  
  Restituisce sempre true: non verifica alcuno stato runtime del worker.
- **`routed_expert_block_bytes`** `ds4.c:4468`  
  Un tipo ignoto termina il processo; Q1_0 è incluso nella whitelist locale.
- **`routed_expert_row_bytes`** `ds4.c:4483`  
  Tipo non supportato o riga disallineata terminano il processo.
- **`routed_moe_align256_checked`** `rocm/ds4_rocm_moe_launch.cuh:7`  
  Restituisce 0 senza scrivere se l'arrotondamento eccede uint64.
- **`routed_moe_build_plan`** `rocm/ds4_rocm_moe_launch.cuh:450`  
  Accetta solo quattro coppie esatte di tipi e fallisce senza log per tutte le altre.
- **`routed_moe_decode_graph_destroy_one`** `ds4_cuda.cu:23739`  
  Ignora gli errori di destroy e azzera comunque gli handle in cache
- **`routed_moe_decode_profile_add_event_ms`** `rocm/ds4_rocm_moe_launch.cuh:120`  
  Sincronizza la GPU sull'evento finale per ogni intervallo raccolto.
- **`routed_moe_decode_profile_collect`** `rocm/ds4_rocm_moe_launch.cuh:145`  
  Un record nullo restituisce successo senza aggiornare le statistiche.
- **`routed_moe_decode_profile_enabled`** `rocm/ds4_rocm_moe_launch.cuh:80`  
  Il flag ambiente è letto una sola volta; ogni valore non vuoto diverso da 0 abilita.
- **`routed_moe_decode_profile_ensure_events`** `rocm/ds4_rocm_moe_launch.cuh:93`  
  Gli eventi creati con successo non vengono mai distrutti.
- **`routed_moe_decode_profile_print`** `rocm/ds4_rocm_moe_launch.cuh:54`  
  Non stampa nulla se calls è zero.
- **`routed_moe_decode_profile_record_event`** `rocm/ds4_rocm_moe_launch.cuh:112`  
  Indice errato o eventi non pronti restituiscono 0 senza diagnostica.
- **`routed_moe_decode_q4_graph_launch`** `ds4_cuda.cu:23747`  
  Usa sempre lo stream CUDA 0; ogni errore distrugge l'intera cache del tier
- **`routed_moe_full_table_is_cached`** `rocm/ds4_rocm_moe_launch.cuh:508`  
  Un solo range non cached rende falso l'intero risultato.
- **`routed_moe_launch`** `rocm/ds4_rocm_moe_launch.cuh:520`  
  Le variabili DS4_CUDA_MOE_* sono flag di presenza: anche il valore "0" le attiva
- **`routed_moe_q2_float_down_launch`** `rocm/ds4_rocm_moe_launch.cuh:196`  
  Copia sempre i conteggi GPU-CPU, sincronizzando anche quando WMMA è disattivo.
- **`routed_moe_tokens_worker`** `ds4.c:12102`  
  È un callback indiretto e alloca scratch una volta per intervallo, non per token.
- **`routed_moe_u64_add_checked`** `rocm/ds4_rocm_moe_launch.cuh:1`  
  Restituisce 0 senza scrivere in caso di overflow o puntatore nullo.
- **`router_score_better`** `rocm/ds4_rocm_router.cuh:7`  
  A parità di score vince l'indice minore.
- **`router_select_kernel`** `ds4_cuda.cu:13424`  
  hash_mode salta il top-6: prende gli indici dalla hash ma i pesi dai logit.
- **`router_select_parallel_kernel`** `ds4_cuda.cu:13476`  
  Dopo le probabilità, solo il thread 0 esegue la selezione seriale.
- **`router_select_warp_topk_kernel`** `rocm/ds4_rocm_router.cuh:11`  
  hash_mode ignora il bias e rimappa token fuori intervallo sulla riga 0.
- **`run_agent`** `ds4_agent.c:10715`  
  Dopo aver rifiutato il save, /quit può chiamare exit(0) e saltare tutto il cleanup.
- **`run_agent_non_interactive`** `ds4_agent.c:10561`  
  Senza -p raggruppa input per 200 ms di quiete, non per righe; con -p ignora stdin.
- **`run_chat_turn`** `ds4_cli.c:1446`  
  Ctrl+C prima del primo token annulla il turno; dopo almeno uno conserva il parziale.
- **`run_clock_sec`** `ds4_eval.c:1439`  
  Il clock usato cambia per piattaforma e può escludere il sonno del sistema.
- **`run_copy_workers`** `src/cuda/dynamic_arena.cu:857`  
  Se creare un thread fallisce completa il lavoro residuo ma restituisce false
- **`run_decode_consistency`** `ds4_cli.c:957`  
  Il successo dipende solo dal top-1, non da max_abs o RMS.
- **`run_extractor_self_tests`** `ds4_eval.c:3483`  
  Gira solo con l'opzione self-test e termina al termine della suite.
- **`run_fixture`** `src/cuda/prefill_observer.cu:582`  
  Azzera l'arena globale all'inizio e alla fine, distruggendo eventuale stato vivo.
- **`run_generation`** `ds4_cli.c:1193`  
  DS4_CLI_FORCE_SESSION forza la sessione solo nella generazione non diagnostica.
- **`run_logits_dump`** `ds4_cli.c:762`  
  I logits non finiti diventano null; il file può essere enorme quanto il vocabolario.
- **`run_logprob_dump`** `ds4_cli.c:850`  
  top-k usa 20 se non positivo ed è troncato silenziosamente a 128.
- **`run_one_case`** `ds4_eval.c:3688`  
  Vicino al limite può forzare </think> al posto del token campionato.
- **`run_perplexity_file`** `ds4_cli.c:1110`  
  I primi 32 token non sono valutati; --tokens limita solo i successivi.
- **`run_repl`** `ds4_cli.c:1608`  
  Ogni /ctx distrugge il KV ma mantiene il transcript, ricalcolato al turno seguente.
- **`run_sampled_generation`** `ds4_cli.c:545`  
  greedy_argmax non ha effetto: have_greedy_next non viene mai impostato.
- **`runtime_config`** `src/cuda/vram_expert_cache.cpp:265`  
  Ignora runtime.valid: un mode non-off invalido usa comunque i campi tiering.
- **`runtime_configuration_snapshot`** `src/cuda/vram_expert_cache.cpp:318`  
  La copia riflette variabili ambiente lette una sola volta dal singleton.
- **`runtime_counters_snapshot`** `src/cuda/vram_expert_cache.cpp:1000`  
  I load relaxed separati non formano uno snapshot coerente tra campi.
- **`runtime_help`** `ds4_agent.c:10290`  
  Il testo è statico e non riflette dinamicamente feature disabilitate o backend.
- **`runtime_note_capacity_full`** `src/cuda/vram_expert_cache.cpp:1058`  
  Può incrementare anche se subito dopo un rimpiazzo riesce.
- **`runtime_note_promotion_attempt`** `src/cuda/vram_expert_cache.cpp:1050`  
  I massimi non diminuiscono finché il report non li azzera.
- **`runtime_note_ram_hit`** `src/cuda/vram_expert_cache.cpp:1040`  
  Con tiering off non conta, anche se la cache legacy è attiva.
- **`runtime_note_ssd_load`** `src/cuda/vram_expert_cache.cpp:1045`  
  Con tiering off non conta, anche se la cache legacy è attiva.
- **`runtime_note_vram_hit`** `src/cuda/vram_expert_cache.cpp:1035`  
  Con tiering off non conta, anche se la cache legacy è attiva.
- **`runtime_report_and_reset`** `src/cuda/vram_expert_cache.cpp:1064`  
  Con tiering off o invalido non stampa e non azzera nulla.
- **`runtime_telemetry_enabled`** `src/cuda/vram_expert_cache.cpp:281`  
  La cache legacy attiva da sola non abilita la telemetria.
- **`sample_argmax`** `ds4.c:37043`  
  Con tutti NaN o -inf restituisce l'indice 0.
- **`sample_candidate_cmp_desc`** `ds4.c:37097`  
  E usata da qsort via puntatore, quindi il grafo la segna senza chiamanti.
- **`sample_candidate_gt`** `ds4.c:37106`  
  A parita di logit vince l'ID numericamente minore.
- **`sample_fast_top_p`** `ds4.c:37141`  
  Restituisce false se 512 candidati non garantiscono la massa top-p, imponendo il fallback.
- **`sample_full_vocab`** `ds4.c:37229`  
  Con top_p minore di uno tenta prima il percorso heap e poi ripiega sul sort completo.
- **`sample_heap_sift_down`** `ds4.c:37122`  
  La radice resta il peggiore dei candidati conservati.
- **`sample_heap_sift_up`** `ds4.c:37111`  
  Usa un predicato greater per mantenere in radice il candidato peggiore.
- **`sample_rng_f32`** `ds4.c:37086`  
  La casualita ha soltanto 24 bit di risoluzione.
- **`sample_rng_next`** `ds4.c:37076`  
  Uno stato zero viene sostituito con una costante non nulla.
- **`sample_top_p_min_p`** `ds4.c:37392`  
  Top-p invalido diventa 1 e top-k viene silenziosamente limitato a 1024.
- **`save_env`** `src/cuda/prefill_observer.cu:364`  
  Copia il valore ma conserva il puntatore originale al nome.
- **`scalar_value_size`** `ds4.c:2154`  
  Restituisce zero sia per tipi composti sia per tipi sconosciuti.
- **`scale_f32`** `ds4.c:10674`  
  La variante NEON gira solo su ARM; altrove usa il ciclo scalare.
- **`scan_first_integer`** `ds4_eval.c:2881`  
  Ignora il segno: -12 viene estratto come 12.
- **`seed_ranked`** `src/cuda/dynamic_arena.cu:1245`  
  Arena disabilitata o lista vuota restituiscono successo senza seminare.
- **`seed_request_ranked`** `src/cuda/dynamic_arena.cu:1288`  
  Con n_experts zero ritorna successo ma conserva ranking e snapshot precedenti.
- **`seed_selected`** `src/cuda/dynamic_arena.cu:1267`  
  Ogni ID ripetuto aumenta ancora il peso; lista vuota o arena spenta danno successo.
- **`select_ranking_locked`** `src/cuda/prefill_observer.cu:290`  
  La quota fallisce se anche un solo layer ha meno candidati del richiesto.
- **`send_all`** `ds4_server.c:4695`  
  Ogni progresso resetta la scadenza, quindi la durata totale può superare il timeout di stallo.
- **`send_model`** `ds4_server.c:12602`  
  Restituisce false solo dal trasporto, senza loggare localmente.
- **`send_models`** `ds4_server.c:12611`  
  Pubblicizza alias fissi scelti solo dalla famiglia GLM o non GLM.
- **`send_prefill_failure_response`** `ds4_server.c:10728`  
  Se lo stream è già fallito registra soltanto un log e non invia risposta.
- **`server_chdir`** `ds4_server.c:241`  
  Su Windows ogni errore salvo la conversione viene esposto come EACCES
- **`server_close_resources`** `ds4_server.c:12910`  
  Azzera l'intera struttura dopo aver distrutto le risorse.
- **`server_cond_timedwait_us`** `ds4_server.c:11088`  
  Su Windows arrotonda al millisecondo superiore e impone almeno 1 ms.
- **`server_decode_coalesce_us`** `ds4_server.c:11077`  
  Zero disattiva l'attesa; valori non validi ricadono muti su 2000 microsecondi.
- **`server_eval_token`** `ds4_server.c:11041`  
  In batched la chiamata resta sincrona e attende il completamento del batch.
- **`server_exchange_listener`** `ds4_server.c:94`  
  La chiamata trasferisce al chiamante la chiusura del vecchio socket
- **`server_fseek`** `ds4_server.c:256`  
  Restituisce direttamente il codice della libreria senza normalizzarlo
- **`server_generation_enter`** `ds4_server.c:11025`  
  In modalità non batched non modifica alcun contatore.
- **`server_generation_leave`** `ds4_server.c:11033`  
  Se il contatore è già zero non segnala lo sbilanciamento.
- **`server_log`** `ds4_server.c:8365`  
  Se la misura vsnprintf fallisce, stampa il formato letterale ignorando gli argomenti.
- **`server_log_mutex_init`** `ds4_server.c:8361`  
  Non ha chiamanti diretti: è un callback di inizializzazione pigra.
- **`server_model_alias_known`** `ds4_server.c:1171`  
  Gli alias deepseek-chat e deepseek-reasoner non sono inclusi
- **`server_model_id_from_engine`** `ds4_server.c:1165`  
  Per DeepSeek ogni model_id diverso da uno viene presentato come flash
- **`server_model_syntax_for_engine`** `ds4_server.c:1160`  
  Ogni engine non GLM usa la sintassi DeepSeek
- **`server_next_prefill_slot_locked`** `ds4_server.c:10459`  
  La ricerca parte dallo slot successivo all'ultimo servito.
- **`server_next_sequence`** `ds4_server.c:11189`  
  La sequenza parte da uno e può traboccare senza controllo.
- **`server_prefill_enter`** `ds4_server.c:10468`  
  In modalità batched attende anche che non resti alcun decode pendente.
- **`server_prefill_leave`** `ds4_server.c:10496`  
  In modalità non batched non aggiorna model_busy.
- **`server_prefill_quantum`** `ds4_server.c:10521`  
  Il solo contatore active_generations cambia il valore predefinito.
- **`server_prefill_quantum_for`** `ds4_server.c:10506`  
  Valori d'ambiente non validi ricadono muti su 128 o 2048 token.
- **`server_progress_cb`** `ds4_server.c:10648`  
  A progresso ripetuto può salvare KV ma non emette un nuovo log.
- **`server_recursive_mutex_init`** `ds4_server.c:310`  
  Restituisce sempre zero anche se InitializeCriticalSection puo sollevare un'eccezione
- **`server_request_decode_stop`** `ds4_server.c:13188`  
  In modalità non batched ritorna senza impostare model_stopping.
- **`server_request_stop`** `ds4_server.c:112`  
  Chiamate ripetute trovano la sentinella e non richiudono il socket
- **`server_request_worker_stop`** `ds4_server.c:13180`  
  Chiama ancora il dispatch: i job già accodati vengono drenati, non annullati.
- **`server_session_sync`** `ds4_server.c:10532`  
  In batched può ricostruire da zero se il prefix comune non coincide col frontier live.
- **`server_unlink`** `ds4_server.c:264`  
  Su Windows gli errori diversi da file assente diventano tutti EACCES
- **`server_winsock_cleanup`** `ds4_server.c:184`  
  Ignora il risultato di WSACleanup
- **`session_cpu_comp_cap`** `ds4.c:48933`  
  Preferisce il primo layer ratio 4, non un minimo o massimo globale.
- **`session_cpu_payload_live_tensor_bytes`** `ds4.c:48946`  
  Misura righe vive, non le capacità allocate.
- **`session_cpu_raw_live_rows`** `ds4.c:48926`  
  Un checkpoint non valido produce zero anche se la cache contiene dati.
- **`session_cpu_reset_cache`** `ds4.c:48966`  
  Libera tutto lo stato precedente prima di riallocare la cache.
- **`session_glm_compact_live_rows`** `ds4.c:48580`  
  Assume vive tutte le righe fino a min(capacità, checkpoint).
- **`session_glm_full_live_rows`** `ds4.c:48569`  
  Senza full_kv_cache restituisce zero anche con un checkpoint valido.
- **`session_glm_payload_live_tensor_bytes`** `ds4.c:48587`  
  Conta f32 su disco anche quando la cache residente è f16.
- **`session_greedy_splitkv_reset`** `ds4.c:49894`  
  Con sessione NULL ritorna in silenzio.
- **`session_payload_live_tensor_bytes`** `ds4.c:48550`  
  Misura righe vive, non le capacità allocate.
- **`session_raw_live_rows`** `ds4.c:48539`  
  raw_window zero usa DS4_N_SWA, non significa zero righe.
- **`set_client_socket_nonblocking`** `ds4_server.c:12814`  
  Ignora il fallimento; i client lenti vengono poi trattati come errori di stream.
- **`set_env_value`** `src/cuda/prefill_observer.cu:350`  
  Su Windows la rimozione passa una stringa vuota a _putenv_s.
- **`set_nonblock`** `ds4_agent.c:9052`  
  Salva i flag originali prima del F_SETFL, anche se quest'ultimo poi fallisce.
- **`sha1_bytes_hex`** `ds4_server.c:9109`  
  Non esiste nella build di produzione.
- **`sha1_final`** `ds4_kvstore.c:413`  
  Finalizzare modifica irreversibilmente il contesto
- **`sha1_transform`** `ds4_kvstore.c:344`  
  Usa SHA-1 solo come identificatore, non come garanzia crittografica
- **`sha1_update`** `ds4_kvstore.c:396`  
  Il contatore dei byte puo' traboccare per input estremi
- **`shared_gate_up_swiglu_q8_0_batch_sharedx_w32_kernel`** `rocm/ds4_rocm_q8.cuh:523`  
  Con store_gate_up a zero gate e up restano invariati, mentre mid viene scritto
- **`shared_gate_up_swiglu_q8_0_pair_preq_warp8_kernel`** `rocm/ds4_rocm_q8.cuh:250`  
  Con store_gate_up a zero lascia gate e up intatti ma scrive comunque mid
- **`shared_gate_up_swiglu_q8_0_rows_w32_kernel`** `rocm/ds4_rocm_q8.cuh:948`  
  clamp limita gate solo superiormente, mentre limita up in entrambe le direzioni
- **`shared_mid_q8_0_preq_warp8_exact_kernel`** `ds4_cuda.cu:7820`  
  In parita' tra esperti home e peer scrive il rank home; l'altro termina senza scrivere.
- **`short_phase_name`** `ds4_eval.c:2307`  
  Qualsiasi fase sconosciuta viene mostrata come RUN.
- **`shouldFoldHistoryText`** `linenoise.c:1102`  
  Le soglie combinano byte e numero di newline, non colonne visuali.
- **`shouldFoldText`** `linenoise.c:1095`  
  La soglia di 200 è in byte, non in caratteri.
- **`should_canonicalize_tool_checkpoint`** `ds4_server.c:11015`  
  Con replay esatto attivo, il solo raw_tool_text non vuoto disattiva la canonicalizzazione.
- **`should_remember_thinking_checkpoint`** `ds4_server.c:10611`  
  Accetta anche finish nullo; rifiuta solo error e length espliciti.
- **`sigmoid_stable`** `ds4.c:10688`  
  Usa formule diverse sopra e sotto zero per evitare overflow esponenziale.
- **`silu`** `ds4.c:10815`  
  Eredita il ramo stabile della sigmoide.
- **`skip_ascii_ws`** `ds4_server.c:4839`  
  Il nome dice ASCII ma usa isspace dipendente dalla locale
- **`skip_value`** `ds4.c:2176`  
  Il controllo depth > 8 consente il livello 8 e fallisce solo entrando nel 9.
- **`sleep_sec`** `ds4.c:1695`  
  Su POSIX un segnale interrompe il sonno e il tempo residuo non viene recuperato.
- **`slot_capacity`** `src/cuda/dynamic_arena.cu:279`  
  Il risultato satura a UINT32_MAX
- **`slot_reader_acquire`** `src/cuda/dynamic_arena.cu:186`  
  Non attende: writer presente o contatore saturo causano subito false
- **`slot_reader_release`** `src/cuda/dynamic_arena.cu:211`  
  Un rilascio sbilanciato manda il contatore in underflow
- **`slot_refs_load`** `src/cuda/dynamic_arena.cu:176`  
  Su Windows una CAS 0 su 0 simula la sola lettura
- **`slot_worker_main`** `ds4_server.c:12434`  
  Marca lo slot libero solo dopo aver svegliato il client del job concluso.
- **`slot_writer_release`** `src/cuda/dynamic_arena.cu:233`  
  Azzera l'intero contatore invece di rimuovere un singolo bit
- **`slot_writer_try_acquire`** `src/cuda/dynamic_arena.cu:220`  
  Non attende la fine dei reader: fallisce immediatamente
- **`socket_error_text`** `ds4_server.c:279`  
  Su Windows produce solo il numero, non il testo di sistema
- **`softplus_dev`** `rocm/ds4_rocm_router.cuh:1`  
  Per x minore di -20 approssima softplus con exp(x).
- **`softplus_stable`** `ds4.c:10819`  
  Sopra 20 restituisce x; sotto -20 restituisce exp(x).
- **`spec_frontier_commit_prefix1`** `ds4.c:49867`  
  La seconda riga speculativa resta come spazzatura invisibile nelle cache append-only.
- **`spec_frontier_free`** `ds4.c:49779`  
  Non libera memoria: esegue soltanto memset della struttura.
- **`spec_frontier_restore`** `ds4.c:49821`  
  Aggiorna contatori CPU prima che tutte le copie GPU riescano; un errore lascia stato parziale.
- **`spec_frontier_snapshot`** `ds4.c:49784`  
  Non copia le cache dati, ma solo contatori e stati di compressore e indexer.
- **`special_token_at`** `ds4.c:36702`  
  Il confronto è per prefisso e non richiede confini lessicali
- **`split_reasoning_content`** `ds4_server.c:4993`  
  Un </think> senza apertura divide comunque il testo
- **`sse_chat_delta_n`** `ds4_server.c:5887`  
  Con len zero restituisce successo senza inviare un evento
- **`sse_chat_finish`** `ds4_server.c:5745`  
  Invia sempre un chunk iniziale di ruolo anche se la risposta è vuota
- **`sse_chat_tool_call_args_delta_n`** `ds4_server.c:5928`  
  Con len zero restituisce successo senza inviare un evento
- **`sse_chat_tool_call_start_delta`** `ds4_server.c:5909`  
  Dichiara arguments come stringa vuota già nel delta iniziale
- **`sse_chunk`** `ds4_server.c:5662`  
  Nella chat, text e finish NULL emettono il ruolo assistant
- **`sse_done`** `ds4_server.c:5739`  
  Se il chunk usage fallisce non invia il marcatore DONE
- **`sse_error_event`** `ds4_server.c:5645`  
  Qualunque API non Anthropic usa la stessa forma generica
- **`sse_event`** `ds4_server.c:7675`  
  Non esegue escaping di event o data prima di inserirli nel framing SSE.
- **`sse_headers`** `ds4_server.c:5632`  
  Dichiara Connection: close anche per uno stream SSE
- **`sse_usage_chunk`** `ds4_server.c:5716`  
  Se stream_include_usage è falso restituisce successo senza inviare nulla
- **`status_name`** `ds4_eval.c:1796`  
  Uno stato sconosciuto diventa semplicemente ?.
- **`stdout_is_tty`** `ds4_agent.c:9189`  
  Restituisce false anche per errori di isatty, senza distinguerli da una pipe.
- **`stop_console_handler`** `ds4_server.c:172`  
  Gli eventi non riconosciuti sono lasciati al gestore successivo
- **`stop_list_clear`** `ds4_server.c:1185`  
  Capacita e puntatore restano invariati mentre max_len torna a zero
- **`stop_list_find_from`** `ds4_server.c:1234`  
  A parità di posizione vince la prima stop configurata, non necessariamente la più lunga.
- **`stop_list_push`** `ds4_server.c:1191`  
  Una stringa NULL o vuota viene liberata e non inserita
- **`stop_list_stream_safe_len`** `ds4_server.c:1256`  
  Trattiene sempre max_len-1 byte, anche se la coda non può iniziare alcuna stop.
- **`stop_signal_handler`** `ds4_server.c:188`  
  Un secondo segnale termina con _exit(130), saltando ogni pulizia
- **`store_raw_kv_batch_kernel`** `rocm/ds4_rocm_fp8_kv.cuh:31`  
  Memorizza il valore arrotondato come float32 e sovrascrive le righe modulo raw_cap.
- **`strcasestr_local`** `ds4_eval.c:2734`  
  Restituisce un puntatore non const anche se l'input è const.
- **`stream_append_token_text`** `ds4_eval.c:2171`  
  Rimuove i tag e sostituisce ogni chiusura think con un newline.
- **`stream_append_visible`** `ds4_eval.c:2166`  
  Lo stile segue i byte, non i caratteri Unicode.
- **`streaming_layer_gate_down_expert_bytes`** `ds4.c:4533`  
  Azzera entrambi gli output anche quando poi fallisce.
- **`streaming_layer_routed_expert_bytes`** `ds4.c:4490`  
  Azzera sempre l'output prima dei controlli e restituisce false sugli overflow.
- **`streq`** `ds4_help.c:101`  
  Restituisce falso se una delle due stringhe è NULL
- **`streq_any`** `ds4_agent.c:3046`  
  Le alternative NULL vengono semplicemente ignorate.
- **`style_append`** `ds4_eval.c:1408`  
  Conta byte, non caratteri Unicode, e termina il processo su OOM.
- **`style_free`** `ds4_eval.c:1430`  
  Dopo free cancella anche lunghezza e capacità.
- **`sum_down_pairs_worker`** `ds4.c:9961`  
  È marcata MAYBE_UNUSED e non viene referenziata.
- **`support_kind_name`** `ds4.c:2847`  
  Valori enum sconosciuti diventano la stringa unknown
- **`support_model_detect`** `ds4.c:2856`  
  DSpark richiede almeno tre stadi; altrimenti può ricadere nel rilevamento legacy
- **`swiglu`** `ds4.c:10825`  
  Il clamp limita il gate solo superiormente, mentre up è limitato sui due segni.
- **`swiglu_batch_worker`** `ds4.c:10906`  
  È un callback indiretto: il grafo statico lo mostra senza chiamanti.
- **`swiglu_kernel`** `rocm/ds4_rocm_output.cuh:23`  
  Il clamp del gate è solo superiore; quello di up è simmetrico.
- **`table_free`** `ds4.c:35581`  
  Dopo free azzera anche capacità e contatore.
- **`table_get`** `ds4.c:35604`  
  Una tabella completamente piena senza la chiave causerebbe un ciclo infinito.
- **`table_init`** `ds4.c:35575`  
  La capacità minima è 16 ed è maggiore del doppio degli elementi attesi.
- **`table_put`** `ds4.c:35586`  
  Una chiave già presente sovrascrive il valore senza incrementare used.
- **`tensor_1d_value`** `ds4.c:8137`  
  Non richiede ndim uguale a 1: indicizza linearmente qualsiasi tensore supportato.
- **`tensor_2d_value`** `ds4.c:8151`  
  Usa layout row-major con indice y*dim[0]+x.
- **`tensor_by_mtp_stage_suffix`** `ds4.c:4309`  
  Il tensore può mancare e dare NULL, mentre un nome troppo lungo è fatale.
- **`tensor_by_namef`** `ds4.c:4295`  
  Un nome oltre 127 byte è fatale, ma un tensore assente restituisce NULL.
- **`tensor_data`** `ds4.c:3139`  
  Non esegue alcun controllo dei limiti
- **`tensor_expect_dense_quant_layout`** `ds4.c:4390`  
  Ogni errore di tipo o forma termina il processo.
- **`tensor_expect_f16_or_q8_0_layout`** `ds4.c:4440`  
  Ogni difformità termina il processo.
- **`tensor_expect_glm_dense_quant_layout`** `ds4.c:4372`  
  Riusa il tipo effettivo nel controllo finale; la whitelist è verificata prima.
- **`tensor_expect_layout`** `ds4.c:4319`  
  Ogni difformità termina il processo, non restituisce un esito.
- **`tensor_expect_optional`** `ds4.c:4408`  
  Un puntatore NULL è accettato senza alcuna segnalazione.
- **`tensor_expect_plain_layout`** `ds4.c:4418`  
  Accetta F32 oltre a F16, ma rifiuta ogni formato quantizzato.
- **`tensor_expect_routed_expert`** `ds4.c:4772`  
  Rifiuta Q1_0 anche se il calcolo dei byte per blocco sa gestirlo.
- **`tensor_expert_bytes`** `ds4.c:8159`  
  Deriva lo stride con blocchi arrotondati e presume esperti contigui senza padding extra.
- **`tensor_is_routed_expert_type`** `ds4.c:4458`  
  Q1_0 non è ammesso qui benché il calcolo dei byte di blocco lo supporti.
- **`tensor_nbytes`** `ds4.c:2227`  
  Arrotonda gli elementi a un blocco intero invece di richiedere divisibilità.
- **`tensor_to_entry`** `ds4.c:54767`  
  Nomi ignoti o layer con oltre quattro cifre finiscono silenziosamente nel bucket 0.
- **`tensor_type`** `ds4.c:2216`  
  Tipi GGUF senza voce nella tabella risultano non supportati.
- **`tensor_type_is_dense_quant`** `ds4.c:4366`  
  F16 e F32 non sono considerati densi validi da questo predicato.
- **`tensor_type_is_f16_or_q8_0`** `ds4.c:4436`  
  F32 viene rifiutato nonostante sia un tipo in virgola mobile semplice.
- **`tensor_type_is_glm_dense_quant`** `ds4.c:4360`  
  Accetta q4_0 oltre a q8_0 e q4_K.
- **`tensor_type_name`** `ds4.c:2222`  
  Un tipo non supportato diventa la stringa letterale unknown senza errore.
- **`term_clear_to_eol`** `ds4_eval.c:1765`  
  Su terminali senza ANSI stampa caratteri di controllo.
- **`term_move`** `ds4_eval.c:1761`  
  Emette soltanto la sequenza, senza flush.
- **`term_set_color_for_status`** `ds4_eval.c:1784`  
  Non ha default: uno stato sconosciuto conserva il colore precedente.
- **`terminal_size`** `ds4_eval.c:1735`  
  In caso di errore imposta 80x24; il chiamante ignora il codice negativo.
- **`test_agent_dsml_stream_tool_call_chunked`** `ds4_agent.c:6881`  
  Richiede che i tag DSML non appaiano nell'output renderizzato.
- **`test_agent_glm_stream_greedy_sampling_boundaries`** `ds4_agent.c:6834`  
  Nel corpo libero del valore parametro il greedy deve spegnersi.
- **`test_agent_glm_stream_ignores_tool_inside_think`** `ds4_agent.c:6811`  
  La chiamata ignorata diventa una nota visibile, non sparisce in silenzio.
- **`test_agent_glm_stream_tool_call_chunked`** `ds4_agent.c:6782`  
  Pretende che i tag strutturali spariscano ma il comando resti visibile.
- **`test_agent_glm_template_policy`** `ds4_agent.c:6938`  
  GLM non usa EOS nel turno assistente, DSML sì.
- **`test_agent_glm_tool_parser_streams_param_state`** `ds4_agent.c:6727`  
  Controlla anche un prefisso di chiusura spezzato tra chunk.
- **`test_agent_glm_tools_prompt_is_native`** `ds4_agent.c:6923`  
  Verifica esplicitamente l'assenza di DSML e del limite a una sola chiamata.
- **`test_anthropic_full_replay_allows_unknown_live_id`** `ds4_server.c:15919`  
  Un ID ignoto allo stato live è valido se la call è già nella cronologia.
- **`test_anthropic_live_stream_sends_incremental_blocks`** `ds4_server.c:13938`  
  I marcatori DSML grezzi sono soppressi dal wire.
- **`test_anthropic_live_tail_renders_tool_results_only`** `ds4_server.c:15839`  
  Un system finale viene ignorato cercando la coda e il nome Bash non viene ripetuto.
- **`test_anthropic_thinking_and_tool_args_preserve_call_order`** `ds4_server.c:15043`  
  I blocchi escono thinking, text, tool_use e non secondo il solo ordine della call.
- **`test_anthropic_tool_memory_replays_sampled_dsml`** `ds4_server.c:15785`  
  Il nome Bash mantiene anche la maiuscola del testo campionato.
- **`test_anthropic_tool_result_id_validation`** `ds4_server.c:15884`  
  Senza stato live fallisce; con lo stesso ID passa chiedendo il ripristino live.
- **`test_anthropic_tool_stream_sends_live_tool_use`** `ds4_server.c:13997`  
  L'ID toolu_ viene assegnato dallo stato stream, non dal parser DSML.
- **`test_anthropic_tool_use_parses_before_role`** `ds4_server.c:15950`  
  L'ordine dei campi JSON non deve far perdere gli ID storici.
- **`test_anthropic_usage_reports_cache_details`** `ds4_server.c:14082`  
  La risposta finale riporta input_tokens 0 nel caso costruito.
- **`test_api_thinking_controls_parse`** `ds4_server.c:14769`  
  budget_tokens non riabilita un oggetto con type disabled.
- **`test_assert`** `ds4_server.c:13470`  
  Accumula i fallimenti invece di abortire al primo.
- **`test_batched_live_continuation_slot_binding`** `ds4_server.c:13507`  
  Un binding richiesto ma invalidato deve risultare indistinguibile da assente.
- **`test_batched_prefill_round_robin`** `ds4_server.c:13486`  
  Non crea mutex: testa direttamente la helper locked in singolo thread.
- **`test_canonical_rewrite_rebuilds_when_live_tail_changes`** `ds4_server.c:16695`  
  Anche righe SWA ancora presenti non evitano il rebuild se le frontiere compresse sono avanzate
- **`test_client_socket_nonblocking_flag`** `ds4_server.c:16607`  
  Dopo un assert fallito sui socket la funzione esce senza eseguire le verifiche successive
- **`test_context_length_error_uses_protocol_standard_shape`** `ds4_server.c:13829`  
  Una richiesta con token uguali a n_ctx è già eccedente.
- **`test_cors_headers_are_opt_in`** `ds4_server.c:13874`  
  Con CORS attivo Allow-Headers vale *, non una lista restrittiva.
- **`test_cors_preflight_response_is_no_content`** `ds4_server.c:13903`  
  Content-Length: 0 è presente anche senza Content-Type.
- **`test_cors_sse_headers`** `ds4_server.c:13921`  
  La funzione emette subito uno status HTTP 200.
- **`test_dsml_decode_state_separates_structure_and_payload`** `ds4_server.c:16248`  
  Il solo prefisso </ riporta già lo stato da payload stringa a strutturale.
- **`test_dsml_parser_recovers_loose_nested_parameters`** `ds4_server.c:15134`  
  Un parametro edits annidato senza chiusura propria diventa un oggetto JSON.
- **`test_dsml_prompt_escapes_tool_supplied_text`** `ds4_server.c:16364`  
  Non escapa genericamente <, >, &; neutralizza solo chiusure che romperebbero il framing.
- **`test_dsml_repair_produces_parseable_calls`** `ds4_server.c:15167`  
  Non modifica input bilanciato né ripara chiusure orfane.
- **`test_dsml_tool_args_preserve_call_order`** `ds4_server.c:15007`  
  Lo schema non riordina description e command nel DSML.
- **`test_exact_dsml_tool_replay_can_be_disabled`** `ds4_server.c:16207`  
  kv_tool_map_write riesce ma dichiara zero byte scritti.
- **`test_glm_tool_checkpoint_suffix_is_canonical`** `ds4_server.c:15572`  
  Il suffisso GLM non aggiunge EOS DS4 e non usa DSML.
- **`test_invalid_dsml_tool_error_suffix_includes_system_prompt`** `ds4_server.c:15407`  
  Include il system ma omette il testo del turno user precedente.
- **`test_invalid_glm_tool_error_suffix`** `ds4_server.c:15429`  
  Il recupero GLM non contiene DSML né token EOS DS4.
- **`test_json_parser_handles_tool_heavy_requests`** `ds4_server.c:16539`  
  Rianalizza gli stessi due buffer 32 volte; non crea 32 richieste diverse.
- **`test_json_skip_has_nesting_limit`** `ds4_server.c:16447`  
  Il limite esatto passa, un solo livello aggiuntivo fallisce.
- **`test_json_string_handles_surrogates`** `ds4_server.c:16576`  
  Una high surrogate non valida diventa U+FFFD senza inghiottire il carattere seguente
- **`test_kv_cache_chat_anchor_ignores_multiturn_tail`** `ds4_server.c:16756`  
  ID ruolo mancanti o anchor sotto min_tokens producono -1 senza fallback
- **`test_kv_cache_chat_anchor_uses_last_user_before_assistant`** `ds4_server.c:16724`  
  Ignora i token user precedenti e sceglie l'ultimo prima del primo assistant
- **`test_kv_cache_cold_store_suppresses_duplicate_continued_boundary`** `ds4_server.c:16807`  
  La soppressione muta continued_last_store_tokens e va annullata esplicitamente
- **`test_kv_cache_continued_uses_aligned_frontiers`** `ds4_server.c:16783`  
  Sotto la prossima frontiera restituisce 0; con align zero usa la distanza minima predefinita
- **`test_kv_cache_eviction_decayed_hits_tie_break_by_age`** `ds4_server.c:17400`  
  Quindici hit molto vecchi non salvano il file dall'eviction
- **`test_kv_cache_eviction_ignores_oversize_incoming`** `ds4_server.c:17253`  
  Un arrivo impossibile da salvare viene ignorato e non fa spazio inutilmente
- **`test_kv_cache_eviction_keeps_aligned_continued_frontiers`** `ds4_server.c:17439`  
  Il continued da 2048 token sopravvive mentre il cold da 512 viene eliminato
- **`test_kv_cache_eviction_keeps_smaller_context_prefix`** `ds4_server.c:17332`  
  Un file creato per contesto 32768 resta riusabile da 65536 e viene protetto
- **`test_kv_cache_eviction_makes_room_before_store`** `ds4_server.c:17224`  
  Lo spazio extra viene conteggiato prima che il nuovo file esista
- **`test_kv_cache_eviction_prefers_anchor_reason`** `ds4_server.c:17188`  
  A parità di dimensione, token e tempo il reason cold sopravvive al continued
- **`test_kv_cache_eviction_prefers_superseded_continued_prefix`** `ds4_server.c:17282`  
  La relazione di prefisso fa eliminare il continued e conserva un cold non correlato
- **`test_kv_cache_eviction_score_decays_stale_hits`** `ds4_server.c:17382`  
  Hit vecchi decadono fino a perdere contro il valore base token-per-byte di un file fresco
- **`test_kv_cache_eviction_values_fresh_snapshots`** `ds4_server.c:17152`  
  La recenza e il rapporto token-byte possono far eliminare un file più grande
- **`test_kv_cache_file_size_must_fit_budget`** `ds4_server.c:16822`  
  Budget zero significa illimitato, ma un overflow resta sempre rifiutato
- **`test_kv_cache_lookup_rejects_stale_payload_abi`** `ds4_server.c:16976`  
  Un file altrimenti valido viene ignorato se il byte ABI riservato vale zero
- **`test_kv_cache_lookup_rejects_wrong_model`** `ds4_server.c:16944`  
  Lo stesso testo è invisibile con model_id errato ma valido con quello esatto
- **`test_kv_cache_lookup_uses_longest_text_prefix`** `ds4_server.c:16904`  
  Il match è sui byte del testo e preferisce il prefisso più lungo, non il primo file trovato
- **`test_kv_cache_store_len_uses_configured_boundary`** `ds4_server.c:16710`  
  Con allineamento zero salva tutti i token; sotto la soglia predefinita non arrotonda
- **`test_kv_stub_file`** `ds4_server.c:16842`  
  Scrive payload un byte alla volta e torna presto se fopen fallisce dopo aver registrato l'assert
- **`test_kv_text_stub_file`** `ds4_server.c:16898`  
  Imposta sempre model_id a zero
- **`test_kv_text_stub_file_model`** `ds4_server.c:16867`  
  Il nome file dipende solo dallo SHA-1 del testo, non da model_id o reason
- **`test_kv_tool_map_filters_by_dsml_text`** `ds4_server.c:17017`  
  La mappa non salva tutti gli ID: scarta quelli il cui DSML non compare nel testo selezionato
- **`test_kv_tool_map_restores_before_prompt_render`** `ds4_server.c:17077`  
  Il DSML esatto su disco prevale sugli argomenti canonici ricostruiti dal messaggio
- **`test_model_alias_thinking_controls`** `ds4_server.c:14756`  
  glm-5.2 resta neutro, mentre i suffissi chat e reasoner comandano il thinking.
- **`test_model_metadata_clamps_completion_to_context`** `ds4_server.c:16588`  
  Il limite di completamento viene ridotto al contesto solo quando lo supera
- **`test_nested_json_array`** `ds4_server.c:16439`  
  A profondità zero restituisce il valore JSON 0, non un array.
- **`test_openai_chat_stream_splits_reasoning_without_tools`** `ds4_server.c:14279`  
  Il reasoning può iniziare senza tag <think> e chiudersi con </think>.
- **`test_openai_glm_tool_stream_suppresses_raw_tool_call`** `ds4_server.c:14413`  
  I tag GLM vengono soppressi come i marcatori DSML.
- **`test_openai_stream_usage_reports_cache_details`** `ds4_server.c:14190`  
  L'usage è emesso nello stream prima di data: [DONE].
- **`test_openai_tool_args_preserve_call_order`** `ds4_server.c:15023`  
  L'ordine schema command-description non sovrascrive quello della call.
- **`test_openai_tool_stream_handles_multiple_calls`** `ds4_server.c:14647`  
  Ogni call riceve un ID call_ distinto nello stesso chunk.
- **`test_openai_tool_stream_holds_partial_dsml_entities`** `ds4_server.c:14548`  
  Sul wire appare & solo dopo il completamento; &amp non trapela.
- **`test_openai_tool_stream_holds_partial_utf8_arguments`** `ds4_server.c:14592`  
  Non sostituisce il carattere spezzato con U+FFFD.
- **`test_openai_tool_stream_sends_incremental_text`** `ds4_server.c:14132`  
  Tag think e marcatori DSML non raggiungono il client.
- **`test_openai_tool_stream_sends_partial_arguments`** `ds4_server.c:14333`  
  Nome e chiave JSON precedono i frammenti del valore sul wire.
- **`test_openai_tool_stream_sends_partial_raw_arguments`** `ds4_server.c:14512`  
  Il frammento [1,2,3 viene inviato prima di essere JSON completo.
- **`test_openai_tool_stream_waits_for_incomplete_tool_tags`** `ds4_server.c:14471`  
  Il nome bash può uscire mentre il tag parameter incompleto resta nascosto.
- **`test_parse_glm_tool_call_message`** `ds4_server.c:15105`  
  Anche timeout viene conservato come stringa "10".
- **`test_parse_short_dsml_and_canonical_suffix`** `ds4_server.c:15068`  
  Accetta tag corti ma il checkpoint aggiunge chiusura think ed EOS canonici.
- **`test_reasoning_effort_mapping`** `ds4_server.c:14743`  
  low, medium, high e xhigh collassano tutti su DS4_THINK_HIGH.
- **`test_render_chat_prompt_text_renders_tools_before_system`** `ds4_server.c:14887`  
  Il system client resta nella coda dinamica dopo gli schemi, utile alla cache prefisso.
- **`test_render_drops_old_reasoning_without_tools`** `ds4_server.c:14826`  
  Al posto del reasoning scartato resta una chiusura </think> vuota.
- **`test_render_glm_chat_prompt_text`** `ds4_server.c:14915`  
  Il prompt GLM non contiene alcun marcatore DSML.
- **`test_render_glm_drops_old_reasoning_without_tools`** `ds4_server.c:14947`  
  Il contenuto resta preceduto da <think></think> vuoto.
- **`test_render_glm_preserves_reasoning_with_tools`** `ds4_server.c:14974`  
  Il risultato usa observation/tool_response, non il formato DSML.
- **`test_render_non_thinking_prompt_closes_think`** `ds4_server.c:14811`  
  Compare </think> senza un <think> di apertura nel turno assistant.
- **`test_render_preserves_reasoning_with_tools`** `ds4_server.c:14852`  
  Il reasoning viene preservato anche passando tool_schemas nullo.
- **`test_render_think_max_prompt_prefix`** `ds4_server.c:14789`  
  Il prompt termina con <think> aperto e senza chiusura.
- **`test_request_defaults_use_min_p_filtering`** `ds4_server.c:14732`  
  top_k è zero mentre il filtro min-p resta attivo.
- **`test_responses_function_named_tool_search_stays_function_call`** `ds4_server.c:13593`  
  Il solo nome tool_search non basta a produrre tool_search_call.
- **`test_responses_input_function_call_namespace_round_trips_to_dsml`** `ds4_server.c:13729`  
  Nel DSML compare il nome interno concatenato, non il nome wire isolato.
- **`test_responses_input_tool_search_output_loads_tools`** `ds4_server.c:13680`  
  I tool caricati usano internamente il nome namespace più funzione.
- **`test_responses_input_tool_search_output_rejects_bad_tools`** `ds4_server.c:13715`  
  Il fallimento è dell'intero input, non il salto del solo elemento errato.
- **`test_responses_live_tail_renders_tool_outputs_only`** `ds4_server.c:16027`  
  Il suffisso non ripete il nome exec_command della call.
- **`test_responses_namespace_tool_schemas_restore_wire_namespace`** `ds4_server.c:13632`  
  Il nome interno concatenato non deve comparire sul wire.
- **`test_responses_output_sends_tool_search_call_item`** `ds4_server.c:13764`  
  Gli argomenti restano un oggetto JSON, non una stringa da function_call.
- **`test_responses_stateless_tool_replay_requires_reasoning`** `ds4_server.c:16099`  
  Neppure lo stato live elimina il requisito; DS4_THINK_NONE invece lo annulla.
- **`test_responses_tool_output_id_validation`** `ds4_server.c:16064`  
  Un output isolato fallisce senza stato live ma passa se l'ID è nel frontier.
- **`test_responses_usage_reports_cache_details`** `ds4_server.c:14221`  
  Lo stesso schema usage è richiesto sia nel finale HTTP sia nell'evento completed.
- **`test_responses_visible_suffix_matches_client_replay`** `ds4_server.c:16175`  
  Il summary è omesso col solo testo ma incluso quando segue una tool call.
- **`test_server_bind_slot`** `ds4_server.c:13478`  
  Azzera completamente lo slot passato.
- **`test_sha1_bytes_hex_matches_known_vector`** `ds4_server.c:16836`  
  Il test copre un solo vettore e non lunghezze o input binari limite
- **`test_stop_list_parses_all_sequences`** `ds4_server.c:16406`  
  Con stop massima lunga quattro trattiene sempre gli ultimi tre byte.
- **`test_stop_list_streaming_holds_and_trims_stop_text`** `ds4_server.c:16422`  
  Da hello </ risultano sicuri solo i primi tre caratteri.
- **`test_streaming_holds_partial_utf8`** `ds4_server.c:14691`  
  I due byte iniziali dell'emoji non producono carattere sostitutivo.
- **`test_thinking_canonical_empty_content`** `ds4_server.c:17558`  
  Anche senza contenuto produce </think> più EOS e rimuove il reasoning dal prompt futuro
- **`test_thinking_canonical_multi_turn`** `ds4_server.c:17607`  
  Il prompt futuro elimina il reasoning di entrambi i turni assistant precedenti
- **`test_thinking_canonical_non_thinking_mode_noop`** `ds4_server.c:17715`  
  Il prompt finisce con </think> pur avendo thinking disattivato, quindi non scatta il binding live
- **`test_thinking_canonical_with_tools_preserves_reasoning`** `ds4_server.c:17676`  
  Con i tool il reasoning resta tra <think> e </think>, opposto al percorso senza tool
- **`test_thinking_checkpoint_canonical_matches_future_prompt`** `ds4_server.c:17475`  
  La forma canonica scarta il reasoning e inserisce </think>, contenuto visibile ed EOS
- **`test_thinking_checkpoint_remember_gate`** `ds4_server.c:16646`  
  Ricorda solo su stop, fuori da think, senza reasoning preservato né tool e con thinking attivo
- **`test_thinking_dsml_after_think_close_is_executable`** `ds4_server.c:15474`  
  La stessa sintassi ignorata nel thinking diventa eseguibile subito dopo la chiusura.
- **`test_thinking_dsml_is_not_executable_before_think_close`** `ds4_server.c:15450`  
  Una call sintatticamente valida resta testo di reasoning e calls rimane vuoto.
- **`test_thinking_state_tracks_prompt_and_generated_tags`** `ds4_server.c:16619`  
  I tag spezzati su più chunk cambiano stato; con think disattivo il prompt non lo apre
- **`test_tool_checkpoint_canonicalization_gate_exact_replay`** `ds4_server.c:15998`  
  Testo raw presente evita la canonicalizzazione, salvo flag di disabilitazione.
- **`test_tool_checkpoint_minifies_json_parameters`** `ds4_server.c:15648`  
  La canonicalizzazione minifica il JSON pur mantenendo identico il prompt futuro.
- **`test_tool_checkpoint_suffix_is_future_prompt_canonical`** `ds4_server.c:15499`  
  Operatori shell come && e > restano non escapati nel DSML canonico.
- **`test_tool_marker_state_ignores_orphan_end`** `ds4_server.c:16671`  
  Un marcatore finale orfano alza orphan_end ma lascia saw_end falso
- **`test_tool_memory_max_ids_prunes_oldest`** `ds4_server.c:16311`  
  Il replay dell'elemento espulso ricade in forma canonica e conta un ID mancante.
- **`test_tool_memory_replays_sampled_dsml`** `ds4_server.c:15722`  
  Il replay ripristina l'ordine campionato, non quello del JSON ricostruito.
- **`test_tool_parse_failure_returns_recoverable_finish`** `ds4_server.c:15370`  
  La funzione ritorna false ma imposta recovered e converte finish in stop.
- **`test_tool_schema_order_from_anthropic_schema`** `ds4_server.c:13534`  
  Controlla solo due proprietà di un singolo tool.
- **`test_tool_schema_order_from_openai_tools`** `ds4_server.c:13548`  
  Controlla l'ordine di dichiarazione, non quello dell'array required.
- **`test_tool_schema_order_from_responses_tool_search`** `ds4_server.c:13570`  
  tool_search viene normalizzato come schema di funzione ma marcato a parte.
- **`test_tool_separator_whitespace_is_not_content`** `ds4_server.c:16341`  
  Quattro newline di separazione vengono rimossi fino al testo visibile.
- **`text_starts_with_think_tag`** `ds4_server.c:2734`  
  Riconosce il tag solo al byte zero, senza spazi iniziali.
- **`text_stream_safe_limit`** `ds4_server.c:8143`  
  Durante lo stream trattiene whitespace finale e l'ultimo frammento che inizia con <.
- **`think_close_kind_name`** `ds4_eval.c:2581`  
  Valori sconosciuti vengono classificati come none.
- **`think_mode_from_enabled`** `ds4_server.c:1033`  
  Ogni effort non NONE e non MAX viene promosso a HIGH
- **`thinking_live_clear`** `ds4_server.c:8769`  
  Con server o slot nullo non fa nulla.
- **`thinking_live_remember`** `ds4_server.c:8776`  
  Un testo vuoto lascia intatto l'eventuale checkpoint precedente.
- **`thinking_live_visible_prefix_prompt`** `ds4_server.c:9842`  
  Richiede un suffisso non vuoto e rifiuta sempre API Responses.
- **`thinking_state_feed`** `ds4_server.c:10268`  
  Riconosce i tag anche se compaiono come semplice testo o attraversano più token.
- **`thinking_state_from_prompt`** `ds4_server.c:10281`  
  Senza prompt testuale presume di essere dentro think quando la modalità è attiva.
- **`title`** `ds4_help.c:40`  
  Senza colore stampa comunque il titolo
- **`title_red`** `ds4_help.c:44`  
  Senza colore stampa comunque il titolo
- **`token_printer_finish`** `ds4_cli.c:488`  
  Un prefisso think incompleto è stampato letteralmente solo con format_thinking attivo.
- **`token_printer_process`** `ds4_cli.c:442`  
  Se malloc fallisce scarta silenziosamente tutto il testo del segmento.
- **`token_printer_set_grey`** `ds4_cli.c:422`  
  Non emette nulla se l'output non è TTY o il colore risulta già aperto.
- **`token_printer_write_char`** `ds4_cli.c:436`  
  Tratta ogni byte separatamente; non valida UTF-8.
- **`token_printer_write_text`** `ds4_cli.c:506`  
  Nel ramo diretto non esegue flush; lo fanno i chiamanti.
- **`token_rank_in_top`** `ds4_eval.c:2591`  
  OOM e token assente producono entrambi rango zero.
- **`token_vec_free`** `ds4.c:35629`  
  Azzera l'intera struttura dopo free.
- **`token_vec_push`** `ds4.c:35621`  
  Il raddoppio della capacità non controlla overflow.
- **`tokenize_rendered_chat_vocab`** `ds4.c:36754`  
  Le stringhe speciali nel testo bypassano il normale BPE ovunque compaiano
- **`tokenize_span`** `ds4.c:36742`  
  Un intervallo vuoto non produce alcuna operazione
- **`tokens_append`** `ds4_kvstore.c:815`  
  Con puntatori NULL non fa nulla senza errore
- **`tokens_copy_prefix`** `ds4_server.c:9430`  
  La destinazione viene modificata dal wrapper sottostante.
- **`tokens_insert`** `ds4_cli.c:1329`  
  Corregge pos fuori intervallo, ma su realloc fallita termina il processo.
- **`tokens_remove`** `ds4_cli.c:1348`  
  Posizione o lunghezza non valide diventano un no-op o vengono troncate.
- **`tool_block_unlink_entry`** `ds4_server.c:8597`  
  Se la voce non è presente termina senza segnalare errore.
- **`tool_call_free`** `ds4_server.c:891`  
  Azzera la struttura dopo la liberazione
- **`tool_call_json_args_add`** `ds4_server.c:4900`  
  Solo il flag esatto true quota il valore; gli altri sono JSON grezzo
- **`tool_calls_contains_id`** `ds4_server.c:8987`  
  Un limite negativo produce sempre falso; uno eccessivo viene troncato.
- **`tool_calls_free`** `ds4_server.c:898`  
  Libera anche raw_tool_text, non solo il vettore di chiamate
- **`tool_calls_push`** `ds4_server.c:905`  
  Copia superficialmente la struttura e trasferisce di fatto la proprieta dei campi
- **`tool_has_topic`** `ds4_help.c:405`  
  Un topic NULL o all è accettato per ogni strumento
- **`tool_memory_attach_to_messages`** `ds4_server.c:8932`  
  Su mismatch usa il rendering canonico senza segnalare errore.
- **`tool_memory_find_block_locked`** `ds4_server.c:8609`  
  Un DSML vuoto non è mai ricercabile.
- **`tool_memory_find_entry_locked`** `ds4_server.c:8674`  
  ID nulli o vuoti vengono trattati come assenti senza errore.
- **`tool_memory_free`** `ds4_server.c:8723`  
  Azzera anche i limiti configurati insieme al resto della struttura.
- **`tool_memory_get_block_locked`** `ds4_server.c:8617`  
  La contabilizzazione include struttura e terminatore, non solo il testo DSML.
- **`tool_memory_has_id`** `ds4_server.c:8887`  
  Con replay esatto disabilitato restituisce falso anche per ID presenti.
- **`tool_memory_init_locked`** `ds4_server.c:8567`  
  Se esiste un solo indice, ne sovrascrive il puntatore creando una perdita.
- **`tool_memory_link_head`** `ds4_server.c:8574`  
  Su lista vuota imposta anche tail.
- **`tool_memory_lookup_locked`** `ds4_server.c:8895`  
  Una semplice lettura modifica l'ordine di espulsione LRU.
- **`tool_memory_max_bytes`** `ds4_server.c:8563`  
  Un limite configurato a zero riattiva il default di 512 MiB.
- **`tool_memory_max_entries`** `ds4_server.c:8559`  
  Un limite configurato a zero o negativo riattiva il default di 100000.
- **`tool_memory_prune_locked`** `ds4_server.c:8666`  
  Può espellere subito la voce appena inserita se supera da sola il limite byte.
- **`tool_memory_put`** `ds4_server.c:8927`  
  Non esiste nella build di produzione.
- **`tool_memory_put_locked`** `ds4_server.c:8681`  
  RAM aggiorna una voce disk, ma una scrittura disk non declassa una voce RAM.
- **`tool_memory_put_source`** `ds4_server.c:8917`  
  Con replay esatto disabilitato ignora silenziosamente l'inserimento.
- **`tool_memory_release_block_locked`** `ds4_server.c:8637`  
  Un contatore refs incoerente può liberare il blocco prematuramente.
- **`tool_memory_remember`** `ds4_server.c:8906`  
  Tutte le chiamate del gruppo puntano allo stesso blocco DSML.
- **`tool_memory_remove_entry_locked`** `ds4_server.c:8650`  
  I contatori saturano a zero invece di segnalare un underflow logico.
- **`tool_memory_touch`** `ds4_server.c:8590`  
  Incrementa il clock anche se la voce è già in testa.
- **`tool_memory_unlink`** `ds4_server.c:8582`  
  Azzera prev e next della voce rimossa.
- **`tool_name`** `ds4_help.c:109`  
  Un enum sconosciuto ricade silenziosamente su ds4
- **`tool_param_value_stream_safe_len`** `ds4_server.c:6372`  
  Protegge le entità DSML solo quando is_string è vero
- **`tool_parse_failure_recovery_finish`** `ds4_server.c:5421`  
  Conserva solo length; anche NULL e valori inattesi diventano stop
- **`tool_schema_order_free`** `ds4_server.c:952`  
  Azzera l'intera struttura dopo la liberazione
- **`tool_schema_order_prop_push`** `ds4_server.c:967`  
  Trasferisce la proprieta di prop senza duplicarla
- **`tool_schema_orders_add_json_wire`** `ds4_server.c:1682`  
  Ignora l'esito del parsing properties e può salvare un ordine parziale.
- **`tool_schema_orders_find`** `ds4_server.c:997`  
  Restituisce un puntatore preso in prestito, invalidabile da push o free
- **`tool_schema_orders_find_index`** `ds4_server.c:975`  
  Il confronto e esatto e sensibile alle maiuscole; NULL restituisce -1
- **`tool_schema_orders_push`** `ds4_server.c:983`  
  Un nome duplicato libera e sostituisce silenziosamente l'ordine precedente
- **`tool_summary`** `ds4_help.c:136`  
  Un enum sconosciuto restituisce una stringa vuota
- **`tool_usage`** `ds4_help.c:120`  
  Un enum sconosciuto ricade silenziosamente sull'uso di ds4
- **`top2_insert_candidate`** `ds4_cuda.cu:14325`  
  Ignora in silenzio un indice già presente in una delle due posizioni.
- **`topic_is`** `ds4_help.c:105`  
  Un topic NULL produce sempre falso
- **`topk_desc`** `ds4.c:11025`  
  A parità di punteggio conserva prima l'indice incontrato prima.
- **`topk_float_ordered_key`** `rocm/ds4_rocm_indexer.cuh:312`  
  I NaN vengono ordinati per rappresentazione binaria, non per semantica numerica.
- **`topk_mask_kernel`** `rocm/ds4_rocm_indexer.cuh:745`  
  Indici fuori intervallo o duplicati non danno errore e lasciano meno di top_k zeri.
- **`topk_pack_key`** `rocm/ds4_rocm_indexer.cuh:317`  
  L'indice è complementato, quindi a parità vince quello minore.
- **`topk_score_better`** `rocm/ds4_rocm_indexer.cuh:308`  
  A parità di score vince l'indice minore.
- **`tp_command_decode_tokens`** `ds4_tp.c:1971`  
  Con count zero alloca comunque un byte e riesce.
- **`tp_dial`** `ds4_tp.c:502`  
  Stampa un messaggio già al primo tentativo fallito.
- **`tp_gate_slot`** `ds4_tp.c:1047`  
  Con seq zero il calcolo underflowa.
- **`tp_hello_exchange`** `ds4_tp.c:1451`  
  In auto, RDMA assente degrada silenziosamente a TCP.
- **`tp_listen`** `ds4_tp.c:475`  
  Host vuoto effettua bind wildcard.
- **`tp_now_sec`** `ds4_tp.c:400`  
  Non è tempo civile.
- **`tp_peer_closed`** `ds4_tp.c:465`  
  I dati letti con PEEK restano nel socket.
- **`tp_rdma_big_gate_capable`** `ds4_tp.c:1183`  
  Non verifica rdma_active, solo risorse e capienza batch.
- **`tp_rdma_big_gate_exchange`** `ds4_tp.c:1288`  
  Fuori slab usa e sovrascrive le regioni batch come staging.
- **`tp_rdma_close`** `ds4_tp.c:1435`  
  Non chiude librdma né distrugge il mutex.
- **`tp_rdma_drain_cq`** `ds4_tp.c:1057`  
  Un solo errore di completion abortisce tutto il drain.
- **`tp_rdma_drain_decode_window`** `ds4_tp.c:1195`  
  Usa batch_out come scratch e invia dati dummy.
- **`tp_rdma_gate_exchange`** `ds4_tp.c:1118`  
  La presenza di DS4_TP_GATE_TRACE abilita il log, anche se vuota.
- **`tp_rdma_load_api`** `ds4_tp.c:793`  
  Cerca solo librdma.dylib e fallisce senza spiegare il simbolo mancante.
- **`tp_rdma_open`** `ds4_tp.c:835`  
  Senza indice esplicito accetta solo un GID IPv4-mapped.
- **`tp_rdma_post_gate_recv`** `ds4_tp.c:1081`  
  Spezza oltre 16 KiB; solo l'ultimo chunk porta la seq.
- **`tp_rdma_probe`** `ds4_tp.c:826`  
  Lascia la libreria caricata anche se non trova device.
- **`tp_rdma_register_and_exchange`** `ds4_tp.c:940`  
  Lascia vuota la receive queue fino al primo gate di decode.
- **`tp_read_frame_header`** `ds4_tp.c:547`  
  Non valida il tipo né limita la lunghezza dichiarata.
- **`tp_read_full`** `ds4_tp.c:433`  
  EOF prima di len byte è indistinguibile da errore.
- **`tp_send_frame`** `ds4_tp.c:540`  
  Header e payload sono due scritture separate.
- **`tp_send_token_command`** `ds4_tp.c:1834`  
  Converte ogni int in int32_t senza controllo.
- **`tp_set_err`** `ds4_tp.c:406`  
  Con err NULL o errlen zero non fa nulla.
- **`tp_slab_layout`** `ds4_tp.c:744`  
  Non alloca né verifica la capienza del buffer.
- **`tp_slot`** `ds4_tp.c:764`  
  Non controlla i limiti.
- **`tp_socket_tune`** `ds4_tp.c:448`  
  Ignora tutti gli errori di setsockopt.
- **`tp_wc_status_str`** `ds4_tp.c:1038`  
  Restituisce un buffer statico sovrascritto alla chiamata seguente.
- **`tp_windows_unavailable`** `ds4_tp.c:23`  
  Con err NULL o errlen zero non segnala nulla.
- **`tp_worker_send_logits`** `ds4_tp.c:2228`  
  Copia tutto il vocabolario nel buffer ma invia solo la seconda metà.
- **`tp_worker_session_add`** `ds4_tp.c:2201`  
  ID zero, duplicato e realloc fallita producono lo stesso esito senza diagnostica.
- **`tp_worker_session_find`** `ds4_tp.c:2195`  
  Il puntatore restituito diventa pendente appena la sessione viene rimossa.
- **`tp_worker_session_index`** `ds4_tp.c:2186`  
  L'ID zero è sempre trattato come assente e la ricerca è lineare.
- **`tp_worker_session_remove`** `ds4_tp.c:2217`  
  Un indice non valido è ignorato; quelli successivi cambiano dopo memmove.
- **`tp_write_full`** `ds4_tp.c:414`  
  Riprova solo EINTR; una send da zero è errore.
- **`trace_begin`** `ds4_server.c:10052`  
  Con trace disattivo restituisce ID 0 senza segnalare errore.
- **`trace_cache_capture`** `ds4_server.c:9902`  
  Marca la diagnosi valida anche se live o prompt sono nulli.
- **`trace_cache_miss_reason`** `ds4_server.c:9934`  
  Restituisce live-prefix-match anche se il chiamante la usa come reason di miss.
- **`trace_copy_model_output`** `ds4_eval.c:3246`  
  Nel formato legacy il primo delimitatore incorporato tronca il payload.
- **`trace_copy_self_test_case`** `ds4_eval.c:3407`  
  Copre soltanto il formato contato, non il fallback legacy.
- **`trace_event`** `ds4_server.c:10115`  
  Con trace disattivo o ID 0 non produce alcun evento.
- **`trace_find_block_begin`** `ds4_eval.c:3193`  
  Confronta solo il prefisso della riga, quindi accetta etichette con suffissi inattesi.
- **`trace_find_next_case`** `ds4_eval.c:3170`  
  I vecchi blocchi senza conteggio non proteggono marker CASE incorporati.
- **`trace_finish`** `ds4_server.c:10128`  
  Per richieste non chat omette reasoning, contenuto e tool call analizzati.
- **`trace_get_line_field`** `ds4_eval.c:3216`  
  Non salta i blocchi contati; un campo mancante può essere imitato dal testo del modello.
- **`trace_piece`** `ds4_server.c:10107`  
  Ignora in silenzio ID 0, puntatore nullo e pezzi vuoti.
- **`trace_skip_counted_block`** `ds4_eval.c:3131`  
  Un conteggio malformato non viene saltato e può esporre falsi marker CASE allo scanner.
- **`trace_time`** `ds4_server.c:10043`  
  Non include fuso orario né millisecondi.
- **`trace_write_block`** `ds4_eval.c:2568`  
  Il newline aggiunto al testo non è incluso nel conteggio bytes.
- **`trace_write_cache_diag`** `ds4_server.c:9979`  
  Non scrive la finestra token se il prefisso vivo è riusabile.
- **`trace_write_case`** `ds4_eval.c:2650`  
  Ogni caso non multiple-choice, incluso COMPSEC, viene etichettato exact_integer.
- **`trace_write_escaped_bytes`** `ds4_server.c:9942`  
  I byte non ASCII vengono emessi grezzi, senza validazione UTF-8.
- **`trace_write_header`** `ds4_eval.c:2607`  
  Con trace NULL ritorna senza alcuna segnalazione.
- **`trace_write_token`** `ds4_server.c:9967`  
  Un token negativo produce il segnaposto none senza interrogare il tokenizer.
- **`tracking_enabled`** `src/cuda/vram_expert_cache.cpp:312`  
  Observe abilita il tracking pur senza allocare né pubblicare slot VRAM.
- **`trim_const_span`** `ds4_server.c:5192`  
  Usa isspace dipendente dalla locale
- **`trim_inplace`** `ds4_cli.c:1286`  
  Il puntatore restituito può trovarsi dentro il buffer originale.
- **`trim_tool_separator_ws`** `ds4_server.c:4834`  
  Usa isspace dipendente dalla locale, non solo spazi ASCII
- **`try_repair_dsml`** `ds4_server.c:5365`  
  Conta anche sequenze simili a tag presenti nei payload
- **`tui_clear_left_line`** `ds4_eval.c:1776`  
  Lascia infine il cursore all'inizio della riga.
- **`tui_consume_input`** `ds4_eval.c:1967`  
  L'uscita cancella la pausa e scarta movimento e invio dello stesso lotto.
- **`tui_draw_frame`** `ds4_eval.c:2056`  
  Cancella l'intero schermo alternativo.
- **`tui_draw_left`** `ds4_eval.c:2068`  
  La finestra segue la selezione dell'utente, non necessariamente il caso attivo.
- **`tui_draw_question_preview`** `ds4_eval.c:1828`  
  Il wrapping è a byte e può spezzare parole o UTF-8.
- **`tui_draw_right_status`** `ds4_eval.c:2316`  
  Nel thinking limita solo il conteggio visualizzato, non quello reale.
- **`tui_draw_stream`** `ds4_eval.c:2220`  
  Wrapping e indici stile sono per byte; UTF-8 può essere spezzato.
- **`tui_draw_title`** `ds4_eval.c:2044`  
  La durata mostrata esclude gli intervalli in pausa.
- **`tui_free`** `ds4_eval.c:2406`  
  Azzera ui ma non annulla global_ui, che resta puntato alla struttura.
- **`tui_has_quit_request`** `ds4_eval.c:3647`  
  Con TUI disabilitata ignora quit_requested anche se impostato.
- **`tui_has_switch_request`** `ds4_eval.c:3640`  
  Una richiesta verso il caso già in esecuzione viene ignorata.
- **`tui_refresh`** `ds4_eval.c:2347`  
  Con TUI abilitata fa un redraw completo e un flush a ogni chiamata.
- **`tui_reset_stream`** `ds4_eval.c:2137`  
  Azzera le lunghezze ma conserva la memoria CPU già allocata.
- **`tui_restore`** `ds4_eval.c:2013`  
  È chiamabile sia esplicitamente sia da atexit e diventa un no-op dopo la prima volta.
- **`tui_right_text_w`** `ds4_eval.c:1769`  
  Riserva sempre l'ultima colonna fisica per evitare il wrapping differito.
- **`tui_run_clock_start`** `ds4_eval.c:1306`  
  Una seconda chiamata mentre è attivo non reimposta l'istante.
- **`tui_run_clock_stop`** `ds4_eval.c:1312`  
  Prima di fermarsi esegue un tick finale.
- **`tui_run_clock_tick`** `ds4_eval.c:1298`  
  Ignora delta nulli o negativi e non fa nulla a clock fermo.
- **`tui_run_clock_visible_sec`** `ds4_eval.c:1318`  
  Calcola il tratto attivo senza modificare l'accumulatore.
- **`tui_signal_restore`** `ds4_eval.c:2022`  
  Dopo il ripristino reinstalla l'azione predefinita e termina tramite lo stesso segnale.
- **`tui_start`** `ds4_eval.c:2355`  
  Alloca gli array anche con TUI disabilitata o terminale troppo piccolo.
- **`tui_start_input`** `ds4_eval.c:1912`  
  Su errore o stdin non TTY disabilita l'input senza rendere fallita la TUI.
- **`tui_stop_input`** `ds4_eval.c:1952`  
  Può attendere il join prima di ripristinare termios.
- **`tui_wait_if_paused`** `ds4_eval.c:3656`  
  Esegue polling ogni 50 ms e può attendere indefinitamente.
- **`unlock_source_range`** `src/cuda/dynamic_arena.cu:789`  
  Su Windows ERROR_NOT_LOCKED vale successo; su POSIX usa posix_madvise
- **`update_and_wrap_locked`** `src/cuda/dynamic_arena.cu:1063`  
  Con accumulate=true il ranking persiste e può saturare UINT64_MAX
- **`utf8ByteLen`** `linenoise.c:245`  
  Byte iniziali non validi vengono trattati come caratteri da un byte.
- **`utf8CharWidth`** `linenoise.c:457`  
  È una euristica parziale: caratteri ambigui possono disallineare il cursore.
- **`utf8DecodeChar`** `linenoise.c:256`  
  Non valida continuation byte, overlong encoding o code point illegali.
- **`utf8DecodePrev`** `linenoise.c:323`  
  Scansiona al massimo quattro byte e non valida la sequenza trovata.
- **`utf8NextCharLen`** `linenoise.c:400`  
  Accoppia una sola coppia RI e usa regole ZWJ semplificate.
- **`utf8PrevCharLen`** `linenoise.c:344`  
  Le bandiere vengono accoppiate con una semplificazione, non secondo tutta la sequenza RI.
- **`utf8SingleCharWidth`** `linenoise.c:567`  
  len non limita il decoder oltre al caso zero.
- **`utf8StrWidth`** `linenoise.c:527`  
  La larghezza dei grafemi è euristica e può differire da quella del terminale.
- **`utf8_decode_one`** `ds4.c:36907`  
  Non valida byte di continuazione, overlong o codepoint illegali.
- **`utf8_expected_len`** `ds4_server.c:1265`  
  Byte iniziali invalidi e byte di continuazione sono trattati come unità da un byte.
- **`utf8_is_cjk_hira_kata`** `ds4.c:36136`  
  Il CJK termina a U+9FA5 e non copre tutte le estensioni
- **`utf8_len_from_first_byte`** `ds4.c:36000`  
  Un byte iniziale non valido viene trattato come carattere da un byte
- **`utf8_peek_one`** `ds4.c:36142`  
  Non valida continuazioni, codifiche overlong o valori Unicode illegali
- **`utf8_put`** `ds4_server.c:419`  
  Non valida il limite Unicode né i code point surrogati
- **`utf8_stream_safe_len`** `ds4_server.c:1278`  
  Con final=true restituisce il limite senza validare la coda UTF-8.
- **`validate_compress_ratio_metadata`** `ds4.c:5563`  
  Accetta array più lunghi e ignora gli elementi oltre DS4_N_LAYER.
- **`validate_swiglu_clamp_metadata`** `ds4.c:5601`  
  Accetta elementi extra e converte i FLOAT64 a float prima del confronto.
- **`verify_active_locked`** `src/cuda/dynamic_arena.cu:1109`  
  Rifiuta anche uno snapshot coerente ma vuoto
- **`visible_live_clear_locked`** `ds4_server.c:8754`  
  Non libera la struttura contenitore, solo il testo posseduto.
- **`visible_live_free`** `ds4_server.c:8763`  
  Esegue un memset completo dopo che clear ha già azzerato i campi.
- **`vocab_free`** `ds4.c:36621`  
  Azzera anche tutti gli ID speciali dopo la liberazione
- **`vocab_load`** `ds4.c:36542`  
  In GLM molti marcatori mancanti restano silenziosamente a meno uno
- **`vocab_lookup`** `ds4.c:36525`  
  Un token mancante termina immediatamente il processo
- **`vocab_lookup_optional`** `ds4.c:36534`  
  L'assenza viene accettata silenziosamente come meno uno
- **`vocab_token_is_generation_stop`** `ds4.c:36992`  
  Su GLM anche system, user, assistant e observation fermano la generazione.
- **`vocab_token_is_literal_special`** `ds4.c:36953`  
  La sola presenza della barra rende letterale l'intero token.
- **`wait_distributed_route`** `ds4_eval.c:4102`  
  Non ha timeout e può attendere per sempre, ripetendo il log ogni 20 cicli.
- **`wall_ms`** `ds4_server.c:4691`  
  Il nome suggerisce wall clock, ma il valore è monotono e non tempo civile.
- **`warp_max_f32`** `rocm/ds4_rocm_common.cuh:361`  
  Solo la lane 0 riceve il massimo globale; le altre conservano massimi parziali.
- **`warp_sum_f32`** `rocm/ds4_rocm_common.cuh:350`  
  Solo la lane 0 riceve la somma completa; le altre conservano somme parziali.
- **`warp_sum_f32_oldhip_w32`** `rocm/ds4_rocm_q8.cuh:1148`  
  Solo la lane 0 riceve la somma completa; le altre mantengono somme parziali
- **`web_browser_ws_url`** `ds4_web.c:1177`  
  Il parser testuale può selezionare una chiave omonima non pertinente
- **`web_buf_append`** `ds4_web.c:122`  
  Su realloc fallito termina l'intero processo
- **`web_buf_take`** `ds4_web.c:144`  
  Da un buffer vuoto restituisce comunque una stringa allocata
- **`web_cancelled`** `ds4_web.c:170`  
  Web nullo o callback assente significano sempre non annullato
- **`web_cdp_alive`** `ds4_web.c:333`  
  Basta trovare la sottostringa webSocketDebuggerUrl nel corpo
- **`web_cdp_call`** `ds4_web.c:666`  
  Scarta definitivamente eventi e risposte con id diverso mentre attende
- **`web_cdp_call_optional`** `ds4_web.c:697`  
  Scarta silenziosamente sia risposta sia errore
- **`web_cdp_eval_string`** `ds4_web.c:803`  
  Risultati validi non stringa sono trattati come errore
- **`web_cdp_navigate`** `ds4_web.c:846`  
  Una risposta CDP contenente un errore è comunque considerata successo
- **`web_cdp_prepare_page`** `ds4_web.c:936`  
  Ignora gli errori dei due comandi Emulation opzionali
- **`web_chrome_executable`** `ds4_web.c:1002`  
  Se non trova nulla restituisce comunque google-chrome senza verificarlo
- **`web_close_tab`** `ds4_web.c:1227`  
  Non propaga il fallimento: al massimo lo invia al callback di log
- **`web_ensure_browser`** `ds4_web.c:1144`  
  Un CDP già attivo bypassa approvazione e proprietà del processo
- **`web_err_is_interrupted`** `ds4_web.c:191`  
  Accetta solo la corrispondenza testuale esatta
- **`web_hex4`** `ds4_web.c:703`  
  Restituisce -1 al primo carattere non esadecimale
- **`web_http_request`** `ds4_web.c:284`  
  Ignora status HTTP, Content-Length e codifica chunked
- **`web_json_get_string`** `ds4_web.c:789`  
  La ricerca testuale può prendere una chiave omonima annidata o contenuta in una stringa
- **`web_json_id_matches`** `ds4_web.c:656`  
  Non esegue parsing JSON strutturale e atoi accetta prefissi numerici
- **`web_json_parse_string_at`** `ds4_web.c:740`  
  Un escape sconosciuto perde il backslash invece di causare errore
- **`web_json_quote`** `ds4_web.c:398`  
  Un puntatore NULL viene serializzato come stringa vuota, non come null JSON
- **`web_log`** `ds4_web.c:160`  
  Senza callback scarta silenziosamente il messaggio
- **`web_macos_chrome_app_name`** `ds4_web.c:1052`  
  Anche DS4_CHROME presente ma vuota disabilita il lancio tramite open
- **`web_mkdir_p`** `ds4_web.c:195`  
  EEXIST è trattato come successo anche se il percorso esistente non è una directory
- **`web_open_tab`** `ds4_web.c:1186`  
  Costruisce l'URL pagina assumendo sempre host locale, porta configurata e percorso fisso
- **`web_page_probe`** `ds4_web.c:862`  
  strtol accetta una lunghezza con suffisso non numerico
- **`web_random_bytes`** `ds4_web.c:359`  
  Se urandom non basta usa senza avviso un generatore prevedibile basato su tempo e PID
- **`web_read_exact`** `ds4_web.c:524`  
  Interroga l'annullamento ogni fetta di polling da 100 ms
- **`web_read_some`** `ds4_web.c:273`  
  Timeout e fine stream restituiscono entrambi zero
- **`web_run_page_js`** `ds4_web.c:1300`  
  Tenta lo script di consenso Google su ogni pagina, non solo su Google
- **`web_scroll_dynamic_page`** `ds4_web.c:950`  
  Ignora ogni errore di valutazione salvo quello testuale interrupted
- **`web_set_cancel_err`** `ds4_web.c:174`  
  L'errore è identificato altrove confrontando esattamente la stringa interrupted
- **`web_set_err`** `ds4_web.c:152`  
  Con buffer nullo o lungo zero non segnala nulla; il testo può essere troncato
- **`web_sleep_ms`** `ds4_web.c:180`  
  Con ms non positivo non dorme ma interroga comunque l'annullamento alla fine
- **`web_spawn_chrome`** `ds4_web.c:1062`  
  Se eseguito come root aggiunge automaticamente --no-sandbox
- **`web_tab_free`** `ds4_web.c:1169`  
  Non libera la struttura web_tab stessa
- **`web_tcp_connect`** `ds4_web.c:208`  
  Non controlla l'annullamento durante risoluzione e connessione
- **`web_url_encode`** `ds4_web.c:344`  
  Un puntatore NULL produce una stringa vuota allocata
- **`web_utf8_append`** `ds4_web.c:717`  
  Non rifiuta surrogati né valori oltre U+10FFFF
- **`web_wait_navigated_ready`** `ds4_web.c:886`  
  Ignora il parametro url e restituisce true anche allo scadere dei 100 tentativi
- **`web_wait_ready`** `ds4_web.c:826`  
  Dopo 80 tentativi restituisce true anche se la pagina non è pronta
- **`web_windows_unavailable`** `ds4_web.c:11`  
  Restituisce sempre NULL anche se il buffer d'errore manca
- **`web_write_all`** `ds4_web.c:257`  
  Senza MSG_NOSIGNAL usa write e una socket chiusa può generare SIGPIPE
- **`web_ws_close`** `ds4_web.c:517`  
  Chiude TCP senza inviare un frame WebSocket close
- **`web_ws_connect`** `ds4_web.c:424`  
  Accetta l'handshake dalla sola presenza di status 101 senza validare Sec-WebSocket-Accept
- **`web_ws_read_message`** `ds4_web.c:595`  
  Il limite vale per singolo frame, non per il messaggio frammentato accumulato
- **`web_ws_send_pong`** `ds4_web.c:583`  
  Tronca silenziosamente payload oltre 125 byte
- **`web_ws_send_text`** `ds4_web.c:549`  
  Costruisce in memoria una copia mascherata dell'intero messaggio
- **`web_xmalloc`** `ds4_web.c:105`  
  Una richiesta di zero byte alloca un byte; un fallimento chiama exit(1)
- **`web_xstrdup`** `ds4_web.c:114`  
  Un puntatore NULL viene convertito nella stringa vuota
- **`weights_bind`** `ds4.c:5982`  
  Un caricamento completo forza la testata obbligatoria ignorando i flag ricevuti.
- **`weights_bind_glm_dsa_layer`** `ds4.c:5886`  
  I layer densi iniziali e quelli finali next-token richiedono insiemi diversi.
- **`weights_bind_layer`** `ds4.c:5928`  
  In DeepSeek4 exp_probs_b è opzionale mentre quasi tutti gli altri tensori sono obbligatori.
- **`weights_bind_output`** `ds4.c:5852`  
  Una testata opzionale presente solo in parte è fatale.
- **`weights_first_bound_layer`** `ds4.c:4951`  
  Salta silenziosamente layer parziali e restituisce NULL se nessuno è completo.
- **`weights_free`** `ds4.c:6959`  
  Non libera memoria: azzera soltanto la struttura.
- **`weights_glm_dsa_layer_has_required`** `ds4.c:4836`  
  Gli ultimi layer MTP richiedono quattro tensori next-token aggiuntivi.
- **`weights_have_output_head`** `ds4.c:4812`  
  GLM richiede solo norm e output; DeepSeek4 richiede anche i tre tensori HC.
- **`weights_have_partial_output_head`** `ds4.c:4824`  
  Anche un solo puntatore valorizzato rende la testata parziale.
- **`weights_layer_has_required`** `ds4.c:4886`  
  Con ratio 4 richiede l'indexer; nei primi hash layer richiede tid2eid.
- **`weights_layers_bound`** `ds4.c:4941`  
  UINT32_MAX come estremo finale significa ultimo layer.
- **`weights_model_map_decode_layer_spans`** `ds4.c:6724`  
  Restituisce falso anche per un layer valido se non emerge alcun intervallo.
- **`weights_model_map_decode_static_slice_spans`** `ds4.c:6749`  
  UINT32_MAX come estremo finale significa ultimo layer.
- **`weights_model_map_decode_static_spans`** `ds4.c:6734`  
  Può includere i blob esperti quando il relativo streaming non è disponibile.
- **`weights_model_map_output_spans`** `ds4.c:6811`  
  Una testata assente porta a falso, non a un errore esplicito.
- **`weights_model_map_sharded_spans`** `ds4.c:6685`  
  Con un numero dispari di esperti il rank 1 prende quello rimanente.
- **`weights_model_map_spans`** `ds4.c:6654`  
  L'embedding token viene incluso soltanto quando la slice parte dal layer zero.
- **`weights_model_map_token_spans`** `ds4.c:6802`  
  Un embedding assente porta a falso, non a un errore esplicito.
- **`weights_streaming_layer_experts_uniform`** `ds4.c:4671`  
  Input invalido o misura impossibile restituiscono true, quindi sembrano uniformi.
- **`weights_streaming_non_routed_bytes`** `ds4.c:6782`  
  Malgrado il nome può contare esperti se il loro streaming non è supportato.
- **`weights_validate_glm_dsa_layout`** `ds4.c:4962`  
  Embedding e testata sono validati se presenti, anche quando non obbligatori.
- **`weights_validate_layout`** `ds4.c:5045`  
  Il bias ffn_exp_probs_b è opzionale; l'assenza passa senza errore.
- **`worker_accept_generated_token`** `ds4_agent.c:8311`  
  Accoda il token al transcript prima dell'eval; un errore lascia il transcript avanzato e invalida la KV.
- **`worker_answer_queued_user_drain`** `ds4_agent.c:4543`  
  Prende proprietà di text e libera qualsiasi risposta precedente.
- **`worker_answer_web_approval`** `ds4_agent.c:4499`  
  Una negazione senza testo usa un errore predefinito.
- **`worker_apply_pending_power`** `ds4_agent.c:8924`  
  Consuma la richiesta prima della chiamata: su errore non la ritenta e lo stato può restare ottimistico.
- **`worker_cancel_session_cb`** `ds4_agent.c:3947`  
  Tratta stop come cancellazione esattamente come interrupt.
- **`worker_check_raw_mode_restore`** `ds4_agent.c:9062`  
  Una lettura true azzera subito la richiesta, prima che la UI ripristini davvero il terminale.
- **`worker_clear_interrupt`** `ds4_agent.c:3937`  
  Non azzera il flag stop.
- **`worker_consume`** `ds4_agent.c:9143`  
  Azzera wake_pending anche se il chiamante non richiede l'output.
- **`worker_force_generated_text`** `ds4_agent.c:8341`  
  Un errore a metà sequenza conserva i token forzati già accettati.
- **`worker_get_status`** `ds4_agent.c:9160`  
  La semplice lettura aggiorna nel worker ctx_used, ctx_size e power_percent.
- **`worker_interrupt`** `ds4_agent.c:9116`  
  Solo il coordinatore distribuito passa subito a DRAINING; gli altri mantengono lo stato corrente.
- **`worker_is_idle`** `ds4_agent.c:9169`  
  Considera IDLE anche lo stato ERROR, purché il worker sia inizializzato.
- **`worker_is_initialized`** `ds4_agent.c:9178`  
  Anche senza status richiesto aggiorna i campi contesto e potenza dentro il worker.
- **`worker_main`** `ds4_server.c:12420`  
  Usa sempre lo slot zero, quindi nessuna concorrenza di inferenza.
- **`worker_progress_cb`** `ds4_agent.c:3890`  
  Ignora total e, con progress_direct, scarta prefill_chunk e prefill_display.
- **`worker_request_compact`** `ds4_agent.c:8879`  
  Non compatta subito: richieste multiple collassano in un solo booleano.
- **`worker_request_power`** `ds4_agent.c:8887`  
  Aggiorna subito lo stato mostrato, prima di sapere se il backend accetterà il cambio.
- **`worker_request_queued_user_drain`** `ds4_agent.c:4517`  
  Attende stop ma non interrupt; con stop può restituire NULL senza una risposta.
- **`worker_request_save`** `ds4_agent.c:8871`  
  Non salva subito: imposta solo un flag e segnala il worker.
- **`worker_run_deferred_compact`** `ds4_agent.c:8951`  
  Se la lunghezza non cambia dichiara che non c'era nulla da compattare, anche dopo successo.
- **`worker_run_deferred_save`** `ds4_agent.c:8938`  
  Un fallimento viene solo pubblicato e lo stato torna comunque IDLE.
- **`worker_run_raw_prompt`** `ds4_agent.c:8770`  
  Dopo il sync sostituisce l'intero transcript con prompt grezzo e token generati.
- **`worker_run_turn`** `ds4_agent.c:8425`  
  Non esiste un limite ai round tool; compattazione, interrupt o risposta finale sono gli unici stop.
- **`worker_sample_with_mode`** `ds4_agent.c:8403`  
  In greedy azzera temperature e min-p e forza top-p a 1, ignorando la configurazione.
- **`worker_set_greedy_sampling`** `ds4_agent.c:8413`  
  Sveglia la UI soltanto quando il valore cambia.
- **`worker_should_interrupt`** `ds4_agent.c:3926`  
  Stop e interrupt sono indistinguibili nel valore restituito.
- **`worker_status_power_locked`** `ds4_agent.c:9109`  
  Una potenza configurata zero o negativa viene mostrata come 100 percento.
- **`worker_stop`** `ds4_agent.c:9134`  
  Imposta il flag e segnala soltanto; non attende la terminazione del thread.
- **`worker_submit`** `ds4_agent.c:9085`  
  Imposta PREFILL prima che il worker inizi davvero, per chiudere la finestra di falso idle.
- **`worker_take_compact_requested`** `ds4_agent.c:8905`  
  La lettura azzera sempre il flag, quindi richieste concorrenti già collassate non si distinguono.
- **`worker_take_power_requested`** `ds4_agent.c:8913`  
  Copia il valore solo se richiesto; accetta power NULL e consuma comunque la richiesta.
- **`worker_take_queued_user_drain_request`** `ds4_agent.c:4535`  
  Azzera pending prima che il testo sia consegnato al worker.
- **`worker_take_save_requested`** `ds4_agent.c:8897`  
  La lettura azzera sempre il flag, anche se il salvataggio successivo fallirà.
- **`worker_take_web_approval_request`** `ds4_agent.c:4487`  
  Azzera pending prima che la richiesta riceva una risposta.
- **`wrap_enabled`** `src/cuda/prefill_observer.cu:376`  
  Rilegge l'ambiente a ogni chiamata, quindi può cambiare durante una richiesta.
- **`wrap_transaction`** `src/cuda/dynamic_arena.cu:917`  
  Con trust=false calcola FNV due volte per slot; con true salta la verifica indipendente
- **`write_all`** `ds4_agent.c:431`  
  Un errore diverso da EINTR interrompe la scrittura senza segnalare quanti byte mancano.
- **`write_f32_binary_file`** `ds4.c:1753`  
  Una scrittura corta salta fclose per il corto circuito logico.
- **`write_frontier_logits_json`** `ds4_bench.c:416`  
  NaN e infiniti diventano null; la directory di destinazione non viene creata.
- **`xcalloc`** `ds4.c:1175`  
  Con la guardia decode attiva termina prima di allocare.
- **`xmalloc`** `ds4_server.c:206`  
  Una richiesta di zero byte può terminare se malloc restituisce NULL.
- **`xmalloc_zeroed`** `ds4.c:1203`  
  Un totale di zero byte alloca comunque un byte.
- **`xrealloc`** `ds4_server.c:212`  
  Con size zero realloc può liberare ptr e poi il wrapper termina su NULL.
- **`xstrdup`** `ds4_server.c:218`  
  La funzione non accetta una sorgente NULL
- **`xstrndup`** `ds4_server.c:337`  
  Gli eventuali NUL interni restano nella copia allocata

### Certezza media (4)

- **`dequant_q8_0_to_f16_kernel`** `rocm/ds4_rocm_q8.cuh:1737`  
  Materializza tutta la matrice e può espandere molto l'uso di VRAM.
- **`dequant_q8_0_to_f32_kernel`** `rocm/ds4_rocm_q8.cuh:1756`  
  Materializza tutta la matrice in FP32, ampliandola di circa quattro volte.
- **`ds4_engine_tp_batch_exchange`** `ds4.c:57118`  
  Un singolo errore marca fallito il contesto TP; non gira sulla nostra CUDA.
- **`matvec_f16_serial`** `ds4.c:7109`  
  È deliberatamente seriale, senza ds4_parallel_for.

## Come rifare questo documento

```bash
python ricongiungi.py ../../../ds4-port/lotti
```
