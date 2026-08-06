# MANDATO — far partire la decodifica Jacobi (lookahead)

*Scritto il 6/8/2026 alle 09:10, a fine di una sessione lunga. Da dare a una
chat nuova: contiene tutto, non serve rileggere altro.*

---

## L'obiettivo, in una riga

`llama-lookahead.exe` è già compilato in `D:\llama-dspark\build\bin\` e **muore
in silenzio dopo due token**. Farlo funzionare, e misurarlo contro il metro.

## Perché questo e non altro

Il decode su questa macchina usa **il 6% della GPU** (842 GFLOPS a batch 1 su una
scheda che ne fa migliaia): non manca banda, manca **lavoro da fare insieme**.
Un token sono 12,98 GFLOP spalmati su 43 passi ordinati.

Il lookahead di Fu et al. è **Jacobi con un pool di n-grammi**: `W=15` posizioni
di finestra, `N=5` n-grammi, `G=15` rami verificati — circa **75 posizioni per
passo invece di 1**. Non usa nessun modello di bozza, e al punto fisso la
sequenza è **identica** a quella della greedy autoregressiva: è esatta per
costruzione, non approssimata.

**Non confonderlo con la speculazione.** Provata e chiusa il 6/8: la bozza genera
in *sequenza* e il bersaglio verifica in blocco, quindi il tetto è il tasso di
accettazione — misurato **0,17%** (3 token su 1.792), decode 2,34 t/s contro un
metro di 8,04. È decodifica in blocco, non parallelismo.

E si compone con il resto invece di competerci: a batch 8 gli esperti distinti
per token scendono da 258 a 155, quindi il parallelismo **ammortizza** il
trasporto invece di aggravarlo.

## Cosa è già stato tentato (non rifarlo)

| tentativo | esito |
|---|---|
| batch di difetto (2048) | OOM: chiede 7.995 MiB di buffer di calcolo |
| `-b 128 -ub 128` | risolve l'OOM |
| prompt come argomento `-p "..."` | si spezza sugli spazi: `error: invalid argument: una` |
| prompt da file `-f` | risolve |
| `editbin /STACK:67108864` sul binario | applicato, **non basta** |

**Il sintomo che resta:** carica, stampa il prompt, genera due token, il processo
**esce senza messaggio** dopo ~25 s di CPU. Quattro righe di log, nessun errore,
nessuna statistica finale. Firma tipica di `0xC00000FD`, ma lo stack è già a
64 MiB.

Log dei tentativi: `D:\ds4_work\llama_run\jacobi{,2,3,4}.log`.

## Il comando che riproduce il difetto

```
cd D:\llama-dspark\build\bin
set LLAMA_MAPPED_IBRIDO=1
set LLAMA_REAP=0
set LLAMA_CACHE_ESPERTI_SLOT=0
llama-lookahead.exe -m C:/ds4-models/DS4-0731-IQ2XXS.gguf ^
  -c 4096 -b 128 -ub 128 -ngl 99 ^
  -ot "ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped" ^
  -t 8 --no-mmap -n 300 -f D:/ds4_work/llama_run/jprompt.txt
```

## Da dove comincerei

1. **Vedere l'errore vero.** Il processo muore muto: lanciarlo sotto un debugger
   (`cdb -g -G`), oppure abilitare i minidump, oppure bisezionare disattivando
   l'ibrido (`LLAMA_MAPPED_IBRIDO=0`) e l'override `-ot` — se senza mappatura non
   muore, il problema è nell'interazione fra il buffer mappato e il grafo del
   lookahead, che ha una topologia molto più frammentata del decode normale.
2. **Ridurre W/G.** Sono costanti nel sorgente (`examples/lookahead/lookahead.cpp`
   righe 52-54). Con `W=4, G=2` il grafo si semplifica di molto: se così regge, è
   una questione di scala del grafo e si risale al limite vero.
3. **Provare prima su un modello piccolo** (`DSpark-draft-Q2K.gguf`, arch `dflash`,
   3 strati) per separare "lookahead è rotto" da "lookahead + DSV4 è rotto".

## PRIMA COSA: lavorare in un worktree separato

Non toccare `D:\llama-dspark`. La sessione principale ci compila e ci misura, e
il 6/8 due processi sullo stesso albero si sono bloccati le DLL a vicenda —
l'agente ha dovuto rinominarle per poter linkare.

```
git -C D:\llama-dspark worktree add -b jacobi D:\llama-jacobi dspark-dsv4
```

Poi si compila **lì dentro**, con la sua cartella `build` propria: due binari
distinti, nessun file conteso, e i due filoni si riuniscono con un merge quando
funzionano. Il costo è una compilazione da zero (~10 minuti); il beneficio è che
nessuno dei due deve aspettare l'altro.

Vale anche per le misure: **un processo pesante alla volta sulla macchina**,
perché la RAM è una sola e il modello ne vuole 74 GiB.

## L'ambiente, che non è standard

- **Ricompilare**: `build_cuda.bat` (copiarlo nel worktree, o lanciarlo con i
  percorsi corretti — usa `cd /d D:\llama-dspark` cablato dentro)
- **Dopo OGNI link**: `editbin /STACK:67108864` sul binario, previo `vcvars64.bat`.
  Senza, llama.cpp va in `0xC00000FD` sui grafi frammentati.
- `--no-mmap` è **obbligatorio** quando si mappa: senza, gli stessi byte stanno
  due volte in RAM (153 GiB su 96).
- `LLAMA_MAPPED_IBRIDO=1` è l'ibrido: prefill su GPU, decode su CPU, stessi byte
  sotto UVA.
- Ramo `dspark-dsv4`, ultimo commit rilevante `394a797`.

## I cancelli

- **Bit-esattezza**: al punto fisso la sequenza deve coincidere con la greedy.
  Confrontare lo SHA256 dell'uscita con quella del metro. Se differisce,
  l'implementazione è sbagliata, non "approssimata".
- **Condizione della macchina**: campionare la RAM libera all'avvio di ogni
  braccio. **Sotto 10 GiB il braccio non vale.** Il 6/8 due processi da 74 GiB
  hanno girato insieme e falsato un'ora di misure.
- **Un processo pesante alla volta.** Se qualcuno sta misurando, la macchina è
  sua.

## Cosa misurare, e contro cosa

Metro stabilito e ripetuto: **8,04 / 8,00 t/s** di decode (ctx 10000, ub 64,
np 1, ibrido, 300 token, temperatura 0). A ctx 102400 il metro è **7,83**.

Da riportare: `n_predict`, `n_accept`, il rapporto (= il fattore di parallelismo
effettivo), il t/s, e lo SHA dell'uscita. Il t/s da solo non basta: serve sapere
se il guadagno viene da meno passi o da passi più veloci.

## Il contesto in tre numeri

```
8,04 t/s   metro autoregressivo
9,16 t/s   con la cache esperti in VRAM (380 slot, bit-esatto, +14%)
  ~17 t/s  il tetto della strada della memoria, misurato
```

Oltre i 17 non si va spostando pesi: lì il limite è che si genera **un token
alla volta**. Questo mandato è l'unica strada aperta oltre quel tetto.

Ledger completo: `docs/porto/LEDGER_RUN.tsv` (103 righe).
