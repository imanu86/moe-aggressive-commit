// Appended to source-extracted MMVQ helpers/kernel by make_occ12_unit.py.
#include <cmath>
#include <cstring>
#include <random>
#include <stdexcept>

static void check_cuda(cudaError_t status) {
    if (status != cudaSuccess) {
        throw std::runtime_error(cudaGetErrorString(status));
    }
}

template<int min_blocks>
static void launch_unit(const block_q4_K * up, const block_q4_K * gate,
                        const block_q8_1 * y, float * dst, int k, int rows) {
    ggml_cuda_mm_fusion_args_device fusion{};
    fusion.gate = gate;
    fusion.glu_op = GGML_GLU_OP_SWIGLU;
    mul_mat_vec_q<GGML_TYPE_Q4_K, 1, true, false, false, false, min_blocks>
        <<<dim3(rows, 1, 1), dim3(32, 4, 1)>>>(
            up, y, nullptr, fusion, dst, k, make_uint3(0, 0, 0),
            k / QK_K, k / QK8_1, rows, init_fastdiv_values(1),
            rows * (k / QK_K), k / QK8_1, rows, init_fastdiv_values(1),
            rows * (k / QK_K), k / QK8_1, rows, 0);
    check_cuda(cudaGetLastError());
}

template<int min_blocks>
static float time_unit(const block_q4_K * up, const block_q4_K * gate,
                       const block_q8_1 * y, float * dst, int k, int rows) {
    cudaEvent_t start, stop;
    check_cuda(cudaEventCreate(&start));
    check_cuda(cudaEventCreate(&stop));
    check_cuda(cudaEventRecord(start));
    for (int i = 0; i < 32; ++i) { launch_unit<min_blocks>(up, gate, y, dst, k, rows); }
    check_cuda(cudaEventRecord(stop));
    check_cuda(cudaEventSynchronize(stop));
    float elapsed;
    check_cuda(cudaEventElapsedTime(&elapsed, start, stop));
    check_cuda(cudaEventDestroy(start));
    check_cuda(cudaEventDestroy(stop));
    return elapsed * 1000.0f / 32;
}

static void run_case(unsigned seed, int pattern) {
    constexpr int k = 2560;
    constexpr int rows = 9216;
    constexpr float canary = 123456.0f;
    std::mt19937 random(seed);
    std::vector<block_q4_K> up(rows * k / QK_K), gate(up.size());
    for (auto * weights : {&up, &gate}) {
        for (auto & block : *weights) {
            block.data.d = __float2half(pattern == 1 ? 0.0f : (pattern == 2 ? 0.00001f : 0.001f));
            block.data.dmin = __float2half(pattern == 1 ? 0.0f : 0.003f);
            for (auto & v : block.scales) { v = static_cast<uint8_t>(random()); }
            for (auto & v : block.qs) { v = static_cast<uint8_t>(random()); }
        }
    }
    std::vector<block_q8_1> y(k / QK8_1);
    for (auto & block : y) {
        const float scale = pattern == 3 ? 0.01f : 0.001f;
        block.data.d = __float2half(scale);
        int sum = 0;
        for (auto & v : block.qs) {
            v = static_cast<int8_t>(static_cast<int>(random() % 255) - 127);
            sum += v;
        }
        block.data.s = __float2half(__half2float(block.data.d) * sum);
    }
    block_q4_K * du = nullptr, * dg = nullptr;
    block_q8_1 * dy = nullptr;
    float * da = nullptr, * db = nullptr;
    const size_t weight_bytes = up.size() * sizeof(block_q4_K);
    const size_t result_bytes = (rows + 2) * sizeof(float);
    check_cuda(cudaMalloc(&du, weight_bytes));
    check_cuda(cudaMalloc(&dg, weight_bytes));
    check_cuda(cudaMalloc(&dy, y.size() * sizeof(block_q8_1)));
    check_cuda(cudaMalloc(&da, result_bytes));
    check_cuda(cudaMalloc(&db, result_bytes));
    check_cuda(cudaMemcpy(du, up.data(), weight_bytes, cudaMemcpyHostToDevice));
    check_cuda(cudaMemcpy(dg, gate.data(), weight_bytes, cudaMemcpyHostToDevice));
    check_cuda(cudaMemcpy(dy, y.data(), y.size() * sizeof(block_q8_1), cudaMemcpyHostToDevice));
    std::vector<float> a(rows + 2, canary), b(a);
    check_cuda(cudaMemcpy(da, a.data(), result_bytes, cudaMemcpyHostToDevice));
    check_cuda(cudaMemcpy(db, b.data(), result_bytes, cudaMemcpyHostToDevice));
    launch_unit<1>(du, dg, dy, da + 1, k, rows);
    launch_unit<12>(du, dg, dy, db + 1, k, rows);
    check_cuda(cudaDeviceSynchronize());
    check_cuda(cudaMemcpy(a.data(), da, result_bytes, cudaMemcpyDeviceToHost));
    check_cuda(cudaMemcpy(b.data(), db, result_bytes, cudaMemcpyDeviceToHost));
    size_t mismatches = 0;
    float max_abs = 0;
    for (int i = 1; i <= rows; ++i) {
        if (!std::isfinite(a[i]) || !std::isfinite(b[i])) { throw std::runtime_error("nonfinite result"); }
        if (std::memcmp(&a[i], &b[i], sizeof(float))) { ++mismatches; }
        max_abs = std::max(max_abs, std::abs(a[i] - b[i]));
    }
    if (a.front() != canary || a.back() != canary || b.front() != canary || b.back() != canary) {
        throw std::runtime_error("output canary changed");
    }
    const float baseline_us = time_unit<1>(du, dg, dy, da + 1, k, rows);
    const float candidate_us = time_unit<12>(du, dg, dy, db + 1, k, rows);
    std::printf("{\"seed\":%u,\"pattern\":%d,\"rows\":%d,\"mismatches\":%zu,\"max_abs\":%.9g,\"baseline_us\":%.3f,\"occ12_us\":%.3f}\n",
                seed, pattern, rows, mismatches, max_abs, baseline_us, candidate_us);
    check_cuda(cudaFree(du)); check_cuda(cudaFree(dg)); check_cuda(cudaFree(dy));
    check_cuda(cudaFree(da)); check_cuda(cudaFree(db));
    if (mismatches) { throw std::runtime_error("bitwise baseline/candidate mismatch"); }
}

int main() {
    try {
        cudaDeviceProp props{};
        check_cuda(cudaGetDeviceProperties(&props, 0));
        if (props.major != 8 || props.minor != 6) { throw std::runtime_error("validator requires sm86"); }
        cudaFuncAttributes a{}, b{};
        check_cuda(cudaFuncGetAttributes(&a, mul_mat_vec_q<GGML_TYPE_Q4_K, 1, true, false, false, false, 1>));
        check_cuda(cudaFuncGetAttributes(&b, mul_mat_vec_q<GGML_TYPE_Q4_K, 1, true, false, false, false, 12>));
        int blocks_a, blocks_b;
        check_cuda(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&blocks_a,
            mul_mat_vec_q<GGML_TYPE_Q4_K, 1, true, false, false, false, 1>, 128, 0));
        check_cuda(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&blocks_b,
            mul_mat_vec_q<GGML_TYPE_Q4_K, 1, true, false, false, false, 12>, 128, 0));
        std::printf("{\"baseline_regs\":%d,\"occ12_regs\":%d,\"baseline_local_bytes\":%zu,\"occ12_local_bytes\":%zu,\"baseline_blocks\":%d,\"occ12_blocks\":%d}\n",
                    a.numRegs, b.numRegs, a.localSizeBytes, b.localSizeBytes, blocks_a, blocks_b);
        for (unsigned seed : {1u, 17u, 777u}) {
            for (int pattern = 0; pattern < 4; ++pattern) { run_case(seed, pattern); }
        }
        return 0;
    } catch (const std::exception & e) {
        std::fprintf(stderr, "FAIL: %s\n", e.what());
        return 1;
    }
}
