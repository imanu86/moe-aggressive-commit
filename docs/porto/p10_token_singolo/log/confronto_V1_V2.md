| caso | V1 ms/tok | V1 t/s | V2 ms/tok | V2 t/s | delta ms | delta t/s | delta % |
|---|---:|---:|---:|---:|---:|---:|---:|
| L01@ctx131k | 37.353 | 26.772 | 37.392 | 26.743 | **+0.040** | -0.029 | -0.11% |
| L02@ctx131k | 37.692 | 26.531 | 37.497 | 26.669 | **-0.196** | +0.138 | +0.52% |
| **aggregato (2048 tok)** | **37.486** | **26.677** | **37.408** | **26.732** | **-0.078** | **+0.055** | **+0.21%** |

| caso | impronta V1 | impronta V2 | identica |
|---|---|---|:--:|
| riscaldamento_1 | `b626d0e377e6075e` | `b626d0e377e6075e` | si |
| riscaldamento_2 | `b626d0e377e6075e` | `b626d0e377e6075e` | si |
| L01@ctx131k | `99ba1423cf128585` | `99ba1423cf128585` | si |
| L02@ctx131k | `dc916b9c428225c2` | `dc916b9c428225c2` | si |

| | V1 | V2 |
|---|---:|---:|
| prefill L01@ctx131k (t/s) | 251.75 | 251.65 |
| prefill L02@ctx131k (t/s) | 50.00 | 49.73 |
| VRAM libera minima (MiB) | 1213 | 1213 |
| RAM disponibile minima (GB) | 3.03 | 2.77 |
| guasto | None | None |
