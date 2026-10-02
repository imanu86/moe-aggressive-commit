"""Analisi CPU della serie modello QSA: tempi, cache, MTP e primi logits."""
import argparse
import json
from pathlib import Path
import re
import sys
from compila_0131 import BASE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import numpy as np
    result = {'scope': 'model ABA, real 131k, KV262144, elastic', 'runs': {}}
    logits = {}
    rx = re.compile(r'strata serve: prompt (\d+) tokens =.*?, (\d+) generated in ([\d.]+) ms.*?drafts accepted (\d+) of (\d+)')
    for name in ['A1', 'B', 'A2']:
        root = a.runs/name
        outcome = json.loads((root/'esito.json').read_text(encoding='utf-8'))
        assert outcome['status'] == 'completed', name+' incomplete'
        files = list((root/'banco').glob('*/results.jsonl'))
        assert len(files) == 1
        rows = [json.loads(s) for s in files[0].read_text(encoding='utf-8').splitlines()]
        rows = [r for r in rows if not r.get('riscaldamento')]
        assert len(rows) == 2
        native = []
        for m in rx.finditer((root/'strata.log').read_text(encoding='utf-8')):
            depth, generated, ms, accepted, offered = m.groups()
            if int(depth) >= 131000 and int(generated) == 1024:
                native.append({'generated': int(generated), 'decode_ms': float(ms),
                               'accepted': int(accepted), 'offered': int(offered)})
        assert len(native) == 2, name+' native rows missing'
        verified = sum(r['generated'] - r['accepted'] + r['offered'] for r in native)
        cpu = [json.loads(s) for s in (root/'cpu.jsonl').read_text(encoding='utf-8').splitlines()]
        others = [sum(v for k, v in r['proc'].items() if k not in ('System Idle Process', 'strata.exe', 'python.exe')) for r in cpu]
        record = {'exe_sha256': outcome['exe_sha256'], 'qsa_ch': outcome['qsa_ch'],
                  'topk_mode': outcome.get('topk_mode'),
                  'initial_cache': outcome['initial_cache'], 'prefill_tps': rows[0]['prefill_tps_motore'],
                  'ttft_s': rows[0]['ttft_s'], 'decode_tps': outcome['summary']['decode_aggregato_tps'],
                  'cost_per_verified_row_ms': sum(r['decode_ms'] for r in native)/verified,
                  'native': native, 'cpu_other_mean_cores': sum(others)/len(others),
                  'cpu_jump_mean_cores': sum(r['proc'].get('JumpConnect.exe', 0) for r in cpu)/len(cpu),
                  'real_prompt_tokens': [r['motore']['prompt_tokens'] for r in rows],
                  'reused_prompt_tokens': [r['motore']['reused'] for r in rows], 'logits': {}}
        logits[name] = {}
        for pos in [131247, 131238]:
            x = np.fromfile(root/f'first-logits.pos{pos}.f32', dtype=np.float32)
            assert len(x) == 248320 and np.isfinite(x).all()
            logits[name][pos] = x
            record['logits'][str(pos)] = {'values': len(x), 'finite': True, 'argmax': int(x.argmax())}
        result['runs'][name] = record
    x, b, y = [result['runs'][k]['prefill_tps'] for k in ['A1', 'B', 'A2']]
    avg = (x+y)/2
    result['prefill'] = {'baseline_mean_tps': avg, 'candidate_tps': b,
                         'gain_percent': 100*(b/avg-1), 'baseline_variation_percent': 100*abs(x-y)/avg,
                         'candidate_beats_both_references': b > max(x, y),
                         'benefit_demonstrated': b > max(x, y) and (b-avg) > abs(x-y)}
    result['logits_comparisons'] = {}
    for left, right in [('A1', 'B'), ('A2', 'B'), ('A1', 'A2')]:
        pairs = {}
        for pos in [131247, 131238]:
            x, y = logits[left][pos], logits[right][pos]
            diff = np.abs(x-y)
            pairs[str(pos)] = {'max_abs': float(diff.max()), 'mean_abs': float(diff.mean()),
                               'equal_values': int((x == y).sum()), 'same_argmax': int(x.argmax()) == int(y.argmax())}
        result['logits_comparisons'][left+'-'+right] = pairs
    a.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
