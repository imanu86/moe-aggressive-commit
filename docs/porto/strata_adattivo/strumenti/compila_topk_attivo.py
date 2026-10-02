"""Candidata daily con top-k prefill limitato dai blocchi attivi, KV262k.

Ricompila selezione CUDA e chiamante prefill, riusando gli altri input daily.
Il default delle altre modalita' KV/dispositivi resta quello dei sorgenti base.
"""
import argparse
from port_topk_attivo import integrate_topk
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
    ap.add_argument('--daily-bundle', type=Path, required=True)
    ap.add_argument('--daily-build', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    bundle, daily = [p.resolve(strict=True) for p in [a.daily_bundle, a.daily_build]]
    meta = json.loads((daily/'build-result.json').read_text(encoding='utf-8'))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(bundle/'strata.exe') == meta['exe_sha256']
    base, hc, hcl = [Path(meta[k]).resolve(strict=True) for k in ['base', 'hc', 'hc_logits']]
    build = base/'build'
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import psutil
    assert 'STRATA_API_KEY' not in os.environ
    assert not any((p.info['name'] or '').lower() in ('strata.exe', 'llama-server.exe')
                   for p in psutil.process_iter(['name']))
    out = a.out.resolve()
    out.mkdir(exist_ok=False)
    source = out/'source'
    shutil.copytree(bundle/'source', source)
    patch = ''
    changes = integrate_topk(source)
    for name, after in changes.items():
        before = (source/name).read_text(encoding='utf-8')
        patch += ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                          fromfile='a/'+name, tofile='b/'+name))
        (source/name).write_text(after, encoding='utf-8')
    (out/'topk-active.patch').write_text(patch, encoding='utf-8')
    env = dict(os.environ)
    env.pop('STRATA_QSA_CH', None)
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            env[key] = value
    env['PATH'] = str(CUDA/'bin') + os.pathsep + env.get('Path', env.get('PATH', ''))
    binary = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result = {'base_exe_sha256': sha(bundle/'strata.exe'), 'scope': 'daily + prefill QSA topk active bound',
              'source_sha256': {name: sha(source/name) for name in changes}, 'steps': []}

    def run(name, command, shell=False):
        print(name, flush=True)
        started = time.monotonic()
        with (out/(name+'.log')).open('w', encoding='utf-8') as log:
            p = subprocess.run(command if shell else list(map(str, command)), cwd=out,
                               env=env, shell=shell, stdout=log, stderr=subprocess.STDOUT)
        result['steps'].append({'name': name, 'exit': p.returncode,
                                'seconds': round(time.monotonic()-started, 2)})
        (out/'build-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        if p.returncode:
            raise RuntimeError(name+' failed; '+str(out/(name+'.log')))

    replacements = {}
    for target in [r'CMakeFiles\strata_kernels.dir\src\kernels\cuda\qsa_select.cu.obj',
                   r'CMakeFiles\strata_prefill.dir\src\prefill\prefill.cpp.obj']:
        obj = out/target
        obj.parent.mkdir(parents=True)
        replacements[Path(target).name] = obj
        command = subprocess.check_output([str(NINJA), '-C', str(build), '-t', 'commands', target]).decode().splitlines()[-1]
        command = command.replace(str(base/'source'), str(source)).replace((base/'source').as_posix(), source.as_posix())
        run('compile-'+obj.name, command, shell=True)
    lines = (daily/'strata_kernels.lib.rsp').read_text(encoding='utf-8').splitlines()[2:]
    objects = [Path(line.strip('"')) for line in lines]
    assert sum(p.name == 'qsa_select.cu.obj' for p in objects) == 1
    objects = [replacements.get(p.name, p) for p in objects]
    assert all(p.is_file() for p in objects)
    rsp = out/'kernels.rsp'
    rsp.write_text('/nologo\n/out:"'+str(out/'strata_kernels.lib')+'"\n' +
                   '\n'.join('"'+str(p)+'"' for p in objects), encoding='utf-8')
    run('archive-kernels', [binary/'lib.exe', '@'+str(rsp)])
    prefill_objects = [Path(line.strip('"')) for line in (hc/'prefill.rsp').read_text(encoding='utf-8').splitlines()[2:]]
    prefill_objects = [replacements.get(p.name, p) for p in prefill_objects]
    assert len(prefill_objects) == 3 and all(p.is_file() for p in prefill_objects)
    rsp = out/'prefill.rsp'
    rsp.write_text('/nologo\n/out:"'+str(out/'strata_prefill.lib')+'"\n' +
                   '\n'.join('"'+str(p)+'"' for p in prefill_objects), encoding='utf-8')
    run('archive-prefill', [binary/'lib.exe', '@'+str(rsp)])
    libs = [daily/'strata_engine.lib', out/'strata_prefill.lib', build/'strata_spec.lib',
            out/'strata_kernels.lib', build/'strata_core.lib', build/'strata_kernels_cpu.lib',
            build/'ggml/src/ggml-cpu.lib', build/'strata_mmq.lib', build/'ggml/src/ggml-base.lib']
    result['reused_libs_sha256'] = {str(p): sha(p) for p in libs if p.parent != out}
    libs += [CUDA/'lib/x64'/(x+'.lib') for x in ['cudart', 'cuda', 'cublas', 'cublasLt', 'cudadevrt']]
    libs += [x+'.lib' for x in ['kernel32', 'user32', 'gdi32', 'winspool', 'shell32',
                             'ole32', 'oleaut32', 'uuid', 'comdlg32', 'advapi32']]
    run('link', [binary/'link.exe', '/nologo', '/machine:x64', '/INCREMENTAL:NO', '/subsystem:console',
        '/DEBUG', '/OPT:REF', '/OPT:ICF', '/MANIFEST:EMBED', '/out:'+str(out/'strata.exe'),
        '/pdb:'+str(out/'strata.pdb'), hcl/r'CMakeFiles\strata.dir\src\program\generate.cpp.obj', *libs])
    result['exe_sha256'] = sha(out/'strata.exe')
    (out/'build-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('TOPK_ACTIVE_BUILD_OK', out, flush=True)


if __name__ == '__main__':
    main()
