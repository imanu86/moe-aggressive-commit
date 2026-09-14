# P1 — Contratto della cache esperti con miss CPU e GPU

Versione 1.0, 14 settembre 2026. Fase **P1** del [piano CPU/GPU](PIANO_CPU_GPU_14_SETTEMBRE.md); misure e criteri nel [protocollo](PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md); decisioni D04, D05, D07 nel [registro](REGISTRO_CPU_GPU_14_SETTEMBRE.md). Risultati della verifica in [P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md](P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md).

Questo documento **specifica**. Non è una patch, non è un benchmark e non contiene misure di velocità. Le righe citate sono quelle lette il 14 settembre nell'albero sperimentale `C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source`, che questa fase **non modifica**. Prima di scrivere codice si riverifica il manifest: una riga spostata invalida i riferimenti, non il contratto.

## 1. Perimetro

Il contratto riguarda il planner della cache esperti a domanda di un singolo strato MoE durante il decode, con `cpu_max` in `{0, 1, 2}`. Restano fuori: l'esecutore CPU (P2), l'integrazione nel graph (P3), gli strati oltre il primo (P4), la speculazione a due o tre token (P5). Il numero massimo di esperti CPU per strato resta due (D03); lo strato 2 resta sulla GPU (D07).

Con `cpu_max = 0` il contratto deve essere **la politica attuale, senza alcuna differenza osservabile**: è la condizione di uscita di P1.

## 2. Vocabolario

| Termine | Significato preciso |
|---|---|
| Route | Una posizione della matrice degli ID del router: `n_routes = top_k * rows`, con `rows` = token del batch (da 1 a 3, `moe-demand.cuh:232`). Una route è una coppia token/esperto. |
| Richiesta unica | Un esperto distinto all'interno di una chiamata al planner, nell'ordine di prima comparsa fra le route. `plan->n_unique`. |
| Colpo (hit) | Richiesta unica il cui esperto ha già uno slot valido e reciproco. |
| Miss GPU | Richiesta unica da **trasferire** in uno slot: entra negli array di trasferimento e nel commit. |
| Miss CPU | Richiesta unica da **calcolare** sulla CPU con i pesi originali host: non entra negli array di trasferimento né nel commit. |
| Incarnazione | Una `bound_group` (`moe-demand.cuh:10-55`): un legame fra i tre tensori host e i tre banchi in VRAM. Il campo `group` della traccia è il suo `trace_id`. Un `unbind` la distrugge con tutto il suo stato. |
| Fase differita | Il commit del piano precedente, eseguito all'inizio della chiamata successiva (`fork-moe-kernels.cuh:217-254`). |
| Slot alias | Lo slot di una route GPU reale della richiesta corrente, usato come ID di calcolo per una route CPU, con peso GPU zero. |

## 3. Flusso attuale

Punto di ingresso host: `qwen_moe_demand::remap` (`moe-demand.cuh:226-284`), chiamato dal percorso `mul_mat_id` per i tensori legati. Il piano viene costruito una sola volta per strato e per chiamata, sul banco 1 oppure quando gate/up sono fusi (`moe-demand.cuh:243`), e lanciato con un solo blocco (`moe-demand.cuh:249-253`).

### 3.1 Ingressi

`ids` è il tensore I32 del router, forma `[top_k, rows]`, con passo di riga `ids->nb[1]/4` (`moe-demand.cuh:250`). Gli ID sono **ID logici di esperto** in `[0, n_experts)`, prodotti da `ggml_argsort_top_k` in `llama-graph.cpp:2064`. I pesi di routing sono un tensore separato, costruito in `llama-graph.cpp:2078` e già normalizzato (`norm_w`, righe 2089-2103) e scalato (`w_scale`, righe 2104-2107) prima di essere usato in `llama-graph.cpp:2367`. Per Qwen4exp `norm_w = true` e `w_scale = expert_weights_scale` (`qwen4exp.cpp:1446-1460`).

Il planner **non** vede i pesi: riceve solo gli ID. Questa separazione è la ragione per cui gli ID logici possono essere conservati per la contabilità mentre gli ID di calcolo vengono rimappati sugli slot.

### 3.2 Fase differita: commit del piano precedente

`fork-moe-kernels.cuh:218` entra nel ramo solo se `plan->status == MOE_GROUPED_PLAN_READY`, cioè se esiste un piano completo non ancora applicato. Vengono fatte due cose distinte:

1. **Mappatura** (righe 222-235): per ogni miss del piano precedente si legge `miss_experts[miss]` e `miss_slots[miss]`, si cancella il vecchio residente (`slot_for_expert[old_expert] = -1`) e si scrive la coppia reciproca `expert_for_slot[slot] = expert`, `slot_for_expert[expert] = slot`.
2. **Recenza e frequenza** (righe 237-253): per ogni **unico** del piano precedente si scrive `last_used[slot] = plan->next_clock - plan->n_unique + unique + 1` (riga 247) e si aggiorna `expert_frequency[expert]` con la frequenza efficace più uno, riscrivendo `expert_frequency_epoch[expert]` (righe 248-252).

Perché è differita: il gather che copia realmente i byte è accodato **dopo** il piano, sullo stesso stream (`moe-demand.cuh:257-273`). Quando il kernel del piano successivo gira su quello stream, il gather precedente è concluso per ordinamento di stream. Il differimento è quindi il meccanismo che realizza l'invariante 2: **solo un trasferimento concluso diventa residente**. Non è un effetto collaterale da rimuovere.

Conseguenza da mettere per iscritto: l'ultima ammissione di una incarnazione **non viene mai applicata**, perché non esiste una chiamata successiva. `llama_moe_cache_set_device_active(false)` (`llama-moecache.cpp:404-440`) esegue `unbind` e libera i buffer; la `bound_group` e il suo `plan` muoiono con lo stato pendente dentro. Non è un difetto osservabile — nessuno legge più quegli slot — ma va dichiarato, perché un simulatore ad ammissione immediata differisce dal kernel esattamente su quell'ultimo passo.

### 3.3 Nuovo passo, epoca, orologio

`thread == 0` azzera il piano e preleva il passo con `atomicAdd(device_step, 1)` (riga 262): il valore restituito è **pre-incremento**, quindi a base zero. L'epoca della frequenza è `step >> 6` (righe 10 e 266). La traccia diagnostica registra invece il valore del contatore **dopo** il kernel (`moe-demand.cuh:182`), quindi a base uno: sui passi della traccia l'epoca corretta è `(step - 1) >> 6`. È il difetto già corretto nel simulatore di riferimento.

L'orologio di recenza è riservato a blocchi: `device_clock` avanza di `n_routes` per piano (righe 268-283), mentre `plan->next_clock = clock_begin + plan->n_unique` (riga 530). Quindi la parte riservata e non usata viene scartata. Contano solo gli **ordini relativi** di `last_used`, non i valori assoluti: un simulatore che avanzi di `n_unique` invece di `n_routes` produce lo stesso ordine totale e la stessa scelta di vittime.

### 3.4 Deduplica

Due cammini equivalenti. Il cammino a warp (righe 298, 302-386) è attivo quando `n_routes == top_k` e `n_routes <= WARP_SIZE`, cioè nel decode a un token: usa `__match_any_sync` e i prefissi di maschera per assegnare `route_unique[route]` e `unique_experts[unique]`. Il cammino a blocco (righe 388-425) usa `atomicMin` su `expert_routes[expert]` e un ciclo seriale del thread zero. **Entrambi producono l'ordine di prima comparsa fra le route**: è l'unico ordine su cui il contratto può appoggiarsi.

### 3.5 Classificazione

Per ogni unico si legge `slot_for_expert[expert]`; un valore `>= 0` è un colpo, `-1` un miss. Si controlla la reciprocità (`expert_for_slot[slot] != expert` fa fallire il piano, righe 356-358 e 405-411). I miss vengono impilati in `miss_unique` e `miss_experts` **nell'ordine degli indici unici** (righe 373-376 nel cammino a warp, 416-421 in quello a blocco), e `plan->n_misses` è il loro numero (righe 383 e 423).

I contatori diagnostici vengono inseriti qui (righe 430-436): `demand_counters[0] += n_unique`, `demand_counters[1] += n_misses`. `report_hits` (`moe-demand.cuh:200-224`) ne ricava `colpi = 1 - mancanti/richiesti`.

### 3.6 Protezione e scelta della vittima

`route_storage` viene riusato come bitmap di protezione (righe 437-450): prima azzerato per ogni slot, poi messo a uno per ogni unico che ha già uno slot, cioè per i **colpi correnti**. Il ciclo dei miss (righe 455-512) sceglie per ciascuno il minimo di `(frequenza efficace, last_used, indice di slot)` fra gli slot con bitmap zero, con riduzione a warp e a blocco; appena assegnato, lo slot viene protetto (riga 509). `frequency_aware` viene da `GGML_CUDA_MOE_FREQUENCY` (`moe-demand.cuh:244-247`): se spento la chiave diventa `(0, last_used, slot)`, cioè LRU pura.

### 3.7 ID di calcolo

Dopo il ciclo si verifica che ogni unico abbia uno slot (righe 514-518) e si scrive `remapped_ids[route] = unique_slots[route_unique[route]]` (righe 520-525). `remap` restituisce un tensore che punta a quell'array (`moe-demand.cuh:278-283`): è ciò che `mul_mat_id` consuma come indici, e per questo gli ID originali non sopravvivono oltre questo punto.

### 3.8 Gather e tre banche

`moe_grouped_gather_decode` (righe 539-604) copia `words_per_miss * plan->n_misses` parole a 128 bit (riga 562) dai puntatori host mappati verso gli slot, scorrendo le tre banche per ogni miss. Con `QWEN_MOE_OVERLAP_DOWN=1` gate e up vanno sullo stream di calcolo e down su uno stream dedicato, con eventi `gate_ready`/`down_ready` (`moe-demand.cuh:114-121`, `240-268`). L'unità di ammissione è quindi l'esperto **con tutte e tre le banche**: non esiste uno stato valido con due banche su tre.

### 3.9 Incarnazioni

`bind` (`moe-demand.cuh:70-140`) verifica tipi, forme, contiguità, allineamento a 16 byte e che la sorgente sia memoria host mappata e la destinazione memoria del dispositivo; alloca e azzera `slot_for_expert` a `0xff` (cioè `-1`), `expert_for_slot` a `-1`, `last_used`, `frequency`, `frequency_epoch`, `step`, `clock`, `counters` e il piano. La chiave dei binding è il **puntatore dei dati di destinazione**. `unbind` (righe 142-157) cancella i binding e distrugge il gruppo. Ogni `bind` è una incarnazione nuova e vuota: nessuno stato sopravvive.

### 3.10 Punto di somma del contributo degli esperti

`experts` è il risultato di `mul_mat_id` su `down_exps` (`llama-graph.cpp:2317`), viene moltiplicato per i pesi (`llama-graph.cpp:2366-2369`), poi ridotto sommando le viste per esperto in `moe_out` (`llama-graph.cpp:2373-2400`) e restituito (riga 2404). In `qwen4exp.cpp` il valore torna come `moe_out` (riga 1446) e solo dopo viene sommato allo shared expert (riga 1484). **Il punto di somma del contributo CPU è `moe_out`, dopo la pesatura e la riduzione e prima dello shared expert.**

## 4. Flusso proposto con `cpu_max`

### 4.1 Struttura del piano

Il piano attuale ha otto array di capacità `n_slots` più `n_experts` valori (`fork-moe-kernels.cuh:53-64`, `80-91`). Il contratto ne richiede tre in più, e la dimensione va ricalcolata in `moe_grouped_plan_size`:

| Nuovo array | Contenuto |
|---|---|
| `UNIQUE_IS_CPU` | Un flag per unico: la route è servita dalla CPU. |
| `CPU_UNIQUE` | Gli indici unici serviti dalla CPU, in ordine crescente. |
| `CPU_EXPERTS` | Gli ID logici corrispondenti, per i job e per la contabilità. |

Il campo `n_misses` della struttura (`fork-moe-kernels.cuh:44-51`) assume il significato più stretto di **miss GPU da trasferire**, e serve un campo `n_cpu`. Questo non è un dettaglio interno: `n_misses` è letto dal gather (riga 562), dal commit differito (riga 222), dai contatori diagnostici (riga 434) e dalla traccia (`moe-demand.cuh:192`). Ognuno di quei punti va aggiornato **nello stesso cambiamento**, altrimenti il tasso di colpi riportato conta le route CPU come colpi.

### 4.2 Ordine delle fasi

1. **Commit differito** del piano precedente, con tre insiemi distinti:
   - mappatura: solo `miss_gpu` del piano precedente;
   - recenza: solo unici **non** CPU, con `last_used[slot] = clock_begin + indice + 1`;
   - frequenza e decadimento: **tutti** gli unici, CPU compresi.
   Il tick di orologio di un unico CPU viene consumato ma non scritto da nessuna parte: così l'aritmetica dell'indice resta quella attuale e la disposizione degli array non dipende dalla partizione.
2. **Nuovo passo, epoca, riserva di orologio**: invariati.
3. **Deduplica**: invariata, ordine di prima comparsa.
4. **Classificazione** sugli ID logici originali: colpo se `slot_for_expert[expert] >= 0` e reciproco.
5. **Partizione dei miss in CPU e GPU**, prima di qualunque assegnazione di slot e prima del gather.
6. **Assegnazione degli slot ai soli miss GPU**, con la stessa regola di vittima e la stessa protezione. Gli unici CPU non hanno slot e non proteggono nulla: sono miss, quindi non erano residenti, quindi non c'è nulla da proteggere.
7. **Array di trasferimento e commit**: contengono solo i miss GPU.
8. **ID di calcolo**: `remapped_ids[route]` è lo slot dell'unico, oppure lo **slot alias** se l'unico è CPU.
9. **Pesi**: il peso GPU della route CPU è esattamente zero; i pesi GPU rimanenti restano identici bit per bit. **Nessuna rinormalizzazione.**
10. **Job CPU**: uno per ogni route la cui richiesta unica è CPU, con token, ID logico dell'esperto e peso originale.

### 4.3 Quanti miss alla CPU

```
n_idonei = numero di miss idonei al ramo CPU
n_cpu    = max(0, min(cpu_max, n_idonei, n_unique - 1))
```

Il termine `n_unique - 1` garantisce che **resti almeno un unico GPU** da cui prendere lo slot alias. Con `top_k = 10` non è vincolante nel decode a un token, ma deve esistere come guardia: se una generalizzazione futura lo rende vincolante, serve un percorso apposito e non il riuso implicito dello slot zero (piano, paragrafo sul limite di due esperti CPU).

`n_idonei` esclude i miss di uno strato non supportato. L'idoneità è una proprietà dello strato e del formato, decisa **prima dell'invio** (invariante 7): strato 2 escluso per IQ3_S (D07), e guardie del primo ramo (banche contigue separate, SiLU, nessun bias/scala/LoRA, gate e up non uniti, nessuna pesatura prima dell'FFN). Con `n_idonei = 0` il piano è identico a `cpu_max = 0`.

### 4.4 Quali miss alla CPU: ordine deterministico proposto

**Proposta per P3: i primi `n_cpu` miss nell'ordine degli indici unici**, cioè l'ordine in cui `miss_unique`/`miss_experts` sono già riempiti, che è l'ordine di prima comparsa fra le route del router.

Motivazioni:

1. È **già materializzato** da entrambi i cammini del kernel (righe 373-376 e 416-421). Non serve nessun ordinamento aggiuntivo, nessuna lettura extra di stato del dispositivo, nessuna riduzione in più dentro un kernel a blocco singolo.
2. Non legge **nulla** dello stato della cache: la partizione non dipende da frequenza, recenza o mappatura. Le due politiche restano separate, e un difetto nella regola di sfratto non può spostare la partizione né viceversa. È la proprietà che rende P1 falsificabile con un riferimento in Python.
3. È calcolato **prima** dell'assegnazione degli slot, quindi è invariante rispetto a qualunque cambiamento futuro della regola di sfratto.
4. Dipende solo dall'uscita del router, quindi è identico fra cammino a warp e cammino a blocco, e riproducibile esattamente fuori dalla GPU.

Limite dichiarato: è **cieco al riuso**. Un esperto molto richiesto che compare sempre fra i primi miss può vedersi negata l'ammissione a ogni passo, e il piano avverte esplicitamente che saltare l'ammissione di un esperto richiesto spesso può annullare il risparmio del passo corrente. Sulla traccia storica questo costa, nel tratto caldo, colpi GPU dal 75,55% al 70,58% con `cpu_max = 2` (numeri nel rapporto; **non** sono t/s).

Alternative da confrontare in P4, tutte già implementate come opzioni nel simulatore:

| Ordine | Regola | Perché confrontarlo |
|---|---|---|
| `freq` | Frequenza efficace minima prima | Manda alla CPU ciò che serve meno: mitiga direttamente il limite sopra. Sulla traccia storica trattiene più colpi e meno byte dell'ordine di route. Costo: legge lo stato della cache dentro la partizione, quindi accoppia due politiche. |
| `freq_high` | Frequenza efficace massima prima | Controllo di segno: se `freq` non fosse meglio di `freq_high`, il segnale di riuso non esiste su questo carico. |
| `expert` | ID logico minore prima | Controllo dell'effetto dell'ordine del router: indipendente dalla posizione nella top-k. |
| `last` | Ultimo miss scoperto prima | Secondo controllo dell'ordine, a costo zero. |
| Costo misurato | Frazione da banda osservata in concorrenza, `PCIe/(PCIe+CPU)` come nella calibrazione FreeToken | È il criterio che il progetto esterno usa davvero; richiede però una misura di concorrenza sulla nostra macchina, quindi non prima di P4. |
| Predizione di route | Riuso previsto dal predittore del gate dello strato successivo | Esiste già un risultato che lo dà praticamente gratuito; introduce una dipendenza fra strati e va valutato dopo. |

Non è un'alternativa il criterio per **dimensione del payload**: dentro uno strato tutti gli esperti hanno lo stesso numero di byte (1.971.200 su 47 strati, 2.329.600 sullo strato 2). Diventerebbe rilevante solo con formati diversi per esperto.

### 4.5 Slot alias a peso GPU zero

Lo slot alias è `unique_slots[j*]` con `j*` **il minimo indice unico non CPU**. Regole:

- deve essere `>= 0`: un colpo corrente o un miss GPU di questo stesso piano;
- è **protetto dal piano**, perché la bitmap di protezione contiene tutti i colpi e tutti gli slot assegnati (righe 446-450 e 509): nessuno sfratto di questo piano può toccarlo;
- se è un miss GPU, le tre banche vengono scritte dal gather di **questo** piano, accodato prima del `mul_mat_id` che le consuma: è pronto al momento del consumo;
- non è mai uno slot arbitrario e non richiede capacità riservata: nessuno slot viene sottratto alla cache, nessun conteggio di slot cambia.

La GPU esegue quindi calcoli su righe fittizie e li moltiplica per zero. È una scelta voluta di D05 per tenere ferme le dieci righe GPU e la topologia del graph, e il suo costo va misurato in P3/P4; una maschera che salti il calcolo prima di leggere i pesi si valuta solo dopo.

### 4.6 Pesi e punto di somma

La maschera si applica **dopo** la normalizzazione (`llama-graph.cpp:2089-2103`) e la scala (righe 2104-2107): si azzera il peso della sola route CPU nel tensore consumato da `llama-graph.cpp:2367`, e i pesi delle altre route restano quelli originali. Non si rinormalizza: la somma dei pesi effettivamente applicati resta quella del router perché il contributo mancante viene aggiunto dalla CPU con lo **stesso** peso originale, non perché si ridistribuisca.

Il contributo CPU per il token `t` è `somma sulle route CPU di t di peso[route] * FFN(esperto[route], x_t)` e va sommato a `moe_out` dopo la riduzione (`llama-graph.cpp:2389-2400`) e prima dello shared expert (`qwen4exp.cpp:1484`). Non passa una seconda volta per la moltiplicazione dei pesi. Va verificato che le fusioni CUDA della riduzione consumino il tensore dei pesi mascherato e non quello originale.

### 4.7 Job CPU

Un job è la terna `(token, esperto logico, peso originale)`. I **pesi trasferiti** si deduplicano per esperto; il **calcolo** non si deduplica fra token diversi: con `rows > 1` lo stesso esperto CPU su due token genera due job. Il numero di esperti CPU è limitato da `cpu_max`, il numero di job no.

## 5. I sette invarianti: controllo concreto e punto del flusso

| # | Invariante | Controllo concreto | Dove si verifica |
|---|---|---|---|
| 1 | `richieste uniche = hit GPU + miss GPU + miss CPU`, coppie contate a parte | `assert n_unique == hits + n_miss_gpu + n_cpu` dopo la partizione; `assert n_routes == len(coppie) and len(set(coppie)) == len(coppie)`; sul dispositivo tre contatori invece di due e `counters[0] == somma(counters[1..2]) + colpi` | Fine del passo 5 di §4.2; nel kernel subito dopo la partizione, dove ora stanno gli `atomicAdd` (righe 430-436) |
| 2 | Nessuna ammissione fittizia: solo trasferimenti conclusi diventano residenti | `assert esperti_cpu ∩ esperti(miss_gpu) == vuoto` e `assert esperti_cpu ∩ vittime == vuoto` nel piano; dopo ogni commit `assert slot_for_expert[e] == -1` per ogni esperto CPU del piano committato; `assert len(array_trasferimento) == n_miss_gpu` | Passi 5 e 7 di §4.2; dentro il ramo `status == READY` (righe 218-235) e nel gather, che deve leggere solo `n_misses` come miss GPU |
| 3 | Tutte le richieste logiche in frequenza/decadimento; recenza e ammissione solo su slot validi; LFU non sostituita da LRU | Contatori di commit: `assert aggiornamenti_frequenza == n_unique` e `assert scritture_recenza == n_unique - n_cpu`; ricalcolo indipendente della vittima come `argmin(freq_efficace, last_used, slot)` fra gli slot non protetti e confronto con la scelta del piano | Passo 1 di §4.2 (righe 237-253) e passo 6 (righe 455-512) |
| 4 | Colpi protetti, mappatura reciproca, tre banche dello stesso esperto, nessun dato parziale consumato | Dopo ogni commit: `expert_for_slot[s] = e >= 0 ⇒ slot_for_expert[e] == s` e viceversa, `last_used[s] != 0`, `banche_scritte[s] == 3`; nel piano: la vittima non è mai un esperto colpito né uno slot già assegnato, gli slot assegnati sono distinti; al consumo: `slot_pronto[s] <= indice_piano` per ogni slot in `remapped_ids`, alias compreso | Commit (passo 1) e assegnazione (passo 6); il controllo di prontezza al passo 8 |
| 5 | Ogni coppia token/esperto contribuisce una volta con il peso originale; i pesi si deduplicano, il calcolo no | Per ogni route esattamente una sorgente: `peso_gpu[r] == peso[r]` e nessun job, oppure `peso_gpu[r] == 0.0` ed esattamente un job con `peso == peso[r]`; confronto del **multiinsieme** dei contributi con quello dei pesi originali, non di una somma in virgola mobile; `len(job) == numero di route con unico CPU` | Passi 9 e 10 di §4.2; in P3 si aggiunge il confronto numerico del `moe_out` con il percorso interamente GPU |
| 6 | Nessun callback usa API CUDA o attende un mutex del thread che aspetta il graph; buffer e proprietari vivono fino alla fine degli utilizzatori e dei graph | Non simulabile in Python. Controllo statico: nel corpo del callback nessun simbolo `cuda*`/`cu*` e nessun `lock` di `bindings_mutex` (`moe-demand.cuh:62`); controllo dinamico: un solo proprietario seriale per contesto con `assert` di non rientranza, e distruzione del pool solo dopo l'invalidazione dei graph che referenziano i buffer (`ggml-cuda.cu` intorno a 3666) | P2, con prove di cancellazione e cambio contesto |
| 7 | Un errore invalida la richiesta: nessuno zero come risultato, nessun trasferimento dichiarato concluso; fallback deciso prima dell'invio | Nel simulatore: un piano fallito non resta pendente, non ammette nulla, **rimuove dalla mappatura i residenti degli slot già sovrascritti dal gather** e marca la cache come contaminata; ogni piano successivo è rifiutato finché non si esegue la pulizia esplicita (equivalente a unbind/bind). Fallback: `n_idonei = 0` deve dare un piano identico a `cpu_max = 0` | Passo 5 per il fallback; il ramo di errore è esercitato dallo scenario dedicato e va replicato in P2/P3 |

Sull'invariante 7 il contratto dice una cosa che il codice attuale non dice: se il gather del piano corrente ha già sovrascritto uno slot e poi qualcosa fallisce, il **vecchio** residente di quello slot non esiste più in VRAM mentre la mappatura lo dichiara ancora presente, perché il commit è differito. Il recupero non può quindi limitarsi a scartare il piano: deve invalidare quegli slot, e la via sicura è buttare l'incarnazione.

## 6. Punti in cui il codice attuale rende ambigua la semantica

| Ambiguità | Dove | Come la scioglie il contratto |
|---|---|---|
| `plan->n_misses` significa insieme «miss» e «trasferimenti da fare» | `fork-moe-kernels.cuh:222`, `434`, `562`; `moe-demand.cuh:192` | `n_misses` diventa esclusivamente **miss GPU**; i miss CPU hanno un campo e array propri. Tutti e quattro i lettori vanno aggiornati nello stesso cambiamento. |
| Il commit differito è l'unico punto che rende residente un esperto, ma il codice non lo dichiara e non lo verifica | `fork-moe-kernels.cuh:217-235` | Il differimento è elevato a **meccanismo dell'invariante 2** e vincolato: il commit deve avvenire su uno stream ordinato dopo il gather del piano pendente. |
| L'ultima ammissione di una incarnazione non viene mai applicata | `moe-demand.cuh:142-157`, `llama-moecache.cpp:404-440` | Dichiarato. Il simulatore lo riproduce e il confronto con un riferimento ad ammissione immediata lo esclude esplicitamente (`flush_per_verifica`). |
| Quanto può restare pendente un piano `READY` | `fork-moe-kernels.cuh:218` | Il contratto richiede che fra il gather di un piano e il commit del successivo non ci siano rilasci di buffer, cambi di stream non ordinati, né passaggi prefill/decode con `LLAMA_MOE_PHASE_CACHE` che liberino gli slot. Se una di queste cose può accadere, il commit pendente va annullato con l'incarnazione. |
| Il ciclo del commit tratta recenza e frequenza come una cosa sola | `fork-moe-kernels.cuh:237-253` | Separate: frequenza per tutti gli unici, recenza solo per gli unici con slot. |
| `route_storage` è un array riusato per tre scopi (esperti per route, poi bitmap di protezione) | `fork-moe-kernels.cuh:328`, `443`, `448`, `509` | Non lo si riusa per la partizione: i flag CPU stanno in array propri. Dopo riga 443 gli esperti per route non sono più leggibili da lì, e il contratto vieta di dedurli da `route_storage`. |
| `if (unique_slots[unique] < 0) fail` renderebbe illegale un unico CPU | `fork-moe-kernels.cuh:514-518` | La condizione diventa «slot mancante **e** unico non CPU». |
| `remapped_ids` non ammette un valore «nessuno slot» | `fork-moe-kernels.cuh:520-525` | Si scrive lo slot alias, mai `-1`, e si azzera il peso GPU. Nessun nuovo significato di `src[3]` e nessun ID negativo (D05). |
| Il tasso di colpi riportato è `1 - mancanti/richiesti` | `moe-demand.cuh:200-224` | Con i miss CPU quella formula li conterebbe come colpi. Servono tre contatori e due percentuali distinte, colpi GPU e quota CPU. |
| La traccia diagnostica non ha un campo per i miss CPU | `moe-demand.cuh:190-195` | Lo schema della traccia va esteso con `misses_cpu` prima di riusarla per un replay con CPU attiva; altrimenti un replay futuro confronterebbe grandezze diverse. |
| `frequency_aware` può cambiare la politica sotto il naso del simulatore | `moe-demand.cuh:244-247` | L'identità con il riferimento vale solo con `GGML_CUDA_MOE_FREQUENCY` non impostata a zero. Va registrato nel manifest di ogni corsa. |
| L'orologio riservato (`n_routes`) e quello consumato (`n_unique`) divergono | `fork-moe-kernels.cuh:268-283`, `530` | Dichiarato benigno: conta l'ordine totale di `last_used`, non il valore. Un unico CPU consuma un tick senza scriverlo. |
| L'identità di una incarnazione è il puntatore dei dati di destinazione | `moe-demand.cuh:85`, `137` | Il contratto usa l'incarnazione come confine dello stato: nessun dato attraversa un `unbind`, nemmeno un piano pendente. |

## 7. Fuori dal contratto P1

Non sono specificati qui, e non vanno dedotti da questo documento: l'interfaccia host dell'esecutore e la durata degli oggetti (P2), la forma del graph e la cattura/replay (P3), la scelta del preset e i core (P4), la semantica a due o tre token della speculazione (P5), qualunque conclusione su token al secondo. Le curve di colpi e byte per `cpu_max` 0, 1 e 2 nel rapporto sono **informative**: il piano stabilisce esplicitamente che non si pretende lo stesso tasso di colpi della vecchia ammissione.
