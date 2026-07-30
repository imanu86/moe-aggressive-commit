# Quantizzazione del backbone: inventario, aritmetica e disegno

Data: 2026-07-30. Mandato di sola analisi/disegno: nessuna compilazione,
nessun server e nessuna modifica ai sorgenti. Deliverable unico: questa nota.

## 0. Verdetto

Il dato decisivo emerso dal GGUF reale e' che il backbone **non e' F16**:
dei `7.742.323.036 B` file-backed residenti, `6.598.885.376 B` (85,2313%)
sono gia' Q8_0, `1.132.283.904 B` (14,6246%) sono F16,
`1.845.596 B` (0,0238%) sono F32 e `9.308.160 B` (0,1202%) sono I32
(byte esatti dalla directory di `C:\ds4-models\ds4-2bit.gguf`).
Quindi **F16 -> Q4_K non dimezza il backbone**: il tetto aritmetico e'
`813.829.056 B`, cioe' il 10,5114% del backbone. Per dimezzare davvero
servirebbe requantizzare anche i 6,60 GB Q8_0 di attenzione/shared/testa,
la parte piu' sensibile e oggi priva di kernel dense Q4/Q5/Q6 nel runtime.

C'e' comunque un primo gradino utile: Q8_0 sulle sole matrici F16 che non
decidono selezioni discrete (`hc_*_fn`, `attn_compressor_{kv,gate}`,
`output_hc_fn`) riduce di `275.558.400 B = 262,793 MiB`. Sottratto al
working set sano misurato, porta **per stima** `6,87 -> 6,613 GiB`, appena
sotto il plateau malato di 6,63 GiB. E' sufficiente sulla carta a eliminare
il confine di capacita', senza toccare router e indexer; il margine e' pero'
solo circa 17 MiB rispetto al 6,63 arrotondato, quindi va provato dai
contatori, non assunto. Il meccanismo del confine e i due plateau sono
misurati in `.microbench/stormdiag_codex/NOTA.md:31-55`.

Scelta: **(c), sidecar Q8_0 opt-in e fail-closed**, cominciando dal sottoinsieme
da 587.857.920 B F16 sopra. Riusa il precedente multi-mappa del sidecar Q1,
mantiene intatto il GGUF autorevole, richiede solo ~312.299.520 B di payload
Q8 e permette ablation per famiglia. Non consegno una patch: prima occorre
costruire il convertitore/receipt e il golden di qualita' a 8000 token.

## 1. Provenienza e metodo

File ispezionato:

- `C:\ds4-models\ds4-2bit.gguf`, `86.720.111.488 B`, GGUF v3, 1.328 tensori,
  62 KV, alignment 32, tensor-data offset `5.333.824 B`;
- SHA-256 gia' verificato:
  `efc7ed607ff27076e3e501fc3fefefa33c0ed8cf1eff483a2b7fdc0c2e616668`
  (`C:\ds4-models\ds4-2bit.gguf.receipt.json:2-9`).

Ho letto soltanto header e directory, non gli 86,7 GB di payload. Per ogni
tensore: `elements = prodotto(dims)` e
`bytes = elements / block_elems * block_bytes`. Sono le stesse operazioni
del loader (`ds4-p4a/ds4.c:1406-1454`, `ds4-p4a/ds4.c:1221-1227`) e del
parser sidecar (`tools/gptq_to_sidecar.py:301-356`). La somma dei payload e'
`86.714.775.900 B`; il delta di `5.335.588 B` rispetto al file e'
header/directory/alignment, non pesi.

Definizione operativa: backbone file-backed = tutti i tensori esclusi i
routed expert `*.ffn_{gate,up,down}_exps.weight` e l'embedding servito per
riga. E' esattamente il filtro della startup cache
(`ds4-p4a/ds4.c:1883-1887`, `ds4-p4a/ds4.c:1900-1902`,
`ds4-p4a/ds4.c:1915-1947`). A contesto lungo, un token percorre tutti i 43
layer e la testa (`ds4-p4a/ds4.c:15576-15613`).

Correzione rispetto all'inventario precedente: il GGUF reale contiene 40,
non 43, `exp_probs_b.bias`, e `token_embd.weight` e' esattamente
`1.059.061.760 B` (`4096*129280*2`). Per questo il backbone esatto e'
`7.742.323.036 B`, 3.072 B meno dei `7.742.326.108 B` geometrici in
`.microbench/backbone_bytes/MISURA.md:30-39`. Il per-token precedente usava
gia' correttamente solo 40 bias (`.microbench/backbone_bytes/MISURA.md:85-90`).

## 2. Inventario per categoria

`letti/token` e' per decode a posizione >2048, dove l'indexer e' attivo.
Il conteggio per singola famiglia e il percorso kernel sono gia' auditati
in `.microbench/backbone_bytes/MISURA.md:61-115` e
`.microbench/backbone_bytes/MISURA.md:127-173`. I byte residenti qui sotto
sono stati ricalcolati dalla directory reale.

| categoria | nomi inclusi | tipo attuale | byte residenti esatti | quota di 7.742.323.036 | byte letti/token |
|---|---|---|---:|---:|---:|
| Attenzione densa | `attn_q_a`, `attn_q_b`, `attn_kv`, `attn_output_a/b` | Q8_0 | 4.886.495.232 | 63,1141% | 4.886.495.232 |
| Shared expert | `ffn_gate/up/down_shexp` | Q8_0 | 1.149.763.584 | 14,8504% | 1.149.763.584 |
| Testa | `output`, `output_hc_*`, `output_norm` | Q8_0+F16+F32 | 562.774.036 | 7,2688% | 562.774.036 |
| Hyper-connection layer | `hc_attn_*`, `hc_ffn_*` | F16+F32 | 67.642.440 | 0,8737% | 67.642.440 |
| Compressori attenzione | `attn_compressor_*` | F16+F32 | 522.971.136 | 6,7547% | 520.168.256 |
| Indexer sparso | `indexer.*`, `indexer_compressor_*` | F16+F32 | 451.465.728 | 5,8311% | 451.425.408 |
| Router | `ffn_gate_inp`, `exp_probs_b`, `ffn_gate_tid2eid` | F16+F32+I32 | 99.526.656 | 1,2855% | 90.218.568 |
| Norme/sink restanti | `attn_norm`, `q_a_norm`, `kv_a_norm`, `ffn_norm`, `attn_sinks` | F32 | 1.684.224 | 0,0218% | 1.684.224 |
| **Totale** | | Q8_0+F16+F32+I32 | **7.742.323.036** | **100%** | **7.730.171.748 (99,8431%)** |

L'embedding e' fuori tabella: `token_embd.weight`, F16
`4096x129280 = 1.059.061.760 B`; con row staging si leggono solo
`8.192 B/token` (`ds4-p4a/ds4.c:15538-15545`).

### 2.1 Inventario nominale completo

`blk.N` significa tutte le occorrenze dichiarate nella colonna layer.
Layer r4 = `2,4,...,42` (21); layer r128 = `3,5,...,41` (20); questa
partizione deriva dalla ratio del modello
(`.microbench/backbone_bytes/MISURA.md:51-55`).

| nome GGUF | layer/count | dims | tipo | byte/tensore | byte totali |
|---|---:|---:|---|---:|---:|
| `blk.N.hc_attn_fn.weight` | 0..42 / 43 | 16384x24 | F16 | 786.432 | 33.816.576 |
| `blk.N.hc_attn_scale.weight` | 0..42 / 43 | 3 | F32 | 12 | 516 |
| `blk.N.hc_attn_base.weight` | 0..42 / 43 | 24 | F32 | 96 | 4.128 |
| `blk.N.attn_norm.weight` | 0..42 / 43 | 4096 | F32 | 16.384 | 704.512 |
| `blk.N.attn_q_a.weight` | 0..42 / 43 | 4096x1024 | Q8_0 | 4.456.448 | 191.627.264 |
| `blk.N.attn_q_a_norm.weight` | 0..42 / 43 | 1024 | F32 | 4.096 | 176.128 |
| `blk.N.attn_q_b.weight` | 0..42 / 43 | 1024x32768 | Q8_0 | 35.651.584 | 1.533.018.112 |
| `blk.N.attn_kv.weight` | 0..42 / 43 | 4096x512 | Q8_0 | 2.228.224 | 95.813.632 |
| `blk.N.attn_kv_a_norm.weight` | 0..42 / 43 | 512 | F32 | 2.048 | 88.064 |
| `blk.N.attn_sinks.weight` | 0..42 / 43 | 64 | F32 | 256 | 11.008 |
| `blk.N.attn_output_a.weight` | 0..42 / 43 | 4096x8192 | Q8_0 | 35.651.584 | 1.533.018.112 |
| `blk.N.attn_output_b.weight` | 0..42 / 43 | 8192x4096 | Q8_0 | 35.651.584 | 1.533.018.112 |
| `blk.N.attn_compressor_ape.weight` | r4 / 21 | 1024x4 | F16 | 8.192 | 172.032 |
| `blk.N.attn_compressor_kv.weight` | r4 / 21 | 4096x1024 | F16 | 8.388.608 | 176.160.768 |
| `blk.N.attn_compressor_gate.weight` | r4 / 21 | 4096x1024 | F16 | 8.388.608 | 176.160.768 |
| `blk.N.attn_compressor_norm.weight` | r4 / 21 | 512 | F32 | 2.048 | 43.008 |
| `blk.N.attn_compressor_ape.weight` | r128 / 20 | 512x128 | F16 | 131.072 | 2.621.440 |
| `blk.N.attn_compressor_kv.weight` | r128 / 20 | 4096x512 | F16 | 4.194.304 | 83.886.080 |
| `blk.N.attn_compressor_gate.weight` | r128 / 20 | 4096x512 | F16 | 4.194.304 | 83.886.080 |
| `blk.N.attn_compressor_norm.weight` | r128 / 20 | 512 | F32 | 2.048 | 40.960 |
| `blk.N.indexer.attn_q_b.weight` | r4 / 21 | 1024x8192 | F16 | 16.777.216 | 352.321.536 |
| `blk.N.indexer.proj.weight` | r4 / 21 | 4096x64 | F16 | 524.288 | 11.010.048 |
| `blk.N.indexer_compressor_ape.weight` | r4 / 21 | 256x4 | F16 | 2.048 | 43.008 |
| `blk.N.indexer_compressor_kv.weight` | r4 / 21 | 4096x256 | F16 | 2.097.152 | 44.040.192 |
| `blk.N.indexer_compressor_gate.weight` | r4 / 21 | 4096x256 | F16 | 2.097.152 | 44.040.192 |
| `blk.N.indexer_compressor_norm.weight` | r4 / 21 | 128 | F32 | 512 | 10.752 |
| `blk.N.hc_ffn_fn.weight` | 0..42 / 43 | 16384x24 | F16 | 786.432 | 33.816.576 |
| `blk.N.hc_ffn_scale.weight` | 0..42 / 43 | 3 | F32 | 12 | 516 |
| `blk.N.hc_ffn_base.weight` | 0..42 / 43 | 24 | F32 | 96 | 4.128 |
| `blk.N.ffn_norm.weight` | 0..42 / 43 | 4096 | F32 | 16.384 | 704.512 |
| `blk.N.ffn_gate_inp.weight` | 0..42 / 43 | 4096x256 | F16 | 2.097.152 | 90.177.536 |
| `blk.N.exp_probs_b.bias` | 3..42 / 40 | 256 | F32 | 1.024 | 40.960 |
| `blk.N.ffn_gate_shexp.weight` | 0..42 / 43 | 4096x2048 | Q8_0 | 8.912.896 | 383.254.528 |
| `blk.N.ffn_up_shexp.weight` | 0..42 / 43 | 4096x2048 | Q8_0 | 8.912.896 | 383.254.528 |
| `blk.N.ffn_down_shexp.weight` | 0..42 / 43 | 2048x4096 | Q8_0 | 8.912.896 | 383.254.528 |
| `blk.N.ffn_gate_tid2eid.weight` | 0..2 / 3 | 6x129280 | I32 | 3.102.720 | 9.308.160 |
| `output_hc_fn.weight` | 1 | 16384x4 | F16 | 131.072 | 131.072 |
| `output_hc_scale.weight` | 1 | 1 | F32 | 4 | 4 |
| `output_hc_base.weight` | 1 | 4 | F32 | 16 | 16 |
| `output_norm.weight` | 1 | 4096 | F32 | 16.384 | 16.384 |
| `output.weight` | 1 | 4096x129280 | Q8_0 | 562.626.560 | 562.626.560 |

Il binder richiede esattamente questi nomi
(`ds4-p4a/ds4.c:3443-3502`) e ne valida tipi/dimensioni
(`ds4-p4a/ds4.c:3140-3208`).

## 3. Aritmetica F16 -> Q8/Q6/Q5/Q4

Base F16 quantizzabile nella tabella: `1.132.283.904 B` residenti e
`1.129.521.664 B/token` effettivamente letti. Le differenze sono le righe
APE non usate nel token corrente. Geometria GGML:
Q8_0 `34 B/32`, Q6_K `210 B/256`, Q5_K `176 B/256`, Q4_K `144 B/256`
(`tools/gptq_to_sidecar.py:104-134`). Tutte le righe F16 hanno dim0
divisibile per 256, quindi i payload sotto non hanno blocchi parziali.

I risparmi residenti sono **esatti per il formato ipotizzato**. I risparmi
letti/token sono esatti sotto il contratto di un kernel quantizzato
one-pass che legga una volta ogni blocco usato, come fa oggi Q8_0
(`ds4-p4a/ds4_cuda.cu:23204-23316`); Q5/Q6 non hanno ancora quel kernel,
quindi restano una proiezione, non una misura runtime.

| conversione di tutti gli F16 | nuovo payload F16 | residenti risparmiati | letti/token risparmiati | nuovo backbone | nuovo letto/token | working set 6,87 GiB (stima) |
|---|---:|---:|---:|---:|---:|---:|
| F16 -> Q8_0 | 601.525.824 | 530.758.080 B (506,170 MiB) | 529.463.280 B | 7.211.564.956 | 7.200.708.468 | 6,376 GiB |
| F16 -> Q6_K | 464.413.320 | 667.870.584 B (636,931 MiB) | 666.241.294 B | 7.074.452.452 | 7.063.930.454 | 6,248 GiB |
| F16 -> Q5_K | 389.222.592 | 743.061.312 B (708,638 MiB) | 741.248.592 B | 6.999.261.724 | 6.988.923.156 | 6,178 GiB |
| F16 -> Q4_K | 318.454.848 | 813.829.056 B (776,128 MiB) | 811.843.696 B | 6.928.493.980 | 6.918.328.052 | 6,112 GiB |

La colonna 6,87 e' una **stima**: sottrae i payload esatti da un plateau
loggato con due decimali. Non include allineamenti/raggruppamenti dei range,
workspace CUDA o una diversa frammentazione del pool. Il runtime fonde
tensori distanti fino a 64 KiB negli span (`ds4-p4a/ds4.c:1948-1968`), quindi
il solo test corretto del confine e' `g_model_range_bytes` a fine token 2,
come stabilito in `.microbench/stormdiag_codex/NOTA.md:75-88`.

### 3.1 Primo gradino prudente

Famiglie: i 86 `blk.*.hc_{attn,ffn}_fn`, le 82 matrici
`blk.*.attn_compressor_{kv,gate}` e `output_hc_fn`. Totale F16:
`587.857.920 B`; in Q8_0: `312.299.520 B`; risparmio:
`275.558.400 B`. Sono tutte GEMV dense a uscita continua; nessuna produce
direttamente un indice top-k. Q8_0 usa un kernel gia' esistente e collaudato
sulle proiezioni del backbone (`ds4-p4a/ds4_cuda.cu:23204-23321`).

| gradino | risparmio residente | risparmio letto/token | working set stimato |
|---|---:|---:|---:|
| solo famiglie prudenti -> Q8_0 | 275.558.400 B | 275.558.400 B/token | 6,613 GiB |
| solo famiglie prudenti -> Q6_K | 346.744.320 B | 346.744.320 B/token | 6,547 GiB |
| solo famiglie prudenti -> Q5_K | 385.781.760 B | 385.781.760 B/token | 6,511 GiB |
| solo famiglie prudenti -> Q4_K | 422.522.880 B | 422.522.880 B/token | 6,476 GiB |

Chiamo il primo gradino "prudente", non "qualita' garantita": il compressore
costruisce la KV compressa e gli HC si accumulano per 43 layer. Solo il
protocollo al paragrafo 6 puo' promuoverlo a sicuro.

## 4. Cosa quantizzare e cosa no

### SI' al primo pilot, solo Q8_0

- `blk.*.attn_compressor_{kv,gate}.weight`:
  `520.093.696 B` F16. Influenza valori compressi ma non effettua la selezione
  top-k; le due GEMV girano a ogni token
  (`.microbench/backbone_bytes/MISURA.md:168-173`).
- `blk.*.hc_{attn,ffn}_fn.weight` + `output_hc_fn.weight`:
  `67.764.224 B` F16. Sono trasformazioni continue e Q8_0 e' gia' disponibile
  nel backend; il dispatch plain oggi accetta pero' solo F16/F32
  (`ds4-p4a/ds4.c:14756-14773`), quindi serve un ramo Q8 esplicito.

### NO al primo pilot

- **Indexer completo**, incluse le sue matrici compressor:
  `451.454.976 B` F16. Le proiezioni pesanti sono lette integralmente
  (`ds4-p4a/ds4.c:14004-14043`) e il loro risultato decide la top-k delle
  entry KV (`ds4-p4a/ds4.c:14053-14095`). Un errore cambia quali memorie
  vengono attese, non soltanto il valore della somma.
- **Router** `ffn_gate_inp.weight`: `90.177.536 B` F16. I logits alimentano
  immediatamente la selezione dei 6 expert
  (`ds4-p4a/ds4.c:14277-14290`); e' lo stesso rischio discreto dell'indexer.
- **Norme, scale/base HC, sink e bias**: `1.845.596 B` F32 totali. Sono
  precision-critical e il risparmio massimo F32->Q4 sarebbe irrilevante
  rispetto ai 275,6 MB gia' ottenibili. Il loader le valida F32
  (`ds4-p4a/ds4.c:3158-3166`, `ds4-p4a/ds4.c:3186-3192`).
- **APE** `*_compressor_ape`: `2.836.480 B` F16. Si legge una sola riga per
  token, quindi il guadagno di banda e' minuscolo
  (`.microbench/backbone_bytes/MISURA.md:150-156`); cambiare il layout
  posizionale aggiunge rischio e codice senza spostare il confine.
- **I32 hash tables**: sono indici, non pesi; 72 B letti/token su
  `9.308.160 B` residenti (`.microbench/backbone_bytes/MISURA.md:90`).
- **Attenzione, shared e testa Q8_0**: gia' quantizzati. Un ulteriore
  Q6/Q5/Q4 toccherebbe 85,23% del backbone e sarebbe l'unica via verso il
  dimezzamento, ma e' una fase distinta ad alto rischio. Il binder conferma
  Q8_0 per attenzione/shared/output
  (`ds4-p4a/ds4.c:3161-3168`, `ds4-p4a/ds4.c:3202-3204`,
  `ds4-p4a/ds4.c:3151`).

Q6_K e Q5_K sono **non implementabili con gli strumenti correnti**:
le geometrie sono dichiarate, ma `can_quantize=false`
(`ds4-p4a/gguf-tools/quants.c:39-54`) e il dispatcher di quantizzazione
gestisce soltanto Q8_0, Q2_K, Q4_K e IQ2_XXS
(`ds4-p4a/gguf-tools/quants.c:1050-1073`). Q4_K ha quantizer, ma nel runtime
le sue matvec sono limitate agli expert routed
(`ds4-p4a/ds4.c:6832-7041`), non alle dense del backbone.

## 5. Valutazione delle tre strade

### (a) Nuovo GGUF offline

Pro: un'unica mmap e la startup cache vede direttamente i payload ridotti;
nessuna doppia residenza. Contro: il tool esistente rigenera da HF
safetensors, non requantizza il GGUF
(`ds4-p4a/gguf-tools/README.md:59-67`), e supporta localmente solo Q8/Q4 fra
i candidati (`ds4-p4a/gguf-tools/README.md:8-12`). Soprattutto, "runtime non
cambia" e' falso in questo tree: il validator pretende F16 per HC,
compressori e indexer (`ds4-p4a/ds4.c:3157-3186`), mentre il dispatch plain
accetta solo F16/F32 (`ds4-p4a/ds4.c:14756-14773`). Un GGUF Q8 verrebbe
rifiutato prima del decode. Richiederebbe comunque una patch runtime e un
secondo file quasi grande quanto il modello.

Verdetto: buona destinazione finale dopo la validazione, non il pilot meno
rischioso.

### (b) Quantizzato residente + dequantizzazione/kernel on-the-fly

Per Q8 non serve espandere in F16: esiste gia' la GEMV nativa Q8 che legge
direttamente `34 B/32 pesi` (`ds4-p4a/ds4_cuda.cu:23204-23316`). Espandere
in VRAM annullerebbe il vantaggio di residenza. Q4/Q5/Q6 richiedono invece
nuovi kernel dense o una dequantizzazione a tile; Q5/Q6 richiedono anche il
quantizer. Fare conversione F16->quant a startup richiederebbe inoltre
buffer, ownership e cache-exclusion nuovi.

Verdetto: troppo codice nuovo per il primo gate; Q8 nativo resta il compute
usato dall'opzione (c), senza espansione persistente.

### (c) Sidecar selettivo -- SCELTA

Il tree ha gia' il precedente corretto:

- `model_open` di un secondo GGUF dietro env, bind e fail-closed
  (`ds4-p4a/ds4.c:22686-22703`);
- strutture che portano insieme `model` proprietario e tensori del sidecar
  (`ds4-p4a/ds4.c:2713-2745`, `ds4-p4a/ds4.c:2845-2874`);
- verifica di metadata/identita' e byte di controllo
  (`ds4-p4a/ds4.c:3517-3595`);
- writer atomico che rifiuta overwrite e verifica descriptor/byte copiati
  (`tools/gptq_to_sidecar.py:735-823`,
  `tools/gptq_to_sidecar.py:852-910`);
- precedente di neutralita' env-off e fail-closed misurati
  (`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:3018-3046`).

Il sidecar Q8 prudente pesa circa `312.299.520 B` piu' header, non 86,7 GB.
Il GGUF base resta autorevole e basta cambiare un flag per tornare al
comportamento attuale.

### 5.1 Disegno minimo

```text
DS4_BACKBONE_Q_SIDECAR assente
        |
        +--> percorso odierno byte-identico

DS4_BACKBONE_Q_SIDECAR=FILE + DS4_BACKBONE_Q_SET=hc+attncomp
        |
        +--> model_open(sidecar) + identita' base/receipt + whitelist esatta
        |
        +--> bind {owner_model, tensor_Q8} per le sole famiglie abilitate
        |
        +--> startup cache:
        |      esclude i corrispondenti F16 del base
        |      include i Q8 del sidecar
        |      prova: base_excluded - sidecar_cached = 275.558.400 B
        |
        +--> dispatch Q8_0 esistente; mai espansione F16 persistente
        |
        +--> qualunque mismatch => startup abort (fail-closed), mai fallback misto
```

Il quarto blocco e' obbligatorio. Oggi la cache enumera tutti i tensori base
non expert (`ds4-p4a/ds4.c:1915-1947`): se il binder scegliesse il sidecar
senza escludere gli originali, si terrebbero F16 e Q8 insieme e la leva
fallirebbe per costruzione.

Contratto proposto:

1. flag assente = nessuna apertura, nessuna nuova riga di log, stesso binder;
2. sidecar con whitelist solo dei 169 tensori del primo gradino; tipo Q8_0,
   dims e nome esatti; SHA-256/receipt legato allo SHA del base;
3. contatori startup:
   `overrides=169 base_excluded=587857920 sidecar_cached=312299520
   net_saved=275558400 duplicate_bytes=0`;
4. cache/loader keyed anche per `owner_model`, come gia' fa la sorgente expert;
5. mismatch, tensor mancante, tipo errato, doppione o span che ingloba un
   originale escluso => abort prima della sessione;
6. nessun hook nei percorsi vietati transiente/os_file, teardown/ledger,
   host-pin, stormfix, nextnfix, indexerzc o sharedcore.

Ordine di implementazione futuro: converter+validator offline; test fixture
minuscola; loader/binder sidecar; esclusione/cache accounting; dispatch Q8;
solo infine protocollo A/B. Non va scritto un kernel Q4/Q5/Q6 prima che Q8
superi qualita' e dimostri di chiudere il confine.

## 6. Protocollo di verifica qualita'

Lo SHA `c7525d909341a57a` su 8.145 caratteri e' un controllo di neutralita'
eccellente ma non una metrica per una trasformazione lossy
(`D:\ds4_work\lane_ab\REPORT.md:445-463`). Inoltre il run termina per
`finish_reason=length` a 2.250 token mentre e' ancora nel CSS
(`D:\ds4_work\lane_ab\runs\FB1_drain4\resp.json:1`): non puo' certificare
una pagina eseguibile.

### 6.1 Matrice di prova

Per **entrambe le famiglie di prompt deterministici della campagna**:

1. congelare byte del prompt, system prompt, temperatura 0, seed 12345,
   ctx 150k e ogni env; registrarli in un manifest con SHA-256;
2. baseline F16: due processi indipendenti, max 8000; candidate Q8: due
   processi indipendenti, max 8000;
3. richiedere determinismo interno: i due SHA candidate devono coincidere
   fra loro; non e' richiesto che coincidano col baseline;
4. ordine bilanciato `B-Q-Q-B` su macchina pulita. La posizione nel batch
   e' una variabile reale della campagna
   (`.microbench/stormdiag_codex/NOTA.md:59-88`);
5. conservare risposta JSON completa, HTML estratto, stderr, manifest,
   receipt sidecar e screenshot desktop/mobile.

Affiancare il corpus NLL gia' presente: 100 prompt e continuazioni
deterministiche (`ds4-p4a/gguf-tools/quality-testing/README.md:1-30`), con
`avg_nll`, wins, first-token match e greedy LCP
(`ds4-p4a/gguf-tools/quality-testing/README.md:56-71`). Questo misura
degrado generale; la rubrica sotto misura l'artefatto lungo.

### 6.2 Hard gate automatici sull'HTML completo

Fallimento immediato se uno dei due prompt non soddisfa **tutti**:

- `finish_reason=stop` prima/entro 8000, un solo fence HTML chiuso, un solo
  `<!DOCTYPE html>`, `</head>`, `</body>`, `</html>`;
- parser HTML: zero errori fatal; parser CSS: zero regole troncate e zero
  blocchi/graffe non chiusi; parser JS: sintassi valida;
- tutti i requisiti del prompt trasformati in assert: titolo/brand
  NeuraForge, header/nav, hero+CTA, feature cards, esattamente 3 tier pricing,
  form con label/input/textarea/submit, footer, breakpoint responsive e
  validazione form. La lista va generata dal testo del prompt congelato, non
  adattata dopo aver visto l'output;
- ogni `href="#id"` risolve un id unico; label `for` risolve un input; nessun
  id duplicato; zero URL `javascript:` e zero tag/script estranei al compito;
- rendering headless a 1440x900 e 390x844: `scrollWidth <= clientWidth+1`,
  sezioni con bounding box non vuota, zero eccezioni console; click di ogni
  nav anchor e submit vuoto producono il comportamento previsto;
- nessuna sequenza di 4 parole ripetuta tre volte consecutivamente, nessun
  run di caratteri corrotti, nessun passaggio brusco a testo non HTML dentro
  il fence.

### 6.3 Rubrica 100 punti, artefatto completo

Due valutatori ciechi rispetto a B/Q; divergenza >10 punti va arbitrata.

| voce | punti | criterio verificabile |
|---|---:|---|
| Completezza requisiti | 30 | 3 punti per ciascuno dei 10 assert congelati; niente credito parziale |
| Validita' HTML/CSS/JS | 20 | 10 parse/struttura, 5 link/label/id, 5 interazioni senza errori |
| Coerenza contenuto | 15 | brand, lingua, testi pertinenti e prezzi/features coerenti fra sezioni |
| Layout desktop | 10 | gerarchia, leggibilita', nessuna sovrapposizione/clipping negli screenshot |
| Layout mobile | 10 | stessa verifica a 390x844, nav/form/tier usabili |
| Qualita' visiva | 10 | cyberpunk neon coerente, contrasto e spaziatura; voto cieco 0..10 |
| Assenza degenerazioni | 5 | zero loop, glifi corrotti, frasi spezzate o filler |

Gate di promozione del gradino: hard gate 100% su quattro run, score medio
candidate >=90/100 su ciascuna famiglia, nessun run candidate oltre 5 punti
sotto il peggior baseline, e delta `avg_nll` <= +2% sul corpus da 100 prompt.
La soglia NLL e' una proposta, non una misura esistente.

### 6.4 Gate meccanico separato dalla qualita'

Il candidato passa la leva soltanto se, oltre alla rubrica:

- `g_model_range_bytes` raggiunge il nuovo working set entro fine token 2;
- token 3..fine: `evict_backbone <= 5/token` e
  `reloads/evictions` non presenta il regime ~1 della tempesta;
- accounting startup mostra `duplicate_bytes=0` e almeno
  `275.558.400 B` netti liberati;
- Q8 sidecar bytes letti/token coincidono con il modello aritmetico;
- throughput sostenuto e mediana sono riportati, ma non possono compensare
  un fallimento qualita'.

Solo dopo questo gate ha senso provare, uno alla volta: HC senza compressori,
compressori senza HC, poi eventualmente indexer o router in ablation
separata. Q6/Q5/Q4 non entrano nel piano finche' Q8 non supera tutti i gate.
