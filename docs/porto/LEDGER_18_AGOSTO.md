# LEDGER 18 AGOSTO — bonifica semantica `GGML_CUDA_DISABLE_GRAPHS` (presenza → valore)

Regia: coordinatore (sessione autonoma, worktree zen-morse). Esecuzione: patch dirette al
motore + esecutore banco fresco per la verifica. Mandato: bonifica in coda dal 16/8
(LEDGER_16, sezione forense «La leva decisiva») — unificare la semantica dei lettori di
`GGML_CUDA_DISABLE_GRAPHS` e verificare a binario fermo con tre bracci (assente / `=0` / `=1`).

## Il difetto (com'era)

Due lettori, semantiche opposte, nello stesso albero:

- il motore, `ggml/src/ggml-cuda/common.cuh` (overlap:1266, subtract:1282, dspark:1234):
  `getenv("GGML_CUDA_DISABLE_GRAPHS") != nullptr` — cancello **A PRESENZA**: qualunque
  valore, incluso `0`, spegneva i CUDA graph;
- la sonda terna (patch del 15/8), `ggml/src/ggml-cuda/ggml-cuda.cu` (overlap:2277,
  subtract:2311): `ng && *ng && atoi(ng) != 0` — **A VALORE**, che codificava nell'albero
  l'assunzione opposta.

Costo storico: tutti i banchi del 15-16/8 girati senza grafi credendoli accesi
(A/B a binario fermo: 13,49 → 15,71 t/s, +16,46%); è la trappola della falsa
«regressione del 16%».

## Censimento lettori e setter (chiuso il 18/8)

| dove | natura | lettore | esito |
|---|---|---|---|
| `D:\llama-overlap` | worktree registrato di llama-dspark, ramo `overlap`, HEAD `3014d3756`, 141 file sporchi (sperimentale del mese, non committato) | `common.cuh:1266` a presenza; sonda terna già a valore | **BONIFICATO** (patch del working tree) |
| `D:\llama-subtract` | **COPIA** di llama-overlap col puntatore `.git` ereditato — MAI git qui | `common.cuh:1282` a presenza; sonda terna già a valore | **BONIFICATO** (stesso testo) |
| `D:\llama-dspark` | repo principale, ramo `jacobi` parcheggiato, pulito, build del 7/8 | `common.cuh:1234` a presenza | NON toccato: albero archivio, coerente col suo binario stantio |
| 12 worktree parcheggiati (`llama-antic`, `llama-bisect-893`, `llama-mtp`, `llama-prefetch-codex`, `llama-prefetch-opus`, `llama-ring`, `llama-ring-impl`, `llama-spex`, `llama-vanilla`, `wt-d2r`, `wt-default`, `wt-fiddler`, `wt-join`, `wt-mmqx`, `wt-morti`) | worktree registrati, rami storici | `common.cuh:1234/1241/1257` a presenza | NON toccati. **REGOLA: chi riesuma uno di questi alberi porta PRIMA la bonifica** |
| `D:\llama-b10227` | copia nuda di upstream | nessun lettore | — |
| script e strumenti | `braccio_*.ps1`, `ovl_catena_nograph.ps1` (`=1` diagnostico), `vram-recovery-run.ps1` (`=1` o rimuove), `impronta.ps1` e `sentinella.ps1` (rimuovono), `run_porto_hot.ps1` (non la tocca) | — | **nessuno setta `=0`**: comportamento valido sotto entrambe le semantiche. Aggiornato solo il commento della sentinella (citava la semantica vecchia) |

I comandi avvelenati con `=0` del 15-16/8 erano stringhe `-Extra` composte a mano e registrate
in handoff/ledger; il comando canonico ne è privo dal 16/8. La trappola inversa (uno script
che contasse sulla presenza per SPEGNERE) non esiste: tutti gli spegnimenti deliberati usano
`=1`, che sotto la semantica nuova fa la stessa cosa.

## La semantica scelta

A VALORE, idioma dei cancelli nuovi (`kv-gather.cu`, `cache-esperti.cu`) e di
`GGML_CUDA_DISABLE_FUSION`:

```cpp
static const bool disable_cuda_graphs_due_to_env = [] {
    const char * v = getenv("GGML_CUDA_DISABLE_GRAPHS");
    return v && *v && atoi(v) != 0;
}();
```

`=0` ≡ assente ≡ grafi ACCESI; `=1` spegne. La sonda terna resta invariata: ora concorde.

**Upstream legge ancora A PRESENZA** (master `common.cuh:1258`): a ogni rebase da upstream la
bonifica va ri-applicata. **Ogni binario compilato prima del 18/8 legge ancora a presenza.**

## La build (18/8, 06:31–06:36)

Build shared: `llama-server.exe` è uno stub (~10 KB) e il suo SHA non cambia mai
(`C727251E…`). In una build shared **l'identità del binario è la DLL, non l'exe**.

| binario | pre-bonifica | post-bonifica |
|---|---|---|
| `ggml-cuda.dll` (overlap) | `1ED035D3D3782F39…` (16/8 02:30) | `06BF8AAF120B79CF…` (18/8 06:36) |
| `ggml-cuda.dll` (subtract) | `F45AA564C2D1B807…` (18/8 05:52) — **backup**: `ggml-cuda_pre_bonifica_18ago0552.dll` | NON ricompilata (rinvio deliberato) |

**Errore di backup, da lezione**: prima della ricompila di overlap era stato messo in salvo
solo lo stub `llama-server.exe` (SHA invariato per costruzione — inutile). La DLL del 16/8
(`1ED035D3…`) è stata sovrascritta e NON è ricostruibile bit-uguale. L'ultima DLL a semantica
di presenza sopravvissuta è quella di subtract 05:52 (backup fatto ex post, a macchina libera).

**Subtract NON ricompilata** (scelta deliberata): il banco lungo dell'altra sessione gira sul
suo binario 05:52 e una campagna esige il binario fermo. Il sorgente è già bonificato: la
PROSSIMA build di subtract porta il cancello nuovo e `sha_ggml_cuda` cambierà — è atteso,
non un'anomalia.

Il runbook (§11, buco 12) avverte che una build nuova invalida i confronti con lo storico:
il cancello di verifica qui è INTERNO ai tre bracci sullo stesso binario nuovo; il confronto
con lo storico è solo di zona (riferimento freddo 16,70 del 17/8).

## Collisione sfiorata: la ricompila sotto la campagna altrui

La ricompila delle 06:31–06:36 è avvenuta mentre un'altra sessione aveva una campagna attiva
sul build overlap (`topk_fuso`, bracci a/b alle 05:37 e 06:20). Forense a macchina libera:
**nessun braccio topk_fuso dopo le 06:36** (la runs dir è ferma a `topk_fuso_b`) e **nessuna
build estranea prima della mia** (object non-CUDA fermi al 16/8 02:30) → nessun confronto
contaminato: i due bracci girano entrambi sulla DLL vecchia e sono consistenti fra loro.
Contromisure per il futuro:

- marcatore `ATTENZIONE_BUILD_OVERLAP_CAMBIATA_20260818.md` nella work dir del 15-agosto;
- avviso inviato alla sessione «Recupero sessioni Codex e workflow agenti»;
- **REGOLA: mai ricompilare un albero mentre una campagna altrui può star girando sul suo
  build** — prima il censimento processi/artefatti, poi il backup DELLA DLL, poi la build.

## Il banco a tre bracci — ESEGUITO E VERDE (18/8, corse 15:43–16:20)

Due tentativi fermati AL PREFLIGHT dall'esecutore (zero corse, zero processi toccati):
**06:38** (banco lungo `pad_b0` su subtract + campagna `topk_fuso`) e **10:28** (replica
`gather_g1_r2` partita 22 secondi prima del check — le repliche distavano ~74 minuti: una
sentinella a sola assenza di processi dà falsi «libero»). Sentinella v2 su processi E file,
conferma a 90 minuti; coordinamento: due avvisi alla sessione «Recupero sessioni Codex e
workflow agenti», push all'utente, finestra presa solo a quiete vera (ultima scrittura
altrui 14:05, banco dalle 15:39).

Terzo tentativo: preflight §1 TUTTO verde (RAM 88,9 GB, VRAM libera 11.730 MiB, GPU a
riposo, porte libere) e `sha_ggml_cuda = 06BF8AAF…` verificato PRIMA E DOPO il banco:
binario fermo per costruzione.

| braccio | t/s (r1/r2/r3) | mediana | delta vs assente |
|---|---|---:|---:|
| ASSENTE (`<spento>(D)`) | 16,50 / 16,47 / 16,48 | **16,48** | — |
| ZERO (`0(E)`) | 16,45 / 16,47 / 16,45 | **16,45** | **−0,18 %** (cancello ≤3 %: SUPERATO) |
| UNO (`1(E)`) | 13,66 / 13,62 / 13,61 | **13,62** | **−17,35 %** (cancello ≥10 % sotto: SUPERATO) |

Parità perfetta su tutte e 9 le corse: p1 `.90025 (713/792)`, mean len 2,47; SHA uscita
`4FDCFADF…C65D` **= SOTA storica**; buchi 47.906, colpi 77,9 %; riga `cache-esperti:`
identica carattere per carattere (473 slot, sfratto_par=1); sched-profilo = 0 righe; zero
assert/errori CUDA/divergenze; chiusure ctrl-c pulite; spread interno ≤ 0,37 %. Telemetria
§6.8 su ogni braccio: regime storico (SM 1942 MHz, ~99 W; il braccio UNO consuma ~8 W in
meno a clock quasi pari — grafi spenti = bolle di submission, non throttling). Zona: 16,48
contro il freddo 16,70 del 17/8 = −1,32 %, dentro la deriva; genealogia fredda (9 processi,
snapshot 0), confrontabile SOLO col freddo (§8.9).

**VERDETTO: bonifica CONFERMATA A MISURA.** `=0` è indistinguibile dall'assenza (grafi
accesi); `=1` spegne. Letto al contrario, i CUDA graph valgono **+20,99 %** (13,62 → 16,48),
coerente col +16,46 % storico misurato nell'altro verso. La trappola del 15-16/8 è chiusa;
runbook §3.3 e §10.4 p.14 passati a MISURATO in questo stesso commit. 20/20 cancelli
superati; rapporto completo dell'esecutore agli atti della sessione.

## Artefatti

- backup DLL a semantica vecchia: `D:\llama-subtract\build\bin\ggml-cuda_pre_bonifica_18ago0552.dll`
- backup stub (inutili ma esistenti): `llama-server_pre_bonifica_16ago.exe` (overlap),
  `llama-server_pre_bonifica_18ago0552.exe` (subtract)
- marcatore: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\ATTENZIONE_BUILD_OVERLAP_CAMBIATA_20260818.md`
- log del banco (72 file, 8 per corsa: server.log, summary.json, r1.output/.response,
  hw.csv, cpu.csv, telemetry.out, server.out):
  `…\work\runs\bonifica_graphs_{assente,zero,uno}_b1200_r{1,2,3}_20260818.*`
