#pragma once

// REAP-LOOP: residenza degli esperti guidata dal calore, gradino SSD<->RAM.
//
// Perche' esiste
// --------------
// Su una macchina dove il modello non entra in RAM (80,76 GB su 64), chi decide
// quali pesi restano in memoria e' la cache di Windows: una politica globale,
// LRU, che non sa niente di esperti ne' di quanto ciascuno venga usato. Il
// risultato misurato il 2026-08-02 su questo carico:
//
//     258 esperti distinti per token, sempre esattamente 258
//     90,3% degli accessi sono RILETTURE (solo il 9,7% e' primo tocco)
//     la recency pura prenderebbe ZERO colpi: il ciclo e' piu' lungo della cache
//     un miss RAM->SSD costa ~6x un accesso servito dalla RAM
//
// Con quelle proporzioni, decidere per calore invece che per recency e' la leva
// piu' grande rimasta, e nessuno dei due motori in gara (llama.cpp, DwarfStar)
// ce l'ha su questo gradino.
//
// Cosa fa questo modulo
// ---------------------
// FASE 1 (questo file): osserva. Si aggancia a `cb_eval` e legge il tensore
// `ffn_moe_topk`, cioe' i 6 esperti scelti a ogni strato, per costruire la mappa
// del calore senza toccare il percorso di calcolo.
//
// FASE 2: agisce. Tiene in RAM le pagine degli esperti caldi e lascia andare i
// freddi, con ammissione a bussate.
//
// Perche' NON tocchiamo il gradino RAM->VRAM
// ------------------------------------------
// In llama.cpp l'unita' di trasferimento e' il tensore intero di uno strato
// (1,69 GiB, tutti e 256 gli esperti): `ggml_cuda_mul_mat_id` riceve src0
// completo piu' gli id e indicizza dentro il kernel. Portare in VRAM i soli 6
// selezionati richiederebbe di costruire il gather compatto che llama.cpp non
// ha -- e sappiamo gia' che quel trasporto perde contro il calcolo su CPU
// (DwarfStar 4,37 t/s contro llama.cpp 6,86 sullo stesso banco).

#include <cstdint>
#include <cstddef>

struct ggml_tensor;

// Attivazione: variabile d'ambiente LLAMA_REAP=1 (assente = tutto spento,
// costo zero, nemmeno la callback viene installata).
bool reap_enabled(void);

// Installa l'osservatore sul percorso CPU di mul_mat_id. Da chiamare una volta
// dopo l'inizializzazione del backend.
//
// NON usare cb_eval per questo: leggere `ffn_moe_topk` dalla callback costa una
// lettura sincrona device->host per strato (43 per token) e spezza il grafo.
// Misurato il 2026-08-02: prefill da 1,12 a 0,92 t/s, e la GPU che si ferma a
// cadenza fissa. Sul percorso CPU gli id sono gia' in memoria host.
void reap_install(void);

// Scarica su file la mappa del calore accumulata (LLAMA_REAP_DUMP=percorso).
// Formato: una riga per esperto visto, "layer expert conteggio massa".
void reap_dump(void);
