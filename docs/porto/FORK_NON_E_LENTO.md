il fork NON e' lento: era il compute buffer che sfondava la VRAM

SMENTITO il commit 16db65e, che archiviava il fork dspark-dsv4 come "-21%" e
lo mandava in magazzino insieme a DSpark. Quella decisione poggiava su un
confronto fra run di momenti diversi, l'errore che questa sessione ha fatto
nove volte.

Misurato adesso, stessa macchina, stesso momento:

  fork con -ub 64        regime 7,21
  ufficiale (stanotte)   regime 7,18  e  7,37
  fork con -ub 512       regime 3,70

7,21 contro 7,18: indistinguibili.

LA CAUSA, trovata confrontando le allocazioni a verbosita' 10:

                  CUDA0 compute buffer      nodi del grafo
  ufficiale            835,26 MiB                9.553
  fork              12.254,52 MiB               34.054

Il fork costruisce un grafo 3,6 volte piu' grande e gli serve un'area di lavoro
da 12 GB. Con -ngl 99 l'adattamento automatico viene abortito ("n_gpu_layers
already set by user, abort" -- il messaggio era in OGNI log e l'ho sempre
scorso), quindi procede e sborda 9,3 GB in memoria condivisa. Il fork stesso lo
dichiara: "cannot meet free memory target, need to reduce device memory by
9913 MiB".

Con -ub 64 il buffer scende a 1.780 MiB, la condivisa da 9.286 a 204, e la
velocita' torna. Il grafo resta grande (34.054 nodi) ma l'area di lavoro sta
dentro. E -ub tocca il PREFILL, non il decode: in decode si elabora un token
per volta comunque.

CONSEGUENZA: il piano DSpark e' di nuovo in piedi. Il fork e' l'unico che carica
il draft (upstream non implementa il DFlash con backbone DSV4: 342 righe di
differenza nel solo dflash.cpp), e ora sappiamo che non costa niente. Con
l'ammortamento misurato -- il 78% del costo e' per passata -- la speculazione
vale 1,6-2,1x NETTI, non piu' scontati del debito della base.

Trovato perche' l'utente ha insistito che "10 GB in piu' non si spiegano".
Avevo gia' chiuso la questione due volte con spiegazioni sbagliate.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
