"""Analyze real 10x10 candidate replays and frozen-bank target GPU replays.

SNRv0002 has the SNRv0001 layout, but vectors 5..7 use external union masks;
its cold field means the expert was absent from that bank (full fallback).
This measures local expert outputs, not end-to-end pruned generation or t/s.
"""
import argparse, collections, hashlib, json, struct, time
from pathlib import Path
import numpy as np
import analyze_trace as A

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):digest.update(chunk)
    return digest.hexdigest()

ENTRY = np.dtype([('serial','<u8'),('pos','<i8'),('layer','<i4'),('expert','<i4'),
                  ('tier','<i4'),('gu','<i4'),('down','<i4'),('cold','<i4'),('weight','<f4'),
                  ('h','<f4',(640,)),('y','<f4',(8,2560))])
assert ENTRY.itemsize == 84524

def save(path, obj):
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')

def records(path, magic=b'SNRv0001'):
    with path.open('rb') as f:
        assert f.read(8) == magic
        assert struct.unpack('<4I4i',f.read(32)) == (2560,640,10,4,0,1,35,36)
    size = path.stat().st_size-40
    assert size > 0 and size % ENTRY.itemsize == 0
    arr = np.memmap(path,mode='r',dtype=ENTRY,offset=40,shape=(size//ENTRY.itemsize,))
    assert np.isfinite(arr['h']).all() and np.isfinite(arr['y']).all()
    return arr

def validate_trace(path):
    with path.open('rb') as f:
        rows, groups, _ = A.parse_trace(f)
    return {'entries': len(rows), 'positions': sorted({k[1] for k in rows}), 'groups':len(groups)}

def make_bank(replays, start, path):
    """Union top-|h| for each candidate invocation, separately at three widths."""
    began = time.monotonic(); bank={}; geos={}; n=0
    for replay in replays:
        data=records(replay)
        for row in data:
            if int(row['pos']) < start: continue  # last prefix row is not a candidate
            key=(int(row['layer']),int(row['expert']))
            if key not in bank: bank[key]=np.zeros((3,640),dtype=np.uint8)
            order=np.argsort(-np.abs(row['h']),kind='stable')
            for m,keep in enumerate((160,320,480)): bank[key][m,order[:keep]]=1
            geo=A.geometry(int(row['gu']),int(row['down']))
            assert key not in geos or geos[key]==geo
            geos[key]=geo; n+=1
    assert n==4000, ('must contain exactly 100 candidate positions x 4 layers x 10 experts',n)
    with path.open('xb') as f:
        f.write(b'SNM10001'+struct.pack('<II',640,len(bank)))
        for (layer,expert), masks in sorted(bank.items()):
            f.write(struct.pack('<ii',layer,expert)); f.write(masks.tobytes())
    stats=[]
    for m,keep in enumerate((160,320,480)):
        compact=full=neurons=blocks=indices=0
        for key,masks in bank.items():
            idx=np.flatnonzero(masks[m]); geo=geos[key]
            item=A.mask_footprint(idx,geo)
            compact+=item['weight_bytes'];full+=geo['full_expert_weight_bytes']
            neurons+=len(idx);blocks+=item['down_blocks_touched']
            indices+=2*len(idx)+2*item['down_blocks_touched']+16
        stats.append({'keep_per_candidate':keep,'unique_layer_experts':len(bank),
                      'retained_neurons':neurons,'down_blocks':blocks,
                      'weight_bytes_layout_estimate':compact,'full_weight_bytes':full,
                      'index_bytes_layout_estimate':indices,
                      'weight_fraction':compact/full,'fraction_with_indices':(compact+indices)/full})
    return bank, {'candidate_expert_calls':n,'mask_file_bytes':path.stat().st_size,
                  'mask_sha256':sha(path),'construction_cpu_s':time.monotonic()-began,'footprints':stats}

def evaluate(replay, bank, first_pos):
    data=records(replay,b'SNRv0002'); grouped=collections.defaultdict(list)
    for row in data:
        if row['pos']>=first_pos: grouped[(int(row['pos']),int(row['layer']))].append(row)
    by_pos=collections.defaultdict(list)
    for (pos,layer),rows in sorted(grouped.items()):
        assert len(rows)==10 and len({int(r['expert']) for r in rows})==10
        full=np.zeros(2560); reduced=np.zeros((3,2560)); missing=mass=0.; full_bytes=0
        traffic=np.zeros(3); energy=np.zeros(3); all_energy=0.
        for row in rows:
            weight=float(row['weight']); key=(layer,int(row['expert']))
            full+=weight*row['y'][0].astype(np.float64)
            reduced+=weight*row['y'][5:8].astype(np.float64)
            mass+=abs(weight); geo=A.geometry(int(row['gu']),int(row['down']))
            full_bytes+=geo['full_expert_weight_bytes']; h=row['h'].astype(np.float64)
            all_energy+=float(h@h)
            if key not in bank:
                assert row['cold']==1
                missing+=abs(weight);traffic+=geo['full_expert_weight_bytes'];energy+=h@h
            else:
                assert row['cold']==0
                for m in range(3):
                    mask=bank[key][m].astype(bool)
                    traffic[m]+=A.mask_footprint(np.flatnonzero(mask),geo)['weight_bytes']
                    energy[m]+=h[mask]@h[mask]
        den=np.linalg.norm(full); assert den>0 and mass>0
        errors=np.linalg.norm(reduced-full,axis=1)/den
        by_pos[pos].append({'layer':layer,'errors':errors.tolist(),'missing_weight_fraction':missing/mass,
                            'weight_bytes_fraction':(traffic/full_bytes).tolist(),
                            'retained_h_energy':(energy/all_energy).tolist()})
    curve=[]
    for pos,layers in sorted(by_pos.items()):
        assert len(layers)==4
        curve.append({'pos':pos,'age':pos-first_pos+1,'layers':layers,
                      'mean_layer_relative_l2':np.mean([x['errors'] for x in layers],axis=0).tolist(),
                      'max_layer_relative_l2':np.max([x['errors'] for x in layers],axis=0).tolist(),
                      'mean_missing_route_weight':float(np.mean([x['missing_weight_fraction'] for x in layers]))})
    assert curve and [x['pos'] for x in curve]==list(range(first_pos,curve[-1]['pos']+1))
    return curve

def read_bank(path):
    raw=path.read_bytes()
    assert raw[:8]==b'SNM10001' and len(raw)>=16
    ff,count=struct.unpack('<II',raw[8:16])
    assert ff==640 and 1<=count<=2048 and len(raw)==16+count*(8+1920)
    bank={}
    for i in range(count):
        at=16+i*(8+1920); key=struct.unpack('<ii',raw[at:at+8])
        assert key[0] in (0,1,35,36) and 0<=key[1]<512 and key not in bank
        masks=np.frombuffer(raw[at+8:at+8+1920],dtype=np.uint8).reshape(3,640)
        assert np.all(masks<=1);bank[key]=masks
    return bank

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='action',required=True)
    build=sub.add_parser('build-bank');build.add_argument('--candidates',nargs=10,type=Path,required=True)
    build.add_argument('--start',type=int,required=True);build.add_argument('--masks',type=Path,required=True)
    build.add_argument('--out',type=Path,required=True)
    check=sub.add_parser('evaluate');check.add_argument('--replay',type=Path,required=True)
    check.add_argument('--masks',type=Path,required=True);check.add_argument('--start',type=int,required=True)
    check.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if args.action=='build-bank':
        _,result=make_bank(args.candidates,args.start,args.masks)
    else:
        result={'mask_sha256':sha(args.masks),'replay_sha256':sha(args.replay),
                'curve':evaluate(args.replay,read_bank(args.masks),args.start)}
    save(args.out,result)

if __name__=='__main__':main()
