| caso | V2 r1 ms/tok | V2 r1 t/s | V2 r2 ms/tok | V2 r2 t/s | delta ms | delta t/s | delta % |
|---|---:|---:|---:|---:|---:|---:|---:|
| L01@ctx131k | 37.392 | 26.743 | 37.124 | 26.936 | **-0.268** | +0.193 | +0.72% |
| L02@ctx131k | 37.497 | 26.669 | 37.461 | 26.694 | **-0.036** | +0.025 | +0.09% |
| **aggregato (2048 tok)** | **37.408** | **26.732** | **37.256** | **26.841** | **-0.152** | **+0.109** | **+0.41%** |

| caso | impronta V2 r1 | impronta V2 r2 | identica |
|---|---|---|:--:|
| riscaldamento_1 | `b626d0e377e6075e` | `b626d0e377e6075e` | si |
| riscaldamento_2 | `b626d0e377e6075e` | `b626d0e377e6075e` | si |
| L01@ctx131k | `99ba1423cf128585` | `99ba1423cf128585` | si |
| L02@ctx131k | `dc916b9c428225c2` | `dc916b9c428225c2` | si |

| | V2 r1 | V2 r2 |
|---|---:|---:|
| prefill L01@ctx131k (t/s) | 251.65 | 251.39 |
| prefill L02@ctx131k (t/s) | 49.73 | 50.53 |
| VRAM libera minima (MiB) | 1213 | 1221 |
| RAM disponibile minima (GB) | 2.77 | 6.77 |
| guasto | None | None |
