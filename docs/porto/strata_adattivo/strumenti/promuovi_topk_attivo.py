"""Promuove la candidata top-k esatta solo dopo A/B/A e retrieval/decode250k.

Installa un bundle nuovo, conserva il daily precedente e crea il ripristino
di configurazione e lanciatore prima di qualsiasi sostituzione operativa.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

BASE = Path(r'D:\ds4_work\strata\Strata')
AREA = Path(__file__).resolve().parent.parent
REPO = AREA.parents[2]
OLD_SHA = 'a74e4dadcd4fbb9e71b5cb0ae66922453c6a44a2704db25ddfb5e81601c5f766'
NEW_SHA = 'f469e096e868e4579daaec71ceef63693790e300e7a4cc5b49a8853d075a1d34'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--aba', type=Path, required=True)
    ap.add_argument('--quality', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    for root, branch in [(REPO, 'research/ds4-iq1-subbit-tier-planner'), (BASE, 'main')]:
        found = subprocess.check_output(['git', 'branch', '--show-current'], cwd=root, text=True).strip()
        assert found == branch, (str(root), found)
        print('BRANCH', root, found)
        subprocess.run(['git', 'status', '--short', '--branch', '-uno'], cwd=root, check=True)
    sys.path.insert(0, str(BASE/'.venv/Lib/site-packages'))
    import psutil
    assert not any((p.info['name'] or '').lower() in ('strata.exe', 'llama-server.exe')
                   for p in psutil.process_iter(['name'])), 'Motore attivo: promozione non eseguita'
    candidate = a.candidate.resolve(strict=True)
    assert sha(candidate/'strata.exe') == NEW_SHA
    build = json.loads((candidate/'build-result.json').read_text(encoding='utf-8'))
    assert build['exe_sha256'] == NEW_SHA and build['base_exe_sha256'] == OLD_SHA
    for name, expected in build['source_sha256'].items():
        assert sha(candidate/'source'/name) == expected, name
    aba = json.loads(a.aba.read_text(encoding='utf-8'))
    assert aba['prefill']['benefit_demonstrated']
    assert all(r['exe_sha256'] == NEW_SHA for r in aba['runs'].values())
    quality = json.loads((a.quality/'esito.json').read_text(encoding='utf-8'))
    assert quality['status'] == 'completed' and quality['exe_sha256'] == NEW_SHA
    assert quality['kv_capacity'] == 262144 and quality['topk_mode'] == 'active'
    assert len(quality['needles']) == 3 and all(r['found'] for r in quality['needles'])
    retrieval = quality['retrieval_250k']
    assert retrieval['found'] and retrieval['capacity_validated']
    decode = retrieval['decode_after']
    assert decode['robust'] and decode['requested_output_tokens'] == 1024
    assert decode['engine_request']['prompt_tokens'] >= 250000
    native = json.loads((REPO/'.codex_runs/20261002_topk_active_paired/result.json').read_text(encoding='utf-8'))
    assert len(native['steps']) == 17 and all(r['exit'] == 0 for r in native['steps'])
    config = BASE/'strata-2080ti-sota.json'
    bat = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
    repo_config = AREA/'lanciatori/strata-2080ti-sota.json'
    repo_bat = AREA/'lanciatori'/bat.name
    assert config.read_bytes() == repo_config.read_bytes()
    assert bat.read_bytes() == repo_bat.read_bytes()
    cfg = json.loads(config.read_text(encoding='utf-8-sig'))
    assert sha(Path(cfg['exe'])) == OLD_SHA
    assert '--elastic' in cfg['args']
    for flag, expected in [('--max-context', '262144'), ('--kv', 'int8'), ('--kv-resident', '32768'),
                           ('--expert-cache', 'auto'), ('--prefill', 'auto'), ('--vram-reserve-mib', '1393')]:
        assert cfg['args'][cfg['args'].index(flag)+1] == expected, flag
    assert not any(key in cfg.get('env', {}) for key in ['STRATA_TOPK_OLD', 'STRATA_TOPK_CAPACITY_GUARD', 'STRATA_API_KEY'])
    before_bat = bat.read_bytes().decode('utf-8')
    # Commento, controllo exe, errore e percorso server devono puntare insieme
    # alla build promossa, evitando un lanciatore con controlli della vecchia.
    assert before_bat.count('build-0131-daily') == 4
    installed = BASE/'build-0131-topk-active'
    assert not installed.exists(), 'Non sovrascrivere una build esistente'
    out = a.out.resolve()
    out.mkdir(exist_ok=False)
    backup = BASE.parent/'ripristini'/(time.strftime('%Y%m%d_%H%M%S')+'_0131_topk_active')
    backup.mkdir(parents=True, exist_ok=False)
    for original, name in [(config, 'config-operativo.json'), (bat, 'lanciatore-operativo.bat'),
                           (repo_config, 'config-repository.json'), (repo_bat, 'lanciatore-repository.bat')]:
        shutil.copy2(original, backup/name)
        assert sha(original) == sha(backup/name)
    shutil.copytree(candidate, installed)
    assert sha(installed/'strata.exe') == NEW_SHA
    for name, expected in build['source_sha256'].items():
        assert sha(installed/'source'/name) == expected
    cfg['exe'] = str(installed/'strata.exe')
    new_config = (json.dumps(cfg, indent=2)+'\n').encode('utf-8')
    new_bat = before_bat.replace('build-0131-daily', 'build-0131-topk-active')
    new_bat = new_bat.replace("rem Strata daily validata l'1/10/2026:", 'rem Strata daily validata il 2/10/2026:')
    new_bat = new_bat.replace(' + vector + PR315.', ' + vector + PR315 + top-k attivo.')
    new_bat = new_bat.replace('PROMOZIONE_DAILY_0131_1_OTTOBRE.md', 'RISULTATI_TOPK_2_OTTOBRE.md').encode('utf-8')
    # Backup e bundle verificati; le quattro sostituzioni sono sequenziali.
    for target, content in [(config, new_config), (bat, new_bat), (repo_config, new_config), (repo_bat, new_bat)]:
        temporary = target.with_name(target.name+'.codex-topk.tmp')
        assert not temporary.exists()
        temporary.write_bytes(content)
        os.replace(temporary, target)
        assert target.read_bytes() == content
    result = {'installed': str(installed), 'backup': str(backup), 'exe_sha256': NEW_SHA,
              'previous_exe_sha256': OLD_SHA, 'config_sha256': sha(config), 'bat_sha256': sha(bat),
              'kv_capacity': 262144, 'elastic_preserved': '--elastic' in cfg['args'],
              'prefill_aba': aba['prefill'], 'quality_passed': True,
              'rollback': 'Ripristinare config-operativo.json e lanciatore-operativo.bat nei percorsi originali, e le due copie repository.'}
    assert result['elastic_preserved']
    (out/'promotion.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    (backup/'promotion.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
