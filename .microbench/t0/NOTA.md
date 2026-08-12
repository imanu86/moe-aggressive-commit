# T0 — tracce route-ID e analisi offline

## Emettitore

`logids.patch` aggiunge l'emettitore in `ds4-p4a/ds4_cuda.cu`.

- Helper: inserito all'ancora corrente `ds4_cuda.cu:36165`, immediatamente
  prima di `cuda_moe_tiering_observe_route`.
- Chiamata: loop del route worker all'ancora corrente
  `ds4_cuda.cu:41743-41756`, subito prima delle sei chiamate
  `cuda_moe_tiering_observe_route`.

Le righe `41387-41400` indicate da Fable sono slittate dopo l'integrazione di
lane, kernel, econ, invalidate e drain4. La definizione di
`cuda_moe_tiering_observe_route` riceve un esperto alla volta e non possiede il
vettore completo; il loop rilocalizzato possiede invece, nello stesso snapshot
validato, `layer_index`, `route_count` e `selected[6]`. Per questo il log
per-layer è emesso lì e non ricostruito da sei chiamate separate.

Formato, una riga per layer:

```text
[route-ids] token=17 layer=9 ids=12,44,81,103,177,201
```

`token` è un ordinale process-local derivato dai ritorni del layer a zero. Per
non introdurre un falso overlap fra famiglie, acquisire ogni famiglia in un
processo/log separato. Il parser richiede 6 ID unici in `[0,255]`.

Il flag è `DS4_EXPERT_TIERING_LOG_IDS=1`; assente, `0` o qualsiasi altro valore
significano OFF. A flag spento l'helper fa un'uscita anticipata, non stampa
righe e non tocca strutture di tiering/cache. Il solo residuo è una chiamata e
un branch su un valore statico inizializzato una volta. A flag acceso il costo
è un `fprintf(stderr)` per layer. Non ci sono allocazioni, copie device/host,
eventi, sincronizzazioni CUDA o modifiche a admission, residenza, cache,
contatori e policy.

## Run minimo

Applicare e verificare la patch dal root del repository:

```powershell
git apply --check .microbench/t0/logids.patch
git apply .microbench/t0/logids.patch
```

Usare il normale harness di campagna, una volta per ciascuna delle due
famiglie, con 160 completion token, greedy e `think=false`. L'asset, il
contesto/KV, il prompt e il watchdog restano quelli del gate. Le sole varianti
T0 sono:

```powershell
$env:DS4_EXPERT_TIERING = 'observe'
$env:DS4_EXPERT_TIERING_LOG_IDS = '1'
$env:DS4_MTP_SPEC_DISABLE = '1'

# Lasciare non impostati DS4_SPEX_FILE, DS4_SPEX_PREFETCH_K e ogni flag
# prefetch/mask. Reindirizzare lo stderr del server, per esempio:
$serverArgs = @('-m', $model, '--cuda', '-c', $context, '-n', '160',
                '--host', '127.0.0.1', '--port', $port)
$server = Start-Process $serverExe -ArgumentList $serverArgs -PassThru `
    -WindowStyle Hidden -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog
```

Il body OpenAI-compatible deve contenere almeno:

```json
{"model":"ds4","messages":[{"role":"user","content":"<prompt famiglia>"}],
 "max_tokens":160,"temperature":0,"think":false}
```

Il logger osserva il percorso tiering esistente; non serve
`DS4_EXPERT_TIERING_LOG` (non esiste nel tree corrente). Per il contratto
storico atteso, ciascun log deve contenere 6.923 righe, cioè `43 * 161`
posizioni/layer. Conservare separatamente, per esempio,
`family-a/server.stderr.log` e `family-b/server.stderr.log`.

## Pipeline offline

Da PowerShell, per ciascuna famiglia:

```powershell
python .microbench/t0/scripts/parse_trace.py `
  family-a/server.stderr.log family-a/routes.json `
  --expect-tokens 161 --expect-layers 43

python .microbench/t0/scripts/overlap.py family-a/routes.json `
  --capacity 140 --windows 10,20
```

`parse_trace.py` produce JSON compatto nella forma
`{token: {layer: [6 ID]}}`, rifiuta righe malformate, coordinate conflittuali,
ID fuori range e token incompleti. È stato scelto JSON, non NPZ, per mantenere
la consegna stdlib pura e ispezionabile.

`overlap.py` stampa l'aggregato e le curve per layer:

1. overlap normalizzato degli esperti allo stesso layer fra `t` e `t+1`;
2. hit-rate della LRU semplice globale su chiavi `(layer, expert)`, cap 140;
3. hit-rate dell'oracolo con route esatta del token successivo e finestra
   protetta/JIT di 10 e 20 layer negli stessi 140 slot.

L'oracolo conta il token 0 freddo; il lookahead esatto di un token parte dal
token 1. La finestra include layer corrente più `W` layer futuri, quindi W20
protegge al massimo `21 * 6 = 126` slot. Gli slot restanti mantengono il
contenuto precedente; quando serve spazio l'oracolo sfratta soltanto chiavi
fuori dalla finestra protetta. La colonna `lru_miss_conversion` misura i nuovi
hit dell'oracolo come frazione dei miss LRU140.

Quando esisterà la seconda traccia c-lite:

```powershell
python .microbench/t0/scripts/fidelity_harness.py `
  family-a/routes.json family-a/routes-c-lite.json
```

La conversione è `|veri ∩ predetti| / |veri|`; la precisione è
`|veri ∩ predetti| / |predetti|`. Sono stampate per layer e aggregate.
Coordinate mancanti o extra rendono il risultato `KILL`, oltre alle soglie
`conversione >= 0,75` e `precisione >= 0,85`. Exit code: `0` PASS, `1` KILL,
`2` input/uso non valido.

## Verifiche previste

Questa consegna non compila e non avvia server. I controlli offline sono:

```powershell
git apply --check .microbench/t0/logids.patch
python -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.microbench/t0/scripts').glob('*.py')]"
```

Gli SHA-256 vanno calcolati sull'artefatto finale con:

```powershell
Get-ChildItem .microbench/t0 -File -Recurse |
  Sort-Object FullName | Get-FileHash -Algorithm SHA256
```
