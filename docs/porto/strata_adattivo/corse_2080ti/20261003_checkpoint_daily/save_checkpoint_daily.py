"""Save all completed measurements honestly, including failed local gates."""
from checkpoint_daily_common import *
import shutil,subprocess,datetime,statistics,math
OUT=BASE/'checkpoint_daily_20261003'
MAIN=OUT/'paired-r2';FULL=OUT/'full-qa'
r=json.loads((MAIN/'results.json').read_text(encoding='utf-8'))
c=json.loads((MAIN/'comparison.json').read_text(encoding='utf-8'))
q=json.loads((FULL/'results.json').read_text(encoding='utf-8'))
qc=json.loads((FULL/'comparison.json').read_text(encoding='utf-8'))
assert r['status']==c['status']==q['status']==qc['status']=='completed'
assert len(r['arms'])==12 and len(q['arms'])==6
ensure_free()
raw=[]
for directory,run,full in [(MAIN,r,False),(FULL,q,True)]:
    for name,arm in run['arms'].items():
        for corpus,meta in arm['teacher'].items():
            file=directory/name/(f'{corpus}.logits.bin' if full else f'teacher-{corpus}.bin')
            assert sha(file)==meta['sha256'],file
            if full:V.check_dump(file,meta['rows'],len(TOKENS))
            raw.append({'path':str(file.relative_to(OUT)).replace('\\','/'),'bytes':file.stat().st_size,'sha256':meta['sha256']})
        for file in sorted((directory/name).glob('*-first.f32')):
            row=np.fromfile(file,dtype='<f4');assert row.size==len(TOKENS) and np.isfinite(row).all()
            raw.append({'path':str(file.relative_to(OUT)).replace('\\','/'),'bytes':file.stat().st_size,'sha256':sha(file)})
write(OUT/'raw-private-manifest.json',{'description':'Raw logits retained privately, never uploaded','files':raw})
checks={
 'exe':(Path(CFG['exe']),'c35505ca79b790bd37ed7073fcadd399dd30d1b88e85bb99a6eb24a52d945d0a'),
 'config':(DAILY/'strata-2080ti-sota.json','ccffa537cdb264f99317948c1c6f41ffbc1e5ce370cafb1ca8c0ca717e77e112'),
 'server':(SOURCE/'serve/server.py','73f90f417e9207811fdc47e5e6240f69bbde0f61ff027b9e0d8cb7b7bb2f4d81'),
 'launcher':(Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat'),'1103f2ffb7727aafe1754f964c1969a03c0838a659edfc5984b1f4afbd2bd2c4'),
 'profile':(Path(CFG['args'][CFG['args'].index('--expert-profile')+1]),'8f59b4aa8873209dff11c11e37bcda9529a1335b724a1afeea37bf6388975baf')}
state={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ram_available_gib':psutil.virtual_memory().available/2**30,'daily':{k:{'sha256':sha(p),'matches_prior_record':sha(p)==want} for k,(p,want) in checks.items()},'strata_processes':[]}
assert all(state['daily'][k]['matches_prior_record'] for k in ('exe','config','server','launcher'))
state['gpu_free_mib_used_mib_util_pct']=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
write(OUT/'final-state.json',state)
repo=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
def git(*args):return subprocess.check_output(['git','-c','safe.directory='+str(repo),*args],cwd=repo,text=True).strip()
assert git('branch','--show-current')=='research/ds4-iq1-subbit-tier-planner';print(git('status','--short','--branch'))
area=repo/'docs/porto/strata_adattivo';dest=area/'corse_2080ti/20261003_checkpoint_daily';dest.mkdir(exist_ok=False)
for directory in ('probe','paired','paired-r2','full-qa'):
    for file in sorted((OUT/directory).rglob('*')):
        if file.is_file() and 'cuda-cache' not in file.parts and file.suffix in ('.json','.jsonl','.log','.txt') and file.name!='comparison-partial.json':
            target=dest/file.relative_to(OUT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
for file in ('final-state.json','raw-private-manifest.json'):shutil.copy2(OUT/file,dest/file)
for file in ('checkpoint_daily_common.py','probe_checkpoint_daily.py','test_checkpoint_daily.py','analyze_checkpoint_daily.py','test_checkpoint_daily_full_qa.py','analyze_checkpoint_daily_full_qa.py','save_checkpoint_daily.py'):
    shutil.copy2(BASE/file,dest/file)
shutil.copy2(Path(V.__file__),dest/'validate_model_policy.py')
manifest={'description':'Verified completed runs plus labelled startup-only failure; no binaries/models/raw logits','files':[{'path':str(f.relative_to(dest)).replace('\\','/'),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(dest.rglob('*')) if f.is_file()]}
write(dest/'manifest.json',manifest)
for item in manifest['files']:assert sha(dest/item['path'])==item['sha256']
def median(depth,mode,request,metric):return c['depths'][str(depth)]['performance'][mode][request][metric]['median']
rows=[];quality_rows=[];failed_checks=[]
for depth,info in c['depths'].items():
    for corpus,data in info['quality'].items():
        for check,passed in data['gate']['checks'].items():
            if not passed:failed_checks.append(f'- {depth} token, corpus `{corpus}`: `{check}`.')
    for request,data in info['first_logits'].items():
        if not data['pass']:failed_checks.append(f'- {depth} token, primo output `{request}`: gate KL/top1.')
short_failures='\n'.join(failed_checks) or '- Nessun gate breve fallito.'
full_failures=[]
for depth,info in qc['depths'].items():
    for name,data in list(info['corpora'].items())+[('aggregato',info['aggregate'])]:
        failed=[k for k,v in data['gate']['checks'].items() if not v]
        if failed:full_failures.append(f'- {depth} token, `{name}`: '+', '.join(failed)+'.')
    for request,data in info['first_logits'].items():
        if not data['pass']:full_failures.append(f"- {depth} token, primo output `{request}`: KL {data['candidate']['kl']:.6f}, limite {data['kl_limit']:.6f}; top1 invariato.")
full_failure_text='\n'.join(full_failures) or '- Nessun gate esteso fallito.'
for depth in r['plan']['contexts']:
    rows.append(f"| {depth} | {median(depth,'A','fresh','ttft_s'):.3f} / {median(depth,'B','fresh','ttft_s'):.3f} | {median(depth,'A','branch','ttft_s'):.3f} / {median(depth,'B','branch','ttft_s'):.3f} | {median(depth,'A','conversation','ttft_s'):.3f} / {median(depth,'B','conversation','ttft_s'):.3f} | {median(depth,'A','long_decode','decode_tps'):.3f} / {median(depth,'B','long_decode','decode_tps'):.3f} |")
    for corpus,info in qc['depths'][str(depth)]['corpora'].items():
        ca,ref=info['candidate'],info['reference_repeat']
        quality_rows.append(f"| {depth} | {corpus} | {ca['top1_agreement_pct']:.3f}% / {ref['top1_agreement_pct']:.3f}% | {ca['kl_p99']:.6f} | {ca['ppl_reference']:.6f} / {ca['ppl_candidate']:.6f} | {info['gate']['pass']} |")
overall=bool(c['overall_pass'] and qc['overall_pass'])
oracle_count=sum('oracle_pass' in x for arm in r['arms'].values() for x in arm['requests'])
oracle_pass=sum(bool(x.get('oracle_pass')) for arm in r['arms'].values() for x in arm['requests'])
full_oracle_count=sum(len(arm['requests']) for arm in q['arms'].values());full_oracle_pass=sum(bool(x['oracle_pass']) for arm in q['arms'].values() for x in arm['requests'])
report=f'''# Checkpoint sul Daily elastico — 3 ottobre 2026

**Gate breve: {c['overall_pass']}. QA estesa: {qc['overall_pass']}.
Tutti i gate numerici dichiarati superati: {overall}. Nessuna promozione Daily.**
Misure complete sullo stesso eseguibile operativo 0.1.36, SHA c35505ca.
Non è una nuova patch: cambia soltanto `--prompt-cache-every` da 16384 a 8192.
Il Daily contiene già l'allineamento del fork e sceglie blocchi 8192 in auto:
la prova 6144/6144 del precedente laboratorio non è la configurazione operativa.

## Metodo e configurazione

RTX 2080 Ti modificata a 22 GB, Ryzen 5800X, 96 GB RAM, IQ3_XXS. Stesso pack/profilo,
`--prefill auto --expert-cache auto --elastic`, KV 262144 INT8/residente 32768.
Spec richiesto 4; capacità runtime 6, MTP massimo 4, lookup 3, come nel Daily.
Greedy e ragionamento disattivato nei prompt della prova. Nessun carico di
pressione artificiale o interazione con altre chat. Tutti i ridimensionamenti
dell'elastica sono naturali e registrati; gli slot iniziali non sono fissati.
Tre coppie per profondità, ordine A1/B1, B2/A2, A3/B3; caricamento e warm-up
esclusi dai tempi. Stessa diagnostica first-logits presente in ogni braccio:
il suo costo è incluso nel TTFT, non sono misure SOTA non strumentate.

Prompt fresh/branch 131072 o 250000 token; branch con appendice diversa dello
stesso archivio. Segue un vero turno serializzato, con la risposta precedente
e circa 1000 nuovi token. Il benchmark lungo usa massimo 1024 token e può
terminare per budget: non conta come risposta completa corretta.
Input decode lungo 132260/251188 token, non confondere con capienza KV.
Le guide generate differiscono anche tra due baseline: le velocità di decode
descrivono queste generazioni e non isolano il costo dello stesso testo.

## Tempi mediani A / B

| Contesto iniziale | Fresh TTFT s | Branch TTFT s | Turno successivo TTFT s | Decode lungo t/s |
|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

I tre campioni, min/max e differenze accoppiate sono nel confronto JSON.
A 131k il branch riusa 114688/122880 token; a 250k entrambe le configurazioni
riusano 245760. Il vantaggio è lavoro evitato dove il prefisso cade tra i due
checkpoint, non un kernel più veloce né un'accelerazione di ogni conversazione.

## Risposte e QA

Oracoli del banco: {oracle_pass}/{oracle_count}; QA estesa: {full_oracle_pass}/{full_oracle_count}.
Due fixture retrieval con tre record al 10/50/90%, ripetute: non altrettanti
problemi indipendenti o una stima dell'accuratezza generale.
Il controllo breve valuta 64 posizioni per corpus code/doc/chat e per braccio,
dopo conversazione e guide. Gate originale conservato; le guide differiscono
anche tra baseline, quindi cache/adattamento vedono storie diverse prima dei
test teacher-forced. Questo limite non riguarda il controllo del primo output
del branch, che avviene prima delle guide. Il gate breve non è superato:

{short_failures}

Il fallimento di vicinanza numerica resta tale anche se gli oracoli passano;
non dimostra da solo un errore nella risposta o una peggiore perplessità.

La QA estesa confronta A/B/A prima di conversazioni e guide, con input fissi:
corpora 512/1024/1024 token, logits completi, 2557 posizioni note per braccio,
ultimo target sconosciuto escluso. Sono le lunghezze del metodo di confronto
usato dal repository; testi locali congelati, non copia del corpus ufficiale.
Stessa politica locale KL/NLL/top1, baseline ripetuta e blocchi 32 token.
Non è una soglia universale upstream. Tutti i risultati brevi restano registrati;
nessuna soglia è stata allargata per trasformare un fallimento in successo.

| Contesto | Corpus | Top1 A/B / A/A | KL p99 A/B | PPL A / B | Gate corpus |
|---:|---|---:|---:|---:|---:|
'''+ '\n'.join(quality_rows)+f'''

Gate completi, intervalli approssimati della NLL, controlli primo output e
baseline in `paired-r2/comparison.json` e `full-qa/comparison.json`.
Fallimenti della QA estesa:

{full_failure_text}

La variazione del corpus documentale a250k è presente anche senza guide
generate prima della misura. La sola divergenza delle guide non spiega quindi
tutti i fallimenti. La causa resta da isolare: questi dati non attestano la
configurazione8192 per una promozione operativa.
I limiti sono una sola scheda, un pack, due retrieval e tre testi: niente
certificazione della qualità generale o di ogni livello di pressione VRAM.

## Stato operativo e pubblicazione

Tutti i motori propri chiusi. Daily exe/config/server/launcher invariati per SHA;
RAM libera finale {state['ram_available_gib']:.2f} GiB. Nessuna nuova PR o workflow.
Il primo avvio fu rifiutato prima del warm-up: 759 MiB liberi contro una riserva richiesta di 800 MiB.
Conservato come tentativo startup-only; riserva successiva di 500 MiB segue il margine
del Daily elastico e non modifica alcuna soglia di qualità.

Report ed evidenze salvati localmente sul branch research autorizzato;
staging/push non confermati per blocco su `.git/index.lock`. Non attribuire
questi risultati alla versione online senza il nuovo commit pubblicato.

Evidenze: [manifest](corse_2080ti/20261003_checkpoint_daily/manifest.json).
Raw logits e binari esclusi dalla pubblicazione; hash e dimensioni conservati.
'''
(area/'CHECKPOINT_DAILY_ELASTICO_3_OTTOBRE.md').write_text(report,encoding='utf-8')
handoff=area/'HANDOFF.md';body=handoff.read_text(encoding='utf-8');head,sep,rest=body.partition('\n')
note=f'''\n- **3 ottobre, misure Daily elastico concluse:** stesso exe0136 c35505ca,
  auto/elastic/KV262144, confronto checkpoint16384/8192,3coppie a131072 e250000.
  Gate breve{c['overall_pass']}, QA estesa A/B/A2557posizioni/braccio{qc['overall_pass']}.
  Oracoli{oracle_pass}/{oracle_count} e{full_oracle_pass}/{full_oracle_count}, fixture ripetute;
  niente qualità generale/SOTA. Tutti i fallimenti e baseline conservati.
  Daily invariato perSHA, motori chiusi. Pubblicazione locale/pendingindex.lock.
  [Dati e limiti](CHECKPOINT_DAILY_ELASTICO_3_OTTOBRE.md).
'''
handoff.write_text(head+sep+note+rest,encoding='utf-8')
backup=OUT/'publication-pending';backup.mkdir(exist_ok=False)
for file in ('CHECKPOINT_DAILY_ELASTICO_3_OTTOBRE.md','HANDOFF.md'):shutil.copy2(area/file,backup/file)
print(json.dumps({'report':str(area/'CHECKPOINT_DAILY_ELASTICO_3_OTTOBRE.md'),'all_declared_gates_pass':overall,'evidence_files':len(manifest['files']),'raw_files_verified':len(raw),'final_state':state},indent=2))
