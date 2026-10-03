from pathlib import Path
import os,sys,json,subprocess,re,time
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';sys.path.insert(0,r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages');import psutil
assert not any((p.info['name'] or '').lower()=='strata.exe' or (p.info['name'] or '').lower().startswith('strata-') for p in psutil.process_iter(['name']))
env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')};env['PATH']=r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'+os.pathsep+env.get('PATH','')
OUT=R/'topk-bench-r1';OUT.mkdir(exist_ok=False);rows=[]
for depth,nq,counted in [(131072,256,1),(262144,256,1),(131072,4,0),(262144,4,0)]:
    for pair in range(3):
        for arm in ('base','wide') if pair!=1 else ('wide','base'):
            exe=R/('topk-base-build/qsa_topk_parity.exe' if arm=='base' else 'build/qsa_topk_parity.exe');cmd=[str(exe),str(depth),str(nq),'30','262144',str(counted)]
            p=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stdout+p.stderr
            out=p.stdout+p.stderr;(OUT/f'{depth}-{nq}-{pair}-{arm}.log').write_text(out,encoding='utf-8');m=re.search(r'reference ([\d.]+) ms, dispatched ([\d.]+) ms',out);assert m
            rows.append({'context':depth,'queries':nq,'counted':bool(counted),'pair':pair,'arm':arm,'reference_ms':float(m[1]),'dispatched_ms':float(m[2]),'pass':out.startswith('PASS')});print(depth,nq,pair,arm,m[2],flush=True)
(OUT/'results.json').write_text(json.dumps({'scope':'real SM75 baseline dispatch vs PR603; same driver/inputs; capacity262144; no env forced reference, no artificial pressure; tiny kernel benchmark does not establish model speedup','rows':rows},indent=2))
