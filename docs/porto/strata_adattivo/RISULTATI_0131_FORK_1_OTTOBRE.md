# 0.1.31 e fork 2080 Ti — laboratorio del 1 ottobre 2026

Lavoro sospeso su richiesta dell'utente dopo la corsa A/B/A della dequantizzazione vettoriale.
**Il lanciatore operativo resta 0.1.30 + PR270, KV int8 262.144.** Nessuna promozione.
Il riempimento a circa 250k token reali e la qualita' della variante HC/GDN FP16 restano da provare.

## Provenienza e isolamento

- Upstream 0.1.31: `9259cad4cfa3543cd3b8decab5962672b968c649`, sorgenti esportati nella
  cartella `.codex_runs/strata_0131_sm75_20261001/source`, senza checkout Git.
- Nove patch locali conservate: routing trace, checkpoint allineati, cache elastica VMM,
  due zone, shrink a pressione zero, benchmark esperti, benchmark stabile, adattamento
  `pf_parts`, commit asincrono. Le parti IQ decode-once, TILE sm75, HC opt-in e #270
  gia' upstream non vengono duplicate. #315 non inserita.
- Le risoluzioni degli incastri sono in `prepara_0131.py`: nuova funzione di fallback dei
  chunk conservata insieme al massimo del buffer elastico; diagnostica di avanzamento
  conservata insieme all'allineamento dei checkpoint; benchmark adattato a `iq_set_old_kernels`.
  Ricostruzione da un secondo export pulito: **stessi SHA256 dei nove file modificati**.
- Compilazione CUDA 12.6/MSVC 19.44, Release, sm75+sm86, due lavori. Dipendenze ggml gia'
  presenti nel clone su D:, nessun download di binari o dipendenze. Runtime CUDA esplicitamente
  `Shared`: il primo link aveva incluso sia `cudart` sia `cudart_static`, causando simboli
  duplicati. Correzione di configurazione; link successivo riuscito senza ricompilare i kernel.
- Server Python della 0.1.31 per tutte le corse A/B/A; stesso pack IQ3_XXS, tokenizer, MTP,
  profilo esperti e fixture del banco P0. Nessun carico artificiale, nessuna compilazione
  durante una corsa del modello. La chiave API esclusa dal processo di laboratorio.

## Controlli numerici

Base 0.1.31:

- `iq_multi_parity`: zero fallimenti, percorsi nuovi identici bit per bit agli originali.
- `mmvq_multi_parity`: 148.480 risultati identici con `multi_exact`; il controllo negativo
  trova 63.901 differenze, quindi il banco distingue un percorso non equivalente.
- `gr_parity --selftest`: zero fallimenti, incluse dimensioni reali e replay del grafo.
- QSA: quattro casi, contesti 32.768/1.500/2.100, int8 e FP16, 128 query, zero fallimenti
  rispetto al riferimento FP64 entro le tolleranze del test upstream.

Dequantizzazione vettoriale:

- Codice del [commit ea158a9](https://github.com/jklnvlink/Strata-2080ti/commit/ea158a93ed30340092f1bf4a13522231062453f5),
  piu' il selettore esatto cc 7.5. Il suo parent per `dequant_bf16.cu` coincide con la nostra
  base 0.1.31. Ricompilato un solo oggetto; gli altri oggetti della base sono riusati.
- **18 confronti bitwise sui GGUF reali**: Q5_K, IQ4_XS, IQ4_NL, Q6_K, Q2_0, Q4_K;
  BF16, FP16 e FP32; sette righe a partire da `row0=1` del primo tensore di ogni formato.
  Scalar/vector nella candidata identici; digest anche identici a un eseguibile di controllo
  collegato con la libreria kernel della base. Guardie del buffer integre.
- Questo controllo copre le righe indicate, non ogni valore di tutti i tensori del modello.

## Prova sul modello a 131k

Capacita' KV **262.144**, residenti **32.768**, due richieste L01/L02 da circa 131k,
1024 token generati ciascuna. L01 legge 131.248 token da zero; L02 riusa 131.072 token e
legge solo 167 nuovi: il suo prefill non e' una seconda misura del prefill completo.

Un primo avvio con budget cache 5.000 e' stato escluso prima dei prompt: 6.705 slot
effettivi, 900 MiB liberi, sotto la guardia da 1.000 MiB. Budget ridotto a **4.200** per
tutte le corse accettate: **5.621 slot effettivi, 9.330 MiB di cache, circa 2,4 GiB liberi**.
La configurazione e' diversa dalle precedenti prove a 6.705 slot e dal lanciatore elastico.
Non interpretare la differenza di velocita' rispetto a quelle corse come effetto della versione.

| Corsa | Prefill L01 t/s | TTFT L01 s | Decode L01 / L02 t/s | Decode aggregato t/s | ms/riga aggregati |
|---|---:|---:|---:|---:|---:|
| A1 | 752.52 | 174.977 | 36.295 / 37.377 | 36.828 | 22.469 |
| B | 756.44 | 174.076 | 42.418 / 37.619 | 39.875 | 21.276 |
| A2 | 754.99 | 174.476 | 39.957 / 36.966 | 38.403 | 21.599 |

Prefill della candidata: +0,52% rispetto ad A1 e +0,19% rispetto ad A2, circa **+0,36%**
rispetto alla media delle basi. Il +5% dichiarato dal fork non e' riprodotto qui; queste
misure non giustificano una promozione. Tutte le sei richieste terminano a 1024 token.

Le impronte del testo L01 e L02 sono diverse fra tutte e tre le corse. Cambiano anche
accettazione MTP e tempi per riga: il decode aggregato della stessa base passa da 36,828
a 38,403 t/s (+4,28%). Il valore della candidata 39,875 t/s non dimostra un beneficio
del kernel di prefill sul decode. Dettaglio riproducibile in `confronto.json`.

Confrontare anche testo generato, accettazione MTP, costo per riga e CPU esterna. La cache
fissa mantiene il numero di slot; non impone equivalenza delle risposte o dell'accettazione.
Una variazione del decode non va attribuita al kernel di dequantizzazione del prefill.

## HC/GDN FP16: preparata, non ancora validata sul modello

Variante separata, senza dequantizzazione vettoriale. Portati i commit `56495c3`, `500d12e`,
la restrizione cc 7.5 di `b4f8a44` e il budget di `bdea4cb`. Il budget aggiuntivo conta solo
i tre buffer HC realmente allocati; la variante non alloca una copia PLE FP16. Draft/MTP
rimane BF16. Le firme nuove dei kernel mantengono il parametro opzionale per la copia FP16.

- Compilazione di tre oggetti e link riusciti. **12 controlli superati** a T=1/7/128:
  i tre percorsi di normalizzazione mantengono BF16 e producono la copia FP16 del percorso
  unfused; SiLU mantiene BF16 e produce la copia FP16 attesa su un ingresso noto.
- Il primo test SiLU aveva usato `0xA5A5` come sentinella: puo' coincidere con un risultato
  FP16 valido. Il falso allarme e' stato corretto nel banco usando un valore atteso noto;
  nessuna modifica al kernel per questo controllo.
- Verificate tutte le **360 matrici HC/GDN** del pack, 641.925.120 valori BF16: nessun
  overflow/non-finito dopo conversione, massimo valore assoluto 8,5625. **69.729 valori
  non sono esatti in FP16**: il massimo errore assoluto di conversione e' 2,9802322e-8.
  Il commento del fork sulla conversione lossless non vale senza questa verifica sul nostro
  pack. Inoltre FP16 cambia arrotondamento delle attivazioni e accumulazione GEMM.
- **Nessuna prova di velocita', logits o retrieval sul modello per questa variante**:
  la richiesta di pausa e' arrivata prima dell'avvio. La parita' delle copie non dimostra
  equivalenza del percorso completo HC/GDN FP16.

## Ripresa

1. Confronto vettoriale completato: nessuna promozione; rivalutarlo solo se nuove misure
   o un profilo diverso giustificano un'altra prova.
2. Provare HC/GDN FP16 con la stessa cache e fixture; aggiungere retrieval a 32k, profondita'
   10/50/90, usando gli stessi sorgenti del filler per riferimento e candidata. Controllare
   logits/qualita' prima di qualsiasi promozione.
3. Riempimento distinto a >=250.000 token reali: `retrieval_250k.py` prepara un prompt usando
   tokenizer e chat template del modello, verifica il conteggio runtime e un ago al 50%.
   **Script preparato, non ancora eseguito**. Il limite KV 262.144 non equivale a questa prova.
4. Confronto col lanciatore PR270, poi eventuale conferma elastica. Nessuna automazione o
   ulteriore corsa durante la pausa; attendere una nuova richiesta dell'utente.

## Artefatti

Patch in `patches/su-0.1.31/`: `0016` porting locale, `0017` dequant vettoriale,
`0018` HC/GDN FP16. Le ultime due sono varianti alternative da applicare alla base con `0016`.
Strumenti di preparazione, compilazione e parita' in `strumenti/`.
Evidenza curata in `corse_2080ti/20261001_0131_fork/`; build e snapshot completi restano in
`.codex_runs/`. I binari non vengono pubblicati nel repository.

Al termine: eseguibile operativo verificato SHA256 `713922610f2820b0e726adc371eb774a7d5502a548d08b59d244afbb38e898ed`, JSON ancora PR270/KV262144,
lanciatore Desktop ancora sulla stessa configurazione. Nessun motore o compilatore del
laboratorio rimasto acceso. La chat OCGC-IA e' stata informata della disponibilita' GPU
rispetto a Strata: coordinarsi prima della prossima ripresa. Nessuna ripresa automatica.
