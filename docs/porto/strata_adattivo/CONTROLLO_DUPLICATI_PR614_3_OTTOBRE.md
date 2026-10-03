# Controllo duplicati e PR614 — 3 ottobre 2026

**Aperta [PR614](https://github.com/Niko1221/Strata/pull/614), pronta per review,
solo checkpoint tail.** Base upstream0.1.38 `99f3dbd`, head
`8dad0ca8be0e56c2868a935cd4c63e84e41fa7b2`, due file:
`src/program/generate.cpp` e `docs/PROMPT_CACHE_TAIL.md`.
[Messaggio a Niko1221](https://github.com/Niko1221/Strata/pull/614#issuecomment-5968358423)
pubblicato dopo il controllo, con misure e proposta di confronto sull'elastica.

## Copertura della ricerca

- API GitHub:632fork pubblici elencati, incluso il nostro, escluso dalla ricerca
  di contributi altrui;630default heads esterni letti, un fork
  (`ConsultantTrail/Strata`) restituisce404.
- Tutti i branch pubblici restituiti per i630fork accessibili più upstream:
  **1179branch**. Codice di **535commit distinti** tra default, branch e PR
  correlate: `generate.cpp`/`expert_cache.cpp`, firme e contesto dei checkpoint.
  Il ramo `xyzzing/Strata:rocm-port` non contiene questi due sorgenti;
  tree API verificato, eccezione registrata. I default heads ripetuti nella
  metadata dopo la ripresa sono deduplicati per SHA nella lettura del codice.
- Ricerca issue/PR su elastic/VMM/checkpoint/branch, inclusa storia chiusa;
  lettura delle proposte e dei commenti del maintainer per37/563/378/533/65/203/62.
- Nessuna funzione equivalente al checkpoint aggiuntivo near-tail è emersa nel
  codice e nelle proposte controllate. Non è una prova di assenza di lavoro
  privato, inaccessibile o non pubblicato; i nomi diversi sono valutati nel
  contesto dei blocchi checkpoint, non soltanto tramite il nome del flag.

## Lavoro preesistente e decisione

| Proposta | Stato letto | Differenza rispetto al contributo |
|---|---|---|
| [37](https://github.com/Niko1221/Strata/pull/37) | Chiusa, non merged | VMM cache + vision; reviewer segnalò residenza adattiva errata e conflitto con il prestito prefill |
| [563](https://github.com/Niko1221/Strata/pull/563) | Aperta | RELEASE/REFILL dell'intera cache, conserva il modello e lo stato |
| [378](https://github.com/Niko1221/Strata/pull/378) | Aperta | KV che cresce prendendo VRAM dalla cache; richiede KV interamente residente |
| [533](https://github.com/Niko1221/Strata/issues/533) | Issue aperta | Maintainer propone controllo manuale VRAM; esclude resize automatici dal suo piano |
| [62/65](https://github.com/Niko1221/Strata/pull/62) | Idee integrate0.1.20 | Conservazione root/shared prefix, non checkpoint aggiuntivo near-tail |
| [203](https://github.com/Niko1221/Strata/pull/203) | Chiusa | Copia checkpoint asincrona, nessun guadagno misurato sulla base allora corrente |

La nostra elastica automatica con core/coda resta una variante distinta, ma
si sovrappone al lavoro VMM già proposto e alla direzione di533. **Nessuna
nuova PR dell'elastica aperta:** il messaggio al maintainer indica patch e
misure già pubblicate per valutare un contributo mirato. Nessuna dichiarazione
che l'idea VMM sia nuova o esclusivamente nostra.

La PR614 conserva il flag disattivato di default, non taglia i chunk e non
presenta la grid originale come corretta. Numeri e limiti rimangono nel
[report delle prove](PORT_ELASTICA_CHECKPOINT_TAIL_3_OTTOBRE.md).

## Stato dei checkout

Autorizzazione corrente dell'utente: controllare duplicati, aprire la PR utile
e scrivere al maintainer. Usato il branch `codex/prompt-cache-tail-038`, già
descritto, senza cambiare checkout main: indice temporaneo, albero verificato
per path/SHA, commit con trailer Codex e push immediato.
`C:\Users\imanu\source\repos\Strata-2080Ti` resta main pulito,
HEAD2c39467. Daily e lanciatore non modificati. Nessun build/test GPU in questo
giro; riutilizzata l'attestazione completa già pubblicata.

[Audit, riferimenti API, messaggio e manifest](corse_2080ti/20261003_pr614_duplicate_audit/manifest.json).
