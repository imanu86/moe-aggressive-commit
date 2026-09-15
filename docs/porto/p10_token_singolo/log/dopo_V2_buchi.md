# Buchi e sincronizzazioni — dopo_L01.sqlite

Integrita' geometrica: **PASSATA** (moe_grouped_plan_decode 48.0/48, topk_moe_cuda 48.0/48, moe_weighted_reduction_f32 48.0/48, gated_delta_net_cuda 36.0/36, ssm_conv_f32 36.0/36, flash_attn_ext_f16 12.0/12).

130 forward PULITI (confine = salto di `graphNodeId`, 4256 kernel ciascuno); 1 forward scartati perche' il backend ha ri-catturato il grafo e li ha eseguiti nodo per nodo. Parete **36.700 ms**/forward, GPU inattiva **2.600 ms**/forward.

| fascia | buchi/forward | ms/forward |
|---|---:|---:|
| >100us | 1.85 | 1.171 |
| 5-20us | 64.01 | 0.883 |
| <2us | 4046.87 | 0.378 |
| 2-5us | 62.26 | 0.151 |
| 20-100us | 0.31 | 0.017 |

## Buchi oltre 100 us

### `mul_mat_vec_q` -> `k_bin_bcast` — 1.00/forward, 1.031 ms/forward (mediana 1.010, min 0.856, max 1.431)

posizione nel grafo (indice del kernel dall'inizio del grafo): 0 x130

copie dentro il buco: 16.00, 2.237 MiB, 0.120 ms

| chiamata CUDA dentro il buco | per buco | ms per buco |
|---|---:|---:|
| `cudaMemcpyAsync_v3020` | 16.00 | 0.133 |
| `cudaStreamSynchronize_v3020` | 8.99 | 0.098 |
| `cudaGraphLaunch_v10000` | 1.00 | 0.070 |

### `mul_mat_vec_q` -> `scale_f32` — 0.84/forward, 0.138 ms/forward (mediana 0.146, min 0.101, max 0.620)

posizione nel grafo (indice del kernel dall'inizio del grafo): 45 x109

copie dentro il buco: 0.00, 0.000 MiB, 0.000 ms

| chiamata CUDA dentro il buco | per buco | ms per buco |
|---|---:|---:|
| `cudaGraphLaunch_v10000` | 1.00 | 0.164 |

### `init_offsets` -> `DeviceRadixSortHistogramKernel` — 0.01/forward, 0.002 ms/forward (mediana 0.254, min 0.254, max 0.254)

posizione nel grafo (indice del kernel dall'inizio del grafo): 3122 x1

copie dentro il buco: 1.00, 0.502 MiB, 0.003 ms

| chiamata CUDA dentro il buco | per buco | ms per buco |
|---|---:|---:|
| `cudaStreamSynchronize_v3020` | 1.00 | 0.254 |

## Chiamate dell'host per forward

| chiamata | per forward | ms per forward |
|---|---:|---:|
| `cudaMemcpyAsync_v3020` | 17.25 | 0.150 |
| `cudaStreamSynchronize_v3020` | 9.12 | 29.609 |
| `cudaGraphLaunch_v10000` | 1.02 | 6.301 |

## `cudaStreamSynchronize`: 9.12 per forward

| classe (dalla chiamata precedente sullo stesso filo) | per forward | ms |
|---|---:|---:|
| svuotamento della coda prima di un ingresso (dopo un'altra sync) | 8.12 | 0.013 |
| attesa del forward (> 1 ms) | 1.00 | 29.597 |

## Copie

H2D 15.23 copie, 1.309 MiB, 0.082 ms — D2H 1.02 copie, 0.9618 MiB per forward.

| stream delle H2D | copie/forward | MiB/forward |
|---|---:|---:|
| 63 | 15.23 | 1.309 |

| byte per copia H2D | copie/forward |
|---|---:|
| 527360 | 0.14 |
| 526336 | 1.89 |
| 262144 | 1.02 |
| 16384 | 1.02 |
| 10240 | 2.03 |
| 32 | 2.03 |
| 16 | 2.03 |
| 8 | 3.05 |
| 4 | 2.03 |
