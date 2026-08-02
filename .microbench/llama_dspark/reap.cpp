#include "reap.h"

#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

// ---------------------------------------------------------------- attivazione

static bool env_flag(const char * nome) {
    const char * v = getenv(nome);
    // valore ESATTO "1": il 2026-08-02 abbiamo censito 70 variabili in DwarfStar
    // che si accendevano con getenv()!=NULL, cioe' anche mettendole a zero.
    return v && strcmp(v, "1") == 0;
}

bool reap_enabled(void) {
    static const bool on = env_flag("LLAMA_REAP");
    return on;
}

// ------------------------------------------------------------ mappa del calore

namespace {

struct calore {
    uint64_t colpi  = 0;   // quante volte questo esperto e' stato scelto
    uint64_t ultimo = 0;   // tick dell'ultima scelta
};

struct stato_reap {
    std::mutex mutex;
    // chiave = (strato << 32) | esperto. 43 strati x 256 esperti = 11.008 possibili.
    std::unordered_map<uint64_t, calore> mappa;
    uint64_t tick      = 0;   // avanza UNA volta per chiamata (= uno strato)
    uint64_t selezioni = 0;   // totale di coppie (token, esperto) osservate
};

stato_reap & stato() {
    static stato_reap s;
    return s;
}

// Dal nome del nodo ricava lo strato: llama.cpp formatta "ffn_moe_topk-23".
int strato_dal_nome(const char * nome) {
    if (!nome) return -1;
    const char * p = strrchr(nome, '-');
    if (!p || !p[1]) return -1;
    char * fine = nullptr;
    const long v = strtol(p + 1, &fine, 10);
    if (fine == p + 1 || *fine != '\0') return -1;
    return (int) v;
}

// L'osservatore vero e proprio, chiamato da ggml-cpu.c dentro `if (ith == 0)`.
void osserva(const char * nome, const int32_t * ids,
             int64_t n_used, int64_t n_tokens, size_t nb0, size_t nb1) {
    if (!ids || n_used <= 0 || n_tokens <= 0) return;

    const int strato = strato_dal_nome(nome);
    if (strato < 0) return;

    auto & s = stato();
    std::lock_guard<std::mutex> lock(s.mutex);

    // Il tick avanza per CHIAMATA, non per esperto: e' la stessa unita' di
    // `call_tick` in DwarfStar. Sbagliarla falsa ogni confronto sulla costante
    // di tempo -- ci e' costata un'ora il 2026-08-02.
    s.tick++;

    const char * base = (const char *) ids;
    for (int64_t t = 0; t < n_tokens; t++) {
        for (int64_t i = 0; i < n_used; i++) {
            const int32_t e = *(const int32_t *) (base + t * nb1 + i * nb0);
            if (e < 0) continue;
            const uint64_t chiave =
                ((uint64_t) (uint32_t) strato << 32) | (uint32_t) e;
            calore & c = s.mappa[chiave];
            c.colpi++;
            c.ultimo = s.tick;
            s.selezioni++;
        }
    }
}

} // namespace

// -------------------------------------------------------------- installazione

void reap_install(void) {
    if (!reap_enabled()) return;
    static bool fatto = false;
    if (fatto) return;
    fatto = true;
    ggml_cpu_set_moe_ids_observer(osserva);
    fprintf(stderr, "reap: osservatore installato sul percorso CPU di mul_mat_id\n");
}

// ---------------------------------------------------------------------- dump

void reap_dump(void) {
    if (!reap_enabled()) return;
    const char * percorso = getenv("LLAMA_REAP_DUMP");
    if (!percorso) return;

    auto & s = stato();
    std::lock_guard<std::mutex> lock(s.mutex);

    FILE * f = fopen(percorso, "w");
    if (!f) {
        fprintf(stderr, "reap: non riesco a scrivere %s\n", percorso);
        return;
    }
    fprintf(f, "# reap-loop: mappa del calore\n");
    fprintf(f, "# chiamate=%llu selezioni=%llu esperti_distinti=%zu\n",
            (unsigned long long) s.tick, (unsigned long long) s.selezioni,
            s.mappa.size());
    fprintf(f, "strato\tesperto\tcolpi\tultimo_tick\n");
    for (const auto & kv : s.mappa) {
        fprintf(f, "%u\t%u\t%llu\t%llu\n",
                (unsigned) (kv.first >> 32), (unsigned) (kv.first & 0xffffffffu),
                (unsigned long long) kv.second.colpi,
                (unsigned long long) kv.second.ultimo);
    }
    fclose(f);
    fprintf(stderr,
            "reap: mappa in %s -- %zu esperti distinti, %llu selezioni, %llu chiamate\n",
            percorso, s.mappa.size(),
            (unsigned long long) s.selezioni, (unsigned long long) s.tick);
}
