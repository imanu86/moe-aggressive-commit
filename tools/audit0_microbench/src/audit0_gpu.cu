#include <cuda_runtime.h>
#include <cuda_fp16.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr uint32_t kInputDim = 4096;
constexpr uint32_t kMidDim = 2048;
constexpr uint32_t kOutputDim = 4096;
constexpr size_t kD2hBytes = 16 * 1024;
constexpr uint32_t kThreads = 256;
constexpr size_t kQ1BlockWeights = 128;
constexpr size_t kQ1BlockBytes = 18;
constexpr size_t kIq2BlockWeights = 256;
constexpr size_t kIq2BlockBytes = 66;
constexpr size_t kQ2kBlockWeights = 256;
constexpr size_t kQ2kBlockBytes = 84;

#include "ds4_iq2_tables_cuda.inc"

struct Options {
    uint32_t reps = 101;
    uint32_t warmups = 10;
    double q1_copy_mb = 5.6;
    double q2_copy_mb = 7.6;
    std::string variant = "all";
};

[[noreturn]] void fail(const std::string &message) {
    throw std::runtime_error(message);
}

void cuda_check(cudaError_t error, const char *operation) {
    if (error != cudaSuccess) {
        fail(std::string(operation) + ": " + cudaGetErrorString(error));
    }
}

uint32_t parse_u32(const std::string &text, const char *name) {
    char *end = nullptr;
    const unsigned long value = std::strtoul(text.c_str(), &end, 10);
    if (!end || *end != '\0' || value > UINT32_MAX) {
        fail(std::string("invalid ") + name + ": " + text);
    }
    return static_cast<uint32_t>(value);
}

double parse_double(const std::string &text, const char *name) {
    char *end = nullptr;
    const double value = std::strtod(text.c_str(), &end);
    if (!end || *end != '\0' || !(value > 0.0)) {
        fail(std::string("invalid ") + name + ": " + text);
    }
    return value;
}

Options parse_options(int argc, char **argv) {
    Options result;
    for (int i = 1; i < argc; ++i) {
        const std::string argument(argv[i]);
        const auto value = [&](const char *prefix) {
            return argument.substr(std::strlen(prefix));
        };
        if (argument == "--help") {
            std::cout
                << "audit0_gpu [--variant=all|q1|q2] [--reps=N] [--warmups=N]\n"
                << "           [--q1-copy-mb=5.6] [--q2-copy-mb=7.6]\n";
            std::exit(0);
        } else if (argument.rfind("--variant=", 0) == 0) {
            result.variant = value("--variant=");
        } else if (argument.rfind("--reps=", 0) == 0) {
            result.reps = parse_u32(value("--reps="), "reps");
        } else if (argument.rfind("--warmups=", 0) == 0) {
            result.warmups = parse_u32(value("--warmups="), "warmups");
        } else if (argument.rfind("--q1-copy-mb=", 0) == 0) {
            result.q1_copy_mb =
                parse_double(value("--q1-copy-mb="), "Q1 copy MB");
        } else if (argument.rfind("--q2-copy-mb=", 0) == 0) {
            result.q2_copy_mb =
                parse_double(value("--q2-copy-mb="), "Q2 copy MB");
        } else {
            fail("unknown argument: " + argument);
        }
    }
    if (result.variant != "all" && result.variant != "q1" &&
        result.variant != "q2") {
        fail("--variant must be all, q1, or q2");
    }
    if (result.reps < 100) fail("--reps must be at least 100");
    if (result.warmups == 0) fail("--warmups must be positive");
    return result;
}

__device__ __forceinline__ float half_bits_to_float(uint16_t bits) {
    return __half2float(*reinterpret_cast<const __half *>(&bits));
}

__device__ __forceinline__ float q1_value(
        const uint8_t *matrix,
        uint32_t row,
        uint32_t column,
        uint32_t input_dim) {
    const size_t blocks_per_row = input_dim / kQ1BlockWeights;
    const uint8_t *block =
        matrix + (static_cast<size_t>(row) * blocks_per_row +
                  column / kQ1BlockWeights) * kQ1BlockBytes;
    const uint32_t local = column & (kQ1BlockWeights - 1);
    const uint32_t bit = (block[2 + local / 8] >> (local & 7)) & 1u;
    uint16_t scale_bits;
    memcpy(&scale_bits, block, sizeof(scale_bits));
    return half_bits_to_float(scale_bits) * (bit ? 1.0f : -1.0f);
}

__device__ __forceinline__ uint16_t load_u16_le(const uint8_t *source) {
    return static_cast<uint16_t>(source[0]) |
           static_cast<uint16_t>(source[1] << 8);
}

__device__ __forceinline__ uint32_t load_u32_le(const uint8_t *source) {
    return static_cast<uint32_t>(source[0]) |
           (static_cast<uint32_t>(source[1]) << 8) |
           (static_cast<uint32_t>(source[2]) << 16) |
           (static_cast<uint32_t>(source[3]) << 24);
}

__device__ __forceinline__ float iq2_xxs_value(
        const uint8_t *matrix,
        uint32_t row,
        uint32_t column,
        uint32_t input_dim) {
    const size_t blocks_per_row = input_dim / kIq2BlockWeights;
    const uint8_t *block =
        matrix + (static_cast<size_t>(row) * blocks_per_row +
                  column / kIq2BlockWeights) * kIq2BlockBytes;
    const uint32_t local = column & (kIq2BlockWeights - 1);
    const uint32_t group32 = local / 32;
    const uint32_t lane32 = local & 31;
    const uint32_t group8 = lane32 / 8;
    const uint32_t lane8 = lane32 & 7;
    const uint8_t *packed = block + 2 + group32 * 8;
    const uint32_t aux0 = load_u32_le(packed);
    const uint32_t aux1 = load_u32_le(packed + 4);
    const uint32_t grid_index = (aux0 >> (8 * group8)) & 0xffu;
    const uint32_t sign_index = (aux1 >> (7 * group8)) & 0x7fu;
    uint32_t signs = audit0_ksigns_iq2xs[sign_index];
    signs ^= (__popc(signs) & 1u) << 7;
    const uint64_t grid = audit0_iq2xxs_grid[grid_index];
    const uint32_t magnitude =
        static_cast<uint32_t>((grid >> (8 * lane8)) & 0xffu);
    const float sign = (signs & (1u << lane8)) ? -1.0f : 1.0f;
    const float scale = static_cast<float>(2u * (aux1 >> 28) + 1u);
    return 0.125f * half_bits_to_float(load_u16_le(block)) *
           scale * sign * static_cast<float>(magnitude);
}

__device__ __forceinline__ float q2_k_value(
        const uint8_t *matrix,
        uint32_t row,
        uint32_t column,
        uint32_t input_dim) {
    const size_t blocks_per_row = input_dim / kQ2kBlockWeights;
    const uint8_t *block =
        matrix + (static_cast<size_t>(row) * blocks_per_row +
                  column / kQ2kBlockWeights) * kQ2kBlockBytes;
    const uint32_t local = column & (kQ2kBlockWeights - 1);
    const uint32_t scale_index = local / 16;
    const uint8_t scale_min = block[scale_index];
    const uint32_t q_index = (local / 128) * 32 + (local & 31);
    const uint32_t shift = 2 * ((local / 32) & 3);
    const uint32_t code = (block[16 + q_index] >> shift) & 3u;
    const float d = half_bits_to_float(load_u16_le(block + 80));
    const float dmin = half_bits_to_float(load_u16_le(block + 82));
    return d * static_cast<float>(scale_min & 0x0fu) *
               static_cast<float>(code) -
           dmin * static_cast<float>(scale_min >> 4);
}

template <bool Q1>
__global__ void gate_up_swiglu_kernel(
        const uint8_t *gate,
        const uint8_t *up,
        const float *input,
        float *mid) {
    const uint32_t row = blockIdx.x;
    float gate_sum = 0.0f;
    float up_sum = 0.0f;
    for (uint32_t column = threadIdx.x; column < kInputDim; column += blockDim.x) {
        const float x = input[column];
        if constexpr (Q1) {
            gate_sum += q1_value(gate, row, column, kInputDim) * x;
            up_sum += q1_value(up, row, column, kInputDim) * x;
        } else {
            gate_sum += iq2_xxs_value(gate, row, column, kInputDim) * x;
            up_sum += iq2_xxs_value(up, row, column, kInputDim) * x;
        }
    }
    __shared__ float gate_reduction[kThreads];
    __shared__ float up_reduction[kThreads];
    gate_reduction[threadIdx.x] = gate_sum;
    up_reduction[threadIdx.x] = up_sum;
    __syncthreads();
    for (uint32_t stride = blockDim.x / 2; stride != 0; stride >>= 1) {
        if (threadIdx.x < stride) {
            gate_reduction[threadIdx.x] += gate_reduction[threadIdx.x + stride];
            up_reduction[threadIdx.x] += up_reduction[threadIdx.x + stride];
        }
        __syncthreads();
    }
    if (threadIdx.x == 0) {
        const float value = gate_reduction[0];
        mid[row] = (value / (1.0f + expf(-value))) * up_reduction[0];
    }
}

template <bool Q1>
__global__ void down_kernel(
        const uint8_t *down,
        const float *mid,
        float *output) {
    const uint32_t row = blockIdx.x;
    float sum = 0.0f;
    for (uint32_t column = threadIdx.x; column < kMidDim; column += blockDim.x) {
        if constexpr (Q1) {
            sum += q1_value(down, row, column, kMidDim) * mid[column];
        } else {
            sum += q2_k_value(down, row, column, kMidDim) * mid[column];
        }
    }
    __shared__ float reduction[kThreads];
    reduction[threadIdx.x] = sum;
    __syncthreads();
    for (uint32_t stride = blockDim.x / 2; stride != 0; stride >>= 1) {
        if (threadIdx.x < stride) {
            reduction[threadIdx.x] += reduction[threadIdx.x + stride];
        }
        __syncthreads();
    }
    if (threadIdx.x == 0) output[row] = reduction[0];
}

size_t round_copy_bytes(double mb) {
    return static_cast<size_t>(std::llround(mb * 1000.0 * 1000.0));
}

size_t matrix_bytes(size_t block_weights, size_t block_bytes, uint32_t in, uint32_t out) {
    return static_cast<size_t>(out) * (in / block_weights) * block_bytes;
}

void store_half_bits(uint8_t *destination, uint16_t bits) {
    destination[0] = static_cast<uint8_t>(bits);
    destination[1] = static_cast<uint8_t>(bits >> 8);
}

void initialize_payload(uint8_t *payload, size_t bytes, bool q1) {
    uint32_t state = q1 ? 0x12345678u : 0x9abcdef0u;
    for (size_t i = 0; i < bytes; ++i) {
        state = state * 1664525u + 1013904223u;
        payload[i] = static_cast<uint8_t>(state >> 24);
    }
    if (q1) {
        const size_t gate_bytes =
            matrix_bytes(kQ1BlockWeights, kQ1BlockBytes, kInputDim, kMidDim);
        const size_t encoded_bytes = gate_bytes * 2 +
            matrix_bytes(kQ1BlockWeights, kQ1BlockBytes, kMidDim, kOutputDim);
        for (size_t offset = 0; offset < encoded_bytes; offset += kQ1BlockBytes) {
            store_half_bits(payload + offset, 0x1800);  // fp16 0.001953125
        }
    } else {
        const size_t gate_bytes =
            matrix_bytes(kIq2BlockWeights, kIq2BlockBytes, kInputDim, kMidDim);
        const size_t down_offset = gate_bytes * 2;
        const size_t down_bytes =
            matrix_bytes(kQ2kBlockWeights, kQ2kBlockBytes, kMidDim, kOutputDim);
        for (size_t offset = 0; offset < down_offset; offset += kIq2BlockBytes) {
            store_half_bits(payload + offset, 0x1400);  // fp16 0.0009765625
        }
        for (size_t offset = down_offset; offset < down_offset + down_bytes;
             offset += kQ2kBlockBytes) {
            store_half_bits(payload + offset + 80, 0x1800);
            store_half_bits(payload + offset + 82, 0x1000);
        }
    }
}

double percentile_sorted(const std::vector<float> &sorted, double q) {
    const double index = q * static_cast<double>(sorted.size() - 1);
    const size_t lo = static_cast<size_t>(index);
    const size_t hi = std::min(lo + 1, sorted.size() - 1);
    const double fraction = index - static_cast<double>(lo);
    return sorted[lo] * (1.0 - fraction) + sorted[hi] * fraction;
}

struct Summary {
    double median_us = 0.0;
    double p10_us = 0.0;
    double p90_us = 0.0;
    double min_us = 0.0;
    double max_us = 0.0;
};

Summary summarize(std::vector<float> milliseconds) {
    std::sort(milliseconds.begin(), milliseconds.end());
    Summary result;
    result.median_us = percentile_sorted(milliseconds, 0.50) * 1000.0;
    result.p10_us = percentile_sorted(milliseconds, 0.10) * 1000.0;
    result.p90_us = percentile_sorted(milliseconds, 0.90) * 1000.0;
    result.min_us = milliseconds.front() * 1000.0;
    result.max_us = milliseconds.back() * 1000.0;
    return result;
}

template <bool Q1>
void launch_ffn(
        uint8_t *device_payload,
        float *device_input,
        float *device_mid,
        float *device_output,
        cudaStream_t stream) {
    constexpr size_t block_bytes = Q1 ? kQ1BlockBytes : kIq2BlockBytes;
    const size_t gate_bytes = matrix_bytes(
        Q1 ? kQ1BlockWeights : kIq2BlockWeights,
        block_bytes, kInputDim, kMidDim);
    const size_t up_bytes = gate_bytes;
    const uint8_t *gate = device_payload;
    const uint8_t *up = device_payload + gate_bytes;
    const uint8_t *down = device_payload + gate_bytes + up_bytes;
    gate_up_swiglu_kernel<Q1><<<kMidDim, kThreads, 0, stream>>>(
        gate, up, device_input, device_mid);
    down_kernel<Q1><<<kOutputDim, kThreads, 0, stream>>>(
        down, device_mid, device_output);
}

template <bool Q1>
void run_variant(
        const char *name,
        size_t copy_bytes,
        uint32_t warmups,
        uint32_t reps,
        cudaStream_t stream,
        float *device_input) {
    const size_t gate_bytes = matrix_bytes(
        Q1 ? kQ1BlockWeights : kIq2BlockWeights,
        Q1 ? kQ1BlockBytes : kIq2BlockBytes,
        kInputDim, kMidDim);
    const size_t up_bytes = gate_bytes;
    const size_t down_bytes = matrix_bytes(
        Q1 ? kQ1BlockWeights : kQ2kBlockWeights,
        Q1 ? kQ1BlockBytes : kQ2kBlockBytes,
        kMidDim, kOutputDim);
    const size_t encoded_bytes = gate_bytes + up_bytes + down_bytes;
    if (copy_bytes < encoded_bytes) {
        fail(std::string(name) + " copy payload is smaller than its encoded FFN");
    }

    uint8_t *host_payload = nullptr;
    uint8_t *device_payload = nullptr;
    float *host_output = nullptr;
    float *device_mid = nullptr;
    float *device_output = nullptr;
    cudaEvent_t begin = nullptr;
    cudaEvent_t end = nullptr;
    cuda_check(cudaHostAlloc(&host_payload, copy_bytes, cudaHostAllocDefault), "cudaHostAlloc payload");
    cuda_check(cudaHostAlloc(&host_output, kD2hBytes, cudaHostAllocDefault), "cudaHostAlloc output");
    cuda_check(cudaMalloc(&device_payload, copy_bytes), "cudaMalloc payload");
    cuda_check(cudaMalloc(&device_mid, kMidDim * sizeof(float)), "cudaMalloc mid");
    cuda_check(cudaMalloc(&device_output, kD2hBytes), "cudaMalloc output");
    cuda_check(cudaEventCreate(&begin), "cudaEventCreate begin");
    cuda_check(cudaEventCreate(&end), "cudaEventCreate end");
    initialize_payload(host_payload, copy_bytes, Q1);
    std::memset(host_output, 0, kD2hBytes);

    const auto end_to_end_once = [&]() {
        cuda_check(cudaMemcpyAsync(
            device_payload, host_payload, copy_bytes, cudaMemcpyHostToDevice, stream),
            "cudaMemcpyAsync H2D");
        launch_ffn<Q1>(
            device_payload, device_input, device_mid, device_output, stream);
        cuda_check(cudaGetLastError(), "FFN kernel launch");
        cuda_check(cudaMemcpyAsync(
            host_output, device_output, kD2hBytes, cudaMemcpyDeviceToHost, stream),
            "cudaMemcpyAsync D2H");
    };

    for (uint32_t i = 0; i < warmups; ++i) {
        end_to_end_once();
        cuda_check(cudaStreamSynchronize(stream), "warmup synchronize");
    }

    std::vector<float> e2e_ms;
    e2e_ms.reserve(reps);
    for (uint32_t i = 0; i < reps; ++i) {
        cuda_check(cudaEventRecord(begin, stream), "record E2E begin");
        end_to_end_once();
        cuda_check(cudaEventRecord(end, stream), "record E2E end");
        cuda_check(cudaEventSynchronize(end), "synchronize E2E end");
        float elapsed = 0.0f;
        cuda_check(cudaEventElapsedTime(&elapsed, begin, end), "elapsed E2E");
        e2e_ms.push_back(elapsed);
    }

    std::vector<float> h2d_ms;
    h2d_ms.reserve(reps);
    for (uint32_t i = 0; i < reps; ++i) {
        cuda_check(cudaEventRecord(begin, stream), "record H2D begin");
        cuda_check(cudaMemcpyAsync(
            device_payload, host_payload, copy_bytes, cudaMemcpyHostToDevice, stream),
            "pure cudaMemcpyAsync H2D");
        cuda_check(cudaEventRecord(end, stream), "record H2D end");
        cuda_check(cudaEventSynchronize(end), "synchronize H2D end");
        float elapsed = 0.0f;
        cuda_check(cudaEventElapsedTime(&elapsed, begin, end), "elapsed H2D");
        h2d_ms.push_back(elapsed);
    }

    const Summary e2e = summarize(std::move(e2e_ms));
    const Summary h2d = summarize(std::move(h2d_ms));
    const double gib_per_second =
        (static_cast<double>(copy_bytes) / (1024.0 * 1024.0 * 1024.0)) /
        (h2d.median_us * 1.0e-6);
    const double checksum =
        std::accumulate(host_output, host_output + kOutputDim, 0.0);
    std::cout << std::fixed << std::setprecision(3)
              << "GPU_RESULT variant=" << name
              << " copy_bytes=" << copy_bytes
              << " encoded_ffn_bytes=" << encoded_bytes
              << " d2h_bytes=" << kD2hBytes
              << " e2e_median_us=" << e2e.median_us
              << " e2e_p10_us=" << e2e.p10_us
              << " e2e_p90_us=" << e2e.p90_us
              << " e2e_min_us=" << e2e.min_us
              << " e2e_max_us=" << e2e.max_us
              << " h2d_median_us=" << h2d.median_us
              << " h2d_gib_s=" << gib_per_second
              << " checksum=" << checksum
              << '\n';

    cudaEventDestroy(end);
    cudaEventDestroy(begin);
    cudaFree(device_output);
    cudaFree(device_mid);
    cudaFree(device_payload);
    cudaFreeHost(host_output);
    cudaFreeHost(host_payload);
}

}  // namespace

int main(int argc, char **argv) {
    try {
        const Options options = parse_options(argc, argv);
        int device = 0;
        cuda_check(cudaGetDevice(&device), "cudaGetDevice");
        cudaDeviceProp properties{};
        cuda_check(cudaGetDeviceProperties(&properties, device), "cudaGetDeviceProperties");
        if (properties.major != 8 || properties.minor < 6) {
            fail("audit binary targets sm_86; expected compute capability 8.6");
        }

        cudaStream_t stream = nullptr;
        cuda_check(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking), "cudaStreamCreate");
        std::vector<float> host_input(kInputDim);
        for (uint32_t i = 0; i < kInputDim; ++i) {
            host_input[i] =
                0.75f * std::sin(static_cast<float>(i) * 0.0137f) +
                0.25f * std::cos(static_cast<float>(i) * 0.0311f);
        }
        float *device_input = nullptr;
        cuda_check(cudaMalloc(&device_input, kInputDim * sizeof(float)), "cudaMalloc input");
        cuda_check(cudaMemcpyAsync(
            device_input, host_input.data(), kInputDim * sizeof(float),
            cudaMemcpyHostToDevice, stream), "upload input");
        cuda_check(cudaStreamSynchronize(stream), "input synchronize");

        std::cout << "AUDIT0_GPU schema=1\n"
                  << "device_name=" << properties.name << '\n'
                  << "compute_capability=" << properties.major << '.'
                  << properties.minor << '\n'
                  << "reps=" << options.reps << '\n'
                  << "warmups=" << options.warmups << '\n'
                  << "timing=cuda_events_single_nonblocking_stream\n"
                  << "d2h_bytes=" << kD2hBytes << '\n'
                  << "base2_semantics=IQ2_XXS_gate_up_plus_Q2_K_down\n";

        if (options.variant == "all" || options.variant == "q1") {
            run_variant<true>(
                "q1_0",
                round_copy_bytes(options.q1_copy_mb),
                options.warmups,
                options.reps,
                stream,
                device_input);
        }
        if (options.variant == "all" || options.variant == "q2") {
            run_variant<false>(
                "base_iq2_xxs_q2_k",
                round_copy_bytes(options.q2_copy_mb),
                options.warmups,
                options.reps,
                stream,
                device_input);
        }

        cudaFree(device_input);
        cudaStreamDestroy(stream);
        std::cout << "AUDIT0_GPU status=PASS\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "AUDIT0_GPU status=FAIL error=" << error.what() << '\n';
        return 1;
    }
}
