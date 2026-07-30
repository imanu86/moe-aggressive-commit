# DEADLINEFIX v2 — lease coerente, init thread-safe e terminale senza pending ereditato

Data: 2026-07-30. Base: tree corrente indicato dal mandato. La patch v2 è
sostitutiva: si applica direttamente al tree corrente e non richiede la v1.

Applicazione:

```text
git apply .microbench/deadlinefix2/deadlinefix2.patch
```

La patch tocca solo `ds4-p4a/ds4_cuda.cu`. Non sono stati modificati i sorgenti
del tree di lavoro, non è stata eseguita alcuna compilazione e non è stato
avviato alcun server.

## SHA-256 e verifica statica

| Oggetto | SHA-256 |
|---|---|
| `ds4-p4a/ds4_cuda.cu` prima | `f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37` |
| `ds4-p4a/ds4_cuda.cu` dopo `git apply` | `2c700936fa17a0004de0bdbbf8a76c31ffd83a6092cf156f3e2218bb2854f5f1` |
| `ds4-p4a/ds4.c` prima e dopo (non toccato) | `2d97991e6037c434e484ab6a8c8cc2a364e7cf69aa403ad5e6baa815d3dd6e5c` |
| `deadlinefix2.patch` | `28b2daa286fb378d2104a012ffcdeb55b074a7cb5f0850d41e000513e8eb9829` |

`git apply --check --whitespace=error-all
.microbench/deadlinefix2/deadlinefix2.patch` è pulito sul tree corrente. La
patch è stata anche applicata end-to-end a una copia CRLF fresca; il suo hash è
quello “dopo” riportato sopra.

I riferimenti `ds4_cuda.cu:riga` seguenti sono al post-image verificato.

## Difetto 1 — ordine di pubblicazione della lease

È stata scelta la soluzione `deadline prima dei byte`, non la seqlock. Qui c’è
un solo writer della lease e servono due sole parole; l’ordine release/acquire
chiude direttamente la finestra osservata senza aggiungere una versione, un
campo di struct o un ciclo di retry del reader.

- Lettura chunked: il worker calcola e pubblica `D1` con
  `route_transient_read_deadline.store(..., std::memory_order_release)` e solo
  dopo pubblica `B1` con
  `route_transient_read_bytes.fetch_add(..., std::memory_order_release)`
  (`ds4_cuda.cu:32323-32337`). Anche il disarmo finale `D=0` precede il byte
  conclusivo.
- QD4: identico ordine, deadline rinnovata/disarmata a
  `ds4_cuda.cu:42434-42446`, poi byte pubblicati con release a
  `ds4_cuda.cu:42448-42449`.
- Consumer: a ogni snapshot adaptive acquisisce prima i byte con
  `load(std::memory_order_acquire)` e poi rilegge la deadline con
  `load(std::memory_order_acquire)` (`ds4_cuda.cu:49455-49468`). Lo stesso
  ordine è ripetuto nel watchdog di stallo (`ds4_cuda.cu:49584-49591`).

Se il consumer acquisisce `B1`, lo `store release` di `D1` che lo precede
happens-before la rilettura della deadline: `{B1,D0}` non è più uno snapshot
ammesso. `{B0,D1}` può allungare prudentemente la lease ma non produce un
timeout falso.

## Difetto 2 — init concorrente e neutralità a flag spento

`cuda_transient_deadline_adaptive_requested` usa ora un
`static const int` inizializzato da lambda (`ds4_cuda.cu:4984-4989`); la policy
usa un `static const cuda_moe_transient_deadline_policy` costruito interamente
dalla propria lambda (`ds4_cuda.cu:31800-31835`). In C++ l’inizializzazione
dello static locale è serializzata e la pubblicazione avviene solo a oggetto
completo: spariscono `cached=-1` e `initialized=0` mutabili, la policy
parzialmente visibile e il log duplicato.

Elenco completo dello storage `static` non atomico introdotto dalla patch:

1. `cached`, `static const int` locale (`ds4_cuda.cu:4985`): immutabile dopo il
   guard C++ thread-safe.
2. `policy`, `static const cuda_moe_transient_deadline_policy` locale
   (`ds4_cuda.cu:31802`): immutabile dopo il medesimo guard.
3. `g_transient_deadline_last_worker_evict_count` e
   `g_transient_deadline_worker_recent_evictions`, entrambi
   `static thread_local uint64_t` (`ds4_cuda.cu:31873-31874`): confinati al
   route worker.
4. `adaptive_last_evict_count`, `static thread_local uint64_t`
   (`ds4_cuda.cu:49401`): confinato al consumer.
5. `g_transient_deadline_replacement_pread`,
   `static os_pread_cancellable_t` (`ds4_cuda.cu:29743-29744`): non viene
   letto né usato finché il latch atomico
   `g_transient_deadline_replacement_pread_active` non lo pubblica con release;
   lo stato interno è manipolato solo tramite l’API sincronizzata
   `os_pread_cancellable_*`.

Non resta alcun nuovo `static int` mutabile condiviso. Le altre nuove variabili
statiche condivise sono atomiche. Con
`DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE` assente o diverso da `1`, la policy non
viene costruita, nessuna nuova riga viene loggata, lo slot sostitutivo non viene
pubblicato e i byte/recovery/terminali restano nel percorso storico. Quindi la
neutralità a flag spento copre anche race e log.

## Difetto 3 — terminale adaptive e OVERLAPPED ancora del kernel

Prima di ogni `ready/completed`, il terminale adaptive chiama
`cuda_moe_transient_deadline_terminal_drain` (`ds4_cuda.cu:44708-44718`).
Il limite dichiarato per provare `os_pread_cancellable_pending()==0` è 5,0 s
(`ds4_cuda.cu:32028-32043`).

Ramo drenato:

1. `pending()==0` è provato.
2. Vengono disarmati, in quest’ordine e tutti con release, deadline,
   `io_sequence`, byte, `read_sequence` e i due marker di cancel
   (`ds4_cuda.cu:44721-44735`).
3. Solo dopo viene emessa
   `[transient-deadline] terminal-publish ... pending=0
   action=ready-completed` (`ds4_cuda.cu:44736-44739`), quindi vengono
   pubblicati `route_ready_host` e `route_completed_*`
   (`ds4_cuda.cu:44776`, `ds4_cuda.cu:44795-44796`).

Ramo non drenabile entro 5 s:

- `ready/completed` non vengono pubblicati per quel job.
- Vengono preparati un `os_pread_cancellable_t` a indirizzo stabile e pagine
  host-pinned nuove per gate/up/down; solo quando entrambi sono completi il
  latch dello slot sostitutivo viene pubblicato release
  (`ds4_cuda.cu:31931-32025`).
- Il vecchio slot e il vecchio staging restano quarantinati e irraggiungibili
  dal respawn. Il worker viene marcato `ready=0, failed=1` con release
  (`ds4_cuda.cu:32045-32049`); il normale health path lo join-a e il prepare
  successivo respawna usando esclusivamente I/O e staging nuovi.
- Se nemmeno le risorse sostitutive sono ottenibili, i riferimenti allo staging
  posseduto dal kernel vengono persi intenzionalmente e la cache è
  `safe_leaked`, quindi non può essere riusata (`ds4_cuda.cu:32050-32061`).

Invarianti sui byte:

- **Ramo drenato:** l’upload stream è già stato drenato dal job; `pending==0`
  prova che il kernel non scrive più nello staging. Se `ok`, gate/up/down sono
  completi prima della pubblicazione; se `!ok`, `route_failed_host` precede
  `ready`, quindi il consumer non usa i byte come risultato valido.
- **Ramo respawn:** il job vecchio non pubblica né `ready` né `completed`; i
  byte parziali restano nel vecchio staging quarantinato. Il nuovo worker parte
  con slot e staging nuovi e non può rendere visibile alcun byte finché il
  nuovo job non completa il normale H2D/publish.
- **Ramo fail-closed:** nessun puntatore allo staging kernel-owned rimane
  liberabile o servibile e la cache non è più candidabile.

La riga di ingresso
`[transient-deadline] request-begin seq=<T2> generation=<...> pending=0
io_slot=primary|replacement` è emessa dopo il controllo reale di `pending`
e prima del reset (`ds4_cuda.cu:37479-37499`): è il discriminatore esplicito
che il turno 2 non ha ereditato l’OVERLAPPED del turno 1.

## Difetto 4 — classificazione causale dopo ricreazione

La deduplicazione non usa più la sola sequence. La chiave è ora
`{host_generation, sequence}` (`ds4_cuda.cu:4977-4982`,
`ds4_cuda.cu:31885-31910`). Un `atomic_flag` acquisito con acquire protegge il
confronto e l’aggiornamento congiunto delle due atomiche; il clear è release.
Worker/QD passano la generation consumata o quella della request, il consumer
quella submitted. Una sequence numericamente riusata dopo ricreazione non può
quindi sopprimere un nuovo evento, mentre due classificatori concorrenti della
stessa chiave incrementano un solo contatore.

## Perimetro

Non è stato aggiunto alcun campo alla cache condivisa. Nessun hunk tocca
l’allocatore range 8481-9200, teardown/ledger, host-pin budget, precheck route
worker, nextnfix o indexerzc. Il comportamento nuovo resta interamente dietro
`DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE=1`, default spento.

## Criterio di collaudo

Collaudo non eseguito per vincolo del mandato.

1. Impostare `DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE=1`,
   `DS4_G133_TRANSIENT_IO_TIMEOUT_S=0.25`, NextN `PIN=2`, `K=5`.
2. Il turno 1 deve superare il token 3 senza restart/kill del route worker e
   senza `cache-invalidate site=consumer-starved`.
3. La riga finale `[transient-deadline]` deve avere
   `worker_kills_for_slow_read=0`; ogni lease scaduta deve confluire in uno
   solo fra `slow_io`, `cpu_contention`, `eviction_storm`.
4. Forzare un turno 1 che termini per deadline, poi avviare il turno 2 nella
   stessa sessione. Prima della sua prima pread deve comparire:
   `[transient-deadline] request-begin seq=<T2> ... pending=0
   io_slot=primary|replacement`. Questa è la prova richiesta dell’assenza di
   pending ereditato; non deve comparire alcun fallimento `EBUSY`.
5. Il primo route del turno 2 deve avanzare fino alla propria riga
   `[transient-deadline] terminal-publish seq=<T2> pending=0
   action=ready-completed`. Nel ramo eccezionale del turno 1 sono inoltre
   attese, in ordine, `action=worker-unhealthy-respawn-new-io-staging`, la riga
   esistente `[g73-open] route worker respawned ...`, e poi il
   `request-begin` del turno 2 con `io_slot=replacement`.
