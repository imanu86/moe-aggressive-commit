// P2 — Esecutore CPU degli esperti MoE: contratto host esplicito.
//
// Adattamento di `freetoken_hybrid/fused_cpu.hpp` (prototipo del 13 settembre)
// a un'interfaccia posseduta dal contesto. Differenze volute rispetto al
// prototipo, tutte documentate in PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md §4:
//
//  - il prototipo aveva un proprietario seriale che creava, usava e distruggeva
//    il pool sullo stesso thread, e che eseguiva anche il lavoro del worker 0.
//    Qui il proprietario seriale e' un COORDINATORE interno: il thread che crea
//    l'esecutore non viene ne' affinizzato ne' usato per calcolare;
//  - i worker del prototipo attendevano attivamente e occupavano core anche a
//    riposo. Qui l'attesa e' a due livelli: giro breve e poi blocco vero
//    (WaitOnAddress/WakeByAddressAll, oppure condition_variable altrove).
//    Fuori dal decode e durante il prefill il pool non consuma CPU (D09);
//  - il prototipo abortiva il processo dopo 10 s di attesa. Qui non esiste
//    nessun abort: scadenza, annullamento e header non valido producono uno
//    STATO, e il risultato non viene mai sostituito da zeri (invariante 7);
//  - generazione, stato per job, cancel, quiesce e teardown sono espliciti.
//
// Vincoli di chiamata:
//  - `submit_hook`/`wait_hook` sono i SOLI punti chiamabili da un nodo host
//    CUDA. Non usano API CUDA e non prendono nessun mutex che il thread in
//    attesa del graph possa trattenere (invariante 6);
//  - tutto il resto si chiama dal thread proprietario (quello che ha creato
//    l'esecutore), fuori da una cattura di graph;
//  - un solo job in volo per esecutore: chiamate concorrenti a submit sono un
//    errore di programma e vengono rifiutate, non serializzate.

#ifndef MOE_CPU_EXECUTOR_H
#define MOE_CPU_EXECUTOR_H

#include "moe_cpu_job.h"
#include "moe_cpu_host_memory.h"

#include "ggml.h"

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

// Stato osservabile di un job, dal lato host.
enum class moe_cpu_state : uint32_t {
    unknown   = 0,  // generazione non piu' in finestra
    running   = 1,
    ok        = 2,
    rejected  = 3,
    cancelled = 4,
    timeout   = 5,
    stopped   = 6,
};

const char * moe_cpu_state_name(moe_cpu_state s);

// Fase del contesto: decide la politica d'attesa dei thread.
enum class moe_cpu_phase : uint32_t {
    idle    = 0,  // fuori dal decode: blocco immediato
    prefill = 1,  // blocco immediato; il pool non deve rubare core al prefill
    decode  = 2,  // finestra di giro breve prima del blocco
};

struct moe_cpu_caps {
    int32_t   n_embd        = 0;                 // K
    int32_t   n_ff_exp      = 0;                 // H
    ggml_type type_gate     = GGML_TYPE_COUNT;   // IQ2_S sui 47 strati supportati
    ggml_type type_up       = GGML_TYPE_COUNT;   // IQ2_S
    ggml_type type_down     = GGML_TYPE_COUNT;   // IQ4_NL
    int32_t   max_rows      = 1;                 // 1 fino a P4, 3 in P5
    int32_t   max_per_row   = 2;                 // cpu_max (D03)
    int32_t   n_threads     = 4;                 // 4 o 6 da confrontare in P4
    uint64_t  wait_timeout_us = 2000000;         // limite del nodo host `wait`
    uint32_t  spin_us       = 60;                // finestra di giro in fase decode
};

// I pesi host ORIGINALI di uno strato. Nessuna copia: sono gli stessi byte che
// la GPU legge in zero-copy dal buffer CUDA<n>_Mapped.
//   gate/up: [n_embd, n_ff_exp, n_experts], passo per esperto = nb[2]
//   down:    [n_ff_exp, n_embd, n_experts], passo per esperto = nb[2]
struct moe_cpu_bank {
    const uint8_t * gate = nullptr;  size_t gate_stride = 0;
    const uint8_t * up   = nullptr;  size_t up_stride   = 0;
    const uint8_t * down = nullptr;  size_t down_stride = 0;
    int32_t         n_experts = 0;
};

// Riga della tabella delle allocazioni, per il rapporto di P2/P6.
struct moe_cpu_allocation {
    const char * name;
    size_t       bytes;
    bool         mapped;   // true: visibile anche al dispositivo
};

class moe_cpu_executor {
public:
    // Crea il pool. Fallisce (nullptr + messaggio) se i tipi non hanno i tratti
    // CPU necessari, se le forme non sono divisibili per i blocchi, se non ci
    // sono abbastanza processori fisici o se il fornitore di memoria fallisce.
    static std::unique_ptr<moe_cpu_executor> create(const moe_cpu_caps & caps,
                                                    std::unique_ptr<moe_cpu_host_memory> memory,
                                                    std::string * err);

    ~moe_cpu_executor();

    moe_cpu_executor(const moe_cpu_executor &)             = delete;
    moe_cpu_executor & operator=(const moe_cpu_executor &) = delete;

    // Registra i pesi host di uno strato. Idempotente per lo stesso strato con
    // gli stessi puntatori; un cambio di puntatore e' un errore (significa che
    // la memoria e' stata riallocata sotto un graph catturato).
    bool register_layer(int32_t layer, const moe_cpu_bank & bank, std::string * err);
    void clear_layers();

    // ---- i due soli punti chiamabili da un nodo host CUDA -------------------
    static void submit_hook(void * user);
    static void wait_hook  (void * user);

    // ---- lato host, fuori dal graph ----------------------------------------
    uint64_t      submitted()  const;   // job pubblicati
    uint64_t      completed()  const;   // job conclusi, con qualunque esito
    uint64_t      failures()   const;   // esiti diversi da ok
    moe_cpu_state state(uint64_t generation) const;
    uint64_t      first_failed_generation() const;  // UINT64_MAX se nessuno
    bool          contaminated() const;             // sticky: c'e' stato un fallimento

    // Annulla. Non interrompe il job in volo (durata limitata, decine di
    // microsecondi): ne invalida l'esito, sblocca l'attesa e rifiuta ogni
    // pubblicazione successiva finche' non si chiama rearm().
    void cancel();
    void rearm();

    // Attende che non ci sia lavoro in volo. Da chiamare DOPO la
    // sincronizzazione del dispositivo e PRIMA di distruggere i graph che
    // referenziano i buffer (ggml-cuda.cu:3666) o di liberare i banchi.
    bool quiesce(uint64_t timeout_us, std::string * err);

    void set_phase(moe_cpu_phase phase);

    // Indirizzi stabili per la cattura del graph.
    const moe_cpu_job   * job_host()   const;
    const moe_cpu_flags * flags_host() const;
    const float         * y_host()     const;
    float               * x_host();                 // solo per i banchi host-only
    moe_cpu_job         * job_host_mut();           // solo per i banchi host-only
    void *                job_dev()   const;
    void *                flags_dev() const;
    void *                x_dev()     const;
    void *                y_dev()     const;

    const moe_cpu_caps & caps() const;
    const std::vector<moe_cpu_allocation> & allocations() const;
    size_t allocated_bytes() const;

    // Riferimento CPU seriale a un thread, stessi tratti e stessa
    // quantizzazione: serve al test di parita'. Scrive n_embd float in `out`.
    bool reference_expert(int32_t layer, int32_t expert, const float * x, float * out,
                          std::string * err) const;

private:
    struct impl;
    explicit moe_cpu_executor(std::unique_ptr<impl> p);
    std::unique_ptr<impl> p_;
};

#endif // MOE_CPU_EXECUTOR_H
