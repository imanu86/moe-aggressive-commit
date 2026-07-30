# Output di riferimento ds4 -- "golden"

Il testo che ogni run sano riproduce **al byte**. Serve a due cose: e' il verdetto del
cancello di neutralita', ed e' il termine di paragone per la prima leva che cambiera' lo
sha (speculazione, quantizzazione backbone, maschere) -- dove un hash diverso NON dice se
il testo e' migliore, uguale o degenerato.

## Identita'

| voce | valore |
|---|---|
| char (code point Python) | **8145** |
| sha256[:16] | **c7525d909341a57a** |
| finish_reason | `length` |
| prompt | `PROMPT_HTML` (pagina HTML single-file, startup NeuraForge, cyberpunk neon) |
| parametri | `temperature=0`, `seed=12345`, `think=false`, `max_tokens=2250` |
| CLI | `-c 150000 -n 6000 --mtp-draft 1` |
| modello | `C:\ds4-models\ds4-2bit.gguf` (80,8 GB) |

**Il conteggio si fa SOLO col metodo di `analyze.py`**:
`hashlib.sha256(txt.encode()).hexdigest()[:16]` su `json.load`.
PowerShell conta in unita' UTF-16 e restituisce `8146 / 6e4bb819787c0733`: e' un falso
allarme, gia' preso due volte il 30/7.

## Run che l'hanno prodotto (8 su 46 al 2026-07-30)

`X_fd0bis`, `X_purga1`, `X_ctl_coevo`, `X_neu7c95`, `X_stormfix1792`,
`X_T0_neutralita`, `X_T0_boot` (binario 7C9500D0, PRE-4-patch),
`X_T0_2A82` (binario 2A82ADF1, 4 patch).

**Gli ultimi due sono la prova che le 4 patch sono neutre sull'output**: binari diversi,
stesso testo byte per byte. Tutti gli altri 38 run hanno prodotto 0 char (crash) o
frammenti da troncamento (4-29 char), mai una variante del testo.

## Quando lo sha si muovera'

Un hash diverso da solo non e' un verdetto. Serve il **giudizio cieco** gia' usato il
24/7: due output anonimi, rubric, nessuna etichetta su quale sia il candidato.
Precedente che spiega perche': la maschera REAP K12 dava -82,19% di velocita' **e** testo
degenerato (14 parole uniche su 123) -- due difetti che un confronto di hash non separa.
