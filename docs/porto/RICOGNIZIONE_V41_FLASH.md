# Ricognizione DeepSeek-V4.1-Flash — 10/9/2026

**Stato: solo metadati.** Nessun peso scaricato (ordine utente: «per ora non scarichiamo nulla, voglio capire
come farlo girare»). Letti: `config.json`, `model.safetensors.index.json`, gli header dei 48 safetensors via
richieste a range (`huggingface_hub.get_safetensors_metadata`), le card dei derivati, la PR llama.cpp.
Script riproducibili in `docs/porto/v41_flash/` (vedi §7).

## 1. La release

- `deepseek-ai/DeepSeek-V4.1-Flash`, HF 10/9 02:17 UTC, MIT, non gated, sha `dba1be0a40aa45a94ad051997016db3960a90277`.
- 48 shard, **510.286.023.000 B = 475,24 GiB**, 96.085 tensori. Gli shard 47 e 48 (94,56 GiB l'uno) sono le due
  tabelle Engram.
- Parametri (API HF): I8 557,17B (esperti FP4 logici) · F8_E4M3 204,02B · BF16 1,98B · F32 0,04B = **763,2B**.
  La card dice «552B backbone» (esperti + denso) + «Engram 196B».

## 2. Architettura — NON e' la sagoma V4

| | V4-Flash / Vision-Exp (servito) | **V4.1-Flash** |
|---|---|---|
| strati | 43 | **40 = encoder causale 20 + decoder 20 (CED)** |
| hidden | 4096 | **5120** |
| esperti instradati × attivi | 256 × 6 | **384 × 6** (+1 condiviso) |
| moe_inter | 2048 | **2304** |
| param per esperto | 25,2M | **35,4M** |
| attivi per token | 13B | **8B in prefill / 16B in decode** |
| KV globale | ~4× | **890 B/token** (FP4 E2M1) ⇒ 300k = 0,25 GiB |
| n-gram | — | **Engram, strati 1 e 14** |
| visione | torre 0,47B + `exp_probs_b_vl` | ViT 32×1024 + aligner 9216→5120, `ffn.gate.bias_vl` |
| bozza | DSpark (GGUF separato) | DSpark in `mtp.0-2`: 3 blocchi, 128 esperti top-3 |

- **CED**: il KV globale del decoder e' proiettato dagli stati finali dell'encoder ⇒ il **prefill passa solo
  dall'encoder**; SWA Bounded Replay ripassa nel decoder solo gli ultimi `n_win` = 128 token.
- **CSA2**: ogni strato di attenzione e' Full / Reindex / Reuse (KV e chiavi dell'indexer condivisi fra strati,
  `kv_source_layer_ids [2,8,14,20]`, `index_source_layer_ids [2,8,14,20,24,28,32,36]`), indexer gerarchico con
  pool di candidati dal primo strato Full del decoder (`candidate_topk_blocks 2048`, blocchi da 8).
- **Engram** (`inference/engram.py`): i token passano per una mappa compressa (129.280 → 99.092 id normalizzati),
  ogni posizione fa l'hash di 2/3/4-grammi × 8 teste = **24 righe per strato Engram, 48 per token**, ognuna in un
  intervallo di dimensione prima (~16M). Tabella `layers.N.engram.embed.weight` **[384.016.682, 256]** FP8 + scala
  `[righe, 8]` (una ogni 32 colonne); proiezione `wkv [25600, 6144]`, gate `q_weight/k_weight [4, 5120]`.
  **Gli indirizzi dipendono solo dagli ultimi 4 token** ⇒ sono noti all'istante del campionamento: prefetch
  ESATTO, a zero dipendenze (non e' il prefetch speculativo degli esperti, falsificato il 4/8).

### Composizione misurata dalle forme

| categoria | tensori | release GiB | parametri |
|---|---:|---:|---:|
| esperti instradati 40×384×3 (FP4 + E8M0) | 92.160 | 268,95 | 543,58B |
| tabelle Engram 2× (FP8 + scale) | 4 | 188,83 | 196,61B |
| esperti DSpark 3×128×3 | 2.304 | 6,72 | 13,59B |
| attenzione / indexer / compressore / hc / aligner | 891 | 5,08 | 5,24B |
| esperto condiviso | 240 | 1,32 | 1,42B |
| embed + head | 2 | 2,47 | 1,32B |
| torre visiva | 259 | 0,77 | 0,41B |
| resto DSpark, router, proiezioni Engram | 229 | 1,10 | 1,03B |

## 3. Pesi quantizzati — proiezione

Metodo: parametri logici per categoria (dalle forme vere) × bit/peso della ricetta del **nostro** GGUF
Vision-Exp letto con gguf-py (`gguf_ref_rows.json`: gate/up IQ2_XXS, down 23 strati IQ2_XS + 20 IQ3_XXS,
denso Q6_K, embed/head Q8_0, router BF16; totale 79,27 GiB a 2,394 bpw).

| pezzo | GiB |
|---|---:|
| esperti, ricetta Vision-Exp | 143,1 |
| esperti tutti IQ2_XXS | 130,5 |
| esperti tutti IQ2_XS | 146,3 |
| resto denso (Q6_K, embed/head Q8_0, router F16, proiezioni Engram Q8_0) | ~6,9 |
| **tronco IQ2** | **137-150** (Vision-Exp oggi: 79,3) |
| tabelle Engram Q8_0 / **Q6_K** / Q4_K / IQ2_XXS | 194,6 / **150,2** / 103,0 / 47,2 |
| mmproj F16 | 0,8 |
| bozza DSpark (esperti Q2_K + resto Q6_K) | ~4,6 |

**Validazione su un artefatto reale.** `apetersson/DeepSeek-V4.1-Flash-MixedQ2-GGUF` (gate/up IQ2_XXS, down Q2_K,
denso BF16, **senza** Engram, DSpark e visione, senza imatrix): esperti **152,88 GB**; la stessa ricetta nella
proiezione dà 93,43 + 59,45 = **152,88 GB**. File sull'Hub: 168.929.929.664 B = 157,33 GiB (il denso a BF16
pesa 14,95 GiB contro i ~6,9 a Q6_K).

**Byte di esperti per token**: decode **2,24 GiB** (40 strati × 6) contro **1,71** del Vision-Exp (+31%);
prefill 1,12 (20 strati di encoder).

**Quanti bit all'Engram.** Scala di divergenza della porta MLX PipeNetwork (card del repo
`DeepSeek-V4.1-Flash-MLX-mixed-4_8bit-engram6`, 16.384 token wikitext-2, libera, strato finale): Engram come
rilasciato (FP8) 0,1948 · **6 bit 0,1945 (indistinguibile)** · 4 bit 0,2090 (+7,3%). ⇒ **Q6_K** e' il punto giusto.

## 4. Runtime (stato 10/9 sera)

| runtime | V4.1 |
|---|---|
| llama.cpp | **PR #28696, bozza, SOLO convertitore** (vcruz305). Engram scritto a blocchi di righe su memmap (un float32 intero sarebbe 393 GB); conversione q8_0 = 507,9 GB con 121 GiB di RAM. Il runtime `deepseek4` non carica V4.1 (mancano `output_hc_*`), e mancano CED, CSA2 ed Engram. PR Engram #19654 chiusa |
| llama.cpp, precedente riusabile | **qwen4exp (#27742, fusa)**: tabella n-gram da 97,7 GiB servita con indici calcolati sull'host in `set_input` + `ggml_get_rows`, **nessun op ggml nuovo**; #27794 `--tensor-read-lazy` (lettura pigra via mmap sopra 4 GiB); #27795 quantize a buffer limitato |
| vLLM | modello in main (#56228); il plugin GGUF non ha la mappa DeepSeek |
| SGLang | `dev-dsv41` (#38798); il MixedQ2 mappa 245/245 tensori con patch, avvio non ancora riuscito; Engram sull'host (`SGLANG_ENABLE_DSV41_ENGRAM_HOST_TABLE=1`) |
| MLX | porta PipeNetwork, parità 1e-6 sul `model.py`; ha trovato un bug del riferimento (l'indexer ai passi dispari legge le chiavi dello strato sbagliato, 0,67 di spostamento dei logit) |
| ktransformers, ik_llama.cpp | nulla al 10/9 |
| riferimento DeepSeek | `inference/model.py` (TP8). Il self-test istanzia un modello piccolo a pesi NON inizializzati: controlla forme e kernel, non la numerica. Con pesi casuali fissati diventa un **oracolo di parità senza scaricare pesi**, come per la porta MLX (fp32, 1e-6). Da verificare se i kernel FP8/FP4 di `kernel.py` girano sulla 3060 |

## 5. Contro la nostra macchina (verificata 10/9)

5800X 8C/16T · ASUS PRIME B550M-A WIFI II (4 slot, max 128 GB) · 96 GB DDR4 @3000 (2×32 Corsair + 2×16 SP) ·
RTX 3060 12 GB · **C: Lexar EQ790 NVMe, 310,8 GiB liberi** · **D: EMTEC X160 SATA, 149,4 GiB liberi**.

- **Il tronco IQ2 (137-150 GiB) NON entra in 96 GB + 12 GB.** Bilancio stimato: VRAM = denso ~6,9 + calcolo +
  ~3 GiB di cache esperti; RAM ≈ 78-80 GiB utili agli esperti ⇒ **~50-60 GiB di esperti restano su SSD**
  (con 128 GB: ~15-30).
- **L'Engram su SSD e' il pezzo facile**: 48 letture esatte per token (~10 KB a Q6_K), prefetchabili al
  campionamento; lo strato 14 ha 13 strati di margine. Il prefill ne fa 48 × token: con fault serializzati
  e' latency-bound, servono letture parallele o pre-caricate.
- ⚠ **Ipotesi da verificare: la trappola è la page cache, non la lettura.** Precedente di casa (8/9): Qwen3.8-Flash-Next UD-Q4_K_XL
  (111 GB) su 93 GB di RAM = **0,97 t/s** ⇒ «la tabella resta su disco gratis» falsificata quando il file supera
  la RAM. Col fork `--load-mode none` (esperti residenti, tabella mappata) andava, ma lì la tabella entrava
  comunque in page cache. **Una tabella n-gram servita davvero da SSD sotto pressione di memoria non e' mai
  stata misurata qui.** Se l'ipotesi regge, con V4.1 i fault dell'Engram su mmap ruberebbero page cache agli esperti.
- Siamo tornati nel regime «il modello non entra», l'unico in cui il **gate SSD↔RAM a massa** pagava (5/8: a
  64 GB cancellava la coda, a 96 GB +0,7%).
- Prefill: l'encoder da solo ha ~71,6 GiB di esperti a IQ2 ⇒ durante una lettura lunga può stare tutto in RAM.
- Tetto grezzo del decode: a byte pari col Vision-Exp di oggi (12,4-12,9 t/s), +31% di byte per token porta a
  ~9-10 t/s **se tutto fosse in RAM**. Quanto toglie la coda su SSD non si sa: dipende dalla concentrazione del
  routing a 384 esperti. **È la prima misura da fare, non una previsione.**
- Disco: la release (475 GiB) non entra da nessuna parte ⇒ conversione su pod. Tronco IQ2 + Engram Q6_K ≈
  300 GiB contro i 310,8 liberi su C: ⇒ bisogna fare spazio. D: è SATA: non ci va l'Engram.

## 6. Piano (in ordine, nessun download fino al punto 3)

1. **Test del principio a costo zero** su Qwen3.8-Flash-Next, già su disco (`D:\models\qwen38flashnext\UD-Q2_K_XL`,
   tabella ~27 GiB = 29,2 GB). Esperti residenti (fork `--load-mode none`), page cache ristretta finché la tabella non ci
   sta più, t/s a confronto con la cella libera. Copiarlo prima su C: (NVMe): su D: si misurerebbe il SATA.
2. **Porto del grafo** (nuova arch nel fork o su upstream + #28696): CED, CSA2, Engram secondo lo schema qwen4exp,
   `bias_vl` (già fatto per il Vision-Exp), DSpark a 128 esperti. Parità contro `model.py` a config piccola con pesi casuali fissati (percorso fp32; kernel da verificare sulla 3060).
3. **Pesi**: IQ2 degli esperti convertito su pod, prima senza imatrix (l'imatrix richiede il runtime), Engram Q6_K,
   mmproj. Poi imatrix in casa e riquantizzazione.
4. **Servizio**: denso + cache esperti in VRAM, gate a massa SSD↔RAM con `VirtualLock`, Engram letto da NVMe
   fuori dalla page cache (o con gli esperti bloccati), DSpark.
5. **Leva hardware**: 128 GB (2×32 dello stesso die Hynix M-die, vedi verdetti hardware del 31/7). IQ1 escluso
   per decisione utente.

## 7. Riproduzione (`docs/porto/v41_flash/`)

- `st_headers.py` → `tensors.json` (header dei 48 shard, ~6 s, niente pesi).
- `gguf_ref.py` → `gguf_ref_rows.json` (ricetta del GGUF Vision-Exp in `C:\ds4-models\Vision-Exp-GGUF\`).
- `analyze.py` → pattern, categorie, proiezioni GGUF, byte per token. Nota: la soglia `numel >= 1e8` conta
  anche `engram.wkv` (0,31B) fra le tabelle; nel testo sopra e' riattribuita.
- `config.json` della release (rev `dba1be0a`).

## 8. Aggiornamento 11/9 mattina — un IQ2 vero non c'è ancora

Ricontrollo su 38 repo HF col nome V4.1 (`v41_flash/ricontrollo_quant.py`) e sulle intestazioni dei GGUF remoti
(`v41_flash/gguf_header_remoto.py`: 22 MiB di intestazioni lette, nessun peso).

- **Nessun GGUF IQ2 pubblicato.** L'unico IQ2_XXS resta dentro il MixedQ2 (quantizzato senza imatrix, senza Engram).
- **Perché non può ancora uscire**: IQ2_XXS / IQ2_XS / IQ2_S (e Q2_K_S) vogliono l'imatrix, e l'imatrix si calcola
  facendo girare il modello. Nessun runtime llama.cpp lo esegue: la PR #28696 è ancora bozza e solo convertitore
  (aggiornata l'11/9 alle 02:02, +443 righe); ik_llama e ktransformers: nulla.
- **vcruz305 Q2_K completo: 246,35 GiB**, arch `deepseek41`, 1.046 tensori, senza chiavi imatrix, senza DSpark né
  visione. Composizione dalle intestazioni:

| pezzo | tipo | GiB |
|---|---|---:|
| esperti gate + up | Q2_K | 110,74 |
| esperti down | Q3_K | 72,51 |
| **tabelle Engram** | **Q2_K (2,625 bpw)** | **60,08** |
| denso, condiviso, proiezioni Engram, embed/head | Q2_K / Q3_K / Q6_K / BF16 | 3,01 |

  ⚠ Engram a 2 bit affini: la scala MLX dava già +7,3% di divergenza a 4 bit. Nello stesso repo: Q8_0 completo
  (473,07 GiB), Q3_K_M in caricamento. `AMAImedia/DeepSeek-V4.1-Flash-FP8-GGUF` è una copia del Q2_K.
- **REAP, solo MLX** (pipenetwork, saliency REAP su 65.536 token): REAP25 tiene 288/384 esperti, perplessità
  ×1,028 (peggio su 107/140 finestre); REAP50 tiene 192/384, ×1,168 (peggio su 138/140). rapid-mlx: 336/384 a 2 bit,
  199 GiB, 7,3 t/s su M3 Ultra, 99,995% della massa di routing. **Proiezione a IQ2** (ricetta Vision-Exp):
  REAP50 ~78 GiB (la taglia del Vision-Exp di oggi), REAP25 ~114, 336/384 ~132. ⚠ Potatura statica: vedi il
  collasso per cambio di dominio del reap-loop.
- **Engram HLWQ Q4** (caiovicentino1): rotazione di Hadamard + codebook Lloyd a 4 bit, 132 B/riga, ~101 GB le due
  tabelle, coseno 0,9954. Stesso server: prosa invariata, codice +0,015 nats/token, needle fino a 52k +0,04 (5/5
  recuperati), velocità invariata. Il loro adapter SGLang serve le tabelle da RAM oppure con `OFFLOAD_MODE=nvme`
  sotto i 128 GB di RAM ⇒ **l'Engram su NVMe è un modo di servizio che esiste già** (su 4× RTX PRO 6000).
  Da non confondere con il 4 bit affine MLX (+7,3%).

## 9. Chi ha fatto i REAP di V4.1 e cosa tagliano (11/9)

Il **metodo** è di Cerebras Research: REAP, Router-weighted Expert Activation Pruning (Lasby et al., arXiv 2510.13999,
ICLR 2026, repo `CerebrasResearch/reap`). Cerebras ha pubblicato ~30 modelli REAP (GLM-4.x, MiniMax-M2.x,
Qwen3-Coder, DeepSeek-V3.2) ma **nessun DeepSeek V4 o V4.1**. I REAP di V4.1 sono della comunità, tutti MLX:

| build | autore | esperti tenuti | criterio e calibrazione | costo misurato |
|---|---|---:|---|---|
| REAP25 | Pipenetwork | 288/384 | peso di routing applicato × ‖uscita esperto‖₂, 65.536 token (wikitext-2 train, Wikipedia in 10 lingue, codice) | ppl ×1,028 [1,019-1,039]; saliency tenuta 90,4% (strato peggiore 87,7%) |
| REAP37 (non pubblicato) | Pipenetwork | 242/384 | idem | ppl ×1,077 |
| REAP50 | Pipenetwork | 192/384 | idem | ppl ×1,168, «stile di generazione visibilmente degradato»; saliency 72,7% (peggiore 68,3%) |
| REAP12,5 2 bit | Rapid-MLX (raullenchai), sopra il 2 bit di Vontra | 336/384 | massa di routing «robusta», criterio prudente fra due metà, 2.048 token | massa tenuta 99,995% (peggiore 99,856%); qualità non misurata; 7,3 t/s su M3 Ultra, non esposto nel prodotto |

- **Pipenetwork**: utente HF dal 12/4/2026 (141 modelli), org GitHub `PipeNetwork`, autore della porta MLX
  `deepseek-v41-mlx` (parità 1e-6). Fa REAP in serie: DeepSeek-V4-Flash REAP25/37/50 (31/7), Qwen3.8-2.4T
  reap50/60/75 (13/8), GLM-5.3 e GLM-5.3-Flash REAP25/37/50 (28/8).
- **Cosa tagliano** (intestazioni + `scripts/prune_build.py`): **solo gli esperti instradati**, lungo l'asse degli
  esperti dei tensori impilati `experts.{gate,up,down}_proj`, **e le stesse righe del router** (`gate.weight`
  [192, 5120], `gate.bias` e `gate.bias_vl` [192]). Non è una maschera: gli esperti tolti spariscono, e il top-6
  si sceglie fra i rimasti. **Stesso K in ogni strato** (i 40 strati sono tutti MoE), insieme diverso per
  strato; gli esperti mai instradati in calibrazione escono per primi. Potatura fatta sui tensori già
  quantizzati (equivalente a potare e riquantizzare).
- **Intatti**: attenzione, esperto condiviso, tabelle Engram, embed/head, hyper-connections. DSpark/MTP assenti dai
  build (tolti, non potati); visione portata ma runtime solo testo.
- **La lista degli esperti tenuti non è pubblicata**: `saliency.npz` è citato nel config ma non è nel repo. Per un
  GGUF bisognerebbe ricalcolare la saliency facendo girare il modello.
- Confronto col nostro track REAP ds4 (5/7, V4-Flash): stessa idea, ma maschera di bias a −1e9 invece del taglio
  fisico, saliency sul solo peso di gate, calibrazione di DOMINIO: K50 di dominio ×1,010 (CI attraverso 1),
  casuale ×1,388. Non è un confronto alla pari (modelli e testi diversi), ma il ×1,168 di REAP50 su calibrazione
  generica va nella direzione della lezione del collasso: conta QUALI esperti, e lo decide il dominio.

## Fonti

- https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash (card, config, `inference/`)
- https://github.com/ggml-org/llama.cpp/pull/28696 · /pull/27742 · /pull/27794 · /pull/27795 · /pull/19654
- https://huggingface.co/apetersson/DeepSeek-V4.1-Flash-MixedQ2-GGUF
- https://huggingface.co/pipenetwork/DeepSeek-V4.1-Flash-MLX-mixed-4_8bit-engram6
- https://huggingface.co/vcruz305/DeepSeek-V4.1-Flash-GGUF (Q2_K in caricamento, 4 parti su 7 al 10/9 sera)
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4.1-Flash
