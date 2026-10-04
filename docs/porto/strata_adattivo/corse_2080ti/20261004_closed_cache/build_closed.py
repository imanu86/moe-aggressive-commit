"""Bounded, explicit CPU tests or engine build; immutable output directory for each invocation."""
import argparse, hashlib, json, os
from pathlib import Path
import shutil, subprocess, time
import psutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'20261004_neuron_cache'))
from run_capture import PREFIX

F=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
B=F/'build-sm75-547-msvc'
L=Path(__file__).resolve().parent
CM=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe')
VC=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat')
CUDA=Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a): return subprocess.check_output(['git',*a],cwd=F,text=True).strip()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['cpu','engine'],required=True);ap.add_argument('--name',required=True);ap.add_argument('--run',action='store_true');a=ap.parse_args()
    assert a.name.replace('-','').replace('_','').isalnum()
    assert git('branch','--show-current')=='main'
    print(git('status','--short','--branch'),flush=True)
    paths=set(git('ls-files','src','include','CMakeLists.txt','serve').splitlines())
    paths.update(git('ls-files','--others','--exclude-standard','src','include').splitlines());paths.discard('')
    hashes={p:sha(F/p) for p in sorted(paths)}
    competing, idle=PREFIX.check_competing_processes()
    assert not competing, competing
    out=L/a.name; assert not out.exists()
    if not a.run: print(json.dumps({'ready':True,'stage':a.stage,'source_count':len(hashes),'output':str(out)}));return
    out.mkdir()
    env={k.upper():v for k,v in os.environ.items() if not k.upper().startswith('STRATA_')}
    setup=subprocess.run(f'cmd.exe /d /s /c "call "{VC}" >nul && set"',capture_output=True,text=True,encoding='cp1252',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW,timeout=60)
    assert setup.returncode==0
    for line in setup.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            k,v=line.split('=',1);env[k.upper()]=v
    env['PATH']=str(CUDA/'bin')+os.pathsep+env.get('PATH','')
    commands=[[str(CM),'-S',str(F),'-B',str(B),'-DSTRATA_BUILD_CONVERSATION_TESTS=ON','-DSTRATA_BUILD_NEURON_REPLAY=ON','-DSTRATA_BUILD_CLOSED_PROBE=ON']]
    targets=['prefix_cache_file_test','prefix_cache_portable_test'] if a.stage=='cpu' else ['strata','closed_router_parity']
    commands.append([str(CM),'--build',str(B),'--parallel','2','--target',*targets])
    if a.stage=='cpu': commands.append([str(CM.with_name('ctest.exe')),'--test-dir',str(B),'-R','^prefix_cache_(file|portable)_test$','--output-on-failure'])
    state={'status':'running','stage':a.stage,'source_commit':git('rev-parse','HEAD'),'source_files':hashes,'commands':commands,'cleanup_verified':False}
    started=time.monotonic();owned={}
    try:
        with (out/'build.log').open('wb') as log:
            for command in commands:
                proc=subprocess.Popen(command,cwd=L,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                parent=psutil.Process(proc.pid);owned[proc.pid]=parent.create_time()
                while proc.poll() is None:
                    try:
                        for child in parent.children(recursive=True):owned[child.pid]=child.create_time()
                    except psutil.Error:pass
                    if time.monotonic()-started>600:raise TimeoutError('Build deadline')
                    time.sleep(.5)
                if proc.returncode:raise RuntimeError(f'Command exit {proc.returncode}; inspect build.log')
        assert hashes=={p:sha(F/p) for p in hashes},'Sources changed during build'
        if a.stage=='engine':
            shutil.copy2(B/'strata.exe',out/'strata.exe');state['executable_sha256']=sha(out/'strata.exe')
            shutil.copy2(B/'closed_router_parity.exe',out/'closed_router_parity.exe');state['parity_sha256']=sha(out/'closed_router_parity.exe')
        state['status']='completed'
    except BaseException as e:
        state.update(status='failed',error=repr(e));raise
    finally:
        cleanup_errors=[]
        for pid,born in reversed(list(owned.items())):
            try:
                p=psutil.Process(pid)
                if abs(p.create_time()-born)<.02 and p.is_running():p.kill();p.wait(timeout=5)
            except psutil.NoSuchProcess:pass
            except psutil.Error as e:cleanup_errors.append({'pid':pid,'error':repr(e)})
        remaining=[]
        for pid,born in owned.items():
            try:
                p=psutil.Process(pid)
                if abs(p.create_time()-born)<.02 and p.is_running():remaining.append(pid)
            except psutil.NoSuchProcess:pass
        state.update(cleanup_verified=not remaining,cleanup_errors=cleanup_errors,remaining_owned=remaining,elapsed_s=time.monotonic()-started)
        if remaining:state.update(status='failed',error='Build descendants remain alive')
        (out/'result.json').write_bytes((json.dumps(state,indent=2)+'\n').encode())
    print('FINISHED',state['status'],round(state['elapsed_s'],2),flush=True)
if __name__=='__main__':main()
