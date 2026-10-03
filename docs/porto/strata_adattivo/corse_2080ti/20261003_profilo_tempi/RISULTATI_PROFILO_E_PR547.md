# Profilo tempi 0.1.38 e verifica memoria prefill (#547)

Data: 2026-10-03. Scheda modificata RTX 2080 Ti da 22 GiB; build Strata 0.1.38, KV 262.144, cache elastica, MTP/speculazione configurati come nel Daily. Nessun carico artificiale. Le misure di profilo sono state raccolte con OktoCGControl spento; al successivo controllo era acceso, perciò non sono state ripetute le misure di velocità.

## Tempi e colli di bottiglia

| Prompt effettivo | Tempo wall | Timeline GPU | Prefill | Decode 32 token | Accettazione spec |
|---:|---:|---:|---:|---:|---:|
| 131.065 token | 163,579 s | 163,530 s | 798,2 t/s | 30,7 t/s | 22/27 |
| 249.993 token | 370,011 s | 369,992 s | 674,6 t/s | 30,4 t/s | 22/27 |

Nel profilo a 250k, QSA selection occupa circa 124,1 s (33,5%); gate/up GEMM 47,2 s (12,7%); attention 44,5 s (12,0%). A 131k: QSA selection 34,9 s (21,3%), gate/up GEMM 24,9 s (15,2%), attention 22,9 s (14,0%). La selezione QSA è il candidato più evidente per ulteriore lavoro sul prefill; gate/up è il successivo blocco di calcolo. Setup/attese host non dominano la corsa da 250k, quindi la tokenizzazione incrementale non emerge da questa misura come prima leva per i t/s del prompt.

## Correzione di accounting #547

La correzione riallinea `Prefill::bytes_needed` alle allocazioni reali: include `HC`, conta il buffer `D` soltanto nel percorso GR unfused e usa il layout MoE coerente col percorso con/senza sorgente. Il flag del percorso è passato a tutti e cinque i siti d'uso, incluso il calcolo della riserva 0.1.38.

Verifiche: build SM75 CUDA 12.6 dal fork `main` completata (129/129); smoke CLI `--help` exit 0; suite CUDA mirata precedente 6/6; prova pool quant completata; a 131k i 32 token greedy generati coincidono col baseline. L'A/B/A a 250k ha misurato 671,24 / 672,62 / 672,78 t/s: la differenza della candidata è sotto la variabilità A/A e non è un guadagno SOTA. La stima corretta riduce di circa 0,31 GiB la riserva necessaria al chunk da 8.192; il beneficio è capacità/cache corretta, non velocità.

Il dump logits della prova A/B/A non è valido (`logits_captured=false`): non si dichiara parità bitwise dei logits. La prova di token generati a 131k è la verifica comportamentale disponibile. Nessuna inferenza è stata avviata mentre OktoCGControl era acceso.

La correzione è stata riportata sul fork `main` e pubblicata nel commit `343bee1` (`GPT6-PREFILL-Conta i buffer reali del prefill`), quindi integrata nel pacchetto `build-0138-daily`. Il binario Daily aggiornato ha SHA-256 `13ee1a89be497ad83c67f62553b1133fec2a8d9309230d43a9dae639d89008a5`; backup e file di ripristino sono in `D:\ds4_work\strata\ripristini\20261003_prefill547_postbuild`. Il manifesto originale 0.1.38 è stato conservato; `prefill-547-validation.json` registra l'overlay e le verifiche.

Riferimento upstream: [PR #547](https://github.com/Niko1221/Strata/pull/547).
