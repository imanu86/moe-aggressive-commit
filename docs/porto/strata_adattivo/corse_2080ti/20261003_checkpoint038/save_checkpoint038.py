"""Publish only completed evidence metadata; keep binary weights/logits private."""
from pathlib import Path
import json,hashlib,shutil,statistics,datetime
BASE=Path(__file__).resolve().parent;R=BASE/'checkpoint038_20261003'
root=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo')
speed=json.loads((R/'model-tests-r3/results.json').read_text(encoding='utf-8'))
quality=json.loads((R/'quality-tests-r3/results.json').read_text(encoding='utf-8'))
comparison=json.loads((R/'model-tests-r3/comparison.json').read_text(encoding='utf-8'))
final=json.loads((R/'final-state.json').read_text(encoding='utf-8'))
assert speed['status']==quality['status']=='completed'
assert final['upstream_server_returncode']==0 and not final['strata_processes']
assert all(item['unchanged'] for item in final['daily'].values())
out=root/'corse_2080ti/20261003_checkpoint038';out.mkdir(exist_ok=False)
(out/'.gitattributes').write_text('* -text\n',encoding='utf-8')
selected=['provenance.json','patch-provenance.json','patch-provenance-measured.json','baseline-build.json','qa-build.json','checkpoint-grid.patch','checkpoint-grid-measured.patch','qa-readout-A.patch','qa-readout-B.patch','configure.log','build-baseline.log','build-candidate.log','build-measured-candidate.log','build-qa-A.log','build-qa-B.log','final-state.json','upstream-server-tests.log','geometry-control.json','dependency-pinned-check.json']
for rel in selected:shutil.copy2(R/rel,out/rel)
for folder_name in ['model-tests-r2','model-tests-r3','quality-tests-r3']:
    for src in (R/folder_name).rglob('*'):
        if src.is_file() and src.suffix in ('.json','.jsonl','.log') and src.name!='comparison-pending-cache0.json':
            rel=src.relative_to(R);dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
for name in ['prepare_checkpoint038.py','build_checkpoint038.py','patch_checkpoint038.py','test_checkpoint038.py','finalize_checkpoint038_guard.py','build_checkpoint038_qa.py','test_checkpoint038_qa.py','analyze_checkpoint038.py','compare_checkpoint038_geometry.py','check_checkpoint038_final.py','save_checkpoint038.py']:
    shutil.copy2(BASE/name,out/name)
shutil.copy2(Path(r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75\validate_model.py'),out/'validate_model_policy.py')
manifest={str(src.relative_to(out)).replace('\\','/'):hashlib.sha256(src.read_bytes()).hexdigest() for src in sorted(out.rglob('*')) if src.is_file()}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
perf=comparison['performance'];lines=[]
for chunk,p in perf.items():
    a,b=p['A'],p['B']
    fresh=100*(b['fresh_ttft_s']['median']/a['fresh_ttft_s']['median']-1)
    lines.append(f"| {chunk} | {a['follow_ttft_s']['median']:.3f} ({a['follow_ttft_s']['min']:.3f}–{a['follow_ttft_s']['max']:.3f}) | {b['follow_ttft_s']['median']:.3f} ({b['follow_ttft_s']['min']:.3f}–{b['follow_ttft_s']['max']:.3f}) | {p['follow_ttft_reduction_percent']:.2f}% | {fresh:+.2f}% |")
oracle_n=sum(len(x['requests']) for x in speed['arms'].values())+sum(len(x['requests']) for x in quality['arms'].values())
rows=sum(x.get('teacher',{}).get('positions',0) for x in quality['arms'].values())
report=f'''# Checkpoint-grid su upstream 0.1.38 — 3 ottobre 2026

**Esito: gate numerico FAIL, nessuna nuova PR o promozione Daily.**
Velocità e recupero dei checkpoint sono misurati; la patch resta sperimentale.
Le risposte controllate sono corrette ma non certificano qualità generale.
La causa precisa delle differenze numeriche non è isolata: il diverso ordine
dei calcoli CPU/GPU e le partizioni sono ipotesi, non una diagnosi verificata.

Il prefill serve supera i checkpoint quando il chunk non divide l'intervallo16384.
Un prefisso comune32768 lascia nel riferimento checkpoint16896 (chunk1536) o18432
(chunk6144), costringendo a rileggere molti token. Il port della patch originale
imanu/Claude Opus5.5 taglia il chunk al checkpoint, aggiorna PLE asincrona e indice
dell'ultima riga. Layer-split conserva la geometria precedente. Tre soli file core.

Base upstream99f3dbd0b21d1401b3769e0c0d963913607f380b, esportazione non Git.
Baseline pristine e candidato differiscono soltanto per checkpoint-grid.
Due build CMake Release CUDA sm75, CUDA12.6/MSVC14.44, RTX2080Ti modificata22GB,
Ryzen5800X/96GBRAM. GGML1376file corrispondenti al pin upstream3cf03257.
Qwen3.8-Flash-Next IQ3_XXS native pack, PCIe0.28,
spec4/lookup0, adattamento0, cache fissa richiesta4000/effettiva5357,
KV262144 INT8 residente32768. Nessun carico artificiale.

## Tre coppie intercalate per configurazione

Ordine A1/B1, B2/A2, A3/B3. Ogni braccio riavvia il modello e usa lo stesso
warm-up estraneo al prefisso. Prompt fresh{speed['plan']['fresh_prompt_tokens']} e
follow{speed['plan']['follow_prompt_tokens']} token; prefisso comune{speed['plan']['common_tokens']}.
Output brevi completi con tre record
al10/50/90%; massimo128 token, greedy, ragionamento spento. Stato resettato per
il fresco e riusato per il follow. Caricamento iniziale escluso dal TTFT.

| Chunk | Follow A mediana s (min–max) | Follow B mediana s (min–max) | Riduzione TTFT | Costo TTFT fresco B/A |
|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

Tutti i campioni sono nel [confronto](corse_2080ti/20261003_checkpoint038/model-tests-r3/comparison.json).
Il vantaggio misura il lavoro evitato nel follow-up, non un kernel più veloce.
Non confrontare queste profondità33.8k con SOTA131k o250k. Nessuna promozione Daily.

## Correttezza e metodi upstream

Oracoli completi: {oracle_n} richieste; tempi e QA separati. Oracle tempi:
{comparison['oracle_pass']}; oracle QA: {comparison['qa_oracle_pass']}.
QA teacher-forced: {rows} righe complessive (64 per braccio, A/B/A a ogni chunk),
128 posizioni di riferimento ripetute, non384 problemi indipendenti.
stessi token di riferimento; la predizione viene scartata. Confronto logits interi,
KL, top1, NLL/PPL e ripetizione baseline; anche primo output fresh/follow con
KL <= max(0.01,3*repeat) e top1 identico. Gate locale dichiarato, non soglia
universale upstream. Gate finale: **{comparison['pass']}**.
Riferimenti ripetuti bitwise identici a entrambi i chunk; candidato top1 100%.
Chunk1536: KL medio0.002358, mediana0.000441, p990.032133;
PPL1.269900→1.276110, delta NLL0.004878 nats/token. Falliscono p99 e NLL con
intervallo approssimato a due blocchi, oltre al controllo first-output fresco.
Chunk6144: KL medio0.006070, mediana0.001562, p990.088491;
PPL1.272538→1.285683, delta NLL0.010277 nats/token. Falliscono mediana/p99/NLL
e controlli first-output. La soglia non viene allargata dopo i risultati.
Controllo solo upstream1536→6144: KL p990.008435 e delta NLL0.002075;
variabilità inferiore a quella del candidato. Non assolve la patch.
P99 è il99°percentile della divergenza KL tra le distribuzioni dei token:
non è una percentuale di risposte errate. Questi numeri descrivono il corpus
limitato, non una stima universale del peggioramento del modello.
Ulteriore crescita e divergenza oltre49k nel candidato verifica checkpoint dopo
un resume, con risposta completa e minimo49152 token riusati nel terzo ramo.

Il dump first-logits upstream0.1.38 esiste soltanto nella CLI. QA usa due binari
con identica strumentazione di lettura aggiunta al server, derivata dal readout
upstream ver.copy_logits. Patch QA separata dalla patch core; i tempi usano
eseguibili senza questa strumentazione. SHA e sorgenti conservati.
Il candidato finale aggiunge un bypass per --prompt-cache0 dopo le misure:
il percorso misurato con cache6 resta identico a livello di logica. La QA usa
la revisione finale e verifica anche cache0: logits bitwise {comparison['cache0_bitwise']}.
Le due revisioni di patch/binario hanno hash distinti e sono conservate;
le tre coppie di tempi non sono dichiarate misure del binario finale ricompilato.
Il primo tentativo model-tests-r2 resta fallito per dump mancante, dopo due risposte
corrette; non è contato nelle tre coppie. Un tentativo precedente prima di
avviare il modello è fallito per lettura vocab senza UTF8.
Le prime QA quality-tests e quality-tests-r2 sono invalide: il builder ha
conservato timestamp vecchi nel ripristino dei sorgenti e Ninja ha riusato
prefill.cpp candidato con generate.cpp baseline, ABI Prefill incompatibile.
Errori checkpoint e confronti numerici di quei binari non attestano regressioni
upstream o della patch. Tentativi e metriche invalide preservati solo localmente;
non inclusi nelle evidenze pubblicate. Ricompilati i file dipendenti
dall'header, verificato nel log, prima della QA finale.

La [guida community](https://github.com/Niko1221/Strata/blob/99f3dbd0b21d1401b3769e0c0d963913607f380b/docs/COMMUNITY_BENCHMARKS.md)
raccomanda almeno tre misure/configurazione e mediana/intervallo. Qui sono
pubblicate tutte e tre; non si dichiara replica dell'intero protocollo di release
multi-GPU/multi-quant. Suite server upstream:197 test,190pass/7skipped,95.1s;
dipendenza opzionale jsonschema assente, skip conservati nel log. Non dichiarare
197 test eseguiti con successo. Stato finale nei log del manifest.

Limiti: una scheda modificata22GB, una quantizzazione, un corpus retrieval e una
coda teacher fissa. Non provati stock11GB, multi-GPU, cancellazione del modello
durante un chunk, visione, cache elastica o qualità generale. Logits grezzi e
binari restano locali; runner originali richiedono adattare i percorsi Windows.
Motori propri chiusi, sorgenti shipping ripristinati; Daily verificato tramite SHA.

Patch e provenienza: [checkpoint-grid.patch](corse_2080ti/20261003_checkpoint038/checkpoint-grid.patch),
[manifest](corse_2080ti/20261003_checkpoint038/manifest.json).
'''
(root/'CHECKPOINT_GRID_0138_3_OTTOBRE.md').write_text(report,encoding='utf-8')
print('Saved',len(manifest),'evidence files; gate',comparison['pass'])
