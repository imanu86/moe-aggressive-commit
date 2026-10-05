"""Partial download of a sharded GGUF from Hugging Face: headers + the first N experts of a few layers.

HTTP range requests only. Writes a small "slice" GGUF holding blk.L.ffn_{gate,up,down}_exps.weight with
ne[2] = N (same names, types and row layout as the source) plus a manifest with every layer's tensor types.

    python hf_slice.py --repo R --rev SHA --files a.gguf b.gguf --layers 0 1 35 --experts 48 --out slice.gguf
"""
import argparse, hashlib, json, struct, sys, time
import urllib.request

# (block size, bytes per block); 42 is this fork's Q2_0
QS = {0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22), 7: (32, 24), 8: (32, 34), 10: (256, 84),
      11: (256, 110), 12: (256, 144), 13: (256, 176), 14: (256, 210), 16: (256, 66), 17: (256, 74), 18: (256, 98),
      19: (256, 50), 20: (32, 18), 21: (256, 110), 22: (256, 82), 23: (256, 136), 29: (256, 56), 30: (1, 2),
      39: (32, 17), 42: (64, 18)}


def get(url, a, b, tries=5, allow_short=False):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={'Range': f'bytes={a}-{b}', 'User-Agent': 'strata-slice/1'})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) != b - a + 1 and not (allow_short and data):
                raise IOError(f'short read {len(data)} of {b - a + 1}')
            return data
        except Exception as e:
            print(f'  retry {t + 1}: {e}', flush=True)
            time.sleep(2 + 3 * t)
    raise SystemExit(f'download failed: {url} {a}-{b}')


class Buf:
    def __init__(self, data): self.d, self.p = data, 0
    def take(self, n):
        if self.p + n > len(self.d): raise EOFError
        v = self.d[self.p:self.p + n]; self.p += n; return v
    def u(self, fmt): return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))[0]
    def s(self): return self.take(self.u('Q')).decode('utf-8', 'replace')


SC = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}


def val(b, t):
    if t in SC: return b.u(SC[t])
    if t == 8: return b.s()
    if t == 9:
        et, n = b.u('I'), b.u('Q')
        if et in SC:
            b.take(struct.calcsize('<' + SC[et]) * n); return f'<array {n}>'
        return [val(b, et) for _ in range(n)] if n < 64 else [val(b, et) for _ in range(n)] and f'<array {n}>'
    raise ValueError(f'kv type {t}')


def parse(data):
    b = Buf(data)
    assert b.take(4) == b'GGUF'
    ver, nt, nkv = b.u('I'), b.u('Q'), b.u('Q')
    kv = {}
    for _ in range(nkv):
        k = b.s(); t = b.u('I'); kv[k] = (t, val(b, t))
    tens = []
    for _ in range(nt):
        name = b.s(); nd = b.u('I'); ne = [b.u('Q') for _ in range(nd)]; ty = b.u('I'); off = b.u('Q')
        tens.append(dict(name=name, ne=ne, type=ty, off=off))
    align = kv.get('general.alignment', (4, 32))[1]
    start = (b.p + align - 1) // align * align
    return ver, kv, tens, start


def header(url):
    n = 8 << 20
    while True:
        data = get(url, 0, n - 1, allow_short=True)
        try:
            return parse(data)
        except EOFError:
            if len(data) < n:
                raise SystemExit(f'header oltre la fine del file ({len(data)} byte)')
            n *= 2
            print(f'  header > {n >> 21} MiB, rileggo {n >> 20} MiB', flush=True)


def write_slice(path, arch, tensors):
    align = 32
    out = bytearray(b'GGUF') + struct.pack('<IQQ', 3, len(tensors), 2)
    def s(x): x = x.encode(); return struct.pack('<Q', len(x)) + x
    out += s('general.architecture') + struct.pack('<I', 8) + s(arch)
    out += s('general.alignment') + struct.pack('<II', 4, align)
    off = 0
    offs = []
    for t in tensors:
        offs.append(off)
        out += s(t['name']) + struct.pack('<I', len(t['ne'])) + b''.join(struct.pack('<Q', x) for x in t['ne'])
        out += struct.pack('<IQ', t['type'], off)
        off = (off + len(t['data']) + align - 1) // align * align
    out += b'\0' * ((-len(out)) % align)
    for t, o in zip(tensors, offs):
        out += t['data'] + b'\0' * ((-len(t['data'])) % align)
    with open(path, 'wb') as f:
        f.write(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--rev', required=True)
    ap.add_argument('--files', nargs='+', required=True)
    ap.add_argument('--layers', nargs='+', type=int, required=True)
    ap.add_argument('--experts', type=int, default=48)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    base = f'https://huggingface.co/{a.repo}/resolve/{a.rev}/'
    found, layer_types, arch, total = {}, {}, None, 0
    for fn in a.files:
        url = base + fn
        print(f'header {fn}', flush=True)
        ver, kv, tens, start = header(url)
        arch = arch or kv.get('general.architecture', (8, '?'))[1]
        print(f'  v{ver}, {len(tens)} tensori, dati da {start}', flush=True)
        for t in tens:
            if t['name'].startswith('blk.') and ('_exps' in t['name'] or 'ffn' in t['name']):
                L = int(t['name'].split('.')[1])
                layer_types.setdefault(L, {})[t['name'].split('.', 2)[2]] = [t['type'], t['ne']]
            found[t['name']] = dict(t, url=url, abs=start + t['off'], file=fn)
    picked = []
    for L in a.layers:
        for role in ('gate', 'up', 'down'):
            name = f'blk.{L}.ffn_{role}_exps.weight'
            t = found.get(name)
            if t is None:
                raise SystemExit(f'manca {name}; tensori dello strato: {sorted(layer_types.get(L, {}))}')
            blk, tsz = QS[t['type']]
            per = t['ne'][0] // blk * tsz * t['ne'][1]
            n = min(a.experts, t['ne'][2])
            print(f'scarico {name} tipo {t["type"]} {t["ne"]} -> {n} esperti, {n * per / 2**20:.1f} MiB', flush=True)
            data = bytearray()
            chunk = 32 << 20
            p0, p1 = t['abs'], t['abs'] + n * per
            while p0 < p1:
                q = min(p1, p0 + chunk)
                data += get(t['url'], p0, q - 1)
                p0 = q
            total += len(data)
            picked.append(dict(name=name, ne=[t['ne'][0], t['ne'][1], n], type=t['type'], data=bytes(data),
                               src=dict(file=t['file'], offset=t['abs'], src_ne=t['ne'])))
    write_slice(a.out, arch, picked)
    man = dict(repo=a.repo, rev=a.rev, files=a.files, experts=a.experts, arch=arch, downloaded_bytes=total,
               tensors=[dict(name=p['name'], type=p['type'], ne=p['ne'], sha256=hashlib.sha256(p['data']).hexdigest(),
                             **p['src']) for p in picked],
               layer_types={str(k): v for k, v in sorted(layer_types.items())})
    with open(a.out + '.json', 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1)
    print(f'scritto {a.out}: {total / 2**20:.1f} MiB di esperti', flush=True)


if __name__ == '__main__':
    main()
