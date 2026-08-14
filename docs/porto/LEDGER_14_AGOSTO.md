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

## Split attenzione/FFN e barriera laterale

Il grafo ridotto DSV4 ha mostrato che il residuo non domina tutte le scritture
di stato. Senza fence, avanzare il replay cursor o iniziare il grafo seguente
puo' correre con CSA/HCA/LID ancora in volo. La correzione conservativa e'
`ggml_backend_sched_synchronize()` dopo ogni grafo layer-major.

Fixture p4.100, B8192/UB4096, packetizer 0:

| configurazione | t/s | FNV | verdetto |
|---|---:|---|---|
| normale | 196,7489 | `FD9308B918867FCA` | riferimento |
| attn+FFN separati, stessa UB | 91,3621 | `FD9308B918867FCA` | corretto, troppo lento |

Il B con FFN macro 6.013 e attenzione 4.096 ha fatto 82,742 t/s contro
187,9865 della base p6.013: -56,0%, nessuna replica. Finito, stesso top-1, ma
non promosso. Il roundtrip residuo host e due grafi per layer dominano.

## Sonda di residenza virtuale: kernel/UVA/DMA

Tre run distinguono meccanismo e correttezza:

| run | t/s | output | verdetto |
|---|---:|---|---|
| mono-slab, copia-kernel su stream separato | 145,001 | NaN | invalido |
| SoA + `cudaMemcpyAsync` da UVA, senza fence completa | 137,709 | stesso FNV corrotto | invalido |
| SoA + `cudaMemcpyAsync` da UVA, con fence | 127,4757 | finito, top-1 223 | -32,2%, bocciato |

Base corrente p6.013: 187,9865 t/s, FNV `15A8650CAED23461`.
Il B finito ha FNV `5A2BCC784D1A2DEE`: la differenza numerica non cambia il
verdetto prestazionale e non autorizza repliche.

Conclusione: `CUDA0_Mapped`/UVA non e' il pinned staging ring di G39.
La copia-kernel compete per gli SM; `cudaMemcpyDefault` dall'alias UVA non
dimostra un H2D copy-engine economico. Ramo sperimentale rimosso. Restano:

- barriera laterale nel layer-major;
- `LAYER_STAGING` positivo per chunk;
- `LAYER_EXECUTOR` come scaffold default-off;
- necessita' di backing mmap/pageable + ring pinned + staging VRAM con eventi
  di ownership, prima di parlare di overlap reale.

Artifact: `diag_layersplit_sync_p4100_b8192_ub4096.*`,
`b_layersplit_sync_p6013_b8192_ub4096_moe12288.*`,
`b_layermono_overlap_p6013_b8192_ub4096.*`,
`b_layerdma_sync_p6013_b8192_ub4096.*`,
`b_layerdma_sync_barrier_p6013_b8192_ub4096.*`.

## Audit trasversale prefill/decode

Audit read-only completato; nessuna build o run aggiuntiva.

Contratto comune:

- backing mmap/pageable -> ring pinned piccolo -> slab VRAM;
- ownership per generazione e parita';
- eventi distinti upload-ready/compute-done;
- fallimento fail-closed e drain prima del riuso;
- descrittori comuni, ma layout/policy differenti per risorsa e fase.

Tree corrente: solo staging `layer_major` sincrono sul compute stream. Nessun
percorso overlap/DMA del prototipo rimosso e' raggiungibile.

Prefill promosso come prossimo cancello architetturale:

- macro-window HC residente da 12.288 token (768 MiB F32);
- attenzione tile 4.096;
- FFN grouped expert-major 12.288;
- ring pinned reale, slab VRAM, grafi/buffer persistenti;
- fixture 20,7k: promozione a totale <=50 s; 500 t/s a <=41,4 s.

Decode target, stima corretta:

| copertura miss | solo DMA nascosto | miss trasformato in costo-hit (ottimistico) |
|---:|---:|---:|
| 59% | 17,909 t/s | 18,321 t/s |
| 71% | 18,334 t/s | 18,857 t/s |
| 90% | 19,052 t/s | 19,773 t/s |
| 95% | 19,250 t/s | 20,030 t/s |
| 100% | 19,453 t/s | 20,293 t/s |

Il solo DMA non raggiunge 20: servono almeno altri 1,407 ms/token. La banca
transiente B deve restare separata da MASSA2 A, senza ammissione/sfratto/LRU.

Primo cancello decode: `LLAMA_DSPARK_ROUTE_PROBE=1`, osservativo. Forme
compatibili: DSpark result norm `[4096,n]`, router target `[4096,256]`.
Misurare recall top-6 specifico sui miss A, unici/layer, byte, lead e overhead;
promuovere solo da 70% recall sui miss. Fallback: predictor intra-target
esistente, storico circa 71% top-6. I primi tre layer hash vanno derivati
esattamente dal token id.

Lifecycle DSpark: encoder e KV inject sono attivi nel prefill; solo il decoder
MoE puo' essere lazy/file-backed fino a `DONE_PROMPT -> GENERATING`. Le 12 slot
draft (circa 104 MiB, riuso quasi nullo) sono candidate, in una leva separata,
a slab rotante per gli esperti CPU dei blocchi 1/2.

## UB larga e Flash Attention: localizzato il lavoro inutile

Fixture llama-bench p6.013, B8192, packetizer 0:

| configurazione | t/s | FNV | verdetto |
|---|---:|---|---|
| A, UB6.013, FA normale | 199,6707 | `F38F5B791AE1047B` | controllo |
| B, Q tile4.096 r1 | 198,2160 | uguale | neutro |
| B, Q tile4.096 r2 | 198,4361 | uguale | neutro |
| B, Q tile4.096 r3 | 197,8819 | uguale | neutro |

Media B 198,1780, -0,75%. La UB6.013 senza patch resta comunque +6,2%
rispetto alla base UB4.096 da 187,9865 t/s.

Cancello server 20.728 token, UB12.288, packetizer30, Nsight:

| configurazione | prefill | FA totale | output |
|---|---:|---:|---|
| A profilato | 123,2542 t/s | 65,6200 s | `<` |
| B Q tile4.096 | 122,4207 t/s | 65,9476 s | `<` |

Il B ha prodotto davvero 215 lanci q4.096 + 43 code q248, ma non ha ridotto
FA. Verdetto -0,68%, nessuna replica.

Spiegazione dal codice: `deepseek4.cpp` concatena lungo le chiavi
`raw_k || csa/hca_k`; la maschera contiene quindi blocchi raw futuri `-inf`
prima di blocchi compressi ancora validi. `fattn-common.cuh` calcola al piu'
un `KV_max` di coda e non rappresenta buchi interni. Due sonde di correzione
sono state fermate sul cancello corto:

- prefisso ingenuo di K/V: 115,6021 t/s, FNV `9A63E7340709D5C5`, errato;
- `raw_prefix || compressed_full` ricomposto per tile: 92,9294 t/s, FNV
  `B873872E05D0C497`, troppo costoso e non bit-esatto.

Entrambe rimosse; `src/llama-graph.cpp` e' tornato identico al commit runtime.
La leva macro promossa ad audit e' un iteratore/descrittore block-sparse dentro
Flash Attention: scansione per blocchi della maschera e salto di ogni blocco
tutto `-inf`, senza materializzare K/V. Il tetto empirico da inseguire e'
65,62 -> 34,27 s di FA sul profilo 20,7k.

## Maschere F16 input: micro-B rimosso

| banco | repliche | media | delta | verdetto |
|---|---|---:|---:|---|
| corto UB6.013 | 198,8096 / 199,1358 / 197,7506 | 198,5653 | -0,55% | neutro |
| macro UB12.288 | 123,8118 / 123,8210 / 123,9686 | 123,8671 | +0,50% | pagliuzza |

FNV/top-8 e output corretti. Patch rimossa; nessun residuo runtime.

## Decode: final hidden DSpark non predice i router target

`diag_dspark_route_probe_mass2_t473_d12_r3`: 486/486 cicli, invalidi 0,
102.249 miss A, 5.198 richiamati = **5,1% recall**. Throughput 16,04, p1
0,90025, 47.906 copie, stesso output/SHA della base. Verdetto: bocciato senza
repliche. Il probe era osservativo e viene rimosso dal runtime.

Prossimo B decode: `LLAMA_CACHE_ESPERTI_BANCA_B=1`, predictor intra-target
storico circa 71%, banca ping-pong separata 2x6 slot = 81 MiB. B non ammette e
non sfratta: una domanda vera conserva la stessa vittima A e cambia soltanto la
sorgente da mapped-host a B->A. Tetto stimato 18,33-18,86 t/s.

Seconda trave decode separata: `LLAMA_DSPARK_STAGE_CPU_EXPERTS=1`, slab draft
104,263 MiB riusata per blk.1/2, backing pageable `CUDA0_Staged` e ring pinned
17,377 MiB. Non combinarla col primo B.

## Flash Attention block-sparse: +53,95%

Fixture UB6.013: **289,1010 t/s**, FNV `F38F5B791AE1047B` e top-8 identici;
A densa 199,6707.

Macro 20.728 token, UB12.288, packetizer30, tutti profilati Nsight:

| replica | t/s | FA | scan bitmap | output |
|---|---:|---:|---:|---|
| B1 | 190,3274 | 6,8555 s | 0,0720 s | `<`, length |
| B2 | 191,6210 | 6,8512 s | 0,0720 s | `<`, length |
| B3 | 187,2925 | 6,8522 s | 0,0720 s | `<`, length |

Media **189,7469 t/s**, spread 2,28%, +53,95% su A 123,2542. FA scende da
65,6200 a circa 6,8530 s (-89,6%). Commit runtime `3014d3756`, cinque soli
file Flash Attention, nessun push.

Nuovo collo macro: `mul_mat_q` type16 34,711 s, type10 23,673 s, type8
5,759 s; lightning indexer 4,805 s. Prossimo lavoro prefill: residenza virtuale
e overlap/scheduling dei pesi routed, obiettivo ancora 500/1000 t/s.

## Nuova base prefill: block-sparse + layer staging

Unico B aggiuntivo `LLAMA_DSV4_PREFILL_LAYER_STAGING=1`:

| replica | t/s | prompt ms | output |
|---|---:|---:|---|
| B1 | 271,4432 | 76.362,191 | `<`, length |
| B2 | 275,4867 | 75.241,384 | `<`, length |
| B3 | 279,5895 | 74.137,264 | `<`, length |

Media **275,5065 t/s**, spread 2,96%, +45,20% sulla base block-sparse e
+123,53% sul vecchio A. Il profilo B1 porta routed MMQ da 58,384 a 18,135 s
e aggiunge 5,979 s di `kern_layer_major_copia`; FA resta 6,917 s.

Distanza da 500: 224,4935 t/s, fattore 1,815, +81,48%. Il tempo deve scendere
da 75,236 a 41,456 s (-33,780). La sola copia/overlap non basta: prossimo B
`LLAMA_DSV4_PREFILL_FFN_SUPEROP=1`, tail completo routed+shared+add+HC-post,
cancello iniziale <=50 s / >=414 t/s e correttezza completa.
