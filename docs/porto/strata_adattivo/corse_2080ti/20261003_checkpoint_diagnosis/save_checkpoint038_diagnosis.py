"""Archive checked, bounded checkpoint diagnostics; omit raw logits and binaries."""
from pathlib import Path
import sys,json,hashlib,shutil,subprocess,time
BASE=Path(__file__).resolve().parent;R=BASE/'checkpoint038_20261003'
repo=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
sys.path[:0]=[r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages']
import psutil
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def git(*args): return subprocess.check_output(['git','-c','safe.directory='+str(repo),*args],cwd=repo,text=True).strip()
assert git('branch','--show-current')=='research/ds4-iq1-subbit-tier-planner'
print(git('status','--short','--branch'))
c=json.loads((R/'cache-replay-diagnosis/results.json').read_text(encoding='utf-8'))
a=json.loads((R/'aligned-chunk-control/results.json').read_text(encoding='utf-8'))
assert c['status']==a['status']=='completed'
assert all(x['request']['oracle_pass'] and x['request']['reused']==0 and x['first_cold_vs_hot']['bitwise'] and x['teacher_cold_history_vs_hot_history']['bitwise'] for x in c['arms'].values())
assert all(x['bitwise'] for x in a['comparison'].values())
assert all(x['bitwise'] for arm in a['versus_original_baseline6144'].values() for x in arm.values())
assert all(x['oracle_pass'] for arm in a['arms'].values() for x in arm['requests'])
processes=[{'pid':p.info['pid'],'name':p.info['name']} for p in psutil.process_iter(['pid','name']) if 'strata' in (p.info['name'] or '').lower() and (p.info['name'] or '').lower().endswith('.exe')]
assert not processes
daily=Path(r'D:\ds4_work\strata\Strata')
expected={
    'exe':(daily/'build-0136-daily/strata.exe','c35505ca79b790bd37ed7073fcadd399dd30d1b88e85bb99a6eb24a52d945d0a'),
    'config':(daily/'strata-2080ti-sota.json','ccffa537cdb264f99317948c1c6f41ffbc1e5ce370cafb1ca8c0ca717e77e112'),
    'server':(daily/'build-0136-daily/source/serve/server.py','73f90f417e9207811fdc47e5e6240f69bbde0f61ff027b9e0d8cb7b7bb2f4d81'),
    'launcher':(Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat'),'1103f2ffb7727aafe1754f964c1969a03c0838a659edfc5984b1f4afbd2bd2c4')}
checks={key:{'sha256':sha(path),'unchanged':sha(path)==want} for key,(path,want) in expected.items()}
assert all(x['unchanged'] for x in checks.values())
gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
state={'daily':checks,'ram_available_gib':psutil.virtual_memory().available/2**30,'gpu_free_mib_used_mib_util_pct':gpu,'strata_processes':processes,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
(R/'diagnosis-final-state.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
docs=repo/'docs/porto/strata_adattivo';dest=docs/'corse_2080ti/20261003_checkpoint_diagnosis';dest.mkdir(exist_ok=False)
for dirname in ('cache-replay-diagnosis','aligned-chunk-control'):
    for file in sorted((R/dirname).rglob('*')):
        if file.is_file() and file.name in ('results.json','engine.log'):
            target=dest/file.relative_to(R);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
for file in ('test_checkpoint038_cold.py','test_checkpoint038_aligned.py','save_checkpoint038_diagnosis.py'):
    shutil.copy2(BASE/file,dest/file)
shutil.copy2(R/'diagnosis-final-state.json',dest/'final-state.json')
manifest={'description':'Only completed diagnostics, no model/binary/raw logit uploads; original patch gate remains FAIL','files':[{'path':str(f.relative_to(dest)).replace('\\','/'),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(dest.rglob('*')) if f.is_file()]}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for f in manifest['files']: assert sha(dest/f['path'])==f['sha256']
def prompt_s(mode,prompt): return next(x['prompt_ms']/1000 for x in a['arms'][mode]['requests'] if x['name']==prompt)
report=f'''# Diagnosi checkpoint e configurazione senza tagli aggiuntivi — 3 ottobre 2026

**Il ripristino del checkpoint non introduce differenze nel caso provato.**
Il gate FAIL della patch originale con intervallo16384 rimane FAIL.
La cache elastica degli esperti era disattivata:5357 slot fissi in tutte le prove.

## Lettura da zero contro riuso

Quattro processi separati: upstream0.1.38 A e patch checkpoint-grid B, chunk1536
e6144. Stessi binari QA verificati del report precedente, SHA controllati prima
di ogni avvio. Stesso warm-up estraneo al prefisso; prompt follow33822 token
letto direttamente, senza precedente fresh, con reused0. Prompt-cache6 e
intervallo16384 conservati, KV262144/int8/resident32768, spec4, adattamento0.
Il confronto usa i logits completi della precedente QA valida quality-tests-r3:
primo output completo e64 posizioni teacher-forced dopo la risposta.
Le righe teacher riusano lo stato creato dalla lettura iniziale da zero;
non sono64 letture indipendenti da zero.

In tutti e quattro i confronti: **bitwise identico, KL0, NLL/PPL identiche,
top1 100%**. Quattro risposte complete corrette secondo l'oracolo dei tre codici.
Anche leggendo da zero, il confronto A/B riproduce le stesse divergenze del
precedente confronto con riuso: KL p990.032133 (1536) e0.088491 (6144).
Quindi la differenza nasce nel percorso prefill modificato prima del riuso;
non è evidenza di corruzione del checkpoint in questo workload.
Non è ancora isolato il singolo kernel o dimostrato che siano soli arrotondamenti.

## Configurazione conservativa: confini naturali

Provati A e B con `--prefill 6144 --prompt-cache-every 6144`, invece di16384.
Il salvataggio cade sul confine del blocco: non richiede tagli aggiuntivi.
Questa configurazione funziona anche sull'upstream senza la nostra patch.
Fresh33823/follow33822, stesso prefisso comune32769, stessi prompt e oracoli.
Il follow riusa30720 token, contro18432 del riferimento6144/intervallo16384,
e32768 della patch originale. Rimangono3102 token da leggere.

**A/B bitwise identici** sul primo output fresh, primo output follow e64
posizioni teacher-forced. Anche entrambi contro la baseline originale6144
con intervallo16384 sono bitwise identici, KL0/top1 100% sulle posizioni misurate.
Tutte le quattro risposte complete corrette.

Tempi di lettura prompt riportati dal motore, un solo campione per eseguibile,
con strumentazione QA; non TTFT misurato dal client:

| Eseguibile | Fresh lettura s | Follow lettura s | Follow riusato |
|---|---:|---:|---:|
| Upstream A | {prompt_s('A','fresh'):.3f} | {prompt_s('A','follow'):.3f} | 30720 |
| Candidato B | {prompt_s('B','fresh'):.3f} | {prompt_s('B','follow'):.3f} | 30720 |

Questi tempi sono diagnostici, non tre coppie, non una nuova SOTA o misura
di speedup del kernel. La soluzione verificata qui è una diversa frequenza dei
checkpoint che conserva la geometria di riferimento. Il costo di più copie
checkpoint e il comportamento a131k/250k vanno ancora misurati, così come la
combinazione con la cache elastica e il Daily0.1.36.

## Stato e limiti

Nessuna soglia numerica allargata, nessuna PR nuova o promozione Daily.
Nessuna build o modifica di kernel in questa diagnosi; gli eseguibili QA sono
gli stessi già validati. Una sola quantizzazione IQ3_XXS e un workload retrieval:
questi risultati non certificano la qualità generale né tutti i casi di ripristino.
Nessuna pressione artificiale o interazione con altre chat.
Motori propri chiusi; exe, server, JSON e launcher Daily invariati per SHA.
RAM disponibile finale {state['ram_available_gib']:.2f}GiB.

Evidenze e runner: [manifest](corse_2080ti/20261003_checkpoint_diagnosis/manifest.json).
Logits completi e binari conservati solo localmente.
'''
(docs/'CHECKPOINT_DIAGNOSI_3_OTTOBRE.md').write_text(report,encoding='utf-8')
handoff=docs/'HANDOFF.md';body=handoff.read_text(encoding='utf-8');head,sep,rest=body.partition('\n')
note='''
- **3 ottobre, diagnosi checkpoint conclusa:** A/B chunk1536 e6144, prompt33.8k
  letto da zero contro precedente riuso: logits bitwise in4/4 confronti,
  primo output+64posizioni/braccio. Differenza A/B già presente prima del riuso:
  percorso prefill modificato, singolo kernel/arrotondamenti non ancora isolati.
  Elastica disattivata,5357slot fissi. Configurazione alternativa senza tagli
  `--prefill6144 --prompt-cache-every6144`: upstream e patch bitwise tra loro
  e contro baseline6144 originale, fresh/follow+64posizioni,4risposte corrette;
  riuso30720 invece18432. Un campione temporale/braccio: niente SOTA o
  attestazione generale; ancora da provare131k/250k/elastica/Daily036.
  Gate patch originale16384 restaFAIL; Daily invariato, motori chiusi.
  [Dati e limiti](CHECKPOINT_DIAGNOSI_3_OTTOBRE.md).
'''
handoff.write_text(head+sep+note+rest,encoding='utf-8')
print(json.dumps({'evidence_files':len(manifest['files']),'report':str(docs/'CHECKPOINT_DIAGNOSI_3_OTTOBRE.md'),'state':state},indent=2))
