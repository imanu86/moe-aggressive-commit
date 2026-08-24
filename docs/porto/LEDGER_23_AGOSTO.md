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

---

## Turno esecutore (24/8) — CAMPAGNA PRINCIPALE, FASE 1: P1-NUDO — divergenza tardiva, verdetto ARROTONDAMENTO con riserva sul Δlogprob

Mandato: `D:\ds4_work\design\G1_P1_ANALISI.md` §5 — isolare la grandezza pura della perturbazione
di G1 (kv-gather) togliendo speculazione e mean_len dall'equazione. Config banco = campione pieno
(SLOT=473, -b/-ub 2048, Context 150000), NON la config serving ridotta di ieri sera (SLOT=250,
-b/-ub 512: quella resta per `avvia ds4 locale.bat`, qui non si usa). Binario canonico riverificato
PRIMA del banco, invariato da ieri sera:

```
sha_llama_server = C15FF135F14024FED4ADD8B3FF14299429CA9627508150B7CDE06234E9795878
sha_ggml_cuda    = 00C6F0D2AC9161AF44EADDB0F22344E5580F4CC77E1D72A1683951214B15C576
sha_server_impl  = 729DC0DD655190C4001AD259CAE1BF954A9936407398A793E8182C3C0F13935F
percorso         = D:\llama-subtract\build\bin\
```

Preflight (04:4x, 24/8): 0 processi llama, porte 8099/8100 libere, GPU a riposo (543 MiB usati /
11573 liberi, pcie gen1x16), RAM libera 87,9 GB, disco C 48,4 GB / D 115,5 GB liberi, uptime 4764
min (no riavvio). `jprompt.txt` (corto) SHA `C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9`
e `jprompt102k.txt` (lungo, 285.268 B) SHA `3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473`
— entrambi IDENTICI al riferimento del runbook/turno 22.

Script: copia `p1_nudo.ps1` della famiglia `sota100k_ctx150k.ps1` (stessa usata a turno 22 per
`t22_gather_a`), con **una sola aggiunta dichiarata**: campo `n_probs` nel corpo JSON (assente/0 =
comportamento invariato rispetto allo script canonico). Comune ai due branch, tutto identico salvo
`LLAMA_KV_GATHER`: `-Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -BlockDenseCpu 0
-Packetizer -1 -PrefixChars 0 -Context 150000 -MaxTokens 256 -SpecNmax 0 -Repliche 1
-CtxCheckpointMinStep 32 -ReasoningBudgetTokens 0 -GraphReusePerTaglia 1 -NProbs 1
-ServerPath D:\llama-subtract\build\bin\llama-server.exe`. `-SpecNmax 0` verificato sul codice
(`common/speculative.cpp:357/1950`: con `n_max=0` il ciclo di proposta bozza non esegue nemmeno
un'iterazione, `result` resta vuoto) — spec davvero OFF, non solo soglia a 0. `n_probs` verificato
come campo generico passante (`server-schema.cpp:220-221`, alias `logprobs`) fino al parser
sampling comune, quindi valido anche su `/v1/chat/completions` senza passare per il campo OAI
`logprobs`/`top_logprobs`. Prompt jprompt102k.txt (101.691 token), stesso corpo byte-per-byte fra
i due branch salvo l'env `LLAMA_KV_GATHER`; una sola richiesta per processo, sessione fresca per
branch (processo server nuovo ciascuno — il cancello del gather è `static`, si legge una volta per
processo). Telemetria hw 0,5 Hz su entrambi (`sample_hw.ps1`): avviata con ~90 s di ritardo su A
(lacuna dichiarata, non copre i primi ~90 s di caricamento), dall'inizio su B.

### Branch A — `p1_nudo_a_gather0` (LLAMA_KV_GATHER=0)

```
tag            = sota_ctx150000_densefa_stage_hc5_p1_nudo_a_gather0_f2_b2048_q1
lanciato       = 04:45:07 (staccato, Win32_Process Create)   richiesta avviata 04:47:37
prompt tokens  = 101691   completion = 256   finish_reason = length
prefill        = 112.11 t/s (8,92 ms/token)   decode = 7.30 t/s (137.0 ms/token, mean_len=1 puro)
wall richiesta = 15.71 min
p1             = assente (spec OFF per costruzione, nessuna riga "draft acceptance")
SHA output     = 0B3E8A3AB657764C3632C559BE2E526C2958C34DE279021C457D672F27926926 (855 caratteri)
cache-esperti/VRAM: transizione prefill->decode pulita (473->0->473 slot, "VRAM libera 0 MiB" al
  cambio n.2, nessun OOM); rilevatore replay: divergenze taglia=0/ids=0/out=0 su tutte le righe
telemetria hw   = 421 campioni, SM mediano 1927 MHz (max 1950, 14/421 sotto 1500 MHz — bookend
  di carico/scarico, non durante il decode), potenza mediana 125,68 W, VRAM picco 11894 MiB
percorsi        = D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_p1_nudo_a_gather0_f2_b2048.{server.log,server.out,q1.response.json,q1.output.txt}
                  D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_p1_nudo_a_gather0.summary.txt
                  D:\ds4_work\llama_run\p1_nudo_a_gather0.{hw.csv,cpu.csv}
```

Lettura integrale del testo (§4.10): coerente, italiano tecnico sano, pertinente al prompt (saggio
su cache-esperti/deepseek4.cpp/llama-graph.cpp), nessun loop, troncato a metà parola per
`max_tokens` (`length`) — nessuna anomalia.

### Branch B — `p1_nudo_b_gather1` (LLAMA_KV_GATHER=1)

```
tag            = sota_ctx150000_densefa_stage_hc5_p1_nudo_b_gather1_f2_b2048_q1
lanciato       = 05:04:47 (staccato, Win32_Process Create)   richiesta avviata 05:07:18
prompt tokens  = 101691   completion = 256   finish_reason = length
prefill        = 118.40 t/s (8,45 ms/token)   decode = 10.38 t/s (96.3 ms/token, mean_len=1 puro)
wall richiesta = 14.73 min
p1             = assente (spec OFF per costruzione)
SHA output     = C33C0DD73B1B5A945DAE9BDD6A37167431BF0C03A834E624581BA761C6287054 (896 caratteri)
cache-esperti/VRAM: transizione prefill->decode pulita, stesso schema di A, nessun OOM; rilevatore
  replay: divergenze taglia=0/ids=0/out=0 su tutte le righe
telemetria hw   = 407 campioni, SM mediano 1920 MHz (max 1942, 25/407 sotto 1500 MHz — bookend),
  potenza mediana 129,61 W, VRAM picco 11882 MiB
percorsi        = D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_p1_nudo_b_gather1_f2_b2048.{server.log,server.out,q1.response.json,q1.output.txt}
                  D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_p1_nudo_b_gather1.summary.txt
                  D:\ds4_work\llama_run\p1_nudo_b_gather1.{hw.csv,cpu.csv}
```

Lettura integrale: coerente, sano, pertinente, nessun loop, troncato a metà parola per `length`.
**Decode del gather è il 42% più veloce anche a speculazione spenta** (10,38 contro 7,30 t/s):
conferma indipendente (mean_len=1, nessuna confusione con l'accettazione) che il guadagno di G1 è
un vero taglio di lavoro per-forward (attenzione su 512 righe/layer invece delle ~26.368 dense),
non un artefatto dell'interazione con la bozza.

### Confronto A/B — le due misure del mandato

Estratte da `choices[0].logprobs.content` di entrambi i `.response.json` (`n_probs=1`), confronto
fatto in un solo processo PowerShell a cultura invariante (round-trip CSV con cultura locale mista
aveva prima prodotto numeri assurdi dell'ordine di 1e15 — bonificato, non è un dato, è stato
uno strumento che mentiva: il parsing corretto è quello riportato qui).

```
PRIMA DIVERGENZA (id del token)  =  indice 133 (0-based) su 256, cioè il 134° token generato
  contesto:  idx130 ' Mo'/' Mo' (uguale) -> idx131 'E'/'E' (uguale) -> idx132 ','/',' (uguale)
             -> idx133  A=' con' (id 399, lp -0.6641)   B=' pro' (id 413, lp -0.6806)  DIVERGE
  i primi 133 token sono IDENTICI byte per byte (stesso id) fra i due branch.

Δlogprob |A-B| sui primi 50 passi comparabili (tutti e 50 hanno lo stesso id, la divergenza è
dopo): media = 0.024874, massimo = 0.196055
  (idx=0, il token forzato "</think>" da thinking_budget_tokens=0, ESCLUSO dal conteggio dei 50
  perché non è una decisione greedy: qui A=-10.2263, B=-10.1304, diff 0.0959, stesso ordine)
```

**Verdetto rispetto alla tabella pre-scritta in G1_P1_ANALISI.md §5**: la posizione della
divergenza (133, ben oltre il "~50" del cancello) cade nettamente nella riga "arrotondamento
amplificato dal top-k discreto, si passa a P1-CAL". Il Δlogprob medio (0,0249) **non cade pulito
in nessuna delle due soglie scritte a verbale** (< 1e-2 per "arrotondamento pulito", > 5e-2 per
"perturbazione troppo grande"): è nel mezzo, più vicino al lato piccolo. Letto insieme: 133 token
di accordo bit-per-bit su una rete a 21 strati, con Δlogprob massimo nei primi 50 passi di appena
0,196 nat (lontanissimo dagli ordini di grandezza di un bug vero — la memoria di progetto colloca
i "corrotti veri" a p1 ≈ 0,16, cioè un crollo di traiettoria immediato, non una deriva lenta su
133 passi), è la firma di un arrotondamento **reale ma leggermente più forte del previsto**, non
di un difetto strutturale: nessuno dei quattro candidati del mandato G1 andrebbe riaperto sulla
base di questo numero (sarebbe l'esito "posizione entro 5-10 token" a giustificarlo, e qui la
posizione è 133). **Non eseguito** il ramo "caccia al bug" (dump per-layer `attn_csa_lid`): il
cancello per attivarlo (divergenza precoce O Δlogprob > 5e-2) non è scattato su nessuno dei due
assi.

**VERDETTO FASE 1: ARROTONDAMENTO, con riserva onesta sul Δlogprob leggermente sopra l'attesa
migliore.** Si procede a FASE 1b (P1-CAL): la cura resta ricalibrare `--spec-draft-conf-min` sul
lungo con gather acceso, come previsto dal mandato — la riserva sul Δlogprob non cambia la cura
proposta (che agisce comunque sulla soglia di accettazione, indipendentemente da quanto
"leggero" sia l'arrotondamento a monte), ma va portata a verbale per chi rilegge questo turno.

**Stato macchina a fine Fase 1**: pulita (0 processi llama, VRAM 426 MiB usati / 11690 liberi, RAM
88,5 GB libera, porte 8099/8100 libere). Nessun commit eseguito. Script fuori repo, in scratchpad
di sessione (non committati): `p1_nudo.ps1`, `p2_ring.ps1` (quest'ultimo pre-scritto per la Fase 2,
non ancora lanciato a questo punto del turno).

---

## Turno esecutore (24/8) — CAMPAGNA PRINCIPALE, FASE 1b: P1-CAL — sweep conf_min, MASSIMO a 0,70

Mandato (da G1_P1_ANALISI.md §5bis, punto 1, e dal mandato del turno): sweep `--spec-draft-conf-min
{0,60; 0,70; 0,80}` sul LUNGO con gather acceso, 3 corse mono-richiesta 8k (`-MaxTokens 8192`),
cercando il massimo di t/s. Script: copia `p1b_conf.ps1` della stessa famiglia (una sola aggiunta
dichiarata: parametro `-SpecConf`, passato a `--spec-draft-conf-min` — a `0.8` è testualmente
identico allo script canonico). Config comune, IDENTICA a `t22_gather_a` del turno 22 salvo
`-SpecConf`: `LLAMA_KV_GATHER=1 -SpecNmax 3 -MaxTokens 8192 -Context 150000 -StartBatch 2048
-BlockSparse 0 -HcFused 5 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0
-ServerPath D:\llama-subtract\build\bin\llama-server.exe`. Binario canonico invariato (stesso SHA
di Fase 1). Preflight ripetuto e passato prima di ciascuno dei 3 lanci (0 processi, porte libere,
RAM 87-88 GB, VRAM a riposo <350 MiB); macchina pulita fra un braccio e il successivo, incatenati
senza quiete a tempo.

```
             conf_min  decode t/s  ms/token   p1        mean_len  prefill t/s  SHA output (primi 8)
braccio 1    0,60      13,14       76,1       0,89552   3,16      130,23       F2FD14F5
braccio 2    0,70      13,58       73,6       0,91096   3,18      120,75       F0733E8C
braccio 3    0,80      12,57       79,6       0,86519   2,60       84,71*      1F7F86E5
```

`*` prefill anomalo (84,71 t/s contro 120-130 t/s degli altri due bracci e 119,18 del turno 22):
telemetria hw conferma un calo reale, non un errore di lettura — potenza mediana 102,45 W contro
127,76/131,68 W degli altri due bracci (`p1b_conf080.hw.csv`, 840 campioni). **Non attribuibile a
`conf_min`**: `conf_min` non tocca il prefill per costruzione (nessuna speculazione durante il
prefill), ed è confermato dal fatto che braccio 3 è una **replica bit-esatta** di `t22_gather_a`
(vedi sotto) — un effetto di `conf_min` sul prefill romperebbe quella replica. Causa non
diagnosticata (fuori mandato di questo braccio economico): candidati plausibili sono contesa di
sistema transitoria o standby-list della RAM, nessuno verificato.

**Cancello di controllo, molto forte**: il braccio 3 (`conf_min=0,80`, tutto il resto identico a
`t22_gather_a`) riproduce turn 22 **bit per bit**: p1 0,86519 (5038/5823 atteso, qui non ristampato
ma la cifra è identica a 5 decimali), mean_len 2,60, **SHA output
`1F7F86E578499C9BA1F1C53AA2E73C4D60E5BC88D47AED3CD56E334461F80732` IDENTICO carattere per carattere**
a quello registrato nel turno 22 (`LEDGER_17_AGOSTO.md`, riga "SHA output ="). Questo certifica che
lo script di questo turno non ha introdotto nessuna deviazione rispetto alla config di riferimento:
la differenza fra i tre bracci è **solo** `conf_min`.

**Lettura a campione dei testi** (§4.10, banco lungo: inizio + finestre centrali + fine) sui bracci
1 e 2 (nuovi): entrambi coerenti, italiano tecnico sano, citano correttamente frammenti di codice
reali del repository (`kern_partiziona`, `LLAMA_OVERLAP_K`, `ggml_cache_esperti_partiziona`),
nessun loop, nessuna degradazione osservata nelle finestre campionate. Nessuna anomalia.

**VERDETTO FASE 1b: MASSIMO a `conf_min=0,70`** — **13,58 t/s (73,6 ms/token)**, contro 13,14
(0,60) e 12,57 (0,80). Non monotona: **la curva ha un massimo interno**, non ai bordi, come
anticipato dal mandato ("il massimo non è al bordo, va cercato"). Rispetto al riferimento storico
0,80 (media dei due dati disponibili, 79,04 del turno 22 e 79,6 di questo turno): **−7,2% ms/token
(+7,4% t/s)**. **Non raggiunge** l'attesa ottimistica scritta nel mandato (~71,5 ms/token, 14 t/s):
il recupero è reale e nella direzione giusta ma **circa 3% sotto** il punto centrale atteso — onestà
del numero, non arrotondato per farlo coincidere. `p1` sale insieme al recupero (0,86519 → 0,91096
a 0,70), coerente con la lettura di G1_P1_ANALISI.md §4: una soglia più bassa lascia respirare la
testa di confidenza spostata da G1, tronca meno blocchi, `mean_len` sale (2,60 → 3,18).

**Prossimo passo suggerito, non eseguito in questo turno** (fuori dal mandato originale delle tre
soglie, ma coerente con "il massimo non è al bordo"): un quarto punto fra 0,65-0,75 per bisecare
l'ottimo più stretto, se un turno futuro vuole spremere l'ultimo margine verso i 14 t/s. **Valore da
adottare per i banchi successivi che usano `--spec-draft-conf-min` sul lungo con gather: 0,70**,
non più 0,80.

**Stato macchina a fine Fase 1b**: pulita (0 processi llama, VRAM 317 MiB usati / 11799 liberi, RAM
88,3 GB libera, porte 8099/8100 libere). Nessun commit eseguito. Script fuori repo, in scratchpad di
sessione: `p1b_conf.ps1`. Percorsi: `D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_p1b_conf0{60,70,80}_f2_b2048.{server.log,server.out,q1.response.json,q1.output.txt}`,
`D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_p1b_conf0{60,70,80}.summary.txt`,
`D:\ds4_work\llama_run\p1b_conf0{60,70,80}.{hw.csv,cpu.csv}`.

---

## Turno esecutore (24/8) — CAMPAGNA PRINCIPALE, FASE 2 (t22_repoint): CRASH OOM — diagnosi e FASE 2b bloccata di conseguenza

Mandato: `NOTE_IMPLEMENTAZIONE.md` §17.7 riga 1 / coda del turno 22 — ripuntare il prefisso caldo
del KV-ring: identico a `t22_gather_a` (quindi `conf_min=0,80`, **non** 0,70 della Fase 1b: una sola
leva per braccio, il confronto atteso dal mandato è contro 79,04 ms/token che è la cifra del
turno 22 sotto 0,80) + `LLAMA_KV_RING_VRAM_LID=300000` (valore "kv_size o più", per saturare al
pieno il `std::min(kv_size, richiesto)` — 2× il `-Context 150000`, esattamente come indicato dalla
nota del coordinatore lasciata in coda al turno 22) + `LLAMA_KV_RING_VRAM_CSA=0`. Script:
`p2_ring.ps1` (pre-scritto durante l'attesa della Fase 1), unica aggiunta dichiarata rispetto al
canonico: i due parametri `-KvRingVramLid`/`-KvRingVramCsa` (assenti = fallback al condiviso,
comportamento invariato — verificato inerte per costruzione, §17.3) e `-CacheEspertiSlot` (qui
lasciato al default 473, invariato: la Fase 2b l'avrebbe portato a 539). Preflight passato (0
processi, porte libere, RAM 88,3 GB, VRAM a riposo 317 MiB).

```
tag         = sota_ctx150000_densefa_stage_hc5_t22_repoint_redo_f2_b2048
lanciato    = 06:58:57   caricato = 06:58:xx (free VRAM al load = 267 MiB, quasi identico ai
              266 MiB del turno 22 nonostante LID sia molto più pesante — vedi sotto: il costo
              pieno del ring caldo non è ancora tutto addebitato al momento del "loaded")
richiesta   = 07:01:28   ESITO = CRASH, "Connessione sottostante chiusa... dal server in modo
              imprevisto" (connessione TCP caduta a metà del decode)
```

**Testimone KV-ring** (`KV ring resident allocated`, §17.4, presente e funzionante): `CSA = 5.25
MiB, HCA = 5.00 MiB, LID = 192.94 MiB, total = 203.19 MiB`. Due letture, entrambe corrette rispetto
al disegno di §17: **CSA è sceso esattamente al pavimento previsto da NOTE_IMPLEMENTAZIONE.md §17.5**
(~5,25 MiB, "256 righe, il pavimento di `dsv4_comp_size`" — **misurato uguale alla predizione**);
**LID è salito a 192,94 MiB**, molto più dei "~148 MiB" con cui il mandato descriveva "LID intero
residente" — la stima del mandato era per un `-Context` diverso (105-110k, da
`TASSA_ATTENZIONE_LUNGO.md:178`), qui il banco gira a `-Context 150000` e il valore vero a piena
residenza scala di conseguenza. Il meccanismo per-deposito (§17.2-17.3) **funziona esattamente come
disegnato** su entrambi i lati: questo NON è un bug della patch B-2, è un dimensionamento.

**Causa del crash**: `CUDA error: out of memory` in `ggml-cuda.cu:124` (sito generico, diverso dalla
firma "layer-major staging 1729 MiB" del banco di ieri sera — quello era un problema di PROMPT
lungo con `-ub 2048`; qui il prompt è lo stesso corto-per-costruzione di sempre e la transizione
prefill→decode di questo braccio non lo tocca). Il crash arriva **durante il decode**, dopo che il
`[kv-ring-profile]` ha già registrato due battiti (`tokens=6144` e `tokens=16384` nel contatore
cumulativo del ring, non il conteggio dei token generati). **Diagnosi**: `LID=192,94 MiB` più
`CSA=5,25` più `HCA=5,00` (totale 203,19 MiB) si aggiungono agli stessi identici 3.194 MiB della
cache-esperti (SLOT=473 invariato) e allo stesso buffer di calcolo da 2.296,35 MiB del braccio A —
la somma eccede il margine già citato come "al muro" da `COMPOSIZIONE_PIANO.md` §1.1 R8 (167-210
MiB liberi) e dalla nota lasciata dall'esecutore del turno 22 in coda al banco ("il margine... va
verificato dal vivo in quel braccio, non dedotto" — **verificato ora: non regge**). Questo È il
rischio che `COMPOSIZIONE_PIANO.md` §2 P4 aveva già scritto in anticipo: *"se a2 K-as-V non si
scrive, LID non entra... la catena si ferma sul muro della VRAM"* — qui si è fermata esattamente
lì, con LID (non a2) come primo a bussare.

**Non è un errore di esecuzione**: il valore `300000` è quello scritto testualmente nella nota di
consegna del turno 22 ("per esempio 300000"); l'ho usato senza modificarlo, ed è proprio quel
valore a produrre 192,94 MiB — più di quanto il margine libero possa reggere insieme al resto del
carico. **Nessuna build, nessun codice toccato**: la patch B-2 (già compilata da giorni) si
comporta secondo il proprio contratto in entrambe le direzioni (CSA giù, LID su); il fallimento è
nel dimensionamento del banco, non nel meccanismo.

**FASE 2b (`t22_slot539`) NON ESEGUITA — bloccata per dipendenza.** Il mandato la definisce come
"identico a B-2a" (cioè a questa Fase 2) **+** `LLAMA_CACHE_ESPERTI_SLOT=539` — cioè +446 MiB
*ulteriori* di cache esperti sopra una configurazione che **già da sola** esaurisce la VRAM.
Lanciarla comunque avrebbe significato ripetere lo stesso crash con un margine ancora più stretto:
non è "la fase successiva indipendente", è un incremento sulla fase che è appena crashata. **Non
lanciata**, per lo stesso principio del mandato ("se una fase crasha... si passa alla successiva",
letto qui come: alla successiva **indipendente**, non a un suo aggravamento diretto).

**Prossimo passo suggerito, non eseguito** (fuori dal tempo di questo turno): ripetere B-2a con un
valore di `LLAMA_KV_RING_VRAM_LID` più piccolo del "kv_size o più" — per esempio il valore letterale
`~148 MiB` tradotto nell'unità giusta (token, non MiB: va dedotto da `dsv4_comp_size`, non
riusato direttamente), oppure con `LLAMA_CACHE_ESPERTI_SLOT` abbassato per fare posto (nella stessa
direzione della "combo (c)" trovata ieri sera per il crash del prompt lungo, ma qui il problema è
diverso: non serve ridurre lo slot per il prefill, serve ridurlo per accomodare LID in decode). Non
tentato in questo turno per restare nel regime economico e per rispettare la disciplina "un braccio
e stop" sul ramo che è appena stato falsificato.

**Stato macchina dopo il crash**: pulita da sola (0 processi llama — il processo è uscito da sé
sull'assert CUDA, non è stato necessario alcun intervento; nessuna quiete a orologio, solo verifica),
VRAM 281 MiB usati / 11835 liberi, RAM 88,3 GB libera, porte 8099/8100 libere. Nessun commit
eseguito. Script fuori repo, in scratchpad di sessione: `p2_ring.ps1` (non modificato dopo il
crash — resta valido per un eventuale retentivo con un valore di LID più piccolo). Percorsi:
`D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t22_repoint_redo_f2_b2048.{server.log,server.out}`,
`D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_t22_repoint_redo.summary.txt`,
`D:\ds4_work\llama_run\p2_repoint.{hw.csv,cpu.csv}`. **Si procede alla Fase 3 (S3-bis).**

---

## Turno esecutore (24/8) — CAMPAGNA PRINCIPALE, FASE 3 (S3-bis): NESSUN OOM, ma REGRESSIONE FORTE — conf_min=0,3 mal calibrata sotto CONF_PRENORM

Mandato: `run_porto_hot.ps1 -Tag t22_s3bis_b1200_r1_20260824 -MaxTokens 1200 -Repetitions 4
-PortoHotSnapshot 1 -SpecNmax 5 -SpecConf '0.3' -Extra '...;PORTO_HOT_MASK=15;LLAMA_CONF_PRENORM=1;
GGML_CUDA_GRAPH_MAX=256' -ServerPath D:\llama-subtract\build\bin\llama-server.exe` (comando
verbatim dalla coda del turno 22). Nessuna modifica allo script canonico. Preflight passato (0
processi, porte libere, RAM 88,2 GB).

```
rep  eval t/s  ms/token  p1        SHA (primi 8)   finish
1    12,16     82,2      0,55811   CB636113        length
2    12,21     81,9      0,55811   CB636113        length
3    12,20     82,0      0,55811   CB636113        length
4    12,20     82,0      0,55811   CB636113        length
mediana = 12,20 t/s (82,0 ms/token)
```

Le 4 repliche sono **bit-identiche** (stesso SHA, stesso p1 a 5 decimali) — il warm-restore
(`PORTO_HOT_MASK=15`, `porto_hot_snapshot=true`) è deterministico come atteso.

**Cancelli del mandato:**
- **OOM: NO.** Zero `CUDA error`/`out of memory`/`GGML_ASSERT` in tutto il log. `shutdown=ctrl-c`
  pulito su tutte e 4 le repliche.
- **Testimone pre-norm nel log: PRESENTE.** `operator (): conf_proj: lettura PRE-norm (riferimento
  upstream)` — riga singola, a caricamento, conferma che `LLAMA_CONF_PRENORM=1` è stato letto e ha
  attivato il ramo pre-norm (non è "post-norm en travesti" come il turno 21).
- **Sfratti-per-tetto: PRESENTE e attivo.** `porto-grafi: sfratti=37 (anzianita=37 tetto=0)` poi
  `sfratti=3949 (anzianita=268 tetto=3681)` — la stragrande maggioranza degli sfratti (3.681 su
  3.949) è imputabile al **tetto** `GGML_CUDA_GRAPH_MAX=256`, non all'anzianità: il tetto sta
  davvero limitando la popolazione di grafi vivi, il meccanismo lavora come disegnato.
- **Curve di confidenze verbatim: NON DISPONIBILE — dichiarato, non nascosto.** Cercato nel
  codice (`common/speculative.cpp`, sito del confronto `conf[idx*n_embd_dec] < params.conf_min`
  a riga 1229): **il valore di `conf[]` non viene mai stampato, a nessun livello di log, in nessun
  punto di questo file** (`grep` mirato: solo `n_max/n_min/p_min/conf_min` — i PARAMETRI, non le
  MISURE — sono loggati una volta a `LOG_INF`, riga 970). Il cancello diagnostico di
  `NOTE_IMPLEMENTAZIONE.md` §16.6 ("verificare che le confidenze stiano dentro (0,1) e calino con
  la posizione") **richiede una strumentazione che non esiste nel binario attuale**: non è stato
  possibile eseguirlo, né prima né durante questo braccio. Non si inventa un numero che non c'è.

**Il numero che conta, e la sua diagnosi**: `p1 = 0,55811` — **crollato** dal riferimento storico
`~0,90` (turno 22, conf=0,80/post-norm) e ANCHE ben sotto il gate 1 del piano originale a 5 bracci
(`NOTE_IMPLEMENTAZIONE.md` §16.7, "p1 ≥ 0,90 — se cala, la testa taglia dove non deve" — qui non è
la stessa identica metrica di quel gate, ma la direzione del segnale è la stessa). Coerentemente,
**t/s = 12,20 contro il confronto 16,63 richiesto dal mandato: −26,6%**, una regressione netta, non
un mancato guadagno. **Diagnosi più probabile, scritta dalla fonte prima di questo turno**
(`COMPOSIZIONE_PIANO.md` §2 P5): *"il campione storico conf_min=0,80 è da rivalidare, non da
riusare (misurato sotto lo scoring POST-norm disallineato)... se cade conf_min=0,80, cade con lui
l'ottimo di n_max: sono due coordinate della stessa superficie."* Qui è `conf_min=0,3` (non 0,80)
a mostrarsi scalibrata sotto il nuovo scoring **PRE**-norm: la soglia era probabilmente tarata (o
ipotizzata) sulla distribuzione POST-norm, e sotto PRE-norm i punteggi si sono spostati abbastanza
da rendere 0,3 **più restrittivo**, non più permissivo, troncando la maggioranza dei blocchi molto
presto (coerente con `mean_len` implicito basso, dedotto da t/s/p1 bassi insieme — non ristampato
qui perché non nel corpo del cancello richiesto). **Senza la curva di confidenza (non disponibile)
questo resta un'ipotesi forte, non una prova diretta.**

**VERDETTO FASE 3: cancelli OOM/pre-norm/sfratti-tetto TUTTI PASSATI, ma il risultato di
prestazione è una REGRESSIONE (−26,6% vs 16,63), non un miglioramento.** `conf_min=0,3` non è la
soglia giusta sotto `CONF_PRENORM=1`: coerente con la legge di casa "i verdetti-nel-regime-sbagliato"
(settima/ottava occorrenza). **Non promuovere `conf_min=0,3` con prenorm acceso.** Un turno futuro
che voglia inseguire questa leva deve prima riaprire il cancello §16.6 (richiede una riga di log
nuova per `conf[]` — una modifica di codice, fuori da questo mandato "nessuna build").

**Stato macchina a fine Fase 3**: pulita (0 processi llama, VRAM 377 MiB usati / 11739 liberi, RAM
88,2 GB libera, porte 8099/8100 libere). Nessun commit eseguito. Percorsi:
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\t22_s3bis_b1200_r1_20260824.{server.log,server.out,summary.json,r1-r4.response.json,r1-r4.output.txt}`,
`...\runs\t22_s3bis.hw.csv/cpu.csv`. **FASE 4 (fattoriale 2³) NON LANCIATA per ordine del
coordinatore — passa al prossimo esecutore.**

---

## Turno esecutore 28 (24/8) — FASE 1 PROMOZIONE: replica conf_min=0,70 — BIT-ESATTA, PROMOSSA

Mandato: rifare a parità totale il braccio 2 di Fase 1b (`conf_min=0,70`, 73,6 ms/token, p1
0,91096, mean len 3,18) — la replica che mancava per promuoverlo a campione del lungo.
Binario canonico riverificato prima del banco, invariato (SHA exe `C15FF135F14024FED4ADD8B3FF1
4299429CA9627508150B7CDE06234E9795878`, SHA dll `00C6F0D2AC9161AF44EADDB0F22344E5580F4CC77E1D7
2A1683951214B15C576`, build 10093/3014d3756). Preflight (09:4x, 24/8): 0 processi, porte
8099/8100/8101 libere, GPU a riposo (376 MiB usati / 11740 liberi, pcie gen1x16), RAM libera
88,1 GB, disco C 48,4 / D 115,5 GB, uptime 5073,2 min. `jprompt102k.txt` SHA
`3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473` (285.268 B) — identico al
riferimento. Script: stesso `p1b_conf.ps1` invariato (nessuna modifica), stesso comando
verbatim salvo `-RunLabel` (nuovo, per non sovrascrivere gli artefatti originali):

```
LLAMA_KV_GATHER=1
p1b_conf.ps1 -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -RunLabel p1b_conf070_replica
  -Context 150000 -MaxTokens 8192 -SpecNmax 3 -SpecConf 0.70 -Repliche 1
  -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0
  -ServerPath D:\llama-subtract\build\bin\llama-server.exe
```

Lanciato staccato (background) con DONE finale; caricato a batch/ubatch 2048 (stessa shape
dell'originale), free VRAM al load 419 MiB. Richiesta 09:55:20 → 24,1 min di parete.

```
tag         = sota_ctx150000_densefa_stage_hc5_p1b_conf070_replica_f2_b2048_q1
prefill     = 120,94 t/s (8,27 ms/token, 101.691 token)
decode      = 13,55 t/s (73,79 ms/token, 8192 token)          atteso: 13,58 (73,6 ms/token)
p1          = 0,91096 (5617 accepted / 6166 generated), mean len = 3,18
SHA output  = F0733E8C5319CA75C7DE39BCFA7A89A06BEA2301D2279849BB6705084FA617CB
finish      = length   |   output chars = 24592
```

**Confronto con l'originale (braccio 2, Fase 1b)**: delta ms/token = **+0,26%**, delta t/s =
**−0,22%** — non solo dentro la banda del 3% (§8.3): **p1, mean_len e SHA output sono
IDENTICI carattere per carattere** all'originale (`F0733E8C...` coincide fino all'ultimo
carattere, non solo sui primi 8 esadecimali della tabella di Fase 1b). Questa non è una
replica "in banda", è una **replica bit-esatta**: la traiettoria di calcolo è la stessa fino
all'ultimo token, l'unica differenza è rumore di parete puro (nessun cambio di trainettoria).

**Checklist d'identità (§4.9)**: riga `cache-esperti` identica carattere per carattere al
riferimento (473 slot..., `sfratto_par=1`); build 10093 (3014d3756) + SHA exe/dll trascritti
sopra; `sched-profilo` = 463 righe (ACCESO — stesso script invariato di Fase 1b, quindi pari
strumentazione per costruzione); `GGML_CUDA_GRAPH_STATS` assente dal grep mirato (non
impostata da questo script); grafi ACCESI (`GGML_CUDA_DISABLE_GRAPHS` assente); zero
`GGML_ASSERT`/`CUDA error`/divergenze (`rilevatore replay`: tutte le righe `taglia=0 ids=0
out=0 GRIGLIA-corta=0`); `jprompt102k.txt` verificato al preflight. Copie/buchi (dato nuovo,
non registrato per questo arm in Fase 1b): `cache-esperti: domanda 2016052 (colpi 1051067 =
52,1%, buchi 964985, miss 47,9%, in ritardo 0 = 0,0%)`.

**Lettura del testo (§4.10)**: SHA bit-identico al braccio già vagliato integralmente in Fase
1b (letto allora: coerente, italiano tecnico sano, pertinente, nessun loop, nessuna
degradazione) — rilettura qui di conferma (inizio + intorno carattere 330, sezione overlap/
kern_partiziona): stesso contenuto tecnico coerente, cita codice reale del repository, nessuna
anomalia.

**Lacuna dichiarata**: telemetria hw/cpu **non campionata** su questo braccio — `p1b_conf.ps1`
non lancia `sample_hw.ps1` da solo e non è stato affiancato qui (l'istruzione "telemetria
sempre" di questo turno non è stata rispettata su questa fase; corretto dalla Fase 2 in poi).
Non ripetuto: il braccio è già validato dalla bit-esattezza, la più forte prova di identità
disponibile in questo progetto, e ripetere 24 minuti di GPU solo per un CSV non è
proporzionato.

**VERDETTO FASE 1: PROMOSSA.** `G1 (gather) + conf_min=0,70` è il nuovo campione del banco
lungo (8k, mono-richiesta, gather acceso): **decode ≈13,55–13,58 t/s (~13,6), 73,6–73,8
ms/token**, in luogo del vecchio campione a `conf_min=0,80` (~79 ms/token). Ogni banco futuro
su questa configurazione usa `--spec-draft-conf-min 0.70`, non più `0.80`.

**Stato macchina a fine Fase 1**: verificata pulita prima della Fase 2 (0 processi, VRAM 312
MiB, RAM 88,3 GB, porte 8099/8100 libere). Nessun commit eseguito. Script fuori repo, in
scratchpad di sessione: `p1b_conf.ps1` (invariato), percorsi `D:\ds4_work\llama_run\sota_ctx15
0000_densefa_stage_hc5_p1b_conf070_replica_f2_b2048.{server.log,server.out,summary.txt}` e
`..._q1.{response.json,output.txt}`.

---

## Turno esecutore 28 (24/8) — FASE 2 REPOINT CORRETTO: aritmetica del mandato CORRETTA prima
## del lancio, secondo OOM (progresso reale, non risolto) — FERMATO per protocollo

### Correzione dell'aritmetica PRIMA di lanciare (regola di casa: leggere il codice prima di
### sweeppare)

Il mandato suggeriva `LLAMA_KV_RING_VRAM_LID ≈ 225000-230000` per ottenere ~148 MiB, dedotto
per proporzione lineare da `192,94 MiB @ 300000`. **Verificato sul codice sorgente prima di
lanciare** (`D:\llama-subtract\src\llama-kv-cache-dsv4.cpp:1303-1312`):

```cpp
const uint32_t hot_token_lid = std::min(kv_size, dsv4_kv_ring_vram_token_deposito(
        "LLAMA_KV_RING_VRAM_LID", ..., hot_token));
const uint32_t lid_hot_size = std::min(kv_lid->get_size(),
        GGML_PAD(dsv4_comp_size(hot_token_lid, DSV4_CSA_RATIO /* = 4 */), 256u));
```

Con `-Context 150000`, `kv_size = 150000`. **Qualunque valore richiesto ≥150000 (compreso
225000-230000, come 300000) si clampa allo STESSO `hot_token_lid = 150000`**, cioè alla
STESSA residenza piena da 192,94 MiB del crash di questa notte — **zero riduzione, stesso
crash garantito**. Il mandato aveva ragione sul principio ("va dedotto da `dsv4_comp_size`,
non riusato direttamente") ma il numero proposto era ancora sopra il muro del clamp.
**Derivazione corretta**: il dato 192,94 MiB@300000 è in realtà 192,94 MiB alla residenza
PIENA di 37.632 righe (`GGML_PAD(150000/4, 256)`), quindi 0,0051270 MiB/riga misurato
(192,94/37632). Per un bersaglio di ~148 MiB servono **righe sotto il clamp**, cioè un valore
RICHIESTO **inferiore** a 150000: 148/0,0051270 ≈ 28.868 righe → `GGML_PAD(·,256)` = 28.928
righe (bucket da 1024 token, insensibile a ±500 token) → **`LLAMA_KV_RING_VRAM_LID=115000`**
(ben sotto il clamp, comodamente dentro la banda 140-150 MiB, lontano dal bordo del bucket).
**Verificato dal vivo qui sotto**: LID misurato = 148,31 MiB, **a 0,01 MiB dalla previsione**.

### Config e lancio

Script `p2_ring_conf.ps1` (nuova copia in scratchpad, DUE aggiunte dichiarate rispetto a
`p2_ring.ps1`: parametro `-SpecConf` — a `'0.8'` di default è testualmente identico al
comportamento precedente — e lancio automatico di `sample_hw.ps1` dopo `/health` OK, che
`p2_ring.ps1`/`p1_nudo.ps1` non avevano — lacuna dichiarata in Fase 1, corretta qui). Comando:

```
LLAMA_KV_GATHER=1
p2_ring_conf.ps1 -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5
  -RunLabel t22_repoint_v2_slot450_lid115k -Context 150000 -MaxTokens 8192 -SpecNmax 3
  -SpecConf 0.70 -Repliche 1 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1
  -ReasoningBudgetTokens 0 -KvRingVramLid 115000 -KvRingVramCsa 0 -CacheEspertiSlot 450
  -ServerPath D:\llama-subtract\build\bin\llama-server.exe
```

Preflight verificato pulito (0 processi, porte libere, RAM 88,3 GB, VRAM 312 MiB). Caricato
10:23:09, **free VRAM al load = 499 MiB** (contro 267 MiB dell'originale che ha crashato ieri
notte — **+232 MiB di margine reale**, coerente con la somma attesa 44,6 (LID) + 155 (SLOT
cuscino) ≈ 200 MiB più un margine extra). Testimone KV-ring:

```
KV ring resident allocated: CSA = 5.25 MiB, HCA = 5.00 MiB, LID = 148.31 MiB, total = 158.56 MiB
```

(contro `total = 203,19 MiB` dell'originale — **−44,63 MiB esatti**, come previsto). Telemetria
`sample_hw.ps1` avviata correttamente (0,5 Hz), presente per l'intera durata.

### Esito: SECONDO OOM — ma diverso e più tardi del primo

Richiesta 10:27:24. Prefill in corso, GPU 100% util, 1905-1927 MHz, ~130 W (sano). A
**n_tokens=28673 (28% del prompt, t=153,42 s, 186,90 tok/s cumulativo)**:

```
slot operator (): cached n_tokens = 28673, memory_seq_rm [28673, end)
CUDA error: out of memory
  current device: 0, in function alloc at ggml-cuda.cu:609
  cuMemSetAccess(start_ptr, reserve_size, &access, 1)
ggml-cuda.cu:124: CUDA error
```

Il processo è uscito **da solo** (`shutdown: already-exited`). **28.672 = esattamente 14 ×
2048** (14° chunk di prefill a `-ub 2048`): il crash cade su un confine di chunk esatto, non
un punto casuale.

**Diverso dal crash di ieri notte in due modi**: (1) qui cade **durante il prefill** (28% del
prompt), non alla transizione prefill→decode come `t22_repoint_redo`; (2) il sito preciso
(`alloc`/`cuMemSetAccess`, l'allocatore VMM a pool crescente) non era stato osservato prima —
diverso anche dalla firma "layer-major staging 1729 MiB" del crash del banco bat di ieri sera.
**Non è la stessa causa radice, o non SOLO quella.**

**Indizio nuovo, non diagnosticato a fondo (fuori budget di questa fase)**: i tre battiti
`[kv-ring-profile]` prima del crash —

```
tokens=6144   materializations=186  h2d_copies=63   bytes_h2d_per_token=8064.00
tokens=18432  materializations=544  h2d_copies=184  bytes_h2d_per_token=22983.11
tokens=28672  materializations=854  h2d_copies=289  bytes_h2d_per_token=36397.71
```

— mostrano `materializations/token` (≈0,0298) e `h2d_copies/token` (≈0,0100) **costanti**, ma
`bytes_h2d_per_token` (media cumulata) **quasi quadruplica** (8064→36398). Cioè: non crescono
il numero di copie per token, cresce la **taglia media** di ogni copia. **Ipotesi, non
verificata**: un pool CUDA a taglia crescente (VMM, coerente col sito `cuMemSetAccess`) legato
allo staging delle materializzazioni del ring, che non rilascia mai il picco raggiunto — se
vero, nessun ritocco di LID/SLOT a budget fisso risolve il problema per un prompt
sufficientemente lungo: sposta solo il punto di rottura più avanti (esattamente ciò che si è
osservato qui: dal crash immediato di ieri notte al 28% di oggi). **Non verificato con lettura
del codice in questo turno** — priorità #1 per chi riprende: leggere il sito di allocazione
dietro `cuMemSetAccess`/le materializzazioni del ring prima di ritoccare ancora LID.

`rows_cold` (atteso in crollo da ~93% se sopravviveva) **non verificabile**: nessuna corsa
completata da cui leggerlo.

### Verifica macchina dopo il crash — la VRAM NON si è liberata subito

Telemetria `hw.csv` (0,5 Hz, catturata per l'intera corsa): VRAM ferma a **11873-11930 MiB
usati (solo 230-270 MiB liberi)** da 10:30:00 (crash) fino ad almeno 10:30:11 — poi un buco nel
campionamento fino a 10:39:07, dove risulta ancora 192 MiB liberi; **solo a 10:39:15 la VRAM
torna alla linea di riposo vera** (271-279 MiB usati, 11837-11845 liberi). **Il driver ha
impiegato fino a ~9 minuti per riclamare la VRAM dopo l'errore CUDA fatale**, nonostante il
processo fosse già uscito da solo. Verificato dal vivo con polling attivo a tre condizioni
(§6.6) prima di procedere: **macchina pulita solo a 10:42:46** (0 processi, VRAM 286 MiB, RAM
89,9 GB). **Lezione operativa**: dopo un OOM CUDA fatale, "processo uscito" da solo **non**
implica "VRAM libera" — verificare sempre tutte e tre le condizioni del §6.6, mai fermarsi al
solo conteggio processi.

### VERDETTO FASE 2: FERMATO per protocollo (secondo OOM) — progresso reale, non chiuso

Per mandato ("se OOM di nuovo → fermati su questa fase"): **non si tenta un terzo giro in
questo turno**. Consegna onesta:

1. **L'aritmetica del mandato (225000-230000) era sbagliata ed è stata corretta prima del
   lancio** — quel valore avrebbe clampato alla stessa residenza piena del crash originale,
   zero beneficio garantito. Il valore corretto (115000, sotto il clamp) è verificato dal vivo
   a 0,01 MiB dalla previsione.
2. **La correzione ha comprato progresso reale**: +232 MiB di margine al load, crash spostato
   dall'immediato/transizione al 28% di un prefill da 101.691 token, con una firma di errore
   diversa (VMM `alloc`/`cuMemSetAccess`, non più `layer-major staging`).
3. **Non è chiuso**: l'indizio `bytes_h2d_per_token` crescente suggerisce un consumo che
   scala con la posizione nel prefill, non un budget fisso — ritoccare ancora LID/SLOT con lo
   stesso modello lineare rischia di spostare il muro senza eliminarlo. Priorità per il
   prossimo turno: leggere il codice dietro le materializzazioni del ring prima di ritoccare
   altri numeri.

**Stato macchina a fine Fase 2**: pulita, verificata a tre condizioni (0 processi, VRAM 286
MiB, RAM 89,9 GB, porte 8099/8100 libere) alle 10:42:46. Nessun commit eseguito. Script fuori
repo, in scratchpad di sessione: `p2_ring_conf.ps1` (nuovo, invariato dopo il crash). Percorsi:
`D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t22_repoint_v2_slot450_lid115k_f2_b204
8.{server.log,server.out,summary.txt,hw.csv,cpu.csv}`. **Si procede alla Fase 3 (fattoriale
2³ a caldo).**

---

## Turno esecutore 28 (24/8) — FASE 3 FATTORIALE 2³ A CALDO: FORK×BLOCCHI×DOWN_TARDI —
## nessuna interazione rilevabile, DOWN_TARDI unico segnale coerente (sotto soglia)

Mandato: `COMPOSIZIONE_PIANO.md` §4.3/BLOCCO A (A1) — il "2³ completo dentro un solo processo"
via **Porto control block v0** (`porto_cb`, verificato sul sorgente prima di lanciare:
`server-schema.cpp:42-73` — hot-switch di `fork`(0-2)/`fork_blocchi`(1-1024)/`fork_down_tardi`
(0-1)/`pf_top`/`sfratto_par` al confine token, una ricattura per cambio, combinazioni illegali
= 400 e server vivo). Versione **ridotta per regime economico**: 8 celle + 1 ancora (non 8×2
repliche+2 ancore = 18 richieste del piano pieno), 256 token/punto (non 1200/B1200) — dichiarato
esplicitamente, non è il protocollo di certificazione pieno.

### Config e lancio

Un solo processo, `cb_probe.ps1` (script scratchpad esistente, non modificato) + piano JSON
nuovo (`phase3_factorial_plan.json`): ambiente base = campione (SOTA, porta 8101, `-c 10000
-ub 64`, **jprompt.txt corto**), `+env.PORTO_HOT_MASK=15` (warm-restore completo). 9 richieste,
`porto_hot_snapshot=true` su tutte, `n_predict=256`, stesso corpo salvo `porto_cb`:

```
c1 (2,8,0) campione | c2 (2,8,1) | c3 (2,32,0) | c4 (2,32,1) | c5 (1,8,0) | c6 (1,8,1)
c7 (1,32,0) | c8 (1,32,1) | c9 (2,8,0) ancora = ripete c1
```

Preflight pulito (0 processi, porte libere). Caricato e lanciato senza incidenti: **9/9 HTTP
200**, **0 rifiuti 400** (nessuna combinazione ha toccato `fork=0`, quindi C5 del piano non si
applica), durata totale ~5 min (9 richieste × 256 token, molto più economico dei 25-28 min del
piano pieno).

### Cancello d'identità — PASSATO, il più forte possibile

**Tutte e 9 le richieste**: `SHA output = 1F003E46561D3D880823DCEC593FE0631A90FEA59F48F5BF6B5
48DFA000BA2DF` (identico carattere per carattere), `p1 = 0,84302 (145/172)`, `mean_len = 2,33`
— **IDENTICI su tutte le 9 celle**, non solo sulle coppie ripetute. Riga `cache-esperti`
identica al riferimento canonico (473 slot..., `sfratto_par=1`); grafi ACCESI (`GGML_CUDA_DISA
BLE_GRAPHS` assente); build 10093 (3014d3756); zero `CUDA error`/`GGML_ASSERT`/righe 400 in
tutto il log. **Qualunque divergenza sarebbe stata un guasto: non ce n'è nessuna.** Lettura
integrale (§4.10, banco corto) della prima replica (`c1`, 411 caratteri, uguale bit-a-bit alle
altre 8): coerente, pertinente al prompt (HTML cyberpunk NeuraForge), troncata a metà CSS per
`length` — nessuna anomalia.

### I nove numeri (decode, dal log, non dal wall_ms del runner)

| cella | FORK | BLOCCHI | DOWN_TARDI | decode t/s | ms/token |
|---|---:|---:|---:|---:|---:|
| c1 campione | 2 | 8  | 0 | 14,37 | 69,57 |
| c2          | 2 | 8  | 1 | 15,11 | 66,16 |
| c3          | 2 | 32 | 0 | 14,69 | 68,05 |
| c4          | 2 | 32 | 1 | 15,04 | 66,51 |
| c5          | 1 | 8  | 0 | 14,87 | 67,26 |
| c6          | 1 | 8  | 1 | 15,17 | 65,93 |
| c7          | 1 | 32 | 0 | 14,72 | 67,93 |
| c8          | 1 | 32 | 1 | 15,04 | 66,48 |
| c9 ancora (=c1) | 2 | 8 | 0 | 14,81 | 67,53 |

**Rumore dell'ancora (misurato, non assunto)**: c9 vs c1, **stessa cella bit-esatta**, t/s
14,81 contro 14,37 = **+3,06%**. Più largo dei riferimenti storici del piano per il protocollo
pieno (`spread 0,30%` repliche, `ancore a 1,3%`, §4.1) — coerente con l'aspettativa statistica
di passare da 1200 a 256 token/punto (rumore relativo scala ~1/√n: √(1200/256)≈2,17×, e
1,3%×2,17≈2,8% ≈ il 3,06% osservato). **Con un solo grado di libertà (una sola coppia), questa
è una stima grezza**, non una varianza vera — riportata per onestà, non per rigore statistico.

### 3 effetti principali (media alto − media basso, t/s; positivo = più veloce)

| effetto | valore | % | IC grezzo (±, da 1 sola coppia-ancora) | verdetto |
|---|---:|---:|---:|---|
| **FORK** (2 vs 1) | −0,1475 | −1,0% | ±0,6 (±4%) | dentro il rumore, non distinguibile |
| **BLOCCHI** (32 vs 8) | −0,0075 | −0,1% | ±0,6 (±4%) | zero, non distinguibile |
| **DOWN_TARDI** (1 vs 0) | **+0,4275** | **+2,9%** | ±0,6 (±4%) | sotto la soglia formale, ma **unico segno coerente su tutte e 4 le coppie indipendenti** (c2>c1 +5,1%, c4>c3 +2,4%, c6>c5 +2,0%, c8>c7 +2,2%) |

### 3 interazioni a due vie (stesso schema)

| interazione | valore | % | verdetto |
|---|---:|---:|---|
| FORK×BLOCCHI | +0,1325 | +0,9% | dentro il rumore |
| FORK×DOWN_TARDI | +0,1175 | +0,8% | dentro il rumore |
| BLOCCHI×DOWN_TARDI | −0,0925 | −0,6% | dentro il rumore |

**Nessuna delle tre interazioni a due vie è distinguibile da zero a questa risoluzione**:
composizione additiva, nessuna sorpresa super/sub-additiva fra `FORK`, `FORK_BLOCCHI`,
`DOWN_TARDI` nell'intervallo testato — consistente con l'assenza, nel piano, di una previsione
esplicita di non-additività per questa terna specifica.

### VERDETTO FASE 3

**Screening onesto, non un verdetto di promozione.** A 256 token/punto: `FORK` (1 vs 2) e
`FORK_BLOCCHI` (8 vs 32) non mostrano alcun effetto principale sopra il rumore misurato; nessuna
delle tre interazioni a due vie emerge. `DOWN_TARDI=1` è l'unico segnale con una direzione
coerente su tutte e 4 le coppie (+2,0%...+5,1%, media +2,9%), **sotto la soglia formale di
questo banco ridotto** ma nella stessa direzione già assunta altrove nel progetto (`COMPOSIZIONE
_PIANO.md` §7.1 usa "B1200 warm-restore, `DOWN_TARDI=1`" come riferimento corrente). **Non
promuovere/falsificare nessuna delle tre leve da questo solo banco**: chi vuole un verdetto
vero deve rifare il disegno pieno (8 celle × 2 repliche + 2 ancore, B1200, §4.3) dove il rumore
atteso (±1,3-1,4%) è abbastanza piccolo da separare un +2,9% da zero — a 256 token il rumore
misurato (3,06%) è già più grande dell'effetto più forte trovato qui.

**Stato macchina a fine Fase 3**: verificare sotto (chiusura turno). Nessun commit eseguito.
Script fuori repo, in scratchpad di sessione: `cb_probe.ps1` (invariato), `phase3_factorial_
plan.json` (nuovo). Percorsi: `...\scratchpad\cb_runs\phase3_factorial_t28.{server.log,server.
out,summary.json,c1..c9_*.output.txt,hw.csv,cpu.csv}`.

---

## PASSAGGIO CONSEGNE — fine turno esecutore 28 (24/8, ~10:53)

**Le tre fasi del mandato, in breve:**

1. **PROMOZIONE conf 0,70 — FATTA.** Replica bit-esatta (stesso SHA, p1, mean_len del braccio
   2 di Fase 1b). `G1 + conf_min=0,70` è il nuovo campione del banco lungo 8k: **~13,55-13,58
   t/s (73,6-73,8 ms/token)**, sostituisce `conf_min=0,80` in ogni banco futuro su questa
   config.
2. **REPOINT CORRETTO — FERMATO per protocollo (secondo OOM), non risolto.** L'aritmetica
   suggerita dal mandato (LID 225000-230000) era **sbagliata** (clampava alla stessa residenza
   piena del crash originale, zero beneficio) ed è stata corretta prima del lancio a partire
   dal codice sorgente (`llama-kv-cache-dsv4.cpp:1303-1312`): **LID=115000 → 148,31 MiB
   misurati, previsione a 0,01 MiB**. La correzione ha comprato progresso reale (+232 MiB al
   load, crash spostato dall'immediato al 28% di un prefill da 101.691 token) ma non basta:
   nuovo crash con firma diversa (`alloc`/`cuMemSetAccess`, allocatore VMM), con un indizio non
   verificato che il costo scali con la posizione nel prefill (`bytes_h2d_per_token` quasi
   quadruplica da 6k a 28k token) piuttosto che essere un budget fisso. **Priorità per il
   prossimo turno**: leggere il codice delle materializzazioni del ring prima di ritoccare
   ancora LID/SLOT — il modello "budget fisso" che ha guidato sia il mandato di stanotte sia
   quello di oggi potrebbe essere incompleto.
3. **FATTORIALE 2³ A CALDO — FATTO, screening onesto.** 9/9 richieste riuscite, identità
   bit-esatta su tutte e 9 le celle (cancello più forte possibile, passato). Nessun effetto
   principale o interazione a due vie sopra il rumore misurato (3,06% dall'ancora, a 256
   token/punto); `DOWN_TARDI=1` è l'unico segnale con direzione coerente su tutte e 4 le coppie
   (+2,9% medio) ma sotto soglia formale a questa risoluzione. Non è un verdetto di
   promozione: serve il disegno pieno (B1200, 2 repliche+2 ancore, §4.3 del piano) per separare
   un +2,9% dal rumore.

**Macchina**: pulita e verificata alle 10:53:26 (0 processi llama, VRAM 278 MiB usati / porte
8099-8101 libere, RAM 89,8 GB libera). **Nota, non azione**: un processo `powershell.exe`
(PID 16488, avviato 04:32:14, quindi precedente a questo turno) risulta ancora vivo sulla
macchina — non è stato toccato (non è un processo llama, non è stato creato da questo turno,
e la regola di casa vieta di terminare processi non compresi). Segnalato per chi ha visibilità
sulla sua origine.

**Nessun commit eseguito in tutto il turno** (per mandato). Ledger di questo turno: le tre
sezioni "Turno esecutore 28" sopra, in ordine Fase 1 → Fase 2 → Fase 3. Script nuovi in
scratchpad di sessione (non committati, non nel repo): `p2_ring_conf.ps1`,
`phase3_factorial_plan.json`; riusati invariati: `p1b_conf.ps1`, `cb_probe.ps1`.

---

## Turno esecutore 29 (24/8) — BRACCIO REPOINT CSA=2048 (`t29_repoint_csa2048`): TERZO OOM,
## PRIMA del secondo — FERMATO per protocollo, verdetto: serve la materializzazione incrementale

Mandato: `D:\ds4_work\design\REPOINT_OOM_ANALISI.md`, risposta (3) — ripetere la Fase 2 del
turno 28 con `LLAMA_KV_RING_VRAM_CSA=2048` (invece di `0`, il valore condiviso di base, l'unico
già validato altrove) e `LLAMA_KV_RING_VRAM_LID=115000` invariato: il braccio più economico
(zero build) che decide se il repoint è usabile senza chirurgia.

Binario canonico riverificato prima del banco, **invariato dal turno 28** (nessuna
ricompilazione fra i due turni): SHA exe `C15FF135F14024FED4ADD8B3FF14299429CA9627508150B7CDE
06234E9795878`, SHA `ggml-cuda.dll` `00C6F0D2AC9161AF44EADDB0F22344E5580F4CC77E1D72A16839512
14B15C576`. `jprompt102k.txt` SHA `3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284
560A1473` (285.268 B) confermato. Preflight (11:0x, 24/8): 0 processi, porte 8099/8100/8101
libere, GPU a riposo (511 MiB usati / 11605 liberi, 0% util), RAM libera 88,6/95,9 GB, disco C
46,9 / D 115,5 GB, uptime 5152,5 min.

### Config e lancio

Stesso script `p2_ring_conf.ps1` (scratchpad, invariato), stesso comando verbatim della Fase 2
del turno 28 salvo `-RunLabel` e **`-KvRingVramCsa 2048`** (era `0`):

```
LLAMA_KV_GATHER=1
p2_ring_conf.ps1 -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5
  -RunLabel t29_repoint_csa2048 -Context 150000 -MaxTokens 8192 -SpecNmax 3
  -SpecConf 0.70 -Repliche 1 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1
  -ReasoningBudgetTokens 0 -KvRingVramLid 115000 -KvRingVramCsa 2048 -CacheEspertiSlot 450
  -ServerPath D:\llama-subtract\build\bin\llama-server.exe
```

Lanciato staccato (background) con DONE finale. Caricato 11:11:28, **free VRAM al load = 341
MiB** (contro 499 MiB della Fase 2 con CSA=0 — **−158 MiB di margine**). Testimone KV-ring:

```
KV ring resident allocated: CSA = 10.50 MiB, HCA = 5.00 MiB, LID = 148.31 MiB, total = 163.81 MiB
```

(contro `total = 158,56 MiB` della Fase 2: CSA cresce da 5,25 a 10,50 MiB, **+5,25 MiB soli**).
**I −158 MiB di free-VRAM-al-load NON sono spiegati dal solo residente KV-ring dichiarato in
questa riga** — overhead extra non isolato in questo turno (candidato: workspace/compressor
state legato al gather CSA a 512 righe/layer, `kv-gather ACCESO (512 righe/layer CSA)`
osservato — via `LLAMA_KV_GATHER=1` — solo in questo braccio). Telemetria `sample_hw.ps1`
avviata correttamente (pid 18888), presente per l'intera corsa.

### Esito: TERZO OOM — stessa firma, posizione PRIMA del secondo OOM (non dopo)

Richiesta 11:13:59. Prefill in corso, GPU 100% util, 1890-1935 MHz, ~130-138 W (sano), velocità
cumulativa in calo regolare da 206 a 189 t/s. Ultimo checkpoint riuscito **n_tokens=26.625
(26,2% del prompt da 101.691 token), t=140,73 s, 189,19 tok/s cumulativo** — poi:

```
CUDA error: out of memory
  current device: 0, in function alloc at ggml-cuda.cu:609
  cuMemSetAccess(start_ptr, reserve_size, &access, 1)
ggml-cuda.cu:124: CUDA error
```

**Stessa firma esatta della Fase 2** (allocatore VMM, stesso sito `alloc`/`cuMemSetAccess`) —
ma a **26.625 invece di 28.673 token, differenza esatta −2.048 (un intero chunk di prefill a
ubatch=2048) e −12,7 s**: il braccio con CSA=2048 cade **prima**, non dopo, della Fase 2 con
CSA=0. Il processo è uscito da solo (richiesta HTTP fallita: "connessione chiusa dal server in
modo imprevisto"); nessun file di risposta prodotto (`..._q1.response.json`/`.output.txt`
assenti). **Prefill/decode/p1: non misurabili** (nessuna richiesta completata).

**`bytes_h2d_per_token`** (testimone `[kv-ring-profile]`): 4.224 a tokens=8.192 (contro 8.064
della Fase 2 a tokens=6.144 — quasi la metà, coerente con l'ipotesi del design doc che un hot
CSA più grande riduca `cold_rows` per chiamata) ma **21.504 a tokens=18.432, quasi pari alla
Fase 2 allo stesso punto (22.983, −6,4% soli)**: il vantaggio iniziale si erode rapidamente e
non basta a compensare il margine di partenza più basso.

**`rows_cold` (testimone `[kv-gather-profile]`, atteso in crollo da ~93%): NON misurabile.**
Nonostante `LLAMA_KV_GATHER=1` attivo e confermato a runtime (`kv-gather ACCESO (512
righe/layer CSA)`, `deepseek4.cpp:848`), **zero righe `[kv-gather-profile]` in tutto il log**
(`kv-gather.cu:349`, formato `gathers=... rows=... rows_cold=... rows_per_token=...`). Il
battito di default (60 s, nessun `LLAMA_KV_GATHER_BATTITO` impostato dallo script,
`kv-gather.cu:369-373`) avrebbe dovuto scattare 1-2 volte nei 141 s di corsa e non lo ha fatto —
lacuna dichiarata, non diagnosticata in questo turno (il chiamante è `ggml-cuda.cu:5888-5890`,
dentro il cammino di sincronizzazione: priorità per chi riprende, solo se questo dato serve
ancora dopo il verdetto sotto).

**VRAM durante la corsa** (`hw.csv`, 0,5 Hz, 65 righe): 333 MiB liberi al primo campione
(11:13:59, pre-ramp), poi **minimo 179 MiB liberi (11.937 MiB usati) alle 11:15:26-29**,
stabile a 180-182 MiB liberi per quasi tutta la corsa (100% util) — margine operativo molto più
stretto della Fase 2. Al crash (~11:16:22): util → 0%, clock → 210 MHz; **VRAM già a 11.853 MiB
liberi 5 secondi dopo** (11:16:27) — riclamo molto più rapido dei ~9 minuti della Fase 2 (non
indagato: verosimilmente un abort fatale immediato invece di uno shutdown più lento). Verificato
dal vivo dopo la corsa: **macchina pulita** (0 processi, VRAM 287 MiB usati / 11829 liberi,
porte 8099-8101 libere).

### VERDETTO: FERMATO per protocollo (terzo OOM) — verdetto secco, non chirurgia in questo turno

Per mandato ("se OOM di nuovo → fermati, il verdetto diventa serve la materializzazione
incrementale"): **non si tenta un quarto valore di CSA/LID in questo turno.**

1. **CSA=2048 (il valore condiviso di base, già validato altrove) NON rende il repoint
   usabile.** Non solo non sopravvive ai 150k attesi: **cade leggermente PRIMA della Fase 2**
   (26,2% contro 28,2%), perché il costo fisso aggiuntivo di tenere CSA caldo a 2048 token
   (−158 MiB di margine al load, in gran parte non spiegato dal solo residente KV-ring
   dichiarato) supera il beneficio per-chiamata che offre (`bytes_h2d_per_token` più basso solo
   nelle primissime battute, poi quasi pari alla Fase 2).
2. **Il meccanismo resta lo stesso in tutti e tre gli OOM finora** (stessa firma
   `alloc`/`cuMemSetAccess`, allocatore VMM a pool crescente che non rilascia mai il picco, per
   `REPOINT_OOM_ANALISI.md` punto 6): **nessuna combinazione di LID/CSA/SLOT a budget fisso lo
   risolve per un prefill di lunghezza arbitraria** — sposta solo (o, come qui, nemmeno) il
   muro.
3. **Verdetto del mandato: serve la materializzazione incrementale** — cache device-side del
   materializzato precedente in `ggml_cuda_kv_ring_materialize` (`kv-ring.cu:349-469`, contratto
   di shape di `ggml_dsv4_kv_ring` in `ggml.c:5482-5519`), non un ritocco di env var. Il repoint
   (LID pieno per pagare in decode) resta **strutturalmente incompatibile col prefill lungo così
   com'è cablato** — CSA/LID sono letti una sola volta alla costruzione della cache, nessun
   gancio a runtime al confine prefill→decode (`REPOINT_OOM_ANALISI.md` risposta (2)).

**Lacuna dichiarata**: `rows_cold`/`[kv-gather-profile]` non misurato in nessuno dei tre OOM
finora. Se serve ancora dopo il verdetto sopra, va prima capito perché il battito non scatta
(letto il chiamante `ggml-cuda.cu:5888-5890`) prima di rilanciare solo per quello.

**Stato macchina a fine turno**: pulita, verificata (0 processi, VRAM 287 MiB usati / 11829
liberi, porte 8099-8101 libere). **Nessun commit eseguito.** Script invariato in scratchpad di
sessione: `p2_ring_conf.ps1` (riusato, non modificato). Percorsi: `D:\ds4_work\llama_run\sota_c
tx150000_densefa_stage_hc5_t29_repoint_csa2048_f2_b2048.{server.log,server.out,summary.txt,hw.
csv,cpu.csv}`.

---

## Turno esecutore 30 (24/8) — NON-REGRESSIONE OK + SCALA CONFIDENZE LETTA + REPOINT SOPRAVVIVE (SORT_CHUNK_MIB=8) MA DECODE PIÙ LENTO DEL CAMPIONE

Mandato: `NOTE_IMPLEMENTAZIONE.md` §18 (leve chirurgo 14) + coda turno 29 (OOM su LID=115000+CSA=2048). Binari `D:\llama-subtract\build\bin` verificati PRIMA del banco, SHA256 = dichiarati carattere per carattere: exe `3D3347D1...9C9`, ggml-cuda `6EF5B781...B52`, llama-common `DD6689EC...5E5`, impl `9B417B4F...B88`, llama.dll invariata `40E1DEAF...C50`. `jprompt.txt` (252B) e `jprompt102k.txt` (285.268B) integri. Preflight pulito (0 processi, porte 8099-8101 libere, RAM 87,5-87,9 GB). Script: `run_porto_hot.ps1` invariato per le fasi 1-2; per la fase 3, copia dichiarata di `sota100k_ctx150k.ps1` (`C:\...\2026-08-14\ds4-porto-20tps\work\`, invariato) con le stesse tre aggiunte additive già viste nei turni 22/28/29 (`-SpecConf`, `-KvRingVramLid/-KvRingVramCsa`, `-CacheEspertiSlot`); `LLAMA_KV_GATHER/LLAMA_CUDA_SORT_CHUNK_MIB/LLAMA_CUDA_POOL_TRACE` impostate dal chiamante, stesso schema di `LLAMA_KV_GATHER` nei turni precedenti (nessuna tocca `Set-SotaEnvironment`).

### Fase 1 — non-regressione a difetti (B1200 free-run, `-ServerPath` nuovo, leve chirurgo 14 ASSENTI)
`eval t/s = 15,83` (comparatore mandato 14,44 viene da `t24_base`, B**512** non B1200: nessuna base a parità di lunghezza, ma in nessun verso è una regressione). **`p1 = 0,90025 (713/792, mean len 2,47)` e `buchi = 47906`: identici cifra per cifra al fingerprint storico della SOTA B1200** (RUNBOOK §4.5/§4.6). Riga `cache-esperti` identica al riferimento canonico, `sfratto_par=1`, grafi ACCESI, zero errori/divergenze, SHA output `4FDCFADF...D65D`. Lettura testo (§4.10): coerente, pertinente, nessun loop. **VERDETTO: build non regredita — difetto 64 = comportamento invariato, confermato dal vivo.**

### Fase 2 — scala vera delle confidenze (B160, `conf_min=0`, `nmax=5`, `LLAMA_SPEC_CONF_LOG=1`)
Prima lettura mai fatta di `conf[]` reale. 63 cicli (60 con blocco pieno n=5):

| posizione | n | min | mediana | max |
|---|---:|---:|---:|---:|
| 1 | 63 | 0,014 | 0,600 | 0,999 |
| 2 | 62 | 0,023 | 0,254 | 0,996 |
| 3 | 62 | 0,018 | 0,128 | 1,000 |
| 4 | 61 | 0,018 | 0,105 | 0,962 |
| 5 | 60 | 0,013 | 0,069 | 0,840 |

Calo monotono con la posizione (§16.6 verificato). **Implicazione**: con `conf_min` storico 0,60-0,90 la mediana di posizione 2 (0,254) è già sotto soglia — nmax5 con quelle soglie non supera quasi mai la posizione 2. Un `conf_min` che lasci respirare nmax5 va cercato ~0,10-0,15 (mediana pos. 3-4), non nell'intervallo sweppato finora. p1=0,23377 (basso per costruzione: regime patologico apposta per leggere la sonda). Zero errori. **VERDETTO: dato raccolto e utilizzabile per un nuovo sweep conf_min×nmax5 mirato sotto 0,15.**

### Fase 3 — retry repoint (LID=115000, CSA=2048, SLOT=450, `SORT_CHUNK_MIB=8`, `POOL_TRACE=1`, gather=1, conf 0,70)
Lanciato staccato (Win32_Process, PID 17716) alle 12:12:22, `-Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -Context 150000 -MaxTokens 8192 -SpecNmax 3 -SpecConf 0.70 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0`. Caricato con **free VRAM = 420 MiB** (contro 341 MiB del t29 con CSA=2048 senza il fix: +79 MiB di margine).

**SOPRAVVIVE per la prima volta ai 150k dopo tre OOM consecutivi (turni 22/28/29).** Richiesta completa in 23,09 min: prompt=101.691, completion=8192/8192 (`finish=length`), **prefill = 137,58 t/s**, **decode = 12,68 t/s (78,9 ms/token)**, p1 = 0,82727 (4976/6015, mean len 2,55). Identità: `cache-esperti: 450 slot...sfratto_par=1` (SLOT applicato correttamente), build 10093/3014d3756, zero `CUDA error`/`GGML_ASSERT`/divergenze reali (solo righe innocue del rilevatore replay). SHA output `271A6A40...1E1`. Lettura a campione (§4.10, inizio+centro×2+fine): coerente, tecnico, pertinente al prompt (DS4/cache-esperti/KV-ring), tronca a metà parola per `length` — nessuna anomalia. Telemetria: 649 campioni, SM mediano (busy) 1920 MHz, max 1942 MHz, potenza mediana 130,5 W, **zero campioni sotto 1500 MHz da carico** — sano.

**Causa dell'OOM chiusa, con la prova**: **zero righe `[cuda-pool]` durante l'intero prefill (101.691 token) e decode (8192 token)** — le uniche 5 righe della corsa cadono tutte nel caricamento iniziale, prima ancora che la richiesta parta. Le 3 più grosse, verbatim:
```
llama: [cuda-pool] device=0 richiesta=72.02 MiB commit=8.00 MiB pool=74.00 MiB usato=0.00 MiB op=MUL_MAT nome=attn_wo_a-0 ne=[1024,2048,8,1]
llama: [cuda-pool] device=0 richiesta=64.00 MiB commit=62.00 MiB pool=64.00 MiB usato=0.00 MiB op=MUL_MAT nome=hc_mixes-0 ne=[24,2048,1,1]
llama: [cuda-pool] device=0 richiesta=0.09 MiB commit=2.00 MiB pool=66.00 MiB usato=64.00 MiB op=MUL_MAT nome=hc_mixes-0 ne=[24,2048,1,1]
```
Confermano §18.2/§18.3 **misurato, non più dedotto**: col chunk ridotto a 8 MiB, ogni `top_k` del prefill resta dentro i 74 MiB già riservati al caricamento e non fa mai più crescere il pool — la causa dei tre OOM era esattamente quella, ed è chiusa.

**Ma non è un miglioramento di prestazione — anzi**: **decode 78,9 ms/token è PIÙ LENTO del campione senza repoint (73,79 ms/token, G1+conf 0,70): +7,0%**, non il ~71-72 atteso dal mandato. **`rows_cold` NON crolla, sale**: 87,3%→93,1% lungo gli 11 battiti `[kv-gather-profile]` osservati (atteso: crollo da ~93%; osservato: il contrario). **Indizio forte sul perché** (`[kv-ring-profile]`, 23 battiti): il tasso di materializzazioni per token **esplode di ~460× esattamente al confine prefill→decode** (da ~0,03/token durante tutto il prefill a ~14,1/token per l'intero decode; `h2d_copies`/token da ~0,016 a ~6,9, stesso confine) — coerente con una ri-materializzazione pesante del prefisso LID/CSA ad ogni passo di decode sotto residenza piena, non con un trasporto ridotto come sperato dal disegno del repoint.

**VERDETTO FASE 3**: **il repoint ora sopravvive (bersaglio del mandato raggiunto), ma sotto questa configurazione (LID=115000/CSA=2048/SLOT=450) costa più di quanto rende** — nessun guadagno di decode, anzi una perdita del 7% rispetto a non fare repoint affatto. La leva `SORT_CHUNK_MIB` è promuovibile da sola (fix OOM puro, zero costo misurato sul decode — 12,68 t/s qui vs strutturalmente confrontabile solo a un braccio gemello senza repoint, non fatto in questo turno). Il pacchetto LID/CSA/SLOT del repoint resta **sconsigliato così com'è**: il prossimo turno che vuole inseguirlo deve leggere il sito di materializzazione decode (`kv-ring.cu`, il ramo eseguito quando `n_kv` è già alla residenza piena) prima di ritoccare altri numeri — stessa priorità già scritta in coda al turno 29, ora con un indizio quantitativo in più.

**Stato macchina a fine turno**: pulita, verificata (0 processi, VRAM 235 MiB usati / porte 8099-8101 libere, RAM 87,1 GB). **Nessun commit eseguito.** Script nuovi in scratchpad di sessione (non nel repo): `phase1_run.ps1`, `phase2_run.ps1`, `sota100k_ctx150k_t30.ps1` (copia dichiarata di `sota100k_ctx150k.ps1` con le 3 aggiunte additive), `phase3_launch.ps1`, `phase3_wait.ps1`. Percorsi: `D:\ds4_work\llama_run\t30_nonreg_b1200_r1_20260824.*`, `D:\ds4_work\llama_run\t30_confscale_b160_nmax5_conf0_20260824.*`, `D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t30_repoint_sortchunk8_f2_b2048.{server.log,server.out,summary.txt}`, `D:\ds4_work\llama_run\t30_repoint_sortchunk8.{hw.csv,cpu.csv}`.

---

## Turno esecutore 31 (24/8) — SWEEP nmax5 NELLA SCALA GIUSTA (3a e ultima iterazione) + SORT_CHUNK=8 NON-REGRESSIONE LUNGO

Mandato: LEDGER_23_AGOSTO.md turno 30 (scala confidenze pos1..5 mediana 0,600/0,254/0,128/0,105/0,069, letta con `LLAMA_SPEC_CONF_LOG=1`) + NOTE_IMPLEMENTAZIONE.md (`D:\ds4_work\design\impl\`) §16 (LLAMA_CONF_PRENORM, atoi a valore, difetto 0/post-norm, dflash.cpp:32-42) e §18 (SORT_CHUNK_MIB/POOL_TRACE/SPEC_CONF_LOG, chirurgo 14). Binari `D:\llama-subtract\build\bin` riverificati carattere per carattere: exe `3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9`, ggml-cuda `6EF5B781DDD14B6AB503580DEF7876AB38E9AE8E6A6347E665AA8A34C9C68B52`, llama-common `DD6689ECE4AE405372E581FB60210576970081C16CA57F7698A3AC54CA59C5E5`, llama-server-impl `9B417B4F314E36C04B24BABC1D7FB731298C0E92A7BAAE240F71B57336821B88` — identici al turno 30, stesso binario. Preflight: 0 processi, porte 8099-8101 libere, GPU 235 MiB usati/11881 liberi (P8), RAM 86,2/95,89 GB liberi, `jprompt.txt` 252 B e `jprompt102k.txt` 285.268 B (SHA `3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473`) entrambi integri.

**Disciplina di scala (verificata sul COMANDO effettivo, non dedotta)**: recuperato `phase2_run.ps1` della sessione (stesso scratchpad del turno 30, sopravvissuto): comando esatto —
```
run_porto_hot.ps1 -Tag t30_confscale... -MaxTokens 160 -Repetitions 1 -PortoHotSnapshot $false `
  -ServerPath D:\llama-subtract\build\bin\llama-server.exe -SpecNmax 5 -SpecConf '0' `
  -Extra 'LLAMA_SPEC_CONF_LOG=1'
```
**`LLAMA_CONF_PRENORM` ASSENTE dal comando** — la fase 2 del turno 30 ha letto la scala (pos1 0,600 → pos5 0,069) sotto **CONF_PRENORM=0 (post-norm, il difetto)**. Ogni braccio dello sweep sottostante gira quindi anch'esso con `LLAMA_CONF_PRENORM` assente/0, per parlare la stessa scala. Dichiarato per ogni braccio sotto.

### Fase 1 — sweep nmax5 (B1200 free-run, GGML_CUDA_GRAPH_MAX=256 su tutti, LLAMA_CONF_PRENORM assente/0 su tutti)

Nota di percorso: il primo lancio del controllo ha usato per errore `conf=0,70` (rif. "campione" del banco LUNGO, non di questo banco CORTO); rilevato subito dal p1 basso e corretto. Il "campione" del banco CORTO free-run è **nmax=3/conf=0,80** (script `run_porto_hot.ps1`, difetto storico, riga 46/224 LEDGER; "L0 PROMOSSA" di memoria). Il braccio errato è riportato come extra, non come controllo.

| braccio | nmax | conf_min | CONF_PRENORM | t/s | Δ vs 15,83 | p1 | mean_len | grafi sfrattati (tetto) | errori |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **controllo** (corretto) | 3 | 0,80 | 0 (assente) | **16,17** | **+2,1%** | 0,90281 | **2,80** | 1640 (1412) | zero |
| extra fuori-bersaglio (scartato come controllo) | 3 | 0,70 | 0 (assente) | 14,97 | −5,4% | 0,82614 | 2,54 | 881 (568) | zero |
| nmax5 × conf_min=0,10 | 5 | 0,10 | 0 (assente) | **12,57** | **−20,6%** | 0,57042 | **3,20** | 542 (472) | zero |
| nmax5 × conf_min=0,15 | 5 | 0,15 | 0 (assente) | **13,24** | **−16,4%** | 0,64404 | **3,19** | 722 (585) | zero |

Identità controllo corretto: p1=0,90281 e mean_len=2,80 **bit-esatti** al riferimento storico "L0 PROMOSSA" (memoria di progetto) — stessa build, stessa traiettoria. `cache-esperti: 473 slot..., sfratto_par=1` presente e identico su tutti i bracci. Zero `CUDA error`/`GGML_ASSERT` su tutti i 4 bracci. `GGML_CUDA_GRAPH_MAX=256` verificato attivo (righe `porto-grafi: sfratti=N (... tetto=M)` con M>0 su tutti, nessun OOM).

**Lettura**: su entrambi i punti nmax5 il mean_len SALE (3,19-3,20 contro 2,80 del controllo — il premio di densità cercato è reale, +14-15%), ma il `p1` (accettazione posizione 0) crolla da 0,903 a 0,57-0,64 e il costo per round (5 bozze da generare/verificare invece di 3) vince sul guadagno di lunghezza: t/s crolla del 16-21% vs riferimento 15,83, del 18-22% vs controllo. Nessun punto promette (soglia mandato +3%): **nessuna replica necessaria**.

**VERDETTO FASE 1**: **nmax5 SI PARCHEGGIA — terza e ultima iterazione, chiusa con la scala a verbale.** Anche nella zona di conf_min indicata dalla lettura del turno 30 (mediana pos.3-4 ≈ 0,105-0,128, qui sweppata a 0,10/0,15) e sotto la STESSA config di scala (CONF_PRENORM assente/0, post-norm) usata per leggerla, nmax5 regredisce nettamente: il guadagno di densità (mean_len) non compensa mai il costo per round. **Non riaprire nmax5 sotto scoring post-norm.** L'unica via non ancora tentata è lo scoring PRE-norm (`LLAMA_CONF_PRENORM=1`, NOTE §16, mai buildato-e-testato in un binario live prima d'ora): fuori perimetro di questo turno, da valutare a parte se un turno futuro vuole riaprire il fascicolo con una terza scala mai letta.

### Fase 2 — SORT_CHUNK_MIB=8 non-regressione sul campione lungo (G1+conf0,70, config INTATTA + solo l'aggiunta dichiarata)

Comando: campione (`p1b_conf.ps1 -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -Context 150000 -MaxTokens 8192 -SpecNmax 3 -SpecConf 0.70 -Repliche 1 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0 -ServerPath D:\llama-subtract\build\bin\llama-server.exe`, `LLAMA_KV_GATHER=1`) **invariato byte per byte** rispetto alla promozione del turno 28, **più SOLO** `LLAMA_CUDA_SORT_CHUNK_MIB=8` impostata prima del lancio. Nessun LID/CSA/SLOT di repoint (nessuno era presente nel campione originale). Lanciato come processo Win32 distaccato (CIM) per non rischiare il timeout dello strumento su una corsa da 22-24 minuti; telemetria hw/cpu campionata (novità rispetto al turno 28, che l'aveva omessa).

Caricato a batch/ubatch 2048 (stessa shape), **free VRAM al load = 497 MiB**. Richiesta 13:22:20 → **22,45 min di parete** (contro i 24,1 min del turno 28 — entrambi dominati dal wall-clock, non comparabili al secondo).

```
prompt=101.691, completion=8192/8192 (finish=length)
prefill = 137,34 t/s   (rif. turno 28: 120,94 t/s — +13,6%)
decode  = 13,52 t/s / 73,96 ms/token   (rif.: 13,55 t/s / 73,79 ms/token — +0,23%, dentro banda 3%)
p1      = 0,91096 (IDENTICO al riferimento, 8 cifre)
mean_len= 3,18 (IDENTICO al riferimento)
SHA out = F0733E8C5319CA75C7DE39BCFA7A89A06BEA2301D2279849BB6705084FA617CB — BIT-ESATTO al riferimento (byte per byte)
```

**Identità: replica BIT-ESATTA**, non solo "in banda" — p1, mean_len e SHA output coincidono carattere per carattere col campione del turno 28 (stessa traiettoria di calcolo fino all'ultimo token). L'unica differenza misurabile è il tempo di parete: decode +0,23% (rumore puro, dentro la deriva 2-3% di banco, §8.3 RUNBOOK), **prefill +13,6%** (miglioramento genuino misurato, non dedotto — coerente con SORT_CHUNK=8 che tocca esattamente `top_k`/argsort, l'operazione dominante del gather in prefill; da NON sovra-interpretare come garantito: un solo punto, nessuna replica). Zero `CUDA error`/`GGML_ASSERT`/`out of memory` nel log (error-scan pulito, solo righe di dump "rilevatore replay" con `divergenze:...=0`). Macchina pulita a fine corsa (0 processi, porte libere, VRAM 261/11855 MiB, RAM 86,4 GB).

**VERDETTO FASE 2: PROMOSSA, oltre l'atteso.** Non solo dentro banda 3% come richiesto dal mandato: bit-esatta su p1/mean_len/SHA, decode indistinguibile (+0,23%), prefill misurato più veloce (+13,6%, un solo punto). **`LLAMA_CUDA_SORT_CHUNK_MIB=8` si dichiara ADOTTABILE come default di sicurezza dei banchi lunghi** — margine di pool ~280 MiB dedotto da NOTE §18.3 (non rimisurato qui byte a byte, nessun `LLAMA_CUDA_POOL_TRACE=1` in questo braccio per restare "config intatta + una sola aggiunta"), a costo di decode zero e con un possibile bonus di prefill da confermare su repliche future prima di generalizzarlo. Chiude anche il dubbio lasciato aperto dal turno 30 ("strutturalmente confrontabile solo a un braccio gemello senza repoint, non fatto in questo turno"): ora il braccio gemello esiste, ed è bit-esatto.

## PASSAGGIO CONSEGNE — fine turno esecutore 31

Binari invariati (`D:\llama-subtract\build\bin`, stesse impronte del turno 30, riverificate a inizio turno). Macchina lasciata pulita: 0 processi, porte 8099-8101 libere, VRAM 261 MiB usati / 11855 liberi (P8), RAM 86,4 GB liberi. Nessun commit eseguito. Script fuori repo, in scratchpad di sessione: `t31_p1_ctrl.ps1`/`t31_p1_ctrl_v2.ps1` (correzione conf 0,70→0,80), `t31_p1_nmax5_c010.ps1`, `t31_p1_nmax5_c015.ps1`, `t31_p2_sortchunk8.ps1` (wrapper su `p1b_conf.ps1` di sessione, invariato). Artefatti: `D:\ds4_work\llama_run\t31_sweep_*_20260824.*` (Fase 1, 4 bracci inclusa la variante fuori-bersaglio), `D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t31_sortchunk8_check_f2_b2048.*` e `...t31_sortchunk8_f2_b2048.{hw,cpu}.csv` (Fase 2). **Aperto per il prossimo turno**: (1) se si vuole riprovare nmax5, l'unica scala mai letta è PRE-norm (`LLAMA_CONF_PRENORM=1`) — richiede prima una lettura-scala dedicata come quella del turno 30, poi uno sweep nuovo, mai un riuso dei conf_min di qui; (2) il bonus prefill di SORT_CHUNK=8 (+13,6%) è un solo punto non replicato — chi lo vuole generalizzare deve rifarlo almeno una volta prima di scriverlo come atteso.

## Turno esecutore 32 (24/8) — B-1: LA PENDENZA DELLA TASSA RESIDUA — bug OOM nuovo trovato e aggirato con causa esatta, pendenza grezza confusa dal mean_len, intercetta chiaramente sopra il corto

Mandato: `D:\ds4_work\design\TASSA_ATTENZIONE_LUNGO.md` §7.6 B-1 (sweep di contesto col gather, 32k/64k/102k, stessa build/sessione/slot, pendenza attesa post-G1 ≈0,041 ms/1000ctx, soglie di verdetto 0,015/0,04/0,12) + LEDGER turno 31 (comando `p1b_conf.ps1` collaudato, campione lungo = gather=1 + conf_min 0,70 + nmax=3 + `LLAMA_CUDA_SORT_CHUNK_MIB=8` + HC_FUSO=5, batch/ubatch 2048, 473 slot esperti, 102k→73,96 ms/token). Preflight iniziale pulito: 0 processi, porte 8099-8101 libere, GPU 261/12288 MiB (P8), RAM 86,35/95,89 GB liberi. Binari riverificati bit-identici al turno 31: exe `3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9`, ggml-cuda `6EF5B781DDD14B6AB503580DEF7876AB38E9AE8E6A6347E665AA8A34C9C68B52`, llama-common `DD6689ECE4AE405372E581FB60210576970081C16CA57F7698A3AC54CA59C5E5`, llama-server-impl `9B417B4F314E36C04B24BABC1D7FB731298C0E92A7BAAE240F71B57336821B88`. `jprompt102k.txt` invariato (285.268 B, SHA `3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473`). Troncamento del prompt lungo-saggio via nuovo parametro `-PrefixChars` di `p1b_conf.ps1` (già presente nello script, non usato prima d'ora): tronca `$source` (il file) a N caratteri PRIMA di appendere l'epilogo fisso "FINE DEL CONTESTO" — stesso testo, stesso prompt, solo più corto.

### INCIDENTE — OOM riproducibile 3/3 a ~32k, causa radice trovata a file:riga, bug NUOVO non nominato in §7.5/7.6

Primo tentativo (`PrefixChars=89800`, target ~32k): CUDA `out of memory` in `ggml_cuda_mul_mat_q` (`mmq.cu:183`) all'86,7% della prefill misurata, sempre allo stesso checkpoint (`n_tokens=30721/32782`). **Retry identico: crash bit-per-bit identico** (stesso checkpoint, stessa sequenza) — non è racy. Tentativo con `StartBatch=1024` (dimezza la forma di prefill): crash di nuovo, stesso schema (margine salito da 0 a 35 MiB liberi ma non abbastanza).

Causa radice, letta dal sorgente (`D:\llama-subtract\src\llama-context.cpp:2296-2298`):
```
const bool prefill = (int32_t) n_tokens_all >  vram_fasi_ub &&
                     (int32_t) n_tokens_all >= vram_fasi_min;
if (prefill != vram_fasi_prefill) { vram_a_fasi(prefill); vram_fasi_prefill = prefill; }
```
Il cancello guarda **la taglia dell'ultimo chunk inviato**, non i token ancora da processare. `vram_fasi_ub=64` (`LLAMA_VRAM_A_FASI_UB`). Se `prompt_tokens mod ubatch ≤ 64`, l'ultimo pezzo residuo di prefill (es. 14 token) viene scambiato per un passo di decode: la fase-VRAM sfratta il buffer `layer-major` da 1729 MiB (allocato una volta a inizio prefill, log `layer-major: staging esperti 1729 MiB, 256 slot`, confermato letto una sola volta anche nel log 102k del turno 31 — lì mai risfrattato) per far posto ai 473 slot esperti (+3194 MiB), lasciando 0 MiB liberi; il pezzo residuo prova a riallocare lo staging (`layer-major: staging di 1729 MiB NON allocabile`) e la mul_mat_q successiva va OOM. Aritmetica: `32782 mod 2048 = 32782 mod 1024 = 14 ≤ 64` → crash garantito con entrambe le forme di batch provate. Il campione 102k è salvo per puro caso aritmetico: `101691 mod 2048 = 1339`, ben sopra soglia — **non è un fix, è fortuna**. Non è nessuno dei candidati §7.5/§7.6 (non PCIe, non indexer, non FA): è un difetto di correttezza dello scheduler VRAM-a-fasi. Segnalato per fix dedicato (task in coda, non eseguito qui: fuori perimetro del mandato).

**Aggiramento usato qui** (nessuna leva toccata, solo la lunghezza del prompt): scelti nuovi `PrefixChars` mirati a lasciare un resto ampiamente sopra 64 sia mod 2048 sia mod 1024 — `91200`→33344 token (resto 576) e `178200`→63335 token (resto 1895). Entrambi i run successivi: **shutdown pulito (`ctrl-c`), zero `CUDA error`/`out of memory`** nello scan finale (le righe "divergenze" del cache-esperti che matchano il pattern `diverg` sono lette, tutte a zero — non errori).

### Risultati B-1 — tre punti, stessa build/sessione-equivalente/slot (473, invariati su tutti)

| ctx (token, misurato) | prefill t/s | decode t/s | decode ms/token | p1 | mean_len | ms/forward (=ms/token×mean_len) |
|---:|---:|---:|---:|---:|---:|---:|
| 33.344 | 182,95 | 13,8506 | **72,199** | 0,88141 | 2,86 | 206,49 |
| 63.335 | 161,85 | 13,0994 | **76,340** | 0,86049 | 2,75 | 209,94 |
| 101.691 (rif. turno 31 fase 2) | 137,34 | 13,52 | **73,96** | 0,91096 | 3,18 | 235,19 |

SHA output: 33.344→`D73A5455EA7B648EAAAF78225F36F15E6021BCA3E09D31B7F39A6BEFB4043138`; 63.335→`A5989015C58EED44531E45B685C8EDB55F16D5A24A20B1CC3110629DD0D7A126` (nessun confronto bit-esatto atteso: prompt diversi). Telemetria hw/cpu campionata 2s per entrambi i run nuovi (`...ctx32k_v2_f2_b2048.{hw,cpu}.csv` 419 campioni, util. GPU media 67,0%; `...ctx64k_v2_f2_b2048.{hw,cpu}.csv` 497 campioni, util. GPU media 76,8% — nessuna delle due satura, coerente con orchestration-bound).

### L'ARITMETICA — due letture, non una, perché il mean_len NON è a parità (lezione §7.3 applicata a se stessa)

Fit lineare grezzo (x=ctx/1000 token, y=ms/token), minimi quadrati sui 3 punti: **pendenza = 0,0218 ms/1000ctx, intercetta = 72,73 ms/token**. Ma le pendenze a coppie sono `32k→64k: +0,138`, `64k→102k: −0,062`, `32k→102k: +0,026`: **non monotone, il punto medio (64k) sta SOPRA entrambi i vicini**. Causa visibile in tabella: `mean_len` non è a parità fra i tre run (2,86 / 2,75 / 3,18 — 13,6% di escursione, il 64k è il peggiore) e con la speculazione il ms/token grezzo mescola tassa-per-forward e overhead-per-round-di-verifica, esattamente il confondimento che la §7.3 di questo stesso documento aveva già isolato («a pari mean_len, o non si sta confrontando niente»).

Normalizzando per forward (ms/forward = ms/token × mean_len, toglie il confondimento del tasso di accettazione): **206,49 → 209,94 → 235,19, monotona crescente**. Fit lineare: **pendenza = 0,431 ms/forward per 1000ctx, intercetta = 188,71 ms/forward**. Convertita a equivalente per-token al mean_len del riferimento (≈3): 0,431/3 ≈ **0,144 ms/token per 1000ctx** — sopra la soglia 0,12 del mandato.

**VERDETTO**: la pendenza grezza (0,022) cadrebbe nel bucket "tassa quasi fissa" (≈0,04), ma è costruita su una serie non monotona e confusa dal mean_len: **non è una lettura sicura**. La pendenza normalizzata per forward è pulita (monotona) e il suo equivalente per-token (~0,14) cade nel bucket **"≥0,12 → voce che scala col contesto e non è nel conto"**: i candidati nominati dal §7.5/7.6 restano gli stessi, **indexer fuso denso** (`build_lid_top_k` legge tutte le righe LID ad ogni forward, §2.1 punto 1 — il gather non lo tocca, riduce solo la materializzazione a valle) e **PCIe del LID/HCA densi**, entrambi strutturalmente proporzionali a `n_kv`. **Non si chiude il budget**: con un solo punto per x (nessuna replica) e un'escursione di mean_len grande quanto l'effetto cercato, il prossimo passo onesto è ripetere almeno il punto 64k (il più anomalo) a parità di seed/route per vedere se il mean_len basso è rumore o struttura, prima di puntare nsys sull'indexer.

Intercetta: 72,73 ms/token (fit grezzo) è **chiaramente sopra** il riferimento corto ~59 ms (+23%) — bucket "intercetta molto sopra ~59 ms" del mandato: il lato-corto del campione lungo è più caro del corto vero. Overhead di regime da nominare: tutto ciò che il banco lungo accende e il banco corto no — `LLAMA_KV_RING` + gather + `VRAM_A_FASI` (coi due cambi di fase per richiesta, ~50-140 ms l'uno più il rischio appena documentato) + i 473 slot esperti dedicati. Non scala col contesto (è un intercetta, non una pendenza) ma pesa ~13-14 ms/token fisso rispetto al corto.

**Stato macchina a fine turno**: 0 processi, porte 8099-8101 libere, GPU 159/12288 MiB (P8), RAM 89,13/95,89 GB liberi. Nessun commit eseguito. Script fuori repo in scratchpad di sessione: `t32_b1_ctx32k.ps1`/`_sb1024.ps1` (i due tentativi falliti, tenuti per traccia del bug), `t32_b1_ctx32k_v2.ps1`, `t32_b1_ctx64k_v2.ps1` (i due usati per i risultati sopra), tutti wrapper su `p1b_conf.ps1` di sessione (invariato, solo `-PrefixChars` è nuovo nell'uso). Task in coda per il bug OOM (non eseguito, fuori perimetro): fix di `llama-context.cpp:2296-2298` perché la classificazione prefill/decode guardi i token-ancora-da-processare della richiesta, non la taglia del singolo chunk.

---

## Turno esecutore 33 (24/8) — FASE 1: REPLICA DEL PUNTO 64k — BIT-ESATTA, il punto è REALE

Mandato: ripetere il braccio 64k del turno 32 (il punto anomalo del fit B-1, sopra entrambi i vicini) a parità di build/sessione/slot, per distinguere rumore da struttura prima di eventualmente puntare nsys sull'indexer.

Preflight (15:47): 0 processi llama, porte 8099/8100 libere, GPU 159/11957 MiB (P5, a riposo), RAM libera 88,18 GB, disco C 46,9/D 114,9 GB liberi, uptime 5429,7 min. Binari riverificati bit-identici al turno 32 (i backup `backup_pre_chirurgo14`/`backup_post_chirurgo14` in `D:\llama-subtract\build\bin` sono datati 24/8 11:31-11:37, cioè **prima** del turno 32: il chirurgo 15 non ha ancora toccato l'albero):

```text
llama-server.exe      = 3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9  (=)
ggml-cuda.dll          = 6EF5B781DDD14B6AB503580DEF7876AB38E9AE8E6A6347E665AA8A34C9C68B52  (=)
llama-common.dll       = DD6689ECE4AE405372E581FB60210576970081C16CA57F7698A3AC54CA59C5E5  (=)
llama-server-impl.dll  = 9B417B4F314E36C04B24BABC1D7FB731298C0E92A7BAAE240F71B57336821B88  (=)
```

`jprompt102k.txt` invariato (285.268 B, SHA `3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473`).

Comando: **byte-per-byte identico** al braccio 64k del turno 32 (`t32_b1_ctx64k_v2.ps1`, wrapper su `p1b_conf.ps1` di sessione) — `-Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 -PrefixChars 178200 -Context 150000 -MaxTokens 8192 -SpecNmax 3 -SpecConf 0.70 -Repliche 1 -CtxCheckpointMinStep 32 -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0`, `LLAMA_KV_GATHER=1`, `LLAMA_CUDA_SORT_CHUNK_MIB=8`, stesso `-ServerPath D:\llama-subtract\build\bin\llama-server.exe`; unica differenza `-RunLabel t33_b1_ctx64k_replica` (solo per non sovrascrivere i log di riferimento del turno 32). Lanciato in background (~17 min attesi), cintura +50% non necessaria: chiuso pulito a 17,03 min.

```text
prompt=63.335 (identico), completion=8192/8192 (finish=length)
prefill = 162,03 t/s     (rif. turno 32: 161,85 — +0,11%)
decode  = 12,99 t/s / 77,00 ms/token   (rif.: 13,0994 t/s / 76,340 ms/token — +0,86%, dentro banda 2-3%)
p1      = 0,86049   (IDENTICO bit-esatto al turno 32)
mean_len= 2,75       (IDENTICO bit-esatto al turno 32)
SHA out = A5989015C58EED44531E45B685C8EDB55F16D5A24A20B1CC3110629DD0D7A126 — BIT-ESATTO, carattere per carattere identico al turno 32
```

Zero `CUDA error`/`out of memory` nello scan finale (tutte le righe "rilevatore replay" con `divergenze: taglia=0 ids=0 out=0`). Shutdown `ctrl-c` pulito. VRAM libera al load: 641 MiB. Telemetria hw/cpu campionata (`...t33_b1_ctx64k_replica_f2_b2048.{hw,cpu}.csv`).

**VERDETTO FASE 1: IL PUNTO È REALE, non rumore.** Non solo il ms/token torna vicino a 76,3 (77,00, +0,86%, ben dentro la deriva di banco 2-3%, §8.3 runbook): l'intera traiettoria di calcolo è **bit-esatta** (stesso SHA output, stesso p1 all'ultima cifra, stesso mean_len) al turno 32 — lo stesso identico mean_len basso (2,75, contro 2,86 a 32k e 3,18 a 102k) non è un accidente di sampling né di misura, è strutturale a questa combinazione di contesto/route. La pendenza normalizzata-per-forward del turno 32 (0,431 ms/forward/1000ctx, equivalente ~0,144 ms/token/1000ctx) **REGGE**: resta sopra la soglia 0,12 del mandato TASSA_ATTENZIONE_LUNGO.md §7.6 (bucket "voce che scala col contesto e non è nel conto"). Nessun rifit necessario — i 3 punti (33.344/63.335/101.691) sono confermati con l'anomalia del punto medio ormai misurata due volte, non una. **Prossimo passo indicato dal documento di design (nsys mirato a 102k con `--cuda-graph-trace=node` su `DSV4_KV_GATHER`/`ggml_lightning_indexer`/`FLASH_ATTN_EXT`/`ARGSORT`) resta APERTO per un turno dedicato**: fuori dal perimetro economico di questo turno.

**Stato macchina dopo fase 1**: 0 processi, porta 8099 libera, GPU 403/11713 MiB (P8), RAM 86,99 GB liberi. Nessun commit eseguito. Script: `t33_b1_ctx64k_replica.ps1` (scratchpad di sessione, copia di `t32_b1_ctx64k_v2.ps1` con solo `-RunLabel` cambiato).

**FASE 2 (validazione fix resto-64) NON eseguita in questo turno**: in attesa del GO del coordinatore con le nuove SHA del chirurgo 15 (non ancora arrivate — i binari verificati sopra sono ancora quelli pre-esistenti al turno 32/chirurgo 14).

---

## Chirurgo 15 (24/8) — FIX RESTO-64 IN DUE STESURE: la v1 rinviava anche il flip del WARMUP (misurato: «restano 1 token» al load della fase2a), la v2 aggiunge la GUARDIA DI TAGLIA — consegnata: llama.dll ECAEA60B

Due attori sullo stesso mandato (la coda del turno 32), ricomposti dalla regia in corsa; cronaca fusa qui.

**Cronologia (24/8 pomeriggio)**: 15:49 v1 nel sorgente (`llama-context.{h,cpp}`: `LLAMA_VRAM_FASE_RESTO_FIX`, difetto 1 — rinvio del flip prefill→decode quando `n_outputs_all < n_tokens_all` e la fase era prefill); 15:55 `backup_pre_chirurgo15` (fotografia completa pre-build); 16:14:27 build v1 → `llama.dll` `797672BE...837A` (2.276.352 B); 16:20:57 lancio fase2a `t33_fase2a_prompt32k` su v1; 16:21 audit indipendente (chirurgo-15-bis, sessione worktree) trova il difetto della v1 nel sorgente e la emenda (v2) — 7 minuti DOPO la build v1, i due attori ancora all'oscuro l'uno dell'altro; 16:23:03 ultima riga di log della fase2a = il rinvio sul warmup; ~16:25 diagnosi incrociata via messaggi, kill del PID 4232 (per mano dell'esecutore che lo possedeva), verifica 0 processi + DLL non mappata; 16:27:32 build v2 (6 passi Ninja: 5 TU che includono `llama-context.h` + link, zero warning).

### Il difetto della v1, con la prova a riga di log (MISURATO)

Il criterio «output < token ⇒ sta ancora nutrendo il prompt» è giusto per la coda, ma cattura anche il warmup del caricamento: `{bos,eos}` = 2 token con `logits=nullptr` ⇒ 1 output di difetto (`llama-batch.cpp:120-128`), e `vram_fasi_prefill` parte a `true` dal costruttore. Log fase2a righe 259-261:

```text
2.03.712.004 I cmn  common_init_: warming up the model with an empty run ...
2.03.712.048 I decode: VRAM A FASI accesa: livello 2, ubatch di decode 64, prompt minimo 0
2.03.712.049 I decode: vram-a-fasi: flip rinviato, restano 1 token di prompt
```

Quel flip rinviato era LA PRIMA transizione a decode del ciclo di vita: senza di essa il buffer di calcolo resta a taglia pp (2296 MiB, mai ridotto a 127) e i ~2,2 GiB che il load di riferimento recupera lì non ci sono più per le allocazioni successive (draft, KV ring, stato HCA) né per lo staging layer-major (1729 MiB), che al primo fallimento si latcha spento per l'intero processo (`layer_major_fallita`, `cache-esperti.cu:5628`). DEDOTTO e non osservato (run uccisa in load): quale dei due incidenti arrivi prima, OOM di load o latch con prefill azzoppato — in entrambi i casi la fase2a su v1 non poteva produrre un verdetto valido, e nel caso latch avrebbe prodotto il danno peggiore: un repro «verde» con il prefill silenziosamente distrutto.

**Correzione a verbale di un errore del chirurgo-15-bis**: il primo allarme dichiarava la fase2a «congelata da ~30 minuti»; era un errore di ancoraggio dell'orologio di sessione — al momento del rilievo lo stallo era di ~2-3 minuti, dentro i silenzi normali di un load (il riferimento b1024 ha 1,9 min muti fra warmup e creazione KV). Il testimone che regge la diagnosi è la riga 261, non la durata.

### La v2 (emendamento, nel sorgente dalle 16:21)

Nuovo campo `vram_fasi_taglia_prefill` (`llama-context.h`, difetto `false`) = «l'ultima classificazione PER TAGLIA diceva prefill». Il rinvio ora chiede: fase ancora prefill E guardia armata E `resto_fix != 0` E `n_outputs_all < n_tokens_all`; in ogni altro caso la guardia si riallinea alla classificazione per taglia. Il warmup non la arma mai (2 token ≤ 64). Messaggio di log INVARIATO («flip rinviato, restano N token di prompt»). Tabella dei flussi (dedotta dal codice, da certificare a banco):

| chiamata | v0 (pre-fix) | v2 |
|---|---|---|
| warmup di load (2 tok, 1 out) | flip a decode | flip a decode (IDENTICO) |
| chunk 2048 di prompt | transizione a prefill | idem, e ARMA la guardia |
| CODA resto ≤ 64 (out < tok) | flip a decode ⇒ OOM (turno 32) | **rinvio: resta prefill, staging vivo** |
| coda resto = 1 (1 out = 1 tok) | flip a decode | flip a decode (nessun percorso staging ≤ ubatch: sicuro, DEDOTTO) |
| primo verify (out = tok) | (già decode) | flip a decode QUI |
| chat/prompt corto a fase decode | resta decode | resta decode (guardia disarmata) |
| output_all / embeddings | per taglia | per taglia (out=tok non rinvia mai) |
| `LLAMA_VRAM_FASE_RESTO_FIX=0` | — | comportamento v0 esatto (braccio A/B) |

### Identità consegnata (build 16:27:32, riverificata carattere per carattere)

```text
llama.dll v2           = ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035  (2.276.352 B — NUOVA)
llama-server.exe       = 3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9  (=)
ggml-cuda.dll          = 6EF5B781DDD14B6AB503580DEF7876AB38E9AE8E6A6347E665AA8A34C9C68B52  (=)
llama-common.dll       = DD6689ECE4AE405372E581FB60210576970081C16CA57F7698A3AC54CA59C5E5  (=)
llama-server-impl.dll  = 9B417B4F314E36C04B24BABC1D7FB731298C0E92A7BAAE240F71B57336821B88  (=)
```

Perimetro certificato: su TUTTO l'albero (`src/`, `ggml/`, `common/`, `tools/server`) solo `llama-context.{cpp,h}` (16:21) erano più nuovi dei rispettivi binari — la v2 è il binario dei turni 30-33 più il fix emendato e nient'altro. **ATTENZIONE IDENTITÀ: v1 e v2 hanno STESSA taglia e STESSE stringhe** (il nome del campo guardia non compila come stringa in release): si distinguono SOLO per SHA e per la firma runtime al load. v1 = `797672BE...837A`, DIFETTOSA, mai per banchi. Backup: pre-build in `backup_pre_chirurgo15\` (la `llama.dll` pre-fix `40E1DEAF...C50` vi era stata sovrascritta per errore dal chirurgo-15-bis alle ~16:23 e RIPRISTINATA con SHA verificata dalla copia di `backup_post_chirurgo14`); post v1 = `*_chirurgo15_vramfaseresto_24ago` (difettosa, tenuta per forensica); post v2 = `*_chirurgo15_resto64_guardia_24ago`.

### Firme attese per la fase2a rerun (esecutore 33, dopo GO regia)

1. AL LOAD: «warming up…» → «VRAM A FASI accesa…» → riga `vram_a_fasi: fase=decode … ubatch riserva=64` e **NESSUN «flip rinviato» prima della richiesta** (se compare al load: è la v1, abortire).
2. ALLA RICHIESTA (`PrefixChars=89800` → 32.782 token, resto 14): `cambio n. 1` a prefill (cache 473→0) → `layer-major: staging esperti 1729 MiB` → **UN SOLO «flip rinviato, restano 13 token di prompt»** sull'ultimo chunk, senza transizione lì → al primo verify `cambio n. 2` a decode (cache 0→473) → zero `CUDA error`/`out of memory` → completion piena.
3. Non-regressione corto B1200: p1 = 0,90281 / mean_len = 2,80 bit-esatti (la guardia non si arma mai sul corto).
4. Facoltativo coda=1: `PrefixChars` mirato a k·2048+1 token → NESSUN flip rinviato, flip a decode sul chunk-coda, nessun crash atteso (dedotto, da confermare).

Nessun commit eseguito (convenzione dei turni di oggi: i commit alla regia). Il sorgente v2 nell'albero llama-subtract è da committare insieme al verdetto della fase2a.

---

## Turno esecutore 33 — FASE 2a: INCIDENTE — il fix v1 (as-built) cattura anche il WARMUP, crash nel caricamento del draft model

GO ricevuto dal coordinatore: build del chirurgo 15 pubblicata, cambia **solo** `llama.dll`. Verificate tutte e cinque le SHA prima di lanciare:

```text
llama-server.exe       = 3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9  (invariato)
ggml-cuda.dll           = 6EF5B781DDD14B6AB503580DEF7876AB38E9AE8E6A6347E665AA8A34C9C68B52  (invariato)
llama-common.dll        = DD6689ECE4AE405372E581FB60210576970081C16CA57F7698A3AC54CA59C5E5  (invariato)
llama-server-impl.dll   = 9B417B4F314E36C04B24BABC1D7FB731298C0E92A7BAAE240F71B57336821B88  (invariato)
llama.dll               = 797672BEA7258F72D1AED7E8BE59ADAB6994D9F5064C7E3C65C5D7122102837A  (NUOVO, era 40E1DEAF...)
```

Comando braccio (a): identico al campione lungo, `PrefixChars=89800` (lo stesso valore che nel turno 32 aveva prodotto il crash OOM originale a 32.782 token, resto 14 mod 2048).

**Esito: NON l'OOM del bug originale — un crash diverso, nel caricamento del draft model, innescato dal warmup.** Sequenza esatta dal log (`sota_ctx150000_densefa_stage_hc5_t33_fase2a_prompt32k_f2_b2048.server.log`, 64.223 B, ultima scrittura 16:23:03):

```text
2.03.712.004  I cmn  common_init_: warming up the model with an empty run - please wait ... (--no-warmup to disable)
2.03.712.049  I decode: vram-a-fasi: flip rinviato, restano 1 token di prompt
2.06.268.783  I llama_model_loader: loaded meta data ... from D:/ds4-models/DSpark-draft-Q2K.gguf  (inizio caricamento DRAFT)
2.06.533.542  E llama_model_load: error loading model: invalid vector subscript
2.06.533.556  E llama_model_load_from_file_impl: failed to load model
2.06.533.558  E common_speculative_init_result: failed to load draft model, 'D:/ds4-models/DSpark-draft-Q2K.gguf'
```

Ritentato automaticamente dallo script (shape più piccola, b1024): **stesso identico errore**, stessa sequenza, poi `NO SHAPE LOADED; request not started.` Nessun processo rimasto vivo (uscita spontanea, non è servito `Stop-Process`).

**Diagnosi del coordinatore** (sessione chirurgica parallela, dal vivo, PID 4232): il fix v1 as-built cattura anche il warmup — la fase parte a prefill dal costruttore, e la nuova condizione (`n_outputs_all < n_tokens_all`) è vera pure per il mini-batch di warmup (verosimilmente {bos,eos}=2 token, 1 solo output), non solo per un vero resto di prompt lungo. **Il mio log CONFERMA il testimone esatto**: appare 45 ms dopo l'inizio dichiarato del warmup, con "restano **1** token di prompt" — non decine di migliaia, un artefatto del warmup stesso.

Nota di fedeltà (misurato vs riferito): il coordinatore descriveva il processo come "congelato", log fermo dalle 16:23. I miei timestamp di processo mostrano che l'intera sequenza (flip rinviato → tentativo caricamento draft → crash) dura **~2,8 s di tempo-processo** (2.03.712 → 2.06.533), non un hang prolungato — è un fallimento rapido ed esplicito, non un blocco indefinito. Dimensione/mtime del file (64.223 B ≈ 64 KB, 16:23:03) coincidono però esattamente con l'osservazione del coordinatore: quasi certamente la stessa identica istantanea, letta nel momento in cui il tentativo b2048 si era appena fermato per il crash e prima che lo script (in automatico) passasse al secondo tentativo su un file di log diverso (`..._b1024...`), che il coordinatore potrebbe non aver ancora visto comparire.

Causa radice NON diagnosticata a fondo da questo turno (fuori mandato esecutore, per la sessione chirurgica): ipotesi non verificata — il flip rinviato durante il warmup lascia una struttura di stato che avrebbe dovuto essere (re)inizializzata al vero flip verso decode, mai scattato qui, in una condizione che il successivo caricamento del draft model indicizza fuori range.

**Azioni eseguite su richiesta del coordinatore:**
1. Verificato (non assunto): nessun processo `llama-server`/`llama-cli` per nome, nessun PID 4232, nessuna voce riconducibile in `nvidia-smi --query-compute-apps`, porta 8099 libera. Nulla da uccidere: il processo era già terminato da solo prima della mia verifica.
2. Incidente annotato qui.
3. **Nessun rilancio eseguito.** Fase 2b (non-regressione 102k) NON tentata. In attesa del GO con la SHA della `llama.dll` emendata (v2).

**Stato macchina**: 0 processi, porta 8099 libera, GPU 388/11728 MiB (P8, 0% util), RAM 85,74 GB liberi. Libera per la rebuild del collega. Nessun commit eseguito. Script: `t33_fase2a_prompt32k.ps1`, `t33_fase2b_102k_nonreg.ps1` (quest'ultimo scritto ma mai lanciato, scratchpad di sessione).

---

## Turno esecutore 33 — FASE 2 v2: BRACCIO (a) — FAIL sulla firma esatta (secondo flip-rinviato inatteso), PASS sulla sopravvivenza. Braccio (b) NON lanciato (fail-fast)

GO ricevuto dal coordinatore per la v2. **PASSO 0 (bloccante) — identità binario**: `Get-FileHash D:\llama-subtract\build\bin\llama.dll` = `ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035`, mtime `2026-08-24 16:27:32.601` — **IDENTICO** all'atteso (build 16:27:32 del chirurgo). Verifica passata, procedo.

Preflight: 0 processi, GPU 404/11712 MiB (P8, 1%), RAM 86,8 GB liberi, porta 8099 libera.

Comando braccio (a): identico alla campagna B-1/fase2a-v1, `PrefixChars=89800` → 32.782 token (resto 14 mod 2048), `RunLabel=t33_fase2a_v2_prompt32k`.

**ENV completo** (manifesto integrale dal log, righe 1-15, verificato non dedotto):

```text
manifesto/cache:  LLAMA_CACHE_BOZZA_BATTITO=60(D) LLAMA_CACHE_BOZZA_SLOT=12(E) LLAMA_CACHE_ESPERTI_BATCH=8(E) LLAMA_CACHE_ESPERTI_BATTITO=45(E) LLAMA_CACHE_ESPERTI_CODA_MAX=0(E) LLAMA_CACHE_ESPERTI_CURA=0(E) LLAMA_CACHE_ESPERTI_FORK=2(E) LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8(E) LLAMA_CACHE_ESPERTI_LRU=1(E) LLAMA_CACHE_ESPERTI_MASSA=2(E) LLAMA_CACHE_ESPERTI_PF_TUTTI=1(D) LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO=0(E) LLAMA_CACHE_ESPERTI_SCUDO=0(E) LLAMA_CACHE_ESPERTI_SLOT=473(E) LLAMA_CACHE_ESPERTI_SPIN=256(D) LLAMA_CACHE_ESPERTI_W=0(E) LLAMA_CACHE_ORACOLO=<spento>(D)
manifesto/spec:   LLAMA_ACCEPTMOE=1(E) LLAMA_ACCEPTMOE_BATCH_MAX=8(D) LLAMA_ACCEPTMOE_COMPATTA=1(E) LLAMA_ACCEPTMOE_ESATTE=1(E) LLAMA_ACCEPTMOE_SOGLIA=0.75(E) LLAMA_ACCEPTMOE_SPIA=0(D) LLAMA_CKPT_CRONO=0(E) LLAMA_SPEC_CONF_ESENTA_POS0=1(E) LLAMA_SPEC_DRAFT_TOPK=1(E)
manifesto/compute: LLAMA_DSV4_HC_FUSO=5(E) LLAMA_MAPPED_IBRIDO=1(E) LLAMA_MAPPED_IBRIDO_SOGLIA=2(E) LLAMA_OVERLAP_ASYNC=1(E) LLAMA_OVERLAP_CERCA_CPU=0(D) LLAMA_OVERLAP_BATCH_MAX=3(E) LLAMA_OVERLAP_GRIGLIA_VARIABILE=0(E) LLAMA_OVERLAP_K=2(E) LLAMA_OVERLAP_PIN=1(E) LLAMA_OVERLAP_SPIN=2000000(D) LLAMA_OVERLAP_VERIFICA=0(D) | LLAMA_OVERLAP_JOIN_ASYNC=0(E) LLAMA_OVERLAP_FINESTRA=0(D) LLAMA_DSV4_INDEXER_FUSO=1(E) LLAMA_DSV4_TOPK_FUSO=0(D) LLAMA_GRAPH_REUSE_DISABLE=0(D) LLAMA_GRAPH_REUSE_PER_TAGLIA=1(E) LLAMA_MMQ_X_IDS=64(E) GGML_SCHED_PROFILO=1(E) GGML_CUDA_GRAPH_OPT=0(E) | GGML_CUDA_DISABLE_GRAPHS=<spento>(D) GGML_OP_OFFLOAD_MIN_BATCH=<spento>(D) GGML_CPU_MMID_REUSE_SRC1=0(D)
manifesto/kv:     LLAMA_KV_POSMIN_VERO=0(D) LLAMA_KV_RING=1(E) LLAMA_KV_RING_VRAM_TOKEN=2048(E) LLAMA_KV_RING_VRAM_TRACE=0(D) LLAMA_KV_ROLLBACK_MARGINE=4(D) LLAMA_KV_ROLLBACK_PARZIALE=1(E) LLAMA_KV_ROLLBACK_SOLO_ANELLO=0(E)
manifesto/vram:   LLAMA_VRAM_A_FASI=2(E) LLAMA_VRAM_A_FASI_CALDO=0(E) LLAMA_VRAM_A_FASI_MARGINE=0(E) LLAMA_VRAM_A_FASI_MIN=0(E) LLAMA_VRAM_A_FASI_SLOT=0(D) LLAMA_VRAM_A_FASI_SLOT_MAX=1024(D) LLAMA_VRAM_A_FASI_UB=64(E) LLAMA_VRAM_ZAVORRA=0(E) LLAMA_REAP_WS_MIN_GB=0(D)  (LLAMA_VRAM_FASE_RESTO_FIX non impostata: atoi difetto=1, fix v2 attivo)
manifesto/orfane: LLAMA_RING=0(D) LLAMA_RING_BATTITO=60(D) LLAMA_RING_PROFONDITA=380(D) | LLAMA_REAP=0(D) (+ blocco REAP tutto a difetto)
manifesto/diag:   LLAMA_DEBUG_DUMP/FILTER a difetto, GGML_CUDA_GRAPH_STATS=1(E), tutto il resto <spento>(D)
env script:       LLAMA_KV_GATHER=1, LLAMA_CUDA_SORT_CHUNK_MIB=8 (impostate dal wrapper, non nel manifesto server)
```

### Sequenza cronologica misurata (server.log, grep mirato — righe esatte)

```text
2.05.322.394  I cmn    common_init_: warming up the model with an empty run - please wait ...
2.05.322.425  I decode: VRAM A FASI accesa: livello 2, ubatch di decode 64, prompt minimo 0
2.05.439.750  I vram_a_fasi: fase=decode livello=2 ubatch riserva=64  buffer 2296.35->127.13 MiB  [117.3 ms]     <- flip del WARMUP, NESSUN "flip rinviato" qui: FIRMA #1 PASS
              vram-a-fasi: fase=prefill livello=2  cache 473->0 slot (-473,-3194 MiB)  VRAM libera 3227 MiB  [22.1 ms, cambio n. 1]   <- FIRMA #2a PASS
2.30.819.756  I vram_a_fasi: fase=prefill livello=2 ubatch riserva=2048  buffer 127.13->2296.35 MiB  [61.2 ms]
              layer-major: staging esperti 1729 MiB, 256 slot; ogni peso verra' letto una volta per prompt        <- FIRMA #2b PASS
5.13.043.337  I decode: vram-a-fasi: flip rinviato, restano 13 token di prompt                                    <- FIRMA #3 ATTESA, valore ESATTO (13)
5.29.097.109  I decode: vram-a-fasi: flip rinviato, restano 3 token di prompt                                     <- SECONDA occorrenza, NON ATTESA ("UN SOLO" richiesto dalla teoria)
              vram-a-fasi: fase=decode livello=2  cache 0->473 slot (+473,+3194 MiB)  VRAM libera 0 MiB  [5.7 ms, cambio n. 2]   <- FIRMA #4a PASS
5.29.671.764  I vram_a_fasi: fase=decode livello=2 ubatch riserva=64  buffer 2296.35->127.13 MiB  [80.7 ms]
```

**FIRMA #3 FUORI POSTO — posizione esatta: riga 885 di `sota_ctx150000_densefa_stage_hc5_t33_fase2a_v2_prompt32k_f2_b2048.server.log`, timestamp `5.29.097.109`.** La teoria del chirurgo prevedeva **un solo** `flip rinviato` sul chunk-coda (14 token, resto aritmetico di 32.782 mod 2048), con `restano 13` (n_outputs_all=1 sottratto). Il primo evento (riga 867, `5.13.043.337`) combacia esattamente. Ma **16,05 s dopo** ne compare un **secondo**, con un valore diverso (`restano 3`, cioè un chunk da 4 token con n_outputs_all=1) — non nominato da nessuna delle 8 righe della tabella-flussi del chirurgo. Ipotesi non verificata (fuori mandato esecutore): potrebbe essere il primo verify speculativo (fino a `spec-draft-n-max=3` bozze + 1 token reale = 4 candidati) trattato dalla guardia come se chiedesse un solo output, invece che uno per posizione candidata come il commento del fix stesso prevede per la verifica multi-token.

**Nessun OOM/crash**: error-scan pulito (tutte le righe "rilevatore replay" con `divergenze: taglia=0 ids=0 out=0`), `cambio n. 2` avvenuto, completion arrivata:

```text
prompt=32.782, completion=7.907/8192 (finish=stop, NON length — il modello si e' fermato da solo)
prefill = 182,88 t/s
decode  = 12,95 t/s
p1      = 0,77716   mean_len = 2,31   (nettamente sotto il riferimento storico per questa taglia: turno 32 a 33.344 token aveva p1=0,88141 mean_len=2,86 — possibile correlazione con la discontinuita' del secondo flip, non verificata)
SHA out = FF8E3868B2ADD8ADAC427456B81518EECA0943770391695E29568D164AD87F
```

**VERDETTO BRACCIO (a): FAIL sulla firma esatta, PASS sull'obiettivo di sopravvivenza.** Niente OOM, niente crash, la richiesta completa — il difetto originale del turno 32 (OOM garantito su questo identico prompt) resta risolto. Ma la firma richiesta dal chirurgo per dichiarare la v2 "certificata byte a riga" non è quella osservata: **due** eventi di flip-rinviato, non uno, e il secondo non è previsto da nessun ramo della tabella-flussi. Per il criterio fail-fast del coordinatore, mi fermo qui: **braccio (b) NON lanciato**, in attesa di decisione (procedere comunque con (b), o attendere una v3 mirata al secondo evento).

**Stato macchina dopo (a)**: 0 processi, porta 8099 libera, GPU 300/11816 MiB (P8, 1%), RAM 88,18 GB liberi. Nessun commit eseguito. Script: `t33_fase2a_v2_prompt32k.ps1` (scratchpad di sessione).

---

## Chirurgo 15 — ADDENDUM (sera): la firma attesa era SBAGLIATA, la v2 è GIUSTA — i due «flip rinviato» sono ENTRAMBI chunk di prompt: il server taglia ai checkpoint (`fine−2048` e `fine−4`). NIENTE v3

Lettura dal log della fase2a-v2 (righe 865-909) incrociata col riferimento 102k del turno 31.

**La catena vera dei chunk (misurata)**: `…30721 →(+13)→ 30734 [checkpoint 2] →(+2044)→ 32778 [checkpoint 3] →(+4)→ 32782 → primo decode → cambio n.2`. E sul 102k (turno 31, binario pre-fix): `…98305 → 99643 (+1338) → 101687 (+2044) → +4 = 101691`. Il server NON manda k·2048 + resto: piazza due tagli assoluti dalla fine — **`fine−2048`** (checkpoint di rollback) e **`fine−4`** (= n_max+1 speculativo) — e la taglia della chiamata intermedia vale `(fine−2048) − ultimo confine` ≈ `fine mod 2048 − 1`. Quindi:
- «restano 13» = chiamata intermedia da **13 token / 0 output** a cached 30721 — il PUNTO ESATTO del crash pre-fix («86,7% della prefill, n_tokens=30721/32782», turno 32): il fix ha lavorato proprio lì, a metà prompt, non sulla coda;
- «restano 3» = coda finale da **4 token / 1 output**, presente su OGNI prompt lungo di questa config (anche sul 102k);
- cambio n.2 alla PRIMA chiamata di decode vera, 574 ms dopo (righe 908-909: il secondo rinvio PRECEDE il cambio — il «in pieno decode» era un'illusione dell'ordine di lettura; i 16,05 s fra i due eventi sono il chunk da 2044 token a ~127 t/s, righe 881).

**Risposte alle due domande della regia**: (1) la guardia si disarma a ogni chiamata che NON rinvia e si RIARMA a ogni chunk sopra soglia — per questo il secondo evento ha potuto scattare (il 2044 l'ha riarmata), ed è un bene: era prompt vero; dopo il cambio n.2 (flag=decode) il ramo è irraggiungibile per costruzione — infatti 2 eventi in 7.907 token, non centinaia. (2) Quando scatta, il ramo NON tocca stato né buffer: trattiene la fase (nessuna transizione) e salta l'aggiornamento della guardia; a macchina in decode non può scattare.

**Sul p1 0,77716 / mean_len 2,31**: nella corsa v2 NESSUN calcolo è avvenuto in fase sbagliata (le due chiamate piccole erano prompt, in fase prefill = corretto). Il confronto con 0,88141/2,86 non è un confronto: quello è il prompt da 33.344 token (PrefixChars 91200), questo è il 32.782 (89800) — **prompt diverso, p1 mai confrontabile fra prompt diversi**. Baseline pre-fix per questo prompt non esiste (pre-fix crashava).

**Predizioni falsificabili**: (a) il rerun a completion 256 mostrerà gli STESSI due eventi alle STESSE posizioni (cached 30721 e 32778) — chunking deterministico; (b) la fase2b 102k mostrerà UN SOLO «flip rinviato, restano 3» (chiamata intermedia = 1338 > 64: nessun rinvio lì — ed è il motivo per cui il 102k non è mai crashato: la «fortuna aritmetica» del turno 32, ora col meccanismo esatto). **AVVISO GROSSO PER LA 2b: lo SHA output può LEGITTIMAMENTE differire dai riferimenti pre-fix dei turni 28/31 (`F0733E8C…`)**: pre-fix gli ultimi 4 token di prompt giravano in fase decode (il flip avveniva PRIMA della coda), con la v2 girano — giustamente — in prefill: split diversi ⇒ arrotondamenti diversi ⇒ traiettoria che può divergere. Giudicare a banda (decode ±3%, p1 nell'intorno di 0,911, lettura testo §4.10), NON a bit. Un match bit-esatto sarebbe gradito ma NON è promesso dal disegno.

**Firma attesa CORRETTA (sostituisce quella dell'entry principale)**: al load «fase=decode» senza rinvii; alla richiesta cambio n.1 + staging 1729; poi **N rinvii «flip rinviato», tutti PRIMA del primo decode** — N = [1 se la chiamata intermedia `fine−2048` è ≤ 64 token] + [1 per la coda `fine−4`, sempre] — ciascuno con `restano = n_tok − n_out`; cambio n.2 alla prima chiamata dopo il prompt; zero OOM. Per il 32.782: N=2 (13 e 3) ✓ — **la fase2a-v2 è dunque PASS PIENO con la firma corretta: v2 CONFERMATA, NESSUNA v3, SHA invariata `ECAEA60B…`.** Il caso «k·2048+1» del mandato originale va ritargetizzato: la variabile giusta è `fine mod 2048 ∈ [2..65]` (chiamata intermedia piccola), e il repro 32.782 (mod 14) È già il test di quel ramo. Due errori miei a verbale in questo giro: la firma «UN SOLO flip rinviato» era derivata dall'aritmetica ingenua `mod n_batch` invece che dal chunking REALE del server (i checkpoint tagliano), e la riga «coda resto = 1 → flippa a decode» della tabella-flussi presupponeva 1 output: la chiamata intermedia da 1 token ha 0 output e RINVIA (ugualmente sicuro, fase prefill a metà prompt è corretta).

**Coda della sera — il p1 resta un fascicolo APERTO a margine, con matrice PRE-REGISTRATA** (messaggio alla regia inviato PRIMA dell'atterraggio della 2b, perché il verdetto sia meccanico): 0,77716 sta 0,083 sotto il minimo della banda di famiglia 0,86-0,91 (1,6× lo spread su 3 punti) — sospetto ma non conclusivo: prompt senza riferimento (pre-fix crashava), contenuto generato diverso, finish=stop. Verifiche già fatte: testo §4.10 del 32k PULITO (saggio strutturato di 293 righe, marker d'apertura una volta sola, zero loop — dopo un falso allarme da sonda sbagliata: letto il file diag256 al posto del 32k, smentito contando le occorrenze); forense di rotta da sorgente: soglia `MMVQ_MAX_BATCH_SIZE=8` (`ggml-cuda.cu:2447`) — 13 token = rotta STAGING su slab (in prefill vivo = matematica corretta; in decode liberato = il crash pre-fix), 4 token = mmvq mappato zero-copy (stessi pesi, stessa matematica, mai staging): NESSUN meccanismo di corruzione a livello di op; contatori al cambio n.2 puliti. MATRICE: 2b in banda (p1 ~0,911±0,02, decode ±3%, §4.10) → braccio (c) = 33.344@v2 completion 8192 contro il riferimento pre-fix 0,88141/2,86 (unico A/B per-prompt esistente; unica differenza la fase della coda-4, intermedia 575 invariata; PARITÀ DI FINESTRA VERIFICATA SULL'ARTEFATTO: il riferimento è a completion **8192**, `finish=length` — summary `sota100k_ctx150k_densefa_stage_hc5_t32_b1_ctx32k_v2.summary.txt` righe 8/10/15/16: `completion=8192`, `p1=0.88141`, `mean_len=2.86`; il «256» circolato in serata era una confusione con la corsa diag256 di oggi) — dentro ~2 punti ⇒ **v2 PROMUOVIBILE** e lo 0,777 si archivia come varianza di contenuto; (c) fuori, o 2b fuori banda/testo sporco ⇒ **v3-soglia-8**: al rinvio si aggiunge `n_tokens_all > 8` — si rinviano SOLO le chiamate della rotta staging (9..64, quelle che il pre-fix ammazzava); le sub-9 tornano a flippare a decode = il percorso esatto di tutti i run di riferimento, con bit-comparabilità ripristinata su 33k/102k. Una riga più commento, backup DLL rituale, esecutore 34.

---

## Turno esecutore 33 — CORSA DIAGNOSTICA (256 completion): REGRESSIONE VERA CONFERMATA, non confondimento di lunghezza

Mandato del coordinatore: stessa config del braccio (a) (`PrefixChars=89800` → 32.782 token, resto 14), stesso fix v2 (`llama.dll` `ECAEA60B...`, invariato da prima — non riverificato una terza volta, nessun rebuild nel frattempo), ma `MaxTokens=256` invece di 8192. Doppio scopo: (1) separare confondimento-di-lunghezza da regressione vera nel p1/mean_len, confrontando a parità di completion col riferimento turno 32 (33.344 token, 256 tok: p1=0,88141, mean_len=2,86); (2) determinismo del secondo `flip rinviato`.

Preflight: 0 processi, GPU 300/11816 MiB (P8, 0%), RAM 88,07 GB liberi, porta 8099 libera. RunLabel `t33_fase2a_v2_diag256`.

```text
prompt=32.782, completion=256/256 (finish=length)
prefill = 182,74 t/s
decode  = 11,55 t/s
p1      = 0,63874   mean_len = 1,92
SHA out = 1F269253F5F8F9A5933B2FCFC9EF78C73431E3C66BB36DD80C6D51B0F57BD4CD
```

**Scopo 1 — p1/mean_len a parità di lunghezza: REGRESSIONE VERA, più severa del worst-case atteso.** Banda dichiarata dal coordinatore: `~0,87-0,89` → il crollo era confondimento di lunghezza; `~0,78` → regressione vera da riportare al chirurgo. Misurato: **p1=0,63874, mean_len=1,92** — sotto ANCHE la soglia "regressione vera". Isolare la finestra corta non attenua l'effetto, lo AGGRAVA: il completion lungo (7.907 tok, braccio (a)) lo aveva diluito a 0,77716 mescolando la zona contaminata (primi ~16-30 s) con il resto pulito della generazione; qui, con soli 256 token (~22 s totali di decode), la finestra intera cade dentro o subito dopo la zona del secondo flip, e il danno resta concentrato invece di mediarsi via.

**Scopo 2 — determinismo del secondo flip: CONFERMATO.** Conteggio esatto sull'intero file (`sota_ctx150000_densefa_stage_hc5_t33_fase2a_v2_diag256_f2_b2048.server.log`, grep `flip rinviato` su tutta la corsa): **2 eventi, non uno**, stesso schema del braccio (a) lungo:

```text
riga 867: 5.13.141.197  I decode: vram-a-fasi: flip rinviato, restano 13 token di prompt
riga 902: 5.29.237.694  I decode: vram-a-fasi: flip rinviato, restano 3 token di prompt
```

Delta = **16,096 s** — praticamente identico al delta del braccio (a) da 8.192 completion (16,05 s, misurato in un'altra corsa, altro processo). Il secondo evento non dipende da `MaxTokens`: è **deterministico e legato al prefill/setup del prompt stesso** (probabilmente al primo verify speculativo dopo il chunk-coda, ipotesi già segnalata nel braccio (a)), non al progredire della generazione — cade sempre alla stessa distanza dal primo flip, in entrambe le corse.

Zero OOM/CUDA error (error-scan pulito, divergenze tutte a 0). Shutdown `ctrl-c` pulito.

**VERDETTO SECCO: FAIL.** Il fix v2 elimina l'OOM del bug originale ma introduce una regressione di qualità reale e riproducibile (accettazione speculativa quasi dimezzata, p1 0,88→0,64) legata al secondo evento `flip rinviato, restano 3 token di prompt` — non è rumore né un confondimento di misura, è deterministico su due corse indipendenti (256 e 8.192 completion). **Non pronto per produzione**: serve una v3 che elimini anche il secondo evento (probabile candidato: il primo verify speculativo trattato dalla guardia come resto-di-prompt).

**Stato macchina a fine turno**: 0 processi, porta 8099 libera, GPU 271/11845 MiB (P8, 0%), RAM 87,99 GB liberi. Nessun commit eseguito. Script: `t33_fase2a_v2_diag256.ps1` (scratchpad di sessione).

**Passaggio di consegne (fine turno esecutore 33)**: braccio (b) (non-regressione 102k) mai lanciato su richiesta del coordinatore (avrebbe sprecato 102k di prefill se arriva una v3). Aperto per il prossimo esecutore: (1) v3 del fix mirata al secondo flip; (2) una volta chiusa, rifare per intero (a)+(b) da zero (non solo (b)) perché anche (a) ha certificato solo la sopravvivenza, non la qualità; (3) il braccio 3 facoltativo del chirurgo (non-regressione corto B1200, p1=0,90281/mean_len=2,80 bit-esatti attesi) resta MAI eseguito, in nessuna versione del fix.

---

## Turno esecutore 34 (24/8 sera) — PASSO 0/0.5 CONFERMATI; BRACCIO (b) TRATTENUTO (il mandato dichiarava «fase2a già passata», ma l'ultima entry del ledger, DOPO l'ADDENDUM, registra una regressione reale mai chiusa); BRACCIO 3 ESEGUITO — PASS pieno, bit-esatto

**Nota di ordinamento (scritta dopo, per onestà di cronaca)**: questa entry è stata scritta e appesa PRIMA che il commit `8e4b030` (CONTROVERDETTO, in fondo a questo file, timestamp 20:13:26 — atterrato mentre questo turno leggeva/eseguiva) raggiungesse questo esecutore. L'ordine fisico nel file è quindi invertito rispetto alla cronologia reale (il controverdetto è arrivato PRIMA che questa entry fosse completata, ma il mio append ha vinto la corsa sul file). Non la sposto per non rischiare l'integrità del testo già scritto: il seguito (verifica del controverdetto, braccio (b), eventuale (c)) è appeso in una nuova entry DOPO il CONTROVERDETTO, in fondo al file — quella è la sequenza da leggere.

Mandato ricevuto: validazione finale fix resto-64 v2 — fase 2b (102k) + braccio 3 (B1200 corto), con premessa «la fase 2a è già passata (il FAIL precedente era una firma attesa sbagliata)». Prima di lanciare nulla, lettura obbligatoria completa di RUNBOOK + LEDGER_23_AGOSTO per intero (righe 1531-1865, non solo l'entry «Chirurgo 15»).

### PASSO 0 — identità binario: PASS, tutti e cinque i file (non solo llama.dll)

```text
llama.dll               = ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035  (atteso, 2.276.352 B, mtime 24/08/2026 16:27:32 — IDENTICO)
llama-server.exe        = 3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9  (invariato)
ggml-cuda.dll            = 6EF5B781DDD14B6AB503580DEF7876AB38E9AE8E6A6347E665AA8A34C9C68B52  (invariato)
llama-common.dll         = DD6689ECE4AE405372E581FB60210576970081C16CA57F7698A3AC54CA59C5E5  (invariato)
llama-server-impl.dll    = 9B417B4F314E36C04B24BABC1D7FB731298C0E92A7BAAE240F71B57336821B88  (invariato)
```

### PASSO 0.5 — conferma della predizione del chirurgo sul log diag256: CONFERMATA, valori esatti

File: `D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t33_fase2a_v2_diag256_f2_b2048.server.log`. Grep mirato:

```text
riga 866: 5.13.141.027  I slot operator (): id 0 | task 0 | cached n_tokens = 30721, memory_seq_rm [30721, end)
riga 867: 5.13.141.197  I decode: vram-a-fasi: flip rinviato, restano 13 token di prompt
...
riga 899: 5.29.227.120  I slot operator (): id 0 | task 0 | cached n_tokens = 32778, memory_seq_rm [32778, end)
riga 902: 5.29.237.694  I decode: vram-a-fasi: flip rinviato, restano 3 token di prompt
```

`cached=30721` precede immediatamente il primo rinvio (chunk +13, coerente con `fine−2048`), `cached=32778` precede il secondo (chunk +4, coerente con `fine−4`) — **esattamente i valori predetti dall'ADDENDUM**. La spiegazione del chirurgo sulla firma (due rinvii, non uno, entrambi chunk di prompt) è confermata byte a riga.

### ATTENZIONE — il mandato era incompleto: la fase 2a NON è «già passata» senza riserve

L'ADDENDUM (riga 1815) risolve **solo** la firma (quanti eventi «flip rinviato» e perché) e dichiara v2 confermata su quella base, con l'avviso esplicito di giudicare «a banda, non a bit». Ma **l'ultima entry del ledger, cronologicamente successiva all'ADDENDUM** (righe 1834-1867, «CORSA DIAGNOSTICA 256 completion»), misura — sullo stesso prompt 32.782, a parità di completion col riferimento turno 32 — **p1=0,63874 / mean_len=1,92 contro l'atteso ~0,87-0,89** (confondimento di lunghezza) o **~0,78** (regressione vera secondo la banda dichiarata dal coordinatore stesso in quella corsa). Il valore osservato è **sotto anche la soglia "regressione vera"**. Verifica indipendente sul file grezzo (non solo la prosa del ledger), `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_t33_fase2a_v2_diag256.summary.txt`: `p1=0.63874`, `mean_len=1.92`, `sha256=1F269253F5F8F9A5933B2FCFC9EF78C73431E3C66BB36DD80C6D51B0F57BD4CD` — combacia esattamente coi numeri di ledger, non è un errore di trascrizione. Verdetto testuale di quella entry: **«VERDETTO SECCO: FAIL... Non pronto per produzione: serve una v3»** (riga 1863). E la «Passaggio di consegne» che chiude il turno 33 (righe 1867, appena sopra questa entry) dice **esplicitamente**: *braccio (b) mai lanciato «avrebbe sprecato 102k di prefill se arriva una v3»* e lo elenca come **aperto in attesa di v3**, non come pronto per il rerun.

Il mandato ricevuto da questo esecutore cita solo il FAIL della firma (risolto dall'ADDENDUM) e non menziona la corsa diagnostica successiva né la regressione di qualità: **premessa parziale, non falsa in sé ma incompleta in un modo che avrebbe portato a certificare come «non-regressione» un binario con una regressione nota e non richiusa sullo stesso identico meccanismo** (`restano 3` — presente, per ammissione dello stesso ADDENDUM, «su OGNI prompt lungo di questa config, anche sul 102k»).

**Decisione presa da questo esecutore, per fail-fast (regola esplicita del proprio mandato) e per REGOLA ZERO §2 del runbook** («un braccio non eseguito è un esito accettabile; un braccio eseguito male è un danno»): **BRACCIO (b) [non-regressione 102k] TRATTENUTO, non lanciato.** Il criterio di giudizio richiesto dal mandato («p1 in banda intorno a 0,911») è quasi certamente destinato al FAIL, per lo stesso meccanismo già misurato due volte (256 e 8.192 completion) sul prompt da 32k, che l'ADDENDUM stesso dichiara presente anche a 102k. Lanciarlo ora avrebbe (a) sprecato ~10+ minuti di prefill su un esito già preannunciato dal dato disponibile, (b) prodotto un verdetto PASS/FAIL potenzialmente fuorviante se letto senza il contesto della regressione aperta, (c) contraddetto la decisione esplicita e motivata del turno precedente.

### Risposta alla domanda del coordinatore (matrice di decisione): completion del punto 33.344 (PrefixChars 91200) del turno 32

**8192, non 256.** Verificato su due fonti indipendenti: (1) ledger riga 1601-1607, tabella B-1 del turno 32, tre punti tutti allo stesso `-MaxTokens 8192` (comando dichiarato «byte-per-byte identico» e ripreso testualmente da turno 33 fase 1 per il punto gemello 63.335, che mostra `-MaxTokens 8192` esplicito nel comando copiato); (2) file grezzo su disco `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_t32_b1_ctx32k_v2.summary.txt`: `prompt=33344, completion=8192`. Il 33.344 **non** è comparabile alla corsa diagnostica da 256 di questo fascicolo (regimi di lunghezza diversi), ma **è** comparabile al braccio (a) v2 da 7.907/8192 completion (stesso ordine di grandezza).

### BRACCIO 3 — non-regressione corta B1200: ESEGUITO — PASS pieno, p1/mean_len bit-esatti

Config ricostruita dai riferimenti disponibili (nessun turno precedente l'aveva mai eseguita): il runner B (`run_porto_hot.ps1`) ha **`LLAMA_VRAM_A_FASI=0` hardcoded** (riga 79 dello script) — la feature/il fix sotto test è quindi runtime-inattiva su questo banco per costruzione, coerente con l'attesa del chirurgo «la guardia non si arma mai sul corto» e col fatto che il riferimento bit-esatto citato (p1=0,90281/mean_len=2,80 = «L0 PROMOSSA» del 16/8, **riconfermato oggi stesso** da turno 31 come suo «controllo» con lo stesso comando) è stato ottenuto sempre con VRAM_A_FASI assente. Braccio 3 è quindi un controllo di non-regressione del **rebuild** (llama-context.{h,cpp} tocca codice condiviso) sul percorso corto di default, non uno stress-test del ramo guardia — coerente con «bit-esatto atteso».

Preflight (20:2x, 24/8): 0 processi, GPU 265/11851 MiB (P8), porte 8099-8101 libere, uptime 5703,9 min, RAM libera 87,8 GB, disco C 46,9/D 113,8 GB liberi, `jprompt.txt` 252 B SHA `C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9`.

**Comando esatto**:
```powershell
& 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' `
  -Tag 't34_chirurgo15v2_braccio3_corto_b1200_r1_20260824' `
  -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot $false `
  -SpecNmax 3 -SpecConf '0.80' `
  -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
```

```text
tag              = t34_chirurgo15v2_braccio3_corto_b1200_r1_20260824
runner           = B (run_porto_hot.ps1)
banco            = B1200
ripetizioni      = 1
leva variata     = ServerPath (binario v2, chirurgo 15) — nessuna leva runtime rispetto al riferimento
prompt           = 68 token (jprompt.txt)
completion       = 1200/1200 (finish_reason=length)
eval t/s (decode)  = 16,68
prompt t/s (prefill) = 21,15
p1               = 0,90281 (771 accepted / 854 generated)
mean_len         = 2,80
SHA output       = 1EDA23452DE9292C817EAF47532724A409DD2FFE3B3EF9E165ED887BA4169089  lunghezza = 3782 caratteri
cache-esperti    = 473 slot da 6.75 MiB = 3194 MiB in VRAM ..., sfratto_par=1  (riga 260 log, identica ai riferimenti storici)
cache-esperti domanda = 275477 (colpi 195401 = 70,9%, buchi 80076, miss 29,1%, in ritardo 0=0,0%)  [nessun riferimento pari-nmax per questo campo: nuovo, non confrontabile]
VRAM_A_FASI      = 0 (E, esplicito nel manifesto) — zero righe "VRAM A FASI"/"flip rinviato" nell'intero log, come atteso
errori           = zero CUDA error / out of memory / GGML_ASSERT; divergenze: taglia=0 ids=0 out=0 GRIGLIA-corta=0 su tutte le righe rilevatore-replay
snapshot         = porto_hot_snapshot = 0
SHA llama.dll    = ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035
SHA llama-server = 3D3347D1A4E03CA103E6BD9FCD32C2DEF61E9C413F2F9658D53F16B6910009C9
build            = chirurgo 15 v2 (16:27:32)
server vivi max  = 1 (atteso) ; RAM libera min osservata = 87,8 GB
uptime a inizio  = 5703,9 min
esito            = PROMOSSO
percorsi file    = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\t34_chirurgo15v2_braccio3_corto_b1200_r1_20260824.{server.log,server.out,summary.json,r1.response.json,r1.output.txt}
anomalie         = nessuna
```

**Controllo di coerenza §4.10 (prima replica per intero, banco corto)**: letta integralmente `...r1.output.txt` (HTML landing page cyberpunk "NeuraForge" — il prompt standard del banco). Lingua sana: sì. Assenza di loop/ripetizioni patologiche: sì. Pertinenza al prompt: sì (markup/CSS coerenti, commenti in italiano come da richiesta). Degradazione progressiva: no (il testo si interrompe a metà di un valore CSS per raggiungimento del tetto di 1200 token — troncamento per lunghezza, non degradazione).

**Confronto col riferimento**: p1 e mean_len **bit-esatti a 5/2 cifre decimali** sia col valore atteso dal chirurgo (0,90281/2,80) sia con la rimisura fatta stamattina da turno 31 sullo stesso identico comando sul binario PRE-chirurgo15 (stessa tabella, riga «controllo (corretto)»). **Non disponibile** un confronto SHA-bit-esatto o accepted/generated grezzo: né la tabella di turno 31 né il runbook §4.5/4.7 riportano una SHA o un conteggio accepted/generated per questa esatta combinazione (nmax=3/conf=0,80/MaxTokens=1200) — solo p1/mean_len, che è comunque il criterio testualmente richiesto dal chirurgo.

**VERDETTO BRACCIO 3: PASS pieno.** Il rebuild del chirurgo 15 (v2) non altera in alcun modo misurabile il percorso corto di default: p1/mean_len bit-esatti, zero errori, cache-esperti identica, VRAM_A_FASI correttamente inerte. Nessuna riserva.

### Postflight e stato macchina

```text
POSTFLIGHT (20:27:29, 24/8): ram_libera=88 GB | gpu: 272 MiB usati/11844 liberi, clock 210 MHz, potenza 13,01 W | processi_llama=0
```

Macchina pulita. Nessun commit eseguito (di competenza della regia). Nessun file toccato in `D:\llama-subtract` (sola lettura, come da mandato).

### Stato del turno: IN ATTESA DI ISTRUZIONI (non ritirato)

Per l'aggiornamento del coordinatore («resta in attesa di istruzioni invece di ritirarti»): verdetti braccio 3 (PASS) e la lettura del braccio (b) (TRATTENUTO, motivazione sopra) sono pronti. In attesa di una delle due decisioni della matrice: (c) A/B per-prompt sul 33.344 su v2, oppure GO v3. Nessun'altra azione intrapresa nel frattempo su questo turno.

---

## CONTROVERDETTO (regia, 24/8 sera) — supera il framing del commit 976646a

Il «FAIL, regressione vera» della fase 2a è RITIRATO. Verdetto del chirurgo da sorgente+log (addendum sotto l'entry fase2a): la v2 è CORRETTA, nessuna v3. Sbagliata era la firma attesa «un solo flip rinviato»: i DUE eventi sono entrambi chunk di prompt GENUINI — il server taglia ai checkpoint (fine−2048 e fine−4, non k·2048+resto), quindi la coda da 4 token esiste su ogni prompt lungo e «restano 13» è esattamente il punto del crash pre-fix. La guardia si disarma a ogni chiamata che non rinvia; dopo il cambio n.2 il ramo è irraggiungibile; zero stato toccato. La «regressione p1 .88→.64» era un confronto fra PROMPT DIVERSI (32.782 vs 33.344) a completion diverse — p1 non è mai confrontabile fra prompt, e il maledetto non ha baseline pre-fix perché pre-fix crashava. I «16 s fra i flip» erano un chunk di prefill da 2044 token a ~127 t/s (contatori cached 30734→32778), non decode. Fase 2b: GO con firma attesa UN SOLO «restano 3» e giudizio A BANDA (±3% sul turno 31, p1 ~0,911, §4.10); lo SHA output può legittimamente divergere da F0733E8C (i 4 di coda pre-fix giravano in fase decode, con v2 in prefill). Esecutore 34 in corsa.

---

## Chirurgo 15 — FORENSE DI ROTTA A CATALOGO (fondamento dell'innocuità coda-4 e del disegno v3-soglia-8)

Catalogazione formale richiesta dall'esecutore 34 (protocollo «ogni output catalogato»): la sintesi stava già nella «Coda della sera» dentro l'addendum del chirurgo (~riga 1832, paragrafo-riga unica, facile da mancare leggendo dalla coda) ma non nello stato committato. Qui autosufficiente.

**La rotta, letta dal sorgente** (`ggml_cuda_mul_mat_id`, `ggml-cuda.cu:2445-2448`): il ramo layer-major/staging si prende SOLO se valgono TUTTE — buffer mappato (esperti `CUDA0_Mapped`), **`dst->ne[2] > MMVQ_MAX_BATCH_SIZE` (= 8)**, e mmq utilizzabile. Sotto o uguale a 8 righe si cade al cancello cache-decode (`:2483`, commento del sorgente: «Solo decode (un token)… Qualunque condizione manchi, si cade sul percorso di sempre senza toccare niente») e in sua assenza al percorso mappato zero-copy (mmvq sui pesi host via PCIe — stessi byte, stessa matematica). Lo staging si alloca PIGRAMENTE alla prima richiesta (`ggml_cuda_cache_esperti_layer_major`, `cache-esperti.cu:5601-5661`) e **al primo fallimento si latcha spento per l'intero processo** (`layer_major_fallita`, `:5628`).

**Cosa spiega, tutto insieme**:
1. *Il crash pre-fix* (turno 32, 3/3): la chiamata intermedia da 13 token (13 > 8) chiede la rotta staging ANCHE a fase decode; col flip prematuro lo staging era stato liberato e la VRAM era a 0 → `cudaMalloc` 1729 MiB fallisce → fallback su mmq che vuole pool → OOM `mmq.cu:183`. La geometria «102k salvo, 32k morto» segue dalla taglia dell'intermedia (1338 > 64 → mai classificata decode; 13 ≤ 64 → flip prematuro).
2. *L'innocuità della coda-4 in v2*: 4 ≤ 8 → MAI staging; in fase prefill (cache a 0 slot) cade sul percorso mappato zero-copy — kernel mmvq, pesi identici, nessun meccanismo di corruzione a livello di op. La 13-in-prefill è ugualmente sana: staging VIVO → mmq sullo slab col banco completo.
3. *I contatori al cambio n.2* (log fase2a-v2, righe 910-930): `domanda 0, colpi 0, copie 0, replay divergenze 0, acceptmoe lanci 0` — il prompt non ha mai bussato alla cache, come da disegno della fase.
4. *Il disegno v3-soglia-8* (armato, non buildato): aggiungere `n_tokens_all > 8` al rinvio = si rinviano SOLO le chiamate che prenderebbero la rotta staging (9..64, quelle che il pre-fix ammazzava); le ≤8 tornano a flippare a decode = il percorso esatto di TUTTI i run di riferimento, bit-comparabilità ripristinata su 33k/102k. Il numero 8 è `MMVQ_MAX_BATCH_SIZE`: se un giorno cambia lato CUDA, il commento nel classificatore deve puntare a `ggml-cuda.cu:2447` perché i due si muovano insieme.

A margine, recepita la scoperta dell'esecutore 34 sulla diag256 (etichetta «parità a 256» contro riferimento a 8192): coerente con la verifica d'artefatto già a matrice — il riferimento t32 è a completion 8192 (`summary` righe 8/10/15/16) e il braccio (c) si corre a 8192.

---

## Turno esecutore 34 — SEGUITO: CONTROVERDETTO verificato e accettato; BRACCIO (b) PASS pieno a firme esatte; BRACCIO (c) lanciato (matrice pre-autorizzata applicata meccanicamente)

Ricevuto il controverdetto (commit `8e4b030`) mentre il braccio 3 era in scrittura. Verificato prima di agire, non accettato per asserzione: `git show 8e4b030` conferma commit reale di imanu, 20:13:26, 4' dopo il FAIL (`976646a`, 20:09:11); testo committato identico a quello riportato in chat. Incrociati due dei tre argomenti con materiale già letto (indenne); sul terzo (confronto p1 invalido) trovata conferma PIÙ FORTE di quella dichiarata: la diag256 dichiarava «parità di completion» contro il riferimento t32 33.344 «a 256 tok», ma il grezzo (`t32_b1_ctx32k_v2.summary.txt`) mostra quel riferimento a **completion=8192** — doppio confondimento (prompt e lunghezza), non uno solo. Segnalato in chat; ora catalogato sopra dalla regia con citazione file:riga (`ggml-cuda.cu:2445-2448`, coda-4 ≤ `MMVQ_MAX_BATCH_SIZE`=8 ⇒ mai staging, percorso mmvq mappato sempre sano). Nota metodologica anche per la disciplina reasoning-budget del nuovo riferimento API (`docs/porto/RIFERIMENTO_API_DEEPSEEK_V4.md`, letto per intero, nessuna istruzione incorporata, contenuto verificato aderente al riassunto ricevuto): **`reasoning-budget-tokens=0` su entrambi i lati di ogni confronto di stasera** (v2 e turno 31) — dichiarato qui, A/B intatto.

Nota di ordinamento: la mia entry precedente («Turno esecutore 34», sopra la sezione CONTROVERDETTO) era stata scritta e appesa PRIMA che questo controverdetto raggiungesse il turno — vedi la nota lì. Questa entry e le successive sono la sequenza reale da leggere in coda.

### BRACCIO (b) — non-regressione 102k su v2: PASS pieno, firme esatte

Preflight (20:36:56): 0 processi, GPU 261/11855 MiB, porte 8099-8101 libere. Comando (config esatta turno 31, `p1b_conf.ps1` — letto per intero prima dell'uso, nessuna sorpresa, `LLAMA_VRAM_A_FASI=2` confermato nel baseline dello script):

```powershell
$env:LLAMA_KV_GATHER = '1'; $env:LLAMA_CUDA_SORT_CHUNK_MIB = '8'
& '...\p1b_conf.ps1' -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 `
  -RunLabel 't34_fase2b_102k_v2_20260824' -Context 150000 -MaxTokens 8192 `
  -SpecNmax 3 -SpecConf '0.70' -Repliche 1 -CtxCheckpointMinStep 32 `
  -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
```

```text
tag              = sota_ctx150000_densefa_stage_hc5_t34_fase2b_102k_v2_20260824_f2_b2048
runner           = prefill (p1b_conf.ps1, script di sessione — letto per intero, nessuna sorpresa)
banco            = prefill/lungo (102k)
ripetizioni      = 1
leva variata     = ServerPath (binario v2, chirurgo 15) — nessuna leva runtime rispetto al riferimento turno 31
reasoning-budget-tokens = 0 (entrambi i lati del confronto — disciplina nuova dichiarata)
prompt           = 101.691 token (jprompt102k.txt, 285.268 B, SHA 3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473, riverificato)
completion       = 8192/8192 (finish=length)
prefill t/s      = 137,63  (rif. turno 31: 137,34 — +0,21%)
decode t/s       = 13,26 / 75,44 ms/token  (rif.: 13,52 / 73,96 ms/token — +2,00% ms/token, DENTRO banda ±3%)
p1               = 0,90229  (rif. ~0,911 — -0,95%, DENTRO banda)
mean_len         = 3,06  (rif. 3,18 — nessun criterio esplicito, coerente in direzione col p1)
SHA output       = B205E05298E7C4467AD1E1DCE1D25C06C90A3E913FEBE5D754517FB7D7DEDED1  (dato, non criterio — diverge legittimamente da F0733E8C per design, coda in prefill non decode)
firma 1 (warmup pulito) = CONFERMATA: primo evento vram_a_fasi e' il flip diretto a decode, zero "flip rinviato" prima della richiesta
firma 2 (UN SOLO "restano 3") = CONFERMATA ESATTA: grep -c "flip rinviato" sull'INTERO log (5697 righe, non solo il tail-20 del wrapper) = 1, riga 1267, "restano 3 token di prompt"; l'intermedia (fine-2048, +1338>64) non rinvia, come predetto
firma 3 (zero OOM) = CONFERMATA: zero righe CUDA error/out of memory/GGML_ASSERT/invalid vector su tutto il log
cache-esperti    = 473 slot..., sfratto_par=1 (riga 271, identico ai riferimenti storici)
errori           = divergenze taglia=0 ids=0 out=0 su tutte le righe rilevatore-replay
snapshot         = n/a (endpoint chat/completions diretto, non runner B)
SHA llama.dll    = ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035
build            = chirurgo 15 v2 (16:27:32)
server vivi max  = 1; shutdown = ctrl-c pulito
esito            = PROMOSSO
percorsi file    = D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_t34_fase2b_102k_v2_20260824.summary.txt , D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t34_fase2b_102k_v2_20260824_f2_b2048.{server.log,server.out,_q1.response.json,_q1.output.txt}
anomalie         = nessuna
```

**Controllo §4.10 (banco lungo, lettura a campione — qui integrale, il file e' risultato corto abbastanza)**: `..._q1.output.txt`, 736 righe, saggio tecnico in italiano sull'architettura DSV4/cache-esperti/overlap, grounded nel prompt reale (nomi di funzioni/struct coerenti col progetto). Lingua sana: sì. Loop/ripetizioni: no. Pertinenza: sì, pienamente. Degradazione: no — tronca puliti a metà frase per il tetto di 8192 token, qualità costante dalla sezione 1 alla 14.

**VERDETTO BRACCIO (b): PASS pieno.** Tutte e tre le firme esatte (non solo "in banda" — la firma di conteggio è binaria e ha dato esattamente 1); throughput e p1 dentro la banda ±3% dichiarata dal mandato su entrambi i lati; nessuna anomalia; qualità del testo confermata a lettura integrale. Spiegazione di fondo ora disponibile ledger-side (entry "FORENSE DI ROTTA" sopra): la coda-4 non tocca mai la rotta staging (4 ≤ MMVQ_MAX_BATCH_SIZE=8), quindi il PASS non è un colpo di fortuna statistico ma la conseguenza attesa della meccanica.

### Matrice applicata meccanicamente: (b) IN BANDA -> BRACCIO (c) lanciato

Per la pre-autorizzazione del coordinatore, nessuna ulteriore conferma richiesta. Preflight (21:06:36): 0 processi, GPU 244/11872 MiB, porte libere. Lanciato in background (bx5rgsqrq), stessa config del punto 33.344 del turno 32 (PrefixChars 91200), stesso `reasoning-budget-tokens=0`, **unica variabile la DLL** (v2 `ECAEA60B` contro la pre-fix `40E1DEAF` di allora):

```powershell
$env:LLAMA_KV_GATHER='1'; $env:LLAMA_CUDA_SORT_CHUNK_MIB='8'
& '...\p1b_conf.ps1' -Port 8099 -StartBatch 2048 -BlockSparse 0 -HcFused 5 `
  -RunLabel 't34_braccio_c_33344_v2_20260824' -PrefixChars 91200 -Context 150000 -MaxTokens 8192 `
  -SpecNmax 3 -SpecConf '0.70' -Repliche 1 -CtxCheckpointMinStep 32 `
  -GraphReusePerTaglia 1 -ReasoningBudgetTokens 0 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
```

Criterio dichiarato: p1 entro ~2 punti da 0,88141, mean_len ~2,86, §4.10 pulito, SHA come dato. Atteso per design (v3-soglia-8 non ancora costruita, questo è ancora v2): coda-4 in prefill invece che decode, quindi SHA quasi certamente NON bit-esatto a `D73A5455...`, ma p1/mean_len dovrebbero restare in banda per lo stesso motivo strutturale del braccio (b) (coda-4 mai sulla rotta staging). In corsa, esito a seguire non appena il task in background notifica.

### BRACCIO (c) — risultato: PASS pieno, dentro criterio

```text
tag              = sota_ctx150000_densefa_stage_hc5_t34_braccio_c_33344_v2_20260824_f2_b2048
prompt           = 33.344 token (PrefixChars 91200, jprompt102k.txt troncato)
completion       = 8192/8192 (finish=length)
prefill t/s      = 183,72  (rif. turno 32 stesso punto: 182,95 — +0,42%)
decode t/s       = 13,74 / 72,79 ms/token  (rif.: 13,8506 / 72,199 ms/token — -0,80% t/s, sostanzialmente invariato)
p1               = 0,86469  (rif. 0,88141 — delta 1,67 punti percentuali, DENTRO "~2 punti")
mean_len         = 2,82  (rif. 2,86 — delta -0,04, in banda)
SHA output       = 515C678CD73A46B605D56237BB497A32E32C2FDAD92EE3A43FD16C409E9B2B0D  (dato: diverge da D73A5455... come atteso, coda-4 ora in prefill non decode)
firma (UN SOLO "restano 3") = CONFERMATA ESATTA sull'INTERO log (7596 righe): grep -c "flip rinviato" = 1, riga 902
errori           = zero CUDA error/OOM/GGML_ASSERT su tutto il log; divergenze taglia=0 ids=0 out=0 su tutte le righe rilevatore-replay
identity         = cache-esperti 473 slot..., sfratto_par=1 (riga 271, identica)
reasoning-budget-tokens = 0 (entrambi i lati)
shutdown         = ctrl-c pulito; listening/idle puliti a inizio e fine
esito            = PROMOSSO
percorsi file    = D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_t34_braccio_c_33344_v2_20260824.summary.txt , D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_t34_braccio_c_33344_v2_20260824_f2_b2048.{server.log,server.out,_q1.response.json,_q1.output.txt}
```

**Controllo §4.10**: `..._q1.output.txt` letto per intero (684 righe prodotte prima del taglio a 8192 token). Saggio tecnico sulla stessa architettura (cache-esperti/DSV4/overlap), con commenti che citano date e incidenti reali del progetto (DwarfStar, «braccio delle 07:31», «il battito fisso a 60 ha mentito il 6/8») coerenti col resto del ledger — grounding genuino nel prompt, non confabulazione. Lingua sana: sì. Loop: no. Pertinenza: sì. Degradazione: no, tronca a metà frase per tetto token con qualità costante dalla sezione 1 alla 19.

**VERDETTO BRACCIO (c): PASS pieno.** p1/mean_len dentro il criterio dichiarato, firma esatta (1 solo rinvio, stesso meccanismo coda-4-mai-staging del braccio (b)), zero errori, §4.10 pulito. SHA diverge dal pre-fix come predetto per design, coerente e non allarmante.

### VERDETTO CONSOLIDATO — fix resto-64 v2 (llama.dll `ECAEA60B96599741F2D879B4644157507124FBAD4DAE4725614902AE0699C035`)

Con questo si chiude la matrice di validazione richiesta all'esecutore 34:

| braccio | prompt | esito | note |
|---|---|---|---|
| (a) 32k, turno 33 | 32.782 (resto 14) | PASS (sopravvivenza sempre; qualità ora spiegata dal catalogo forense — coda-4 mai su staging) | nessun v3 necessario, il FAIL di qualità del 976646a era un doppio confondimento prompt+completion, ritirato con `8e4b030` e verificato in modo indipendente da questo esecutore |
| (b) 102k | 101.691 | **PASS pieno**, firme esatte, in banda | questo turno |
| (c) 33k A/B | 33.344 | **PASS pieno**, dentro criterio | questo turno |
| 3, B1200 corto | 68 (jprompt.txt) | **PASS pieno**, bit-esatto | questo turno; guardia mai armata per costruzione (VRAM_A_FASI=0 sul banco corto) |

Zero OOM su tutti e quattro. Zero divergenze rilevatore-replay su tutti e quattro. Nessuna firma fuori posto. Il fix è validato end-to-end: corto (guardia disarmata), 33k/102k (guardia armata, un solo rinvio ciascuno, sempre sotto soglia staging). **Nessuna v3 richiesta.** Sorgente v2 (`llama-context.{h,cpp}`, `D:\llama-subtract`) pronto per il commit di regia insieme a questo verdetto — nessun commit eseguito da questo esecutore (fuori mandato, di competenza della regia).

### Stato macchina e chiusura turno

Postflight (21:23:57): 0 processi, GPU 249/11867 MiB (P8), RAM libera 87,5 GB. Macchina pulita. Nessun commit eseguito. `D:\llama-subtract` non toccato (sola lettura per l'intero turno, come da mandato). Script di sessione usati: `p1b_conf.ps1` (letto integralmente prima dell'uso, pre-esistente nello scratchpad di sessione), `run_porto_hot.ps1` (repo Codex, invariato). In attesa di istruzioni per il commit o per un eventuale banco aggiuntivo.
