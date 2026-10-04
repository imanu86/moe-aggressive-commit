# Decode in chat e diagnostica PLE — 4 ottobre 2026

Server utente spento prima dei test; prove seriali, senza carico artificiale,
senza interventi sulle app dell'utente o coordinamento con altre chat.
L'automazione della precedente sessione di quattro ore resta in pausa.

## Esito operativo

Nessuna nuova SOTA e nessuna modifica al Daily. Aumentare la quota PCIe da
0,36 a 0,55 rallenta tutti e tre i prompt; proposta respinta. È stata scritta
e compilata una diagnostica PLE opzionale, spenta di default, ma non installata:
la parità numerica passa, il controllo della risposta operativa fallisce.

Daily resta `a17d0dd5362bc35420ca9ef3d1a8cf8c014dafbb3aea189c6c664fe7930e8674`;
config `f0237b6abdacd73944fb9232bcdaf016c733bc2dd1fdae6723284ae3659f2e8d`.
Cache auto/elastica, riserva 1393 MiB, KV int8 262144/residenti 32768, tail,
exact-small e QSA invariati. Snapshot sorgenti, manifest e launcher invariati.
Il candidato `07dcf897…` rimane negli artefatti locali della ricerca.
Sorgenti e risultati pubblicati nel fork su `main`, commit
[`93af204`](https://github.com/imanu86/Strata-2080Ti/commit/93af204108aed79d0f680d0131ada5cc7ba397a5).
Il checkout operativo su D: resta al commit precedente `d21d660`.

## Profilo e controllo numerico

Profili iniziali: 4163 token a 44,8 t/s (aritmetica corretta), 9283 a 31,4 t/s
(LRU corretto), 20480 a 33,1 t/s ma risposta troncata a 1536 token: nessun PASS
di qualità sull'ultimo. Il primo controllo aveva contato 4096 anziché 4163
perché mancavano i 67 token JSON iniettati dal server. Il FAIL resta conservato;
la verifica successiva dei grezzi API/native e dell'oracolo è distinta.

Nei profili codice/documento, staging 30–33 ms per finestra. Il totale include
PLE ma non ne dimostra la causa. La nuova diagnostica misura separatamente
submit/wait/dequantizzazione e snapshot I/O prima/dopo. Il contatore riguarda
il verificatore primario, non la somma multi-GPU. Non sottrarre p50/p99 e non
confondere ms per finestra con ms per layer-finestra.

Tre bracci: vecchio Daily, candidato OFF e ON. Tutte le prime righe F32
complete (248320 valori a 4163/9283/20480 input) e tutti i 384 ID per braccio
coincidono bitwise. I 128 token per richiesta sono prefissi, non risposte
complete. Il primo runner fallisce sul parser CRLF dopo la prima richiesta ON;
la ripetizione completa salva prima i grezzi e supera il controllo corretto.
Gather PLE: 0,849/0,758/0,457 ms per finestra; residuo 0,002 ms. L'anomalia
precedente non si riproduce: nessuna causa o accelerazione dimostrata.
Il gate numerico usa 5080 slot/8442 MiB, PCIe 0, spec 4/MTP max 4;
elastica, adattamento, suffix e prompt cache spenti. Non dimostra parità
delle risposte complete sotto la politica elastica operativa.

## Risposta operativa fallita

Con i parametri reali del Daily e timer spenti il candidato conclude il task
LRU da 9283 token, ma restituisce hits=1/misses=13 invece di 2/12.
Evizioni e stato finale sono corretti. La risposta è JSON valido e termina
con stop: è un errore semantico, non un crash o un parser rotto.
Il Daily precedente supera il controllo del risultato. Le sequenze complete
di token sono diverse, con 5849 slot iniziali nel candidato e 6014 nel riferimento.
La cache auto/elastica può cambiare piazzamento tra avvii: questo confronto
non isola da solo una regressione. Il FAIL blocca comunque la promozione;
nessun tentativo viene rinominato PASS. Parità numerica e qualità sono distinti.

## Screening PCIe

Tre warmup, poi A/B/A per task; cache iniziale 5732 slot/9503 MiB, reserve 2048,
elastica/adapt/suffix OFF, workers 7, spec 6/MTP max 4. Il prefill può prendere
slot in prestito: non è il Daily né un piazzamento interamente congelato.

| Input | A1 t/s | B (0,55) t/s | A2 t/s |
|---:|---:|---:|---:|
| 4163 | 38,422 | 28,656 | 36,875 |
| 9283 | 38,082 | 28,363 | 38,851 |
| 20480 | 38,362 | 31,905 | 36,821 |

Tutte le 12 richieste terminano con stop; gli otto risultati aritmetici/LRU
rispettano gli oracoli. I quattro rapporti completano i fatti richiesti in
210/219 parole (whitespace, titolo incluso). Non è una valutazione generale
di qualità né parità numerica delle partizioni CPU/GPU. Primo/terzo controllo
oscillano circa 4,1%, oltre il limite 3%: misure di screening, non stime precise.

## Prossimo lavoro

Upstream main `99f3dbd0` e PR #646 head `ee5a0bfe` invariati all'ultimo controllo.
PR #646 solo analizzata: top-k sovrapposto a #603 già presente; prefetch PLE
e specializzazione NC richiedono verifica. Il port del prefetch deve drenare
tutti i ticket anche su errore e gestire prefissi parziali e suffix; non
importare il bundle senza parità e beneficio misurati.

Priorità: rendere confrontabile lo smoke operativo e capire le attese
intermittenti; poi kernel CPU AVX2 e specializzazioni NC guidate dal profilo.
Non attribuire i 33 t/s della chat a una regressione confrontando task diversi.
MTP max 4 comprende il token base; i draft totali includono anche suffix.
Con la futura 3060 rivalutare PR #663 e maggiore residenza dei pesi.

[Dati sanitizzati e hash](https://github.com/imanu86/Strata-2080Ti/blob/main/docs/sm75/decode-ple-diagnostics-20261004.json).
Runner e grezzi in `.codex_runs/20261004_decode_real/`; i log della chat privata
non vengono pubblicati. Tutti i motori rimangono spenti a fine sessione.
