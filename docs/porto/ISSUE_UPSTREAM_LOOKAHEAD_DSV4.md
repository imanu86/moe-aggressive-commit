# MATERIALE issue upstream — PRONTO, NON APERTO

*Stato: bozza completa. La decisione di aprirla è dell'utente (comunicazione
pubblica a suo nome). Prima di postare, eseguire i TRE CONTROLLI in fondo
sulla configurazione di ggml-org/llama.cpp a master corrente.*

---

## Titolo proposto

`lookahead example dies silently (release fast-fail) on DeepSeek-V4 models:
"DSV4 coupled raw writes require equal sequence lengths"`

## Corpo proposto (inglese)

### Summary

`llama-lookahead` cannot run on DeepSeek-V4 models: the first Jacobi batch
throws `std::runtime_error("DSV4 coupled raw writes require equal sequence
lengths")` from `src/llama-kv-cache-dsv4.cpp`. In a release MSVC build the
exception escapes `main`, `terminate()` is silent (fast-fail `0xC0000409`),
so the process prints the prompt, one token, and exits with no message, no
stats and no crash dump — it looks like a hang/heisenbug rather than what it
is.

### Repro

```
llama-lookahead -m <any DeepSeek-V4 gguf> -c 4096 -b 128 -ub 128 -ngl 99 \
  -t 8 -n 300 -f prompt.txt
```

Prompt content irrelevant. Observed on Windows/MSVC (CUDA build) at commit
<FILL: our base 394a797 is a fork; verify and cite the upstream commit —
constraint present in upstream f5919bf at src/llama-kv-cache-dsv4.cpp:109>.

### Root cause

The lookahead example builds a batch where tokens belong to multiple
sequences with per-sequence token counts that are unequal *by construction*
(1 token for seq 0, sliding windows for seqs 1..W, verification n-grams for
seqs W+1..W+G). The DSV4 raw-write path expands coupled (multi-sequence)
tokens into a dense `[sequence x token]` grid and requires equal counts:

- `dsv4_build_raw_write_ubatch()` — the equal-lengths throw;
- behind it, with `kv_unified` (which lookahead.cpp forces), the compressed
  planner also rejects any ubatch with more than one unique sequence
  ("DSV4 single compressed stream cannot serve multiple sequences");
- and the DSV4 cache is append-only: tail `seq_rm(p0>0)` returns `false`
  (the example ignores the return value), while `seq_cp`/`seq_keep` clear
  the whole compressed state. The sanctioned rollback is checkpointing.

So the example's KV dance (per-step `seq_rm`/`seq_keep`/`seq_cp`) is
incompatible with this cache by design, not by accident. lookahead + any
DSV4 model has plausibly never run anywhere.

### Suggested minimal fixes (either/both)

1. `llama_decode` boundary: convert the DSV4 topology throws into a normal
   non-zero decode return (the API contract is error codes, not exceptions
   escaping through C ABI), so callers get a printable failure.
2. Example-level courtesy catch so the failure is at least *named* (patch
   below, from our fork branch `jacobi`, commit b2b432b).

```
--- a/examples/lookahead/lookahead.cpp
+++ b/examples/lookahead/lookahead.cpp
   (catch std::exception at end of main, print e.what() to stderr,
    return 250 — full patch attached)
```

### Environment

Windows 11, MSVC 19.44, CUDA 13.2, RTX 3060, release build (`-O2`, no
`/EHa`); model: DeepSeek-V4-0731 IQ2_XXS. Also reproduced logically against
vanilla checkout f5919bf (constraint identical).

---

## I TRE CONTROLLI prima di aprire (regola "post esterni")

1. **La LORO testa**: clonare/aggiornare ggml-org/llama.cpp a master di
   OGGI e verificare che `llama-kv-cache-dsv4.cpp` contenga ancora il
   throw e che `lookahead.cpp` forzi ancora `kv_unified` + `n_parallel =
   W+G+1`. Citare il commit hash di master, non il nostro fork.
2. **Issue/PR esistenti**: cercare fra issue e PR aperte/chiuse
   `lookahead`, `dsv4`, `coupled raw writes`, `equal sequence lengths` —
   inclusa la PR #25784 (DSpark/MTP) e discussioni collegate: se il tema è
   già tracciato, commentare lì invece di aprire un duplicato.
3. **Riprodurre sul VANILLA**, non solo dedurre: una run di
   `llama-lookahead` vanilla su un modello DSV4 (basta il crash con lo
   stesso messaggio sotto debugger o con catch temporaneo). La nostra
   riproduzione è sul fork: prima di firmare pubblicamente, il repro deve
   essere loro-su-loro.

*Nota: il fast-fail muto è MSVC-specifico; su Linux/glibc l'eccezione non
gestita stampa il `what()`. L'issue resta valida (il crash c'è ovunque) ma
il paragrafo sulla morte silenziosa va qualificato come Windows-only.*
