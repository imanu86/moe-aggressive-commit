# Qwen3.5-4B: kernel e MTP

## Mandato e autorizzazioni

Utente: ottimizzare in parallelo kernel e testa MTP sulla RTX 3060 12GB.
Autorizzati: branch research/ds4-iq1-subbit-tier-planner esistente, binari sperimentali separati, interruzione temporanea Qwen sulla 8100 per benchmark seriali e ripristino finale.
Nessun cambio branch/worktree. Non modificare i binari daily, i lanciatori originali o le impostazioni DSH. Nessuna azione reale sui telefoni: tool simulati.

## Baseline

- Modello: D:\models\qwen35-4b\Qwen3.5-4B-Q4_K_M.gguf, 2740937888 byte.
- SHA256: 00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4.
- Runtime: D:\ds4_work\bin_q36m3; CUDA SHA256 A8E6D2A95C1FCAA14D28914CEE1657E7E492A9B788AFAAF5430D8019E667886E.
- Contesto allocato 131072, singolo slot, KV Q8_0, batch2048/ubatch512, thinking acceso, niente speculazione.
- Primi test brevi: circa 67 token/s, NON baseline statistica, NON contesto occupato 100k.
- Servizio: localhost:8100; chiave esclusivamente nel lanciatore locale, non in questo repository.
- Ripristino: lanciatore Desktop `Qwen 4B - DSH Cockpit - 128k.bat`.

## Provenienza

Base source: C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\qwen_ram_decode_opt_20260920\source.
Overlay M3: D:\ds4_work\elastico_q36_m3 (context/moecache, riutilizza CUDA M2).
Il manifest prova la catena dei binari, non tutti gli hash dei sorgenti CUDA attuali: necessario gate rebuild senza modifiche.

## Corsie e ownership

- Kernel: lab D:\ds4_work\qwen4b_kernel_lab; nuovo docs/porto/banco_qwen4b_kernel; solo sorgenti CUDA nella copia, nessun modello/context condiviso.
- MTP: lab D:\ds4_work\qwen4b_mtp_lab; nuovo docs/porto/banco_qwen4b_mtp; prima testa standalone con embedding/norm duplicati, tronco invariato.
- Coordinatore: questo registro, banco HTTP, gestione server e accesso GPU esclusivo, confronto/integratore finale.

## Gate

1. Congelare hash e configurazioni, mai segreti nei report.
2. CUDA rebuild non modificato vs runtime originale: compatibilita ABI, output/logits, prestazioni ripetute senza profiler.
3. Profilare lanci CUDA effettivi con Nsight Systems graph-trace=node; non dedurre kernel dai nodi del grafo.
4. MTP standalone: validazione metadati/tensori/normalizzazioni, avvio, verifica token e rollback stati; proposte 1/2/3.
5. Confronto stessi prompt e sampling, TTFT, tempo fino al tool, latenza totale, decode, accettazione, VRAM, errori.
6. Prompt corto e contesto effettivamente occupato lungo separati; nessuna promessa di qualita a 100k basata sulla sola allocazione.
7. Ripristinare sempre servizio originale; nessuna promozione senza risultati misurati.

## Stato

Analisi concluse. Testa MTP standalone Q8_0 pronta (660602592 byte, SHA256 4e1dfbc30b1c1d8b2861be93fb14e5ae0f2481df347f4484df763c347cea26e7), 15 test CPU e verifica indipendente superati. Download selettivo 139710464 byte; tronco invariato.

Build CUDA isolata senza patch completata: comandi compilatore corrispondenti dopo normalizzazione dei path, ABI statica superata; candidato differisce soltanto nella DLL CUDA (SHA256 0559091498F5D9704F51FE7649AB1C264820FF8B0EAF1F268B6BA400DA27E25D). Serve gate numerico, non dedurre equivalenza dal solo ABI.

Smoke MTP1 riuscito: una chiamata tool corretta, 36/36 proposte accettate. Tempi NON benchmark (compilazione concorrente).

Banco HTTP: 6 test CPU superati, revisione indipendente completata; validazione input/suite/hash/config, terminali e schemi; confronto logit/stati NON coperto dal semplice hash testuale. Cancellazione brutale del runner puo richiedere pulizia esplicita del PID registrato: non interrompere job senza verificare figli e ripristino. Il finally copre uscite/errori ordinari.

Campagna pulita pwsh-76 COMPLETATA e daily ripristinato: original_a, rebuild, original_b, mtp1/2/3; 3 ripetizioni per cinque casi, thinking off e greedy SOLO per confronto differenziale. Rebuild: 15/15 output identici, velocita in parita. MTP1: 15/15 identici, tool_batch mediana86.28 vs65.52 token/s. MTP2 e3: prosa divergente3/3 (indagine numerica/rollback ancora aperta), JSON simulati identici. tool_retry fallisce nello stesso modo anche nella baseline: aggiunge name=telefono. Nessuna promozione del daily a thinking off.

Profilo Nsight pwsh-77 COMPLETATO: D:\ds4_work\qwen4b_campaign\nsys_original\capture.nsys-rep, graph-trace=node. MMVQ quantizzato circa83% del tempo GPU sommato; kernel lane prepara un esperimento opt-in molto ristretto sul Q4_K fused2560x9216, occupazione sm86 (non fusioni elementwise marginali).

Sweep tool su richiesta umana bozze3/4/6/8 pwsh-79 COMPLETATO, daily ripristinato. Singolo caso tool_batch, 3 rep: baseline mediana66.55 token/s; bozza8 mediana144.54, tempo totale1.3595->0.8211s, proposte62/72 accettate, JSON corretto. Non e generalizzabile a prosa o100k. Script run_variant autorizza ora1/2/3/4/6/8.

Round2: job parent pwsh-80 COMPLETATO, daily ripristinato. Prompt102827 token reali, una ripetizione tool_batch: baseline prefill79.79s/decode32.44tps/turno82.07s; MTP8 prefill87.99s/decode81.50tps/turno88.97s. JSON identico e corretto, memoriaGPUiniziale10.5GiB complessivi conMTP8. Primo turno freddo PEGGIORA nonostante decode accelerato; nessuna statistica su un solo campione.

Round3/4: unit GPU OCC12 pwsh-85 pass12/12 bitidentico max_abs0; 53->40registri e9->12blocchi, microtempi misti NON prova di speedup. Runtime OFF/ON/OFF pwsh-86: tutti15 output identici; OCC12 tools~68tps vs72-75OFF, prosa68.65ON vs68.64/71.40OFF, varianza evidente, nessun guadagno netto. NON promuovere OCC12 al daily.

Stesso job86: thinking-on retry su device2 simula correttamente entrambe varianti (3/3). Baseline187token, mediana3.02s e67.78tps; MTP8 182token, mediana2.21s e94.82tps, chiamata finale corretta ma ragionamento diverso. Non e equivalenza bitwise; con thinkingOFF lo stesso caso falliva in entrambe.

Round4/5: job87 COMPLETATO e daily ripristinato, healthOK. ProfiloON prova18374lanci effettivi minblocks12,40registri; non cambia verdetto negativo OCC12. Baseline/MTP8 a102k con4turni: 3followup warm identici e corretti,103013/103199/103385token occupati, mediana2.4342->1.6666s,35.73->81.29tps; primo delta tool peggiora0.730->1.011s. Cold77.14->85.42s (n=1). Banco CPU7test e MTP15test nuovamente pass. Report RISULTATI.md.

Utente ha autorizzato esplicitamente COMMIT E PUSH DELL'INTERO RAMO, inclusi i580commit precedenti. Nuovi commit limitati ai tre folderbanco, nessun file altrui aggiunto. L'esito della pubblicazione va verificato sul remoto e riportato nella consegna.

Repo reap-loop letto su indicazione umana, nessuna modifica: ramo plan/0051-transport-gate-20260713 con registro modificato, nessuna autorizzazione a cambiarlo. Eventuale pruning35B e progetto distinto, non eseguito. Repo moe ahead580 gia prima di questa attivita: nessun push della cronologia altrui senza conferma specifica.
