# Audit 50 - ring-esperti e reap tagliati

Data: 10 agosto 2026. Solo modifica e verifica statica: nessuna compilazione e
nessun avvio del server.

## Bilancio

- 2.072 righe nette rimosse dal contenuto esistente, contando anche le 49 righe
  del sostituto `working-set` e senza contare questo rapporto.
- `ring-esperti.cu` e `.cuh` sono stati cancellati insieme a include, dispatch,
  init, pubblicazione token, registrazione in `supports_op`, leve negli script e
  documento `ANELLO.md`.
- `reap.cpp` e `.h` sono stati cancellati insieme a observer CPU, provider e
  maschera di ammissione MoE, thread, politica, dump, include, call-site, CMake e
  reset `LLAMA_REAP` negli script.

Il ring conservava basi e tag per processo con chiave priva dell'identita' del
modello: bersaglio e bozza potevano quindi usare i pesi l'uno dell'altro. Reap
fondeva nella stessa mappa gli id dei due modelli e poteva applicare al bersaglio
un'ammissione costruita anche dal rango di residenza del ramo overlap.

## Cosa resta

Resta solo il minimo vincolante del working set di Windows, ora isolato in
`common/working-set.cpp` e no-op per difetto. La leva storica
`LLAMA_REAP_WS_MIN_GB` resta intenzionalmente compatibile: protegge la memoria
pageable dal trimmer che il 4 agosto sfratto' 36 GB in sette secondi.

## Non tolto pur essendo sospetto

- `kv-ring`, le sue leve e i suoi contatori: e' un sottosistema distinto e vivo.
- `cache-esperti`: e' il sostituto per-istanza del vecchio ring ed e' in uso.
- `REAP_CONFLITTI.md`, gli audit 08/09/10/19/20/47 e
  `patch_cache_bozza.diff`: restano come prove e cronologia, non sono compilati.
- `rif_dwarfstar`: e' un albero di riferimento separato e non collegato a questi
  call-site.

La scansione dei sorgenti vivi non trova piu' simboli ring, observer reap,
provider di ammissione o leve `LLAMA_REAP*` diverse dal minimo del working set.
Il cancello SHA e throughput resta alla macchina di misura.
