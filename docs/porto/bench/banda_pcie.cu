// BANDA VERA DELLA COPIA, nella forma esatta che userebbe la cache esperti:
// blocchi da 6,75 MiB (gate+up+down di UN esperto) da RAM pinnata a VRAM, con
// cudaMemcpyAsync su stream dedicato.
//
// Serve perche' i "25 GiB/s" del PCIe 4.0 x16 sono di targa e tutta la colonna
// "ms esposti" della simulazione ci si divide per. Stasera una costante non
// verificata mi ha gia' ribaltato un verdetto due volte.
#include <cstdio>
#include <cuda_runtime.h>
int main() {
    const size_t E = (size_t)(6.75 * 1024 * 1024);   // un esperto
    const int    N = 400;                            // copie per giro
    void *h, *d;
    if (cudaHostAlloc(&h, E * 8, cudaHostAllocDefault) != cudaSuccess) { printf("host alloc fallita\n"); return 1; }
    if (cudaMalloc(&d, E * 8) != cudaSuccess) { printf("device alloc fallita\n"); return 1; }
    cudaStream_t s; cudaStreamCreate(&s);
    cudaEvent_t a, b; cudaEventCreate(&a); cudaEventCreate(&b);
    for (int giro = 0; giro < 3; giro++) {
        cudaEventRecord(a, s);
        for (int i = 0; i < N; i++)
            cudaMemcpyAsync((char*)d + (i % 8) * E, (char*)h + (i % 8) * E, E, cudaMemcpyHostToDevice, s);
        cudaEventRecord(b, s);
        cudaStreamSynchronize(s);
        float ms = 0; cudaEventElapsedTime(&ms, a, b);
        double gib = (double)N * E / (1024.0*1024.0*1024.0);
        printf("  %3d copie da 6,75 MiB: %7.2f ms  ->  %6.2f GiB/s   (%.3f ms per esperto)\n",
               N, ms, gib / (ms/1000.0), ms / N);
    }
    // e il caso a blocco unico, per sapere quanto costa la frammentazione
    for (int giro = 0; giro < 2; giro++) {
        cudaEventRecord(a, s);
        cudaMemcpyAsync(d, h, E * 8, cudaMemcpyHostToDevice, s);
        cudaEventRecord(b, s);
        cudaStreamSynchronize(s);
        float ms = 0; cudaEventElapsedTime(&ms, a, b);
        printf("  blocco unico da %.1f MiB: %6.2f ms  ->  %6.2f GiB/s\n",
               E*8/1048576.0, ms, (double)E*8/(1024.0*1024.0*1024.0)/(ms/1000.0));
    }
    return 0;
}
