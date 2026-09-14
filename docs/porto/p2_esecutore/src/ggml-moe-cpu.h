// P2 — Confine d'interfaccia minimo fra il backend CUDA e l'esecutore CPU.
//
// In P3 questo file va copiato in `ggml/include/ggml-moe-cpu.h` e le due
// funzioni implementate in `ggml/src/ggml.c` accanto a ggml_set_moe_obs_callback
// (ggml.c:252-265), di cui questo e' il calco esatto: una tabella globale di
// ggml-base, installata da libllama e letta dal backend CUDA.
//
// Perche' cosi' e non altrimenti:
//  - il backend CUDA NON deve conoscere llama_context;
//  - libllama NON deve linkare ggml-cuda;
//  - l'esecutore usa i tratti CPU (ggml_get_type_traits_cpu), quindi vive dal
//    lato che gia' linka ggml-cpu, cioe' libllama;
//  - nessun tipo CUDA compare qui: `ggml_moe_cpu_fn_t` coincide con
//    cudaHostFn_t (void(*)(void*)) e i puntatori sono `void *`.
//
// La sonda del 13 settembre leggeva la struttura interna del backend CUDA
// (overlap_probe.cu:146-147, `ggml_backend_cuda_context::streams`). Quella
// lettura NON diventa un'API: qui passano solo puntatori opachi e due callback.

#ifndef GGML_MOE_CPU_H
#define GGML_MOE_CPU_H

#include "ggml.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

    /* Firma identica a cudaHostFn_t: usabile con cudaLaunchHostFunc senza cast. */
    typedef void (*ggml_moe_cpu_fn_t)(void * user);

    struct ggml_moe_cpu_hooks {
        uint32_t          abi;          /* MOE_CPU_ABI_VERSION */
        void *            user;         /* l'esecutore, opaco */

        /* Nodi host. Vincoli non negoziabili (invariante 6 del piano):
           nessuna API CUDA al loro interno, nessun mutex che possa essere
           trattenuto dal thread che aspetta il graph, ritorno in tempo finito. */
        ggml_moe_cpu_fn_t submit;       /* pubblica il job e sveglia il pool */
        ggml_moe_cpu_fn_t wait;         /* attende l'esito, con limite di tempo */

        /* Alias DEVICE di memoria host pinnata e mappata. Stabili per tutta la
           vita dell'esecutore: sono ingressi di graph e non possono cambiare
           fra cattura e replay. */
        void *  job_dev;                /* struct moe_cpu_job   */
        void *  flags_dev;              /* struct moe_cpu_flags */
        void *  x_dev;                  /* float [max_rows * n_embd], attivazione */
        void *  y_dev;                  /* float [max_rows * n_embd], contributo CPU */

        /* Forme dichiarate alla creazione; il kernel di export le rispetta. */
        int32_t max_rows;
        int32_t max_per_row;
        int32_t n_embd;
        int32_t n_ff_exp;
    };

    /* Installa la tabella. NULL la disinstalla. Il chiamante e' il proprietario
       della memoria puntata e deve disinstallare PRIMA di distruggere
       l'esecutore. Una seconda installazione mentre una e' attiva e' un errore:
       l'implementazione deve rifiutarla e restituire false (un solo pool vivo
       per processo, coerente con «un solo pool per contesto» di D09, perche'
       il percorso a domanda richiede gia' n_seq_max == 1). */
    GGML_API bool ggml_moe_cpu_set_hooks(const struct ggml_moe_cpu_hooks * hooks);

    /* NULL quando la funzione e' spenta. Letta dal backend CUDA a ogni
       costruzione del graph; non va memorizzata fra un replay e l'altro. */
    GGML_API const struct ggml_moe_cpu_hooks * ggml_moe_cpu_get_hooks(void);

#ifdef __cplusplus
}
#endif

#endif /* GGML_MOE_CPU_H */
