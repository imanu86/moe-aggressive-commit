# DS4 Q1_0 runtime step 3 dispatch

Canonical patch: `patches/ds4/0055-ds4-q1-0-runtime-step3-dispatch.patch`

Incremental Windows patch: `patches/ds4/0055-ds4-q1-0-runtime-step3-on-6a44578.patch`

Base:

- Canonical chain: apply after 0052+0053 plus the 0054 blocker corrections.
- Windows runtime branch: apply directly on `imanu86/ds4-win` commit `6a44578` (`feature/q1-0-resident-base`).

Patch encoding: ASCII/UTF-8 bytes, no BOM, no NUL, LF newlines. The first four bytes are `64 69 66 66` (`diff`).

Scope:

- Adds `ds4_gpu_set_q1_0_sidecar()` and installs the Q1_0 sidecar file/source into CUDA separately from IQ1_S.
- Adds Q1_0 CUDA sidecar provenance/file-source state and teardown telemetry: calls, slots, selected loads, failures.
- Adds Q1_0 selected-load from the dedicated sidecar file with `DS4_Q1_0_SELECTED_LOAD` opt-in and fail-closed behavior.
- Dispatches Q1_0 qwarp32 gate/up/down kernels only after selected-load succeeds. This direct `pread` path is a structural smoke, not a performance candidate.
- Leaves IQ1_S env-off and mixed paths separate.

No runtime benchmark, GPU model run, or large model access is included in this task.
