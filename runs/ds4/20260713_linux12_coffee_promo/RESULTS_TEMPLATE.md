# Coffee mask on native 12GB (RTX 3080 Ti) — PROMOTION + PRUNING (n=1)

Pod: <ID> RTX 3080 Ti 12GB community; PCIe <gen/width measured>; driver 580.95.05
Binary: ds4-server da0b3f6 (sm_86); model ds4-2bit.gguf (R2, sha efc7ed60)
Envelope 12 GiB; CACHE_PROFILE=1; cache-experts=400; warm=48 meas=1600 temp0

| arm | keep(k) | GB pinned | rende(grade) | decode_tps | hit% | MiB/tok | copy_ms/tok | noncopy_ms/tok | H2D GiB/s |
|-----|---------|-----------|--------------|-----------|------|---------|-------------|----------------|-----------|
| coffee_k83_promo      | 83  |  |  |  |  |  |  |  |  |
| coffee_k83_staticpin  | 83  |  |  |  |  |  |  |  |  |
| coffee_k65_promo      | 65  |  |  |  |  |  |  |  |  |
| coffee_k100_promo     | 100 |  |  |  |  |  |  |  |  |

## Verdict (honest, n=1)
1. Coffee on native 12GB with promotion+pruning: <decode_tps, grade>
2. Promotion vs static pin (the user's key Q): hit% delta = <promo - static>, t/s delta = <>
3. Noncopy floor measured: <noncopy_ms/tok> => <1000/noncopy> t/s ceiling
4. Width curve: k65 vs k83 vs k100 (residency vs quality)
