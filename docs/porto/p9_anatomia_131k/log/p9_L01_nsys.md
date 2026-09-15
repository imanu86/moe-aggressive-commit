# Cattura p9_L01.sqlite

Controllo di integrita': **PASSATO**. Conteggi per forward attesi dalla geometria (48 strati MoE, 36 GDN, 12 attenzione) contro visti: moe_grouped_plan_decode 48.0/48, topk_moe_cuda 48.0/48, moe_weighted_reduction_f32 48.0/48, gated_delta_net_cuda 36.0/36, ssm_conv_f32 36.0/36, flash_attn_ext_f16 12.0/12

106 forward interi nella finestra (3968.815 ms). Per forward: parete **37.442 ms**, GPU occupata 34.120, inattiva 3.322, somma delle durate 36.430 (sovrapposizione fra kernel 2.310).

| categoria | ms/forward | quota | lanci/forward |
|---|---:|---:|---:|
| 2. matvec DENSI quantizzati (mmvq q6_k) | 9.609 | 25.7% | 202.0 |
| 5. trasporto esperti dal PCIe (moe_grouped_gather_decode) | 6.688 | 17.9% | 96.0 |
| 1. matvec ESPERTI (mmvq iq2_s) | 3.985 | 10.6% | 47.0 |
| 2. matvec DENSI quantizzati (mmvq q8_0) | 3.113 | 8.3% | 247.0 |
| 7. indicizzatore QSA: gather delle celle (k_get_rows) | 2.575 | 6.9% | 136.0 |
| 12. elementari (add/mul/scale/unary/rope/copie) | 2.512 | 6.7% | 1956.0 |
| 1. matvec ESPERTI (mmvq iq4_nl) | 1.852 | 5.0% | 48.0 |
| 4. matvec DENSI in virgola mobile (router f32, inject, ssm, indicizzatore bf16) | 1.651 | 4.4% | 288.0 |
| 6. instradamento MoE (plan, top-k, riduzione) | 0.769 | 2.0% | 144.0 |
| 10. GDN / SSM | 0.764 | 2.0% | 72.0 |
| 3. quantizzazione dell'attivazione (quantize_q8_1) | 0.682 | 1.8% | 545.0 |
| 4b. punteggio QSA sui blocchi (mul_mat_f f32) | 0.640 | 1.7% | 12.0 |
| 8. indicizzatore QSA: ordinamento (radix sort) | 0.631 | 1.7% | 72.0 |
| 11. norme | 0.458 | 1.2% | 256.0 |
| 9. attenzione (flash_attn) | 0.288 | 0.8% | 24.0 |
| 13. altro | 0.120 | 0.3% | 110.0 |
| 1. matvec ESPERTI (mmvq iq3_s) | 0.092 | 0.2% | 1.0 |
| **GPU inattiva** | 3.322 | 8.9% | — |
| **copie H2D (27.0 copie, 7.31 MiB)** | 0.357 | 1.0% | — |

| kernel | ms/forward | lanci | us/lancio | blocchi/lancio | filo/blocco |
|---|---:|---:|---:|---:|---|
| `mul_mat_vec_q<q6_k>` | 9.609 | 202.0 | 47.57 | 5616.2 | 32x4 |
| `moe_grouped_gather_decode` | 6.688 | 96.0 | 69.67 | 70.0 | 256x1 |
| `mul_mat_vec_q<iq2_s>` | 3.985 | 47.0 | 84.79 | 1600.0 | 32x4 |
| `mul_mat_vec_q<q8_0>` | 3.113 | 247.0 | 12.60 | 1376.1 | 32x4 |
| `mul_mat_vec_q<iq4_nl>` | 1.852 | 48.0 | 38.59 | 6400.0 | 32x4 |
| `k_get_rows` | 1.754 | 36.0 | 48.71 | 1538.7 | 256x1 |
| `mul_mat_vec_f<f32>` | 1.486 | 264.0 | 5.63 | 107.8 | 256x1 |
| `k_bin_bcast` | 1.261 | 909.0 | 1.39 | 33.9 | 128x1 |
| `quantize_q8_1` | 0.682 | 545.0 | 1.25 | 17.3 | 256x1 |
| `gated_delta_net_cuda` | 0.666 | 36.0 | 18.50 | 1536.0 | 32x4 |
| `k_get_rows_float_vec` | 0.664 | 36.0 | 18.45 | 768.0 | 256x1 |
| `mul_mat_f<f32>` | 0.640 | 12.0 | 53.33 | 1028.0 | 32x2 |
| `DeviceRadixSortOnesweepKernel` | 0.572 | 48.0 | 11.91 | 17.0 | 384x1 |
| `moe_grouped_plan_decode` | 0.456 | 48.0 | 9.51 | 1.0 | 64x1 |
| `scale_f32` | 0.400 | 399.0 | 1.00 | 3.4 | 256x1 |
| `rms_norm_f32` | 0.366 | 184.0 | 1.99 | 13.7 | 1024x1 |
| `unary_op_kernel` | 0.289 | 294.0 | 0.98 | 22.4 | 256x1 |
| `flash_attn_ext_f16` | 0.266 | 12.0 | 22.16 | 28.0 | 32x4 |
| `unary_gated_op_kernel` | 0.246 | 181.0 | 1.36 | 28.0 | 256x1 |
| `topk_moe_cuda` | 0.220 | 48.0 | 4.58 | 1.0 | 32x8 |
| `mul_mat_vec_f<bf16>` | 0.165 | 24.0 | 6.89 | 320.0 | 256x1 |
| `concat_cont` | 0.114 | 49.0 | 2.32 | 127.9 | 256x1 |
| `ssm_conv_f32` | 0.098 | 36.0 | 2.71 | 80.0 | 128x1 |
| `moe_weighted_reduction_f32` | 0.093 | 48.0 | 1.94 | 10.0 | 256x1 |
| `l2_norm_f32` | 0.092 | 72.0 | 1.28 | 16.0 | 32x1 |
| `mul_mat_vec_q<iq3_s>` | 0.092 | 1.0 | 91.70 | 6400.0 | 32x4 |
| `k_get_rows_float` | 0.086 | 40.0 | 2.15 | 118.3 | 256x1 |
| `k_set_rows_quant` | 0.074 | 36.0 | 2.05 | 1.0 | 256x1 |
| `k_get_rows_scalar` | 0.072 | 24.0 | 2.98 | 261.5 | 256x1 |
| `rope_multi` | 0.068 | 48.0 | 1.41 | 8.0 | 1x256 |
| `fwht_cuda` | 0.052 | 48.0 | 1.07 | 8.2 | 32x4 |
| `DeviceRadixSortHistogramKernel` | 0.047 | 12.0 | 3.88 | 336.0 | 128x1 |
| `cpy_scalar` | 0.031 | 16.0 | 1.94 | 112.0 | 64x1 |
| `flash_attn_stream_k_fixup_uniform` | 0.022 | 12.0 | 1.84 | 32.0 | 256x1 |
| `init_indices` | 0.021 | 12.0 | 1.71 | 514.0 | 256x1 |
| `k_set_rows` | 0.017 | 12.0 | 1.45 | 1.0 | 256x1 |
| `pad_f32` | 0.014 | 12.0 | 1.14 | 9.0 | 256x1 |
| `DeviceRadixSortExclusiveSumKernel` | 0.013 | 12.0 | 1.09 | 4.0 | 256x1 |
| `op_clamp_kernel` | 0.012 | 13.0 | 0.90 | 8.4 | 256x1 |
| `diag_mask_inf_f32` | 0.012 | 12.0 | 0.97 | 72.0 | 1x32 |
| `cpy_scalar_contiguous` | 0.011 | 12.0 | 0.93 | 36.0 | 64x1 |
| `init_offsets` | 0.009 | 12.0 | 0.77 | 1.0 | 256x1 |
| `reduce_rows_f32` | 0.001 | 1.0 | 1.40 | 4.0 | 512x1 |
