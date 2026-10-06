"""Daily 0.1.40-r1, passo 4: manifest e registro di validazione del motore provato - SOLO nella cartella della release.

A differenza di manifest0139r2.py questo script NON tocca il repository del fork (niente scritture nel working tree, niente
commit, niente push): prepara in daily0140_20261006/manifest-out/ i file che andranno nel fork
  docs/sm75/source-manifest.json, validation.json, source-manifest-0139r2.json, validation-0139r2.json, VALIDATION.md
piu' il messaggio di commit gia' scritto (commit-message.txt).  Il manifest 0.1.39-r2 e la sua validazione restano come
-0139r2; i manifest storici sono riportati con il loro hash.  check_source.py (gia' corretto in 0.1.39-r2: legge prima
source-manifest.json) non cambia.

La verifica gira su una copia temporanea dell'export congelato (source/) con sopra i file preparati: check_source.py deve
stampare `SOURCE_OK ... current 0.1.40-r1`.  La copia (in %TEMP%\v0140, percorso corto) viene cancellata.  validation-results.json e' generato qui dai log di
build e check: dice solo cio' che e' stato provato (niente velocita' misurate da questa procedura).
"""
import hashlib, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0140_20261006'
S = R / 'source'
OUT = R / 'manifest-out'
DOCS_REL = 'docs/sm75'
CO = 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>'
LABEL = '0.1.40-r1'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


prep = json.loads((R / 'preparation.json').read_text())
build = json.loads((R / 'build.json').read_text())
check = json.loads((R / 'check.json').read_text())
rec = json.loads((R / 'recovery.json').read_text())
assert check['status'] == 'ok', check['status']   # nessun fallimento accettato a mano
assert prep['fork_head'] == build['fork_head'] == check['fork_head'] == rec['fork_head']
assert sha(R / 'strata.exe') == build['shipping_exe_sha256'] == sha(R / 'build/strata.exe')
assert not OUT.exists() or '--resume' in sys.argv, 'manifest-out exists'
OUT.mkdir(exist_ok=True)
DOCS = S / DOCS_REL
ODOCS = OUT / DOCS_REL
ODOCS.mkdir(parents=True, exist_ok=True)

ggml = re.search(r'GIT_TAG\s+([0-9a-f]{40})', (S / 'CMakeLists.txt').read_text(encoding='utf-8')).group(1)
assert ggml == '3cf03257f219afbe7334045ff7c6a06ac68c627d'

old = json.loads((DOCS / 'source-manifest.json').read_text())
assert old['snapshot_version'] == '0.1.39-r2'
shutil.copyfile(DOCS / 'source-manifest.json', ODOCS / 'source-manifest-0139r2.json')
shutil.copyfile(DOCS / 'validation.json', ODOCS / 'validation-0139r2.json')
historical = dict(old['historical_manifests'])
historical['source-manifest-0139.json'] = sha(DOCS / 'source-manifest-0139.json')
for name, h in historical.items():
    assert sha(DOCS / name) == h, name

# validation-results.json: solo cio' che questa procedura ha provato
ct, st = check['ctest'], check['server_tests']
server_ran = int(re.search(r'Ran (\d+)', st['summary'][0]).group(1))
server_skipped = int(re.search(r'skipped=(\d+)', st['summary'][1]).group(1))
server_failed = len(st['failed'])
assert set(st['failed']) <= set(st['known']), st['failed']
val = dict(
    scope='preparazione: compilato si, CTest si, installato no, provato sul server no; nessun benchmark di velocita\' in questa procedura',
    checks=dict(
        ctest=f"{ct['passed']} su {ct['total']} passati; {len(ct['failed_tests'])} non riusciti per cause ambientali note di questa macchina "
              f"({', '.join(ct['known_failures_seen'])}: modello a percorso relativo, CPU senza AVX512); {len(ct['skipped_tests'])} saltati "
              f"({', '.join(n.split(' ')[0] for n in ct['skipped_tests'])}: servono GPU sm_80 o piu' recenti)",
        pool_quant_parity='GGUF reale: ' + check['pool_quant_parity']['last'][0],
        server_tests=f"{server_ran - server_failed - server_skipped} ok su {server_ran} ({server_skipped} saltati); non riusciti: "
                     + (', '.join(st['failed']) or 'nessuno') + " (test_winjob: tasklist letto come UTF-8 su Windows italiano, noto)",
        build=build['configure']),
    limitations=[
        'eseguibile non installato e non avviato dal server in questa procedura: nessun controllo di salute, nessun oracolo JSON',
        'nessuna misura di velocita\' a 131k su questo eseguibile; i valori di 0.1.39-r2 non si applicano senza nuova misura',
        'il prefisso su disco da 64K (96e2cdc), il riprovare un arena piu piccola (df97358) e la correzione --batch-mtp (0cc421e, il Daily '
        'non usa --batch) sono provati nei commit con i banchi del laboratorio, non con la configurazione completa del Daily',
        'la configurazione proposta non include --pcie-mode dma, --pool-tasks 96 e STRATA_ELASTIC_CORE_ADAPT=1 della r2 mai installata'],
    release_bullets=[
        'upstream v0.1.40 (1735d64) unito nel fork con il port SM75',
        '0cc421e: --batch-mtp copia il tipo della testa del draft condivisa (il motore usciva alla prima ammissione; il Daily non usa --batch)',
        '96e2cdc: prefisso su disco fino a 64K token e 1,5 GB; cache elastica mantenuta con --batch',
        'a32b5e1: test_turns allineato alla semantica dei tag letterali di upstream #931',
        'df97358: la cache elastica riprova un arena piu piccola se cuMemCreate finisce la memoria, invece di ripiegare sulla cache fissa',
        'configurazione proposta: quella del Daily 0.1.39 (--elastic, --prompt-cache-file, --ple-row-cache 16777216) con il nuovo eseguibile, senza --batch'])
val['markdown'] = (
    f"## Daily {LABEL} - 6 ottobre 2026 (preparato, non installato)\n\n"
    f"Sorgente del fork `{prep['fork_head'][:7]}` (upstream v0.1.40 `1735d64` + port SM75 + correzione `--batch-mtp` `0cc421e` + prefisso su disco da 64K e "
    f"cache elastica col batch `96e2cdc` + `test_turns` `a32b5e1` + arena elastica piu' piccola su memoria esaurita `df97358`). Compilato `Release` sm_75, eseguibile `{build['shipping_exe_sha256'][:12]}`. "
    f"CTest: {val['checks']['ctest']}. `pool_quant_parity` sul GGUF reale: passa. Test server: {val['checks']['server_tests']}. "
    "Configurazione proposta: quella del Daily 0.1.39 con il nuovo eseguibile, senza `--batch`. Non installato, non avviato, nessuna misura di velocita'. "
    "Dettagli: `validation.json`.")
(R / 'validation-results.json').write_text(json.dumps(val, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

overrides = [f'{DOCS_REL}/{n}' for n in ('source-manifest.json', 'validation.json', 'source-manifest-0139r2.json',
                                         'validation-0139r2.json', 'VALIDATION.md')]
manifest = dict(snapshot_upstream_commit=prep['upstream'], snapshot_version=LABEL, fork_commit=prep['fork_head'],
                validated_executable_sha256=build['shipping_exe_sha256'], previous_manifest='source-manifest-0139r2.json',
                previous_manifest_sha256=sha(ODOCS / 'source-manifest-0139r2.json'), historical_manifests=historical,
                publication_overrides=overrides, dependency_ggml_commit=ggml,
                meaning='complete tested source export (git archive of fork_commit) with explicit publication overrides; '
                        'no workflow; old source manifests preserved; prepared, not installed',
                files=prep['files'])
(ODOCS / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
validation = dict(date='2026-10-06', upstream_commit=prep['upstream'], version=LABEL, fork_commit=prep['fork_head'],
                  executable_sha256=build['shipping_exe_sha256'], build=build['steps'], **val)
(ODOCS / 'validation.json').write_text(json.dumps(validation, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
vm = (DOCS / 'VALIDATION.md').read_text(encoding='utf-8')
(ODOCS / 'VALIDATION.md').write_text(vm.rstrip('\n') + '\n\n' + val['markdown'] + '\n', encoding='utf-8', newline='\n')
msg = (f"OPUS-DEPLOY-Registra manifest e validazione del Daily {LABEL}\n\n"
       f"Sorgente congelato {prep['fork_head'][:8]} (upstream v0.1.40, prefisso su disco da 64K, arena elastica piu' piccola su memoria esaurita), eseguibile shipping "
       f"{build['shipping_exe_sha256'][:12]}; manifest 0.1.39-r2 conservato come -0139r2.\n\n" + CO + '\n')
(OUT / 'commit-message.txt').write_text(msg, encoding='utf-8', newline='\n')

# verifica su una copia temporanea dell'export congelato + i file preparati
tmp = Path(tempfile.gettempdir()) / 'v0140'   # short path: the export has paths near the 260-character limit
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(S, tmp)
try:
    for f in ODOCS.iterdir():
        shutil.copyfile(f, tmp / DOCS_REL / f.name)
    chk = subprocess.run([sys.executable, '-B', str(tmp / 'tools/sm75/check_source.py')], cwd=tmp, capture_output=True, text=True)
    print(chk.stdout, chk.stderr)
    assert chk.returncode == 0 and f'current {LABEL}' in chk.stdout
    verify = chk.stdout.strip()
finally:
    shutil.rmtree(tmp)
(OUT / 'verifica-check_source.txt').write_text(verify + '\n', encoding='utf-8')
(OUT / 'COME-APPLICARE.txt').write_text(
    "Copiare i 5 file di docs/sm75/ di questa cartella in docs/sm75/ del fork (main pulito, uguale a origin/main alla\n"
    f"{prep['fork_head'][:8]}), eseguire `python tools/sm75/check_source.py` (atteso: SOURCE_OK ... current {LABEL}),\n"
    "poi commit con commit-message.txt (git add con pathspec espliciti) e push. install0140.py richiede che il manifest\n"
    "pubblicato nel fork sia identico a quello di questa cartella.\n", encoding='utf-8')
print('MANIFEST READY (not committed)', sha(ODOCS / 'source-manifest.json'), flush=True)
