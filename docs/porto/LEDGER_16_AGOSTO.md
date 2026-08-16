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
