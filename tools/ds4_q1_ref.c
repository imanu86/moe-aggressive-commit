#include "ds4_q1_ref.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#if defined(_MSC_VER)
#define DS4_PACKED_STRUCT(definition) __pragma(pack(push, 1)) definition __pragma(pack(pop))
#else
#define DS4_PACKED_STRUCT(definition) definition __attribute__((packed))
#endif

DS4_PACKED_STRUCT(
typedef struct {
    uint16_t d;
    uint8_t qs[DS4_Q1_REF_QK1_0 / 8];
} ds4_block_q1_0;
);

DS4_PACKED_STRUCT(
typedef struct {
    uint8_t scales[DS4_Q1_REF_QK_K / 16];
    uint8_t qs[DS4_Q1_REF_QK_K / 4];
    uint16_t d;
    uint16_t dmin;
} ds4_block_q2_K;
);

DS4_PACKED_STRUCT(
typedef struct {
    uint16_t d;
    uint16_t qs[DS4_Q1_REF_QK_K / 8];
} ds4_block_iq2_xxs;
);

typedef char ds4_q1_size_check_q1_0[(sizeof(ds4_block_q1_0) == DS4_Q1_REF_Q1_0_BLOCK_BYTES) ? 1 : -1];
typedef char ds4_q1_size_check_q2_K[(sizeof(ds4_block_q2_K) == DS4_Q1_REF_Q2_K_BLOCK_BYTES) ? 1 : -1];
typedef char ds4_q1_size_check_iq2_xxs[(sizeof(ds4_block_iq2_xxs) == DS4_Q1_REF_IQ2_XXS_BLOCK_BYTES) ? 1 : -1];

#include "ds4_q1_ref_tables.inc"

static float ds4_f32_from_bits(uint32_t bits) {
    union {
        uint32_t u;
        float f;
    } v;
    v.u = bits;
    return v.f;
}

static uint32_t ds4_f32_to_bits(float f) {
    union {
        float f;
        uint32_t u;
    } v;
    v.f = f;
    return v.u;
}

static uint16_t ds4_f32_to_f16(float f) {
    const float scale_to_inf = 0x1.0p+112f;
    const float scale_to_zero = 0x1.0p-110f;
    float base = (fabsf(f) * scale_to_inf) * scale_to_zero;

    const uint32_t w = ds4_f32_to_bits(f);
    const uint32_t shl1_w = w + w;
    const uint32_t sign = w & UINT32_C(0x80000000);
    uint32_t bias = shl1_w & UINT32_C(0xFF000000);
    if (bias < UINT32_C(0x71000000)) bias = UINT32_C(0x71000000);

    base = ds4_f32_from_bits((bias >> 1) + UINT32_C(0x07800000)) + base;
    const uint32_t out = ds4_f32_to_bits(base);
    const uint32_t exp_bits = (out >> 13) & UINT32_C(0x00007C00);
    const uint32_t mantissa_bits = out & UINT32_C(0x00000FFF);
    const uint32_t nonsign = exp_bits + mantissa_bits;
    return (uint16_t)((sign >> 16) | (shl1_w > UINT32_C(0xFF000000) ? UINT16_C(0x7E00) : nonsign));
}

static float ds4_f16_to_f32(uint16_t h) {
    const uint32_t w = (uint32_t)h << 16;
    const uint32_t sign = w & UINT32_C(0x80000000);
    const uint32_t two_w = w + w;
    const uint32_t exp_offset = UINT32_C(0xE0) << 23;
    const float exp_scale = 0x1.0p-112f;
    const float normalized = ds4_f32_from_bits((two_w >> 4) + exp_offset) * exp_scale;
    const uint32_t magic_mask = UINT32_C(126) << 23;
    const float magic_bias = 0.5f;
    const float denormalized = ds4_f32_from_bits((two_w >> 17) | magic_mask) - magic_bias;
    const uint32_t denormalized_cutoff = UINT32_C(1) << 27;
    const uint32_t result = sign | (two_w < denormalized_cutoff ? ds4_f32_to_bits(denormalized) : ds4_f32_to_bits(normalized));
    return ds4_f32_from_bits(result);
}

size_t ds4_q1_ref_row_size(int type_id, int64_t ncols) {
    if (ncols <= 0) return 0;
    int64_t blocks = 0;
    size_t block_bytes = 0;
    switch (type_id) {
        case DS4_Q1_REF_TYPE_Q2_K:
            if (ncols % DS4_Q1_REF_QK_K) return 0;
            blocks = ncols / DS4_Q1_REF_QK_K;
            block_bytes = DS4_Q1_REF_Q2_K_BLOCK_BYTES;
            break;
        case DS4_Q1_REF_TYPE_IQ2_XXS:
            if (ncols % DS4_Q1_REF_QK_K) return 0;
            blocks = ncols / DS4_Q1_REF_QK_K;
            block_bytes = DS4_Q1_REF_IQ2_XXS_BLOCK_BYTES;
            break;
        case DS4_Q1_REF_TYPE_Q1_0:
            if (ncols % DS4_Q1_REF_QK1_0) return 0;
            blocks = ncols / DS4_Q1_REF_QK1_0;
            block_bytes = DS4_Q1_REF_Q1_0_BLOCK_BYTES;
            break;
        default:
            return 0;
    }
    if ((uint64_t)blocks > (uint64_t)SIZE_MAX / block_bytes) return 0;
    return (size_t)blocks * block_bytes;
}

static void dequantize_row_iq2_xxs(const ds4_block_iq2_xxs *x, float *y, int64_t k) {
    const int64_t nb = k / DS4_Q1_REF_QK_K;
    uint32_t aux32[2];
    const uint8_t *aux8 = (const uint8_t *)aux32;

    for (int64_t i = 0; i < nb; i++) {
        const float d = ds4_f16_to_f32(x[i].d);
        for (int ib32 = 0; ib32 < DS4_Q1_REF_QK_K / 32; ++ib32) {
            memcpy(aux32, x[i].qs + 4 * ib32, 2 * sizeof(uint32_t));
            const float db = d * (0.5f + (float)(aux32[1] >> 28)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t *grid = (const uint8_t *)(iq2xxs_grid + aux8[l]);
                const uint8_t signs = ksigns_iq2xs[(aux32[1] >> (7 * l)) & 127u];
                for (int j = 0; j < 8; ++j) {
                    y[j] = db * (float)grid[j] * ((signs & kmask_iq2xs[j]) ? -1.0f : 1.0f);
                }
                y += 8;
            }
        }
    }
}

static void dequantize_row_q2_K(const ds4_block_q2_K *x, float *y, int64_t k) {
    const int nb = (int)(k / DS4_Q1_REF_QK_K);
    for (int i = 0; i < nb; i++) {
        const float d = ds4_f16_to_f32(x[i].d);
        const float min = ds4_f16_to_f32(x[i].dmin);
        const uint8_t *q = x[i].qs;
        int is = 0;
        for (int n = 0; n < DS4_Q1_REF_QK_K; n += 128) {
            int shift = 0;
            for (int j = 0; j < 4; ++j) {
                uint8_t sc = x[i].scales[is++];
                float dl = d * (float)(sc & 0xF);
                float ml = min * (float)(sc >> 4);
                for (int l = 0; l < 16; ++l) *y++ = dl * (float)((q[l] >> shift) & 3) - ml;

                sc = x[i].scales[is++];
                dl = d * (float)(sc & 0xF);
                ml = min * (float)(sc >> 4);
                for (int l = 0; l < 16; ++l) *y++ = dl * (float)((q[l + 16] >> shift) & 3) - ml;

                shift += 2;
            }
            q += 32;
            (void)n;
        }
    }
}

static void quantize_row_q1_0_ref(const float *x, ds4_block_q1_0 *y, int64_t k) {
    const int qk = DS4_Q1_REF_QK1_0;
    const int64_t nb = k / qk;
    for (int64_t i = 0; i < nb; i++) {
        float sum_abs = 0.0f;
        for (int j = 0; j < qk; j++) {
            sum_abs += fabsf(x[i * qk + j]);
        }
        y[i].d = ds4_f32_to_f16(sum_abs / (float)qk);
        memset(y[i].qs, 0, sizeof(y[i].qs));
        for (int j = 0; j < qk; ++j) {
            if (x[i * qk + j] >= 0.0f) {
                y[i].qs[j / 8] |= (uint8_t)(1u << (j % 8));
            }
        }
    }
}

static void dequantize_row_q1_0_ref(const ds4_block_q1_0 *x, float *y, int64_t k) {
    const int qk = DS4_Q1_REF_QK1_0;
    const int64_t nb = k / qk;
    for (int64_t i = 0; i < nb; i++) {
        const float d = ds4_f16_to_f32(x[i].d);
        for (int j = 0; j < qk; ++j) {
            const uint8_t bit = (x[i].qs[j / 8] >> (j % 8)) & 1u;
            y[i * qk + j] = bit ? d : -d;
        }
    }
}

int ds4_q1_ref_dequant_row(int type_id, const void *src, int64_t ncols, float *dst) {
    if (!src || !dst) return -1;
    if (ds4_q1_ref_row_size(type_id, ncols) == 0) return -2;
    switch (type_id) {
        case DS4_Q1_REF_TYPE_IQ2_XXS:
            dequantize_row_iq2_xxs((const ds4_block_iq2_xxs *)src, dst, ncols);
            return 0;
        case DS4_Q1_REF_TYPE_Q2_K:
            dequantize_row_q2_K((const ds4_block_q2_K *)src, dst, ncols);
            return 0;
        default:
            return -3;
    }
}

int ds4_q1_ref_quantize_row_q1_0(const float *src, int64_t ncols, void *dst) {
    if (!src || !dst) return -1;
    if (ds4_q1_ref_row_size(DS4_Q1_REF_TYPE_Q1_0, ncols) == 0) return -2;
    quantize_row_q1_0_ref(src, (ds4_block_q1_0 *)dst, ncols);
    return 0;
}

int ds4_q1_ref_dequant_row_q1_0(const void *src, int64_t ncols, float *dst) {
    if (!src || !dst) return -1;
    if (ds4_q1_ref_row_size(DS4_Q1_REF_TYPE_Q1_0, ncols) == 0) return -2;
    dequantize_row_q1_0_ref((const ds4_block_q1_0 *)src, dst, ncols);
    return 0;
}

int ds4_q1_ref_convert_rows_to_q1_0(
        int type_id,
        const void *src,
        size_t src_size,
        int64_t nrows,
        int64_t ncols,
        void *dst,
        size_t dst_size) {
    if (!src || !dst || nrows <= 0 || ncols <= 0) return -1;
    const size_t src_row = ds4_q1_ref_row_size(type_id, ncols);
    const size_t dst_row = ds4_q1_ref_row_size(DS4_Q1_REF_TYPE_Q1_0, ncols);
    if (!src_row || !dst_row) return -2;
    if ((uint64_t)nrows > (uint64_t)SIZE_MAX / src_row ||
        (uint64_t)nrows > (uint64_t)SIZE_MAX / dst_row ||
        (uint64_t)ncols > (uint64_t)SIZE_MAX / sizeof(float)) {
        return -3;
    }
    const size_t expected_src = src_row * (size_t)nrows;
    const size_t expected_dst = dst_row * (size_t)nrows;
    if (src_size != expected_src || dst_size != expected_dst) return -3;

    float *row = (float *)malloc((size_t)ncols * sizeof(float));
    if (!row) return -4;
    const uint8_t *s = (const uint8_t *)src;
    uint8_t *d = (uint8_t *)dst;
    for (int64_t r = 0; r < nrows; ++r) {
        const int rc = ds4_q1_ref_dequant_row(type_id, s + src_row * (size_t)r, ncols, row);
        if (rc != 0) {
            free(row);
            return rc;
        }
        quantize_row_q1_0_ref(row, (ds4_block_q1_0 *)(d + dst_row * (size_t)r), ncols);
    }
    free(row);
    return 0;
}
