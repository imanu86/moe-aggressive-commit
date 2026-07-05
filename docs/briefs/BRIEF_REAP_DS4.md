# BRIEF — Track REAP su DS4-Flash (chat parallela)

> Sei una chat/agente dedicato al track REAP. Lavora su **branch `reap/ds4-domain-prune`**.
> Contesto generale: `HANDOFF.md §0` + `docs/EXPERIMENTS_LEDGER.md` (NON rifare esperimenti già censiti lì).
> Il track SPEX (prefetch/cache) e il track DSpark (spec-dec) girano in parallelo su altri branch — non toccare i loro file.

## Obiettivo
Produrre la ricetta per un **DS4-Flash potato per dominio** (pipeline CGC Segnali / betting-promo italiano):
da 256 expert/layer → ~50% via **REAP-saliency**, cioè da **86.7GB → ~48-52GB** stimati
(expert 72.6GB → ~36GB + backbone 8.2GB + MTP). Perché ora: sta arrivando RAM 64GB sulla workstation →
un modello ~50GB **sta INTERAMENTE caldo in RAM** = SSD eliminato del tutto per il dominio.

## Vincoli di metodo (dallo studio chiuso — ledger sez. A/C/G)
1. **REAP-saliency (Eq.9, media condizionale g·‖f‖), NON massa/frequenza.** A scala la massa FALLISCE
   (anomalia F-ctrl: 235B K50 massa ppl 18.7 > random 9.2). REAP dom K50 su 30B: ppl 5.50 < full 5.56.
2. **Sempre controllo RANDOM** a pari K (rigore paper) e **dom-vs-gen dichiarato**: il potato è un
   modello DA DOMINIO; sul generale degrada (F3) — non è la north-star generale, è il turbo Segnali.
3. Pruning = escludere expert dal FILE, il router va rinormalizzato sui sopravvissuti (verifica come
   ds4/gguf gestisce expert mancanti — probabilmente serve rimappare gli indici nel gguf, non bucarli).

## Dati necessari (gap da colmare PRIMA)
- La trace attuale (`runs/ds4_routing_trace_smoke/routing_trace_count64.csv`) ha solo expert-ID, **niente
  gate-weight** → la saliency Eq.9 non si calcola da lì. Serve estendere la trace-capture di codex
  (patch 0005) per loggare anche i pesi di gate, oppure calcolare la saliency su pod col modello HF.
- Serve una trace DOMINIO (prompt Segnali reali, 500+ token) — coordinati col task "trace multi-dominio pod".

## Deliverable (in ordine)
1. `docs/REAP_DS4_design.md`: come si applica REAP a un gguf ds4 (formato, rimappatura router, tool da
   scrivere o riuso di `gguf-tools/`), rischi.
2. Estensione trace: patch che logga gate-weights (env `DS4_SPEX_TRACE_ROUTING_WEIGHTS=1`), su branch tuo.
3. Analisi saliency dalla trace dominio → mask json (`reap_mask_ds4_domain.json`) + stima GB risultante.
4. Piano eval: field-accuracy Segnali (N=152 gold) pruned-vs-full + controllo random, su pod.

## Regole
- NIENTE run GPU locale senza coordinarti (il 3060 è conteso col bench SPEX). Analisi/design/patch: liberi.
- Ogni misura riportata deve avere il file su disco citato. Niente numeri a memoria.
- Commit piccoli sul tuo branch, push frequente, aggiorna questo brief con lo stato in coda.

## Stato
- [ ] design doc
- [ ] patch trace weights
- [ ] saliency + mask
- [ ] piano eval
