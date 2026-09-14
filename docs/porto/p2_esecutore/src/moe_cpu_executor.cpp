// P2 — Esecutore CPU degli esperti MoE: implementazione.
//
// Derivato da `freetoken_hybrid/fused_cpu.hpp` (13 settembre). L'aritmetica —
// tratti CPU, vec_dot, quantizzazione dell'attivazione, piastrelle a 32 righe
// per gate/up e a 16 righe per down — e' la stessa che il prototipo ha
// verificato bit-identica al riferimento GGML. Cambiano la proprieta' degli
// oggetti, l'attesa, gli errori e l'annullamento.
//
// NON compilato in questa fase: la compilazione appartiene a una fase separata.

#include "moe_cpu_executor.h"

#include "ggml-cpu.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <thread>
#include <unordered_map>

#if defined(_WIN32)
#  ifndef NOMINMAX
#    define NOMINMAX
#  endif
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  include <windows.h>
#  include <intrin.h>
#  define MOE_CPU_PAUSE() _mm_pause()
#else
#  include <chrono>
#  define MOE_CPU_PAUSE() std::this_thread::yield()
#endif

// ---------------------------------------------------------------------------
// Attesa inattiva senza mutex.
//
// Invariante 6: nessun callback deve attendere un mutex che il thread in attesa
// del graph possa trattenere. Il modo piu' semplice di renderlo vero per
// costruzione e' non usare mutex da nessuna parte in questo percorso.
// Su Windows si usa WaitOnAddress/WakeByAddressAll, che non passa da un lock
// dell'utente e non ha risvegli persi: il confronto con il valore atteso lo fa
// il sistema al momento dell'attesa. Se l'API non e' risolvibile si degrada a
// Sleep(1), che consuma comunque quasi zero CPU: il pool resta inattivo fuori
// dal decode (D09) anche nel percorso di ripiego.
// ---------------------------------------------------------------------------
// Namespace con nome, non anonimo: `moe_cpu_executor::impl` ha un membro di
// tipo `barrier` e un tipo di namespace anonimo dentro una classe a linkage
// esterno e' una fonte inutile di diagnostiche.
namespace moe_cpu_detail {

#if defined(_WIN32)
using pfn_WaitOnAddress   = BOOL (WINAPI *)(volatile VOID *, PVOID, SIZE_T, DWORD);
using pfn_WakeByAddressAll= VOID (WINAPI *)(PVOID);

struct sync_api {
    pfn_WaitOnAddress    wait = nullptr;
    pfn_WakeByAddressAll wake = nullptr;
    sync_api() {
        HMODULE m = LoadLibraryA("api-ms-win-core-synch-l1-2-0.dll");
        if (!m) m = LoadLibraryA("kernelbase.dll");
        if (!m) return;
        wait = (pfn_WaitOnAddress)   GetProcAddress(m, "WaitOnAddress");
        wake = (pfn_WakeByAddressAll)GetProcAddress(m, "WakeByAddressAll");
        if (!wait || !wake) { wait = nullptr; wake = nullptr; }
    }
};
const sync_api & sync() { static sync_api s; return s; }
#endif

inline void block_until_changed(volatile uint64_t * address, uint64_t expected, uint32_t timeout_ms) {
#if defined(_WIN32)
    const sync_api & s = sync();
    if (s.wait) {
        uint64_t compare = expected;
        s.wait(address, &compare, sizeof(uint64_t), timeout_ms ? timeout_ms : INFINITE);
        return;
    }
    Sleep(1);
#else
    (void) address; (void) expected; (void) timeout_ms;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
#endif
}

inline void wake_waiters(volatile uint64_t * address) {
#if defined(_WIN32)
    const sync_api & s = sync();
    if (s.wake) s.wake((PVOID) address);
#else
    (void) address;
#endif
}

// Le celle vivono in memoria mappata condivisa col dispositivo: si accedono
// come volatile + barriere esplicite, non come std::atomic (che non e'
// costruibile sopra memoria altrui senza lanciare un placement new).
inline uint64_t cell_load_acquire(const volatile uint64_t * p) {
    uint64_t v = *p;
    std::atomic_thread_fence(std::memory_order_acquire);
    return v;
}
inline void cell_store_release(volatile uint64_t * p, uint64_t v) {
    std::atomic_thread_fence(std::memory_order_release);
    *p = v;
}

inline uint64_t now_us() {
#if defined(_WIN32)
    static const uint64_t freq = [] {
        LARGE_INTEGER f; QueryPerformanceFrequency(&f); return (uint64_t) f.QuadPart;
    }();
    LARGE_INTEGER c;
    QueryPerformanceCounter(&c);
    return (uint64_t) ((c.QuadPart * 1000000ull) / freq);
#else
    return (uint64_t) std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
#endif
}

// Barriera a inversione di fase, dal prototipo. Tutti i thread del pool la
// attraversano per ogni job; nessuno esce prima che tutti siano arrivati.
class barrier {
    const unsigned count;
    std::atomic<unsigned> arrived{0};
    std::atomic<unsigned> phase{0};
public:
    explicit barrier(unsigned n) : count(n) {}
    void wait() {
        if (count <= 1) return;
        const unsigned p = phase.load(std::memory_order_relaxed);
        if (arrived.fetch_add(1, std::memory_order_acq_rel) == count - 1) {
            arrived.store(0, std::memory_order_relaxed);
            phase.fetch_add(1, std::memory_order_release);
        } else {
            while (phase.load(std::memory_order_acquire) == p) MOE_CPU_PAUSE();
        }
    }
};

#if defined(_WIN32)
// Un processore logico per core fisico, poi i fratelli SMT. Copiata dal
// prototipo (fused_cpu.hpp:18-31) perche' la misura del 13 settembre e' stata
// ottenuta con questa disposizione.
std::vector<DWORD_PTR> physical_first_masks() {
    DWORD bytes = 0;
    GetLogicalProcessorInformation(nullptr, &bytes);
    std::vector<SYSTEM_LOGICAL_PROCESSOR_INFORMATION> info(bytes / sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION));
    std::vector<DWORD_PTR> first, other;
    if (bytes == 0 || !GetLogicalProcessorInformation(info.data(), &bytes)) return first;
    DWORD_PTR allowed = 0, system = 0;
    GetProcessAffinityMask(GetCurrentProcess(), &allowed, &system);
    for (const auto & i : info) {
        if (i.Relationship != RelationProcessorCore) continue;
        DWORD_PTR mask = i.ProcessorMask & allowed;
        if (!mask) continue;
        DWORD_PTR bit = mask & (~mask + 1);
        first.push_back(bit);
        mask ^= bit;
        while (mask) { bit = mask & (~mask + 1); other.push_back(bit); mask ^= bit; }
    }
    first.insert(first.end(), other.begin(), other.end());
    return first;
}
#endif

constexpr int MOE_CPU_DOWN_TILE = 16;   // righe di `down` per piastrella, come nel prototipo
constexpr int MOE_CPU_RING      = 64;   // finestra degli stati per generazione
constexpr int MOE_CPU_MAX_BLOCK = 256;  // blocco massimo del vec_dot_type ammesso

} // namespace moe_cpu_detail

using namespace moe_cpu_detail;

const char * moe_cpu_state_name(moe_cpu_state s) {
    switch (s) {
        case moe_cpu_state::unknown:   return "sconosciuto";
        case moe_cpu_state::running:   return "in corso";
        case moe_cpu_state::ok:        return "valido";
        case moe_cpu_state::rejected:  return "rifiutato";
        case moe_cpu_state::cancelled: return "annullato";
        case moe_cpu_state::timeout:   return "scaduto";
        case moe_cpu_state::stopped:   return "chiuso";
    }
    return "?";
}

// ---------------------------------------------------------------------------

struct moe_cpu_executor::impl {
    moe_cpu_caps caps;
    std::unique_ptr<moe_cpu_host_memory> memory;
    moe_cpu_host_block block;
    std::vector<moe_cpu_allocation> alloc_table;

    // viste sul blocco mappato (host e device)
    moe_cpu_job   * job_h   = nullptr;  void * job_d   = nullptr;
    moe_cpu_flags * flags_h = nullptr;  void * flags_d = nullptr;
    float         * x_h     = nullptr;  void * x_d     = nullptr;
    float         * y_h     = nullptr;  void * y_d     = nullptr;

    // scratch host-privato, mai visto dal dispositivo
    std::vector<uint8_t> xq;      // attivazione quantizzata, una riga per token
    std::vector<uint8_t> hq;      // stato nascosto quantizzato, uno per route

    const ggml_type_traits_cpu * tg = nullptr;  // gate
    const ggml_type_traits_cpu * tu = nullptr;  // up
    const ggml_type_traits_cpu * td = nullptr;  // down
    ggml_from_float_t quant_x = nullptr;
    ggml_from_float_t quant_h = nullptr;
    size_t xq_row = 0, hq_row = 0, hq_block = 0;
    int    blk_h  = 0;            // blocco del vec_dot_type di `down`

    std::unordered_map<int32_t, moe_cpu_bank> layers;

    // stato del job corrente, scritto solo dal coordinatore
    struct route { int32_t row; int32_t expert; float weight; };
    std::vector<route> flat;
    int32_t cur_rows = 0;
    const moe_cpu_bank * cur_bank = nullptr;

    // sincronizzazione del pool
    std::vector<std::thread> threads;
    std::unique_ptr<barrier> gate;
    alignas(64) std::atomic<uint64_t> work{0};
    alignas(64) std::atomic<uint64_t> stopping{0};
    alignas(64) std::atomic<uint64_t> cancelled{0};
    alignas(64) std::atomic<uint32_t> phase{(uint32_t) moe_cpu_phase::idle};

    alignas(64) std::atomic<uint64_t> n_submitted{0};
    alignas(64) std::atomic<uint64_t> n_completed{0};
    alignas(64) std::atomic<uint64_t> n_failed{0};
    alignas(64) std::atomic<uint64_t> gen_first_failed{UINT64_MAX};
    alignas(64) std::atomic<uint64_t> in_flight{0};

    std::atomic<uint64_t> ring_gen[MOE_CPU_RING];
    std::atomic<uint32_t> ring_state[MOE_CPU_RING];

    ~impl() { shutdown(); }

    void shutdown() {
        if (threads.empty()) {
            if (memory) memory->release();
            return;
        }
        stopping.store(1, std::memory_order_release);
        // sveglia il coordinatore (attende su flags.request) e i worker
        if (flags_h) {
            cell_store_release(&flags_h->request.value, 1);
            wake_waiters(&flags_h->request.value);
        }
        work.fetch_add(1, std::memory_order_release);
        wake_waiters((volatile uint64_t *) &work);
        for (auto & t : threads) if (t.joinable()) t.join();
        threads.clear();
        if (memory) memory->release();
    }

    void record(uint64_t generation, moe_cpu_state s) {
        const size_t i = (size_t) (generation % MOE_CPU_RING);
        ring_state[i].store((uint32_t) s, std::memory_order_relaxed);
        ring_gen[i].store(generation, std::memory_order_release);
        if (s != moe_cpu_state::ok) {
            n_failed.fetch_add(1, std::memory_order_relaxed);
            uint64_t expected = UINT64_MAX;
            gen_first_failed.compare_exchange_strong(expected, generation, std::memory_order_relaxed);
        }
    }

    // ---- aritmetica -------------------------------------------------------

    // Fase 1: gate/up -> SiLU(gate)*up -> quantizzazione a blocchi dello stato
    // nascosto. Ogni piastrella di blk_h righe possiede il proprio blocco.
    void phase_gate_up(int worker, int nth) {
        const int H = caps.n_ff_exp;
        const int K = caps.n_embd;
        const int tiles_per_route = H / blk_h;
        const int n_tiles = (int) flat.size() * tiles_per_route;
        alignas(64) float hidden[MOE_CPU_MAX_BLOCK];
        for (int t = worker; t < n_tiles; t += nth) {
            const int r  = t / tiles_per_route;
            const int b  = t % tiles_per_route;
            const int r0 = b * blk_h;
            const route & rt = flat[(size_t) r];
            const uint8_t * g = cur_bank->gate + (size_t) rt.expert * cur_bank->gate_stride;
            const uint8_t * u = cur_bank->up   + (size_t) rt.expert * cur_bank->up_stride;
            const size_t gate_row = cur_bank->gate_stride / (size_t) H;
            const size_t up_row   = cur_bank->up_stride   / (size_t) H;
            const uint8_t * xqr = xq.data() + (size_t) rt.row * xq_row;
            for (int i = 0; i < blk_h; ++i) {
                float gv = 0.0f, uv = 0.0f;
                tg->vec_dot(K, &gv, 0, g + (size_t) (r0 + i) * gate_row, 0, xqr, 0, 1);
                tu->vec_dot(K, &uv, 0, u + (size_t) (r0 + i) * up_row,   0, xqr, 0, 1);
                hidden[(size_t) i] = (gv / (1.0f + std::exp(-gv))) * uv;
            }
            quant_h(hidden, hq.data() + (size_t) r * hq_row + (size_t) b * hq_block, blk_h);
        }
    }

    // Fase 2: down e somma pesata. Ogni piastrella possiede le proprie righe di
    // uscita e somma le route del suo token senza atomiche.
    void phase_down(int worker, int nth) {
        const int H = caps.n_ff_exp;
        const int K = caps.n_embd;
        const int tiles_per_row = (K + MOE_CPU_DOWN_TILE - 1) / MOE_CPU_DOWN_TILE;
        const int n_tiles = cur_rows * tiles_per_row;
        for (int t = worker; t < n_tiles; t += nth) {
            const int row  = t / tiles_per_row;
            const int tile = t % tiles_per_row;
            const int k0 = tile * MOE_CPU_DOWN_TILE;
            const int k1 = std::min(k0 + MOE_CPU_DOWN_TILE, K);
            float * out = y_h + (size_t) row * (size_t) K;
            for (int k = k0; k < k1; ++k) {
                float sum = 0.0f;
                // ordine di somma: route crescenti del token. Il test di parita'
                // riproduce esattamente questo ordine.
                for (size_t r = 0; r < flat.size(); ++r) {
                    if (flat[r].row != row) continue;
                    const size_t down_row = cur_bank->down_stride / (size_t) K;
                    float value = 0.0f;
                    td->vec_dot(H, &value, 0,
                        cur_bank->down + (size_t) flat[r].expert * cur_bank->down_stride + (size_t) k * down_row, 0,
                        hq.data() + r * hq_row, 0, 1);
                    sum += flat[r].weight * value;
                }
                out[k] = sum;
            }
        }
    }

    void compute(int worker) {
        const int nth = (int) threads.size();
        phase_gate_up(worker, nth);
        gate->wait();
        phase_down(worker, nth);
        gate->wait();
    }

    // ---- thread -----------------------------------------------------------

    void pin(int index) {
#if defined(_WIN32)
        static const std::vector<DWORD_PTR> masks = physical_first_masks();
        if (index < (int) masks.size()) SetThreadAffinityMask(GetCurrentThread(), masks[(size_t) index]);
#else
        (void) index;
#endif
    }

    void worker_loop(int index) {
        pin(index);
        uint64_t observed = 0;
        for (;;) {
            uint64_t next;
            const uint64_t deadline = now_us() + caps.spin_us;
            while ((next = work.load(std::memory_order_acquire)) == observed) {
                if (stopping.load(std::memory_order_relaxed)) return;
                const bool spin = phase.load(std::memory_order_relaxed) == (uint32_t) moe_cpu_phase::decode
                                  && now_us() < deadline;
                if (spin) { MOE_CPU_PAUSE(); continue; }
                block_until_changed((volatile uint64_t *) &work, observed, 20);
            }
            if (stopping.load(std::memory_order_relaxed)) return;
            observed = next;
            compute(index);
        }
    }

    // Il coordinatore e' il proprietario seriale del pool: nessun altro thread
    // tocca `flat`, `xq`, `hq` o i buffer mappati mentre un job e' in corso.
    void coordinator_loop() {
        pin(0);
        for (;;) {
            // attesa della richiesta: giro breve solo in fase di decode, poi
            // blocco vero. Fuori dal decode e in prefill si dorme subito (D09).
            {
                const uint64_t deadline = now_us() + caps.spin_us;
                for (;;) {
                    if (stopping.load(std::memory_order_relaxed)) { drain_stop(); return; }
                    if (cell_load_acquire(&flags_h->request.value) == 1) break;
                    const bool spin = phase.load(std::memory_order_relaxed) == (uint32_t) moe_cpu_phase::decode
                                      && now_us() < deadline;
                    if (spin) { MOE_CPU_PAUSE(); continue; }
                    block_until_changed(&flags_h->request.value, 0, 20);
                }
            }
            cell_store_release(&flags_h->request.value, 0);
            if (stopping.load(std::memory_order_relaxed)) { drain_stop(); return; }

            const uint64_t generation = n_submitted.fetch_add(1, std::memory_order_relaxed) + 1;
            record(generation, moe_cpu_state::running);

            moe_cpu_state result = validate_and_prepare();
            if (result == moe_cpu_state::ok && cancelled.load(std::memory_order_acquire)) {
                result = moe_cpu_state::cancelled;
            }
            if (result == moe_cpu_state::ok) {
                if (!flat.empty()) {
                    work.fetch_add(1, std::memory_order_release);
                    wake_waiters((volatile uint64_t *) &work);
                    compute(0);
                } else {
                    // nessuna route CPU per questo passo: il contributo corretto
                    // e' zero. Non e' una maschera d'errore, e' il valore giusto.
                    std::memset(y_h, 0, (size_t) cur_rows * (size_t) caps.n_embd * sizeof(float));
                }
            }

            publish(generation, result);
        }
    }

    void drain_stop() {
        // Sblocca un eventuale `wait` gia' accodato, senza sovrascrivere lo
        // stato dell'ultimo job valido nell'anello.
        publish_flags(moe_cpu_state::stopped);
    }

    void publish_flags(moe_cpu_state result) {
        cell_store_release(&flags_h->result.value, (uint64_t) result);
        cell_store_release(&flags_h->poison.value, result == moe_cpu_state::ok ? 0u : 1u);
        cell_store_release(&flags_h->done.value, 1);
        wake_waiters(&flags_h->done.value);
    }

    void publish(uint64_t generation, moe_cpu_state result) {
        record(generation, result);
        n_completed.fetch_add(1, std::memory_order_release);
        publish_flags(result);
    }

    // Controllo integrale dell'header. Un job non valido NON scrive `y`:
    // nessuno zero viene spacciato per risultato (invariante 7).
    moe_cpu_state validate_and_prepare() {
        flat.clear();
        cur_bank = nullptr;
        cur_rows = 0;

        const moe_cpu_job & j = *job_h;
        if (j.magic != MOE_CPU_JOB_MAGIC || j.abi != MOE_CPU_ABI_VERSION)          return moe_cpu_state::rejected;
        if (j.n_embd != caps.n_embd || j.n_ff_exp != caps.n_ff_exp)                return moe_cpu_state::rejected;
        if (j.n_rows < 1 || j.n_rows > caps.max_rows)                              return moe_cpu_state::rejected;

        const auto it = layers.find(j.layer);
        if (it == layers.end())                                                    return moe_cpu_state::rejected;
        cur_bank = &it->second;
        cur_rows = j.n_rows;

        int32_t cursor = 0;
        for (int32_t row = 0; row < j.n_rows; ++row) {
            const int32_t n = j.n_routes[row];
            if (n < 0 || n > caps.max_per_row)                                     return moe_cpu_state::rejected;
            for (int32_t e = 0; e < n; ++e, ++cursor) {
                if (cursor >= MOE_CPU_MAX_ROUTES)                                  return moe_cpu_state::rejected;
                const int32_t expert = j.expert[cursor];
                const float   weight = j.weight[cursor];
                if (expert < 0 || expert >= cur_bank->n_experts)                   return moe_cpu_state::rejected;
                if (!std::isfinite(weight))                                        return moe_cpu_state::rejected;
                flat.push_back({row, expert, weight});
            }
        }
        if ((size_t) cursor != flat.size())                                        return moe_cpu_state::rejected;

        // Quantizzazione dell'attivazione: una volta per token, condivisa da
        // tutte le route CPU di quel token.
        for (int32_t row = 0; row < j.n_rows; ++row) {
            const float * x = x_h + (size_t) row * (size_t) caps.n_embd;
            for (int32_t k = 0; k < caps.n_embd; ++k) {
                if (!std::isfinite(x[k]))                                          return moe_cpu_state::rejected;
            }
            quant_x(x, xq.data() + (size_t) row * xq_row, caps.n_embd);
        }
        return moe_cpu_state::ok;
    }
};

// ---------------------------------------------------------------------------

moe_cpu_executor::moe_cpu_executor(std::unique_ptr<impl> p) : p_(std::move(p)) {}
moe_cpu_executor::~moe_cpu_executor() = default;

std::unique_ptr<moe_cpu_executor> moe_cpu_executor::create(const moe_cpu_caps & caps,
                                                           std::unique_ptr<moe_cpu_host_memory> memory,
                                                           std::string * err) {
    auto fail = [&](const char * m) -> std::unique_ptr<moe_cpu_executor> {
        if (err) *err = m;
        return nullptr;
    };
    if (!memory)                                             return fail("fornitore di memoria assente");
    if (caps.n_embd <= 0 || caps.n_ff_exp <= 0)              return fail("forme non valide");
    if (caps.max_rows < 1 || caps.max_rows > MOE_CPU_MAX_ROWS)       return fail("max_rows fuori dai limiti");
    if (caps.max_per_row < 1 || caps.max_per_row > MOE_CPU_MAX_PER_ROW) return fail("max_per_row fuori dai limiti");
    if (caps.n_threads < 1 || caps.n_threads > 32)           return fail("n_threads fuori dai limiti");

    ggml_cpu_init();

    auto p = std::unique_ptr<impl>(new impl());
    p->caps   = caps;
    p->memory = std::move(memory);
    for (int i = 0; i < MOE_CPU_RING; ++i) {
        p->ring_gen[i].store(UINT64_MAX, std::memory_order_relaxed);
        p->ring_state[i].store((uint32_t) moe_cpu_state::unknown, std::memory_order_relaxed);
    }

    p->tg = ggml_get_type_traits_cpu(caps.type_gate);
    p->tu = ggml_get_type_traits_cpu(caps.type_up);
    p->td = ggml_get_type_traits_cpu(caps.type_down);
    if (!p->tg || !p->tu || !p->td || !p->tg->vec_dot || !p->tu->vec_dot || !p->td->vec_dot)
        return fail("tipi senza tratti CPU");
    if (p->tg->vec_dot_type != p->tu->vec_dot_type)
        return fail("gate e up devono condividere il tipo di attivazione");

    p->quant_x = ggml_get_type_traits_cpu(p->tg->vec_dot_type)->from_float;
    p->quant_h = ggml_get_type_traits_cpu(p->td->vec_dot_type)->from_float;
    if (!p->quant_x || !p->quant_h)                          return fail("attivazione non quantizzabile");

    p->blk_h = (int) ggml_blck_size(p->td->vec_dot_type);
    if (p->blk_h <= 0 || p->blk_h > MOE_CPU_MAX_BLOCK)       return fail("blocco dell'attivazione di down fuori dai limiti");
    if (caps.n_ff_exp % p->blk_h)                            return fail("n_ff_exp non multiplo del blocco di down");
    if (caps.n_embd % (int) ggml_blck_size(p->tg->vec_dot_type))
        return fail("n_embd non multiplo del blocco dell'attivazione");

    p->xq_row   = ggml_row_size(p->tg->vec_dot_type, caps.n_embd);
    p->hq_row   = ggml_row_size(p->td->vec_dot_type, caps.n_ff_exp);
    p->hq_block = ggml_row_size(p->td->vec_dot_type, p->blk_h);

    // Un solo blocco mappato, suddiviso una volta: job | flags | x | y.
    const size_t sz_job   = (sizeof(moe_cpu_job)   + 63) & ~size_t(63);
    const size_t sz_flags = (sizeof(moe_cpu_flags) + 63) & ~size_t(63);
    const size_t sz_vec   = ((size_t) caps.max_rows * (size_t) caps.n_embd * sizeof(float) + 63) & ~size_t(63);
    const size_t total    = sz_job + sz_flags + 2 * sz_vec;

    std::string merr;
    if (!p->memory->allocate(total, 64, &p->block, &merr)) {
        if (err) *err = "allocazione mappata fallita: " + merr;
        return nullptr;
    }
    char * h = (char *) p->block.host;
    char * d = (char *) p->block.dev;
    size_t off = 0;
    p->job_h   = (moe_cpu_job *)   (h + off); p->job_d   = d + off; off += sz_job;
    p->flags_h = (moe_cpu_flags *) (h + off); p->flags_d = d + off; off += sz_flags;
    p->x_h     = (float *)         (h + off); p->x_d     = d + off; off += sz_vec;
    p->y_h     = (float *)         (h + off); p->y_d     = d + off; off += sz_vec;
    std::memset(h, 0, total);

    p->xq.assign((size_t) caps.max_rows * p->xq_row, 0);
    p->hq.assign((size_t) caps.max_rows * (size_t) caps.max_per_row * p->hq_row, 0);
    p->flat.reserve((size_t) caps.max_rows * (size_t) caps.max_per_row);

    p->alloc_table = {
        {"job (descrittore)",        sz_job,                 true},
        {"flags (4 linee)",          sz_flags,               true},
        {"x (attivazione)",          sz_vec,                 true},
        {"y (contributo CPU)",       sz_vec,                 true},
        {"xq (attivazione quant.)",  p->xq.size(),           false},
        {"hq (nascosto quant.)",     p->hq.size(),           false},
    };

#if defined(_WIN32)
    {
        const auto masks = physical_first_masks();
        if (!masks.empty() && caps.n_threads > (int) masks.size()) {
            // il distruttore di `impl` rilascia la memoria: nessun rilascio qui
            return fail("piu' thread che processori consentiti");
        }
    }
#endif

    p->gate.reset(new barrier((unsigned) caps.n_threads));
    p->threads.reserve((size_t) caps.n_threads);
    impl * raw = p.get();
    p->threads.emplace_back([raw] { raw->coordinator_loop(); });
    for (int i = 1; i < caps.n_threads; ++i) {
        p->threads.emplace_back([raw, i] { raw->worker_loop(i); });
    }

    return std::unique_ptr<moe_cpu_executor>(new moe_cpu_executor(std::move(p)));
}

bool moe_cpu_executor::register_layer(int32_t layer, const moe_cpu_bank & bank, std::string * err) {
    auto fail = [&](const char * m) { if (err) *err = m; return false; };
    if (!bank.gate || !bank.up || !bank.down)        return fail("banco incompleto");
    if (bank.n_experts <= 0)                         return fail("numero di esperti non valido");
    const size_t gate_row = ggml_row_size(p_->caps.type_gate, p_->caps.n_embd);
    const size_t up_row   = ggml_row_size(p_->caps.type_up,   p_->caps.n_embd);
    const size_t down_row = ggml_row_size(p_->caps.type_down, p_->caps.n_ff_exp);
    if (bank.gate_stride != gate_row * (size_t) p_->caps.n_ff_exp) return fail("passo di gate incoerente con la forma");
    if (bank.up_stride   != up_row   * (size_t) p_->caps.n_ff_exp) return fail("passo di up incoerente con la forma");
    if (bank.down_stride != down_row * (size_t) p_->caps.n_embd)   return fail("passo di down incoerente con la forma");
    if (p_->in_flight.load(std::memory_order_acquire))             return fail("registrazione con un job in volo");

    const auto it = p_->layers.find(layer);
    if (it != p_->layers.end()) {
        const moe_cpu_bank & old = it->second;
        if (old.gate != bank.gate || old.up != bank.up || old.down != bank.down ||
            old.n_experts != bank.n_experts) {
            return fail("puntatori dello strato cambiati: memoria riallocata sotto un graph");
        }
        return true;
    }
    p_->layers.emplace(layer, bank);
    return true;
}

void moe_cpu_executor::clear_layers() { p_->layers.clear(); }

// ---- nodi host -------------------------------------------------------------
//
// Nessuna API CUDA, nessun mutex, ritorno in tempo finito. Sono le uniche due
// funzioni che il backend CUDA passa a cudaLaunchHostFunc.

void moe_cpu_executor::submit_hook(void * user) {
    impl * p = ((moe_cpu_executor *) user)->p_.get();
    // Rientranza: due submit senza un wait in mezzo sono un errore di
    // programma, non una coda. Si marca e si lascia che il wait fallisca.
    if (p->in_flight.exchange(1, std::memory_order_acq_rel) != 0) {
        cell_store_release(&p->flags_h->result.value, (uint64_t) moe_cpu_state::rejected);
        cell_store_release(&p->flags_h->poison.value, 1);
        cell_store_release(&p->flags_h->done.value, 1);
        wake_waiters(&p->flags_h->done.value);
        return;
    }
    cell_store_release(&p->flags_h->done.value, 0);
    cell_store_release(&p->flags_h->poison.value, 0);
    cell_store_release(&p->flags_h->result.value, (uint64_t) moe_cpu_state::running);
    cell_store_release(&p->flags_h->request.value, 1);
    wake_waiters(&p->flags_h->request.value);
}

void moe_cpu_executor::wait_hook(void * user) {
    impl * p = ((moe_cpu_executor *) user)->p_.get();
    const uint64_t start      = now_us();
    const uint64_t spin_until = start + p->caps.spin_us;
    const uint64_t deadline   = start + p->caps.wait_timeout_us;
    for (;;) {
        if (cell_load_acquire(&p->flags_h->done.value) == 1) break;
        const uint64_t t = now_us();
        if (t >= deadline) {
            // Scadenza: non si abortisce (il prototipo chiamava std::abort).
            // Si marca l'esito, si avvelena `y` e si ritorna: la richiesta e'
            // invalida e il chiamante deve fallire il decode.
            p->cancelled.store(1, std::memory_order_release);
            p->record(p->n_submitted.load(std::memory_order_relaxed), moe_cpu_state::timeout);
            p->n_failed.fetch_add(0, std::memory_order_relaxed); // record ha gia' contato
            cell_store_release(&p->flags_h->result.value, (uint64_t) moe_cpu_state::timeout);
            cell_store_release(&p->flags_h->poison.value, 1);
            break;
        }
        // Giro breve, poi blocco vero: anche il thread di callback del driver
        // deve poter dormire invece di occupare un core.
        if (t < spin_until) { MOE_CPU_PAUSE(); continue; }
        block_until_changed(&p->flags_h->done.value, 0, 1);
    }
    cell_store_release(&p->flags_h->done.value, 0);
    p->in_flight.store(0, std::memory_order_release);
}

// ---- osservazione ----------------------------------------------------------

uint64_t moe_cpu_executor::submitted() const { return p_->n_submitted.load(std::memory_order_acquire); }
uint64_t moe_cpu_executor::completed() const { return p_->n_completed.load(std::memory_order_acquire); }
uint64_t moe_cpu_executor::failures()  const { return p_->n_failed.load(std::memory_order_acquire); }
uint64_t moe_cpu_executor::first_failed_generation() const { return p_->gen_first_failed.load(std::memory_order_acquire); }
bool     moe_cpu_executor::contaminated() const { return first_failed_generation() != UINT64_MAX; }

moe_cpu_state moe_cpu_executor::state(uint64_t generation) const {
    const size_t i = (size_t) (generation % MOE_CPU_RING);
    if (p_->ring_gen[i].load(std::memory_order_acquire) != generation) return moe_cpu_state::unknown;
    return (moe_cpu_state) p_->ring_state[i].load(std::memory_order_relaxed);
}

void moe_cpu_executor::cancel() {
    p_->cancelled.store(1, std::memory_order_release);
    // Sblocca un eventuale `wait` in corso senza toccare il job: il risultato
    // corrente e' dichiarato non valido.
    cell_store_release(&p_->flags_h->result.value, (uint64_t) moe_cpu_state::cancelled);
    cell_store_release(&p_->flags_h->poison.value, 1);
    cell_store_release(&p_->flags_h->done.value, 1);
    wake_waiters(&p_->flags_h->done.value);
}

void moe_cpu_executor::rearm() {
    p_->cancelled.store(0, std::memory_order_release);
}

bool moe_cpu_executor::quiesce(uint64_t timeout_us, std::string * err) {
    const uint64_t deadline = now_us() + timeout_us;
    for (;;) {
        if (p_->in_flight.load(std::memory_order_acquire) == 0 &&
            p_->n_completed.load(std::memory_order_acquire) >= p_->n_submitted.load(std::memory_order_acquire)) {
            return true;
        }
        if (now_us() >= deadline) {
            if (err) *err = "quiesce scaduta: un job risulta ancora in volo";
            return false;
        }
        std::this_thread::yield();
    }
}

void moe_cpu_executor::set_phase(moe_cpu_phase ph) {
    p_->phase.store((uint32_t) ph, std::memory_order_relaxed);
    if (ph != moe_cpu_phase::decode) {
        // risveglia i thread perche' rileggano la fase e vadano a dormire
        wake_waiters((volatile uint64_t *) &p_->work);
        wake_waiters(&p_->flags_h->request.value);
    }
}

const moe_cpu_job   * moe_cpu_executor::job_host()   const { return p_->job_h; }
moe_cpu_job         * moe_cpu_executor::job_host_mut()     { return p_->job_h; }
const moe_cpu_flags * moe_cpu_executor::flags_host() const { return p_->flags_h; }
const float         * moe_cpu_executor::y_host()     const { return p_->y_h; }
float               * moe_cpu_executor::x_host()           { return p_->x_h; }
void * moe_cpu_executor::job_dev()   const { return p_->job_d; }
void * moe_cpu_executor::flags_dev() const { return p_->flags_d; }
void * moe_cpu_executor::x_dev()     const { return p_->x_d; }
void * moe_cpu_executor::y_dev()     const { return p_->y_d; }

const moe_cpu_caps & moe_cpu_executor::caps() const { return p_->caps; }
const std::vector<moe_cpu_allocation> & moe_cpu_executor::allocations() const { return p_->alloc_table; }
size_t moe_cpu_executor::allocated_bytes() const {
    size_t n = 0;
    for (const auto & a : p_->alloc_table) n += a.bytes;
    return n;
}

bool moe_cpu_executor::reference_expert(int32_t layer, int32_t expert, const float * x, float * out,
                                        std::string * err) const {
    auto fail = [&](const char * m) { if (err) *err = m; return false; };
    const auto it = p_->layers.find(layer);
    if (it == p_->layers.end())                       return fail("strato non registrato");
    const moe_cpu_bank & b = it->second;
    if (expert < 0 || expert >= b.n_experts)          return fail("esperto fuori dai limiti");
    if (!x || !out)                                   return fail("buffer assente");

    const int K = p_->caps.n_embd;
    const int H = p_->caps.n_ff_exp;
    std::vector<uint8_t> xqr(p_->xq_row), hqr(p_->hq_row);
    p_->quant_x(x, xqr.data(), K);

    const size_t gate_row = b.gate_stride / (size_t) H;
    const size_t up_row   = b.up_stride   / (size_t) H;
    const size_t down_row = b.down_stride / (size_t) K;
    std::vector<float> hidden((size_t) p_->blk_h);
    for (int r0 = 0; r0 < H; r0 += p_->blk_h) {
        for (int i = 0; i < p_->blk_h; ++i) {
            float gv = 0.0f, uv = 0.0f;
            p_->tg->vec_dot(K, &gv, 0, b.gate + (size_t) expert * b.gate_stride + (size_t) (r0 + i) * gate_row, 0, xqr.data(), 0, 1);
            p_->tu->vec_dot(K, &uv, 0, b.up   + (size_t) expert * b.up_stride   + (size_t) (r0 + i) * up_row,   0, xqr.data(), 0, 1);
            hidden[(size_t) i] = (gv / (1.0f + std::exp(-gv))) * uv;
        }
        p_->quant_h(hidden.data(), hqr.data() + (size_t) (r0 / p_->blk_h) * p_->hq_block, p_->blk_h);
    }
    for (int k = 0; k < K; ++k) {
        float value = 0.0f;
        p_->td->vec_dot(H, &value, 0,
            b.down + (size_t) expert * b.down_stride + (size_t) k * down_row, 0, hqr.data(), 0, 1);
        out[k] = value;
    }
    return true;
}
