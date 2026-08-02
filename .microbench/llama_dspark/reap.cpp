#include "reap.h"

#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
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

static bool reap_prof(void) {
    static const bool on = env_flag("LLAMA_REAP_PROF");
    return on;
}

namespace {

// ------------------------------------------------------------------- l'anello
//
// La sezione critica e' dentro `if (ith == 0)` di ggml_compute_forward_mul_mat_id,
// subito prima di ggml_barrier: mentre il thread 0 e' li', gli altri 15 girano
// a vuoto su uno spin. Quindi li' dentro si fa SOLO scrittura lineare:
//
//     un fetch_add per chiamata  (non per esperto)
//     n_tokens record scritti in sequenza
//     uno store release per record, che lo dichiara leggibile
//
// Niente lock, niente allocazioni, niente hash map, niente I/O. Il calore, la
// politica e tutto cio' che puo' costare sta nel consumatore, su un altro thread.

constexpr int      REAP_IDS_MAX = 16;          // esperti per token per strato
constexpr uint32_t REAP_CAP     = 1u << 16;    // record nell'anello (~5 MiB)
constexpr uint32_t REAP_MASK    = REAP_CAP - 1;

struct record {
    // `seq` viene scritto per ULTIMO, con release: finche' non vale il giro
    // atteso, il consumatore sa che il record e' incompleto o non ancora suo.
    std::atomic<uint32_t> seq{0};
    uint32_t strato = 0;
    uint32_t n      = 0;
    int32_t  id[REAP_IDS_MAX] = {0};
};

struct calore {
    uint64_t colpi  = 0;   // quante volte questo esperto e' stato scelto
    uint64_t ultimo = 0;   // tick dell'ultima scelta
};

struct stato_reap {
    // --- scritto dal produttore (thread 0 del threadpool) ---
    // parentesi tonde, non graffe: `record` contiene un atomic, non e' copiabile,
    // e vogliamo il costruttore per DIMENSIONE, non una initializer_list.
    std::vector<record>   anello = std::vector<record>(REAP_CAP);
    std::atomic<uint64_t> scritti{0};      // record prodotti in totale
    std::atomic<uint64_t> chiamate{0};     // chiamate a osserva()
    std::atomic<uint64_t> troncati{0};     // n_used > REAP_IDS_MAX
    std::atomic<uint64_t> ns_critica{0};   // solo con LLAMA_REAP_PROF=1

    // --- del consumatore soltanto ---
    uint64_t letti   = 0;
    uint64_t persi   = 0;   // record sovrascritti prima di essere letti
    uint64_t tick    = 0;   // avanza per RECORD (= uno strato, un token)
    uint64_t selezioni = 0;
    std::unordered_map<uint64_t, calore> mappa;   // (strato<<32)|esperto

    std::thread           consumatore;
    std::atomic<bool>     fermati{false};
};

stato_reap & stato() {
    static stato_reap s;
    return s;
}

// Dal nome del nodo ricava lo strato: llama.cpp formatta "ffn_moe_topk-23".
// Resta nella sezione critica perche' costa decine di ns (strrchr su ~16 byte)
// e portarlo fuori vorrebbe dire copiare il nome o fidarsi di un puntatore che
// vive quanto il grafo.
int strato_dal_nome(const char * nome) {
    if (!nome) return -1;
    const char * p = strrchr(nome, '-');
    if (!p || !p[1]) return -1;
    char * fine = nullptr;
    const long v = strtol(p + 1, &fine, 10);
    if (fine == p + 1 || *fine != '\0') return -1;
    return (int) v;
}

// -------------------------------------------------------------- il produttore

void osserva(const char * nome, const int32_t * ids,
             int64_t n_used, int64_t n_tokens, size_t nb0, size_t nb1) {
    if (!ids || n_used <= 0 || n_tokens <= 0) return;

    const int strato = strato_dal_nome(nome);
    if (strato < 0) return;

    auto & s = stato();

    const bool prof = reap_prof();
    const auto t0 = prof ? std::chrono::steady_clock::now()
                         : std::chrono::steady_clock::time_point{};

    int64_t n = n_used;
    if (n > REAP_IDS_MAX) {
        n = REAP_IDS_MAX;
        s.troncati.fetch_add(1, std::memory_order_relaxed);
    }

    // UN solo atomico per chiamata: si prende in blocco lo spazio per tutti i
    // token di questa chiamata. In decode n_tokens vale 1, in prefill vale
    // l'ubatch -- in entrambi i casi e' un fetch_add, non uno per esperto.
    const uint64_t base = s.scritti.fetch_add((uint64_t) n_tokens,
                                              std::memory_order_relaxed);

    const char * src = (const char *) ids;
    for (int64_t t = 0; t < n_tokens; t++) {
        const uint64_t pos = base + (uint64_t) t;
        record & r = s.anello[pos & REAP_MASK];

        r.strato = (uint32_t) strato;
        r.n      = (uint32_t) n;
        if (nb0 == sizeof(int32_t)) {
            memcpy(r.id, src + t * nb1, (size_t) n * sizeof(int32_t));
        } else {
            for (int64_t i = 0; i < n; i++) {
                r.id[i] = *(const int32_t *) (src + t * nb1 + i * nb0);
            }
        }
        // release: chi legge `seq` col giusto valore vede anche il payload.
        r.seq.store((uint32_t) (pos / REAP_CAP) + 1, std::memory_order_release);
    }

    s.chiamate.fetch_add(1, std::memory_order_relaxed);

    if (prof) {
        const auto dt = std::chrono::steady_clock::now() - t0;
        s.ns_critica.fetch_add(
            (uint64_t) std::chrono::duration_cast<std::chrono::nanoseconds>(dt).count(),
            std::memory_order_relaxed);
    }
}

// ------------------------------------------------------------- il consumatore

// Svuota l'anello fino a `limite` (escluso). Qui si puo' spendere: hash map,
// calore, e in fase 2 la politica di residenza.
void drena(stato_reap & s, uint64_t limite) {
    while (s.letti < limite) {
        record & r = s.anello[s.letti & REAP_MASK];
        const uint32_t atteso  = (uint32_t) (s.letti / REAP_CAP) + 1;
        const uint32_t osservato = r.seq.load(std::memory_order_acquire);

        if (osservato < atteso) {
            // non ancora scritto: il produttore ha preso il posto col fetch_add
            // ma non ha finito. Ci fermiamo, riproveremo al prossimo giro.
            return;
        }
        if (osservato > atteso) {
            // ci hanno doppiati: quel record non esiste piu'. Lo contiamo, e
            // saltiamo avanti -- meglio un buco dichiarato di un dato falso.
            s.persi++;
            s.letti++;
            continue;
        }

        s.tick++;
        const uint32_t strato = r.strato;
        const uint32_t n      = r.n;
        for (uint32_t i = 0; i < n && i < REAP_IDS_MAX; i++) {
            const int32_t e = r.id[i];
            if (e < 0) continue;
            calore & c = s.mappa[((uint64_t) strato << 32) | (uint32_t) e];
            c.colpi++;
            c.ultimo = s.tick;
            s.selezioni++;
        }
        s.letti++;
    }
}

void ciclo_consumatore() {
    auto & s = stato();
    while (!s.fermati.load(std::memory_order_acquire)) {
        const uint64_t limite = s.scritti.load(std::memory_order_acquire);
        if (s.letti >= limite) {
            // vuoto: si dorme. Un consumatore che gira a vuoto ruberebbe un core
            // ai 16 del threadpool, che e' esattamente l'errore che stiamo
            // togliendo dalla sezione critica.
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
            continue;
        }
        drena(s, limite);
    }
}

} // namespace

// -------------------------------------------------------------- installazione

void reap_install(void) {
    if (!reap_enabled()) return;
    static bool fatto = false;
    if (fatto) return;
    fatto = true;

    auto & s = stato();
    s.mappa.reserve(43 * 256);   // tutte le coppie possibili: mai un rehash dopo
    s.consumatore = std::thread(ciclo_consumatore);

    ggml_cpu_set_moe_ids_observer(osserva);
    fprintf(stderr,
            "reap: osservatore installato (anello %u record, %.1f MiB)%s\n",
            REAP_CAP, (double) (REAP_CAP * sizeof(record)) / (1024.0 * 1024.0),
            reap_prof() ? ", cronometro ACCESO" : "");
}

// ---------------------------------------------------------------------- dump

void reap_dump(void) {
    if (!reap_enabled()) return;

    auto & s = stato();

    // Prima si ferma il produttore-consumatore, poi si legge: cosi' il dump non
    // ha bisogno di prendere lock nel percorso caldo.
    s.fermati.store(true, std::memory_order_release);
    if (s.consumatore.joinable()) s.consumatore.join();
    drena(s, s.scritti.load(std::memory_order_acquire));

    const uint64_t chiamate = s.chiamate.load(std::memory_order_relaxed);
    const uint64_t ns       = s.ns_critica.load(std::memory_order_relaxed);

    // Le diagnostiche vanno SEMPRE a stderr, anche senza file di dump: sono la
    // risposta alla domanda "quanto costa davvero la sezione critica".
    fprintf(stderr,
            "reap: %llu chiamate, %llu record prodotti, %llu letti, %llu persi, "
            "%zu esperti distinti, %llu selezioni\n",
            (unsigned long long) chiamate,
            (unsigned long long) s.scritti.load(std::memory_order_relaxed),
            (unsigned long long) s.letti, (unsigned long long) s.persi,
            s.mappa.size(), (unsigned long long) s.selezioni);
    if (s.troncati.load(std::memory_order_relaxed)) {
        fprintf(stderr, "reap: ATTENZIONE %llu chiamate con n_used > %d, troncate\n",
                (unsigned long long) s.troncati.load(std::memory_order_relaxed),
                REAP_IDS_MAX);
    }
    if (ns && chiamate) {
        fprintf(stderr,
                "reap: sezione critica %.1f ns/chiamata, %.3f ms in totale\n",
                (double) ns / (double) chiamate, (double) ns / 1e6);
    }

    const char * percorso = getenv("LLAMA_REAP_DUMP");
    if (!percorso) return;

    FILE * f = fopen(percorso, "w");
    if (!f) {
        fprintf(stderr, "reap: non riesco a scrivere %s\n", percorso);
        return;
    }
    fprintf(f, "# reap-loop: mappa del calore\n");
    fprintf(f, "# chiamate=%llu record=%llu persi=%llu selezioni=%llu esperti_distinti=%zu\n",
            (unsigned long long) chiamate, (unsigned long long) s.letti,
            (unsigned long long) s.persi, (unsigned long long) s.selezioni,
            s.mappa.size());
    if (ns && chiamate) {
        fprintf(f, "# sezione_critica_ns_per_chiamata=%.1f totale_ms=%.3f\n",
                (double) ns / (double) chiamate, (double) ns / 1e6);
    }
    fprintf(f, "strato\tesperto\tcolpi\tultimo_tick\n");
    for (const auto & kv : s.mappa) {
        fprintf(f, "%u\t%u\t%llu\t%llu\n",
                (unsigned) (kv.first >> 32), (unsigned) (kv.first & 0xffffffffu),
                (unsigned long long) kv.second.colpi,
                (unsigned long long) kv.second.ultimo);
    }
    fclose(f);
    fprintf(stderr, "reap: mappa in %s\n", percorso);
}
