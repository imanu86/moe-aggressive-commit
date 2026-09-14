// P2 — Prova host-only dell'esecutore CPU. Nessuna GPU, nessun server.
//
// Copre i punti di uscita della fase P2 dichiarati dal piano:
//   T1  parita' col riferimento GGML CPU su una route
//   T2  parita' sulla somma pesata di due route
//   T3  la piastrellatura parallela non cambia il risultato (riferimento interno)
//   T4  zero route CPU: il contributo corretto e' zero, e non e' un errore
//   T5  generazioni e stato per job
//   T6  header non validi: rifiuto, veleno, e `y` NON toccato (niente zeri)
//   T7  annullamento e riarmo
//   T8  nessuna chiamata concorrente allo stesso pool
//   T9  cambio di fase e distruzione senza stallo
//   T10 nessun riuso anticipato del buffer fra job consecutivi
//   T11 nessuna allocazione nuova a regime
//
// Uso:
//   test_esecutore.exe [--full] [--threads N] [--experts N] [--weights DIR]
//     --full     forme reali K=2560 H=640 (lento da quantizzare)
//     --weights  usa i .bin del prototipo: gate_22.bin, up_22.bin, down_20.bin
//                (IQ2_S/IQ2_S/IQ4_NL, 128 esperti, K=2560, H=640)
//
// NON compilato in questa fase.

#include "moe_cpu_executor.h"

#include "ggml.h"
#include "ggml-cpu.h"
#include "ggml-backend.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <random>
#include <string>
#include <utility>
#include <vector>

using clock_t_ = std::chrono::steady_clock;

namespace {

int g_failed = 0;

void check(bool ok, const char * test, const char * what) {
    std::printf("%-6s %-52s %s\n", ok ? "[ok]" : "[NO]", what, test);
    if (!ok) ++g_failed;
}

struct shape {
    int K = 512;
    int H = 128;
    int E = 4;
    ggml_type tg = GGML_TYPE_IQ2_S;
    ggml_type tu = GGML_TYPE_IQ2_S;
    ggml_type td = GGML_TYPE_IQ4_NL;
};

struct banks {
    std::vector<uint8_t> gate, up, down;
    size_t gate_stride = 0, up_stride = 0, down_stride = 0;
};

std::vector<uint8_t> quantize_bank(ggml_type type, int64_t n_per_row, int64_t nrows, uint32_t seed) {
    std::mt19937 rng(seed);
    std::normal_distribution<float> dist(0.0f, 1.0f);
    std::vector<float> src((size_t) n_per_row * (size_t) nrows);
    for (auto & v : src) v = dist(rng);
    std::vector<float> imatrix((size_t) n_per_row, 1.0f);   // IQ2_S pretende una matrice di importanza
    std::vector<uint8_t> dst(ggml_row_size(type, n_per_row) * (size_t) nrows);
    ggml_quantize_chunk(type, src.data(), dst.data(), 0, nrows, n_per_row, imatrix.data());
    return dst;
}

bool load_bank(const std::string & path, size_t expected, std::vector<uint8_t> & out) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f || (size_t) f.tellg() != expected) return false;
    out.resize(expected);
    f.seekg(0);
    f.read((char *) out.data(), (std::streamsize) expected);
    return true;
}

banks make_banks(const shape & s, const std::string & weights_dir) {
    banks b;
    b.gate_stride = ggml_row_size(s.tg, s.K) * (size_t) s.H;
    b.up_stride   = ggml_row_size(s.tu, s.K) * (size_t) s.H;
    b.down_stride = ggml_row_size(s.td, s.H) * (size_t) s.K;
    if (!weights_dir.empty()) {
        const bool ok =
            load_bank(weights_dir + "/gate_22.bin", b.gate_stride * (size_t) s.E, b.gate) &&
            load_bank(weights_dir + "/up_22.bin",   b.up_stride   * (size_t) s.E, b.up)   &&
            load_bank(weights_dir + "/down_20.bin", b.down_stride * (size_t) s.E, b.down);
        if (ok) return b;
        std::printf("       pesi del prototipo non leggibili in %s: si quantizza al volo\n", weights_dir.c_str());
        b.gate.clear(); b.up.clear(); b.down.clear();
    }
    b.gate = quantize_bank(s.tg, s.K, (int64_t) s.H * s.E, 11);
    b.up   = quantize_bank(s.tu, s.K, (int64_t) s.H * s.E, 22);
    b.down = quantize_bank(s.td, s.H, (int64_t) s.K * s.E, 33);
    return b;
}

// Riferimento indipendente: la catena mul_mat_id del backend CPU di GGML,
// esattamente come in freetoken_hybrid/cpu_test.cpp.
class ggml_reference {
    ggml_context *        ctx_ = nullptr;
    ggml_backend_t        be_  = nullptr;
    ggml_backend_buffer_t buf_ = nullptr;
    ggml_tensor *x_=nullptr, *ids_=nullptr, *y_=nullptr;
    shape s_;
    int n_ids_;
public:
    ggml_reference(const shape & s, const banks & b, int n_ids, int threads) : s_(s), n_ids_(n_ids) {
        ggml_init_params ip{};
        ip.mem_size = 16ull << 20;
        ip.no_alloc = true;
        ctx_ = ggml_init(ip);
        auto * g = ggml_new_tensor_3d(ctx_, s.tg, s.K, s.H, s.E);
        auto * u = ggml_new_tensor_3d(ctx_, s.tu, s.K, s.H, s.E);
        auto * d = ggml_new_tensor_3d(ctx_, s.td, s.H, s.K, s.E);
        x_   = ggml_new_tensor_3d(ctx_, GGML_TYPE_F32, s.K, 1, 1);
        ids_ = ggml_new_tensor_2d(ctx_, GGML_TYPE_I32, n_ids, 1);
        auto * hidden = ggml_mul(ctx_, ggml_silu(ctx_, ggml_mul_mat_id(ctx_, g, x_, ids_)),
                                       ggml_mul_mat_id(ctx_, u, x_, ids_));
        y_ = ggml_mul_mat_id(ctx_, d, hidden, ids_);
        graph_ = ggml_new_graph_custom(ctx_, 64, false);
        ggml_build_forward_expand(graph_, y_);
        be_ = ggml_backend_cpu_init();
        ggml_backend_cpu_set_n_threads(be_, threads);
        buf_ = ggml_backend_alloc_ctx_tensors(ctx_, be_);
        ggml_backend_tensor_set(g, b.gate.data(), 0, b.gate.size());
        ggml_backend_tensor_set(u, b.up.data(),   0, b.up.size());
        ggml_backend_tensor_set(d, b.down.data(), 0, b.down.size());
    }
    ~ggml_reference() {
        if (buf_) ggml_backend_buffer_free(buf_);
        if (be_)  ggml_backend_free(be_);
        if (ctx_) ggml_free(ctx_);
    }
    bool run(const float * x, const int32_t * ids, float * out) {
        ggml_backend_tensor_set(x_,   x,   0, (size_t) s_.K * sizeof(float));
        ggml_backend_tensor_set(ids_, ids, 0, (size_t) n_ids_ * sizeof(int32_t));
        if (ggml_backend_graph_compute(be_, graph_) != GGML_STATUS_SUCCESS) return false;
        ggml_backend_tensor_get(y_, out, 0, (size_t) n_ids_ * (size_t) s_.K * sizeof(float));
        return true;
    }
private:
    ggml_cgraph * graph_ = nullptr;
};

// Riempie l'header come lo riempira' il kernel di export in P3.
void fill_job(moe_cpu_job * j, int32_t layer, int32_t n_rows, int32_t n_embd, int32_t n_ff,
              const std::vector<std::vector<std::pair<int32_t,float>>> & routes) {
    std::memset(j, 0, sizeof(*j));
    j->magic    = MOE_CPU_JOB_MAGIC;
    j->abi      = MOE_CPU_ABI_VERSION;
    j->layer    = layer;
    j->n_rows   = n_rows;
    j->n_embd   = n_embd;
    j->n_ff_exp = n_ff;
    int cursor = 0;
    for (int32_t r = 0; r < n_rows; ++r) {
        j->n_routes[r] = (int32_t) routes[(size_t) r].size();
        for (const auto & pr : routes[(size_t) r]) {
            j->expert[cursor] = pr.first;
            j->weight[cursor] = pr.second;
            ++cursor;
        }
    }
}

moe_cpu_state run_once(moe_cpu_executor & ex) {
    const uint64_t gen = ex.submitted() + 1;
    moe_cpu_executor::submit_hook(&ex);
    moe_cpu_executor::wait_hook(&ex);
    return ex.state(gen);
}

double nrmse(const float * a, const float * b, int n) {
    double e = 0, d = 0;
    for (int i = 0; i < n; ++i) { const double x = a[i] - b[i]; e += x * x; d += (double) b[i] * b[i]; }
    return std::sqrt(e / (d > 0 ? d : 1e-30));
}

size_t unequal(const float * a, const float * b, int n) {
    size_t k = 0;
    for (int i = 0; i < n; ++i) k += (a[i] != b[i]);
    return k;
}

} // namespace

int main(int argc, char ** argv) {
    shape s;
    int threads = 4;
    std::string weights_dir;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--full")                        { s.K = 2560; s.H = 640; }
        else if (a == "--threads" && i + 1 < argc) threads = std::atoi(argv[++i]);
        else if (a == "--experts" && i + 1 < argc) s.E = std::atoi(argv[++i]);
        else if (a == "--weights" && i + 1 < argc) { weights_dir = argv[++i]; s.K = 2560; s.H = 640; s.E = 128; }
        else { std::printf("argomento non riconosciuto: %s\n", a.c_str()); return 2; }
    }
    ggml_cpu_init();
    std::printf("forme: K=%d H=%d E=%d thread=%d %s\n", s.K, s.H, s.E, threads,
                weights_dir.empty() ? "(pesi sintetici)" : "(pesi del prototipo)");

    const banks b = make_banks(s, weights_dir);

    moe_cpu_caps caps;
    caps.n_embd      = s.K;
    caps.n_ff_exp    = s.H;
    caps.type_gate   = s.tg;
    caps.type_up     = s.tu;
    caps.type_down   = s.td;
    caps.max_rows    = 1;
    caps.max_per_row = 2;
    caps.n_threads   = threads;
    caps.wait_timeout_us = 5000000;

    std::string err;
    auto ex = moe_cpu_executor::create(caps, moe_cpu_host_memory_plain(), &err);
    if (!ex) { std::printf("creazione fallita: %s\n", err.c_str()); return 2; }
    ex->set_phase(moe_cpu_phase::decode);

    moe_cpu_bank bank;
    bank.gate = b.gate.data(); bank.gate_stride = b.gate_stride;
    bank.up   = b.up.data();   bank.up_stride   = b.up_stride;
    bank.down = b.down.data(); bank.down_stride = b.down_stride;
    bank.n_experts = s.E;
    if (!ex->register_layer(7, bank, &err)) { std::printf("registrazione fallita: %s\n", err.c_str()); return 2; }

    // tabella delle allocazioni
    std::printf("\nallocazioni dell'esecutore (una volta sola, per contesto)\n");
    for (const auto & a : ex->allocations()) {
        std::printf("  %-26s %9zu byte  %s\n", a.name, a.bytes, a.mapped ? "mappata" : "host");
    }
    std::printf("  %-26s %9zu byte\n\n", "TOTALE", ex->allocated_bytes());
    const size_t bytes_before = ex->allocated_bytes();

    ggml_reference ref(s, b, 2, threads);

    std::mt19937 rng(1234);
    std::normal_distribution<float> dist(0.0f, 1.0f);
    std::vector<float> x((size_t) s.K), ref_out((size_t) 2 * s.K), internal((size_t) s.K);
    std::vector<std::vector<std::pair<int32_t,float>>> routes(1);

    // ---------------------------------------------------------------- T1/T2/T3
    double worst_single = 0, worst_pair = 0, worst_internal = 0;
    size_t unequal_single = 0, unequal_pair = 0;
    const int cases = 16;
    for (int c = 0; c < cases; ++c) {
        for (auto & v : x) v = dist(rng) * (c % 3 == 0 ? 0.25f : c % 3 == 1 ? 1.0f : 4.0f);
        const int32_t e0 = (int32_t) ((c * 7) % s.E);
        const int32_t e1 = (int32_t) ((c * 7 + 3) % s.E);
        const int32_t ids[2] = {e0, e1};
        if (!ref.run(x.data(), ids, ref_out.data())) { std::printf("riferimento GGML fallito\n"); return 2; }

        std::memcpy(ex->x_host(), x.data(), (size_t) s.K * sizeof(float));

        // T1: una sola route, peso 1 -> y e' l'uscita dell'esperto
        routes[0] = {{e0, 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        if (run_once(*ex) != moe_cpu_state::ok) { std::printf("job singolo non valido\n"); return 2; }
        unequal_single += unequal(ex->y_host(), ref_out.data(), s.K);
        worst_single = std::max(worst_single, nrmse(ex->y_host(), ref_out.data(), s.K));

        // T3: stessa route col riferimento interno seriale
        if (!ex->reference_expert(7, e0, x.data(), internal.data(), &err)) { std::printf("%s\n", err.c_str()); return 2; }
        worst_internal = std::max(worst_internal, nrmse(ex->y_host(), internal.data(), s.K));

        // T2: due route con pesi, stesso ordine di somma
        const float w0 = 0.3f, w1 = 0.7f;
        routes[0] = {{e0, w0}, {e1, w1}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        if (run_once(*ex) != moe_cpu_state::ok) { std::printf("job doppio non valido\n"); return 2; }
        std::vector<float> expected((size_t) s.K);
        for (int k = 0; k < s.K; ++k) expected[(size_t) k] = w0 * ref_out[(size_t) k] + w1 * ref_out[(size_t) s.K + k];
        unequal_pair += unequal(ex->y_host(), expected.data(), s.K);
        worst_pair = std::max(worst_pair, nrmse(ex->y_host(), expected.data(), s.K));
    }
    std::printf("       route singola: nrmse=%.3g diversi=%zu | coppia: nrmse=%.3g diversi=%zu | interno: nrmse=%.3g\n",
                worst_single, unequal_single, worst_pair, unequal_pair, worst_internal);
    check(worst_single   <= 1e-6, "T1", "parita' col riferimento GGML, una route");
    check(worst_pair     <= 1e-6, "T2", "parita' sulla somma pesata di due route");
    check(worst_internal == 0.0,  "T3", "la piastrellatura parallela non cambia il risultato");

    // ------------------------------------------------------------------- T4
    routes[0].clear();
    fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
    {
        const moe_cpu_state st = run_once(*ex);
        bool zero = true;
        for (int k = 0; k < s.K; ++k) zero = zero && ex->y_host()[k] == 0.0f;
        check(st == moe_cpu_state::ok && zero, "T4", "zero route: contributo nullo, esito valido");
        check(ex->flags_host()->poison.value == 0, "T4", "zero route: nessun veleno");
    }

    // ------------------------------------------------------------------- T5
    {
        const uint64_t before = ex->submitted();
        routes[0] = {{0, 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        const uint64_t gen = before + 1;
        moe_cpu_executor::submit_hook(ex.get());
        moe_cpu_executor::wait_hook(ex.get());
        check(ex->submitted() == gen,                       "T5", "la generazione cresce di uno per submit");
        check(ex->state(gen) == moe_cpu_state::ok,          "T5", "stato del job appena concluso");
        check(ex->state(gen + 1000) == moe_cpu_state::unknown, "T5", "generazione fuori finestra: sconosciuta");
        check(ex->completed() == ex->submitted(),           "T5", "nessun job in volo dopo il wait");
    }

    // ------------------------------------------------------------------- T6
    {
        struct bad { const char * what; int kind; };
        const bad cases_bad[] = {
            {"magic errato",              0},
            {"strato non registrato",     1},
            {"esperto fuori dai limiti",  2},
            {"peso non finito",           3},
            {"n_rows fuori dai limiti",   4},
            {"troppe route per token",    5},
        };
        bool all_rejected = true, all_poisoned = true, all_untouched = true;
        for (const auto & bc : cases_bad) {
            // sentinella: `y` non deve essere toccato da un job rifiutato
            for (int k = 0; k < s.K; ++k) const_cast<float *>(ex->y_host())[k] = -12345.0f;
            routes[0] = {{0, 1.0f}};
            fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
            moe_cpu_job * j = ex->job_host_mut();
            switch (bc.kind) {
                case 0: j->magic     = 0xdeadbeef;      break;
                case 1: j->layer     = 999;             break;
                case 2: j->expert[0] = s.E;             break;
                case 3: j->weight[0] = std::nanf("");   break;
                case 4: j->n_rows    = MOE_CPU_MAX_ROWS + 1; break;
                case 5: j->n_routes[0] = MOE_CPU_MAX_PER_ROW + 1; break;
            }
            const moe_cpu_state st = run_once(*ex);
            all_rejected  = all_rejected  && st == moe_cpu_state::rejected;
            all_poisoned  = all_poisoned  && ex->flags_host()->poison.value == 1;
            for (int k = 0; k < s.K; ++k) all_untouched = all_untouched && ex->y_host()[k] == -12345.0f;
            if (st != moe_cpu_state::rejected) std::printf("       non rifiutato: %s\n", bc.what);
        }
        check(all_rejected,  "T6", "header non validi: rifiutati");
        check(all_poisoned,  "T6", "header non validi: risultato avvelenato");
        check(all_untouched, "T6", "header non validi: `y` non toccato, nessuno zero");
        check(ex->contaminated(), "T6", "la contaminazione e' registrata e appiccicosa");
    }

    // ------------------------------------------------------------------- T7
    {
        for (int k = 0; k < s.K; ++k) const_cast<float *>(ex->y_host())[k] = -777.0f;
        routes[0] = {{1 % s.E, 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        ex->cancel();
        const auto t0 = clock_t_::now();
        moe_cpu_executor::submit_hook(ex.get());
        moe_cpu_executor::wait_hook(ex.get());
        const double us = std::chrono::duration<double, std::micro>(clock_t_::now() - t0).count();
        bool untouched = true;
        for (int k = 0; k < s.K; ++k) untouched = untouched && ex->y_host()[k] == -777.0f;
        check(us < 200000.0,  "T7", "l'annullamento sblocca l'attesa senza stallo");
        check(untouched,      "T7", "annullamento: `y` non toccato");
        ex->rearm();
        routes[0] = {{1 % s.E, 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        check(run_once(*ex) == moe_cpu_state::ok, "T7", "dopo il riarmo il pool torna a servire");
    }

    // ------------------------------------------------------------------- T8
    {
        routes[0] = {{0, 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        moe_cpu_executor::submit_hook(ex.get());
        moe_cpu_executor::submit_hook(ex.get());   // secondo submit senza wait
        const auto t0 = clock_t_::now();
        moe_cpu_executor::wait_hook(ex.get());
        const double us = std::chrono::duration<double, std::micro>(clock_t_::now() - t0).count();
        check(us < 200000.0, "T8", "submit concorrente: rifiutato, non accodato, senza stallo");
        check(ex->quiesce(1000000, &err), "T8", "il pool torna quieto dopo la rientranza");
        ex->rearm();
    }

    // ------------------------------------------------------------------ T10
    {
        bool distinct = true;
        std::vector<float> previous((size_t) s.K, 0.0f);
        for (int c = 0; c < 8; ++c) {
            for (auto & v : x) v = dist(rng);
            std::memcpy(ex->x_host(), x.data(), (size_t) s.K * sizeof(float));
            const int32_t e = (int32_t) (c % s.E);
            routes[0] = {{e, 1.0f}};
            fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
            if (run_once(*ex) != moe_cpu_state::ok) { distinct = false; break; }
            const int32_t ids[2] = {e, e};
            ref.run(x.data(), ids, ref_out.data());
            if (nrmse(ex->y_host(), ref_out.data(), s.K) > 1e-6) { distinct = false; break; }
            if (c && std::memcmp(previous.data(), ex->y_host(), (size_t) s.K * sizeof(float)) == 0) { distinct = false; break; }
            std::memcpy(previous.data(), ex->y_host(), (size_t) s.K * sizeof(float));
        }
        check(distinct, "T10", "nessun riuso anticipato del buffer fra job consecutivi");
    }

    // ------------------------------------------------------------------ T11
    check(ex->allocated_bytes() == bytes_before, "T11", "nessuna allocazione nuova a regime");

    // ------------------------------------------------------------------- T9
    {
        ex->set_phase(moe_cpu_phase::prefill);
        ex->set_phase(moe_cpu_phase::idle);
        check(ex->quiesce(1000000, &err), "T9", "quiesce ritorna senza lavoro in volo");
        const auto t0 = clock_t_::now();
        ex.reset();
        const double ms = std::chrono::duration<double, std::milli>(clock_t_::now() - t0).count();
        std::printf("       distruzione in %.1f ms\n", ms);
        check(ms < 2000.0, "T9", "distruzione senza stallo");
    }

    std::printf("\n%s: %d controlli falliti\n", g_failed ? "ESITO NEGATIVO" : "ESITO POSITIVO", g_failed);
    return g_failed ? 3 : 0;
}
