# Diagnosi checkpoint e configurazione senza tagli aggiuntivi — 3 ottobre 2026

**Il ripristino del checkpoint non introduce differenze nel caso provato.**
Il gate FAIL della patch originale con intervallo16384 rimane FAIL.
La cache elastica degli esperti era disattivata:5357 slot fissi in tutte le prove.

## Lettura da zero contro riuso

Quattro processi separati: upstream0.1.38 A e patch checkpoint-grid B, chunk1536
e6144. Stessi binari QA verificati del report precedente, SHA controllati prima
di ogni avvio. Stesso warm-up estraneo al prefisso; prompt follow33822 token
letto direttamente, senza precedente fresh, con reused0. Prompt-cache6 e
intervallo16384 conservati, KV262144/int8/resident32768, spec4, adattamento0.
Il confronto usa i logits completi della precedente QA valida quality-tests-r3:
primo output completo e64 posizioni teacher-forced dopo la risposta.
Le righe teacher riusano lo stato creato dalla lettura iniziale da zero;
non sono64 letture indipendenti da zero.

In tutti e quattro i confronti: **bitwise identico, KL0, NLL/PPL identiche,
top1 100%**. Quattro risposte complete corrette secondo l'oracolo dei tre codici.
Anche leggendo da zero, il confronto A/B riproduce le stesse divergenze del
precedente confronto con riuso: KL p990.032133 (1536) e0.088491 (6144).
Quindi la differenza nasce nel percorso prefill modificato prima del riuso;
non è evidenza di corruzione del checkpoint in questo workload.
Non è ancora isolato il singolo kernel o dimostrato che siano soli arrotondamenti.

## Configurazione conservativa: confini naturali

Provati A e B con `--prefill 6144 --prompt-cache-every 6144`, invece di16384.
Il salvataggio cade sul confine del blocco: non richiede tagli aggiuntivi.
Questa configurazione funziona anche sull'upstream senza la nostra patch.
Fresh33823/follow33822, stesso prefisso comune32769, stessi prompt e oracoli.
Il follow riusa30720 token, contro18432 del riferimento6144/intervallo16384,
e32768 della patch originale. Rimangono3102 token da leggere.

**A/B bitwise identici** sul primo output fresh, primo output follow e64
posizioni teacher-forced. Anche entrambi contro la baseline originale6144
con intervallo16384 sono bitwise identici, KL0/top1 100% sulle posizioni misurate.
Tutte le quattro risposte complete corrette.

Tempi di lettura prompt riportati dal motore, un solo campione per eseguibile,
con strumentazione QA; non TTFT misurato dal client:

| Eseguibile | Fresh lettura s | Follow lettura s | Follow riusato |
|---|---:|---:|---:|
| Upstream A | 34.848 | 4.439 | 30720 |
| Candidato B | 34.983 | 4.432 | 30720 |

Questi tempi sono diagnostici, non tre coppie, non una nuova SOTA o misura
di speedup del kernel. La soluzione verificata qui è una diversa frequenza dei
checkpoint che conserva la geometria di riferimento. Il costo di più copie
checkpoint e il comportamento a131k/250k vanno ancora misurati, così come la
combinazione con la cache elastica e il Daily0.1.36.

## Stato e limiti

Nessuna soglia numerica allargata, nessuna PR nuova o promozione Daily.
Nessuna build o modifica di kernel in questa diagnosi; gli eseguibili QA sono
gli stessi già validati. Una sola quantizzazione IQ3_XXS e un workload retrieval:
questi risultati non certificano la qualità generale né tutti i casi di ripristino.
Nessuna pressione artificiale o interazione con altre chat.
Motori propri chiusi; exe, server, JSON e launcher Daily invariati per SHA.
RAM disponibile finale 67.72GiB.

Evidenze e runner: [manifest](corse_2080ti/20261003_checkpoint_diagnosis/manifest.json).
Logits completi e binari conservati solo localmente.

Il primo tentativo di staging fu negato su `.git/index.lock`; l'accesso completo
è stato successivamente ripristinato. Il commit di pubblicazione sul branch
research autorizzato identifica le evidenze online; il blocco iniziale è storico.
