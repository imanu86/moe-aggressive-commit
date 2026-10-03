# Buffer dei turni brevi: esperimento del 3 ottobre

Commit fork pubblicato su main: `15fd2eacd46c0057a91e876dca0a3e99990907ca`.
Candidata SM75 SHA-256 `d46a0752fd7b92726b34dd0332bf772cba22bba589aa22aed6e730becfb4b8fa`.
**Opzione disattivata per default; non installata nel Daily. Nessuna nuova SOTA.**

`STRATA_PREFILL_EXACT_SMALL=1` evita che l'arrotondamento di un batch da1007 a1024
faccia allocare il ring grande, quando il batch reale usa il percorso routed.
Per1007 token il prestito scende da1033 a517 slot:516 esperti restano residenti
in piu' durante il prefill. Soglia streaming1024 e limite KV262144 invariati.
Non e' la precedente prova con `STRATA_PREFILL_STREAM_MIN=1000`.

Windows,2080Ti modificata22GB,Ryzen5800X,96GB RAM,CUDA12.6,IQ3_XXS,
OktoCGControl aperto e nessun carico artificiale. Banco a6167 esperti fissi,
KV int8/residenti32768,spec4,7 worker,profilatore spento,trace/logits accesi.
Il Daily conserva la sua cache elastica; la cache fissa vale solo per il banco.

## Evidenza completata

- Compilazione Release SM75 e519268 controlli C++ del dimensionamento passati.
- A/B/A breve valido sulle taglie batch256,768,769,1007,1023,1024,1025,1536.
  A1007: base2336,1/2324,9ms, candidata2196,2ms; +6,12% t/s rispetto alla media
  dei ms base. Il tempo comprende1008 token di input e il refill finale.
- Su8 prompt brevi e4 richieste lunghe completate, tutti i248320 logits della
  prima riga target coincidono bit per bit;130 token greedy totali uguali tra
  A1 e candidata. Le4 richieste lunghe sono due preparazioni e due continuazioni.
  E' un controllo numerico circoscritto, non una prova estesa di qualita'/PPL.

| Contesto reale | Nuovi token | Base A1 | Candidata | Limite |
|---|---:|---:|---:|---|
|130380|1014|3873,1ms|3713,9ms|Coppia singola, guadagno non confermato|
|249322|1014|4357,9ms|4363,1ms|Nessun vantaggio osservato|

## Corse escluse e mancata promozione

La prima esplorazione comprendeva anche un gather raggruppato a8 slot: parita'
passata ma nessun guadagno osservato nelle coppie brevi utilizzabili. Tolto dalla
candidata finale; sorgenti/binario conservati nel laboratorio `gather8-experiment`.
Il suo ultimo controllo rallentava di circa5x ed e' escluso dai tempi.

Una ripetizione breve fu interrotta da un percorso relativo errato nel banco di
dump logits; corretto in assoluto e rifatto con successo l'intero A/B/A breve.

Nel test lungo l'ultimo controllo base ha rallentato molto durante il prefill
freddo; fermato a circa65536 token. Il controllo riavviato agli stessi parametri
ha rallentato ancora; fermato vicino a32768. Nessuna richiesta completata in
questi due controlli. I risultati grezzi mantengono lo stato failed e non sono
stati riscritti come prove completate. La coppia A1/E resta valida per la parita'
numerica, ma il confronto prestazionale lungo resta inconclusivo.

Anche la prova candidata con la configurazione elastica operativa e' stata
fermata nel primo chunk freddo:6426 esperti,1001MiB liberi all'avvio; caricamento
arena0,37GiB/s, circa146s complessivi contro circa32s negli avvii rapidi.
**Smoke operativo non superato, candidata non promossa.** Non e' un errore CUDA
accertato: il motore e' stato fermato da noi per non prolungare la corsa anomala.

Un'istantanea del primo controllo lento mostrava620MiB VRAM liberi, clockGPU
1830MHz/memoria6800MHz, RAM disponibile circa25GiB. Durante lo startup operativo
un campione5s mostrava circa76MiB/s letti da Strata, senza altro processo con I/O
comparabile. Priorita' CPU/I/O normali, nessun EcoQoS esplicito rilevato nella
catena dei processi. I due SSD risultano Healthy/OK, ma cio' non spiega ne'
esclude problemi temporanei. La causa resta ignota: non attribuirla a Okto,
alla patch, a throttling o a paging WDDM senza una traccia specifica.

## Stato e seguito

Binario Daily ancora `13ee1a89be497ad83c67f62553b1133fec2a8d9309230d43a9dae639d89008a5`;
configurazione SHA-256 `a049543f81b2f881bba20aa463c3110e7c759df612a679d7af0bf18a5b6363ed`.
Nessun test GPU lasciato acceso. La tokenizzazione incrementale PR567 gia'
installata prima di questo esperimento resta attiva. Non eseguito lo script di
installazione preparato nel laboratorio, che richiede uno smoke operativo passato.

Prima della promozione: localizzare il rallentamento su un solo chunk reale da8192
con profilo di fase, confrontare il vecchio eseguibile Daily e la candidata a flag
spento, registrare memoria/budget e I/O senza stress artificiale. Solo dopo una
condizione ripetibile rifare il controllo lungo e lo smoke elastico. Non lanciare
un'altra curva intera da250k per diagnosticare il primo chunk lento.

I dati compatti sono in [evidence.json](evidence.json). Dati grezzi, input, log,
script, build e prove escluse sono in `.codex_runs/20261003_exact_small` del repo
research. `short_exact_final` e' il breve valido; `long_exact_final` conserva A1/E
completi e A2 interrotto; `long_control_repeat` e `operational_exact` sono interrotti.


## Ripetizione singola B richiesta dall'utente: completata

Ripetuta **solo B, una volta**, sugli stessi input, eseguibile, argomenti CLI e
profilo esperti del tentativo operativo interrotto. Quattro richieste completate
in372,2s incluso startup, senza il precedente rallentamento. Cache elastica:
6342 esperti iniziali,10512MiB;1137MiB VRAM libera all'avvio. KV262144 invariato.

| Contesto | Nuovi token | Prefill | Primo token, pipe nativa |
|---|---:|---:|---:|
|130380|1014|279,6t/s|3,702s|
|249322|1014|248,5t/s|4,193s|

Il primo prompt freddo da129366 token misura937,1t/s. La preparazione successiva
riusa130373 token: i639,4t/s riguardano117935 token nuovi e non un prompt248k
letto da zero. I32 token generati per continuazione misurano25,4/33,6t/s: campioni
brevi, non SOTA decode. Quattro righe da248320 logits finite; qui non c'e' un
nuovo confronto numerico accoppiato. Il banco mantiene `STRATA_IQ_MT_MIN=1`, come
nel tentativo precedente, mentre il default del motore e'2; trace e dump logits
accesi. Precisazione valida anche per la descrizione dello smoke precedente:
argomenti/cache del Daily, con questi override del banco.

Nessun compilatore rilevato in64 campioni CPU/processi/I/O; CPU mediana22%, RAM
disponibile minima22,9GiB. Non prova quale fosse la causa della corsa precedente.
Le anomalie originali restano conservate. Nessun altro A/B avviato, motore chiuso,
Daily invariato in questa richiesta di sola ripetizione. Dati e hash:
[single-B-repeat.json](single-B-repeat.json). Fork main: documentato in158f208.
