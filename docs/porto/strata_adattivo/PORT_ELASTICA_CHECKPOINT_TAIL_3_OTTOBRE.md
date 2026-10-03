# Port elastica e checkpoint tail — 3 ottobre 2026

Le due contribuzioni sono preparate separatamente su upstream 0.1.38
(`99f3dbd0b21d1401b3769e0c0d963913607f380b`). Il gate locale è passato.
Aperta [PR614 checkpoint tail](https://github.com/Niko1221/Strata/pull/614), pronta
per review. Dopo il controllo dei duplicati, l'elastica resta una proposta
da concordare con il maintainer per la sovrapposizione con37/378/563/533.
[Audit e messaggio inviato](CONTROLLO_DUPLICATI_PR614_3_OTTOBRE.md). Daily invariato.

## Cosa proponiamo

- **Elastica CUDA opt-in:** port della cache Daily originariamente realizzata
  da Claude Opus 5.5, con core fisso, coda ridimensionabile e indirizzi VMM
  stabili. Codex ha isolato il contributo e adattato il contesto 0.1.38,
  il link al driver CUDA e i token buffer al massimo chunk di prefill.
  CLI, layer split, peer/remote e resident CPU complement conservano la cache
  fissa; HIP ha fallback fisso, senza attestazione di compilazione/hardware AMD.
- **`--prompt-cache-tail` opt-in:** nuova alternativa Codex che salva al massimo
  un checkpoint aggiuntivo su un confine di chunk già raggiunto. Riutilizza la
  cache limitata esistente e non taglia i chunk. La patch checkpoint-grid del
  Daily conserva il FAIL numerico documentato: questa proposta non la dichiara
  corretta e non la sostituisce automaticamente nell'operativo.

## Parità e correttezza

Macchina: RTX 2080 Ti modificata a 22 GB, Ryzen 5800X, 96 GB RAM;
CUDA 12.6/MSVC 14.44. GGML pin `3cf03257f219afbe7334045ff7c6a06ac68c627d`.
KV int8, capacità 262144 e 32768 residenti. Le prove isolate mantengono
5357 slot effettivi, geometria e residenza fisse; prompt fresh/follow circa
33,8k, speculative window 4, suffix draft 0, PCIe fraction 0.28.

| Contributo | Confronto | Teacher rows per braccio | Posizioni valutate | Esito |
|---|---|---:|---:|---|
| Elastica | upstream / port off / VMM stabile / upstream ripetuto | 2560 | 2557 | Tutti i logits bitwise, KL 0, top1 100% |
| Checkpoint tail | upstream / tail / upstream ripetuto | 2560 | 2557 | Tutti i logits bitwise, KL 0, top1 100% |

Corpora completi: codice 512, documento 1024, chat 1024. NLL/PPL identici;
anche i riferimenti ripetuti e le prime righe fresh/follow sono bitwise.
Oracoli completi: 8/8 per elastica e 6/6 per tail, su fixture ripetute;
non sono una misura generale della qualità del modello.

La parità dell'elastica isola l'arena mantenendo disattivati i resize tramite
intervalli molto lunghi. Le modifiche di residenza o chunk in auto possono
modificare gli arrotondamenti: il comportamento dinamico è verificato a parte.
Il gate completo usa la revisione V1 conservata. La versione finale aggiunge
parsing/help, esclusione dei tier non supportati e attesa aggiuntiva prima del
prestito solo quando l'elastica è attiva. Il corpo numerico resta verificato
identico salvo questa guardia, e il binario finale passa fresh/follow più
64 teacher rows bitwise contro V1. Non attribuire il gate completo direttamente
a un eseguibile diverso senza questa distinzione di provenienza.

Elastica finale: CTest **3/3**, inclusi **35 controlli CUDA VMM** su crescita,
shrink/regrowth, indirizzi/offset stabili, byte preservati, nuovi slot azzerati,
richieste invalide e riapertura fissa; **42 casi CLI** passati. La mappatura
massima del test è 6 MiB (l'etichetta iniziale 8 MiB è corretta nella revisione
finale). Non è una prova del rollback per OOM parziale del driver.

## Misura checkpoint tail

Tre coppie intercalate A1/B1, B2/A2, A3/B3, binari shipping, tutte le 12 risposte
complete corrette. Chunk 6144, intervallo checkpoint 16384, prefisso condiviso
32769 token: riuso **18432 → 30720**.

| Tempo al primo token | Mediana upstream | Mediana tail | Differenza |
|---|---:|---:|---:|
| Prompt fresco | 34,178 s | 34,497 s | +0,93% |
| Richiesta ramificata | 17,047 s | 4,470 s | −73,78% |

Spread dei riferimenti: 0,90% fresh e 1,91% follow. È una misura di questa
ramificazione da 33,8k, non un incremento universale né una nuova SOTA t/s.

## Prova combinata e conversazione profonda

Elastica auto + tail, capacità KV262144, prompt a 20k, 131072 e 250000:
**9/9 risposte di richiamo corrette**, primi logits finiti, crescita e shrink
reali della cache e relayout a chunk8192 osservati. Nessun carico artificiale.
Startup: 6432 slot, core3190/tail3242; finestra effettiva6, MTPmax4/lookup3,
PCIe fraction0.36. Queste impostazioni non equivalgono alle prove isolate.
La riserva500MiB è un obiettivo della policy, non una garanzia Windows.

Nel primo tentativo operativo i due prompt guide a131k/250k omettevano la
risposta assistant completa e il delimitatore di turno: uscite48token stop,
**non** prove long-decode. Il risultato è conservato in `operational-r1`.
La successiva sequenza `dialogue-r1` include le risposte assistant chiuse,
istruzioni lunghe rinforzate e un marcatore utente nuovo prima/dopo il decode:
**1024token/length a entrambe le profondità e 6/6 oracoli completi**,
inclusi i quattro distinti marcatori. Non è dimostrato che il delimitatore,
da solo, spieghi il risultato precedente.

Il binario combinato precede soltanto le ultime guardie peer/default dell'elastica;
il percorso single-GPU con flag attivo provato resta equivalente. AMD,
multi-GPU e 2080 Ti stock11GB non sono validati. I test non sostituiscono una
attestazione generale di qualità o di ogni possibile ridimensionamento.

## Evidenze e stato operativo

[Patch, script, log, fixture e manifest](corse_2080ti/20261003_elastica_checkpoint_tail/README.md).
I dump grezzi multi-GB restano privati; SHA e lunghezze sono nei risultati.
Tutti i fallimenti precedenti restano nei rispettivi report, senza essere
riclassificati come pass. SHA del Daily, server, configurazione, profilo e
lanciatore sono verificati invariati; motori di test chiusi.
Non installare la build upstream pura come SOTA: non contiene tutte le altre
patch SM75 del Daily. La promozione operativa va fatta integrando e verificando
il contributo nel suo ramo reale.
