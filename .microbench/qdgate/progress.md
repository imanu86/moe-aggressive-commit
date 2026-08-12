# QD gate work log

## 2026-07-28T07:26:36.7704040+02:00 — pre-change verification

- Scope: `ds4-p4a/ds4_cuda.cu`.
- The deep-read implementation owns no G73-only resource. Its state is stored in
  the general `cuda_moe_expert_cache`: four Windows `OVERLAPPED` values, four
  events, counters, the existing per-route pinned host staging, and the general
  transient-read cancellation/deadline fields.
- `cuda_moe_route_io_qd_read` reads from the general `g_model_file`, writes the
  supplied general route staging spans, and uses the request sequence/deadline.
  It does not reference the G73 terminal, G73 buffers, or G73 outcomes.
- The G73 dependency is the enclosing `if constexpr (G73)` at current
  `ds4_cuda.cu:38420`; it was introduced together with the QD implementation in
  commit `8ec491b175406c9f95b380b65ab0da5ebdc589ec`, alongside the
  G73-specific env name and startup log. No code comment or commit message
  records a stronger data-structure dependency.
- Real preconditions retained: QD request equals 4, valid model file, composed
  tiering is absent or router-open, layer is not nested residual, valid routes,
  valid experts/ranges, and initialized QD events.
- Decision: treat the G73 gate as historical/experimental ownership and open it
  only behind the new opt-in `DS4_CUDA_ROUTE_IO_QD_ALLOW_NO_G73=1`.
- Starting binary:
  `ds4-p4a/build-native/ds4_server.exe`
  SHA256 `86E66F0C5482498B6D6AF1D9F876DE587D22F02D9401B5562CF84510A1E59EB1`.
- Backup:
  `ds4-p4a/build-native/ds4_server.pre_qdgate.exe`
  SHA256 `86E66F0C5482498B6D6AF1D9F876DE587D22F02D9401B5562CF84510A1E59EB1`.
- `GO_BUILD` is absent; no build started.

## 2026-07-28T07:29:22.1000418+02:00 — patch and static checks

- Added the exact opt-in `DS4_CUDA_ROUTE_IO_QD_ALLOW_NO_G73`.
- Parser accepts only unset/empty/`0` (disabled) and `1` (enabled); invalid
  values warn and remain disabled.
- Cached the opt-in in `cuda_moe_expert_cache`, including release reset,
  cache-reuse comparison, and allocation-time publication.
- Replaced only the historical compile-time wrapper with
  `if (G73 || cache->route_io_qd_allow_no_g73)`.
- The inner QD=4, valid-file, composed/router-open, non-nested, plan/range, and
  event checks are unchanged.
- Default behavior is preserved: with the new flag unset or `0`, the G73-off
  specialization cannot enter QD; the original G73 startup log is also retained.
- Static checks passed:
  - `.microbench/qdgate/test_qdgate_static.ps1`
  - `tests/test_p4a_demand_budget_static.ps1`
  - `tests/test_p4a_demand_pipeline_static.ps1`
  - `tests/test_prep6_route_read_whole_static.ps1`
- No `ds4_server` process was started or observed by the test harness.
- `git diff --check -- ds4_cuda.cu` passed.

## 2026-07-28T07:30 external build-tree mutation

- `GO_BUILD` remained absent and this task did not invoke a compiler or build.
- `ds4-p4a/build-native/ds4_server.exe` changed externally at
  `2026-07-28T07:27:25.4743699+02:00` to SHA256
  `F13536388CFB4BA870FF61442E41B91A2B8A20D4DB9A8B4899F2EC210C8DFA9B`.
- `.ninja_log` also gained a CUDA compilation/link cycle, consistent with an
  external build while the machine was not yet released.
- The immutable task backup still has SHA256
  `86E66F0C5482498B6D6AF1D9F876DE587D22F02D9401B5562CF84510A1E59EB1`.
- No overwrite or restoration was attempted.

## 2026-07-28T07:32:35.6863152+02:00 — build semaphore poll

- `GO_BUILD` is still absent after the requested 120-second interval.
- No build or compiler was invoked.

## 2026-07-28T07:35:07.5394196+02:00 — build semaphore poll

- `GO_BUILD` is still absent after the next 120-second interval.
- No build or compiler was invoked.

## 2026-07-28T07:37:26.5711834+02:00 and 07:39:42.8063759+02:00

- Two further 120-second polls found `GO_BUILD` absent.
- No build or compiler was invoked.

## 2026-07-28T07:42:07.0693555+02:00 and 07:44:24.7145069+02:00

- Two further 120-second polls found `GO_BUILD` absent.
- No build or compiler was invoked.

## 2026-07-28T07:46:48.4998100+02:00 and 07:49:02.8653459+02:00

- Two further 120-second polls found `GO_BUILD` absent.
- No build or compiler was invoked.

## 2026-07-28T07:51:29.9853048+02:00 and 07:54:03.5737316+02:00

- Two final 120-second polls found `GO_BUILD` absent.
- No build or compiler was invoked by this task.
- The shared `ds4_cuda.cu` was externally modified at
  `2026-07-28T07:33:09.3645064+02:00`; the QD-gate patch remained present.
- The shared `ds4_server.exe` was externally rebuilt at
  `2026-07-28T07:34:38.5702711+02:00`; current SHA256 is
  `06395075C5487F9CB30FC3878F4DB5E1966127C802463605EBBEB2F3280AC296`.
  This is not reported as the authorized post-build artifact.
- Re-ran all four static checks against the final shared source state: PASS.
- Final `git diff --check -- ds4_cuda.cu`: PASS.
- No `ds4_server` process was started or observed.
- Authorized post-build SHA256: unavailable because `GO_BUILD` never appeared.
