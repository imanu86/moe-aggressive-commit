# Follow-up × profondità — risultati del 21 settembre 2026

Corse: `D:\ds4_work\banco_followup_run\20260921_065613_x4` (produzione, 40 slot fissi) e
`20260921_070735_m1` (runtime elastico M1, 70 slot dinamici). Una corsa per braccio, 38 richieste
ciascuna, 38/38 completate, cache del prompt rispettata a ogni passo, chiusura con CTRL_BREAK e
VRAM tornata a ~2,1 GB (il desktop ne occupava 2,1-2,3 prima e dopo). Modello GSQ-RCO IQ3_XXS, MTP
spento, KV q8_0, contesto 262144. Rumore sulle celle ripetute: mediano 4,7% (x4) e 10,3% (m1),
massimo 14%: **differenze sotto il 10% fra i due bracci non sono leggibili**.

## In una riga

Il prefill di un follow-up realistico non è governato dalla profondità ma da un **costo fisso di
~2,7-3,5 s per ubatch**: lo staging di ~40 GB di esperti su PCIe (`qwen_prefetch: staged 141 tensors,
39862 MiB`, ~3,5 s a ~11 GB/s), che si paga uguale per 256 token o per 4096. I «400 t/s» esistono
solo per blocchi da 4k in su a contesto corto.

## Tempo di prefill (s) — produzione X4, 40 slot

| contesto | 256 | 1024 | 2048 | 4096 | 8192 |
|---|---|---|---|---|---|
| 0 | 3,04 | 4,07 | 5,41 | 9,83 | 19,26 |
| 33k | 3,37 | 4,67 | 6,65 | 11,36 | 23,32 |
| 66k | 3,46 | 5,05 | 7,48 | 16,31 | 31,13 |
| 99k | 3,60 | 5,58 | 8,70 | 15,83 | 33,16 |
| 116k | 3,48 | 5,56 | 9,80 | 17,72 | 32,56 |

In t/s apparenti (token valutati / tempo):

| contesto | 256 | 1024 | 2048 | 4096 | 8192 |
|---|---|---|---|---|---|
| 0 | 103 | 256 | 381 | 418 | 426 |
| 33k | 81 | 223 | 310 | 362 | 352 |
| 66k | 79 | 206 | 276 | 252 | 264 |
| 99k | 75 | 186 | 237 | 260 | 248 |
| 116k | 78 | 187 | 211 | 232 | 252 |

Riempimenti da ~16k: 424 t/s a 17k, 322 a 50k, 281 a 83k.

## Tempo di prefill (s) — runtime elastico M1, 70 slot dinamici

| contesto | 256 | 1024 | 2048 | 4096 | 8192 |
|---|---|---|---|---|---|
| 0 | 2,94 | 3,85 | 5,15 | 8,93 | 17,80 |
| 33k | 3,82 | 5,03 | 6,69 | 11,55 | 21,47 |
| 66k | 3,65 | 5,34 | 7,61 | 14,79 | 28,36 |
| 99k | 3,94 | 5,98 | 8,13 | 15,96 | 31,38 |
| 116k | 4,23 | 6,85 | 10,08 | 16,54 | 34,98 |

Riempimenti da ~16k: 434 t/s a 17k, 357 a 50k, 318 a 83k.

## Letture

1. **Follow-up piccoli: la profondità conta poco.** 256 token costano 3,0 s a contesto vuoto e 3,5 s a
   116k (+15%); 1024 token 4,1 → 5,6 s (+37%). Intercetta ~2,7 s a ogni profondità; il costo
   marginale per token passa da ~1,3 ms (contesto vuoto) a ~2,7-4 ms (116k).
2. **Blocchi grossi: il degrado è soprattutto la scaletta dell'ubatch.** 4096 token: 9,8 s a 0,
   11,4 s a 33k, poi **16,3 s a 66k** — il salto coincide con `demand workspace tokens=3072 kv=80k`:
   il blocco non sta più in un ubatch, ne servono due, e ogni ubatch in più ripaga lo staging.
   Da 112k l'ubatch scende a 2048. La scaletta è imposta dalla VRAM (l'area di lavoro cresce col KV).
   In un ubatch pieno da 4096 lo staging pesa ~3,5 s su ~9-10 s.
3. **Elastico contro produzione: pari dentro il rumore.** M1 è un po' più veloce sui blocchi grossi
   (riempimenti +2/+12%, 8192 token +6/+10% fino a 99k) e un po' più lento sui follow-up piccoli in
   profondità (256 e 1024 token a 116k: +20%), dove paga lo smontaggio della cache da 5,9 GB a ogni
   prefill. In questa corsa M1 ha seguito la scaletta (4096 → 3072 → 2048) senza il dimezzamento a
   1024 visto nel 6×20k di Codex: quello scatta solo quando la riserva trova la VRAM a zero.
4. **Primi token dopo il prefill** (indicativo, 8 token per passo): 11,7 → 10,6 t/s su X4, 6,4 → 5,2
   su M1. L'elastico svuota la cache esperti a ogni prefill e la ricostruisce in decode partendo da 30
   slot: è anche la VRAM che «oscilla» fra 11 e 5,9 GB quando i prefill sono ravvicinati. Da misurare
   su risposte lunghe prima di trarre conclusioni sul decode.

## Leva da provare (non provata)

Nei binari di produzione esiste `GGML_OP_OFFLOAD_MIN_BATCH` (default 32, `ggml-cuda.cu:6104`): sotto
quella taglia di batch i pesi su CPU non vengono portati alla GPU. Alzarla (256-512) eviterebbe lo
staging da ~40 GB ai follow-up corti; se il calcolo degli esperti su CPU per ~256 token sta sotto i
~3 s, il tempo al primo token dei messaggi brevi scende molto più del 5%. Rischio: i percorsi propri
del fork (`LLAMA_MOE_DEMAND_GPU`, staging) potrebbero scavalcare la manopola. Prova minima: un solo
livello, celle 64/128/256/512, con e senza la variabile. `GGML_CUDA_MOE_CPU_PREFILL`, che sta nel
preset, in questo albero **non ha lettore**: è inerte.

## Difetto trovato

`/completion` grezzo con prompt a vettore di token (512 o 4608 token) come prima richiesta: il server
cade con `CUDA error: an illegal memory access` subito dopo `demand workspace tokens=508 kv=16384`.
Tre corse su tre, su entrambi i binari. In chat il primo blocco è sempre il preambolo del template
(42-89 token a kv=256) e il difetto non si presenta; i client di produzione passano tutti dalla chat.
Causa non indagata.

## Con la 2080 Ti da 22 GB

Due dei tre costi visti qui dipendono dalla VRAM: la scaletta dell'ubatch (l'area di lavoro a 4096
starebbe a ogni profondità) e la quota di esperti da portare a ogni ubatch (più esperti residenti =
meno byte di staging). Il terzo, la banda dello staging, no: ~11 GB/s effettivi sono già da PCIe 3.0.
