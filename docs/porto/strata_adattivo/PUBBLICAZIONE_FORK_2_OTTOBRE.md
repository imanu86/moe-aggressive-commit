# Fork pubblico e daily operativo — 2 ottobre 2026

Su richiesta dell'utente, pubblicato il fork MIT:
https://github.com/imanu86/Strata-2080Ti

Release finale:
https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.31-sm75-20261002-r1

Snapshot Strata0.1.31 gia' validato: nove patch locali, HC/GDN FP16,
dequant vettoriale, PR315 e prefill top-k col limite dei blocchi attivi.
CH16, score BPW e PR439 esclusi. Conservati cronologia upstream e crediti.
Misure pubblicate riferite alla **RTX2080Ti modificata a22GB**, non alla11GB:
prefill886,38t/s a131k,638,67t/s a250k; decode39,272/39,218t/s.
Benchmark con limiti,16parita' native, retrieval e manifest sorgenti pubblici.

## Release e controlli

ZIP30.030.900byte, solo eseguibile gia' testato, licenza, crediti,
requisiti runtime e checksum. Nessun peso modello, configurazione privata,
chiave o DLL CUDA inclusa.

- Exe SHA256: `f469e096e868e4579daaec71ceef63693790e300e7a4cc5b49a8853d075a1d34`.
- ZIP SHA256: `6cc41aea68683248e85d931f3c4f62f8d00e2365d261ae44ea16e38c77089552`.
- Server SHA256: `3e556df4e13f783f9d961113dd0bbed7481f677e265b45c3a7f238b18530484a`.
- Tag finale: `v0.1.31-sm75-20261002-r1`, commit `b9e3c88853106afc1027e995f8613b265fbbc2ae`.

521file originali verificati sia nel checkout sia nei blob Git. Un file BAT
aveva fine riga diversi nel blob: corretti, senza cambiare il motore. Verifica
CPU del generatore/lanciatore superata, incluso percorso con spazi, porta
personalizzata, conservazione del JSON esistente e limite contesto.

Un workflow CPU aggiunto durante la pubblicazione e' stato **rimosso su richiesta
dell'utente**; GitHub Actions disabilitato nel fork. Nessuna automazione attiva.
La prima release e' conservata come packaging superato; usare quella r1.
Nessuna nuova compilazione CUDA, avvio modello o prova GPU per pubblicare.

## Daily allineato, 09:59 Europe/Rome

L'utente ha segnalato correttamente che il lanciatore SOTA puntava al bundle
top-k attuale, ma la cartella canonica `build-0131-daily` conteneva ancora a74e,
e il checkout operativo era fermo alla vecchia base0.1.30 piu'13commit.

Ora `D:\ds4_work\strata\Strata` e' `main` del nostro fork pubblico, commit
`ad4700d61852af3481c8c36a98e5411a76e167cc`. Merge con entrambi i genitori:
13commit locali preservati; tree identico allo snapshot gia' validato.
`origin` nostro fork; `upstream` Niko1221. Sorgenti nel checkout operativo
verificati sul manifest; file locali/untracked preservati.

`build-0131-daily` contiene ora il bundle esatto f469, inclusi source/server.
JSON SOTA e BAT Desktop/copie repository puntano al percorso daily canonico;
copie byte-identiche, KV262144/int8/resident32768, reserve1393MiB, cache
auto/elastica e MTP invariati. SHA JSON:
`24c17abb0962a20a4a53fcdd7acc053805df38ae6ceb4997e1791b64b6480645`;
SHA BAT: `5d66298cb04b391f373697e024f36574f08082e71dc07f32634f9b93ff80d41f`.

Ripristino completo del daily precedente, bundle Git e quattro copie JSON/BAT:
`D:\ds4_work\strata\ripristini\20261002_095931_allinea_daily_sota`.
Record `alignment.json`; vecchio exe a74e preservato nel sottobundle.
Nessuna ricompilazione o modifica della combinazione validata. Motori spenti,
macchina libera; non interagire con le altre chat e non avviare altri test.
