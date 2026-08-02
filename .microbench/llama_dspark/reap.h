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
// FASE 1 (questo file): osserva. Si aggancia al percorso CPU di mul_mat_id e
// registra i 6 esperti scelti a ogni strato, per costruire la mappa del calore
// senza toccare il percorso di calcolo.
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
//
// ---------------------------------------------------------------------------
// DUE DISEGNI SCARTATI, e il conto che ha corretto il secondo
// ---------------------------------------------------------------------------
// 1. cb_eval su `ffn_moe_topk`. Lettura sincrona device->host per strato, 43
//    stop per token, spezza il grafo. Misurato: prefill 1,12 -> 0,92 (-18%).
//
// 2. hash map + mutex dentro `if (ith == 0)`. Misurato una volta a 4,66 contro
//    6,86 (-32%), e attribuito al lookup. IL CONTO NON TORNA: il barrier di ggml
//    e' uno spin puro (ggml-cpu.c:599, nessun fallback a sleep), quindi gli
//    altri thread pagano esattamente il ritardo del thread 0 e nulla di piu'.
//    Quel ritardo sarebbe
//        68,8 ms/token / (42 strati x 3 mul_mat_id x 6 id) = 91 us per lookup,
//    contro i 20-100 ns che un unordered_map costa davvero: mille volte tanto.
//    Il -32% va cercato altrove (build diversa, page cache fredda dopo la
//    ricompilazione su una macchina che sta 16 GB sopra la RAM); il run era
//    anche a 800 token contro i 1500 del riferimento.
//
// Il disegno qui sotto e' comunque quello giusto -- nella sezione critica
// nessun lock e nessuna allocazione -- ma la sua giustificazione ora e' la
// misura diretta, non l'inferenza: con LLAMA_REAP_PROF=1 il modulo cronometra
// se stesso e stampa i nanosecondi effettivi passati nella sezione critica.

#include <cstdint>
#include <cstddef>

struct ggml_tensor;

// Attivazione: variabile d'ambiente LLAMA_REAP=1 (assente = tutto spento,
// costo zero, nemmeno la callback viene installata: `g_moe_ids_observer` resta
// NULL e sul percorso CPU resta un solo test di puntatore per nodo).
bool reap_enabled(void);

// Installa l'osservatore sul percorso CPU di mul_mat_id e avvia il consumatore.
// Da chiamare una volta dopo l'inizializzazione del backend.
//
// NON usare cb_eval per questo: leggere `ffn_moe_topk` dalla callback costa una
// lettura sincrona device->host per strato (43 per token) e spezza il grafo.
// Sul percorso CPU gli id sono gia' in memoria host.
void reap_install(void);

// Scarica su file la mappa del calore accumulata (LLAMA_REAP_DUMP=percorso).
// Ferma e raccoglie il consumatore, poi svuota quel che resta nell'anello.
// Formato: intestazione con le diagnostiche, poi "strato esperto colpi ultimo".
void reap_dump(void);
