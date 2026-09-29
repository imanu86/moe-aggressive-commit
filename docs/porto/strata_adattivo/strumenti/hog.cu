// hog.cu - occupa VRAM come farebbe un altro programma, per collaudare la cache elastica di Strata (29/9/2026).
// Uso: hog.exe MiB secondi [MiB2 secondi2 ...]  -> tiene MiB per secondi, poi passa alla coppia successiva
// (0 MiB = niente), infine rilascia tutto. La memoria e' scritta, cosi' sotto WDDM e' davvero residente.
#include <cuda_runtime.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>

int main(int argc, char** argv) {
    if (argc < 3 || argc % 2 == 0) {
        std::fprintf(stderr, "uso: hog.exe MiB secondi [MiB secondi ...]\n");
        return 2;
    }
    void* p = nullptr;
    for (int i = 1; i + 1 < argc; i += 2) {
        const size_t mib = std::strtoull(argv[i], nullptr, 10);
        const int secs = std::atoi(argv[i + 1]);
        if (p != nullptr) { cudaFree(p); p = nullptr; }
        if (mib > 0) {
            if (cudaMalloc(&p, mib << 20) != cudaSuccess) {
                std::fprintf(stderr, "hog: cudaMalloc(%zu MiB) non riuscita\n", mib);
                return 1;
            }
            cudaMemset(p, 1, mib << 20);
            cudaDeviceSynchronize();
        }
        size_t f = 0, t = 0;
        cudaMemGetInfo(&f, &t);
        const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        char hms[16];
        std::strftime(hms, sizeof hms, "%H:%M:%S", std::localtime(&now));
        std::printf("[%s] hog: tengo %zu MiB per %d s (libera per me: %zu MiB)\n", hms, mib, secs, f >> 20);
        std::fflush(stdout);
        std::this_thread::sleep_for(std::chrono::seconds(secs));
    }
    if (p != nullptr) cudaFree(p);
    std::printf("hog: rilasciato tutto\n");
    return 0;
}
