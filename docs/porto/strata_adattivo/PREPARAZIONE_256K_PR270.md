# Contesto 262k e PR #270: preparazione senza carichi aggiuntivi

L'utente ha confermato l'1 ottobre 2026 che intende un contesto di circa 250k e che il sistema e' gia' sotto pressione:
non aggiungere carichi artificiali per simulare un PC saturo, come hog GPU o stress CPU/RAM. Compilazioni e prove
normali del motore restano nel lavoro e usano il carico reale presente. Questo giro prepara file e analizza sorgenti;
la patch non e' ancora applicata o validata nel clone operativo per le restrizioni del filesystem descritte sotto. La validazione del
giro precedente a 131k resta valida per quel contesto e non certifica 262k.

**Aggiornamento:** eseguita la prova con capacita' KV 262.144 e gli stessi due prompt a 131k. Avvio e richieste
completati, 43,0 token/s aggregati, prefill freddo 663 token/s. Vedi `RISULTATI_KV262K_1_OTTOBRE.md`.
Questo prova l'allocazione della capacita' 262k e il funzionamento a 131k, non un prompt che riempia 250k token.

## Configurazione candidata

`lanciatori/strata-2080ti-256k.json` e' una copia della SOTA promossa, con una sola differenza:
`--max-context 139264` diventa **`--max-context 262144`**. Quest'ultimo era anche il contesto del precedente daily,
indicato nei risultati del 28 settembre. Eseguibile ancora `build-0130`, KV int8, KV residente 32.768, riserva di
avvio 1.393 MiB e cache esperti a due zone.

Il parser di Strata accetta questa capacita'. `generate.cpp` documenta 262.144 come contesto addestrato predefinito
per i controlli RoPE; nessuna nuova opzione di scaling viene aggiunta. Dal codice di `core/layer.cpp`:

- gli slot della KV in VRAM dipendono da `--kv-resident`, quindi il pool K/V residente resta da 32.768 token;
- la copia completa di K/V in RAM bloccata cresce col contesto;
- anche tabelle delle pagine, indice e tabella RoPE crescono: la VRAM totale non resta identica.

La prova successiva ha verificato l'allocazione sotto il carico attuale, con 3,09 GiB di K/V in RAM bloccata.
Dopo l'accesso completo e la richiesta dell'utente, il JSON operativo
`D:\ds4_work\strata\Strata\strata-2080ti-sota.json` e' stato aggiornato a 262.144 e alla build #270 validata,
conservando JSON e BAT precedenti nel ripristino `20261001_060447_pr270_262k`. Una sessione gia' avviata non cambia
contesto. I blocchi del precedente runtime protetto non si applicano piu'.

## PR #270: prefill con tensor core su Turing

Fonte: ref locale gia' scaricato `pr-270`, commit `3d3939d`. Patch integrale con autore e trailer preservati in
`patches/da-valutare/0014-PR270-prefill-Turing.patch`. Tocca solo `src/kernels/cuda/qsa_prompt_attn.cu`.

Su Turing il controllo delle capacita' abilita il percorso tensor core, scomponendo l'operazione MMA k16 in due
MMA k8. L'attenzione int8 sceglie `launch<1>` e non il percorso `launch_i8` con `cp.async`, assente su sm_75.
Per sm_80+ resta il percorso esistente. La PR cambia l'ordine di somma: non promette identita' bit per bit.
Le misure di parita' e velocita' nella descrizione del commit sono dell'autore su altro hardware, non nostre.

**Controllo eseguito:** `git apply --check` della patch contro il clone operativo su `main`, commit `ade7160`,
0.1.30 + 13 patch. Superato senza scrivere nei sorgenti. Patch non applicata al clone operativo.

Tentata anche la compilazione offline del solo file CUDA, su una copia temporanea nel repository, con CUDA 12.6,
sm_75+86 e un thread NVCC. La catena di avvio termina con codice 1 senza diagnostica CUDA; nessun oggetto prodotto.
Questo primo tentativo non confermava la compilazione, senza attribuire il fallimento al kernel. Esito storico in
`patches/da-valutare/PR270-compilazione.json`; sorgente e script temporanei in `.codex_runs/strata_pr270_20261001/`.

**Compilazione e parita' ora superate (1/10):** risolto l'avvio della catena MSVC/NVCC attraverso il Python
integrato; CUDA 12.6, C++20, sm_75+86. Ricompilato solo il file della PR e ricreati libreria ed eseguibile dagli
altri oggetti della build 0130, senza modificarla. Strumento `strumenti/compila_pr270.py`; output separato in
`.codex_runs/strata_pr270_20261001/`. Tutti gli 8 casi int8/fp16 di `qsa_prompt_attn_parity` superati contro il
percorso precedente e il riferimento CPU FP64. A 2.048 query: int8 65,359 -> 20,161 ms (3,24x), fp16
62,498 -> 25,067 ms (2,49x). Sono tempi del singolo kernel, non del modello completo. Una ripetizione cronometrata
per caso; le differenze numeriche rispettano le soglie del test, senza identita' bit per bit.

**Prova del modello completata:** KV 262.144, stessi prompt a 131k e carico reale, nessun hog aggiuntivo.
Prefill 808,91 contro 661,76 token/s nel riferimento successivo (+22,24%), primo token 162,98 contro 199,10 s;
entrambe le richieste a budget. Primo caricamento lento (223 s), riavvio 61 s: ritardo non ripetuto.
Misure, limiti e stato operativo in `RISULTATI_PR270_1_OTTOBRE.md`. Build promossa in `build-0130-pr270`,
separata da `build-0130`; lanciatore aggiornato dopo l'accesso completo.

## PR #317: SSD

Fonte: ref locale `pr-317`, commit `3653faf`. Introduce una lettura di pagina dopo 100 ms senza letture per mantenere
l'SSD sveglio, fino a 60 s dall'ultima richiesta; la nuova funzione e' attiva per default se si applica la patch.
`STRATA_SSD_KEEPALIVE=0` la disabilita. Non dimostra da sola la causa del blocco iniziale oltre 60 s osservato qui:
la descrizione dell'autore riguarda ritardi SSD di 50–150 ms.

La PR rimane da valutare: non viene applicata in questo giro. Manteniamo il watchdog operativo a 240 s.

## Stato del salvataggio

File nel checkout research autorizzato. Nella precedente sessione protetta staging e push erano bloccati
(`index.lock: Permission denied`, autenticazione Windows indisponibile). L'utente ha poi abilitato accesso completo:
installazione operativa completata e salvataggio sul branch research ripreso, senza includere gli altri file locali.
