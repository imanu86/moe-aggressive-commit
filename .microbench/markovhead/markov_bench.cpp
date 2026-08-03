// markov_bench: replica ISOLATA del sottografo di build_dspark_markov_head
// (D:\llama-dspark\src\models\dflash.cpp:233) su sched CUDA+CPU, per trovare
// dove stanno i 538 ms/chiamata misurati (W1-W2, 3/8/2026).
//
// Varianti (argv[1]):
//   full      replica fedele: concat accumulativo + conf head + catena argmax
//   noconf    senza la testa di confidenza
//   nochain   indici da input invece che da argmax (spezza la serialita')
//   treecat   concat ad albero invece che accumulativo
//   prealloc  niente concat: cpy delle colonne su viste di un tensore unico
//   nohead    grafo vuoto che tocca solo base (pavimento)
//
// Regimi: REUSE (alloc una volta, compute N) e REBUILD (build+alloc+compute N,
// come fa il server: il grafo del draft non viene mai riusato).

#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-cuda.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>

static double now_ms() {
    using namespace std::chrono;
    return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}

// dimensioni del caso reale
static const int64_t R        = 256;     // rank della testa di Markov
static const int64_t N_VOCAB  = 129280;
static const int64_t N_EMBD   = 4096;
static const int64_t N_BLOCKS = 1;       // n_seqs nel decode del blocco
static const int64_t N_DRAFTS = 5;       // block_drafts
static const int64_t N_TOK    = N_BLOCKS * N_DRAFTS;

struct bench {
    ggml_backend_t cuda = nullptr;
    ggml_backend_t cpu  = nullptr;
    ggml_backend_sched_t sched = nullptr;

    ggml_context * ctx_w = nullptr;   // pesi + "compute inputs" pre-piazzati
    ggml_backend_buffer_t buf_cuda = nullptr;
    ggml_context * ctx_tok = nullptr; // tokens su CPU
    ggml_backend_buffer_t buf_cpu = nullptr;

    ggml_tensor * w1 = nullptr;      // f16  [R, N_VOCAB]
    ggml_tensor * w2 = nullptr;      // q2_K [R, N_VOCAB]
    ggml_tensor * conf_w = nullptr;  // bf16 [N_EMBD+R, 1]
    ggml_tensor * conf_b = nullptr;  // f32  [1]
    ggml_tensor * base = nullptr;    // f32  [N_VOCAB, N_TOK]  (t_logits, su CUDA come nel server)
    ggml_tensor * embd = nullptr;    // f32  [N_EMBD, N_TOK]   (t_embd, su CUDA)
    ggml_tensor * tokens = nullptr;  // i32  [N_TOK]           (su CPU: arriva dall'host)

    // grafo corrente
    ggml_context * ctx0 = nullptr;
    ggml_cgraph  * gf   = nullptr;
    ggml_tensor  * t_logits = nullptr;
    std::vector<uint8_t> gbuf;
};

static void die(const char * msg) { fprintf(stderr, "FATAL: %s\n", msg); exit(1); }

static void fill_f32(std::vector<float> & v, std::mt19937 & rng, float scale) {
    std::uniform_real_distribution<float> d(-scale, scale);
    for (auto & x : v) x = d(rng);
}

static void init(bench & b) {
    b.cuda = ggml_backend_cuda_init(0);
    if (!b.cuda) die("no CUDA backend");
    b.cpu = ggml_backend_cpu_init();
    if (!b.cpu) die("no CPU backend");
    ggml_backend_cpu_set_n_threads(b.cpu, 8);

    // pesi e tensori residenti su CUDA (come nel server: w1/w2 f16+q2K sul device,
    // base/embd nel compute buffer CUDA)
    {
        ggml_init_params ip = { ggml_tensor_overhead()*16, nullptr, true };
        b.ctx_w = ggml_init(ip);
        b.w1     = ggml_new_tensor_2d(b.ctx_w, GGML_TYPE_F16,  R, N_VOCAB);
        b.w2     = ggml_new_tensor_2d(b.ctx_w, GGML_TYPE_Q2_K, R, N_VOCAB);
        b.conf_w = ggml_new_tensor_2d(b.ctx_w, GGML_TYPE_BF16, N_EMBD + R, 1);
        b.conf_b = ggml_new_tensor_1d(b.ctx_w, GGML_TYPE_F32,  1);
        b.base   = ggml_new_tensor_2d(b.ctx_w, GGML_TYPE_F32,  N_VOCAB, N_TOK);
        b.embd   = ggml_new_tensor_2d(b.ctx_w, GGML_TYPE_F32,  N_EMBD, N_TOK);
        ggml_set_name(b.w1, "markov_w1"); ggml_set_name(b.w2, "markov_w2");
        ggml_set_name(b.base, "base_logits"); ggml_set_name(b.embd, "t_embd");
        b.buf_cuda = ggml_backend_alloc_ctx_tensors(b.ctx_w, b.cuda);
        if (!b.buf_cuda) die("alloc cuda tensors");
    }
    // tokens su CPU
    {
        ggml_init_params ip = { ggml_tensor_overhead()*4, nullptr, true };
        b.ctx_tok = ggml_init(ip);
        b.tokens = ggml_new_tensor_1d(b.ctx_tok, GGML_TYPE_I32, N_TOK);
        ggml_set_name(b.tokens, "tokens");
        b.buf_cpu = ggml_backend_alloc_ctx_tensors(b.ctx_tok, b.cpu);
        if (!b.buf_cpu) die("alloc cpu tensors");
    }

    std::mt19937 rng(42);
    { // w1 f16
        std::vector<float> f(R*N_VOCAB); fill_f32(f, rng, 0.05f);
        std::vector<ggml_fp16_t> h(f.size());
        for (size_t i = 0; i < f.size(); ++i) h[i] = ggml_fp32_to_fp16(f[i]);
        ggml_backend_tensor_set(b.w1, h.data(), 0, h.size()*sizeof(h[0]));
    }
    { // w2 quantizzato q2_K da f32
        std::vector<float> f(R*N_VOCAB); fill_f32(f, rng, 0.05f);
        std::vector<uint8_t> q(ggml_nbytes(b.w2));
        size_t n = ggml_quantize_chunk(GGML_TYPE_Q2_K, f.data(), q.data(), 0, N_VOCAB, R, nullptr);
        if (n != q.size()) die("q2_K quantize size mismatch");
        ggml_backend_tensor_set(b.w2, q.data(), 0, q.size());
    }
    { // conf bf16 + bias
        std::vector<float> f(N_EMBD + R); fill_f32(f, rng, 0.05f);
        std::vector<ggml_bf16_t> h(f.size());
        for (size_t i = 0; i < f.size(); ++i) h[i] = ggml_fp32_to_bf16(f[i]);
        ggml_backend_tensor_set(b.conf_w, h.data(), 0, h.size()*sizeof(h[0]));
        float bias = -0.1f;
        ggml_backend_tensor_set(b.conf_b, &bias, 0, sizeof(bias));
    }
    { // base, embd
        std::vector<float> f(N_VOCAB*N_TOK); fill_f32(f, rng, 4.0f);
        ggml_backend_tensor_set(b.base, f.data(), 0, f.size()*sizeof(float));
        std::vector<float> e(N_EMBD*N_TOK); fill_f32(e, rng, 1.0f);
        ggml_backend_tensor_set(b.embd, e.data(), 0, e.size()*sizeof(float));
    }
    { // tokens
        int32_t t[N_TOK];
        for (int i = 0; i < N_TOK; ++i) t[i] = 1000 + 37*i;
        ggml_backend_tensor_set(b.tokens, t, 0, sizeof(t));
    }

    ggml_backend_t backends[2] = { b.cuda, b.cpu };
    b.sched = ggml_backend_sched_new(backends, nullptr, 2, 4096, false, true);
    if (!b.sched) die("sched");
}

// replica di build_dspark_markov_head con le varianti
static void build(bench & b, const std::string & mode) {
    if (b.ctx0) { ggml_free(b.ctx0); b.ctx0 = nullptr; }
    size_t sz = ggml_tensor_overhead()*4096 + ggml_graph_overhead_custom(4096, false);
    b.gbuf.resize(sz);
    ggml_init_params ip = { sz, b.gbuf.data(), true };
    b.ctx0 = ggml_init(ip);
    ggml_context * ctx0 = b.ctx0;
    b.gf = ggml_new_graph_custom(ctx0, 4096, false);

    ggml_tensor * base = b.base;
    ggml_tensor * tokens = b.tokens;

    if (mode == "nohead") {
        ggml_tensor * out = ggml_scale(ctx0, base, 1.0f); // tocca base e basta
        ggml_set_output(out);
        b.t_logits = out;
        ggml_build_forward_expand(b.gf, out);
        return;
    }

    const int64_t n_vocab = N_VOCAB;
    const int64_t n_blocks = N_BLOCKS;
    const int64_t block_drafts = N_DRAFTS;

    const size_t token_stride = (size_t) block_drafts * tokens->nb[0];
    const size_t base_stride  = (size_t) block_drafts * base->nb[1];

    ggml_tensor * prev = ggml_view_2d(ctx0, tokens, 1, n_blocks, token_stride, 0);
    prev = ggml_cont_1d(ctx0, prev, n_blocks);

    const bool use_conf  = (mode != "noconf");
    const bool use_chain = (mode != "nochain");

    ggml_tensor * conf_inp = use_conf ? b.embd : nullptr;

    ggml_tensor * cat = nullptr;
    ggml_tensor * cat_conf = nullptr;
    std::vector<ggml_tensor *> cols;

    ggml_tensor * prealloc = nullptr;
    if (mode == "prealloc") {
        prealloc = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, n_vocab, block_drafts*n_blocks);
        ggml_set_output(prealloc); // vive per tutto il grafo
    }

    for (int64_t i = 0; i < block_drafts; ++i) {
        ggml_tensor * w1_prev = ggml_get_rows(ctx0, b.w1, prev);   // [R, n_blocks]
        ggml_tensor * bias    = ggml_mul_mat(ctx0, b.w2, w1_prev); // [n_vocab, n_blocks]

        ggml_tensor * base_i = ggml_view_2d(ctx0, base, n_vocab, n_blocks, base_stride, i*base->nb[1]);
        ggml_tensor * col    = ggml_add(ctx0, base_i, bias);

        if (mode == "prealloc") {
            // scrive la colonna nella posizione i del tensore unico
            ggml_tensor * dst = ggml_view_2d(ctx0, prealloc, n_vocab, n_blocks,
                                             (size_t) block_drafts * prealloc->nb[1], i*prealloc->nb[1]);
            ggml_build_forward_expand(b.gf, ggml_cpy(ctx0, col, dst));
        } else if (mode == "treecat") {
            cols.push_back(col);
        } else {
            cat = cat ? ggml_concat(ctx0, cat, col, 1) : col;
        }

        if (use_conf) {
            ggml_tensor * conf_inp_i = ggml_view_2d(ctx0, conf_inp, conf_inp->ne[0], n_blocks,
                                                    (size_t) block_drafts * conf_inp->nb[1], i*conf_inp->nb[1]);
            ggml_tensor * feat = ggml_concat(ctx0, ggml_cont(ctx0, conf_inp_i), w1_prev, 0);
            ggml_tensor * conf = ggml_mul_mat(ctx0, b.conf_w, feat);
            conf = ggml_add(ctx0, conf, b.conf_b);
            conf = ggml_sigmoid(ctx0, conf);
            cat_conf = cat_conf ? ggml_concat(ctx0, cat_conf, conf, 1) : conf;
        }

        if (i + 1 < block_drafts) {
            if (use_chain) {
                prev = ggml_argmax(ctx0, col);
            } else {
                ggml_tensor * pv = ggml_view_2d(ctx0, tokens, 1, n_blocks, token_stride, (i+1)*tokens->nb[0]);
                prev = ggml_cont_1d(ctx0, pv, n_blocks);
            }
        }
    }

    if (mode == "treecat") {
        // concat bilanciato
        while (cols.size() > 1) {
            std::vector<ggml_tensor *> next;
            for (size_t k = 0; k + 1 < cols.size(); k += 2) {
                next.push_back(ggml_concat(ctx0, cols[k], cols[k+1], 1));
            }
            if (cols.size() % 2) next.push_back(cols.back());
            cols = next;
        }
        cat = cols[0];
    }

    ggml_tensor * out;
    if (mode == "prealloc") {
        out = prealloc;
        // block-major <- position-major
        out = ggml_reshape_3d(ctx0, out, n_vocab, n_blocks, block_drafts);
        out = ggml_cont(ctx0, ggml_permute(ctx0, out, 0, 2, 1, 3));
        out = ggml_reshape_2d(ctx0, out, n_vocab, N_TOK);
    } else {
        out = ggml_reshape_3d(ctx0, cat, n_vocab, n_blocks, block_drafts);
        out = ggml_cont(ctx0, ggml_permute(ctx0, out, 0, 2, 1, 3));
        out = ggml_reshape_2d(ctx0, out, n_vocab, N_TOK);
    }

    if (cat_conf) {
        ggml_tensor * conf = ggml_reshape_3d(ctx0, cat_conf, 1, n_blocks, block_drafts);
        conf = ggml_cont(ctx0, ggml_permute(ctx0, conf, 0, 2, 1, 3));
        conf = ggml_reshape_2d(ctx0, conf, 1, N_TOK);
        conf = ggml_repeat(ctx0, conf, b.embd);
        ggml_set_output(conf);
        ggml_build_forward_expand(b.gf, conf);
    }

    ggml_set_output(out);
    b.t_logits = out;
    ggml_build_forward_expand(b.gf, out);
}

static double run_once(bench & b) {
    double t0 = now_ms();
    if (ggml_backend_sched_graph_compute(b.sched, b.gf) != GGML_STATUS_SUCCESS) die("compute");
    ggml_backend_sched_synchronize(b.sched);
    return now_ms() - t0;
}

int main(int argc, char ** argv) {
    std::string mode = argc > 1 ? argv[1] : "full";
    int iters = argc > 2 ? atoi(argv[2]) : 20;

    bench b;
    init(b);

    // ---- REUSE: stesso grafo, compute ripetuto ----
    build(b, mode);
    ggml_backend_sched_reset(b.sched);
    if (!ggml_backend_sched_alloc_graph(b.sched, b.gf)) die("alloc graph");
    int n_splits = ggml_backend_sched_get_n_splits(b.sched);
    int n_nodes  = ggml_graph_n_nodes(b.gf);

    run_once(b); // riscaldamento
    std::vector<double> reuse;
    for (int i = 0; i < iters; ++i) reuse.push_back(run_once(b));

    // argmax dell'ultima colonna per il confronto di correttezza fra varianti
    std::vector<float> lastcol(N_VOCAB);
    ggml_backend_tensor_get(b.t_logits, lastcol.data(),
                            (size_t)(N_TOK-1)*b.t_logits->nb[1], N_VOCAB*sizeof(float));
    int amax = (int)(std::max_element(lastcol.begin(), lastcol.end()) - lastcol.begin());

    // ---- REBUILD: build + reset + alloc + compute, come il server ----
    std::vector<double> rebuild;
    for (int i = 0; i < iters; ++i) {
        double t0 = now_ms();
        build(b, mode);
        ggml_backend_sched_reset(b.sched);
        if (!ggml_backend_sched_alloc_graph(b.sched, b.gf)) die("alloc graph 2");
        if (ggml_backend_sched_graph_compute(b.sched, b.gf) != GGML_STATUS_SUCCESS) die("compute 2");
        ggml_backend_sched_synchronize(b.sched);
        rebuild.push_back(now_ms() - t0);
    }

    auto med = [](std::vector<double> v) {
        std::sort(v.begin(), v.end());
        return v[v.size()/2];
    };

    printf("MODE=%-9s nodes=%3d splits=%2d | REUSE med=%8.3f ms | REBUILD med=%8.3f ms | argmax_last=%d\n",
           mode.c_str(), n_nodes, n_splits, med(reuse), med(rebuild), amax);

    return 0;
}
