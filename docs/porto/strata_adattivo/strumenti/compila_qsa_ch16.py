"""Candidata daily con QSA CH16 solo Turing/int8 e override CH32 per A/B.

Ricompila un solo oggetto e riusa tutti gli input della combinazione daily.
Il default delle altre modalita' KV/dispositivi resta quello dei sorgenti base.
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


def integrate(before):
    after = before.replace('constexpr int CH = D1_CH;', 'constexpr int DEFAULT_CH = D1_CH;')
    assert after != before
    assert after.count('template <int KV_MODE>') == 3
    after = after.replace('template <int KV_MODE>', 'template <int KV_MODE, int CH>')
    after = after.replace('Smem<KV_MODE>', 'Smem<KV_MODE, CH>')
    after = after.replace('prompt_attn_kernel<KV_MODE>', 'prompt_attn_kernel<KV_MODE, CH>')
    anchor = 'template <int KV_MODE, int CH>\nbool launch('
    assert after.count(anchor) == 1
    after = after.replace(anchor, 'template <int KV_MODE, int CH = DEFAULT_CH>\nbool launch(')
    loop = ('        for (int nt = 0; nt < CH / 32; ++nt) {\n'
            '            const int cb = (warp + 4 * nt) * 8;')
    assert after.count(loop) == 1
    after = after.replace(loop, '        for (int nt = warp; nt < CH / 8; nt += 4) {\n'
                               '            const int cb = nt * 8;')
    split = after.index('    const int bytes = (int) sizeof(Smem<KV_MODE, CH>);')
    anchor = '        attr[dev] = true;\n'
    tail = after[split:]
    assert tail.count(anchor) == 1
    after = after[:split] + tail.replace(anchor,
        '        if constexpr (CH == 16 && KV_MODE == 1) {\n'
        '            if (cudaFuncSetAttribute(prompt_attn_kernel<KV_MODE, CH>,\n'
        '                    cudaFuncAttributePreferredSharedMemoryCarveout, 100) != cudaSuccess) {\n'
        '                cudaGetLastError();\n'
        '                return false;\n'
        '            }\n'
        '        }\n' + anchor)
    anchor = '        if (v1 || turing) return launch<1>(q, pools, ids, steps, cap, s, attn, n_q, st);'
    assert after.count(anchor) == 1
    after = after.replace(anchor,
        '        if (turing) {\n'
        '            const char* ch = std::getenv("STRATA_QSA_CH");\n'
        '            if (ch && ch[0] == \'3\' && ch[1] == \'2\' && ch[2] == \'\\0\')\n'
        '                return launch<1, 32>(q, pools, ids, steps, cap, s, attn, n_q, st);\n'
        '            if (ch && !(ch[0] == \'1\' && ch[1] == \'6\' && ch[2] == \'\\0\')) {\n'
        '                std::fprintf(stderr, "STRATA_QSA_CH must be 16 or 32\\n");\n'
        '                std::exit(1);\n'
        '            }\n'
        '            return launch<1, 16>(q, pools, ids, steps, cap, s, attn, n_q, st);\n'
        '        }\n'
        '        if (v1) return launch<1>(q, pools, ids, steps, cap, s, attn, n_q, st);')
    return after


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
    name = 'src/kernels/cuda/qsa_prompt_attn.cu'
    before = (source/name).read_text(encoding='utf-8')
    after = integrate(before)
    (source/name).write_text(after, encoding='utf-8')
    (out/'qsa-ch16.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),
        after.splitlines(True), fromfile='a/'+name, tofile='b/'+name)), encoding='utf-8')
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
    result = {'base_exe_sha256': sha(bundle/'strata.exe'), 'scope': 'daily + QSA CH16 Turing/int8',
              'source_sha256': sha(source/name), 'steps': []}

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

    target = r'CMakeFiles\strata_kernels.dir\src\kernels\cuda\qsa_prompt_attn.cu.obj'
    obj = out/target
    obj.parent.mkdir(parents=True)
    command = subprocess.check_output([str(NINJA), '-C', str(build), '-t', 'commands', target]).decode().splitlines()[-1]
    command = command.replace(str(base/'source'), str(source)).replace((base/'source').as_posix(), source.as_posix())
    run('compile-qsa', command, shell=True)
    lines = (daily/'strata_kernels.lib.rsp').read_text(encoding='utf-8').splitlines()[2:]
    objects = [Path(line.strip('"')) for line in lines]
    assert sum(p.name == 'qsa_prompt_attn.cu.obj' for p in objects) == 1
    objects = [obj if p.name == 'qsa_prompt_attn.cu.obj' else p for p in objects]
    assert all(p.is_file() for p in objects)
    rsp = out/'kernels.rsp'
    rsp.write_text('/nologo\n/out:"'+str(out/'strata_kernels.lib')+'"\n' +
                   '\n'.join('"'+str(p)+'"' for p in objects), encoding='utf-8')
    run('archive-kernels', [binary/'lib.exe', '@'+str(rsp)])
    libs = [daily/'strata_engine.lib', hc/'strata_prefill.lib', build/'strata_spec.lib',
            out/'strata_kernels.lib', build/'strata_core.lib', build/'strata_kernels_cpu.lib',
            build/'ggml/src/ggml-cpu.lib', build/'strata_mmq.lib', build/'ggml/src/ggml-base.lib']
    result['reused_libs_sha256'] = {str(p): sha(p) for p in libs if p.parent != out}
    libs += [CUDA/'lib/x64'/(x+'.lib') for x in ['cudart', 'cuda', 'cublas', 'cublasLt', 'cudadevrt']]
    libs += [x+'.lib' for x in ['kernel32', 'user32', 'gdi32', 'winspool', 'shell32',
                             'ole32', 'oleaut32', 'uuid', 'comdlg32', 'advapi32']]
    run('link', [binary/'link.exe', '/nologo', '/machine:x64', '/INCREMENTAL:NO', '/subsystem:console',
        '/DEBUG', '/OPT:REF', '/OPT:ICF', '/MANIFEST:EMBED', '/out:'+str(out/'strata.exe'),
        '/pdb:'+str(out/'strata.pdb'), hcl/r'CMakeFiles\strata.dir\src\program\generate.cpp.obj', *libs])
    test = source/'src/kernels/qsa_prompt_attn_parity.cpp'
    run('compile-parity', [binary/'cl.exe', '/nologo', '/std:c++20', '/EHsc', '/O2', '/MD',
        '/I'+str(source/'include'), '/I'+str(CUDA/'include'), test,
        '/Fo:'+str(out/'parity.obj'), '/Fe:'+str(out/'parity.exe'), '/link',
        out/'strata_kernels.lib', build/'strata_core.lib', CUDA/'lib/x64/cudart.lib',
        CUDA/'lib/x64/cublas.lib', CUDA/'lib/x64/cudadevrt.lib'])
    run('parity-131k-8192', [out/'parity.exe', '131072', '8192', '3'])
    print((out/'parity-131k-8192.log').read_text(encoding='utf-8'), flush=True)
    result['exe_sha256'] = sha(out/'strata.exe')
    (out/'build-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('QSA_CH16_BUILD_OK', out, flush=True)


if __name__ == '__main__':
    main()
