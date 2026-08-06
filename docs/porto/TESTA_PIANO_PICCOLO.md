# PIANO — la pipeline della testa, validata in piccolo (punto 4 del mandato)

*Cantiere TESTA, 6/8/2026 sera. Scritto DOPO il braccio A (spec-type confermato,
5,4 contro 2,3 t/s) e PRIMA del braccio A2 (p1 per posizione). Il piano ha
trigger espliciti perché il braccio A ha cambiato la domanda.*

> **AGGIORNAMENTO 7/8 01:07 — IL BIVIO È DECISO DALLA MISURA, e questo piano è
> la via principale, non il piano B.** Il braccio della retta (n_max 1/2/3
> nella stessa config, ledger `TESTA_RETTA_TRE_PUNTI`) ha mostrato che il
> costo dominante del DSpark è la fase di **iniezione** (`process()`: due
> forward CPU della bozza per sincronizzare la sua KV, mai cronometrata —
> +104,8 ms per POSIZIONE contro i 4,65 del pezzo strumentato). Con il DSpark
> la profondità PEGGIORA (7,50 → 5,82 → 5,00 t/s); rifacendo il conto con un
> proponente **senza stato** e gli stessi colpi e mlen misurati la profondità
> **cambia segno** (11,13 → 11,78 → **12,20 t/s**, +32% sulla SOTA).
>
> **Conseguenza di disegno, vincolante per tutto ciò che segue: la testa deve
> restare SENZA STATO.** Niente KV propria, niente iniezione, niente encode:
> legge uno stato che il bersaglio ha già calcolato e produce una
> distribuzione. Non è un dettaglio implementativo — è *il* vantaggio
> strutturale, ed è ciò che sblocca la profondità. Qualunque variante che
> introduca una seconda macchina da sincronizzare rientra nel costo appena
> falsificato.
>
> Il bersaglio diventa **fino a 12,2 t/s a n_max=3**, non 10,6 a profondità 1.
> Taglia da confermare (il controfattuale usa il per_pos del DSpark come
> sostituto di quello ignoto della testa); direzione robusta.

## Il bivio, e chi lo decide

Il braccio A2 (server, `n_accepted_per_pos`) consegna due numeri: **p1 del
DSpark sbloccato** sul nostro carico, e **c_draft** (costo per proposta nel
porto, dai timing per ciclo). Il budget è già scritto nella metrica:
`c_max(p1) = 108·(1+p1) − 168,8` (36 ms a p1=0,899; ~1,08 ms per +0,01 di p1).

    p1 ≥ 0,6  E  c_draft ≤ c_max   →  il proponente ESISTE GIÀ: si ingegnerizza
                                       (potatura del drafter, n_max=1, caching),
                                       la testa nuova diventa PIANO B
    p1 ≥ 0,6  MA  c_draft >> c_max →  serve un proponente ECONOMICO: la testa
                                       piccola è il piano A, bersaglio di costo
                                       0,1-1 ms (adapter, niente 3 strati MoE)
    p1 < 0,6                       →  la testa deve anche essere PIÙ BRAVA del
                                       DSpark: pipeline uguale, ambizione
                                       maggiore, e il pavimento 70,3% della
                                       sonda dice che il segnale c'è

## L'architettura candidata (qualunque ramo del bivio)

**Adapter su stati + lm_head congelata** (puntatore della coordinatrice,
coerente con la sonda):

    h_42(t) [4096]  →  adapter (4096×4096 + norm, ~17 M par, ~34 MB fp16)
                    →  ĥ_finale(t+1)  →  lm_head DEL MODELLO (congelata)  →  logits t+1

- Il one-hot del token corrente NON serve: misurato (70,3% identico con e
  senza) — h_42 lo contiene già. La testa di profondità 1 legge il SOLO stato.
- Niente testa-a-vocabolario piena (4096×129k ≈ 530 M par): la proiezione
  esiste già nel modello, si riusa congelata.
- La sonda lineare (ridge, zero nonlinearità) fa 70,3% in mondo chiuso: un
  adapter MLP con dati veri parte da lì in su, sul vocabolario aperto.

## La validazione in piccolo (prima di toccare i 284 miliardi)

Modelli: `granite_1b_a400m` / `olmoe_1b_7b` (config in `reap-loop/configs/models/`).
Attrezzo di addestramento: **PyTorch** (il mandato indicava llama-finetune:
CORRETTO dalla coordinatrice, commit 68a9c04 — quello è finetune del modello
intero).

1. **Tracce dal piccolo** con la RICETTA (llama-eval-callback, filtro su
   norm/route, **id dal log** — mai ritokenizzare, lezione a ledger): dominio
   codice + prosa, ~50-100k token (il piccolo gira veloce).  [macchina: ~min]
2. **Estrazione per PyTorch**: stati h_L(t) + id(t+1) dal log; lm_head e
   norm finale del piccolo dequantizzati da GGUF (gguf-py, come già fatto
   per il gate nel warm_start).  [offline]
3. **Addestramento adapter** (PyTorch CPU o GPU piccola — passa comunque dal
   coordinatore: "finetune anche piccolo").  [macchina: ~min, non ore]
4. **p1_replay offline**: top-1 su held-out temporale contro il token vero —
   stessa disciplina della sonda (split temporale, metri bigram/moda,
   pedice di dominio).  [offline]
5. **Cancello di pipeline**: il p1_replay del piccolo deve battere il SUO
   bigram con margine, e la pipeline non deve avere buchi di allineamento
   (il cancello id==T della sonda, riusato identico).

Solo DOPO: dataset grande dal modello vero (run lunghe → punto 5 del mandato,
coordinatore) e adapter sul grande, misurato in serving (A2-style), non solo
in replay.

## Cosa NON decidere adesso

- Dimensione/profondità dell'adapter (1 strato lineare? MLP×2? norm?): la
  decide il replay in piccolo, non l'intuito.
- Se servano più strati sorgente (h_42 + h_30?): solo se il replay in piccolo
  mostra un tetto basso con lo strato finale solo.
- L'integrazione nel porto (graph GPU, dove il DSpark insegna che
  l'orchestrazione mangia 25× i FLOP): si disegna quando c'è una testa che
  merita l'integrazione.
