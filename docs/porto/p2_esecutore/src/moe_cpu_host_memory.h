// P2 — Fornitore dei buffer host mappati dell'esecutore.
//
// L'esecutore non chiama CUDA. Riceve un fornitore che sa restituire, per una
// stessa allocazione, l'indirizzo HOST (quello che la CPU dereferenzia) e
// l'indirizzo DEVICE (quello che i kernel vedono). Due implementazioni:
//
//  - `moe_cpu_host_memory_plain()`: malloc allineato, dev == host. Serve al
//    test host-only e a qualunque banco senza GPU.
//  - `moe_cpu_host_memory_cuda_mapped(device)`: allocazione sul buffer type
//    `CUDA<n>_Mapped` (ggml-cuda.cu:1447-1477, cudaHostAlloc(MAPPED|PORTABLE)
//    + cudaHostGetDevicePointer), raggiunto per proc-address come gia' fa
//    llama-moecache.cpp:461-466 per `ggml_backend_cuda_moe_demand_unbind`.
//    Vive in un file separato che il test non compila.
//
// ATTENZIONE (difetto costoso se lo si dimentica): per un tensore allocato su
// `CUDA<n>_Mapped`, `tensor->data` e' l'indirizzo DEVICE, perche' get_base
// restituisce ctx->dev (ggml-cuda.cu:1372-1375). Su x86-64 host e device
// coincidono (UVA), ma il codice NON deve dipenderne: l'indirizzo host si
// ottiene solo da `ggml_cuda_mapped_tensor_host_ptr` (ggml-cuda.cu:1387).

#ifndef MOE_CPU_HOST_MEMORY_H
#define MOE_CPU_HOST_MEMORY_H

#include <cstddef>
#include <memory>
#include <string>

struct moe_cpu_host_block {
    void * host = nullptr;
    void * dev  = nullptr;
    size_t size = 0;
};

class moe_cpu_host_memory {
public:
    virtual ~moe_cpu_host_memory() = default;

    // Una sola chiamata per esecutore: un blocco unico, poi suddiviso
    // internamente. Allineamento richiesto: 64 byte o piu'.
    virtual bool allocate(size_t size, size_t align, moe_cpu_host_block * out, std::string * err) = 0;

    // Rilascio esplicito. L'esecutore lo invoca nel proprio distruttore, DOPO
    // aver disinstallato i hook e atteso il pool: i graph che referenziano
    // questi indirizzi devono essere gia' stati distrutti.
    virtual void release() = 0;

    virtual const char * name() const = 0;
};

std::unique_ptr<moe_cpu_host_memory> moe_cpu_host_memory_plain();

// Definita in moe_cpu_host_memory_cuda.cpp (non compilata dal test host-only).
std::unique_ptr<moe_cpu_host_memory> moe_cpu_host_memory_cuda_mapped(int device);

#endif // MOE_CPU_HOST_MEMORY_H
