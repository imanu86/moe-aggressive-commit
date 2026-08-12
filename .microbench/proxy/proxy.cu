// IL PROXY HOST: vale il giro di ritorno per liberare gli SM?
//
// LA DOMANDA. Il nostro trasporto e' kern_copia/kern_fj_copia: un KERNEL che
// legge la RAM host mappata con gli SM. Misurato l'11/8 con nsys:
//   34,36 ms/token, 832 MiB, 23,6 GiB/s -> gia' al tetto del PCIe
//   e occupa 8 SM su 28, mentre i matmul girano sui restanti ~20
//   con tutti e 28 costerebbero 36,26 x 20/28 = 25,9 invece di 36,26
//   -> ~10,4 ms/token, ~+12%
//
// cudaMemcpyAsync userebbe ZERO SM, ma i suoi argomenti sono HOST-side mentre
// la lista di cosa copiare nasce da un top-k SUL DEVICE. La caccia esterna
// dell'11/8 dice che questa strada e' chiusa per tutti (le stream memory ops
// richiedono TCC su Windows; i device graph si aggiornano solo dall'host) e che
// TUTTI i sistemi esterni -- ProMoE, MoE-Infinity, ktransformers, vLLM --
// usano lo stesso schema: INDICIZZAZIONE SUL DEVICE, TRASPORTO SULL'HOST.
//
// IL PROXY HOST e' quello schema: il device scrive la lista in memoria pinnata
// mappata e alza una bandiera, un filo host gira in attesa, legge la lista e
// accoda le cudaMemcpyAsync. Costa un GIRO DI RITORNO per strato.
//
// PERCHE' NON SERVE PREVEDERE NIENTE. La sonda del fork dice copertura 5,2% al
// join: l'attesa la paghiamo GIA'. Il proxy non serve a evitarla, serve a NON
// occupare gli SM mentre aspettiamo. Quindi basta il trasporto dello STRATO
// CORRENTE, non un anticipo -- ed e' esattamente cio' che il cammino DMA
// esistente sbagliava, provando a prevedere e arrivando stantio (settemila
// chunk scartati, zero consegnati).
//
// IL CONTO DA VERIFICARE:
//   costo aggiunto   43 strati x (giro di ritorno) per token
//   costo tolto      ~10,4 ms/token di SM restituiti al matmul
//   conviene se il giro di ritorno sta sotto ~240 us per strato
//
// COSA MISURA, sulla geometria vera (esperti da 6,75 MiB in tre pezzi):
//   A  kernel      come oggi: 8 blocchi che leggono la mappata (il riferimento)
//   B  proxy host  il device alza la bandiera, l'host gira e accoda le memcpy
//   e in entrambi i casi CONCORRENTI a un kernel che legge la VRAM a piena
//   banda, cioe' il matmul che vogliamo liberare.
//
// IL CANCELLO, SCRITTO PRIMA:
//   B deve essere piu' veloce di A sul TOTALE, e il kernel di carico deve
//   essere piu' veloce in B che in A -- e' la prova che gli SM sono tornati
//   al calcolo. Se il totale migliora ma il carico no, il guadagno viene da
//   altro e il disegno non e' quello che credo.
//
// SI MISURA ANCHE IL GIRO DI RITORNO DA SOLO, perche' e' il numero che decide
// se in produzione il disegno regge: se e' 300 us per strato, 43 strati fanno
// 12,9 ms/token e si mangia tutto il guadagno.
//
// build:  nvcc -O3 -arch=sm_86 proxy.cu -o proxy.exe
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

// Il carico: legge la VRAM in streaming, come i mul_mat_vec sui pesi residenti.
__global__ static void kern_carico(const int4 * __restrict__ p, size_t n4, int giri, int * out) {
    long long acc = 0;
    for (int g = 0; g < giri; g++) {
        for (size_t i = (size_t) blockIdx.x * blockDim.x + threadIdx.x;
             i < n4; i += (size_t) gridDim.x * blockDim.x) {
            const int4 v = p[i];
            acc += (long long) v.x + v.y + v.z + v.w;
        }
    }
    if (acc == 123456789123LL) out[0] = (int) acc;
}

// Il trasporto di oggi: gli SM leggono la mappata.
//
// DIFETTO CORRETTO (era mio): la prima versione indicizzava i pezzi con
// blockIdx.x, quindi con 8 blocchi copiava 8 PEZZI (18 MiB) invece di tutti
// (692 MiB), e il confronto col proxy era fra due lavori diversi. In blocco.cu
// il lancio era <<<N*PEZZI>>>, un blocco per pezzo; qui i blocchi sono una
// MANOPOLA (l'ottimo misurato in produzione e' 8), quindi serve un passo di
// griglia sui pezzi, come fa kern_fj_copia in cache-esperti.cu.
__global__ static void kern_copia_finto(char * const * dst, const char * const * src,
                                        size_t n, int n_pezzi) {
    for (int j = blockIdx.x; j < n_pezzi; j += gridDim.x) {
        const char * s = src[j];
        char * d = dst[j];
        for (size_t i = threadIdx.x * 16; i < n; i += blockDim.x * 16) {
            *(int4 *) (d + i) = *(const int4 *) (s + i);
        }
    }
}

// Il device pubblica la lista e alza la bandiera. In produzione questo lavoro
// lo fa gia' kern_decidi/kern_fj_maschera: qui si simula solo la PUBBLICAZIONE,
// perche' e' quella che l'host deve vedere.
__global__ static void kern_pubblica(volatile int * bandiera, int epoca) {
    if (threadIdx.x == 0 && blockIdx.x == 0) {
        __threadfence_system();       // la lista sia visibile PRIMA della bandiera
        *bandiera = epoca;
    }
}

int main(int argc, char ** argv) {
    const int N        = argc > 1 ? atoi(argv[1]) : 105;  // 105 x 6,75 = 707 MiB = un token
    const int GIRI     = argc > 2 ? atoi(argv[2]) : 20;
    const size_t HOST  = (size_t) (argc > 3 ? atoi(argv[3]) : 4) * 1024ull * 1024 * 1024;
    const int CARICO_G = argc > 4 ? atoi(argv[4]) : 24;
    const int BLOCCHI  = argc > 5 ? atoi(argv[5]) : 8;    // l'ottimo misurato

    CHECK(cudaSetDevice(0));
    cudaDeviceProp prop; CHECK(cudaGetDeviceProperties(&prop, 0));
    const double MiB = (double) N * ESPERTO / 1048576.0;
    printf("%s | %d SM | N=%d esperti = %.0f MiB | %d giri | copia a %d blocchi\n\n",
           prop.name, prop.multiProcessorCount, N, MiB, GIRI, BLOCCHI);

    char * host = nullptr;
    CHECK(cudaHostAlloc(&host, HOST, cudaHostAllocMapped | cudaHostAllocPortable));
    char * host_dev = nullptr;
    CHECK(cudaHostGetDevicePointer(&host_dev, host, 0));
    memset(host, 7, 1024 * 1024);

    char * slab = nullptr;   CHECK(cudaMalloc(&slab, (size_t) N * ESPERTO));
    const size_t CAR = 1024ull * 1024 * 1024;
    int4 * carico = nullptr; CHECK(cudaMalloc(&carico, CAR));
    CHECK(cudaMemset(carico, 3, CAR));
    int * out = nullptr;     CHECK(cudaMalloc(&out, sizeof(int)));

    std::vector<size_t> off(N);
    std::mt19937_64 rng(12345);
    const size_t max_off = (HOST - ESPERTO) / ESPERTO;
    for (int i = 0; i < N; i++) off[i] = (rng() % max_off) * ESPERTO;

    // le tabelle per il kernel di copia (modo A)
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

    // la bandiera in memoria pinnata MAPPATA: il device scrive, l'host legge
    volatile int * bandiera_h = nullptr;
    CHECK(cudaHostAlloc((void **) &bandiera_h, sizeof(int),
                        cudaHostAllocMapped | cudaHostAllocPortable));
    *bandiera_h = 0;
    int * bandiera_d = nullptr;
    CHECK(cudaHostGetDevicePointer((void **) &bandiera_d, (void *) bandiera_h, 0));

    cudaStream_t s_cop, s_cal;
    CHECK(cudaStreamCreate(&s_cop)); CHECK(cudaStreamCreate(&s_cal));
    const size_t n4 = CAR / sizeof(int4);
    const int blocchi_carico = prop.multiProcessorCount * 4;

    auto raffica = [&](cudaStream_t st) {
        for (int i = 0; i < N; i++)
            for (int q = 0; q < PEZZI; q++)
                CHECK(cudaMemcpyAsync(slab + (size_t) i * ESPERTO + q * PEZZO,
                                      host + off[i] + q * PEZZO,
                                      PEZZO, cudaMemcpyHostToDevice, st));
    };

    // scaldata
    kern_carico<<<blocchi_carico, 256, 0, s_cal>>>(carico, n4, 2, out);
    kern_copia_finto<<<BLOCCHI, 256, 0, s_cop>>>(d_dst, d_src, PEZZO, N * PEZZI);
    raffica(s_cop);
    CHECK(cudaDeviceSynchronize());

    cudaEvent_t e0, e1; CHECK(cudaEventCreate(&e0)); CHECK(cudaEventCreate(&e1));
    float ms_carico_solo = 0;

    // ---- IL GIRO DI RITORNO, MISURATO DA SOLO ----
    // DIFETTO CORRETTO (era mio): la prima versione lo misurava con
    // kern_pubblica accodato DIETRO la raffica dell'iterazione precedente,
    // quindi l'host aspettava il DRENAGGIO della coda (77 ms), non la latenza
    // device->host. Qui la coda e' vuota e non c'e' nient'altro in volo: e'
    // il numero che decide se il disegno regge in produzione.
    {
        CHECK(cudaDeviceSynchronize());
        *bandiera_h = 0;
        double tot = 0; const int PROVE = 200;
        for (int k = 1; k <= PROVE; k++) {
            const auto t0 = std::chrono::steady_clock::now();
            kern_pubblica<<<1, 1, 0, s_cop>>>(bandiera_d, k);
            while (*bandiera_h != k) { }
            const auto t1 = std::chrono::steady_clock::now();
            tot += std::chrono::duration<double, std::micro>(t1 - t0).count();
        }
        CHECK(cudaDeviceSynchronize());
        printf("  %-26s %8.2f us   (lancio + esecuzione + visibilita' all'host,\n",
               "GIRO DI RITORNO", tot / PROVE);
        printf("  %-26s              a coda VUOTA: e' il pavimento, non il caso medio)\n", "");
        printf("  %-26s %8.2f ms/token su 43 strati\n\n", "  -> in produzione", 43 * (tot / PROVE) / 1000.0);
    }

    // ---- 0. il carico DA SOLO, per sapere quanto vale un SM restituito ----
    CHECK(cudaEventRecord(e0, s_cal));
    for (int g = 0; g < GIRI; g++) kern_carico<<<blocchi_carico, 256, 0, s_cal>>>(carico, n4, CARICO_G, out);
    CHECK(cudaEventRecord(e1, s_cal));
    CHECK(cudaEventSynchronize(e1));
    CHECK(cudaEventElapsedTime(&ms_carico_solo, e0, e1));
    ms_carico_solo /= GIRI;

    // ---- A. OGGI: kernel di copia su stream separato, concorrente al carico ----
    CHECK(cudaDeviceSynchronize());
    float ms_car_A = 0;
    auto tA0 = std::chrono::steady_clock::now();
    CHECK(cudaEventRecord(e0, s_cal));
    for (int g = 0; g < GIRI; g++) {
        kern_carico<<<blocchi_carico, 256, 0, s_cal>>>(carico, n4, CARICO_G, out);
        kern_copia_finto<<<BLOCCHI, 256, 0, s_cop>>>(d_dst, d_src, PEZZO, N * PEZZI);
    }
    CHECK(cudaEventRecord(e1, s_cal));
    CHECK(cudaDeviceSynchronize());
    auto tA1 = std::chrono::steady_clock::now();
    CHECK(cudaEventElapsedTime(&ms_car_A, e0, e1));
    ms_car_A /= GIRI;
    const double ms_tot_A = std::chrono::duration<double, std::milli>(tA1 - tA0).count() / GIRI;

    // ---- B. PROXY HOST: il device alza la bandiera, l'host gira e accoda ----
    // Il giro di ritorno si misura da solo: bandiera alzata -> host la vede.
    CHECK(cudaDeviceSynchronize());
    *bandiera_h = 0;
    double us_giro_tot = 0;
    float ms_car_B = 0;
    auto tB0 = std::chrono::steady_clock::now();
    CHECK(cudaEventRecord(e0, s_cal));
    for (int g = 0; g < GIRI; g++) {
        kern_carico<<<blocchi_carico, 256, 0, s_cal>>>(carico, n4, CARICO_G, out);
        // il device pubblica: in produzione lo fa kern_fj_maschera
        kern_pubblica<<<1, 1, 0, s_cop>>>(bandiera_d, g + 1);
        // l'host gira in attesa, poi accoda le copie sul MOTORE
        const auto giro0 = std::chrono::steady_clock::now();
        while (*bandiera_h != g + 1) { /* spin */ }
        const auto giro1 = std::chrono::steady_clock::now();
        us_giro_tot += std::chrono::duration<double, std::micro>(giro1 - giro0).count();
        raffica(s_cop);
    }
    CHECK(cudaEventRecord(e1, s_cal));
    CHECK(cudaDeviceSynchronize());
    auto tB1 = std::chrono::steady_clock::now();
    CHECK(cudaEventElapsedTime(&ms_car_B, e0, e1));
    ms_car_B /= GIRI;
    const double ms_tot_B = std::chrono::duration<double, std::milli>(tB1 - tB0).count() / GIRI;
    const double us_giro = us_giro_tot / GIRI;

    printf("  %-26s %8.2f ms\n", "carico DA SOLO", ms_carico_solo);
    printf("\n  A) oggi: kernel di copia a %d blocchi\n", BLOCCHI);
    printf("  %-26s %8.2f ms   (+%.2f contro il carico solo)\n", "  carico dentro A", ms_car_A, ms_car_A - ms_carico_solo);
    printf("  %-26s %8.2f ms\n", "  totale A", ms_tot_A);
    printf("\n  B) proxy host: cudaMemcpyAsync sul motore\n");
    printf("  %-26s %8.2f ms   (+%.2f contro il carico solo)\n", "  carico dentro B", ms_car_B, ms_car_B - ms_carico_solo);
    printf("  %-26s %8.2f ms\n", "  totale B", ms_tot_B);
    printf("  %-26s %8.2f us  <- ARTEFATTO, NON LEGGERE: qui kern_pubblica e'\n", "  (giro nel ciclo)", us_giro);
    printf("  %-26s             accodato dietro la raffica precedente, quindi\n", "");
    printf("  %-26s             misura il DRENAGGIO della coda, non la latenza.\n", "");
    printf("  %-26s             Il giro vero e' quello a coda vuota, in cima.\n", "");

    printf("\n  --- I CANCELLI ---\n");
    const bool tot_ok = ms_tot_B < ms_tot_A;
    const bool car_ok = ms_car_B < ms_car_A;
    printf("  totale B < totale A          %s  (%.2f contro %.2f)\n", tot_ok ? "SI" : "NO", ms_tot_B, ms_tot_A);
    printf("  carico piu' veloce in B      %s  (%.2f contro %.2f)  <- gli SM sono tornati al calcolo\n",
           car_ok ? "SI" : "NO", ms_car_B, ms_car_A);
    if (tot_ok && !car_ok) {
        printf("  ATTENZIONE: il totale migliora ma il carico no. Il guadagno viene da\n");
        printf("  altro e il disegno non e' quello che credo: NON costruirci sopra.\n");
    }
    printf("\n  --- IL CONTO IN PRODUZIONE ---\n");
    printf("  43 strati x %.1f us di giro = %.2f ms/token di latenza aggiunta\n", us_giro, 43 * us_giro / 1000.0);
    printf("  contro ~10,4 ms/token di SM restituiti al matmul\n");
    printf("  conviene se il giro sta sotto ~240 us per strato\n");
    printf("\n  CAVEAT: qui l'host gira in attesa e non fa altro. In produzione lo\n");
    printf("  stesso filo serve anche il resto, e la cattura dei CUDA graph NON puo'\n");
    printf("  contenere un intervento host per strato. Questo microbench misura se il\n");
    printf("  gioco vale, non se il disegno e' realizzabile com'e'.\n");
    return 0;
}
