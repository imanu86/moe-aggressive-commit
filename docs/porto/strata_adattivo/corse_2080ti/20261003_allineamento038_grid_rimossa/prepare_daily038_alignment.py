from pathlib import Path
import subprocess,json,hashlib,shutil,time,os,re,difflib,sys
BASE=Path(__file__).resolve().parent;R=BASE/'daily038_alignment_20261003';R.mkdir(exist_ok='--resume' in sys.argv)
P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti');D=Path(r'D:\ds4_work\strata\Strata');BAT=Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
OLD='2c394674ed933a817741506b0b35e370f4d45c21';UP='99f3dbd0b21d1401b3769e0c0d963913607f380b';B036='36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca'
def git(root,*args):return subprocess.check_output(['git',*args],cwd=root)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for root in (P,D):
    assert git(root,'branch','--show-current').strip()==b'main';print(git(root,'status','--short','--branch').decode(),flush=True)
    assert git(root,'rev-parse','HEAD').decode().strip()==OLD
    assert not git(root,'diff','--name-only') and not git(root,'diff','--cached','--name-only')
if '--resume' not in sys.argv:
    backup=Path(r'D:\ds4_work\strata\ripristini')/time.strftime('%Y%m%d_%H%M%S_allineamento038');backup.mkdir(exist_ok=False,parents=True)
    git(P,'bundle','create',str(backup/'fork-main-before.bundle'),'--all');git(D,'bundle','create',str(backup/'daily-main-before.bundle'),'--all')
    for p in (D/'strata-2080ti-sota.json',BAT,P/'docs/sm75/source-manifest.json',P/'docs/sm75/validation.json'):shutil.copyfile(p,backup/p.name)
    untracked=git(D,'ls-files','--others','--exclude-standard').decode().splitlines()
    for name in untracked:
        src=D/name;dest=backup/'untracked'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if src.suffix.lower()=='.dmp':os.link(src,dest)
        else:shutil.copyfile(src,dest)
    recovery={'backup':str(backup),'old_head':OLD,'upstream':UP,'untracked_preserved':untracked,'daily_exe_sha256':sha(D/'build-0136-daily/strata.exe'),'cfg_sha256':sha(D/'strata-2080ti-sota.json'),'launcher_sha256':sha(BAT)}
    (R/'recovery.json').write_text(json.dumps(recovery,indent=2));print('RECOVERY',backup,flush=True)
S=R/'source'
if not S.exists():
    shutil.copytree(BASE/'elastic038_20261003/source',S)
    patch=BASE/'checkpoint-tail038_20261003/checkpoint-tail.patch'
    subprocess.run(['git','-c','core.autocrlf=false','apply',str(patch)],cwd=S,check=True)
paths=['include/strata/core/tc_sm75.hpp','include/strata/kernels/cpu/pool.hpp','src/kernels/cpu/pool.cpp','src/kernels/cpu/pool_quant_parity.cpp','src/kernels/native_expert_bench.cpp','include/strata/prefill/kernels.hpp','src/prefill/kernels.cu','src/prefill/prefill.cpp','src/kernels/cuda/dequant_bf16.cu']
TMP=R/'merge';TMP.mkdir(exist_ok=True);conflicts=[]
for name in paths:
    local=(P/name).read_bytes().replace(b'\r\n',b'\n');initial=BASE/'elastic038_20261003/source'/name;incoming=initial.read_bytes().replace(b'\r\n',b'\n') if initial.exists() else b''
    base=subprocess.run(['git','show',B036+':'+name],cwd=P,capture_output=True).stdout.replace(b'\r\n',b'\n')
    if name=='src/prefill/prefill.cpp':
        start=local.index(b'    // this chunk\'s length: the plan\'s chunk');end=local.index(b'    auto ple_gather',start)
        # Restore the upstream chunk length; the rejected grid is not ported.
        local=local[:start]+local[end:]
        local=local.replace(b', &chunk_len]',b']').replace(b'chunk_len(c0)',b'std::min(m.T, n - c0)')
    if not base:
        assert not incoming,name;out=local
    else:
        for i,data in enumerate((local,base,incoming)):(TMP/f'{i}.txt').write_bytes(data)
        p=subprocess.run(['git','merge-file','-p','--diff3','-L','daily036-sm75','-L','upstream036','-L','upstream038-elastic',*[str(TMP/f'{i}.txt') for i in range(3)]],capture_output=True)
        assert 0<=p.returncode<=127,name
        if p.returncode:conflicts.append(name)
        out=p.stdout
    dest=S/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(out)
# Port only SM75 accounting from generate.cpp. The pending-fill ordering is
# already upstream038; original elastic and grid hunks must not be transplanted.
raw=git(P,'diff',B036,OLD,'--','src/program/generate.cpp').decode('utf-8')
parts=re.split(r'(?=^@@ )',raw,flags=re.M);chosen=[h for h in parts[1:] if 'sm75_prompt_extra_bytes' in h or '+#include "strata/core/tc_sm75.hpp"' in h]
assert len(chosen)==5,len(chosen)
selected='--- a/src/program/generate.cpp\n+++ b/src/program/generate.cpp\n'+''.join(chosen)
(R/'sm75-budget.patch').write_text(selected,encoding='utf-8',newline='\n')
q=subprocess.run(['git','-c','core.autocrlf=false','apply','--reject',str(R/'sm75-budget.patch')],cwd=S,capture_output=True,text=True)
(R/'budget-apply.log').write_text(q.stdout+q.stderr);assert q.returncode==0,q.stderr
# Keep local CPU diagnostics/build targets, avoiding duplicate upstream top-k.
p=S/'CMakeLists.txt';s=p.read_text(encoding='utf-8')
needle='  set(_strata_mmq_types';at=s.index(needle)
s=s[:at]+'''  option(STRATA_PARITY_POOL_QUANT "Build the native expert pool quantization parity check" OFF)
  if(STRATA_BUILD_TESTS OR STRATA_PARITY_POOL_QUANT)
    add_executable(pool_quant_parity src/kernels/cpu/pool_quant_parity.cpp)
    target_link_libraries(pool_quant_parity PRIVATE strata_kernels_cpu)
  endif()
'''+s[at:]
needle='  # #296\'s real-weight checks';at=s.index(needle)
s=s[:at]+'''  if(STRATA_ENABLE_CUDA AND STRATA_BUILD_TESTS)
    add_executable(native_expert_bench src/kernels/native_expert_bench.cpp)
    target_include_directories(native_expert_bench PRIVATE ${_strata_gpu_include_directories})
    target_link_libraries(native_expert_bench PRIVATE strata_kernels strata_kernels_cpu strata_artifact ${_strata_gpu_runtime_target})
  endif()
'''+s[at:];p.write_text(s,encoding='utf-8',newline='\n')
assert 'align_every' not in (S/'include/strata/prefill/prefill.hpp').read_text()
assert 'align_every' not in (S/'src/program/generate.cpp').read_text()
assert 'align_every' not in (S/'src/prefill/prefill.cpp').read_text()
(R/'preparation.json').write_text(json.dumps({'upstream':UP,'old_daily':OLD,'ported_sm75_paths':paths,'conflicts':conflicts,'grid_removed':True,'elastic':'final isolated validated038 port','checkpoint_tail':'PR614 tested source','no_workflows':not any((S/'.github/workflows').glob('*'))},indent=2))
print('PREPARED',S,'CONFLICTS',conflicts,flush=True)
