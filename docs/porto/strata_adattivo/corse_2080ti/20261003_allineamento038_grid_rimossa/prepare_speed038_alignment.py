from pathlib import Path
B=Path(__file__).resolve().parent
d=(B/'test_daily038_alignment_dialogue.py').read_text()
d=d.replace("OUT=R/'dialogue-r1'","label=sys.argv[1];assert label in ('A1','B','A2');OUT=R/'speed-r1'/label;OUT.parent.mkdir(exist_ok=True);OUT=OUT")
d=d.replace("args=list(cfg['args'])+['--prompt-cache-tail','--prompt-cache-every','16384']","args=list(parity['plan']['args'])+['--prompt-cache-tail'];args=V.set_arg(args,'--prefill',8192)")
d=d.replace("str(R/'strata-qa-wide.exe')","str(R/('strata-qa-wide.exe' if label=='B' else 'strata-qa-base.exe'))")
d=d.replace("V.sha(R/'strata-qa-wide.exe')","V.sha(R/('strata-qa-wide.exe' if label=='B' else 'strata-qa-base.exe'))")
d=d.replace("'contexts':[131072,250000]","'contexts':[250000],'arm':label,'fixed_expert_placement':5357,'fixed_prefill':8192,'fixed_spec':4,'purpose':'same aligned038 source and geometry; isolated PR603 at250k, A/B/A'")
d=d.replace("for depth in (131072,250000):","for depth in (250000,):")
d=d.replace("result['startup_info']=dict(e.info);save()","result['startup_info']=dict(e.info);assert int(e.info['expert_slots'])==5357;save()")
(B/'test_daily038_alignment_speed.py').write_text(d,encoding='utf-8',newline='\n')
print('Controlled250k A/B/A runner ready')
