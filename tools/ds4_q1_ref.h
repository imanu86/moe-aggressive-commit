/*
 * DS4 Q1_0 reference conversion helper.
 *
 * Provenance: minimal routines ported from ggml-org/llama.cpp commit
 * 635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b:
 * - ggml/src/ggml-common.h: block_q1_0, block_q2_K, block_iq2_xxs,
 *   kmask_iq2xs, ksigns_iq2xs, iq2xxs_grid
 * - ggml/src/ggml-quants.c: dequantize_row_iq2_xxs,
 *   dequantize_row_q2_K, quantize_row_q1_0_ref,
 *   dequantize_row_q1_0, quantize_q1_0
 *
 * Upstream license: MIT. This file keeps only CPU reference row/chunk APIs for
 * converter tooling in this knowledge repo; it is not a DS4 runtime change.
 */

#ifndef DS4_Q1_REF_H
#define DS4_Q1_REF_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define DS4_Q1_REF_TYPE_Q2_K 10
#define DS4_Q1_REF_TYPE_IQ2_XXS 16
#define DS4_Q1_REF_TYPE_Q1_0 41

#define DS4_Q1_REF_QK_K 256
#define DS4_Q1_REF_QK1_0 128
#define DS4_Q1_REF_Q2_K_BLOCK_BYTES 84
#define DS4_Q1_REF_IQ2_XXS_BLOCK_BYTES 66
#define DS4_Q1_REF_Q1_0_BLOCK_BYTES 18

size_t ds4_q1_ref_row_size(int type_id, int64_t ncols);
int ds4_q1_ref_dequant_row(int type_id, const void *src, int64_t ncols, float *dst);
int ds4_q1_ref_quantize_row_q1_0(const float *src, int64_t ncols, void *dst);
int ds4_q1_ref_dequant_row_q1_0(const void *src, int64_t ncols, float *dst);
int ds4_q1_ref_convert_rows_to_q1_0(
        int type_id,
        const void *src,
        size_t src_size,
        int64_t nrows,
        int64_t ncols,
        void *dst,
        size_t dst_size);

#ifdef __cplusplus
}
#endif

#endif
