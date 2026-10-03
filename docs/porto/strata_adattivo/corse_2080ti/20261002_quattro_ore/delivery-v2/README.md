# Pacchetto locale sperimentale, 0.1.37 / RTX2080Ti22GB

Non installato nel Daily e non pubblicato. Il profilo operativo resta0.1.36, cache auto/elastica, spec4, KVINT8 capienza262144/residente32768. Non c'è una nuova SOTA confermata dal top-k dinamico: +1,148% nel confronto controllato a131118token, sotto soglia3%, una coppia negativa.

- `align037-from-2c394674.patch`: allineamento del fork2c394674 a upstream db4f91a, preservando il port Turing.
- `experimental-dynamic2.patch`: controllo dinamico per graph catturate, successivo alla patch di allineamento; defaultOFF.
- `align037-dynamic2-from-2c394674.patch`: alternativa completa alle due patch precedenti. Non applicare entrambe le alternative.
- `source037-dynamic2-EXPERIMENTAL.zip`: sorgenti esatti del candidato con harness portabile228casi, senza workflow del fork.
- `strata-037-sm75-dynamic2-EXPERIMENTAL.exe`: binario locale testato, SHA256 `2818665cdbc004147cf1ac71137ed5cb0a0293e7e0013d1097cc76bc2d9a3422`.
- `pr512-isolated-on-upstream037.patch`: quattro soli file della PR512, da applicare esclusivamente a upstreamdb4f91a; non è la patch completa del fork.

Patch controllate con `git apply --no-index --check` sui rispettivi sorgenti di base; manifest dei sorgenti in `manifest.json`. Eseguibile sm75, CUDA12.6, MSVC14.44.35207 Release; richiede runtimeCUDA/cuBLAS della workstation. Nessun modello o credenziale incluso. Il codice è per la2080Ti modificata22GB, non validato sulla versione11GB.

Build locale: VisualStudio2022/vcvars64, CMake/Ninja, `CMAKE_CUDA_ARCHITECTURES=75`, `CMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc`, `CMAKE_CUDA_RUNTIME_LIBRARY=Shared`, `STRATA_NATIVE_EXPERTS=ON`, `STRATA_PARITY_PROMPT_ATTN=ON`, `STRATA_BUILD_TESTS=OFF`. Questa prova usa `STRATA_GGML_DIR=D:/ds4_work/strata/Strata/third_party/llama.cpp`; la CMake del progetto fissa il fallback a3cf03257f219afbe7334045ff7c6a06ac68c627d. Riferimento completo nei log configure/build della sessione.

Per ispezionare il kernel: impostare `STRATA_TOPK_DYNAMIC=1` per il solo processo sperimentale; `strata_tune.topk_dynamic=0|1` confronta gli stessi grafi tra richieste. Il setter sincronizza prima di cambiare il modo. Solo sm75, unaGPU; altri percorsi restano invariati. Non modificare il launcher operativo per fare questa prova.

Pubblicazione/integrabilità: controllare branch/status e proteggere eventuali modifiche prima di applicare sul main autorizzato. Le scritture effettive nel fork/Daily sono attualmente negate dal profilo, e GitHub `create_blob` restituisce403 “Resource not accessible by integration”. Non è un'approvazione ancora attesa dall'utente. Non aggirare il blocco usando un indice Git alternativo o credenziali copiate. Quando il canale di scrittura torna disponibile, fare commit piccoli con pathspec espliciti e push immediato. Per la PR preservare tutti i file ufficiali upstream, compresi i workflow: la copia di build non è un albero sostitutivo da pubblicare integralmente.

Le prove di questo candidato usano esplicitamente `--pcie-frac 0.28`: la0.1.37 cambia il calcolo del valore automatico e il nuovo default non è stato validato sulla nostra macchina. Il confronto isolato dellaPR512 ha dispersione51,50% fra i riferimenti, quindi resta inconcludente e draft.

I risultati finali di correttezza, PR512 e variante547 sono nel report `QUATTRO_ORE_2_OTTOBRE.md` del checkout research. Il primo A/B/A apparentemente favorevole, i prefill outlier e gli output non identici sono tutti conservati nell'evidenza; non usarli come prova di nuova SOTA.
