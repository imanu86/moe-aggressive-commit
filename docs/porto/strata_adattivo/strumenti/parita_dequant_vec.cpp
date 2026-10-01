// Real GGUF rows: scalar/vector stores must be bitwise identical in all three output formats.
#include "strata/artifact/gguf_reader.hpp"
#include "strata/artifact/dequant.hpp"
#include "strata/kernels/dequant_bf16.hpp"
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <vector>

static void check(cudaError_t e) {
    if (e != cudaSuccess) { std::fprintf(stderr, "%s\n", cudaGetErrorString(e)); std::exit(2); }
}

int main(int argc, char** argv) {
    cudaDeviceProp prop{};
    check(cudaGetDeviceProperties(&prop, 0));
    if (prop.major != 7 || prop.minor != 5 || argc < 2) return 2;
    int cases = 0, failures = 0;
    std::set<int> done;
    for (int a = 1; a < argc; ++a) {
        strata::GgufFile file(argv[a]);
        for (const auto& t : file.tensors()) {
            int type = (int)t.type, be = 0, bb = 0;
            if (done.count(type) || t.shape.size() < 2 || t.shape[1] < 2 ||
                !strata::kernels::dequant_bf16_supported(type) || !strata::block_geometry(t.type, be, bb)) continue;
            int64_t cols = t.shape[0], rows = std::min<int64_t>(7, t.shape[1]-1);
            size_t bytes = (rows+1)*cols/be*bb;
            void* input = nullptr;
            void* output = nullptr;
            check(cudaMalloc(&input, bytes));
            check(cudaMalloc(&output, rows*cols*4+32));
            check(cudaMemcpy(input, file.tensor_data(t), bytes, cudaMemcpyHostToDevice));
            for (int mode = 0; mode < 3; ++mode) {
                size_t size = rows*cols*(mode == 2 ? 4 : 2)+32;
                std::vector<unsigned char> old(size), now(size);
                for (int vector = 0; vector < 2; ++vector) {
                    _putenv_s("STRATA_TC_SM75", vector ? "auto" : "0");
                    check(cudaMemset(output, 0xA5, size));
                    auto* dst = static_cast<unsigned char*>(output)+16;
                    if (mode == 0) strata::kernels::dequant_bf16(type, input, 1, rows, cols, (uint16_t*)dst, nullptr);
                    if (mode == 1) strata::kernels::dequant_f16(type, input, 1, rows, cols, (uint16_t*)dst, nullptr);
                    if (mode == 2) strata::kernels::dequant_f32(type, input, 1, rows, cols, (float*)dst, nullptr);
                    auto& result = vector ? now : old;
                    check(cudaMemcpy(result.data(), output, size, cudaMemcpyDeviceToHost));
                }
                bool guards = true;
                for (int i = 0; i < 16; ++i) guards &= now[i] == 0xA5 && now[size-1-i] == 0xA5;
                bool ok = guards && old == now;
                uint64_t digest = 14695981039346656037ull;
                for (auto value : now) { digest ^= value; digest *= 1099511628211ull; }
                ++cases;
                failures += !ok;
                std::printf("type=%d rows=%lld cols=%lld row0=1 format=%s bitwise=%s guards=%s hash=%016llx\n",
                    type, (long long)rows, (long long)cols, mode == 0 ? "bf16" : mode == 1 ? "fp16" : "fp32",
                    old == now ? "PASS" : "FAIL", guards ? "PASS" : "FAIL", (unsigned long long)digest);
            }
            cudaFree(input); cudaFree(output);
            done.insert(type);
        }
    }
    std::printf("cases=%d types=%zu failures=%d\n", cases, done.size(), failures);
    return cases && !failures ? 0 : 1;
}
