# STORMSPLIT - separazione retry exact-size / riserva hot-all

Data: 2026-07-30.

Sono stati letti integralmente, prima dell'analisi, il mandato e i dossier
obbligatori:

- `.microbench/stormfixctx/NOTA.md`;
- `.microbench/stormfix/NOTA.md` e `stormfix.patch`;
- `.microbench/adv_percorso/NOTA.md`.

Non sono stati modificati sorgenti, non e' stata eseguita alcuna compilazione
e non e' stato avviato alcun server. `D:\` e' rimasto in sola lettura. Gli
unici file scritti sono questa nota e `stormsplit.patch`.

## Verdetto

La revisione e' confermata. Nel tree corrente
`DS4_CUDA_STREAM_ADMIT_UNIFIED=1` controlla due leve indipendenti:

1. il retry/attesa di un buffer exact-size nel `for (;;)` di reclaim
   (`ds4-p4a/ds4_cuda.cu:9002-9043`), che e' il fix voluto;
2. la selezione `use_hot_reserve=is_hot`
   (`ds4-p4a/ds4_cuda.cu:9138-9148`), che estende il floor hot a tutto il
   non-MoE.

Il secondo effetto non e' necessario al primo ed era gia' stato falsificato:
la prima policy larga affamo' la cache esperti e aborto' al token 19; il ledger
promosse quindi il solo `indexer_f16`
(`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:5974-5979`). Il successivo
run storico con floor esclusivo completo' 4000/4000
(`EXPERIMENTS_LEDGER.md:5998-6009`), e I1 con cache 140 completo' 2600/2600
riducendo `evict_backbone` da 229.376 a 791
(`EXPERIMENTS_LEDGER.md:17789-17799`).

Il danno recente e' di prefill, non un'inversione del decode: `G_storm`
mantiene 15 sfratti nel decode ma aggiunge 12.293 sfratti nel prefill della
richiesta successiva, contro +1.597 di `G_base`
(`.microbench/adv_percorso/NOTA.md`, righe `DA CORREGGERE Q5`). Questo separa
anche sperimentalmente le due ipotesi: il retry appare utile, mentre hot-all e'
pericoloso, ma stormfix v1 non consente ancora di attribuirli isolatamente.

## Patch

`stormsplit.patch` si applica alla preimage corrente e introduce il flag:

```text
DS4_CUDA_STREAM_HOT_RESERVE_ALL=1
```

Entrambi i flag accettano soltanto la stringa esatta `1`.

- `DS4_CUDA_STREAM_ADMIT_UNIFIED` resta usato esclusivamente dentro
  `cuda_model_stream_alloc`: governa il retry/attesa exact-size e non
  seleziona piu' la riserva hot.
- Con il nuovo flag spento, `use_hot_reserve` torna sempre al predicato
  `what != NULL && strcmp(what, "indexer_f16") == 0`.
- Con il nuovo flag acceso, e indipendentemente da `ADMIT_UNIFIED`,
  `use_hot_reserve=is_hot` riproduce hot-all e lo mantiene misurabile.
- Con `ADMIT_UNIFIED=1` e il nuovo flag spento, il comportamento e'
  stormfix v1 meno hot-all: il codice del reclaim-loop non cambia.
- Con entrambi i flag spenti, il ramo allocator, i predicati di riserva e lo
  stderr restano quelli legacy. La neutralita' al byte e allo stderr e' per
  costruzione, non misurata: il nuovo helper fa soltanto un `getenv` cached,
  non aggiunge stampe, e nello stato OFF restituisce lo stesso predicato
  `indexer_f16` gia' usato dal controllo.

La patch tocca soltanto `ds4-p4a/ds4_cuda.cu` (+15/-2): un helper di flag e la
selezione di `use_hot_reserve`. Non cambia struct o layout e non tocca
transiente/deadline, host-pin, preservazione fra richieste, nextnfix o
indexerzc.

## Matrice retry x policy hot

Per "hot-solo" si intende la policy che concede
`DS4_CUDA_STREAM_HOT_RESERVE_MB` soltanto a `indexer_f16`; per "hot-all" la
policy che la concede a tutto il non-MoE.

| Retry exact-size | Policy hot | Flag della patch | Mai provata? | Evidenza / verdetto |
|---|---|---|---|---|
| OFF | solo `indexer_f16` | `ADMIT_UNIFIED=0`, `HOT_RESERVE_ALL=0` | **Si'** | Prova storica senza retry: 4000/4000; inoltre I1 cache 140, 2600/2600 (`ledger:5974-6009,17789-17799`). |
| OFF | hot-all | `ADMIT_UNIFIED=0`, `HOT_RESERVE_ALL=1` | **Si'** | Prima versione larga antecedente al retry: falsificata, cache esperti affamata e abort al token 19 (`ledger:5974-5979`). |
| ON | solo `indexer_f16` | `ADMIT_UNIFIED=1`, `HOT_RESERVE_ALL=0` | **No, mai insieme** | E' la combinazione raccomandata e il nuovo braccio discriminante. Il ledger conferma esplicitamente che non e' mai stata provata (`ledger:19324-19330`). |
| ON | hot-all | `ADMIT_UNIFIED=1`, `HOT_RESERVE_ALL=1` | **Si'** | Equivale a stormfix v1/G_storm: decode sano, ma +12.293 sfratti nel prefill follow-up; pericolosa (`ledger:19075-19095,19332-19337`). |

Conferma quindi il revisore: **retry + hot-solo-indexer non sono mai stati
provati insieme**. Non va confusa questa matrice con la precedente matrice
hot-policy x INDEXER_ZC di `adv_percorso`.

## Natura della riserva

I 256 MiB della riserva hot non sono memoria allocata, preallocata o sottratta
alla cache. Sono il valore intero restituito da
`cuda_model_stream_hot_reserve_bytes()` e usato soltanto nei predicati:

```text
freeb >= reserve
freeb >= aligned + reserve
```

(`ds4-p4a/ds4_cuda.cu:8325-8347,9004-9041`). Il costo e' quindi **zero slot**,
non 37 slot. Il problema di hot-all e' la diversa soglia di ammissione concessa
al dense, non un'allocazione da 256 MiB.

## Collaudo discriminante

Compilazione ed esecuzione sono deliberatamente demandate. Il collaudo deve
usare lo stesso binario per i due bracci, `expert_cache_count=140`,
`DS4_CUDA_WEIGHT_CACHE_VERBOSE`, e campionare entro 30 s dal confine di ogni
richiesta il delta per fase del contatore esatto
`CUDA evicted streamed range`, riconciliandolo con
`evict_backbone/backbone_reloads` (`ds4_cuda.cu:8542-8555,8754-8763`).
Non usare il cumulato globale diviso per token.

Braccio raccomandato:

```text
DS4_CUDA_STREAM_ADMIT_UNIFIED=1
DS4_CUDA_STREAM_HOT_RESERVE_ALL=0
DS4_CUDA_STREAM_HOT_RESERVE_MB=256
expert_cache_count=140
```

Accettazione: la raffica di prefill deve sparire senza ridurre la cache esperti.
Controllo causale sullo stesso binario: lasciare retry ON e porre
`DS4_CUDA_STREAM_HOT_RESERVE_ALL=1`; il riferimento dannoso arriva a
12.308 sfratti / 11.977 reload nel follow-up. Registrare separatamente
prefill iniziale, decode, request-end e ogni prefill successivo.

Restano inoltre i due collaudi gia' prescritti: 1792 MiB con 2250/2250
(riferimento <=15 sfratti totali) e default 2048 MiB con 4000/4000 piu'
follow-up. Il secondo e' indispensabile per escludere la regressione di
prefill che il solo decode non vede.

## Verifiche statiche

```text
git apply --check --verbose .microbench/stormsplit/stormsplit.patch
Checking patch ds4-p4a/ds4_cuda.cu...

git apply --numstat .microbench/stormsplit/stormsplit.patch
15  2  ds4-p4a/ds4_cuda.cu
```

SHA-256:

```text
f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37  ds4-p4a/ds4_cuda.cu (prima)
f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37  ds4-p4a/ds4_cuda.cu (dopo: sorgente non modificato)
8523e043b948724558db2adf4e3c9c83577463f4a2c0583d3a8c21f896143631  .microbench/stormsplit/stormsplit.patch
```
