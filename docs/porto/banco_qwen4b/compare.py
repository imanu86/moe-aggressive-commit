"""Compare frozen HTTP result files; report differences without hiding failures."""
import argparse
import json
from pathlib import Path
import statistics


def load(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def median(rows, key):
    values = [key(row) for row in rows]
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def compare(a, b):
    keys_a = [(r['case'], r['repeat']) for r in a]
    keys_b = [(r['case'], r['repeat']) for r in b]
    if not keys_a or not keys_b:
        raise ValueError('Empty benchmark results')
    if len(set(keys_a)) != len(keys_a) or len(set(keys_b)) != len(keys_b):
        raise ValueError('Duplicate case/repeat keys')
    if set(keys_a) != set(keys_b):
        raise ValueError('Different case/repeat sets')
    indexed = {(r['case'], r['repeat']): r for r in a}
    output = []
    for name in sorted({r['case'] for r in b}):
        rb = [r for r in b if r['case'] == name]
        ra = [indexed[(r['case'], r['repeat'])] for r in rb
              if (r['case'], r['repeat']) in indexed]
        if len(ra) != len(rb):
            raise ValueError('Missing paired runs: ' + name)
        if any(x['request_sha256'] != y['request_sha256'] for x, y in zip(ra, rb)):
            raise ValueError('Different request payloads: ' + name)
        valid = all(r.get('successful_terminal') and r.get('context_budget_ok')
                    and r.get('tool_correct', True) for r in ra + rb)
        equal_output = all(x['output_sha256'] == y['output_sha256'] for x, y in zip(ra, rb))
        ta = median(ra, lambda r: r['seconds'])
        tb = median(rb, lambda r: r['seconds'])
        output.append({'case': name, 'pairs': len(ra),
            'baseline_seconds_median': ta, 'candidate_seconds_median': tb,
            'latency_speedup': ta / tb if tb and valid and equal_output else None,
            'performance_gate_eligible': valid and equal_output and len(ra) >= 3,
            'all_terminal_states_successful': valid,
            'repetitions_sufficient': len(ra) >= 3,
            'baseline_seconds_range': [min(r['seconds'] for r in ra), max(r['seconds'] for r in ra)],
            'candidate_seconds_range': [min(r['seconds'] for r in rb), max(r['seconds'] for r in rb)],
            'baseline_first_delta_s': median(ra, lambda r: r['first_delta_s']),
            'candidate_first_delta_s': median(rb, lambda r: r['first_delta_s']),
            'baseline_first_text_s': median(ra, lambda r: r['first_text_s']),
            'candidate_first_text_s': median(rb, lambda r: r['first_text_s']),
            'baseline_first_tool_s': median(ra, lambda r: r['first_tool_s']),
            'candidate_first_tool_s': median(rb, lambda r: r['first_tool_s']),
            'baseline_prompt_tokens': [r.get('actual_prompt_tokens') for r in ra],
            'candidate_prompt_tokens': [r.get('actual_prompt_tokens') for r in rb],
            'logit_state_gate': 'not_performed_by_this_output_comparator',
            'baseline_decode_tps_median': median(ra, lambda r: r['timings'].get('predicted_per_second')),
            'candidate_decode_tps_median': median(rb, lambda r: r['timings'].get('predicted_per_second')),
            'identical_outputs': sum(x['output_sha256'] == y['output_sha256'] for x, y in zip(ra, rb)),
            'baseline_tool_correct': [r['tool_correct'] for r in ra if 'tool_correct' in r],
            'candidate_tool_correct': [r['tool_correct'] for r in rb if 'tool_correct' in r],
            'all_streams_completed': all(r['done'] for r in ra + rb),
            'baseline_generated': [r['timings'].get('predicted_n') for r in ra],
            'candidate_generated': [r['timings'].get('predicted_n') for r in rb]})
    return output


def validate_manifests(paths):
    manifests = [json.loads(Path(p).with_name('manifest.json').read_text(encoding='utf-8')) for p in paths]
    runtimes = [json.loads(Path(p).parent.parent.joinpath('runtime.json').read_text(encoding='utf-8')) for p in paths]
    if runtimes[0]['model_sha256'] != runtimes[1]['model_sha256']:
        raise ValueError('Different target model hashes')
    if any(m.get('logprobs_probe') for m in manifests):
        raise ValueError('Logprob probes must not be used as performance comparisons')
    for key in ('thinking', 'temperature', 'logprobs_probe', 'multi_turn', 'repeats', 'max_tokens',
                'prefix_tokens_requested', 'prefix_sha256', 'script_sha256'):
        if manifests[0].get(key) != manifests[1].get(key):
            raise ValueError('Different benchmark setting: ' + key)
    for key in ('n_ctx',):
        values = [m['props']['default_generation_settings'][key] for m in manifests]
        if values[0] != values[1]:
            raise ValueError('Different server context')
    allowed_env_variants = {'GGML_CUDA_QWEN4B_Q4K_OCC12'}
    invariant_envs = [{k: v for k, v in r['env'].items() if k not in allowed_env_variants} for r in runtimes]
    if invariant_envs[0] != invariant_envs[1]:
        raise ValueError('Different unapproved server environment')
    # Runtime DLL hashes may differ intentionally (kernel candidate), but target flags must not.
    variant_options = {'-md', '--spec-type', '-ngld', '-ctkd', '-ctvd',
                       '--spec-draft-n-max', '--spec-draft-n-min', '--spec-draft-p-min',
                       '--slot-save-path', '--log-file', '--port'}
    def target_flags(command):
        result = []
        i = 1
        while i < len(command):
            if command[i] in variant_options:
                i += 2
            else:
                result.append(command[i])
                i += 1
        return result
    if target_flags(runtimes[0]['command']) != target_flags(runtimes[1]['command']):
        raise ValueError('Different target runtime flags')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline')
    parser.add_argument('candidate')
    args = parser.parse_args()
    validate_manifests([args.baseline, args.candidate])
    print(json.dumps(compare(load(args.baseline), load(args.candidate)), indent=2))


if __name__ == '__main__':
    main()
