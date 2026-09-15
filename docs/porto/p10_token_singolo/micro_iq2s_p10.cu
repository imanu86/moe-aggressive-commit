// P10 cella 3 - microbanco isolato del kernel mul_mat_vec_q<iq2_s> a UNA RIGA.
//
// Riproduce ESATTAMENTE una delle 47 chiamate per forward misurate in P9:
//   x    = esperti gate/up iq2_s, [n_embd=2560, n_ff_exp=640, n_expert]
//   y    = una riga di attivazioni q8_1 (80 blocchi da 32)
//   ids  = 10 esperti scelti
//   dst  = [640, 10]
//   gate+up fusi (has_fusion=true, use_gate=true, SWIGLU)
// Geometria identica a quella che il dispatcher sceglie sulla 3060 (cc 8.6,
// tabella GENERIC, has_ids, ncols_dst=1): nwarps=4, small_k=TRUE -> rpb=4.
// Byte letti per lancio: 10 esperti * 640 righe * 10 blocchi * 82 B * 2 = 10,01 MiB.
//
// Le varianti CANDIDATE non cambiano MAI l'ordine delle somme: cambiano solo
// da dove vengono letti i byte e quanti registri il compilatore puo' usare.
// Le ABLAZIONI (bit 4, 8) cambiano il risultato: servono solo a diagnosticare,
// non sono adottabili, e il confronto bit a bit su di esse e' privo di senso.
//
// Compilazione: compila_micro_p10.ps1

#define GGML_COMMON_DECL_CUDA
#define GGML_COMMON_IMPL_CUDA
#include "ggml-common.h"

#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <string>
#include <vector>
#include <algorithm>

#define CHK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { \
    printf("ERRORE CUDA %s:%d -> %s\n", __FILE__, __LINE__, cudaGetErrorString(e_)); exit(1); } } while (0)

// ---------------------------------------------------------------- forme reali
static const int N_EMBD    = 2560;          // ncols_x
static const int N_FF_EXP  = 640;           // nrows_x
static const int N_POOL    = 48;            // esperti tenuti in VRAM nel banco
static const int N_USED    = 10;            // esperti per token
static const int QI2S      = QK_K / 16;     // 16
static const int VDR       = 2;
static const int WSZ       = 32;
static const int NWARPS    = 4;
static const int RPB       = 4;             // small_k -> rows_per_cuda_block = nwarps

// ------------------------------------------------------------- le varianti
#define VAR_BASE      0
#define VAR_GRIGLIA   1   // tabella dei codici in memoria condivisa
#define VAR_ATTIV     2   // attivazioni q8_1 in memoria condivisa (passo 9 int)
#define ABL_NOGRID    4   // ABLAZIONE: niente ricerca in tabella (indice fisso)
#define ABL_NOSEGNI   8   // ABLAZIONE: niente aritmetica dei segni
#define VAR_UNROLL1  16   // il ciclo sulle righe NON srotolato (stesso ordine delle somme)
#define VAR_UNROLL2  32   // il ciclo sulle righe srotolato per due
#define VAR_GRID32   64   // griglia in shared come due vettori di uint32 (lo/hi)
#define VAR_LDCS    128   // pesi letti con .cs (sfratto per primo dalla L1)
#define VAR_LDCG    256   // pesi letti con .cg (non passano per la L1)

// --------------------------------------------------------------- helper ggml
static __device__ __forceinline__ int get_int_b2(const void * x, const int & i32) {
    const uint16_t * x16 = (const uint16_t *) x;
    int x32  = x16[2*i32 + 0] <<  0;
    x32     |= x16[2*i32 + 1] << 16;
    return x32;
}
static __device__ __forceinline__ int get_int_b4(const void * x, const int & i32) {
    return ((const int *) x)[i32];
}
// lettura dei byte dei pesi: gli esperti non hanno NESSUN riuso dentro il kernel,
// quindi la politica di cache e' libera senza cambiare un bit del valore letto.
template <int VAR>
static __device__ __forceinline__ unsigned short ld_u16(const unsigned short * p) {
    if (VAR & VAR_LDCG) return __ldcg(p);
    if (VAR & VAR_LDCS) return __ldcs(p);
    return *p;
}
template <int VAR>
static __device__ __forceinline__ unsigned char ld_u8(const unsigned char * p) {
    if (VAR & VAR_LDCG) return __ldcg(p);
    if (VAR & VAR_LDCS) return __ldcs(p);
    return *p;
}
template <int VAR>
static __device__ __forceinline__ int get_int_b2_(const void * x, const int & i32) {
    const unsigned short * x16 = (const unsigned short *) x;
    int x32  = ld_u16<VAR>(x16 + 2*i32 + 0) <<  0;
    x32     |= ld_u16<VAR>(x16 + 2*i32 + 1) << 16;
    return x32;
}
static __device__ __forceinline__ int dp4a_(const int a, const int b, int c) {
    return __dp4a(a, b, c);
}
template<int width = 32>
static __device__ __forceinline__ float warp_reduce_sum_(float x) {
#pragma unroll
    for (int offset = width/2; offset > 0; offset >>= 1) {
        x += __shfl_xor_sync(0xffffffff, x, offset, width);
    }
    return x;
}
static __device__ __forceinline__ float silu_(float x) {
    return x / (1.0f + expf(-x));
}


struct sh_t {
    const uint64_t * grid;
    const uint32_t * g_lo;
    const uint32_t * g_hi;
    const int      * y_qs;
    const float    * y_d;
    int              y_base;
};

template <int VAR>
static __device__ __forceinline__ float vec_dot_iq2_s(
        const void * __restrict__ vbq, const block_q8_1 * __restrict__ bq8_1,
        const int & kbx, const int & iqs, const sh_t & sh) {

    const block_iq2_s * bq2 = (const block_iq2_s *) vbq + kbx;

    const int       qs_packed = get_int_b2_<VAR>(bq2->qs, iqs/2);
    const uint8_t * qs        = (const uint8_t *) &qs_packed;

    const int qh = ld_u8<VAR>((const unsigned char *) bq2->qh + iqs/2);

    const int       signs_packed_32 = get_int_b2_<VAR>(bq2->qs, QK_K/32 + iqs/2);
    const uint8_t * signs_packed_8  = (const uint8_t *) &signs_packed_32;

    const int sc  = ld_u8<VAR>((const unsigned char *) bq2->scales + iqs/2);
    const int ls0 = sc & 0x0F;
    const int ls1 = sc >> 4;

    int sumi0 = 0;
    int sumi1 = 0;
#pragma unroll
    for (int l0 = 0; l0 < 8; l0 += 2) {
        const int idx = (VAR & ABL_NOGRID) ? (qs_packed & 0x1) : (qs[l0/2] | ((qh << (8-l0)) & 0x300));
        int gl, gh;
        if (VAR & VAR_GRID32) {
            gl = (int) sh.g_lo[idx];
            gh = (int) sh.g_hi[idx];
        } else {
            const int * grid_pos = (const int *)(sh.grid + idx);
            gl = grid_pos[0];
            gh = grid_pos[1];
        }

        int signs0 = 0, signs1 = 0;
        if (!(VAR & ABL_NOSEGNI)) {
            signs0 = __vcmpne4(((signs_packed_8[l0/2] & 0x03) << 7) | ((signs_packed_8[l0/2] & 0x0C) << 21), 0x00000000);
            signs1 = __vcmpne4(((signs_packed_8[l0/2] & 0x30) << 3) | ((signs_packed_8[l0/2] & 0xC0) << 17), 0x00000000);
        }

        const int grid_l = __vsub4(gl ^ signs0, signs0);
        const int grid_h = __vsub4(gh ^ signs1, signs1);

        int u0, u1;
        if (VAR & VAR_ATTIV) {
            const int b = sh.y_base + iqs/2;
            u0 = sh.y_qs[b*9 + l0 + 0];
            u1 = sh.y_qs[b*9 + l0 + 1];
        } else {
            u0 = get_int_b4(bq8_1[iqs/2].qs, l0 + 0);
            u1 = get_int_b4(bq8_1[iqs/2].qs, l0 + 1);
        }

        if (l0 < 4) {
            sumi0 = dp4a_(grid_l, u0, sumi0);
            sumi0 = dp4a_(grid_h, u1, sumi0);
        } else {
            sumi1 = dp4a_(grid_l, u0, sumi1);
            sumi1 = dp4a_(grid_h, u1, sumi1);
        }
    }
    const int sumi = (sumi0*ls0 + sumi1*ls1 + (sumi0 + sumi1)/2)/4;

    float dy;
    if (VAR & VAR_ATTIV) {
        dy = sh.y_d[sh.y_base + iqs/2];
    } else {
        dy = __low2float(bq8_1[iqs/2].ds);
    }
    const unsigned short dbits = ld_u16<VAR>((const unsigned short *) &bq2->d);
    __half dh;
    memcpy(&dh, &dbits, sizeof(dh));
    const float d = __half2float(dh) * dy;
    return d * sumi;
}

// kernel: copia fedele di mul_mat_vec_q<IQ2_S, 1, true, small_k=true> per la 3060.
// MINB = secondo argomento di __launch_bounds__ (blocchi minimi per SM):
// 1 = come l'originale (il compilatore usa 118 registri), >1 = tetto ai registri.
template <int VAR, int MINB>
__launch_bounds__(NWARPS*WSZ, MINB)
static __global__ void mmvq_iq2s(
        const void * __restrict__ vx, const void * __restrict__ vgate,
        const void * __restrict__ vy, const int32_t * __restrict__ ids,
        float * __restrict__ dst,
        const uint32_t ncols_x, const uint32_t stride_row_x,
        const uint32_t stride_channel_x, const uint32_t stride_channel_dst) {

    extern __shared__ char smem[];
    sh_t sh;
    sh.grid   = iq2s_grid;
    sh.g_lo   = nullptr;
    sh.g_hi   = nullptr;
    sh.y_qs   = nullptr;
    sh.y_d    = nullptr;
    sh.y_base = 0;

    const int tid  = WSZ*threadIdx.y + threadIdx.x;
    const int row0 = RPB*blockIdx.x;
    const int blocks_per_row_x = ncols_x / QK_K;
    constexpr int blocks_per_iter = VDR * NWARPS*WSZ / QI2S;   // 16

    const uint32_t channel_dst = blockIdx.y;
    const uint32_t channel_x   = ids[channel_dst];

    const block_q8_1 * y = (const block_q8_1 *) vy;            // nchannels_y = 1
    const int kbx_offset = channel_x*stride_channel_x + row0*stride_row_x;

    const int n_yblk = ncols_x / QK8_1;                        // 80
    if (VAR & VAR_GRIGLIA) {
        uint64_t * g = (uint64_t *) smem;
        for (int i = tid; i < 1024; i += NWARPS*WSZ) {
            g[i] = iq2s_grid[i];
        }
        sh.grid = g;
    }
    if (VAR & VAR_GRID32) {
        uint32_t * lo = (uint32_t *) smem;
        uint32_t * hi = lo + 1024;
        for (int i = tid; i < 1024; i += NWARPS*WSZ) {
            const uint64_t v = iq2s_grid[i];
            lo[i] = (uint32_t) v;
            hi[i] = (uint32_t) (v >> 32);
        }
        sh.g_lo = lo;
        sh.g_hi = hi;
    }
    if (VAR & VAR_ATTIV) {
        char * p = smem + (((VAR & VAR_GRIGLIA) || (VAR & VAR_GRID32)) ? 1024*8 : 0);
        int   * yq = (int *) p;
        float * yd = (float *) (p + n_yblk*9*4);
        for (int b = tid; b < n_yblk; b += NWARPS*WSZ) {
#pragma unroll
            for (int j = 0; j < 8; ++j) {
                yq[b*9 + j] = get_int_b4(y[b].qs, j);
            }
            yd[b] = __low2float(y[b].ds);
        }
        sh.y_qs = yq;
        sh.y_d  = yd;
    }
    if (VAR & (VAR_GRIGLIA | VAR_ATTIV | VAR_GRID32)) {
        __syncthreads();
    }

    float tmp[RPB]      = {0.0f};
    float tmp_gate[RPB] = {0.0f};

#define CORPO_RIGA \
        tmp[i]      += vec_dot_iq2_s<VAR>(vx,    &y[kby], kbx_offset + i*stride_row_x + kbx, kqs, sh); \
        tmp_gate[i] += vec_dot_iq2_s<VAR>(vgate, &y[kby], kbx_offset + i*stride_row_x + kbx, kqs, sh);

    for (int kbx = tid / (QI2S/VDR); kbx < blocks_per_row_x; kbx += blocks_per_iter) {
        const int kby = kbx * (QK_K/QK8_1);
        const int kqs = VDR * (tid % (QI2S/VDR));
        sh.y_base = kby;
        if (VAR & VAR_UNROLL1) {
#pragma unroll 1
            for (int i = 0; i < RPB; ++i) { CORPO_RIGA }
        } else if (VAR & VAR_UNROLL2) {
#pragma unroll 2
            for (int i = 0; i < RPB; ++i) { CORPO_RIGA }
        } else {
#pragma unroll
            for (int i = 0; i < RPB; ++i) { CORPO_RIGA }
        }
    }
#undef CORPO_RIGA

    __shared__ float tmp_shared     [NWARPS-1][1][RPB][WSZ];
    __shared__ float tmp_shared_gate[NWARPS-1][1][RPB][WSZ];

    if (threadIdx.y > 0) {
#pragma unroll
        for (int i = 0; i < RPB; ++i) {
            tmp_shared     [threadIdx.y-1][0][i][threadIdx.x] = tmp[i];
            tmp_shared_gate[threadIdx.y-1][0][i][threadIdx.x] = tmp_gate[i];
        }
    }
    __syncthreads();
    if (threadIdx.y > 0) {
        return;
    }

    dst += channel_dst*stride_channel_dst + row0;

#pragma unroll
    for (int i = 0; i < RPB; ++i) {
#pragma unroll
        for (int l = 0; l < NWARPS-1; ++l) {
            tmp[i]      += tmp_shared     [l][0][i][threadIdx.x];
            tmp_gate[i] += tmp_shared_gate[l][0][i][threadIdx.x];
        }
        tmp[i]      = warp_reduce_sum_<WSZ>(tmp[i]);
        tmp_gate[i] = warp_reduce_sum_<WSZ>(tmp_gate[i]);

        if (threadIdx.x == i && uint32_t(row0 + i) < stride_channel_dst) {
            float result     = tmp[i];
            float gate_value = tmp_gate[i];
            result *= silu_(gate_value);
            dst[i] = result;
        }
    }
}

// ------------------------------------------------------------------ host
struct esito_t { double us_min; double us_med; };

template <int VAR, int MINB>
static esito_t corri(const void * dx, const void * dg, const void * dy, const int32_t * dids,
                     float * ddst, int ripet, int round) {
    const uint32_t stride_row_x     = N_EMBD / QK_K;
    const uint32_t stride_channel_x = (uint32_t) N_FF_EXP * stride_row_x;
    const int n_yblk = N_EMBD / QK8_1;
    size_t smem = 0;
    if (VAR & VAR_GRIGLIA) smem += 1024*8;
    if (VAR & VAR_GRID32)  smem += 1024*8;
    if (VAR & VAR_ATTIV)   smem += (size_t) n_yblk*9*4 + (size_t) n_yblk*4;

    dim3 nb(N_FF_EXP/RPB, N_USED, 1);
    dim3 nt(WSZ, NWARPS, 1);

    for (int i = 0; i < 20; ++i) {
        mmvq_iq2s<VAR, MINB><<<nb, nt, smem>>>(dx, dg, dy, dids, ddst, N_EMBD, stride_row_x,
                                               stride_channel_x, (uint32_t) N_FF_EXP);
    }
    CHK(cudaDeviceSynchronize());
    CHK(cudaGetLastError());

    std::vector<double> t;
    cudaEvent_t e0, e1;
    CHK(cudaEventCreate(&e0)); CHK(cudaEventCreate(&e1));
    for (int r = 0; r < round; ++r) {
        CHK(cudaEventRecord(e0));
        for (int i = 0; i < ripet; ++i) {
            mmvq_iq2s<VAR, MINB><<<nb, nt, smem>>>(dx, dg, dy, dids, ddst, N_EMBD, stride_row_x,
                                                   stride_channel_x, (uint32_t) N_FF_EXP);
        }
        CHK(cudaEventRecord(e1));
        CHK(cudaEventSynchronize(e1));
        float ms = 0;
        CHK(cudaEventElapsedTime(&ms, e0, e1));
        t.push_back(ms*1000.0/ripet);
    }
    CHK(cudaEventDestroy(e0)); CHK(cudaEventDestroy(e1));
    std::sort(t.begin(), t.end());
    esito_t e; e.us_min = t.front(); e.us_med = t[t.size()/2];
    return e;
}

static std::vector<uint8_t> leggi(const char * path, size_t atteso) {
    FILE * f = fopen(path, "rb");
    if (!f) { printf("ERRORE: non apro %s\n", path); exit(1); }
    std::vector<uint8_t> v(atteso);
    size_t n = fread(v.data(), 1, atteso, f);
    fclose(f);
    if (n != atteso) { printf("ERRORE: %s letto %zu invece di %zu\n", path, n, atteso); exit(1); }
    return v;
}

struct riga_t { const char * nome; esito_t e; int uguali; int reg; };

int main(int argc, char ** argv) {
    const char * p_gate = argc > 1 ? argv[1] : "D:\\ds4_work\\p8_work\\prove\\p10c3_iq2s_gate.bin";
    const char * p_up   = argc > 2 ? argv[2] : "D:\\ds4_work\\p8_work\\prove\\p10c3_iq2s_up.bin";
    const int ripet = argc > 3 ? atoi(argv[3]) : 100;
    const int round = argc > 4 ? atoi(argv[4]) : 9;
    const int solo  = argc > 5 ? atoi(argv[5]) : -1;   // per il profilatore: una sola variante

    const size_t byte_esperto = (size_t) N_EMBD * N_FF_EXP / QK_K * sizeof(block_iq2_s);
    const size_t byte_tot     = byte_esperto * N_POOL;

    std::vector<uint8_t> hx = leggi(p_gate, byte_tot);
    std::vector<uint8_t> hg = leggi(p_up,   byte_tot);

    const int n_yblk = N_EMBD / QK8_1;
    std::vector<block_q8_1> hy(n_yblk);
    {
        std::vector<float> x(N_EMBD);
        uint32_t s = 1234567u;
        for (int i = 0; i < N_EMBD; ++i) {
            s = s*1664525u + 1013904223u;
            x[i] = ((float) (s >> 8) / 8388608.0f - 1.0f) * 1.7f;
        }
        for (int b = 0; b < n_yblk; ++b) {
            float amax = 0, sum = 0;
            for (int j = 0; j < QK8_1; ++j) amax = fmaxf(amax, fabsf(x[b*QK8_1 + j]));
            const float d  = amax / 127.0f;
            const float id = d ? 1.0f/d : 0.0f;
            for (int j = 0; j < QK8_1; ++j) {
                const int q = (int) roundf(x[b*QK8_1 + j]*id);
                hy[b].qs[j] = (int8_t) std::max(-127, std::min(127, q));
                sum += (float) hy[b].qs[j];
            }
            const __half2 ds = __floats2half2_rn(d, sum*d);
            memcpy(&hy[b].ds, &ds, sizeof(ds));
        }
    }

    std::vector<int32_t> hids(N_USED);
    for (int i = 0; i < N_USED; ++i) hids[i] = (i*7 + 3) % N_POOL;

    void * dx = nullptr; void * dg = nullptr; void * dy = nullptr;
    int32_t * dids = nullptr; float * ddst = nullptr;
    CHK(cudaMalloc(&dx, byte_tot));
    CHK(cudaMalloc(&dg, byte_tot));
    CHK(cudaMalloc(&dy, hy.size()*sizeof(block_q8_1)));
    CHK(cudaMalloc(&dids, hids.size()*sizeof(int32_t)));
    CHK(cudaMalloc(&ddst,  (size_t) N_FF_EXP*N_USED*sizeof(float)));
    CHK(cudaMemcpy(dx, hx.data(), byte_tot, cudaMemcpyHostToDevice));
    CHK(cudaMemcpy(dg, hg.data(), byte_tot, cudaMemcpyHostToDevice));
    CHK(cudaMemcpy(dy, hy.data(), hy.size()*sizeof(block_q8_1), cudaMemcpyHostToDevice));
    CHK(cudaMemcpy(dids, hids.data(), hids.size()*sizeof(int32_t), cudaMemcpyHostToDevice));

    const double mib = (double) N_USED * N_FF_EXP * (N_EMBD/QK_K) * sizeof(block_iq2_s) * 2 / (1024.0*1024.0);
    printf("# microbanco iq2_s - un lancio reale: %.3f MiB, griglia %dx%d, blocco %dx%d, small_k=1 rpb=%d\n",
           mib, N_FF_EXP/RPB, N_USED, WSZ, NWARPS, RPB);
    printf("# ripetizioni %d, round %d\n\n", ripet, round);

    std::vector<float> h0((size_t) N_FF_EXP*N_USED), h1((size_t) N_FF_EXP*N_USED);
    std::vector<riga_t> righe;
    int caso = 0;

#define RIF(V, M, NOME, REG) \
    if (solo < 0 || solo == caso) { \
        esito_t e = corri<V, M>(dx, dg, dy, dids, ddst, ripet, round); \
        CHK(cudaMemcpy(h0.data(), ddst, h0.size()*sizeof(float), cudaMemcpyDeviceToHost)); \
        righe.push_back({NOME, e, 1, REG}); \
    } ++caso;
#define PROVA(V, M, NOME, REG) \
    if (solo < 0 || solo == caso) { \
        esito_t e = corri<V, M>(dx, dg, dy, dids, ddst, ripet, round); \
        CHK(cudaMemcpy(h1.data(), ddst, h1.size()*sizeof(float), cudaMemcpyDeviceToHost)); \
        int ug = (solo < 0) ? (memcmp(h0.data(), h1.data(), h1.size()*sizeof(float)) == 0) : -1; \
        righe.push_back({NOME, e, ug, REG}); \
    } ++caso;
#define ABLA(V, M, NOME, REG) \
    if (solo < 0 || solo == caso) { \
        esito_t e = corri<V, M>(dx, dg, dy, dids, ddst, ripet, round); \
        righe.push_back({NOME, e, -1, REG}); \
    } ++caso;

    RIF  (VAR_BASE, 1, "V0  originale (launch_bounds 128,1)", 0)
    // --- candidate lossless: solo il tetto ai registri
    PROVA(VAR_BASE, 2, "R2  originale + launch_bounds(128,2)", 0)
    PROVA(VAR_BASE, 3, "R3  originale + launch_bounds(128,3)", 0)
    PROVA(VAR_BASE, 4, "R4  originale + launch_bounds(128,4)", 0)
    PROVA(VAR_BASE, 5, "R5  originale + launch_bounds(128,5)", 0)
    PROVA(VAR_BASE, 6, "R6  originale + launch_bounds(128,6)", 0)
    PROVA(VAR_BASE, 8, "R8  originale + launch_bounds(128,8)", 0)
    // --- candidate lossless: memoria condivisa (con e senza tetto ai registri)
    PROVA(VAR_GRIGLIA,           1, "S1  griglia in shared", 0)
    PROVA(VAR_ATTIV,             1, "S2  attivazioni in shared", 0)
    PROVA(VAR_GRIGLIA|VAR_ATTIV, 1, "S3  griglia + attivazioni in shared", 0)
    PROVA(VAR_ATTIV,             6, "S2+R6 attivazioni in shared + lb(128,6)", 0)
    PROVA(VAR_GRID32,            1, "S4  griglia in shared come lo/hi a 32 bit", 0)
    PROVA(VAR_GRID32,            8, "S4+R8 griglia lo/hi a 32 bit + lb(128,8)", 0)
    PROVA(VAR_GRIGLIA,           8, "S1+R8 griglia in shared + lb(128,8)", 0)
    // --- candidate lossless: tetto piu' alto e srotolamento del ciclo sulle righe
    PROVA(VAR_BASE,             10, "R10 originale + launch_bounds(128,10)", 0)
    PROVA(VAR_BASE,             12, "R12 originale + launch_bounds(128,12)", 0)
    PROVA(VAR_UNROLL1,           1, "U1  ciclo righe non srotolato", 0)
    PROVA(VAR_UNROLL2,           1, "U2  ciclo righe srotolato per due", 0)
    PROVA(VAR_UNROLL2,           8, "U2+R8 srotolato per due + lb(128,8)", 0)
    PROVA(VAR_UNROLL1,           8, "U1+R8 non srotolato + lb(128,8)", 0)
    // --- candidate lossless: politica di cache sui pesi (nessun riuso)
    PROVA(VAR_LDCS,              1, "C1  pesi con .cs", 0)
    PROVA(VAR_LDCG,              1, "C2  pesi con .cg (fuori L1)", 0)
    PROVA(VAR_LDCS,              8, "C1+R8 pesi .cs + lb(128,8)", 0)
    PROVA(VAR_LDCG,              8, "C2+R8 pesi .cg + lb(128,8)", 0)
    PROVA(VAR_LDCG|VAR_GRID32,   8, "C2+S4+R8 .cg + griglia lo/hi in shared + lb(128,8)", 0)
    PROVA(VAR_LDCS|VAR_GRID32,   8, "C1+S4+R8 .cs + griglia lo/hi in shared + lb(128,8)", 0)
    PROVA(VAR_LDCG,              6, "C2+R6 pesi .cg + lb(128,6)", 0)
    PROVA(VAR_LDCG,             10, "C2+R10 pesi .cg + lb(128,10)", 0)
    // --- ABLAZIONI (risultato diverso per costruzione: solo diagnosi)
    ABLA(ABL_NOGRID,             1, "A1  ablazione: nessuna ricerca in tabella", 0)
    ABLA(ABL_NOSEGNI,            1, "A2  ablazione: nessuna aritmetica dei segni", 0)
    ABLA(ABL_NOGRID|ABL_NOSEGNI, 1, "A3  ablazione: ne' tabella ne' segni", 0)
    ABLA(ABL_NOGRID|ABL_NOSEGNI, 6, "A4  ablazione: ne' tabella ne' segni + lb(128,6)", 0)
#undef RIF
#undef PROVA
#undef ABLA

    printf("%-46s %9s %9s %9s %8s\n", "variante", "us(min)", "us(med)", "GB/s", "bit=V0");
    for (const auto & r : righe) {
        const double gbs = mib/1024.0*1.073741824e9 / (r.e.us_min*1e-6) / 1e9;
        printf("%-46s %9.2f %9.2f %9.1f %8s\n", r.nome, r.e.us_min, r.e.us_med, gbs,
               r.uguali < 0 ? "-" : (r.uguali ? "SI" : "NO"));
    }

    size_t libera = 0, tot = 0;
    CHK(cudaMemGetInfo(&libera, &tot));
    printf("\n# VRAM libera %.0f MiB su %.0f MiB\n", libera/1048576.0, tot/1048576.0);
    CHK(cudaFree(dx)); CHK(cudaFree(dg)); CHK(cudaFree(dy));
    CHK(cudaFree(dids)); CHK(cudaFree(ddst));
    return 0;
}
