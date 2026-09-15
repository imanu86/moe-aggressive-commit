# Scandaglio — teste di bozza (MTP/EAGLE/HASS/DFlash/Medusa/FastMTP) per Qwen3.8-Flash-Next (15 settembre 2026)

Solo lettura. Nessun download di modelli, nessuna build, nessun server, nessun commit.
Letta prima la ricognizione del 14/9 (`RICOGNIZIONE_MTP_ACCETTAZIONE_14_SETTEMBRE.md`): questo documento
non ripete quanto gia' trovato li' (PR upstream, fork con cache MoE, leve di costo) e si concentra
sul reperimento di **teste addestrate diverse** da quella che usiamo, con enfasi sull'accettazione
alla seconda posizione.

## Punto di partenza (dal 14/9, per contesto)

Testa unsloth `shared-Q8_0`: accettazione 0,785 alla prima posizione, 0,553 alla seconda (pareggio
necessario 0,633). Nessuna testa FastMTP pubblicata trovata ieri per Flash-Next ne' per la famiglia
Qwen3-Next/3.5/3.6/3.8. Oggi ho cercato in modo mirato: (a) se `dzannotti/Qwen3.8-Flash-Next-MTP-GGUF`
sia davvero riaddestrata o solo riconfezionata, (b) cosa sia davvero "HauhauCS FastMTP" (citato in
piu' repository con 2,2M download), (c) se esista un metodo riproducibile per riaddestrare la testa
alla ricorsione anche senza un checkpoint gia' pronto.

---

## 1. Tabella completa dei risultati

### 1a. Teste MTP per Qwen3.8-Flash-Next specificamente

| fonte | data | cosa contiene | origine della testa | accettazione dichiarata | compatibilita' llama.cpp | licenza | per noi |
|---|---|---|---|---|---|---|---|
| [unsloth/Qwen3.8-Flash-Next-GGUF/MTP](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/blob/main/MTP/README.md) | 2026 | shared Q8_0/Q4_K_M/BF16 | **estratta** dal checkpoint ufficiale | 0,785 (nostra misura, 1a pos.) | nativa (e' quella che usiamo) | Qwen | gia' in uso |
| [dzannotti/Qwen3.8-Flash-Next-MTP-GGUF](https://huggingface.co/dzannotti/Qwen3.8-Flash-Next-MTP-GGUF) | 2026-08-27 | Q4_K_M 2,5 GB (embed a Q4_K), BF16 7,8 GB | **CHIARITO OGGI: non riaddestrata.** La model card lo dice esplicitamente: *"The multi-token-prediction head that ships inside Qwen/Qwen3.8-Flash-Next"*, *"exported straight from the bf16 checkpoint and quantized with plain `llama-quantize`"* — nessun addestramento ricorsivo, nessuna distillazione, nessun FastMTP | 0,90/0,74 (codice/prosa, ROCm UD-Q4_K_XL); 0,88/0,82 (Vulkan UD-IQ4_XS) — con drafting adattivo `p-min 0,75`, non profondita' fissa | GGUF stock, 34 tensori, blocco 48 completo | Qwen Community License 1.0 | **NO come testa nuova** — e' la stessa testa unsloth, solo requantizzata con embedding a precisione diversa e gate p-min diverso. Il numero 0,90 e' l'effetto del **gate**, non della testa (coerente con la leva n.1 del 14/9) |
| agentionai, pugant, quimmedes, sh0wie (riconversioni varie) | 2026 | Q8_0/ROCm-FP4/MLX della stessa testa | riconversioni, nessun peso nuovo | — | varia | Qwen | **NO** — nessun addestramento, gia' escluso il 14/9 |
| evsinlb, txgsync, catplusplus, Vontra, Jundot, Youssofal, MidnightPhreaker | 2026 (agosto-settembre) | varianti MLX/EXL3/NVFP4 della testa ufficiale, trovate via API HF ricerca "Flash-Next mtp" | tutte riconversioni/requantizzazioni della stessa testa unsloth | non dichiarata per posizione | MLX/EXL3, non GGUF llama.cpp diretto | varia | **NO** — nessuna e' un riaddestramento; sono conversioni di formato per altri runtime (MLX per Apple Silicon, EXL3 per ExLlama) |

### 1b. "FastMTP" — il nome vero e il nome preso in prestito

| fonte | data | cosa e' davvero | per quale architettura | metodo/dati | accettazione dichiarata | compatibilita' | licenza | per noi |
|---|---|---|---|---|---|---|---|---|
| [Tencent-BAC/FastMTP (GitHub)](https://github.com/Tencent-BAC/FastMTP) + [TencentBAC/FastMTP (HF)](https://huggingface.co/TencentBAC/FastMTP) | collegato ad arXiv 2509.18362 | **il repository originale** del metodo: *"fine-tunes a single MTP head with shared weights across multiple causal draft steps"* + compressione del vocabolario | **testato su MiMo-7B-RL e Qwen2-7B-Instruct.** Nessuna menzione di Qwen3, Qwen3-Next o Flash-Next nel README | H20 GPU per il training, procedura non dettagliata nel README pubblico | 2,03x medio su 7 benchmark, +82% su MTP vanilla (aggregato, non per posizione, nel README) | **SGLang**, non llama.cpp/GGUF | apache-2.0 | **NO come checkpoint pronto** — architettura diversa (MiMo/Qwen2 densi), nessun ponte verso qwen4exp. **SI' come metodo** (confermato: e' proprio l'arXiv 2509.18362 citato nel mandato) |
| [HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF) e ~10 mirror (taurusduan, IMUGLYHUH, AIconjured, gshe-x2333, Whytime, hardcoremoore...) | agosto-settembre 2026 | **"HauhauCS FastMTP" e' un sidecar di bozza da 903 MB, NON una testa MTP riaddestrata.** Citazione diretta: *"HauhauCS FastMTP is the custom, variant-specific acceleration profile built for this exact Aggressive release: a compact 32K draft sidecar"* affiancato al modello bersaglio invariato | **Qwen3.8-27B denso**: *"64 language-model layers... 48 Gated DeltaNet layers and 16 gated-attention layers"* — architettura diversa da Flash-Next (che e' un MoE a 512 esperti con iper-connessioni, blocco `qwen4exp`) | **nessun metodo dichiarato** — la card non dice come e' stato costruito il sidecar | 92,0% aggregato a 190k token di contesto, **nessuna scomposizione per posizione** | richiede **fork patchato**: *"requires the sidecar and HauhauCS-FastMTP-llama.cpp.patch"* — la testa MTP embedded (quella ufficiale) resta invece stock-compatibile | Apache 2.0 (eredita dal modello Qwen) | **NO su tutti i fronti**: architettura diversa dalla nostra, nessun metodo di addestramento dichiarato, fork obbligatorio, nessuna accettazione per posizione. Il nome "FastMTP" qui e' **preso in prestito come marchio**, non e' il metodo dell'arXiv 2509.18362 — nessuna delle card lo cita. L'ecosistema di mirror (2,2M download dichiarati sul repo principale) e' rumore: tutti ridistribuiscono lo stesso sidecar |
| brandonbondig, MATTAM540, Skare69, forceware680 (repository "FastMTP" per Qwen3.8-27B) | agosto-settembre 2026 | script di deploy/patch che confezionano il sidecar HauhauCS | stesso di sopra | nessuno dichiarato | nessuna | fork patchato obbligatorio | varia | **NO** — stessa catena di sopra, solo automazione del deploy |

### 1c. Un metodo riproducibile, non un checkpoint: vLLM Speculators + FastMTP recursive recipe

| fonte | data | cosa fa | target dimostrati | costo | output | per noi |
|---|---|---|---|---|---|---|
| [vllm-project/speculators](https://github.com/vllm-project/speculators) | attivo, 2026 | libreria di training per teste di bozza in vLLM. Dal README: *"Added support for finetuning the native Multi-Token Prediction (MTP) heads of models like Qwen3-Next on domain-specific data"* — **esattamente la stessa famiglia architetturale del nostro `nextn`/qwen4exp** (PR #27836 lo conferma: il nostro modulo segue le convenzioni MTP di Qwen3-Next) | esempi pubblicati per **Qwen3-8B** (il modello denso piu' vecchio, non "Qwen3.8" — attenzione a non confondere i due nomi) con EAGLE3/DFlash/DFlash2/DSpark; **nessun esempio per Qwen3.8-Flash-Next specificamente** nella cartella `examples/train/` | esempio Qwen3.5-9B: 2× H200 141GB, **443 secondi totali** (31s preprocessing + 114s server vLLM + 256s training 3 epoche + 42s stitching), dataset auto-generato (~8000 campioni), lr 1e-4, beta 0,6, 3 passi speculativi | HF safetensors "stitchati" nel checkpoint del verificatore — **non GGUF diretto**, serve poi lo stesso passo di conversione/quantizzazione usato per la testa ufficiale | **SI', e' la leva vera**: e' il codice dietro ai numeri Red Hat qui sotto. Il nostro modello e' gia' servito nativamente da vLLM con `method: mtp` ([ricetta ufficiale](https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next)), quindi l'infrastruttura di `speculators` dovrebbe riconoscerlo come target valido — **da verificare, non dato per scontato** |
| [Red Hat Developer, 8/9/2026](https://developers.redhat.com/articles/2026/09/08/optimize-vllm-speculative-decoding-fastmtp-heads) | 8/9/2026 | applica la ricetta sopra a **Qwen3-Next-80B-A3B-Instruct** (stessa famiglia architetturale nostra, dimensione diversa) | GSM8K, ~8000 campioni auto-generati dal modello stesso (self-distillation, coerente col nome FastMTP) | stesso script, stesso ordine di grandezza (minuti, non ore) | pesi non pubblicati — solo la ricetta | **SI' come prova numerica migliore trovata**: pos.0 0,897→0,912, **pos.1 0,719→0,776, pos.2 0,476→0,616** (delta +0,14 alla seconda posizione, dove il nostro pareggio e' piu' stretto) |

### 1d. Runtime alternativo con la stessa testa: ik_llama.cpp

| fonte | data | cosa fa | accettazione dichiarata | per noi |
|---|---|---|---|---|
| [ikawrakow/ik_llama.cpp PR #2369 `qwen4exp: MTP (NextN) self-speculative decoding support`](https://github.com/ikawrakow/ik_llama.cpp/pull/2369) | 2026 | **non e' una testa nuova**: porta l'infrastruttura MTP esistente (la stessa testa ufficiale da 2,6B) su ik_llama.cpp, con layout di tensori piu' flessibile (accetta sia la convenzione unsloth sia quella dzannotti sia il naming legacy `mtp.*`) | RTX 5090, modello 125B: **0,93-0,99 per round**, 95%/pos su codice, **~63% su prosa narrativa libera**, ~90% su continuazione stile editing; **decadimento 73%→52% dalla posizione 1 alla 4 su testo creativo** — stessa forma del nostro profilo | **NO come nuova testa** (stesso peso, nessun riaddestramento); **FORSE come runtime**: se il loro costo per riga di verifica fosse piu' basso del nostro (~2 ms/call di draft pass dichiarati, 131-144 nodi di grafo), varrebbe la pena confrontare — ma non e' l'oggetto di questo mandato (accettazione, non costo di riga) e richiederebbe portare il nostro albero su un fork diverso. Nota anche: single-slot, rifiuta `-np > 1` (come noi) |

### 1e. Famiglia Qwen3-Next/3.5/3.6 — EAGLE3, DFlash, DSpark: esistono, non per Flash-Next

| fonte | data | modello bersaglio | per noi |
|---|---|---|---|
| [Ex0bit/Qwen3.6-27B-PRISM-EAGLE3](https://huggingface.co/Ex0bit/Qwen3.6-27B-PRISM-EAGLE3) e derivati (gelim, wimmmm) | 2026-05/06 | Qwen3.6-**27B** | gia' noto dal 14/9. Non e' Flash-Next |
| circulus, VirVen, EntityDeletr, PatchyTisa, rjmalagon, Dogacel, develoco (EAGLE3 per Qwen3.6-27B/35B-A3B) | mag-ago 2026 | Qwen3.6-27B / Qwen3.6-35B-A3B | **NO** — trovati oggi via API, confermano che l'EAGLE3 esiste per fratelli minori/diversi di Flash-Next, mai per Flash-Next stesso |
| [z-lab/Qwen3.8-27B-DFlash2-GGUF](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF) e decine di mirror/varianti (incoai, Busdriver, changh95, ...) | 2026 | Qwen3.8-**27B** (denso, stessa architettura di HauhauCS sopra) | **NO** — non e' Flash-Next. Confermato con ricerca GitHub `DFlash qwen3-next`: **0 risultati** |
| [RadixArk/Qwen3.8-27B-DSpark](https://huggingface.co/RadixArk/Qwen3.8-27B-DSpark) | 2026 | Qwen3.8-27B | **NO** — stesso motivo; e Jetson AI Lab conferma dal 14/9 che llama.cpp non supporta DSpark |
| **HASS per Qwen3-Next o Qwen3.8** | — | — | **NON TROVATO.** Nessun risultato pertinente ne' su HF ne' su GitHub, ne' via ricerca web mirata |
| **Medusa per Qwen3-Next o Flash-Next** | — | — | **NON TROVATO.** Solo il repository generico [FasterDecoding/Medusa](https://github.com/FasterDecoding/Medusa), nessuna testa Medusa pubblicata per la famiglia Qwen3-Next |

---

## Candidate utilizzabili

Ordinate per aspettativa di accettazione alla seconda posizione (dalla piu' promettente).

### 1 — Addestrare la testa noi stessi con `vllm-project/speculators`, ricetta FastMTP ricorsiva, puntata su `Qwen/Qwen3.8-Flash-Next`

**Aspettativa.** E' l'unico percorso trovato che punta dritto al bersaglio del mandato: alza
l'accettazione **per posizione**, non sposta il costo. Applicando il delta osservato da Red Hat sulla
stessa famiglia architetturale (Qwen3-Next-80B-A3B-Instruct, pos.2 0,476→0,616, cioe' +0,14) al
nostro 0,553 si stimerebbe ~0,69 — sopra il pareggio 0,633. **Attenzione**: il delta Red Hat e' su
GSM8K (matematica strutturata), non su prosa/ragionamento a contesto lungo, dove la nostra
accettazione e' piu' bassa in partenza; e la vLLM issue #47602 (dal 14/9) dice che l'accettazione
decade col contesto. Il delta reale sulle nostre generazioni e' ignoto finche' non si prova.

**Cosa serve per provarla.**
1. Verificare (con un `curl` all'API vLLM o leggendo il codice di `speculators`) che il registro dei
   modelli riconosca `Qwen/Qwen3.8-Flash-Next` come target valido per il training MTP — non e'
   negli esempi pubblicati, quindi va controllato prima di affittare macchine.
2. Hosting: il loro esempio usa 2×H200 141GB per **Qwen3.5-9B** (piccolo). Qwen3.8-Flash-Next e' un
   MoE da ~125B totali — per servirlo in vLLM durante il training online serve una macchina molto
   piu' grande (verosimilmente 4-8 GPU classe H100/H200, noleggiate). Download: il checkpoint bf16
   completo di Flash-Next (non solo la testa) deve essere ospitabile da vLLM — decine di GB minimo,
   piu' probabilmente centinaia se non quantizzato in FP8/NVFP4 lato server.
3. Corpus: **non GSM8K** — coerente con l'avvertenza hqmtp gia' nel ledger 14/9 (17 punti persi su
   corpora generici): servirebbero le nostre generazioni, col ragionamento acceso, a contesti lunghi.
4. Conversione: l'output e' safetensors "stitchato" nel checkpoint verificatore, **non GGUF**. Va
   poi rifatto lo stesso passo che unsloth ha fatto per la testa ufficiale (export + `llama-quantize`)
   — percorso plausibile ma non documentato per questo caso specifico, quindi rischio di lavoro di
   conversione non banale.

**Rischio.** Alto in costo (noleggio GPU multiplo per hosting + training, ordine di grandezza
probabilmente superiore ai 443 secondi/2 GPU dell'esempio piccolo, per via delle dimensioni del
modello), medio in esito (il delta e' dimostrato su un dominio e una dimensione diversi dai nostri).
Mitigazione consigliata: **replay forzato prima** (metodo hqmtp, gia' nel ledger 14/9) per stimare se
il delta necessario e' raggiungibile, poi eventualmente un run piccolo di prova prima di scalare.

### 2 — Provare la testa `dzannotti` con `--spec-draft-p-min 0,75` (non e' una testa nuova, ma un secondo dato sul gate)

**Aspettativa.** Nessun guadagno di accettazione **della testa** (e' la stessa testa unsloth, solo
requantizzata con embedding diverso). Il numero 0,90 dichiarato e' l'effetto del gate `p-min`, non
del riaddestramento — coerente con la leva n.1 gia' identificata il 14/9. **Non risponde al mandato**
di questa ricognizione (cercare una testa riaddestrata), ma e' l'unico dato empirico in piu' trovato
oggi sul comportamento del gate su hardware affamato di banda simile al nostro.

**Cosa serve.** Nessun download nuovo se si tiene la testa unsloth gia' in uso — basta lo sweep di
`p-min` gia' pianificato nel documento del 14/9 (leva n.1). Se si vuole isolare l'effetto
dell'embedding a Q4_K della testa dzannotti: 2,5 GB di download.

**Rischio.** Basso, ma il guadagno atteso e' quello gia' stimato ieri (+1-3% col solo gate, salvo
sblocco di n-max 3-4).

### 3 — Riprodurre da zero il metodo Tencent-BAC/FastMTP sull'architettura qwen4exp

**Aspettativa.** Sconosciuta — nessun precedente su architetture con iper-connessioni/MoE a 512
esperti. Il metodo (auto-distillazione + loss ricorsiva pesata) e' description-compatibile con
qwen4exp in linea di principio, ma servirebbe scrivere l'adattamento da zero (il codice pubblico
gira su SGLang per MiMo/Qwen2, non ha un adattatore per qwen4exp).

**Cosa serve.** Stesso ordine di sforzo della candidata 1, ma **senza** il tooling gia' pronto di
`speculators` per "modelli come Qwen3-Next" — piu' lavoro di integrazione, stesso costo GPU.
Dominata dalla candidata 1: non ha senso partire da qui se `speculators` gia' supporta la famiglia.

**Rischio.** Alto, dominata dalla candidata 1.

### 4 — Non una testa, ma un runtime: valutare ik_llama.cpp (PR #2369) con la testa ufficiale invariata

**Aspettativa.** Zero guadagno di accettazione (stessa testa, stesso addestramento teacher-forced).
Fuori mandato in senso stretto, ma segnalato perche' dichiara un costo di passo di bozza molto basso
(~2 ms/call) e un decadimento per posizione della stessa forma del nostro (73%→52% pos1→pos4 su
prosa creativa) — utile come termine di paragone indipendente, non come soluzione.

**Cosa serve.** Portare l'albero su un fork diverso: sforzo di integrazione non banale, fuori scopo
per questo mandato di sola ricognizione.

**Rischio.** N/A — non risponde alla domanda posta (accettazione per posizione), la escludo dalle
priorita' pratiche.

---

## Cose cercate, nessun risultato pertinente

- **HASS per Qwen3-Next / Qwen3.8 / Flash-Next**: nessun repository, nessun paper collegato, nessuna
  discussione. Zero risultati pertinenti su HF, GitHub e web.
- **Medusa per Qwen3-Next / Flash-Next**: solo il repository generico del metodo, nessuna testa
  specifica pubblicata per questa famiglia.
- **DFlash per Qwen3-Next** (query GitHub diretta `DFlash qwen3-next`): **0 repository**. DFlash/DFlash2
  esistono solo per Qwen3.8-27B (architettura densa diversa).
- **FastMTP per Qwen3-Next/3.5/3.6/3.8 con pesi pubblicati**: nessuno. Esiste solo la ricetta
  riproducibile (`speculators`) e una dimostrazione numerica (Red Hat) senza checkpoint scaricabile.
- **EAGLE3 per Qwen3.8/Flash-Next specificamente**: nessuno (esiste solo per Qwen3.6-27B/35B-A3B).
- **"draft model qwen3 next gguf" come termine isolato**: risultati tutti riconducibili a quanto gia'
  in tabella (nessuna scoperta aggiuntiva).

---

## Verdetto in tre righe

**Per Flash-Next specificamente: no.** Nessuna testa riaddestrata alla ricorsione esiste pubblicata
per questo modello — `dzannotti` e tutte le altre riconversioni sono la stessa testa ufficiale
unsloth, solo requantizzata; "HauhauCS FastMTP" prende in prestito il nome ma e' un sidecar non
addestrato per un'architettura diversa (Qwen3.8-27B denso) e richiede un fork patchato.
**Per la famiglia: parzialmente si', ma senza checkpoint.** `vllm-project/speculators` supporta
esplicitamente il riaddestramento ricorsivo delle teste MTP "per modelli come Qwen3-Next", e Red Hat
ha dimostrato +0,14 alla seconda posizione su Qwen3-Next-80B-A3B-Instruct (GSM8K) — e' un metodo
riproducibile, non un peso scaricabile, e mai provato su un modello della taglia/architettura di
Flash-Next ne' su prosa a contesto lungo.
**Primo passo:** prima di affittare GPU, fare il replay forzato (metodo hqmtp) per stimare il delta
di accettazione necessario a superare il pareggio 0,633 *dopo* le leve di costo del 14/9, poi
verificare se `speculators` riconosce `Qwen/Qwen3.8-Flash-Next` come target — solo allora vale la
pena del costo di un run di addestramento vero.
