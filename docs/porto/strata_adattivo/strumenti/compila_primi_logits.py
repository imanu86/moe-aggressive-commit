"""Diagnostica primi logits adattata da upstream ad48d5c5ca anche al server persistente.

Due oggetti CPU ricompilati per variante, nessun kernel CUDA ricompilato.
La sorgente di riferimento e le librerie originali restano intatte.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from compila_0131 import BASE, CUDA, VC, NINJA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--variant', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    base, variant, out = a.base.resolve(strict=True), a.variant.resolve(strict=True), a.out.resolve()
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import psutil
    if any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name'])):
        raise RuntimeError('Motore attivo: compilazione rinviata')
    out.mkdir(parents=True, exist_ok=False)
    source, build = out/'source', base/'build'
    shutil.copytree(variant/'source', source)
    changes = {}
    name = 'include/strata/core/verify.hpp'
    text = (source/name).read_text(encoding='utf-8')
    anchor = '    bool run(int T, const int32_t* tokens, int64_t pos0, PoolMultiFn pool, void* user, int32_t* out, std::string& err);'
    assert text.count(anchor) == 1
    changes[name] = text.replace(anchor, anchor+'\n    bool copy_logits(int t, float* host) const;\n    int64_t vocab() const { return next_ ? next_->vocab() : n_vocab_; }')
    name = 'src/core/verify.cpp'
    text = (source/name).read_text(encoding='utf-8')
    anchor = '}  // namespace strata::core'
    assert text.count(anchor) == 1
    code = '''bool Verifier::copy_logits(int t, float* host) const {
    if (next_ != nullptr) return next_->copy_logits(t, host);
    if (head_logits_ == nullptr || host == nullptr || t != 0 || n_vocab_ <= 0) return false;
    return cudaMemcpy(host, head_logits_, (size_t) n_vocab_ * sizeof(float), cudaMemcpyDeviceToHost) == cudaSuccess;
}

'''
    changes[name] = text.replace(anchor, code+anchor)
    name = 'src/program/generate.cpp'
    text = (source/name).read_text(encoding='utf-8')
    assert text.count('first_window = false;') == 2
    code = '''if (first_window) {
                    if (const char* prefix = std::getenv("STRATA_DUMP_FIRST_LOGITS")) {
                        const std::string path = std::string(prefix) + ".pos" + std::to_string(p) + ".f32";
                        std::vector<float> row((size_t) ver.vocab());
                        std::FILE* f = ver.copy_logits(0, row.data()) ? std::fopen(path.c_str(), "wb") : nullptr;
                        if (f == nullptr || std::fwrite(row.data(), sizeof(float), row.size(), f) != row.size())
                            std::fprintf(stderr, "strata generate: cannot dump first logits %s\\n", path.c_str());
                        if (f) std::fclose(f);
                    }
                }
                first_window = false;'''
    changes[name] = text.replace('first_window = false;', code)
    patch = ''
    for name, after in changes.items():
        before = (source/name).read_text(encoding='utf-8')
        patch += ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
        (source/name).write_text(after, encoding='utf-8')
    (out/'first-logits.patch').write_text(patch, encoding='utf-8')
    env = dict(os.environ)
    if 'STRATA_API_KEY' in env: raise RuntimeError('Escludere STRATA_API_KEY')
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"', capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=',1); env[key]=value
    env['PATH'] = str(CUDA/'bin')+os.pathsep+env.get('Path',env.get('PATH',''))
    binary = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result = {'upstream_diagnostic':'ad48d5c5ca', 'base':str(base), 'variant':str(variant), 'steps':[]}
    def run(name, command, shell=False):
        start=time.monotonic()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            proc=subprocess.run(command if shell else list(map(str,command)),cwd=out,env=env,shell=shell,stdout=log,stderr=subprocess.STDOUT)
        result['steps'].append({'name':name,'exit':proc.returncode,'seconds':round(time.monotonic()-start,2)})
        if proc.returncode: raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))
    replacements={}
    for target in [r'CMakeFiles\strata_engine.dir\src\core\verify.cpp.obj', r'CMakeFiles\strata.dir\src\program\generate.cpp.obj']:
        command=subprocess.check_output([str(NINJA),'-C',str(build),'-t','commands',target]).decode().splitlines()[-1]
        assert ' -c ' in command and target in command
        command=command.replace(str(base/'source'),str(source)).replace((base/'source').as_posix(),source.as_posix())
        destination=out/target; destination.parent.mkdir(parents=True,exist_ok=True)
        replacements[target]=destination
        run('compile-'+destination.name,command,shell=True)
    ninja=(build/'build.ninja').read_text(encoding='utf-8')
    line=next(x for x in ninja.splitlines() if x.startswith('build strata_engine.lib:'))
    objects=line.split('Release ',1)[1].split(' ||',1)[0].split()
    rsp=out/'engine.rsp'
    rsp.write_text('/nologo\n/out:"'+str(out/'strata_engine.lib')+'"\n'+'\n'.join('"'+str(replacements.get(x,build/x))+'"' for x in objects),encoding='utf-8')
    run('archive',[binary/'lib.exe','@'+str(rsp)])
    prefill = variant/'strata_prefill.lib' if variant != base else build/'strata_prefill.lib'
    libs=[out/'strata_engine.lib',prefill,build/'strata_spec.lib']
    libs += [build/x for x in ['strata_kernels.lib','strata_core.lib','strata_kernels_cpu.lib','ggml/src/ggml-cpu.lib','strata_mmq.lib','ggml/src/ggml-base.lib']]
    libs += [CUDA/'lib/x64'/(x+'.lib') for x in ['cudart','cuda','cublas','cublasLt','cudadevrt']]
    libs += [x+'.lib' for x in ['kernel32','user32','gdi32','winspool','shell32','ole32','oleaut32','uuid','comdlg32','advapi32']]
    run('link',[binary/'link.exe','/nologo','/machine:x64','/INCREMENTAL:NO','/subsystem:console','/DEBUG','/OPT:REF','/OPT:ICF','/MANIFEST:EMBED','/out:'+str(out/'strata.exe'),'/pdb:'+str(out/'strata.pdb'),replacements[r'CMakeFiles\strata.dir\src\program\generate.cpp.obj'],*libs])
    result['exe_sha256']=hashlib.sha256((out/'strata.exe').read_bytes()).hexdigest()
    result['source_sha256']={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in changes}
    (out/'build-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('BUILD_OK',out,flush=True)


if __name__ == '__main__': main()
