# DS4 Q1_0 blocker fixes on 60f743d

Patch artifact: `patches/ds4/0054-ds4-q1-0-blocker-fixes-on-60f743d.patch`

Base: apply directly on DS4 Windows commit `60f743de1104b1c8be6aadedde1f80d5470899dc`, which already contains the original 0052+0053 Q1_0 runtime foundation.

Patch encoding: ASCII/UTF-8 bytes, no BOM, no NUL, LF newlines. The first four bytes are `64 69 66 66` (`diff`).

Fixes:

- Corrects Q1_0 half128 dot indexing: each `cuda_block_q1_0` reads only `qs[0..15]`; the `half` argument selects only the Q8_K half and `bsums` half.
- Restricts the Q1_0 sidecar binder to routed layers `3..42` by default. Env overrides outside `3..42` fail closed, and layers `0..2` are not validated or counted into `routed_bytes`.
- Fails closed at engine open when `DS4_Q1_0_EXPERT_SIDECAR` and `DS4_IQ1_S_MIXED_COLD_K=1` are both active for the first smoke.
- Removes Q1_0 from the generic primary routed-expert type gate, so type 41 is accepted only by the explicit sidecar binder until CPU prefill Q1_0 support exists.

Verification target:

1. `git apply --check patches/ds4/0054-ds4-q1-0-blocker-fixes-on-60f743d.patch` on a clean checkout of `60f743de1104b1c8be6aadedde1f80d5470899dc`.
2. Build `ds4_cuda` and `ds4` with `DS4_CUDA_ARCHITECTURES=86`.
3. Do not run DS4, use GPU, or touch model files.
