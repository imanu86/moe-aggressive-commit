# REAP-LOOP verso Qwen35B: audit di fattibilita

## Stato reale

Audit sola lettura. Nessun corpus1000 generato, nessuna attivazione raccolta, nessun modello potato o addestrato. Nessuna azione sui telefoni. Repo REAP invariato: `plan/0051-transport-gate-20260713`,28commit ahead, modifica preesistente a `runs/ds4/20260710_experiment_ledger/all_evidence_ledger.csv` preservata. L'autorizzazione a pubblicare il ramo moe-aggressive-commit NON autorizza automaticamente i28commit del distinto repo REAP.

Identita VERIFICATA leggendo solo header/catalogo GGUF (circa11MB, nessun payload): `general.name=Qwen3.6-35B-A3B`, `general.architecture=qwen35moe`, E256/top-k8, embed2048, expertFF512/sharedFF512. Q4_K_M20419565568byte,40layer,733tensori. UD-IQ3_XXS14069266720byte,41layer,753tensori,nextn_predict_layers1: incorpora MTP e NON ha la stessa composizione del Q4. Nessun Qwen3.5-35B trovato. Non confondere Qwen3.6 commerciale con architecture enum del loader.

mmproj locale VERIFICATO:614194304byte,446571248elementi-parametro,architectureclip,visionencoder27blocchi/hidden1152/proiezione2048,projectorqwen3vl_merger,quantizzazioni misteQ8/F16. Nessun mmproj4B nella sua cartella; la precedente cifra676MB citata in chat per il4B non era verificata e non e usata come evidenza.

## Vincolo architetturale verificato

Q4 senzaMTP:34660610688parametri totali,32212254720routed,2448355968nonrouted. Shared125911040,router20971520; embedding e output SEPARATI da508559360ciascuno.

Anche escludendo ENTRAMBI embedding/output e tutto il router restano1410265728parametri nonrouted del trunk: gia oltre0.5B. Routed top8 invariato attiva1006632960parametri per token sui40layer, qualunque sia il pool>=8. Dunque **solo pool-pruning non puo ottenere0.5Battivi**. Conteggio convenzionale con fixed e senza embeddinginput circa2.946B; questo non equivale a FLOP/VRAM e lookupembedding non attiva tutta la matrice.

Con export fisico uniforme K esperti/layer e router compattato, senzaMTP: `P(K)=2427384448 +125911040*K`. K12 da3938316928text-only ma4384888176convision. Convision intatta K8 da3881244016 e K9 da4007155056: per stare sotto4B occorrerebbe praticamente il minimo top8. Con K8 tutti gli otto sono sempre scelti: si perde adattivita nella selezione, pur mantenendo pesi gate variabili. Questi sono conti dal catalogo, NON potatura ottenuta ne qualita preservata; non e il primo pilot consigliato.

## Cosa riutilizzare

Path relativi a `C:\Users\imanu\source\repos\reap-loop`:

- `src/msc/instrument/trace.py:18-49`: record JSONL session/token/layer/esperti/pesi, base generica.
- `scripts/build_session_mask_canonical.py`: ranking massa-gate e generazione keep-list, ma parser da correggere per architettura.
- `scripts/score_routing_mask_coverage.py`: verifica copertura call/massa, parametrizzare expert_count.
- Metodo di controlli full/mask/random, valutazione funzionale e registro `docs/CLAIMS_CURRENT.md`; non trasferire claim ritrattati o numeri DS4 a Qwen.

## Parti NON pronte per Qwen

- `scripts/01_warmup_trace.py:49-55` e uno stub: non produce una traccia reale. La cattura DS4 esiste nelle patch specifiche, non rende questo collector Transformers operativo.
- `src/msc/instrument/router_hooks.py:38-48,151-190`: adapter Qwen vecchi e assunzioni su wrapper/shape, non adapter Qwen3.5/3.6 verificato.
- `scripts/build_session_mask_canonical.py:46-47,65-84` assume top6 e offset fissi: con top8 rischia di interpretare ID come pesi. Serve parser dinamico e validazioni.
- `src/msc/workingset/estimator.py:76-147` usa frequenza e denominatore degli osservati: non chiamarlo automaticamente copertura della massa sull'intero pool.
- `scripts/reap_saliency_ds4.py` usa media condizionale del gate, non salienza completa con norma output; geometria DS4 hardcoded.
- Patch DS4 di trace/mask e `DS4_REAP_MASK_FILE` non si attivano magicamente in llama-server.
- `scripts/reap_bias_mask_ds4.py` modifica GGUF IN PLACE: non applicarlo a Qwen o all'originale.
- Export sparse DS4 e manifest custom non equivalgono a un GGUF Qwen compatto standard. Nessun exporter Qwen potato identificato.

## Punto di integrazione llama.cpp

Donor congelato `C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920\source`:

- `src/models/qwen35moe.cpp:493-540`: routed e shared separati, shared da mantenere.
- `src/llama-graph.cpp:1980-2106`: logits/probabilita, `ffn_moe_topk`, pesi normalizzati. Catturare selezioni/pesi EFFETTIVI tramite callback, non ricostruire routing ipotetico dai soli logits.
- `src/llama-context.cpp:221-222,1729`: cb_eval nello scheduler.
- Maschera candidata prima della selezione top-k, conservando semantica dei pesi/normalizzazione. Implementazione solo in copia isolata autorizzata, mai nel donor/live.
- `--moe-expert-cache` controlla residenza, NON pruning. Non identificata CLI mask pronta.

## Pilot minimo proposto, NON eseguito

1. Confermare hparams/tensor catalogue del GGUF; quantificare parte sempre attiva e routed.
2. Due fixture offline: no-mask con/ senza collector deve preservare output; validare shape, ID, pesi, allineamento layer/token e fase prefill/decode.
3. Cinquanta sessioni di calibrazione, venti held-out separati per sito/layout. Testi/DOM e screenshot se vision e un requisito. Tool simulati, dati sanitizzati, nessuna credenziale.
4. Full vs mask prudente vs mask casuale a pari pool; top-k invariato, keep>=top-k. Copertura95/99 come primo screening, non riduzione immediata a4B.
5. Score: correttezza schemi/argomenti, selector grounding/unicita, recupero errori, task concluso, loop e violazioni. Qualita e timing strumentato separati; almeno3repliche dei casi critici.
6. Solo dopo il gate espandere verso1000episodi e studiare export fisico compatibile/roundtrip.

## Limiti del risultato atteso

Mascherare il POOL puo restringere il working-set, ma non riduce automaticamente file, RAM allocata o numero di esperti attivi. Export fisico e riduzione top-k sono due fasi ulteriori. Conservare mmproj non garantisce vision: token immagine attraversano gli esperti del trunk, quindi serve calibrazione multimodale.

Non c'e ancora evidenza che4Btotali/0.5Battivi sia raggiungibile conservando i task. Il bound della parte condivisa deve guidare il target, non viceversa.

Prima di implementare: autorizzazione esplicita per edit sul branch REAP attuale, copia sorgente/build separata e sessioni GPU35B con stop/ripristino daily. Nessun permesso di alterare altri file, pesi originali o pubblicare la cronologia REAP e implicito in questo audit.
