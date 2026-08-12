# 12 agosto: il banco ha perso il 13-14%, e la perdita ha un nome

## Il fatto

Il 12/8 alle 06:07 l'utente riavvia il PC. Da quel momento **la stessa
configurazione, sullo stesso binario, con la stessa uscita bit per bit** rende il
13-14% in meno. Non e' deriva: e' un gradino, riprodotto da nove corse.

```
  05:06  f5b     14,48   \  stesso ggml-cuda.dll (02:35), stesso manifesto,
  05:10  j_rif   14,46   /  stesso SHA d'uscita FE90AC77066D
  ----------------------- RIAVVIO 06:07 -----------------------
  06:23  m5a     12,79
  06:33  m5b     12,88
  07:20  p_rif2  12,30
  07:37  p512b   12,45
```

Due catene omogenee (sonda accesa e sonda spenta) danno lo stesso salto: -14,3%
e -13,1%. Non e' un artefatto della sonda.

## Dove sta, con un numero

Il braccio `j_rif` rifatto identico, con la stessa sonda `GGML_SCHED_PROFILO`:

```
                       05:10      dopo      delta
  ingressi             2,839      7,202     +154%
    di cui sync        2,166      6,488     +200%   <-- tutto qui
  calc CPU             0,848      0,810     piu' BASSO
  calc altri (lancio)  3,015      2,933     piu' BASSO
  worker calcolo      15,445     15,898     +2,9%
  join (sched)        24,698     25,601     +3,7%
```

**Tutto cio' che calcola e' uguale o piu' veloce. E' cresciuta solo l'attesa.**
E' un costo **per confine**: ~76 confini CPU-GPU a token, +140 us l'uno, cioe'
+10,7 ms/token contro i +12,8 osservati.

Corroborazione indipendente: la sonda `GGML_SCHED_PROFILO` cronometra proprio le
sync, e il suo costo e' passato da **0%** (ieri: `b_f512` accesa 14,78 contro
`qs512b` spenta 14,77) a **3,6%** (oggi: 12,835 contro 12,375).

## Cosa e' stato escluso, ognuno con un numero

- **Configurazione**: manifesto identico in 77 voci su 77 (l'unica differenza e'
  `VRAM_ZAVORRA=0(E)` contro `0(D)`, stesso valore).
- **Binario**: il `ggml-cuda.dll` delle 02:35 aveva gia' fatto 14,46-14,48 alle
  05:00. Niente da bisezionare.
- **I tre KB**: KB5123304 e KB5120708 **installati alle 03:28-03:29**, cioe' due
  ore PRIMA delle corse buone delle 05:06. KB5121003 e' in coda dalle 03:31, e
  anche quello stato c'era gia' mentre il banco faceva 14,48. Il contenuto
  dell'aggiornamento e' escluso dalla cronologia (registro `Setup`).
- **Traiettoria**: SHA `FE90AC77066D`, p1 0,85449, `mean len` 1,85, `graphs
  reused` 627: identici.
- **Banda del letto mappato**: `blocco.exe` da' **24,4 GiB/s** sia a 4 che a 64
  GiB di pinnata, identico all'11/8.
- **GPU**: SM 1950 MHz stabile, mem 7301, PCIe **gen 4 x16**, throttle 0x0,
  94 W su 170. E il proponente e' piu' VELOCE (8,45 -> 8,31 ms/chiamata).
- **CPU**: boost 123% a riposo, 118-120% sotto carico (~4,5 GHz all-core).
- **Driver NVIDIA**: `nvcuda.dll` di aprile (596.21), non toccato.
- **OneDrive**: parte da solo al boot ed era il sospettato migliore -- con
  OneDrive **chiuso** la corsa fa 12,21, cioe' peggio. Falsificato.
- **VRAM libera all'avvio**: `11255 MiB free` in tutte e sette le corse, buone e
  rotte, identica al MiB.
- **Contesa**: campionata ogni 3 s, `server vivi` max 1.
- **Secondo riavvio**: non riporta indietro niente (12,30). Non e' uno stato di
  avvio transitorio.

**Cosa NON e' stato nominato**: il meccanismo dietro i +140 us per confine.

## La conseguenza pratica: l'ottimo della capienza si e' spostato

In questo regime il costo per confine domina, e la curva si ribalta. Ieri 512
batteva 339 del 3,9%; oggi:

```
  slot    t/s                  ciclo                sync              colpi
  512     12,30  12,45         150,7  148,9         6,49  7,08         60%
  448     12,91  12,99  12,78  144,6  144,0  146,3  6,33  6,62  6,76   55-60%
  339     12,63  12,82         139,2  137,3         5,02  5,02         55%
  256     10,44                178,2                15,17              11%
```

Sul **ciclo** vince 339 (137-139 contro 149-151), sul **t/s** vince 448 -- a 339
il p1 esce 0,75806, la stessa lotteria di traiettoria riprodotta tre volte. A 256
la cache cade dal precipizio.

**Attenzione**: la ripetizione a 339 riproduce `sync` alla terza cifra (5,019
contro 5,017), quindi lo strumento e' preciso; il 9,2% di scarto visto fra le due
corse a 512 e' una proprieta' di quella configurazione, non del banco.

## Aperto, e non ancora misurato

1. **Il 2x2 bozza x lane.** Sulla piattaforma buona la lane valeva **+15%**
   (14,78 con lane contro 12,85 senza). Oggi con la lane facciamo 12,3-12,5,
   gia' sotto il 12,85 di ieri senza. Se la lane e' andata a zero, il bersaglio
   numero uno diventano le **277 `cudaMemcpyAsync` a token** del fallback dello
   scheduler, che esistono solo perche' la lane impone `LLAMA_MAPPED_IBRIDO=1`.
   Celle mai fatte con `FORK=2/BLOCCHI=8`: bozza+lane spenta+IBRIDO=0 (`n_fork`),
   e la stessa con IBRIDO=1 (`n_ibrido`), che separa i due effetti.
2. **Capienza contro MARGINE.** Che il pool "si riprenda" la VRAM liberata e'
   solo una delle due letture; l'altra e' che a 512 il pool sia **strozzato**.
   Si separa con `339 slot + 645 MiB di zavorra`, che riporta il margine a quello
   di 512 tenendo ferma la capienza (`LLAMA_VRAM_ZAVORRA`, in MiB, esiste
   apposta: "abbassa il margine a capienza ferma", `cache-esperti.cuh:426`).
   La falsificazione della soglia dei 400 MiB e' dell'11/8, su una piattaforma
   dove `sync` valeva 2,17: non si trasferisce.

## Le trappole che questa giornata ha comprato

- **Si salva PRIMA, si spegne DOPO.** La chiusura pulita fa `AttachConsole` e
  manda `GenerateConsoleCtrlEvent(0,0)`, che va a tutto il gruppo della console
  **incluso lo script che lo manda**. Un ciclo di bracci si suicida al primo
  giro; un braccio singolo muore dopo aver misurato e prima di scrivere. Sono
  andati persi tre bracci prima di capirlo.
- **Chi orchestra non si fida del marcatore, legge l'artefatto.** Il regista
  aspettava 15 minuti una stringa che non poteva arrivare, senza mai guardare il
  log del server, che invece conteneva il risultato.
- **Un file vecchio con lo stesso nome e' un risultato falso.** `k448.server.log`
  di un'altra giornata e' stato letto 15 s dopo l'avvio e ha prodotto un numero
  plausibile e sbagliato. Cancellare gli artefatti del tag prima di lanciare.
- **Le date, non gli orari.** Ho letto `07:57` senza l'anno e ho concluso che un
  altro processo stesse misurando in parallelo: erano file del giorno prima.
- **Il prefill del nostro banco NON e' una banda.** Il prompt e' di 68 token e il
  tempo e' quasi tutto costo fisso: a 68 token `ub 512` da' 21,9 e `ub 64` da'
  ~22, identici. I 100+ t/s di prefill sono di corse con prompt da 6000 token.
  Usare il calo del prefill come prova del costo per confine e' debole.
- **I processi lanciati dalla shell di Claude muoiono con la sessione.** Si
  staccano con `Invoke-CimMethod Win32_Process Create`.

## Gli strumenti scritti oggi

```
  docs/porto/freddo_fuso.ps1      ABBA FUSO 5/7 a macchina fredda
  docs/porto/dopo_il_riavvio.ps1  UN braccio: <tag> <slot> [zavorra MiB]
  docs/porto/due_per_due.ps1      il 2x2 bozza x lane, un braccio per invocazione
  docs/porto/curva_capienza.ps1   (superato dal regista: aveva il ciclo interno)
  docs/porto/regista.ps1          incatena i bracci, staccato, legge dal log
```
