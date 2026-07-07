"""Wiring hidden-probe (0015) su ds4.c gia' patchato con 0003/0004 (versione reap-loop
con prefetch_ids/prefetch_n + branch markov). Inserisce un branch hidden-probe che, se
DS4_SPEX_HIDDEN_FILE e' caricato, predice gli esperti di il+1 da g->cpu_router_norm
(hidden(il) su host) e SOVRASCRIVE prefetch_ids/prefetch_n. K via DS4_SPEX_HIDDEN_K.
"""
import sys
P = sys.argv[1] if len(sys.argv) > 1 else "/root/ds4/ds4.c"
src = open(P).read()

if "ds4_spex_hidden_get" in src:
    print("gia' applicato"); sys.exit(0)

# 1) loader + include, PRIMA di metal_graph_spex_prefetch_next_layer_enabled (0003)
anchor1 = "static bool metal_graph_spex_prefetch_next_layer_enabled("
assert anchor1 in src, "anchor1 non trovato"
loader = r'''#include "ds4_spex_predict.c"
static ds4_spex_model g_spex_hidden_model;
static int g_spex_hidden_state = 0;  /* 0=untried 1=loaded -1=fail */
static const ds4_spex_model *ds4_spex_hidden_get(void) {
    if (g_spex_hidden_state == 0) {
        const char *p = getenv("DS4_SPEX_HIDDEN_FILE");
        if (p && p[0] && ds4_spex_load(p, &g_spex_hidden_model) == 0) {
            g_spex_hidden_state = 1;
            fprintf(stderr, "ds4: SPEX hidden-probe loaded %s (%u layer, %u embd, %u expert)\n",
                    p, g_spex_hidden_model.n_layer, g_spex_hidden_model.n_embd,
                    g_spex_hidden_model.n_expert);
        } else {
            g_spex_hidden_state = -1;
            if (p && p[0]) fprintf(stderr, "ds4: SPEX hidden-probe load FAILED for %s\n", p);
        }
    }
    return g_spex_hidden_state == 1 ? &g_spex_hidden_model : NULL;
}
'''
src = src.replace(anchor1, loader + "\n" + anchor1, 1)

# 2) branch hidden-probe PRIMA di "if (prefetch_n == 0) return true;"
anchor2 = "    if (prefetch_n == 0) return true;"
assert anchor2 in src, "anchor2 (prefetch_n==0) non trovato"
inject = r'''    {
        const ds4_spex_model *spex_hm = ds4_spex_hidden_get();
        if (spex_hm && g->cpu_router_norm) {
            static float spex_hp_scr[DS4_MAX_EXPERT];
            int spex_hp_k = (int)DS4_N_EXPERT_USED;
            const char *spex_hp_kenv = getenv("DS4_SPEX_HIDDEN_K");
            if (spex_hp_kenv) { int kk = atoi(spex_hp_kenv);
                if (kk > 0 && kk <= (int)DS4_MAX_EXPERT) spex_hp_k = kk; }
            int spex_hp_np = ds4_spex_predict_topk(spex_hm, il, g->cpu_router_norm,
                                                   spex_hp_k, prefetch_ids, spex_hp_scr);
            if (spex_hp_np > 0) { prefetch_n = (uint32_t)spex_hp_np; profile_label = "hidden"; }
        }
    }
'''
src = src.replace(anchor2, inject + anchor2, 1)

open(P, "w").write(src)
print("0015 hidden-probe wiring applicato")
