# 51 - COPIA DI RITORNO ASINCRONA DEL RAMO CPU

Data: 10 agosto 2026. Worktree `D:\wt-join`, ramo `fix/join`.

L'audit 44 non era presente in questo worktree. Ho letto integralmente la copia
indicata dallo stesso repository di ricerca in
`D:\llama-overlap\audit\44-overlap-macchina.md`, in particolare i paragrafi 3
e 9, prima di leggere e modificare il percorso del join.

## 1. Atteso scritto prima della patch

Dato di partenza del mandato:

    ciclo attuale                  140,6 ms
    attesa fissa osservata          45,0 ms
    strati con lane CPU                43
    costo fisso per join            1,047 ms

Non divido i 45 ms in quattro quote uguali. La H2D fisica e' di circa 32 KiB
per strato e il join host a K=2 e' previsto quasi interamente coperto. La mia
ipotesi e' quindi che i due punti di sincronizzazione host/driver rimossi dalla
patch pesino piu' della meta' del totale fisso.

Previsione centrale, fissata prima di scrivere il codice:

    recupero                       45,0 x 0,65 = 29,25 ms/ciclo
    ciclo atteso                  140,6 - 29,25 = 111,35 ms
    accelerazione                 140,6 / 111,35 = 1,263
    t/s attesi da 13,19-13,26                   16,65-16,74

Fascia di falsificazione: recupero di 20-38 ms, quindi ciclo di 120,6-102,6 ms
e circa 15,38-18,17 t/s a lavoro utile per ciclo invariato. Un recupero sotto
10 ms smentisce l'attribuzione dei 45 ms ai drain. Il numero misurato non deve
essere usato per riscrivere questa previsione.

## 2. Modifica

La leva nuova e' `LLAMA_OVERLAP_JOIN_ASYNC`. E' spenta per difetto e viene
considerata solo quando anche `LLAMA_OVERLAP_ASYNC` ha attivato il worker.

Al join lo scheduler conserva l'id dello split CPU appena unito. Per ogni
input della coda verifica che la sorgente sia davvero un nodo di quello split,
che il backend sorgente sia CPU, che il buffer sia host e che il backend
destinatario esponga `set_tensor_async`.

Solo in quel caso il percorso:

    synchronize destinazione per il riuso
    tentativo cpy_tensor_async
    synchronize sorgente
    secondo synchronize destinazione
    tensor_copy con H2D sincrona su cudaStreamPerThread

diventa:

    tensor_set_async sul backend della coda

Nel backend CUDA `tensor_set_async` accoda `cudaMemcpyAsync` sullo stream di
calcolo del backend. La chiamata avviene dopo il join del worker, dietro il
ramo GPU gia' accodato e prima del lancio della coda che consuma il risultato.
Lo stesso ordine di stream protegge il riuso del destinatario senza un drain.

Il percorso generico degli altri confini non cambia. Non e' stata estesa
globalmente `cpy_tensor_async` alle sorgenti CPU.

## 3. Correttezza e cancelli

### Cancello SHA

Con la leva spenta il nuovo predicato e' sempre falso e si percorre il codice
precedente. Questo e' il controllo d'identita' del binario.

Con la leva accesa, il join acquisisce lo stato `FATTO` pubblicato dal worker:
la scrittura CPU e' terminata prima che lo scheduler accodi la H2D. Sul lato
GPU, stream unico significa:

    1b -> H2D risultato CPU -> concat e coda

Il riferimento obbligatorio resta `33D76723EB8D`. Qualunque SHA diverso e' un
difetto di correttezza, non un risultato prestazionale.

### Cancello dell'attesa

`GGML_SCHED_PROFILO=1` esponeva gia' `us_sync/grafo`; la patch continua a
usare quel numero come cancello e aggiunge `copie join-async/grafo` alla riga
del worker. A K=2 l'atteso e':

    lavori worker/grafo            43, invariato
    copie join-async/grafo         43 circa
    us_sync/grafo                  calo di almeno l'80% della quota overlap
    join sched/grafo               invariato entro rumore

Se le copie contate sono circa 43 ma `us_sync` non crolla, restano drain in un
altro input o confine. Se le copie sono zero, il profilo degli split non
corrisponde alla macchina descritta dall'audit 44.

### Cancello di ingaggio

La matrice minima e' sullo stesso binario e con il resto dell'ambiente fisso:

    LLAMA_OVERLAP_JOIN_ASYNC non definita
    LLAMA_OVERLAP_JOIN_ASYNC=0
    LLAMA_OVERLAP_JOIN_ASYNC=1

I primi due bracci devono coincidere. Il terzo deve mantenere SHA e numero di
lavori, contare le copie asincrone e ridurre `us_sync`.

## 4. Verifiche fatte qui

- Nessuna compilazione e nessun server avviato, come richiesto.
- `git diff --check` pulito dopo la modifica.
- Scansione byte diretta prima della modifica: `ggml-backend.cpp` e
  `ggml-alloc.c` erano gia' LF puri e identici ai rispettivi blob dell'indice.
- La scansione byte diretta finale conferma ancora zero CR in entrambi i file.

Le misure di SHA, `us_sync`, ciclo e t/s sono lasciate alla macchina di misura.

## 5. Lasciato indietro

- Il join resta host-side; non e' un rendezvous device-side.
- Non e' stato dimezzato il numero dei join con K frazionario e non e' stato
  corretto il lettore `atoi` del pin.
- Non sono stati modificati i percorsi di copia generici o gli altri backend.
- La previsione prestazionale assume che il buffer host CUDA non sia caduto
  nel ripiego pageable. Il ripiego resta corretto, ma puo' ridurre o annullare
  il vantaggio asincrono.
- La misura deve ancora stabilire quanta parte dei 45 ms fosse davvero nei
  drain e quanta nella sottomissione WDDM rimasta.
