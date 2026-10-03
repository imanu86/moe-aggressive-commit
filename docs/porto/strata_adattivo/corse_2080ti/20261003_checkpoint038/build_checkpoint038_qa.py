"""Build common test-only server logits readout; restore shipping sources afterwards."""
from pathlib import Path
import os,subprocess,hashlib,json,shutil,difflib,sys
R=Path(__file__).resolve().parent/'checkpoint038_20261003'
files=['include/strata/prefill/prefill.hpp','src/prefill/prefill.cpp','src/program/generate.cpp']
if '--verify-existing' in sys.argv:
    meta=json.loads((R/'qa-build.json').read_text(encoding='utf-8'))
    added=[]
    for mode in ('A','B'):
        patch=(R/f'qa-readout-{mode}.patch').read_text(encoding='utf-8')
        added.append('\n'.join(line for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++')))
        assert hashlib.sha256((R/f'strata-qa-{mode}.exe').read_bytes()).hexdigest()==meta['qa_binaries'][mode]['sha256']
    assert added[0]==added[1]
    for rel in files:assert (R/'source'/rel).read_bytes()==(R/'shipping-candidate'/rel).read_bytes()
    assert (R/'build/strata.exe').read_bytes()==(R/'strata-candidate.exe').read_bytes()
    meta.update(common_readout_sha256=hashlib.sha256(added[0].encode()).hexdigest(),preparation_note='Both compiles succeeded; original whole-diff equality assertion failed because hunk positions differ by 3 lines. Identical added readout lines verified; shipping source and executable restored.')
    (R/'qa-build.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print('QA binaries, common added readout and shipping restore verified')
    raise SystemExit(0)
rebuild='--rebuild-existing' in sys.argv
saved=R/'shipping-candidate'
candidate=R/'strata-candidate.exe'
if rebuild:
    recovery=R/'invalid-qa-build';recovery.mkdir(exist_ok=False)
    for name in ['qa-build.json','strata-qa-A.exe','strata-qa-B.exe','build-qa-A.log','build-qa-B.log','qa-readout-A.patch','qa-readout-B.patch']:
        shutil.copy2(R/name,recovery/name)
else:
    saved.mkdir(exist_ok=False)
    for rel in files:
        dst=saved/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'source'/rel,dst)
    assert not candidate.exists();shutil.copy2(R/'build/strata.exe',candidate)
VC=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
env=dict(os.environ);env.pop('STRATA_API_KEY',None)
init=subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',capture_output=True,text=True,encoding='cp1252',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW)
assert init.returncode==0
for line in init.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k,v=line.split('=',1);env[k]=v
env.pop('STRATA_API_KEY',None)
needle='                first_window = false;\n                bool eos = false;'
hook='''                // Test-only readout, identical in both QA binaries; excluded from shipping patch.
                if (first_window) {
                    if (const char* fl = std::getenv("STRATA_TEST_FIRST_LOGITS")) {
                        std::vector<float> row((size_t) ver.vocab());
                        std::FILE* f = ver.copy_logits(0, row.data()) ? std::fopen(fl, "wb") : nullptr;
                        if (f == nullptr || std::fwrite(row.data(), sizeof(float), row.size(), f) != row.size())
                            std::fprintf(stderr, "strata test: cannot write first logits %s\\n", fl);
                        if (f) std::fclose(f);
                    }
                }
'''
meta={'shipping_patch_separate':True,'qa_binaries':{}}
try:
    for mode,tree in [('A',R/'original'),('B',saved)]:
        for rel in files:
            target=R/'source'/rel;shutil.copy2(tree/rel,target);os.utime(target,None)
        path=R/'source/src/program/generate.cpp';before=path.read_text(encoding='utf-8');assert before.count(needle)==1
        after=before.replace(needle,hook+needle);path.write_text(after,encoding='utf-8',newline='\n')
        diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/src/program/generate.cpp',tofile='b/src/program/generate.cpp'))
        (R/f'qa-readout-{mode}.patch').write_text(diff,encoding='utf-8',newline='\n')
        print('BUILD QA',mode,flush=True)
        with (R/f'build-qa-{mode}.log').open('w',encoding='utf-8') as log:
            p=subprocess.run([str(CM/'CMake/bin/cmake.exe'),'--build',str(R/'build'),'--parallel','2','--target','strata'],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW)
        assert p.returncode==0,f'QA build {mode} failed'
        log_text=(R/f'build-qa-{mode}.log').read_text(encoding='utf-8',errors='replace')
        assert 'prefill.cpp.obj' in log_text and 'generate.cpp.obj' in log_text,'Both translation units must rebuild after ABI changes'
        exe=R/f'strata-qa-{mode}.exe';assert rebuild or not exe.exists();shutil.copy2(R/'build/strata.exe',exe)
        meta['qa_binaries'][mode]={'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'readout_patch_sha256':hashlib.sha256(diff.encode()).hexdigest(),'both_translation_units_rebuilt':True}
        print('BUILT QA',mode,flush=True)
    def added(mode):
        return '\n'.join(line for line in (R/f'qa-readout-{mode}.patch').read_text(encoding='utf-8').splitlines() if line.startswith('+') and not line.startswith('+++'))
    assert added('A')==added('B')
    meta['common_readout_sha256']=hashlib.sha256(added('A').encode()).hexdigest()
finally:
    for rel in files:
        target=R/'source'/rel;shutil.copy2(saved/rel,target);os.utime(target,None)
    shutil.copy2(candidate,R/'build/strata.exe')
    (R/'qa-build.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
