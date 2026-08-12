# Transport ledger patch

Base file: `ds4-p4a/ds4_cuda.cu`

Base SHA-256:
`AAC858FC5C8422C5D5160E4C6FC4C2F5D262A5C416F42154665E89F1B43242B0`

Patch SHA-256:
`C41E8D0BDB46FEB5DF97CE3BB7D54EC12E179A749CC4743CC677DF58AECCB052`

The production file was not edited. `transport.patch` is a unified diff
against that exact file snapshot.

## Apply

From the repository root, after the other writers have released the file:

```powershell
git apply --check .microbench/transport/transport.patch
git apply .microbench/transport/transport.patch
```

If the check fails because `ds4_cuda.cu` changed, do not force the patch:
rebase its hunks on the final file first.

## Hook map on the base snapshot

- Request/decode lifecycle: `ds4_cuda.cu:15638`, `:29714`, `:29817`,
  `:32563`.
- Fixed table and reporter: `ds4_cuda.cu:27490`.
- File materializations: transient chunk reader `:30034`; SSD-wrap reader
  `:33414`; `cuda_moe_tiering_load_to_ram` `:34859`; route-QD completion
  `:38396`; enforce transient call sites `:38868`; non-enforce worker preads
  `:39895`; nested residual preads `:41290` and `:41574`.
- Pair H2D enqueue/publication: enforce resident/transient call sites `:39145`
  and `:39292`; demand-pipeline flush `:39420`; existing enforce drain
  `:39443`; non-enforce enqueue `:39956` and drain `:40086`.

## Runtime

```powershell
$env:DS4_CUDA_TRANSPORT_LEDGER='1'
$env:DS4_CUDA_TRANSPORT_LEDGER_EVERY_TOKENS='32'
```

Both variables are optional. The ledger defaults to disabled; the periodic
interval defaults to 32 tokens.

## Exact row

```text
ds4: [transport] phase=<periodic|final> tokens=<u64> unique_pairs_touched=<u64> first_touch_bytes=<u64> repeat_h2d_bytes=<u64> repeat_file_bytes=<u64> repeat_ratio=<f9> h2d_bytes_total=<u64> h2d_active_ms=<f3> decode_ms=<f3> pcie_busy_pct=<f6> ledger_complete=<0|1>
```

`first_touch_bytes` and `repeat_h2d_bytes` partition `h2d_bytes_total`.
`repeat_ratio` is `repeat_h2d_bytes / (first_touch_bytes +
repeat_h2d_bytes)`. The pair's file counter advances once per conceptual
materialization; gate/up/down and any chunking share that classification.
Consequently, the three distinct planes of the first materialization are all
first-touch traffic, while `repeat_file_bytes` starts with bytes actually
returned for the second materialization of that `(layer, expert)` pair.

`h2d_active_ms` is the wall-clock union of intervals in which at least one
ledgered expert-payload H2D batch has been submitted and has not yet completed
its existing stream drain. `pcie_busy_pct` is
`100 * h2d_active_ms / decode_ms`.

`ledger_complete=0` means CUDA or file-I/O error handling exposed no exact byte
count for a partial operation. Such unknown bytes are omitted, never estimated.

## Deliberate limits

- Scope is decode expert payload transport only. Prefill is disarmed and the
  table is re-cleared at decode start.
- Metadata H2D, KV traffic, dense weights, D2D copies and D2H copies are not
  pair payload transfers and are excluded.
- GPU reads from mapped host memory (the `[zc]` path) can cross PCIe without an
  H2D copy. This translation unit has no exact per-pair byte counter for those
  hardware reads; they are omitted rather than inferred.
- Mmap page-fault traffic has no exact per-pair positioned-read completion and
  is omitted.
- `h2d_active_ms` is not copy-engine hardware-active time. Exact copy-engine
  occupancy would require CUPTI/activity tracing and would perturb the run.
- No build or runtime test was performed before delivery because application
  and build are gated by `GO_APPLY` and `GO_BUILD`.
