# LEDGER 16 AGOSTO

## truth_clean_b1200_r1_20260816 — tentativo baseline B1200 "verità" a profiler spento — RESPINTO AL CANCELLO

```text
tag              = truth_clean_b1200_r1_20260816
data/ora         = 2026-08-16 16:15:54 (lancio) -> 16:19:40 (server.log concluso) ; verifica 16:20-16:22
runner           = B (run_porto_hot.ps1)
banco            = B1200
ripetizioni      = 1 (R2/R3 NON eseguite: il mandato impone l'arresto immediato al fallimento del cancello 3.a)
leva variata     = nessuna (tentativo di riferimento "verità" con profiler e sonde dichiarate spente)
comando esatto   = & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag 'truth_clean_b1200_r1_20260816' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'LLAMA_SCHED_PROFILO=0;GGML_CUDA_GRAPH_STATS=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;GGML_CUDA_DISABLE_GRAPHS=0'
eval t/s         = R1: 12,82   (nessuna mediana: R2/R3 non eseguite)
prompt t/s       = 21,19
ms/token         = 78,00   (wall_ms richiesta = 96.887,1)
p1               = 0.90025 (713 accepted / 792 generated), mean len 2,47  -- COINCIDE con l'atteso del mandato
SHA output       = 4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D   lunghezza = 3572 caratteri (content_chars)
finish_reason    = length
copie/buchi      = domanda 216737 (colpi 168831 = 77.9%, buchi 47906, miss 22.1%, in ritardo 0 = 0.0%)  -- COINCIDE con l'atteso (216.737 / 168.831 / 47.906)
riga cache-esperti = cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
profiler         = ACCESO -- CANCELLO FALLITO (righe sched-profilo = 41, atteso 0)
manifesto        = GGML_SCHED_PROFILO=1(E)  (il default resta acceso nonostante -Extra contenesse "LLAMA_SCHED_PROFILO=0", vedi anomalie)
graph stats      = SPENTO (manifesto: GGML_CUDA_GRAPH_STATS=0(E))
snapshot         = porto_hot_snapshot = 0 (false, confermato in summary.json)
SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330
build            = build 10093 (3014d3756) with MSVC 19.44.35227.0
clock SM mediano = non misurato (nvidia-smi limitato per mandato a una sola invocazione per l'intero banco, gia' usata in preflight)
potenza mediana  = non misurata (stesso motivo)
server vivi max  = 1   RAM libera min durante la corsa = non campionata (stesso motivo)
uptime a inizio  = 2393,3 min
esito            = RESPINTO AL CANCELLO DI STRUMENTAZIONE (punto 3.a del mandato) -- NON e' un verdetto di prestazione, non promosso ne' respinto nel merito del t/s
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean_b1200_r1_20260816.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean_b1200_r1_20260816.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean_b1200_r1_20260816.r1.output.txt
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean_b1200_r1_20260816.r1.response.json
anomalie         = (1) Il comando prescritto dal mandato imposta "LLAMA_SCHED_PROFILO=0" dentro -Extra. Il runbook (RUNBOOK_BANCO_DS4.md SS3.2 config. default, SS3.3 comando canonico, SS4.4 verifica, SS11 buco n.1, SS12.2/12.4 firme) chiama SEMPRE questa leva "GGML_SCHED_PROFILO", mai "LLAMA_SCHED_PROFILO". Il manifesto di questa corsa conferma che la variabile effettivamente attiva e' GGML_SCHED_PROFILO=1(E) = il default non sovrascritto. Il comando e' stato eseguito ESATTAMENTE come scritto nel mandato, senza correzioni di iniziativa (come da regola "non improvvisare" del runbook e "ESATTAMENTE questo comando" del mandato). Esito: l'override non ha raggiunto la leva che il codice legge, il profiler e' rimasto acceso, 41 righe sched-profilo -- stesso numero e stesso manifesto del caso "current_clean_noprobes_b1200_r1_20260816" gia' documentato come trappola in RUNBOOK SS11.1.
                    (2) Lo SHA output ottenuto (4FDCFADF...) NON coincide con lo SHA "atteso" scritto nel mandato (3BAC3069...), ma coincide CARATTERE PER CARATTERE con lo SHA della SOTA storica certificata riportato in RUNBOOK_BANCO_DS4.md SS12.1 (16,0733 t/s media, build 95/963a2cfca). Lunghezza (3572 content_chars) e p1 (.90025) sono identici sotto entrambi gli SHA (3BAC3069 e 4FDCFADF): per la regola SS4.7/SS8.6 del runbook questa discrepanza NON viene normalizzata o decisa da questo esecutore -- viene solo registrata come fatto grezzo, con tutti e tre i valori (SHA, lunghezza byte del file, lunghezza caratteri) a disposizione di chi deve giudicare.
                    (3) R2 e R3 non eseguite per rispetto letterale del mandato ("Se >0: FERMA TUTTO, nessuna altra ripetizione").
                    (4) Nessun errore GGML_ASSERT / CUDA error / divergenze diverse da zero. Chiusura server pulita (ctrl-c, non RISERVA Stop-Process). Postflight pulito: processi_llama=0, RAM libera 88,4 GB.
```

Stato macchina a fine banco (2026-08-16 16:21:44): processi_llama = 0, RAM libera = 88,4 GB. Nessuna ulteriore invocazione di nvidia-smi oltre quella unica di preflight (2026-08-16, memory.used 650 MiB / memory.free 11466 MiB / SM 210 MHz / PCIe width 16 / throttle 0x0000000000000001), come da divieto assoluto del mandato. Nessun commit git eseguito.

---

## truth_clean2_b1200_r1/r2/r3_20260816 — baseline B1200 "verità" a profiler spento, CORRETTA — PROMOSSA

Il coordinatore ha segnalato che l'errore del cancello precedente era nel proprio mandato: il nome
corretto della leva è `GGML_SCHED_PROFILO` (come dice il runbook ovunque), non `LLAMA_SCHED_PROFILO`.
Confermato dai fatti (vedi sezione precedente). Banco rilanciato con `-Extra` che include
`GGML_SCHED_PROFILO=0` (oltre a `LLAMA_SCHED_PROFILO=0`, lasciata perché innocua).

**Deviazione dal mandato originale, esplicitamente autorizzata dal coordinatore durante l'esecuzione**:
niente QUIETE fissa di 300 s fra le repliche. Sostituita da verifica di stato (processi llama = 0,
chiusura `ctrl-c` non `RISERVA Stop-Process`, RAM libera) subito dopo ogni replica, poi lancio
immediato della successiva. La QUIETE di 300 s prima di R1 (la prima del banco) è stata comunque
eseguita per intero. §11 buco n.5 del runbook già segnalava questa regola come contestata/da
verificare; qui la deviazione è tracciata esplicitamente, non assunta.

```text
tag R1           = truth_clean2_b1200_r1_20260816
tag R2           = truth_clean2_b1200_r2_20260816
tag R3           = truth_clean2_b1200_r3_20260816
data/ora         = R1 lancio 16:31:14 -> R2 lancio 16:36:48 -> R3 lancio 16:40:58 -> fine 16:45:02
runner           = B (run_porto_hot.ps1)
banco            = B1200
ripetizioni      = 3 (R1, R2, R3), tutte passano il cancello
leva variata     = nessuna (riferimento "verità" con profiler e sonde davvero spente questa volta)
comando esatto (R1, R2 e R3 identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'LLAMA_SCHED_PROFILO=0;GGML_CUDA_GRAPH_STATS=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;GGML_CUDA_DISABLE_GRAPHS=0;GGML_SCHED_PROFILO=0'

riga cache-esperti (identica sulle tre repliche, verbatim) =
  cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0

                    R1              R2              R3
righe sched-profilo 0               0               0            -- CANCELLO PASSATO su tutte e tre (atteso 0)
manifesto profiler  GGML_SCHED_PROFILO=0(E)  GGML_SCHED_PROFILO=0(E)  GGML_SCHED_PROFILO=0(E)
graph stats         GGML_CUDA_GRAPH_STATS=0(E)  (idem)          (idem)       -- spento su tutte
eval t/s            13,49           13,44           13,50
ms/token            74,14           74,40           74,06
prompt t/s          21,59           20,91           21,91
wall_ms             92.203,5        92.615,9        92.064,7
p1                  0.90025 (713/792)  0.90025 (713/792)  0.90025 (713/792)   -- COINCIDE con l'atteso su tutte e tre
copie/buchi         216737/168831/47906  216737/168831/47906  216737/168831/47906  -- COINCIDE con l'atteso su tutte e tre
finish_reason       length          length          length
SHA output          4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D  (le tre repliche, identico)
content_chars       3572            3572            3572
divergenze          taglia=0 ids=0 out=0 GRIGLIA-corta=0 su tutte e tre, nessun GGML_ASSERT/CUDA error
chiusura            ctrl-c          ctrl-c          ctrl-c       -- pulita su tutte e tre

MEDIANA eval t/s     = 13,49    (valori ordinati 13,44 / 13,49 / 13,50 -- vedi ATTENZIONE FORMULA sotto)
media eval t/s       = 13,4767
spread max-min       = 0,45 %   -- ben sotto la soglia del 5% (banco NON rumoroso)
MEDIANA ms/token      = 74,14   (valori ordinati 74,06 / 74,14 / 74,40)

SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (invariato dal banco precedente, stessa sessione)
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (invariato)
build            = build 10093 (3014d3756) with MSVC 19.44.35227.0
snapshot         = porto_hot_snapshot = 0 su tutte e tre repliche
server vivi max  = 1 per replica
esito            = PROMOSSO come baseline B1200 "verità" a profiler spento: 3/3 repliche passano
                    il cancello completo (sched-profilo=0, p1, copie, SHA). MEDIANA = 13,49 t/s.
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean2_b1200_r{1,2,3}_20260816.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean2_b1200_r{1,2,3}_20260816.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_clean2_b1200_r{1,2,3}_20260816.r1.output.txt
```

### ATTENZIONE — bug verificato nella formula "mediana" del runbook §7.4

La formula canonica del runbook,
```powershell
$v[[int]($v.Count/2)]
```
per un array **di 3 elementi** dà un risultato SBAGLIATO: **non** l'elemento centrale, ma l'**ultimo
(il massimo)**. Causa verificata empiricamente su questa macchina (PowerShell 5.1): il cast `[int]`
su un valore `.5` esatto usa l'arrotondamento bancario (round-half-to-even), non il troncamento.
Con `Count=3`, `Count/2 = 1.5`, e `[int](1.5) = 2` (arrotonda al pari), non `1`. Quindi
`$v[[int]($v.Count/2)]` restituisce `$v[2]` = il massimo dell'array ordinato, non `$v[1]` = il centro.

Verificato con un test diretto su questa sessione:
```text
[int](1.5) = 2   [int](0.5) = 0   [int](2.5) = 2
$v = @(13.44, 13.49, 13.50)
$v[[int]($v.Count/2)]  = 13.5    (formula del runbook -- SBAGLIATA per N=3)
$v[1]                  = 13.49   (elemento centrale vero -- la mediana corretta)
```
Per **qualunque** tripletta di repliche (`N=3` è il caso standard del progetto, vedi runbook §6.2),
`Count/2` fa sempre `1.5`, quindi la formula del runbook restituisce **sempre** il massimo, mai il
centro. La MEDIANA riportata sopra (13,49) è il valore centrale vero, calcolato correttamente
(`$v[1]` su un array ordinato a 3 elementi), non il valore che la formula del runbook avrebbe dato
(13,50). La differenza qui è piccola (0,01 t/s, dentro lo spread di 0,45%) e non cambia alcun
verdetto di questo banco, ma la formula va corretta ovunque sia usata per triplette: se altre
mediane storiche del progetto sono state calcolate con questa stessa formula su gruppi di 3 valori,
quei numeri sono sistematicamente il MASSIMO della tripletta, non la mediana. Non ho verificato
mediane storiche: fuori perimetro di questo mandato, segnalato separatamente.

### Verifica indipendente dell'equivalenza SHA (richiesta dal coordinatore, verificata su disco)

Confronto byte-per-byte fra `current_clean_noprobes_b1200_r1_20260816.r1.output.txt` (SHA
`3BAC3069DD0E47D38F09CD6A0608E6B6F47B95CDE64D1CE79A79B30E3F4CA31A`, 3575 byte, nessun BOM) e
`truth_clean_b1200_r1_20260816.r1.output.txt` (SHA `4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D`,
3578 byte, con BOM UTF-8 `EF BB BF`). Dopo rimozione del BOM e di tutti i caratteri CR: **stesso
SHA256** (`B122297452096BF19EDAFFEC174239BB9A7278AC913F994A6E24B9705D46A135`), stessa lunghezza
(3574 byte). Confermato indipendentemente: sono lo stesso testo, differiscono solo per BOM/CR come
previsto da runbook §4.7/§8.6.

### Nota richiesta dal coordinatore sul run precedente (profiler ACCESO)

`truth_clean_b1200_r1_20260816` (sezione precedente di questo ledger, 41 righe sched-profilo,
profiler ACCESO) vale **12,82 t/s** a parità semantica perfetta (p1 .90025, copie 47.906, SHA
4FDCFADF... = SOTA storica). È la misura **«profiler ON»**, confrontabile per pari strumentazione
con lo storico **16,04 t/s profiler ON** (RUNBOOK §12.1): delta = (12,82-16,04)/16,04 =
**-20,07 % ≈ -20,1%**. Riportato come dato grezzo su richiesta esplicita del coordinatore; non
è un confronto fra questo banco (profiler OFF, 13,49 t/s) e lo storico (profiler ON, 16,04 t/s) --
quel confronto violerebbe la regola di pari strumentazione (runbook §4.4/§8.2) e non viene fatto qui.

Stato macchina a fine banco (2026-08-16 16:45:23): processi_llama = 0, RAM libera = 88,6 GB.
Nessuna invocazione di nvidia-smi in questa seconda parte del banco (unica invocazione dell'intera
sessione resta quella di preflight, 16:15 circa). Chiusura pulita su tutte e tre le repliche
(`ctrl-c`, mai `RISERVA Stop-Process`). Nessun commit git eseguito.

---

## truth_graphs_b1200_r1/r2/r3_20260816 — CUDA graph riaccesi: buco trovato — PROMOSSA

Il coordinatore ha segnalato una seconda variabile mancante: `GGML_CUDA_DISABLE_GRAPHS=0`, presente
in `-Extra` in ogni banco della serata precedente (compreso `truth_clean2`), **disabilitava** i
CUDA graph. Causa: il cancello nel codice è sulla **presenza** della variabile d'ambiente, non sul
suo valore.

**Verificato indipendentemente da questo esecutore**, leggendo `D:\llama-overlap\ggml\src\ggml-cuda\common.cuh`,
righe 1265-1268:
```cpp
bool is_enabled() const {
    static const bool disable_cuda_graphs_due_to_env = (getenv("GGML_CUDA_DISABLE_GRAPHS") != nullptr);
    return !(disable_due_to_gpu_arch || disable_cuda_graphs_due_to_env);
}
```
`getenv(...) != nullptr` è vero indipendentemente dal valore della stringa puntata: impostare
`GGML_CUDA_DISABLE_GRAPHS=0` rende comunque `getenv` non-null, quindi `disable_cuda_graphs_due_to_env
= true` e i grafi restano disattivati. Confermata la causa, non solo assunta.

**Preflight aggiuntivo eseguito** (richiesto dal coordinatore, un altro agente stava compilando su
`D:\llama-subtract`): trovati 9 processi di compilazione attivi (cmake, ninja, 7x nvcc.exe, avviati
17:42-17:46). Atteso con polling attivo la loro sparizione: terminati dopo un solo check
(~30 s, riscontrato alle 17:48:02). Verificato stato pulito (0 processi compilazione, 0 processi
llama, RAM 87,6 GB) prima di procedere.

**Deviazione dal mandato originale, confermata dal coordinatore per questo banco**: nessuna QUIETE
fissa fra le repliche, sostituita da verifica di stato (processi=0, chiusura ctrl-c, RAM libera) e
lancio immediato, come già per `truth_clean2`.

**Nota sulla stringa `-Extra` fornita**: rispetto a `truth_clean2`, il testo del mandato descriveva
l'intenzione come "comando identico, rimuovi SOLO `GGML_CUDA_DISABLE_GRAPHS`", ma la stringa
`-Extra` fornita letteralmente omette anche `GGML_CUDA_GRAPH_STATS=0`. Eseguito il comando
esattamente come scritto (nessuna correzione di iniziativa). Verificato dal manifesto che questo non
ha creato un problema: `GGML_CUDA_GRAPH_STATS=0(D)` — il valore di default per questa variabile è
già spento anche senza impostarla esplicitamente, quindi la regola "va spento in ogni banco di
certificazione" (runbook §4.4) resta rispettata.

```text
tag R1           = truth_graphs_b1200_r1_20260816
tag R2           = truth_graphs_b1200_r2_20260816
tag R3           = truth_graphs_b1200_r3_20260816
data/ora         = R1 lancio 17:48:24 -> R2 lancio 17:53:05 -> R3 lancio 17:57:05 -> fine 18:01:13
runner           = B (run_porto_hot.ps1)
banco            = B1200
ripetizioni      = 3 (R1, R2, R3), tutte passano il cancello
leva variata     = GGML_CUDA_DISABLE_GRAPHS rimossa completamente da -Extra (non 0, ASSENTE)
comando esatto (R1, R2 e R3 identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'GGML_SCHED_PROFILO=0;LLAMA_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'

riga cache-esperti (identica sulle tre repliche, verbatim) =
  cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0

                    R1              R2              R3
GGML_CUDA_DISABLE_GRAPHS  <spento>(D)     <spento>(D)     <spento>(D)   -- CANCELLO PASSATO su tutte e tre (atteso <spento>(D), non 0(E))
righe sched-profilo 0               0               0            -- CANCELLO PASSATO su tutte e tre (atteso 0)
eval t/s            15,30           15,84           15,71
ms/token            65,38           63,13           63,67
prompt t/s          16,29           21,25           19,11
wall_ms             82.755          79.037,2        80.045,9
p1                  0.90025 (713/792)  0.90025 (713/792)  0.90025 (713/792)   -- COINCIDE con l'atteso su tutte e tre
copie/buchi         216737/168831/47906  216737/168831/47906  216737/168831/47906  -- COINCIDE con l'atteso su tutte e tre
finish_reason       length          length          length
SHA output          4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D  (le tre repliche, identico)
content_chars       3572            3572            3572
divergenze          taglia=0 ids=0 out=0 GRIGLIA-corta=0 su tutte e tre, nessun GGML_ASSERT/CUDA error
chiusura            ctrl-c          ctrl-c          ctrl-c       -- pulita su tutte e tre

MEDIANA eval t/s     = 15,71    (valori ordinati 15,30 / 15,71 / 15,84 -- elemento centrale vero, v[1])
media eval t/s       = 15,6167
spread max-min       = 3,53 %   -- sotto la soglia del 5% (non "rumoroso" per lo standard del runbook, ma piu' alto del banco precedente 0,45%)
MEDIANA ms/token      = 63,67   (valori ordinati 63,13 / 63,67 / 65,38)

build            = build 10093 (3014d3756) with MSVC 19.44.35227.0  (invariato)
SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (invariato)
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (invariato)
snapshot         = porto_hot_snapshot = 0 su tutte e tre repliche
server vivi max  = 1 per replica
esito            = PROMOSSO: 3/3 repliche passano il cancello completo (grafi accesi via manifesto,
                    sched-profilo=0, p1, copie, SHA). MEDIANA = 15,71 t/s.
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_graphs_b1200_r{1,2,3}_20260816.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_graphs_b1200_r{1,2,3}_20260816.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\truth_graphs_b1200_r{1,2,3}_20260816.r1.output.txt
```

### ENV COMPLETO (tutte le variabili, non solo quelle cambiate -- nuova regola del coordinatore)

Catturato integralmente da `truth_graphs_b1200_r1_20260816.server.log` (tutte le righe
`server_manif:`; R2 e R3 identiche, stesso comando):

```text
server_manif: manifesto: E=ambiente D=difetto; LLAMA_MANIFESTO=1(D)
server_manif: manifesto/cache: LLAMA_CACHE_BOZZA_BATTITO=60(D) LLAMA_CACHE_BOZZA_SLOT=12(E) LLAMA_CACHE_ESPERTI_BATCH=8(E) LLAMA_CACHE_ESPERTI_BATTITO=45(E) LLAMA_CACHE_ESPERTI_CODA_MAX=0(E) LLAMA_CACHE_ESPERTI_CURA=0(E) LLAMA_CACHE_ESPERTI_FORK=2(E) LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8(E) LLAMA_CACHE_ESPERTI_LRU=1(E) LLAMA_CACHE_ESPERTI_MASSA=2(E) LLAMA_CACHE_ESPERTI_PF_TUTTI=1(D) LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO=0(E) LLAMA_CACHE_ESPERTI_SCUDO=0(E) LLAMA_CACHE_ESPERTI_SLOT=473(E) LLAMA_CACHE_ESPERTI_SPIN=256(D) LLAMA_CACHE_ESPERTI_W=0(E) LLAMA_CACHE_ORACOLO=<spento>(D)
server_manif: manifesto/spec: LLAMA_ACCEPTMOE=1(E) LLAMA_ACCEPTMOE_BATCH_MAX=8(D) LLAMA_ACCEPTMOE_COMPATTA=1(E) LLAMA_ACCEPTMOE_ESATTE=1(E) LLAMA_ACCEPTMOE_SOGLIA=0.75(E) LLAMA_ACCEPTMOE_SPIA=0(D) LLAMA_CKPT_CRONO=0(E) LLAMA_SPEC_CONF_ESENTA_POS0=1(E) LLAMA_SPEC_DRAFT_TOPK=1(E)
server_manif: manifesto/compute: LLAMA_DSV4_HC_FUSO=5(E) LLAMA_MAPPED_IBRIDO=1(E) LLAMA_MAPPED_IBRIDO_SOGLIA=2(E) LLAMA_OVERLAP_ASYNC=1(E) LLAMA_OVERLAP_CERCA_CPU=0(D) LLAMA_OVERLAP_BATCH_MAX=3(E) LLAMA_OVERLAP_GRIGLIA_VARIABILE=0(E) LLAMA_OVERLAP_K=2(E) LLAMA_OVERLAP_PIN=1(E) LLAMA_OVERLAP_SPIN=2000000(D) LLAMA_OVERLAP_VERIFICA=0(D)
server_manif: manifesto/kv: LLAMA_KV_POSMIN_VERO=0(D) LLAMA_KV_RING=1(E) LLAMA_KV_RING_VRAM_TOKEN=2048(E) LLAMA_KV_RING_VRAM_TRACE=0(D) LLAMA_KV_ROLLBACK_MARGINE=4(D) LLAMA_KV_ROLLBACK_PARZIALE=1(E) LLAMA_KV_ROLLBACK_SOLO_ANELLO=0(E)
server_manif: manifesto/orfane: LLAMA_RING=0(D) LLAMA_RING_BATTITO=60(D) LLAMA_RING_PROFONDITA=380(D)
server_manif: manifesto/vram: LLAMA_VRAM_A_FASI=0(E) LLAMA_VRAM_A_FASI_CALDO=0(D) LLAMA_VRAM_A_FASI_MARGINE=0(D) LLAMA_VRAM_A_FASI_MIN=0(D) LLAMA_VRAM_A_FASI_SLOT=0(D) LLAMA_VRAM_A_FASI_SLOT_MAX=1024(D) LLAMA_VRAM_A_FASI_UB=64(D) LLAMA_VRAM_ZAVORRA=0(E)
server_manif: manifesto/orfane: LLAMA_REAP=0(D) LLAMA_REAP_AMMISSIONE=1.0(D) LLAMA_REAP_DECADIMENTO=1.0(D) LLAMA_REAP_DECADIMENTO_BUSSATE=0.90(D) LLAMA_REAP_DUMP=<spento>(D) LLAMA_REAP_ISTERESI=1(D) LLAMA_REAP_LOCK=0(D) LLAMA_REAP_MARGINE=1.25(D) LLAMA_REAP_MAX_SCAMBI=64(D) LLAMA_REAP_PERIODO=12900(D) LLAMA_REAP_PESO=ripida(D) LLAMA_REAP_PREFETCH=0(D) LLAMA_REAP_PROF=0(D) LLAMA_REAP_SOGLIA=3(D) LLAMA_REAP_THREADS=8(D) LLAMA_REAP_TOPK=2400(D)
server_manif: manifesto/vram: LLAMA_REAP_WS_MIN_GB=0(D)
server_manif: manifesto/diag: LLAMA_DEBUG_DUMP=<spento>(D) LLAMA_DEBUG_FILTER=<tutto>(D) LLAMA_DFLASH_SINKHORN_ITERS=<gguf>(D) LLAMA_DSV4_SINKHORN_ITERS=<gguf>(D) LLAMA_STREAM_GC=60(D) LLAMA_STREAM_MAX_MB=4(D) LLAMA_STREAM_TTL=300(D)
server_manif: manifesto/cache: LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1(E) LLAMA_CACHE_ESPERTI_DMA=0(D) LLAMA_CACHE_ESPERTI_DOMANDA_DMA=0(D) LLAMA_CACHE_ESPERTI_FORK_ESATTO=0(D) LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=0(D) LLAMA_CACHE_ESPERTI_FORK_STADI=0(D) LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA=0(E) LLAMA_CACHE_ESPERTI_FORK_PRIORITA=0(D) LLAMA_CACHE_ESPERTI_FORK_SERIALE=0(D) LLAMA_CACHE_ESPERTI_FATE=0(D)
server_manif: manifesto/compute: LLAMA_OVERLAP_JOIN_ASYNC=0(E) LLAMA_OVERLAP_FINESTRA=0(D) LLAMA_DSV4_INDEXER_FUSO=0(E) LLAMA_DSV4_TOPK_FUSO=0(D) LLAMA_GRAPH_REUSE_DISABLE=0(D) LLAMA_GRAPH_REUSE_PER_TAGLIA=1(E) LLAMA_MMQ_X_IDS=<spento>(D) GGML_SCHED_PROFILO=0(E) GGML_CUDA_GRAPH_OPT=0(E)
server_manif: manifesto/diag: GGML_CUDA_GRAPH_STATS=0(D)
server_manif: manifesto/compute: GGML_CUDA_DISABLE_GRAPHS=<spento>(D) GGML_OP_OFFLOAD_MIN_BATCH=<spento>(D) GGML_CPU_MMID_REUSE_SRC1=0(D)
server_manif: manifesto/diag: GGML_BACKEND_PATH=<spento>(D) GGML_BACKTRACE_LLDB=<spento>(D) GGML_CPU_DISABLE_FUSION=<spento>(D) GGML_CUDA_ALLREDUCE=<spento>(D) GGML_CUDA_CUBLAS_COMPUTE_TYPE=<spento>(D) GGML_CUDA_DISABLE_FUSION=<spento>(D) GGML_CUDA_ENABLE_UNIFIED_MEMORY=<spento>(D) GGML_CUDA_NO_PINNED=<spento>(D) GGML_CUDA_P2P=<spento>(D) GGML_CUDA_PDL=<spento>(D) GGML_CUDA_REGISTER_HOST=<spento>(D) GGML_DISABLE_VULKAN=<spento>(D) GGML_KLEIDIAI_CHUNK_MULTIPLIER=<spento>(D) GGML_KLEIDIAI_SME=<spento>(D) GGML_META_DEBUG=<spento>(D) GGML_NO_BACKTRACE=<spento>(D) GGML_SCHED_DEBUG=<spento>(D) GGML_SCHED_DEBUG_INFO=<spento>(D) GGML_SCHED_DEBUG_REALLOC=<spento>(D) GGML_TOTAL_THREADS=<spento>(D) LLAMA_APP_CMD=<spento>(D) LLAMA_ATTN_ROT_DISABLE=<spento>(D) LLAMA_BATCH_DEBUG=<spento>(D) LLAMA_CACHE=<spento>(D) LLAMA_DSV4_COMPRESS_DEBUG=<spento>(D) LLAMA_GRAPH_INPUT_DEBUG=<spento>(D) LLAMA_GRAPH_RESULT_DEBUG=<spento>(D) LLAMA_KV_CACHE_DEBUG=<spento>(D) LLAMA_MANIFESTO=<spento>(D) LLAMA_MEDIA_MARKER=<spento>(D) LLAMA_SERVER_CHILD_MODE=<spento>(D) LLAMA_SERVER_ROUTER_PORT=<spento>(D) LLAMA_SERVER_SLOTS_DEBUG=<spento>(D) LLAMA_TRACE=<spento>(D)
```

### Confronti (con avvertenza esplicita sulla strumentazione)

- **vs `truth_clean2` (stessa strumentazione: profiler OFF, sched-profilo=0 su entrambi; unica
  differenza i CUDA graph)**: mediana 15,71 contro 13,49 -- delta **+16,46%**. Questo confronto
  RISPETTA la regola di pari strumentazione (runbook §4.4/§8.2): stesso p1, stesse copie, stesso
  SHA su entrambi i banchi, quindi stessa traiettoria -- la differenza è imputabile solo ai grafi
  CUDA.
- **vs SOTA storica (runbook §12.1, profiler ACCESO, 16,04-16,11-16,07, media 16,0733)**: NON è un
  confronto a pari strumentazione (quella storica ha il profiler ON, questa ha sched-profilo=0) --
  non viene fatto qui come verdetto. Riportato solo come dato grezzo: mediana di questo banco
  (15,71) è a circa 2,3 punti percentuali sotto la media storica, ma i due numeri non sono
  direttamente sottraibili per la regola di pari strumentazione.

Stato macchina a fine banco (2026-08-16 18:01:13): processi_llama = 0, RAM libera = 87,8 GB.
Nessuna invocazione di nvidia-smi in questa terza parte del banco (unica invocazione dell'intera
sessione resta quella di preflight, 16:15 circa). Chiusura pulita su tutte e tre le repliche
(`ctrl-c`, mai `RISERVA Stop-Process`). Nessun commit git eseguito. Nessuna build avviata da questo
esecutore (la compilazione trovata al preflight apparteneva a un altro agente, su un albero diverso,
ed è terminata prima del lancio di R1).

---

## subtract_graphs_b1200_r1/r2/r3_20260816 — Fase 0, attribuzione del residuo (binario "sottrazione") — PROMOSSA, nessuna divergenza

Banco richiesto dal coordinatore per isolare il costo (se esiste) del codice sperimentale del
15-16/8 (EXPERT_REUSE, fusione GATE_UP, check per-nodo): stesso comando di `truth_graphs` (grafi
CUDA accesi, `GGML_CUDA_DISABLE_GRAPHS` assente dall'ambiente) ma puntato su un binario compilato
**senza** quel codice, tramite `-ServerPath`.

### Verifica identità del binario (richiesta esplicitamente dal mandato, eseguita prima e durante)

**Prima del banco** (hash della DLL, che è dove sta il codice: l'exe è un launcher sottile):
```text
file       : D:\llama-subtract\build\bin\ggml-cuda.dll
lunghezza  : 212.806.144 byte  (atteso 212.806.144, coincide)
delta vs originale (D:\llama-overlap, 213.380.608 byte) : 574.464 byte  (atteso 574.464, coincide esattamente)
SHA256     : 00A914B9C2192A5F71D3B61E923AB16F3E1CE6E0582215D122E393E6827A2962
atteso     : 00A914B9C2192A5F71D3B61E923AB16F3E1CE6E0582215D122E393E6827A2962
coincide   : True
exe        : D:\llama-subtract\build\bin\llama-server.exe, 10.752 byte (launcher sottile, coerente col pattern gia' visto su D:\llama-overlap)
```

**Durante ciascuna replica** (a server pronto, `(Get-Process llama-server).Path`):
```text
R1 (PID 10180) : D:\llama-subtract\build\bin\llama-server.exe  -- coincide
R2             : D:\llama-subtract\build\bin\llama-server.exe  -- coincide
R3             : D:\llama-subtract\build\bin\llama-server.exe  -- coincide
```

**Preflight aggiuntivo**: nessun processo di compilazione residuo (verificato prima del banco,
0 processi cl/nvcc/ninja/cmake/MSBuild — la compilazione vista nel banco precedente, che
presumibilmente produceva proprio questo binario, era già terminata).

**Policy di divergenza per questo banco (diversa dagli altri, dichiarata dal mandato)**: se
p1/copie/SHA fossero divergenti, la regola era completare comunque la replica e segnalare, non
fermarsi -- la divergenza stessa sarebbe stata un risultato (il codice rimosso non sarebbe stato
neutro sulla traiettoria). **Non si è verificata alcuna divergenza**: tutte e tre le repliche
hanno p1/copie/SHA identici allo storico, quindi questa policy non è stata esercitata.

```text
tag R1           = subtract_graphs_b1200_r1_20260816
tag R2           = subtract_graphs_b1200_r2_20260816
tag R3           = subtract_graphs_b1200_r3_20260816
data/ora         = R1 lancio 18:10:24 -> R2 lancio 18:14:28 -> R3 lancio 18:20:31 -> fine 18:24:33
runner           = B (run_porto_hot.ps1) con -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
banco            = B1200
ripetizioni      = 3 (R1, R2, R3), tutte passano il cancello, nessuna divergenza
leva variata     = binario (codice sperimentale del 15-16/8 rimosso), grafi CUDA accesi come in truth_graphs
comando esatto (R1, R2 e R3 identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe' -Extra 'GGML_SCHED_PROFILO=0;LLAMA_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'

riga cache-esperti (identica sulle tre repliche, verbatim, identica anche a truth_graphs) =
  cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0

                    R1              R2              R3
GGML_CUDA_DISABLE_GRAPHS  <spento>(D)     <spento>(D)     <spento>(D)   -- CANCELLO PASSATO su tutte e tre
righe sched-profilo 0               0               0            -- CANCELLO PASSATO su tutte e tre
eval t/s            15,69           15,52           15,86
ms/token             63,73           64,43           63,03
prompt t/s           23,22           21,33           22,25
wall_ms             79.474,1        80.580,7        78.778,6
p1                  0.90025 (713/792)  0.90025 (713/792)  0.90025 (713/792)   -- COINCIDE con lo storico su tutte e tre, NESSUNA DIVERGENZA
copie/buchi         216737/168831/47906  216737/168831/47906  216737/168831/47906  -- COINCIDE con lo storico su tutte e tre
finish_reason       length          length          length
SHA output          4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D  (le tre repliche, identico allo storico)
content_chars       3572            3572            3572
divergenze          taglia=0 ids=0 out=0 GRIGLIA-corta=0 su tutte e tre, nessun GGML_ASSERT/CUDA error
chiusura            ctrl-c          ctrl-c          ctrl-c       -- pulita su tutte e tre
percorso processo   D:\llama-subtract\build\bin\llama-server.exe -- coincide su tutte e tre (verificato a server pronto)

MEDIANA eval t/s     = 15,69    (valori ordinati 15,52 / 15,69 / 15,86 -- elemento centrale vero, v[1])
media eval t/s       = 15,69    (coincide numericamente con la mediana in questo caso)
spread max-min       = 2,19 %   -- sotto la soglia del 5% (non "rumoroso")
MEDIANA ms/token      = 63,73   (valori ordinati 63,03 / 63,73 / 64,43)

build            = build 10093 (3014d3756) with MSVC 19.44.35227.0  (invariato: stessa base, differisce solo il codice sperimentale sottratto)
snapshot         = porto_hot_snapshot = 0 su tutte e tre repliche
server vivi max  = 1 per replica
esito            = PROMOSSO: 3/3 repliche passano tutti i cancelli (grafi accesi, sched-profilo=0,
                    p1, copie, SHA, DLL, percorso processo). MEDIANA = 15,69 t/s. Nessuna
                    divergenza rilevata rispetto allo storico.
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\subtract_graphs_b1200_r{1,2,3}_20260816.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\subtract_graphs_b1200_r{1,2,3}_20260816.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\subtract_graphs_b1200_r{1,2,3}_20260816.r1.output.txt
```

### ENV COMPLETO (identico a `truth_graphs`, nessuna riga aggiuntiva -- nuova regola, verificato non solo assunto)

Confrontate le righe `server_manif:` di `subtract_graphs_b1200_r1_20260816.server.log` con quelle
già trascritte per `truth_graphs_b1200_r1_20260816.server.log` (sezione precedente di questo
ledger): stesse variabili, stessi valori, incluso `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` e
`GGML_CUDA_GRAPH_STATS=0(D)`. Non ripetute qui per esteso per evitare duplicazione: vedi la sezione
`truth_graphs` sopra per il testo completo verbatim.

### INTERPRETAZIONE (richiesta esplicitamente dal mandato, accanto alla mediana)

```text
riferimento (truth_graphs, stesso regime, grafi accesi, profiler spento) = 15,71 t/s
questo banco (subtract_graphs, stesso regime, codice sperimentale rimosso) = 15,69 t/s
delta = -0,13 %
```
**Dentro la banda ±3% dichiarata dal mandato**: il codice sperimentale del 15-16/8 (EXPERT_REUSE,
fusione GATE_UP, check per-nodo) risulta **gratis** in questo regime -- il piccolo residuo
osservato (-0,13%) è compatibile con la deriva/rumore del banco (lo spread interno di questo stesso
banco, 2,19%, è già più grande del delta osservato fra i due banchi). Non si può concludere che il
codice sperimentale sia la causa del gap fra 15,71/15,69 (grafi accesi, entrambi) e la SOTA storica
16,04-16,11-16,07 (profiler acceso, non a pari strumentazione con questi due banchi) -- quel gap
resta un residuo non attribuito da questa fase 0.

Stato macchina a fine banco (2026-08-16 18:24:33): processi_llama = 0, RAM libera = 87,3 GB.
Nessuna invocazione di nvidia-smi in questa quarta parte del banco (unica invocazione dell'intera
sessione resta quella di preflight, 16:15 circa). Chiusura pulita su tutte e tre le repliche
(`ctrl-c`, mai `RISERVA Stop-Process`). Nessun commit git eseguito. Nessuna build avviata da questo
esecutore (il binario "sottrazione" era già compilato, come dichiarato dal mandato).

---

## profile_graphs_b1200_r1/r2/r3_20260816 — banco finale della serata: confronto a pari strumentazione + tabella di profilo — PROMOSSA

Binario ORIGINALE di `D:\llama-overlap` (nessun `-ServerPath`, già identificato per SHA256 nel
preflight iniziale). Obiettivo duplice: (1) chiudere il capitolo regressione con un confronto alla
storica a **pari strumentazione** (profiler acceso su entrambi i lati, invece dei confronti a
strumentazione diversa fatti finora); (2) estrarre la scomposizione del profiler per grafo e per
worker come fondamento della Fase 1 del macro-v2.

**Cancello con un punto INVERTITO rispetto a tutti i banchi precedenti della serata**: qui le righe
`sched-profilo` DEVONO essere **> 0** (profiler acceso, come nella storica), non 0. Applicato
correttamente: verificato `> 0` su tutte e tre le repliche, non `= 0`.

```text
tag R1           = profile_graphs_b1200_r1_20260816
tag R2           = profile_graphs_b1200_r2_20260816
tag R3           = profile_graphs_b1200_r3_20260816
data/ora         = R1 lancio 18:28:16 -> R2 lancio 18:32:36 -> R3 lancio 18:36:30 -> fine 18:40:34
runner           = B (run_porto_hot.ps1), binario originale D:\llama-overlap (nessun -ServerPath)
banco            = B1200
ripetizioni      = 3 (R1, R2, R3), tutte passano il cancello (con il punto (b) invertito)
leva variata     = GGML_SCHED_PROFILO=1 (acceso, non spento); GGML_CUDA_DISABLE_GRAPHS assente (grafi accesi, come in truth_graphs/subtract_graphs); nessuna LLAMA_SCHED_PROFILO (variabile inesistente, correttamente omessa)
comando esatto (R1, R2 e R3 identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'GGML_SCHED_PROFILO=1;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'

riga cache-esperti (identica sulle tre repliche, verbatim, identica a tutti i banchi precedenti) =
  cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0

                    R1              R2              R3
GGML_CUDA_DISABLE_GRAPHS  <spento>(D)     <spento>(D)     <spento>(D)   -- CANCELLO PASSATO (grafi accesi)
righe sched-profilo 41              41              41           -- CANCELLO PASSATO (>0 richiesto stavolta, non =0)
eval t/s            15,86           16,00           15,94
ms/token             63,07           62,49           62,74
prompt t/s           21,18           22,23           21,36
wall_ms             78.976,8        78.125,6        78.551,7
p1                  0.90025 (713/792)  0.90025 (713/792)  0.90025 (713/792)   -- COINCIDE con l'atteso su tutte e tre
copie/buchi         216737/168831/47906  216737/168831/47906  216737/168831/47906  -- COINCIDE con l'atteso su tutte e tre
finish_reason       length          length          length
SHA output          4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D  (le tre repliche, identico)
content_chars       3572            3572            3572
divergenze          taglia=0 ids=0 out=0 GRIGLIA-corta=0 su tutte e tre, nessun GGML_ASSERT/CUDA error
chiusura            ctrl-c          ctrl-c          ctrl-c       -- pulita su tutte e tre

MEDIANA eval t/s     = 15,94    (valori ordinati 15,86 / 15,94 / 16,00 -- elemento centrale vero, v[1])
media eval t/s       = 15,9333
spread max-min       = 0,88 %   -- il piu' basso spread della serata, banco molto stabile
MEDIANA ms/token      = 62,74   (valori ordinati 62,49 / 62,74 / 63,07)

build            = build 10093 (3014d3756) with MSVC 19.44.35227.0  (invariato)
SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (invariato, verificato nel preflight iniziale della sessione)
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (invariato)
snapshot         = porto_hot_snapshot = 0 su tutte e tre repliche
server vivi max  = 1 per replica
esito            = PROMOSSO: 3/3 repliche passano il cancello completo (grafi accesi, sched-profilo
                    ACCESO come richiesto, p1, copie, SHA). MEDIANA = 15,94 t/s.
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\profile_graphs_b1200_r{1,2,3}_20260816.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\profile_graphs_b1200_r{1,2,3}_20260816.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\profile_graphs_b1200_r{1,2,3}_20260816.r1.output.txt
```

### CONFRONTO A PARI STRUMENTAZIONE CON LA STORICA (chiude il capitolo regressione)

```text
storica (RUNBOOK SS12.1)     : 16,04 / 16,11 / 16,07 t/s   media 16,0733   profiler ACCESO
questo banco                 : 15,86 / 16,00 / 15,94 t/s   media 15,9333   mediana 15,94   profiler ACCESO

delta mediana (15,94) vs media storica (16,0733)  = -0,829 %
delta media   (15,9333) vs media storica (16,0733) = -0,871 %
```
**Entrambi i delta sono sotto la soglia del 3% (RUNBOOK SS8.3): "non distingue: dentro la deriva di
banco".** Questo è il **primo confronto della serata a pari strumentazione reale** (profiler acceso
su entrambi i lati) -- tutti i confronti precedenti (12,12 / 13,49 / 15,71 / 15,69 contro 16,0733)
erano fra strumentazioni diverse (profiler spento contro storica con profiler acceso) e quindi non
validi per giudicare la regressione. A pari strumentazione, il gap è **sostanzialmente chiuso**: la
causa della "regressione del 13-14%" della sessione precedente e dei 12,12-13,49 t/s misurati stasera
prima di questo banco era interamente (o quasi) il bug `GGML_CUDA_DISABLE_GRAPHS` (presenza-vs-valore,
vedi sezione `truth_graphs` sopra), non una regressione strutturale del codice.

### TABELLA DI PROFILO (il valore principale del banco, fondamento Fase 1 macro-v2)

Estratta da `profile_graphs_b1200_r1_20260816.server.log` (R2/R3 non ri-estratte per esteso, come
da mandato "estrai da UNA replica"; il conteggio grafi/lavori è identico su tutte e tre le repliche
per costruzione, essendo lo stesso carico deterministico).

**Formato scoperto e verificato in questa sessione**: le righe `sched-profilo:` sono medie
cumulative stampate ogni 50 grafi; l'ultima (al numero di grafi piu' alto) e' la piu' convergente e
coincide esattamente col conteggio storico. Le righe `sched-profilo-finale:` riportano le statistiche
worker; ne compaiono due per corsa (una intermedia, una finale) -- si usa l'ultima (lavori piu' alto).

**Per grafo** (riga raw: `sched-profilo: 1951 grafi, 35.6 split/grafo, per grafo: ingressi 3.770 ms
(di cui sync 2.839), calc CPU 1.375 ms, calc altri 4.253 ms, dispatch 0.188 ms, sched-sync 0.120 ms
(0.750 chiamate/grafo)`):

| metrica | oggi (profile_graphs R1) | storico | delta |
|---|---:|---:|---:|
| n. grafi | 1.951 | 1.951 | identico |
| split/grafo | 35,6 | 35,6 | identico |
| ingressi ms/grafo | 3,770 | 3,692 | +2,1% |
| di cui sync ms/grafo | 2,839 | 2,741 | +3,6% |
| calc CPU ms/grafo | 1,375 | 1,358 | +1,3% |
| calc altri ms/grafo | 4,253 | 4,080 | +4,2% |
| dispatch ms/grafo | 0,188 | 0,193 | -2,6% |
| sched-sync ms/grafo | 0,120 | 0,133 | -9,8% |

**Per worker** (riga raw: `sched-profilo-finale: worker 20941 lavori, per lavoro: evento 0.883 ms,
calcolo 1.807 ms, attesa-lavoro 1.070 ms, join 2.670 ms (1.000 join/lavoro)`):

| metrica | oggi (profile_graphs R1) | storico | delta |
|---|---:|---:|---:|
| n. lavori | 20.941 | 20.941 | identico |
| evento ms/lavoro | 0,883 | 0,878 | +0,6% |
| calcolo CPU ms/lavoro | 1,807 | 1,772 | +2,0% |
| attesa-lavoro ms/lavoro | 1,070 | 1,063 | +0,7% |
| join ms/lavoro | 2,670 | 2,631 | +1,5% |

**Lettura**: accordo eccellente su tutta la linea, tutti i delta sotto il 10% (la maggior parte sotto
il 5%), i due conteggi strutturali (n. grafi, split/grafo, n. lavori) identici carattere per
carattere allo storico. Il profilo di oggi riproduce fedelmente quello storico -- ulteriore conferma
indipendente, a livello di composizione del costo per grafo/worker (non solo di t/s aggregato), che
il gap era il bug dei CUDA graph e non una deriva strutturale del codice.

### ENV COMPLETO (nuova regola, tutte le variabili non solo quelle cambiate)

Coincide con l'ENV di `truth_graphs`/`subtract_graphs` per tutte le righe eccetto due, che qui
cambiano deliberatamente:
```text
server_manif: manifesto/compute: ... GGML_SCHED_PROFILO=1(E) GGML_CUDA_GRAPH_OPT=0(E)   [era =0(E) negli altri banchi]
server_manif: manifesto/compute: GGML_CUDA_DISABLE_GRAPHS=<spento>(D) ...               [identico agli altri due banchi con grafi accesi]
```
Tutte le altre righe manifesto (cache, spec, kv, orfane, vram, reap, diag) sono identiche a quelle
già trascritte per esteso nella sezione `truth_graphs` sopra -- non ripetute per evitare duplicazione.

### Anomalia osservata durante il postflight (da riportare, non spiegata)

Un comando PowerShell di post-elaborazione (verifica processi/RAM + calcolo mediana con divisioni
aritmetiche `[math]::Round((...)/(...) * 100, N)`) ha prodotto l'errore
`Remove-Item on system path '/' is blocked. This path is protected from removal.` Il comando **non
conteneva alcun `Remove-Item`** -- solo `Get-Process`, `Get-CimInstance`, `Write-Output`, `Get-Date`
e aritmetica con l'operatore `/`. Il blocco ha impedito l'esecuzione (nessun output, nessun effetto):
non risulta alcuna cancellazione avvenuta. La misura R3 era già completa e al sicuro in quel momento
(summary.json già scritto, confermato dal monitor prima dell'anomalia). Non spiegata la causa;
plausibile un falso positivo di un livello di sicurezza sugli operatori `/` nel testo del comando.
Non ripetuto il comando originale: rifatti gli stessi controlli con un comando PowerShell minimale
(solo `Get-Process`/`Get-CimInstance`, senza aritmetica) e i calcoli di mediana/delta con Python
(tool Bash), entrambi riusciti senza anomalie. Nessun impatto sui dati del banco.

Stato macchina a fine banco (2026-08-16 18:40:34 circa): processi_llama = 0, RAM libera = 87,9 GB
(92.191.744 KB, verificato con comando minimale dopo l'anomalia). Nessuna invocazione di nvidia-smi
in questa quinta parte del banco (unica invocazione dell'intera sessione resta quella di preflight,
16:15 circa). Chiusura pulita su tutte e tre le repliche (`ctrl-c`, mai `RISERVA Stop-Process`).
Nessun commit git eseguito. Nessuna build avviata da questo esecutore. Banco finale della serata.

---

## Censimento split (Fase 1 macro-v2) — split_census_b160_r1_20260816 — CANCELLI PASSATI, COMPITO PRINCIPALE NON ESEGUIBILE

Braccio diagnostico richiesto per censire i blocchi `## SPLIT #` dei grafi di decode. Binario
originale `D:\llama-overlap`, B160, singola replica.

```text
tag              = split_census_b160_r1_20260816
data/ora         = lancio 18:46:53 -> fine 18:49:20
runner           = B (run_porto_hot.ps1), binario originale (nessun -ServerPath)
banco            = B160
ripetizioni      = 1 (come da mandato: braccio diagnostico, singola replica)
comando esatto   = & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag 'split_census_b160_r1_20260816' -MaxTokens 160 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'GGML_SCHED_PROFILO=0;GGML_SCHED_DEBUG_INFO=1;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

### Cancelli minimi

| cancello | atteso | ottenuto | esito |
|---|---|---|---|
| manifesto GGML_CUDA_DISABLE_GRAPHS | `<spento>(D)` | `<spento>(D)` | PASSATO |
| p1 | .77670 | 0.77670 (80 accepted / 103 generated) | PASSATO |
| SHA output | 991AF3E1... | AD3D3770... (raw diverso) | PASSATO dopo verifica -- vedi sotto |

**Verifica SHA** (stesso pattern gia' visto due volte in questa sessione): raw diverso per BOM UTF-8
(`AD3D3770...`, 88 byte, inizia `EF BB BF`) contro lo storico senza BOM (`991AF3E1...`, 85 byte).
Dopo rimozione BOM e CR: **stesso SHA256 normalizzato** (`E31819614C78D59B25CA108848CA3AA8C9CF3088EE49D2C28E8C7B6202F69C15`),
stessa lunghezza (84 byte). Confermato indipendentemente, non solo assunto: stesso testo.

t/s (dato grezzo, **diagnostico, non confrontabile** -- come da mandato, il debug scheduler rallenta):
eval 12,64 t/s, ms/token 79,11, wall_ms 15.900,1, prompt t/s 21,53, finish_reason length.

### COMPITO PRINCIPALE (censimento split): NON ESEGUIBILE con questa configurazione -- causa trovata sul codice sorgente

Nessun blocco `## SPLIT #` presente nel log (`split_census_b160_r1_20260816.server.log`, 53.435
byte, 549 righe). Non e' un problema di pattern di ricerca: **il dato non e' stato prodotto**.

**Causa verificata leggendo `D:\llama-overlap\ggml\src\ggml-backend.cpp`:**

```cpp
// riga 1666-1668 -- la funzione che stampa i blocchi "## SPLIT #" e' chiamata SOLO se sched->debug e' vero
if (sched->debug) {
    ggml_backend_sched_print_assignments(sched, graph);
}

// riga 2445-2446 -- sched->debug dipende ESCLUSIVAMENTE da GGML_SCHED_DEBUG, non da GGML_SCHED_DEBUG_INFO
const char * GGML_SCHED_DEBUG = getenv("GGML_SCHED_DEBUG");
sched->debug = GGML_SCHED_DEBUG ? atoi(GGML_SCHED_DEBUG) : 0;

// righe 1182-1188 -- GGML_SCHED_DEBUG_INFO controlla SOLO il LIVELLO di log (INFO vs DEBUG)
// della stampa, una volta che questa gia' avviene -- non se avviene
static bool ggml_sched_debug_info(void) {
    static const bool v = [] {
        const char * e = getenv("GGML_SCHED_DEBUG_INFO");
        return e && *e && *e != '0';
    }();
    return v;
}
```

Il commento del codice stesso (righe 1162-1167, dell'autore del progetto) conferma l'intento della
variabile: *"Con GGML_SCHED_DEBUG_INFO=1 la stessa stampa esce a livello INFO"* -- cioe'
`GGML_SCHED_DEBUG_INFO` presuppone che la stampa sia gia' abilitata da altrove (`GGML_SCHED_DEBUG`),
e serve solo a farla passare il filtro di verbosita' del server. Impostare solo
`GGML_SCHED_DEBUG_INFO=1` (come da `-Extra` del mandato) senza `GGML_SCHED_DEBUG>=1` non produce
alcuna riga `## SPLIT #`: verificato nel manifesto di questo run,
`GGML_SCHED_DEBUG=<spento>(D) GGML_SCHED_DEBUG_INFO=1(E)` -- la prima e' rimasta al default.

**Di conseguenza, i punti (a)-(d) del compito principale (split/grafo, breakdown backend/op di testa,
top 5 pattern, lane CPU K2 vs altri forzati) non sono stati eseguiti**: non c'e' materiale nel log da
cui estrarli. Coerentemente con la disciplina di questa sessione (non improvvisare una correzione e
rilanciare di propria iniziativa quando una variabile d'ambiente non produce l'effetto atteso per un
motivo tecnico preciso), questo esecutore si ferma qui e segnala, senza lanciare una replica
aggiuntiva con `GGML_SCHED_DEBUG` aggiunto.

percorsi file:
```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_b160_r1_20260816.server.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_b160_r1_20260816.summary.json
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_b160_r1_20260816.r1.output.txt
D:\llama-overlap\ggml\src\ggml-backend.cpp  (righe 1162-1228, 2443-2448 -- riferimento del codice)
```

Stato macchina a fine banco (2026-08-16 18:49 circa): processi_llama = 0, RAM libera = 88,1 GB
(92.386.584 KB). Nessuna invocazione di nvidia-smi in questa sesta parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita (`ctrl-c`). Nessun
commit git eseguito. Nessuna build avviata da questo esecutore. Nessuna replica aggiuntiva lanciata.

---

## Censimento split (Fase 1 macro-v2) — split_census_b160_r2_20260816 — CANCELLI PASSATI, censimento eseguito

Correzione confermata dal coordinatore: `GGML_SCHED_DEBUG=1` aggiunto accanto a
`GGML_SCHED_DEBUG_INFO=1`. Verificato che questo abilita davvero la stampa (3.973 righe `## SPLIT #`
trovate, contro 0 nel tentativo precedente).

```text
tag              = split_census_b160_r2_20260816
data/ora         = lancio 18:53:49 -> fine 18:56:13
runner           = B (run_porto_hot.ps1), binario originale (nessun -ServerPath)
banco            = B160
ripetizioni      = 1
comando esatto   = & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag 'split_census_b160_r2_20260816' -MaxTokens 160 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'GGML_SCHED_PROFILO=0;GGML_SCHED_DEBUG_INFO=1;GGML_SCHED_DEBUG=1;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

### Cancelli minimi

| cancello | atteso | ottenuto | esito |
|---|---|---|---|
| manifesto GGML_CUDA_DISABLE_GRAPHS | `<spento>(D)` | `<spento>(D)` | PASSATO |
| manifesto debug | -- | `GGML_SCHED_DEBUG=1(E) GGML_SCHED_DEBUG_INFO=1(E)` | entrambe attive, confermato |
| p1 | .77670 | 0.77670 (80/103) | PASSATO |
| SHA output | 991AF3E1... (equiv. normalizzato) | AD3D3770... (identico a R1, gia' verificato equivalente) | PASSATO |

t/s (dato grezzo, **diagnostico, non confrontabile**): eval 13,23 t/s, wall_ms 15.274,1. Log:
236.826 byte, 4.522 righe, 3.973 blocchi `## SPLIT #`. Nessun errore/assert.

### Metodologia di esclusione warm-up/prefill

I 3.973 blocchi si raggruppano in 294 "grafi" (ogni sequenza riparte da `## SPLIT #0`). I primi 9
grafi (split-count 45,45,5,45,45,5,45,5,131) sono concentrati in una finestra di **36 millisecondi**
all'avvio (timestamp da `1.33.847.902` a `1.33.883.720`), seguiti da un **salto di ~18 secondi**
prima che il grafo #10 (in ordine di apparizione) riprenda a `1.51.488.818`. Questo e' il segnale piu'
netto disponibile nel log per separare warm-up/graph-capture da calcolo reale: i 9 grafi iniziali sono
esclusi, i restanti **285 grafi** sono trattati come "fase decode" (nota: questo include
verosimilmente anche l'unica passata di prefill del prompt da 68 token, che non si distingue
nettamente dal resto per timing -- vedi discrepanza con l'atteso, sotto).

### (a) Split per grafo: media e distribuzione

```text
totale split (fase decode) = 3.602   su 285 grafi
media split/grafo           = 12,639
```

| split/grafo | grafi | % |
|---:|---:|---:|
| 1 | 170 | 59,6% |
| 10 | 80 | 28,1% |
| 131 | 19 | 6,7% |
| 8 | 6 | 2,1% |
| 6 | 5 | 1,8% |
| 5 | 4 | 1,4% |
| 45 | 1 | 0,4% |

**Discrepanza onestamente segnalata**: la media osservata (12,639) NON e' vicina ai ~35,6 attesi dal
profiler (misurato su B1200, 1.951 grafi, regime stazionario di decode lungo). Possibili letture, **non
verificate**: (i) B160 (160 token) ha un peso proporzionalmente maggiore di transitori
iniziali/steady-state-non-ancora-raggiunto rispetto a B1200; (ii) il conteggio "split/grafo" del
profiler potrebbe aggregare una popolazione di grafi diversa da quella censita qui (es. solo i grafi
"principali" del target, escludendo i piccoli ausiliari da 1 split); (iii) il grafo residuo da 45
split fra i "decode" potrebbe essere mal classificato (coda del warm-up, soglia dei 9 grafi
imperfetta). Nessuna di queste e' stata verificata: si registra il fatto, non si forza una
spiegazione.

### (b) Breakdown per backend

| backend | split | % |
|---|---:|---:|
| CUDA0 | 2.322 | 64,46% |
| CPU | 1.280 | 35,54% |
| **totale** | **3.602** | **100%** |

**Breakdown per "op di testa dello split" (nome del primo nodo): NON DISPONIBILE.** Verificato sul
codice sorgente (`D:\llama-overlap\ggml\src\ggml-backend.cpp`, riga 1211): i nomi dei nodi/operazioni
sono stampati solo se `sched->debug > 1`; con `GGML_SCHED_DEBUG=1`, `sched->debug == 1`, quindi quella
condizione e' falsa e nessun nome di nodo esce nel log. Solo backend e numero di input per split sono
disponibili a questo livello. Alzare a `GGML_SCHED_DEBUG=2` produrrebbe anche il dump per-nodo di ogni
grafo (log ordini di grandezza piu' grande) -- non tentato in questo braccio, in attesa di indicazioni.

### (c) I 5 pattern di split più frequenti (firma = sequenza backend per grafo)

Pattern unici totali nella fase decode: 7. I primi 5 coprono 280/285 grafi (98,2%).

| # | grafi | % | n. split | firma backend |
|---:|---:|---:|---:|---|
| 1 | 170 | 59,6% | 1 | `CUDA0` |
| 2 | 80 | 28,1% | 10 | `CPU,CUDA0` ripetuto 5 volte |
| 3 | 19 | 6,7% | 131 | `CPU,CUDA0,CUDA0` ripetuto ~43-44 volte |
| 4 | 6 | 2,1% | 8 | `CPU,CUDA0` ripetuto 4 volte |
| 5 | 5 | 1,8% | 6 | `CPU,CUDA0` ripetuto 3 volte |

Esempi verbatim (una riga per pattern, la testata del primo split):

```text
#1 (1 split, CUDA0):     ## SPLIT #0: CUDA0 # 1 inputs                          [ts 1.55.556.208]
#2 (10 split, inizio):   ## SPLIT #0: CPU # 0 inputs                            [ts 1.51.846.365]
                         ## SPLIT #1: CUDA0 # 5 inputs                          [ts 1.51.846.369]
                         ## SPLIT #2: CPU # 2 inputs                            [ts 1.51.846.370]
                         ## SPLIT #3: CUDA0 # 1 inputs                          [ts 1.51.846.371]
                         ## SPLIT #4: CPU # 2 inputs                            [ts 1.51.846.371]
#3 (131 split, inizio):  ## SPLIT #0: CPU # 0 inputs                            [ts 1.55.298.163]
                         ## SPLIT #1: CUDA0 # 5 inputs                          [ts 1.55.298.166]
                         ## SPLIT #2: CUDA0 # 0 inputs                          [ts 1.55.298.166]
                         ## SPLIT #3: CPU # 2 inputs                            [ts 1.55.298.168]
                         ## SPLIT #4: CUDA0 # 1 inputs                          [ts 1.55.298.169]
#4 (8 split, inizio):    ## SPLIT #0: CPU # 0 inputs                            [ts 1.51.488.818]
                         ## SPLIT #1: CUDA0 # 5 inputs                          [ts 1.51.488.821]
#5 (6 split, inizio):    ## SPLIT #0: CPU # 0 inputs                            [ts 1.51.489.177]
                         ## SPLIT #1: CUDA0 # 5 inputs                          [ts 1.51.489.179]
```

### (d) Split CPU per grafo: lane K2 vs altri forzati CPU

| split CPU/grafo | grafi |
|---:|---:|
| 0 | 170 |
| 1 | 5 |
| 3 | 5 |
| 4 | 6 |
| 5 | 80 |
| 44 | 19 |

**Non e' possibile attribuire con certezza** quali split CPU appartengano alla lane K2 (route
esperti su CPU, `LLAMA_OVERLAP_K=2`) e quali siano forzati CPU per altri motivi (es. `GET_ROWS` sui
k-quant): questo richiederebbe i nomi delle operazioni, non disponibili a `GGML_SCHED_DEBUG=1` (vedi
punto b). Osservazione grezza, **non un'attribuzione verificata**: nei grafi da 10 split (il gruppo
piu' numeroso dopo i CUDA-only, 80 grafi = il numero piu' vicino ai ~80 round di decode attesi da
160 token / mean-len 2,01) il pattern alterna esattamente CPU e CUDA0 cinque volte, un conteggio
compatibile con -- ma non a dimostrazione di -- l'ipotesi K2. Da verificare con `GGML_SCHED_DEBUG=2`
se richiesto.

### Percorsi file

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_b160_r2_20260816.server.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_b160_r2_20260816.summary.json
C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad\parse_splits3.py  (script di aggregazione usato)
```

Stato macchina a fine banco (2026-08-16 18:57 circa): processi_llama = 0, RAM libera = 88,1 GB
(92.335.556 KB). Nessuna invocazione di nvidia-smi in questa settima parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita (`ctrl-c`). Nessun
commit git eseguito. Nessuna build avviata da questo esecutore. Nessuna replica aggiuntiva lanciata.

---

## Attribuzione per-operazione (Fase 1 macro-v2, finale) — split_census_debug2_b20_r1_20260816 — VERDETTO

Ultimo braccio diagnostico della catena. `GGML_SCHED_DEBUG=2` (oltre a `GGML_SCHED_DEBUG_INFO=1`)
per ottenere i nomi di op e tensori dei nodi, non solo le testate degli split. B20 (20 token, non
160) per contenere la dimensione del log, che con debug=2 esplode: 11.984.259 byte per soli 20 token,
contro 236.826 byte per 160 token a debug=1.

```text
tag              = split_census_debug2_b20_r1_20260816
data/ora         = lancio 19:04:18 -> fine 19:07:12
runner           = B (run_porto_hot.ps1), binario originale (nessun -ServerPath)
banco            = B20
ripetizioni      = 1
comando esatto   = & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag 'split_census_debug2_b20_r1_20260816' -MaxTokens 20 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'GGML_SCHED_PROFILO=0;GGML_SCHED_DEBUG=2;GGML_SCHED_DEBUG_INFO=1;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

### Cancelli minimi

| cancello | atteso | ottenuto |
|---|---|---|
| manifesto GGML_CUDA_DISABLE_GRAPHS | `<spento>(D)` | `<spento>(D)` -- PASSATO |
| manifesto debug | -- | `GGML_SCHED_DEBUG=2(E) GGML_SCHED_DEBUG_INFO=1(E)` -- entrambe attive |
| p1 | nessun vincolo (B20 senza firma nota) | 0.57143 (8 accepted / 14 generated), mean len 1,73 -- solo registrato |
| SHA output | nessun vincolo | CF45FBFB944507BD41CA6B14D7C8B5A556597435DFD7AA546349F0069E6ADD17 -- solo registrato |

**t/s non riportato**, nemmeno come dato grezzo, come esplicitamente richiesto dal mandato (il
livello di debug 2 distorce il tempo di esecuzione). Nessun errore/assert.

### Metodologia

1.061 blocchi `## SPLIT #`, 105.368 righe `node #...` (nomi op/tensore). Raggruppati in 74 grafi.
Stesso criterio di esclusione warm-up gia' usato nel censimento precedente (salto temporale netto):
i primi 9 grafi (stesso identico pattern di split-count del run precedente: 45,45,5,45,45,5,45,5,131)
occupano stavolta ~1 minuto e 20 secondi (il logging a debug=2 rallenta molto anche il warm-up
stesso), seguiti da un gap di ~17,5 secondi prima che il grafo #10 (in ordine di apparizione) riprenda.
**65 grafi decode** analizzati.

### (2) Aggregazione op-nome sul primo nodo di ogni split CPU (tutte le famiglie insieme)

234 split CPU nella fase decode, con almeno un nodo estratto:

| op | conteggio | % |
|---|---:|---:|
| MUL_MAT_ID | 175 | 74,8% |
| GET_ROWS | 59 | 25,2% |

Tensori (nome del primo nodo, normalizzato togliendo il suffisso numerico di layer):

| tensore | conteggio |
|---|---:|
| ffn_moe_gate_overlap | 129 |
| ffn_moe_gate-N | 46 |
| inp_noise_embd | 23 |
| node_500 | 18 |
| node_510 | 12 |
| embd | 6 |

### (3) Le due famiglie di grafi

**Famiglia A -- grafi grandi, 131 split** (3 nel decode di questo B20; nel censimento B160
precedente erano 19/285 = 6,7%). 44 split CPU/grafo. Sequenza (verificata su tutti i 3 esempi):

```text
split #0  : GET_ROWS   embd                    <- lookup embedding, una volta per grafo
split #3  : MUL_MAT_ID ffn_moe_gate_overlap    <- poi ripetuto ogni 3 split fino al #129
split #6  : MUL_MAT_ID ffn_moe_gate_overlap
split #9  : MUL_MAT_ID ffn_moe_gate_overlap
...
split #129: MUL_MAT_ID ffn_moe_gate_overlap    (43 ripetizioni totali per grafo)
```

Aggregato sui 3 grafi: `MUL_MAT_ID`=129 (43/grafo), `GET_ROWS`=3 (1/grafo). **Il nome del tensore
stesso -- `ffn_moe_gate_overlap` -- e' la prova diretta**: non serve inferire, la lane e' nominata
esplicitamente "overlap" nel codice. Risposta al punto 3(a) del mandato: **si', sono le route esperti
della lane K2** (gate MoE della cache-esperti, ramo overlap), non altro.

**Famiglia B -- grafi da 10 split** (12 nel decode di questo B20; nel censimento B160 precedente
erano gli 80/285 = 28,1%, il gruppo piu' numeroso dopo i CUDA-only). 5 split CPU/grafo, sempre la
stessa sequenza:

```text
split #0: GET_ROWS   inp_noise_embd
split #2: MUL_MAT_ID ffn_moe_gate-1     <- SENZA suffisso _overlap: gate normale, non lane K2
split #4: MUL_MAT_ID ffn_moe_gate-2
split #6: GET_ROWS   node_500
split #8: GET_ROWS   node_510
```

Aggregato sui 12 grafi: `GET_ROWS`=36 (3/grafo), `MUL_MAT_ID`=24 (2/grafo). Risposta al punto 3(b) del
mandato: il sospetto "GET_ROWS su markov_w1/k-quant" **non e' confermato per nome** (nessun tensore
si chiama `markov_w1` in questo estratto; compaiono invece `inp_noise_embd`, `node_500`, `node_510`),
ma la lettura strutturale e' compatibile: due gate MoE **senza** overlap (`ffn_moe_gate-1`,
`ffn_moe_gate-2`, coerenti con un modello a pochi strati) piu' tre `GET_ROWS`, uno dei quali
(`inp_noise_embd`) suggerisce fortemente un input specifico del drafter (rumore/embedding di
innesco), non del target.

### (4) Caratteristiche distintive fra le due famiglie -- verdetto sull'ipotesi 131=target+K2, 10=drafter

| caratteristica | Famiglia A (131 split) | Famiglia B (10 split) |
|---|---:|---:|
| split CPU/grafo | 44 | 5 |
| nodi totali estratti (esempio) | 5.879 | 304 |
| totale input dichiarati (somma split) | 234 | 16 |
| tensori `hc_mixes/hc_pre/hc_post/hc_comb` | 86 occorrenze ciascuno | 6 occorrenze ciascuno |
| tensori `ffn_moe_*_overlap` (gate/up/swiglu/down) | 86 occorrenze ciascuno | assenti |
| tensori attention (`qr`,`q_norm`,`q_pe`,`kv_pe`,`attn_derope`,...) | presenti, alto conteggio | presenti, 3 occorrenze ciascuno |
| tensori `csa_state_compress` / `lid_state_compress` | 84 occorrenze ciascuno | assenti |

**Verdetto**: l'ipotesi del mandato e' **confermata dall'evidenza dei nomi dei tensori**, non solo
dal conteggio split:
- **Famiglia A (131 split) = grafo del modello TARGET con la lane overlap (K2) attiva** -- i tensori
  `ffn_moe_gate_overlap`, `ffn_moe_upc_overlap`, `ffn_moe_swiglu_overl`, `ffn_moe_down_overlap`
  compaiono esattamente 86 volte ciascuno (verosimilmente una volta per strato con MoE attivo), e
  sono nominati esplicitamente "overlap" nel codice stesso -- non e' un'inferenza, e' il nome del
  tensore. Le dimensioni (5.879 nodi, 234 input dichiarati) sono coerenti con un forward pass
  completo del modello grande.
- **Famiglia B (10 split) = grafo del DRAFTER** -- struttura enormemente piu' piccola (304 nodi
  contro 5.879), nessun tensore con suffisso `_overlap`, gate MoE numerati solo `-1`/`-2` (pochi
  strati, coerente con un drafter leggero), e l'input distintivo `inp_noise_embd` che non compare
  affatto nella famiglia A. Questo e' coerente con quanto gia' noto sul drafter DSpark/Markov
  (memoria del progetto: pochi strati DSV4, testa Markov).

Questa e' un'attribuzione basata su evidenza diretta (nomi dei tensori nel log), non una congettura:
il grado di confidenza e' alto per la distinzione A=target/overlap vs B=drafter/non-overlap; e' piu'
debole per l'identificazione puntuale di `node_500`/`node_510` (nomi generici, non descrittivi) e per
il dettaglio esatto della "catena DFlash" menzionata nel mandato, che non compare per nome in
questo estratto.

### Percorsi file

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_debug2_b20_r1_20260816.server.log  (11.984.259 byte)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\split_census_debug2_b20_r1_20260816.summary.json
C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-moe-aggressive-commit\4b4c0194-0c4f-4f6b-8e2c-cb939d8d7daa\scratchpad\parse_splits_debug2b.py  (script di aggregazione usato)
```

Stato macchina a fine banco (2026-08-16 19:08 circa): processi_llama = 0, RAM libera = 87,9 GB
(92.211.744 KB). Nessuna invocazione di nvidia-smi in questa ottava parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita (`ctrl-c`). Nessun
commit git eseguito. Nessuna build avviata da questo esecutore. Nessuna replica aggiuntiva lanciata.
Ultimo braccio diagnostico della catena, come dichiarato dal mandato.

---

## Banco F2-A — leva GGML_SCHED_EVENT_JOIN — f2a_on_diag_b160_r1_20260816 — FERMATO AL CANCELLO (N=0)

Prima leva di **codice** (non solo diagnostica) testata in questa sessione, su un secondo binario
"sottrazione" (`D:\llama-subtract`) con una nuova `ggml-base.dll` che introduce
`GGML_SCHED_EVENT_JOIN` (default 0, letta con `atoi`).

### Preflight -- verifica dei tre hash (richiesta esplicitamente dal mandato)

| file | atteso | ottenuto | esito |
|---|---|---|---|
| llama-server.exe | `88991BB4...` | `88991BB4556DAF793E504C9CDC7EE5BC699CCC7F6E6B7DBB016F81BA7717D6C7` | coincide |
| ggml-cuda.dll | `00A914B9...` | `00A914B9C2192A5F71D3B61E923AB16F3E1CE6E0582215D122E393E6827A2962` | coincide (= sottrazione gia' nota, invariata) |
| ggml-base.dll | `6FBF3E8154EFC480493D68CAF2C9F2C526FF83E364B6F16F3847785B3D9F70A9` | idem | coincide -- NUOVO file, timestamp 19:34:45 (ricompilato dopo il banco precedente) |

Verificato inoltre che `GGML_SCHED_EVENT_JOIN` non compare in nessun documento sotto `docs\porto\`
(grep sul nome esatto e su varianti "evento/join"): nessuna prova che sia una famiglia gia' chiusa o
respinta (runbook SS10.4 punto 9). Non e' una verifica esaustiva della storia del progetto -- solo
un controllo sui documenti effettivamente disponibili in questa sessione.

```text
tag              = f2a_on_diag_b160_r1_20260816
data/ora         = lancio 19:41:07 -> fine 19:46:21 (caricamento insolitamente lento, ~4,5 min,
                    coerente con cache filesystem fredda sulla ggml-base.dll appena compilata --
                    nessun errore, solo piu' lento del tipico 1-2 min)
runner           = B (run_porto_hot.ps1), -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
banco            = B160
ripetizioni      = 1 (diagnostico)
comando esatto   = & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag 'f2a_on_diag_b160_r1_20260816' -MaxTokens 160 -Repetitions 1 -PortoHotSnapshot 0 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe' -Extra 'GGML_SCHED_EVENT_JOIN=1;GGML_SCHED_PROFILO=1;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

### Cancelli generali (tutti passati)

manifesto `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` -- PASSATO. Manifesto conferma
`GGML_SCHED_PROFILO=1(E)` -- profiler ACCESO come richiesto per il diagnostico. Nessun
`GGML_ASSERT`/`CUDA error`/divergenza. Chiusura pulita (`shutdown=ctrl-c` nel log del runner). t/s
non e' un verdetto qui (non riportato come dato di merito, per esplicita istruzione del mandato).

### CANCELLO PRINCIPALE -- riga `sched-event-join`: N=0, FERMATO

Tutte e quattro le occorrenze della riga (stampata piu' volte durante la corsa, non solo allo
shutdown come atteso dal mandato -- correzione fattuale rispetto alla descrizione del mandato,
segnalata qui) mostrano **confini a evento = 0**:

```text
sched-event-join: confini a evento 0, confini a blocco host 256
sched-event-join: confini a evento 0, confini a blocco host 268
sched-event-join: confini a evento 0, confini a blocco host 11626
sched-event-join: confini a evento 0, confini a blocco host 11626
```

Riga `sched-profilo` finale completa, **non parsata posizionalmente** (i due campi nuovi in coda
sono letti dall'etichetta esplicita `| confini evento/blocco N/M`, non da una posizione fissa):

```text
sched-profilo: 301 grafi, 35.1 split/grafo, per grafo: ingressi 7.523 ms (di cui sync 5.570), calc CPU 1.298 ms, calc altri 16.344 ms, dispatch 0.220 ms, sched-sync 0.118 ms (0.751 chiamate/grafo) | confini evento/blocco 0/10506
```

`N=0` in ogni occorrenza (le quattro righe `sched-event-join` e la coda della riga `sched-profilo`,
quest'ultima con `M=10506`, leggermente diverso dagli `M` delle righe `sched-event-join` perche'
sono snapshot presi in momenti diversi della corsa -- `M` cresce nel tempo, `N` resta a zero in ogni
snapshot). **Per mandato: N==0 => FERMA TUTTO.** Nessun braccio successivo (B1200 OFF/ON) eseguito.

**Interpretazione non richiesta ma disponibile**: `GGML_SCHED_EVENT_JOIN=1` non ha prodotto un solo
confine a evento in tutta la corsa (301 grafi, 160 token) -- la leva, cosi' come impostata ed
eseguita, e' risultata **completamente inerte** su questo banco: zero effetto osservabile sul
meccanismo che dovrebbe attivare. Non e' stato investigato il motivo (fuori mandato per questo
braccio, che chiede di fermarsi qui).

### Percorsi file

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\f2a_on_diag_b160_r1_20260816.server.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\f2a_on_diag_b160_r1_20260816.summary.json
```

Stato macchina a fine banco (2026-08-16 19:46 circa): processi_llama = 0, RAM libera = 88,0 GB
(92.297.028 KB). Nessuna invocazione di nvidia-smi in questa nona parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita (`ctrl-c`). Nessun
commit git eseguito. Nessuna build avviata da questo esecutore. Nessuna replica aggiuntiva lanciata
(fermato al cancello come da mandato, prima di B1200 OFF/ON).

---

## Banco L0 — ri-taratura n_max=3 — nmax3_graphs_b1200_r1_20260816 — FERMATO AL CANCELLO (leva inerte)

Test parametrico (non solo diagnostico) sulla speculazione: il verdetto storico "NMAX3-5 peggiora"
potrebbe essere stato misurato nel regime con i grafi CUDA rotti (bug scoperto in questa sessione,
banco `truth_graphs`), quindi da ri-testare nel regime corretto.

### Ricerca del nome esatto della variabile (richiesta esplicitamente, "non tirare a indovinare")

Trovato **non ambiguamente** in entrambi i file indicati dal mandato, indipendentemente l'uno
dall'altro:

```text
docs\porto\dopo_il_riavvio.ps1  riga 143:
  $NMAX = if ($env:PORTO_SPEC_NMAX -match '^\d+$') { [int]$env:PORTO_SPEC_NMAX } else { 1 }
  (poi passato al binario come --spec-draft-n-max)

run_porto_hot.ps1  riga 62:
  $env:PORTO_SPEC_NMAX = '2'   (default SOTA)
```

Variabile: **`PORTO_SPEC_NMAX`**. Coincide con quanto gia' letto nel runbook SS3.2.

```text
tag              = nmax3_graphs_b1200_r1_20260816
data/ora         = lancio 19:50:53 -> fine 19:54:56
runner           = B (run_porto_hot.ps1), binario originale (nessun -ServerPath)
banco            = B1200
ripetizioni      = 1 (fermato prima di R2/R3)
comando esatto   = & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag 'nmax3_graphs_b1200_r1_20260816' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -Extra 'GGML_SCHED_PROFILO=0;PORTO_SPEC_NMAX=3;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

### CANCELLO (a) FALLITO: n_max effettivo = 2, non 3

```text
1.49.836.710 I common_speculative_impl_draft_dflash: - n_max=2, n_min=0, p_min=0.00, conf_min=0.80
```

Nessuna riga manifesto con `PORTO_SPEC_NMAX` trovata nel log. Il valore effettivamente usato dal
motore di speculazione e' rimasto **2** (il default SOTA impostato da `run_porto_hot.ps1`), non 3
come da `-Extra`.

**Evidenza comportamentale indipendente, multipla, che conferma la lettura del log** (il mandato
stesso avvertiva che una speculazione diversa avrebbe legittimamente cambiato traiettoria e p1 --
qui invece nulla e' cambiato):

| campo | ottenuto (nmax3, atteso diverso) | storico n_max=2 | coincide? |
|---|---|---|---|
| SHA output | `4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D` | stesso | SI', bit-per-bit |
| p1 | 0.90025 (713 accepted / 792 generated) | 0.90025 (713/792) | SI', identico |
| mean len accettata | 2,47 | 2,47 | SI', identico |
| copie/buchi | domanda 216737, colpi 168831, buchi 47906 | stessi | SI', identico |

Se `PORTO_SPEC_NMAX=3` avesse avuto effetto, questi quattro valori sarebbero quasi certamente
cambiati (piu' token speculativi per ciclo = piu' route, come previsto esplicitamente dal mandato).
Sono rimasti identici in ogni cifra: prova convergente, non solo la singola riga di log, che la leva
e' rimasta inerte.

### Altri cancelli (passati, per completezza)

manifesto `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` -- PASSATO. Righe `sched-profilo` = 0 -- PASSATO.
Salute: `finish_reason=length`, nessun `GGML_ASSERT`/`CUDA error`/NaN anomalo (l'unica occorrenza di
`-inf` e' il bias del token EOS, comportamento normale e atteso, non un errore). Chiusura pulita
(`ctrl-c`). eval 16,02 t/s, ms/token 62,44 (dato grezzo, la leva non era davvero attiva quindi non e'
un punto dati per il verdetto n_max=3).

**Fermato qui per disciplina di sessione** (non improvviso una correzione e non rilancio con un nome
di variabile diverso di mia iniziativa): nessuna R2/R3 eseguita, nessun verdetto sul merito di
n_max=3 possibile con questo dato -- il banco non ha misurato quello che doveva misurare.

### Percorsi file

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax3_graphs_b1200_r1_20260816.server.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax3_graphs_b1200_r1_20260816.summary.json
```

Stato macchina a fine banco (2026-08-16 19:55 circa): processi_llama = 0, RAM libera = 88,0 GB
(92.312.776 KB). Nessuna invocazione di nvidia-smi in questa decima parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita (`ctrl-c`). Nessun
commit git eseguito. Nessuna build avviata da questo esecutore. Nessuna replica aggiuntiva lanciata.

---

## Banco F2-B — leva LLAMA_OVERLAP_JOIN_ASYNC — coppia diagnostica B160 OFF/ON — FERMATO (segnale primario non osservabile)

F2-A (eventi, `GGML_SCHED_EVENT_JOIN`) era morta per costruzione (N=0, banco precedente). Nuova leva
gia' esistente nella configurazione SOTA (`LLAMA_OVERLAP_JOIN_ASYNC`, default 0), verificata sul
codice sorgente prima del lancio (`D:\llama-overlap\ggml\src\ggml-backend.cpp`):

```cpp
// righe 1923-1925 -- lettura corretta sul VALORE, non solo sulla presenza
static const bool v = [] {
    const char * e = getenv("LLAMA_OVERLAP_JOIN_ASYNC");
    return e && *e && *e != '0';
}();

// riga 2025 -- richiede anche l'overlap generale attivo (gia' vero nel default SOTA)
const bool join_async = overlap && ggml_sched_overlap_join_async_attivo();

// righe 2115-2139 -- se join_async e le altre condizioni sono vere, copia asincrona
// invece di attesa/sync esplicita; incrementa prof.n_join_async SOLO se profilo attivo
```

```text
tag OFF          = joinasync_off_b160_r1_20260816
tag ON           = joinasync_on_b160_r1_20260816
data/ora         = OFF lancio 19:57:38 -> ON lancio 20:02:18 -> fine 20:05:07
runner           = B (run_porto_hot.ps1), binario originale (nessun -ServerPath)
banco            = B160, diagnostico, profiler ACCESO su entrambi
comando OFF      = -Extra 'GGML_SCHED_PROFILO=1;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'   (JOIN_ASYNC assente = default 0)
comando ON       = come sopra + 'LLAMA_OVERLAP_JOIN_ASYNC=1;...'
```

### Cancelli generali (passati su entrambi)

manifesto `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` -- PASSATO su entrambi. Manifesto conferma
`LLAMA_OVERLAP_JOIN_ASYNC=0(E)` (OFF) e `=1(E)` (ON) -- la leva raggiunge correttamente il
processo in entrambi i casi (a differenza di F2-A). Nessun errore/assert. Chiusura pulita
(`ctrl-c`) su entrambi. p1/SHA identici fra OFF e ON e identici allo storico B160
(0.77670, 80/103, mean len 2,01, SHA `AD3D3770...`) -- atteso per una leva di puro meccanismo di
trasporto, non di traiettoria.

### SEGNALE PRIMARIO RICHIESTO NON OSSERVABILE: "copie join-async"

La sonda specifica richiesta (`ggml_sched_profilo_stampa`, righe 1880-1892 di `ggml-backend.cpp`,
riga `sched-profilo: worker N lavori/grafo ... | copie join-async X`) **non e' comparsa in nessuno
dei due log** (OFF ne' ON), nonostante il manifesto confermi la leva attiva in ON. Verificato che
NON e' un problema di ricerca: e' assente anche cercando il prefisso esatto `^sched-profilo: worker`.

**Piu' rilevante**: questa stessa riga non e' comparsa **in nessun log di questa intera sessione**,
incluso il banco `profile_graphs_b1200_r1_20260816` (profiler pienamente attivo, 1.951 grafi, la
stampa per-grafo `sched-profilo: N grafi...` funzionava perfettamente li'). L'unica riga worker
osservata ovunque in sessione e' l'ALTRA, distinta, `sched-profilo-finale: worker N lavori...`
(da `ggml_backend_sched_free`, righe 2519-2525), che non contiene il campo "copie join-async".

Verificato inoltre nel codice (righe 2386-2389, 2458-2460) che `sched->worker` nasce **pigro** (al
primo lavoro spedito dal ramo CPU dell'overlap generale, non specificamente da JOIN_ASYNC) e che
la sua esistenza e' confermata indirettamente dal fatto che la riga `sched-profilo-finale: worker...`
appare in entrambi i log (86 lavori iniziali, poi 3.440 finali, identico OFF e ON) -- quindi il
worker ESISTE in entrambi i casi, ma il ramo di stampa con "copie join-async" non si attiva
comunque. Causa non identificata con certezza: non ulteriormente investigata per restare dentro il
perimetro del banco (verifica, non debug del codice).

### Segnali indiretti disponibili (non sostituiscono il cancello mancante)

| metrica (per-grafo, ultima riga, 301 grafi) | OFF | ON | delta |
|---|---:|---:|---:|
| ingressi ms/grafo | 7,519 | 7,188 | -4,4% |
| di cui sync ms/grafo | 5,581 | 5,237 | -6,2% |
| calc CPU ms/grafo | 1,280 | 1,285 | +0,4% |
| calc altri ms/grafo | 14,792 | 14,857 | +0,4% |

| metrica worker (`sched-profilo-finale`, 3.440 lavori) | OFF | ON | delta |
|---|---:|---:|---:|
| evento ms/lavoro | 0,892 | 0,899 | +0,8% |
| calcolo ms/lavoro | 1,585 | 1,573 | -0,8% |
| attesa-lavoro ms/lavoro | 1,929 | 1,924 | -0,3% |
| join ms/lavoro | 2,435 | 2,430 | -0,2% |

| t/s (dato grezzo, B160 diagnostico) | OFF | ON |
|---|---:|---:|
| eval t/s | 13,24 | 13,26 |

Lettura onesta: il tempo di `sync` per-grafo scende del 6,2% con la leva accesa (unico delta sopra
il rumore visivo), ma il campo `join` nella riga worker resta sostanzialmente invariato e il t/s
aggregato non si muove in modo apprezzabile su un banco B160 di 160 token. Non e' una prova ne' a
favore ne' contro l'efficacia della leva: e' un indizio debole, senza la conferma diretta del
contatore richiesto.

### Decisione: fermato prima di B1200 OFF/ON

Coerentemente con la disciplina di sessione (fermarsi quando un cancello di verifica non si
comporta come documentato, invece di procedere su un'ipotesi non confermata), **non sono stati
lanciati i bracci B1200 OFF x3 / ON x3** previsti come passi successivi del mandato. Il segnale
richiesto per decidere se procedere non e' disponibile con gli strumenti di log usati finora.

### Percorsi file

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\joinasync_off_b160_r1_20260816.server.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\joinasync_on_b160_r1_20260816.server.log
```

Stato macchina a fine banco (2026-08-16 20:05 circa): processi_llama = 0, RAM libera = 87,9 GB
(92.222.016 KB). Nessuna invocazione di nvidia-smi in questa undicesima parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita (`ctrl-c`) su
entrambe le repliche. Nessun commit git eseguito. Nessuna build avviata da questo esecutore.

---

## Mandato n.2 — fix del runner per NMAX3, modifica autorizzata esplicitamente — DOCUMENTAZIONE DELLA MODIFICA

**Autorizzazione**: il divieto assoluto originale "non modificare nessun file oltre al ledger
indicato" e' stato **esplicitamente e consapevolmente sospeso dal coordinatore, limitatamente a
UN solo file** (`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1`),
per la sola modifica descritta qui sotto. Ogni altro file resta sotto il divieto originale. Il
conflitto era stato segnalato esplicitamente da questo esecutore prima di qualunque azione; la
sospensione e' arrivata come messaggio dedicato, nominando il file esatto e la modifica esatta.

### Diagnosi (sotto-fase 1 del mandato n.2) -- CORREZIONE all'ipotesi del mandato

Il mandato ipotizzava un problema di **ordine** fra la riga 62 (`$env:PORTO_SPEC_NMAX = '2'`) e
l'applicazione di `-Extra`. **Non e' quello il problema.** Lettura completa del file:

- Il blocco `-Extra` (righe 84-90 originali) usa `[Environment]::SetEnvironmentVariable($Matches[1], $Matches[2])`
  senza scope esplicito (= scope Processo per difetto in .NET), quindi **sovrascrive correttamente**
  qualunque `$env:X` impostato prima, incluso `PORTO_SPEC_NMAX` alla riga 62. L'ordine, di per se',
  non era il difetto.
- **Il vero difetto era alla riga 114 originale**: l'argomento CLI del binario e' costruito con un
  **letterale hardcoded indipendente**, non con la variabile d'ambiente:
  ```powershell
  '-ngld', '99', '--spec-draft-n-max', '2', '--spec-draft-ubatch-size', '16', '-otd', $otd,
  ```
  `$env:PORTO_SPEC_NMAX` non viene letto **da nessuna parte** in questo file per costruire
  `$argsServer`: e' impostato alla riga 62 e mai piu' consultato. E' per questo che nessuna
  combinazione di variabili d'ambiente via `-Extra` avrebbe mai potuto funzionare (a differenza
  del runner A, `dopo_il_riavvio.ps1`, che LEGGE `$env:PORTO_SPEC_NMAX` per costruire il suo
  argomento CLI -- i due runner si comportano diversamente su questo punto).

### Modifica applicata (minima, comportamento invariato quando non specificato)

Nuovo parametro `-SpecNmax` (default `2`, identico al valore precedente), che sostituisce **sia**
l'assegnazione della riga 62 (per coerenza del manifesto/env) **sia** -- il fix vero -- il
letterale hardcoded della riga 114:

```powershell
# param block: aggiunta riga finale
    [string] $ServerPath = 'D:\llama-overlap\build\bin\llama-server.exe',
    [int] $SpecNmax = 2
)

# riga ~62 (era $env:PORTO_SPEC_NMAX = '2')
$env:PORTO_SPEC_NMAX = "$SpecNmax"

# riga ~114 (era '--spec-draft-n-max', '2', ...) -- QUESTO e' il fix che conta
'-ngld', '99', '--spec-draft-n-max', "$SpecNmax", '--spec-draft-ubatch-size', '16', '-otd', $otd,
```

Verificato dopo la modifica: `[System.Management.Automation.Language.Parser]::ParseFile(...)`
sul file modificato -- **sintassi OK, zero errori di parsing**. Nessun'altra riga toccata.
Comportamento per tutti i bracci precedenti di questa sessione (che non passavano `-SpecNmax`)
**invariato**, perche' il default resta `2` in entrambi i punti.

Diff salvato in:
```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\runner_specnmax.patch
```
(la cartella non e' sotto controllo versione git; diff in formato unified scritto a mano dal
confronto diretto fra il contenuto letto prima e dopo le tre modifiche puntuali).

---

## Banco L0 corretto — nmax3fix_graphs_b1200_r1/r2/r3_20260816 — PROMOSSO: L0 PAGA (+4,01%)

Rilancio con il runner corretto (`-SpecNmax 3`). Cancello nuovo obbligatorio per ogni replica: la
riga del **motore** (`common_speculative_impl_draft_dflash`), non l'intenzione.

```text
tag R1/R2/R3     = nmax3fix_graphs_b1200_r{1,2,3}_20260816
data/ora         = R1 lancio 20:11:44 -> R2 lancio 20:19:03 -> R3 lancio 20:23:00 -> fine 20:27:05
runner           = run_porto_hot.ps1 MODIFICATO (vedi sezione precedente), binario originale
banco            = B1200
comando esatto (R1/R2/R3, identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -SpecNmax 3 -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
  (PORTO_SPEC_NMAX non piu' presente in -Extra: ora inutile, il parametro -SpecNmax lo sostituisce)
```

### CANCELLO CRUCIALE: riga del motore, valore effettivo (tutte e tre PASSATO)

```text
R1: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80
R2: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80
R3: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80
```

**Il fix funziona**: a differenza del tentativo precedente (log del motore fermo a `n_max=2`
nonostante l'intenzione), qui il motore riceve davvero `n_max=3`.

### Altri cancelli (passati su tutte e tre)

manifesto `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` -- PASSATO. Righe `sched-profilo` = 0 su tutte --
PASSATO. Salute: nessun `GGML_ASSERT`/`CUDA error`/`invalid index`, `finish_reason=length` su
tutte, chiusura pulita (`ctrl-c`) su tutte.

### Dati per replica (valuta nuova, nessun vincolo di parita' SHA come da mandato)

|                    | R1                | R2                | R3                |
|---|---|---|---|
| eval t/s           | 16,31              | 16,34              | 16,34              |
| p1                 | 0.90281 (771/854)  | 0.90281 (771/854)  | 0.90281 (771/854)  |
| **mean len accettata** | **2,80**       | **2,80**           | **2,80**           |
| copie/buchi        | domanda 275477, colpi 195401 (70,9%), buchi 80076 | idem | idem |
| SHA output         | `1EDA23452DE9292C817EAF47532724A409DD2FFE3B3EF9E165ED887BA4169089` (identico sulle tre) | | |
| content_chars      | 3782               | 3782               | 3782               |
| finish_reason      | length             | length             | length              |

Le tre repliche sono **bit-identiche fra loro** (SHA, p1, mean len, copie/buchi) -- coerente con la
determinatezza del decode (temperature=0), come gia' osservato in tutti i banchi B1200 di questa
sessione. Lunghezza media accettata **2,80**, contro il riferimento storico n_max=2 **2,47**:
**+13,36%**, esattamente il tipo di cambiamento previsto e legittimo per una speculazione diversa
(il drafter ora puo' proporre fino a 3 token, il target ne accetta di piu' per round quando la
proposta e' buona). Copie/buchi salgono da 216.737/47.906 (n_max=2) a 275.477/80.076 (n_max=3):
+27,1% di domande, +67,2% di copie -- come previsto dal mandato, non un errore: piu' token
speculativi verificati per ciclo significa piu' route esperti da calcolare, anche per i token poi
scartati.

### MEDIANA e VERDETTO

```text
valori ordinati  : 16,31 / 16,34 / 16,34
MEDIANA          : 16,34   (elemento centrale vero, v[1])
media            : 16,33
spread max-min   : 0,18 %   (banco molto stabile)

riferimento (truth_graphs, stesso binario e regime) = 15,71 t/s
delta mediana vs riferimento = +4,01 %
delta media vs riferimento   = +3,95 %
```

**+4,01% e' SOPRA la soglia del +3%.** Per il mandato: **"L0 paga e domani si sweepa (n_max=4,
conf)"**. Il verdetto storico "NMAX3-5 peggiora" **non regge** nel regime corretto (grafi CUDA
riparati, banco `truth_graphs`): con il costo fisso per ciclo crollato, l'ottimo di n_max si e'
davvero spostato, come ipotizzato dal coordinatore.

### Nota richiesta dal mandato: il run "nmax3" inerte come replica truth_graphs

Il tentativo precedente (`nmax3_graphs_b1200_r1_20260816`, sezione precedente di questo ledger,
16,02 t/s) aveva la leva NMAX inerte (motore fermo a `n_max=2`) mentre tutti gli altri parametri
(profiler spento, grafi accesi, binario originale) coincidevano esattamente con `truth_graphs`. Va
quindi registrato **come una replica extra della configurazione `truth_graphs`**, non come un punto
dati per n_max: aggiungendolo alle tre repliche gia' note di quel banco (15,71/15,84/15,86 --
mediana 15,71), la nuova quaterna e' 15,71/15,84/15,86/16,02, mediana fra i due centrali
15,84 (a 4 valori la "mediana" e' la media dei due centrali: (15,84+15,86)/2 = 15,85 -- non
ricalcolata formalmente qui, riportata solo come nota, il riferimento ufficiale per questo banco
resta la mediana di 3 gia' promossa, 15,71).

### Percorsi file

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax3fix_graphs_b1200_r{1,2,3}_20260816.server.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax3fix_graphs_b1200_r{1,2,3}_20260816.summary.json
```

Stato macchina a fine banco (2026-08-16 20:27 circa): processi_llama = 0, RAM libera = 87,8 GB
(92.064.868 KB). Nessuna invocazione di nvidia-smi in questa tredicesima parte (unica invocazione
dell'intera sessione resta quella di preflight, 16:15 circa). Chiusura pulita su tutte e tre le
repliche (`ctrl-c`). Nessun commit git eseguito. Nessuna build avviata da questo esecutore
(solo la modifica dello script runner, documentata sopra e autorizzata esplicitamente).

---

## Retrofit — variabili complete dei banchi truth_clean/truth_clean2

Ricostruzione a posteriori dell'ambiente **effettivo** dei run di stasera, ottenuta unendo
il runner (`run_porto_hot.ps1`, letto per intero) e il manifesto stampato nel log del server.
Sola lettura: nessun run, nessuna build, nessun commit.

### Fonti

```text
runner       = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1
log stasera  = ...\work\runs\truth_clean2_b1200_r{1,2,3}_20260816.server.log
log SOTA     = D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.server.log
runner SOTA  = C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\dopo_il_riavvio.ps1
               (dichiarato "runner storico" in docs\porto\HANDOFF_14_AGOSTO.md:25-57; la porta
                8099 del log SOTA e la terna di uscite <tag>.server.log/.hw.csv/.output.html
                corrispondono a quello script e a nessun altro in D:\ds4_work\llama_run)
```

### Ambiente impostato dal runner (run_porto_hot.ps1:37-82)

```text
LLAMA_CACHE_BOZZA_SLOT=12                      LLAMA_ACCEPTMOE=1
LLAMA_CACHE_ESPERTI_BATCH=8                    LLAMA_ACCEPTMOE_ESATTE=1
LLAMA_CACHE_ESPERTI_BATTITO=45                 LLAMA_ACCEPTMOE_SOGLIA=0.75
LLAMA_CACHE_ESPERTI_CODA_MAX=0                 LLAMA_ACCEPTMOE_COMPATTA=1
LLAMA_CACHE_ESPERTI_CURA=0                     LLAMA_CKPT_CRONO=0
LLAMA_CACHE_ESPERTI_SCUDO=0                    LLAMA_SPEC_CONF_ESENTA_POS0=1
LLAMA_CACHE_ESPERTI_MASSA=2                    LLAMA_SPEC_DRAFT_TOPK=1
LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE=0         PORTO_SPEC_NMAX=2
LLAMA_CACHE_ESPERTI_MASSA_CORSIE=0             PORTO_SPEC_CONF_MIN=0.8
LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO=0          LLAMA_MAPPED_IBRIDO=1
LLAMA_CACHE_ESPERTI_LRU=1                      LLAMA_MAPPED_IBRIDO_SOGLIA=2
LLAMA_CACHE_ESPERTI_W=0                        LLAMA_OVERLAP_ASYNC=1
LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1              LLAMA_OVERLAP_K=2
LLAMA_CACHE_ESPERTI_SLOT=473                   LLAMA_OVERLAP_BATCH_MAX=3
LLAMA_CACHE_ESPERTI_FORK=2                     LLAMA_OVERLAP_GRIGLIA_VARIABILE=0
LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8             LLAMA_OVERLAP_PIN=1
LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT=0          LLAMA_OVERLAP_JOIN_ASYNC=0
LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA=0  LLAMA_KV_RING=1
LLAMA_VRAM_A_FASI=0                            LLAMA_KV_RING_VRAM_TOKEN=2048
LLAMA_VRAM_ZAVORRA=0                           LLAMA_KV_ROLLBACK_PARZIALE=1
LLAMA_DSV4_INDEXER_FUSO=0                      LLAMA_KV_ROLLBACK_SOLO_ANELLO=0
LLAMA_DSV4_HC_FUSO=5                           LLAMA_GRAPH_REUSE_PER_TAGLIA=1
GGML_CUDA_GRAPH_OPT=0                          GGML_SCHED_PROFILO=1  (poi sovrascritta da -Extra)
```

Il runner **non** imposta affatto: `GGML_CUDA_DISABLE_GRAPHS`, `GGML_CUDA_GRAPH_STATS`,
`LLAMA_OVERLAP_FINESTRA`, `LLAMA_CACHE_ESPERTI_SPIN`, `LLAMA_CACHE_ESPERTI_PF_TUTTI`,
`LLAMA_CACHE_ESPERTI_DMA`, `LLAMA_CACHE_ORACOLO`, `LLAMA_GRAPH_REUSE_DISABLE`,
`LLAMA_DSV4_TOPK_FUSO`, `GGML_OP_OFFLOAD_MIN_BATCH`. Tutte queste restano al difetto —
che nel log si legge come `(D)` — **tranne** quelle riportate dentro `-Extra`.

`-Extra` (run_porto_hot.ps1:84-90) applica le coppie `NOME=VALORE` separate da `;`
**dopo** il blocco comune, quindi sovrascrive. `-Extra` di truth_clean2:

```text
LLAMA_SCHED_PROFILO=0        (variabile INESISTENTE: nessun codice la legge, no-op)
GGML_CUDA_GRAPH_STATS=0
LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0
LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0
LLAMA_DSV4_DECODE_GATE_UP_FUSO=0
LLAMA_DSV4_DECODE_EXPERT_REUSE=0
LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0
GGML_CUDA_DISABLE_GRAPHS=0   <-- NON e' un no-op: vedi sezione successiva
GGML_SCHED_PROFILO=0
```

(truth_clean, il primo run, aveva lo stesso `-Extra` **senza** `GGML_SCHED_PROFILO=0` finale:
il profiler e' quindi rimasto ACCESO a 1 e il run vale 12,82 t/s. `LLAMA_SCHED_PROFILO=0` era
un refuso e non spegne nulla.)

### Argomenti del server (run_porto_hot.ps1:112-118)

```text
-m C:/ds4-models/DS4-0731-IQ2XXS.gguf   -md D:/ds4-models/DSpark-draft-Q2K.gguf
--spec-type draft-dspark  --fit off  -ngld 99  --spec-draft-n-max 2
--spec-draft-ubatch-size 16  --spec-draft-conf-min 0.8
-otd 'blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'
-ot  'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'
-c 10000  -ub 64  -np 1  -ngl 99  -t 7  --no-mmap  -lv 4
--host 127.0.0.1  --port 8100  --cache-ram 8192  --ctx-checkpoints 32
```

Nessun `--seed` e nessun `-b` in nessuno dei due banchi: `n_batch` resta 2048 per difetto,
il campionamento e' `temperature=0`. Il runner SOTA non passa `--cache-ram`/`--ctx-checkpoints`,
ma il log prova che i valori efficaci sono gli stessi (8192 MiB / max 32): sono i difetti.

---

## Diff variabili vs SOTA 14/8

Metodo: estratte le righe 1-465 (dall'inizio fino a `listening on`) dei due log, tolto il
timbro temporale, e diffate riga per riga. Il diff completo e' di **49 righe** e non contiene
nessuna altra differenza oltre a quelle in tabella.

### Tabella

| variabile / parametro | log SOTA 14/8 | lanciatore SOTA (`dopo_il_riavvio.ps1`) | `dopo_il_riavvio.ps1` (stato odierno) | banco stasera (runner + `-Extra`) | esito |
|---|---|---|---|---|---|
| `GGML_CUDA_DISABLE_GRAPHS` | `<spento>` (D) | non impostata | non impostata | **`0` (E)** | **DIVERSA — decisiva** |
| `GGML_SCHED_PROFILO` | `1` (E) | `'1'` (riga 129) | `'1'` (riga 129) | `1` poi **`0`** via `-Extra` | **DIVERSA** (sfavorisce la SOTA) |
| `GGML_CUDA_GRAPH_STATS` | `0` (D) | non impostata | non impostata | `0` (E) | stesso valore, no-op (gate `atoi != 0`) |
| `LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA` | `0` (D) | non impostata | non impostata | `0` (E) | stesso valore, no-op (gate `atoi != 0`) |
| **build del binario** | **95 (`963a2cfca`)** | — | — | **10093 (`3014d3756`)** | **DIVERSA — seconda variabile** |
| `LLAMA_CACHE_ESPERTI_FORK` | `2` (E) | `'2'` (riga 116) | `'2'` | `2` (E) | identica |
| `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI` | `8` (E) | `'8'` (riga 116) | `'8'` | `8` (E) | identica |
| `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` | `1` (E) | `'1'` (riga 114) | `'1'` | `1` (E) | identica |
| `LLAMA_OVERLAP_JOIN_ASYNC` | `0` (E) | `'0'` (riga 122) | `'0'` | `0` (E) | identica |
| `LLAMA_OVERLAP_ASYNC` | `1` (E) | `'1'` | `'1'` | `1` (E) | identica |
| `LLAMA_OVERLAP_K` | `2` (E) | `'2'` | `'2'` | `2` (E) | identica |
| `LLAMA_OVERLAP_FINESTRA` | `0` (D) | non impostata | non impostata | `0` (D) | identica |
| `LLAMA_OVERLAP_BATCH_MAX` | `3` (E) | `'2'` poi `3` via EXTRA | `'2'` | `3` (E) | identica nel log |
| `LLAMA_OVERLAP_PIN` / `_GRIGLIA_VARIABILE` / `_SPIN` / `_VERIFICA` / `_CERCA_CPU` | 1 / 0 / 2000000 / 0 / 0 | idem | idem | 1 / 0 / 2000000 / 0 / 0 | identiche |
| `LLAMA_SPEC_DRAFT_TOPK` | `1` (E) | `'1'` (riga 118) | `'1'` | `1` (E) | identica |
| `PORTO_SPEC_NMAX` (`--spec-draft-n-max`) | `n_max=2` nel log | via env | via env | `2` | identica |
| `PORTO_SPEC_CONF_MIN` (`--spec-draft-conf-min`) | `conf_min=0.80` nel log | via env | via env | `0.8` | identica |
| `LLAMA_ACCEPTMOE` / `_ESATTE` / `_SOGLIA` / `_COMPATTA` / `_BATCH_MAX` / `_SPIA` | 1 / 1 / 0.75 / 1 / 8 / 0 | `'0'` poi 1 via EXTRA | `'0'` | 1 / 1 / 0.75 / 1 / 8 / 0 | identiche nel log |
| `LLAMA_CACHE_ESPERTI_MASSA` | `2` (E) | `'0'` poi 2 via EXTRA | `'0'` | `2` (E) | identica nel log |
| `MASSA_AMMISSIONE` / `MASSA_CORSIE` (copy-all / corsie stabili) | `ammissione=0, corsie=0` | via EXTRA | non impostate | `ammissione=0, corsie=0` | identiche |
| `LLAMA_CACHE_ESPERTI_SLOT` | `473` (E) | arg 2 = `473` | difetto `'512'` | `473` (E) | identica |
| `LLAMA_CACHE_BOZZA_SLOT` | `12` (E) | `'32'` poi 12 via EXTRA | `'32'` | `12` (E) | identica nel log |
| `LLAMA_CACHE_ESPERTI_SPIN` / `PF_TUTTI` / `CURA` / `SCUDO` / `LRU` / `W` / `CODA_MAX` / `PREFETCH_FILTRO` / `BATCH` / `BATTITO` | 256 / 1 / 0 / 0 / 1 / 0 / 0 / 0 / 8 / 45 | idem | idem | 256 / 1 / 0 / 0 / 1 / 0 / 0 / 0 / 8 / 45 | identiche |
| `LLAMA_CACHE_ESPERTI_DMA` / `DOMANDA_DMA` / `FATE` / `FORK_ESATTO` / `FORK_DOWN_TARDI` / `FORK_STADI` / `FORK_PRIORITA` / `FORK_SERIALE` | tutte `0` (D) | non impostate | non impostate | tutte `0` (D) | identiche |
| `LLAMA_DSV4_HC_FUSO` / `INDEXER_FUSO` / `TOPK_FUSO` | 5 / 0 / 0 | idem | idem | 5 / 0 / 0 | identiche |
| `LLAMA_GRAPH_REUSE_PER_TAGLIA` / `_DISABLE` | 1 / 0 | via EXTRA / non impostata | — | 1 / 0 | identiche |
| `LLAMA_KV_RING` / `_VRAM_TOKEN` / `ROLLBACK_PARZIALE` / `ROLLBACK_SOLO_ANELLO` / `POSMIN_VERO` / `ROLLBACK_MARGINE` | 1 / 2048 / 1 / 0 / 0 / 4 | idem | idem | 1 / 2048 / 1 / 0 / 0 / 4 | identiche |
| `LLAMA_MAPPED_IBRIDO` / `_SOGLIA` | 1 / 2 | idem | idem | 1 / 2 | identiche |
| `LLAMA_VRAM_A_FASI` / `LLAMA_VRAM_ZAVORRA` | 0 / 0 | idem | idem | 0 / 0 | identiche |
| `GGML_CUDA_GRAPH_OPT` | `0` (E) | `'0'` (riga 126) | `'0'` | `0` (E) | identica (e no-op: gate `== 1`) |
| `LLAMA_CKPT_CRONO` / `LLAMA_SPEC_CONF_ESENTA_POS0` | 0 / 1 | via EXTRA | 0 / 0 | 0 / 1 | identiche nel log |
| `LLAMA_REAP*`, `LLAMA_RING*`, `LLAMA_STREAM*`, `GGML_*` diagnostiche | tutte a difetto | — | — | tutte a difetto | identiche |
| thread (`-t`) | `n_threads = 7 / 16` | `-t 7` | `-t 7` | `-t 7` | identici |
| `n_batch` / `n_ubatch` / `n_ctx` | 2048 / 64 / 10240 | `-ub 64 -c 10000` | idem | `-ub 64 -c 10000` | identici |
| draft: `n_max` / `n_min` / `p_min` / `conf_min` / `block_size` / `n_extract` / ubatch | 2 / 0 / 0.00 / 0.80 / 5 / 3 / 16 | idem | idem | **identici** | identici |
| `--cache-ram` / `--ctx-checkpoints` | 8192 / 32 (difetto) | non passati | non passati | 8192 / 32 (espliciti) | identici |
| seed | non passato | non passato | non passato | non passato | identico (`temperature=0`) |
| porta | 8099 | `$PORTA = 8099` | 8099 | 8100 | irrilevante |

### La leva decisiva: `GGML_CUDA_DISABLE_GRAPHS=0` **spegne** i CUDA graph

> **[CHIUSA 18/8]** Bonifica applicata: cancello A VALORE in `common.cuh` (overlap +
> subtract), DLL overlap ricompilata (`1ED035D3…` → `06BF8AAF…`). Banco di verifica a tre
> bracci in coda (macchina contesa la mattina del 18/8). Cronaca: `LEDGER_18_AGOSTO.md`.

Verificato nel sorgente, non dedotto —
`D:\llama-overlap\ggml\src\ggml-cuda\common.cuh:1266`:

```cpp
static const bool disable_cuda_graphs_due_to_env = (getenv("GGML_CUDA_DISABLE_GRAPHS") != nullptr);
return !(disable_due_to_gpu_arch || disable_cuda_graphs_due_to_env);
```

Il cancello e' sulla **presenza** della variabile (`!= nullptr`), non sul suo valore: scriverla
a `0` la definisce, e i grafi vengono **disabilitati**. La trappola era gia' documentata in casa
(`docs\porto\lettura\02-grafo-e-modello.md:525-526` e `:705-706`), ed e' il comportamento opposto
a quello della cugina `GGML_CUDA_GRAPH_OPT`, che invece e' `atoi(env) == 1`.

Tutti e tre i run di stasera (r1/r2/r3) e anche `truth_clean` hanno `GGML_CUDA_DISABLE_GRAPHS=0(E)`:
hanno girato **senza CUDA graph**. La SOTA del 14/8 ha `<spento>(D)`, cioe' con i grafi accesi.

### Prova che il lavoro e' identico e a cambiare e' solo il costo di lancio

| grandezza | SOTA 14/8 b1 | stasera truth_clean2 r1 |
|---|---|---|
| domanda / colpi / buchi (finale) | 216.737 / 168.831 (77,9%) / 47.906 | **216.737 / 168.831 (77,9%) / 47.906** |
| copie / zero-copy / CPU / partizioni | 47.906 / 0 / 110.338 / 55.169 | **47.906 / 0 / 110.338 / 55.169** |
| draft acceptance | 0,90025 (713/792), mean len 2,47 | **0,90025 (713/792), mean len 2,47** |
| SHA256 dell'uscita | `4FDCFADF...C65D` (3578 byte) | **`4FDCFADF...C65D` (3578 byte)** |
| graph nodes / splits (bs=1) | 11.791 / 45 | **11.791 / 45** |
| eval | 74.804,71 ms / 1200 tok = 62,34 ms/tok = **16,04 t/s** | 88.972,26 ms / 1200 tok = 74,14 ms/tok = **13,49 t/s** |

Stessa domanda, stessi colpi, stesse copie, stessa bozza, stessa uscita byte per byte, stesso
grafo — e **+11,80 ms per token**. Su 11.791 nodi per token fa **circa 1,0 us di sovraccarico per
nodo**, che e' esattamente l'ordine di grandezza di un lancio di kernel individuale su WDDM
contro il replay di un grafo catturato. Il precedente in casa: `CACHE_ESPERTI_MISURE.txt:28`
misura 8,04 verso 3,99 t/s spegnendo i grafi in un altro regime.

### La seconda variabile: il binario NON e' lo stesso

```text
SOTA 14/8   : build 95    (963a2cfca) with MSVC 19.44.35227.0
stasera     : build 10093 (3014d3756) with MSVC 19.44.35227.0
```

`D:\llama-overlap\build\bin\llama-server.exe` risulta riscritto il **2026-08-16 alle 02:30**,
cioe' dopo la SOTA. Nel diff dei log si vedono due altre impronte dello stesso fatto:
la riga `cache-esperti: FORK/JOIN acceso` e' emessa **prima** di `warming up` nella SOTA e
**dopo** stasera (ordine del codice cambiato), e la VRAM libera al carico della bozza passa
da 389 a 495 MiB (e da 216,78 a 323,00 MiB dopo). Quindi il gap 16,04 verso 13,49 ha **due**
candidati, non uno; la variabile d'ambiente e' il candidato piu' probabile per taglia
dell'effetto, ma l'attribuzione va fatta con un A/B che tolga `GGML_CUDA_DISABLE_GRAPHS`
dall'`-Extra` **a binario fermo**.

### Nota sul `FORK` e la bit-esattezza — la premessa non e' violata

Il fatto delicato ipotizzato dal coordinatore non si verifica: `LLAMA_CACHE_ESPERTI_FORK=2(E)`
e `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8(E)` compaiono in **entrambi** i log, e in entrambi la riga
`cache-esperti: FORK/JOIN acceso (livello 2, blocchi copia 8, esatto 0: ...)` e' presente. Non
c'e' nessun run con FORK0 stasera, quindi lo SHA identico non falsifica la non-bit-esattezza
del FORK.

C'e' pero' un fatto vicino che va registrato: lo **stesso SHA d'uscita** (`4FDCFADF...`, 3578
byte) e gli **stessi contatori della cache** al singolo evento si ottengono su **due build
diverse** (95 e 10093). O le modifiche fra le due build non toccano l'aritmetica, oppure una
delle due premesse su cosa il binario e' autorizzato a cambiare va rivista. Non risolto qui:
segnalato.

### Verifica sulle repliche

| run | `GGML_CUDA_DISABLE_GRAPHS` | `GGML_SCHED_PROFILO` | t/s |
|---|---|---|---:|
| `truth_clean_b1200_r1` | `0(E)` grafi spenti | `1(E)` acceso | 12,82 |
| `truth_clean2_b1200_r1` | `0(E)` grafi spenti | `0(E)` spento | 13,49 |
| `truth_clean2_b1200_r2` | `0(E)` grafi spenti | `0(E)` spento | 13,44 |
| `truth_clean2_b1200_r3` | `0(E)` grafi spenti | `0(E)` spento | 13,50 |
| `mass2_copyall_stablelane_t473_d12_b1` (14/8) | `<spento>(D)` grafi ACCESI | `1(E)` acceso | 16,04 |

A pari strumentazione (profiler ACCESO in tutti e due) il confronto e' **16,04 contro 12,82**,
cioe' -20,1%: la sonda non spiega niente, anzi la SOTA la pagava e andava comunque piu' forte.

---

## Cancello lungo L0 — certificazione n_max=3 sul banco ctx150k (neuraforge prefill)

Nuovo mandato: le leve grosse (n_max=3, gia' promossa sul banco corto B1200 con +4,01%) si
certificano anche sul prompt lungo (regola dell'utente), non solo sul banco corto. Riferimento
storico della base lunga: `sota100k_ctx150k_densefa_stage_hc5_resident*` — prefill 116,1985 t/s
(mediana 111,09), decode 7,9492 t/s, p1 .61702 (RUNBOOK SS12.5).

### FASE 1 — Ricognizione (riassunto; dettaglio gia' riportato al coordinatore in chat)

Lanciatore identificato: `C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1`
(non `docs\porto\prefill_100k.ps1`, che e' un braccio diverso: ctx 104k, tag fisso `p100k`,
n_max hardcoded `1`, shutdown sempre `Stop-Process -Force`). Confermato con la sola copia
esistente sul disco (nessun'altra versione trovata sotto `C:\Users\imanu\Documents\Codex`).

Tre fatti verificati leggendo il file per intero e i log storici, non assunti:
1. **n_max era un letterale hardcoded**, riga 191 originale: `'--spec-draft-n-max', '2'`, nessuna
   lettura di `$env:PORTO_SPEC_NMAX` da nessuna parte nel file. Log storico
   (`sota100k_ctx150k_densefa_stage_hc5_resident_f2_b2048.server.log`) conferma
   `common_speculative_impl_draft_dflash: - n_max=2` -- coerente col letterale.
2. **Wildcard `blk\..*=CPU` presente nel codice** (righe 25-29 originali), attivata da
   `$BlockDenseCpu`, il cui **default era `1` (ATTIVO)**. Verificato sul summary storico
   (UTF-16LE) che il run che ha prodotto la baseline citata dal mandato dichiara esplicitamente
   `block-dense-cpu=0`: la wildcard vietata (RUNBOOK SS10.4.1) NON era in uso in quel run, ma
   SOLO perche' invocato con l'override esplicito -- coi soli default, lo stesso script
   l'avrebbe attivata. Nessuna riga `CPU model buffer` diffusa nel log storico (solo 4
   occorrenze totali di righe buffer/tensor, tutte `CUDA0_Mapped`), coerente con l'assenza.
3. **Lo script attuale non e' bit-per-bit quello che ha prodotto la baseline storica**: il tag
   interno che il codice ATTUALE costruirebbe e' `sota_ctx${Context}_...` (parametrico), ma i
   file storici sul disco si chiamano `sota100k_ctx150k_..._f2_b2048` (letterale) -- lo script e'
   stato generalizzato dopo quella corsa. n_max=2 resta comunque coerente fra le due versioni
   (verificato sul log), ma non e' garantito che ogni altra riga sia rimasta identica. Segnalato
   al coordinatore, nessuna azione richiesta oltre alla segnalazione.
4. Meccanismo di stop gia' `ctrl-c` pulito (funzione `Stop-Clean`, fallback a `Stop-Process -Force`
   solo dopo 60 s con anomalia implicita) -- log storico conferma `shutdown: ctrl-c`. Nessuna
   modifica necessaria qui.

### Autorizzazione esplicita e dedicata (ricevuta dal coordinatore, stesso pattern di `run_porto_hot` di ieri notte)

Il divieto di modifica e' stato sospeso **per un solo file**,
`C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1`, per
**due modifiche esatte, nominate dal coordinatore**:
1. Riga 191: sostituire il letterale `'--spec-draft-n-max', '2'` con un parametro `-SpecNmax`
   (default 2) nel blocco `param()` -- stesso pattern usato per `run_porto_hot.ps1`.
2. Default di sicurezza: `$BlockDenseCpu` da default `1` a default `0` -- "uno script il cui
   DEFAULT attiva la wildcard vietata... e' una mina, e va disinnescata ora" (testuale dal
   coordinatore).

### Modifiche applicate (verificate: nessun'altra riga toccata)

Verificato **prima** della modifica (rilettura del file) e **dopo** (rilettura integrale delle
269 righe, confrontata riga per riga con la lettura originale): solo tre righe cambiate, tutte
dentro il perimetro autorizzato.

```powershell
# blocco param() -- era:
    [string] $RunLabel = 'pin',
    [ValidateSet(0, 1)]
    [int] $BlockDenseCpu = 1,
    [int] $Packetizer = -1,
    [int] $PrefixChars = 0,
    [int] $Context = 150000,
    [int] $MaxTokens = 64
)
# ora:
    [string] $RunLabel = 'pin',
    [ValidateSet(0, 1)]
    [int] $BlockDenseCpu = 0,
    [int] $Packetizer = -1,
    [int] $PrefixChars = 0,
    [int] $Context = 150000,
    [int] $MaxTokens = 64,
    [int] $SpecNmax = 2
)

# riga ~191 -- era: '-ngld', '99', '--spec-draft-n-max', '2', '--spec-draft-conf-min', '0.8',
# ora:              '-ngld', '99', '--spec-draft-n-max', "$SpecNmax", '--spec-draft-conf-min', '0.8',
```

Verifica sintattica dopo la modifica: `[System.Management.Automation.Language.Parser]::ParseFile(...)`
-- **sintassi OK, zero errori di parsing**.

Diff reale (non scritto a mano: generato con `git diff --no-index` fra una copia del contenuto
originale, ricostruita dalla lettura fatta prima di modificare, e il file modificato) salvato in:

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\sota100k_specnmax.patch
```

Comportamento per chi invoca lo script senza `-BlockDenseCpu`/`-SpecNmax`: **cambiato
deliberatamente** rispetto a prima (era: wildcard attiva di default, n_max=2 fisso; ora: wildcard
spenta di default, n_max=2 di default ma sostituibile) -- e' esattamente l'effetto voluto
dall'autorizzazione (disinnescare la mina di default, parametrizzare n_max).

### Anomalia: primo tentativo di `longgate_nmax2_r1` ucciso dal timeout del tool (non un guasto)

Primo lancio (come task PowerShell del tool, in foreground rispetto allo strumento) partito
21:16:09: shape 12288 fallita per OOM dopo **37 minuti** (`graph_reserve: failed to allocate
compute buffers` -> `failed to initialize the context` -> `failed to create context`), shutdown
`ctrl-c` **pulito** registrato -- comportamento sano, coerente con "i fallimenti OOM in sequenza
sono attesi" del mandato. Passato al tentativo con shape 8192 (21:53:07); dopo altri ~20 minuti
il task e' stato **ucciso** (status "killed", non da questo esecutore, nessun `TaskStop` chiamato)
-- diagnosi: limite di tempo massimo sui task del tool eseguiti in foreground/background rispetto
allo strumento stesso (osservato empiricamente attorno ai 55-60 minuti), non un guasto del
lanciatore ne' della macchina. **Verificato subito dopo**: zero processi `llama-server`/`llama-cli`
residui, porta 8099 libera, RAM 90,1 GB -- nessun danno, nessun residuo pericoloso. Nessun segno
di `GET_ROWS_Q`/`i01=-1`/`GGML_ASSERT`/`CUDA error` in tutto l'output raccolto.

### Procedura aggiornata, autorizzata dal coordinatore: salto delle shape condannate + lancio staccato

1. **Salto delle shape che sappiamo gia' fallire**: `-StartBatch` esiste gia' come parametro
   dello script (default 12288, `ValidateSet(1024, 2048, 4096, 8192, 12288)`) -- verificato
   sulla lettura del file, **nessuna modifica aggiuntiva necessaria**. Passando `-StartBatch 2048`
   il ciclo `foreach ($shape in $shapes)` filtra a `Batch -le 2048`, quindi prova direttamente
   2048 (la shape che nella baseline storica aveva successo).
2. **Lancio staccato**: processo avviato **non come figlio** del tool, con
   `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=...}`,
   cosi' sopravvive a qualunque timeout del tool. Da quel momento in poi seguito **solo tramite i
   file su disco**, con chiamate brevi (secondi) ogni 90 s, cercando il segnale di fine
   (`DONE tag=...`) o errori critici (`GET_ROWS_Q`, `i01=-1`, `GGML_ASSERT`, `CUDA error`).

### `longgate_nmax2_r1` -- riancoraggio del riferimento -- PROMOSSO (SHA identico allo storico)

```text
tag              = longgate_nmax2_r1
tag interno file = sota_ctx150000_densefa_stage_hc5_resident_f2_b2048  (nome diverso dal summary,
                    vedi FASE 1: lo script attuale usa un pattern parametrico per i file di log)
lancio           = staccato, Win32_Process.Create, PID 15016, avviato 22:20:05
comando esatto   = powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1' -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -RunLabel resident -BlockDenseCpu 0 -Packetizer -1 -PrefixChars 0 -Context 150000 -MaxTokens 64 -SpecNmax 2 *> '...\longgate_nmax2_r1.launcher.out'"
```

**Cancelli**:

| cancello | atteso | ottenuto | esito |
|---|---|---|---|
| riga motore | `n_max=2` | `common_speculative_impl_draft_dflash: - n_max=2, n_min=0, p_min=0.00, conf_min=0.80` | PASSATO |
| manifesto graphs | `<spento>(D)` | `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` | PASSATO |
| sched-profilo | richiesto 0 | **259 righe**, manifesto `GGML_SCHED_PROFILO=1(E)` | **NON conforme al cancello letterale -- vedi nota sotto** |
| salute | 0 assert/CUDA-error/GET_ROWS_Q/i01=-1 | 0 trovati | PASSATO |
| shutdown | pulito | `ctrl-c` | PASSATO |
| processi post-braccio | 0 | 0 (verificato) | PASSATO |

**Nota onesta sul profiler**: questo lanciatore imposta `GGML_SCHED_PROFILO='1'` dentro
`Set-SotaEnvironment` (riga propria dello script) e **non offre un meccanismo `-Extra`** per
sovrascriverlo dall'esterno (a differenza di `run_porto_hot.ps1`) -- non e' stato spento perche'
il mandato non ha autorizzato una terza modifica al file. **Verificato pero' che e' strutturale,
non un difetto introdotto ora**: il log storico backuppato
(`sota100k_ctx150k_densefa_stage_hc5_resident_f2_b2048.server.log`, pre-lancio) ha **260** righe
`sched-profilo` con lo stesso manifesto -- praticamente identico. Per la regola del runbook
SS4.4/SS8.2 ("confrontabili solo se stesso verdetto sul profiler, entrambi 0 o entrambi >0"), il
confronto fra `longgate_nmax2_r1` e la baseline storica, e fra `longgate_nmax2_r1` e
`longgate_nmax3_r1` (stesso lanciatore), **resta valido a pari strumentazione** perche' tutti i
lati hanno il profiler ACCESO allo stesso modo.

**Riga cache-esperti VERBATIM** (identica in entrambe le occorrenze del log, prefill e decode):
```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
```
**Nota onesta**: il mandato anticipava "a ctx150k gli slot saranno MENO di 473". Osservato invece
**473 slot pieni**, identici al banco corto -- non forzato per farlo combaciare con l'attesa.
Spiegazione plausibile (non verificata a fondo): `LLAMA_VRAM_A_FASI=2` rialloca la cache esperti
**dopo** aver liberato il buffer di calcolo del prefill (vedi `vram-a-fasi: fase=decode ... cache
0 -> 473 slot (+473, +3194 MiB) ... VRAM libera 0 MiB`), quindi in fase di decode non c'e'
contesa con il buffer di prefill e la capienza piena e' raggiungibile.

**Metriche**:

| campo | valore |
|---|---|
| decode t/s | **8,26** (8.258661271007797 preciso) |
| prefill t/s | 124,14 (124.14278661695427 preciso) |
| p1 | 0.61702 (29 accepted / 47 generated) |
| **mean len accettata** | **1,85** |
| copie/buchi (ultima riga, totale) | domanda 14672 (colpi 9681 = 66,0%, buchi 4991, miss 34,0%, in ritardo 0 = 0,0%) |
| finish_reason | length |
| output chars | 266 |
| SHA output | `D556C4C30669464AB3E05C7F3037348EC063DEFA5558ADD51C0BAE731B722C31` |
| usage | prompt=101597, completion=64, total=101661 |

**Confronto con la baseline storica** (RUNBOOK SS12.5, media di 3 repliche: prefill 116,1985 t/s
-- 110,70/111,09/126,80 -- mediana 111,09; decode 7,9492 t/s; p1 .61702):

```text
SHA output      : IDENTICO byte per byte (D556C4C3...) -- stessa traiettoria esatta
p1               : IDENTICO (0.61702)
prefill          : 124,14 t/s -- dentro il range delle tre repliche storiche (110,70-126,80)
decode           : 8,26 t/s -- sopra la media storica (7,9492), dentro la variabilita' plausibile
                    di UNA sola replica contro una media di tre
```

**Esito**: PROMOSSO come riancoraggio del riferimento. Nonostante le differenze strutturali
trovate in Fase 1 (script generalizzato, naming dei file cambiato), la configurazione EFFETTIVA
(dopo le due modifiche autorizzate) riproduce **esattamente** la baseline storica: stesso SHA di
output, stesso p1. Le due modifiche al file non hanno alterato il comportamento quando i
parametri passati coincidono con quelli storici.

Backup di sicurezza fatti prima che i lanci successivi sovrascrivessero i file (stesso tag
interno per ogni `RunLabel=resident`, indipendentemente da `SpecNmax`):
```text
D:\ds4_work\llama_run\backup_baseline_ctx150k_pre_longgate\   (i 15 file storici originali, pre-sessione)
D:\ds4_work\llama_run\backup_longgate_nmax2_r1\               (i file di questo braccio, pre-nmax3)
```

Percorsi file di questo braccio (posizione originale, prima di essere sovrascritti da nmax3):
```text
D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_resident_f2_b2048.server.log  (backup)
D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_resident_f2_b2048.output.txt  (backup)
D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_resident_f2_b2048.response.json  (backup)
D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_resident.summary.txt  (backup)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\longgate_nmax2_r1.launcher.out  (originale, non sovrascritto)
```

### `longgate_nmax3_r1` -- PROMOSSO (cancelli passati)

Stesso lancio staccato (Win32_Process.Create, PID 9516, avviato 22:40:38), comando identico a
`longgate_nmax2_r1` salvo `-SpecNmax 3`. Backup fatto **subito dopo** il completamento (stesso
tag interno di nmax2, sovrascriverebbe altrimenti al lancio successivo).

```text
comando esatto   = powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1' -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -RunLabel resident -BlockDenseCpu 0 -Packetizer -1 -PrefixChars 0 -Context 150000 -MaxTokens 64 -SpecNmax 3 *> '...\longgate_nmax3_r1.launcher.out'"
caricamento      = shape 2048 diretta, riuscito in 2 min, free VRAM=487 MiB
richiesta        = 22:42:38 -> completa in 13,76 min
```

**Cancelli**:

| cancello | atteso | ottenuto | esito |
|---|---|---|---|
| riga motore | `n_max=3` | `common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80` | PASSATO |
| manifesto graphs | `<spento>(D)` | `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` | PASSATO |
| sched-profilo | -- | `GGML_SCHED_PROFILO=1(E)` -- stesso stato di nmax2_r1 e della baseline storica | pari strumentazione OK |
| salute | 0 assert/CUDA-error/GET_ROWS_Q/i01=-1 | 0 trovati | PASSATO |
| shutdown | pulito | `ctrl-c` | PASSATO |
| processi post-braccio | 0 | 0 (verificato) | PASSATO |

**Riga cache-esperti VERBATIM** (identica a `longgate_nmax2_r1`, entrambe le occorrenze):
```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
```

**Metriche**:

| campo | valore |
|---|---|
| decode t/s | **10,09** (10.086105396964681 preciso) |
| prefill t/s | 124,11 (124.11085870147866 preciso) |
| p1 | 0.88095 (37 accepted / 42 generated) |
| **mean len accettata** | **2,48** |
| copie/buchi (ultima riga, totale) | domanda 15468 (colpi 9705 = 62,7%, buchi 5763, miss 37,3%, in ritardo 0 = 0,0%) |
| finish_reason | length |
| output chars | 282 |
| SHA output | `5E51A3D056195F3386E0B3EDBEBDFC4CD03FE30E5FA785F74E3390E17A38BA44` (diverso da nmax2 -- atteso, non e' un cancello) |
| usage | prompt=101597, completion=64, total=101661 |

### Confronto R1 vs R1 (una sola replica per lato finora) -- delta grande, richiede r2 per conferma

```text
                    nmax2_r1         nmax3_r1         delta
decode t/s          8,26             10,09            +22,15 %
prefill t/s         124,14           124,11            -0,02 %  (invariato, atteso: n_max non tocca il prefill)
p1                  0.61702          0.88095           +42,8 % relativo (base campionaria piccola: 47 vs 42 generated)
mean len             1,85             2,48             +34,1 %
copie/buchi          14672/9681/4991  15468/9705/5763   +5,4% domande, +15,5% buchi
```

**+22,15% e' ben sopra la soglia del +5%** che il mandato usa per richiedere una seconda replica
di conferma per ENTRAMBI i lati (la stessa regola vale anche nel caso opposto, dentro ±3%: qui
non si applica, il delta e' grande). Il salto di p1 (.617 -> .881) e' molto piu' marcato di
quanto osservato sul banco corto B1200 (dove n_max=3 manteneva p1 sostanzialmente pari a n_max=2:
.90025 -> .90281) -- **non interpretato oltre con un solo campione per lato**: la base
campionaria e' piccola (completion=64 token, 42-47 eventi di draft), quindi il rumore statistico
puo' essere rilevante. Procedo con le repliche r2 di entrambi come richiesto dal mandato prima di
trarre un verdetto.

### `longgate_nmax2_r2` -- PROMOSSO, bit-esatto rispetto a nmax2_r1

Lancio staccato, PID 9280, `-RunLabel resident_r2` (per non sovrascrivere r1 durante il lancio;
backup fatto comunque subito dopo, dato che nmax3_r2 riusera' lo stesso RunLabel). Comando identico
a `longgate_nmax2_r1` salvo `-RunLabel resident_r2`.

**Cancelli**: motore `n_max=2` (`common_speculative_impl_draft_dflash: - n_max=2, n_min=0,
p_min=0.00, conf_min=0.80`) PASSATO; `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` PASSATO;
`GGML_SCHED_PROFILO=1(E)` (stesso stato di tutti i bracci precedenti, pari strumentazione OK);
0 errori/assert; `shutdown: ctrl-c`; 0 processi post-braccio.

Riga cache-esperti VERBATIM: identica a tutti i bracci precedenti (473 slot, stessa stringa
integrale).

**Metriche e confronto con `longgate_nmax2_r1`**:

| campo | nmax2_r1 | nmax2_r2 | note |
|---|---:|---:|---|
| decode t/s | 8,26 | **8,35** | |
| prefill t/s | 124,14 | 120,96 | |
| p1 | 0.61702 (29/47) | 0.61702 (29/47) | **identico** |
| mean len | 1,85 | 1,85 | **identico** |
| copie/buchi | 14672/9681/4991 | 14672/9681/4991 | **identico** |
| SHA output | `D556C4C3...` | `D556C4C3...` | **identico, bit-esatto** |

Le due repliche sono bit-esatte su ogni campo tranne il timing (decode/prefill t/s, che e'
l'unica cosa che puo' legittimamente variare per rumore di misura fra ripetizioni con lo stesso
carico deterministico). MEDIANA nmax2 (2 repliche, media dei due centrali) = **(8,26+8,35)/2 =
8,305 t/s**.

### `longgate_nmax3_r2` -- PROMOSSO, bit-esatto rispetto a nmax3_r1

Lancio staccato, PID 13624, comando identico a `longgate_nmax3_r1` salvo `-RunLabel resident_r2`.
Backup fatto subito dopo.

**Cancelli**: motore `n_max=3` (`common_speculative_impl_draft_dflash: - n_max=3, n_min=0,
p_min=0.00, conf_min=0.80`) PASSATO; `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` PASSATO;
`GGML_SCHED_PROFILO=1(E)` (pari strumentazione con tutti gli altri bracci); 0 errori/assert;
`shutdown: ctrl-c`; 0 processi post-braccio. Riga cache-esperti VERBATIM identica (473 slot).

**Metriche e confronto con `longgate_nmax3_r1`**:

| campo | nmax3_r1 | nmax3_r2 | note |
|---|---:|---:|---|
| decode t/s | 10,09 | **10,00** | |
| prefill t/s | 124,11 | 122,25 | |
| p1 | 0.88095 (37/42) | 0.88095 (37/42) | **identico** |
| mean len | 2,48 | 2,48 | **identico** |
| copie/buchi | 15468/9705/5763 | 15468/9705/5763 | **identico** |
| SHA output | `5E51A3D0...` | `5E51A3D0...` | **identico, bit-esatto** |

**Determinismo confermato su entrambi i lati**: sia nmax2 (r1/r2 bit-esatte) sia nmax3 (r1/r2
bit-esatte) sono completamente deterministici a parita' di n_max su questo banco -- il salto di
p1 fra i due lati (.617 -> .881) **non e' rumore campionario**, e' un effetto riproducibile legato
alla profondita' di speculazione. MEDIANA nmax3 (2 repliche, media dei due) = **(10,09+10,00)/2 =
10,045 t/s**.

### VERDETTO PROVVISORIO dopo le r2 (prima della coppia m256)

```text
MEDIANA nmax2 (r1=8,26 / r2=8,35)   = 8,305 t/s
MEDIANA nmax3 (r1=10,09 / r2=10,00) = 10,045 t/s
delta = (10,045-8,305)/8,305 = +20,95 %
```

**Le repliche NON hanno ribaltato il quadro**: il delta resta a **+20,95%**, anzi confermato con
determinismo bit-esatto su entrambi i lati (stesso SHA/p1/mean-len fra r1 e r2 per ciascun n_max).
Per l'istruzione del coordinatore ("se le r2 ribaltano il quadro sotto il 5%, fermati; altrimenti
procedi con la coppia -MaxTokens 256"): **procedo con la coppia m256** per allargare la base
campionaria (64 -> 256 token di completion) prima del verdetto finale.

### `longgate_nmax2_m256_r1` / `longgate_nmax3_m256_r1` -- coppia finale, base 4x piu' larga

`-RunLabel resident_m256`, `-MaxTokens 256` (invece di 64), altrimenti comandi identici alle
rispettive r1. Lancio staccato: nmax2 PID 15268 (23:37:37), nmax3 PID 960 (a seguire).

**`longgate_nmax2_m256_r1`**:

| cancello | ottenuto | esito |
|---|---|---|
| riga motore | `n_max=2, n_min=0, p_min=0.00, conf_min=0.80` | PASSATO |
| manifesto graphs | `<spento>(D)` | PASSATO |
| sched-profilo | `GGML_SCHED_PROFILO=1(E)` (pari a tutti gli altri bracci) | pari strumentazione OK |
| salute | 0 assert/CUDA-error/GET_ROWS_Q/i01=-1 | PASSATO |
| shutdown | `ctrl-c` | PASSATO |
| cache-esperti | 473 slot, riga identica | -- |

| campo | valore |
|---|---|
| decode t/s | **8,94** (8.944116010215717 preciso) |
| prefill t/s | 122,27 |
| p1 | 0.64972 (115 accepted / 177 generated) |
| mean len | 1,83 |
| copie/buchi (finale) | domanda 54384 (colpi 37302 = 68,6%, buchi 17082, miss 31,4%) |
| SHA output | `7F9A1B9D59C0FDCF809475E02F6FE66E12DA4DD919FE9B4D4F9F91599112BBC28` |
| completion | 256 token, finish=length, 1138 caratteri |

Nota: con base 4x piu' larga (177 vs 47 eventi di draft), p1 converge leggermente piu' in alto
(.650 contro .617 a 64 token) ma resta nello stesso ordine di grandezza -- coerente, non
contraddittorio.

**`longgate_nmax3_m256_r1`**:

| cancello | ottenuto | esito |
|---|---|---|
| riga motore | `n_max=3, n_min=0, p_min=0.00, conf_min=0.80` | PASSATO |
| manifesto graphs | `<spento>(D)` | PASSATO |
| sched-profilo | `GGML_SCHED_PROFILO=1(E)` (pari a tutti gli altri bracci) | pari strumentazione OK |
| salute | 0 assert/CUDA-error/GET_ROWS_Q/i01=-1 | PASSATO |
| shutdown | `ctrl-c` | PASSATO |
| cache-esperti | 473 slot, riga identica | -- |

| campo | valore |
|---|---|
| decode t/s | **9,06** (9.056177236180645 preciso) |
| prefill t/s | 120,99 |
| p1 | 0.71264 (124 accepted / 174 generated) |
| mean len | 1,95 |
| copie/buchi (finale) | domanda 57616 (colpi 38540 = 66,9%, buchi 19076, miss 33,1%) |
| SHA output | `86ADC2E5FC5B7BF2AB08DC79DD1CF5347E269BDD6C3C4D10CADE8C96BCF99F3B` |
| completion | 256 token, finish=length, 1173 caratteri |

### VERDETTO FINALE -- scoperta cruciale: il delta crolla con la base campionaria piu' larga

```text
                     nmax2            nmax3            delta
base 64 (mediana 2 repliche)   8,305 t/s        10,045 t/s       +20,95 %
base 256 (1 replica ciascuno)  8,94 t/s          9,06 t/s        **+1,34 %**
```

**Il vantaggio di n_max=3 sul banco lungo NON e' quello che sembrava dopo le sole r1/r2 a 64
token.** Quando la base campionaria del decode passa da 64 a 256 token (4x), il delta **crolla da
+20,95% a +1,34%** -- ben **dentro** la soglia del 3% che il runbook (SS8.3) classifica come "non
distingue: dentro la deriva di banco". Il grande vantaggio osservato a 64 token (peraltro
bit-esatto e riproducibile su due repliche per lato -- non era rumore di misura in senso stretto)
era un **artefatto del segmento specifico dei primi 64 token generati**, non un effetto stabile
della profondita' di speculazione a contesto lungo.

**Confronto con il banco corto B1200** (dove n_max=3 vale +4,01%, promosso stanotte): sul banco
lungo, con la misura piu' affidabile disponibile (256 token), il delta e' **+1,34%** -- piu'
debole del banco corto e dentro la banda di rumore. **Il vantaggio non trasferisce in modo
riproducibile e affidabile sul prompt lungo**: ne' si inverte (resta leggermente positivo), ne'
si conferma con la stessa forza del banco corto -- si **affievolisce fino a diventare
indistinguibile dal rumore**.

### Tabella completa di tutti i bracci lunghi

| tag | n_max | tokens | decode t/s | prefill t/s | p1 (acc/gen) | mean len | SHA output |
|---|---:|---:|---:|---:|---|---:|---|
| baseline storica (RUNBOOK SS12.5, media 3 rep.) | 2 | 64 | 7,9492 | 116,1985 | .61702 | -- | `D556C4C3...` |
| `longgate_nmax2_r1` | 2 | 64 | 8,26 | 124,14 | .61702 (29/47) | 1,85 | `D556C4C3...` |
| `longgate_nmax2_r2` | 2 | 64 | 8,35 | 120,96 | .61702 (29/47) | 1,85 | `D556C4C3...` |
| `longgate_nmax3_r1` | 3 | 64 | 10,09 | 124,11 | .88095 (37/42) | 2,48 | `5E51A3D0...` |
| `longgate_nmax3_r2` | 3 | 64 | 10,00 | 122,25 | .88095 (37/42) | 2,48 | `5E51A3D0...` |
| `longgate_nmax2_m256_r1` | 2 | 256 | 8,94 | 122,27 | .64972 (115/177) | 1,83 | `7F9A1B9D...` |
| `longgate_nmax3_m256_r1` | 3 | 256 | 9,06 | 120,99 | .71264 (124/174) | 1,95 | `86ADC2E5...` |

Riga cache-esperti VERBATIM: **identica su tutti i sette bracci** (473 slot, stessa stringa
integrale) -- nessuna riduzione di slot osservata a ctx150k, diversamente da quanto anticipato dal
mandato (spiegazione plausibile: `LLAMA_VRAM_A_FASI=2` rialloca la cache esperti a piena capienza
dopo la fase di prefill, quando il buffer di calcolo prefill e' gia' stato liberato).

### Riepilogo backup fatti durante questo banco (nessun artefatto perso)

```text
D:\ds4_work\llama_run\backup_baseline_ctx150k_pre_longgate\   (15 file storici originali)
D:\ds4_work\llama_run\backup_longgate_nmax2_r1\
D:\ds4_work\llama_run\backup_longgate_nmax3_r1\
D:\ds4_work\llama_run\backup_longgate_nmax2_r2\
D:\ds4_work\llama_run\backup_longgate_nmax3_r2\
D:\ds4_work\llama_run\backup_longgate_nmax2_m256_r1\
D:\ds4_work\llama_run\backup_longgate_nmax3_m256_r1\
```

Stato macchina a fine catena (2026-08-17 00:11 circa): processi_llama = 0, RAM libera 89,4 GB.
Tutti i lanci di questa catena sono stati fatti come processi **staccati**
(`Invoke-CimMethod`/`Win32_Process.Create`), seguiti solo tramite i file su disco, per
sopravvivere al limite di tempo del tool osservato sul primo tentativo (~55-60 min). Chiusura
pulita (`ctrl-c`, mai `RISERVA Stop-Process`) su tutti i sei bracci completati con successo.
Nessun commit git eseguito. Uniche modifiche a file diversi dal ledger: le due autorizzate
esplicitamente su `sota100k_ctx150k.ps1` (diff in
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\sota100k_specnmax.patch`).

---

## Sweep L0, punto n_max=4 — nmax4_graphs_b1200_r1/r2/r3_20260816 — RESPINTO: la curva ha girato, resta n_max=3

Prossimo punto del sweep annunciato dal banco `nmax3fix_graphs` ("L0 paga e domani si sweepa
n_max=4"). Turno nuovo, contesto fresco: preflight completo di §1 rieseguito per intero
all'inizio di questa sessione (nessuna delle verifiche precedenti riusata per assunzione).

### Preflight (§1 del runbook, eseguito per intero)

```text
data/ora         = 2026-08-16 20:45:44
uptime_min       = 2663,2  (macchina non appena riavviata: nessun lancio a freddo §2 richiesto)
processi llama   = 0
porta 8000 (UI)  = nessun processo in ascolto (non toccata)
ram_libera_gb    = 87,5
gpu a riposo     = NVIDIA GeForce RTX 3060, SM 210 MHz, mem 405 MHz, 12,99 W, vram_usata 584 MiB,
                    vram_libera 11532 MiB, PCIe gen1 x16 a riposo (risparmio energetico, non un
                    cancello: solo width=16 e' controllato dal runbook, PASSATO)
porte 8099/8100  = entrambe libere
disco_c_gb       = 48,4      disco_d_gb = 120,4
sha_llama_server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485
sha_ggml_cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330
sha_jprompt      = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9  (Length=252, coincide)
```

Unica invocazione di `nvidia-smi` di tutta la sessione, come da regola vitale del mandato: quella
di preflight sopra. Verificato anche il codice del runner (`run_porto_hot.ps1`, letto per intero)
prima di lanciare: il parametro `-SpecNmax` (default 2) esiste davvero, imposta sia
`$env:PORTO_SPEC_NMAX` sia — il punto che conta, dal fix del mandato n.2 della sessione precedente —
l'argomento CLI `--spec-draft-n-max "$SpecNmax"` passato al binario.

### Anomalia iniziale (recuperata, nessun impatto sulla misura)

Il primissimo tentativo di lancio di R1 e' fallito con `PSSecurityException: L'esecuzione di
script e' disabilitata` — causato dall'aver invocato `powershell.exe` da dentro il tool Bash
(Git Bash), che ha una execution policy di sistema diversa da quella della shell PowerShell
primaria di questa sessione (verificata poi: scope Process = `Bypass`). L'errore e' avvenuto al
caricamento dello script, **prima** di qualunque avvio di `llama-server.exe`: nessun processo mai
avviato, nessun ripristino necessario. Rilanciato con lo strumento PowerShell corretto,
riuscito al primo colpo. Non e' un'anomalia del banco o della macchina.

```text
tag R1/R2/R3     = nmax4_graphs_b1200_r{1,2,3}_20260816
data/ora         = R1 lancio 20:47:14 -> R2 lancio 20:52:08 -> R3 lancio 20:56:24 -> fine 20:59:56
runner           = B (run_porto_hot.ps1), binario originale D:\llama-overlap (nessun -ServerPath)
banco            = B1200
ripetizioni      = 3 (incatenate senza QUIETE fissa, come da mandato: verificata solo la chiusura
                    pulita — processi llama=0 — fra una replica e l'altra, nessuna nvidia-smi
                    aggiuntiva)
leva variata     = -SpecNmax 4 (n_max del motore di speculazione, unica leva rispetto al
                    riferimento n_max=3)
comando esatto (R1/R2/R3, identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -SpecNmax 4 -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

### CANCELLO CRUCIALE (a): riga del motore, valore EFFETTIVO (tutte e tre PASSATO)

```text
R1: common_speculative_impl_draft_dflash: - n_max=4, n_min=0, p_min=0.00, conf_min=0.80
R2: common_speculative_impl_draft_dflash: - n_max=4, n_min=0, p_min=0.00, conf_min=0.80
R3: common_speculative_impl_draft_dflash: - n_max=4, n_min=0, p_min=0.00, conf_min=0.80
```

### Altri cancelli (b, c, d — passati su tutte e tre)

| cancello | atteso | R1 | R2 | R3 |
|---|---|---|---|---|
| (b) manifesto `GGML_CUDA_DISABLE_GRAPHS` | `<spento>(D)` | `<spento>(D)` | `<spento>(D)` | `<spento>(D)` |
| (c) righe `sched-profilo` | 0 | 0 | 0 | 0 |
| (d) `finish_reason` | `length` | `length` | `length` | `length` |
| (d) GGML_ASSERT / CUDA error / invalid index | assenti | assenti | assenti | assenti |
| (d) divergenze | tutte a zero | `taglia=0 ids=0 out=0 GRIGLIA-corta=0` | idem | idem |
| (d) MORTO / RICHIESTA FALLITA / CONTESA | assenti | assenti | assenti | assenti |
| riga `cache-esperti` | identica al riferimento | identica (verbatim sotto) | identica | identica |
| chiusura | `ctrl-c` | `ctrl-c` | `ctrl-c` | `ctrl-c` |

Riga cache-esperti (identica sulle tre repliche, verbatim, identica a tutti i banchi B1200 di
questa serie):
```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
```
`sfratto_par=1` confermato anche dal manifesto (`LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1(E)`).
`build 10093 (3014d3756) with MSVC 19.44.35227.0` su tutte e tre, invariato.

### Dati per replica (valuta non-parity: cambiare n_max cambia legittimamente traiettoria/SHA/p1, non sono cancelli)

|                        | R1                 | R2                 | R3                 |
|---|---|---|---|
| eval t/s               | 13,54              | 13,70              | 13,71              |
| ms/token               | 73,88              | 72,98              | 72,92              |
| prompt t/s             | 22,01              | 19,52              | 20,67              |
| wall_ms (richiesta)    | 91.828,9           | 91.203,9           | 90.873,1           |
| p1                     | 0.79955 (706/883)  | 0.79955 (706/883)  | 0.79955 (706/883)  |
| **mean len accettata** | **2,43**           | **2,43**           | **2,43**           |
| copie/buchi            | domanda 284301, colpi 200559 (70,5%), buchi 83742 | idem | idem |
| SHA output             | `D56BBF5010861E9DA187BA32A8CECDA557742BC743BDE3929F1ABF8B845C6535` (identico sulle tre) | | |
| content_chars          | 2292               | 2292               | 2292               |
| finish_reason          | length             | length             | length             |

Le tre repliche sono **bit-identiche fra loro** (SHA, p1, mean len, copie/buchi), coerente con la
determinatezza del decode (temperature=0) gia' osservata su tutti i banchi B1200 di questa
sessione.

**Il quadro rispetto a n_max=3 e' coerente e negativo su tutta la linea**: p1 crolla da 0,90281
(n_max=3) a **0,79955** (n_max=4), mean len accettata scende da 2,80 a **2,43** — il drafter perde
precisione oltre 3 token proposti, non ne guadagna. Le domande alla cache esperti salgono
ulteriormente (275.477 -> 284.301, +3,2%) e le copie pure (80.076 -> 83.742, +4,6%), mentre il
tasso di colpi peggiora leggermente (70,9% -> 70,5%): piu' lavoro speculativo sprecato *e* piu'
trasporto da pagare, la doppia penalita' gia' vista fra n_max=2 e n_max=3 ma qui senza il
compenso di un'accettazione migliore.

### MEDIANA e VERDETTO

```text
valori ordinati  : 13,54 / 13,70 / 13,71
MEDIANA          : 13,70   (elemento centrale vero, v[1] su array ordinato a 3 -- non [int](Count/2))
media            : 13,65
spread max-min   : 1,26 %   (banco stabile, ben sotto la soglia del 5%)

riferimento n_max=3 (nmax3fix_graphs, stesso binario e regime, ledger sopra) = 16,34 t/s
delta mediana vs n_max=3 = -16,16 %

riferimento n_max=2 (truth_graphs, stesso binario e regime, ledger sopra)    = 15,71 t/s
delta mediana vs n_max=2 = -12,79 %
```

**-16,16% e' ben SOTTO la soglia del -3%.** Per il mandato: **"sotto −3% → la curva ha girato,
resta n_max=3."** n_max=4 e' anche peggiore di n_max=2 (-12,79%), quindi non e' nemmeno un
ripiegamento verso il vecchio ottimo: la curva ha un massimo netto a n_max=3 e scende bruscamente
oltre quel punto. Non si segnala n_max=5 come prossimo campione: il mandato non lo richiede in
questo ramo del verdetto (solo nel caso "sopra +3%").

### ENV COMPLETO (tutte le variabili, non solo quelle cambiate — regola vitale del mandato)

Catturato integralmente da `nmax4_graphs_b1200_r1_20260816.server.log` (tutte le righe
`server_manif:`; R2 e R3 verificate identiche riga per riga, stesso comando salvo `-Tag`).
**Coincide esattamente** con l'ENV gia' trascritto per esteso nella sezione `truth_graphs` sopra
(nessuna riga manifesto porta `PORTO_SPEC_NMAX` o `SpecNmax` — coerente con quanto gia' osservato
nel banco `nmax3_graphs_b1200_r1`: quella leva non e' tracciata nel manifesto, solo nella riga del
motore e negli argomenti CLI del server):

```text
server_manif: manifesto: E=ambiente D=difetto; LLAMA_MANIFESTO=1(D)
server_manif: manifesto/cache: LLAMA_CACHE_BOZZA_BATTITO=60(D) LLAMA_CACHE_BOZZA_SLOT=12(E) LLAMA_CACHE_ESPERTI_BATCH=8(E) LLAMA_CACHE_ESPERTI_BATTITO=45(E) LLAMA_CACHE_ESPERTI_CODA_MAX=0(E) LLAMA_CACHE_ESPERTI_CURA=0(E) LLAMA_CACHE_ESPERTI_FORK=2(E) LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8(E) LLAMA_CACHE_ESPERTI_LRU=1(E) LLAMA_CACHE_ESPERTI_MASSA=2(E) LLAMA_CACHE_ESPERTI_PF_TUTTI=1(D) LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO=0(E) LLAMA_CACHE_ESPERTI_SCUDO=0(E) LLAMA_CACHE_ESPERTI_SLOT=473(E) LLAMA_CACHE_ESPERTI_SPIN=256(D) LLAMA_CACHE_ESPERTI_W=0(E) LLAMA_CACHE_ORACOLO=<spento>(D)
server_manif: manifesto/spec: LLAMA_ACCEPTMOE=1(E) LLAMA_ACCEPTMOE_BATCH_MAX=8(D) LLAMA_ACCEPTMOE_COMPATTA=1(E) LLAMA_ACCEPTMOE_ESATTE=1(E) LLAMA_ACCEPTMOE_SOGLIA=0.75(E) LLAMA_ACCEPTMOE_SPIA=0(D) LLAMA_CKPT_CRONO=0(E) LLAMA_SPEC_CONF_ESENTA_POS0=1(E) LLAMA_SPEC_DRAFT_TOPK=1(E)
server_manif: manifesto/compute: LLAMA_DSV4_HC_FUSO=5(E) LLAMA_MAPPED_IBRIDO=1(E) LLAMA_MAPPED_IBRIDO_SOGLIA=2(E) LLAMA_OVERLAP_ASYNC=1(E) LLAMA_OVERLAP_CERCA_CPU=0(D) LLAMA_OVERLAP_BATCH_MAX=3(E) LLAMA_OVERLAP_GRIGLIA_VARIABILE=0(E) LLAMA_OVERLAP_K=2(E) LLAMA_OVERLAP_PIN=1(E) LLAMA_OVERLAP_SPIN=2000000(D) LLAMA_OVERLAP_VERIFICA=0(D)
server_manif: manifesto/kv: LLAMA_KV_POSMIN_VERO=0(D) LLAMA_KV_RING=1(E) LLAMA_KV_RING_VRAM_TOKEN=2048(E) LLAMA_KV_RING_VRAM_TRACE=0(D) LLAMA_KV_ROLLBACK_MARGINE=4(D) LLAMA_KV_ROLLBACK_PARZIALE=1(E) LLAMA_KV_ROLLBACK_SOLO_ANELLO=0(E)
server_manif: manifesto/orfane: LLAMA_RING=0(D) LLAMA_RING_BATTITO=60(D) LLAMA_RING_PROFONDITA=380(D)
server_manif: manifesto/vram: LLAMA_VRAM_A_FASI=0(E) LLAMA_VRAM_A_FASI_CALDO=0(D) LLAMA_VRAM_A_FASI_MARGINE=0(D) LLAMA_VRAM_A_FASI_MIN=0(D) LLAMA_VRAM_A_FASI_SLOT=0(D) LLAMA_VRAM_A_FASI_SLOT_MAX=1024(D) LLAMA_VRAM_A_FASI_UB=64(D) LLAMA_VRAM_ZAVORRA=0(E)
server_manif: manifesto/orfane: LLAMA_REAP=0(D) LLAMA_REAP_AMMISSIONE=1.0(D) LLAMA_REAP_DECADIMENTO=1.0(D) LLAMA_REAP_DECADIMENTO_BUSSATE=0.90(D) LLAMA_REAP_DUMP=<spento>(D) LLAMA_REAP_ISTERESI=1(D) LLAMA_REAP_LOCK=0(D) LLAMA_REAP_MARGINE=1.25(D) LLAMA_REAP_MAX_SCAMBI=64(D) LLAMA_REAP_PERIODO=12900(D) LLAMA_REAP_PESO=ripida(D) LLAMA_REAP_PREFETCH=0(D) LLAMA_REAP_PROF=0(D) LLAMA_REAP_SOGLIA=3(D) LLAMA_REAP_THREADS=8(D) LLAMA_REAP_TOPK=2400(D)
server_manif: manifesto/vram: LLAMA_REAP_WS_MIN_GB=0(D)
server_manif: manifesto/diag: LLAMA_DEBUG_DUMP=<spento>(D) LLAMA_DEBUG_FILTER=<tutto>(D) LLAMA_DFLASH_SINKHORN_ITERS=<gguf>(D) LLAMA_DSV4_SINKHORN_ITERS=<gguf>(D) LLAMA_STREAM_GC=60(D) LLAMA_STREAM_MAX_MB=4(D) LLAMA_STREAM_TTL=300(D)
server_manif: manifesto/cache: LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1(E) LLAMA_CACHE_ESPERTI_DMA=0(D) LLAMA_CACHE_ESPERTI_DOMANDA_DMA=0(D) LLAMA_CACHE_ESPERTI_FORK_ESATTO=0(D) LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=0(D) LLAMA_CACHE_ESPERTI_FORK_STADI=0(D) LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA=0(E) LLAMA_CACHE_ESPERTI_FORK_PRIORITA=0(D) LLAMA_CACHE_ESPERTI_FORK_SERIALE=0(D) LLAMA_CACHE_ESPERTI_FATE=0(D)
server_manif: manifesto/compute: LLAMA_OVERLAP_JOIN_ASYNC=0(E) LLAMA_OVERLAP_FINESTRA=0(D) LLAMA_DSV4_INDEXER_FUSO=0(E) LLAMA_DSV4_TOPK_FUSO=0(D) LLAMA_GRAPH_REUSE_DISABLE=0(D) LLAMA_GRAPH_REUSE_PER_TAGLIA=1(E) LLAMA_MMQ_X_IDS=<spento>(D) GGML_SCHED_PROFILO=0(E) GGML_CUDA_GRAPH_OPT=0(E)
server_manif: manifesto/diag: GGML_CUDA_GRAPH_STATS=0(D)
server_manif: manifesto/compute: GGML_CUDA_DISABLE_GRAPHS=<spento>(D) GGML_OP_OFFLOAD_MIN_BATCH=<spento>(D) GGML_CPU_MMID_REUSE_SRC1=0(D)
server_manif: manifesto/diag: GGML_BACKEND_PATH=<spento>(D) GGML_BACKTRACE_LLDB=<spento>(D) GGML_CPU_DISABLE_FUSION=<spento>(D) GGML_CUDA_ALLREDUCE=<spento>(D) GGML_CUDA_CUBLAS_COMPUTE_TYPE=<spento>(D) GGML_CUDA_DISABLE_FUSION=<spento>(D) GGML_CUDA_ENABLE_UNIFIED_MEMORY=<spento>(D) GGML_CUDA_NO_PINNED=<spento>(D) GGML_CUDA_P2P=<spento>(D) GGML_CUDA_PDL=<spento>(D) GGML_CUDA_REGISTER_HOST=<spento>(D) GGML_DISABLE_VULKAN=<spento>(D) GGML_KLEIDIAI_CHUNK_MULTIPLIER=<spento>(D) GGML_KLEIDIAI_SME=<spento>(D) GGML_META_DEBUG=<spento>(D) GGML_NO_BACKTRACE=<spento>(D) GGML_SCHED_DEBUG=<spento>(D) GGML_SCHED_DEBUG_INFO=<spento>(D) GGML_SCHED_DEBUG_REALLOC=<spento>(D) GGML_TOTAL_THREADS=<spento>(D) LLAMA_APP_CMD=<spento>(D) LLAMA_ATTN_ROT_DISABLE=<spento>(D) LLAMA_BATCH_DEBUG=<spento>(D) LLAMA_CACHE=<spento>(D) LLAMA_DSV4_COMPRESS_DEBUG=<spento>(D) LLAMA_GRAPH_INPUT_DEBUG=<spento>(D) LLAMA_GRAPH_RESULT_DEBUG=<spento>(D) LLAMA_KV_CACHE_DEBUG=<spento>(D) LLAMA_MANIFESTO=<spento>(D) LLAMA_MEDIA_MARKER=<spento>(D) LLAMA_SERVER_CHILD_MODE=<spento>(D) LLAMA_SERVER_ROUTER_PORT=<spento>(D) LLAMA_SERVER_SLOTS_DEBUG=<spento>(D) LLAMA_TRACE=<spento>(D)
```

```text
SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (invariato, verificato in preflight)
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (invariato)
build            = build 10093 (3014d3756) with MSVC 19.44.35227.0
snapshot         = porto_hot_snapshot = 0 su tutte e tre repliche
server vivi max  = 1 per replica
esito            = RESPINTO: 3/3 repliche passano tutti i cancelli di identita' e salute, ma il
                    valore di merito e' ben sotto la soglia del mandato. MEDIANA = 13,70 t/s,
                    -16,16% vs n_max=3 (16,34), -12,79% vs n_max=2 (15,71). VERDETTO: la curva ha
                    girato, resta n_max=3 come punto migliore dello sweep L0.
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax4_graphs_b1200_r{1,2,3}_20260816.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax4_graphs_b1200_r{1,2,3}_20260816.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\nmax4_graphs_b1200_r{1,2,3}_20260816.r1.output.txt
```

### Confronto riassuntivo dello sweep L0 (tutti a pari strumentazione: profiler spento, grafi accesi, binario originale)

| n_max | mediana t/s | delta vs n_max=2 | p1 | mean len | domande/copie |
|---:|---:|---:|---|---:|---|
| 2 (`truth_graphs`)     | 15,71 | —      | 0,90025 | 2,47 | 216.737 / 47.906 |
| 3 (`nmax3fix_graphs`)  | 16,34 | +4,01% | 0,90281 | 2,80 | 275.477 / 80.076 |
| 4 (`nmax4_graphs`, questo banco) | 13,70 | -12,79% | 0,79955 | 2,43 | 284.301 / 83.742 |

Lo sweep L0 ha un massimo netto a **n_max=3**: sale da 2 a 3, poi crolla bruscamente a 4. La causa
visibile nei dati e' che a n_max=4 il tasso di accettazione della bozza (p1) cede prima ancora
della lunghezza media accettata (mean len scende insieme a p1, non sale): il drafter smette di
essere affidabile oltre 3 token proposti, quindi il costo extra di verifica (piu' domande, piu'
copie) non viene ripagato da piu' accettazioni. Nessun ulteriore punto (n_max=5) segnalato, come
da mandato per questo ramo del verdetto.

Stato macchina a fine banco (2026-08-16 21:00 circa): processi_llama = 0. Nessuna invocazione di
`nvidia-smi` oltre l'unica di preflight (20:45:44). Chiusura pulita su tutte e tre le repliche
(`ctrl-c`, mai `RISERVA Stop-Process`). Nessun commit git eseguito. Nessuna build avviata. Nessuna
modifica a file diversi da questo ledger.

---

## Sweep L0, manopola conf_min (soglia di confidenza del drafter) — conf07/conf09 — ENTRAMBI RESPINTI, resta conf_min=0.80

Turno nuovo, contesto fresco (rotazione preventiva, non per guasti). Preflight completo di SS1
rieseguito per intero (nessuna verifica precedente riusata per assunzione). Mandato: due punti,
tre repliche ciascuno, n_max=3 fissato (vincitore dello sweep precedente), sweep sulla soglia di
confidenza del drafter conf_min attorno al valore corrente 0.80.

### FASE 1 — Scoperta del meccanismo (conf_min: come raggiunge il motore)

Letti per intero `run_porto_hot.ps1` (runner B) e `dopo_il_riavvio.ps1` (runner A, riscontro),
poi il codice sorgente C++ per verificare, non assumere.

**Il motore legge `params.speculative.draft.conf_min` esclusivamente da:**
1. l'argomento CLI `--spec-draft-conf-min <valore>` (`common/arg.cpp:3776-3783`, handler
   `params.speculative.draft.conf_min = std::stof(value)`), oppure
2. in sua assenza, la variabile d'ambiente `LLAMA_ARG_SPEC_DRAFT_CONF_MIN` (registrata via
   `.set_env(...)`, meccanismo standard llama.cpp).

**Verificato in `common/arg.cpp` righe 627-684**: il parser applica prima tutti i valori da ENV
per ogni opzione, poi scorre gli argomenti effettivi della riga di comando e li applica sempre
per ultimo — con un warning esplicito quando l'argomento CLI sovrascrive un valore da ENV
(`"warn: %s environment variable is set, but will be overwritten by command line argument %s"`,
riga 683). **L'argomento CLI ha quindi sempre precedenza quando presente sulla riga di comando.**

**Nel runner B (`run_porto_hot.ps1`), riga 118 (prima della modifica), l'argomento era
hardcoded**: `'--spec-draft-conf-min', '0.8'` — stringa letterale fissa nell'array
`$argsServer`, non derivata da nessun parametro dello script ne' da `-Extra`.

**La variabile `$env:PORTO_SPEC_CONF_MIN`** (impostata a riga 64 del runner B, sovrascrivibile
con `-Extra`) **non e' letta da nessun codice C++** — grep esplicito su tutto l'albero
`D:\llama-overlap` per la stringa `PORTO_SPEC_CONF_MIN`: zero occorrenze. E' una variabile
fantasma. Nel runner A invece funziona, perche' li' viene tradotta a mano in
`--spec-draft-conf-min` (righe 149-151 di `dopo_il_riavvio.ps1`):
```powershell
if ($env:PORTO_SPEC_CONF_MIN -match '^(?:\d+(?:\.\d*)?|\.\d+)$') {
  $a += @('--spec-draft-conf-min', $env:PORTO_SPEC_CONF_MIN)
}
```
Nel runner B questa traduzione non esiste: l'argomento CLI e' scritto fisso nell'array.

**Conclusione**: hardcode confermato nel runner B, non ambiguo. Anche tentare
`LLAMA_ARG_SPEC_DRAFT_CONF_MIN` via `-Extra` non avrebbe funzionato: il runner passa sempre
l'argomento esplicito `--spec-draft-conf-min`, che vince sempre sulla ENV per il meccanismo
verificato sopra. Come da mandato, autorizzata l'aggiunta di un parametro `-SpecConf`.

### Modifica al runner B (autorizzata dal mandato)

Aggiunto il parametro `[string] $SpecConf = '0.80'` al param block (dopo `$SpecNmax`), e
sostituito l'hardcode `'--spec-draft-conf-min', '0.8'` con `'--spec-draft-conf-min', $SpecConf`
nell'array `$argsServer`. Tipo `string` (non `double`) per lo stesso motivo gia' noto dal
runner A: un binding a un parametro `[double]` rischierebbe la formattazione con virgola della
cultura di sistema (`it-IT`) quando riconvertito a stringa. **Verificato empiricamente prima di
qualunque lancio** (test isolato `Test-Param([string]$X) { ... }` chiamato con `-X 0.70` non
quotato su una shell con `Get-Culture` = `it-IT`): il literal numerico del linguaggio PowerShell
mantiene il punto anche senza quote esplicite. Nei comandi reali, comunque, il valore e' sempre
stato passato quotato (`-SpecConf '0.70'` / `'0.90'`) per la massima esplicitezza.

Sintassi del file verificata con `[System.Management.Automation.Language.Parser]::ParseFile`
dopo la modifica: zero errori di parsing.

Diff salvato in
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\runner_specconf.patch`:
```diff
@@ -8,7 +8,8 @@ param(
     [bool] $HardwareProbe = $false,
     [int] $ClockKeeperBlocks = 0,
     [string] $ServerPath = 'D:\llama-overlap\build\bin\llama-server.exe',
-    [int] $SpecNmax = 2
+    [int] $SpecNmax = 2,
+    [string] $SpecConf = '0.80'
 )
 
 $ErrorActionPreference = 'Stop'
@@ -115,7 +116,7 @@ $argsServer = @(
     '-ngld', '99', '--spec-draft-n-max', "$SpecNmax", '--spec-draft-ubatch-size', '16', '-otd', $otd,
     '-c', '10000', '-ub', '64', '-np', '1', '-ngl', '99', '-ot', $ot,
     '-t', '7', '--no-mmap', '-lv', '4', '--host', '127.0.0.1', '--port', "$port",
-    '--spec-draft-conf-min', '0.8', '--cache-ram', '8192', '--ctx-checkpoints', '32'
+    '--spec-draft-conf-min', $SpecConf, '--cache-ram', '8192', '--ctx-checkpoints', '32'
 )
```
Nessun'altra riga del runner toccata. Nessuna altra modifica a file diversi da questo ledger e
dal runner autorizzato.

### Preflight (SS1 del runbook, eseguito per intero)

```text
data/ora         = 2026-08-17 00:21:32
uptime_min       = 2879,9  (macchina non appena riavviata: nessun lancio a freddo SS2 richiesto)
processi llama   = 0
porta 8000 (UI)  = nessun processo in ascolto (non toccata)
ram_libera_gb    = 89,3
gpu a riposo     = NVIDIA GeForce RTX 3060, SM 210 MHz, mem 405 MHz, 12,55 W, vram_usata 365 MiB,
                    vram_libera 11751 MiB, PCIe gen1 x16 a riposo (risparmio energetico, non un
                    cancello: solo width=16 e' controllato dal runbook, PASSATO), throttle 0x1
porte 8099/8100  = entrambe libere
disco_c_gb       = 50,8      disco_d_gb = 120,4
sha_llama_server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (invariato)
sha_ggml_cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (invariato)
sha_jprompt      = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9  (Length=252, coincide)
```

Unica invocazione di `nvidia-smi` di preflight, come da regola vitale del mandato. Riferimento
letto dal ledger di questa sessione (non da un commento in uno script, SS8.4): n_max=3 mediana
16,34 t/s (`nmax3fix_graphs_b1200_r{1,2,3}_20260816`, p1 .90281, mean len 2,80, conf_min=0.80),
sezione sopra in questo stesso file.

### Punto 1 — conf07: n_max=3, conf_min=0.70

```text
tag R1/R2/R3   = conf07_graphs_b1200_r{1,2,3}_20260817
runner         = B (run_porto_hot.ps1, modificato come sopra)
banco          = B1200
ripetizioni    = 3 (incatenate senza QUIETE, come da mandato: verificata solo chiusura pulita
                  fra una replica e l'altra — processi llama=0 — nessuna nvidia-smi aggiuntiva)
leva variata   = -SpecConf 0.70 (unica leva rispetto al riferimento conf_min=0.80)
comando esatto (R1/R2/R3, identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -SpecNmax 3 -SpecConf '0.70' -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

**CANCELLO CRUCIALE: riga del motore, valore EFFETTIVO (tutte e tre PASSATO)**

```text
R1: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.70
R2: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.70
R3: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.70
```

**Altri cancelli (passati su tutte e tre)**

| cancello | atteso | R1 | R2 | R3 |
|---|---|---|---|---|
| manifesto `GGML_CUDA_DISABLE_GRAPHS` | `<spento>(D)` | `<spento>(D)` | `<spento>(D)` | `<spento>(D)` |
| righe `sched-profilo` | 0 | 0 | 0 | 0 |
| `GGML_CUDA_GRAPH_STATS` | `0(D)` | `0(D)` | (non ristampato, manifesto invariato) | (idem) |
| riga `cache-esperti` | identica al riferimento | identica (verbatim sotto) | identica | identica |
| `finish_reason` | `length` | `length` | `length` | `length` |
| GGML_ASSERT / CUDA error / invalid index | assenti | assenti (0 match) | assenti (0 match) | assenti (0 match) |
| divergenze | tutte a zero | `taglia=0 ids=0 out=0 GRIGLIA-corta=0` | idem | idem |
| MORTO / RICHIESTA FALLITA / CONTESA | assenti | assenti | assenti | assenti |
| chiusura | `ctrl-c` | `ctrl-c` | `ctrl-c` | `ctrl-c` |
| build | `10093 (3014d3756)` | invariato | invariato | invariato |

Riga cache-esperti (identica sulle tre repliche, verbatim, identica a tutti i banchi B1200 della
sessione):
```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
```
`sfratto_par=1` confermato anche dal manifesto (`LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1(E)`).

**Dati per replica** (valuta non-parity: cambiare conf_min cambia legittimamente traiettoria,
SHA e p1 — non sono cancelli):

|                        | R1                 | R2                 | R3                 |
|---|---|---|---|
| eval t/s               | 15,41              | 15,46              | 15,47              |
| ms/token                | 64,89              | 64,68              | 64,63              |
| prompt t/s             | 21,71              | 21,27              | 22,13              |
| wall_ms (richiesta)    | 81.091,2           | 80.905,8           | 80.730,3           |
| p1                      | 0.82614 (727/880)  | 0.82614 (727/880)  | 0.82614 (727/880)  |
| **mean len accettata**  | **2,54**           | **2,54**           | **2,54**           |
| copie/buchi             | domanda 289224, colpi 200745 (69,4%), buchi 88479, miss 30,6% | idem | idem |
| SHA output              | `E00220D5A83F1DD84FF24620AED2B12D55CBA12D1E500878AEE8B28CEA0EC9DA` (identico sulle tre) | | |
| content_chars           | 2956               | 2956               | 2956               |
| finish_reason           | length             | length             | length             |

Le tre repliche sono bit-identiche fra loro (SHA, p1, mean len, copie/buchi) — coerente con la
determinatezza del decode (temperature=0) gia' osservata su tutti i banchi B1200 precedenti.

**MEDIANA e VERDETTO — conf07**

```text
valori ordinati  : 15,41 / 15,46 / 15,47
MEDIANA          : 15,46   (elemento centrale, v[1] su array ordinato a 3)
media            : 15,45
spread max-min   : 0,39 %   (banco stabile, ben sotto la soglia del 5%)

riferimento n_max=3 conf_min=0.80 (nmax3fix_graphs, ledger sopra) = 16,34 t/s
delta mediana vs riferimento = -5,39 %
```

**-5,39% e' sotto la soglia del -3%: RESPINTO.** Non e' "molto male" (sotto -8%), quindi si
procede regolarmente con conf09 come da mandato ("le due direzioni sono indipendenti").

Rispetto al riferimento (p1 .90281, mean len 2,80): a soglia piu' bassa (0.70) il drafter viene
troncato meno spesso per bassa confidenza, ma p1 CROLLA a 0.82614 e mean len scende a 2,54 —
il drafter propone blocchi piu' lunghi che il verificatore poi rigetta piu' spesso. Le domande
alla cache esperti salgono (275.477 -> 289.224, +5,0%) e le copie pure (80.076 -> 88.479,
+10,5%): piu' lavoro speculativo sprecato, senza compenso.

### Punto 2 — conf09: n_max=3, conf_min=0.90

```text
tag R1/R2/R3   = conf09_graphs_b1200_r{1,2,3}_20260817
runner         = B (run_porto_hot.ps1, modificato come sopra)
banco          = B1200
ripetizioni    = 3 (incatenate senza QUIETE, come da mandato: verificata solo chiusura pulita)
leva variata   = -SpecConf 0.90 (unica leva rispetto al riferimento conf_min=0.80)
comando esatto (R1/R2/R3, identici salvo -Tag) =
  & 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -SpecNmax 3 -SpecConf '0.90' -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

**CANCELLO CRUCIALE: riga del motore, valore EFFETTIVO (tutte e tre PASSATO)**

```text
R1: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.90
R2: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.90
R3: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.90
```

**Altri cancelli (passati su tutte e tre)**

| cancello | atteso | R1 | R2 | R3 |
|---|---|---|---|---|
| manifesto `GGML_CUDA_DISABLE_GRAPHS` | `<spento>(D)` | `<spento>(D)` | `<spento>(D)` | `<spento>(D)` |
| righe `sched-profilo` | 0 | 0 | 0 | 0 |
| `GGML_CUDA_GRAPH_STATS` | `0(D)` | `0(D)` | (manifesto invariato) | `0(D)` |
| riga `cache-esperti` | identica al riferimento | identica (verbatim sotto) | identica | identica |
| `finish_reason` | `length` | `length` | `length` | `length` |
| GGML_ASSERT / CUDA error / invalid index | assenti | assenti (0 match) | assenti (0 match) | assenti (0 match) |
| divergenze | tutte a zero | `taglia=0 ids=0 out=0 GRIGLIA-corta=0` | (non ristampato) | idem |
| MORTO / RICHIESTA FALLITA / CONTESA | assenti | assenti | assenti | assenti |
| chiusura | `ctrl-c` | `ctrl-c` | `ctrl-c` | `ctrl-c` |
| build | `10093 (3014d3756)` | invariato | invariato | invariato |

Riga cache-esperti (identica sulle tre repliche, e identica a quella di conf07 sopra):
```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
```

**Dati per replica**:

|                        | R1                 | R2                 | R3                 |
|---|---|---|---|
| eval t/s               | 15,50              | 15,47              | 15,43              |
| ms/token                | 64,53              | 64,63              | 64,81              |
| prompt t/s             | 21,37              | 21,73              | 21,77              |
| wall_ms (richiesta)    | 80.705,0           | 80.771,2           | 80.991,6           |
| p1                      | 0.87763 (710/809)  | 0.87763 (710/809)  | 0.87763 (710/809)  |
| **mean len accettata**  | **2,45**           | **2,45**           | **2,45**           |
| copie/buchi             | domanda 259485, colpi 186990 (72,1%), buchi 72495, miss 27,9% | idem | idem |
| SHA output              | `4EA0FACE4282CF56040C8E634CFF2A2852FC29268D3F58DA713F8E19F346F618` (identico sulle tre) | | |
| content_chars           | 3332               | 3332               | 3332               |
| finish_reason           | length             | length             | length             |

Le tre repliche sono bit-identiche fra loro.

**MEDIANA e VERDETTO — conf09**

```text
valori ordinati  : 15,43 / 15,47 / 15,50
MEDIANA          : 15,47   (elemento centrale, v[1] su array ordinato a 3)
media            : 15,47
spread max-min   : 0,45 %   (banco stabile, ben sotto la soglia del 5%)

riferimento n_max=3 conf_min=0.80 (nmax3fix_graphs, ledger sopra) = 16,34 t/s
delta mediana vs riferimento = -5,32 %
```

**-5,32% e' sotto la soglia del -3%: RESPINTO.**

Rispetto al riferimento (p1 .90281, mean len 2,80): a soglia piu' alta (0.90) il drafter viene
troncato piu' spesso per bassa confidenza (esattamente l'effetto atteso), mean len scende a
2,45 (il blocco proposto e' piu' corto in media) e p1 sale rispetto a conf07 (0.87763 contro
0.82614) ma resta comunque sotto il riferimento (.90281). Le domande alla cache esperti CALANO
rispetto al riferimento (275.477 -> 259.485, -5,8%) e anche le copie (80.076 -> 72.495, -9,5%) —
meno lavoro speculativo sprecato, ma il blocco piu' corto vale meno per token generato: il
guadagno di efficienza per domanda non compensa la perdita di lunghezza accettata.

### Confronto riassuntivo dello sweep conf_min (n_max=3 fissato, tutti a pari strumentazione)

| conf_min | mediana t/s | delta vs 0.80 | p1 | mean len | domande/copie |
|---:|---:|---:|---|---:|---|
| 0,70 (`conf07_graphs`, questo banco) | 15,46 | -5,39% | 0,82614 | 2,54 | 289.224 / 88.479 |
| 0,80 (`nmax3fix_graphs`, riferimento) | 16,34 | —      | 0,90281 | 2,80 | 275.477 / 80.076 |
| 0,90 (`conf09_graphs`, questo banco) | 15,47 | -5,32% | 0,87763 | 2,45 | 259.485 / 72.495 |

**Entrambe le direzioni sono RESPINTE.** La curva ha un massimo netto a conf_min=0.80: sia
abbassare la soglia (piu' token bozzati proposti, ma verificati con successo meno spesso) sia
alzarla (blocchi piu' corti e piu' sicuri, ma troppo corti per ripagare l'overhead di
verifica) peggiorano il throughput di circa il 5,3-5,4%. Il valore attuale (0.80) e' gia' vicino
o coincidente con l'ottimo locale per questa manopola, alla risoluzione di 0,10 qui testata.
Nessun punto ulteriore proposto: il mandato prevede un nuovo campione solo per un punto sopra
+3%, e nessuno dei due lo e'.

### ENV completo (manifesto, identico su tutti e sei i bracci — regola vitale del mandato)

Verificato per confronto letterale (dopo normalizzazione del timestamp per riga, che varia
naturalmente run per run): il manifesto e' **carattere per carattere identico** su tutte e tre
le repliche di conf07, su tutte e tre le repliche di conf09, e **fra conf07 e conf09** — coerente
con quanto gia' osservato per `-SpecNmax` nel banco precedente: `conf_min` non e' tracciata nel
manifesto, solo nella riga del motore (cancello cruciale sopra) e negli argomenti CLI del server.

```text
server_manif: manifesto: E=ambiente D=difetto; LLAMA_MANIFESTO=1(D)
server_manif: manifesto/cache: LLAMA_CACHE_BOZZA_BATTITO=60(D) LLAMA_CACHE_BOZZA_SLOT=12(E) LLAMA_CACHE_ESPERTI_BATCH=8(E) LLAMA_CACHE_ESPERTI_BATTITO=45(E) LLAMA_CACHE_ESPERTI_CODA_MAX=0(E) LLAMA_CACHE_ESPERTI_CURA=0(E) LLAMA_CACHE_ESPERTI_FORK=2(E) LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8(E) LLAMA_CACHE_ESPERTI_LRU=1(E) LLAMA_CACHE_ESPERTI_MASSA=2(E) LLAMA_CACHE_ESPERTI_PF_TUTTI=1(D) LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO=0(E) LLAMA_CACHE_ESPERTI_SCUDO=0(E) LLAMA_CACHE_ESPERTI_SLOT=473(E) LLAMA_CACHE_ESPERTI_SPIN=256(D) LLAMA_CACHE_ESPERTI_W=0(E) LLAMA_CACHE_ORACOLO=<spento>(D)
server_manif: manifesto/spec: LLAMA_ACCEPTMOE=1(E) LLAMA_ACCEPTMOE_BATCH_MAX=8(D) LLAMA_ACCEPTMOE_COMPATTA=1(E) LLAMA_ACCEPTMOE_ESATTE=1(E) LLAMA_ACCEPTMOE_SOGLIA=0.75(E) LLAMA_ACCEPTMOE_SPIA=0(D) LLAMA_CKPT_CRONO=0(E) LLAMA_SPEC_CONF_ESENTA_POS0=1(E) LLAMA_SPEC_DRAFT_TOPK=1(E)
server_manif: manifesto/compute: LLAMA_DSV4_HC_FUSO=5(E) LLAMA_MAPPED_IBRIDO=1(E) LLAMA_MAPPED_IBRIDO_SOGLIA=2(E) LLAMA_OVERLAP_ASYNC=1(E) LLAMA_OVERLAP_CERCA_CPU=0(D) LLAMA_OVERLAP_BATCH_MAX=3(E) LLAMA_OVERLAP_GRIGLIA_VARIABILE=0(E) LLAMA_OVERLAP_K=2(E) LLAMA_OVERLAP_PIN=1(E) LLAMA_OVERLAP_SPIN=2000000(D) LLAMA_OVERLAP_VERIFICA=0(D)
server_manif: manifesto/kv: LLAMA_KV_POSMIN_VERO=0(D) LLAMA_KV_RING=1(E) LLAMA_KV_RING_VRAM_TOKEN=2048(E) LLAMA_KV_RING_VRAM_TRACE=0(D) LLAMA_KV_ROLLBACK_MARGINE=4(D) LLAMA_KV_ROLLBACK_PARZIALE=1(E) LLAMA_KV_ROLLBACK_SOLO_ANELLO=0(E)
server_manif: manifesto/orfane: LLAMA_RING=0(D) LLAMA_RING_BATTITO=60(D) LLAMA_RING_PROFONDITA=380(D)
server_manif: manifesto/vram: LLAMA_VRAM_A_FASI=0(E) LLAMA_VRAM_A_FASI_CALDO=0(D) LLAMA_VRAM_A_FASI_MARGINE=0(D) LLAMA_VRAM_A_FASI_MIN=0(D) LLAMA_VRAM_A_FASI_SLOT=0(D) LLAMA_VRAM_A_FASI_SLOT_MAX=1024(D) LLAMA_VRAM_A_FASI_UB=64(D) LLAMA_VRAM_ZAVORRA=0(E)
server_manif: manifesto/orfane: LLAMA_REAP=0(D) LLAMA_REAP_AMMISSIONE=1.0(D) LLAMA_REAP_DECADIMENTO=1.0(D) LLAMA_REAP_DECADIMENTO_BUSSATE=0.90(D) LLAMA_REAP_DUMP=<spento>(D) LLAMA_REAP_ISTERESI=1(D) LLAMA_REAP_LOCK=0(D) LLAMA_REAP_MARGINE=1.25(D) LLAMA_REAP_MAX_SCAMBI=64(D) LLAMA_REAP_PERIODO=12900(D) LLAMA_REAP_PESO=ripida(D) LLAMA_REAP_PREFETCH=0(D) LLAMA_REAP_PROF=0(D) LLAMA_REAP_SOGLIA=3(D) LLAMA_REAP_THREADS=8(D) LLAMA_REAP_TOPK=2400(D)
server_manif: manifesto/vram: LLAMA_REAP_WS_MIN_GB=0(D)
server_manif: manifesto/diag: LLAMA_DEBUG_DUMP=<spento>(D) LLAMA_DEBUG_FILTER=<tutto>(D) LLAMA_DFLASH_SINKHORN_ITERS=<gguf>(D) LLAMA_DSV4_SINKHORN_ITERS=<gguf>(D) LLAMA_STREAM_GC=60(D) LLAMA_STREAM_MAX_MB=4(D) LLAMA_STREAM_TTL=300(D)
server_manif: manifesto/cache: LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1(E) LLAMA_CACHE_ESPERTI_DMA=0(D) LLAMA_CACHE_ESPERTI_DOMANDA_DMA=0(D) LLAMA_CACHE_ESPERTI_FORK_ESATTO=0(D) LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=0(D) LLAMA_CACHE_ESPERTI_FORK_STADI=0(D) LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA=0(E) LLAMA_CACHE_ESPERTI_FORK_PRIORITA=0(D) LLAMA_CACHE_ESPERTI_FORK_SERIALE=0(D) LLAMA_CACHE_ESPERTI_FATE=0(D)
server_manif: manifesto/compute: LLAMA_OVERLAP_JOIN_ASYNC=0(E) LLAMA_OVERLAP_FINESTRA=0(D) LLAMA_DSV4_INDEXER_FUSO=0(E) LLAMA_DSV4_TOPK_FUSO=0(D) LLAMA_GRAPH_REUSE_DISABLE=0(D) LLAMA_GRAPH_REUSE_PER_TAGLIA=1(E) LLAMA_MMQ_X_IDS=<spento>(D) GGML_SCHED_PROFILO=0(E) GGML_CUDA_GRAPH_OPT=0(E)
server_manif: manifesto/diag: GGML_CUDA_GRAPH_STATS=0(D)
server_manif: manifesto/compute: GGML_CUDA_DISABLE_GRAPHS=<spento>(D) GGML_OP_OFFLOAD_MIN_BATCH=<spento>(D) GGML_CPU_MMID_REUSE_SRC1=0(D)
server_manif: manifesto/diag: GGML_BACKEND_PATH=<spento>(D) GGML_BACKTRACE_LLDB=<spento>(D) GGML_CPU_DISABLE_FUSION=<spento>(D) GGML_CUDA_ALLREDUCE=<spento>(D) GGML_CUDA_CUBLAS_COMPUTE_TYPE=<spento>(D) GGML_CUDA_DISABLE_FUSION=<spento>(D) GGML_CUDA_ENABLE_UNIFIED_MEMORY=<spento>(D) GGML_CUDA_NO_PINNED=<spento>(D) GGML_CUDA_P2P=<spento>(D) GGML_CUDA_PDL=<spento>(D) GGML_CUDA_REGISTER_HOST=<spento>(D) GGML_DISABLE_VULKAN=<spento>(D) GGML_KLEIDIAI_CHUNK_MULTIPLIER=<spento>(D) GGML_KLEIDIAI_SME=<spento>(D) GGML_META_DEBUG=<spento>(D) GGML_NO_BACKTRACE=<spento>(D) GGML_SCHED_DEBUG=<spento>(D) GGML_SCHED_DEBUG_INFO=<spento>(D) GGML_SCHED_DEBUG_REALLOC=<spento>(D) GGML_TOTAL_THREADS=<spento>(D) LLAMA_APP_CMD=<spento>(D) LLAMA_ATTN_ROT_DISABLE=<spento>(D) LLAMA_BATCH_DEBUG=<spento>(D) LLAMA_CACHE=<spento>(D) LLAMA_DSV4_COMPRESS_DEBUG=<spento>(D) LLAMA_GRAPH_INPUT_DEBUG=<spento>(D) LLAMA_GRAPH_RESULT_DEBUG=<spento>(D) LLAMA_KV_CACHE_DEBUG=<spento>(D) LLAMA_MANIFESTO=<spento>(D) LLAMA_MEDIA_MARKER=<spento>(D) LLAMA_SERVER_CHILD_MODE=<spento>(D) LLAMA_SERVER_ROUTER_PORT=<spento>(D) LLAMA_SERVER_SLOTS_DEBUG=<spento>(D) LLAMA_TRACE=<spento>(D)
```

Leve fuori dal manifesto, verificate solo sulla riga del motore e sugli argv (non stampate da
nessun manifesto — motivo dichiarato di questo intero banco, SS4.2 del runbook):
`--spec-draft-n-max 3`, `--spec-draft-conf-min 0.70|0.90`.

```text
SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (invariato)
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (invariato)
build            = build 10093 (3014d3756) with MSVC 19.44.35227.0
snapshot         = porto_hot_snapshot = 0 su tutte e sei le repliche
server vivi max  = 1 per replica
esito complessivo = ENTRAMBI I PUNTI RESPINTI. conf_min=0.80 (gia' in uso) resta il valore
                    migliore fra i tre testati per questa manopola a n_max=3.
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\conf07_graphs_b1200_r{1,2,3}_20260817.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\conf07_graphs_b1200_r{1,2,3}_20260817.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\conf09_graphs_b1200_r{1,2,3}_20260817.server.log
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\conf09_graphs_b1200_r{1,2,3}_20260817.summary.json
                    C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\runner_specconf.patch
```

### Postflight e stato macchina a fine banco

```text
POSTFLIGHT (subito dopo l'ultimo shutdown): ram_libera=88,8 GB | vram_usata=365 MiB, vram_libera=11751 MiB | clock SM=210 MHz | potenza=12,78 W | processi_llama=0
```

Tutte e sei le repliche lanciate come task in background del tool (non processi Windows staccati
via WMI), seguite tramite notifica di completamento e file su disco, senza polling attivo ne'
`nvidia-smi` addizionali durante l'esecuzione (coerente con la regola vitale del mandato — la
sola `nvidia-smi` di preflight e la sola di postflight, due invocazioni totali in tutta la
sessione). Chiusura pulita (`ctrl-c`, mai `RISERVA Stop-Process`) su tutte e sei le repliche.
Nessuna QUIETE di 300 s fra i sei bracci (autorizzata dal mandato: "incatena senza quiete, solo
verifica chiusura pulita"); verificato `processi llama = 0` prima di ogni lancio successivo.
Nessun commit git eseguito. Nessuna build avviata. `D:\llama-overlap` non toccato in scrittura.
Nessun invito a `codex`. Uniche modifiche a file diversi da questo ledger: il runner B
(`run_porto_hot.ps1`, diff sopra e in `runner_specconf.patch`), autorizzato esplicitamente dal
mandato per la Fase 1.

---

## Braccio L3 — mappa device-side del decode (Nsight Systems) — 17/8, notte

Esecuzione del `PIANO_L3.md`. Tre archi previsti (L3-0 pilota, L3-A nodo, L3-B grafo) su B1200 al
campione `n_max=3` (mediana 16,34 t/s, `nmax3fix_graphs_b1200_r{1,2,3}_20260816`, righe 1276-1372
sopra in questo stesso file). L3-A **completato e analizzato per intero**. L3-B **non ottenuto a
B1200** dopo tre tentativi (fallimento riproducibile, documentato sotto); ottenuta invece una sonda
diagnostica a B160 che permette comunque la cross-verifica prevista dal piano.

### Preflight

```text
data/ora inizio  = 2026-08-17 ~01:15
processi llama   = 0
porta 8000 (UI)  = nessun listener
porte 8099/8100  = libere
GPU a riposo     = 365 MiB usati, 11751 MiB liberi, SM 210 MHz, PCIe gen1x16 a riposo (normale)
ram libera       = 88,3 GB
uptime            = 2923,8 min
disco C / D      = 50,9 / 120,4 GB liberi
SHA llama-server = C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485
SHA ggml-cuda    = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330
SHA jprompt.txt  = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9 (identico, atteso)
nsys.exe         = presente, versione 2024.5.1.113-245134619542v0
shell            = NON amministratore (verificato, sola lettura: IsInRole Administrator = False)
```

### Verifica flag nsys 2024.5.1 — tre correzioni empiriche al piano

Il piano imponeva di non fidarsi dei flag a memoria (§0.1). Verificato con `--help` e con prove
dirette su un target innocuo prima di toccare il banco vero; **tre correzioni**, tutte riconciliate
prima di qualunque cattura reale:

1. **Il separatore `--` fra opzioni nsys e comando target rompe il parsing.** Con nsys 2024.5.1 su
   questa macchina, `nsys profile <opzioni> -- <exe> <args>` da' `option is ambiguous and matches
   'auto-report-name', 'cpuctxsw', ...` (un `--` isolato viene letto come nome di opzione lunga
   vuoto). **Soluzione verificata**: nessun separatore, il primo argomento che non inizia per `-`
   (il percorso dell'eseguibile) chiude comunque il parsing delle opzioni di nsys — verificato con
   un target di prova che passa correttamente `-NoProfile`/`-Command` al processo figlio.
2. **`--trace=wddm`, `--sample=process-tree`, `--cpuctxsw=process-tree` richiedono privilegi
   amministrativi**, assenti in questa shell e non ottenibili (vietato elevare). Degradano con un
   WARNING e si disattivano da soli (`"...requires administrative privileges, disabling"`), NON
   abortiscono la cattura.
3. **`--gpu-metrics-devices=0` invece FALLISCE IN MODO DURO** (`ERR_NVGPUCTRPERM`, exit 1, nessun
   `.nsys-rep` scritto) — verificato sia con `--gpu-metrics-devices=help` sia con una cattura reale.
   Va escluso del tutto, non solo "provato e tolto se fallisce": includerlo abortirebbe l'intera
   cattura.

**Conseguenza per il disegno**: nessuno dei tre archi ha potuto usare `wddm`, `cpuctxsw` o
`gpu-metrics`. La correlazione con la lane CPU (§5.4 del piano, "la biforcazione principale
dell'arm") e il cross-check hardware-indipendente del busy% **non sono disponibili in questo
ambiente**, non per scelta di disegno ma per il vincolo di privilegi. Registrato come limite
aperto, non come misura mancante per negligenza.

### Copia del runner e patch

Copiato `run_porto_hot.ps1` &rarr; `run_porto_hot_nsys.ps1` (stessa cartella `work\`), originale
intatto. Modifiche, tutte nella sola copia:

- `Start-Process` del server avvolta da `nsys profile` con i flag verificati sopra; parametri
  aggiunti `-NsysGraphGranularity node|graph` (default `node`) e `-NsysOutDir` per servire sia
  L3-0/L3-A sia L3-B dallo stesso file, senza duplicare la logica di setup ambiente/richiesta/shutdown
  gia' testata — estensione minima oltre le due modifiche letteralmente prescritte dal piano
  (avvolgimento + timeout), necessaria perche' L3-A e L3-B richiedono granularita' diverse e il
  mandato autorizzava una sola copia.
- `WaitForExit` in `Stop-PortoHotServer` alzato da 60.000 a 300.000 ms (la trappola citata dal
  piano: sotto nsys il PID e' nsys, non il server, e il rapporto si scrive solo alla chiusura
  pulita).
- Aggiunta creazione di `$NsysOutDir` all'avvio.

Diff completo: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\runner_nsys.patch`.

**Scoperta operativa non anticipata dal piano**: sotto `Start-Process -WindowStyle Hidden` con
redirect, l'output del processo FIGLIO (llama-server) non arriva ne' su stderr ne' su stdout del
wrapper nsys (che restano quasi vuoti: solo i messaggi di stato propri di nsys). E' incorporato nel
`.nsys-rep` stesso, recuperabile dopo l'export SQLite dalla tabella `ProcessStreams` (join su
`StringIds` per `filenameId` e `contentId`, filtro sul nome file `%stderr%`). Tutte le verifiche di
identita' sui bracci sotto sonda sono state fatte su questo log estratto, non su `.server.log`
(che resta a 0 byte per design sotto nsys — non e' un'anomalia).

### Comando campione (identico su tutti gli archi, verificato riga per riga dal ledger di stanotte)

```powershell
-MaxTokens <160|1200> -Repetitions 1 -PortoHotSnapshot 0 -SpecNmax 3 `
-Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
```

Nota su un'apparente contraddizione fra mandato e piano: il mandato chiedeva questi cinque zeri
nell'`-Extra`; il piano (§3.2) diceva che le stesse famiglie di variabili "devono restare ASSENTI,
non =0". Verificato nel codice sorgente (sola lettura, `D:\llama-overlap`) prima di lanciare
qualunque cosa: tutti e cinque i punti di lettura (`cache-esperti.cu:2125-2126`, `llama-graph.cpp:1876-1878`,
`ggml-cuda.cu:4497-4498`, `mmvq.cu:1808-1809`, `mmvq.cu:2748-2749`) usano il pattern
`valore && *valore && atoi(valore) != 0` (o equivalente): per queste cinque variabili — a differenza
di `GGML_CUDA_DISABLE_GRAPHS`, che e' un cancello a presenza — `=0` e "assente" sono
**comportamentalmente identici**. Confermato anche dal ledger di stanotte: il comando esatto del
campione `nmax3fix_graphs` (riga 1287 sopra) usa proprio questi cinque `=0` nell'`-Extra`. Nessuna
contraddizione reale; il piano era prudente ma impreciso su questo punto specifico.

Trovato anche, non menzionato dal piano, un secondo cancello di identita' essenziale: la riga del
motore `common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80`
(distingue l'intenzione dal valore che il motore riceve davvero — vedi ledger di stanotte,
`nmax3fix_graphs`). Verificato PASSATO su ogni arco sotto sonda.

---

### L3-0 — pilota B160 (node) — CANCELLO C3 PASSATO

```text
tag              = l3_0_pilota_b160_node_20260817
comando          = run_porto_hot_nsys.ps1 -Tag ... -MaxTokens 160 -Repetitions 1 -PortoHotSnapshot 0
                    -SpecNmax 3 -NsysGraphGranularity node -Extra '<i cinque zeri + GGML_SCHED_PROFILO=0>'
lancio staccato  = Win32_Process.Create, ReturnValue=0, 01:18:29 -> done 01:21:04 (2m35s)
.nsys-rep        = D:\ds4_work\l3_nsys\l3_0_pilota_b160_node_20260817.nsys-rep (30.794.744 byte)
riga cache-esperti = 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62),
                    cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0,
                    copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
                    -- IDENTICA alla riga SOTA storica (runbook §12.1)
build            = build 10093 (3014d3756) — SHA invariati
profiler         = SPENTO (0 righe sched-profilo, manifesto GGML_SCHED_PROFILO=0(E) -- concordi)
GGML_CUDA_DISABLE_GRAPHS = <spento>(D) -- grafi accesi, PASSATO
motore n_max     = n_max=3, n_min=0, p_min=0.00, conf_min=0.80 -- PASSATO
p1               = 0.80952 (85/105), mean len 2.16 (proprio di B160, non confrontabile col B1200)
copie/buchi      = NON PRESENTE nel log (la riga finale "cache-esperti: domanda" non viene
                    stampata su un B160 cosi' breve — registrato cosi', non dedotto)
errori/divergenze = zero reali (i match del pattern ampio erano tutti falsi positivi su "info"/"-inf")
finish_reason    = length, completion_tokens = 160
```

**Cancello C3**: PASSATO con ampio margine. 594.365 istanze kernel nella traccia (contro il
fallimento noto dell'11/8 di "4 token invece di 500"), `mul_mat_vec_q_moe_maschera` 16.545 istanze
(103/token), `cudaGraphLaunch_v10000` 5.286 lanci. **Scoperta**: i lanci di grafo sono piu' granulari
di un lancio-per-ciclo-di-decode (coerente con "301 grafi, 35,1 split/grafo" gia' visto nel ledger di
stanotte) — il rapporto "istanze moe_maschera / lanci grafo ~= 43" del piano non si verifica su
questa base cosi' com'e' scritta; non e' un fallimento del cancello, e' una correzione al modello
implicito nel piano. **Nomi kernel**: trovato sia `kern_copia` (6.840 istanze) sia `kern_fj_copia`
(3.309 istanze) come kernel DISTINTI — il piano nominava solo `kern_fj_copia`; entrambi sono reali e
vanno sommati per il trasporto totale.

### Gemello B160 senza sonda (per il fattore di correzione)

```text
tag        = l3_0_pilota_twin_b160_20260817 (runner ORIGINALE, non la copia nsys)
eval t/s   = 13,89   |   p1 = 0.80952   |   SHA output = 9863BCD6D16E38750C671A390C6F0C6DE6F902B8533CCF23126A777D930757BE
```

**SHA e p1 identici fra pilota sotto sonda e gemello**: la sonda node non altera la traiettoria di
calcolo. **Overhead sonda node a B160**: (13,89 - 12,35) / 13,89 = **+11,1%**, stesso ordine di
grandezza del +9,4% dell'11/8 (li' con speculazione spenta).

---

### L3-A — mappa kernel B1200 (node) — COMPLETATO, ANALISI PIENA

```text
tag              = l3a_b1200_node_20260817
lancio           = foreground diretto (non staccato in background-poll: la chiamata WMI stessa
                    e' rapida), 01:45:09 -> done 01:49:17 (4m8s)
.nsys-rep        = D:\ds4_work\l3_nsys\l3a_b1200_node_20260817.nsys-rep (149.301.959 byte, 142,4 MiB
                    -- piu' piccolo della stima del piano 0,8-2,0 GB: regime speculativo attuale
                    genera meno eventi/token del riferimento 11/8)
.sqlite          = D:\ds4_work\l3_nsys\l3a_b1200_node_20260817.sqlite (386.461.696 byte, export in 13,5s,
                    5.752.143 eventi)
```

**Identita' (tutti PASSATI)**: riga cache-esperti identica; build/SHA invariati; profiler spento (0
righe, manifesto concorde); `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)`; motore
`n_max=3, n_min=0, p_min=0.00, conf_min=0.80`; **p1 = 0.90281 (771/854), mean len 2,80 — identico al
campione di riferimento** `nmax3fix_graphs`; zero `GGML_ASSERT`/`CUDA error`/divergenze (tutte le
righe `divergenze: taglia=0 ids=0 out=0 GRIGLIA-corta=0`); `finish_reason=length`,
`completion_tokens=1200`; chiusura pulita (`ctrl-c`).

**SHA output = `1EDA23452DE9292C817EAF47532724A409DD2FFE3B3EF9E165ED887BA4169089` — IDENTICO byte per
byte al campione non sondato di stanotte** (`nmax3fix_graphs_b1200_r{1,2,3}_20260816`). La sonda
node, anche a B1200, non altera in alcun modo la traiettoria di calcolo.

```text
eval t/s sotto sonda (log)  = 15,65   (76691,24 ms / 1200 token)
eval t/s riferimento (log, nmax3fix_graphs mediana) = 16,34
overhead sonda node a B1200 = (16,34-15,65)/16,34 = +4,22%   (molto piu' basso del +11,1% a B160:
                               l'overhead per-lancio si ammortizza meglio su un run lungo)
copie/buchi sotto sonda     = domanda 227069, colpi 160849 (70,8%), buchi 66220
copie/buchi riferimento     = domanda 275477, colpi 195401 (70,9%), buchi 80076
```

Nota onesta sulla divergenza copie/buchi (colpi% quasi identico, 70,8 vs 70,9%, ma volume assoluto
diverso -17,6%): con SHA/p1/mean-len bit-identici, la sequenza di esperti richiesti e' la stessa; la
sonda altera la **temporizzazione fine** (il costo per-nodo di CUPTI cambia quando un rendezvous
CPU/GPU arriva "in tempo" o "in ritardo"), quindi il conteggio hit/miss della cache — che e' una
proprieta' di prestazione, non di correttezza — puo' divergere pur restando l'output finale
identico. Non e' un errore, e' un artefatto noto della sonda sul bookkeeping della cache.

**Controllo incrociato con `nsys stats --report cuda_gpu_kern_sum` (report ufficiale, sull'intera
traccia)**: `kern_fj_copia` 18.532 istanze/21.770,26 ms sull'intera traccia contro le mie 18.403/
21.654,16 ms nella sola finestra decode — la differenza (129 istanze, 116 ms) e' esattamente la
piccola quota di prefill/avvio esclusa dalla finestra. Stesso riscontro per `kern_copia`,
`kern_decidi`, `mul_mat_vec_q_moe_maschera` (variante per tipo). La metodologia SQL propria (finestra
via `mul_mat_q`, aggregazione per `shortName`) e' validata contro lo strumento ufficiale.

#### (a) GPU busy% e bolle — unione di intervalli (kernel+memcpy), non somma

```text
finestra decode  = 76.859,472 ms (76,859 s) -- contro 76.691,24 ms del log (scarto 0,22%, il confine
                    mul_mat_q ha funzionato)
GPU ATTIVA (unione, kernel+memcpy) = 50.037,404 ms = 65,10% della parete
BOLLE totale                        = 26.822,069 ms = 34,90% della parete   (verificato: busy+bolle=parete esatto)

Istogramma bolle (5 classi):
  a) <10us      n=3.188.176  ms_tot=1.257,512   1,64% parete   us_medio=0,39   (overhead di lancio)
  b) 10-100us   n=  240.263  ms_tot=5.574,418   7,25% parete   us_medio=23,20
  c) 0.1-1ms    n=   11.587  ms_tot=4.990,910   6,49% parete   us_medio=430,73
  d) 1-10ms     n=    7.300  ms_tot=13.653,435  17,76% parete  us_medio=1.870,33  <- LA PIU' GRANDE
  e) >10ms      n=       58  ms_tot=1.345,794   1,75% parete   us_medio=23.203,34 (max singola 422,8 ms, vicino a inizio finestra)
```

La classe (d) 1-10ms da sola vale **17,76% dell'intera parete** (13,65 s su 76,86 s) — la firma che
il piano associa ai "join della lane CPU" (10/8: "47,5% la CPU calcola mentre la GPU aspetta"). **Non
posso confermare la correlazione con lo stato della CPU** (richiede `--cpuctxsw=process-tree`,
indisponibile senza privilegi amministrativi — vedi sopra). Resta un buco aperto, non un verdetto:
le bolle grandi ESISTONO e sono quantificate, ma la biforcazione "calcolo puro vs serializzazione
CPU/GPU" (piano §5.4, "la biforcazione principale dell'arm") non e' risolvibile in questo ambiente.

#### (c) Sovrapposizione trasporto/calcolo — LA DOMANDA CHE IL PIANO DICE "DECIDE DOVE VA IL PROSSIMO MESE"

Classificato per NOME kernel (non per streamId, come prescritto dal piano §5.6), unione di intervalli
per trasporto e per calcolo separatamente, poi sweep-line per l'intersezione esatta:

```text
trasporto (kern_fj_copia + kern_copia, unione) = 23.041,061 ms  (kern_fj_copia da solo: 21.654,159 ms)
calcolo   (mul_mat_vec_q + moe_maschera + moe + mul_mat_f + mul_mat_vec_f, unione) = 22.192,836 ms
sovrapposto (trasporto AND calcolo attivi insieme) = 3.983,066 ms

sovrapposto / trasporto = 17,29%   (kern_fj_copia da solo: 18,39%; kern_copia da solo: 0,00%)
```

**VERDETTO: vicino a 0%, non vicino a 100%.** Il meccanismo FORK (`LLAMA_CACHE_ESPERTI_FORK=2`,
stream dedicato) **non sta nascondendo la gran parte del trasporto dietro il calcolo** nel regime
combinato attuale (n_max=3 + IBRIDO=1 + ACCEPTMOE + tutte le altre leve della SOTA insieme). Questo
e' in forte contrasto con la misura isolata dell'11/8 ("sonda 99,4% coperto", vedi memoria
`fork-join-giudicato-nel-regime-sbagliato`), fatta pero' in un regime diverso e piu' semplice. Circa
**19,06 ms/ciclo di trasporto NON sovrapposto** (23.041-3.983=19.058 ms totali, 15,88 ms/token) sono
sul tavolo PRIMA di toccare adaptive-K — e' il lato "vicino a 0" della biforcazione che il piano
poneva, con la leva indicata: capienza/fork, non n_max. Controllo di robustezza: il risultato regge
identico usando solo `kern_fj_copia` (18,39%) o la somma con `kern_copia` (17,29%) — non e' un
artefatto della classificazione.

#### (d) Quota del drafter DSpark

Nessun `graphId` nella traccia a granularita' `node` (verificato: la colonna non esiste in
`CUPTI_ACTIVITY_KIND_KERNEL` sotto questa modalita' — e' presente SOLO nella traccia a granularita'
`graph`, in `CUPTI_ACTIVITY_KIND_GRAPH_TRACE`, scoperta fatta piu' sotto su L3-B). Usato il ripiego
gia' previsto dal piano (§5.7): segmentazione per `cudaGraphLaunch_v10000` come confini, ogni
segmento classificato bersaglio se contiene >=1 `mul_mat_vec_q_moe_maschera`, altrimenti bozza.

```text
lanci totali (finestra)      = 24.088
segmenti BERSAGLIO            = 10.585  (kernel/segmento medio 219,41)
segmenti BOZZA                 = 13.503  (kernel/segmento medio 70,03)
DRAFTER (somma ms, tutti i kernel dei segmenti bozza) = 7.668,760 ms = 9,98% della parete = 6,39 ms/token
```

Metodo approssimato (confini temporali, non identita' di grafo vera) — la quota della bozza e' quindi
una stima, non una misura esatta come per L3-B (dove il vero `graphId` era disponibile, vedi sotto).

#### (e) Tempo per nodo e replay dei grafi

```text
segmenti bersaglio: 10.585, somma_ms=45.593,140 (RAW, con overlap interno) -> ~4,31 ms/replay medio
kernel/segmento bersaglio: media 219,41  ->  ~19,6 us/nodo
```

Ordine di grandezza atteso dal piano ("se e' dell'ordine dei microsecondi con migliaia di nodi, il
costo per nodo e' una voce di budget in se'") — confermato: 19,6 us/nodo su ~2,3 milioni di nodi
bersaglio complessivi e' un costo strutturale, non rumore.

---

### L3-B — bolle e lane CPU (graph) — B1200 NON OTTENUTO dopo tre tentativi; sonda diagnostica B160 riuscita

**Tre tentativi a B1200, tutti falliti con la stessa firma**, nessuno per un errore GGML/CUDA o un
crash del server:

```text
tentativo 1 (l3b_b1200_graph_20260817)       : lancio combinato QUIETE+WMI in background.
                                                Morto dopo ~4m36s. server.out = solo "Collecting data...".
                                                NESSUN .nsys-rep scritto (nsys non ha fatto in tempo a
                                                finalizzare). console.log = solo "shutdown=ctrl-c"
                                                (l'eccezione nello script ha saltato la scrittura del
                                                done-marker).
tentativo 2 (l3b_b1200_graph_retry_20260817) : stesso pattern di lancio. Morto dopo ~2m36s. Stream
                                                stderr estratto dal .nsys-rep (12,45 MiB, questa volta
                                                scritto correttamente) mostra il decode in corso
                                                NORMALE (n_decoded 148->172, tg~9,5-9,9 t/s) subito
                                                seguito dal dump di chiusura standard di un vero
                                                Ctrl+C -- non un crash, un'interruzione esterna.
tentativo 3 (l3b_final_b1200_graph_20260817) : lancio WMI come chiamata FOREGROUND separata (pattern
                                                identico a quello che ha fatto funzionare L3-A), QUIETE
                                                prima come task background separato. Morto dopo ~11m19s
                                                (molto piu' lungo dei primi due). console.log VUOTO
                                                (0 byte, nemmeno "shutdown=ctrl-c" -- terminazione
                                                ancora piu' brusca, dall'esterno del processo, non
                                                un'eccezione dentro lo script). Nessun .nsys-rep.
```

**Diagnosi**: fenomenologia riproducibile tre volte, sempre B1200 (lungo), mai legata a
`--cuda-graph-trace=graph` in se' (la sonda diagnostica a B160, sotto, con la STESSA granularita',
completa senza problemi). Nessun `GGML_ASSERT`/`CUDA error`, stato macchina pulito prima e dopo ogni
tentativo (RAM 88-90 GB, VRAM <400 MiB, 0 processi). Il pattern (morte dopo tempi variabili fra 2,6 e
11,3 minuti, nessun errore applicativo, terminazione dall'esterno del processo) e' compatibile con un
limite dell'ambiente sandboxato per processi staccati di lunga durata, non con un difetto del disegno
sperimentale o della configurazione. **Non ho insistito oltre un terzo tentativo con variazione
metodologica reale**, per non violare la regola "non improvvisare, non provare varianti a
oltranza" del runbook: registro questo come esito, non lo nascondo.

**Sonda diagnostica L3-B a B160 (`l3b_diag_b160_20260817`) — RIUSCITA**, stesso identico ambiente,
lancio combinato QUIETE+WMI in background (come i tentativi falliti, ma su una durata breve, ~3m16s
totali) — a conferma che la CAUSA e' la durata, non il pattern di lancio.

```text
tag              = l3b_diag_b160_20260817
completion_tokens = 160, finish_reason=length, chiusura pulita
riga cache-esperti = identica (473 slot ... sfratto_par=1 ...)
profiler          = SPENTO, GGML_CUDA_DISABLE_GRAPHS=<spento>(D), motore n_max=3 -- tutti PASSATI
p1                = 0.75229 (82/109), mean len 2,08
errori            = zero
eval t/s sotto sonda graph = 12,29   (13.021,19 ms / 160 token)
```

**Correzione metodologica importante, scoperta durante l'analisi**: sotto granularita' `graph`, nsys
NON registra i nodi dentro i grafi in `CUPTI_ACTIVITY_KIND_KERNEL` (per design: "CUDA graphs will be
traced as a whole and node activities will not be collected"). La mia prima lettura (solo KERNEL+
MEMCPY) dava GPU attiva 11,32% — un numero assurdo, sbagliato per costruzione, non un dato reale.
La tabella giusta e' **`CUPTI_ACTIVITY_KIND_GRAPH_TRACE`** (un evento per l'INTERO replay del grafo,
con `graphId`/`graphExecId` propri — assenti invece nella traccia a granularita' `node`). Rifatto il
calcolo unendo GRAPH_TRACE + kernel-non-catturati + memcpy:

```text
GPU ATTIVA (unione, corretta) = 7.575,434 ms = 56,69% della parete (13.363,442 ms)
BOLLE                          = 5.788,008 ms = 43,31%   (verificato: busy+bolle=parete esatto)

confronto diretto con L3-0 pilota (node, stessa scala B160):
  GPU attiva: 56,69% (graph)  vs  56,41% (node)   -- differenza 0,28 punti, praticamente identiche
  bolle:      43,31% (graph)  vs  43,59% (node)
```

**Questo E' la cross-verifica che il piano chiedeva (§2, "la (a) si misura due volte... i due numeri
si confrontano")**, anche se solo alla scala B160 invece di B1200: le due granularita' concordano
strettamente. Dato che la distorsione da sonda node e' minima a B160, e che l'overhead di sonda node
scende (non sale) passando da B160 a B1200 (+11,1% -> +4,22%, vedi sopra), c'e' ragionevole fiducia
che i numeri di L3-A a B1200 (65,10% busy, 34,90% bolle) non siano pesantemente distorti — ma questo
resta un'inferenza, non una misura diretta a B1200 con `graph`.

Non rifatta la scomposizione bersaglio/bozza via `graphId` vero per L3-B (il campo esiste ma la
struttura e' > 100 `graphId` distinti con conteggi piccoli — coerente con "301 grafi, 35,1
split/grafo" del ledger di stanotte, non un semplice 2-grafi bersaglio/bozza) — priorita' data a
chiudere il deliverable principale nel tempo residuo del banco.

---

## DELIVERABLE — tabella voce -> ms/token -> % del token

Base: **L3-A** (B1200, node, unico arco completo alla scala piena), token = 1200 (verita' di terra
da `completion_tokens` nel summary, non stimato da cicli). Finestra 76.859,472 ms. t/s sotto sonda
node = 15,65; t/s stesso banco senza sonda (campione di riferimento di stanotte) = 16,34; overhead
sonda = +4,22%.

```text
voce                                        ms/token   % del token   istanze
--------------------------------------------------------------------------------
TRASPORTO cache (kern_fj_copia+kern_copia)    18,10        28,27%      55.215
  di cui sovrapposto al calcolo                3,32     (5,18% parete; 18,3% di questa riga --
                                                 la sezione (c) sotto usa la base target+bozza
                                                 insieme, 17,29%: stessa conclusione, basi diverse)
logica cache/fork (kern_decidi, kern_fj_*)     1,16         1,81%     110.424
MMVQ MoE mascherate (+legacy)                  7,80        12,19%      92.021
MMVQ/MM densi (vec_q, mul_mat_f, vec_f)        6,82        10,65%     171.566
MMQ prefill (fuori finestra)                   0,00         0,00%           0
attenzione (flash_attn*, soft_max)             0,77         1,20%      45.304
AcceptMoE / routing / partiziona / argsort     0,46         0,72%      62.412
DSV4 HC fuso (post/comb)                       0,17         0,26%      53.716
norm/elementwise/rope/copy/concat/reduce       2,71         4,23%   1.553.461
quantizzazione attivazioni (quantize_q8_1)     0,34         0,53%     193.314
copie CUDA (fallback scheduler, cudaMemcpy)    0,67         1,04%     294.462
DRAFTER DSpark (tutti i suoi nodi, stima)      6,39         9,98%     945.561
--------------------------------------------------------------------------------
GPU ATTIVA (unione, no overlap)               41,70        65,10%
BOLLE totali                                  22,35        34,90%
  a) <10us   (overhead di lancio)              1,05         1,64%   3.188.176
  b) 10-100us                                  4,65         7,25%     240.263
  c) 0,1-1ms                                   4,16         6,49%      11.587
  d) 1-10ms  (probabile firma "join lane CPU") 11,38        17,76%       7.300
  e) >10ms                                     1,12         1,75%          58
  di cui con lane CPU in Running                 NON DISPONIBILE (richiede privilegi
                                                  amministrativi, non ottenibili in questo ambiente)
--------------------------------------------------------------------------------
TOTALE = parete/token                         64,05        100%
```

**Nota sulla chiusura**: le voci per-tipo (trasporto...drafter) sommano a 54.467,15 ms (70,87% della
parete) — PIU' del 65,10% di GPU-attiva-unione, perche' includono overlap interno fra kernel
concorrenti (es. i 3.983 ms di trasporto/calcolo sovrapposti vengono contati in entrambe le righe).
L'identita' che chiude esattamente sulla parete e' **GPU ATTIVA (unione) + BOLLE = parete**
(50.037,404 + 26.822,069 = 76.859,473 ms, verificato). Le voci per-tipo restano il modo giusto di
vedere "quanto SM-tempo consuma ciascun meccanismo" (la leva che ciascuna riga porta con se', come
chiede il piano), ma non sono sommabili linearmente contro le bolle senza contare due volte
l'overlap. Riportato cosi' invece di arrotondare per far quadrare un totale fittizio (vietato
esplicitamente dal piano, §6: "non si arrotonda").

**La leva che ciascuna riga porta con se'** (piano §6): TRASPORTO -> capienza/fork (vedi (c) sopra,
la scoperta piu' importante del banco: overlap 17-18%, non ~100%, quindi la leva del fork e' in
larga parte ancora da incassare in QUESTO regime combinato, prima ancora di guardare adaptive-K);
MMVQ MoE mascherate -> adaptive-K/oracolo/gate+up fuso (12,19% del token, il bersaglio dichiarato
dal mandato); bolle classe (d) -> finestra di join, ipotesi non verificabile qui per mancanza di
`cpuctxsw`; DRAFTER -> n_max/conf (gia' esplorati ieri sera, vedi banchi L0 sopra in questo ledger).

### File prodotti (tutti assoluti)

```text
D:\ds4_work\l3_nsys\l3_0_pilota_b160_node_20260817.nsys-rep   (30.794.744 byte)
D:\ds4_work\l3_nsys\l3_0_pilota_b160_node_20260817.sqlite
D:\ds4_work\l3_nsys\l3_0_pilota_b160_node_20260817.extracted_stderr.log
D:\ds4_work\l3_nsys\l3a_b1200_node_20260817.nsys-rep           (149.301.959 byte)
D:\ds4_work\l3_nsys\l3a_b1200_node_20260817.sqlite              (386.461.696 byte)
D:\ds4_work\l3_nsys\l3a_b1200_node_20260817.extracted_stderr.log
D:\ds4_work\l3_nsys\l3b_b1200_graph_retry_20260817.nsys-rep     (13.055.686 byte, cattura PARZIALE,
                                                                  non usata per il deliverable)
D:\ds4_work\l3_nsys\l3b_diag_b160_20260817.nsys-rep             (12.045.822 byte)
D:\ds4_work\l3_nsys\l3b_diag_b160_20260817.sqlite
D:\ds4_work\l3_nsys\l3b_diag_b160_20260817.extracted_stderr.log
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot_nsys.ps1  (copia autorizzata)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\runner_nsys.patch  (diff)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\l3_0_pilota_b160_node_20260817.* (summary/log/output)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\l3_0_pilota_twin_b160_20260817.* (gemello senza sonda)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\l3a_b1200_node_20260817.*
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\l3b_diag_b160_20260817.*
```

### Postflight e stato macchina a fine banco

```text
POSTFLIGHT FINALE (03:00): ram_libera=90,1 GB | vram_usata=372 MiB, vram_libera=11744 MiB |
                            clock SM=210 MHz | potenza=12,72 W | processi (llama-server+nsys) = 0
```

Nessun commit git eseguito. Nessuna build avviata. `D:\llama-overlap` non toccato in scrittura
(solo letto per verificare il comportamento delle variabili d'ambiente, §"comando campione" sopra).
Nessun invito a `codex`. File toccati oltre a questo ledger: la copia del runner
(`run_porto_hot_nsys.ps1`, autorizzata esplicitamente dal mandato) e la cartella `D:\ds4_work\l3_nsys\`
(autorizzata). QUIETE di 300 s rispettata fra ogni arco con server attivo. Tre tentativi B1200 di
L3-B, tutti con preflight/QUIETE regolari e postflight pulito verificato dopo ciascuno.

**Ricorda per la prossima sessione**: (1) la sovrapposizione trasporto/calcolo del fork e' al 17-18%
nel regime combinato attuale, non al ~99% misurato in isolamento l'11/8 — merita un banco dedicato
prima di toccare adaptive-K; (2) L3-B a B1200 non ottenuto per un limite dell'ambiente (processi
staccati di lunga durata terminati dall'esterno dopo 2,6-11,3 minuti, non riproducibile a B160) — se
serve la cattura B1200 a granularita' `graph`, va tentata da una sessione/ambiente diverso o con
`nsys start`/`nsys stop` su sessione con nome invece di `profile` con `--stop-on-exit`; (3) i
`cpuctxsw`/`gpu-metrics`/`wddm` restano indisponibili senza privilegi amministrativi, che questo
esecutore non e' autorizzato a richiedere o attivare.
