/* Micro-bench 0013: GEMV della testa LM (Q8_0, 129280x4096) su CPU.
 * Fedele al layout Q8_0 di ggml/ds4: blocchi da 32 pesi int8 + scala f16 (qui f32
 * per semplicita' -- differenza di banda ~5%, dichiarata). Accumulo fp32, OpenMP
 * sulle righe. Riporta ms/GEMV ed effettivi GB/s. Aggiunge stima del blocco MoE
 * del drafter (6 expert x 3 matvec 4096x2048 Q4K ~ 28MB) in proporzione di banda.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <omp.h>

#define ROWS 129280
#define COLS 4096
#define QB 32
#define NBLK (COLS / QB)

typedef struct { float d; signed char q[QB]; } blk_q8;

int main(int argc, char **argv) {
    int reps = argc > 1 ? atoi(argv[1]) : 8;
    size_t row_bytes = sizeof(blk_q8) * NBLK;
    size_t total = row_bytes * (size_t)ROWS;
    printf("pesi: %.1f MB (row=%zuB, %d blocchi/riga)\n", total / 1048576.0, row_bytes, NBLK);

    blk_q8 *W = malloc(total);
    if (!W) { printf("alloc fallita\n"); return 1; }
    /* pattern non banale per evitare ottimizzazioni della memoria */
    #pragma omp parallel for
    for (long r = 0; r < ROWS; r++)
        for (int b = 0; b < NBLK; b++) {
            W[r * NBLK + b].d = 0.01f + (r % 7) * 0.001f;
            for (int i = 0; i < QB; i++) W[r * NBLK + b].q[i] = (signed char)((r + b + i) % 251 - 125);
        }

    float x[COLS], *y = malloc(sizeof(float) * ROWS);
    for (int i = 0; i < COLS; i++) x[i] = sinf(i * 0.01f);

    /* warmup */
    #pragma omp parallel for schedule(static)
    for (long r = 0; r < ROWS; r++) {
        float acc = 0.f;
        const blk_q8 *row = &W[r * NBLK];
        for (int b = 0; b < NBLK; b++) {
            float s = 0.f;
            for (int i = 0; i < QB; i++) s += row[b].q[i] * x[b * QB + i];
            acc += s * row[b].d;
        }
        y[r] = acc;
    }

    double best = 1e9, sum = 0;
    for (int rep = 0; rep < reps; rep++) {
        double t0 = omp_get_wtime();
        #pragma omp parallel for schedule(static)
        for (long r = 0; r < ROWS; r++) {
            float acc = 0.f;
            const blk_q8 *row = &W[r * NBLK];
            for (int b = 0; b < NBLK; b++) {
                float s = 0.f;
                for (int i = 0; i < QB; i++) s += row[b].q[i] * x[b * QB + i];
                acc += s * row[b].d;
            }
            y[r] = acc;
        }
        double ms = (omp_get_wtime() - t0) * 1000.0;
        sum += ms; if (ms < best) best = ms;
    }
    /* argmax per chiudere il ciclo del draft */
    int arg = 0; for (long r = 1; r < ROWS; r++) if (y[r] > y[arg]) arg = r;

    double avg = sum / reps;
    printf("threads=%d  GEMV testa: best=%.1f ms  avg=%.1f ms  banda_eff=%.1f GB/s  (argmax=%d)\n",
           omp_get_max_threads(), best, avg, total / (best / 1000.0) / 1e9, arg);
    /* stima drafter completo: testa + MoE 6 exp (28MB Q4K) + attn/proj (~20MB) in banda */
    double extra_ms = best * (28.0 + 20.0) / (total / 1048576.0);
    printf("stima draft completo (testa + ~48MB blocco): ~%.1f ms/token\n", best + extra_ms);
    free(W); free(y);
    return 0;
}
