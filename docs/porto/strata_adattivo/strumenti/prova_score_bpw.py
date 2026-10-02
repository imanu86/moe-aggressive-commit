"""Confronto bitwise e timing A/B/A dei punteggi QSA BPW1/4/8/16.

Usa il banco upstream con scorer originale come riferimento; verifica ogni
score attivo e ogni indice selezionato, inclusi i percorsi decode preservati.
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
    text = (source/'src/kernels/qsa_select_bench.cpp').read_text(encoding='utf-8')
    text = text.replace('#include <algorithm>', '#include <algorithm>\n#include <cstring>')
    text = text.replace('    const k::QsaShapes s =',
        '    const char* bpw = argc > 4 ? argv[4] : "16";\n    const k::QsaShapes s =')
    text = text.replace('    auto run_old = [&] { k::qsa_block_scores',
        '    ck(cudaMemset(sc_old, 0, (size_t)(nq * max_blocks) * 4), "zero-old");\n'
        '    ck(cudaMemset(sc_new, 0, (size_t)(nq * max_blocks) * 4), "zero-new");\n'
        '    auto run_old = [&] { _putenv_s("STRATA_SCORE_BPW", "1"); k::qsa_block_scores')
    start = text.index('    auto run_new = [&] {')
    end = text.index('    run_old();', start)
    text = text[:start] + ('    auto run_new = [&] {\n'
        '        _putenv_s("STRATA_SCORE_BPW", bpw);\n'
        '        k::qsa_block_scores(d_pooled, d_dead, d_q, d_steps, nq, max_blocks, s, sc_new, nullptr, active);\n'
        '    };\n') + text[end:]
    text = text.replace('    // time',
        '    const bool exact = std::memcmp(a.data(), b.data(), a.size() * sizeof(float)) == 0;\n'
        '    bool finite = true;\n'
        '    for (size_t i = 0; i < a.size(); ++i) finite = finite && std::isfinite(a[i]) && std::isfinite(b[i]);\n'
        '    // time')
    text = text.replace('    const float t_old = timed(run_old), t_new = timed(run_new);',
        '    const float t_old = timed(run_old), t_new = timed(run_new), t_after = timed(run_old);\n'
        '    std::printf("ABA BPW%s ctx %lld queries %lld: %.6f %.6f %.6f ms; bitwise %d finite %d\\n",\n'
        '        bpw, (long long)ctx, (long long)nq, t_old, t_new, t_after, exact, finite);')
    text = text.replace('    return 0;\n}',
        '    return exact && finite && same_sel == nq && reg_same == nq ? 0 : 1;\n}')
    text = text.replace('    const int64_t active = steps[',
        '    const int64_t active = argc > 5 ? 0 : steps[')
    test = out/'paired-score.cpp'
    test.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    env.pop('STRATA_SCORES_MULTI', None)
    init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                          capture_output=True, text=True, env=env, check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key, value = line.split('=', 1)
            env[key] = value
    binary = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result = {'scope': 'BPW1/selected/1; bitwise scores + selected IDs; finite; decode preserved', 'steps': []}

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
            print((out/(name+'.log')).read_text(encoding='utf-8'), flush=True)
            raise RuntimeError(name+' failed')

    run('compile-score-paired', [binary/'cl.exe', '/nologo', '/std:c++20', '/EHsc', '/O2', '/MD',
        '/I'+str(source/'include'), '/I'+str(CUDA/'include'), test,
        '/Fo:'+str(out/'paired.obj'), '/Fe:'+str(out/'paired.exe'), '/link',
        candidate/'strata_kernels.lib', a.core_lib.resolve(strict=True),
        CUDA/'lib/x64/cudart.lib', CUDA/'lib/x64/cudadevrt.lib'])
    for bpw in [4, 8, 16]:
        for ctx, nq in [(131072, 128), (131072, 8192), (262144, 8192), (1111, 128), (131072, 8)]:
            name = f'bpw{bpw}-ctx{ctx}-q{nq}'
            run(name, [out/'paired.exe', str(ctx), str(nq), '5', str(bpw)])
            print((out/(name+'.log')).read_text(encoding='utf-8'), flush=True)
    run('decode-multi-preserved', [out/'paired.exe', '131072', '8', '5', '16', 'multi'])
    print((out/'decode-multi-preserved.log').read_text(encoding='utf-8'), flush=True)


if __name__ == '__main__':
    main()
