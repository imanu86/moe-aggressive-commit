# Kernel esperti su GPU: il tempo segue i pesi, non i byte

Nsight Systems 2024.5.1, solo tempi: i contatori GPU richiedono un permesso di sistema
non abilitato (ERR_NVGPUCTRPERM). Banco `hybrid_expert_probe` (build-sm75-547-msvc),
input reali `code.shb`, 40 casi, 20 iterazioni, 1 token, layer 0/1/35/36.
Lanci per formato e griglia in `expert_kernel_launches.csv`.

| Kernel | Formato | Lanci | Mediana us (10 esperti) | MB letti | GB/s | Gpesi/s |
|---|---|---:|---:|---:|---:|---:|
| gate+up | IQ2_XXS | 290 | 66,7 | 8,45 | 127 | 491 |
| gate+up | IQ2_XS | 290 | 76,2 | 9,47 | 124 | 430 |
| gate+up | IQ3_XXS | 580 | 70,2 | 12,54 | 179 | 467 |
| down | IQ4_NL | 1180 | 41,4 | 9,22 | 223 | 396 |
| down | Q2_0 | 1180 | 34,9 | 4,61 | 132 | 470 |

Il tempo segue il numero di pesi (circa 400–490 miliardi al secondo), non i byte.
Su 616 GB/s disponibili i kernel restano a 124–223 GB/s: il limite sono le istruzioni
di decodifica e prodotto per peso, non la memoria. Un formato a piu' bit (IQ4, INT8,
FP8 emulato: Turing non ha FP8) non accorcerebbe il tempo per peso e occuperebbe
piu' VRAM.

Le leve sono:
- meno pesi elaborati (esperti o neuroni saltati);
- decodifica condivisa da piu' token (finestre piu' lunghe);
- kernel con meno istruzioni per peso (per esempio #646 upstream).

Verificato anche che IQ3_XXS/IQ2_XXS/IQ2_XS hanno al massimo 8/3/6 ampiezze per blocco
da 32: una ricodifica esatta a 4 bit e' possibile, ma per quanto sopra non serve.

## Percorso CPU per formato (2026-10-05)

Banco `cpu_format_bench` (Strata-2080Ti `main`, `src/kernels/cpu/cpu_format_bench.cpp`): gli stessi kernel
del pool (`native_gu_rows`, `native_down_rows`, `q2_rows_any` per il down Q2_0), 48 esperti distinti per
passata (piu' della L3), Ryzen 5800X con la macchina in uso. Esperti reali degli strati 0/1/35 e gate/up
dello strato 35 riquantizzati dalla ggml in IQ3_S, IQ4_XS, Q4_K, Q8_0: valgono per la velocita', non per
la qualita' (niente imatrix). Uscite complete: `cpu_format_bench.txt`, `cpu_format_bench_smt.txt`.

Tetto di lettura RAM: 24 GB/s con 1 thread, 33–34 GB/s con 8, 32 GB/s con 16.

| gate+up, 8 thread | bpw | us/esperto 1 token | GB/s | us/esperto 4 token |
|---|---:|---:|---:|---:|
| IQ2_XXS | 2,06 | 51–54 | 16–17 | 65–83 |
| IQ2_XS | 2,31 | 52–62 | 15–18 | 89–103 |
| IQ3_XXS | 3,06 | 56–58 | 21–22 | 81–90 |
| IQ3_S (riq.) | 3,44 | 83 | 17 | 127 |
| IQ4_XS (riq.) | 4,25 | 52 | 33 | 69–74 |
| Q4_K (riq.) | 4,5 | 51–56 | 33–36 | 77–82 |
| Q8_0 (riq.) | 8,5 | 102–109 | 32–34 | 114–128 |

Down, 8 thread, 1 token: Q2_0 19–22 us, IQ4_NL 26–34 us (un giro rumoroso a 46).

- IQ2 e IQ3 sono **limitati dal calcolo** (decodifica a codebook): leggono 15–22 GB/s su 34. Su un core
  IQ2_XS costa 235 us contro 111 di Q4_K.
- IQ4_XS e Q4_K sono **limitati dalla banda**: stanno al tetto di 33–34 GB/s e costano lo stesso tempo di
  IQ3_XXS a 1 token, meno a 4 token (69 contro 81–90).
- Scendere a IQ2 per gli esperti calcolati su CPU **non accelera**: stesso tempo per esperto.
- IQ3_S e' il **piu' lento** su CPU (+45% a 1 token): la sua griglia a 512 voci costa piu' istruzioni.
- Q8_0 raddoppia i byte e il tempo.
- SMT (16 thread) non aiuta (solo IQ2_XXS gate/up +17%, al limite del rumore): un worker per core fisico,
  come fa il pool, e' corretto.

Conclusione: il formato in RAM non e' una leva di velocita' per il percorso CPU. IQ4_XS sarebbe una leva di
qualita' a costo di tempo nullo (+39% di byte gate/up rispetto a IQ3_XXS), ma cambia l'output e richiede
pesi veri con imatrix compatibili con GSQ-RCO.
