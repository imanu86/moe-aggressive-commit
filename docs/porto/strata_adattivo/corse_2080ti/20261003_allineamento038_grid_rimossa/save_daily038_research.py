"""Publish measured metadata, portable patch and scripts; retain raw logits privately."""
from pathlib import Path
import json,hashlib,shutil,statistics,subprocess
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';REPO=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit');AREA=REPO/'docs/porto/strata_adattivo';OUT=AREA/'corse_2080ti/20261003_allineamento038_grid_rimossa'
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True,encoding='utf-8',errors='replace').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
print(git('branch','--show-current'),git('status','--short','--branch'),flush=True)
assert git('branch','--show-current')=='research/ds4-iq1-subbit-tier-planner'
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
installation=json.loads((R/'daily-installation.json').read_text());smoke=json.loads((R/'installed-startup/esito.json').read_text());release=json.loads((R/'release-publication.json').read_text());speed=json.loads((R/'speed-summary.json').read_text());dialogue=json.loads((R/'dialogue-r1/results.json').read_text());parity=json.loads((R/'parity-r1/results.json').read_text())
assert smoke['status']=='completed' and smoke['smoke']['oracle_pass'];assert installation['exe_sha256']==release['exe_sha256']==smoke['exe_sha256']
OUT.mkdir(exist_ok=False)
(OUT/'.gitattributes').write_text('* -text\n*.patch -whitespace\n',encoding='utf-8',newline='\n')
for name in ['build-base.json','build-wide.json','old-qa-build.json','pr603-provenance.json','patch-provenance.json','038-sm75-elastica-tail-wide.patch','pr603.patch','qa-readout-base.patch','qa-readout-wide.patch','speed-summary.json','main-prepared.json','daily-installation.json','release-publication.json','ctest-base.log','ctest-wide.log','topk-wide-selftest.log','pool-quant-base.log','pool-quant-wide.log','server-tests.log','build-topk-base.log','topk-base-build.json']:
    shutil.copy2(R/name,OUT/name)
for directory in ('parity-r1','dialogue-r1','topk-bench-r1','speed-r1','installed-startup'):
    for src in (R/directory).rglob('*'):
        if src.is_file() and (src.suffix in ('.json','.jsonl','.log') or src.name.endswith('.ids.json')):
            rel=src.relative_to(R);dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
for name in ['prepare_daily038_alignment.py','finish_daily038_source.py','build_daily038_alignment.py','prepare_wide038.py','build_old_daily_qa038_alignment.py','build_topk_base038.py','bench_topk038_alignment.py','prepare_alignment_tests.py','test_daily038_alignment_parity.py','test_daily038_alignment_dialogue.py','prepare_speed038_alignment.py','test_daily038_alignment_speed.py','summarize_daily038_speed.py','prepare_daily038_patch.py','integrate_daily038_main.py','install_daily038_alignment.py','check_installed038.py','publish_release038_alignment.py','save_daily038_research.py']:
    shutil.copy2(B/name,OUT/name)
fixture=Path(B/'checkpoint_daily_20261003/paired-r2')
for depth in (131072,250000):shutil.copy2(fixture/f'{depth}-fresh.ids.json',OUT/f'{depth}-fresh.ids.json')
OLD=B/'checkpoint038_20261003/model-tests-r3'
for name in ('fresh','follow'):shutil.copy2(OLD/f'{name}.ids.json',OUT/f'{name}.ids.json')
metadata={'status':'completed','upstream':'99f3dbd0b21d1401b3769e0c0d963913607f380b','installation':installation,'startup':smoke,'release':release,'paired_gate':parity['gate_pass'],'paired_oracles':parity['oracle_pass'],'teacher_rows_per_arm':2560,'scored_positions_per_arm':2557,'paired_comparisons':parity['comparisons'],'reference_repeat':parity['reference_repeat'],'daily_dialogue':dialogue,'isolated_pr603':speed,'source_and_binary_match':True,'dependency_ggml_commit':'3cf03257f219afbe7334045ff7c6a06ac68c627d','private_raw_logits':'binary float dumps and binaries retained in laboratory; not copied to Git','author_provenance':json.loads((R/'patch-provenance.json').read_text()),'artificial_pressure':False}
(OUT/'validation.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
rows=[]
for depth in (131072,250000):
    fresh=next(x for x in dialogue['requests'] if x['name']==f'{depth}-fresh');long=next(x for x in dialogue['requests'] if x['name']==f'{depth}-long')
    rows.append(f"| {depth} | {fresh['prompt_read']*1000/fresh['prompt_ms']:.2f} | {long['generated']*1000/long['decode_ms']:.3f} | {long['input_tokens']} | {long['generated']} |")
st=speed['timing']['250000-fresh']['arms'];tps=[x['prompt_read']*1000/x['prompt_ms'] for x in st];baseline=statistics.mean([tps[0],tps[2]]);gain=(tps[1]/baseline-1)*100;spread=abs(tps[0]-tps[2])/baseline*100
report=f'''# Daily0.1.38: grid rimossa, tail ed elastica, top-k largo — 3 ottobre2026

Il Daily operativo e il fork `main` sono allineati a upstream0.1.38,
`99f3dbd0b21d1401b3769e0c0d963913607f380b`. La storia upstream è raggiungibile;
i sorgenti completi provati sono importati con manifest distinto. Commit operativo:
`{installation['daily_head']}`. La grid originale è assente da header, implementazione
e chiamante; i FAIL precedenti rimangono conservati. Il checkpoint tail salva un
confine di chunk già esistente vicino alla fine, senza tagliare diversamente il prefill.

Conservati elastica automatica a core fisso/tail VMM, SM75 HC/GDN FP16, dequant
vettoriale e budget dei buffer propri; seriale per la quantizzazione intermedia.
Il nostro active-bound top-k512 è già upstream. Integrata la PR603 di asp345/Opus5.5
al commit6ba96984ac8a5f019edd84d7a83c278e6a1d363d, dopo verifica sulla nostra scheda.
Tail: Codex/PR614; elastica originale: Claude Opus, port/guardie Codex. Non viene
pubblicata una seconda PRelastica sovrapposta a37/378/563 e al piano533.

## Misure con impostazioni automatiche del Daily

Windows, RTX2080Ti **modificata22GB**, Ryzen5800X/AVX2,96GB RAM, CUDA12.6,
IQ3_XXS, KV262144/int8, residenti32768, riserva1393MiB, cache e chunk automatici,
elastica attiva, tail attivo, checkpoint16384. Nessuna pressione artificiale.
La CLI conserva `--spec 4`; con `auto` upstream038 dichiara a runtime spec6,
MTPmax4, lookup3 e PCIe0.36. Nel test controllato sotto i valori effettivi sono
spec4, MTPmax0/lookup0, PCIe0.28: sono due profili distinti.

| Input fresh reale | Prefill fresh t/s | Decode lungo t/s | Input del decode lungo | Output lungo |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

Sono singoli campioni del nuovo Daily, con cache/MTP e attività desktop variabili:
non costituiscono un guadagno causale su0136 o una curva completa KV/t/s.
Conversazione: recupero tre record a profondità diverse, vero turno assistant
chiuso, marcatore nuovo, guida1024token, marcatore distinto dopo il decode.
Entrambe le profondità: logits finiti,1024token/finish length, sei oracoli corretti.
Cache iniziale6339slot; crescita reale durante il test documentata nei log.

## PR603 isolata, profilo fisso250k

Stessa base038, stesso tail,5357slot, chunk8192, spec4 e intervalli reali lunghi
che disabilitano il resize nel confronto. A1/B/A2: prefill fresh
**{tps[0]:.2f}/{tps[1]:.2f}/{tps[2]:.2f} t/s**. Guadagno rispetto alla media A:
**{gain:+.2f}%**; spread A/A **{spread:.2f}%**. Tempi TTFT/decode, ID e risorse in
`corse_2080ti/20261003_allineamento038_grid_rimossa/speed-summary.json`.
Primi logits bitwise per tutte le quattro richieste e ripetizione A; tutte le
risposte generate {'identiche' if speed['all_output_ids_equal'] else 'con ID non tutti identici (dettagli nel report)'};
nove oracoli e tre decode1024passano. Un solo A/B/A, non uno studio statistico esteso.

Microbenchmark con identico driver e vere librerie baseline SM75, nessun override
`STRATA_TOPK_OLD`:256query a262144celle, mediana18.166→1.056ms, circa17.2x.
A131072celle la selezione prefill è sostanzialmente invariata. Le misure decode
sono più variabili; non trasferire il17.2x al motore completo.

## Correttezza e installazione

Old036/new038/old036, chunk2048 e5357slot:2560teacher rows/2557posizioni per
braccio sui corpora code/doc/chat, logits bitwise, KL0, top-1 agreement100%,
NLL/PPL invariati; sei recall completi corretti. Gate locale di regressione,
non una certificazione generale del modello. Caso0136 con grid e chunk2048
divisibile per16384 ha la stessa geometria; i vecchi test grid falliti non cambiano.
Sei CTest,18casi top-k (punteggi continui, livelli/tie, tutti uguali; prompt/decode
fino524288celle),64casi quantizzazione CPU bitwise con GGUF reale,118test server.

Eseguibile shipping `{installation['exe_sha256']}`. I binari QA aggiungono solo
il readout comune; quello installato e pubblicato non contiene l'hook di test.
Cartella: `{Path(installation['exe']).parent}`; server congelato completo della
stessa build. Configurazione e BAT desktop puntano lì, porta8100/127.0.0.1.
Health e nuovo JSON `DAILY-038-READY` passati sul vero shipping dopo installazione;
processi propri chiusi.{installation['untracked_preserved']}file non tracciati preservati; build0136 mantenuta.

Ripristino: `{installation['backup']}`. Per tornare al vecchio motore basta
ripristinare config e BAT dalla copia; la build0136con il suo server è intatta.
Non serve resettare la storia Git. Bundle e file locali sono salvati nel ripristino.

[Release verificata]({release['url']}) · [PRtail614](https://github.com/Niko1221/Strata/pull/614)
· [PRwide603](https://github.com/Niko1221/Strata/pull/603).
Nessun workflow aggiunto; nessuna misura stock11GB/multiGPU o banda DRAM fisica.
'''
(AREA/'ALLINEAMENTO_0138_GRID_RIMOSSA_3_OTTOBRE.md').write_text(report,encoding='utf-8',newline='\n')
handoff=AREA/'HANDOFF.md';old=handoff.read_text(encoding='utf-8');old=old.split('\n',1)[1]
intro=f'''# HANDOFF — Strata Daily0.1.38 SM75, grid rimossa, elastica/tail/top-k603, KV262k

- **3ottobre, Daily e main aggiornati:** upstream99f3dbd/0.1.38, commit
  {installation['daily_head'][:12]}. Grid originale rimossa; tail614abilitato,
  elastica e SM75conservati; top-k largo603validato/integrato, seriale.
  Numerica A/B/A2560righe/braccio bitwise/KL0/top-1100%; sei recall.
  Auto Daily131k/250k:1024token per profondità e6oracoli corretti.
  Prefill1027.01/833.50t/s; decode lungo36.913/39.065t/s, singoli campioni.
  Controllo603250k: {tps[0]:.2f}/{tps[1]:.2f}/{tps[2]:.2f}t/s,
  {gain:+.2f}% rispetto alla media A, spread{spread:.2f}%; logits bitwise.
  Shipping/BAT/config/server coerenti; health e JSON su8100passano,
  {installation['untracked_preserved']}untracked preservati, rollback0136disponibile. Release038pubblicata,
  nessun workflow. Motori chiusi; test senza pressione artificiale.
  [Dati, provenienza, limiti e ripristino](ALLINEAMENTO_0138_GRID_RIMOSSA_3_OTTOBRE.md).

## Stato storico (le note Daily invariato sotto si riferiscono ai giri precedenti)

'''
handoff.write_text(intro+old,encoding='utf-8',newline='\n')
LA=AREA/'lanciatori';shutil.copy2(Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json'),LA/'strata-2080ti-sota.json');bat=Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat');shutil.copy2(bat,LA/bat.name)
manifest={'files':{p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},'limits':'raw binary logits/model/binaries stay private; metadata includes exact SHA and complete output IDs; historical evidence unchanged'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
changed=[p.relative_to(REPO).as_posix() for p in OUT.rglob('*') if p.is_file()]+[(AREA/'ALLINEAMENTO_0138_GRID_RIMOSSA_3_OTTOBRE.md').relative_to(REPO).as_posix(),handoff.relative_to(REPO).as_posix(),(LA/'strata-2080ti-sota.json').relative_to(REPO).as_posix(),(LA/bat.name).relative_to(REPO).as_posix()]
pathfile=R/'stage-research.paths';pathfile.write_bytes(b''.join(x.encode()+b'\0' for x in sorted(set(changed))))
subprocess.run(['git','add','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul'],cwd=REPO,check=True)
for rel,h in manifest['files'].items():
    staged=subprocess.check_output(['git','show',':'+(OUT/rel).relative_to(REPO).as_posix()],cwd=REPO);assert hashlib.sha256(staged).hexdigest()==h,rel
print('Verified staged research evidence',len(changed),'paths',flush=True)
