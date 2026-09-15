| categoria | misurato ms | lanci | MiB/token | banda usata GB/s | pavimento ms | efficienza | spreco ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| esperti: matvec dalla cache in VRAM (iq2_s/iq3_s/iq4_nl) | 5.929 | 96.0 | 905.8 | 160.2 | 2.791 | 47% | 3.138 |
| esperti: trasporto dal PCIe (gather) | 6.688 | 96.0 | 168.5 | 26.4 | 6.717 | 100% | -0.029 |
| densi quantizzati: matvec q6_k/q8_0 (+quantize_q8_1) | 13.404 | 994.0 | 3446.4 | 269.6 | 10.620 | 79% | 2.784 |
| densi in virgola mobile: router f32, inject, ssm, indicizzatore bf16 | 1.651 | 288.0 | 336.2 | 213.5 | 1.036 | 63% | 0.615 |
| punteggio QSA sui blocchi (legge la cache dei blocchi) | 0.640 | 12.0 | 192.3 | 315.0 | 0.592 | 93% | 0.048 |
| indicizzatore/KV: gather delle celle (host mappato) | 2.575 | 136.0 | 54.2 | 22.1 | 2.160 | 84% | 0.415 |
| instradamento MoE (plan, top-k, riduzione) | 0.769 | 144.0 | — | — | — | — | — |
| indicizzatore: ordinamento | 0.631 | 72.0 | — | — | — | — | — |
| attenzione (flash_attn) | 0.288 | 24.0 | — | — | — | — | — |
| GDN / SSM | 0.764 | 72.0 | — | — | — | — | — |
| norme | 0.458 | 256.0 | — | — | — | — | — |
| elementari (add/mul/scale/unary/rope/copie) | 2.512 | 1956.0 | — | — | — | — | — |
| altro | 0.120 | 110.0 | — | — | — | — | — |
| copie H2D esplicite (bias QSA e piccole) | 0.357 | 27.0 | 7.3 | 21.5 | 0.292 | — | — |
| **somma delle durate** | **36.786** | | | | **24.208** | | |
| *GPU inattiva* | 3.322 | | | | | | |
| *sovrapposizione fra kernel (da sottrarre)* | −2.310 | | | | | | |
| **parete per token** | **37.442** | | | | | | |
