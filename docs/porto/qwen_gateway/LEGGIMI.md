# Gateway locale: Qwen al posto di Haiku in Claude Code (app desktop compresa)

**Obiettivo.** Tenere Fable/Opus/Sonnet sull'abbonamento e mandare al llama-server locale le richieste
destinate a Haiku (in prima battuta solo quelle dei subagent). Anthropic dichiara non supportato
l'instradamento verso modelli non Claude: è un assetto a nostro rischio, reversibile.

**Perché un proxy HTTPS e non `ANTHROPIC_BASE_URL`.** L'app desktop forza
`ANTHROPIC_BASE_URL=https://api.anthropic.com` nelle sessioni del tab Code e la sua modalità gateway
(«Third-Party Inference») sostituisce il login claude.ai con una credenziale del gateway. La doc
`network-config` dice però che in una sessione locale del tab Code con login claude.ai Claude Code legge
`HTTPS_PROXY`, `NO_PROXY` e `NODE_EXTRA_CA_CERTS` da ogni `settings.json`. Da qui il disegno:

```
Claude Code ──CONNECT──> gateway 127.0.0.1:8787 ──┬─ api.anthropic.com: TLS aperto col certificato locale,
                                                  │    richiesta inoltrata INTATTA ad Anthropic (fase 1)
                                                  │    oppure, se il modello è Haiku, verso Qwen (fase 2)
                                                  └─ ogni altro host: tunnel cieco, mai aperto
```

## File

| file | cosa fa |
|---|---|
| `genera_ca.py` | CA locale vincolata (nameConstraints critico) a `api.anthropic.com` + certificato; la chiave della CA viene cancellata dopo la firma; tutto in `%USERPROFILE%\.claude\qwen-gateway`, ACL del solo utente, fuori dal repo. **Mai installarla nello store di Windows.** |
| `gateway.py` | il proxy, solo libreria standard. Fase 1 = solo inoltro. Registra solo metadati (modello, stream, n. messaggi, n. tool, subagent sì/no, status, tempi) in `D:\ds4_work\qwen_gateway_run\log_gateway\`; mai header di autenticazione né contenuti. |
| `prova_gateway.py` | prova da Python senza toccare Claude Code: 401 vero di Anthropic attraverso il certificato locale, tunnel cieco verso example.com, rifiuto di example.com con la sola CA locale. |
| `server_locale.py` | avvia un llama-server isolato (127.0.0.1:8113, chiave temporanea), bracci `m1`/`x4` del banco follow-up. |
| `sonda_messages.py` | sonda di `/v1/messages` col corredo di campi che Claude Code manda. |

## Esiti del 21 settembre 2026

**Sonda di `/v1/messages`, binari di produzione p11 (`20260921_122…_sonda_x4`):**

- risposta e stream nel formato Anthropic corretto (`message_start` … `message_stop`), primo byte a 0,5 s
  perché `message_start` parte subito; **nessun evento `ping`**: durante un prefill lungo lo stream tace,
  e Claude Code abortisce dopo 180 s di silenzio → sulla rotta locale i ping li deve emettere il gateway;
- accettati senza errore: `thinking` (adaptive ed enabled), `output_config`, `context_management`,
  `metadata`, tool con `defer_loading` / `strict` / `cache_control`, `system` a blocchi con `cache_control`
  e blocco di attribuzione in testa, messaggi a blocchi con `cache_control`, `?beta=true`, header `anthropic-beta`;
- **rifiutato (500, template Jinja «System message must be at the beginning»): un messaggio
  `role: system` a metà conversazione** → il gateway lo deve convertire in un turno utente;
- tool use: blocco `tool_use` con JSON valido, `stop_reason: tool_use`, secondo giro col `tool_result` corretto;
- i blocchi `thinking` tornano con `signature` vuota; `model` nella risposta è il percorso del GGUF
  (da riscrivere con l'ID richiesto); `/v1/messages/count_tokens` risponde.

**Sonda sul runtime elastico M1 (`…_sonda_m1`): tutte le richieste 500 «Compute error».** Nel log:
`RAM decode canary rejects new prefill while expert pages are absent`. A fine caricamento la RAM
disponibile era ~2,1 GB (programmi aperti: ~5 GB in più di stamattina), la politica RAM ha sfrattato 158
gruppi di pagine degli esperti e da lì il server rifiuta OGNI nuovo prompt. Le prove di Codex applicavano
la pressione solo durante il decode: il prefill con pagine assenti non era mai stato provato. **Il
lanciatore adattivo non è usabile come daily finché il runtime non ripristina le pagine prima del prefill.**

**Gateway in solo inoltro:** `prova_gateway.py` 3/3 (401 vero di Anthropic con `request_id` attraverso il
certificato locale; example.com in tunnel cieco; CA locale rifiutata per example.com). Con la CLI `claude`
lanciata con `HTTPS_PROXY` + `NODE_EXTRA_CA_CERTS` nel solo processo, le sue chiamate a
`api.anthropic.com` (`/mcp-registry`, `/api/event_logging`) sono passate dal gateway con 200: Claude Code
onora proxy e CA. La richiesta al modello non è partita perché la CLI non è loggata (si usa solo l'app).

**App desktop attraverso il gateway (21/9, 13:02, con l'ok dell'utente): FUNZIONA, abbonamento intatto.**
`imposta_proxy.py --attiva` ha messo `HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS` e `NO_PROXY` nell'`env` di
`%USERPROFILE%\.claude\settings.json` (copia di sicurezza accanto). L'app applica la modifica **a caldo**:
le due sessioni del tab Code già aperte sono passate subito dal gateway, senza riavvio. Nel registro:
`POST /v1/messages` con `claude-fable-5-1` → 200 in streaming (primo byte 1,0-2,2 s), più
`/v1/code/sessions/*/worker/events` e `/api/event_logging` → 200; nessun errore. Campi visti nelle
richieste vere: `context_management`, `diagnostics`, `metadata`, `output_config`, `thinking`; 47-49 tool.

Sul Desktop: `Claude - avvia gateway Qwen.bat` e `Claude - TORNA DIRETTO (senza gateway).bat` (toglie le tre
chiavi). **Finché non c'è l'avvio automatico, dopo un riavvio del PC il gateway va acceso prima di aprire
Claude, altrimenti l'app non si collega.**

**Prima chat vera su Haiku servita da Qwen (21/9, 13:21-13:26, binari p11 a 40 slot, server isolato):**
elenco dei file + lettura e riassunto del README con gli strumenti, esito corretto, 4 richieste tutte `LOCALE`.

| turno | token nuovi | prefill | generati | totale | note |
|---|---|---|---|---|---|
| 1 | 48.038 | 123 s (390 t/s) | 187 a 18,5 t/s | 134 s | 12 ping, nessun abort; il prompt di una chat dell'app pesa ~48k token (sistema + CLAUDE.md + indice della memoria + 45 tool) |
| 2 | 978 | 4,2 s | 131 | 11 s | cache del prompt riusata |
| 3 | 847 | 3,8 s | 529 a 19,2 t/s | 32 s | |
| 4 | 51.011 | 125 s | 133 | 132 s | **cache persa**: il prompt è cambiato al token 26.541 (Claude Code ritocca una parte già inviata) e il primo checkpoint utile stava a 29.877 → il modello ibrido non può tornare indietro e rifà tutto |

**Traffico Haiku di sfondo.** Con `instrada: tutti` le richieste di sfondo di Claude Code (non in streaming,
1 messaggio, ~5k token, `max_tokens` 1024, da OGNI sessione aperta, a ripetizione) sono finite su Qwen:
50-173 s l'una, due troncate a 1024 token dal ragionamento, slot sempre occupato, e la verifica del modello
di `set_session_model` è scaduta in coda. All'apertura di una sessione partono anche ~50 richieste Haiku
minuscole (conteggio dei token, una per tool più una con tutti i 141 tool). Da qui la regola predefinita
`instrada: stream`: a Qwen vanno solo le richieste in streaming (chat e subagent), il resto al vero Haiku.

## Prossimi passi

1. Lasciar lavorare l'app qualche ora e leggere dal registro quali richieste usano Haiku e da dove
   vengono (principale o subagent): decide la regola d'instradamento.
2. Fase 2: instradamento Haiku → Qwen (solo subagent), conversione dei `system` a metà conversazione,
   ping durante il prefill, riscrittura di `model`, ricaduta sul vero Haiku se il server locale non risponde.
3. Avvio automatico, guardiano che toglie le due righe se il gateway non risponde, bat «torna diretto».
