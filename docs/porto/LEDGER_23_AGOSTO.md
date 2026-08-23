# LEDGER 23 AGOSTO — banco tool/jinja: quanto costano le sonde, quanto la modalita' tool

Mandato: chiudere coi numeri la domanda dell'utente — il server locale con tool
(`avvia ds4 locale.bat`, bonificato il 23/8: sonde commentate, restano `--jinja` +
`--chat-template-file` + `--reasoning`) decodificava a ~11 t/s contro i ~14 attesi. Quanto e'
colpa delle sonde e quanto costa davvero la modalita' tool/template?

Binario canonico (verificato PRIMA del banco, invariato durante):

```text
sha_llama_server = C15FF135F14024FED4ADD8B3FF14299429CA9627508150B7CDE06234E9795878
sha_ggml_cuda    = 00C6F0D2AC9161AF44EADDB0F22344E5580F4CC77E1D72A1683951214B15C576
sha_server_impl  = 729DC0DD655190C4001AD259CAE1BF954A9936407398A793E8182C3C0F13935F
build            = build 10093 (3014d3756) MSVC 19.44.35227.0
percorso         = D:\llama-subtract\build\bin\  (== canonico backuppato in canonico_bonifica_23ago\)
```

Preflight (18:5x, 23/8): nessun processo llama, porte 8099/8100 libere, GPU a riposo
(794 MiB usati, 11322 liberi, PCIe gen1x16 a riposo — normale), RAM libera 86 GB, disco
C 45,8 GB / D 115,5 GB liberi, uptime 4178 min (non e' un cold-start post-riavvio).
jprompt.txt: Length=252, SHA256 `C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9`
— IDENTICO al riferimento runbook §1.8.

Tutti e quattro i bracci: stesso jprompt.txt (68 token base), `-MaxTokens 512`,
`temperature=0`, `cache_prompt=true`, `stream=false`, `porto_hot_snapshot=false` (free-run),
1 sola richiesta per processo (screening, non certificazione — nessuna mediana su 3).
`GGML_CUDA_DISABLE_GRAPHS` sempre ASSENTE sui quattro bracci (post-bonifica: assente = grafi
ACCESI, verificato dal manifesto `<spento>(D)` su ognuno).

---

## Braccio 1 — t24_base (riferimento "campione", free-run)

```text
tag              = t24_base_b512_r1_20260823
runner           = B (run_porto_hot.ps1), -ServerPath sul canonico D:\llama-subtract
banco            = B512 (fixture di screening, non B160/B1200 storico)
ripetizioni      = 1 (screening)
leva variata     = nessuna (riferimento) -- config di default dello script + GGML_SCHED_PROFILO=0
comando esatto   = run_porto_hot.ps1 -Tag t24_base_b512_r1_20260823 -MaxTokens 512 -Repetitions 1
                   -PortoHotSnapshot $false -ServerPath D:\llama-subtract\build\bin\llama-server.exe
                   -Extra 'GGML_SCHED_PROFILO=0'
CLI server       = -m DS4-0731-IQ2XXS -md DSpark-draft-Q2K --spec-type draft-dspark --fit off
                   -ngld 99 --spec-draft-n-max 2 --spec-draft-ubatch-size 16 -otd <blk0 mapped/cpu>
                   -c 10000 -ub 64 -np 1 -ngl 99 -ot <mapped> -t 7 --no-mmap -lv 4
                   --host 127.0.0.1 --port 8100 --spec-draft-conf-min 0.80 --cache-ram 8192
                   --ctx-checkpoints 32 -cms 8192   (NIENTE --jinja/--chat-template-file/--reasoning)
eval t/s         = 14.44 (unica ripetizione)
prompt t/s       = 21.75
ms/token         = 69.27
p1               = 0.87234 (287 accepted / 329 generated), mean len 2.29
SHA output       = 90A28151DAB6AF1282A5CB68933E99352F7362D89E4E31F85130023F6E6454ED  (1311 caratteri)
finish_reason    = length
copie/buchi      = domanda 94929 (colpi 70939 = 74.7%, buchi 23990, miss 25.3%)
riga cache-esperti = cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06
                   + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2,
                   peso_copia_pm=0, copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0,
                   dma_strato=0
profiler         = SPENTO (righe sched-profilo = 0; manifesto GGML_SCHED_PROFILO=0(E) -- COERENTE,
                   nessuna discrepanza log/manifesto)
graph stats      = SPENTO (GGML_CUDA_GRAPH_STATS=0(D))
graphs           = ACCESI (GGML_CUDA_DISABLE_GRAPHS=<spento>(D), assente)
snapshot         = porto_hot_snapshot = 0 (free-run)
clock/potenza    = NON CAMPIONATO (telemetria hw.csv mancante su questo braccio -- lacuna
                   dichiarata: run_porto_hot.ps1 non lancia sample_hw.ps1 da solo e non e' stato
                   affiancato qui; non ripetuto per costo, i bracci 2-4 ce l'hanno)
server vivi max  = 1
uptime a inizio  = 4178 min
esito            = DIAGNOSTICO (screening 1 colpo, non certificazione a 3 repliche)
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\t24_base_b512_r1_20260823.{server.log,summary.json,r1.output.txt,r1.response.json,server.out}
anomalie         = nessuna; chiusura ctrl-c pulita; zero GGML_ASSERT/CUDA error/divergenze;
                   postflight pulito (processi=0, VRAM 549 MiB, RAM 87.1 GB)
NOTA IMPORTANTE  = PORTO_SPEC_NMAX=2 qui (default dello script run_porto_hot.ps1), NON 3.
                   Se "nmax3" e' ormai il valore campione adottato (vedi memoria 16/8: adottato
                   come "miglioria innocua"), questo script e' rimasto sul vecchio default e la
                   parola "campione" andrebbe riverificata contro il codice, non assunta dal
                   nome dello script. I bracci 4 (t24_tool_campione) e questo condividono lo
                   STESSO nmax=2 per costruzione, quindi il confronto 4-vs-1 resta pulito
                   (un solo asse di differenza: jinja/template/reasoning) anche se nmax "vero"
                   fosse 3.
```

## Confronto comando bat vs comando campione (run_porto_hot.ps1) -- richiesto dal coordinatore

Il bat bonificato (`avvia ds4 locale.bat`) e la config campione (`run_porto_hot.ps1`, usata dal
braccio 1) **NON sono identiche a meno di jinja**. Differenze CLI:

| parametro | campione (braccio 1) | bat | uguale? |
|---|---|---|---|
| `-c` (contesto) | 10000 | 150000 | NO |
| `-ub` | 64 | 2048 | NO |
| `-b` | (default) | 2048 | possibile NO |
| `--spec-draft-n-max` | 2 | 3 | NO |
| `--cache-ram` | 8192 | 0 | NO |
| `-cms` | 8192 | 32 | NO |
| `--ctx-checkpoints` | 32 | (assente) | NO |
| `--host` | 127.0.0.1 | 0.0.0.0 (+ `--no-host`) | NO |
| `--api-key` | assente | presente | NO (irrilevante per t/s) |
| `--jinja`/`--chat-template-file`/`--reasoning*` | assenti | presenti | **la differenza cercata** |

Differenze ambiente (il bat ne imposta molte che il campione non tocca affatto, quindi il
campione gira sui DEFAULT di codice per quelle leve, non su un valore verificato uguale):

```text
LLAMA_VRAM_A_FASI            campione=0            bat=2 (+ _CALDO=0 _UB=64 _MIN=0 _MARGINE=0,
                                                     assenti nel campione)
LLAMA_DSV4_INDEXER_FUSO      campione=0            bat=1
LLAMA_MMQ_X_IDS               (non impostata)       bat=64
LLAMA_DSV4_MASK_F16_INPUT     (non impostata)       bat=0
LLAMA_CUDA_FATTN_BLOCK_SPARSE (non impostata)       bat=0
LLAMA_DSV4_PREFILL_LAYER_STAGING/EXECUTOR/SPLIT/FFN_SUPEROP/MOE_UB  (non impostate) bat=1/0/0/0/2048
GGML_SCHED_OFFLOAD_PACCHETTI  (non impostata)       bat=0
```

**Verdetto sul mandato del coordinatore**: le due configurazioni NON sono identiche salvo
jinja — il bat cambia anche contesto, batch/ubatch, cache-ram, checkpoint step, n-max della
bozza, alcune leve VRAM/prefill. Il braccio 2 (bat-pulito) **non isola** da solo il costo di
jinja: isola il costo del "passaggio completo al regime del bat" (tutte le differenze sopra
insieme). **Quarto braccio ESEGUITO** (non saltato) per isolare jinja/template/reasoning da
solo: `t24_tool_campione` = config del braccio 1 (script, env, CLI identici) + SOLO
`--jinja --chat-template-file <stesso file del bat> --reasoning on --reasoning-preserve`
in coda agli argomenti. Vedi braccio 4 sotto.

## Braccio 2 — t24_bat (bat-pulito, sonde OFF)

```text
tag              = t24_bat_b512_r1_20260823
runner           = script dedicato bat_replica_launcher.ps1 (replica 1:1 del bat, ProbesOn=$false)
banco            = B512
ripetizioni      = 1 (screening)
leva variata     = TUTTO il regime del bat (vedi tabella diff sopra) rispetto al braccio 1;
                   sonde ESPLICITAMENTE spente (assenti)
comando esatto   = powershell bat_replica_launcher.ps1 -Tag t24_bat_b512_r1_20260823
                   -ProbesOn $false -MaxTokens 512   (env/CLI = copia 1:1 di
                   "avvia ds4 locale.bat" bonificato, vedi CLI nel braccio 1 vs bat sopra)
tempo di boot    = 300 s fino a /health (contro pochi secondi del braccio 1 -- -c 150000 e
                   il mapped buffer 74.304 MiB pesano sul load, non sul decode)
eval t/s         = 14.45 (unica ripetizione)  <-- QUASI IDENTICO al braccio 1 (14.44, +0.07%)
prompt t/s       = 16.70 (contro 21.75 del braccio 1 -- prompt minuscolo, 68 token, il costo
                   fisso del batch/ub piu' grande pesa qui, non sul decode)
ms/token         = 69.21
p1               = 0.87714 (307 accepted / 350 generated), mean len 2.50
SHA output       = 644ACC409298572A68BC4CDA173C9B701435D214A7ED9B4CD1FA44BF0A0ADD9B (1275 caratteri)
finish_reason    = length   |  used_reasoning_fallback = false (il campo "content" e' arrivato
                   valorizzato anche con --reasoning on: il modello non ha speso tutto il
                   budget nel pensiero)
copie/buchi      = domanda 115535 (colpi 79902 = 69.2%, buchi 35633, miss 30.8%)
riga cache-esperti = IDENTICA carattere per carattere al braccio 1 (473 slot..., sfratto_par=1)
profiler         = SPENTO (righe sched-profilo = 0; manifesto GGML_SCHED_PROFILO=0(D))
graph stats      = SPENTO (GGML_CUDA_GRAPH_STATS=0(D))
graphs           = ACCESI (GGML_CUDA_DISABLE_GRAPHS=<spento>(D), assente)
SPECULAZIONE SOTTO JINJA = ATTIVA -- riga presente: "draft acceptance = 0.87714 (307
                   accepted / 350 generated), mean len = 2.50". Risposta alla domanda del
                   coordinatore: jinja/chat-template NON disattiva la speculazione in
                   questo binario.
clock/potenza    = telemetria hw.csv/cpu.csv avviata via sample_hw.ps1 (0,5 Hz) -- presente
                   per questo braccio (vedi <run>\t24_bat_b512_r1_20260823.hw.csv)
server vivi max  = 1
esito            = DIAGNOSTICO (screening 1 colpo)
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\t24_bat_b512_r1_20260823.{server.log,summary.json,r1.output.txt,r1.response.json,server.out,hw.csv,cpu.csv}
anomalie         = nessuna; chiusura ctrl-c pulita; zero GGML_ASSERT/CUDA error/divergenze;
                   postflight pulito (processi=0, VRAM 425 MiB, RAM 87.8 GB); PRIMO TENTATIVO
                   di lancio fallito PRIMA di questo (nested `powershell -File ... -ProbesOn:$false`
                   -> errore di binding parametro, MAI arrivato ad avviare un processo server:
                   corretto invocando lo script con l'operatore `&` diretto, stesso idioma che
                   ha funzionato per il braccio 1)
VERDETTO PARZIALE = il regime completo del bat (contesto 150k, batch/ubatch 2048, cache-ram 0,
                   nmax3, DSV4_INDEXER_FUSO, jinja+template+reasoning -- TUTTO insieme) COSTA
                   ~0% in decode t/s rispetto al campione, quando le sonde sono spente. Il
                   sospetto "e' colpa di jinja/tool-mode" NON regge su questo dato: il costo
                   deve stare altrove (sonde, braccio 3).
```

NOTA PROTOCOLLO (dettato utente a banco in corso): la regola QUIETE 300s fra bracci (runbook
§6.6) e' **ABOLITA dal 12/8** ("roba vecchia di quando andavamo in paging") -- con chiusura
pulita (ctrl-c, 0 processi, VRAM a riposo) si incatena SUBITO il braccio successivo. Applicato
da qui in avanti: verifica macchina-pulita si', attesa a orologio no.

## Braccio 3 — t24_bat_sonde (bat-pulito + sonde ON)

```text
tag              = t24_bat_sonde_b512_r1_20260823
runner           = bat_replica_launcher.ps1, ProbesOn=$true (IDENTICO al braccio 2 +
                   GGML_SCHED_PROFILO=1 + GGML_CUDA_GRAPH_STATS=1, unico asse di differenza)
banco            = B512, 1 ripetizione (screening)
comando esatto   = powershell bat_replica_launcher.ps1 -Tag t24_bat_sonde_b512_r1_20260823
                   -ProbesOn $true -MaxTokens 512
tempo di boot    = 140 s (contro 300 s del braccio 2 -- cache pagine OS calda dallo stesso
                   file modello letto poco prima: NON e' un effetto delle sonde)
eval t/s         = 14.28   (contro 14.45 del braccio 2: DELTA -1,18% -- dentro la deriva di
                   banco 2-3%, §8.3 runbook)
prompt t/s       = 16.86
p1               = 0.87714 (307/350, mean len 2.50)  -- IDENTICO bit per bit al braccio 2
SHA output       = 644ACC409298572A68BC4CDA173C9B701435D214A7ED9B4CD1FA44BF0A0ADD9B
                   -- IDENTICO carattere per carattere al braccio 2 (stesso SHA)
copie/buchi      = domanda 115535, colpi 79902 (69.2%), buchi 35633  -- IDENTICO al braccio 2
riga cache-esperti = IDENTICA carattere per carattere ai bracci 1-2
profiler         = ACCESO (righe sched-profilo = 18; manifesto GGML_SCHED_PROFILO=1(E))
graph stats      = ACCESO (GGML_CUDA_GRAPH_STATS=1(E))
graphs           = ACCESI (GGML_CUDA_DISABLE_GRAPHS=<spento>(D), assente)
classificazione sonda = PASSIVA per definizione runbook §6.9 (traiettoria, p1, copie, SHA
                   TUTTI identici fra sonda ON/OFF -- non solo il t/s)
server vivi max  = 1
esito            = DIAGNOSTICO
percorsi file    = ...\work\runs\t24_bat_sonde_b512_r1_20260823.{server.log,summary.json,r1.output.txt,r1.response.json,server.out,hw.csv,cpu.csv}
anomalie         = nessuna; ctrl-c pulito; zero errori/divergenze; postflight pulito
                   (processi=0, VRAM 446 MiB, RAM 87.6 GB, porte libere)
VERDETTO PARZIALE = le due sonde (GGML_SCHED_PROFILO + GGML_CUDA_GRAPH_STATS) costano
                   -1,18% su questo banco corto (512 token, 1 richiesta) -- MOLTO meno del
                   buco 14->11 (~-24%) riferito dall'utente. Ne' jinja/tool-mode (braccio 2,
                   ~0%) ne' le sonde (braccio 3, -1,2%) spiegano da sole il buco reale.
                   Sommando bracci 2+3 (tutto insieme contro il campione): 14,28 vs 14,44 =
                   -1,1%. IPOTESI aperta: il buco reale nasce da un regime che questo banco
                   corto a richiesta singola non riproduce -- il candidato piu' forte e' il
                   pattern multi-turno con storia che cresce (vedi braccio 5, addendum
                   coordinatore).
```

## Braccio 4 — t24_tool_campione (config campione + SOLO jinja/template/reasoning) — addendum 1

```text
tag              = t24_tool_campione_b512_r1_20260823
runner           = campione_plus_jinja_launcher.ps1 -- REPLICA ESATTA di run_porto_hot.ps1
                   (stesso env, stesso SpecNmax=2/SpecConf=0.80, stesso -c 10000 -ub 64,
                   stesso --cache-ram 8192 --ctx-checkpoints 32 -cms 8192) + SOLO in coda
                   `--jinja --chat-template-file <stesso file del bat> --reasoning on
                   --reasoning-preserve`. Un solo asse di differenza rispetto al braccio 1.
comando esatto   = powershell campione_plus_jinja_launcher.ps1 -Tag t24_tool_campione_b512_r1_20260823 -MaxTokens 512
tempo di boot    = 140 s
eval t/s         = 14.95   (contro 14.44 del braccio 1: DELTA +3,53% -- leggermente sopra la
                   deriva di banco 2-3%, ma di SEGNO POSITIVO: nessuna traccia di rallentamento)
prompt t/s       = 21.67 (= 21.75 del braccio 1, entro rumore)
p1               = 0.87234 (287/329, mean len 2.29) -- IDENTICO BIT PER BIT al braccio 1
SHA output       = 90A28151DAB6AF1282A5CB68933E99352F7362D89E4E31F85130023F6E6454ED
                   -- IDENTICO CARATTERE PER CARATTERE al braccio 1 (stesso SHA, stessi 1311
                   caratteri)
copie/buchi      = domanda 94929, colpi 70939 (74.7%), buchi 23990 -- IDENTICO al braccio 1
riga cache-esperti = IDENTICA carattere per carattere ai bracci precedenti
profiler/graph stats = SPENTI (0 righe sched-profilo; GGML_CUDA_GRAPH_STATS=0(D))
graphs           = ACCESI (assente)
SPECULAZIONE SOTTO JINJA (config campione) = ATTIVA -- "draft acceptance = 0.87234 (287
                   accepted / 329 generated)", identica al non-jinja
server vivi max  = 1
esito            = DIAGNOSTICO
percorsi file    = ...\work\runs\t24_tool_campione_b512_r1_20260823.{server.log,summary.json,r1.output.txt,r1.response.json,server.out}
anomalie         = nessuna; ctrl-c pulito; zero errori/divergenze; postflight pulito
VERDETTO ADDENDUM 1 = jinja+chat-template+reasoning, aggiunti DA SOLI alla config campione
                   (nessun'altra variabile toccata), producono una corsa BIT-IDENTICA
                   (stesso SHA, stesso p1, stesse copie) al non-jinja: la traiettoria di
                   calcolo non cambia affatto per questa richiesta a turno singolo. Il costo
                   netto della modalita' tool sopra il regime migliore e' ~0% (il +3,5% e'
                   rumore di banco, nella direzione opposta a un rallentamento). CHIUDE
                   l'addendum 1: jinja/template/reasoning non e' la causa del buco 14->11.
```

## Braccio 5 — t24_codex_reuse (riuso KV/prompt dall'endpoint chat, pattern Codex) — addendum 2

### Tentativo 1 — CRASH (OOM), reperto importante di per se'

```text
tag              = t24_codex_reuse_20260823 (tentativo 1)
config server    = bat-pulito (identica al braccio 2/3: jinja+template+reasoning, -c 150000,
                   sonde spente)
system prompt    = 500 righe sintetiche generate -> risultato REALE 27.985+ token (molto
                   piu' dei 10-13k stimati: il testo di riempimento tokenizza a ~60
                   token/riga, non ai ~25-30 assunti in fase di progettazione dello script)
esito            = CRASH -- "CUDA error: out of memory" in ggml_cuda_mul_mat_q
                   (D:\llama-subtract\ggml\src\ggml-cuda\mmq.cu:183), preceduto da
                   "layer-major: staging di 1729 MiB NON allocabile", durante/subito dopo il
                   prefill di r1 (prompt processing arrivato al 93%, n_tokens=27985,
                   182,34 token/s -- il prefill IN SE' era veloce e sano fino a quel punto)
processo         = uscito da solo dopo l'assert CUDA (connessione TCP chiusa a meta',
                   Invoke-RestMethod ha sollevato WebException); NON e' stato necessario
                   Stop-Process; postflight pulito subito dopo (processi=0, VRAM 352 MiB,
                   RAM 89,9 GB, GPU 45°C, porte libere) -- nessuna quiete a orologio, solo
                   verifica macchina-pulita, poi si incatena
REPERTO          = a ~28-30k token di prompt FRESCO (non riusato), questa combinazione
                   (bat-pulito, IQ2XXS, mapped-ibrido, KV_RING_VRAM_TOKEN=2048, cache-ram=0,
                   -c 150000) esaurisce la VRAM su un buffer di staging del prefill. La soglia
                   "~30k" e' la STESSA soglia a cui l'utente riferisce che Codex CLI diventa
                   inusabile: puo' non essere SOLO un problema di riuso KV lato client, ma
                   anche un TETTO VRAM reale lato server intorno a quella taglia. Segnalato
                   come reperto a se stante, non ancora diagnosticato a fondo (fuori mandato
                   di questo banco economico: servirebbe un banco dedicato sulla dimensione
                   del buffer "layer-major staging").
azione           = ripetuto il test con un system prompt piu' piccolo (~180 righe, mirato a
                   10-13k token come da mandato originale) per rispondere comunque alla
                   domanda sul MECCANISMO di riuso, che non richiede necessariamente 30k
                   token per essere osservato. Vedi tentativo 2 sotto.
```

### Tentativo 2 — CRASH IDENTICO a ~10,7k token (non e' questione di 30k)

```text
tag              = t24_codex_reuse_v2_20260823 (tentativo 2, prompt ridotto a 180 righe)
system prompt    = ~10.744 token stimati (n_tokens=6144 a progress=0.57 dal log prima del
                   crash -> totale atteso ~10.779), quindi centrato nel target 10-13k
esito            = CRASH IDENTICO: stessa riga esatta "layer-major: staging di 1729 MiB NON
                   allocabile" -> "CUDA error: out of memory" in ggml_cuda_mul_mat_q,
                   stesso identico size di staging (1729 MiB) del tentativo 1 a 28k token
CONCLUSIONE      = il crash NON scala col numero di token del prompt (30k e 10,7k falliscono
                   allo stesso modo, sullo stesso buffer di taglia IDENTICA) -- il colpevole
                   e' quasi certamente che la richiesta a 68 token (bracci 1-4, tutti con un
                   SOLO messaggio "user") sta sotto UNA sola ubatch (2048), mentre QUALUNQUE
                   prompt che supera la ubatch di 2048 token forza uno stadio di "layer-major
                   staging" che su questa combinazione bat (-c 150000 -ub 2048 --cache-ram 0,
                   VRAM gia' quasi satura dal buffer ibrido mappato 74.304 MiB + KV ring) non
                   ha piu' margine VRAM. Il "circa 30k" riferito dall'utente per Codex CLI e'
                   probabilmente quando la SUA metrica cumulativa di conversazione tocca quella
                   soglia, ma il crash server-side puo' scattare molto PRIMA (~2-3k token in
                   una singola richiesta), non a 30k -- coerente con "unusabile", non con un
                   semplice rallentamento.
macchina         = pulita dopo il crash (0 processi, VRAM 351 MiB, RAM 90,5 GB, GPU 46°C,
                   porte libere) -- nessuna quiete a orologio, verificato e incatenato subito
```

### Tentativo 3 — isolamento della causa: NON e' il ruolo "system", e' la TRANSIZIONE DI FASE VRAM_A_FASI

Test mirato (script `oom_isolate_test.ps1`): UNA sola richiesta, UN SOLO messaggio "user"
(nessun "system"), stessa config bat-pulito, ~150 righe di riempimento (~6.200 token totali,
sotto la soglia dei tentativi 1-2).

```text
tag              = oom_isolate_useronly_20260823
esito            = CRASH ANCORA, stessa identica firma ("layer-major: staging di 1729 MiB
                   NON allocabile" -> CUDA OOM in ggml_cuda_mul_mat_q) -- QUINDI NON e' il
                   ruolo "system": un prompt lungo anche solo come "user" crasha allo stesso
                   modo. Il ruolo del messaggio e' irrilevante.
punto esatto del crash (log verbatim) =
  "prompt processing, n_tokens = 4097, progress = 0.66" (prefill in corso, sano, 213,87 tok/s)
  poi, alla FINE del prefill, transizione a decode:
  "vram-a-fasi: fase=decode livello=2  cache 0 -> 473 slot (+473, +3194 MiB)  riciclati 2158
   MiB dal buffer  VRAM libera 0 MiB  [8.7 ms, cambio n. 2]"
  "vram_a_fasi: fase=decode livello=2 ubatch riserva=64  buffer di calcolo 2296.35 ->
   137.95 MiB (-2158.40)  [56.6 ms]"
  "layer-major: staging di 1729 MiB NON allocabile" -> CUDA error: out of memory
CAUSA RADICE IDENTIFICATA = non e' la lunghezza del prompt di per se', e' la TRANSIZIONE DI
                   FASE 1->2 di VRAM_A_FASI (prefill a footprint ridotto -> decode con cache
                   esperti piena, 473 slot = 3194 MiB, + un buffer di staging layer-major da
                   1729 MiB). Con un prompt di 68 token (bracci 1-4) il footprint di prefill e'
                   minuscolo e la transizione ha margine; con QUALUNQUE prompt di qualche
                   migliaio di token, il buffer di calcolo del prefill cresce abbastanza da
                   lasciare "VRAM libera 0 MiB" appena prima del salto, e la transizione
                   fallisce SEMPRE, indipendentemente dal ruolo del messaggio o dal superare
                   30k. Il sospetto principale e' `LLAMA_VRAM_A_FASI_MARGINE=0` (impostato dal
                   bat, vedi env del braccio 2/3): margine di sicurezza ZERO per la
                   transizione. NON verificato in questo banco (fuori mandato/tempo): alzare
                   quel margine, o ridurre `LLAMA_CACHE_ESPERTI_SLOT`, o rivedere
                   `LLAMA_VRAM_A_FASI_UB=64`, sono le prime leve candidate per un banco
                   dedicato di riparazione.
macchina         = pulita dopo il crash (verificato)
```

**QUESTO, non le sonde ne' jinja, e' il candidato piu' probabile per "diventa inusabile":**
un crash duro (non un rallentamento) su qualunque richiesta con piu' di poche migliaia di
token in questa esatta configurazione bat. Un client come Codex CLI che invia contesto o
storia di conversazione oltre quella soglia otterrebbe un errore dal server, non semplicemente
un t/s piu' basso -- coerente con "inusabile" molto piu' di un -1% o -24% di velocita'.

**Domanda originale addendum 2 (il riuso KV/prompt scatta dall'endpoint chat?) rimane APERTA,
non falsificata**: non e' stato possibile completare nemmeno r1 di un turno multi-messaggio con
prompt non banale, quindi r2/r3 (dove si sarebbe letto il riuso) non sono mai stati raggiunti.
La domanda sul riuso e' logicamente SUCCESSIVA alla riparazione del crash: prima si ripara la
transizione VRAM_A_FASI, poi si puo' tornare a misurare il riuso.

---

## Bonus economico — profilo Codex CLI per il server locale (addendum 2, punto 3)

File letto: `C:\Users\imanu\.codex\config.toml` (228 righe, letto per intero) +
grep di `8100|model_providers|profiles|context_window|base_url` su tutto `~/.codex/*.toml`.

```text
RISULTATO: NESSUN profilo/model_provider per localhost:8100 in tutto config.toml.
           NESSUN campo context_window o max_tokens dichiarato per NESSUN modello
           (nemmeno per il default "gpt-5.6-luna"). NESSUN base_url. L'unica menzione di
           "localhost" e' una regola di permesso di rete generica
           ([permissions.ds4-work.network.domains] "localhost" = "allow"), non un profilo
           modello. Nessun altro file .toml in ~/.codex/ (solo due sessioni browser
           irrilevanti) menziona la porta 8100.
```

**Conseguenza**: se Codex CLI parla col server locale, lo fa con un meccanismo NON persistito
in `config.toml` (flag a riga di comando o variabile d'ambiente della sessione, es.
`OPENAI_BASE_URL`, non trovata qui). Senza una finestra di contesto dichiarata per quel
"modello" sconosciuto a Codex, il client usera' quasi certamente un default INTERNO
conservativo, scollegato dal vero `-c 150000` del server -- spiegazione lato-client
plausibile per una compattazione precoce, **indipendente** dal crash lato-server sopra (le
due cause possono coesistere: il client compatta per prudenza PRIMA, il server comunque
crasherebbe DOPO se il client mandasse un prompt lungo). Non verificato: quale sia il default
interno di Codex per un modello sconosciuto (fuori dal perimetro leggibile in locale).

---

## VERDETTO COMPLESSIVO DEL BANCO 23/8

| braccio | config | t/s | delta vs base | p1 | SHA output |
|---|---|---:|---:|---|---|
| 1 t24_base | campione, no jinja, sonde off | 14,44 | — (riferimento) | .87234 | 90A28151... |
| 2 t24_bat | bat completo, sonde off | 14,45 | +0,07% | .87714 | 644ACC40... |
| 3 t24_bat_sonde | bat completo, sonde ON | 14,28 | -1,18% vs braccio 2 | .87714 | 644ACC40... (= braccio 2) |
| 4 t24_tool_campione | campione + SOLO jinja/template/reasoning | 14,95 | +3,53% | .87234 | 90A28151... (= braccio 1) |
| 5 t24_codex_reuse | bat + storia multi-turno, prompt >2k token | **CRASH (OOM)**, non un t/s | — | — | — |

**Attribuzione del buco 14->11 (~-24%) riferito dall'utente**: NON spiegato ne' dalle sonde
(-1,2%) ne' da jinja/tool-mode (0/+3,5%, rumore). Sommati insieme (braccio 3 vs braccio 1):
-1,1%. **Il vero candidato e' il crash di transizione VRAM_A_FASI** su prompt di piu' di
poche migliaia di token (bracci 5 e i due tentativi di isolamento): un uso reale con contesto
o storia di conversazione lunga non rallenta all'11 t/s, PUO' letteralmente fallire con un
errore CUDA OOM prima di produrre un token.

**Verdetto secco sulla domanda dell'utente**: la colpa NON e' delle sonde (piccola, -1,2%,
gia' commentate correttamente il 23/8) ne' della modalita' tool/jinja/reasoning (misurata
due volte, ~0%). Il sospetto originale era mal indirizzato: il problema reale e' un
crash-per-VRAM alla transizione prefill->decode di `VRAM_A_FASI` (candidato:
`LLAMA_VRAM_A_FASI_MARGINE=0`) che si attiva con QUALUNQUE prompt/storia oltre poche migliaia
di token in questa configurazione -- coerente com'era descritta l'esperienza reale
("inusabile", non "piu' lento"). Priorita' consigliata: riparare quella transizione prima di
richiedere altri banchi su sonde o jinja.

**Stato macchina a fine banco**: pulita (0 processi llama, VRAM 288 MiB, RAM 90,9 GB libera,
GPU 45°C, porte 8099/8100 libere). Nessun commit eseguito. Nessuna quiete a orologio applicata
dal braccio 3 in poi (regola abolita dal 12/8, corretta a banco in corso). Script usati (fuori
repo, in scratchpad, non committati): `bat_replica_launcher.ps1`,
`campione_plus_jinja_launcher.ps1`, `codex_reuse_test.ps1`, `oom_isolate_test.ps1`.

---

## Turno riparazione (23/8 sera, dopo il banco sopra) — CRASH RIPARATO + riuso KV CONFERMATO VIVO

Mandato: rendere il server usabile sui prompt lunghi. Tre passi. Binario canonico invariato
(vedi intestazione file). Script nuovi (scratchpad, non committati): `t25_repro.ps1` (repro
parametrizzato: Lines/Margine/Ub/B/MoeUb/Slot, un solo messaggio "user"), `t25_kvreuse.ps1`
(stessa parametrizzazione, 3 turni via `/v1/chat/completions`, system lungo ~13k).

### Passo 1 — lettura del codice PRIMA di sweeppare (regola di casa)

`D:\llama-subtract\ggml\src\ggml-cuda\cache-esperti.cu:2153-2317`
(`ggml_cuda_cache_esperti_fasi`): `LLAMA_VRAM_A_FASI_MARGINE` e' a MiB (`margine_mib`,
`atoi`), ma **anche quando la branca dinamica lo usa, il risultato e' sempre forzato al
minimo `slot_base`** (`if (voluti < slot_base) voluti = slot_base;`, riga ~2234) — e
`slot_base` viene da `LLAMA_CACHE_ESPERTI_SLOT` (473 nel bat). MARGINE puo' solo far
crescere la cache OLTRE slot_base quando c'e' VRAM libera in abbondanza: non puo' MAI
farla scendere sotto. Con `LLAMA_CACHE_ESPERTI_SLOT=473` fisso, MARGINE e' strutturalmente
inerte per QUESTO problema, qualunque valore gli si dia. Il buffer "layer-major" (1729 MiB,
`cache-esperti.cu:5609-5644`) e' un blocco A TAGLIA FISSA = `n_esperti * byte_slot` (256 x
6.75 MiB), NON scala con `-ub`: quello che scala con `-ub` e' il buffer di calcolo del
prefill (`sched_reserve`), che libera spazio INDIRETTAMENTE per il blocco fisso.

### Manopole — repro a 1 messaggio "user", ~6,2k token (oom_isolate-style), poi ~28k

| manopola (rispetto al bat) | 6,2k | VRAM libera alla transizione | prefill t/s | decode t/s |
|---|---|---:|---:|---:|
| **(a)** `MARGINE=512` (resto bat: ub/b=2048, slot=473) | **CRASH-OOM identico** (stessa riga, "cache 0->473", 0 buchi diversi) | 0 MiB | — | — |
| **(b)** `-ub 512 -b 512` (margine=0, slot=473) | **CRASH-OOM** (spostato da 33% a 91% di progress: il buffer di calcolo scende da 2296 a 621 MiB, ma non basta) | 58 MiB (serve ≥1729) | — | — |
| **(c)** `-ub 512 -b 512` + `LLAMA_CACHE_ESPERTI_SLOT=150` (margine=0) | **SOPRAVVIVE** | 2249 MiB | 99,97 | 11,28 |
| (c) stessa combo, ripetuta a **~28k** (27908 tok reali) | **SOPRAVVIVE** | 2199 MiB | 100,08 | 10,63 |

**Verdetto (a)+(b) FALSIFICATI da soli**: nessuna delle due manopole indicate dal mandato
basta; la loro combinazione e' anche IDENTICA a (b) da sola (MARGINE resta inerte). Terza
leva NECESSARIA, gia' candidata dal banco di ieri sera (tentativo 3): **ridurre
`LLAMA_CACHE_ESPERTI_SLOT`** (473->150, -68%) per lasciare margine reale al blocco
layer-major da 1729 MiB al momento esatto della transizione prefill->decode. Costo
misurato: decode 11,28-10,63 t/s contro 14,44-14,45 t/s del campione/bat-corto a slot=473
(braccio 1-2 di ieri sera) = **-21,9% / -26,4%**. 150 e' una scelta PRUDENTE (margine finale
~2200 MiB, ben oltre i 1729 richiesti): un valore meno drastico (dedotto, NON misurato, es.
~250-300) probabilmente basta e recupera parte del t/s, ma bisecare costava altri banchi da
5-8 minuti l'uno e non rientrava nel regime economico di stanotte.

### Passo 2 — riuso KV dall'endpoint chat: VIVO, confermato due volte

Config: combo (c) sopra, system ~13k righe sintetiche (217 righe stile codex_reuse), 3 turni
`/v1/chat/completions`, `cache_prompt=true`. Tag `t25_kvreuse_slot150_20260823`.

```text
r1 (system+u1, freddo)  prompt_tokens_usage=13053  wall=139,77 s
  prompt eval time = 129775.22 ms / 13053 tokens (9.94 ms/tok, 100.58 tok/s)
r2 (+assistant+u2)      prompt_tokens_usage=13202  wall=17,10 s
  prompt eval time =   7790.39 ms /   181 tokens (43.04 ms/tok,  23.23 tok/s)
r3 (+assistant+u3)      prompt_tokens_usage=13349  wall=18,17 s
  prompt eval time =   7793.73 ms /   167 tokens (46.67 ms/tok,  21.43 tok/s)
```

**IL NUMERO**: r2 e r3 rivalutano SOLO 181 e 167 token (il delta del turno, non i 13053+
cumulativi) — **riuso DELTA-ONLY, VIVO**, esattamente nel range 150-300 tok atteso dal
mandato. Il caso Codex (system fisso + storia che cresce di pochi turni corti) e' RISOLTO
per intero dall'endpoint chat, A CONDIZIONE di girare sulla combo (c) che non crasha. Prima
di ieri sera questo test non era MAI arrivato a r2/r3 (crash su r1). Nota: Codex CLI reale
parla quasi certamente con `/v1/responses` (vedi Passo 3), non `/v1/chat/completions`
testato qui — il binario canonico li implementa ENTRAMBI (`server.cpp:450-453`,
`post_responses_oai` converte verso chat completions), ma l'equivalenza esatta del
comportamento di riuso fra i due endpoint non e' stata verificata byte per byte in questo
banco (dedotto plausibile, non misurato).

### Passo 3 — consegna pratica

**(a) Diff esatto per `avvia ds4 locale.bat`** (canonico bonificato, vedi intestazione file
per lo SHA): il mandato chiedeva "1-2 righe" ma la misura sopra dice che ne servono 3 (il
lettore fa da floor duro su MARGINE, vedi Passo 1) — dichiarato, non nascosto:

```diff
- set "LLAMA_CACHE_ESPERTI_SLOT=473"
+ set "LLAMA_CACHE_ESPERTI_SLOT=150"
...
-  -b 2048 ^
-  -ub 2048 ^
+  -b 512 ^
+  -ub 512 ^
```

più, come righe commentate pronte (promosse dai turni 20-23 del banco GRAPHS/gather,
verificate a getenv `atoi(v)!=0` in `kv-gather.cu:174-179` e `cache-esperti.cu:3236-3237`
— attivare a scelta, non testate in QUESTO banco):

```bat
rem set "LLAMA_KV_GATHER=1"
rem set "LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1"
```

Trade-off dichiarato: prefill ~3x piu' lento sui prompt lunghi (100 t/s a ub512 contro
~200+ a ub2048 sui chunk brevi) e decode -22/-26% (sopra) — accettabile per rendere il
server USABILE oltre i 68 token invece di crashare, non gratis.

**(b) Snippet `config.toml` per il Codex dell'altro PC** (IP LAN di questa macchina:
`192.168.1.30`; verificato che nessun profilo/model_provider per la porta 8100 esiste gia'
in `~/.codex/config.toml` di QUESTO pc, quindi sintassi dedotta da doc esterna, non da un
esempio locale funzionante — **da fumare-testare sull'altro PC prima di fidarsene**):
Codex >=0.59 (feb 2026) ha eliminato `wire_api="chat"`, resta solo `"responses"` — motivo
per cui il binario canonico e' stato verificato supportare `/v1/responses` nativamente
(sopra) prima di scrivere questo snippet.

```toml
[model_providers.ds4_local]
name = "ds4_local"
base_url = "http://192.168.1.30:8100/v1"
wire_api = "responses"
env_key = "DS4_LOCAL_API_KEY"
requires_openai_auth = false

[profiles.ds4local]
model = "ds4-0731-iq2xxs"
model_provider = "ds4_local"
model_context_window = 150000
approval_policy = "on-request"
```

Sull'altro PC: `setx DS4_LOCAL_API_KEY "Stigrangazzi86!11235813"` poi `codex --profile
ds4local`.

**Stato macchina a fine turno riparazione**: pulita (0 processi llama, VRAM 339 MiB usati /
11777 liberi, RAM 89,7 GB libera, GPU 47°C, porte 8099/8100 libere). Nessun commit eseguito.
Script fuori repo in scratchpad: `t25_repro.ps1`, `t25_kvreuse.ps1`.

---

## Turno esecutore (23/8, a seguire) — ricerca dello SLOT massimo sicuro: IL 28k NON è IL CASO PEGGIORE

Mandato: partendo dalla combo sopravvissuta (`-ub 512 -b 512` + `LLAMA_CACHE_ESPERTI_SLOT=150`,
margine 2.249 MiB liberi a 6,2k e 2.199 a 28k), trovare il massimo SLOT sicuro (stima iniziale
~250 slot in più, 6,75 MiB/slot) usando il repro 28k come presunto caso peggiore, convergendo
con margine ≥400 MiB liberi alla transizione. Binario invariato (SHA verificato identico
all'intestazione file prima del banco). Preflight pulito (0 processi, porte libere, GPU a
riposo 339 MiB/11777 liberi, RAM 89,3 GB, disco C 45,9/D 115,5 GB, uptime 4329,8 min).
Script: `t25_repro.ps1` (scratchpad, invariato, parametri `-Lines -Margine -Ub -B -MoeUb -Slot`).

### Lanci sul repro 28k (Lines=680, 27908 token reali)

| SLOT | esito | VRAM libera a "cambio n. 2" | prefill t/s | decode t/s |
|---:|---|---:|---:|---:|
| 400 | sopravvive | 511 MiB | 100,11 | 11,95 |
| 440 | sopravvive | 241 MiB | 100,13 | 11,67 |
| 416 | sopravvive | 398 MiB (**sotto** i 400 richiesti, di 2 MiB) | 100,12 | 12,17 |
| 410 | sopravvive | 443 MiB | 100,04 | 11,96 |
| 250 (conferma finale) | sopravvive | 1523 MiB | 99,45 | 10,20 |

Il modello lineare 6,75 MiB/slot **regge alla perfezione** dentro questa serie (400→440→416→410,
tutti a 28k): `libera(slot) = 2199 − (slot−150)·6,75`, verificato a <1 MiB su quattro punti
indipendenti (esempio: slot 440 predetto 241,5, misurato 241). Su questa sola serie, 410-416
sarebbe stato il "massimo sicuro" cercato dal mandato.

### Il repro 6,2k SMENTISCE il 28k come caso peggiore

Conferma del vincitore apparente (SLOT=410) sul repro 6,2k (Lines=150, 6178 token reali):
**CRASH-OOM**, stessa firma esatta (`layer-major: staging di 1729 MiB NON allocabile` → CUDA
OOM in `mmq.cu:183`), **nonostante un margine nominale PIÙ ALTO** del 28k che era sopravvissuto
(493 MiB contro 443). Ripetuto con SLOT=400 (il primo lancio, quello con più margine nominale
di tutti sul 28k): **CRASH-OOM anche qui**, margine nominale 561 MiB — ancora insufficiente.

Lettura dei due log affiancati (`t25_slot410_ub512_28k_20260823.server.log` vs
`t25_slot410_ub512_6k_20260823.server.log`, righe intorno a "cambio n. 2"): in ENTRAMBI i casi
compare la stessa riga `porto-cb: epoca=1 IN VIGORE senza cambi di leva (ricattura comunque,
l'epoca e' salita)` subito dopo la transizione. Nel caso 28k (sopravvive) questa riga è seguita
da centinaia di catture di chiave che procedono senza intoppi. Nel caso 6,2k (crash) la riga
successiva è **immediatamente** `layer-major: staging di 1729 MiB NON allocabile`. Conclusione:
il numero "VRAM libera N MiB" stampato al "cambio n. 2" **non predice la sopravvivenza fra
casi di lunghezza diversa** — la ricattura del grafo CUDA innescata a quel punto consuma/richiede
VRAM aggiuntiva in modo dipendente dalla lunghezza del prompt (verosimilmente da quanti "shape"
di batch sono già stati catturati durante il prefill: un prefill lungo, con molti più chunk da
512 token, arriva alla transizione con quasi tutte le chiavi di grafo già catturate; un prefill
corto ne lascia molte da catturare proprio nel momento più stretto). Il modello 6,75 MiB/slot
resta valido **dentro** una singola lunghezza di prompt, ma la soglia assoluta di sopravvivenza
è determinata dal caso **corto** (6,2k), non dal lungo — l'ipotesi di mandato ("il 28k è il
caso peggiore") è **falsificata**.

### Bisezione sul vero caso vincolante (6,2k)

| SLOT | esito | VRAM libera a "cambio n. 2" | prefill t/s | decode t/s |
|---:|---|---:|---:|---:|
| 410 | **CRASH-OOM** | 493 MiB (insufficiente) | — | — |
| 400 | **CRASH-OOM** | 561 MiB (insufficiente) | — | — |
| 250 | sopravvive | 1568 MiB | 98,62 | 12,08 |

La soglia reale per il 6,2k sta fra 250 (vivo) e 400 (morto) — non ulteriormente bisecata per
restare nel regime economico (già 9 lanci contro i 3-4 preventivati, giustificati dalla scoperta
di cui sopra). SLOT=250 è stato poi riconfermato anche sul 28k (tabella sopra, ultima riga):
sopravvive con 1523 MiB liberi, ampio margine su entrambi i casi.

### Verdetto e valore vincente

**SLOT=250** è il valore raccomandato: sopravvive su ENTRAMBI i repro (6,2k: 1568 MiB liberi;
28k: 1523 MiB liberi — margini ~3,5× il target di 400 MiB scritto nel mandato, target che si è
rivelato calibrato sul caso sbagliato). Decode: 6,2k passa da 11,28 (SLOT=150) a **12,08**
(+7,1%); 28k passa da 10,63 (SLOT=150) a 10,20 (**-4,0%, verosimilmente rumore di banco**: colpo
singolo senza repliche, protocollo di screening §6.2 runbook). **NON è il "massimo" nel senso
letterale del mandato** (SLOT=400 sarebbe più aggressivo ma crasha sul 6,2k, quindi non è
sicuro): è il massimo fra i valori effettivamente VERIFICATI su entrambi i casi. Uno spazio
1568→561 MiB resta inesplorato fra 250 e 400 sul 6,2k: chi volesse spingere oltre 250 deve
ripartire bisecando lì, non dal modello lineare (falsificato fra lunghezze diverse).

### Diff aggiornato per `avvia ds4 locale.bat` (sostituisce quello del turno precedente)

```diff
- set "LLAMA_CACHE_ESPERTI_SLOT=473"
+ set "LLAMA_CACHE_ESPERTI_SLOT=250"
...
-  -b 2048 ^
-  -ub 2048 ^
+  -b 512 ^
+  -ub 512 ^
```

**Stato macchina a fine turno**: pulita (0 processi llama, VRAM 566 MiB usati / 11550 liberi,
RAM 89,1 GB libera, GPU 42°C, porte 8099/8100 libere). Nessun commit eseguito. 8 lanci server
totali in questo turno (tag `t25_slot{400,440,416,410}_ub512_28k`, `t25_slot{410,400,250}_ub512_6k`,
`t25_slot250_ub512_28k`), tutti sullo script scratchpad invariato `t25_repro.ps1`.
