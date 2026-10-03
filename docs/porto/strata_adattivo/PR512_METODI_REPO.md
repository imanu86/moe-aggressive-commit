# Conformità della validazione PR512 ai metodi Strata

Verifica del 3 ottobre 2026. La PR512 è già chiusa e il codice integrato manualmente in upstream0.1.38.

Fonti primarie:
- https://github.com/Niko1221/Strata/blob/main/docs/COMMUNITY_BENCHMARKS.md
- https://github.com/Niko1221/Strata/blob/main/CMakeLists.txt
- https://github.com/Niko1221/Strata/releases/tag/v0.1.38

Copertura locale del test isolato0.1.37 + sola PR512:
- Build CMake del motore e del target qsa_topk_active_parity: completata.
- Esecuzione del binario registrato in CTest:16/16 ID identici. Non equivale all'esecuzione di tutta la suite CTest.
- A/B/A stesso motore, stesso workload, stessi5357 slot e impostazioni; fresca131248, follow-up131239/reuse131072; due output1024 per braccio.
- Prefill776.53/832.24/772.34; +7.46%, riferimento0.54%spread. Solo due riferimenti e un candidato nella ripetizione stabile.
- Hardware, software, cache, warm-up, conteggi effettivi, finestre temporali, log grezzi, risorse, hash e limiti riportati.
- Il primo A/B/A rumoroso è conservato. Non va sommato alle nuove prove come se tutte avessero condizioni stabili.
- Nessun nuovo oracle di risposte complete o confronto teacher-forced dell'intero modello in questo test isolato. Le verifiche del Daily/port combinato non sostituiscono quelle su questa precisa build.
- Il maintainer ha inoltre incluso il nostro test nella release e riferito un passaggio su RTX5070; è una verifica esterna, non un test eseguito localmente.

La guida community raccomanda di provare almeno tre misure per configurazione, pubblicarle tutte, mediana e intervallo; ammette esplicitamente anche una sola misura se dichiarata. Non impone un gate universale a ogni patch.
Per una validazione più ampia della prestazione del cambiamento: almeno tre coppie intercalate capacità/attivi, mediana/intervallo; un controllo indipendente con risposte complete e/o logits teacher-forced, stessa cache statica e adattamento disabilitato per evitare ambiguità. Distinguere state reset e prefissi riusati.

Il maintainer documenta per0.1.38 confronti a più coppie e oracle10/10 su quattro quantizzazioni. Non dichiariamo di aver replicato l'intero protocollo di release su questa build isolata.

Ulteriori contributi locali:
1. Checkpoint grid: align_every/align_origin e taglio PLE del chunk, assenti nel main controllato; bug indipendente da portare e validare.
2. Cache elastica VMM, core/coda, margine e isteresi: assente nel main controllato; richiede port e gate specifico.
3. Banco esperti con righe GGUF reali e strumenti qualità/teacher-forced: strumenti condivisibili separatamente.
Il multi-token grouped expert ha ormai una soluzione equivalente upstream (row_dot_multi/native_gu_multi_kernel): non trattarlo come feature mancante. HC/GDN/vector provengono dalla community. Top-k decode dinamico ha guadagno insufficiente per il gate locale.

Proposta preparata: PR512_FOLLOWUP_PROPOSTA.md.
Invio commento a Niko: NON ESEGUITO. La chiamata github_add_comment_to_issue è stata rifiutata prima dell'esecuzione:
"MCP tool call requires approval, but approval policy is never".
Non è un rifiuto editoriale di Niko, né una rejection di un automatic approval review, né un nuovo403.
Nessun percorso browser alternativo utilizzato.

Aggiornamento dopo accesso completo: Git locale e push funzionanti; questo audit e le evidenze sono pubblicati. La nuova proposta checkpoint-grid aspetta le sue misure intercalate e il gate qualità su upstream0.1.38. Nessun commento pubblico inviato.
