# LEDGER 14 AGOSTO 2026 — massa globale, 16,07 t/s e contesto 150k

## Riferimento promosso

Configurazione: target/draft 473/12, NMAX2, conf 0,8, AcceptMoE soglia 0,75,
MASSA2, copy-all, corsie stabili.

| tag | t/s | p1 | hit target | miss/copie | verdetto |
|---|---:|---:|---:|---:|---|
| `mass2_copyall_stablelane_t473_d12_b1` | 16,04 | 0,90025 | 77,9% | 47.906 | replica 1 |
| `mass2_copyall_stablelane_t473_d12_b2` | 16,11 | 0,90025 | 77,9% | 47.906 | replica 2 |
| `mass2_copyall_stablelane_t473_d12_b3` | 16,07 | 0,90025 | 77,9% | 47.906 | replica 3 |

Media **16,0733 t/s**, range 0,44%, stesso SHA. Nuova base.

## Bracci della politica globale

| braccio | t/s | risultato |
|---|---:|---|
| MASSA2 con ammissione/zero-copy | 15,08 | terza passata critica, bocciato |
| MASSA2 copy-all + corsie per massa B1 | 15,62 | dentro varianza, replicato |
| stessa B2 | 15,61 | — |
| stessa B3 | 15,35 | media 15,53, bocciata |
| MASSA2 copy-all + corsie stabili B1 | 16,04 | promosso |
| stessa B2 | 16,11 | promosso |
| stessa B3 | 16,07 | media 16,0733 |

La massa migliora la residenza, ma nel banco corrente non deve cambiare le
corsie e non deve introdurre zero-copy.

## Micro-leve chiuse

| leva | run | t/s | p1 | verdetto |
|---|---|---:|---:|---|
| `FORK_RIUSA_SLOT=1` | B1 | 15,84 | stabile | entro varianza, replicato |
| stessa | B2 | 15,71 | stabile | — |
| stessa | B3 | 15,73 | stabile | media 15,76, bocciata |
| `FORK_SALTA_COPIA_PARITA=1` | B1 | 15,37055 | 0,90025 | -4,37%, non replicare |

La rimozione del lavoro apparentemente vuoto riduce la finestra disponibile
alla copia e trasferisce il tempo al join.

Il B di parita' conserva `713/792` token draft accettati e produce lo stesso
output byte per byte dei tre run base (`SHA256
4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D`): la
regressione e' prestazionale, non logica.

## Qualita' lunga a contesto corto

`neuraforge_b2_ctx8192_full`: prompt 74, completion 6.147, totale 6.221,
finish `stop`, 15,91 t/s. HTML/CSS/JS completo, coerente e verificato nel
browser. Questo e' il cancello semantico della famiglia NMAX2/AcceptMoE.

## Contesto 150k

### Tentativo FASI1

`ctx150k_mass2_stable_b1024`: OOM VMM al token prompt 7.169. Causa: slab
target da circa 3.194 MiB ancora residente durante il prefill.

### Tentativo FASI2 — riuscito

`ctx150k_mass2_stable_f2_b1024`:

| metrica | valore |
|---|---:|
| n_ctx effettivo | 150.016 |
| prompt | 101.676 |
| completion | 2.048 |
| totale finale | 103.724 |
| prefill | 92,30 t/s |
| decode medio | 9,69 t/s |
| p1 | 0,76501 |
| finish | length |

Cache target `473 -> 0 -> 473`; workspace `136,70 -> 1.144,24 -> 136,70`
MiB. Attraversati i gradini 102.404 e 103.000. Nessun OOM, errore CUDA o
divergenza replay. Output coerente ma incompleto per il limite 2.048.

## Evidenze memoria/prefill

Target: 7.383,67 MiB densi CUDA0, 74.304 MiB routed experts mapped, embedding
1.010 MiB CUDA_Host. DSpark inutilizzato nel prefill ma ancora caricato:
4.458,36 MiB CPU + 2.224 MiB mapped + 159,49 MiB CUDA.

Direzione:

- differire DSpark al decode;
- UB2048 come primo B zero-code;
- compattare maschere e fare top-k chunked;
- liberare graph + pool alla transizione;
- UB4096 con indexer/top-k tiled;
- se serve, streaming phase-aware dei densi da pageable/mmap con piccolo
  staging VRAM, poi reload in VRAM per decode.

## Fixture KV

Lo state DSV4 target e' gia' completo. `/slots` persiste solo target e non
DSpark: per questo i restore storici rifanno il prompt. Patch minima prevista:
bundle target + draft + manifest; cancello corto 6,5k fresh/restore, poi
fixture 100.992 token con suffix token-array esplicito.

## Coda immediata

1. Singolo B MASSA2 + `FORK_BLOCCHI=4`.
2. Se bocciato, patch ILP4 su `kern_fj_copia`, default-off.
3. Poi RPB4 sul solo MMVQ masked IQ2_XXS mancante.
4. In parallelo, fixture target+draft per eliminare il costo dei test lunghi.

## Stato commit

Nessun commit nuovo di questa fase e nessun push. Il runtime ha un worktree
pregresso molto sporco; prima di committare, separare gli hunk di MASSA2,
corsie e RIUSA_SLOT dalle modifiche estranee. Anche `HANDOFF_13_AGOSTO.md`,
`LEDGER_13_AGOSTO.md` e `dopo_il_riavvio.ps1` erano gia' modificati.

## Prefill layer-major: risultati del 14 agosto

### Staging bulk per chunk — promosso

Fixture 6.510 token, B8192/UB4096, stesso output SHA `C526531F...`:

| configurazione | run | t/s |
|---|---:|---:|
| standard | A | 162,6134 |
| `LAYER_STAGING=1` | B1 | 196,0796 |
| stessa | B2 | 195,9432 |
| stessa | B3 | 194,8275 |

Media B **195,6168 t/s**, +20,30%. Il server divide ancora il prompt in
2.598+4.096; il guadagno viene dalla copia compatta della banca completa dei
256 esperti per layer/chunk, non ancora dalla vera inversione esterna.

### Esecutore layer->tile — bocciato come implementazione

Una sola decode sintetica da 6.013 token:

| configurazione | t/s | delta |
|---|---:|---:|
| standard | 192,1177 | base |
| vero layer-major, pageable | 139,6749 | -27,3% |

Il prototipo completa tutti i 43 layer. Pinned (140,4588), CUDA Graph sul
frammento (150,6279 contro 151,5333 a p20k) e D2H async (137,1090) non lo
recuperano e sono stati rimossi.

Profilo p4.100, 86 grafi: build 34,9 ms; alloc 7.655,6 ms; input 2.269,9 ms;
compute 20.736,8 ms. Causa della regressione: allocazione scheduler e input
ripetuti 43 x tile. Il prossimo braccio non e' un'altra micro-leva: e' un
supergrafo per layer con tutte le tile, una allocazione/compute per layer e
pesi condivisi. Tetto teorico del compute frammentato attuale: circa 198 t/s,
quindi il target 500 richiede anche maschere descrittore/fuse e meno lavoro
per tile.

Artifact principali:

- `a_layer_major_fixture6510_b8192_ub4096.*`;
- `b_layer_major_fixture6510_b8192_ub4096{,_r2,_r3}.*`;
- `a_layer_major_single_decode_p6013_b8192_ub4096.*`;
- `b_layer_major_single_decode_p6013_b8192_ub4096.*`;
- `diag_layer_major_dsprof_single_decode_p4100_b8192_ub4096.*`.

Leve mantenute default-off: `LAYER_STAGING` (positiva) e
`LAYER_EXECUTOR` (scaffold). Leve diagnostiche rimosse: pinned, async output,
layer graphs.
