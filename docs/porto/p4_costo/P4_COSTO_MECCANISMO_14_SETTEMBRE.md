# P4, prima cella — Dove vanno i +1,801 ms per token

Versione 1.0, 14 settembre 2026. Fase **P4** del [piano CPU/GPU](../PIANO_CPU_GPU_14_SETTEMBRE.md).
Parte da [P3](../p3_uno_strato/P3_UNO_STRATO_14_SETTEMBRE.md) §9, apertura A1, e dal
[progetto P2](../p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md) §9 e §15 (R1, R2, R3, R7, R14).
Misure e criteri: [protocollo](../PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md). Decisioni: [registro](../REGISTRO_CPU_GPU_14_SETTEMBRE.md).

Questa fase **non estende** il ramo CPU ai 47 strati: lo scompone. Il piano lo dice
esplicitamente — «se il guadagno scompare, localizzare il costo prima di estendere il
sistema». Patch incrementale: [`p4_costo.patch`](p4_costo.patch), 6 file, diff rispetto
allo stato patchato di P3. Log in [`log/`](log/), preset in
[`../banco_p0/preset_C*_p4.json`](../banco_p0/).

---

**In una riga:** i +1,801 ms per token del meccanismo **non sono il meccanismo**: 0,21 ms
sono l'impianto, ~0,10 l'aritmetica CPU, e **~1,72 sono contesa fra il pool a quattro
thread e il threadpool del server** — con **due** thread lo stesso identico meccanismo,
sullo stesso strato, costa **+0,309** invece di **+2,028**, cioe' 6,6 volte meno; e
dell'impianto che resta, **l'80% sono i due `cudaLaunchHostFunc`**.

---

## 1. Che cosa e' stato toccato, e che cosa no

| | |
|---|---|
| Copia di lavoro | `D:\ds4_work\p3_work\source` (gia' patchata da P3), **6 file** modificati |
| Build | `D:\ds4_work\p3_work\build`, **una sola** compilazione per tutte le celle (codice 0). Hash in [`log/hash_binari.txt`](log/hash_binari.txt) |
| **Non** toccati | `qwen38_clean\bin_prod`, `qwen38_clean\source` e la sua build, il lanciatore quotidiano, il modello, lo snapshot `D:\ds4_work\p0_snapshot_20260914` |
| Commit | nessuno |
| Server | uno alla volta, guardia d'istanza unica superata prima di ognuno dei **22** avvii; nessun processo residuo al termine |

Le quattro opzioni nuove sono **inerti al default**: con i valori di default il
comportamento e' quello di P3, riga per riga. Nessun preset di produzione le nomina.

| variabile | valori | default | che cosa fa |
|---|---|---|---|
| `LLAMA_MOE_CPU_ALLOW_ZERO` | 0/1 | **0** | consente `LLAMA_MOE_CPU_MAX=0` senza spegnere la funzione: l'impianto esiste, nessuna route viene deviata, `y` resta zero e **l'uscita del modello non cambia**. E' la riga di guardia che P3 aveva indicato come ostacolo alla misura A1 |
| `LLAMA_MOE_CPU_NODES` | maschera 0-31 | **31** | quali pezzi accodare: 1 export, 2 `submit`, 4 `wait`, 8 guardia, 16 `add` |
| `LLAMA_MOE_CPU_NOCOMPUTE` | 0/1 | **0** | il pool accetta il job e scrive subito un contributo zero, senza aritmetica |
| (dedotta) | | | se `submit` e `wait` non sono **entrambi** accesi, i due hook installati sono **inerti**: ritornano subito e non toccano nessuno stato |

### 1.1 Perche' gli hook inerti, e non un `submit` vero senza `wait`

Un `submit` vero accodato senza il `wait` abbinato lascerebbe `in_flight` alto per
sempre: ogni job successivo verrebbe rifiutato per rientranza, il pool resterebbe fermo
e la cella misurerebbe un sistema rotto invece di un sistema piu' piccolo. Con gli hook
inerti la cella misura esattamente cio' che deve: **il prezzo della consegna di una
callback al driver**, senza nulla dietro. Le stesse due regole — niente `wait` senza
`add`, niente `submit` senza export — sono applicate **da tutti e due i lati** (libllama
e backend CUDA), perche' il confine di P2 non porta configurazione.

## 2. Il pavimento di rumore, misurato e non assunto

Tre celle sono state ripetute. Non era una precauzione formale: se il rumore fosse stato
lo 0,5% ipotizzato (±0,21 ms), meta' delle differenze qui sotto sarebbe stata illeggibile.

| cella | r1 | r2 | scarto |
|---|---:|---:|---:|
| C0 (spento) | 42,135 | 42,126 | 0,009 ms — **0,02%** |
| C1 (impianto) | 42,324 | 42,361 | 0,037 ms — 0,09% |
| C20 (attiva, 2 thread) | 42,459 | 42,481 | 0,022 ms — 0,05% |

**Il profilo `fumo` e' ripetibile allo 0,02-0,09%, non allo 0,5%.** L'incertezza su una
differenza si prende a **±0,03 ms per token**. Tutte le differenze di questo documento,
tranne quella del solo nodo `add`, sono risolte con margine.

## 3. Le celle

Tutte con lo stesso modello, le stesse fixture congelate, gli stessi binari, lo stesso
preset a meno delle opzioni dell'ibrido, `LLAMA_MOE_CPU_REPORT=0` (i contatori fanno un
`cudaDeviceSynchronize` e non possono entrare in una misura di tempo).

### 3.1 Scala a uno strato — lo strato 1, lo stesso di P3

| cella | configurazione | ms/token | Δ su C0 | lettura |
|---|---|---:|---:|---|
| **C0** | ibrido spento | **42,131** | — | riferimento, due repliche |
| C3 | add + export + guardia + **un** nodo host (inerte, `wait`) | 42,247 | +0,117 | un solo nodo host |
| C2 | add + export + guardia + **un** nodo host (inerte, `submit`) | 42,280 | +0,149 | idem; differenza da C3 al limite della risoluzione |
| C5 | diagnostica, job accettato, **nessuna aritmetica**, 4 thread | 42,315 | +0,184 | impianto + risveglio del pool |
| **C1** | **impianto completo, `cpu_max=0`**, 4 thread | **42,343** | **+0,212** | la misura A1 di P3, due repliche |
| C22 | diagnostica, 2 thread, **un** esperto CPU | 42,425 | +0,295 | |
| C17 | diagnostica, 2 thread, due esperti CPU | 42,440 | +0,309 | |
| C21 | attiva, 2 thread, contatori accesi (**verifica**, non a tempo) | 42,455 | +0,324 | |
| **C20** | **attiva, `cpu_max=2`, 2 thread** | **42,470** | **+0,339** | il candidato corretto, due repliche |
| C18 | diagnostica, **1** thread, due esperti CPU | 42,680 | +0,549 | |
| **C4** | **diagnostica, 4 thread** (il lato D di P3) | **44,159** | **+2,028** | |
| C6 | attiva, 4 thread (**il candidato B di P3**) | 44,503 | +2,372 | |
| C16 | diagnostica, **6** thread | 49,790 | **+7,659** | |

### 3.2 Scala amplificata — lo stesso pezzo su 47 strati

Su un solo strato ogni pezzo dell'impianto vale decine di microsecondi: al limite della
risoluzione anche con un pavimento di rumore da 0,03 ms. Le celle C10-C15 accendono lo
stesso pezzo su **47 strati** con `cpu_max=0`: il segnale si moltiplica per 47 e il costo
per strato si legge dividendo. Con `cpu_max=0` nessuna route viene deviata, `y` resta
zero, **l'uscita del modello non cambia** — e infatti le impronte restano identiche a C0
in tutte e sei le celle, cioe' l'oracolo funziona anche alla scala amplificata.

| cella | pezzo aggiunto | ms/token | Δ su C0 | **per strato** |
|---|---|---:|---:|---:|
| C10 | nessuno (solo `src[4]` e il pool fermo) | 42,116 | −0,015 | ~0 |
| C11 | + nodo `add` | 42,254 | +0,124 | **2,9 µs** |
| C12 | + kernel di export | 42,496 | +0,365 | **5,1 µs** |
| C13 | + guardia del merge | 43,202 | +1,072 | **15,0 µs** |
| C14 | + **un** nodo host (callback che ritorna subito) | 45,170 | +3,040 | **41,9 µs** |
| C15 | + **secondo** nodo host e hook **veri** | 47,501 | +5,370 | **49,6 µs** |
| | **impianto completo** | | **+5,385** | **114,6 µs** |

Ripartizione dell'impianto: `add` **2,6%**, export **4,5%**, guardia **13,1%**,
**nodi host 79,9%**.

*Una cautela onesta.* L'impianto su **un** strato misura 0,212 ms (C1), mentre 47 strati
misurano 114,6 µs per strato: su un solo strato costa **quasi il doppio**. Le due misure
non sono in contraddizione — sono due regimi. L'ipotesi piu' semplice e' che il thread di
callback del driver, invocato **94 volte per token** invece di due, resti caldo e non
debba essere risvegliato da un sonno profondo a ogni strato. **E' un'ipotesi, non una
misura**: nessuna delle due scale e' stata strumentata dall'interno. Per la decisione
conta poco, perche' entrambe le letture portano alla stessa conclusione; conta per chi
volesse moltiplicare un numero per 47, e la moltiplicazione resta vietata.

## 4. La scomposizione dei +1,801

P3 aveva misurato il meccanismo come **D − A = +1,801 ms/token** sull'insieme libero. Qui
lo stesso meccanismo, sullo stesso strato, con gli stessi binari a meno della patch di
P4, misura **C4 − C0 = +2,028** sul profilo `fumo`. I due numeri sono lo stesso fatto su
due carichi diversi: la scomposizione che segue e' in proporzioni, e le proporzioni non
dipendono da quale dei due si usi.

| pezzo | ms/token | come si ottiene | quota |
|---|---:|---|---:|
| **impianto** — `add`, export, guardia, due nodi host, giro del pool | **+0,184** ± 0,03 | C5 − C0 | 9,1% |
| **aritmetica CPU a quattro thread** | **+1,844** ± 0,03 | C4 − C5 | 90,9% |
| — di cui aritmetica **vera** (misurata a due thread) | +0,097 | C17 − C1 | 4,8% |
| — di cui **contesa** col threadpool del server | **+1,719** | C4 − C17 | **84,8%** |
| **totale** | **+2,028** | C4 − C0 | 100% |

La scomposizione e' additiva perche' le due righe si prendono dalla stessa scala: C5 e C4
differiscono **solo** per l'aritmetica. La cella C1 misura lo stesso impianto per un'altra
via — `cpu_max = 0`, nessuna route da calcolare — e da' **+0,212**: le due letture
distano 0,028 ms, cioe' meno del pavimento di rumore (±0,03). **L'impianto costa
0,18-0,21 ms per token su un solo strato**, e le due misure indipendenti concordano.

E, dentro l'impianto (proporzioni della scala amplificata applicate ai 0,212):

| pezzo dell'impianto | ms/token a uno strato |
|---|---:|
| due nodi host `cudaLaunchHostFunc` | **~0,169** |
| guardia del merge | ~0,028 |
| kernel di export | ~0,010 |
| nodo `add` | ~0,005 |

### 4.1 Il difetto: il numero di thread del pool

La curva dei thread, misurata **in diagnostica** perche' li' il carico e il testo non
cambiano da cella a cella:

| thread | ms/token | Δ su C0 |
|---:|---:|---:|
| 1 | 42,680 | +0,549 |
| **2** | **42,440** | **+0,309** |
| 4 (**il default**, e la configurazione di tutto P3) | 44,159 | +2,028 |
| 6 | 49,790 | **+7,659** |

Da uno a due il costo scende, come deve: l'aritmetica si divide. Da due a quattro **sale
di 6,6 volte**, da quattro a sei di altre **3,8**. Non e' una curva di calcolo: e' una
curva di **contesa**.

Il meccanismo e' identificato e non e' misterioso. La macchina ha **otto core fisici e
sedici logici** (Ryzen 7 5800X); il server gira con `-t 16`, quindi il threadpool di ggml
occupa **tutti** i core fisici. Il pool degli esperti si appunta un thread per core
fisico, partendo dal primo (`physical_first_masks`, `moe_cpu_executor.cpp:164`): con
quattro thread occupa i core 0-3, fra cui quello su cui gira anche il thread che
**accoda il lavoro alla GPU**. Ogni volta che il pool calcola davvero, quel thread viene
prelazionato, la GPU resta senza lavoro accodato, e il costo che si paga non e'
l'aritmetica ma la **bolla nello stream**. Con sei thread il fenomeno si estende a sei
core su otto e il decode perde il 18%.

Questa e' la ragione per cui la curva sale invece di scendere, ed e' esattamente il
rischio **R7** del progetto P2 («contesa fra i thread del pool e il threadpool del
server»), che P3 aveva lasciato non toccato e che D03 aveva anticipato nella direzione
sbagliata: «4 o 6 da confrontare in P4». Il confronto dice **2**.

### 4.2 La concorrenza c'e' — il rischio R2 non si e' materializzato

Il costo marginale del **secondo** esperto CPU, a due thread, e' **+0,015 ms**
(C17 − C22): un esperto in piu' raddoppia il lavoro del pool e non si vede. L'aritmetica,
quando il pool non e' sovradimensionato, e' **quasi tutta nascosta dietro il lavoro GPU
dello strato**: la disposizione dello stream del progetto P2 §9.2 — export, `submit`,
lavoro GPU, `wait` — funziona come progettata. Il `wait` **non** e' accodato troppo
presto.

Questo chiude **R2** in senso favorevole e ribalta la lettura che si sarebbe potuta dare
ai +1,8 di P3: non erano «la CPU e' troppo lenta», erano «il pool si prende i core del
processo che alimenta la GPU».

### 4.3 Il nodo `add` non rompe niente di caro — apertura A4 chiusa

Il nodo `add` costa **2,9 µs per strato** (C11 − C10). Se avesse rotto la fusione della
riduzione pesata (`ggml_cuda_match_moe_weighted_reduction`), il conto sarebbe un altro
ordine di grandezza. P3 aveva gia' provato che la **numerica** non cambia (impronte
identiche in diagnostica); qui si aggiunge che nemmeno il **costo** cambia. **A4 e'
chiusa**, e con essa l'ultimo residuo di R3.

### 4.4 La guardia del merge costa tre volte il kernel di export

**15,0 µs per strato** (C13 − C12) contro i 5,1 del kernel che copia l'attivazione e
scrive il descrittore del job. E' sproporzionato per un kernel a un blocco che, fuori
dalla diagnostica, legge **un flag** e non scrive niente. La spiegazione piu' probabile
e' che quel flag stia in **memoria host mappata**: `flags_dev` e' un puntatore dispositivo
dentro il blocco `cudaHostAlloc(MAPPED)` dell'esecutore, quindi leggerlo dal kernel e' una
**lettura PCIe**, non una lettura di VRAM, e 15 µs e' compatibile con un giro di PCIe piu'
il lancio. **Ipotesi con un fondamento, non una misura**: si falsifica in un pomeriggio
mettendo una copia del flag in VRAM, scritta dal kernel di export.

## 5. Verdetto

> **Il costo e' riducibile sotto il risparmio di banda, ma non con un solo intervento:
> ne servono due, e il primo e' gia' fatto e misurato.**

Il termine di paragone e' il risparmio di banda misurato da P3 sullo strato 1:
**0,209 ms per token** (B − D sull'insieme libero), meno sugli altri strati.

| stato | costo del meccanismo, uno strato | rapporto col risparmio |
|---|---:|---:|
| P3, quattro thread | +2,028 | **9,7 volte** |
| **oggi, due thread** (C17) | **+0,309** | **1,5 volte** |
| togliendo i due nodi host (stima da C13 e C15) | ~+0,14 | **0,7 volte** |

1. **Il numero di thread e' il primo intervento, e vale da solo un fattore 6,6.** Non e'
   una stima: la cella **C20** e' il candidato attivo di P3 con due thread invece di
   quattro, e misura **42,470** contro i **44,503** di C6 — la stessa configurazione,
   lo stesso testo generato (impronte identiche fra C6, C20 e la corsa attiva di P3),
   **2,03 ms per token recuperati**. Il default di `LLAMA_MOE_CPU_THREADS` va portato a
   **2**.
2. **I due nodi host sono il secondo intervento, e sono l'80% di cio' che resta.** Con
   due thread il meccanismo costa +0,309 contro un risparmio di 0,209: **manca ancora un
   decimo di millisecondo**, e i due `cudaLaunchHostFunc` ne valgono ~0,17. Toglierli
   porta il meccanismo **sotto** il risparmio. E' il pezzo che la cella C9 avrebbe dovuto
   provare.

**Il candidato non batte ancora il riferimento**: C20 sta a +0,339 ms per token da C0.
Ma il divario e' passato da **+2,372 a +0,339**, e per la prima volta e' dello stesso
ordine del risparmio invece che dieci volte piu' grande. La pista CPU **non va chiusa**.

### 5.1 Perche' C9 non e' stata implementata

Il criterio scritto nell'incarico e' esplicito: «implementa solo se C1-C3 mostrano che le
callback costano piu' di ~0,5 ms/token». **Non lo mostrano**: a uno strato i due nodi host
costano **~0,17 ms/token**, un terzo della soglia. La cella non e' stata fatta, e non
inventarla e' la risposta corretta al criterio.

**Ma il criterio va riletto prima di estendere.** A 47 strati i due nodi host costano
**4,30 ms per token** — il 10,2% del decode — e l'impianto completo 5,385, cioe' il 12,8%.
**Non e' l'aritmetica CPU a impedire l'estensione: e' l'impianto, e dentro l'impianto sono
i due nodi host.** Prima di accendere il ramo su piu' di una manciata di strati, C9 (o
qualunque altro modo di segnalare senza `cudaLaunchHostFunc`) diventa **obbligatoria**.
Il rischio da documentare quando si fara' — attesa a flag sul dispositivo dentro un CUDA
graph che viene **rigiocato** — e' che un `wait` a giro sul dispositivo non abbia un modo
pulito di essere annullato dall'host (progetto P2 §9.1, la ragione **non** prestazionale
per cui `cuStreamWaitValue64` era stata scartata). La via che resta aperta senza quel
rischio e' **ridurre il numero di nodi host** invece di cambiarne la natura: uno solo per
strato, oppure uno ogni N strati con un solo giro di `wait` a fine gruppo.

## 6. Verifica di correttezza

La cella **C21** ripete C20 con i contatori accesi. Non e' una misura di tempo
(`report_cpu()` fa un `cudaDeviceSynchronize`): serve a provare che il ramo CPU e' partito
davvero e che due thread non cambiano niente se non la velocita'.

| controllo | esito |
|---|---|
| contatori a fine corsa | uniche 3170 = colpi 1686 + missGPU 888 + missCPU 596; coppie 3170; routeCPU 596; uniciCPU 596; byte 1.750.425.600 — **identici cifra per cifra** alla corsa attiva di P3 |
| invariante 1 | **OK** a ogni stampa |
| valori non finiti in `y` | **0** |
| contaminazione, decode falliti | nessuno |
| cattura del graph | 11 catture e 4 riavvii di riscaldamento su 2496 lanci — **gli stessi numeri di P3 e del lato spento** |
| impronte del testo | identiche a C6 e alla corsa attiva di P3 |
| impronte nelle celle che non devono cambiare | **18 corse su 18**: C1 (due repliche), C2, C3, C4, C5, C10-C18, C22 e la seconda replica di C0 danno lo stesso testo di C0, e L01@corto piu' i due riscaldamenti coincidono anche col blocco di riferimento `20260914_072049` |

Nessuno stallo, nessun NaN, nessun errore di memoria, nessuna scadenza del `wait` o del
riconoscimento (R9, R15 non sollecitati), nessuna ricattura del graph in piu'.

## 7. Difetti trovati

1. **`LLAMA_MOE_CPU_THREADS=4` (il default, e la configurazione di tutto P3) e' quasi la
   peggiore scelta possibile.** Costa +1,72 ms per token rispetto a 2, su un solo strato.
   Il difetto e' di *configurazione*, non di codice, ma ha prodotto un verdetto sbagliato:
   P3 ha concluso «il meccanismo costa nove volte quello che il risparmio restituisce» e
   ha proposto di non estendere. La conclusione giusta era «il pool e' sovradimensionato».
   La correzione e' un numero. **Il default va cambiato a 2**, e D03 va rivisto.
2. **La guardia del merge costa tre volte il kernel di export** (15,0 contro 5,1 µs per
   strato) per leggere un flag che sta in memoria host mappata. Riducibile.
3. **L'avviso «ramo CPU non avviato» si accende anche quando tutto funziona.** Nel
   prefill `n_rows` vale 2 e `max_rows` vale 1, quindi la guardia scatta, l'avviso viene
   stampato una volta sola e dice «hook presenti, righe 2/1» — che e' vero e innocuo, ma
   chi legge il log di una corsa riuscita trova un avviso che sembra un guasto. L'avviso
   dovrebbe tacere quando la causa e' il numero di righe fuori dal perimetro dichiarato.
4. **`diff` senza `-d` rende un inserimento come «cancella 62 righe e riscrivile
   identiche».** La prima stesura di `p4_costo.patch` era illeggibile per questo. La
   patch e' stata verificata applicandola davvero a una copia dello stato P3 e
   confrontando i sei file byte per byte con l'albero di lavoro: identici.

**Difetti NON trovati**, e vanno elencati perche' erano i rischi attesi: nessuna
rottura di fusione attribuibile al nodo `add` (A4 chiusa), nessuna perdita di concorrenza
fra `submit` e `wait` (R2 chiuso in senso favorevole), nessuna instabilita' dei puntatori
di graph alla scala amplificata — 47 nodi `add` in piu' e 94 nodi host per token non
aggiungono **nessuna** ricattura.

## 8. Limiti

- **Un solo profilo.** Tutte le celle sono sul `fumo` (due casi, 1396 token). Il
  risparmio di banda (0,209) viene invece dall'insieme libero di P3, sedici casi: il
  confronto fra le due colonne del verdetto **mescola due carichi**. La verifica del
  candidato C20 sull'insieme libero, contro il lato A, e' la prossima misura e non e'
  stata fatta qui.
- **Un solo strato per le celle a scala reale**, 47 per quelle amplificate, e le due
  scale non danno lo stesso costo per strato (§3.2). Nessun numero di questo documento va
  moltiplicato per 47.
- **Un solo token per passo**, MTP spento, un solo contesto.
- **La scala amplificata gira a `cpu_max=0`**: misura l'impianto con job vuoti. Con job
  veri su 47 strati il `wait` blocca davvero, e quel regime non e' stato misurato.
- **La spiegazione della contesa (§4.1) e' un modello**, coerente con la curva e con il
  codice di affinita', ma non strumentata: non sono stati raccolti campioni di
  scheduling ne' contatori per core.
- **Nessuna verifica di qualita'** (non consentita in screening, D15), **nessuna misura
  di prefill**.

## 9. Aperture, in ordine di valore

| # | apertura | perche' adesso | prima misura |
|---|---|---|---|
| B1 | **Il candidato a due thread sull'insieme libero** | e' l'unico confronto omogeneo col risparmio di banda di P3, e chiude o riapre il verdetto | `preset_C20_p4.json`, profilo `solo_libero`, contro `preset_C0_p4.json` |
| B2 | **Ridurre i nodi host da due a uno** (o a uno ogni N strati) | sono l'80% dell'impianto e il 10% del decode a 47 strati; e' la leva che porta il costo sotto il risparmio senza toccare la natura della segnalazione | accodare il `wait` solo sull'ultimo strato di un gruppo e misurare a scala amplificata, dove il segnale e' ×47 |
| B3 | **Il flag della guardia in VRAM** | 15 µs per strato per una lettura PCIe; il kernel di export puo' scriverne una copia in VRAM a costo zero | C13 rifatta con il flag duplicato |
| B4 | **Curva dei thread sotto carico reale** | la curva 1/2/4/6 e' stata presa con `-t 16`; con `-t 12` o `-t 8` il punto ottimo puo' spostarsi, ed e' una manopola del lanciatore, non del codice | C17 con `-t 12` e `-t 8` |
| B5 | **`cpu_max` piu' grande** | il secondo esperto costa 0,015 ms: la finestra di concorrenza non e' satura, e il risparmio di banda cresce con `cpu_max` | C17 con `cpu_max` 3 e 4 (il tetto strutturale e' 4) |
| B6 | **Ordine dei miss CPU** (A5 di P3) e **scelta degli strati** | restano dove P3 li aveva lasciati; hanno senso solo dopo B1 e B2 | rifare le curve di P1 sulla traccia del banco congelato |
| B7 | **C9, la segnalazione senza callback** | oggi sotto la soglia dell'incarico, ma obbligatoria prima di qualunque estensione | solo dopo B2, e solo se B2 non basta |

Restano aperti e non sollecitati **R14** e **R15** del progetto P2, come in P3.

---

## 10. Bozza di voce per il registro

**Data e fase.** 14 settembre 2026. **P4, prima cella — localizzazione del costo del
meccanismo.** Scomposizione dei +1,801 ms per token misurati da P3, con 22 blocchi del
banco, una sola build e nessun commit.

**Ipotesi.** I +1,801 ms per token del meccanismo si scompongono in parti misurabili una
per una, e la parte dominante non e' quella che P3 aveva ipotizzato. Verificata: la parte
dominante non e' l'impianto (0,18-0,21 ms, 9%) ne' l'aritmetica CPU (+0,097 ms, 5%) ma la
**contesa fra il pool a quattro thread e il threadpool del server** (~1,72 ms, 85%).
Ipotesi secondarie: che i due nodi host dominino l'impianto — **verificata**, 80%; che il
nodo `add` rompa una fusione — **falsificata**, 2,9 µs per strato; che la concorrenza fra
`submit` e `wait` non ci sia (R2) — **falsificata**, il secondo esperto CPU costa 0,015 ms.

**ID della modifica/revisione.** P4-v1.0, patch incrementale
`docs/porto/p4_costo/p4_costo.patch` (236 righe aggiunte, 81 tolte, 6 file), diff rispetto
allo stato patchato di P3. Verificata applicandola a una copia dello stato P3: i sei file
risultanti coincidono byte per byte con l'albero di lavoro.

**File toccati.** libllama: `src/llama-moecpu.h`, `src/llama-moecpu.cpp` (tre opzioni
nuove, guardia di `cpu_max = 0` allentata, hook inerti, riga di misura nel log),
`src/llama-graph.cpp` (il nodo `add` si costruisce solo col bit 16 della maschera),
`src/moe_cpu_executor.h/.cpp` (`caps.nocompute`). Backend CUDA:
`ggml/src/ggml-cuda/moe-demand.cuh` (le stesse opzioni lette dall'altro lato, i quattro
pezzi accendibili uno per uno).

**Configurazioni confrontate.** Venti preset `preset_C<n>_p4.json` in
`docs/porto/banco_p0/`, generati da `docs/porto/p4_costo/genera_preset_p4.py`. Ognuno
dichiara **esplicitamente** tutte e undici le opzioni dell'ibrido, comprese le tre nuove.
Tutti con `LLAMA_MOE_CPU_REPORT=0` tranne C21, che e' una verifica e non una misura.

**Run validi.** Ventidue, tutti sul profilo `fumo`, budget screening, nessun guasto.
Elenco completo con corsa, token, ms/token e impronte in
[`log/tabella_celle.txt`](log/tabella_celle.txt); scomposizione in
[`log/scomposizione.txt`](log/scomposizione.txt). I quattro che decidono:

| corsa | cella | risultato |
|---|---|---|
| `20260914_105030` + `20260914_121240` | C0 | 42,131 ms/token, scarto fra repliche 0,02% |
| `20260914_105546` + `20260914_121733` | C1 | 42,343 — **l'impianto costa +0,212** |
| `20260914_110053` / `20260914_110550` | C4 / C5 | 44,159 / 42,315 — **l'aritmetica a 4 thread costa +1,844** |
| `20260914_120240` + `20260914_120746` | C20 | 42,470 — **il candidato a 2 thread recupera 2,03 ms su C6** |

**Run invalidi.** Nessuno.

**Risultato e limite.** Il meccanismo, sullo stesso strato e con lo stesso codice, costa
**+2,028** ms per token con quattro thread e **+0,309** con due: **il 85% dei
+1,801 di P3 era contesa di core, non meccanismo**. Di cio' che resta, l'impianto vale
0,212 ms per strato e i due `cudaLaunchHostFunc` ne sono l'**80%**; il nodo `add` 2,9 µs,
il kernel di export 5,1, la guardia 15,0 (scala amplificata su 47 strati). Il candidato
attivo passa da 44,503 a 42,470 ms per token, contro i 42,131 del riferimento: **non
batte ancora il riferimento, ma il divario e' passato da +2,372 a +0,339**, dello stesso
ordine del risparmio di banda (0,209) invece che dieci volte piu' grande. Limiti: un solo
profilo (`fumo`), un solo strato per le celle a scala reale, un solo token per passo, la
scala amplificata a job vuoti, la spiegazione della contesa non strumentata, nessuna
verifica di qualita', nessun prefill.

**Decisione.** **Proseguire, correggendo.** La pista CPU non si chiude: (1) portare il
default di `LLAMA_MOE_CPU_THREADS` da 4 a **2** e rivedere D03; (2) misurare il candidato
a due thread sull'insieme libero contro il lato A, che e' l'unico confronto omogeneo col
risparmio di banda; (3) solo dopo, ridurre il numero di nodi host. **Non** estendere agli
altri strati: a 47 strati il solo impianto costerebbe 5,385 ms per token, il 12,8% del
decode, e l'80% di quel costo sono i nodi host. La funzione resta **spenta di default**.

**Regressioni aperte.** Nessuna: le quattro opzioni nuove sono inerti ai default e le
impronte del testo restano identiche al riferimento in tutte e diciotto le corse dove
devono esserlo (le altre quattro sono in modalita' attiva). A funzione attiva il testo cambia come in P3 (rischio R10), con le stesse
impronte. R14 e R15 del progetto P2 restano aperti e non sollecitati.

**Stato dei processi avviati.** Nessun `llama-server` attivo, nessun LISTENING sulla 8100,
nessuna compilazione in corso al termine.

**Prossima azione.** Apertura B1: `preset_C20_p4.json` e `preset_C0_p4.json` sul profilo
`solo_libero`, una replica per lato, regola D14 (prima il candidato). E' il numero che
dice se due thread bastano a far pareggiare il risparmio di banda su un solo strato, o se
serve gia' il secondo intervento sui nodi host.
