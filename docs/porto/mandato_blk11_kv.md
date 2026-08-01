# MANDATO — blocco 11, KV staged (senza la corsia CPU)

LAVORO DI IMPLEMENTAZIONE. Scrivi codice, nel worktree indicato e SOLO li'.

  IL TUO WORKTREE:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-port-kv
                    branch port/blk11-kv, partito dal TRONCO `port/upstream-substrate`
                    che contiene gia' i blocchi 0-6 e 10.
  RIFERIMENTO:      C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a
                    il nostro fork, HEAD af84c42. **SOLO LETTURA.**

**TUTTO CIO' CHE SCRIVI DEVE STARE DENTRO LA TUA RADICE.** Sotto `workspace-write` il resto del
disco e' negato, e te ne accorgeresti solo alla fine, a lavoro fatto. **Non usare git per
scrivere**: il `.git` di questo worktree sta fuori dalla radice e `git add`/`git commit`
falliranno con *Permission denied*. Leggere con git va bene. Al commit ci pensa chi ti ha
lanciato.

Un altro agente sta lavorando al tiering (blocco 7) in `ds4-port-nucleo`, sullo stesso
`ds4_cuda.cu`. **Non preoccuparti dei conflitti: preoccupati del contratto.**

## OBIETTIVO: il KV staged. **NON la corsia CPU G132.**

Il blocco 11 del piano dice *"KV staged e G132 CPU lane"*. **Porta solo la prima meta'.**

> **La corsia CPU G132 e' gia' FALSIFICATA IN MISURA**: costa **+47 ms/token**, perche' il
> pedaggio che paga supera quello che evita. Il bilanciatore stesso si assestava a 1 route su 5
> per minimizzare la perdita. E' nell'atlante delle leve come FALS.

Portarla sarebbe portare una cosa che abbiamo misurato come dannosa. **Se durante il lavoro
trovi che il KV staged dipende dalla corsia CPU, fermati e dillo**: e' un'informazione che
cambia il piano, non un fallimento.

## IL VINCOLO DI PROGETTO GIA' DECISO, e non e' negoziabile

`ds4_gpu_tensor` resta **`{ptr, bytes, owner, device_id}`**. Il campo `host_ptr` del nostro
vecchio fork **non va aggiunto**.

Il KV staged usa invece una **tabella laterale limitata al registry KV**. E attenzione, perche'
qui c'e' la trappola gia' individuata:

> **Non basta una mappa `tensore -> host_ptr`.** Le view ereditano `host_ptr + offset`, e con
> `ptr == NULL` l'offset **non e' ricavabile**. La tabella deve tenere abbastanza da
> ricostruire la view, non solo il puntatore base.

Se la tua implementazione ha bisogno di risolvere una view a partire dal solo tensore, **hai
gia' sbagliato**: e' esattamente il caso che questa nota descrive.

## VINCOLI

- **Nessuna seconda API pubblica.** Il KV ha gia' la sua superficie in `ds4_gpu.h`.
- **Solo single-GPU**: c'e' un guard che rifiuta `g_n_gpus != 1`.
- **Additivo**: upstream resta compilabile su Linux.
- **Spento di default.** Con il flag assente il KV deve comportarsi **identico a upstream**.
  Nel tronco ci sono gia' tre opt-in indipendenti e tutti spenti
  (`DS4_CUDA_DYNAMIC_ARENA_GB`, `DS4_CUDA_PREFILL_MASS_OBSERVE`,
  `DS4_CUDA_VRAM_EXPERT_CACHE`): il tuo sara' il quarto e deve rispettare la stessa disciplina.

## UN FATTO MISURATO CHE TI RIGUARDA

A 150k di contesto i **3,3 GB di VRAM che sembrano liberi non lo sono**: sono lo spazio di
lavoro dell'attenzione. Il blocco 6 ha gia' una fixture che verifica proprio questo caso
(3379 MiB "liberi" -> zero slot, non 480 esperti fantasma). **Se il tuo staging del KV assume
di poter usare quella VRAM, e' sbagliato per la stessa ragione.**

## VERIFICA

```
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" ^
  -S . -B build-kv -G Ninja -DCMAKE_MAKE_PROGRAM="C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe" ^
  -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CUDA_COMPILER="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" ^
  -DCMAKE_CUDA_ARCHITECTURES=86 && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build build-kv --parallel 6
```

Senza `-DCMAKE_C_COMPILER=cl` espliciti CMake non trova il compilatore nemmeno sotto vcvars.

**Fixture** che non richiede il modello da 81 GB: registra un KV, prendine una **view con
offset non nullo**, mettila in staging, e verifica che si risolva alla stessa memoria. **La
view con offset e' il caso che rompe, non il tensore intero.** Guarda
`tests/dynamic_arena_fixture.cu` per lo stile: gira in meno di un secondo, e deve restare nel
build di default come le altre tre.

**Rapporto** in `PORT_BLOCK11_KV.md` **nella radice del tuo worktree**: cosa hai portato con
le righe, la forma esatta della tabella laterale e cosa ci tieni dentro, come risolvi le view
con offset, e **cosa hai trovato sulla dipendenza dalla corsia CPU** (anche se la risposta e'
"nessuna").

Rispondi in italiano, con righe esatte.
