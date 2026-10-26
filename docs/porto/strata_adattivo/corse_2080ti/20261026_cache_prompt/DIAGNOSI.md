# Prompt non riusato fra i turni di un agente su Strata 0.2.6 Daily (26/10/2026)

## Esito
Il prefisso cambia perche **l'elenco `tools` non e lo stesso fra il turno 0 e il turno 1**: i tool dei server MCP
(`mcp__cgc-infra__*`, 7 tool) compaiono solo dal secondo turno, quando il server MCP finisce di connettersi.
Il template scrive i tool PRIMA del prompt di sistema, quindi il primo token diverso cade nell'elenco, a ~13.9K token:
sotto il primo checkpoint da 16384 (`--prompt-cache-every 16384`) e sotto il prefisso su disco. Ne segue «0 reused».

## Prove
- Dal log dell'utente: prefisso su disco salvato 17072 token (turno 0) e 17703 (turno 1): +631. La parte dopo il prefisso
  (primo messaggio utente con CLAUDE.md, memoria e ambiente) e identica, 11427 token in entrambi. Quindi cambia solo
  la parte «tool + sistema», non i messaggi.
- `costo_tool.py` misura con template e tokenizer del server: i 7 tool `cgc-infra` valgono **esattamente 631 token**
  (cgc-cockpit 1092, promo-sil 2693, interni 12796).
- `simula_mcp_tardivo.py`: turno 0 senza i tool `cgc-infra`, turno 1 con tutti i 41 -> primo token diverso = **13914**,
  testo: `"name": "mcp__promo-sil__sil_check"` (turno 0) contro `"name": "mcp__cgc-infra__cgc_clients_roster"` (turno 1).
- Campi esclusi come causa: il blocco di attribuzione/billing (`x-anthropic-billing-header: cc_version=2.1.294.50c;
  cc_entrypoint=sdk-py;`) e identico a ogni richiesta (con `sdk-py` non c'e `cch=`; con la CLI `cch` cambia ma
  `pin_billing_stamp` lo fissa gia); i blocchi `system`, l'ordine dei `tools`, `defer_loading` (assente) e il primo
  messaggio sono byte per byte uguali fra i turni.
- Due corse reali con proxy (8106, `richieste/`, 4 richieste, MCP gia connessi al turno 0): il prompt del turno 1 contiene
  per intero quello del turno 0 e il server riusa 28987 token su 30967; la seconda corsa riusa il prefisso su disco
  (17458) e poi 29249 su 33581. Il difetto **non si e riprodotto dal vivo**: li gli MCP erano pronti prima del turno 0.
  Il meccanismo e dimostrato dalla simulazione e dai 631 token, non da una cattura del turno difettoso.
- Non spiegato: il prefisso del turno 0 dell'utente (17072) e 386 token meno del mio (17458, 41 tool) e quello del
  turno 1 (17703) 245 piu: il suo elenco tool aveva altri insiemi/sorgenti MCP. Va confermato con una cattura (sotto).

## Correzione minima proposta (non applicata)
1. **Cliente (consigliata, zero rischio per il server)**: in `locale_agent.py` fissare l'elenco tool ai soli interni
   con `tools=["Bash","Read","Write","Edit","Glob","Grep"]` (non `allowed_tools`, che non toglie i tool dal prompt) e
   `extra_args={"strict-mcp-config": None}` senza MCP. Elenco identico a ogni turno e ~4.4K token in meno per prompt
   (cockpit 1092 + cgc-infra 631 + promo-sil 2693) a ~1000 tok/s di prefill: circa 4 s per ogni lettura completa.
2. **Server (solo se si vuole tollerare gli MCP tardivi)**: non c'e una riga innocua. `_stable_tool_order`
   (serve/frontend.py) copre solo lo stesso insieme in ordine diverso. Estenderlo a un insieme che cresce
   (ordine di prima vista, nuovi in coda) alza il punto di divergenza solo da 13.9K a 14.5K: resta sotto il checkpoint
   a 16384, quindi non basta. Servirebbe un checkpoint a fine elenco tool; non proposto: il costo e una lettura completa
   una sola volta, al turno in cui gli MCP si connettono (dal turno dopo il prefisso e stabile).
3. Verifica: rilanciare l'agente reale dell'utente dietro `proxy_cattura.py <cartella>` (porta 8106, salva il solo corpo
   JSON) e confrontare con `confronta_prompt.py <source> <pack> <cartella>`: se il primo token diverso cade dentro
   `<tools>`, la causa e confermata.

## File
`proxy_cattura.py`, `confronta_prompt.py`, `costo_tool.py`, `simula_mcp_tardivo.py`, `brief_multi.md`. Le richieste
catturate (`richieste/`, `*.log.jsonl`) restano solo in locale: contengono CLAUDE.md e memoria personali. Strata sulla
8100 non e stato toccato.
