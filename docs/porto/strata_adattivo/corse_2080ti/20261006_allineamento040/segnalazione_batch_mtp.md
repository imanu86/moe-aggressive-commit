**Title:** `--batch-mtp` exits (code 1) on the first admission when the drafter has a draft-vocab head: the slot drafters never copy its type

**Body:**

On 0.1.40 (`1735d64`), `--batch 2 --batch-mtp` with an MTP directory that ships `draft_vocab.bin` exits on the first
request that a batch slot takes:

```
strata batch: MTP admission for slot 0 failed: mtp: unsupported native MMVQ GGML type
```

The engine returns 1 and the server reports "the engine stopped unexpectedly". `--batch 2` without `--batch-mtp` runs
fine on the same setup.

**Cause.** In `MtpDrafter::bind` (`src/core/mtp.cpp`) a slot drafter that shares the main drafter's head copies
`dhead_`, `dvocab_` and `n_dvocab_`, but not `dhead_type_`. That stays at its default `-1`, so the first
`native_mmvq(sub ? dhead_type_ : ..., ...)` in `draft_first` hits the `default:` case and throws. Any draft-vocab
subset triggers this, the `--mtp-q4` Q4_0 head included.

**Fix (one line):**

```cpp
        dhead_ = shared->dhead_;
        dhead_type_ = shared->dhead_type_;
        dvocab_ = shared->dvocab_;
        n_dvocab_ = shared->n_dvocab_;
```

**Setup:** RTX 2080 Ti 22 GB (sm_75, our Turing fork on top of 0.1.40), Windows, CUDA 12.6,
Qwen3.8-Flash-Next IQ3_XXS, MTP draft with `draft_vocab.bin` (48,542 tokens), `--spec 4`, two concurrent
Claude Code agents (each with a ~40K-token prompt).

**Verified** with the fix: the same setup starts, two concurrent requests both finish (batch windows average 3.44
rows, i.e. both slots with their MTP proposals, no exit). Without the
fix the first admission exits every time.
