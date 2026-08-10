# 34 — IL COSTO FISSO DELLA CONFIDENZA: non esiste. Esistono cicli da 191 ms

Data: 10 agosto 2026. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `0adb16c`.
**Niente compilato, niente eseguito**: codice letto riga per riga e i log della
campagna 4 già su disco (`D:\ds4_work\llama_run\c4_*.server.log`, corse delle
01:14–01:53 di stanotte). Marcatura: [MISURATO] = log o codice; [DEDOTTO] =
aritmetica su misure; [IPOTESI] = da falsificare, misura indicata. Sono l'ottavo
agente: qui non serve il fattore α — il bersaglio era già in ms sul cammino
critico e l'attribuzione è algebra diretta sui contatori dei log. L'unico punto
dove NON so ripartire (la struttura interna del sovrapprezzo, §5) lo dichiaro
non risolto invece di stimarlo.

## L'esito in cinque righe

1. **I 14,3 ms/ciclo fissi non esistono.** Sono l'artefatto di una metrica
   composita: `ms/ciclo = 1000·mean_len/t_s` usa il `mean_len` CONDIZIONATO ai
   soli cicli speculativi, e spalma su tutti i cicli il costo dei cicli in cui
   la soglia **azzera la bozza alla posizione 0**. Quei cicli sono il 12,1% a
   soglia 0,3 e il 14,8% a 0,5 — la premessa "a 0,3 la leva quasi non scatta"
   è falsificata dai log ([MISURATO] §2): `mean_len` 1,85 ingannava perché è
   una media sui sopravvissuti.
2. Il sistema 3×3 sui contatori dei log si risolve esatto: **ciclo di verifica
   136,1 ms, ciclo di replay 137,4, ciclo senza bozza 191,1**. Il libro mastro
   chiude al 99,9% su entrambi i bracci ([DEDOTTO su MISURATO] §3): spiego
   14,3 ms su 14,3, con la struttura, non con un costo nascosto.
3. Le piste 1 e 2 del mandato (`embeddings_nextn`, `output_reorder`/sync) sono
   **assolte dal timer già nei log**: `gen` avvolge l'intera `draft()`
   *compresa* la chiamata `llama_get_embeddings_nextn` (`speculative.cpp:
   2663-2668`) e si muove di +0,13 ms (8,36→8,49). Tutto ciò che la leva fa
   in più dentro il ciclo costa ≤0,13 ms ([MISURATO] §4).
4. Il ciclo da 191 ms si scompone: 8,4 di bozza eseguita e buttata + ~137 di
   forward a 1 riga (un forward costa quasi uguale a 2 — orchestration-bound)
   + **~46-55 di sovrapprezzo del passaggio 2→1→2 righe**: riuso del grafo
   ggml rotto (2 rebuild per sequenza di episodi, contati: `graphs reused`
   659→592/561) e slot CUDA-graph condiviso fra le due taglie (chiave =
   `nodes[0]`) che resetta il warmup e ricattura ([MISURATO codice+contatori],
   riparto interno NON risolto dai log — lo separa `DSPARK_PROF=1`, §7).
5. **Si possono togliere? Non c'è niente da prendere.** Anche a sovrapprezzo
   ZERO (ciclo senza bozza = 136,1) il braccio conf 0,5 farebbe 12,88 t/s
   contro 12,91 della base: il +3,8% sognato non esiste, perché i "1,94 token
   a ciclo" sono una media condizionata — i cicli sacrificati rendono 1 token
   allo stesso prezzo base. **A n-max 1 la leva conf-min è chiusa per
   aritmetica, non per costo** (§6). Il suo valore vero resta a n-max ≥ 2 con
   `LLAMA_SPEC_CONF_ESENTA_POS0=1`, già misurato stanotte (10,71 contro 9,43).

---

## 1. Le tre corse, e cosa dicono i contatori [MISURATO]

Log: `c4_base` / `c4_n1c03` / `c4_n1c05` (01:43-01:53), stessa base, solo
`--spec-draft-conf-min` diverso. Dalla riga `statistics draft-dspark` e da
`print_timing`:

| | conf 0 | conf 0,3 | conf 0,5 |
|---|---:|---:|---:|
| t/s | 12,91 | 11,63 | 12,19 |
| chiamate `draft()` (g) | 599 | 638 | 647 |
| bozze prodotte (#gen drafts) | 599 | 561 | 551 |
| **bozze AZZERATE dalla soglia** | **0** | **77 (12,1%)** | **96 (14,8%)** |
| verifiche (#calls a) | 599 | 561 | 551 |
| decodi totali (chiamate PROC) | 682 | 726 | 684 |
| replay (decodi − chiamate g) | 83 | 88 | 37 |
| p1 pulito (`acc per pos`) | 0,868 | 0,849 | 0,940 |
| `gen` ms/chiamata | 8,36 | 8,49 | 8,40 |
| PROC ms/chiamata | 0,54 | 0,59 | 0,58 |
| **graphs reused** | **659** | **592** | **561** |
| buchi | 67.630 | 104.441 | 61.222 |

Tre identità che inchiodano la struttura (tutte verificate):

- `chiamate g = verifiche + bozze azzerate` (599=599+0; 638=561+77; 647=551+96):
  ogni bozza azzerata È un ciclo che poi decodifica **1 sola riga**.
- `decodi = verifiche + azzerate + replay` (682; 726; 684): il replay non
  richiama la bozza (riusa `spec_draft` residuo, `server-context.cpp:2950`).
- replay ≈ verifiche×(1−p1): 79/85/33 attesi contro 83/88/37 — il bordo dei
  primi token spiega lo scarto.
- Libro mastro dei token: `(verifiche−replay)·2 + replay·2 + azzerate·1` =
  1198/1199/1198 ≈ 1200 in tutti e tre.

**La falsificazione della premessa del mandato sta nella terza riga**: a
soglia 0,3 la leva scatta nel 12,1% dei cicli — quasi quanto a 0,5. Il
`mean_len` 1,85 "come il controllo" è `1+p1` calcolato **sui soli cicli con
bozza** (`update_spec_stats` gira solo sulle verifiche): i 77 cicli senza
speculazione non lo toccano. È lo stesso salto d'asse contro cui mette in
guardia il registro (media condizionata letta come incondizionata).

## 2. Perché "159,1 in entrambi" sembrava un costo fisso [DEDOTTO]

`ms/ciclo` stampato = `1000·mean_len/t_s` con `mean_len` condizionato. Quindi
non è il tempo di un ciclo: è "tempo totale × mean_len / token". Due bracci con
miscele MOLTO diverse (77 azzerate+88 replay contro 96 azzerate+37 replay)
possono atterrare sullo stesso numero composito — ed è successo: 159,07 e
159,15. **Coincidenza aritmetica, non meccanismo.** Predizione falsificabile:
a soglia 0,4 il composito NON resterà 159,1; il §3 dà la formula che lo
predice dai contatori.

## 3. L'attribuzione: tre tipi di ciclo, sistema esatto [DEDOTTO su MISURATO]

Definizione pulita (una "iterazione" = un decode del bersaglio con la sua coda):

- **V** = verifica: bozza + decode a 2 righe `[campionato, bozza]` + sample/accept + checkpoint;
- **R** = replay post-rigetto: decode a 2 righe `[campionato prec., corretto]`, senza bozza (`server-context.cpp:3904-3929` + `handle_last_sampled_token:496-512`);
- **E** = episodio senza bozza: bozza eseguita e AZZERATA dalla soglia + decode a **1 riga** `[campionato]` (`server-context.cpp:488-493`) — l'**unico decode a 1 riga dell'intera corsa**, ed esiste solo nei bracci conf.

Tempo totale (1200/t_s): 92.951 / 103.181 / 98.441 ms. Sistema:

```
599·C_V +  83·C_R           =  92.951
561·C_V +  88·C_R + 77·C_E  = 103.181
551·C_V +  37·C_R + 96·C_E  =  98.441

→  C_V = 136,1    C_R = 137,4    C_E = 191,1   (ms)
```

Convalide (il sistema è determinato, quindi la prova non è il residuo ma la
coerenza esterna):

- stimando C_E per-braccio con l'ipotesi indipendente C_R = C_V + ripristino:
  187,7 (c05) e 192,4 (c03) — **costante attraverso bracci con miscele opposte**;
- C_V = 136 è il ciclo di verifica noto della base (92.951/682 = 136,3);
- C_R − C_V = +1,3 con la bozza risparmiata (−8,4) dentro: il ripristino puro
  vale ~+9,7 ms — coerente con gli ~11,7 MiB del checkpoint verso l'host
  (commento misurato in `server-context.cpp:3016-3021`);
- il libro mastro in forma Δ: **c03: 77·191,1 − 38·136,1 + 5·137,4 = +10.229
  contro +10.230 misurati (100,0%). c05: 96·191,1 − 48·136,1 − 46·137,4 =
  +5.490 contro +5.490 (100,0%).**

Questa è la risposta alla domanda del mandato: *dove vanno i 14,3 ms* — vanno
in 77/96 episodi da 191,1 ms l'uno, al netto delle verifiche e dei replay che
quegli episodi sostituiscono. Attribuiti tutti, residuo ≤ 0,1%.

Nota a margine che vale da sola: i buchi oscillano di ±37k fra i bracci
(104k a c03, 61k a c05) e il fit chiude comunque a tariffa **zero** — a
n-max 1 i buchi restano coperti (α≈0), quinta conferma della fisica di casa.
L'anomalia c03 (+54% buchi) viaggia col testo divergente (SHA diversi per
braccio, legittimo con la soglia accesa), non col tempo.

## 4. Le piste del mandato, giudicate

**Pista 1 — `cparams.embeddings_nextn` aggiunge nodi al grafo: ASSOLTA.**
Nessuno la accende "quando conf_min > 0": è accesa **incondizionatamente** nel
costruttore dell'impl DSpark (`common/speculative.cpp:1016`,
`llama_set_embeddings_nextn(ctx_dft, true, true)`), identica nei tre bracci; su
`ctx_tgt` resta spenta (la accende solo l'impl MTP, riga 1373, non nostra). E
il tensore confidenza sta nel grafo della bozza **sempre**: `dflash.cpp:
335-339` costruisce `conf → repeat → res->t_h_nextn` senza guardare cparams.
Il conteggio nodi fra conf 0 e conf 0,5 è identico per costruzione — il
cancello `-lv 4` non serve. `embeddings_nextn` governa solo l'ESTRAZIONE
(`llama-context.cpp:2135, 2178-2193`, `ggml_backend_tensor_get_async` del
tensore già nel grafo), attiva in tutti e tre i bracci.

**Pista 2 — `output_reorder()` come sincronizzazione D2H: ASSOLTA.**
`get_embeddings_nextn()` (`llama-context.cpp:1013-1017`) chiama
`output_reorder()`: solo scambi host-side di righe già estratte, svuota
`output_swaps` (riga 2528, idempotente), zero accessi device. La `synchronize()`
del wrapper (`llama-context.cpp:3935-3939`) è la stessa che il campionatore
esegue comunque un microsecondo dopo (`common/sampling.cpp:541`,
`llama_synchronize(ctx)` incondizionata): il costo netto della chiamata in più
è ~0. **Prova nei numeri, non per plausibilità**: il timer di `gen` avvolge
l'intera `impl->draft()` — riga 1211 inclusa — (`speculative.cpp:2663-2668`,
stampa a 2799) e si muove di +0,04/+0,13 ms. Qualunque cosa costasse quella
chiamata, sarebbe finita lì. Non c'è.

**Pista 3 — la taglia del batch che varia: FAMIGLIA GIUSTA, canale e
frequenza sbagliati.** La tensione segnalata dal mandato ("a 0,3 la taglia
cambia di rado") si scioglie: cambia nel 12,1% dei cicli (§1) — `mean_len`
nascondeva gli episodi. E il canale non è la corruzione del replay CUDA: è il
**ciclo di vita** dei grafi al cambio di taglia (§5), più il fatto bruto che
l'episodio rende 1 token al prezzo di ~1,4 cicli.

**Pista 4 — "una volta per ciclo quando conf_min > 0"**: esiste
(`speculative.cpp:1211`) e costa 0,13 ms. La voce da 14 ms non è per-ciclo:
è per-episodio, 191 ms, 12-15% dei cicli.

## 5. L'anatomia del ciclo da 191 ms

```
C_E = 191,1 =   8,4   bozza eseguita e scartata (gen invariato: la soglia
                      tronca DOPO il decode della bozza, righe 1211-1229)
             + ~137   forward a 1 riga (≈ C_R: un decode costa quasi uguale
                      a 1 o 2 righe — orchestration-bound, fisica di casa)
             + ~46-55 SOVRAPPREZZO della taglia che cambia   ← il pezzo nuovo
             − ~0-8   checkpoint bersaglio saltato (si salva solo con bozza,
                      server-context.cpp:3007 → il sovrapprezzo lordo è più alto)
```

I meccanismi del sovrapprezzo, nel codice:

1. **Riuso del grafo ggml rotto due volte per sequenza di episodi.**
   `allow_reuse` esige `ubatch.n_tokens` identico (`llama-graph.h:790`): il
   decode a 1 riga dopo una verifica a 2 ricostruisce tutto (`process_ubatch`,
   `llama-context.cpp:1432-1529`: `build_graph` + `sched_alloc_graph` del
   grafo bersaglio, decine di migliaia di nodi), e il ritorno a 2 righe
   ricostruisce di nuovo. **Contato nei log**: `graphs reused` 659→592 (c03,
   −67 su +44 decodi = +111 rebuild) e →561 (c05, +100 rebuild). I rebuild
   sono ~2× le SEQUENZE di episodi consecutivi (c03: 111 ≈ 2×55,5; c05:
   100 = 2×50 → gli episodi si aggregano, run medio 1,4-1,9 — la confidenza
   è autocorrelata sul testo). [MISURATO]
2. **Slot CUDA-graph condiviso fra le due taglie.** La chiave è il puntatore
   del primo nodo (`ggml-cuda.cu:3135-3137`) e il buffer meta viene riusato:
   grafo a 1 e a 2 righe cadono sullo **stesso** slot. Il cambio di proprietà
   (dimensioni ne[]) resetta il warmup (`ggml-cuda.cu:4854-4875`): l'episodio
   gira DIRETTO (niente replay dei lanci), la prima verifica dopo pure, la
   seconda paga la RICATTURA. [MISURATO codice]
3. **Il decode a 1 riga attraversa percorsi propri** (bucket `tok1` del
   profiler; prenota/prefetch e lane con metà id; MMVQ a 1 colonna). Quota
   ignota. [IPOTESI]

**Il riparto interno fra 1/2/3 e il forward non è risolvibile dai log
attuali**: il sistema che separerebbe "per-episodio" da "per-sequenza" è mal
condizionato (determinante ~1.500 su coefficienti ~10⁵: la stima del termine
per-sequenza porta ±23 ms di banda). Lo dichiaro non spiegato nel dettaglio —
lo risolve una corsa con `DSPARK_PROF=1` (§7.2), che separa build/alloc/
compute proprio fra `tok1` e `block` (`llama-context.cpp:1418-1428`).

## 6. Si possono togliere? Il conto che chiude il fronte

Il sogno del mandato — "1,94 token al ciclo di 144,8 = 13,40 t/s" — mescola
una media condizionata (1,94 = `1+p1` dei soli cicli sopravvissuti) con un
ciclo incondizionato. Il p1 0,940 è **selezione**, non miglioramento: si
ottiene BUTTANDO il 14,8% dei cicli speculativi, e ogni ciclo buttato rende
1 token invece di 1,87 allo stesso prezzo di base.

Il tetto esatto, coi numeri del §3: se il sovrapprezzo sparisse del tutto
(C_E = C_V = 136,1):

```
T(c05, sovrapprezzo zero) = 551·136,1 + 37·137,4 + 96·136,1 = 93.161 ms
→ 12,88 t/s  contro  12,91 della base.  Guadagno: −0,2%.
```

E con C_E reale: 12,19. **La leva a n-max 1 è strettamente non-positiva: nel
migliore dei mondi PERDE ancora due decimi.** Perché paghi servirebbe che i cicli scartati
avessero p1 atteso ≈ 0 — e il braccio 0,3 mostra il contrario (rimosso il 12%
dei cicli, il p1 dei sopravvissuti non sale nemmeno: 0,849). Coerente con
audit 32 §4: "anche a p1 0,68 la speculazione a 1 vince".

Quindi:

- **La "patch minima che li toglie" esiste già ed è l'esenzione della
  posizione 0**: `LLAMA_SPEC_CONF_ESENTA_POS0=1` (`speculative.cpp:1219-1227`).
  A n-max 1 rende la soglia un **no-op esatto** (esiste solo la posizione 0)
  → si torna alla base per costruzione. Detto senza giri: a n-max 1 conf-min
  va tenuta SPENTA, e il +3,8% va depennato dal registro delle attese.
- **La patch vera del sovrapprezzo** (un `gf_res` per taglia in
  `llama_context` — mappa `n_tokens → llm_graph_result`; con buffer meta
  separati anche le chiavi CUDA si separano da sole e ogni taglia resta calda
  e catturata) è scrivibile e piccola, ma **qui non comprerebbe niente**
  (12,90 contro 12,91). Va tenuta nel cassetto per i regimi ad alternanza
  strutturale — e i contatori di stanotte ridimensionano anche quello: a
  n-max 2 con esenzione l'alternanza 3↔2 tocca il 33% dei cicli ma i rebuild
  quasi non crescono (`graphs reused` 399 contro 423 della base n-max 2: le
  taglie si aggregano in sequenze lunghe), e senza il decode a 1 riga manca
  il pezzo grosso dell'episodio. Proporla solo se DSPROF la prezza. [MISURATO]
- **Dove il meccanismo confidenza PAGA davvero** (fuori mandato ma nel
  registro): n-max 2 + esenzione, stanotte 10,71 contro 9,43 (c4_n2bm3c08e) —
  lì la soglia gata la posizione ≥ 1, cioè quella da 116 ms, senza mai
  produrre cicli senza bozza (bozze azzerate: 0 su 458/468 chiamate nei log
  `e`; senza esenzione erano 178 su 556, il 32%).

## 7. Cancelli di falsificazione (quale numero mi smentisce)

1. **Già passato, gratis**: il libro mastro Δ del §3 chiude al 99,9% su due
   bracci con miscele opposte. Se qualcuno rifà i conti e non chiude, C_E
   costante è falso e l'attribuzione cade.
2. **`DSPARK_PROF=1` sul braccio conf 0,5** (una corsa): il dump per-fase
   (`llama-context.cpp:52-64`) deve mostrare per il bersaglio `tok1.n ≈ 96`
   (base: `tok1.n = 0`) e `tok1` per-chiamata ≈ `block` per-chiamata
   **+46-55 ms** somma di build+alloc+compute. Il riparto build/alloc contro
   compute decide fra rebuild ggml (meccanismo 1) e CUDA/percorsi-a-1-riga
   (2/3). Se `tok1` esce ≈ `block`, il sovrapprezzo non è nell'episodio e ho
   sbagliato pista.
3. **Braccio `conf 0,5 + LLAMA_SPEC_CONF_ESENTA_POS0=1` a n-max 1**: atteso
   il ritorno ESATTO alla base — t/s 12,83-12,95, bozze azzerate = 0
   (`#calls g == #gen drafts` nel log), `graphs reused` ≈ 659, p1 ≈ 0,868.
   **Se resta sotto 12,6 o le bozze azzerate non vanno a zero, esiste un vero
   costo d'accensione che questo rapporto ha mancato** — è il cancello che
   falsifica l'intera tesi.
4. **Braccio a soglia 0,4**: il composito stampato NON deve restare 159,1;
   deve valere `T = 136,1·V + 137,4·R + 191,1·E ± 1,5%` coi contatori del suo
   log. Se atterra di nuovo a 159,1 con contatori diversi dai predetti, la
   "coincidenza" del §2 è un meccanismo che non ho visto.

## 8. Dati che si ottengono solo eseguendo (in ordine di valore)

1. **Cancello 3** (esenzione a n-max 1): chiude il fronte in 4 minuti e
   decide se il rapporto è giusto. Costo: una corsa.
2. **Cancello 2** (`DSPARK_PROF=1` su c05): attribuisce i ~50 ms interni
   dell'episodio (rebuild contro CUDA contro percorso-1-riga). Decide se la
   patch per-taglia dei `gf_res` ha un bersaglio da ≥20 ms o da briciole —
   e quindi se vale per i bracci n-max 2 a alternanza alta (c09e: 62% di
   bozze corte).
3. **Cancello 4** (soglia 0,4): conferma la predittività del modello a tre
   cicli fuori dai punti usati per stimarlo. Insieme al 2 fissa anche il
   prezzo del checkpoint dentro C_V (`LLAMA_CKPT_CRONO=1`, già in albero,
   `server-context.cpp:3022`).
4. (Igiene, non urgente) una corsa c03 con SHA agganciato per separare
   l'anomalia buchi (+54%) fra divergenza di testo e contatori — non porta
   tempo (§3), ma il registro dei buchi resta sporco finché non è etichettata.
