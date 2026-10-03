from checkpoint_daily_common import *
import time
out=BASE/'checkpoint_daily_20261003';out.mkdir(exist_ok=False)
folder=out/'probe';folder.mkdir();ensure_free()
r={'status':'running','exe_sha256':sha(CFG['exe']),'config_sha256':sha(DAILY/'strata-2080ti-sota.json'),'args':CFG['args']};write(folder/'results.json',r)
e=engine(folder,readout=True)
try:
    e.restart();r['info']=dict(e.info);assert e.max_context==262144
    clear_dump(folder)
    generated=[x for x in e.generate(WARM,32,{'temperature':0},threading.Event()) if x is not None]
    text=decode(generated);r['warm']={'content':text,**e.last,'oracle_pass':oracle(text,e.last['finish'],{'ready':True})}
    assert r['warm']['oracle_pass']
    row=first_row(folder,len(WARM));r['readout']={'vocab':len(row),'finite':True}
    r['chunk_events']=chunk_events(folder/'engine.log');r['status']='completed'
finally:
    e.close();write(folder/'results.json',r)
print(json.dumps(r,indent=2))
