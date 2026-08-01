La strategia è corretta: **upstream deve restare il substrato**. La sostituzione di `ds4_cuda.cu` sarebbe più costosa e rischiosa del trapianto selettivo.

La granularità giusta, però, non è la singola funzione CUDA: bisogna trapiantare **blocchi con ownership dello stato**, conservando ABI, allocatori, resolver e dispatcher upstream. Il primo porto deve inoltre essere esplicitamente limitato a `g_n_gpus == 1` e al ramo DSV4 non-TP/non-EP.

## Perimetro verificato

Ho lavorato in sola lettura, senza compilare né modificare file.

Le righe richieste corrispondono al **working tree corrente non committato** di `ds4-p4a`, non al solo HEAD:

| File | HEAD `646f3be` | Working tree analizzato |
|---|---:|---:|
| `ds4.c` | 21.550 | **25.043** |
| `ds4_cuda.cu` | 47.052 | **56.765** |

Abbreviazioni:

- `CU`: [nostro ds4_cuda.cu](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu:1)
- `C`: [nostro ds4.c](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4.c:1)
- `H`: [nostro ds4_gpu.h](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_gpu.h:1)
- `OF`: [os_file.c](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.c:1)
- `MM`: [os_mmap.c](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_mmap.c:1)
- `TH`: [os_thread.c](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_thread.c:1)
- `UCU`: [upstream ds4_cuda.cu](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:1)
- `UC`: [upstream ds4.c](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:1)
- `UH`: [upstream ds4_gpu.h](/C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:1)

`LOC` è l’estensione inclusiva della definizione, dalla firma alla graffa finale.

L’estrazione lessicale trova in `CU`:

| Misura verificata | Numero |
|---|---:|
| Nomi callable assenti da `UCU` | 869 |
| Raggiungibili staticamente dai confini `ds4.c` | 427 |
| Punti d’ingresso chiamati direttamente da `ds4.c` | **63** |

Gli 869 includono kernel leaf, overload template, accessor di strutture, fixture e metodi locali. Sotto elenco esaustivamente i **63 confini reali** e poi i controller interni che possiedono lifecycle/stato. I kernel leaf vengono assegnati al controller che li contiene: non costituiscono unità di trapianto indipendenti.

# 1. Inventario dei simboli

## 1.1 Confini diretti con `ds4.c` — elenco esaustivo

### Arena dinamica

| Simbolo assente upstream | Noi / LOC | Chiamante diretto in `ds4.c` | Entry `ds4.c` |
|---|---:|---|:---:|
| `ds4_gpu_dynamic_arena_release` | CU:10354 / 8 | lifecycle/cleanup di `ds4_session_create` | Sì |
| `ds4_gpu_dynamic_arena_bind` | CU:10585 / 8 | `ds4_session_create` | Sì |
| `ds4_gpu_set_primary_moe_geometry` | CU:10594 / 49 | `ds4_session_create` | Sì |
| `ds4_gpu_dynamic_arena_bind_q1_0` | CU:10644 / 89 | `ds4_session_create` | Sì |
| `ds4_gpu_dynamic_arena_bind_q1_0_snapshot` | CU:10734 / 24 | `ds4_session_create` | Sì |
| `ds4_gpu_dynamic_arena_prepare_q1_0` | CU:10759 / 285 | `ds4_session_create` | Sì |
| `ds4_gpu_dynamic_arena_prepare` | CU:11045 / 368 | `ds4_session_create` | Sì |
| `ds4_gpu_dynamic_arena_begin` | CU:11681 / 10 | fixture WRAP/abort in `ds4.c` | Sì |
| `ds4_gpu_dynamic_arena_finish_load` | CU:11737 / 8 | fixture WRAP/abort | Sì |
| `ds4_gpu_dynamic_arena_publish` | CU:11746 / 116 | fixture WRAP | Sì |
| `ds4_gpu_dynamic_arena_abort` | CU:11863 / 37 | fixture WRAP/abort e cleanup | Sì |
| `ds4_gpu_dynamic_arena_request_begin` | CU:16843 / 53 | `ds4_session_sync` | Sì |
| `ds4_gpu_dynamic_arena_observer_preserve_short_suffix` | CU:16908 / 111 | `ds4_session_sync` | Sì |
| `ds4_gpu_dynamic_arena_observer_reset` | CU:17020 / 41 | `ds4_session_sync` | Sì |

### Streaming, mailbox e SPEX

| Simbolo assente upstream | Noi / LOC | Chiamante diretto in `ds4.c` | Entry |
|---|---:|---|:---:|
| `ds4_gpu_async_read_ring_alloc` | CU:17136 / 34 | init SPEX CPU, shared1 e SPEX GPU | Sì |
| `ds4_gpu_async_read_free` | CU:17175 / 25 | release SPEX/shared1 | Sì |
| `ds4_gpu_async_read_host_slot` | CU:17201 / 6 | worker SPEX CPU/shared1, `spex_before_layer` | Sì |
| `ds4_gpu_async_read_ready_slot` | CU:17212 / 14 | score e `spex_before_layer` | Sì |
| `ds4_gpu_async_read_wait_slot` | CU:17231 / 8 | worker SPEX/shared1 | Sì |
| `ds4_gpu_tensor_read_async_slot` | CU:17244 / 38 | `metal_graph_spex_score_next` | Sì |
| `ds4_gpu_tensor_read_async_ordered_slot` | CU:17290 / 35 | scheduler SPEX CPU/shared1 | Sì |
| `ds4_gpu_tensor_write_async_ordered_slot` | CU:17332 / 35 | join shared1/GPU | Sì |
| `ds4_gpu_spex_queue_create` | CU:17500 / 47 | `metal_graph_spex_init` | Sì |
| `ds4_gpu_spex_queue_reset` | CU:17548 / 18 | SPEX disable/inizio token | Sì |
| `ds4_gpu_spex_queue_submit` | CU:17567 / 43 | `metal_graph_spex_before_layer` | Sì |
| `ds4_gpu_spex_queue_destroy` | CU:17634 / 39 | `metal_graph_spex_release` | Sì |
| `ds4_gpu_spex_hidden_score_tensor` | CU:23224 / 22 | `metal_graph_spex_score_next` | Sì |
| `ds4_gpu_spex_hidden_topk_tensor` | CU:23279 / 26 | `metal_graph_spex_score_next` | Sì |
| `ds4_gpu_matmul_f16_indexer_tensor` | CU:23764 / 13 | decode layer e attention batch | Sì |

### Modello, sidecar e configurazione

| Simbolo assente upstream | Noi / LOC | Chiamante diretto | Entry |
|---|---:|---|:---:|
| `ds4_gpu_model_span_cpu_owned` | CU:2217 / 8 | `accelerator_cache_model_tensors` | Sì |
| `ds4_gpu_model_span_release` | CU:9098 / 38 | `metal_graph_shared1_release_spans` | Sì |
| `ds4_gpu_set_mtp_model_map_range` | CU:18002 / 89 | `ds4_engine_open` | Sì |
| `ds4_gpu_set_model_file` | CU:18092 / 49 | `ds4_engine_open` | Sì |
| `ds4_gpu_sparse_bake_set_retained_mask` | CU:18242 / 35 | `ds4_engine_open` | Sì |
| `ds4_gpu_set_iq1_s_sidecar` | CU:18278 / 32 | `ds4_engine_open` | Sì |
| `ds4_gpu_set_q1_0_sidecar` | CU:18311 / 37 | `ds4_engine_open` | Sì |
| `ds4_gpu_set_nested_residual_sidecar` | CU:18349 / 245 | `ds4_engine_open` | Sì |
| `ds4_gpu_model_streaming_begin` | CU:18601 / 16 | `accelerator_cache_model_tensors` | Sì |

### Routing, cache e tiering

| Simbolo assente upstream | Noi / LOC | Chiamante diretto | Entry |
|---|---:|---|:---:|
| `ds4_gpu_reap_router_bias_reset` | CU:18203 / 3 | `ds4_reap_mask_apply` | Sì |
| `ds4_gpu_reap_router_bias_update` | CU:18207 / 34 | `ds4_reap_mask_apply` | Sì |
| `ds4_gpu_moe_route_consumer_done` | CU:33063 / 41 | decode layer e FFN batch | Sì |
| `ds4_gpu_g133_decode_position_begin` | CU:33631 / 12 | decode, MTP e verify | Sì |
| `ds4_gpu_g133_validate_context` | CU:33648 / 12 | `ds4_session_create` | Sì |
| `ds4_gpu_routed_moe_prepare_selected` | CU:46203 / 59 | `metal_graph_encode_decode_layer` | Sì |
| `ds4_gpu_routed_moe_last_selected` | CU:49040 / 14 | observer/SPEX dopo il layer | Sì |
| `ds4_gpu_routed_moe_mixed_q1_0_one_tensor` | CU:54905 / 1227 | `metal_graph_encode_decode_layer` | Sì |
| `ds4_gpu_routed_moe_mixed_iq1_one_tensor` | CU:56133 / 331 | `metal_graph_encode_decode_layer` | Sì |

### KV staged

| Simbolo assente upstream | Noi / LOC | Chiamante diretto | Entry |
|---|---:|---|:---:|
| `ds4_gpu_tensor_alloc_kv_cache` | CU:9923 / 34 | `metal_graph_alloc_raw_cap` | Sì |

### Telemetria

| Simbolo assente upstream | Noi / LOC | Chiamante diretto | Entry |
|---|---:|---|:---:|
| `ds4_gpu_alloc_trace_mark` | CU:917 / 4 | cache modello, init GPU, graph generation | Sì |
| `ds4_gpu_decode_trace_token_begin` | CU:30741 / 74 | `metal_graph_eval_token_raw_swa` | Sì |
| `ds4_gpu_decode_trace_layer_begin` | CU:30816 / 29 | encode/decode layer | Sì |
| `ds4_gpu_decode_trace_layer_end` | CU:30846 / 28 | encode/decode layer | Sì |
| `ds4_gpu_decode_trace_output_begin` | CU:30875 / 17 | encode token | Sì |
| `ds4_gpu_decode_trace_output_end` | CU:30893 / 19 | encode token | Sì |
| `ds4_gpu_decode_trace_split_sync_begin` | CU:30913 / 10 | barriera/split-sync del graph | Sì |
| `ds4_gpu_decode_trace_split_sync_end` | CU:30924 / 14 | barriera/split-sync del graph | Sì |
| `ds4_gpu_decode_trace_token_encoded` | CU:30939 / 16 | fine encode token | Sì |
| `ds4_gpu_decode_trace_sync_complete` | CU:30965 / 55 | completamento graph/sync | Sì |
| `ds4_gpu_decode_trace_logits_begin` | CU:31021 / 10 | produzione logits | Sì |
| `ds4_gpu_decode_trace_logits_end` | CU:31032 / 17 | produzione logits | Sì |
| `ds4_gpu_decode_trace_token_end` | CU:31096 / 59 | `metal_graph_eval_token_raw_swa` | Sì |
| `ds4_gpu_vram_ledger_decode_start` | CU:31778 / 105 | avvio decode/request | Sì |
| `ds4_gpu_vram_ledger_request_end` | CU:31884 / 32 | teardown richiesta | Sì |

Altri entry point esportati, ma non chiamati da `ds4.c`:

| Simbolo | Noi / LOC | Chiamante | Entry `ds4.c` |
|---|---:|---|:---:|
| `ds4_gpu_g130_attribution_request_begin` | CU:5995 / 14 | `ds4_server.c:generate_job` | No |
| `ds4_gpu_g130_attribution_token_begin` | CU:6010 / 13 | `ds4_server.c:generate_job` | No |
| `ds4_gpu_g130_attribution_token_end` | CU:6024 / 70 | `ds4_server.c:generate_job` | No |
| `ds4_gpu_g130_attribution_request_end` | CU:6095 / 55 | `ds4_server.c:generate_job` | No |
| `ds4_gpu_token_watch_begin` | CU:35350 / 21 | guardiano richiesta | No |
| `ds4_gpu_token_watch_end` | CU:35372 / 53 | guardiano richiesta | No |

## 1.2 Controller interni: streaming e cache esperti

Queste sono le unità funzionali da trapiantare; i kernel richiamati sotto ciascun controller devono seguirlo.

| Simbolo | Noi / LOC | Chiamato da | Entry |
|---|---:|---|:---:|
| `cuda_model_file_clear` | CU:6631 / 23 | setup/teardown model file | No |
| `cuda_model_stage_pool_alloc` | CU:6897 / 78 | staging modello | No |
| `cuda_model_stage_read` | CU:8330 / 40 | loader streaming | No |
| `cuda_moe_route_worker_drain_completed` | CU:33010 / 52 | route worker/consumer | No |
| `cuda_moe_route_worker_respawn` | CU:40491 / 88 | recovery route worker | No |
| `cuda_moe_route_pick_slot` | CU:41611 / 21 | route worker | No |
| `cuda_moe_route_copy_h2d_async` | CU:41633 / 53 | route worker | No |
| `cuda_moe_route_publish_append` | CU:41729 / 25 | route worker | No |
| `cuda_moe_demand_pipeline_stage_host` | CU:41822 / 33 | route worker | No |
| `cuda_moe_demand_pipeline_flush` | CU:41856 / 93 | route worker | No |
| `cuda_moe_route_io_qd_read` | CU:42679 / 257 | route worker | No |
| `cuda_moe_route_worker` | CU:44299 / **946** | thread route service | No |
| `cuda_moe_fill_spans_overlapped` | CU:45399 / 115 | selected loader | No |
| `cuda_moe_selected_load` | CU:47127 / **1134** | routed-MoE dispatcher | No |
| `cuda_moe_selected_load_q1_0` | CU:49108 / 391 | percorso Q1 | No |
| `cuda_moe_gpu_resident_routes_begin` | CU:49501 / 387 | routed launch | No |
| `cuda_moe_gpu_resident_routes_finish` | CU:49889 / 524 | routed launch | No |
| `cuda_moe_gpu_resident_routes_submit` | CU:50414 / 24 | routed launch | No |
| `cuda_g73_mailbox_copy` | CU:50439 / 104 | route dispatch G73 | No |
| `cuda_routed_moe_launch_impl` | CU:50545 / **2324** | entry routed-MoE | No |
| `cuda_g73_dispatch_init` | CU:52879 / 88 | routed launch | No |

### Cache VRAM

| Simbolo | Noi / LOC | Chiamato da |
|---|---:|---|
| `cuda_model_pick_victim` | CU:8936 / 32 | vecchio allocator globale |
| `cuda_model_stream_pool_push` | CU:9003 / 13 | allocator globale |
| `cuda_model_stream_pool_take` | CU:9020 / 29 | allocator globale |
| `cuda_model_stream_pool_reclaim` | CU:9052 / 15 | allocator globale |
| `cuda_model_stream_alloc` | CU:9166 / 158 | resolver/streaming generico |
| `cuda_moe_expert_cache_invalidate` | CU:38652 / 69 | lifecycle cache |
| `cuda_moe_expert_cache_release` | CU:39183 / 536 | lifecycle/teardown |
| `cuda_moe_q1_vram_cache_prepare` | CU:39775 / 111 | loader Q1 |
| `cuda_moe_q1_vram_cache_resolve` | CU:39888 / 55 | routed Q1 |
| `cuda_moe_prefill_vram_seed` | CU:40096 / 388 | prefill ranked |
| `cuda_moe_expert_cache_prepare` | CU:40580 / **994** | route worker/tiering |
| `cuda_moe_expert_cache_find` | CU:41575 / 15 | selected loader |
| `cuda_moe_expert_cache_lru_slot` | CU:41591 / 19 | victim selection |
| `cuda_moe_iq1_vram_cache_prepare` | CU:45666 / 62 | loader IQ1 |
| `cuda_moe_iq1_vram_cache_resolve` | CU:45731 / 47 | routed IQ1 |

## 1.3 Arena dinamica

| Simbolo/controller | Noi / LOC | Chiamato da |
|---|---:|---|
| `cuda_dynamic_arena_slot_reader_acquire` | CU:2387 / 26 | resolver e route reader |
| `cuda_dynamic_arena_slot_reader_release` | CU:2414 / 10 | reader teardown |
| `cuda_dynamic_arena_slot_writer_try_acquire` | CU:2425 / 15 | transaction begin |
| `cuda_dynamic_arena_slot_writer_release` | CU:2441 / 10 | commit/abort |
| `cuda_dynamic_arena_fnv1a64_continue` | CU:10049 / 10 | checksum WRAP |
| `cuda_dynamic_arena_copy_expert_async` | CU:10073 / 114 | arena loader |
| `cuda_dynamic_arena_storage_release` | CU:10188 / 41 | arena teardown |
| `cuda_dynamic_arena_begin_internal` | CU:11426 / 254 | `ds4_gpu_dynamic_arena_begin` |
| `cuda_dynamic_arena_finish_load_impl` | CU:11692 / 44 | finish/commit |
| `cuda_dynamic_arena_dual_sparse_stage` | CU:12101 / 183 | IQ1/Q1 dual source |
| `cuda_dynamic_arena_dual_sparse_commit` | CU:12285 / 80 | publish dual source |
| `cuda_dynamic_arena_wrap_build_source_parts` | CU:12546 / 86 | WRAP scheduler |
| `cuda_dynamic_arena_part_copy_worker` | CU:12785 / 121 | WRAP copy workers |
| `cuda_dynamic_arena_copy_phase_file_qd` | CU:12938 / 138 | WRAP file queue |
| `cuda_dynamic_arena_checksum_worker` | CU:13084 / 19 | WRAP verification |
| `cuda_dynamic_arena_verify_worker` | CU:14741 / 33 | post-load verify |
| `cuda_dynamic_arena_observer_finalize_preloads` | CU:14775 / 104 | ranked prefill |
| `cuda_dynamic_arena_observer_publish` | CU:14928 / 60 | request boundary |
| `cuda_dynamic_arena_observer_mirror_ptr` | CU:14989 / 102 | observer/prefill |
| `cuda_dynamic_arena_observe_selected` | CU:17062 / 73 | routed-MoE observer |

L’arena core è separabile. Non lo sono invece, come blocco funzionale completo, `observer → ranked prefill → tiering → route worker`.

## 1.4 Tiering, promozione, vittime

| Simbolo/controller | Noi / LOC | Chiamato da |
|---|---:|---|
| `cuda_moe_prefill_router_mask_publish_candidate` | CU:16009 / 141 | prefill observer |
| `cuda_moe_prefill_router_mask_finalize` | CU:16151 / 464 | fine prefill |
| `cuda_moe_tiering_admission_gate` | CU:34044 / 15 | prepare/enforce |
| `cuda_moe_tiering_report_reset` | CU:34084 / 208 | request boundary |
| `cuda_moe_tiering_prepare` | CU:34362 / 531 | inizio request |
| `cuda_moe_promotion_record_context` | CU:35782 / 66 | promotion ledger |
| `cuda_moe_tiering_observe_route` | CU:38151 / 52 | routed execution |
| `cuda_moe_stage_observed_cold_to_2bit_ram` | CU:38354 / 237 | promotion RAM |
| `cuda_moe_mass_lfru_score` | CU:41950 / 10 | victim selection |
| `cuda_moe_tiering_pick_vram_slot` | CU:41977 / 222 | reservations |
| `cuda_moe_tiering_commit_reservations` | CU:42200 / 65 | route worker |
| `cuda_moe_tiering_refund_failed` | CU:42266 / 30 | failure path |
| `cuda_moe_tiering_finish_reservations` | CU:42555 / 62 | publish/abort |
| `cuda_moe_tiering_enforce_request` | CU:43092 / **1206** | `cuda_moe_route_worker` |

`cuda_moe_tiering_enforce_request`, cache esperti e route worker sono **inseparabili a runtime**. Si possono implementare in quest’ordine, ma non validare separatamente come feature.

## 1.5 Guardiani

| Simbolo/controller | Noi / LOC | Chiamato da |
|---|---:|---|
| `cuda_transient_deadline_policy_get` | CU:32005 / 36 | route worker |
| `cuda_transient_deadline_budget` | CU:32041 / 9 | route worker |
| `cuda_transient_deadline_note` | CU:32089 / 40 | retry/timeout |
| `cuda_transient_deadline_replace_io` | CU:32135 / 96 | recovery |
| `cuda_transient_deadline_terminal_drain` | CU:32232 / 37 | teardown |
| `cuda_moe_transient_pread_chunked` | CU:32405 / 150 | transient loader |
| `cuda_moe_timeout_cancel_fallback` | CU:32571 / 19 | deadline failure |
| `cuda_moe_retry_slot` | CU:32593 / 45 | route worker |
| `cuda_moe_fallback_serve` | CU:32655 / 102 | degradazione controllata |
| `cuda_moe_route_worker_cancel_join` | CU:32933 / 76 | teardown |
| `cuda_moe_route_io_qd_cancel_pending` | CU:42659 / 20 | cancellation |
| `cuda_g73_terminal_classify` | CU:48280 / 25 | terminal outcome |
| `cuda_g73_terminal_read` | CU:48306 / 29 | terminal outcome |
| `cuda_g73_terminal_exact_outcomes` | CU:48365 / 116 | terminal outcome |
| `cuda_g73_terminal_commit` | CU:48492 / 48 | publish/teardown |

I guardiani **non sono un modulo autonomo**: dipendono dalla semantica precisa degli slot, dalle reservation del tiering, dal cancellable I/O e dal lifecycle del worker.

## 1.6 Windows e I/O

Upstream non ha `src/platform`. Questa è la parte più indipendente.

| Simbolo | File / LOC | Chiamato da | Entry `ds4.c` |
|---|---:|---|:---:|
| `os_file_init` | OF:70 / 10 | model/session init | Sì |
| `os_file_valid` | OF:79 / 8 | I/O helpers | No |
| `os_file_open_read` | OF:88 / 34 | model open | Sì |
| `os_file_dup` | OF:123 / 22 | worker handles | No |
| `os_file_reopen_read_sequential` | OF:146 / 36 | sequential loader | No |
| `os_fopen` | OF:183 / 20 | file users in `ds4.c` | Sì |
| `os_file_close` | OF:204 / 10 | teardown | Sì |
| `os_file_size` | OF:215 / 18 | model validation | Sì |
| `os_pread_cancellable_init` | OF:234 / 11 | route worker | No |
| `os_pread_cancellable_prepare` | OF:246 / 15 | OVERLAPPED request | No |
| `os_pread_cancellable_pending` | OF:262 / 26 | worker polling | No |
| `os_pread_cancellable_destroy` | OF:289 / 27 | worker teardown | No |
| `os_pread_cancel` | OF:329 / 21 | deadline guardian | No |
| `os_pread_cancellable_timeout` | OF:351 / 191 | route worker | No |
| `os_pread_cancellable` | OF:543 / 6 | loader | No |
| `os_pread_cancellable_max_chunk` | OF:550 / 23 | chunk policy | No |
| `os_pread_plain` | OF:574 / 31 | fallback | No |
| `os_pread` | OF:606 / 63 | tutti i loader | No |
| `os_mmap_init` | MM:13 / 21 | engine/model init | Sì |
| `os_mmap_open_read` | MM:27 / 48 | model mapping | Sì |
| `os_mmap_close` | MM:76 / 14 | teardown | Sì |
| `os_mmap_warm` | MM:91 / 10 | preload | Sì |
| `os_mmap_cold` | MM:102 / 13 | eviction hint | No |
| `os_once` | TH:23 / 3 | init globals | Sì |
| `os_thread_create` | TH:37 / 13 | worker creation | Sì |
| `os_thread_join` | TH:51 / 4 | teardown | Sì |
| `os_thread_join_timeout` | TH:56/76 / 6/23 | guarded teardown | No |
| `os_cpu_count` | TH:67 / 5 | worker sizing | Sì |

Upstream usa ancora `pread` direttamente in `UCU:1550`, `UC:18349` e `UC:47573`.

## 1.7 Telemetria interna

| Famiglia | Simboli/controller principali | Intervallo nostro | Dipendenza |
|---|---|---:|---|
| Worker-prof | `cuda_workerprof_*`, start/stop, pickup, idle, report | CU:5167–5515 | thread + clock |
| G130 attribuzione | init, token switch/restore, request/token begin/end | CU:5941–6149 | server/request |
| Transport ledger | H2D begin/append/finish, deferred, snapshot/report | CU:28956–29431 | route worker |
| Decode trace | init/flush/NVTX/token/layer/logit events | CU:30102–31154 | graph hooks |
| VRAM ledger | log/decode start/request end | CU:31675–31915 | alloc/cache |
| Zero-copy | init, touch, admissible, report | CU:35060–35315 | loader/cache |

È separabile come infrastruttura, ma i punti di misura vanno inseriti assieme ai rispettivi owner. Non deve diventare una dipendenza di correttezza.

# 2. Grafo e ordine di trapianto

```text
ABI upstream + guard single-GPU
              │
              ├──────────────► telemetria di base
              │
Windows/I/O ──┴─► model-file/loader selettivo
                         │
                         ▼
                  arena dinamica core
                         │
                         ▼
             cache VRAM esperti/publish
                         │
                         ▼
        tiering + promozione + mass-LFRU
                         │
                         ▼
          route worker + mailbox + dispatcher
                         │
                         ▼
       deadline/cancel/respawn/terminal guardians
                         │
                         ▼
       IQ1/Q1/nested residual/SSD rotation
```

Rami laterali:

```text
ABI tensor ─► async readback/SPEX ─► dispatcher
ABI tensor ─► KV staged ─► firme attention ─► guardians
arena + cache + dispatcher + guardians ─► G132 CPU lane
```

## Ordine operativo

| Ordine | Blocco | Perché viene qui | Può funzionare isolato? |
|---:|---|---|---|
| 0 | Contratto upstream: `device_id`, resolver, firme, guard `g_n_gpus==1` | Impedisce che il fork contamini multi-device/GLM/TP/EP | Sì |
| 1 | `os_file`, cancellable `pread`, mmap, thread | Nessuna dipendenza CUDA; serve a tutti i loader | **Sì** |
| 2 | Telemetria passiva: alloc, hostpin, worker-prof, transport ledger | Consente di misurare i blocchi successivi | Sì, runtime-off |
| 3 | Adattatore dietro `ds4_gpu_stream_expert_cache_*` upstream | Riusa il control plane upstream già chiamato da `ds4.c` | Sì, loader semplice |
| 4 | Arena core: slot, transaction, wrap, checksum, snapshot | Dipende solo da file/model layout | **Sì**, con fixture |
| 5 | Async readback/SPEX e observer prefill/REAP | Richiede ABI tensor stabile e arena | Parzialmente |
| 6 | Cache VRAM esperti, capacity, eviction, publish | Consuma arena e loader selettivo | Parzialmente |
| 7 | Tiering/promozione/G133, admission, knocks, mass-LFRU | Richiede identità esperto e lifecycle cache | No |
| 8 | Route worker, mailbox, selected-load, seam routed-MoE | Integra tutti i blocchi precedenti | Primo end-to-end |
| 9 | Guardiani G73: deadline, cancel, retry, respawn, terminal | Deve conoscere gli stati reali del worker | No |
| 10 | IQ1/Q1/nested residual/SSD rotator | Percorso grande e quantizzazione-specifico | No |
| 11 | KV staged e G132 CPU lane | Collidono con attention e dispatcher; non bloccano il porto base | No |

Blocchi non separabili:

| Blocco intrecciato | Motivo |
|---|---|
| `route_worker + expert_cache + tiering_enforce_request` | Reservation, victim, publish e refund condividono lo stesso stato |
| `deadline + cancellable I/O + worker teardown` | Il timeout corretto dipende dalla proprietà dello slot e dall’OVERLAPPED pendente |
| Q1 mixed + nested residual + SSD rotator | Il resolver restituisce parti provenienti da tier diversi nella stessa chiamata |
| G132 + reservation + dispatcher | Il CPU lane usa claim/rollback del medesimo request state |
| Observer + ranked prefill + REAP | La graduatoria senza le osservazioni del router non ha semantica |

# 3. Collisioni

Misura basata sull’intersezione dei contesti di hunk modificati dalla base `8809b90`:

| File | Hunk nostri | Hunk upstream | Zone comuni |
|---|---:|---:|---:|
| `ds4.c` | 89 | 361 | **69** |
| `ds4_cuda.cu` | 251 | 193 | **164** |
| `ds4_gpu.h` | 14 | 46 | **8** |
| `ds4_metal.m` | 9 | 201 | **8** |

Le estensioni sono ortogonali per quantità di codice, ma non per punti d’integrazione.

| Collisione | Upstream | Nostro fork | Decisione |
|---|---|---|---|
| `ds4_gpu_tensor` | `ds4_gpu_mgpu.h:39`: `{ptr, bytes, owner, device_id}`; alloc/view/free/read/write/copy device-aware | CU:1040: `{ptr, host_ptr, bytes, owner}`; `host_ptr` alimenta KV/readback | **Conciliabile**: struttura upstream, aggiunta controllata di `host_ptr`; mai perdere `device_id` |
| Resolver pesi | UCU:541 `cuda_model_range_ptr`; UCU:728 `cuda_resolve_weight_ptr`, tier/device-aware | CU:4379 resolver globale + CU:9166 allocator streaming | Upstream primario. Il fallback fork solo nel ramo single-GPU |
| `set_model_map_range` | UH:98 aggiunge `max_tensor_bytes` e supporta span/multi-device | H:208 firma più vecchia | Tenere firma upstream; aggiungere solo registrazione file/host range |
| Cinque attention | UH:1677,1818,1840,1862,1901 aggiungono `comp_kv_f16` e nuovi layout | H:673,718,739,760,775 hanno hook staged-KV ma firma vecchia | Tenere corpo/firma upstream; staged-KV come early branch strettamente sorvegliato |
| Due router | UH:2049/2068: `n_expert`, `n_expert_used`, `expert_weight_scale`; resolver per tier | H:847/864: `layer_index`, usato da REAP/bias/trace | **Conciliabile**: firma upstream + contesto `layer_index`; eliminare assunzioni pubbliche 256/6/1.5 |
| Routed-MoE one | UH:2309: `n_total_expert`, `n_expert`, `add_in`, `force_resident`, `layer_index` | H:882: G133 epoch, SPEX queue/key, pipeline selettiva | Conservare contratto upstream; servizio fork come fast path single-GPU prima del fallback upstream |
| Routed-MoE batch | UH:2339: generalità expert/count e `force_resident` | H:1006: probabilità, mid-path, layer context | Stessa soluzione; non sostituire il dispatcher |
| Dispatcher `ds4.c` | UC:22785–23650 e UC:39643–39792: tier placement, TP/EP, cross-device reduction, GLM | C:14354–14528: sidecar, G133, SPEX, G132 | Hook solo nel leaf DSV4 single-GPU, dopo la scelta di placement upstream |
| Streaming cache | UCU:22953 loader selettivo compatto, API usata estesamente da `UC` | Cache persistente, LFRU, promozione, worker asincrono | Innestare il backend fork dietro l’API upstream |
| `pread` | Upstream usa POSIX diretto | Abstraction Windows + cancellazione OVERLAPPED | Portare prima l’astrazione; non riscrivere subito le letture upstream estranee allo streaming |
| Allocazione KV | Upstream UCU:2480–2511 ha policy managed/device-aware | CU:9881/9923 aggiunge `host_ptr` e ring staged | Conservare policy upstream; allocatore staged dedicato costruito su `*_managed_on` |
| Metal | Upstream ha 201 hunk e API multi-device/GLM | Nostri stub seguono API vecchie | Non trapiantare funzioni Metal; aggiungere solamente no-op per nuove API |

La collisione routed-MoE è la più costosa. Sei soli owner coinvolti valgono **7.831 LOC verificate**:

| Owner | LOC |
|---|---:|
| `cuda_moe_route_worker` | 946 |
| `cuda_moe_selected_load` | 1134 |
| `cuda_moe_tiering_enforce_request` | 1206 |
| `cuda_moe_expert_cache_prepare` | 994 |
| `ds4_gpu_routed_moe_mixed_q1_0_one_tensor` | 1227 |
| `cuda_routed_moe_launch_impl` | 2324 |

Questo conferma che il porto selettivo è corretto, ma deve essere trattato come integrazione di sottosistemi, non come copia di singole funzioni.

# 4. Cosa buttare o non trapiantare

| Componente nostro | Evidenza upstream | Decisione |
|---|---|---|
| “Riempire il buco Q4_K” | Nostro `CU`: **0** occorrenze. Upstream: **7**; kernel a UCU:18061 e 18932, dispatch UCU:20838–21832 | **Buttare l’idea intera**. Upstream vince |
| Vecchie firme e corpi delle attention | Upstream aggiunge `comp_kv_f16`, layout tier/device e varianti GLM | Non portare; solo hook staged-KV |
| Vecchi router con contratto fisso | Upstream passa esplicitamente numero esperti, top-k e scale | Non portare come API; conservare solo bias/REAP per-layer |
| Corpi routed-MoE generali | Upstream gestisce `n_total_expert`, `add_in`, `force_resident`, TP/EP | Non sostituire; innestare il servizio fork |
| Alloc/view/free/read/write/copy tensor | Upstream è device-aware e costituisce il plumbing multi-device | **Scartare le nostre versioni generiche** |
| Resolver globale `cuda_model_range_ptr` come autorità | Upstream ha `cuda_resolve_weight_ptr` per tier | Scartare come resolver principale |
| Allocator globale G6: `cuda_model_pick_victim`, stream pool, `cuda_model_stream_alloc` | Upstream ha placement modello più cache selettiva esperti | Non portare inizialmente; mantenere solo se emerge un consumatore non-esperto verificato |
| Seconda API pubblica cache esperti | `UH:146–205`; `UC` la usa in decine di punti | Non crearla. Implementare il nostro backend dietro questa superficie |
| Budget/hotness upstream CUDA come implementazione | UCU:27260 restituisce 0; UCU:27380–27398 contiene no-op | Non va “buttato” il nostro algoritmo: va usato per completare questi hook upstream |
| Loader selettivo upstream | UCU:22953–23087 deduplica esperti, compatta e carica gate/up/down; già limita `g_n_gpus != 1` | Conservare come fallback/base; estendere con arena/cache persistente |
| Policy generica `ds4_gpu_graph_tensor_device_requested` | Upstream sceglie managed/device per tier | Scartare; mantenere solo `host_ptr` per le allocazioni staged esplicite |
| Stub Metal del fork | API upstream molto più ampia e diversa | Scartare; rigenerare solo gli stub additivi |
| `cuda_dynamic_arena_trim_process_working_set` e trim globale WRAP | Cronologia del fork: esperimento “reject global WRAP working-set trim” | Non portare |
| Secondo pass checksum globale | Il design corrente dispone già del checksum per-worker/trusted worker checksum | Non portare pass ridondanti |
| Prototipo mailbox precedente | Cronologia: “remove rejected router mailbox prototype” | Non resuscitare |
| Cache residente layer-local precedente | Cronologia: “reject layer-local resident expert cache” | Non portare |
| Catena CPU Q4_K/MTP del fork | `C:2429`, `6885`, `6901`, `7132`, `9563–9898`; upstream ha GPU Q4_K e MTP più generale | **Defer/scarto probabile**, ma richiede confronto numerico MTP prima della rimozione definitiva |

Nota importante sulla cache upstream: non è soltanto una superficie vuota. `cuda_stream_selected_cache_begin_load` a UCU:22953–23087:

- deduplica gli ID selezionati;
- alloca buffer compatti gate/up/down;
- effettua le copie selettive;
- costruisce la remap degli slot;
- conserva `device_id`;
- rifiuta esplicitamente il multi-GPU.

Però budget, hotness e seed sono ancora stub/no-op a UCU:27260–27431. Quello è esattamente il punto naturale in cui innestare arena, cache e tiering del fork.

# Stima aggiornata

Questa parte è **stima**, non misura.

| Milestone | Stima |
|---|---:|
| ABI/guard, Windows I/O, cache API adapter | 3–4 gg |
| Arena core + fixture | 3–4 gg |
| Cache VRAM + tiering/promozione | 5–7 gg |
| Route worker + dispatcher routed-MoE | 4–6 gg |
| Guardiani + teardown | 2–3 gg |
| Controllo numerico single-GPU | 2–3 gg |
| Totale core single-GPU | **19–27 gg** |
| Q1/IQ1/nested residual completo | +3–5 gg |
| KV staged + G132 CPU lane | +4–7 gg |

Quindi la vecchia stima **18–25 giorni resta plausibile solo per il core single-GPU**, escludendo dal primo traguardo KV staged, G132 e parte del percorso sidecar avanzato. Per piena parità del working tree corrente stimerei **26–36 giornate**.

La prima milestone pianificabile è: upstream invariato per multi-device, loader selettivo upstream funzionante, arena e cache del fork abilitate esclusivamente sul ramo DSV4 single-GPU, con fallback immediato al routed-MoE upstream.

Codex session ID: 019fbc41-9008-7782-b0e2-b24270570e2b
Resume in Codex: codex resume 019fbc41-9008-7782-b0e2-b24270570e2b
