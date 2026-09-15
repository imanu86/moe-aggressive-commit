# P7 · cella 6 — la curva dei thread sulla corsia CPU delle righe di bozza — 15 settembre 2026

Prova A3′ della [cella 5](P7_CELLA5_A7_15_SETTEMBRE.md): la sola apertura rimasta sulla corsia CPU
delle righe di bozza dell'MTP era «più thread nel pool ribalta il segno?». Questa cella la chiude
con la misura.

---

## 0. Verdetto in sei righe

1. **No, nessun numero di thread provato fa scendere il ciclo sotto la corsia spenta** (57,41 ms).
   Il minimo misurato, a **4 thread**, è **61,15 ms** — ancora **+3,74 ms** sopra T5. **La corsia sulle
   righe di bozza resta CHIUSA**, come l'aveva lasciata la cella 5.
2. **Ma non è piatta: 4 thread batte nettamente 2.** `R` scende da **22,20 ms** (T6, 2 thread) a
   **19,51 ms** (U4, 4 thread): **−12,1%**, e il divario dal cancello `R < 13` si restringe da 9,2 a
   6,5 ms (−29%). t/s sale da **28,086 a 29,319** (+4,4%).
3. **La curva NON è monotona e NON è quella ipotizzata dalla cella 5.** L'ipotesi A3′ («se
   l'aritmetica scalasse linearmente, 6 thread porterebbero il saldo sotto zero») è **falsificata**:
   6 thread è la configurazione **peggiore** delle quattro misurate (R = 23,94), peggio anche di 2. E
   3 thread (U3, aggiunta perché U4 migliorava) è **peggio di 2** (R = 23,17), nonostante stia fra 2 e
   4. Il minimo a 4 è un punto isolato, non l'inizio di una discesa.
4. **L'aritmetica CPU (route, byte, invarianti) è bit-per-bit identica a tutti i thread**: `missCPU`
   27024, byte risparmiati 46,61%, zero non finiti, zero falliti, impronte del testo identiche a T6 in
   tutte e sei le corse. Il numero di thread cambia **solo** quanto costa calcolare, non cosa si
   calcola — verificato, non assunto.
5. **Il costo per esperto CPU scende da ~69 µs (2 thread) a ~52 µs (4 thread) e risale a ~75-80 µs (3
   e 6 thread)** — sotto la cifra di riferimento di 72-76 µs stabilita da P4/cella5 solo a 4 thread.
   È la prima volta che aggiungere thread riduce davvero il costo per esperto invece di aumentarlo:
   la ragione più probabile è l'affinità `auto` (ultimi core fisici), che a 4 thread copre i core
   4-7 senza toccare quelli bassi dove P4 aveva misurato la contesa col thread che accoda alla GPU.
6. **Uso CPU cresce in modo monotono col numero di thread** (9,6%→17,6%→26,6%→28,2%→31,9% di
   utilizzo totale del sistema da T5 a U6) mentre il ciclo no: la spesa di CPU non compra tempo in
   proporzione, tranne nel punto isolato a 4.

---

## 1. Che cosa è stato toccato, e che cosa no

| | |
|---|---|
| Preset nuovi | `preset_U3_p7.json`, `preset_U3C_p7.json`, `preset_U4_p7.json`, `preset_U4C_p7.json`, `preset_U6_p7.json`, `preset_U6C_p7.json` in `docs/porto/banco_p0/` (JSON senza BOM) |
| Generatore | `genera_preset_p7c6.py` in `docs/porto/p7_speculazione/`: copia `preset_T6_p7.json` (misura di tempo) e `preset_T7_p7.json` (contatori) cambiando **solo** `LLAMA_MOE_CPU_THREADS` (e dichiarando `LLAMA_MOE_CPU_AFFINITY=auto`, già il default di T6/T7) |
| Codice | **nessuna riga toccata**, nessuna build. Binari `D:\ds4_work\p3_work\build\bin` invariati dalla cella 5: `llama.dll` 15/9 08:21 (2.684.416 byte), `ggml-cuda.dll` 15/9 07:58 (192.400.384 byte) — stessi hash, verificato prima di partire |
| Non toccati | `qwen38_clean\bin_prod`, `qwen38_clean\source`, il lanciatore quotidiano, i modelli |
| Commit | nessuno |
| Server | uno alla volta, guardia d'istanza unica superata prima di ognuno dei **6** avvii; nessun processo residuo al termine (verificato dopo ogni blocco e a fine cella) |
| RAM libera minima | **5,55 GB** (U3), sempre sopra la soglia R-RAM di 4 GB; più bassa dei 7,08 GB della cella 5 ma la macchina non era nello stesso momento della giornata — nessun'altra corsa era attiva (guardia verificata) |

Ogni cella ha **due** preset: uno di **misura** (`LLAMA_MOE_CPU_REPORT=0`, come T6) e uno di
**verifica dei contatori** (`LLAMA_MOE_CPU_REPORT=64`, come T7 — NON una misura di tempo, la
sincronizzazione del dispositivo la contamina). Sei corse totali, tutte valide, tutte con le
impronte del testo identiche a T6/T7 della cella 5.

### 1.1 Perché l'affinità non ha bisogno di una maschera esplicita

Il dispaccio chiedeva «i 4/6 core fisici più lontani dal core del server» e, in mancanza di una
maschera documentata, di dichiarare la scelta. Non è servita una maschera: `LLAMA_MOE_CPU_AFFINITY`
è già `auto` nel preset base (T6/T7), e la lettura del sorgente
(`D:\ds4_work\p3_work\source\src\moe_cpu_executor.cpp:462-489`, `build_affinity()`,
`affinity_mode == 1`) mostra che il modo `auto` prende gli **ultimi** `n` core fisici dell'elenco
(`physical[n_phys-1-i]` per `i` da 0 a `n-1`), cioè esattamente:

| thread | core fisici assegnati (auto) |
|---:|---|
| 2 (T6/T7, cella 5) | 7, 6 |
| 3 (U3) | 7, 6, 5 |
| 4 (U4) | 7, 6, 5, 4 |
| 6 (U6) | 7, 6, 5, 4, 3, 2 |

Coincide esattamente con «core 4-7» per U4 e «core 2-7» per U6 richiesti dal dispaccio: nessuna
maschera esplicita necessaria, il comportamento di `auto` **è** la manopola giusta a ogni N.

---

## 2. Le corse

Profilo `fumo`, budget screening. Guardia d'istanza unica verificata prima di ogni avvio; porta 8100
e nessun `llama-server` residuo dopo ogni blocco.

| corsa | cella | thread | contatori | esito | RAM min |
|---|---|---:|---|---|---:|
| `20260915_090853_P7-cella6_p7c6_u4_mtp1_corsia_accesa_corretta_4thread_r1` | **U4** | 4 | OFF (misura) | valida | 5,85 GB |
| `20260915_091514_P7-cella6_p7c6_u4_mtp1_corsia_accesa_corretta_4thread_contatori_r1` | U4C | 4 | ON (verifica) | valida | 5,85 GB |
| `20260915_092246_P7-cella6_p7c6_u6_mtp1_corsia_accesa_corretta_6thread_r1` | **U6** | 6 | OFF (misura) | valida | 5,81 GB |
| `20260915_092800_P7-cella6_p7c6_u6_mtp1_corsia_accesa_corretta_6thread_contatori_r1` | U6C | 6 | ON (verifica) | valida | 5,74 GB |
| `20260915_093305_P7-cella6_p7c6_u3_mtp1_corsia_accesa_corretta_3thread_r1` | **U3** | 3 | OFF (misura) | valida | 5,55 GB |
| `20260915_093814_P7-cella6_p7c6_u3_mtp1_corsia_accesa_corretta_3thread_contatori_r1` | U3C | 3 | ON (verifica) | valida | 5,68 GB |

Sei corse, sei valide, nessun guasto, nessun NaN. `U3` è stata eseguita **perché** `U4` migliorava
il ciclo rispetto a T6, come previsto dal dispaccio.

Log puliti in `docs/porto/p7_speculazione/log/`, prefisso `c6_` (riepilogo testo/json, righe del
log del server sull'ibrido CPU/GPU, `carico.jsonl` della sonda). Copiatore:
[`copia_log_c6.py`](copia_log_c6.py).

---

## 3. La tabella — ciclo, R, t/s, accettazione

Stesso metodo della cella 5: `ms/token` e `draft_n`/`draft_n_accepted` letti da `timings_server` sul
caso lungo `L01@corto` (1.024 token generati); `lunghezza media = (draft_n + draft_n_accepted) /
draft_n`; `ciclo = ms/token × lunghezza media`; `R = 15,77 + Δciclo` (testa della riga di verifica,
cella 3, riusata identica). Formula e numeri di T5/T6 ricalcolati qui **dai file grezzi**
(`results.jsonl`) e coincidono con la tabella della cella 5 alla terza cifra (57,413 contro 57,41;
63,839 contro 63,84).

| | **T5** spenta | **T6** 2 thread | **U3** 3 thread | **U4** 4 thread | **U6** 6 thread |
|---|---:|---:|---:|---:|---:|
| affinità | — | auto (7,6) | auto (7,6,5) | auto (7,6,5,4) | auto (7,6,5,4,3,2) |
| ms/token (`L01`) | 32,439 | 35,605 | 36,150 | **34,108** | 36,579 |
| lunghezza media accettazione | 1,7699 | 1,7930 | 1,7930 | 1,7930 | 1,7930 |
| **ciclo** (ms) | **57,413** | 63,839 | 64,816 | **61,154** | 65,586 |
| **Δciclo** vs T5 | — | +6,426 | +7,403 | **+3,741** | +8,173 |
| **R** (ms) | 15,77 | 22,196 | 23,173 | **19,511** | 23,943 |
| t/s (`L01`) | 30,827 | 28,086 | 27,663 | **29,319** | 27,338 |
| t/s (aggregato 2 casi) | 30,463 | 27,834 | 27,387 | **29,112** | 27,489 |
| accettazione | 0,76990 (445/578) | 0,79298 (452/570) | 0,79298 (452/570) | 0,79298 (452/570) | 0,79298 (452/570) |
| impronta `L01` | `c35b20a2...` | `e31f4ae1...` | `e31f4ae1...` | `e31f4ae1...` | `e31f4ae1...` |
| impronta `S01` | `f9382a09...` | `8335d70e...` | `8335d70e...` | `8335d70e...` | `8335d70e...` |
| uso CPU sistema (media decode) | 9,58% | 17,56% | 26,64% | 28,20% | 31,94% |
| uso CPU processo server (media decode, %core) | 120,3 | 248,1 | 289,4 | 317,0 | 372,3 |
| RAM libera minima | 7,15 GB *(c5)* | 7,25 GB *(c5)* | 5,55 GB | 5,85 GB | 5,74 GB |
| NaN / non finiti | 0 | 0 | 0 | 0 | 0 |

*L'accettazione, la lunghezza media e le impronte sono identiche in tutte e quattro le corse con la
corsia accesa: l'esito del testo non dipende dal numero di thread, solo dalla velocità con cui ci
si arriva — atteso, ma verificato qui invece di assunto.*

### 3.1 Il cancello

> **Il cancello della cella 5 era `R < 13 ms`. Nessuna delle quattro configurazioni lo passa.**
> Il minimo misurato è **U4, R = 19,51 ms**, il 50% sopra il cancello.

### 3.2 Il costo per esperto CPU, per thread

Usando la stessa decomposizione della cella 5 (§7 di quel documento): la *consegna* (impianto +
attesa esposta − risparmio di trasporto) non dipende dal numero di thread del pool — è lavoro sul
lato GPU/host, non sul lato CPU — quindi si assume costante al valore di cella 5,
`ciclo(T9) = 53,13 ms` (corsia accesa, `NOCOMPUTE=1`: il pool non esegue una sola moltiplicazione,
quindi il numero di thread è indifferente per costruzione). **Questa è un'assunzione, non una
misura**: T9 non è stato rieseguito a 3/4/6 thread in questa cella — se lo si vuole verificare,
è una corsa sola per ciascun N. L'aritmetica CPU per configurazione è allora
`ciclo(U_N) − ciclo(T9)`, e il costo per esperto si ottiene dividendo per **155** (il numero di
esperti CPU per ciclo stabilito da P4/cella5, che i contatori di U3C/U4C/U6C confermano invariato —
`missCPU` identico a T7 in tutte e tre).

| | T6 (2) | U3 (3) | U4 (4) | U6 (6) |
|---|---:|---:|---:|---:|
| aritmetica CPU (ms/ciclo) = ciclo − 53,13 | 10,71 | 11,69 | **8,02** | 12,46 |
| costo per esperto (µs) = aritmetica / 155 | 69,1 | 75,4 | **51,8** | 80,4 |

Il numero di riferimento indipendente (memoria del 10/9, cella 4, T8 di cella 5) è **72-76 µs**. Solo
**4 thread** scende sotto quella banda; 3 e 6 la superano, con 6 il peggiore delle quattro.

---

## 4. Perché non monotona — una lettura, non una misura

Non è stato strumentato il perché, solo misurato il fatto. Un'ipotesi con un fondamento (P4 §4.1,
P4-estensione §4): la contesa che P4 aveva trovato a 4 thread di default (+1,72 ms/token, curva
1→2→4→6 di 42,44/42,44/44,16/49,79 ms/token) usava l'affinità `first` (i **primi** core fisici, cioè
proprio quelli su cui P4-estensione ha poi mostrato che gira il thread che accoda alla GPU, per
quanto non appuntato). Qui l'affinità è `auto` in tutte le celle: a 4 thread il pool occupa i core
4-7 e **non tocca mai** i core bassi. Se la curva di P4 fosse dominata dalla stessa contesa vista lì,
ripeterla con `auto` a 4 e 6 thread dovrebbe dare un risultato diverso da quella — ed è quello che si
osserva: **U4 batte nettamente T6**, cosa che con affinità `first` P4 non aveva mai visto (lì il
salto 2→4 era sempre in perdita). Ma **U6 torna a peggiorare**, il che dice che a 6 thread interviene
un secondo meccanismo di costo — probabilmente la contesa con l'HyperThreading: a 6 thread pinnati
sui core fisici 2-7, ciascuno di quei core ha un **fratello SMT** che il sistema operativo può ancora
usare per altro lavoro (inclusi i 16 thread del threadpool `-t 16`, che non sono vincolati a nessuna
maschera), e più core fisici occupati significa più superficie per quella contesa. **Non è stato
misurato**: servirebbe una sonda per-core (affinità del thread che accoda alla GPU, come
P4-estensione §4, ripetuta a ogni N) per distinguere le due ipotesi. Non fatto qui: fuori perimetro
del dispaccio, e il verdetto (la corsia resta chiusa) non cambia comunque.

E il caso di **U3**, peggiore di T6 nonostante stia "in mezzo" fra 2 e 4: con affinità `auto` a 3
thread il pool occupa i core 5-7, cioè un sottoinsieme diverso da quello di U4 (4-7) e di T6 (6-7) —
non un sottoinsieme annidato. Non c'è ragione a priori per cui la curva debba essere monotona in un
sistema con topologia SMT e code del sistema operativo concentrate sui core bassi: il punto isolato a
4 potrebbe essere il primo N per cui i 4 core scelti evitano una particolare risorsa condivisa (una
coppia di core sullo stesso CCX/CCD, una cache L3 slice, o semplicemente il rumore di una singola
corsa senza repliche — §5).

---

## 5. Limiti

- **Una sola replica per configurazione.** Il profilo `fumo` a parità di configurazione è ripetibile
  allo 0,02-0,09% (P4-costo, tre celle ripetute) — ma quella cifra è stata misurata sulla scala
  amplificata diagnostica, a configurazione IDENTICA fra le repliche. Qui le quattro configurazioni
  (T6/U3/U4/U6) sono **diverse fra loro** e sono state misurate **una volta ciascuna**: la
  non-monotonicità di §3-4 è un fatto solido (il salto U4 è 2,7-4,4 ms, un ordine di grandezza sopra
  il pavimento di rumore noto), ma non è stata falsificata l'ipotesi «rumore di giornata più alto del
  solito sulle repliche singole». Se si vuole capitalizzare il risultato di U4 (o proporlo come nuovo
  default), **una replica di conferma di U4 e T6 è il prossimo passo naturale**, non fatta qui per
  restare dentro il perimetro «solo le celle richieste».
- **Il costo di consegna (T9) non è stato rimisurato per N thread**: si assume costante (§3.2), con
  la giustificazione che `NOCOMPUTE=1` non fa girare aritmetica sul pool — ma non è stato verificato
  che il *risveglio* del pool (l'impianto, i due nodi host) non dipenda anch'esso dal numero di
  thread attivi nel pool stesso.
- **Il meccanismo di §4 è una lettura, non una misura**: nessuna sonda per-core è stata aggiunta in
  questa cella.
- **Profilo `fumo`, due casi.** Nessuna valutazione di qualità (D15, invariata da tutte le celle
  precedenti). Nessuna delle configurazioni ha superato il cancello `R < 13`, quindi — come in cella
  5 — il blocco `solo_libero` (16 casi) non è stato eseguito: il dispaccio lo subordina al
  superamento del cancello, e nessuna cella lo supera.

---

## 6. Bozza di voce di registro

**Data e fase.** 15 settembre 2026, mattina (09:05-09:42). P7 cella 6 — prova A3′ della cella 5: la
corsia CPU sulle righe di bozza dell'MTP, a 3/4/6 thread con affinità `auto`, contro il riferimento a
2 thread (T6) e a corsia spenta (T5).

**Ipotesi.** A3′ di cella 5: l'aritmetica CPU costa 11,17 ms/ciclo contro 4,29 ms di consegna
guadagnata (fattore 2,6 da recuperare). Se l'aritmetica scalasse linearmente coi thread, 6
thread porterebbero il saldo sotto zero (corsia in vantaggio), 4 thread lo porterebbero a +1,3 ms
(ancora in perdita ma quasi pareggiato). La curva dei thread di P4 (ottimo a 2) era stata presa a un
solo strato, dove dominava la contesa — non l'aritmetica —, quindi potrebbe non valere qui.

**File toccati.** Nessun file di codice. Preset nuovi: `docs/porto/banco_p0/preset_U3_p7.json`,
`preset_U3C_p7.json`, `preset_U4_p7.json`, `preset_U4C_p7.json`, `preset_U6_p7.json`,
`preset_U6C_p7.json` (JSON senza BOM). Generatore:
`docs/porto/p7_speculazione/genera_preset_p7c6.py`. Copiatore log:
`docs/porto/p7_speculazione/copia_log_c6.py`. Documento:
`docs/porto/p7_speculazione/P7_CELLA6_THREAD_15_SETTEMBRE.md`. Log puliti:
`docs/porto/p7_speculazione/log/c6_*` (18 file: riepilogo txt/json, righe moe-cpu, `carico.jsonl`
per ognuna delle 6 corse).

**Configurazioni.** Profilo `fumo`, budget screening, MTP bozza 1, contesto 262144, 64 slot esperti,
47 strati nell'ibrido, `cpu_max = 0`, `LLAMA_MOE_CPU_AFFINITY=auto`, `LLAMA_MOE_CPU_THREADS` in
{3, 4, 6}, tutto il resto identico a T6/T7 della cella 5. Binari `D:\ds4_work\p3_work\build\bin`
invariati (`llama.dll` 15/9 08:21, `ggml-cuda.dll` 15/9 07:58 — stessi hash di cella 5, nessuna
build).

**Run validi.** Sei su sei: U3, U3C, U4, U4C, U6, U6C. Nessun avvio fallito, nessun guasto, nessun
NaN, nessun job fallito, nessuna contaminazione. Impronte del testo identiche a T6/T7 in tutte le sei
corse. RAM libera minima 5,55 GB (U3), sempre sopra la soglia R-RAM di 4 GB.

**Risultato e limite.** **Nessuna configurazione (2/3/4/6 thread) porta il ciclo sotto quello della
corsia spenta** (57,41 ms). Il minimo è a **4 thread**: ciclo 61,15 ms (+3,74 su T5), R = 19,51 ms
(contro il cancello R < 13), t/s 29,32 — il 12% meglio di T6 (2 thread, R = 22,20, t/s 28,09). La
curva non è monotona: 3 thread (R = 23,17) e 6 thread (R = 23,94) sono **entrambi peggio** di 2
thread, falsificando l'ipotesi lineare di cella 5 («6 thread porterebbe il saldo sotto zero»). Il
costo per esperto CPU scende a ~52 µs solo a 4 thread (contro 69-80 µs alle altre configurazioni).
L'aritmetica (route CPU, byte risparmiati 46,61%, zero non finiti) è identica a tutti i thread:
verificato con i contatori (U3C/U4C/U6C), non assunto. Limite: una sola replica per configurazione,
nessuna sonda per-core sul meccanismo della non-monotonicità, costo di consegna (T9) assunto costante
sui thread e non rimisurato.

**Decisione.** **La corsia CPU sulle righe di bozza resta CHIUSA.** Nessun numero di thread provato
la fa passare sotto la corsia spenta, e il dispaccio chiedeva la chiusura definitiva se nessuna
configurazione batteva T5 — è il caso. Il miglioramento di U4 rispetto a T6 (−12% su R) è reale e
verificato, ma non basta a invertire il segno: resta una perdita di 3,74 ms/ciclo rispetto a non fare
nulla. Non si propone `LLAMA_MOE_CPU_THREADS=4` come nuovo default della corsia, perché la corsia
stessa resta spenta di default — il numero serve solo se in futuro si riapre la leva per altri motivi
(A5′, A10 della cella 5), nel qual caso 4 thread con affinità `auto` è il punto di partenza migliore
misurato finora, non 2.

**Regressioni.** Nessuna. Tutte le corse con corsia accesa hanno impronte identiche a T6; nessun file
di codice toccato; `qwen38_clean\bin_prod`, `qwen38_clean\source`, il lanciatore quotidiano e i
modelli non sono stati toccati.

**Stato processi.** Nessun `llama-server` attivo, porta 8100 libera, nessun processo residuo
(verificato dopo ogni blocco e a chiusura cella).

**Prossima azione.** La corsia CPU sulle righe di bozza è **chiusa definitivamente** per questo
progetto (P7). Le aperture rimaste della cella 5 che non riguardano il numero di thread — **A1** (la
politica della cache senza la corsia CPU, costo zero), **A5′** (la corsia su pochi strati, se mai
riaperta), **A6a/A6b** (bias QSA per riga, dedup del gather QSA) — restano le prossime candidate. Se
si volesse capitalizzare il risultato di U4 prima di chiudere il capitolo, il passo naturale è una
replica di conferma (U4 r2, T6 r2) per escludere che il salto sia rumore di giornata.

---

## 7. Artefatti

- Preset: [`../banco_p0/preset_U3_p7.json`](../banco_p0/preset_U3_p7.json),
  [`preset_U3C_p7.json`](../banco_p0/preset_U3C_p7.json),
  [`preset_U4_p7.json`](../banco_p0/preset_U4_p7.json),
  [`preset_U4C_p7.json`](../banco_p0/preset_U4C_p7.json),
  [`preset_U6_p7.json`](../banco_p0/preset_U6_p7.json),
  [`preset_U6C_p7.json`](../banco_p0/preset_U6C_p7.json). Generatore:
  [`genera_preset_p7c6.py`](genera_preset_p7c6.py).
- Log puliti: [`log/`](log/), prefisso `c6_`. Copiatore: [`copia_log_c6.py`](copia_log_c6.py).
- Corse complete: `D:\ds4_work\banco_p0_run\20260915_09*_P7-cella6_*` (sei cartelle).
