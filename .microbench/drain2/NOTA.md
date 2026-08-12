# MANDATO A2 — neutralità del drain con flag spento

## Esito

`drain2.patch` è stata rigenerata contro il `ds4-p4a/ds4_cuda.cu`
corrente, blob Git:

```
509cab7cb7a8fde489eb490d381291b043b2b55d
```

La patch non è stata applicata al sorgente corrente. Non è stata eseguita
alcuna compilazione e non è stato avviato `ds4_server`.

## Causa accertata della non-neutralità

La prima patch dichiarava che il helper overlap non fosse chiamato con
`DS4_CUDA_DRAIN_OVERLAP=0`, ma il diff prova il contrario.

Nel drain ENFORCE aveva trasformato la chiamata bloccante diretta in:

```cpp
allow_overlap && commit_on_success &&
pending_error == cudaSuccess &&
cuda_moe_route_upload_overlap_arm(...)
```

Il call site finale passava `allow_overlap=1` anche con il flag ambiente
spento. Il test di `drain_overlap_requested` era dentro
`cuda_moe_route_upload_overlap_arm`: il percorso OFF entrava quindi nel
costrutto nuovo e decideva di non armare l'evento soltanto dentro il helper,
prima di tornare alla sync.

La stessa ristrutturazione era presente nel drain non-ENFORCE:

```cpp
ok && pending_error == cudaSuccess &&
cuda_moe_route_upload_overlap_arm(...)
```

Inoltre la prima patch eseguiva due operazioni nuove anche con flag OFF:

- un `route_upload_ready_generation.load(memory_order_acquire)` dopo il drain
  ENFORCE;
- un load acquire di `route_submitted_generation` nel consumer, prima del test
  del flag.

Infine aveva inserito due handle evento e un atomic nel mezzo di
`cuda_moe_expert_cache`, spostando il layout degli atomic e del mailbox
condivisi fra decode e worker anche quando gli eventi non venivano allocati.

Questi sono fatti riproducibili sul vecchio diff, non ipotesi sul valore della
variabile ambiente. La prova runtime fornita nel mandato completa
l'attribuzione causale alla patch: 2135 ms/token e abort col drain applicato
contro 255 ms/token e run completo togliendo soltanto quella patch, sulla
stessa macchina appena riavviata.

I dati disponibili non separano quale dei tre cambiamenti non-neutrali
(call/riordinamento del drain, load acquire aggiuntivi, layout condiviso)
producesse la quota dominante dei 13.648 ms/token di worker fermo. Attribuirla
a uno solo sarebbe congettura. `drain2.patch` li elimina tutti dal percorso
OFF.

## Correzione

1. Lo stato nuovo è in `cuda_moe_drain_overlap_sidecar`, separato da
   `cuda_moe_expert_cache`. La struct condivisa legacy resta identica.
2. `cuda_moe_tiering_finish_vram_reservations` resta letteralmente identica
   al sorgente corrente. La variante asincrona è una funzione distinta.
3. I due drain hanno un ramo esterno:

   ```cpp
   if (!g_moe_drain_overlap.requested) {
       /* blocco originale duplicato */
   } else {
       /* solo via nuova */
   }
   ```

   Il helper di armamento non è raggiungibile dal ramo OFF.
4. Il load della generazione e `cudaStreamWaitEvent` sono entrambi dentro
   `if (g_moe_drain_overlap.requested)`.
5. Il drain anticipato prima del fallback SSD transiente continua a chiamare
   esclusivamente il helper bloccante originale.
6. Se il record dell'evento non riesce, il ramo ON ricade sulla sync
   bloccante. Il ledger H2D viene invalidato soltanto quando l'evento è stato
   realmente armato.

Il diff contiene accanto al sidecar e al helper il commento A2 che documenta
il costrutto della prima patch responsabile della violazione di neutralità.

## Verifica meccanica della neutralità OFF

La patch è stata materializzata soltanto su una copia temporanea per eseguire
confronti byte-per-byte; la copia è stata poi rimossa. Tolta la sola
indentazione introdotta dal ramo esterno, i risultati sono:

```
shared-cache-struct:  IDENTICAL bytes=4794 sha=11be3f59adc172cc
legacy-tiering-finish: IDENTICAL bytes=1653 sha=ed65a52748d9643c
legacy-enforce-drain:  IDENTICAL bytes=1010 sha=8f704dadc7f89c27
legacy-worker-drain:   IDENTICAL bytes=2575 sha=65ad06cfe25aa0d1
```

Quindi nel ramo OFF sono conservati esattamente:

- layout della cache condivisa;
- helper di finish bloccante;
- sequenza ENFORCE da `drain_started` fino alla gestione di
  `transfers_ok`;
- sequenza non-ENFORCE da publish, `cudaGetLastError`,
  `cudaStreamSynchronize`, accounting e commit/rollback degli slot.

Controllo di applicabilità eseguito:

```
git apply --check --verbose .microbench/drain2/drain2.patch
Checking patch ds4-p4a/ds4_cuda.cu...
```

Il controllo prestazionale definitivo resta, correttamente, il run richiesto
dal mandato sul binario compilato dall'utilizzatore con flag non impostato.
