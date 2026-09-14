# P7 · cella 4 — l'impianto a polling, e la corsia CPU sulle righe di bozza — 14 settembre 2026

Cella in **due stadi con un cancello secco in mezzo**. Parte da
[P7 cella 3](P7_RIGA_DI_VERIFICA_14_SETTEMBRE.md) §5.1 (il progetto della corsia CPU),
da [P4-costo](../p4_costo/P4_COSTO_MECCANISMO_14_SETTEMBRE.md) §5.1 e
[P4-estensione](../p4_estensione/P4_ESTENSIONE_14_SETTEMBRE.md) §2.4 e §10 (la variante **C9**,
descritta due volte e mai fatta), e dal [progetto P2](../p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md)
§7, §9, §11.

Patch incrementale [`p7_cella4.patch`](p7_cella4.patch), **9 file**, diff `-d` rispetto allo stato
dopo P4-estensione. Log in [`log/`](log/), preset `preset_S<n>_p7.json` in
[`../banco_p0/`](../banco_p0/). Nessun commit.

---

## 0. Verdetto in cinque righe

1. **Stadio 1 — il cancello passa.** L'ultimo `cudaLaunchHostFunc` sparisce: l'attesa del contributo
   CPU la fa un kernel che gira a vuoto su una parola mappata scritta dal pool. L'impianto per strato
   passa da **59,8 a 13,8 µs** (−77%), sotto il cancello di 15; a 47 strati sono **+0,65 ms per
   token** contro i +2,81 di oggi. Impronte identiche al riferimento spento in tutte e quattro le
   celle a `cpu_max = 0` (S1, S2, S5 r1 e r2) e nelle due repliche del riferimento (§3).
2. **Il costo del nodo host era 46,0 µs per strato**, coerente con la stima indipendente di
   P4-estensione (42,3). E sul *costo per strato attivo* a `cpu_max = 2` l'intervento vale ancora di
   più: **75,9 → 41,9 µs** (§3.4).
3. **Stadio 2 — la corsia CPU sulle righe di bozza funziona e risparmia quanto previsto**: con
   l'MTP a bozza 1 e 47 strati accesi, i contatori reali del dispositivo danno **47,8% dei byte
   degli esperti risparmiati**, **2,61 esperti CPU per strato** contro i 2,39 simulati dalla cella 3,
   invariante 1 verificato riga per riga, **zero valori non finiti**, nessuno stallo (§5).
4. **Ma il cancello dello stadio 2 non passa, e non passa nemmeno quello di correttezza.** Sul
   **tempo**: `R ≈ 19,7 ms` contro un cancello di **13** — la corsia doveva togliere 5,5 ms alla riga
   e invece ne aggiunge 3,9; sul t/s, **27,243 contro 30,238 = −9,9%** (§6.6). Sulla **correttezza**:
   le impronte **non** sono identiche a M1, e non potevano esserlo — la cella 3 aveva scritto «la
   corsia calcola la stessa FFN, quindi il testo non deve cambiare», ma il contributo CPU non è
   bit-identico per costruzione (P2 §8) e con l'MTP a bozza 1 la riga di bozza **produce un token
   accettato**, non una semplice verifica (§5.4). L'accettazione cala da 0,770 a **0,697**.
5. **Per arrivare a quel numero è servito trovare un difetto che valeva un fattore 12, e che non era
   dove sembrava.** La prima misura dava `R ≈ 695 ms`: sembrava l'aritmetica CPU, e sarebbe stata
   la conferma del difetto n. 5 della cella 3. **Non lo era**: la cella di diagnosi — corsia accesa
   e pool che **non calcola niente** — misura lo **stesso** t/s. La causa vera è che il batch di
   verifica della speculazione ha due token, viene quindi classificato `batched`, e da lì il pool
   finisce in fase **prefill**, dove il coordinatore si addormenta su un'attesa da 1 ms che su
   Windows dura un tick dello scheduler: **47 strati × 15,6 ms = 734 ms per ciclo**, esattamente il
   costo osservato. Tre righe di correzione (§6.5) valgono **2,31 → 27,24 t/s** (§6.3, §6.6).

---

## 1. Che cosa è stato toccato, e che cosa no

| | |
|---|---|
| Copia di lavoro | `D:\ds4_work\p3_work\source` (già patchata da P3, P4-costo, P4-estensione), **9 file** modificati |
| Stato di partenza congelato | `D:\ds4_work\p7_cella4_base` (gli stessi byte del 14/9 13:05, lato sinistro del diff; mai modificato) |
| Build | `D:\ds4_work\p3_work\build`, `compila.ps1`, **cinque** compilazioni: impianto a polling (16:26), un errore di sintassi (16:43, codice 1), correzione (16:44), corsia di bozza (17:14), gate dimenticato del difetto 1 (17:25). Quattro a codice 0 |
| **Non** toccati | `qwen38_clean\bin_prod`, `qwen38_clean\source` e la sua build, il lanciatore quotidiano, i modelli, lo snapshot `D:\ds4_work\p0_snapshot_20260914` |
| Commit | nessuno |
| Server | uno alla volta, guardia d'istanza unica (`netstat` + `tasklist`) superata prima di **ognuno** degli avvii; nessun processo residuo al termine |
| RAM libera minima | registrata per ogni corsa: **7,6 GB** nelle celle senza MTP, **5,1 GB** in quelle con i due modelli caricati (soglia di invalidità 4 GB). Nessuna cella invalida per R-RAM, ma il margine con l'MTP è di un solo gigabyte (§1.1) |

Le opzioni nuove sono **tre**, tutte **spente di default**:

| variabile | valori | default | che cosa fa |
|---|---|---|---|
| `LLAMA_MOE_CPU_POLL` | 0/1 | **0** | toglie l'ultimo nodo host: l'attesa del contributo CPU diventa il prologo della guardia del merge, che gira a vuoto sulla cella `complete` scritta dal pool |
| `LLAMA_MOE_CPU_POLL_US` | N | 50000 | scadenza del giro a vuoto, misurata **dentro** il kernel con `clock64()` |
| `LLAMA_MOE_CPU_DRAFT_ROWS` | 0/1 | **0** | corsia CPU sulle sole righe di bozza: gli esperti non residenti chiesti soltanto dalle righe oltre la prima non si trasferiscono e non si ammettono |

### 1.1 Le corse

Tutte sul profilo `fumo`, budget screening. `RAM min` è la RAM **libera** minima campionata durante
la corsa: sotto 4 GB la cella sarebbe invalida (R-RAM).

| corsa | cella | che cos'è | esito | RAM min |
|---|---|---|---|---:|
| `20260914_163054` | S0 r1 | riferimento spento | valida | 7,65 GB |
| `20260914_163550` | S1 | 47 strati, nodo host | valida | 7,74 GB |
| `20260914_164056` | S2 | 47 strati, polling a **tre** letture PCIe | valida | 8,03 GB |
| `20260914_164805` | S5 r1 | 47 strati, polling a **una** lettura | valida | 8,14 GB |
| `20260914_165330` | S0 r2 | riferimento spento, replica | valida | 8,15 GB |
| `20260914_165822` | S5 r2 | polling, replica | valida | 8,13 GB |
| `20260914_170320` | S3 | 8 strati `cpu_max=2`, polling | valida | 8,18 GB |
| `20260914_170805` | S4 | 8 strati `cpu_max=2`, nodo host | valida | 8,15 GB |
| `20260914_171850` | S6 | MTP bozza 1, corsia spenta (neutralità dei binari) | valida | 5,44 GB |
| `20260914_172345` | S7 r1 | MTP bozza 1, corsia «accesa» | **VUOTA**: la corsia non è mai partita (difetto 1) | 5,45 GB |
| `20260914_172928` | S9 | MTP bozza 1, corsia accesa, **contatori** | **INVALIDA come tempo**, valida come lettura dei contatori: fermata dalla contaminazione (§6.2) | 5,20 GB |
| `20260914_174313` | S7 r2 | MTP bozza 1, corsia accesa, contatori spenti | valida | 5,12 GB |
| `20260914_175404` | S10 | come S7 ma **senza aritmetica CPU** (`NOCOMPUTE=1`) — la diagnosi che ha trovato la causa vera (§6.3) | valida | 5,12 GB |
| `20260914_181444` | S11 | come S7 con la **fase del pool corretta** (§6.5) | valida | 5,12 GB |
| `20260914_183050` | S12 | riferimento a corsia spenta **sullo stesso binario** di S11 | valida | 5,43 GB |

Tredici corse valide, una invalida come misura di tempo, una vuota. **La RAM libera minima non è mai
scesa sotto 5,1 GB**, ma nelle corse con l'MTP il margine sulla soglia è di un solo gigabyte: con
due modelli caricati questo banco è vicino al limite, e va detto.

---

## 2. Stadio 1 — l'impianto a polling

### 2.1 Che cosa c'era già, e che cosa mancava davvero

Vale la pena scriverlo, perché la metà del lavoro era già fatta e non se ne era accorto nessuno:
**una delle due direzioni della segnalazione era già a polling da P4-estensione.**

| direzione | come era | chi l'ha fatta |
|---|---|---|
| dispositivo → host («job pronto») | il kernel di export scrive `flags->publish`, un numero di generazione preso da un contatore atomico in VRAM; il coordinatore del pool gira a vuoto su quella cella e poi blocca con `WaitOnAddress` | **P4-estensione, intervento 1** |
| host → dispositivo («contributo pronto») | un `cudaLaunchHostFunc` che sveglia un thread del driver: **42,3 µs per strato** | — |

L'incarico di questa cella descrive entrambe le direzioni. La prima esisteva già, parola per parola
(«un thread CPU dedicato che aspetta — spin breve poi `WaitOnAddress` — su una parola in memoria
mappata scritta da un kernel GPU minuscolo alla fine del planner, con generazione»). **Mancava solo
la seconda**, ed è quella che costava.

### 2.2 Il progetto: l'attesa è il prologo della guardia, non un kernel in più

La forma più ovvia — un kernel `wait` dedicato accodato dove stava il nodo host — costa un lancio.
Su 47 strati un lancio vale qualche microsecondo per strato, e il cancello è a 15: buttarne cinque
per un kernel che non calcola niente sarebbe stato un cattivo affare.

La guardia del merge (`moe_cpu_merge_guard_kernel`) è **già accodata nel punto esatto in cui
serviva l'attesa**: dopo il lavoro GPU dello strato e prima dell'`add` che consuma `y`. È il punto
che P4-estensione §2.4 indicava («la guardia stessa gira a vuoto sulla cella `done` in memoria
mappata»). L'attesa diventa quindi il **prologo** di quel kernel: nessun lancio in più, nessun nodo
in più nel grafo.

```
   plan_L, export_L  (scrive descrittore + attivazione, poi publish = n)   <- VRAM: pub_counter = n
   gather_L, lavoro GPU L                       <- il pool calcola qui, in parallelo
   guardia_L : thread 0 gira su `complete` finche' complete >= n           <- l'ATTESA
               poi veleno / diagnostica / NaN come prima
   add_L : moe_out += y
```

Le due celle nuove della struttura dei flag, entrambe in memoria host mappata:

| cella | chi la scrive | chi la legge |
|---|---|---|
| `complete` | il **coordinatore del pool**, come ultima cosa dopo `publish_flags` e dopo `y` | il kernel di attesa |
| `gpu_timeout` | il **kernel**, quando la scadenza scade | l'host, a fine decode |

### 2.3 Come si evita lo stallo col replay del graph

Il grafo viene catturato una volta e rigiocato a ogni token (7 catture su ~2.700 lanci in questa
cella, gli stessi numeri di P3 e P4). I nodi di attesa sono dentro il grafo e vengono rieseguiti
tali e quali. La condizione da evitare è «il kernel attende un numero che nessuno alzerà mai».
È chiusa da quattro proprietà, tutte nel codice e nessuna probabilistica.

1. **Il numero atteso non è un parametro del nodo.** `want` si legge **al momento
   dell'esecuzione** dal contatore di pubblicazione `pub_counter`, che vive in VRAM e viene
   incrementato con `atomicAdd` dal kernel di export dello stesso replay. Un replay non può quindi
   leggere il numero di un replay precedente: il valore è sempre quello appena scritto.
2. **La generazione è strettamente crescente su tutto il processo.** Un numero già concluso è per
   costruzione *minore* di quello nuovo, quindi un `complete` vecchio non può mai far passare
   un'attesa nuova — che è esattamente il modo in cui un flag booleano avrebbe fallito.
3. **Uno strato che non pubblica non attende.** Se questo strato ha ripiegato sul percorso GPU
   (piano fallito, righe fuori perimetro, bit `export` spento), `pub_counter` porta ancora il numero
   dello strato precedente, **già concluso**: il confronto è vero al primo giro e il kernel ritorna
   senza aspettare. È la stessa guardia del nodo host di P4-estensione, scritta sullo stesso numero.
4. **Ogni numero pubblicato viene sempre concluso.** Il kernel di export pubblica anche quando il
   piano è fallito (scrive `magic = 0` e pubblica lo stesso); il pool prende il job, lo rifiuta per
   intestazione non valida e alza `complete`. Un piano fallito resta uno **stato**, non un blocco
   (invariante 7 di P2).

E quando niente di tutto questo basta — il pool è morto, o troppo lento — c'è la **scadenza dentro
il kernel**, che è la ragione per cui la cella C9 era stata rimandata due volte («un `wait` a giro
sul dispositivo non ha un modo pulito di essere annullato dall'host», P2 §9.1):

- il budget arriva in **cicli di SM**, convertito sull'host dal clock nominale del dispositivo
  (`cudaDevAttrClockRate`), e si misura con `clock64()` dentro il kernel. Sotto throttling il budget
  reale è più lungo del nominale, mai più corto: è il verso giusto per una scadenza di sicurezza, e
  resta due ordini di grandezza sotto il TDR di Windows;
- alla scadenza il kernel scrive `gpu_timeout = want`, alza `poison` — così la guardia scrive NaN
  invece di una somma plausibile — e **scrive anche `complete = want`**. Quest'ultima è una bugia
  deliberata, e serve a una cosa sola: un pool fermo deve costare **una** scadenza, non una per
  strato. La verità sul guasto sta in `gpu_timeout` e nel veleno, che non vengono toccati;
- l'host legge `gpu_timeout` una volta per decode, fuori dal grafo, dentro
  `llama_moe_cpu_contaminated()`: una parola di memoria mappata. La registra **una volta sola** come
  esito `timeout` nella macchina a stati di P2, il job diventa irrecuperabile e il decode fallisce.
  **Questo meccanismo è scattato davvero nello stadio 2** (§6.2): non è una rete teorica.

Quello che il modo polling *non* ha, e va dichiarato come P4-estensione dichiarò il suo prezzo:
`cancel()` non è esercitabile dal kernel, e la scadenza non strappa il job al coordinatore — lo
marca. È la stessa scelta del modo fuso, per la stessa ragione (il proprietario unico dell'esito è
il coordinatore).

### 2.4 Il costo delle letture PCIe: perché la prima forma non passava il cancello

Il prologo è fatto di letture di memoria host mappata, e **ognuna è un giro di PCIe**. La prima
stesura ne faceva tre — `publish`, `gpu_timeout`, `complete` — e ha misurato **16,0 µs per strato**:
sopra il cancello. Due si tolgono senza perdere niente:

- `want` non si legge da `flags->publish` (host mappata) ma da `pub_counter` (VRAM): dopo il kernel
  di export i due valori sono **lo stesso numero** per costruzione, e la VRAM costa un ordine di
  grandezza meno;
- `gpu_timeout` non si legge affatto nel percorso veloce, perché la scadenza scrive anche
  `complete` (§2.3).

Resta **una** lettura PCIe, quella che porta l'informazione cercata. Misura: **13,8 µs per strato**.

Le due forme sono state misurate entrambe e sono entrambe nella tabella: la prima non è stata
cancellata perché è la misura del costo di un giro di PCIe in questo punto — **~1,1 µs per lettura
per strato**, un numero che vale per qualunque altra cella voglia leggere una parola mappata da un
kernel.

---

## 3. Stadio 1 — le misure e il cancello

Scala **amplificata**, la stessa di P4-estensione: lo stesso impianto su **47 strati** con
`cpu_max = 0`, profilo `fumo` (2 casi, 1.396 token), `LLAMA_MOE_CPU_REPORT=0`, contatori spenti.
Nessuna route viene deviata, `y` resta zero, **l'uscita del modello non cambia** — e infatti le
impronte restano identiche allo spento in tutte le celle, cioè l'oracolo funziona anche qui.

### 3.1 La tabella

| cella | configurazione | ms/token | Δ su S0 | **µs/strato** | impronte |
|---|---|---:|---:|---:|---|
| **S0** r1 / r2 | ibrido spento — riferimento | 42,140 / 42,178 — **media 42,159** | — | — | identiche |
| **S1** | impianto leggero di P4-estensione: **UN nodo host** per strato | **44,971** | +2,812 | **59,8** | identiche |
| **S2** | polling, prima forma (**tre** letture PCIe nel prologo) | 42,911 | +0,752 | 16,0 | identiche |
| **S5** r1 / r2 | **polling, forma finale (una lettura PCIe)** | 42,788 / 42,824 — **media 42,806** | **+0,647** | **13,8** | identiche |

Ripetibilità: S0 due repliche a **0,09%** di distanza (42,140 / 42,178), S5 due repliche a **0,08%**
(42,788 / 42,824). È lo stesso pavimento di rumore dichiarato da P4-costo (±0,03 ms per token), e
le differenze in tabella sono tutte risolte con margine.

S1 riproduce la cella E4 di P4-estensione (44,993 ms/token) a **0,022 ms** di distanza, su una build
diversa e a un'ora di distanza: la scala amplificata resta ripetibile fra build, come già osservato
fra E1 e C15.

*Avvertenza, perché mescolare build in un confronto è un difetto se non lo si dichiara.* S0 r1, S1 e
S2 girano sulla **prima** build (16:26); S0 r2, S5 r1/r2, S3 e S4 sulla **seconda** (16:44), che
differisce solo per il prologo dell'attesa. Il confronto che decide il cancello — **S5 contro S0 r2**
— è quindi *dentro* la stessa build; e le due repliche di S0, una per build, distano **0,09%**, cioè
meno del pavimento di rumore. Il confronto S1 − S5, che dà i 46,0 µs del nodo host, attraversa
invece le due build, e va letto con quel margine.

### 3.2 Il cancello

> **Cancello: impianto ≤ 15 µs/strato a 47 strati, `cpu_max=0`, profilo `fumo`, impronte identiche
> al riferimento spento.**
>
> **Misura: 13,8 µs/strato** (+0,647 ms per token su 47 strati, contro i +2,81 dell'impianto con
> nodo host). Impronte identiche in 6 corse su 6 (S0 r1/r2, S1, S2, S5 r1/r2). **PASSA.**

Il margine è 1,2 µs per strato, cioè 0,056 ms per token: circa due volte il pavimento di rumore, e
confermato da due repliche indipendenti. Non è un margine largo, e va detto.

### 3.3 Dove sono finiti i 46 µs

| pezzo | µs/strato | da dove |
|---|---:|---|
| nodo `add` | 2,9 | P4-costo (C11 − C10) |
| kernel di export | 5,1 | P4-costo (C12 − C11) |
| guardia leggera | 3,3 | P4-estensione (15,0 − 11,7) |
| **prologo di attesa sul dispositivo** | **~2,5** | questa cella, per differenza |
| — *la stessa attesa come nodo host* | *48,5* | S1 − (add + export + guardia) |
| **impianto a polling, totale** | **13,8** | **S5 − S0** |
| impianto con nodo host, totale | 59,8 | S1 − S0 |

**Il nodo host costava 46,0 µs per strato** (S1 − S5). La stima indipendente di P4-estensione lo
metteva a 42,3 (ricavata da E1 − E2 sul nodo `submit`) e quella di P4-costo a 41,9 (C14 − C13): le
tre misure concordano entro il 10%, e la nostra è la più alta perché il nodo che resta è quello che
**blocca**, non quello che pubblica.

### 3.4 Calibrazione a `cpu_max = 2` — il costo per strato ATTIVO

Otto strati (`0,1,6,7,12,18,22,38`, gli stessi di EB8), `cpu_max = 2`, profilo `fumo`. Qui il pool
calcola davvero, quindi il testo cambia rispetto allo spento (rischio R10 di P2, atteso): le
impronte di S3 e S4 sono **identiche fra loro** — cioè l'attesa sul dispositivo e il nodo host
producono lo stesso identico testo, che è la prova di correttezza della sostituzione — e diverse da
S0.

| cella | attesa | ms/token | Δ su S0 | **µs/strato attivo** |
|---|---|---:|---:|---:|
| **S4** | nodo host | 42,766 | +0,607 | **75,9** |
| **S3** | **sul dispositivo** | **42,494** | **+0,335** | **41,9** |

**−34,0 µs per strato attivo**, cioè lo stesso ordine dei 46,0 misurati a `cpu_max = 0`: il valore
dell'intervento non dipende dal fatto che il pool calcoli o no, come deve essere.

Questo numero merita una riga a sé, perché **cambia un pezzo del bilancio di P4-estensione §9**:
quel documento stimava il costo per strato attivo in ~156 µs (impianto 59,1 + aritmetica ~97) contro
un risparmio di banda di 209 µs sullo strato più ricco, e ne concludeva un margine stretto di 1,34×.
Qui lo stesso costo, misurato invece che sommato, è **41,9 µs**. Non è una riapertura di D18 — il
confronto sta su due profili diversi e il risparmio di banda resta quello che era — ma è
l'apertura A1 di §8.

*Avvertenza sul confronto.* S3 e S4 generano un testo diverso da S0 (1.351 token invece di 1.396):
il Δ su S0 mescola due testi, esattamente come faceva la coppia EV8/E0 di P4-estensione. Il
confronto **S3 contro S4** è invece omogeneo (stesso testo, stesse impronte) ed è quello su cui si
appoggia il −34,0.

---

## 4. Stadio 2 — il progetto della corsia CPU sulle righe di bozza

Il cancello dello stadio 1 è passato, quindi lo stadio 2 è stato fatto.

### 4.1 Che cosa cambia nel pianificatore

Il pianificatore aveva già un meccanismo di miss-CPU (P3): sceglie i **primi `cpu_max` miss**
nell'ordine degli indici unici, li toglie dagli array di trasferimento e di commit, e dà loro uno
**slot alias**. La corsia di bozza non aggiunge un meccanismo, **cambia il criterio di scelta**:

> non più «i primi `cpu_max` miss», ma «**tutti i miss richiesti soltanto dalle righe di bozza**».

Un unico è «di sola bozza» quando nessuna delle sue route sta in una riga di ammissione, cioè quando
`route / top_k >= draft_from_row` per tutte le sue route. Con l'MTP a bozza 1 le righe sono due e
`draft_from_row = 1`: la riga 0 è il token già accettato, la riga 1 è la bozza.

Le due leve sono **indipendenti e si sommano**: `cpu_max` continua a decidere quanti miss della
riga di ammissione deviare — nelle prove di questa cella vale **zero**, così la riga 0 conserva la
politica attuale parola per parola — e la corsia di bozza aggiunge i suoi. La scelta continua a non
leggere **niente** dello stato della cache: dipende solo da *chi* ha chiesto l'esperto.

### 4.2 Gli invarianti della cella 3 §5.1, e come sono garantiti

| invariante | come è garantito |
|---|---|
| **1. Nessun residente fantasma** (commit differito su trasferimenti mai avvenuti) | i miss di bozza sono tolti da `miss_experts`/`miss_unique` **prima** del gather, quindi non entrano mai nel commit differito. Il commit resta differito e intatto: non è stato toccato un rigo di quel ramo |
| **2. Un solo piano per strato** | `group->plan` resta unico e la corsia non ne crea un secondo: è la stessa chiamata di pianificazione, con un criterio di selezione diverso |
| **3. Protezione dallo sfratto degli esperti di bozza RESIDENTI** | già garantita dal codice esistente e verificata rileggendolo: la bitmap `route_storage[slot] = 1` viene alzata per **ogni** unico che abbia uno slot, colpi compresi, prima che cominci la scelta delle vittime. Un esperto residente chiesto solo dalla bozza è un colpo, quindi è nella bitmap, quindi nessuno sfratto di questo piano può toccarlo |
| **4. `n_routes <= n_slots`** | invariato: 2 righe × 10 = 20 rotte contro 64 slot, e l'assert è quello di sempre |
| **5. Frequenza e LRU non aggiornate sulle righe di bozza** | richiede un flag che **sopravviva fino alla chiamata successiva**, perché recenza e frequenza si aggiornano nel commit differito. È il nuovo array `MOE_GROUPED_PLAN_UNIQUE_DRAFT`, scritto dal piano e letto dal commit del piano dopo. Copre anche i **colpi** di sola bozza, che un flag calcolato sui soli miss avrebbe mancato |
| **6. Attivo solo con righe ≥ 2** | `draft_from_row` vale 1 solo se `n_rows >= 2`; con una riga sola vale 0 e il piano è identico a prima, riga per riga |
| **7. Spenta di default** | `LLAMA_MOE_CPU_DRAFT_ROWS=0`, e la corsia si spegne anche se manca il kernel di export o il nodo `add` |

Una conseguenza di forma, non di politica: il tetto di route CPU per riga passa da **4 a 10**
(`MOE_CPU_MAX_PER_ROW`), cioè a `top_k`. Nella corsia di bozza il tetto non è una scelta — è la
forma del descrittore del job — e la simulazione della cella 3 conta fino a 10 esperti di sola bozza
per strato (p90 = 5). Un tetto a 4 avrebbe rimesso sul PCIe proprio la coda che la leva vuole
togliere.

### 4.3 Il perimetro delle righe

Con la corsia accesa il perimetro dell'esecutore passa da **una a due righe**
(`caps.max_rows = 2`), che è la forma del batch di verifica dell'MTP a bozza 1. È la prima volta che
la decisione D06 («MTP spento nella prima integrazione») viene allentata, e lo è **solo** quando la
corsia è accesa.

---

## 5. Stadio 2 — le prove

### 5.1 Prova 1 — neutralità dei binari

`preset_S6_p7.json`: M1 (MTP bozza 1) sui binari della copia di lavoro, ibrido **spento** e corsia
**spenta**. Profilo `fumo`.

| | M1 (binari `qwen38_clean`) | S6 (binari `p3_work`) |
|---|---|---|
| impronta `L01@corto` | `c35b20a2290b9c1b` | **`c35b20a2290b9c1b`** |
| t/s (profilo diverso, non confrontabile) | 28,665 su `solo_libero` | 30,07 su `fumo` |
| accettazione | — | 0,770 (`L01`) / 0,897 (`S01`), lunghezza media **1,80** |

**L'impronta coincide**: i binari patchati con l'ibrido spento producono lo stesso testo di quelli
di M1. `S01@corto` non ha un termine di paragone in M1, che girava sul profilo `solo_libero`.
Il t/s non è confrontabile perché i profili sono diversi (`fumo` = 2 casi corti, `solo_libero` =
16 casi); il confronto omogeneo con 28,66 avrebbe richiesto un blocco `solo_libero` da 16 minuti,
e §6 spiega perché non è stato fatto.

*Nota sulla prima corsa di S7.* Il primo tentativo con la corsia «accesa» ha dato impronte e t/s
**identici a S6** (`c35b20a2` / `f9382a09`, 29,91 contro 30,07). Non era una prova di neutralità:
era una corsa **vuota**, in cui la corsia non era mai partita per il gate dimenticato del difetto 1.
Vale la pena tenerla nel documento, perché è il caso in cui «tutto sembra a posto» è la firma di
una leva che non c'è.

### 5.2 Prova 2 — la corsia accesa: i contatori

`preset_S9_p7.json`, profilo `fumo`, `LLAMA_MOE_CPU_REPORT=64`. **Corsa di verifica, non una misura
di tempo** (i contatori forzano un `cudaDeviceSynchronize`). Contatori reali del dispositivo,
aggregati sui 47 strati, all'ultima stampa completa:

| grandezza | valore |
|---|---:|
| richieste uniche | 436.716 |
| colpi GPU | 290.676 |
| miss **GPU** (trasferiti) | 76.277 |
| miss **CPU** (non trasferiti, calcolati dal pool) | **69.763** |
| invariante 1 (`uniche = colpi + missGPU + missCPU`) | **OK** a ogni stampa |
| coppie token/esperto | 534.080 |
| route servite dalla CPU | 69.763 |
| byte trasferiti | 150.357.222.400 |
| **byte risparmiati** | **137.516.825.600 — 47,77%** |
| valori **non finiti** in `y` | **0** |
| catture di graph | 7 su 2.560 lanci |

*(riga `moe cpu TOTALE` delle 10.30.406.914 in `log/c4_p7c4_s9_..._moecpu.txt`, l'ultima con tutti e
47 gli strati legati. Le stampe successive dicono «strati 1» perché il banco ha attraversato un
`llama_moe_cache_set_device_active(false)` — la cache viene sciolta e i gruppi si rilegano uno per
uno alla passata dopo: non è un guasto, ma rende non aggregabili le stampe di quella finestra.)*

Letture:

1. **La corsia fa esattamente quello che doveva.** 534.080 coppie / 20 rotte per piano = 26.704
   piani; 69.763 esperti CPU su 26.704 piani = **2,61 esperti CPU per strato per piano**, cioè
   ~123 per ciclo su 47 strati. La cella 3 aveva previsto **2,39 per strato e 114,5 per ciclo**
   simulando la politica sulle rotte vere. **Lo scarto è del 9% e nella direzione attesa** (la
   simulazione sottostima i miss del 18%, §2.2c della cella 3).
2. **Il risparmio di byte è del 47,8%**, contro il −84,6% *della riga in più* previsto dalla
   simulazione. I due numeri non sono in contraddizione e vanno letti insieme: il 47,8% è sul
   traffico **totale** dei due token, mentre il −84,6% era sul **delta** della seconda riga. Se la
   riga in più portava 140,2 MiB su 271,0 di base, togliendone l'84,6% si toglie il 34% del totale;
   qui se ne toglie il 48%, cioè **di più**, perché la corsia prende anche gli esperti di sola bozza
   che la simulazione contava come condivisi.
3. **Zero valori non finiti, invariante 1 verificato a ogni stampa, nessuna corruzione della cache,
   nessuna ricattura di graph in più.** Il meccanismo è corretto.
4. **L'iso-testo, però, NON regge** — e il motivo non è un difetto di questa realizzazione ma un
   errore nel progetto della cella 3. Vedi §5.4: è il secondo risultato negativo della cella, e
   sarebbe stato un cancello di correttezza fallito anche se il tempo fosse andato bene.

### 5.3 Prova 3 — la corsia accesa: il tempo

`preset_S7_p7.json`, profilo `fumo`, contatori **spenti**, scadenza del giro a vuoto portata a
300 ms (§6.2). Confronto sul caso lungo `L01@corto` (1.024 token generati), che è la lettura che non
mescola casi:

| | S6 (corsia spenta) | S7 (corsia accesa) |
|---|---:|---:|
| t/s del server su `L01` | **30,40** | **2,31** |
| ms per token su `L01` | 32,9 | **433,6** |
| accettazione della bozza su `L01` | 0,770 (lunghezza media **1,77**) | **0,697** (lunghezza media **1,70**) |
| impronta `L01@corto` | `c35b20a2290b9c1b` | **`aacc1d0c9b2a614f`** |
| impronta `S01@corto` | `f9382a098058a1f2` | **`0c30b61c05fb2468`** |
| *(banco, tutti i casi)* t/s | *30,07* | *2,349* |
| *(banco, tutti i casi)* ms/token | *33,26* | *425,63* |

Il **fattore 13** fra le due colonne è lo stesso letto in tre modi indipendenti: il `print_timing`
del server sul caso lungo (30,40 → 2,31), l'aggregato del banco sui due casi (30,07 → 2,349) e la
corsa con i contatori accesi (2,32, §5.2). Nessuna delle tre è contaminata dalle altre.

### 5.4 Il cancello di correttezza della cella 3 non era raggiungibile

La cella 3 §5.1 scriveva: «*le impronte SHA256 devono restare identiche a quelle di M1 — la corsia
CPU calcola la stessa FFN, quindi il testo non deve cambiare: è il cancello di correttezza*».
**Quella frase è sbagliata, e lo è per una ragione che sta scritta nel progetto P2 §8.**

1. **Il contributo CPU non è, e non può essere, bit-identico a quello GPU.** «*CPU e CUDA
   quantizzano diversamente l'attivazione: il contributo CPU non sarà mai bit-identico al percorso
   interamente GPU*», con NRMSE misurata ~0,0084. La corsia calcola la **stessa** FFN, non gli
   **stessi bit**.
2. **La riga di bozza del batch di verifica non è una riga da buttare: produce un token accettato.**
   Con l'MTP a bozza 1 il batch è `[t_accettato, t_abbozzato]`; l'uscita della **riga 1** è il token
   *successivo*, quello che viene emesso quando la bozza è accettata — cioè nel 77% dei casi.
   Perturbare la riga 1 di 8 parti su mille perturba direttamente un token su due.

Le due cose insieme dicono che **il testo doveva cambiare**, e infatti cambia. Il ragionamento della
cella 3 aveva implicitamente trattato la riga di bozza come una riga di sola verifica, come lo è in
uno schema di speculazione classico dove la riga in più serve solo a controllare un token già
proposto da un'altra testa. Nell'MTP con bozza 1 non è così.

Conseguenza pratica, visibile nei numeri: **l'accettazione cala da 0,770 a 0,697** (lunghezza media
da 1,77 a 1,70).

**Questa cella avrebbe quindi fallito anche un cancello di solo tempo.** Una leva che cambia il
testo va giudicata con una verifica di qualità (P6), non con un'impronta, e il protocollo non la
consente in fase di screening (D15).

### 5.5 Una domanda aperta, e va lasciata aperta: il contributo CPU arriva a `moe_out`?

Il ragionamento di §5.4 dice *perché* il testo può cambiare. Non dice *che cosa* lo cambia, e c'è un
dato che non torna.

**S7** (corsia accesa, il pool calcola) e **S10** (corsia accesa, `NOCOMPUTE=1`, il pool **non
calcola niente** e `y` resta zero) producono **le stesse identiche impronte**: `aacc1d0c9b2a614f` e
`0c30b61c05fb2468`, su 1.397 token. Entrambe diverse da S6.

Se il testo cambiasse per la perturbazione del contributo CPU, le due corse dovrebbero differire fra
loro: in una il contributo c'è, nell'altra è zero. Non differiscono. Restano tre letture, e questa
cella **non ha i dati per sceglierne una**:

1. **Il contributo CPU non raggiunge `moe_out`.** Sarebbe un difetto di correttezza vero: la corsia
   toglierebbe esperti senza restituirli, e il 47,8% di byte risparmiati sarebbe comprato con una
   perdita numerica silenziosa. Contro questa lettura c'è il fatto che il nodo `add` viene
   costruito (`moe_cpu_ok` è vero, altrimenti non ci sarebbe nemmeno la guardia — e la guardia c'è,
   perché la sua scadenza è scattata in S9).
2. **Il testo cambia per la sola mascheratura**, e la differenza fra «esperto tolto» e «esperto
   tolto e rimesso con 8 parti su mille di errore» non basta a spostare nessun argmax in questi due
   casi. Possibile, ma su 1.397 token è una coincidenza generosa.
3. **Il testo cambia per il difetto 6** (il contesto della bozza eredita un nodo `add` che non gli
   appartiene), che è comune a S7 e S10 e domina le altre due.

**La misura che decide costa una corsa** ed è già preparata ma non eseguita:
`preset_S13_p7.json`, modalità **diagnostica**, dove la guardia confronta il contributo CPU con
quello che la GPU calcola per le **stesse** route e riporta NRMSE e massimo assoluto. Se la NRMSE è
~0,008 il pool calcola la cosa giusta e la lettura 1 cade; se è 1,0 il contributo non c'è.
È l'apertura A7, ed è la prima cosa da fare prima di riaprire qualunque discorso sulla corsia.

---

## 6. Stadio 2 — il cancello, e perché non passa

### 6.1 Il numero

Confronto omogeneo, **stesso caso, stesso testo, stessa lunghezza di accettazione**, preso dal
`print_timing` del server sul caso lungo `L01@corto` (1.024 token generati), che è il modo di
leggerlo che non mescola profili:

| | S6 (corsia spenta) | S7 (corsia accesa) |
|---|---:|---:|
| t/s del server su `L01` | **30,40** | **2,31** |
| ms per token | 32,9 | **433,6** |
| lunghezza media di accettazione | 1,77 | 1,70 |
| **ciclo** (ms/token × lunghezza) | **58,2** | **737** |

Il costo della riga di verifica, con il modello della cella 3 (`ciclo = T1 + R + H`, e `T1` e `H`
invariati perché la corsia non li tocca):

> `ΔR = Δciclo = 737 − 58 = **+679 ms**`, quindi `R ≈ 15,77 + 679 = **695 ms**`.

**Questo numero è vero e non è la risposta.** Un fattore 13 sul decode non è un costo aritmetico: è
la firma di qualcosa che si è rotto. La cella di diagnosi §6.3 lo dimostra in una riga, e §6.6 dà il
numero dopo la correzione. Il cancello di correttezza — impronte identiche a M1 — non passa comunque,
per una ragione che sta nel progetto della cella 3 e non in questa realizzazione (§5.4).

### 6.2 Il guasto, e la rete che ha tenuto

Con i contatori accesi (S9) la corsa è **fallita**, e vale la pena raccontarlo perché è la prima
volta che la scadenza dentro il kernel scatta sul serio:

```
moe cpu [contaminazione]: pubblicati 27964, conclusi 27964, falliti 28, non finiti 0,
                          scadenza sul dispositivo 27938, contaminato SI, irrecuperabile no
decode: esecutore CPU degli esperti CONTAMINATO: il passo fallisce
llama_decode: failed to decode, ret = -1
```

Che cosa è successo: con la corsia accesa un job dura **millisecondi**, e un job lungo ha superato
i 50 ms della scadenza di default. Il kernel ha fatto esattamente quello per cui è stato scritto —
ha scritto `gpu_timeout`, alzato il veleno, e **non è rimasto appeso**; l'host ha letto la cella a
fine decode, ha registrato l'esito `timeout` nella macchina a stati di P2 e ha fatto fallire il
passo invece di restituire un risultato dubbio. `pubblicati = conclusi`: il pool non ha perso
nessun job, e non c'è stato nessuno stallo.

**È la prova che la scadenza dentro il kernel serve e funziona**, ed è anche la risposta al rischio
per cui C9 era stata rimandata due volte («un `wait` a giro sul dispositivo non ha un modo pulito di
essere annullato dall'host»). Il modo pulito è non annullarlo: dargli una scadenza sua, e un canale
per dire all'host che è scaduta.

S7 è stato rieseguito con `LLAMA_MOE_CPU_POLL_US=300000` e non è più scaduto. E il t/s e' lo stesso
di S9 (**2,31 contro 2,32**): i contatori non c'entravano niente, il costo è tutto della corsia.

### 6.3 La causa NON è l'aritmetica CPU: è una fase sbagliata, e un `Sleep(1)` che dura 15,6 ms

La spiegazione ovvia — «gli esperti in più costano 679 ms di aritmetica CPU, cioè ~5,5 ms l'uno» —
sembrava chiusa. **La cella S10 la falsifica in un colpo solo.**

`preset_S10_p7.json` è S7 con `LLAMA_MOE_CPU_NOCOMPUTE=1`: il job viene pubblicato, preso in carico
e validato, ma il pool **non esegue una sola moltiplicazione**. È la cella C5 di P4-costo applicata
alla corsia di bozza, e serve proprio a separare il calcolo dal resto.

| cella | aritmetica CPU | t/s su `L01` |
|---|---|---:|
| S6 | — (corsia spenta) | 30,40 |
| **S7** | **sì** | **2,31** |
| **S10** | **NO** | **2,31** |

**Identici.** Il costo non è l'aritmetica: sarebbe rimasto lo stesso anche se il pool avesse
calcolato gratis. Quindi il costo è nella **consegna** del lavoro, e c'è un numero che lo identifica
senza ambiguità:

> `679 ms per ciclo ÷ 47 strati = **14,4 ms per strato**`,
> contro `47 × 15,625 ms = **734 ms**`, che è il **tick dello scheduler di Windows**.

L'accordo è troppo preciso per essere una coincidenza, e il meccanismo è nel codice, in due righe
scritte in due momenti diversi che nessuno aveva mai visto insieme:

1. **`llama-context.cpp:1493`** chiama `graph_compute(gf, ubatch.n_tokens > 1)`. Quel booleano si
   chiama `batched` e serve a scegliere il threadpool: per quello è giusto.
2. **`llama-context.cpp:2637`** riusa lo stesso booleano per decidere la **fase del pool degli
   esperti**: `if (batched) set_phase(prefill) else set_phase(decode)`.

Un batch di **verifica** della speculazione ha `n_tokens = 2`, quindi è `batched`, quindi il pool
viene messo in fase **prefill** — dove per disegno (D09: «il pool non deve rubare core al prefill»)
il coordinatore **smette di girare a vuoto** e si addormenta su
`block_until_changed(..., timeout 1 ms)`. Su Windows, senza `timeBeginPeriod`, un'attesa da 1 ms
dura un **tick**, cioè ~15,6 ms. Il coordinatore si sveglia, vede la pubblicazione, conclude il job
in microsecondi — ma ha già bruciato un tick, e lo fa **47 volte per ciclo**.

Perché non si era mai visto: P3 e P4 hanno sempre girato con l'**MTP spento**, dove ogni decode ha
un token solo, `batched` è falso e la fase è `decode`. **Questa è la prima cella che accende insieme
l'ibrido e la speculazione**, ed è l'unica configurazione in cui il difetto si manifesta.

La correzione è di tre righe e sta in §6.5. Il criterio giusto non è il numero di token ma il
**perimetro dichiarato dall'esecutore**: se il batch ci sta dentro, il ramo CPU è sul cammino
critico e la fase è decode.

### 6.4 Che cosa NON è la causa

- **non è l'impianto a polling**: vale 13,8 µs per strato, cioè 0,65 ms per token su 47 strati —
  lo 0,1% dei 679 (§3);
- **non è l'aritmetica CPU**: S10, che non ne fa nessuna, misura lo stesso t/s di S7 (§6.3);
- **non sono i contatori**: S7 (spenti) e S9 (accesi) danno 2,31 e 2,32 t/s;
- **non sono i binari**: S6, sugli stessi binari con la corsia spenta, dà 30,40 t/s sullo stesso
  caso e la stessa impronta di M1 (§5.1);
- **non è il costo per esperto CPU della memoria del 10/9**: quel numero (0,074-0,08 ms) resta **non
  rimisurato**, ed era il difetto n. 5 che la cella 3 dichiarava di sé. Questa cella non lo conferma
  né lo smentisce — semplicemente, non è lui a decidere il verdetto. Resta l'apertura A4.

### 6.5 La correzione, e che cosa resta da misurare

La patch di questa cella include la correzione (`src/llama-context.{h,cpp}`, ottavo e nono file):
`graph_compute` riceve anche `ubatch.n_tokens`, e la fase del pool diventa

```c
const bool moe_cpu_in_perimetro = moe_cpu_rows > 0 && (int) ubatch_n_tokens <= moe_cpu_rows;
if (batched && !moe_cpu_in_perimetro) set_phase(prefill); else set_phase(decode);
```

Il threadpool continua a seguire `batched`: la correzione non tocca il prefill vero, dove
`n_tokens = 2048` è fuori da qualunque perimetro dichiarabile.

### 6.6 Il numero vero, e il cancello

`preset_S11_p7.json` è S7 sul binario corretto — stessa configurazione, stessa corsia, stessi
47 strati.

Riferimento e candidato girano **sullo stesso binario** (S12 è S6 rifatto dopo la correzione, e dà
30,238 contro 30,070: la correzione non tocca il lato spento, come deve):

| | **S12** (corsia spenta) | **S11** (corsia accesa) | *S7, fase sbagliata* |
|---|---:|---:|---:|
| t/s su `L01` (1.024 token) | **30,238** | **27,243** | *2,306* |
| ms per token | 33,07 | **36,71** | *433,6* |
| lunghezza media di accettazione | **1,77** | **1,70** | 1,70 |
| **ciclo** (ms/token × lunghezza) | **58,5** | **62,4** | 737 |
| t/s, tutti i casi | 29,911 | 27,101 | 2,349 |
| impronta `L01@corto` | `c35b20a2290b9c1b` | `aacc1d0c9b2a614f` | `aacc1d0c9b2a614f` |
| impronta `S01@corto` | `f9382a098058a1f2` | `0c30b61c05fb2468` | `0c30b61c05fb2468` |

**La correzione di tre righe vale un fattore 11,8**: 2,306 → 27,243 t/s, e il decode torna dal regime
patologico a uno confrontabile con il riferimento. Le impronte e l'accettazione sono **identiche**
fra S7 e S11 (`0,69652`, 420 accettati su 603): la fase cambiava solo il tempo, non l'aritmetica —
che è la conferma che la diagnosi di §6.3 ha colpito il bersaglio giusto.

Il costo della riga di verifica, rifatto sul numero buono:

> `ΔR = Δciclo = 62,4 − 58,5 = **+3,9 ms**`, quindi `R ≈ 15,77 + 3,9 = **19,7 ms**`.

> **Cancello dello stadio 2: `R < 13 ms`. Misura: ~19,7 ms. NON PASSA — ma di un fattore 1,5, non
> di 53.** La corsia doveva togliere 5,5 ms alla riga e invece ne aggiunge 3,9: il segno è ancora
> sbagliato, l'ordine di grandezza no.

Sul t/s, il confronto diretto sullo stesso caso e sullo stesso binario: **27,243 contro 30,238 =
−9,9%** (−9,4% sull'aggregato dei due casi), contro il **+5% su 28,66** che sarebbe servito per
l'adozione. E la perdita ha **due** componenti, entrambe della
leva e nessuna dell'impianto:

| componente | quanto | perché |
|---|---:|---|
| costo della corsia sul ciclo | **+3,9 ms** (+6,7%) | l'aritmetica CPU di ~123 esperti per ciclo, meno il risparmio di ~5,5 ms di PCIe: il saldo è positivo, cioè in perdita |
| calo dell'accettazione | 1,77 → **1,70** (−4,0%) | il testo cambia (§5.4-5.5), e con esso la lunghezza media accettata: meno token per ciclo |

Le prove 3 (blocco `solo_libero` contro 28,66) e 4 (bozza 2) **non sono state eseguite**. La ragione
non è più «il candidato è a 2,31 t/s» ma il criterio del piano: il cancello è sul **costo della
riga**, non sui t/s, e `R = 19,7` contro `< 13` lo manca. La prova 4, poi, aveva senso solo se `R`
fosse sceso: la soglia di pareggio della seconda posizione è `(H + R)/ms-per-token` e con
`R = 19,7` **sale** a 0,69 invece di scendere a 0,50, cioè ben sopra lo 0,553 misurato in cella 1.
La bozza a 2 token resta fuori.

---

### 6.7 Perché la corsia non paga, adesso che il numero è giusto

Con `R = 19,7` invece di 15,8, il bilancio è:

| voce | ms per ciclo | da dove |
|---|---:|---|
| risparmio di trasporto | **−5,5** (atteso) | 47,8% dei byte in meno, alla banda misurata (cella 3 §5.1) |
| costo della corsia | **+9,4** (dedotto: 3,9 + 5,5) | aritmetica CPU di ~123 esperti per ciclo, più la serializzazione per strato |
| **saldo** | **+3,9** | misurato (§6.6) |

Da cui **il costo per esperto CPU, questa volta in un regime sano**:
`9,4 ms ÷ 123 esperti = **76 µs**`.

Ed è, con uno scarto del 5%, **esattamente il numero della memoria del 10/9** — «un esperto sulla
CPU costa 0,08 ms». Il parametro che la cella 3 aveva usato senza rimisurarlo **era giusto**; ciò
che era sbagliato era l'aspettativa costruita sopra, perché 123 esperti a 76 µs fanno **9,4 ms per
ciclo** contro **5,5 ms** di trasporto risparmiato. La disuguaglianza, riscritta con i numeri veri:

> la corsia paga quando **`n_cpu × costo_per_esperto < byte_risparmiati / banda_del_bus`**.
> Qui: `123 × 76 µs = 9,4 ms` contro `5,5 ms`. Manca un fattore **1,7** — o sul costo per esperto,
> o sul numero di esperti deviati.

Questo è un verdetto molto diverso da quello che la prima misura suggeriva, e molto più utile: la
leva non è assurda, è **in perdita di meno del doppio**. Le due strade per ribaltarla sono in §8
(A3 e A5), e nessuna delle due è stata misurata qui.

---

## 7. Difetti trovati

1. **Un gate dimenticato sul lato CUDA è costato una corsa intera.** La corsia di bozza tiene in
   piedi l'impianto a `cpu_max = 0` esattamente come `allow_zero`, e questo era scritto nel lato
   libllama ma **non** in `moe-demand.cuh`. Risultato: la funzione taceva, il testo restava identico
   (che è proprio l'esito atteso dalla leva, quindi non insospettiva) e l'unica traccia era un avviso
   che dava la colpa ai **tipi dei banchi**. Corretto in due modi: la condizione, e l'avviso, che ora
   dice quale delle quattro condizioni è mancata. *La regola generale: un avviso che nomina una sola
   causa possibile mente quando le cause sono quattro.*
2. **La prima forma del prologo di attesa faceva tre letture PCIe dove ne bastava una**, e questo da
   solo spostava l'impianto da 13,8 a 16,0 µs per strato, cioè da dentro a fuori il cancello. Il
   difetto non è la lettura in sé ma l'aver scritto il prologo come se leggere una parola mappata da
   un kernel costasse quanto leggerla da un registro: costa **~1,1 µs per strato**.
3. **`MOE_CPU_MAX_PER_ROW = 4` era un tetto di politica travestito da tetto di forma.** Con la
   corsia di bozza il numero di esperti CPU per riga non lo decide una manopola, lo decide il
   routing, e la simulazione ne conta fino a 10.
4. **LA FASE DEL POOL DECISA DAL NUMERO DI TOKEN — un fattore 12 sul decode.** È il difetto più
   costoso di questa cella e il più facile da non vedere: `graph_compute` riceve
   `batched = (ubatch.n_tokens > 1)` per scegliere il threadpool, e **riusa lo stesso booleano** per
   mettere il pool degli esperti in fase `prefill`. Un batch di **verifica** della speculazione ha
   due token, quindi finisce in `prefill`, dove il coordinatore smette di girare a vuoto e dorme su
   un'attesa da 1 ms — che su Windows dura un tick dello scheduler, ~15,6 ms. Su 47 strati sono
   **734 ms per ciclo**, cioè tutto il costo che la corsia sembrava avere. Invisibile a P3 e P4,
   che hanno sempre girato con l'MTP spento. **Corretto** (§6.5); la correzione vale 2,31 → 27,24
   t/s. *La lezione generale: un booleano usato per due decisioni diverse è giusto per una sola.*
5. **Il costo per esperto CPU della cella 3 era GIUSTO, e la prima misura di questa cella lo
   smentiva a torto.** Con la fase sbagliata il bilancio dava 5,5 ms per esperto e sembrava la
   conferma del difetto n. 5 della cella 3; con la fase corretta dà **76 µs**, cioè il valore della
   memoria del 10/9 a meno del 5%. Il difetto non era nel parametro ma nell'**aspettativa**
   costruita sopra: 123 esperti a 76 µs costano 9,4 ms per ciclo contro 5,5 ms di trasporto
   risparmiato, e nessuno aveva fatto quella moltiplicazione. *La lezione: un numero preso dalla
   memoria va rimisurato, ma prima ancora va **moltiplicato per quante volte lo si userà**.*
6. **Il contesto della BOZZA eredita un nodo `add` che non gli appartiene.** `llama-graph.cpp:2155`
   decide di costruire il nodo di somma da tre condizioni globali — funzione accesa, strato
   nell'elenco, `n_tokens <= max_rows` — e nessuna di queste distingue il modello bersaglio dal
   modello di bozza. Il contesto della bozza ha `n_moe_cache_slots = 0`, quindi i suoi esperti non
   sono legati alla cache a domanda e `remap` non parte: nessun piano, nessun export, nessun job. Ma
   il nodo `add` **c'è lo stesso**, e somma a `moe_out` della bozza il buffer `y` così come lo ha
   lasciato l'ultimo job del bersaglio. Il risultato è una perturbazione della testa MTP che non ha
   niente a che vedere con la leva in esame. **È un difetto che P3 e P4 non potevano vedere**, perché
   hanno sempre girato con l'MTP spento: questa è la prima cella che mette insieme l'ibrido e la
   speculazione. Non è stato corretto perché il verdetto non ne dipende (il divario è di un fattore
   50, non del qualche per cento che questo difetto può valere), ma **va corretto prima di
   qualunque altra cella che accenda l'ibrido con l'MTP**: la condizione giusta è «questo strato ha
   un gruppo legato alla cache a domanda», non «questo strato è nell'elenco».
7. **In diagnostica il flag di sola bozza non viene ignorato.** Con `LLAMA_MOE_CPU_DIAG=1` il piano
   resta identico a `cpu_max = 0` per costruzione, ma l'array `UNIQUE_DRAFT` viene scritto lo stesso
   e il commit differito continua a sopprimere frequenza e recenza. La diagnostica resta neutra
   sull'**uscita** — la cache è esatta, un colpo e un miss producono gli stessi numeri — ma non più
   sulla **politica**. Piccolo, dichiarato, non corretto.

---

## 8. Aperture, in ordine di valore

| # | apertura | perché adesso | prima misura |
|---|---|---|---|
| **A1** | **La politica della cache senza la corsia CPU.** Dell'intera leva, il pezzo che costa zero è l'invariante 5: *un esperto chiesto solo dalla bozza non aggiorna frequenza e recenza*. Il flag che lo realizza (`MOE_GROUPED_PLAN_UNIQUE_DRAFT`) è **già nel piano e già scritto**, e non ha niente a che vedere con la CPU: toglie dalla politica i token che hanno il 21,5% di probabilità di essere rifiutati, lasciando ogni byte dov'è. Costo atteso: nulla. Guadagno atteso: un tasso di colpi migliore per la riga che conta | una manopola che accenda `draft_from_row` **senza** la selezione CPU (tre righe), poi `preset_M1` contro sé stesso sui colpi reali |
| **A2** | **L'impianto a polling applicato a P4-estensione.** Il costo per strato **attivo** misurato qui è 41,9 µs (§3.4), contro i ~156 che il bilancio di P4-estensione §9 sommava. Quel bilancio dava un margine di 1,34× sullo strato più ricco e negativo in media; con 41,9 il margine cambia di segno su molti più strati. **Non è D18 riaperta** — il confronto sta su due profili — ma è il confronto che va rifatto per primo | `preset_EB8_p4` con `LLAMA_MOE_CPU_POLL=1` sul profilo `solo_libero`, contro il riferimento libero 24,44 t/s |
| **A3** | **Più thread nel pool, adesso che il regime è un altro.** La curva dei thread di P4 (che dava **2** come ottimo) è stata presa dove il pool calcolava per **un** strato: lì dominava la contesa, non l'aritmetica. Qui il pool fa ~123 esperti per ciclo su 47 strati, e a 76 µs l'uno l'aritmetica è **9,4 ms per ciclo**, cioè il termine dominante. Se scala con i thread, 4 thread porterebbero il saldo da +3,9 a circa −0,8, cioè **sotto zero**, che è la soglia in cui la leva comincia a pagare | `preset_S11_p7.json` con `LLAMA_MOE_CPU_THREADS` 4 e 6, profilo `fumo`, contro S12 |
| **A4** | **Il costo per esperto CPU, misurato da solo.** Questa cella lo deduce a **76 µs** da un bilancio (§6.7), e il valore conferma la memoria del 10/9 (0,074-0,08 ms) — ma resta un numero dedotto, non misurato. Serve a qualunque cella futura che voglia spostare lavoro sulla CPU, e serve a sapere quanto di quei 76 µs sia aritmetica e quanto serializzazione | il banco host-only di P2 (`test_esecutore.exe`) con un cronometro attorno a `reference_expert` |
| **A5** | **La corsia di bozza su POCHI strati.** Costo e risparmio scalano entrambi con gli strati, ma non con la stessa pendenza: gli strati con più miss di sola bozza restituiscono più byte a parità di esperti calcolati. Con la disuguaglianza in perdita di 1,8× un sottoinsieme scelto bene può bastare | `LLAMA_MOE_CPU_LAYERS` con gli strati a più alta frazione di miss di sola bozza, letti dai contatori per strato di S9 |
| **A6** | **Deduplicare il gather QSA fra le due righe** (cella 3 §5.2) e **il bias QSA in F16 o costruito sul dispositivo** (cella 3 §5.3). Restano dove la cella 3 le ha lasciate, e adesso sono le uniche due leve sulla riga di verifica che non passano dalla CPU | la misura da dieci minuti sull'intersezione dei top-2048, che la cella 3 chiedeva e che nessuno ha fatto |
| **A7** | **Il contributo CPU arriva davvero a `moe_out`?** (§5.5). S7 e S10 — con e senza aritmetica — danno lo stesso identico testo, e questo non torna. È la domanda che va risolta **prima** di qualunque altra sulla corsia: se la risposta è no, il 47,8% di byte risparmiati è comprato con una perdita numerica silenziosa | `preset_S13_p7.json`, già generato e mai eseguito: modalità diagnostica, NRMSE fra contributo CPU e contributo GPU sulle stesse route |

### 8.1 Che cosa NON riaprire

- **Il prefetch della riga di verifica durante la testa**: chiuso dalla cella 3 per due ragioni
  indipendenti, e niente di questa cella le tocca.
- **La bozza a 2 token** come conseguenza di questa leva: la soglia di pareggio della seconda
  posizione è `(H + R)/ms-per-token`, e con `R = 19,7` **sale** a 0,69 invece di scendere a 0,50.
  L'ordine giusto resta quello della cella 3 — prima la riga, poi la lunghezza — ma la riga non è
  scesa.

---

## 9. Bozza di voce di registro

**Data e fase.** 14 settembre 2026. **P7, cella 4 — l'impianto a polling (la variante C9) e la
corsia CPU sulle righe di bozza.** Due stadi con un cancello secco in mezzo: il primo passa, il
secondo no.

**Ipotesi.** *(stadio 1)* Sostituendo l'ultimo `cudaLaunchHostFunc` con un'attesa sul dispositivo —
un kernel che gira a vuoto su una parola mappata scritta dal pool — l'impianto per strato scende
sotto i 15 µs (oggi 59, 115 all'origine). **Verificata: 13,8 µs.**
*(stadio 2)* Non trasferendo e non ammettendo gli esperti non residenti richiesti soltanto dalle
righe di bozza del batch di verifica MTP, e calcolandoli sulla CPU, il costo della riga di verifica
scende sotto 13 ms (cella 3 §5.1: −84,6% dei byte, 114,5 esperti CPU per ciclo, aspettativa da
+2,2% a +9,7% su 28,66 t/s). **Falsificata: R sale a ~714 ms.**

**File toccati.** `D:\ds4_work\p3_work\source`, **sette file**: `ggml/include/moe_cpu_job.h`
(due celle nuove nei flag — `complete` e `gpu_timeout` — e `MOE_CPU_MAX_PER_ROW` da 4 a 10),
`ggml/src/ggml-cuda/moe-demand.cuh` (opzioni `POLL`/`POLL_US`/`DRAFT_ROWS`, prologo di attesa sul
dispositivo nella guardia del merge, nessun nodo host accodato, conversione microsecondi→cicli,
idoneità dello strato con la corsia di bozza, avviso con la causa),
`ggml/src/ggml-cuda/fork-moe-kernels.cuh` (array `UNIQUE_DRAFT`, selezione dei miss di sola bozza,
compattazione generale dei miss GPU, frequenza e recenza non aggiornate sugli unici di sola bozza),
`src/moe_cpu_executor.{h,cpp}` (scrittura della cella `complete`, lettura registrata di
`gpu_timeout`), `src/llama-moecpu.{h,cpp}` (le tre opzioni, perimetro a due righe con la corsia,
righe di log `[P7c4]`). `src/llama-graph.cpp` **non** è stato toccato.
Patch incrementale `docs/porto/p7_speculazione/p7_cella4.patch` (diff `-d` rispetto allo stato dopo
P4-estensione, 815 righe), **verificata applicandola davvero** a una copia dello stato di partenza:
i sette file risultanti coincidono byte per byte con l'albero di lavoro. *Si applica con
`patch -p1 --binary`*: senza `--binary` il `patch` di Git Bash rifiuta ogni hunk dei due `.cuh` con
«different line endings» pur non essendoci un solo CR né nella patch né nei sorgenti.
**Nessun commit.** `bin_prod`, `qwen38_clean\source`, lanciatore quotidiano, modelli e snapshot P0
invariati.

**Configurazioni confrontate.** Undici preset `preset_S<n>_p7.json` in `docs/porto/banco_p0/`,
generati da `genera_preset_p7c4.py` (stadio 1) e `genera_preset_p7c4_stadio2.py` (stadio 2). Ognuno
dichiara esplicitamente **tutte** le opzioni dell'ibrido, comprese le tre nuove. Quattro
compilazioni, tutte a codice 0.

**Run validi / invalidi.** Dieci corse valide, **una invalida** (S9, fermata dalla contaminazione
descritta sotto — resta valida come lettura dei contatori, non come misura di tempo) e **una vuota**
(il primo tentativo di S7, in cui la corsia non è mai partita per il gate dimenticato: difetto 1).
Nessun processo residuo, porta 8100 mai occupata da altri, guardia d'istanza unica superata prima di
ogni avvio. **RAM libera minima registrata in ogni corsa: mai sotto 7,6 GB** (soglia di invalidità
4 GB).

**Risultato e limite.** *Stadio 1, cancello superato.* L'ultimo nodo host sparisce: l'attesa del
contributo CPU diventa il **prologo della guardia del merge** — non un kernel in più, lo stesso
kernel che fa anche un'altra cosa — che gira a vuoto sulla cella `complete` scritta dal pool, con
scadenza in cicli di SM misurata da `clock64()` **dentro** il kernel. L'impianto per strato passa da
**59,8 a 13,8 µs** (cancello: ≤ 15), cioè da +2,81 a **+0,65 ms per token** su 47 strati; impronte
identiche al riferimento spento in tutte e quattro le celle a `cpu_max = 0`, due repliche per lato a
0,08-0,09% di distanza.
Il nodo host costava **46,0 µs per strato**, coerente con le due stime indipendenti di P4 (42,3 e
41,9). Sul costo per strato **attivo** (`cpu_max=2`, 8 strati) l'intervento vale **75,9 → 41,9 µs**,
con impronte identiche fra le due attese — cioè la sostituzione è iso-testo. Difetto trovato per
strada: il prologo nella sua prima forma faceva **tre** letture di memoria host mappata invece di
una e misurava 16,0 µs per strato, **sopra** il cancello; una lettura PCIe da un kernel costa
**~1,1 µs per strato**. *Stadio 2, cancello fallito — ma non dove sembrava.* La corsia funziona:
invariante 1 verificato a ogni stampa, **zero valori non finiti**, nessuna ricattura di graph in
più, **2,61 esperti CPU per strato per ciclo** contro i 2,39 previsti dalla simulazione della
cella 3, **47,8% dei byte degli esperti risparmiati**. La prima misura, però, dava un decode da
**433,6 ms per token** contro 32,9, cioè `R ≈ 695 ms`: un fattore 13 che sarebbe stato letto come
«l'aritmetica CPU costa 5,5 ms per esperto» e avrebbe confermato, a torto, il difetto n. 5 della
cella 3. **Una cella di diagnosi lo falsifica in un colpo**: con
`LLAMA_MOE_CPU_NOCOMPUTE=1` — corsia accesa, pool che **non calcola niente** — il t/s è lo
**stesso**. La causa vera è una **fase**: `graph_compute` riceve `batched = (n_tokens > 1)` per
scegliere il threadpool e riusa lo stesso booleano per mettere il pool degli esperti in `prefill`;
un batch di verifica della speculazione ha due token, quindi ci finisce, e lì il coordinatore dorme
su un'attesa da 1 ms che su Windows dura un tick dello scheduler, **15,6 ms × 47 strati = 734 ms per
ciclo** — esattamente il costo osservato. **Corretta in tre righe** (nona modifica della patch), la
stessa configurazione misura **27,24 t/s invece di 2,31**, con impronte e accettazione identiche:
la fase cambiava il tempo, non l'aritmetica. Il numero vero è quindi `R ≈ **19,7 ms**` contro un
cancello di 13, e **−9,9% sul t/s** (27,243 contro 30,238, stesso binario) contro il +5% che serviva. Il bilancio
onesto: la corsia risparmia ~5,5 ms di trasporto per ciclo e ne costa ~9,4 di aritmetica, cioè
**76 µs per esperto CPU** — che è, a meno del 5%, il valore della memoria del 10/9 che la cella 3
aveva usato. **Quel parametro era giusto: mancava la moltiplicazione per 123.** Manca un fattore
**1,7**, non 123. E il **secondo** cancello, quello di correttezza, non passa comunque: le impronte
non sono identiche a M1, e non potevano esserlo — il contributo CPU non è bit-identico per
costruzione (P2 §8) e con l'MTP a bozza 1 la riga di bozza produce un token accettato, non una
semplice verifica; l'accettazione scende da 0,770 a 0,697. Limiti: un solo profilo (`fumo`), una
sola replica per le celle dello stadio 2, il blocco `solo_libero` contro 28,66 non eseguito, la
curva dei thread **non** rifatta nel regime nuovo (A3), e una domanda di correttezza aperta e
dichiarata — S7 e S10, con e senza aritmetica CPU, danno lo **stesso testo**, il che non torna
(§5.5, apertura A7).

**Decisione.** **Adottare lo stadio 1 e la correzione della fase; NON adottare la corsia, e non
chiuderla.** Tre cose distinte:
1. **L'impianto a polling si adotta** (spento di default): è la variante C9 che P4-costo §5.2
   dichiarava «obbligatoria prima di qualunque estensione» e che P4-estensione §10 metteva come
   prima delle due condizioni per riaprire D18 («impianto sotto ~10 µs/strato senza nodi host»:
   13,8 non ci arriva, ma −77% sì).
2. **La correzione della fase si adotta senza riserve.** Non è una leva, è un difetto: vale un
   fattore 12 sul decode in qualunque configurazione che accenda l'ibrido con la speculazione, e
   non ha controindicazioni (il prefill vero resta fuori dal perimetro dichiarato).
3. **La corsia CPU sulle righe di bozza NON si adotta e NON si chiude.** Il cancello è mancato di
   un fattore 1,7, non di 123, e le due strade per ribaltarlo (più thread ora che il regime è
   cambiato, A3; un sottoinsieme di strati scelto sui contatori, A5) non sono state misurate. Prima
   di entrambe va risolta A7: S7 e S10 danno lo stesso testo con e senza aritmetica CPU, e finché
   quella domanda è aperta non si sa se il 47,8% di byte risparmiati sia comprato o regalato.

**Regressioni aperte.** Nessuna a funzione spenta: le tre opzioni nuove sono inerti ai default e le
impronte del testo restano identiche al riferimento in tutte le corse dove devono esserlo. **A
corsia accesa il testo cambia** (R10 di P2), e questa cella ha stabilito che *doveva* cambiare:
§5.4. Difetto vero e non corretto, trovato qui e invisibile a P3/P4 perché hanno sempre girato con
l'MTP spento: **il contesto della BOZZA eredita un nodo `add` che non gli appartiene** (difetto 6
di §7) — va corretto prima di qualunque altra cella che accenda l'ibrido con l'MTP. Rischio noto
dichiarato: nel modo polling `cancel()` non è esercitabile dal kernel e la scadenza marca il job
invece di strapparlo, come già nel modo fuso. Difetto di diagnostica noto e non corretto: con
`LLAMA_MOE_CPU_DIAG=1` il flag di sola bozza sopprime comunque frequenza e recenza, quindi la
diagnostica non è più identica a `cpu_max=0` *nella politica della cache* — resta identica
nell'**uscita**, perché la cache è esatta e un colpo e un miss producono gli stessi numeri.

**Stato dei processi avviati.** Nessun `llama-server` attivo, nessun LISTENING sulla 8100, nessuna
compilazione in corso al termine.

**Prossima azione.** Apertura **A7**, ed è una corsa sola: `preset_S13_p7.json`, già generato,
modalità diagnostica, che confronta il contributo CPU con quello che la GPU calcola per le stesse
route e ne riporta la NRMSE. Risponde alla domanda che tiene in sospeso tutto il resto — il
contributo arriva a `moe_out`? Subito dopo, **A3** (`LLAMA_MOE_CPU_THREADS` 4 e 6 nel regime nuovo,
dove l'aritmetica domina invece della contesa: se scala, il saldo passa da +3,9 a circa −0,8 e la
leva comincia a pagare) e **A1** (staccare l'invariante 5 dalla corsia: il flag «unico di sola
bozza» è già nel piano e già scritto, usarlo **solo** per non aggiornare frequenza e recenza costa
tre righe e zero millisecondi).

---

## 10. Artefatti

| dove | che cosa |
|---|---|
| `p7_cella4.patch` | patch incrementale, 9 file, diff `-d` rispetto allo stato dopo P4-estensione. Si applica con `patch -p1 --binary` |
| `genera_patch_c4.sh` | come è stata generata (lato sinistro: `D:\ds4_work\p7_cella4_base`) |
| `genera_preset_p7c4.py` | preset dello stadio 1 (S0-S5) |
| `genera_preset_p7c4_stadio2.py` | preset dello stadio 2 (S6-S10) |
| `raccogli_c4.py` | tabella delle celle: ms/token, t/s, impronte, **RAM libera minima** |
| `copia_log_c4.py` | estrae da ogni corsa le sole righe dell'ibrido CPU/GPU |
| `log/c4_tabella_celle.json` | la tabella, in forma leggibile da una macchina |
| `log/c4_*_riepilogo.{txt,json}` | riepiloghi delle corse |
| `log/c4_*_moecpu.txt` | righe dell'ibrido estratte dal log del server |
| `../banco_p0/preset_S*_p7.json` | tredici preset, con **tutte** le opzioni dell'ibrido dichiarate. Due sono generati e **mai eseguiti**, di proposito: `preset_S8_p7.json` (bozza 2, la prova 4, che avrebbe avuto senso solo con `R` sceso) e `preset_S13_p7.json` (diagnostica numerica, l'apertura A7) |
