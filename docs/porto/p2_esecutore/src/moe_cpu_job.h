// P2 — Esecutore CPU/GPU: descrittore del lavoro condiviso fra dispositivo e host.
//
// Questo header e' C puro e deve poter essere incluso sia da .cpp host sia da .cu.
// Le strutture qui dentro vivono in memoria host PINNATA E MAPPATA: il kernel di
// export le scrive attraverso l'alias device (zero-copy), il pool CPU le legge
// attraverso l'alias host. Nessuna API CUDA compare in questo file.
//
// Regole di ordine (vincolanti per P3):
//  1. Il kernel di export scrive header + attivazione e termina con
//     __threadfence_system() prima di concludere.
//  2. Il nodo host `submit` e' accodato sullo STESSO stream, DOPO quel kernel:
//     l'ordinamento di stream garantisce la visibilita' delle scritture all'host.
//  3. Il nodo host `wait` e' accodato DOPO il lavoro GPU degli esperti e PRIMA
//     del nodo che consuma `y`.
//  4. C'e' un solo slot di job per contesto: gli strati sono seriali sullo
//     stesso stream, quindi lo strato il+1 non puo' pubblicare prima che il
//     `wait` dello strato il sia ritornato.

#ifndef MOE_CPU_JOB_H
#define MOE_CPU_JOB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MOE_CPU_JOB_MAGIC    0x4D4F4543u  /* 'MOEC' */
#define MOE_CPU_ABI_VERSION  1u

/* Tetti di forma. MOE_CPU_MAX_ROWS = 3 e' il massimo MTP dichiarato dal piano
   (moe-demand.cuh:232 accetta ids->ne[1] in [1,3]); MOE_CPU_MAX_PER_ROW e' un
   tetto strutturale, il limite operativo `cpu_max` resta 1 o 2 (D03). */
#define MOE_CPU_MAX_ROWS     3
#define MOE_CPU_MAX_PER_ROW  4
#define MOE_CPU_MAX_ROUTES   (MOE_CPU_MAX_ROWS * MOE_CPU_MAX_PER_ROW)

/* Esito di un job. Scritto dal pool, letto dall'host e dal kernel di merge. */
enum moe_cpu_result {
    MOE_CPU_RESULT_NONE      = 0,  /* nessun risultato ancora */
    MOE_CPU_RESULT_OK        = 1,  /* `y` contiene il contributo valido */
    MOE_CPU_RESULT_REJECTED  = 2,  /* header non valido: `y` NON e' stato toccato */
    MOE_CPU_RESULT_CANCELLED = 3,  /* annullamento esplicito */
    MOE_CPU_RESULT_TIMEOUT   = 4,  /* il pool non ha risposto entro il limite */
    MOE_CPU_RESULT_STOPPED   = 5,  /* esecutore in chiusura */
};

/* Una cella per linea di cache: host e dispositivo scrivono su celle diverse e
   non devono condividere una linea sul PCIe. */
struct moe_cpu_cell {
    volatile uint64_t value;
    uint8_t           pad[56];
};

/* Bandiere. Allocate in memoria mappata; l'alias device e' esposto ai kernel.
   - request: alzata dal callback `submit`, abbassata dal coordinatore.
   - done:    alzata dal coordinatore, abbassata dal callback `wait`.
   - result:  uno dei moe_cpu_result del job appena concluso.
   - poison:  1 quando il contenuto di `y` NON e' un risultato valido.
              Il kernel di merge la legge e, se e' 1, NON somma `y`: scrive NaN
              nelle righe interessate. Un errore non puo' diventare uno zero
              silenzioso (invariante 7). */
struct moe_cpu_flags {
    struct moe_cpu_cell request;
    struct moe_cpu_cell done;
    struct moe_cpu_cell result;
    struct moe_cpu_cell poison;
};

/* Descrittore del job. Scritto interamente dal kernel di export.
   `weight` e' il peso ORIGINALE della route, gia' normalizzato e scalato
   (llama-graph.cpp:2089-2107): il contributo CPU non passa una seconda volta
   per la moltiplicazione dei pesi (P1 §4.6).
   Gli ID esperto sono ID LOGICI, non slot. */
struct moe_cpu_job {
    uint32_t magic;                        /* MOE_CPU_JOB_MAGIC */
    uint32_t abi;                          /* MOE_CPU_ABI_VERSION */
    int32_t  layer;                        /* indice di strato registrato */
    int32_t  n_rows;                       /* token in questo job, 1..MOE_CPU_MAX_ROWS */
    int32_t  n_embd;                       /* K, controllo di forma */
    int32_t  n_ff_exp;                     /* H, controllo di forma */
    int32_t  n_routes[MOE_CPU_MAX_ROWS];   /* route CPU per token, 0..MOE_CPU_MAX_PER_ROW */
    int32_t  expert  [MOE_CPU_MAX_ROUTES]; /* ID logico, riga-maggiore per token */
    float    weight  [MOE_CPU_MAX_ROUTES];
    uint64_t sequence;                     /* numero di job, scritto dal dispositivo o 0 */
    uint32_t reserved[6];
};

#ifdef __cplusplus
}
#endif

#endif /* MOE_CPU_JOB_H */
