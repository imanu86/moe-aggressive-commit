import json, os, time
from huggingface_hub import get_safetensors_metadata

S = os.path.dirname(os.path.abspath(__file__))
R = 'deepseek-ai/DeepSeek-V4.1-Flash'
t0 = time.time()
md = get_safetensors_metadata(R)
out = {}
for fname, fm in md.files_metadata.items():
    for tname, ti in fm.tensors.items():
        a, b = ti.data_offsets
        out[tname] = dict(file=fname, dtype=ti.dtype, shape=list(ti.shape), nbytes=b - a)
json.dump(out, open(os.path.join(S, 'tensors.json'), 'w'))
print('tensors', len(out), 'files', len(md.files_metadata), 'secs', round(time.time() - t0, 1))
print('parameter_count by dtype (HF, stored elements):', md.parameter_count)
by_dtype = {}
for v in out.values():
    by_dtype[v['dtype']] = by_dtype.get(v['dtype'], 0) + v['nbytes']
print('bytes by dtype:', {k: '%.3f GiB' % (x / 2**30) for k, x in by_dtype.items()})
print('total tensor bytes', sum(by_dtype.values()), '%.3f GiB' % (sum(by_dtype.values()) / 2**30))
