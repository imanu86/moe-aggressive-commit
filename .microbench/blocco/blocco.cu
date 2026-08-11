// QUANTO COSTA PORTARLI IN BLOCCO invece che un pezzo per volta.
//
// Idea dell'utente, 11/8: «sapendo in anticipo cosa dobbiamo portare non c'e'
// bisogno di richiamare un pezzo alla volta, possiamo portarli in blocco».
//
// PERCHE' E' LA DOMANDA GIUSTA. Misurato in produzione lo stesso giorno, il
// trasporto degli esperti viaggia a 5,5 GiB/s a domanda e 9,9 GiB/s col
// prefetch -- contro i 18,4 del letto mappato e i 24,4 del DMA. Non siamo
// vicini al limite di banda in nessuno dei due casi: il collo e' PER
// OPERAZIONE. Se e' cosi', amortizzarlo su un lancio solo vale piu' di
// qualunque miglioria della previsione (che infatti e' gia' stata falsificata:
// con la pianificazione esatta il prefetch fa 5,97 t/s contro 5,89 del cieco).
//
// COSA MISURA, sulla geometria vera: esperti da 6,75 MiB in tre pezzi
// (gate/up/down da 2,25 MiB), sorgenti SPARSE in RAM bloccata, destinazioni
// negli slot di una slab di VRAM.
//
//   1. kernel        come kern_copia oggi: gli SM leggono la memoria mappata
//   2. dma_uno       una cudaMemcpyAsync per pezzo, con sync dopo ogni gruppo
//                    (il caso patologico: e' cio' che fa DOMANDA_DMA, che
//                    infatti ha reso zero)
//   3. dma_raffica   tutte le cudaMemcpyAsync accodate, un sync alla fine
//                    <- QUESTO E' «IN BLOCCO»
//   4. contiguo      una sola copia della stessa massa, da sorgente contigua
//                    <- il tetto: non e' realizzabile (le sorgenti sono
//                       sparse) ma dice quanto lascia sul tavolo la sparsita'
//
// Il numero che decide: (3) contro (1). Se la raffica va molto piu' veloce del
// kernel, i 469 MiB per token passano da 94 ms a molto meno e la leva esiste.
// Se va uguale, il collo non e' il lancio ed e' la SPARSITA' -- e allora si
// riprogetta la disposizione in RAM, non l'orchestrazione.
//
// build:  nvcc -O3 -arch=sm_86 blocco.cu -o blocco.exe
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <algorithm>
#include <random>

#define CHECK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { \
    fprintf(stderr, "%s:%d %s -> %s\n", __FILE__, __LINE__, #x, cudaGetErrorString(e_)); \
    exit(1); } } while (0)

static const size_t PEZZO   = 2250ull * 1024;     // gate/up/down, 2,25 MiB
static const int    PEZZI   = 3;
static const size_t ESPERTO = PEZZO * PEZZI;      // 6,75 MiB

// Come kern_copia: un blocco per pezzo, tutti i thread copiano. Legge la
// memoria HOST MAPPATA, che sotto UVA e' indirizzabile dal device.
__global__ static void kern_copia_finto(char * const * dst, const char * const * src, size_t n) {
    const char * s = src[blockIdx.x];
    char * d = dst[blockIdx.x];
    for (size_t i = threadIdx.x * 16; i < n; i += blockDim.x * 16) {
        *(int4 *) (d + i) = *(const int4 *) (s + i);
    }
}

int main(int argc, char ** argv) {
    const int N       = argc > 1 ? atoi(argv[1]) : 339;   // esperti per passata
    const int GIRI    = argc > 2 ? atoi(argv[2]) : 20;
    const size_t HOST = (size_t) (argc > 3 ? atoi(argv[3]) : 4) * 1024ull * 1024 * 1024;

    CHECK(cudaSetDevice(0));
    printf("N=%d esperti da %.2f MiB (%d pezzi da %.2f MiB), %d giri, host %.1f GiB\n",
           N, ESPERTO / 1048576.0, PEZZI, PEZZO / 1048576.0, GIRI, HOST / 1073741824.0);

    // la RAM bloccata e MAPPATA, come in produzione
    char * host = nullptr;
    CHECK(cudaHostAlloc(&host, HOST, cudaHostAllocMapped | cudaHostAllocPortable));
    char * host_dev = nullptr;
    CHECK(cudaHostGetDevicePointer(&host_dev, host, 0));
    memset(host, 7, 1024 * 1024);   // toccarne un po' basta: interessa il trasporto

    char * slab = nullptr;
    CHECK(cudaMalloc(&slab, (size_t) N * ESPERTO));

    // sorgenti SPARSE: N esperti a caso nella regione host, come lo sono
    // davvero gli id che il router chiede
    std::vector<size_t> off(N);
    std::mt19937_64 rng(12345);
    const size_t max_off = (HOST - ESPERTO) / ESPERTO;
    for (int i = 0; i < N; i++) off[i] = (rng() % max_off) * ESPERTO;

    std::vector<const char *> h_src(N * PEZZI);
    std::vector<char *>       h_dst(N * PEZZI);
    for (int i = 0; i < N; i++)
        for (int q = 0; q < PEZZI; q++) {
            h_src[i * PEZZI + q] = host_dev + off[i] + q * PEZZO;
            h_dst[i * PEZZI + q] = slab + (size_t) i * ESPERTO + q * PEZZO;
        }
    const char ** d_src = nullptr; char ** d_dst = nullptr;
    CHECK(cudaMalloc(&d_src, N * PEZZI * sizeof(char *)));
    CHECK(cudaMalloc(&d_dst, N * PEZZI * sizeof(char *)));
    CHECK(cudaMemcpy(d_src, h_src.data(), N * PEZZI * sizeof(char *), cudaMemcpyHostToDevice));
    CHECK(cudaMemcpy(d_dst, h_dst.data(), N * PEZZI * sizeof(char *), cudaMemcpyHostToDevice));

    cudaStream_t s; CHECK(cudaStreamCreate(&s));
    cudaEvent_t a, b; CHECK(cudaEventCreate(&a)); CHECK(cudaEventCreate(&b));
    const double MiB = (double) N * ESPERTO / 1048576.0;

    auto riporta = [&](const char * nome, float ms_tot) {
        const double ms = ms_tot / GIRI;
        printf("  %-12s %8.2f ms   %6.2f GiB/s   %7.3f ms per esperto\n",
               nome, ms, MiB / 1024.0 / (ms / 1000.0), ms / N);
    };

    // scaldata
    kern_copia_finto<<<N * PEZZI, 256, 0, s>>>(d_dst, d_src, PEZZO);
    CHECK(cudaStreamSynchronize(s));

    float ms = 0;
    // 1. il kernel di oggi
    CHECK(cudaEventRecord(a, s));
    for (int g = 0; g < GIRI; g++) kern_copia_finto<<<N * PEZZI, 256, 0, s>>>(d_dst, d_src, PEZZO);
    CHECK(cudaEventRecord(b, s)); CHECK(cudaEventSynchronize(b));
    CHECK(cudaEventElapsedTime(&ms, a, b)); riporta("kernel", ms);

    // 2. una copia per volta, con sync dopo ogni esperto (cio' che fa DOMANDA_DMA)
    CHECK(cudaEventRecord(a, s));
    for (int g = 0; g < GIRI; g++)
        for (int i = 0; i < N; i++) {
            for (int q = 0; q < PEZZI; q++)
                CHECK(cudaMemcpyAsync(h_dst[i * PEZZI + q], h_src[i * PEZZI + q],
                                      PEZZO, cudaMemcpyDefault, s));
            CHECK(cudaStreamSynchronize(s));
        }
    CHECK(cudaEventRecord(b, s)); CHECK(cudaEventSynchronize(b));
    CHECK(cudaEventElapsedTime(&ms, a, b)); riporta("dma_uno", ms);

    // 3. IN BLOCCO: tutte accodate, un sync alla fine
    CHECK(cudaEventRecord(a, s));
    for (int g = 0; g < GIRI; g++) {
        for (int i = 0; i < N * PEZZI; i++)
            CHECK(cudaMemcpyAsync(h_dst[i], h_src[i], PEZZO, cudaMemcpyDefault, s));
    }
    CHECK(cudaEventRecord(b, s)); CHECK(cudaEventSynchronize(b));
    CHECK(cudaEventElapsedTime(&ms, a, b)); riporta("dma_raffica", ms);

    // 4. il tetto: una sola copia contigua della stessa massa
    CHECK(cudaEventRecord(a, s));
    for (int g = 0; g < GIRI; g++)
        CHECK(cudaMemcpyAsync(slab, host_dev, (size_t) N * ESPERTO, cudaMemcpyDefault, s));
    CHECK(cudaEventRecord(b, s)); CHECK(cudaEventSynchronize(b));
    CHECK(cudaEventElapsedTime(&ms, a, b)); riporta("contiguo", ms);

    printf("\n  il confronto che decide: dma_raffica contro kernel.\n");
    printf("  in produzione (11/8) il trasporto misura 5,5 GiB/s a domanda, 9,9 col prefetch.\n");
    printf("  469 MiB per token: a 5,5 sono 94 ms, a 18,4 sono 25,5.\n");
    return 0;
}
