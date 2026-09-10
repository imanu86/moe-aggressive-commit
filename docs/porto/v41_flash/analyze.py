import json, re, collections, os

S = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(S, 'tensors.json'), encoding='utf-8'))
N_LAYERS = 40
GiB = 2**30


def numel(shape):
    n = 1
    for d in shape:
        n *= d
    return n


# ---------- 1) patterns with shapes ----------
pat = collections.defaultdict(lambda: [0, 0, 0, None])
for name, v in T.items():
    g = re.sub(r'(?<=\.)\d+(?=\.)', '#', name)
    p = pat[(g, v['dtype'])]
    p[0] += 1
    p[1] += numel(v['shape'])
    p[2] += v['nbytes']
    if p[3] is None:
        p[3] = v['shape']
print('=== patterns: count dtype stored_elements GiB pattern example_shape ===')
for (g, dt), (c, ne, nb, exs) in sorted(pat.items()):
    print('%6d %-8s %14d %9.3f  %-75s %s' % (c, dt, ne, nb / GiB, g, exs))


# ---------- 2) categories ----------
def layer_of(n):
    m = re.search(r'layers\.(\d+)\.', n)
    return int(m.group(1)) if m else None


def cat_of(name, v):
    n = name.lower()
    L = layer_of(n)
    is_scale = v['dtype'] == 'F8_E8M0' or n.endswith('scale') or 'scale_inv' in n
    if any(k in n for k in ('vision', 'visual', 'vit.', 'projector', 'patch_embed', 'mm_')):
        c = 'vision'
    elif any(k in n for k in ('dspark', 'mtp', 'nextn', 'draft')) or (L is not None and L >= N_LAYERS):
        c = 'draft_experts' if re.search(r'experts\.\d+\.', n) else 'draft_other'
    elif 'engram' in n:
        c = 'engram_table' if numel(v['shape']) >= 10**8 else 'engram_other'
    elif re.search(r'experts\.\d+\.', n):
        c = 'routed'
    elif 'shared' in n:
        c = 'shared'
    elif 'embed' in n:
        c = 'embed'
    elif 'lm_head' in n or n.startswith('head.'):
        c = 'head'
    elif re.search(r'\.gate\.(weight|bias)', n) or 'e_score_correction' in n or 'router' in n or 'tid2eid' in n:
        c = 'router'
    else:
        c = 'dense_other'
    return c, is_scale


cat = collections.defaultdict(lambda: dict(n=0, stored_bytes=0, scale_bytes=0, logical=0, logical_2d=0, logical_1d=0))
routed_proj = collections.Counter()
for name, v in T.items():
    c, sc = cat_of(name, v)
    d = cat[c]
    d['n'] += 1
    d['stored_bytes'] += v['nbytes']
    if sc:
        d['scale_bytes'] += v['nbytes']
        continue
    ne = numel(v['shape']) * (2 if v['dtype'] == 'I8' else 1)  # FP4 packed two per byte
    d['logical'] += ne
    if len(v['shape']) >= 2 and min(v['shape']) > 1:
        d['logical_2d'] += ne
    else:
        d['logical_1d'] += ne
    if c == 'routed':
        leaf = name.split('experts.')[1].split('.', 1)[1]
        routed_proj[leaf] += ne

print()
print('=== categories: tensors, release GiB (scales incl.), logical params ===')
tot_l = tot_b = 0
for c, d in sorted(cat.items(), key=lambda x: -x[1]['stored_bytes']):
    tot_l += d['logical']
    tot_b += d['stored_bytes']
    print('%-14s n=%6d  release %8.3f GiB (scales %6.3f)  params %8.3fB  (2D %8.3fB, 1D %.4fB)' % (
        c, d['n'], d['stored_bytes'] / GiB, d['scale_bytes'] / GiB, d['logical'] / 1e9, d['logical_2d'] / 1e9, d['logical_1d'] / 1e9))
print('TOTAL release %.3f GiB, logical params %.3fB' % (tot_b / GiB, tot_l / 1e9))
print('routed leaves (logical params):', {k: '%.3fB' % (x / 1e9) for k, x in routed_proj.items()})

# ---------- 3) GGUF projections ----------
BPW = dict(IQ2_XXS=2.0625, IQ2_XS=2.3125, IQ2_S=2.5, IQ2_M=2.7, IQ3_XXS=3.0625, Q2_K=2.625, IQ4_XS=4.25,
           Q4_K=4.5, Q6_K=6.5625, Q8_0=8.5, F16=16.0, F32=32.0)


def gb(params, bpw):
    return params * bpw / 8


def routed_bytes(recipe):
    tot = 0
    for leaf, ne in routed_proj.items():
        kind = 'down' if ('down' in leaf or leaf.startswith('w2')) else 'gateup'
        if recipe == 'REF':  # prometheusAIR Vision-Exp: gate/up IQ2_XXS, down 23/43 IQ2_XS + 20/43 IQ3_XXS
            b = BPW['IQ2_XXS'] if kind == 'gateup' else (23 * BPW['IQ2_XS'] + 20 * BPW['IQ3_XXS']) / 43
        else:
            b = BPW[recipe]
        tot += gb(ne, b)
    return tot


def dense_bytes(c, q2d='Q6_K', q1d='F32'):
    d = cat[c]
    return gb(d['logical_2d'], BPW[q2d]) + gb(d['logical_1d'], BPW[q1d])


rest = (dense_bytes('dense_other') + dense_bytes('shared') + dense_bytes('router', 'F16') +
        dense_bytes('embed', 'Q8_0') + dense_bytes('head', 'Q8_0') + dense_bytes('engram_other', 'Q8_0'))
print()
print('=== GGUF projection, main LLM without Engram tables / vision / draft ===')
print('non-expert rest (attn/indexer/hc Q6_K, shared Q6_K, router F16, embed+head Q8_0, engram gates Q8_0): %.3f GiB' % (rest / GiB))
for r in ('REF', 'IQ2_XXS', 'IQ2_XS', 'IQ2_M'):
    rb = routed_bytes(r)
    print('  experts %-8s %8.3f GiB  -> backbone total %8.3f GiB  (%.1f GB)' % (r, rb / GiB, (rb + rest) / GiB, (rb + rest) / 1e9))

et = cat['engram_table']['logical']
print()
print('=== Engram tables (%.3fB params) ===' % (et / 1e9))
for q in ('F16', 'Q8_0', 'Q6_K', 'Q4_K', 'IQ4_XS', 'Q2_K', 'IQ2_XXS'):
    print('  %-8s %8.3f GiB  (%.1f GB)' % (q, gb(et, BPW[q]) / GiB, gb(et, BPW[q]) / 1e9))

vis = dense_bytes('vision', 'F16')
print()
print('vision mmproj F16: %.3f GiB (%.3fB params)' % (vis / GiB, cat['vision']['logical'] / 1e9))
de = cat['draft_experts']['logical']
dr = dense_bytes('draft_other')
print('draft (DSpark/MTP): experts %.3fB -> Q2_K %.3f GiB, IQ2_XXS %.3f GiB; rest Q6_K %.3f GiB' % (
    de / 1e9, gb(de, BPW['Q2_K']) / GiB, gb(de, BPW['IQ2_XXS']) / GiB, dr / GiB))

# ---------- 4) expert bytes per token vs Vision-Exp reference ----------
ref = json.load(open(os.path.join(S, 'gguf_ref_rows.json'), encoding='utf-8'))
ref_routed = sum(r['n_bytes'] for r in ref if r['kind'] == 'llm' and re.match(r'blk\.#\.ffn_(gate|up|down)_exps\.weight$', r['pattern']))
ref_per_expert = ref_routed / (43 * 256)
n_exp = 384
per_expert = routed_bytes('REF') / (N_LAYERS * n_exp)
print()
print('=== routed expert bytes per token (6 experts/layer) ===')
print('Vision-Exp IQ2 ref: per expert %.2f MiB, decode 43 layers %.3f GiB/token' % (ref_per_expert / 2**20, 43 * 6 * ref_per_expert / GiB))
print('V4.1 REF recipe   : per expert %.2f MiB, decode 40 layers %.3f GiB/token, prefill 20 enc layers %.3f GiB/token' % (
    per_expert / 2**20, 40 * 6 * per_expert / GiB, 20 * 6 * per_expert / GiB))
