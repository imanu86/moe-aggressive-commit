// Micro-banco: quanto costa il riempimento host del pool QSA di set_input_qsa
// (llama-memory-hybrid-idx.cpp:425-460, ramo veloce) a n_kv = 131584, r = 4.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <vector>

int main(int argc, char ** argv) {
    const int64_t n_kv     = argc > 1 ? atoll(argv[1]) : 131584;
    const int64_t r        = argc > 2 ? atoll(argv[2]) : 4;
    const int64_t n_blocks = n_kv / r;
    const int     ripet    = argc > 3 ? atoi(argv[3]) : 200;

    std::vector<int32_t> cell_blk(n_kv);
    std::vector<int32_t> blk_cells(r * n_blocks);
    std::vector<int32_t> blk_pos(4 * n_blocks);
    std::vector<float>   bias(n_kv);

    int64_t pos0 = 131247;
    volatile int64_t sink = 0;
    double best = 1e30, somma = 0;
    for (int it = 0; it < ripet; ++it) {
        const int64_t used     = pos0 + it + 1;
        const int64_t complete = used / r;
        const int32_t dead     = (int32_t) std::min(complete, n_blocks - 1);
        auto t0 = std::chrono::high_resolution_clock::now();

        std::fill(cell_blk.begin(), cell_blk.end(), dead);
        std::fill(blk_cells.begin(), blk_cells.end(), 0);
        std::fill(blk_pos.begin(), blk_pos.end(), 0);
        for (int64_t b = 0; b < complete; ++b) {
            for (int64_t j = 0; j < r; ++j) {
                cell_blk[b*r + j]  = (int32_t) b;
                blk_cells[b*r + j] = (int32_t) (b*r + j);
            }
            for (int64_t sec = 0; sec < 4; ++sec) {
                blk_pos[sec*n_blocks + b] = (int32_t) (b*r);
            }
        }
        const int64_t query_used     = used;
        const int64_t query_complete = query_used / r;
        const int64_t query_tail     = query_complete * r;
        std::fill(bias.begin(),                bias.begin() + query_tail, 0.0f);
        std::fill(bias.begin() + query_tail,   bias.begin() + query_used, 1e9f);
        std::fill(bias.begin() + query_used,   bias.end(),                -INFINITY);

        auto t1 = std::chrono::high_resolution_clock::now();
        double us = std::chrono::duration<double, std::micro>(t1 - t0).count();
        if (it >= 20) { best = std::min(best, us); somma += us; }
        sink += cell_blk[n_kv/2] + blk_pos[7] + (int64_t) bias[3];
    }
    printf("n_kv=%lld r=%lld  minimo %.1f us  media %.1f us  (sink %lld)\n",
           (long long) n_kv, (long long) r, best, somma / (ripet - 20), (long long) sink);
    return 0;
}
