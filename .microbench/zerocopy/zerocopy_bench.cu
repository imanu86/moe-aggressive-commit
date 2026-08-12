// zerocopy_bench.cu
// Microbench: three ways of serving MoE expert weights (7,077,888 B each) to a
// GEMV-realistic kernel on an RTX 3060 (Windows 11 / WDDM).
//
//   S1  VRAM resident                       (baseline, no PCIe traffic)
//   S2a zero-copy, kernels serialized       (kernel reads mapped host RAM over PCIe)
//   S2b zero-copy, one kernel per stream    (6-way concurrency)
//   S3a memcpyAsync + kernel, per-expert    (current runtime pattern, serialized)
//   S3b 6x memcpyAsync then 6x kernel       (batched copies)
//   S3c memcpy/kernel pipelined, 3 streams  (EXTRA: overlapped double/triple buffer)
//   S4  cudaMemcpy H2D of 512 MB pinned     (real PCIe peak reference)
//
// Anti-dead-code: every scenario writes y[] to global memory and the host sums
// it back into a checksum that is printed. All memory forms hold *identical*
// bytes, so the checksums must match across scenarios -- if a scenario did not
// really read the weights, its checksum would differ.

#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <algorithm>
#include <chrono>
#include <cuda_runtime.h>

#define CHK(call)                                                                     \
    do {                                                                              \
        cudaError_t _e = (call);                                                      \
        if (_e != cudaSuccess) {                                                      \
            std::fprintf(stderr, "CUDA ERROR %s:%d: %s -> %s\n", __FILE__, __LINE__,  \
                         #call, cudaGetErrorString(_e));                              \
            std::fflush(stderr);                                                      \
            std::exit(1);                                                             \
        }                                                                             \
    } while (0)

static const int    ROWS              = 1728;
static const int    COLS              = 4096;                       // int8 per row
static const size_t EXPERT_BYTES      = (size_t)ROWS * (size_t)COLS; // 7,077,888
static const int    NEXPERTS          = 64;                          // pool size
static const int    GROUP             = 6;                           // experts per measured group
static const int    WARMUP            = 3;
static const int    ITERS             = 20;
static const double EXPERTS_PER_TOKEN = 188.5;
static const size_t S4_BYTES          = (size_t)512 << 20;           // 512 MiB
static const int    THREADS           = 256;                         // 256 thr * int4(16B) = 4096 B = 1 row
static const int    NPIPE             = 3;                           // streams/slots for S3c

// ---------------------------------------------------------------------------
// GEMV-like kernel: W is int8 [ROWS x COLS] row-major, x is fp32[COLS] in VRAM.
// y[i] = sum_j W[i][j] * x[j], fp32 accumulate.
// One block per row; the 256 threads of a block read the row with 256 fully
// coalesced 16-byte loads (512 B per warp instruction) -- the access pattern a
// real int8 matmul would issue. Identical kernel for VRAM and zero-copy; only
// the base pointer changes.
// ---------------------------------------------------------------------------
__global__ __launch_bounds__(THREADS) void gemv_i8(const int4* __restrict__ W,
                                                   const float* __restrict__ x,
                                                   float* __restrict__ y)
{
    const int row = blockIdx.x;
    const int t   = threadIdx.x;                       // 0..255

    const int4 v = W[(size_t)row * (COLS / 16) + t];   // 16 bytes, coalesced across warp
    const signed char* b = reinterpret_cast<const signed char*>(&v);
    const float* xp = x + (t << 4);

    float acc = 0.0f;
#pragma unroll
    for (int k = 0; k < 16; ++k) acc += (float)b[k] * xp[k];

    // warp reduction
#pragma unroll
    for (int off = 16; off > 0; off >>= 1) acc += __shfl_down_sync(0xffffffffu, acc, off);

    __shared__ float s[THREADS / 32];
    if ((t & 31) == 0) s[t >> 5] = acc;
    __syncthreads();

    if (t < (THREADS / 32)) {
        float w = s[t];
#pragma unroll
        for (int off = (THREADS / 64); off > 0; off >>= 1)
            w += __shfl_down_sync((1u << (THREADS / 32)) - 1u, w, off);
        if (t == 0) y[row] = w;
    }
}

// ---------------------------------------------------------------------------
static inline uint32_t lcg(uint32_t& s) { s = s * 1664525u + 1013904223u; return s; }

static double median(std::vector<double> v)
{
    std::sort(v.begin(), v.end());
    size_t n = v.size();
    return (n & 1) ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

struct Result {
    const char* name;
    const char* note;
    double ms_med;      // median ms per group of GROUP experts (cudaEvent)
    double ms_min;
    double ms_wall;     // median wall-clock ms per group (includes launch overhead)
    double gbs;         // effective GB/s of expert bytes served
    double ms_token;    // extrapolation to EXPERTS_PER_TOKEN experts
    double checksum;
};

static std::vector<Result> g_results;

static void report(const char* name, const char* note, std::vector<double>& ev,
                   std::vector<double>& wall, size_t bytes_per_group, double checksum)
{
    Result r;
    r.name     = name;
    r.note     = note;
    r.ms_med   = median(ev);
    r.ms_min   = *std::min_element(ev.begin(), ev.end());
    r.ms_wall  = median(wall);
    r.gbs      = (double)bytes_per_group / (r.ms_med * 1e-3) / 1e9;
    r.ms_token = r.ms_med * (EXPERTS_PER_TOKEN / (double)GROUP);
    r.checksum = checksum;
    g_results.push_back(r);

    std::printf("  %-46s ev_med %8.3f ms | min %8.3f | wall %8.3f ms | %7.2f GB/s | "
                "%7.3f ms/expert | -> %8.1f ms/token | chk %.0f\n",
                name, r.ms_med, r.ms_min, r.ms_wall, r.gbs,
                r.ms_med / (double)GROUP, r.ms_token, checksum);
    std::fflush(stdout);
}

// ---------------------------------------------------------------------------
int main()
{
    CHK(cudaSetDevice(0));
    CHK(cudaSetDeviceFlags(cudaDeviceMapHost));

    cudaDeviceProp p;
    CHK(cudaGetDeviceProperties(&p, 0));

    std::printf("=====================================================================\n");
    std::printf(" ZERO-COPY MICROBENCH -- MoE expert weight delivery (RTX 3060 / WDDM)\n");
    std::printf("=====================================================================\n");
    std::printf("device                : %s (sm_%d%d, %d SMs)\n", p.name, p.major, p.minor,
                p.multiProcessorCount);
    std::printf("L2 cache              : %.2f MB\n", p.l2CacheSize / 1048576.0);
    std::printf("VRAM theoretical BW   : %.1f GB/s (%d-bit @ %.0f MHz)\n",
                2.0 * p.memoryClockRate * 1e3 * (p.memoryBusWidth / 8.0) / 1e9,
                p.memoryBusWidth, p.memoryClockRate / 1e3);
    std::printf("canMapHostMemory      : %d   unifiedAddressing: %d   asyncEngines: %d   integrated: %d\n",
                p.canMapHostMemory, p.unifiedAddressing, p.asyncEngineCount, p.integrated);
    std::printf("expert size           : %zu B (int8 [%d x %d])\n", EXPERT_BYTES, ROWS, COLS);
    std::printf("group                 : %d experts = %.2f MB;  pool = %d experts = %.1f MB per form\n",
                GROUP, GROUP * EXPERT_BYTES / 1048576.0, NEXPERTS,
                NEXPERTS * EXPERT_BYTES / 1048576.0);
    std::printf("timing                : %d warmup + %d measured, median, cudaEvent (wall as cross-check)\n",
                WARMUP, ITERS);
    std::printf("cache guard           : group working set %.1f MB >> L2 %.2f MB, and the expert group\n"
                "                        rotates through the %d-expert pool every iteration.\n",
                GROUP * EXPERT_BYTES / 1048576.0, p.l2CacheSize / 1048576.0, NEXPERTS);
    std::printf("---------------------------------------------------------------------\n");
    std::fflush(stdout);

    // ---------------- allocations ----------------
    const size_t pool_bytes = (size_t)NEXPERTS * EXPERT_BYTES;

    std::printf("[alloc] pinned source pool  %.1f MB ...\n", pool_bytes / 1048576.0);
    std::fflush(stdout);
    signed char* h_pinned = nullptr;                       // classic pinned (source for copy mode)
    CHK(cudaHostAlloc((void**)&h_pinned, pool_bytes, cudaHostAllocDefault));

    std::printf("[alloc] mapped  zero-copy pool %.1f MB ...\n", pool_bytes / 1048576.0);
    std::fflush(stdout);
    signed char* h_mapped = nullptr;                       // cudaHostAllocMapped
    CHK(cudaHostAlloc((void**)&h_mapped, pool_bytes, cudaHostAllocMapped | cudaHostAllocPortable));
    signed char* d_mapped = nullptr;                       // device-side alias of h_mapped
    CHK(cudaHostGetDevicePointer((void**)&d_mapped, h_mapped, 0));

    std::printf("[alloc] VRAM resident pool  %.1f MB ...\n", pool_bytes / 1048576.0);
    std::fflush(stdout);
    signed char* d_vram = nullptr;
    CHK(cudaMalloc((void**)&d_vram, pool_bytes));

    signed char* d_slot[GROUP];                            // H2D destinations for copy modes
    for (int i = 0; i < GROUP; ++i) CHK(cudaMalloc((void**)&d_slot[i], EXPERT_BYTES));

    float* d_x = nullptr;
    CHK(cudaMalloc((void**)&d_x, COLS * sizeof(float)));
    float* d_y = nullptr;
    CHK(cudaMalloc((void**)&d_y, (size_t)GROUP * ROWS * sizeof(float)));
    std::vector<float> h_y((size_t)GROUP * ROWS);

    // ---------------- data ----------------
    std::printf("[init]  filling pool with pseudorandom int8 in [-8,7] ...\n");
    std::fflush(stdout);
    {
        uint32_t seed = 0x1234567u;
        uint32_t* w32 = reinterpret_cast<uint32_t*>(h_pinned);
        const size_t nw = pool_bytes / 4;
        for (size_t i = 0; i < nw; ++i) {
            uint32_t r = lcg(seed);
            uint32_t o = ((r & 15u) - 8u) & 0xFFu;
            o |= ((((r >> 8) & 15u) - 8u) & 0xFFu) << 8;
            o |= ((((r >> 16) & 15u) - 8u) & 0xFFu) << 16;
            o |= ((((r >> 24) & 15u) - 8u) & 0xFFu) << 24;
            w32[i] = o;
        }
    }
    std::memcpy(h_mapped, h_pinned, pool_bytes);                     // identical bytes
    CHK(cudaMemcpy(d_vram, h_pinned, pool_bytes, cudaMemcpyHostToDevice));

    {
        std::vector<float> hx(COLS);
        for (int j = 0; j < COLS; ++j) hx[j] = (float)((j % 7) - 3); // small ints -> y exact in fp32
        CHK(cudaMemcpy(d_x, hx.data(), COLS * sizeof(float), cudaMemcpyHostToDevice));
    }
    CHK(cudaDeviceSynchronize());
    std::printf("[init]  done. all three memory forms hold identical bytes.\n");
    std::printf("---------------------------------------------------------------------\n");
    std::fflush(stdout);

    // ---------------- streams / events ----------------
    cudaStream_t s0;
    CHK(cudaStreamCreate(&s0));
    cudaStream_t sg[GROUP];
    for (int i = 0; i < GROUP; ++i) CHK(cudaStreamCreate(&sg[i]));
    cudaStream_t sp[NPIPE];
    for (int i = 0; i < NPIPE; ++i) CHK(cudaStreamCreate(&sp[i]));

    cudaEvent_t evA, evB;
    CHK(cudaEventCreate(&evA));
    CHK(cudaEventCreate(&evB));
    cudaEvent_t evJoin[GROUP];
    for (int i = 0; i < GROUP; ++i) CHK(cudaEventCreate(&evJoin[i]));

    const size_t GROUP_BYTES = (size_t)GROUP * EXPERT_BYTES;

    // expert index for iteration `it`, slot `g` -- rotates so nothing is reused warm
    auto eidx = [](int it, int g) { return ((it * GROUP) + g) % NEXPERTS; };

    auto sum_y = [&](void) -> double {
        CHK(cudaMemcpy(h_y.data(), d_y, h_y.size() * sizeof(float), cudaMemcpyDeviceToHost));
        double s = 0.0;
        for (size_t i = 0; i < h_y.size(); ++i) s += (double)h_y[i];
        return s;
    };

    std::vector<double> ev(ITERS), wall(ITERS);

    // ================= S1 : VRAM resident =================
    {
        double chk = 0.0;
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            for (int g = 0; g < GROUP; ++g) {
                const int4* W = (const int4*)(d_vram + (size_t)eidx(it < 0 ? 0 : it, g) * EXPERT_BYTES);
                gemv_i8<<<ROWS, THREADS, 0, s0>>>(W, d_x, d_y + (size_t)g * ROWS);
            }
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            CHK(cudaGetLastError());
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                ev[it]   = ms;
                wall[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
                chk += sum_y();
            }
        }
        std::printf("S1  VRAM resident (baseline, no PCIe)\n");
        report("S1  vram, 6 kernels serial", "", ev, wall, GROUP_BYTES, chk);
    }

    // ================= S2a : zero-copy serial =================
    {
        double chk = 0.0;
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            for (int g = 0; g < GROUP; ++g) {
                const int4* W = (const int4*)(d_mapped + (size_t)eidx(it < 0 ? 0 : it, g) * EXPERT_BYTES);
                gemv_i8<<<ROWS, THREADS, 0, s0>>>(W, d_x, d_y + (size_t)g * ROWS);
            }
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            CHK(cudaGetLastError());
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                ev[it]   = ms;
                wall[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
                chk += sum_y();
            }
        }
        std::printf("S2  ZERO-COPY (kernel reads mapped host RAM directly over PCIe)\n");
        report("S2a zero-copy, 6 kernels serial", "", ev, wall, GROUP_BYTES, chk);
    }

    // ================= S2b : zero-copy, one kernel per stream =================
    {
        double chk = 0.0;
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            for (int g = 0; g < GROUP; ++g) CHK(cudaStreamWaitEvent(sg[g], evA, 0));
            for (int g = 0; g < GROUP; ++g) {
                const int4* W = (const int4*)(d_mapped + (size_t)eidx(it < 0 ? 0 : it, g) * EXPERT_BYTES);
                gemv_i8<<<ROWS, THREADS, 0, sg[g]>>>(W, d_x, d_y + (size_t)g * ROWS);
                CHK(cudaEventRecord(evJoin[g], sg[g]));
            }
            for (int g = 0; g < GROUP; ++g) CHK(cudaStreamWaitEvent(s0, evJoin[g], 0));
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            CHK(cudaGetLastError());
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                ev[it]   = ms;
                wall[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
                chk += sum_y();
            }
        }
        report("S2b zero-copy, 6 kernels / 6 streams", "", ev, wall, GROUP_BYTES, chk);
    }

    // ================= S3a : copy+kernel serialized per expert =================
    {
        double chk = 0.0;
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            for (int g = 0; g < GROUP; ++g) {
                const signed char* src = h_pinned + (size_t)eidx(it < 0 ? 0 : it, g) * EXPERT_BYTES;
                CHK(cudaMemcpyAsync(d_slot[g], src, EXPERT_BYTES, cudaMemcpyHostToDevice, s0));
                gemv_i8<<<ROWS, THREADS, 0, s0>>>((const int4*)d_slot[g], d_x, d_y + (size_t)g * ROWS);
            }
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            CHK(cudaGetLastError());
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                ev[it]   = ms;
                wall[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
                chk += sum_y();
            }
        }
        std::printf("S3  COPY pinned->VRAM then compute\n");
        report("S3a copy+kernel serialized per-expert", "", ev, wall, GROUP_BYTES, chk);
    }

    // ================= S3b : batched copies then batched kernels =================
    {
        double chk = 0.0;
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            for (int g = 0; g < GROUP; ++g) {
                const signed char* src = h_pinned + (size_t)eidx(it < 0 ? 0 : it, g) * EXPERT_BYTES;
                CHK(cudaMemcpyAsync(d_slot[g], src, EXPERT_BYTES, cudaMemcpyHostToDevice, s0));
            }
            for (int g = 0; g < GROUP; ++g)
                gemv_i8<<<ROWS, THREADS, 0, s0>>>((const int4*)d_slot[g], d_x, d_y + (size_t)g * ROWS);
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            CHK(cudaGetLastError());
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                ev[it]   = ms;
                wall[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
                chk += sum_y();
            }
        }
        report("S3b 6 copies batched, then 6 kernels", "", ev, wall, GROUP_BYTES, chk);
    }

    // ================= S3c (extra) : pipelined copy/compute, NPIPE streams =================
    {
        double chk = 0.0;
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            for (int i = 0; i < NPIPE; ++i) CHK(cudaStreamWaitEvent(sp[i], evA, 0));
            for (int g = 0; g < GROUP; ++g) {
                cudaStream_t st = sp[g % NPIPE];
                const signed char* src = h_pinned + (size_t)eidx(it < 0 ? 0 : it, g) * EXPERT_BYTES;
                CHK(cudaMemcpyAsync(d_slot[g], src, EXPERT_BYTES, cudaMemcpyHostToDevice, st));
                gemv_i8<<<ROWS, THREADS, 0, st>>>((const int4*)d_slot[g], d_x, d_y + (size_t)g * ROWS);
            }
            for (int i = 0; i < NPIPE; ++i) {
                CHK(cudaEventRecord(evJoin[i], sp[i]));
                CHK(cudaStreamWaitEvent(s0, evJoin[i], 0));
            }
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            CHK(cudaGetLastError());
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                ev[it]   = ms;
                wall[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
                chk += sum_y();
            }
        }
        report("S3c copy/kernel pipelined, 3 streams [EXTRA]", "", ev, wall, GROUP_BYTES, chk);
    }

    // ================= S4 : raw PCIe H2D reference =================
    {
        std::printf("S4  RAW PCIe reference\n");
        signed char* h_big = nullptr;
        signed char* d_big = nullptr;
        CHK(cudaHostAlloc((void**)&h_big, S4_BYTES, cudaHostAllocDefault));
        CHK(cudaMalloc((void**)&d_big, S4_BYTES));
        std::memset(h_big, 0x5A, S4_BYTES);

        std::vector<double> e4(ITERS), w4(ITERS);
        for (int it = -WARMUP; it < ITERS; ++it) {
            auto t0 = std::chrono::high_resolution_clock::now();
            CHK(cudaEventRecord(evA, s0));
            CHK(cudaMemcpyAsync(d_big, h_big, S4_BYTES, cudaMemcpyHostToDevice, s0));
            CHK(cudaEventRecord(evB, s0));
            CHK(cudaEventSynchronize(evB));
            auto t1 = std::chrono::high_resolution_clock::now();
            if (it >= 0) {
                float ms; CHK(cudaEventElapsedTime(&ms, evA, evB));
                e4[it] = ms;
                w4[it] = std::chrono::duration<double, std::milli>(t1 - t0).count();
            }
        }
        double med = median(e4);
        double gbs = (double)S4_BYTES / (med * 1e-3) / 1e9;
        std::printf("  %-46s ev_med %8.3f ms | min %8.3f | wall %8.3f ms | %7.2f GB/s "
                    "(512 MiB pinned H2D)\n",
                    "S4  cudaMemcpy H2D 512MB pinned", med, *std::min_element(e4.begin(), e4.end()),
                    median(w4), gbs);
        std::fflush(stdout);

        Result r{};
        r.name     = "S4  cudaMemcpy H2D 512MB pinned";
        r.ms_med   = med;
        r.ms_min   = *std::min_element(e4.begin(), e4.end());
        r.ms_wall  = median(w4);
        r.gbs      = gbs;
        r.ms_token = EXPERTS_PER_TOKEN * (double)EXPERT_BYTES / (gbs * 1e9) * 1e3;
        r.checksum = 0.0;
        g_results.push_back(r);

        CHK(cudaFreeHost(h_big));
        CHK(cudaFree(d_big));
    }

    // ---------------- summary ----------------
    const double tok_bytes = EXPERTS_PER_TOKEN * (double)EXPERT_BYTES;
    std::printf("---------------------------------------------------------------------\n");
    std::printf("SUMMARY  (extrapolation: %.1f experts/token = %.3f GB/token)\n",
                EXPERTS_PER_TOKEN, tok_bytes / 1e9);
    std::printf("---------------------------------------------------------------------\n");
    std::printf("%-46s %10s %10s %12s %12s\n", "scenario", "ms/6exp", "GB/s", "ms/expert", "ms/token");
    for (size_t i = 0; i < g_results.size(); ++i) {
        const Result& r = g_results[i];
        if (std::strncmp(r.name, "S4", 2) == 0) {
            std::printf("%-46s %10.3f %10.2f %12s %12.1f  (pure wire time at this BW)\n",
                        r.name, r.ms_med, r.gbs, "-", r.ms_token);
        } else {
            std::printf("%-46s %10.3f %10.2f %12.3f %12.1f\n",
                        r.name, r.ms_med, r.gbs, r.ms_med / GROUP, r.ms_token);
        }
    }
    std::printf("---------------------------------------------------------------------\n");
    std::printf("reference points: runtime today ~288 ms/token (copy+orchestration);\n");
    std::printf("                  wire time at 12 GB/s = %.1f ms/token.\n", tok_bytes / 12e9 * 1e3);

    // checksum sanity
    bool all_same = true;
    double ref = -1.0;
    for (size_t i = 0; i < g_results.size(); ++i) {
        if (std::strncmp(g_results[i].name, "S4", 2) == 0) continue;
        if (ref < 0) ref = g_results[i].checksum;
        else if (g_results[i].checksum != ref) all_same = false;
    }
    std::printf("checksum cross-check: %s (all compute scenarios produced %s results;\n"
                "                      y[] is stored to global memory, so the loads cannot be elided)\n",
                all_same ? "PASS" : "FAIL", all_same ? "identical" : "DIFFERENT");
    std::printf("=====================================================================\n");

    CHK(cudaFreeHost(h_pinned));
    CHK(cudaFreeHost(h_mapped));
    CHK(cudaFree(d_vram));
    for (int i = 0; i < GROUP; ++i) CHK(cudaFree(d_slot[i]));
    CHK(cudaFree(d_x));
    CHK(cudaFree(d_y));
    return 0;
}
