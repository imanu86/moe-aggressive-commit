# Recupero della sessione lunga

Fonte primaria: `1c34df6e-b359-4454-9f30-2ea9f48b0bb4.jsonl`, letto fino
alla riga 24.786. Il file era ancora in crescita durante il recupero; i numeri
di riga qui sotto sono stabili perché le nuove righe vengono aggiunte in coda.

Questo documento contiene **solo** ciò che manca da
`LEDGER_10_AGOSTO.md` e `ATLANTE_LEVE.md`, oppure ciò che li contraddice.
Non ripete i risultati già registrati correttamente nei due documenti.

## Regola di lettura

- **[MISURATO]**: valore presente nel contenuto di un `tool_result`.
- **[CONTAMINATO]**: il braccio ha prodotto numeri, ma una leva, un parser, un
  contatore o il testo in ingresso non era quello dichiarato.
- **[INVALIDO]**: la velocità esiste, ma l'output o il cancello non consentono
  di usarla come confronto.
- **[DEDOTTO]**: calcolo fatto qui a partire da misure, non osservazione diretta.
- **[IPOTESI]**: spiegazione non verificata.
- **[CORREZIONE UTENTE]**: premessa corretta dall'utente; non viene trasformata
  in misura se non è sostenuta anche da un `tool_result`.

La prosa dell'assistente è usata solo per trovare aspettative, bias e
contraddizioni. In caso di conflitto vince il `tool_result`.

## 1. Errori e affermazioni da correggere nei due documenti

### 1.1 `K` frazionario non è «mai misurato»

`ATLANTE_LEVE.md`, §4, dice: «K frazionario [...] mai misurato». È falso come
inventario delle corse.

| braccio | K nominale | t/s | ms/ciclo | p1 | colpi |
|---|---:|---:|---:|---:|---:|
| `kf_A_233` | 2,33 | 10,14 | n.d. | 0,85977 | 42,6% |
| `kf_B_250` | 2,50 | 10,41 | n.d. | 0,88815 | 42,4% |
| `kf_C_200` | 2,00 | 10,16 | n.d. | 0,86477 | 38,7% |

Fonte: **[MISURATO]** JSONL L15410.

Esiste poi la spazzata sulla base FUSO5:

| braccio | K nominale | t/s | ms/ciclo | p1 |
|---|---:|---:|---:|---:|
| `c6_k15` | 1,5 | 11,53 | 156,1 | 0,80801 |
| `c6_k2` | 2,0 | 12,92 | 144,7 | 0,86811 |
| `c6_k25` | 2,5 | 12,80 | 147,7 | 0,89649 |

Fonte: **[MISURATO]** JSONL L22021.

Il verdetto corretto non è però «K frazionario verificato»: queste corse sono
anteriori alla scoperta che una parte del codice leggeva K con `atoi` e una
parte con `atof`, corretta solo in `979efd899`. Quindi i bracci esistono ma
sono **[CONTAMINATI]**. La riga dell'Atlante deve diventare: «misurato prima
della correzione del parser; mai rimisurato validamente dopo la correzione».

### 1.2 A 104k il modello carica: manca la curva, non la prova di caricamento

`LEDGER_10_AGOSTO.md`, §8.4, dice che per la banda 102k–110k «non sappiamo se
carica». Due `tool_result` dicono il contrario:

- **[MISURATO]** `ctx=104000`, `ub=64`, `--no-host True`: caricamento riuscito,
  VRAM libera 419 MiB, prefill 22,61 t/s, decode 9,71 t/s, p1 0,58333
  (JSONL L23092).
- **[MISURATO]** `ctx=104000`, `ub=512`, indexer fuso: caricamento riuscito,
  VRAM libera 965 MiB, prefill 75,62 t/s, decode 9,81 t/s, p1 0,59459
  (JSONL L23264).

I prompt/output erano troppo corti per misurare davvero la **profondità**
102k–110k. La formulazione corretta è: «il caricamento a `-c 104000` è
verificato; la velocità a coda 102k–110k non è misurata».

### 1.3 `prefetch: effetto ~0` cancella perdite grandi e ripetute

`ATLANTE_LEVE.md`, §4, riassume il prefetch come «effetto sul ciclo ~0». Questo
non rappresenta i risultati grezzi, nei quali diverse varianti sono fortemente
negative:

| configurazione | controllo | prefetch | effetto osservato |
|---|---:|---:|---:|
| multi-blocco corretto, W0→W1 | 9,26 t/s, hit 44,0% | 7,90, hit 75,1% | −14,7% |
| multi-blocco corretto, W0→W2 | 9,26 | 6,89, hit 77,9% | −25,6% |
| `pf_w1_tutti` | riferimento 10,40 | 5,84, hit 39%, p1 0,89482 | −43,8% |
| `_CURA=2` / `_CURA=1` | riferimento 10,40 | 6,11 / 6,09 | circa −41% |
| `_PREFETCH_FILTRO` | riferimento 10,40 | 6,01 | −42,2% |
| overlap 0, W0→W1 | 6,85 | 5,35 | −21,9% |

Fonti: **[MISURATO]** JSONL L8122/L20263, L19873, L19942, L19991,
L20100 e L20209.

La vecchia L7000 riporta W2 1,93, W1 3,10, W0 4,08 t/s, ma il 100% di hit è
**[CONTAMINATO]**: il contatore leggeva il punto sbagliato nel cammino
gate/up. Le velocità restano output di macchina; quel contatore no. Il
verdetto prudente è: «il prefetch non ha un effetto unico; in più setup è
molto negativo, e alcune campagne avevano telemetria guasta».

### 1.4 La banda PCIe ha due numeri incompatibili, non uno

`ATLANTE_LEVE.md`, §5, registra 18,4 GiB/s. Il microbenchmark grezzo riporta:

```text
400 × 6,75 MiB = 108,28 ms = 24,35 GiB/s = 0,271 ms/esperto
```

e una copia da 54 MiB dà 24,46 GiB/s. Fonti: **[MISURATO]** JSONL L6596 e
L8122. Il valore 18,4 compare nell'audit riprodotto a L24476, non nello stesso
microbenchmark.

Non si può scegliere un numero senza distinguere i cammini. **[IPOTESI]**:
24,35–24,46 è `cudaMemcpy` sintetico da RAM pinnata a VRAM; 18,4 è lettura
demand da memoria mappata. Finché non vengono etichettati, usare 18,4 come
costante fisica unica è scorretto.

### 1.5 La soglia di 400 MiB di VRAM è stata falsificata dalla zavorra

Il ginocchio ricavato dalla residenza degli strati era:

| braccio | VRAM libera | t/s |
|---|---:|---:|
| nessuno strato esperto in VRAM | 3.683 MiB | 7,94 |
| un blocco | 1.956 MiB | 8,06 |
| due blocchi | 305 MiB | 7,34 |

Fonti: **[MISURATO]** JSONL L6657/L6661. Da qui è nata l'idea che sotto circa
400 MiB il decode degradi.

La spazzata controllata con sola `LLAMA_VRAM_ZAVORRA`, stesso SHA
`33D76723EB8D` e stesso p1 0,86470, la smentisce:

| braccio | zavorra | VRAM libera | t/s | ms/ciclo |
|---|---:|---:|---:|---:|
| `z000` | 0 MiB | 1.247 MiB | 13,25 | 140,4 |
| `z320` | 320 | 927 | 13,24 | n.d. |
| `z620` | 620 | 627 | 13,25 | n.d. |
| `z770` | 770 | 477 | 13,20 | n.d. |
| `z870` | 870 | 377 | 13,17 | n.d. |

Fonte: **[MISURATO]** JSONL L23313. La perdita a due blocchi non era causata
dal solo margine VRAM; resta da isolare il costo specifico della loro
residenza/esecuzione.

### 1.6 I 24–28 ms dello sfratto a 339 slot non sono una misura diretta

Nel Ledger, §1, «a 339 slot quel termine vale 24–28 ms» è presentato dentro
«due cause sommate, entrambe misurate». Misurati sono i punti 339/448/480 e la
pendenza locale di circa 0,07–0,08 ms per slot/ciclo. Moltiplicare quella
pendenza per 339 produce 24–27 ms, ma è **[DEDOTTO]** e assume intercetta zero e
causalità interamente nello scan. Nessun braccio isola lo scan a 339 slot.
L'Atlante stesso, §6, ammette che costo di scansione, indirizzamento e contesa
non sono separati. Il Ledger deve abbassare la marcatura da misurato a dedotto.

### 1.7 «Più capienza = −8,3%» è specifico del binario/setup

Prima della campagna serale, sulla base FUSO5:

- `c6_k2`, 339 slot: 12,92 t/s, 144,7 ms/ciclo, p1 0,86811;
- `c6_k2s448`, 448 slot: 12,76 t/s, 146,6 ms/ciclo, p1 0,88481, hit 62,2%.

Fonte: **[MISURATO]** JSONL L22021. La perdita è circa 1,2%, dentro la deriva
serale, non 8,3%. Il braccio ha p1 e SHA dell'output differenti da quelli della
campagna del Ledger, quindi non è una replica appaiata. Non smentisce la misura
serale, ma smentisce la sua generalizzazione a legge: va riconciliato cosa è
cambiato tra i due setup.

## 2. Reperti misurati rimasti fuori dai documenti

### 2.1 Il muro di `ub=2048`: il dato più importante dimenticato

Prima spazzata, prompt da 6.510 token:

| ub | prefill t/s | decode t/s | p1 | VRAM libera |
|---:|---:|---:|---:|---:|
| 64 | 22,58 | 10,54 | 0,63889 | 1.256 MiB |
| 128 | 29,84 | 11,41 | 0,73529 | 1.152 |
| 256 | 46,27 | 10,56 | 0,70000 | 934 |
| 512 | 72,92 | 10,48 | 0,63889 | 506 |

Fonte: **[MISURATO]** JSONL L22552.

Spazzata estesa:

| braccio | ub | prefill t/s | CUDA compute buffer |
|---|---:|---:|---:|
| `u512` | 512 | 75,53 | 269,84 MiB |
| `u1024` | 1.024 | **113,47** | 540,62 MiB |
| `u2048` | 2.048 | **59,63** | 1.085,18 MiB |
| `u4096` | 4.096 nominale | 59,94 | 1.085,18 MiB |

Fonte: **[MISURATO]** JSONL L23652. `u4096` è uguale a 2048 perché
`n_batch=2048` lo limita. Il braccio `u1024 FUSO=0` muore ed è invalido, non un
numero da confrontare.

Aspettative registrate prima: `ub1024` 97–102 t/s, cancello sotto 85;
`ub2048` 117–125, cancello sotto 108 (JSONL L23554/L24418/L24648).
`ub1024` supera il cancello; `ub2048` lo falsifica di quasi metà. Dopo il
carico restavano 3.237 MiB a ub1024 e 2.645 MiB a ub2048 (L24655), quindi non
è fame di VRAM. **[IPOTESI]** non verificata: cambio di kernel/occupancy o
tiling oltre 1024.

Questo non contraddice la misura più recente `ub1024=101,00` del Ledger, fatta
su prompt e stato macchina diversi. Dimostra però che «ub più grande non è un
problema» vale fino a 1024, non fino a 2048.

### 2.2 Lo slot si ripristina in 0,78 s, ma la richiesta rifà tutto il prefill

Il test arrivato mentre questo recupero era in corso separa finalmente due
cose che la prosa mescolava:

- **[MISURATO]** `/slots/0?action=restore` ripristina 23.693 token e legge
  244.860.876 byte: 0,78 s visti dallo script, `restore_ms=603,536` restituito
  dal server;
- **[MISURATO]** la richiesta immediatamente successiva seleziona lo slot con
  similarità LCP 1,000, ma ri-prefilla comunque tutti i 23.693 token in 6,19
  minuti;
- decode finale 10,52 t/s e p1 0,89557, non confrontabili direttamente con la
  madre lunga 9,33/p1 0,78323 perché l'intervallo generato è diverso.

Fonti: JSONL L24752 e L24778. Verdetto: il restore **meccanico** funziona; il
riuso del prefisso restaurato **non** funziona nel cammino della richiesta.

La spiegazione successiva — dopo `state_read`, `seq_pos_min` restituisce
`seq_pos_max` se `LLAMA_KV_POSMIN_VERO=0` — viene da lettura del codice e dalla
prosa dell'assistente: è **[IPOTESI]**, non misura. Al cutoff era partita una
seconda prova con `LLAMA_KV_POSMIN_VERO=1`, senza risultato disponibile.

### 2.3 L'«oracolo» non ha mai misurato il soffitto del prefetch

Il modello dichiara 43 blocchi (`deepseek4.block_count=43`); nello stesso
metadata compare 64 come `head_count` (JSONL L16320). Il registratore
dell'oracolo alloca invece `1189 token × 64 layer × 6` piste (L14784).

Risultati grezzi:

- primo replay «esatto»: 5,75 t/s, hit 1,3%, `in_late` 32%, domanda
  1.962 GiB e prefetch 1.771 GiB (L14841);
- controllo successivo: solo 33,5% delle richieste trovate, quando un oracolo
  utile ne richiedeva circa 90%; clock device/host non allineati (L15033);
- piste spostate di −1/+1/−2 restano circa 36,7%/31,3%/42,0%, nessuna vicino
  al soffitto (L15079);
- «oracle2»: 38,3% trovati, 6,08 t/s, hit 1,7%; variante no-demand 12,4%
  trovati e 9,82 t/s, ma SHA vuoto/diverso (L15174).

Verdetto: i numeri sono **[MISURATI]**, ma l'etichetta «oracolo» è
**[INVALIDA]**. Non è mai stato misurato il caso «staging perfetto»; pertanto
anche le conclusioni sul suo soffitto (circa 12,5/17/25 t/s nelle attese della
sessione) restano non verificate.

### 2.4 Il decode è fortemente sensibile al clock CPU nella base fusa

| K | CPU | t/s |
|---:|---:|---:|
| 4 | 4.764 MHz | 9,68 |
| 4 | 2.475 MHz | 6,88 |
| 2 | 4.798 MHz | 10,90 |
| 2 | 2.475 MHz | 9,38 |

SHA identici dentro ogni coppia. Fonte: **[MISURATO]** JSONL L21265. È un
risultato più forte del vecchio downclock, fatto su un'altra configurazione.
Il primissimo tentativo al 70% era anche strumentalmente falso: entrambi i
bracci restavano a 3.801 MHz e facevano 7,77 t/s (L6286). Il rifacimento vero
misurò 3.801 MHz/7,76 contro 2.660 MHz/5,67 (L6305).

### 2.5 KV ring: due campagne danno segni opposti

Prima campagna valida:

| contesto | ring | t/s | p1 | VRAM libera |
|---|---|---:|---:|---:|
| 10k | off | 10,31 | 0,87980 | 864 MiB |
| 10k | on | 10,23 | 0,86811 | 916 |
| 100k | off | 8,62 | 0,81803 | 390 |
| 100k | on | **9,29** | 0,82638 | 455 |

Fonte: **[MISURATO]** JSONL L15595.

Campagna successiva: a 10k 9,97 on contro 9,86 off, rumore; a 100k **8,05 on
contro 8,54 off**, segno opposto, con 236 contro 335 MiB liberi
(L15850/L15947). Il primo 100k-on a L15540 aveva contenuto utile 0 e 1.041
token di reasoning: **[INVALIDO]** per qualità. Non esiste ancora un verdetto
riconciliato sul ring a contesto lungo.

### 2.6 La cache senza prefetch migliorò sia la media sia, soprattutto, la coda

Nella campagna zero-copy W0/W1/W2:

| braccio | t/s finale | mediana istantanea | minimo | p10 | quota sotto 2 t/s |
|---|---:|---:|---:|---:|---:|
| W1, 17 mappati | 6,37 | 6,49 | 4,73 | 5,95 | 0% |
| W2, 8 mappati | 6,11 | 6,71 | 0,92 | 3,91 | 4,1% |
| W0, controllo | 5,68 | 7,01 | 0,18 | 1,53 | 16,6% |

Fonte: **[MISURATO]** JSONL L2223. Guardare solo la mediana avrebbe eletto il
controllo; il risultato utile è che W1 elimina la coda catastrofica. È una
metrica diversa dal solo t/s e non è entrata nei due documenti.

Un braccio con uno strato residente in VRAM scese invece da 6,35 a 5,59 t/s;
una variante con 22 mappati + strato fece 6,15 (L2372). Le lunghezze/output
non sono perfettamente appaiati: reperto da ripetere, non verdetto.

### 2.7 FUSO e `nmax=2`: numeri utili rimasti senza tabella finale

Campagna FUSO, **[MISURATO]** JSONL L21376:

- FUSO0, K2: 10,86 t/s, 170,3 ms/ciclo;
- FUSO7, K2: 12,63 e 12,69 t/s, circa 145 ms/ciclo;
- FUSO1: 12,27 t/s, 155,7 ms/ciclo;
- FUSO4: 11,25 t/s, 163,6 ms/ciclo;
- FUSO7, K3: 12,27 t/s;
- con `nmax=2`, FUSO7 10,01 contro FUSO0 7,63 t/s;
- nodi del grafo: 33.813 → 9.991.

Sulla campagna seguente FUSO5 risultò il riferimento migliore: 12,92 t/s,
144,7 ms/ciclo, contro FUSO7 12,71 (L21663/L21674). Nel lungo HTML: FUSO5
12,63 e 151,2 ms/ciclo contro FUSO0 11,06 e 173,6; gli output differiscono
anche per contenuto generato, quindi il delta non è puramente prestazionale
(L21869).

Per `nmax=2`, FUSO5:

| soglia | t/s | ms/ciclo | p1 |
|---:|---:|---:|---:|
| 0 | 8,69 | 295,7 | 0,7909 |
| 0,5 | 9,35 | 265,2 | 0,8722 |
| 0,8 | 9,99 | 261,3 | 0,9673 |
| 0,95 | 9,74 | 265,9 | 1,0000 |

Fonte: **[MISURATO]** L21663. Con batch max 3 ed esenzione posizione 0, i
bracci migliori arrivano a 10,71 t/s e 197,8–205,4 ms/ciclo, ancora sotto
`nmax=1` a 12,92 (L21771). L'aumento di p1 non ripaga il costo.

### 2.8 Q2_K GateUp: la quantizzazione più ricca perde nettamente

Il riferimento IQ2 a `ub=1024` ripete 113,59/113,55 t/s di prefill e
9,71/9,72 di decode (L23671). Il modello interamente Q2_K non entra: il mapping
di 76.608 MiB fallisce su `cudaHostAlloc` a 2.224 MiB. Il parziale `q_q2k7`,
72.576 MiB mappati e 15.122 MiB CPU, dà:

- `ub=1024`: 64,66 t/s prefill, 7,95 decode;
- `ub=512`: 48,24 t/s prefill, 8,51 decode.

Fonte: **[MISURATO]** JSONL L23686. È una doppia perdita, non una leva di
qualità gratuita.

### 2.9 Quattro richieste aumentano l'aggregato, non il servizio per chat

| richieste | t/s per richiesta | t/s aggregati |
|---:|---|---:|
| 1 | 6,47 finale; 5,56 aggregato | 5,56 |
| 2, stesso prompt | 4,51 / 4,47 | 7,73 |
| 2, prompt diversi | 4,41 / 4,38 | 7,51 |
| 4, diversi | 2,18…2,07 | 7,60 |

Fonte: **[MISURATO]** JSONL L8590. L'aggregato satura a circa 7,5–7,7; la
singola chat peggiora. Il filone multi-request non è stato ripreso.

### 2.10 Reap/gate: più veloce nonostante più hard fault

- `lock1200`: 6,32 contro controllo 5,80 t/s; mediane istantanee 6,98 contro
  6,52; minimi 2,87 contro 0,60. Ma hard fault mediani 4.386 contro 3.300
  (JSONL L1112).
- politica a massa 6,04, controllo 5,63, frequenza 5,11 sullo stesso output da
  5.822 token (L1271).
- niente decay 6,50, decay 0,9 = 5,42, decay 0,8 = 5,73: il churn cresce
  (L1355).
- Q1 tutto in RAM: gate off 6,36, gate on 6,20; hard fault mediani 0, contro
  Q2 massa 795 e controllo 1.124 (L1545).

Sono **[MISURATI]**. Il primo risultato spezza l'equivalenza «meno hard fault
= più veloce»: il contatore di paging non spiega da solo la coda.

Il successivo Q1 «30 mappati» a 7,63 contro CPU 6,24 è **[INVALIDO]**: l'output
mappato completa 0/6 sezioni e ha ripetizione 51, contro 6/6 e ripetizione 4
del controllo (L3278).

### 2.11 Leve minori con esito già misurato

- `GGML_CUDA_GRAPH_OPT`: K2, 10,35/10,77 on contro 10,84 off; K4, 9,54 on
  contro 9,58 off. Nessun guadagno risolto oltre il rumore
  (**[MISURATO]** L21198/L21215).
- Sinkhorn bersaglio: 20 iterazioni 10,21 e SHA base; 1 iterazione 10,76 ma
  SHA/output cambiato; 4 iterazioni 10,29. Non è una leva prestazionale
  bit-esatta (L20966/L20985).
- Sinkhorn bozza: 1/4/20 iterazioni = 10,24/10,52/10,47 t/s; nessun guadagno
  stabilito (L21079).
- fork/join: fork2 10,63 contro fork0 10,24, copia già conclusa nel 98,7% dei
  casi; gli SHA differiscono, quindi il confronto è **[CONTAMINATO]**
  (L20828).
- indexer fuso a 10k, ub512: 21,17 contro 21,03 t/s non fuso, buffer 269,84
  contro 832,34 MiB; decode 11,92/11,94 e stesso SHA. Libera circa 562 MiB ma
  non accelera quel prefill (L23264/L23280).

## 3. Attese registrate prima della misura

### Falsificate o verificate, ma poi dimenticate

| attesa/cancello | misura corrispondente | stato |
|---|---|---|
| `ub1024` 97–102 t/s; fallisce sotto 85 | 113,47 t/s | **verificata e superata** |
| `ub2048` 117–125; fallisce sotto 108 | 59,63 t/s | **falsificata duramente** |
| K frazionario negativo | K2 12,92; K1,5 11,53; K2,5 12,80 | segno coerente, ma **contaminato dal parser** |
| più VRAM libera evita il ginocchio sotto 400 MiB | zavorra stabile fino a 377 MiB | **falsificata come causa unica** |
| KV ring aiuta a 100k | +7,8% nella prima campagna, −5,7% nella seconda | **contraddittoria** |
| FUSO porta il grafo a circa 10k nodi e accelera | 33.813→9.991; 10,86→12,63/12,69 | **verificata** |
| restore evita il prefill dopo riavvio | restore 0,78 s, poi ri-prefill integrale da 6,19 min | **meccanica verificata, riuso falsificato** |

Fonti: le righe dei reperti §2.

### Dichiarate ma non verificate

1. **Oracolo/staging perfetto.** Le attese di hit intorno al 90% e i soffitti
   di velocità non hanno una misura valida: entrambi gli «oracoli» erano
   disallineati e usavano 64 piste di layer su un modello da 43 blocchi.
2. **Riuso dello slot dopo un riavvio, con `LLAMA_KV_POSMIN_VERO=1`.** Il primo
   test completo dimostra restore meccanico in 0,78 s ma riuso fallito; la
   seconda prova con la leva candidata era ancora in corso al cutoff. Quindi
   resta non verificata la cura, non il difetto.
3. **Reap senza decay con periodo 25.** Proposto dopo il risultato del decay
   (circa L1372); non è stato trovato un braccio corrispondente.
4. **Cache da 1.400 slot.** L20100 contiene soltanto contatori intermedi
   (colpi 99,5%, buchi 2.737, volume 18,05 GiB); manca un risultato finale di
   t/s e non è stato trovato un braccio prestazionale concluso. Non va contato
   come misura della capienza 1.400.
5. **K adattivo agganciato a un contatore.** L'utente ricorda un K variabile
   già testato (L18015/L20500), ma nella parte recuperata non c'è una nuova
   misura sulla base FUSO5 dopo il fix `atoi`/`atof`.

## 4. Fili lasciati cadere

1. **Costruire un vero oracolo di staging.** È il buco sperimentale più grave:
   l'intera domanda «quanto vale trasportare perfettamente in anticipo?» resta
   senza misura, mentre conclusioni successive la trattano come chiusa.
2. **Spiegare il collasso fra ub1024 e ub2048.** La VRAM non è il limite e il
   buffer raddoppia regolarmente. Mancano profilo per kernel, occupancy e
   tempo per strato sul prefill.
3. **Separare i due cammini PCIe.** 24,35–24,46 GiB/s sintetici e 18,4 GiB/s
   applicativi non possono condividere la stessa etichetta.
4. **Riconciliare cache/prefetch per SHA e patch.** Lo stesso nominale D2 passa
   da cache 6,49 contro off 7,96 (L8667) a cache 8,94 contro off 7,77 (L8953).
   Non sono repliche: lo stato del binario/patch è diverso e non è stato
   ricostruito.
5. **Riconciliare KV ring a 100k.** Una campagna dà +7,8%, la successiva −5,7%.
   Servono stessi prompt, SHA, margine VRAM e output appaiato.
6. **Capire perché il gate/Reap migliora la coda aumentando gli hard fault.**
   Il contatore usato come causalità va declassato a correlato.
7. **Misurare il servizio, non solo l'aggregato, in multi-request.** Quattro
   chat non superano l'aggregato di due e dimezzano ancora la velocità per
   utente. Nessun lavoro successivo tratta scheduling o fairness.
8. **Qualità prima della velocità.** I bracci Q1 mappato, KV100k iniziale,
   Sinkhorn a 1 iterazione e no-demand oracle producono output/SHA incompatibili
   col controllo. Sono stati talvolta discussi come prestazioni prima di
   guardare il contenuto.
9. **Riuso reale del prompt.** Il log del server dice esplicitamente «forcing
   full prompt re-processing due to lack cache data (likely
   SWA/hybrid/recurrent)» (L22395). Ora sappiamo che save e restore cross-process
   funzionano, che il server sceglie lo slot con LCP 1,000 e che, nonostante
   questo, la richiesta ri-prefilla tutto. Il filo caduto si è ristretto al
   riconoscimento del confine KV restaurato; `KV_POSMIN_VERO` è solo il primo
   candidato, non ancora verificato.

## 5. Correzioni dell'utente, testuali

Questa sezione conserva le correzioni di premessa. I refusi sono lasciati
quando fanno parte del testo; la codifica mojibake del JSONL è stata soltanto
normalizzata in Unicode leggibile. I lunghi rapporti dell'utente sono marcati
come tali, non promossi a `tool_result`.

### Banco, metri e stato della macchina

- L2748: «I 7-8 t/s non intendevo come media ma come punte toccate».
- L3827: «comunque non sono 20 secondi di caricamento! per quello dicevo che
  gli stratin che gli servono dovrebbero risiedere già di la...poi vedi tu la
  memoria gpu viene costantenente buttata fuori».
- L5717: «però non mi sembra l'ibrido che faceva 15 di prefill e quasi 8 di
  deode / vedo memoria gpu vuota..non hai pinnato».
- L6200: «hai sbagliato tutto! il gate deve essere tra ram e ram pinnata...è
  li che ci deve essere...l'ssd era già fuori dai giochi con 96 gb di ram!!
  magari quello che abbiamo recuperato in calcolo l'abbiamo perso nel portare
  da ram a ram pinnata».
- L21146: «Abbiamo già fatto un downclock e non cambiava troppo ma all’epoca
  non avevamo questa config».
- L22490: «Invece a ledger ci sono i doppi prompt! Assolutamente!».
- L22831: «Stai ancora ragionando per scarsità… togliamo anche il back bone e
  mettiamoli in ram se serve a velocizzare il prefill! Se chiedo una modifica a
  una pagina HTML appena creata, ho un profilo di 10.000 token!».
- L23744: «ma non andavamo a 13 t/s?».
- L24158: «74,3 GiB di esperti non stanno in VRAM: sono in RAM bloccata e
  mappata, letti sul PCIe. / bella scoperta, mi riferivo al fatto che c'è almeno
  1gb non sfruttato in vram».
- L24296: «C:\pagefile.sys: allocato 58997 MB, in uso 613 MB, picco 58879 MB».
  Questo smentisce l'attribuzione alla paginazione; l'assistente lo ammette a
  L24304. È un dato fornito dall'utente, non un `tool_result` autonomo.
- L24376: «ma non dire cazzate il desktop oscilla tra 0,6 e 0,7...ora carica /
  non toccare». Il conteggio processi grezzo a L24358 mostrava processi
  transitori; sommarli in «1.141 MiB di desktop» cambiava il perimetro.
- L24556: «ma non avevamo un modo per riusare il prompt? che cazzo ci serve
  fare dei test da 250 e 6000 con un turno da 20?».
- L24587: «ma non l'avevi misurata a 1200?». Correzione decisiva: `jprompt` è
  circa 60 token iniziali + 1.200 generati, quindi coda 60→1.260 e profondità
  media circa 660, non «250 token di coda».
- L24646: «ub 2048? avevamo detto che non era un problema». Il recupero del
  `tool_result` L23652 mostra invece il crollo 113,47→59,63 t/s.

### Trasporto, cache e politica di residenza

- L7028: «Si ma la maschera per dominio non aveva senso…serviva a togliere il
  trasporto!! Trasporto che se prediciamo possiamo eliminare…».
- L7034: «Mah…non sono d’accordo!! Usiamo o no 6+1 esperti per token? A 10
  token al secondo sono 60’esperti al secondo perché 1 sempre residente».
- L8051: «Il trasporto già ora non è un problema, l'abbiamo visto prima che
  anche tenessimo solo 258 expert in vram, non tutti cambiano da un token
  all'altro...molti sono condivisi. quindi il trasporto vero è poco!
  rimisuralo!».
- L15922: «te lho detto che la copia deve essere peoibita! o li spostiam in
  tempo o li calcoliamo con sovrapposizione ovunque siano gpu o cpu».
- L16455: «non fisicamente tutti in una volta! cazzo aabbiamo 320 slot che
  possono essere alzati anche oltre se liberiamo quello spazio che non sappiamo
  riottenere e che si prende cuda anche togliendo la kv / il 30% minimo è
  identico a ogni token! / se i caldi e /o quelli con massa alta restano in
  vram sono pochi quelli da portare per ogni token e con un buffer di 380 slot
  dovremmo avere margine quasi per due token consecutivi!! [...] la predizione
  serve per poortare quelli giusti, dove sbagliamo andiamo su cpu in overlap».
- L17103: «avresti già sbaglisto! il nuovo codice codex che libera vram diventa
  base, cache si alza al max che ci sta e diventa base più tutto quello che
  abbiamo girato prima come base».
- L17299: «quelle previsioni se prima non erank sbagliate allora c'è altro che
  va verificato non devono inquinare! e soprattutto non copiare roba gia
  residente in vram».
- L17736: «si ma questo test senza esperti invram non dice nhlla di
  informativo! non aveva senso!».
- L17851: «Ecco bravo! Ottimizzare sul contatore sbagliato non porta a nulla!».
- L17950: «Nella prima versione aveva vari gate. Quella che leggi qui è la
  versione edulcorata. Tuttavia, ragionare per massa potrebbe ottimizzare il
  prefetch ovvero se un esperto è già lì con una certa massa, non lo devi
  sloggiare».
- L17972: «Ora facciamolo così ma la politica di reap introduceva proprio
  quell’isteresi che ci servirebbe per fare meno Miss. Ovvero hai peso alto ma
  non ti porto dentro per stare la durata di un token!».
- L19683: «forse perchè gli esperti sono sparsi e portarli uno a uno è lento,
  in blocco invece? ci abbiamo mai pensato? un po' come faceva wrap da ssd?».
- L20433: «non dava benefici ma non eravamo in questo setup o sbaglio?».

### Configurazione, identità e validità dell'output

- L9: «ripeto non possiamo spostare dspark sul minipc? lavora su gpu
  integrata? sarà un po' lenta ma non togliamo nulla al backbone...».
- L1681: «su q1 avevamo fatto una prova con due strati i 3 (non ho fatto i
  calcoli) in vram?».
- L1691: «ma non avevamo anche un q1 piu quantizzato che avevo realizzato su
  pod?».
- L2099: «ma non dire cazzate che la gpu lavorava pochissimo anche prima!».
- L3602: «accendiamo e spegnamo server di continuo, non sono 3 min una tantum!
  documentati e guarda online».
- L5200: «non avevi detto che non si ragiona più a strati ma expert?».
- L5284: «guarda che questa roba qua su llama non la conosciamo, ma su
  dwarfstar l'abbiamo già fatta e pagava tanto il reap loop!».
- L5345: «ma questa roba dovrebbe essere documentata sul reap loop, il mio
  repo..penso...lavoro che abbiamo già fatto!».
- L5740: «mi riferivo alla memoria gpu condivisa che avevamo poertato oltre 70
  gb».
- L13820: «Che la testa fosse a cinque posizioni io lo sapevo da sempre
  l'abbiamo già visto almeno al tre 10 volte così come Che la verifica viene
  fatta in Blocco da cinque volendo».
- L11474: «lascia perdere guarda k4».
- L11514: «guarda anche il test t8 / somaro / è gia finito».
- L13253: «avevamo gia spostato l'indexerr ma nkn pagava, leggi il ledger».
- L13487: «bene digli di costruirlo trovando un modo! attenzione la KV non
  deve essere quella di 10 K, deve essere MASSIMO quella con kv 10k e token
  2000 pesa in vram».
- L13934: «non ha senso metterlo in coda a misure inutili».
- L14112: «perché non vai a guardare gli output per non ritrovarci poi con cose
  insensate?».
- L14316: «non è certo il per 2 che ci aspettavamo».
- L16005: «Sulla bit Esattezza a seconda che lavoriamo di più su GPU o CPU,
  avremo un output diverso o sbaglio?».
- L16014: «Ecco a questo punto, avevi fatto i due test prima guarda gli output
  di quelli che non avevano più lo stesso sha».
- L16790, citando la proposta di ridimensionare i buffer dopo il prefill:
  «questo è già l'approccio ibrido nel mio eseguibile se non sbaglio».
- L18015: «E avevamo un k variabile testato che trovava l’ottimo da solo! Quel
  k variabile potremmo agganciarlo a un contatore».
- L18301: «A me sembrava di averla già detta questa cosa, ma avevi ragionato
  solo sulle tre teste MTP a tre passate».
- L18468: «Sì, ma gli esperti del DS Park li avevi portati su GPU?».
- L18687: «cache 32 e 64 li avevi proposti prima».
- L19591: «ma scusa tutto questo non l'abbiamo già misurato mettendo tutto
  dspark in vram e tutto il backbone in ram pinnata?».
- L20500: «ma te l'avevo già detto che K dovesse essere variabile!».
- L20466: «intendevo la verifica della bozza parallelizzata su gpu e cpu invece
  di spostare anche quegli esperti».
- L21361: «Scusa, ma non avevamo una moltitudine di live da provare. C’è solo
  questo.?».
- L21420: «Ma non solo di nostro codice, parlo anche di funzioni base che non
  conoscevamo come quella di tenere kv su disco».
- L22235: «Avevi già un prompt pronto se non sbaglio fatto bene non ripetizione
  di roba».
- L23593: «Abbiamo i vecchi pesi 0731 che secondo te erano più lenti da
  decomprimere…avevamo scaricato questa versione apposta».
- L23609: «No l’avevamo scelta perché in teoria doveva essere più veloce da
  processare non per la teglia né il pin».
- L23580: «Quando dici che kernel non si tocca sbagli!! tutto quello che è
  software si può manipolare».
- L24413: «non avevamo un ub per il prefill e uno per il decode? cazzo dormi».
- L24427: «avevamo provato ub 1024...eravamo oltre 100t/s di ub in prefill...».

### Correzioni alla direzione tecnica e al problema da risolvere

- L609: «il gate va messo solo tra ssd e ram. fine! qui su llama non servono
  altri gate! la logica per massa che tiene fuori un esperto sotto soglia (da
  trovare) è il meccanismo giusto». Questa premessa appartiene alla fase prima
  dei 96 GB; L6200 la corregge poi in RAM→RAM pinnata, perché l'SSD era uscito
  dal cammino.
- L2719: «ma scusa perchè in modalità chat c'è questo calo esagerato di
  performance? non ha senso...stiamo leggendo tutto da disco!».
- L2792: «[...] abbiamo detto che il problema non è la capacità di calcolo, non
  è la ram che tiene il 90% del modello e non è l'ssd che comunque leggiamo
  molto poco, non è la cpu...che cazzo resta per velocizzare?».
- L5395: «ma indica anche la cura: leggerli in parallelo invece che uno alla
  volta...la cura si chiama fattorino o wrap...c'è anhce quello da qualche
  parte! hai letto tutte le intuizioni in generale o solo su reap loop?».
- L6477: «Ma ragionare per strato non ha senso? Meglio pernexpert?».
- L7102: «Gira e rigira mi tocca ripetere che il problema non è il trasporto».
- L7212: «Ma scusa non era più sensato lavorare su un token intero predetto
  velocemente e poi far passare quel token intero al router per vedere cosa
  chiama come esperti per il token successivo e non per singolo strato ma per
  tutti? [...] Il token lo scartiamo, la predizione esperti ci serve per la
  cache».
- L7267: «Ma non si era detto che il routing esperti è noto per i token
  successivi?».
- L7967: «ma non si poteva fare una testata più piccola, ottimizzata per cpu?».
- L8060: «ti sto dicendo che nel computing e orchestrazione bisogna lavorare
  sul parallelismo finchè non sia il trasporto il problema vero!».
- L14215: «Che poi, il primo l'abbiamo finito! [...] sfruttare il router per
  spostare in vram esattamente gli esperti Che useremo rendendo di fatto la
  cache in vram Uno spazio di rotazione che annulla totalmente il problema di
  dimensione».
- L14917: «fammi capire, sappiamo con esattezza quali esperti si devono trovare
  in vram e in quale preciso momento ma non sappiamo portarli al momento
  giusto?».
- L15842: «non capisco come portare esperti dove servono in anticipo quasi
  dinezzi risoetto al precedente sota senza overlap e dapaek! non ha senso!».
- L15956: «ma k4 disabilitando copie e migliorando il trasporto...se non
  portiamo in antjcipo che senso ha?».
- L16418: «intendevo la doppia copia quando parlavo di expert ring che per me
  èm il nuovo meccanismo fatto oggi, non quello soperato da orologio».
- L16484: «avevamo anche chiesto a codex di spiegare perchè liberare la kv col
  ring non restituiva tutto! ogni mb di vram lo voglio pieno della roba giusta!
  [...] il resto che si alloca al prefill e poi rimane incastrato bisogna
  capire come riottenerlo!».
- L17829: «Abbiamo già fatto i conti: se portassimo gli esperti in anticipo
  togliendo solo quelli non usati e lasciando quelli in comune col token
  precedente staremmo lavorando come se tutti gli esperti richiesti fossero già
  in ram!».
- L17993: «se indoviniamo l’Expert al momento giusto lo facciamo processare
  alla GPU. Se invece siamo in ritardo, facciamo fare alla CPU».
- L18448: «buttare fuori dalla rapinata esperti che non stiamo usando e sono
  completamente freddi, ha senso per far spazio a DS Park».
- L18651: «invece di portare tutto il blocco dobbiamo implementare la stessa
  politica del modello ds4 ovvero i caldi di dspark in vram, freddi fuori».
- L20439: «con K=4 potrebbe beneficiare parecchio visto tutto il lavoro che
  facciamo ora su cpu...e non abbiamo pensato al lavoro misto del drafter
  gpu/cpu...su quello ci avevamo lavorato?».
- L22714: «Con una GPU che è quasi sempre in attesa della CPU, portargli lavoro,
  non è che sia sbagliato quindi è un tipo di ottimizzazione che ha senso farla
  comunque».
- L22841: «non costerebbe pesi densi in ram perché questo meccanismo ha senso
  se se possiamo riportare il back bone dentro prima del Decode [...] durante
  le ultime fasi del prefill procediamo a gradini reintroducendo man mano tutto
  quello che serve per iniziare il decode».

### Correzioni tecniche riportate dall'utente, non `tool_result`

- L3766: «Il punto 3 del mandato è risolto, e la risposta è: nessuna perdita
  su TCP». La workstation vera `.30:3389` dà 50/50, 0% perdita, mediana 3,04
  ms, p95 3,59, minimo 2,23; il vecchio `.10` era un altro MAC/dispositivo e
  l'ICMP della workstation era bloccato. **[RIPORTATO DALL'UTENTE]**.
- L3852: backend CPU 32.471 MiB totali/23.664 liberi, spazio stimato per otto
  strati; Vulkan misurato dal rapporto a 878,9 µs gate + 878,9 µs up +
  2.295,1 µs down = 4,05 ms/strato, già peggiore dei 3,65 ms del PC principale
  prima della rete. **[RIPORTATO DALL'UTENTE]**, non misura locale nel JSONL.

## 6. Contraddizioni da riconciliare, ordinate per valore

1. **Oracolo nominale contro modello reale:** 64 piste di layer contro 43
   blocchi; 33–42% di richieste trovate contro circa 90% atteso. Tutte le
   conclusioni sul soffitto del prefetch restano sospese.
2. **`ub2048` atteso 117–125 contro misurato 59,63**, con ancora 2.645 MiB
   liberi. È un muro computazionale non spiegato.
3. **Cache/prefetch:** W0 è più veloce di W1/W2 nella campagna corretta, mentre
   due campagne D2 nominalmente simili invertono il segno. Mancano identità di
   binario e patch.
4. **KV ring 100k:** 9,29 contro 8,62 in una campagna; 8,05 contro 8,54 nella
   successiva.
5. **Capienza 448:** −1,2% sulla base FUSO5 contro −8,3% nella campagna serale.
   Il risultato serale è reale, la legge generale no.
6. **VRAM libera:** due blocchi e 305 MiB perdono 8,9%, ma la zavorra pura a
   377 MiB perde solo 0,6%. Il colpevole non è il margine da solo.
7. **Banda PCIe:** 24,35–24,46 GiB/s nel microbenchmark contro 18,4 GiB/s
   nell'audit. Probabilmente cammini diversi, oggi etichettati come uno.
8. **Hard fault:** `lock1200` è più veloce e ha una coda molto migliore pur
   mostrando più hard fault mediani del controllo.
9. **Velocità contro correttezza:** diversi bracci apparentemente rapidi hanno
   SHA diverso, contenuto nullo o ripetizioni patologiche. Il cancello output
   è stato applicato dopo, non prima, in più campagne.
10. **Restore contro riuso:** 23.693 token vengono letti in 0,78 s e lo slot ha
    LCP 1,000, ma la richiesta li ricalcola tutti in 6,19 minuti. È una
    contraddizione interna del cammino KV/prompt, non un fallimento del file.

## Verdetto sul mandato

Il mandato non era sbagliato. Il recupero trova numeri ad alto valore realmente
persi, almeno quattro affermazioni documentali da correggere e due intere
famiglie di esperimenti — oracolo e contesto lungo/restore — che la prosa aveva
trattato come più chiuse di quanto dicano i risultati grezzi.
