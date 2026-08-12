# NEXTNFIX — handoff verifier one-row -> mailbox decode

Data: 2026-07-29. Tree bersaglio: `ds4-p4a` corrente. Artefatto:
`nextnfix.patch`, un solo file sorgente (`ds4-p4a/ds4.c`), 90 inserimenti /
10 rimozioni. Nessuna build e nessun server avviato.

## Diagnosi chiusa sui sei log

I due sintomi sono lo stesso producer one-row, non pressione di memoria,
ampiezza K, timeout o `--mtp-draft`:

- con G133 attivo, `seq=130 layer=0` arriva al worker con
  `g133_request_epoch=0 g133_position_epoch=0` e muore `request-invalid`;
- con G133 spento, la stessa 130 viene servita: il summary finale prova
  `calls=130 worker_jobs=130 errors=0`. La 131 muore invece perché l'evento
  consumer è ancora registrato sulla 129 (`consumer-event-generation`);
- K=1 riproduce identicamente la 131. È il discriminatore decisivo: il verifier
  layer-major con `n_tokens==1` entra nel mailbox perché il begin accetta solo
  richieste one-row (`ds4_cuda.cu:48444-48448`), mentre l'API batch gli passa
  sempre epoch nullo (`ds4_cuda.cu:55018-55028`) e il batch encoder non ha un
  consumer boundary.

Il literal `{0}` in `metal_graph_eval_mtp_draft_from_hc()` è un secondo
produttore dello stesso contratto rotto, ma non è da solo la spiegazione dei
run NextN CPU: quel drafter GPU è escluso da `!nextn_cpu` (`ds4.c:24199`).
Perciò **FIX A da solo non basta**: il braccio G133-off prova FIX B
indipendentemente.

## Flag e neutralità

Un solo opt-in, default spento:

```text
DS4_NEXTN_TRANSITION_FIX=1
```

A flag spento:

- il verifier/prefill continua a chiamare `ds4_gpu_routed_moe_batch_tensor`;
- tutti i nuovi argomenti interni sono `false` e `{0}`;
- il literal MTP resta semanticamente `{0}` e non viene creato alcun epoch;
- non viene aggiunta alcuna chiamata `consumer_done`.

Quindi il comportamento a flag spento resta quello corrente al byte. Nessuna
struct, layout, mailbox slot o protocollo condiviso è modificato. PIN=2, pin
budget, transient/os_file, teardown/ledger, indexerzc, sharedcore e allocatore
di range non sono toccati.

## FIX A — epoch corretto per posizione

Il patch copre entrambi i producer one-row:

1. `metal_graph_eval_mtp_draft_from_hc()` crea
   `ds4_gpu_g133_decode_position_begin()` una volta per la posizione MTP e
   riusa la coppia nell'intero layer;
2. `metal_graph_verify_suffix_tops()` fa lo stesso una volta quando
   `n_tokens==1`, poi riusa l'epoch per tutti i 43 layer. In quel solo caso e
   solo con G133 attivo usa l'API one-tensor, che già trasporta esplicitamente
   l'epoch fino al payload mailbox. Con G133 spento conserva il kernel batch.

Non è un placeholder non nullo: request epoch e position epoch provengono
dall'unico generatore ordinario (`ds4_gpu_g133_decode_position_begin`) e la
position viene incrementata una sola volta, non una volta per layer.

## FIX B — consumer boundary del verifier

Dopo un route one-row servito, il batch FFN salva
`one_row_route_submitted`. Alla fine del layer registra
`ds4_gpu_moe_route_consumer_done()` dopo che routed MoE, shared expert e HC
post sono stati accodati su stream 0. La registrazione viene tentata anche se
un consumer successivo ha abbassato `ok`: l'evento resta ordinato dopo tutti i
kernel già pubblicati, mentre il valore di ritorno del layer resta fallito.

Il claim non viene rilassato: continuano a essere obbligatori generation
esatta, slot esatto ed evento CUDA completato (`ds4_cuda.cu:32133-32175`).
Quindi la 131 non può mai leggere byte non pubblicati; o trova il vero evento
della 130, o resta fail-closed come oggi.

## Criterio di accettazione

Con patch applicata e `DS4_NEXTN_TRANSITION_FIX=1`, il braccio NextN
`PIN=2`, `K=5`, G133 attivo e timeout transiente di default deve superare il
token 3 e stampare una riga/campo `k_accepted` nel ciclo successivo. Oggi tutti
i run muoiono prima e il summary resta `k_accepted=0`; questo test riapre la
domanda n.1 di DSpark senza regredire il guadagno PIN=2.

## Verifiche statiche

- `git apply --check .microbench/nextnfix/nextnfix.patch`: PASS.
- `git apply --numstat`: `90  10  ds4-p4a/ds4.c`.
- Round-trip su copia: patch applicata e post-image hashata; sorgenti reali
  mai modificati.
- Delta grezzo bilanciato: `{}` +12/+12, `()` +20/+20, `[]` +0/+0.
- Nessuna compilazione, nessun server, nessuna scrittura su `D:\`.

## SHA-256

```text
ds4-p4a/ds4.c preimage
6db7eb31f93135bb0dfb4da99addd29207bb3c4b9789a05f1f2b88ec696e14b4

ds4-p4a/ds4.c postimage
2d97991e6037c434e484ab6a8c8cc2a364e7cf69aa403ad5e6baa815d3dd6e5c

.microbench/nextnfix/nextnfix.patch
e50638710e7656726cb58443c9594735d883a1d3685881e0372314e9eee4ebf1
```
