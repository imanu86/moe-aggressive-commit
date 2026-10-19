import zstandard, io, json, sys, glob, os
def lines(path):
    d = zstandard.ZstdDecompressor()
    with open(path,'rb') as f, d.stream_reader(f, read_across_frames=True) as r:
        buf = b''
        while True:
            ch = r.read(1<<20)
            if not ch: break
            buf += ch
            parts = buf.split(b'\n'); buf = parts.pop()
            for p in parts:
                if p.strip(): yield json.loads(p)
        if buf.strip(): yield json.loads(buf)
if __name__=='__main__':
    import collections
    p=sys.argv[1]
    keys=collections.Counter(); types=collections.Counter(); n=0
    for r in lines(p):
        n+=1; keys.update(r.keys()); types[str(r.get('type'))]+=1
    print(n, dict(keys.most_common(20)), dict(types.most_common(20)))
