/* =====================================================================
 * IQ2/Q2_K REAL-KERNEL ZERO-COPY MICROBENCH  (standalone)
 * ---------------------------------------------------------------------
 * Purpose: re-run the zero-copy GO/NO-GO gate with the ACTUAL runtime
 *          kernels (66-byte IQ2_XXS blocks for gate/up, 84-byte Q2_K
 *          blocks for down) instead of the linear int8 kernel used in
 *          .microbench/zerocopy.
 *
 * Kernels below marked [VERBATIM] are byte-for-byte copies from
 *   ds4-p4a/ds4_cuda.cu
 * (only `static` / name decorations preserved; no logic simplified).
 *
 *   dev_f16_to_f32                            ds4_cuda.cu:22958
 *   dev_unpack_iq2_signs                      ds4_cuda.cu:22962
 *   dev_dot_q2_16                             ds4_cuda.cu:22979
 *   dev_iq2_i8x8_lut                          ds4_cuda.cu:22996
 *   dev_dot_iq2_xxs_q8_K_block_lut            ds4_cuda.cu:23011
 *   dev_dot_q2_K_q8_K_block                   ds4_cuda.cu:23269
 *   quarter_warp_sum_f32                      ds4_cuda.cu:23444
 *   q8_K_quantize_kernel                      ds4_cuda.cu:23453
 *   moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel   ds4_cuda.cu:24160
 *   moe_down_ptrs_masked_qwarp32_kernel             ds4_cuda.cu:25287
 *   cuda_block_q2_K / q8_K / iq2_xxs structs   ds4_cuda.cu:690-706
 *   ds4_iq2_tables_cuda.inc                    (copied verbatim)
 *
 * Real geometry (from ds4_cuda.cu:45011 + g7_runs/g75 receipts):
 *   expert_in_dim  = 4096   expert_mid_dim = 2048   out_dim = 4096
 *   gate_row_bytes = 16 * 66 = 1056     gate_expert_bytes = 2,162,688
 *   down_row_bytes =  8 * 84 =  672     down_expert_bytes = 2,752,512
 *   expert total   = gate+up+down       = 7,077,888 B  (matches the
 *                                         int8 stand-in of the old bench)
 *   arena layout: gate || up || down contiguous  (ds4_cuda.cu:30357-30360)
 *   launch shapes: gate/up  <<<(16,6),256>>>     (ds4_cuda.cu:43554/43562)
 *                  down     <<<(128,6),256>>>    (ds4_cuda.cu:43556/43697)
 * ===================================================================== */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cstdarg>
#include <vector>
#include <algorithm>
#include <chrono>

#define CUDA_QK_K 256

/* ---------------- [VERBATIM] block structs (ds4_cuda.cu:690-706) ------ */
typedef struct {
    uint8_t scales[CUDA_QK_K / 16];
    uint8_t qs[CUDA_QK_K / 4];
    uint16_t d;
    uint16_t dmin;
} cuda_block_q2_K;

typedef struct {
    float d;
    int8_t qs[CUDA_QK_K];
    int16_t bsums[CUDA_QK_K / 16];
} cuda_block_q8_K;

typedef struct {
    uint16_t d;
    uint16_t qs[CUDA_QK_K / 8];
} cuda_block_iq2_xxs;

static_assert(sizeof(cuda_block_iq2_xxs) == 66, "IQ2_XXS must be 66 bytes");
static_assert(sizeof(cuda_block_q2_K)    == 84, "Q2_K must be 84 bytes");

#include "ds4_iq2_tables_cuda.inc"   /* cuda_ksigns_iq2xs[128], cuda_iq2xxs_grid[256] */

/* ---------------- [VERBATIM] device helpers -------------------------- */
__device__ static float dev_f16_to_f32(uint16_t v) {
    return __half2float(*reinterpret_cast<const __half *>(&v));
}

__device__ __forceinline__ static uint32_t dev_unpack_iq2_signs(uint32_t v) {
    const uint32_t p = __popc(v) & 1u;
    const uint32_t s = v ^ (p << 7u);
    return s * 0x01010101u;
}

__device__ static int32_t dev_dot_q2_16(const uint8_t *q2, const int8_t *q8, int shift) {
    int32_t sum = 0;
    #pragma unroll
    for (uint32_t i = 0; i < 16; i += 4) {
        const int32_t v = (*(const int32_t *)(q2 + i) >> shift) & 0x03030303;
        sum = __dp4a(v, *(const int32_t *)(q8 + i), sum);
    }
    return sum;
}

__device__ __forceinline__ static void dev_iq2_i8x8_lut(
        const uint64_t *grid,
        const uint8_t *signs,
        uint8_t grid_idx,
        uint32_t sign_idx,
        int32_t *w0,
        int32_t *w1) {
    const uint32_t s = dev_unpack_iq2_signs(signs[sign_idx]);
    const int32_t sm0 = __vcmpne4(s & 0x08040201u, 0);
    const int32_t sm1 = __vcmpne4(s & 0x80402010u, 0);
    const uint64_t g = grid[grid_idx];
    *w0 = __vsub4((int32_t)(uint32_t)g ^ sm0, sm0);
    *w1 = __vsub4((int32_t)(uint32_t)(g >> 32) ^ sm1, sm1);
}

__device__ static float dev_dot_iq2_xxs_q8_K_block_lut(
        const cuda_block_iq2_xxs *x,
        const cuda_block_q8_K *y,
        const uint64_t *grid,
        const uint8_t *signs) {
    const float xd = dev_f16_to_f32(x->d);
    const uint16_t *q2 = x->qs;
    const int8_t *q8 = y->qs;
    int32_t bsum = 0;
    for (int ib32 = 0; ib32 < CUDA_QK_K / 32; ib32++) {
        const uint32_t aux0 = (uint32_t)q2[0] | ((uint32_t)q2[1] << 16);
        const uint32_t aux1 = (uint32_t)q2[2] | ((uint32_t)q2[3] << 16);
        q2 += 4;
        const int32_t ls = (int32_t)(2u * (aux1 >> 28) + 1u);
        int32_t w[8];
        dev_iq2_i8x8_lut(grid, signs, (uint8_t)(aux0 & 0xffu),           (aux1 >> 0)  & 127u, &w[0], &w[1]);
        dev_iq2_i8x8_lut(grid, signs, (uint8_t)((aux0 >> 8)  & 0xffu),   (aux1 >> 7)  & 127u, &w[2], &w[3]);
        dev_iq2_i8x8_lut(grid, signs, (uint8_t)((aux0 >> 16) & 0xffu),   (aux1 >> 14) & 127u, &w[4], &w[5]);
        dev_iq2_i8x8_lut(grid, signs, (uint8_t)((aux0 >> 24) & 0xffu),   (aux1 >> 21) & 127u, &w[6], &w[7]);
        int32_t sumi = 0;
        sumi = __dp4a(w[0], *(const int32_t *)(q8 + ib32 * 32u + 0),  sumi);
        sumi = __dp4a(w[1], *(const int32_t *)(q8 + ib32 * 32u + 4),  sumi);
        sumi = __dp4a(w[2], *(const int32_t *)(q8 + ib32 * 32u + 8),  sumi);
        sumi = __dp4a(w[3], *(const int32_t *)(q8 + ib32 * 32u + 12), sumi);
        sumi = __dp4a(w[4], *(const int32_t *)(q8 + ib32 * 32u + 16), sumi);
        sumi = __dp4a(w[5], *(const int32_t *)(q8 + ib32 * 32u + 20), sumi);
        sumi = __dp4a(w[6], *(const int32_t *)(q8 + ib32 * 32u + 24), sumi);
        sumi = __dp4a(w[7], *(const int32_t *)(q8 + ib32 * 32u + 28), sumi);
        bsum += sumi * ls;
    }
    return 0.125f * xd * y->d * (float)bsum;
}

__device__ static float dev_dot_q2_K_q8_K_block(const cuda_block_q2_K *x, const cuda_block_q8_K *y) {
    const uint8_t *q2 = x->qs;
    const int8_t *q8 = y->qs;
    const uint8_t *sc = x->scales;
    int summs = 0;
    for (int j = 0; j < 16; j++) summs += y->bsums[j] * (sc[j] >> 4);
    const float dall = y->d * dev_f16_to_f32(x->d);
    const float dmin = y->d * dev_f16_to_f32(x->dmin);
    int isum = 0;
    int is = 0;
    for (int k = 0; k < CUDA_QK_K / 128; k++) {
        int shift = 0;
        for (int j = 0; j < 4; j++) {
            int d = sc[is++] & 0x0f;
            isum += d * dev_dot_q2_16(q2, q8, shift);
            d = sc[is++] & 0x0f;
            isum += d * dev_dot_q2_16(q2 + 16, q8 + 16, shift);
            shift += 2;
            q8 += 32;
        }
        q2 += 32;
    }
    return dall * (float)isum - dmin * (float)summs;
}

__device__ static float quarter_warp_sum_f32(float v, uint32_t lane8) {
    uint32_t mask = 0xffu << (threadIdx.x & 24u);
    for (int offset = 4; offset > 0; offset >>= 1) {
        v += __shfl_down_sync(mask, v, offset, 8);
    }
    (void)lane8;
    return v;
}

/* ---------------- [VERBATIM] q8_K quantize (ds4_cuda.cu:23453) -------- */
__global__ static void q8_K_quantize_kernel(
        cuda_block_q8_K *out,
        const float *x,
        uint32_t in_dim,
        uint32_t n_rows,
        const uint32_t *route_hit_mask,
        uint32_t route_count,
        uint32_t select_hits) {
    uint32_t b = blockIdx.x;
    uint32_t row = blockIdx.y;
    if (row >= n_rows || b >= in_dim / CUDA_QK_K) return;
    if (route_hit_mask && route_count != 0u) {
        const uint32_t slot = row % route_count;
        const uint32_t is_hit = (*route_hit_mask >> slot) & 1u;
        if (is_hit != select_hits) return;
    }
    const float *xr = x + (uint64_t)row * in_dim + (uint64_t)b * CUDA_QK_K;
    cuda_block_q8_K *yb = out + (uint64_t)row * (in_dim / CUDA_QK_K) + b;
    __shared__ float abs_part[256];
    __shared__ float val_part[256];
    __shared__ float maxv_s;
    __shared__ float iscale_s;
    uint32_t tid = threadIdx.x;
    float v = tid < CUDA_QK_K ? xr[tid] : 0.0f;
    abs_part[tid] = tid < CUDA_QK_K ? fabsf(v) : 0.0f;
    val_part[tid] = v;
    __syncthreads();
    for (uint32_t stride = blockDim.x >> 1; stride > 0; stride >>= 1) {
        if (tid < stride && abs_part[tid + stride] > abs_part[tid]) {
            abs_part[tid] = abs_part[tid + stride];
            val_part[tid] = val_part[tid + stride];
        }
        __syncthreads();
    }
    float amax = abs_part[0];
    if (amax == 0.0f) {
        if (tid == 0) yb->d = 0.0f;
        if (tid < CUDA_QK_K) yb->qs[tid] = 0;
        if (tid < CUDA_QK_K / 16) yb->bsums[tid] = 0;
        return;
    }
    if (tid == 0) {
        maxv_s = val_part[0];
        iscale_s = -127.0f / maxv_s;
    }
    __syncthreads();
    if (tid < CUDA_QK_K) {
        int qv = (int)lrintf(iscale_s * xr[tid]);
        if (qv > 127) qv = 127;
        if (qv < -128) qv = -128;
        yb->qs[tid] = (int8_t)qv;
    }
    __syncthreads();
    if (tid < CUDA_QK_K / 16) {
        int sum = 0;
        for (int i = 0; i < 16; i++) sum += yb->qs[tid * 16 + i];
        yb->bsums[tid] = (int16_t)sum;
    }
    if (tid == 0) yb->d = 1.0f / iscale_s;
}

/* ---------------- [VERBATIM] gate/up decode (ds4_cuda.cu:24160) ------- */
__global__ static void moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel(
        float *gate_out,
        float *up_out,
        float *mid_out,
        const uint64_t *route_ptrs,
        const cuda_block_q8_K *xq,
        const float *weights,
        uint64_t gate_row_bytes,
        uint32_t xq_blocks,
        uint32_t expert_mid_dim,
        uint32_t n_expert,
        uint32_t write_aux,
        float clamp,
        const uint32_t *route_hit_mask,
        uint32_t select_hits) {
    uint32_t lane = threadIdx.x & 7u;
    uint32_t row_lane = threadIdx.x >> 3u;
    uint32_t slot = blockIdx.y;
    if (route_hit_mask) {
        const uint32_t is_hit = (*route_hit_mask >> slot) & 1u;
        if (is_hit != select_hits) return;
    }
    const cuda_block_q8_K *xqb = xq;
    __shared__ cuda_block_q8_K sxq[16];
    __shared__ uint64_t s_iq2_grid[256];
    __shared__ uint8_t s_iq2_signs[128];
    if (xq_blocks <= 16u) {
        for (uint32_t i = threadIdx.x; i < xq_blocks; i += blockDim.x) sxq[i] = xqb[i];
        for (uint32_t i = threadIdx.x; i < 256u; i += blockDim.x) s_iq2_grid[i] = cuda_iq2xxs_grid[i];
        for (uint32_t i = threadIdx.x; i < 128u; i += blockDim.x) s_iq2_signs[i] = cuda_ksigns_iq2xs[i];
        __syncthreads();
        xqb = sxq;
    }
    const char *gate_ptr = (const char *)(uintptr_t)route_ptrs[slot];
    const char *up_ptr = (const char *)(uintptr_t)route_ptrs[n_expert + slot];
    for (uint32_t rr = 0; rr < 4u; rr++) {
        uint32_t row = blockIdx.x * 128u + row_lane + rr * 32u;
        if (row >= expert_mid_dim) continue;
        const cuda_block_iq2_xxs *gr = (const cuda_block_iq2_xxs *)(gate_ptr + (uint64_t)row * gate_row_bytes);
        const cuda_block_iq2_xxs *ur = (const cuda_block_iq2_xxs *)(up_ptr + (uint64_t)row * gate_row_bytes);
        float gate = 0.0f;
        float up = 0.0f;
        for (uint32_t b = lane; b < xq_blocks; b += 8u) {
            gate += dev_dot_iq2_xxs_q8_K_block_lut(gr + b, xqb + b, s_iq2_grid, s_iq2_signs);
            up += dev_dot_iq2_xxs_q8_K_block_lut(ur + b, xqb + b, s_iq2_grid, s_iq2_signs);
        }
        gate = quarter_warp_sum_f32(gate, lane);
        up = quarter_warp_sum_f32(up, lane);
        if (lane == 0) {
            if (clamp > 1.0e-6f) {
                if (gate > clamp) gate = clamp;
                if (up > clamp) up = clamp;
                if (up < -clamp) up = -clamp;
            }
            const uint64_t off = (uint64_t)slot * expert_mid_dim + row;
            if (write_aux) {
                gate_out[off] = gate;
                up_out[off] = up;
            }
            mid_out[off] = (gate / (1.0f + expf(-gate))) * up * weights[slot];
        }
    }
}

/* ---------------- [VERBATIM] down masked (ds4_cuda.cu:25287) ---------- */
__global__ static void moe_down_ptrs_masked_qwarp32_kernel(
        float *down_out,
        const uint64_t *down_ptrs,
        const cuda_block_q8_K *midq,
        const uint32_t *route_hit_mask,
        uint32_t select_hits,
        uint64_t down_row_bytes,
        uint32_t midq_blocks,
        uint32_t out_dim) {
    uint32_t lane = threadIdx.x & 7u;
    uint32_t row = blockIdx.x * 32u + (threadIdx.x >> 3u);
    uint32_t slot = blockIdx.y;
    if (row >= out_dim) return;
    const uint32_t is_hit = (*route_hit_mask >> slot) & 1u;
    if (is_hit != select_hits) return;
    const char *down_ptr = (const char *)(uintptr_t)down_ptrs[slot];
    const cuda_block_q2_K *wr =
        (const cuda_block_q2_K *)(down_ptr + (uint64_t)row * down_row_bytes);
    const cuda_block_q8_K *xq = midq + (uint64_t)slot * midq_blocks;
    float acc = 0.0f;
    for (uint32_t b = lane; b < midq_blocks; b += 8u) {
        acc += dev_dot_q2_K_q8_K_block(wr + b, xq + b);
    }
    acc = quarter_warp_sum_f32(acc, lane);
    if (lane == 0) down_out[(uint64_t)slot * out_dim + row] = acc;
}

/* ---------------- [VARIANT] gate/up, parametric rows-per-block --------
 * Identical dequant / addressing / reduction; ONLY the row->block
 * decomposition changes (RR rows per row_lane instead of the hard-coded 4).
 * RR=4 reproduces the verbatim kernel exactly (used as an equivalence check).
 * RR=1 -> 4x more blocks -> 4x more warps in flight to hide PCIe latency. */
template<uint32_t RR>
__global__ static void VARIANT_gate_up_rr_kernel(
        float *gate_out,
        float *up_out,
        float *mid_out,
        const uint64_t *route_ptrs,
        const cuda_block_q8_K *xq,
        const float *weights,
        uint64_t gate_row_bytes,
        uint32_t xq_blocks,
        uint32_t expert_mid_dim,
        uint32_t n_expert,
        uint32_t write_aux,
        float clamp,
        const uint32_t *route_hit_mask,
        uint32_t select_hits) {
    uint32_t lane = threadIdx.x & 7u;
    uint32_t row_lane = threadIdx.x >> 3u;
    uint32_t slot = blockIdx.y;
    if (route_hit_mask) {
        const uint32_t is_hit = (*route_hit_mask >> slot) & 1u;
        if (is_hit != select_hits) return;
    }
    const cuda_block_q8_K *xqb = xq;
    __shared__ cuda_block_q8_K sxq[16];
    __shared__ uint64_t s_iq2_grid[256];
    __shared__ uint8_t s_iq2_signs[128];
    if (xq_blocks <= 16u) {
        for (uint32_t i = threadIdx.x; i < xq_blocks; i += blockDim.x) sxq[i] = xqb[i];
        for (uint32_t i = threadIdx.x; i < 256u; i += blockDim.x) s_iq2_grid[i] = cuda_iq2xxs_grid[i];
        for (uint32_t i = threadIdx.x; i < 128u; i += blockDim.x) s_iq2_signs[i] = cuda_ksigns_iq2xs[i];
        __syncthreads();
        xqb = sxq;
    }
    const char *gate_ptr = (const char *)(uintptr_t)route_ptrs[slot];
    const char *up_ptr = (const char *)(uintptr_t)route_ptrs[n_expert + slot];
    for (uint32_t rr = 0; rr < RR; rr++) {
        uint32_t row = blockIdx.x * (32u * RR) + row_lane + rr * 32u;
        if (row >= expert_mid_dim) continue;
        const cuda_block_iq2_xxs *gr = (const cuda_block_iq2_xxs *)(gate_ptr + (uint64_t)row * gate_row_bytes);
        const cuda_block_iq2_xxs *ur = (const cuda_block_iq2_xxs *)(up_ptr + (uint64_t)row * gate_row_bytes);
        float gate = 0.0f;
        float up = 0.0f;
        for (uint32_t b = lane; b < xq_blocks; b += 8u) {
            gate += dev_dot_iq2_xxs_q8_K_block_lut(gr + b, xqb + b, s_iq2_grid, s_iq2_signs);
            up += dev_dot_iq2_xxs_q8_K_block_lut(ur + b, xqb + b, s_iq2_grid, s_iq2_signs);
        }
        gate = quarter_warp_sum_f32(gate, lane);
        up = quarter_warp_sum_f32(up, lane);
        if (lane == 0) {
            if (clamp > 1.0e-6f) {
                if (gate > clamp) gate = clamp;
                if (up > clamp) up = clamp;
                if (up < -clamp) up = -clamp;
            }
            const uint64_t off = (uint64_t)slot * expert_mid_dim + row;
            if (write_aux) {
                gate_out[off] = gate;
                up_out[off] = up;
            }
            mid_out[off] = (gate / (1.0f + expf(-gate))) * up * weights[slot];
        }
    }
}

/* ---------------- [VARIANT] down, parametric rows-per-block ----------- */
template<uint32_t ROWS>
__global__ static void VARIANT_down_rows_kernel(
        float *down_out,
        const uint64_t *down_ptrs,
        const cuda_block_q8_K *midq,
        const uint32_t *route_hit_mask,
        uint32_t select_hits,
        uint64_t down_row_bytes,
        uint32_t midq_blocks,
        uint32_t out_dim) {
    uint32_t lane = threadIdx.x & 7u;
    uint32_t row = blockIdx.x * ROWS + (threadIdx.x >> 3u);
    uint32_t slot = blockIdx.y;
    if (row >= out_dim) return;
    const uint32_t is_hit = (*route_hit_mask >> slot) & 1u;
    if (is_hit != select_hits) return;
    const char *down_ptr = (const char *)(uintptr_t)down_ptrs[slot];
    const cuda_block_q2_K *wr =
        (const cuda_block_q2_K *)(down_ptr + (uint64_t)row * down_row_bytes);
    const cuda_block_q8_K *xq = midq + (uint64_t)slot * midq_blocks;
    float acc = 0.0f;
    for (uint32_t b = lane; b < midq_blocks; b += 8u) {
        acc += dev_dot_q2_K_q8_K_block(wr + b, xq + b);
    }
    acc = quarter_warp_sum_f32(acc, lane);
    if (lane == 0) down_out[(uint64_t)slot * out_dim + row] = acc;
}

/* ---------------- [CONTROL] coalesced streaming reader -----------------
 * NOT a runtime kernel. Reads exactly the same expert bytes from exactly
 * the same pool, but with perfectly coalesced 16-byte loads. Its only job
 * is to prove that the memory form (mapped host RAM) still delivers full
 * PCIe bandwidth, so that any shortfall of the real kernels is attributable
 * to their access granularity and not to the harness or the allocation. */
__global__ static void CONTROL_stream_uint4_kernel(
        float *out,
        const uint64_t *ptrs,
        uint64_t expert_bytes,
        uint32_t n_expert) {
    const uint32_t slot = blockIdx.y;
    const uint4 *src = (const uint4 *)(uintptr_t)ptrs[slot];
    const uint64_t n4 = expert_bytes / 16u;
    uint32_t acc = 0;
    for (uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x; i < n4;
         i += (uint64_t)gridDim.x * blockDim.x) {
        uint4 v = src[i];
        acc += v.x + v.y + v.z + v.w;
    }
    atomicAdd(out + slot * n_expert, (float)(acc & 0xffffu));
}

/* ===================================================================== */
/*                          HOST HARNESS                                 */
/* ===================================================================== */

#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { \
    fprintf(stderr, "CUDA ERROR %s:%d %s -> %s\n", __FILE__, __LINE__, #x, \
            cudaGetErrorString(e_)); exit(1);} } while(0)

static FILE *g_out = NULL;
static void emit(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt); vprintf(fmt, ap); va_end(ap);
    if (g_out) { va_start(ap, fmt); vfprintf(g_out, fmt, ap); va_end(ap); fflush(g_out); }
    fflush(stdout);
}

/* real geometry */
static const uint32_t EXPERT_IN_DIM  = 4096;
static const uint32_t EXPERT_MID_DIM = 2048;
static const uint32_t OUT_DIM        = 4096;
static const uint32_t XQ_BLOCKS      = EXPERT_IN_DIM  / CUDA_QK_K;   /* 16 */
static const uint32_t MIDQ_BLOCKS    = EXPERT_MID_DIM / CUDA_QK_K;   /* 8  */
static const uint64_t GATE_ROW_BYTES = (uint64_t)XQ_BLOCKS   * sizeof(cuda_block_iq2_xxs); /* 1056 */
static const uint64_t DOWN_ROW_BYTES = (uint64_t)MIDQ_BLOCKS * sizeof(cuda_block_q2_K);    /*  672 */
static const uint64_t GATE_EXPERT_BYTES = GATE_ROW_BYTES * EXPERT_MID_DIM;  /* 2,162,688 */
static const uint64_t DOWN_EXPERT_BYTES = DOWN_ROW_BYTES * OUT_DIM;         /* 2,752,512 */
static const uint64_t EXPERT_BYTES = 2ull * GATE_EXPERT_BYTES + DOWN_EXPERT_BYTES; /* 7,077,888 */

static const uint32_t N_EXPERT   = 6;    /* routes per layer (kernel blockIdx.y) */
static const uint32_t POOL_EXP   = 64;   /* rotating pool */
static const uint32_t N_GROUPS   = POOL_EXP / N_EXPERT;   /* 10 groups of 6 */
static const int WARMUP = 3;
static const int ITERS  = 20;

/* extrapolation bases */
static const double EXP_PER_TOKEN_MISS = 137.6; /* RAM-arena misses = patch perimeter */
static const double EXP_PER_TOKEN_OLD  = 188.5; /* base used by the int8 bench */

/* -------- deterministic pseudo-random fill -------- */
static uint32_t rng_state = 0x13579BDFu;
static inline uint32_t rnd32() {
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 17; rng_state ^= rng_state << 5;
    return rng_state;
}
static inline uint16_t f2h(float f) { __half h = __float2half(f); uint16_t u; memcpy(&u, &h, 2); return u; }

static void fill_expert_pool(char *base) {
    for (uint32_t e = 0; e < POOL_EXP; e++) {
        char *ep = base + (uint64_t)e * EXPERT_BYTES;
        /* gate + up : IQ2_XXS rows */
        for (int gu = 0; gu < 2; gu++) {
            char *w = ep + (uint64_t)gu * GATE_EXPERT_BYTES;
            for (uint32_t row = 0; row < EXPERT_MID_DIM; row++) {
                cuda_block_iq2_xxs *blk = (cuda_block_iq2_xxs *)(w + (uint64_t)row * GATE_ROW_BYTES);
                for (uint32_t b = 0; b < XQ_BLOCKS; b++) {
                    blk[b].d = f2h(0.004f + 0.0005f * (float)(rnd32() & 15u));
                    for (uint32_t q = 0; q < CUDA_QK_K / 8; q++) blk[b].qs[q] = (uint16_t)(rnd32() & 0xffffu);
                }
            }
        }
        /* down : Q2_K rows */
        char *w = ep + 2ull * GATE_EXPERT_BYTES;
        for (uint32_t row = 0; row < OUT_DIM; row++) {
            cuda_block_q2_K *blk = (cuda_block_q2_K *)(w + (uint64_t)row * DOWN_ROW_BYTES);
            for (uint32_t b = 0; b < MIDQ_BLOCKS; b++) {
                for (uint32_t s = 0; s < CUDA_QK_K / 16; s++) blk[b].scales[s] = (uint8_t)(rnd32() & 0xffu);
                for (uint32_t q = 0; q < CUDA_QK_K / 4;  q++) blk[b].qs[q]     = (uint8_t)(rnd32() & 0xffu);
                blk[b].d    = f2h(0.006f + 0.0004f * (float)(rnd32() & 15u));
                blk[b].dmin = f2h(0.002f + 0.0002f * (float)(rnd32() & 7u));
            }
        }
    }
}

/* -------- FNV-1a over a device buffer -------- */
static uint64_t checksum_dev(const void *dptr, size_t bytes) {
    std::vector<uint8_t> h(bytes);
    CK(cudaMemcpy(h.data(), dptr, bytes, cudaMemcpyDeviceToHost));
    uint64_t hsh = 1469598103934665603ull;
    for (size_t i = 0; i < bytes; i++) { hsh ^= h[i]; hsh *= 1099511628211ull; }
    return hsh;
}

struct Res { double med, mn, wall; };

template <class F>
static Res measure(F f) {
    cudaEvent_t a, b; CK(cudaEventCreate(&a)); CK(cudaEventCreate(&b));
    for (int i = 0; i < WARMUP; i++) { f(i); }
    CK(cudaDeviceSynchronize());
    std::vector<float> ms(ITERS);
    auto w0 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < ITERS; i++) {
        CK(cudaEventRecord(a));
        f(i);
        CK(cudaEventRecord(b));
        CK(cudaEventSynchronize(b));
        CK(cudaEventElapsedTime(&ms[i], a, b));
    }
    auto w1 = std::chrono::high_resolution_clock::now();
    std::vector<float> s = ms; std::sort(s.begin(), s.end());
    Res r;
    r.med  = 0.5 * (s[ITERS/2 - 1] + s[ITERS/2]);
    r.mn   = s[0];
    r.wall = std::chrono::duration<double, std::milli>(w1 - w0).count() / ITERS;
    CK(cudaEventDestroy(a)); CK(cudaEventDestroy(b));
    return r;
}

/* pointer table: [group][3*N_EXPERT] -> gate(6) up(6) down(6) */
static void build_ptr_table(std::vector<uint64_t> &tbl, char *dev_base) {
    tbl.resize((size_t)N_GROUPS * 3u * N_EXPERT);
    for (uint32_t g = 0; g < N_GROUPS; g++) {
        for (uint32_t s = 0; s < N_EXPERT; s++) {
            uint32_t e = (g * N_EXPERT + s) % POOL_EXP;
            char *ep = dev_base + (uint64_t)e * EXPERT_BYTES;
            tbl[(size_t)g * 3u * N_EXPERT + s]                = (uint64_t)(uintptr_t)(ep);
            tbl[(size_t)g * 3u * N_EXPERT + N_EXPERT + s]     = (uint64_t)(uintptr_t)(ep + GATE_EXPERT_BYTES);
            tbl[(size_t)g * 3u * N_EXPERT + 2u * N_EXPERT + s]= (uint64_t)(uintptr_t)(ep + 2ull * GATE_EXPERT_BYTES);
        }
    }
}

static const char *tag_of(int form) {
    return form == 0 ? "VRAM" : (form == 1 ? "ZERO-COPY(mapped RAM)" : "pinned->VRAM copy");
}

int main(int argc, char **argv) {
    const char *outfile = argc > 1 ? argv[1] : "results_stdout.txt";
    g_out = fopen(outfile, "a");

    CK(cudaSetDeviceFlags(cudaDeviceMapHost));
    cudaDeviceProp p; CK(cudaGetDeviceProperties(&p, 0));

    emit("=====================================================================\n");
    emit(" IQ2/Q2_K REAL-KERNEL ZERO-COPY MICROBENCH -- MoE expert delivery\n");
    emit("=====================================================================\n");
    emit("device                : %s (sm_%d%d, %d SMs)\n", p.name, p.major, p.minor, p.multiProcessorCount);
    emit("L2 cache              : %.2f MB   maxThreadsPerSM %d   sharedPerSM %zu KB\n",
         p.l2CacheSize / 1048576.0, p.maxThreadsPerMultiProcessor, (size_t)(p.sharedMemPerMultiprocessor / 1024));
    emit("canMapHostMemory      : %d   unifiedAddressing: %d   asyncEngines: %d\n",
         p.canMapHostMemory, p.unifiedAddressing, p.asyncEngineCount);
    emit("geometry              : in=%u mid=%u out=%u | gate_row=%llu B (16x66) down_row=%llu B (8x84)\n",
         EXPERT_IN_DIM, EXPERT_MID_DIM, OUT_DIM,
         (unsigned long long)GATE_ROW_BYTES, (unsigned long long)DOWN_ROW_BYTES);
    emit("expert bytes          : gate %llu + up %llu + down %llu = %llu B\n",
         (unsigned long long)GATE_EXPERT_BYTES, (unsigned long long)GATE_EXPERT_BYTES,
         (unsigned long long)DOWN_EXPERT_BYTES, (unsigned long long)EXPERT_BYTES);
    emit("group                 : %u experts = %.2f MB ; pool %u experts = %.1f MB per form\n",
         N_EXPERT, N_EXPERT * EXPERT_BYTES / 1048576.0, POOL_EXP, POOL_EXP * EXPERT_BYTES / 1048576.0);
    emit("timing                : %d warmup + %d measured, median, cudaEvent (wall cross-check)\n", WARMUP, ITERS);
    emit("cache guard           : gate/up working set %.1f MB, down %.1f MB, both >> L2 %.2f MB;\n",
         N_EXPERT * 2.0 * GATE_EXPERT_BYTES / 1048576.0, N_EXPERT * DOWN_EXPERT_BYTES / 1048576.0,
         p.l2CacheSize / 1048576.0);
    emit("                        group rotates over %u groups (%u distinct experts) each iteration.\n",
         N_GROUPS, N_GROUPS * N_EXPERT);
    emit("---------------------------------------------------------------------\n");

    const uint64_t POOL_BYTES = (uint64_t)POOL_EXP * EXPERT_BYTES;

    /* ---- allocate the three memory forms ---- */
    emit("[alloc] pinned source pool  %.1f MB ...\n", POOL_BYTES / 1048576.0);
    char *h_pinned = NULL; CK(cudaHostAlloc((void **)&h_pinned, POOL_BYTES, cudaHostAllocDefault));
    emit("[alloc] mapped zero-copy pool %.1f MB ...\n", POOL_BYTES / 1048576.0);
    char *h_mapped = NULL; CK(cudaHostAlloc((void **)&h_mapped, POOL_BYTES, cudaHostAllocMapped));
    char *d_mapped = NULL; CK(cudaHostGetDevicePointer((void **)&d_mapped, h_mapped, 0));
    emit("[alloc] VRAM resident pool  %.1f MB ...\n", POOL_BYTES / 1048576.0);
    char *d_vram = NULL; CK(cudaMalloc((void **)&d_vram, POOL_BYTES));

    emit("[init]  filling pool with pseudorandom IQ2_XXS / Q2_K blocks ...\n");
    fill_expert_pool(h_pinned);
    memcpy(h_mapped, h_pinned, POOL_BYTES);
    CK(cudaMemcpy(d_vram, h_pinned, POOL_BYTES, cudaMemcpyHostToDevice));
    emit("[init]  done. all three memory forms hold identical bytes (memcmp %s).\n",
         memcmp(h_pinned, h_mapped, POOL_BYTES) == 0 ? "OK" : "MISMATCH");

    /* ---- staging buffer for the copy scenario (6 experts) ---- */
    char *d_stage = NULL; CK(cudaMalloc((void **)&d_stage, (uint64_t)N_EXPERT * EXPERT_BYTES));

    /* ---- activations / outputs ---- */
    cuda_block_q8_K *d_xq = NULL;  CK(cudaMalloc((void **)&d_xq, (size_t)XQ_BLOCKS * sizeof(cuda_block_q8_K)));
    {
        std::vector<cuda_block_q8_K> hx(XQ_BLOCKS);
        for (uint32_t b = 0; b < XQ_BLOCKS; b++) {
            hx[b].d = 0.021f;
            for (int i = 0; i < CUDA_QK_K; i++) hx[b].qs[i] = (int8_t)((int)(rnd32() & 0xffu) - 128);
            for (int j = 0; j < CUDA_QK_K / 16; j++) {
                int s = 0; for (int i = 0; i < 16; i++) s += hx[b].qs[j * 16 + i];
                hx[b].bsums[j] = (int16_t)s;
            }
        }
        CK(cudaMemcpy(d_xq, hx.data(), (size_t)XQ_BLOCKS * sizeof(cuda_block_q8_K), cudaMemcpyHostToDevice));
    }
    cuda_block_q8_K *d_midq = NULL; CK(cudaMalloc((void **)&d_midq, (size_t)N_EXPERT * MIDQ_BLOCKS * sizeof(cuda_block_q8_K)));
    float *d_gate = NULL, *d_up = NULL, *d_mid = NULL, *d_down = NULL, *d_w = NULL;
    CK(cudaMalloc((void **)&d_gate, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
    CK(cudaMalloc((void **)&d_up,   (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
    CK(cudaMalloc((void **)&d_mid,  (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
    CK(cudaMalloc((void **)&d_down, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
    CK(cudaMalloc((void **)&d_w,    (size_t)N_EXPERT * sizeof(float)));
    { std::vector<float> w(N_EXPERT, 1.0f / (float)N_EXPERT);
      CK(cudaMemcpy(d_w, w.data(), N_EXPERT * sizeof(float), cudaMemcpyHostToDevice)); }
    uint32_t *d_mask = NULL; CK(cudaMalloc((void **)&d_mask, sizeof(uint32_t)));
    CK(cudaMemset(d_mask, 0, sizeof(uint32_t)));   /* all slots = miss -> select_hits=0 passes */

    /* ---- device pointer tables, one per memory form ---- */
    std::vector<uint64_t> t_vram, t_map, t_stage;
    build_ptr_table(t_vram, d_vram);
    build_ptr_table(t_map,  d_mapped);
    /* staging table: the 6 experts land contiguously at d_stage */
    t_stage.resize((size_t)3u * N_EXPERT);
    for (uint32_t s = 0; s < N_EXPERT; s++) {
        char *ep = d_stage + (uint64_t)s * EXPERT_BYTES;
        t_stage[s]                 = (uint64_t)(uintptr_t)ep;
        t_stage[N_EXPERT + s]      = (uint64_t)(uintptr_t)(ep + GATE_EXPERT_BYTES);
        t_stage[2u * N_EXPERT + s] = (uint64_t)(uintptr_t)(ep + 2ull * GATE_EXPERT_BYTES);
    }
    uint64_t *dp_vram = NULL, *dp_map = NULL, *dp_stage = NULL;
    CK(cudaMalloc((void **)&dp_vram, t_vram.size() * 8)); CK(cudaMemcpy(dp_vram, t_vram.data(), t_vram.size() * 8, cudaMemcpyHostToDevice));
    CK(cudaMalloc((void **)&dp_map,  t_map.size()  * 8)); CK(cudaMemcpy(dp_map,  t_map.data(),  t_map.size()  * 8, cudaMemcpyHostToDevice));
    CK(cudaMalloc((void **)&dp_stage,t_stage.size()* 8)); CK(cudaMemcpy(dp_stage,t_stage.data(),t_stage.size()* 8, cudaMemcpyHostToDevice));

    const dim3 qgrid((EXPERT_MID_DIM + 127u) / 128u, N_EXPERT, 1);     /* (16,6) */
    const dim3 dgrid((OUT_DIM + 31u) / 32u, N_EXPERT, 1);              /* (128,6) */
    const dim3 midqgrid(MIDQ_BLOCKS, N_EXPERT, 1);                     /* (8,6)  */
    const float CLAMP = 0.0f;
    const uint32_t WRITE_AUX = 1u;

    /* occupancy report */
    {
        int nb = 0;
        CK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&nb, moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel, 256, 0));
        emit("[occ]   gate/up verbatim: %d blocks/SM resident max -> grid %ux%u = %u blocks = %.1f warps/SM offered\n",
             nb, qgrid.x, qgrid.y, qgrid.x * qgrid.y, qgrid.x * qgrid.y * 8.0 / p.multiProcessorCount);
        CK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&nb, moe_down_ptrs_masked_qwarp32_kernel, 256, 0));
        emit("[occ]   down    verbatim: %d blocks/SM resident max -> grid %ux%u = %u blocks = %.1f warps/SM offered\n",
             nb, dgrid.x, dgrid.y, dgrid.x * dgrid.y, dgrid.x * dgrid.y * 8.0 / p.multiProcessorCount);
        CK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&nb, VARIANT_gate_up_rr_kernel<1>, 256, 0));
        emit("[occ]   gate/up RR=1    : %d blocks/SM resident max -> grid %ux%u = %u blocks = %.1f warps/SM offered\n",
             nb, EXPERT_MID_DIM / 32u, N_EXPERT, (EXPERT_MID_DIM / 32u) * N_EXPERT,
             (EXPERT_MID_DIM / 32u) * N_EXPERT * 8.0 / p.multiProcessorCount);
    }
    emit("---------------------------------------------------------------------\n");

    /* seed midq once (fixed input for the standalone down kernel) */
    {
        std::vector<float> hmid((size_t)N_EXPERT * EXPERT_MID_DIM);
        for (size_t i = 0; i < hmid.size(); i++) hmid[i] = 0.05f * (float)((int)(rnd32() % 200u) - 100) / 100.0f;
        CK(cudaMemcpy(d_mid, hmid.data(), hmid.size() * sizeof(float), cudaMemcpyHostToDevice));
        q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
        CK(cudaDeviceSynchronize());
    }

    struct Row { char name[80]; double ms; double gbs; double ms_exp; double ms_tok_miss; double ms_tok_old; uint64_t chk; };
    std::vector<Row> rows;
    auto record = [&](const char *name, Res r, double bytes_per_call, uint64_t chk) {
        Row row; snprintf(row.name, sizeof(row.name), "%s", name);
        row.ms = r.med;
        row.gbs = bytes_per_call / (r.med * 1e-3) / 1e9;
        /* ms/expert is always normalised over the 6 experts of the group */
        row.ms_exp = r.med / (double)N_EXPERT;
        row.ms_tok_miss = row.ms_exp * EXP_PER_TOKEN_MISS;
        row.ms_tok_old  = row.ms_exp * EXP_PER_TOKEN_OLD;
        row.chk = chk;
        rows.push_back(row);
        emit("  %-44s ev_med %8.3f ms | min %8.3f | wall %8.3f | %7.2f GB/s | %7.4f ms/exp | -> %7.1f ms/tok(137.6) | chk %016llx\n",
             name, r.med, r.mn, r.wall, row.gbs, row.ms_exp, row.ms_tok_miss, (unsigned long long)chk);
    };

    const double GU_BYTES = 2.0 * (double)GATE_EXPERT_BYTES * N_EXPERT;   /* gate+up, 6 experts */
    const double DN_BYTES = (double)DOWN_EXPERT_BYTES * N_EXPERT;
    const double ALL_BYTES = (double)EXPERT_BYTES * N_EXPERT;

    /* helper: run one fixed-group pass and checksum the output */
    auto chk_gu = [&](uint64_t *tbl) {
        CK(cudaMemset(d_mid, 0, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
        moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
            d_gate, d_up, d_mid, tbl, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
            EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        CK(cudaDeviceSynchronize());
        return checksum_dev(d_mid, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float));
    };
    auto chk_dn = [&](uint64_t *tbl) {
        CK(cudaMemset(d_down, 0, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
        moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
            d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        CK(cudaDeviceSynchronize());
        return checksum_dev(d_down, (size_t)N_EXPERT * OUT_DIM * sizeof(float));
    };

    /* ================== K0 : coalesced control ================== */
    emit("K0  CONTROL coalesced uint4 streamer over the SAME pool (not a runtime kernel)\n");
    {
        dim3 cg(256, N_EXPERT, 1);
        Res rv = measure([&](int it) {
            uint64_t *tbl = dp_vram + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            CONTROL_stream_uint4_kernel<<<cg, 256>>>(d_gate, tbl, EXPERT_BYTES, N_EXPERT);
        });
        record("K0a CONTROL coalesced VRAM", rv, ALL_BYTES, 0);
        Res rm = measure([&](int it) {
            uint64_t *tbl = dp_map + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            CONTROL_stream_uint4_kernel<<<cg, 256>>>(d_gate, tbl, EXPERT_BYTES, N_EXPERT);
        });
        record("K0b CONTROL coalesced ZERO-COPY", rm, ALL_BYTES, 0);
    }

    /* ================== K1 / K2 : gate/up ================== */
    emit("K1/K2  gate/up  (moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel, 1 launch = 6 experts)\n");
    {
        Res r = measure([&](int it) {
            uint64_t *tbl = dp_vram + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
                d_gate, d_up, d_mid, tbl, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
                EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        });
        record("K1  gate/up VRAM", r, GU_BYTES, chk_gu(dp_vram));
    }
    {
        Res r = measure([&](int it) {
            uint64_t *tbl = dp_map + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
                d_gate, d_up, d_mid, tbl, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
                EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        });
        record("K2  gate/up ZERO-COPY (mapped RAM)", r, GU_BYTES, chk_gu(dp_map));
    }

    /* ================== K3 / K4 : down ================== */
    emit("K3/K4  down  (moe_down_ptrs_masked_qwarp32_kernel, 1 launch = 6 experts)\n");
    {
        Res r = measure([&](int it) {
            uint64_t *tbl = dp_vram + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
                d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        });
        record("K3  down VRAM", r, DN_BYTES, chk_dn(dp_vram));
    }
    {
        Res r = measure([&](int it) {
            uint64_t *tbl = dp_map + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
                d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        });
        record("K4  down ZERO-COPY (mapped RAM)", r, DN_BYTES, chk_dn(dp_map));
    }

    /* ================== K5 : realistic sequence ================== */
    emit("K5  realistic sequence gate/up -> q8_K quantize -> down, 6 experts\n");
    {
        Res r = measure([&](int it) {
            uint64_t *tbl = dp_vram + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
                d_gate, d_up, d_mid, tbl, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
                EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
            q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
            moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
                d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        });
        record("K5a full expert VRAM", r, ALL_BYTES, 0);
    }
    {
        Res r = measure([&](int it) {
            uint64_t *tbl = dp_map + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
                d_gate, d_up, d_mid, tbl, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
                EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
            q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
            moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
                d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        });
        record("K5b full expert ZERO-COPY", r, ALL_BYTES, 0);
    }
    /* K5 checksum: run the chain once from a fixed group on both forms */
    uint64_t k5_chk_vram, k5_chk_map;
    {
        auto chain = [&](uint64_t *tbl) {
            CK(cudaMemset(d_mid, 0, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
            CK(cudaMemset(d_down, 0, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
            moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
                d_gate, d_up, d_mid, tbl, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
                EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
            q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
            moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
                d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
            CK(cudaDeviceSynchronize());
            return checksum_dev(d_down, (size_t)N_EXPERT * OUT_DIM * sizeof(float));
        };
        k5_chk_vram = chain(dp_vram);
        k5_chk_map  = chain(dp_map);
        rows[rows.size()-2].chk = k5_chk_vram;
        rows[rows.size()-1].chk = k5_chk_map;
        emit("  K5 chain checksums: VRAM %016llx  ZERO-COPY %016llx  -> %s\n",
             (unsigned long long)k5_chk_vram, (unsigned long long)k5_chk_map,
             k5_chk_vram == k5_chk_map ? "IDENTICAL" : "MISMATCH!");
    }
    /* restore the fixed midq used by K3/K4 */
    CK(cudaDeviceSynchronize());

    /* ================== K6 : status quo (copy pinned->VRAM then compute) === */
    emit("K6  status quo: copy 6 experts pinned->VRAM, then the same two kernels\n");
    {
        Res r = measure([&](int it) {
            uint32_t g = (uint32_t)(it % N_GROUPS);
            for (uint32_t s = 0; s < N_EXPERT; s++) {
                uint32_t e = (g * N_EXPERT + s) % POOL_EXP;
                cudaMemcpyAsync(d_stage + (uint64_t)s * EXPERT_BYTES,
                                h_pinned + (uint64_t)e * EXPERT_BYTES,
                                EXPERT_BYTES, cudaMemcpyHostToDevice, 0);
            }
            moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
                d_gate, d_up, d_mid, dp_stage, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
                EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
            q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
            moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
                d_down, dp_stage + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        });
        /* checksum with group 0 staged */
        for (uint32_t s = 0; s < N_EXPERT; s++)
            CK(cudaMemcpy(d_stage + (uint64_t)s * EXPERT_BYTES, h_pinned + (uint64_t)s * EXPERT_BYTES,
                          EXPERT_BYTES, cudaMemcpyHostToDevice));
        CK(cudaMemset(d_mid, 0, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
        CK(cudaMemset(d_down, 0, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
        moe_gate_up_mid_decode_ptrs_lut_qwarp32_kernel<<<qgrid, 256>>>(
            d_gate, d_up, d_mid, dp_stage, d_xq, d_w, GATE_ROW_BYTES, XQ_BLOCKS,
            EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
        moe_down_ptrs_masked_qwarp32_kernel<<<dgrid, 256>>>(
            d_down, dp_stage + 2u * N_EXPERT, d_midq, d_mask, 0u, DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        CK(cudaDeviceSynchronize());
        record("K6  full expert copy pinned->VRAM + compute", r, ALL_BYTES,
               checksum_dev(d_down, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
    }

    /* re-seed the fixed midq for the variant section */
    {
        std::vector<float> hmid((size_t)N_EXPERT * EXPERT_MID_DIM);
        rng_state = 0x2468ACE0u;
        for (size_t i = 0; i < hmid.size(); i++) hmid[i] = 0.05f * (float)((int)(rnd32() % 200u) - 100) / 100.0f;
        CK(cudaMemcpy(d_mid, hmid.data(), hmid.size() * sizeof(float), cudaMemcpyHostToDevice));
        q8_K_quantize_kernel<<<midqgrid, 256>>>(d_midq, d_mid, EXPERT_MID_DIM, N_EXPERT, d_mask, N_EXPERT, 0u);
        CK(cudaDeviceSynchronize());
    }

    /* ================== K7 : occupancy variants ================== */
    emit("K7  occupancy variants (same dequant/addressing, different row->block split)\n");
    auto run_gu_variant = [&](const char *nm, uint64_t *base, int rr) {
        dim3 g(EXPERT_MID_DIM / (32u * (uint32_t)rr), N_EXPERT, 1);
        Res r = measure([&](int it) {
            uint64_t *tbl = base + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            if (rr == 1)
                VARIANT_gate_up_rr_kernel<1><<<g, 256>>>(d_gate, d_up, d_mid, tbl, d_xq, d_w,
                    GATE_ROW_BYTES, XQ_BLOCKS, EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
            else if (rr == 2)
                VARIANT_gate_up_rr_kernel<2><<<g, 256>>>(d_gate, d_up, d_mid, tbl, d_xq, d_w,
                    GATE_ROW_BYTES, XQ_BLOCKS, EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
            else
                VARIANT_gate_up_rr_kernel<4><<<g, 256>>>(d_gate, d_up, d_mid, tbl, d_xq, d_w,
                    GATE_ROW_BYTES, XQ_BLOCKS, EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        });
        /* checksum on a fixed group */
        CK(cudaMemset(d_mid, 0, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
        if (rr == 1)
            VARIANT_gate_up_rr_kernel<1><<<g, 256>>>(d_gate, d_up, d_mid, base, d_xq, d_w,
                GATE_ROW_BYTES, XQ_BLOCKS, EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        else if (rr == 2)
            VARIANT_gate_up_rr_kernel<2><<<g, 256>>>(d_gate, d_up, d_mid, base, d_xq, d_w,
                GATE_ROW_BYTES, XQ_BLOCKS, EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        else
            VARIANT_gate_up_rr_kernel<4><<<g, 256>>>(d_gate, d_up, d_mid, base, d_xq, d_w,
                GATE_ROW_BYTES, XQ_BLOCKS, EXPERT_MID_DIM, N_EXPERT, WRITE_AUX, CLAMP, d_mask, 0u);
        CK(cudaDeviceSynchronize());
        record(nm, r, GU_BYTES, checksum_dev(d_mid, (size_t)N_EXPERT * EXPERT_MID_DIM * sizeof(float)));
    };
    run_gu_variant("K7a gate/up RR=4 (== verbatim) VRAM", dp_vram, 4);
    run_gu_variant("K7b gate/up RR=4 (== verbatim) ZERO-COPY", dp_map, 4);
    run_gu_variant("K7c gate/up RR=2 (2x blocks) ZERO-COPY", dp_map, 2);
    run_gu_variant("K7d gate/up RR=1 (4x blocks) ZERO-COPY", dp_map, 1);
    run_gu_variant("K7e gate/up RR=1 (4x blocks) VRAM", dp_vram, 1);

    auto run_dn_variant = [&](const char *nm, uint64_t *base, int rows_pb) {
        dim3 g(OUT_DIM / (uint32_t)rows_pb, N_EXPERT, 1);
        Res r = measure([&](int it) {
            uint64_t *tbl = base + (size_t)(it % N_GROUPS) * 3u * N_EXPERT;
            if (rows_pb == 16)
                VARIANT_down_rows_kernel<16><<<g, 128>>>(d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u,
                    DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
            else
                VARIANT_down_rows_kernel<32><<<g, 256>>>(d_down, tbl + 2u * N_EXPERT, d_midq, d_mask, 0u,
                    DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        });
        CK(cudaMemset(d_down, 0, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
        if (rows_pb == 16)
            VARIANT_down_rows_kernel<16><<<g, 128>>>(d_down, base + 2u * N_EXPERT, d_midq, d_mask, 0u,
                DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        else
            VARIANT_down_rows_kernel<32><<<g, 256>>>(d_down, base + 2u * N_EXPERT, d_midq, d_mask, 0u,
                DOWN_ROW_BYTES, MIDQ_BLOCKS, OUT_DIM);
        CK(cudaDeviceSynchronize());
        record(nm, r, DN_BYTES, checksum_dev(d_down, (size_t)N_EXPERT * OUT_DIM * sizeof(float)));
    };
    run_dn_variant("K7f down ROWS=32 (== verbatim) ZERO-COPY", dp_map, 32);
    run_dn_variant("K7g down ROWS=16/128thr (2x blocks) ZERO-COPY", dp_map, 16);

    /* ================== K8 : raw PCIe ceiling ================== */
    emit("K8  raw PCIe reference (cudaMemcpy H2D, 384 MB pinned)\n");
    double pcie_gbs = 0.0;
    {
        const uint64_t nb = 402653184ull; /* 384 MiB */
        Res r = measure([&](int) { cudaMemcpy(d_vram, h_pinned, nb, cudaMemcpyHostToDevice); });
        pcie_gbs = (double)nb / (r.med * 1e-3) / 1e9;
        emit("  %-44s ev_med %8.3f ms | min %8.3f | wall %8.3f | %7.2f GB/s (PCIe peak)\n",
             "K8  cudaMemcpy H2D 384 MiB pinned", r.med, r.mn, r.wall, pcie_gbs);
        /* the pool in VRAM was just overwritten -> restore it */
        CK(cudaMemcpy(d_vram, h_pinned, POOL_BYTES, cudaMemcpyHostToDevice));
    }

    /* ================== SUMMARY ================== */
    emit("---------------------------------------------------------------------\n");
    emit("SUMMARY   (ms/expert normalised over the %u experts of one launch group)\n", N_EXPERT);
    emit("          extrapolation A: %.1f experts/token = RAM-arena misses (patch perimeter)\n", EXP_PER_TOKEN_MISS);
    emit("          extrapolation B: %.1f experts/token = base of the previous int8 bench\n", EXP_PER_TOKEN_OLD);
    emit("---------------------------------------------------------------------\n");
    emit("%-46s %9s %8s %11s %11s %11s\n", "scenario", "ms/6exp", "GB/s", "ms/expert", "ms/tok(137.6)", "ms/tok(188.5)");
    for (const Row &r : rows)
        emit("%-46s %9.3f %8.2f %11.4f %11.1f %11.1f\n", r.name, r.ms, r.gbs, r.ms_exp, r.ms_tok_miss, r.ms_tok_old);
    emit("---------------------------------------------------------------------\n");
    emit("PCIe ceiling measured this run: %.2f GB/s. Sanity: no scenario may exceed it.\n", pcie_gbs);
    for (const Row &r : rows)
        if (r.gbs > pcie_gbs * 1.02 && strstr(r.name, "VRAM") == NULL)
            emit("  !! SUSPECT: %s at %.2f GB/s exceeds the PCIe ceiling\n", r.name, r.gbs);
    emit("checksums (must be identical across memory forms for the same kernel):\n");
    for (const Row &r : rows) emit("  %-46s %016llx\n", r.name, (unsigned long long)r.chk);
    emit("=====================================================================\n");

    CK(cudaFreeHost(h_pinned)); CK(cudaFreeHost(h_mapped));
    CK(cudaFree(d_vram)); CK(cudaFree(d_stage));
    CK(cudaFree(d_xq)); CK(cudaFree(d_midq));
    CK(cudaFree(d_gate)); CK(cudaFree(d_up)); CK(cudaFree(d_mid)); CK(cudaFree(d_down));
    CK(cudaFree(d_w)); CK(cudaFree(d_mask));
    CK(cudaFree(dp_vram)); CK(cudaFree(dp_map)); CK(cudaFree(dp_stage));
    CK(cudaDeviceReset());
    if (g_out) fclose(g_out);
    return 0;
}
