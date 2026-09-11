"""Legge SOLO l'intestazione dei GGUF remoti (richieste a range), niente pesi."""
import struct, sys, re, json, collections, urllib.request

sys.path.insert(0, r'D:/llama-vision-upstream/gguf-py')
try:
    from gguf.constants import GGMLQuantizationType, GGML_QUANT_SIZES
except Exception as e:  # pragma: no cover
    print('gguf-py non disponibile:', e)
    GGMLQuantizationType, GGML_QUANT_SIZES = None, {}

REPO = sys.argv[1] if len(sys.argv) > 1 else 'vcruz305/DeepSeek-V4.1-Flash-GGUF'
PATTERN = sys.argv[2] if len(sys.argv) > 2 else 'Q2_K'
UA = 'curl/8.5'


class NeedMore(Exception):
    pass


def fetch(url, n):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Range': 'bytes=0-%d' % (n - 1)})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


class R:
    def __init__(self, b):
        self.b, self.p = b, 0

    def take(self, n):
        if self.p + n > len(self.b):
            raise NeedMore()
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]

    def u64(self):
        return struct.unpack('<Q', self.take(8))[0]

    def s(self):
        return self.take(self.u64()).decode('utf-8', 'replace')


SCALAR = {0: ('<B', 1), 1: ('<b', 1), 2: ('<H', 2), 3: ('<h', 2), 4: ('<I', 4), 5: ('<i', 4), 6: ('<f', 4),
          7: ('<?', 1), 10: ('<Q', 8), 11: ('<q', 8), 12: ('<d', 8)}


def val(r, t):
    if t in SCALAR:
        f, n = SCALAR[t]
        return struct.unpack(f, r.take(n))[0]
    if t == 8:
        return r.s()
    if t == 9:
        et, cnt = r.u32(), r.u64()
        if et in SCALAR:
            r.take(SCALAR[et][1] * cnt)
            return '<array %d x t%d>' % (cnt, et)
        first = []
        for i in range(cnt):
            v = val(r, et)
            if i < 2:
                first.append(v)
        return '<array %d x t%d: %s ...>' % (cnt, et, first)
    raise ValueError('tipo kv %d' % t)


def parse(b):
    r = R(b)
    if r.take(4) != b'GGUF':
        raise ValueError('magic')
    ver, nt, nkv = r.u32(), r.u64(), r.u64()
    kv = {}
    for _ in range(nkv):
        k = r.s()
        kv[k] = val(r, r.u32())
    tensors = []
    for _ in range(nt):
        name = r.s()
        nd = r.u32()
        dims = [r.u64() for _ in range(nd)]
        ty, off = r.u32(), r.u64()
        tensors.append((name, dims, ty, off))
    return ver, kv, tensors


def tname(ty):
    try:
        return GGMLQuantizationType(ty).name
    except Exception:
        return 'T%d' % ty


def nbytes(dims, ty):
    ne = 1
    for d in dims:
        ne *= d
    try:
        bs, ts = GGML_QUANT_SIZES[GGMLQuantizationType(ty)]
        return ne, ne // bs * ts
    except Exception:
        return ne, None


def categoria(name):
    m = re.match(r'blk\.(\d+)\.', name)
    L = int(m.group(1)) if m else None
    if 'engram' in name:
        return 'engram_tabella' if 'embd' in name or 'embed' in name else 'engram_altro'
    if 'nextn' in name or 'mtp' in name or 'dspark' in name or (L is not None and L >= 40):
        return 'mtp/dspark'
    if re.search(r'ffn_(gate|up|down)_exps', name):
        return 'esperti_' + re.search(r'ffn_(gate|up|down)_exps', name).group(1)
    if name.startswith(('token_embd', 'output.')):
        return 'embed/head'
    if name.startswith(('v.', 'mm.')):
        return 'visione'
    return 'denso'


tree = json.loads(urllib.request.urlopen(urllib.request.Request(
    'https://huggingface.co/api/models/%s/tree/main?recursive=1' % REPO, headers={'User-Agent': UA}), timeout=120).read())
parts = sorted([x for x in tree if x.get('type') == 'file' and x['path'].endswith('.gguf') and PATTERN in x['path']],
               key=lambda x: x['path'])
print('repo', REPO, 'pattern', PATTERN, 'parti', len(parts), 'GiB %.2f' % (sum(x['size'] for x in parts) / 2**30))

agg = collections.defaultdict(lambda: [0, 0, 0])
kv_first = None
letti = 0
for x in parts:
    url = 'https://huggingface.co/%s/resolve/main/%s' % (REPO, x['path'])
    n = 1 << 20
    while True:
        b = fetch(url, n)
        try:
            ver, kv, tensors = parse(b)
            break
        except NeedMore:
            if n >= 64 << 20:
                raise
            n *= 4
    letti += len(b)
    if kv_first is None:
        kv_first = kv
    print('  %-70s header letto %6.1f MiB, tensori %d' % (x['path'], len(b) / 2**20, len(tensors)))
    for name, dims, ty, off in tensors:
        ne, nb = nbytes(dims, ty)
        a = agg[(categoria(name), tname(ty))]
        a[0] += 1
        a[1] += ne
        a[2] += nb or 0

print('\nbyte letti in tutto: %.1f MiB' % (letti / 2**20))
print('\n=== metadati (prima parte)')
for k, v in kv_first.items():
    if k.startswith('tokenizer.'):
        continue
    if any(s in k for s in ('general.', 'split.', 'quantize', 'imatrix', 'engram', 'expert', 'block_count', 'file_type')):
        print('  %s = %s' % (k, v))
print('\n=== tipi per categoria')
tot = 0
for (c, t), (n, ne, nb) in sorted(agg.items()):
    tot += nb
    print('  %-16s %-8s n=%5d  param %8.3fB  %9.3f GiB  bpw %.3f' % (c, t, n, ne / 1e9, nb / 2**30, nb * 8 / ne if ne else 0))
print('TOTALE tensori: %.3f GiB' % (tot / 2**30))
