# HANDOFF — 13 agosto 2026, sera

Tutto quello che serve per riprendere senza rifare gli errori di oggi. Leggere
nell'ordine: §1 per lanciare, §2 per le variabili, §3 per dove siamo, §4 per
cosa fare.

---

## 1. COME SI ACCENDE E SI SPEGNE IL SERVER

### 1.1 La regola che viene prima di tutte

**I processi vanno lanciati STACCATI dalla sessione.** Se la sessione muore, i
figli muoiono con lei — è già successo e ha ucciso una campagna a metà.

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = 'powershell -NoProfile -ExecutionPolicy Bypass -File "<script>"'
}
```

Mai `Start-Process` per i bracci, mai `&` in background da bash.

### 1.2 Un braccio singolo

```
docs/porto/dopo_il_riavvio.ps1  <tag> <slot> [zavorra MiB] [extra "A=1;B=2"]
```

Esempio:

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = 'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\dopo_il_riavvio.ps1" mio_tag 448 0 "LLAMA_CACHE_ESPERTI_PF_DEV=1;LLAMA_CACHE_ESPERTI_FORK=0"'
}
```

Il quarto parametro è applicato **DOPO** le variabili comuni, quindi le
sovrascrive. È il modo giusto di cambiare una leva sola.

### 1.3 Una campagna (più bracci in fila)

Un regista lancia **un processo staccato per braccio** e legge i risultati
**dal log del server**, non da un marcatore. Modello: `docs/porto/regista27.ps1`
(o qualunque `regista*.ps1`, sono tutti la stessa forma). Copiare la testa fino
a `Nota "====="` e sostituire solo i `Braccio`.

Il regista **cancella gli artefatti del tag prima di lanciare** — un log vecchio
di un altro giorno produce un risultato plausibile e falso. È già successo.

### 1.4 Il guardiano (poll staccato)

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = 'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\guardiano.ps1"'
}
```

Scrive `D:\ds4_work\llama_run\stato.txt` ogni 60 s: chi è vivo, VRAM, ultime
righe del regista, contatori del braccio in corso, tabella dei chiusi. Marca
`*** FERMO ***` se passano 20 minuti senza righe nuove. Esce quando trova
`===== FINITA` (il **banner**, non la parola: `Select-String` è
case-insensitive e `finita 15.5%` compare in ogni riga di braccio).

### 1.5 Lo spegnimento pulito

`Spegni()` in `dopo_il_riavvio.ps1:52`:

```
FreeConsole -> AttachConsole(pid) -> SetConsoleCtrlHandler(NULL,TRUE)
-> GenerateConsoleCtrlEvent(0,0) -> attesa 10 s -> WaitForExit(60 s)
-> riserva Stop-Process (e va REGISTRATA come anomalia)
```

Due cose che sono costate ore:

- **`GenerateConsoleCtrlEvent(0,0)` colpisce tutto il gruppo console**, mittente
  compreso. Per questo serve **un processo per braccio**: uno script che cicla
  i bracci si suicida.
- **Si salva PRIMA e si spegne DOPO.** Un braccio morto durante la pulizia
  perde i risultati che aveva già prodotto.

Se serve chiudere tutto a mano:

```powershell
Get-Process llama-server -EA SilentlyContinue | Stop-Process -Force
```

Dopo, aspettare che la VRAM torni sotto 1200 MiB (`nvidia-smi
--query-gpu=memory.used --format=csv,noheader,nounits`) prima del braccio dopo.

### 1.6 La compilazione

```powershell
$p = (Get-FileHash D:\llama-overlap\build\bin\ggml-cuda.dll -Algorithm SHA256).Hash.Substring(0,12)
$VCV='C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
$CM='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$out = & cmd /c "`"$VCV`" >nul 2>&1 && `"$CM`" --build D:\llama-overlap\build --target llama-server 2>&1"
$d = (Get-FileHash D:\llama-overlap\build\bin\ggml-cuda.dll -Algorithm SHA256).Hash.Substring(0,12)
"ggml-cuda.dll: $p -> $d  " + $(if ($p -ne $d) {'RICOSTRUITA'} else {'*** INVARIATA ***'})
```

**L'exit code NON è il cancello: lo è lo SHA del prodotto.** Una build può
"riuscire" senza aver ricostruito niente. E **la DLL è bloccata mentre un
server gira** — fermare i server prima, o il link fallisce con `LNK1104`.

### 1.7 Il binario e il banco

```
binario   D:\llama-overlap\build\bin\llama-server.exe
sorgenti  D:\llama-overlap\  (git, 10 commit oggi)
banco     D:\ds4_work\llama_run\
log       <tag>.server.log   <- TUTTI i numeri stanno qui
```

Riga di lancio completa (`dopo_il_riavvio.ps1:140`):

```
-m C:/ds4-models/DS4-0731-IQ2XXS.gguf
-md D:/ds4-models/DSpark-draft-Q2K.gguf  --spec-type draft-dspark
--fit off  -ngld 99  --spec-draft-n-max 1  --spec-draft-ubatch-size 16  -otd <OTD>
-c 10000  -ub 64  -np 1  -ngl 99
-ot 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'
-t 7  --no-mmap  -lv 4  --host 127.0.0.1  --port <PORTA>
```

---

## 2. TUTTE LE VARIABILI

> **La lezione del 12/8**: ho costruito l'ambiente **dal manifesto** invece che
> dalla lista di configurazione, e `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` **non è nel
> manifesto**. Un giorno perso a inseguire una regressione del 13-14% che era
> una variabile mancante. **Il manifesto non è la configurazione.**
>
> L'identità di due corse si verifica sul **log**, non sul manifesto:
> `grep -o "sfratto_par=[0-9]" <tag>.server.log`

### 2.1 Il blocco comune (`dopo_il_riavvio.ps1:97-127`) — copiare INTERO

```powershell
$env:LLAMA_CACHE_BOZZA_SLOT = '32'
$env:LLAMA_CACHE_ESPERTI_BATCH = '8';   $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
$env:LLAMA_CACHE_ESPERTI_CODA_MAX = '0'
$env:LLAMA_CACHE_ESPERTI_CURA = '0';    $env:LLAMA_CACHE_ESPERTI_SCUDO = '0'
$env:LLAMA_CACHE_ESPERTI_MASSA = '0';   $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
$env:LLAMA_CACHE_ESPERTI_LRU = '1';     $env:LLAMA_CACHE_ESPERTI_W = '0'
$env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'      # <-- LA VARIABILE DEL MANIFESTO MANCANTE
$env:LLAMA_CACHE_ESPERTI_SLOT = $SLOT           # 448 = ottimo attuale
$env:LLAMA_CACHE_ESPERTI_FORK = '2';    $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
$env:LLAMA_ACCEPTMOE = '0';             $env:LLAMA_CKPT_CRONO = '0'
$env:LLAMA_SPEC_CONF_ESENTA_POS0 = '0'; $env:LLAMA_SPEC_DRAFT_TOPK = '1'
$env:LLAMA_MAPPED_IBRIDO = '1';         $env:LLAMA_MAPPED_IBRIDO_SOGLIA = '2'
$env:LLAMA_OVERLAP_ASYNC = '1';         $env:LLAMA_OVERLAP_K = '2'
$env:LLAMA_OVERLAP_BATCH_MAX = '2';     $env:LLAMA_OVERLAP_GRIGLIA_VARIABILE = '0'
$env:LLAMA_OVERLAP_PIN = '1';           $env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
$env:LLAMA_KV_RING = '1';               $env:LLAMA_KV_RING_VRAM_TOKEN = '2048'
$env:LLAMA_KV_ROLLBACK_PARZIALE = '1';  $env:LLAMA_KV_ROLLBACK_SOLO_ANELLO = '0'
$env:LLAMA_VRAM_A_FASI = '0';           $env:LLAMA_DSV4_INDEXER_FUSO = '0'
$env:LLAMA_DSV4_HC_FUSO = '5';          $env:GGML_CUDA_GRAPH_OPT = '0'
$env:GGML_SCHED_PROFILO = '1'
[Environment]::SetEnvironmentVariable('LLAMA_CACHE_ORACOLO', $null)
```

### 2.2 Le variabili nuove di oggi

| variabile | difetto | cosa fa |
|---|---|---|
| `LLAMA_CACHE_ESPERTI_STRICT` | **1 (acceso)** | una leva chiesta e spenta in silenzio **ferma il processo**. `=0` per proseguire sapendo che quella leva non c'è |
| `LLAMA_CACHE_ESPERTI_FORK_COMPONI` | 0 | toglie i due rifiuti che tenevano separati fork e prefetch. Regge sulla protezione «in volo» |
| `LLAMA_CACHE_ESPERTI_SCUDO_TRANSITO` | 0 | il transito prende una classe sua in `kern_partiziona`: la lane CPU non prende ciò che stiamo copiando |
| `LLAMA_CACHE_ESPERTI_PF_DEV` | 0 | il prefetch copia sul device, senza host nel giro |
| `LLAMA_CACHE_ESPERTI_PF_DEV_MAX` | 2 | terne di drenaggio accodate per strato (lanci incondizionati) |
| `LLAMA_CACHE_ESPERTI_PF_TOP` | 0 (tutti) | quanti dei sei previsti prenotare. **1 è l'ottimo misurato** |
| `LLAMA_CACHE_ESPERTI_DMA_CODA` | 1 | batch di prefetch in volo insieme. Inerte se `scartati=0` |
| `LLAMA_CACHE_ESPERTI_DMA_GATE` | 1 | `=0` spegne il cancello auto-spegnente del DMA |

### 2.3 Le incompatibilità che il binario ora fa rispettare

```
FORK>0  richiede  LLAMA_CACHE_ESPERTI_W=0     (cache-esperti.cu:1745)
FORK>0  incompatibile con  DMA / DOMANDA_DMA  (cache-esperti.cu:1758)
```

Entrambe si tolgono con `FORK_COMPONI=1`. **Senza `COMPONI`, chiedere
`FORK=2` con `W=1` ora ferma il processo** invece di spegnere il fork in
silenzio — che è come si sono persi otto ore misurando codice mai eseguito.

### 2.4 Le tre configurazioni di riferimento

```powershell
# SOTA -- niente extra, solo il blocco comune
dopo_il_riavvio.ps1 tag 448

# prefetch al suo ottimo (14,17 t/s, colpi 58,8%)
"LLAMA_CACHE_ESPERTI_FORK_COMPONI=1;LLAMA_CACHE_ESPERTI_DMA=1;LLAMA_CACHE_ESPERTI_W=1;LLAMA_CACHE_ESPERTI_DMA_GATE=0;LLAMA_CACHE_ESPERTI_PF_DEV=1;LLAMA_CACHE_ESPERTI_SCUDO_TRANSITO=1;LLAMA_CACHE_ESPERTI_PF_DEV_MAX=2;LLAMA_CACHE_ESPERTI_DMA_CODA=8;LLAMA_CACHE_ESPERTI_PF_TOP=1"

# prefetch pieno (colpi 62,8% ma 10,6 t/s) -- per studiare la residenza
"...uguale ma senza PF_TOP"
```

### 2.5 Interruttori che NON fanno quello che sembra

- **`LLAMA_MAPPED_IBRIDO=0` non spegne lo zero-copy.** Spegnendolo il buffer
  mappato diventa VRAM vera e **il modello non entra** (fallisce
  l'allocazione di 2,3 GB per il drafter). La lettura diretta è ciò che fa
  entrare il modello.
- **`LLAMA_OVERLAP_ASYNC=0`** toglie il worker e il confine forzato, ma il
  nodo di partizione resta nel grafo. L'interruttore **strutturale** della
  lane è `LLAMA_OVERLAP_K=0`.
- **`LLAMA_CACHE_ESPERTI_CURA=2`** è raggiungibile e gira (`lanci=28.896`) ma
  `transiti riusati=0` sempre: lo spin da 256 a 20.000 giri non cambia di una
  unità. Non è la strada.

---

## 3. DOVE SIAMO

`docs/porto/LEDGER_13_AGOSTO.md` ha la tabella completa. In sintesi:

- **SOTA 14,74-14,79** a macchina fredda (`FORK=2`, 448 slot, niente DMA).
  **14,42 a caldo** dopo sedici ore — la deriva è reale, rimisurare a freddo.
- **Niente di oggi la batte.** Il ramo prefetch, portato dal non funzionare al
  funzionare al 100%, si ferma a **14,17**.
- **Il risultato che conta**: il **70,8%** degli esperti copiati in VRAM non
  viene **mai** riusato; l'85,5% non arriva ai due usi che ripagano la copia.
  Vale il **17-20%** più 85.594 sfratti risparmiati.

### Commit di oggi (fork `D:\llama-overlap`)

```
893a48671  il 70,8% degli installati non viene mai riusato
ef316f957  PF_TOP: la curva di selettivita'
2d220ce90  l'ordine lungo il token
fa41f7661  stream_pf era FUORI dal grafo
68bbe2b9c  il consumatore dell'anello passa sul DEVICE
1c2456ff2  scudo dell'esperto in transito
192bcac5a  protezione IN VOLO
3fc45684a  il drenaggio non alza la consegna: e' la FASE
e9bcf3052  il prefetch device-side ora gira
9e40c9ed6  PF_DEV non raggiungibile + abort di chiusura
```

---

## 4. IL LAVORO DA FARE

### 4.1 Portare il peso del router dentro la cache — È QUESTO IL LAVORO

Tutte le firme della cache sono `const int32_t * ids`: la massa si ferma prima.
Senza quel dato non si può decidere **cosa non installare**, che è dove sta il
17-20%.

**Il tensore esiste già nel grafo**: `cb(weights, "ffn_moe_weights_norm", il)`
in `src/llama-graph.cpp:2170` (e `ffn_moe_weights` a `:2149`).

**Il modo di prenderlo esiste già**: intercettazione per nome nel backend CUDA,
`ggml-cuda.cu:4714-4724`, il pattern usato per `cache_pf-<strato>-<n>`:

```c
strncmp(node->name, "cache_pf-", 9) == 0
```

**Il piano**: intercettare `ffn_moe_weights_norm-<il>`, salvare il puntatore
device nel runtime della cache indicizzato per strato, e passarlo a
`kern_decidi` come `const float * pesi` accanto agli `ids`. Da lì la decisione
per esperto.

**Attenzione al formato**: `ffn_moe_topk` è una **vista** di un argsort su
tutti i 256 esperti, non un tensore impacchettato — il passo si ricava come
`(totale - ne0) / (ne1 - 1)`, che dà 6 sui file impacchettati e **256** sulle
viste. Leggendolo impacchettato si prendono numeri a caso (già successo:
persistenza allo 0,1%, sotto il 2,3% del caso puro).

### 4.2 La politica a tre livelli

```
massa alta       -> COPIA in VRAM        rientra al secondo uso (0,403 poi 0,079)
massa bassa      -> ZERO-COPY in posto   0,274 sempre, nessuno slot, nessuno sfratto
massa bassissima -> CPU, fino a K=2      0,242, zero byte sul bus, capienza dura
```

L'ordine CPU-in-fondo è per **capienza**, non per costo: `K=3` porta i colpi al
73,8% (massimo storico) e fa 12,53 contro 14,17 di `K=2`.

**La macchina per instradare esiste**: il fork maschera le colonne residenti e
calcola mentre copia le mancanti (`kern_fj_maschera`). Serve una maschera a
**tre** valori invece che a due; la terza passata è il `mul_mat_id` originale
sul tensore mappato, già scritto e collaudato. Le due passate differiscono solo
per **come indicizzano la sorgente**: slab per slot, pesi mappati per id.

**Da rimisurare in produzione**: i tre costi (0,079 / 0,274 / 0,403) vengono da
un microbench **in isolamento**. Sotto contesa lo zero-copy legge sparso mentre
la copia è contigua, e può degradare. Anche pareggiando resta vantaggioso per
lo slot risparmiato.

### 4.3 Aperto

- `docs/porto/TODO_LANE_ADATTIVA.md` — `k_cpu` deve adattarsi a quanti non
  residenti veri ci sono, o col prefetch acceso la CPU si prende dei residenti
  (0,242 contro 0,060: fattore quattro buttato).
- **Anomalia da spiegare**: `K=1` (13,67) batte `K=1,8` (13,11). Sospetto la
  distribuzione di Bresenham, che a valori frazionari alterna forme fra strati
  adiacenti.
- **Rimisurare a freddo** SOTA e ottimo di capienza: tutte le tarature vecchie
  sono state fatte con la copia esposta all'84,5%, e ora la copertura è un
  parametro di progetto (fino all'81,8%).

---

## 5. GLI ERRORI DI OGGI, PERCHÉ NON SI RIPETANO

1. **Quattro difetti di raggiungibilità in fila** — codice mai eseguito che
   restituiva numeri plausibili. **Stampare il contatore sempre, anche a zero**:
   è lo zero che dimostra che il ramo è stato raggiunto.
2. **Tre volte ho usato un numero misurato in un braccio per ragionare su un
   altro.** Ogni numero che entra in un calcolo deve venire **dal log del
   braccio di cui si sta parlando**.
3. **Uno script con indici calcolati ha cancellato 3.593 righe** — `s.index()`
   aveva trovato la dichiarazione anticipata invece della definizione. Usare
   ancore testuali e `assert` sul numero di righe tolte.
4. **`grep` degli avvisi, non solo dei numeri**: `SPENTO`, `richiede`, `non
   componibile`. Un banco che stampa `SPENTO` e restituisce comunque un t/s
   misura un'altra configurazione.
5. **Codex non consegna** su questa macchina: l'11/8 quattro mandati e quattro
   consegne vuote. Usare `general-purpose`/`Explore`.

---

## 6. 22:31 — TRACCIA ESATTA E REPLAY DELLA RESIDENZA GLOBALE

È stato fatto **un solo run strumentato**, sulla SOTA invariata (`448`, `K=2`,
stesso `dopo_il_riavvio.ps1`). Le sole leve aggiunte scrivono la traccia:

```text
LLAMA_CACHE_ESPERTI_TRACCIA=D:\ds4_work\llama_run\trace_global_sota_b1.routes.bin
LLAMA_CACHE_ESPERTI_TRACCIA_ACCEPT=D:\ds4_work\llama_run\trace_global_sota_b1.accept.tsv
```

Il run ha riprodotto il riferimento al singolo contatore e allo stesso output:

```text
14,09 t/s strumentato; p1=0,86604; SHA=18353172D402
domanda=222.912; hit=122.361; miss=100.551
DSpark=556 accettati / 642 verificati
```

Il 14,09 **non è un nuovo benchmark**: la diagnostica costa circa il 2,3%
rispetto al 14,42 caldo. La cosa importante è SHA + contatori identici.

La traccia contiene 55.470 righe route, cioè 221.880 delle 222.912 domande
GPU (99,54%). Mancano 258 righe di route, pari a sei token-righe per 43
strati, nelle chiamate di warmup/prompt fuori dal partizionatore overlap. Dopo
50 cicli di riscaldamento, il replay LRU differisce dallo stato registrato di
soli 197 hit su 204.852 domande (<0,10%).

### Risultato

Il criterio giusto non è «il più vecchio», né il peso istantaneo del router.
È una **massa globale decaduta per (modello, strato, esperto)**, aggiornata su
tutti e sei gli esperti instradati, inclusi quelli mandati alla CPU.

Politica robusta emersa dal replay:

```text
massa: decadimento esponenziale, emivita 32-64 cicli di verifica
domanda target certa: +1
domanda della riga speculativa: +1 anche se poi rifiutata
ammissione: massa candidato >= 0,75
sfratto/copia: candidato >= vittima globale + 0,50
altrimenti: zero-copy, nessuno sfratto
vittima: massa minima globale; LRU soltanto come spareggio
peso softmax del router: 0 nel migliore robusto
```

La riga DSpark rifiutata **non va sottratta**: la verifica del target ha davvero
calcolato quegli esperti. L'esito di accettazione esplicito cambia il costo del
replay di meno dello 0,3%; la domanda fisica contiene già l'informazione utile.

Sul tratto dopo il warmup, usando i costi misurati 0,079/0,403/0,274 ms:

| replay | hit | copie | zero-copy | costo trasporto | vs SOTA |
|---|---:|---:|---:|---:|---:|
| SOTA registrata | 112.061 | 92.791 | 0 | 46.247,6 ms | — |
| corsie SOTA congelate | 104.565 | 4.222 | 96.065 | 36.283,9 ms | -21,5% |
| corsie ricalcolate dalla residenza | 132.816 | 1.927 | 70.109 | 30.478,9 ms | -34,1% |

La prima riga nuova è il limite conservativo: non cambia quali esperti fanno
CPU/GPU. La seconda è la politica completa: i residenti meritevoli finiscono
nelle quattro corsie GPU e i freddi nelle due CPU. Queste percentuali sono
**costo di trasporto seriale equivalente, non t/s promessi**: fork, CPU e PCIe
si sovrappongono, quindi il guadagno reale va misurato con un solo B.

### Budget fra target e drafter

La cache separata di DSpark ha 32 slot da 8,69 MiB. Nel run ha censito 1.023
installazioni: 1.020 mai riusate e 3 riusate una volta. Non merita 278 MiB di
residenza persistente; deve conservare soltanto il minimo insieme in volo e
servire il resto in posto. Ridare quel budget al target porta la simulazione
da 448 a un massimo teorico di 489 slot e riduce di un altro 2,4% il costo del
trasporto della nuova politica. Prima va stabilito il minimo sicuro del
working set DSpark: il suo contatore `domanda` sotto grafo è noto incompleto.

### Stato del codice

Il fork contiene ora diagnostica **spenta per default** per route e accept.
Non è stata implementata la nuova politica. Il prossimo braccio sensato è uno
solo: massa globale decaduta + ammissione contro la vittima, inizialmente con
448/32 invariati; se B è buono si ripete B, poi si prova la redistribuzione del
budget fra target e drafter.

---

## 7. 14 AGOSTO — BASE 16,0733, 150K VALIDATO E PROSSIMO BRACCIO

Questa sezione sostituisce lo stato operativo del paragrafo precedente. La
politica `MASSA=2` è stata implementata e poi separata in leve indipendenti. Il
regime promosso usa massa globale per la vittima, **copy-all** e corsie stabili:

```text
slot target/draft: 473 / 12
PORTO_SPEC_NMAX=2; PORTO_SPEC_CONF_MIN=0.8
LLAMA_OVERLAP_BATCH_MAX=3
LLAMA_SPEC_CONF_ESENTA_POS0=1
LLAMA_ACCEPTMOE=1; LLAMA_ACCEPTMOE_ESATTE=1
LLAMA_ACCEPTMOE_SOGLIA=0.75; LLAMA_ACCEPTMOE_COMPATTA=1
LLAMA_GRAPH_REUSE_PER_TAGLIA=1
LLAMA_CACHE_ESPERTI_MASSA=2
LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE=0
LLAMA_CACHE_ESPERTI_MASSA_CORSIE=0
```

Tre run corti identici: `16,04 / 16,11 / 16,07`, media **16,0733 t/s**.
Tutti hanno `p1=0,90025`, output identico byte per byte, hit target `77,9%` e
`47.906` miss/copie (`22,1%`). È la base corta autoritativa.

Leve già chiuse sopra questa base:

- `LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT=1`: `15,84 / 15,71 / 15,73`, media
  `15,76`; respinta. I kernel apparentemente ridondanti fornivano distanza utile
  alla copia asincrona.
- `LLAMA_CACHE_ESPERTI_SALTA_COPIA_PARITA=1`: un solo B, **15,37055 t/s**,
  `p1=0,90025`, `713/792` draft accettati. Output corto identico byte per byte
  alla base (`SHA256 4FDCFADF...ADC65D`), ma parete `-4,37%`: respinta, nessuna
  replica. Artifact in
  `C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\mass2_stable_nocopypar_t473_d12_b1.*`.

### Contesto lungo realmente validato

Capacità effettiva `150.016`, prompt `101.676` token, completamento `2.048`,
contesto finale `103.724`: superati i gradini `101.380` e `102.404`.

```text
LLAMA_VRAM_A_FASI=2; batch/ubatch prefill=1024
prefill: 92,30 t/s
decode medio dei 2.048 token: 9,69 t/s
cache target: 473 -> 0 nel prefill -> 473 nel decode
p1=0,76501; zero OOM, divergenze replay o errori CUDA
```

L'output è coerente e non degenerato, ma termina a `length` prima delle 20
sezioni richieste. `FASI=1` era OOM a 7.169 token; `FASI=2` libera 3.194 MiB.
Artifact: `D:\ds4_work\llama_run\ctx150k_mass2_stable_f2_b1024.*`.

### Due fronti separati

- **Decode corto verso 20 t/s**: prossimo B economico non ancora falsificato,
  una sola leva, è la vecchia combinazione `MASSA2 + FORK_BLOCCHI=4`. Se è
  chiaramente negativa si torna al codice; se è positiva o entro circa il 4%,
  si fanno tre run totali identici e si usa la media. Alternativa di codice:
  `FORK_COPIA_ILP=4`, default-off, con target copia media `<=0,752 ms`.
- **Prefill verso 1000 t/s**: i moltiplicatori VRAM principali sono maschere
  CSA/LID/HCA, `indexer_score` e fallback top-k/argsort a tre piani. Prima di
  un ring generico: maschere descrittore/F16, top-k chunked e rilascio congiunto
  graph + pool; per `ub=4096`, indexer/top-k tiled e grouped MoE.

Inventario denso target verificato: CUDA0 `7.383,67 MiB` = attention
`4.660,125`, shared expert `1.096,5`, compressori+indexer `929,295`,
output+norm `536,578`, resto circa `161`. Gli esperti routed sono già
`74.304 MiB CUDA0_Mapped`; embedding F16 `1.010 MiB` è già `CUDA_Host`.
Non aggiungere altro `CUDA0_Mapped`: il pin base è circa `76,3 GiB`. Per il
prefill phase-aware usare backing pageable/mmap e piccolo staging VRAM. DSpark
resta il primo candidato da caricare soltanto alla transizione decode.

Per i test lunghi, lo state DSV4 target serializza già raw/SWA, CSA/HCA/LID,
compressori e cold ring. `/slots` salva però soltanto `ctx_tgt`: patch minima
nel server per bundle target+draft+manifest; validare prima a 6,5k, poi creare
una sola fixture a circa 101k.

Il worktree `D:\llama-overlap` è deliberatamente molto dirty. Preservare tutto;
le modifiche di questa sessione sono intrecciate con lavoro preesistente nei
file CUDA. Ogni commit deve essere costruito con path/hunk espliciti, mai con
`git add -A`, e senza push.
