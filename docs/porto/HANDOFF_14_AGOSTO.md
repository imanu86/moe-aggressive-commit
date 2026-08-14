# HANDOFF — 14 agosto 2026

Questo file continua `HANDOFF_13_AGOSTO.md`. Non sostituisce log e codice:
per ogni numero, la fonte autoritativa resta l'artifact del relativo braccio.

## 1. Obiettivo e metodo

Obiettivo ancora aperto: **20 token/s sul banco DS4 + DSpark Porto**, con
correttezza semantica verificata.

Regole operative richieste dall'utente:

- un solo B per leva; niente sequenze ABBA o sweep senza una domanda precisa;
- se B e' chiaramente peggiore, si scarta e si torna al codice;
- se il risultato cade entro circa il 4% della base, si eseguono tre run
  identici totali e si usa la media;
- SHA uguale non basta: controllare coerenza, completezza, finish reason,
  acceptance e contatori; un cambio CPU/GPU puo' cambiare SHA legittimamente;
- evitare polling del disco mentre vengono letti gli oltre 80 GiB di modello;
- Ledger e Handoff vanno aggiornati e il lavoro va committato per scope, senza
  includere modifiche estranee e senza push.

## 2. Banco corto e nuova base

Runner storico:

```text
C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\dopo_il_riavvio.ps1
```

Binario e modelli:

```text
D:\llama-overlap\build\bin\llama-server.exe
C:\ds4-models\DS4-0731-IQ2XXS.gguf
D:\ds4-models\DSpark-draft-Q2K.gguf
```

La base corta corrente usa target/draft `473/12`, `FORK=2`, `BLOCCHI=8`,
CPU `K=2`, `ctx=10000`, `ub=64`, `t=7`, modello target IQ2_XXS e draft Q2_K.
Le aggiunte esatte al blocco comune sono:

```text
LLAMA_CACHE_BOZZA_SLOT=12
PORTO_SPEC_NMAX=2
PORTO_SPEC_CONF_MIN=0.8
LLAMA_OVERLAP_BATCH_MAX=3
LLAMA_SPEC_CONF_ESENTA_POS0=1
LLAMA_ACCEPTMOE=1
LLAMA_ACCEPTMOE_ESATTE=1
LLAMA_ACCEPTMOE_SOGLIA=0.75
LLAMA_ACCEPTMOE_COMPATTA=1
LLAMA_GRAPH_REUSE_PER_TAGLIA=1
LLAMA_CACHE_ESPERTI_MASSA=2
LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE=0
LLAMA_CACHE_ESPERTI_MASSA_CORSIE=0
```

Tre repliche della nuova base:

| tag | t/s | p1 | SHA output |
|---|---:|---:|---|
| `mass2_copyall_stablelane_t473_d12_b1` | 16,04 | 0,90025 | `4FDCFADF...` |
| `mass2_copyall_stablelane_t473_d12_b2` | 16,11 | 0,90025 | `4FDCFADF...` |
| `mass2_copyall_stablelane_t473_d12_b3` | 16,07 | 0,90025 | `4FDCFADF...` |

**Media 16,0733 t/s**, range 0,44%. E' il riferimento da battere.

Contatori identici nelle tre corse:

```text
domanda target 216.737
hit 168.831 = 77,9%
miss/copie 47.906 = 22,1%
partizioni 55.169
CPU 110.338
zero-copy 0
```

La base precedente NMAX2/AcceptMoE senza MASSA2 era 15,87/15,85, media 15,86,
con 60.951 miss e 401,98 GiB copiati. La politica globale ha quindi prodotto
un guadagno reale di circa **+0,21 t/s / +1,35%**.

## 3. Politica globale implementata

La politica `MASSA=2` mantiene massa decaduta per `(strato, esperto)`, con
emivita 64 cicli, unita' 4, floor 3 e margine vittima 2. La vittima e' la
massa minima globale; LRU e' solo spareggio. Le colonne AcceptMoE compattate
con peso zero non alimentano la massa.

Sono state separate due decisioni che all'inizio erano accoppiate:

- `LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE`: ammettere o mandare in zero-copy;
- `LLAMA_CACHE_ESPERTI_MASSA_CORSIE`: riordinare le corsie CPU/GPU per massa.

Il risultato vincente tiene `AMMISSIONE=0` e `CORSIE=0`: **la massa governa
la residenza/sfratto, ma non cambia le corsie e non introduce la terza passata
zero-copy**. Le versioni piu' aggressive hanno aumentato hit ma peggiorato il
cammino critico.

File toccati nel runtime:

```text
D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cu
D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cuh
D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu
```

Il worktree era gia' molto sporco prima di questi cambi. Non fare `git add -A`.
Le modifiche di questa fase non risultano ancora consolidate in un commit
circoscritto: ispezionare diff e provenienza hunk per hunk.

## 4. Bracci chiusi dopo la nuova base

| leva | run | risultato | verdetto |
|---|---|---:|---|
| `SPIN=0` sulla base vecchia | 15,89 / 15,69 / 15,93 | media 15,84 | neutra |
| MASSA2 + ammissione/zero-copy | `mass2_lanecold...` | 15,08 | regressione |
| MASSA2 copy-all + corsie per massa | 15,62 / 15,61 / 15,35 | media 15,53 | regressione |
| nuova base, corsie stabili | 16,04 / 16,11 / 16,07 | media 16,0733 | promossa |
| `FORK_RIUSA_SLOT=1` | 15,84 / 15,71 / 15,73 | media 15,76 | bocciata |
| `FORK_SALTA_COPIA_PARITA=1` | 15,37055 | singolo B | bocciata, non replicare |

`FORK_RIUSA_SLOT` dimostra che i kernel apparentemente ridondanti lasciavano
in realta' distanza utile alla copia asincrona: rimuoverli trasferisce il tempo
al join. `SALTA_COPIA_PARITA` conserva `kern_decidi` ma elimina le due griglie
di copia vuote; anche questa riduzione peggiora nettamente il risultato.

Artifact dell'ultimo B, prodotto durante il cambio di permessi della task:

```text
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\mass2_stable_nocopypar_t473_d12_b1.*
```

Il run ha mantenuto `p1=0,90025` e `713/792` token draft accettati. L'output
corto e' identico byte per byte ai tre run base (`SHA256
4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D`). La
perdita e' `-4,37%` dalla media 16,0733: regressione prestazionale pura, non una
traiettoria diversa.

## 5. Qualita' dell'output

La vecchia base NMAX2 e' stata validata con il prompt NeuraForge fino a stop
naturale:

```text
ctx 8192
prompt 74 token
completion 6.147 token
totale 6.221
finish_reason stop
15,91 t/s
```

L'output e' un HTML/CSS/JS completo e coerente; sono stati controllati anche
rendering nel browser e comportamento del form. I run corti da 1.200 token
sono coerenti ma si interrompono a meta' CSS e non bastano da soli come prova
di completezza.

Artifact:

```text
D:\ds4_work\llama_run\neuraforge_b2_ctx8192_full.*
```

## 6. Run reale a contesto lungo

Obiettivo del test: `-c 150000`, prompt non ripetitivo gia' vicino a 101k,
attraversamento dei gradini CSA/LID fra 101k e 103k, nuova base 16,07 e fasi
prefill/decode separate.

Il primo tentativo con `LLAMA_VRAM_A_FASI=1` ha lasciato la slab esperti in
VRAM ed e' andato OOM al token di prompt 7.169 durante una crescita VMM.

La configurazione corretta usa:

```text
LLAMA_VRAM_A_FASI=2
LLAMA_VRAM_A_FASI_UB=64
LLAMA_KV_RING=1
LLAMA_KV_RING_VRAM_TOKEN=2048
LLAMA_DSV4_INDEXER_FUSO=1
LLAMA_DSV4_HC_FUSO=5
-c 150000        # effettivo 150016
-b 1024 -ub 1024
--no-host
--cache-ram 0
```

Risultato `ctx150k_mass2_stable_f2_b1024`:

```text
prompt 101.676 token
completion 2.048 token
totale 103.724 token
finish_reason length
prefill 92,30 t/s
decode 9,69 t/s medio sui 2.048 token
p1 0,76501
SHA output 26D998D35538EB96ACF23F7724EE8122550568E8C20EE6E307C54F4617544225
```

Transizione VRAM riuscita:

```text
prefill: cache target 473 -> 0, -3.194 MiB, VRAM libera 3.353 MiB
workspace decode -> prefill: 136,70 -> 1.144,24 MiB
decode: cache target 0 -> 473, +3.194 MiB
workspace prefill -> decode: 1.144,24 -> 136,70 MiB
```

Il run ha attraversato `102404` e `103000` assoluti. Intorno a 102404 il
decode cumulativo era circa 10,1 t/s; a fine corsa 9,69. Nessun errore CUDA,
OOM o divergenza replay.

L'output contiene 4.267 caratteri di reasoning e 2.700 di risposta tecnica,
entrambi coerenti. E' incompleto perche' il compito chiedeva 20 sezioni e il
limite 2.048 e' stato raggiunto; non mostra degenerazione o ripetizione.

Artifact:

```text
D:\ds4_work\llama_run\ctx150k_mass2_stable_f2_b1024.*
```

## 7. Prefill: inventario e direzione

Il run lungo dimostra che 150k funziona, ma 92,3 t/s significa circa 18 minuti
per 101k token. Il nuovo obiettivo parallelo e' un prefill dell'ordine di
centinaia fino a circa 1.000 t/s.

Collocazione pesi target misurata dal GGUF e dal log:

| famiglia | collocazione | MiB |
|---|---|---:|
| attention | CUDA0 | 4.660,125 |
| shared expert | CUDA0 | 1.096,500 |
| compressori + indexer | CUDA0 | 929,295 |
| output + norm | CUDA0 | 536,578 |
| altri densi | CUDA0 | circa 161 |
| totale densi target | CUDA0 | 7.383,67 |
| embedding F16 | CUDA_Host | 1.010 |
| routed experts | CUDA0_Mapped | 74.304 |

DSpark resta caricato durante il prefill anche se non viene usato:

```text
CPU model       4.458,36 MiB
CUDA0_Mapped    2.224,00 MiB
CUDA0              159,49 MiB
```

Il primo guadagno phase-aware e' quindi differire il caricamento del drafter
fino al decode.

I buffer che crescono davvero con UB e contesto sono:

- maschere CSA/LID/HCA;
- `indexer_score`;
- Q/output della Flash Attention;
- intermedi MoE;
- fallback top-k/argsort, che mantiene tre piani pieni nel CUDA pool.

KV ring e cache esperti non crescono con UB. A UB4096, il fallback top-k puo'
richiedere circa 1,72 GiB oltre allo score e al workspace.

Ordine raccomandato:

1. Provare `UB=2048` con `FASI=2`, `INDEXER_FUSO=1`, `HC_FUSO=5`, senza nuovo
   codice, per misurare la curva reale.
2. Produrre CSA/HCA direttamente in F16/descrittore compatto e fare top-k a
   chunk con ausiliari limitati.
3. Alla transizione, sincronizzare e liberare insieme CUDA graph e pool VMM;
   il pool corrente mantiene l'high-water anche dopo `free()`.
4. Per UB4096+, fondere/tile-izzare indexer + top-k senza score pieno.
5. Solo se serve ancora VRAM, rendere phase-aware i densi: backing pageable o
   mmap, piccolo doppio staging VRAM per layer, reload bulk prima del decode.

Non aggiungere altro `CUDA0_Mapped`: sono gia' pinnati almeno 76,3 GiB e il
limite osservato e' vicino. Attention + shared + compressori con staging
layer-major libererebbero circa 6,345 GiB netti; includendo output si arriva a
circa 6,7 GiB. Il traffico aggiunto e' 6,53 GiB per passata, circa il 9% dei
72,56 GiB degli esperti. A UB4096 sono circa 18,5-23,6 s totali su 150k senza
overlap: il compromesso e' promettente, ma PCIe e zero-copy condividono il
collo di bottiglia.

Il ring di attivazioni e' un abilitatore, non l'acceleratore principale. Il
moltiplicatore deve venire da grouped/batched MoE: con 256 esperti e top-6,
ogni esperto riceve in media circa 24 righe a UB1024, 96 a UB4096 e 192 a
UB8192.

## 8. Fixture KV per non rifare il prefill

Lo state DSV4 FULL serializza gia':

- raw/SWA, posizioni e seq-id;
- cold CSA/HCA/LID;
- anelli `kv` e `score` dei tre compressori;
- il backing cold del KV ring; l'hot VRAM viene ricostruito con
  `sync_ring_hot()`.

Il difetto e' nell'involucro server: `/slots` salva solo `ctx_tgt`, non
`ctx_dft`. La prompt cache RAM salva entrambi ma non e' persistente e a 150k
rischia il paging.

Patch minima raccomandata in `tools/server/server-context.cpp`:

```text
fixture.tgt.bin
fixture.dft.bin
fixture.json
```

Il manifest deve contenere hash dei due GGUF, token base, n_ctx, layout KV,
rapporti CSA/HCA/LID, rope/compressione e versioni ABI dello state. In restore,
target e draft sono entrambi obbligatori; su errore si puliscono context,
token, checkpoint e speculative state.

Cancello prima corto: fixture 6,5k, suffix token-array esplicito, 200 token di
output; fresh e restore devono coincidere token per token e il prompt eval
dopo restore deve essere soltanto il suffix. Poi costruire una sola fixture a
100.992 token (multiplo di 128) e riusarla nei test decode lunghi.

Non usare `/v1/chat/completions` per l'estensione della fixture: il template
sposta i token di chiusura. Usare `/completion` con array token esplicito.

## 9. Prossime leve decode, in ordine

1. **MASSA2 + `FORK_BLOCCHI=4`**, singolo B. Il vecchio B4 era pessimo con
   MASSA0, miss circa 48% e solo 5% copie finite; oggi i miss sono 22,1% e il
   47,4% delle copie e' gia' finito al join. E' un regime diverso e il retune
   non e' falsificato.
2. **ILP di `kern_fj_copia`**, leva default-off
   `LLAMA_CACHE_ESPERTI_FORK_COPIA_ILP=4`, lasciando BLOCCHI=8. Il riferimento
   ha copia media 0,794 ms e 52,6% join ancora in corso; per meritare il banco
   deve scendere circa a 0,752 ms o aumentare chiaramente la copertura.
3. **MMVQ masked IQ2_XXS rows-per-block=4** soltanto nelle passate mancanti.
   Oggi il clone usa 2 senza tuning dedicato; RPB4 dimezza `grid.x` e i blocchi
   che escono dopo aver letto la maschera.
4. **Fusione gate/up mancanti**: condividere quantizzazione Q8, maschera e
   attivazione; piu' complessa, da affrontare solo dopo le leve isolate.

Cancello di promozione per una micro-ottimizzazione: output/acceptance
corretti e almeno circa **16,17 t/s** per un +0,1 reale; se il primo B cade
entro la varianza, completare tre repliche identiche.

## 10. Ricerca esterna

Tenere controllati repo ufficiali, fork llama.cpp, DwarfStar/DSpark e ricerche
GitHub mirate prima di inventare componenti grandi. Il nuovo repo ufficiale
`deepseek-ai/deepseek-harness` e' stato esaminato: e' un harness agent/plugin
in developer preview, non un runtime di inferenza, quindi non offre oggi una
soluzione diretta a trasporto, cache o prefill; resta da monitorare.

## 11. Ripresa immediata

1. Leggere questo file, `HANDOFF_13_AGOSTO.md`, `LEDGER_14_AGOSTO.md`, poi
   verificare codice/log correnti.
2. Il B `FORK_SALTA_COPIA_PARITA=1` e' registrato e chiuso a 15,37055.
3. Eseguire un solo B `MASSA2 + FORK_BLOCCHI=4` sulla base 16,0733.
4. Se chiaramente peggiore, niente repliche: tornare al codice e implementare
   ILP4 default-off.
5. In parallelo, progettare prima la fixture target+draft; evita 20 minuti di
   prefill per ogni futuro test decode lungo.
6. Prima del commit, separare rigorosamente gli hunk della sessione dalle
   modifiche pregresse del worktree.

## 12. Aggiornamento: staging bulk e prototipo layer-major

La direzione proposta dall'utente, "leggere i pesi una volta e farli bastare
per tutto il prompt", e' stata implementata in due passi distinti.

### 12.1 Staging bulk promosso

`LLAMA_DSV4_PREFILL_LAYER_STAGING=1` copia in VRAM l'intera banca dei 256
esperti di un layer (circa 1.729 MiB) e riusa lo slab compatto per tutti i
matmul di quel layer. Sulla fixture reale da 6.510 token, il server ha ancora
spezzato il prompt in 2.598 + 4.096 token: non e' quindi ancora l'inversione
completa dei cicli, ma elimina le letture sparse zero-copy all'interno di ogni
chunk.

| braccio | t/s | verdetto |
|---|---:|---|
| A standard | 162,6134 | riferimento fixture |
| B staging bulk 1 | 196,0796 | positivo |
| B staging bulk 2 | 195,9432 | replica |
| B staging bulk 3 | 194,8275 | replica |

Media B **195,6168 t/s**, **+20,30%**, con lo stesso SHA output
`C526531F...` e stesso contenuto. Questo e' il primo salto architetturale
promosso; la leva resta default-off finche' non viene integrata e verificata
sul percorso lungo.

Artifact:

- `a_layer_major_fixture6510_b8192_ub4096.*`;
- `b_layer_major_fixture6510_b8192_ub4096.*`;
- `b_layer_major_fixture6510_b8192_ub4096_r2.*`;
- `b_layer_major_fixture6510_b8192_ub4096_r3.*`.

### 12.2 Inversione vera dei cicli: corretta, ma meccanicamente lenta

E' stato aggiunto un esecutore sperimentale separato,
`LLAMA_DSV4_PREFILL_LAYER_EXECUTOR=1`, che fa davvero:

```text
for layer:
    stage una volta la banca esperti
    for tile del prompt:
        esegui un solo layer
```

Il prototipo porta il residuo HC completo in un backing host pageable e
rewind/replay delle viste KV DSV4 tra i layer. I primi crash hanno isolato due
requisiti corretti nel codice definitivo del prototipo: conservare i token ID
fino agli hash layer e non registrare l'input token dopo l'ultimo hash layer.
Il percorso completa tutti i 43 layer senza errori.

Braccio singolo sintetico da 6.013 token, una sola `llama_decode`:

| braccio | t/s | tempo | verdetto |
|---|---:|---:|---|
| A normale | 192,1177 | 31,299 s | riferimento |
| B layer-major vero | 139,6749 | 43,050 s | -27,3%, bocciato |

Artifact: `a_layer_major_single_decode_p6013_b8192_ub4096.*` e
`b_layer_major_single_decode_p6013_b8192_ub4096.*`.

Tre tentativi di recupero sono stati falsificati e rimossi dal codice:

- residuo host pinned: 140,4588 t/s, solo +0,56% sul B rotto;
- CUDA Graph sul grafo frammentato a p20k: 150,6279 contro 151,5333 t/s;
- copia D2H asincrona a p20k: 137,1090 t/s, -9,5%.

Artifact: `b_layer_major_pinned_single_decode_p6013_b8192_ub4096.*`,
`a_layer_major_nographs_single_decode_p20000_b32768_ub4096.*`,
`b_layer_major_graphs_single_decode_p20000_b32768_ub4096.*`,
`b_layer_major_asyncout_single_decode_p20000_b32768_ub4096.*`.

### 12.3 Profilo che decide il prossimo disegno

`DSPARK_PROF=1` su p4.100, due tile e 43 layer, misura 86 chiamate al grafo:

```text
build       34,9 ms
alloc    7.655,6 ms
input    2.269,9 ms
compute 20.736,8 ms
```

Artifact: `diag_layer_major_dsprof_single_decode_p4100_b8192_ub4096.*`.

Il collo non e' piu' la copia del residuo: sono `sched_reset/alloc` ripetuti e
la ricostruzione di input/maschere per ogni mini-grafo. Anche eliminando tutto
l'overhead non-compute, il frammento attuale avrebbe un tetto di circa 198
t/s su questa fixture: la sola inversione dei cicli non basta a 500 t/s.

Il prossimo braccio grande deve quindi essere un **supergrafo per layer**:
tutte le tile del prompt nello stesso grafo, pesi condivisi e una sola
`graph_compute`/allocazione per layer. In alternativa, una cache persistente
di grafi gia' allocati per coppia layer/taglia, ma il supergrafo e' preferibile
perche' riduce anche il costo di input. Le maschere CSA/HCA/LID devono poi
diventare descrittori o essere preparate una volta per tile, non rimaterializzate
43 volte.

Stato delle leve dopo la pulizia:

- `LLAMA_DSV4_PREFILL_LAYER_STAGING`: mantenuta, positiva;
- `LLAMA_DSV4_PREFILL_LAYER_EXECUTOR`: mantenuta solo come scaffold
  sperimentale e strumento di verifica, default-off;
- pinned, async output e compatibilita' CUDA Graph: rimossi dopo i B negativi.

## 13. Aggiornamento pomeriggio: split di fase, barriera e trasporto reale

Il grafo DSV4 layer-major e' stato separato, default-off, in tre forme:

- parte 0: layer completo;
- parte 1: sola attenzione/stato;
- parte 2: solo FFN/MoE.

La prima versione produceva NaN o divergenze non per il calcolo FFN, ma per
una dipendenza asincrona nascosta: CSA/HCA/LID e le cache DSV4 hanno scritture
laterali che non sono tutte antenate del residuo esportato. Una
`tensor_get(residuo)` non garantisce che tali rami siano terminati. La barriera
conservativa `ggml_backend_sched_synchronize()` dopo ogni grafo layer-major ha
reso la fixture p4.100 bit-exact:

| run | t/s | FNV logits | top-8 |
|---|---:|---|---|
| riferimento normale | 196,7489 | `FD9308B918867FCA` | riferimento |
| split attn+FFN, UB4096/4096 | 91,3621 | `FD9308B918867FCA` | identico |

Artifact: `diag_layersplit_reference_p4100_b8192_ub4096.*` e
`diag_layersplit_sync_p4100_b8192_ub4096.*`.

Il packetizer scheduler deve restare spento sul grafo ridotto: con
`GGML_SCHED_OFFLOAD_PACCHETTI=1` le branche FFN ridotte non sono affidabili;
con 0 il confronto del primo stadio FFN era bit-exact.

Il singolo B macro-MoE (attenzione UB4096, FFN 6.013 token) e' stato
chiaramente negativo: **82,742 t/s** contro A corrente **187,9865 t/s**
(-56,0%), finito e stesso top-1 ma numerica diversa. Nessuna replica.
Artifact: `b_layersplit_sync_p6013_b8192_ub4096_moe12288.*` e
`a_current_packet0_p6013_b8192_ub4096.*`.

### 13.1 Perche' il primo overlap "alla DwarfStar" non valeva

E' stato provato un mono-slab: upload del layer L su stream separato mentre
l'attenzione L gira sullo stream di calcolo. Il primo tentativo usava ancora
`kern_layer_major_copia`, cioe' un kernel che legge `CUDA0_Mapped`: occupava
gli stessi SM dell'attenzione. Ha ingaggiato 42/43 layer e fatto 145,001 t/s,
ma con NaN nei logits; e' una sonda invalida, non evidenza prestazionale.

Il secondo tentativo ha trasformato lo slab in SoA contiguo e usato tre
`cudaMemcpyAsync`. Senza la barriera laterale ha riprodotto lo stesso identico
FNV corrotto. Con la barriera e' finito senza NaN, stesso top-1, ma ha fatto
solo **127,4757 t/s**, -32,2% contro la base corrente; nessuna replica.

Artifact:

- `b_layermono_overlap_p6013_b8192_ub4096.*` (invalido, NaN);
- `b_layerdma_sync_p6013_b8192_ub4096.*` (invalido, NaN);
- `b_layerdma_sync_barrier_p6013_b8192_ub4096.*` (finito, 127,4757 t/s).

Il ramo overlap/SoA-DMA e' stato rimosso; resta la barriera di correttezza nel
solo scaffold layer-major. La lezione trasversale e' importante: un puntatore
UVA di `CUDA0_Mapped` non equivale al pinned-host staging di DwarfStar e
`cudaMemcpyDefault` non garantisce automaticamente un percorso H2D economico
su copy engine. Per simulare residenza serve distinguere esplicitamente:

1. backing pageable/mmap;
2. ring pinned posseduto da eventi;
3. staging VRAM;
4. stream di upload e wait su ogni stream consumatore;
5. side-effect fence del modello, separata dalla disponibilita' dei pesi.

Questa conoscenza e' riutilizzabile nel decode per esperti target, DSpark,
densi e KV, ma la policy cambia: layer noto/full bank nel prefill; route
selettive previste da router/drafter nel decode.

### 13.2 Ripresa aggiornata

1. Non ripetere macro-MoE, mono-slab kernel o SoA-DMA diretto da UVA.
2. Prima di un altro full-model B, dimostrare con profilo che il trasporto usa
   davvero il copy engine: mmap/pageable -> piccolo ring pinned -> VRAM.
3. Sul prefill, eliminare il costo strutturale del driver: supergrafo per layer
   o tile pipeline persistente, non un altro aumento UB.
4. Tre audit decode read-only sono in corso: cache esperti selettiva,
   lifecycle/residenza DSpark, motore comune di VRAM virtuale.
5. Il decode resta alla base autorevole 16,0733 t/s finche' un singolo braccio
   macro non supera correttezza e throughput.

## 14. Audit parallelo: motore comune e policy decode

Tre audit read-only sul tree e sui log correnti hanno convergito sullo stesso
contratto di residenza virtuale:

1. backing pageable/mmap;
2. ring pinned piccolo e fisso;
3. slab VRAM posseduto dal motore;
4. stato per generazione `EMPTY/FILLING/READY/IN_USE`;
5. `upload_ready` e `compute_done` per ogni parita';
6. drain o seal fail-closed su resize, abort e rollback.

Nel tree corrente non esiste alcun overlap layer-major attivo: resta solo
`ggml_cuda_cache_esperti_layer_major`, chiamato da `ggml-cuda.cu`, con la
copia accodata sul medesimo compute stream. Il vecchio simbolo `layer_stage`
apparteneva a un prototipo transitorio gia' rimosso.

### 14.1 Prefill: macro-window residente, non prompt intero

La hidden HC DSV4 F32 occupa 768 MiB per 12.288 token e circa 9,155 GiB per
150k token. Il disegno attuabile sul banco Porto e' quindi una macro-window:

- hidden HC 12.288 residente in VRAM;
- attenzione fisica in tile da 4.096;
- FFN grouped/expert-major sui 12.288 token;
- staging routed e denso del layer seguente con vero ring pinned/copy engine;
- buffer e grafo persistenti, senza roundtrip host del residuo e senza
  `sched_reset`/allocazione per tile.

Il cancello iniziale e' la fixture da circa 20,7k token. Un solo B viene
promosso se mantiene l'output coerente, porta alloc+input sotto 1 s, routed
MoE sotto 25 s, Flash Attention sotto 36 s e totale sotto 50 s (circa
414 t/s). 500 t/s richiede non oltre 41,4 s; 1000 t/s non oltre 20,7 s.

### 14.2 Decode target: cache A stabile piu' banca B transiente

MASSA2 resta la cache persistente A. Le route previste devono alimentare una
banca B ping-pong separata, con tag `(epoch, layer, expert, slot)`:

- prima si filtrano gli hit gia' presenti in A;
- B non ammette, non sfratta e non aggiorna LRU/massa di A;
- il consumer risolve tre origini disgiunte: hit A, hit B pronto, miss base;
- una previsione errata o tardiva decade nel percorso base e non puo' cambiare
  l'output.

Base: 62,214 ms/token; 39,9217 copie/token; 6,75 MiB per esperto; banda
24,35 GiB/s. Il solo trasporto fisico vale circa 10,807 ms/token. Nasconderlo
al 100% porta al massimo conservativo di 19,453 t/s, non a 20. Per superare
20 servono anche almeno 1,407 ms/token di gestione miss/sincronizzazioni, o
una copertura intorno al 95% che trasformi davvero i miss in costo-hit.

Primo cancello decode, prima di implementare B:
`LLAMA_DSPARK_ROUTE_PROBE=1`, solo osservativo. Il final hidden DSpark e i
router target sono dimensionalmente compatibili (`4096 -> 256`), ma la
compatibilita' semantica va misurata. Il probe deve riportare recall top-6 sui
miss A, unici non residenti/layer, byte/ciclo, lead e overhead, senza copie o
mutazioni cache. Promozione con recall sui miss almeno 70%, preferibilmente
80%+, e non oltre 8 esperti/layer. Se fallisce, il fallback e' il predictor
intra-target gia' presente in `deepseek4.cpp`, con recall storico circa 71%.

### 14.3 DSpark durante il prefill e nel decode

DSpark non e' completamente inutilizzato nel prefill. Per ogni ubatch target,
`common_speculative_process` raccoglie i tap 41/42/43, esegue l'encoder draft
e inietta il KV. Questo percorso usa encoder, `wkv`, norm e KV, ma non il
decoder MoE completo. Caricare tutto solo al decode richiederebbe conservare o
rigiocare circa 4,654 GiB di tap su un prompt da 101.676 token.

La separazione corretta e': seed/KV residenti nel prefill; pesi esclusivamente
decode file-backed/lazy; attivazione alla transizione
`DONE_PROMPT -> GENERATING` (Porto `np=1`). Le 12 slot draft occupano circa
104 MiB e hanno riuso quasi nullo: in una leva separata possono diventare slab
rotante per gli esperti CPU dei blocchi DSpark 1/2. Non combinarla con il
primo probe route, cosi' ogni verdetto resta interpretabile.
