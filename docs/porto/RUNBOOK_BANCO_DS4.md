# RUNBOOK BANCO DS4 / PORTO — procedura operativa

Versione: 16 agosto 2026. Ambiente: Windows 11 Pro, RTX 3060 12 GB, PowerShell 5.1.

Questo documento serve a **eseguire** misure sul banco, non a progettarle. È scritto perché
un esecutore che non conosce il progetto possa lavorare senza decidere nulla. Ogni passo ha
tre parti: **COMANDO** (da copiare così com'è), **ATTESO** (la stringa esatta da trovare),
**SE FALLISCE** (che cosa fare, sempre esplicito).

---

## REGOLA ZERO — leggere prima di qualunque cosa

1. **Non improvvisare mai.** Se un passo non produce l'output atteso, si esegue il ramo
   «SE FALLISCE» di quel passo e basta. Non si prova una variante, non si cambia un
   parametro, non si «riprova a mano».
2. **Se un passo dice FERMATI, ci si ferma.** Si scrive che cosa si è visto (comando,
   output testuale, percorso dei file) e si consegna. Un braccio non eseguito è un esito
   accettabile; un braccio eseguito male è un danno, perché entra nel ledger.
3. **Non si inventa nessun numero.** Ogni numero riportato deve venire da un file su disco
   di cui si dà il percorso assoluto. Se un numero non c'è nel file, si scrive
   «non presente nel log», non lo si deduce.
4. **Non si legge il risultato da un documento o da un commento in uno script.** Il
   riferimento si legge dal **log della corsa di riferimento**. Le note incollate negli
   script sono storiche e possono essere false.
5. **Un solo server llama alla volta.** Mai due. Vedi §1.4.
6. **Non si tocca la configurazione della GPU** (niente `nvidia-smi -rgc`, niente pannello
   NVIDIA, niente overclock, niente clock-keeper). Vedi §10.
7. Tutte le attese sono **polling attivo** con un check che si ripete. Mai una `Start-Sleep`
   lunga «sperando che sia pronto». I comandi di questo runbook implementano già il polling.
8. **Non si scrive niente dentro `D:\llama-overlap`** e non si eseguono `git reset`,
   `git checkout --`, `git clean` in nessun albero. Vedi §10.

Percorsi che ricorrono (tutti assoluti, da usare così):

```text
Binario server     : D:\llama-overlap\build\bin\llama-server.exe
DLL CUDA           : D:\llama-overlap\build\bin\ggml-cuda.dll
Modello target     : C:\ds4-models\DS4-0731-IQ2XXS.gguf
Modello draft      : D:\ds4-models\DSpark-draft-Q2K.gguf
Prompt del banco   : D:\ds4_work\llama_run\jprompt.txt
Runner A (freddo)  : C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\dopo_il_riavvio.ps1
Runner B (bracci)  : C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1
Artefatti runner A : D:\ds4_work\llama_run\
Artefatti runner B : C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\
```

**Due alberi di output, non uno.** I run fino al 15 agosto stanno in `D:\ds4_work\llama_run`;
i run del 16 agosto stanno nella cartella `work\runs` del runner B. Cercare un tag nella
cartella sbagliata dà un falso negativo. Quando si cita un artefatto si scrive **sempre** il
percorso completo.

---

## 1. Prerequisiti e check di salute

Eseguire **tutti** i passi di questa sezione, in ordine, prima di qualunque corsa. Se anche
uno solo fallisce, non si lancia niente.

### 1.1 Nessun processo llama attivo

**COMANDO**

```powershell
Get-Process -Name llama-server, llama-cli -ErrorAction SilentlyContinue |
    Select-Object Id, ProcessName, StartTime
```

**ATTESO** — nessun output (la tabella è vuota).

**SE FALLISCE** (viene elencato almeno un processo): NON uccidere niente. Attendere con
polling fino a 10 minuti che escano da soli:

```powershell
for ($i = 0; $i -lt 120; $i++) {
    $p = @(Get-Process -Name llama-server, llama-cli -ErrorAction SilentlyContinue).Count
    Write-Output "check $i : processi=$p"
    if ($p -eq 0) { break }
    Start-Sleep -Seconds 5
}
```

Se dopo 10 minuti sono ancora vivi: **FERMATI**. Riporta PID e nome. Non usare
`Stop-Process`. Un `Stop-Process -Force` è una `TerminateProcess`: non distrugge il contesto
CUDA e non rilascia in modo ordinato le decine di GiB di memoria pinnata; il braccio
successivo ne paga il conto e la misura non vale.

### 1.2 Non uccidere mai il server della UI

**COMANDO**

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue } |
    Select-Object Id, ProcessName
```

**ATTESO** — o nessun output, o un processo qualunque.

**REGOLA** — se qualcosa ascolta sulla porta 8000, **si lascia stare**. È il server della
interfaccia utente. Non si arresta, non si riavvia, non lo si conta come «processo llama
residuo». Le porte del banco sono altre: **8099** (runner A), **8100** (runner B), 8110
(agente DS4 read-only). Se una di quelle tre è già occupata, vedi §1.5.

### 1.3 Salute e stato a riposo della GPU

**COMANDO**

```powershell
& nvidia-smi --query-gpu=name,clocks.sm,clocks.mem,power.draw,memory.used,memory.free,pcie.link.gen.gpucurrent,pcie.link.width.current,clocks_throttle_reasons.active --format=csv,noheader,nounits
```

**ATTESO** — una riga sola, del tipo:

```text
NVIDIA GeForce RTX 3060, 210, 405, 13.09, 616, 11500, 4, 16, 0x0000000000000001
```

Controlli, uno per uno:

| campo | valore accettabile | se fuori |
|---|---|---|
| `memory.used` (5° campo) | **< 1200** MiB | FERMATI: c'è ancora qualcosa in VRAM |
| `memory.free` (6° campo) | **>= 10000** MiB | FERMATI |
| `pcie.link.width.current` (8° campo) | **16** | FERMATI e riporta: link degradato |
| clock SM a riposo (2° campo) | 200-450 MHz | è normale: a riposo la GPU sta bassa |

**SE FALLISCE `nvidia-smi` stesso** (comando non trovato, errore): FERMATI. Non cercare
percorsi alternativi, non installare niente.

**NON FARE**: `nvidia-smi -rgc`, `nvidia-smi -lgc`, `nvidia-smi -pl`, o qualunque comando
che *imposti* qualcosa. Solo `--query-gpu`. Un tentativo di reset clock è già stato negato
per privilegi insufficienti ed è **vietato aggirarlo**.

### 1.4 RAM libera

**COMANDO**

```powershell
$ram = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
Write-Output "RAM libera = $ram GB"
```

**ATTESO** — `RAM libera = <numero> GB` con numero **>= 28**.

**SE FALLISCE** (< 28 GB): attendere con polling fino a 15 minuti che risalga, poi
FERMATI e riporta il valore. Non chiudere applicazioni dell'utente.

Perché 28: è la barriera di cold-start del runner collaudato
(`C:\Users\imanu\Documents\Codex\2026-07-25\legg\work\c4k_diag_sameenv.ps1`, righe 58-84),
che pretende **nessun server vivo + VRAM usata < 1200 MiB + RAM disponibile >= 28 GiB**
prima di allocare l'arena.

### 1.5 Porte libere

**COMANDO**

```powershell
foreach ($p in 8099, 8100) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($c) { Write-Output "porta $p OCCUPATA da PID $($c.OwningProcess)" }
    else    { Write-Output "porta $p libera" }
}
```

**ATTESO** — `porta 8099 libera` e `porta 8100 libera`.

**SE FALLISCE**: FERMATI e riporta quale porta è occupata e da quale PID. Non liberarla.

### 1.6 Spazio su disco

**COMANDO**

```powershell
Get-PSDrive -PSProvider FileSystem |
    Where-Object { $_.Name -in 'C', 'D' } |
    Select-Object Name, @{n='LiberiGB';e={[math]::Round($_.Free/1GB,1)}}
```

**ATTESO** — `C` con almeno **20 GB** liberi e `D` con almeno **20 GB** liberi.

**SE FALLISCE**: FERMATI. Non cancellare niente per fare spazio (in quelle cartelle ci
sono run non ancora catalogati). Riporta i valori.

### 1.7 Il binario esiste ed è quello che credi

**COMANDO**

```powershell
Get-Item 'D:\llama-overlap\build\bin\llama-server.exe','D:\llama-overlap\build\bin\ggml-cuda.dll' |
    Select-Object FullName, Length, LastWriteTime
Get-FileHash 'D:\llama-overlap\build\bin\llama-server.exe' -Algorithm SHA256 |
    Select-Object -ExpandProperty Hash
Get-FileHash 'D:\llama-overlap\build\bin\ggml-cuda.dll' -Algorithm SHA256 |
    Select-Object -ExpandProperty Hash
```

**ATTESO** — entrambi i file esistono. `llama-server.exe` è piccolo (~10 KB: è un launcher
sottile) e `ggml-cuda.dll` è grande (~213 MB): **è normale**, non è un errore.

**AZIONE OBBLIGATORIA** — trascrivere i due SHA256 nel verbale del braccio. Il numero di
build stampato dal server può essere stantio (lo dice l'audit del 16/8): i due hash sono
l'unica identità affidabile del binario.

**SE FALLISCE** (un file manca): FERMATI. Non compilare niente. Non cercare un altro
binario. Riporta.

### 1.8 Il prompt del banco è intatto

**COMANDO**

```powershell
$pp = 'D:\ds4_work\llama_run\jprompt.txt'
Get-Item $pp | Select-Object Length, LastWriteTime
(Get-FileHash $pp -Algorithm SHA256).Hash
```

**ATTESO**, esattamente:

```text
Length = 252
SHA256 = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9
```

**SE FALLISCE**: **FERMATI immediatamente**. Se il prompt è cambiato, nessuna corsa è
confrontabile con lo storico e tutte le firme d'identità di §12 sono inutilizzabili.
Riporta lunghezza e hash trovati.

Testo del prompt (per verifica visiva, 252 caratteri, **tutto ASCII**):

> Genera una pagina HTML completa single-file per una startup AI NeuraForge, stile cyberpunk
> neon: head con CSS interno, header con nav, hero, 3 feature card, tabella prezzi 3 tier,
> form contatti con validazione JS, footer. Codice completo e commentato.

### 1.9 Verbale di preflight

Prima di proseguire, scrivere queste righe nel verbale (servono a §8 e §9):

```text
data/ora        =
uptime_min      =   (comando sotto)
ram_libera_gb   =
vram_usata_mib  =
vram_libera_mib =
disco_c_gb      =
disco_d_gb      =
sha_llama_server=
sha_ggml_cuda   =
sha_jprompt     =
```

```powershell
[math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes, 1)
```

---

## 2. Lancio A FREDDO (prima corsa dopo un riavvio di Windows)

A inizio sessione, e **sempre dopo un riavvio**, la prima cosa che si misura è il
riferimento, non la leva. Serve a sapere in che stato è la macchina oggi.

### 2.1 Attendere che il sistema si assesti

Dopo il login, prima di lanciare: attendere che l'uptime sia **>= 10 minuti** e che la RAM
libera sia stabile.

**COMANDO**

```powershell
for ($i = 0; $i -lt 60; $i++) {
    $up  = [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes, 1)
    $ram = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
    Write-Output "check $i : uptime=$up min  ram=$ram GB"
    if ($up -ge 10 -and $ram -ge 28) { break }
    Start-Sleep -Seconds 30
}
```

**ATTESO** — una riga finale con `uptime >= 10` e `ram >= 28`.

**SE FALLISCE** dopo 30 minuti di polling: FERMATI e riporta.

### 2.2 Rifare tutti i check di §1

Sì, tutti. Anche se sembrano già passati.

### 2.3 Lanciare il riferimento a freddo con il runner A

Il runner A è `docs\porto\dopo_il_riavvio.ps1`. Prende **argomenti posizionali**, in
quest'ordine:

| posizione | significato | valore da usare |
|---:|---|---|
| 1 | `tag` (nome del braccio) | vedi convenzione §9.3 |
| 2 | `SLOT` — capienza cache esperti | `512` è il default dello script |
| 3 | `ZAV` — zavorra VRAM in MiB, diagnostica | **lasciare vuoto: `''`** |
| 4 | `EXTRA` — variabili extra `NOME=VALORE;NOME=VALORE` | `''` se non richiesto |
| 5 | `MAXTOK` — token da generare | `1200` è il default |

**AVVERTENZA CRITICA — il runner A NON è la configurazione della SOTA.** Ha `MASSA=0`,
`ACCEPTMOE=0`, `OVERLAP_BATCH_MAX=2`, `SPEC_CONF_ESENTA_POS0=0`, `CACHE_BOZZA_SLOT=32`,
`SLOT=512`; la SOTA ha `MASSA=2`, `ACCEPTMOE=1` soglia 0,75, `BATCH_MAX=3`,
`ESENTA_POS0=1`, `BOZZA_SLOT=12`, `SLOT=473`. **Sono due banchi diversi.** Il runner A serve
a misurare il riferimento *del runner A*, non a riprodurre la SOTA. Per la SOTA si usa il
runner B (§3).

**COMANDO** (esempio con tag di riferimento a freddo):

```powershell
& 'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\dopo_il_riavvio.ps1' `
  'rif_freddo_b1200_r1_20260816' '512' '' '' '1200'
```

**Che cosa fa da solo, senza che tu faccia niente:**
- attende che nessun processo `llama-*` sia vivo, poi dorme 30 s;
- imposta l'ambiente completo (incluso `LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1` e
  `GGML_SCHED_PROFILO=1`);
- avvia il server sulla **porta 8099**;
- avvia in parallelo un campionatore hardware ogni **3 secondi** che scrive
  `<tag>.hw.csv` (200 campioni = 10 minuti);
- attende `/health` con polling ogni 10 s, fino a 15 minuti;
- manda la richiesta HTTP e salva `<tag>.output.html`;
- **legge prima il log, spegne dopo** (regola non negoziabile: il numero si perde se si
  spegne prima);
- spegne con Ctrl+C vero (`GenerateConsoleCtrlEvent`), non con `Stop-Process`;
- appende la relazione a `D:\ds4_work\llama_run\dopo_il_riavvio.txt`.

**ATTESO** — alla fine, in `D:\ds4_work\llama_run\dopo_il_riavvio.txt`, un blocco che
contiene le righe:

```text
=== rif_freddo_b1200_r1_20260816  HH:MM   (uptime NN min)  SLOT=512  -- ...
  t/s <numero>   p1 <numero>   SHA <12 caratteri>        (j_rif delle 05:10 -> 14,46)
  ...
DOPO_IL_RIAVVIO FINITO
  chiusura: ctrl-c
```

**Controlli obbligatori sull'output:**

| riga | atteso | se no |
|---|---|---|
| `DOPO_IL_RIAVVIO FINITO` | presente | FERMATI: la corsa non è arrivata in fondo |
| `chiusura: ctrl-c` | esattamente così | se dice `RISERVA Stop-Process`, **registra l'anomalia** nel verbale: la pinnata non è stata rilasciata in modo ordinato e il braccio successivo non è confrontabile |
| `*** MORTO ***` | assente | se presente: FERMATI, il server è uscito prima di essere pronto |
| `*** RICHIESTA FALLITA ***` | assente | se presente: FERMATI, non c'è misura |
| `*** CONTESA: piu' di un server durante la corsa, la misura NON vale ***` | assente | se presente: **la misura non vale**, scartala e riparti da §1 |

**SE FALLISCE lo script stesso** (eccezione PowerShell): FERMATI, copia il testo
dell'errore, non modificare lo script.

### 2.4 Nota sul commento in testa al runner A

Le righe 1-26 di `dopo_il_riavvio.ps1` raccontano una regressione post-riavvio Windows
(14,48 → 12,84 t/s dopo KB5123304 + KB5121003 + KB5120708, con banda del letto mappato
invariata a 24,47 GiB/s). **È un commento, non un dato verificato**: l'audit del 16/8 ha
cercato le corse citate (`f5b` delle 05:06, `j_rif` delle 05:10) e **non le ha trovate**.
Non usare quei numeri come riferimento. Il riferimento si legge dal log della corsa che hai
appena fatto.

---

## 3. Lancio del server con una configurazione data (runner B)

Il runner B è il banco dei bracci. È l'unico che parte già nella configurazione della SOTA.

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1
```

### 3.1 Parametri del runner B

| parametro | tipo | default | uso |
|---|---|---|---|
| `-Tag` | stringa | **obbligatorio** | nome del braccio, vedi §9.3 |
| `-MaxTokens` | int | 160 | 160 = banco breve (B160); 1200 = banco lungo (B1200) |
| `-Repetitions` | int | 3 | numero di richieste nello **stesso** processo server |
| `-Extra` | stringa | `''` | variabili d'ambiente `NOME=VALORE` separate da `;` |
| `-PortoHotSnapshot` | bool | `$true` | **per riprodurre la SOTA va messo a `0`** |
| `-PortoHotSequence` | stringa | `''` | ON/OFF per ripetizione, es. `'1,0,1'` |
| `-HardwareProbe` | bool | `$false` | polling `nvidia-smi` a 1 s — vedi §6.5 |
| `-ClockKeeperBlocks` | int | 0 | **VIETATO. Lasciare 0.** Vedi §10 |
| `-ServerPath` | stringa | binario di `D:\llama-overlap` | per un worktree isolato |

### 3.2 Dove si impostano le leve

**Tutte** le leve del runtime sono variabili d'ambiente lette dal server **all'avvio del
processo**. Si impostano **solo** con `-Extra`, mai a mano nella shell.

Configurazione di default già dentro il runner B (è la SOTA; non serve ripeterla in
`-Extra`):

```text
LLAMA_CACHE_BOZZA_SLOT=12          LLAMA_CACHE_ESPERTI_SLOT=473
LLAMA_CACHE_ESPERTI_MASSA=2        LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1
LLAMA_CACHE_ESPERTI_LRU=1          LLAMA_CACHE_ESPERTI_SCUDO=0
LLAMA_CACHE_ESPERTI_FORK=2         LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8
LLAMA_CACHE_ESPERTI_BATCH=8        LLAMA_CACHE_ESPERTI_BATTITO=45
LLAMA_ACCEPTMOE=1                  LLAMA_ACCEPTMOE_SOGLIA=0.75
LLAMA_ACCEPTMOE_ESATTE=1           LLAMA_ACCEPTMOE_COMPATTA=1
LLAMA_SPEC_CONF_ESENTA_POS0=1      LLAMA_SPEC_DRAFT_TOPK=1
PORTO_SPEC_NMAX=2                  PORTO_SPEC_CONF_MIN=0.8
LLAMA_OVERLAP_ASYNC=1              LLAMA_OVERLAP_K=2
LLAMA_OVERLAP_BATCH_MAX=3          LLAMA_OVERLAP_PIN=1
LLAMA_OVERLAP_JOIN_ASYNC=0         LLAMA_MAPPED_IBRIDO=1
LLAMA_MAPPED_IBRIDO_SOGLIA=2       LLAMA_KV_RING=1
LLAMA_KV_RING_VRAM_TOKEN=2048      LLAMA_DSV4_HC_FUSO=5
LLAMA_GRAPH_REUSE_PER_TAGLIA=1     GGML_CUDA_GRAPH_OPT=0
GGML_SCHED_PROFILO=1               LLAMA_VRAM_ZAVORRA=0
```

`LLAMA_SPEC_DRAFT_TOPK=1` **non si tocca mai**: senza, la bozza estrae a sorte fra i primi
dieci e il rumore del banco passa da ±1,6% a ±4%, rendendo ogni verdetto illeggibile.

### 3.3 Comando di lancio — baseline lunga pulita

Questo è il comando canonico da cui partire, copiato dalla fonte autoritativa:

```powershell
& 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' `
  -Tag 'rif_b1200_r1_20260816' `
  -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 `
  -Extra 'LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;GGML_SCHED_PROFILO=0'
```

**`GGML_CUDA_DISABLE_GRAPHS` rimossa (16/8) da questo comando canonico**: non è un interruttore
a valore, è un cancello **a presenza** — vedi §10.4 punto 14. Impostarla, a qualunque valore
compreso `=0`, disabilita i CUDA graph.

### 3.4 Attesa della readiness

Il runner B fa già il polling da solo: `/health` ogni 5 s, fino a 120 tentativi (10 minuti).

**ATTESO** — nel file `<runs>\<tag>.server.log` compare la riga:

```text
srv  llama_server: listening on http://127.0.0.1:8100
```

seguita poco dopo da:

```text
srv  update_slots: all slots are idle
```

Il caricamento richiede **1-2 minuti** (nel log storico la riga `listening` compare a
`1.37` = 1 min 37 s; in una corsa del 16/8 a `1.57`). È normale.

**SE FALLISCE** — il runner solleva `Server non pronto entro 10 minuti.`: FERMATI, riporta
le ultime 40 righe del `.server.log`:

```powershell
Get-Content 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\<tag>.server.log' -Tail 40
```

**SE FALLISCE** con `Un processo llama-cli/llama-server e' gia' attivo.`: torna a §1.1. Non
uccidere il processo.

### 3.5 Divieto di lancio manuale

**Non lanciare `llama-server.exe` a mano.** Un ambiente incompleto produce una corsa che
riesce e che misura un'altra cosa. Si usa sempre uno dei due runner.

---

## 4. VERIFICA D'IDENTITÀ della corsa — obbligatoria, prima di leggere il t/s

Questa sezione esiste perché una giornata intera è stata persa inseguendo una «regressione
del 13-14%» che era una singola variabile d'ambiente mancante. Si eseguono **tutti** i
controlli, sul **log**, non sullo script e non sul manifesto.

Nel resto della sezione `$LOG` è il percorso completo del `.server.log` del braccio:

```powershell
$LOG = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\<tag>.server.log'
```

### 4.1 La riga `cache-esperti` — l'unica identità di configurazione valida

**COMANDO**

```powershell
Select-String -Path $LOG -Pattern '^cache-esperti: \d+ slot' | Select-Object -First 1 -ExpandProperty Line
```

**ATTESO**, per la configurazione SOTA, **carattere per carattere**:

```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
```

**Confronto fra due corse**: le due righe devono essere **identiche carattere per carattere**.

```powershell
$a = (Select-String -Path $LOG_A -Pattern '^cache-esperti: \d+ slot' | Select-Object -First 1).Line
$b = (Select-String -Path $LOG_B -Pattern '^cache-esperti: \d+ slot' | Select-Object -First 1).Line
if ($a -ceq $b) { 'IDENTICHE' } else { "DIVERSE`nA: $a`nB: $b" }
```

**SE DIVERSE**: le due corse **non sono confrontabili**. FERMATI e riporta le due righe.

**Controllo singolo più costoso della storia del progetto** — `sfratto_par`:

```powershell
Select-String -Path $LOG -Pattern 'sfratto_par=([0-9])' | Select-Object -First 1 -ExpandProperty Line
```

Deve dire `sfratto_par=1`. Con `sfratto_par=0` la scelta della vittima è una scansione
sequenziale su **un solo thread GPU** invece di una riduzione a 256 thread: tutte le corse
veloci (14,46-14,77) hanno `sfratto_par=1`, tutte le corse lente di quella giornata (12,79-12,88)
avevano `sfratto_par=0`.

### 4.2 Il manifesto NON è la configurazione — non usarlo mai come prova

Il server stampa righe `server_manif: manifesto/...`. **Non sono la configurazione**:
- **omette** variabili decisive — `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` non compare, e altre
  leve del gruppo overlap/join sono state trovate mancanti;
- **stampa** decine di voci che nessun codice legge;
- può riportare valori non allineati a quel che il runtime ha effettivamente fatto (vedi
  §11, buco n. 1: un log dichiarato «profiler off» ha manifesto `GGML_SCHED_PROFILO=1(E)`).

Il manifesto si legge solo come indizio. La prova sono le righe operative (`cache-esperti:`,
`sched-profilo:`, i contatori finali).

### 4.3 Identità della build

**COMANDO**

```powershell
Select-String -Path $LOG -Pattern 'common_params_print_info: build' | Select-Object -First 1 -ExpandProperty Line
```

**ATTESO** — una riga del tipo:

```text
0.00.029.172 I cmn  common_param: common_params_print_info: build 10093 (3014d3756) with MSVC 19.44.35227.0 for Windows AMD64
```

Riferimenti noti: il log della **SOTA storica** dice `build 95 (963a2cfca)`; il binario
corrente dice `build 10093 (3014d3756)`.

**AVVERTENZA** — il build-info CMake **può essere stantio**. Riportare sempre anche i due
SHA256 dei binari raccolti al passo §1.7. Se cambia uno dei due SHA fra due bracci che si
vogliono confrontare, **non sono confrontabili**: FERMATI.

### 4.4 Strumentazione — pari o niente confronto

Un confronto fra una corsa profilata e una non profilata **non è valido**. Il verdetto va
letto dal log, non dal comando che credi di aver dato.

**COMANDO**

```powershell
$n = (Select-String -Path $LOG -Pattern 'sched-profilo').Count
$m = (Select-String -Path $LOG -Pattern 'GGML_SCHED_PROFILO=[01]\([ED]\)' |
      Select-Object -First 1 -ExpandProperty Line)
Write-Output "righe sched-profilo = $n"
Write-Output "manifesto           = $m"
```

**Come si legge:**

| `righe sched-profilo` | verdetto |
|---:|---|
| `0` | profiler **SPENTO** |
| `> 0` | profiler **ACCESO** |

**Il conteggio delle righe vince sul manifesto.** Se il conteggio è > 0 la sonda ha emesso,
punto.

**Regola di confronto**: due bracci sono confrontabili solo se hanno **lo stesso verdetto**
(entrambi 0, oppure entrambi > 0). Esempio concreto di ciò che **non si fa**: 16,04
(profilato) contro 12,12 — non è un confronto.

Stessa regola per le altre sonde:

```powershell
Select-String -Path $LOG -Pattern 'GGML_CUDA_GRAPH_STATS' | Select-Object -First 1 -ExpandProperty Line
```

`GGML_CUDA_GRAPH_STATS=1` produce un log enorme e va **spento** in ogni banco di
certificazione.

### 4.5 p1 (acceptance della speculazione)

**COMANDO**

```powershell
Select-String -Path $LOG -Pattern 'draft acceptance = ([0-9.]+)' | Select-Object -Last 1 -ExpandProperty Line
```

**ATTESO** — riga del tipo:

```text
slot print_timing: id  0 | task 0 | draft acceptance = 0.90025 (  713 accepted /   792 generated), mean len =  2.47
```

Valori di riferimento: **B1200 → `0.90025` (713/792), mean len 2,47**; **B160 → `0.77670`**.

**SE p1 è diversa dal riferimento**: la corsa ha seguito una **traiettoria diversa**. Non è
un confronto valido di prestazione. Registralo e FERMATI, salvo che il braccio sia stato
esplicitamente dichiarato «cambia p1» dal mandato.

### 4.6 Numero di copie (miss della cache esperti)

**COMANDO**

```powershell
Select-String -Path $LOG -Pattern '^cache-esperti: domanda \d+' | Select-Object -Last 1 -ExpandProperty Line
```

**ATTESO** per il B1200 SOTA, **esattamente**:

```text
cache-esperti: domanda 216737 (colpi 168831 = 77.9%, buchi 47906, miss 22.1%, in ritardo 0 = 0.0% dei prenotati)
```

`buchi 47906` sono le **47.906 copie** citate come firma d'identità.

**ATTENZIONE** — il log contiene **più** righe `domanda ...`: sono istantanee intermedie e
la riga della cache draft. Si prende **l'ultima** (`-Last 1`), che è il totale.

**SE il numero di copie è diverso**: la corsa non ha lo stesso carico. Non confrontabile.

### 4.7 SHA dell'output

**COMANDO** (runner B):

```powershell
$OUT = 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\<tag>.r1.output.txt'
(Get-FileHash $OUT -Algorithm SHA256).Hash
(Get-Item $OUT).Length
(Get-Content $OUT -Raw).Length
```

Confronta con §12. **Se lo SHA differisce ma lunghezza e p1 coincidono**, può essere solo
BOM/CR/newline: **non decidere da solo**, registra i tre valori (SHA, byte, caratteri) e
segnala. La normalizzazione (rimozione BOM, rimozione CR, trim finale) è già stata usata
in passato ed è legittima, ma va fatta e dichiarata, non assunta.

### 4.8 Errori e divergenze

**COMANDO**

```powershell
Select-String -Path $LOG -Pattern 'GGML_ASSERT|CUDA error|invalid index|nan|inf|divergenze' |
    Select-Object -Last 20 -ExpandProperty Line
```

**ATTESO** — solo righe `divergenze: taglia=0 ids=0 out=0 GRIGLIA-corta=0` (tutti zero) e
nient'altro.

**SE compare `GGML_ASSERT` o `CUDA error`**: la corsa è **abortita**. Un crash prima della
riga `eval time` **non è 0 t/s: è nessuna misura**. Non riportare un t/s. FERMATI.

### 4.9 Checklist d'identità da incollare nel verbale

```text
[ ] riga cache-esperti identica al riferimento (carattere per carattere)
[ ] sfratto_par=1
[ ] build <n> (<hash>) + SHA256 exe + SHA256 dll trascritti
[ ] righe sched-profilo: <n>   -> profiler ACCESO/SPENTO
[ ] GGML_CUDA_GRAPH_STATS spento
[ ] p1 = <valore>   (atteso <valore>)
[ ] copie/buchi = <valore>   (atteso <valore>)
[ ] SHA output = <valore>   lunghezza = <n> caratteri
[ ] zero GGML_ASSERT / CUDA error / divergenze
[ ] jprompt.txt SHA verificato al preflight
```

---

## 5. Leve a caldo contro leve che richiedono il riavvio del server

### 5.1 Regola generale, valida oggi

**Tutte** le variabili `LLAMA_*`, `GGML_*`, `PORTO_*` sono lette dal server **all'avvio del
processo**. Cambiare una qualunque di esse richiede **riavviare il server**, cioè rilanciare
il runner con un `-Extra` diverso. Non esiste oggi un modo di cambiarle a caldo.

Lo stesso vale per **tutti** gli argomenti da riga di comando del server (`-c`, `-ub`,
`-ngl`, `-ot`, `-otd`, `-t`, `--spec-draft-*`, `--cache-ram`, `--ctx-checkpoints`,
`--no-mmap`, `--port`).

I documenti indicano come lavoro **futuro** «portare le leve da variabili d'ambiente a un
control block atomico al confine token». Non è disponibile: non cercarlo.

### 5.2 L'unica leva verificata a caldo

`porto_hot_snapshot` — è un campo del **corpo JSON della richiesta**, quindi cambia per
richiesta senza riavviare il server.

- Nel runner B: `-PortoHotSnapshot 0|1` (vale per tutte le ripetizioni) oppure
  `-PortoHotSequence '1,0,1'` (una voce per ripetizione).
- Lo switch per-richiesta è **verificato**: ON 10,35 / OFF 10,11 / ON 10,68 t/s su B160,
  con ritorno esatto allo stesso SHA e alla stessa p1 nelle due accensioni.
- **Per riprodurre la SOTA va messo a 0.** Con snapshot ON la traiettoria cambia (p1 .85316
  invece di .90025) e il testo generato è diverso.

Altri campi del corpo che cambiano a caldo: `max_tokens`, `temperature`, `cache_prompt`.
`temperature` resta **0** in tutti i banchi.

### 5.3 Tabella per leva

| leva | dove si imposta | a caldo? |
|---|---|---|
| `porto_hot_snapshot` | corpo JSON / `-PortoHotSnapshot` / `-PortoHotSequence` | **SÌ**, verificato |
| `max_tokens`, `temperature`, `cache_prompt` | corpo JSON / `-MaxTokens` | **SÌ** |
| `LLAMA_CACHE_ESPERTI_*` (SLOT, MASSA, FORK, SFRATTO_PAR, LRU, SCUDO, BATCH, BATTITO, CALENDARIO_*) | `-Extra` | NO — riavvio |
| `LLAMA_OVERLAP_*` (K, ASYNC, BATCH_MAX, PIN, JOIN_ASYNC) | `-Extra` | NO — riavvio |
| `LLAMA_ACCEPTMOE*`, `LLAMA_SPEC_*`, `PORTO_SPEC_*` | `-Extra` | NO — riavvio |
| `LLAMA_DSV4_*` (HC_FUSO, DECODE_GATE_UP_FUSO, DECODE_EXPERT_REUSE) | `-Extra` | NO — riavvio |
| `LLAMA_KV_RING*`, `LLAMA_MAPPED_IBRIDO*`, `LLAMA_VRAM_*` | `-Extra` | NO — riavvio |
| `GGML_SCHED_PROFILO`, `GGML_CUDA_GRAPH_STATS`, `GGML_CUDA_GRAPH_OPT`, `GGML_CUDA_DISABLE_GRAPHS` | `-Extra` | NO — riavvio |
| `PORTO_HOT_MASK` (bit: target=1, draft=2, stato spec=4, cache esperti=8, no-clear diagnostico=16) | variabile d'ambiente | **[da verificare]** — documentata come variabile, quindi presumibilmente riavvio; nessuna fonte dice che sia per-richiesta |
| `-ServerPath` (binario alternativo) | parametro del runner | NO — è il processo stesso |

---

## 6. Esecuzione di un braccio

### 6.1 Struttura obbligatoria di un braccio

1. Preflight completo di §1.
2. Lancio (§3) con **una sola** leva diversa dal riferimento.
3. Verifica d'identità completa di §4.
4. Lettura del risultato (§7).
5. **QUIETE**: attesa prima del braccio successivo (§6.6).
6. Registrazione nel ledger (§9).

**Una leva per braccio.** Se il mandato ne chiede due, si eseguono due bracci. Non si
combinano mai due leve sperimentali nello stesso braccio.

### 6.2 Quante ripetizioni

| situazione | ripetizioni |
|---|---|
| primo colpo su una leva nuova | **1** (`-Repetitions 1`) |
| il primo colpo è chiaramente peggiore (oltre −4%) | **si scarta il braccio.** Nessuna replica |
| il primo colpo è positivo, oppure entro ±4% | **3 in totale**, e si usa la **MEDIANA** |
| verdetto primario da promuovere | **3 repliche**, mediana, con i controlli di §8 |

**AGGIORNATO (17/8) — vedi §8.7 PROTOCOLLO B-FIRST.** Questa tabella resta valida come
riferimento sul *numero* di repliche, ma l'ordine e il *quando* farle sono ridefiniti da
§8.7: un primo colpo (braccio B) **sotto +3%** non fa più le 3 repliche di questa riga — va
subito in **PARCHEGGIO** (§8.8). Dove le due sezioni non concordano, **vince §8.7**.

Non fare ABBA. Non fare sweep di parametri.

### 6.3 Richiesta HTTP fatta a mano — solo se il runner non è utilizzabile

Normalmente **non serve**: i runner mandano la richiesta da soli. Se un mandato chiede una
richiesta manuale contro un server già in ascolto, si usa **questo** idioma e nessun altro.

```powershell
# ---- richiesta manuale, byte UTF-8: e' l'unica forma corretta su PowerShell 5.1 ----
$porta   = 8100
$prompt  = [IO.File]::ReadAllText('D:\ds4_work\llama_run\jprompt.txt', [Text.Encoding]::UTF8)
$oggetto = @{
    messages           = @(@{ role = 'user'; content = $prompt })
    max_tokens         = 1200
    temperature        = 0
    cache_prompt       = $true
    porto_hot_snapshot = $false
    stream             = $false
}
$corpo = [Text.Encoding]::UTF8.GetBytes(($oggetto | ConvertTo-Json -Compress -Depth 5))
$risposta = Invoke-RestMethod "http://127.0.0.1:$porta/v1/chat/completions" `
    -Method Post -Body $corpo `
    -ContentType 'application/json; charset=utf-8' -TimeoutSec 7200
```

**Perché due cose e non una.** Su PowerShell 5.1, `Invoke-RestMethod -Body <stringa>
-ContentType 'application/json'` serializza il corpo in **ISO-8859-1**, non in UTF-8. Il
danno non è un errore: è una traslitterazione silenziosa. `｜` (U+FF5C) diventa `|`, `—`
diventa `-`, `▁ ∞ → α π` diventano `?`. Il marcatore del template DeepSeek e il confine
SentencePiece diventano ASCII che si legge bene e **si tokenizza in un altro modo**: la
corsa riesce, su un prompt diverso, senza dire niente. Servono **entrambe** le correzioni:
l'array di byte **e** `charset=utf-8`.

`jprompt.txt` è puramente ASCII (§1.8) e quindi immune: è l'unico motivo per cui il runner
B, che manda una stringa, produce misure valide. Se il prompt cambia, quella immunità
sparisce.

### 6.4 Registrazione dello stato hardware durante la corsa

**Sempre**, per ogni braccio, deve esistere una registrazione di clock e potenza. La lezione
del 16/8 è che il banco girava a **780 MHz / 50-56 W** contro i **1950 MHz / 95-100 W**
storici e nessuno l'aveva guardato come primo sospetto.

Come si ottiene, per runner:

| runner | file prodotto | intervallo | va usato? |
|---|---|---|---|
| A (`dopo_il_riavvio.ps1`) | `D:\ds4_work\llama_run\<tag>.hw.csv` | 3 s, automatico | **SÌ, sempre** |
| B (`run_porto_hot.ps1`) con `-HardwareProbe $true` | `<runs>\<tag>.r<N>.hw.csv` | 1 s | **solo in probe dedicato**, mai nel braccio di certificazione |
| B senza `-HardwareProbe` | nessuno | — | serve lo spot-check di §6.5 |

**Il campionamento a 3 s è dentro il regime della SOTA**: i tre run del record
(`mass2_copyall_stablelane_t473_d12_b1/b2/b3`) hanno tutti il loro `.hw.csv` a 3 s e hanno
fatto 16,04 / 16,11 / 16,07. Il campionamento a **1 s** del runner B è invece invasivo:
misurato, porta un B160 da 12,34 a 10,40 t/s.

**AGGIORNATO (17/8) — vedi §6.8 TELEMETRIA STANDARD.** La riga della tabella sopra "B senza
`-HardwareProbe` → nessuno → serve lo spot-check di §6.5" non è più il default: ora si usa
sempre `sample_hw.ps1` a 0,5 Hz (§6.8), su entrambi i runner. Lo spot-check di §6.5 resta un
ripiego per diagnostica rapida, non più il caso normale nei bracci di certificazione.

### 6.5 Spot-check hardware quando non c'è polling continuo

Quando si usa il runner B **senza** `-HardwareProbe` (cioè in ogni braccio di
certificazione), si prende un campione singolo **subito prima** e **subito dopo** la corsa,
più al massimo **tre** campioni durante, distanziati:

```powershell
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$g = (& nvidia-smi --query-gpu=clocks.sm,clocks.mem,power.draw,utilization.gpu,memory.used,memory.free,clocks_throttle_reasons.active --format=csv,noheader,nounits) -join ','
Write-Output "$stamp,$g"
```

Trascrivere le righe nel verbale. Se il clock SM sotto carico è **< 1500 MHz**, scrivilo
accanto al numero e **non promuovere la misura**: registrala come diagnostica.

**VIETATO** correggere il clock. Nessun keeper, nessun pannello NVIDIA, nessun reset. Vedi
§10.

### 6.6 QUIETE fra bracci

Fra la fine di un braccio (server uscito) e l'inizio del successivo: **300 secondi**, con
polling attivo, non con una sleep cieca.

```powershell
$fine = (Get-Date).AddSeconds(300)
while ((Get-Date) -lt $fine) {
    $p   = @(Get-Process -Name llama-server, llama-cli -ErrorAction SilentlyContinue).Count
    $vr  = (& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
    $ram = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
    $res = [math]::Round(($fine - (Get-Date)).TotalSeconds, 0)
    Write-Output "quiete: restano $res s | processi=$p vram_usata=$vr MiB ram=$ram GB"
    Start-Sleep -Seconds 15
}
```

**Condizioni per considerare finita la quiete** (tutte e tre):
- processi llama = 0;
- `memory.used` < 1200 MiB;
- RAM libera >= 28 GB.

**SE dopo i 300 s una condizione non è soddisfatta**: continuare il polling fino a 15 minuti
totali. Se ancora no: FERMATI e riporta.

Nota onesta: le fonti sono in disaccordo sulla necessità dei 300 s (vedi §11, buco n. 5).
Finché il disaccordo non è risolto, **si applicano i 300 s**: costano tempo, non correttezza.

### 6.7 Divieto di lavoro concorrente durante una misura

Durante un braccio, sulla stessa macchina:
- **niente** altri agenti che leggono file grandi (i sorgenti CUDA e i transcript sono
  decine di MB: riempiono la standby list, che è la stessa risorsa che serve al modello);
- **niente** build, niente `git` pesanti, niente copie di file;
- **niente** secondo server llama.

Il runner A rileva la contesa da solo e stampa
`*** CONTESA: piu' di un server durante la corsa, la misura NON vale ***`. Se compare, la
misura si butta.

### 6.8 TELEMETRIA STANDARD — sostituisce la restrizione al polling nei banchi finali (dettato utente, 17/8)

**SOSTITUISCE**, come default, la restrizione di §6.4 (Runner B con `-HardwareProbe`: "solo
in probe dedicato, mai nel braccio di certificazione") e la logica di §6.5 (spot-check invece
di polling continuo). Quella restrizione nasceva dal costo del **sampling ad alta frequenza**
(1 s, misurato in §6.4: B160 da 12,34 a 10,40 t/s) nell'era anomala del 15-16/8 — non dal
polling in sé. La SOTA storica certificata (§12.1,
`mass2_copyall_stablelane_t473_d12_b1/b2/b3`, 16,04/16,11/16,07 t/s) girava **con** `.hw.csv`
attivo a **3 s** (Runner A, automatico). Un campionatore leggero e uniforme applicato **su
entrambi i lati di ogni confronto** è quindi la strumentazione storicamente fedele, non una
deviazione da essa.

**Regola**: ogni braccio (Runner A o B, certificazione o diagnostica) **DEVE** avere
`<tag>.hw.csv` e `<tag>.cpu.csv`, campionati a **0,5 Hz** (ogni 2 secondi), prodotti da:

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\sample_hw.ps1 -Tag <tag> -OutDir <cartella artefatti del runner in uso>
```

Si avvia **prima** della richiesta (dopo che `/health` risponde), e si ferma da solo alla
fine del processo `llama-server`, oppure prima creando il file sentinella
`<OutDir>\<tag>.stop`. Resta **vietato** il sampling **oltre 1 Hz**: è il costo misurato in
§6.4 a essere vietato, non il polling in sé — lo script rifiuta da solo un `-IntervalSeconds`
sotto 1.

**Nel ledger** (§9.2), oltre ai campi già obbligatori, riportare da `<tag>.hw.csv`: VRAM di
picco e VRAM media, regime di clock (minimo e mediana durante il decode — mediana con la
formula corretta di §7.4, non quella difettosa), potenza media; da `<tag>.cpu.csv`: CPU%
media.

**Cancello 2 di §8.2 aggiornato**: vedi nota lì.

---

## 7. Lettura del risultato

### 7.1 Quali file esistono, per runner

**Runner B** (`run_porto_hot.ps1`), in
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\`:

| file | contenuto |
|---|---|
| `<tag>.summary.json` | **il risultato**: un oggetto per ripetizione |
| `<tag>.server.log` | log del server: identità, contatori, profilo, errori |
| `<tag>.server.out` | stdout del server (di norma vuoto: 0 byte è normale) |
| `<tag>.r<N>.output.txt` | il testo generato dalla ripetizione N |
| `<tag>.r<N>.response.json` | la risposta HTTP completa |
| `<tag>.r<N>.hw.csv` | telemetria a 1 s, solo con `-HardwareProbe` |

**Runner A** (`dopo_il_riavvio.ps1`), in `D:\ds4_work\llama_run\`:

| file | contenuto |
|---|---|
| `dopo_il_riavvio.txt` | relazione **appesa** (non sovrascritta) con t/s, p1, SHA, hardware |
| `<tag>.server.log` | log del server |
| `<tag>.output.html` | il testo generato |
| `<tag>.hw.csv` | telemetria a 3 s |

**Runner prefill** (`sota100k_ctx150k.ps1`, in
`C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\`), in
`D:\ds4_work\llama_run\`: produce `<nome>.summary.txt`. **Attenzione: è codificato UTF-16LE.**
Va letto con `Get-Content` (che lo gestisce), **non** con strumenti che assumono UTF-8: con
quelli il testo appare con uno spazio fra ogni carattere.

### 7.2 Campi del `.summary.json` e loro unità

```json
{
  "tag": "current_clean_noprobes_b1200_r1_20260816",
  "max_tokens": 1200,
  "repetitions": 1,
  "results": [
    {
      "repetition": 1,
      "wall_ms": 102460.6,
      "eval_tps": "12.12",
      "prompt_tps": "20.31",
      "p1": "0.90025",
      "finish_reason": "length",
      "sha256": "3BAC3069DD0E47D38F09CD6A0608E6B6F47B95CDE64D1CE79A79B30E3F4CA31A",
      "content_chars": 3572,
      "prompt_tokens": 68,
      "completion_tokens": 1200
    }
  ]
}
```

| campo | unità / significato |
|---|---|
| `wall_ms` | millisecondi di parete della richiesta HTTP, **misurati dal runner** |
| `eval_tps` | **token/s del decode** — è il numero primario. Stringa, va convertita |
| `prompt_tps` | token/s del prefill |
| `p1` | acceptance della bozza, frazione 0-1 |
| `finish_reason` | deve essere `length` |
| `sha256` | hash del file `<tag>.r<N>.output.txt` |
| `content_chars` | caratteri del testo generato |
| `completion_tokens` | deve coincidere con `max_tokens` |

**`eval_tps` è ricopiato dal log**, con la regola «ultimo match». Verificalo sul log:

```powershell
Select-String -Path $LOG -Pattern '\|\s+eval time =' | Select-Object -Last 1 -ExpandProperty Line
```

**ATTESO** — riga del tipo:

```text
slot print_timing: id  0 | task 0 |        eval time =   74804.71 ms /  1200 tokens (   62.34 ms per token,    16.04 tokens per second)
```

Da questa riga si leggono: **ms totali**, **token**, **ms/token**, **t/s**. Se
`.summary.json` e log non concordano, **vince il log**: riportalo e segnala.

### 7.3 Lettura dell'`.hw.csv`

Formato del runner A (con intestazione):

```text
t,sm_mhz,mem_mhz,power_w,util,pcie_gen,pcie_width,throttle,vram_usata,vram_libera,cpu_perf,server_vivi,ram_libera_gb
150,1950, 7301, 100.34, 64, 4, 16, 0x0000000000000000, 11841, 275,120,1,5.8
```

Formato del runner B con `-HardwareProbe` (**senza** intestazione), colonne in ordine:
`timestamp, pstate, clocks.sm, clocks.memory, power.draw, utilization.gpu, clocks_event_reasons.active`:

```text
2026/08/16 01:55:52.423, P2, 780, 7301, 55.29, 79, 0x0000000000000001
```

**Estrazione delle mediane sotto carico** (runner A):

```powershell
$hw  = Import-Csv 'D:\ds4_work\llama_run\<tag>.hw.csv'
$car = @($hw | Where-Object { $_.util -match '^[0-9]+$' -and [int]$_.util -gt 50 })
$sm  = @($car | ForEach-Object { [int]$_.sm_mhz }   | Sort-Object)
$pw  = @($car | ForEach-Object { [double]$_.power_w } | Sort-Object)
Write-Output ("campioni util>50 : " + $car.Count)
Write-Output ("SM mediano       : " + $sm[[math]::Floor(($sm.Count-1)/2)] + " MHz (min " + $sm[0] + ", max " + $sm[-1] + ")")
Write-Output ("potenza mediana  : " + $pw[[math]::Floor(($pw.Count-1)/2)] + " W")
Write-Output ("throttle finale  : " + $car[-1].throttle)
Write-Output ("server vivi max  : " + (($car | ForEach-Object { [int]$_.server_vivi } | Measure-Object -Maximum).Maximum))
Write-Output ("RAM libera min   : " + (($car | ForEach-Object { [double]$_.ram_libera_gb } | Measure-Object -Minimum).Minimum) + " GB")
```

**Riferimenti**: nel regime SOTA, SM **1950 MHz**, memoria **7301 MHz**, potenza **95-100 W**,
PCIe **Gen4 x16**, `throttle` = `0x0000000000000000` sotto carico. Nel regime anomalo del
16/8: SM ~**780 MHz**, potenza ~**50-56 W**, PCIe ancora Gen4 x16, nessun throttle termico.

`server vivi max` deve essere **1**. Se è 2, la misura non vale.

**BUG CORRETTO (16/8)** — anche qui le formule precedenti, `$sm[[int]($sm.Count/2)]` e
`$pw[[int]($pw.Count/2)]`, sbagliavano per il banker's rounding di `[int]` (stessa causa
spiegata in §7.4). Portata misurata: l'indice cade **un passo sopra il centro** per i
conteggi dispari 3, 7, 11, … (`Count ≡ 3 mod 4`); con **3 campioni** quel passo è proprio
il **MASSIMO**; per 5, 9, 13, … era per caso corretto. Su telemetrie lunghe (centinaia di
campioni) l'errore storico è quindi lieve; il caso velenoso sono i conteggi piccoli.

### 7.4 Come si calcola la mediana di 3 ripetizioni

La mediana di tre numeri è **il valore centrale dopo l'ordinamento**, non la media.

```powershell
$s = Get-Content 'C:\...\work\runs\<tag>.summary.json' -Raw | ConvertFrom-Json
$v = @($s.results | ForEach-Object { [double]$_.eval_tps } | Sort-Object)
Write-Output ("valori ordinati : " + ($v -join ' / '))
Write-Output ("MEDIANA         : " + $v[[math]::Floor(($v.Count-1)/2)])
Write-Output ("media           : " + [math]::Round(($v | Measure-Object -Average).Average, 4))
Write-Output ("spread max-min  : " + [math]::Round((($v[-1] - $v[0]) / $v[0]) * 100, 2) + " %")
```

Se le tre ripetizioni sono in file `.summary.json` diversi (un file per ripetizione),
raccogli i tre `eval_tps` a mano nella stessa lista e applica la stessa formula.

**BUG CORRETTO (16/8)** — la formula precedente, `$v[[int]($v.Count/2)]`, su un array di
**3** elementi restituiva il **MASSIMO**, non il centro. Causa: PowerShell 5.1 arrotonda
`[int]` con banker's rounding (round-half-to-even): con `Count=3`, `Count/2` fa `1.5`, e
`[int](1.5) = 2` (arrotonda al pari), non `1`. Quindi `$v[2]` = il massimo dell'array
ordinato, non `$v[1]` = il centro. Verificato con test locale: `[int](1.5) = 2`,
`[int](0.5) = 0`, `[int](2.5) = 2`; su `$v = @(13.44, 13.49, 13.50)` la vecchia formula dava
`13.5` (il massimo), quella nuova dà `13.49` (il centro vero). La forma corretta,
`[math]::Floor(($v.Count-1)/2)`, vale per **conteggi dispari**, il caso standard del
progetto (§6.2: 1 o 3 ripetizioni).

**AVVERTENZA** — le mediane storiche di questo progetto calcolate con la vecchia formula
possono essere in realtà il **massimo** della tripletta, non il valore centrale. Non è stata
fatta una verifica retroattiva di tutte le mediane storiche del progetto: se un mandato si
appoggia a un valore «mediana» registrato prima del 16/8, ricalcolare dai tre `eval_tps`
grezzi prima di usarlo come riferimento.

**Il verdetto primario è la MEDIANA.** La media si riporta accanto, come informazione. Se
`spread max-min` supera il **5%**, scrivilo esplicitamente nel verbale: il braccio è
rumoroso e il verdetto è debole.

---

## 8. Validità del verdetto

Un numero diventa un verdetto **solo** se passa tutti i cancelli seguenti. Se anche uno solo
non passa, il numero si registra come **diagnostico**, mai come promozione.

### 8.1 Cancello 1 — identità

Tutta la checklist §4.9 spuntata su **entrambi** i lati del confronto.

### 8.2 Cancello 2 — pari strumentazione

`righe sched-profilo` con lo stesso verdetto (entrambi 0 o entrambi > 0) sui due lati.
`GGML_CUDA_GRAPH_STATS` spento su entrambi. Stesso stato di polling hardware su entrambi
(o entrambi senza `-HardwareProbe`, o entrambi con). Stesso `porto_hot_snapshot`.

**AGGIORNATO (17/8) — vedi §6.8 TELEMETRIA STANDARD.** "Stesso stato di polling hardware" ora
significa di norma **entrambi con `sample_hw.ps1` attivo a 0,5 Hz**, non più "entrambi senza
`-HardwareProbe`". Il polling interno del Runner B (`-HardwareProbe`, 1 Hz) resta comunque
vietato in certificazione (§6.4): non è quello che questo cancello richiede.

### 8.3 Cancello 3 — soglia del 3%

La deriva del banco è **2-3%**.

```powershell
$a = 12.12   # braccio
$b = 12.34   # riferimento
$d = [math]::Round((($a - $b) / $b) * 100, 2)
Write-Output "delta = $d %"
if ([math]::Abs($d) -lt 3) { Write-Output 'NON DISTINGUE: dentro la deriva di banco' }
else { Write-Output 'DIFFERENZA APPREZZABILE (verificare gli altri cancelli)' }
```

| |delta| | conclusione da scrivere |
|---|---|
| < 3% | «**non distingue**: dentro la deriva di banco (2-3%)». Non è né un guadagno né una perdita |
| 3-4% | differenza sospetta: servono **3 repliche per lato** e si giudica sulle mediane |
| > 4% e negativo | braccio **peggiore**: si scarta senza repliche |
| > 4% e positivo | candidato: **3 repliche**, mediana, e si rilegge tutta §8 |

**Non si promuove mai un +1% o un +1,47%**: sono dentro la deriva.

**AGGIORNATO (17/8) — vedi §8.7 PROTOCOLLO B-FIRST.** Il flusso operativo ora è: braccio B
(1 replica) contro il riferimento; **sotto +3%** → PARCHEGGIO diretto (§8.8), niente braccio
di controllo; **sopra +3%** → 3 repliche di B, poi il braccio di controllo A rifatto nella
stessa sessione (mai un riferimento stantio). La tabella qui sopra resta valida per leggere
un **singolo** delta; il *seguito* (3-4% vs >4%, quando fare A) è ridefinito da §8.7.

### 8.4 Cancello 4 — il riferimento si legge dal log

Il valore di riferimento con cui confronti deve venire da un `.server.log` o
`.summary.json` **di questa sessione o di una sessione identificata**, di cui scrivi il
percorso assoluto. **Mai** da:
- un commento in testa a uno script (es. il `-> 14,46` stampato dal runner A);
- una nota in un handoff;
- questo runbook (§12 elenca firme d'identità, che servono a **verificare**, non a
  sostituire una misura).

### 8.5 Cancello 5 — quando rimisurare a freddo

Rimisurare il riferimento a macchina fredda:
- **a inizio di ogni sessione**, prima di qualunque braccio;
- dopo ogni **riavvio** di Windows o aggiornamento (KB);
- dopo ogni cambio di **binario** (SHA256 di `llama-server.exe` o `ggml-cuda.dll` diverso);
- se sono passate **più di 3 ore** dall'ultima misura del riferimento;
- se sono stati eseguiti **più di 3 bracci** nella sessione;
- se un braccio ha chiuso con `RISERVA Stop-Process`, o con `CONTESA`, o con `MORTO`.

### 8.6 Correttezza, non solo velocità

Lo SHA da solo non basta. Per ogni candidato registrare:
`t/s`, `ms/token`, `p1` e accepted/generated, SHA e lunghezza dell'output, `finish_reason`,
copie/buchi, divergenze, ID invalidi, NaN/Inf, assert, stato profilo/sonde dichiarato
esplicitamente, clock/potenza.

### 8.7 PROTOCOLLO B-FIRST — sostituisce l'ordine dei bracci precedente (dettato utente, 17/8)

**Disambiguazione preliminare, obbligatoria prima di usare questa sezione**: qui "braccio A"
e "braccio B" indicano il **ruolo nel confronto** (A = controllo/leva spenta, B = leva
accesa), **non** i Runner A/B di §2/§3. Il braccio B si lancia con il Runner B (§3, con la
leva impostata via `-Extra`); il braccio A di questo protocollo è la **stessa configurazione
di riferimento**, anch'essa lanciata con il Runner B (leva spenta/di default) — **non** il
Runner A cold-start di §2, che resta riservato al primo braccio di sessione.

Questo protocollo **sostituisce** l'ordine implicito in §6.1 punto 2 e la tabella di §6.2, e
ridefinisce il flusso di §8.3 (vedi le note aggiunte lì). Dove questa sezione e quelle
contraddicono, **vince questa**.

**Il flusso:**

1. **Ogni banco parte SEMPRE dal braccio B** (leva accesa), **1 replica**, confrontato contro
   il riferimento noto (letto dal log, §8.4 — mai da un documento).
2. **B sotto +3%** (cancello di §8.3) → **niente braccio di controllo A**. La leva va in
   **PARCHEGGIO** (§8.8) con il suo unico numero (1 replica), e si passa alla leva successiva.
   Non si fanno le 3 repliche che la vecchia tabella di §6.2 avrebbe richiesto per un colpo
   "entro ±4%".
3. **B sopra +3%** → si completano le **3 repliche di B** (stesso processo, §8.9), mediana.
   **Poi**, e solo poi, il **braccio di controllo A**, con la baseline **rifatta nella stessa
   sessione** — mai un riferimento stantio letto da un log di un'altra sessione (§8.4/§8.5).
   Il verdetto è **B vs A della stessa sessione**, non B contro uno storico: elimina i falsi
   positivi da deriva del banco (2-3%, §8.3) che un confronto contro un riferimento vecchio
   non può distinguere da un guadagno vero.
4. **Leve commutabili a caldo per-richiesta** (es. `porto_hot_snapshot`, §5.2): si fanno **4
   bracci con UN solo caricamento del server** — 3 richieste con B acceso, poi 1 con A (leva
   spenta), stesso processo, via `-PortoHotSequence` o il campo JSON pertinente. Resta
   **B-first**: le 3 di B prima, la 1 di A dopo, mai intercalate.
   **Leve lette a init del processo** (la maggioranza, tabella di §5.3): niente hot-switch
   possibile — si riavvia per B (3 repliche), poi si riavvia per A. **Vale comunque B-first**:
   B prima, A dopo, mai il contrario.
   **Prima di ogni banco**, verificare nel sorgente **il momento** in cui la leva viene letta
   (init vs per-chiamata/richiesta) con un `grep` mirato sul nome esatto della variabile —
   **non un'assunzione dal nome**. Se il grep non chiarisce, trattarla come "a init" (il caso
   più conservativo, richiede il riavvio fra B e A).

### 8.8 PARCHEGGIO LEVE

Elenco **distinto dalle famiglie falsificate** (§10.4 punto 9: quelle sono chiuse e non si
riaprono senza segnalare prima). Una leva qui **resta candidata**: non è stata giudicata
dannosa, solo insufficiente **da sola** sotto la soglia del 3% del suo primo colpo B. Prima di
riprovarla da sola, verificare se è già stata **composta** con un'altra leva parcheggiata o
promossa: se sì, il numero da battere è quello della composizione, non quello isolato qui
sotto.

| leva | risultato B (1 replica) | note |
|---|---|---|
| gate+up fuso | +1,47% | stesso numero già citato in §8.3 come esempio di "non promuovere mai" |
| `JOIN_ASYNC` | copertura parziale ~20-25% | non basta da sola; vedi anche il banco F2-B (17/8, ledger del giorno) |
| L2-A, kernel `GET_ROWS` k-quant | — | parcheggiata, nessun numero registrato qui ancora |

Aggiungere una riga per ogni nuova leva parcheggiata, stesso schema: leva, risultato B, note.

### 8.9 Protocollo repliche-in-processo — SOSPESA in attesa di decisione dell'utente sulla genealogia delle repliche (17/8)

**SOSPESA.** La prescrizione precedente (un processo, `-Repetitions 3`) non è più operativa.
Al suo posto, questa nota tecnica:

> Le repliche nello stesso processo con `porto_hot_snapshot=0` **NON** sono corse
> indipendenti: la residenza della cache esperti sopravvive fra richieste
> (`run_porto_hot.ps1:37-38`; precedente §5.2) — misurano il **REGIME CALDO STAZIONARIO**.
> Sono legittime **SOLO** come genealogia dichiarata a parte (più veloce ~3× e più simile
> alla produzione), **MAI** mescolabili con banchi a processi-separati nello stesso
> confronto. Fino alla decisione dell'utente (freddo vs caldo), il protocollo operativo
> resta: **una replica = un processo**. Il rifiuto motivato dell'esecutore del 17/8
> (LEDGER_17, nota metodologica) è la prassi corretta.

**Conseguenza per §8.7 punto 3**: dove quel punto dice "stesso processo, §8.9" per le 3
repliche di B, si legga **sospeso allo stesso modo** — fino alla decisione dell'utente valgono
lì pure tre processi separati (una replica = un processo), non uno.

---

## 9. Postflight e ledger

### 9.1 Postflight — subito dopo che il server è uscito

```powershell
$ram = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
$gpu = (& nvidia-smi --query-gpu=memory.used,memory.free,clocks.sm,power.draw --format=csv,noheader,nounits)
$np  = @(Get-Process -Name llama-server, llama-cli -ErrorAction SilentlyContinue).Count
Write-Output "POSTFLIGHT ram_libera=$ram GB | gpu=$gpu | processi_llama=$np"
```

**ATTESO** — `processi_llama=0`, `memory.used` < 1200 MiB, `ram_libera` >= 28 GB.

**SE la RAM libera non risale** entro 15 minuti di polling, o la VRAM resta occupata:
registralo come **anomalia** nel verbale e FERMATI. Il braccio successivo non è
confrontabile.

### 9.2 Che cosa si registra nel ledger

**Ogni** output prodotto va catalogato con il suo tag. Nessun run resta fuori, nemmeno
quelli falliti (un crash è un'informazione).

**REGOLA UTENTE — ripetuta più volte, finora mai applicata: ogni voce di ledger registra
TUTTE le variabili usate dal run — l'ambiente completo effettivo, comprese quelle ai valori
di default — non solo quelle cambiate rispetto al riferimento. Una variabile non registrata
è una variabile che prima o poi verrà persa (è già successo due volte: SFRATTO_PAR il 12/8,
GGML_SCHED_PROFILO il 16/8).**

Riga di ledger, campi obbligatori:

```text
tag              =
data/ora         =
runner           = A (dopo_il_riavvio) | B (run_porto_hot) | prefill (sota100k_ctx150k)
banco            = B160 | B1200 | prefill | fixture64
ripetizioni      =
leva variata     = <una sola, oppure "nessuna (riferimento)">
comando esatto   = <la riga completa, copiabile>
eval t/s         = <per ripetizione> -> MEDIANA
prompt t/s       =
ms/token         =
p1               = <valore> (accepted/generated)
SHA output       = <64 hex>   lunghezza = <n> caratteri
finish_reason    =
copie/buchi      =
riga cache-esperti = <copiata integralmente>
profiler         = ACCESO/SPENTO (righe sched-profilo = <n>)
graph stats      = ACCESO/SPENTO
snapshot         = porto_hot_snapshot = 0|1
SHA llama-server =
SHA ggml-cuda    =
build            = build <n> (<hash>)
clock SM mediano = <MHz>   potenza mediana = <W>   throttle = <maschera>
server vivi max  =   RAM libera min = <GB>
uptime a inizio  = <min>
esito            = PROMOSSO | RESPINTO | DIAGNOSTICO | NESSUNA MISURA (crash)
percorsi file    = <log, summary, output, hw.csv — tutti assoluti>
anomalie         = <chiusura, contesa, clock basso, ...>
```

### 9.3 Convenzione del tag

```text
<famiglia>_<variante>_b<MAXTOKENS>_r<RIPETIZIONE>_<AAAAMMGG>
```

Esempi reali, da imitare:

```text
current_clean_noprobes_b1200_r1_20260816
hotmask15_natural_full_b1200_r2_20260816
sota_k2_no_hot_snapshot_b1200_r1_20260816
macro_v2_gateup_no_dedup_native_zero_diag_k0_q8_b160_r1_20260816
bisect893_topk_profile_b160_r1_20260816
```

Regole: solo `[A-Za-z0-9_]`, niente spazi, niente accenti, niente punti (il punto separa le
estensioni). Il tag non si riusa mai: sovrascriverebbe gli artefatti precedenti.

### 9.4 Dove va scritto

Nei ledger del progetto, sotto `docs\porto\`. Un braccio non registrato è un braccio perso:
è già successo che una corsa completa sia stata buttata perché il numero non era stato letto
prima della pulizia.

---

## 10. Stop pulito, ripristino e DIVIETI ASSOLUTI

### 10.1 Stop pulito

Entrambi i runner spengono da soli, **dopo** aver letto il log, con un Ctrl+C vero
(`AttachConsole` + `GenerateConsoleCtrlEvent`), perché il server ha un gestore di segnale e
non espone una rotta HTTP di arresto.

**Non intervenire mentre spengono.** L'operazione può richiedere fino a 60 secondi.

Se il runner riporta `chiusura: ctrl-c -> RISERVA Stop-Process`: **registra l'anomalia**.
Significa che il Ctrl+C non ha funzionato e il processo è stato terminato: il contesto CUDA
non è stato distrutto ordinatamente. Dopo un evento simile, prima del braccio successivo,
rifai §1 per intero e considera il riferimento da rimisurare.

### 10.2 Se il server resta appeso

```powershell
for ($i = 0; $i -lt 24; $i++) {
    $p = @(Get-Process -Name llama-server -ErrorAction SilentlyContinue)
    Write-Output "attesa uscita $i : processi=$($p.Count)"
    if ($p.Count -eq 0) { break }
    Start-Sleep -Seconds 5
}
```

Se dopo 2 minuti è ancora vivo: **FERMATI e riporta il PID**. Non usare `Stop-Process`. Sarà
l'utente a decidere.

### 10.3 Ripristino

Dopo una sessione: nessun ripristino è previsto. **Non si cancellano artefatti**, non si
«fa pulizia» nelle cartelle di run, non si toccano i worktree.

### 10.4 DIVIETI ASSOLUTI (riepilogo)

1. **Mai rilanciare il braccio prefill full con placement misto `blk.*=CPU`.** Ha reso il PC
   completamente inutilizzabile e produce il guasto `GET_ROWS_Q invalid index:
   src0='markov_w1.weight' ... i01=-1 ne01=129280`, aperto e non riparato. Vale per tutte le
   forme con wildcard `blk\..*=CPU`, con o senza packetizer.
2. **Mai usare il clock-keeper.** `-ClockKeeperBlocks` resta **0**. Misurato: peggiora il
   B160 da 12,34 a 10,14 t/s. Il boost artificiale ruba risorse e non raccoglie throughput.
3. **Mai cambiare la configurazione della GPU.** Niente `nvidia-smi -rgc` / `-lgc` / `-pl`,
   niente pannello NVIDIA, niente profili 3D, niente piani di risparmio energetico. Il reset
   clock è già stato negato per privilegi insufficienti: **non aggirarlo**.
4. **Mai `git reset --hard`, `git checkout --`, `git clean`** in nessun albero. `D:\llama-overlap`
   contiene il codice della SOTA in file **mai committati** (29 modificati e oltre 100 nuovi,
   ultimo commit del 14/8): perderlo significa perdere la SOTA e la possibilità stessa di
   bisecare la regressione. Vale anche per `ds4-upstream-cuda-measure`, `ds4-p4a` e gli altri
   worktree sporchi.
5. **Mai uccidere il server della UI sulla porta 8000.**
6. **Mai due server llama insieme.** Se il mandato prevede più configurazioni, si eseguono in
   sequenza con la QUIETE di §6.6.
7. **Mai `Stop-Process -Force`** su un server llama, se non come riserva già dentro i runner,
   e in quel caso registrando l'anomalia.
8. **Mai attese passive.** Ogni attesa è polling con un check che si stampa.
9. **Mai riaprire famiglie già chiuse**: K adattivo/frazionario, FIDDLER, prefetch locale
   (current/next-layer, cieco, oracle, CURA, SCUDO, PF_TOP, W2/W4), exact-demand DMA in tutte
   e tre le forme, RCI mapped, whole-FFN, shared-overlap, banca B multi-stream e single-stream,
   VRES a K=2, TILE GPU-driven, CPU FFN super-op, dedup/owner-mate dell'expert-reuse.
   Se un mandato chiede una di queste, **FERMATI e segnala** prima di eseguire.
10. **Mai attivare `LLAMA_DSV4_DECODE_EXPERT_REUSE` nel banco normale.** Resta a 0.
11. **Mai usare WSL.** Tutto è Windows nativo.
12. **Mai fare commit o push** senza richiesta esplicita.
13. **Mai far girare agenti che leggono file grandi durante una misura.**
14. **`GGML_CUDA_DISABLE_GRAPHS` è un cancello A PRESENZA: non va MAI impostata, nemmeno a
    0, se si vogliono i grafi accesi.** Verificato nel codice
    (`ggml-cuda/common.cuh:1266`): `getenv("GGML_CUDA_DISABLE_GRAPHS") != nullptr` — controlla
    se la variabile **esiste** nell'ambiente, non il suo valore. Impostarla a `=0` la
    disabilita esattamente come `=1`. Verifica obbligatoria nel manifesto del log: la riga
    deve dire `<spento>(D)`. Questa trappola ha nascosto **~2,5 t/s per due giorni**: tutti i
    banchi del 15-16/8 giravano senza grafi.

---

## 11. BUCHI DA COLMARE

Elenco di ciò che le fonti **non** documentano, o documentano in modo contraddittorio. Non
inventare risposte: se un mandato dipende da uno di questi punti, FERMATI e segnala.

1. **Lo stato del profiler nelle baseline «pulite» non torna.** I due valori promossi come
   «prima baseline pulita, profiler off con override esplicito» risultano, dai loro stessi
   log, **profilati**:

   | tag | righe `sched-profilo` | manifesto | conclusione dal log |
   |---|---:|---|---|
   | `current_clean_noprobes_b1200_r1_20260816` (12,12 t/s) | **41** | `GGML_SCHED_PROFILO=1(E)` | profiler **ACCESO** |
   | `current_clean_noprobes_b160_r1_20260816` (12,34 t/s) | **8** | `GGML_SCHED_PROFILO=1(E)` | profiler **ACCESO** |
   | `sota_k2_no_hot_snapshot_b1200_r1_20260816` (10,54 t/s) | **0** | `GGML_SCHED_PROFILO=0(E)` | profiler **SPENTO** |
   | `sota_k2_no_hot_profile_diag_b1200_r1_20260816` (10,53 t/s) | **41** | `GGML_SCHED_PROFILO=1(E)` | profiler **ACCESO** |

   (verificato leggendo i quattro `.server.log` in
   `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\`
   con `Select-String -Pattern 'sched-profilo'` e `-Pattern 'GGML_SCHED_PROFILO=[01]\([ED]\)'`).

   Di conseguenza: (a) la «ritirata» del verdetto on/off 10,54/10,53 non è supportata dai
   log — quei due bracci differivano davvero per la sonda; (b) il salto 10,53 → 12,12 non è
   attribuibile allo spegnimento della sonda, perché la sonda risulta accesa in entrambi.
   **Nessun confronto che coinvolga 12,12 o 12,34 va usato finché il punto non è risolto.**

2. **La differenza 16,0733 → 12,12 resta non spiegata.** È localizzata (+18,238 ms/grafo
   dentro `graph_compute_async`, il 90,8% del delta) ma non causata. Il runbook non contiene
   una procedura per chiuderla perché non esiste.

3. **`PORTO_HOT_MASK` non è documentata come per-richiesta o per-processo.** I bit sono noti
   (target=1, draft=2, stato spec=4, cache esperti=8, no-clear diagnostico=16); il momento di
   lettura no. [da verificare]

4. **`DS4_LOCK_FILE` e la porta 8014 appartengono a un altro runtime.** `DS4_LOCK_FILE` è una
   variabile di `ds4.c` (famiglia `ds4_server.exe`, funzione `ds4_acquire_instance_lock`), non
   di `llama-server.exe`. Il banco Porto usa le porte 8099 / 8100 / 8110 e **non ha un lock
   file documentato**: la mutua esclusione è ottenuta dal controllo `Get-Process` del runner B,
   che solleva un'eccezione se trova un llama vivo. [da verificare] se esista un lock per
   `llama-server`.

5. **La QUIETE di 300 s è contestata.** La regola nasce da un regime con il modello in mmap; con
   `--no-mmap` una campagna ABBA a 60 s di distanza ha dato uno spread di 0,7%. Nessuna fonte
   ha ritirato formalmente i 300 s. Questo runbook li impone (§6.6) come scelta prudente.
   [da verificare]

6. **Il costo della sonda `GGML_SCHED_PROFILO` non è stabile.** Registrato a 0% l'11/8, a 3,6%
   il 12/8, a 0,01 t/s (10,54 vs 10,53) il 16/8. Non esiste un fattore di correzione: per
   questo l'unica regola praticabile è **pari strumentazione**, non «sottrai il costo».

7. **Il polling hardware: quanto costa davvero, non è chiuso.** Misurato 12,34 → 10,40 su B160
   con polling a 1 s; il polling a 3 s è dentro il regime della SOTA. Nessuna misura isola il
   costo dell'intervallo di campionamento. [da verificare]

8. **Nessuna procedura documentata per la QUIETE dopo un crash.** Le fonti dicono solo che dopo
   un crash non si rilancia identico.

9. **Il microprobe del clock non ha lasciato reperto.** L'affermazione «il driver raggiunge
   1935-1950 MHz e 124-126 W su carico compute» è centrale ma l'unico output su disco di
   `cuda_clock_probe.exe` è `launches=2155 value=0`. Non c'è un CSV da confrontare.

10. **Il ceiling DMA ~19,453 t/s e il ceiling del riuso esperti (22,84% / 7,7167%) sono
    aritmetica dichiarata**, senza file di output salvato. Non usarli come cancello.

11. **La regressione post-riavvio 14,48 → 12,84 t/s e la banda 24,47 GiB/s** esistono solo nel
    commento in testa a `dopo_il_riavvio.ps1`; le corse citate non sono state trovate.

12. **Non esiste una procedura documentata di build** dentro un runbook operativo. Il comando
    esiste (vcvars64 + cmake --build, target `llama-server`, `--parallel 8`) ma questo runbook
    **non autorizza a compilare**: la build cambia gli SHA dei binari e invalida ogni confronto
    con lo storico.

13. **Il cancello SHA fra CPU e GPU vale solo con speculazione OFF e K=0.** La residenza decide
    chi calcola su CPU e CPU/GPU arrotondano diversamente. Nessuna fonte documenta la procedura
    esatta per costruire quel banco (quali variabili, quale prompt). [da verificare]

14. **`dopo_il_riavvio.ps1` non produce un `.summary.*`.** Il suo risultato vive solo nella
    relazione appesa a `dopo_il_riavvio.txt` e nel `.server.log`. Non c'è un formato strutturato
    da cui leggere il t/s in modo programmatico.

15. **Non è documentato che cosa fare se `p1` coincide ma lo SHA no.** La normalizzazione
    (BOM/CR/newline) è stata usata caso per caso, senza uno script canonico.

16. **Un terzo albero di run potrebbe esistere.** L'audit segnala `D:\llama-overlap` come hub di
    altri 15 worktree fratelli mai auditati. Se un tag non si trova nei due alberi noti, non
    concludere che non esista: segnala.

---

## 12. FIRME D'IDENTITÀ NOTE

Valori di riferimento correnti. **Servono a verificare, non a sostituire una misura**
(§8.4).

### 12.1 Decode — SOTA storica certificata (non riprodotta oggi)

```text
media 3 run B1200 : 16,0733 t/s   (16,04 / 16,11 / 16,07)
B1, log           : eval time = 74804.71 ms / 1200 tokens (62.34 ms per token, 16.04 t/s)
prefill del B1    : prompt eval time = 3116.27 ms / 68 tokens (45.83 ms per token, 21.82 t/s)
p1                : .90025  (713 accepted / 792 generated), mean len 2,47
copie (buchi)     : 47.906
contatori cache   : domanda 216737 (colpi 168831 = 77.9%, buchi 47906, miss 22.1%)
SHA output        : 4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D
build             : build 95 (963a2cfca) with MSVC 19.44.35227.0
profiler          : ACCESO (righe sched-profilo presenti)
telemetria        : SM 1950 MHz, mem 7301 MHz, 95-100 W, PCIe Gen4 x16, throttle 0x0
configurazione    : MASSA2 copy-all stable lanes, 473 slot da 6,75 MiB (3194 MiB VRAM),
                    draft 12, K=2, NMAX2, conf .8, AcceptMoE .75 compact,
                    FORK=2 + FORK_BLOCCHI=8, lru=1, scudo=0, sfratto_par=1, dma=0
riga cache-esperti: cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06
                    + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2,
                    peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1,
                    dma=0, dma_strato=0
artefatti         : D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.server.log
                    D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.output.html
                    D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.hw.csv
                    (idem per _b2 e _b3)
```

### 12.2 Decode — baseline corrente B1200

```text
tag        : current_clean_noprobes_b1200_r1_20260816
eval       : 12,12 t/s          wall richiesta 102.460,6 ms
prompt     : 20,31 t/s
p1         : .90025
SHA output : 3BAC3069DD0E47D38F09CD6A0608E6B6F47B95CDE64D1CE79A79B30E3F4CA31A
caratteri  : 3.572 (content_chars) — conteggio reale senza BOM 3.574, con BOM 3.575
finish     : length
contatori  : domanda 216737, colpi 168831 (77,9%), buchi 47906  [identici alla SOTA]
build      : build 10093 (3014d3756)
profiler   : ATTENZIONE — dichiarato spento, ma il log ha 41 righe sched-profilo. Vedi §11.1
replica R2 : 12,22 t/s (tag hotmask15_natural_full_b1200_r2_20260816, stesso p1 e stesso SHA)
percorso   : C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\
```

### 12.3 Decode — reference breve B160

```text
tag        : current_clean_noprobes_b160_r1_20260816
eval       : 12,34 t/s          wall 16.197,9 ms
prompt     : 21,53 t/s
p1         : .77670
SHA output : 991AF3E11ACEC20A7DCBB01317A7D8F4312B94592EF596721ECB4B1842899C1B
caratteri  : 83
finish     : length
profiler   : ATTENZIONE — dichiarato spento, log con 8 righe sched-profilo. Vedi §11.1
NOTA       : NON confrontabile con il B1200 (p1 diversa, ammortamento diverso)
```

### 12.4 Decode — altri punti noti (per riconoscimento, non per confronto)

```text
10,54 t/s  sota_k2_no_hot_snapshot_b1200_r1_20260816   p1 .90025, profiler SPENTO (0 righe)
10,53 t/s  sota_k2_no_hot_profile_diag_b1200_r1_20260816  p1 .90025, profiler ACCESO
 9,87 t/s  sota_k2_current_codegen_b1200_r1_20260816   p1 .85316, snapshot ON, testo diverso
10,38 t/s  macro no-dedup B160 K0, bit-esatto, SHA EE1E260F..., p1 .80583
10,14 t/s  B160 con clock keeper -> VIETATO (peggiora rispetto a 12,34)
 7,97 t/s  bisect893_topk_profile_b160_r1_20260816, SHA 013755F5..., p1 .84848
           -> traiettoria diversa dal controllo: NON e' un punto di bisect valido
```

### 12.5 Prefill — base lunga corretta

```text
prefill medio : 116,1985 t/s   (110,7005 / 111,0928 / 126,8021)  — MEDIANA 111,09
decode assoc. : 7,9492 t/s
p1            : .61702
SHA output    : D556C4C30669464AB3E05C7F3037348EC063DEFA5558ADD51C0BAE731B722C31
caratteri     : 266     finish: length
carico        : prompt 101.597 + completion 64, ctx 150.000, B/UB 2048, FASI2
spread        : 13,86% fra le repliche -> usare la mediana, non scegliere R3
artefatti     : D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_resident.summary.txt
                (+ _r2, _r3)  — codifica UTF-16LE
NOTA          : 275,506 t/s e' una misura target-only, NON una SOTA end-to-end
```

### 12.6 Il prompt del banco

```text
file      : D:\ds4_work\llama_run\jprompt.txt
byte      : 252     codifica: ASCII puro (immune al difetto ISO-8859-1)
SHA256    : C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9
token     : 68 (prompt_tokens riportati dal server)
confine   : il batching naturale del prompt da 68 token e' 64+4 (ubatch 64).
            Un batching forzato 67+1 cambia la traiettoria dal primo carattere.
```

### 12.7 Cancello di recupero proposto (non ancora accettato dall'utente)

```text
calc altri  <= 5 ms/grafo
testo       identico allo storico
p1          .90025
copie       47.906
t/s         >= 15,8
poi         3 repliche
```

Questo cancello è **proposto**, non deliberato. Non applicarlo come se fosse deciso: se un
mandato lo richiama, eseguilo; se un mandato lo contraddice, segui il mandato e registra la
discrepanza.
