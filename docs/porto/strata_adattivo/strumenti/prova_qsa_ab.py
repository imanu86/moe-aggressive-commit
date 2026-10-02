"""Banco A/B/A QSA CH32/CH16 nello stesso oggetto candidato, con FP64.

128, 2048 e 8192 query, pool contesto131072; include FP16 invariato,
contesto corto e limite identity/sparse. Non carica il modello.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from compila_0131 import BASE, CUDA, VC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--core-lib', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    candidate = a.candidate.resolve(strict=True)
    out = a.out.resolve()
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import psutil
    assert 'STRATA_API_KEY' not in os.environ
    assert not any((p.info['name'] or '').lower() in ('strata.exe', 'llama-server.exe')
                   for p in psutil.process_iter(['name']))
    out.mkdir(exist_ok=False)
    source = candidate/'source'
    text = (source/'src/kernels/qsa_prompt_attn_parity.cpp').read_text(encoding='utf-8')
    start = text.index('    auto old_run = [&]() {')
    end = text.index('    auto new_run = [&]() {', start)
    text = text[:start] + ('    auto old_run = [&]() {\n'
        '        _putenv_s("STRATA_QSA_CH", "32");\n'
        '        if (!k::qsa_prompt_attn_batch(d_q, pl, d_ids, d_steps, cap, s, d_old, nq, nullptr)) std::exit(2);\n'
        '    };\n') + text[end:]
    text = text.replace('    auto new_run = [&]() {',
                        '    auto new_run = [&]() {\n        _putenv_s("STRATA_QSA_CH", "16");')
    text = text.replace('    // 2. new vs old everywhere',
        '    for (size_t i = 0; i < o.size(); ++i) {\n'
        '        if (!std::isfinite(o[i]) || !std::isfinite(nw[i])) {\n'
        '            std::fprintf(stderr, "nonfinite output\\n"); std::exit(3);\n'
        '        }\n'
        '    }\n    // 2. new vs old everywhere')
    text = text.replace('    const bool ok1 =',
        '    float ms_after = 0;\n'
        '    cudaEventRecord(e0);\n'
        '    for (int r = 0; r < reps; ++r) old_run();\n'
        '    cudaEventRecord(e1);\n'
        '    ck(cudaEventSynchronize(e1), "after");\n'
        '    cudaEventElapsedTime(&ms_after, e0, e1);\n'
        '    std::printf("ABA %s ctx %lld queries %lld: CH32 %.6f CH16 %.6f CH32 %.6f ms\\n",\n'
        '        fmt == 1 ? "int8" : "fp16", (long long)ctx, (long long)nq, ms_old/reps, ms_new/reps, ms_after/reps);\n'
        '    const bool ok1 =')
    text = text.replace('    const bool ok2 = diff <= 1e-4 * scale;',
        '    const bool ok2 = fmt == 0 ? diff == 0.0 : diff <= 1e-4 * scale;')
    test = out/'paired.cpp'
    test.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            env[key] = value
    binary = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result = {'scope': 'same candidate library, CH32/CH16/CH32, finite + FP64 + FP16 exact', 'steps': []}

    def run(name, command):
        print(name, flush=True)
        t = time.monotonic()
        with (out/(name+'.log')).open('w', encoding='utf-8') as log:
            p = subprocess.run(list(map(str, command)), cwd=out, env=env,
                               stdout=log, stderr=subprocess.STDOUT, timeout=180)
        result['steps'].append({'name': name, 'exit': p.returncode,
                                'seconds': round(time.monotonic()-t, 2)})
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        if p.returncode:
            raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))

    run('compile-paired', [binary/'cl.exe', '/nologo', '/std:c++20', '/EHsc', '/O2', '/MD',
        '/I'+str(source/'include'), '/I'+str(CUDA/'include'), test,
        '/Fo:'+str(out/'paired.obj'), '/Fe:'+str(out/'paired.exe'), '/link',
        candidate/'strata_kernels.lib', a.core_lib.resolve(strict=True),
        CUDA/'lib/x64/cudart.lib', CUDA/'lib/x64/cublas.lib', CUDA/'lib/x64/cudadevrt.lib'])
    for nq in [128, 2048, 8192]:
        run('paired-'+str(nq), [out/'paired.exe', '131072', str(nq), '5'])
        print((out/('paired-'+str(nq)+'.log')).read_text(encoding='utf-8'), flush=True)


if __name__ == '__main__':
    main()
