"""Confronta CH32 daily e CH16 isolato, nello stesso banco e processo GPU.

Non modifica il daily. Usa il banco numerico FP64 upstream, sostituendo il
vecchio riferimento decode con il prompt CH32. CH16 non e' bitwise: cambia
il raggruppamento della softmax. Nessuna validazione del modello implicita.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from compila_0131 import BASE, CUDA, VC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--daily', type=Path, required=True)
    ap.add_argument('--daily-kernels', type=Path, required=True)
    ap.add_argument('--core-lib', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    daily = a.daily.resolve(strict=True)
    kernels = a.daily_kernels.resolve(strict=True)
    core = a.core_lib.resolve(strict=True)
    metadata = json.loads((kernels.parent/'build-result.json').read_text(encoding='utf-8'))
    assert metadata['exe_sha256'] == hashlib.sha256((daily/'strata.exe').read_bytes()).hexdigest()
    out = a.out.resolve()
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import psutil
    assert 'STRATA_API_KEY' not in os.environ
    assert not any((p.info['name'] or '').lower() in ('strata.exe', 'llama-server.exe')
                   for p in psutil.process_iter(['name']))
    out.mkdir(exist_ok=False)
    source = daily/'source'
    before = (source/'src/kernels/cuda/qsa_prompt_attn.cu').read_text(encoding='utf-8')
    anchor = '        attr[dev] = true;\n'
    # Replace only the v1 launcher; v2 has its own earlier attribute cache.
    split = before.index('    const int bytes = (int) sizeof(Smem<KV_MODE>);')
    tail = before[split:]
    assert tail.count(anchor) == 1
    after = before[:split] + tail.replace(anchor,
        '        if constexpr (D1_CH == 16 && KV_MODE == 1) {\n'
        '            if (cudaFuncSetAttribute(prompt_attn_kernel<KV_MODE>,\n'
        '                    cudaFuncAttributePreferredSharedMemoryCarveout, 100) != cudaSuccess) {\n'
        '                cudaGetLastError();\n'
        '                return false;\n'
        '            }\n'
        '        }\n' + anchor)
    score_loop = ('        for (int nt = 0; nt < CH / 32; ++nt) {\n'
                  '            const int cb = (warp + 4 * nt) * 8;')
    assert after.count(score_loop) == 1
    after = after.replace(score_loop,
        '        for (int nt = warp; nt < CH / 8; nt += 4) {\n'
        '            const int cb = nt * 8;')
    kernel = out/'qsa_prompt_attn.cu'
    kernel.write_text(after, encoding='utf-8')
    (out/'ch16-carveout.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile='a/src/kernels/cuda/qsa_prompt_attn.cu',
        tofile='b/src/kernels/cuda/qsa_prompt_attn.cu')), encoding='utf-8')
    text = (source/'src/kernels/qsa_prompt_attn_parity.cpp').read_text(encoding='utf-8')
    declaration = (source/'include/strata/kernels/qsa_prompt_attn.hpp').read_text(encoding='utf-8')
    declaration = declaration[declaration.index('namespace strata::kernels {'):]
    declaration = declaration.replace('qsa_prompt_attn_batch', 'qsa_prompt_attn_ch16')
    text = text.replace('namespace k = strata::kernels;', declaration+'\nnamespace k = strata::kernels;')
    start = text.index('    auto old_run = [&]() {')
    end = text.index('    auto new_run = [&]() {', start)
    text = text[:start] + ('    auto old_run = [&]() {\n'
        '        if (!k::qsa_prompt_attn_batch(d_q, pl, d_ids, d_steps, cap, s, d_old, nq, nullptr)) std::exit(2);\n'
        '    };\n') + text[end:]
    text = text.replace('if (!k::qsa_prompt_attn_batch(d_q, pl, d_ids, d_steps, cap, s, d_new',
                        'if (!k::qsa_prompt_attn_ch16(d_q, pl, d_ids, d_steps, cap, s, d_new')
    test = out/'ch32_vs_ch16.cpp'
    test.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            env[key] = value
    env['PATH'] = str(CUDA/'bin') + os.pathsep + env.get('Path', env.get('PATH', ''))
    binary = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result = {'daily_exe_sha256': hashlib.sha256((daily/'strata.exe').read_bytes()).hexdigest(),
              'reference_kernels_sha256': hashlib.sha256(kernels.read_bytes()).hexdigest(),
              'core_lib_sha256': hashlib.sha256(core.read_bytes()).hexdigest(),
              'scope': 'CH32 vs CH16, isolated kernel; FP64 sample; no model test', 'steps': []}

    def run(name, command):
        print(name, flush=True)
        started = time.monotonic()
        with (out/(name+'.log')).open('w', encoding='utf-8') as log:
            p = subprocess.run(list(map(str, command)), cwd=out, env=env,
                               stdout=log, stderr=subprocess.STDOUT, timeout=100)
        result['steps'].append({'name': name, 'exit': p.returncode,
                                'seconds': round(time.monotonic()-started, 2)})
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        if p.returncode:
            print((out/(name+'.log')).read_text(encoding='utf-8', errors='replace'), flush=True)
            raise RuntimeError(name+' failed')

    obj = out/'ch16.obj'
    run('compile-ch16', [CUDA/'bin/nvcc.exe', '-std=c++20', '-O3', '-DNDEBUG',
        '-DD1_CH=16', '-Dqsa_prompt_attn_batch=qsa_prompt_attn_ch16',
        '--generate-code=arch=compute_75,code=sm_75', '-Xcompiler=/MD,/EHsc,/O2',
        '-I'+str(source/'include'), '-c', kernel, '-o', obj])
    run('compile-check', [binary/'cl.exe', '/nologo', '/std:c++20', '/EHsc', '/O2', '/MD',
        '/I'+str(source/'include'), '/I'+str(CUDA/'include'), test,
        '/Fo:'+str(out/'test.obj'), '/Fe:'+str(out/'check.exe'), '/link', obj,
        kernels, core,
        CUDA/'lib/x64/cudart.lib', CUDA/'lib/x64/cublas.lib', CUDA/'lib/x64/cudadevrt.lib'])
    run('parity-131k-2048', [out/'check.exe', '131072', '2048', '3'])
    print((out/'parity-131k-2048.log').read_text(encoding='utf-8'), flush=True)


if __name__ == '__main__':
    main()
