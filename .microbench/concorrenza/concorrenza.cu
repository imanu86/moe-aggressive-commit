// IL MOTORE DI COPIA REGGE MENTRE LA GPU CALCOLA?
//
// E' il cardine del tetto misurato l'11/8 e non ha nessuna misura sotto.
//
// Il reperto (nsight_banco3, --cuda-graph-trace=node, banco sc_rif):
//   la GPU e' occupata al 97,3% e kern_copia e' il 41% del tempo GPU,
//   37,87 ms/token, sullo STREAM DI CALCOLO. Mentre copia, non calcola.
//     token = calcolo 54,2 ms + trasporto 37,9 ms   IN SERIE
//   Portando il trasporto sul motore di copia (24,4 GiB/s nel microbench
//   `blocco` = 28,2 ms per 707 MiB):
//     token = max(54,2 ; 28,2) = 54,2 ms  ->  18,5 t/s contro 11,22
//
// MA QUEI 24,4 GiB/s SONO STATI MISURATI A GPU SCARICA. Qui la GPU e' satura,
// e la copia scrive in VRAM: contende la stessa banda che il calcolo sta gia'
// consumando a leggere i pesi. Il `max(...)` presume una sovrapposizione che
// nessuno ha visto. Se i due si serializzano sulla banda VRAM, il tetto e'
// `54,2 + 28,2` e la leva vale ZERO.
//
// COSA MISURA, sulla geometria vera (esperti da 6,75 MiB in tre pezzi):
//   1. calcolo solo    un kernel che legge la VRAM a piena banda, come fanno i
//                      302 mul_mat_vec per token sui pesi residenti
//   2. copia solo      cudaMemcpyAsync in raffica da RAM mappata -> VRAM, un
//                      sync alla fine (il modo `dma_raffica` di blocco.cu)
//   3. INSIEME         i due su stream diversi, lanciati insieme, parete totale
//
// IL CANCELLO, SCRITTO PRIMA DEI NUMERI:
//   insieme <= 1,15 x max(calcolo, copia)  -> si sovrappongono, il tetto REGGE
//   insieme >= 0,85 x (calcolo + copia)    -> si serializzano, il tetto e' FALSO
//   in mezzo -> sovrapposizione parziale, e il guadagno e' la differenza
//               fra `insieme` e la somma, non il max
//
// Riporta anche quanto RALLENTA ciascuno dei due: e' quello il prezzo vero, e
// se il calcolo rallenta molto il conto va rifatto sul calcolo, non sulla copia.
//
// build:  nvcc -O3 -arch=sm_86 concorrenza.cu -o concorrenza.exe
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <vector>
#include <random>

#define CHECK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { \
    fprintf(stderr, "%s:%d %s -> %s\n", __FILE__, __LINE__, #x, cudaGetErrorString(e_)); \
    exit(1); } } while (0)

static const size_t PEZZO   = 2250ull * 1024;     // gate/up/down, 2,25 MiB
static const int    PEZZI   = 3;
static const size_t ESPERTO = PEZZO * PEZZI;      // 6,75 MiB

// Il carico: legge la VRAM in streaming, come mul_mat_vec sui pesi residenti.
// Non fa aritmetica pesante apposta -- il decode e' limitato dalla banda VRAM,
// non dalle FLOP, e la contesa che ci interessa e' proprio sulla banda.
__global__ static void kern_carico(const int4 * __restrict__ p, size_t n4, int giri, int * out) {
    long long acc = 0;
    for (int g = 0; g < giri; g++) {
        for (size_t i = (size_t) blockIdx.x * blockDim.x + threadIdx.x;
             i < n4; i += (size_t) gridDim.x * blockDim.x) {
            const int4 v = p[i];
            acc += (long long) v.x + v.y + v.z + v.w;
        }
    }
    if (acc == 123456789123LL) out[0] = (int) acc;   // impedisce l'eliminazione
}

int main(int argc, char ** argv) {
    const int N        = argc > 1 ? atoi(argv[1]) : 105;  // esperti: 105 x 6,75 = 707 MiB, un token
    const int GIRI     = argc > 2 ? atoi(argv[2]) : 20;
    const size_t HOST  = (size_t) (argc > 3 ? atoi(argv[3]) : 4) * 1024ull * 1024 * 1024;
    const int CARICO_G = argc > 4 ? atoi(argv[4]) : 24;   // passate del kernel di carico

    CHECK(cudaSetDevice(0));
    cudaDeviceProp prop; CHECK(cudaGetDeviceProperties(&prop, 0));
    const double MiB = (double) N * ESPERTO / 1048576.0;
    printf("%s | %d SM | N=%d esperti = %.0f MiB (un token del banco: 707 MiB)\n",
           prop.name, prop.multiProcessorCount, N, MiB);
    printf("%d giri, host %.1f GiB, carico %d passate\n\n", GIRI, HOST / 1073741824.0, CARICO_G);

    char * host = nullptr;
    CHECK(cudaHostAlloc(&host, HOST, cudaHostAllocMapped | cudaHostAllocPortable));
    memset(host, 7, 1024 * 1024);

    char * slab = nullptr;                       // destinazione delle copie
    CHECK(cudaMalloc(&slab, (size_t) N * ESPERTO));
    // sorgente del carico: buffer VRAM SEPARATO, cosi' il carico non legge
    // proprio i byte che la copia sta scrivendo (sarebbe un artefatto)
    const size_t CAR = 1024ull * 1024 * 1024;
    int4 * carico = nullptr;
    CHECK(cudaMalloc(&carico, CAR));
    CHECK(cudaMemset(carico, 3, CAR));
    int * out = nullptr; CHECK(cudaMalloc(&out, sizeof(int)));

    std::vector<size_t> off(N);
    std::mt19937_64 rng(12345);
    const size_t max_off = (HOST - ESPERTO) / ESPERTO;
    for (int i = 0; i < N; i++) off[i] = (rng() % max_off) * ESPERTO;

    cudaStream_t s_cop, s_cal;
    CHECK(cudaStreamCreate(&s_cop)); CHECK(cudaStreamCreate(&s_cal));
    cudaEvent_t a, b; CHECK(cudaEventCreate(&a)); CHECK(cudaEventCreate(&b));

    const size_t n4 = CAR / sizeof(int4);
    const int blocchi = prop.multiProcessorCount * 4;
    const double car_MiB = (double) CAR / 1048576.0 * CARICO_G;

    auto raffica = [&](cudaStream_t st) {
        for (int i = 0; i < N; i++)
            for (int q = 0; q < PEZZI; q++)
                CHECK(cudaMemcpyAsync(slab + (size_t) i * ESPERTO + q * PEZZO,
                                      host + off[i] + q * PEZZO,
                                      PEZZO, cudaMemcpyHostToDevice, st));
    };

    // scaldata
    kern_carico<<<blocchi, 256, 0, s_cal>>>(carico, n4, 2, out);
    raffica(s_cop);
    CHECK(cudaDeviceSynchronize());

    float ms_cal = 0, ms_cop = 0, ms_ins = 0;

    // 1. CALCOLO SOLO
    CHECK(cudaEventRecord(a, s_cal));
    for (int g = 0; g < GIRI; g++) kern_carico<<<blocchi, 256, 0, s_cal>>>(carico, n4, CARICO_G, out);
    CHECK(cudaEventRecord(b, s_cal));
    CHECK(cudaEventSynchronize(b));
    CHECK(cudaEventElapsedTime(&ms_cal, a, b));
    ms_cal /= GIRI;

    // 2. COPIA SOLA
    CHECK(cudaEventRecord(a, s_cop));
    for (int g = 0; g < GIRI; g++) raffica(s_cop);
    CHECK(cudaEventRecord(b, s_cop));
    CHECK(cudaEventSynchronize(b));
    CHECK(cudaEventElapsedTime(&ms_cop, a, b));
    ms_cop /= GIRI;

    // 3. INSIEME, su stream diversi. La parete la prende l'orologio dell'host:
    //    due eventi su stream diversi non misurano il totale.
    CHECK(cudaDeviceSynchronize());
    const auto t0 = std::chrono::steady_clock::now();
    for (int g = 0; g < GIRI; g++) {
        kern_carico<<<blocchi, 256, 0, s_cal>>>(carico, n4, CARICO_G, out);
        raffica(s_cop);
    }
    CHECK(cudaDeviceSynchronize());
    const auto t1 = std::chrono::steady_clock::now();
    ms_ins = std::chrono::duration<float, std::milli>(t1 - t0).count() / GIRI;

    printf("  %-14s %8.2f ms   (%.1f GiB/s di VRAM letta)\n",
           "calcolo solo", ms_cal, car_MiB / 1024.0 / (ms_cal / 1000.0));
    printf("  %-14s %8.2f ms   (%.2f GiB/s di trasporto)\n",
           "copia sola", ms_cop, MiB / 1024.0 / (ms_cop / 1000.0));
    printf("  %-14s %8.2f ms\n\n", "INSIEME", ms_ins);

    const float mx = ms_cal > ms_cop ? ms_cal : ms_cop;
    const float sm = ms_cal + ms_cop;
    printf("  max(calcolo, copia) = %.2f ms      somma = %.2f ms\n", mx, sm);
    printf("  insieme / max   = %.2f      insieme / somma = %.2f\n", ms_ins / mx, ms_ins / sm);
    if (ms_ins <= 1.15f * mx)       printf("  => SI SOVRAPPONGONO: il tetto di 18,5 t/s REGGE\n");
    else if (ms_ins >= 0.85f * sm)  printf("  => SI SERIALIZZANO sulla banda VRAM: il tetto e' FALSO, la leva vale ZERO\n");
    else {
        const float risp = sm - ms_ins;
        printf("  => sovrapposizione PARZIALE: si risparmiano %.2f ms su %.2f (%.0f%%)\n",
               risp, sm, 100.0f * risp / sm);
        printf("     il guadagno vero va calcolato su questo, non sul max\n");
    }
    printf("\n  costo MARGINALE della copia dentro il calcolo: %.2f ms invece di %.2f\n",
           ms_ins - ms_cal, ms_cop);
    printf("  cioe' il %.0f%% di quel che costa da sola.\n",
           100.0f * (ms_ins - ms_cal) / ms_cop);
    printf("  a GPU scarica il microbench `blocco` dava 24 GiB/s in tutte le modalita'.\n");
    printf("\n  CAVEAT: questo e' il verdetto dell'HARDWARE, non dello SCHEDULER. Qui i due\n");
    printf("  flussi sono indipendenti; in produzione la copia di uno strato deve finire\n");
    printf("  prima del mul_mat_vec che la consuma. Che il ferro regga e' condizione\n");
    printf("  NECESSARIA e non sufficiente: resta da vedere se il grafo sa esprimerlo.\n");
    return 0;
}
