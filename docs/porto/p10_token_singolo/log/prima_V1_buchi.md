# Buchi e sincronizzazioni — prima_L01.sqlite

Integrita' geometrica: **PASSATA** (moe_grouped_plan_decode 48.0/48, topk_moe_cuda 48.0/48, moe_weighted_reduction_f32 48.0/48, gated_delta_net_cuda 36.0/36, ssm_conv_f32 36.0/36, flash_attn_ext_f16 12.0/12).

127 forward PULITI (confine = salto di `graphNodeId`, 4256 kernel ciascuno); 7 forward scartati perche' il backend ha ri-catturato il grafo e li ha eseguiti nodo per nodo. Parete **36.807 ms**/forward, GPU inattiva **2.801 ms**/forward.

| fascia | buchi/forward | ms/forward |
|---|---:|---:|
| >100us | 1.50 | 1.346 |
| 5-20us | 64.20 | 0.885 |
| <2us | 4048.83 | 0.381 |
| 2-5us | 60.59 | 0.147 |
| 20-100us | 0.50 | 0.041 |

## Buchi oltre 100 us

### `mul_mat_vec_q` -> `k_bin_bcast` — 1.00/forward, 1.267 ms/forward (mediana 1.258, min 1.095, max 1.717)

posizione nel grafo (indice del kernel dall'inizio del grafo): 0 x127

copie dentro il buco: 16.00, 2.237 MiB, 0.121 ms

| chiamata CUDA dentro il buco | per buco | ms per buco |
|---|---:|---:|
| `cudaStreamSynchronize_v3020` | 41.99 | 0.243 |
| `cudaMemcpyAsync_v3020` | 15.00 | 0.112 |
| `cudaGraphLaunch_v10000` | 1.00 | 0.060 |

### `mul_mat_vec_q` -> `scale_f32` — 0.50/forward, 0.080 ms/forward (mediana 0.139, min 0.101, max 0.293)

posizione nel grafo (indice del kernel dall'inizio del grafo): 45 x64

copie dentro il buco: 0.00, 0.000 MiB, 0.000 ms

| chiamata CUDA dentro il buco | per buco | ms per buco |
|---|---:|---:|
| `cudaGraphLaunch_v10000` | 1.00 | 0.158 |

## Chiamate dell'host per forward

| chiamata | per forward | ms per forward |
|---|---:|---:|
| `cudaStreamSynchronize_v3020` | 43.61 | 29.970 |
| `cudaMemcpyAsync_v3020` | 16.59 | 0.130 |
| `cudaGraphLaunch_v10000` | 1.04 | 6.094 |

## `cudaStreamSynchronize`: 43.61 per forward

| classe (dalla chiamata precedente sullo stesso filo) | per forward | ms |
|---|---:|---:|
| svuotamento della coda prima di un ingresso (dopo un'altra sync) | 27.02 | 0.022 |
| coda bloccante di una copia (dopo cudaMemcpyAsync) | 15.59 | 0.144 |
| attesa del forward (> 1 ms) | 1.00 | 29.803 |

## Copie

H2D 15.59 copie, 1.340 MiB, 0.084 ms — D2H 1.04 copie, 0.9846 MiB per forward.

| stream delle H2D | copie/forward | MiB/forward |
|---|---:|---:|
| 14 | 15.59 | 1.340 |

| byte per copia H2D | copie/forward |
|---|---:|
| 527360 | 0.17 |
| 526336 | 1.91 |
| 262144 | 1.04 |
| 16384 | 1.04 |
| 10240 | 2.08 |
| 32 | 2.08 |
| 16 | 2.08 |
| 8 | 3.12 |
| 4 | 2.08 |
