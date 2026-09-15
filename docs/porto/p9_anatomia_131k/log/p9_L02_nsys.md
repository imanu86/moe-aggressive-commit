# Cattura p9_L02.sqlite

Controllo di integrita': **FALLITO — il profilatore ha perso eventi**. Conteggi per forward attesi dalla geometria (48 strati MoE, 36 GDN, 12 attenzione) contro visti: moe_grouped_plan_decode 48.0/48, topk_moe_cuda 35.202/48, moe_weighted_reduction_f32 45.872/48, gated_delta_net_cuda 13.851/36, ssm_conv_f32 30.926/36, flash_attn_ext_f16 2.128/12

94 forward interi nella finestra (3929.38 ms). Per forward: parete **41.802 ms**, GPU occupata 29.896, inattiva 11.906, somma delle durate 32.050 (sovrapposizione fra kernel 2.154).

| categoria | ms/forward | quota | lanci/forward |
|---|---:|---:|---:|
| 2. matvec DENSI quantizzati (mmvq q6_k) | 8.330 | 19.9% | 163.2 |
| 5. trasporto esperti dal PCIe (moe_grouped_gather_decode) | 7.234 | 17.3% | 80.0 |
| 1. matvec ESPERTI (mmvq iq2_s) | 4.072 | 9.7% | 46.9 |
| 2. matvec DENSI quantizzati (mmvq q8_0) | 2.932 | 7.0% | 238.9 |
| 12. elementari (add/mul/scale/unary/rope/copie) | 2.039 | 4.9% | 1596.4 |
| 1. matvec ESPERTI (mmvq iq4_nl) | 1.817 | 4.3% | 46.9 |
| 4. matvec DENSI in virgola mobile (router f32, inject, ssm, indicizzatore bf16) | 1.654 | 4.0% | 282.6 |
| 7. indicizzatore QSA: gather delle celle (k_get_rows) | 0.812 | 1.9% | 87.4 |
| 6. instradamento MoE (plan, top-k, riduzione) | 0.751 | 1.8% | 129.1 |
| 3. quantizzazione dell'attivazione (quantize_q8_1) | 0.653 | 1.6% | 518.3 |
| 4b. punteggio QSA sui blocchi (mul_mat_f f32) | 0.566 | 1.4% | 10.7 |
| 11. norme | 0.344 | 0.8% | 189.8 |
| 10. GDN / SSM | 0.340 | 0.8% | 44.8 |
| 8. indicizzatore QSA: ordinamento (radix sort) | 0.266 | 0.6% | 40.5 |
| 1. matvec ESPERTI (mmvq iq3_s) | 0.103 | 0.2% | 1.1 |
| 13. altro | 0.085 | 0.2% | 74.6 |
| 9. attenzione (flash_attn) | 0.053 | 0.1% | 5.3 |
| **GPU inattiva** | 11.906 | 28.5% | — |
| **copie H2D (28.7 copie, 7.78 MiB)** | 0.385 | 0.9% | — |

| kernel | ms/forward | lanci | us/lancio | blocchi/lancio | filo/blocco |
|---|---:|---:|---:|---:|---|
| `mul_mat_vec_q<q6_k>` | 8.330 | 163.2 | 51.05 | 6308.7 | 32x4 |
| `moe_grouped_gather_decode` | 7.234 | 80.0 | 90.45 | 70.6 | 256x1 |
| `mul_mat_vec_q<iq2_s>` | 4.072 | 46.9 | 86.75 | 1600.0 | 32x4 |
| `mul_mat_vec_q<q8_0>` | 2.932 | 238.9 | 12.27 | 1367.3 | 32x4 |
| `mul_mat_vec_q<iq4_nl>` | 1.817 | 46.9 | 38.72 | 6400.0 | 32x4 |
| `mul_mat_vec_f<f32>` | 1.486 | 259.2 | 5.73 | 111.7 | 256x1 |
| `k_bin_bcast` | 1.021 | 758.2 | 1.35 | 24.0 | 128x1 |
| `quantize_q8_1` | 0.653 | 518.3 | 1.26 | 16.9 | 256x1 |
| `mul_mat_f<f32>` | 0.566 | 10.7 | 53.07 | 1028.0 | 32x2 |
| `moe_grouped_plan_decode` | 0.500 | 48.0 | 10.42 | 1.0 | 64x1 |
| `k_get_rows_float_vec` | 0.453 | 24.5 | 18.46 | 768.0 | 256x1 |
| `scale_f32` | 0.346 | 344.4 | 1.01 | 3.6 | 256x1 |
| `rms_norm_f32` | 0.273 | 134.3 | 2.03 | 8.2 | 1024x1 |
| `gated_delta_net_cuda` | 0.257 | 13.9 | 18.52 | 1536.0 | 32x4 |
| `k_get_rows` | 0.242 | 8.5 | 28.36 | 867.9 | 256x1 |
| `unary_gated_op_kernel` | 0.222 | 161.0 | 1.38 | 29.4 | 256x1 |
| `unary_op_kernel` | 0.215 | 209.0 | 1.03 | 33.1 | 256x1 |
| `DeviceRadixSortOnesweepKernel` | 0.203 | 16.0 | 12.71 | 17.0 | 384x1 |
| `mul_mat_vec_f<bf16>` | 0.168 | 23.5 | 7.15 | 337.4 | 256x1 |
| `topk_moe_cuda` | 0.161 | 35.2 | 4.58 | 1.0 | 32x8 |
| `concat_cont` | 0.112 | 48.0 | 2.33 | 128.4 | 256x1 |
| `mul_mat_vec_q<iq3_s>` | 0.103 | 1.1 | 96.51 | 6400.0 | 32x4 |
| `moe_weighted_reduction_f32` | 0.089 | 45.9 | 1.94 | 10.0 | 256x1 |
| `k_get_rows_float` | 0.087 | 40.5 | 2.15 | 118.2 | 256x1 |
| `ssm_conv_f32` | 0.084 | 30.9 | 2.71 | 80.0 | 128x1 |
| `l2_norm_f32` | 0.071 | 55.4 | 1.28 | 16.0 | 32x1 |
| `DeviceRadixSortHistogramKernel` | 0.050 | 12.8 | 3.88 | 336.0 | 128x1 |
| `k_set_rows_quant` | 0.048 | 23.5 | 2.04 | 1.0 | 256x1 |
| `flash_attn_ext_f16` | 0.047 | 2.1 | 22.09 | 28.0 | 32x4 |
| `rope_multi` | 0.044 | 32.0 | 1.36 | 8.7 | 1x256 |
| `fwht_cuda` | 0.034 | 30.9 | 1.08 | 4.4 | 32x4 |
| `k_get_rows_scalar` | 0.030 | 13.9 | 2.17 | 86.5 | 256x1 |
| `init_indices` | 0.022 | 12.8 | 1.71 | 514.0 | 256x1 |
| `k_set_rows` | 0.019 | 12.8 | 1.46 | 1.0 | 256x1 |
| `DeviceRadixSortExclusiveSumKernel` | 0.013 | 11.7 | 1.09 | 4.0 | 256x1 |
| `op_clamp_kernel` | 0.012 | 13.9 | 0.90 | 8.4 | 256x1 |
| `diag_mask_inf_f32` | 0.011 | 11.7 | 0.97 | 72.0 | 1x32 |
| `cpy_scalar` | 0.011 | 5.3 | 2.03 | 147.2 | 64x1 |
| `flash_attn_stream_k_fixup_uniform` | 0.006 | 3.2 | 1.84 | 32.0 | 256x1 |
| `pad_f32` | 0.002 | 2.1 | 1.14 | 9.0 | 256x1 |
| `cpy_scalar_contiguous` | 0.002 | 2.1 | 0.92 | 36.0 | 64x1 |
| `init_offsets` | 0.002 | 2.1 | 0.77 | 1.0 | 256x1 |
| `reduce_rows_f32` | 0.001 | 1.1 | 1.40 | 4.0 | 512x1 |
