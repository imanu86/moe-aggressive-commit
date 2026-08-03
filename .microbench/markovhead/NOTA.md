# markovhead — il sottografo della testa di Markov, isolato

3/8/2026. Replica esatta di `build_dspark_markov_head` (fork dspark-dsv4,
`src/models/dflash.cpp`) su `ggml_backend_sched` CUDA+CPU: w1 f16, w2 q2_K,
conf bf16, base [129.280×5] su CUDA, tokens I32 su CPU, 5 iterazioni con
concat accumulativo e catena argmax.

```
full 2,06 ms | noconf 1,94 | nochain 2,01 | treecat 2,05 | pavimento 0,04
(mediane, 20 esecuzioni; REBUILD con build+alloc per giro: identico)
```

**Esito: il sottografo costa 2 ms, non 538.** I tre sospetti (concat
quadratico, argmax serializzante, intermedi da 517 KB) sono falsificati
in isolamento. Il resto della storia in `docs/porto/MARKOV_ASSOLTA.md`:
i 538 ms erano verifica MoE-CPU del bersaglio, non testa.

Build: `build.bat` (cl + link alle import lib di D:\llama-dspark\build).
Esecuzione: `markov_bench.exe <variante> [iterazioni]` con le DLL del build
nel PATH. La variante `prealloc` (cpy su viste di un tensore unico) crasha
in ggml-alloc (`buffer_id >= 0`): il pattern non è allocabile così, ma non
serviva più dopo il verdetto.
