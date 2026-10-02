"""Compila il gather #439 su una sorgente daily preparata, senza alterare l'operativo.

Riusa le librerie della daily 0.1.31 gia' validate e ricompila solo prefill.cpp e
moe_mmq.cu. Il controllo byte-per-byte confronta gather singolo e batch sulla GPU.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from compila_0131 import BASE, CUDA, VC, NINJA


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--hc', type=Path, required=True)
    parser.add_argument('--hc-logits', type=Path, required=True)
    parser.add_argument('--daily', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='Sorgenti portati in out/source')
    a = parser.parse_args()
    base, hc, hcl, daily, out = [p.resolve(strict=True) for p in
                                 [a.base, a.hc, a.hc_logits, a.daily, a.out]]
    source, build = out/'source', base/'build'
    porting = json.loads((out/'porting.json').read_text(encoding='utf-8'))
    assert sha(daily/'strata.exe') == porting['base_exe_sha256']
    assert sha(source/'src/prefill/kernels.cu') == sha(hc/'source/src/prefill/kernels.cu')
    assert not (out/'strata.exe').exists(), 'Non sovrascrivere una candidata compilata'
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import psutil
    if any((p.info['name'] or '').lower() in ('strata.exe', 'llama-server.exe')
           for p in psutil.process_iter(['name'])):
        raise RuntimeError('Motore attivo: attendere prima della compilazione')
    env = dict(os.environ)
    if 'STRATA_API_KEY' in env:
        raise RuntimeError('Escludere STRATA_API_KEY')
    env.pop('STRATA_PREFILL_GATHER_ONE', None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            env[key] = value
    env['PATH'] = str(CUDA/'bin') + os.pathsep + env.get('Path', env.get('PATH', ''))
    binary = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result = {'base': str(base), 'hc': str(hc), 'daily': str(daily),
              'pr_head_sha': porting['pr_head_sha'], 'scope': 'daily 0.1.31 + PR439 gather', 'steps': []}

    def run(name, command, shell=False):
        print(name, flush=True)
        started = time.monotonic()
        with (out/(name+'.log')).open('w', encoding='utf-8') as log:
            process = subprocess.run(command if shell else list(map(str, command)), cwd=out,
                                     env=env, shell=shell, stdout=log, stderr=subprocess.STDOUT)
        result['steps'].append({'name': name, 'exit': process.returncode,
                                'seconds': round(time.monotonic()-started, 2)})
        (out/'build-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        if process.returncode:
            raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))

    targets = [r'CMakeFiles\strata_prefill.dir\src\prefill\prefill.cpp.obj',
               r'CMakeFiles\strata_mmq.dir\src\prefill\moe_mmq.cu.obj']
    replacements = {}
    for target in targets:
        command = subprocess.check_output([str(NINJA), '-C', str(build), '-t', 'commands', target]).decode().splitlines()[-1]
        assert target in command
        command = command.replace(str(base/'source'), str(source)).replace((base/'source').as_posix(), source.as_posix())
        destination = out/target
        destination.parent.mkdir(parents=True, exist_ok=True)
        replacements[target] = destination
        run('compile-'+destination.name, command, shell=True)

    # HC's kernels object and the base GEMM object are retained; only prefill.cpp changes.
    lines = (hc/'prefill.rsp').read_text(encoding='utf-8').splitlines()[2:]
    objects = [Path(line.strip('"')) for line in lines]
    objects = [replacements[targets[0]] if p.name == 'prefill.cpp.obj' else p for p in objects]
    assert len(objects) == 3
    rsp = out/'strata_prefill.lib.rsp'
    rsp.write_text('/nologo\n/out:"'+str(out/'strata_prefill.lib')+'"\n' +
                   '\n'.join('"'+str(p)+'"' for p in objects), encoding='utf-8')
    run('archive-prefill', [binary/'lib.exe', '@'+str(rsp)])
    ninja = (build/'build.ninja').read_text(encoding='utf-8')
    line = next(x for x in ninja.splitlines() if x.startswith('build strata_mmq.lib:'))
    objects = line.split('Release ', 1)[1].split(' ||', 1)[0].split()
    rsp = out/'strata_mmq.lib.rsp'
    rsp.write_text('/nologo\n/out:"'+str(out/'strata_mmq.lib')+'"\n' +
                   '\n'.join('"'+str(replacements.get(x, build/x))+'"' for x in objects), encoding='utf-8')
    run('archive-mmq', [binary/'lib.exe', '@'+str(rsp)])
    libs = [daily/'strata_engine.lib', out/'strata_prefill.lib', build/'strata_spec.lib',
            daily/'strata_kernels.lib', build/'strata_core.lib', build/'strata_kernels_cpu.lib',
            build/'ggml/src/ggml-cpu.lib', out/'strata_mmq.lib', build/'ggml/src/ggml-base.lib']
    cuda_libs = [CUDA/'lib/x64'/(x+'.lib') for x in ['cudart', 'cuda', 'cublas', 'cublasLt', 'cudadevrt']]
    windows_libs = [x+'.lib' for x in ['kernel32', 'user32', 'gdi32', 'winspool', 'shell32',
                                      'ole32', 'oleaut32', 'uuid', 'comdlg32', 'advapi32']]
    run('link', [binary/'link.exe', '/nologo', '/machine:x64', '/INCREMENTAL:NO', '/subsystem:console',
                 '/DEBUG', '/OPT:REF', '/OPT:ICF', '/MANIFEST:EMBED', '/out:'+str(out/'strata.exe'),
                 '/pdb:'+str(out/'strata.pdb'), hcl/r'CMakeFiles\strata.dir\src\program\generate.cpp.obj',
                 *libs, *cuda_libs, *windows_libs])
    run('compile-gather-parity', [binary/'cl.exe', '/nologo', '/std:c++20', '/EHsc', '/O2', '/MD',
                                 '/I'+str(source/'include'), '/I'+str(CUDA/'include'),
                                 source/'tests/cuda/prefill_gather_batch_test.cpp',
                                 '/Fo:'+str(out/'gather-parity.obj'), '/Fe:'+str(out/'gather-parity.exe'),
                                 '/link', out/'strata_mmq.lib', build/'ggml/src/ggml-base.lib',
                                 *cuda_libs, *windows_libs])
    run('gather-parity', [out/'gather-parity.exe'])
    print((out/'gather-parity.log').read_text(encoding='utf-8'), flush=True)
    result['exe_sha256'] = sha(out/'strata.exe')
    result['source_sha256'] = {name: sha(source/name) for name in porting['changes']}
    result['reused_lib_sha256'] = {str(p): sha(p) for p in libs if p.parent != out}
    result['generate_obj_sha256'] = sha(hcl/r'CMakeFiles\strata.dir\src\program\generate.cpp.obj')
    (out/'build-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('PR439_BUILD_AND_PARITY_OK', out, flush=True)


if __name__ == '__main__':
    main()
