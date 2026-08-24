# RIFERIMENTO — Documentazione ufficiale API DeepSeek V4 (distillato per la campagna DS4)

Fonte: https://api-docs.deepseek.com/guides/ — letta il 24/8/2026 sera, su indicazione dell'utente
(«molte cose sono scritte in queste pagine»). Ogni voce: il fatto DOCUMENTATO lato API, poi *perché
ci riguarda* sul serving locale. Attenzione al confine: queste sono semantiche dell'ENDPOINT
ufficiale — dicono per cosa il modello è addestrato/servito da loro, NON cosa fa llama.cpp da noi
(dove sampling, template e cache li decidiamo noi).

## 1. Identità del modello — il nostro DS4-0731 È `deepseek-v4-flash`
- Modelli correnti: **DeepSeek-V4-Flash-0731** (`deepseek-v4-flash`), DeepSeek-V4-Pro-0813
  (`deepseek-v4-pro`), più una flash-vision sperimentale.
- Specifiche ufficiali: **contesto 1M token, output massimo 384K**, per tutti.
- *Perché ci riguarda*: il nostro `DS4-0731-IQ2XXS` è la Flash-0731; il tetto a 150k del banco è un
  limite NOSTRO di VRAM/KV, non del modello. Ogni discorso su «tassa del contesto lungo»
  (TASSA_ATTENZIONE_LUNGO) ha davanti una pista ufficiale che arriva a 1M.

## 2. Thinking mode — ACCESO PER DIFETTO, effort «high»
- Parametri endpoint: OpenAI-style `{"thinking": {"type": "enabled/disabled"}}` in `extra_body`,
  `reasoning_effort: "low/high/max"`; Anthropic-style `{"reasoning": {"effort": "none/low/high/max"}}`
  (`none` = spento). Mappatura effort: low→low; medium/high/xhigh→high; max→max (identica flash/pro).
- La catena di pensiero torna nel campo **`reasoning_content`**, allo stesso livello di `content`.
- **In thinking mode `temperature`, `top_p`, `presence_penalty`, `frequency_penalty` sono IGNORATI**
  («will not trigger an error but will also have no effect») — lato endpoint ufficiale.
- *Perché ci riguarda*: (a) il modello è addestrato a pensare di default — il nostro
  `reasoning-budget-tokens=0` (riga `common_reaso: forced sequence complete` nei log) lo forza fuori
  dal regime per cui è tarato: ogni confronto di qualità/p1 con altre configurazioni deve dichiarare
  il budget; (b) l'endpoint ufficiale NON campiona con temperatura nel thinking — se mai sweeppiamo
  temperatura/top_p sul tratto di pensiero, stiamo esplorando un regime che il fornitore non serve
  nemmeno; (c) qualunque strumento che parli con l'API vera deve leggere `reasoning_content`, non
  cercare tag nel testo.

## 3. Multi-round — il reasoning NON entra nella storia (senza tool)
- API stateless: il client concatena i messaggi. **Senza tool: `reasoning_content` dei turni
  precedenti va ESCLUSO dalla storia** (se lo passi viene ignorato). **Con tool: va RIMESSO in ogni
  richiesta successiva, pena errore 400.**
- *Perché ci riguarda*: è la semantica ufficiale del template per la chat multi-turno — la storia
  «giusta» contiene solo i `content`. Chi costruisce banchi multi-turno o confronta col serving
  ufficiale deve replicarla; e per il prefix-caching (nostro `cache_prompt` o loro) reinserire il
  reasoning cambierebbe il prefisso e ammazzerebbe i colpi.

## 4. Context caching ufficiale — tagli «a intervalli fissi» sugli input lunghi
- Cache su disco, attiva di default, a «unità di prefisso»: unità salvate (a) ai confini di
  richiesta (fine input utente, fine output modello), (b) al prefisso comune fra richieste, e
  **(c) a intervalli fissi di token dentro input/output LUNGHI**, «per evitare prefissi lunghi non
  cacheabili». Colpo solo a prefisso INTERO combaciante. Campi di telemetria:
  `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`. Costruzione in secondi, eviction
  automatica in ore-giorni.
- *Perché ci riguarda*: la scoperta di stasera — il server locale che taglia il prompt ai checkpoint
  (`fine−2048`, `fine−4`) invece di mandare `k·2048+resto` — ha un gemello DOCUMENTATO nel serving
  ufficiale: spezzare gli input lunghi a punti fissi è un tratto di famiglia di questo stack, non un
  accidente del nostro fork. La firma «N rinvii» del fix resto-64 va pensata così: i tagli ESISTONO
  per design, la classificazione di fase deve conviverci.

## 5. Chat Prefix Completion (beta) — continuazione ancorata
- Ultimo messaggio con `"role": "assistant"`, `"prefix": True`, `base_url` = `https://api.deepseek.com/beta`;
  si combina con `stop` (es. prefisso ```` ```python\n ```` + stop ``` per ottenere SOLO codice).
- *Perché ci riguarda*: è lo strumento ufficiale per ancorare una continuazione deterministica a un
  prefisso assistente — utile per banchi di confronto con l'API vera (stessa continuazione forzata
  da entrambe le parti) e concettualmente identico al nostro uso di completion su testo grezzo.

## 6. Token e tokenizzatore
- Stima ufficiale: **inglese ≈ 0,3 token/carattere** (cinese ≈ 0,6). Il nostro corpus tecnico misura
  0,365 (89.800 char → 32.782 tok): coerente, il codice/markup è più denso della prosa.
- Tokenizzatore offline scaricabile: https://cdn.deepseek.com/api-docs/deepseek_v3_tokenizer.zip —
  utile per predire le lunghezze prompt SENZA caricare il server (i `PrefixChars` mirati del banco
  oggi si scelgono a tentativi: col tokenizer offline si calcolano).
- *Nota per l'aritmetica dei tagli*: con il tokenizer offline si può scegliere `PrefixChars` per
  colpire una taglia ESATTA dell'intermedia (`fine mod 2048`), cioè costruire i repro del resto-64
  a tavolino.

## 7. Prezzi (per confronti costo/pod)
- Input cache-hit: $0,007–0,022 /1M (off-peak–peak range per modello); cache-miss: $0,22–1,32 /1M;
  output: $0,66–3,96 /1M. Fasce orarie: peak 01:00-04:00 e 06:00-10:00 UTC lun-ven. **Un colpo di
  cache costa ~30× meno del miss**: il loro intero listino è costruito attorno al prefix-caching —
  conferma esterna che la residenza/riuso del prefisso è LA leva economica di questa famiglia.

## Pagine non distillate (lette solo d'indice)
Vision, JSON Output, Tool Calls, Files API, Responses API, Anthropic API, rate limit, error codes —
fuori perimetro banco; l'indice completo sta su https://api-docs.deepseek.com/guides/.
