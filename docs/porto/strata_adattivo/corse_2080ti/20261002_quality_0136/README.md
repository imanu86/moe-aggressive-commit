# Qualità 0.1.36: metodo upstream e A/B/A — 2 ottobre 2026

**Metodo implementato e prove concluse. Gate numerico PASS; gate complessivo
delle risposte FAIL**, per un errore aritmetico presente anche nel riferimento.
Nessun aumento di bozze o nuovo SOTA promosso. Il daily rimane elastico.

Tre motori sequenziali: A1 0.1.31, B 0.1.36, A2 0.1.31. Tutti con 6.167
slot reali, budget laboratorio 4.600, chunk 2.048, KV 262.144/int8/resident
32.768, riserva configurata 1.393 MiB. IQ_MT_MIN=1, adattamento/PCIe dei miss
spenti, lookup spento, MTP massimo 4 (fino a tre bozze). Non sono impostazioni
di throughput del daily. Eseguibili f469e096/c35505ca invariati.

## Confronto numerico

Dump completi identici bit per bit tra tutti i bracci. 512/1024/1024 token
di input sui testi codice/documento/dialogo; 2.557 posizioni con target noto.
Top-1 100%, KL 0, perplexity identica, anche nella ripetizione A1/A2.
Il test usa prefissi forzati e scarta la predizione prima di aggiungere il
successivo token di riferimento. La diagnostica nativa raccoglie una riga
completa per posizione, con verifica di dimensioni e valori finiti.

| Testo | Posizioni | Top-1 A1/B | KL media | PPL A1 | PPL B |
|---|---:|---:|---:|---:|---:|
| code | 511 | 100.0% | 0.000000 | 1.834109 | 1.834109 |
| doc | 1023 | 100.0% | 0.000000 | 1.860732 | 1.860732 |
| chat | 1023 | 100.0% | 0.000000 | 2.290217 | 2.290217 |

## Risposte complete

Sette richieste per braccio, tutte `finish=stop`. Sei controlli corretti:
conversioni MiB/GiB, unicità stabile, saldo, ordine dipendenze, lookup breve
e tre codici recuperati al 10/50/90% di un prompt freddo da 131.072 token.
È un insieme di sette controlli ripetuto tre volte, non 21 problemi indipendenti.

Il problema `3*17 + 2*23 + 8` riceve **92** invece di **105** in A1/B/A2,
con ragionamento disattivato. Non cancellare il FAIL della corsa originale.
Le risposte e i criteri sono salvati, compreso il fallimento.

## Diagnosi senza bozze

Stesso 0.1.36, capacità verificatore 2 e massimo MTP 1, lookup spento:
zero bozze effettivamente offerte. Senza ragionamento risponde ancora 92;
con ragionamento risponde 105 e termina normalmente. Il caso non richiede
speculazione per fallire. Non provati tutti gli altri limiti di bozza.
Questo controllo mirato non è una valutazione generale della qualità.

## Evidenze, operatività e limiti

Metodo e test CPU pubblicati su main nel fork: `tools/sm75/validate_model.py`,
`test_validate_model.py`, `docs/sm75/VALIDATION.md`. Cinque controlli CPU PASS.
La policy numerica è locale, dichiarata prima dei token; non è una soglia
universale upstream. Conservati tre avvii interrotti senza prompt e la
correzione esplicita del controllo di ammissione VRAM. Non alterato il gate
numerico o l'oracolo dopo aver visto i risultati.

Evidenze: [rapporto](../../QUALITA_0136_2_OTTOBRE.md).
Circa 7,6 GB di logits grezzi rimangono in
`D:\ds4_work\strata\validazioni\20261002_quality_0136_aba_final`.
ID congelati, hash, output, risultati e log sono nel repo. La prova mirata
è in `20261002_quality_0136_non_spec_probe` e nella copia `non_spec_probe/`.

La nuova evidenza riguarda corpus brevi e retrieval 131k, non qualità a250k,
parità dell'elastica o PR isolata sulla nuova base. PR #512 resta in bozza.
Nessun workflow aggiunto, nessuna altra chat coinvolta, nessun carico artificiale.
Binario/server/lanciatore/configurazione daily invariati. I motori propri
sono conclusi e la macchina viene lasciata libera dalle nostre prove.
