// P2 — Fornitore di memoria mappata per il server.
//
// Non chiama CUDA direttamente: usa il buffer type `CUDA<n>_Mapped` del backend
// (ggml-cuda.cu:1447-1477, cudaHostAlloc(MAPPED|PORTABLE) + cudaHostGetDevicePointer)
// raggiunto per proc-address, esattamente come llama-moecache.cpp:461-466 fa con
// `ggml_backend_cuda_moe_demand_unbind`. Cosi' libllama non linka ggml-cuda.
//
// ATTENZIONE: per un tensore di quel buffer, `tensor->data` e' l'indirizzo
// DEVICE (get_base restituisce ctx->dev, ggml-cuda.cu:1372-1375). L'indirizzo
// host si ottiene SOLO da `ggml_cuda_mapped_tensor_host_ptr` (ggml-cuda.cu:1387).
// Su x86-64 i due coincidono (UVA) ma il codice non ci si appoggia.
//
// DA FARE IN P3: `ggml_cuda_mapped_tensor_host_ptr` non e' ancora nella tabella
// dei proc-address (ggml-cuda.cu:6015-6030). Va aggiunta la voce, altrimenti la
// risoluzione qui sotto fallisce e l'esecutore non si crea.
//
// NON compilato dal test host-only.

#include "moe_cpu_host_memory.h"

#include "ggml.h"
#include "ggml-backend.h"

namespace {

using mapped_buft_fn = ggml_backend_buffer_type_t (*)(int);
using mapped_host_fn = const void * (*)(const ggml_tensor *, size_t);

class cuda_mapped_memory : public moe_cpu_host_memory {
    int                     device_;
    ggml_context *          ctx_    = nullptr;
    ggml_backend_buffer_t   buf_    = nullptr;
    moe_cpu_host_block      block_{};
public:
    explicit cuda_mapped_memory(int device) : device_(device) {}
    ~cuda_mapped_memory() override { release(); }

    bool allocate(size_t size, size_t align, moe_cpu_host_block * out, std::string * err) override {
        auto fail = [&](const char * m) { if (err) *err = m; release(); return false; };
        if (buf_) return fail("gia' allocato");
        (void) align;  // il buffer type allinea a 128 (ggml-cuda.cu:1479-1482)

        ggml_backend_dev_t dev = ggml_backend_dev_by_name(device_ == 0 ? "CUDA0" : nullptr);
        if (!dev) {
            for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
                ggml_backend_dev_t d = ggml_backend_dev_get(i);
                if (ggml_backend_dev_type(d) == GGML_BACKEND_DEVICE_TYPE_GPU) { dev = d; break; }
            }
        }
        if (!dev) return fail("nessun dispositivo CUDA");

        ggml_backend_reg_t reg = ggml_backend_dev_backend_reg(dev);
        auto buft_fn = (mapped_buft_fn) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cuda_mapped_buffer_type");
        auto host_fn = (mapped_host_fn) ggml_backend_reg_get_proc_address(reg, "ggml_cuda_mapped_tensor_host_ptr");
        if (!buft_fn) return fail("buffer type mappato non esposto dal backend");
        if (!host_fn) return fail("ggml_cuda_mapped_tensor_host_ptr non esposta: aggiungerla in P3");

        ggml_backend_buffer_type_t buft = buft_fn(device_);
        if (!buft) return fail("buffer type mappato assente per questo dispositivo");

        ggml_init_params ip{};
        ip.mem_size   = ggml_tensor_overhead() * 2;
        ip.no_alloc   = true;
        ctx_ = ggml_init(ip);
        if (!ctx_) return fail("contesto ggml non creato");

        ggml_tensor * t = ggml_new_tensor_1d(ctx_, GGML_TYPE_I8, (int64_t) size);
        if (!t) return fail("tensore non creato");
        ggml_set_name(t, "moe_cpu_mapped");

        buf_ = ggml_backend_alloc_ctx_tensors_from_buft(ctx_, buft);
        if (!buf_) return fail("allocazione del buffer mappato fallita");

        const void * host = host_fn(t, 0);
        if (!host) return fail("indirizzo host del buffer mappato non risolvibile");

        block_.host = const_cast<void *>(host);
        block_.dev  = t->data;          // indirizzo DEVICE: e' quello che vedono i kernel
        block_.size = size;
        if (out) *out = block_;
        return true;
    }

    void release() override {
        if (buf_) { ggml_backend_buffer_free(buf_); buf_ = nullptr; }
        if (ctx_) { ggml_free(ctx_); ctx_ = nullptr; }
        block_ = {};
    }

    const char * name() const override { return "cuda-mapped"; }
};

} // namespace

std::unique_ptr<moe_cpu_host_memory> moe_cpu_host_memory_cuda_mapped(int device) {
    return std::unique_ptr<moe_cpu_host_memory>(new cuda_mapped_memory(device));
}
