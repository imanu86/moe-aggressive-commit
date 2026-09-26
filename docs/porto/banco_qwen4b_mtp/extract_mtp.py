"""CPU-only standalone dense Qwen3.5 MTP extraction. Never loads inference engines.
Remote tensors are fetched ONLY with strict, bounded HTTP ranges from pinned GGUF.
Original trunk is opened read-only and its complete SHA256 is checked twice.
"""
import argparse, hashlib, io, json, math, os, pathlib, re, struct, urllib.request

TRUNK_SHA = '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
REPO = 'unsloth/Qwen3.5-4B-MTP-GGUF'
REV = '86835bf9949e4d14d6860f7910b1340ad4f271a9'
DONOR = 'Qwen3.5-4B-Q8_0.gguf'
MAX_HEADER = 32 * 1024**2
CHUNK = 1024**2
MAX_SEGMENT = 32 * 1024**2
EXPECTED = {
 'attn_norm': [2560], 'post_attention_norm': [2560],
 'attn_q': [2560,8192], 'attn_k': [2560,1024], 'attn_v': [2560,1024],
 'attn_output': [4096,2560], 'attn_q_norm': [256], 'attn_k_norm': [256],
 'ffn_gate': [2560,9216], 'ffn_up': [2560,9216], 'ffn_down': [9216,2560],
 'nextn.eh_proj': [5120,2560], 'nextn.enorm': [2560],
 'nextn.hnorm': [2560], 'nextn.shared_head_norm': [2560],
}
EXPECTED = {'blk.32.'+k+'.weight':v for k,v in EXPECTED.items()}

def sha(data): return hashlib.sha256(data).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''): h.update(b)
 return h.hexdigest()
def require(ok,msg):
 if not ok: raise ValueError(msg)
def packstr(s):
 b=s.encode('utf-8'); return struct.pack('<Q',len(b))+b

def public_json(url):
 with urllib.request.urlopen(url, timeout=60) as r:
  require(r.status==200,'metadata HTTP status')
  data=r.read(2*1024**2+1)
  require(len(data)<=2*1024**2,'metadata exceeds bound')
 return json.loads(data)

class Remote:
 def __init__(self,cache,size):
  self.cache=cache; self.size=size; self.pos=0; self.header=bytearray(); self.records=[]
  self.url=f'https://huggingface.co/{REPO}/resolve/{REV}/{DONOR}'
 def fetch(self,start,length):
  require(0<length<=MAX_SEGMENT and start>=0 and start+length<=self.size,'range bounds')
  end=start+length-1; p=self.cache/f'{start:012d}-{end:012d}.bin'; proof=p.with_suffix('.json')
  if p.exists() and proof.exists():
   rec=json.loads(proof.read_text()); data=p.read_bytes()
   require(rec['url']==self.url and rec['start']==start and rec['end']==end and
           rec['total']==self.size and len(data)==length and sha(data)==rec['sha256'], 'cached range proof mismatch')
  else:
   req=urllib.request.Request(self.url+f'?download=true&range_start={start}&range_end={end}',
      headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
   with urllib.request.urlopen(req,timeout=120) as r:
    # Reject HTTP 200 BEFORE reading any body. Never silently download the full model.
    require(r.status==206,f'Range ignored, status {r.status}')
    cr=r.headers.get('Content-Range','')
    require(cr==f'bytes {start}-{end}/{self.size}',f'Content-Range mismatch: {cr}')
    require(r.headers.get('Content-Encoding','identity')=='identity','encoded range')
    cl=r.headers.get('Content-Length')
    if cl is not None: require(int(cl)==length,'Content-Length mismatch')
    data=r.read(length+1)
    require(len(data)==length,'short/oversized bounded range')
   rec={'url':self.url,'start':start,'end':end,'total':self.size,'http_status':206,
        'content_range':cr,'sha256':sha(data)}
   with p.open('xb') as f:f.write(data)
   with proof.open('x') as f:json.dump(rec,f,indent=2)
  self.records.append(rec)
  return data
 def read(self,n):
  require(n>=0 and self.pos+n<=MAX_HEADER,'GGUF header exceeds bound')
  need=self.pos+n
  while len(self.header)<need:
   at=len(self.header); self.header.extend(self.fetch(at,min(CHUNK,self.size-at)))
  b=bytes(self.header[self.pos:need]); self.pos=need; return b
 def tell(self):return self.pos
 def seek(self,p):self.pos=p

def exact(f,n):
 b=f.read(n); require(len(b)==n,'truncated GGUF'); return b

def u(f,fmt):return struct.unpack('<'+fmt,exact(f,struct.calcsize('<'+fmt)))[0]
def string(f):
 n=u(f,'Q'); require(n<=MAX_HEADER,'oversized string'); return exact(f,n).decode('utf-8')
def value(f,t,keep=True):
 types={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
 if t in types:return u(f,types[t])
 if t==8:return string(f)
 if t==9:
  subtype=u(f,'I'); count=u(f,'Q'); require(count<=2000000,'oversized array')
  require(subtype!=9,'nested array unsupported')
  for _ in range(count):value(f,subtype,False)
  return {'array_type':subtype,'count':count}
 raise ValueError(f'unknown GGUF value type {t}')

def parse(f):
 require(exact(f,4)==b'GGUF','GGUF magic'); version=u(f,'I'); require(version==3,'GGUF version')
 nt,nk=u(f,'Q'),u(f,'Q'); require(nt<10000 and nk<10000,'header counts')
 fields={}
 for _ in range(nk):
  start=f.tell(); key=string(f); typ=u(f,'I'); val=value(f,typ); end=f.tell()
  f.seek(start); raw=exact(f,end-start)
  require(key not in fields,'duplicate metadata')
  fields[key]={'type':typ,'value':val,'raw':raw}
 tensors={}
 for _ in range(nt):
  name=string(f); ndim=u(f,'I'); require(0<ndim<=4,'ndim'); dims=[u(f,'Q') for _ in range(ndim)]
  typ=u(f,'I'); off=u(f,'Q'); require(name not in tensors,'duplicate tensor')
  tensors[name]={'name':name,'shape':dims,'type':typ,'offset':off}
 alignment=fields.get('general.alignment',{}).get('value',32)
 require(alignment==32,'unexpected GGUF alignment')
 base=(f.tell()+31)//32*32
 return fields,tensors,base

def nbytes(t):
 # Only the types that this extraction may copy. Fail closed on anything else.
 block,size={0:(1,4),8:(32,34),14:(256,210)}[t['type']]
 require(t['shape'][0]%block==0,'quantized row not aligned')
 return math.prod(t['shape'])//block*size

def modified(key,typ,val):
 if typ==8:b=packstr(val)
 elif typ==4:b=struct.pack('<I',val)
 else:raise ValueError('replacement type')
 return {'type':typ,'value':val,'raw':packstr(key)+struct.pack('<I',typ)+b}

def run(args):
 trunk=pathlib.Path(args.trunk); lab=pathlib.Path(args.lab); out=pathlib.Path(args.output)
 require(not out.exists(),'Refusing to replace existing sidecar')
 require(file_sha(trunk)==TRUNK_SHA,'original trunk SHA256 mismatch')
 lab.mkdir(parents=True,exist_ok=True); cache=lab/'ranges';cache.mkdir(exist_ok=True)
 with trunk.open('rb') as f:tf,tt,tbase=parse(f)
 require(len(tt)==426,'expected original trunk 426 tensors')
 require(tf['general.architecture']['value']=='qwen35','trunk architecture')
 require(tf['qwen35.block_count']['value']==32,'trunk block count')
 require(not any(n.startswith('blk.32.') for n in tt),'trunk unexpectedly contains MTP')
 require('output.weight' not in tt,'trunk must have tied output')
 require(tt['token_embd.weight']['shape']==[2560,248320] and tt['token_embd.weight']['type']==14,'embedding must be Q6_K [2560,248320]')
 require(tt['output_norm.weight']['shape']==[2560] and tt['output_norm.weight']['type']==0,'output norm must be F32 [2560]')
 listing=public_json(f'https://huggingface.co/api/models/{REPO}/tree/{REV}')
 entry=next(x for x in listing if x['path']==DONOR)
 require(entry['lfs']['size']==entry['size'],'LFS metadata size mismatch')
 with (lab/'donor-file-metadata.json').open('w') as f:json.dump(entry,f,indent=2)
 remote=Remote(cache,entry['size']); df,dt,dbase=parse(remote)
 require(df['general.architecture']['value']=='qwen35','donor architecture')
 require(df['qwen35.block_count']['value']==33,'donor block count')
 require(df['qwen35.nextn_predict_layers']['value']==1,'donor MTP count')
 actual={k:v for k,v in dt.items() if k.startswith('blk.32.')}
 require(set(actual)==set(EXPECTED),f'head name mismatch: {set(actual)^set(EXPECTED)}')
 for name,dims in EXPECTED.items():
  t=actual[name]; require(t['shape']==dims,f'geometry {name}: {t["shape"]} != {dims}')
  require(t['type']==(0 if len(dims)==1 else 8),f'expected F32 norms / Q8_0 matrices: {name}')
 # All structural architecture metadata must match, except explicit layer accounting.
 structural={k for k in tf if k.startswith('qwen35.')}-{ 'qwen35.block_count','qwen35.nextn_predict_layers'}
 for k in structural:
  require(k in df and tf[k]['raw']==df[k]['raw'],f'architecture metadata mismatch {k}')
 # Verify exact vocabulary/tokenizer, except template text (we always keep original).
 for k in tf:
  if k.startswith('tokenizer.') and k!='tokenizer.chat_template':
   require(k in df and tf[k]['raw']==df[k]['raw'],f'tokenizer mismatch {k}')
 fields=dict(tf)
 fields['qwen35.block_count']=modified('qwen35.block_count',4,33)
 fields['qwen35.nextn_predict_layers']=modified('qwen35.nextn_predict_layers',4,1)
 fields['general.name']=modified('general.name',8,'Qwen3.5-4B standalone MTP: Q8_0 head + original Q6_K tied embedding')
 fields['general.file_type']=modified('general.file_type',4,7) # MOSTLY_Q8_0; mixed embedding documented
 # Preserve original metadata/tokenizer verbatim, remove only stale split metadata if present.
 require(not any(k.startswith('split.') for k in fields),'split metadata not supported')
 blobs=[]; tensor_manifest=[]
 with trunk.open('rb') as f:
  for name in ('token_embd.weight','output_norm.weight'):
   t=tt[name]; length=nbytes(t); f.seek(tbase+t['offset']); b=exact(f,length)
   blobs.append((t,b)); tensor_manifest.append(dict(t,source='original trunk',source_absolute_offset=tbase+t['offset'],bytes=length,sha256=sha(b)))
 for name in sorted(actual):
  t=actual[name]; length=nbytes(t); start=dbase+t['offset']; parts=[]
  for at in range(0,length,MAX_SEGMENT):parts.append(remote.fetch(start+at,min(MAX_SEGMENT,length-at)))
  b=b''.join(parts); blobs.append((t,b)); tensor_manifest.append(dict(t,source='pinned third-party donor',source_absolute_offset=start,bytes=length,sha256=sha(b)))
 header=b'GGUF'+struct.pack('<IQQ',3,len(blobs),len(fields))+b''.join(v['raw'] for v in fields.values())
 offset=0; desc=[]
 for t,b in blobs:
  desc.append(packstr(t['name'])+struct.pack('<I',len(t['shape']))+struct.pack('<'+'Q'*len(t['shape']),*t['shape'])+struct.pack('<IQ',t['type'],offset))
  offset+=(len(b)+31)//32*32
 header+=b''.join(desc); header+=b'\0'*((-len(header))%32)
 temp=out.with_suffix(out.suffix+'.partial')
 with temp.open('xb') as f:
  f.write(header)
  for t,b in blobs:f.write(b);f.write(b'\0'*((-len(b))%32))
 # Independent read-back parse and per-tensor byte comparison; no inference or quantizer.
 with temp.open('rb') as f:
  of,ot,obase=parse(f)
  require(len(ot)==17 and 'output.weight' not in ot,'standalone tensor count/tied output')
  require(of['qwen35.block_count']['value']==33 and of['qwen35.nextn_predict_layers']['value']==1,'standalone metadata')
  for k in tf:
   if k.startswith('tokenizer.'):require(of[k]['raw']==tf[k]['raw'],f'original tokenizer lost: {k}')
  intervals=[]
  for rec in tensor_manifest:
   t=ot[rec['name']]; require(t['shape']==rec['shape'] and t['type']==rec['type'],'readback geometry/type')
   f.seek(obase+t['offset']);b=exact(f,rec['bytes']);require(sha(b)==rec['sha256'],'readback tensor hash')
   intervals.append((t['offset'],t['offset']+len(b)))
  intervals.sort(); require(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'overlapping output tensors')
  require(obase+max(x[1] for x in intervals)<=temp.stat().st_size,'output bounds')
 require(file_sha(trunk)==TRUNK_SHA,'trunk changed during extraction')
 output_sha=file_sha(temp); os.rename(temp,out)
 manifest={'format':'qwen4b-mtp-extraction/1','trunk':str(trunk),'trunk_sha256':TRUNK_SHA,
  'donor_repo':REPO,'donor_revision':REV,'donor_file':DONOR,'donor_full_sha256_reference':entry['lfs']['oid'],
  'donor_full_file_downloaded_or_hash_verified':False,'donor_size':entry['size'],
  'source_note':'Third-party preconverted Unsloth head; NOT independently compared to official BF16 weights.',
  'output':str(out),'output_sha256':output_sha,'output_bytes':out.stat().st_size,
  'tensor_count':len(blobs),'tokenizer_copied_verbatim':True,'architecture_metadata_matched':sorted(structural),
  'head_quantization':'Q8_0 matrices / F32 norms, no conversion applied','embedding':'Original byte-identical Q6_K, tied output',
  'ranges':remote.records,'downloaded_range_bytes':sum(x['end']-x['start']+1 for x in remote.records),
  'tensors':tensor_manifest,'checks':['full original SHA256 before and after','exact 15 head tensor names/shapes/types',
  'donor structural metadata matches trunk','tokenizer metadata copied byte-identically',
  '17 output tensor SHA256 readback checks','no output.weight; tied output','strict HTTP206 and bounded range reads'],
  'not_tested':['runtime loading','GPU inference','MTP acceptance','distribution equivalence','100k context compatibility']}
 with (lab/'manifest.json').open('w') as f:json.dump(manifest,f,indent=2)
 print(json.dumps({k:manifest[k] for k in ('output','output_sha256','output_bytes','tensor_count','downloaded_range_bytes')},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--trunk',required=True);p.add_argument('--lab',required=True);p.add_argument('--output',required=True)
 run(p.parse_args())
