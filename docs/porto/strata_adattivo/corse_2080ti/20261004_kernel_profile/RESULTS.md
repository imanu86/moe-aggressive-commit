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
