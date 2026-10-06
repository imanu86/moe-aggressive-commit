## What

`--elastic` (opt-in, `--serve`, one CUDA GPU): the expert cache follows the free VRAM **automatically** while the
server runs. It complements #533's `--vram-elastic` (resized on request through `POST /v1/vram`): the two never open
together, and nothing changes when `--elastic` is not given.

- **Stable addresses.** The arena is a reserved virtual range backed by physical chunks (CUDA VMM). Growing and
  shrinking never move the arena or the slot-offset table, so the verify plan, the prompt path and the device
  residency table keep the pointers they got at startup.
- **Two zones.** The startup profile fills the cache; its last part is the **tail** (by default half the startup
  cache, at most 6 GiB; `--elastic-tail-mib`), which rotates, is lent, grows and shrinks. The slots before it are a
  fixed **core**: never lent to the prompt path, never chosen as a swap victim and never shrunk.
- **Policy.** Keeps `--elastic-reserve-mib` (500) free. Grows with the most-used missing experts (then the profile's
  order) once the room has lasted `--elastic-stable-ms` (5000; doubles after a shrink that follows a growth, back to
  the base after 5 minutes without one).
  Shrinks at once when the room is gone, at most `--elastic-shrink-step-mib` (1024) per check, moving the tail's
  hottest experts into colder slots first, never a flush. Checked every `--elastic-period-ms` (1000) at the decode's
  safe point and at each request's start; the prompt path replans its loan after a resize.
- **Scope.** Native pack with a startup profile and sized slots, one local CUDA GPU, serve mode. CLI generation, layer
  split, peer/remote tiers, the resident CPU complement and HIP keep the fixed cache; no VMM -> the plain arena.
- **Naming.** `ExpertCache::elastic_grow` / `elastic_shrink` / `elastic_mapped_bytes`, apart from #533's byte-sized
  `grow` / `shrink` on the segmented arena.

Files: `src/core/expert_cache.cpp` + header (VMM arena), `src/program/generate.cpp` (options, core/tail, policy,
loan), `src/prefill/prefill.{hpp,cpp}` (host buffers sized for the largest chunk a later relayout can ask for),
`tests/core/expert_cache_elastic_test.cpp`, `docs/ELASTIC_CACHE.md`, `CMakeLists.txt` (driver library link, test).

## Tests (RTX 2080 Ti 22 GB, Windows 11, CUDA 12.6, Release sm_75)

- CTest `expert_cache_elastic_test` (real VMM: grow, shrink, regrow, stable addresses/offsets, preserved bytes,
  zeroed new slots, unchanged state after rejected requests, fixed reopen), `expert_cache_per_layer_test`,
  `expert_profile_save_test`, `expert_cache_segmented_test`: 4/4.
- **Without `--elastic` the output is bit-identical to upstream 0.1.39**: teacher forcing with a fixed expert
  placement on a code and an explain task, per-position log-probabilities byte for byte equal.
- 131k context, one run each on an idle machine: with `--elastic` the cache started at 6781 slots (core 3357 /
  tail 3424) and grew +300 experts while VRAM was free; L01 49.4 tok/s, L02 45.8 tok/s, prefill 153.9 s - against
  upstream's fixed cache 47.3 / 46.3 tok/s, 153.1 s (run-to-run noise). The gain is not on an idle machine but when
  other programs take and return VRAM: the fixed cache must be sized for the worst moment.

Full logs, scripts and the first port on 0.1.38 (numeric gate, 131k/250k dialogues):
https://github.com/imanu86/Strata-2080Ti/tree/evidence/elastic-cache

## Origin

Written for the community Strata-2080Ti fork (https://github.com/imanu86/Strata-2080Ti), where it has been the
daily build's default since late September 2026 on a modified RTX 2080 Ti shared with desktop programs. This PR
isolates it from the fork's other changes on top of 0.1.39.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
