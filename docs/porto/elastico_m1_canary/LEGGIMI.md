# Elastico M1 — il canary del prefill dopo uno sfratto RAM (21 settembre 2026)

**Conclusione.** Il difetto è riprodotto su richiesta (`20260921_130752_m1_originale`: tre prompt su tre
→ 500 «Compute error», con 12 GiB di RAM di nuovo liberi). Non è un problema di soglie: nel runtime
**non esiste nessun percorso che riporti le pagine in RAM prima di un prefill**, e il decode da solo non
riesce a riportare `missing` a zero. Basta una terna sfrattata e il server non accetta più nessun prompt
fino al riavvio. Codex lo elenca fra i limiti noti del prototipo (`qwen_ram_decode_opt_20260920/README.md`,
«A later multi-token prefill is rejected while expert pages are absent»). Correzione proposta: ripristino
dal GGUF di tutte le terne assenti in testa a `decode()` quando il batch ha più di 3 token (sotto).
**Stato: diagnosi e prova fatte; correzione NON implementata, in attesa di approvazione.**

## Dove e perché

| cosa | dove (sorgente di Codex, sola lettura) |
|---|---|
| il canary | `src/llama-context.cpp:2042-2051` (overlay M1: `:2046-2055`): `n_tokens > 3` + `ggml_backend_cuda_ram_has_missing()` → `return -3` |
| il flag | `ggml/src/ggml-cuda/moe-ram-store.cuh:131,735`: atomico, vero se `missing_groups != 0` |
| lo sfratto | `moe-ram-store.cuh:496-559` `evict_locked`: `MEM_DECOMMIT` delle pagine interne + bordi azzerati; chiamato **solo** da `ggml_cuda_ram_prepare` (`:645`), cioè dentro il decode |
| il ripristino | `moe-ram-store.cuh:661-701`: solo per gli esperti instradati **e** mancanti nella cache VRAM, in decode |
| chi legge in prefill | `ggml/src/ggml-backend.cpp:2010-2021` `copy_experts` e `:1792` `qwen_prefetch_eval::enqueue` |

**Perché il prefill non può girare con pagine assenti.** Sopra le 3 righe il grafo è quello di serie
(«prefill graph unchanged», `llama-moecache.cpp:484`): `MUL_MAT_ID` sui tensori sorgente, che per gli 8
strati gestiti stanno nel buffer `CUDA_RamStore` (`VirtualAlloc` paginabile, `is_host = true`). Lo
scheduler li porta in VRAM leggendo **memoria grezza**: `copy_experts` fa `set_tensor_async` da
`input->data + expert_offset` (più 512 byte di coda dentro l'esperto successivo), e con ubatch ≥ 512 token
lo staging `QWEN_PREFETCH_EXPERTS` copia il **tensore intero** in un colpo. Nessuno dei due conosce
`resident[]`: su una pagina decommittata è una violazione d'accesso (il server cade), sui bordi azzerati
sono pesi sbagliati in silenzio. Il canary è quindi una guardia giusta; manca il recupero.

**Perché non si sblocca da solo.** (1) Il ripristino vive solo nel decode, ma a un server appena avviato
o fra un turno e l'altro ogni richiesta comincia con un prefill, che viene rifiutato: al decode non si
arriva più. (2) Anche decodificando, tornano solo gli esperti instradati e mancanti in VRAM, e dopo uno
sfratto `resident_ceiling = resident_bytes`: ogni ripristino passa da `make_room_locked` e ne sfratta un
altro di pari peso, quindi `missing` resta costante finché il tetto non viene tolto (15 s di fila sopra
2,5 GiB, e il sensore gira solo in decode). Nella prova: 4112 sfratti, 16 ripristini, `missing` fermo a 4096.

**Come ci si arriva in pratica.** Nel caso del 21/9 (`20260921_122442_sonda_m1`) lo sfratto è avvenuto
**nel warmup**: fra la prima e la nona chiamata di staging il caricamento dell'mmproj ha portato il
disponibile a 1,88 GiB, `emergency=1` (sotto i 5 s della soglia morbida: è scattato il ramo d'emergenza,
notifica di memoria bassa o commit), 158 terne via (294 MiB), e la prima richiesta ha trovato il canary.
L'altro caso è uno sfratto durante un decode qualsiasi: il turno successivo della conversazione muore.

**Buco collegato (non provato).** Il canary copre solo `n_tokens > 3`. Se la cache elastica è a 0 slot
(`resize(0, "compute_failure")` o budget VRAM insufficiente) anche il decode usa il grafo di serie e
`copy_experts` legge le stesse pagine grezze: lì non c'è nessuna guardia.

## La prova

`prova_canary_prefill.py --run` (server isolato su 127.0.0.1:8113 via `qwen_gateway/server_locale.py`,
configurazione `reference_gsq_64.json` + env elastiche; solo `/v1/chat/completions`):

1. controllo: prompt corto (~60 token) e lungo (~2k token, oltre la soglia dei 512 dello staging a tensore
   intero), due volte ciascuno, greedy e `cache_prompt: false`: l'impronta del testo deve ripetersi;
2. pressione: durante un decode in streaming da 768 token un processo di servizio alloca e blocca
   (`VirtualLock`) RAM finché il disponibile scende a `--target-mib` (1536), e continua a riempire quello
   che gli sfratti liberano; rilascia a fine decode, alla morte del genitore o dopo `--max-secondi`;
3. dopo lo sfratto: gli stessi prompt. SUPERATA = 200 **e** impronte uguali al controllo (le pagine
   ripristinate sono quelle giuste); DIFETTO RIPRODOTTO = 500 col canary; INCONCLUSIVA = nessuno sfratto.

Lancio staccato, esito su file (`STATO.txt` → `FINE ok: <verdetto>`, `rapporto.json`, `runner.log`, `logs\`):

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine='"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" -B "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\elastico_m1_canary\prova_canary_prefill.py" --run'
  CurrentDirectory='D:\ds4_work\elastico_m1_canary_run' }
```

`--runtime <llama-server.exe>` prova altri binari con la stessa configurazione (serve per la correzione);
`--senza-pressione` fa solo il controllo (caso «sfratto nel warmup» con poca RAM all'avvio). Il server si
chiude con CTRL_BREAK; la prova rifiuta di partire se c'è già un `llama-server.exe` vivo e non tocca mai la 8100.

### Esito sui binari M1 attuali (`llama.dll` b21096d1…, `ggml-cuda.dll` 0ab93b18…, gli stessi di `D:\ds4_work\bin_elastico_m1`)

| fase | esito |
|---|---|
| a server pronto (79 GB liberi prima del caricamento) | `missing` 0, disponibile 4,2 GiB |
| controllo ×4 | 200; impronte ripetute (`25bcfc3488db` corto, `1235d4b1aad7` lungo) |
| decode sotto pressione | 200, 768 token; disponibile minimo 1355 MiB; `emergency=1`; **4112 sfratti, 16 ripristini, `missing` 4096 = tutte le terne degli 8 strati**, residente 0 |
| dopo il rilascio (12 GiB disponibili) | corto, lungo, corto-bis: **500 «Compute error»**, una riga di canary ciascuno |

Corsa: `D:\ds4_work\elastico_m1_canary_run\20260921_130752_m1_originale`.

## Correzione proposta (da approvare)

**A — ripristino prima del prefill (consigliata).**
- `moe-ram-store.cuh`: nuova `ggml_cuda_ram_restore_all()`, sotto il mutex del registro: per ogni terna
  assente `commit` delle tre banche, `read_locked` dal GGUF direttamente a destinazione, `publish_warm`;
  su errore rollback della terna (come fa già `prepare`) e ritorno negativo. A fine giro
  `resident_ceiling = resident_bytes`, altrimenti il primo ripristino in decode risfratta tutto.
  Ammissione: conta il **commit** (limite duro), non il pavimento dei 2 GiB — al prefill quelle pagine
  servono tutte comunque; sotto il pavimento si scrive un avviso e la politica di sfratto riparte al decode.
- `ggml-cuda.cu`: esportazione `ggml_backend_cuda_ram_restore_all` accanto a `ram_has_missing`.
- `llama-context.cpp` (overlay M1): al posto del rifiuto secco, `if (missing()) restore_all()`; il
  `return -3` resta solo se il ripristino fallisce. Stessa chiamata anche con `n_tokens <= 3` quando la
  capacità della cache è 0 (il buco collegato).
- Percorso normale: con `missing == 0` resta una lettura atomica, come oggi — nessuna regressione possibile
  sul prefill a regime. Costo sotto pressione: al peggio 5,8 GiB riletti da SSD prima del prefill (~2-3 s).

**B — prefill che legge da SSD senza ricommittare (scartata per ora).** Tocca lo scheduler
(`ggml-backend.cpp`, `ggml-base.dll`) e serve un aggancio fra DLL verso il deposito; lo staging a tensore
intero va spezzato in segmenti residenti/assenti; ogni ubatch di ogni prefill rilegge da SSD gli assenti
(costo fisso ~3 s per ubatch già oggi). Unico vantaggio: la RAM non ricresce durante il prefill.

**Build e collaudo**, in una cartella nuova (`D:\ds4_work\elastico_m2`), laboratorio di Codex in sola lettura:
overlay di `ggml/src/ggml-cuda/` + `llama-context.cpp`, ricompilazione dei soli due oggetti coi flag di
`compile_commands.json` e ricollegamento di `ggml-cuda.dll` e `llama.dll` dagli oggetti O2 con SHA prima/dopo
(lo schema di `build_context_overlay.py`); binari in `runtime-m2`, mai sopra `bin_elastico_m1`. Poi:
(1) caso «restore_all» nel test d'integrazione del deposito (decommit vero, contenuto identico al GGUF);
(2) questa prova con `--runtime ...\runtime-m2\llama-server.exe` → attesa SUPERATA con le stesse impronte;
(3) `banco_followup.py --livelli 1` su m2 contro i numeri di m1 per il prefill a regime.
