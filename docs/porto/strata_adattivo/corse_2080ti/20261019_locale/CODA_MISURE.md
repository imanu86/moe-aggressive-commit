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

Criterio: `force_trace.txt` **identico byte a byte** a quello di `DET-ov-A0` (altrimenti: la leva cambia i token →
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

# CODA 20 OTTOBRE 2026 — blocchi 8-14 (la pipeline accesa, e i due numeri che mancano)

Perché questa seconda coda: le corse dei blocchi 1-6 (20/10 01:00-01:52) hanno girato il **loop seriale** — il banco
`run_long.py` non chiede `--pipeline-windows` e in 0.1.45 l'auto la lascia spenta su CUDA. Quindi NOSWITCH (17),
`STRATA_OV_CHAIN_PRIO` (19), `STRATA_OV_TOP2_STAT` (20) e `STRATA_MTP_STAGE0` (che richiede `pipeline_windows >= 2`) erano
**inerti**: quei bracci non erano verdetti. Tutte le corse qui sotto usano
`build-overlap2-f20bd46e` (sha256 `96846f4aecca69c0790ac40c8f9a552d13fcb71fb3e0762666ca17a71e6b444d`, `lab/overlap` con le
patch 19+20+21, copiata in `20261004_routed_keep\build-overlap2-f20bd46e`). Prima di ogni blocco: `pause` assente,
`bench.lock` libero, `tasklist | findstr strata.exe` e Jump annotati. Metro noto: i bracci identici corsi la notte del 20/10
si sono differenziati **0,4-2,7%** (media 1,1%) con Jump connesso — sotto ~2,7% non si chiama guadagno.

**Verifica obbligatoria del blocco 8:** se dopo `--add-opt=--pipeline-windows=2` non compare nel log la riga
`note: --pipeline-windows 2 on a layer split of two stages without the draft layer on the first card` oppure una riga
`strata pipeline classes:`, **la pipeline non è partita**: fermarsi e scrivere l'engine.log, non ripetere i bracci.

## 8. Metro con la pipeline accesa (A/A) — prima di tutto

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
bash det_force.sh DET-ov2-A0 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
bash det_force.sh DET-ov2-A0b build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
python bab_verdict.py DET-ov2-A0 DET-ov2-A0b
grep -a "pipeline classes\|pipeline-windows 2 on a layer split\|drafter on CUDA" DET-ov2-A0\engine.log DET-ov2-A0b\engine.log
```

Criterio: la riga `strata pipeline classes: fresh N windows X ms Y tok | speculative …` **deve esserci** (altrimenti il resto
della coda non serve). Dispersione (max−min)/media su L01+L02: è il metro di tutti i blocchi 9-13; se sta sopra il 3%,
ripetere a PC fermo. In questi bracci la catena sta sulla 2080 Ti (default CUDA: `mtp_first_default_on() = false`), cioè
esattamente la configurazione dove PIPELINE2 le misurò portare via 0,6-7,5 ms allo stadio 1.

Una variabile alla volta: qui si accende **solo** la pipeline. Il Daily e il banco della comunità hanno anche
`STRATA_SA_BET=1 STRATA_SA_CHAIN=1` (lo stesso di PIPELINE2): se i verdetti 9-11 restano sotto la dispersione, un secondo
giro li aggiunge ad A e B insieme — ma non insieme alla leva in prova.

## 9. Blocco 9 — `STRATA_P2_FLUSH_NOSWITCH=1` (patch 17) sulla pipeline

```
bash det_force.sh DET-ov2-nsw-A1 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
bash det_force.sh DET-ov2-nsw-B1 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2 --env STRATA_P2_FLUSH_NOSWITCH=1
bash det_force.sh DET-ov2-nsw-A2 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
python bab_verdict.py DET-ov2-nsw-B1 DET-ov2-nsw-A1 DET-ov2-nsw-A2
fc /b DET-ov2-nsw-A1\force_trace.txt DET-ov2-nsw-B1\force_trace.txt
grep -a "pipeline classes\|p2 flush" DET-ov2-nsw-A1\engine.log DET-ov2-nsw-B1\engine.log DET-ov2-nsw-A2\engine.log
```

Criterio (segno letto al contrario, il primo braccio è il B): promuovere solo se **entrambi** gli A sono più lenti del B di
più della dispersione del blocco 8. `force_trace.txt` identici; se differiscono la leva cambia i token → scrivere e fermarsi.

## 10. Blocco 10 — `STRATA_OV_CHAIN_PRIO=1` (patch 19) sulla catena kind 1

```
bash det_force.sh DET-ov2-prio-A1 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
bash det_force.sh DET-ov2-prio-B1 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2 --env STRATA_OV_CHAIN_PRIO=1
bash det_force.sh DET-ov2-prio-A2 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
python bab_verdict.py DET-ov2-prio-B1 DET-ov2-prio-A1 DET-ov2-prio-A2
fc /b DET-ov2-prio-A1\force_trace.txt DET-ov2-prio-B1\force_trace.txt
grep -a "STRATA_OV_CHAIN_PRIO=1\|pipeline classes\|chain from its launch to B\|chain late" DET-ov2-prio-A1\engine.log DET-ov2-prio-B1\engine.log DET-ov2-prio-A2\engine.log
```

Criterio: il B-A-B letto al contrario **e** le righe `strata pipeline classes`: i ms delle finestre speculative a parità di
T devono scendere, `chain late` non deve salire (stage 0 che aspetta B), e la riga `strata mtp: STRATA_OV_CHAIN_PRIO=1:
the chain's stream runs at the default priority` **deve comparire solo nel braccio B** — è la prova che la leva è partita.
Se le speculative non calano: leva chiusa, codice lasciato opt-in com'è.

## 11. Blocco 11 — drafter sulla prima scheda (`STRATA_MTP_STAGE0=1`) con la pipeline accesa

```
bash det_force.sh DET-ov2-stg-A1 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
bash det_force.sh DET-ov2-stg-B1 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2 --env STRATA_MTP_STAGE0=1
bash det_force.sh DET-ov2-stg-A2 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
python bab_verdict.py DET-ov2-stg-B1 DET-ov2-stg-A1 DET-ov2-stg-A2
fc /b DET-ov2-stg-A1\force_trace.txt DET-ov2-stg-B1\force_trace.txt
grep -a "drafter on CUDA" DET-ov2-stg-A1\engine.log DET-ov2-stg-B1\engine.log
```

Criterio: qui la leva esiste davvero (nel blocco 3 era inerte): la riga `strata pipeline: drafter on CUDA0` deve comparire
nel B e `drafter on CUDA1` negli A. Il 20/10 nel loop seriale B aveva perso 2,2% contro A2; sul banco comunità del 19/10
(`mtpst0-0145-a` 634/65,9 · 1220/63,0 · 1500/65,7) stava sotto `nobatch0145-a` (663/67,0 · 1282/66,4 · 1519/69,2). Se anche
qui il B non batte entrambi gli A oltre la dispersione: **chiudere la leva e scrivere «no» nel doc**.

## 12. Blocco 12 — il numero top-2 sulla **pipeline** (patch 20, what decides B ad albero #1)

```
bash det_force.sh DET-ov2-top2 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2 --env STRATA_OV_TOP2_STAT=1 --env STRATA_DECODE_TIMING=1
fc /b DET-ov2-top2\force_trace.txt DET-ov2-A0\force_trace.txt
grep -a "strata overlap top2\|runner-up" DET-ov2-top2\engine.log
```

Criterio: `force_trace.txt` identico byte a byte a `DET-ov2-A0` (altrimenti la leva cambia i token → fermarsi). Leggere
`strata overlap top2: bonus=top1 N1, bonus=top2 N2, altro N3 su N (runner-up non letto U, sua probabilita media p)`:
**N2/(N2+N3) sotto 0,20 → la B ad albero è chiusa per sempre su questo modello; a 0,30 o sopra → segnalare all'owner come
lavoro da 8-12 giorni per un modello grande** (non implementarla). Se `runner-up non letto` è una frazione grande di N la
corsa non è valida: rifarla annotando `STRATA_SA_CHAIN` (che taglia la catena).

## 13. Blocco 13 — il numero top-2 sul **loop seriale** (patch 21; si può correre anche senza pipeline)

```
bash det_force.sh DET-ov2-t2s build-overlap2-f20bd46e --env STRATA_MTP_TOP2=1 --env STRATA_DECODE_TIMING=1
fc /b DET-ov2-t2s\force_trace.txt DET-ov-A0\force_trace.txt
grep -a "mtp top2" DET-ov2-t2s\engine.log
```

Criterio: `force_trace.txt` identico a `DET-ov-A0` (braccio senza leva, stessa config, loop seriale: la leva spenta non
tocca niente). Leggere, per ogni richiesta: `strata serve: mtp top2: rejected/runner-up by depth N/N N/N N/N N/N of W
windows; seconda scelta giusta N di M respinte (%)`. **Sotto 20% → la B ad albero è chiusa su questo modello anche sul
percorso che gira davvero; a 30% o sopra → da segnalare all'owner.** Nota: questa misura rende il draft più lento (una
copia host per passo) e quindi **non è un braccio di velocità**: serve solo il rapporto, non i t/s di questa corsa. Se i due
numeri (blocchi 12 e 13) non concordano, quello che vale è quello della strada che il Daily usa davvero.

## 14. Blocco 14 — `--spec-min-p 0.70` sul banco della comunità (il DET non può vederlo)

Il DET (blocco 4) dice B più lento 1,0-1,3%; ma il banco della comunità ha già un braccio a favore, corso il 19/10 19:13:
`minp070-0143-a` (Daily 0.1.43, unica differenza `--spec-min-p` 0,5 → 0,70) **701/75,9 → 689/76,5 · 1439/70,4 → 1431/77,2 ·
1720/75,3 → 1723/81,1** (prompt/decode, mediane), cioè 128K **+7,7%** sopra la soglia di successo 78. Però: **i testi
generati sono diversi** (confrontati i nove `tokens-*-raw.json`: tutti e nove divergono dalla prima frase) → non soddisfa il
criterio «con token identici». Da chiudere così, B-A-B:

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap
python -c "import json,io;p=r'corse_2080ti\20261019_overlap\cfg-overlap.json';c=json.load(io.open(p,encoding='utf-8'));a=c['args'];a[a.index('--spec-min-p')+1]='0.70';io.open(r'corse_2080ti\20261019_overlap\cfg-overlap-minp.json','w',encoding='utf-8').write(json.dumps(c,indent=1,ensure_ascii=False))"
python ..\20261019_banco_comunita\community_bench.py COMM-ov-minp-A "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap\cfg-overlap.json" "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-overlap2-f20bd46e"
python ..\20261019_banco_comunita\community_bench.py COMM-ov-minp-B  "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap\cfg-overlap-minp.json" "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-overlap2-f20bd46e"
python ..\20261019_banco_comunita\community_bench.py COMM-ov-minp-A2 "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap\cfg-overlap.json" "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-overlap2-f20bd46e"
```

(la prima riga va lanciata da `corse_2080ti\`: scrive `cfg-overlap-minp.json` accanto a `cfg-overlap.json`, cambiato solo
`--spec-min-p`). Criteri: decode mediano 128K del B ≥ entrambi gli A di più della dispersione del banco (i tre bracci
danno anche quella); confrontare i testi:

```
python -c "import json,io,glob
def t(p):
 d=json.load(io.open(p,encoding='utf-8'));return ''.join((c.get('choices') or [{}])[0].get('delta',{}).get('content','') for c in d['chunks'])
for k in ('4096','32768','128000'):
 for r in (1,2,3):
  x=t(r'corse_2080ti\20261019_banco_comunita\COMM-ov-minp-A\tokens-%s-run-%s-raw.json'%(k,r));y=t(r'corse_2080ti\20261019_banco_comunita\COMM-ov-minp-B\tokens-%s-run-%s-raw.json'%(k,r))
  print(k,r,'IDENTICO' if x==y else 'DIVERSO')"
```

Se il guadagno si replica ma i token restano diversi: **non promuovere** (regola del piano par. 0) e passare all'owner la
decisione se accettare risposte diverse per 75,3 → 81,1 t/s. **Attenzione:** `community_bench.py` alla fine fa
`taskkill /F /IM strata.exe` e rilascia `bench.lock` → ferma anche il servizio agenti sulla 8100: blocco da eseguire solo
con l'ok dell'owner.

## Chiusura blocchi 8-14 — corsa del 20/10 02:24-03:32 (`misura_ov2.log`)

Pipeline partita in tutti i bracci 9-12 (righe `pipeline classes` presenti). Esiti nel doc
`OVERLAP_2026-10-19.md`, sezione «CODA 20 OTTOBRE MATTINA». Conferma per il piano:

- **Metro blocco 8 ROTTO**: `DET-ov2-A0 rc=1` (`TimeoutError: Startup deadline`, engine oltre 300 s), `bab_verdict`
  → IndexError. Nessun metro A/A con pipeline. Da rifare a PC fermo prima di promuovere qualunque leva.
- **17 NOSWITCH**: B più veloce 3,4% ma metro assente e identità token non dimostrabile (force_trace differisce anche
  A1-vs-A2 in pipeline) → **inconclusiva, non promossa**. Nessuna config di prova.
- **19 CHAIN_PRIO**: 0,1%, speculative non calate → **chiusa, codice opt-in**.
- **MTP_STAGE0**: B perde **17,4%** (reali, `drafter on CUDA0` solo in B, GPU-reach wait 23,5 vs ~17 ms) → **chiuso «no»**.
- **20/21 top-2**: 29,5% (pipeline) e **45,2% (seriale = percorso Daily)** → B ad albero **segnalata all'owner** come
  lavoro da modello grande; non implementata.
- **min-p 0,70 (blocco 14)**: braccio B **fallito** — `FileNotFoundError: cfg-overlap-minp.json` (la riga `python -c`
  che lo genera non è stata eseguita). Solo i due A: 128K 72,2 / 73,3. Da rifare.

Nessuna leva raggiunge i criteri del piano 1.5 (128K ≥ 78 con token identici): **nessuna config di prova preparata**.

Comandi di riapertura (solo con l'ok dell'owner per la parte GPU; il `python -c` non tocca il Daily):
```
# metro pulito, PC fermo / Jump scollegato
bash det_force.sh DET-ov2-A0 build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
bash det_force.sh DET-ov2-A0b build-overlap2-f20bd46e --add-opt=--pipeline-windows=2
python bab_verdict.py DET-ov2-A0 DET-ov2-A0b
# rigenerare la copia min-p (da corse_2080ti\), poi i tre bracci del blocco 14
python -c "import json,io;p=r'corse_2080ti\20261019_overlap\cfg-overlap.json';c=json.load(io.open(p,encoding='utf-8'));a=c['args'];a[a.index('--spec-min-p')+1]='0.70';io.open(r'corse_2080ti\20261019_overlap\cfg-overlap-minp.json','w',encoding='utf-8').write(json.dumps(c,indent=1,ensure_ascii=False))"
```

## 15. Da non rifare (già misurato, il piano lo vieta)

`STRATA_P2_SWITCH_STAT=1` in un B-A-B; nsys/hop_bench/census di PIPELINE2; expert-parallel, tensor-parallel,
micro-finestre, `--pipeline-windows 3`, `post()` persistente, P-state, `STRATA_P2_SMEM`, `STRATA_P2_FLUSH_US`; la
B ad albero (si decide solo con il numero del blocco 5).

# CODA 20 OTTOBRE SERA — blocchi 16-18 (metro con avvio lungo, min-p sulla comunità, B ad albero)

Giro di codice di questa sera (nessuna GPU: l'agente gira sul motore Strata acceso sulla 8100). Cosa è pronto:

- build **`build-overlap3-168d3fa5`** (sha256 `4f09094e184395ec635a44dc55798c6928a27396a2855ea80c0a5fcf7c13d44f`), copia
  di `lab/overlap` HEAD `168d3fa5` con le patch 19, 20, 21 e **22** (B ad albero, livelli 1 e 2). Log:
  `..\20261019_overlap\build4.log` (`rc 0`, 17 s incrementale). `strata-vision.exe` dal Daily build-0143-daily.
  **Compilata sì, installata no, provata no, misurata no.**
- config nuove in `corse_2080ti\20261019_overlap\`: **`cfg-overlap3.json`** (copia di `cfg-overlap.json` con cambiati
  **solo** `exe`/`vision.exe` → build-overlap3, `log`, `--prompt-cache-file` → file proprio; `env` identico e `args`
  verificato per confronto dei due JSON: 54 opzioni, una sola riga diversa) e **`cfg-overlap3-minp.json`** (uguale, con
  `--spec-min-p` 0,5 → **0,70** e un file di prompt-cache suo, così i bracci non leggono una cache scritta con l'altra
  soglia).
- **`run_long.py` ha un'opzione nuova: `--startup-s <secondi>`** (default 300, quindi i bracci già corsi non cambiano;
  il valore finisce nel `plan.json` del braccio come `startup_s`). Serve perché il blocco 8 è morto lì:
  `TimeoutError: Startup deadline` su `bounded(engine.restart, 300, ...)` — con `--pipeline-windows 2` su questa coppia i
  pesi non finiscono di caricarsi in 300 s (lo stesso runlog segnava anche `gpu_error: too many values to unpack
  (expected 2)` nella lettura di stato VRAM). Con `--startup-s 900` il `timeout 3000` di `det_force.sh` resta sopra il
  peggio possibile (900 di avvio + 2 × 900 di `gen deadline`).

Prima di ogni blocco: `pause` assente, `bench.lock` libero, `tasklist | findstr strata.exe` annotato (il servizio agenti
sulla 8100 è uno di questi), Jump annotato. Metro corrente: i bracci identici corsi la notte del 20/10 si sono
differenziati **0,4-2,7%** (media 1,1%) con Jump connesso; il blocco 8 **non è mai arrivato a un numero**.

## 16. Metro A/A con la pipeline accesa, avvio lungo — il numero che manca dall'inizio

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
bash det_force.sh DET-ov3-A0  build-overlap3-168d3fa5 --add-opt=--pipeline-windows=2 --startup-s 900
bash det_force.sh DET-ov3-A0b build-overlap3-168d3fa5 --add-opt=--pipeline-windows=2 --startup-s 900
python bab_verdict.py DET-ov3-A0 DET-ov3-A0b
grep -a "pipeline classes\|pipeline-windows 2 on a layer split\|drafter on CUDA" DET-ov3-A0\engine.log DET-ov3-A0b\engine.log
```

Criterio: **devono** esserci le righe `strata pipeline classes: fresh … | speculative …`; se mancano la pipeline non è
partita e i blocchi 17-18 non servono (fermarsi, scrivere l'engine.log). Dispersione (max−min)/media su L01+L02 = il
metro di 17 e 18; sopra il 3% ripetere a PC fermo (Jump scollegato). Se `Startup deadline` torna anche a 900 s non
allungare ancora: scrivere `startup_s` e le ultime righe dell'`engine.log`, perché vuol dire che il caricamento compete
con l'engine vivo sulla stessa GPU (il servizio 8100) e il metro va preso con il servizio fermato, con l'ok dell'owner.

## 17. B ad albero, livelli 1 e 2 (patch 22) — cosa paga il secondo ramo

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
bash det_force.sh DET-ov3-tree1-A1 build-overlap3-168d3fa5 --add-opt=--pipeline-windows=2 --startup-s 900
bash det_force.sh DET-ov3-tree1-B1 build-overlap3-168d3fa5 --add-opt=--pipeline-windows=2 --startup-s 900 --env STRATA_OV_TREE=1 --env STRATA_DECODE_TIMING=1
bash det_force.sh DET-ov3-tree1-A2 build-overlap3-168d3fa5 --add-opt=--pipeline-windows=2 --startup-s 900
python bab_verdict.py DET-ov3-tree1-B1 DET-ov3-tree1-A1 DET-ov3-tree1-A2
grep -a "strata overlap tree\|overlap top2\|pipeline classes" DET-ov3-tree1-B1\engine.log
python -c "import io
for n in ('DET-ov3-tree1-A1','DET-ov3-tree1-B1'):
    p=r'..\20261004_routed_keep\%s\force_trace.txt'%n
    w=[l.split() for l in io.open(p,encoding='utf-8',errors='replace') if l.startswith('W ')]
    print(n,len(w),[tuple(x[:4]) for x in w[:6]])"
```

Cosa leggere, nell'ordine:

1. la riga `strata overlap tree (STRATA_OV_TREE=1): seconda ipotesi fatta N su M finestre B; finestre intere N -> prima
   scelta giusta N, seconda giusta N, nessuna N; seconda sopra la soglia <theta>: N; p_on media: prima X, seconda Y`.
   È il numero **sulla strada pipeline con la leva accesa**: `seconda giusta / (finestre intere − prima giusta)` è la
   quota che il livello 3 recovererebbe; `seconda sopra la soglia` dice quante di queste passerebbero il gate `theta` e
   quindi potrebbero essere davvero lanciate. Sotto 0,20 la B ad albero si chiude anche qui; a 0,30 o sopra il livello 3
   (lancio + scelta + scarto) è il lavoro da aprire.
2. **i t/s di B1 non sono un verdetto di velocità**: `STRATA_OV_TREE=1` accende anche la strada dei logit in host (nodo
   memcpy dentro il grafo di ogni passo di catena), quindi B1 è più lento di proposito; `bab_verdict` qui registra solo
   il costo della diagnostica.
3. **identità**: nessuna seconda finestra è lanciata, quindi i token emessi devono restare identici. Nel banco in
   pipeline `force_trace.txt` non è byte-identico nemmeno fra due bracci A (nota metodologica del 20/10: la struttura
   delle finestre cambia ad ogni corsa), quindi il confronto si fa sulle **sole righe `W`** con i token forzati, come
   sopra: stesse righe `W` → la leva non tocca i token; diverse → fermarsi e scrivere il diff.

Livello 2 (la corsia in più esiste, e sta sulla 3060?):

```
bash det_force.sh DET-ov3-tree2 build-overlap3-168d3fa5 --add-opt=--pipeline-windows=2 --startup-s 900 --env STRATA_OV_TREE=2
grep -a "a third lane on CUDA\|three verifiers per stage\|kept out of the expert cache\|tree lane\|does not fit" DET-ov3-tree2\engine.log
grep -a "strata pipeline classes\|decode timing" DET-ov3-tree2\engine.log | cut -c1-260
```

Criterio: `strata serve: STRATA_OV_TREE: a third lane on CUDA0 and CUDA<n>` e `three verifiers per stage` **devono**
esserci, e va scritta la riga `--pipeline-windows 2: <N> MiB of CUDA0 kept out of the expert cache (…, the tree draft's
lane)` con il suo numero (atteso ~270 + 144 MiB di riserva, cioè ~160 MiB in meno di cache esperti sulla prima scheda).
Se compare `the tree lane's GDN snapshot … does not fit`, o `the tree lane's hand-off does not fit`, o la corsia non
compare: **la 3060 non tiene la terza finestra** → il livello 3 è chiuso su questa coppia di schede, e questo è un
numero, non un fallimento. Lo stesso verdetto vale se il braccio parte ma l'engine chiude con una riga `ERR` che nomina
`capture_all` / `verify: capture` (i grafi della terza verifier non stanno): non è un crash del loop, è la corsia che non
si può fare su questa coppia — scrivere le ultime 20 righe dell'`engine.log` e non ripetere il braccio. Se la corsia c'è e il preload regge, il passo successivo è il livello 3 (lancio delle due
ipotesi, scelta al verdetto, scarto con un metodo restore-only nuovo sul `Verifier`: oggi `pl_commit_async` rifiuta
`n_keep < 1`).

## 18. `--spec-min-p 0,70` sul banco della comunità — la config si genera PRIMA (il blocco 14 è fallito lì)

Il braccio B del blocco 14 è morto con `FileNotFoundError: cfg-overlap-minp.json`: la riga che generava la copia non era
stata eseguita. Qui le due copie **esistono già**; verificare prima di correre, poi i tre bracci B-A-B con la stessa
build:

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo
python -c "import json,io
for f in (r'corse_2080ti\20261019_overlap\cfg-overlap3.json', r'corse_2080ti\20261019_overlap\cfg-overlap3-minp.json'):
    a=json.load(io.open(f,encoding='utf-8'))['args']
    print(f,'spec-min-p',a[a.index('--spec-min-p')+1],'pipeline-windows',a[a.index('--pipeline-windows')+1])"
python corse_2080ti\20261019_banco_comunita\community_bench.py COMM-ov3-minp-A  "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap\cfg-overlap3.json"     "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-overlap3-168d3fa5"
python corse_2080ti\20261019_banco_comunita\community_bench.py COMM-ov3-minp-B  "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap\cfg-overlap3-minp.json" "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-overlap3-168d3fa5"
python corse_2080ti\20261019_banco_comunita\community_bench.py COMM-ov3-minp-A2 "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_overlap\cfg-overlap3.json"     "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-overlap3-168d3fa5"
```

Criteri (par. 1.5 del piano): decode mediano 128K del B **≥ entrambi gli A** di più della dispersione dei due A di questo
stesso blocco (il blocco 14 la dava a 1,5% sul 128K, 5,5% sul 4K), e **token identici**:

```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo
python -c "import json,io
def t(p):
 d=json.load(io.open(p,encoding='utf-8'));return ''.join((c.get('choices') or [{}])[0].get('delta',{}).get('content','') for c in d['chunks'])
for k in ('4096','32768','128000'):
 for r in (1,2,3):
  x=t(r'corse_2080ti\20261019_banco_comunita\COMM-ov3-minp-A\tokens-%s-run-%s-raw.json'%(k,r));y=t(r'corse_2080ti\20261019_banco_comunita\COMM-ov3-minp-B\tokens-%s-run-%s-raw.json'%(k,r))
  print(k,r,'IDENTICO' if x==y else 'DIVERSO')"
```

Il braccio favorevole del 19/10 (128K 81,1 contro 75,3, testi diversi) resta un'indicazione: se il guadagno si replica e
i token restano diversi, **non promuovere** (par. 0 del piano) e passare all'owner la decisione se accettare risposte
diverse per quel guadagno. **Attenzione:** `community_bench.py` alla fine fa `taskkill /F /IM strata.exe` e rilascia
`bench.lock` → ferma anche il servizio agenti sulla 8100: blocco da eseguire solo con l'ok dell'owner.

## Correzione a quello che dice il blocco 15 di questa stessa coda

La riga finale del blocco 15 («Da non rifare … la B ad albero (si decide solo con il numero del blocco 5)») è superata:
quel numero è arrivato il 20/10 (45,2% seriale, 29,5% pipeline) e l'owner ha aperto il lavoro, che è la patch 22 di
`lab/overlap` (blocchi 12-13 per il numero, blocco 17 per la conferma con la leva accesa).

## Cosa chiude questa coda e cosa no

- Blocco 16: se riesce, per la prima volta c'è un metro A/A **con la pipeline accesa**, e i verdetti «inconclusivi» dei
  blocchi 9-11 si possono riprendere con un metro vero.
- Blocco 17: decide il **livello 3** della B ad albero (patch 22): la quota di seconde scelte giuste sulla strada
  pipeline con la leva accesa, e se la terza corsia sta sulla 3060. Nessuna promozione: i livelli 1 e 2 non lanciano
  nessuna seconda finestra.
- Blocco 18: chiude finalmente il min-p 0,70 in B-A-B con i testi confrontati.
- Non si tocca: soglia min-p del Daily, `STRATA_MTP_STAGE0` (chiuso «no»), `STRATA_OV_CHAIN_PRIO` (chiusa, opt-in).
  Questo giro di coda è stato scritto senza GPU: compilato sì, installato no, provato no, misurato no.
