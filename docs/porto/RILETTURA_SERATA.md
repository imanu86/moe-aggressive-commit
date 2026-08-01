# RILETTURA DELLA SERATA DEL 1/8 — cosa è stato misurato davvero

Ricostruzione a posteriori del transcript
`C:\Users\imanu\.claude\projects\C--Users-imanu-source-repos-moe-aggressive-commit\8e3de907-7134-4d2d-b2d0-a3be80c02465.jsonl`
incrociato con i log dei run in `D:\ds4_work\porto_run\` e con la storia git di
`docs/porto/braccio.ps1` e `docs/porto/preset_A.ps1`.

Il documento è stato scritto in due passate. Le sezioni **1** e **2** coprono il transcript fino
alle 21:41Z (3.223 righe, 17 run); poi la sessione è caduta ed è ripartita. Le sezioni
**1-bis**, **3** e **4** sono state scritte sul transcript esteso (3.728 righe, fino alle
22:33Z, 20 run) e coprono anche la parte notturna — che è quella in cui il tronco è stato
misurato per la prima volta. Per questo l'ordine sulla pagina è 1, 2, **1-bis**, 3, 4: il
documento è scritto in append e non è stato riordinato.

```
§1       cronologia dei 17 run della serata
§2       le 12 affermazioni invalide
§1-bis   cronologia dei 3 run della notte, i primi veri sul tronco
§3       cosa resta valido, con "cosa la falsificherebbe"
§4       le 37 correzioni dell'utente, in ordine
POSTILLA cosa la notte cambia alle sezioni 1 e 2, e il quadro in una pagina
```

**Convenzioni.** I riferimenti al transcript sono `L<riga> [<timestamp UTC>]`. Gli orari
dei run sono **locali** (UTC+2), perché è il fuso con cui l'harness costruisce il tag del
log: `A_161600` = braccio A avviato alle 16:16:00 locali = 14:16:00Z.

**Il fatto centrale.** Tutti e 13 i run del braccio A hanno usato
`ds4-p4a\build-native\ds4_server.exe`, il **fork**, ramo `codex/prep4-mtp-secondary-map`,
staccato da upstream il 12/05/2026 con 314 commit di upstream mancanti. I 4 run del tronco
della serata (`ds4-port\build-verify\ds4-server.exe`, upstream 54b36ed del 28/07 + i 14
blocchi portati) hanno chiesto 64 e 200 token, cioè meno del token 300 sotto il quale il
REGIME non esiste per definizione. **Nessun numero di velocità prodotto nella serata viene dal
motore portato.** I primi tre run veri del tronco sono di notte, dopo la scoperta: vedi §1-bis.

**Come ho attribuito il binario a ciascun log**, senza fidarmi del prefisso nel nome del file:

| marcatore nel log | lo stampa |
|---|---|
| `ds4: [host-pin] kind=model_stage ...` | solo il **fork** |
| `ds4: SSD streaming initial cuda model map restricted to token embedding` | solo il **tronco** (gira con `--ssd-streaming`) |
| `chat ctx=0..25:25` | prompt **generico** Python (25 token) |
| `chat ctx=0..43:43` | prompt **della campagna**, pagina HTML cyberpunk (43 token) |

L'unico caso ambiguo è `C_194024`, che è morto prima di stampare qualsiasi marcatore: lì
l'attribuzione al tronco viene dal comando (`-Arm C -NoStreaming`, L2166) e dal messaggio
d'errore, che è del percorso di caricamento di upstream.

---

## 1. CRONOLOGIA DEI RUN

Diciassette avvii del server, dalle 16:16 alle 22:16 locali. Otto sono arrivati in fondo
alla richiesta, quattro sono stati interrotti dall'assistente, cinque sono falliti.

| # | ora | tag | braccio | binario | pesi | ctx | tok chiesti | tok generati | prompt | esito | risultato riportato nel transcript |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16:16:00 | `A_161600` | A | fork (non è partito) | `D:\ds4-models\ds4-2bit.gguf` | 8192 | 10 | 0 | — | **FALLITO** | Il server stampa l'help ed esce: `--ssd-streaming` non esiste nel fork. L1302 [14:16:21Z] «Ha stampato l'aiuto ed è uscito» |
| 2 | 16:16:39 | `A_161639` | A | fork | `D:` ds4-2bit | 8192 | 10 | 10 | Python | completo | `gen=10 avg=0,22 t/s`, `finish=length 209,707s`. L1326: END2END 0,048 t/s, «92 volte sotto il riferimento»; L1330 corregge: 45 s di decode e ~165 di prefill |
| 3 | 16:23:23 | `A_162323` | A | fork | `D:` ds4-2bit | 8192 | 400 | 200 | Python | **interrotto** | ultimo campione `gen=200 chunk=0,37 avg=0,36 549,098s`. Fermato alle ~16:36 dopo la scoperta di `G73_OPEN=1` nel preset (L1372 [14:36:31Z]) |
| 4 | 16:39:38 | `A_163938` | A | fork | `D:` ds4-2bit | 8000 | 400 | 0 | Python | **FALLITO** | prefill chiuso in 131,3 s, poi `prefill/tiering compose requires expert tiering enforce` → `expert tiering preparation failed`. Nel transcript è raccontato come «bloccato nella fase `down` del wrap» (L1468 [14:55:40Z]) |
| 5 | 16:50:59 | `A_165059` | A | fork | `C:\ds4-models\ds4-2bit.gguf` | 8000 | 400 | 0 | Python | **FALLITO/interrotto** | log fermo dopo `arena-wrap-source-unlock phase=up`; nessun `gen=`. Ucciso alle ~16:56 |
| 6 | 16:56:53 | `A_165653` | A | fork | `C:` ds4-2bit | 8000 | 400 | 100 | Python | **interrotto** | `gen=100 chunk=0,35 avg=0,21 478,097s`; `capacity=135`, `free_at_size=1040,6 MiB`, `masked_budget_mib=2048` ma `masked_mib=0` (L1602 [15:19:07Z]) |
| 7 | 17:14:06 | `A_171406` | A | fork, **binario pre-ricostruzione** | `C:` ds4-2bit | 8000 | 64 | 64 | Python | completo | `avg=0,30 chunk=0,33 292,521s`; `capacity=135`, `free_at_size=1045,2`, **`evict_backbone=70.877`** in 64 token. L1610: «un quindicesimo del riferimento» |
| — | 17:23 | — | — | **ricostruzione di `ds4_server.exe`** (`ds4-p4a/ds4_cuda.cu` modificato alle 17:22: solo la separazione di `DS4_CUDA_TRANSIENT_VERBOSE`) | | | | | | | Confonde tutti i confronti che attraversano questa riga |
| 8 | 18:47:51 | `A_184751` | A | fork, **binario nuovo** | `C:` ds4-2bit | 8000 | 64 | 64 | Python | completo | `avg=0,69 chunk=2,74 271,361s`; `capacity=306`, `free_at_size=2199,9`, **`evict_backbone=0`**. Unica variabile aggiunta al preset: `DS4_METAL_PREFILL_CHUNK=256` (commit `a7d681b`, 18:47) |
| 9 | 18:57:51 | `B_185751` | B | **tronco** | `C:` ds4-2bit | 8000 | 64 | 64 | Python | completo | `avg=2,05 chunk=2,28`, `finish=length 56,231s`, caricamento 3,3 s. Zero righe `arena`/`prefill-mass`/`vram-prio`/`tiering` |
| 10 | 19:00:59 | `C_190059` | C | **tronco** | `C:` ds4-2bit | 8000 | 200 | 200 | Python | completo | `avg=2,49 chunk finale 2,37`, `finish=length 85,106s`. **Zero righe `[arena]`**: le tre variabili erano impostate e ignorate (L1961 [17:02:11Z]) |
| 11 | 19:09:39 | `A_190939_DS4_G73_OPEN=1` | A | fork | `C:` ds4-2bit | 8000 | 64 | 0 | Python | **FALLITO** | morto a 7 righe durante il caricamento: la sessione Claude Code precedente è terminata portandosi via i processi in background (L2036 [17:11:57Z]). La prova a variabile singola su `G73_OPEN` **non è mai stata rifatta** |
| 12 | 19:16:03 | `C_191603` | C | **tronco**, C corretto (`MASS_WRAP=1`, senza `VRAM_EXPERT_CACHE`) | `C:` ds4-2bit | 8000 | 200 | 200 | Python | completo | `avg=0,41`, progressione `0,66 → 0,79 → 0,42 → 0,22`, `569,219s`. `[arena] allocated mapped-pinned=29.999 GiB slots=4551`, 44 righe `[arena]`, **6 righe `CUDA loading model tensors` durante il decode**. Ma **zero** righe `prefill-mass`, `vram-prio`, `iq2-expert-cache-size` |
| 13 | 19:40:24 | `C_194024` | C | **tronco**, `-NoStreaming` | `C:` ds4-2bit | 8000 | 64 | 0 | — | **FALLITO** | `CUDA model arena alloc failed for tensor-span:99 (1792.00 MiB chunk): out of memory` dopo `prepared model tensor mappings 52.84 GiB` su una scheda da 12 GB |
| 14 | 20:42:02 | `A_204202_DS4_CUDA_HOST_PIN_DIAGNOSTICS=1` | A | fork | `C:` ds4-2bit | 8000 | 400 | 400 | Python | completo | `avg=2,90 chunk=3,36 451,635s`; cache 318/320, `evict_backbone=0`; `[host-pin]` totale `31.015,8 MiB` di cui `dynamic_arena 30.719,2` |
| 15 | 21:13:11 | `A_211311` | A | fork | `C:\ds4-models\DS4-0731-IQ2XXS.gguf` | 10000 | 8000 | **909** (`finish=stop`) | Python | completo, **carico sbagliato** | `avg=4,50`, REGIME 4,70 su n=14 (ricalcolato: 4,71 su n=13). Annunciato come «Nuovo SOTA» a L2350 [19:19:17Z] e ritirato a L2359 [19:21:43Z] |
| 16 | 21:23:19 | `A_212319` | A | fork | `C:` DS4-0731-IQ2XXS | 10000 | 8000 | **6358** (`finish=stop`) | **campagna HTML** | completo | `avg=4,48`, REGIME 4,49 (ricalcolato 4,50 su n=122), pre-ginocchio 4,68 / post 4,44; `evict_backbone=28.672`; `[arena] final hits=81173 misses=78598 uploaded=535,08 GiB` |
| 17 | 22:16:06 | `A_221606` | A | fork | `C:\ds4-models\ds4-2bit.gguf` (**vecchi**) | 10000 | 8000 | **7285** (fermato dal modello) | **campagna HTML** | completo, spento con `CTRL_BREAK` | `avg=2,87`, REGIME 3,83–3,85 (ricalcolato 3,83 su n=140), pre 4,00 / post 3,76; `evict_backbone=3584`, tutti a fine richiesta. Finestra `gen 4200–4750` contaminata da un `git add`+`commit` su `C:` fatto dall'assistente (L2604 [20:47:20Z]) |

### Note sulla tabella

- **Il disco.** I run 1–4 leggevano il modello da `D:` (EMTEC X160, SATA), non da `C:`
  (Lexar EQ790, NVMe). Verificato nel preflight stampato nei tool result: L1297, L1313,
  L1323, L1348 dicono `modello D:\ds4-models\ds4-2bit.gguf`; da L1453 [14:51:52Z] in poi
  dicono `C:`. L'ha visto l'utente, non l'assistente (L1429 [14:50:00Z]).
- **Il prompt.** Fino al run 15 incluso, `braccio.ps1` mandava
  *«Write a Python function that merges two sorted lists…»* (`4ebcb82:93`). Il prompt della
  campagna con guardia SHA256 entra col commit `dcc645d` delle 21:23 locali, quindi vale
  **solo** per i run 16 e 17. Nei log si distingue senza ambiguità: `ctx=0..25:25` contro
  `ctx=0..43:43`.
- **I quattro run del tronco non sono falliti per fragilità.** Tre su quattro chiudono con
  `shutdown requested, draining requests` dopo aver servito esattamente i token richiesti.
  L'unico fallimento vero è `C_194024`, che è il caso senza streaming. L'assistente se ne
  accorge solo a L3162 [21:35:16Z]: *«Il tronco non si è fermato: gli ho chiesto io 64 e
  200 token.»*
- **REGIME.** L'ho ricalcolato indipendentemente dai log (mediana dei `chunk=` oltre il
  token 300) e coincide con quanto riportato entro il centesimo, tranne su `A_204202` dove
  ottengo 3,20 su n=2 contro il 3,36 su n=3 dichiarato — differenza irrilevante ma da un
  campione troppo piccolo per essere chiamato REGIME.
- **Un run dopo la fine del transcript non c'è.** Il run 17 è l'ultimo lanciato; il
  transcript prosegue fino alle 21:41Z con analisi, senza altri avvii.

---

## 2. LE AFFERMAZIONI INVALIDE

Elencate in ordine cronologico. Per ciascuna: cosa è stato detto, quando, e perché non
regge. Alcune sono state ritirate dall'assistente stesso nel corso della serata — lo
segnalo, ma restano qui perché sono state comunicate come risultati.

### 2.1 «B è tre volte più veloce di A» — L1943 [16:59:37Z]

> «**B è tre volte più veloce di A in media, e cinque volte end-to-end** — con due
> variabili d'ambiente contro trentaquattro, e senza arena.»

Confronta `A_184751` (fork, 64 token, `avg 0,69`) con `B_185751` (tronco, 64 token,
`avg 2,05`). Non regge per tre ragioni indipendenti:

- **64 token sono interamente transitorio.** Il protocollo scritto dall'assistente stesso
  in `PRIMO_RUN.md` dice che il REGIME è la mediana oltre il token 300. Nessuno dei due run
  ha un solo campione oltre quella soglia (verificato: 2 righe `chunk=` ciascuno).
- **Il costo fisso è la differenza, non la velocità.** A riempie 30 GiB di arena, B no.
  L'assistente lo nota nello stesso messaggio (`chunk` 2,74 contro 2,28, cioè A **più
  veloce** nella finestra recente) ma il titolo resta l'opposto.
- Il confronto è fra due binari *e* due configurazioni: non isola niente.

L'utente ha preso il numero sul serio — L1991 [17:06:31Z]: *«strano che il baseline vada
già così forte!! magari c'è spazio di miglioramento ampio!»* — e ha costruito su un
confronto che non esisteva.

### 2.2 «Siamo il doppio più veloci di un DGX Spark» — L1993 [17:07:02Z]

> «la issue upstream **#639** misura il substrato nudo a **~1,0 t/s su un DGX Spark**.
> Noi ne facciamo **2,35 su un 3060 da 12 GB**.»

Il 2,35 è l'END2END di `C_190059`, un run da **200 token** con prompt generico, sotto la
soglia del regime, su una macchina con 54,7 GB di page cache calda — che l'assistente
misura e dichiara cinque minuti dopo (L1998 [17:07:46Z]). Non è il costo del substrato:
è il costo del substrato con una cache implicita da 54 GB regalata dal sistema operativo.
Confrontarlo con un numero altrui di cui non conosciamo ctx, prompt né lunghezza è
esattamente l'errore già in memoria (`external-posts-read-their-config`).

### 2.3 «Quattro cambiamenti per +36%, e uno solo per +840%» — L1998 [17:07:46Z]

> «Fra quei due run **è cambiata quella e basta**. Tutto il resto del preset era identico.»

I due run sono `A_171406` (17:14) e `A_184751` (18:47). Fra loro **è cambiato anche il
binario**: `ds4-p4a/ds4_cuda.cu` modificato alle 17:22 e ricostruito alle 17:23 per
separare `DS4_CUDA_TRANSIENT_VERBOSE`, cioè per togliere 4.693 righe di log su 5.073 in un
run da 64 token — circa 73 righe formattate e scritte su `stderr` sincrono **per token**,
dentro il percorso caldo. L'assistente se ne accorge solo a L3045 [21:25:57Z], dopo che
l'utente lo ha spinto sulla definizione di «motore».

Sopravvive la parte aritmetica (`capacity 135 → 306`, `free_at_size 1045 → 2199 MiB`: il
volume dei log non tocca la VRAM). **Non** sopravvive il `+840%` di velocità come
attribuzione al solo `prefill_chunk`.

### 2.4 «Con la nostra politica accesa il tronco va quattro/sei volte più lento» — L2135 [17:23:33Z] e L2151 [17:27:01Z]

> «**Con l'arena accesa il tronco è sei volte più lento, e peggiora nel tempo.** L'opposto
> di quello che l'arena dovrebbe fare.»

`C_191603` non aveva «la nostra politica accesa». Il log contiene 44 righe `[arena]` ma
**zero** righe `prefill-mass`, `vram-prio`, `iq2-expert-cache-size`, `tiering`: l'arena si
alloca e si riempie, il resto della politica non esiste sul tronco. Lo stesso assistente lo
stabilirà a L2555 [20:36:39Z] contando i simboli (`VRAM_PREFER_EXPERT_VICTIM`,
`THRASH_LIMIT`, `BACKBONE_RESERVE_MB`, i 17 `EXPERT_TIER_*` non ci sono). Quindi il run
misura *tronco + arena senza governo*, e chiamarlo «la nostra politica» attribuisce a un
meccanismo la responsabilità di un altro.

### 2.5 «Su 64 GB di RAM un'arena esplicita da 30 GiB peggiora la residenza» — L2151 [17:27:01Z]

Presentato come «il paradosso, che è la vera scoperta della serata», in forma di regola
generale. Smentito dall'utente 13 minuti dopo — L2158 [17:39:32Z]: *«ma smetti di dire
cazzate!! abbiamo sempre girato con un'arena pinnata da 30»* — e ritirato dall'assistente a
L2160. Era una generalizzazione da un run singolo su un binario in cui l'arena convive con
lo streaming di upstream.

### 2.6 «32,3 GB, esattamente la cifra del fork: la doppia residenza è confermata» — L2180 [17:41:24Z] e L2187 [17:42:46Z]

> «**Trentadue gigabyte, cioè esattamente l'arena da 30 più un paio di margine — la stessa
> cifra del fork.** I quindici gigabyte in più erano davvero il meccanismo di streaming di
> upstream che si sommava alla nostra arena.»

Il numero è un'istantanea di `C_194024` **mentre stava ancora allocando**: il log mostra
`42,70 → 43,37 → 47,76 → 48,02 → 48,43 → 52,57 → 52,84 GiB` e poi
`alloc failed for tensor-span:99 ... out of memory`. Quel processo non ha mai servito una
richiesta (zero righe `chat ctx=`). Ritirato a L2216 [18:05:09Z] dopo la domanda dell'utente
*«Hai girato arena senza streaming?»*. Nel frattempo la riga falsa era finita **dentro il
mandato a Codex** (corretto a L2242, commit `a4f84b7`).

Resta valida una cosa sola da quel run: senza `--ssd-streaming` il tronco prova a mappare
il modello in VRAM e muore. Nient'altro.

### 2.7 «Nuovo SOTA» — L2350 [19:19:17Z]

> «**Nuovo SOTA.** riferimento X_CTL8K 4,48 / questo run 4,70 … il +11% su `dec.avg` è
> attribuibile al checkpoint e a nient'altro.»

Cade su quattro fronti, tre dei quali scoperti la sera stessa:

1. **Prompt diverso.** `A_211311` usava il prompt generico Python (25 token nel log,
   `ctx=0..25:25`) e si è esaurito a 909 token, tutti prima del ginocchio a 2048. Il
   riferimento usa la pagina HTML. L'utente lo intercetta a L2354 [19:21:24Z]: *«Ma dovevi
   fare il solito prompt per il sito web»*.
2. **Tre variabili cambiate insieme**, non una: pesi, ctx (8000 → 10000) e
   `prefill_chunk`. L'«attribuibile al checkpoint e a nient'altro» non è sostenibile.
3. **Il riferimento X_CTL8K è una pagina troncata** — 8,3 KB, 2113 token, zero sezioni,
   zero JavaScript, zero form, si ferma dentro il foglio di stile (L2951 [21:16:15Z]).
4. **Il motore è il fork di maggio.** Nessun «SOTA» misurato stasera dice qualcosa sul
   codice portato.

### 2.8 Tutti i confronti contro `X_CTL8K` — L2290 [18:50:48Z], L2389 [19:35:45Z], L2397 [19:39:31Z], L2428 [19:58:40Z]

La colonna di riferimento usata per l'intera serata:

```
X_CTL8K   REGIME 4,48   dec.avg 4,05   END2END 3,53   pre-ginocchio 4,42   post 3,28
```

Due difetti indipendenti, entrambi ammessi solo dopo le 21:

- **È un carico diverso.** 2113 token di CSS troncato contro le pagine complete da 5300+
  token con 9 handler JS. L2951 [21:16:15Z]: *«Tutti i confronti di stasera che passano per
  X_CTL8K sono da buttare.»*
- **I numeri non sono mai stati letti dal suo log.** L3021 [21:22:03Z]: *«Il 4,49 del SOTA
  del 31/7 non l'ho mai letto dal suo log — viene dai miei appunti, e su quegli appunti ho
  già trovato un'anomalia.»* L'anomalia è che `evict_backbone=28.672` compare identico negli
  appunti del 31/7 e nel log di `A_212319`, il che suggerisce una colonna trasposta. **Non
  è mai stato verificato.**

Cadono quindi: il «+3,8% sul regime e +13,3% sulla media» (L2389), il «ginocchio costa il
3,6% invece del 25%» e il «+37% dopo il ginocchio» (L2397), e la tabella a quattro metriche
di L2428 con «END2END −12%, dec.avg +11%, REGIME pari, +35% dopo il ginocchio».

### 2.9 «Il porto del codice è completo e funziona» — L1976 [17:04:16Z]

> «**Il porto del codice è completo e funziona**: 14 blocchi su 14, e il binario portato
> gira — 2,35 t/s end-to-end su 200 token.»

«Completo» è contraddetto dall'analisi dell'assistente stesso a L2555 [20:36:39Z]:
324 simboli del fork mancano nel tronco, e fra questi l'intera superficie di manopole della
politica (`VRAM_PREFER_EXPERT_VICTIM`, `VRAM_BACKBONE_RESERVE_MB`, `THRASH_LIMIT/WINDOW`,
`MIN_EXPERT_SLOTS`, i 17 `EXPERT_TIER_*`) mentre `choose_victim` è portato. *«Il porto è
14/14 sui blocchi ma non sulla superficie di politica.»* E il 2,35 è un END2END su 200
token, cioè un numero di transitorio.

### 2.10 «Nel tronco portato non gira niente di nostro» — L1984 [17:05:18Z]

> «Tutto quello che abbiamo trapiantato oggi — 18.041 righe, sei fixture verdi — è
> compilato dentro il binario e **non viene mai chiamato dal decode**.»

Vero per `C_190059`, falso come proprietà del porto: bastava togliere
`DS4_CUDA_VRAM_EXPERT_CACHE=1` e aggiungere `PREFILL_MASS_WRAP=1` perché l'arena si
accendesse (`C_191603`, L2098 [17:18:58Z]). Sulla stessa riga l'assistente aveva costruito
mezza serata di diagnosi sopra la stringa `hot_path=disconnected`, che Codex ha poi
mostrato essere **una costante stampata senza condizioni** (L2046 [17:12:42Z]).

### 2.11 «Il motore nuovo va più forte» — la cornice di tutta la serata

Non c'è una singola frase da citare: è il quadro dentro cui sono stati raccontati i run 14,
15, 16 e 17. L'utente lo formula lui stesso a L3038 [21:25:04Z]: *«ma non avevamo detto che
era merito del nuovo motore andare più veloci con vecchi pesi?»*. La risposta, a L3145
[21:33:39Z], è che il binario di tutti quei run si stacca da upstream il **12/05/2026** con
314 commit mancanti, non ha DSpark (2 riscontri contro 1224), non ha il Markov (0 contro
169) e non ha la route Q4_K nel dispatcher CUDA (0 in `ds4_cuda.cu` contro 7 nel tronco).

### 2.12 Il numero che regge ma con un buco aperto: «+17% ai pesi nuovi»

`A_212319` (4,49) contro `A_221606` (3,83) è l'unico confronto a variabile singola
sopravvissuto — stesso binario, stesso ctx, stesso preset, stesso prompt, cancelli di
promozione verificati identici dal log (L2623 [20:50:29Z]). Ma va detto cosa manca:

- **`A_221606` ha una finestra contaminata** dal `git add`+`commit` che l'assistente ha
  fatto su `C:` durante il run (gen 4200–4750, da 3,85 a 1,96 t/s). Il REGIME «pulito» è
  ricalcolato escludendo 15 campioni.
- **La verifica simmetrica su `A_212319` non è mai stata fatta.** L2604 [20:47:20Z]:
  *«non ho verificato se anche il run dei pesi nuovi avesse una finestra contaminata. Lo
  controllo appena questo finisce»* — nel transcript non risulta che sia stato fatto.
- La percentuale è cambiata tre volte nel corso di un'ora (+13,4% a L2604, +16,6% a L2773,
  +17% a L3169) senza che i due numeri sottostanti cambiassero.

---

## 1-bis. CRONOLOGIA — I RUN DELLA NOTTE (dopo la scoperta)

Aggiunta scritta dopo che la sessione è proseguita oltre le 21:41Z. Sono i primi run in cui
il **tronco** riceve un carico vero, e sono anche i primi con la catalogazione su disco.

| # | ora | tag | braccio | binario | pesi | ctx | tok chiesti | tok generati | esito | risultato |
|---|---|---|---|---|---|---|---|---|---|---|
| 18 | 23:43:37 | `C_234337` | C | **tronco** | `C:` DS4-0731-IQ2XXS | 10000 | 8000 | 600 | **interrotto** (caduta del processo Claude) | `avg 1,53`, END2END 1,526, **REGIME 1,70 su n=6** (ricalcolato 1,69). `[arena] allocated mapped-pinned=29.999 GiB slots=4551`, residenza salita a 4096, 5 ricarichi del modello. RAM libera da 55,1 a 4,0 GB, 91.870 hard fault/s. Output **PERSO** |
| 19 | 23:54:32 | `C_235432` | C `-NoStreaming` | **tronco** | `C:` DS4-0731-IQ2XXS | 10000 | 8000 | 0 | **FALLITO** | `16,37 → 27,52 → 32,07 → 39,99 → 47,77 → 48,43 GiB`, poi `CUDA model arena alloc failed for tensor-span:99 (1792,00 MiB): out of memory`. Stesso span, stessa richiesta di `C_194024` quattro ore prima |
| 20 | 23:56:34 | `B_235634` | B (nudo) | **tronco** | `C:` DS4-0731-IQ2XXS | 10000 | 8000 | 1340 | **interrotto su richiesta** | `avg 2,59`, END2END 2,595, **REGIME 2,71 su n=21** (ricalcolato identico). Prefill 19,0 s contro i 66,6 s del run con arena. RAM libera 50 GB. Output **salvato**: 237 KB di `stream.ndjson`, 1339 delta — ma tutto `reasoning_content`: la pagina non è mai iniziata |

Il quadro a tre celle, tutti e tre sugli stessi pesi 0731, ctx 10000, prompt della campagna
(sha256 `38f6ec5e…`), stessa macchina:

```
fork (ds4-p4a, maggio) + politica intera        REGIME 4,49    A_212319
tronco nudo (upstream 28/07 + 14 blocchi)       REGIME 2,71    B_235634    −39%
tronco + la nostra arena da 30 GiB              REGIME 1,70    C_234337    −62%
tronco + arena SENZA --ssd-streaming            non parte      C_235432
```

Le riserve su questo quadro sono in §3.3 e §3.12: non è motore-contro-motore.

---

## 3. COSA RESTA VALIDO

Criterio di ammissione: la conclusione non deve dipendere da *quale binario girava*, oppure
deve essere un confronto a variabile singola **sullo stesso** binario. Per ciascuna voce dico
su cosa poggia e **cosa la falsificherebbe** — se non c'è un modo di smentirla, non è un
risultato.

### 3.1 Il motore misurato per tutta la serata era il fork di maggio

```
fork    codex/prep4-mtp-secondary-map   si stacca a 8809b90, 12/05/2026
                                        314 commit di upstream mancanti
tronco  port/upstream-substrate         0 commit mancanti + i 14 blocchi
```

**Poggia su**: `git merge-base` contro `upstream/main` (L3145 [21:33:39Z]); conteggi sui file
(`dspark` 2 contro 1224, `markov` 0 contro 169, `Q4_K` 37 contro 68 e **0 contro 7 nel
dispatcher `ds4_cuda.cu`**); e, indipendentemente, sul marcatore `[host-pin]` presente in
tutti i 13 log del braccio A e assente in tutti e 7 quelli del tronco.

**Falsificherebbe**: trovare `[host-pin]` in un log del tronco, o un `merge-base` diverso.

### 3.2 Non esiste nessun rilascio di *motore* «0731»

```
GitHub  antirez/ds4  main = 54b36ed, 28/07/2026   nessun commit dopo, nessun tag
                     rami: main, ds4f-mxfp4, glm5.2, laguna-s2.1, responses-api
HF      scheda 0731  «requires DwarfStar (ds4)»   nessuna versione minima
```

**0731 è la data dei pesi**, non del runtime. Quindi l'ultimo DwarfStar *è* il motore nuovo, e
`ds4-port` ce l'ha per intero.

**Poggia su**: verifica contro il remoto fatta in diretta — `git ls-remote --heads --tags` e le
schede via WebFetch (L3183 [21:38:37Z], L3193 [21:39:33Z]). È la risposta alla domanda
dell'utente L3173, ed è l'unico punto della serata in cui una fonte esterna è stata
consultata prima di concludere.

**Falsificherebbe**: un tag o un commit successivo sul remoto.

### 3.3 Il tronco misurato per la prima volta — con tre riserve dichiarate

I numeri sono in §1-bis. Reggono come **misure**, non come verdetto sul motore.

**Poggia su**: tre run consecutivi, stessa notte, stessa macchina, stessi pesi, stesso ctx,
stesso prompt con hash verificato; REGIME ricalcolato da me sui log e coincidente
(C_234337 1,69 su n=6; B_235634 2,71 su n=21; A_212319 4,50 su n=122).

**Le tre riserve, tutte da mettere sul tavolo insieme al numero**:

1. **`C_234337` ha n=6.** Sei campioni, e il run è morto per la caduta del processo Claude,
   non per un cancello. Non è un REGIME robusto.
2. **I due run del tronco erano ancora in fase THINKING** quando sono stati fermati, mentre
   `A_212319` era uscito dal ragionamento a gen 200 (§3.5). Non è lo stesso carico di token.
3. **Il braccio C non aveva la cache esperti attiva** (§3.13). Quel run non è «0731 con la
   nostra politica»: è 0731 con un'arena orfana.

**Falsificherebbe il verdetto (non le misure)**: rifare C con `STREAMING_EXPERT_CACHE_N=320`
letto davvero, e con `think=false`, e ottenere più di 2,71.

### 3.4 `--ssd-streaming` è obbligatorio su questa macchina

Senza, upstream imbocca il percorso avido e vuole il modello **intero** in host: sale a
48,43 GiB e muore chiedendo altri 1792,00 MiB per lo span 99. Il modello è 80,76 GiB su 64 GB
di RAM: non è configurazione, non ci sta.

**Poggia su**: due run indipendenti a quattro ore di distanza, con **pesi diversi** e con il
braccio C prima e dopo la correzione — `C_194024` (19:40, pesi vecchi) e `C_235432` (23:54,
pesi 0731). Stesso span, stessa taglia di chunk, stesso messaggio. Più il codice: il bivio è a
`ds4.c:56636`, e a `ds4.c:56805-56812` il fallimento è trattato come **fatale** benché il
messaggio dica *optional* (L3451 [21:59:04Z]):

```c
if (!accelerator_cache_model_tensors(...)) {
    fprintf(stderr, "ds4: %s failed to prepare optional model cache\n", ...);
    ...
    ds4_engine_close(e);   /* "optional", e poi chiude il motore */
    return 1;
}
```

**Due conseguenze che ne discendono, non ipotesi**:
- la **doppia residenza è strutturale**, non un nostro errore di configurazione;
- **DSpark è bloccato per costruzione**: `ds4.c:55951` vuole `--mtp` insieme a `--dspark`, e
  `ds4.c:56365` rifiuta `--mtp` insieme a `--ssd-streaming`, che è obbligatorio.

**Falsificherebbe**: un ramo di ripiego che renda quel fallimento davvero opzionale (è il
lavoro «una residenza sola»), oppure più RAM.

### 3.5 Tutti i run della serata avevano il ragionamento acceso

Il server accetta `"think": false` nel corpo della richiesta (`ds4_server.c:3292`, letto con
`json_bool`); l'harness non lo passava mai. Verificato sui delta dello stream: il modello
emette `reasoning_content`, non `content`.

```
A_212319   fork, pesi nuovi     esce dal pensiero a gen 200
A_221606   fork, pesi vecchi    esce a gen 550
C_234337   0731 + arena         ancora pensante a gen 600    (fermato)
B_235634   0731 nudo            ancora pensante a gen 1340   (fermato)
```

**Poggia su**: L3532 [22:07:01Z], L3537 [22:07:30Z], L3565 [22:09:15Z], e sul file
`B_235634.thinking.txt` (5149 caratteri di solo ragionamento).

**Conseguenze**: le pagine di riferimento della campagna (`RIF_GSPEC`) sono HTML puro senza
ragionamento, quindi **nemmeno il carico era lo stesso**; i REGIME del tronco sono misurati
interamente in fase di ragionamento e quelli del fork no; e anche il confronto fra i due run
del fork (§3.16) ha frazioni di pensiero diverse, 200 token contro 550.

**Falsificherebbe la sua rilevanza**: una coppia di run con `think=false` che dia gli stessi
rapporti.

### 3.6 «Il modello è letto senza buffering» è FALSO su Windows

```
Windows   src/platform/os_file.c:100
          CreateFileW con FILE_ATTRIBUTE_NORMAL | FILE_FLAG_RANDOM_ACCESS | FILE_FLAG_OVERLAPPED
          NIENTE FILE_FLAG_NO_BUFFERING  ->  le letture SONO bufferizzate
          lo stesso handle alimenta CreateFileMappingW / MapViewOfFile (os_mmap.c:44-49)
Linux     CUDA tenta un secondo open(..., O_RDONLY | O_DIRECT) a ds4_cuda.cu:5855
          disattivabile solo con DS4_CUDA_NO_DIRECT_IO
```

**Poggia su**: lettura del codice da parte dell'agente Codex «moeio», riportata a L3718
[22:31:17Z]. È una **smentita** dell'ipotesi dell'assistente formulata a L3451 [21:59:04Z].

E cade anche l'osservazione che la sosteneva: `SystemCacheResidentBytes` **non conta le pagine
dei file mappati in memoria**. Il modello è mappato con `MapViewOfFile`, quindi le sue pagine
stanno nel working set del mapping e nella lista standby, non nella system cache. I «3,6 GB di
page cache con 50 GB liberi» citati più volte non misuravano quello che si credeva — è il
quarto contatore letto male in una giornata.

**Resta vero il dato grezzo**: 229 IOPS a coda 2. Solo che la causa non è il buffering, e le
leve di coda diventano più promettenti, non meno.

### 3.7 Il disco non è degradato: è la forma delle richieste

```
durante diskpart compact   lettura 574,0 MB/s + scrittura 595,3 MB/s   96% attivo
durante un run             58,9 MB/s, 971 letture/s, coda 8, 8,2 ms di latenza media
piu' tardi                 48,4 MB/s, 229 IOPS, coda 2
durante il thrashing       518 MB/s, 528 IOPS, coda 2, 91.870 hard fault/s
```

**Poggia su**: misure CIM sullo stesso disco a un'ora di distanza (L1774 [15:47:40Z]), poi
L2696 [20:57:49Z] e L3299 [21:49:54Z]. Indipendente da quale binario girava: è una proprietà
del supporto e del pattern di accesso.

**Attenzione a cosa NON poggia su cosa**: la lettura «coda 1 perché il binario dichiara
`file_qd=1`» non è sostenuta. Il rapporto Codex sul wrap avverte che `file_qd_observed` è
inizializzato a 1 *prima* di sapere se la sorgente sarà mmap o file, e che i contatori
`submits`/`completions` si muovono solo nella routine overlapped (L1808 [16:03:14Z]). La coda
2 misurata dal sistema operativo regge; il contatore del binario no.

### 3.8 L'aritmetica della VRAM e la catena della vittima — **sul fork**

Tabella ricostruita dai log, riproducibile in qualunque momento
(capacity / `free_at_size_mib` / righe `no-expert-victim`):

```
A_161639   143   1094,0    51        A_184751   306   2199,9     0
A_162323   143   1093,9   981        A_204202   318   2275,2     0
A_163938   134   1033,2   160        A_211311   311   2229,2    17
A_165653   135   1040,6   637
A_171406   135   1045,2   284
------------------------- chunk 2048 -> 256 -------------------------
```

Il conto torna a mano: `(free_at_size − 128 MiB di riserva) ÷ 6,75 MiB per esperto`.

**Poggia su**: aritmetica di VRAM, che il volume dei log non tocca. È un **argomento di
codice, non sperimentale**, e va detto perché: la soglia del chunk coincide esattamente con la
ricostruzione del binario delle 17:23. Il diff di quella ricostruzione (commit `a6c764e`,
28 inserzioni e 11 cancellazioni in `ds4_cuda.cu`) tocca **solo** la guardia del verbose, che
non può cambiare quanta VRAM è libera.

**Falsificherebbe**: un run col binario precedente e `prefill_chunk=256` che dia comunque
capacity 135.

**Vale solo sul fork.** Su 0731 il dimensionamento sta a `ds4_cuda.cu:26817` e la stampa
`[iq2-expert-cache-size]` non era stata portata affatto (L3639 [22:22:04Z]).

### 3.9 Su 0731 la catena della vittima NON esiste — quindi metà della cura non serve

> Nel fork la politica vittima opera su `g_model_ranges`, un pool **misto** dove i range
> esperto sono sfrattabili e quelli backbone sono `pinned`. In 0731 il model cache non ha né
> selettore LRU né sfratto a caldo: arene append-only, e a budget esaurito ripiega sul
> puntatore diretto. `mass_lfru_policy::choose_victim` riceve **esclusivamente slot esperto
> validi**: backbone, KV e range modello non possono entrare nella lista candidati.
> In questo albero non esistono le stringhe `reason=no-expert-victim` e
> `victim_category=backbone`.

**Poggia su**: rapporto dell'agente Codex «vittima», L3639 [22:22:04Z]. Letto nel codice, non
misurato.

**Falsificherebbe**: un grep che trovi quelle due stringhe in `ds4-port`.

**Conseguenza pratica**: metà del mandato «vittima» va dichiarata non portabile, e va bene
così — non si simula un guasto per poterlo curare.

### 3.10 Il porto ha trasferito i meccanismi, non le politiche

Delle 33 variabili del preset del fork: **10 esistono** nel tronco, **23 no**, **0 erano attive**
nel run del braccio B.

```
esistono   DYNAMIC_ARENA_GB, PREFILL_MASS_OBSERVE, PREFILL_MASS_WRAP,
           le quattro ARENA_WRAP_*, NO_Q8_F16_CACHE,
           STREAMING_EXPERT_CACHE_RESERVE_GB, TRANSIENT_DEADLINE_ADAPTIVE

non esistono   EXPERT_TIERING, EXPERT_TIER_POLICY, EXPERT_TIER_ADMIT_KNOCKS_SSD (leva
               PROMOSSA, +4,0% misurato), _HYSTERESIS, _MIN_FREQUENCY, _CLOCK_CALLS,
               _REPLACEMENT_BUDGET, G133_TIER/_KNOCK_X/_ROTATOR_IO_TIMEOUT_S,
               G73_OPEN (quella dell'8x), MOE_CACHE_POLICY, MOE_GPU_RESIDENT_ROUTES,
               MOE_ROUTE_NO_DEFAULT_SYNC, PREFILL_TIER_COMPOSE/_RESERVE_SLOTS/_ROUTER,
               STREAMING_EXPERT_CACHE_N, STREAM_FROM_RAM_MASKED_BUDGET_GB,
               REAP_PREFETCH_THREADS

famiglie intere assenti   DS4_CUDA_REAP_MASS_*  (il reap-loop)
                          DS4_SPEX_*
                          VRAM_PREFER_EXPERT_VICTIM, VRAM_THRASH_LIMIT/_WINDOW
                          PRESERVE_ACROSS_REQUESTS
                          MOE_IO_QD, G73_ROUTE_IO_QD
KV_STAGED_RING            esiste, ma spento
```

**Poggia su**: conteggio nome per nome contro l'albero del tronco (L3490 [22:04:37Z]), e prima
ancora sul conteggio dei simboli — 324 simboli del fork assenti, `choose_victim` portato ma non
le sue manopole, 219 leve del tronco che il fork non ha (L2555 [20:36:39Z]).

**Conseguenza che riqualifica tutti i confronti**: 4,49 contro 2,71 non è motore contro
motore. È **politica intera contro upstream nudo**.

### 3.11 Cosa il tronco stampa e cosa no

Confronto riga per riga fra `C_191603` (tronco) e `A_212319` (fork), L3252 [21:44:28Z]:

```
                          TRONCO   FORK
[arena-cap]                   0      1        [vram-prio]              0    123
dynamic arena ready           0      1        [vram-ledger]            0      2
[prefill-mass]                0      9        [host-pin]               0      7
[prefill-mass-compose]        0      3        [arena-wrap]             0      5
[arena] publish               0      1        [iq2-expert-cache-size]  0      1
```

Le uniche due righe nostre che il tronco stampa sono `[arena] allocated` e `[arena] snapshot`.

**Poggia su**: conteggio sui log; l'ho riverificato — `C_191603` ha 44 righe `[arena]` e zero
`prefill-mass`, `vram-prio`, `iq2-expert-cache-size`.

**Corollario**: `hot_path=disconnected` non è un segnale. È una stringa letterale stampata
senza alcuna condizione (`dynamic_arena.cu:481`, `:1308`), e la fixture la scrive lei stessa
(L2046 [17:12:42Z]). Mezza serata di diagnosi ci è stata costruita sopra.

### 3.12 Sul tronco l'arena, così com'è, costa

```
                        REGIME   prefill   RAM libera   hard fault/s
tronco nudo              2,71     19,0 s      50,0 GB        —
tronco + arena 30 GiB    1,70     66,6 s       4,0 GB     91.870
```

Il meccanismo è misurato, non dedotto: l'arena è **pinnata** (`mapped-pinned=29.999 GiB`),
quindi Windows non può sfrattarla; restano ~3,5 GB alla page cache per servire un modello da
80 GB, e i 91.870 hard fault/s a 4 KB fanno ~360 MB/s dei 518 MB/s letti su C:. In più
l'arena copre solo 4096 slot × 6,75 MiB = 27 GiB su 72,56 GiB di esperti, cioè il 37%: si paga
la strada veloce per una minoranza togliendo la RAM alla maggioranza (L3299, L3308, L3313).

**Poggia su**: due run consecutivi a variabile singola (le tre variabili del braccio C), stessa
notte, stessi pesi, stesso ctx, stesso prompt.

**La riserva è grossa e va detta**: in `C_234337` la cache esperti non era attiva (§3.13),
quindi il confronto è «arena orfana contro niente», non «la nostra politica contro niente».

**Falsificherebbe**: rifare C con la cache accesa e ottenere più di 2,71.

### 3.13 Il braccio C era configurato male, e la ragione è tracciabile

Su 0731 la cache esperti si attiva **solo** con budget non nullo **e** con la cache VRAM
opt-in; il gate è `DS4_CUDA_VRAM_EXPERT_CACHE=1`, e prima di questo porto
`DS4_CUDA_STREAMING_EXPERT_CACHE_N` non era letto da nessun file di 0731. Il tiering conferma
dall'altro lato: configurazione cablata alle costanti mass-LFRU `430/3/1.25/0.95`, budget `16`,
**gate `DS4_CUDA_VRAM_EXPERT_CACHE=1`** (L3639 [22:22:04Z]).

Il commento che l'assistente aveva messo nel braccio C — *«`DS4_CUDA_VRAM_EXPERT_CACHE` NON va
acceso insieme all'arena: si escludono»* (commit `6aaa619`) — veniva da un rapporto precedente
che diceva anche che `requested_slots`/`expert_bytes` li valorizza il core **solo sotto
`--ssd-streaming`** (`ds4.c:53898`). Il braccio C gira con `--ssd-streaming`: quei campi ci
sono, il budget non è zero, il sabotaggio non si applica.

**Poggia su**: lettura del codice da parte di due agenti indipendenti che convergono.

### 3.14 DSpark: cosa si sa, e perché non basta saperlo

```
--dspark, --dspark-confidence <0..1>, --dspark-strict   ds4_server.c:13002
le DS4_DSPARK_* sono tutte di tipo DISABILITA
riserva 4,5 GiB: NON ci tocca — engine_install_dspark_support_cache esce se
                 !e->multi_tier (ds4.c:55497), e multi_tier=1 solo con piu' tier (ds4.c:55184)
guardiano 1      ds4.c:55951   --dspark senza --mtp -> esce
guardiano 2      ds4.c:56365   --mtp con --ssd-streaming -> esce
e->ssd_streaming = opt->ssd_streaming   ds4.c:55921   assegnazione unica, dal flag CLI
conteggi         dspark 2 vs 1224, flag --dspark 0 vs 3, kernel markov 0 vs 7
```

**Poggia su**: lettura del codice del tronco (L2569 [20:39:02Z], L3234 [21:43:20Z]). Corregge
due affermazioni precedenti dell'assistente — «non c'è un interruttore» e «ci costa 4,5 GiB» —
entrambe false.

**Combinato con §3.4**: il guardiano non è il muro, il muro è che `--ssd-streaming` non si può
togliere. **DSpark è irraggiungibile finché upstream non prende i byte dall'arena.** Non è una
configurazione da trovare, è codice da scrivere.

### 3.15 Route Q4_K nel tronco, e il falso allarme sul nostro file

7 riscontri nel dispatcher MoE del tronco (`ds4_cuda.cu:24254`) contro 0 nel fork. Ma il file
che abbiamo **non** è la build mista:

```
DS4-0731-IQ2XXS.gguf   86.720.111.488 byte
ds4-2bit.gguf          86.720.111.488 byte      differenza: 0
primi 64 KB            identici
offset 0,1 / 1 / 10 / 40 / 73,6 / 80,7 GB   DIVERSI a ognuno
```

È il Q2 piatto da 80,76 GiB, non la variante da ~98 GB con Q4_K sugli strati 37-42. Quindi
girare i pesi 0731 sul fork non ha incontrato un tipo non dispacciabile, e nei log non c'è
nessuna lamentela (L3193, L3198, L3220 [21:39–21:41Z]).

**Poggia su**: confronto binario a campione su sette offset più i metadati. È anche la prova
che il file è un **drop-in**: stessa geometria, stesso schema di tensori, pesi diversi.

**Falsificherebbe**: passare alla build mista, dove il fork perderebbe la route.

### 3.16 Il +17% dei pesi nuovi — la parte che regge

`A_212319` (4,49) contro `A_221606` (3,83), stesso binario, stesso ctx 10000, stesso preset,
stesso prompt. I cancelli sono identici, letti dal log e non dallo script:

```
                       A_212319 (nuovi)   A_221606 (vecchi)
arena requested_gib        29.999             29.999
slots / capped           4551 / 0           4551 / 0
prefill-mass         router=unbiased residency=prefill-ranked policy=bulk-wrap  (identici)
capacity                    4423               4423
backbone_reserve_mib      1536,0             1536,0
cache richiesta/concessa  320 / 274          320 / 274
free_at_size_mib          1977,5             1977,7
candidate_fnv1a64   1d12a58d0b6da1d8   24404c372d1c0364     <- DIVERSE
```

**Poggia su**: L2623 [20:50:29Z] più la verifica della geometria del file (§3.15). L'ipotesi
dell'utente — che gli sfratti venissero da una politica di promozione più aggressiva — è
**smentita con i numeri**: i cancelli non sono cambiati, è cambiato il working set instradato.

**I buchi, tutti aperti**: la finestra contaminata di `A_221606` (§2.12), la verifica
simmetrica mai fatta su `A_212319`, e adesso anche la frazione di ragionamento diversa fra i
due (esce a gen 200 contro gen 550, §3.5). Il numero resta il migliore che abbiamo, ma non è
pulito come è stato raccontato.

### 3.17 L'igiene degli strumenti — quello che è stato costruito e provato

- **L'endpoint di spegnimento portato a mano** (commit `4d0ca34`) funziona: verificato vivo su
  `A_161639`, uscita pulita, `teardown result=clean`, VRAM a 671 MiB (L1326 [14:20:59Z]).
- **`CTRL_BREAK_EVENT` chiama la stessa `server_request_stop()` dell'endpoint, senza token**
  (L2900 [21:12:57Z]). Usato per chiudere `A_221606` e `B_235634`.
- **Il preflight** è l'unica cosa costruita nella giornata che ha *impedito* un errore invece
  di scoprirlo dopo: a L2225 [18:06:57Z] ha escluso l'ipotesi «macchina sporca» con VRAM,
  RAM, daemon e uptime dichiarati.
- **L'harness buttava via l'output**: leggeva `usage.completion_tokens` e scartava
  `choices[0].message.content`. **Tutti i `.log.out` sono a 0 byte** — l'ho riverificato:
  `find -size +0c` non restituisce nessun file. Corretto con lo streaming su disco via `curl -o`
  (commit `bf5f8cf`, L3367 [21:54:25Z]) e **provato**: `B_235634` ha lasciato 237 KB e 1339
  delta pur essendo stato interrotto.
- **Le 7 pagine sopravvissute**: 4 su 7 troncate dentro il foglio di stile, zero sezioni, zero
  JS, zero form. Fra queste `X_CTL8K`, usata come colonna di riferimento per tutta la serata
  (L2951 [21:16:15Z]).
- **I Codex non riescono a committare nei worktree**: i metadati git stanno in
  `ds4-p4a/.git/worktrees/<nome>`, **fuori** dalla radice `-C`, e il sandbox `workspace-write`
  non li vede — `Unable to create index.lock: Permission denied` (L3661 [22:25:40Z]). Il lavoro
  resta sul disco, i commit no: deve committare il coordinatore.

### 3.18 I quattro bracci del tronco della sera non erano guasti

`B_185751`, `C_190059`, `C_191603` chiudono tutti con `shutdown requested, draining requests`
dopo aver servito esattamente i token richiesti. L'unico fallimento vero è `C_194024`
(L3162 [21:35:16Z]). Verificato nei log.

**Perché conta**: la frase «massimo 200 token, zero REGIME» suonava come fragilità del motore
nuovo, ed è stata usata per giustificare il ritorno sul braccio A. Non era fragilità: non gli
era mai stato chiesto di più.

---

### Cosa resta APERTO (non concluso, da non scambiare per risultato)

| domanda | stato |
|---|---|
| Quanto costa il substrato upstream a **parità di politica** | non separabile finché le 23 variabili non sono portate; i quattro Codex della notte stanno lavorando esattamente a questo (~2650 righe alle 22:33Z) |
| Perché `PREFILL_MASS_OBSERVE/WRAP` esistono su 0731 e non stampano una riga | domanda messa nel mandato «prefill» (L3629 [22:15:28Z]); **risposta non trovata nel transcript** |
| Perché la residenza dell'arena si ferma a 4096 slot su 4551 allocati | *«o ha finito la domanda, o c'è un tetto»* (L3313 [21:50:47Z]); **non risolto nel transcript** |
| L'anomalia dei 28.672 sfratti identici negli appunti del 31/7 e in `A_212319` | sospetta trasposizione di colonne; **mai verificata** |
| `G73_OPEN` a variabile singola sul binario corrente | il run è morto a 7 righe (`A_190939`); **mai rifatto** |
| Il REGIME 4,48/4,49 del riferimento 31/7 | **mai letto dal suo log**, viene dagli appunti (L3021 [21:22:03Z]) |

---

## 4. LE CORREZIONI CHE L'UTENTE HA DOVUTO FARE

Trentasette interventi in dieci ore (contati come voci qui sotto; alcune raggruppano due o più
messaggi consecutivi sullo stesso punto). Per ciascuno: cosa aveva detto l'assistente, cosa ha
corretto l'utente, e se l'assistente ha poi **verificato** con un dato oppure si è limitato a
**concordare**. Le parole dell'utente sono riportate testuali quando sono nette.

### 14:35:17Z — L1362 · la RAM pageable

L'assistente stava riportando `0,33 t/s` come misura del braccio A.

> «Io vedo ram 10 gb sopra la solita soglia hai acceso ram pageable? Performance veramente
> scadenti»

**Verificato.** Ha letto il preset e trovato `DS4_G73_PAGEABLE_OVERFLOW_GB=14` **e**
`DS4_G73_OPEN=1`, ereditati in blocco da `g73_open.env.ps1` — un file di *test*, non il preset
della campagna (L1368, L1372 [14:35:54Z, 14:36:31Z]). Il ledger documentava `G73_OPEN=0` come
otto volte più veloce.

### 14:36:42Z — L1377 e 14:37:43Z — L1392 · il ledger

> «Spiegami perché siamo passati a una configurazione completamente diversa da quelle di
> stamattina che giravano bene?»
>
> «**Ma guarda il ledger coglione**»

**Verificato.** Ha cercato il preset *registrato* nei manifest dei run e ha prodotto la tabella
registrato-contro-usato (L1389 [14:37:57Z]). Ma la cura ha generato il guasto successivo: ha
sostituito in blocco la configurazione con una presa da `ledger:12945`, una sezione vecchia
scritta per un altro binario, e due run si sono appesi.

### 14:50:00Z — L1429 · il disco

L'assistente stava attribuendo la lentezza alla configurazione.

> «Hi capito il problema, stiamo girando da D»

**Verificato in trenta secondi**: `C:` = Lexar EQ790 NVMe, `D:` = EMTEC X160 SATA, dischi 1 e 0
(L1435 [14:50:28Z]). Reso strutturale: `C:` come default nello script con la ragione scritta in
commento. Quattro run — `A_161600`, `A_161639`, `A_162323`, `A_163938` — erano già stati fatti
sul disco sbagliato.

### 14:51:18Z — L1447 · chi deve guardare la macchina

> «Sono cose che dovresti guardare tu, non io da task manager»

**Risposta strutturale**, non solo verifica: ha aggiunto al lanciatore un preflight che stampa
disco, VRAM, RAM, uptime, daemon vivi e l'intero preset **prima** di ogni lancio (L1454
[14:52:06Z]). È l'unica cosa costruita quel giorno che poi ha *impedito* un errore invece di
scoprirlo dopo (§3.17).

### 15:01:51Z — L1493 · i contatori del disco

L'assistente aveva scritto «nessuna lettura sopra 1 MB/s, sta copiando dalla page cache».

> «[immagine] Per me leggi dati errati»

**Verificato e ammesso**: aveva usato `Get-Counter` con **un solo campione**, e i contatori di
rate ne vogliono due per calcolare la differenza. Il disco era al 100% (L1498 [15:02:26Z]).
Passato a CIM, che è neutro rispetto alla lingua dei contatori.

### 15:04:07Z — L1513 e 15:05:57Z — L1522 · il disco non è la causa

L'assistente stava per attribuire tutto a un NVMe degradato e pieno all'89%.

> «Il disco è sempre andato così!!»
>
> «Non è mai stato normale che quel disco leggesse a 60mb/s anche se si tratta di dati molto
> sparsi…ci torneremo poi»

**Prima concordato** («allora la mia ipotesi cade»), **poi verificato per caso** tre quarti
d'ora dopo: durante la compattazione WSL lo stesso disco faceva 574 MB/s in lettura contro i
58,9 del run (L1774 [15:47:40Z]). La seconda frase dell'utente è rimasta aperta per ore e ha
poi ricevuto la risposta giusta in §3.7.

### 15:10:56Z — L1559 · la macchina degradata

> «Questo run ha la forma di macchina degradata»

Qui l'assistente **ha resistito alla suggestione e ha verificato**: l'aritmetica torna
(1045 MiB liberi − 128 di riserva ÷ 6,75 MiB = 135 slot), quindi non è degrado, è un budget
(L1565 [15:11:58Z]). Una delle poche volte in cui una misura ha contraddetto l'utente.

### 15:15:16Z — L1584 · il verbose

L'assistente aveva identificato il diluvio di log e aveva lanciato lo stesso.

> «Ma hai tolto tutto quel verbose dai log che scriveva a 20 mb/s?»

**Ammesso senza attenuanti** («No, non l'ho tolto. L'ho identificato e poi ho lanciato lo
stesso — errore mio»), poi **verificato nel codice** — è un `fprintf` senza guardia a
`ds4_cuda.cu:45176` (L1594 [15:16:09Z]) — e infine **corretto in codice**: commit `a6c764e`,
che ha scoperto anche che le due stampe stavano *dentro* il ramo della leva promossa
`DEADLINE_ADAPTIVE`, quindi la misura del 31/7 «a costo zero» includeva quel costo.

### 15:46:18Z — L1763 · i 38 GB di WSL

L'assistente aveva scritto che `.wslconfig memory=38GB` competeva con i run.

> «è sempre stato spento non compete in nulla!»

**Solo concordato**, senza misurare: «Hai ragione, ritiro: `memory=38GB` è un tetto per la VM
di WSL, e se WSL è spento non riserva niente» (L1765 [15:46:28Z]). Il ragionamento è corretto,
ma non c'è un dato dietro.

### 15:49:34Z — L1788 · delegare la lettura

> «delega codex per leggere il codice non farlo tu»

È la correzione con il rendimento più alto della giornata. Da lì in poi arrivano il rapporto
sul wrap (L1808 [16:03:14Z]), quello sul percorso caldo (L2046 [17:12:42Z]), quello sulla
residenza (L2253 [18:16:14Z]) e i quattro della notte. L'assistente lo riconosce a L2541
[16:48:04Z]: *«le prime cinque ipotesi le ho tirate a indovinare variando l'ambiente, e sono
cadute tutte. Questa viene dal codice letto … Ed è stata la tua indicazione di delegare la
lettura invece di farla io a produrla.»*

### 16:57:50Z — L1930 · le leve del SOTA

> «questo run appena fatto erano tutte le leve attive del precedente SOTA ma con nuovo guuf?»

**Verificato, e la risposta è una smentita di sé**: il GGUF è quello vecchio (il download era
fermo a 1,9 GiB su 87) e il preset è un ibrido — tre variabili ereditate dal file di test che
il preset registrato non ha, e cinque del registrato che mancano (L1936 [16:58:32Z]).

### 16:59:38Z — L1946 · a cosa stiamo lavorando

> «ma non dovevamo impiantare tutto sul nuovo guuf per l'ultima release? cosa diavolo stiamo
> facendo?»

**Ammesso**: *«ci ho fatto passare una serata, e il risultato è che stiamo confrontando un
preset ricostruito che non è nemmeno il SOTA, su pesi che non sono quelli per cui abbiamo
fatto il porto»* (L1948 [17:00:19Z]). Ha fatto ripartire il download.

### 17:01:40Z — L1957 · l'arena che non si riempie

L'assistente aveva appena lanciato il braccio C credendo di misurare la nostra politica.

> «non vedo ram rempirsi e la gpu lavora forte!»

**Verificato**: processo a 2,3 GB invece di ~32, zero righe `arena` nel log. *«C non è "il
tronco con la nostra politica accesa": è B con tre variabili che il binario ignora»* (L1961
[17:02:11Z]).

### 17:20:22Z — L2110 · l'arena da 30 l'abbiamo sempre messa

> «noi di arena pinnata mettevamo 30...non è che è intervenuto altro?»

**Verificato**, e ha aperto la questione che ha retto tutta la notte: fork 32-33 GB contro
tronco 47,4 GB **con la stessa arena** (L2112 [17:20:39Z]).

### 17:21:54Z — L2119 · il vocabolario

> «ma c che fork è? abbiamo un fork anche nel port? che casino»

**Ammessa l'ambiguità** e chiarito il vocabolario: `ds4-p4a` = il fork, `ds4-port` = il tronco
(L2121 [17:22:20Z]). Ma l'ambiguità non è stata risolta davvero: alle 21:25 l'utente dovrà
rifare la stessa domanda in un'altra forma, e sarà quella a far crollare il castello.

### 17:39:32Z — L2158 · l'arena non è il problema

L'assistente aveva appena scritto la regola generale «su 64 GB di RAM un'arena esplicita da
30 GiB peggiora la residenza invece di migliorarla».

> «**ma smetti di dire cazzate!! abbiamo sempre girato con un'arena pinnata da 30...forse ora
> stiamo facendo una cosa diversa o si somma un altro fenomeno**»

**Ritirata la generalizzazione**, e la seconda metà della frase dell'utente — *«si somma un
altro fenomeno»* — è diventata l'ipotesi giusta: la doppia residenza (L2160 [17:40:02Z]).
Subito **messa alla prova** con `-NoStreaming`.

### 17:40:45Z — L2172 · quale contatore

> «non eravamo a 47 eravamo a 60»

**Verificato**: `WorkingSet 21,0` / `PrivateBytes 32,3` / `Commit 32,3` / `VirtualSize 201,4 GB`
(L2180 [17:41:24Z]). Da lì in poi dichiara sempre quale contatore sta leggendo. È il quarto
contatore letto male in giornata, e non sarà l'ultimo (§3.6).

### 18:04:17Z — L2211 · hai davvero girato quel run?

L'assistente aveva usato i «32,3 GB» come prova della doppia residenza.

> «Hai girato arena senza streaming?»

**Verificato e ritirato**: quel run non aveva mai servito una richiesta (27 righe di log, zero
`chat ctx=`), e i 32,3 GB erano un fotogramma di un processo ancora in crescita, morto poco
dopo (L2216 [18:05:09Z]). Ha anche **corretto il mandato già inviato a Codex**, dove la riga
falsa era finita come premessa (commit `a4f84b7`).

### 18:06:15Z — L2220 · la macchina sporca

> «È probabile che arena senza streaming ora si trovi una configurazione macchina sporca»

**Verificato, e l'assistente ha detto di no**: il preflight dichiarava VRAM 584 MiB, RAM 57,0 GB
libera, 0 daemon, disco NVMe, 14 minuti di quiete dal run precedente (L2225 [18:06:57Z]). Il
fallimento era genuino.

### 19:21:24Z — L2354 e 19:22:47Z — L2372 · il prompt

L'assistente aveva annunciato «Nuovo SOTA» su un prompt generico su una funzione Python.

> «Ma dovevi fare il solito prompt per il sito web»
>
> «**Mamma mia quanto fai pena! Datti una regolata e cerca di essere più preciso e
> professionale!**»

**Verificato e corretto strutturalmente**: ha trovato il prompt vero in
`g103_iq1_cold_sota_ab.ps1`, dove è già protetto da un controllo SHA256 che aborte se cambia,
e ha messo lo stesso presidio nel lanciatore (L2368 [19:22:41Z], commit `dcc645d`). E ha
ritirato il SOTA: *«Il 4,70 di prima resta agli atti come misura di un altro carico.»*

### 20:49:16Z — L2608 · i cancelli di promozione

> «Comunque pensavo che gli sfratti forse dipendono da una politica più aggressiva di
> promozione, i gate erano identici al run precedente?»

**Verificato dal log del binario, non dallo script**, e l'ipotesi dell'utente **smentita** con i
numeri: tutti i cancelli identici riga per riga, ma impronte `candidate_fnv1a64` diverse
(L2623 [20:50:29Z]). È la verifica meglio fatta della serata.

### 20:55:30Z — L2670 · i 45-46 GB

> «[immagine] Col vecchio eseguibile viaggiavamo a 45-46 gb»

**Verificato**: WorkingSet 30,8 GB, Commit 41,8, RAM libera 22,2, page cache 3,4 (L2696
[20:57:49Z]). Da lì è nata la misura dei 229 IOPS a coda 2 — e, molto più tardi, la scoperta
che quella «page cache» non misurava le pagine mappate (§3.6).

### 20:59:49Z — L2729 e 21:01:46Z — L2750 · il KV ring

L'assistente aveva appena detto che il ring era escluso dal preset con la ragione scritta.

> «Perché nel vecchio sota in teoria era acceso proprio per spostare in ram quel valore»
>
> «Avevano un chunk in vram piccolo e il resto in ram (parlo di kv ring)»

**Verificato sull'atlante e ammesso**: la voce C-7 dice che il ring è **nella ricetta 150k
validata**, e `preset_A.ps1` l'aveva tolto — quindi il preset della serata non era la ricetta
validata, e confrontarlo col SOTA del 31/7 era confrontare due configurazioni diverse
(L2747 [21:01:44Z]). Poi **verificato nel codice** anche il meccanismo descritto dall'utente:
4 MiB × 2 slot = finestra di 8 MiB in VRAM, il resto in `host_arena` (`ds4_cuda.cu:1048`,
`:1071-1076`), e l'assistente ha corretto sé stesso — `_BYTES` e `_SLOTS` sono costanti di
compilazione, non leve (L2759 [21:02:21Z]).

### 21:09:36Z — L2849 · il catalogo

Contesto: l'assistente aveva appena scoperto che i 17 `.log.out` erano a 0 byte.

> «D'ora in avanti voglio ogni output catalogato con stesso identificativo che finisce nel
> ledger! Non vanno persi»

**Implementata subito** (commit `b024d55`) — ma **non ha funzionato alla prima prova**:
`C_234337` ha perso comunque l'output, perché l'harness teneva il testo in una variabile
PowerShell in attesa della risposta completa. Corretta davvero solo alle 23:53 con lo
streaming su disco (commit `bf5f8cf`), e allora ha retto.

### 21:18:30Z — L2983 · accantonare il vecchio

> «d'ora in avanti il vecchio binario e vecchi pesi vanno accantonati»

**Implementata subito**: il braccio A ora lancia un `throw` esplicito, sbloccabile solo con
`-Comunque` e in quel caso il tag porta `_ACCANTONATO`; default del modello sui pesi nuovi
(commit `f48e589`).

### 21:21:07Z → 21:34:25Z — L3012, L3025, L3038, L3113, L3139, L3152 · **la sequenza che ha rotto la serata**

Sei domande di fila, ognuna più precisa della precedente:

> «scusa ma il nuovo pareggio rispetto al sota con cosa l'abbiamo ottenuto?»
>
> «non era il B o C?»
>
> «ma non avevamo detto che era merito del nuovo motore andare più veloci con vecchi pesi?
> … **quando parlo di motore parlo dell'eseguibile che non era aggiornato agli ultimi commit e
> al nuovo 0731**»
>
> «**si ma non dirmi un codice di binario! è il 0731 sul quale sono stati applicati i 14
> blocchi? sennò cosa abbiamo misurato?**»
>
> «che senso avrebbe avuto fare 14 blocchi per non portarli sopra a nessun motore?»
>
> «ma che senso ha avuto misurare e sorprenderci di certi numeri usando lo stesso motore che
> abbiamo sempre usato? non capisco questa parte...»

**Verificato a ogni passo**, e ogni verifica ha peggiorato il quadro:

```
L3021 [21:22:03Z]   8 righe di log che solo il fork stampa -> il pareggio e' del fork
L3031 [21:22:55Z]   tabella dei 4 run del tronco: max 200 token, ZERO campioni di REGIME
L3045 [21:25:57Z]   date di build: il binario e' del 17:23 di OGGI, non "vecchio"
                    -> e fra A_171406 e A_184751 e' cambiato anche il binario
L3106 [21:29:45Z]   i 14 blocchi sono su port/upstream-substrate, un solo repo, worktree
L3145 [21:33:39Z]   il fork si stacca il 12/05/2026: 314 commit mancanti
```

La conclusione — *«ho misurato la cosa sbagliata per otto ore, e me ne sono accorto adesso
perché tu hai insistito»* (L3145) — è dell'assistente, ma è arrivata **alla sesta domanda**.
Il segnale era disponibile dalle 19: i log di B e C dicevano `shutdown requested, draining
requests`, cioè «ho finito quello che mi hai chiesto», non «mi sono rotto» (§3.18).

### 21:34:51Z — L3158 · la rilettura

> «cazzo delega un agente a rileggere tutta la conversazione di questa chat»

È il mandato da cui nasce questo documento.

### 21:37:53Z — L3173 · verifica le fonti esterne

> «primo, verifica github e huggingface per il motore nuovo 0731...perchè sennò continiamo a
> lavorare sull'ultimo dwarfstar ma non sul motore nuovo»

**Verificato contro il remoto**: `git ls-remote` su `antirez/ds4` più le schede via WebFetch.
Nessun commit dopo il 28/07, nessun tag, e «0731» è la data dei **pesi** (L3183, L3193
[21:38:37Z, 21:39:33Z]). Qui l'assistente ha corretto una premessa dell'utente, con la fonte
citata.

### 21:41:11Z — L3218 · il file dei pesi

> «avevamo preso il q2 di un altro utente su huggingface se non ricordo male...da 80 gb circa
> infatti avevi detto che era dropin»

**Verificato al byte**: stessa dimensione esatta, primi 64 KB identici, dati diversi a tutti e
sette gli offset campionati (L3220 [21:41:42Z]). E fa cadere il timore Q4_K che l'assistente
stesso aveva sollevato due minuti prima.

### 21:44:30Z — L3256 · cosa hai lanciato

> «**ma cosa hai lanciato ora? con che variabili? non lavorare alla cazzo**»

Ha risposto copiando il preflight per intero — binario, modello, disco, VRAM, RAM, le 5
variabili, la riga di comando, lo sha256 del prompt (L3261 [21:44:56Z]). Nessuna verifica
aggiuntiva serviva: era già stampato, non era stato mostrato.

### 21:49:54Z — L3303 · arena contro SSD

> «sicuramente con la concorrenza arena e ssd siamo limitati dall'ssd che ora gira a 700mb/s
> invece dell'arena che andava anche a 4000mb/s»

**Corretta in parte, con i numeri**: l'arena pinnata non compete per la *banda*, toglie la
*RAM* alla page cache. E ha quantificato: 4096 slot × 6,75 MiB = 27 GiB su 72,56 GiB di
esperti, cioè il 37%; il restante 63% passa dal disco con 3,5 GB di cache (L3308, L3313
[21:50:13Z, 21:50:47Z]).

### 21:50:59Z — L3317 · il disegno a tre celle

> «facciamo due run come questo ma uno con arena pinnata senza streaming e l'altro senza arena
> pinnata a e solo streaming giusto?»

È il disegno sperimentale dell'utente, ed è quello che ha prodotto **gli unici numeri validi sul
tronco**. **Eseguito**: `C_235432` (arena sola → muore) e `B_235634` (solo streaming → 2,71).

### 21:51:52Z — L3339 · gli output

> «non buttiamo via gli output come in precedenza»

**Implementata e provata**: `curl` in streaming con `-o` su `<tag>.stream.ndjson`, così i byte
toccano il disco mentre escono (commit `bf5f8cf`). La prova che ha funzionato è arrivata subito
dopo: 237 KB e 1339 delta sopravvissuti a un'interruzione.

### 22:00:56Z — L3469 · più veloce di cosa

L'assistente aveva usato due «più veloce» con due metri diversi nello stesso messaggio.

> «hai appena detto che il modello nuovo con pesi nuovi è più veloce? ma di cosa?»

**Ammessa l'ambiguità** e rifatta la classifica con un metro solo (L3474 [22:02:08Z]):

```
fork (motore di maggio)          4,49    <- il piu' veloce, ancora adesso
tronco nudo                      2,73    -39%
tronco + la nostra arena         1,70    -62%
tronco + arena, senza streaming  non parte
```

con la frase secca: *«il motore nuovo con i pesi nuovi è più lento del motore vecchio con gli
stessi pesi. Non ho mai misurato un vantaggio del tronco, e non ce n'è uno.»*

### 22:03:38Z — L3478 · le nostre variabili sono attive?

> «si ma ancora le nostre variabili di reap loop kv ring ecc non sono attive giusto?»

**Verificato con un conteggio nome per nome**: 10 esistono, 23 no, 0 attive nel run in corso;
famiglie intere assenti, reap-loop compreso (L3490 [22:04:37Z]). È la correzione che
riqualifica tutti i confronti — *«non stiamo confrontando due motori: stiamo confrontando un
motore vestito con uno in mutande»*.

### 22:08:33Z — L3551 · il ragionamento

> «**ancora pensante perchè non hai messo nothink coglione**»

**Verificato nel codice**: il server accetta `"think": false` nel corpo (`ds4_server.c:3292`,
letto con `json_bool`); il `nothink=1` della campagna era solo l'annotazione nel manifesto.
L'harness non lo passava (L3565 [22:09:15Z]). Conseguenza dichiarata: **tutti i run della
serata hanno pensato**, e le pagine di riferimento della campagna no — quindi nemmeno il
carico era lo stesso (§3.5).

### 22:06:09Z, 22:09:59Z, 22:10:31Z — L3520, L3588, L3597 · porta le variabili

> «fatta eccezione per spex porta tutte le variabili utili nel tronco che ora chiameremo 0731»
>
> «basta porta le nostre variabili e patch sul motore 0731»
>
> «usa vari agenti codex e riconcilia...**datti anche una mossa coglione**»

**Eseguito**: quattro worktree, quattro Codex in parallelo (`vittima`, `tiering`, `moeio`,
`prefill`), con tre vincoli in ogni mandato — additivo e spento di default, promozione e
pruning invariati, deve compilare. Alle 22:33Z: ~2650 righe scritte, zero errori di
compilazione, commit bloccati dal sandbox (§3.17). **In corso al momento di questa rilettura.**

---

### Il conto

Le categorie si sovrappongono — una direttiva eseguita può anche essere stata verificata — quindi
i numeri non sommano a 37.

| esito della correzione | quante |
|---|---|
| L'assistente ha **verificato** con un dato o col codice | 24 |
| Si è limitato a **concordare**, senza misurare | 2 — i 38 GB di WSL (L1765) e il vocabolario fork/tronco (L2121), che infatti è tornato quattro ore dopo |
| Ha **ammesso** senza una verifica nuova | 2 — «cosa diavolo stiamo facendo» (L1948), «cosa hai lanciato ora» (L3261, il dato c'era già ma non era stato mostrato) |
| Direttive operative **eseguite** (non correzioni fattuali) | 7 — delegare a Codex, catalogare, accantonare il fork, non buttare gli output, il disegno a tre celle, la rilettura, i quattro Codex |
| L'utente aveva torto e l'assistente lo ha **mostrato con un dato** | 3 — la macchina degradata (L1565), la macchina sporca (L2225), i cancelli di promozione (L2623); più in parte la premessa sul «motore 0731» (L3193) |
| Correzioni diventate **strutturali** nel repo | 6 — preflight, default `C:`, preset versionato, prompt con hash SHA256, catalogo + `LEDGER_RUN.tsv`, streaming dell'output su disco |

**Il pattern che si ripete.** La maggior parte delle correzioni riguarda la stessa classe di
errore: *un numero letto per quello che sembrava dire invece che per quello che misurava*, e
una tesi costruita sopra prima di verificarla. Il conto dei contatori sbagliati in una sola
giornata è quattro — `Get-Counter` a campione singolo, `evict_backbone` di fase sbagliata,
`WorkingSet` contro `Commit`, `SystemCacheResidentBytes` che non conta le pagine mappate — più
un quinto caso che non è un contatore ma la stessa forma di errore: `file_qd_observed=1` letto
come prova che il percorso a file fosse attivo.

**E il pattern nelle risposte.** Le conclusioni che sopravvivono in §3 vengono quasi tutte dal
**leggere il codice**, non dal misurare. Le sei ore di misure hanno prodotto un risultato utile
— il confronto sui pesi, e anche quello con tre buchi aperti — e un mucchio di numeri su un
motore che nel frattempo abbiamo deciso di abbandonare.

---

## POSTILLA — cosa la notte cambia alle sezioni 1 e 2

Le sezioni 1 e 2 sono state scritte prima che il tronco venisse misurato. Tre precisazioni,
per non lasciare il documento incoerente con sé stesso.

**§2.12 (il +17% dei pesi nuovi) ha un buco in più di quelli che elencava.** Oltre alla
finestra contaminata di `A_221606` e alla verifica mai fatta su `A_212319`, i due run avevano
frazioni di ragionamento diverse — il modello esce dal pensiero a gen 200 sul primo e a gen 550
sul secondo (§3.5). Non è lo stesso carico. Il numero resta il migliore che abbiamo, e i pesi
0731 sono comunque quelli che useremo, ma non è il confronto pulito che è stato raccontato.

**§2.4 esce rafforzata.** Dicevo che `C_191603` non aveva «la nostra politica accesa» perché nel
log mancavano tutte le righe di politica. La notte ha aggiunto la ragione precisa: su 0731 la
cache esperti si attiva solo con il gate `DS4_CUDA_VRAM_EXPERT_CACHE=1`, che il braccio C
spegneva di proposito per un'inferenza sbagliata (§3.13). Quindi anche il run notturno
`C_234337` misura un'arena orfana, non la nostra politica.

**§2.5 resta valida come critica al metodo, ma il fenomeno esiste sul tronco.** La regola
generale «su 64 GB un'arena da 30 GiB peggiora la residenza» era ingiustificata a quel punto,
da un run solo, e l'utente l'ha smontata citando settimane di run del fork. Sul **tronco**
però la misura notturna la conferma in quel contesto specifico: 2,71 nudo contro 1,70 con
l'arena, con 91.870 hard fault/s. La differenza è che ora c'è un meccanismo misurato — la doppia
residenza strutturale di §3.4 — invece di una generalizzazione.

## IL QUADRO IN UNA PAGINA

```
COSA E' STATO MISURATO             fork ds4-p4a, ramo codex/prep4-mtp-secondary-map
                                   staccato il 12/05/2026, 314 commit di upstream indietro
                                   13 run, tutti i numeri della serata

COSA DOVEVA ESSERE MISURATO        tronco ds4-port, ramo port/upstream-substrate
                                   upstream 54b36ed (28/07, la punta) + i 14 blocchi
                                   4 run da 64-200 token la sera, 3 run veri la notte

IL NUMERO CHE NE ESCE              fork + pesi 0731            REGIME 4,49
(stessi pesi, ctx, prompt)         tronco nudo                 REGIME 2,71   -39%
                                   tronco + la nostra arena    REGIME 1,70   -62%
                                   tronco senza streaming      non parte

PERCHE' NON E' MOTORE vs MOTORE    delle 33 variabili del preset del fork, sul tronco
                                   ne esistono 10 e ne mancano 23, reap-loop compreso

IL MURO                            --ssd-streaming e' obbligatorio: senza, upstream vuole
                                   80,76 GiB in host e muore a 48,43. Da qui discendono
                                   la doppia residenza E il blocco di DSpark

COSA VALE LA PENA RIFARE PRIMA     braccio C con VRAM_EXPERT_CACHE=1 e think=false,
                                   perche' nessun confronto fatto finora ha avuto
                                   ne' la cache accesa ne' lo stesso carico
```
