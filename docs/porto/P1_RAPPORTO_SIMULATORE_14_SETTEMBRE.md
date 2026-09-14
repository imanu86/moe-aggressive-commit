# P1 — Rapporto del simulatore della cache CPU/GPU

14 settembre 2026. Fase **P1** del [piano CPU/GPU](PIANO_CPU_GPU_14_SETTEMBRE.md). Specifica: [P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md](P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md). Strumenti: `docs/porto/strumenti_p1_cache_cpu_gpu/`.

**Solo lavoro analitico su CPU.** Nessun server avviato, nessuna compilazione, nessun uso della GPU, nessuna modifica ai sorgenti del motore né agli alberi `qwen38_clean\source` e `Documents\Codex\2026-09-13`. Nessuna misura di velocità e nessun t/s è ricavabile da questo rapporto.

## 1. Che cosa è stato verificato

| Verifica | Esito |
|---|---|
| Riproduzione dei 36.913 piani storici con `cpu_max = 0` | **36.913 piani confrontati, 36.866 confronti di stato, zero differenze** |
| Il confronto ha potere discriminante (controllo negativo) | Anticipando di un passo il decadimento: **58.802 differenze** su 73.779 confronti (25.007 di piano, 33.747 di stato, 48 di stato finale) |
| Nessun residente fantasma con `cpu_max` 1 e 2 | Zero, su tutte e quattro le corse |
| Invariante 1 sulle somme, in ogni corsa | Vero nel tratto caldo e sul totale |
| Scenari dedicati con CPU attiva | **13 su 13 superati** |

I 36.913 piani storici **esistono**: `trace64.jsonl`, SHA256 `690d7c26e248d05a83f244c477e5d55fe644b40d481c3c90ebb9f63ea9861212`, in `C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\freetoken_audit\replay_verify\`. È la stessa traccia di `cache_policy_results.json` e dello ZIP di evidenza. Non è stato necessario ripiegare su `routes.bin`.

Struttura della traccia: `k = 10` in tutti i record, `rows = 1` in 36.819 record e `rows = 2` in 94 (tutti dentro i primi 64 passi), ID in `[0, 511]`, 95 incarnazioni su 48 strati fisici, `bytes_per_miss` 1.971.200 su 47 strati e 2.329.600 sullo strato 2 — coerente con D07.

## 2. Come è fatto il confronto con `cpu_max = 0`

Il riferimento è la classe `Cache` di `analyze_trace.py` (copia nel repository in `docs/porto/strumenti_qwen38_13settembre/`, SHA256 `6f756836bcf89ed4166a183ca8541631624293687800e9642b76ba47f6eeb165`, identica a quella dell'audit), che sulla stessa traccia riproduce senza differenze i miss misurati dalla GPU. Il riferimento applica l'ammissione **subito**; il simulatore nuovo la applica **differita**, come il kernel. Per ogni piano si confrontano due cose:

1. **Contenuto del piano**: numero di richieste uniche, numero e identità dei miss nell'ordine degli indici unici, slot assegnati nello stesso ordine, esperti sfrattati nello stesso ordine.
2. **Stato dopo il commit**: mappatura `expert_for_slot` e `slot_for_expert`, frequenze, epoche e **ordine totale di recenza degli slot**. Lo stato del simulatore al passo `t+1`, subito dopo la fase differita, viene confrontato con lo stato del riferimento dopo il passo `t`.

La recenza si confronta come ordine e non come valore: il dispositivo riserva `n_routes` tick per piano e ne consuma `n_unique`, il riferimento ne consuma `n_unique`, quindi i numeri assoluti divergono per costruzione mentre l'ordine totale — l'unica cosa che la scelta della vittima legge — coincide.

Sono esclusi dal confronto di stato i 95 primi piani (nessuno stato precedente) e i 47 ultimi piani delle incarnazioni sostituite in corsa: `36.913 - 95 + 48 = 36.866`. I 47 piani pendenti mai applicati sono la conseguenza dichiarata del commit differito, non una differenza.

## 3. Comandi riproducibili

Un solo processo Python alla volta; nessun argomento contiene credenziali.

```powershell
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strumenti_p1_cache_cpu_gpu
$T = "C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\freetoken_audit\replay_verify\trace64.jsonl"

python replay_p1.py --trace $T --cpu-max 0 --out p1_replay_cpu0.json
python replay_p1.py --trace $T --cpu-max 0 --controllo-negativo --out p1_controllo_negativo.json
python replay_p1.py --trace $T --cpu-max 1 --strato-escluso 2 --out p1_replay_cpu1.json
python replay_p1.py --trace $T --cpu-max 2 --strato-escluso 2 --out p1_replay_cpu2.json
python replay_p1.py --trace $T --cpu-max 1 --cpu-order freq --strato-escluso 2 --out p1_replay_cpu1_freq.json
python replay_p1.py --trace $T --cpu-max 2 --cpu-order freq --strato-escluso 2 --out p1_replay_cpu2_freq.json
python test_scenari_p1.py
```

`replay_p1.py` esce con 1 se trova una differenza o un residente fantasma; `test_scenari_p1.py` esce con 1 se uno scenario fallisce. Tutte le corse sopra sono uscite con 0, tranne il controllo negativo che deve fallire e fallisce.

| File | SHA256, primi 16 |
|---|---|
| `cache_cpu_gpu.py` | `83c7f864849195a6` |
| `replay_p1.py` | `94a6e8fcb234e44a` |
| `test_scenari_p1.py` | `d71d63fff7461d20` |

## 4. Risultati numerici

### 4.1 Riproduzione della politica attuale

| Finestra | Piani | Richieste uniche | Colpi | Miss | Colpi % | Payload dei miss |
|---|---:|---:|---:|---:|---:|---:|
| Intera traccia | 36.913 | 369.831 | 275.564 | 94.267 | 74,51079% | 187.062.758.400 |
| Passi oltre 64 | 33.747 | 337.470 | 254.944 | 82.526 | 75,54568% | 163.807.436.800 |

Coincide cifra per cifra con `cache_policy_results.json` del 13 settembre e con il tasso diretto misurato dai contatori del dispositivo. Sfratti effettivi nella traccia intera: 89.789.

### 4.2 Curve con `cpu_max` 1 e 2 — **solo informative**

Tratto caldo (passi oltre 64), strato 2 escluso dal ramo CPU, 337.470 richieste uniche in tutte le righe.

| `cpu_max` | Ordine | Colpi GPU | Miss GPU | Miss CPU | Job CPU | Byte caricati | Colpi GPU % | Byte rispetto a `cpu_max=0` |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | 254.944 | 82.526 | 0 | 0 | 163.807.436.800 | 75,55% | 1,000 |
| 1 | route | 246.729 | 62.300 | 28.441 | 28.441 | 123.937.945.600 | 73,11% | 0,757 |
| 2 | route | 238.192 | 45.185 | 54.093 | 54.093 | 90.200.857.600 | 70,58% | 0,551 |
| 1 | freq | 250.853 | 59.240 | 27.377 | 27.377 | 117.906.073.600 | 74,33% | 0,720 |
| 2 | freq | 245.593 | 41.160 | 50.717 | 50.717 | 82.266.777.600 | 72,77% | 0,502 |

Come vanno letti questi numeri, e come **non** vanno letti:

- Non sono t/s e non ne implicano nessuno. Il piano stabilisce esplicitamente che con la nuova ammissione non si pretende lo stesso tasso di colpi; qui infatti il tasso **scende**, perché i miss serviti dalla CPU non vengono ammessi e tornano miss al passo successivo.
- I byte non caricati non sono tempo risparmiato: il calcolo CPU ha un costo proprio, non misurato qui, e la sovrapposizione con la GPU è la vera variabile (rapporto del 13 settembre).
- Il carico CPU **non** si può calcolare dalla traccia storica. Sommando `min(cpu_max, miss)` sui miss storici si otterrebbero 26.737 job con `cpu_max=1` e 46.503 con `cpu_max=2`; le corse reali ne producono 28.441 e 54.093, cioè +6,4% e +16,3%. La partizione cambia la traiettoria della cache: i miss futuri non sono quelli della traccia. Vale la regola già registrata, le leve di residenza cambiano la traiettoria.
- L'ordine `freq` domina l'ordine `route` su questa traccia in entrambe le colonne — più colpi e meno byte — ma è **una sola traccia**, su un carico di 703 token circa, e legge lo stato della cache dentro la partizione. È un candidato per P4, non una decisione di P1.

Contesto della traccia calda: 33.747 piani, di cui 7.010 senza alcun miss (20,8%) e 20.963 con uno-quattro miss (62,1%); l'82,9% dei piani ha al massimo quattro miss. Lo strato 2, escluso, mantiene con `cpu_max=2` i suoi 3.470 miss GPU e zero miss CPU: il fallback è neutro come richiesto.

### 4.3 Scenari dedicati (13 su 13 superati)

| Scenario | Che cosa dimostra |
|---|---|
| `cambio_di_vittima` | Con un miss servito dalla CPU cambiano sia la sequenza delle vittime sia l'insieme dei residenti finali. |
| `vittima_argmin_lfu` | La vittima è l'argmin indipendente di (frequenza efficace, ultimo uso, indice): LFU, non LRU. |
| `saturazione` | Cache piena, quattro miss nuovi: con `cpu_max=0` si sfrattano quattro residenti, con `cpu_max=2` soltanto due e le due route CPU condividono un unico slot alias; `n_routes` oltre gli slot è rifiutato. |
| `riuso_ravvicinato` | Un esperto servito dalla CPU al passo `t` e richiesto a `t+1` è di nuovo un miss, non è residente, e la sua frequenza logica è stata comunque aggiornata. |
| `invalidazione_incarnazioni` | La nuova incarnazione parte vuota, zero colpi; l'ammissione pendente della vecchia è persa e non viene applicata altrove. |
| `id_ai_limiti` | ID 0 e 511 accettati e classificati; `-1` e `512` rifiutati. |
| `zero_uno_due_job_cpu` | `n_cpu = max(0, min(cpu_max, n_miss, n_unique - 1))` su nove combinazioni; con un solo unico non si usa la CPU, perché mancherebbe la route GPU reale per l'alias. |
| `stesso_esperto_due_token` | Con due token lo stesso esperto CPU genera **due** job: i pesi si deduplicano, il calcolo no. |
| `pesi_zero_e_non_uniformi` | Peso GPU esattamente zero sulle route CPU, pesi GPU rimanenti identici bit per bit, peso originale nel job; nessuna rinormalizzazione. |
| `fallback_non_supportato` | Strato non idoneo con `cpu_max=2`: firme dei piani e residenti identici a `cpu_max=0`. |
| `errore_job_cpu` | Il piano fallito non resta pendente, non ammette nulla, invalida i residenti degli slot già sovrascritti dal gather e blocca ogni uso successivo finché non si esegue la pulizia esplicita. |
| `alias_slot_protetto` | L'alias è lo slot di una route GPU reale del piano corrente, protetto e con le tre banche pronte prima del consumo. |
| `frequenza_include_cpu` | 12 aggiornamenti di frequenza contro 8 scritture di recenza su quattro piani da tre unici con `cpu_max=1`: la contabilità logica include le route CPU, la recenza no. |

## 5. Che cosa resta aperto

1. **I pesi del router non sono nella traccia.** Il simulatore usa pesi sintetici deterministici, con una route a peso zero per piano. È verificata la **contabilità** dell'invariante 5 (ogni coppia una volta sola, peso originale, nessuna rinormalizzazione), non un valore numerico del modello. La verifica numerica del contributo CPU contro il percorso interamente GPU appartiene a P3.
2. **Invarianti 6 e 7 solo in parte.** Il simulatore copre la macchina a stati dell'errore e il fallback deciso prima dell'invio. Concorrenza, callback, mutex e durata dei buffer non sono simulabili in Python e restano a P2, con i controlli indicati nel contratto.
3. **Una sola traccia, un solo carico.** 36.913 piani da una sessione di 768 token generati con MTP spento e contesto effettivo di 867 token. Non copre prefill, contesti lunghi, più turni né la speculazione. Le curve del §4.2 vanno rifatte su una traccia del banco congelato di P0 prima di sceglierne l'ordine.
4. **Lo schema della traccia va esteso** con un campo per i miss CPU prima di riusare `LLAMA_MOE_ROUTE_TRACE` con la CPU attiva, altrimenti un replay futuro confronterebbe grandezze diverse.
5. **Tre contatori invece di due** nel dispositivo, e due percentuali distinte in `report_hits`: con i miss CPU la formula attuale `1 - mancanti/richiesti` li conterebbe come colpi.
6. **`rows > 1`.** Il contratto è scritto per coppie token/esperto e gli scenari coprono due token, ma la semantica completa della speculazione resta a P5.
7. **Il costo delle righe GPU fittizie** dell'alias non è misurabile qui: è una misura di P3/P4.

## 6. Bozza di voce per il registro

> **14 settembre 2026 — P1, contratto e simulatore della cache.**
> *Ipotesi:* la politica attuale può essere riscritta con l'ammissione differita esplicita e con la partizione dei miss in CPU/GPU prima dell'assegnazione degli slot, senza cambiare nulla quando `cpu_max = 0` e senza produrre residenti fantasma quando `cpu_max > 0`.
> *File toccati:* `docs/porto/P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md`, `docs/porto/P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md`, `docs/porto/strumenti_p1_cache_cpu_gpu/` (`cache_cpu_gpu.py`, `replay_p1.py`, `test_scenari_p1.py`, sei JSON di risultato). Nessun sorgente del motore, nessun binario, nessun launcher, nessun file sotto `qwen38_clean\source` o `Documents\Codex\2026-09-13`.
> *Configurazioni confrontate:* traccia `trace64.jsonl` SHA256 `690d7c26…`, 64 slot, 512 esperti, `cpu_max` 0/1/2, ordini `route` e `freq`, strato 2 escluso dal ramo CPU; riferimento `analyze_trace.py` SHA256 `6f756836…`.
> *Risultato e limite:* con `cpu_max = 0`, 36.913 piani confrontati e 36.866 confronti di stato, **zero differenze**; il controllo negativo che anticipa il decadimento di un passo produce 58.802 differenze, quindi il confronto discrimina. Con `cpu_max` 1 e 2: zero residenti fantasma, invariante 1 sempre soddisfatto, 13 scenari su 13 superati. Limiti: pesi del router sintetici, invarianti 6 e 7 coperti solo nella parte di stato, una sola traccia e un solo carico, nessuna misura di velocità.
> *Decisione:* proseguire. Adottare per P3 l'ordine deterministico «primi miss in ordine di indice unico», già materializzato dal kernel e indipendente dallo stato della cache; tenere `freq` come prima alternativa da confrontare in P4. Portare nel kernel la separazione fra `n_misses` (miss GPU) e miss CPU, aggiornando insieme gather, commit differito, contatori e traccia.
> *Regressioni aperte:* nessuna introdotta; restano i rischi già registrati sul commit differito e sul costo delle righe GPU fittizie.
> *Stato dei processi avviati:* nessuno; solo processi Python seriali su CPU, tutti conclusi.
> *Prossima azione:* P0 congela le fixture e la baseline; poi P2 sull'esecutore, riusando gli assert degli invarianti 2, 4 e 5 come controlli di stato attorno all'interfaccia host.
