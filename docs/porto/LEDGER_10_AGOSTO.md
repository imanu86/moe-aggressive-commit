# Ledger del 10 agosto

Giornata in due tempi. Di mattina i guadagni grossi (fusione HC, prefill, KV);
di sera **tre fronti chiusi e due strumenti che mentivano**. Il risultato piu'
importante della sera non e' un t/s: e' che due cose che credevamo misurate non
lo erano.

## Il tabellone della sera

| braccio | t/s | ms/ciclo | p1 | colpi | VRAM libera | SHA |
|---|---:|---:|---:|---:|---:|---|
| k339_a (riferimento) | **12,59** | 147,7 | 0,86470 | 54,0% | 1.109 | 33D76723EB8D |
| k448 | 11,55 | 156,7 | 0,80845 | 60,5% | 362 | 9F1EF2F280D9 |
| k480 | 11,48 | 159,4 | 0,83180 | 63,8% | 282 | 4C7070E4D946 |
| k339_b (deriva) | 12,29 | 151,3 | 0,86470 | 54,4% | 1.189 | 33D76723EB8D |

Riferimento storico dello stesso braccio, stesso SHA: **13,25 t/s, 140,4 ms**.

---

## 1. LA CAPIENZA NON PAGA -- e i colpi non sono la valuta

Da settimane il ragionamento era: piu' slot -> piu' colpi -> meno trasporto ->
piu' t/s. I primi due anelli reggono. **Il terzo no.**

```
  slot    colpi      t/s
   339    54,0%    12,59
   448    60,5%    11,55      +6,5 punti di colpi,  -8,3% di velocita'
   480    63,8%    11,48      +9,8 punti di colpi,  -8,8%
```

Due cause sommate, entrambe misurate:

**(a) Il ciclo cresce col numero di slot.** Fra i bracci la pendenza e'
~0,07-0,08 ms per slot per ciclo (109 slot -> +7...9 ms; altri 32 -> +2,7).
E' la scansione sequenziale dello sfratto: a 339 slot quel termine vale
**24-28 ms su ~150, un sesto del ciclo speso a decidere quale slot buttare**.

**(b) Il p1 si sposta, ma NON monotonamente.** 0,86470 -> 0,80845 -> 0,83180.
Avevo previsto che a 480 scendesse sotto 0,808: previsione **falsificata**.
Cambiare la residenza cambia chi calcola su CPU e chi su GPU, i due arrotondano
diverso, il bersaglio produce stati leggermente diversi e DSpark -- che quegli
stati li legge -- va meno d'accordo con lui. Ma e' un effetto **erratico**, non
una funzione della capienza: non si puo' ne' prevedere ne' ottimizzare.

Terza volta oggi che inciampiamo nella stessa retroazione (AcceptMoE: rifiuti
raddoppiati; rollback KV: -1,5% di p1). Ora ha tre conferme e va trattata come
legge: **qualunque leva sposti il confine CPU/GPU paga un pedaggio sulla bozza,
e il pedaggio non e' preventivabile.**

## 2. LA DERIVA E' DEL 2,4%, non dello 0,8%

`k339_a` 12,59 contro `k339_b` 12,29: stessa configurazione, **stesso SHA,
stesso p1 alla quinta cifra**, 2,4% di scarto. Tutti i verdetti di oggi vanno
riletti con quella soglia: la differenza 448 vs 480 (0,6%) e' rumore e non
esiste. Le cadute a 448/480 restano vere perche' sono tre volte la deriva.

## 3. IL CANCELLO BIT-ESATTO HA PESCATO UN DIFETTO IN GIORNATA

Il commit `mmqx` (tile del cammino esperti configurabile) aveva evitato
correttamente la trappola documentata nell'audit 56 par. 7.1 -- non toccare
`ncols_max` -- e ne aveva aperta un'altra a due righe di distanza:

```c
int mmq_x_best = args.ids_dst ? get_mmq_x_ids_host() : 0;
int ntiles_x_best = INT_MAX;
for (int mmq_x = 8; mmq_x_best == 0 && mmq_x <= mmq_x_max && ...; mmq_x += 8)
```

`ntiles_x_best` parte da `INT_MAX`, quindi il primo candidato ammissibile
assegna **sempre** `mmq_x_best`: la guardia fa uscire il ciclo subito dopo.
La scelta di difetto passa da «il tile con meno riquadri» a «il primo tile che
ci sta» -- e siccome a leva spenta `mmq_x_best` parte da 0 anche per i
`mul_mat_q` **densi**, cambiava la selezione dell'intero modello.

Misurato a leva spenta: 13,25 -> 12,59 t/s e SHA `33D76723EB8D` ->
`2CE6DA51313F`. Nessuna lettura del diff l'aveva vista, mia compresa: l'ha
vista il cancello. Corretto in `37da31659` (il valore forzato non entra nella
condizione: e' invariante di ciclo, si applica dopo).

## 4. L'INVIO HTTP CORROMPEVA I PROMPT IN SILENZIO

Il prefill a 96k e' fallito in cinque secondi con
`parse error at column 285444`. Quella colonna e' esattamente la prima `e`
accentata del prompt: la diagnosi si e' validata sull'aritmetica dell'offset.

PowerShell 5.1 manda il corpo in **ISO-8859-1** se il `ContentType` non dichiara
il charset. Misurato sul filo con un `HttpListener` locale, non dedotto:

```
  ▁ ∞ ≈ → α π   ->  '?'
  ｜ (U+FF5C)   ->  '|'        <-- il peggiore
  —  (U+2014)   ->  '-'
  è é È ·       ->  byte alto  ->  500 ill-formed UTF-8
```

Non e' «un carattere perso»: e' una **traslitterazione al meglio** che produce
testo plausibile e sbagliato. `<｜User｜>` -- il marcatore del template
DeepSeek -- viaggiava come `<|User|>`: si legge bene e si tokenizza in un altro
modo. `ctx_08k_prompt.txt` ne ha **312**, e non essendo mai fallito non l'aveva
mai detto nessuno: ogni corsa che l'ha usato ha misurato un testo diverso da
quello che credevamo, **compreso il riferimento di prefill a 113,5 t/s**.

Cura: array di byte UTF-8 **e** `charset=utf-8`. Entrambe verificate sul filo.

## 5. LO SFRATTO PARALLELO SI IMPICCA NEL WARMUP

`LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1`: il server non e' mai salito in 15 minuti,
ultima riga del log l'avvio del warmup subito dopo l'inizializzazione della
cache. Non un crash: un blocco.

Revisione statica fatta, e il protocollo **regge sulla carta**: barriere
bilanciate su ogni cammino, nessuna barriera vagante fuori dalle funzioni
cooperative, nessuna uscita anticipata nel cammino del thread 0, congedo
incondizionato, 256 fili leciti, 3 KB di memoria condivisa. L'unico buco
individuato: **`coop.comando` non e' inizializzato** prima che i lavoranti lo
leggano alla prima barriera.

Vale la pena sistemarlo: e' il candidato piu' grosso rimasto sul tavolo, perche'
attacca i 24-28 ms del punto 1a.

## 5bis. STAVAMO OTTIMIZZANDO IL REGIME SBAGLIATO

Il riferimento di tutta la campagna e' `jprompt.txt`: ~60 token di prompt piu'
1.200 generati, cioe' una coda che va da 60 a 1.260, **profondita' media ~660**.
Nessuno aveva mai misurato un turno vero.

Sullo stesso binario, stessa configurazione, prompt da 5.987 token (coda da
5.987 a 7.187, media ~6.590):

```
  profondita' media ~660      12,59 t/s     p1 0,86470     colpi 54,0%
  profondita' media ~6.590    10,51 t/s     p1 0,71689     colpi 46,9%
```

**−16,5% e quindici punti di p1**, e non e' una regressione: e' il regime in cui
abbiamo sempre girato senza guardarlo. Tutte le classifiche di leve degli ultimi
giorni sono state stilate a profondita' ~660.

Conseguenza di metodo: il `t/s` finale di llama.cpp e' **cumulativo su tutto
l'intervallo di profondita'**, quindi mescola la parte poco profonda con quella
profonda e appiattisce proprio la pendenza che interessa. Lo strumento giusto e'
`print_timing` (`n_decoded` + `tg_3s`): profondita' della coda e velocita'
istantanea in quel punto. Una generazione lunga da' tutta la curva; i punti
storici diventano due righe di quella curva.

## 5ter. ub 1024 E' GRATIS, e la VRAM a fasi risolve un problema che non abbiamo piu'

Quattro bracci sullo stesso prompt da 5.987 token, con la deriva in coda:

| braccio | prefill | decode | ms/ciclo | p1 | VRAM dopo carico | SHA |
|---|---:|---:|---:|---:|---:|---|
| ub 64 | 22,16 | 10,51 | 163,7 | 0,71689 | 1.260 | CDC50E63C3B0 |
| ub 1024 | **101,00** | 10,51 | 167,5 | 0,76154 | 710 | 4F77E5909450 |
| ub 1024 + fasi=1 | 100,65 | 10,46 | 168,3 | 0,76154 | **1.216** | 4F77E5909450 |
| ub 64 (deriva) | 22,48 | 10,73 | 160,3 | 0,71689 | 1.269 | CDC50E63C3B0 |

**(a) `ub 1024` vale prefill x4,5 e costa ZERO in decode.** I quattro decode
stanno fra 10,46 e 10,73, dentro la deriva del 2,4%. Il buffer di calcolo passa
da 34 a 541 MiB -- 750 MiB di VRAM in meno -- e il decode non se ne accorge.
Giravamo a `ub 64` per paura che il buffer rubasse spazio alla cache: il buffer
non costa, **e** la cache piu' grande non paga (§1). Le due paure si annullano.
`ub 1024` va adottato come difetto.

**(b) `LLAMA_VRAM_A_FASI=1` fa esattamente quello che promette**: restituisce
506 MiB dopo il carico (710 -> 1.216) con **SHA identico**, quindi e'
computazionalmente inerte come deve essere. Non serve piu' per la cache; serve
per far entrare **contesti piu' lunghi**, dove il buffer di calcolo cresce.

**(c) `ub` sposta il p1 di 4,5 punti** (0,71689 -> 0,76154) e sposta il ciclo di
altrettanto in senso opposto: le due cose si annullano esattamente sul t/s.
Quarto caso in giornata in cui il p1 si muove perche' e' cambiato **come** il
bersaglio ha costruito il suo stato, non quanto lavoro ha fatto.

## 5quater. LA CURVA A PROFONDITA' VERA — mai vista prima

Prompt da 73.200 caratteri, `-c 32000`, `ub 1024`, 339 slot, VRAM libera 1.211.

```
  prefill      75,62 t/s su 23.693 token   [5,2 min]
  salvataggio  0,2 s  ->  233,5 MiB su disco
```

Due cose gia' qui. **Il rapporto caratteri/token e' 3,09**, non 3,66 come
stimavo (73.200 / 23.693): tutte le stime di lunghezza dei prompt vanno rifatte
con questo. E **il prefill degrada col contesto**: 101,00 t/s a 6k token,
**75,62 a 23,7k**, stesso `ub`, stesso binario.

E poi la curva, letta da `print_timing` (`tg_3s`, velocita' istantanea):

```
  profondita' coda      t/s ISTANTANEO
     23.793               10,37
     24.018               10,16
     24.529                9,56
     25.008                9,14
     25.500                8,71
```

**−16% in 1.700 token di crescita della coda**, cioe' circa un t/s ogni mille
token a questa profondita'. Il t/s cumulativo della stessa corsa era 9,33: la
media da sola avrebbe nascosto sia il punto di partenza sia la pendenza.

Il quadro completo delle profondita' misurate oggi, stesso binario:

```
  coda media ~660      12,59 t/s     p1 0,86470
  coda media ~6.590    10,51         p1 0,71689
  coda 23.793          10,37         (p1 cumulativo 0,78323)
  coda 25.500           8,71
```

Non e' ancora chiaro **quanto** della caduta sia costo dell'attenzione e quanto
sia il p1 che si degrada: la corsa da' il p1 solo cumulativo. Serve leggerlo a
finestra come il t/s.

## 5quinquies. DUE TRAPPOLE DEL BANCO, costate due corse

**(a) PowerShell SROTOLA gli array restituiti da una funzione.** Una funzione
che ritorna `[Text.Encoding]::UTF8.GetBytes(...)` restituisce 73.948 oggetti
separati, e `-Body` li manda come la stringa `"123 34 109 ..."`. Il server
risponde `500 parse error at column 6: unexpected number literal`, che sembra un
problema di codifica e non lo e'. Cura: `return ,$bytes` -- la virgola
impacchetta. Negli script che assegnano a una variabile il difetto non si vede.

**(b) I nomi di variabile in PowerShell NON distinguono maiuscole e minuscole.**
`$KV` (il percorso di `--slot-save-path`) e `$kv` (la profondita' della coda nel
ciclo che stampa la curva) sono **la stessa variabile**. Il rilancio del server
e' fallito con `--slot-save-path: not a directory: 25690`, dove 25690 era
l'ultima profondita' stampata.

Entrambe hanno prodotto errori che puntavano altrove. Fa parte della stessa
famiglia di [[strumenti-che-mentono-in-silenzio]].

## 5sexies. `mmq_x`: IL RIEMPITIVO NON ERA IL COLLO

Cancello bit-esatto **PASSATO**: SHA `AF3766AF0A87` identico in tutti e cinque
i bracci. La leva e' corretta, quindi i numeri valgono.

```
  mmq_x   prefill (t/s)   contro il difetto
   128       101,73             --          (il secondo braccio a 128: 101,82)
    32        63,70          -37,4%
    48       100,33           -1,4%
    64       104,25           +2,4%
```

Deriva fra i due bracci a 128: **0,1%** -- macchina ferma, quindi il +2,4% di
`mmq_x=64` e' ventiquattro volte il rumore ed e' reale.

**L'ipotesi dell'audit 56 e' falsificata.** Il ragionamento era: a `ub` alto un
esperto serve ~12 token su un tile da 128 colonne, quindi il 91% e' riempitivo,
quindi tile piu' piccoli vanno piu' veloci. E' il contrario: `mmq_x=32` perde il
37%. **Frammentare i lanci costa piu' di quanto il riempitivo faccia sprecare.**

Le due controipotesi scritte prima della misura avevano ragione entrambe:

- Codex, `audit/57-mmqx.md`: «`32` puo' perdere contro `48` se il costo dei tile
  vuoti o la coda degli esperti grassi domina il risparmio medio».
- Fable, dal repo di DwarfStar: «la decomposizione multi-taglia dei tail HA
  PERSO contro un lancio guarded» (`reslice6: 64% of down time in tail
  launches`).

Attesa dichiarata da Codex prima del codice: ~123 t/s per `mmq_x=32` (+8,4%).
Misurato: 63,70. **Falsificata di 60 punti.**

Il decode non si muove in nessun braccio (10,44-10,59): a batch 2 il cammino
`MUL_MAT_ID` non passa da MMQ, come atteso.

## 6. COSE CHE ESISTEVANO E NON STAVAMO USANDO

- **`LLAMA_VRAM_A_FASI`** (+ `_UB`, `_MIN`): ubatch grande in prefill e piccolo
  in decode, coi buffer grossi liberati nel passaggio
  (`llama-context.cpp:2187` e `:867`). **Spenta in ogni braccio di oggi.**
  Diventa interessante proprio ora: i ~750 MiB che il buffer di prefill si
  mangia valgono 111 slot di cache, e i 111 slot il punto 1 li ha appena
  dichiarati dannosi. Il baratto che ieri era caro oggi e' gratis.
- **La telemetria.** Fino a stasera non campionavamo clock, watt, util,
  RAM e VRAM durante le corse: «la GPU aspetta» era dedotto da contatori
  nostri, mai osservato. Ora c'e' `telemetria.ps1`, un campione ogni 5 s.

## 7. IL CANTIERE D2R (Fable, ramo `fix/d2r`, `14bce99d6`)

Premessa del mandato **capovolta dall'agente**: la *fusione* di D2R da noi vale
~zero (risparmia banda VRAM e lanci gia' nascosti sotto il PCIe) e riassocia,
quindi niente bit-esatto. Il pezzo che vale e' il **doppio buffer `cp.async`**,
ri-derivato sul layout AoS del GGUF senza repack: la stage grezza in memoria
condivisa alimenta il `load_tiles` originale, quindi **bit-esatto per
costruzione anche a leva accesa**. Leva `LLAMA_MMQ_IDS_CP_RING`, spenta di
difetto. Attesa registrata prima del codice: prefill 113,5 -> 126-140 t/s,
pavimento di falsificazione +8%. Rischio dichiarato: `LDGSTS` su memoria
mappata dall'host non ha precedenti nel repo, serve uno smoke test da 128 token.

Dato dal loro albero, utile a `mmqx`: **la decomposizione in tile piu' piccoli
ha PERSO** contro un lancio unico guardato.

## 8. Aperto, in ordine di valore

1. **Sfratto parallelo**: sistemare il blocco. Attacca 24-28 ms su 150.
2. **`VRAM_A_FASI` + ub 1024**: prefill veloce senza pagare il decode. In corso.
3. **K piu' basso a capienza alta** (idea dell'utente): se la GPU ha piu'
   esperti residenti, il ramo CPU e' un residuo. K frazionario funziona **solo
   da oggi** (`979efd899`: il contesto leggeva K con `atoi`, il costruttore del
   grafo con `atof`).
4. **La banda 102k-110k**: mai misurata. Richiede contesto oltre 110k e non
   sappiamo se carica. Il muro atteso e' la **memoria GPU condivisa**, che
   Windows limita a ~76,7 GB e di cui i nostri esperti mappati occupano gia'
   74,3.
5. **`mmqx`**: spazzata 32/48/64 mai fatta, il difetto ha mangiato la finestra.
6. **Perche' il riferimento e' passato da 13,25 a 12,5-12,6** a SHA identico.
