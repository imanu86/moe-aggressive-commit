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
// e, aggiunte dopo la revisione del 14 settembre (difetti B1/B2, buchi D1-D5):
//   T12 cancel() mentre compute() e' GENUINAMENTE in corso: il completamento
//       tardivo non tocca i flag ne' l'uscita del job successivo
//   T13 scadenza del wait con completamento tardivo: job irrecuperabile,
//       submit rifiutati, riconoscimento del coordinatore, recupero
//   T14 un annullamento di routine non contamina; un errore vero si;
//       acknowledge_contamination() sblocca
//   T15 distruzione con un job in volo, senza stallo
//   T16 percorsi di fallimento di create()
//   T17 register_layer: idempotenza e rifiuto di un puntatore cambiato
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
#include <thread>
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

void sleep_ms(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

// Attende una condizione con scadenza, senza mai bloccare in eterno il banco.
template <typename F>
bool wait_until(F f, int timeout_ms) {
    const auto t0 = clock_t_::now();
    for (;;) {
        if (f()) return true;
        if (std::chrono::duration<double, std::milli>(clock_t_::now() - t0).count() > timeout_ms) return false;
        std::this_thread::yield();
    }
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
    caps.ack_timeout_us  = 2000000;

    moe_cpu_bank bank;
    bank.gate = b.gate.data(); bank.gate_stride = b.gate_stride;
    bank.up   = b.up.data();   bank.up_stride   = b.up_stride;
    bank.down = b.down.data(); bank.down_stride = b.down_stride;
    bank.n_experts = s.E;

    std::string err;
    auto ex = moe_cpu_executor::create(caps, moe_cpu_host_memory_plain(), &err);
    if (!ex) { std::printf("creazione fallita: %s\n", err.c_str()); return 2; }
    ex->set_phase(moe_cpu_phase::decode);
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
        check(!ex->contaminated(), "T4", "nessuna contaminazione dopo soli esiti validi");
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
    // Dieci header non validi: i sei della prima stesura piu' i quattro
    // segnalati come mancanti dalla revisione (n_routes negativo, peso
    // infinito, attivazione non finita, indice di strato negativo).
    {
        struct bad { const char * what; int kind; };
        const bad cases_bad[] = {
            {"magic errato",              0},
            {"strato non registrato",     1},
            {"esperto fuori dai limiti",  2},
            {"peso non finito (NaN)",     3},
            {"n_rows fuori dai limiti",   4},
            {"troppe route per token",    5},
            {"n_routes negativo",         6},
            {"peso infinito",             7},
            {"attivazione non finita",    8},
            {"indice di strato negativo", 9},
        };
        bool all_rejected = true, all_poisoned = true, all_untouched = true;
        const float x0_saved = ex->x_host()[0];
        for (const auto & bc : cases_bad) {
            // sentinella: `y` non deve essere toccato da un job rifiutato
            for (int k = 0; k < s.K; ++k) const_cast<float *>(ex->y_host())[k] = -12345.0f;
            ex->x_host()[0] = x0_saved;
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
                case 6: j->n_routes[0] = -1;            break;
                case 7: j->weight[0] = HUGE_VALF;       break;
                case 8: ex->x_host()[0] = HUGE_VALF;    break;
                case 9: j->layer     = -1;              break;
            }
            const moe_cpu_state st = run_once(*ex);
            all_rejected  = all_rejected  && st == moe_cpu_state::rejected;
            all_poisoned  = all_poisoned  && ex->flags_host()->poison.value == 1;
            for (int k = 0; k < s.K; ++k) all_untouched = all_untouched && ex->y_host()[k] == -12345.0f;
            if (st != moe_cpu_state::rejected) std::printf("       non rifiutato: %s\n", bc.what);
        }
        ex->x_host()[0] = x0_saved;
        check(all_rejected,  "T6", "header non validi: rifiutati (10 casi)");
        check(all_poisoned,  "T6", "header non validi: risultato avvelenato");
        check(all_untouched, "T6", "header non validi: `y` non toccato, nessuno zero");
        check(ex->contaminated(), "T6", "un header non valido contamina, e la marca e' appiccicosa");
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
        const uint64_t g1 = ex->submitted() + 1;      // job legittimo
        moe_cpu_executor::submit_hook(ex.get());
        const uint64_t g2 = ex->submitted() + 1;      // generazione del submit rientrante
        moe_cpu_executor::submit_hook(ex.get());      // secondo submit senza wait
        const auto t0 = clock_t_::now();
        moe_cpu_executor::wait_hook(ex.get());
        const double us = std::chrono::duration<double, std::micro>(clock_t_::now() - t0).count();
        check(us < 200000.0, "T8", "submit concorrente: rifiutato, non accodato, senza stallo");
        check(ex->state(g2) == moe_cpu_state::rejected, "T8", "il submit rientrante e' registrato come rifiutato");
        check(ex->state(g1) == moe_cpu_state::ok, "T8", "il job legittimo non viene disturbato dal rientrante");
        // Un secondo `wait` (quello abbinato al submit rifiutato) non deve
        // trovare niente da attendere ne' rilasciare: `in_flight` e' gia' zero.
        const auto t1 = clock_t_::now();
        moe_cpu_executor::wait_hook(ex.get());
        const double us2 = std::chrono::duration<double, std::micro>(clock_t_::now() - t1).count();
        check(us2 < 200000.0, "T8", "il wait spaiato ritorna subito, senza attendere il vuoto");
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

    // ------------------------------------------------------------------ T17
    // register_layer: idempotente con gli stessi puntatori, errore se cambiano.
    {
        check(ex->register_layer(7, bank, &err), "T17", "register_layer e' idempotente con gli stessi puntatori");
        moe_cpu_bank moved = bank;
        moved.gate = bank.gate + 1;           // puntatore diverso, mai dereferenziato
        const bool refused = !ex->register_layer(7, moved, &err);
        check(refused, "T17", "un puntatore sorgente cambiato e' rifiutato, non aggiornato");
        moe_cpu_bank broken = bank;
        broken.down_stride = bank.down_stride + 64;
        check(!ex->register_layer(9, broken, &err), "T17", "un passo incoerente con la forma e' rifiutato");
        check(!ex->register_layer(-3, bank, &err),  "T17", "un indice di strato negativo e' rifiutato");
    }

    // ------------------------------------------------------------------ T12
    // Annullamento mentre compute() e' GENUINAMENTE in corso.
    //
    // Il ritardo iniettato tiene il coordinatore dentro la finestra di calcolo
    // (i worker sono gia' entrati in compute() e sono fermi alla prima
    // barriera). Un secondo thread annulla a meta'. Si verifica che:
    //  - il `wait` ritorna senza stallo;
    //  - l'esito annunciato e' `cancelled`, avvelenato: mai `ok`;
    //  - il completamento TARDIVO del coordinatore non promuove l'esito;
    //  - il job successivo e' corretto e il suo `y` combacia col riferimento:
    //    nessun flag e nessuna uscita del job successivo e' stata toccata.
    {
        check(ex->acknowledge_contamination(&err), "T12", "acknowledge_contamination riparte da pulito");
        check(!ex->contaminated(), "T12", "dopo il riconoscimento la marca e' spenta");

        const uint64_t failures_before = ex->failures();
        ex->set_test_delay_us(120000);   // 120 ms di finestra di calcolo osservabile
        for (auto & v : x) v = dist(rng);
        std::memcpy(ex->x_host(), x.data(), (size_t) s.K * sizeof(float));
        routes[0] = {{(int32_t) (2 % s.E), 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);

        const uint64_t gen_slow = ex->submitted() + 1;
        std::thread canceller([&] { sleep_ms(30); ex->cancel(); });
        const auto t0 = clock_t_::now();
        moe_cpu_executor::submit_hook(ex.get());
        moe_cpu_executor::wait_hook(ex.get());
        const double wait_ms = std::chrono::duration<double, std::milli>(clock_t_::now() - t0).count();
        const uint64_t result_seen = ex->flags_host()->result.value;
        const uint64_t poison_seen = ex->flags_host()->poison.value;
        canceller.join();                 // il riconoscimento del coordinatore avviene qui dentro
        ex->set_test_delay_us(0);

        check(wait_ms < 2000.0, "T12", "il wait ritorna senza stallo durante un calcolo lungo");
        check(result_seen != (uint64_t) moe_cpu_state::ok && poison_seen == 1,
              "T12", "l'esito del job annullato non e' mai `ok` ed e' avvelenato");
        check(ex->state(gen_slow) == moe_cpu_state::cancelled, "T12", "il job annullato e' registrato come annullato");
        check(!ex->unrecoverable(), "T12", "il coordinatore ha riconosciuto l'annullamento entro la scadenza");
        check(!ex->contaminated(),  "T12", "un annullamento di routine non contamina");
        check(ex->failures() == failures_before + 1, "T12", "l'annullamento resta contato fra i non-ok");
        check(ex->quiesce(2000000, &err), "T12", "nessun job in volo dopo il riconoscimento");

        // Job successivo: se il completamento tardivo avesse toccato flag o
        // uscita, questo confronto fallirebbe.
        ex->rearm();
        for (auto & v : x) v = dist(rng);
        std::memcpy(ex->x_host(), x.data(), (size_t) s.K * sizeof(float));
        const int32_t e_next = (int32_t) (3 % s.E);
        routes[0] = {{e_next, 1.0f}};
        fill_job(ex->job_host_mut(), 7, 1, s.K, s.H, routes);
        const moe_cpu_state st_next = run_once(*ex);
        const int32_t ids_next[2] = {e_next, e_next};
        ref.run(x.data(), ids_next, ref_out.data());
        check(st_next == moe_cpu_state::ok, "T12", "il job successivo e' valido");
        check(ex->flags_host()->poison.value == 0, "T12", "il job successivo non eredita il veleno");
        check(nrmse(ex->y_host(), ref_out.data(), s.K) <= 1e-6,
              "T12", "il completamento tardivo non ha toccato l'uscita del job successivo");
    }

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

    // ------------------------------------------------------------------ T13
    // Scadenza del `wait` con completamento tardivo.
    //
    // Esecutore dedicato con una scadenza del `wait` di 3 ms e un calcolo da
    // 300 ms: la scadenza scatta mentre il coordinatore sta calcolando.
    // Il job diventa IRRECUPERABILE: `in_flight` resta alto, ogni submit e'
    // rifiutato, e il completamento tardivo del coordinatore NON riscrive i
    // flag — e' precisamente il difetto B1.
    {
        moe_cpu_caps c2 = caps;
        c2.wait_timeout_us = 3000;
        auto ex2 = moe_cpu_executor::create(c2, moe_cpu_host_memory_plain(), &err);
        if (!ex2) { std::printf("creazione ex2 fallita: %s\n", err.c_str()); return 2; }
        ex2->set_phase(moe_cpu_phase::decode);
        if (!ex2->register_layer(7, bank, &err)) { std::printf("registrazione ex2 fallita: %s\n", err.c_str()); return 2; }
        ex2->set_test_delay_us(300000);

        for (auto & v : x) v = dist(rng);
        std::memcpy(ex2->x_host(), x.data(), (size_t) s.K * sizeof(float));
        routes[0] = {{0, 1.0f}};
        fill_job(ex2->job_host_mut(), 7, 1, s.K, s.H, routes);

        const uint64_t gen_to = ex2->submitted() + 1;
        const auto t0 = clock_t_::now();
        moe_cpu_executor::submit_hook(ex2.get());
        moe_cpu_executor::wait_hook(ex2.get());
        const double ms = std::chrono::duration<double, std::milli>(clock_t_::now() - t0).count();

        check(ms < 200.0, "T13", "il wait scade e ritorna, non aspetta la fine del calcolo");
        check(ex2->state(gen_to) == moe_cpu_state::timeout, "T13", "la scadenza produce lo stato `timeout`");
        check(ex2->contaminated(), "T13", "la scadenza contamina");
        check(ex2->unrecoverable(), "T13", "il job scaduto resta marcato irrecuperabile");
        check(!ex2->acknowledge_contamination(&err), "T13", "non si riconosce una contaminazione con un job irrecuperabile");

        // Un submit durante la finestra irrecuperabile: rifiutato, e le celle
        // condivise NON vanno toccate.
        const uint64_t gen_ref = ex2->submitted() + 1;
        moe_cpu_executor::submit_hook(ex2.get());
        moe_cpu_executor::wait_hook(ex2.get());
        check(ex2->state(gen_ref) == moe_cpu_state::rejected, "T13", "durante l'irrecuperabile ogni submit e' rifiutato");
        check(ex2->flags_host()->result.value == (uint64_t) moe_cpu_state::timeout &&
              ex2->flags_host()->poison.value == 1,
              "T13", "il submit rifiutato non sovrascrive le celle del job abbandonato");

        // Riconoscimento del coordinatore alla fine del calcolo tardivo.
        const bool reaped = wait_until([&] { return !ex2->unrecoverable(); }, 5000);
        check(reaped, "T13", "il coordinatore riconosce il job e riapre il servizio");
        check(ex2->flags_host()->result.value == (uint64_t) moe_cpu_state::timeout &&
              ex2->flags_host()->poison.value == 1,
              "T13", "il completamento tardivo NON riscrive i flag del job abbandonato");
        check(ex2->quiesce(2000000, &err), "T13", "dopo il riconoscimento il pool e' quieto");

        // Recupero completo, come da contratto P1 §5.
        check(ex2->acknowledge_contamination(&err), "T13", "acknowledge_contamination dopo il riconoscimento");
        check(!ex2->contaminated(), "T13", "la marca di contaminazione e' spenta");
        ex2->set_test_delay_us(0);
        ex2->rearm();
        for (auto & v : x) v = dist(rng);
        std::memcpy(ex2->x_host(), x.data(), (size_t) s.K * sizeof(float));
        const int32_t e_ok = (int32_t) (1 % s.E);
        routes[0] = {{e_ok, 1.0f}};
        fill_job(ex2->job_host_mut(), 7, 1, s.K, s.H, routes);
        const moe_cpu_state st = run_once(*ex2);
        const int32_t ids_ok[2] = {e_ok, e_ok};
        ref.run(x.data(), ids_ok, ref_out.data());
        check(st == moe_cpu_state::ok && nrmse(ex2->y_host(), ref_out.data(), s.K) <= 1e-6,
              "T13", "dopo il recupero il pool torna a produrre risultati corretti");
    }

    // ------------------------------------------------------------------ T14
    // Separazione fra annullamento di routine ed errore vero (difetto B2).
    {
        auto ex3 = moe_cpu_executor::create(caps, moe_cpu_host_memory_plain(), &err);
        if (!ex3) { std::printf("creazione ex3 fallita: %s\n", err.c_str()); return 2; }
        ex3->set_phase(moe_cpu_phase::decode);
        if (!ex3->register_layer(7, bank, &err)) { std::printf("registrazione ex3 fallita: %s\n", err.c_str()); return 2; }
        std::memcpy(ex3->x_host(), x.data(), (size_t) s.K * sizeof(float));

        check(!ex3->contaminated(), "T14", "un esecutore appena creato non e' contaminato");

        // 1. annullamento di routine, ripetuto: non deve contaminare mai.
        for (int r = 0; r < 3; ++r) {
            ex3->cancel();
            routes[0] = {{0, 1.0f}};
            fill_job(ex3->job_host_mut(), 7, 1, s.K, s.H, routes);
            const moe_cpu_state st = run_once(*ex3);
            if (st != moe_cpu_state::cancelled) { check(false, "T14", "l'annullamento produce lo stato `cancelled`"); break; }
            ex3->rearm();
        }
        check(!ex3->contaminated(), "T14", "tre annullamenti di routine non contaminano");
        check(ex3->failures() >= 3, "T14", "gli annullamenti restano contati fra i non-ok");

        // 2. il pool serve ancora: la contaminazione non e' stata innescata.
        routes[0] = {{0, 1.0f}};
        fill_job(ex3->job_host_mut(), 7, 1, s.K, s.H, routes);
        check(run_once(*ex3) == moe_cpu_state::ok, "T14", "dopo gli annullamenti il pool serve ancora");

        // 3. errore vero: contamina, con la generazione giusta.
        routes[0] = {{0, 1.0f}};
        fill_job(ex3->job_host_mut(), 7, 1, s.K, s.H, routes);
        ex3->job_host_mut()->magic = 0xdeadbeef;
        const uint64_t gen_bad = ex3->submitted() + 1;
        moe_cpu_executor::submit_hook(ex3.get());
        moe_cpu_executor::wait_hook(ex3.get());
        check(ex3->state(gen_bad) == moe_cpu_state::rejected, "T14", "un header non valido e' rifiutato");
        check(ex3->contaminated(), "T14", "un errore vero contamina");
        check(ex3->first_failed_generation() == gen_bad, "T14", "la prima generazione contaminante e' quella giusta");

        // 4. riconoscimento: solo dopo aver buttato l'incarnazione.
        const uint64_t failures_kept = ex3->failures();
        check(ex3->acknowledge_contamination(&err), "T14", "acknowledge_contamination riesce a pool quieto");
        check(!ex3->contaminated(), "T14", "dopo il riconoscimento la marca e' spenta");
        check(ex3->first_failed_generation() == UINT64_MAX, "T14", "la prima generazione contaminante e' azzerata");
        check(ex3->failures() == failures_kept, "T14", "il riconoscimento non riscrive il contatore storico");
        routes[0] = {{0, 1.0f}};
        fill_job(ex3->job_host_mut(), 7, 1, s.K, s.H, routes);
        check(run_once(*ex3) == moe_cpu_state::ok, "T14", "dopo il riconoscimento il pool torna a servire");
    }

    // ------------------------------------------------------------------ T15
    // Distruzione con un job genuinamente in volo, senza `wait` abbinato:
    // e' il caso che la revisione segnala come R13 (join senza limite di
    // tempo). I worker escono solo quando il coordinatore si ritira, quindi
    // nessuna barriera puo' restare spaiata.
    {
        auto ex4 = moe_cpu_executor::create(caps, moe_cpu_host_memory_plain(), &err);
        if (!ex4) { std::printf("creazione ex4 fallita: %s\n", err.c_str()); return 2; }
        ex4->set_phase(moe_cpu_phase::decode);
        if (!ex4->register_layer(7, bank, &err)) { std::printf("registrazione ex4 fallita: %s\n", err.c_str()); return 2; }
        std::memcpy(ex4->x_host(), x.data(), (size_t) s.K * sizeof(float));
        ex4->set_test_delay_us(150000);
        routes[0] = {{0, 1.0f}};
        fill_job(ex4->job_host_mut(), 7, 1, s.K, s.H, routes);
        moe_cpu_executor::submit_hook(ex4.get());   // nessun wait: il job resta in volo
        sleep_ms(20);                               // il coordinatore e' dentro la finestra di calcolo
        const auto t0 = clock_t_::now();
        ex4.reset();
        const double ms = std::chrono::duration<double, std::milli>(clock_t_::now() - t0).count();
        std::printf("       distruzione con job in volo in %.1f ms\n", ms);
        check(ms < 2000.0, "T15", "distruzione con un job in volo: nessuno stallo");
    }

    // ------------------------------------------------------------------ T16
    // Percorsi di fallimento di create(). Nessuno di questi deve costruire un
    // esecutore, e nessuno deve dereferenziare fuori dai limiti: in
    // particolare `GGML_TYPE_COUNT`, che e' il valore di difetto di
    // `moe_cpu_caps`, indicizzerebbe la tabella dei tratti CPU fuori dai
    // limiti (ggml-cpu.c:418-420 non controlla nulla).
    {
        struct bad_caps { const char * what; moe_cpu_caps c; };
        std::vector<bad_caps> bad;
        {
            moe_cpu_caps c;                       // tutti i tipi = GGML_TYPE_COUNT
            c.n_embd = s.K; c.n_ff_exp = s.H; c.n_threads = threads;
            bad.push_back({"tipi non impostati (GGML_TYPE_COUNT)", c});
        }
        {
            moe_cpu_caps c = caps; c.type_up = GGML_TYPE_Q8_0;   // vec_dot_type diverso da IQ2_S
            bad.push_back({"gate e up con tipo di attivazione diverso", c});
        }
        {
            moe_cpu_caps c = caps; c.n_ff_exp = s.H + 1;         // non multiplo del blocco di down (32)
            bad.push_back({"n_ff_exp non multiplo del blocco di down", c});
        }
        {
            moe_cpu_caps c = caps; c.max_rows = MOE_CPU_MAX_ROWS + 1;
            bad.push_back({"max_rows fuori dai limiti", c});
        }
        {
            moe_cpu_caps c = caps; c.max_per_row = 0;
            bad.push_back({"max_per_row nullo", c});
        }
        {
            moe_cpu_caps c = caps; c.n_embd = 0;
            bad.push_back({"forma nulla", c});
        }
        {
            moe_cpu_caps c = caps; c.wait_timeout_us = 0;
            bad.push_back({"scadenza del wait nulla", c});
        }
        bool all_failed = true, all_explained = true;
        for (const auto & bc : bad) {
            std::string m;
            auto bad_ex = moe_cpu_executor::create(bc.c, moe_cpu_host_memory_plain(), &m);
            if (bad_ex) { all_failed = false; std::printf("       creato per sbaglio: %s\n", bc.what); }
            if (m.empty()) { all_explained = false; std::printf("       fallito senza messaggio: %s\n", bc.what); }
        }
        check(all_failed,    "T16", "ogni configurazione non valida fallisce la creazione");
        check(all_explained, "T16", "ogni fallimento di create() porta un messaggio");
        std::string m;
        check(moe_cpu_executor::create(caps, nullptr, &m) == nullptr && !m.empty(),
              "T16", "senza fornitore di memoria la creazione fallisce");
    }

    std::printf("\n%s: %d controlli falliti\n", g_failed ? "ESITO NEGATIVO" : "ESITO POSITIVO", g_failed);
    return g_failed ? 3 : 0;
}
