# Come DeepSeek Harness tiene valida la cache del prompt (21 settembre 2026)

Fonti: codice di DSH Desktop 0.9.0 (`…\DSH Desktop\resources\app\node_modules\@deepseek-ai\*` e
`@earendil-works\pi-ai`), 108 log di sessione dell'utente, log di llama-server di produzione del 19-20/9.
I numeri di riga sono quelli della versione installata.

## Il dato

`analizza_cache_server.py` sui log di produzione: con DSH, 319 richieste, prompt medio 75-90k token,
**98,3% dei token ripresi dalla cache**; prefill da zero solo al cambio di conversazione (6 volte, stacco al
token 3); gli altri stacchi sono sempre in coda e ripartono da un checkpoint a pochi k dalla fine. Con
Claude Code, prima della correzione del gateway: 41%.

## Cosa NON fa

Nessun parametro specifico di llama.cpp: niente `cache_prompt`, `id_slot`, `n_keep`, niente `/slots`.
`prompt_cache_key` verso localhost resta `undefined`. Manda solo `x-deepseek-harness-session-id`, che il
server ignora. Si affida per intero al riuso automatico del prefisso comune.

«Checkpoint» in DSH non riguarda la KV: è (a) il flush del log prima di parlare col modello
(`dsh-session-checkpoint-policy`), (b) il riassunto di compattazione (`<compacted-summary>`), (c) il fork,
che tronca il log evento per evento e quindi dà una cronologia figlia byte-identica al prefisso del padre.

## Le scelte che tengono fermo il prefisso

1. **Il contenuto dinamico non entra mai nel system prompt.** Due registri: `section()` statico e
   `context()` dinamico (`dsh-system-prompt\lib\index.js`). Il dinamico diventa un messaggio utente appeso:
   «Current runtime context. This snapshot supersedes earlier runtime-context snapshots.» — il vecchio resta
   dov'è.
2. **Niente data/ora, stato git, elenco file nel prompt** (il plugin `dsh-time-context` esiste ma non è
   caricato; zero occorrenze in 108 sessioni).
3. **Cronologia append-only imposta dal tipo**: ogni evento dichiara `surfaceOp: "append"` o un `replace`
   validato; il nodo 0 (system) è protetto da un'asserzione (`dsh-session\lib\index.js:266-281, 373-383`).
   In 108 sessioni i `replace` sono 442 su `tool/result`, 24 su `user/message`, 3 su `system/message`.
4. **Dedup**: contesto di runtime e istruzioni di progetto si riemettono solo se cambiati (~1,4 snapshot
   a sessione).
5. **Tool canonicalizzati**: ordine lessicografico indipendente dal locale, confronto con l'header
   registrato; 6 cambi effettivi su 108 sessioni. Stanno nel campo `tools`, che il template rende subito.
6. **Ragionamento rimandato identico** sullo stesso campo da cui è arrivato (`reasoning_content`) +
   `preserve_thinking: true` nei `chat_template_kwargs`: il prefisso dopo ogni risposta coincide con ciò che
   il server ha generato.
7. **Compattazione in una sola transazione** all'80% della finestra, che risparmia il system; la chiamata
   di riassunto è costruita come prefisso letterale dell'ultima richiesta (stesso system, stessi tool,
   istruzione solo in coda: `dsh-compaction-basic\lib\index.js:213-219`).

## Dove DSH stesso rompe il prefisso

- compattazione (26 volte in 108 sessioni: inevitabile, ammortizzata);
- **potatura dei tool result senza compattazione** (`pruneSession` riscrive risultati a metà storia; se poi
  si scende sotto soglia il riassunto non parte: 4 sessioni su 108);
- tool che cambiano a sessione avviata (MCP che si connette tardi) → `startsSeries` → `replace` sul nodo 0;
- ripresa di sessione con composizione dei tool cambiata; `replayState` non utilizzabile.

## Confronto con Claude Code, visto sui corpi veri

Claude Code è append-only quanto DSH: fra un turno e l'altro system, tool e messaggi precedenti restano
identici. L'unica cosa che cambiava era il **blocco di attribuzione** in testa al system
(`x-anthropic-billing-header: …; cch=…; cc_prev_req=…; cc_prompt_id=…`): cambia a ogni turno, il fork ne
normalizza solo `cch`, e siccome il template di Qwen rende prima i tool (~26,5k token) e poi il system, lo
stacco cadeva al token 26.541 → 50k token rifatti a ogni turno. `rotta_locale.pulisci()` ora lo toglie.
In più Claude Code a fine turno manda una richiesta laterale in streaming (stessa conversazione + un
messaggio in coda) e molto traffico Haiku di sfondo non in streaming, che resta sul vero Haiku.

## Come muoversi

1. Rimisurare la chat su Haiku col gateway corretto: l'attesa è un riuso alla DSH.
2. Per Qwen dentro Claude Code puntare sui subagent con pochi tool (prompt di qualche migliaio di token).
3. Lato server, checkpoint più fitti durante il prefill (oggi stanno solo in fondo al prompt) limiterebbero
   il danno di qualunque stacco a metà, anche quelli di DSH (potatura, cambio dei tool).
