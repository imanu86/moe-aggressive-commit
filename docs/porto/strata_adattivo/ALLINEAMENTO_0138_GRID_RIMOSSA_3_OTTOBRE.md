# Daily0.1.38: grid rimossa, tail ed elastica, top-k largo — 3 ottobre2026

Il Daily operativo e il fork `main` sono allineati a upstream0.1.38,
`99f3dbd0b21d1401b3769e0c0d963913607f380b`. La storia upstream è raggiungibile;
i sorgenti completi provati sono importati con manifest distinto. Commit operativo:
`fc9a767b15c38cc21bc3c2aac315f63b12dd0e4c`. La grid originale è assente da header, implementazione
e chiamante; i FAIL precedenti rimangono conservati. Il checkpoint tail salva un
confine di chunk già esistente vicino alla fine, senza tagliare diversamente il prefill.

Conservati elastica automatica a core fisso/tail VMM, SM75 HC/GDN FP16, dequant
vettoriale e budget dei buffer propri; seriale per la quantizzazione intermedia.
Il nostro active-bound top-k512 è già upstream. Integrata la PR603 di asp345/Opus5.5
al commit6ba96984ac8a5f019edd84d7a83c278e6a1d363d, dopo verifica sulla nostra scheda.
Tail: Codex/PR614; elastica originale: Claude Opus, port/guardie Codex. Non viene
pubblicata una seconda PRelastica sovrapposta a37/378/563 e al piano533.

## Misure con impostazioni automatiche del Daily

Windows, RTX2080Ti **modificata22GB**, Ryzen5800X/AVX2,96GB RAM, CUDA12.6,
IQ3_XXS, KV262144/int8, residenti32768, riserva1393MiB, cache e chunk automatici,
elastica attiva, tail attivo, checkpoint16384. Nessuna pressione artificiale.
La CLI conserva `--spec 4`; con `auto` upstream038 dichiara a runtime spec6,
MTPmax4, lookup3 e PCIe0.36. Nel test controllato sotto i valori effettivi sono
spec4, MTPmax0/lookup0, PCIe0.28: sono due profili distinti.

| Input fresh reale | Prefill fresh t/s | Decode lungo t/s | Input del decode lungo | Output lungo |
|---|---:|---:|---:|---:|
| 131072 | 1027.01 | 36.913 | 131244 | 1024 |
| 250000 | 833.50 | 39.065 | 250172 | 1024 |

Sono singoli campioni del nuovo Daily, con cache/MTP e attività desktop variabili:
non costituiscono un guadagno causale su0136 o una curva completa KV/t/s.
Conversazione: recupero tre record a profondità diverse, vero turno assistant
chiuso, marcatore nuovo, guida1024token, marcatore distinto dopo il decode.
Entrambe le profondità: logits finiti,1024token/finish length, sei oracoli corretti.
Cache iniziale6339slot; crescita reale durante il test documentata nei log.

## PR603 isolata, profilo fisso250k

Stessa base038, stesso tail,5357slot, chunk8192, spec4 e intervalli reali lunghi
che disabilitano il resize nel confronto. A1/B/A2: prefill fresh
**701.49/832.03/699.49 t/s**. Guadagno rispetto alla media A:
**+18.78%**; spread A/A **0.29%**. Tempi TTFT/decode, ID e risorse in
`corse_2080ti/20261003_allineamento038_grid_rimossa/speed-summary.json`.
Primi logits bitwise per tutte le quattro richieste e ripetizione A; tutte le
risposte generate identiche;
nove oracoli e tre decode1024passano. Un solo A/B/A, non uno studio statistico esteso.

Microbenchmark con identico driver e vere librerie baseline SM75, nessun override
`STRATA_TOPK_OLD`:256query a262144celle, mediana18.166→1.056ms, circa17.2x.
A131072celle la selezione prefill è sostanzialmente invariata. Le misure decode
sono più variabili; non trasferire il17.2x al motore completo.

## Correttezza e installazione

Old036/new038/old036, chunk2048 e5357slot:2560teacher rows/2557posizioni per
braccio sui corpora code/doc/chat, logits bitwise, KL0, top-1 agreement100%,
NLL/PPL invariati; sei recall completi corretti. Gate locale di regressione,
non una certificazione generale del modello. Caso0136 con grid e chunk2048
divisibile per16384 ha la stessa geometria; i vecchi test grid falliti non cambiano.
Sei CTest,18casi top-k (punteggi continui, livelli/tie, tutti uguali; prompt/decode
fino524288celle),64casi quantizzazione CPU bitwise con GGUF reale,118test server.

Eseguibile shipping `014d7773886a45b10072cf362cf01082ec048a9063b318e3cd1ff024b3beaf71`. I binari QA aggiungono solo
il readout comune; quello installato e pubblicato non contiene l'hook di test.
Cartella: `D:\ds4_work\strata\Strata\build-0138-daily`; server congelato completo della
stessa build. Configurazione e BAT desktop puntano lì, porta8100/127.0.0.1.
Health e nuovo JSON `DAILY-038-READY` passati sul vero shipping dopo installazione;
processi propri chiusi.48file non tracciati preservati; build0136 mantenuta.

Ripristino: `D:\ds4_work\strata\ripristini\20261003_131031_allineamento038`. Per tornare al vecchio motore basta
ripristinare config e BAT dalla copia; la build0136con il suo server è intatta.
Non serve resettare la storia Git. Bundle e file locali sono salvati nel ripristino.

[Release verificata](https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.38-sm75-20261003-r1) · [PRtail614](https://github.com/Niko1221/Strata/pull/614)
· [PRwide603](https://github.com/Niko1221/Strata/pull/603).
Nessun workflow aggiunto; nessuna misura stock11GB/multiGPU o banda DRAM fisica.
