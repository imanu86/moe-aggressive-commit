# PIANO OPERATIVO — il gate sul modello che non entra

*Scritto il 5/8 dopo aver letto per intero `reap-loop/docs/INTUITION_REGISTER.md`
(89 righe) e `BOOT_PROBE_DESIGN.md`. Le due letture cambiano l'ordine dei test.*

---

## 0. Quello che il registro dice e che stavamo per ignorare

**La regola procedurale** (registro, 27/7, "terza occorrenza"):

> Prima di ogni NUOVA famiglia di test: grep su questo registro E sul ledger per
> la famiglia gia' vincente.

**La famiglia gia' vincente per la velocita' non e' il trasporto.** Sono due:

1. **tenere il working set DENTRO la memoria veloce** — sul 3060, un working set
   che entra nella cache da' ~25 t/s contro 3; il costo segue la *dimensione*
   della cache, non la residenza;
2. **COMPRIMERE IL VOLUME del working set** — le maschere a dominio davano 4-5
   t/s su DwarfStar con 32 GB di RAM. Non spostavano byte piu' in fretta: ne
   chiedevano di meno.

Il trasporto e' stato falsificato **sette volte** su ds4 (P4a, capacita' cache,
politica cache, pageable, QD4, Q1 residente, prefetch) e **cinque** qui
(zero-copy, banchi, mappatura, IQ1, PCIe). Ogni volta con lo stesso esito: il
numero di miss non cambia, quindi il costo non cambia.

**Il working set vero e' molto piu' piccolo di quanto assumiamo.** Registro,
Addendum 23: *16 token = 34 esperti distinti, p90 111* — non 258. I 258 sono i
*richiami* per token, non gli esperti *distinti* nel tempo.

---

## 1. Cos'e' il WRAP (il "fattorino") e perche' adesso conta

Misurato l'11/7 nel boot-probe, sullo stesso tipo di percorso che abbiamo qui:

| percorso | banda |
|---|---|
| SSD freddo, **un flusso alla volta** (QD1) | **0,314 GiB/s** |
| SSD freddo, **4 thread in parallelo** | **2,10 GiB/s** |
| RAM calda | 16,6 GiB/s |

**6,7× per la sola profondita' di coda.** Il collo dell'SSD non e' la banda ma la
latenza a QD1 — ed e' anche la ragione per cui il RAID e' chiuso nel registro
(§3: *"il collo e' la latenza a QD1, non la banda; la leva e' queue-depth"*).

Su ds4 il WRAP era `DS4_REAP_PREFETCH_THREADS` (default 8, max 16) +
`_PREFETCH_LOCK`, patch `0013-reap-wrap.patch`: **un pool di thread che fa il
page-in bloccando**. Il nostro `reap.cpp` fa la stessa cosa **in un ciclo
seriale** ([reap.cpp:691](D:/llama-dspark/common/reap.cpp#L691)), un esperto alla
volta, dal thread consumatore. E' il ramo a 0,314.

**La regola di attivazione e' gia' scritta** (`BOOT_PROBE_DESIGN.md` §2b):

```
working_set_fits_ram = ram_disponibile / working_set >= 1
deeply_ssd_bound     = (NON entra) AND (banda_SSD_threaded / domanda_decode < 1)
wrap_recommended     = deeply_ssd_bound
```

In tutta la campagna llama.cpp **la prima condizione non e' mai stata vera**: il
modello e' sempre entrato in RAM. Col misto da 112,1 GiB su 95,9 disponibili
diventa vera per la prima volta. Il WRAP non era sbagliato: era fuori regime.

---

## 2. L'aritmetica del modello misto

```
modello            112,1 GiB
RAM disponibile     95,9 GiB   (96 fisici)
fuori               ~16,2 GiB  = 14,5%

non-esperti Q8_0   ~12-15 GiB  (erano 8,20 a IQ2_XXS)
esperti            ~97-100 GiB su 43x256 = 11.008 esperti
per esperto         ~9,1 MiB   (era 6,75)

esperti che entrano  (95,9 - 12 riserva) / 9,1 MiB ~= 8.600  = 78%
esperti mai toccati su un prompt tipo          2.774 = 25,2%
```

**Il margine c'e' ma e' stretto: 78% di posti contro 74,8% di domanda.** Non i
"quasi il doppio" che avevo scritto in `mxfp4_gate.ps1` — quello era il conto sul
14% invece che sul 22% di riserva reale. Il gate deve essere *buono*, non solo
*acceso*.

---

## 3. Le tre cose da fare PRIMA di lanciare (~60 righe, mentre scarica)

### F0 — lo strumento che manca: il tasso di copertura

Il gate oggi riporta un'**intenzione** (quanti esperti ha bloccato, quanti byte)
e non un **esito** (quanta domanda ha coperto). Regola del registro (25/7):

> un buon falsificatore riporta un ESITO (valore ottenuto), non un'INTENZIONE
> (che un ramo di codice sia passato).

Senza, M1 contro M2 da' solo "t/s su o giu'" e non si sa perche'. Con, la
domanda diventa: *degli esperti che il router ha davvero chiesto, quanti erano
bloccati?* — ed e' il numero che decide se la tesi regge.

`reap.cpp` vede gia' ogni id instradato in `registra()`. Serve un contatore
`colpi_su_bloccati / colpi_totali` con `bloccati` promosso da statica locale di
`applica_politica` a stato condiviso.

**Costo: ~20 righe. Nessun rischio. Va fatto per primo.**

### F1 — mmap ACCESO, non `--no-mmap`

`mxfp4_gate.ps1` riga 96 passa `--no-mmap`. **E' sbagliato per un modello che non
entra**: i 16,2 GiB di troppo diventano memoria anonima, quindi il pagefile li
sostiene, quindi **ogni sfratto e' una scrittura e poi una lettura**. Con mmap le
pagine degli esperti sono pulite (file-backed): lo sfratto e' gratis e il page-in
legge dal GGUF. Dimezza l'I/O per costruzione.

`VirtualLock` funziona lo stesso su una vista mappata — e' esattamente quello che
fa `--mlock` di llama.cpp.

**Il numero che chiude la questione:** il pagefile e' **21,5 GB su C:**, cioe'
sullo *stesso disco del modello*. Con `--no-mmap` i 16,2 GiB di troppo ci
finirebbero dentro (a filo) e il traffico di scrittura andrebbe sulla stessa
coda delle letture — non solo il doppio dell'I/O, ma sullo stesso disco.

llama.cpp stampa l'avviso opposto: *"tensor overrides to CPU are used with mmap
enabled — consider using --no-mmap for better performance"*. E' il consiglio
giusto per un modello che ENTRA (una lettura sequenziale grande batte migliaia
di fault). Qui il regime e' rovesciato e l'avviso va contro. Vale la pena
dirlo perche' e' l'unico punto del piano dove ignoro deliberatamente il motore.

Nota: `--no-mmap` resta obbligatorio nel regime *precedente* (modello che entra +
pinning), dove serve a evitare la doppia residenza. E' regime-dipendente, come il
resto.

### F2 — il WRAP: `VirtualLock` in parallelo

Il braccio-tesi vuole bloccare ~77 GiB. Seriale a 0,314 GiB/s sono **4,1
minuti**, dentro il thread consumatore, mentre il modello genera. A 8 thread
sono ~37 secondi.

`LLAMA_REAP_THREADS` (default 8, tetto 16), il ciclo di riga 691 spezzato in
blocchi. ~40 righe.

Gate: il log deve stampare **il tempo di blocco misurato**, non il numero di
esperti. Se non scende di ~6x, il WRAP non ha funzionato e va detto.

---

## 4. La corsa (quando il download finisce)

Quattro bracci, tesi per prime sulla macchina piu' fredda, riferimento per
ultimo con la cache piu' calda:

| braccio | modello | gate | TOPK | cosa risponde |
|---|---|---|---|---|
| **M1** | misto | spento | — | Windows con la sua LRU su 112 GiB |
| **M2** | misto | acceso | 1.200 | il nucleo caldo bloccato, il resto a Windows |
| **M3** | misto | acceso | ~8.000 | **la tesi**: riempi la RAM con quelli GIUSTI |
| **M4** | IQ2_XXS | spento | — | il metro assoluto (7,60 / 15,3 di oggi) |

**M3 e' il braccio nuovo e il piu' importante**: e' l'unico che chiede al gate di
fare quello per cui esiste — decidere *chi* sta nei 96 GB quando il modello ne
vuole 112. M2 con 1.200 blocca 11 GiB su 112 e lascia il 90% del problema a
Windows: e' un mezzo esperimento.

Rischio di M3: `alza_quota` chiede a Windows un working set da 77 GiB. Va
cappato a (RAM totale − 12 GiB) e **va loggato il valore ottenuto**, non quello
chiesto.

### Cosa si misura oltre al t/s

- `colpi_su_bloccati / colpi_totali` (F0) — la copertura;
- `sbloccati_tot` per passata — il churn: se il gate blocca e sblocca gli stessi
  esperti ogni giro, serve l'isteresi (§5);
- `PageReadsPerSec` / `PagesInputPerSec` — se restano a zero come nei run a 96 GB,
  il modello e' di fatto residente e la tesi e' dimostrata;
- il tempo di blocco (F2).

---

## 5. Dopo, e solo se il churn lo chiede: l'isteresi

L'intuizione dell'utente di oggi —

> l'ammissione non va data se non dopo un tot di chiamate o una massa molto alta;
> ma se c'e' un freddo che si sta scaldando abbastanza da voler entrare in ram si
> tira via un esperto che invece si sta raffreddando

— **e' gia' scritta e gia' implementata su ds4**: patch **0033**, commit
`8723e29`, `reap-loop/docs/TIERED_RESIDENCY.md`. Tier per-slot SSD/RAM/VRAM,
knock decaduto, seed dinamico a ~token 12, **isteresi X=3 (SSD→RAM) / X+Y=8
(RAM→VRAM)**, rientro (il knock decade, non si azzera), bit-exact.

Il nostro `applica_politica` ha la meta' che sfratta (il delta: sblocca chi esce
dai primi K) ma **non ha la soglia di ammissione**: un esperto entra nei primi K
per un colpo di fortuna. L'EMA con `LLAMA_REAP_DECADIMENTO` < 1 e' una versione
molle della stessa cosa.

Porta 0033: contatore di bussate per esperto, X=3 minimo per l'ammissione,
decadimento 0,98 per chiamata, rientro. **Ma solo se `sbloccati_tot` mostra che
il churn c'e'** — altrimenti si aggiunge complessita' a un problema che non
esiste, che e' l'errore che il registro documenta piu' spesso.

---

## 6. Cosa NON fare (dal registro §3, chiuse con ragione)

- **RAID SSD / piu' partizioni** — il collo e' QD1, la leva e' la profondita' di
  coda (= F2), non piu' dischi.
- **Pre-caricare in VRAM il profilo intero** — non ci sta; si carica il set
  attivo.
- **Staircase dinamico / cambiare la membership in corsa** — avvelena la cache
  (Legge dell'Ancora). *Distinto* dal ruotare la RESIDENZA, che e' quello che
  facciamo.
- **Mixed-precision come leva di QUALITA'** — ritirata: il soffitto e' la taglia
  del modello, non i bit. La nostra tesi MXFP4 e' sull'asse *costo di
  dequantizzazione*, che e' un altro asse — va detto per non ri-litigare una
  cosa gia' chiusa.
