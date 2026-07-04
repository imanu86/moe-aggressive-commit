# Corso IA avanzato — da builder a ricercatore in inferenza efficiente / MoE

> Costruito su misura (giugno 2026). Obiettivo: capire i **meccanismi** a fondo e arrivare a fare
> **ricerca vera** nell'area che ti interessa (LLM efficienti, MoE, inferenza su HW basso).
> Non è "impara il machine learning": è il percorso più corto dal punto in cui sei a poter
> *contribuire*.

## Da dove parti (e perché è un vantaggio, non un ritardo)
- **Sai costruire sistemi** (BonusX, flotta, infra, far girare modelli reali). La maggior parte di chi
  studia ML *non* sa fare questo — ed è metà del mestiere nella ricerca di sistemi-per-ML.
- **Hai già fatto ricerca, oggi:** hai progettato esperimenti (predire-vs-reagire, coverage,
  prefill→decode), riprodotto in autonomia un risultato pubblicato (MoE-Infinity: lo skew di riuso è
  intra-richiesta), e ragionato sul prior-art (DynaExq, MC#, EASY-EP). **Questo è il metodo scientifico
  applicato.** Ti mancano le fondamenta formali per renderlo rigoroso e veloce.
- **Buco da colmare:** la matematica e la teoria che ti fanno *ragionare* invece di *provare a caso*.
  Inevitabile per la ricerca vera, ma con l'approccio "build-first" (sotto) è digeribile.

## Il metodo di studio (come si fa, non solo cosa)
1. **Build-first.** Per ogni concetto, implementalo da zero in piccolo prima di leggere la teoria
   completa. Sei un builder: impari facendo, non leggendo. (Karpathy è costruito così apposta.)
2. **Paper come unità.** Impara a leggere un paper in 3 passate (abstract+figure → metodo → dettagli).
   Tieni un diario: 1 paper a settimana, riassunto in 5 righe + "cosa NON ho capito".
3. **Riproduci.** Il vero apprendimento è ri-eseguire un risultato e vedere se torna. L'hai già fatto.
4. **Spaziatura.** 6-8 ore/settimana sostenibili battono sprint da weekend. Stima realistica: **6-9 mesi**
   per arrivare a leggere/contribuire seriamente, non settimane. È un investimento, non un corso lampo.

---

## FASE 1 — Fondamenta (il minimo serio, ~6-8 settimane)
Non serve una laurea in matematica. Servono **quattro cose**, viste in modo applicato.

### 1.1 Algebra lineare (la lingua delle reti)
- **Perché:** ogni layer è una moltiplicazione matrice-vettore; l'attention è prodotti scalari;
  la quantizzazione è approssimare matrici. Senza questo non capisci *niente* a fondo.
- **Cosa:** vettori, matrici, prodotto matriciale, rango, autovalori/SVD (per quant e compressione),
  norme, proiezioni.
- **Risorse:** 3Blue1Brown "Essence of Linear Algebra" (YouTube, intuizione visiva) → poi i capitoli
  di algebra lineare di *Mathematics for Machine Learning* (Deisenroth, PDF gratuito).

### 1.2 Probabilità e statistica
- **Perché:** un LLM è una distribuzione di probabilità sul prossimo token; il router MoE è un softmax;
  il campionamento (temperature, top-p) è statistica.
- **Cosa:** distribuzioni, condizionali/Bayes, aspettazione/varianza, entropia/cross-entropy (la loss!),
  KL-divergence, maximum likelihood.
- **Risorse:** *Mathematics for ML* cap. probabilità; StatQuest (YouTube) per l'intuizione.

### 1.3 Calcolo e ottimizzazione
- **Perché:** l'addestramento è discesa del gradiente; la backprop è la regola della catena.
- **Cosa:** derivate, gradienti, regola della catena, gradient descent, convessità (cenni).
- **Risorse:** 3Blue1Brown "Neural Networks" (la serie spiega backprop visivamente).

### 1.4 Programmazione numerica
- **Perché:** è il tuo strumento. Già lo usi.
- **Cosa:** NumPy/PyTorch a fondo (tensori, broadcasting, autograd), profilare memoria/tempo.
- **Risorsa:** il tutorial ufficiale PyTorch + ricostruisci `micrograd` di Karpathy (autograd in 100 righe).

**Progetto Fase 1:** implementa una rete neurale e la backprop **da zero in NumPy** (no framework) su un
problema giocattolo. Quando funziona, hai capito davvero il motore.

---

## FASE 2 — Deep Learning core (~6-8 settimane)
- **Perché:** transformer e MoE sono *casi speciali* di reti neurali. Ti serve la base prima dei dettagli.
- **Cosa:** percettrone → MLP, funzioni di attivazione, loss, SGD/Adam, regolarizzazione (dropout,
  weight decay), normalizzazione (BatchNorm/LayerNorm/RMSNorm), inizializzazione, overfitting,
  il training loop completo, embeddings.
- **Risorse (in ordine):**
  1. **Karpathy — "Neural Networks: Zero to Hero"** (YouTube). *Questo è il corso più importante per te.*
     Costruisce tutto da zero, da builder: micrograd → makemore → GPT. Fallo tutto, scrivendo il codice.
  2. **fast.ai "Practical Deep Learning for Coders"** — pratico, top-down, adatto a chi costruisce.
  3. **d2l.ai (*Dive into Deep Learning*)** — libro interattivo gratuito, da riferimento.

**Progetto Fase 2:** addestra un piccolo modello (es. classificatore o un char-level language model)
end-to-end, e fai un esperimento controllato (cambia 1 iperparametro, misura, spiega *perché*).

---

## FASE 3 — Transformers & LLM (~6-8 settimane)
Qui inizia la tua area.
- **Cosa:** tokenizzazione (BPE), self-attention e multi-head, il blocco transformer completo,
  positional encoding (sinusoidale → **RoPE**, che hai già visto nel codice!), pretraining vs
  fine-tuning, le fasi **prefill vs decode**, la **KV cache** (perché esiste, costo a contesto lungo),
  sampling, **scaling laws** (Chinchilla: quanti dati/parametri).
- **Risorse:**
  1. **Karpathy — "Let's build GPT from scratch"** + **nanoGPT** (costruisci un GPT vero). Indispensabile.
  2. **Stanford CS336 "Language Modeling from Scratch"** (materiali pubblici) — costruisce un LLM
     end-to-end, *esattamente* il tuo livello-obiettivo. Molto consigliato.
  3. **"The Illustrated Transformer"** (Jay Alammar) per l'intuizione visiva.
  4. **Paper fondanti:** *Attention Is All You Need* (2017), *GPT-2/3*, *Chinchilla* (scaling laws),
     *LoRA* (fine-tuning efficiente), *FlashAttention* (attention efficiente in memoria).

**Progetto Fase 3:** prendi nanoGPT, aggiungi **RoPE** e la **KV cache** a mano, misura il guadagno a
contesto lungo. (Colleghi la teoria a ciò che hai già toccato nel nostro engine.)

---

## FASE 4 — MoE e inferenza efficiente (~8-10 settimane) — il tuo fronte di ricerca
Qui la tua esperienza pratica e la teoria si saldano.
- **MoE (la tua area):** routing/gating, top-k, expert condivisi (DeepSeek) vs solo-routed (Qwen3),
  load-balancing (perché gli expert si usano ~uniformemente — *il muro che hai trovato oggi!*),
  fine-grained experts, auxiliary loss.
  - Paper: *Mixtral of Experts*, *DeepSeek-V2/V3* (MLA + MoE fine-grained), una survey MoE recente.
- **Quantizzazione:** da fp16 a int8/int4/2-bit; **GPTQ, AWQ**, k-quants (i tuoi GGUF!), QuIP#/QTIP,
  quant MoE-specifica (MC#, MoQE). Capisci *perché* int4 ≈ pieno e int2 cieco rompe.
- **Inferenza-sistemi (il fronte che ti interessa):** KV-cache quant (KIVI/KVQuant), **speculative
  decoding** (Leviathan 2023; EAGLE), offload CPU/GPU (**ktransformers, PowerInfer**), prefetch expert
  (MoE-Infinity, HOBBIT), prefix/prompt caching, sparsità contestuale (Deja Vu).
- **Risorse:** i paper dell'area + il codice reale (llama.cpp, ktransformers — leggere il sorgente è
  formativo quanto i paper). Conferenza di riferimento: **MLSys**.

**Progetto Fase 4 (= ricerca vera):** riproduci una delle direzioni che abbiamo isolato — es. **MoBiLE**
(attiva K/2 expert + escalation a confidenza) o lo **speculative-prefetch su llama.cpp/12GB** — sul tuo
3060. Misura, confronta col baseline, scrivi i risultati. Questo *è* un contributo.

---

## FASE 5 — Fare ricerca vera (continuo, in parallelo dalla Fase 3)
- **Leggere paper sul serio:** 3 passate; ricostruire la figura chiave; trovare l'assunzione nascosta
  (come hai fiutato la "metrica sbagliata" del distinct-count oggi).
- **Disegno sperimentale:** baseline onesto, una variabile alla volta, segnale precision-independent
  (l'hai già fatto con il `saving` in miss), evitare confondenti (cache calda tra sessioni → processi
  separati: lo dice anche lo scoping ds4).
- **Riproducibilità:** seed, ambiente, script versionati, CSV dei risultati (già lo fai in `runs/`).
- **Comunicare:** scrivere un report onesto (negativi inclusi), poi eventualmente arXiv / workshop
  (es. workshop a NeurIPS/ICML/MLSys su efficient ML). Un buon "negative result" ben misurato è
  pubblicabile.
- **Comunità:** segui i gruppi giusti (autori di ktransformers, PowerInfer, llama.cpp), contribuisci a
  issue reali (es. la #20757 SLRU cache, che è la formalizzazione del tuo risultato).

---

## La spina dorsale pratica (un progetto che cresce con te)
Non studiare in astratto: porta avanti **un filo conduttore** che collega tutte le fasi al tuo HW reale.
1. (Fase 2) rete da zero in NumPy →
2. (Fase 3) nanoGPT con RoPE + KV cache →
3. (Fase 4) tuning llama.cpp `--n-cpu-moe` + prompt-cache sul tuo 3060 (**il primo lo facciamo insieme**),
   poi quantizzazione e misura qualità/velocità →
4. (Fase 4-5) replica di MoBiLE o speculative-prefetch → report.
Alla fine hai: le basi, un GPT che hai costruito, e un contributo reale misurato sul tuo hardware.

## Note oneste
- **La matematica non si salta** se vuoi ricerca *vera* (non solo smanettare). Ma con l'approccio
  build-first è molto più leggera di quanto temi.
- **Tempo:** 6-9 mesi a ritmo sostenibile per arrivare a contribuire. Non è un corso da weekend, ed è
  giusto così.
- **Il tuo vantaggio resta enorme:** intuizione di sistemi + un workload reale (BonusX) + dati veri.
  Studia per *formalizzare* quell'intuizione, non per sostituirla.

## Inizia questa settimana
1. Apri **3Blue1Brown "Essence of Linear Algebra"** (intuizione, basso sforzo).
2. Inizia **Karpathy "Neural Networks: Zero to Hero"**, video 1 (micrograd) — scrivi il codice con lui.
3. Con me: **tuniamo lo stack llama.cpp sul tuo `~/llama`** (sweep `--n-cpu-moe` + prompt-cache, misura
   tok/s reali) — è il Lab 1 della Fase 4, e ti dà un guadagno pratico subito mentre studi le basi.
