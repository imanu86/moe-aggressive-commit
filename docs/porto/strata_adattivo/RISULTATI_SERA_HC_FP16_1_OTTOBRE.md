# HC/GDN FP16 — finestra serale del 1 ottobre 2026

Ripresa autorizzata dall'utente: una o due patch, massimo tre corse, massimo 30 minuti
complessivi. Finestra comunicata a OCGC-IA: **19:52–20:22 Europe/Rome**; OCGC attende il via
prima di riprendere la GPU. Nessun carico artificiale. Branch autorizzato
`research/ds4-iq1-subbit-tier-planner`; clone operativo e lanciatore #270 preservati.

## Ricognizione aggiornata

Snapshot API alle 17:53 UTC: upstream **0.1.32**, SHA
`c499bd102e7a4135c0de389dcfe38c399759ccc8`. Confrontati **380 fork accessibili** sul ramo
predefinito, **39 con commit propri**, zero errori; **42 PR aperte**. Contatore generale 384,
distinto dall'elenco accessibile. Rispetto al mattino upstream ha 89 commit aggiuntivi.
Il fork [jklnvlink/Strata-2080ti](https://github.com/jklnvlink/Strata-2080ti) resta a
`235350960d853674f0279e5838a16e68e71be2bd`: nessun nuovo fix HC da aggiungere.
Snapshot in `corse_2080ti/20261001_sera_hc_fp16/ricognizione/`; risposte integrali locali in
`.codex_runs/strata_ricognizione_20261001_sera/`.

La [0.1.32](https://github.com/Niko1221/Strata/commit/c499bd102e7a4135c0de389dcfe38c399759ccc8)
include #315 con switch rinominati, commit asincrono e relativo follow-up sugli eventi,
keep-alive SSD, diagnostica dei primi logits e chunk sopra 8192 opt-in. Numerosi guadagni
riguardano AMD, split su piu' GPU o altri pack: nessun aggiornamento indiscriminato del nostro
clone operativo durante questa finestra. Il confronto resta sulla base 0.1.31 gia' verificata.

Piste per la prossima sessione, **non applicate/provate qui**:

- [#372](https://github.com/Niko1221/Strata/pull/372): gather degli esperti in una chiamata per
  gruppo, con meno wait/eventi; misura dell'autore circa -9% sul prompt 32k su 5090/IQ2_XS.
  E' pertinente a Windows/WDDM, ma va verificata sulla nostra scheda.
- [#374](https://github.com/Niko1221/Strata/pull/374): prima lettura PLE sovrapposta a layer 0
  e piu' letture in volo. Dati dell'autore su un SSD diverso; non assumere lo stesso guadagno.
- [#378](https://github.com/Niko1221/Strata/pull/378): crescita KV con VMM. Richiede tutto il KV
  in VRAM, senza `--kv-resident`: non si applica direttamente al nostro profilo con 32.768
  residenti e resto in RAM, e va riconciliata con la nostra cache elastica.
- [#407](https://github.com/Niko1221/Strata/pull/407): memoria piu' lunga e scambi piu' frequenti
  nella cache adattiva. Meno miss/PCIe sul pack dell'autore, tempo per passata entro il rumore;
  nessun guadagno dichiarato su IQ2_XS. Non equivale a un incremento certo sul nostro IQ3_XXS.
- [#385](https://github.com/Niko1221/Strata/pull/385): attesa DMA fra generazioni dello stager,
  rilevante per blob non pinned. Correzione di robustezza da valutare nel prossimo porting.

## Le due patch

1. **HC/GDN FP16 sm75**, `0018` gia' preparata nel giro precedente: proiezioni HC e alpha/beta
   del prefill sui tensor core FP16, draft/MTP ancora BF16. Stessi controlli numerici delle
   copie e dei pesi del rapporto precedente; nessuna nuova variante vettoriale o #315.
2. **Primi logits nel server persistente**, diagnostica basata sul
   [commit upstream ad48d5c5ca](https://github.com/Niko1221/Strata/commit/ad48d5c5ca): lettura
   della prima riga del verificatore, opt-in `STRATA_DUMP_FIRST_LOGITS`. Adattata anche al
   ciclo del server e salva file distinti per posizione del prompt; nessun cambiamento al
   calcolo. Ricompilati soltanto `verify.cpp` e `generate.cpp` per base e candidata; stessi
   kernel/librerie originali, salvo la libreria HC della candidata. Preparazione riproducibile
   in `strumenti/compila_primi_logits.py`. Patch LF applicabile ai sorgenti CRLF con
   `git apply --ignore-space-change`, verificata su entrambe le varianti.

Il banco aggiunge limite totale di durata e modalita' solo retrieval 250k, per rispettare
la finestra senza ripetere il benchmark 131k nella terza corsa. Il limite comprende l'avvio;
il cleanup termina solo i processi avviati dalla corsa. API key esclusa dall'ambiente.

## Tre corse

Stesso pack IQ3_XXS, server 0.1.31, KV int8 **262.144**, residenti **32.768**, cache richiesta
**4.200**, slot effettivi **5.621**. Le prime due corse usano la fixture P0 L01/L02 da circa
131k e 1024 token generati per richiesta, con i consueti due riscaldamenti brevi. L01 e'
il prefill freddo completo; L02 riusa 131.072 token e legge solo 167 nuovi.
La terza corsa e' un riempimento/retrieval distinto, senza il banco P0.
Le immagini FP16 aumentano il prestito del prefill: **2.846 slot / 4,56 GiB** nella base,
**2.950 slot / 4,73 GiB** nella candidata. I 5.621 slot totali sono uguali, ma il prestito
puo' cambiare la residenza dopo il prefill e quindi l'arrotondamento CPU/GPU del primo verify.

| Corsa | Prefill L01 t/s | TTFT L01 s | Decode aggregato t/s | ms/riga aggregati |
|---|---:|---:|---:|---:|
| sera_0131_base_logits | 725.83 | 181.432 | 37.409 | 22.735 |
| sera_0131_hc_logits | 828.53 | 159.000 | 36.489 | 22.890 |

Prefill **+14.15%**, primo token **22.432 s prima**.
Il decode non migliora; output e accettazione MTP differiscono. Nessuna attribuzione causale
della variazione di decode alla patch di prefill. Entrambe le corse completano L01 e L02.

CPU degli altri processi (escluso System Idle Process): media **0.94 / 1.02 core**
in base/candidata sull'intera corsa; RAM disponibile minima **25.20 / 27.11 GiB**.

Logits: 248.320 valori finiti per riga. Warm-up identico bit per bit; L01/L02 non identici,
argmax coincidente (token 1596), RMS **0,339 / 0,389**, massimo errore assoluto
**1,837 / 2,009**, overlap top-10 **9/10 e 8/10**. Il percorso FP16 cambia l'aritmetica;
il prestito diverso e' un altro limite nell'attribuzione delle differenze. La verifica
generale di qualita' resta aperta.

Terza corsa: **250.022 token reali** confermati sia dal tokenizer sia dal runtime,
ago a meta' del testo **recuperato** (`ARCO-AMBRA-742913`), 13 token di risposta,
**521.66 s** di richiesta. Prefill **480.75 t/s**, decode **21.40 t/s**
per questa risposta brevissima: non confrontarlo col decode P0 da 1024 token.
Il motore aveva capacita' KV262144, residenti32768; test sulla candidata HC a cache fissa,
non una validazione del lanciatore elastico operativo. Prompt SHA256 e filler SHA256
nel risultato conservato. Un solo ago/profondita': nessuna valutazione retrieval completa.

Non e' una conferma A/B/A: il vincolo di tre corse privilegia il primo riempimento reale
250k. Un primo token con argmax uguale e un ago recuperato sono controlli delimitati;
non dimostrano equivalenza numerica del modello o qualita' generale. FP16 cambia gli
arrotondamenti rispetto alla base. Il dato storico #270 sopra 800 t/s usa un'altra
configurazione, quindi questo A/B non lo sostituisce.

## Chiusura e ripresa

Tre corse eseguite, nessuna quarta prova. Carichi Strata chiusi entro **25.8 minuti**
dall'inizio della finestra (il tempo finale include ancora la pubblicazione). OCGC-IA
ha ricevuto il via esplicito per riprendere la GPU. **Nessuna promozione:** rimane
il lanciatore 0.1.30 + #270, KV262144, hash `713922610f2820b0e726adc371eb774a7d5502a548d08b59d244afbb38e898ed`.
La candidata HC e' promettente per prefill; prima di promuoverla servono una conferma
A/B/A e piu' verifiche di qualita'/retrieval. Nessun altro job Strata programmato.

Evidenza curata in `corse_2080ti/20261001_sera_hc_fp16/`. I dump FP32 completi e i binari
restano nel laboratorio locale; pubblicati digest e confronto numerico. Prossima sessione:
conferma della candidata se le misure la giustificano, poi valutazione #372/#374 su base
aggiornata conservando cache elastica, checkpoint allineati e commit async senza duplicazioni.
