from pathlib import Path
import datetime, hashlib, json, shutil, subprocess, sys
sys.path.insert(0,r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages')
import psutil
BASE=Path(__file__).resolve().parent; R=BASE/'retest_pr512_20261003'
REPO=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
AREA=REPO/'docs/porto/strata_adattivo'
def git(*args):
    return subprocess.run(['git','-c','safe.directory='+REPO.as_posix(),'-C',str(REPO),*args],capture_output=True,text=True,check=True)
assert git('branch','--show-current').stdout.strip()=='research/ds4-iq1-subbit-tier-planner'
status=git('status','--short','--branch').stdout
recovery=R/'documentation-recovery'; recovery.mkdir(exist_ok=False)
(recovery/'status-before.txt').write_text(status)
shutil.copy2(AREA/'HANDOFF.md',recovery/'HANDOFF.before.md')
assert not any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name']))
final={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'model_process_count':0,'ram_available_gib':psutil.virtual_memory().available/2**30,
       'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu','--format=csv,noheader'],text=True).strip(),
       'daily_installed':False}
(R/'final-state.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
s=json.loads((R/'analysis.json').read_text()); a=s['arms']
dest=AREA/'corse_2080ti/20261003_pr512_ripetizione'; dest.mkdir(exist_ok=False)
selected=[]
for p in R.rglob('*'):
    if p.is_file() and p.suffix in ('.json','.jsonl','.log','.py') and 'cuda-cache' not in p.parts and 'documentation-recovery' not in p.parts:
        selected.append((p,p.relative_to(R)))
selected.extend((BASE/name,Path('strumenti')/name) for name in ['retest_pr512.py','analyze_pr512_retest.py','save_pr512_retest.py'])
hashes={}
for source,rel in selected:
    target=dest/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
    hashes[rel.as_posix()]=hashlib.sha256(target.read_bytes()).hexdigest()
(dest/'manifest.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
(dest/'.gitattributes').write_text('* -text\n')
doc=f'''# PR512: integrazione upstream e ripetizione del 3 ottobre 2026

La patch top-k è stata integrata manualmente nella release upstream 0.1.38, autore imanu86,
commit [474a94b](https://github.com/Niko1221/Strata/commit/474a94bfdc68dc1ef473b7d9df50521b253e04e4),
con Co-Authored-By Codex. Il [commento del maintainer](https://github.com/Niko1221/Strata/pull/512#issuecomment-5964019532)
spiega perché GitHub non presenta la PR come merged. Il successivo flag STRATA_TOPK_ACTIVE_ANY=1 permette
al test di attivare il percorso anche su altre GPU; non cambia il default Turing del motore.

## Ripetizione isolata

RTX2080Ti modificata22GB, Ryzen5800X,96GB RAM,Windows,CUDA12.6. **Stesso eseguibile della prova precedente:**
upstream0.1.37 db4f91a1171d697928b0d2e1f50ef95e25559d4c più le sole quattro modifiche della PR512.
Questa ripetizione non è una build completa0.1.38. SHA256 motore: `{s['exe_sha256']}`.

Capacità/attivi/capacità A/B/A; KV262144 int8, resident32768; PCIe0.28, prefillauto,
spec4 con lookup3, stesso profilo esperti; cache fissa budget4000, **5357 slot effettivi** in tutte le braccia.
Nessuna elasticità e nessun carico artificiale. CUDA cache condivisa tra le braccia.
Due output da1024 token per braccio: prompt fresco131248 e follow-up131239 con131072 token riusati.

| Percorso | Prefill fresco t/s | TTFT s | Decode aggregato t/s |
|---|---:|---:|---:|
| Capacità A1 | {a['A1']['prefill_tps']:.2f} | {a['A1']['ttft_s']:.3f} | {a['A1']['decode_tps']:.3f} |
| Attivi B | {a['B']['prefill_tps']:.2f} | {a['B']['ttft_s']:.3f} | {a['B']['decode_tps']:.3f} |
| Capacità A2 | {a['A2']['prefill_tps']:.2f} | {a['A2']['ttft_s']:.3f} | {a['A2']['decode_tps']:.3f} |

**Prefill +{s['active_gain_percent']:.2f}%** sulla media dei riferimenti; spread dei riferimenti
**{s['reference_spread_percent']:.2f}%**. TTFT ridotto di **{s['ttft_saved_s']:.2f}s**.
Guadagno osservato in questo A/B/A; nessun guadagno decode attribuito alla patch.
Parità del kernel: **16/16**, ID selezionati identici bit per bit. Sei richieste lunghe completate.
Il corpus dei tempi non contiene un nuovo oracle numerico dell'intero modello e non dimostra qualità generale.

## Controllo dei carichi

Monitor circa ogni10s: CPU totale/per-thread, processi, RAM libera, I/O disco, GPU/VRAM/clock/temperatura.
Le finestre prefill sono derivate da `history.time = started` nel server e da prompt_ms: 15/14/15 campioni.
Durante i prefill: RAM libera almeno21.3GiB, VRAM nvidia-smi3269MiB libera, GPU quasi sempre99–100%,
CPU totale17.7–25.6%, altro CPU incluse le utility della prova al massimo7.3% della macchina.
Clock memoria6800MHz; medianaSM1815/1777.5/1785MHz, massimo65°C. Non è stata osservata saturazione globale
esterna nei campioni; un contatore GPU aggregato non separa ogni applicazione. I/O lettura mediano
42.7/25.5/23.3MiB/s, inclusa la lettura PLE del modello; non è una misura isolata del disco delle altre app.
Le misure precedenti457.26/521.45/774.41 restano conservate e inconcludenti: questa ripetizione
non identifica retroattivamente la causa dei valori bassi.

## Contributi ulteriori

- **Cache elastica:** API CUDA VMM open_sized_elastic/grow/shrink, indirizzi stabili per i graph,
  margine VRAM e isteresi, core stabile e coda ridimensionabile. Presente nel nostro fork, assente
  dalle API expert_cache e dall'opzione --elastic in generate.cpp della0.1.38 controllata.
  Candidato concreto per una PR separata; serve un port minimo su upstream e una verifica specifica
  di crescita/riduzione, dati degli esperti, fallback e sincronizzazione. Nessuna pressione artificiale richiesta.
- **Strumenti di parità e benchmark riproducibili:** riutilizzabili per valutare cache e kernel.
- HC/GDN FP16 e vector dequant provengono da jklnvlink: preservare l'attribuzione; non presentarli come invenzioni nostre.
- Il top-k dinamico decode sperimentale non ha superato il gate prestazionale: non proporlo come guadagno confermato.

**Nessuna nuova SOTA del Daily:** questa è una prova upstream con cache fissa e senza gli altri port Turing.
Il Daily operativo resta invariato. Motori chiusi; RAM libera finale{final['ram_available_gib']:.1f}GiB.

Evidenze locali: [manifest](corse_2080ti/20261003_pr512_ripetizione/manifest.json),
[analisi](corse_2080ti/20261003_pr512_ripetizione/analysis.json),
[confronto completo](corse_2080ti/20261003_pr512_ripetizione/comparison.json),
[risorse](corse_2080ti/20261003_pr512_ripetizione/resources.jsonl).
'''
path=AREA/'PR512_RIPETIZIONE_3_OTTOBRE.md'; assert not path.exists(); path.write_text(doc,encoding='utf-8')
handoff=AREA/'HANDOFF.md'; text=handoff.read_text(encoding='utf-8')
lines=text.splitlines(keepends=True)
entry='\n- **3 ottobre: PR512 integrata upstream0.1.38; ripetizione isolata +7,46% prefill, spread riferimenti0,54%, parità16/16.** [Dati e limiti](PR512_RIPETIZIONE_3_OTTOBRE.md). Daily invariato.\n'
handoff.write_text(''.join(lines[:1])+entry+''.join(lines[1:]),encoding='utf-8')
for rel,digest in hashes.items(): assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==digest
print(json.dumps({'report':str(path),'evidence_files_verified':len(hashes),'final':final},indent=2))
