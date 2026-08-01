# NUCLEO 6-7-8 — inventario del fork, recuperato

**1/8.** L'agente di progetto ha completato l'ispezione (386.000 token) ma **non ha potuto
scrivere il rapporto**: il mandato gli chiedeva di scrivere in `ds4-port\docs\porto\`, fuori
dalla sua radice scrivibile. Errore nel mandato, non dell'agente. Questo file recupera cio' che
aveva gia' trovato, dal suo log.

> **Regola che ne esce**: la destinazione di scrittura di un mandato deve stare **dentro** la
> radice passata a `-C`. Sotto `-s workspace-write` tutto il resto e' negato, e l'agente se ne
> accorge solo alla fine, quando il lavoro e' gia' fatto.

## Le 164 funzioni del nucleo, con la riga nel fork

Sono in `ds4-p4a/ds4_cuda.cu`. Servono ai blocchi 6, 7, 8 e 9: cache VRAM, tiering, route
worker, guardiani.

```
31922    cuda_moe_route_memory_barrier
31935    cuda_g133_rotator_io_timeout_seconds
31956    cuda_g133_transient_io_timeout_seconds
31988    cuda_moe_transient_deadline_env_seconds
32041    cuda_moe_transient_deadline_budget_seconds
32051    cuda_moe_transient_deadline_from_now
32056    cuda_moe_transient_deadline_backoff
32080    cuda_moe_transient_deadline_worker_request_begin
32089    cuda_moe_transient_deadline_note
32135    cuda_moe_transient_deadline_replace_io_and_staging
32232    cuda_moe_transient_deadline_terminal_drain
32270    cuda_moe_route_read_whole_requested
32279    cuda_moe_route_prefetch_hint_requested
32303    cuda_moe_route_prefetch_add_range
32320    cuda_moe_route_prefetch_hint
32399    cuda_moe_route_prefetch_hint
32405    cuda_moe_transient_pread_chunked
32571    cuda_moe_transient_timeout_cancel_for_fallback
32593    cuda_moe_transient_prepare_retry_slot
32655    cuda_moe_transient_timeout_fallback_serve
32758    cuda_moe_route_mailbox_fail_closed
32789    cuda_moe_route_mailbox_worker_claim
32859    cuda_moe_route_mailbox_publish_upload
32880    cuda_moe_route_worker_publish_completed
32895    cuda_moe_route_upload_stream_quiesce
32929    cuda_moe_drain_overlap4_decide_pending_joined
32933    cuda_moe_route_worker_cancel_and_join
33010    cuda_moe_route_worker_drain_completed
33105    cuda_moe_gpu_routes_requested
33124    cuda_moe_split_hit_miss_requested
33129    cuda_moe_split_fused_requested
33134    cuda_moe_route_no_default_sync_requested
33139    cuda_moe_resolver_priority_stream_requested
33148    cuda_moe_resolver_priority_timing_retire
33171    cuda_moe_route_packed_copy_requested
33176    cuda_moe_route_batched_publish_requested
33181    cuda_moe_demand_pipeline_requested
33186    cuda_moe_demand_pipeline_environment_valid
33199    cuda_g73_host_selected_reuse_requested
33204    cuda_g73_route_io_qd_requested
33252    cuda_moe_prefill_vram_seed_per_layer_requested
33284    cuda_moe_prefill_vram_seed_total_requested
33301    cuda_moe_prefill_vram_seed_floor_per_layer_requested
33317    cuda_moe_expert_cache_requested
33328    cuda_moe_expert_cache_layer_top1
33333    cuda_moe_expert_cache_stats_interval
33345    cuda_moe_expert_cache_reserve_bytes
33359    cuda_moe_tiering_mode_requested
33378    cuda_moe_tiering_policy_requested
33390    cuda_g133_bool_env
33405    cuda_moe_prefill_tier_compose_requested
33415    cuda_moe_prefill_tier_router_open_requested
33425    cuda_moe_prefill_tier_reserve_slots_requested
33442    cuda_moe_tiering_u32_env
33508    cuda_moe_tiering_double_env
33590    cuda_moe_tiering_adaptive_budget_requested
33605    cuda_moe_tiering_double_env
33627    cuda_moe_tiering_entry_index
33644    cuda_g133_epoch_valid
33661    cuda_g133_advisory_fields_from_epoch
33672    cuda_g133_advisory_same_epoch
33679    cuda_g133_advisory_epoch_after
33691    cuda_g133_advisory_elapsed
33704    cuda_g133_advisory_epoch_consecutive
33711    cuda_g133_advisory_age_add
33718    cuda_g133_advisory_current_snapshot
33735    cuda_g133_consecutive_streak
33742    cuda_g133_consecutive_streak_at
33753    cuda_g133_advisory_heat
33768    cuda_g133_mark_promotion
33791    cuda_g133_ram_candidate
33798    cuda_g133_ram_candidate_relaxed
33804    cuda_g133_vram_candidate
33812    cuda_g133_demotion_eligible_at
33833    cuda_g133_update_entry_candidate_state
33843    cuda_g133_refresh_entry
33850    cuda_g133_record_observation
33910    cuda_g133_decayed_heat
33917    cuda_g133_ram_demotion_eligible
33924    cuda_g133_advisory_budget_refresh
33944    cuda_g133_advisory_budget_reserve
33959    cuda_g133_advisory_budget_refund
33968    cuda_moe_tiering_lfru
33974    cuda_moe_tiering_admit_adjust_threshold
33991    cuda_moe_tiering_admit_refresh_window
34035    cuda_moe_tiering_admit_note
34044    cuda_moe_tiering_admit_gate
34060    cuda_moe_tiering_clear_owned_slots
34084    cuda_moe_tiering_report_and_reset
34293    cuda_moe_tiering_request_boundary_reset
34308    cuda_moe_tiering_reserve_open_router_slots
34362    cuda_moe_tiering_prepare
34897    cuda_moe_tiering_snapshot_ram_ptrs
34930    cuda_moe_tiering_ram_ptrs
35060    cuda_moe_zerocopy_now_ms
35065    cuda_moe_zerocopy_parse_u64_env
35085    cuda_moe_zerocopy_init
35159    cuda_moe_zerocopy_note_request
35186    cuda_moe_zerocopy_touch
35202    cuda_moe_zerocopy_pointers_admissible
35259    cuda_moe_zerocopy_report
35426    cuda_moe_tiering_has_exact_vram
35448    cuda_moe_tiering_pick_ram_slot
35563    cuda_moe_tiering_pick_ram_slot_admit
35849    cuda_g73_io_deadline
35868    cuda_g73_finish_launched_copy
35891    cuda_g73_open_rotation_record_context_init
37334    cuda_g73_open_maybe_schedule_rotation
37716    cuda_moe_transient_read_publish_once
37773    cuda_moe_tiering_admission_pread
37839    cuda_moe_tiering_load_to_ram
38127    cuda_moe_tiering_log_route_ids
38151    cuda_moe_tiering_observe_route
38220    cuda_moe_tiering_advance_call_tick
38354    cuda_moe_tiering_stage_observed_quant_cold_to_2bit_ram
38592    cuda_moe_tiering_stage_iq1_cold_to_2bit_ram
38618    cuda_moe_tiering_demote_cache_entry
38652    cuda_moe_expert_cache_invalidate
38896    cuda_moe_drain_overlap4_requested
38905    cuda_moe_drain_overlap4_events_ready
38914    cuda_moe_drain_overlap4_events_create
38934    cuda_moe_drain_overlap4_events_destroy
38950    cuda_moe_drain_overlap4_outstanding
38960    cuda_moe_drain_overlap4_retire
38989    cuda_moe_drain_overlap4_poll
39014    cuda_moe_drain_overlap4_retire_at_claim
39035    cuda_moe_drain_overlap4_decide_pending_joined
39063    cuda_moe_drain_overlap4_tail_retire
39100    cuda_moe_drain_overlap4_note_arm_veto
39119    cuda_moe_drain_overlap4_consumer_fence
39150    cuda_moe_drain_overlap4_consumer_sync_enter
39156    cuda_moe_drain_overlap4_consumer_sync_exit
39175    cuda_moe_teardown_leak_residual
39183    cuda_moe_expert_cache_release
39944    cuda_moe_gather_release
40096    cuda_moe_prefill_vram_seed
40491    cuda_moe_route_worker_respawn
41575    cuda_moe_expert_cache_find
41591    cuda_moe_expert_cache_lru_slot
41611    cuda_moe_route_worker_pick_slot
41633    cuda_moe_route_copy_expert_h2d_async
41687    cuda_moe_route_legacy_copy_expert_h2d_async
41729    cuda_moe_route_publish_batch_append
41757    cuda_moe_route_publish_batch_append_host
41779    cuda_moe_route_publish_batch_flush
41816    cuda_moe_demand_pipeline_batch_init
41822    cuda_moe_demand_pipeline_stage_host
41856    cuda_moe_demand_pipeline_flush
41950    cuda_moe_tiering_mass_lfru_score
41977    cuda_moe_tiering_pick_vram_slot
42200    cuda_moe_tiering_commit_vram_reservations
42266    cuda_moe_tiering_refund_failed_promotions
42328    cuda_moe_route_failure_scoped_sign
42346    cuda_moe_route_failure_scoped_consume
42352    cuda_moe_tiering_scoped_invalidate
42459    cuda_moe_drain_overlap4_arm
42555    cuda_moe_tiering_finish_vram_reservations
42617    cuda_g73_classify_request
42642    cuda_g73_publish_pending_outcomes
42659    cuda_moe_route_io_qd_cancel_pending
42679    cuda_moe_route_io_qd_read
43092    cuda_moe_tiering_enforce_request
45245    cuda_moe_expert_cache_copy_to_compact_async
50439    cuda_g73_copy_selected_from_route_mailbox
```

## I quattro contratti statici del fork FALLISCONO tutti

L'agente ha eseguito i test statici in `ds4-p4a/tests/`. **Nessuno passa:**

```
test_g133_m1_static.ps1                 route worker must consume only its immutable
                                        request epoch snapshot
test_g73_open_static.ps1                OFF resolver no longer uses its original
                                        synchronization
test_p4a_demand_pipeline_static.ps1     missing flush contract:
                                        batch->publish.count != request.miss_count
test_prep6_route_read_whole_static.ps1  read contract missing:
                                        cuda_wall_sec() >= absolute_deadline
```

### Il quarto e' un test STANTIO, non un contratto rotto — verificato

```
il test cerca      'cuda_wall_sec() >= absolute_deadline'   tests/...:57
il sorgente ha     cuda_wall_sec() >= read_deadline         ds4_cuda.cu:32437
                   double read_deadline = absolute_deadline;        :32419
                   if (adaptive && absolute_deadline >= 0.0) {      :32420
```

**E' stata la nostra stessa leva `DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE`** — promossa il 31/7 —
a introdurre la variabile locale. Il contratto e' rispettato, il test cerca il nome vecchio.

**Gli altri tre non sono stati verificati**: vanno letti allo stesso modo prima di
concludere qualcosa.

### Perche' conta per il PORTO, non solo per il fork

Questi quattro test sono **esattamente gli invarianti che i blocchi 7, 8 e 9 devono
preservare**: epoca immutabile del route worker, sincronizzazione del resolver, contratto di
flush della pipeline, deadline della lettura. Erano il cancello naturale del trapianto.

**Un cancello che fallisce sempre non e' un cancello.** Vanno riparati *prima* che il nucleo
arrivi, altrimenti nel porto non avremo modo di distinguere un trapianto corretto da uno rotto.
