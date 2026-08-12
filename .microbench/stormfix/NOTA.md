# STORMFIX - ammissione unificata del backbone

Data: 2026-07-29. Letta per prima `.microbench/stormdiag_codex/NOTA.md`;
diagnosi riverificata sul tree corrente. Scritto solo in questa directory.
Nessuna compilazione e nessun server avviato; `D:\` non e' stato modificato.

## Diagnosi confermata riga per riga

1. Il working set stabile e' circa 6,87 GiB di `g_model_range_bytes`. Nei run
   sani viene raggiunto entro il token 2; da li' i 2248 token restanti sono
   hit, quindi `cuda_model_stream_alloc()` e il reclaim non vengono piu'
   chiamati.
2. Nei run malati il set residente resta sotto il working set. Il giro del
   token sfratta la testa per caricare la coda e il giro seguente richiede di
   nuovo la testa: `reloads/evictions=0,9994..1,0012` sui sei run, circa
   6,37 MiB/evento e circa 1100 eventi/token. E' un LRU ciclico di capacita',
   non una perdita di range morti.
3. Colpevole primaria confermata nella preimage a
   `ds4_cuda.cu:8975-8977`: `cuda_stream_pool_take()` e' prima del `for (;;)`,
   prima di `cudaMemGetInfo()` e prima del test di riserva. Dopo il reclaim
   (`:8998-9002`) o l'eviction nel pool (`:9072-9076`) il ciclo non riprova
   quel bucket: puo' sincronizzarlo/liberarlo e poi rifare `cudaMalloc` della
   stessa taglia.
4. L'aggravante e' confermata a `:9094-9103`: `is_hot` classifica gia' tutto
   il non-MoE come backbone/dense, ma `use_hot_reserve` seleziona la riserva
   ridotta soltanto per `indexer_f16`; gli altri pesi restano sotto i 2048 MiB
   normali.

## Nuovo test discriminante

`DS4_CUDA_STREAM_RUNTIME_RESERVE_MB=1792` ha prodotto la tempesta 2/2 su
macchina fresca (arm 1 e 2); il braccio successivo, stessa macchina e default
2048, e' stato il migliore della campagna: 4,209 t/s, mediana 225,0,
0,4 sfratti/token e SHA del testo identico.

Il risultato controintuitivo e' decisivo: abbassare la riserva, quindi offrire
piu' spazio nominale, ha fermato il working set ancora piu' in basso
(6,03-6,06 GiB invece di 6,87). Il tetto non e' dunque la sola disuguaglianza
su `freeb`; l'ordine e l'esito delle due vie di ammissione scelgono uno dei due
rami. Una volta entrato nel ramo basso, l'ordine
`evict-to-pool -> reclaim/free -> malloc` conserva il deficit e l'LRU lo
trasforma in rotazione perpetua. Il braccio 2048 dimostra sulla stessa
macchina che la capacita' fisica per 6,87 GiB esiste.

## Fix in `stormfix.patch`

Il fix e' opt-in con:

```text
DS4_CUDA_STREAM_ADMIT_UNIFIED=1
```

- Il flag vale solo per la stringa esatta `1`. Spento, resta il fast path
  legacy: stesso `pool_take` prima del ciclo, stessi predicati, stesso ordine
  CUDA, nessun log nuovo.
- Acceso, il pool viene interrogato dentro ogni iterazione, dopo
  `cudaMemGetInfo()`, quindi e' riprovato dopo ogni reclaim ed eviction.
  Prima si cerca un evento exact-size gia' pronto; se una nuova allocazione
  non e' ammissibile, si attende l'exact-size piu' vecchio e lo si riusa.
  E' la stessa attesa che il reclaim avrebbe gia' pagato, ma senza distruggere
  il buffer per ricrearlo subito.
- La policy e' unica e interpreta la riserva come pavimento di VRAM libera
  **dopo** l'ammissione: il riuso, costo incrementale zero, richiede
  `freeb >= reserve`; `cudaMalloc`, costo `aligned`, richiede
  `freeb >= reserve + aligned`. Imporre anche `+aligned` al pool
  sovrastimerebbe un riuso senza crescita e ricreerebbe proprio il percorso
  free/malloc. Se manca perfino la riserva, il pool viene invece reclamato.
- Nello stesso flag, `use_hot_reserve` usa `is_hot`: la riserva hot configurata
  si estende a tutto il backbone/dense non-MoE, mentre i `moe_*` conservano la
  riserva runtime piena. Il rischio per il trasporto esperti resta quindi
  confinato alla quota backbone esplicitamente ammessa dal flag.

Nessuna struct cambia layout. La patch non modifica percorso
transiente/`os_file`, teardown/ledger, host-pin budget, precheck route worker,
indexerzc, sharedcore o `dspark*`.

## Neutralita' e collaudo

La neutralita' OFF e' per costruzione, non misurata (compilazione vietata):
il controllo deve conservare il riferimento di 8145 caratteri,
SHA `c7525d909341a57a`, e circa 0,4 sfratti/token.

Criterio di accettazione obbligatorio: con
`DS4_CUDA_STREAM_ADMIT_UNIFIED=1` e
`DS4_CUDA_STREAM_RUNTIME_RESERVE_MB=1792` - l'interruttore che oggi causa
sempre la tempesta - completare 2250 token con meno di 5 sfratti/token e
`g_model_range_bytes` a circa 6,87 GiB entro il token 2.

## Verifiche e SHA-256

`git apply --check .microbench/stormfix/stormfix.patch` passa sul tree
corrente. Patch: un solo file, +57/-12. Round-trip su copia temporanea
verificato e copia rimossa; nessuna esecuzione del codice.

```text
2c5ddefa1bae43b91f26e418e544c03cf57bb81ce6f1f17eee8aefc15374b58e  ds4-p4a/ds4_cuda.cu (preimage corrente)
f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37  ds4-p4a/ds4_cuda.cu (postimage atteso)
c35f932eaa1914f7a8800e4b4ffd738bf5fe04531642470a62438d6c0f020d51  .microbench/stormfix/stormfix.patch
```
