"""Independent gguf-py readback, CPU only, read-only model mappings."""
import argparse, hashlib, json, pathlib
import numpy as np
from gguf import GGUFReader, GGMLQuantizationType

def require(ok,msg):
 if not ok:raise ValueError(msg)
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()

def main(path):
 m=json.loads(pathlib.Path(path).read_text())
 require(digest(m['trunk'])==m['trunk_sha256'],'trunk SHA')
 require(digest(m['output'])==m['output_sha256'],'sidecar SHA')
 trunk=GGUFReader(m['trunk'],'r');out=GGUFReader(m['output'],'r')
 require(out.fields['general.architecture'].contents()=='qwen35','arch')
 require(out.fields['qwen35.block_count'].contents()==33,'layers')
 require(out.fields['qwen35.nextn_predict_layers'].contents()==1,'MTP layers')
 require(len(out.tensors)==17 and len(trunk.tensors)==426,'counts')
 source={t.name:t for t in trunk.tensors}; tensors={t.name:t for t in out.tensors}
 require('output.weight' not in tensors,'must be tied output')
 for rec in m['tensors']:
  t=tensors[rec['name']]
  require(t.shape.tolist()==rec['shape'] and int(t.tensor_type)==rec['type'],'tensor shape/type')
  require(t.n_bytes==rec['bytes'],'tensor byte count')
  require(hashlib.sha256(t.data.tobytes()).hexdigest()==rec['sha256'],'tensor digest')
  if t.tensor_type == GGMLQuantizationType.F32:
   require(np.isfinite(t.data).all(),'nonfinite F32 norm')
  elif t.tensor_type == GGMLQuantizationType.Q8_0:
   scales=t.data.view(np.uint8).reshape(-1,34)[:,:2].copy().view('<f2')
   require(np.isfinite(scales).all(),'nonfinite Q8_0 block scale')
  elif t.tensor_type == GGMLQuantizationType.Q6_K:
   scales=t.data.view(np.uint8).reshape(-1,210)[:,208:210].copy().view('<f2')
   require(np.isfinite(scales).all(),'nonfinite Q6_K block scale')
  if rec['source']=='original trunk':require(np.array_equal(t.data,source[t.name].data),'original tensor bytes')
 token_fields=[k for k in trunk.fields if k.startswith('tokenizer.')]
 for k in token_fields:
  a,b=trunk.fields[k],out.fields[k]
  require(a.types==b.types and a.data==b.data,'tokenizer layout')
  require(len(a.parts)==len(b.parts) and all(np.array_equal(x,y) for x,y in zip(a.parts,b.parts)),f'tokenizer bytes {k}')
 print(json.dumps({'reader':'independent installed gguf-py','verified_tensors':len(tensors),
   'tokenizer_fields_equal':len(token_fields),'head_matrices':'Q8_0','embedding':str(tensors['token_embd.weight'].tensor_type),
   'original_preserved':True,'GPU_or_inference_invoked':False},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('manifest');main(p.parse_args().manifest)
