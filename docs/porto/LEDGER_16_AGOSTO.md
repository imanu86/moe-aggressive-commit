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
