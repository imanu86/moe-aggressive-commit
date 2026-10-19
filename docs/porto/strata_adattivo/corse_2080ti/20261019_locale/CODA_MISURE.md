# CODA MISURE — Obiettivo 1 (lab/overlap), 19 ottobre 2026 sera

Le corse qui sotto NON sono state eseguite: chi scrive gira sul motore Strata acceso sulla porta 8100 (servi_agenti.py,
che tiene `bench.lock` per tutto il servizio) e quindi non può prendere la GPU. Ogni blocco è un passo del
`PIANO_GLOBALE_2026-10-19.md` (par. 1.0-1.5) già pronto da copiare, nell'ordine. Prima di ogni blocco: `pause` assente,
`bench.lock` libero, `tasklist | findstr strata.exe` annotato, Jump annotato (`tasklist | findstr JumpConnect`).
In questo momento: Jump **connesso**, un `strata.exe` vivo (il servizio agenti).

Build di laboratorio già fatta (CPU, senza GPU): `lab/overlap` compilato con
`python -u build_lock_noeng.py C:\Users\imanu\source\repos\Strata-wt\overlap --jobs 4`
→ esito in `corse_2080ti\20261019_overlap\build1.log` (vedere là `rc` e `sha256`).

## 0. Copia della build accanto ai banchi — **FATTA** (non è una misura)

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
python copia_build.py C:\Users\imanu\source\repos\Strata-wt\overlap overlap "lab/overlap, leve 19 ov-chain-prio + 20 ov-top2-stat opt-in"
→ C:\...\20261004_routed_keep\build-overlap-bc2e87a0   sha256 c8a1a437b5ff2e8bdf87facc6162db88ef6b25c2873deb56a4dae3d072b53479
```

Già eseguita il 19/10 (20:20): cartella `build-overlap-bc2e87a0` con `strata.exe` + `build.json` + `source/serve` +
`source/tools`; `strata-vision.exe` copiato dal Daily build-0143-daily. L'exe è compilato da HEAD `b2c2aefd`
(le leve); i commit dopo sono solo `docs/` e `stack/`, quindi l'exe non cambia. Tutti i blocchi sotto usano
`build-overlap-bc2e87a0`.

## 1. Passo 1.0 — dispersione A/A (metro di tutto il lavoro)

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
bash det_force.sh DET-ov-A0 build-overlap-bc2e87a0
bash det_force.sh DET-ov-A0b build-overlap-bc2e87a0
python bab_verdict.py DET-ov-A0 DET-ov-A0b
```

Criterio: dispersione (max−min)/media su L01+L02 **sotto il 3%**. Se è sopra: ripetere a PC fermo (Jump scollegato)
prima di proseguire, e non promuovere nessuna leva finché non è sotto.

## 2. Passo 1.1a — polling senza cambio scheda (`STRATA_P2_FLUSH_NOSWITCH=1`)

```
bash det_force.sh DET-ov-nsw-A1 build-overlap-bc2e87a0
bash det_force.sh DET-ov-nsw-B1 build-overlap-bc2e87a0 --env STRATA_P2_FLUSH_NOSWITCH=1
bash det_force.sh DET-ov-nsw-A2 build-overlap-bc2e87a0
python bab_verdict.py DET-ov-nsw-B1 DET-ov-nsw-A1 DET-ov-nsw-A2
```

Criterio (chiamata invertita, si legge il segno al contrario): la leva vale solo se **entrambi** gli A sono più lenti
del B di più della dispersione A1/A2 del blocco 1. `fc /b DET-ov-nsw-A1\force_trace.txt DET-ov-nsw-B1\force_trace.txt`
deve dire che i file sono identici; se differiscono la leva cambia i token → scrivere e fermarsi.

## 3. Passo 1.1b — drafter sulla prima scheda (`STRATA_MTP_STAGE0=1`)

```
bash det_force.sh DET-ov-stg-A1 build-overlap-bc2e87a0
bash det_force.sh DET-ov-stg-B1 build-overlap-bc2e87a0 --env STRATA_MTP_STAGE0=1
bash det_force.sh DET-ov-stg-A2 build-overlap-bc2e87a0
python bab_verdict.py DET-ov-stg-B1 DET-ov-stg-A1 DET-ov-stg-A2
```

Criterio: il primo braccio (13/10) era 63-66 t/s contro 66-69 senza → se anche al B-A-B B non batte entrambi gli A,
chiudere la leva e scrivere «no» nel doc. `force_trace.txt` identico A/B1.

## 4. Passo 1.1c — soglia bozze (`--spec-min-p 0.70`)

La soglia è già nella config del banco: `run_long.py` ha `--set-opt` che la sostituisce (con `--add-opt` ci sarebbero
due valori), quindi la copia della config non si tocca.

```
bash det_force.sh DET-ov-minp-A1 build-overlap-bc2e87a0
bash det_force.sh DET-ov-minp-B1 build-overlap-bc2e87a0 --set-opt=--spec-min-p=0.70
bash det_force.sh DET-ov-minp-A2 build-overlap-bc2e87a0
python bab_verdict.py DET-ov-minp-B1 DET-ov-minp-A1 DET-ov-minp-A2
```

Criterio: guardare **ms per token**, non ms per finestra (`strata pipeline classes:` in `engine.log`: ms e tok per
finestra, fresca e speculativa). Se ms/token non migliora oltre la dispersione: scartata. Nota: qui i token forzati
restano gli stessi ma le finestre cambiano dimensione, quindi `force_trace.txt` resta confrontabile solo come testo
forzato — il numero che decide è ms/token.

## 5. Passo 1.2 — diagnostica «seconda scelta» (`STRATA_OV_TOP2_STAT=1`)

```
bash det_force.sh DET-ov-top2 build-overlap-bc2e87a0 --env STRATA_OV_TOP2_STAT=1 --env STRATA_DECODE_TIMING=1
fc /b DET-ov-top2\force_trace.txt DET-ov-A0\force_trace.txt
grep -a "strata overlap top2" DET-ov-top2\engine.log
```

Criterio: `force_trace.txt` **identico byte a byte** a quello di `DET-ov-A0` (altrui: la leva cambia i token →
fermarsi). Leggere la riga `strata overlap top2: bonus=top1 N1, bonus=top2 N2, altro N3 su N (runner-up non letto U,
sua probabilita media p)` e scrivere nel doc `N2/(N2+N3)`: **sotto 0,20 la B ad albero è chiusa per sempre su questo
modello; a 0,30 o sopra va segnalata all'owner come lavoro da 8-12 giorni per un modello grande** (non implementarla).
Se `runner-up non letto` è una frazione grande di N, la corsa non è valida: rifarla annotando `STRATA_SA_CHAIN`.

## 6. Passo 1.3 — catena kind 1 senza contesa (`STRATA_OV_CHAIN_PRIO=1`)

```
bash det_force.sh DET-ov-prio-A1 build-overlap-bc2e87a0
bash det_force.sh DET-ov-prio-B1 build-overlap-bc2e87a0 --env STRATA_OV_CHAIN_PRIO=1
bash det_force.sh DET-ov-prio-A2 build-overlap-bc2e87a0
python bab_verdict.py DET-ov-prio-B1 DET-ov-prio-A1 DET-ov-prio-A2
grep -a "strata pipeline classes" DET-ov-prio-A1\engine.log DET-ov-prio-B1\engine.log DET-ov-prio-A2\engine.log
grep -a "strata pipeline: the chain from its launch to B" DET-ov-prio-A1\engine.log DET-ov-prio-B1\engine.log DET-ov-prio-A2\engine.log
```

Criterio: B-A-B con il segno letto al contrario **e** le righe `pipeline classes`: i ms delle speculative a parità di T
devono scendere; la riga «the chain from its launch to B» (forced) non deve peggiorare in modo che lo stadio 0 resti
attivo («B: fine stadio 0 prima del verdetto» non sotto 0 — in `engine.log`, righe `strata pipeline classes: ... chain
late`). Se le speculative non calano: chiudere la leva e lasciare il codice opt-in com'è.

## 7. Passo 1.5 — banco della comunità, solo con le leve promosse dal DET

Config: `corse_2080ti\20261019_overlap\cfg-overlap.json` (copia di `strata-0143-daily.json` con `exe`/`vision.exe`
della build, `log` e `--prompt-cache-file` nella cartella). Braccio con le leve = stesso file con l'env delle leve
promosse aggiunte a mano (`env` della copia), oppure `--env` del runner se lo supporta.

```
python ..\20261019_banco_comunita\community_bench.py COMM-ov-A  <cfg Daily 0.1.43 assoluta> <build Daily 0.1.43 assoluta>
python ..\20261019_banco_comunita\community_bench.py COMM-ov-B  <cfg-overlap.json assoluto> <build-overlap-bc2e87a0 assoluto>
python ..\20261019_banco_comunita\community_bench.py COMM-ov-A2 <cfg Daily 0.1.43 assoluta> <build Daily 0.1.43 assoluta>
```

Criterio di successo dell'obiettivo 1: decode mediano 128K ≥ **78 t/s** (Daily 75,3) con token identici tra i bracci;
obiettivo pieno 80. Riferimento 19/10 (Jump scollegato): Daily 0.1.43 r2 prompt/decode 701/75,9 · 1439/70,4 ·
1720/75,3.

## 8. Da non rifare (già misurato, il piano lo vieta)

`STRATA_P2_SWITCH_STAT=1` in un B-A-B; nsys/hop_bench/census di PIPELINE2; expert-parallel, tensor-parallel,
micro-finestre, `--pipeline-windows 3`, `post()` persistente, P-state, `STRATA_P2_SMEM`, `STRATA_P2_FLUSH_US`; la
B ad albero (si decide solo con il numero del blocco 5).
