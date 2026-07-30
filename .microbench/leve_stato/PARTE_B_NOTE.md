# PARTE B — nota di riconciliazione
Il TSV contiene 39 righe dati; le famiglie strettamente accoppiate sono aggregate con wildcard o parentesi.
Il codice corrente prevale su documenti storici quando il comportamento è cambiato.
`DS4_MTP_BATCH_VERIFY=1` oggi esclude `decode2-exact`: non è un interruttore per abilitarlo.
`DS4_CUDA_REAP_MASS_*` è tornata raggiungibile nel codice, ma non ha ancora una misura.
`DS4_G73_OPEN` resta OFF e cancella il vecchio 7,8×, confuso con `TOKEN_SPLIT=0`.
`DS4_CUDA_STREAM_ADMIT_UNIFIED` resta SPORCA perché unisce pool-retry e hot-all in un run incompleto.
La famiglia deadline resta MAI: patch pronta non applicata.
