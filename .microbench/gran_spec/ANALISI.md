# Mandato C — granularità QD e tracciamento MTP strict

Analisi statica sul file corrente. Nessun sorgente è stato modificato, nessun
binario è stato compilato e `ds4_server` non è stato avviato.

Baseline usate per i diff:

- `ds4-p4a/ds4_cuda.cu`:
  `044696C0674C11034BC318FCC8A2B0E1AB5F4D1DCFD51667A2A1BC0747B0C797`
- `ds4-p4a/ds4.c`:
  `C03D3A15D5D8144C7E28463F6BE860632B0A59CF995762F23D5E783F4035EE67`

## C1 — granularità della coda profonda

### Dove nasce e quanto si estende una lettura QD

La catena corrente è questa:

1. `ds4_cuda.cu:39024-39027` invoca l'hint opzionale
   `cuda_moe_route_prefetch_hint(request)`.
2. Il piano QD viene costruito in `ds4_cuda.cu:39036-39095`. Per ogni miss non
   già residente in RAM vengono prodotti **tre span logici**:

   - gate: `gate_offset + expert * gate_expert_bytes`, lunghezza
     `gate_expert_bytes` (`:39079-39087`);
   - up: `up_offset + expert * gate_expert_bytes`, stessa lunghezza
     (`:39081-39090`);
   - down: `down_offset + expert * down_expert_bytes`, lunghezza
     `down_expert_bytes` (`:39083-39093`).

3. `cuda_moe_route_io_qd_read`, `ds4_cuda.cu:38775-38950`, non estende gli
   span. Valida esattamente `offset` e `bytes` (`:38819-38825`), copia l'offset
   direttamente in `OVERLAPPED.Offset/OffsetHigh` (`:38827-38832`) e passa
   `span.destination` e `(DWORD)span.bytes` direttamente a `ReadFile`
   (`:38835-38837`). Anche il completamento pretende
   `got == span.bytes` (`:38887-38903`).
4. Il fallback seriale legge gli stessi tre slice in
   `ds4_cuda.cu:39380-39422`. La sola differenza è la granularità delle syscall:
   `cuda_moe_transient_pread_chunked`, `:30479-30565`, usa chunk da 1 MiB
   (`:30485`, `:30502-30505`) salvo `DS4_CUDA_ROUTE_READ_WHOLE`.

Quindi oggi la lettura QD è “whole logical span”: una richiesta per l'intero
slice di un expert, non una lettura arrotondata a un blocco più grande. Non
esiste un'estensione agli expert vicini, né un round-down dell'offset o un
round-up della lunghezza nel percorso QD Windows.

### Allineamento reale

Il model file Windows viene aperto in
`src/platform/os_file.c:100-108` con:

```text
FILE_ATTRIBUTE_NORMAL | FILE_FLAG_RANDOM_ACCESS | FILE_FLAG_OVERLAPPED
```

Manca `FILE_FLAG_NO_BUFFERING`; `ds4_gpu_set_model_file` duplica quel medesimo
handle a `ds4_cuda.cu:16843-16854`. Per questa forma di `ReadFile` buffered non
c'è un requisito di allineamento a settore né per offset, buffer o lunghezza.
Il minimo tecnicamente leggibile è 1 byte. Poiché il flag proposto è espresso
in KiB, il suo minimo pratico è 1 KiB.

L'unico round-down/round-up a un allineamento di dispositivo trovato è il ramo
Linux `O_DIRECT` di `cuda_model_stage_read`, `ds4_cuda.cu:7522-7553`; non è
usato da `cuda_moe_route_io_qd_read`.

L'hint opzionale `DS4_CUDA_ROUTE_PREFETCH_HINT` costruisce anch'esso range
esatti (`ds4_cuda.cu:30377-30437`), ma `PrefetchVirtualMemory` opera
naturalmente sulle pagine del mapping. Può quindi popolare pagine contenenti
byte adiacenti; quei byte non sono però completamenti `ReadFile`, non sono
registrati dai contatori QD e non sono H2D del ledger.

### Perché i byte H2D non possono dipendere dalla dimensione dello span QD

Il dato 362 GB -> 1.082 GB è `h2d_bytes_total`, non il numero di byte letti dal
file. Il ledger aggiunge un solo payload completo
`gate_expert_bytes * 2 + down_expert_bytes` per expert a
`ds4_cuda.cu:39719-39722` (e nel percorso gemello `:39877-39880`), e lo
contabilizza soltanto dopo il drain riuscito in `:27756-27804`.

`cuda_moe_route_io_qd_read` termina prima di questi H2D e non modifica la loro
lunghezza. Suddividere uno span in chunk più piccoli:

- aumenta i submit/completamenti file;
- limita i byte già in volo quando arriva cancel/timeout;
- lascia invariato il totale file per un batch completato;
- lascia invariato, per definizione, il payload H2D di ogni materializzazione.

Pertanto il triplo di `h2d_bytes_total` non è spiegato da “intorno” o
allineamento QD. Indica circa tre volte le materializzazioni H2D degli expert
(più coppie distinte e/o più repeat). Per separare le due cause vanno confrontati
nella stessa riga ledger `unique_pairs_touched`, `first_touch_bytes` e
`repeat_h2d_bytes`. Un cap degli span non può correggere quel totale; può solo
ridurre lavoro file speculativo residuo su operazioni interrotte.

### Diff proposto

`qd_span.patch` aggiunge `DS4_CUDA_ROUTE_IO_QD_SPAN_KB` con questa semantica:

- unset/vuoto: `UINT64_MAX`, quindi submit whole-span identici a oggi;
- intero decimale positivo: massimo per ogni singolo `ReadFile`, in KiB;
- valore invalido: una diagnostica e fallback whole-span;
- gli span logici gate/up/down restano invariati;
- quattro chunk restano concorrenti; ogni logical span avanza con un cursor
  `(destination + completed, offset + completed)`;
- byte, chiamate e completamenti sono contabilizzati sui chunk effettivi.

La patch è deliberatamente un controllo di granularità/cancellabilità, non una
promessa di ridurre i byte logici o H2D di un run completato.

## C2 — cancello del verifier batch MTP strict

### Correzione dell'assunto sul log

La riga:

```text
ds4: mtp conf drafted=... committed=...
```

non è dentro il ramo `use_decode2_exact`. È a `ds4.c:21246-21256`, dentro il
blocco opposto aperto da:

```c
if (!use_decode2_exact) {                 /* ds4.c:21195 */
```

Quindi con `draft_n == 2`, `strict_mtp == true` e
`DS4_MTP_BATCH_VERIFY` assente, **quella riga deve essere assente**. Non è
evidenza che il verifier exact non sia stato raggiunto.

### Catena esatta delle condizioni

1. Il server entra nella speculazione se
   `temperature <= 0`, `ds4_engine_mtp_draft_tokens(engine) > 1` e
   `DS4_MTP_SPEC_DISABLE` è assente
   (`ds4_server.c:7484-7495`).
2. Il getter del secondo predicato prova soltanto `backend != CPU`,
   `mtp_ready` e il valore engine di `mtp_draft_tokens`
   (`ds4.c:18301-18303`). Non prova che la sessione riuscirà a produrre un
   draft.
3. `ds4_session_eval_speculative_argmax` decodifica e committa sempre prima il
   token target normale (`ds4.c:20965-20968`).
4. Nella `ds4_session_eval` appena chiamata, il draft iniziale viene tentato
   soltanto se `probe_mtp && mtp_ready && mtp_logits &&
   mtp_draft_tokens > 1` (`ds4.c:20877-20880`). La chiamata MTP è a
   `:20906-20914`; solo se ritorna true vengono impostati
   `mtp_draft_token` e `mtp_draft_valid` (`:20915-20916`). Il fallimento è
   silenzioso salvo `DS4_MTP_PROBE` (`:20917-20919`).
5. Subito dopo esistono questi ritorni prima del gate exact:

   - EOS, ultimo token richiesto o accepted buffer pieno:
     `ds4.c:20968`;
   - `!mtp_ready || !mtp_draft_valid || mtp_draft_tokens <= 1`:
     `ds4.c:20970`;
   - cap ridotto a zero da token budget, accepted capacity o context room:
     `ds4.c:20972-20977`;
   - il draft iniziale non coincide con l'argmax target appena calcolato:
     `ds4.c:21007-21011`.

6. Con `mtp_draft_tokens=2`, budget e context sufficient, `draft_cap` vale 2.
   Il loop `ds4.c:21027-21050` esegue esattamente una chiamata ricorsiva
   `metal_graph_eval_mtp_draft_from_hc` per produrre `drafts[1]`.
   Se la chiamata fallisce, il ritorno a `:21043` è silenzioso. Se riesce,
   l'incremento del `for` porta realmente `draft_n` a 2.
7. `--quality` è copiato in `e->quality` a `ds4.c:19510`; quindi
   `strict_mtp` è true a `ds4.c:20983`. A questo punto
   `use_decode2_exact` a `:21109-21110` è true se e solo se il secondo draft
   è stato prodotto e `DS4_MTP_BATCH_VERIFY` è assente.
8. Nel ramo exact:

   - snapshot: call site `ds4.c:21119`, implementazione e possibili failure
     `ds4.c:18321-18351`;
   - verifier: call site `ds4.c:21123-21131`, implementazione
     `ds4.c:16048-16184`;
   - verifier riuscito e `row0_top == drafts[1]`: commit di entrambi i draft e
     ritorno a `ds4.c:21134-21154`;
   - verifier riuscito ma mismatch: commit del prefix-1 tramite
     `spec_frontier_commit_prefix1`, poi ritorno a
     `ds4.c:21157-21181`;
   - snapshot/verifier/prefix failure: cleanup/restore a
     `ds4.c:21183-21192`, poi il ramo generic `:21195-21446` viene saltato
     perché `use_decode2_exact` resta true.

9. Non c'è un'uscita silenziosa dopo il fallimento exact: il controllo cade nel
   verifier sequenziale di sicurezza a `ds4.c:21448-21527`. Il primo confronto
   usa di nuovo `s->logits` e `drafts[0]` (`:21454-21470`), già confrontati con
   successo a `:21007`; in stato integro deve quindi accettare almeno
   `drafts[0]`.

### Dove si ferma il flusso osservato

Occorre distinguere due significati di “token committati per passo”:

- Se è il numero di **draft speculativi** oltre al token target normale,
  `committed=1` è il normale partial accept del ramo exact
  `ds4.c:21157-21181`. Il server riceve `ntok=2`: il token base più
  `drafts[0]`. Non c'è alcun blocco del verifier.
- Se `ntok` del server è realmente 1 in ogni iterazione, l'uscita è prima di
  `use_decode2_exact`: nel run normale le alternative vive sono
  `mtp_draft_valid == false` a `ds4.c:20970`, first-draft miss a
  `ds4.c:21007-21011`, oppure failure della seconda chiamata MTP a
  `ds4.c:21031-21043`. Snapshot o `metal_graph_verify_decode2_exact == false`
  non spiegano da soli `ntok=1`, perché conducono al fallback sequenziale.

I soli due sintomi forniti (assenza della riga generic e “1” senza specificare
se sia `ntok` o draft accettati) non distinguono le tre uscite pre-gate. Il
sorgente non contiene una riga sempre emessa che permetta di scegliere tra
esse; attribuire un punto più preciso senza il log dei run sarebbe inventarlo.

### Diff minimo di visibilità

`spec_trace.patch` aggiunge, dietro il flag già esistente
`DS4_MTP_CONF_LOG`, una sola riga subito dopo snapshot+verifier exact:

```text
ds4: mtp conf path=decode2-exact drafted=2 exact_prefix=<0|1|2> snapshot=<0|1> verifier=<0|1> target_next=<id> draft_next=<id>
```

Interpretazione:

- `snapshot=0 verifier=0`: fallimento snapshot;
- `snapshot=1 verifier=0`: fallimento del verifier exact;
- `snapshot=1 verifier=1 exact_prefix=1`: exact raggiunto, partial accept;
- `snapshot=1 verifier=1 exact_prefix=2`: exact raggiunto, full accept;
- riga assente: uscita prima del ramo exact secondo i gate elencati sopra.

Il campo si chiama `exact_prefix`, non `committed`, perché in caso di failure
exact il successivo fallback sequenziale può ancora committare draft.

## Verifica dei deliverable

- `qd_span.patch`: unified diff contro il `ds4_cuda.cu` con hash indicato sopra.
- `spec_trace.patch`: unified diff contro il `ds4.c` con hash indicato sopra.
- Entrambi hanno superato `git apply --check --whitespace=error-all` contro i
  file correnti.
- Non è stata eseguita compilazione, applicazione dei patch o esecuzione del
  server.
