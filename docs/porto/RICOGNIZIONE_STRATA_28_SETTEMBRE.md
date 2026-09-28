# Strata (github.com/Niko1221/Strata) contro il nostro motore — 28 settembre 2026

Solo lettura del repo e del codice via web, niente scaricato ne' eseguito. Strata e' un motore scritto a mano per
**lo stesso modello del nostro daily**: Qwen3.8-Flash-Next **GSQ-RCO** di ISTA-DASLab (quant Q2_0, IQ2_XS, IQ3_XXS,
IQ3_S; Coder IQ1_M). Da ggml prende solo formati e alcuni kernel (MMQ, IQ). Numeri dichiarati su RTX 5070 12 GB +
Ryzen 5 7600 (AVX-512) + 64 GB DDR5: IQ3_XXS 62 t/s corto, 46 t/s a 128K, prefill 1.110 t/s a 32K.

**Dato chiave, da utenti su macchine come la nostra** (issue del repo, motori spesso vecchi): **3060 + Ryzen 9 5950X
(16 core Zen 3, AVX2) + DDR4-3200, IQ2_XS a 32K: ~40,5 t/s decode, prefill 421 su 16,5K** (#13; sulla stessa macchina
llama.cpp b11146 con `--n-cpu-moe 40` fa 10,9 e 227; MTP non dichiarato); 3060 + i5-10400 ~21 t/s (#12); 3090 + Ryzen 5
5600X (solo AVX2) 23-25 → 39-43 t/s coi nuovi kernel AVX2 (#54); 5060 Ti su PCIe 4.0 x8: `pcie_frac` 0,30 meglio di
0,55 (#44). Attenzione: IQ2_XS e' un file piu' leggero del nostro (vedi sotto).

**Noi, sul daily GSQ-RCO IQ3_XXS** (3060 + 5800X 8 core + DDR4-3000, PCIe 4.0 x16 26 GB/s; greedy, ragionamento acceso):
23,2-25,4 t/s a 131k con MTP spento e 40-70 slot (Codex, 20/9, `BENCHMARK_GSQ_20_SETTEMBRE.md`); 22,4-22,9 a 100k con
l'elastico senza deposito RAM, 19,7-19,9 col deposito della produzione (21/9); con MTP e sotto pressione RAM 20,45 a 32k
(Codex, `MTP_RAM_20_SETTEMBRE.md`); ~11 nell'uso reale, non spiegato. **Correzione della prima stesura:** i 28,66 t/s a
32k, i 27,25 a 131k e l'anatomia P9 (37,4 ms/token, pavimento dei byte 21,9 ms) sono del vecchio Unsloth UD-IQ3_XXS,
cancellato: non sono il riferimento del daily. Dove la colonna «noi» qui sotto cita P9, descrive la forma del nostro
motore (lanci, sincronizzazioni, riga di verifica); i millisecondi vanno rimisurati sul GSQ.

Il nostro GSQ-RCO «IQ3_XXS» e' un mix per tensore (intestazioni lette con `docs/porto/gguf_tipi.py`): esperti instradati
39,97 GiB in sette tipi (IQ3_S 8,73, IQ4_NL 7,91, Q2_0 6,59, IQ2_S 5,00, IQ2_XS 4,52, IQ2_XXS 3,63, IQ3_XXS 3,59; media
~2,83 bpw, ~1,74 MB per esperto), PLE 26,88 GiB IQ4_NL, densi 2,99 GiB, embedding/uscita 0,67. Un IQ2_XS sta intorno ai
2,3 bpw: circa il 20% di byte in meno per ogni mancanza e piu' esperti in cache. **Un confronto pulito non esiste**: stima
grezza di Strata qui col nostro file ~28-35 t/s a 32k (esperti piu' pesanti, meta' dei core del 5950X), da misurare.

## Cosa fa diversamente (con i file)

| Strata | noi | trasferibile qui |
|---|---|---|
| **Mancanze divise in tre, in parallelo, per strato**: hit in VRAM, una quota letta dalla GPU via PCIe (`pcie_frac`, default 0,55) e il resto calcolato dalla **CPU su tutti i core fisici** (pool pinnato, l'host partecipa); `src/core/expert_source.cpp`, `src/kernels/cpu/pool.cpp` | tutte le mancanze lette dalla GPU via PCIe (percorso a domanda); la corsia CPU del 14/9 (P3/P4) aveva 2 thread e al massimo 2 esperti per strato, chiusa con D18 (−1,6% / −5,9%) e D31 | si', con `pcie_frac` ~0,25-0,3 per il nostro bus |
| **Sincronizzazione a «doorbell»** in memoria pinned mappata: un kernel pubblica x/ids/pesi, l'host fa spin; il ritorno lo attende un kernel a un thread che fa spin sul flag, dentro lo stesso grafo (`inc/core/layer.hpp` ~396-424, `src/core/session.cpp` ~992-1100) | nodi host del grafo (59-112 µs/strato); il polling a 13,8 µs/strato e' stato misurato ma usato solo per le righe di bozza | si' |
| **Un CUDA graph per token o per finestra di verifica**, niente scheduler ggml (`src/core/graph.cpp`, `inc/core/verify.hpp`) | 4.256 lanci/token, 78 sincronizzazioni per passata, 3,3 ms di GPU ferma (P9) | si' |
| **MTP con finestra di verifica T<=4 in un grafo**: pesi densi letti una volta per T token; kernel CPU multi-token che decodificano i pesi degli esperti una volta per tutte le righe; unione delle mancanze divisa fra PCIe e CPU; bozza finche' p >= 0,5; prompt lookup se batte l'MTP del 3%. **2,35-3,52 token per round** | vince solo la bozza a 1 (1,79 token/passata): la riga di verifica costa 16,6-20,2 ms (mmvq + trasferimenti) | si': e' la leva principale a contesto corto |
| **KV a pagine** da 4 celle con clock second-chance: copia vera in RAM pinned, in VRAM solo le pagine usate dalla QSA (`inc/kernels/kv_stream.hpp`) | KV mappata, si raccolgono le 2.048 celle scelte a ogni token (2,6 ms/token) | si' |
| **Prefill a blocchi 8.192/6.144/4.096** secondo quanto la cache presta, MMQ int8, anello di streaming degli esperti con anticipo durante l'attenzione (`src/prefill/prefill.cpp`) | ubatch <= 4096, staging ~11 GB/s, 8.192 non entrava (WDDM) | si' |
| Tabella PLE su SSD con I/O diretto e prefetch (~0,3 ms/token) | in RAM (27,5 GB) | irrilevante con 96 GB |
| Cache riempita da un profilo statico (colpi 64% contro 49% senza) + adattamento lento (ogni 4 round, <=96 scambi) | frequenza con decadimento, colpi 63% a 40 slot e 74% a 64 slot (GSQ, Codex 20/9) | nessun divario |
| Q2_0 (blocchi da 64, 2,25 bpw) con kernel AVX-512 VNNI / AVX2 | nel GSQ 6,59 GiB di esperti sono proprio Q2_0 (tipo ggml 42); sul vecchio UD l'IQ2_S era limitato dalla dequantizzazione (2,5 bpw costavano come 6,87) | kernel AVX2 si', VNNI no |

Non si trasferiscono: AVX-512 VNNI, DDR5 (~44 GB/s per loro contro 33 per noi), PCIe 5.0.

## Correzione a una conclusione precedente

La corsia CPU chiusa il 14/9 (D18) era stata provata in una forma stretta: 2 thread, massimo 2 esperti per strato,
sincronizzazione con nodi host. Sulla nostra macchina un esperto costa alla CPU 0,08 ms contro ~0,10 ms via PCIe (misure
sul vecchio UD; col GSQ, ~1,74 MB per esperto, il rapporto resta circa pari), quindi da sola la CPU non vince: il guadagno viene dal SOMMARE le due vie (GPU + CPU ~38-39 GB/s contro 26) dentro
un unico grafo con attese sul device, e dal rendere economica la verifica MTP. Strata fa esattamente questo.

## Provato qui la sera del 28/9

`strata_prova/RISULTATI_28_SETTEMBRE.md`: con gli altri programmi aperti Strata fa 19,55 t/s di decode aggregato
(702 esperti in VRAM, 1,56-1,92 token per passata) contro 7,09 del daily, la cui cache elastica resta a 0 slot per il
cancello di crescita RAM di M2. Prefill pari.

## Provarlo qui

- Usa il nostro stesso file: `--gguf-dir` accetta la cartella coi due shard GSQ-RCO-IQ3_XXS gia' in Downloads (niente
  download da 76 GB); per IQ3_XXS servono 60 GB di RAM (arena 42,9 GB), il daily va spento. La testa MTP la scarica
  a parte (~5 GB dal checkpoint originale, `tools/mtp_fetch.py`).
- Espone `/v1/messages` (Anthropic) e `/v1` (OpenAI), `--port` e `--api-key`: puo' stare sulla 8100 dietro il gateway.
- Driver richiesto >= 580: il nostro e' 596.21. Per compilare dal sorgente serve il CUDA Toolkit 13.0 (qui c'e' solo
  12.6); in alternativa binari precompilati della release (sm_86 compreso).
