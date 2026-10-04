// PCIe full-duplex check: host->device and device->host copies alone, then together on two streams.
// Pinned host buffers, 256 MiB per direction, 8 repetitions each, median GB/s. Build: nvcc -O2 -o pcie_duplex.exe
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdio>
#include <vector>

#define CK(x) do { cudaError_t e = (x); if (e != cudaSuccess) { std::printf("CUDA %s: %s\n", #x, cudaGetErrorString(e)); return 1; } } while (0)

static double median(std::vector<double> v) { std::sort(v.begin(), v.end()); return v[v.size() / 2]; }

int main() {
    cudaDeviceProp p{};
    CK(cudaGetDeviceProperties(&p, 0));
    std::printf("device %s, asyncEngineCount %d, pci %d:%d\n", p.name, p.asyncEngineCount, p.pciBusID, p.pciDeviceID);
    const size_t n = 256ull << 20;
    void *h_up, *h_down, *d_up, *d_down;
    CK(cudaHostAlloc(&h_up, n, cudaHostAllocDefault));
    CK(cudaHostAlloc(&h_down, n, cudaHostAllocDefault));
    CK(cudaMalloc(&d_up, n));
    CK(cudaMalloc(&d_down, n));
    cudaStream_t s1, s2;
    CK(cudaStreamCreateWithFlags(&s1, cudaStreamNonBlocking));
    CK(cudaStreamCreateWithFlags(&s2, cudaStreamNonBlocking));
    cudaEvent_t a0, a1, b0, b1;
    CK(cudaEventCreate(&a0)); CK(cudaEventCreate(&a1)); CK(cudaEventCreate(&b0)); CK(cudaEventCreate(&b1));
    const double gb = (double) n / 1e9;
    std::vector<double> up, down, both_up, both_down, both_wall;
    for (int r = 0; r < 9; ++r) {
        float ms = 0;
        CK(cudaEventRecord(a0, s1)); CK(cudaMemcpyAsync(d_up, h_up, n, cudaMemcpyHostToDevice, s1)); CK(cudaEventRecord(a1, s1));
        CK(cudaEventSynchronize(a1)); CK(cudaEventElapsedTime(&ms, a0, a1)); if (r) up.push_back(gb / (ms / 1e3));
        CK(cudaEventRecord(b0, s2)); CK(cudaMemcpyAsync(h_down, d_down, n, cudaMemcpyDeviceToHost, s2)); CK(cudaEventRecord(b1, s2));
        CK(cudaEventSynchronize(b1)); CK(cudaEventElapsedTime(&ms, b0, b1)); if (r) down.push_back(gb / (ms / 1e3));
        CK(cudaDeviceSynchronize());
        CK(cudaEventRecord(a0, s1)); CK(cudaEventRecord(b0, s2));
        CK(cudaMemcpyAsync(d_up, h_up, n, cudaMemcpyHostToDevice, s1));
        CK(cudaMemcpyAsync(h_down, d_down, n, cudaMemcpyDeviceToHost, s2));
        CK(cudaEventRecord(a1, s1)); CK(cudaEventRecord(b1, s2));
        CK(cudaDeviceSynchronize());
        float m1 = 0, m2 = 0, mw = 0;
        CK(cudaEventElapsedTime(&m1, a0, a1)); CK(cudaEventElapsedTime(&m2, b0, b1));
        mw = std::max(m1, m2);
        if (r) { both_up.push_back(gb / (m1 / 1e3)); both_down.push_back(gb / (m2 / 1e3)); both_wall.push_back(2 * gb / (mw / 1e3)); }
    }
    std::printf("H2D alone   %.2f GB/s\n", median(up));
    std::printf("D2H alone   %.2f GB/s\n", median(down));
    std::printf("together    H2D %.2f GB/s, D2H %.2f GB/s, aggregate %.2f GB/s\n", median(both_up), median(both_down),
                median(both_wall));
    return 0;
}
