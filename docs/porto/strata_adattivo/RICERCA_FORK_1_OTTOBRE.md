# Ricognizione Strata — 1 ottobre 2026

**Priorita' aggiornata:** preparare una base di laboratorio **0.1.31**, mantenendo le nostre patch
ancora necessarie; poi provare le ottimizzazioni sm75 del fork **jklnvlink/Strata-2080ti** una per volta.
L'utente ha autorizzato di procedere dopo la ricognizione. Lanciatore operativo ancora #270,
KV int8 262.144 e 32.768 residenti; nessun carico artificiale.

## Perimetro e fotografia

Letture via GitHub API e pagine dei progetti; nessun codice dei fork eseguito in questa ricognizione.
Snapshot iniziato il 1/10/2026 alle 10:28 UTC. Upstream fissato a
[`9259cad4cfa3543cd3b8decab5962672b968c649`](https://github.com/Niko1221/Strata/commit/9259cad4cfa3543cd3b8decab5962672b968c649).

- API paginata: **326 fork accessibili**, tutti confrontati sul ramo predefinito; **35 con commit propri**,
  zero errori di confronto. Il contatore generale del repository era 330: il perimetro verificato e'
  quello effettivamente restituito dall'elenco paginato, non il contatore della pagina.
- **46 PR aperte** censite con SHA del ramo sorgente; descrizione/codice approfonditi per quelle pertinenti.
- **61 commit** tra 0.1.30 (`30ec18e`) e la nuova base. Conteggi rispetto allo SHA fissato,
  non rispetto a `main` che puo' avanzare durante o dopo la scansione.
- Non sono enumerati tutti i rami non predefiniti di ogni fork. I rami delle PR aperte sono
  censiti separatamente; non attribuire a questa ricerca una verifica di ogni esperimento privato.

Inventario riproducibile in `ricognizioni/20261001/`: metadati, elenco dei 326 confronti, i 35 fork
avanti, PR aperte/selezionate, commit upstream e commit dei due fork piu' pertinenti.
`strumenti/ricognizione_strata.py` ripete la scansione e puo' riprendere con `--resume`;
il materiale completo letto e' conservato in `.codex_runs/strata_ricognizione_20261001/`.

## 0.1.31: evitare di reintegrare cose gia' arrivate

La [0.1.31](https://github.com/Niko1221/Strata/commit/9259cad4cfa3543cd3b8decab5962672b968c649)
ha gia' assorbito:

| Lavoro | Stato nella nuova base | Conseguenza per noi |
|---|---|---|
| #270, attenzione prefill sui tensor core di Turing | [`b6bdc70350`](https://github.com/Niko1221/Strata/commit/b6bdc70350), piu' follow-up `d9cbe3c349` | non applicare di nuovo 0014; il follow-up sceglie la scheda per chiamata |
| #242, IQ decode-once anche sulle proiezioni dense | [`8ec94aa228`](https://github.com/Niko1221/Strata/commit/8ec94aa228) | supersede 0007 sugli esperti e copre anche la parte densa; A/B con `STRATA_OLD_IQ_MMVQ=1` |
| #258, tile HC 1280 sm75 | `68f1362b26` | non riapplicare 0010 |
| #186, HC a due kernel | `de3f0454a7` + `8895c1263d`, opt-in | non riapplicare 0012/0013; #315 resta una candidata separata |
| Fix server FIFO, tokenizer heap, tool call troncate, lettura GGUF Windows | presenti | utili per agenti e avvio, non sono percentuali nuove di decode da sommare |

Le PR #242/#270 risultano **chiuse senza `merged_at`**, ma il lavoro e' presente nei commit
upstream: lo stato del pulsante merge non sostituisce il controllo del codice.
La #284 (commit async) risulta ancora aperta; conservare 0011 quando si integra la nuova base.

La 0.1.31 introduce anche formati Unsloth, GGUF diviso e tier SSD/RAM. Non serve cambiare modello
o pack per misurare le ottimizzazioni sul nostro IQ3_XXS. Verificare la compatibilita' delle patch
elastiche con la nuova gestione delle sorgenti e i prestiti del prefill; non aggiornare il clone
operativo con un `pull` indiscriminato.

## Il fork piu' pertinente: jklnvlink/Strata-2080ti

[Repository](https://github.com/jklnvlink/Strata-2080ti), ramo `main`, SHA dello snapshot
`235350960d853674f0279e5838a16e68e71be2bd`: **15 commit avanti, zero indietro** rispetto
alla 0.1.31 fissata. Specifico per sm75; le misure riportate dall'autore sono su **due 2080 Ti
22 GB**, piattaforma X99/DDR3, soprattutto Coder IQ1_M e prompt 1k/4k/28k.
Non sono misure sul nostro IQ3_XXS, su una singola scheda o a 131k/250k.

| Candidato | Commit | Evidenza dell'autore | Valutazione |
|---|---|---|---|
| Dequantizzazione dei pesi densi con scritture vettoriali | [`ea158a93ed`](https://github.com/jklnvlink/Strata-2080ti/commit/ea158a93ed30340092f1bf4a13522231062453f5) | circa +5% prefill; aritmetica dichiarata invariata | primo esperimento perche' delimitato e verificabile bit per bit |
| Proiezioni HC del prefill tramite FP16 tensor core | [`56495c36cb`](https://github.com/jklnvlink/Strata-2080ti/commit/56495c36cb749492300a07098775b45a8436be2a) | HC 3610 → 910 ms, prefill 28k 1372 → 1565 t/s (+14%) | opportunita' maggiore; richiede verifiche numeriche del prefill |
| Indexer block scores: otto blocchi per warp | [`95afc8d39a`](https://github.com/jklnvlink/Strata-2080ti/commit/95afc8d39aeff1d7f34a89c2444f737ffdb7c4a0) | select 70 → circa 45 ms/chunk, totale +1–2% | candidato secondario bitwise da verificare su sm75 |
| Gather esperti raggruppato | [`496a4f3a19`](https://github.com/jklnvlink/Strata-2080ti/commit/496a4f3a195b98a935c0ac1fd1f5dfbf46ab3f58) | una launch per gruppo, totale 28k +0,4–1,6% | piccolo, controllare eventi e vita degli slot del ring |
| `moe_combine` float4 | [`caf592c5da`](https://github.com/jklnvlink/Strata-2080ti/commit/caf592c5daf59c95bf315ff487ceab08f4aadefb) | kernel migliore, totale entro rumore | priorita' inferiore |
| Attention a un solo stage + pipeline di registri | `4984829100` | vantaggio totale entro rumore | base di ricerca, non un incremento misurato da sommare |

I guadagni sono **dichiarati dall'autore**, non replicati qui e non additivi. Non proiettare
automaticamente +14% sugli 809–811 t/s della nostra SOTA.

### Vincoli tecnici dell'HC FP16

L'arena conserva i pesi BF16; la proiezione li converte in uno staging da circa 6,55 MB per matrice,
evitando una copia permanente da circa 1,9 GB. Ci sono pero' anche immagini **FP16 delle attivazioni**,
mentre il percorso originale usa immagini BF16. Cambiano arrotondamenti e accumulazione:
non trattare il percorso come identico bit per bit solo perche' l'autore descrive la conversione
dei pesi come esatta. Sul nostro modello vanno controllati range, overflow/underflow, logits e
qualita' a contesto lungo.

Il fork stesso documenta correzioni necessarie: inizialmente mancava la scrittura di un'immagine
FP16 (`gr_write_norm_rs`), causando needle 0/3; contabilita' dei buffer corretta in `500d12e0ca`
e `bdea4cb4b8`; gate esatto cc 7.5 in `b4f8a4453c`. **Non prelevare il primo commit da solo**
senza includere o ricostruire questi fix. La bozza MTP resta BF16 nel codice finale: l'autore
riporta perdita di accettazione quando l'aveva spostata sul percorso FP16.

## Altre piste

- [#282](https://github.com/Niko1221/Strata/pull/282): prefill auto fino a 16.384/32.768 token,
  meno streaming ripetuto degli esperti. Autore: +15% a 32k su 5090/IQ2_XS. Patch piccola ma
  memoria maggiore: provare solo quando il prestito della cache lascia il margine richiesto e
  mantenere i checkpoint allineati. Il nostro obiettivo resta 262.144, non un contesto ridotto.
- [#317](https://github.com/Niko1221/Strata/pull/317): keep-alive SSD PLE, latenza delle letture
  dopo pause. Priorita' per robustezza/TTFT quando il log dimostra quel problema, non per un
  record di decode continuo. Misurata dall'autore su SN7100: non assumere lo stesso difetto nel nostro SSD.
- [#320](https://github.com/Niko1221/Strata/pull/320): corregge colonne del profiler
  `STRATA_VERIFY_PROFILE` (collisione slot e sottrazione unsigned). Utile prima di nuove analisi
  per kernel; non cambia il calcolo o la velocita'. I nostri log `STRATA_SPLIT_TIMING` sono un'altra misura.
- [#309](https://github.com/Niko1221/Strata/pull/309): evita ricattura completa delle conversazioni
  a cache piena. Utile quando attiveremo piu' conversazioni; non agisce sulle corse attuali che la disabilitano.
- [DmitriyW9/Strata](https://github.com/DmitriyW9/Strata): cinque commit propri, aggiornato alla
  stessa base; dequantizzazione FP16 di gate/up e PLE. Codice interessante ma senza una misura
  A/B pertinente e una validazione numerica comparabile nella documentazione letta.
- [gputier/StrataGP](https://github.com/gputier/StrataGP): 228 commit propri, 265 upstream mancanti.
  Ha ormai misure GPU (5090, 29/9: circa +11% decode e +49% prefill sul prompt 23k contro una base
  0.1.21), ma molte ottimizzazioni sono gia' upstream e la sua ammissione GPU richiede sm80+.
  Usarlo come catalogo per isolare il lavoro ancora nuovo, non trasferire il guadagno alla nostra base.
  Router e indexer multi-token sono gia' nel nostro `verify.cpp`; niente doppio conteggio.

## Cosa non inseguire adesso

- [#343](https://github.com/Niko1221/Strata/pull/343): **GEMV BF16 di decode** sui tensor core
  Turing risulta 1,3–2,2 volte piu' lento nel banco RTX 2070. Non contraddice il fork HC:
  quello accelera **GEMM del prefill**, con molte righe. Limite della prova #343: banco insieme
  al motore sulla stessa GPU; e' evidenza negativa utile, non una legge su tutte le forme.
- Fork [tntcannon5000/Strata](https://github.com/tntcannon5000/Strata): batching fra richieste,
  ancora sperimentale, con fallimenti di validazione documentati e revert recente. Fuori
  priorita' rispetto alla velocita' e correttezza della singola conversazione.
- NVFP4 [#353](https://github.com/Niko1221/Strata/pull/353), AMD, Volta/Pascal, macOS, 4 GB VRAM:
  hardware/modelli diversi; non miglioramenti immediati per il nostro IQ3_XXS su sm75.
- [webpolis/Strata](https://github.com/webpolis/Strata), [RX5950XT/Strata](https://github.com/RX5950XT/Strata)
  e [13600k/Strata-for-daniel](https://github.com/13600k/Strata-for-daniel): spunti per la 3060
  quando tornera', ancora fuori perimetro della singola 2080 Ti.

## Sequenza autorizzata

1. Esportare sorgenti 0.1.31 in una cartella di laboratorio nel checkout autorizzato. Il clone
   operativo `D:\ds4_work\strata\Strata` resta sul suo `main` +13 commit; nessun checkout,
   stash, merge o nuovo branch/worktree. Fetch degli oggetti sorgente consentito dalla ripresa.
2. Portare 0001–0006, 0008–0009 e 0011 se ancora necessarie; eliminare le duplicazioni 0007,
   0010, 0012, 0013 e #270 gia' presenti upstream. Non inserire #315 nello stesso confronto.
3. Compilare sm75+86, parita' e avvio a KV 262.144, poi riferimento 0.1.31 sulle stesse fixture.
4. Variante di dequantizzazione vettoriale, parita' e confronto; poi variante HC FP16 completa
   dei fix, controlli numerici e qualita', confronto separato. Nessuna somma di percentuali fra varianti.
5. Confermare a 131k; il riempimento vicino a 250k resta una prova distinta ancora da completare.
   Promuovere solo un eseguibile concretamente validato; conservare la #270 come ripristino.
