"""Seleziona il top-k a registri col limite attivo del prefill, non lo stride KV.

La nuova API non e' per grafi catturati. Decode e API originale sono preservati;
il chiamante prefill possiede gia' il massimo n_bid+1 del batch monotono.
"""


def integrate_topk(source):
    header = 'include/strata/kernels/qsa_select.hpp'
    cuda = 'src/kernels/cuda/qsa_select.cu'
    prefill = 'src/prefill/prefill.cpp'
    h = (source/header).read_text(encoding='utf-8')
    c = (source/cuda).read_text(encoding='utf-8')
    p = (source/prefill).read_text(encoding='utf-8')
    anchor = '/// The original kernel (keys read from memory on every radix pass), for tests: the same ids.'
    assert h.count(anchor) == 1
    declaration = '''/// Prefill only, not for a captured graph: active_blocks >= every query's n_bid+1.
/// max_blocks remains the score-row stride; the register limit applies to active_blocks.
void qsa_block_topk_active(const float* scores, const int32_t* steps, int64_t nq, int64_t max_blocks, int64_t cap,
                           const QsaShapes& s, int32_t* ids, void* stream, int64_t active_blocks);
'''
    h = h.replace(anchor, declaration+anchor)
    anchor = '}  // namespace strata::kernels'
    assert c.count(anchor) == 1
    function = '''void qsa_block_topk_active(const float* scores, const int32_t* steps, int64_t nq, int64_t max_blocks,
                           int64_t cap, const QsaShapes& s, int32_t* ids, void* stream, int64_t active_blocks) {
    if (nq <= 0) return;
    // The caller supplies the batch's true upper bound. A captured decode graph
    // must keep the original API: its input context can grow after capture.
    if (active_blocks <= 0 || active_blocks > max_blocks || active_blocks > (int64_t)TK_T * TK_PER ||
        std::getenv("STRATA_TOPK_CAPACITY_GUARD") || std::getenv("STRATA_TOPK_OLD")) {
        qsa_block_topk(scores, steps, nq, max_blocks, cap, s, ids, stream);
        return;
    }
    if (s.idx_block != R || cap < qsa_selection_width(kTopkMaxCells, s)) {
        std::fprintf(stderr, "qsa_block_topk_active: unsupported geometry or cap\\n");
        std::exit(1);
    }
    block_topk_reg_kernel<<<(unsigned)nq, TK_T, 0, (cudaStream_t)stream>>>(
        scores, steps, max_blocks, cap, ids);
    const cudaError_t e = cudaGetLastError();
    if (e != cudaSuccess) { std::fprintf(stderr, "qsa_block_topk_active: %s\\n", cudaGetErrorString(e)); std::exit(1); }
}

'''
    c = c.replace(anchor, function+anchor)
    anchor = ('                        strata::kernels::qsa_block_topk(m.sel_scores, steps0, nb, m.max_blocks, m.cap, s,\n'
              '                                                        m.sel_ids + t0 * m.cap, m.cs);')
    assert p.count(anchor) == 1
    p = p.replace(anchor,
        '                        strata::kernels::qsa_block_topk_active(m.sel_scores, steps0, nb, m.max_blocks, m.cap, s,\n'
        '                                                               m.sel_ids + t0 * m.cap, m.cs, active);')
    return {header: h, cuda: c, prefill: p}
