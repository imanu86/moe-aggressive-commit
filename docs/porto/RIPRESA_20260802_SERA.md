# Ripresa — 2 agosto 2026, sera (dopo il riavvio)

---

## 0. DECISIONE: si abbandona il tronco DwarfStar

Presa dall'utente il 2/8 sera. Il motore di lavoro e' **llama.cpp**, non piu' il
fork ds4.

Cosa vuol dire, in pratica:

```
ABBANDONATO   il tronco DwarfStar e i 14 blocchi del porto (fb57329, 16.354
              righe). Non si cancella niente: resta in git come archivio, e il
              piano resta in docs/porto/PIANO.md. Non ci si lavora piu'.
              Con lui va via anche il KV staged ring (blocco 11, d4a5550,
              dietro DS4_CUDA_KV_STAGED_RING): non e' mai stato portato su
              llama.cpp e non lo sara'.

RESTA VIVO    D:\llama-vanilla, worktree su b10227 (f5919bf) + le patch reap.
              docs/porto/curva_run.py, scala_reap.ps1, llama_confronto.ps1,
              mappa/capienza.py -- gli strumenti di misura, che sono agnostici.

RESTA VALIDO  il tracciato [route-ids] prodotto da DwarfStar. La scelta degli
              esperti e' una proprieta' del MODELLO, non del motore: stesso
              modello e stesso prompt a temperatura 0 danno la stessa routing.
              E' il dato su cui gira capienza.py.

DECADE        docs/porto/mappa/catena.py e MAPPA_SINTESI.md interrogano il
              codice DwarfStar. Restano leggibili come archivio, ma non
              descrivono piu' il motore in uso.
```

Perche' ha senso: llama.cpp fa 6,79 t/s medi in decode contro i 4,37 di
DwarfStar sullo stesso banco, e lo fa senza avere un trasporto -- calcola dove
sta il dato. Le nostre leve migliori su llama.cpp (`-ncmoe`, `-ot`) sono di
collocazione statica, e non richiedono niente del tronco vecchio.

---

Scritto **prima** di riavviare il PC. Il riavvio serve a riportare la macchina
allo stato in cui il banco riproduceva il proprio riferimento.

---

## 0-bis. DECISIONE: il reap-loop si tiene e si accende

Presa dall'utente il 2/8 sera, **dopo** aver visto il conto di capienza che
falsifica la fase 2. La falsificazione riguarda la **politica** (a capienza RAM
la LRU sta a 2,2 punti dall'ottimo, l'insieme caldo ne guadagna 0,3): non
riguarda l'osservatore, che l'utente vuole acceso.

Quindi: **non rimuovere il modulo reap.** Se un domani sembra codice morto, la
ragione per cui e' li' e' questa riga.

Stato reale al momento della decisione:

```
D:/llama-b10227          reap NON compilato   <- il binario di TUTTE le misure di stasera
D:/llama-vanilla/build   reap compilato       <- la nostra build, mai lanciata in misura
LLAMA_REAP               mai impostata
```

**L'osservatore riscritto senza lock non e' MAI STATO ESEGUITO.** Riscritto,
compilato, verificato dentro `llama-common.dll`, e mai lanciato una volta. Il
primo passo per "accenderlo" non e' una misura di velocita': e' un run di prova
che dimostri che gira.

```powershell
$env:LLAMA_REAP='1'; $env:LLAMA_REAP_PROF='1'
$env:LLAMA_REAP_DUMP='D:\ds4_work\llama_run\reap_calore.tsv'
& docs\porto\llama_confronto.ps1 -Ngl 99 -Tokens 1500 -Ctx 10000 `
    -Exe 'D:\llama-vanilla\build\bin\llama-server.exe' -Extra @('-ncmoe','42') `
    -Etichetta 'reap_prova'
```

Cosa deve uscire, allo spegnimento del server:

```
reap: osservatore installato (anello 65536 record, 5.0 MiB), cronometro ACCESO
reap: N chiamate, M record prodotti, M letti, 0 persi, ~11000 esperti distinti
reap: sezione critica X ns/chiamata
```

I **ns/chiamata** sono il numero che il 2/8 abbiamo dedotto invece di misurare,
e che ha fatto accusare l'osservatore di un -32% che era della macchina. Se
"persi" non e' zero, l'anello e' troppo piccolo o il consumatore troppo lento.

---

## 1. IL RISULTATO DELLA SERATA: l'osservatore reap e' innocente

Il handoff attribuiva all'osservatore un -32% (6,86 -> 4,66) causato dal lookup
su hash map dentro `if (ith == 0)`, prima di `ggml_barrier`. **Non era lui.**

Due controlli, entrambi nuovi:

```
                                       finale   regime(500-800)
ncmoe42 riferimento      15:16           6,86        7,88
ncmoe42 ripetizione      15:48           6,75        7,82
reap_cpu, osservatore ACCESO  17:32      4,66        5,74
A1, osservatore SPENTO        17:53      5,07        5,67   <- stessa build
```

Con `LLAMA_REAP` assente la callback non viene nemmeno installata
(`g_moe_ids_observer` resta NULL: un test di puntatore per nodo, nient'altro),
e la macchina fa **5,67** contro i **5,74** del run che ce l'aveva accesa.
Sono lo stesso numero.

Il conto lo diceva gia' prima di misurare: il barrier di ggml e' uno spin puro
(`ggml-cpu.c:599`, nessun fallback a sleep), quindi gli altri thread pagano
esattamente il ritardo del thread 0. Quel ritardo sarebbe stato

    68,8 ms/token / (42 strati x 3 mul_mat_id x 6 id) = 91 us per lookup

contro i 20-100 **ns** che un `unordered_map` costa davvero: mille volte tanto.

L'osservatore e' comunque stato riscritto senza lock (commit `123847a`) — e'
il disegno giusto e serve alla fase 2 — ma **non era quello il problema**.

---

## 2. IL PROBLEMA VERO: il banco non riproduce piu' se stesso

Alle 15:16 la configurazione promossa faceva regime 7,88. Alle 17:53 la stessa
identica configurazione ne fa 5,67. **-28% che non appartiene a nessuna leva.**

Finche' e' cosi', ogni misura non confronta la leva: confronta lo stato della
macchina. E' per questo che si riavvia.

Stato misurato appena prima del riavvio:

```
Disponibile   56,7 GB      Standby   48,0 GB      Free+Zero   8,7 GB
VRAM          580 MiB      (base pulita ~750 MiB, quindi pulita)
modello       80,76 GiB  -> al massimo il 59% sta in standby, e QUALE 59% decide tutto
```

Indiziato principale: `offload1` (GGML_OP_OFFLOAD_MIN_BATCH=1) ha girato
**17:18:44 -> ~17:31**, tredici minuti a copiare il tensore intero per strato
per token (72 GB/token), abortito. Il run reap e' partito alle 17:32:34, un
minuto dopo. Da li' in poi nessun run e' piu' risalito.

Nota: il ledger data `offload1` "16:5x", ma il nome del file dice 17:18:44.

---

## 3. LA PRIMA COSA DA FARE DOPO IL RIAVVIO

**Rimisurare il riferimento**, prima di qualunque leva. E' il cancello: se non
torna ~7,8 di regime, il riavvio non ha risolto e non si misura altro.

```powershell
$env:LLAMA_ARG_CPU_MOE = '1'
& C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\llama_confronto.ps1 `
    -Ngl 99 -Tokens 1500 -Ctx 10000 `
    -Exe 'D:\llama-dspark\build\bin\llama-server.exe' `
    -Extra @('-ncmoe','42') -Etichetta 'postriavvio_rif'
```

poi

```bash
python docs/porto/curva_run.py "D:/ds4_work/llama_run/<tag>.server.log"
```

e si legge la riga **REGIME**, non il finale.

### Se il riferimento torna, i tre bracci sono gia' pronti

`docs/porto/reap_3bracci.ps1` fa A-B-A da solo (controllo, trattamento,
controllo), con 120 s di quiete fra i bracci. L'ordine mette il trattamento FRA
i due controlli apposta: se la cache si scalda run dopo run, il confronto
B-contro-media(A) non ne e' falsato.

A1 e' gia' stato fatto e catalogato; mancano **B** (`LLAMA_REAP=1` +
`LLAMA_REAP_PROF=1`) e **A2**. Rilanciandolo intero si rifanno tutti e tre, che
va bene: A1 rifatto dopo il riavvio vale piu' di quello di stasera.

Con `LLAMA_REAP_PROF=1` il modulo cronometra la propria sezione critica e
stampa i **ns/chiamata effettivi** allo spegnimento: cosi' il costo si misura
invece di inferirlo.

---

## 4. LO STRUMENTO NUOVO: `docs/porto/curva_run.py`

Il ledger registrava `eval time = ... N tokens per second`, che e' una media
**cumulativa** su tutta la corsa. Su questa macchina la corsa non e'
stazionaria — il modello sta 16 GB sopra la RAM e la page cache si scalda:

```
ncmoe42   a100 4,51   a400 5,04   a800 6,06   a1200 6,53   a1500 6,86
```

Quindi il numero finale dipende dalla **lunghezza della corsa** e da **quanto
era calda la cache alla partenza**, due cose che non c'entrano con la leva.
Il run reap era a 800 token contro i 1500 del riferimento: un terzo del divario
era solo lunghezza.

`curva_run.py` stampa la mediana di `tg_3s` in finestre **fisse** di token. La
finestra 500-800 e' quella che ogni run della campagna raggiunge.

Rimisurando il 2/8 a finestra appaiata:

```
                       finale   regime(500-800)
ncmoe42                 6,86        7,88
ncmoe42 ripetizione     6,75        7,82      <- scarto 0,8%, non 1,6%
gate3                   6,60        7,79
cmoe                    6,61        7,45
reap_cpu                4,66        5,74
A1 (osservatore spento) 5,07        5,67
ncmoe41                 4,61        4,81
```

La "varianza fra run ~1,6%" era per meta' rumore di riscaldamento.

**Da rifare con questa lente**: i verdetti del pomeriggio sono tutti misurati
sui finali. `gate3` contro `ncmoe42` passa da -3,8% a -1,1%; `cmoe` contro
`ncmoe42` da -3,6% a -5,5%. Nessuno si ribalta, ma i margini cambiano.

---

## 5. DA REGISTRARE D'ORA IN POI: lo stato della cache

E' la variabile che ha fatto perdere la serata, e non era in nessun manifest.
Prima e dopo ogni run:

```powershell
$m = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
'{0:N1} GB disponibile, {1:N1} GB standby' -f ($m.AvailableMBytes/1024),
  (($m.StandbyCacheNormalPriorityBytes + $m.StandbyCacheCoreBytes + $m.StandbyCacheReserveBytes)/1GB)
```

(I nomi inglesi di `Get-Counter` non funzionano su questo Windows: serve
`Win32_PerfRawData_PerfOS_Memory`, che ha le proprieta' in inglese comunque.)

---

## 6. ALTRO CHIUSO OGGI

- **Guardiano dello sha**: la costante attesa in `llama_confronto.ps1` era
  `38f6ec5e5f9d3d8f`, che non e' lo sha del prompt scritto tre righe sopra.
  L'avviso e' suonato a ogni run del 2/8 e ci si era abituati a scorrerlo.
  Corretta a `38f6ec5ee5403f59`. Verificato il fatto che doveva proteggere: la
  stringa e' identica byte per byte in `braccio.ps1:277`,
  `llama_confronto.ps1:31` e `dspark.ps1:31`.

---

## 7. LA CODA AGGIORNATA

1. **Cancello dopo il riavvio**: il riferimento torna a ~7,8 di regime? Se no,
   non si misura altro finche' non si capisce perche'.
2. Bracci **B** e **A2** del reap (A1 fatto). Con `LLAMA_REAP_PROF=1`.
3. **Rileggere l'atlante con `curva_run.py`**: i verdetti del 2/8 sono sui
   finali, non sul regime.
4. Fase 2 del reap-loop. **Prima pero' un conto che non e' stato fatto**: i
   numeri che la giustificano (LRU 0%, insieme caldo 28,2%, Belady 47,8%)
   vengono da una cache di 181 slot su 4551, cioe' il 4% di capacita'. Il
   gradino RAM<->SSD ne ha ~59% (48 GB di standby su 80,76 GiB). A quella
   capacita' la curva e' tutta un'altra, e va ricalcolata dal dump del calore
   **prima** di scrivere la politica.
5. Quantizzare DSpark (MXFP4 -> Q2_0), 20 minuti.
6. Recuperare VRAM dedicata per far entrare il secondo strato a `-ncmoe 41`.
