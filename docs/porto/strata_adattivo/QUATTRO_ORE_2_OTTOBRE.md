# Quattro ore Strata sm_75 — 2/3 ottobre 2026

Finestra autorizzata: 19:11:07–23:11:07 UTC (21:11–01:11 Roma). Nessun carico artificiale; motori modello sequenziali. Le build sovrapposte a QA erano prove di correttezza senza misure prestazionali.

## Esito e stato operativo

Il top-k dinamico non conferma una nuova SOTA: il primo A/B/A +5,39% non regge al controllo con quattro coppie intercalate nello stesso processo. Daily 0.1.36, spec4, cache auto/elastica, KV INT8 262144, residente32768 conservati. Il candidato 0.1.37 e le patch sono esportazioni locali; fork/main e launcher non aggiornati.

Pubblicazione bloccata: il connettore GitHub rifiuta `create_blob` e l'aggiornamento dellaPR512 con403 `Resource not accessible by integration`; il profilo locale nega scritture nel fork e nel Daily e precedentemente in .git/index.lock. Il browser ha bloccato l'apertura di GitHub indicando permesso negato dall'utente: nessun nuovo tentativo di scrittura o aggiramento dopo il rifiuto. L'utente ha già autorizzato accesso/modifiche nella chat; le restrizioni effettive degli strumenti restano presenti. Nessun workflow aggiunto.

## Misure ripetibili

Aggiornamento 3 ottobre: l'accesso completo ha ripristinato le scritture Git locali
e il push autenticato. Il blocco descritto sopra è lo stato storico della corsa;
il report e le evidenze sono ora pubblicati sul branch research autorizzato.
Nessun commento al maintainer o nuova PR accompagna questo recupero documentale.

Baseline reale Daily: prompt fresco131248, prefill970,01t/s, decode43,916t/s; follow-up131239 con131072 riusati, decode38,308t/s; aggregato40,92t/s. Startup6201slot, crescita elastica6774. Una sola sessione: non è una curva completa né una nuova SOTA.

| Top-k dinamico, stesso motore037 | Token contesto reali | Mediana OFF | Mediana ON | Variazione |
|---|---:|---:|---:|---:|
| 20k | 20046 | 47,612 | 46,334 | −2,685% |
| 131k | 131118 | 44,972 | 45,489 | +1,148% |

Quattro coppie1024token/profondità; argmax, lookup3/spec4 operativo, PCIe0,28 esplicito, cache elastica. A131k una coppia è negativa e la dispersione del riferimento1,24% è simile al guadagno. Soglia preventiva3% non superata. Le sequenze generate delle coppie non sono identiche: il throughput non sostituisce il gate di correttezza. Mode0/1 verificato nei log nativi10/8volte.

Kernel top-k catturato: 228casi con1,2,3,4,6,8,11righe, contesti1111–262144, pareggi, zeri, righe miste e replay delle stesse graph OFF/ON; ID esatti. V1 a131k circa−30% con1riga/−54% con8righe sul solo kernel. Il vantaggio non si trasferisce integralmente alla pipeline.

Shared-LUT IQ2_XS/IQ3_S sm75: microkernel circa8–15% più veloce in molte forme, parità bitwise; A/B/A sul modello circa40,31t/s contro media riferimenti40,28: nessuna SOTA. Quattro warp non migliorano uniformemente T2/T6. Combinefloat4 circa1–3%, fase già breve. CPU AVX2 gather: 480casi bitwise, generalmente più lento; casoNT1 favorevole già eguagliato dal vecchio kernel senzaprefetch e non è il percorso predefinito IQ_MT_MIN2. Queste patch restano sperimentali.

PR453 ringMTP: 30risposte corrette e768righe teacher finite/bitwise, KL0, top1 100%; prefill ON976,21 contro riferimento valido968,71, +0,77%. Primo OFF524,70 mantenuto come outlier. Nessuna promozione per il solo guadagno dichiarato dall'autore. CalibrazionePCIe/minp: +3,73% a20k con(.15,.7), −0,48% a131k con(.15,.85); nessun cambio globale da un solo contesto.

## Correttezza del candidato combinato037

Stato: **completed**; gate **True**. Riferimento installato036 / candidato037 con dinamicoON / riferimento036. Cache laboratorio6167, prefill2048, PCIe0,28, spec4/lookup0, reasoninglow; dieci oracoli completi per braccio, quattro profondità20/32/65/131k, 64continuazioni teacher per profondità ebraccio. Fences JSON registrati separatamente dal risultato semantico; non cancellare i fallimenti del vecchio gate strict. Suite server:114test passati dopo l'aggiunta del controllo runtime. Le prove non certificano qualità generale del modello o contesto250k.

## PR512 isolata su upstream037

[PR512](https://github.com/Niko1221/Strata/pull/512): OPEN/DRAFT, non mergiata, head42131caf. Preparata copia pura db4f91a più quattro soli file della PR, senza port fork/altre patch. Build completa e16test selezione bitwise passati. Primo tentativo6167slot fermato prima del prompt perché887MiB erano sotto il margine1000MiB. Ripetuto capacity/active/capacity con5357slot effettivi, budget richiesto4000, KV262144, PCIe0,28; non confondere con il Daily elastico.

Stato A/B/A: **completed**.

| Braccio | Exit | Prefill fresco t/s | Decode aggregato t/s |
|---|---:|---:|---:|
| A1 | 0 | 457.26 | 39.338 |
| B | 0 | 521.45 | 40.568 |
| A2 | 0 | 774.41 | 40.597 |

Riferimenti457,26/774,41t/s, attivo521,45: il primo confronto +14% non regge alla ripetizione. Dispersione riferimenti51,50%; candidato−15,33% rispetto alla media, confronto inconcludente: non attribuire un guadagno o una regressione alla patch. La PR remota resta DRAFT; nuovo corpo descrizione locale in `PR512_VALIDATED_BODY.md`, aggiornamento remoto rifiutato403. Il pacchetto di quattro file conserva lo scope originale; non sostituire l'albero ufficiale con la copia di build che omette i workflow.

## Nuova PR547 — contabilizzazione del prestito alla cache

[PR547](https://github.com/Niko1221/Strata/pull/547), head4072b708: `bytes_needed` ora segue `carve`, non conta `xn` nel percorso GR fused e conta sempre `grs`; propagato `srcp` nei quattro chiamanti. Port preserva esplicitamente tutte le allocazioni fp16sm75. Risparmio teorico40944byte/token, circa0,312GiB a8192; il beneficio dichiarato su5090 non è misura2080Ti. PR546 riguarda layout fused con pack misti; non attivato nel nostro Daily. PR540 è perVolta e cambia anche un kernel decode: da valutare a parte, non applicata.

Gate qualità contro le stesse due baseline036, SHA e argomenti verificati: **completed**, pass **True**.
Stato A/B/A operativo037 / +547 /037: **completed**.

| Braccio | Exit | Prefill fresco t/s | Decode aggregato t/s |
|---|---:|---:|---:|
| A1 | 0 | 955.32 | 39.775 |
| B | 0 | 966.42 | 41.346 |
| A2 | 0 | 529.89 | 41.017 |

Riferimenti955,32/529,89t/s, candidato966,42: forte dispersione anche in questo confronto. Il +1,16% della prima coppia e la media distorta dall'ultimo riferimento non dimostrano una nuova SOTA. Decode candidato41,346 contro media riferimenti40,396 (+2,35%), sotto soglia3%. Gli outlier e il maggiore staging del riscaldamento restano registrati; la causa non è stata isolata. Correttezza passata, vantaggio globale di velocità inconcludente.

## Ripresa, evidenza e limiti

Snapshot periodici commit/fork/PR nel sottoalbero `github`, compreso stato PR512 e nuovi fork. Nessun contatto con altre chat o commento pubblico. Copie semplici di sorgenti, nessun branch/worktree nuovo. Patch complete controllate con `git apply --no-index --check` e pacchetto sperimentale in `C:\Users\imanu\Documents\Codex\2026-10-01\https-github-com-imanu86-moe-aggressive\strata-main-alignment\fourhour_20261002\delivery-v2`. L'eseguibile candidato SHA2818665c… è lo stesso della prova; dinamico disattivato salvo `STRATA_TOPK_DYNAMIC=1`. Nessun automatismo di installazione.

Manifest dei file salvati in `corse_2080ti/20261002_quattro_ore/manifest.json`; binari, modelli e logits raw restano locali. Preservati anche outlier, tentativi falliti e limiti: non tutte le PR esplorate hanno un A/B/A completo, né abbiamo una curva conversazionale20k→250k. Per aumentare t/s privilegiare il percorso critico CPU/host e il prestito/refill durante prefill; guadagni del solo kernel non provano saturazione della banda fisica.

Tutti i motori propri chiusi entro la finestra; hash Daily/server/config/launcher invariati, circa68GiB RAM disponibili e19105MiB VRAM liberi al controllo finale. Prossimo passo: isolare i forti outlier di prefill con controllo nello stesso processo, warm-up del percorso completo e timing di staging/paging; poi ripetere le patch con riferimenti stabili prima della promozione. Le prove037 usano PCIe0,28 esplicito: il nuovo auto037 resta da validare.
