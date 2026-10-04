# Vocabolario bozze MTP allargato (italiano + codice + inglese)

**Esito: sulla prosa italiana le bozze accettate salgono dal 56–60% al 63–64% e il decode da
36,2 a 39,4 t/s di media (+9%); sul codice nessun effetto (era gia' coperto al 100%).**
Basta un file dati, compatibile con il Daily 0.1.38; il pack MTP non va rigenerato.

## Candidato

`draft_vocab_it_code_en_48542.bin`: 48.542 id, sha256 `4903e972...ba44`. I primi 40.525 sono
quelli attuali, nello stesso ordine (vecchio file sha256 `369151522226...fb25`, identico a
`data/draft_vocab_en.bin` di v0.1.39). Costruito con `tools/draft_vocab.py --corpus` di v0.1.39,
non modificato, `--coverage 0.99` per ogni parte, su un corpus locale:
- 10,6 MB di italiano: documentazione dei repo dell'utente, senza file che sembrano segreti;
- 2,7 MB di codice;
- 0,8 MB di inglese;
- 0,76 MB di JSON.

Gli script sono in `tools/`, i token aggiunti in `added_tokens.tsv`.

Il motore 0.1.38 legge il file in `MtpDrafter::bind()` e raccoglie le righe della testa dal GGUF
nativo: nessun limite di dimensione ne' ordinamento. Il log conferma
`draft head over 48542 tokens (81.5 MiB)` contro 40.525 (68,0 MiB): +13,5 MiB, 6 slot esperti
in meno su ~6.370.

## Copertura (token della risposta presenti nel sottoinsieme)

| Testo | Attuale | Candidato |
|---|---:|---:|
| risposta codice | 100% | 100% |
| risposta JSON | 92,8% | 100% |
| risposta prosa italiana | 76,8% | 98,2% |
| italiano held-out, altro dominio | 79,2% | 98,5% |
| inglese / codice held-out | 99,1% / 98,2% | 99,8% / 99,5% |

## A/B reale (contesto corto, config elastica del Daily, macchina in uso)

`../20261004_routed_keep/SV-*`. Prompt prosa 85 token e 512 generati; codice 2470 + ~170.

| | A t/s | V t/s | A bozze accettate | V bozze accettate |
|---|---|---|---|---|
| Prosa | 33,7 · 38,1 · 36,9 | 38,1 · 40,6 · (23,6*) | 56% · 58% · 60% | 64% · 64% · 63% |
| Codice | 40,7 · 41,6 · 43,4 | 35,6 · 43,9 · (32,3*) | 92% · 93% · 93% | 93% · 92% · 90% |

\* contesa GPU esterna (`stage` 40,6 e 19,5 ms per finestra contro 1–2 normali), esclusi.
L'output verificato resta quello del modello completo: cambia solo cosa il drafter puo'
proporre. Da confermare a 131k (`K-V*`, `K-VM08-*`).
