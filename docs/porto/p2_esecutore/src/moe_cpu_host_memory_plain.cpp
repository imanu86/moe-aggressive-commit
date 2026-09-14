// P2 — Fornitore di memoria «semplice»: malloc allineato, dev == host.
// Serve al test host-only e a qualunque banco senza GPU. Non e' usato nel server.

#include "moe_cpu_host_memory.h"

#include <cstdlib>
#include <cstring>

#if defined(_WIN32)
// `_aligned_malloc`/`_aligned_free` sono dichiarate in <malloc.h>, non in
// <stdlib.h>: senza questo include MSVC da' «identificatore non trovato».
// (difetto E2 della revisione del 14 settembre)
#  include <malloc.h>
#endif

namespace {

class plain_memory : public moe_cpu_host_memory {
    void * raw_ = nullptr;
    moe_cpu_host_block block_{};
public:
    ~plain_memory() override { release(); }

    bool allocate(size_t size, size_t align, moe_cpu_host_block * out, std::string * err) override {
        if (raw_) { if (err) *err = "gia' allocato"; return false; }
        if (align < 64) align = 64;
#if defined(_WIN32)
        raw_ = _aligned_malloc(size, align);
#else
        if (posix_memalign(&raw_, align, size) != 0) raw_ = nullptr;
#endif
        if (!raw_) { if (err) *err = "memoria insufficiente"; return false; }
        std::memset(raw_, 0, size);
        block_.host = raw_;
        block_.dev  = raw_;   // nessun dispositivo: gli alias coincidono
        block_.size = size;
        if (out) *out = block_;
        return true;
    }

    void release() override {
        if (!raw_) return;
#if defined(_WIN32)
        _aligned_free(raw_);
#else
        free(raw_);
#endif
        raw_   = nullptr;
        block_ = {};
    }

    const char * name() const override { return "plain"; }
};

} // namespace

std::unique_ptr<moe_cpu_host_memory> moe_cpu_host_memory_plain() {
    return std::unique_ptr<moe_cpu_host_memory>(new plain_memory());
}
