# HANDOFF PORTO - 15 AGOSTO 2026, NOTTE

Questo documento e' il punto di ripresa autoritativo dopo l'audit completo dei
ledger, degli Atlanti, del registro intuizioni e delle task Codex precedenti.
Non sostituisce i dati grezzi. Per un conflitto numerico vince sempre il record
piu' recente in `LEDGER_15_AGOSTO.md`, poi `LEDGER_14_AGOSTO.md`.

## 0. Stato esecutivo

- Obiettivo ancora aperto: decode corretto DS4 + DSpark Porto ad almeno
  **20,00 token/s medi verificati**. Traguardo 30 t/s soltanto se un cancello
  quantitativo mostra un ceiling credibile.
- Record storico certificato: **16,0733 t/s**, tre run 16,04 / 16,11 / 16,07,
  `MASSA2`, target 473 slot, draft 12 slot, K2, NMAX2, conf 0,8,
  AcceptMoE 0,75 compact, copy-all, corsie stabili, FORK2 blocks8.
- **Avvertenza 16 agosto:** il record non e' la baseline operativa del binario
  corrente. La stessa configurazione lunga, stesso testo e stessi contatori,
  produce oggi **10,53-10,54 t/s**. Prima di cercare 20 bisogna recuperare il
  fast path da 16,07; la regressione e' localizzata nel tempo host del backend
  CUDA (`calc altri` 4,080 -> 22,318 ms/grafo), non nell'acceptance.
- Ultimo B160 valido: **10,37 t/s**, 96,40 ms/token, p1=.80583, SHA output
  identico alla reference slot-diretto. E' la fusione gate+up cache-aware,
  +1,47% contro 10,22 t/s nello stesso banco. E' corretta ma troppo piccola e
  resta spenta di default.
- Il macro-kernel senza deduplica e' bit-esatto a **10,38 t/s** nel B160 K0;
  tutte le forme di deduplica provate corrompono l'uscita. Leva default-off.
- Nessun commit e nessun push eseguiti.
- Worktree `D:\llama-overlap` molto dirty e condiviso con il lavoro utente.
  Non resettare, non fare checkout distruttivi, non pulire file non tracciati.
- Al termine del tentativo fallito il server e' uscito; non e' stato lasciato
  intenzionalmente alcun processo llama attivo.

## 1. Vincoli non negoziabili dell'utente

1. **Mai WSL.** Tutto il mese di lavoro e' Windows nativo. Build, server,
   runner, Python e strumenti devono restare Windows.
2. Non ripetere politiche gia' falsificate sotto un nome nuovo.
3. L'idea guida e' far girare il modello come se fosse interamente residente
   in VRAM: anticipare, orchestrare e trasportare; CPU solo come rescue quando
   una deadline e' gia' a rischio, non come rendez-vous per layer.
4. Unire le lezioni del prefill al decode senza imporre layer-major dove il
   decode non lo consente. La lezione utile e' ridurre allocazioni, dispatch,
   barriere e riletture, preservando la MMVQ/MMQ Porto.
5. Le sonde rallentano. Un profilo invasivo vale soltanto per la scomposizione
   dei tempi e non va confrontato in t/s con un banco pulito.
6. Crediti cloud scarsi. Evitare nuovi subagenti cloud per lavori che si possono
   fare localmente. DS4 locale e' stato collegato come agente read-only nativo
   Windows; usarlo con prompt corti e contesto controllato.
7. Nessun commit/push senza approvazione esplicita.

## 2. Repositori, modelli e percorsi

Runtime attivo:

```text
D:\llama-overlap
```

Documentazione Porto:

```text
C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto
```

Workspace della task:

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3
```

Runner e analizzatore:

```text
...\work\run_porto_hot.ps1
...\work\analyze_route_trace.py
```

Modelli:

```text
Target: C:\ds4-models\DS4-0731-IQ2XXS.gguf
Draft:  D:\ds4-models\DSpark-draft-Q2K.gguf
```

Prompt breve:

```text
D:\ds4_work\llama_run\jprompt.txt
```

Binario:

```text
D:\llama-overlap\build\bin\llama-server.exe
```

## 3. Fonti effettivamente lette

L'audit delegato e' stato completato prima di questa ripresa:

- tutti gli otto ledger Porto disponibili, inclusi 6-8, 9, 10, 11, 13, 14,
  15 agosto;
- `LEDGER_RUN.tsv` e documenti di recupero sessione;
- tutti i documenti Atlante e relativi riferimenti lunghi;
- il vero registro intuizioni:
  `C:\Users\imanu\source\repos\reap-loop\docs\INTUITION_REGISTER.md`;
- quattro task Codex prioritarie paginate fino a EOF, inclusa la pinned luglio;
- gli handoff 14/15 agosto e il documento nuova chat.

Reperto decisivo non sempre esplicito nei ledger: la richiesta dell'utente e'
un planner globale del ciclo target + DSpark, con trasporto L -> L+1/L+2 e CPU
solo per deadline gia' perse. La vecchia implementazione aveva deviato verso
K2 fisso o partizioni locali. Non confondere le due cose.

## 4. Perche' si vedevano 8,5-11 t/s invece dei 16 t/s

**Correzione autoritativa del 16 agosto:** non era solo clock, banco corto o
profiling. Questi effetti esistevano, ma un B1200 identico al record ha provato
una regressione reale del runtime corrente.

1. I B20/B160 hanno acceptance piu' bassa e ammortizzano male warm-up e cambi
   di forma; non possono sostituire il banco lungo.
2. Planner seriale, graph spenti e alcune sonde invasive spiegano parte degli
   8,39-10,37 t/s infrastrutturali.
3. `porto_hot_snapshot=true` non e' neutro: nel B1200 corrente da' 9,87 t/s e
   p1=.85316; senza snapshot torna il testo storico byte-identico normalizzato,
   p1=.90025 e 10,54 t/s.
4. Anche senza snapshot, a parita' di testo, p1, grafi, split, hit e copie,
   restano circa 39,1 secondi di regressione. Il profiler localizza 35,6 secondi
   in piu' dentro le chiamate non-CPU `graph_compute_async`.
5. Accendere `GGML_SCHED_PROFILO=1` nel banco corrente cambia 10,54 -> 10,53:
   in questo caso la sonda misura il difetto ma non lo causa. Le altre sonde
   devono comunque restare fuori dal banco di produzione.

Numeri da non mescolare:

| Banco | Decode | Significato |
|---|---:|---|
| Record 13/14 agosto, tre run | **16,0733 t/s** | storico certificato, non riprodotto oggi |
| K2 B1200 corrente, snapshot off | **10,54 t/s** | testo storico identico, p1=.90025 |
| K2 B1200 corrente, snapshot on | **9,87 t/s** | traiettoria diversa, p1=.85316 |
| Reference planner lunga contingente | **11,38 t/s** | A relativo serale |
| Planner async tail509 | **11,49 t/s** | +0,97% relativo, parita' esatta |
| Slot diretto B160 | **10,22 t/s** | reference breve contingente |
| Gate+up fuso B160 | **10,37 t/s** | +1,47%, corretto, non macro |
| Macro no-dedup B160 K0 | **10,38 t/s** | bit-esatto, ma nessun riuso |

## 5. Budget quantitativo verso 20 e 30

Da 16,0733 a 20 t/s:

```text
62,215 ms/token -> 50,000 ms/token
guadagno richiesto = circa 12,214 ms/token
su 43 layer = circa 0,284 ms/layer
```

Da 16,0733 a 30 t/s:

```text
62,215 ms/token -> 33,333 ms/token
guadagno richiesto = circa 28,882 ms/token
```

Il solo trasporto DMA ha ceiling misurato circa 19,453 t/s. Quindi 20 richiede
anche una riduzione del lavoro compute/dispatch/rilettura. Trenta t/s non e'
oggi una promessa credibile: richiede quasi dimezzare il tempo SOTA, oppure un
cambio di hardware, numerica o algoritmo molto piu' grande dei bracci correnti.

## 6. Architettura corrente funzionante

La catena promossa, pur senza guadagno macro, e' corretta:

```text
processo Windows unico
  -> target e DSpark caricati una volta
  -> prompt/prefill
  -> snapshot caldo target + draft + slab
  -> restore caldo
  -> attivazione calendario soltanto al confine prompt/decode
  -> planner assegna (layer, expert, slot, release, deadline)
  -> trasportatore persistente prepara la slab fuori dalla cattura graph
  -> MMVQ consuma slot diretti
  -> drain del piano
```

Proprieta' verificate:

- planner lungo: 509/509 cicli;
- 43.244 copie nel tail lungo;
- 222.396/222.396 hit allineati;
- zero deadline miss e zero divergenze;
- SHA e p1 identici alla reference;
- restore caldo target 473/473 slot, circa 3.194 MiB;
- restore caldo draft 9/12 slot nel banco breve;
- attivazione slot-diretti post-prompt, mai durante il prefill;
- identita' CUDA Graph include lo stato slot-diretti per evitare replay stantio.

Questa infrastruttura va conservata. Il suo guadagno misurato e' circa un punto
percentuale, quindi non va ottimizzata localmente come se fosse il fronte macro.

## 7. Audit blacklist: non ripetere

### 7.1 Corsie CPU/GPU locali

- K fisso/frazionario/adattivo locale gia' esplorato.
- Sweep valido: K1 13,67; K1,8 13,11; K2 14,17; K3 12,53.
- FIDDLER residente->GPU/non residente->CPU: -7,8%; 29 rendez-vous per ciclo,
  27,4 ms/ciclo persi.
- Lane mobile per massa: 15,53 contro 16,0733.
- Non proporre di nuovo "CPU se trasporto indietro" come partizione per layer.
  CPU rescue a deadline e' diverso, ma non deve creare join per layer.

### 7.2 Prefetch locale

- Current/next-layer, cieco, oracle, CURA, SCUDO, PF_TOP, W2/W4 tutti provati.
- Anche l'oracle esatto perde per duplicazione del lavoro.
- Aumentare hit rate non ha automaticamente aumentato t/s.
- Non fare un'altra variante locale di prefetch o replacement.

### 7.3 Exact-demand e mapped

- RCI mapped, whole-FFN, VRES, banca B transiente, single/multi-stream, TILE
  GPU-driven gia' chiusi.
- TILE deduplicato e bit-identico: 10,45 t/s, circa 25,15 GiB letti via SM/UVA,
  solo 4,10 GiB/s end-to-end.
- Exact host rendez-vous dentro CUDA Graph ha deadlock/failure.
- Non tentare altre griglie/coalescenze dello stesso mapped read/install.

### 7.4 Super-op e microtuning

- Super-op FFN custom v1 ha abbandonato la MMVQ Porto e perso circa 53%.
- CPU FFN super-op perde contro i tre MMID CPU esistenti.
- FORK_RIUSA_SLOT -1,95%; SALTA_COPIA_PARITA -4,37%.
- JOIN_ASYNC neutro/rumore.
- Allungare drafter/NMAX3-5 peggiora.
- Acceptance locale, ESATTE2, Q2Kfix e row0 gia' provati.

### 7.5 Prefill portato ciecamente al decode

- Staging bulk chunk prefill +20,3% e block-sparse FA +53,95% sono lezioni
  positive del prefill.
- Layer-major vero, split attention/FFN, macro FFN custom e packetizer CPU hanno
  perso o corrotto.
- Portare nel decode la riduzione di dispatch/barriere e il grouped reuse;
  non forzare l'ordine layer-major.

### 7.6 KV e hot state

- `/slots` salva circa 840 MiB in 1,43 s ma il restore successivo aveva LCP=1
  e riprefillava: non e' riuso KV automatico.
- KV ring vecchio: +7,8% in un braccio e -5,7% nel composto. Contraddittorio,
  riapribile solo su banco corrente con contabita' byte e checksum multi-turn.
- Non presentare la KV come scorciatoia gia' pronta.

## 8. Fronti ancora aperti dopo l'audit

1. Macro-v2 attorno alla MMVQ Porto, senza riscrivere i dot veloci.
2. Planner globale target+DSpark come demand calendar, non K locale.
3. Trasportatore persistente batch/multi-layer con ownership e generazioni.
4. Snapshot target+draft realmente riusabile dal server e prompt cache.
5. Switch runtime atomico a confini di token/fase.
6. DSpark lazy/hot-cold; remoto soltanto se esiste davvero un secondo host.
7. Testa router addestrata/MTP nativo come oracle di domanda futura.
8. KV ring soltanto come esperimento di contabita' attuale.

## 9. Lavoro eseguito nella ripresa del 15 agosto sera/notte

### 9.1 DS4 locale come agente Windows

Creati nel workspace:

```text
work\start_ds4_agent_server.ps1
work\ds4_readonly_agent.py
```

Caratteristiche:

- server llama nativo Windows su porta 8110;
- strumenti read-only `read`, `search`, `git_diff` limitati al repo;
- compattazione output tool e limiti di contesto;
- nessun WSL;
- prova reale riuscita: DS4 ha chiamato strumenti e letto il diff.

Limite incontrato: la sintesi multi-turn ha saturato 10k contesto; una prova
successiva di alias/restore ha innescato un assert DSpark `GET_ROWS_Q i01` e il
server e' uscito. Connessione agente provata, audit finale pulito non ottenuto.
Non riavviare alla cieca con prompt enormi.

### 9.2 Planner globale e trasporto

Risultati principali:

| Braccio | Decode | Correttezza |
|---|---:|---|
| sync B160 | 8,39 | stesso SHA, 80/80 |
| async graph-off B160 | 9,03 | stesso SHA, zero miss |
| async graph-on B160 | 10,11 | +1,5% relativo |
| reference lunga | 11,38 | SHA lungo |
| async tail509 | 11,49 | stesso SHA/p1, 509/509 |

Il piano offline riduce miss unici 52.421 -> 37.157 (-29,12%), ma end-to-end
guadagna solo circa 1%. Semantica promossa, politica non macro.

### 9.3 Planner -> slot diretto

- Gli slot diretti si attivano soltanto dopo hot restore.
- K0 calendario Q9 lungo: 11,50 t/s, corretto, circa +1% sulla base K2
  contingente.
- Q8 burst corrompe: respinto.
- Slot diretto Q8 B160: 10,22 t/s, p1=.80583,
  SHA `EE1E260FC20863D0E63E8A6C2285CB3016B744C2AF50A4E04A57BAB8531E6E96`.
- Maschera compact: stesso 10,22; nessun recupero.

### 9.4 Profilo macro-v2

Profilo invasivo K0, calendario, graph-off:

```text
gate -> up -> GLU -> down = 1,9256 ms/layer
tre MMVQ mascherate       = 1,4816 ms/layer
contorno                  = 0,4440 ms/layer
launch MMVQ               = 3 per layer
```

Questo profilo dimostra che per il target 20 t/s il contorno intero non e'
sufficiente: servono anche meno letture/lavoro MMVQ.

### 9.5 Fusione gate+up cache-aware

File principale:

```text
D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu
```

Leva:

```text
LLAMA_DSV4_DECODE_GATE_UP_FUSO=1
```

Default off. La fusione:

- riconosce i due `MUL_MAT_ID`, clamp e SWIGLU;
- valida shape, stride, layer e memoria;
- usa gate/up dalla slab planner;
- preserva maschera e slot diretti;
- chiama la MMVQ Porto esistente;
- scrive il GLU, down invariato.

B160:

```text
reference slot direct compact: 10,22 t/s, 97,83 ms/token
gate+up fuso:                 10,37 t/s, 96,40 ms/token
delta: +1,47%, -1,43 ms/token, circa -0,033 ms/layer
p1: .80583, 83/103
planner: 7740/7740
trasporto: 78/78
SHA: identico alla reference
```

Verdetto: corretto ma troppo piccolo; niente run lungo.

### 9.6 Ceiling offline del riuso esperti tra token

`work\analyze_route_trace.py` ora riporta anche riuso intra-group. Sulla coda
lunga da 509 cicli, K0 compact:

```text
route totali:              291000
esperti unici per layer:   222644
duplicati:                  68356
riduzione peso ideale:     23,490%
gruppi con riuso:          19834 / 21887
n_tok=2:                   20,198%
n_tok=3:                   26,060%
```

Ceiling ottimistico applicato a 1,4816 ms/layer MMVQ:

```text
circa 0,348 ms/layer
```

Supera di poco la soglia 0,284 ms/layer e giustificava un microbraccio. Non e'
una previsione di guadagno reale: serializzazione, registri e scansione route
possono mangiarlo completamente.

### 9.7 Conoscenza recuperata dal vecchio runtime

Nel vecchio sorgente:

```text
C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-0731-merge\ds4_cuda.cu
```

esiste `glm_routed_moe_gateup_tok2_reuse_kernel`:

- attivo nel verify a due token quando
  `DS4_GLM_MTP_NO_MOE_TOK2` non e' impostata;
- token 0 possiede l'esperto condiviso;
- token 1 salta il duplicato;
- un helper block8 valuta due input caricando il peso una volta;
- mantiene lane assignment e albero di riduzione nativo;
- copre gate/up, non dimostra automaticamente il down;
- usa Q8_K nel vecchio runtime, non Q8_1 Porto.

Quindi l'idea non era nuova e non va attribuita a questa task. Il lavoro utile
era il port al runtime llama corrente, non un nuovo kernel aritmetico generico.

### 9.8 Port sperimentale 2-3 token: stato fallito

File:

```text
D:\llama-overlap\ggml\src\ggml-cuda\mmvq.cu
```

Leva:

```text
LLAMA_DSV4_DECODE_EXPERT_REUSE=1
```

Default off. Codice aggiunto:

- helper multi-input per IQ2_XXS/Q8_1;
- helper multi-input per Q2_K/Q8_1;
- owner della prima occorrenza slot tra 2-3 token;
- riuso gate/up, compatibile con la fusione;
- tentativo di riuso down;
- fallback invariato per leva spenta.

Build Windows Release riuscita. Il B160 usava:

```text
K0
MASSA0
FORK0
calendario Q8 all77 + drain
slot diretti
async transport blocks8
CUDA Graph attivi
GGML_SCHED_PROFILO=0
gate+up fuso=1
expert reuse=1
```

Risultato:

```text
prompt: 21,02 t/s
hot snapshot/restore: riusciti
slot diretti: attivi
primo forward decode: crash
D:\llama-overlap\ggml\src\ggml-cpu\ops.cpp:4823
GGML_ASSERT(i01 >= 0 && i01 < ne01) failed
decode t/s: NON DISPONIBILE
```

L'assert CPU e' downstream: indica che il forward precedente ha prodotto uno
stato/indice non valido. Non prova che il bug sia in GET_ROWS. Non combinare il
braccio con altre ottimizzazioni.

## 10. Artefatti esatti

Reference/fusione valida:

```text
...\work\runs\macro_v2_gate_up_fused_k0_q8_graph_b160_r1_20260815.*
```

Trace lunga per analisi riuso:

```text
...\work\runs\calendar_k0_compact_fork0_mass0_graph_trace_b1200_r1_20260815.cestrc
```

Trace e piano breve 77 cicli:

```text
...\work\runs\calendar_k0_compact_fork0_mass0_graph_trace_b160_r1_20260815.cestrc
...\work\runs\calendar_k0_compact_fork0_mass0_graph_trace_b160_all77_q8_drain_r1_20260815.portcal
```

Tentativo expert reuse fallito:

```text
...\work\runs\macro_v2_expert_reuse_gateup_k0_q8_noprobe_b160_r1_20260815.server.log
...\work\runs\macro_v2_expert_reuse_gateup_k0_q8_noprobe_b160_r1_20260815.server.out
```

Il runner non ha scritto summary/response perche' la connessione e' stata
interrotta dal crash del server.

## 11. Build Windows nativa

Da PowerShell, mai WSL:

```powershell
& cmd.exe /d /c 'call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1 && "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build "D:\llama-overlap\build" --target llama-server --parallel 8'
```

Ultima build: exit 0. Warning preesistenti su float fuori range e `tmp_gate`
non usato in istanziazioni senza fusion; nessun errore di link.

## 12. Comando del B fallito, ricostruibile

Usare il runner, non lanciare a mano un server con ambiente incompleto:

```powershell
& 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' `
  -Tag 'macro_v2_expert_reuse_gateup_k0_q8_noprobe_b160_r1_20260815' `
  -MaxTokens 160 -Repetitions 1 `
  -Extra 'LLAMA_CACHE_ESPERTI_MASSA=0;LLAMA_CACHE_ESPERTI_FORK=0;LLAMA_OVERLAP_K=0;LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\calendar_k0_compact_fork0_mass0_graph_trace_b160_r1_20260815.cestrc;LLAMA_CACHE_ESPERTI_CALENDARIO_CICLI=77;LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\calendar_k0_compact_fork0_mass0_graph_trace_b160_all77_q8_drain_r1_20260815.portcal;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=1;LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;LLAMA_DSV4_DECODE_GATE_UP_FUSO=1;LLAMA_DSV4_DECODE_EXPERT_REUSE=1;GGML_CUDA_DISABLE_GRAPHS=0;GGML_SCHED_PROFILO=0'
```

Non rilanciare identico: e' registrato come crash.

## 13. Roadmap operativa dalla prossima task

### Fase A - rendere sicuro il ramo corrente

1. Verificare nessun processo `llama-server`/`llama-cli` attivo.
2. Non abilitare `LLAMA_DSV4_DECODE_EXPERT_REUSE` nel banco normale.
3. Separare il controllo expert reuse in modalita' diagnostiche:
   `gate/up IQ2_XXS only`, `down Q2_K only`, `both`.
4. Non usare subito la generazione completa. Costruire una fixture di un solo
   MMID/layer con input, ids, mask e slab catturati dalla reference, poi
   confrontare output device byte/float prima del router.
5. Per gate/up partire dal port piu' conservativo del vecchio kernel:
   **solo n_tok=2**, stesso ordine, nessuna estensione n_tok=3 e nessun down.
6. Accettare il braccio soltanto se output identico o entro il contratto
   numerico gia' ammesso, senza NaN/Inf e senza route invalidi.
7. Soltanto dopo, aggiungere n_tok=3; il down e' un braccio separato.

Questo ordine evita di diagnosticare una corruzione IQ2 dal successivo assert
Q2/GET_ROWS, o viceversa.

### Fase B - microcancello prestazionale pulito

1. A/B nello stesso processo/binario, profilo e probe spenti.
2. Stesso continuation, seed, temperatura, piano e output.
3. Primo B20 solo per correttezza; poi B160.
4. Promozione solo con:
   - SHA/output coerente;
   - p1 invariato;
   - planner e trasporto completamente consumati;
   - zero divergenze;
   - almeno circa 5% sul B160. Un +1% non giustifica B lungo.
5. B1200 e tre repliche soltanto se il B160 supera il cancello.

### Fase C - composizione con la SOTA K2

Il planner K0 e' utile per isolare la residenza, ma la SOTA e' K2. Qualunque
macro guadagno deve essere composto con la corsia CPU senza reintrodurre un
join per layer. Possibili forme, da verificare e non assumere:

- riuso resident expert tra token sul ramo GPU, CPU K2 invariata;
- CPU esegue soltanto rescue deadline gia' persa, non due route fisse se il
  planner le ha rese disponibili in tempo;
- completamento CPU e GPU raccolto una volta per macro-fase/ciclo, non 43 volte.

Non implementare questa composizione prima che il kernel resident reuse sia
corretto e materialmente piu' veloce da solo.

### Fase D - hot switch e snapshot server

Portare le leve da env launch a un control block atomico al token boundary:

- planner on/off;
- K rescue e deadline budget;
- transport budget/quanta;
- DSpark hot/cold;
- profilo/probe soltanto su finestra esplicita.

Integrare snapshot target + DSpark + manifest nel prompt cache server. Il
checkpoint same-process `-cms32` aveva ridotto un follow-up da 288 s a 2,7 s;
`/slots` da solo non evita il prefill.

## 14. Misure e correttezza obbligatorie

Per ogni candidato:

- t/s e ms/token;
- p1 e accepted/generated;
- output e SHA;
- finish_reason e lunghezza;
- planner posizione/atteso;
- trasporto cicli/atteso;
- copie, no-op, guasti, release max;
- replay e divergenze;
- invalid ids, NaN/Inf, assert;
- CUDA Graph reuse;
- profilo/probe esplicitamente dichiarati on/off;
- clock/regime, o almeno A/B ravvicinato nello stesso processo.

Un crash prima di `eval time` non e' 0 t/s: e' **nessuna misura**.

## 15. File modificati o creati da questa ripresa

Runtime principali:

```text
D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cu
D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cuh
D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu
D:\llama-overlap\ggml\src\ggml-cuda\mmvq.cu
D:\llama-overlap\ggml\src\ggml-cuda\mmvq.cuh
```

Il worktree contiene molte altre modifiche anteriori e dell'utente. Non
attribuirle automaticamente a questa ripresa.

Workspace:

```text
work\run_porto_hot.ps1
work\analyze_route_trace.py
work\start_ds4_agent_server.ps1
work\ds4_readonly_agent.py
work\runs\...
```

Documenti aggiornati:

```text
LEDGER_15_AGOSTO.md
HANDOFF_NUOVA_CHAT_15_AGOSTO_NOTTE.md
```

## 16. Stato git e disciplina

`git status --short` mostra decine di file modificati e numerosi untracked.
Il diff complessivo supera 7.500 inserimenti e include lavoro non isolabile con
certezza per autore. Regole:

- niente `git reset --hard`;
- niente `git checkout --` su file condivisi;
- niente clean ricorsivo;
- niente commit monolitico automatico;
- prima di un commit, selezionare hunk e chiedere approvazione;
- nessun push.

## 17. Decisione finale della task

Risultati positivi reali:

- audit storico consolidato;
- planner globale e trasporto persistente corretti;
- snapshot caldo target+draft+slab funzionante nel banco;
- slot diretti corretti;
- fusione gate+up corretta ma piccola;
- quantificato un riuso route del 23,49%;
- recuperato il precedente tok2 reuse dal vecchio runtime;
- DS4 locale collegato come agente Windows read-only.

Risultato negativo da non mascherare:

- il primo port 2-3 token gate/up+down corrompe il primo decode e non produce
  alcun t/s valido.

Conclusione: **20 t/s non e' raggiunto**. Il prossimo lavoro non deve cercare
un'altra politica di cache. Deve prima rendere corretto e misurabile il riuso
resident expert a due token, separando gate/up dal down; se il microcancello non
produce almeno un guadagno materiale, chiudere anche questa famiglia e tornare
al macro scheduling/ciclo senza inventare varianti locali.

---

## 18. Aggiornamento autoritativo - 16 agosto 2026

Questa sezione **sostituisce** le conclusioni operative delle sezioni 4, 9, 12,
13 e 17 quando sono in conflitto. E' stata scritta dopo nuovi B160/B1200 sul
binario corrente, confrontati direttamente con gli artefatti grezzi del record
del 14 agosto conservati in `D:\ds4_work\llama_run`.

### 18.1 Esito esecutivo reale

- 20 t/s: **non raggiunto**.
- 30 t/s: nessun ceiling credibile nel runtime/hardware corrente.
- record storico: **16,0733 t/s**, ancora valido come misura passata.
- baseline operativa corrente, stesso testo del record: **10,54 t/s**.
- regressione da recuperare prima di ottimizzare: **5,53 t/s**, cioe' il tempo
  per token e' passato da 62,34 a 94,89 ms (+52,2%).
- causa primaria localizzata: tempo host dentro `graph_compute_async` del
  backend non-CPU, etichetta profiler `calc altri`.
- nessun commit, push, reset o WSL.

### 18.2 Il primo crash expert-reuse era contaminato dal banco

Il comando riportato nella vecchia sezione 12 abilitava:

```text
LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=1
```

ma ometteva:

```text
LLAMA_CACHE_ESPERTI_CALENDARIO_K0=1
```

Questo e' un errore semantico: la slab veniva indirizzata per slot, mentre il
grafo continuava a passare expert-id logici. Il crash GET_ROWS e i primi B20
gibberish non sono quindi prove contro il macro-kernel. Non riusarli come
verdetto. Il cancello valido deve contenere **entrambi** `CALENDARIO_K0=1` e
`SLOT_DIRETTI=1`.

Altro chiarimento sulle variabili:

- `LLAMA_CACHE_ESPERTI_TRACCIA=<file>` registra una trace;
- `LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=<file>` la usa in replay;
- una cattura testimone K0 richiede anche `CALENDARIO_K0=1`.

### 18.3 Trace e piano ricostruiti dal codegen corrente

Trace valida:

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\macro_v2_current_codegen_calendar_k0_trace_b160_r1_20260815.cestrc
```

Proprieta':

```text
517.412 byte
8.084 record
81 cicli totali
SHA256 116187C00501D4911E2BC8AC889093F83E3A6C834712C7A79EF134BD941B9780
byte-identica alla trace storica B160
```

Piano tail77 Q8 + drain:

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\macro_v2_current_codegen_calendar_k0_tail77_q8_drain_b160_r1_20260815.portcal
```

Proprieta':

```text
244.088 byte
78 cicli
20.260 voci
release massima 473
SHA256 D909D1EB31090DA9BCA4984ACA3798399B9B4182EA1521A43E115810D9886DBC
byte-identico al piano storico
```

Comando di generazione:

```powershell
python C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\analyze_route_trace.py `
  <trace> --tail-cycles 77 --lane k0 --copy-quanta 8 `
  --emit-layer-plan <piano> --drain-cycle
```

### 18.4 Macro-kernel: cosa e' provato e cosa no

La leva sperimentale resta default-off:

```text
LLAMA_DSV4_DECODE_EXPERT_REUSE=0
```

Modalita' oggi presenti in `mmvq.cu`:

| valore | significato | stato |
|---:|---|---|
| 1 | IQ2 gate/up multi-input, deduplica globale | errato |
| 2 | Q2 down multi-input | non promosso |
| 3 | gate/up + down | non usare |
| 4 | IQ2 gate/up, dot Porto nativo, owner globale | errato |
| 8 | Q2 down nativo diagnostico | non promosso |
| 16 | IQ2 gate/up senza deduplica, 8 warp, dot nativo | bit-esatto |
| 32 | Q2 down senza deduplica | non misurato |
| 64 | IQ2 gate/up, deduplica stessa corsia, dot nativo | errato |
| 128 | IQ2 gate/up, deduplica stessa corsia, dot multi-input | errato |

`LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=1` azzera l'output fuso prima del
kernel e serve soltanto a rendere visibili colonne non scritte; non e' una leva
di produzione.

Risultati validi col banco K0 corretto:

| tag | t/s | p1 / SHA | esito |
|---|---:|---|---|
| `macro_v2_gateup_no_dedup_native_zero_diag_k0_q8_b160_r1_20260816` | **10,38** | p1=.80583, SHA `EE1E260F...` | 160 token, bit-identico, planner 7.740/7.740, trasporto 78/78 |
| `macro_v2_reuse_gateup_only_valid_calendar_k0_q8_b160_r1_20260815` | 7,71 | p1=.16197, SHA errato | dedup globale errata |
| `macro_v2_reuse_gateup_owner_native_valid_calendar_k0_q8_b160_r1_20260815` | 7,39 | stesso output errato | il helper multi non e' la causa primaria |
| `macro_v2_reuse_gateup_ds4_owner_native_valid_k0_q8_b160_r1_20260815` | 7,71 | stesso output errato | topologia 8 warp non cura |
| `macro_v2_reuse_gateup_logical_owner_native_valid_k0_q8_b160_r1_20260815` | 5,50 | p1=.00417 | logical-id ricostruito dal grafo non sicuro |
| `macro_v2_reuse_logical_owner_native_zero_dst_diag_k0_q8_b160_r1_20260815` | 5,97 | p1=.03175 | zero-dst sposta la divergenza, prova colonne stale/non scritte |
| `macro_v2_gateup_same_channel_native_zero_k0_q8_b160_r1_20260816` | 6,96 | acceptance .13014, SHA log `e7312b...` | divergenza ciclo 19 |
| `macro_v2_gateup_same_channel_multi_zero_k0_q8_b160_r1_20260816` | 7,18 | stessa acceptance e stesso SHA errato | dot multi/nativo equivalenti nel fallimento |

Conclusione stretta:

1. griglia DS4, indirizzo slot, fusione gate/up e dot Porto sono corretti;
2. l'unico difetto e' l'adozione di una colonna da parte di un blocco diverso;
3. perfino la deduplica stessa-corsia fallisce, quindi non e' solo una
   permutazione cross-channel;
4. il sottoinsieme stessa-corsia vale appena 3.240 duplicati su 41.987 route
   tail77, **7,7167%**: anche corretto, il ceiling e' troppo piccolo per 20;
5. non investire altri B lunghi su questa microfamiglia finche' la baseline da
   16 non e' recuperata.

Statistiche offline tail77:

```text
route 41.987
unici (ciclo,layer,expert) 32.397
duplicati globali 9.590 = 22,840%
duplicati stessa corsia 3.240 = 7,7167%
n_tok=2: 21.737 route, 4.428 duplicati globali, 1.432 stessa corsia
n_tok=3: 19.734 route, 5.162 duplicati globali, 1.808 stessa corsia
```

### 18.5 Riproduzione del record: banco e risultato

Artefatto storico usato come autorita':

```text
D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.server.log
D:\ds4_work\llama_run\mass2_copyall_stablelane_t473_d12_b1.output.html
```

Record B1:

```text
16,04 t/s
74.804,71 ms / 1.200 token
p1 .90025 = 713/792
mean len 2,47
hit target 77,9%
47.906 miss/copie
SHA file 4FDCFADFBFE0D009C7FA826EA8AFE25A6707BF6D3A75296F3E0E50C376ADC65D
```

Il runner nuovo aveva `porto_hot_snapshot=true`. Con quello:

```text
tag sota_k2_current_codegen_b1200_r1_20260816
9,87 t/s
121.5 s circa di eval
p1 .85316 = 674/790
output diverso
```

Senza snapshot:

```text
tag sota_k2_no_hot_snapshot_b1200_r1_20260816
10,54 t/s
113.871,83 ms / 1.200 token
p1 .90025 = 713/792
mean len 2,47
output normalizzato byte-per-byte identico allo storico
stessi 216.737 accessi, 168.831 hit, 47.906 miss/copie
stessi 486 cicli DSpark
```

La diversa SHA del file nuovo (`3BAC3069...`) dipende solo da BOM/newline ed
estensione `.txt`; dopo rimozione CR e trim finale i 3.571 caratteri sono
identici con confronto case-sensitive.

**Verdetto snapshot:** l'infrastruttura cattura/ripristina target, draft e slab,
ma non e' neutra sul banco end-to-end: cambia traiettoria e costa circa 7,1%
rispetto allo stesso binario senza snapshot. Non usarla per certificare t/s
finche' non conserva output/p1 del percorso fresh.

### 18.6 Profilo che localizza la regressione

Il run storico aveva `GGML_SCHED_PROFILO=1`. E' stato ripetuto sul binario
corrente, snapshot off, ottenendo 10,53 t/s e lo stesso testo. La sonda ha costo
irrilevante qui: 10,54 off contro 10,53 on.

Confronto a 1.951 grafi e 35,6 split/grafo:

| componente per grafo | storico 16,04 | corrente 10,53 | delta |
|---|---:|---:|---:|
| ingressi | 3,692 ms | 6,022 ms | +2,330 |
| di cui sync | 2,741 ms | 5,120 ms | +2,379 |
| calc CPU | 1,358 ms | 1,655 ms | +0,297 |
| **calc altri** | **4,080 ms** | **22,318 ms** | **+18,238** |
| dispatch | 0,193 ms | 0,308 ms | +0,115 |
| sched-sync | 0,133 ms | 0,238 ms | +0,105 |

`calc altri` misura il tempo host dentro:

```cpp
ggml_backend_graph_compute_async(split_backend, &split->graph)
```

per backend non-CPU. Il delta 18,238 ms * 1.951 grafi vale circa **35,58 s**,
quasi tutta la regressione totale di 39,19 s.

Worker, per lavoro (20.941 lavori):

| voce | storico | corrente |
|---|---:|---:|
| evento | .878 ms | .772 ms |
| calcolo CPU | 1,772 ms | 1,885 ms |
| attesa lavoro | 1,063 ms | 2,936 ms |
| join | 2,631 ms | 2,495 ms |

Il join non e' peggiorato. La corsia CPU cresce poco. La regressione primaria
e' prima/dentro l'accodamento CUDA graph, non nel calcolo CPU MoE.

DSpark e' anch'esso piu' lento:

```text
storico: gen 13,47 + PROC .64 = 14,12 ms/chiamata
corrente: gen 20,51 + PROC 1,02 = 21,54 ms/chiamata
```

Questo spiega circa 3,4 s, non i 35,6 s del target.

### 18.7 Ipotesi falsificate durante la localizzazione

1. **Solo banco corto/acceptance:** falso; il B1200 senza snapshot ha p1 e testo
   identici ma resta a 10,54.
2. **Solo profiler:** falso nel banco corrente; on/off differiscono .01 t/s.
3. **Barriere trace/calendario dentro `kern_partiziona`:** separate con
   template fast/strumentato; 9,84 contro 9,87 nello snapshot-on, nessun
   recupero materiale.
4. **Scansione semantica calendario nel backend anche da spento:** ora gated da
   `ggml_cuda_cache_esperti_calendario_backend_attivo`; `calc altri` 22,318 ->
   22,014 ms/grafo, quindi neutro entro varianza e non causa primaria.
5. **Clock come spiegazione unica:** non sufficiente; stessi contatori e profilo
   host localizzano un costo software per grafo.

I due fix 3-4 sono corretti per disciplina del fast path ma non vanno venduti
come prestazione. Restano default-safe e il planner sperimentale continua a
usare l'istanza strumentata.

### 18.8 Codice modificato in questa ripresa

`D:\llama-overlap\ggml\src\ggml-cuda\mmvq.cu`:

- macro-kernel gate/up multi-input e diagnostiche;
- modalita' 1/2/4/8/16/32/64/128;
- variante no-dedup bit-esatta;
- variante same-channel falsificata;
- `EXPERT_REUSE_ZERO_DST` diagnostica;
- tentativo di ricostruire logical-id dal testimone K0, non promosso.

`D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cu/.cuh`:

- `kern_partiziona<planner_trace>` con istanze compile-time separate;
- getter O(1) per escludere la scansione calendario dal backend fast path.

`D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu`:

- scansione dei confini calendario eseguita solo se async o slot-diretti attivi.

`D:\llama-overlap\ggml\src\ggml-cpu\ops.cpp`:

- dettaglio degli ID GET_ROWS stampato solo prima dell'assert invalid-id.

Runner:

```text
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1
```

Ora accetta `-PortoHotSnapshot 0|1`; default resta 1 per compatibilita' con i
test planner, ma la riproduzione SOTA richiede 0.

### 18.9 Comando corretto per la baseline operativa

```powershell
& 'C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1' `
  -Tag 'sota_k2_no_hot_snapshot_b1200_r1_20260816' `
  -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 `
  -Extra 'LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;GGML_CUDA_DISABLE_GRAPHS=0;GGML_SCHED_PROFILO=0'
```

Risultato atteso sul binario corrente: circa 10,54 t/s, p1 .90025, 1.200
token e testo normalizzato identico al B1 storico.

### 18.10 Roadmap obbligatoria dalla prossima ripresa

#### P0 - recuperare 16,0733 prima di cercare 20

1. Non cambiare output, p1, cache o speculazione: usare sempre B1200 snapshot
   off e confronto testo normalizzato col B1 storico.
2. Bisectare **solo** il tempo host di `ggml_cuda_graph_compute_one` / replay
   CUDA, non cache policy, K o prefetch.
3. Aggiungere timing gerarchico temporaneo dentro `ggml_cuda_graph_compute_one`
   su una finestra breve: lookup graph key, update/capture, launch e qualunque
   scansione/copia host. Togliere la sonda dal banco finale.
4. Confrontare il sorgente/build effettivo precedente al record con quello
   corrente in un worktree Windows separato; non resettare `D:\llama-overlap`.
   Il build-info storico stampa `build 95 (963a2cfca)`, quello corrente
   `build 10093 (3014d3756)`, ma il build-info CMake puo' essere stantio: usare
   il bisect dei file e i profili, non il numero da solo.
5. Cancello di recupero: `calc altri <= 5 ms/grafo`, testo identico, p1 .90025,
   47.906 copie e almeno 15,8 t/s. Solo allora tre repliche.

#### P1 - percorso da 16 a 20

Budget invariato:

```text
16,0733 t/s = 62,214 ms/token
20 t/s = 50,000 ms/token
servono 12,214 ms/token = circa .284 ms/layer
```

Ordine di lavoro:

1. macro-kernel v2 attorno alla MMQ/MMVQ Porto, senza riscrivere la GEMM;
2. owner/mate map esplicita prodotta dal route kernel o buffer dedicato, non
   inferita ad hoc dentro ogni MMVQ;
3. trasporto persistente multi-layer e planner globale target+draft;
4. CPU soltanto rescue di deadline e raccolta a confine macro, mai 43 join;
5. snapshot hot riaperto solo dopo parita' fresh/snapshot sullo stesso testo.

Il riuso teorico globale 22,84% supera appena il budget, ma il sottoinsieme
corretto same-channel e' solo 7,72%. Non promettere 20 col solo dedup.

#### P2 - 30 t/s

```text
30 t/s = 33,333 ms/token
dal record servono 28,881 ms/token
```

Richiede quasi dimezzare il record. Con ceiling DMA-only 19,453 t/s non e'
raggiungibile tramite solo trasporto/residenza; serve un cambio macro di
compute, algoritmo, numerica o hardware. Non usarlo come promessa operativa.

### 18.11 Stato alla consegna

- nessun `llama-server` lasciato intenzionalmente attivo;
- build Windows Release riuscita;
- nessun commit/push;
- worktree molto dirty, con modifiche utente e storiche da preservare;
- ultimo run: `sota_k2_calendar_scan_gated_b1200_r1_20260816`, 10,53 t/s,
  p1=.90025, testo storico identico;
- prossimo passo unico: profilare/bisectare `ggml_cuda_graph_compute_one`, non
  riaprire politiche di cache o il dedup same-channel.
