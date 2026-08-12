# drain4fix — la leva era inerte a flag acceso: causa vera e correzione

Data: 2026-07-29. Nessuna compilazione, nessun server, `D:\` non toccato.
Scritto solo in `.microbench/drain4fix/`.

Base del diff: `ds4-p4a/ds4_cuda.cu` del tree CORRENTE
(drain4+shared1+dspark1+dspark2+logids composti), SHA-256
`ebf06a37744047fde71cd9c442e1c8c0884df8300a5ac5fe1eefc0b5acaad573`.

Patch: `drain4fix.patch`, SHA-256
`c233ea8370ee63d1ccb2a9b65fc8ce78d85493d7e6d36626e76ae6f893cf1304`,
`git apply --check` PASS sul tree corrente, `--numstat` +66/−10 su un solo
file; roundtrip base+patch byte-identico verificato. Tutti gli hunk stanno
dentro il codice di drain4: shared1/dspark1/dspark2/logids NON toccati
(verificato: le loro +156 righe in ds4_cuda.cu stanno in 7 punti estranei
alle zone DOV; l'unica riga dentro il worker e' il log-ids a monte del
servizio, senza interazione).

Le righe «:N» sotto sono del file DOPO drain4fix; «base :N» = tree corrente
prima della fix.

## 1. Causa vera dell'inerzia (punto 1 del mandato)

**NON e' la matrice del dispatch.** Verificata riga per riga sul tree del
run (base :49814-49870): tutti e quattro i rami (g73×general) propagano
`dov_enabled` su launch, general e worker; per il caso concreto del run D1
(g73=0, general=0, scoped=1, DOV=1) l'istanza selezionata era gia'
`cuda_moe_route_worker<false,false,true,true>` e
`routed_moe_launch_impl<false,false,true>` — il quarto parametro C'ERA.
Le 16 combinazioni worker e le 8 launch sono tutte raggiungibili; il ramo
scoped=1 del caso in esame estende DOV correttamente (base :49857-49869).

**La causa e' un veto RUNTIME dentro l'arm, messo da drain4 stessa.** Alla
base :40020:

```cpp
if (cuda_g133_shared_policy_active()) return 0;   /* SILENZIOSO */
```

`cuda_g133_shared_policy_active()` (base :28575-28579) =
`g133_enabled && mode != OFF && compose_prefill_mass_tiering`, cioe'
`DS4_G133_TIER=1` + `DS4_CUDA_PREFILL_TIER_COMPOSE=1` + tiering ENFORCE:
**l'intero assetto di campagna**. Il veto scattava su OGNI richiesta, l'arm
ritornava 0 in silenzio, ogni layer ricadeva sul drain bloccante: percio'
`dispatch=armed` ma `drain_overlap_ms=0`, `gpu_stall_on_drain_ms=0`,
regime identico all'ancora (219 vs 220 ms/token). Il difetto e' mio, di
drain4: avevo allargato il §3.3 del disegno («niente Q1/IQ1, dispatch mixed
su istanze DOV=false») a «mai armare sotto la policy condivisa», senza
accorgermi che la policy condivisa E' la campagna. Le altre due vie di
ritorno-0 silenzioso (eventi mancanti, errore CUDA pendente) sono escluse
dall'evidenza: la creazione eventi fallita logga forte
(`event-create-failed`, :38806 nel file fixato) e un errore pendente
persistente non convive con un run sano a 219 ms/token.

## 2. La correzione

### 2.1 Perimetro giusto del veto (:40040-40074)

Il divieto del disegno protegge i quattro lettori MIXED di
`drain_completed` — `q1-0-mixed-entry` (:51962), `q1-0-mixed-policy`
(:52752), `iq1-mixed-entry` (:53153), `iq1-mixed-policy` (:53390) — che
leggono `route_completed_*` come prova di quiescenza del lavoro di rotta.
Quei percorsi esistono solo se il processo serve rotte Q1_0/IQ1_S, cioe'
solo con un sidecar Q1/IQ1 mappato. Il veto diventa quindi:

```cpp
if (g_q1_0_sidecar_file_valid || g_q1_0_sidecar_host_base != NULL ||
    g_iq1_s_sidecar_file_valid || g_iq1_s_sidecar_host_base != NULL)
```

fatti di processo stabiliti al load del modello (:1097-1104), PRIMA di ogni
decode — niente stato che cambi sotto i piedi del worker. In campagna base
(nessun sidecar) il veto non scatta mai e la leva e' viva.

### 2.2 Nessun veto silenzioso mai piu' (:37058-37078, :40060-40074)

Ogni classe di veto dell'arm ora logga UNA volta per processo
(`cuda_moe_drain_overlap4_note_arm_veto`, bitmask `arm_vetoes_logged` nel
sidecar :36928, solo thread worker):

```
ds4: [drain-overlap4] result=arm-veto reason=q1-iq1-sidecar-present|events-missing|pending-cuda-error seq=.. layer=..
```

Se questa riga fosse esistita, il run D1 avrebbe dato la diagnosi alla
prima richiesta invece che a fine run. Il fallimento del record era gia'
loggato (`record-failed`, :40078-40086) e resta.

### 2.3 La riga di dispatch dichiara DOV (punto 2 del mandato) (:49859-49868)

```
ds4: [drain-overlap4] dispatch=armed g73=%d general=%d scoped=%d dov=%d
```

`dov=` in coda (i parser a chiave non si spostano). A flag spento la riga
non esiste, come prima.

## 3. Perche' e' LECITO armare sotto la policy condivisa (l'analisi che regge la fix)

I sei lettori di `drain_completed` nel tree corrente: :15960
(request-boundary), :47310 (route-failure-invalidate), piu' i quattro mixed
del §2.1. I mixed restano vietati dal veto. Gli altri due NON richiedono
«completed ⇒ upload drenato»:

- **route-failure-invalidate** (:47363, dentro il check di
  `route_failed_host`): gira solo su richieste FALLITE. Arm e failed sono
  mutuamente esclusivi per generazione (l'arm avviene solo con `ok` alla
  fine del servizio; ogni fallimento prende il ramo bloccante). L'overlap
  della generazione PRECEDENTE non puo' essere in volo li': il worker, per
  claimare e poi servire (e fallire) la generazione N, ha superato il
  claim-gate che prova — done-event dietro il waitEvent — il completamento
  fisico di upload(N−1). Quindi al momento dell'invalidate non esistono
  copie armate in volo: semantica identica a oggi.
- **request-boundary** (:15960, `ds4_gpu_dynamic_arena_request_begin`): il
  suo commento protegge «SSD-wrap commits» ed «epoch advance». Con un
  overlap dell'ULTIMO layer ancora in volo: (a) `cuda_q1_0_ssd_wrap_flush`
  consolida staging host del wrap verso il sidecar SSD — non legge ne'
  staging di rotta ne' VRAM; in piu' in questa campagna (G73_OPEN=0) la
  rotazione wrap non viene mai schedulata (poll e schedule stanno sotto
  `if constexpr (G73)`); (b) `cuda_moe_tiering_request_boundary_reset`
  (:32613-32619) fa solo report+reset di contatori; (c) l'avanzamento
  d'epoca marca le promozioni FUTURE — quelle della richiesta chiusa sono
  gia' committate all'arm con la loro epoca, come oggi lo erano al drain.
  Il riciclo di staging/slot resta comunque dietro il claim-gate
  (fail-closed), che con l'overlap prova anche il completamento fisico
  (I3 di drain4, invariato). Nessun invariante tocca il confine di
  richiesta in modo nuovo.

I quattro invarianti I1-I4 di drain4 non sono toccati dalla fix: cambia
solo QUANDO l'arm accetta, non cosa garantisce una volta armato.

## 4. Copertura del ramo di campagna SPLIT_FUSED=1, G73_OPEN=0 (punto 3 del mandato)

Verificata sul tree corrente, era gia' coperta (l'inerzia veniva SOLO dal
veto):

1. dispatch (g73=0, general=0, dov=1) → `routed_moe_launch_impl<false,false,true>`
   su entrambi i puntatori (:49870-49926); `ds4_gpu_routed_moe_one_tensor`
   usa il general dispatch (:49935-49937) → istanza DOV=true.
2. `split_fused_requested` non e' gated su G73 (:47757-47761); begin
   → passata hit → `routes_finish<false,true>(split_mode=2)` (:49008-49011).
3. Il fence del ramo split sta a :49131-49161 («split-before-miss-pass»),
   dopo il blocco G132/kernel Fable e prima della passata miss. Con
   general=0 (G132=false) il blocco Fable e' compilato via e il fence
   siede direttamente fra la finish e la passata miss — il posizionamento
   §3.2 degenera correttamente (non c'e' alcun kernel di ownership da
   lasciare sotto le copie).
4. Lato worker (ENFORCE): arm al drain finale (:41709), poll idle
   (:41819), ritiro al claim (:41879). Dopo la fix, in questa
   configurazione, nessun veto scatta.

Nota di misura: `gpu_stall_on_drain_ms` e' campionato attorno alla sync del
resolver nel ramo default-sync (enter :47147, exit :47158); se il run usa
`DS4_CUDA_MOE_ROUTE_NO_DEFAULT_SYNC=1` quella voce resta 0 per costruzione
mentre `drain_overlap_ms` si muove comunque (worker-side).

## 5. Servono due condizioni per armare? (punto 4 del mandato)

**No: il flag e' uno solo, `DS4_CUDA_DRAIN_OVERLAP4=1`** (piu' l'ordinario
stack di campagna gia' nel runner: worker delle rotte residenti attivo,
tiering). Non esiste una seconda condizione ambientale stile lane
(`CPU_LANE` + `CPU_LANE_GENERAL`). Pero':

- perche' i CONTATORI si muovano serve `DS4_CUDA_WORKER_PROFILE=1` (gia'
  standard nel protocollo; l'overlap in se' funziona anche senza);
- veti legittimi, ora SEMPRE dichiarati nel log alla prima occorrenza:
  sidecar Q1/IQ1 presente nel processo (`reason=q1-iq1-sidecar-present`),
  eventi non creati (`reason=events-missing`, preceduto dal log di
  `event-create-failed` alla prepare), errore CUDA pendente
  (`reason=pending-cuda-error`).

Runner: nessun flag nuovo da aggiungere. Unica avvertenza: nei run Q1/IQ1
con DOV=1 la leva resta volutamente spenta e ora lo DICE.

## 6. Neutralita' a flag spento

Invariata rispetto a drain4: ogni riga nuova della fix sta in codice
raggiungibile solo dalle istanze DOV=true (helper del veto, guardie
dell'arm) oppure dentro il ramo `if (dov_enabled)` gia' esistente del
dispatch (riga di log). Il campo nuovo `arm_vetoes_logged` sta nel sidecar
privato di drain4, non in struct condivise. A flag spento: zero chiamate,
zero rami nuovi eseguiti, stesso stderr.

## 7. SHA-256

```
ebf06a37744047fde71cd9c442e1c8c0884df8300a5ac5fe1eefc0b5acaad573  ds4-p4a/ds4_cuda.cu (base del diff, tree corrente con drain4+shared1+dspark1+dspark2+logids)
c233ea8370ee63d1ccb2a9b65fc8ce78d85493d7e6d36626e76ae6f893cf1304  drain4fix.patch
```
