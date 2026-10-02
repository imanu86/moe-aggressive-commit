# QSA CH16 e profiling del daily — 2 ottobre 2026

Finestra GPU 05:24–05:50, limite concordato 05:54. **Candidato concreto:
QSA prompt int8 CH16, kernel isolato 21,904 → 16,142 ms (−26,30%)**.
Quattro controlli numerici superati; nessuna prova del modello con CH16,
nessuna promozione. Daily operativo a74e preservato, KV 262144 e cache elastica.
Nessun carico artificiale. Processi propri chiusi, VIA inviato a OCGC-IA/PROMO.

## Cosa abbiamo misurato

Nsight Systems 2024.5.1 sul daily reale, prompt previsto 131248 token e KV
int8 residente 32768 / capacita' 262144. Trace CUDA node, avvio cattura dopo
45 s, durata 240 s. Timer interni VERIFY_PROFILE e PREFILL_TIMING accesi.
La combinazione ha perturbato pesantemente la corsa: timeout complessivo
480 s, nessuna richiesta lunga completata e nessuna misura decode utilizzabile.
Questo esito descrive una prova strumentata; non dimostra un rallentamento
operativo. Nsight termina la propria cattura prima del target su Windows:
exit 0 del profiler non implica completamento della richiesta.

Sono disponibili 47 chiamate del kernel **v1 prompt_attn_kernel<1>**:
grid 8192×2, 128 thread, 128 registri/thread, **37904 B = 37,02 KiB shared**,
zero memoria locale/thread, media 83,008 ms. Turing usa questo v1;
la pipeline cp.async dei fork sm80+ non e' il percorso attivo della 2080 Ti.

Fra la prima e l'ultima di queste chiamate: intervallo 123,511 s,
somma dei kernel 25,739 s. Matrici/esperti 56,79%, attenzione QSA 15,16%,
GDN 7,48%, selezione QSA 6,57%, HC 3,11%, altro 10,89% della somma kernel.
Raggruppamento per nome, finestra parziale iniziale; **non sono quote del
runtime normale o del modello intero**. Anche la frazione GPU attiva 20,84%
e' perturbata dai timer/eventi e dal profiler: non usarla come utilizzo daily.

Nsight Compute 2024.3.2 separato dai timer interni, tre chiamate previste dopo
360 kernel di attenzione. Metriche richieste: gpu__time_duration.sum,
dram__bytes_read.sum, dram__bytes_write.sum; clock/cache non forzati.
La richiesta resta sul warmup di 61 token. Interrotta, engine riavviato dal
server e poi chiuso con tutti i discendenti propri. **Nessun contatore DRAM
catturato**; causa precisa del blocco non isolata. Nessuna modifica driver,
registro di Windows, clock o permessi globali.

## Perche' provare CH16

64 KiB shared/SM della Turing e 37904 B per blocco consentono un solo blocco:
4 warp sui 32 massimi, limite teorico 12,5% dell'occupazione dei warp.
CH16 richiede **27536 B = 26,89 KiB**, con preferenza carveout massimo per
la modalita' int8. Due blocchi diventano compatibili con i limiti shared e
registri: obiettivo teorico 8 warp / 32 = 25%, **non occupazione misurata**.
Oggetto sm75 candidato: 126 registri/thread int8, stack/local zero.

La prima variante CH16 non calcolava gli score: il ciclo CH/32 valeva zero.
Il banco l'ha respinta in tutti e quattro i casi (log conservato, tempi esclusi).
Correzione: assegnare i tile da 8 celle ai warp con nt=warp; nt<CH/8; nt+=4.
A CH32 conserva gli stessi tile; CH16 usa i primi due warp per gli score,
e tutti i quattro per il prodotto p.v. Il file sorgente e' compilato con
**-DD1_CH=16 sia lato host sia device**, non una macro basata su CUDA_ARCH.

## Banco della variante corretta

Riferimento CH32 dalla libreria esatta della daily, candidato CH16 con nome
pubblico distinto, nello stesso processo. Banco upstream adattato:
FP64 su un campione, confronto CH32/CH16 su tutti gli output, soglie originali
1e-4 della scala e limite relativo al riferimento FP64. Dati deterministici
con pagine permutate e selezioni sparse; nessun modello caricato. Tre ripetizioni
per il timing, ordine CH32 poi CH16: singolo confronto, nessun A/B/A.

| KV / contesto / query | CH32 ms | CH16 ms | Differenza | Esito numerico |
|---|---:|---:|---:|---|
| int8 / 131072 / 2048 | 21,904 | 16,142 | −26,30% | PASS |
| fp16 / 131072 / 2048 | 28,241 | 38,694 | +37,01% | PASS |
| int8 / 1500 / 1500 | 6,490 | 4,133 | −36,32% | PASS |
| int8 / 2100 / 256 | 2,355 | 1,849 | −21,49% | PASS |

A 131k int8 errore massimo FP64 3,78e-6 CH32 / 3,79e-6 CH16;
differenza fra kernel 5,25e-6, circa 1,4e-6 della scala. **Non bitwise**:
softmax e accumulo hanno raggruppamenti differenti. FP16 peggiora, quindi
non applicare CH16 indiscriminatamente a tutte le modalita' KV.

Il contesto 131072 e' quello del pool del banco; sono 2048 query, non un
prefill reale di 131k token, e non usa il KV streaming del modello.
Il −26,3% non si trasferisce direttamente ai t/s totali. La quota attenzione
sul modello a contesto profondo resta da misurare senza doppia strumentazione.

## Prossimo passaggio concreto

1. Integrare una variante CH16 **solo su Turing + KV int8**, preservando CH32
   per FP16 e per gli altri dispositivi; mantenere l'override CH32 per A/B.
2. Ricompilare una candidata della combinazione daily, senza perdere HC/GDN FP16,
   vector, PR315 e le patch elastiche. Controllo numerico e A/B/A reale 131k,
   capacità 262144, cache auto/elastica, poi retrieval 250k e primi logits.
3. Promuovere nel lanciatore operativo solo dopo la prova combinata; il banco
   numerico corrente non valida qualita', stabilita' e t/s del modello.

Profiling fisico della banda ancora aperto: usare un banco senza kernel
persistenti per i contatori o isolare il blocco dell'instrumentazione NCU.
Letture logiche e percentuale NVML memory utilization non sono GB/s DRAM.
Durante il carico osservato memoria a 6800 MHz: 352 bit × 2 × 6800 MHz / 8
= circa 598,4 GB/s teorici; non abbiamo misurato quanti ne trasferisce il kernel.

Riferimenti primari: [Turing tuning guide](https://docs.nvidia.com/cuda/archive/12.6.2/turing-tuning-guide/index.html),
[NVML utilization](https://docs.nvidia.com/deploy/archive/R550/nvml-api/structnvmlUtilization__t.html),
[Nsight Compute profiling guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html).

## Riproduzione ed evidenza

Patch sperimentale `patches/su-0.1.31/0022-QSA-CH16-sperimentale.patch`:
la patch sola lascia il default CH32; il banco applica anche -DD1_CH=16.
Strumento `strumenti/prova_qsa_ch16.py --daily <bundle-operativo>
--daily-kernels <libreria-della-build-validata> --core-lib <strata_core.lib>
--out <cartella-nuova>`. Verifica che l'hash exe del bundle corrisponda al
build-result.json della libreria. Non modifica o promuove il bundle operativo.

Evidenza selezionata in `corse_2080ti/20261002_qsa_kernel/`;
trace/sqlite grezzi restano in .codex_runs e non vengono pubblicati.
JSON e BAT operativi confrontati byte per byte con le copie repository.
Exe operativo SHA256 a74e4dadcd4fbb9e71b5cb0ae66922453c6a44a2704db25ddfb5e81601c5f766.

## Ripresa successiva autorizzata dall'utente

Alle05:53 l'utente ha richiesto tutti i test necessari, piu' righe e lavoro sui
kernel, e ha vietato altre interazioni con OCGC-IA/PROMO. Nessun altro messaggio
a queste chat dopo quella richiesta. Il precedente limite della finestra e'
riferito alla prima serie conclusa; la nuova serie prosegue su autorizzazione.

**Candidata completa compilata:** `.codex_runs/strata_qsa_ch16_20261002/strata.exe`,
SHA256 437edc05de9cf0d755138d49e6d479c1660b7e3cea0204280d8133f80eac731d.
Patch0023: CH parametrizzato nei template; default16 solo Turing+int8,
STRATA_QSA_CH=32 per confronto, CH32 preservato per FP16/ibrido e altri GPU.
Tutti gli altri oggetti della combinazione daily riusati, hash nel build-result.

Banco upstream contro FP32 decode e FP64 ampliato a8192 query, quattro casi
superati. Banco distinto **stesso oggetto candidato CH32/CH16/CH32**, verifica
output finiti, FP64 e FP16 identico: **12 casi superati**, 128/2048/8192 query.
A8192 int8: **88,493530 /66,441116 /87,719933 ms**, −24,59% sulla media A;
variazione A/A0,88%. FP16108,231735/108,359215/109,262573ms, output uguale.
I casi piccoli mostrano rumore piu' ampio e non sostituiscono il chunk8192.

Nsight Compute sul banco isolato non si blocca piu' sul modello, ma restituisce
**ERR_NVGPUCTRPERM**, contatori prestazioni GPU non accessibili al processo
Windows corrente. Nessun contatore DRAM prodotto. Questo chiarisce il limite
dei contatori; non prova la causa del precedente blocco con il motore completo.
[Errore NVIDIA ufficiale](https://developer.nvidia.com/ERR_NVGPUCTRPERM).
I tempi stampati nella corsa NCU fallita sono esclusi dal confronto di velocita'.

**A/B/A reale avviato alle06:00**, stessa candidata con CH32/CH16/CH32,
cache auto/elastica, due richieste131k/1024output per corsa, diagnostica primi
logits. Seguiranno esiti e controllo250k prima di un'eventuale promozione.
